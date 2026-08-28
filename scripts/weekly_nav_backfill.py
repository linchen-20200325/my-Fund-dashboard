"""scripts/weekly_nav_backfill.py — 每週 NAV 自動補齊(GitHub Actions 美國 IP / NAS)v19.479。

不靠 user 開 App:**每天**(v19.495,原每週)對「**持倉 ∪ 選股池**」跑一次 `backfill_to_gs`,把最新可得淨值
append 進雲端 `nav_history`(永久、重開不丟)。與 App「🔄 一鍵補抓全部缺淨值」**同一條 L2**
(`services.nav_history_store.backfill_to_gs`),`(code, date)` 冪等去重;含 LU 檔的
**ISIN → Yahoo secId 自動解析**(v19.478),故雲端跑一次就把 LU 檔的最新淨值也補上。

── 為何建議 GitHub Actions(美國 IP)────────────────────────────
Yahoo / 晨星從**美國 IP** 可達(台灣 IP 被擋)。LU 檔要靠 `ISIN→secId→Yahoo chart` 抓,
只有在美國 IP 環境(GitHub Actions / Streamlit Cloud)才成功;NAS(台灣 IP)可跑但 LU 檔
只拿得到 MoneyDJ 短窗。TW000 台灣註冊檔兩邊都靠 MoneyDJ(增量抓最新一筆即可)。

── 前置(env / GitHub repo secrets;infra.config env fallback)────
    google_service_account = Service Account 完整 JSON 字串(須為 nav / pool Sheet 編輯者)
    NAV_SHEET_ID           = (選填)nav_history 目標 Sheet;未設走 baked 預設
    POLICY_SHEET_ID        = 持倉 Sheet ID(讀持倉代碼;未設 → 退 macro_weights_sheet_id)
    macro_weights_sheet_id = (fallback)持倉 / 內部表 Sheet ID
cron:.github/workflows/weekly_nav_backfill.yml(**每天** 20:00 台灣;NAV 多 T+1 傍晚已確定;
    (code,date) 冪等 → 週末/假日無新值時 no-op)。檔名沿用 weekly_*(legacy,避免動 references)。
先手動驗證(不寫入,只列將補的代號):
    python scripts/weekly_nav_backfill.py --dry-run

── 行為(§1 Fail Loud)──────────────────────────────────────────
缺 SA / 讀不到任何代號 → exit 2;backfill 全數抓不到 → exit 1;部分抓不到 → 顯式列出 + exit 0
(增量場景單檔暫時抓不到非致命);雲端未啟用(is_enabled=False)→ exit 2(只存本機無意義)。
**任一檔被 Gate 0 擋下 → exit 1**(2026-08-28 稽核修正:被擋 ≠ 抓不到,且是**持續性**
故障 —— 舊版 n_ok>0 就回 0,一檔被擋會綠燈零通知、每天重演,fail-closed 退化成
silent data loss;理由與「天天紅」的權衡完整寫在 `main` 末段)。
另寫 `$GITHUB_STEP_SUMMARY`(有設才寫)讓 run 頁面一眼看懂,見 `_step_summary`。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _log(msg: str) -> None:
    print(f"[weekly_nav_backfill] {msg}", file=sys.stderr)


def _gather_codes(client, sheet_id) -> list:
    """持倉(政策 Sheet)∪ 選股池 → 去重(§2.1 upper)代號清單。純函式(client/sheet 注入,可測)。"""
    _codes: list = []
    # 持倉(重用已驗證的 headless 讀取)
    try:
        from scripts.weekly_switch_notify import _read_holdings
        _codes.extend(_read_holdings(client, sheet_id) if (client and sheet_id) else [])
    except Exception as _e:  # noqa: BLE001 — 讀持倉失敗不擋(還有選股池);§1 記 log 不靜默
        _log(f"讀持倉失敗(略過持倉):{type(_e).__name__}: {_e}")
    # 選股池(self-contained,SA 內部解析)
    try:
        from repositories.pool_repository import list_pool
        _codes.extend(str(e.code or "").strip().upper() for e in list_pool())
    except Exception as _e:  # noqa: BLE001
        _log(f"讀選股池失敗(略過選股池):{type(_e).__name__}: {_e}")
    _seen: set = set()
    out: list = []
    for _c in _codes:
        _c = str(_c or "").strip().upper()
        if _c and _c not in _seen:
            _seen.add(_c)
            out.append(_c)
    return out


def _load_client_and_holdings_sheet():
    """(gspread client, 持倉 sheet_id)。缺 SA → (None, None)。持倉 sheet 優先 POLICY_SHEET_ID。"""
    try:
        from infra.config import get_secret
        from repositories.policy_repository import get_gspread_client
    except Exception as _e:  # noqa: BLE001
        _log(f"import 失敗:{type(_e).__name__}: {_e}")
        return None, None
    _sa = get_secret("google_service_account")
    if not _sa:
        _log("缺 google_service_account secret")
        return None, None
    try:
        client = get_gspread_client(_sa)
    except Exception as _e:  # noqa: BLE001
        _log(f"建 gspread client 失敗:{type(_e).__name__}: {_e}")
        return None, None
    _sid = get_secret("POLICY_SHEET_ID") or get_secret("macro_weights_sheet_id")
    return client, (str(_sid) if _sid else None)


def _step_summary(res: dict, blocked: list) -> None:
    """把結果寫進 `$GITHUB_STEP_SUMMARY`（有設才寫;本機/NAS 無此 env → no-op）。

    exit code 負責**叫人來看**（見 `main` 末段的理由）,本函式負責**讓他一眼看懂** ——
    run 頁面直接看到哪一檔被擋、差在哪一天,不必翻 log。§5 可觀測。
    失敗只 log 不擋（寫 summary 壞掉不該讓一次成功的補淨值變成失敗）。
    """
    import os
    _path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not _path:
        return
    _nb = int(res.get("n_blocked") or 0)
    _nf = int(res.get("n_fail") or 0) - _nb
    _lines = [
        "## NAV 回填結果",
        "",
        f"- ✅ 抓到並寫入:**{res.get('n_ok', 0)}** 檔（雲端去重後新增 "
        f"**{res.get('gs_written', 0)}** 筆）",
        f"- ⬜ 抓不到:**{_nf}** 檔",
        f"- 🔴 被 Gate 0 擋下（**抓到了但沒寫入**）:**{_nb}** 檔",
        f"- Gate 0 模式:`{res.get('gate_mode', '?')}`",
    ]
    if res.get("gs_error"):
        _lines += ["", f"> 🔴 雲端寫入:{res['gs_error']}"]
    if blocked:
        _lines += [
            "",
            "### 🔴 被 Gate 0 擋下的檔（資料完整性偵測,不是抓不到）",
            "",
            "| 代號 | 原因 |", "|---|---|",
        ]
        _lines += [f"| `{r['code']}` | {str(r.get('error') or '').replace('|', '/')} |"
                   for r in blocked]
        _lines += [
            "",
            "這幾檔今天**沒有寫入任何淨值**,不處理就會每天重演。",
            "確認是誤擋 → 設 `NAV_GATE0_MODE=observe` 先止血,再修來源。",
        ]
    try:
        with open(_path, "a", encoding="utf-8") as _f:
            _f.write("\n".join(_lines) + "\n")
    except Exception as _e:  # noqa: BLE001 — 寫 summary 失敗不該擋補淨值;§1 記 log 不靜默
        _log(f"寫 GITHUB_STEP_SUMMARY 失敗(非致命):{type(_e).__name__}: {_e}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="每週 NAV 自動補齊(持倉 ∪ 選股池 → 雲端 nav_history)")
    ap.add_argument("--dry-run", action="store_true", help="只列將補的代號,不抓取/不寫入")
    args = ap.parse_args(argv)

    client, sheet_id = _load_client_and_holdings_sheet()
    if client is None:
        _log("缺 Service Account → 無法讀持倉/選股池(§1 exit 2)")
        return 2

    codes = _gather_codes(client, sheet_id)
    if not codes:
        _log("持倉與選股池都讀不到任何代號(§1 exit 2)")
        return 2
    _log(f"將補抓 {len(codes)} 檔:{', '.join(codes)}")

    if args.dry_run:
        _log("--dry-run:不抓取/不寫入,結束。")
        return 0

    from services.nav_history_gs import is_enabled
    if not is_enabled():
        _log("雲端 nav_history 未啟用(缺 SA / NAV_SHEET_ID)→ 只存本機無意義(§1 exit 2)")
        return 2

    from services.nav_history_store import backfill_to_gs
    res = backfill_to_gs(codes)
    _blocked = [r for r in res["results"] if r.get("blocked")]
    for r in res["results"]:
        if r["error"] is None and r["fetched"]:
            _log(f"  ✅ {r['code']}: {r['fetched']} 筆 ({r['date_min']}~{r['date_max']}) "
                 f"src={r.get('source')}")
        elif r.get("blocked"):
            # 🔴 不是「抓不到」—— 抓得好好的,是**資料完整性偵測**把它擋下來的。
            _log(f"  🔴 {r['code']}: 【Gate 0 擋下,未寫入】{r['error']}")
        else:
            _log(f"  ⬜ {r['code']}: {r['error']}")
    # 2026-08-28 稽核修正:被擋下的檔**抓得好好的**,舊版把它併進「N 檔抓不到」是說謊。
    _n_blocked = int(res.get("n_blocked") or 0)
    _n_nofetch = int(res["n_fail"]) - _n_blocked
    _log(f"完成:{res['n_ok']} 檔抓到 → 雲端去重後新增 {res['gs_written']} 筆;"
         f"{_n_nofetch} 檔抓不到;{_n_blocked} 檔被 Gate 0 擋下(抓到了但沒寫入)。"
         f" gate_mode={res.get('gate_mode', '?')}")
    _step_summary(res, _blocked)
    if res.get("gs_error"):
        _log(f"⚠️ 雲端寫入失敗:{res['gs_error']}(§1 exit 1)")
        return 1
    if res["n_ok"] == 0:
        _log("全數抓不到(§1 exit 1)")
        return 1
    if _blocked:
        # ── 為什麼**被擋也要 exit 1**（2026-08-28 稽核修正）────────────────
        # 舊版只在 `gs_error` 或 `n_ok == 0` 時回 1。一檔被擋、其他正常 → n_ok > 0
        # → exit 0 → **綠燈、零通知**,那檔基金從此每天被擋、每天沒人知道 ——
        # fail-closed 於是退化成 **silent data loss**（本 repo 剛修完它的鏡像:
        # 「假紅讓真錯誤沒人看見」;這裡是「假綠讓真失敗沒人看見」）。
        # 這是**持續性**故障:不處理就每天重演,而 exit code 是這條排程上唯一
        # 會主動通知人的管道（沒有人會去點開綠色 run 的 summary）。
        # ⚠️ 「天天紅會麻痺」的疑慮成立,但答案不是靜音,是:
        #   (a) 訊息直接指名哪一檔、差在哪一天（上面已列）;
        #   (b) `NAV_GATE0_MODE=observe` 是**刻意的**止血開關,改 env 即可,不必改 code;
        #   (c) C1（把「1 天對不上就整檔擋」改成比例/型態門檻）要靠**真實觸發頻率**
        #       才能校準 —— 看得見是校準的前提,所以現在不能靜音。
        _log(f"🔴 {len(_blocked)} 檔被 Gate 0 擋下(資料完整性偵測,**不是抓不到**):"
             f"{'、'.join(r['code'] for r in _blocked)} —— 這幾檔今天沒有寫入任何淨值,"
             f"不處理就會每天重演(§1 exit 1)。"
             f"確認是誤擋 → 設 NAV_GATE0_MODE=observe 先止血,再修來源。")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
