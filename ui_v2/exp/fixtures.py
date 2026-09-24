# -*- coding: utf-8 -*-
"""標的探索的假資料（示意值）。純 dict／list，零 streamlit import、零網路、零舊 repo import。

欄位名與型別逐字照 `44` 第四節（`fund_profile` 第六小節、`nav` 第二小節、
`dividend` 第三小節、`user_setting` 第五小節）。**一個欄位也沒有多、也沒有改名。**

⚠️ **本檔一個真實觀測值也沒有。** 每一個會隨資料變的數，畫面上都帶「（示意）」三個字
（那三個字由 `logic.hinted()` 加，本檔只放數）。
**`44` 逐字訂死、不隨資料變的數不帶（示意）** —— 例如 `EXP-3` 的上限 3 檔、
`EXP-2` 的「近 12 個月」裡那個 12。體例沿用已拍板的草稿 `ui_prototype_exp.html` §A。

⚠️ **登記：本檔的基金母體是程式生出來的，不是手寫的。**
`_universe()` 用一個固定的整數混合函式（無亂數種子、無時間相依）生 128 檔，
所以 `EXP-7` 那三欄（套用前檔數／套用後檔數）是**真的濾出來的**，不是填上去的數字。
**這一點有意為之**：`44` `EXP-7` 判準逐字要求「最後一列的套用後檔數與 `EXP-0` 顯示的 N 相等」——
把數字寫死，那一條就只是在比兩個常數。
"""

from __future__ import annotations

# ───────────────────────── 示意母體 ─────────────────────────

# `44` 4.6 `fund_profile.ccy` 的型別是「字串／ISO 4217」。
_CCY_POOL = ("USD", "EUR", "TWD", "JPY")
# `44` 4.6 `dividend_policy` 的語意欄逐字：「配息方式：`accum`（累積）／`dist`（配息）」。
_POLICY_POOL = ("dist", "accum")

# 基金名前綴（純示意）。用途見 `_universe()` 裡那一段註解。
_NAME_PREFIX = ("丁", "丙", "乙", "甲")

UNIVERSE_SIZE = 128
FETCHED_AT = "2026-09-24T01:30:00Z"


def _mix(index: int, salt: int) -> int:
    """固定的整數混合函式。**不是亂數** —— 同一個 `index` 永遠回同一個值。

    刻意不用 `random` 與 `hash()`：前者要種子、後者在不同進程會變（`PYTHONHASHSEED`），
    兩者都會讓 `EXP-7` 的檔數在不同機器上不一樣，那一頁就不可重現了（`CLAUDE.md` §5）。
    """
    value = (index * 2654435761 + salt * 40503) & 0xFFFFFFFF
    value ^= value >> 13
    value = (value * 1274126177) & 0xFFFFFFFF
    value ^= value >> 16
    return value


def _universe() -> list:
    """128 檔示意基金。欄位逐字照 `44` 4.6。"""
    rows = []
    for index in range(1, UNIVERSE_SIZE + 1):
        code = f"F{index:04d}"
        rows.append(
            {
                "fund_code": code,
                # ⚠️ 前綴刻意讓**名字的順序與代碼的順序不同** —— 兩者同序的話，
                #    「依基金名排序」與預設的 `fund_code` 字面值排列在畫面上分不出來，
                #    那條正控就驗不到東西（本輪突變測試抓到的 `_sort_key` 全支未執行，根因之一）。
                "fund_name": f"{_NAME_PREFIX[_mix(index, 7) % len(_NAME_PREFIX)]}示意基金 {code}",
                "ccy": _CCY_POOL[_mix(index, 1) % 4],
                "inception_on": "{:04d}-{:02d}-{:02d}".format(
                    2011 + _mix(index, 3) % 16,
                    1 + _mix(index, 4) % 12,
                    1 + _mix(index, 5) % 28,
                ),
                "dividend_policy": _POLICY_POOL[_mix(index, 2) % 2],
                # `44` 4.6：`mgmt_fee_rate_pct` 可空為「是」，未知為空。
                "mgmt_fee_rate_pct": round(0.55 + (_mix(index, 6) % 200) / 100.0, 2),
                "fetched_at": FETCHED_AT,
            }
        )
    return rows


