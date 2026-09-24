# -*- coding: utf-8 -*-
"""標的探索純邏輯。零 streamlit import、零舊 repo import、零網路。

所有判定住在這裡；page.py 只負責把 build_page_model() 產出的模型畫出來。
理由：streamlit 在本環境要靠 scratchpad 才匯入得到，邏輯綁進 streamlit 會讓測試跑不起來。

模型慣例：底線開頭的鍵是**機器用**（狀態、色調、層號…），不開頭底線的鍵是**畫面文字**。

⚠️ 本檔逐處標了「登記」的地方，是 `44` 沒有寫、而不決定就畫不出來的。
   一律照最保守的畫法做，**不自行發明規格、不補 SSOT 缺口**，逐筆列進回報。
"""

from __future__ import annotations

# ───────────────────────── 常數（逐字引 `44`） ─────────────────────────

# `44` 5.1 卡片四狀態。本檔沿用「逐主值判定」那個現行讀法，狀態不掛在整張卡。
STATE_OK = "ok"
STATE_MISSING = "資料未備"
STATE_BIZ = "業務例外"
STATE_ERROR = "系統錯誤"

# `44` 5.2 徽章：`狀態` 那一列的七個字面值（封閉列舉）。
STATUS_BADGE_LITERALS = (
    "資料未備",
    "不適用",
    "取數失敗",
    "推估",
    "修正過",
    "部分缺",
    "未定義",
)

# `44` 5.3 按鈕：八類，八類之外沒有第九類。
BUTTON_KINDS = ("取數", "套用", "展開", "匯出", "新增列", "清除", "導覽", "存檔")

# `44` 5.3 禁止欄：這四張表由 Sheets 維護，本儀表板唯讀，沒有任何一類按鈕寫入它們。
READONLY_TABLES = ("holding", "policy", "nav", "dividend")

# `44` 4.5 `user_setting.value_kind`：封閉六種。
VALUE_KINDS = ("int", "float", "date", "ratio", "list", "rules")

# `source_tier` 的值域：封閉四種（`44` 2026-09-23 逐欄補上）。
# ⚠️ **帶這一欄的是 `nav`、`market_indicator`、`fetch_log` 三張表** ——
#    `fund_profile`（`44` 4.6）**沒有這一欄**，所以本頁的候選清單拿不到任何來源層級字面值。
#    ⛔ 這正是 `E-21` 那兩枚徽章只能畫成佔位的原因之一：**本頁沒有一個真的層級值可以填。**
SOURCE_TIERS = ("淨值", "配息", "市場指標", "其他")

_BUTTON_WRITES = {
    "取數": frozenset({"fetch_log"}),
    "套用": frozenset(),
    "展開": frozenset(),
    "匯出": frozenset(),
    "新增列": frozenset(),
    "清除": frozenset(),
    "導覽": frozenset(),
    "存檔": frozenset({"user_setting"}),
}
SAVE_WRITES = set(_BUTTON_WRITES["存檔"])

# `44` 1.2 呈現層禁令：禁方向詞。
FORBIDDEN_DIRECTION_WORDS = (
    "買進",
    "賣出",
    "加碼",
    "減碼",
    "調升",
    "調降",
    "汰弱留強",
    "逢低",
    "停利",
    "停損",
)
# `44` 1.2：禁箭頭。
FORBIDDEN_ARROWS = ("↑", "↓", "▲", "▼")
# `44` 1.1 節判準：按鈕標籤四個禁詞。
FORBIDDEN_BUTTON_WORDS = ("一鍵", "最佳", "推薦", "最適")
# `44` 1.2：禁排名為推薦 —— 清單的欄名集合裡不得有這四類欄。
FORBIDDEN_COLUMN_WORDS = ("分數", "星等", "排名", "推薦")

# ⛔ **2026-09-24 第二輪稽核更正：這一行原本的註解是假的。**
# 舊註解寫「判『同一張卡有沒有把兩種幣別合成一個數』用的幣別字面值」——
# 而真正在做那件判定的 `cross_currency_nodes()` **從頭到尾沒有讀過這個常數一次**
# （它比的是每個值節點自己掛的 `_ccy`）。**一個宣稱了用途、卻沒有任何人用的常數，
# 比單純的死碼更危險：它會讓讀者以為那個守衛是靠白名單在把關。**
# 現況：**零呼叫者**，已登記於 `KNOWN_NO_CALLER`。保留不刪（`44` §6「不刪，只標」）。
KNOWN_CURRENCIES = ("USD", "EUR", "TWD", "JPY", "GBP")

_TONE_BY_STATE = {
    STATE_OK: "中性",
    STATE_MISSING: "灰",
    STATE_BIZ: "黃",
    STATE_ERROR: "紅",
}

# ⚠️ **`44` 對卡片那四個狀態只排過一次序，而那一次把中間兩個並列同級。**
# `44` :310（`MKT-0` 規則欄，全檔唯一明文排過卡片四狀態的地方）逐字：
#   「三塊狀態取最差者：三塊皆 `ok` → 燈為中性灰，文案「三張卡的資料齊」；任一塊為 `資料未備` 或
#   `業務例外` → 燈為黃，文案列出是哪一張卡；任一塊為 `系統錯誤` → 燈為紅，文案列出失敗的那一段」
# 也就是 `ok` ＜ {`資料未備`, `業務例外`} ＜ `系統錯誤` —— 這是一個**偏序**，不是全序。
# ⛔ **本檔不替 `44` 排那兩個的先後。** 同級時 `worst_state()` 回 `STATE_UNRANKED`。
_BAND = {STATE_OK: 0, STATE_MISSING: 1, STATE_BIZ: 1, STATE_ERROR: 2}
_UNRANKED_BAND = 1

# `worst_state()` 在「`資料未備` 與 `業務例外` 同時是最差」時回這個哨符。
# ⛔ 它**不是第五個狀態**（`44` 5.1 的四狀態是封閉列舉），也**不得寫進任何畫面文字**；
#    它只表示一件事：**`44` 沒有排這兩個的先後，本檔不替它排。**
# ⚠️ 考慮過、而且刻意**不用** `44` 5.2 的 `未定義` 徽章字面值 —— 那一個在 `44` 是
#    「某塊的來源欄寫了一個本檔第四節未定義的欄位 → 該欄位單獨列出並掛「未定義」徽章」，
#    與本處無關，借來用等於替 `44` 造新語意。
STATE_UNRANKED = None

# ⚠️ **登記（本頁的實況，據實寫明）**：`44` 本頁八塊的空狀態欄**沒有一句**寫 `⬜ 不適用`，
#    所以 `STATE_BIZ` 在本頁**沒有任何一個情境會產生**。
#    它照舊留在上面那份封閉列舉裡（那是 `44` 的四狀態），`worst_state()` 也照舊正確處理它 ——
#    **本檔不因為「這一頁用不到」就把 `44` 的列舉砍短**。
#    ⛔ 連帶：`STATE_UNRANKED` 這條路在本頁**沒有情境走得到**，只有直接呼叫 `worst_state()` 的
#    單元測試走得到。**寫在這裡，免得下一個人以為它被情境覆蓋過。**

# `44` 5.5 空狀態四種。客戶 2026-09-23 裁示的嚴重度序是**全序**，四種各自分得出先後。
EMPTY_SOURCE = "來源缺"
EMPTY_PARTIAL = "部分缺"
EMPTY_UNCOMPUTABLE = "算不出來"
EMPTY_ERROR = "系統錯誤"
# `44` 5.5 逐字：「**嚴重度由重到輕排定為 `系統錯誤` ＞ `來源缺` ＞ `算不出來` ＞ `部分缺`**」。
# ⚠️ 與上面那個 `_BAND` **不是同一把尺，也不得互換** —— 這一把排的是**空狀態的四種**，
#    那一把排的是**卡片的四狀態**。兩組各有一個成員叫 `系統錯誤`，其餘三個成員完全不同。
_EMPTY_SEVERITY = {EMPTY_ERROR: 3, EMPTY_SOURCE: 2, EMPTY_UNCOMPUTABLE: 1, EMPTY_PARTIAL: 0}


BLOCK_TITLES = {
    "EXP-0": "篩選結果結論列",
    "EXP-1": "條件輸入卡",
    "EXP-2": "候選清單卡",
    "EXP-3": "並排對照卡",
    "EXP-4": "欄位與排序設定",
    "EXP-5": "加入觀察清單",
    "EXP-6": "單檔基礎資料",
    "EXP-7": "篩選軌跡",
}
BLOCK_LAYERS = {
    "EXP-0": 1,
    "EXP-1": 2,
    "EXP-2": 2,
    "EXP-3": 2,
    "EXP-4": 3,
    "EXP-5": 3,
    "EXP-6": 4,
    "EXP-7": 4,
}

# 「回答什麼」逐字引 `44` 3.3 各塊那一格。
ANSWERS = {
    "EXP-0": "我這組條件濾出來還剩幾檔",
    "EXP-1": "我現在是用哪幾條規則在濾",
    "EXP-2": "符合我條件的是哪幾檔，它們的客觀欄位各是多少",
    "EXP-3": "這幾檔擺在一起，同一個指標各是多少",
    "EXP-4": "清單上現在顯示哪些欄、依哪一欄排",
    "EXP-5": "我把哪幾檔留下來下次再看",
    "EXP-6": "這一檔的基本資料原本是怎麼登記的",
    "EXP-7": "是哪一條條件把檔數砍下來的",
}

PAGE_TITLE = "標的探索"
# `44` 3.3 頁首「回答什麼」逐字。
PAGE_ANSWERS = "符合我輸入條件的基金有哪些，它們彼此差在哪"
# `44` 3.3 頁首「不負責什麼」逐字，拆成三句。
PAGE_NOT_RESPONSIBLE = (
    "不排名、不標最佳（G1†）",
    "不談我目前的持倉狀況（那是持倉體檢）",
    "不談配置比重（那是資產配置）",
)
# `44` 1.3 那張表：本頁的紅線落點三枚。
PAGE_REDLINES = ("G1†", "G2†", "G3†")

# `44` 4.5：時間一律以世界協調時間存放。
STORAGE_TIMEZONE = "UTC"

# `44` `EXP-3` 規則欄逐字訂死的上限 —— **不隨資料變，所以不帶（示意）**。
COMPARE_LIMIT = 3
# `44` `EXP-2` 規則欄的欄名裡那個 12 —— 同上，不帶（示意）。
DIVIDEND_WINDOW_MONTHS = 12

HINT = "（示意）"

# 兩組勾選框的組名（`44` `EXP-2` 規則欄逐字：一組標「對照」，一組標「觀察清單」）。
GROUP_COMPARE = "對照"
GROUP_WATCH = "觀察清單"

# `page.py` 用的 session_state 鍵（鍵名住在這裡，畫面層不自己編）。
_CHECKED_KEY_BASE = {GROUP_COMPARE: "exp_checked_compare", GROUP_WATCH: "exp_checked_watch"}


def checked_key(group: str, scenario: str) -> str:
    """勾選狀態的 session 鍵。**鍵名帶情境名**。

    ⚠️ 不帶情境名的話，切到另一個情境時上一個情境的勾選會留著 ——
    於是 `?scenario=nocond`（首次開啟，兩組都該是空的）會帶著前一頁勾好的三檔進來，
    `44` `EXP-1` 那一行判準（「首次開啟本頁……卡片上沒有任何已勾選的選項」）就驗不到東西。
    """
    return f"{_CHECKED_KEY_BASE[group]}__{scenario}"


def toggle_checked(current, fund_code: str, *, checked: bool):
    """把某一檔的勾選狀態換成 `checked`，回一個排序過的 tuple。

    住在 logic 而不是 page 的理由：這是「按下之後變成什麼」的規則，**那是判定**。
    ⚠️ 本函式**不管上限** —— 上限由 `_build_exp2` 決定哪一個框 `_enabled` 為假，
       停用的框根本按不下去（`44` 5.3：按鈕停用時不隱藏，但按不動）。
    """
    out = set(current)
    if checked:
        out.add(fund_code)
    else:
        out.discard(fund_code)
    return tuple(sorted(out))


# ───────────────────────── 欄位 ─────────────────────────

