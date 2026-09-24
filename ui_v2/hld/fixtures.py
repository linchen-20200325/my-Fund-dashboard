# -*- coding: utf-8 -*-
"""假資料（示意值）。純 dict/list，無 pandas、無網路、無舊 repo import。

每一列的欄位逐字照 `44` 第四節那幾張表：
  `holding` 十一欄／`nav` 七欄／`dividend` 七欄／`policy` 八欄／
  `fund_profile` 七欄／`user_setting` 四欄。

⚠️ 本檔的每一個數字都是**示意值**，不是任何真實觀測。
   客戶裁示本輪用假資料；本樹不接任何真實資料源、不發任何網路請求。

⚠️ **逐檔帶 `ccy`**（客戶 2026-09-22 設計引導第三條）：三檔刻意跨兩種幣別
   （AAAA／BBBB 為 USD，CCCC 為 EUR），好讓「同卡不混不同幣別做平均」這條驗得到。

⚠️ **本檔的數列刻意做成自洽的**（不是照抄草稿螢幕上那幾個數）：
   `44` HLD-7 判準要求「軌跡的輸出值與該值所在那一塊上顯示的字串**逐字相同**」，
   而草稿上的示意數字**彼此不自洽**（例：`128.40 USD` 與 `4.10%` 在任何一個單位數下
   都不能同時成立）。照抄會讓那一行判準永遠跑不過，所以本檔改為
   **只固定輸入（淨值與配息序列），輸出一律算出來**。
   逐處差異寫在本輪回報。
"""

from __future__ import annotations

from datetime import date, timedelta

CURRENCIES = ("USD", "EUR")

# `44` 4.2／4.5／4.6 三張表的 `source_tier` 欄值域（2026-09-23 補上，決策者：客戶）：
# **四個之一**，`淨值`／`配息`／`市場指標`／`其他`。同一份值域也是 `44` 5.2 `來源` 徽章的文字
# —— 該類自 2026-09-23 起**不再是開放集**（同輪就地更正）。
# ⚠️ 本檔原本寫的是 `"T1"`，那是舊 repo 的五層權威分級，**不在這四個之內**；
#    它在 `HLD-6` 的淨值表上會被畫成一枚 `來源` 徽章，等於在畫面上印一個值域外的字面值。
SOURCE_TIERS = ("淨值", "配息", "市場指標", "其他")
# `nav` 表這一欄取哪一個：本頁的 `nav` 列就是淨值來源。
SOURCE_TIER_NAV = SOURCE_TIERS[0]

# 草稿 fetchfail 那一態的訊息原文（`44`：照印，不改寫成安撫語句）。
FETCH_FAIL_MESSAGE = "ConnectionError: 來源未回應，連線逾時（示意）"

# 檢視區間（示意）。起訖刻意落在**實際有列的交易日**上，
# 這樣「區間首筆」「區間末筆」就是下面錨點那兩筆本身，不受漣漪影響。
WINDOW_START = "2026-01-01"
WINDOW_END = "2026-09-19"
FIRST_ANCHOR = "2026-01-01"
LAST_ANCHOR = "2026-09-18"

# 另一段**不重疊**的區間（`44` HLD-4 判準用得到）。
OTHER_WINDOW = ("2025-07-01", "2025-12-31")

# 只含一筆淨值的區間（`44` HLD-7 判準第三句用得到）。
ONE_NAV_WINDOW = ("2026-09-18", "2026-09-18")

_FUNDS = (
    {
        "fund_code": "AAAA",
        "fund_name": "基金 A（示意）",
        "ccy": "USD",
        "policy_id": "DIRECT",
        "units_shares": 1240.500,
        "cost_orig_ccy": 12800.00,
        "cost_twd": 398400,
        "opened_on": "2024-03-11",
        "bucket": "核心（示意）",
        "inception_on": "2023-05-04",
    },
    {
        "fund_code": "BBBB",
        "fund_name": "基金 B（示意）",
        "ccy": "USD",
        "policy_id": "P-001",
        "units_shares": 2080.000,
        "cost_orig_ccy": 16400.00,
        "cost_twd": 511800,
        "opened_on": "2024-09-02",
        "bucket": "核心（示意）",
        "inception_on": "2022-11-01",
    },
    {
        "fund_code": "CCCC",
        "fund_name": "基金 C（示意）",
        "ccy": "EUR",
        "policy_id": "DIRECT",
        "units_shares": 820.000,
        "cost_orig_ccy": 11900.00,
        "cost_twd": 401500,
        "opened_on": "2025-06-02",
        "bucket": "衛星（示意）",
        "inception_on": "2023-02-15",
    },
)