# 三條示意條件濾完之後剩下的那幾檔（由 `_universe()` ＋ `RULES_THREE` 真的濾出來，
# 本檔不另外寫死一份名單 —— 寫死就會與濾出來的結果漂移）。
NAV_DATE = "2026-09-23"
# 逐檔交錯用的那幾個淨值日（都不晚於 `NAV_DATE`）。
_NAV_DATES = ("2026-09-23", "2026-09-19", "2026-09-22", "2026-09-18", "2026-09-21")
# ⚠️ **這一檔刻意沒有 `nav`**：`44` `EXP-2` 空狀態逐字「某檔缺淨值 → 該檔仍列出，
#    缺的格顯示 `⬜`，不因為缺值就把該檔剔除」。
NO_NAV_FUND = "F0055"
# ⚠️ **這一檔刻意沒有 `mgmt_fee_rate_pct`**：`44` 4.6 表判準逐字
#    「把 `mgmt_fee_rate_pct` 清空，`EXP-6` 該欄顯示 `⬜` 而不是 0」。
NO_FEE_FUND = "F0025"

FETCH_FAIL_MESSAGE = "HTTP 503 upstream unavailable (示意訊息原文，未改寫)"
SAVE_FAIL_MESSAGE = "write conflict: setting_value rejected (示意訊息原文，未改寫)"

# ⚠️ **這個代碼刻意不在母體裡**：`44` `EXP-6` 判準逐字
#    「輸入一個不存在的 `fund_code`，畫面出現『查無此 `fund_code`』而不是空白區塊」。
MISSING_FUND_CODE = "F9999"


# ───────────────────────── 條件列 ─────────────────────────

# ⚠️ **登記：比較方向這六個字面值 `44` 一個也沒有列。**
#    `44` `EXP-1` 規則欄只寫「每列為『欄位＋比較方向＋數值』」。
#    本檔沿用已拍板的草稿 `ui_prototype_exp.html` §H 的 T-03 那一組（該處自陳是草稿那一組擬的）。
#    **這是沿用，不是本組新發明；客戶可以逐項推翻，推翻不必改 `44`。**
OPERATORS = ("等於", "不等於", "大於", "小於", "早於或等於", "晚於")

RULES_THREE = (
    {"field": "ccy", "op": "等於", "value": "USD"},
    {"field": "dividend_policy", "op": "等於", "value": "dist"},
    {"field": "inception_on", "op": "早於或等於", "value": "2014-12-31"},
)
# 第四條的數值欄留空 —— `44` `EXP-1` 空狀態逐字「數值欄留空 → 該列不生效」。
RULES_WITH_BLANK = RULES_THREE + (
    {"field": "mgmt_fee_rate_pct", "op": "小於", "value": ""},
)
# 收緊到沒有任何一檔符合。
RULES_ZERO = RULES_THREE + (
    {"field": "inception_on", "op": "早於或等於", "value": "2000-01-01"},
)
# 只剩一檔 —— `44` `EXP-0` 判準的「把條件放寬到至少一檔符合，燈由灰轉黃」下界。
RULES_ONE = ({"field": "fund_code", "op": "等於", "value": "F0025"},)
# 十檔 —— 同一行判準的「再把符合的檔數由一檔加到十檔，燈維持黃」。
# ⚠️ 這兩條是**倒推出來的**：先要「剛好十檔」這個數（`44` 判準指定），再去找哪一組條件會留下十檔。
#    `_universe()` 是固定的，所以這個數在任何機器上都一樣（見 `_mix()`）。
RULES_TEN = (
    {"field": "ccy", "op": "等於", "value": "USD"},
    {"field": "inception_on", "op": "早於或等於", "value": "2018-06-28"},
)

