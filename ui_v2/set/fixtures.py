# -*- coding: utf-8 -*-
"""設定與診斷的假資料（示意值）＋ 一份 `44` 規格快照。純 dict／tuple，零 streamlit import、零網路、零舊 repo import。

欄位名與型別逐字照 `44` 第四節（`nav` 4.2、`dividend` 4.3、`market_indicator`／`user_setting`／`fetch_log` 4.5）。
**一個欄位也沒有多、也沒有改名。**`setting_value` 依 `44` 4.5 是「設定值的字串形式」，本檔一律放字串或 `None`。

⚠️ **本檔一個真實觀測值也沒有。** 時間、列數、訊息原文都只表示位置與格式；頁首與每一塊的說明行寫明「本塊數字皆為示意值」
（體例同 `ui_v2/alo`，登記 `SET-GAP-示意標記`）。

⚠️ **規格快照（`SPEC_TABLES`／`SPEC_BLOCK_SOURCES`／`SPEC_SETTING_KEYS`）不是資料庫內容**，是 `SET-7` 與 `SET-4`
要讀的那一份「第四節的表與欄位、第三節各塊的來源欄」。本頁執行時不去讀 `44`（登記 `SET-GAP-SET7寫死`）；
這份快照與 `44` 現行文字由 `tests/ui_v2/test_set_logic.py` 逐項重抽比對，漂了就紅。
"""

from __future__ import annotations

NOW_UTC = "2026-09-22T04:00:00Z"  # 「今天」固定在這一刻（登記 SET-GAP-距今時區）；本頁不讀系統時鐘。
UPDATED_AT = "2026-09-15T02:30:00Z"

READ_FAIL_MESSAGE = "HTTP 503 upstream unavailable（示意訊息原文，未改寫）"
TIER_FAIL_MESSAGE = "HTTP 503 from upstream endpoint (request id 4f2a-91c7)（示意訊息原文，未改寫）"
SAVE_FAIL_MESSAGE = "write conflict: setting_value rejected（示意訊息原文，未改寫）"

# `44` 4.2／4.5：`source_tier` 四個之一（2026-09-23 補上的值域）。
TIERS = ("淨值", "配息", "市場指標", "其他")

# ───────────────────────── 規格快照：`44` 第四節八張表的欄位 ─────────────────────────
SPEC_TABLES = (
    ("holding", ("holding_id", "policy_id", "fund_code", "fund_name", "ccy", "units_shares",
                 "cost_orig_ccy", "cost_twd", "opened_on", "bucket", "last_synced_at")),
    ("nav", ("fund_code", "nav_date", "nav_orig_ccy", "ccy", "source_tier", "is_estimated", "fetched_at")),
    ("dividend", ("fund_code", "ex_date", "pay_date", "div_per_unit_orig_ccy", "ccy", "div_kind", "fetched_at")),
    ("policy", ("policy_id", "policy_name", "issuer", "ccy", "premium_paid_twd", "fee_rate_pct", "opened_on",
                "status")),
    ("market_indicator", ("indicator_key", "obs_date", "release_date", "value_num", "value_unit", "source_tier",
                          "is_revised", "fetched_at")),
    ("user_setting", ("setting_key", "setting_value", "value_kind", "updated_at")),
    ("fetch_log", ("log_id", "source_tier", "started_at", "finished_at", "outcome", "row_count", "message")),
    ("fund_profile", ("fund_code", "fund_name", "ccy", "inception_on", "dividend_policy", "mgmt_fee_rate_pct",
                      "fetched_at")),
)