# 淨值錨點：(日期, 值)。段與段之間以工作日線性內插，另加一層**零均值的確定性漣漪**
# （漣漪在每一段的兩端為 0，所以錨點上的值是精確的）。
# 漣漪存在的唯一理由：沒有它，日報酬標準差會是 0，「期間波動」就永遠印 0.00% ——
# 那不是造假，但它會讓這張卡看起來像壞掉的。
_ANCHORS = {
    "AAAA": (
        ("2025-06-02", 9.2000),
        (FIRST_ANCHOR, 10.0000),
        ("2026-04-15", 11.0000),
        ("2026-06-15", 9.7680),
        (LAST_ANCHOR, 10.3280),
    ),
    "BBBB": (
        ("2025-06-02", 7.5000),
        (FIRST_ANCHOR, 8.0000),
        ("2026-03-10", 8.6000),
        ("2026-05-20", 7.9636),
        (LAST_ANCHOR, 8.0848),
    ),
    "CCCC": (
        ("2025-06-02", 14.0000),
        (FIRST_ANCHOR, 15.0000),
        ("2026-05-05", 16.0000),
        ("2026-07-14", 15.2000),
        (LAST_ANCHOR, 14.6775),
    ),
}
_RIPPLE = 0.008  # 0.8%

# 配息：(除息日, 入帳日或 None, 每單位金額, 類別)
_DIVIDENDS = {
    "AAAA": (
        ("2025-08-15", "2025-08-20", 0.1010, "income"),
        ("2026-01-15", "2026-01-20", 0.1059, "income"),
        ("2026-04-15", "2026-04-20", 0.1059, "income"),
        ("2026-07-15", "2026-07-20", 0.1059, "income"),
        ("2026-09-16", "2026-09-21", 0.1059, "principal"),
    ),
    "BBBB": (
        ("2025-09-12", "2025-09-17", 0.1600, "principal"),
        ("2026-02-13", "2026-02-18", 0.1698, "income"),
        ("2026-05-15", "2026-05-20", 0.1698, "principal"),
        ("2026-08-14", None, 0.1698, "income"),
        ("2026-09-11", "2026-09-16", 0.1698, "principal"),
    ),
    "CCCC": (
        ("2025-10-10", "2025-10-15", 0.1400, "income"),
        ("2026-02-10", "2026-02-13", 0.1492, "income"),
        ("2026-05-12", "2026-05-15", 0.1492, "income"),
        ("2026-07-10", "2026-07-15", 0.1492, "unknown"),
    ),
}

# 只有 `2026-09-17` 這一筆是推估值 —— `44` HLD-6 判準要求
# 「該列出現『推估』徽章而**相鄰列沒有**」，所以刻意只標一筆。
_ESTIMATED = {("AAAA", "2026-09-17")}


# ───────────────────────── 產生器 ─────────────────────────


def _weekdays(start: str, end: str, *, include_end: bool) -> list:
    """工作日序列。週末沒有列 —— `44` 4.2：那是正常狀態，不補列。"""
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    out, cursor = [], first
    while cursor < last or (include_end and cursor == last):
        if cursor.weekday() < 5:
            out.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return out


def _series(anchors) -> list:
    rows = []
    for (date0, value0), (date1, value1) in zip(anchors, anchors[1:]):
        days = _weekdays(date0, date1, include_end=False)
        span = len(days)
        for index, day in enumerate(days):
            share = index / span if span else 0.0
            base = value0 + (value1 - value0) * share
            window = 1.0 - abs(2.0 * share - 1.0)
            noise = ((index * 7919) % 101 - 50) / 50.0
            rows.append((day, round(base * (1.0 + _RIPPLE * window * noise), 4)))
    rows.append((anchors[-1][0], anchors[-1][1]))
    return rows


