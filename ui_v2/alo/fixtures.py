# -*- coding: utf-8 -*-
"""資產配置的假資料（示意值）。純 dict／list，零 streamlit import、零網路、零舊 repo import。

欄位名與型別逐字照 `44` 第四節（`holding` 4.1、`nav` 4.2、`policy` 4.4、
`market_indicator` 與 `user_setting` 4.5）。**一個欄位也沒有多、也沒有改名。**

⚠️ **本檔一個真實觀測值也沒有。** 基金名、類別名一律帶「（示意）」；
數字只表示位置與格式。頁首副標與每一塊的說明行會寫明「本塊數字皆為示意值」
—— 本頁**不**像 `ui_v2/hld` 與 `ui_v2/exp` 那樣在每一個數字後面加「（示意）」，理由見 `logic.HINT_NOTE` 上方的登記。

⚠️ **示意數字刻意避開容許帶的端點**：`full` 的三個差距是 +6.0／-1.0／-5.0 個百分點，
容許帶 4（`inband` 為 8），沒有一個剛好等於容許帶 —— `44` 沒有寫端點算內還是外
（登記 `ALO-GAP-端點`，見 `logic`），示意值不該替 `44` 把那個洞蓋掉。
"""

from __future__ import annotations

FETCHED_AT = "2026-09-23T01:30:00Z"
SYNCED_AT = "2026-09-23T01:00:00Z"
UPDATED_AT = "2026-09-20T06:00:00Z"
NAV_DATE = "2026-09-23"
PREV_NAV_DATE = "2026-09-22"

FETCH_FAIL_MESSAGE = "HTTP 503 upstream unavailable（示意訊息原文，未改寫）"
SAVE_FAIL_MESSAGE = "write conflict: setting_value rejected（示意訊息原文，未改寫）"

# 類別名：`44` ALO-1 逐字「類別名稱一律由使用者新增與命名（G3†）」——
# 下面三個是「使用者已經命名好的」示意值，不是本頁提供的預設組合。
CORE = "核心（示意）"
SATELLITE = "衛星（示意）"
CASH = "現金（示意）"
BOND = "債券（示意）"
BUCKET_NAMES = (CORE, SATELLITE, CASH)

# `44` 4.4：`DIRECT` 那一列固定存在。
_POLICIES = (
    {
        "policy_id": "DIRECT",
        "policy_name": "直接持有",
        "issuer": "—",
        "ccy": "TWD",
        "premium_paid_twd": 0,
        "fee_rate_pct": None,
        "opened_on": "2020-01-01",
        "status": "active",
    },
    {
        "policy_id": "P001",
        "policy_name": "示意投資型保單甲",
        "issuer": "示意發行單位",
        "ccy": "USD",
        "premium_paid_twd": 900000,
        "fee_rate_pct": 1.2,
        "opened_on": "2021-03-15",
        "status": "active",
    },
)

# 成本合計 1,000,000：核心 660,000（66%）、衛星 290,000（29%）、現金 50,000（5%）。
_HOLDINGS = (
    {
        "holding_id": "H001",
        "policy_id": "P001",
        "fund_code": "AAAA",
        "fund_name": "全球股票示意基金",
        "ccy": "USD",
        "units_shares": 1000.0,
        "cost_orig_ccy": 14500.0,
        "cost_twd": 460000,
        "opened_on": "2021-04-01",
        "bucket": CORE,
        "last_synced_at": SYNCED_AT,
    },
    {
        "holding_id": "H002",
        "policy_id": "DIRECT",
        "fund_code": "BBBB",
        "fund_name": "臺灣中小示意基金",
        "ccy": "TWD",
        "units_shares": 10000.0,
        "cost_orig_ccy": 200000.0,
        "cost_twd": 200000,
        "opened_on": "2022-06-10",
        "bucket": CORE,
        "last_synced_at": SYNCED_AT,
    },
    {
        "holding_id": "H003",
        "policy_id": "P001",
        "fund_code": "CCCC",
        "fund_name": "高收益債示意基金",
        "ccy": "USD",
        "units_shares": 3000.0,
        "cost_orig_ccy": 9100.0,
        "cost_twd": 290000,
        "opened_on": "2021-04-01",
        "bucket": SATELLITE,
        "last_synced_at": SYNCED_AT,
    },
    {
        "holding_id": "H004",
        "policy_id": "DIRECT",
        "fund_code": "DDDD",
        "fund_name": "貨幣市場示意基金",
        "ccy": "TWD",
        "units_shares": 5000.0,
        "cost_orig_ccy": 50000.0,
        "cost_twd": 50000,
        "opened_on": "2023-01-05",
        "bucket": CASH,
        "last_synced_at": SYNCED_AT,
    },
)
UNBUCKETED_FUND = "CCCC"

