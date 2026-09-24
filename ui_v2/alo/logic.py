# -*- coding: utf-8 -*-
"""資產配置純邏輯。零 streamlit import、零舊 repo import、零網路。

所有判定住在這裡；page.py 只負責把 build_page_model() 產出的模型畫出來。
模型慣例：底線開頭的鍵是**機器用**（狀態、色調、層號…），不開頭底線的鍵是**畫面文字**。

規格來源只有 `44` 第三節第四小節（`ALO-0`～`ALO-7`）、它引用的第四節資料表與第五節元件規則。
**`44` 與已拍板線框 `ui_prototype_alo.html` 不一致處一律照 `44`**，逐處登記在 `GAPS`。
`44` 沒寫、不決定就畫不出來的地方，照最保守的畫法做，同樣登記在 `GAPS`，
**不自行發明規格、按鈕、欄位或資料源**。

⚠️ 本頁只呈現**使用者自己輸入的目標**與**算術差距**。不給方向、不排先後、不標哪一組較好（G1†／G3†）。
"""

from __future__ import annotations

import csv
import io
import math
from datetime import datetime, timedelta, timezone

# ───────────────────────── 缺口與矛盾登記（`44` 沒寫或與線框不一致） ─────────────────────────
#
# ⛔ 每一筆都是**登記，不是動工授權**；本頁照每一筆寫的畫法做，不替 `44` 補規格。
#    代號在程式碼裡被引用的地方，就是那個畫法落地的地方（`test_缺口登記表每一筆都在原始碼裡被引用`）。
GAPS = {
    "ALO-GAP-線框導覽鈕": (
        "線框把 ALO-4 那一枚「前往 Sheets 維護持倉」畫成持倉表不為空時才出現；"
        "44 現行規則欄（2026-09-24 客戶裁示）是只在持倉表為空時出現，44 已登記線框待重繪。本頁照 44。"
    ),
    "ALO-GAP-取數失敗": (
        "資產配置頁八塊的空狀態欄沒有一塊寫出取數失敗那一句；本頁照 44 第五節第五小節「系統錯誤」的通用模板"
        "（⚠ 取數失敗：<訊息原文>，紅）畫在受影響的塊。模板帶的那一枚「重新取數」依同小節「空狀態欄整格為準」不畫。"
        "本頁處理 holding／nav／market_indicator／policy／user_setting 五張表的取數失敗，"
        "依各塊的來源（44 來源欄，加上本頁判讀的依賴，例如 ALO-6 跟著 ALO-4 的基準）判定受影響的塊；其餘表收到才炸。"
    ),
    "ALO-GAP-失敗時導覽鈕": (
        "holding 取數失敗時持倉表是空還是有資料不知道；本頁不把它當成空，ALO-4 不掛導覽鈕、燈也不說尚未建立任何持倉。"
    ),
    "ALO-GAP-燈狀態字": (
        "取數失敗時燈維持灰（44 燈沒有紅），但狀態字不寫「中性」——那會與失敗的文案打架。"
        "本頁改印「狀態：取數失敗」這句事實描述，圖示用 ⚠；這一句是本頁擬的，44 沒寫。"
    ),
    "ALO-GAP-設定取數失敗": (
        "user_setting 取數失敗時，讀它的塊（ALO-1／2／3／4／6／7，ALO-0 經 ALO-2）該長什麼樣 44 沒寫。"
        "本頁照 5.5 系統錯誤模板畫，並且不畫那幾個輸入欄與「⬜ 未設定」——值是取不到，不是沒設定。存檔鈕照舊（其一）。"
    ),
    "ALO-GAP-缺匯率從嚴": (
        "market_indicator 取數失敗時，本頁讓整張 ALO-2 進系統錯誤，連只含新臺幣的類別也不算；"
        "44 對缺匯率寫的是只影響含外幣的那一類（其餘類別照算）。本頁對取數失敗從嚴，與缺匯率的畫法不同，據實登記。"
    ),
    "ALO-GAP-深色主題前提": (
        "本頁的對比是在 repo 根的 .streamlit/config.toml（base = dark、textColor #e6edf3）之下量的；"
        "Streamlit 元件（輸入欄、展開區標題、按鈕）的字色來自那份設定，不在本頁檔案裡。換成淺色主題，對比守衛的結論不成立。"
    ),
    "ALO-GAP-燈圖示共用": (
        "⚠ 本頁同時用於黃燈（狀態：要多看一眼）與取數失敗；44 的 ⚠ 只出現在取數失敗的模板裡。"
        "本輪不改圖示（屬畫面設計），待客戶裁。"
    ),
    "ALO-GAP-保單失敗從嚴": (
        "policy 取數失敗時本頁讓整張 ALO-6 進系統錯誤（紅）；44 ALO-6 來源欄裡 policy 只供保單名一欄。"
        "本頁從嚴，不只把那一欄標失敗，據實登記。"
    ),
    "ALO-GAP-無紅燈": (
        "ALO-0 規則欄只給灰與黃兩色（線框 A-01），燈沒有紅。紅只出現在受取數失敗影響的卡與展開區，燈維持灰、文案照抄 ALO-2 的失敗字串。"
    ),
    "ALO-GAP-燈讀不到差距": (
        "基準未選、或某個有目標的類別差距算不出來（缺匯率、目標比重留空）時，ALO-0 該出哪一句，44 沒寫。"
        "本頁燈為灰，文案取 ALO-2 那一格已經顯示的空狀態字串；不宣稱「各類別皆在容許帶內」。"
    ),
    "ALO-GAP-燈的正負號": (
        "ALO-0 的「差 N 個百分點」帶不帶正負號 44 沒寫（線框 A-22）。"
        "來源欄取的是絕對值、規則欄寫燈不指出方向，本頁印絕對值。"
    ),
    "ALO-GAP-端點": (
        "差距剛好等於容許帶算內還是外，44 沒寫（線框 A-31）。本頁判讀：44 ALO-0 寫「超出容許帶 → 燈為黃」，"
        "相等不算超出，算帶內（燈灰、內外欄寫內）。"
    ),
    "ALO-GAP-同差並列": (
        "帶外有兩個以上類別並列最大絕對差距時，燈的點名方式 44 未寫，本頁全列：依 alo_bucket_names 的順序以頓號列出，"
        "不另造評語。皆在帶內時照 44 寫各類別皆在容許帶內。"
    ),
    "ALO-GAP-灰字落點": (
        "「目標合計 X%」那一行灰字的落點 44 自己登記為待裁（本檔四層結構沒有頁首）。"
        "本頁照規則欄現行字面「頁面頂端」畫在層 1 之上；X 取合計乘以一百（44 標為可推翻）。"
    ),
    "ALO-GAP-新增類別": (
        "ALO-1 要使用者新增與命名類別，規則欄又寫本塊只掛「存檔」一枚；新增一列的元件 44 沒有宣告（線框 A-18）。"
        "本頁不畫新增鈕，目標列只呈現已存的那幾列。"
    ),
    "ALO-GAP-當下值或已存值": (
        "ALO-2 吃 ALO-1 的當下值還是已存值，44 塊下方登記為待裁（其二）。本頁讀已存值，並寫在 ALO-2 卡上。"
    ),
    "ALO-GAP-存檔停用": "「存檔」什麼時候停用 44 沒訂（其一）。本頁三枚存檔都不宣告停用條件。",
    "ALO-GAP-留空列存不存": "比重或金額留空的那一列存不存得下來 44 沒訂（其三）。本頁的假資料照已存的樣子呈現。",
    "ALO-GAP-未分類無目標": (
        "「未分類」那一列沒有目標比重（線框 A-07）。本頁三格畫 ⬜，不當成目標 0，燈也不讀它。"
    ),
    "ALO-GAP-分母": (
        "某類別缺匯率被排除時，其餘類別的分母 44 沒寫（線框 A-09）。本頁分母不含被排除的類別，卡上寫合計未涵蓋。"
    ),
    "ALO-GAP-非美元幣別": (
        "44 全檔唯一的匯率鍵是 fx_twd_per_usd（線框 A-08），而 holding.ccy 不限美元。"
        "市值基準碰到新臺幣與美元以外的幣別時本頁炸掉，不自行發明匯率鍵。"
    ),
    "ALO-GAP-匯率對齊鍵": (
        "ALO-2 來源欄寫取 obs_date 不晚於淨值日的最近一筆，而 market_indicator 表規則寫跨期間對齊一律用 release_date。"
        "本頁照塊規則（obs_date），兩句不一致登記在此。"
    ),
    "ALO-GAP-類別名不符": (
        "holding.bucket 有值、卻不在 alo_bucket_names 裡時怎麼歸，44 沒寫。本頁併入「未分類」並在 ALO-4 另列出來。"
    ),
    "ALO-GAP-內外不著色": "容許帶內外欄著不著色 44 沒寫（線框 A-19）。本頁不著色，純文字。",
    "ALO-GAP-容許帶未設內外欄": "ALO-2 沒有「容許帶未設」這一種空狀態（線框 A-20）。本頁內外欄畫 ⬜ 未設定，差額照算。",
    "ALO-GAP-ALO3目標": "ALO-3 來源欄沒有宣告目標，規則欄卻要算新差額（線框 A-17）。本頁取 ALO-1 的已存目標。",
    "ALO-GAP-ALO3上游": (
        "ALO-2 因持倉表為空或基準未選而沒有列時，ALO-3 該顯示什麼 44 只寫了目標未設那一種。"
        "本頁 ALO-3 照抄 ALO-2 那一格的空狀態字串。"
    ),
    "ALO-GAP-ALO3類別不在清單": (
        "試算輸入點名一個 ALO-2 沒有的類別時 44 沒寫。本頁照 44 第五節「算不出來」模板在該列列尾寫不適用，那一列不生效，不自己開一列。"
    ),
    "ALO-GAP-試算總額": (
        "試算後各類別合計為零或負時比重算不出來，44 沒寫。本頁在 ALO-3 卡上照「算不出來」模板寫不適用，不出任何比重。"
    ),
    "ALO-GAP-新增假設與只掛一枚": (
        "ALO-3 空狀態欄要一枚「新增假設」，規則欄寫本塊只掛「存檔」一枚。本頁照空狀態欄：輸入零列時兩枚都在。"
    ),
    "ALO-GAP-提示文字": "ALO-3 輸入零列時的「提示文字」44 沒給字面。本頁印第四節未設定鍵的字面「⬜ 未設定」。",
    "ALO-GAP-金額標籤": "ALO-3 只給欄名 amount_twd，沒有畫面標籤（線框 A-30）。本頁標籤寫欄名本身。",
    "ALO-GAP-指派欄": "ALO-4 判準點名的「指派欄」44 沒有宣告（44 已登記）。本頁把每檔的類別畫成唯讀表格的一欄。",
    "ALO-GAP-導覽目的地": "「前往 Sheets 維護持倉」要開哪一個位址 44 沒給。本頁的按鈕不接任何連結。",
    "ALO-GAP-導覽改指派": (
        "裁示後那一枚只在持倉表為空時出現，而規則欄原文說它帶使用者去改指派——出現時沒有指派可改（44 已登記）。"
    ),
    "ALO-GAP-缺匯率不帶鍵": "ALO-4 的缺換算匯率沒有帶鍵名、ALO-2 的有（線框 A-27）。本頁兩塊各照各自的字面。",
    "ALO-GAP-value_kind": "alo_basis 的值在 44 第四節 value_kind 六種裡對不上任何一種。假資料那一列放空，不補第七種。",
    "ALO-GAP-匯出兩組欄名": (
        "ALO-5 匯出「一份」表格檔，而 ALO-2 與 ALO-3 欄名不同（線框 A-23）。本頁一份檔內兩段，各帶自己的欄名列。"
    ),
    "ALO-GAP-無列判定": "ALO-2 只有一格空狀態時算不算「畫面上無列」44 沒寫（線框 A-24）。本頁判為無列，匯出停用。",
    "ALO-GAP-ALO6基準": "ALO-6 來源欄沒有宣告用誰的基準設定（線框 A-15）。本頁跟著 ALO-4 的已存基準。",
    "ALO-GAP-ALO6幣別": (
        "44 ALO-6 規則欄未列幣別欄（線框 A-16），本頁不顯示幣別欄；基準值一律是新臺幣，格內寫出 TWD。"
    ),
    "ALO-GAP-ALO6表尾": "「各類別內的佔比合計」有幾個類別就有幾個（線框 A-14）。本頁表尾逐類別各印一個，再加總體一個。",
    "ALO-GAP-排除顆粒": (
        "缺基準值時 ALO-2 排除整個類別、ALO-6 只排除那一檔，兩塊的佔總體比例因此不同。本頁照各塊字面，不統一。"
    ),
    "ALO-GAP-來源缺按鈕": (
        "第五節來源缺的模板帶一枚「重新取數」；ALO-2／ALO-6 的空狀態欄沒有寫那一枚，"
        "44 第五節第五小節「空狀態欄整格為準」→ 本頁不畫。"
    ),
    "ALO-GAP-ALO7值格": "alo_target_weights 那一列的當前值怎麼印 44 沒寫（線框 A-13）。本頁印「類別 比重」以全形斜線串起。",
    "ALO-GAP-ALO7兩句相撞": (
        "某鍵從未設定過時，值為空與 updated_at 為空兩句同時命中（線框 A-10）。本頁取值為空那一句（值格未設定、時間格 ⬜）。"
    ),
    "ALO-GAP-ALO7重疊": "ALO-7 與 ALO-1 回答同一件事，44 已登記待裁。本頁兩塊都照畫。",
    "ALO-GAP-時區": "第四節寫顯示時才轉當地時區，當地是哪一區 44 沒寫。本頁顯示 UTC+8 並把時區寫出來。",
    "ALO-GAP-輸入元件": "這一頁的輸入欄與基準二選一不屬第五節五類元件的任何一類（線框 A-26）。本頁照實畫，不硬塞成按鈕。",
    "ALO-GAP-示意標記": (
        "ui_v2/hld 與 ui_v2/exp 在每個數字後面加（示意）（ui_v2/mkt 沒有）；ALO-2 判準要求差額欄只有數字、小數點、正負號與百分點符號，"
        "本頁因此改為頁首一行涵蓋全頁，另在每一塊畫面上有數字的塊各加一行「本塊數字皆為示意值」，不逐數加註。"
    ),
    "ALO-GAP-窄寬度表格": "卡內表格在窄寬度怎麼塌 44 沒寫（線框 A-33）。本頁讓格內文字換行，不出橫向捲動、不藏欄。",
    "ALO-GAP-節判準鏈": (
        "第二節節判準（抽掉被燈讀的卡、其餘核心卡數值不變）在本頁跑不過：燈只讀 ALO-2，ALO-3 也讀 ALO-2（44 已登記）。"
    ),
    "ALO-GAP-來源徽章": (
        "第五節卡片 ok 態要掛來源與新鮮度徽章，而本頁的來源 holding 與 user_setting 沒有 source_tier 與 fetched_at 欄。"
        "本頁不掛，不自己編一個層級。"
    ),
    "ALO-GAP-同類別兩列": "同一張保單同一檔基金登記成兩列而 bucket 不同時該歸哪一類 44 沒寫。本頁炸掉。",
}