def _plus_days(day: str, days: int) -> str:
    return (date.fromisoformat(day) + timedelta(days=days)).isoformat()


# ───────────────────────── 五張表 ─────────────────────────


def holdings() -> list:
    return [
        {
            "holding_id": f"H-{fund['fund_code']}",
            "policy_id": fund["policy_id"],
            "fund_code": fund["fund_code"],
            "fund_name": fund["fund_name"],
            "ccy": fund["ccy"],
            "units_shares": fund["units_shares"],
            "cost_orig_ccy": fund["cost_orig_ccy"],
            "cost_twd": fund["cost_twd"],
            "opened_on": fund["opened_on"],
            "bucket": fund["bucket"],
            "last_synced_at": "2026-09-19T01:00:00Z",
        }
        for fund in _FUNDS
    ]


def navs() -> list:
    rows = []
    for fund in _FUNDS:
        code = fund["fund_code"]
        for day, value in _series(_ANCHORS[code]):
            rows.append(
                {
                    "fund_code": code,
                    "nav_date": day,
                    "nav_orig_ccy": value,
                    "ccy": fund["ccy"],
                    "source_tier": SOURCE_TIER_NAV,
                    "is_estimated": (code, day) in _ESTIMATED,
                    "fetched_at": _plus_days(day, 1) + "T02:00:00Z",
                }
            )
    return rows


def dividends() -> list:
    rows = []
    for fund in _FUNDS:
        code = fund["fund_code"]
        for ex_date, pay_date, per_unit, kind in _DIVIDENDS[code]:
            rows.append(
                {
                    "fund_code": code,
                    "ex_date": ex_date,
                    "pay_date": pay_date,
                    "div_per_unit_orig_ccy": per_unit,
                    "ccy": fund["ccy"],
                    "div_kind": kind,
                    "fetched_at": _plus_days(ex_date, 1) + "T02:00:00Z",
                }
            )
    return rows


def policies() -> list:
    """`44` 4.4 保留列：`DIRECT` 那一列固定存在。"""
    return [
        {
            "policy_id": "DIRECT",
            "policy_name": "直接持有",
            "issuer": "—",
            "ccy": "TWD",
            "premium_paid_twd": 0,
            "fee_rate_pct": None,
            "opened_on": "2024-01-01",
            "status": "active",
        },
        {
            "policy_id": "P-001",
            "policy_name": "某某投資型保單（示意）",
            "issuer": "某某人壽（示意）",
            "ccy": "TWD",
            "premium_paid_twd": 600000,
            "fee_rate_pct": 1.25,
            "opened_on": "2024-08-01",
            "status": "active",
        },
    ]


def fund_profiles(*, inception_override=None) -> list:
    override = inception_override or {}
    return [
        {
            "fund_code": fund["fund_code"],
            "fund_name": fund["fund_name"],
            "ccy": fund["ccy"],
            "inception_on": override.get(fund["fund_code"], fund["inception_on"]),
            "dividend_policy": "dist",
            "mgmt_fee_rate_pct": 1.50,
            "fetched_at": "2026-09-19T01:00:00Z",
        }
        for fund in _FUNDS
    ]


_RULES_DEFAULT = (
    {"indicator": "最大回撤", "direction": "低於", "value": -10.00},
    {"indicator": "配息佔淨值比", "direction": "高於", "value": 6.00},
)
_RULES_NOEXCEED = (
    {"indicator": "最大回撤", "direction": "低於", "value": -30.00},
    {"indicator": "配息佔淨值比", "direction": "高於", "value": 20.00},
)


def user_settings(*, window=None, rules=None, updated_at=None) -> list:
    """`44` 4.5：未設定的鍵 `setting_value` 為空，**不預先寫入任何一列有值的設定**（G3†）。"""
    start, end = window if window else (None, None)
    return [
        {
            "setting_key": "hld_window_start",
            "setting_value": start,
            "value_kind": "date",
            "updated_at": updated_at,
        },
        {
            "setting_key": "hld_window_end",
            "setting_value": end,
            "value_kind": "date",
            "updated_at": updated_at,
        },
        {
            "setting_key": "hld_deviation_rules",
            "setting_value": list(rules) if rules else None,
            "value_kind": "rules",
            "updated_at": updated_at,
        },
    ]


