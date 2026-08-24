"""scripts/dividend_calendar_notify.py — 每月月初 除息行事曆 LINE 摘要(方式 C)v19.443。

不靠 user 開 App:每月月初對「**持倉 ∪ 追蹤清單**」抓配息史 → 推估本月除息日 → 推一則
LINE 文字摘要(「8/7 摩根 JFZN3 除息…」)。視覺完整月曆看 App「我的管理室 → 除息行事曆」(方式 A)。

reuse:`weekly_switch_notify` 的 `_load_client_and_sheet` / `_read_holdings` / `_read_watchlist`
(讀代碼);配息用輕量 `auto_fetch_moneydj`(只需 dividends + 名稱,不算全指標)。

環境變數(同週報):google_service_account / macro_weights_sheet_id(讀持倉,可缺→只跑追蹤清單)、
WATCH_CSV_URL(追蹤清單)、LINE_CHANNEL_TOKEN(或 LINE_CHANNEL_ACCESS_TOKEN)/ LINE_USER_ID。

§1:無任何代碼 → exit 2;全部抓失敗 → exit 1;LINE 未送出(缺憑證)→ exit 1;dry-run 只印。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _log(msg: str) -> None:
    print(f"[dividend_calendar_notify] {msg}", file=sys.stderr)


def _fetch_divs(codes: list) -> list:
    """codes → [{code, name, house, dividends}]。單檔失敗顯式 skip(§1 不偽造)。"""
    from services.dividend_calendar import detect_house
    from services.moneydj_fetcher import auto_fetch_moneydj
    out: list = []
    for c in codes:
        try:
            fd = auto_fetch_moneydj(c) or {}
            name = str(fd.get("fund_name") or c)
            out.append({"code": c, "name": name, "house": detect_house(name),
                        "dividends": fd.get("dividends")})
        except Exception as _e:  # noqa: BLE001 — 單檔抓失敗不拖累整批
            _log(f"略過 {c}:{type(_e).__name__}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="每月除息行事曆 LINE 摘要(headless)")
    ap.add_argument("--dry-run", action="store_true", help="只印不送")
    args = ap.parse_args(argv)

    from scripts.weekly_switch_notify import (
        _load_client_and_sheet,
        _read_holdings,
        _read_watchlist,
    )
    from services.dividend_calendar import (
        build_month_calendar,
        build_summary_flex,
        build_summary_text,
    )

    client, sheet_id = _load_client_and_sheet()
    held = _read_holdings(client, sheet_id) if client else []
    watch = _read_watchlist()
    codes = list(dict.fromkeys([*held, *watch]))       # 去重保序
    if not codes:
        _log("無持倉也無追蹤清單代碼 → 中止")
        return 2
    _log(f"觀察 {len(codes)} 檔(持倉 {len(held)} + 追蹤 {len(watch)})→ 抓配息…")

    funds = _fetch_divs(codes)
    # 稽核 H1:auto_fetch_moneydj 失敗時回 dict(不 raise)→ funds 非空但 dividends 全 None。
    # 成功抓取(含累積型)dividends 會是 list([] 或有紀錄);全部都不是 list = 系統性抓取失敗
    # → 不可送「本月無除息」誤導訊息(§1 不讓失敗看起來像成功)。
    _fetched = sum(1 for f in funds if isinstance(f.get("dividends"), list))
    if _fetched == 0:
        _log("全部基金配息抓取失敗(可能 proxy/網路/美國 IP 擋 MoneyDJ)→ 不送誤導訊息,中止")
        return 1

    now = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8)))
    # user 2026-08-24:推「下個月」預估(每月 1 號先知道下月除息 + 到帳),非本月。12 月 → 隔年 1 月。
    _ny, _nm = (now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1)
    # ref = 本月(現在)→ 陳舊度相對現在量,正常月配基金推下月不會被誤判低信心/疑停配(v19.518)。
    cal = build_month_calendar(funds, _ny, _nm, ref_year=now.year, ref_month=now.month)
    text = build_summary_text(cal)              # dry-run 預覽用(可讀純文字)
    flex = build_summary_flex(cal)              # 實送:LINE Flex 彩色卡片(user 2026-08-24)
    _log(f"下月 {_ny}-{_nm:02d} 推估除息 {cal['counts']['events']} 檔｜排除 {cal['counts']['excluded']} 檔")

    if args.dry_run:
        print("─" * 40 + "\n" + text + "\n" + "─" * 40)
        _log(f"(實送為 Flex 彩色卡片;altText:{flex['alt_text']})")
        return 0

    from infra.line_push import LinePushError, push_flex, push_text
    try:
        res = push_flex(flex["contents"], flex["alt_text"], dry_run=False)
    except LinePushError as _e:  # noqa: BLE001 — Flex 若被 LINE 退(如版型問題)→ 退回純文字,提醒仍送達
        _log(f"Flex 推播失敗:{_e} → 退回純文字")
        try:
            res = push_text(text, dry_run=False)
        except LinePushError as _e2:  # noqa: BLE001
            _log(f"純文字推播也失敗:{_e2}")
            return 1
    if not res["sent"]:
        _log(f"未送出({res['reason']})— 缺 LINE_CHANNEL_TOKEN/ACCESS_TOKEN / LINE_USER_ID?")
        return 1
    _log("✅ 已送出月曆到 LINE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