# 每檔兩筆淨值，最近一筆是 `NAV_DATE`（`44` ALO-6 來源欄逐字「`nav.nav_orig_ccy` 最近一筆」）。
_NAV_POINTS = {
    "AAAA": (("2026-09-22", 15.10, "USD"), ("2026-09-23", 15.20, "USD")),
    "BBBB": (("2026-09-22", 21.40, "TWD"), ("2026-09-23", 21.50, "TWD")),
    "CCCC": (("2026-09-22", 3.08, "USD"), ("2026-09-23", 3.10, "USD")),
    "DDDD": (("2026-09-22", 10.01, "TWD"), ("2026-09-23", 10.01, "TWD")),
}

# `fx_twd_per_usd`：三筆。第三筆的 `obs_date` 晚於淨值日 —— `44` ALO-2 來源欄逐字
# 「取 `obs_date` 不晚於 `nav.nav_date` 的最近一筆」，那一筆不得被取用（有測試釘住）。
FX_KEY = "fx_twd_per_usd"
_FX_POINTS = (
    ("2026-09-19", "2026-09-22", 31.80),
    ("2026-09-22", "2026-09-23", 32.00),
    ("2026-09-24", "2026-09-24", 32.30),
)
FX_USED = 32.00

TARGETS = (
    {"bucket": CORE, "weight_ratio": 0.60},
    {"bucket": SATELLITE, "weight_ratio": 0.30},
    {"bucket": CASH, "weight_ratio": 0.10},
)
# 合計 0.9，而且有一列比重留空（`44` ALO-1 空狀態逐字「某列比重留空 → 該列不計入合計」）。
TARGETS_PARTIAL = (
    {"bucket": CORE, "weight_ratio": 0.60},
    {"bucket": SATELLITE, "weight_ratio": 0.20},
    {"bucket": CASH, "weight_ratio": 0.10},
    {"bucket": BOND, "weight_ratio": None},
)
TOLERANCE = 4.0
TOLERANCE_WIDE = 8.0

SCENARIO_ROWS = (
    {"bucket": SATELLITE, "amount_twd": 100000},
    {"bucket": CASH, "amount_twd": 50000},
)
# 一列金額留空、一列負向金額大於該類別現值（現金現值 50,000）。
SCENARIO_ROWS_PARTIAL = (
    {"bucket": SATELLITE, "amount_twd": 100000},
    {"bucket": CORE, "amount_twd": None},
    {"bucket": CASH, "amount_twd": -80000},
)


def holdings(*, unbucket=None) -> list:
    rows = []
    for row in _HOLDINGS:
        copy = dict(row)
        if copy["fund_code"] == unbucket:
            # `44` 4.1：`bucket` 可空，空值表示未分類 —— 放 `None`，不放空字串。
            copy["bucket"] = None
        rows.append(copy)
    return rows


def navs(codes) -> list:
    rows = []
    for code in codes:
        for nav_date, value, ccy in _NAV_POINTS[code]:
            rows.append(
                {
                    "fund_code": code,
                    "nav_date": nav_date,
                    "nav_orig_ccy": value,
                    "ccy": ccy,
                    "source_tier": "淨值",
                    "is_estimated": False,
                    "fetched_at": FETCHED_AT,
                }
            )
    return rows