def _dataset(
    *,
    holding=None,
    nav=None,
    dividend=None,
    profiles=None,
    window=None,
    rules=None,
    errors=None,
    updated_at="2026-09-19T03:20:00Z",
) -> dict:
    return {
        "holding": holdings() if holding is None else holding,
        "nav": navs() if nav is None else nav,
        "dividend": dividends() if dividend is None else dividend,
        "policy": policies(),
        "fund_profile": fund_profiles() if profiles is None else profiles,
        "user_setting": user_settings(window=window, rules=rules, updated_at=updated_at),
        "errors": dict(errors or {}),
    }


# ───────────────────────── 六種狀態 ＋ 判準用的幾種 ─────────────────────────


def dataset_full() -> dict:
    """狀態 1｜全齊。兩檔超出門檻。"""
    return _dataset(window=(WINDOW_START, WINDOW_END), rules=_RULES_DEFAULT)


def dataset_srcmiss() -> dict:
    """狀態 2｜某塊缺來源：把 CCCC 的淨值整個抽掉。

    ⚠️ 本情境**另把 CCCC 那一筆 `unknown` 配息改成 `income`**，理由寫明：
    `44` HLD-8 空狀態有一句「某檔缺淨值 → 該檔的最大回撤欄顯示 `⬜ 資料未備`，
    **同一列的本金類配息佔比照出數**」。若同一檔又帶 `unknown`，那一欄會進
    `⬜ 不適用：配息類別未知`，**這一句判準就永遠驗不到**。
    兩種示範各自需要一檔，本檔讓它們落在不同情境，不落在同一檔。
    """
    rows = []
    for row in dividends():
        row = dict(row)
        if row["fund_code"] == "CCCC" and row["div_kind"] == "unknown":
            row["div_kind"] = "income"
        rows.append(row)
    return _dataset(
        nav=[row for row in navs() if row["fund_code"] != "CCCC"],
        dividend=rows,
        window=(WINDOW_START, WINDOW_END),
        rules=_RULES_DEFAULT,
    )


def dataset_bizexc() -> dict:
    """狀態 3｜某塊業務例外：CCCC 成立日晚於區間起點，且門檻調到沒有一檔超出。"""
    return _dataset(
        profiles=fund_profiles(inception_override={"CCCC": "2026-04-08"}),
        window=(WINDOW_START, WINDOW_END),
        rules=_RULES_NOEXCEED,
    )


def dataset_fetchfail() -> dict:
    """狀態 4｜某塊取數失敗：配息來源失敗。"""
    return _dataset(
        window=(WINDOW_START, WINDOW_END),
        rules=_RULES_DEFAULT,
        errors={"dividend": FETCH_FAIL_MESSAGE},
    )


def dataset_nothr() -> dict:
    """狀態 5｜門檻未設：區間有設、門檻一列也沒有。"""
    return _dataset(window=(WINDOW_START, WINDOW_END), rules=None)


def dataset_empty() -> dict:
    """狀態 6｜全空（首次開啟）：持倉表為空、區間未填、門檻未設。"""
    return _dataset(
        holding=[],
        nav=[],
        dividend=[],
        profiles=[],
        window=None,
        rules=None,
        updated_at=None,
    )


def dataset_emptyfail() -> dict:
    """狀態 7｜全空而且有一塊取數失敗（客戶 2026-09-23 裁示「改紅後要補 fixture」）。

    與狀態 6 的差別**只有一個**：配息來源取數失敗。
    `44` :489 規則欄「任一塊為 `系統錯誤` → 燈為**紅**」與同塊空狀態欄
    「持倉表為空 → 燈為**灰**」在這一組資料上**同時命中**，客戶裁示取紅。
    方向出自 `44` :1620 逐字「**一句把空白報成平安的文案，比沒有文案更誤導**」。

    ⚠️ **刻意只讓配息那一源失敗，不讓三源全失敗** —— 這樣畫面上同時看得到
    「紅燈 ＋ 它點名的那一塊」與「另外兩塊仍然是空的」，
    驗的是**先後**（紅壓過灰），不是「全部都紅」。
    """
    return _dataset(
        holding=[],
        nav=[],
        dividend=[],
        profiles=[],
        window=None,
        rules=None,
        updated_at=None,
        errors={"dividend": FETCH_FAIL_MESSAGE},
    )