# 混幣別 —— `44` `EXP-3` 判準逐字要「把兩檔不同 `ccy` 的基金並排」。
# ⚠️ 上面那三條示意條件第一條就是 `ccy 等於 USD`，濾完只剩同一種幣別，
#    **那一行判準在那一組條件下結構上驗不到**。這一組刻意不濾幣別。
RULES_MIXED_CCY = (
    {"field": "dividend_policy", "op": "等於", "value": "dist"},
    {"field": "inception_on", "op": "早於或等於", "value": "2012-06-30"},
)

# `44` `EXP-2` 規則欄逐字列出的那五欄的鍵名（畫面標籤住在 `logic.COLUMN_LABELS`）。
COLUMNS_DEFAULT = ("fund_name", "ccy", "nav_date", "nav_orig_ccy", "div_ratio_pct")


# ───────────────────────── 各表 ─────────────────────────


def _navs(profiles) -> list:
    """`44` 4.2 `nav`。欄位逐字照該表。

    ⚠️ **`nav.ccy` 逐檔取自該檔的 `fund_profile.ccy`**，不是全部填同一個幣別。
    `44` 4.2 與 4.6 兩張表**各自有一個 `ccy` 欄**，`44` 沒有保證它們相同；
    但把假資料填成「全部 USD」會讓客戶 2026-09-22 設計引導第三條（多幣別逐檔標明）
    在畫面上**永遠驗不到**，那等於用假資料把一條硬要求藏起來。
    """
    rows = []
    for offset, profile in enumerate(sorted(profiles, key=lambda r: r["fund_code"])):
        if profile["fund_code"] == NO_NAV_FUND:
            continue
        rows.append(
            {
                "fund_code": profile["fund_code"],
                # ⚠️ 逐檔交錯，理由同 `fund_name` 的前綴：全部同一天的話，
                #    「依最近淨值日排序」在畫面上與預設排列分不出來。
                "nav_date": _NAV_DATES[offset % len(_NAV_DATES)],
                "nav_orig_ccy": round(9.5 + offset * 3.25, 4),
                "ccy": profile["ccy"],
                # `44` 4.2：`source_tier` 值域四個之一。
                "source_tier": "淨值",
                "is_estimated": False,
            }
        )
    return rows


def _dividends(profiles) -> list:
    """`44` 4.3 `dividend` 的最近 12 個月。

    ⚠️ **登記：本頁沒有任何一個顯示值是從這張表算出來的。**
    `44` `EXP-2` 只寫了欄名「近 12 個月配息佔淨值比」，**沒有給算式**
    （分子含不含 `div_kind` 未知的筆、分母取哪一天的 `nav_orig_ccy`、
    `dividend.ccy` 與 `nav.ccy` 不同幣時怎麼辦 —— 三件事一件都沒寫）。
    本套件**不自行選一種算法**，那一欄的數由 `div_ratio_pct()` 直接給示意值。
    這張表照 `44` 的來源欄放著，**它的用途只有一個：取數失敗時要有東西可以失敗**。
    """
    rows = []
    for offset, profile in enumerate(sorted(profiles, key=lambda r: r["fund_code"])):
        rows.append(
            {
                "fund_code": profile["fund_code"],
                "ex_date": "2026-0{}-15".format(3 + offset % 6),
                "pay_date": "2026-0{}-28".format(3 + offset % 6),
                "div_amount_orig_ccy": round(0.05 + offset * 0.011, 4),
                "ccy": profile["ccy"],
                # `44` 4.3 `div_kind`：配息類別。`unknown` 不當成 `income`。
                "div_kind": "income",
            }
        )
    return rows


def div_ratio_pct(codes) -> dict:
    """「近 12 個月配息佔淨值比」的**示意值**，逐檔一個數。

    ⛔ **這不是算出來的，也不該被讀成算出來的。** 理由見 `_dividends()` 的登記。
    """
    # ⚠️ 取模是為了讓示意值落在一個**看起來合理**的帶裡 —— 128 檔直接遞增會跑到 40% 以上，
    #    而一個 48% 的配息佔淨值比會讓讀的人以為那是 bug。示意值只表示位置與格式。
    return {code: round(1.5 + (index % 40) * 0.17, 2) for index, code in enumerate(sorted(codes))}


