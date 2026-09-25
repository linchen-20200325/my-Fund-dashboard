"""`docs/v2/` 底下受檢文件（`.md` 規格文件 ＋ `prototype/` 線框 HTML；
**射程的定義處是 `DOCS_GLOBS`，本句只是轉述**）的計數／指令／全稱句守衛 ——
讓「數字沒釘 SHA、指令自己掃自己、
全稱句沒有反向檢查」在 CI 當場紅燈，不再靠人工複驗。

**前例**：`tests/test_constitution_file_refs.py`（憲法的檔案引用守衛）。
那一支靠 CI 逼出 22 處過期路徑 —— **那 22 處不是靠人回頭讀發現的，是紅燈逼出來的**。
本檔是同一個做法換一個對象：`docs/v2/` 底下的規格／裁決／稽核文件。

---
## 客戶 2026-09-21 裁示（本檔的法源，逐字，不得改寫）

    1. 所有計數釘 commit SHA，不寫「工作樹」「HEAD」「origin/main..HEAD」。
    2. 計數指令不准寫進被計數的檔。
    3. 凡「每一個」「所有」「全部」「都」開頭的斷言，
       必須附反向檢查指令與輸出。沒有反向檢查的，不准寫。

---
## 三道檢查（各自獨立成一個 test，一道紅不影響另外兩道的可讀性）

* **(A) `test_counting_sentences_pin_a_commit_sha`**
  一個**句段**若同時含「掃描指令」與「數字＋量詞」，它就是一句**計數**，
  必須在同一句段內出現 commit SHA（7–40 位十六進位、且至少含一個 `a`–`f`）。
  `origin/main` / `HEAD` / `工作樹` **不算釘** —— 它們是會移動的 ref，
  下一個人照跑會拿到不同的數字，那個計數就不可重現。

* **(B) `test_scan_commands_do_not_live_in_the_file_they_scan`**
  一個句段若同時含「掃描指令」與**該檔自己的檔名**，就是**指令自計**：
  掃 `X` 的指令寫進 `X` 自己，它會把自己算進去。
  `docs/v2/41_counters.md` 開頭的硬禁令講的就是這件事。

* **(C) `test_sentence_initial_universals_carry_a_reverse_check`**
  **句首**的「每一個／所有／全部／都」斷言，必須在它自己那一行起算的**視窗**內
  找得到「指令 ＋ 輸出」。沒有反向檢查的全稱句，不准寫。

## 「句首」怎麼定義（客戶寫的是「**開頭**」，這裡把語意寫死）

母體不是「這四個詞出現幾次」。把那四個詞（字面見下方 `_UNIVERSAL_HEADS`，
**刻意不在本段重印**，理由同 `CLAUDE.md` §-2.A 第 8 款：受測字串寫進文件就會被自己掃到）
交給 `git grep -ohE ... -- 'docs/v2/*.md' | wc -l`，在 `0d9753f` 上的**出現次數**是 **1915** 次；
但其中絕大多數是句中副詞（例：「三處**都**是…」），**不是**以它開頭的斷言。

本檔的「句首」＝ 把全文切成**句段**之後，**去掉排版裝飾**，第一個字就是那四個詞之一：

1. **切句段**：在換行、`。！？!?；;`、`<br>` 處切開；**只有 markdown 表格列**
   （該行第一個非空白字元是豎線的那種）**額外**在未跳脫的豎線處再切 ——
   表格一格就是一個獨立斷言。
   ⚠️ **非表格列一律不切豎線**：那裡的豎線是 shell pipeline 或 regex 的交替符號。
   本檔的負控抓到過這個：早期版本一律切，於是一條釘好 SHA 的
   `git show <sha>:path | grep -c …` 會被切成兩半，後半看不到 SHA 而被誤報。
2. **去排版裝飾**：反覆剝掉行首的空白、`>`、`#`、清單符號 `-`／`*`／`+`／`1.`、
   強調符號 `**`／`__`／`` ` ``／`~~`、`(1)`／`（1）` 這類序號、emoji 與符號
   （⚠️ ⛔ ✅ ❌ 📌 ⭐ → 之類）、**以及行首的 HTML 標籤**（`<p>`／`<li>`／`<b>`／`</td>` 之類）。
   ⚠️ **標籤那一項是第十二輪才補上的**（客戶 2026-09-23 裁示第 1 件）。在那之前，
   以標籤開頭的那一行，句首斷言**一律偵測不到** —— 而 `docs/v2/prototype/` 的線框整份是 HTML，
   它們的斷言幾乎都長在標籤後面，於是 (C) 對那一批檔形同空掃：
   **綠燈、而且少看**，正是本檔下限測試那一段在講的失效模式。
   ⚠️ **標籤的剝除與其餘裝飾同在一個迴圈裡剝到不動為止**，不是收尾單獨補一刀 ——
   兩者的差別量得出來：`<td>「…` 這種「標籤 ＋ 開引號」要兩者交替剝才看得到第一個實字，
   收尾補一刀的版本剝完標籤就停住，那一類會整批漏掉（本輪實測差兩句，見下方續記）。
   ⚠️ **`<!--` 不在標籤那一項的射程內**（`!` 不是標籤名的字元），**但被註解掉的句子並沒有因此逃掉**：
   ASCII `!` 本來就是上面第 1 步的切點，`<!-- 句子` 會在那裡被切開，剩下的 `--` 當成清單符號剝掉
   ⇒ 那句話照樣進 (C)。**本輪改動前後都是這個行為，不是本輪造成的。**
   ⛔ **本段初稿寫的是「註解掉的句首斷言不會被 (C) 看到」，那一句是假的** ——
   落筆時沒有實跑，被本輪自己新增的負控當場推翻（見
   `test_control_C_a_commented_out_universal_is_still_checked`）。留著這一筆，
   是因為它正是 `CLAUDE.md` §-2.A 第 1 款在講的那件事：能跑的東西不准用猜的。
3. **剩下的第一個字**是「每一個／所有/全部/都」之一，**且其後還有至少 2 個字**
   （擋掉表格裡只寫「全部」兩個字的那種格子 —— 那是欄位值，不是斷言）。

量測（**全部釘 `0d9753f`**，由本檔的 `--report` 與 `_is_sentence_initial_universal` 跑出來）：
本定義下**活的**句首斷言 **84** 句，其中已附反向檢查 **16** 句、缺 **68** 句。
`0d9753f` 上 **1915 → 84** 的收斂，來源只有「句首」這個限定，不是本檔偷偷放寬了什麼。

⚠️ **2026-09-23 第十二輪續記（定義多了「剝行首 HTML 標籤」那一項，數字跟著動）**：
上面那三個數是 `0d9753f` 的量測，**刻意不改寫** —— 帶日期的歷史量測值一律保留、只在後面續記。
本輪在 `325fa58` 上重量：`.md` 那一側的句首斷言候選 **85** 句，**與剝標籤前逐筆相同**；
`prototype/` 那一側在 `325fa58` 上由零變成 **11** 句，且那 **11** 句無一來自 `.md`。
⚠️ **「交替剝」與「收尾補一刀」在 `325fa58` 上實測差 2 句**（**11** vs **9**）——
差的那 **2** 句都是 `<td>「…` 這種「標籤 ＋ 開引號」的形狀，兩者要交替剝才看得到第一個實字。
**寫這一筆是因為它會被誤讀成量錯**：拿到 **9** 的人不是算錯，是剝除寫成了收尾補一刀。

## 刪除線：被 `~~` 劃掉的一律不檢查

本 repo 的核心慣例是「舊條文保留不刪 ＋ 加刪除線」。**被劃掉的舊句是已正確退役的紀錄**，
拿它紅燈只會逼後人去刪歷史 —— 那是**不可逆**的傷害。
本檔沿用 `tests/test_constitution_file_refs.py` 的 `strike_mask` 做法（含它那兩個
「配不到伴的 `~~` 不吃掉後文」的上限），理由與該處相同。

---
## baseline：本守衛**只擋新增的**

上面那三條規則是 **2026-09-21** 才定下來的；`docs/v2/` 底下絕大多數文字寫在那之前。
**沒有 baseline 的話，這支守衛一上線就紅燈，永遠進不了 main，等於沒有守衛。**

* **baseline 內的** → 跳過（它是「已登記的歷史欠債」，不是「已修好」）。
* **不在 baseline 內的** → **紅燈**，並印出檔名、正規化後的句子、以及修法指引。

### baseline 的 key **刻意不用行號**

這個 repo 的行號每一輪都在漂 —— **那正是本守衛要治的病之一**。
key ＝ `sha256(檔案相對路徑 + "\\0" + 正規化後的句子)` 取前 16 位。

**正規化規則（本段即為權威定義，改這裡等於讓整份 baseline 失效）**：

1. 去掉 markdown 強調符號：`**`、`__`、`~~`、反引號 `` ` ``。
2. 去掉行首的清單符號／引用符號／序號（同上「去排版裝飾」那一套）。
3. 連續空白（含全形空白 `　`、不斷行空白 ` `）一律壓成一個半形空格。
4. 去掉頭尾空白。
5. **其餘一個字都不動** —— 不轉全半形、不去標點、不小寫化。
   （中文文件裡全半形與標點本身就帶語意，動了會讓兩句不同的話撞同一個 key。）

### key 含檔案路徑，是刻意的

同一句話搬到另一個檔會**重新紅燈**。理由：baseline 記的是「**這個位置的這句話**已登記」，
不是「這句話在全 repo 通行」。一份豁免若能跨檔通用，就會變成
「A 檔登記過 ⇒ B 檔照抄免驗」—— 那正是 `CLAUDE.md` §8.2.A.1 驗證段 ④ 點名的失效模式
（**條件只往外用、不往內用**）。
⚠️ **代價據實寫明**：同一檔內**逐字相同**的多句會收斂成同一個 key，
baseline 一筆會蓋住那一檔內的全部同字句。這是已知的、刻意接受的粗粒度。

### 怎麼重建 baseline

    python3 tests/test_doc_counters.py --update-baseline [<rev>]   # 省略 <rev> ＝ HEAD

**產生端讀的是釘死的 commit，不是工作樹**（見 `docs_at_sha` 的說明）——
一份要求別人釘 SHA 的守衛，自己的 baseline 若產生自工作樹，就沒有人能原樣重建它。
本檔隨附的那一份釘在 **`6880a2b`**，`_generated_from_sha` 欄自陳其出處。
~~⚠️ 若主線已經往前走，commit 本守衛的人請對**實際的 merge base** 重跑一次，並**逐句讀** `git diff` —— 那份 diff 會列出這段期間新欠的債。~~
→ **2026-09-23 第十二輪就地更正（有意識的更正，不是漏刪 · 決策者 AI 總管，依客戶 2026-09-23 裁示第 3 件）**：
   上面那一句**在這個 repo 上不可執行**，理由與可執行版本見下。
   **舊表述的用意仍然成立** —— 「重建前要先確認基準、重建後要逐句讀 diff」這兩件事一字未變；
   **被權衡掉的是它指定的那個基準**：merge base 上沒有受檢檔，照它做只會拿到一個例外。

⛔ **自 2026-09-23 起：禁止用任何 SHA 重建這一份 baseline，只准手工增補。**
   **理由（實測，非推論）**：本份自該日起是**混合來源** —— 多數 entry 出自 `6880a2b`，
   但線框那 7 筆是**手工增補**的，而 `6880a2b` 上根本沒有 `prototype/`。
   對它重建實測產出 189／35／**65**：本輪 7 筆全消失，
   **連既有 5 筆 `why_safe` 與整個 `_why_safe_notes` 一起被洗掉**（產生端每筆只寫 `file` 與 `text`）。
   ⚠️ merge base 更不能用：`docs/v2/` 是功能分支才出現的（首見 `588e3ae`），
   而本分支與 `origin/main` 的 merge base（`9cbf037`）底下**一個受檢檔都沒有**，
   對它重建會撞上 `docs_at_sha` 那句「拒絕產生一份空的 baseline」——**那是對的行為，不是 bug**。
   ✅ **要登記新欠債就手工加一筆**：`file` ＝ 失敗訊息印的路徑、`text` ＝ 它印的那一句、
   `why_safe` ＝ 為什麼這一筆可以掛著；改完逐句讀那份 diff 再 commit。

⛔ **重建 baseline ＝ 承認新的違規，要有人明確決定。**
它不是「把紅燈弄綠」的按鈕：跑完之後 `git diff` 會列出每一筆新登記的句子，
**那份 diff 就是你在簽名承認的東西**，請逐句讀過再 commit。
本 repo 的正解一律是**先照 `_FIX_GUIDE_*` 修**，修不動才登記。

---
## ⚠️ 射程外（是「還沒解決」，不是「已解決」）

⛔ 下面三項**不得**被讀成「守衛已經涵蓋」。綠燈**不**代表 `docs/v2/` 的數字都查過了。

* **缺口 1｜(A) 只看「帶指令的」計數。** 一句「本表其餘 12 欄該指令確實回 0 行」
  沒有指令 token，**不會**被檢查。要補的人：把 `_COUNT_TOKEN` 的觸發條件放寬到
  「數字＋量詞」即可觸發，但那會把「3 個理由」這種非量測句一起抓進來，
  **必須先想好怎麼分辨量測與敘述**，不要直接放寬了事。
* **缺口 2｜(A) 只驗「有沒有 SHA」，不驗「那個 SHA 對不對」。**
  隨便寫一個 7 位十六進位字串就能過。要補的人：可用
  `git cat-file -e <sha>^{commit}` 驗存在性 —— 但那會讓本守衛依賴 git 物件庫，
  在 shallow clone（CI 預設）下可能誤紅，**先確認 fetch-depth 再做**。
* **缺口 3｜(C) 只驗「視窗內有指令與輸出」，不驗那個反向檢查**真的能推翻那句話。
  一條無關的指令貼在旁邊就能過。這一層需要讀懂語意，**機器判不到**。
* ~~**缺口 5｜(C) 逐行切段，對硬換行的 HTML 會把句中詞讀成句首。**~~
  → ✅ **2026-09-23 第十三輪已修**（客戶裁示第 1 件與第 2 件）。**整段原文保留不刪**，
  因為它記的是「當初為什麼會那樣、憑什麼判、憑什麼判錯」—— 那是下一個人唯一讀得到的病歷。
  **修法**：切段改成**看得見上一行結尾**（`_is_continuation` ／ `_starts_a_new_block` ／
  `_ends_a_block`；三條判準與極性寫在那一節的區塊註解）；剝除式補上五種逃網形狀
  （`_LEADING_QUOTE_OR_COLON` ／ 懂屬性的 `_LEADING_HTML_TAG` ／ `_LEADING_TAG_TAIL`）。
  **量測（工作樹，量測日 2026-09-23；`--report` 跑得出來，這些數會漂移，引用前請現場重跑）**：
  第十三輪**實作輪**：(C) 的命中由 **75** 降為 **65**，(A)／(B) 逐筆不動，新增違規 0 筆。
  第十三輪**回修輪**（把 `_ends_a_block` 的句末字表由 6 個字元補到 13 個，見 G1）：
  (C) 回到 **68**，(A) **207**、(B) **35**，**三項的新增違規都是 0**。
  ⚠️ **回來的 3 筆是刻意接受的誤紅**（`03_adjudication`／`23_ui_draft_01_macro`／`ui_prototype_today`）——
  它們是真續行，但上一行以 `）` 收尾，而 `）` 在中文裡同時是「收句」與「插入語結尾」，
  **單一字元判不出來**；三筆都已在 baseline 逐筆寫明這個張力。
  **淨下降的 7 筆逐筆看過**：3 筆是下面點名的線框登記，4 筆是 `.md` 的硬換行續行，
  **沒有一筆是「本來該抓卻被放過」**。
  ⚠️ **下面這段原文有三處在本輪被推翻，就地點名，不要照舊讀**：
  (1)「本輪只登記、不動判定」是**第十二輪**的狀態，不是現況；
  (2)「要補的人從這裡開始：把『前一個非空白行有沒有結句』納入句首判定」——
  **那條判準本輪實測太弱**，只用它會把 `` ``` `` 圍籬與標題的下一行、
  以及以 `**` 收尾的那種句子一起吃掉（本輪第一版就是這樣，實測多吃了 5 句，
  已改為「結構行 ＋ 行尾強調符號 ＋ 冒號」三補）；
  (3)「另有五種形狀目前仍逃得掉（**不必修**）」—— 本輪**已經全部修掉**，
  逐一配了正控與突變（`_ESCAPED_SHAPES`）。
  ⚠️ **那幾筆孤兒登記一個字都沒刪**（回修輪後為 **7 筆**），去留由總管裁決；
  狀態註記與機器守衛見 baseline 的 `_orphan_notes`、
  `test_control_annotated_orphans_are_really_orphans`（已註記的又活過來 → 紅）
  與 `test_orphans_without_an_annotation_are_a_red_light`（沒註記的孤兒 → 紅）。
  ⛔ **仍然成立、本輪沒有解決的那一半**：那幾句話**本身一個字未動**，
  它們**仍然是沒有反向檢查的全稱宣稱** —— 變的只有「守衛還看不看得到」。
  ⚠️ **本輪的射程外**（誠實揭露，不是免責）：`_LEADING_TAG_TAIL` **只收「第一個屬性帶成對引號的值」**，
  `class=foo>` 這種未加引號的**下半截**仍然逃得掉，裸屬性名（`disabled>`）、行首半形單引號、
  行首 ASCII 冒號同樣逃得掉 —— **四種方向全部是「少看」，沒有一種是誤抓**（稽核逐一驗過）。
  ⚠️ **反過來，本組上一輪把射程寫得比實況保守**：**完整標籤** `<td class=foo>`（未加引號的屬性值）
  其實**抓得到**（`_TAG_ATTR` 允許未加引號的值），`    title='y'>`（單引號）也抓得到。
  `_INLINE_TAGS` 是一張**行內標籤白名單**：漏收一個名字只會多紅、收錯一個會無聲漏抓，
  封閉性由 `test_control_inline_tag_table_is_closed_against_block_tags` 對
  `_BLOCK_LEVEL_TAGS` **逐一窮舉**（第十三輪回修前它是抽樣，只守得住自己寫下的六個名字）。

  ↓ **以下為第十二輪的原文，保留不刪** ↓
  （**2026-09-23 第十二輪登記，下一輪候選；本輪只登記、不動判定**）
  `split_segments` 以**行**為單位切，所以一句被硬換行斷開的話，**下半行的第一個詞就被當成句首**。
  markdown 很少這樣寫，但 `docs/v2/prototype/` 的線框是手寫 HTML，整份都在硬換行。
  **本輪的實證，就是 baseline 裡那 5 筆帶「硬換行假句首」`why_safe` 的登記**
  （`ui_prototype_alo` ／ `exp` ／ `set` ／ `today` ×2）—— 它們的全稱詞在原句裡都是句子中段的詞，
  逐筆的「前一行未結句」證據寫在各該筆的 `why_safe` 欄裡。
  要補的人從這裡開始：把「**前一個非空白行有沒有結句**」納入句首判定（本輪是用這個條件人工判的）。
  ⚠️ **那條判準太弱，已知至少 1 筆（`exp`）量測通過但結論不成立**（前一行是已閉合的 `</td>`，
  它真的是格首）—— 該筆的真正理由已就地改寫在它的 `why_safe` 裡，**分類依客戶裁示不動**。
  ⚠️ **另有五種形狀目前仍逃得掉**（2026-09-23 稽核登記，**不必修**，現況 0 個真實斷言落在上面）：
  半形雙引號開頭、`title="a>b"`、`title="a<b"`、跨行標籤的下半行、全形冒號開頭。
  ⚠️ **那 5 筆的內容仍然是本組的全稱宣稱** —— 切段修好之後**要回頭重判**，
  **不得**因為「已經進 baseline」就當成已結案。
  ⚠️ 改判定會讓那 5 筆的命中與否改變，**必須同一輪重新登記並逐句讀 diff**（同缺口 4 的警語）。
  📌 本輪把剝標籤後曝出來的 11 筆分流成：**改文件 4 筆**、**44 逐字進 baseline 2 筆**、
  **硬換行假句首進 baseline 5 筆**（客戶 2026-09-23 裁示）。
* **缺口 4｜(B) 的判定分不出「釘 SHA 的快照自掃」與「讀工作樹的自掃」。**
  前者（形如 `git show <凍結 sha>:<自己>`）讀的是凍結的 blob，
  這個檔**現在**長什麼樣影響不了它的輸出 —— **機制上不可能自計**；
  後者（對工作樹跑的掃描）才是這個 repo 連續數輪在治的那個病。
  `find_self_scanning_commands` 目前**只在 `note` 字串裡**分辨兩者（那個 `snapshot` 布林），
  **判定一律紅燈**；而 baseline 每一筆只留 `file` 與 `text`、**不留 `note`** ⇒
  兩種形態進了 baseline 之後長得一模一樣，**後人分不出哪一筆是無害的**。
  要補的人從這裡開始：把 `snapshot` 從「只影響訊息」升成「影響分區」，
  例如讓快照自掃落進一個獨立分區、與真正讀工作樹的那種分開記。
  ⚠️ **改分區 key 等於讓既有 baseline 的該區整區失效**（全部變回「新違規」），
  所以必須**同一輪重建 baseline 並逐句讀 diff**，不能只改判定就走。
  ⚠️ 更要先決定的是**該不該放行**：客戶裁示裡
  「計數指令不准寫進被計數的檔」那一條，**字面上沒有為快照開後門** ——
  放行它是**放寬規則**，不是修 bug，那個決定不該由守衛自己做掉。
  在那個決定做出來之前，正解是照現況紅燈、逐筆登記 baseline 並寫明理由
  （本輪已對 5 筆這樣做，理由寫在 baseline 的 `why_safe` 欄）。
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs" / "v2"

# 受檢語料 —— 每一項是 `(glob, 這個 glob 至少要看到幾個檔)`。
#
# ⚠️ **下限綁在「每一個 glob」上，不是只綁總數** —— 這是本輪擴射程最關鍵的一根釘子：
#    只綁總數的話，有人把 `prototype/*.html` 那一列拿掉，剩下的 `.md` 照樣遠超總數下限
#    ⇒ **三道檢查全綠、而且少看了五個檔、沒有任何人會發現**。那正是本檔
#    「綠燈但少看」那一段要擋的失效模式，只是換到射程這一層。
# ⚠️ **glob 的語意是 `Path.glob`（非遞迴）**：`*.md` 只收 `docs/v2/` 的直屬子檔，
#    **不含** `prototype/` 底下的。要收子目錄必須像下面那樣把目錄寫出來。
DOCS_GLOBS: tuple[tuple[str, int], ...] = (
    ("*.md", 15),
    ("prototype/*.html", 5),
)
BASELINE_PATH = Path(__file__).resolve().parent / "doc_counters_baseline.json"

# baseline 的三個分區 key（改名等於讓既有 baseline 的該區整區失效）
SEC_COUNTS = "counts_without_sha"
SEC_SELFSCAN = "self_scanning_commands"
SEC_UNIVERSALS = "universals_without_reverse_check"
# baseline 自陳它是從哪個 commit 產生的 —— 讓它可以被**原樣重建**。
META_SHA = "_generated_from_sha"


def _matches_glob(rel_to_docs_dir: str, pattern: str) -> bool:
    """一條 `DOCS_GLOBS` 的 glob 對一條相對路徑的配對 —— **配對邏輯的單一實作**。

    ⚠️ **`_in_scope()`（受檢與否）與 `scope_counts()`（逐 glob 幾個檔）都只走這裡。**
    第十一輪稽核實測過兩邊各寫一套的後果（隔離副本重跑確認）：只要讓射程判定
    多排除一類檔、而 `DOCS_GLOBS` 一字未動，`iter_docs()` 就讀到 0 個線框、
    `scope_counts()` 卻仍宣稱 5 個 ⇒ **逐 glob 下限不紅，那批檔已經沒有人在檢查。**
    （`--report` 的「受檢檔數」那一行會掉下來，但**沒有任何測試會因此紅** ——
    那一行只比 `_MIN_DOCS`，少掉整批線框之後仍然遠高於它。）

    ⚠️ **刻意不拿 `fnmatch` 或 `PurePath.match` 去比整條路徑** —— 兩者都表達不出
    「非遞迴」，但**成因不同，別混為一談**（py3.11.15 實測）：

    * `fnmatch.fnmatchcase("prototype/x.md", "*.md")` → True：它的 `*` **會吃掉 `/`**。
    * `PurePath("prototype/x.md").match("*.md")` → True：它的 `*` **不**吃 `/`
      （`PurePath("a/b/x.md").match("a/*.md")` → False 即為證），
      為 True 的成因是**相對 pattern 從右端錨定**，左邊多幾層都算命中。

    兩種語意都會讓子目錄的檔被上層的 glob 收進來，**非遞迴當場破掉**。
    故這裡把 glob 拆成「目錄部分逐字相等 ＋ 檔名部分 `fnmatch`」，
    自己做出 `Path.glob`（非遞迴）的語意；`iter_docs()` 實際走的是
    `scoped_paths()`（`rglob("*")` ＋ `_in_scope()` ＋ 本函式），**不是** `Path.glob`。
    """
    d, _, n = rel_to_docs_dir.rpartition("/")
    pd, _, pn = pattern.rpartition("/")
    return d == pd and fnmatch.fnmatchcase(n, pn)


def _in_scope(rel_to_docs_dir: str) -> bool:
    """``rel_to_docs_dir`` 是相對 `DOCS_DIR` 的路徑；判斷它在不在受檢射程內。

    ⚠️ `iter_docs()`（測試端讀工作樹，經由 `scoped_paths()`）與 `docs_at_sha()`
    （baseline 產生端讀釘死的 commit，直接呼叫）**都走這一個函式**。
    兩邊各寫一套過濾是本輪差點踩到的坑：它們一旦不一致，
    就會出現**測試看得到、`--update-baseline` 產不出來**的違規 ——
    那一筆永遠登記不進 baseline，卡在紅燈而且沒有任何修法，
    只能靠改守衛繞過（＝把守衛改成擺設）。
    """
    return any(_matches_glob(rel_to_docs_dir, pattern) for pattern, _floor in DOCS_GLOBS)


# ══════════════════════════════════════════════════════════════════════════
# 刪除線遮罩（做法與上限沿用 `tests/test_constitution_file_refs.py`）
# ══════════════════════════════════════════════════════════════════════════
# 兩個上限刻意有限：若有人寫出單邊的刪除線符號，全域貪婪配對會讓它後面**所有**
# 句子一起被當成「已退役」而不再檢查 —— 該檢查的變成不檢查，而且是無聲的。
# 有上限的話，配不到伴的那一個會被當成普通文字，影響只留在原地。
_MAX_STRIKE_NEWLINES = 2
_MAX_STRIKE_CHARS = 1500
_STRIKE = "~" * 2
# HTML 的刪除線標籤 —— **2026-09-23 第十二輪新增**（客戶裁示：`~~` 改 `<s>`，屬修 bug）。
# ⚠️ `docs/v2/prototype/` 的線框整份是 HTML，**`~~` 在瀏覽器裡不會渲染成刪除線**
#    （實測：五個線框沒有任何 `line-through` CSS，也沒有把 `~~` 轉成標籤的 JS）⇒
#    退役句會在**客戶審過的畫面上**直接印出波浪號。改用 `<s>` 之後畫面才對得上。
# ⚠️ **母體講準**：這個理由適用的是本輪**新加**的 4 處（`alo`×2／`exp`×1／`today`×1，都在會渲染的
#    `<td>`／`<span>` 裡）；同輪一併轉換的另 3 處（`hld` 在 HTML 註解、`set`×2 在 JS 註解）
#    **從來沒進過畫面**，改它們的實益是一致性與本遮罩，不是渲染。
# ⚠️ **遮罩不認 `<s>` 的話，那些退役句會整批重新變成活句** —— 與本輪第 1 件同型：
#    遮罩不懂 HTML，正如行首判定原本不懂 HTML。
_STRIKE_TAGS = re.compile(r"<(s|del)\b[^>]*>(.*?)</\1>", re.S)


def strike_mask(text: str) -> bytearray:
    """回傳與 ``text`` 等長的遮罩，被刪除線（`~~` 或 `<s>`／`<del>`）包住的位置為 1。"""
    mask = bytearray(len(text))
    i = 0
    while True:
        open_at = text.find(_STRIKE, i)
        if open_at < 0:
            break
        limit = min(len(text), open_at + 2 + _MAX_STRIKE_CHARS)
        close_at = text.find(_STRIKE, open_at + 2, limit)
        if close_at < 0 or text.count("\n", open_at, close_at) > _MAX_STRIKE_NEWLINES:
            i = open_at + 2
            continue
        for k in range(open_at, close_at + 2):
            mask[k] = 1
        i = close_at + 2
    for m in _STRIKE_TAGS.finditer(text):      # 兩個上限與 `~~` 那一側完全相同，理由同上
        if (text.count("\n", m.start(), m.end()) > _MAX_STRIKE_NEWLINES
                or m.end() - m.start() > _MAX_STRIKE_CHARS):
            continue
        for k in range(m.start(), m.end()):
            mask[k] = 1
    return mask


# ══════════════════════════════════════════════════════════════════════════
# 句段切分 ＋ 正規化
# ══════════════════════════════════════════════════════════════════════════
# **`|` 只在 markdown 表格列上才是切點** —— 表格一格就是一個獨立斷言，不切開會讓
# 「這一格有指令、那一格有數字」黏成同一句而被誤判。
# ⚠️ 但在**非表格列**上，`|` 是 shell pipeline 或 regex 的交替符號。
#    早期版本一律切 `|`，於是 `git show <sha>:path | grep -c 'X' → 7 處` 會被切成兩半，
#    後半「grep -c 'X' → 7 處」**看不到前半的 SHA** ⇒ 一個釘好 SHA 的計數被誤報。
#    這是本檔的負控當場抓到的（見 `test_control_A_unpinned_count_fires_and_pinned_count_does_not`）。
# ⚠️ 表格列內的 `\|`（跳脫的豎線）同樣是 pipeline，不切 —— 本 repo 的文件大量這樣寫。
_SENTENCE_SPLIT = re.compile(r"[。！？!?；;]|<br\s*/?>")
_TABLE_SPLIT = re.compile(r"[。！？!?；;]|<br\s*/?>|(?<!\\)\|")

# 行首 HTML 標籤 —— **第十二輪新增**（客戶 2026-09-23 裁示第 1 件）。
# ⚠️ **在它之前，以 `<p>`／`<li>`／`<b>` 開頭的那一行，句首斷言一律偵測不到** ——
#    而 `docs/v2/prototype/` 的線框整份是 HTML，斷言幾乎都長在標籤後面
#    ⇒ (C) 對那一批檔形同空掃，**而且是全綠的空掃**。
# ⚠️ **刻意寫成通用形狀，不列白名單**：白名單漏掉一個標籤名，後果是**無聲漏抓**
#    （測試照樣全綠）；寫寬的後果只是**多紅一次**，而誤紅有人會來修。
#    極性與 `_is_word_boundary` 的選邊一致，理由同該處。
# ⚠️ **只可能多抓、不可能少抓**：三道檢查裡只有 (C) 吃正規化後的文字，
#    而那四個全稱詞是中日韓字元、本式咬不到它們 ⇒ 剝標籤只會**讓更多句首露出來**。
#    (A)／(B) 讀的是 `seg.live`（未正規化），完全不受本式影響。
# ⚠️ **`[^<>]` 而不是 `[^>]`**：後者會讓 `<b 大於 <code>x</code>` 這種文字被一口吃到
#    第一個 `>` 為止。限制在標籤內不得再出現 `<`，可以少吃掉一段真正的內文。
# ⛔ **`<!--` 不在本式射程內**（`!` 不是 `[A-Za-z]`），**但那不等於註解掉的句子逃得掉** ——
#    ASCII `!` 是 `_SENTENCE_SPLIT` 的切點，`<!-- 句子` 會在那裡被切開、`--` 當清單符號剝掉，
#    那句話照樣進 (C)。**改動前後同一個行為**，正控見
#    `test_control_C_a_commented_out_universal_is_still_checked`。
# ⚠️ **2026-09-23 第十三輪就地更正（有意識的更正，不是漏刪 · 決策者 客戶，裁示第 2 件）**：
#    本式原寫 ~~`r"</?[A-Za-z][^<>]*>"`~~，**第十二輪稽核登記過它咬不掉的五種形狀**，
#    其中兩種就長在這一式自己身上：`title="a>b"`（屬性值裡有 `>`，`[^<>]*` 提早收尾）
#    與 `title="a<b"`（屬性值裡有 `<`）。本輪改成**懂屬性**的文法（下方 `_TAG_*`）。
#    **舊表述的用意仍然成立** ——「限制在標籤內不得再出現 `<`，可以少吃掉一段真正的內文」
#    這個考量一字未變，新式用 `_TAG_ATTR` 把 `<` 擋在**未加引號的屬性值**外面，
#    只在**成對引號之內**才允許 `<`／`>`；**被權衡掉的是它的粗糙度**，不是它的極性。
#    負控 `test_control_C_a_bare_open_angle_is_not_treated_as_a_tag` 一字未改、仍然綠。
#
# **標籤文法（本檔唯一一份，行首剝除與 `_ends_a_block` 的行尾判定共用）**：
# ⚠️ **刻意共用** —— 兩處各寫一套的後果，本檔在 `_matches_glob` 已經記過一次：
#    它們一旦不一致，就會出現「剝得掉、卻判不出它是區塊收尾」這種**只有人讀得出來**的分家。
_TAG_NAME = r"[A-Za-z][A-Za-z0-9]*(?:[:\-][A-Za-z0-9]+)*"
# 一個屬性：名稱（不含空白／`=`／角括號／斜線／引號），可選的值 ——
# **成對引號內什麼都允許（含 `<` 與 `>`）**，未加引號的值則把角括號與引號擋在外面。
_TAG_ATTR = r'''[^\s=<>/"\']+(?:\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s"\'<>`]+))?'''
_LEADING_HTML_TAG = rf"</?{_TAG_NAME}(?:\s+{_TAG_ATTR})*\s*/?>"

# **跨行標籤的下半截**（第十二輪登記的第 4 種形狀）—— 一個開啟標籤被硬換行切開時，
# 下半行的開頭長成「`屬性="值" …>`」。它**不是**一個完整標籤，上面那一式咬不到。
# ⚠️ **刻意要求第一個屬性帶「成對引號的值」**，不是寫成 `^[^<>]*>`：
#    後者會把散文裡任何一個 `>` 之前的字整段吃掉（例：`x = 3 > 2`），
#    而**吃掉真正的內文會改變正規化結果 ⇒ 既有 baseline 的 key 當場全部漂掉**。
# ⚠️ **未涵蓋的形狀據實寫明**（`CLAUDE.md` §-1.5.1c 判定 2：明列未涵蓋範圍）：
#    第一個屬性**沒有加引號**（`class=foo>`）、或下半行以**裸屬性名**開頭（`disabled>`）
#    時本式不命中 —— 那是**漏抓**（少看），不是誤抓。收得更寬要先確認不會咬進內文。
_LEADING_TAG_TAIL = rf'''[^\s=<>/"\']+\s*=\s*(?:"[^"]*"|\'[^\']*\')(?:\s+{_TAG_ATTR})*\s*/?>'''

# 行首排版裝飾：空白／引用／標題／清單符號／序號／強調符號／emoji 與箭頭符號／開括號／HTML 標籤。
# ⚠️ 這一串**必須反覆剝到不動為止**（見 `normalize`）——「`- **所有**…`」要剝三層
#    （清單符號 → 空白 → 強調符號）才看得到第一個實字。只剝一次會讓句首斷言漏抓。
# ⚠️ **標籤那一項必須留在這個迴圈裡，不得改成收尾單獨補一刀** —— 那不是等價的寫法：
#    `<td>「…` 這種「標籤 ＋ 開引號」要兩者**交替**剝才看得到第一個實字，
#    收尾補一刀的版本剝完標籤就停住 ⇒ 那一類整批漏掉（本輪實測兩種寫法差兩句）。
# ⚠️ **拆成 parts 是為了讓突變測試能精準拿掉其中一項**（見
#    `test_mutation_removing_the_leading_tag_rule_turns_the_control_red`）——
#    不拆的話那條突變只能把整串 regex 重打一次，重打的那一份會與本體無聲分家。
# **半形雙引號與全形冒號**（第十二輪登記的第 1 與第 5 種形狀）——
# ⚠️ **刻意獨立成一項、不塞進上面那個字元類**：塞進去的話突變測試只能把整個字元類
#    重打一次，重打的那一份會與本體**無聲分家**（理由同 `_LEADING_FURNITURE_PARTS`
#    自己那句「拆成 parts 是為了讓突變測試能精準拿掉其中一項」）。
# ⚠️ **只收這兩個字元，不順手擴大**：全形引號 `「『【（` 上面已經收了；
#    半形**單**引號 `\'` **刻意不收** —— 它在英文裡是所有格與縮寫符號，
#    收進來會在行首以外的判讀上多出一種說不清的形狀，而第十二輪登記的是雙引號。
#    ASCII 冒號 `:` 同樣不收（登記的是全形冒號）。**少收 ＝ 漏抓 ＝ 少看**，
#    不是誤抓；要收更多請先量測再改，不要順手加。
_LEADING_QUOTE_OR_COLON = r'["\uff1a]'

_LEADING_FURNITURE_PARTS: tuple[str, ...] = (
    r"[\s\u3000\u00a0>#*+\-_`~]",
    # ⚠️ **2026-09-23 第十三輪回修（G6；決策者 客戶）**：本式原寫 `r"\d+[.)]"`，
    #    **沒有要求後面接空白**，於是它會吃進一個**數字的中間**。
    #    **實證（稽核提供，本組已自行重現）**：本輪新加的 `_LEADING_QUOTE_OR_COLON` 把開頭的
    #    半形雙引號剝掉之後，`"31.0" : …` 曝出 `31.`，**被本式當成清單序號吃掉**，
    #    正規化結果變成 `0" : …` —— **一個實質字元被吃掉了**。
    #    HEAD 上不會發生，因為那時雙引號擋在前面：**是本輪兩項新舊規則的交互作用造出來的。**
    #    ⛔ 這剛好命中 `_LEADING_TAG_TAIL` 自己寫的警語（「吃掉真正的內文會改變正規化結果
    #    ⇒ 既有 baseline 的 key 當場全部漂掉」）—— **本組替 `_LEADING_TAG_TAIL` 想到了，
    #    沒替 `_LEADING_QUOTE_OR_COLON` 想到**，而兩者是同一輪加的。
    #    **修法**：序號後面必須是空白或字串結尾，與 `_MD_BLOCK_START` 的 `\d+[.)][\s　]` 同口徑。
    #    **代價**：`1.項目`（序號後不空格）自此不剝 —— 那是**少剝**，方向安全。
    #    正控 `test_control_normalize_never_eats_into_a_number`＋突變就守在這一條上。
    r"\d+[.)](?=[\s　 ]|$)",
    r"[(（]\d+[)）]",
    r"[\u2190-\u2BFF\uFE0F\u2000-\u206F\U0001F000-\U0001FAFF]",
    r"[「『【（(\[]",
    _LEADING_QUOTE_OR_COLON,
    _LEADING_HTML_TAG,
    _LEADING_TAG_TAIL,
)


def _furniture_re(parts: tuple[str, ...]) -> "re.Pattern[str]":
    """把 parts 組成「行首、反覆」的剝除式 —— 本體與突變測試**共用同一個組裝器**。"""
    return re.compile("^(?:" + "|".join(parts) + ")+")


_LEADING_FURNITURE = _furniture_re(_LEADING_FURNITURE_PARTS)

_EMPHASIS = re.compile(r"\*\*|__|" + _STRIKE + r"|`")
_WHITESPACE = re.compile(r"[\s\u3000\u00a0]+")


def normalize(segment: str) -> str:
    """把一個句段正規化成 baseline 的 key 素材。

    規則（與模組 docstring 的「正規化規則」逐條對應，**改這裡等於讓整份 baseline 失效**）：

    1. 反覆剝掉行首排版裝飾（清單符號／引用／序號／強調／emoji／開括號／**HTML 標籤**），
       剝到不動為止。
    2. 去掉所有 markdown 強調符號與反引號。
    3. 連續空白（含全形與不斷行空白）一律壓成一個半形空格。
    4. 去頭尾空白。

    其餘一個字都不動 —— 不轉全半形、不去標點、不小寫化。
    中文文件裡全半形與標點本身就帶語意，動了會讓兩句不同的話撞同一個 key，
    那會讓一筆 baseline 意外蓋住另一句它沒看過的話。

    ⚠️ **2026-09-23 第十三輪：剝除改成整條管線的不動點（fixpoint），不是「末尾補一刀」**
    （**有意識的更正，不是漏刪** · 決策者 **客戶**，裁示第 2 件）。
    ~~舊寫法是「行首裝飾剝到不動為止 → **然後**把強調符號剝一次」~~ ——
    **舊表述的用意仍然成立**（行首那一圈本來就該剝到不動，這一點一字未變）；
    **被權衡掉的是它把強調符號那一刀留在迴圈外面**：強調符號一旦被剝掉，
    有可能**曝出新的行首裝飾**，而收尾那一刀已經跑完了 ⇒ 那一類整批漏掉。
    第十二輪就是因為「一次性剝」漏掉兩句（該輪自己的續記寫著「兩種寫法差 2 句」）。
    現在兩者同在一個迴圈裡**交替跑到整體不動為止**，
    由 `test_control_normalize_is_a_fixpoint_over_the_corpus` 逐句釘住。

    ⛔ **2026-09-23 第十三輪回修：上面那一段把外層 `while` 的功勞講得比實際大，就地更正**
    （**有意識的更正，不是漏刪** · 決策者 **客戶** · 依據 **G11 稽核，本組已自行重現**）。
    **實測（本組重跑，母體 `docs/v2/` 全部 58,143 個句段）**：把 `normalize` 換成
    (a) 現行寫法、(b) **第十二輪寫法**（行首剝到不動 → 強調剝一次）、(c) 兩者各跑一次 ——
    **三者的輸出差異全部是 0**。本組另外拿 4×7 組合成樣本去找反例，**也找不到**。
    **原因**：`_LEADING_FURNITURE` 本身是 `^(?:…)+`，**單次 `sub` 裡就已經反覆剝**；
    而 `_EMPHASIS` 的四個標記（`**` `__` 反引號 `~~`）**每一個字元也都在行首字元類裡**
    ⇒ 強調符號**不可能**曝出新的「行首」裝飾。**外層那個 `while` 在今天是死的。**
    ✅ **仍然保留它，理由只有一個（而且是弱理由，據實寫明）**：日後若有人在 `_EMPHASIS`
    加進一個**不在行首字元類裡**的標記，它就會重新活過來；拿掉它則會讓那一天無聲漏抓。
    ⛔ **不得再宣稱「本輪靠這個迴圈救回了什麼」** —— 真正在做事的是
    `_LEADING_FURNITURE` 的 `+`（各 part 之間的交替），那一條有真正控，見
    `test_control_normalize_alternates_between_furniture_parts`。
    """
    prev = None
    s = segment
    while prev != s:
        prev = s
        s = _LEADING_FURNITURE.sub("", s)
        s = _EMPHASIS.sub("", s)
    s = _WHITESPACE.sub(" ", s)
    return s.strip()


class Segment:
    """一個句段。

    * ``raw``  —— 原文（含被劃掉的部分）。
    * ``live`` —— **把被刪除線劃掉的字元拿掉之後**剩下的文字。三道檢查一律看這個。
    * ``text`` —— ``live`` 正規化後的結果，同時是 baseline key 的素材與錯誤訊息的顯示字串。
    * ``struck`` —— 整段都被劃掉（``live`` 是空的）。
    * ``initial`` —— **這一段是不是一句話的開頭**（第十三輪新增，見 `_is_continuation`）。
      行內第二段以後恆為真（它前面就是一個切點）；每一行的**第一段**才要判。
      ⚠️ **只有 (C) 讀它**；(A)／(B) 讀 `seg.live`，一個字都沒動。
      ⚠️ **預設值刻意是 `True`（＝當成句首）** —— 與 `_is_continuation` 同一個極性：
      判成續行的後果是 (C) 不看它（**無聲漏抓**），判成句首的後果只是多紅一次。

    ⚠️ **為什麼是「拿掉劃掉的字」而不是「整段被劃掉才跳過」**：本 repo 最常見的退役寫法是
    `~~舊句~~ → 2026-09-21 更正，見 <sha>` —— **同一段裡一半死一半活**。
    用「整段」判，這種句子會被當成活的，而它正規化之後還是以那個全稱詞開頭 ⇒ 誤報。
    改看活文字之後，開頭那個詞已經隨刪除線一起消失，句子自然不再是句首斷言。
    做法與 `tests/test_constitution_file_refs.py` 同向（該檔判的是**每一個引用自己**的位置
    有沒有被劃掉，不是整行）。
    """

    __slots__ = ("line", "raw", "live", "text", "struck", "initial")

    def __init__(self, line: int, raw: str, live: str, initial: bool = True):
        self.line = line
        self.raw = raw
        self.live = live
        self.text = normalize(live)
        self.struck = not live.strip()
        self.initial = initial


# ══════════════════════════════════════════════════════════════════════════
# 續行判定 —— 這一行的第一個句段，是不是上一行那句話的下半截？
# ══════════════════════════════════════════════════════════════════════════
# **第十三輪新增**（客戶 2026-09-23 裁示第 1 件；第十二輪已把它登記為模組 docstring 的
# 「缺口 5」）。在它之前 `split_segments` 是**純逐行**切段，於是一句被硬換行斷開的話，
# **下半行的第一個詞就被當成句首** —— 而 `docs/v2/prototype/` 的線框整份是手寫 HTML、
# 整份都在硬換行，(C) 因此把句子中段的副詞讀成全稱斷言。
# **本輪之前的實證，就是 baseline 裡那幾筆帶「硬換行假句首」`why_safe` 的登記。**
#
# **判準（三條，依序；任一成立 ⇒ 它**不是**續行 ⇒ 照常當句首）**
#   1. **前面沒有東西承接** —— 這是全檔第一個非空行，或上一行是空白行（段落界）。
#   2. **這一行自己開啟了一個新區塊**（`_starts_a_new_block`）。
#   3. **上一行已經把句子或區塊收掉**（`_ends_a_block`）。
# 三條都不成立 ⇒ 續行 ⇒ (C) 不把它當句首。
#
# ⚠️ **極性寫死，與 `_is_word_boundary` 同向 —— 這一段比規則本身重要**：
#    判成**續行**的後果是 (C) **不看它** ＝ **無聲漏抓**（三道檢查照樣全綠，沒有人會發現）；
#    判成**句首**的後果只是**多紅一次**，而誤紅有人會來修。
#    所以兩個述詞都刻意往「當成句首」那一邊倒：**只在三條都不成立時才敢判續行。**
# ⚠️ **`_INLINE_TAGS` 是一張「行內標籤」白名單，它的極性是這樣安排的**：
#    漏收一個行內標籤名 ⇒ 它被當成**區塊** ⇒ 判成句首 ⇒ **多紅**（吵，但看得見）；
#    收錯一個（把區塊標籤寫進來）⇒ 判成續行 ⇒ **無聲漏抓**。
#    **只准往「漏收」那邊錯**，正控見 `test_control_unknown_tag_at_line_start_is_a_block`。
# ⚠️ **`<br>` 刻意不在行內表裡** —— 它是換行，`<br>` 收尾就是把那一句收掉了
#    （它本來就是 `_SENTENCE_SPLIT` 的切點之一，兩處口徑必須一致）。
# ⚠️ **本判定只在 (C) 被讀**（`Segment.initial`）。(A)／(B) 讀的是 `seg.live`，
#    完全不受影響；而 (C) 這一側**設計上只可能少抓、不可能多抓** ——
#    那個方向由 `test_control_continuation_rule_can_only_remove_findings` 逐筆釘住。
_INLINE_TAGS = frozenset((
    "a abbr b bdi bdo big cite code data del dfn em font i ins kbd mark q rp rt "
    "ruby s samp small span strike strong sub sup time tt u var wbr"
).split())

# 行首縮排（**刻意不用 `str.strip()` 的預設集合**：那會連 `\n` 一起吃，而這裡拿到的是單行）
_INDENT = " \t　 "

# 這一行自己就是一個新區塊的開頭：markdown 的標題／引用／表格列／清單／有序清單／圍籬。
# ⚠️ `>` 也收在這裡 —— 在 markdown 它是引用，在硬換行的 HTML 它是**跨行標籤的下半截**。
#    兩種讀法都指向「這裡是一個新的東西」，而且**兩種讀法都往多紅那一邊倒**。
# ⚠️ **2026-09-23 第十三輪回修（G2；決策者 客戶）**：本式原本**只認 markdown 的五種**，
#    而 `normalize` 的行首裝飾表比它**多 17 類**。兩張表不一致的後果是單向的：
#    `normalize` 把裝飾剝掉好讓句首露出來，本式卻不認得那一行是新區塊 ⇒ **整句被判續行吞掉**。
# ✅ **本輪補上的只有「本語料真的拿來當項目符號用」的兩類**（逐一實測過）：
#    `(1)`／`（1）` 這種帶括號的編號，以及 ⚠ ⛔ ✅ ❌ 📌 ⭐ → ⇒ ↳ ✓ ✗ ▸ ▾ ◧ 這些符號項目符號。
# ⛔ **刻意不補的，逐一寫明理由（這一段比補了什麼重要）**：
#    * 強調符號（`**` `__` 反引號 `~~`）、開括號（`「『【（(` `[`）、半形雙引號、全形冒號 ——
#      它們在中文散文裡**本來就會出現在句子中段**，一行以它們開頭**多半真的是續行**；
#      當成區塊開頭會把**真續行**判成句首 ⇒ 誤紅。
#      （稽核量過反向做法：讓本式吃整張 `_LEADING_FURNITURE`，**6 筆真續行全部變誤紅**。）
#    * **行內標籤**（`<b>`／`<code>`…）—— 已由 `_INLINE_TAGS` 在 `_starts_a_new_block` 裡分流，
#      區塊標籤照舊判區塊；補進本式等於連行內標籤也當區塊開頭，同上。
#    * **破折號與刪節號**（`—` `–` `…`，即 `\u2000-\u206F` 那一段）——
#      **本語料實測：`docs/v2/*.md` 行首以 `——`／`…` 開頭的共 50 行，全部是續行的接續號**
#      （量測日 2026-09-23）。補它就是 50 行誤紅。
# ⚠️ **沒補的那幾類不是放掉，是改由 `_ends_a_block` 救**：上一行真的收了句
#    （本輪已把收句字表由 6 個字元補到 13 個），它們就會被當成句首；
#    上一行沒收句才判續行 —— **那正是「續行」該有的定義。**
# ⚠️ **本輪這兩類對現行語料的命中是 0**（實測：加與不加，(C) 都是 68、新增都是 0）——
#    **它是預防性的，語料證不了它**；唯一的證據是 `_CONT_BLOCK_STARTS` 那組正控與它的突變。
_MD_BLOCK_START = re.compile(
    r"(?:[#>|]"
    r"|[-*+][\s　]"
    r"|\d+[.)][\s　]"
    r"|[(（]\d+[)）]"
    r"|[\u26A0\u26D4\u2705\u274C\U0001F4CC\u2B50\u2192\u21D2\u21B3\u2713\u2717\u25B8\u25BE\u25E7]"
    r"|```|~~~"
    r")")

_HTML_TAG_HEAD = re.compile(rf"</?({_TAG_NAME})")
# 行**尾**的標籤 —— 與行首剝除共用同一份標籤文法（`_TAG_NAME` / `_TAG_ATTR`），
# 所以 `title="a>b"` 這種屬性值含角括號的標籤在兩處讀法一致。
_HTML_TAG_AT_END = re.compile(rf"<(/?)({_TAG_NAME})(?:\s+{_TAG_ATTR})*\s*/?>$")

# **自成一行的結構行** —— 標題／引用／表格列／圍籬／水平線。
# ⚠️ 它們**兩邊都是界**：`_starts_a_new_block` 認它們是開頭，本式認它們是結尾。
#    少了這一式，`` ``` `` 圍籬的下一行、以及標題的下一行會被判成續行 ⇒ **無聲漏抓**。
#    **這不是想出來的，是本輪實測抓到的**：第一版少了它，
#    `20_ui_spec` 與 `21_decision_log` 兩份的「裁示編號」句（前一行是圍籬）
#    以及 `01_wireframe_grp` 的「不進畫面」句（前一行是標題型的粗體宣告）被一起吃掉。
# ⚠️ **清單符號與 HTML 標籤刻意不收進本式**：markdown 的清單項**本來就允許
#    懶惰續行**（下一行不縮排也算同一項），HTML 的區塊標籤則由 `_HTML_TAG_AT_END`
#    按「開／收」分別判 —— 把它們一起塞進來會把真正的續行判成句首，那是**誤紅**方向，
#    雖然安全但會把本輪的修復抵消掉。
_SELF_CONTAINED_LINE = re.compile(r"(?:[#>|]|```|~~~|-{3,}\s*$|={3,}\s*$)")

# 句末標點。
# ⚠️ **2026-09-23 第十三輪回修就地更正（有意識的更正，不是漏刪 · 決策者 客戶 · 依據 G1 稽核）**：
#    本行原寫 ~~「**與 `_SENTENCE_SPLIT` 的字元集刻意逐字相同**」，字表只有 `。！？!?；;` 六個~~。
#    **舊表述的用意仍然成立**（兩處口徑一致，讀起來簡單）；**被權衡掉的是它的極性** ——
#    這是一張**白名單**，白名單外的一切收尾一律回「話沒講完」＝ 判續行 ＝ **(C) 不看它 ＝ 無聲漏抓**。
#    **稽核實測**：全語料 **33,067 個非空行**裡有 **10,451 行（31.6%）** 收在白名單之外，
#    其中 `）`714 行、`」`217 行、`)`210 行、`]`61 行、`"`88 行 ——
#    **這些在中文書寫裡都是已經收句的形狀**；造 30 個樣本實測，**13 個位置無聲漏抓**。
# ⚠️ **本檔的極性宣告當時與實作不符，就地寫明**：區塊註解寫「兩個述詞都刻意往『當成句首』那一邊倒」——
#    **描述結構的那句是對的，但兩個述詞自己的預設答案都倒向不安全那一邊**
#    （`_ends_a_block` 預設「沒收句」、`_starts_a_new_block` 預設「不是區塊」）。
#    **宣告的是「寧可多紅」，實作出來的是「寧可不看」。** 本輪把 `_ends_a_block` 這一側補齊。
# ⛔ **`_SENTENCE_SPLIT` 一個字都沒動，兩處自此刻意不同** —— 動它會改變**切段**，
#    讓三位數的 baseline key 整批漂掉；本字表只影響「上一行算不算把話講完」。
# ⚠️ **代價據實寫明，不是零成本**：`）` 在中文裡**同時**是「收句」與「句中插入語結尾」，
#    **單一字元判不出來，這是真張力，不是誰寫錯**。補了它，三筆**真續行**會變成誤紅
#    （`03_adjudication`／`23_ui_draft_01_macro`／`ui_prototype_today`）——
#    那三筆進 baseline、逐筆寫明這個張力。**誤紅是安全方向，正是本檔宣告的極性。**
# ⚠️ **那三筆原本「不被抓」靠的是巧合** —— `）` 剛好不在字表裡；**結論對、機制是巧合**。
#    把巧合換成明確的登記，是升級不是降級。
_SENTENCE_END_CHARS = "。！？!?；;」』）)】.…》"
# **子句末標點**：冒號。它引入的是一段**新的陳述**，不是上一句的下半截。
# ⚠️ **只用在本判定，刻意不加進 `_SENTENCE_SPLIT`** —— 加進去會改變切段、
#    讓既有 baseline 的 key 整批漂掉（那是三位數的欠債登記簿）。
# ⚠️ **與 `_LEADING_QUOTE_OR_COLON` 口徑一致**：本檔已經把**行首**的全形冒號當裝飾剝掉，
#    那就等於承認冒號不屬於後面那句斷言；**行尾**沒有理由反過來把它讀成「句子還沒完」。
#    實證：`38_audit_spec_r6` 的「全部 0 命中」句，前一行正是以冒號收尾的檔名清單。
_CLAUSE_END_CHARS = "：:"
# 行尾的 markdown 強調符號 —— `…的。**` 這種寫法會讓句號不在最後一個字元上。
# **這也是實測抓到的**（`01_wireframe_grp` 那一句），不是預防性的。
_TRAILING_MARKUP = "*_`~"


def _starts_a_new_block(line: str) -> bool:
    """``line``（**未正規化的整行原文**）自己是不是一個新區塊的開頭。"""
    body = line.lstrip(_INDENT)
    if not body:
        return True
    if _MD_BLOCK_START.match(body):
        return True
    m = _HTML_TAG_HEAD.match(body)
    if m:
        return m.group(1).lower() not in _INLINE_TAGS
    return False


def _ends_a_block(line_raw: str, line_live: str) -> bool:
    """上一行有沒有把句子或區塊收掉（收掉 ⇒ 下一行是新的句首）。

    ⚠️ **終止符的判讀吃 `live`（刪除線已拿掉）而不是 `raw`**：若上一行的句號本身
    被劃掉，在**活文字**的讀法裡那句話就沒有結束 —— 與三道檢查一律看 `live` 的口徑一致。
    ⚠️ **結構行的判讀吃 `raw`**：`` ``` `` 圍籬與 `#` 標題是**排版**事實，與退役無關。
    ⚠️ **整行都被劃掉時回 `True`**（＝不承接）：那一行已經退役，
    讓它去承接下一行，等於讓一筆退役紀錄**無聲地**關掉下一句的檢查。
    """
    if _SELF_CONTAINED_LINE.match(line_raw.lstrip(_INDENT)):
        return True
    tail = line_live
    while True:                     # 把行尾的強調符號與**行內**收尾標籤剝到不動為止
        shorter = tail.rstrip(_INDENT + _TRAILING_MARKUP)
        m = _HTML_TAG_AT_END.search(shorter)
        if m and m.group(1) == "/" and m.group(2).lower() in _INLINE_TAGS:
            shorter = shorter[:m.start()]
        if shorter == tail:
            break
        tail = shorter
    if not tail:
        return True
    if tail[-1] in _SENTENCE_END_CHARS or tail[-1] in _CLAUSE_END_CHARS:
        return True
    m = _HTML_TAG_AT_END.search(tail)
    return bool(m) and m.group(2).lower() not in _INLINE_TAGS


def _is_continuation(prev_line: tuple[str, str] | None, line: str) -> bool:
    """``line`` 的第一個句段，是不是上一行那句話的下半截？

    ``prev_line`` ＝ 上一個「原文非空白」的行的 ``(原文, 活文字)``；
    ``None`` ＝ 前面是檔首或空白行。
    **判準三條與極性寫在本節開頭的區塊註解裡，改這裡請連同那一段一起讀。**
    """
    if prev_line is None:
        return False
    if _starts_a_new_block(line):
        return False
    if _ends_a_block(*prev_line):
        return False
    return True


def split_segments(doc: str) -> list[Segment]:
    """把整份文件切成句段（逐行處理，表格列才切 `|`）。

    每一段另帶 `initial`（**是不是一句話的開頭**）：
    行內第二段以後恆為真（它前面就是一個切點 ＝ 句末標點／`<br>`／表格的 `|`）；
    每一行的**第一段**交給 `_is_continuation` 判。
    ⚠️ **空白行會把承接關係切斷**（`prev_line_live = None`），那就是段落界。
    ⚠️ **切出來的段、段的文字、以及 (A)／(B) 的行為一字未變** ——
    本輪只是替每一段多掛一個旗標，這一點由
    `test_control_continuation_rule_can_only_remove_findings` 釘住。
    """
    mask = strike_mask(doc)
    out: list[Segment] = []
    pos = 0
    prev_line: tuple[str, str] | None = None
    for lineno, line in enumerate(doc.split("\n"), start=1):
        start = pos
        pos += len(line) + 1
        if not line.strip():
            prev_line = None               # 空白行 ＝ 段落界，下一行重新算句首
            continue
        head_initial = not _is_continuation(prev_line, line)
        splitter = _TABLE_SPLIT if line.lstrip().startswith("|") else _SENTENCE_SPLIT
        spans, last = [], 0
        for m in splitter.finditer(line):
            spans.append((last, m.start()))
            last = m.end()
        spans.append((last, len(line)))
        for a, b in spans:
            raw = line[a:b]
            if not raw.strip():
                continue
            live = "".join(ch for i, ch in enumerate(raw, start=start + a) if not mask[i])
            out.append(Segment(lineno, raw, live, head_initial if a == 0 else True))
        prev_line = (line, "".join(
            ch for i, ch in enumerate(line, start=start) if not mask[i]))
    return out


# ══════════════════════════════════════════════════════════════════════════
# 三種 token
# ══════════════════════════════════════════════════════════════════════════
# 「掃描指令」—— 會產生一個數字的東西。刻意寧可多抓不可漏抓（同 `CLAUDE.md`
# §-1.5.1c 判定 2 的驗證指令慣例：**會多抓是設計，不是瑕疵**）。
_SCAN_CMD = re.compile(
    r"(?:"
    r"git\s+(?:grep|show|diff|ls-files|ls-tree|log|cat-file|rev-list)"
    r"|(?<![\w-])grep(?![\w-])"
    r"|(?<![\w-])rg(?![\w-])"
    r"|(?<![\w-])wc\s+-[lcmw]"
    r"|(?<![\w-])awk(?![\w-])"
    r"|(?<![\w-])sed\s+-n"
    r"|(?<![\w-])cmp(?![\w-])"
    r"|(?<![\w-])find\s+\S"
    r"|(?<![\w-])head\s+-\d"
    r"|(?<![\w-])tail\s+-"
    r"|(?<![\w-])diff\s+<?\("
    r")"
)

# 「數字＋量詞」—— 一個計數的結果長什麼樣。
# ⚠️ 三個 lookbehind 是用來擋掉**序數**（「第 1 條」「第 3 項」）—— 那是在**指涉**
#    某一條，不是在**數**東西。不擋的話，「違反同一批裁示的第 1 條」會被當成一句計數，
#    然後要求它釘 SHA —— 一個顯然荒謬的紅燈，會讓人學會忽略這支守衛。
#    （`0d9753f` 的工作樹上實測到 1 筆這種誤報，就是這樣被抓出來並修掉的。）
_COUNT_TOKEN = re.compile(
    r"(?:"
    r"(?<!第)(?<!第 )(?<!第\u3000)"
    r"\d{1,7}\s*[*`~_]{0,2}\s*(?:處|行|檔|筆|個|次|組|列|句|條|項|欄|命中|字元|字)"
    r"|命中\s*[*`~_]{0,2}\s*\d{1,7}"
    r")"
)

# commit SHA：7–40 位十六進位。
#
# ⚠️ **這裡原本多一條「至少含一個 a–f」的條件，已經拿掉 —— 負控當場證明它是錯的。**
# 當初加那條，是想擋掉「一串純數字剛好 7 位」被誤當成 SHA。
# 但本檔的負控用了 `4851465` 當釘樁（它是 `CLAUDE.md` §-2.A 實際引用的 commit），
# 而 **`4851465` 整串都是數字** —— 實測 `git cat-file -t 4851465` → `commit`。
# 也就是說那條件會把一個**真的釘好 SHA 的計數判成沒釘**，
# 而誤紅比漏抓更傷：它教人「這支守衛會亂叫」，然後所有人開始無視它。
#
# 換上的替代防線是下面那個 negative lookahead：一串十六進位數字若**緊接著量詞**
# （「1234567 筆」），那是計數不是 SHA，不算釘。
_SHA = re.compile(
    r"(?<![0-9a-zA-Z])"
    r"(?=[0-9a-f]{7,40}(?![0-9a-zA-Z]))"
    r"[0-9a-f]{7,40}"
    r"(?!\s*[*`~_]{0,2}\s*(?:處|行|檔|筆|個|次|組|列|句|條|項|欄|命中|字))"
)

# 會移動的 ref —— 客戶裁示第 1 條點名禁止的三種寫法。命中它們只是**加註診斷**，
# 判定仍然一律看「有沒有 SHA」：一句話可以同時寫 `origin/main` 與一個 SHA，
# 那樣是合規的（例：`git show <sha>:path`，而散文裡順帶提到主線）。
_MOVING_REF = re.compile(r"origin/main|(?<![\w])HEAD(?![\w])|工作樹")

# 反向檢查的「輸出」長什麼樣。
_OUTPUT_MARKER = re.compile(r"exit\s*=|→|⇒|無輸出|0\s*命中|回\s*非?\s*0|not found|No such")

# 句首全稱詞 —— 本字表是它們在本檔的**定義處**。
# ⚠️ **2026-09-23 第十一輪就地更正（有意識的更正，不是漏刪 · 決策者 AI 總管，
#    依客戶第十一輪裁示第 1 件）**：本行原寫 ~~「這是本檔**唯一**寫出這四個字面的地方
#    —— 其餘各處一律以『那四個詞』指稱」~~，**那句話在它被寫下的那一輪就已經不成立**：
#    本檔另有**數十行**逐字寫著它們之一（模組 docstring 的規則說明、錯誤訊息、
#    以及正控／負控的受測字串本身）。第十輪已在 `_head_ending_with` 的 docstring
#    修掉同一句話的副本，**漏了這一處**，於是同一檔內兩處說法不一致 —— 本輪補齊，
#    **口徑與該處對齊**。⛔ **不得據此宣稱「其餘各處都沒有寫出那四個字面」。**
# **舊表述的用意仍然成立**（少寫一處字面就少一處要同步的東西，理由同 `CLAUDE.md`
#    §-2.A 第 8 款：受測字串寫進文件就會被自己掃到）；**被權衡掉的是它的全稱強度** ——
#    它把一個「該往哪個方向走」寫成了「現況已經如此」。本字表做的只是**不再多添一處**，
#    **不是**把既有的那些收乾淨。
# ⛔ **刻意不寫「有幾處」**：這一段自己就會提到那些詞，寫下數字存檔當刻就過期
#    （同 `CLAUDE.md` §-2.A 第 8 款：把掃描用的字串寫進文件，它就會自己命中）。
_UNIVERSAL_HEADS = ("每一個", "所有", "全部", "都")

# 句首斷言的最短長度：去掉開頭那個詞之後，還要剩至少這麼多字才算一句斷言。
# 擋掉的是表格裡只填兩個字當欄位值的格子 —— 那是**值**，不是斷言。
_MIN_ASSERTION_TAIL = 2

# ── 字表的例外：字面以全稱詞開頭、但整串其實是**另一個詞** ──────────────
# 客戶 2026-09-23 裁示（第十輪第三件）：(C) 把一個文法術語誤判成全稱詞 → **改字表**。
#
# **事發（第九輪實測）**：凍結組在 §7.2 寫紀錄時，一個句段以**文法術語**開頭
# （英文 possessive case 的中譯，是一個名詞），它的前兩個字剛好就是上面字表裡的一個詞，
# 於是 (C) 把它讀成句首全稱斷言 ⇒ **CI 誤紅**。
# 凍結組當時是**改寫措辭繞開**的 —— 守衛沒動、baseline 沒動，
# 也就是說**下一個人寫到同一個詞還會再紅一次**。本表把那一刀補在守衛上。
#
# ⚠️ **這是修誤報，不是放寬規則。** 真正的危險是那個複合詞的**字面會被更長的詞吃回去**：
#    同樣那幾個字再接一個名詞字，就變回「全稱詞 ＋ 一個名詞」＝ **一句真的全稱斷言**
#    （本檔的正控就是拿這種句子在守）。所以「命中複合詞」**還不夠**，
#    後面必須真的碰到**詞尾邊界**才放過 —— 見 `_is_word_boundary`。
def _head_ending_with(tail: str) -> str:
    """從 `_UNIVERSAL_HEADS` 取出以 ``tail`` 結尾的那一個詞。

    ⚠️ **刻意用「取」而不是「重打一次」** —— 本檔少一處要同步的字面
    （理由同 `CLAUDE.md` §-2.A 第 8 款：受測字串寫進文件就會被自己掃到）。
    ⛔ **不得據此宣稱「其餘各處都沒有寫出那四個字面」** —— 那句話不成立：
    本檔另有**數十行**逐字寫著它們之一（模組 docstring 的規則說明、錯誤訊息、
    以及本輪新增的受測字串本身）。本函式做的只是**不再多添一處**，
    **不是**把既有的那些收乾淨。
    ⚠️ **也刻意不用索引**：有人重排 `_UNIVERSAL_HEADS` 時，索引會**靜默**指到別的詞，
    本表就變成一張永遠不命中的死表，**而三道檢查照樣全綠**。
    這個寫法在那種情況下當場炸掉（`CLAUDE.md` §1 Fail Loud）。
    """
    hits = [h for h in _UNIVERSAL_HEADS if h.endswith(tail)]
    if len(hits) != 1:
        raise RuntimeError(
            f"`_UNIVERSAL_HEADS` 裡以 {tail!r} 結尾的詞有 {len(hits)} 個，預期剛好 1 個 —— "
            "字表被改動過，請同步檢查 `_LOOKALIKE_COMPOUNDS`。")
    return hits[0]


# ⚠️ **只收「有實證誤紅」的詞。** 想像得到、但沒有真的紅過的複合詞一律不收 ——
#    每收一筆就多放掉一種形狀，而**沒有任何機器驗得出**收進來的是不是真的名詞。
_LOOKALIKE_COMPOUNDS: tuple[str, ...] = (
    _head_ending_with("有") + "格",
)

# 詞尾邊界：複合詞後面接到什麼，才算它真的是一個**獨立的名詞**。
_CJK = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]")


def _is_word_boundary(text: str, pos: int) -> bool:
    """``text`` 在 ``pos`` 這個位置是不是一個詞的結尾（或已到句段尾）。

    **判定只有一條**：後面沒有字了，或下一個字**不是中日韓文字**。
    標點、空白、拉丁字母、數字都算邊界；後面接著一個中日韓文字 ⇒ **不算邊界**，照抓。

    ⚠️ **這個條件是封閉的，而且必須維持封閉 —— 這段比規則本身重要**：
    它是 `_CJK` 的補集，**不是**一張「還可以再往裡加幾個字」的清單。
    任何「某些中日韓文字也算邊界」的放寬都會把它變成一張**開放的放過清單**：
    每加一個字就多放掉一種形狀，而它放掉的是**沒有人會發現**的漏抓 ——
    三道檢查照樣全綠，沒有任何一條測試會紅。本函式選的是另一邊：
    判錯的後果只是**多紅一次**，而誤紅有人會來修。

    ⚠️ **代價據實寫明，不要誤以為本判定分得出詞性**：中文不寫空格，
    「複合詞 ＋ 中日韓文字」與「全稱詞 ＋ 一個名詞」在**字面上完全一樣**，
    沒有任何詞表分得出來。本判定把這一類**一律判成斷言** ⇒
    `_LOOKALIKE_COMPOUNDS` 的那個詞**後面直接接中文時仍然會紅**。
    那是**刻意付的成本，不是漏掉** —— 正控見
    `test_control_C_lookalike_followed_by_cjk_still_fires`。
    """
    if pos >= len(text):
        return True
    return not _CJK.match(text[pos])


# (C) 的反向檢查視窗：從該句段所在行起算，往下看幾行。
# 取 8 行的理由：`docs/v2/41_counters.md` §41.3 的既有體例是
# 「全稱句一行 ＋ 反向檢查標題一行 ＋ 圍籬 3–5 行」，8 行放得下一整組，
# 又不會跨到下一個條目去撿別人的指令當自己的證據。
_REVERSE_CHECK_WINDOW = 8


class Finding:
    """一筆違規：哪個檔、哪一行、正規化後的句子、以及附註。"""

    __slots__ = ("doc", "line", "text", "note")

    def __init__(self, doc: str, line: int, text: str, note: str = ""):
        self.doc = doc
        self.line = line
        self.text = text
        self.note = note

    @property
    def key(self) -> str:
        """baseline key —— **不含行號**（行號每一輪都在漂，那正是本守衛要治的病）。"""
        raw = f"{self.doc}\0{self.text}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:16]

    def render(self) -> str:
        body = self.text if len(self.text) <= 160 else self.text[:157] + "…"
        note = f"\n\t\t└ {self.note}" if self.note else ""
        return f"  {self.doc}:{self.line}\t[{self.key}]\n\t\t{body}{note}"


def _own_name_tokens(doc_rel: str) -> tuple[str, str]:
    """回 (repo 相對路徑, 純檔名) —— 檢查 (B) 用來判斷「掃的是不是自己」。"""
    return doc_rel, doc_rel.rsplit("/", 1)[-1]


# ── (A) 計數句必須釘 SHA ────────────────────────────────────────────────
def find_counts_without_sha(doc_rel: str, doc: str) -> list[Finding]:
    """句段同時含「掃描指令」與「數字＋量詞」⇒ 它是一句計數 ⇒ 必須釘 SHA。"""
    out = []
    for seg in split_segments(doc):
        if seg.struck:
            continue
        if not (_SCAN_CMD.search(seg.live) and _COUNT_TOKEN.search(seg.live)):
            continue
        if _SHA.search(seg.live):
            continue
        moving = sorted({m.group(0) for m in _MOVING_REF.finditer(seg.live)})
        note = ("基準是會移動的 ref：" + "、".join(moving)) if moving else "整句找不到任何 commit SHA"
        out.append(Finding(doc_rel, seg.line, seg.text, note))
    return out


# ── (B) 掃描指令不得住在被掃描的檔裡 ──────────────────────────────────
def find_self_scanning_commands(doc_rel: str, doc: str) -> list[Finding]:
    """句段同時含「掃描指令」與「這個檔自己的名字」⇒ 指令自計。"""
    full, base = _own_name_tokens(doc_rel)
    out = []
    for seg in split_segments(doc):
        if seg.struck:
            continue
        if not _SCAN_CMD.search(seg.live):
            continue
        if base not in seg.live:
            continue
        which = full if full in seg.live else base
        # 兩種形態分開描述，讓人一眼判得出該修還是該登記：
        #   * `git show <sha>:<自己>` 讀的是**凍結的 blob**，機制上不會自計 ——
        #     但它**字面違反**客戶裁示第 3 條，故仍然紅燈；要放行請登記 baseline。
        #   * 其餘（對工作樹跑的 grep/wc/sed…）是**真的會把自己算進去**。
        snapshot = bool(re.search(r"git\s+show\s+[0-9a-f]{7,40}:", seg.live))
        note = (f"指令與被掃的檔（{which}）在同一句。"
                + ("這是釘 SHA 的**快照**自掃 —— 機制上不會自計，但字面違反裁示第 3 條"
                   if snapshot else
                   "它會把自己算進去 —— 掃 X 的指令住在 X 裡面"))
        out.append(Finding(doc_rel, seg.line, seg.text, note))
    return out


# ── (C) 句首全稱斷言必須附反向檢查 ────────────────────────────────────
def _is_sentence_initial_universal(text: str) -> str | None:
    """``text`` 已正規化。回傳開頭那個全稱詞，或 ``None``。"""
    for word in _LOOKALIKE_COMPOUNDS:
        # 字面以某個全稱詞開頭，但整串其實是另一個詞（名詞）⇒ 根本不是斷言。
        # ⚠️ 必須**同時**碰到詞尾邊界：否則那幾個字是被更長的詞吃回去了
        #    （＝「全稱詞 ＋ 一個名詞」），那是**真的**全稱斷言，不得放過。
        if text.startswith(word) and _is_word_boundary(text, len(word)):
            return None
    for head in _UNIVERSAL_HEADS:
        if text.startswith(head):
            tail = text[len(head):].strip(" 　)）」』】]　")
            if len(tail) >= _MIN_ASSERTION_TAIL:
                return head
    return None


def find_universals_without_reverse_check(doc_rel: str, doc: str) -> list[Finding]:
    """句首全稱斷言，視窗內必須同時看得到「指令」與「輸出」。"""
    lines = doc.split("\n")
    out = []
    for seg in split_segments(doc):
        if seg.struck:
            continue
        if not seg.initial:
            # **硬換行的下半截不是句首**（第十三輪，客戶裁示第 1 件）——
            # 判準與極性見 `_is_continuation` 上方的區塊註解。
            continue
        head = _is_sentence_initial_universal(seg.text)
        if head is None:
            continue
        window = "\n".join(lines[seg.line - 1: seg.line - 1 + _REVERSE_CHECK_WINDOW])
        has_cmd = bool(_SCAN_CMD.search(window))
        has_out = bool(_OUTPUT_MARKER.search(window))
        if has_cmd and has_out:
            continue
        missing = []
        if not has_cmd:
            missing.append("指令")
        if not has_out:
            missing.append("輸出")
        out.append(Finding(
            doc_rel, seg.line, seg.text,
            f"以「{head}」開頭，但往下 {_REVERSE_CHECK_WINDOW} 行內找不到"
            + "與".join(missing)))
    return out


CHECKS = (
    (SEC_COUNTS, find_counts_without_sha),
    (SEC_SELFSCAN, find_self_scanning_commands),
    (SEC_UNIVERSALS, find_universals_without_reverse_check),
)


# ══════════════════════════════════════════════════════════════════════════
# 受檢檔案 ＋ baseline
# ══════════════════════════════════════════════════════════════════════════
def _rel_to_docs(path: Path) -> str:
    """檔案路徑 → 相對 `DOCS_DIR` 的 POSIX 字串（`_matches_glob` 吃的那個形態）。"""
    return str(path.relative_to(DOCS_DIR)).replace("\\", "/")


def scoped_paths() -> list[Path]:
    """受檢射程內的檔案路徑（排序固定）—— **`iter_docs()` 與 `scope_counts()` 共用這一份**。

    ⚠️ **目錄不見了一律 raise，不得靜默回空清單**（`CLAUDE.md` §1 Fail Loud）。
    靜默回空 ＝ 三道檢查全部變成 0 筆違規 ＝ **全綠，而且沒有人會發現**。
    一支綠燈但什麼都沒看的守衛，比一支紅燈的守衛危險得多。
    """
    if not DOCS_DIR.is_dir():
        raise FileNotFoundError(
            f"找不到受檢目錄 {DOCS_DIR.relative_to(REPO_ROOT)}。\n"
            "本守衛的全部價值來自「真的把那些檔讀完」。讀不到就直接炸掉，\n"
            "不要讓它靜默地變成一支什麼都沒檢查的綠燈測試。\n"
            "若目錄是**刻意**搬走或改名，請同步改 `DOCS_DIR`／`DOCS_GLOBS`，\n"
            "並重新量測 `DOCS_GLOBS` 的每一項下限與 `_MIN_DOCS`。")
    return sorted(p for p in DOCS_DIR.rglob("*")
                  if p.is_file() and _in_scope(_rel_to_docs(p)))


def iter_docs() -> list[tuple[str, str]]:
    """回 [(repo 相對路徑, 內容)]，路徑排序固定（射程見 `scoped_paths()`）。"""
    return [(str(p.relative_to(REPO_ROOT)).replace("\\", "/"),
             p.read_text(encoding="utf-8")) for p in scoped_paths()]


def scope_counts() -> dict[str, int]:
    """每一個 glob 在 `scoped_paths()` 交出的**那一份清單**裡各佔幾個檔。

    ⚠️ **刻意不自己再掃一次磁碟** —— 它只能數 `iter_docs()` 真的會交出去的檔。
    自己掃一套的版本會分家成「下限看得到、三道檢查沒讀到」，理由寫在 `_matches_glob`。
    ⚠️ 一個檔同時命中多條 glob 時**只算給第一條**（`break`），
    所以各項之和恆等於受檢檔數 —— 那個等式由 `test_control_scope_counts_*` 看著。
    """
    out = {pattern: 0 for pattern, _floor in DOCS_GLOBS}
    for path in scoped_paths():
        rel = _rel_to_docs(path)
        for pattern, _floor in DOCS_GLOBS:
            if _matches_glob(rel, pattern):
                out[pattern] += 1
                break
    return out


def collect(section: str) -> list[Finding]:
    """跑某一道檢查，回**全部**違規（還沒扣掉 baseline）。"""
    fn = dict(CHECKS)[section]
    out: list[Finding] = []
    for doc_rel, doc in iter_docs():
        out += fn(doc_rel, doc)
    return out


def load_baseline() -> dict[str, dict[str, dict[str, str]]]:
    """讀 baseline。**檔案不存在一律 raise** —— 理由同 `iter_docs`。

    若 baseline 不見了而本函式回空 dict，三道檢查會把**全部**歷史欠債當成新違規，
    一上線就滿江紅；反過來若有人為了變綠而砍掉 baseline 再重建，
    `git diff` 會把那件事攤在 PR 上 —— 那正是本設計要的效果。
    """
    if not BASELINE_PATH.is_file():
        raise FileNotFoundError(
            f"baseline 不見了：{BASELINE_PATH.relative_to(REPO_ROOT)}\n"
            "重建方式：python3 tests/test_doc_counters.py --update-baseline\n"
            "⛔ 重建 ＝ 承認當下所有違規，要有人明確決定（請逐句讀 git diff 再 commit）。")
    data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    for section, _ in CHECKS:
        data.setdefault(section, {})
    return data


def _new_findings(section: str) -> list[Finding]:
    """扣掉 baseline 之後**還在**的違規 —— 也就是本守衛真正要擋的東西。"""
    known = load_baseline()[section]
    return [f for f in collect(section) if f.key not in known]


_FIX_GUIDE_COMMON = """
⛔ **禁止**：直接把那一行刪掉。本 repo 的慣例是「舊條文保留不刪」，
   刪掉紀錄會讓後人失去「為什麼會變成這樣」的線索，而且是**不可逆**的。
   要退役就照慣例：**加刪除線保留** ＋ 註明「有意識的更正，不是漏刪」＋ 日期 ＋ 決策者
   ＋ 兩邊理由並陳。劃掉之後本守衛就不再檢查它 —— 那正是它該有的行為。

