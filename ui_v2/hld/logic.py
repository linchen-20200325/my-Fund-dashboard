# -*- coding: utf-8 -*-
"""持倉體檢純邏輯。零 streamlit import、零舊 repo import、零網路。

所有判定住在這裡；page.py 只負責把 build_page_model() 產出的模型畫出來。
理由：streamlit 在本環境要靠 scratchpad 才匯入得到，邏輯綁進 streamlit 會讓測試跑不起來。

模型慣例：底線開頭的鍵是**機器用**（狀態、色調、層號…），不開頭底線的鍵是**畫面文字**。

⚠️ 本檔逐處標了「登記」的地方，是 `44` 沒有寫、而不決定就畫不出來的。
   一律照最保守的畫法做，**不自行發明規格、不補 SSOT 缺口**，逐筆列進回報。
"""

from __future__ import annotations

import contextvars
import math
import re
from datetime import date

# 「這個參數沒有被傳」與「這個參數被傳成 None」是兩件事。
_UNSET = object()

# ───────────────────────── 常數（逐字引 `44`） ─────────────────────────

# `44` 5.1 卡片四狀態。本輪已改為逐主值判定，不掛在整張卡。
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

# 各類按鈕的寫入對象。
# ⚠️ 登記：`44` 寫「`取數` 類只寫取數回來的列與 `fetch_log`」，
#    但本頁缺的四張表**都在唯讀清單裡**，於是這一頁的 `取數` 沒有表可寫。
#    那正是草稿登記的 ⛔ H-05（「這一頁缺的是 Sheets 維護的表，這枚重新取數按了沒事」）。
#    本檔照最保守的一邊做：**只寫 `fetch_log`**，不自行擴權去寫那四張表。
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

# `44` HLD-4 二次擴寫：「套用」重算本頁每一個以那三組欄位取值的塊。
APPLY_RECALC_BLOCKS = ("HLD-1", "HLD-2", "HLD-3", "HLD-5", "HLD-7", "HLD-8")

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

# 判「同一張卡有沒有把兩種幣別合成一個數」用的幣別字面值。
KNOWN_CURRENCIES = ("USD", "EUR", "TWD", "JPY", "GBP")

_TONE_BY_STATE = {
    STATE_OK: "中性",
    STATE_MISSING: "灰",
    STATE_BIZ: "黃",
    STATE_ERROR: "紅",
}
# ⚠️ **`44` 對這四個狀態只排過一次序，而那一次把中間兩個並列同級。**
# `44` :310（`MKT-0` 規則欄，全檔唯一明文排過卡片四狀態的地方）逐字：
#   「三塊狀態取最差者：三塊皆 `ok` → 燈為中性灰，文案「三張卡的資料齊」；
#     任一塊為 `資料未備` 或 `業務例外` → 燈為黃，文案列出是哪一張卡；
#     任一塊為 `系統錯誤` → 燈為紅，文案列出失敗的那一段」
# ⚠️ **2026-09-24 就地更正（有意識的更正，不是漏刪；決策者：AI 總管）**：
#   ~~上一輪這裡抄的是刪節版~~ —— 它砍掉「三塊狀態取最差者：」與三個「，文案…」子句、
#   把「，」換成「；」、還多加了一組粗體，**旁邊卻標著「逐字」**。
#   語意沒錯，**字不對**；那正是 `44` :2347 寫的那個形狀（改寫一次、標成逐字一次）。
#   **本輪抓到它的是本輪新建的逐字守衛**（`test_標了逐字的引文_每一句都回比過44`）——
#   ⚠️ 而**同一輪 `mkt` 那一份從一開始就是全句逐字的**：
#   **一份對、一份刪節，尺往外用沒往內用。就地補齊。**
#   ⛔ 只換引文，本段的結論（偏序、不是全序）一字未改。
# 也就是 `ok` ＜ {`資料未備`, `業務例外`} ＜ `系統錯誤` —— 這是一個**偏序**，不是全序。
# 舊表述 `{ok:0, 資料未備:1, 業務例外:2, 系統錯誤:3}` 把中間兩個排出先後，
# **那個先後是實作自己發明的，`44` 沒有授權**（客戶 2026-09-23 裁示拆掉）。
_BAND = {STATE_OK: 0, STATE_MISSING: 1, STATE_BIZ: 1, STATE_ERROR: 2}

# 📌 **2026-09-24 登記（本組實測，不處置）：同一個被發明的 tie-break 也住在 `ui_v2/mkt/logic.py`。**
#    該檔的 `_SEVERITY` 與本檔改掉的舊值**逐字相同**，它的 `worst_state()` 一樣用 `max()` 取。
#    ⚠️ **而且那一邊更尖銳**：它的 docstring 自陳引的是「`44` MKT-0 規則逐字：三塊狀態取最差者」，
#    而 `MKT-0` 的規則欄（`44` :310）**正是全檔唯一把那兩個並列同級的地方** ——
#    也就是它引的那一行，恰好否證它自己排出來的先後。
#    ⛔ **本輪不動它**：`ui_v2/mkt/**` 不在本輪的檔案邊界內。**登記，待裁。**

# `worst_state()` 在「`資料未備` 與 `業務例外` 同時是最差」時回這個哨符。
# ⛔ 它**不是第五個狀態**（`44` 5.1 的四狀態是封閉列舉），也**不得寫進任何畫面文字**；
#    它只表示一件事：**`44` 沒有排這兩個的先後，本檔不替它排。**
# ⚠️ 考慮過、而且刻意**不用** `44` 5.2 的 `未定義` 徽章字面值 —— 那一個在 `44` :1735 逐字是
#    「某塊的來源欄寫了一個本檔第四節未定義的欄位 → 該欄位單獨列出並掛「未定義」徽章」，
#    與本處無關，借來用等於替 `44` 造新語意。
# ⚠️ **2026-09-24 就地更正（有意識的更正，不是漏刪；決策者：AI 總管）**：
#    ~~原寫「某塊來源欄寫了一個第四節未定義的欄位」~~ —— 少了「的」與「本檔」兩處，
#    而它就擺在一個行號引用旁邊、包在「」裡，讀起來像逐字。
#    **這不是本輪三件事之一**，改它的理由是：本輪在 `mkt` 那一邊照抄了這一句，
#    而本輪的主題正是「引了 `44` 卻沒讀完自己寫了什麼」——
#    **修 `mkt` 那一份、把它的孿生兄弟留在這裡，就是「同一把尺只往外用」**。
#    ⛔ 只動引文，這一段的結論（不借 `未定義` 這個字面值）一字未改。
STATE_UNRANKED = None

# 📌 **2026-09-24 登記兩筆同型、但不是本輪造成的（不處置，只寫下來）**：
#    本輪自查「凡標『逐字』的引號內容，是否真的逐字出現在 `44`」，掃出兩處**先於本任務就存在**
#    （`a7f8c1b` 上即有）的「把改寫放進引號、旁邊標 `44` 判準」：
#      (1) 本檔 `fund_metrics()` docstring 的「軌跡與所在那一塊逐字相同」；
#      (2) `fixtures.py` 檔頭的「軌跡的輸出值與該值所在那一塊上顯示的字串逐字相同」。
#    `44` :733（`HLD-7` 那一行判準）的實際字面與這兩句**都不相同** —— 它們是**意思對、字不對**的改寫。
#    ⛔ **本輪不改它們**：兩者皆非本輪產物，也不在本輪那十二項必修之內，
#       動它們等於在一個「不准長出第十三項」的輪次裡自行擴張射程。**登記，待裁。**

# ⚠️ **`STATE_UNRANKED` 沒有「名字」，但它有「級」** —— 它只在
#    `資料未備` 與 `業務例外` 同時最差時產生，而 `44` :310 把那兩個放在**同一級**，
#    所以「哪一級」是確定的（就是中間那一級），不確定的只有「哪一個名字」。
#    `_band()` 因此答得出它；`_BAND` 本身**刻意不收這個鍵**，
#    因為收進去就等於承認它是第五個狀態。
_UNRANKED_BAND = 1


def _band(state) -> int:
    """狀態 → `44` :310 那三級。`STATE_UNRANKED` 走上面那條註解說明的路。"""
    return _UNRANKED_BAND if state is STATE_UNRANKED else _BAND[state]

# 塊名逐字引 `44` 3.2 的層次表與各塊標題。
BLOCK_TITLES = {
    "HLD-0": "體檢結論燈",
    "HLD-1": "偏離提示卡",
    "HLD-2": "績效與風險卡",
    "HLD-3": "配息與本金卡",
    "HLD-4": "檢視區間與門檻輸入",
    "HLD-5": "單檔展開",
    "HLD-6": "淨值與配息序列",
    "HLD-7": "計算軌跡",
    "HLD-8": "最大回撤與本金類配息佔比",
}
BLOCK_LAYERS = {
    "HLD-0": 1,
    "HLD-1": 2,
    "HLD-2": 2,
    "HLD-3": 2,
    "HLD-4": 3,
    "HLD-5": 3,
    "HLD-6": 4,
    "HLD-7": 4,
    "HLD-8": 4,
}

# 「回答什麼」逐字引 `44` 3.2 各塊那一格（HLD-2／HLD-3／HLD-7 取 2026-09-22 改寫後的句子）。
ANSWERS = {
    "HLD-0": "這個月我需不需要打開這一頁細看",
    "HLD-1": "哪幾檔現在超出了我自己寫下的那條線，超出多少",
    "HLD-2": "我這幾檔在同一段期間裡，各自走了多少、抖了多大",
    "HLD-3": "我在這段區間裡逐檔收到多少配息，這些配息相當於淨值的多少",
    "HLD-4": "我現在是用哪一段期間、哪幾條線在檢查",
    "HLD-5": "這一檔單獨看，淨值和配息是怎麼交錯的",
    "HLD-6": "本頁那四塊用到的原始數字，逐筆是什麼",
    "HLD-7": "本頁那四塊上的每一個數字，是拿哪幾筆、怎麼算出來的",
    "HLD-8": "那兩個從核心卡移下來的值，逐檔是多少",
}

PAGE_TITLE = "持倉體檢"
PAGE_ANSWERS = "我手上這些基金，哪幾檔偏離了我自己設的門檻"

# `44` 4.5：時間一律以世界協調時間存放。
STORAGE_TIMEZONE = "UTC"

# `44` HLD-2 規則欄逐字：年化基數為交易日 252（欄位語意 `days_trading`）。
TRADING_DAYS_PER_YEAR = 252

# 每一個數字後面帶的字。草稿逐字要求：「螢幕上每一個數字後面都帶（示意）」。
# 理由寫在草稿 §A：填一個看起來合理的數字、客戶會把它讀成真的，那是線框最容易犯的一種造假。
HINT = "（示意）"

# ⭐ **2026-10-02 hld 接真資料 S3：示意字樣的模式開關**（客戶 2026-10-02 裁示 2-A：正式版全部拿掉，
#    假資料版照舊保留；草稿 `docs/wireframes/draft_hld_live.html` §E P4「由一個模式開關控制」）。
#    開關只有一個入口：`build_page_model(..., demo_hint=)`。本檔每一處接示意字尾的地方一律走 `_hint()`，
#    不直接讀 `HINT` —— 直接讀的那一處，在正式模式下就會漏一個「（示意）」上畫面。
#    ⚠️ 用 `contextvars` 而不是模組層變數：streamlit 每個連線各跑一條執行緒，模組層的全域旗標會互相污染；
#       `ContextVar` 每條執行緒各一份，`build_page_model` 結束時一定還原（`finally`）。
#    預設值是 `HINT` ⇒ 不傳 `demo_hint` 的呼叫端（示範入口、既有測試）輸出逐字不變。
_HINT_SUFFIX = contextvars.ContextVar("hld_hint_suffix", default=HINT)


def _hint() -> str:
    """目前這一次組模型該接的示意字尾：示範模式為 `HINT`，正式模式為空字串。"""
    return _HINT_SUFFIX.get()

# 指標名 → 它住在哪一塊（`44` HLD-7 規則欄：輸出值與該列指標名所在那一塊上顯示的值逐字相同）。
INDICATOR_OWNER = {
    "區間報酬率": "HLD-2",
    "期間波動": "HLD-2",
    "期間配息合計": "HLD-3",
    "配息佔淨值比": "HLD-3",
    "最大回撤": "HLD-8",
    "本金類配息佔比": "HLD-8",
}

# `44` :583（第七輪）：門檻的指標名取 `HLD-1`／`HLD-2`／`HLD-3`／`HLD-8` 四塊各自出的指標。
# ⚠️ `HLD-1` 不另外貢獻名字 —— 它出的是「<指標名> 與門檻的差額」，由門檻自己導出來，會繞回自己。
#    **不替 `44` 發明第七個名字**（登記，不是動工授權）。
RULE_INDICATOR_NAMES = tuple(INDICATOR_OWNER)

# ⚠️ 0 caller。依 `44` §6「**不刪，只標**」保留（上一輪誤刪，本輪復原）。
#    它的四項與現行母體六項**對不上** —— ⛔ 不要拿它當母體用。**登記待裁。**
_RULE_INDICATORS = ("最大回撤", "配息佔淨值比", "區間報酬率", "期間波動")

# 算式的文字寫法（`44` HLD-7：算式以文字寫出，不寫任何實作語言的語法）。
FORMULA_TEXT = {
    "區間報酬率": "區間末單位淨值 ÷ 區間首單位淨值，再減一",
    "期間波動": "日報酬標準差 × 年化基數 252 的平方根",
    "最大回撤": "區間內每一日的單位淨值除以它之前的最高單位淨值，取最小值後減一",
    "期間配息合計": "區間內各筆每單位配息 × 持有單位數，加總",
    "配息佔淨值比": "區間內各筆每單位配息加總，除以區間末單位淨值",
    "本金類配息佔比": "本金類配息金額，除以期間配息合計",
}
_DEVIATION_FORMULA = "該檔的實際值減門檻值"

# `HLD-7` 輸入欄取自淨值列（`metric["nav_rows"]`）的指標；其餘三個指標的輸入欄取自配息列。
# 原本是 `_inputs_text` 裡的一個字面 tuple，S5 第二輪（紅隊必修 M1）原封提出來成具名常數，
# 讓正式模式判斷「哪幾列以淨值為輸入」時讀同一份，不另寫一份清單。值與順序一字未改。
NAV_INPUT_INDICATORS = ("區間報酬率", "期間波動", "最大回撤")


# ───────────────────────── 格式 ─────────────────────────


def format_pct(value: float, *, signed: bool = False) -> str:
    """百分點，小數 2 位（`44` HLD-2 規則欄逐字）。"""
    return f"{value:+.2f}%" if signed else f"{value:.2f}%"


def format_amount(value: float, ccy: str) -> str:
    """原幣金額。逐檔寫出該檔 `ccy` 的字面值（客戶 2026-09-22 設計引導第三條）。"""
    return f"{value:,.2f} {ccy}"


def format_signed_pp(value: float) -> str:
    """`44` 1.2：期間變化以正負號與數字寫出，不配箭頭。"""
    return f"{value:+.2f} pp"


def hinted(text: str) -> str:
    return text + _hint()


def tone_for_state(state: str) -> str:
    """四狀態 → 顏色語意。`44` 5.1 卡片那張表。回傳語意字串，不回色碼。"""
    return _TONE_BY_STATE[state]


def worst_state(states):
    """最差的那一個狀態；**兩者同級時不替 `44` 排先後**，回 `STATE_UNRANKED`。

    `44` :310 只排到 `ok` ＜ {`資料未備`, `業務例外`} ＜ `系統錯誤`。
    最差那一級只有一個成員時照回那個成員；最差那一級同時有 `資料未備` 與 `業務例外` 時
    **沒有答案** —— 回 `STATE_UNRANKED`，不挑一個充數。

    ⚠️ **回傳值與輸入順序無關。** ~~舊版 `max()` 在同級時回「第一個」，那是一個看不見的
       tie-break。~~ → **2026-09-24 就地更正（有意識的更正，不是漏刪；決策者：AI 總管）：
       劃掉那一句是假的，本組實跑推翻。** 在 `a7f8c1b` 上把四狀態的 **69 組 multiset ×
       全部排列**餵進舊 `worst_state`，**零個 order-dependent case** —— 因為舊 `_SEVERITY`
       把那兩個排成不同級，`max()` **從來沒遇過平手**。
       **成立的是上面 `_BAND` 那段註解自己寫的那句**（那個先後是實作發明的、`44` 沒授權）；
       「順序相關」是疊上去的假宣稱。**本函式與順序無關仍然為真**，只是它**不是**第 6 件
       修好的東西，而是本來就這樣。
    ⚠️ 空集回 `資料未備`：本檔既有行為，`44` 未訂（`_build_core_card` 無持倉時整塊沒有主值）。
    ⚠️ **輸入可以含 `STATE_UNRANKED`**（結論燈讀的三塊狀態就可能含它）——
       見 `_band()`。⛔ 這一條是 2026-09-24 稽核抓到的 `KeyError: None` 的修復點。
    """
    if not states:
        return STATE_MISSING
    top = max(_band(s) for s in states)
    tied = {s for s in states if _band(s) == top}
    if len(tied) == 1:
        return next(iter(tied))
    return STATE_UNRANKED


def block_tone(states) -> str:
    """一塊的邊框顏色。**只做呈現，不做嚴重度判定。**

    ⚠️ 為什麼要有這一支：`44` 5.1 現行讀法逐字「**四狀態掛在主值上，不掛在整張卡**」，
    而同小節現行參數表的卡層級只有 `title`／`detail_slot`／`partial_badge` 三個 ——
    **`44` 沒有給卡層級一個狀態，也沒有給卡層級一個顏色**。邊框得有個顏色才畫得出來，
    這一支就是那個實作必需品，**它不宣稱任何一個狀態比另一個嚴重**。
    規則：這一塊的主值裡出現過最顯眼的那個顏色。顏色語意逐值取自 `44` 5.1 那張表。
    ⚠️ **本段的出處，2026-09-24 就地更正（有意識的更正，不是漏刪；決策者：AI 總管）。**
    ~~原寫：`44` 5.5 客戶 2026-09-23 裁示「顏色是介面呈現，嚴重度是判定，兩者正交」。~~
    **那個標成「客戶裁示」的字串不是客戶的字。** `44` :2344-2346 自己就更正過這一筆：
    客戶的原話是「**顏色是 UI 顯示，不是嚴重度；兩者正交**」，而
    「**介面呈現**」與「**嚴重度是判定**」**都不是客戶的字** ——「介面呈現」是總管派工單裡的改寫。
    ⛔ 本檔犯的是 `44` :2347 逐字寫下的那個形狀：「**改寫一次、標成逐字一次，
    兩步各自都小，合起來就是替客戶造話**」。**引了那一段，卻沒讀到它。**
    **現行表述**：客戶的原話是「顏色是 UI 顯示，不是嚴重度；兩者正交」（`44` :2344 轉述），
    本檔據此把兩件事分開 —— 本函式站在「顯示」那一邊，所以它可以排顏色；
    `worst_state()` 站在「嚴重度」那一邊，所以它**不**排 `資料未備` 與 `業務例外`。
    ⚠️ 「站在哪一邊」是**本組的接法**，不是客戶的字。
    """
    tones = {tone_for_state(s) for s in states}
    for tone in ("紅", "黃", "灰"):
        if tone in tones:
            return tone
    return "中性"