# ───────────────────────── 常數（逐字引 `44`） ─────────────────────────

STATE_OK = "ok"
STATE_MISSING = "資料未備"
STATE_BIZ = "業務例外"

# `44` 5.2 徽章 `狀態` 那一列的七個字面值（封閉列舉）。
STATUS_BADGE_LITERALS = ("資料未備", "不適用", "取數失敗", "推估", "修正過", "部分缺", "未定義")

# `44` 5.3 按鈕：八類之外沒有第九類。
BUTTON_KINDS = ("取數", "套用", "展開", "匯出", "新增列", "清除", "導覽", "存檔")
# `44` 5.3 禁止欄：這四張表由 Sheets 維護，本儀表板唯讀。
READONLY_TABLES = ("holding", "policy", "nav", "dividend")
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

# `44` 1.2 呈現層禁令：禁方向詞、禁箭頭。
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
FORBIDDEN_ARROWS = ("↑", "↓", "▲", "▼")
# 比 `44` 1.2 更嚴的補充（總管 2026-09-24 裁定加入，只能更嚴、不能更鬆）。
FORBIDDEN_ADVICE_WORDS = ("應該調整", "應調", "該調整", "宜調")
# `44` 1.1 節判準：按鈕標籤四個禁詞。
FORBIDDEN_BUTTON_WORDS = ("一鍵", "最佳", "推薦", "最適")