# ───────────────────────── 規格快照：`44` 第三節四十一塊「來源」欄 ─────────────────────────
# 抽法（登記 SET-GAP-SET7母體）：去掉刪除線後，來源欄裡以反引號寫出的 `表.欄位`；
# 寫成「`表` 全表」或「`表` 全欄」的記為 `表.*`（整張表的每一欄）。裸欄名（沒有帶表名）不計。
SPEC_BLOCK_SOURCES = (
    ("MKT-0", ()),
    ("MKT-1", ("market_indicator.value_num",)),
    ("MKT-2", ("market_indicator.value_num",)),
    ("MKT-3", ("market_indicator.value_num",)),
    ("MKT-4", ("user_setting.setting_value", "user_setting.updated_at")),
    ("MKT-5", ("user_setting.setting_value",)),
    ("MKT-6", ("market_indicator.*",)),
    ("MKT-7", ("market_indicator.fetched_at", "market_indicator.obs_date", "market_indicator.source_tier")),
    ("HLD-0", ()),
    (
        "HLD-1",
        (
            "holding.bucket",
            "holding.cost_twd",
            "holding.fund_code",
            "holding.units_shares",
            "nav.nav_date",
            "nav.nav_orig_ccy",
            "user_setting.setting_value",
        ),
    ),
    (
        "HLD-2",
        (
            "fund_profile.inception_on",
            "nav.ccy",
            "nav.nav_date",
            "nav.nav_orig_ccy",
            "user_setting.setting_value",
        ),
    ),
    (
        "HLD-3",
        (
            "dividend.ccy",
            "dividend.div_kind",
            "dividend.div_per_unit_orig_ccy",
            "dividend.ex_date",
            "holding.units_shares",
            "nav.nav_date",
            "nav.nav_orig_ccy",
            "user_setting.setting_value",
        ),
    ),
    ("HLD-4", ("user_setting.setting_value", "user_setting.updated_at")),
    ("HLD-5", ("policy.issuer", "policy.policy_name", "holding.*")),
    ("HLD-6", ("nav.*", "dividend.*")),
    ("HLD-7", ()),
    (
        "HLD-8",
        (
            "dividend.ccy",
            "dividend.div_kind",
            "dividend.div_per_unit_orig_ccy",
            "dividend.ex_date",
            "fund_profile.inception_on",
            "holding.fund_code",
            "holding.units_shares",
            "nav.ccy",
            "nav.nav_date",
            "nav.nav_orig_ccy",
            "user_setting.setting_value",
        ),
    ),
    ("EXP-0", ()),
    ("EXP-1", ("user_setting.setting_value", "user_setting.updated_at")),
    ("EXP-2", ("nav.nav_date", "nav.nav_orig_ccy", "fund_profile.*")),
    ("EXP-3", ()),
    ("EXP-4", ("user_setting.setting_value", "user_setting.updated_at")),
    ("EXP-5", ("user_setting.setting_value", "user_setting.updated_at")),
    ("EXP-6", ("fund_profile.*",)),
    ("EXP-7", ()),
    ("ALO-0", ()),
    ("ALO-1", ("user_setting.setting_value", "user_setting.updated_at")),
    (
        "ALO-2",
        (
            "holding.bucket",
            "holding.cost_twd",
            "holding.units_shares",
            "market_indicator.value_num",
            "nav.nav_date",
            "nav.nav_orig_ccy",
        ),
    ),
    ("ALO-3", ("user_setting.setting_value", "user_setting.updated_at")),
    ("ALO-4", ("holding.bucket", "user_setting.setting_value", "user_setting.updated_at")),
    ("ALO-5", ()),
    (
        "ALO-6",
        (
            "holding.bucket",
            "holding.cost_twd",
            "holding.fund_code",
            "holding.units_shares",
            "nav.nav_orig_ccy",
            "policy.policy_name",
        ),
    ),
    ("ALO-7", ("user_setting.setting_key", "user_setting.setting_value", "user_setting.updated_at")),
    ("SET-0", ()),
    (
        "SET-1",
        (
            "dividend.fetched_at",
            "market_indicator.fetched_at",
            "nav.fetched_at",
            "user_setting.setting_value",
        ),
    ),
    ("SET-2", ("fetch_log.message", "fetch_log.outcome", "fetch_log.source_tier", "fetch_log.started_at")),
    ("SET-3", ("user_setting.*",)),
    (
        "SET-4",
        (
            "user_setting.setting_key",
            "user_setting.setting_value",
            "user_setting.updated_at",
            "user_setting.value_kind",
        ),
    ),
    ("SET-5", ("fetch_log.*",)),
    ("SET-6", ("fetch_log.*",)),
    ("SET-7", ()),
)


# ───────────────────────── 規格快照：`user_setting` 的鍵 ─────────────────────────
# `44` 沒有把鍵列成一張表（登記 SET-GAP-鍵清單）；下面十七個是 `44` 全文以反引號寫出的 `set_`／`mkt_`／`hld_`／
# `exp_`／`alo_` 開頭的鍵名。`value_kind` 是本頁配的（登記 SET-GAP-型別本頁配），`44` 沒有寫哪一鍵是哪一種。
# `alo_basis` 放 `None`：它存的是二選一，`44` 4.5 那六種對不上（同 ui_v2/alo 的登記）。
SPEC_SETTING_KEYS = (
    ("alo_basis", None),
    ("alo_bucket_names", "list"),
    ("alo_scenario_input", "list"),
    ("alo_target_weights", "list"),
    ("alo_tolerance_pp", "float"),
    ("exp_filter_rules", "rules"),
    ("exp_sort_column", "list"),
    ("exp_visible_columns", "list"),
    ("exp_watchlist", "list"),
    ("hld_deviation_rules", "rules"),
    ("hld_window_end", "date"),
    ("hld_window_start", "date"),
    ("mkt_baseline_date", "date"),
    ("mkt_indicator_keys", "list"),
    ("mkt_window_days", "int"),
    ("set_log_keep_rows", "int"),
    ("set_max_age_days", "int"),
)