# `44` `EXP-2` 規則欄逐字列出的那五欄（**順序照 `44` 寫下來的順序**）。
# ⚠️ **登記（`E-07`）**：`44` `EXP-4` 逐字要求「欄位清單依欄位名字面值排列」，
#    而這五欄裡**有三欄不是 `fund_profile` 的欄位名** —— 最近淨值日與最近淨值來自 `nav`，
#    「近 12 個月配息佔淨值比」是算出來的、**連欄位名都沒有**。
#    ⛔ 本檔**不自行發明一套排法**，照 `44` 自己寫下那五欄的順序排，**並把這個缺口寫到畫面上**。
# ⚠️ **這份清單比已拍板的那張圖多一項，關鍵事實就地寫明（2026-09-24 補）**：
#    已拍板草稿 `ui_prototype_exp.html` §H 的 `T-09` 逐字是「可選欄位**四項**」，
#    並寫明「本組當時取 `EXP-2` 那五欄**扣掉「基金名」**」——**畫面上是四個勾選項**。
#    本頁是**五項**（其餘四項的相對順序與草稿相同，沒有重排），依據是 `44` `EXP-4` 規則欄
#    2026-09-23 那一句（母體＝`EXP-2` 規則欄那五欄，含基金名）。
#    ⛔ **而那一句 `44` 自己標的是「決策者：AI 總管，本輪派工指定」，不是客戶裁的**（實讀 44）。
#    ⇒ 相對於客戶已經拍板的那張圖，**「基金名進入勾選集」是一次視覺元件增加**，
#    而它的授權來自總管的一筆派工指定、不是客戶的裁示。**本頁照 `44` 做（44 是 SSOT），
#    但這個事實必須讓客戶看得到，不能只寫「草稿沒跟上」。**
COLUMN_ORDER = ("fund_name", "ccy", "nav_date", "nav_orig_ccy", "div_ratio_pct")
COLUMN_LABELS = {
    "fund_name": "基金名",
    "ccy": "ccy",
    "nav_date": "最近淨值日",
    # `44` `EXP-2` 規則欄 2026-09-22 改寫後的逐字欄名。
    "nav_orig_ccy": "最近淨值（nav_orig_ccy，原幣）",
    "div_ratio_pct": "近 12 個月配息佔淨值比",
}
# 全不勾時的**退路**：`44` `EXP-4` 空狀態欄逐字「欄位一個也沒勾 → `EXP-2` 只顯示基金名一欄」。
# ⛔ **2026-09-24 就地更正：這裡原本寫「勾它與不勾它，`EXP-2` 看起來一模一樣」—— 那是假的。**
#    **實測（四行就看得出來）**：`columns=()` → `['fund_name']`；`('fund_name',)` → `['fund_name']`；
#    **`('ccy',)` → `['ccy']`（基金名不見了）**；`('fund_name','ccy')` → `['fund_name','ccy']`。
#    程式是 `... or [ALWAYS_SHOWN_COLUMN]` —— **那是全不勾時的退路，不是「永遠顯示」。那個框會動。**
#    **舊表述只在一個角落成立**（其他欄一個都沒勾時），而我把它寫成了全稱句，
#    還一路寫進註解、測試 docstring 與測試名三個地方，測試也只覆蓋了那個角落。
# ⚠️ **成立的版本（本輪測試釘的就是這個）**：
#    **其他欄一個都沒勾時**，勾基金名與不勾基金名的結果相同（都只顯示基金名）。
# ⚠️ **真正的登記換成這一筆**：**勾了別的欄而沒勾基金名時，清單上就沒有基金名了** ——
#    `44` 只保障「全不勾」那一種，**沒有寫這一種算不算可接受**。本頁照字面走，登記待裁。
ALWAYS_SHOWN_COLUMN = "fund_name"

# `44` `EXP-2` 規則欄逐字：「預設不排序，依 `fund_code` 字面值排列」。
DEFAULT_SORT_FIELD = "fund_code"

# `44` `EXP-1` 規則欄逐字：「可選欄位取自 `fund_profile` 的欄位名清單」。
FUND_PROFILE_FIELDS = (
    "fund_code",
    "fund_name",
    "ccy",
    "inception_on",
    "dividend_policy",
    "mgmt_fee_rate_pct",
    "fetched_at",
)

# `44` `EXP-6` 規則欄逐字列出要顯示的六個欄位。
EXP6_FIELDS = (
    ("fund_name", "基金全名"),
    ("fund_code", "fund_code"),
    ("ccy", "ccy"),
    ("inception_on", "成立日（inception_on）"),
    ("dividend_policy", "配息方式（dividend_policy）"),
    ("mgmt_fee_rate_pct", "費率欄（mgmt_fee_rate_pct）"),
)

# ⚠️ **登記（`E-16`）**：`44` `EXP-3` 的來源欄只寫「其 `fund_profile`、`nav`、`dividend` 對應欄」，
#    **沒有列出是哪幾個指標**。本檔沿用已拍板的草稿 `ui_prototype_exp.html` §H 的 T-07 那四列
#    （該處自陳是草稿那一組擬的：借 `EXP-2` 三欄 ＋ 補一列經理費率）。
#    ⛔ **這是沿用，不是本組新發明；客戶可以逐項推翻，推翻不必改 `44`。**
# ⚠️ 同處另有一個 `44` 沒有處理的點，一併登記：規則欄逐字「格內只放數字與單位」，
#    而「最近淨值日」是**日期**，嚴格讀起來不該進格。本檔照放並在卡上就地寫出這件事。
COMPARE_ROWS = (
    ("nav_date", "最近淨值日"),
    ("nav_orig_ccy", "最近淨值"),
    ("div_ratio_pct", "近 12 個月配息佔淨值比"),
    ("mgmt_fee_rate_pct", "經理費率"),
)


# ───────────────────────── 小工具 ─────────────────────────


def hinted(text: str) -> str:
    """每一個**會隨資料變**的數後面帶的三個字。"""
    return text + HINT


def format_count(value: int) -> str:
    return f"{value:,}"


def format_nav(value: float, ccy: str) -> str:
    """原幣單位淨值。逐檔寫出該檔 `ccy` 的字面值（客戶 2026-09-22 設計引導第三條）。"""
    return f"{value:,.4f} {ccy}"


def format_pct(value: float) -> str:
    return f"{value:.2f}%"


def format_fee(value: float) -> str:
    """`44` 4.6：`mgmt_fee_rate_pct` 的單位是「百分點／年」。"""
    return f"{value:.2f}%"


def tone_for_state(state: str) -> str:
    """四狀態 → 顏色語意。`44` 5.1 卡片那張表。回傳語意字串，不回色碼。"""
    return _TONE_BY_STATE[state]


def _band(state) -> int:
    """狀態 → `44` :310 那三級。`STATE_UNRANKED` 走上面那條註解說明的路。"""
    return _UNRANKED_BAND if state is STATE_UNRANKED else _BAND[state]


def worst_state(states):
    """最差的那一個狀態；**兩者同級時不替 `44` 排先後**，回 `STATE_UNRANKED`。

    `44` :310 只排到 `ok` ＜ {`資料未備`, `業務例外`} ＜ `系統錯誤`。
    最差那一級只有一個成員時照回那個成員；最差那一級同時有 `資料未備` 與 `業務例外` 時
    **沒有答案** —— 回 `STATE_UNRANKED`，不挑一個充數。

    ⚠️ **回傳值與輸入順序無關**（同級時不看誰先出現，直接回哨符）。
    ⚠️ 空集回 `STATE_OK`：本頁沒有主值的那幾塊（`EXP-1`／`EXP-4`／`EXP-5`）走這一條。
       **這是本檔的選擇，`44` 沒有訂**「一塊沒有任何主值時它是什麼狀態」——
       回 `資料未備` 會讓一張**明明畫得出來**的輸入卡被標成缺資料，那是一句假話（§1）。
    ⚠️ **輸入可以含 `STATE_UNRANKED`**（見 `_band()`）—— 不處理會 `KeyError: None`。
    """
    if not states:
        return STATE_OK
    top = max(_band(s) for s in states)
    tied = {s for s in states if _band(s) == top}
    if len(tied) == 1:
        return next(iter(tied))
    return STATE_UNRANKED


def block_tone(states) -> str:
    """一塊的邊框顏色。**只做呈現，不做嚴重度判定。**

    客戶的原話是「顏色是 UI 顯示，不是嚴重度；兩者正交」（`44` 5.5 那一段轉述）。
    本函式站在「顯示」那一邊，所以它可以排顏色；`worst_state()` 站在「嚴重度」那一邊，
    所以它**不**排 `資料未備` 與 `業務例外`。
    ⚠️ 「站在哪一邊」是**本組的接法**，不是客戶的字。
    """
    tones = {tone_for_state(s) for s in states if s is not STATE_UNRANKED}
    for tone in ("紅", "黃", "灰"):
        if tone in tones:
            return tone
    return "中性"


def tone_for_block(state, states) -> str:
    """一塊要畫的顏色。

    狀態排得出來 → 照 `44` 5.1 那張表把那個狀態翻成顏色。
    排不出來（`資料未備` 與 `業務例外` 同級）→ 才退到 `block_tone()` 看主值的顏色。
    """
    return block_tone(states) if state is STATE_UNRANKED else tone_for_state(state)


def worst_empty_state(kinds):
    """空狀態四種同時成立時取最嚴的一種。**這一把是全序，四種都分得出先後。**

    `44` 5.5 客戶 2026-09-23 裁示逐字：「**顏色不參與這個排序**」。
    ⛔ 空集回 `None` —— 沒有空狀態時不硬挑一個。
    """
    if not kinds:
        return None
    return max(kinds, key=lambda kind: _EMPTY_SEVERITY[kind])


# ───────────────────────── 斷點 ─────────────────────────


def columns_for_width(width_px: int) -> int:
    """`44` 2.1 客戶最終版：≤768 單欄／769-1279 兩欄／≥1280 三欄。"""
    if width_px <= 768:
        return 1
    if width_px <= 1279:
        return 2
    return 3


def layer_columns(layer: int, width_px: int) -> int:
    """各層在該寬度下同一列並排幾塊。`44` 2.1 那張四段表。"""
    if layer in (1, 4):
        return 1  # 單欄滿寬，逐塊上下堆疊
    if layer == 2:
        return columns_for_width(width_px)
    # 層 3：`44` 逐字「五頁的層 3 各只有兩塊，兩塊並排同一列，第三欄空著」。
    return min(2, columns_for_width(width_px))


# ⛔ **登記（`E-15`，2026-09-24 第二輪稽核；本輪只登記、不動行為）**：
#    **下面這支算出來的 `_stacked` 在任何情境下都畫不出來。**
#    `page.py` 從不傳 `viewport_width`（恆用預設 1280），而 `block["_stacked"]`
#    **沒有任何渲染端讀它**。畫面上真正會堆疊，靠的是 `page.py` 的 CSS media query。
#    ⚠️ **所以它不是錯的，是「模型算了一個沒有人看的值」** ——
#    危險在於：讀模型的人會以為堆疊是由這支決定的，改它卻什麼都不會變。
#    ✅ **它仍然有一個真實用途**：`page.py` 用它**反推**那個 CSS 斷點該寫多少
#    （見 `page.py` 的 `_MAX_PROBE_WIDTH` 那一段），所以拿掉它 CSS 會失去唯一真相源。
def compare_stacks(width_px: int) -> bool:
    """`EXP-3` 的對照矩陣在這個寬度要不要改成逐檔上下堆疊。

    ⚠️ **登記（`E-15`）**：`44` `EXP-3` 逐字「同時最多對照 3 檔。一欄一檔」，
    而 `44` 2.1 硬規則逐字「任何一段都不出現橫向捲動 —— 一塊放不進當前寬度時，
    它自己換行或改成單欄，不把整頁推寬」。**`44` 沒有寫卡內表格怎麼塌。**
    本檔沿用已拍板的草稿 `ui_prototype_exp.html` §H 的 T-08：`≤768` 改成逐檔上下堆疊。
    ⛔ **這是沿用草稿挑的那一邊，不是 `44` 的字。**
    """
    return columns_for_width(width_px) == 1


# ───────────────────────── 文案模板（逐字引 `44` 5.5） ─────────────────────────


def empty_source_text(source_keys) -> str:
    return "⬜ 資料未備：" + " 與 ".join(source_keys) + " 尚無資料"


def not_applicable_text(reason: str) -> str:
    return "⬜ 不適用：" + reason


def fetch_failed_text(message: str) -> str:
    """訊息原文照印 —— 不改寫成安撫語句，也不截斷。"""
    return "⚠ 取數失敗：" + message


ND_TEXT = "⬜ 資料未備"
ERR_TEXT = "⚠ 取數失敗"

# 逐字引 `44` 3.3 各塊空狀態欄／規則欄裡那幾句要印在畫面上的話。
TEXT_NO_CONDITION = "尚未設定條件"
TEXT_NO_MATCH = "目前條件下沒有符合的基金"
TEXT_BLANK_VALUE = "⬜ 資料未備：數值未填"
TEXT_NOT_EFFECTIVE = "未生效"
TEXT_PICK_THREE = "勾選最多 3 檔以並排對照"
TEXT_NO_PICK = "尚未勾選任何基金"
TEXT_ONLY_FUND_NAME = "目前只顯示基金名"
TEXT_ALREADY_WATCHED = "已在觀察清單"
TEXT_NO_SUCH_FUND = "查無此 fund_code"
TEXT_ADD_CONDITION = "新增條件"
TEXT_ADD_WATCH = "加入觀察清單"
TEXT_SAVE = "存檔"
TEXT_CLEAR_ROW = "清除這一列"
TEXT_SAVE_FAILED = "存檔寫入失敗"
TEXT_NO_SORT = "不排序"
# `EXP-0` 空狀態欄逐字要「並列出目前生效的條件列」——「目前生效的條件列」這幾個字是**標題**，
# `44` 沒有給標題的字面，本行是本組擬的。放在這裡而不是畫面層，是為了讓
# `test_page沒有把任何一句44文案寫成字面值` 那條守衛的母體乾淨。
TEXT_EFFECTIVE_CONDITIONS = "目前生效的條件列"
# 頁首那一枚「存檔失敗開關」的標籤。**不是 `44` 的文案，是本頁的審稿工具列**。
# ⚠️ 刻意不寫成「存檔寫入失敗」——那是 `44` 三塊空狀態欄的字面，同字會讓
#    「畫面上有幾個失敗框」數不準（本輪實測數出過 4 而不是 3）。
TEXT_SAVEFAIL_BANNER = "＋ 存檔失敗開關（開）"