def tone_for_block(state, states) -> str:
    """一塊要畫的顏色。

    狀態排得出來 → 照 `44` 5.1 那張表把那個狀態翻成顏色（本檔既有行為，一格未動）。
    排不出來（`資料未備` 與 `業務例外` 同級）→ 才退到 `block_tone()` 看主值的顏色。
    ⚠️ 這樣寫的用意：**拆掉 tie-break 不改變任何一個現行畫面的顏色**，
    改變的只有「這一塊最差的是哪一個狀態」這句宣稱在同級時不再硬答。
    """
    return block_tone(states) if state is STATE_UNRANKED else tone_for_state(state)


def _counts_for_block_state(node) -> bool:
    """這一個主值算不算進塊態。

    只屬於某一檔的取數失敗**不算**（S2 原則：一檔失敗不得讓整塊進 `系統錯誤`）；
    但那張表的逐檔錯誤涵蓋了全部持倉時**照算**，視同表層級（總管 2026-10-02 M3 裁定）。
    ⚠️ 沒有 `fund_errors` 時每一個值都算 ⇒ 塊態與先前逐格相同。
    """
    return not node.get("_fund_scoped_error") or bool(node.get("_fund_error_table_wide"))


def _block_tone_with_errors(state, states) -> str:
    """塊的邊框色。塊裡只要有一個 ⛔ 的值，邊框就是紅（總管 2026-10-02 規格組裁定 5）——
    即使塊態因為「只有一檔失敗」而不是 `系統錯誤`。其餘照 `tone_for_block()`。
    ⚠️ 沒有逐檔錯誤時：有 ⛔ 的值 ⇒ 塊態本來就是 `系統錯誤` ⇒ 本來就是紅，結果一格不變。
    """
    if STATE_ERROR in states:
        return tone_for_state(STATE_ERROR)
    return tone_for_block(state, states)


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


# ───────────────────────── 文案模板（逐字引 `44` 5.5） ─────────────────────────


def empty_source_text(source_keys) -> str:
    return "⬜ 資料未備：" + " 與 ".join(source_keys) + " 尚無資料"


def not_applicable_text(reason: str) -> str:
    return "⬜ 不適用：" + reason


def fetch_failed_text(message: str) -> str:
    """訊息原文照印 —— 不改寫成安撫語句，也不截斷。"""
    return "⛔ 取數失敗：" + message


def fund_fetch_failed_text(fund_code: str, message: str) -> str:
    """某一檔的取數失敗：同一個模板，訊息前面寫出是哪一檔。

    ⚠️ **總管 2026-10-02 裁定的寫法，不是 `44` 的字**：`44` 5.5 的模板只有
       「⛔ 取數失敗：<訊息>」，沒有替「只有一檔失敗」訂寫法。
       訊息原文照印、不截斷，只在它前面加 `<fund_code>：`。
    """
    return fetch_failed_text(f"{fund_code}：{message}")


PRINT_AS_IS_LINE = "訊息原文照印，不改寫成安撫語句。"


def _fund_error_lines(pairs, *, include_table=False) -> list:
    """`(fund_code, 主值節點)` 裡的取數失敗，逐檔寫成一行（去重）。

    預設只收**只屬於某一檔**的（`fund_errors`）；`include_table=True` 連表層級的也收
    （`HLD-1` 卡尾用：計數算進了幾檔，就要列得出幾檔的原因 —— 紅隊建議 3）。
    有任何一行時，尾端補一次「訊息原文照印」。沒有時回空清單 ⇒ 版面一格不變。
    """
    lines = []
    for fund_code, node in pairs:
        if node.get("_fund_scoped_error") or (
            include_table and node["_state"] == STATE_ERROR and node["reason_text"]
        ):
            line = fund_fetch_failed_text(fund_code, node["reason_text"])
            if line not in lines:
                lines.append(line)
    if lines:
        lines.append(PRINT_AS_IS_LINE)
    return lines


def _is_fail_tail_line(line) -> bool:
    """只用在 `HLD-1` 的 `tail_lines` 上：取數失敗那一類的卡尾行 ——
    前導句「⛔ 另有 N 檔…取數失敗，未列入」與其下逐檔的「⛔ 取數失敗：<code>：<原文>」。
    （紅隊建議 2：燈帶上去時要連前導句一起帶，說明燈上的 N 只是下限。）"""
    return line.startswith("⛔")


def partial_range_text(start: str, end: str) -> str:
    return f"缺 {start} 至 {end}"


TEXT_NO_HOLDING = "尚未建立任何持倉"
TEXT_NO_RULES = "尚未設定門檻"
TEXT_NO_DEVIATION = "無偏離項"
TEXT_SHEETS_READONLY = "持倉資料在 Sheets 維護，本儀表板唯讀"
TEXT_GOTO_SHEETS = "前往 Sheets 維護持倉"
TEXT_BAD_RANGE = "起日不晚於迄日"
# S6a-2 第 4 項：門檻列不可套用時「套用」的停用原因。**客戶 2026-10-03 核准的字面，逐字**；改字先回客戶。
TEXT_RULES_BAD = "門檻列未填齊，或格式不符"
# S6a-2 第 3 項：比較方向只收這兩個（`_breaches` 認得的就是這兩個；其他寫法原本被默默當成「沒有超出」，N2）。
RULE_DIRECTIONS = ("低於", "高於")
# HLD-1 卡尾，有檔因缺淨值未列入時的說明行（客戶 2026-10-03 裁示刪去後半句，見 `deviation_rows` 下方 `_build_hld1`）。
HLD1_SKIPPED_NOTE = "未列入的檔不進上表、也不進偏離筆數。"
TEXT_BOTH_EMPTY = "區間兩個欄位皆未填"
TEXT_DIRECT_HOLD = "直接持有"
# HLD-2 說明區的最後一行（示範模式照印）。抽成常數只為了讓 `live.py` 正式模式能逐字比對拿掉它
# （S6a：畫面上的開發過程字句，比照 `ui_v2/set/live.py::_strip_demo` 的體例）；字面一字未改。
HLD2_MOVED_NOTE = "第三個值「最大回撤」已依客戶 2026-09-22 裁定移到層 4 的 HLD-8。"
# 以下三句同理（S6a 第二輪）：抽成常數只為了讓 `live.py` 逐字比對；字面一字未改，示範模式照印。
HLD3_MOVED_NOTE = (
    "第三個值「本金類配息佔比」已依客戶 2026-09-22 裁定移到層 4 的 HLD-8。"
    "配息類別未知的列仍計入期間配息合計。"
)
HLD8_DETAIL_NOTE = (
    "這兩個值原本各是績效與風險卡、配息與本金卡的第三個值；"
    "客戶 2026-09-22 裁定核心卡各留兩個主值，第三個值移到這一層。"
    "兩個值都是比率，逐檔仍寫出幣別字面值，本表沒有任何跨幣別的合計、平均或比值。"
)
HLD0_NO_RULES_ASIDE = "（另：尚未設定門檻。兩句同時成立時哪一句出現，規格沒有寫）"
# HLD-4 說明區講兩枚按鈕的三句（S6a-1：正式版「套用」尚未接線、「存檔」停用，三句都不成立 ⇒ 正式版不印；
# 示範模式照印）。抽成常數只為了讓 `live.py` 逐字比對；字面一字未改。
HLD4_APPLY_NOTE = (
    "兩枚按鈕並存，各做一件事。「套用」只讀這些欄位的當下值、"
    "重算 HLD-1、HLD-2、HLD-3、HLD-5、HLD-7、HLD-8 六塊，"
    "不寫任何資料表、不改欄位的內容。"
)
HLD4_SAVE_NOTE = (
    "「存檔」把當下值寫回使用者設定並更新最後修改時間，不重算任何一塊。"
    "要兩件事都發生就兩枚都按；兩枚的先後不影響結果。"
)
HLD4_SAVE_SCOPE_NOTE = (
    "「存檔」只寫使用者設定，不寫持倉、保單、淨值、配息四張表任何一張，"
    "也不代你填任何值、不把空欄補成任何候選值。"
)

NA_NO_WINDOW = not_applicable_text("尚未設定區間")
NA_NO_RULES = not_applicable_text(TEXT_NO_RULES)
# ⚠️ 下列四個 0 caller，依 `44` §6「不刪，只標」保留：字面值與 `fund_metrics` 裡
#    `not_applicable_text(...)` 是同一句話的第二份來源。**登記待裁。**
#    （`NA_NO_WINDOW`／`NA_NO_RULES` 是 live 的，不在此列。）
NA_FEW_NAV = not_applicable_text("區間內淨值筆數不足")
NA_LATE_INCEPTION = not_applicable_text("成立日晚於區間起點")
NA_NO_DIVIDEND = not_applicable_text("區間內無配息")
NA_UNKNOWN_KIND = not_applicable_text("配息類別未知")
ND_TEXT = "⬜ 資料未備"
# `44` 5.1 卡片表 `業務例外` 那一列的主值字面（`44` :2010）。HLD-1 零列而有檔不適用時用（客戶 2026-10-08 裁示）。
NA_TEXT = "⬜ 不適用"
ERR_TEXT = "⛔ 取數失敗"  # 客戶 2026-09-24 裁示：取數失敗 ⛔（44 第五節第五小節已同步），黃燈仍 ⚠


# ───────────────────────── 算式（純數學） ─────────────────────────


def return_pct(navs) -> float | None:
    """區間報酬率：以區間首末兩筆計算，單位百分點。"""
    if not navs or len(navs) < 2:
        return None
    first = navs[0]
    if math.isclose(first, 0.0, abs_tol=1e-12):
        return None
    return (navs[-1] / first - 1.0) * 100.0


def drawdown_pct(navs) -> float | None:
    """最大回撤：逐日除以之前的最高值，取最小值後減一。"""
    if not navs or len(navs) < 2:
        return None
    peak = navs[0]
    worst = 0.0
    for value in navs:
        peak = max(peak, value)
        if math.isclose(peak, 0.0, abs_tol=1e-12):
            return None
        worst = min(worst, value / peak - 1.0)
    return worst * 100.0


def vol_pct(navs) -> float | None:
    """期間波動：日報酬標準差年化，年化基數為交易日 252。"""
    if not navs or len(navs) < 2:
        return None
    rets = []
    for previous, current in zip(navs, navs[1:]):
        if math.isclose(previous, 0.0, abs_tol=1e-12):
            return None
        rets.append(current / previous - 1.0)
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    variance = sum((r - mean) ** 2 for r in rets) / len(rets)
    return math.sqrt(variance) * math.sqrt(TRADING_DAYS_PER_YEAR) * 100.0


# ───────────────────────── 取數與切片 ─────────────────────────


def pending_tables(dataset) -> frozenset:
    """這一份 dataset 裡**尚未接上**的表名。

    「尚未接上」≠「讀失敗」：接線狀態由資料來源層交給畫面，畫面不自己猜。
    體例同 `ui_v2/alo/source.py`：尚未接上的表給空列表、**不進 `errors`**
    （它把清單放在 `notes["pending_tables"]`，清單來自 L2 `settings_store.PENDING_TABLES`）。
    本頁沒有 `notes` 這一層，`build_page_model()` 只吃 dataset，所以把同一個名字的鍵
    放進 dataset —— ~~這是本頁 dataset **唯一新增的鍵**~~（2026-10-02 S2 起另有 `fund_errors`，
    見 `fund_errors()`；本句在寫下當時為真）。
    ⚠️ 不叫 `pending`：`ui_v2/mkt/source.py` 的 `notes["pending"]` 是「鍵 → 原因代碼」，
       語意不同，同名會讓人以為可以互換。
    ⚠️ 假資料模式**不設**這個鍵（假資料的每一張表都算接上了）⇒ 回空集合，畫面一格不變。
    """
    value = dataset.get("pending_tables")
    if value is None:
        return frozenset()
    # ⛔ 字串也是可迭代的：`frozenset("dividend")` 會被拆成單字元，於是「dividend 未備」
    #    靜默變成「什麼都沒未備」。型別不對一律 raise（§1 Fail Loud），不猜。
    if not isinstance(value, (list, tuple, set, frozenset)):
        raise TypeError(f"pending_tables 必須是表名的集合，收到 {type(value).__name__}：{value!r}")
    bad = [name for name in value if not isinstance(name, str) or not name]
    if bad:
        raise TypeError(f"pending_tables 裡每一項都必須是非空字串，收到：{bad!r}")
    return frozenset(value)


# 逐檔取數的表：接真資料後，淨值與配息是**逐檔**即時取的，會有「某一檔取失敗、其他檔正常」。
FUND_ERROR_TABLES = ("nav", "dividend")


def fund_errors(dataset) -> dict:
    """逐檔取數失敗：`{表名: {fund_code: 錯誤訊息原文}}`，表名只會是 `nav` 或 `dividend`。

    與 `dataset["errors"]`（整張表取數失敗）並存：**表層級優先**，表層級沒有錯時才看逐檔。
    鍵用 `fund_code`：同一檔基金掛在兩張保單下時取數只取一次，失敗也是一起失敗
    （總管 2026-10-02 S2 裁定）。
    ⚠️ 假資料模式**不設**這個鍵 ⇒ 回空 dict，畫面一格不變。
    ⛔ 形狀不對一律 raise（§1 Fail Loud），體例同 `pending_tables()`：
       不猜、不吞、不把壞掉的形狀讀成「沒有失敗」。
    """
    value = dataset.get("fund_errors")
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError(
            f"fund_errors 必須是 {{表名: {{fund_code: 訊息}}}}，收到 {type(value).__name__}：{value!r}"
        )
    # 比對用持倉 `fund_code` 的**原值**，不做大小寫或空白正規化（總管 2026-10-02 J2 裁定）。
    held = {h["fund_code"] for h in dataset.get("holding", [])}
    out = {}
    for table, per_fund in value.items():
        if table not in FUND_ERROR_TABLES:
            raise ValueError(
                f"fund_errors 的表名只能是 {FUND_ERROR_TABLES!r} 之一，收到：{table!r}"
            )
        if not isinstance(per_fund, dict):
            raise TypeError(
                f"fund_errors[{table!r}] 必須是 {{fund_code: 訊息}}，"
                f"收到 {type(per_fund).__name__}：{per_fund!r}"
            )
        bad = [
            (code, message)
            for code, message in per_fund.items()
            if not isinstance(code, str) or not code
            # 只有空白的訊息（例如 "   "）等於沒有訊息：先 strip 再判（總管 2026-10-02 裁定）。
            or not isinstance(message, str) or not message.strip()
        ]
        if bad:
            raise TypeError(
                f"fund_errors[{table!r}] 的 fund_code 與訊息都必須是非空字串，收到：{bad!r}"
            )
        # 點名持倉以外的代碼 ⇒ raise（總管 2026-10-02 J2 裁定，客戶已確認）：
        # 上游與持倉對不上，靜默略過等於把一筆失敗吞掉（§1）。
        stray = sorted(code for code in per_fund if code not in held)
        if stray:
            raise ValueError(
                f"fund_errors[{table!r}] 點名了持倉裡沒有的 fund_code：{stray!r}"
            )
        out[table] = dict(per_fund)
    return out


def _rows_for(dataset, table, fund_code):
    return [row for row in dataset.get(table, []) if row["fund_code"] == fund_code]


def _in_window(rows, key, window):
    start, end = window
    if not start or not end:
        return []
    return sorted(
        (row for row in rows if start <= row[key] <= end), key=lambda row: row[key]
    )


def _setting(dataset, key):
    for row in dataset.get("user_setting", []):
        if row["setting_key"] == key:
            return row["setting_value"]
    return None


def saved_window(dataset):
    return (_setting(dataset, "hld_window_start"), _setting(dataset, "hld_window_end"))


def saved_rules(dataset):
    return list(_setting(dataset, "hld_deviation_rules") or ())


# S6a 第四輪（紅隊 M4）：區間只收嚴格的 `YYYY-MM-DD`（`re.ASCII`：`\d` 只認 0～9）。
# 3.11 的 `date.fromisoformat` 也收 `20260601`、`2026-W23-1` 這類寫法 —— 原本 `20260601` 被當成合法，
# 結果算出「區間內淨值筆數不足」這種錯的結論。先過這一關再交給 `fromisoformat`（同 `live._DATE_ONLY` 的寫法）。
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}", re.ASCII)


def window_is_valid(window) -> bool:
    start, end = window
    if not start or not end:
        return False
    if not all(isinstance(v, str) and _ISO_DATE.fullmatch(v) for v in (start, end)):
        return False
    try:
        return date.fromisoformat(start) <= date.fromisoformat(end)
    except ValueError:
        return False


# ── 「套用」讀欄位當下值（S6a 第三、四輪；`44` HLD-4：「套用」只讀這些欄位的當下值、重算六塊）──
# 門檻列的數值欄只收十進位寫法（可帶正負號、可帶小數），前後不得有空白；不收 `1e3`、`inf`、`1_0`。
_RULE_NUMBER = re.compile(r"[+-]?\d+(\.\d+)?", re.ASCII)


def rules_from_inputs(rows):
    """門檻列欄位的當下值 `[(指標名, 比較方向, 數值), ...]` → `[{"indicator", "direction", "value"}, ...]`。

    - 三格全空的列 ＝ 沒有這一列（`_build_hld4` 本來就用一列空白列表示「門檻一列也沒有」）；
    - 指標名照原字收 —— 母體之外的指標名照 `deviation_rows` 既有的處理（未列入）；
    - 比較方向只收 `RULE_DIRECTIONS`（S6a-2 第 3 項，N2：其他寫法原本被 `_breaches` 默默當成沒有超出）；
    - 數值轉成數（存過的門檻就是數，`_breaches` 拿它直接比大小），只收有限的數
      （S6a-2 第 4 項：位數超長的十進位寫法 `float()` 之後是 inf，一律不收）。
    其餘（只填了一兩格、方向不是那兩個、數值不合格）→ 回 None，由呼叫端讓「套用」不可按，
    原因句 `TEXT_RULES_BAD`。
    """
    out = []
    for row in rows:
        indicator, direction, value = ("" if v is None else v for v in row)
        if not isinstance(indicator, str) or not isinstance(direction, str) or not isinstance(value, str):
            return None
        if indicator == "" and direction == "" and value == "":
            continue
        if indicator == "" or direction not in RULE_DIRECTIONS or not _RULE_NUMBER.fullmatch(value):
            return None
        number = float(value)
        if not math.isfinite(number):
            return None
        out.append({"indicator": indicator, "direction": direction, "value": number})
    return out