⛔ **禁止**：直接跑 `--update-baseline` 讓它變綠。
   baseline 是**欠債登記簿**，不是豁免按鈕。登記一筆等於簽名承認
   「這句話現在不可重現，我知道」。先試著照上面修；真的修不動才登記，
   並在 PR 描述裡寫明為什麼修不動。
"""

_FIX_GUIDE_A = """
================================================================================
(A) 計數句沒釘 commit SHA —— 怎麼修
================================================================================
(a) **把基準換成 SHA**：`git show <sha>:<path> | grep -c '…' → N`。
    ⚠️ `origin/main` / `HEAD` / `origin/main..HEAD` / 「工作樹」**都不算釘** ——
       它們是會移動的 ref，下一個人照跑會拿到不同的數字。
(b) **兩點式兩端都釘**：`<merge-base sha>..<目標 sha>`，不要只釘一端。
(c) **本輪自己的 commit SHA 寫不出來**（它還沒產生）——
    沿用 `CLAUDE.md` §-2.A 容量登記的既有慣例：基準端釘死那個已存在的 SHA，
    目標端寫「本輪 commit」，並在**下一輪續記時把它換成真的 SHA**。
    這一種請登記進 baseline，並在 PR 描述說明。
""" + _FIX_GUIDE_COMMON

_FIX_GUIDE_B = """
================================================================================
(B) 掃描指令寫進了它自己要掃的那個檔 —— 怎麼修
================================================================================
(a) **把指令移出去**：只留結論與「見 `docs/v2/41_counters.md` §41.x」，
    指令本體寫到那個指標檔裡。這是客戶 2026-09-21 裁示第 3 條的標準走法。