def conclusion_text(count: int) -> str:
    """`44` `EXP-0` 規則欄逐字：「目前條件下有 N 檔」。**N 會隨資料變，所以帶（示意）。**"""
    return f"目前條件下有 {hinted(format_count(count))} 檔"


# ───────────────────────── 條件比較 ─────────────────────────


class UnspecifiedComparison(Exception):
    """條件比較撞到 `44` 沒有訂的情形。**炸掉，不靜默選一邊**（`CLAUDE.md` §1）。"""


def rule_is_effective(rule: dict) -> bool:
    """`44` `EXP-1` 空狀態欄逐字：「數值欄留空 → 該列不生效」。"""
    return str(rule.get("value", "")).strip() != ""


def rule_text(rule: dict) -> str:
    """`44` `EXP-7` 規則欄那三欄的第一欄：「條件文字」。**字面由本檔組，`44` 沒有給格式。**"""
    value = rule.get("value", "")
    shown = value if str(value).strip() != "" else ND_TEXT
    return f"{rule['field']} {rule['op']} {shown}"


def _compare(left, op: str, right: str) -> bool:
    """一格比較。

    ⛔ **`44` 一個比較方向也沒有列** —— 規則欄只寫「每列為『欄位＋比較方向＋數值』」。
       六個字面值沿用已拍板的草稿 §H 的 T-03（見 `fixtures.OPERATORS`）。
    ⛔ **`44` 也沒有寫「缺值算通過還是不通過」**（`E-09`）。**本檔不替它選**，
       撞到就 `raise` —— 一個靜默的選擇會讓 `EXP-7` 的檔數與 `EXP-0` 的 N 悄悄對不起來，
       而 `44` `EXP-7` 判準逐字要求那兩個數相等。**炸掉比較誠實。**
    """
    if left is None:
        raise UnspecifiedComparison(
            f"欄位值為空而條件要比較它（`44` 沒有訂缺值算通過還是不通過；"
            f"見 `44` `EXP-2` 空狀態欄與 `E-09` 登記）：op={op!r} right={right!r}"
        )
    if op in ("等於", "不等於"):
        same = str(left) == str(right)
        return same if op == "等於" else not same
    if op in ("大於", "小於"):
        try:
            a, b = float(left), float(right)
        except (TypeError, ValueError):
            raise UnspecifiedComparison(
                f"「{op}」用在一個轉不成數的值上（`44` 沒有訂型別不合時怎麼辦）："
                f"left={left!r} right={right!r}"
            )
        return a > b if op == "大於" else a < b
    if op in ("早於或等於", "晚於"):
        a, b = str(left), str(right)
        return a <= b if op == "早於或等於" else a > b
    raise UnspecifiedComparison(f"沒有這個比較方向：{op!r}")


def apply_rules(rows, rules):
    """依序套用條件，回 `[(rule, before_count, after_count, rows_after), ...]`。

    `44` `EXP-7` 規則欄逐字：「條件依使用者新增的順序套用並逐列記錄」、
    「最後一列的套用後檔數與 `EXP-0` 的 N 相等」。
    """
    steps = []
    current = list(rows)
    for rule in rules:
        before = len(current)
        if not rule_is_effective(rule):
            # `44` `EXP-7` 空狀態欄逐字：「該列兩個檔數相等，並在列尾寫 `未生效`」。
            steps.append((rule, before, before, current))
            continue
        current = [r for r in current if _compare(r.get(rule["field"]), rule["op"], rule["value"])]
        steps.append((rule, before, len(current), current))
    return steps


# ───────────────────────── 讀資料 ─────────────────────────


def _setting(dataset, key):
    for row in dataset.get("user_setting", ()):
        if row["setting_key"] == key:
            return row
    return None


def setting_value(dataset, key):
    row = _setting(dataset, key)
    return None if row is None else row.get("setting_value")


def setting_updated_at(dataset, key):
    row = _setting(dataset, key)
    return None if row is None else row.get("updated_at")


def saved_rules(dataset):
    return tuple(setting_value(dataset, "exp_filter_rules") or ())


def saved_columns(dataset):
    """`exp_visible_columns` 的已存值。

    ⚠️ **登記**：`44` 4.5 把「未設定」與「設成空」寫成同一件事（`setting_value` 為空），
    而 `EXP-4` 空狀態欄只寫了「欄位一個也沒勾」那一種。**兩者在本頁畫起來一樣。**
    本檔照 `44` 的字走（未設定 ＝ 一個也沒勾），**不自行替未設定另立一種畫面**。
    """
    return tuple(setting_value(dataset, "exp_visible_columns") or ())


def saved_sort_column(dataset):
    return setting_value(dataset, "exp_sort_column")


def saved_watchlist(dataset):
    return tuple(setting_value(dataset, "exp_watchlist") or ())


def latest_nav(dataset, fund_code):
    """`44` `EXP-2` 來源欄逐字：「`nav.nav_orig_ccy` 與 `nav.nav_date` 取最近一筆」。"""
    rows = [r for r in dataset.get("nav", ()) if r["fund_code"] == fund_code]
    return max(rows, key=lambda r: r["nav_date"]) if rows else None


def profile_of(dataset, fund_code):
    for row in dataset.get("fund_profile", ()):
        if row["fund_code"] == fund_code:
            return row
    return None


# `44` 3.3 各塊「來源」欄逐字點名、而且是**取數取回來**的那幾張表。
# ⚠️ **唯一的篩選**：只收「取數取回來的表」。`user_setting` 是**使用者自己輸入的**，
#    不經取數，所以取數失敗與它無關。**這是本組的判斷，不是 `44` 的字**（體例同姊妹頁 `hld`）。
# ⚠️ **連帶登記**：`EXP-1` 的來源欄只有 `user_setting`，所以依上面那條篩選，
#    **`EXP-1` 沒有任何一條取數失敗的路徑**。而 `44` `EXP-0` 規則欄逐字寫著
#    「本塊讀到的那兩塊任一為 `系統錯誤` → 燈為紅」—— 那個「任一」在本頁實際上只剩 `EXP-2` 一塊。
#    `44` 5.5 把 `系統錯誤` 的觸發條件寫成「取數或計算本身失敗」，**「計算本身失敗」那一半
#    在 `EXP-1` 上要長什麼樣，`44` 一個字都沒有寫。** 登記，不自行補。
BLOCK_SOURCE_TABLES = {
    "EXP-2": ("fund_profile", "nav", "dividend"),
    "EXP-3": ("fund_profile", "nav", "dividend"),
    "EXP-6": ("fund_profile", "nav", "dividend"),
    # ⚠️ **`EXP-7` 這一列是推導出來的，不是它來源欄的字面。** `44` `EXP-7` 的來源欄寫的是
    #    「`EXP-1` 的條件列，以及每一條條件套用前後的候選檔數」—— **那些檔數是在
    #    `fund_profile` 上數出來的**，那張表取數失敗時，那三欄的數就不是真的。
    #    ⛔ **這是本組判讀，`44` 沒有逐字寫；**不推導的話，`EXP-7` 會在來源掛掉時
    #    印出一串「0 → 0」並且什麼都不說，那正是 §1 在擋的那一種。
    "EXP-7": ("fund_profile",),
}


def source_error(dataset, code):
    """這一塊的來源表有沒有取數失敗；有就回訊息原文，沒有回 `None`。"""
    errors = dataset.get("errors") or {}
    for table in BLOCK_SOURCE_TABLES.get(code, ()):
        message = errors.get(table)
        if message:
            return message
    return None


def source_error_lines(dataset, code):
    """這一塊的來源表失敗訊息，**一張表一行，每一行都帶自己的表名**。

    `44` 4.4 逐字：「`message` 存來源回傳的原始字串，不換成安撫語句，也不截斷。」
    ⛔ **2026-09-24 就地更正：這裡原本有一句 `if line not in lines` 的去重，那是死碼。**
    每一行都以 `表名：` 開頭，而同一塊的來源表名**必不相同**，所以那個條件**結構上永遠為假** ——
    **本組實測（量測日 2026-09-24）**：`twofail` 那一組回的兩行是 `nav：…` 與 `dividend：…`，
    **前綴必不相同**，所以那個條件一次也不會成立。
    ⚠️ 「拿掉它 158 條全綠存活」那個數是**稽核**跑出來的，本組沒有重跑那一版。
    ⚠️ 連帶：那一句旁邊的測試叫「同一句失敗訊息在同一塊只印一次」，**而它自己斷言的是兩行**
    —— **測試名與它的斷言方向相反**。兩者一起修。
    **真的不變量是「每一行都認得出自己是哪一張表」**（那也是兩行不會變成一模一樣的原因），
    現在由 `test_兩張表同時失敗時兩行各自帶自己的表名` 守著，拿掉表名前綴會轉紅。
    """
    errors = dataset.get("errors") or {}
    lines = []
    for table in BLOCK_SOURCE_TABLES.get(code, ()):
        message = errors.get(table)
        if message:
            lines.append(f"{table}：{fetch_failed_text(message)}")
    return lines


def upstream_failure_notes(dataset, code):
    """上游取數失敗時，這一塊要顯示的那幾句（**一張失敗的表一句，句首帶表名**）。

    沒有失敗回空 list。
    ⛔ **2026-09-24 就地更正：上一版回單數的一句，而且與 `source_error_lines()` 並存** ——
    於是同一塊把同一句訊息印兩次（一次在空狀態、一次在紅框）。
    **本組實測（量測日 2026-09-24，修復前）**：`profilefail` 全頁印 11 次、`twofail` 17 次、
    `navfail` 10 次。**現在一塊只有一個地方印。**
    ⚠️ `EXP-0` 是唯一的例外，而且是 `44` 要的：它的規則欄逐字「**文案列出失敗的那一段**」——
    那一塊的職責就是**轉述**哪一塊、哪一張表失敗了，所以它印的那一份不算重複。


    ⛔ **為什麼不能讓各塊照原本的空狀態文案走**：`fund_profile` 取數失敗時，
    `EXP-2` 會印「目前條件下沒有符合的基金」、`EXP-3` 會印「勾選最多 3 檔以並排對照」、
    `EXP-6` 會印「查無此 `fund_code`」—— **三句都是假的**，而 `EXP-6` 那一句最糟：
    它對一檔基金**斷言了一件事實**（這個代碼不存在），而真相是我們根本沒查到。
    §1 Fail Loud：一句把取數失敗報成別的東西的文案，比沒有文案更誤導。

    **法源**：`44` 5.5 那張表的 `系統錯誤` 一列，觸發條件逐字「取數或計算本身失敗」，
    畫面文案模板逐字 `⚠ 取數失敗：<訊息原文>`。
    ⚠️ `44` 本頁八塊只有 `EXP-0` 寫出 `系統錯誤` 這個字面（其餘七塊沒有，那是 `E-14`）；
    但 `44` `EXP-0` 塊下方已經就地撤回過「塊沒寫種類名 ⇒ 該狀態不會發生」這個推論，
    並逐字寫明「『塊寫畫面模板、不寫種類名』本來就是本檔對每一種空狀態的共通體例，
    不是本頁的缺陷」。**所以套 5.5 的模板不是本組發明的，是照它的共通體例走。**
    ⛔ **模板裡那一枚「重新取數」本頁不掛** —— 見 `E-22` 的登記
    （`nav` 與 `dividend` 在 `44` 5.3 的唯讀清單裡，那枚鈕按了不能寫它缺的表）。
    """
    return source_error_lines(dataset, code)


def save_error(dataset, keys):
    """這一枚「存檔」上一次寫入有沒有失敗；有就回訊息原文。"""
    errors = dataset.get("save_errors") or {}
    for key in keys:
        message = errors.get(key)
        if message:
            return message
    return None


# ───────────────────────── 元件工廠 ─────────────────────────