def dataset_noexceed() -> dict:
    """把門檻調到沒有任何一檔超出（`44` HLD-0 與 HLD-1 判準第一句）。"""
    return _dataset(window=(WINDOW_START, WINDOW_END), rules=_RULES_NOEXCEED)


def dataset_other_window() -> dict:
    """換一段與原本那段不重疊、而 HLD-8 兩欄都出得了數的期間。"""
    return _dataset(window=OTHER_WINDOW, rules=_RULES_DEFAULT)


def dataset_one_nav() -> dict:
    """把區間縮到只含一筆淨值。"""
    return _dataset(window=ONE_NAV_WINDOW, rules=_RULES_DEFAULT)


def dataset_badrange() -> dict:
    """起日晚於迄日 —— 三個鍵都還沒有存過任何值。"""
    return _dataset(window=None, rules=None, updated_at=None)


_BAD_FIELDS = {"window_start": "2026-09-19", "window_end": "2026-01-01"}


def scenario(name: str) -> dict:
    """回傳一組可以直接餵給 `logic.build_page_model(**...)` 的參數。"""
    table = {
        "full": {"dataset": dataset_full()},
        "srcmiss": {"dataset": dataset_srcmiss()},
        "bizexc": {"dataset": dataset_bizexc()},
        "fetchfail": {"dataset": dataset_fetchfail()},
        "nothr": {"dataset": dataset_nothr()},
        "empty": {"dataset": dataset_empty()},
        "emptyfail": {"dataset": dataset_emptyfail()},
        "noexceed": {"dataset": dataset_noexceed()},
        "other_window": {"dataset": dataset_other_window()},
        "onenav": {"dataset": dataset_one_nav()},
        # 欄位填了一段壞區間，而三個鍵一個也沒存過 → 不套用也不存檔。
        "badrange": {"dataset": dataset_badrange(), "fields": dict(_BAD_FIELDS)},
        # 已套用的是「全齊」那一組；欄位當下被改成壞區間 →
        # 六塊的主值必須與套用前逐字相同（`44` HLD-4 判準）。
        "full_then_badrange": {"dataset": dataset_full(), "fields": dict(_BAD_FIELDS)},
    }
    if name not in table:
        raise KeyError(f"沒有這個情境：{name!r}")
    return table[name]


# 草稿上方那排狀態鈕的六種（順序照草稿）＋ 客戶 2026-09-23 裁示補的第七種。
# ⚠️ ~~**`ui_v2/app_hld.py` 的 docstring 也列了一份情境清單，本輪沒有動它** ——~~
# ~~   那一檔不在本輪的檔案邊界內。**已停下來回報，未自行修改。**~~
# → **2026-09-24 就地更正：那一句已經過期（有意識的更正，不是漏刪；決策者：總管）。**
#   **舊表述在寫下當時為真** —— 那一輪該檔確實不在邊界內，停下來回報是對的處置。
#   **被權衡掉的是它的前提**：總管其後**授權動那一檔的那一行**，本組已補上 `emptyfail`。
#   ⚠️ **而且那一句留著會自相矛盾**：本檔新增的兩條 docstring 正控
#   （`test_進入點docstring列的情境集合等於SCENARIO_NAMES` 與同組那一條）
#   **必須**靠那個改動才會綠 —— 一邊說沒動，一邊靠它過測試。
SCENARIO_NAMES = (
    "full", "srcmiss", "bizexc", "fetchfail", "nothr", "empty", "emptyfail",
)

SCENARIO_LABELS = {
    "full": "狀態 1｜全齊",
    "srcmiss": "狀態 2｜某塊缺來源",
    "bizexc": "狀態 3｜某塊業務例外",
    "fetchfail": "狀態 4｜某塊取數失敗",
    "nothr": "狀態 5｜門檻未設",
    "empty": "狀態 6｜全空（首次開啟）",
    "emptyfail": "狀態 7｜全空而且有一塊取數失敗",
}


def all_datasets() -> dict:
    return {name: scenario(name)["dataset"] for name in SCENARIO_NAMES}