# 各鍵被哪幾塊的來源欄以反引號寫出（`SET-4`「改了會影響哪幾塊」；抽法同 `SPEC_BLOCK_SOURCES`）。
SPEC_KEY_USED_BY = (
    ("alo_basis", ("ALO-4",)),
    ("alo_bucket_names", ("ALO-4",)),
    ("alo_scenario_input", ("ALO-3",)),
    ("alo_target_weights", ("ALO-1", "ALO-7")),
    ("alo_tolerance_pp", ("ALO-1", "ALO-7")),
    ("exp_filter_rules", ("EXP-1",)),
    ("exp_sort_column", ("EXP-4",)),
    ("exp_visible_columns", ("EXP-4",)),
    ("exp_watchlist", ("EXP-5",)),
    ("hld_deviation_rules", ("HLD-1", "HLD-4")),
    ("hld_window_end", ("HLD-2", "HLD-3", "HLD-4", "HLD-8")),
    ("hld_window_start", ("HLD-2", "HLD-3", "HLD-4", "HLD-8")),
    ("mkt_baseline_date", ("MKT-4",)),
    ("mkt_indicator_keys", ("MKT-5",)),
    ("mkt_window_days", ("MKT-4",)),
    ("set_log_keep_rows", ()),
    ("set_max_age_days", ("SET-1",)),
)

# 各鍵已存的示意值（字串）。
_VALUES = {
    "alo_basis": "cost",
    "alo_bucket_names": '["核心（示意）", "衛星（示意）", "現金（示意）"]',
    "alo_scenario_input": '[["衛星（示意）", 100000]]',
    "alo_target_weights": '[["核心（示意）", 0.6], ["衛星（示意）", 0.3], ["現金（示意）", 0.1]]',
    "alo_tolerance_pp": "4",
    "exp_filter_rules": '["示意條件一"]',
    "exp_sort_column": '["fund_code"]',
    "exp_visible_columns": '["fund_code", "fund_name"]',
    "exp_watchlist": '["AAAA", "BBBB"]',
    "hld_deviation_rules": '["示意門檻一"]',
    "hld_window_end": "2026-09-21",
    "hld_window_start": "2026-06-21",
    "mkt_baseline_date": "2026-08-31",
    "mkt_indicator_keys": '["vol_index", "credit_spread_pct"]',
    "mkt_window_days": "90",
    "set_log_keep_rows": "50",
    "set_max_age_days": "14",
}
BAD_KIND_KEY = "mkt_window_days"
BAD_KIND_LITERAL = "ninety"

# ───────────────────────── 資料表 ─────────────────────────

# 三類資料最近一次取得時間：淨值 1 日前、配息 4 日前、市場指標 2 日前（以 UTC+8 的日曆日計）。
NAV_FETCHED = "2026-09-21T03:10:00Z"
DIV_FETCHED = "2026-09-18T03:12:00Z"
MI_FETCHED = "2026-09-20T03:11:00Z"


TODAY_FETCHED = "2026-09-22T02:00:00Z"  # 與 NOW_UTC 同一個 UTC+8 日曆日：距今 0 日


def navs(latest=NAV_FETCHED) -> list:
    return [
        {"fund_code": "AAAA", "nav_date": "2026-09-19", "nav_orig_ccy": 15.10, "ccy": "USD",
         "source_tier": "淨值", "is_estimated": False, "fetched_at": "2026-09-20T03:10:00Z"},
        {"fund_code": "AAAA", "nav_date": "2026-09-20", "nav_orig_ccy": 15.20, "ccy": "USD",
         "source_tier": "淨值", "is_estimated": False, "fetched_at": latest},
        {"fund_code": "BBBB", "nav_date": "2026-09-20", "nav_orig_ccy": 21.50, "ccy": "TWD",
         "source_tier": "淨值", "is_estimated": False, "fetched_at": latest},
    ]


def dividends() -> list:
    return [
        {"fund_code": "CCCC", "ex_date": "2026-09-15", "pay_date": None, "div_per_unit_orig_ccy": 0.05,
         "ccy": "USD", "div_kind": "income", "fetched_at": DIV_FETCHED},
    ]