def window_input_blocked(start, end) -> bool:
    """區間兩格的當下值能不能拿去「套用」：兩格都空 → 可以（＝尚未設定區間，既有行為）；
    只填一格、格式不是 `YYYY-MM-DD`、起日晚於迄日 → 不可以（S6a 第四輪，紅隊 M4 與建議 2）。"""
    if not start and not end:
        return False
    return not window_is_valid((start, end))


def applied_from_inputs(start, end, rule_rows):
    """按「套用」時欄位的當下值 → `{"window": (起, 迄), "rules": [...]}`；不可套用回 None。
    `page.py` 的「套用」回呼與 `_build_hld4` 的停用判定**讀同一支**，兩邊不會各說各話。"""
    if window_input_blocked(start, end):
        return None
    rules = rules_from_inputs(rule_rows)
    if rules is None:
        return None
    return {"window": (start or None, end or None), "rules": rules}


# ───────────────────────── 逐檔指標 ─────────────────────────


def main_value_state(*, error=None, missing=False, na_reason=None) -> str:
    """一個主值的四狀態。`44` 5.1：四狀態掛在主值上，不掛在整張卡。

    順序刻意是「失敗 → 缺 → 不適用 → ok」：取數失敗比缺資料更該說出來（§1 Fail Loud）。
    """
    if error:
        return STATE_ERROR
    if missing:
        return STATE_MISSING
    if na_reason:
        return STATE_BIZ
    return STATE_OK


def _metric(
    value, *, text, ccy, error=None, missing=False, na_reason=None, label="",
    fund_scoped=False, table_wide=False,
):
    state = main_value_state(error=error, missing=missing, na_reason=na_reason)
    if state == STATE_OK:
        shown = text
    elif state == STATE_MISSING:
        shown = ND_TEXT
    elif state == STATE_BIZ:
        shown = na_reason
    else:
        shown = ERR_TEXT
    node = {
        "_value_node": True,
        "_state": state,
        "_tone": tone_for_state(state),
        "_has_number": state == STATE_OK,
        "_ccy": ccy,
        "_raw": value if state == STATE_OK else None,
        "label": label,
        "text": shown,
        "value_text": shown,
        "reason_text": (error or "") if state == STATE_ERROR else "",
    }
    # 這一個 `系統錯誤` 只屬於這一檔（`fund_errors`），不是整張表。塊層級讀它來決定
    # 「一檔失敗不讓整塊進 `系統錯誤`」與「錯誤原因寫出是哪一檔」。
    # ⚠️ 只在真的是逐檔錯誤時才放這個鍵 —— 沒有 `fund_errors` 時，節點與先前逐鍵相同。
    if fund_scoped and state == STATE_ERROR:
        node["_fund_scoped_error"] = True
        # 這張表的逐檔錯誤涵蓋了**全部持倉**：塊態一律視同表層級錯誤（總管 2026-10-02 M3 裁定），
        # 免得「一欄全失敗」與「整表失敗」畫出不同的燈。
        if table_wide:
            node["_fund_error_table_wide"] = True
    return node


# 📌 2026-10-05「讀取失敗不說空」：`window_error` ＝ 設定讀取失敗的原文，~~只在區間取自存過的設定時才給~~
#    → 只在區間未知時才給：區間取自存過的設定，或套用的區間兩格都空
#    （見 `_build_page_model`）。六個值一律排在表層級與逐檔錯誤之後判成 `系統錯誤`，不判成「⬜ 不適用：尚未設定區間」。
#    六個都要改：`HLD-7` 的輸出欄要與值所在那一塊上的字串相同（`44` :733）。
#    劃線那一處是 2026-10-05 的更正（有意識的更正，不是漏刪；決策者：總管；稽核乙 M-1：設定讀取失敗時，空白套用仍算未知）。
def fund_metrics(dataset, fund, window, *, window_error=None):
    """一檔在一段區間內的六個指標。**所有卡與所有表都讀這一份**，
    這樣 `44` HLD-7 判準要的「軌跡與所在那一塊逐字相同」才是由構造保證的。"""
    code = fund["fund_code"]
    ccy = fund["ccy"]
    errors = dataset.get("errors", {})
    # 表層級優先；表層級沒有錯時，才看這一檔有沒有逐檔錯誤（總管 2026-10-02 S2 裁定）。
    # 逐檔錯誤一樣走 `main_value_state()` 進 `系統錯誤`，只多標一個「只屬於這一檔」。
    per_fund = fund_errors(dataset)
    nav_error = errors.get("nav")
    nav_fund_scoped = False
    if not nav_error:
        nav_error = per_fund.get("nav", {}).get(code)
        nav_fund_scoped = bool(nav_error)
    div_error = errors.get("dividend")
    div_fund_scoped = False
    if not div_error:
        div_error = per_fund.get("dividend", {}).get(code)
        div_fund_scoped = bool(div_error)
    held = {h["fund_code"] for h in dataset.get("holding", [])}
    table_wide = {t for t, codes in per_fund.items() if held and held <= set(codes)}
    nav_wide = nav_fund_scoped and "nav" in table_wide
    div_wide = div_fund_scoped and "dividend" in table_wide

    pending = pending_tables(dataset)
    # `fund_profile` 尚未接上 ⇒ **不讀**它（總管 2026-10-02 S2 裁定）。改用下面的
    # `nav_starts_late` 推定規則；讀一張還沒接上的表，等於拿不存在的成立日去下判斷。
    profile = None if "fund_profile" in pending else next(
        (p for p in dataset.get("fund_profile", []) if p["fund_code"] == code), None
    )
    start, end = window
    has_window = window_is_valid(window)

    nav_rows = _in_window(_rows_for(dataset, "nav", code), "nav_date", window)
    navs = [row["nav_orig_ccy"] for row in nav_rows]
    all_nav_rows = _rows_for(dataset, "nav", code)

    late = bool(
        profile and start and profile.get("inception_on") and profile["inception_on"] > start
    )

    # `fund_profile` 尚未接上時的推定規則：這一檔在 `nav` 表裡（**不限區間**）最早的
    # `nav_date` 晚於區間起點 ⇒ 區間報酬率／期間波動／最大回撤判 `⬜ 資料未備`。
    # ⛔ 不寫「不適用：成立日晚於區間起點」：分不出是成立日晚、還是來源只給到那麼舊，
    #    所以只能說資料未備（總管 2026-10-02 S2 裁定）。
    # ⛔ **不重用 `nav_missing`**：那一個的意思是「一列都沒有」，`HLD-1` 的
    #    「缺淨值」卡尾與 `HLD-5` 讀它；這一檔表裡有淨值，只是不夠舊。
    nav_starts_late = bool(
        "fund_profile" in pending
        and has_window
        and all_nav_rows
        and min(row["nav_date"] for row in all_nav_rows) > start
    )

    def nav_na():
        if not has_window:
            return "尚未設定區間"
        if late:
            return "成立日晚於區間起點"
        if len(navs) < 2:
            return "區間內淨值筆數不足"
        return None

    nav_missing = bool(has_window and not all_nav_rows)
    nav_value_missing = nav_missing or nav_starts_late
    na_nav = None if nav_value_missing else nav_na()
    na_nav_text = not_applicable_text(na_nav) if na_nav else None

    ret = return_pct(navs)
    vol = vol_pct(navs)
    draw = drawdown_pct(navs)

    div_rows = _in_window(_rows_for(dataset, "dividend", code), "ex_date", window)
    per_unit_total = sum(row["div_per_unit_orig_ccy"] for row in div_rows)
    units = fund["units_shares"]
    div_total = per_unit_total * units
    nav_last = navs[-1] if navs else None
    unknown_rows = [row for row in div_rows if row["div_kind"] == "unknown"]
    principal_sum = sum(
        row["div_per_unit_orig_ccy"] for row in div_rows if row["div_kind"] == "principal"
    )

    def div_na():
        if not has_window:
            return "尚未設定區間"
        if not div_rows:
            return "區間內無配息"
        return None

    # 整張 `dividend` 表**尚未接上** ⇒ 每一檔的配息值都是 `⬜ 資料未備`，不是「區間內無配息」。
    # 訊號是 dataset 的 `pending_tables`（表層級，見 `pending_tables()`）。
    # ⛔ **不看「這一檔在表裡有沒有列」**：累積型基金本來就不配息，表已接上時它一列也沒有，
    #    `44` HLD-3 空狀態欄給它的就是「⬜ 不適用：區間內無配息」。逐檔用「零列」判缺，
    #    會把累積型基金報成資料未備（總管 2026-10-02 第 2 輪裁定）。
    #    「某一檔的配息列被轉換規則丟掉」這種逐檔情形本輪不處理 —— 要等 L2 能交出
    #    「被略過的列」才分得出來，登記到轉換層那一輪。
    # 依據：`44` 5.5 `來源缺` 的觸發條件「這一塊依賴的來源一筆資料也沒有」，主值位置顯示
    # `⬜ 資料未備`（與 `HLD-3` 空狀態欄「區間末無淨值 → 佔比顯示 `⬜ 資料未備`」同一個字面值）。
    # ⚠️ 區間未設時照舊「尚未設定區間」（與 `nav_missing` 同一個形狀）；
    #    取數失敗照舊由 `main_value_state()` 先判成 `系統錯誤`。
    div_missing = bool(has_window and "dividend" in pending)
    na_div = None if div_missing else div_na()
    na_div_text = not_applicable_text(na_div) if na_div else None

    # 配息佔淨值比：`44` 寫「期間配息除以區間末 `nav_orig_ccy`」。
    # ⚠️ 登記（量綱，`44` 沒有講清楚）：`期間配息合計` 是**金額**，而 `nav_orig_ccy` 是
    #    **每單位淨值**，兩者相除得到的是**單位數**，不是百分點。
    #    唯一能得到百分點的讀法是「**每單位配息加總** ÷ 區間末每單位淨值」——
    #    它與「合計 ÷ 區間末淨值 × 持有單位數」同值。本檔取這一種，**不自行改規格**。
    yield_na = na_div
    if yield_na is None and nav_last is None:
        yield_value = None
    else:
        yield_value = (per_unit_total / nav_last * 100.0) if nav_last else None

    if div_error:
        yield_error, yield_fund_scoped, yield_wide = div_error, div_fund_scoped, div_wide
    else:
        yield_error, yield_fund_scoped, yield_wide = nav_error, nav_fund_scoped, nav_wide

    principal_na = na_div
    if principal_na is None and unknown_rows:
        principal_na = "配息類別未知"
    principal_value = (
        (principal_sum / per_unit_total * 100.0)
        if per_unit_total and not principal_na
        else None
    )

    return {
        "_fund_code": code,
        # `HLD-5` 用它找回**這一筆**持倉、也用它當展開鍵。`44` 4.1：`holding` 的主鍵是
        # `holding_id`；同一檔基金可以掛在不同保單下（業務唯一鍵是（`policy_id`, `fund_code`）），
        # 只拿 `fund_code` 找會讓同基金的兩列互相蓋掉。
        # ⚠️ 依賴 `build_page_model()` 開頭的 `_check_holding_ids()`：走到這裡它已經是非空字串。
        "_holding_id": fund["holding_id"],
        "_ccy": ccy,
        "fund_name": fund["fund_name"],
        "units_shares": units,
        "nav_rows": nav_rows,
        "div_rows": div_rows,
        "unknown_count": len(unknown_rows),
        "nav_missing": nav_missing,
        # `fund_profile` 尚未接上時的推定（見上）。與 `nav_missing` 分開，理由同上。
        "nav_starts_late": nav_starts_late,
        "div_missing": div_missing,
        "區間報酬率": _metric(
            ret,
            text=hinted(format_pct(ret, signed=True)) if ret is not None else "",
            ccy=ccy,
            error=nav_error or window_error,
            missing=nav_value_missing,
            na_reason=na_nav_text,
            fund_scoped=nav_fund_scoped,
            table_wide=nav_wide,
            label="區間報酬率",
        ),
        "期間波動": _metric(
            vol,
            text=hinted(format_pct(vol)) if vol is not None else "",
            ccy=ccy,
            error=nav_error or window_error,
            missing=nav_value_missing,
            na_reason=na_nav_text,
            fund_scoped=nav_fund_scoped,
            table_wide=nav_wide,
            label="期間波動",
        ),
        "最大回撤": _metric(
            draw,
            text=hinted(format_pct(draw)) if draw is not None else "",
            ccy=ccy,
            error=nav_error or window_error,
            missing=nav_value_missing,
            na_reason=na_nav_text,
            fund_scoped=nav_fund_scoped,
            table_wide=nav_wide,
            label="最大回撤",
        ),
        "期間配息合計": _metric(
            div_total,
            text=hinted(format_amount(div_total, ccy)),
            ccy=ccy,
            error=div_error or window_error,
            missing=div_missing,
            na_reason=na_div_text,
            label="期間配息合計",
            fund_scoped=div_fund_scoped,
            table_wide=div_wide,
        ),
        "配息佔淨值比": _metric(
            yield_value,
            text=hinted(format_pct(yield_value)) if yield_value is not None else "",
            ccy=ccy,
            # 分母是區間末淨值 ⇒ `nav` 取數失敗也讓它進 `系統錯誤`，不是 `資料未備`
            # （總管 2026-10-02 J1 裁定）。兩張都失敗時印配息那一句（本值掛在配息卡上）。
            error=yield_error or window_error,
            missing=bool(
                nav_missing or div_missing or (na_div is None and nav_last is None)
            ),
            na_reason=na_div_text,
            label="配息佔淨值比",
            fund_scoped=yield_fund_scoped,
            table_wide=yield_wide,
        ),
        "本金類配息佔比": _metric(
            principal_value,
            text=hinted(format_pct(principal_value)) if principal_value is not None else "",
            ccy=ccy,
            error=div_error or window_error,
            missing=div_missing,
            na_reason=not_applicable_text(principal_na) if principal_na else None,
            label="本金類配息佔比",
            fund_scoped=div_fund_scoped,
            table_wide=div_wide,
        ),
    }


def all_metrics(dataset, window, *, window_error=None):
    funds = sorted(dataset.get("holding", []), key=lambda h: h["fund_code"])
    return [fund_metrics(dataset, fund, window, window_error=window_error) for fund in funds]


# ───────────────────────── 徽章與按鈕 ─────────────────────────


def status_badge(text: str) -> dict:
    if text not in STATUS_BADGE_LITERALS:
        raise ValueError(f"狀態徽章字面值 {text!r} 不在 `44` 5.2 的七個之內")
    return {"_kind": "狀態", "_tone": "灰" if text == "資料未備" else "黃", "text": text}


def source_badge(tier: str) -> dict:
    """`44` 5.2：來源徽章中性、不著色。"""
    return {"_kind": "來源", "_tone": "中性", "text": tier}


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


def _retry_button() -> dict:
    return _button("重新取數", "取數")


# `44` 各塊「來源」欄逐字點名的資料表。**來源欄的行號是 `44` :513／:531／:542。**
#
# ⚠️ **2026-09-24 就地更正兩件事（有意識的更正，不是漏刪；決策者：AI 總管；稽核抓到）**：
# **(1) 行號指錯。** ~~原寫 `44` :515／:529／:543~~ —— 那三個分別是 `HLD-1` 的**空狀態**欄、
#     `HLD-2` 的**表頭**、`HLD-3` 的**規則**欄，**沒有一個是來源欄**。已逐行重讀改正。
# **(2) 自稱「逐字取」卻漏了兩張表。** ~~原本 `HLD-2` 只收 `nav`、`HLD-3` 只收
#     `dividend`／`nav`~~，而來源欄逐字還列了 `HLD-2` 的 **`fund_profile.inception_on`**
#     與 `HLD-3` 的 **`holding.units_shares`**。原本的自述**只解釋了 `user_setting`**，
#     那兩張是**無理由漏掉**的。
#     **行為後果（稽核實測）**：空持倉 ＋ `errors={"holding"}` 時 `HLD-1` 進 `系統錯誤`
#     而 `HLD-3` 仍是 `資料未備` —— 兩塊都把 `holding` 寫在來源欄裡，卻不同調。
#     **本輪補齊，讓自述為真。**
# ⛔ **不准留一個自稱抄寫、實際是判斷的東西** —— 現在這張表**真的是**來源欄的逐字子集，
#    唯一的篩選規則寫在下一行，而且那條規則自己說得出理由。
# ⚠️ ~~**唯一的篩選**：只收「取數取回來的表」。`user_setting` 三塊都列了，但它是**使用者自己
#    輸入的**，不經取數，所以取數失敗與它無關。**這是本組的判斷，不是 `44` 的字。**~~
# → 📌 **2026-10-05「讀取失敗不說空」：篩選拿掉，三塊各收 `user_setting`，排在最後**
#    （有意識的政策變更，不是漏刪；決策者：客戶 2026-10-05 裁示「設定讀取失敗顯示『⛔ 取數失敗：<原文>』」
#    與「`BLOCK_SOURCE_TABLES` 加 `user_setting`」）。
#    **舊表述在寫下當時撐得住**：設定值確實是使用者自己輸入的。**被權衡掉的是「不經取數」**：
#    正式模式的設定是讀表讀回來的，讀不到時 `errors["user_setting"]` 帶原文
#    （`live.assemble_live_load`、`live.parse_user_settings`），與其他來源表一樣會取數失敗。
#    現在這張表與來源欄點名的表相同、沒有篩選（A3 守衛那一條測試守著）。
#    排在最後：來源欄三格都把 `user_setting` 列在最後；`source_error()` 依這個次序回第一個失敗。
BLOCK_SOURCE_TABLES = {
    "HLD-1": ("holding", "nav", "user_setting"),
    "HLD-2": ("nav", "fund_profile", "user_setting"),
    "HLD-3": ("dividend", "nav", "holding", "user_setting"),
}


def source_error(dataset, code):
    """這一塊的來源表有沒有取數失敗；有就回訊息原文，沒有回 None。

    `44` 5.5 `系統錯誤` 觸發條件逐字：「**取數或計算本身失敗**」——
    來源整張表取數失敗，就是這一種，與這一頁有沒有持倉無關。

    ⚠️ ~~**一筆沒登記的不對稱，2026-09-24 稽核指出，就地登記（不處置）**：
    本函式的回傳值**只有 `not has_holdings` 那一支用得到**。有持倉時，
    `nav`／`dividend` 的失敗會經由 `fund_metrics()` 逐值浮出來，但
    **`holding` 與 `fund_profile` 的失敗沒有任何一條路會浮出來** ——
    於是同一個來源掛掉，**資料多的時候反而比較不警戒**
    （有持倉時 `HLD-1` 是 `ok`，空持倉時是 `系統錯誤`）。
    ⛔ **本輪不處置**：補那條路等於讓有持倉的情境也開始變紅，
    那是行為擴張，**客戶只裁了空持倉那一種畫面**。**登記，待客戶裁決。**~~
    → ✅ **2026-09-24 客戶裁示補那條路（有意識的政策變更，不是漏刪；決策者：客戶）。**
    **上面那段的事實描述全部成立、一字未被推翻** —— 被權衡掉的只有它的處置
    （「不處置、待裁」）。**裁決已經下來了，所以待裁那一句過期了。**
    新路走 `unsurfaced_source_error()`，射程寫在那一支的 docstring 裡。
    ⚠️ **本函式自己一格未動** —— 它仍然只服務 `not has_holdings` 那一支。
    """
    errors = dataset.get("errors", {})
    for table in BLOCK_SOURCE_TABLES[code]:
        if errors.get(table):
            return errors[table]
    return None


