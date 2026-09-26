# -*- coding: utf-8 -*-
"""設定與診斷的 `44` 規格快照（第四節的表與欄位、第三節各塊的來源欄、`SET-4` 的鍵與型別）。純 tuple，零 import。

**這不是資料，也不是假資料**：它是 `SET-7`（欄位對照表）與 `SET-4`（改了會影響哪幾塊）要讀的那一份規格。
示範模式（`fixtures.py`）與正式模式（`source.py`）讀的是**同一份**（`49` §2.5：`spec` 快照維持現狀，不需要接資料）。
原本住在 `fixtures.py`；2026-09-26 set 頁接正式模式時搬來這裡 —— 正式路徑不得 import `fixtures`
（`tests/ui_v2/test_ui_v2_live_import_guard.py` 第 3 條），而正式模式同樣需要這份規格。
`fixtures.py` 以同名重新匯出，示範模式一個字都不變。

本頁執行時不去讀 `44`（登記 `SET-GAP-SET7寫死`）；這份快照與 `44` 現行文字由
`tests/ui_v2/test_set_logic.py` 逐項重抽比對，漂了就紅。
"""

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
# ⚠️ 2026-09-26 起 `alo_basis` 在實作層定為 `list`（枚舉），見下方 `IMPLEMENTATION_KINDS`；本表（示範模式讀的那一份）
#    刻意不改，示範畫面因此一字不變。
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


# 實作層定型別，客戶 2026-09-26 裁示；44 未改。
# `alo_basis`：value_kind 為 `list`（枚舉），可選值「成本」「市值」寫死在 L2
# `services/v2_tables/settings_store.py::ENUM_SETTING_VALUES`。只在正式模式套用（`dataset_spec(live=True)`）。
IMPLEMENTATION_KINDS = {"alo_basis": "list"}


def dataset_spec(extra_sources=(), *, live=False) -> dict:
    """`dataset["spec"]` 的形狀（`logic.build_page_model` 讀這一份）。`live=True` 時套用 `IMPLEMENTATION_KINDS`。"""
    keys = SPEC_SETTING_KEYS
    if live:
        keys = tuple((key, IMPLEMENTATION_KINDS.get(key, kind)) for key, kind in SPEC_SETTING_KEYS)
    return {
        "tables": SPEC_TABLES,
        "block_sources": SPEC_BLOCK_SOURCES + tuple(extra_sources),
        "setting_keys": keys,
        "key_used_by": SPEC_KEY_USED_BY,
    }