def status_badge(text: str) -> dict:
    """`44` 5.2 的 `狀態` 徽章。

    ⚠️ **本頁一枚也沒有掛，據實寫明理由，不是漏掛**：
    - `部分缺` 的觸發條件逐字是「來源只涵蓋區間的一部分」，而**本頁沒有任何一塊有「區間」**
      （它不畫時間序列）；
    - `資料未備`／`不適用`／`取數失敗` 三種在本頁是寫在**格子與說明區**上的文案
      （`⬜`／`⚠ 取數失敗：…`），`44` 各塊的空狀態欄寫的就是文案，沒有一格寫「掛徽章」；
    - `推估`／`修正過`／`未定義` 三種本頁沒有對應的資料欄位在畫面上。
    ⛔ 本函式因此是 **0 caller**。**刻意留著**：它是那份封閉列舉的守門員 ——
    哪天有人要在這一頁掛第一枚狀態徽章，得先過它，而過不了的字面值當場炸。
    （`44` §6 死碼處置：本檔的作法是「留著、就地寫明為什麼」，不是靜默留著。）
    """
    if text not in STATUS_BADGE_LITERALS:
        raise ValueError(f"狀態徽章字面值 {text!r} 不在 `44` 5.2 的七個之內")
    return {"_kind": "狀態", "_tone": "灰" if text == "資料未備" else "黃", "text": text}


def source_badge(tier: str) -> dict:
    """`44` 5.2：來源徽章中性、不著色。"""
    return {"_kind": "來源", "_tone": "中性", "text": tier}


def placeholder_badge(kind: str, text: str) -> dict:
    """卡底那兩枚**佔位**徽章。

    ⚠️ **登記（`E-21`）**：`44` 5.1 的卡片參數是**逐主值**的
    （`value_text`／`value_state`／`reason_text`／`source_badge`／`freshness_badge`），
    而本頁層 2 三張卡**沒有一張是主值卡** —— `EXP-1` 是一組輸入列、`EXP-2` 是一張表、
    `EXP-3` 是一個矩陣。`44` 5.1 自己也就地登記過「本檔從頭到尾沒有定義『主值』」並標為待裁決。
    ⛔ 本檔沿用已拍板的草稿 §H 的 T-17：**每卡掛一組，而且刻意畫成佔位** ——
    **不編造 `source_tier` 的字面值，也不編造新鮮度的日數。**
    """
    return {"_kind": kind, "_tone": "中性", "_placeholder": True, "text": text}


def _redline_badge(mark: str) -> dict:
    """`44` 5.2：紅線徽章只出現在說明區，不出現在任何數值旁。"""
    return {"_kind": "紅線", "_tone": "中性", "_slot": "說明區", "text": mark}


def button_writes(kind: str) -> set:
    return set(_BUTTON_WRITES[kind])


def _button(label, kind, *, enabled=True, disabled_reason="") -> dict:
    if kind not in BUTTON_KINDS:
        raise ValueError(f"按鈕類別 {kind!r} 不在 `44` 5.3 的八類之內")
    for word in FORBIDDEN_BUTTON_WORDS:
        if word in label:
            raise ValueError(f"按鈕標籤 {label!r} 含禁詞 {word!r}（`44` 1.1）")
    return {
        "_action_kind": kind,
        "_writes": button_writes(kind),
        "_enabled": bool(enabled),
        "_visible": True,  # `44` 5.3：按鈕停用時不隱藏
        "label": label,
        "disabled_reason": disabled_reason,
    }


def _value(text, *, state=STATE_OK, has_number=False, ccy=None, label="") -> dict:
    return {
        "_value_node": True,
        "_state": state,
        "_tone": tone_for_state(state),
        "_has_number": bool(has_number),
        "_ccy": ccy,
        "label": label,
        "text": text,
    }


def _missing_value(label="") -> dict:
    """缺的格。`44` `EXP-2` 空狀態欄逐字：「缺的格顯示 `⬜`」。"""
    return _value("⬜", state=STATE_MISSING, label=label)


def _checkbox(group, fund_code, *, checked, enabled=True, disabled_reason="", note="") -> dict:
    """`EXP-2` 每一列的勾選框。

    ⚠️ **登記（`44` `EXP-2` 塊下方那一筆待裁決）**：勾選框算不算本塊的「欄」，`44` 沒有寫，
    而且就地標為**待客戶或總管裁決**。本檔照 `44` 規則欄那份欄位清單走 ——
    **那份清單裡沒有它們**，所以本檔**不把勾選框算進欄**；
    `EXP-4` 的可選欄位清單也因此不多出兩項。⛔ **這是照 `44` 沒寫進清單的字面走，不是裁決。**
    """
    return {
        "_checkbox": True,
        "_group": group,
        "_fund_code": fund_code,
        "_checked": bool(checked),
        "_enabled": bool(enabled),
        "_visible": True,
        "label": group,
        "disabled_reason": disabled_reason,
        "note": note,
    }


def _field(name, label, placeholder, value) -> dict:
    """一個輸入欄。`44` 1.1 節判準：**沒有一列帶有非空的預設值**。"""
    return {
        "_input": True,
        "name": name,
        "_value": value,
        "label": label,
        "placeholder": placeholder,
    }


# ───────────────────────── 塊 ─────────────────────────


def _block(code, *, state, states=(), **extra) -> dict:
    block = {
        "code": code,
        "title": BLOCK_TITLES[code],
        "answers": ANSWERS[code],
        "_layer": BLOCK_LAYERS[code],
        # `44` 2 硬規則：層 1 與層 2 預設展開，層 3 與層 4 預設收合。
        "_default_open": BLOCK_LAYERS[code] <= 2,
        "_state": state,
        "_tone": tone_for_block(state, states),
        "notes": [],
        "detail_lines": [],
        # ⛔ **取數失敗的行有自己的鍵，不混進 `detail_lines`。**
        #    上一版把它們塞進 `detail_lines`，於是 `page.py` 只能用 `if ERR_TEXT in line` 去挑 ——
        #    (a) 那是**畫面層在做分類**，與它 docstring 的「一個判定也不做」不一致；
        #    (b) 挑出來畫一次紅框之後，`_lines(detail_lines)` 又把同一行原封再畫一次 ——
        #        **本組實測（量測日 2026-09-24，修復前）：`profilefail` 印 11 次、`twofail` 17 次、`navfail` 10 次。**
        #    ⚠️ 與 `error_lines` 分開：那一族是**存檔**寫入失敗（`44` `EXP-1`／`EXP-4`／`EXP-5` 空狀態欄），
        #        這一族是**取數**失敗（`44` 5.5）。兩族混在一個鍵裡，畫面上就數不清哪一種出了幾個。
        "fetch_fail_lines": [],
        # 存檔失敗那一族的**登記註記**（不是失敗訊息本身；一個鍵不裝兩種東西）。
        "save_fail_notes": [],
        "badges": [],
        "buttons": [],
    }
    block.update(extra)
    return block


def _build_exp1(dataset, *, draft_rules, save_failed_message):
    """`EXP-1` 條件輸入卡。"""
    rules = tuple(draft_rules)
    rows = []
    for index, rule in enumerate(rules):
        effective = rule_is_effective(rule)
        rows.append(
            {
                "_index": index,
                "_effective": effective,
                "_fields": [
                    # `44` `EXP-1` 規則欄逐字：「每列為『欄位＋比較方向＋數值』」。
                    # 三個標籤的字面是本檔直接拿那一句來當標籤用（草稿 §H 的 T-02 同此）。
                    _field(f"rule{index}_field", "欄位", "", rule["field"]),
                    _field(f"rule{index}_op", "比較方向", "", rule["op"]),
                    _field(f"rule{index}_value", "數值", "", rule.get("value", "")),
                ],
                # ⚠️ **登記（`E-18`）**：`44` 只寫「條件列由使用者新增」，**沒有寫怎麼刪、也沒有給字面**。
                #    整顆按鈕是沿用已拍板的草稿 §H 的 T-04（含「對到八類的 `清除`」那個歸類）。
                "_button": _button(TEXT_CLEAR_ROW, "清除"),
                "tail_text": "" if effective else TEXT_BLANK_VALUE,
                "text": rule_text(rule),
            }
        )

    detail_lines = [
        f"可選欄位取自 fund_profile 的欄位名清單：{'、'.join(FUND_PROFILE_FIELDS)}。",
        "本卡不提供任何預先勾選的條件組合，也不提供條件的一鍵套用（G1†）。",
    ]
    # ⚠️ **登記（`44` `EXP-1` 塊下方的「其二」，就地標為待客戶或總管裁決）**：
    #    條件的「當下值」與「已存值」哪一個餵 `EXP-2`，`44` 沒有寫。
    saved = saved_rules(dataset)
    if tuple(saved) != rules:
        detail_lines.append(
            "⚠ 欄位的當下內容與已存值不同。本頁把當下內容餵給 EXP-2（即時生效）—— "
            "44 就地登記這一題為待客戶或總管裁決，本頁只是把選了哪一邊寫在畫面上。"
        )

    notes = []
    if not rules:
        # `44` `EXP-1` 空狀態欄逐字：「一列也沒有 → 卡片顯示提示文字與一枚『新增條件』按鈕」。
        # ⚠️ **那句「提示文字」的字面 `44` 沒有給**（按鈕的標籤有給，提示文字沒有）——
        #    下面這一句是本組擬的，客戶可以逐字推翻，推翻不必改 `44`。
        notes.append("尚未新增任何條件列。")

    buttons = [
        _button(TEXT_ADD_CONDITION, "新增列"),
        # `44` `EXP-1` 規則欄逐字：「本塊掛一枚『存檔』按鈕（`action_kind` 為 `存檔`）」。
        # ⚠️ 停用條件：`44` 塊下方的「其一」已就地判讀為走 `SET-4` 那一種（**不宣告任何停用條件**），
        #    並註明「這一步是本組判讀，客戶未逐字點名，可推翻」。本檔照那個判讀做。
        _button(TEXT_SAVE, "存檔"),
    ]

    error_lines = []
    if save_failed_message:
        # `44` `EXP-1` 空狀態欄逐字：「存檔寫入失敗 → 卡上顯示失敗訊息原文，
        # 條件列的當下內容留在畫面上不清掉，`EXP-2` 的列數不變」。
        error_lines.append(TEXT_SAVE_FAILED + "：" + save_failed_message)

    # `EXP-1` 沒有主值 —— 它是一組輸入列（`E-21`）。
    state = STATE_OK
    return _block(
        "EXP-1",
        state=state,
        states=(),
        summary_text=(
            f"{hinted(format_count(len(rules)))} 條條件" if rules else TEXT_NO_CONDITION
        ),
        _rows=rows,
        notes=notes,
        detail_lines=detail_lines,
        error_lines=error_lines,
        buttons=buttons,
        badges=[
            placeholder_badge("來源", "〔來源層級〕"),
            placeholder_badge("新鮮度", "〔新鮮度〕"),
        ],
        redline_note="G3†：條件列由使用者自行輸入，系統不代填；G1†：無一鍵套用。",
        _save_writes=sorted(SAVE_WRITES),
        _save_keys=("exp_filter_rules",),
    )


