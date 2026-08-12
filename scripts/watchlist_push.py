"""scripts/watchlist_push.py — 追蹤清單 → MoneyDJ 淨值 → LINE 推播(v19.438)

架構(依 user 提供的 watchlist_line_push spec):
    公開 CSV 追蹤清單 → 排程(GitHub Actions cron / NAS cron)→ 逐檔抓 MoneyDJ 淨值
    → 組訊息 → LINE Messaging API push → 手機收到。

**零 GCP 金鑰讀清單**:清單分頁「發布成公開 CSV」,排程用 plain HTTP GET 讀(spec §1)。
**LINE**:重用既有 `infra.line_push.push_text`(Messaging API,LINE Notify 已停用),
         沿用週報同一組 `LINE_CHANNEL_TOKEN` / `LINE_USER_ID`,不必另設 LINE 憑證。

⚠️ IP 限制(§1 誠實):GitHub Actions 跑在**美國 IP**,MoneyDJ/境外基金淨值從美國 IP 常抓不到。
   兩條可行路:(a) 設 `PROXY_URL` 走你的 NAS 代理(infra.proxy 自動吃);(b) 直接把本腳本掛
   NAS cron(台灣 IP 直連)。抓不到的檔誠實標「資料不足」,不捏造(§1)。

§ 設計原則(spec §6):Fail Loud（URL 未設 / 解析 0 項 → 非零 exit,不送空/假訊息);
  缺 LINE 憑證 → push 端回報不送(cron log 可見);log 不整段印例外(避免洩漏含 URL/token 的訊息);
  dry-run 先驗解析與訊息再實送。

環境變數(GitHub Actions secrets / NAS env):
    WATCH_CSV_URL          發布的 Google Sheet 追蹤清單 CSV 連結（必要）
    LINE_CHANNEL_TOKEN     LINE 官方帳號 channel access token（必要,同週報）
    LINE_USER_ID           你的 U 開頭 userId（必要,同週報）
    PROXY_URL              （選填）NAS 代理,讓美國 IP 也抓得到 MoneyDJ

CLI:
    python scripts/watchlist_push.py --dry-run   # 只印不送
    python scripts/watchlist_push.py             # 實送
"""
from __future__ import annotations

