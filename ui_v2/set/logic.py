# -*- coding: utf-8 -*-
"""設定與診斷純邏輯。零 streamlit import、零舊 repo import、零網路。

所有判定住在這裡；page.py 只負責把 build_page_model() 產出的模型畫出來。
模型慣例：底線開頭的鍵是**機器用**（狀態、色調、層號…），不開頭底線的鍵是**畫面文字**。

規格來源只有 `44` 第三節第五小節（`SET-0`～`SET-7`）、它引用的第四節資料表與第五節元件規則。
**`44` 與拍板原型 `ui_prototype_set.html`／拍板草稿 `draft_set_savefail.html` 不一致處一律照 `44`**，
逐處登記在 `GAPS`。`44` 沒寫、不決定就畫不出來的地方，照最保守的畫法做，同樣登記在 `GAPS`，
**不自行發明規格、按鈕、欄位或資料源**。

⚠️ 本頁只描述資料狀態（新鮮度、來源成敗、參數值），不描述市場或持倉，不給任何處置方向（G1†／G3†）。
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone

# ───────────────────────── 缺口與矛盾登記（`44` 沒寫或與原型不一致） ─────────────────────────
#
# ⛔ 每一筆都是**登記，不是動工授權**；本頁照每一筆寫的畫法做，不替 `44` 補規格。
#    代號在程式碼裡被引用的地方，就是那個畫法落地的地方（`test_缺口登記表每一筆都在原始碼裡被引用`）。
GAPS = {
    "SET-GAP-取數失敗圖示": (
        "已結案（2026-09-24，決策者：客戶）：客戶裁示取數失敗改用 ⛔、黃燈保留 ⚠，44 第五節第五小節系統錯誤模板"
        "已於第二十一輪同步為「⛔ 取數失敗」。本頁的取數失敗圖示仍集中在 FETCH_FAIL_GLYPH 一個常數，已改為 ⛔。"
        "舊登記「44 現行字面仍是 ⚠、待 44 同步」寫下時為真。自此取數失敗與存檔寫入失敗同用 ⛔（兩者都是失敗，文字不同），黃燈仍 ⚠。"
    ),
    "SET-GAP-取數失敗": (
        "設定與診斷頁八塊的空狀態欄沒有一塊寫出「讀不到某張表」時畫什麼（SET-5 寫的是取數失敗要寫進 fetch_log.message，"
        "那是另一件事）。本頁照 44 第五節第五小節「系統錯誤」的通用模板（圖示＋取數失敗：＋訊息原文，紅）畫在受影響的塊；"
        "模板帶的那一枚「重新取數」依同小節「空狀態欄整格為準」不畫。本頁處理 nav／dividend／market_indicator／"
        "fetch_log／user_setting 五張表的讀取失敗，其餘表收到才炸。"
    ),
    "SET-GAP-燈讀取失敗": (
        "SET-0 讀的兩塊（SET-1、SET-2）任何一張來源表讀不到時燈該長什麼樣 44 沒寫。本頁燈為紅（5.5 系統錯誤的顏色），"
        "文案照抄那一格的失敗字串，不說成資料齊、也不說成尚未設定。"
    ),
    "SET-GAP-燈紅與空狀態相撞": (
        "失敗來源大於零而新鮮度上限未設時，44 規則欄給紅、空狀態欄給灰，兩句同時命中。"
        "本頁照 44 第五節第五小節的嚴重度（系統錯誤最嚴）取紅。"
    ),
    "SET-GAP-燈兩句同時成立": (
        "新鮮度上限未設與尚無取數紀錄同時成立時（全新環境），44 判準寫「其中一句」。"
        "本頁取空狀態欄的第一句「尚未設定新鮮度上限」；拍板原型取的是另一句，44 兩句都准。"
    ),
    "SET-GAP-上限型別不符": (
        "set_max_age_days 已存的值與型別不符時燈該出哪一句 44 沒寫。本頁燈為灰，文案印 SET-3 那一格同一句「⬜ 不適用：值與型別不符」。"
    ),
    "SET-GAP-燈狀態字": "燈旁的狀態字（狀態：…）是本頁擬的，44 只訂了燈色與文案；本頁為了狀態不靠顏色單獨辨識補上。",
    "SET-GAP-紅燈文案": "44 規則欄只寫「文案列出失敗的來源層級」，沒給句型。本頁寫「失敗的來源層級：」接層級字面值，以頓號串起。",
    "SET-GAP-燈圖示共用": (
        "已結案（2026-09-24）：FETCH_FAIL_GLYPH 已改為 ⛔，紅燈（取數失敗）用 ⛔、黃燈（有逾期）用 ⚠，不再共用。"
        "舊登記「紅燈與黃燈同用 ⚠」在常數還是 ⚠ 的那段期間為真（見 SET-GAP-取數失敗圖示）。"
    ),
    "SET-GAP-某類無列不入燈": (
        "某一類資料一列也沒有（SET-1 那一列三欄 ⬜）、或某一層級從無紀錄（SET-2 那一列三欄 ⬜）時，"
        "它既不是逾期、也不是失敗來源；照 44 SET-0 規則欄字面，燈仍是灰「資料齊、來源皆可達」。本頁照字面，不自行把它算進燈。"
    ),
    "SET-GAP-端點": (
        "端點由 44 SET-1 判準推得：「把上限設成 0 日，三列的比較欄皆為「外」且 SET-0 的 N 等於 3」—— "
        "今天取得的那一類距今 0 日，要在上限 0 日時算外，端點只能是「距今日數大於等於上限算外」。"
        "（原型 S-13 當時登記為 44 沒寫；本頁照判準推得的讀法。）"
    ),
    "SET-GAP-距今時區": (
        "距今日數用哪個時區的日曆日算 44 沒寫（原型 S-11）。本頁以 UTC+8 的日曆日相減；"
        "「今天」固定在 fixtures.NOW_UTC 那一刻，本頁不讀系統時鐘。"
    ),
    "SET-GAP-時區": "第四節寫顯示時才轉當地時區，當地是哪一區 44 沒寫。本頁顯示 UTC+8，並依 SET-1 規則把時區寫在表頭。",
    "SET-GAP-觀測日欄": (
        "SET-1 來源欄宣告了「各自的觀測日欄」，規則欄三欄卻用不到它（原型 S-09／S-10）。本頁不畫那一欄。"
    ),
    "SET-GAP-內外不著色": "SET-1 與上限比較那一欄著不著色 44 沒寫。本頁不著色，純文字「內」「外」。",
    "SET-GAP-層級名": (
        "拍板原型的四個層級名是示意佔位；44 已定四個（淨值／配息／市場指標／其他）。本頁照 44 的四個字面值。"
    ),
    "SET-GAP-ok訊息欄": "SET-2 第三欄逐字是失敗時的訊息原文；ok 那一列那一格印什麼 44 沒寫（原型 S-27）。本頁印破折號 —。",
    "SET-GAP-回應為空": (
        "取數回空時，SET-5 空狀態欄要 SET-2 訊息欄寫「回應為空」，而 SET-2 第三欄是失敗時的訊息原文、"
        "fetch_log.message 成功時為空（原型 S-03，三處打架）。本頁 message 維持空，SET-2 由那一列 outcome 為 ok 且 "
        "row_count 為 0 推得並印「回應為空」。"
    ),
    "SET-GAP-來源缺按鈕": (
        "第五節來源缺的模板帶一枚「重新取數」；SET-2 與 SET-6 的空狀態欄沒有寫那一枚，"
        "44 第五節第五小節「空狀態欄整格為準」→ 本頁不畫（拍板原型畫了，原型 S-28）。"
    ),
    "SET-GAP-鍵清單": (
        "SET-3 來源是 user_setting 全表、空狀態要「逐鍵列出」，但 44 沒有把鍵列成一張表（原型 S-15／S-16）。"
        "本頁的鍵清單是 44 全文以反引號寫出的十七個鍵，再加上表裡實際有的列；那個數是本頁掃出來的，不是 44 給的。"
    ),
    "SET-GAP-型別本頁配": (
        "44 定義了六種 value_kind，沒有寫哪一鍵是哪一種（原型 S-44）。每一鍵的型別是本頁配的；"
        "alo_basis 放空（同 ui_v2/alo 的登記）；alo_target_weights 與 alo_scenario_input 取 ui_v2/alo 的 list，拍板原型寫的是 rules。"
    ),
    "SET-GAP-型別缺": "某鍵的 value_kind 為空時（alo_basis），型別欄畫 ⬜，本頁不判它的值合不合型別。",
    "SET-GAP-型別判定規則": (
        "六種 value_kind 各怎麼判合不合 44 沒寫。本頁：int 為整數字面、float 為數字字面、ratio 為 0 到 1 的數字、"
        "date 為 YYYY-MM-DD、list 與 rules 為 JSON 陣列字面。"
    ),
    "SET-GAP-原始字面值位置": "值與型別不符時原始字面值印在哪 44 沒寫，而判準要求沒有第五欄（原型 S-25）。本頁印在目前值那一格的第二行。",
    "SET-GAP-updated_at空": "updated_at 為空時 SET-3 最後修改時間那一格印什麼 44 沒寫（原型 S-26）。本頁印 ⬜。",
    "SET-GAP-輸入欄型態": "六種 value_kind 的輸入欄各長什麼樣 44 沒寫（原型 S-22）。本頁 list 與 rules 畫多行框，其餘畫單行框，標籤寫出型別。",
    "SET-GAP-清除鈕": (
        "SET-4 規則欄寫本塊只掛「存檔」一枚，同一格又寫「清除某鍵的操作」。拍板原型每一列畫了一枚清除鈕；"
        "本頁照 44 只掛存檔一枚，清除的操作＝把該鍵的輸入欄清空後存檔。"
    ),
    "SET-GAP-存檔停用": "「存檔」什麼時候停用 44 沒訂（44 已登記其一）。本頁不宣告停用條件。",
    "SET-GAP-當下值或已存值": "SET-3 讀的是當下值還是已存值 44 已登記待裁（其二）。本頁 SET-3 讀已存值。",
    "SET-GAP-無後端": (
        "本頁是假資料畫的頁面，沒有後端：「存檔」與「重新取數」按得下去但不寫任何東西。"
        "SET-4 判準（重新載入後逐字相同）與 SET-5 判準（fetch_log 多一列）在本頁跑不動，只驗得到按鈕的寫入對象宣告。"
    ),
    "SET-GAP-失敗鍵": (
        "44 寫的是單數的「該鍵」，沒有指定哪一鍵。示範用的鍵與當下輸入取拍板草稿的選擇（set_max_age_days）。"
    ),
    "SET-GAP-失敗無輸入欄": (
        "user_setting 讀不到時本頁不畫輸入欄（值是取不到，不是沒設定）；此時若疊上存檔寫入失敗，失敗框沒有輸入欄可掛，"
        "本頁把它畫在 SET-4 的失敗框下方，44 沒寫這個組合。"
    ),
    "SET-GAP-型別說明文字": "SET-4 型別不符時「欄位下方顯示型別說明」，44 沒給字面。本頁寫出該鍵的 value_kind 與它要的字面格式。",
    "SET-GAP-必要鍵": "SET-4 空狀態的「必要鍵」44 沒有定義（原型 S-23）。本頁不標任何一鍵為必要。",
    "SET-GAP-影響哪幾塊": (
        "SET-4 回答「改了會影響哪幾塊」，44 沒給清單。本頁照 44 各塊來源欄以反引號寫出該鍵的塊列出（與 SET-7 同一個射程）；"
        "set_log_keep_rows 只在 SET-6 規則欄出現、沒有任何一塊的來源欄宣告它，本頁照實寫沒有。"
        "mkt_indicator_keys 依 44 來源欄是 MKT-5，拍板原型寫 MKT-6。"
    ),
    "SET-GAP-執行中": "「執行中」那一態的進行式文字與秒數格式 44 沒給（原型 S-41）。本頁沒有後端，不演這一態。",
    "SET-GAP-SET5寫到哪": (
        "SET-5 寫「取數只寫入資料表與 fetch_log」，第五節按鈕禁止欄寫 holding／policy／nav／dividend 四張表本儀表板唯讀（原型 S-02）。"
        "本頁的「重新取數」只宣告寫 fetch_log（同第五節 取數 類的寫法），不在畫面上宣稱任何一張表被寫入。"
    ),
    "SET-GAP-層級單選": "SET-5 的層級選擇不屬第五節五類元件（原型 S-40）。本頁照實畫成單選，初次開啟不預選（44 1.1 節判準）。",
    "SET-GAP-保留筆數移除": (
        "超出保留筆數的最舊列由誰、什麼時候移除 44 沒寫（原型 S-29／S-33）。本頁只顯示最新的 N 列，"
        "已移除筆數＝紀錄總數減 N；保留筆數未設或讀不到時全部列出並在表尾寫明。"
    ),
    "SET-GAP-保留筆數為負": (
        "44 沒有替 set_log_keep_rows 訂值域。存了一個負整數時它合 int 型別，說成「值與型別不符」會誤導；"
        "本頁照 44 第五節「算不出來」模板寫「⬜ 不適用：保留筆數小於 0」，並全部列出不截斷。"
    ),
    "SET-GAP-保留筆數為零": (
        "set_log_keep_rows 為 0 時 SET-6 該長什麼樣 44 沒寫。本頁照規則欄字面：表上零列、表尾註明已移除的筆數；"
        "不出空狀態欄那一句「尚無取數紀錄」——紀錄存在，只是全部超出保留上限。"
    ),
    "SET-GAP-fetch_log值域越界": (
        "fetch_log 的 source_tier 不在 44 那四個之內、或 outcome 不是 ok／failed 時畫法 44 沒寫。本頁炸掉，不自行歸類。"
    ),
    "SET-GAP-其他表讀取失敗炸": (
        "本頁沒有任何一塊讀 holding／policy／fund_profile；資料集若帶這幾張表的讀取失敗，本頁不假裝它無關，炸掉（同 SET-GAP-取數失敗）。"
    ),
    "SET-GAP-耗時格式": "耗時的小數位數 44 沒給（原型 S-42）。本頁寫到小數一位。",
    "SET-GAP-SET7母體": (
        "SET-7 只掃來源欄（44 自己寫的射程限制）。本頁的抽法：去掉刪除線後以反引號寫出的「表.欄位」，"
        "加上寫成「表 全表／全欄」的整張表；裸欄名（沒帶表名）不計，所以 SET-6 用到的 set_log_keep_rows 這一類本表看不見。"
    ),
    "SET-GAP-SET7寫死": (
        "SET-7 是寫死的還是執行時去讀規格 44 沒寫（原型 S-32）。本頁用一份快照（fixtures），"
        "由測試逐項對 44 現行文字重抽比對；執行時不讀 44。"
    ),
    "SET-GAP-來源徽章": (
        "第五節卡片 ok 態要掛來源與新鮮度徽章；本頁 SET-1 一列一類、SET-2 一列一層級，那個層級本身就印在列上。"
        "本頁不另掛，不自己編一個層級。"
    ),
    "SET-GAP-示意標記": (
        "本頁的時間、列數、訊息原文全是示意值。本頁頁首一行涵蓋全頁，另在每一塊畫面上有數字的塊各加一行"
        "「本塊數字皆為示意值」，不逐數加註（同 ui_v2/alo）。"
    ),
    "SET-GAP-深色主題前提": (
        "本頁的對比是在 repo 根的 .streamlit/config.toml（base = dark、textColor #e6edf3）之下量的；"
        "Streamlit 元件（輸入欄、展開區標題、按鈕）的字色來自那份設定，不在本頁檔案裡。"
    ),
    "SET-GAP-窄寬度表格": "卡內表格在窄寬度怎麼塌 44 沒寫。本頁讓格內文字在任何字元處換行，不出橫向捲動、不藏欄。",
    "SET-GAP-設定取數失敗": (
        "user_setting 讀不到時，讀它的塊（SET-1 上限、SET-3、SET-4、SET-6 保留筆數）該長什麼樣 44 沒寫。"
        "本頁照 5.5 系統錯誤模板畫，並且不畫輸入欄與「⬜ 未設定」——值是取不到，不是沒設定。存檔鈕照舊（其一）。"
    ),
    "SET-GAP-讀取失敗逐列": (
        "nav／dividend／market_indicator 其中一張讀不到時，SET-1 只讓那一列進系統錯誤（最近取得時間那一格印失敗字串，"
        "另兩格 ⬜），其餘兩列照出；44 沒寫這個顆粒。"
    ),
}


# ───────────────────────── 常數（逐字引 `44`） ─────────────────────────

# ⛔ 本頁畫「取數失敗」用的圖示**只住在這一個常數裡**（SET-GAP-取數失敗圖示）。任何一處要畫取數失敗，都經由它。
FETCH_FAIL_GLYPH = "⛔"
# 存檔寫入失敗框的圖示（客戶 2026-09-24 裁示「失敗框補圖示」，拍板原型用 ⛔）。與上一個常數是兩件事（值自第二十一輪起相同）。
SAVE_FAIL_GLYPH = "⛔"
# 黃燈的圖示（客戶裁示「黃燈保留 ⚠」）。
WARN_GLYPH = "⚠"
EMPTY_GLYPH = "⬜"

# `44` 5.2 徽章 `狀態` 那一列的七個字面值（封閉列舉）與各自的顏色語意。
STATUS_BADGE_LITERALS = ("資料未備", "不適用", "取數失敗", "推估", "修正過", "部分缺", "未定義")
_STATUS_BADGE_TONE = {
    "資料未備": "灰",
    "不適用": "黃",
    "取數失敗": "紅",
    "推估": "黃",
    "修正過": "黃",
    "部分缺": "黃",
    "未定義": "黃",
}

# `44` 5.3 按鈕：八類之外沒有第九類。
BUTTON_KINDS = ("取數", "套用", "展開", "匯出", "新增列", "清除", "導覽", "存檔")
READONLY_TABLES = ("holding", "policy", "nav", "dividend")
_BUTTON_WRITES = {
    "取數": frozenset({"fetch_log"}),  # SET-GAP-SET5寫到哪
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
# 比 `44` 1.2 更嚴的補充（同 ui_v2/alo，只能更嚴、不能更鬆）。
FORBIDDEN_ADVICE_WORDS = ("應該調整", "應調", "該調整", "宜調")
# `44` 1.1 節判準：按鈕標籤四個禁詞。
FORBIDDEN_BUTTON_WORDS = ("一鍵", "最佳", "推薦", "最適")

# 塊名逐字引 `44` 3.5 的八個 `#### 塊 SET-n｜…` 標題。
BLOCK_TITLES = {
    "SET-0": "可信度結論燈",
    "SET-1": "資料新鮮度卡",
    "SET-2": "來源健康卡",
    "SET-3": "規則參數卡",
    "SET-4": "參數編輯",
    "SET-5": "重新取數",
    "SET-6": "取數紀錄",
    "SET-7": "欄位對照表",
}
BLOCK_LAYERS = {
    "SET-0": 1,
    "SET-1": 2,
    "SET-2": 2,
    "SET-3": 2,
    "SET-4": 3,
    "SET-5": 3,
    "SET-6": 4,
    "SET-7": 4,
}
ANSWERS = {
    "SET-0": "其他四頁的數字，現在可不可以照著讀",
    "SET-1": "哪一類資料已經放到超過我能接受的時間",
    "SET-2": "是哪一層來源在失敗，失敗訊息說了什麼",
    "SET-3": "四頁上那些門檻和區間，現在各是多少、是我什麼時候設的",
    "SET-4": "我要怎麼改這些門檻，改了會影響哪幾塊",
    "SET-5": "我可以怎麼讓它再試一次，試完結果寫在哪",
    "SET-6": "這些數字上一次是什麼時候取的、取回幾列",
    "SET-7": "這一欄資料是餵給哪一塊的；這一塊的數字又是從哪幾欄來的",
}

PAGE_TITLE = "設定與診斷"
PAGE_ANSWERS = "畫面上的數字現在可不可信，不可信是卡在哪一段"
NOT_RESPONSIBLE = (
    "不解釋市場（那是市場總覽）",
    "不手動編輯任何一筆資料的值",
    "不下任何投資判斷",
)
# `44` 1.3 設定與診斷那一列：`G1†` `G3†`。
REDLINE_MARKS = ("G1†", "G3†")

# ── 畫面文案（每一句都逐字取自 `44` 現行文字；`test_44逐字的文案常數每一句都在現行文字裡`） ──
TEXT_ALL_OK = "資料齊、來源皆可達"
TEXT_NO_LIMIT = "尚未設定新鮮度上限"
TEXT_NO_RECORDS = "尚無取數紀錄"
TEXT_OVERDUE_TAIL = "筆資料超過你設定的新鮮度上限"
TEXT_NA_NO_LIMIT = "⬜ 不適用：尚未設定上限"
TEXT_UNSET = "⬜ 未設定"
TEXT_NA_NEGATIVE_KEEP = "⬜ 不適用：保留筆數小於 0"  # 44 5.5「算不出來」模板；原因句是本頁擬的（SET-GAP-保留筆數為負）
TEXT_NA_BAD_KIND = "⬜ 不適用：值與型別不符"
TEXT_NA_NO_FINISH = "⬜ 不適用：未記錄結束時間"
TEXT_UNUSED = "⬜ 未被任何塊使用"
TEXT_EMPTY_RESPONSE = "回應為空"
TEXT_NO_TIER_PICKED = "尚未選定來源層級"
TEXT_REFETCH = "重新取數"
TEXT_SAVE = "存檔"
TEXT_SAVE_FAILED = "存檔寫入失敗"
TEXT_FETCH_FAILED = "取數失敗"
# 拍板草稿與拍板原型失敗框的第二行（44 同句作「該欄的當下輸入留在畫面上不清掉」）。
TEXT_KEEP_INPUT = "上面這一欄的當下輸入留在畫面上不清掉"
# 拍板原型型別說明的句尾；44 SET-4 空狀態欄逐字「不存檔，`SET-3` 的值不變」。
TEXT_NOT_SAVED = "本次不存檔，SET-3 的值不變。"
# 44 逐字「把上限設成 0 日，三列的比較欄皆為「外」且 `SET-0` 的 N 等於 3」
TEXT_SET1_JUDGE = "把上限設成 0 日，三列的比較欄皆為「外」且 `SET-0` 的 N 等於 3"
TEXT_IN = "內"
TEXT_OUT = "外"
TEXT_RULE_SCOPE = "本表的母體只有「來源」欄"
TEXT_SET5_WRITES = "取數只寫入資料表與 `fetch_log`，不改寫任何 `user_setting`"
TEXT_SET2_RAW = "訊息原文照印，不改寫成安撫語句"
TEXT_SET2_NO_DIRECTION = "本卡不對失敗給出處置方向"
TEXT_SET4_PER_KEY = "逐鍵編輯，一鍵一個輸入欄，欄位型態依 `value_kind` 決定"
TEXT_SET4_CLEAR = "清除某鍵的操作把它變回未設定，不變成零"
TEXT_SET4_NO_RESTORE = "沒有系統值可還原"
TEXT_SET6_ORDER = "依 `started_at` 由新到舊"
TEXT_SET3_NO_DEFAULT_COLUMN = "本卡不顯示任何「內建預設值」欄"
TEXT_SET7_NO_INFERENCE = "本表不做推論，只列本檔各塊「來源」欄寫出的對應"
TEXT_LAMP_DATA_ONLY = "燈描述資料狀態，不描述市場或持倉"

VERBATIM_TEXTS = {
    "TEXT_ALL_OK": TEXT_ALL_OK,
    "TEXT_NO_LIMIT": TEXT_NO_LIMIT,
    "TEXT_NO_RECORDS": TEXT_NO_RECORDS,
    "TEXT_OVERDUE_TAIL": TEXT_OVERDUE_TAIL,
    "TEXT_NA_NO_LIMIT": TEXT_NA_NO_LIMIT,
    "TEXT_UNSET": TEXT_UNSET,
    "TEXT_NA_BAD_KIND": TEXT_NA_BAD_KIND,
    "TEXT_NA_NO_FINISH": TEXT_NA_NO_FINISH,
    "TEXT_UNUSED": TEXT_UNUSED,
    "TEXT_EMPTY_RESPONSE": TEXT_EMPTY_RESPONSE,
    "TEXT_NO_TIER_PICKED": TEXT_NO_TIER_PICKED,
    "TEXT_REFETCH": TEXT_REFETCH,
    "TEXT_SAVE": TEXT_SAVE,
    "TEXT_SAVE_FAILED": TEXT_SAVE_FAILED,
    "TEXT_FETCH_FAILED": TEXT_FETCH_FAILED,
    "TEXT_RULE_SCOPE": TEXT_RULE_SCOPE,
    "TEXT_SET5_WRITES": TEXT_SET5_WRITES,
    "TEXT_SET2_RAW": TEXT_SET2_RAW,
    "TEXT_SET2_NO_DIRECTION": TEXT_SET2_NO_DIRECTION,
    "TEXT_SET4_PER_KEY": TEXT_SET4_PER_KEY,
    "TEXT_SET4_CLEAR": TEXT_SET4_CLEAR,
    "TEXT_SET4_NO_RESTORE": TEXT_SET4_NO_RESTORE,
    "TEXT_SET6_ORDER": TEXT_SET6_ORDER,
    "TEXT_SET3_NO_DEFAULT_COLUMN": TEXT_SET3_NO_DEFAULT_COLUMN,
    "TEXT_SET7_NO_INFERENCE": TEXT_SET7_NO_INFERENCE,
    "TEXT_LAMP_DATA_ONLY": TEXT_LAMP_DATA_ONLY,
    "TEXT_NOT_SAVED_44": "不存檔，`SET-3` 的值不變",
    "TEXT_SET1_JUDGE": TEXT_SET1_JUDGE,
    "PAGE_ANSWERS": PAGE_ANSWERS,
}

# 44 逐字「上限由使用者輸入（G3†）」
# 44 逐字「訊息原文照印，不改寫成安撫語句」
# 44 逐字「本塊不提供「一鍵還原為系統值」之類的動作」（本頁因此沒有那一類按鈕；按鈕標籤禁詞見 FORBIDDEN_BUTTON_WORDS）
# 44 逐字「超出的最舊列被移除並在表尾註明已移除的筆數」

HINT_NOTE = "本塊數字皆為示意值"  # SET-GAP-示意標記
PAGE_HINT_NOTE = "資料為假資料，每一個時間、列數與訊息原文都是示意值"
DISPLAY_TZ = timezone(timedelta(hours=8))  # SET-GAP-時區
DISPLAY_TZ_LABEL = "UTC+8"

# SET-1 三類資料：44 逐字「一列一類資料（淨值、配息、市場指標）」
KIND_TABLES = (("淨值", "nav"), ("配息", "dividend"), ("市場指標", "market_indicator"))
# `44` 第四節 `source_tier` 值域（SET-GAP-層級名）。
TIERS = ("淨值", "配息", "市場指標", "其他")

MAX_AGE_KEY = "set_max_age_days"
KEEP_ROWS_KEY = "set_log_keep_rows"
VALUE_KINDS = ("int", "float", "date", "ratio", "list", "rules")
MULTILINE_KINDS = ("list", "rules")  # SET-GAP-輸入欄型態

# SET-GAP-型別說明文字
# 只寫格式，不給任何示例值（示例值等於替使用者代填一個候選值，G3†；照拍板原型「要輸入一個整數」的寫法）。
KIND_HINTS = {
    "int": "要輸入一個整數",
    "float": "要輸入一個數字",
    "ratio": "要輸入 0 到 1 之間的數字",
    "date": "要輸入 YYYY-MM-DD 格式的日期",
    "list": "要輸入 JSON 陣列",
    "rules": "要輸入 JSON 陣列，每一個元素是一條規則",
}

_EMPTY_TONE = {"來源缺": "灰", "算不出來": "黃", "部分缺": "黃", "系統錯誤": "紅"}
FETCHABLE_TABLES = ("nav", "dividend", "market_indicator", "fetch_log", "user_setting")


# ───────────────────────── 格式與時間 ─────────────────────────


def _parse_utc(text) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def format_time(utc_text) -> str:
    """`44` 第四節：時間欄以世界協調時間存放，顯示時才轉當地時區。時區字面值寫在表頭（SET-GAP-時區）。"""
    return f"{_parse_utc(utc_text).astimezone(DISPLAY_TZ):%Y-%m-%d %H:%M}"


def days_since(utc_text, now_utc) -> int:
    """距今日數（`days_calendar`）：UTC+8 的日曆日相減（SET-GAP-距今時區）。"""
    then = _parse_utc(utc_text).astimezone(DISPLAY_TZ).date()
    today = _parse_utc(now_utc).astimezone(DISPLAY_TZ).date()
    return (today - then).days


def fetch_failed_text(message: str) -> str:
    """`44` 5.5 `系統錯誤` 的文案模板。圖示只從 FETCH_FAIL_GLYPH 來；訊息原文照印，不改寫、不截斷。"""
    return f"{FETCH_FAIL_GLYPH} {TEXT_FETCH_FAILED}：{message}"


def save_failed_text(message: str) -> str:
    """`44` SET-4 空狀態：存檔寫入失敗 → 顯示失敗訊息原文。⛔ 開頭（客戶 2026-09-24 裁示）。"""
    return f"{SAVE_FAIL_GLYPH} {TEXT_SAVE_FAILED}：{message}"


def save_fail_box(message: str) -> list:
    """存檔寫入失敗框的兩行，照拍板草稿：第一行是失敗訊息原文（前面加 ⛔，客戶 2026-09-24 裁示），
    第二行是 TEXT_KEEP_INPUT。"""
    return [save_failed_text(message), TEXT_KEEP_INPUT]


def overdue_text(count: int) -> str:
    """44 逐字「有 N 筆資料超過你設定的新鮮度上限」"""
    return f"有 {count} {TEXT_OVERDUE_TAIL}"


def fetch_error(dataset, table):
    return (dataset.get("errors") or {}).get(table)


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
    tone = _STATUS_BADGE_TONE[text]
    glyph = {"灰": EMPTY_GLYPH, "紅": FETCH_FAIL_GLYPH}.get(tone, WARN_GLYPH)
    return {"_kind": "狀態", "text": text, "_tone": tone, "glyph": glyph}


def _redline_badge(mark: str) -> dict:
    return {"_kind": "紅線", "text": mark, "_tone": "中性"}


def _button(label, kind, *, enabled=True, disabled_reason="") -> dict:
    if kind not in BUTTON_KINDS:
        raise ValueError(f"按鈕類別 {kind!r} 不在 `44` 5.3 的八類之內")
    for word in FORBIDDEN_BUTTON_WORDS:
        if word in label:
            raise ValueError(f"按鈕標籤 {label!r} 含禁詞 {word!r}（`44` 1.1）")
    return {
        "_action_kind": kind,
        "_writes": set(_BUTTON_WRITES[kind]),
        "_enabled": bool(enabled),
        "label": label,
        "disabled_reason": disabled_reason,
    }


def _placeholder(text: str, kind: str, *, glyph: str = "") -> dict:
    node = {"text": text, "_empty_kind": kind, "_tone": _EMPTY_TONE[kind]}
    if glyph:
        node["glyph"] = glyph
    return node


def _fail_node(message: str) -> dict:
    # SET-GAP-取數失敗：通用模板，不畫重新取數。
    return _placeholder(fetch_failed_text(message), "系統錯誤")


# ───────────────────────── user_setting ─────────────────────────


def value_matches_kind(value: str, kind) -> bool:
    """SET-GAP-型別判定規則。`kind` 為 `None` 時不判（SET-GAP-型別缺），回真。"""
    if kind is None:
        return True
    if kind not in VALUE_KINDS:
        raise ValueError(f"value_kind {kind!r} 不在 `44` 4.5 那六種之內")
    text = value.strip()
    if kind == "int":
        return re.fullmatch(r"-?\d+", text) is not None
    if kind in ("float", "ratio"):
        if re.fullmatch(r"-?\d+(\.\d+)?", text) is None:
            return False
        return kind == "float" or 0.0 <= float(text) <= 1.0
    if kind == "date":
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text) is None:
            return False
        try:
            date.fromisoformat(text)
        except ValueError:
            return False
        return True
    try:
        parsed = json.loads(text)
    except ValueError:
        return False
    return isinstance(parsed, list)


def settings_failure(dataset):
    return fetch_error(dataset, "user_setting")


def setting_rows(dataset, known_keys) -> list:
    """SET-GAP-鍵清單：規格掃出的鍵 ＋ 表裡實際有的列，依 `setting_key` 排列。讀不到表時回空（由各塊畫失敗框）。"""
    if settings_failure(dataset) is not None:
        return []
    table = {row["setting_key"]: row for row in dataset["user_setting"]}
    out = []
    for key in sorted(set(table) | set(known_keys)):
        row = table.get(key)
        if row is None:
            # 表裡沒有這一列：未設定（`44` 4.5「未設定的鍵 `setting_value` 為空」），型別取規格快照。
            row = {"setting_key": key, "setting_value": None, "value_kind": known_keys.get(key), "updated_at": None}
        out.append(dict(row))
    return out


def _setting_state(dataset, key, known_keys):
    """回 (狀態, 整數值)：狀態為 failed／unset／bad／ok。"""
    if settings_failure(dataset) is not None:
        return "failed", None
    for row in setting_rows(dataset, known_keys):
        if row["setting_key"] == key:
            value = row["setting_value"]
            if value is None:
                return "unset", None
            if not value_matches_kind(value, "int"):
                return "bad", None
            return "ok", int(value.strip())
    raise KeyError(f"user_setting 沒有 {key!r} 這一列")


# ───────────────────────── SET-1 ─────────────────────────


def _build_set1(dataset, known_keys) -> dict:
    """SET-GAP-觀測日欄：不畫觀測日欄。SET-GAP-來源徽章：不另掛來源與新鮮度徽章。"""
    now = dataset["now_utc"]
    limit_state, limit = _setting_state(dataset, MAX_AGE_KEY, known_keys)
    rows = []
    for label, table in KIND_TABLES:
        failure = fetch_error(dataset, table)
        row = {"_kind_label": label, "kind_text": label, "badges": [], "_failed": False, "_empty": False}
        if failure is not None:
            # SET-GAP-讀取失敗逐列
            row.update(_failed=True, at_text=fetch_failed_text(failure), days_text="⬜", compare_text="⬜")
            row["_days"] = None
        elif not dataset[table]:
            # 44 逐字「某類無任何列 → 三欄皆 `⬜` 並掛 `資料未備` 徽章」
            row.update(_empty=True, at_text="⬜", days_text="⬜", compare_text="⬜", _days=None)
            row["badges"] = [status_badge("資料未備")]
        else:
            latest = max(r["fetched_at"] for r in dataset[table])
            days = days_since(latest, now)
            row.update(at_text=format_time(latest), days_text=str(days), _days=days)
            if limit_state == "failed":
                row["compare_text"] = "⬜"  # SET-GAP-設定取數失敗：值取不到，不說成未設定
            elif limit_state == "unset":
                row["compare_text"] = TEXT_NA_NO_LIMIT
            elif limit_state == "bad":
                row["compare_text"] = TEXT_NA_BAD_KIND
            else:
                # SET-GAP-端點：大於等於上限算外（由 44 SET-1 判準推得）。SET-GAP-內外不著色。
                row["compare_text"] = TEXT_OUT if days >= limit else TEXT_IN
        rows.append(row)
    fail_nodes = []
    if limit_state == "failed":
        fail_nodes.append(_fail_node(settings_failure(dataset)))
    overdue = sum(1 for r in rows if r["compare_text"] == TEXT_OUT)
    read_failure = next((fetch_error(dataset, t) for _l, t in KIND_TABLES if fetch_error(dataset, t)), None)
    if read_failure is None and limit_state == "failed":
        read_failure = settings_failure(dataset)
    if read_failure is not None:
        tone = "紅"
    elif any(r["_empty"] for r in rows) or limit_state in ("unset", "bad"):
        tone = "灰"
    else:
        tone = "中性"
    if limit_state == "ok":
        limit_line = f"新鮮度上限 {limit} 日（{MAX_AGE_KEY}）"
    elif limit_state == "unset":
        limit_line = f"新鮮度上限：{TEXT_UNSET}（{MAX_AGE_KEY}）"
    elif limit_state == "bad":
        limit_line = f"新鮮度上限：{TEXT_NA_BAD_KIND}（{MAX_AGE_KEY}）"
    else:
        limit_line = ""
    return {
        "code": "SET-1",
        "title": BLOCK_TITLES["SET-1"],
        "answers": ANSWERS["SET-1"],
        "_layer": 2,
        "_default_open": True,
        "_tone": tone,
        "_limit_state": limit_state,
        "_overdue": overdue if limit_state == "ok" else 0,
        "_read_failure": read_failure,
        "column_labels": ["資料類", f"最近取得時間（{DISPLAY_TZ_LABEL}）", "距今日數（days_calendar）", "與上限比較"],
        "_rows": rows,
        "fail_nodes": fail_nodes,
        "limit_lines": [limit_line] if limit_line else [],
        "detail_lines": [
            f"距今日數大於等於上限寫外，由 44 本塊判準推得：「{TEXT_SET1_JUDGE}」。",
            HINT_NOTE,
        ],
        "buttons": [],
    }


# ───────────────────────── SET-2 ─────────────────────────


def latest_per_tier(logs) -> dict:
    out = {}
    for row in logs:
        tier = row["source_tier"]
        if tier not in TIERS:
            raise ValueError(f"fetch_log 的 source_tier {tier!r} 不在 `44` 第四節那四個之內（SET-GAP-fetch_log值域越界）")
        if tier not in out or row["started_at"] > out[tier]["started_at"]:
            out[tier] = row
    return out


def _build_set2(dataset) -> dict:
    base = {
        "code": "SET-2",
        "title": BLOCK_TITLES["SET-2"],
        "answers": ANSWERS["SET-2"],
        "_layer": 2,
        "_default_open": True,
        "column_labels": ["來源層級", "最近一次結果", f"最近一次時間（{DISPLAY_TZ_LABEL}）", "訊息原文"],
        "detail_lines": [TEXT_SET2_RAW + "。" + TEXT_SET2_NO_DIRECTION + "。", HINT_NOTE],
        "buttons": [],
    }
    failure = fetch_error(dataset, "fetch_log")
    if failure is not None:
        return {**base, "_tone": "紅", "_rows": [], "placeholder": _fail_node(failure),
                "_failed_tiers": (), "_no_records": False, "_read_failure": failure}
    logs = dataset["fetch_log"]
    if not logs:
        # 44 逐字「各層級皆無紀錄 → `來源缺`，文案「尚無取數紀錄」」。SET-GAP-來源缺按鈕：不畫重新取數。
        node = _placeholder(TEXT_NO_RECORDS, "來源缺", glyph=EMPTY_GLYPH)
        return {**base, "_tone": "灰", "_rows": [], "placeholder": node,
                "_failed_tiers": (), "_no_records": True, "_read_failure": None}
    latest = latest_per_tier(logs)
    rows, failed = [], []
    for tier in TIERS:  # 44 逐字「四個逐一列出，不依 `fetch_log` 裡有沒有紀錄而增減」
        row = {"_tier": tier, "tier_text": tier, "badges": [], "_tone": "中性"}
        record = latest.get(tier)
        if record is None:
            row.update(result_text="⬜", time_text="⬜", message_text="⬜", _tone="灰")
            row["badges"] = [status_badge("資料未備")]
        elif record["outcome"] == "failed":
            failed.append(tier)
            message = record["message"]
            row.update(result_text="failed", time_text=format_time(record["started_at"]),
                       message_text="⬜" if message is None else message, _tone="紅")
            row["badges"] = [status_badge("取數失敗")]
        elif record["outcome"] == "ok":
            if record["row_count"] == 0:
                message = TEXT_EMPTY_RESPONSE  # SET-GAP-回應為空
            else:
                message = "—"  # SET-GAP-ok訊息欄
            row.update(result_text="ok", time_text=format_time(record["started_at"]), message_text=message)
        else:
            raise ValueError(f"fetch_log.outcome {record['outcome']!r} 不是 ok 或 failed（`44` 4.5；SET-GAP-fetch_log值域越界）")
        rows.append(row)
    tone = "紅" if failed else ("灰" if any(r["_tone"] == "灰" for r in rows) else "中性")
    return {**base, "_tone": tone, "_rows": rows, "placeholder": None,
            "_failed_tiers": tuple(failed), "_no_records": False, "_read_failure": None}


# ───────────────────────── SET-0 ─────────────────────────

_LAMP_LOOK = {
    "灰": (EMPTY_GLYPH, "狀態：無逾期、無失敗來源"),
    "黃": (WARN_GLYPH, "狀態：有逾期"),
}


def conclusion_light(set1, set2) -> dict:
    """`44` SET-0。**只讀 SET-1 的逾期筆數與 SET-2 的失敗來源數**，不自取數。"""
    read_failure = set2["_read_failure"] or set1["_read_failure"]
    if read_failure is not None:
        # SET-GAP-燈讀取失敗
        return {"_tone": "紅", "text": fetch_failed_text(read_failure), "_state": "讀取失敗"}
    failed = set2["_failed_tiers"]
    if failed:
        # SET-GAP-燈紅與空狀態相撞：失敗來源優先於空狀態欄。SET-GAP-紅燈文案。
        return {"_tone": "紅", "text": "失敗的來源層級：" + "、".join(failed), "_state": "來源失敗"}
    # 44 逐字「空狀態欄那兩句任一成立時，改出空狀態欄那一句，本句不出」
    if set1["_limit_state"] == "unset":
        # SET-GAP-燈兩句同時成立：取空狀態欄第一句。
        return {"_tone": "灰", "text": TEXT_NO_LIMIT, "_state": "空狀態"}
    if set1["_limit_state"] == "bad":
        # SET-GAP-上限型別不符
        return {"_tone": "灰", "text": TEXT_NA_BAD_KIND, "_state": "空狀態"}
    if set2["_no_records"]:
        return {"_tone": "灰", "text": TEXT_NO_RECORDS, "_state": "空狀態"}
    if set1["_overdue"] > 0:
        return {"_tone": "黃", "text": overdue_text(set1["_overdue"]), "_state": "有逾期"}
    # SET-GAP-某類無列不入燈
    return {"_tone": "灰", "text": TEXT_ALL_OK, "_state": "齊"}


def _build_set0(set1, set2) -> dict:
    light = conclusion_light(set1, set2)
    if light["_tone"] == "紅":
        # SET-GAP-燈圖示共用：紅燈的圖示也經由 FETCH_FAIL_GLYPH。
        glyph = FETCH_FAIL_GLYPH
        state_word = "狀態：取數失敗" if light["_state"] == "讀取失敗" else "狀態：來源失敗"
    elif light["_state"] == "空狀態":
        glyph, state_word = EMPTY_GLYPH, "狀態：尚不足以判定"
    else:
        glyph, state_word = _LAMP_LOOK[light["_tone"]]  # SET-GAP-燈狀態字
    return {
        "code": "SET-0",
        "title": BLOCK_TITLES["SET-0"],
        "answers": ANSWERS["SET-0"],
        "_layer": 1,
        "_default_open": True,
        "_reads": ("SET-1", "SET-2"),
        "_tone": light["_tone"],
        "_state": light["_state"],
        "glyph": glyph,
        "state_word": state_word,
        "text": light["text"],
        "detail_lines": [TEXT_LAMP_DATA_ONLY + "。本燈只讀 SET-1 的逾期筆數與 SET-2 的失敗來源數。"],
        "buttons": [],
    }


# ───────────────────────── SET-3 ─────────────────────────


def _value_cell(value, kind):
    """回 (目前值那一格的字串, 第二行原始字面值 或 "")。"""
    if value is None:
        return TEXT_UNSET, ""
    if not value_matches_kind(value, kind):
        # SET-GAP-原始字面值位置
        return TEXT_NA_BAD_KIND, "原始字面值：" + value
    return value, ""


def _build_set3(dataset, known_keys) -> dict:
    base = {
        "code": "SET-3",
        "title": BLOCK_TITLES["SET-3"],
        "answers": ANSWERS["SET-3"],
        "_layer": 2,
        "_default_open": True,
        "column_labels": ["鍵名", "目前值", "型別（value_kind）", f"最後修改時間（{DISPLAY_TZ_LABEL}）"],
        "detail_lines": [
            TEXT_SET3_NO_DEFAULT_COLUMN + "。",
            # SET-GAP-鍵清單／SET-GAP-當下值或已存值
            "⚠ 44 沒有把鍵列成一張表；本卡的鍵是本頁從 44 掃出來的，數目不是 44 給的。本卡讀的是已存值。",
            HINT_NOTE,
        ],
        "buttons": [],
    }
    failure = settings_failure(dataset)
    if failure is not None:
        # SET-GAP-設定取數失敗
        return {**base, "_tone": "紅", "_rows": [], "placeholder": _fail_node(failure)}
    rows = []
    for row in setting_rows(dataset, known_keys):
        value_text, raw_text = _value_cell(row["setting_value"], row["value_kind"])
        rows.append(
            {
                "_key": row["setting_key"],
                "key_text": row["setting_key"],
                "value_text": value_text,
                "raw_text": raw_text,
                "kind_text": row["value_kind"] or "⬜",  # SET-GAP-型別缺
                "time_text": format_time(row["updated_at"]) if row["updated_at"] else "⬜",  # SET-GAP-updated_at空
            }
        )
    grey = any(r["value_text"] in (TEXT_UNSET, TEXT_NA_BAD_KIND) for r in rows)
    return {**base, "_tone": "灰" if grey else "中性", "_rows": rows, "placeholder": None}


# ───────────────────────── SET-4 ─────────────────────────


def _used_by_text(key, key_used_by) -> str:
    blocks = key_used_by.get(key, ())
    if not blocks:
        return "改這個鍵會影響：44 各塊的來源欄沒有宣告用它"  # SET-GAP-影響哪幾塊
    return "改這個鍵會影響：" + "、".join(blocks)


def _build_set4(dataset, known_keys, key_used_by) -> dict:
    save_errors = dataset.get("save_errors") or {}
    save_inputs = dataset.get("save_inputs") or {}
    failure = settings_failure(dataset)
    inputs = []
    for row in setting_rows(dataset, known_keys):
        key, kind, stored = row["setting_key"], row["value_kind"], row["setting_value"]
        # 44 逐字「該欄的當下輸入留在畫面上不清掉」—— 失敗的那一鍵畫的是當下輸入，不是已存值。
        current = save_inputs.get(key, stored)
        hint_lines = []
        if current is not None and current != "" and not value_matches_kind(current, kind):
            # SET-GAP-型別說明文字。句尾照拍板原型；其中「不存檔，SET-3 的值不變」是 44 SET-4 空狀態欄的字。
            hint_lines.append(f"型別說明：這個鍵的 value_kind 是 {kind}，{KIND_HINTS[kind]}。{TEXT_NOT_SAVED}")
        fail_lines = save_fail_box(save_errors[key]) if save_errors.get(key) else []
        # `44` 4.5：未設定的鍵畫面顯示 ⬜ 未設定，不顯示任何候選值（輸入欄本身留空）。
        unset_lines = [TEXT_UNSET] if stored is None and key not in save_inputs else []
        inputs.append(
            {
                "_input": True,
                "name": key,
                "label": f"{key}（{kind or '⬜'}）",  # SET-GAP-輸入欄型態
                "_kind": kind,
                "_multiline": kind in MULTILINE_KINDS,
                "_value": stored,
                "value_text": "" if current is None else current,
                "used_by_text": _used_by_text(key, key_used_by),
                "hint_lines": hint_lines,
                "unset_lines": unset_lines,
                "fail_lines": fail_lines,
            }
        )
    fail_nodes, orphan_fail_lines = [], []
    if failure is not None:
        fail_nodes.append(_fail_node(failure))  # SET-GAP-設定取數失敗
        # SET-GAP-失敗無輸入欄
        # 此時畫面上沒有任何輸入欄，第二行（「上面這一欄的當下輸入…」）會是假話 —— 只印第一行。
        orphan_fail_lines = [[save_failed_text(message)] for _k, message in sorted(save_errors.items()) if message]
    unset = sum(1 for f in inputs if f["_value"] is None)
    if failure is not None:
        summary = f"{TEXT_FETCH_FAILED}：user_setting"
    else:
        missing = [f["name"] for f in inputs if f["_value"] is None]
        # `44` 5.4：摘要在資料缺時寫出缺什麼。
        summary = f"{len(inputs)} 個鍵" + (f"，{unset} 個未設定：" + "、".join(missing) if missing else "，皆已設定")
    tone = "紅" if failure is not None else ("灰" if any(f["fail_lines"] for f in inputs) else "中性")
    return {
        "code": "SET-4",
        "title": BLOCK_TITLES["SET-4"],
        "answers": ANSWERS["SET-4"],
        "_layer": 3,
        "_default_open": False,
        "_tone": tone,
        "summary_text": summary,
        "inputs": inputs,
        "fail_nodes": fail_nodes,
        "orphan_fail_lines": orphan_fail_lines,
        # SET-GAP-清除鈕：只掛存檔一枚。SET-GAP-存檔停用：不宣告停用條件。SET-GAP-必要鍵：不標必要鍵。
        "buttons": [_button(TEXT_SAVE, "存檔")],
        "detail_lines": [
            TEXT_SET4_PER_KEY.replace("`", "") + "。",
            TEXT_SET4_CLEAR + "；本塊只掛「存檔」一枚，清除＝把該鍵的輸入欄清空後存檔。",
            "本塊不提供還原為系統值之類的動作 —— " + TEXT_SET4_NO_RESTORE + "（G1†、G3†）。",
            # SET-GAP-無後端
            "⚠ 本頁沒有後端：「存檔」按得下去，但不寫任何東西。",
        ],
    }


# ───────────────────────── SET-5 ─────────────────────────


def set5_button(picked) -> dict:
    """44 逐字「未選層級 → 按鈕停用，停用原因「尚未選定來源層級」」。`picked` 是畫面上單選的當下值。"""
    if picked is not None and picked not in TIERS:
        raise ValueError(f"來源層級 {picked!r} 不在 `44` 第四節那四個之內")
    return _button(TEXT_REFETCH, "取數", enabled=picked is not None,
                   disabled_reason="" if picked is not None else TEXT_NO_TIER_PICKED)


def _build_set5() -> dict:
    return {
        "code": "SET-5",
        "title": BLOCK_TITLES["SET-5"],
        "answers": ANSWERS["SET-5"],
        "_layer": 3,
        "_default_open": False,
        "_tone": "中性",
        "summary_text": "可選四個來源層級：" + "／".join(TIERS),
        # SET-GAP-層級單選：初次開啟不預選。
        "tier_options": TIERS,
        "tier_label": "來源層級",
        "buttons": [set5_button(None)],
        "detail_lines": [
            TEXT_SET5_WRITES.replace("`", "") + "。",
            # SET-GAP-SET5寫到哪／SET-GAP-執行中／SET-GAP-無後端
            "⚠ 本頁沒有後端：「重新取數」按得下去，但不取數、不寫 fetch_log，也不演執行中那一態。",
        ],
    }


# ───────────────────────── SET-6 ─────────────────────────


def _duration_text(record) -> str:
    if record["finished_at"] is None:
        return TEXT_NA_NO_FINISH
    seconds = (_parse_utc(record["finished_at"]) - _parse_utc(record["started_at"])).total_seconds()
    return f"{seconds:.1f}"  # SET-GAP-耗時格式


def _build_set6(dataset, known_keys) -> dict:
    labels = ["log_id", "來源層級", f"開始（{DISPLAY_TZ_LABEL}）", "耗時（秒）", "結果", "取回列數", "訊息"]
    base = {
        "code": "SET-6",
        "title": BLOCK_TITLES["SET-6"],
        "answers": ANSWERS["SET-6"],
        "_layer": 4,
        "_default_open": False,
        "column_labels": labels,
        "detail_lines": [TEXT_SET6_ORDER.replace("`", "") + "。", HINT_NOTE],
        "buttons": [],
    }
    failure = fetch_error(dataset, "fetch_log")
    if failure is not None:
        return {**base, "_tone": "紅", "_rows": [], "placeholder": _fail_node(failure), "tail_lines": [],
                "summary_text": f"{TEXT_FETCH_FAILED}：fetch_log"}
    logs = sorted(dataset["fetch_log"], key=lambda r: r["started_at"], reverse=True)
    if not logs:
        node = _placeholder(TEXT_NO_RECORDS, "來源缺", glyph=EMPTY_GLYPH)  # SET-GAP-來源缺按鈕
        return {**base, "_tone": "灰", "_rows": [], "placeholder": node, "tail_lines": [],
                "summary_text": "缺 fetch_log：" + TEXT_NO_RECORDS}
    keep_state, keep = _setting_state(dataset, KEEP_ROWS_KEY, known_keys)
    tail = []
    if keep_state == "ok" and keep >= 0:
        shown = logs[:keep]
        # SET-GAP-保留筆數移除。保留 0 筆時表上零列，但紀錄是存在的 —— 不說成尚無取數紀錄（SET-GAP-保留筆數為零）。
        tail.append(f"保留筆數上限 {keep}（{KEEP_ROWS_KEY}），已移除 {len(logs) - len(shown)} 筆")
    elif keep_state == "ok":
        shown = logs
        # SET-GAP-保留筆數為負：型別合（int），值不能當筆數用；不說成值與型別不符。
        tail.append(f"保留筆數上限 {keep}（{KEEP_ROWS_KEY}）：{TEXT_NA_NEGATIVE_KEEP}；全部列出")
    elif keep_state == "failed":
        shown = logs
        tail.append(f"保留筆數上限讀不到：{fetch_failed_text(settings_failure(dataset))}；全部列出")
    elif keep_state == "unset":
        shown = logs
        tail.append(f"保留筆數上限 {TEXT_UNSET}（{KEEP_ROWS_KEY}）；全部列出")
    else:
        shown = logs
        tail.append(f"保留筆數上限 {TEXT_NA_BAD_KIND}（{KEEP_ROWS_KEY}）；全部列出")
    rows = [
        {
            "_log_id": r["log_id"],
            "cells": [
                r["log_id"],
                r["source_tier"],
                format_time(r["started_at"]),
                _duration_text(r),
                r["outcome"],
                "⬜" if r["row_count"] is None else str(r["row_count"]),
                "—" if r["message"] is None else r["message"],
            ],
        }
        for r in shown
    ]
    tone = "紅" if keep_state == "failed" else ("灰" if any(TEXT_NA_NO_FINISH in r["cells"] for r in rows) else "中性")
    return {**base, "_tone": tone, "_rows": rows, "placeholder": None, "tail_lines": tail,
            "summary_text": f"{len(rows)} 列"}


# ───────────────────────── SET-7 ─────────────────────────


def expand_sources(spec) -> dict:
    """{塊代號: [表.欄位, …]}；`表.*` 展成那張表的每一欄（SET-GAP-SET7母體）。"""
    tables = dict(spec["tables"])
    out = {}
    for code, declared in spec["block_sources"]:
        fields = out.setdefault(code, [])
        for token in declared:
            name, _dot, column = token.partition(".")
            if column == "*" and name in tables:
                fields.extend(f"{name}.{c}" for c in tables[name])
            else:
                fields.append(token)
    return out


def _build_set7(dataset) -> dict:
    """SET-GAP-SET7寫死：讀的是 fixtures 的規格快照，不是執行時的 44。"""
    spec = dataset["spec"]
    defined = [f"{t}.{c}" for t, cols in spec["tables"] for c in cols]
    used = expand_sources(spec)
    users = {}
    for code, fields in used.items():
        for field in fields:
            users.setdefault(field, [])
            if code not in users[field]:
                users[field].append(code)
    rows = []
    for field in defined:
        blocks = users.get(field, [])
        rows.append({"_field": field, "field_text": field, "_blocks": tuple(blocks),
                     "blocks_text": "、".join(blocks) if blocks else TEXT_UNUSED, "badges": []})
    undefined = [f for f in users if f not in defined]
    for field in undefined:
        # 44 逐字「該欄位單獨列出並掛「未定義」徽章」
        rows.append({"_field": field, "field_text": field, "_blocks": tuple(users[field]),
                     "blocks_text": "、".join(users[field]), "badges": [status_badge("未定義")]})
    summary = f"第四節 {len(spec['tables'])} 張表 {len(defined)} 個欄位"
    if undefined:
        summary += f"，另有 {len(undefined)} 個未定義"
    return {
        "code": "SET-7",
        "title": BLOCK_TITLES["SET-7"],
        "answers": ANSWERS["SET-7"],
        "_layer": 4,
        "_default_open": False,
        "_tone": "黃" if undefined else "中性",
        "summary_text": summary,
        "column_labels": ["欄位名（表.欄位）", "用到它的塊代號清單"],
        "_rows": rows,
        "placeholder": None,
        "detail_lines": [
            TEXT_SET7_NO_INFERENCE + "。",
            TEXT_RULE_SCOPE + "；規則欄或空狀態欄用到、卻沒有在來源欄宣告的欄位，本表結構上抓不到（44 自己寫的射程限制）。",
        ],
        "buttons": [],
    }


# ───────────────────────── 整頁 ─────────────────────────


def build_page_model(dataset: dict) -> dict:
    """`dataset` 的形狀見 `fixtures._dataset`。本函式不改動 `dataset`。"""
    unknown = sorted(set(dataset.get("errors") or {}) - set(FETCHABLE_TABLES))
    if unknown:
        # SET-GAP-取數失敗／SET-GAP-其他表讀取失敗炸：本頁只處理五張表的讀取失敗；其餘的不假裝成空資料，炸掉。
        raise ValueError(f"資料集帶本頁沒有畫法的取數失敗 {unknown}")
    known_keys = dict(dataset["spec"]["setting_keys"])
    bad_save = sorted(set(dataset.get("save_errors") or {}) - set(known_keys))
    if bad_save:
        raise ValueError(f"存檔寫入失敗點名了本頁不認得的鍵 {bad_save}")
    key_used_by = dict(dataset["spec"]["key_used_by"])
    set1 = _build_set1(dataset, known_keys)
    set2 = _build_set2(dataset)
    blocks = [
        _build_set0(set1, set2),
        set1,
        set2,
        _build_set3(dataset, known_keys),
        _build_set4(dataset, known_keys, key_used_by),
        _build_set5(),
        _build_set6(dataset, known_keys),
        _build_set7(dataset),
    ]
    return {
        "title": PAGE_TITLE,
        "answers": PAGE_ANSWERS,
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