def market_indicators() -> list:
    return [
        {"indicator_key": "vol_index", "obs_date": "2026-09-19", "release_date": "2026-09-19", "value_num": 18.2,
         "value_unit": "index", "source_tier": "市場指標", "is_revised": False, "fetched_at": MI_FETCHED},
    ]


def _log(log_id, tier, started, finished, outcome, row_count, message=None):
    return {
        "log_id": log_id,
        "source_tier": tier,
        "started_at": started,
        "finished_at": finished,
        "outcome": outcome,
        "row_count": row_count,
        "message": message,
    }


def fetch_logs() -> list:
    """五列：四個層級各有一次最近的 `ok`，淨值另有一列較舊的。故意不依時間排（排序是 `SET-6` 的事）。"""
    return [
        _log("lg-0002", "配息", "2026-09-18T03:12:00Z", "2026-09-18T03:12:03Z", "ok", 12),
        _log("lg-0005", "淨值", "2026-09-21T03:10:02Z", "2026-09-21T03:10:06Z", "ok", 128),
        _log("lg-0001", "淨值", "2026-09-17T03:10:00Z", "2026-09-17T03:10:05Z", "ok", 127),
        _log("lg-0004", "市場指標", "2026-09-20T03:11:15Z", "2026-09-20T03:11:19Z", "ok", 64),
        _log("lg-0003", "其他", "2026-09-19T03:09:41Z", "2026-09-19T03:09:44Z", "ok", 31),
    ]


FAILED_TIER = "市場指標"
EMPTY_TIER = "配息"
NO_RECORD_TIER = "其他"
BROKEN_LOG_ID = "lg-0005"
UNDEF_FIELD = "nav.nav_value"  # 示意：改名前的舊欄位名（`SET-7` 判準那一種輸入）
UNDEF_BLOCK = "HLD-2"


def user_settings(values) -> list:
    """`44` 4.5：未設定的鍵照樣建列，`setting_value` 與 `updated_at` 皆為 `None`（不以 0 或空字串補）。"""
    rows = []
    for key, kind in SPEC_SETTING_KEYS:
        value = values.get(key)
        rows.append(
            {
                "setting_key": key,
                "setting_value": value,
                "value_kind": kind,
                "updated_at": UPDATED_AT if value is not None else None,
            }
        )
    return rows


def _dataset(*, values=None, nav=True, dividend=True, mi=True, logs=None, errors=None, extra_sources=(),
             nav_latest=NAV_FETCHED) -> dict:
    values = dict(_VALUES if values is None else values)
    errors = dict(errors or {})
    return {
        "now_utc": NOW_UTC,
        # 取數失敗就是沒有資料，不是「有資料但旁邊掛一個旗標」（體例同 ui_v2/alo）。
        "nav": navs(nav_latest) if nav and not errors.get("nav") else [],
        "dividend": dividends() if dividend and not errors.get("dividend") else [],
        "market_indicator": market_indicators() if mi and not errors.get("market_indicator") else [],
        "fetch_log": [] if errors.get("fetch_log") else (fetch_logs() if logs is None else logs),
        "user_setting": [] if errors.get("user_setting") else user_settings(values),
        "errors": errors,
        # `44` SET-4 空狀態：存檔寫入失敗 → 該鍵輸入欄下方顯示失敗訊息原文，當下輸入留在畫面上。
        "save_errors": {},
        "save_inputs": {},
        "spec": {
            "tables": SPEC_TABLES,
            "block_sources": SPEC_BLOCK_SOURCES + tuple(extra_sources),
            "setting_keys": SPEC_SETTING_KEYS,
            "key_used_by": SPEC_KEY_USED_BY,
        },
    }


def _with(**changes):
    values = dict(_VALUES)
    values.update(changes)
    return values


def _logs_failed():
    logs = fetch_logs()
    logs.append(_log("lg-0006", FAILED_TIER, "2026-09-22T03:10:00Z", "2026-09-22T03:10:31Z", "failed", None,
                     TIER_FAIL_MESSAGE))
    return logs


def _logs_emptyresp():
    logs = fetch_logs()
    logs.append(_log("lg-0006", EMPTY_TIER, "2026-09-22T03:12:00Z", "2026-09-22T03:12:02Z", "ok", 0))
    return logs


def _logs_broken():
    logs = fetch_logs()
    for row in logs:
        if row["log_id"] == BROKEN_LOG_ID:
            row["finished_at"] = None
    return logs


# `scenario()` 認得的全部名字，照該函式裡的順序。**`page.py` 的閘門讀的就是這一份。**
ALL_SCENARIO_NAMES = (
    "ok",
    "first",
    "stale",
    "zero",
    "nolimit",
    "norows",
    "failed",
    "notier",
    "emptyresp",
    "badkind",
    "broken",
    "undef",
    "keep1",
    "navfail",
    "logfail",
    "settingfail",
    "zerotoday",
)