def _build_exp2(
    dataset,
    *,
    matched,
    has_rules,
    visible_columns,
    sort_column,
    compare_checked,
    watch_checked,
    watchlist,
):
    """`EXP-2` 候選清單卡。"""
    fail_message = source_error(dataset, "EXP-2")
    ratios = dataset.get("div_ratio_pct") or {}

    # `44` `EXP-4` 空狀態欄逐字：「欄位一個也沒勾 → `EXP-2` 只顯示基金名一欄」。
    shown = [c for c in COLUMN_ORDER if c in visible_columns] or [ALWAYS_SHOWN_COLUMN]

    rows = []
    cell_states = []
    for profile in matched:
        code = profile["fund_code"]
        nav = latest_nav(dataset, code)
        cells = {}
        for column in shown:
            if column == "fund_name":
                cells[column] = _value(profile["fund_name"], label=COLUMN_LABELS[column])
            elif column == "ccy":
                cells[column] = _value(profile["ccy"], label=COLUMN_LABELS[column])
            elif column == "nav_date":
                cells[column] = (
                    _value(hinted(nav["nav_date"]), label=COLUMN_LABELS[column])
                    if nav
                    else _missing_value(COLUMN_LABELS[column])
                )
            elif column == "nav_orig_ccy":
                cells[column] = (
                    _value(
                        hinted(format_nav(nav["nav_orig_ccy"], nav["ccy"])),
                        has_number=True,
                        ccy=nav["ccy"],
                        label=COLUMN_LABELS[column],
                    )
                    if nav
                    else _missing_value(COLUMN_LABELS[column])
                )
            else:
                # ⚠️ **登記（`E-05`）**：`44` 只給了這個欄名，**沒有給算式**。
                #    值由 `fixtures.div_ratio_pct()` 直接給示意值（見該處），本檔不自行選一種算法。
                #    ⚠️ 缺淨值時這一格跟著缺 —— **那是本組的讀法**：欄名逐字是「佔淨值比」，
                #    分母就是淨值。`44` 沒有明寫這個連動。
                ratio = ratios.get(code)
                cells[column] = (
                    _value(
                        hinted(format_pct(ratio)),
                        has_number=True,
                        ccy=profile["ccy"],
                        label=COLUMN_LABELS[column],
                    )
                    if (nav and ratio is not None)
                    else _missing_value(COLUMN_LABELS[column])
                )
        cell_states.extend(cell["_state"] for cell in cells.values())
        rows.append(
            {
                "_fund_code": code,
                "_ccy": profile["ccy"],
                "_cells": cells,
                "_checkboxes": {},
            }
        )

    # `44` `EXP-2` 規則欄逐字：「預設不排序，依 `fund_code` 字面值排列；
    # 使用者自選排序欄位後依該欄排序，排序結果不加任何冠詞」。
    rows = _sorted_rows(rows, dataset, sort_column, ratios)

    # 兩組勾選框。`44` 規則欄逐字：「兩組並存、互不連動」。
    compare_count = sum(1 for r in rows if r["_fund_code"] in compare_checked)
    for row in rows:
        code = row["_fund_code"]
        is_compared = code in compare_checked
        # ⚠️ **登記（2026-09-24 就地更正歸屬：上一版把這一步寫成「本組做的」，那把授權寫小了）**：
        #    `44` `EXP-3` 空狀態欄逐字寫的是「該組的**第 4 個**勾選框停用」，而候選清單可以超過四列。
        #    本檔的作法是：**「對照」勾滿上限之後，該組每一個未勾的框都停用**。
        #    ✅ **這不是本組發明的** —— **已拍板草稿 `ui_prototype_exp.html` 的渲染碼就是同一條規則**
        #    （實讀：`var cOver = (!cOn && cmp.length >= 3);`，不是舊版的 `i === 3`），
        #    而該檔就地寫著「**這是照 `44` 修正，不是新設計**」。
        #    ⚠️ **據實寫明我讀到的授權字樣**：那一筆的就地回修註記寫的是「決策者：AI 總管」，
        #    而它所在的那一輪（第十六輪）整輪是「客戶拍板草稿後併入」。**本檔只寫讀到的，不替它歸給客戶。**
        #    ✅ **而且推廣是唯一與 `44` 自洽的讀法**：照單數字面只停第 4 列、留第 5 列可按，
        #    使用者按下去就會有 4 檔被勾 —— **那會違反同一格逐字的「同時最多對照 3 檔」**。
        at_limit = compare_count >= COMPARE_LIMIT and not is_compared
        row["_checkboxes"][GROUP_COMPARE] = _checkbox(
            GROUP_COMPARE,
            code,
            checked=is_compared,
            enabled=not at_limit,
            disabled_reason=f"同時最多對照 {COMPARE_LIMIT} 檔" if at_limit else "",
        )
        # `44` `EXP-5` 空狀態欄逐字：「觀察清單已含該檔 → 該檔「觀察清單」那一組的勾選框
        # 顯示『已在觀察清單』且不重複寫入」。
        row["_checkboxes"][GROUP_WATCH] = _checkbox(
            GROUP_WATCH,
            code,
            checked=code in watch_checked,
            note=TEXT_ALREADY_WATCHED if code in watchlist else "",
        )

    notes = []
    failure_notes = upstream_failure_notes(dataset, "EXP-2")
    if failure_notes:
        # ⛔ 取數失敗時**不印**「尚未設定條件」或「目前條件下沒有符合的基金」——
        #    那兩句在來源掛掉的時候是假的。理由見 `upstream_failure_notes()`。
        notes.extend(failure_notes)
    elif not has_rules:
        notes.append(TEXT_NO_CONDITION)
    elif not rows:
        notes.append(TEXT_NO_MATCH)
    # ⛔ **2026-09-24 就地更正：上一版把這一行寫在 `EXP-4`，理由是「『卡上』是哪一張卡 `44` 沒有寫」。**
    #    **那個理由是錯的 —— 我只讀了空狀態欄那一格，沒有讀判準行。**
    #    `44` `EXP-4` 判準行逐字：「取消全部欄位勾選，`EXP-2` 剩下基金名一欄且出現「目前只顯示基金名」」
    #    —— **那一句的主詞是 `EXP-2`**，「且出現」承的是同一個主詞。**44 把指代解開了，而且解向 `EXP-2`。**
    #    ⇒ 本頁自本輪起把它寫在 **`EXP-2`**，照判準行走（§0.2：判準是那個可以被執行的檢查）。
    #    ⚠️ 空狀態欄那句「在卡上寫一行」的「卡上」確實仍然含混，**但它不再是本頁挑邊的理由**。
    if len(shown) == 1 and shown[0] == ALWAYS_SHOWN_COLUMN and not visible_columns:
        notes.append(TEXT_ONLY_FUND_NAME)

    # ⚠️ **登記（`E-08`）**：`44` 說依 `fund_code` 排，但那一欄不在它自己列的五欄裡。
    #    本檔把排序依據寫成表頭上方一行，**不自行把 `fund_code` 加進欄位清單**。
    # ⛔ 它有自己的鍵，**不是 `detail_lines` 的第一項** —— 畫面層靠位置取某一行，
    #    下一個人在前面插一行說明就會把排序說明畫到別的地方去，而且不會有任何東西轉紅。
    sort_caption = _sort_caption(sort_column)
    detail_lines = [
        "本卡沒有綜合分數欄、沒有星等欄、沒有排名欄；排序結果不加任何冠詞（G1†）。",
    ]
    if sort_column == "nav_orig_ccy":
        # ⚠️ **登記（`E-06`）**：依「最近淨值（原幣）」排序＝把不同幣別的數字拿去比大小。
        #    `44` 允許使用者自選排序欄位，**也沒有任何一條擋它**；客戶那句「同卡不混不同幣別做平均」
        #    字面上擋不到排序。本檔照 `44` 把這一項留在下拉裡，**並把這件事寫在畫面上**。
        detail_lines.append(
            "⚠ 目前依最近淨值（原幣）排序，不同幣別的數字因此被放在同一個順序裡比大小。"
            "44 允許使用者自選排序欄位，也沒有一條規則擋這一種；就地寫出來，不自行拿掉這一項。"
        )
    state = STATE_ERROR if fail_message else worst_state(cell_states)
    return _block(
        "EXP-2",
        state=state,
        states=cell_states,
        summary_text=(
            TEXT_NO_CONDITION
            if not has_rules
            else f"{hinted(format_count(len(rows)))} 檔候選"
        ),
        _rows=rows,
        column_keys=tuple(shown),
        column_labels=[COLUMN_LABELS[c] for c in shown],
        sort_caption=sort_caption,
        notes=notes,
        detail_lines=detail_lines,
        badges=[
            placeholder_badge("來源", "〔來源層級〕"),
            placeholder_badge("新鮮度", "〔新鮮度〕"),
        ],
        redline_note="G1†：本卡不排名、不標最佳，也不預設排序欄位。",
    )


def scenario_fallback_note(asked, used, label):
    """網址給的情境名不認得時，畫面上要說的那一句。認得就回 `None`。

    ⛔ **2026-09-24 第二輪稽核：閘門會安靜退回，而畫面上一個字都沒說。**
    實測 `?scenario=sortnvav`（打錯）與 `?scenario=full` **渲染逐字相同**，
    頁首還肯定地寫「情境 狀態 1｜全齊」——
    **使用者看到的是一個他沒要求的畫面，而畫面不承認這件事。**
    ⚠️ 這不違反 §1（沒有編造任何數值、資料層照舊 `raise KeyError`），
    但它與本輪第 6、7 條**同形**：**真相寫在註解裡，畫面上沒有。**
    """
    if not asked or asked == used:
        return None
    return f"⚠ 網址給的情境名「{asked}」查無此情境，已退回「{label}」。"


def column_for_label(label):
    """排序下拉顯示的字 → 欄位鍵（`不排序` → `None`）。

    ⛔ **這是判定，所以住在這裡，不住在 `page.py`**（`page.py` 一個判定也不做）。
    ⚠️ 認不得的字**回 `None`（＝不排序），不猜** —— 但那本來就走不到：
    下拉的選項集合就是本函式的定義域（由 `test_排序下拉的每一個選項都對得回一個欄位` 釘住）。
    """
    if not label or label == TEXT_NO_SORT:
        return None
    for column, text in COLUMN_LABELS.items():
        if text == label:
            return column
    return None


def _sort_caption(sort_column) -> str:
    if not sort_column:
        return f"依 {DEFAULT_SORT_FIELD} 字面值排列（未選排序欄位）"
    return f"依「{COLUMN_LABELS[sort_column]}」排序"


def _sort_key(row, column, ratios):
    """排序鍵。

    ⚠️ **登記**：`44` **沒有寫排序時缺值要排哪裡**。本檔把缺值一律排在最後、同值保持原順序
    （原順序＝`fund_code` 字面值）。⛔ **這是本組挑的一邊。**
    """
    cell = row["_cells"].get(column)
    if cell is None or cell["_state"] is not STATE_OK:
        return (1, "")
    if column == "div_ratio_pct":
        # ⚠️ 這一欄拿**數**去排，不是拿畫面字串 —— 字串帶「%」與「（示意）」，
        #    照字串排會把 `10.0%` 排在 `2.1%` 前面。
        return (0, ratios.get(row["_fund_code"], 0.0))
    # ⚠️ **`nav_orig_ccy` 不走這裡** —— 它同樣要拿數排，而數在 `nav` 那張表上，
    #    所以由 `_sorted_rows()` 單獨處理。這裡刻意不留一個永遠走不到的分支
    #    （一個走不到的分支看起來像有處理過，實際上沒有）。
    return (0, cell["text"])


def _sorted_rows(rows, dataset, sort_column, ratios):
    rows = sorted(rows, key=lambda r: r["_fund_code"])
    if not sort_column:
        return rows
    if sort_column not in {c for r in rows for c in r["_cells"]}:
        # `44` `EXP-4` 空狀態欄逐字：「排序欄位所指的欄被取消勾選 → 排序回到『不排序』」。
        # ⛔ **登記（2026-09-24 第二輪稽核，本輪只登記、不動行為）**：
        #    **同一條 `44` 規則在本檔有兩份實作**，而**活的是另一份**
        #    （`build_page_model` 那邊先把 `sort_column` 收掉，所以走到這裡時它必定已經在欄裡）。
        #    稽核實測：這個 TRUE 分支在 production 與兩個測試檔**全部 0 次**，整段刪掉全綠。
        #    ⚠️ **留著的成本寫明**：它帶著一句 `44` 的逐字引文，
        #    **下一個人會以為這條規則是在這裡被驗過的** —— 實際上驗它的是另一份。
        #    **本輪不刪**（`44` §6「不刪，只標」＋ 本輪授權是「只登記」）。
        return rows
    if sort_column == "nav_orig_ccy":
        navs = {r["_fund_code"]: latest_nav(dataset, r["_fund_code"]) for r in rows}
        return sorted(
            rows,
            key=lambda r: (
                (1, 0.0) if navs[r["_fund_code"]] is None
                else (0, navs[r["_fund_code"]]["nav_orig_ccy"])
            ),
        )
    return sorted(rows, key=lambda r: _sort_key(r, sort_column, ratios))


def _build_exp3(dataset, *, matched, compare_checked, viewport_width):
    """`EXP-3` 並排對照卡。"""
    ratios = dataset.get("div_ratio_pct") or {}
    by_code = {p["fund_code"]: p for p in matched}
    # `44` `EXP-3` 來源欄，那一格劃線改寫之後的逐字：「『對照』那一組勾選框被勾起的檔」。
    picked = [by_code[c] for c in sorted(compare_checked) if c in by_code][:COMPARE_LIMIT]

    columns = []
    cell_states = []
    for profile in picked:
        code = profile["fund_code"]
        nav = latest_nav(dataset, code)
        cells = {}
        for key, _label in COMPARE_ROWS:
            if key == "nav_date":
                cells[key] = (
                    _value(hinted(nav["nav_date"])) if nav else _missing_value()
                )
            elif key == "nav_orig_ccy":
                cells[key] = (
                    _value(
                        hinted(f"{nav['nav_orig_ccy']:,.4f}"),
                        has_number=True,
                        ccy=nav["ccy"],
                    )
                    if nav
                    else _missing_value()
                )
            elif key == "div_ratio_pct":
                ratio = ratios.get(code)
                cells[key] = (
                    _value(hinted(format_pct(ratio)), has_number=True, ccy=profile["ccy"])
                    if (nav and ratio is not None)
                    else _missing_value()
                )
            else:
                fee = profile.get("mgmt_fee_rate_pct")
                cells[key] = (
                    _value(hinted(format_fee(fee)), has_number=True, ccy=profile["ccy"])
                    if fee is not None
                    else _missing_value()
                )
        cell_states.extend(cell["_state"] for cell in cells.values())
        columns.append(
            {
                "_fund_code": code,
                "_ccy": profile["ccy"],
                # `44` 規則欄逐字：「不同幣別的檔並排時，幣別寫在欄頭」。
                "head_text": f"{profile['fund_name']}　{profile['ccy']}",
                "_cells": cells,
            }
        )

    notes = []
    failure_notes = upstream_failure_notes(dataset, "EXP-3")
    if failure_notes:
        notes.extend(failure_notes)
    elif not picked:
        # `44` 空狀態欄逐字：「「對照」那一組勾選為零 → 文案『勾選最多 3 檔以並排對照』」。
        notes.append(TEXT_PICK_THREE)

    detail_lines = [
        "本塊採 G2† 三形式中的「客觀對照」：一欄一檔、一列一個指標，卡上不標示哪一欄比較好。",
        "跨欄不做合計，也不做差額排序；不同幣別的檔並排時幣別寫在欄頭。",
        # ⚠️ **登記（`E-16`）**：指標列是沿用已拍板草稿的四列，見 `COMPARE_ROWS` 的登記。
        "⚠ 44 的來源欄只寫「對應欄」，沒有列出是哪幾個指標；上面四列沿用已拍板草稿擬的那一組。",
        "⚠ 44 規則欄寫「格內只放數字與單位」，而「最近淨值日」是日期；44 沒有處理這一點，照放並就地寫明。",
    ]
    if compare_stacks(viewport_width):
        # ⚠️ **登記（`E-15`）**：見 `compare_stacks()`。
        detail_lines.append(
            "⚠ 目前寬度改成逐檔上下堆疊：44 禁橫向捲動，但沒有寫卡內表格怎麼塌，這一種塌法沿用已拍板草稿。"
        )
    return _block(
        "EXP-3",
        state=STATE_ERROR if failure_notes else worst_state(cell_states),
        states=cell_states,
        summary_text=(
            f"對照 {hinted(format_count(len(picked)))} 檔" if picked else TEXT_PICK_THREE
        ),
        _columns=columns,
        row_labels=[label for _key, label in COMPARE_ROWS],
        row_keys=tuple(key for key, _label in COMPARE_ROWS),
        _stacked=compare_stacks(viewport_width),
        notes=notes,
        detail_lines=detail_lines,
        badges=[
            placeholder_badge("來源", "〔來源層級〕"),
            placeholder_badge("新鮮度", "〔新鮮度〕"),
            _redline_badge("G2†"),
        ],
        redline_note="G2†：客觀對照，不提供具體處置方向。",
    )