# 有持倉時，這兩張表的取數失敗**本來就有一條路浮得出來**：`fund_metrics()` 逐值讀
# `errors["nav"]`／`errors["dividend"]`，失敗會變成該值的 `系統錯誤`，
# 再由核心卡與 `HLD-8` 把訊息原文印出來。
# ⚠️ **這兩個名字不是憑印象列的** —— 逐表注入一個錯誤實測出來的，
#    而且那個實測本身就是一條測試（見 `test_哪些來源表在有持倉時本來就浮得出來`），
#    所以日後 `fund_metrics()` 改讀別的鍵，這張清單會**紅燈**，不會靜默過期。
_SURFACED_PER_VALUE = ("nav", "dividend")
# 📌 2026-10-02 S2：逐檔取數失敗（`fund_errors`）只會點名這兩張表（`FUND_ERROR_TABLES`），
#    而它們本來就逐值浮出 ⇒ `source_error()`／`unsurfaced_source_error()` **一格未動**，
#    逐檔錯誤不經這兩支（否則一檔失敗就會讓整塊進 `系統錯誤`，違反 S2 原則）。
#    空持倉時沒有任何一檔可掛 ⇒ 逐檔錯誤無處可浮，這是本來就成立的（形狀照樣先驗）。


def unsurfaced_source_error(dataset, code):
    """有持倉時，這一塊的來源表裡**沒有任何其他路會浮出來**的那種取數失敗。

    ⭐ **2026-09-24 客戶裁示新增（第 2 件）。射程就在這裡，寫死，不得外推：**

    **補的是**：有持倉時，來源表取數失敗而**現行一條路也沒有**的那幾張
    （實測為 `holding` 與 `fund_profile`），現在會讓該塊進 `系統錯誤`
    並把訊息原文印進說明區。
    **要修掉的病**（上一輪登記的原話）：同一個來源掛掉，
    **資料多的時候反而比較不警戒**。

    ⛔ **不補、而且一格未動的**（逐條列出來，免得日後被人讀成授權）：
      · `44` 的四狀態、五塊模板、任何一塊的空狀態欄 —— **一個字未動**；
      · `not has_holdings` 那兩支（空持倉）的行為 —— **一格未動**，
        它們照舊走 `source_error()`；
      · `conclusion_light()` 的早退次序 —— **一格未動**。燈變紅不是本件改的，
        是 `44` :489 本來就寫「任一塊為 `系統錯誤` → 燈為紅」，
        本件只是讓更多情形**合法地**進 `系統錯誤`；
      · `BLOCK_SOURCE_TABLES` 與它的 A3 守衛 —— **一格未動**；
      · 主值層的逐值判定 —— **一格未動**。本件只動塊層的 `_state` 與說明區；
      · 那三塊照舊**不掛**「重新取數」按鈕（客戶 2026-09-23 裁示）；
      · `HLD-7`／`HLD-8` 不在本件射程 —— `BLOCK_SOURCE_TABLES` 沒有它們的來源表，
        替它們編一組就是造規格。**登記，不處置。**

    📌 **2026-10-05「讀取失敗不說空」改了上面三項**（客戶 2026-10-05 核准開工）。上面各句說的是
    2026-09-24 那一件，在當時為真，一字未改：
      · `not has_holdings` 那兩支：持倉表讀取失敗時不再接「尚未建立任何持倉」；
      · `BLOCK_SOURCE_TABLES` 三塊各收 `user_setting`，A3 守衛的篩選拿掉；
      · 主值層：設定讀取失敗、~~區間取自存過的設定時~~ → 區間未知時（區間取自存過的設定，或套用的區間兩格都空），
        六個值一律判成 `系統錯誤`（`fund_metrics()` 的 `window_error`）。
    `user_setting` 不在 `_SURFACED_PER_VALUE`：~~按過「套用」之後主值照算~~ → 套用的區間有值時主值照算，
    本支照樣把設定讀取失敗印進說明區。
    （兩處劃線：2026-10-05 更正，有意識的更正，不是漏刪；決策者：總管；稽核乙 M-1 —— 設定讀取失敗時，空白套用仍算未知。）

    **`系統錯誤` 這個狀態的依據**：`44` 5.5 該狀態的觸發條件逐字是
    「**取數或計算本身失敗**」—— 來源整張表取數失敗就是這一種，
    **這一句與這一頁有沒有持倉無關**。⇒ 本件不是新規則，
    是把一條既有規則補到它原本被無理由排除掉的那一半。
    ⚠️ **與 `source_error()` 的差別只有一處**：本支跳過 `_SURFACED_PER_VALUE`，
       免得同一個失敗被印兩次（一次逐值、一次整塊）。
    """
    errors = dataset.get("errors", {})
    for table in BLOCK_SOURCE_TABLES[code]:
        if table in _SURFACED_PER_VALUE:
            continue
        if errors.get(table):
            return errors[table]
    return None


def blocks_recalculated_by(action_kind: str) -> tuple:
    """`44` HLD-4：「套用」重算六塊；「存檔」不重算任何一塊。"""
    return APPLY_RECALC_BLOCKS if action_kind == "套用" else ()


# ───────────────────────── HLD-1 偏離提示卡 ─────────────────────────


def _breaches(rule, value) -> bool:
    if rule["direction"] == "低於":
        return value < rule["value"]
    if rule["direction"] == "高於":
        return value > rule["value"]
    return False


def deviation_rows(metrics, rules):
    """逐檔算出門檻所指的值，只列出超出門檻的檔。

    回傳 (列, 未列入的原因統計)。缺淨值的檔**不進本表、不佔一列、不計入列數**
    （客戶 `H-01` 裁示；`44` HLD-1 空狀態 2026-09-22 改寫）。
    """
    rows = []
    skipped = {"missing": set(), "missing_other": set(), "error": set(), "na": set()}
    for metric in metrics:
        for rule in rules:
            name = rule["indicator"]
            if name not in RULE_INDICATOR_NAMES:
                # `44` :583 自第七輪起給了母體，草稿 ⛔ H-12「沒有候選清單」已為假、已撤。
                # 母體之外的名字仍然**不猜**，照舊登記成一種未列入。
                skipped["na"].add(metric["_fund_code"])
                continue
            node = metric[name]
            if node["_state"] == STATE_ERROR:
                skipped["error"].add(metric["_fund_code"])
                continue
            if node["_state"] == STATE_MISSING:
                # 「缺淨值」＝這一檔在 `nav` 表裡一列也沒有（`nav_missing`，不限區間）——
                # `44` HLD-1 判準逐字「把某一檔的淨值整個抽掉」。
                # ⛔ 不看區間內切片 `nav_rows`：表裡有淨值、只是區間內剛好沒有的檔，
                #    不是缺淨值（紅隊 2026-10-02 指出）。
                if metric["nav_missing"]:
                    skipped["missing"].add(metric["_fund_code"])
                else:
                    # 其他原因的 `資料未備`（配息表尚未接上；區間內一筆淨值都沒有，配息佔淨值比沒有分母）。
                    # ⚠️ 登記：`44` HLD-1 空狀態欄只替「缺淨值」寫了卡尾那一行，這一種沒有，
                    #    本檔不發明卡尾文案。它在 `_build_hld1` 裡被讀：零列時不得宣稱「無偏離項」。
                    skipped["missing_other"].add(metric["_fund_code"])
                continue
            if node["_state"] == STATE_BIZ:
                skipped["na"].add(metric["_fund_code"])
                continue
            if not _breaches(rule, node["_raw"]):
                continue
            delta = node["_raw"] - rule["value"]
            rows.append(
                {
                    "_fund_code": metric["_fund_code"],
                    "_indicator": name,
                    # 軌跡上的指標名刻意與 HLD-8 的「最大回撤」分開 ——
                    # 門檻可以拿任何一個指標來比，同名會讓 `44` HLD-7 那一行判準
                    # 分不出「這一列的值該去哪一塊對」。
                    "trace_indicator": f"{name} 與門檻的差額",
                    "_ccy": metric["_ccy"],
                    "_value_node": True,
                    "_state": STATE_OK,
                    "_tone": "中性",
                    "_has_number": True,
                    "fund_name": metric["fund_name"],
                    "actual_text": node["text"],
                    "threshold_text": hinted(format_pct(rule["value"])),
                    "delta_text": hinted(format_signed_pp(delta)),
                    "text": hinted(format_signed_pp(delta)),
                }
            )
    rows.sort(key=lambda row: (row["_fund_code"], row["_indicator"]))
    # 取數失敗的那一檔**只算「取數失敗」**，不再同時算進缺淨值／其他缺漏／不適用
    # （總管 2026-10-02 J1 裁定）：同一檔進兩類，卡尾的計數會加總超過持倉檔數。
    for kind in ("missing", "missing_other", "na"):
        skipped[kind] -= skipped["error"]
    return rows, skipped


def _missing_other_lines(metrics, missing_other, pending) -> list:
    """門檻指標 `資料未備`（不是缺淨值）的原因，只用 `44` 已宣告的顯示文案。

    唯一寫得出的原因：配息表尚未接上 → `44` 5.5 `來源缺` 模板
    `⬜ 資料未備：<來源鍵> 尚無資料`，**來源鍵只列 `dividend`**。
    ⛔ 不取 `pending` 與 `HLD-3` 全部來源的交集：`pending` 也點名 `nav` 時，那一句會變成
       「dividend 與 nav 尚無資料」，而這裡的資料未備跟 `nav` 無關（紅隊 2026-10-02 重現）。
    ⚠️ 另一種原因（配息佔淨值比在區間內一筆淨值都沒有、沒有分母）`44` 沒有宣告顯示文案，
       這一支不寫原因，只留主值的 `⬜ 資料未備`（總管 2026-10-02 第五輪裁定；原因句另案改 `44`）。
    ⭐ **2026-10-02 S2 增補**：~~唯一寫得出的原因~~ 現在有第二個 —— `fund_profile` 尚未接上，
       某檔在 `nav` 表裡最早的淨值晚於區間起點（`nav_starts_late`）→ 同一個模板，
       **來源鍵只列 `fund_profile`**（總管 S2 裁定，比照 `dividend` 那一支）。
       兩句各自成行、各自只列自己那一個來源鍵，理由同上（不取交集、不合併成一句）。
    """
    hit = [m for m in metrics if m["_fund_code"] in missing_other]
    lines = []
    if "dividend" in pending and any(m["div_missing"] for m in hit):
        lines.append(empty_source_text(["dividend"]))
    if "fund_profile" in pending and any(m["nav_starts_late"] for m in hit):
        lines.append(empty_source_text(["fund_profile"]))
    return lines


def _is_missing_reason_line(line) -> bool:
    return line.startswith(ND_TEXT + "：")


def _build_hld1(
    metrics, rules, *, has_holdings, fail_message=None, unsurfaced=None, pending=frozenset(),
    settings_error=None, rules_unknown=False, holding_unknown=False,
):
    badges = [_redline_badge("G2†")]
    # ⛔ **本塊不掛「重新取數」按鈕**（客戶 2026-09-23 裁示；有意識的政策變更，不是漏刪）。
    # `44` :515 本塊空狀態欄**一個按鈕也沒有寫**，而 `44` 5.5「各塊自己寫的優先於本表模板」
    # 同輪補的分句逐字：「**一塊的空狀態欄整格為準：那一格沒有寫出按鈕，
    # 該塊的那個空狀態畫面上就沒有按鈕，不回退成本表模板裡的那一枚**」。
    # 決定性理由（`44` :2420 逐字）：缺的不是來源、是使用者還沒輸入或資料在 Sheets 維護，
    # 「**一枚按了不動的按鈕，比沒有按鈕更誤導**」。
    # ⚠️ **反方理由照實寫（兩邊理由並陳）**：`44` 5.1 卡片那張表的 `資料未備` 與
    #    `系統錯誤` 兩列，**逐字各帶一枚「重新取數」按鈕**，而這三塊都是卡片。
    #    照那張表讀，這三枚該留。**這個張力不是本輪發現的** —— `44` 5.5 那一條
    #    「各塊自己寫的優先於本表模板」自己就登記了「**本條的射程限本小節那張表**，
    #    第五節卡片那一張表的那兩列算不算，本輪不替客戶選」，掛著待裁。
    #    **客戶 2026-09-23 就這三塊裁了「拿掉」** ⇒ 對這三塊，塊的空狀態欄整格為準。
    # ⛔ **客戶裁的是這三塊，不是 `44` 5.1 那張表** —— 那張表一個字未動，
    #    它與 5.5 之間那筆射程待裁**仍然掛著**。本檔不替客戶把它一般化。
    # ⚠️ `44` :2423 的實測同向：四格裡寫出 `來源缺` 的十五塊，同格寫出那枚鈕的只有兩塊
    #    （`MKT-1` 與 `HLD-8`）—— 本塊不在那兩塊裡。
    buttons = []
    detail_lines = ["依 fund_code 字面值排列，不排序成優先順序。"]
    tail_lines = []

    if not has_holdings and fail_message:
        # 與 `_build_core_card` 同一筆登記（`44` 沒有訂這一組先後；客戶 2026-09-23 對
        # `HLD-0` 裁示「改紅」，本輪同向辦並就地登記，待客戶覆核）。
        rows, skipped = [], {"missing": set(), "error": set(), "na": set()}
        state = STATE_ERROR
        summary = fetch_failed_text(fail_message)
        detail_lines = [
            fetch_failed_text(fail_message),
            "訊息原文照印，不改寫成安撫語句。",
        ]
        # 📌 2026-10-05「讀取失敗不說空」：失敗的正是持倉表時，「持倉為空」不成立，不接下一句。
        #    上面那筆待客戶覆核的先後（紅壓過灰）一格未動；本件只改這一句接不接。
        if not holding_unknown:
            detail_lines.append(TEXT_NO_HOLDING)
        placeholder = _metric(
            None, text="", ccy="", error=fail_message, label="偏離筆數"
        )
    elif not has_holdings:
        rows, skipped = [], {"missing": set(), "error": set(), "na": set()}
        state = STATE_MISSING
        summary = TEXT_NO_HOLDING
        detail_lines = [empty_source_text(["holding"]), TEXT_NO_HOLDING]
        placeholder = _metric(None, text="", ccy="", missing=True, label="偏離筆數")
    elif rules_unknown:
        # 📌 2026-10-05「讀取失敗不說空」（總管 2026-10-05 裁定：「未設定」字句全面拿掉）：
        #    門檻是讀不到，不是沒設定 —— 不畫「⬜ 不適用：尚未設定門檻」。主值走 `44` 5.5 `系統錯誤`，
        #    原因是設定讀取失敗的原文。只有有持倉時走得到這一支（空持倉時上面兩支先接走）。
        rows, skipped = [], {"missing": set(), "error": set(), "na": set()}
        state = STATE_ERROR
        summary = fetch_failed_text(settings_error)
        detail_lines = [fetch_failed_text(settings_error), PRINT_AS_IS_LINE]
        placeholder = _metric(None, text="", ccy="", error=settings_error, label="偏離筆數")
    elif not rules:
        rows, skipped = [], {"missing": set(), "error": set(), "na": set()}
        state = STATE_BIZ
        summary = TEXT_NO_RULES
        detail_lines = ["不以任何內建值代替。"]
        placeholder = _metric(
            None, text="", ccy="", na_reason=NA_NO_RULES, label="偏離筆數"
        )
    else:
        rows, skipped = deviation_rows(metrics, rules)
        state = STATE_OK
        placeholder = None
        # 門檻指標取數失敗而沒列入的檔（逐檔或表層級都算）：不進本表、不計入列數；
        # 卡尾逐檔寫出是哪一檔、訊息原文。**計數算進了幾檔，就列得出幾檔的原因**
        # （紅隊建議 3：表層級錯誤也逐檔列一行，免得「3 檔」底下只列 1 行）。
        error_nodes = [
            (metric["_fund_code"], metric[rule["indicator"]])
            for metric in metrics
            if metric["_fund_code"] in skipped["error"]
            for rule in rules
            if rule["indicator"] in RULE_INDICATOR_NAMES
        ]
        fail_lines = _fund_error_lines(error_nodes, include_table=True)
        # S3：原為寫死的「（示意）」字面，沒有走 `HINT`（草稿 §E P7 點名「只把 HINT 改空，這一處會漏」）。
        summary = f"{len(rows)} 列{_hint()}" if rows else TEXT_NO_DEVIATION
        if not rows and skipped["error"]:
            # ⭐ 零列偏離，而且有檔因取數失敗沒列入 ⇒ 本塊進 `系統錯誤`
            #    （總管 2026-10-02 M2 裁定；比照下一支 `missing_other` 零列進 `資料未備` 的先例）。
            #    「無偏離項」在這裡是假話：那幾檔超不超出，不知道。`HLD-0` 依既有對應走（紅燈）。
            # ⚠️ 有偏離列時**不**走這一支：塊維持 `ok`，卡尾說明 N 只是下限（S2 原則：
            #    一檔失敗不得讓整塊進 `系統錯誤`）。排在 `missing_other` 前面：失敗比缺更該說出來。
            reason = next(
                node["reason_text"] for _code, node in error_nodes
                if node["_state"] == STATE_ERROR and node["reason_text"]
            )
            state = STATE_ERROR
            summary = ERR_TEXT
            placeholder = _metric(None, text="", ccy="", error=reason, label="偏離筆數")
        elif not rows and (skipped["missing_other"] or skipped["missing"]):
            # 零列，但有檔的門檻指標是 `資料未備`（而且不是缺淨值那一種）⇒ 「無偏離項」與
            # 「沒有任何一檔超出」都是假話：那幾檔超不超出，不知道（紅隊 2026-10-02 指出）。
            # 字樣只用 `44` 已宣告的：主值位置 `⬜ 資料未備`（`44` 5.1 卡片表 `資料未備` 那一列），
            # 尚未接上的來源用 `44` 5.5 `來源缺` 的模板 `⬜ 資料未備：<來源鍵> 尚無資料`。
            # 📌 客戶 2026-10-08 裁示：缺淨值零列＝未評估，同一支（卡尾「另有 N 檔缺淨值」照留）。
            #    ~~原本只看 `missing_other`：缺淨值的檔零列時照印「無偏離項」~~（有意識的更正，不是漏刪）。
            state = STATE_MISSING
            summary = ND_TEXT
            placeholder = _metric(None, text="", ccy="", missing=True, label="偏離筆數")
        elif not rows and skipped["na"]:
            # 📌 客戶 2026-10-08 裁示：零列而有檔的門檻指標不適用 ⇒ 那幾檔沒有評估，「無偏離項」是假話。
            #    主值 `⬜ 不適用`；原因句只用各檔節點上既有的 `⬜ 不適用：<原因>`，
            #    指標名不在清單內的那一種沒有現成句，只留主值。
            state = STATE_BIZ
            summary = NA_TEXT
            placeholder = _metric(None, text="", ccy="", na_reason=NA_TEXT, label="偏離筆數")
            detail_lines.extend(dict.fromkeys(
                metric[rule["indicator"]]["text"]
                for metric in metrics
                if metric["_fund_code"] in skipped["na"]
                for rule in rules
                if rule["indicator"] in RULE_INDICATOR_NAMES
                and metric[rule["indicator"]]["_state"] == STATE_BIZ
            ))
        elif not rows and not unsurfaced:
            # ⚠️ 登記：零列長什麼樣 `44` 沒有寫（草稿 ⛔ H-06：零筆偏離不屬空狀態四種）。
            #    本檔照草稿的畫法：一句「無偏離項」，不掛任何空狀態徽章。
            # ⚠️ 有檔取數失敗（逐檔或表層級）時走不到這裡 —— 上面第一支先接走，
            #    「沒有任何一檔超出」那一句因此不會出現（紅隊 J3：條件看 `skipped["error"]`）。
            # 📌 客戶 2026-10-08 裁示：只剩「每一檔都評估過」走得到這裡；有來源讀取失敗（`unsurfaced`）時
            #    讀不到的那幾檔沒有評估，這一句不寫，摘要與主值由下方 `unsurfaced` 那一段改成取數失敗。
            detail_lines.append("目前這一組門檻下，沒有任何一檔超出。")
        # 有偏離列也要寫：那幾檔的門檻指標沒有評估，燈上的 N 只是下限（紅隊 2026-10-02 指出）。
        detail_lines.extend(_missing_other_lines(metrics, skipped["missing_other"], pending))
        if skipped["missing"]:
            tail_lines.append(
                f"⬜ 另有 {len(skipped['missing'])} 檔缺淨值，未列入{_hint()}"
            )
            # ~~「未列入的檔不進上表、也不進偏離筆數；燈上的 N 與本卡列數因此相等。」~~
            # → 客戶 2026-10-03 裁示（有意識的更正，不是漏刪）：燈改數不重複的檔（N1）之後，
            #   同一檔超出兩條門檻時 N 小於列數，後半句不再成立 ⇒ 只刪「；燈上的 N 與本卡列數因此相等」，
            #   前半句一字不改。與 `44` 的偏離登記在 `ACCEPTANCE.md` 第九節。
            tail_lines.append(HLD1_SKIPPED_NOTE)
        if skipped["error"]:
            tail_lines.append(
                f"⛔ 另有 {len(skipped['error'])} 檔的門檻指標取數失敗，未列入{_hint()}"
            )
            tail_lines.extend(fail_lines)
        if skipped["na"]:
            tail_lines.append(
                f"⬜ 另有 {len(skipped['na'])} 檔的門檻指標不適用，未列入{_hint()}"
            )

    # ⭐ **第 2 件（客戶 2026-09-24 裁示）：有持倉時的來源取數失敗也要浮得出來。**
    # 射程見 `unsurfaced_source_error()` 的 docstring。
    # ⚠️ **刻意放在整條 if/elif/else 之後**，因為「有持倉」不只 `else` 那一支 ——
    #    `elif not rules`（有持倉但門檻未設）同樣是有持倉。只補 `else` 會漏掉它，
    #    而那正是本件要修的那個形狀（一條路只補一半）。
    # ⚠️ **算出來的東西一律留著**（`rows`／`placeholder`／`summary` 一格未動）：
    #    空持倉那一支會清空是因為它本來就沒東西可顯示；這裡有，
    #    把它清掉等於用一個失敗訊息蓋掉還算得出來的事實，那是另一種說謊。
    if has_holdings and unsurfaced:
        # 📌 客戶 2026-10-08 裁示：~~`if state == STATE_MISSING:`~~ → 有門檻、零列、尚未是系統錯誤的都算
        #    （原本是 ok 零列時，摘要「無偏離項」留著；有意識的更正，不是漏刪）。
        #    門檻未設那一支（`rules` 為空）不在射程內，照舊。
        if rules and not rows and state != STATE_ERROR:
            # 摘要與主值讓位給取數失敗：塊態是 `系統錯誤`，主值不能還寫 `⬜ 資料未備`。
            # 說明區原有的資料未備原因照留（算出來的東西一律留著）。
            summary = fetch_failed_text(unsurfaced)
            placeholder = _metric(
                None, text="", ccy="", error=unsurfaced, label="偏離筆數"
            )
        state = STATE_ERROR
        # 📌 2026-10-05「讀取失敗不說空」：門檻讀不到那一支已經寫了同一句時不再寫一次
        #    （與 `_build_core_card` 的 `error_lines` 同一條去重）。
        if fetch_failed_text(unsurfaced) not in detail_lines:
            detail_lines = detail_lines + [
                fetch_failed_text(unsurfaced),
                "訊息原文照印，不改寫成安撫語句。",
            ]

    return {
        "code": "HLD-1",
        "title": BLOCK_TITLES["HLD-1"],
        "_layer": 2,
        "_default_open": True,
        "_state": state,
        "_tone": tone_for_state(state),
        "_rows": rows,
        "_placeholder": placeholder,
        "missing_nav_count": len(skipped["missing"]),
        "column_labels": ["基金名", "實際值", "門檻值", "差額"],
        "answers": ANSWERS["HLD-1"],
        "summary_text": summary,
        "detail_lines": detail_lines,
        "tail_lines": tail_lines,
        "badges": badges,
        "buttons": buttons,
        "redline_note": "偏離提示只客觀描述現況與目標差距，不提供任何處置方向。",
    }