(b) **真的必須在本檔出現**（例如客戶原話逐字碼塊、或正在指出它錯而重述它）——
    那就登記進 baseline，並在 PR 描述寫明是哪一類。

⚠️ **為什麼 SHA 釘死的自掃也照樣紅燈**：這些檔每一輪都在被改，
   而一條住在自己目標裡的指令，遲早會有人拿它對工作樹跑一次 ——
   那一刻它就把自己算進去了。**把指令搬出去是唯一結構上安全的走法。**
""" + _FIX_GUIDE_COMMON

_FIX_GUIDE_C = """
================================================================================
(C) 句首全稱斷言沒有反向檢查 —— 怎麼修
================================================================================
(a) **附反向檢查**（客戶 2026-09-21 裁示原文：沒有反向檢查的，不准寫）：
    在該句底下附**指令 ＋ 輸出 ＋ exit code**，讓這句話可以被推翻。
    體例見 `docs/v2/41_counters.md` §41.3。
(b) **把它改成不是全稱句**：改寫成「**已知的** N 處是…（非窮舉）」之類的
    分類敘述。這正是 `CLAUDE.md` §-1.5.1c 判定 2 的方法教訓：
    **能被一條 grep 推翻的全稱句，就不該寫**。
(c) **它本來就不是斷言**（表格欄位值、客戶原話逐字引用、wireframe 版面草稿裡的
    字樣）—— 那就登記進 baseline，並在 PR 描述寫明它是哪一種。