def policies() -> list:
    return [dict(row) for row in _POLICIES]


def market_indicators(*, fx=True) -> list:
    if not fx:
        return []
    return [
        {
            "indicator_key": FX_KEY,
            "obs_date": obs,
            "release_date": release,
            "value_num": value,
            "value_unit": "TWD/USD",
            "source_tier": "市場指標",
            "is_revised": False,
            "fetched_at": FETCHED_AT,
        }
        for obs, release, value in _FX_POINTS
    ]


def _row(key, value, kind):
    """`44` 4.5 `user_setting`：未設定的鍵照樣建列，`setting_value` 與 `updated_at` 皆為 `None`。"""
    return {
        "setting_key": key,
        "setting_value": value,
        "value_kind": kind,
        "updated_at": UPDATED_AT if value is not None else None,
    }


def user_settings(*, targets, tolerance, basis, bucket_names, scenario_rows) -> list:
    """五個鍵。`44` 4.5「沒有內建值」：沒有值的鍵 `setting_value` 為 `None`，不以 0 或空字串補。

    ⚠️ **登記 `ALO-GAP-value_kind`**：`alo_basis` 存的是「成本或市值」二選一，
    而 `44` 4.5 的 `value_kind` 封閉六種（`int`／`float`／`date`／`ratio`／`list`／`rules`）
    **沒有一種對得上**。本檔不自行補第七種，那一列的 `value_kind` 放 `None`。
    `alo_target_weights` 是「類別＋比重」的一組列，本檔放 `list`（本組判讀）。
    """
    return [
        _row("alo_target_weights", [dict(r) for r in targets] if targets else None, "list"),
        _row("alo_tolerance_pp", tolerance, "float"),
        _row("alo_basis", basis, None),
        _row("alo_bucket_names", list(bucket_names) if bucket_names else None, "list"),
        _row("alo_scenario_input", [dict(r) for r in scenario_rows] if scenario_rows else None, "list"),
    ]


def _dataset(
    *,
    with_holdings=True,
    targets=TARGETS,
    tolerance=TOLERANCE,
    basis="cost",
    bucket_names=BUCKET_NAMES,
    scenario_rows=SCENARIO_ROWS,
    fx=True,
    unbucket=None,
    errors=None,
) -> dict:
    errors = dict(errors or {})
    hold = holdings(unbucket=unbucket) if with_holdings and not errors.get("holding") else []
    return {
        "holding": hold,
        "nav": navs([h["fund_code"] for h in hold]),
        "policy": [] if errors.get("policy") else policies(),
        # 取數失敗就是沒有資料，不是「有資料但旁邊掛一個旗標」（體例同 ui_v2/exp）。
        "market_indicator": market_indicators(fx=fx and not errors.get("market_indicator")),
        "user_setting": [] if errors.get("user_setting") else user_settings(
            targets=targets,
            tolerance=tolerance,
            basis=basis,
            bucket_names=bucket_names,
            scenario_rows=scenario_rows,
        ),
        # 取數失敗照 `44` 5.5 系統錯誤通用模板畫（見 `logic.GAPS` 的 ALO-GAP-取數失敗）。
        "errors": errors,
        # `44` ALO-1／ALO-3／ALO-4 空狀態欄各有一句「存檔寫入失敗 → …」。
        "save_errors": {},
    }


# `scenario()` 認得的全部名字，照該函式裡的順序。**`page.py` 的閘門讀的就是這一份。**
ALL_SCENARIO_NAMES = (
    "full",
    "first",
    "noholding",
    "notarget",
    "nobasis",
    "inband",
    "notol",
    "mvbasis",
    "nofx",
    "unbkt",
    "nobucket",
    "partial",
    "holdfail",
    "fxfail",
    "settingfail",
    "policyfail",
)