# ───────────────────────── HLD-2 / HLD-3 核心卡 ─────────────────────────


def _build_core_card(
    code, metrics, labels, *, has_holdings, has_window, subtitle, moved_note,
    fail_message=None, unsurfaced=None, window_unknown=False, holding_unknown=False,
):
    groups = []
    for metric in metrics:
        values = [metric[label] for label in labels]
        groups.append(
            {
                "_fund_code": metric["_fund_code"],
                "_ccy": metric["_ccy"],
                "head_text": f"{metric['fund_name']} · 幣別 {metric['_ccy']}{_hint()}",
                "main_values": values,
            }
        )

    states = [mv["_state"] for group in groups for mv in group["main_values"]]
    # 塊態只讀「不是逐檔取數失敗」的那些主值（總管 S2 原則：一檔失敗不得讓整塊進
    # `系統錯誤`，其他檔的值照常顯示）。**每一個主值都是逐檔失敗**時才進 `系統錯誤` ——
    # 那時這一塊一個值也出不來，與整張表失敗同一個畫面。
    # ⚠️ 沒有 `fund_errors` 時 `block_states` 就是 `states`，塊態與先前逐格相同。
    block_states = [
        mv["_state"]
        for group in groups
        for mv in group["main_values"]
        if _counts_for_block_state(mv)
    ]
    badges = []
    detail_lines = [subtitle]
    # ⛔ **本塊不掛「重新取數」按鈕**（客戶 2026-09-23 裁示；有意識的政策變更，不是漏刪）。
    # `44` :533（`HLD-2`）與 :544（`HLD-3`）空狀態欄**一個按鈕也沒有寫**，
    # 而 `44` 5.5「各塊自己寫的優先於本表模板」同輪補的分句逐字：
    # 「**一塊的空狀態欄整格為準：那一格沒有寫出按鈕，該塊的那個空狀態畫面上就沒有按鈕，
    #   不回退成本表模板裡的那一枚**」。
    # 決定性理由（`44` :2420 逐字）：這一頁缺的四張表由 Sheets 維護、本儀表板唯讀，
    # 按下去不會有任何效果 ——「**一枚按了不動的按鈕，比沒有按鈕更誤導**」。
    # ⚠️ **反方理由照實寫（兩邊理由並陳）**：`44` 5.1 卡片那張表的 `資料未備` 與
    #    `系統錯誤` 兩列，**逐字各帶一枚「重新取數」按鈕**，而這三塊都是卡片。
    #    照那張表讀，這三枚該留。**這個張力不是本輪發現的** —— `44` 5.5 那一條
    #    「各塊自己寫的優先於本表模板」自己就登記了「**本條的射程限本小節那張表**，
    #    第五節卡片那一張表的那兩列算不算，本輪不替客戶選」，掛著待裁。
    #    **客戶 2026-09-23 就這三塊裁了「拿掉」** ⇒ 對這三塊，塊的空狀態欄整格為準。
    # ⛔ **客戶裁的是這三塊，不是 `44` 5.1 那張表** —— 那張表一個字未動，
    #    它與 5.5 之間那筆射程待裁**仍然掛著**。本檔不替客戶把它一般化。
    buttons = []

    if not has_holdings and fail_message:
        # ⚠️ **登記：這一組先後 `44` 沒有訂，本輪照客戶 2026-09-23 對 `HLD-0` 的裁示同向辦。**
        # ⛔ **2026-09-24 就地更正：上一版在這裡編了一句逐字引文**
        #    （有意識的更正，不是漏刪；決策者：AI 總管；稽核抓到）。
        # ~~原寫：`44` :529／:543 空狀態欄寫「無任何持倉 → `來源缺`」。~~
        # **那一句在 `44` 裡不存在。** 本組實跑 grep：`無任何持倉` 在 `44` 只出現於
        # :515（`HLD-1`）、:762（`HLD-8`）、:1407、:1457（`ALO-6`）**四處**，
        # 而 `HLD-2` 的空狀態欄（:533）談的是淨值筆數／成立日／週末假日，
        # `HLD-3` 的空狀態欄（:544）談的是區間內無配息／`unknown`／區間末無淨值 ——
        # **這兩塊的空狀態欄從頭到尾沒有提過持倉。**
        # ⇒ 那個「兩句同時命中、`44` 沒寫誰先」的衝突，**對這兩塊而言在 `44` 裡根本不存在**。
        # ⚠️ **結論方向不受影響，但理由是編的** —— 編一個看起來可查的出處，
        #    比沒有出處更糟：下一個人照著翻會翻不到，然後合理懷疑整段。
        #
        # **改寫後成立的理由（逐條可查）**：
        #  (a) `44` 5.5 `系統錯誤` 的觸發條件逐字是「**取數或計算本身失敗**」——
        #      來源整張表取數失敗就是這一種，這一句與持倉有沒有資料無關。
        #  (b) 這兩塊的空狀態欄**沒有**替「無任何持倉」寫任何畫面，
        #      所以本檔原本在該情形下回 `資料未備`，**那是本檔自己的補洞，不是 `44` 的字**。
        #  (c) 客戶 2026-09-23 就 `HLD-0` 那一組同型衝突裁了「**改紅**」，
        #      方向出自 `44` :1620 逐字「**一句把空白報成平安的文案，比沒有文案更誤導**」。
        #  (d) 不同向辦的話，`44` :489「任一塊為 `系統錯誤` → 燈為紅」在空持倉下
        #      **永遠沒有一塊進得了 `系統錯誤`**（稽核窮舉 256 組確認），
        #      客戶剛裁的那一條當場變成空條文。
        # ⚠️ 客戶裁的是燈，這一步是塊；**本輪就地登記，待客戶覆核。**
        state = STATE_ERROR
        detail_lines = [
            fetch_failed_text(fail_message),
            "訊息原文照印，不改寫成安撫語句。",
        ]
        # 📌 2026-10-05「讀取失敗不說空」：失敗的正是持倉表時，「持倉為空」不成立，不接下一句。
        #    上面那筆待客戶覆核的先後（紅壓過灰）一格未動；本件只改這一句接不接。
        if not holding_unknown:
            detail_lines.append(TEXT_NO_HOLDING)
        summary = fetch_failed_text(fail_message)
    elif not has_holdings and holding_unknown:
        # 📌 2026-10-05「讀取失敗不說空」（總管 2026-10-05 裁定）：持倉表讀不到，不是空 ——
        #    不印「尚未建立任何持倉」。只有 `HLD-2` 走得到這一支：`holding` 不在它的來源表裡（`44` :531），
        #    `HLD-3` 的來源表有 `holding`，先進上面那一支。本塊照自己的來源欄畫：灰、「⬜ 資料未備」，
        #    不進 `系統錯誤`；讀取失敗的原文由 `HLD-1`（持倉表是它來源表的第一張）、`HLD-3`（上面那一支）、
        #    `HLD-5`、`HLD-8` 印出（`HLD-3` 原本漏列，2026-10-05 補上；稽核甲指出）。
        state = STATE_MISSING
        detail_lines = [NA_NO_WINDOW if not has_window else subtitle, ND_TEXT]
        summary = ND_TEXT
    elif not has_holdings:
        state = STATE_MISSING
        detail_lines = [NA_NO_WINDOW if not has_window else subtitle, ND_TEXT, TEXT_NO_HOLDING]
        summary = TEXT_NO_HOLDING
    else:
        state = worst_state(block_states) if block_states else STATE_ERROR
        # 📌 2026-10-05「讀取失敗不說空」：區間是讀不到時不寫「⬜ 不適用：尚未設定區間」，原因已在主值與說明區。
        if not has_window and not window_unknown:
            detail_lines.insert(0, NA_NO_WINDOW)
        # `44` 5.1：一組主值為 ok 而另一組不是時，標題掛「部分缺」徽章。
        for group in groups:
            group_states = [mv["_state"] for mv in group["main_values"]]
            if STATE_OK in group_states and any(s != STATE_OK for s in group_states):
                badges.append(status_badge("部分缺"))
                break
        summary = f"{len(groups)} 檔{_hint()}"

    if moved_note:
        detail_lines.append(moved_note)

    error_lines = []
    for group in groups:
        for mv in group["main_values"]:
            if mv.get("_fund_scoped_error"):
                continue  # 逐檔失敗另寫一行，帶出是哪一檔（見下）。
            if mv["_state"] == STATE_ERROR and mv["reason_text"]:
                line = fetch_failed_text(mv["reason_text"])
                if line not in error_lines:
                    error_lines.append(line)
                    error_lines.append("訊息原文照印，不改寫成安撫語句。")
    error_lines.extend(
        _fund_error_lines(
            (group["_fund_code"], mv) for group in groups for mv in group["main_values"]
        )
    )

    # ⭐ **第 2 件（客戶 2026-09-24 裁示）** —— 與 `_build_hld1` 同一條路、同一套理由。
    # 射程見 `unsurfaced_source_error()` 的 docstring。
    # ⚠️ 訊息走既有的 `error_lines` 管道（去重規則沿用），**不另開一種說明區寫法**。
    # ⚠️ 逐檔算出來的主值一格未動 —— 本件只動塊層的 `_state`。
    if has_holdings and unsurfaced:
        state = STATE_ERROR
        line = fetch_failed_text(unsurfaced)
        if line not in error_lines:
            error_lines.append(line)
            error_lines.append("訊息原文照印，不改寫成安撫語句。")

    return {
        "code": code,
        "title": BLOCK_TITLES[code],
        "_layer": 2,
        "_default_open": True,
        "_state": state,
        "_tone": _block_tone_with_errors(state, states),
        "fund_groups": groups,
        "answers": ANSWERS[code],
        "summary_text": summary,
        "detail_lines": detail_lines + error_lines,
        "badges": badges,
        "buttons": buttons,
    }


# ───────────────────────── HLD-0 結論燈 ─────────────────────────

_LAMP_LOOK = {
    "灰": ("⬜", "狀態：中性"),
    "黃": ("⚠", "狀態：要多看一眼"),
    # 紅＝取數失敗：客戶 2026-09-24 裁示取數失敗的圖示用 ⛔（原為 ✖；44 第五節第五小節已同步），黃燈仍 ⚠。
    "紅": ("⛔", "狀態：取數失敗"),
}