def _build_exp4(dataset, *, visible_columns, sort_column, save_failed_message):
    """`EXP-4` 欄位與排序設定。"""
    # `44` 規則欄逐字：「可選欄位清單取 `EXP-2` 規則欄逐字列出的那幾欄」。
    options = [
        {
            "_checkbox": True,
            "_group": "欄位",
            "_fund_code": None,
            "_checked": key in visible_columns,
            "_enabled": True,
            "_visible": True,
            "label": COLUMN_LABELS[key],
            "disabled_reason": "",
            "note": "",
            "_column": key,
        }
        for key in COLUMN_ORDER
    ]
    # `44` 規則欄逐字：「排序欄位的下拉選單不預先選定任何一欄；沒有選任何一欄時清單就不排序（G3†）」。
    sort_options = [TEXT_NO_SORT] + [COLUMN_LABELS[key] for key in COLUMN_ORDER]
    sort_shown = COLUMN_LABELS[sort_column] if sort_column else TEXT_NO_SORT

    notes = []
    # ⛔ 「目前只顯示基金名」那一行**不在這裡** —— `44` 的判準行把它的主詞寫成 `EXP-2`，
    #    見 `_build_exp2()` 裡那一段就地更正。本塊只寫排序那一句。
    saved_sort = saved_sort_column(dataset)
    if saved_sort and saved_sort not in visible_columns:
        # `44` 空狀態欄逐字：「排序欄位所指的欄被取消勾選 → 排序回到『不排序』，並顯示一行說明」。
        notes.append(
            f"排序欄位「{COLUMN_LABELS[saved_sort]}」目前沒有被勾選，排序已回到{TEXT_NO_SORT}。"
        )

    detail_lines = [
        "本塊不提供推薦欄位組合；「存檔」只寫 user_setting，不寫入 holding、policy、nav、dividend（G1†）。",
        # ⚠️ **登記（`E-07`）**：見 `COLUMN_ORDER`。
        "⚠ 44 要求「欄位清單依欄位名字面值排列」，而上面五項裡有三項不是 fund_profile 的欄位名"
        "（最近淨值日與最近淨值來自 nav，配息佔淨值比連欄位名都沒有）；"
        "本頁照 44 自己寫下那五欄的順序排，不自行發明一套排法。",
        # ⛔ **2026-09-24 第二輪稽核抓到：這一筆本來只活在註解裡。**
        #    `COLUMN_ORDER` 上方那段登記自己寫著「**這個事實必須讓客戶看得到**」，
        #    而唯一釘它的斷言是 `assert "不是客戶裁的" in source` —— **斷言的是 Python 原始碼**。
        #    稽核掃 46 份模型、162 條畫面字串並用 streamlit 真渲染覆驗：
        #    「四項」「AI 總管」「總管」「客戶」**畫面上四個都 0 命中**。
        #    ⛔ 同一塊的 `E-07`／`E-17` 都寫上了畫面 —— **唯獨這筆「客戶沒拍板過的視覺元件」停在註解層。**
        #    現在比照它們寫進 `detail_lines`，並由畫面層測試釘住。
        # ⚠️ 這一句刻意**不寫「逐字」**：它引的是**草稿**、不是 `44`，
        #    而逐字守衛的契約是「宣告自己逐字的句子必須對得回 `44`」。
        #    用「原字樣」而不是「逐字」，既準確、也不必去擴充那張豁免表。
        "⚠ 這份可選欄位是五項，而客戶已拍板的線框草稿畫的是四項（草稿原字樣為 可選欄位四項，"
        "是 EXP-2 那五欄扣掉「基金名」）。多出來的「基金名」進入勾選集，"
        "相對於客戶拍板的那張圖是一次視覺元件增加；它的依據是 44 EXP-4 規則欄 2026-09-23 那一句，"
        "而那一句 44 自己標的決策者是「AI 總管，本輪派工指定」，不是客戶裁示。"
        "本頁照 44 做（44 是 SSOT），但這個差異讓客戶看得到，不寫成「草稿沒跟上」。",
        # ⛔ **2026-09-24 第二輪稽核：這一組控制項的實際行為必須寫在畫面上，不能靠使用者自己發現。**
        "⚠ 上面五個欄位勾選框目前是唯讀的：它們顯示已存的設定，改不動。"
        "原因是接線會讓「取消勾基金名、其他仍勾著」變成走得到的狀態，"
        "而 44 只保障「全部不勾」那一種，沒有寫這一種算不算可接受；那一格待裁決之前本頁不提供它。"
        "欄位組合的各種樣子改由情境示範（例如全不勾那一種）。"
        "排序下拉則是真的接上的：選了就會重排，下面那行說明也跟著換。",
    ]
    kind = None
    row = _setting(dataset, "exp_sort_column")
    if row is not None:
        kind = row.get("value_kind")
    if kind not in VALUE_KINDS:
        # ⚠️ **登記（`E-17`）**：`exp_sort_column` 存的是一個欄位名，
        #    而 `44` 4.5 的 `value_kind` 是封閉六種，六種一個也對不上。**本頁不補第七種。**
        detail_lines.append(
            "⚠ exp_sort_column 這一鍵存的是一個欄位名，而 44 第四節第五小節的 value_kind 是封閉六種"
            "（int／float／date／ratio／list／rules），六種一個也對不上；本頁不自行補第七種，就地寫出來。"
        )

    error_lines = []
    save_fail_notes = []
    if save_failed_message:
        # `44` 空狀態欄逐字：「存檔寫入失敗 → 卡上顯示失敗訊息原文，欄位勾選狀態與排序欄位的當下值
        # 留在畫面上不清掉，`EXP-2` 顯示的欄與排序不變」。
        error_lines.append(TEXT_SAVE_FAILED + "：" + save_failed_message)
        # ⛔ **2026-09-24 第二輪稽核（本組先自報、稽核確認）：`error_lines` 原本同時裝兩種東西** ——
        #    **真的失敗訊息** ＋ **一句登記註記**。那正是本輪 `F` 項修掉的同一個形狀
        #    （`fetch_fail_lines` 就是為了「一個鍵不要裝兩種東西」才拆出來的）。
        #    當時沒出錯，是因為測試數的是**字面** `存檔寫入失敗` 而不是 `len(error_lines)`；
        #    但下一個人只要改成數長度，`EXP-4` 就會被讀成兩個失敗框。
        #    ⇒ 登記註記自本輪起住在自己的鍵 `save_fail_notes`。
        save_fail_notes.append(
            "⚠ 這一枚按鈕同時寫兩鍵。兩鍵一成一敗時畫面長什麼樣，44 沒有寫，本頁不替它選；"
            "目前這個畫面演的是兩鍵都失敗。"
        )

    return _block(
        "EXP-4",
        state=STATE_OK,
        states=(),
        summary_text=(
            f"{hinted(format_count(len(visible_columns)))} 欄　排序：{sort_shown}"
            if visible_columns
            else TEXT_ONLY_FUND_NAME
        ),
        _options=options,
        sort_options=sort_options,
        sort_shown=sort_shown,
        notes=notes,
        detail_lines=detail_lines,
        error_lines=error_lines,
        save_fail_notes=save_fail_notes,
        # `44` 規則欄逐字：「一枚按鈕同時寫兩鍵，不拆成兩枚。」
        buttons=[_button(TEXT_SAVE, "存檔")],
        badges=[],
        redline_note="G3†：不代使用者勾任何欄位，也不把「不排序」補成任何一個候選欄位。",
        _save_writes=sorted(SAVE_WRITES),
        _save_keys=("exp_visible_columns", "exp_sort_column"),
    )


def _build_exp5(dataset, *, watch_checked, watchlist, save_failed_message):
    """`EXP-5` 加入觀察清單。"""
    picked = sorted(watch_checked)
    # `44` 空狀態欄逐字：「「觀察清單」那一組勾選為零 → 按鈕停用，停用原因為『尚未勾選任何基金』」。
    button = _button(
        TEXT_ADD_WATCH,
        "存檔",
        enabled=bool(picked),
        disabled_reason="" if picked else TEXT_NO_PICK,
    )

    # `44` 規則欄逐字：「觀察清單只存 `fund_code`，不存任何金額、不存任何比重。」
    # 同一檔按兩次，清單裡只出現一次 —— 用集合合併，不 append。
    after = sorted(set(watchlist) | set(picked))

    detail_lines = [
        f"觀察清單目前有 {hinted(format_count(len(watchlist)))} 檔："
        + ("、".join(watchlist) if watchlist else "（空）"),
        "本塊只寫 user_setting 的 exp_watchlist，不寫入 holding，不產生任何交易意圖的紀錄（G1†）。",
        "按鈕標籤是「加入觀察清單」，action_kind 是「存檔」—— 那是 44 第五節按鈕那一類的兩個不同參數。",
    ]
    already = [code for code in picked if code in watchlist]
    if already:
        detail_lines.append(
            "已在觀察清單、按了不會重複寫入的：" + "、".join(already)
        )

    error_lines = []
    if save_failed_message and picked:
        # `44` 空狀態欄逐字：「存檔寫入失敗 → 卡上顯示失敗訊息原文，`EXP-2` 那一組「觀察清單」
        # 勾選框的當下勾選狀態留在畫面上不清掉，觀察清單的內容不變」。
        error_lines.append(TEXT_SAVE_FAILED + "：" + save_failed_message)
    elif save_failed_message:
        # ⚠️ **登記**：按鈕停用時會不會有失敗態，`44` 沒有寫。本檔取「停用就不出失敗框」，
        #    理由同已拍板草稿 §F 那一框：反過來畫會讓畫面自己打架（一枚按不到的按鈕報說它寫失敗了）。
        detail_lines.append(
            "⚠ 這一枚按鈕目前停用，所以不出存檔失敗框。按不到的按鈕會不會有失敗態，44 沒有寫，"
            "本頁取「停用就不出失敗框」這一邊。"
        )

    return _block(
        "EXP-5",
        state=STATE_OK,
        states=(),
        summary_text=(
            f"勾起 {hinted(format_count(len(picked)))} 檔"
            if picked
            else TEXT_NO_PICK
        ),
        _picked=tuple(picked),
        _after=tuple(after),
        notes=[],
        detail_lines=detail_lines,
        error_lines=error_lines,
        buttons=[button],
        badges=[],
        redline_note="G1†：本塊不寫入 holding，也不產生任何交易意圖的紀錄。",
        _save_writes=sorted(SAVE_WRITES),
        _save_keys=("exp_watchlist",),
    )


def exp6_fund_code(compare_checked):
    """`EXP-6` 顯示的是哪一檔。

    ⚠️ **登記（`E-10`）**：`44` `EXP-6` 的來源欄**沒有說是哪一檔**
    （它不像 `EXP-3` 那樣寫「`EXP-2` 中「對照」那一組勾選框被勾起的檔」），
    而它那一行判準又逐字寫「輸入一個不存在的 `fund_code`」—— 要一個輸入框；
    但本塊在**層 4**，而 `44` 2 的層 4 逐字是「原始序列、計算軌跡、來源與新鮮度明細」，
    使用者輸入在層 3。
    ⛔ 本檔沿用已拍板的草稿 §H 的 T-12，取**最保守**的那一種：
    **跟著「對照」那一組勾起的第一檔，不新增 `44` 沒有宣告的輸入框。**
    """
    picked = sorted(compare_checked)
    return picked[0] if picked else None