""" + _FIX_GUIDE_COMMON


def _fail(section: str, headline: str, findings: list[Finding], guide: str) -> None:
    lines = ["", headline, ""]
    for f in sorted(findings, key=lambda x: (x.doc, x.line)):
        lines.append(f.render())
    lines += [
        "",
        "（被刪除線劃掉的句子不算 —— 那是已正確退役的紀錄，本守衛不碰。）",
        f"（上面每一筆方括號裡的 16 位字串，就是它在 baseline `{section}` 區的 key。）",
        guide,
    ]
    raise AssertionError("\n".join(lines))


# ══════════════════════════════════════════════════════════════════════════
# 三道檢查（各自獨立，一道紅不影響另外兩道的可讀性）
# ══════════════════════════════════════════════════════════════════════════
def test_counting_sentences_pin_a_commit_sha():
    """(A) `docs/v2/*.md` 裡**新增的**計數句必須釘 commit SHA。"""
    new = _new_findings(SEC_COUNTS)
    if new:
        _fail(SEC_COUNTS,
              f"`docs/v2/` 有 {len(new)} 句**新增的**計數沒有釘 commit SHA。",
              new, _FIX_GUIDE_A)


def test_scan_commands_do_not_live_in_the_file_they_scan():
    """(B) 掃描指令不得寫在它自己要掃的那個檔裡。"""
    new = _new_findings(SEC_SELFSCAN)
    if new:
        _fail(SEC_SELFSCAN,
              f"`docs/v2/` 有 {len(new)} 句**新增的**指令，寫在它自己要掃的那個檔裡。",
              new, _FIX_GUIDE_B)


def test_sentence_initial_universals_carry_a_reverse_check():
    """(C) 句首全稱斷言必須附反向檢查（指令 ＋ 輸出）。"""
    new = _new_findings(SEC_UNIVERSALS)
    if new:
        _fail(SEC_UNIVERSALS,
              f"`docs/v2/` 有 {len(new)} 句**新增的**句首全稱斷言沒有反向檢查。",
              new, _FIX_GUIDE_C)


# ══════════════════════════════════════════════════════════════════════════
# ⭐ 保護這三道檢查本身的東西（不是第四道規則，是防止前三道無聲失效）
# ══════════════════════════════════════════════════════════════════════════
# 本守衛最危險的失效模式**不是**紅燈，是**綠燈而少看**：
# 有人把某條 regex 收窄、或把 `DOCS_GLOBS` 改窄、或目錄被搬走，
# 三道檢查的命中數一起掉到 0，**測試全綠，而且沒有人會發現**。
# 下面的下限就是為了讓那種情況**跌破而紅燈**。
#
# 量測（**全部釘 `0d9753f`**，指令見本檔 `__main__` 的 `--report`）：
#     受檢檔 **25** 個；三道檢查的**違規**命中數 (A) **207**、(B) **30**、(C) **68**
#     （這是**違規數**，不是候選句數；(C) 的候選母體是 84 句，其中 16 句已附反向檢查）。
#     ⚠️ 上列數字**含**已登記進 baseline 的 —— `collect()` 不扣 baseline，下限才擋得住「少看」。
# 下限刻意設得低於現值一大截，理由據實寫出（不是隨手挑一個數）：
#   * 它**擋得住結構性損失** —— 少掉一個 regex 分支、或少掉一半的受檢檔，都會跌破。
#   * 它**擋不住、也刻意不擋逐筆的正常減少** —— 本 repo 鼓勵把過期句子加刪除線退役，
#     那會讓命中數變少。把下限貼著現值，等於把「正確退役」變成紅燈，逼人不敢退役。
# ⚠️ 若哪天真的掉到下限以下：**請改這些常數並在此寫下新的量測與理由**，
#    不要把下限一路往下調到 0 —— 那等於把這個保護拆掉。
_MIN_DOCS = 20  # ＝ `DOCS_GLOBS` 各項下限之和（15 ＋ 5）
_MIN_TOTAL_FINDINGS = {SEC_COUNTS: 120, SEC_SELFSCAN: 15, SEC_UNIVERSALS: 50}

# ⚠️ **2026-09-23 第十三輪新增（G9；決策者 客戶）：線框那一側單獨設下限。**
# **成因（稽核實測）**：總下限擋不住任何單一收窄 —— (C) 現值 68、下限 50，
# 還可以再掉 18 筆才紅；把 `_SENTENCE_END_CHARS` **整個清空**只掉到 56、
# `_MIN_ASSERTION_TAIL` 改 6 只掉到 59、毒化 `_INLINE_TAGS` 只掉到 62，**三種都不紅**。
# ⛔ **更尖銳的是**：(C) 的 68 筆裡**線框只佔 3 筆** ——
# **五個線框全部靜音也只掉 3，總下限永遠不會知道。**
# ✅ 所以這一側單獨綁。**這裡刻意貼著現值 3**（與總下限的做法不同，理由寫在下面）：
# 那 3 筆**全部是 baseline 登記過、`why_safe` 明寫「一個字都不得改」的句子**
# （`exp` 一筆格首、`hld` 兩筆 44 逐字引述、`today` 一筆 G1 後回來的），
# **不會因為正常編輯而消失**；它們掉了只有兩個成因：判定被收窄，或線框離開了射程。
# ⚠️ 若哪天真的要退役其中一句：**改這個數，並在 PR 描述寫明退役的是哪一句。**
_MIN_FINDINGS_IN_PROTOTYPES = 3


def test_guard_still_sees_the_documents_it_claims_to_check():
    """受檢檔數與三道檢查的總命中數都不得跌破下限（防「綠燈但少看」）。"""
    docs = iter_docs()
    assert len(docs) >= _MIN_DOCS, (
        f"只看到 {len(docs)} 個受檢檔，低於總下限 {_MIN_DOCS}。\n"
        f"（`{DOCS_DIR.relative_to(REPO_ROOT)}/` ＋ globs {DOCS_GLOBS}）\n"
        "檔案被搬走／改副檔名／glob 被改窄時，三道檢查會一起靜默失效。")
    seen = scope_counts()
    for pattern, floor in DOCS_GLOBS:
        assert seen[pattern] >= floor, (
            f"glob `{pattern}` 只看到 {seen[pattern]} 個檔，低於它自己的下限 {floor}。\n"
            "⚠️ **這一條是逐 glob 的，不是只看總數** —— 整列被拿掉時總數下限擋不住"
            "（`.md` 一個人就遠超總下限），三道檢查會對那一批檔靜默停止檢查。")
    proto = len([f for f in collect(SEC_UNIVERSALS) if f.doc.startswith(_PROTOTYPE_DIR)])
    assert proto >= _MIN_FINDINGS_IN_PROTOTYPES, (
        f"(C) 在 `{_PROTOTYPE_DIR}` 那一側只剩 {proto} 筆，低於它自己的下限 "
        f"{_MIN_FINDINGS_IN_PROTOTYPES}。\n"
        "⚠️ **總下限擋不住這個** —— 線框那一側只佔 (C) 的個位數，五個線框全部靜音，"
        "總數也只掉個位數。\n"
        "   兩個成因：(a) 判定被收窄了（無聲失效，正是本條要擋的）；"
        "(b) 真的退役了其中一句（那請改 `_MIN_FINDINGS_IN_PROTOTYPES` 並在 PR 描述寫明是哪一句）。")
    for section, floor in _MIN_TOTAL_FINDINGS.items():
        total = len(collect(section))
        assert total >= floor, (
            f"檢查 `{section}` 的總命中數掉到 {total}，低於下限 {floor}。\n"
            "⚠️ 這**不一定**是好消息：命中數大幅下降的兩個成因，\n"
            "   一是真的把文件修好了（那請重新量測並改這裡的下限），\n"
            "   二是**偵測器被收窄了**（那是一次無聲的失效，正是本測試要擋的）。\n"
            "   兩者靠 `git diff` 分辨：改的是 `docs/v2/*.md` 還是本檔的 regex？")


def test_baseline_has_no_unknown_sections_and_is_readable():
    """baseline 結構完整、每一筆都帶得起人看的檔名與句子。"""
    data = load_baseline()
    known = {s for s, _ in CHECKS}
    unknown = {k for k in data if not k.startswith("_")} - known
    assert not unknown, (
        f"baseline 有本檔不認得的分區：{sorted(unknown)}\n"
        "（分區改名會讓那一整區的登記無聲失效 —— 全部變回「新違規」。）")
    for section in known:
        for key, entry in data[section].items():
            assert re.fullmatch(r"[0-9a-f]{16}", key), f"{section} 的 key 形態不對：{key!r}"
            assert isinstance(entry, dict) and entry.get("file") and entry.get("text"), (
                f"{section}/{key} 少了 `file` 或 `text` —— "
                "baseline 必須人讀得懂，否則沒有人能稽核它登記了什麼。")


def test_baseline_entries_that_no_longer_match_are_reported():
    """已修好／已改寫的 baseline 登記會變成「孤兒」，在這裡印出來提醒清理。

    ⚠️ **刻意只印不紅燈**（與 `tests/test_constitution_file_refs.py` 的
    `test_every_exemption_is_still_needed` 不同，理由在此寫明，不是漏抄）：
    那一支的豁免清單只有個位數，而本檔的 baseline 是三位數的**歷史欠債登記簿**。
    只要有人編輯一句已登記的話，它的正規化文字就變了 ⇒ 舊 key 變孤兒、新 key 同時觸發。
    把孤兒也設成紅燈，等於**每一次正常的文字編輯都罰兩次**，
    後果是沒有人敢動 `docs/v2/`。**少看的風險已由上面的下限測試擋住**，
    孤兒在這裡只需要可見。

    ⚠️ **2026-09-23 第十三輪就地更正（有意識的更正，不是漏刪 · 決策者 客戶，裁示第 1 件）**：
    本函式原本印 ~~「（已修好或已改寫，可以清掉）」~~ —— **那句話把三種成因說成兩種**。
    **舊表述的用意仍然成立**（前兩種成因確實存在，而且確實可以清掉）；
    **被權衡掉的是它的窮舉性**：第十三輪把句首判定改成看得見上一行結尾之後，
    出現了**第三種成因** —— **句子一個字未動，是守衛不再把它當句首**。
    那一種**不是已修好**，清掉它等於把「這句話仍未附反向檢查」這個事實一起抹掉。
    ⇒ 訊息改成「成因見下，不要一律當成已修好」，並由
    `test_control_annotated_orphans_are_really_orphans` 看著那批被註記的列。
    """
    data = load_baseline()
    for section, _ in CHECKS:
        live = {f.key for f in collect(section)}
        orphans = [(k, v) for k, v in data[section].items() if k not in live]
        if orphans:
            print(f"\n[warning] baseline `{section}` 有 {len(orphans)} 筆孤兒登記"
                  f"（成因見下，**不要一律當成已修好**）：")
            for k, v in orphans[:10]:
                print(f"  [{k}] {v['file']}  {v['text'][:80]}")
            if len(orphans) > 10:
                print(f"  …另有 {len(orphans) - 10} 筆未列出")


def test_orphans_without_an_annotation_are_a_red_light():
    """**沒有註記**的孤兒一律紅燈；**已註記**的照舊只印不紅（上一條）。

    ⚠️ **2026-09-23 第十三輪新增（G8；決策者 客戶）。** 在它之前，孤兒**只**走上一條的
    `print`，而 **pytest 對「通過的測試」會吞掉 stdout** —— 實測 `-q` 只印 `1 passed`，
    要加 `-s` 才看得到。上一條的 docstring 寫「孤兒在這裡只需要可見」，
    **而它在 CI 上根本不可見**。
    ⚠️ **為什麼只對「未註記」紅**：對全部孤兒紅會讓**每一次正常的文字編輯都罰兩次**
    （編一句已登記的話 ⇒ 新 key 觸發一次、舊 key 變孤兒再觸發一次），
    那正是上一條當初刻意不紅的理由，**那個理由一個字都沒有被推翻**。
    ⛔ **代價據實寫明，不要以為這一條沒有成本**：編輯一句已登記的話，
    **確實**會同時拿到「新違規」與「未註記孤兒」兩個紅燈。
    **兩者都有明確的修法**（照 `_FIX_GUIDE_*` 修好，或在 baseline 那一列加註記說明它為什麼不再命中），
    而在它之前，那個孤兒是**一個字都看不到的**。
    """
    data = load_baseline()
    bad = []
    for section, _ in CHECKS:
        live = {f.key for f in collect(section)}
        bad += [(section, k, v) for k, v in data[section].items()
                if k not in live and _ORPHAN_FIELD not in v]
    assert not bad, (
        f"baseline 有 {len(bad)} 筆**沒有註記**的孤兒登記（已登記、但現在不再命中）：\n  "
        + "\n  ".join(f"[{k}] {v['file']}  {v['text'][:70]}" for _s, k, v in bad[:10])
        + (f"\n  …另有 {len(bad) - 10} 筆未列出" if len(bad) > 10 else "")
        + f"""

怎麼修（三條路，**選一條並在 PR 描述寫明**）：
  (a) **那句話真的被修好／改寫了** → 把那一列從 baseline 刪掉。刪掉就是承認「這筆債清了」。
  (b) **句子一個字沒動，是判定改了**（本輪 G1／G6 就是這一種）→
      在那一列加 `{_ORPHAN_FIELD}` 欄位，寫明**為什麼它不再命中**，並說明
      **那句話本身是不是還有問題**（多半還有 —— 守衛不看它，不等於它變乾淨了）。
  (c) **它其實該回來** → 把判定改回去，或替它補反向檢查。