import argparse
import csv as _csv
import datetime as _dt
import io
import os
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── 清單項目格式:基金代號(英數 3~12 碼;fallback 掃描要求至少 1 個字母或 00 開頭 ETF,
#    以排除把「數量/金額」等純數字欄誤當代號)。header 命中「代號」欄則只讀該欄,最準。
_HEADER_KEYS = ("代號", "代碼", "基金代號", "股號", "ticker", "code", "symbol")
_ITEM_RE = re.compile(r"^[A-Za-z0-9]{2,12}$")
_HAS_ALPHA = re.compile(r"[A-Za-z]")
_LINE_MAX = 4900          # LINE 單則 5000,留 buffer;超長切多則


def extract_items_from_csv(text: str) -> list:
    """CSV 文字 → 去重後的基金代號清單。

    - 首列表頭含「代號/ticker/code…」→ **只讀那一欄**(避免把旁欄數字當代號)。
    - 否則 fallback:掃全表 cell,用 _ITEM_RE 挑合法 token(要求含字母或 00 開頭)。
    - 去 BOM、支援全形逗號/頓號分隔、去重、大寫正規化。
    """
    rows = list(_csv.reader(io.StringIO(text or "")))
    if not rows:
        return []
    seen: set = set()
    out: list = []

    def _add(tok: str, *, require_alpha: bool) -> None:
        c = str(tok).replace("﻿", "").strip().upper()
        if not _ITEM_RE.match(c):
            return
        if require_alpha and not (_HAS_ALPHA.search(c) or c.startswith("00")):
            return                       # fallback 掃描:排除純數字(數量/金額欄)
        if c not in seen:
            seen.add(c)
            out.append(c)

    header = [str(h).replace("﻿", "").strip().lower() for h in rows[0]]
    _keyset = {k.lower() for k in _HEADER_KEYS}
    # 先精確比對(避免 substring 誤中:如「備考code」把 code 欄搶去 index 0 → 漏掉真「代號」欄);
    # 精確找不到才退 substring(容「基金代號欄」這種變體)。
    col = next((i for i, h in enumerate(header) if h in _keyset), None)
    if col is None:
        col = next((i for i, h in enumerate(header)
                    if any(k in h for k in _keyset)), None)
    if col is not None:                  # 有表頭欄 → 只讀該欄(不要求含字母,尊重使用者填的)
        for r in rows[1:]:
            if col < len(r):
                _add(r[col], require_alpha=False)
        if out:
            return out
    for r in rows:                       # 無表頭 → 掃全表 token(含全形逗號/頓號)
        for cell in r:
            for tok in re.split(r"[\s,、，]+", str(cell)):
                _add(tok, require_alpha=True)
    return out


def fetch_csv(url: str, *, timeout: float = 30.0) -> str:
    """公開 CSV → 文字。非 200 raise(§1;訊息不含 url)。"""
    import requests
    r = requests.get(url, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"CSV HTTP {r.status_code}")
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def _default_fetch(code: str) -> dict:
    """App 已驗證的 MoneyDJ 抓取鏈(tab2/健診/累積器同一條)。"""
    from services.moneydj_fetcher import auto_fetch_moneydj
    return auto_fetch_moneydj(code) or {}


def _label(code: str, fd: dict) -> str:
    name = str((fd or {}).get("fund_name") or "").strip()
    return f"{code} {name}".strip() if name else code


def _series_latest(series):
    """序列 → (nav, date, 近5日漲跌字串)。抽不到 / nav<=0 / 非日期索引 → None(§1 不偽造)。

    守 index 型別:非日期(RangeIndex/NaT)→ date 非 YYYY-MM-DD → 不把假日期配真 nav。
    近5日需 t 與 t-5;不足則誠實省略(不猜)。
    """
    try:
        if series is not None and len(series) > 0:
            nav = float(series.iloc[-1])
            date = str(series.index[-1])[:10]
            if nav > 0 and re.match(r"^\d{4}-\d{2}-\d{2}$", date):
                chg = ""
                try:
                    if len(series) >= 6:
                        base = float(series.iloc[-6])
                        if base > 0:
                            chg = f" ｜近5日 {(nav / base - 1) * 100:+.1f}%"
                except (TypeError, ValueError):
                    chg = ""
                return nav, date, chg
    except Exception:  # noqa: BLE001 — 單檔壞不拖累整批
        pass
    return None


def _fund_line(code: str, fd: dict) -> str:
    """live MoneyDJ 淨值行:代號 名稱:淨值(日期) ｜近5日 ±x%。抓不到 → 「資料不足」(§1)。"""
    got = _series_latest((fd or {}).get("series"))
    if got is not None:
        nav, date, chg = got
        return f"• {_label(code, fd)}:{nav:.4f}（{date}）{chg}"
    return f"• {_label(code, fd)}:⚠️ 資料不足（抓不到 MoneyDJ 淨值）"


def _hist_line(code: str, fd: dict, series) -> "str | None":
    """live 抓不到時,退用 nav_history 累積序列**最近一筆**,誠實標『累積存檔』+ 真實日期。

    §1/§2.4:這不是今日 live 值,是已累積存檔的最近一筆(帶 as_of 日期),
    不偽造成當期;存檔序列稀疏 → 不報近5日(避免誤導)。抽不到 → None。
    """
    got = _series_latest(series)
    if got is None:
        return None
    nav, date, _chg = got
    return f"• {_label(code, fd)}:{nav:.4f}（{date}｜累積存檔）"


def _default_hist(code: str):
    """讀已累積的 nav_history 序列(Service Account;美國 IP 也讀得到)。未啟用 → 空 Series。"""
    from services.nav_history_gs import load_series
    return load_series(code)


def build_message(items: list, *, fetch_fn=None, hist_fn=None, as_of: str = "",
                  stats_out: "dict | None" = None) -> str:
    """逐檔抓 MoneyDJ 淨值 → 組推播文字。純資料驅動,缺料誠實標,不捏造(§1/spec §6-2)。

    hist_fn:opt-in 退路 — live 抓不到時,用它讀 nav_history 累積序列最近一筆(標『累積存檔』)。
        傳 None → 不退(build_message 保持純注入);main() 會帶入 `_default_hist`(讀 GS)。
        用途:GitHub Actions 美國 IP 抓不到 live MoneyDJ 時,仍能報**真實的**最近存檔淨值。
    stats_out:opt-in 側車 dict — 若傳入,填 {"total", "missing"} 供 caller 判斷全失敗
        (§5 可觀測;既有 caller 傳 None 行為零變化)。
    """
    if fetch_fn is None:
        fetch_fn = _default_fetch
    _as_of = as_of or _dt.datetime.now(
        _dt.timezone(_dt.timedelta(hours=8))).date().isoformat()
    lines = [f"📈 追蹤清單淨值（{_as_of}）", f"共 {len(items)} 檔", ""]
    _miss = 0
    _stale = 0
    for code in items:
        try:
            fd = fetch_fn(code)
        except Exception as _e:  # noqa: BLE001 — 抓取層錯誤 → 該檔標資料不足,不整批中斷
            print(f"  ⚠️ {code} 抓取失敗:{type(_e).__name__}")   # §3.3 留痕(只印型別)
            fd = {}
        line = _fund_line(code, fd)
        if "資料不足" in line and hist_fn is not None:      # live 抓不到 → 退累積存檔
            try:
                _s = hist_fn(code)
            except Exception as _e:  # noqa: BLE001 — nav_history I/O 失敗 → 放棄退路,不中斷
                print(f"  ⚠️ {code} nav_history 退路失敗:{type(_e).__name__}")
                _s = None
            _hl = _hist_line(code, fd, _s)
            if _hl is not None:
                line = _hl
                _stale += 1
        if "資料不足" in line:
            _miss += 1
        lines.append(line)
    _notes = []
    if _stale:
        _notes.append(f"🗂️ {_stale} 檔為累積存檔的最近一筆（非今日 live；美國 IP 抓不到即時值時的退路）。")
    if _miss:
        _notes.append(f"⚠️ {_miss} 檔完全無資料（live 與存檔都沒有；美國 IP 直連常擋 MoneyDJ，"
                      "可設 PROXY_URL 走 NAS 代理，或改在 NAS 端跑）。")
    if _notes:
        lines += [""] + _notes
    if stats_out is not None:
        stats_out["total"] = len(items)
        stats_out["missing"] = _miss
        stats_out["stale"] = _stale
    return "\n".join(lines)


def _chunks(text: str, n: int = _LINE_MAX) -> list:
    """依行切成 ≤n 字的塊;單行超長硬切(LINE 單則上限)。"""
    out: list = []
    buf = ""
    for line in str(text).split("\n"):
        if len(line) > n and buf:      # 先 flush 待送 buf,避免超長行的前段插到 buf 之前(順序亂)
            out.append(buf)
            buf = ""
        while len(line) > n:
            out.append(line[:n])
            line = line[n:]
        if buf and len(buf) + len(line) + 1 > n:
            out.append(buf)
            buf = line
        else:
            buf = (buf + "\n" + line) if buf else line
    if buf:
        out.append(buf)
    return out


def send(message: str, *, dry_run: bool = False, push_fn=None) -> dict:
    """切塊 → 逐塊經 infra.line_push.push_text 推播。回 {"chunks", "sent", "dry_run"}。"""
    if push_fn is None:
        from infra.line_push import push_text
        push_fn = push_text
    parts = _chunks(message)
    sent = 0
    for p in parts:
        res = push_fn(p, dry_run=dry_run)
        if res.get("sent"):
            sent += 1
    return {"chunks": len(parts), "sent": sent, "dry_run": bool(dry_run)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="追蹤清單 → MoneyDJ 淨值 → LINE 推播")
    ap.add_argument("--dry-run", action="store_true", help="只印不送")
    args = ap.parse_args(argv)

    url = os.environ.get("WATCH_CSV_URL", "").strip()
    if not url:
        print("❌ 未設 WATCH_CSV_URL（發布的 Google Sheet 追蹤清單 CSV 連結）")
        return 1                                    # §1 fail loud,不送空
    try:
        csv_text = fetch_csv(url)
    except Exception as e:  # noqa: BLE001 — 不印 {e},避免 log 洩漏含 url 的例外
        print(f"❌ CSV 抓取失敗:{type(e).__name__}")
        return 1

    items = extract_items_from_csv(csv_text)
    if not items:
        print("❌ 解析 0 個代號 → 不送（清單空或表頭欄未命中）")
        return 1
    print(f"📋 追蹤 {len(items)} 檔:{', '.join(items)}")

    _stats: dict = {}
    # hist_fn=_default_hist:live 抓不到時退用已累積 nav_history 最近一筆(§ 美國 IP 退路)
    msg = build_message(items, hist_fn=_default_hist, stats_out=_stats)
    _all_missing = len(items) > 0 and _stats.get("missing", 0) >= len(items)
    if args.dry_run:
        print("─" * 40 + "\n" + msg + "\n" + "─" * 40)
        return 0

    try:
        res = send(msg)
    except Exception as e:  # noqa: BLE001 — LinePushError 等 → 非零 exit,cron 紅燈
        print(f"❌ LINE 推播失敗:{type(e).__name__}")     # 只印型別(§ 不洩 URL/token)
        return 1
    if res["sent"] < res["chunks"]:      # 未全送(缺憑證 / 部分失敗)→ 非零
        print("⚠️ 未全部送出（缺 LINE_CHANNEL_TOKEN / LINE_USER_ID?）— 見上方 line_push 訊息")
        return 1
    if _all_missing:                     # 送出了但**全部**抓不到淨值 → 讓 cron 紅燈(§1 surface 系統性失敗)
        print("⚠️ 已送通知,但全部 %d 檔都抓不到 MoneyDJ 淨值（美國 IP 被擋/代理失效?）→ 標記失敗"
              % len(items))
        return 2
    print(f"✅ 已送出 {res['sent']}/{res['chunks']} 則到 LINE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