def _build_exp6(dataset, *, compare_checked):
    """`EXP-6` 單檔基礎資料。"""
    code = exp6_fund_code(compare_checked)
    profile = profile_of(dataset, code) if code else None

    fields = []
    cell_states = []
    if profile is not None:
        for key, label in EXP6_FIELDS:
            raw = profile.get(key)
            if raw is None or raw == "":
                # `44` 空狀態欄逐字：「某欄為空 → 顯示 `⬜`，不以零或字串『無』填。」
                node = _missing_value(label)
            elif key == "mgmt_fee_rate_pct":
                node = _value(hinted(format_fee(raw)), has_number=True,
                              ccy=profile["ccy"], label=label)
            else:
                # `44` 規則欄逐字：「欄位值原樣顯示，不做任何換算與四捨五入以外的加工」。
                node = _value(str(raw), label=label)
            cell_states.append(node["_state"])
            fields.append(node)

    notes = []
    failure_notes = upstream_failure_notes(dataset, "EXP-6")
    if failure_notes:
        # ⛔ **這一塊是四塊裡最要緊的一塊**：照原本的路走，它會在 `fund_profile` 取數失敗時
        #    印「查無此 `fund_code`」—— 那是對一檔基金**斷言了一件事實**，而真相是沒查到。
        notes.extend(failure_notes)
    elif code is None:
        notes.append("「對照」那一組一檔也沒有勾，本塊沒有要顯示的基金。")
    elif profile is None:
        # `44` 空狀態欄逐字：「整檔查無 → `來源缺`，文案『查無此 `fund_code`』」。
        notes.append(TEXT_NO_SUCH_FUND)

    detail_lines = [
        f"本塊目前要顯示的是 {code}。" if code else "本塊目前沒有要顯示的基金。",
        "本塊跟著「對照」那一組勾起的第一檔。⚠ 44 的來源欄沒有寫是哪一檔，"
        "而它那一行判準又要一個輸入 fund_code 的位置；本塊在層 4，44 的層 4 不放使用者輸入。"
        "本頁取最保守的一種，不新增 44 沒有宣告的輸入框。",
        # ⚠️ **登記（`E-11`）**：來源欄取了 `nav` 最近 1 筆與 `dividend` 最近 12 個月，
        #    而規則欄列出要顯示的六欄**全部來自 `fund_profile`**。
        "⚠ 44 的來源欄取了 nav 最近 1 筆與 dividend 最近 12 個月，而規則欄列的六欄全部來自 "
        "fund_profile；本塊只畫那六欄，不自行加 nav／dividend 的格。",
    ]
    empty_kind = None
    if failure_notes:
        empty_kind = EMPTY_ERROR
    elif code is not None and profile is None:
        empty_kind = EMPTY_SOURCE
    state = (
        STATE_ERROR if empty_kind == EMPTY_ERROR
        else STATE_MISSING if empty_kind
        else worst_state(cell_states)
    )
    return _block(
        "EXP-6",
        state=state,
        states=cell_states,
        summary_text=(
            ERR_TEXT if failure_notes
            else f"{code}" if profile is not None
            else (TEXT_NO_SUCH_FUND if code else "尚未勾選任何基金")
        ),
        _fund_code=code,
        # 一檔一區塊，所以幣別掛在塊上。`cross_currency_nodes()` 靠它把這一塊的每一個數
        # 歸屬到這一檔底下 —— 沒有它，這一塊出的數會變成「掛不到任何一檔」而被誤報。
        _ccy=(profile or {}).get("ccy"),
        _fields=fields,
        _empty_kind=empty_kind,
        notes=notes,
        detail_lines=detail_lines,
        badges=[],
        redline_note="本塊只顯示登記值原樣，不做任何加工。",
    )


def _build_exp7(dataset, *, steps, has_rules, conclusion_count):
    """`EXP-7` 篩選軌跡。"""
    failure_notes = upstream_failure_notes(dataset, "EXP-7")
    rows = []
    for rule, before, after in steps:
        effective = rule_is_effective(rule)
        rows.append(
            {
                "condition_text": rule_text(rule),
                "before_text": hinted(format_count(before)),
                "after_text": hinted(format_count(after)),
                "_before": before,
                "_after": after,
                # ⚠️ **登記（`E-23`）**：`44` 空狀態欄逐字要「在列尾**寫** `未生效`」，
                #    而 `未生效` **不在** `44` 5.2 `狀態` 徽章那七個封閉字面值裡。
                #    ⛔ 本檔照 `44` 用的動詞「寫」做成**列尾的一段文字，不是一枚徽章**，
                #    也**不自行把第八種字面值加進那份封閉清單**。
                "tail_text": "" if effective else TEXT_NOT_EFFECTIVE,
            }
        )

    notes = []
    empty_kind = None
    if failure_notes:
        # ⛔ 上游那張表掛掉時，這三欄的數不是真的 —— 印一串「0 → 0」而什麼都不說，
        #    比沒有這一塊更誤導。理由見 `BLOCK_SOURCE_TABLES` 裡 `EXP-7` 那一列。
        notes.extend(failure_notes)
        empty_kind = EMPTY_ERROR
        rows = []
    elif not has_rules:
        # `44` 空狀態欄逐字：「條件一列也沒有 → `來源缺`，文案『尚未設定條件』。」
        notes.append(TEXT_NO_CONDITION)
        empty_kind = EMPTY_SOURCE

    detail_lines = [
        f"最後一列的套用後檔數與 EXP-0 的 N 相等：{hinted(format_count(conclusion_count))}。"
        if rows
        else ("上游取數失敗，本塊不列出任何軌跡列。" if failure_notes else "尚未套用任何條件。"),
        # ⚠️ **登記（`E-12` 還開著的那一半）**：`44` 把「尚未設定條件」這個畫面掛上 `來源缺`
        #    這個種類名，而那**不是**來源缺 —— 那是使用者還沒輸入。
        "⚠ 44 把「尚未設定條件」這個畫面掛上「來源缺」這個種類名，而那其實是使用者還沒輸入，"
        "不是來源一筆資料也沒有；44 同一節又寫「本表的顏色與種類名各塊不得自訂」。"
        "本頁照塊規則的文案畫、不自訂種類名，就地寫出這個落差。",
    ]

    state = (
        STATE_ERROR if empty_kind == EMPTY_ERROR
        else STATE_MISSING if empty_kind
        else STATE_OK
    )
    return _block(
        "EXP-7",
        state=state,
        states=(),
        # ⛔ **2026-09-24 本組自查補的 Fail-Loud 洞：這一格原本只有兩個分支**
        #    （`rows` 有 → 「N 條軌跡」；否則 → 「尚未設定條件」）。
        #    **上游取數失敗時 `rows` 被清空，於是它掉進第二支，宣告「尚未設定條件」**
        #    —— 而 `profilefail` 這個情境**明明設了三條規則**（實測：`user_setting` 的
        #    `exp_filter_rules` 有三列），條件在、掛掉的是來源。
        #    **那是「把取數失敗講成別的原因」**，正是 §1 與 `44` 都點名禁止的那一種
        #    （同一輪已經替 `EXP-2`／`EXP-3`／`EXP-6` 修掉四句同型的話，**這一句漏了**：
        #    當時看的是 `_state`，而 `_state` 早就正確地是 `系統錯誤`，**說謊的是文案**）。
        #    ⇒ 改成三個分支，失敗那一支用與其他塊同一個常數 `ERR_TEXT`。
        #    由 `test_上游掛掉時EXP7的摘要不講成尚未設定條件` 釘住。
        summary_text=(
            f"{hinted(format_count(len(rows)))} 條軌跡" if rows
            else ERR_TEXT if failure_notes
            else TEXT_NO_CONDITION
        ),
        _rows=rows,
        column_labels=("條件", "套用前", "套用後"),
        _empty_kind=empty_kind,
        notes=notes,
        detail_lines=detail_lines,
        badges=[],
        redline_note="本塊只記錄哪一條條件把檔數砍下來，不對結果加任何評語。",
    )


def conclusion_light(*, count, has_rules, read_states):
    """`EXP-0` 的燈色與文案。**只讀 `EXP-1` 與 `EXP-2` 算出來的東西，不自取數。**

    `44` `EXP-0` 規則欄逐字（客戶 2026-09-22 裁示的三色）：
    「N 為零 → 燈為中性灰。N 大於零 → 燈為黃。本塊讀到的那兩塊任一為 `系統錯誤` → 燈為紅，
    文案列出失敗的那一段」。

    ⚠️ 空狀態欄逐字補了一句本檔照做的優先序：「**這兩句同時成立時（條件未設時 N 必定為零）
    取「尚未設定條件」那一句**」。
    """
    if STATE_ERROR in read_states:
        return "紅", STATE_ERROR
    if count == 0:
        return "灰", STATE_MISSING if not has_rules else STATE_OK
    return "黃", STATE_OK


def _build_exp0(dataset, *, count, has_rules, rules, read_states):
    """`EXP-0` 篩選結果結論列。"""
    tone, state = conclusion_light(count=count, has_rules=has_rules, read_states=read_states)

    fetch_fail_lines = []
    if tone == "紅":
        # `44` 規則欄逐字：「文案列出失敗的那一段」。
        # ⚠️ 這一族是**取數**失敗，不是存檔失敗 —— 放 `fetch_fail_lines`，不放 `error_lines`。
        for code in ("EXP-1", "EXP-2"):
            fetch_fail_lines.extend(
                f"{code}　{line}" for line in source_error_lines(dataset, code)
            )
        text = "讀到的那兩塊有一塊取數失敗"
    elif not has_rules:
        text = TEXT_NO_CONDITION
    elif count == 0:
        text = TEXT_NO_MATCH
    else:
        text = conclusion_text(count)

    # `44` 空狀態欄逐字：「N 為零 → 文案「目前條件下沒有符合的基金」，並列出目前生效的條件列」。
    # ⚠️ **登記（`E-02`）**：來源欄逐字只授權「只讀 `EXP-2` 的列數與 `EXP-1` 的條件列數」，
    #    而列出條件列要讀條件的**內容**。**兩格說法不同。**
    #    本檔照**空狀態欄**做（列出條件列），並就地寫出這個互斥。
    condition_lines = []
    if has_rules and count == 0 and tone != "紅":
        condition_lines = [rule_text(rule) for rule in rules if rule_is_effective(rule)]

    detail_lines = [
        "本塊不自取數：只讀 EXP-2 的列數與 EXP-1 的條件列數。",
        "⚠ 44 的來源欄只授權讀列數，而空狀態欄要求列出目前生效的條件列（那要讀條件的內容）；"
        "兩格說法不同，本頁照空狀態欄做，就地寫出來。",
        "燈色描述的是「這組條件下現在有沒有東西可看」，不描述任何一檔基金的好壞（G1†）。",
    ]

    # 客戶 2026-09-22 設計引導第二條：狀態不靠顏色單獨辨識 —— 圖示與文字同時出現。
    # ⚠️ **登記：這四句狀態文字 `44` 一句也沒有給**（客戶裁的是三個**顏色**）。下面是本組擬的。
    # ⛔ **刻意不借卡片四狀態那一組字**（`資料未備`／`業務例外`／`系統錯誤`）——
    #    `44` `EXP-0` 塊下方自己就地登記過：**本塊的燈與前四枚燈方向相反**
    #    （前四枚灰＝正常、黃＝要注意；本塊灰＝什麼都沒有、黃＝有結果）。
    #    把灰寫成「資料未備」會把那個相反的方向**又藏回去**：條件未設的時候資料好端端的，
    #    缺的是使用者還沒輸入。**一句把「你還沒設條件」說成「資料未備」的文案，是假的。**
    glyph = {"灰": "⬜", "黃": "◧", "紅": "⚠"}[tone]
    if tone == "紅":
        state_word = "取數失敗"
    elif not has_rules:
        state_word = "條件未設"
    elif count == 0:
        state_word = "零檔符合"
    else:
        state_word = "有檔符合"

    block = _block(
        "EXP-0",
        state=state,
        states=(),
        summary_text=text,
        text=text,
        _tone_override=tone,
        glyph=glyph,
        state_word=state_word,
        condition_lines=condition_lines,
        condition_caption=TEXT_EFFECTIVE_CONDITIONS,
        fetch_fail_lines=fetch_fail_lines,
        notes=[],
        detail_lines=detail_lines,
        badges=[],
        redline_note="G1†：本行不對檔數的多寡加任何評語。",
    )
    # ⚠️ **結論燈的顏色不走卡片那張四狀態表** —— `44` 給了本塊自己的三色規則
    #    （客戶 2026-09-22 裁示：N 為零灰／N 大於零黃／讀到的塊出錯紅）。
    #    這裡把 `_block()` 依四狀態算出來的 `_tone` 覆寫掉，讓這一塊只有**一個**顏色，
    #    **不留兩個會各說各話的欄位**給畫面層挑。
    block["_tone"] = tone
    return block


# ───────────────────────── 整頁 ─────────────────────────