⛔ **不要靠 `--update-baseline` 重建來消掉它** —— 本份 baseline 禁止重建（見模組 docstring）。""")


# ══════════════════════════════════════════════════════════════════════════
# ⭐ 正控 ＋ 負控 —— 沒有正控的綠燈 ＝ 沒有檢查
# ══════════════════════════════════════════════════════════════════════════
# 一支「什麼都抓不到」的守衛也會全綠。下面每一道檢查都配一個**刻意造的違規**
# （正控：必須被抓到）與一個**乾淨的句子**（負控：必須不被誤報）。
# ⚠️ 本段的字串**刻意長成違規的樣子** —— 那就是正控的定義。
#    故下方的自我合規測試把射程限在**模組 docstring**，並就地寫明，不藏。
_DEMO = "docs/v2/99_demo.md"


def test_control_A_unpinned_count_fires_and_pinned_count_does_not():
    bad = "實測 `git grep -n 'X' -- '*.py'` → **7 處**"
    good = "實測 `git show 4851465:CLAUDE.md | grep -c 'X'` → **7 處**"
    assert len(find_counts_without_sha(_DEMO, bad)) == 1, "正控失效：沒釘 SHA 的計數沒有被抓到"
    assert find_counts_without_sha(_DEMO, good) == [], "負控失效：釘了 SHA 的計數被誤報"


def test_control_A_moving_refs_are_not_accepted_as_pinned():
    for ref in ("origin/main", "HEAD", "工作樹"):
        doc = f"實測 `git grep -c 'X' {ref}` → **12 筆**"
        found = find_counts_without_sha(_DEMO, doc)
        assert len(found) == 1, f"正控失效：以 {ref} 當基準的計數沒有被抓到"
        assert "會移動的 ref" in found[0].note, f"診斷訊息沒有點名 {ref}"


def test_control_A_struck_through_count_does_not_fire():
    doc = "~~實測 `git grep -n 'X' -- '*.py'` → **7 處**~~ → 已於 4851465 撤銷"
    assert find_counts_without_sha(_DEMO, doc) == [], "負控失效：被劃掉的舊計數不該被檢查"


def test_control_B_self_scan_fires_and_scanning_another_file_does_not():
    bad = "實測 `grep -c 'X' docs/v2/99_demo.md` → **3 處**"
    good = "實測 `grep -c 'X' docs/v2/20_ui_spec.md` → **3 處**"
    assert len(find_self_scanning_commands(_DEMO, bad)) == 1, "正控失效：指令自計沒有被抓到"
    assert find_self_scanning_commands(_DEMO, good) == [], "負控失效：掃別的檔被誤報成自計"


def test_control_B_mentioning_own_name_without_a_command_does_not_fire():
    doc = "本節的結論寫在 docs/v2/99_demo.md 第二段，指令見 41_counters.md"
    assert find_self_scanning_commands(_DEMO, doc) == [], "負控失效：只提到自己檔名不算指令自計"


def test_control_C_bare_universal_fires_and_one_with_a_reverse_check_does_not():
    bad = "所有欄位都已經查過了"
    good = ("所有欄位都已經查過了\n"
            "- 反向檢查：`git grep -n 'Y' -- '*.py'` → **0 命中**，exit=1")
    assert len(find_universals_without_reverse_check(_DEMO, bad)) == 1, \
        "正控失效：沒有反向檢查的句首全稱斷言沒有被抓到"
    assert find_universals_without_reverse_check(_DEMO, good) == [], \
        "負控失效：附了反向檢查的全稱句被誤報"


def test_control_C_mid_sentence_universal_does_not_fire():
    """句**中**的副詞不是句首斷言 —— 這正是 1915 收斂到 86 的那一刀。"""
    doc = "本組三處實測結果都一致，沒有例外"
    assert find_universals_without_reverse_check(_DEMO, doc) == [], \
        "負控失效：句中副詞被誤判成句首斷言"


def test_control_C_table_cell_that_is_just_a_value_does_not_fire():
    doc = "| 射程 | 全部 | 見 §2 |"
    assert find_universals_without_reverse_check(_DEMO, doc) == [], \
        "負控失效：表格裡只填兩個字的欄位值被誤判成斷言"


def test_control_C_grammar_term_lookalike_does_not_fire():
    """負控：以**文法術語**開頭的句段不是全稱斷言 —— 客戶 2026-09-23 裁示的那個誤紅。

    第九輪凍結組在 §7.2 寫紀錄時被這一刀誤紅，當時是**改寫措辭繞開**的（守衛沒動、
    baseline 沒動），所以在本輪之前，下一個人寫到同一個詞還會再紅一次。
    ⚠️ 受測字串**現編** —— 由 `_LOOKALIKE_COMPOUNDS` 取出再接上下文，不在本檔重打那個字面。

    ⚠️ **射程據實寫明**：本例外只涵蓋「該詞後面碰到**非中日韓字元**」這一種形狀
    （標點、空白、拉丁字母、數字）。**後面直接接中文的一律照抓** ——
    那不是漏掉，是刻意付的成本，理由與正控見 `_is_word_boundary`。
    """
    word = _LOOKALIKE_COMPOUNDS[0]
    for tail in ("，限定到第八輪那一行登記",      # 標點邊界
                 " (possessive case)",            # 空白 ＋ 拉丁字母邊界
                 "」這個詞在本檔只出現在測試裡"):  # 全形引號邊界
        assert find_universals_without_reverse_check(_DEMO, word + tail) == [], \
            f"負控失效：以文法術語開頭的句段被誤判成句首全稱斷言（後接 {tail!r}）"


def test_control_C_lookalike_followed_by_cjk_still_fires():
    """正控：複合詞後面**直接接中文**時一律照抓 —— 第十輪稽核抓到的無聲漏抓。

    第十輪之前，詞尾邊界判定除了「非中日韓字元」之外**還多吃了一種放過條件**，
    於是下面這四句**真的全稱斷言**全部被放過 —— 而且是
    **三道檢查照樣全綠、沒有任何一條測試會紅**的那種漏抓。
    ⚠️ 這四句與那個文法術語**字面同形**（中文不寫空格），**沒有任何詞表分得出來**；
    本檔選的是「寧可多紅一次」那一邊，理由寫在 `_is_word_boundary` 的 docstring。
    ⚠️ **這一條同時是「字表例外沒有被放寬過頭」的正控** ——
    它與下一條（被更長的詞吃回去）合起來，把「後面接中文」的兩種形狀都釘住了。
    """
    word = _LOOKALIKE_COMPOUNDS[0]
    for tail in ("的寬度都一樣",
                 "是黃的",
                 "與欄都要對齊",
                 "在第二欄"):
        assert len(find_universals_without_reverse_check(_DEMO, word + tail)) == 1, \
            f"正控失效：以複合詞開頭、後面直接接中文的全稱斷言被放過（後接 {tail!r}）"


def test_control_C_longer_word_that_swallows_the_lookalike_still_fires():
    """正控：複合詞的字面被更長的詞吃回去時，它**還是**一句全稱斷言，必須照抓。

    ⚠️ 這一條就是 `_is_word_boundary` 存在的理由 —— 沒有它，字表例外會從
    「修誤報」變成「**放寬規則**」：下面這兩句都是**真的**全稱斷言，
    只是前幾個字碰巧與那個文法術語相同。放寬**不在客戶裁示的射程內**。
    """
    word = _LOOKALIKE_COMPOUNDS[0]
    for tail in ("式都必須改成同一種寫法",   # …＋「格式」
                 "子都是同一個寬度"):        # …＋「格子」（UI 規格裡真的會這樣寫）
        assert len(find_universals_without_reverse_check(_DEMO, word + tail)) == 1, \
            f"正控失效：被更長的詞吃回去的全稱斷言沒有被抓到（後接 {tail!r}）—— 字表例外放寬過頭了"


def test_control_C_word_boundary_predicate_is_a_closed_set():
    """`_is_word_boundary` 的「**不算**邊界」那一側必須維持封閉 —— 不得被逐字挖洞。

    ⚠️ **這一條是第十輪突變實測逼出來的，不是預防性的**：把 `_CJK` 改成帶
    negative lookahead、只挖掉**一個**中日韓文字，**全部測試照樣綠** ——
    而挖掉的那個字正好是 `docs/v2/` 底下真的寫過的一句全稱斷言用到的
    （「⋯⋯線一律 …」）。逐字挖洞是「開放的放過清單」的**同型後繼**，
    只是門檻高一點：它放掉的同樣是**沒有人會發現**的漏抓。

    ⚠️ **刻意逐碼位窮舉，不取樣** —— 本組第一版用的是「每 17 碼位取一點」，
    而挖在取樣點之外的洞照樣全綠（實測：挖掉 U+4E86 → 全綠）。
    **一個抽樣式的封閉性檢查，本身就是一張開放清單。** 現改為把
    `_CJK` 自己宣告的三個區段**逐一走完**：任何一處被挖掉都會當場紅燈。
    ⚠️ **本條鎖的是下限不是上限**：把區段**加寬**（例如補上擴充區）不會紅，
    只有**變窄或挖洞**才會 —— 極性與 `_is_word_boundary` 同向。
    """
    word = _LOOKALIKE_COMPOUNDS[0]
    covered = [(0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF)]
    for lo, hi in covered:
        for cp in range(lo, hi + 1):
            assert not _is_word_boundary(word + chr(cp), len(word)), \
                (f"U+{cp:04X} 被判成詞尾邊界 —— 『不算邊界』那一側被挖洞或收窄了，"
                 "「複合詞 ＋ 這個字」的全稱斷言會無聲漏抓")


def test_control_C_lookalike_table_is_wired_to_the_word_table():
    """字表例外必須真的長在 `_UNIVERSAL_HEADS` 上，否則它是一張**死表**。

    死表的危險與本檔下限測試擋的是同一種：例外永遠不命中、**測試照樣全綠、沒有人會發現**。
    這一條讓「表寫錯了／字表被重排了」當場紅燈。
    """
    assert _LOOKALIKE_COMPOUNDS, "字表例外不得是空的 —— 空表等於這次修復沒有生效"
    for word in _LOOKALIKE_COMPOUNDS:
        assert any(word.startswith(h) and len(word) > len(h) for h in _UNIVERSAL_HEADS), \
            f"{word!r} 並不是「某個全稱詞 ＋ 後綴」—— 這一筆登記在這裡沒有意義"
        assert _is_sentence_initial_universal(word + "，後面接一句話") is None, \
            f"{word!r} 沒有被字表例外擋下"
        # ⚠️ **單獨出現時它不歸字表例外管**，擋它的是**尾長下限** ——
        #    去掉開頭那個全稱詞之後只剩不到 `_MIN_ASSERTION_TAIL` 個字。
        #    第十輪稽核實測：原本擺在這裡的
        #    `assert _is_sentence_initial_universal(word) is None` **毫無鑑別力**
        #    —— 把整個字表例外拿掉它照樣綠，而它的失敗訊息還會把病因指錯。
        #    現在改成驗「那條路還在」：有人調低下限或收進更長的複合詞時，
        #    這一條會紅，提醒他此時才真的需要一條字表例外的正控。
        head = next(h for h in _UNIVERSAL_HEADS if word.startswith(h))
        assert len(word) - len(head) < _MIN_ASSERTION_TAIL, \
            (f"{word!r} 去掉 {head!r} 之後尾長已達 {_MIN_ASSERTION_TAIL}，"
             "「單獨出現」不再由尾長下限擋 —— 請為這個情形補一條真的正控")


# ── (C) 行首 HTML 標籤：正控 ／ 負控 ／ 突變（第十二輪客戶裁示第 1 件）─────────
# 受測字串**現編**：開頭那個詞由 `_UNIVERSAL_HEADS` 取出再接上下文，本段不重打那四個字面
# （理由同 `_head_ending_with`：受測字串寫進文件就會被自己掃到，`CLAUDE.md` §-2.A 第 8 款）。
# ⚠️ **六種形狀刻意都留著**：單層、雙層、帶屬性、收尾標籤、以及「標籤 ＋ 開引號」——
#    最後一種就是 `docs/v2/prototype/ui_prototype_hld.html` 那兩句 44 逐字引述的形狀，
#    它同時證明「標籤必須與其餘裝飾交替剝」（只剝標籤不剝 `「` 的版本會放過它）。
_LEADING_TAG_SHAPES: tuple[tuple[str, str], ...] = (
    ("<p>", "</p>"),
    ("<li>", "</li>"),
    ("<b>", "</b>"),
    ('<td class="src">', "</td>"),
    ("<span><b>", "</b></span>"),
    ("<td>「", "」</td>"),
    ("</td><td>", "</td>"),          # 以**收尾標籤**開頭 —— 本分支原本零覆蓋
)

# 一句**刻意造的**全稱斷言的尾巴 —— 與 `test_control_C_bare_universal_*` 用的是同一句，
# 差別只在前面包了標籤。兩者並排，才看得出本輪改的是「標籤」而不是別的東西。
_TAG_CONTROL_TAIL = "欄位都已經查過了"


def _tag_led_sample(head: str, shape: tuple[str, str]) -> str:
    return f"{shape[0]}{head}{_TAG_CONTROL_TAIL}{shape[1]}"


def test_control_C_universal_behind_a_leading_html_tag_fires():
    """正控：以行首 HTML 標籤開頭的全稱斷言**必須**被 (C) 抓到。

    ⛔ **沒有這一條，本輪的改動就沒有證據。** **本輪（第十二輪）之前** `_LEADING_FURNITURE`
    只剝 markdown 裝飾、不剝標籤（第十一輪把線框納入射程時也沒有動這裡）
    ⇒ 下面每一句都被靜默放過，
    而 `docs/v2/prototype/` 的線框整份是 HTML。
    ⚠️ **四個全稱詞逐個跑**：只挑一個詞的版本，換一個詞就可能無聲漏抓。
    """
    for head in _UNIVERSAL_HEADS:
        for shape in _LEADING_TAG_SHAPES:
            doc = _tag_led_sample(head, shape)
            assert len(find_universals_without_reverse_check(_DEMO, doc)) == 1, \
                f"正控失效：行首標籤後面的句首全稱斷言被放過（{doc!r}）"


def test_control_C_tag_led_universal_with_a_reverse_check_does_not_fire():
    """負控：標籤開頭、但**附了反向檢查**的全稱句不得被誤報 —— 剝標籤沒有改變 (C) 的判準。"""
    for head in _UNIVERSAL_HEADS:
        doc = (_tag_led_sample(head, _LEADING_TAG_SHAPES[0])
               + "\n<li>反向檢查：`git grep -n 'Y' -- '*.py'` → **0 命中**，exit=1</li>")
        assert find_universals_without_reverse_check(_DEMO, doc) == [], \
            f"負控失效：附了反向檢查的標籤開頭全稱句被誤報（head={head!r}）"


def test_control_C_a_bare_open_angle_is_not_treated_as_a_tag():
    """負控：`<` 後面不是標籤名時不得被剝掉 —— 否則本式會咬進真正的內文。

    ⚠️ **`<!--` 刻意不在這一組裡，而且不是因為它「不該紅」** —— 它**會**紅，
    但成因與本式無關（見 `test_control_C_a_commented_out_universal_is_still_checked`）。
    把它放進負控會讓這條測試量到別的東西 —— 本組初稿就是這樣寫的，當場被自己的測試推翻。
    """
    # ⚠️ `"<b 大於 <code>"` 這一個是 `[^<>]` 的**唯一**覆蓋：換成 `[^>]` 會一口吃到
    #    第一個 `>`、把後面的斷言曝出來 ⇒ 本條轉紅。那是往「無聲漏抓」走的方向。
    for prefix in ("<<< ", "< ", "<1> ", "<b 大於 <code>"):
        for h in _UNIVERSAL_HEADS:
            doc = f"{prefix}{h}{_TAG_CONTROL_TAIL}"
            assert find_universals_without_reverse_check(_DEMO, doc) == [], \
                f"負控失效：{prefix!r} 被當成 HTML 標籤剝掉了（head={h!r}）"


def test_control_C_a_commented_out_universal_is_still_checked():
    """正控：被 HTML 註解掉的句首全稱斷言**照樣**進 (C) —— 而且與剝標籤無關。

    **機制（實測，非推論）**：ASCII `!` 是 `_SENTENCE_SPLIT` 的切點之一，
    所以 `<!-- 句子` 會在 `!` 處被切成 `<` 與 `-- 句子`，後者的 `--` 被當成清單符號剝掉
    ⇒ 剩下的就是那句斷言本身。**本輪改動前後都是這個行為。**

    ⚠️ **記這一條的理由**：本組在 `_LEADING_HTML_TAG` 的初稿註解裡寫過
    「註解掉的句首斷言不會被 (C) 看到，這是已登記的缺口」—— **那一句是假的，沒有實跑就寫下**，
    被本輪新增的負控當場推翻。條文留著，是為了讓下一個人不要再憑直覺重新登記一次同樣的假缺口。
    ⚠️ **這一條鎖的是現況，不是主張它應該如此**：若日後有人認為註解掉的句子該被豁免
    （與刪除線同一個道理），那是**放寬規則**，要走客戶裁示，不是改掉這條測試了事。
    """
    for h in _UNIVERSAL_HEADS:
        for prefix in ("<!-- ", "<!--"):
            doc = f"{prefix}{h}{_TAG_CONTROL_TAIL}"
            assert len(find_universals_without_reverse_check(_DEMO, doc)) == 1, \
                f"正控失效：被註解掉的句首全稱斷言被放過（{doc!r}）"


def test_control_html_strike_tags_are_masked_like_tildes():
    """正控：`<s>`／`<del>` 包住的退役句與 `~~` 一樣不受檢，拿掉標籤就該重新命中。"""
    for tag in ("s", "del"):
        for h in _UNIVERSAL_HEADS:
            body = f"{h}{_TAG_CONTROL_TAIL}"
            assert find_universals_without_reverse_check(
                _DEMO, f"<td><{tag}>{body}</{tag}> → 2026-09-23 退役") == [], \
                f"正控失效：<{tag}> 包住的退役句仍被檢查（head={h!r}）"
            assert len(find_universals_without_reverse_check(_DEMO, f"<td>{body}")) == 1, \
                f"對照失效：同一句拿掉 <{tag}> 之後就該命中（head={h!r}）"


def test_mutation_dropping_html_strike_tag_support_turns_the_control_red():
    """突變：拿掉遮罩對 `<s>`／`<del>` 的支援 → 上一條正控必須轉紅。"""
    global _STRIKE_TAGS
    original = _STRIKE_TAGS
    try:
        _STRIKE_TAGS = re.compile(r"(?!x)x")            # 永不命中
        for h in _UNIVERSAL_HEADS:
            assert len(find_universals_without_reverse_check(
                _DEMO, f"<td><s>{h}{_TAG_CONTROL_TAIL}</s>")) == 1, \
                f"突變後仍不命中 —— 正控抓的不是 `<s>` 支援，沒有鑑別力（head={h!r}）"
    finally:
        _STRIKE_TAGS = original
    for h in _UNIVERSAL_HEADS:
        assert find_universals_without_reverse_check(
            _DEMO, f"<td><s>{h}{_TAG_CONTROL_TAIL}</s>") == [], "突變後沒有還原遮罩"


def test_control_leading_tag_stripping_leaves_the_markdown_corpus_untouched():
    """負控（語料層）：`docs/v2/*.md` 那一側的三道檢查結果**逐筆不變**。

    ⚠️ **這一條刻意不寫死「85」那個數字**：寫死的下一秒就會因為別人正常編輯文件而紅，
    而本檔自己的下限測試那一段已經說明「把數字貼著現值等於逼人不敢退役」。
    改成**當場跑兩次**（剝標籤 ／ 不剝標籤）逐筆比對 —— 它問的是
    「本輪這一項改動有沒有碰到 `.md`」，而那個答案不隨文件編輯漂移。

    ⚠️ **它哪一天會紅**：有人在 `docs/v2/*.md` 寫出一行以 HTML 標籤開頭的句子。
    那不是這條測試壞了，是 `.md` 那一側**真的**被本項改動涵蓋到了 ——
    屆時請重新量測、把新出現的那幾筆照 `_FIX_GUIDE_C` 修掉或明確登記，**不要刪掉這條測試**。
    """
    global _LEADING_FURNITURE
    original = _LEADING_FURNITURE

    def md_side() -> dict[str, set[tuple[str, str]]]:
        return {section: {(f.doc, f.text) for f in collect(section)
                          if not f.doc.startswith(_PROTOTYPE_DIR)}
                for section, _ in CHECKS}

    try:
        with_tags = md_side()
        _LEADING_FURNITURE = _furniture_re(
            tuple(p for p in _LEADING_FURNITURE_PARTS if p != _LEADING_HTML_TAG))
        without_tags = md_side()
    finally:
        _LEADING_FURNITURE = original
    assert _LEADING_FURNITURE is original, "沒有還原 `_LEADING_FURNITURE`"
    for section, _ in CHECKS:
        added = sorted(with_tags[section] - without_tags[section])
        dropped = sorted(without_tags[section] - with_tags[section])
        assert not added and not dropped, (
            f"剝行首標籤改動了 `docs/v2/*.md` 那一側的 `{section}`：\n"
            f"  多出來 {len(added)} 筆：{added[:3]}\n"
            f"  不見了 {len(dropped)} 筆：{dropped[:3]}\n"
            "⚠️ **`dropped` 非空是嚴重訊號** —— 剝標籤在設計上只可能讓更多句首露出來，\n"
            "   少掉任何一筆代表本式咬到了不該咬的東西（見 `_LEADING_HTML_TAG` 的說明）。")


def test_mutation_removing_the_leading_tag_rule_turns_the_control_red():
    """突變：把剝標籤那一項拿掉 → 上面的正控**必須**轉紅。

    ⚠️ **這一條是「正控有沒有鑑別力」的唯一證據**（體例同
    `test_mutation_narrowing_the_scope_back_turns_the_controls_red`）：
    一條永遠綠的正控，與根本沒有正控，效果完全一樣。
    ⚠️ **突變只拿掉一項、其餘 parts 原封不動** —— 這樣轉紅才只能歸因於那一項。
    """
    global _LEADING_FURNITURE
    original = _LEADING_FURNITURE
    try:
        _LEADING_FURNITURE = _furniture_re(
            tuple(p for p in _LEADING_FURNITURE_PARTS if p != _LEADING_HTML_TAG))
        for head in _UNIVERSAL_HEADS:
            for shape in _LEADING_TAG_SHAPES:
                doc = _tag_led_sample(head, shape)
                assert find_universals_without_reverse_check(_DEMO, doc) == [], (
                    f"突變後仍然抓得到 {doc!r} —— 正控抓的不是「剝標籤」這一項，沒有鑑別力")
    finally:
        _LEADING_FURNITURE = original
    for head in _UNIVERSAL_HEADS:
        assert len(find_universals_without_reverse_check(
            _DEMO, _tag_led_sample(head, _LEADING_TAG_SHAPES[0]))) == 1, "突變後沒有還原剝除式"


# ── (C) 硬換行續行：正控 ／ 負控 ／ 兩個方向的突變（第十三輪客戶裁示第 1 件）─────
# ⚠️ **受測字串現編**（同 `_head_ending_with` 的理由）：全稱詞由 `_UNIVERSAL_HEADS` 取出。
# ⚠️ **句子本體在正控與負控裡逐字相同，只有它前面那一行不同** —— 這是刻意的：
#    第十一輪出過一次事故，一條正控的綠燈**純粹來自位置**而不是來自判定，
#    那叫規避不叫修好。並排同一句話，才看得出改的是「上一行有沒有把話講完」。
_CONT_TAIL = "欄位都已經查過了"
# 一行**沒有把話講完**的開頭（無句末標點、無區塊收尾標籤、不是結構行）。
_CONT_UNFINISHED_HEAD = "<li><b>本組實測</b>：三個來源"
# 同一句話的前半，但**把話講完了**的各種形態。
# ⚠️ **2026-09-23 第十三輪回修（G3；決策者 客戶）—— 這張表原本只有三列，而且第三列在空轉。**
#    稽核實測：原本代表「結構行」的那一列用的是 `` ``` ``，
#    但 `_ends_a_block("```", "```")` 裡反引號**被 `_TRAILING_MARKUP` 的 `rstrip` 吃光**，
#    走的是 `if not tail: return True` —— **根本沒有經過 `_SELF_CONTAINED_LINE`**。
#    也就是：**那條述詞有一條自稱在守它的正控，實際上一次都沒有碰到它**；
#    把 `_SELF_CONTAINED_LINE` 整個關掉，58 條測試 **0 紅**。
# ✅ 現在每一列都標出**它負責打哪一條述詞**，並由
#    `test_mutation_each_finished_head_is_pinned_to_its_own_predicate` 逐列關掉那一條、驗它真的轉啞。
# ⛔ **新增一列時必須同時指定 `pred`，而且那一列要真的只靠那條述詞成立** ——
#    打在會被別條分支攔截的樣本上，就是本輪在修的這個病。
_CONT_FINISHED_HEADS: tuple[tuple[str, str, str], ...] = (
    ("句末標點（原本就有的六個字元）", "<li><b>本組實測</b>：三個來源都查過了。", "句末字表整個關掉"),
    ("句末標點（本輪補的全形右括號）", "<li>本組實測（三個來源都查過了）", "句末字表退回第十二輪"),
    ("句末標點（本輪補的右引號）", "<li>本組實測，他說「三個來源都查過了」", "句末字表退回第十二輪"),
    ("區塊收尾標籤", "<tr><td>三個來源</td>", "_INLINE_TAGS"),
    ("結構行（標題）", "## 這一節的標題沒有句號", "_SELF_CONTAINED_LINE"),
    ("結構行（引用）", "> 這一行是引用，沒有句號", "_SELF_CONTAINED_LINE"),
    ("結構行（表格列）", "| 欄一 | 欄二 |", "_SELF_CONTAINED_LINE"),
    ("結構行（水平線）", "---", "_SELF_CONTAINED_LINE"),
    ("子句末冒號", "<li><b>本組實測</b>，三個來源：", "_CLAUSE_END_CHARS"),
    ("行尾強調符號蓋住句號", "**三個來源都查過了。**", "_TRAILING_MARKUP"),
)

# 上一行**沒把話講完**，但**這一行自己開了一個新區塊**的形態 ——
# 打的是 `_starts_a_new_block` 那一側（`_CONT_FINISHED_HEADS` 打的是 `_ends_a_block` 那一側）。
# ⚠️ **`|` 表格列刻意不收進這張表**：那種行的第一個句段起點不在 0
#    （`|` 本身就是切點），`initial` 恆為真，**根本不經過 `_starts_a_new_block`** ——
#    收進來就是又一條「打在會被別條分支攔截的樣本上」的假正控。
_CONT_BLOCK_STARTS: tuple[tuple[str, str, str], ...] = (
    ("markdown 清單符號", "- ", "_MD_BLOCK_START"),
    ("markdown 標題", "## ", "_MD_BLOCK_START"),
    ("markdown 引用", "> ", "_MD_BLOCK_START"),
    ("有序清單", "1. ", "_MD_BLOCK_START"),
    ("帶括號的編號（本輪新增）", "(1) ", "_MD_BLOCK_START"),
    ("符號項目符號（本輪新增）", "⚠ ", "_MD_BLOCK_START"),
    ("區塊標籤", "<td>", "_INLINE_TAGS"),
)


def _cont_doc(first_line: str, head: str) -> str:
    """兩行：第一行是 ``first_line``，第二行以 ``head`` 開頭的全稱斷言（**永遠同一句**）。"""
    return f"{first_line}\n  <b>{head}{_CONT_TAIL}</b>"


# ⚠️ **G4（2026-09-23 第十三輪回修，客戶裁示）：受測表一律先驗非空。**
#    稽核實測：把下面任一張表清成 `()`，靠它的正控與突變**全部變綠** ——
#    `_ESCAPED_SHAPES = ()` 一行就能把「五種形狀都修好了」的全部證據一次抹掉。
#    ⛔ **同一支檔案上一輪才替 `_LOOKALIKE_COMPOUNDS` 加過 `assert ...`（見
#    `test_control_C_lookalike_table_is_wired_to_the_word_table`）——**上一輪做了、這一輪漏了**。
#    本條把那個體例補齊到本輪新增的四張表上。
# ⚠️ **非空只是地基，不是證明**：表有內容不代表內容是對的；
#    「內容對不對」由各自的正控與突變管。缺了非空，那些正控**連跑都沒跑到**。
_REQUIRED_TABLES: tuple[tuple[str, int], ...] = (
    ("_ESCAPED_SHAPES", 5),            # 第十二輪登記的五種逃網形狀，一種都不得少
    ("_CONT_FINISHED_HEADS", 3),       # 三種「上一行把話講完」的收尾機制
    ("_CONTINUATION_SUPPRESSED", 3),   # 本輪判定為硬換行假句首的那幾筆（G1 後由 4 → 3）
    ("_CONTINUATION_STILL_CAUGHT", 4), # 同批裡**不同型**、仍然照抓的那幾筆（G1 後由 3 → 4）
)


def test_control_every_new_lookup_table_is_non_empty():
    """所有受測表都必須非空，而且筆數不得低於它登記的下限。

    ⛔ **沒有這一條，本輪全部的正控都是可以一行關掉的。**
    ⚠️ **下限刻意等於當前筆數**（不是「大於 0」）：這幾張表記的是**已登記的具體項目**
    （五種形狀／三種收尾機制／逐筆的 baseline key），**少一筆就是少驗一種**，
    與 `_MIN_TOTAL_FINDINGS` 那種「會隨文件編輯正常浮動」的量完全不同 ——
    那裡貼著現值會逼人不敢退役，這裡貼著現值正是要求「要退役請有意識地改這個數」。
    """
    for name, floor in _REQUIRED_TABLES:
        table = globals().get(name)
        assert table is not None, f"`{name}` 不存在了 —— 靠它的正控會靜默變成空掃"
        assert len(table) >= floor, (
            f"`{name}` 只剩 {len(table)} 筆，低於下限 {floor}。\n"
            "⚠️ 這張表是某一組正控的**母體**：它變短，那組正控就少驗了幾種，\n"
            "   而**測試照樣全綠**。要刪請同步改上面的下限，並在 PR 描述寫明刪了哪一筆、為什麼。")


def test_control_C_a_hard_wrapped_continuation_is_not_a_sentence_head():
    """負控：上一行沒把話講完 ⇒ 下半行的第一個詞**不是**句首 ⇒ (C) 不抓。

    ⛔ **這就是第十二輪那 5 筆「硬換行假句首」登記的成因。** 在本輪之前
    `split_segments` 是純逐行切段，這一句必定命中 —— 而 `docs/v2/prototype/` 的
    線框整份是手寫 HTML、整份都在硬換行。
    """
    for head in _UNIVERSAL_HEADS:
        doc = _cont_doc(_CONT_UNFINISHED_HEAD, head)
        assert find_universals_without_reverse_check(_DEMO, doc) == [], \
            f"負控失效：硬換行的下半截被當成句首斷言（{doc!r}）"


def test_control_C_the_same_sentence_after_a_finished_line_still_fires():
    """正控：**同一句話**，只要上一行把話講完了就照抓 —— 每一種收尾機制逐個驗。"""
    for head in _UNIVERSAL_HEADS:
        for why, first, _pred in _CONT_FINISHED_HEADS:
            doc = _cont_doc(first, head)
            assert len(find_universals_without_reverse_check(_DEMO, doc)) == 1, \
                f"正控失效：上一行已經以「{why}」收尾，下一行卻沒被當成句首（{doc!r}）"


def test_control_C_a_new_block_on_this_line_always_restarts_the_sentence():
    """正控：上一行沒講完，但**這一行自己開了新區塊** ⇒ 照抓（打 `_starts_a_new_block`）。"""
    for head in _UNIVERSAL_HEADS:
        for why, prefix, _pred in _CONT_BLOCK_STARTS:
            doc = f"{_CONT_UNFINISHED_HEAD}\n{prefix}{head}{_CONT_TAIL}"
            assert len(find_universals_without_reverse_check(_DEMO, doc)) == 1, \
                f"正控失效：這一行以「{why}」開了新區塊，卻被當成續行（{doc!r}）"


# 「關掉某一條述詞」要怎麼關 —— **標籤 → (全域名, 關掉後的值)**。
# ⚠️ **同一個全域可以有兩種關法**，而且必須分開：`_SENTENCE_END_CHARS` 整個清空，
#    驗的是「有沒有句末字表」；退回第十二輪那六個字元，驗的是「**本輪補的七個字元**」。
#    只用前一種，本輪補的那幾個字元就沒有任何正控 —— 那正是 G3 在講的病。
_PREDICATE_KILL: dict[str, tuple[str, object]] = {
    "句末字表整個關掉": ("_SENTENCE_END_CHARS", ""),
    "句末字表退回第十二輪": ("_SENTENCE_END_CHARS", "。！？!?；;"),
    "_CLAUSE_END_CHARS": ("_CLAUSE_END_CHARS", ""),
    "_TRAILING_MARKUP": ("_TRAILING_MARKUP", ""),
    "_SELF_CONTAINED_LINE": ("_SELF_CONTAINED_LINE", re.compile(r"(?!x)x")),
    "_MD_BLOCK_START": ("_MD_BLOCK_START", re.compile(r"(?!x)x")),
    "_INLINE_TAGS": ("_INLINE_TAGS", frozenset(_INLINE_TAGS | {"td", "tr"})),
}


def _with_predicate_killed(label: str):
    """把某一條述詞換成它的「關掉」版本，離開時還原。"""
    name, value = _PREDICATE_KILL[label]

    class _Kill:
        def __enter__(self):
            self.original = globals()[name]
            globals()[name] = value
            return self

        def __exit__(self, *_exc):
            globals()[name] = self.original
            return False
    return _Kill()


def test_control_every_predicate_kill_switch_is_wired():
    """每一個「關掉」標籤都必須真的指到一個存在的全域，而且真的換掉它的值。

    ⚠️ 沒有這一條，上面那整組突變可以靠一個打錯的標籤靜默失效（同 G7 的形狀）。
    """
    assert _PREDICATE_KILL, "關法表是空的 —— 上面那整組突變正在空轉"
    used = {p for _w, _f, p in _CONT_FINISHED_HEADS} | {p for _w, _f, p in _CONT_BLOCK_STARTS}
    assert used <= set(_PREDICATE_KILL), f"這些標籤沒有登記關法：{sorted(used - set(_PREDICATE_KILL))}"
    for label, (name, value) in _PREDICATE_KILL.items():
        assert name in globals(), f"`{label}` 指到不存在的全域 `{name}`"
        assert globals()[name] != value, (
            f"`{label}` 的『關掉值』與現值相同 —— 這個關法什麼都沒關掉")


def test_mutation_each_finished_head_is_pinned_to_its_own_predicate():
    """突變：逐列關掉**它自己登記的那條述詞** → 那一列必須轉啞。

    ⛔ **這一條是 G3 的核心。** 在它之前，`_SELF_CONTAINED_LINE`／`_CLAUSE_END_CHARS`／
    `_MD_BLOCK_START`／`_TRAILING_MARKUP` **四條述詞拿掉之後 58 條測試 0 紅** ——
    有註解、有理由、**沒有守衛**。而本檔的第一句話就是「**綠燈而沒有正控 ＝ 沒有檢查**」。
    ⚠️ **一次只關一條、其餘原封不動**，這樣轉啞才只能歸因於那一條。
    """
    for why, first, pred in _CONT_FINISHED_HEADS:
        with _with_predicate_killed(pred):
            for head in _UNIVERSAL_HEADS:
                doc = _cont_doc(first, head)
                assert find_universals_without_reverse_check(_DEMO, doc) == [], (
                    f"關掉 `{pred}` 之後，「{why}」那一列**仍然命中** ——\n"
                    f"  它不是靠那條述詞成立的（被別的分支攔截了），這條正控沒有鑑別力。\n"
                    f"  樣本：{doc!r}")
    for why, prefix, pred in _CONT_BLOCK_STARTS:
        with _with_predicate_killed(pred):
            for head in _UNIVERSAL_HEADS:
                doc = f"{_CONT_UNFINISHED_HEAD}\n{prefix}{head}{_CONT_TAIL}"
                assert find_universals_without_reverse_check(_DEMO, doc) == [], (
                    f"關掉 `{pred}` 之後，開頭是「{why}」那一列**仍然命中** —— 沒有鑑別力。\n"
                    f"  樣本：{doc!r}")


def test_control_C_a_blank_line_always_restarts_the_sentence():
    """正控：中間隔一個空白行 ⇒ 段落界 ⇒ 照抓（上一行講完沒講完都一樣）。"""
    for head in _UNIVERSAL_HEADS:
        doc = _cont_doc(_CONT_UNFINISHED_HEAD + "\n", head)
        assert len(find_universals_without_reverse_check(_DEMO, doc)) == 1, \
            f"正控失效：空白行沒有把承接關係切斷（head={head!r}）"


# HTML5 裡**不是** phrasing content 的元素名，逐一列出（下方封閉性測試的母體）。
# ⚠️ **刻意窮舉，不取樣** —— 理由與 `test_control_C_word_boundary_predicate_is_a_closed_set`
#    的 docstring 逐字相同：**一個抽樣式的封閉性檢查，本身就是一張開放清單**。
#    第十輪已經為 `_CJK` 踩過這個坑並改成逐碼位窮舉；本表是同一個處方換一個對象。
_BLOCK_LEVEL_TAGS: frozenset[str] = frozenset("""
    address article aside blockquote body caption col colgroup dd details dialog div dl dt
    fieldset figcaption figure footer form h1 h2 h3 h4 h5 h6 head header hgroup hr html
    iframe legend li main menu nav noscript ol optgroup option p pre search section
    select style summary table tbody td textarea tfoot th thead tr ul