def conclusion_light(cards, *, has_holdings, has_rules, deviation_count,
                     holding_unknown=False, rules_unknown=False):
    """`44` HLD-0 規則與空狀態逐字。本塊不自取數，只讀三塊已經算出來的值。"""
    states = [card["_state"] for card in cards]
    lines = []

    # ⚠️ **2026-09-23 客戶裁示：`系統錯誤` 排在空狀態之前（有意識的政策變更，不是漏刪；
    #    日期 2026-09-23；決策者：客戶）。**
    # `44` :489 規則欄逐字「任一塊為 `系統錯誤` → 燈為**紅**」與 `44` :490 空狀態欄逐字
    # 「持倉表為空 → 燈為灰」「門檻未設定 → 燈為灰」**同時命中，`44` 沒有訂先後**。
    # ~~舊表述：`not has_holdings` 排在前面，於是空持倉時永遠回灰。~~
    # **舊表述在寫下當時撐得住** —— 它照 `44` 空狀態欄的字面辦，而空狀態欄本來就是
    # 「這一塊沒東西可讀時畫什麼」，把它放前面看起來是最保守的一邊。
    # **被權衡掉的是它會說謊**：取數真的失敗了，燈卻回「尚未建立任何持倉」，
    # 讀的人會把失敗讀成沒事 —— `44` :1620 逐字
    # 「**一句把空白報成平安的文案，比沒有文案更誤導**」。
    #
    # ⛔ **射程，2026-09-24 就地更正（有意識的更正，不是漏刪；決策者：AI 總管）**：
    # ~~收掉的**只有**「空持倉而且有一塊進了 `系統錯誤`」這一種。~~
    # **那一句是假的，稽核實測推翻。** 這個早退分支排在 `not has_holdings` **與
    # `not has_rules` 兩段之前**，所以收掉的是**兩種**：
    #   (1) 空持倉 ＋ 有一塊 `系統錯誤`；(2) **有持倉 ＋ 門檻未設 ＋ 有一塊 `系統錯誤`**。
    # 第 (2) 種在 `a7f8c1b` 上是灰「尚未設定門檻」，現在是紅。
    # ⚠️ **本組抄了 `44` :1623（`SET-0`）那句「收掉的只有那一種它原本蓋不住的情形」的體例，
    #    卻沒有去驗自己這一句是不是真的** —— `44` 那句是真的，抄過來的這句不是。
    # **兩種都在客戶裁示的方向上**（`系統錯誤` 不該被空狀態報成平安），故維持；
    # **改的是這段描述，不是行為。**
    if STATE_ERROR in states:
        # ⚠️ 登記：紅燈的文案字面 `44` 沒有給（草稿 ⛔ H-16）。本句取自草稿。
        named = [c["title"] for c in cards if c["_state"] == STATE_ERROR]
        # ⛔ **空狀態欄那兩句都要降級成補述，一句都不准吞掉**
        #    （2026-09-24 稽核抓到：原本只補了持倉那一句，門檻那一句在
        #     `emptyfail`〔`rules=None`〕底下整句消失，三件事只活下來兩件）。
        # 📌 2026-10-05「讀取失敗不說空」（燈不說：失敗不等於空，說了就是造假 —— 客戶 2026-09-28 核准，
        #    alo 草稿第 16 題）：持倉表或設定讀不到時，那一句補述不成立，不寫；真的空、真的沒設定照舊寫。
        if not has_holdings and not holding_unknown:
            lines.append(f"（另：{TEXT_NO_HOLDING}。{TEXT_SHEETS_READONLY}）")
        if not has_rules and not rules_unknown:
            lines.append(f"（另：{TEXT_NO_RULES}。門檻由你自己輸入，這一頁不提任何候選值）")
        return {
            "_tone": "紅",
            "_state": STATE_ERROR,
            "text": "有一塊取數失敗，這一頁的數字先不要照著讀",
            "lines": lines + [f"{'、'.join(named)}：取數失敗。"],
            "detail_lines": [
                "紅燈說的是「這一頁的數字能不能照著讀」，不是「你的持倉出事了」。"
            ],
            "buttons": [],
        }

    if not has_holdings:
        # ⚠️ 登記：持倉為空與門檻未設兩句同時成立時哪一句出現，`44` 沒有寫（草稿 ⛔ H-17）。
        #    本檔照草稿：取持倉那一句，另一句補在下面括號裡。
        if not has_rules:
            lines.append(HLD0_NO_RULES_ASIDE)
        return {
            "_tone": "灰",
            "_state": STATE_MISSING,
            "text": TEXT_NO_HOLDING,
            "lines": lines,
            "detail_lines": [TEXT_SHEETS_READONLY],
            "buttons": [_button(TEXT_GOTO_SHEETS, "導覽")],
        }

    if not has_rules:
        return {
            "_tone": "灰",
            "_state": STATE_BIZ,
            "text": TEXT_NO_RULES,
            "lines": ["門檻由你自己輸入，這一頁不提任何候選值。"],
            "detail_lines": [],
            "buttons": [],
        }

    hld1_state = next((c["_state"] for c in cards if c.get("code") == "HLD-1"), None)
    # 門檻指標取數失敗而沒列入 `HLD-1` 的檔：由 `HLD-1` 卡尾已經寫好的那幾行帶上來
    # （本塊不自取數），**連「⛔ 另有 N 檔…取數失敗，未列入」前導句一起帶**，
    # 說明燈上的 N 只是下限（紅隊建議 2）。
    # ⚠️ 只有「有偏離列」那一支用得到：零列偏離而有檔取數失敗時，`HLD-1` 自己就進
    #    `系統錯誤`（M2 裁定），燈在上面那一支已經紅了。所以零列的那三支**刻意不帶**
    #    —— 帶了也走不到（上一輪帶過，總管 M11／M12 指出無測試守住，本輪查明是走不到的路，拿掉）。
    fail_lines = [
        line
        for card in cards
        if card.get("code") == "HLD-1"
        for line in card.get("tail_lines", ())
        if _is_fail_tail_line(line)
    ]
    if deviation_count == 0 and hld1_state in (STATE_MISSING, STATE_BIZ):
        # `HLD-1` 零列、而且有檔的門檻指標資料未備 ⇒ 不得說「無偏離項」，
        # 也不得說「有一塊進了『不適用』」（紅隊 2026-10-02 指出）。
        # 字樣只用 `44` 已宣告的 `⬜ 資料未備`／`⬜ 資料未備：<來源鍵> 尚無資料`，
        # 由 `HLD-1` 已經算好的那幾行帶過來，本塊不自取數（`44` HLD-0 來源欄）。
        # 📌 客戶 2026-10-08 裁示：`HLD-1` 零列而有檔不適用（業務例外）同一支 —— 燈印 `HLD-1` 的既有主值
        #    （`⬜ 資料未備` 或 `⬜ 不適用`），不新增第二套判斷、不寫新字句。
        #    ~~`hld1_state == STATE_MISSING`、`"text": ND_TEXT`~~（有意識的更正，不是漏刪）。
        hld1 = next(c for c in cards if c.get("code") == "HLD-1")
        return {
            "_tone": "灰",
            "_state": hld1_state,
            "text": hld1["_placeholder"]["text"],
            "lines": [l for l in hld1["detail_lines"] if _is_missing_reason_line(l)],
            "detail_lines": [],
            "buttons": [],
        }

    if deviation_count > 0:
        hld1 = next((c for c in cards if c.get("code") == "HLD-1"), {"detail_lines": []})
        return {
            "_tone": "黃",
            "_state": STATE_OK,
            "text": f"有 {deviation_count} 檔超出你設定的門檻{_hint()}",
            # 有檔的門檻指標資料未備時，把原因帶上來：N 只是下限。
            "lines": ["哪幾檔分別超出的是哪一條線，看下面的偏離提示卡。"]
            + [l for l in hld1["detail_lines"] if _is_missing_reason_line(l)]
            + fail_lines,
            "detail_lines": ["黃燈說的是「要不要多看一眼」，不是「該調整了」。"],
            "buttons": [],
        }

    if all(state == STATE_OK for state in states):
        return {
            "_tone": "灰",
            "_state": STATE_OK,
            "text": TEXT_NO_DEVIATION,
            "lines": ["目前這一組門檻下，沒有任何一檔超出。"],
            "detail_lines": [],
            "buttons": [],
        }

    # ⚠️ 登記：三塊不全是 ok、偏離筆數為零、又沒有系統錯誤時，
    #    `44` HLD-0 三條規則**一條也沒命中**（草稿 ⛔ H-03）。
    #    本檔照草稿被迫挑的那一邊：灰燈，文案沿用「無偏離項」。**這不是規格。**
    # 📌 客戶 2026-10-08 裁示：走得到這裡時 `HLD-1` 每一檔都已評估且零偏離（未完整評估的已被上面那一支接走），
    #    維持灰燈「無偏離項」，只刪掉 ~~「有一塊進了「不適用」，偏離筆數為零。」~~ 那一句
    #    （不實：走到這裡的那一塊常是 `資料未備`，不是「不適用」；有意識的更正，不是漏刪）。不加任何新字句。
    return {
        "_tone": "灰",
        "_state": worst_state(states),
        "text": TEXT_NO_DEVIATION,
        "lines": [],
        "detail_lines": [
            "這一頁的燈色描述的是「要不要多看一眼」，不描述持倉好壞。"
        ],
        "buttons": [],
    }


def _build_hld0(cards, *, has_holdings, has_rules, deviation_count,
                holding_unknown=False, rules_unknown=False):
    light = conclusion_light(
        cards,
        has_holdings=has_holdings,
        has_rules=has_rules,
        deviation_count=deviation_count,
        holding_unknown=holding_unknown,
        rules_unknown=rules_unknown,
    )
    glyph, state_word = _LAMP_LOOK[light["_tone"]]
    return {
        "code": "HLD-0",
        "title": BLOCK_TITLES["HLD-0"],
        "_layer": 1,
        "_default_open": True,
        "_state": light["_state"],
        "_tone": light["_tone"],
        "_reads": ("HLD-1", "HLD-2", "HLD-3"),
        "_deviation_count": deviation_count,
        "glyph": glyph,
        "state_word": state_word,
        "text": light["text"],
        "main_values": [],  # `44`：這一塊沒有任何數字
        "answers": ANSWERS["HLD-0"],
        "summary_text": light["text"],
        "lines": light["lines"],
        "detail_lines": light["detail_lines"],
        "badges": [],
        "buttons": light["buttons"],
    }


# ───────────────────────── HLD-4 檢視區間與門檻輸入 ─────────────────────────


def _field(name, label, placeholder, value):
    return {
        "_input": True,
        "_default": None,  # `44` HLD-4：三組欄位皆為使用者輸入，無預設值（G3†）
        "_value": value,
        "name": name,
        "label": label,
        "placeholder": placeholder,
    }


def _build_hld4(*, applied_window, fields, rules, settings_error=None, window_unknown=False,
                rules_unknown=False):
    field_start = fields.get("window_start")
    field_end = fields.get("window_end")
    both_empty = not field_start and not field_end
    bad_range = bool(
        field_start and field_end and not window_is_valid((field_start, field_end))
    )

    detail_lines = []
    if bad_range:
        detail_lines.append(TEXT_BAD_RANGE)
    # 📌 2026-10-05「讀取失敗不說空」（客戶裁示：HLD-4 不得畫成「未設定」）：區間是讀不到時不寫「尚未設定區間」，
    #    改寫設定讀取失敗的原文（`44` 5.5 `系統錯誤` 的模板，`44` :2326）。按過「套用」之後照樣寫：設定仍然讀不到。
    #    M-2：判斷改看 `settings_error` 而不是 `window_unknown` —— 套用過有值的區間後再清空欄位，設定照樣讀不到，空白不是沒設定。
    if both_empty and not settings_error:
        detail_lines.append(NA_NO_WINDOW)
    if settings_error:
        detail_lines.extend([fetch_failed_text(settings_error), PRINT_AS_IS_LINE])

    inputs = [
        _field("window_start", "區間起日", "請選擇日期（YYYY-MM-DD）", field_start),
        _field("window_end", "區間迄日", "請選擇日期（YYYY-MM-DD）", field_end),
    ]
    threshold_rows = []
    # 門檻列的格子（S6a-2 第 5 項）：欄位已經畫過（`fields` 帶著門檻列的當下值）→ 照當下值的列數畫，
    # 「新增一列」「清除這一列」改的就是這一份；還沒畫過（首次渲染、情境自帶的 `fields`）→ 照已套用的門檻畫，
    # 輸出逐字同前。摘要的門檻列數照舊讀已套用的 `rules`。
    grid = (
        [dict(zip(("indicator", "direction", "value"), row)) for row in fields["rule_rows"]]
        if fields.get("rule_rows")
        else rules
    )
    for index, rule in enumerate(grid or [{"indicator": "", "direction": "", "value": ""}]):
        threshold_rows.append(
            [
                _field(f"rule_{index}_indicator", "指標名", "請輸入指標名", rule["indicator"]),
                _field(f"rule_{index}_direction", "比較方向", "請輸入比較方向", rule["direction"]),
                _field(f"rule_{index}_value", "數值", "請輸入數值", rule["value"]),
            ]
        )

    enabled_save = not both_empty and not bad_range
    reason = TEXT_BOTH_EMPTY if both_empty else (TEXT_BAD_RANGE if bad_range else "")
    # 「套用」能不能按：讀**欄位的當下值**，與 `page.py` 的回呼同一支（`applied_from_inputs`）。
    # 區間不可套用（顛倒、格式不是 `YYYY-MM-DD`、只填一格）→ 沿用既有原因句 `TEXT_BAD_RANGE`
    #   （⚠️ 登記：格式錯與只填一格時這一句不是真正的原因；總管 S6a 第四輪裁定先不修）。
    # 門檻列不可套用（`rules_from_inputs` 回 None）→ 停用，原因句 `TEXT_RULES_BAD`（S6a-2 第 4 項，客戶核准字面）。
    # ~~原因留空（待補文案）~~ → 客戶 2026-10-03 核准字面後補上（有意識的更正，不是漏刪；決策者：客戶）。
    # 兩者同時不可套用時寫區間那一句（區間先判，既有順序）。
    # 欄位裡沒有門檻列的當下值（首次渲染、情境自帶的 `fields`）→ 不判。
    window_blocked = window_input_blocked(field_start, field_end)
    rules_blocked = "rule_rows" in fields and rules_from_inputs(fields["rule_rows"]) is None
    apply_reason = TEXT_BAD_RANGE if window_blocked else (TEXT_RULES_BAD if rules_blocked else "")
    buttons = [
        _button("新增一列", "新增列"),
        _button("套用", "套用", enabled=not (window_blocked or rules_blocked), disabled_reason=apply_reason),
        _button("存檔", "存檔", enabled=enabled_save, disabled_reason=reason),
    ]
    row_buttons = [_button("清除這一列", "清除") for _ in threshold_rows]

    # S6a 第四輪（紅隊 M1）：摘要的區間與門檻列數讀**已套用**的那一組（`applied_window`／`rules`），
    # 不讀欄位當下值 —— 只改欄位、還沒按「套用」時，摘要與下面各塊的數字對得上。
    # 欄位當下值只用在「輸入尚未通過檢查」那一句（`bad_range`，既有寫法；首次渲染逐字同前）。
    applied_start, applied_end = applied_window
    if bad_range:
        summary = "輸入尚未通過檢查"
    elif window_unknown or rules_unknown:
        # 📌 2026-10-05「讀取失敗不說空」：不寫「尚未設定區間；門檻一列也沒有；存檔停用」—— 是讀不到，不是沒設定。
        summary = fetch_failed_text(settings_error)
    elif not applied_start and not applied_end:
        summary = "尚未設定區間；門檻一列也沒有；存檔停用" if not rules else "尚未設定區間"
    elif not window_is_valid(applied_window):
        summary = "輸入尚未通過檢查"
    else:
        rule_count = len(rules or ())
        summary = f"區間 {applied_start}{_hint()} 至 {applied_end}{_hint()} · 門檻 {rule_count} 列{_hint()}"

    return {
        "code": "HLD-4",
        "title": BLOCK_TITLES["HLD-4"],
        "_layer": 3,
        "_default_open": False,
        "_state": STATE_OK,
        "_tone": "中性",
        "_applied": window_is_valid(applied_window),
        "answers": ANSWERS["HLD-4"],
        "summary_text": summary,
        "inputs": inputs,
        "rule_indicator_names": RULE_INDICATOR_NAMES,
        "threshold_caption": "門檻（指標名＋比較方向＋數值，可增減列）",
        "threshold_rows": threshold_rows,
        "row_buttons": row_buttons,
        "detail_lines": detail_lines,
        "badges": [_redline_badge("G3†")],
        "buttons": buttons,
        "notes": [
            HLD4_APPLY_NOTE,
            HLD4_SAVE_NOTE,
            HLD4_SAVE_SCOPE_NOTE,
            "欄位一律無預設值：首次開啟四個欄位全是空的。本塊不對門檻數值提出任何候選值。",
        ],
        "redline_note": "所有試算參數均由使用者自行輸入，系統不代填。",
    }


# ───────────────────────── HLD-5 單檔展開 ─────────────────────────


# `44` HLD-5 規則欄逐字：「**點一檔展開一檔，同時最多展開一檔**」。
# 展開中的是哪一檔，存在 `st.session_state` 的這個鍵底下；鍵名住在 logic，
# 好讓「哪一檔是開的」這個判定不散到 page.py 去（page.py 一個判定也不做）。
HLD5_OPEN_KEY = "hld5_open_fund"

# 這一枚按鈕的類別與標籤。
# **類別** `展開` 是 `44` 5.3 八類中的一類，不是新發明的第九類。
# **標籤** `44` 沒有給字面，本檔取 `44` 5.3 狀態表那一句「`可用` | 文字按鈕，
# **標籤為動作本身**」—— 動作是 `展開`，標籤就寫 `展開`。**登記：字面為本組所取。**
HLD5_OPEN_LABEL = "展開"
# `停用` 時滑過顯示的一行原因（`44` 5.3：按鈕停用時不隱藏，停用附原因才說得清楚）。
HLD5_OPEN_DISABLED_REASON = "這一檔已經展開"


def open_fund_after_click(current, clicked):
    """按下某一檔的展開鈕之後，展開中的是哪一檔。

    ⚠️ 2026-10-02 起兩個參數與回傳值都是**持倉的 `holding_id`**，不是 `fund_code`
       （理由見 `_build_hld5` 的 `_holding_id` 那一行）。函式名與 session 鍵名沿用舊名，不改。

    `44` HLD-5 規則欄逐字：「點一檔展開一檔，**同時最多展開一檔**」，
    判準逐字：「展開第二檔時第一檔自動收合，**同時處於展開狀態的檔數為 1**」。
    ⇒ 按下去就換成它，前一檔自動收合。`current` 只是為了讓這條規則看得見，不影響結果。

    ⚠️ **登記：`44` 沒有寫「怎麼收回到零檔」。** 本檔**不發明一枚收合鈕**
    —— `44` 5.3 是封閉八類，沒有 `收合` 這一類。展開中的那一檔，它的鈕改為
    `停用`（`44` 5.3「按鈕停用時不隱藏」），所以按不下去、也不會有一枚按了不動的鈕
    （`44` :2420）。

    ⛔ **2026-09-24 就地更正：本段原本把一條不存在的出口寫成既有的出口**
    （有意識的更正，不是漏刪；決策者：AI 總管；稽核抓到）。
    ~~原寫：回到零檔的路是 `44` 第二節那一句「展開狀態不跨頁保留；離開再回來，回到預設」。~~
    **那一句本身引得沒錯**（`44` :120 逐字如此），**錯的是把它當成本原型已經有的路**。
    **本組實測**：展開 `AAAA` → 把查詢參數切到別的情境 → 再切回來，
    `st.session_state` 裡那個鍵**仍然是 `AAAA`**，那一檔的鈕**仍然是 `停用`** ——
    `st.session_state` 是**同一個 session 內持久**的，
    **同一個 session 內沒有任何一條路把它設回 `None`**。
    `44` :120 講的「離開再回來」指的是**跨頁**，而本原型只有一頁。
    ⇒ **現行事實：展開之後，在同一個 session 內回不到零檔。**
    **要不要給一條收合的路，待客戶裁決**（給的話得先解決「`收合` 不在八類裡」那個問題）。
    """
    return clicked


class HoldingIdError(ValueError):
    """`holding_id` 缺、空或重複。體例同 L2 `services/v2_tables/alo_holdings.py` 的
    `HoldingIdCollision`：一律往上拋，不靜默去重、不靜默補值（§1 Fail Loud）。"""


def _check_holding_ids(holdings) -> None:
    """`44` 4.1：`holding_id` 是主鍵，不可空。展開鍵與欄位對應都靠它。"""
    ids = [h.get("holding_id") for h in holdings]
    empty = [h.get("fund_code") for h, i in zip(holdings, ids) if i is None or i == ""]
    if empty:
        raise HoldingIdError(f"holding_id 缺或為空：fund_code={empty!r}")
    wrong = [(h.get("fund_code"), type(i).__name__) for h, i in zip(holdings, ids)
             if not isinstance(i, str)]
    if wrong:
        raise HoldingIdError(f"holding_id 型別不對（要字串）：{wrong!r}")
    # ⛔ 不偷偷 strip：前後帶空白的 id 與不帶空白的是兩個不同的鍵，悄悄修掉會讓兩邊對不上。
    padded = [i for i in ids if i != i.strip() or not i.strip()]
    if padded:
        raise HoldingIdError(f"holding_id 前後帶空白或只有空白：{padded!r}")
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise HoldingIdError(f"holding_id 重複：{dup!r}")