def scenario(name: str) -> dict:
    """回傳一個 dataset（純 dict）。"""
    table = {
        "full": lambda: _dataset(),
        # 全新環境：持倉表為空、五個鍵皆未設定（`44` 4.5「新環境初始化後，表上有值的列數為 0」）。
        "first": lambda: _dataset(
            with_holdings=False,
            targets=None,
            tolerance=None,
            basis=None,
            bucket_names=None,
            scenario_rows=None,
        ),
        # 設定都在、持倉表為空。
        "noholding": lambda: _dataset(with_holdings=False),
        "notarget": lambda: _dataset(targets=None),
        "nobasis": lambda: _dataset(basis=None),
        "inband": lambda: _dataset(tolerance=TOLERANCE_WIDE),
        "notol": lambda: _dataset(tolerance=None),
        "mvbasis": lambda: _dataset(basis="mv"),
        "nofx": lambda: _dataset(basis="mv", fx=False),
        "unbkt": lambda: _dataset(unbucket=UNBUCKETED_FUND),
        "nobucket": lambda: _dataset(bucket_names=None),
        "partial": lambda: _dataset(targets=TARGETS_PARTIAL, scenario_rows=SCENARIO_ROWS_PARTIAL),
        # holding 取數失敗（持倉表是空是滿不知道）。
        "holdfail": lambda: _dataset(errors={"holding": FETCH_FAIL_MESSAGE}),
        # 市值基準下匯率那張表取數失敗。
        "fxfail": lambda: _dataset(basis="mv", errors={"market_indicator": FETCH_FAIL_MESSAGE}),
        # user_setting 取數失敗（值取不到，不是沒設定）。
        "settingfail": lambda: _dataset(errors={"user_setting": FETCH_FAIL_MESSAGE}),
        # policy 取數失敗（只有 ALO-6 讀它）。
        "policyfail": lambda: _dataset(errors={"policy": FETCH_FAIL_MESSAGE}),
    }
    assert tuple(table) == ALL_SCENARIO_NAMES, (tuple(table), ALL_SCENARIO_NAMES)
    if name not in table:
        raise KeyError(f"沒有這個情境：{name!r}")
    return table[name]()


# 「存檔寫入失敗」與情境**正交**：存檔會不會寫失敗，與資料狀態無關（體例同 `ui_v2/exp`）。
SAVE_FAIL_CHOICES = (False, True)
# 會被「存檔」寫到的鍵：ALO-1 兩鍵、ALO-3 一鍵、ALO-4 兩鍵，共五個。
SAVE_FAIL_KEYS = (
    "alo_target_weights",
    "alo_tolerance_pp",
    "alo_scenario_input",
    "alo_basis",
    "alo_bucket_names",
)


def with_save_failure(dataset: dict) -> dict:
    out = dict(dataset)
    out["save_errors"] = {key: SAVE_FAIL_MESSAGE for key in SAVE_FAIL_KEYS}
    return out


def scenario_with(name: str, *, save_failed: bool = False) -> dict:
    dataset = scenario(name)
    return with_save_failure(dataset) if save_failed else dataset


SCENARIO_LABELS = {
    "full": "狀態 1｜全齊·超出容許帶",
    "first": "狀態 2｜首次載入",
    "noholding": "狀態 3｜持倉表為空",
    "notarget": "狀態 4｜目標未設",
    "nobasis": "狀態 5｜基準未選",
    "inband": "狀態 6｜皆在容許帶內",
    "notol": "狀態 7｜容許帶未設",
    "mvbasis": "狀態 8｜市值基準",
    "nofx": "狀態 9｜市值基準缺換算匯率",
    "unbkt": "狀態 10｜某檔未分類",
    "nobucket": "狀態 11｜類別一個也沒定義",
    "partial": "狀態 12｜輸入未完成·目標合計不為一",
    "holdfail": "狀態 13｜holding 取數失敗",
    "fxfail": "狀態 14｜市值基準下匯率取數失敗",
    "settingfail": "狀態 15｜user_setting 取數失敗",
    "policyfail": "狀態 16｜policy 取數失敗",
}
