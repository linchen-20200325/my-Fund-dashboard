"""scripts/dividend_calendar_notify.py — 每月月底 除息行事曆 LINE 摘要(方式 C)v19.537。

不靠 user 開 App:**每月 28 號 08:23(台灣)**對「**持倉 ∪ 追蹤清單**」抓配息史 →
推估**下個月**除息日 → 推一則 LINE 摘要(「10/7 摩根 JFZN3 除息…」)。
視覺完整月曆看 App「我的管理室 → 除息行事曆」(方式 A;App 那邊看的是**本月**)。

⚠️ **「28 號」與「推下個月」是一組配對**(v19.537):user 2026-09-01 裁示「月底發下個月,
或月初發本月,**絕對不會是月初發下個月**」。cron 在 `.github/workflows/dividend_calendar_notify.yml`,
兩邊必須同進退(成因:2026-08-24 只改了目標月沒改 cron);漂移由
`tests/test_dividend_calendar_cron_v19537.py` 鎖住。

補送指定月份:`--target-month 2026-09`(或 env `TARGET_MONTH`,旗標優先);
留空 = 下個月。**格式不合法一律報錯離開(exit 2),絕不靜默退回下個月**(§1)。

reuse:`weekly_switch_notify` 的 `_load_client_and_sheet` / `_read_holdings` / `_read_watchlist`
(讀代碼);配息用輕量 `auto_fetch_moneydj`(只需 dividends + 名稱,不算全指標)。

環境變數(同週報):google_service_account / macro_weights_sheet_id(讀持倉,可缺→只跑追蹤清單)、
WATCH_CSV_URL(追蹤清單)、LINE_CHANNEL_TOKEN(或 LINE_CHANNEL_ACCESS_TOKEN)/ LINE_USER_ID。

§1:target_month 格式錯 → exit 2;無任何代碼 → exit 2;全部抓失敗 → exit 1;
LINE 未送出(缺憑證)→ exit 1;dry-run 只印。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _log(msg: str) -> None:
    print(f"[dividend_calendar_notify] {msg}", file=sys.stderr)


_TZ_TW = _dt.timezone(_dt.timedelta(hours=8))
_TARGET_MONTH_ENV = "TARGET_MONTH"          # workflow 走 env 傳(不插進 shell 指令列,防 injection)
_TARGET_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")
_YEAR_MIN, _YEAR_MAX = 2000, 2100           # 打錯字防呆(如 0226 / 20261);非業務門檻


def _now_tw() -> "_dt.datetime":
    """現在(台北時間)。獨立成函式讓測試可凍結時間。"""
    return _dt.datetime.now(_TZ_TW)


def _resolve_target_month(now: "_dt.datetime", raw: "str | None") -> "tuple[int, int]":
    """(現在, 指定值) → 目標 (year, month)。

    `raw` 空/None → **下個月**(12 月 → 隔年 1 月),即排程路徑;
    `raw` = "YYYY-MM" → 該月(補送用)。

    §1:格式不合法 → **raise ValueError**(呼叫端 exit 2),**嚴禁**靜默退回「下個月」——
    那會讓 user 以為補送成功、實際收到另一個月,是最糟的失敗模式(錯的數字比沒有數字危險)。
    """
    s = (raw or "").strip()
    if not s:
        return (now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1)
    m = _TARGET_MONTH_RE.match(s)
    if not m:
        raise ValueError(f"target_month 格式不合法,需 YYYY-MM(例 2026-09):收到 {raw!r}")
    _y, _mo = int(m.group(1)), int(m.group(2))
    if not 1 <= _mo <= 12:
        raise ValueError(f"target_month 月份須 1~12:收到 {raw!r}")
    if not _YEAR_MIN <= _y <= _YEAR_MAX:
        raise ValueError(f"target_month 年份須 {_YEAR_MIN}~{_YEAR_MAX}:收到 {raw!r}")
    return _y, _mo


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


def _render_and_publish(cal: dict, year: int, month: int) -> "str | None":
    """月曆 → PNG → 發佈到公開分支 → 回傳可推播的圖片網址;任一步失敗 → None(呼叫端退 Flex)。

    §1:**失敗一律回 None 並記 log**,絕不回猜的網址 —— 推一個抓不到的網址,LINE 端會是破圖,
    比退回 Flex 卡片更糟。三個已知失敗點:Chromium/中文字型缺(產圖)、GITHUB_TOKEN 缺或
    workflow 未給 `contents: write`(發佈)、網路。
    """
    try:
        from infra.line_push import LINE_IMAGE_PREVIEW_MAX_BYTES as _MAX
        from ui.helpers.dividend_calendar_render import render_month_calendar_png
        _png = render_month_calendar_png(cal)
        # LINE preview 上限(SSOT 在 infra.line_push)。明細表列數隨基金數成長,retina(scale=2)
        # 在檔數多時可能超標 → 超過就用 scale=1 重畫;仍超標則退 Flex,不推會被 LINE 退的圖。
        if len(_png) > _MAX:
            _log(f"月曆圖 {len(_png)} bytes 超過 LINE preview 上限({_MAX})→ 改 scale=1 重畫")
            _png = render_month_calendar_png(cal, scale=1)
            if len(_png) > _MAX:
                _log(f"縮圖後仍 {len(_png)} bytes 超標 → 退 Flex(不推會被 LINE 退的圖)")
                return None
    except Exception as _e:  # noqa: BLE001 — 產圖失敗(Chromium/字型/逾時)→ 退 Flex
        _log(f"月曆產圖失敗:{type(_e).__name__}: {_e} → 退 Flex")
        return None
    try:
        from infra.asset_publish import publish_asset
        _url = publish_asset(_png, f"dividend-calendar/{year}-{month:02d}.png",
                             message=f"chore(assets): 除息月曆 {year}-{month:02d} [skip ci]")
    except Exception as _e:  # noqa: BLE001 — 發佈失敗(缺 token/權限/網路)→ 退 Flex
        _log(f"月曆圖發佈失敗:{type(_e).__name__}: {_e} → 退 Flex")
        return None
    _log(f"月曆圖已發佈({len(_png)} bytes):{_url}")
    return _url


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="每月除息行事曆 LINE 摘要(headless)")
    ap.add_argument("--dry-run", action="store_true", help="只印不送")
    ap.add_argument("--target-month", default=None,
                    help=f"指定目標月 YYYY-MM(留空 = 下個月);亦可用 env {_TARGET_MONTH_ENV},旗標優先")
    args = ap.parse_args(argv)

    # 目標月**先解析再抓資料**:格式錯就該立刻死,不要抓完幾十檔配息才發現參數是錯的。
    now = _now_tw()
    _raw_tm = args.target_month if args.target_month is not None else os.environ.get(
        _TARGET_MONTH_ENV, "")
    try:
        _ny, _nm = _resolve_target_month(now, _raw_tm)
    except ValueError as _e:
        _log(f"❌ {_e} → 中止(不退回下個月,避免補送到錯的月份)")
        return 2
    _log(f"目標月 {_ny}-{_nm:02d}" + (f"(手動指定 {_raw_tm.strip()})" if (_raw_tm or "").strip()
                                     else "(未指定 → 下個月)"))

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

    # ⚠️ `ref_*` 是**陳舊度量測基準,語意是「現在」,與目標月無關** —— 一律傳 now,
    # **即使手動指定了 target_month 也不跟著跑**(v19.537;鎖在 test_dividend_calendar_cron_v19537)。
    # ref = 現在 → 陳舊度相對現在量,正常月配基金推下月不會被誤判低信心/疑停配(v19.518)。
    # ref_day = **今天幾號**(v19.532 bug 4):L2 未給日時會退回月中(15 號),等於把陳舊度多/少
    # 算半個月。實測(月配、last_ex=2026-05-11、於 2026-09-01 量):
    #   ref=2026-09 day=1 → stale 3 個月、too_stale=False(正確);day=15 → 4、True(整檔誤判疑停配);
    #   ref 若跟著目標月跑到 2026-10 day=15 → 5、True(更嚴重)。
    cal = build_month_calendar(funds, _ny, _nm, ref_year=now.year, ref_month=now.month,
                               ref_day=now.day)
    text = build_summary_text(cal)              # dry-run 預覽用(可讀純文字)
    flex = build_summary_flex(cal)              # 實送:LINE Flex 彩色卡片(user 2026-08-24)
    _log(f"目標月 {_ny}-{_nm:02d} 推估除息 {cal['counts']['events']} 檔｜排除 {cal['counts']['excluded']} 檔")

    if args.dry_run:
        print("─" * 40 + "\n" + text + "\n" + "─" * 40)
        _log(f"(實送為月曆圖檔 + 上列文字;圖失敗才退 Flex,altText:{flex['alt_text']})")
        return 0

    from infra.line_push import LinePushError, push_flex, push_image, push_text

    # ── 首選:月曆 PNG 圖檔(user 2026-08-24 指定「截 App 那張」)+ 圖下方文字清單 ──────────
    # 三段都可能失敗(產圖需 Chromium/中文字型、發佈需 GITHUB_TOKEN、LINE 需公開網址),
    # 任一段失敗 → 退 Flex 彩色卡片 → 再退純文字。§1:提醒一定送達,不讓失敗看起來像「本月沒配息」。
    _img_url = _render_and_publish(cal, _ny, _nm)
    if _img_url:
        try:
            res = push_image(_img_url, caption=text, dry_run=False)
            if res["sent"]:
                _log("✅ 已送出月曆圖檔到 LINE")
                return 0
            _log(f"圖檔未送出({res['reason']})→ 退 Flex")
        except LinePushError as _e:  # noqa: BLE001 — LINE 退圖(網址不可達/格式)→ 往下退 Flex
            _log(f"圖檔推播失敗:{_e} → 退 Flex")

    # Flex 有**兩種**失敗形態:raise(被 LINE 退)與 res["sent"]=False(如空內容,不 raise)。
    # 兩種都要往下退純文字 —— 只接 exception 會讓 sent=False 直接落到最後 return 1,明明手上
    # 有現成的 text 卻不送,提醒消失(§1 稽核 MEDIUM-LOW-5)。
    res = None
    try:
        res = push_flex(flex["contents"], flex["alt_text"], dry_run=False)
        if not res["sent"]:
            _log(f"Flex 未送出({res['reason']})→ 退回純文字")
    except LinePushError as _e:  # noqa: BLE001 — Flex 被 LINE 退(如版型問題)→ 退回純文字
        _log(f"Flex 推播失敗:{_e} → 退回純文字")
    if res is None or not res["sent"]:
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