# 塊名逐字引 `44` 3.4 的八個 `#### 塊 ALO-n｜…` 標題。
BLOCK_TITLES = {
    "ALO-0": "差距結論燈",
    "ALO-1": "目標輸入卡",
    "ALO-2": "目標對照卡",
    "ALO-3": "情境試算卡",
    "ALO-4": "分組定義",
    "ALO-5": "試算結果匯出",
    "ALO-6": "歸屬明細",
    "ALO-7": "目標修改紀錄",
}
BLOCK_LAYERS = {
    "ALO-0": 1,
    "ALO-1": 2,
    "ALO-2": 2,
    "ALO-3": 2,
    "ALO-4": 3,
    "ALO-5": 3,
    "ALO-6": 4,
    "ALO-7": 4,
}
# 各塊「回答什麼」。ALO-7 取的是現行那一句（舊那一句在 `44` 已劃線退役）。
ANSWERS = {
    "ALO-0": "我這一季需不需要打開這一頁細看",
    "ALO-1": "我自己寫下的目標比重是多少",
    "ALO-2": "各類別現在離我的目標差幾個百分點",
    "ALO-3": "如果我照自己想的數字動一筆，比重會變成多少",
    "ALO-4": "這些檔是怎麼被歸到那幾個類別的",
    "ALO-5": "我剛才看到的這張對照表，怎麼帶走",
    "ALO-6": "ALO-2 那幾個比重，是哪幾檔加起來的",
    "ALO-7": "現在的目標配置是什麼",
}

PAGE_TITLE = "資產配置"
# 44 逐字「我目前的分布，和我自己寫下的目標，差多少」
PAGE_ANSWERS = "我目前的分布，和我自己寫下的目標，差多少"
# `44` 3.4 頁首「不負責什麼」那一行，拆成三句。
NOT_RESPONSIBLE = (
    "不挑標的（那是標的探索）",
    "不產生再平衡動作（G1†）",
    "不談單檔績效好壞（那是持倉體檢）",
)
REDLINE_MARKS = ("G1†", "G2†", "G3†")

# ── 畫面文案（每一句都逐字取自 `44` 現行文字；`test_44逐字的文案常數每一句都在現行文字裡`） ──
TEXT_NO_HOLDING = "尚未建立任何持倉"
TEXT_NO_TARGET = "尚未設定目標"
TEXT_NO_TOLERANCE = "尚未設定容許帶"
TEXT_ALL_IN_BAND = "各類別皆在容許帶內"
TEXT_INTRO = "以下依序：目標 → 對照 → 試算"
TEXT_GOTO_SHEETS = "前往 Sheets 維護持倉"
TEXT_SHEETS_READONLY = "持倉資料在 Sheets 維護，本儀表板唯讀"
TEXT_UNSET = "⬜ 未設定"
TEXT_NOT_READY = "⬜ 資料未備"
TEXT_NA_NO_TARGET = "⬜ 不適用：尚未設定目標"
TEXT_NA_NO_BASIS = "⬜ 不適用：尚未選定比重基準"
TEXT_NA_OVERFLOW = "⬜ 不適用：假設金額超出該類別現值"
TEXT_FX_MISSING_ALO2 = "⬜ 資料未備：缺換算匯率 fx_twd_per_usd"
TEXT_FX_MISSING_ALO4 = "⬜ 資料未備：缺換算匯率"  # ALO-GAP-缺匯率不帶鍵
TEXT_NO_EXPORT_ROWS = "目前沒有可匯出的列"
TEXT_NO_SCENARIO_IN_EXPORT = "未含試算"
TEXT_NEVER_SET = "⬜ 資料未備：尚未設定過"
TEXT_SAVE_FAILED = "存檔寫入失敗"
TEXT_ADD_SCENARIO = "新增假設"
PAGE_HINT_NOTE = "資料為假資料，每一個數字都是示意值"
TEXT_NA_UNKNOWN_BUCKET = "⬜ 不適用：這一列的類別不在目標對照卡的類別清單內"
TEXT_NA_ZERO_TOTAL = "⬜ 不適用：試算後各類別合計不為正，比重算不出來"
TEXT_SAVE = "存檔"
TEXT_IN = "內"
TEXT_OUT = "外"
UNCLASSIFIED = "未分類"

VERBATIM_TEXTS = {
    "TEXT_NO_HOLDING": TEXT_NO_HOLDING,
    "TEXT_NO_TARGET": TEXT_NO_TARGET,
    "TEXT_NO_TOLERANCE": TEXT_NO_TOLERANCE,
    "TEXT_ALL_IN_BAND": TEXT_ALL_IN_BAND,
    "TEXT_INTRO": TEXT_INTRO,
    "TEXT_GOTO_SHEETS": TEXT_GOTO_SHEETS,
    "TEXT_SHEETS_READONLY": TEXT_SHEETS_READONLY,
    "TEXT_UNSET": TEXT_UNSET,
    "TEXT_NOT_READY": TEXT_NOT_READY,
    "TEXT_NA_NO_TARGET": TEXT_NA_NO_TARGET,
    "TEXT_NA_NO_BASIS": TEXT_NA_NO_BASIS,
    "TEXT_NA_OVERFLOW": TEXT_NA_OVERFLOW,
    "TEXT_FX_MISSING_ALO2": TEXT_FX_MISSING_ALO2,
    "TEXT_FX_MISSING_ALO4": TEXT_FX_MISSING_ALO4,
    "TEXT_NO_EXPORT_ROWS": TEXT_NO_EXPORT_ROWS,
    "TEXT_NO_SCENARIO_IN_EXPORT": TEXT_NO_SCENARIO_IN_EXPORT,
    "TEXT_NEVER_SET": TEXT_NEVER_SET,
    "TEXT_SAVE_FAILED": TEXT_SAVE_FAILED,
    "TEXT_ADD_SCENARIO": TEXT_ADD_SCENARIO,
    "UNCLASSIFIED": UNCLASSIFIED,
    "PAGE_ANSWERS": PAGE_ANSWERS,
}

# 44 逐字「燈不指出該往哪個方向調」—— 本頁的燈只寫類別名與差距大小（ALO-GAP-燈的正負號）。
# 44 逐字「差額只寫數字與正負號，不配箭頭、不著紅綠」
# 44 逐字「容許帶內外欄只寫「內」或「外」兩個字」
# 44 逐字「卡片不產生任何金額的候選值、不排出「先動哪一個」、不標示哪一組假設較好」
# 44 逐字「持倉表不為空時本塊不掛這一枚」

HINT_NOTE = "本塊數字皆為示意值"  # ALO-GAP-示意標記
DISPLAY_TZ = timezone(timedelta(hours=8))  # ALO-GAP-時區
DISPLAY_TZ_LABEL = "UTC+8"

BASIS_COST = "cost"
BASIS_MV = "mv"
BASIS_LABELS = {BASIS_COST: "成本（cost_twd）", BASIS_MV: "市值（淨值 × 單位數，美元依 fx_twd_per_usd 換算）"}
FX_KEY = "fx_twd_per_usd"

# ALO-GAP-燈圖示共用：黃燈與取數失敗都用 ⚠，待客戶裁。
_LAMP_LOOK = {
    "灰": ("⬜", "狀態：中性"),
    "黃": ("⚠", "狀態：要多看一眼"),
}
# ALO-GAP-燈狀態字：取數失敗時燈仍灰，但不寫「中性」。
_LAMP_LOOK_FAILED = ("⚠", "狀態：取數失敗")
# `44` 5.5 空狀態四種的顏色（本頁只用到其中三種）。
_EMPTY_TONE = {"來源缺": "灰", "算不出來": "黃", "部分缺": "黃", "系統錯誤": "紅"}


# ───────────────────────── 格式 ─────────────────────────


def format_number(value: float) -> str:
    """最多四位小數、去掉尾零（`0.9000000000000001` → `0.9`；`1.0` → `1`）。"""
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def format_share(pct: float) -> str:
    return f"{pct:.1f}%"


def format_pp(diff: float) -> str:
    """`44` 1.2：以正負號與數字寫出，不配箭頭。"""
    return f"{diff:+.1f} pp"


def format_twd(value: float) -> str:
    """新臺幣金額，逐格寫出幣別字面值（客戶設計引導第三條）。"""
    return f"{round(value):,} TWD"


