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
    for r in res["results"]:
        if r["error"] is None and r["fetched"]:
            _log(f"  ✅ {r['code']}: {r['fetched']} 筆 ({r['date_min']}~{r['date_max']}) "
                 f"src={r.get('source')}")
        else:
            _log(f"  ⬜ {r['code']}: {r['error']}")
    _log(f"完成:{res['n_ok']} 檔抓到 → 雲端去重後新增 {res['gs_written']} 筆;"
         f"{res['n_fail']} 檔抓不到。")
    if res.get("gs_error"):
        _log(f"⚠️ 雲端寫入失敗:{res['gs_error']}(§1 exit 1)")
        return 1
    if res["n_ok"] == 0:
        _log("全數抓不到(§1 exit 1)")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