def _settings(
    *,
    rules=None,
    columns=None,
    sort_column=None,
    watchlist=None,
    updated_at="2026-09-23T14:02:00Z",
) -> list:
    """`44` 4.5 `user_setting`。

    `44` 4.5 逐字：「本表不預先寫入任何一列有值的設定（G3†）。未設定的鍵 `setting_value` 為空，
    畫面顯示 `⬜ 未設定`，不顯示任何候選值。」
    → 沒有值的鍵在本函式裡**照樣建列、但 `setting_value` 為 `None`、`updated_at` 為 `None`**，
    不以空字串或 `0` 補。

    ⚠️ **登記（`44` 自己沒有解的 `E-17`）**：`exp_sort_column` 存的是**一個欄位名**，
    而 `44` 4.5 的 `value_kind` 是封閉六種（`int`／`float`／`date`／`ratio`／`list`／`rules`），
    **六種一個也對不上**。本檔**不自行補第七種**，那一列的 `value_kind` 放 `None`，
    由 `logic` 就地把這個缺口寫到畫面的說明區上，**不讓它靜默通過**。
    """
    return [
        {
            "setting_key": "exp_filter_rules",
            "setting_value": list(rules) if rules else None,
            "value_kind": "rules",
            "updated_at": updated_at if rules else None,
        },
        {
            "setting_key": "exp_visible_columns",
            "setting_value": list(columns) if columns is not None else None,
            "value_kind": "list",
            "updated_at": updated_at if columns is not None else None,
        },
        {
            "setting_key": "exp_sort_column",
            "setting_value": sort_column,
            "value_kind": None,  # ⛔ 見本函式 docstring 的 `E-17` 登記
            "updated_at": updated_at if sort_column else None,
        },
        {
            "setting_key": "exp_watchlist",
            "setting_value": list(watchlist) if watchlist else None,
            "value_kind": "list",
            "updated_at": updated_at if watchlist else None,
        },
    ]


def _dataset(
    *,
    rules=None,
    columns=COLUMNS_DEFAULT,
    sort_column=None,
    watchlist=None,
    errors=None,
    save_errors=None,
    profile_rows=None,
    drop_fee_for=(),
    ratio_override=None,
) -> dict:
    profiles = list(profile_rows if profile_rows is not None else _universe())
    for row in profiles:
        if row["fund_code"] in drop_fee_for:
            # `44` 4.6：`mgmt_fee_rate_pct` 可空，未知為空 —— 不以 0 或字串補。
            row["mgmt_fee_rate_pct"] = None
    codes = [row["fund_code"] for row in profiles]
    errors = dict(errors or {})
    tables = {
        "fund_profile": profiles,
        "nav": _navs(profiles),
        "dividend": _dividends(profiles),
    }
    # ⛔ **取數失敗就是沒有資料，不是「有資料但旁邊掛一個旗標」。**
    #    `44` 5.5 `系統錯誤` 的觸發條件逐字是「取數或計算本身失敗」——
    #    一張失敗的表還留著上一輪的列，畫面會拿失敗的來源當成功的資料用，那是 §1 在擋的那一種。
    for table in tables:
        if errors.get(table):
            tables[table] = []
    return {
        "fund_profile": tables["fund_profile"],
        "nav": tables["nav"],
        "dividend": tables["dividend"],
        "user_setting": _settings(
            rules=rules, columns=columns, sort_column=sort_column, watchlist=watchlist
        ),
        "div_ratio_pct": {**div_ratio_pct(codes), **(ratio_override or {})},
        "errors": errors,
        # `44` `EXP-1`／`EXP-4`／`EXP-5` 空狀態欄各有一句「存檔寫入失敗 → …」。
        "save_errors": dict(save_errors or {}),
    }


def _slim_universe() -> list:
    """只留會被三條示意條件留下來的那幾檔 ＋ 幾檔陪襯的。

    用途：`EXP-6` 的「查無此 `fund_code`」與費率為空那兩個畫面不需要 128 檔。
    """
    keep = set(surviving_codes()) | {"F0001", "F0002", "F0003"}
    return [row for row in _universe() if row["fund_code"] in keep]