def format_time(utc_text) -> str:
    """`44` 第四節：時間欄以世界協調時間存放，顯示時才轉當地時區（ALO-GAP-時區）。"""
    moment = datetime.strptime(utc_text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    local = moment.astimezone(DISPLAY_TZ)
    return f"{local:%Y-%m-%d %H:%M}（{DISPLAY_TZ_LABEL}）"


def empty_source_text(source_keys) -> str:
    """`44` 5.5 `來源缺` 的文案模板。"""
    return "⬜ 資料未備：" + " 與 ".join(source_keys) + " 尚無資料"


def not_applicable_text(reason: str) -> str:
    """`44` 5.5 `算不出來` 的文案模板。"""
    return "⬜ 不適用：" + reason


def fetch_failed_text(message: str) -> str:
    """`44` 5.5 `系統錯誤` 的文案模板。訊息原文照印，不改寫、不截斷。"""
    return "⚠ 取數失敗：" + message


# 本頁處理得了的取數失敗來源（ALO-GAP-取數失敗）。
FETCHABLE_TABLES = ("holding", "nav", "market_indicator", "policy", "user_setting")


def fetch_error(dataset, tables):
    """回第一張取數失敗的表的訊息原文，或 `None`。"""
    errors = dataset.get("errors") or {}
    for table in tables:
        if errors.get(table):
            return errors[table]
    return None


def _source_tables(basis):
    """ALO-2 的來源：holding（市值基準再加 nav 與匯率）＋ user_setting（目標、容許帶、基準、類別名稱）。
    ALO-GAP-缺匯率從嚴：market_indicator 失敗時整塊進系統錯誤。"""
    base = ("holding", "nav", "market_indicator") if basis == BASIS_MV else ("holding",)
    return base + ("user_setting",)


def settings_failure(dataset):
    return fetch_error(dataset, ("user_setting",))


# ───────────────────────── 斷點 ─────────────────────────


def columns_for_width(width_px: int) -> int:
    """`44` 2.1 客戶最終版：≤768 單欄／769-1279 兩欄／≥1280 三欄。"""
    if width_px <= 768:
        return 1
    if width_px <= 1279:
        return 2
    return 3


def layer_columns(layer: int, width_px: int) -> int:
    if layer in (1, 4):
        return 1
    if layer == 2:
        return columns_for_width(width_px)
    return min(2, columns_for_width(width_px))


# ───────────────────────── 元件工廠 ─────────────────────────


def status_badge(text: str) -> dict:
    if text not in STATUS_BADGE_LITERALS:
        raise ValueError(f"狀態徽章 {text!r} 不在 `44` 5.2 那七個之內")
    return {"_kind": "狀態", "text": text, "_tone": "灰" if text == "資料未備" else "黃"}


def _redline_badge(mark: str) -> dict:
    return {"_kind": "紅線", "text": mark, "_tone": "中性"}


def _button(label, kind, *, enabled=True, disabled_reason="", keys=()) -> dict:
    if kind not in BUTTON_KINDS:
        raise ValueError(f"按鈕類別 {kind!r} 不在 `44` 5.3 的八類之內")
    for word in FORBIDDEN_BUTTON_WORDS:
        if word in label:
            raise ValueError(f"按鈕標籤 {label!r} 含禁詞 {word!r}（`44` 1.1）")
    return {
        "_action_kind": kind,
        "_writes": set(_BUTTON_WRITES[kind]),
        "_keys": tuple(keys),
        "_enabled": bool(enabled),
        "label": label,
        "disabled_reason": disabled_reason,
    }


def _field(name, label, value, *, options=None) -> dict:
    """一個輸入欄。`_value` 是已存值，沒有就是 `None` —— 不放任何候選值（`44` 1.1 節判準）。"""
    # 畫面上的字串：浮點數走同一支格式（`4.0` 顯示為 `4`），與 ALO-7 的當前值同一個寫法。
    shown = "" if value is None else (format_number(value) if isinstance(value, float) else str(value))
    node = {"_input": True, "name": name, "label": label, "_value": value, "value_text": shown}
    if options is not None:
        node["_options"] = tuple(options)
    return node


def _placeholder(text: str, kind: str) -> dict:
    return {"text": text, "_empty_kind": kind, "_tone": _EMPTY_TONE[kind]}


# ───────────────────────── 讀資料 ─────────────────────────


def _setting_row(dataset, key):
    for row in dataset["user_setting"]:
        if row["setting_key"] == key:
            return row
    if settings_failure(dataset) is not None:
        # 取數失敗：值取不到。回一列空的，由各塊自己畫失敗框（ALO-GAP-設定取數失敗），不在這裡說成未設定。
        return {"setting_key": key, "setting_value": None, "value_kind": None, "updated_at": None}
    raise KeyError(f"user_setting 沒有 {key!r} 這一列")


def setting_value(dataset, key):
    return _setting_row(dataset, key)["setting_value"]


def setting_updated_at(dataset, key):
    return _setting_row(dataset, key)["updated_at"]


def aggregated_holdings(dataset) -> list:
    """`44` 4.1：業務唯一鍵（`policy_id`, `fund_code`）；來源端登記成多列時顯示時加總成一列。"""
    merged, order = {}, []
    for row in dataset["holding"]:
        key = (row["policy_id"], row["fund_code"])
        if key not in merged:
            merged[key] = dict(row)
            order.append(key)
            continue
        base = merged[key]
        if base["bucket"] != row["bucket"]:
            raise ValueError(f"{key} 兩列的 bucket 不同（ALO-GAP-同類別兩列）")
        for column in ("units_shares", "cost_orig_ccy", "cost_twd"):
            base[column] = base[column] + row[column]
    return [merged[key] for key in order]


def latest_nav(dataset, fund_code):
    """`44` ALO-6 來源欄：`nav.nav_orig_ccy` 最近一筆。"""
    rows = [r for r in dataset["nav"] if r["fund_code"] == fund_code]
    return max(rows, key=lambda r: r["nav_date"]) if rows else None


def fx_for_date(dataset, nav_date):
    """44 逐字「取 `obs_date` 不晚於 `nav.nav_date` 的最近一筆」（ALO-GAP-匯率對齊鍵）。"""
    rows = [
        r
        for r in dataset["market_indicator"]
        if r["indicator_key"] == FX_KEY and r["obs_date"] <= nav_date
    ]
    return max(rows, key=lambda r: r["obs_date"])["value_num"] if rows else None


def basis_value(dataset, holding, basis):
    """回 (新臺幣值 或 None, 缺值原因字串 或 None)。"""
    if basis == BASIS_COST:
        return float(holding["cost_twd"]), None
    nav = latest_nav(dataset, holding["fund_code"])
    if nav is None:
        return None, empty_source_text(["nav"])
    value = holding["units_shares"] * nav["nav_orig_ccy"]
    if nav["ccy"] == "TWD":
        return value, None
    if nav["ccy"] != "USD":
        raise ValueError(f"{holding['fund_code']} 的幣別 {nav['ccy']} 沒有對應的換算匯率鍵（ALO-GAP-非美元幣別）")
    rate = fx_for_date(dataset, nav["nav_date"])
    if rate is None:
        return None, TEXT_FX_MISSING_ALO2
    return value * rate, None


def category_of(holding, bucket_names) -> str:
    """`44` 4.1：`bucket` 空值表示未分類；不在類別名稱裡的也併入未分類（ALO-GAP-類別名不符）。"""
    bucket = holding["bucket"]
    if bucket is None or bucket not in (bucket_names or ()):
        return UNCLASSIFIED
    return bucket


# ───────────────────────── ALO-2（其餘幾塊都從這裡讀） ─────────────────────────


def _band_text(diff, tolerance):
    if tolerance is None:
        return TEXT_UNSET  # ALO-GAP-容許帶未設內外欄
    return TEXT_OUT if exceeds(diff, tolerance) else TEXT_IN


def exceeds(diff, tolerance) -> bool:
    """44 逐字「超出容許帶 → 燈為黃」。相等不算超出（ALO-GAP-端點，本頁判讀）。"""
    return abs(diff) > tolerance and not math.isclose(abs(diff), tolerance, abs_tol=1e-9)


def _category_values(dataset, basis, bucket_names):
    """回 {類別: {"value": float|None, "reason": str|None, "count": int}}，依持倉出現順序。"""
    values = {}
    for holding in aggregated_holdings(dataset):
        cat = category_of(holding, bucket_names)
        slot = values.setdefault(cat, {"value": 0.0, "reason": None, "count": 0})
        slot["count"] += 1
        value, reason = basis_value(dataset, holding, basis)
        if slot["reason"] is not None:
            continue
        if value is None:
            slot["value"], slot["reason"] = None, reason
        else:
            slot["value"] += value
    return values


def _row_order(targets, bucket_names, values):
    order = []
    for target in targets or ():
        if target["bucket"] not in order:
            order.append(target["bucket"])
    for name in bucket_names or ():
        if name in values and name not in order:
            order.append(name)
    if UNCLASSIFIED in values and UNCLASSIFIED not in order:
        order.append(UNCLASSIFIED)
    return order


def _build_alo2(dataset) -> dict:
    """ALO-GAP-來源徽章：本塊的來源沒有 source_tier／fetched_at 欄，不掛來源與新鮮度徽章。
    ALO-GAP-節判準鏈：燈只讀本塊、ALO-3 也讀本塊，第二節那一行節判準在本頁跑不過（44 已登記）。
    """
    holdings = aggregated_holdings(dataset)
    targets = setting_value(dataset, "alo_target_weights")
    tolerance = setting_value(dataset, "alo_tolerance_pp")
    basis = setting_value(dataset, "alo_basis")
    bucket_names = setting_value(dataset, "alo_bucket_names")

    placeholder = None
    failure = fetch_error(dataset, _source_tables(basis))
    # `44` 5.5：四種同時成立時取最嚴的一種，`系統錯誤` ＞ `來源缺` ＞ `算不出來`。
    if failure is not None:
        # ALO-GAP-取數失敗：通用模板，不畫重新取數。
        placeholder = _placeholder(fetch_failed_text(failure), "系統錯誤")
    elif not holdings:
        # ALO-GAP-來源缺按鈕：本塊空狀態欄沒有寫那一枚「重新取數」，本頁不畫。
        placeholder = _placeholder(empty_source_text(["holding"]), "來源缺")
    elif not targets:
        placeholder = _placeholder(TEXT_NA_NO_TARGET, "算不出來")
    elif basis is None:
        placeholder = _placeholder(TEXT_NA_NO_BASIS, "算不出來")

    rows, tail_lines, uncovered = [], [], []
    values = {}
    if placeholder is None:
        values = _category_values(dataset, basis, bucket_names)
        denominator = sum(v["value"] for v in values.values() if v["value"] is not None)
        if denominator <= 0:
            raise ValueError("目前比重的分母為零或負，44 沒有這種情形的畫法（fixtures 不會走到）")
        target_of = {t["bucket"]: t["weight_ratio"] for t in targets}
        for bucket in _row_order(targets, bucket_names, values):
            slot = values.get(bucket, {"value": 0.0, "reason": None, "count": 0})
            has_target = bucket in target_of
            weight = target_of.get(bucket)
            row = {
                "_bucket": bucket,
                "bucket_text": bucket,
                "_count": slot["count"],
                "_value": slot["value"],
                "_band_tone": "中性",  # ALO-GAP-內外不著色
                "_gap_text": None,
            }
            if slot["value"] is None:
                uncovered.append(bucket)  # ALO-GAP-分母
                row["_current_pct"] = None
                row["current_text"] = slot["reason"]
                row["_gap_text"] = slot["reason"]
            else:
                row["_current_pct"] = slot["value"] / denominator * 100.0
                row["current_text"] = format_share(row["_current_pct"])
            if not has_target:
                # ALO-GAP-未分類無目標：不當成目標 0。
                row["_target_pct"] = None
                row["target_text"] = "⬜"
            elif weight is None:
                row["_target_pct"] = None
                row["target_text"] = TEXT_NOT_READY
                row["_gap_text"] = row["_gap_text"] or TEXT_NOT_READY
            else:
                row["_target_pct"] = weight * 100.0
                row["target_text"] = format_share(row["_target_pct"])
            if row["_current_pct"] is None or row["_target_pct"] is None:
                row["_diff"] = None
                row["diff_text"] = "⬜"
                row["band_text"] = "⬜"
            else:
                # 44 逐字「差額的算式逐字釘死：當前值減目標值」—— 逐列各自相減，不先歸一。
                row["_diff"] = row["_current_pct"] - row["_target_pct"]
                row["diff_text"] = format_pp(row["_diff"])
                row["band_text"] = _band_text(row["_diff"], tolerance)
            row["_has_target"] = has_target
            # 有目標、卻因缺基準值算不出差距的那一列，燈不得跳過它（ALO-GAP-燈讀不到差距）。
            # 目標比重留空的那一列不算：它不計入合計，與「未分類」同樣沒有可比的目標。
            row["_blocks_lamp"] = row["_current_pct"] is None and row["_target_pct"] is not None
            rows.append(row)
        if UNCLASSIFIED in values:
            tail_lines.append(f"{UNCLASSIFIED} {values[UNCLASSIFIED]['count']} 檔")
            tail_lines.append("⚠ 44 沒有寫「未分類」的目標比重；本頁目標、差額、內外三格不算。")
        if uncovered:
            tail_lines.append("合計未涵蓋 " + "、".join(uncovered))

    cell_tones = set()
    for row in rows:
        if row["_gap_text"] == TEXT_FX_MISSING_ALO2 or row["target_text"] == TEXT_NOT_READY:
            cell_tones.add("灰")
    tone = placeholder["_tone"] if placeholder else ("灰" if cell_tones else "中性")
    return {
        "code": "ALO-2",
        "title": BLOCK_TITLES["ALO-2"],
        "answers": ANSWERS["ALO-2"],
        "_layer": 2,
        "_default_open": True,
        "_tone": tone,
        "_holdings_empty": not holdings,
        "_failed": failure is not None,
        "_bucket_names": tuple(bucket_names or ()),
        "_target_unset": not targets,
        "_tolerance": tolerance,
        "_values": values,
        "column_labels": ["類別", "目前比重", "目標比重", "差額", "容許帶內外"],
        "_rows": rows,
        "placeholder": placeholder,
        "tail_lines": tail_lines,
        "detail_lines": [
            # ALO-GAP-當下值或已存值（上畫面的體例同 ui_v2/exp：「⚠ 44 …；本頁…」）
            "⚠ 44 沒有寫本卡吃的是當下值還是已存值；本頁讀已存值（目標取 ALO-1、基準取 ALO-4 最後一次存檔的內容）。",
            HINT_NOTE,
        ],
        "buttons": [],
        "badges": [],
    }


# ───────────────────────── ALO-0 ─────────────────────────


def conclusion_light(alo2) -> dict:
    """`44` ALO-0。**只讀 ALO-2 已經算出來的值**，不自取數。

    空狀態三句的先後照 `44` 空狀態欄：持倉表為空 → 目標未設 → 容許帶未設，取到第一句就停。
    """
    if alo2["_failed"]:
        # ALO-GAP-無紅燈：燈沒有紅；燈為灰，文案照抄 ALO-2 那一格的失敗字串（不說成尚未建立持倉）。
        return {"_tone": "灰", "text": alo2["placeholder"]["text"], "_max_bucket": None}
    if alo2["_holdings_empty"]:
        return {"_tone": "灰", "text": TEXT_NO_HOLDING, "_max_bucket": None}
    if alo2["_target_unset"]:
        return {"_tone": "灰", "text": TEXT_NO_TARGET, "_max_bucket": None}
    if alo2["_tolerance"] is None:
        return {"_tone": "灰", "text": TEXT_NO_TOLERANCE, "_max_bucket": None}
    if alo2["placeholder"] is not None:
        # ALO-GAP-燈讀不到差距：基準未選。
        return {"_tone": "灰", "text": alo2["placeholder"]["text"], "_max_bucket": None}
    computed = [r for r in alo2["_rows"] if r["_diff"] is not None]
    blocked = [r for r in alo2["_rows"] if r["_blocks_lamp"]]
    if blocked:
        # ALO-GAP-燈讀不到差距：44 逐字「取絕對值最大者」—— 有一個有目標的類別差距算不出來時，
        # 最大者是哪一個就不知道；本頁不拿其餘類別的差距去點名，也不宣稱皆在帶內。
        return {"_tone": "灰", "text": blocked[0]["_gap_text"], "_max_bucket": None}
    outside = [r for r in computed if exceeds(r["_diff"], alo2["_tolerance"])]
    if not outside:
        # 含全部差 0、以及差距剛好等於容許帶（ALO-GAP-端點）。
        return {"_tone": "灰", "text": TEXT_ALL_IN_BAND, "_max_bucket": None}
    top = max(abs(r["_diff"]) for r in outside)
    leaders = [r["_bucket"] for r in outside if math.isclose(abs(r["_diff"]), top, abs_tol=1e-9)]
    # ALO-GAP-同差並列：全列，依 alo_bucket_names 的順序；不在名單裡的照 ALO-2 的列序排在後面。
    names = alo2["_bucket_names"]
    row_order = list(leaders)
    leaders = sorted(row_order, key=lambda b: (0, names.index(b)) if b in names else (1, row_order.index(b)))
    # ALO-GAP-燈的正負號：印絕對值。
    text = f"{'、'.join(leaders)} 與目標差 {top:.1f} 個百分點"
    return {"_tone": "黃", "text": text, "_max_bucket": leaders[0], "_leaders": tuple(leaders)}


def _build_alo0(alo2) -> dict:
    light = conclusion_light(alo2)
    glyph, state_word = _LAMP_LOOK_FAILED if alo2["_failed"] else _LAMP_LOOK[light["_tone"]]
    return {
        "code": "ALO-0",
        "title": BLOCK_TITLES["ALO-0"],
        "answers": ANSWERS["ALO-0"],
        "_layer": 1,
        "_default_open": True,
        "_reads": ("ALO-2",),
        "_tone": light["_tone"],
        "_max_bucket": light["_max_bucket"],
        "glyph": glyph,
        "state_word": state_word,
        "text": light["text"],
        "detail_lines": [
            "⚠ 44 沒有寫燈上的差距帶不帶正負號；本頁寫絕對值。本燈只讀 ALO-2 算出的差距，不指出方向。",
            HINT_NOTE,
        ],
        "buttons": [],
        "badges": [],
    }


# ───────────────────────── ALO-1 ─────────────────────────


def _save_error_lines(dataset, keys) -> list:
    errors = dataset.get("save_errors") or {}
    for key in keys:
        if errors.get(key):
            # 44 逐字「存檔寫入失敗 → 卡上顯示失敗訊息原文」—— 原文照印，不改寫、不截斷。
            return [TEXT_SAVE_FAILED + "：" + errors[key]]
    return []


def target_sum(targets):
    """`44` ALO-1：留空的那一列不計入合計。"""
    return sum(t["weight_ratio"] for t in targets or () if t["weight_ratio"] is not None)


def _build_alo1(dataset) -> dict:
    targets = setting_value(dataset, "alo_target_weights")
    tolerance = setting_value(dataset, "alo_tolerance_pp")
    keys = ("alo_target_weights", "alo_tolerance_pp")
    failure = settings_failure(dataset)
    inputs, rows = [], []
    # ALO-GAP-留空列存不存：留空的那一列照已存的樣子呈現。
    for index, target in enumerate(targets or ()):
        inputs.append(_field(f"alo_target_{index}_bucket", "類別", target["bucket"]))
        inputs.append(_field(f"alo_target_{index}_weight", "目標比重 weight_ratio", target["weight_ratio"]))
        weight = target["weight_ratio"]
        rows.append(
            {
                "_bucket": target["bucket"],
                "_weight": weight,
                "bucket_text": target["bucket"],
                "weight_text": "" if weight is None else format_number(weight),
                "tail_text": TEXT_NOT_READY if weight is None else "",
            }
        )
    if failure is None:
        inputs.append(_field("alo_tolerance_pp", "容許帶（百分點）", tolerance))
    sum_lines = []
    if targets:
        total = target_sum(targets)
        if not math.isclose(total, 1.0, abs_tol=1e-9):
            # 44 逐字「合計不等於 1 時卡上顯示合計值與差額，不自動歸一」
            sum_lines = [f"合計 {format_number(total)}", f"差額 {format_number(total - 1.0)}"]
    unset_lines = []
    if not targets and failure is None:
        unset_lines.append(TEXT_UNSET)
    if failure is not None:
        tolerance_text = ""  # 值取不到，不寫「未設定」（ALO-GAP-設定取數失敗）
    else:
        tolerance_text = TEXT_UNSET if tolerance is None else format_number(tolerance)
    return {
        "code": "ALO-1",
        "title": BLOCK_TITLES["ALO-1"],
        "answers": ANSWERS["ALO-1"],
        "_layer": 2,
        "_default_open": True,
        "_tone": "紅" if failure is not None else "中性",
        # ALO-GAP-設定取數失敗
        "placeholder": _placeholder(fetch_failed_text(failure), "系統錯誤") if failure is not None else None,
        "intro_line": TEXT_INTRO,
        "inputs": inputs,
        "_rows": rows,
        "column_labels": ["類別", "目標比重 weight_ratio"],
        "tolerance_text": tolerance_text,
        "tolerance_lines": [] if failure is not None else ["容許帶：" + tolerance_text],
        "sum_lines": sum_lines,
        "unset_lines": unset_lines,
        "error_lines": _save_error_lines(dataset, keys),
        # ALO-GAP-存檔停用：不宣告停用條件。ALO-GAP-新增類別：不畫新增鈕。
        "buttons": [_button(TEXT_SAVE, "存檔", keys=keys)],
        "detail_lines": [HINT_NOTE],
        "badges": [],
    }


def top_lines(dataset) -> list:
    """頁面頂端那一行灰字（ALO-GAP-灰字落點）。44 逐字「目標合計 X%」。"""
    targets = setting_value(dataset, "alo_target_weights")
    if not targets:
        return []
    total = target_sum(targets)
    if math.isclose(total, 1.0, abs_tol=1e-9):
        return []
    return [f"目標合計 {format_number(total * 100.0)}%"]


# ───────────────────────── ALO-3 ─────────────────────────


def _build_alo3(dataset, alo2) -> dict:
    scenario_rows = setting_value(dataset, "alo_scenario_input") or []
    keys = ("alo_scenario_input",)
    placeholder = None
    if alo2["placeholder"] is not None:
        # 目標未設那一種是 44 ALO-1 空狀態欄逐字寫的；另外兩種是 ALO-GAP-ALO3上游。
        placeholder = dict(alo2["placeholder"])

    rows_by_bucket = {r["_bucket"]: r for r in alo2["_rows"]}
    accepted = {}
    inputs, input_rows = [], []
    for index, item in enumerate(scenario_rows):
        amount = item["amount_twd"]
        inputs.append(_field(f"alo_scenario_{index}_bucket", "類別", item["bucket"]))
        # ALO-GAP-金額標籤
        inputs.append(_field(f"alo_scenario_{index}_amount", "金額 amount_twd", amount))
        tail, effective = "", False
        if amount is None:
            tail = TEXT_NOT_READY
        elif placeholder is None:
            base = rows_by_bucket.get(item["bucket"])
            if base is None:
                # ALO-GAP-ALO3類別不在清單：那一列不生效，列尾照「算不出來」模板寫。
                tail = TEXT_NA_UNKNOWN_BUCKET
            elif base["_value"] is None:
                tail = base["current_text"]
            elif base["_value"] + accepted.get(item["bucket"], 0.0) + amount < 0:
                tail = TEXT_NA_OVERFLOW
            else:
                accepted[item["bucket"]] = accepted.get(item["bucket"], 0.0) + amount
                effective = True
        input_rows.append(
            {
                "bucket_text": item["bucket"],
                "amount_text": "⬜" if amount is None else format_twd(amount),
                "tail_text": tail,
                "_effective": effective,
            }
        )

    result_rows = []
    total_note = None
    if placeholder is None and scenario_rows:
        new_values = {
            r["_bucket"]: r["_value"] + accepted.get(r["_bucket"], 0.0)
            for r in alo2["_rows"]
            if r["_value"] is not None
        }
        total = sum(new_values.values())
        if total <= 0:
            # ALO-GAP-試算總額：不出任何比重，卡上照「算不出來」模板寫。
            total_note = _placeholder(TEXT_NA_ZERO_TOTAL, "算不出來")
        for base in (alo2["_rows"] if total_note is None else ()):
            row = {"_bucket": base["_bucket"], "bucket_text": base["bucket_text"]}
            if base["_value"] is None:
                row["_share_pct"], row["share_text"] = None, base["current_text"]
                row["_new_diff"], row["new_diff_text"] = None, "⬜"
            else:
                row["_share_pct"] = new_values[base["_bucket"]] / total * 100.0
                row["share_text"] = format_share(row["_share_pct"])
                if base["_target_pct"] is None:
                    row["_new_diff"], row["new_diff_text"] = None, "⬜"
                else:
                    # ALO-GAP-ALO3目標：目標取 ALO-1 的已存值（經 ALO-2）。
                    row["_new_diff"] = row["_share_pct"] - base["_target_pct"]
                    row["new_diff_text"] = format_pp(row["_new_diff"])
            result_rows.append(row)

    buttons = []
    unset_lines = []
    if not scenario_rows and settings_failure(dataset) is None:
        # ALO-GAP-提示文字；ALO-GAP-新增假設與只掛一枚
        unset_lines.append(TEXT_UNSET)
        buttons.append(_button(TEXT_ADD_SCENARIO, "新增列"))
    buttons.append(_button(TEXT_SAVE, "存檔", keys=keys))
    if total_note is not None:
        placeholder = total_note
    tones = {placeholder["_tone"]} if placeholder else set()
    if any(r["tail_text"] == TEXT_NA_UNKNOWN_BUCKET for r in input_rows):
        tones.add("黃")
    if any(r["tail_text"] == TEXT_NA_OVERFLOW for r in input_rows):
        tones.add("黃")
    if any(r["tail_text"].startswith("⬜ 資料未備") for r in input_rows):
        tones.add("灰")
    tone = next((c for c in ("紅", "黃", "灰") if c in tones), "中性")
    return {
        "code": "ALO-3",
        "title": BLOCK_TITLES["ALO-3"],
        "answers": ANSWERS["ALO-3"],
        "_layer": 2,
        "_default_open": True,
        "_tone": tone,
        "inputs": inputs,
        "input_labels": ["類別", "金額 amount_twd", ""],
        "input_rows": input_rows,
        "column_labels": ["類別", "試算後比重", "與目標的新差額"],
        "_rows": result_rows,
        "placeholder": placeholder,
        "unset_lines": unset_lines,
        "error_lines": _save_error_lines(dataset, keys),
        "buttons": buttons,
        "detail_lines": [HINT_NOTE, "試算只是算術結果，列的順序照 ALO-2，不代表先後"],
        "badges": [],
    }


# ───────────────────────── ALO-4 ─────────────────────────


def _fx_missing_for_mv(dataset) -> bool:
    for holding in aggregated_holdings(dataset):
        nav = latest_nav(dataset, holding["fund_code"])
        if nav is not None and nav["ccy"] == "USD" and fx_for_date(dataset, nav["nav_date"]) is None:
            return True
    return False


def _build_alo4(dataset) -> dict:
    holdings = aggregated_holdings(dataset)
    basis = setting_value(dataset, "alo_basis")
    bucket_names = setting_value(dataset, "alo_bucket_names")
    keys = ("alo_basis", "alo_bucket_names")

    setting_failed = settings_failure(dataset) is not None
    inputs = (
        []
        if setting_failed
        else [_field("alo_basis", "比重基準", basis, options=(BASIS_COST, BASIS_MV))]
    )
    for index, name in enumerate(bucket_names or ()):
        inputs.append(_field(f"alo_bucket_name_{index}", f"類別名稱 {index + 1}", name))

    assign_rows, unassigned, mismatched = [], [], []
    for holding in holdings:
        fund_text = f"{holding['fund_name']}（{holding['fund_code']}）"
        bucket = holding["bucket"]
        # ALO-GAP-指派欄：唯讀，畫面上沒有任何可以改它的輸入元件。
        assign_rows.append(
            {
                "_fund_code": holding["fund_code"],
                "_readonly": True,
                "fund_text": fund_text,
                "bucket_text": bucket if bucket is not None else TEXT_UNSET,
                "category_text": category_of(holding, bucket_names),
            }
        )
        if bucket is None:
            unassigned.append(f"未指派：{fund_text}")
        elif bucket not in (bucket_names or ()):
            mismatched.append(f"類別名稱裡沒有「{bucket}」：{fund_text} 併入{UNCLASSIFIED}")

    detail_lines = []
    failure = fetch_error(dataset, _source_tables(basis))
    fail_nodes = [_placeholder(fetch_failed_text(failure), "系統錯誤")] if failure is not None else []
    fx_missing = failure is None and basis == BASIS_MV and bool(holdings) and _fx_missing_for_mv(dataset)
    if fx_missing:
        # 44 ALO-4 空狀態：基準不自動退回成本。ALO-GAP-缺匯率不帶鍵。
        detail_lines.append(TEXT_FX_MISSING_ALO4)
    detail_lines.append("每一檔的類別在 Sheets 維護，本塊唯讀呈現；本塊的存檔只寫比重基準與類別名稱兩鍵")
    detail_lines.append(HINT_NOTE)

    buttons = []
    goto_note = None
    holdings_empty = not holdings and fetch_error(dataset, ("holding",)) is None
    if holdings_empty:
        # ALO-GAP-失敗時導覽鈕：holding 取數失敗時持倉表是空是滿不知道，不當成空，不掛這一枚。
        # 44 逐字「本塊在持倉表為空時掛一枚「前往 Sheets 維護持倉」按鈕」
        # ALO-GAP-線框導覽鈕：線框畫的是相反面，照 44。ALO-GAP-導覽目的地：不接連結。
        # ALO-GAP-導覽改指派：出現時沒有指派可改，44 已登記。
        buttons.append(_button(TEXT_GOTO_SHEETS, "導覽"))
        goto_note = TEXT_SHEETS_READONLY
    buttons.append(_button(TEXT_SAVE, "存檔", keys=keys))

    missing = []
    if holdings_empty:
        missing.append("holding")
    if basis is None and not setting_failed:
        missing.append("alo_basis")
    if not bucket_names and not setting_failed:
        missing.append("alo_bucket_names")
    if fx_missing:
        missing.append(FX_KEY)
    summary = "基準 " + (BASIS_LABELS[basis] if basis else ("取不到" if setting_failed else "未設定"))
    summary += f"；類別 {len(bucket_names or ())} 個；未指派 {len(unassigned)} 檔"
    if missing:
        summary += "；缺 " + "、".join(missing)
    if failure is not None:
        summary += "；取數失敗"
    return {
        "code": "ALO-4",
        "title": BLOCK_TITLES["ALO-4"],
        "answers": ANSWERS["ALO-4"],
        "_layer": 3,
        "_default_open": False,
        "_tone": "紅" if failure is not None else ("灰" if fx_missing else "中性"),
        "summary_text": summary,
        "fail_nodes": fail_nodes,
        "inputs": inputs,
        "basis_line": "" if setting_failed else "目前基準：" + (BASIS_LABELS[basis] if basis else TEXT_UNSET),
        "basis_option_labels": dict(BASIS_LABELS),
        "bucket_unset_lines": [] if (bucket_names or setting_failed) else [TEXT_UNSET],
        "assign_labels": ["基金", "Sheets 上的類別", "本頁歸入"],
        "_assign_rows": assign_rows,
        "unassigned_lines": unassigned,
        "mismatch_lines": mismatched,
        "goto_note": goto_note,
        "error_lines": _save_error_lines(dataset, keys),
        "buttons": buttons,
        "detail_lines": detail_lines,
        "badges": [],
    }


# ───────────────────────── ALO-5 ─────────────────────────


def export_text(alo2, alo3) -> str:
    """一份表格檔。內容與畫面上的列逐格相同，欄名沿畫面欄名（ALO-GAP-匯出兩組欄名）。"""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    if not alo3["_rows"]:
        # 44 逐字「匯出只含 `ALO-2` 的列，並在檔首註明未含試算」
        writer.writerow([TEXT_NO_SCENARIO_IN_EXPORT])
    writer.writerow(alo2["column_labels"])
    for row in alo2["_rows"]:
        writer.writerow(
            [row["bucket_text"], row["current_text"], row["target_text"], row["diff_text"], row["band_text"]]
        )
    if alo3["_rows"]:
        writer.writerow([])
        writer.writerow(alo3["column_labels"])
        for row in alo3["_rows"]:
            writer.writerow([row["bucket_text"], row["share_text"], row["new_diff_text"]])
    return buffer.getvalue()


def _build_alo5(alo2, alo3) -> dict:
    has_rows = bool(alo2["_rows"])  # ALO-GAP-無列判定
    button = _button(
        "匯出",
        "匯出",
        enabled=has_rows,
        disabled_reason="" if has_rows else TEXT_NO_EXPORT_ROWS,
    )
    parts = ["ALO-2 的列"] + (["ALO-3 的列"] if alo3["_rows"] else [])
    return {
        "code": "ALO-5",
        "title": BLOCK_TITLES["ALO-5"],
        "answers": ANSWERS["ALO-5"],
        "_layer": 3,
        "_default_open": False,
        "_tone": "中性",
        "summary_text": (f"可匯出 {len(alo2['_rows'])} 列" if has_rows else TEXT_NO_EXPORT_ROWS),
        "_export_text": export_text(alo2, alo3) if has_rows else "",
        "file_name": "alo_export.csv",
        "detail_lines": [
            ("匯出檔會含：" + "、".join(parts)) if has_rows else TEXT_NO_EXPORT_ROWS,
            "匯出不寫入任何資料表",
            HINT_NOTE,
        ],
        "buttons": [button],
        "badges": [],
    }


# ───────────────────────── ALO-6 ─────────────────────────


def _build_alo6(dataset) -> dict:
    holdings = aggregated_holdings(dataset)
    basis = setting_value(dataset, "alo_basis")  # ALO-GAP-ALO6基準
    bucket_names = setting_value(dataset, "alo_bucket_names")
    policy_name = {p["policy_id"]: p["policy_name"] for p in dataset["policy"]}
    # ALO-GAP-ALO6幣別：44 規則欄沒有幣別欄，本頁不顯示。
    labels = ["基金", "保單", "類別", "基準值", "佔所屬類別", "佔總體"]
    # ALO-GAP-保單失敗從嚴：policy 失敗整塊進系統錯誤。
    failure = fetch_error(dataset, _source_tables(basis) + ("policy",))
    if failure is not None or not holdings:
        # 44 ALO-6 空狀態「無任何持倉 → `來源缺`」；ALO-GAP-來源缺按鈕：不畫重新取數。
        # 取數失敗照 44 5.5 系統錯誤通用模板（ALO-GAP-取數失敗）。
        node = (
            _placeholder(fetch_failed_text(failure), "系統錯誤")
            if failure is not None
            else _placeholder(empty_source_text(["holding"]), "來源缺")
        )
        return {
            "code": "ALO-6",
            "title": BLOCK_TITLES["ALO-6"],
            "answers": ANSWERS["ALO-6"],
            "_layer": 4,
            "_default_open": False,
            "_tone": node["_tone"],
            "summary_text": "取數失敗" if failure is not None else "缺 holding",
            "column_labels": labels,
            "_rows": [],
            "placeholder": node,
            "footer_lines": [],
            "detail_lines": [HINT_NOTE],
            "buttons": [],
            "badges": [],
        }

    rows = []
    for holding in holdings:
        cat = category_of(holding, bucket_names)
        if basis is None:
            value, reason = None, TEXT_NA_NO_BASIS
        else:
            value, reason = basis_value(dataset, holding, basis)
        rows.append(
            {
                "_fund_code": holding["fund_code"],
                "_bucket": cat,
                "_value": value,
                "_reason": reason,
                "fund_text": f"{holding['fund_name']}（{holding['fund_code']}）",
                "policy_text": policy_name.get(holding["policy_id"], "⬜"),
                "bucket_text": cat,
                # 44 ALO-6 空狀態「某檔缺基準值 → 該列基準值格 `⬜`」
                "value_text": "⬜" if value is None else format_twd(value),
            }
        )
    included = [r for r in rows if r["_value"] is not None]
    total = sum(r["_value"] for r in included)
    by_bucket = {}
    for row in included:
        by_bucket[row["_bucket"]] = by_bucket.get(row["_bucket"], 0.0) + row["_value"]
    for row in rows:
        if row["_value"] is None or total <= 0:
            row["_in_bucket"], row["_in_total"] = None, None
            row["in_bucket_text"], row["in_total_text"] = "⬜", "⬜"
        else:
            row["_in_bucket"] = row["_value"] / by_bucket[row["_bucket"]]
            row["_in_total"] = row["_value"] / total
            row["in_bucket_text"] = format_number(row["_in_bucket"])
            row["in_total_text"] = format_number(row["_in_total"])

    footer = []
    if included and total > 0:
        # ALO-GAP-ALO6表尾：逐類別各一個，再加總體一個。
        for bucket in by_bucket:
            subtotal = sum(r["_in_bucket"] for r in rows if r["_bucket"] == bucket and r["_in_bucket"] is not None)
            footer.append(f"類別內佔比合計（{bucket}） {format_number(subtotal)}")
        footer.append(f"總體佔比合計 {format_number(sum(r['_in_total'] for r in included))}")
    excluded = len(rows) - len(included)
    if excluded:
        footer.append(f"被排除 {excluded} 檔")
    detail = [HINT_NOTE, "⚠ 44 兩塊的字面不同：本塊佔總體的分母只排除缺基準值的那幾檔，ALO-2 排除整個類別；本頁照各塊字面。"]
    if basis is None:
        detail.insert(0, TEXT_NA_NO_BASIS)
    return {
        "code": "ALO-6",
        "title": BLOCK_TITLES["ALO-6"],
        "answers": ANSWERS["ALO-6"],
        "_layer": 4,
        "_default_open": False,
        "_tone": "灰" if excluded else "中性",
        "summary_text": f"{len(rows)} 檔" + (f"；被排除 {excluded} 檔" if excluded else ""),
        "column_labels": labels,
        "_rows": rows,
        "placeholder": None,
        "footer_lines": footer,  # ALO-GAP-排除顆粒
        "detail_lines": detail,
        "buttons": [],
        "badges": [],
    }


# ───────────────────────── ALO-7 ─────────────────────────


def _setting_text(key, value) -> str:
    if key == "alo_target_weights":
        # ALO-GAP-ALO7值格
        return "／".join(
            f"{t['bucket']} {'⬜' if t['weight_ratio'] is None else format_number(t['weight_ratio'])}"
            for t in value
        )
    return format_number(value)


def _build_alo7(dataset) -> dict:
    """ALO-GAP-ALO7重疊：本塊與 ALO-1 回答同一件事，兩塊照畫，不替 44 消除。"""
    keys = ("alo_target_weights", "alo_tolerance_pp")
    values = {key: setting_value(dataset, key) for key in keys}
    labels = ["鍵名", "當前值", "最後修改時間"]
    base = {
        "code": "ALO-7",
        "title": BLOCK_TITLES["ALO-7"],
        "answers": ANSWERS["ALO-7"],
        "_layer": 4,
        "_default_open": False,
        "column_labels": labels,
        "detail_lines": [
            "本塊只有一個時間點，不依時間排序。",
            "⚠ 44 已登記本塊與 ALO-1 回答同一件事、待客戶裁決；本頁兩塊都照畫。",
            HINT_NOTE,
        ],
        "buttons": [],
        "badges": [],
    }
    failure = settings_failure(dataset)
    if failure is not None:
        # ALO-GAP-設定取數失敗
        node = _placeholder(fetch_failed_text(failure), "系統錯誤")
        return {**base, "_tone": "紅", "summary_text": "取數失敗", "_rows": [], "placeholder": node}
    missing = [key for key in keys if values[key] in (None, [])]
    if len(missing) == len(keys):
        # 44 ALO-7 空狀態：兩鍵皆為空 → `來源缺`，文案「尚未設定目標」。
        return {
            **base,
            "_tone": "灰",
            "summary_text": "缺 " + "、".join(keys),
            "_rows": [],
            "placeholder": {"text": TEXT_NO_TARGET, "glyph": "⬜", "_empty_kind": "來源缺", "_tone": "灰"},
        }
    rows = []
    for key in keys:
        value = values[key]
        updated = setting_updated_at(dataset, key)
        if value in (None, []):
            # ALO-GAP-ALO7兩句相撞：取值為空那一句。
            value_text, time_text = TEXT_UNSET, "⬜"
        else:
            value_text = _setting_text(key, value)
            time_text = TEXT_NEVER_SET if updated is None else format_time(updated)
        rows.append({"_key": key, "key_text": key, "value_text": value_text, "time_text": time_text})
    return {
        **base,
        "_tone": "灰" if missing else "中性",
        "summary_text": ("缺 " + "、".join(missing)) if missing else "兩鍵皆有值",
        "_rows": rows,
        "placeholder": None,
    }


# ───────────────────────── 整頁 ─────────────────────────


def build_page_model(dataset: dict) -> dict:
    """`dataset` 的形狀見 `fixtures._dataset`。本函式不改動 `dataset`（ALO-5 判準）。"""
    unknown = sorted(set(dataset.get("errors") or {}) - set(FETCHABLE_TABLES))
    if unknown:
        # ALO-GAP-取數失敗：本頁只處理三張表的取數失敗；其餘的不假裝成空資料，炸掉。
        raise ValueError(f"資料集帶本頁沒有畫法的取數失敗 {unknown}")
    alo2 = _build_alo2(dataset)
    alo3 = _build_alo3(dataset, alo2)
    blocks = [
        _build_alo0(alo2),
        _build_alo1(dataset),
        alo2,
        alo3,
        _build_alo4(dataset),
        _build_alo5(alo2, alo3),
        _build_alo6(dataset),
        _build_alo7(dataset),
    ]
    return {
        "title": PAGE_TITLE,
        "answers": PAGE_ANSWERS,
        "top_lines": top_lines(dataset),
        "hint_note": PAGE_HINT_NOTE,
        "blocks": blocks,
        "footer_lines": list(NOT_RESPONSIBLE),
        "footer_badges": [_redline_badge(m) for m in REDLINE_MARKS],
    }


def find_block(model: dict, code: str) -> dict:
    for block in model["blocks"]:
        if block["code"] == code:
            return block
    raise KeyError(code)


def codes_in_layer(model: dict, layer: int) -> list:
    return [b["code"] for b in model["blocks"] if b["_layer"] == layer]


def _walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, (list, tuple, set)):
        for value in node:
            yield from _walk(value)


def collect_badges(model) -> list:
    return [n for n in _walk(model) if "_kind" in n and "text" in n]


def collect_buttons(model) -> list:
    return [n for n in _walk(model) if "_action_kind" in n]


def collect_inputs(model) -> list:
    return [n for n in _walk(model) if n.get("_input") is True]


def collect_ui_strings(model) -> list:
    """把介面全頁文字抓成一份清單（`44` 1.2 節判準）。連機器用的鍵一起走 —— 寧可多抓。"""
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
    """`44` 1.2：禁方向詞與禁箭頭。回 `{命中的詞: [那幾句]}`。"""
    hits = {}
    for word in FORBIDDEN_DIRECTION_WORDS + FORBIDDEN_ARROWS + FORBIDDEN_ADVICE_WORDS:
        found = [s for s in strings if word in s]
        if found:
            hits[word] = found
    return hits
