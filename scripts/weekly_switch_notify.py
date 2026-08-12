"""scripts/weekly_switch_notify.py — 每週換股顧問健康週報 LINE(NAS / 本機 / GitHub Actions cron)v19.441。

不靠 user 開 App:每週對「**持倉 ∪ 追蹤清單(觀察標的)**」跑一次**同一套換股顧問**
(services.switch_advisor,與「組合健診 → 換股顧問」完全相同的邏輯),**有檔不健康才推 LINE**
(沒事不吵),並附選股池建議替換。健康問題含:🔴 嚴重吃本金 / 🔄 高基期該換 / 🔴 成長看衰賣現金 /
⚠️ 跑輸大盤。追蹤清單來源 = `WATCH_CSV_URL`(公開 CSV;未設則只跑持倉);與持倉**依代號去重**。

v19.441:①觀察集合擴為 持倉 ∪ 追蹤清單;②吃本金燈號餵進 switch_signal(修好「嚴重吃本金
不觸發」的漏洞 —— 高配息掩蓋的吃本金原本會漏報);③通知每檔標 [持倉]/[觀察] 來源。

與 App 端的差異:純 headless(不啟動 Streamlit)。所有取數/計算走 streamlit-free 的
L1/L2 primitive;**不 import** `ui/helpers/.../switch_advisor_section.py`(那層有 st.* 呼叫),
改在本檔重製它三個非 UI helper(_assemble_rows / _pool_rows / _underperf),phase="" score=None
(略過唯一的 st.session_state 讀取,那個值只餵 advisor 用不到的 MK 欄)。

── NAS / 本機 前置 ─────────────────────────────────────────────
1. 台灣 IP(直連即可;PROXY_URL 有設也相容)
2. `pip install -r requirements.txt`(streamlit 只是被 import,不啟動)
3. 環境變數(infra.config env fallback):
     google_service_account  = Service Account 的**完整 JSON 字串**
     macro_weights_sheet_id   = 政策/選股池/nav_history 共用的 Google Sheet ID
     LINE_CHANNEL_TOKEN       = LINE Messaging API channel access token
     LINE_USER_ID             = 你自己的 LINE userId
     WATCH_CSV_URL            = (選填)追蹤清單公開 CSV;未設 → 只跑持倉
4. cron(建議台灣時間**週日傍晚**,基金 NAV 多 T+1 傍晚更新):
     0 18 * * 0  cd /path/to/my-Fund-dashboard && python scripts/weekly_switch_notify.py
   (或用 GitHub Actions:.github/workflows/weekly_switch_notify.yml,週日 18:00 台灣)
5. 先手動驗證(不真的送):
     python scripts/weekly_switch_notify.py --dry-run

── 行為 ────────────────────────────────────────────────────────
§1 Fail Loud:secrets 缺 → exit 2;無持倉也無追蹤清單 → exit 2;全部抓失敗 → exit 1;
             單檔抓失敗 → 顯式 skip + 計數(不偽造);LINE 送失敗 → exit 1(cron 信可見)。
成長型賣出訊號需總經 composite;headless 預設 macro=None(誠實降級,成長型不觸發賣出,
§1 缺料不臆測)——若要成長型賣出通知,加 --with-macro(會多打 ~28 FRED series,需 FRED_API_KEY)。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# repo root 進 sys.path(mirror scripts/accumulate_nav_tw.py)
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_PRINCIPAL = 1_000_000.0     # process_one_fund 的名目本金(僅走管線,不影響型態/基期/表現差)


def _log(msg: str) -> None:
    print(f"[weekly_switch_notify] {msg}", file=sys.stderr)


# ───────────────────────── secrets / client ─────────────────────────

def _load_client_and_sheet():
    """(gspread client, sheet_id)。缺 secret → None(呼叫端 exit 2,§1 不靜默)。"""
    try:
        from infra.config import get_secret
        from repositories.policy_repository import get_gspread_client
    except Exception as _e:  # noqa: BLE001
        _log(f"import 失敗:{type(_e).__name__}: {_e}")
        return None, None
    _sa = get_secret("google_service_account")
    _sid = get_secret("macro_weights_sheet_id")
    if not _sa or not _sid:
        _log("缺 google_service_account / macro_weights_sheet_id secret")
        return None, None
    try:
        client = get_gspread_client(_sa)          # str/dict 皆可,內部正規化
    except Exception as _e:  # noqa: BLE001
        _log(f"建 gspread client 失敗:{type(_e).__name__}: {_e}")
        return None, None
    return client, str(_sid)


# ───────────────────────── 讀持倉代碼(headless)─────────────────────────

def _read_holdings(client, sheet_id) -> list:
    """政策 Sheet → 持有基金代碼清單(大寫,去重)。v2 優先、v1 fallback。空 → []。"""
    from repositories.policy.v2 import (
        detect_sheet_schema_version,
        load_all_policies_v2,
        load_all_policy_worksheets,
    )
    try:
        _ver = detect_sheet_schema_version(client, sheet_id)
        _codes: list = []
        if _ver == "v2":
            df = load_all_policies_v2(client, sheet_id)
            for _, _r in df.iterrows():
                if str(_r.get("item_type", "fund")).strip().lower() not in ("", "fund"):
                    continue                      # 跳過現金等非基金列
                _c = str(_r.get("fund_code", "") or "").strip().upper()
                if _c:
                    _codes.append(_c)
        elif _ver == "v1":
            from repositories.policy.v1 import _extract_code_from_url
            df = load_all_policy_worksheets(client, sheet_id)
            for _, _r in df.iterrows():
                _c = (_extract_code_from_url(str(_r.get("fund_url", "") or "")) or "").strip().upper()
                if _c:
                    _codes.append(_c)
        else:
            _log(f"Sheet schema = {_ver}(無保單分頁)")
    except Exception as _e:  # noqa: BLE001 — 讀帳本失敗 → 回 [](呼叫端 exit 2,§1 不拋原始 traceback)
        _log(f"讀帳本失敗:{type(_e).__name__}: {_e}")
        return []
    # 去重保序
    _seen: set = set()
    return [c for c in _codes if not (c in _seen or _seen.add(c))]


# ───────────────────────── 讀追蹤清單(觀察標的,headless)─────────────────────────

def _read_watchlist() -> list:
    """WATCH_CSV_URL 公開 CSV → 觀察代號(大寫去重)。未設/抓失敗 → [](§1:不擋主流程)。

    重用 watchlist_push 的 CSV 解析(表頭鎖「代號」欄 / 排除純數字 / 去重),不重造。
    """
    import os
    _url = os.environ.get("WATCH_CSV_URL", "").strip()
    if not _url:
        return []
    try:
        from scripts.watchlist_push import extract_items_from_csv, fetch_csv
        _codes = extract_items_from_csv(fetch_csv(_url))
        _log(f"追蹤清單讀到 {len(_codes)} 檔觀察標的")
        return _codes
    except Exception as _e:  # noqa: BLE001 — 追蹤清單抓失敗 → 只跑持倉,不整批中斷
        _log(f"讀追蹤清單失敗(略過,只跑持倉):{type(_e).__name__}")
        return []


# ───────────────────────── 抓 rich fund dict(headless)─────────────────────────

def _fetch_rich(codes: list) -> dict:
    """codes → {code: rich fund dict}。單檔抓失敗顯式 skip + log(§1 不偽造)。"""
    from services.fund_row import process_one_fund
    from ui.helpers.fund_grp_health._utils import _build_fund_dict
    out: dict = {}
    for _c in codes:
        try:
            _r = process_one_fund(_c, _PRINCIPAL)
            if _r.get("ok") and _r.get("_fund_raw"):
                out[_c] = _build_fund_dict(_r["_fund_raw"], _c, _PRINCIPAL)
            else:
                _log(f"略過 {_c}:{_r.get('error') or '抓取未成功'}")
        except Exception as _e:  # noqa: BLE001
            _log(f"略過 {_c}(例外):{type(_e).__name__}: {_e}")
    return out


# ───────────────────────── 組 advisor rows(重製 _assemble_rows,headless)──────────

def _assemble_rows(funds: list, pool_by_code: dict) -> list:
    """rich fund dict → advise_switches 需要的列(重製 rotation._assemble_rows,phase="" score=None,
    + 加 nav_series / type_override / 類別 fallback)。streamlit-free。"""
    from services.health.dividend import check_eating_principal_1y_mk
    from services.health.report import build_health_analysis_row
    from ui.helpers.fund_grp_health.unified import build_merged_extra_columns

    _extra = build_merged_extra_columns(funds, "", None)[1]     # σ rank / 距 HWM % / 操盤評分
    rows = []
    for _f in funds:
        _code = _f.get("code", "?")
        _fd = _f.get("moneydj_raw") or _f
        try:
            _h = build_health_analysis_row(_fd, _code)
        except Exception:  # noqa: BLE001
            _h = {}
        try:
            _eat = (check_eating_principal_1y_mk(_fd) or {}).get("status", "")
        except Exception:  # noqa: BLE001
            _eat = ""
        _e = _extra.get(_code, {})
        _pe = pool_by_code.get(_code)
        rows.append({
            "code": _code, "name": _f.get("name") or _code,
            "基金類別": _h.get("基金類別") or (getattr(_pe, "category", None) if _pe else None),
            "4D Grade": _h.get("4D Grade"),
            "σ rank": _e.get("σ rank"), "距 HWM %": _e.get("距 HWM %"),
            "操盤評分": _e.get("操盤評分"), "吃本金燈號": _eat,
            "nav_series": _f.get("series"),
            "type_override": (getattr(_pe, "type_override", "") if _pe else "") or "",
        })
    return rows


# ───────────────────────── 表現差(重製 _underperf_by_code,headless)──────────

def _underperf_by_code(funds: list) -> dict:
    """{str(code): assess_underperformance(...)}。跑輸大盤走 capture_by_code、絕對虧損走
    switch_score+switch_signal(重製 switch_advisor_section 的兩個 helper,streamlit-free)。"""
    from services.capture_ratio import benchmark_for_currency
    from services.currency import normalize_ccy
    from services.fund_total_return import compute_1y_total_return
    from services.health.dividend import check_eating_principal_1y_mk
    from services.switch_advisor import assess_underperformance, eat_is_red
    from services.switch_strategy import RED, switch_score, switch_signal
    from ui.helpers.fund_grp_health.capture import capture_by_code

    _cap = capture_by_code(funds)
    _excess = {c: (_cap.get(c) or {}).get("vs 大盤%") for c in (_cap or {})}
    out: dict = {}
    for _f in funds:
        _code = _f.get("code")
        # v19.441:吃本金燈號餵進 switch_signal → 嚴重吃本金 = 一級紅燈(user 明確要留意)。
        # 原本傳 eat="" 讓「嚴重吃本金」分支永遠不觸發,只靠「含息<0且Sharpe<0」→ 高配息掩蓋的
        # 吃本金會漏報。改抓 MK 1Y 吃本金 status 傳入(缺料 → "" 誠實降級,不臆測 §1)。
        try:
            _eat = (check_eating_principal_1y_mk(_f) or {}).get("status", "")
        except Exception as _e:  # noqa: BLE001
            _log(f"{_code} 吃本金判定失敗:{type(_e).__name__}")
            _eat = ""
        # 絕對虧損紅燈(嚴重吃本金 或 含息1Y<0且Sharpe<0;含息 × Sharpe × 最大跌幅 × vs大盤)
        try:
            _tr, _ = compute_1y_total_return(_f)
            _m = _f.get("metrics") or {}
            _rm = _f.get("risk_metrics") or {}
            _dd = _rm.get("max_drawdown")
            if _dd is None:
                _dd = _m.get("max_drawdown")
            _cov: dict = {}
            _sc = switch_score(_tr, _m.get("sharpe"), _dd, _excess.get(_code), coverage_out=_cov)
            # switch_signal 只認「嚴重」紅;正報酬但配息侵蝕本金(plain 🔴 吃本金)靠 eat_is_red 補
            _red = (switch_signal(_tr, _m.get("sharpe"), _eat, _sc, coverage=_cov) == RED
                    or eat_is_red(_eat))
        except Exception as _e:  # noqa: BLE001
            _log(f"{_code} 紅燈判定失敗:{type(_e).__name__}: {_e}")
            _red = None
        _c = _cap.get(_code) or {}
        out[str(_code)] = assess_underperformance(
            excess_pct=_c.get("vs 大盤%"),
            full_period=str(_c.get("vs 大盤期間", "")).startswith("⚠️ 全期"),
            benchmark_label=benchmark_for_currency(normalize_ccy(_f.get("currency"), default="")),
            eat_status=_eat,          # 讓 reason 標「🔴 嚴重吃本金」而非籠統「絕對虧損」
            redlight=_red,
        )
    return out


# ───────────────────────── 選配:總經 composite(headless)─────────────

def _macro_composite() -> "float | None":
    """--with-macro 時計算總經 composite;失敗/無 key → None(誠實降級)。"""
    try:
        from infra.config import get_secret
        from services.macro.composite_score import calculate_composite_score
        from services.macro.us_indicators import fetch_all_indicators
        _key = get_secret("FRED_API_KEY")
        if not _key:
            _log("--with-macro 但缺 FRED_API_KEY → macro=None")
            return None
        _ind = fetch_all_indicators(_key)
        _res = calculate_composite_score(_ind)
        _v = _res.get("score") if isinstance(_res, dict) else _res
        return float(_v) if isinstance(_v, (int, float)) else None
    except Exception as _e:  # noqa: BLE001
        _log(f"macro composite 計算失敗 → None:{type(_e).__name__}: {_e}")
        return None


def _fx_label() -> "str | None":
    try:
        from ui.helpers.fund_grp_health.fx_regime import fx_regime_by_ccy
        return (fx_regime_by_ccy().get("USD") or {}).get("regime")
    except Exception as _e:  # noqa: BLE001
        _log(f"fx_regime 取得失敗 → None:{type(_e).__name__}: {_e}")
        return None


# ───────────────────────── main ─────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="每週換股顧問 LINE 週報(headless)")
    ap.add_argument("--dry-run", action="store_true", help="不真的送 LINE,只印訊息預覽")
    ap.add_argument("--notify-empty", action="store_true", help="即使無建議也送一則週報(心跳)")
    ap.add_argument("--with-macro", action="store_true", help="計算總經 composite(啟用成長型賣出訊號;較慢)")
    args = ap.parse_args(argv)

    client, sheet_id = _load_client_and_sheet()
    if client is None:
        _log("secrets/client 不齊 → 中止")
        return 2

    try:
        from repositories.pool_repository import list_pool
        _pool = list_pool()
    except Exception as _e:  # noqa: BLE001
        _log(f"讀選股池失敗(視為空池):{type(_e).__name__}: {_e}")
        _pool = []
    # 稽核修:pool code 存的是「使用者輸入原樣」,持倉代碼一律 .upper() → 鍵統一大寫,
    # 否則同一檔在帳本(大寫)與選股池(小寫)會被當兩檔(重複抓 + 對不到 type_override)。
    _pool_by_code = {str(e.code).upper(): e for e in _pool}

    _held_codes = _read_holdings(client, sheet_id)
    _watch_codes = _read_watchlist()
    # 觀察集合 = 持倉 ∪ 追蹤清單(去重保序;source 標記,同檔持倉優先)
    _source_by_code: dict = {}
    for _c in _held_codes:
        _source_by_code[_c] = "持倉"
    for _c in _watch_codes:
        _source_by_code.setdefault(_c, "觀察")
    _observed_codes = list(_source_by_code.keys())
    if not _observed_codes:
        _log("無持倉也無追蹤清單代碼(帳本空 + WATCH_CSV_URL 未設/空)→ 中止")
        return 2

    _all_codes = list(dict.fromkeys(_observed_codes + list(_pool_by_code.keys())))
    _log(f"觀察 {len(_observed_codes)} 檔(持倉 {len(_held_codes)} + 追蹤 {len(_watch_codes)})"
         f" + 選股池 {len(_pool_by_code)} 檔 → 抓 {len(_all_codes)} 檔資料…")
    _rich = _fetch_rich(_all_codes)
    if not _rich:
        _log("全部基金資料抓取失敗 → 中止")
        return 1

    _observed_funds = [_rich[c] for c in _observed_codes if c in _rich]
    if not _observed_funds:
        _log("觀察標的全部抓取失敗 → 中止")
        return 1
    _pool_funds = [_rich[c] for c in _pool_by_code if c in _rich]

    _observed_rows = _assemble_rows(_observed_funds, _pool_by_code)
    _pool_rows = _assemble_rows(_pool_funds, _pool_by_code)
    _under = _underperf_by_code(_observed_funds)
    _macro = _macro_composite() if args.with_macro else None
    _fx = _fx_label()

    from services.switch_advisor import advise_switches
    from services.switch_notify import build_notification
    _res = advise_switches(_observed_rows, _pool_rows, fx_label=_fx,
                           macro_composite=_macro, underperformance_by_code=_under)
    import datetime as _dt
    _as_of = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8))).strftime("%Y-%m-%d")
    _skipped = len(_observed_codes) - len(_observed_funds)   # 抓不到的觀察標的數(誠實帶進訊息)
    _note = build_notification(_res, as_of=_as_of, skipped=_skipped,
                               source_by_code=_source_by_code)
    _log(f"該通知={_note['should_notify']}｜需留意 {_note['n_actionable']} 檔"
         f"（觀察載入 {len(_observed_funds)}/{len(_observed_codes)}）")

    if not _note["should_notify"] and not args.notify_empty:
        _log("本週無建議 → 不推播(--notify-empty 可強制送心跳)")
        return 0

    from infra.line_push import LinePushError, push_text
    try:
        _r = push_text(_note["message"], dry_run=args.dry_run)
    except LinePushError as _e:  # noqa: BLE001
        _log(f"LINE 推播失敗:{_e}")
        return 1
    _log(f"LINE:{_r['reason']}(sent={_r['sent']})")
    # 稽核修:正式跑(非 dry-run)有建議卻沒送出(多半缺 LINE_CHANNEL_TOKEN/LINE_USER_ID)
    # → 視為失敗 exit 1(§1;否則 cron 監控會誤判成功、通知悄悄漏掉)。
    if not args.dry_run and not _r["sent"]:
        _log(f"有建議但 LINE 未送出({_r['reason']})→ 視為失敗")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