# 「沒有覆寫」的哨符。**不能用 `None`** —— `sort_column=None` 是一個**有意義的值**
# （＝不排序），拿 `None` 當「沒給」會把「使用者選了不排序」和「使用者沒動過」混成一件事。
_NO_OVERRIDE = object()


def build_page_model(
    dataset: dict,
    *,
    draft_rules=None,
    compare_checked=(),
    watch_checked=(),
    viewport_width: int = 1280,
    save_failed: bool = False,
    visible_columns=_NO_OVERRIDE,
    sort_column=_NO_OVERRIDE,
) -> dict:
    """把假資料 ＋ 使用者當下的勾選組成一份純資料模型。page.py 只負責把它畫出來。

    ⚠️ **`draft_rules` 是「欄位的當下內容」，`dataset` 裡的 `exp_filter_rules` 是「已存值」。**
    `44` `EXP-1` 塊下方就地登記過：「條件的『當下值』與『已存值』哪一個餵 `EXP-2`，本塊沒有寫」，
    並標為**待客戶或總管裁決**。**本檔取「當下值」**，理由是 `44` `EXP-1` 那一行判準逐字寫
    「新增一列但數值留空，該列尾端出現 `⬜ 資料未備：數值未填` 且 `EXP-2` 的列數不因這一列改變」——
    那一句要成立，`EXP-2` 就得看得到還沒存的那一列。
    ⛔ **這是被迫挑的一邊，不是規格**；客戶裁哪一邊，改的只有這一行。畫面上也寫了這件事。
    """
    rules = tuple(draft_rules) if draft_rules is not None else saved_rules(dataset)
    has_rules = bool(rules)
    compare_checked = tuple(compare_checked)
    watch_checked = tuple(watch_checked)

    profiles = list(dataset.get("fund_profile", ()))
    steps_full = apply_rules(profiles, rules)
    matched = steps_full[-1][3] if steps_full else (profiles if has_rules else [])
    if not has_rules:
        matched = []

    # ⛔ **2026-09-24 第二輪稽核抓到：`EXP-4` 的五個勾選框與排序下拉完全沒接線。**
    #    取消勾「基金名」之後 `EXP-2` 的欄位**完全不變**；選了排序欄位之後，
    #    排序說明列**仍印「依 fund_code 字面值排列（未選排序欄位）」** ——
    #    **那是使用者操作之後畫面說的一句假話**，與本頁到處在防的那一類同形。
    #    ⚠️ 而同一頁的 `EXP-2` 對照勾選框**是有接線的** —— 同一種元件，一組接、一組不接、零登記。
    #    現在兩者都接上：沒有覆寫就用已存值（行為與從前完全相同），有覆寫就用使用者當下選的。
    visible_columns = (
        saved_columns(dataset) if visible_columns is _NO_OVERRIDE else tuple(visible_columns)
    )
    sort_column = (
        saved_sort_column(dataset) if sort_column is _NO_OVERRIDE else sort_column
    )
    if sort_column and sort_column not in visible_columns:
        # `44` `EXP-4` 空狀態欄逐字：「排序欄位所指的欄被取消勾選 → 排序回到『不排序』」。
        sort_column = None
    watchlist = saved_watchlist(dataset)

    exp1 = _build_exp1(
        dataset,
        draft_rules=rules,
        save_failed_message=save_error(dataset, ("exp_filter_rules",)) if save_failed else None,
    )
    exp2 = _build_exp2(
        dataset,
        matched=matched,
        has_rules=has_rules,
        visible_columns=visible_columns,
        sort_column=sort_column,
        compare_checked=compare_checked,
        watch_checked=watch_checked,
        watchlist=watchlist,
    )
    exp3 = _build_exp3(
        dataset,
        matched=matched,
        compare_checked=compare_checked,
        viewport_width=viewport_width,
    )
    exp4 = _build_exp4(
        dataset,
        visible_columns=visible_columns,
        sort_column=sort_column,
        save_failed_message=(
            save_error(dataset, ("exp_visible_columns", "exp_sort_column"))
            if save_failed
            else None
        ),
    )
    exp5 = _build_exp5(
        dataset,
        watch_checked=watch_checked,
        watchlist=watchlist,
        save_failed_message=save_error(dataset, ("exp_watchlist",)) if save_failed else None,
    )
    exp6 = _build_exp6(dataset, compare_checked=compare_checked)

    # `44` `EXP-0` 規則欄逐字：「N 為 `EXP-2` 的列數」。
    # ⚠️ **取數失敗不把 N 歸零** —— 失敗的那張表在資料層就已經沒有列了（見 `fixtures._dataset`），
    #    所以列數自己會反映它。硬把 N 壓成 0，`EXP-7` 那一行「最後一列的套用後檔數與 `EXP-0` 的 N 相等」
    #    就會在 `nav` 失敗時對不起來（清單照列、只有淨值那幾格是 `⬜`）。
    count = len(exp2["_rows"])
    exp7 = _build_exp7(
        dataset,
        steps=[(rule, before, after) for rule, before, after, _rows in steps_full],
        has_rules=has_rules,
        conclusion_count=count,
    )
    exp0 = _build_exp0(
        dataset,
        count=count,
        has_rules=has_rules,
        rules=rules,
        # `44` `EXP-0` 來源欄逐字：只讀 `EXP-2` 與 `EXP-1` 這兩塊。
        read_states=(exp1["_state"], exp2["_state"]),
    )

    blocks = [exp0, exp1, exp2, exp3, exp4, exp5, exp6, exp7]
    return {
        "title": PAGE_TITLE,
        "answers": PAGE_ANSWERS,
        "footer_lines": list(PAGE_NOT_RESPONSIBLE),
        "footer_badges": [_redline_badge(mark) for mark in PAGE_REDLINES],
        "_viewport_width": viewport_width,
        "blocks": blocks,
    }


# ───────────────────────── 取用與掃描 ─────────────────────────


# ⛔ **無呼叫者登記（2026-09-24 第二輪稽核抓到：這九筆原本是「靜默留著」）**
#
# **為什麼要有這張表**：本檔在 `status_badge` 上方自己訂過體例 ——
# 「**留著、就地寫明為什麼，不是靜默留著**」。而下列九筆**留著、卻一個字都沒寫**。
# 稽核把其中六支改名之後 **170 passed、零參照**。
#
# ⛔ **處置與 `44` §6 有一個我不能自己解決的衝突，就地寫明，不替它選**：
#   · `44` §6 逐字：「**不刪，只標**」，而且「死碼的逐筆登記在 `46_fund_live_dead.md`」。
#   · 但 **`46_fund_live_dead.md` 明文不在本組的檔案邊界內**（「一律不准動」）。
#   · 也就是說：**照 `44` 做要寫進一個我不准動的檔；而「刪掉」直接違反 `44` §6 的「不刪」。**
#   ⇒ **本輪的處置是「標在這裡」** —— 讓它們不再是靜默的，
#     同時**把登記寫進 `46` 這件事回報上去請裁決**。**本組不自行刪除任何一筆。**
#   ⚠️ 姊妹頁 `ui_v2/hld` 在 `46` 裡有 6 列，**`ui_v2/exp` 一列都沒有** —— 那個缺口還開著。
#
# ⚠️ **本表不是「三層確認」的結論**：`44` §6 要求 grep caller → 查 caller 是否 live → AST 掃 import
#    三層都過才寫得出 `dead`。**本組只做到第一層（全 repo grep 只剩定義處）**，
#    所以這裡一律標 **`未確認`**，不標 `dead`。**不要把這張表當成 `44` §6 的登記表。**
KNOWN_NO_CALLER = {
    "KNOWN_CURRENCIES": "幣別白名單。⛔ 註解原本宣稱它是跨幣別守衛用的，而真正做那件事的 "
                        "`cross_currency_nodes()` 從頭到尾沒讀過它 —— 那句宣稱已於本輪改掉。",
    "STORAGE_TIMEZONE": "`44` 4.x 的儲存時區常數；本頁的假資料都是日期字串，沒有時刻，用不到。",
    "empty_source_text": "空來源的文案產生器；現行空狀態走 `44` §5.5 的四種 kind，沒有走這一支。",
    "not_applicable_text": "「不適用」文案產生器；本頁目前沒有一塊判得出「不適用」。",
    "source_badge": "來源徽章產生器；現行三張核心卡掛的是 `_placeholder_badges()` 那一組佔位徽章。",
    "all_blocks": "取全部塊的便利函式；呼叫端一律直接走 `model[\"blocks\"]`。",
    "non_ok_value_nodes": "非 ok 值節點的便利查詢；目前沒有任何一塊需要它。",
    "checkbox_groups": "某一列兩組勾選框的便利查詢；`page.py` 直接從 `_rows` 讀。",
    "fixtures.NAV_DATE": "單一基準淨值日；自從 `_navs()` 改成逐檔交錯之後，實際用的是 `_NAV_DATES`。",
}


def all_blocks(model: dict) -> list:
    return list(model["blocks"])


def find_block(model: dict, code: str) -> dict:
    for block in model["blocks"]:
        if block["code"] == code:
            return block
    raise KeyError(code)


def codes_in_layer(model: dict, layer: int) -> list:
    return [b["code"] for b in model["blocks"] if b["_layer"] == layer]


def find_row(block: dict, fund_code: str) -> dict:
    for row in block.get("_rows", ()):
        if row.get("_fund_code") == fund_code:
            return row
    raise KeyError(fund_code)


def find_button(model: dict, label: str) -> dict:
    for button in collect_buttons(model):
        if button["label"] == label:
            return button
    raise KeyError(label)


def _walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, (list, tuple, set)):
        for value in node:
            yield from _walk(value)


def collect_badges(model) -> list:
    return [n for n in _walk(model) if isinstance(n, dict) and "_kind" in n and "text" in n]


def collect_buttons(model) -> list:
    return [n for n in _walk(model) if isinstance(n, dict) and "_action_kind" in n]


def collect_checkboxes(model) -> list:
    return [n for n in _walk(model) if isinstance(n, dict) and n.get("_checkbox") is True]


def collect_inputs(model) -> list:
    return [n for n in _walk(model) if isinstance(n, dict) and n.get("_input") is True]


def value_nodes(model) -> list:
    return [n for n in _walk(model) if isinstance(n, dict) and n.get("_value_node")]


def numeric_nodes(model) -> list:
    return [n for n in value_nodes(model) if n["_has_number"]]


def non_ok_value_nodes(model) -> list:
    return [n for n in value_nodes(model) if n["_state"] != STATE_OK]


def collect_ui_strings(model) -> list:
    """模型裡所有**會上畫面**的字串。底線開頭的鍵是機器用的，不收。"""
    out = []

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(key, str) and key.startswith("_"):
                    continue
                walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value)
        elif isinstance(node, str):
            out.append(node)

    walk(model)
    return out


def scan_forbidden(strings) -> dict:
    """`44` 1.2：禁方向詞與禁箭頭。回 `{命中的詞: [那幾句]}`。"""
    hits = {}
    for word in FORBIDDEN_DIRECTION_WORDS + FORBIDDEN_ARROWS:
        found = [s for s in strings if word in s]
        if found:
            hits[word] = found
    return hits


def cross_currency_nodes(model) -> list:
    """把兩種幣別的數合成一個值的節點。

    客戶 2026-09-22 設計引導第三條：「多幣別：逐檔標明幣別，同卡不混不同幣別做平均」；
    `44` `EXP-3` 規則欄逐字：「跨欄不做合計也不做差額排序」。

    **歸屬檢查**：每一個出數的值都必須掛在某一檔底下，且幣別與那一檔相同。
    一個跨幣別的合計／平均／比值，**要嘛掛不到任何一檔底下**，**要嘛幣別對不上它所在的那一檔** ——
    兩條路都會被抓到。
    """
    bad = []
    for block in model["blocks"]:
        containers = [
            item
            for key in ("_rows", "_columns")
            for item in block.get(key, ())
            if isinstance(item, dict) and "_fund_code" in item and item.get("_ccy")
        ]
        # `44` `EXP-6` 逐字「一檔一區塊」—— 那一塊自己就是容器，幣別掛在塊上。
        if block.get("_fund_code") and block.get("_ccy"):
            containers.append(block)
        owned = set()
        for container in containers:
            ccy = container["_ccy"]
            for node in value_nodes(container):
                owned.add(id(node))
                if not node["_has_number"]:
                    continue
                if node["_ccy"] != ccy:
                    bad.append(node)
        for node in value_nodes(block):
            if node["_has_number"] and id(node) not in owned:
                bad.append(node)
    return bad


def column_label_words(model) -> list:
    """全頁用到的欄名。`44` `EXP-2` 判準：欄名集合裡沒有分數、星等、排名、推薦四類欄。"""
    labels = []
    for block in model["blocks"]:
        labels.extend(block.get("column_labels", ()) or ())
        labels.extend(block.get("row_labels", ()) or ())
    return labels


def checkbox_groups(block: dict, fund_code: str) -> dict:
    return find_row(block, fund_code)["_checkboxes"]