def _row_is_open(holding_id, open_fund) -> bool:
    """這一列是不是展開中。⛔ `None == None` 不算展開 —— 沒有鍵的列絕不自動展開。"""
    return bool(holding_id) and holding_id == open_fund


def _sync_field_value(raw):
    """HLD-5「最後對帳」那一格的值。

    示範模式：照 base 逐字 —— 取前 10 個字再接示意字尾（`None` 照舊在 `[:10]` 炸掉，那是 base 就有的行為）。
    正式模式（`demo_hint=False`）：**原值照交**，由 `ui_v2/hld/live.py` 驗格式、換算台灣日期、
    不合格時改成 `系統錯誤` 的值節點（S3 第二輪，總管裁定 1／2）。
    ⚠️ 在這裡先截 10 個字，帶時區的值就換算不了（`…T20:30:00Z` 的台灣日期是隔天），所以正式模式不截。
    ⚠️ 正式模式的這一格**一定要經過** `live.apply_live_notes`，否則畫面上印的是未驗的原值；
       正式入口一律走 `live.build_live_model`。
    """
    if _hint():
        return raw[:10] + _hint()
    return raw


def _build_hld5(dataset, metrics, *, open_fund, has_window, window_unknown=False,
                settings_error=None, holding_error=None, holding_unknown=False):
    policies = {p["policy_id"]: p for p in dataset.get("policy", [])}
    holdings = {h["holding_id"]: h for h in dataset.get("holding", [])}
    items = []
    for index, metric in enumerate(metrics):
        holding = holdings[metric["_holding_id"]]
        policy = policies.get(holding["policy_id"])
        is_direct = holding["policy_id"] == "DIRECT"
        fields = [
            ("保單", TEXT_DIRECT_HOLD if is_direct else (policy or {}).get("policy_name", "⬜")),
            ("發行單位", "—" if is_direct else (policy or {}).get("issuer", "⬜")),
            ("持有起始日", holding["opened_on"] + _hint()),
            ("單位數", f"{holding['units_shares']:,.3f}{_hint()}"),
            ("成本（原幣）", hinted(format_amount(holding["cost_orig_ccy"], holding["ccy"]))),
            ("成本（新臺幣）", f"{holding['cost_twd']:,} 元{_hint()}"),
            ("類別", holding["bucket"] or "⬜"),
            ("最後對帳", _sync_field_value(holding["last_synced_at"])),
        ]
        has_nav = bool(metric["nav_rows"])
        items.append(
            {
                "_fund_code": metric["_fund_code"],
                # 展開鍵（總管 2026-10-02 第 2 輪裁定）：`44` 4.1 畫面上一列＝一組
                # （`policy_id`, `fund_code`），所以「點一檔展開一檔」的「檔」是畫面上那一列。
                # 用 `fund_code` 當鍵，同一檔基金掛在兩張保單下時兩列會一起展開，
                # 頁面的按鈕鍵也會撞號（`StreamlitDuplicateElementKey`）。
                "_holding_id": metric["_holding_id"],
                "_ccy": metric["_ccy"],
                # `44` :119／:128／§5.4「展開區不自動展開」—— 上一輪寫 `index == 0`，三處都撞。
                "_open": _row_is_open(metric["_holding_id"], open_fund),
                "_button": _button(
                    HLD5_OPEN_LABEL,
                    "展開",
                    enabled=not _row_is_open(metric["_holding_id"], open_fund),
                    disabled_reason=HLD5_OPEN_DISABLED_REASON,
                ),
                "_fields": fields,
                "head_text": f"{metric['fund_name']} · {metric['_fund_code']}{_hint()}",
                # 📌 2026-10-05「讀取失敗不說空」（總管 2026-10-05 裁定）：區間是讀不到時，「該檔在區間內無淨值」
                #    無從判斷，不印「⬜ 資料未備：nav 尚無資料」，改印設定讀取失敗的原文。
                "nav_plot_text": (
                    fetch_failed_text(settings_error)
                    if window_unknown
                    else "〔淨值折線〕與〔配息長條〕共用同一條時間軸"
                    if has_nav
                    # `44` :708 明文回指 §5.5 模板，不是自己寫一句散文。
                    else empty_source_text(["nav"])
                ),
                "div_plot_text": "〔配息長條〕照畫 · 本輪以佔位框代替，不畫真圖",
            }
        )

    if not items and holding_unknown:
        # 📌 2026-10-05「讀取失敗不說空」：持倉表讀不到，不是沒有持倉 —— 不印「尚未建立任何持倉」，
        #    走 `44` 5.5 `系統錯誤`（本塊的來源有 `holding`）。本塊向來沒有塊層級的按鈕，這裡也不加。
        state = STATE_ERROR
        summary = fetch_failed_text(holding_error)
        detail_lines = [fetch_failed_text(holding_error), PRINT_AS_IS_LINE]
    elif not items:
        state = STATE_MISSING
        summary = TEXT_NO_HOLDING
        detail_lines = [ND_TEXT, "尚未建立任何持倉，沒有可以展開的檔。"]
    else:
        state = STATE_OK
        summary = f"{len(items)} 檔{_hint()} · 同時最多展開一檔"
        detail_lines = [
            "點一檔展開一檔，同時最多展開一檔；展開區不巢狀第二層。",
            "展開中的那一檔，它的展開鈕停用；初次載入零檔展開。",
        ]
        if window_unknown:
            # 📌 2026-10-05「讀取失敗不說空」（總管 2026-10-05 裁定）：與下一支同一個位置，換成真話 ——
            #    區間是讀不到，不是沒設定。
            detail_lines[0:0] = [fetch_failed_text(settings_error), PRINT_AS_IS_LINE]
        elif not has_window:
            detail_lines.insert(0, NA_NO_WINDOW)

    return {
        "code": "HLD-5",
        "title": BLOCK_TITLES["HLD-5"],
        "_layer": 3,
        "_default_open": False,
        "_state": state,
        "_tone": tone_for_state(state),
        "_items": items,
        "_rows": items,
        "answers": ANSWERS["HLD-5"],
        "summary_text": summary,
        "detail_lines": detail_lines,
        "badges": [],
        "buttons": [],
    }


# ───────────────────────── HLD-6 淨值與配息序列 ─────────────────────────

_DIV_KIND_TEXT = {"income": "收益", "principal": "本金", "unknown": "來源未區分"}


def _build_hld6(dataset):
    nav_rows = []
    for row in sorted(
        dataset.get("nav", []), key=lambda r: (r["fund_code"], r["nav_date"])
    ):
        nav_rows.append(
            {
                "_fund_code": row["fund_code"],
                "_estimated_badge": "推估" if row["is_estimated"] else "",
                # ⚠️ 兩枚徽章**做進模型**：渲染時現組的 dict 沒有 `_kind`，`collect_badges()`
                #    結構上收不到（`test_來源徽章中性不著色` 因此空掃至今）；走 helper 另有
                #    字面值守衛（不在 `44` 5.2 那七個之內會 raise）。
                "_source_badge": source_badge(row["source_tier"]),
                "_estimated_badge_node": (
                    status_badge("推估") if row["is_estimated"] else None
                ),
                "fund_code": row["fund_code"],
                "nav_date": row["nav_date"],
                "nav_text": f"{row['nav_orig_ccy']:.4f}{_hint()}",
                "ccy": row["ccy"],
                "source_tier": row["source_tier"],
            }
        )
    div_rows = []
    for row in sorted(
        dataset.get("dividend", []), key=lambda r: (r["fund_code"], r["ex_date"])
    ):
        div_rows.append(
            {
                "_fund_code": row["fund_code"],
                "fund_code": row["fund_code"],
                "ex_date": row["ex_date"],
                # `44` 4.3：`pay_date` 是兩張表裡唯一「可空」為是的欄位；空的時候顯示 ⬜。
                "pay_date": row["pay_date"] or "⬜",
                "div_text": f"{row['div_per_unit_orig_ccy']:.4f}{_hint()}",
                "ccy": row["ccy"],
                "div_kind": _DIV_KIND_TEXT.get(row["div_kind"], row["div_kind"]),
            }
        )

    state = STATE_OK if (nav_rows or div_rows) else STATE_MISSING
    summary = (
        f"淨值 {len(nav_rows)} 列{_hint()} · 配息 {len(div_rows)} 列{_hint()}"
        if state == STATE_OK
        else f"{ND_TEXT}：兩張表都沒有列"
    )
    detail_lines = [
        "表不做任何補值，缺的日期不出現在表上；週末與假日沒有列屬正常。"
        "可空的只有配息表的入帳日一欄，空的時候顯示 ⬜。"
    ]
    if state == STATE_MISSING:
        # `44` :719 只寫「無列 → `來源缺`」。兩張表為空**不一定**等於沒有持倉
        # （取數失敗、區間外都可能），上一輪那句原因是假資料下碰巧成立，已撤。
        detail_lines = [empty_source_text(["nav", "dividend"])]

    return {
        "code": "HLD-6",
        "title": BLOCK_TITLES["HLD-6"],
        "_layer": 4,
        "_default_open": False,
        "_state": state,
        "_tone": tone_for_state(state),
        "nav_rows": nav_rows,
        "div_rows": div_rows,
        "nav_labels": ["基金代碼", "淨值日期", "單位淨值（原幣）", "幣別", "來源層級", "推估"],
        "div_labels": ["基金代碼", "除息日", "入帳日", "每單位配息（原幣）", "幣別", "配息類別"],
        "answers": ANSWERS["HLD-6"],
        "summary_text": summary,
        "detail_lines": detail_lines,
        "badges": [],
        "buttons": [],
    }


# ───────────────────────── HLD-8 ─────────────────────────


def _build_hld8(metrics, *, has_holdings, has_window, window_unknown=False,
                settings_error=None, holding_error=None, holding_unknown=False):
    rows = []
    unknown_total = 0
    for metric in metrics:
        unknown_total += metric["unknown_count"]
        rows.append(
            {
                "_fund_code": metric["_fund_code"],
                "_ccy": metric["_ccy"],
                "fund_name": metric["fund_name"],
                "ccy_text": f"{metric['_ccy']}{_hint()}",
                "drawdown": metric["最大回撤"],
                "principal": metric["本金類配息佔比"],
            }
        )

    detail_lines = [HLD8_DETAIL_NOTE]
    buttons = []
    states = []  # 無持倉時本表沒有任何主值；先給空集，`tone_for_block` 才有東西可讀。
    block_states = []
    if not has_holdings and holding_unknown:
        # 📌 2026-10-05「讀取失敗不說空」：持倉表讀不到，不是沒有持倉 —— 不印「尚未建立任何持倉」，
        #    也不印「⬜ 資料未備：holding 尚無資料」，走 `44` 5.5 `系統錯誤`。表內一欄也沒有，
        #    不掛「重新取數」（總管 2026-10-05 裁定；`44` :762 把那枚按鈕綁在「該欄」）。
        state = STATE_ERROR
        summary = fetch_failed_text(holding_error)
        detail_lines = [fetch_failed_text(holding_error), PRINT_AS_IS_LINE]
    elif not has_holdings:
        state = STATE_MISSING
        summary = f"{ND_TEXT}：{TEXT_NO_HOLDING}"
        detail_lines = [empty_source_text(["holding"]), TEXT_NO_HOLDING]
    else:
        states = [row["drawdown"]["_state"] for row in rows] + [
            row["principal"]["_state"] for row in rows
        ]
        # 與核心卡同一條（總管 S2 原則）：塊態不讀逐檔取數失敗的值；每一個值都是逐檔失敗
        # 才進 `系統錯誤`。⚠️ 沒有 `fund_errors` 時 `block_states` 就是 `states`。
        block_states = [
            row[key]["_state"]
            for key in ("drawdown", "principal")
            for row in rows
            if _counts_for_block_state(row[key])
        ]
        state = worst_state(block_states) if block_states else STATE_ERROR
        # 摘要讀**全部**的值：有一檔逐檔失敗時，「兩個值皆出數」是假話。
        summary = (
            f"{len(rows)} 檔{_hint()} · 兩個值皆出數"
            if all(s == STATE_OK for s in states)
            else f"{len(rows)} 檔{_hint()} · 有值取不到或不適用"
        )
        # 📌 2026-10-05「讀取失敗不說空」：區間是讀不到時不寫「⬜ 不適用：尚未設定區間」，原文寫在表下（見下）。
        if not has_window and not window_unknown:
            detail_lines.insert(0, NA_NO_WINDOW)
        if unknown_total:
            # `44` HLD-8 空狀態逐字：並在**表下**寫出未知的筆數。
            detail_lines.append(f"配息類別未知的筆數：{unknown_total} 筆{_hint()}")
        # ~~⚠️ 上一輪曾收成「只有取數失敗才掛」，**本輪撤回**：`44` :762 第一句逐字~~
        # ~~   「四狀態逐值判定，**與核心卡同一套**」，收窄後同一個缺淨值條件下核心卡各一枚、~~
        # ~~   本塊零枚，同一套當場破掉；上一輪引的 §5.5「整格為準」自己寫明射程不含核心卡那張表。~~
        # ~~   ⛔ 「四塊一起拿掉」是另一邊，**屬客戶地盤，不替客戶選**（登記待裁）。~~
        # → **2026-09-23 就地更正：上面那個理由的另一端已經不存在了**
        #   （**有意識的更正，不是漏刪** · 日期 2026-09-23 · 決策者：客戶〔裁示拿掉三枚〕）。
        #   客戶本日裁示拿掉 `HLD-1`／`HLD-2`／`HLD-3` 那三枚，**核心卡現在零枚** ——
        #   舊理由說的「收窄後核心卡各一枚、本塊零枚，同一套當場破掉」**這個對照組沒有了**。
        #   **舊表述在寫下當時為真**（那時三張卡確實各掛一枚）；**被權衡掉的是它的前提。**
        #
        # ⛔ **本輪刻意不動這個綁法，行為一個位元未改** —— 派工單明寫「若判定會產生新的
        #   不一致，**登記，不要自己再改 `HLD-8`**」。
        # ⚠️ **登記（拿掉三枚之後浮出來的張力）—— 2026-09-24 改寫成兩邊並陳**
        #   （有意識的更正，不是漏刪；決策者：AI 總管，依總管 2026-09-24 裁決）。
        #   ~~原本只寫一邊：「本行綁得比 `44` 的字面寬」。~~
        #   **那一半是真的，但把它寫成唯一的一邊，等於把一個張力寫成一個錯誤。**
        #
        #   **甲（窄的那一邊）**：`44` :762 寫按鈕那一句逐字是「**取數失敗時**該欄印出
        #   失敗訊息原文並掛『重新取數』按鈕」——**只綁 `取數失敗`**，
        #   而下面這一行綁的是 `資料未備` ∪ `系統錯誤`，**比那一句寬**。
        #   實測：`srcmiss` 情境下本塊沒有任何一個值進 `取數失敗`，卻照樣掛得出鈕。
        #
        #   **乙（寬的那一邊，而且它也出自 `44`）**：`44` :762 **同一格的第一句**是
        #   「四狀態逐值判定，**與核心卡同一套**」，而核心卡那張表（`44` :2009）
        #   給 `資料未備` 那一列**也逐字掛了一枚「重新取數」按鈕**。
        #   **照那條連結讀，現行這個較寬的綁法才是 `44`-compliant，
        #   :762 的按鈕子句反而是窄的那一個。**
        #
        #   ⇒ **`44` 在同一格裡給了兩個答案**，本檔不替客戶選。**待客戶裁決。**
        #   ⚠️ 本組原本在 `_build_hld1`／`_build_core_card` 的註解裡就寫出了 `:2009` 這個
        #   反方理由，**卻沒有把它接到這一筆登記上** —— 而這裡正是它最有力的地方。
        #   這個現況由 `test_登記_HLD8那枚鈕綁得比44的字面寬` 釘住，不讓它無聲漂移。
        if any(s in (STATE_MISSING, STATE_ERROR) for s in states):
            buttons.append(_retry_button())
        # 逐檔取數失敗：逐檔寫出是哪一檔、訊息原文（S2）。沒有 `fund_errors` 時為空。
        detail_lines.extend(
            _fund_error_lines(
                (row["_fund_code"], row[key])
                for row in rows
                for key in ("drawdown", "principal")
            )
        )
        if window_unknown:
            # 📌 2026-10-05「讀取失敗不說空」：~~區間取自存過的設定而設定讀不到~~ → 區間未知（設定讀不到，
            #    而區間取自存過的設定、或套用的區間兩格都空），兩欄無從計算；
            #    設定讀取失敗的原文印在表下（~~`44` :762~~ → 依 S2 的先例：逐檔取數失敗的原文經 `_fund_error_lines`
            #    寫進說明區、畫在表下，格內只顯示 `ERR_TEXT`；見 `page.py::_render_live_error` 說明第 (2)、(3) 條
            #    與 `page.py::_render_hld8`）。
            #    兩處劃線是 2026-10-05 的更正（有意識的更正，不是漏刪；決策者：總管）：前一處是稽核乙 M-1；
            #    後一處是稽核甲指出 `44` :762 寫失敗訊息的那一句是「取數失敗時該欄印出失敗訊息原文」，
            #    位置是該欄、不是表下（同一格寫到表下的是未知的筆數）。
            #    ⚠️ 登記既有差距（不是本件造成的）：格內不帶原文，與 `44` :762 那一句的字面不同。
            detail_lines.extend([fetch_failed_text(settings_error), PRINT_AS_IS_LINE])

    return {
        "code": "HLD-8",
        "title": BLOCK_TITLES["HLD-8"],
        "_layer": 4,
        "_default_open": False,
        "_state": state,
        "_tone": _block_tone_with_errors(state, states),
        "_rows": rows,
        "column_labels": ["基金名", "幣別", "最大回撤", "本金類配息佔比"],
        "answers": ANSWERS["HLD-8"],
        "summary_text": summary,
        "detail_lines": detail_lines,
        "badges": [],
        "buttons": buttons,
    }


# ───────────────────────── HLD-7 計算軌跡 ─────────────────────────


def _inputs_text(metric, indicator):
    if indicator in NAV_INPUT_INDICATORS:
        rows = metric["nav_rows"]
        if not rows:
            return f"0 筆{_hint()}"
        return (
            f"{len(rows)} 筆{_hint()} · {rows[0]['nav_date']}{_hint()}"
            f" 至 {rows[-1]['nav_date']}{_hint()}"
        )
    rows = metric["div_rows"]
    if not rows:
        return f"0 筆{_hint()}"
    return (
        f"{len(rows)} 筆{_hint()} · {rows[0]['ex_date']}{_hint()}"
        f" 至 {rows[-1]['ex_date']}{_hint()}"
    )