def scenario(name: str) -> dict:
    """回傳一個 dataset（純 dict）。前十二種對得到拍板原型控制列那十二顆，後五種是本頁加的。"""
    table = {
        "ok": lambda: _dataset(),
        # 全新環境：三張資料表與 fetch_log 皆空、十七個鍵皆未設定（`44` 4.5 表判準）。
        "first": lambda: _dataset(values={}, nav=False, dividend=False, mi=False, logs=[]),
        "stale": lambda: _dataset(values=_with(set_max_age_days="3")),
        "zero": lambda: _dataset(values=_with(set_max_age_days="0")),
        "nolimit": lambda: _dataset(values=_with(set_max_age_days=None)),
        "norows": lambda: _dataset(dividend=False),
        "failed": lambda: _dataset(values=_with(set_max_age_days="3"), logs=_logs_failed()),
        "notier": lambda: _dataset(logs=[r for r in fetch_logs() if r["source_tier"] != NO_RECORD_TIER]),
        "emptyresp": lambda: _dataset(logs=_logs_emptyresp()),
        "badkind": lambda: _dataset(values=_with(**{BAD_KIND_KEY: BAD_KIND_LITERAL})),
        "broken": lambda: _dataset(logs=_logs_broken()),
        "undef": lambda: _dataset(extra_sources=((UNDEF_BLOCK, (UNDEF_FIELD,)),)),
        "keep1": lambda: _dataset(values=_with(set_log_keep_rows="1")),
        "navfail": lambda: _dataset(errors={"nav": READ_FAIL_MESSAGE}),
        "logfail": lambda: _dataset(errors={"fetch_log": READ_FAIL_MESSAGE}),
        "settingfail": lambda: _dataset(errors={"user_setting": READ_FAIL_MESSAGE}),
        # 淨值今天才取得（距今 0 日）且上限 0 日。`44` SET-1 判準逐字「把上限設成 0 日，三列的比較欄皆為「外」且 `SET-0` 的 N 等於 3」。
        "zerotoday": lambda: _dataset(values=_with(set_max_age_days="0"), nav_latest=TODAY_FETCHED),
    }
    assert tuple(table) == ALL_SCENARIO_NAMES, (tuple(table), ALL_SCENARIO_NAMES)
    if name not in table:
        raise KeyError(f"沒有這個情境：{name!r}")
    return table[name]()


# 「存檔寫入失敗」與情境**正交**（拍板草稿：正交開關，不是第 13 種狀態）。
SAVE_FAIL_CHOICES = (False, True)
# 示範失敗的那一鍵與它的當下輸入（拍板草稿 §3 挑的鍵；登記 SET-GAP-失敗鍵）。
FAIL_KEY = "set_max_age_days"
FAIL_INPUT = "21"


def with_save_failure(dataset: dict, key: str = None, attempted: str = None) -> dict:
    """預設示範 `FAIL_KEY`；測試可點名另一鍵（驗失敗框掛在「那一鍵」下方，不是恰好掛在最後）。"""
    key = FAIL_KEY if key is None else key
    out = dict(dataset)
    out["save_errors"] = {key: SAVE_FAIL_MESSAGE}
    out["save_inputs"] = {key: FAIL_INPUT if attempted is None else attempted}
    return out


def scenario_with(name: str, *, save_failed: bool = False) -> dict:
    dataset = scenario(name)
    return with_save_failure(dataset) if save_failed else dataset


SCENARIO_LABELS = {
    "ok": "狀態 1｜全齊（灰燈）",
    "first": "狀態 2｜首次載入",
    "stale": "狀態 3｜有逾期（黃燈）",
    "zero": "狀態 4｜上限設為 0 日",
    "nolimit": "狀態 5｜上限未設",
    "norows": "狀態 6｜某類無任何列",
    "failed": "狀態 7｜某層級取數失敗（紅燈）",
    "notier": "狀態 8｜某層級從無紀錄",
    "emptyresp": "狀態 9｜取數回空",
    "badkind": "狀態 10｜值與型別不符",
    "broken": "狀態 11｜取數中斷",
    "undef": "狀態 12｜未定義欄位",
    "keep1": "狀態 13｜保留筆數設為 1",
    "navfail": "狀態 14｜nav 取數失敗",
    "logfail": "狀態 15｜fetch_log 取數失敗",
    "settingfail": "狀態 16｜user_setting 取數失敗",
    "zerotoday": "狀態 17｜上限 0 日·淨值今天才取得",
}