def surviving_codes() -> list:
    """三條示意條件濾完之後剩下的 `fund_code`，**真的濾出來的**。

    ⚠️ 這一支與 `logic.apply_rules()` 是**同一套比較語意的兩份實作** —— 刻意如此：
    本檔不 import `logic`（假資料不該依賴判定層），而測試會比對兩者一致。
    """
    out = []
    for row in _universe():
        if row["ccy"] != "USD":
            continue
        if row["dividend_policy"] != "dist":
            continue
        if row["inception_on"] > "2014-12-31":
            continue
        out.append(row["fund_code"])
    return out


# ───────────────────────── 情境 ─────────────────────────


def dataset_full() -> dict:
    """三條條件全設、五檔符合。"""
    return _dataset(rules=RULES_THREE, sort_column=None, watchlist=("F0050",))


def dataset_nocond() -> dict:
    """首次開啟：四個鍵一個也沒存過值（`44` 4.5「新環境初始化後，表上有值的列數為 0」）。"""
    return _dataset(rules=None, columns=None, sort_column=None, watchlist=None)


def dataset_zero() -> dict:
    """條件收緊到沒有任何一檔符合。"""
    return _dataset(rules=RULES_ZERO)


def dataset_blankvalue() -> dict:
    """第四條條件的數值欄留空 → 該列不生效。"""
    return _dataset(rules=RULES_WITH_BLANK)


def dataset_onematch() -> dict:
    return _dataset(rules=RULES_ONE)


def dataset_tenmatch() -> dict:
    return _dataset(rules=RULES_TEN)


def dataset_nocolumn() -> dict:
    """`EXP-4` 欄位一個也沒勾。"""
    return _dataset(rules=RULES_THREE, columns=())


def dataset_sortdropped() -> dict:
    """排序欄位指到一個**沒有被勾選**的欄。"""
    return _dataset(
        rules=RULES_THREE, columns=("fund_name", "ccy"), sort_column="nav_orig_ccy"
    )


def dataset_sortnav() -> dict:
    """依「最近淨值（原幣）」排序 —— 那是把不同幣別的數字拿去比大小（登記見 `logic`）。"""
    return _dataset(rules=RULES_THREE, sort_column="nav_orig_ccy")


def dataset_sortname() -> dict:
    """依「基金名」排序 —— 名字的順序與 `fund_code` 的順序不同（見 `_universe()`）。"""
    return _dataset(rules=RULES_THREE, sort_column="fund_name")


def dataset_sortccy() -> dict:
    """依「ccy」排序。**用混幣別那一組條件** —— 全 USD 的話這一欄排不出差別。"""
    return _dataset(rules=RULES_MIXED_CCY, sort_column="ccy")


def dataset_sortdate() -> dict:
    """依「最近淨值日」排序 —— 各檔的淨值日交錯（見 `_navs()`）。"""
    return _dataset(rules=RULES_THREE, sort_column="nav_date")


# ⛔ **這個覆寫是一個正控用的形狀，不是隨手挑的數**：`9.5` 與 `12.5` 的
#    **數序**（9.5 < 12.5）與**字串序**（`"12.50%" < "9.50%"`，因為 `"1" < "9"`）**相反**。
#    沒有它，「這一欄拿數去排、不是拿畫面字串去排」這句登記**連錯得出來都不會**
#    —— 本輪突變測試就是這樣抓到 `_sort_key` 整支從未被執行的。
RATIO_STRING_TRAP = {"F0025": 9.5, "F0050": 12.5}


def dataset_sortratio() -> dict:
    """依「近 12 個月配息佔淨值比」排序，而且有一檔的值會讓字串序與數序**相反**。"""
    return _dataset(
        rules=RULES_THREE, sort_column="div_ratio_pct", ratio_override=RATIO_STRING_TRAP
    )


def dataset_profilefail() -> dict:
    """`fund_profile` 取數失敗 → `EXP-2` 進 `系統錯誤`，`EXP-0` 的燈轉紅。"""
    return _dataset(rules=RULES_THREE, errors={"fund_profile": FETCH_FAIL_MESSAGE})