def _build_hld7(metrics, hld1_rows, *, has_holdings):
    rows = []
    for metric in metrics:
        for indicator, owner in INDICATOR_OWNER.items():
            node = metric[indicator]
            rows.append(
                {
                    "_fund_code": metric["_fund_code"],
                    "_indicator": indicator,
                    "_owner_code": owner,
                    "_ccy": metric["_ccy"],
                    "indicator_text": f"{indicator}（{metric['fund_name']}）",
                    "inputs_text": _inputs_text(metric, indicator),
                    "formula_text": FORMULA_TEXT[indicator],
                    "output_text": node["text"],
                }
            )
    for row in hld1_rows:
        rows.append(
            {
                "_fund_code": row["_fund_code"],
                "_indicator": row["trace_indicator"],
                "_owner_code": "HLD-1",
                "_ccy": row["_ccy"],
                "indicator_text": f"{row['trace_indicator']}（{row['fund_name']}）",
                "inputs_text": f"1 條門檻{_hint()} · 門檻值 {row['threshold_text']}",
                "formula_text": _DEVIATION_FORMULA,
                "output_text": row["delta_text"],
            }
        )

    # `44` :730「四塊沒有一塊出數 → `來源缺`」。上一輪只看有沒有持倉，於是「有持倉但
    # 四塊一個數都沒出」時塊態還是 `ok`（實測 18 列全不適用，塊卻宣稱正常）。
    # ⚠️ 同一格另有一句「輸入欄照列」，兩句**同時滿足**：`來源缺` 定塊的狀態、
    #    「輸入欄照列」定列的畫面，兩者不同層。⛔ 把列吞掉只印「來源缺」是假話 ——
    #    來源在，是區間沒設。
    any_output = bool(hld1_rows) or any(
        metric[indicator]["_state"] == STATE_OK
        for metric in metrics
        for indicator in INDICATOR_OWNER
    )
    state = STATE_OK if (has_holdings and rows and any_output) else STATE_MISSING
    if state == STATE_MISSING:
        detail_lines = [
            empty_source_text(["HLD-1", "HLD-2", "HLD-3", "HLD-8"]),
            "四塊沒有一塊出數；下面各列的輸入筆數與不適用原因照列。",
        ]
        summary = (
            f"{ND_TEXT}：四塊沒有一塊出數 · {len(rows)} 列{_hint()}"
            if rows
            else f"{ND_TEXT}：四塊沒有一塊出數"
        )
    else:
        detail_lines = [
            "輸出值與該列指標名所在那一塊上顯示的值逐字相同；"
            "算式以文字寫出，不寫任何實作語言的語法。"
            "該塊把該指標判為不適用時，輸出欄顯示同一句不適用文案，輸入欄照列。"
        ]
        summary = f"逐檔逐指標 {len(rows)} 列{_hint()}"

    return {
        "code": "HLD-7",
        "title": BLOCK_TITLES["HLD-7"],
        "_layer": 4,
        "_default_open": False,
        "_state": state,
        "_tone": tone_for_state(state),
        "_rows": rows,
        "column_labels": [
            "指標名",
            "取用的輸入筆數與首末日期",
            "算式的文字寫法",
            "輸出值",
        ],
        "answers": ANSWERS["HLD-7"],
        "summary_text": summary,
        "detail_lines": detail_lines,
        "badges": [],
        "buttons": [],
    }


# ───────────────────────── 組裝 ─────────────────────────


def build_page_model(
    dataset: dict,
    *,
    fields=None,
    viewport_width: int = 1280,
    open_fund=None,
    demo_hint: bool = True,
    applied_window=None,
    applied_rules=None,
) -> dict:
    """把假資料 ＋ 使用者輸入組成一份純資料模型。page.py 只負責把它畫出來。

    `applied_window`：使用者按「套用」時欄位的當下值 `(起日, 迄日)`（S6a 第三輪，紅隊 M1）。
    `44` HLD-4：「套用」只讀這些欄位的當下值、重算六塊（`APPLY_RECALC_BLOCKS`），不寫任何資料表。
    `None`（還沒按過「套用」）＝ 照舊用存過的區間（`saved_window`），輸出逐字同前。
    `applied_rules`：同一次「套用」時門檻列的當下值（`rules_from_inputs` 的結果；S6a 第四輪，紅隊 M3）。
    `None` ＝ 照舊用存過的門檻（`saved_rules`）。

    `open_fund`：展開中那一列持倉的 `holding_id`（2026-10-02 起；之前是 `fund_code`）。

    `demo_hint`：數字後面要不要接「（示意）」（2026-10-02 S3；客戶裁示 2-A）。
    預設 `True` ＝ 示範模式，輸出逐字同前；正式模式（`ui_v2/hld/live.py`）傳 `False`。
    ⚠️ S3 第二輪起它也是 HLD-5「最後對帳」那一格的模式開關：`False` 時那一格交原值，
       由 live 層驗與換算（見 `_sync_field_value`）。
    ⚠️ 只管本檔自己接上去的字尾；資料本身的字（例如假資料的基金名）不在射程內 ——
       正式模式不讀 fixtures，那些字本來就不會出現（草稿 §E P16）。

    ⚠️ **登記（`44` HLD-4 自己登記為待客戶裁決的那一個缺口）**：
    使用者按了「存檔」、沒按「套用」，然後重新載入 —— 此時三張核心卡顯示什麼，`44` 沒有訂。
    兩種讀法（載入時就拿存過的值算一次／等使用者再按一次「套用」）都讀得通。
    **本檔取前者**，理由是後者會讓畫面印出「⬜ 不適用：尚未設定區間」，
    而那句話在區間明明已經設過的情況下**是假的** —— 印一句假的比多算一次危險（§1）。
    **這不是規格，是被迫挑的一邊；客戶裁哪一邊，改的只有這一行。**
    """
    token = _HINT_SUFFIX.set(HINT if demo_hint else "")
    try:
        return _build_page_model(
            dataset, fields=fields, viewport_width=viewport_width, open_fund=open_fund,
            applied_window=applied_window, applied_rules=applied_rules,
        )
    finally:
        _HINT_SUFFIX.reset(token)


def _build_page_model(
    dataset, *, fields, viewport_width, open_fund, applied_window=None, applied_rules=None
) -> dict:
    # 📌 2026-10-05「讀取失敗不說空」（客戶 2026-10-05 核准開工）：讀不到不等於空。
    #    設定或持倉表讀取失敗時，不從空列表推出「未設定」或「尚未建立任何持倉」。
    errors = dataset.get("errors", {})
    settings_error = errors.get("user_setting")
    holding_error = errors.get("holding")
    if settings_error and dataset.get("user_setting"):
        # 呼叫端契約（客戶 2026-10-05 裁示）：解析器回傳問題訊息時交空列表，不交部分結果。
        # 帶著列又帶著失敗，是上游組錯；不猜要信哪一邊（§1，體例同 `fund_errors()` 點名持倉以外的代碼就 raise）。
        raise ValueError(
            f"errors 帶 user_setting 時，user_setting 必須是空列表，收到：{dataset['user_setting']!r}"
        )
    # ~~「未知」只在值取自存過的設定時成立；按過「套用」的那一份是欄位當下值，照用。~~
    # → 📌 2026-10-05 更正（有意識的更正，不是漏刪；決策者：總管 2026-10-05 裁定；稽核乙 M-1 指出）：
    #    設定讀取失敗時，空白套用仍算未知。套用的區間兩格都空、或門檻一列也沒有，與沒按過「套用」一樣算未知；
    #    有值的那一半照用欄位當下值。理由：設定讀不到時 HLD-4 的欄位帶不出存過的值，本來就是空的，
    #    按「套用」交出的空白不表示使用者沒有設定。
    #    舊表述在寫下當時撐得住（按過「套用」的那一份確實是欄位當下值）；被權衡掉的是它沒有分有值與空白 ——
    #    空白套用之後「未設定」字句又回到畫面上，與「⛔ 取數失敗：<原文>」同時出現。
    #    設定讀得到時照舊：清空再套用說「尚未設定」，那是真的沒設定。
    window_unknown = bool(settings_error) and (applied_window is None or not any(applied_window))
    rules_unknown = bool(settings_error) and not applied_rules
    # 持倉表有取數失敗、而且一列也沒有讀到：這時不能說「尚未建立任何持倉」。
    holding_unknown = bool(holding_error) and not dataset.get("holding")
    applied_window = saved_window(dataset) if applied_window is None else tuple(applied_window)
    rules = saved_rules(dataset) if applied_rules is None else list(applied_rules)
    # `holding_id` 先驗（`44` 4.1 主鍵）：`fund_metrics()` 與 `_build_hld5()` 都直接拿它當鍵。
    _check_holding_ids(dataset.get("holding", []))
    # `fund_errors` 形狀先驗：空持倉時 `fund_metrics()` 一次也不會跑，壞形狀不得因此靜默通過（§1）。
    fund_errors(dataset)
    metrics = all_metrics(dataset, applied_window, window_error=settings_error if window_unknown else None)
    has_holdings = bool(dataset.get("holding"))
    has_window = window_is_valid(applied_window)

    fields = dict(fields) if fields else {
        "window_start": applied_window[0],
        "window_end": applied_window[1],
    }

    hld1 = _build_hld1(
        metrics, rules, has_holdings=has_holdings,
        fail_message=source_error(dataset, "HLD-1"),
        unsurfaced=unsurfaced_source_error(dataset, "HLD-1"),
        pending=pending_tables(dataset),
        settings_error=settings_error,
        rules_unknown=rules_unknown,
        holding_unknown=holding_unknown,
    )
    hld2 = _build_core_card(
        "HLD-2",
        metrics,
        ("區間報酬率", "期間波動"),
        has_holdings=has_holdings,
        has_window=has_window,
        fail_message=source_error(dataset, "HLD-2"),
        unsurfaced=unsurfaced_source_error(dataset, "HLD-2"),
        window_unknown=window_unknown,
        holding_unknown=holding_unknown,
        subtitle="兩個主值。各值以原幣計算，逐檔寫出幣別字面值；"
        "本卡沒有任何跨幣別的合計、平均或比值。",
        moved_note=HLD2_MOVED_NOTE,
    )
    hld3 = _build_core_card(
        "HLD-3",
        metrics,
        ("期間配息合計", "配息佔淨值比"),
        has_holdings=has_holdings,
        has_window=has_window,
        fail_message=source_error(dataset, "HLD-3"),
        unsurfaced=unsurfaced_source_error(dataset, "HLD-3"),
        window_unknown=window_unknown,
        holding_unknown=holding_unknown,
        subtitle="兩個主值，皆為算術結果，卡上不對它們加任何評語。"
        "配息合計以原幣逐檔顯示，逐檔寫出幣別字面值；"
        "本卡沒有任何跨幣別的合計、平均或比值。",
        moved_note=HLD3_MOVED_NOTE,
    )
    cards = [hld1, hld2, hld3]
    hld0 = _build_hld0(
        cards,
        has_holdings=has_holdings,
        has_rules=bool(rules),
        # S6a-2 第 2 項（N1，客戶 2026-10-03）：文案字面是「有 N 檔超出」，N 數**不重複的 fund_code**。
        # ~~`len(hld1["_rows"])`~~（列數：同一檔超出兩條門檻會算兩次，持倉 3 檔卻寫「有 4 檔超出」）。
        # HLD-1 偏離表的列數不變。與 `44` HLD-0 規則欄、判準與 HLD-1 判準（「N 與列數相等」）的偏離，
        # 客戶 2026-10-03 裁示登記在 `ACCEPTANCE.md` 第九節；HLD-1 卡尾那一句的後半句同日刪去。
        deviation_count=len({row["_fund_code"] for row in hld1["_rows"]}),
        holding_unknown=holding_unknown,
        rules_unknown=rules_unknown,
    )
    blocks = [
        hld0,
        hld1,
        hld2,
        hld3,
        _build_hld4(
            applied_window=applied_window, fields=fields, rules=rules,
            settings_error=settings_error, window_unknown=window_unknown, rules_unknown=rules_unknown,
        ),
        _build_hld5(
            dataset, metrics, open_fund=open_fund, has_window=has_window,
            window_unknown=window_unknown, settings_error=settings_error,
            holding_error=holding_error, holding_unknown=holding_unknown,
        ),
        _build_hld6(dataset),
        _build_hld7(metrics, hld1["_rows"], has_holdings=has_holdings),
        _build_hld8(
            metrics, has_holdings=has_holdings, has_window=has_window,
            window_unknown=window_unknown, settings_error=settings_error,
            holding_error=holding_error, holding_unknown=holding_unknown,
        ),
    ]

    return {
        "title": PAGE_TITLE,
        "answers": PAGE_ANSWERS,
        "_viewport_width": viewport_width,
        "_columns": columns_for_width(viewport_width),
        "_window": applied_window,
        "blocks": blocks,
        # `44` 3.2：本頁不負責什麼。
        "footer_lines": [
            "不挑新標的，那是標的探索",
            "不談市場環境，那是市場總覽",
            "不決定要不要調整 —— 本頁只呈現偏離，處置方向不在本頁產生",
            "偏離提示只客觀描述現況與目標差距；門檻與區間由使用者自行輸入",
        ],
        "footer_badges": [_redline_badge("G2†"), _redline_badge("G3†")],
    }


# ───────────────────────── 查詢與掃描 ─────────────────────────


def all_blocks(model: dict) -> list:
    return list(model["blocks"])


def find_block(model: dict, code: str) -> dict:
    for block in model["blocks"]:
        if block["code"] == code:
            return block
    raise KeyError(code)


def codes_in_layer(model: dict, layer: int) -> list:
    return [b["code"] for b in model["blocks"] if b["_layer"] == layer]


def fund_group(block: dict, fund_code: str) -> dict:
    for group in block.get("fund_groups", []):
        if group["_fund_code"] == fund_code:
            return group
    raise KeyError(fund_code)


def find_row(block: dict, fund_code: str) -> dict:
    for row in block.get("_rows", []):
        if row["_fund_code"] == fund_code:
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


def collect_badges(model: dict) -> list:
    return [n for n in _walk(model) if isinstance(n, dict) and "_kind" in n and "text" in n]


def collect_buttons(model: dict) -> list:
    return [n for n in _walk(model) if isinstance(n, dict) and "_action_kind" in n]


def collect_inputs(model: dict) -> list:
    return [n for n in _walk(model) if isinstance(n, dict) and n.get("_input") is True]


def value_nodes(model) -> list:
    return [n for n in _walk(model) if isinstance(n, dict) and n.get("_value_node")]


def numeric_nodes(model) -> list:
    return [n for n in value_nodes(model) if n["_has_number"]]


def non_ok_value_nodes(model) -> list:
    return [n for n in value_nodes(model) if n["_state"] != STATE_OK]


def empty_state_texts(model) -> set:
    """全頁用到的空狀態文案。

    母體不只主值位置 —— `44` HLD-4 把「⬜ 不適用：尚未設定區間」放在**核心卡的副標**，
    所以只掃主值會漏掉它。這裡收兩種：主值位置的字串，
    加上任何一句**恰好是**不適用／資料未備／取數失敗模板本身的畫面文字
    （帶來源鍵或帶訊息原文的那幾句不算 —— 它們是那一句後面再接東西，不是同一句）。
    """
    texts = {n["text"] for n in non_ok_value_nodes(model)}
    for line in collect_ui_strings(model):
        if line in (ND_TEXT, ERR_TEXT) or line.startswith("⬜ 不適用："):
            texts.add(line)
    return texts


def cross_currency_nodes(model) -> list:
    """把兩種幣別的數合成一個值的節點。`44` 5.1「同一張卡不混不同幣別做平均」、
    `HLD-2` 判準「沒有任何一個跨幣別的合計數」、`HLD-8`「本表不做任何跨幣別的合計、平均或比值」。

    ⚠️ **舊版從來沒有守到東西**：它要求「同一個 `text` 字串裡出現兩個幣別字面值」，
    而本頁的百分比不帶幣別、金額只帶一個 —— 實測六情境每個節點的幣別命中數恆為 1，
    **那個條件永遠不成立**。稽核把一個真的跨幣別平均塞進核心卡，舊版毫無反應。

    現行改為**歸屬檢查**：每一個出數的值都必須掛在某一檔底下，且幣別與那一檔相同。
    一個跨幣別的合計／平均／比值，**要嘛掛不到任何一檔底下**（卡層級或表層級的合計），
    **要嘛幣別對不上它所在的那一檔** —— 兩條路都會被抓到。
    """
    bad = []
    for block in model["blocks"]:
        containers = list(block.get("fund_groups", ())) + [
            row for row in block.get("_rows", ()) if isinstance(row, dict) and "_fund_code" in row
        ]
        owned = set()
        for container in containers:
            ccy = container.get("_ccy")
            for node in value_nodes(container):
                owned.add(id(node))
                if not node["_has_number"]:
                    continue
                if not isinstance(ccy, str) or not ccy or node["_ccy"] != ccy:
                    bad.append(node)
        for node in value_nodes(block):
            # 掛不到任何一檔底下的出數值 —— 那正是一個跨幣別合計會長的樣子。
            if node["_has_number"] and id(node) not in owned:
                bad.append(node)
    return bad


def block_value_strings(block: dict) -> list:
    return [n["text"] for n in value_nodes(block)]


def value_shown_in_block(model, owner_code, fund_code, indicator) -> str:
    """那一塊上實際顯示的字串。`44` HLD-7 判準要的就是這個。"""
    block = find_block(model, owner_code)
    if owner_code in ("HLD-2", "HLD-3"):
        for mv in fund_group(block, fund_code)["main_values"]:
            if mv["label"] == indicator:
                return mv["text"]
    elif owner_code == "HLD-8":
        row = find_row(block, fund_code)
        key = "drawdown" if indicator == "最大回撤" else "principal"
        return row[key]["text"]
    elif owner_code == "HLD-1":
        for row in block["_rows"]:
            if row["_fund_code"] == fund_code and row["trace_indicator"] == indicator:
                return row["delta_text"]
    raise KeyError((owner_code, fund_code, indicator))


def collect_ui_strings(model: dict) -> list:
    """把介面全頁文字抓成一份清單（`44` 1.2 節判準）。

    刻意連機器用的鍵一起走過 —— 寧可多抓，不可漏抓。
    ⚠️ 走的是**模型**，不是本檔的原始碼 —— 禁令字表住在本檔的常數裡，
    所以它不會掃到自己（負控不落文件）。
    """
    out = []

    def walk(node):
        if isinstance(node, str):
            out.append(node)
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple, set)):
            for value in node:
                walk(value)

    walk(model)
    return out


def scan_forbidden(strings) -> dict:
    """禁方向詞 ＋ 禁箭頭的字表掃描。回傳 {詞: [命中的字串]}，全清時回 {}。"""
    hits = {}
    for term in FORBIDDEN_DIRECTION_WORDS + FORBIDDEN_ARROWS:
        matched = [s for s in strings if isinstance(s, str) and term in s]
        if matched:
            hits[term] = matched
    return hits