""".split())


def test_control_inline_tag_table_is_closed_against_block_tags():
    """封閉性：**任何一個區塊級標籤名都不得混進 `_INLINE_TAGS`**，而且逐一驗它被判成區塊。

    ⚠️ **2026-09-23 第十三輪回修（G5；決策者 客戶）——本條原本是抽樣，不是封閉集。**
    舊版硬寫 6 個名字（`td` `li` `p` `div` `section` `zzcustomtag`）。稽核逐一毒化
    **它沒點名的**區塊標籤：`td` 會紅，但 `tr`／`blockquote`／`h2`／`figure`／`tbody`／
    `dd`／`article` **全部綠** —— 也就是那條測試只守得住它自己寫下的那六個字。
    ⛔ **這正是本檔第十輪自己記過的教訓的再犯**（見
    `test_control_C_word_boundary_predicate_is_a_closed_set` 的 docstring）。
    ✅ 現改為對 `_BLOCK_LEVEL_TAGS` **逐一窮舉**。
    ⚠️ **極性照舊**：行內表漏收一個名字 ⇒ 該標籤被判區塊 ⇒ **多紅**（吵，看得見）；
    收錯一個（把區塊標籤寫進來）⇒ **無聲漏抓**。**只准往「漏收」那邊錯。**
    ✅ **現況是對的**：本輪逐一比對過，34 個成員裡沒有任何區塊級標籤。
    """
    assert _BLOCK_LEVEL_TAGS, "區塊標籤母體是空的 —— 這條封閉性檢查正在空轉"
    intruders = sorted(_BLOCK_LEVEL_TAGS & _INLINE_TAGS)
    assert not intruders, (
        f"這些**區塊級**標籤被收進 `_INLINE_TAGS`：{intruders}\n"
        "⚠️ 後果是**無聲漏抓**：以它們開頭的行不再被當成新區塊，整句會被判成續行、"
        "(C) 從此看不到它，而三道檢查照樣全綠。")
    for name in sorted(_BLOCK_LEVEL_TAGS):
        assert _starts_a_new_block(f'  <{name} class="x">文字'), \
            f"<{name}> 沒有被當成區塊開頭"
        assert _starts_a_new_block(f"  </{name}>文字"), \
            f"</{name}> 沒有被當成區塊開頭"
    for name in ("zzcustomtag", "my-widget", "x1"):
        assert _starts_a_new_block(f"  <{name}>文字"), \
            f"不認得的標籤 <{name}> 必須當成區塊（極性：寧可多紅）"
    for name in sorted(_INLINE_TAGS):
        assert not _starts_a_new_block(f"  <{name}>文字"), \
            f"<{name}> 被當成區塊開頭 —— 行內表沒有被讀到"


def test_control_block_tag_table_is_not_silently_shrinkable():
    """`_BLOCK_LEVEL_TAGS` 少掉任何一個常見容器就紅 —— 擋「把母體改小來變綠」。"""
    must = {"tr", "td", "th", "thead", "tbody", "table", "li", "ul", "ol", "p", "div",
            "section", "article", "blockquote", "figure", "figcaption", "dd", "dt", "dl",
            "h1", "h2", "h3", "h4", "h5", "h6", "header", "footer", "main", "nav", "form"}
    missing = sorted(must - _BLOCK_LEVEL_TAGS)
    assert not missing, (
        f"`_BLOCK_LEVEL_TAGS` 少了：{missing}\n"
        "⚠️ 母體變小，上面那條封閉性檢查就少驗幾個名字，**而它照樣全綠**。")


def _live_keys(section: str) -> set[str]:
    return {f.key for f in collect(section)}


def _without_continuation_rule():
    """把續行判定關掉（一律回「不是續行」）—— 突變測試與語料正控**共用同一個開關**。"""
    class _Off:
        def __enter__(self):
            global _is_continuation
            self.original = _is_continuation
            _is_continuation = lambda *_a, **_k: False       # noqa: E731
            return self

        def __exit__(self, *_exc):
            global _is_continuation
            _is_continuation = self.original
            return False
    return _Off()


def test_mutation_disabling_the_continuation_rule_turns_the_control_red():
    """突變：關掉續行判定 → 上面的負控**必須**開始命中（否則它沒有鑑別力）。"""
    with _without_continuation_rule():
        for head in _UNIVERSAL_HEADS:
            doc = _cont_doc(_CONT_UNFINISHED_HEAD, head)
            assert len(find_universals_without_reverse_check(_DEMO, doc)) == 1, \
                f"關掉續行判定之後仍然不命中 —— 負控抓的不是這一項（{doc!r}）"
    for head in _UNIVERSAL_HEADS:
        assert find_universals_without_reverse_check(
            _DEMO, _cont_doc(_CONT_UNFINISHED_HEAD, head)) == [], "突變後沒有還原續行判定"


def test_mutation_treating_everything_as_a_continuation_silences_the_positive_control():
    """突變（反方向）：把**每一行**都當成續行 → 正控必須全部啞掉。

    ⚠️ **兩個方向都要測**：只測「關掉會轉紅」證明不了旗標真的被讀。
    一個永遠回 `True` 的判定會讓 (C) 對**整份語料**停止檢查 ——
    那是本檔最危險的失效模式（綠燈而少看），這一條讓它當場可見。
    """
    global _is_continuation
    original = _is_continuation
    try:
        _is_continuation = lambda *_a, **_k: True            # noqa: E731
        for head in _UNIVERSAL_HEADS:
            for _why, first, _pred in _CONT_FINISHED_HEADS:
                assert find_universals_without_reverse_check(
                    _DEMO, _cont_doc(first, head)) == [], \
                    "把所有行都當成續行之後，正控仍然命中 —— `initial` 根本沒有被讀"
    finally:
        _is_continuation = original
    assert _is_continuation is original, "沒有還原續行判定"


def test_control_continuation_rule_can_only_remove_findings_from_the_corpus():
    """語料正控：續行判定在**真的語料**上只能讓 (C) 少抓，且 (A)／(B) 逐筆不動。

    ⚠️ **這一條問的是「本輪這一項改動有沒有越界」，答案不隨文件編輯漂移** ——
    所以它刻意不寫死任何一個數字（同
    `test_control_leading_tag_stripping_leaves_the_markdown_corpus_untouched` 的理由）。
    """
    with_rule = {section: _live_keys(section) for section, _ in CHECKS}
    with _without_continuation_rule():
        without_rule = {section: _live_keys(section) for section, _ in CHECKS}
    for section in (SEC_COUNTS, SEC_SELFSCAN):
        assert with_rule[section] == without_rule[section], (
            f"續行判定動到了 `{section}` —— 它只該被 (C) 讀到。\n"
            f"  多出來：{sorted(with_rule[section] - without_rule[section])[:3]}\n"
            f"  不見了：{sorted(without_rule[section] - with_rule[section])[:3]}")
    added = with_rule[SEC_UNIVERSALS] - without_rule[SEC_UNIVERSALS]
    assert not added, (
        f"續行判定讓 (C) **多**抓了 {len(added)} 筆：{sorted(added)[:5]}\n"
        "⚠️ 這在設計上不可能 —— 它只是一個 `continue`。多出來代表有人改了別的東西。")


# ⚠️ **逐筆釘死本輪處置的那幾句 —— 沒有這一條，上面全部是合成字串的自說自話。**
#    左邊是「本輪判定為硬換行假句首、因此 (C) 不再抓」的 baseline 登記；
#    右邊是「同一批 `why_safe` 裡**不同型**、本輪**仍然照抓**」的那幾筆。
# ⚠️ **右邊那一筆 `exp` 就是第十二輪稽核登記的「與另外四筆不同型」** ——
#    它的前一行是**已閉合的 `</td>`**（同列另一欄），它**真的是格首**；
#    第十二輪那條「前一個非空白行未結句」的人工判準在它身上量測通過、結論卻不成立。
#    本輪的機器判定與該筆稽核結論一致：**它沒有被放過。**
# ⛔ **這張表不得為了讓測試變綠而修改** —— 它若對不上，代表判定或文件真的變了，
#    那時要重新量測並在 PR 描述寫明，不是改這裡。
# ⚠️ **2026-09-23 第十三輪回修（G1）：`d41a42259834605e` 由本表移到下表。**
#    它的上一行以 `）` 收尾，而 `）` 本輪被補進句末字表 ⇒ **它不再是「被放過」，是「照抓」**。
#    **不是它的文字改了，是判定改了** —— 移動本身就是簽名承認這一點。
_CONTINUATION_SUPPRESSED: tuple[tuple[str, str], ...] = (
    ("79affb5d58c35bdb", "docs/v2/prototype/ui_prototype_alo.html"),
    ("52eb0ab98c2a8f11", "docs/v2/prototype/ui_prototype_set.html"),
    ("f6d519139e040390", "docs/v2/prototype/ui_prototype_today.html"),
)
_CONTINUATION_STILL_CAUGHT: tuple[tuple[str, str], ...] = (
    ("547b52442a9fe27e", "docs/v2/prototype/ui_prototype_exp.html"),
    ("32e87333a4be75f8", "docs/v2/prototype/ui_prototype_hld.html"),
    ("40500ae0a577b551", "docs/v2/prototype/ui_prototype_hld.html"),
    ("d41a42259834605e", "docs/v2/prototype/ui_prototype_today.html"),
)


def test_control_the_registered_fake_sentence_heads_are_the_ones_that_went_quiet():
    """語料正控（逐筆）：該安靜的安靜了、該照抓的照抓 —— 而且**安靜是這一項造成的**。

    三個斷言缺一不可：
      1. 開著規則時，`_CONTINUATION_SUPPRESSED` 那幾筆**不在**命中集合裡；
      2. **關掉規則時它們全部回來** —— 這一條才證明安靜來自本項改動，
         而不是有人把那幾行文字編輯掉了（兩者在測試輸出上長得一模一樣）；
      3. `_CONTINUATION_STILL_CAUGHT` 那幾筆**開著規則也照樣命中**。
    """
    live = _live_keys(SEC_UNIVERSALS)
    for key, doc in _CONTINUATION_SUPPRESSED:
        assert key not in live, (
            f"[{key}] {doc} 仍然被 (C) 當成句首斷言 —— 續行判定沒有涵蓋它")
    for key, doc in _CONTINUATION_STILL_CAUGHT:
        assert key in live, (
            f"[{key}] {doc} 不再命中 —— 它**不是**硬換行假句首（`exp` 那一筆是格首、\n"
            "`hld` 那兩筆是 44 逐字引述），本輪不該把它放過。\n"
            "若那幾行文字真的被改了，請重新量測並在 PR 描述寫明，**不要改這張表**。")
    with _without_continuation_rule():
        back = _live_keys(SEC_UNIVERSALS)
    for key, doc in _CONTINUATION_SUPPRESSED:
        assert key in back, (
            f"[{key}] {doc} 關掉續行判定之後**沒有**回來 —— 它的安靜不是本項造成的，\n"
            "這條正控因此沒有鑑別力（那幾行文字可能已經被編輯掉了）。")


# ── (C) 行首裝飾：第十二輪登記的五種漏網形狀（第十三輪客戶裁示第 2 件）─────────
# ⚠️ **五種逐一具名、逐一配一條突變** —— 只驗「現在抓得到」證明不了是哪一項在抓。
#    每一列是 `(這是什麼形狀, 前綴, 負責的那一個 part)`。
_ESCAPED_SHAPES: tuple[tuple[str, str, str], ...] = (
    ("半形雙引號開頭", '"', _LEADING_QUOTE_OR_COLON),
    ("全形冒號開頭", "：", _LEADING_QUOTE_OR_COLON),
    ('屬性值裡有 `>`', '<td title="a>b">', _LEADING_HTML_TAG),
    ('屬性值裡有 `<`', '<td title="a<b">', _LEADING_HTML_TAG),
    ("跨行標籤的下半截", '    title="y">', _LEADING_TAG_TAIL),
)


def test_control_C_the_five_registered_escape_shapes_are_now_caught():
    """正控：第十二輪登記的五種形狀，現在**逐一**抓得到。"""
    for why, prefix, _part in _ESCAPED_SHAPES:
        for head in _UNIVERSAL_HEADS:
            doc = f"{prefix}{head}{_TAG_CONTROL_TAIL}"
            assert len(find_universals_without_reverse_check(_DEMO, doc)) == 1, \
                f"正控失效：「{why}」仍然逃得掉（{doc!r}）"


def test_mutation_removing_each_new_furniture_part_turns_its_shape_red():
    """突變：逐一拿掉負責的那一個 part → 對應的形狀**必須**重新逃掉。

    ⚠️ **一次只拿掉一項、其餘原封不動** —— 這樣啞掉才只能歸因於那一項
    （體例同 `test_mutation_removing_the_leading_tag_rule_turns_the_control_red`）。
    ⚠️ **兩種舊形狀（`"` 與 `：`）共用同一個 part**，所以拿掉它會讓兩種一起啞掉，
    這是預期的，不是測試寫鬆了。
    """
    global _LEADING_FURNITURE
    original = _LEADING_FURNITURE
    for why, prefix, part in _ESCAPED_SHAPES:
        try:
            _LEADING_FURNITURE = _furniture_re(
                tuple(x for x in _LEADING_FURNITURE_PARTS if x != part))
            for head in _UNIVERSAL_HEADS:
                doc = f"{prefix}{head}{_TAG_CONTROL_TAIL}"
                assert find_universals_without_reverse_check(_DEMO, doc) == [], (
                    f"拿掉負責「{why}」的那一項之後仍然抓得到（{doc!r}）——\n"
                    "正控抓的不是那一項，沒有鑑別力")
        finally:
            _LEADING_FURNITURE = original
    assert _LEADING_FURNITURE is original, "沒有還原 `_LEADING_FURNITURE`"


# 一個**必須交替剝**才看得到第一個實字的樣本：標籤 → 全形開引號 → 半形雙引號 →
# 全形冒號 → markdown 強調。**任何「依序各剝一次」的寫法都會在中途停住。**
_ALTERNATION_SAMPLE_PREFIX = '<td title="a>b">「"：**'


def test_control_normalize_alternates_between_furniture_parts():
    """正控：行首裝飾的**各 part 之間必須交替剝**，不是「每一項依序各剝一次」。

    ⚠️ **2026-09-23 第十三輪就地更名與更正（G11）**：本條原名
    ~~`test_control_normalize_strips_to_a_fixpoint_not_one_pass`~~，
    名字與 docstring 都讓人以為它在守 `normalize` 的**外層 `while` 迴圈**。**它不是。**
    **實測**：把外層迴圈換成第十二輪的寫法，全語料 58,143 個句段**輸出差異 0**，
    而本條**照樣綠**（它的樣本不依賴那個迴圈）。
    **它真正守的、而且真的守得住的**，是 `_LEADING_FURNITURE` 那個 `^(?:…)+` 裡
    **各 part 之間的交替** —— 標籤 → 全形開引號 → 半形雙引號 → 全形冒號 → 強調符號，
    疊五層時任何「依序各剝一次」的寫法都會在中途停住。
    ⛔ **第十二輪就是栽在這裡**：那一輪把剝標籤寫成「收尾補一刀」，
    `<td>「…` 這種「標籤 ＋ 開引號」剝完標籤就停住，整批漏掉（該輪續記寫著差 2 句）。
    ⚠️ **鑑別力的射程，誠實寫明**：突變體（逐 part 依序各剝一次）**對應的是第十二輪真的寫過的形狀**，
    不是憑空造的；但它**不**對應「拿掉外層 `while`」那一種改法 —— 那一種今天**量不出差別**。
    ⚠️ **突變體刻意用 `_LEADING_FURNITURE_PARTS` 本體組裝，不重打 regex** ——
    重打的那一份會與本體無聲分家，那條突變就永遠證不了東西。
    """
    def strip_once_in_order(text: str) -> str:
        for part in _LEADING_FURNITURE_PARTS:
            text = re.compile("^(?:" + part + ")+").sub("", text)
        return text

    for head in _UNIVERSAL_HEADS:
        sample = f"{_ALTERNATION_SAMPLE_PREFIX}{head}{_TAG_CONTROL_TAIL}"
        assert normalize(sample).startswith(head), (
            f"剝到不動為止之後仍然看不到第一個實字：{normalize(sample)!r}")
        assert len(find_universals_without_reverse_check(_DEMO, sample)) == 1, \
            f"正控失效：疊了五層裝飾的句首全稱斷言逃掉了（{sample!r}）"
        once = strip_once_in_order(sample)
        assert not once.startswith(head), (
            "「依序各剝一次」竟然也剝乾淨了 —— 這個樣本沒有鑑別力，"
            f"請換一個真的需要交替剝的形狀（得到 {once!r}）")


def test_control_normalize_never_eats_into_a_number():
    """正控（G6）：行首剝除**不得吃進一個數字的中間**。

    ⛔ **成因（實證，非預防）**：行首序號規則原寫 `\\d+[.)]`，**沒有要求後面接空白**。
    於是 `### 3.2 退場順序…` 的 `3.` 被當成清單序號吃掉，正規化結果變成 `2 退場順序…`
    —— **節號被吃掉一半**。本輪新加的「剝行首半形雙引號」又替它開了一條新路徑：
    `"31.0" : …` 剝掉引號後曝出 `31.`，結果變成 `0" : …`。
    **兩者是同一個 bug 的兩條入口。**
    ⚠️ **這個 bug 不是本輪造出來的** —— 本組拿 `ce2d307`（本輪一個字都沒改的 HEAD）
    上的守衛對同一份語料重跑，**當時就有 257 個句段被吃進數字中間**；
    本輪只是讓它多了一條路徑、並且第一次被看見。
    ⚠️ **三道檢查原本沒有一道看得見它**：兩種寫法都是不動點（不動點測試看不到）、
    都不改變 (C) 的命中集合、而 `test_control_leading_tag_stripping_leaves_the_markdown_corpus_untouched`
    只驗 `.md` 那一側、而且只針對 `_LEADING_HTML_TAG`。**本條是專門為它開的那隻眼睛。**
    """
    for text, must_keep in (('"31.0" : (g.rc === "0（示意）"', "31.0"),
                            ("### 3.2 退場順序", "3.2"),
                            ("1.75（示意）", "1.75"),
                            ("- 12.3 節的那一行", "12.3")):
        out = normalize(text)
        assert out.startswith(must_keep), (
            f"{text!r} 正規化成 {out!r} —— {must_keep!r} 這個數字被吃掉了一半")
    # 正向對照：真的是清單序號（後面接空白）**必須**照剝，否則本條變成「什麼都不剝」
    for text, want in (("1. 項目內容", "項目內容"), ("(1) 項目內容", "項目內容"),
                       ("3) 項目內容", "項目內容")):
        assert normalize(text) == want, f"{text!r} 的清單序號沒有被剝掉（剝過頭的反方向）"

    # 語料層：行首剝除是**前綴**操作（正規表示式錨在 `^`），所以可以逐段還原出被剝掉的前綴。
    # ⚠️ **刻意只跑 `_LEADING_FURNITURE`、不跑 `_EMPHASIS`** —— 後者會刪掉字串**中間**的
    #    反引號，`len` 差就不再等於前綴長度（本組第一版正是這樣寫的，當場誤報 200+ 筆）。
    bad = []
    for doc_rel, doc in iter_docs():
        for seg in split_segments(doc):
            rest, prev = seg.live, None
            while prev != rest:
                prev = rest
                rest = _LEADING_FURNITURE.sub("", rest)
            prefix = seg.live[: len(seg.live) - len(rest)]
            if re.search(r"\d[.)]$", prefix) and rest[:1].isdigit():
                bad.append((doc_rel, seg.line, seg.live[:60], rest[:60]))
    assert not bad, (
        f"有 {len(bad)} 個句段的行首剝除吃進了數字中間，前三筆：\n  "
        + "\n  ".join(f"{d}:{ln}\n    原 {a!r}\n    剝後 {b!r}" for d, ln, a, b in bad[:3])
        + "\n⚠️ 成因多半是行首序號規則少了「後面必須接空白」那個 lookahead。")


def test_mutation_dropping_the_ordinal_lookahead_turns_the_number_control_red():
    """突變：把序號規則退回 `\\d+[.)]`（沒有 lookahead）→ 上一條必須轉紅。"""
    global _LEADING_FURNITURE
    original = _LEADING_FURNITURE
    try:
        _LEADING_FURNITURE = _furniture_re(tuple(
            r"\d+[.)]" if p_.startswith(r"\d+[.)]") else p_
            for p_ in _LEADING_FURNITURE_PARTS))
        assert normalize("### 3.2 退場順序") != "3.2 退場順序", \
            "突變之後節號竟然沒有被吃掉 —— 這條突變沒有鑑別力"
        assert normalize('"31.0" : x') != '31.0" : x', "突變之後數字竟然沒有被吃掉"
    finally:
        _LEADING_FURNITURE = original
    assert normalize("### 3.2 退場順序") == "3.2 退場順序", "突變後沒有還原剝除式"


def test_control_normalize_is_a_fixpoint_over_the_corpus():
    """正控（語料層）：`normalize` 對**真的語料**是冪等的 —— 再剝一次不會再變。

    ⚠️ 上一條用的是合成樣本；這一條把整份 `docs/v2/` 的每一個句段都餵進去。
    **一個不是不動點的正規化，會讓同一句話在不同呼叫路徑上得到不同的 key**，
    而 key 就是 baseline 的身分證。
    """
    bad = []
    for doc_rel, doc in iter_docs():
        for seg in split_segments(doc):
            if normalize(seg.text) != seg.text:
                bad.append((doc_rel, seg.line, seg.text, normalize(seg.text)))
    assert not bad, (
        f"`normalize` 在 {len(bad)} 個句段上不是不動點，前三筆：\n  "
        + "\n  ".join(f"{d}:{ln}\n    once={a!r}\n    twice={b!r}" for d, ln, a, b in bad[:3]))


# ── 射程正控：那五個線框草稿**真的被讀到了** ──────────────────────────
# ⚠️ **沒有正控的綠燈 ＝ 沒有檢查。** 把 `prototype/*.html` 加進 `DOCS_GLOBS` 之後，
#    三道檢查對它們的命中數可能很低（**`edc9319` 實測 (A)0／(B)0／(C)3**）——
#    **低命中與「根本沒讀到」在測試輸出上長得一模一樣**。下面兩條把兩者分開。
# ⚠️ **那三個數字原本沒有釘 SHA，而它已經漂掉了**（2026-09-23 第十一輪回修就地補釘）：
#    同輪另一組把線框裡那 3 句全稱斷言改成刪除線之後，**工作樹上 (C) 已經是 0**。
#    釘 SHA 是本檔自己對 `docs/v2/` 開的第一條規則（客戶裁示第 1 條），
#    **守衛自己的註解不釘，就沒有立場要求任何人。** 引用這三個數字前請現場重量。
_PROTOTYPE_DIR = "docs/v2/prototype/"
# 這五個檔的內容長度下限 —— 用來擋「讀到了，但讀進來的是空字串」。
# **單位是字元**，因為被比較的量是 `len(doc)`（`str` 的長度），不是檔案的 bytes。
# ⚠️ **2026-09-23 第十一輪回修（有意識的更正，不是漏刪 · 決策者 AI 總管）**：
#    本常數原名 ~~`_PROTOTYPE_MIN_BYTES`~~、理由也用 bytes 寫（「8 萬 bytes 以上」），
#    **但斷言從第一天起比的就是字元數** —— `CLAUDE.md` §4.1 命名規範明文要求
#    變數名編碼單位，而這裡名、理由、被比較的量**三者是兩種單位**。
#    **結論沒有被推翻，錯的是援引的證據**：五個之中最短的 `ui_prototype_today.html`
#    實測 87,147 bytes ／ **67,258 字元**（量測日 2026-09-23；**這兩個數字會漂移，
#    要用請現場量**）⇒ 安全邊際是 **1.35×**，不是拿 bytes 算出來的 1.74×。
_PROTOTYPE_MIN_CHARS = 50000


def test_control_scope_really_includes_the_prototype_wireframes():
    """正控：五個線框 HTML 真的進了受檢清單，而且真的被切出句段。"""
    docs = dict(iter_docs())
    protos = sorted(d for d in docs if d.startswith(_PROTOTYPE_DIR))
    assert len(protos) >= 5, (
        f"只看到 {len(protos)} 個線框草稿：{protos}\n"
        "`DOCS_GLOBS` 的 `prototype/*.html` 那一列失效了 —— 三道檢查對它們靜默停擺。")
    for d in protos:
        live = [s for s in split_segments(docs[d]) if not s.struck]
        assert len(live) > 100, f"{d} 只切出 {len(live)} 個句段 —— 讀到了但沒真的解析"


# ── 射程正控之二：釘的是**身分**，不是個數 ────────────────────────────────
# ⚠️ **上面那一條與逐 glob 下限都只數個數，擋不住「換人」。** 第十一輪稽核指出的路徑：
#    先新增第六個線框（這個 repo 一定會發生），再把其中一個搬走或改副檔名 ⇒
#    **檔數仍是 5、逐 glob 下限照樣過**，而剛修過的那一個已經整個離開語料。
#    隔離副本實測（補進去的那一個取既有線框的副本）：`--report` 與正常狀態 `diff` 無差異
#    ⇒ **這支守衛不會發出任何訊號。**
# ⛔ **期望值刻意逐字硬寫，不得改成從 `DOCS_GLOBS`／目錄列表推導** ——
#    那樣「改設定」與「改期望」會同一個動作完成，防線當場失效（＝沒有期望值）。
# ✅ 正解：真的要換掉哪一個，就來改這個 tuple —— **改它本身就是簽名承認換掉了哪一個。**
_PROTOTYPE_FILES: tuple[str, ...] = (
    "docs/v2/prototype/ui_prototype_alo.html",
    "docs/v2/prototype/ui_prototype_exp.html",
    "docs/v2/prototype/ui_prototype_hld.html",
    "docs/v2/prototype/ui_prototype_set.html",
    "docs/v2/prototype/ui_prototype_today.html",
)


def _prototype_files_in_scope() -> list[str]:
    """受檢清單裡屬於線框那一側的檔（repo 相對路徑）。

    ⚠️ **只走 `scoped_paths()` ＋ `_matches_glob`，不自己掃磁碟** —— 理由同 `_md_docs_in_scope()`：
    自己掃一套會分家成「清單看得到、三道檢查沒讀到」。
    ⚠️ 這裡的 `"prototype/*.html"` 是**挑語料的哪一側**，不是期望值；
    期望值只有 `_PROTOTYPE_FILES` 一份。
    """
    return sorted(str(p.relative_to(REPO_ROOT)).replace("\\", "/")
                  for p in scoped_paths()
                  if _matches_glob(_rel_to_docs(p), "prototype/*.html"))


def _named_wireframes_diff(seen: set[str]) -> tuple[list[str], list[str]]:
    """回 (清單有、語料沒有, 語料有、清單沒有) —— 正控與突變測試**共用同一個判定**。

    ⚠️ **第十三輪把第二個方向補上**（客戶 2026-09-23 裁示第 5 件）：
    本函式原名 ~~`_named_wireframes_missing_from`~~、**只回「少了誰」**，
    於是「**新增一個沒登記的線框**」這件事在本側完全沒有訊號。
    """
    missing = [f for f in _PROTOTYPE_FILES if f not in seen]
    unexpected = sorted(d for d in seen if d not in _PROTOTYPE_FILES)
    return missing, unexpected


def test_control_each_named_wireframe_is_still_in_scope_by_name():
    """正控：五個線框**逐個具名**都還在受檢清單裡，而且沒有沒登記的檔混進來。"""
    missing, unexpected = _named_wireframes_diff(set(_prototype_files_in_scope()))
    assert not missing and not unexpected, (
        "`docs/v2/prototype/*.html` 的受檢清單與 `_PROTOTYPE_FILES` 對不起來：\n"
        + (f"  ⛔ 清單裡有、語料裡沒有（被搬走／改名／刪除了）：{missing}\n" if missing else "")
        + (f"  ⛔ 語料裡有、清單裡沒有（新增的線框還沒登記）：{unexpected}\n" if unexpected else "")
        + "⚠️ **檔數下限與逐 glob 下限都擋不住這兩種** —— 新增一個、搬走一個，數字一模一樣。\n"
          "怎麼修（**改 `_PROTOTYPE_FILES`，不要改這個測試**）：\n"
          "  * **新增了線框** → 把它的路徑加進 `_PROTOTYPE_FILES`。加進去就是承認\n"
          "    「我知道這一份自此納入三道檢查」—— 它身上的既有違規會當場變成新違規。\n"
          "  * **搬走／改名／刪除了線框** → 把它從 `_PROTOTYPE_FILES` 移除，**並在 PR 描述寫明去向**。\n"
          "⛔ **不得**把 `_PROTOTYPE_FILES` 改成從目錄列表推導 —— 那樣「改設定」與「改期望」\n"
          "   會由同一個動作完成，這道防線當場等於不存在。")


def test_mutation_dropping_one_named_wireframe_turns_the_identity_control_red():
    """突變：任一具名線框被別的檔頂掉 → 上一條必須轉紅，而**個數完全沒變**。

    ⚠️ 這一條證的是「釘身分」比「數個數」多抓到什麼：替換後集合大小不變
    ⇒ **只數個數的斷言看不出差別**；具名判定則會**同時**咬出
    「不見的那一個」與「沒登記的那一個」，訊息裡點名得出來。
    （集合層級的突變，不動工作樹上任何一個檔。）
    """
    seen = set(_prototype_files_in_scope())
    assert _named_wireframes_diff(seen) == ([], []), "突變前本來就對不起來 —— 先修正控"
    newcomer = f"{_PROTOTYPE_DIR}ui_prototype_newcomer.html"
    for victim in _PROTOTYPE_FILES:
        mutated = (seen - {victim}) | {newcomer}
        assert len(mutated) == len(seen), "替換後個數就該不變，否則這條突變測不到東西"
        missing, unexpected = _named_wireframes_diff(mutated)
        assert missing == [victim], f"拿掉 {victim} 之後具名判定沒有咬它 —— 這條正控沒有鑑別力"
        assert unexpected == [newcomer], f"混進來的 {newcomer} 沒有被咬出來 —— 只驗了一個方向"


# ── 射程正控之三：31 個 `.md` 規格文件同樣釘身分（第十二輪客戶裁示第 2 件）──────
# ⚠️ **線框那一側已經釘了身分（`_PROTOTYPE_FILES`），`.md` 這一側在本輪之前只有個數下限**
#    —— 同一套劇本照樣通得過：**補一個新檔、再搬走一個真的**，檔數一模一樣、
#    逐 glob 下限不紅，而被搬走的那一份已經整個離開語料，沒有任何人會發現。
# ⛔ **清單刻意逐字硬寫，不得改成從 `DOCS_GLOBS`／目錄列表／`glob()` 推導** ——
#    推導的話「改設定」與「改期望」由同一個動作完成，期望值當場等於不存在。
# ✅ **新增文件時要有意識地把它加進這張清單**；搬走／改名／刪除時要有意識地把它移除。
#    **改這個 tuple 本身，就是簽名承認你換掉了哪一個。**
# ⚠️ **2026-09-23 第十三輪就地更正（有意識的更正，不是漏刪 · 日期 2026-09-23 · 決策者 客戶，裁示第 5 件）**：
#    ~~「**本清單比 `_PROTOTYPE_FILES` 多管一個方向（多出來的檔也紅）**，這是刻意的，不是體例不一致：~~
#    ~~客戶第 2 件要的就是『新增文件必須有意識地登記』，只驗『少了誰』擋不住清單無聲過期。~~
#    ~~線框那一側本輪**未動**（不在本輪射程內），兩邊的差別記在這裡，不要當成漏改。」~~
#    → **兩側現在都驗兩個方向，這段描述的不對稱已經不存在。**
#    **舊表述的用意仍然成立**（它要講「第二個方向是必要的，而且當時只有這一側有」——
#    那個理由一字未變，它正是本輪把另一側也補上的依據）；
#    **被權衡掉的是它的現況描述**：它把一個「**本輪還沒做到**」寫成了體例上的差別，
#    而一句寫在程式碼註解裡的現況描述，**下一輪就會過期，卻沒有任何機器看著它**。
#    ⚠️ 真正的教訓是**當時那個不對稱本身就是個缺口**：線框那一側少驗的那個方向
#    （**新增一個沒登記的線框**）在本輪之前**完全沒有訊號** —— 測試全綠，而且少看。
_MD_DOCS: tuple[str, ...] = (
    "docs/v2/01_wireframe_grp_S0-S4_Q1-Q12.md",
    "docs/v2/02_decision_grp_S5-S8.md",
    "docs/v2/03_adjudication_grp_S1-S2-S6-S8.md",
    "docs/v2/04_design_grp_S3-S4-S5-S7.md",
    "docs/v2/10_db_inventory.md",
    "docs/v2/11_contradictions_resolution.md",
    "docs/v2/20_ui_spec.md",
    "docs/v2/21_decision_log.md",
    "docs/v2/22_ui_page_today.md",
    "docs/v2/23_ui_draft_01_macro.md",
    "docs/v2/24_proposal_4a.md",
    "docs/v2/25_proposal_4b.md",
    "docs/v2/30_audit_inventory.md",
    "docs/v2/31_audit_caliber_sweep.md",
    "docs/v2/32_audit_spec_r1.md",
    "docs/v2/33_audit_spec_r2.md",
    "docs/v2/34_audit_spec_r3.md",
    "docs/v2/35_branch_strategy_check.md",
    "docs/v2/36_audit_spec_r4.md",
    "docs/v2/37_audit_spec_r5.md",
    "docs/v2/38_audit_spec_r6.md",
    "docs/v2/39_audit_spec_r7.md",
    "docs/v2/40_handover_2026-09-17.md",
    "docs/v2/41_counters.md",
    "docs/v2/42_live_dead.md",
    "docs/v2/43_ui_draft_01_macro_target.md",
    "docs/v2/44_fund_ui_ssot.md",
    "docs/v2/45_fund_db_inventory.md",
    "docs/v2/46_fund_live_dead.md",
    "docs/v2/47_fund_wireframe_mkt.md",
    "docs/v2/README_DRAFT_PACK.md",
)


def _md_docs_in_scope() -> list[str]:
    """受檢清單裡屬於 `.md` 那一側的檔（repo 相對路徑）。

    ⚠️ **只走 `scoped_paths()` ＋ `_matches_glob`，不自己掃磁碟** —— 理由同 `scope_counts()`：
    自己掃一套會分家成「清單看得到、三道檢查沒讀到」。
    ⚠️ 這裡的 `"*.md"` 是**挑語料的哪一側**，不是期望值；期望值只有 `_MD_DOCS` 一份。
    """
    return sorted(str(p.relative_to(REPO_ROOT)).replace("\\", "/")
                  for p in scoped_paths() if _matches_glob(_rel_to_docs(p), "*.md"))


def _named_md_docs_diff(seen: set[str]) -> tuple[list[str], list[str]]:
    """回 (清單有、語料沒有, 語料有、清單沒有) —— 正控與突變測試**共用同一個判定**。"""
    missing = [f for f in _MD_DOCS if f not in seen]
    unexpected = sorted(d for d in seen if d not in _MD_DOCS)
    return missing, unexpected


def test_control_each_named_md_doc_is_still_in_scope_by_name():
    """正控：31 個 `.md` **逐個具名**都還在受檢清單裡，而且沒有沒登記的檔混進來。"""
    missing, unexpected = _named_md_docs_diff(set(_md_docs_in_scope()))
    assert not missing and not unexpected, (
        "`docs/v2/*.md` 的受檢清單與 `_MD_DOCS` 對不起來：\n"
        + (f"  ⛔ 清單裡有、語料裡沒有（被搬走／改名／刪除了）：{missing}\n" if missing else "")
        + (f"  ⛔ 語料裡有、清單裡沒有（新增的檔還沒登記）：{unexpected}\n" if unexpected else "")
        + "\n怎麼修（**改 `_MD_DOCS`，不要改這個測試**）：\n"
          "  * **新增了文件** → 把它的路徑加進 `_MD_DOCS`。加進去就是承認\n"
          "    「我知道這一份自此納入三道檢查」—— 它身上的既有違規會當場變成新違規，\n"
          "    請照 `_FIX_GUIDE_A/B/C` 修，修不動才登記 baseline。\n"
          "  * **搬走／改名／刪除了文件** → 把它從 `_MD_DOCS` 移除，**並在 PR 描述寫明去向**。\n"
          "    同時檢查 baseline 裡以它為 `file` 的登記是不是該一起清掉（孤兒會在警告裡印出來）。\n"
          "⛔ **不得**把 `_MD_DOCS` 改成從目錄列表推導 —— 那樣「改設定」與「改期望」\n"
          "   會由同一個動作完成，這道防線當場等於不存在。")


def test_mutation_swapping_one_named_md_doc_turns_the_identity_control_red():
    """突變：任一具名 `.md` 被別的檔頂掉 → 上一條必須轉紅，而**個數完全沒變**。

    ⚠️ 這一條證的是「釘身分」比「數個數」多抓到什麼：替換後集合大小不變
    ⇒ **逐 glob 下限與檔數下限都看不出差別**；具名判定則會同時咬出
    「不見的那一個」與「沒登記的那一個」，訊息裡點名得出來。
    （集合層級的突變，不動工作樹上任何一個檔。）
    """
    seen = set(_md_docs_in_scope())
    assert _named_md_docs_diff(seen) == ([], []), "突變前本來就對不起來 —— 先修正控"
    newcomer = "docs/v2/99_newcomer_that_nobody_registered.md"
    for victim in _MD_DOCS:
        mutated = (seen - {victim}) | {newcomer}
        assert len(mutated) == len(seen), "替換後個數就該不變，否則這條突變測不到東西"
        missing, unexpected = _named_md_docs_diff(mutated)
        assert missing == [victim], f"拿掉 {victim} 之後具名判定沒有咬它 —— 這條正控沒有鑑別力"
        assert unexpected == [newcomer], f"混進來的 {newcomer} 沒有被咬出來 —— 只驗了一個方向"


def _docs_each_check_was_run_on() -> dict[str, list[tuple[str, int]]]:
    """把三道檢查各包一層間諜，跑一次 `collect()`，回「它實際被餵了哪些檔、各多長」。

    ⚠️ **這是射程正控的核心手法，理由寫在這裡而不是呼叫端**：
    正控原本釘的是「線框裡那句真的全稱斷言必須被 (C) 抓到」。本輪把那三句**修好了**
    ⇒ 那條正控當場永遠紅。問題在於**「修好了」與「根本沒讀到」在測試輸出上長得一模一樣**
    —— 一條會因為別人把文件修好而轉紅的正控，逼的是下一個人把正控拿掉，
    那就回到「綠燈而沒有正控」。
    **違規可以被修掉，呼叫不會** ⇒ 改釘「三道檢查有沒有真的被呼叫在那五個檔上、
    而且餵進去的是真內容」。
    """
    global CHECKS
    original = CHECKS
    seen: dict[str, list[tuple[str, int]]] = {}
    try:
        for section, fn in original:
            log: list[tuple[str, int]] = []

            def spy(doc_rel, doc, _fn=fn, _log=log):
                _log.append((doc_rel, len(doc)))
                return _fn(doc_rel, doc)

            CHECKS = tuple((s, spy if s == section else f) for s, f in original)
            collect(section)
            seen[section] = log
    finally:
        CHECKS = original
    return seen


def test_control_the_three_checks_really_run_over_the_prototype_wireframes():
    """正控：三道檢查**真的被呼叫在**那五個線框上，而且拿到的是真內容。

    ⛔ **沒有這一條，`prototype/*.html` 的 0 筆違規就沒有意義** ——
    「掃過了但很乾淨」與「根本沒掃」會印出一模一樣的 0。
    """
    seen = _docs_each_check_was_run_on()
    for section, _ in CHECKS:
        protos = [(d, n) for d, n in seen[section] if d.startswith(_PROTOTYPE_DIR)]
        assert len(protos) >= 5, (
            f"檢查 `{section}` 只被餵了 {len(protos)} 個線框草稿：{[d for d, _ in protos]}\n"
            "`DOCS_GLOBS` 的 `prototype/*.html` 那一列失效了 —— 那一批檔靜默停止檢查。")
        short = [(d, n) for d, n in protos if n < _PROTOTYPE_MIN_CHARS]
        assert not short, (
            f"檢查 `{section}` 拿到的線框內容過短（讀到了但內容不對）：{short}")


def test_mutation_narrowing_the_scope_back_turns_the_controls_red():
    """突變測試：把射程改回只看 `.md`，上面兩條正控**必須**轉紅。

    ⚠️ **這一條是「正控有沒有鑑別力」的唯一證據。** 一條永遠綠的正控與一條
    沒有正控的守衛，效果完全一樣 —— 本檔下限測試的 docstring 講的就是這件事。
    """
    global DOCS_GLOBS
    original = DOCS_GLOBS
    try:
        DOCS_GLOBS = (("*.md", 15),)
        docs = dict(iter_docs())
        assert not [d for d in docs if d.startswith(_PROTOTYPE_DIR)], \
            "射程收窄後線框草稿竟然還在 —— `DOCS_GLOBS` 沒有真的控制 `iter_docs()`"
        # ⚠️ **這裡刻意驗「呼叫」而不是「違規」**：線框裡那三句已在本輪修好，
        #    「收窄後抓不到違規」在今天是**恆真**的 —— 用它當突變證據等於沒有證據。
        #    驗呼叫則不受文件內容影響：收窄之後三道檢查**根本不會被餵到**那五個檔。
        seen = _docs_each_check_was_run_on()
        for section, _ in CHECKS:
            assert not [d for d, _n in seen[section] if d.startswith(_PROTOTYPE_DIR)], \
                f"射程收窄後 `{section}` 仍被餵了線框草稿 —— 正控抓的不是射程，沒有鑑別力"
        # 逐 glob 下限：整列被拿掉時必須紅 —— 只看總數是擋不住的。
        seen = scope_counts()
        assert "prototype/*.html" not in seen, "收窄後 `scope_counts()` 仍宣稱看得到那一列"
        assert len(docs) >= _MIN_DOCS, (
            "⚠️ 這一行是**反向證據**：收窄之後總數下限照樣過 —— "
            "證明總數下限**擋不住整列被拿掉**，逐 glob 下限不是多餘的。")
    finally:
        DOCS_GLOBS = original
    assert [d for d, _ in iter_docs() if d.startswith(_PROTOTYPE_DIR)], "突變後沒有還原射程"


def test_control_no_doc_under_the_scope_dir_escapes_every_glob():
    """正控：`docs/v2/` 底下不得有 `.md`／`.html` 落在**所有** glob 之外。

    ⚠️ glob 是非遞迴的 ⇒ **新增一層子目錄就能讓整批文件無聲逃掉**
    （稽核實測：`docs/v2/notes/x.md` 帶違規句 → 三道檢查全綠）。
    逐 glob 下限擋不住這個：它只數**射程內**的檔。
    """
    stray = sorted(_rel_to_docs(p) for p in DOCS_DIR.rglob("*")
                   if p.is_file() and p.suffix in (".md", ".html")
                   and not _in_scope(_rel_to_docs(p)))
    assert not stray, (
        f"下列檔在 `{DOCS_DIR.name}/` 底下，卻不在任何 glob 射程內 —— 三道檢查對它們完全沒看：\n"
        f"  {stray}\n"
        "請把它納入 `DOCS_GLOBS`（並同步該項下限與 `_MIN_DOCS`），"
        "或確認它本來就不該受檢、並在此就地寫明理由。")


# baseline 裡標記「第十三輪之後不再命中」的那些列所用的欄位名 —— **本檔與 baseline 共用這一個字面**。
# ⚠️ 寫成常數而不是在測試裡重打，是為了少一處要同步的字面（同 `_head_ending_with` 的理由）。
_ORPHAN_FIELD = "orphaned_since_r13"


def test_control_annotated_orphans_are_really_orphans():
    """正控：baseline 裡標為「第十三輪之後不再命中」的列，**必須真的不再命中**。

    ⚠️ **這一條是第十三輪那 10 筆註記的唯一機器守衛。** 那些列一個字都沒刪
    （刪不刪是總管的決定），但**一筆留著卻又重新命中的「孤兒」註記就是一句謊**：
    它會讓下一個人以為那句話已經不在檢查範圍內。這條讓它當場紅燈。
    ⚠️ **刻意只驗一個方向（註記 ⊆ 孤兒），不驗反向（孤兒 ⊆ 註記）** ——
    反向會讓**每一次正常的文字編輯**都紅一次（編一句已登記的話 ⇒ 舊 key 立刻變孤兒），
    理由與 `test_baseline_entries_that_no_longer_match_are_reported` 的 docstring 完全相同。
    ⚠️ **它同時是續行判定的第二層語料證據**：註記說「因為續行判定，所以不再命中」，
    而 `test_control_the_registered_fake_sentence_heads_are_the_ones_that_went_quiet`
    已經證過「關掉續行判定它們就回來」—— 兩條合起來才是完整的因果。
    """
    data = load_baseline()
    # ⚠️ **G7（第十三輪回修）**：先驗母體非空。稽核實測把 `_ORPHAN_FIELD` 打成一個
    #    不存在的欄位名 → 下面的過濾回空集合 → **全綠**，而這是那 10 筆註記的**唯一**守衛。
    annotated = [(s_, k) for s_, _ in CHECKS
                 for k, v in data[s_].items() if _ORPHAN_FIELD in v]
    assert annotated, (
        f"baseline 裡沒有任何一列帶 `{_ORPHAN_FIELD}` —— 這條正控正在空掃。\n"
        "兩種成因：(a) 欄位名被改掉或打錯了；(b) 那些註記真的被清掉了。\n"
        "若是 (b)，請連同本測試與 baseline 的 `_orphan_notes` 一起處置，不要留一條空轉的守衛。")
    for section, _ in CHECKS:
        live = {f.key for f in collect(section)}
        back = [(k, v) for k, v in data[section].items()
                if _ORPHAN_FIELD in v and k in live]
        assert not back, (
            f"baseline `{section}` 有 {len(back)} 筆標了 `{_ORPHAN_FIELD}`、卻**又命中了**：\n  "
            + "\n  ".join(f"[{k}] {v['file']}  {v['text'][:70]}" for k, v in back)
            + "\n⇒ 那筆註記現在是假的。**請回頭重判**：\n"
              "  * 若句首判定改了 ⇒ 重新量測，把註記改掉或拿掉（並在 PR 描述寫明）。\n"
              "  * 若是文件被編輯回去了 ⇒ 那句話又變成一句沒有反向檢查的全稱斷言，照 `_FIX_GUIDE_C` 修。\n"
              "⛔ **不要為了變綠就把註記刪掉** —— 註記記的是「這句話仍未附反向檢查」這個事實。")


def test_control_rebuild_refuses_to_drop_hand_written_rows():
    """正控＋突變：基準樹上少了線框 → 重建入口那道 raise 必須擋下來；完整清單不得誤擋。

    ⚠️ **只跑那道檢查，不跑 `_update_baseline`** —— 後者會寫檔。
    """
    full = [(d, "") for d, _ in iter_docs()]
    mutated = [(d, t) for d, t in full if not d.startswith(_PROTOTYPE_DIR)]   # ← 突變：模擬沒有線框的 rev
    try:
        _refuse_if_rebuild_would_drop_rows("<模擬>", mutated)
    except RuntimeError as e:
        assert _PROTOTYPE_DIR in str(e), f"訊息沒有點名被丟掉的檔：{e}"
    else:
        raise AssertionError("正控失效：會洗掉手工增補那幾筆的重建竟然沒有被擋下來")
    _refuse_if_rebuild_would_drop_rows("<模擬>", full)          # 負控：不得誤擋


def test_control_strike_tags_are_balanced_in_the_corpus():
    """正控：語料裡 `<s>`／`<del>` 必須成對、且不得自閉合 —— 沒配對會造成**過度遮罩**。

    ⚠️ `<s>…</s>` 的配對語意與 `~~` 不同：未閉合的 `<s>` 會與**後方不相干**的 `</s>` 配對，
    把中間整段當成已退役 ⇒ **無聲漏抓**。`~~` 那側有兩個上限擋著，這一側靠這條測試。
    """
    for doc_rel, doc in iter_docs():
        for tag in ("s", "del"):
            opens = len(re.findall(rf"<{tag}(?:\s[^>]*)?>", doc))
            closes = doc.count(f"</{tag}>")
            assert opens == closes, f"{doc_rel}：<{tag}> {opens} 個、</{tag}> {closes} 個 —— 不成對會過度遮罩"
            assert not re.search(rf"<{tag}(?:\s[^>]*)?/>", doc), \
                f"{doc_rel}：出現自閉合 <{tag}/>，遮罩會把它當成開標籤"


def test_control_scope_predicate_is_not_recursive_by_accident():
    """負控：`*.md` **不得**把 `prototype/` 底下的檔收進來（`fnmatch` 的 `*` 會吃掉 `/`）。"""
    assert _in_scope("41_counters.md")
    assert _in_scope("prototype/ui_prototype_set.html")
    assert not _in_scope("prototype/whatever.md"), \
        "`*.md` 把子目錄的檔收進來了 —— 非遞迴語意破了，測試端與 baseline 產生端會不一致"
    assert not _in_scope("prototype/deeper/x.html")
    assert not _in_scope("README.txt")


def test_control_scope_counts_only_counts_what_the_checks_actually_read():
    """`scope_counts()` 不得宣稱看得到 `iter_docs()` 沒有交出去的檔。

    ⚠️ **這是第十一輪必修二的看門狗。** 稽核實測過兩邊各寫一套配對的後果：
    只在射程判定多加一行排除、`DOCS_GLOBS` 一字未動 ⇒
    三道檢查實際讀到 0 個線框，`scope_counts()` 卻仍宣稱 5 個 ⇒
    **逐 glob 下限不會紅**（而逐 glob 下限正是本輪自稱最關鍵的那根釘子）。
    合併到 `scoped_paths()` 之後這個等式由結構保證；本條是防止後人再把它拆開。
    """
    docs = [d for d, _ in iter_docs()]
    counts = scope_counts()
    assert sum(counts.values()) == len(docs), (
        f"`scope_counts()` 合計 {sum(counts.values())}、`iter_docs()` 交出 {len(docs)} 個檔"
        " —— 兩邊的射程判定分家了，逐 glob 下限正在數一批沒人檢查的檔。")
    assert set(counts) == {pattern for pattern, _floor in DOCS_GLOBS}, \
        "`scope_counts()` 的 key 與 `DOCS_GLOBS` 不同步 —— 逐 glob 下限會查無此 key 而 KeyError"


def test_control_scope_predicate_matches_the_baseline_generator():
    """測試端（工作樹）與 baseline 產生端（釘死的 commit）必須看到**同一組檔**。

    ⚠️ 兩邊不一致的後果是最難查的一種：一筆違規在測試裡看得到、
    `--update-baseline` 卻產不出它 ⇒ **永遠登記不進去、永遠紅燈、沒有合法修法**。
    """
    prefix = f"{DOCS_DIR.relative_to(REPO_ROOT)}/".replace("\\", "/")
    at_head = {n for n, _ in docs_at_sha(_git("rev-parse", "HEAD").strip())}
    tracked_at_head = set(_git("ls-tree", "-r", "--name-only", "HEAD", "--", prefix).splitlines())
    from_worktree = {d for d, _ in iter_docs()}
    # **方向是單向的，這一點是刻意的**：要擋的是「測試看得到、產生端產不出來」。
    # 反方向（產生端有、工作樹沒有）在正常開發中會自然發生（有人把檔改名或刪掉還沒 commit），
    # 拿它紅燈只會製造誤紅。
    missing = (from_worktree & tracked_at_head) - at_head
    assert not missing, (
        "下列檔在測試端（工作樹）看得到，`--update-baseline` 卻產不出來：\n"
        f"  {sorted(missing)[:5]}\n"
        "⇒ 它們身上的違規**永遠登記不進 baseline**，會卡在紅燈而且沒有合法修法。\n"
        "成因一定是 `iter_docs()` 與 `docs_at_sha()` 的射程判定分了家 —— 兩邊都要走 `_in_scope`。")
    # ⚠️ **刻意不用 `git ls-files`**：那讀的是**索引**，別組新增並 stage 一個 doc
    #    就會讓這一條為了**不相干的理由**轉紅。改讀 HEAD 的樹，與產生端同一個基準。


def test_control_C_struck_through_universal_does_not_fire():
    doc = "~~所有欄位都已經查過了~~ → 2026-09-21 撤銷，見 4851465"
    assert find_universals_without_reverse_check(_DEMO, doc) == [], \
        "負控失效：被劃掉的舊全稱句不該被檢查"


def test_control_normalization_collapses_markup_but_not_wording():
    a = normalize("- **所有**　欄位　`都` 查過了")
    b = normalize("所有 欄位 都 查過了")
    assert a == b == "所有 欄位 都 查過了", f"正規化結果不如預期：{a!r} / {b!r}"
    assert normalize("所有欄位查過了") != a, "正規化不該把不同的句子壓成同一個 key"


def test_control_baseline_key_ignores_line_number_but_not_file():
    f1 = Finding("docs/v2/a.md", 10, "所有欄位都查過了")
    f2 = Finding("docs/v2/a.md", 999, "所有欄位都查過了")
    f3 = Finding("docs/v2/b.md", 10, "所有欄位都查過了")
    assert f1.key == f2.key, "key 不該隨行號改變（行號每一輪都在漂）"
    assert f1.key != f3.key, "key 必須含檔案路徑（豁免不得跨檔通用）"


# ══════════════════════════════════════════════════════════════════════════
# ⭐ 守衛自己不得違反它自己的三道規則
# ══════════════════════════════════════════════════════════════════════════
# 自我合規檢查的**唯一**豁免。體例與理由寫法沿用
# `tests/test_constitution_file_refs.py` 的 `EXEMPTIONS`：
# **理由必須說明「為什麼這個位置是對的」，不是「它長得像什麼」。**
#
# ⚠️ 只有一種東西進得來：**客戶原話的逐字引用**。
#    `CLAUDE.md` §-1.5.1／§-1.5.1a／§-1.5.1c 三處都明文寫著客戶頒布原文
#    「**不得刪改或「優化」**」。若本測試要求把客戶那句話改寫才會變綠，
#    它就是在逼人做憲法明文禁止的事 —— **那是一支壞掉的守衛**
#    （同前例對 Tier 2 裸檔名的處置理由：一條要求修改 user 逐字封存才能變綠的守衛，
#    是壞掉的守衛）。
# ⛔ **不得**把本組自己寫的句子加進來。自己的句子改寫得動，改寫就是了 ——
#    本輪就有一句（正規化規則第 3 條）是這樣改掉的，不是登記進來的。
_DOCSTRING_ALLOWED: dict[str, str] = {
    "c0b3736b72bd998b": (
        "客戶 2026-09-21 裁示第 1 條的**逐字原文**（本檔 docstring 開頭的法源引用）。"
        "它確實以那四個詞之一開頭、也確實沒有附反向檢查 —— 但它是**客戶頒布的規則本身**，"
        "不是本組對事實的斷言，本來就沒有東西可以反向檢查。"
        "而且 `CLAUDE.md` §-1.5.1／§-1.5.1a／§-1.5.1c 三處明文規定客戶原文"
        "「不得刪改或『優化』」⇒ **改寫它才能變綠是憲法禁止的解法**。"
    ),
}


def _docstring_findings() -> list[tuple[str, Finding]]:
    doc = __doc__ or ""
    out = []
    for section, fn in CHECKS:
        for f in fn("tests/test_doc_counters.py", doc):
            out.append((section, f))
    return out


def test_this_guards_own_docstring_obeys_the_three_rules():
    """本檔的**模組 docstring** 自己跑一次三道檢查，零容忍、不吃 baseline。

    **射程就是 docstring，不含檔內其餘部分 —— 這一句是界線，不是免責**：
    檔內那一整段正控／負控的字串**刻意**長成違規的樣子（那是正控的定義），
    把它們一起掃會讓本測試永遠紅。**守衛對外做的宣稱住在 docstring 裡**，
    所以那裡是零容忍的；`_DOCSTRING_ALLOWED` 是唯一的出口，而且只收客戶原話逐字引用。
    """
    doc = __doc__ or ""
    assert doc.strip(), "模組 docstring 不見了 —— 本測試會變成空掃"
    problems = [
        f"[{section}] docstring 第 {f.line} 行  [{f.key}]\n      {f.text[:140]}\n      ← {f.note}"
        for section, f in _docstring_findings() if f.key not in _DOCSTRING_ALLOWED
    ]
    assert not problems, (
        "\n本守衛的 docstring 自己違反了它自己的規則：\n    "
        + "\n    ".join(problems)
        + "\n\n⚠️ 這不是小事：本 repo 連續數輪栽在「治這個病的東西自己犯這個病」。\n"
          "   一份要求別人釘 SHA 的文件，自己的數字沒釘 SHA，就沒有立場要求任何人。\n"
          "   **修 docstring，不要改這個測試** —— 除非那句話是客戶原話逐字引用，\n"
          "   那才走 `_DOCSTRING_ALLOWED`（理由要寫清楚為什麼那個位置是對的）。")


def test_every_docstring_exemption_is_still_needed():
    """`_DOCSTRING_ALLOWED` 只能因為「現在還需要」而存在，不能因為「以前需要過」而留著。

    （體例取自 `tests/test_constitution_file_refs.py::test_every_exemption_is_still_needed`。
    豁免清單一旦可以留著沒人用的條目，就會慢慢變成一張沒有人敢動的白名單。）
    """
    live = {f.key for _, f in _docstring_findings()}
    stale = sorted(set(_DOCSTRING_ALLOWED) - live)
    assert not stale, (
        f"`_DOCSTRING_ALLOWED` 有 {len(stale)} 筆已經用不到了，請刪掉：\n  "
        + "\n  ".join(f"[{k}] {_DOCSTRING_ALLOWED[k]}" for k in stale))



# ══════════════════════════════════════════════════════════════════════════
# CLI —— 重建 baseline ／ 現況報表
# ══════════════════════════════════════════════════════════════════════════
_BASELINE_README = [
    "這是 tests/test_doc_counters.py 的 baseline —— 一份**歷史欠債登記簿**，不是豁免清單。",
    "每一筆代表：這句話在規則訂立之前就寫在那裡了，本守衛暫時不為它紅燈。",
    "登記一筆 ＝ 簽名承認「這句話現在不可重現／不可推翻，我知道」。",
    "",
    "key ＝ sha256(檔案相對路徑 + NUL + 正規化後的句子)[:16]。**刻意不含行號** ——",
    "這個 repo 的行號每一輪都在漂，那正是本守衛要治的病之一。",
    "正規化規則的權威定義在 tests/test_doc_counters.py 的模組 docstring 與 normalize()。",
    "",
    "重建：python3 tests/test_doc_counters.py --update-baseline [<rev>]（省略 <rev> ＝ HEAD）",
    "產生端讀的是 _generated_from_sha 那個 commit，不是工作樹；但自 2026-09-23 起本份是**混合來源** ——",
    "線框那 7 筆是手工增補的，該 commit 上沒有 prototype/ ⇒ 它**不能**被原樣重建。",
    "⛔ 禁止用任何 SHA 跑 --update-baseline，只准手工增補：重建會洗掉全部 why_safe 與 _why_safe_notes。",
    "（本說明 _README 本身會被原樣寫回，_why_safe_notes 不會 —— 產生端每筆只寫 file 與 text。）",
    "⛔ 重建等於承認當下**全部**違規。跑完請逐句讀 git diff 再 commit ——",
    "   那份 diff 就是你在簽名承認的東西。正解一律是先照 _FIX_GUIDE_* 修，修不動才登記。",
]


def _report() -> int:
    print(f"受檢目錄：{DOCS_DIR.relative_to(REPO_ROOT)}/")
    counts = scope_counts()
    for pattern, floor in DOCS_GLOBS:
        print(f"  glob {pattern:22s} 看到 {counts[pattern]:3d} 個檔（下限 {floor}）")
    docs = iter_docs()
    print(f"受檢檔數：{len(docs)}")
    try:
        base = load_baseline()
    except FileNotFoundError:
        base = {s: {} for s, _ in CHECKS}
        print("（baseline 尚未存在，下面的『新增』欄等同總數）")
    for section, _ in CHECKS:
        found = collect(section)
        new = [f for f in found if f.key not in base[section]]
        print(f"  {section:36s} 總命中 {len(found):4d}   已登記 {len(base[section]):4d}"
              f"   新增 {len(new):4d}")
    return 0


def _git(*args: str) -> str:
    r = subprocess.run(("git", "-C", str(REPO_ROOT)) + args,
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失敗（exit={r.returncode}）：{r.stderr.strip()}")
    return r.stdout


def docs_at_sha(sha: str) -> list[tuple[str, str]]:
    """從**釘死的 commit** 讀受檢檔，而不是讀工作樹。

    ⚠️ **這一段是本檔自己的裁示第 1 條**：baseline 是一份會被 commit 進 repo、
    被後人引用的清單 —— 它若產生自「工作樹」，就**沒有人能原樣重建它**，
    下一個人跑 `--update-baseline` 會拿到一份不一樣的清單而不知道為什麼。
    一份要求別人釘 SHA 的守衛，自己的 baseline 產生自工作樹，就沒有立場要求任何人。

    ⚠️ **測試本身仍然讀工作樹**（`iter_docs`）—— 那是對的：
    守衛要判的是**現在**的內容。釘 SHA 的只有 baseline 的產生端。
    """
    prefix = f"{DOCS_DIR.relative_to(REPO_ROOT)}/".replace("\\", "/")
    names = [n for n in _git("ls-tree", "-r", "--name-only", sha, "--", prefix).splitlines()
             if n.startswith(prefix) and _in_scope(n[len(prefix):])]
    if not names:
        raise RuntimeError(
            f"在 {sha} 上找不到任何符合 {DOCS_GLOBS} 的檔（{prefix}）—— 拒絕產生一份空的 baseline。")
    return [(n, _git("show", f"{sha}:{n}")) for n in sorted(names)]


def _refuse_if_rebuild_would_drop_rows(sha: str, docs: list[tuple[str, str]]) -> None:
    """⛔ 重建若會讓現行 baseline 的某些檔**整批消失**，直接炸掉，不留「安靜洗掉」那條路。

    本份 baseline 自 2026-09-23 起是**混合來源**：多數 entry 出自 `_generated_from_sha`，
    線框那幾筆是**手工增補**的，而那個 commit 上根本沒有 `prototype/`。
    ⚠️ 在這一道之前，那句「只准手工增補」**只寫在散文裡、零機械守衛** ——
    而破壞半徑是 7 筆 entry ＋ 12 筆 `why_safe` ＋ 整個 `_why_safe_notes`。
    """
    have = {n for n, _ in docs}
    known = {e["file"] for section, _ in CHECKS for e in load_baseline()[section].values()}
    lost = sorted(known - have)
    if lost:
        raise RuntimeError(
            f"拒絕重建：{sha} 的樹上沒有下列檔，而現行 baseline 有它們的登記：\n"
            f"  {lost[:5]}\n"
            "⇒ 重建會把那些 entry 連同全部 `why_safe` 與 `_why_safe_notes` 一起洗掉。\n"
            "⛔ 這一份只准**手工增補**（作法見模組 docstring 的「禁止用任何 SHA 重建」那一段）。")


def _update_baseline(rev: str = "HEAD") -> int:
    sha = _git("rev-parse", rev).strip()
    docs = docs_at_sha(sha)
    _refuse_if_rebuild_would_drop_rows(sha, docs)
    print(f"baseline 來源：commit {sha}（{len(docs)} 個受檢檔）—— **不是工作樹**")
    data: dict[str, object] = {"_README": _BASELINE_README, META_SHA: sha}
    total = 0
    for section, fn in CHECKS:
        found: list[Finding] = []
        for doc_rel, doc in docs:
            found += fn(doc_rel, doc)
        entries: dict[str, dict[str, str]] = {}
        for f in sorted(found, key=lambda x: (x.doc, x.line)):
            entries.setdefault(f.key, {"file": f.doc, "text": f.text})
        data[section] = dict(sorted(entries.items(), key=lambda kv: (kv[1]["file"], kv[1]["text"])))
        total += len(entries)
        print(f"  {section:36s} 命中 {len(found):4d} → 去重後 {len(entries):4d} 筆")
    BASELINE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8")
    print(f"已寫入 {BASELINE_PATH.relative_to(REPO_ROOT)}（合計 {total} 筆）")
    print("⛔ 請逐句讀 `git diff` 再 commit —— 那份 diff 就是你在簽名承認的東西。")
    return 0


if __name__ == "__main__":
    _args = sys.argv[1:]
    if _args and _args[0] == "--update-baseline" and len(_args) <= 2:
        raise SystemExit(_update_baseline(_args[1] if len(_args) == 2 else "HEAD"))
    if _args == ["--report"] or not _args:
        raise SystemExit(_report())
    print(__doc__)
    print("用法：python3 tests/test_doc_counters.py [--report | --update-baseline [<rev>]]")
    raise SystemExit(2)