def dataset_profilefail_picked() -> dict:
    """⚠️ **本體與 `dataset_profilefail()` 逐字相同，故意的。**

    ⛔ **2026-09-24 就地更正：上一版把「差別」寫在這裡，而這裡沒有差別。**
    兩者真正的差別在 `scenario()` 那張表給的 `compare_checked`
    （`profilefail` 不給，`profilefail_picked` 給 `COMPARE_THREE`）——
    **勾選是使用者狀態，不是資料**，所以它不在 dataset 裡。
    ⚠️ 那一組存在的理由（寫在對的地方了）：沒有它，`EXP-6` 那條
    「上游掛掉時不要謊稱查無此代碼」的路**沒有任何情境走得到**。
    """
    return _dataset(rules=RULES_THREE, errors={"fund_profile": FETCH_FAIL_MESSAGE})


def dataset_navfail() -> dict:
    """`nav` 取數失敗（`EXP-2` 三張來源表之一）。"""
    return _dataset(rules=RULES_THREE, errors={"nav": FETCH_FAIL_MESSAGE})


def dataset_twofail() -> dict:
    """兩張來源表同時失敗、訊息相同 —— 同一句話在同一塊只能印一次。"""
    return _dataset(
        rules=RULES_THREE,
        errors={"nav": FETCH_FAIL_MESSAGE, "dividend": FETCH_FAIL_MESSAGE},
    )


def dataset_nofee() -> dict:
    """`EXP-6` 那一檔的 `mgmt_fee_rate_pct` 為空。"""
    return _dataset(
        rules=RULES_THREE, profile_rows=_slim_universe(), drop_fee_for=(NO_FEE_FUND,)
    )


def dataset_unknownfund() -> dict:
    """`EXP-6` 要顯示的那一檔不在 `fund_profile` 裡 → 「查無此 `fund_code`」。"""
    return _dataset(rules=RULES_THREE, profile_rows=_slim_universe())


def dataset_mixedccy() -> dict:
    """濾出來的那幾檔幣別不同 —— `44` `EXP-3` 判準要的那個畫面。"""
    return _dataset(rules=RULES_MIXED_CCY)


def dataset_watchall() -> dict:
    """勾起來的那幾檔**已經都在**觀察清單裡。"""
    return _dataset(rules=RULES_THREE, watchlist=tuple(surviving_codes()))


# ───────────────────────── 勾選與草稿 ─────────────────────────

# `44` `EXP-2` 規則欄：每一列兩組勾選框，一組「對照」只餵 `EXP-3`、一組「觀察清單」只餵 `EXP-5`。
# ⚠️ **這些不是預設值** —— `44` 1.1 節判準逐字要求「沒有一列帶有非空的預設值」。
#    它們是**情境**：代表「使用者已經按過了」的那個畫面。首次開啟兩組都是空的（見 `dataset_nocond`）。
COMPARE_THREE = ("F0025", "F0050", "F0055")
WATCH_TWO = ("F0050", "F0124")
# 兩檔**不同幣別**的（`F0021` 為 JPY、`F0024` 為 TWD；兩個都由 `RULES_MIXED_CCY` 濾得到）。
MIXED_PAIR = ("F0021", "F0024")


def scenario(name: str) -> dict:
    """回傳一組可以直接餵給 `logic.build_page_model(**...)` 的參數。"""
    table = {
        "full": {
            "dataset": dataset_full(),
            "compare_checked": COMPARE_THREE,
            "watch_checked": WATCH_TWO,
        },
        # 首次開啟：條件零列、兩組勾選皆空。
        "nocond": {"dataset": dataset_nocond()},
        "zero": {"dataset": dataset_zero()},
        "blankvalue": {"dataset": dataset_blankvalue(), "compare_checked": COMPARE_THREE},
        "onematch": {"dataset": dataset_onematch(), "compare_checked": ("F0025",)},
        "tenmatch": {"dataset": dataset_tenmatch(), "compare_checked": COMPARE_THREE},
        "nocolumn": {"dataset": dataset_nocolumn(), "compare_checked": COMPARE_THREE},
        "sortdropped": {"dataset": dataset_sortdropped()},
        "sortnav": {"dataset": dataset_sortnav(), "compare_checked": COMPARE_THREE},
        # ⛔ 這四個是本輪補的：在它們之前，**五個可排序欄裡有四個從來沒有被排過**，
        #    **本組實測（量測日 2026-09-24，今天仍可重現）**：把這四個拿掉，
        #    `logic._sort_key` 在**全部情境 × 兩種存檔結果**建模型的過程中被呼叫 **0 次**；
        #    四個加回去 → **46 次**。
        #    ⚠️ 「158 條全綠存活」那個數是**稽核**跑出來的，本組沒有重跑那一版。
        "sortname": {"dataset": dataset_sortname()},
        "sortccy": {"dataset": dataset_sortccy()},
        "sortdate": {"dataset": dataset_sortdate()},
        "sortratio": {"dataset": dataset_sortratio()},
        "profilefail": {"dataset": dataset_profilefail()},
        "profilefail_picked": {
            "dataset": dataset_profilefail_picked(),
            "compare_checked": COMPARE_THREE,
            "watch_checked": WATCH_TWO,
        },
        "navfail": {"dataset": dataset_navfail(), "compare_checked": COMPARE_THREE},
        "twofail": {"dataset": dataset_twofail(), "compare_checked": COMPARE_THREE},
        "nofee": {"dataset": dataset_nofee(), "compare_checked": (NO_FEE_FUND,)},
        # `EXP-6` 跟著「對照」那一組勾起的第一檔（本組判讀，登記見 `logic._build_exp6`）。
        "unknownfund": {
            "dataset": dataset_unknownfund(),
            "compare_checked": (MISSING_FUND_CODE,),
        },
        "watchall": {"dataset": dataset_watchall(), "watch_checked": WATCH_TWO},
        # 觀察清單一檔也沒勾 → `EXP-5` 的按鈕停用。
        "nowatch": {"dataset": dataset_full(), "compare_checked": COMPARE_THREE},
        # `44` `EXP-3` 判準：把兩檔不同 `ccy` 的基金並排，欄頭各自出現幣別字面值。
        "mixedccy": {"dataset": dataset_mixedccy(), "compare_checked": MIXED_PAIR},
        # 欄位的**當下值**與**已存值**不同 —— `44` `EXP-1` 塊下方逐字登記為待裁決的那一題。
        "draftdiffers": {
            "dataset": dataset_full(),
            "draft_rules": RULES_ONE,
            "compare_checked": ("F0025",),
        },
    }
    # ⚠️ 兩者不得漂移：`ALL_SCENARIO_NAMES` 是 `page.py` 的閘門讀的那一份，
    #    寫死在模組層（讓 import 得到它）；這一行保證它與本表**永遠一致**。
    assert tuple(table) == ALL_SCENARIO_NAMES, (tuple(table), ALL_SCENARIO_NAMES)
    if name not in table:
        raise KeyError(f"沒有這個情境：{name!r}")
    return table[name]


# `scenario()` 認得的**全部**名字，**照該函式裡的順序**。
# ⛔ **`page.py` 的閘門讀的就是這一份** —— 一個進得了 `scenario()`、卻進不了閘門的情境，
#    等於「做出來沒有人看得見」。姊妹頁 `hld` 在 2026-09-24 就因為閘門讀了另一份較短的清單，
#    讓三個新做的畫面**頁面永遠選不到、任何測試也沒渲染過**。本檔只有這一份，不分兩份。
ALL_SCENARIO_NAMES = (
    "full",
    "nocond",
    "zero",
    "blankvalue",
    "onematch",
    "tenmatch",
    "nocolumn",
    "sortdropped",
    "sortnav",
    "sortname",
    "sortccy",
    "sortdate",
    "sortratio",
    "profilefail",
    "profilefail_picked",
    "navfail",
    "twofail",
    "nofee",
    "unknownfund",
    "watchall",
    "nowatch",
    "mixedccy",
    "draftdiffers",
)

# 「存檔寫入失敗」與上面那一整份情境清單**正交**，不是多出來的一種情境。
# ⛔ **2026-09-24 就地更正：這裡原本寫「與上面那十七種正交，不是第十八種」——
#    當時上面已經是 19 種，而且同一份 diff 裡另一處寫「不是第十九種」，兩個數字互相打架。**
#    **會漂移的數字不寫進註解**：要知道有幾種，看 `ALL_SCENARIO_NAMES` 本身。
# ⚠️ 理由（沿用已拍板草稿 `ui_prototype_exp.html` §F 表下那一框的三條，逐條覆驗過）：
#    存檔會不會寫失敗，與「條件設了沒／濾出幾檔／欄位勾了沒」**沒有關係**；
#    做成互斥的另一種情境，等於宣稱「失敗只會發生在某一種資料狀態底下」，那不是 `44` 寫的東西。
#    做成正交的開關，才驗得到「`EXP-5` 勾選為零時那一枚是停用的、停用就沒有失敗態」這種交互作用。
SAVE_FAIL_CHOICES = (False, True)

# ⛔ **2026-09-24 第二輪稽核更正：這一行原本寫「三個」，底下列的是四個。**
# 會被「存檔」寫到的鍵（`44` `EXP-1`／`EXP-4`／`EXP-5` 的來源欄點名的那幾個）**共四個**：
# `EXP-1` 寫 `exp_filter_rules`、`EXP-4` **一枚按鈕同時寫兩鍵**
# （`exp_visible_columns` ＋ `exp_sort_column`）、`EXP-5` 寫 `exp_watchlist`。
# ⚠️ 「三」大概是照「三塊」數的 —— **塊數不等於鍵數，正是因為 `EXP-4` 那一枚寫兩鍵。**
SAVE_FAIL_KEYS = ("exp_filter_rules", "exp_visible_columns", "exp_sort_column", "exp_watchlist")


def with_save_failure(params: dict) -> dict:
    """把一組情境參數疊上「上一次存檔寫入失敗」。回新的 dict，不改原來那一份。"""
    out = dict(params)
    dataset = dict(out["dataset"])
    dataset["save_errors"] = {key: SAVE_FAIL_MESSAGE for key in SAVE_FAIL_KEYS}
    out["dataset"] = dataset
    return out


def scenario_with(name: str, *, save_failed: bool = False) -> dict:
    params = scenario(name)
    return with_save_failure(params) if save_failed else params


SCENARIO_LABELS = {
    "full": "狀態 1｜全齊",
    "nocond": "狀態 2｜尚未設定條件",
    "zero": "狀態 3｜零檔符合",
    "blankvalue": "狀態 4｜某列數值未填",
    "onematch": "狀態 5｜只有一檔符合",
    "tenmatch": "狀態 6｜十檔符合",
    "nocolumn": "狀態 7｜欄位全不勾",
    "sortdropped": "狀態 8｜排序欄被取消勾選",
    "sortnav": "狀態 9｜依最近淨值排序",
    "sortname": "狀態 9a｜依基金名排序",
    "sortccy": "狀態 9b｜依 ccy 排序",
    "sortdate": "狀態 9c｜依最近淨值日排序",
    "sortratio": "狀態 9d｜依配息比排序（字串序與數序相反）",
    "profilefail": "狀態 10｜fund_profile 取數失敗",
    "profilefail_picked": "狀態 10b｜fund_profile 取數失敗且已勾起對照",
    "navfail": "狀態 11｜nav 取數失敗",
    "twofail": "狀態 12｜兩張來源表同時失敗",
    "nofee": "狀態 13｜費率欄為空",
    "unknownfund": "狀態 14｜查無此代碼",
    "watchall": "狀態 15｜勾起的檔都已在觀察清單",
    "nowatch": "狀態 16｜觀察清單一檔也沒勾",
    "mixedccy": "狀態 17｜兩檔不同幣別並排",
    "draftdiffers": "狀態 18｜當下值與已存值不同",
}
