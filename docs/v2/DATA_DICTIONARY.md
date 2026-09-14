# v2 資料字典與指標 SSOT（階段 1 交付物）

> **狀態**：階段 1 文件交付物。**不含任何實作**。
> **base**：`origin/main` = `9cbf03776f2a0ee6bdb5a649efb93352c40baba6`（量測日 **2026-09-14**）
> **涵蓋**：終審令階段 1 檢查表第 **1**（可用資料庫白皮書）、第 **2**（指標 SSOT 附錄）、第 **5**（持倉與交易資料模型）項。

---

## §0. 射程宣告（承重段，先讀這一段）

**本文件只涵蓋「基金儀表板」（`my-Fund-dashboard`）。**
股票／ETF 戰情室由另一條線負責；跨儀表板共用的 `v2_holdings` 契約，
**在此僅記載基金側的需求與待協調項**，**不替股票側決定任何欄位**。

⚠️ **這一段是承重的。** 少了它，下一個人會把這份白皮書當成全系統的資料字典，
然後在一份**只量過一半**的文件上做決定 —— 那正是本專案 `CLAUDE.md §-2.A` 反覆記載的事故形狀。

**具體邊界**：

| 範圍 | 本文件的處理 |
|---|---|
| 基金側資料源、欄位、指標 | ✅ 本文件盤點並定義 |
| `v2_transactions`（基金側交易） | ✅ 本文件定義完整欄位 |
| `v2_holdings` 的**基金側需求**與**唯讀引用方式** | ✅ 本文件定義 |
| `v2_holdings` 的 `asset_class` 完整列舉、ETF 專屬欄位 | ⛔ **不決定** → 見 §4.7 跨儀表板待協調項 |
| 股票／ETF 指標（本益比 TTM 等） | ⛔ 不盤點。**例外**：若基金側自己也在用，則以基金側實際用法為準（實測結果見 §3.1.3） |

### 0.1 「禁用語」對本文件的射程界定（2026-09-14 總管裁決）

v2 母法 §6.2.1 列了**客戶逐字定死的六個禁用語**：
**建議買進、立即出清、應該加碼、推薦、必漲、目標價**。

> ⚠️ **2026-09-14 第三輪就地更正（有意識的更正，不是漏刪；由獨立稽核抓出）**：
> **下表原本只有兩欄，第一欄叫「全文命中」，六格分別是 ~~0／0／0／5／0／0~~ —— 六格全部為假。**
> **在物理上不可能為 0**：那六個詞就逐字列在上一段的引言與本表的第一欄裡。
> 宣告值**只有在「排除 §0.1 本節」這個母體下才重現**，而**原表從未寫出這個母體**。
> ⛔ **這**至少**是本文件第三次踩同一個自我污染陷阱**（依本文件自己的記載：§3.1.1(a) 的 `DTB3`、
> §7.5.2 的腳本 docstring —— 後者還**遞迴了一層**，連「描述這個污染」的句子都造成同一個污染），
> 而這一次**就犯在它用來處理「禁用語」的那張表上**。
> ⚠️ **「誰抓到的」逐一照本文件自己的署名寫，不憑印象**：`DTB3` 那次自陳「**由獨立稽核抓出**」，
> §7.5.2 腳本 docstring 那次自陳「本節在本輪**又踩了一次**……就地記下來」（＝**自己抓到**），
> 本次**由獨立稽核抓出**。**⛔ 不宣稱「只有這三次」** —— 那取決於有沒有漏看（`CLAUDE.md §-2` 規則 5）。
> **承重後果**：本節同時對階段 2 下了硬性要求。階段 2 若拿原表當基準去驗守衛，
> 會量到與宣告完全不同的數字，然後合理懷疑守衛壞掉或本文件違規。
> **實質裁決與逐一判讀的結論未改，改的是那張表與它的母體敘述。**

**本文件的實測（量測日 2026-09-14；量測對象 ＝ 本 PR head 的本檔定稿；工具 ＝ `str.count`）**

⛔ **先寫母體，因為上一版就是敗在沒寫母體**：

| 欄 | 母體 |
|---|---|
| **A** | **整份文件，含 §0.1 本節** —— 本節逐字列出六個詞，故 A 欄**必然 > 0**，它**不回答**任何合規問題 |
| **B** | **整份文件，排除 §0.1 本節**（＝原表宣告值真正的母體） |
| **C** | **只取 §4.6**（面向使用者的文案草稿） |
| **D** | **只取 §3.3 表格的「顯示」欄**（同樣是要顯示給使用者看的字串，見下方 Advisory 註） |

| 禁用語 | A：全文（含本節） | B：排除本節 | C：§4.6 | D：§3.3 顯示欄 |
|---|---|---|---|---|
| 建議買進 | 2 | 0 | 0 | 0 |
| 立即出清 | 2 | 0 | 0 | 0 |
| 應該加碼 | 2 | 0 | 0 | 0 |
| **推薦** | **18** | **5** | **0** | **0** |
| 必漲 | 2 | 0 | 0 | 0 |
| 目標價 | 2 | 0 | 0 | 0 |

⚠️ **A 欄會隨本節每一次改寫而變動，這是它的性質不是它的錯** ——
**引用本表請用 B／C／D，不要用 A**；A 欄留在表上，是為了讓「為什麼不能宣告 0」這件事看得見。

**⭐ 正／負對照與空檔防護（原表寫了「含正／負對照」四個字，卻從未寫出那兩個對照是什麼，
因此無法被複跑；本輪把三者逐一寫出）**：

| # | 種類 | 做法 | 本輪實跑結果 | 它擋掉什麼 |
|---|---|---|---|---|
| 1 | **正對照** | 對**記憶體中的副本**各植入一次該詞（不寫回檔案），要求計數**恰好 +1** | 六個詞**全部 +1，PASS** | 計數器恆回 0（＝它根本沒在看） |
| 2 | **負對照** | **同一次執行**換母體：A 欄非 0、C／D 欄為 0 | 同一支工具同時回出非 0 與 0 | 計數器恆回同一個常數 |
| 3 | ⭐ **空檔防護** | 讀檔後先斷言 `len(bytes) >= 1000`，不足即中止、**不往下算** | **PASS**（本檔遠高於門檻；⚠️ **刻意不寫實際位元組數** —— 那是一個寫下去就會改變它自己的自我計數） | **空檔與「這些字真的不在裡面」輸出一模一樣** |

⛔ **第 3 條不是理論**：本輪覆核期間，上游用 `git show <sha>:<path> > f.md` 取檔，
**該 rev 當時尚未 fetch、指令失敗，但 shell 的 `>` 已經先建好一個空檔**，
接著對空檔數這六個詞 —— **全部回 0，而 0 正好就是原表宣告的值**。
**差一步就要據此判定稽核講錯。** 沒有第 3 條，任何「0 命中」都只是「我沒量到」的同義詞。

**B 欄那 5 個「推薦」逐一判讀，全部是治理用語，沒有一處是對使用者講的投資建議**：
「本文件給推薦但不單方決定」（§4.2）／「**總管推薦**：物化 `v2_holdings`」（§4.2）／
「**總管推薦方案**（依 `CLAUDE.md §-1.5.1b` 裁決二…）」（§6）／
「請示必須附推薦，不得只丟選項」（§6）／「本推薦未查證 FRED…」（§6）。

> 📌 **2026-09-14 第三輪就地更正之二：一句被撤下的全稱句（有意識的更正，不是漏刪）**
> 上表原本的第三欄欄名寫 §4.6 是「~~**唯一**要顯示給使用者看的文案草稿~~」。
> **那是一句可被一條指令推翻的全稱句，正是 §7.4 明文禁止本文件書寫的句型。**
> **實測反例**：§3.3 `N/A` 觸發條件表的**「顯示」整欄**同樣是要顯示給使用者看的字串
> （`N/A（虧損）`、`N/A（樣本不足 n/250）`、`N/A（無同類可比）`…），
> 其中**兩列還標著「客戶逐字指定」** —— 它比 §4.6 更接近「客戶定死的使用者可見文案」。
> ⇒ 故本輪把它降為**不帶量詞的描述**，並**把 §3.3 的「顯示」欄實際量出來當 D 欄**。
> ✅ **結論不受影響**：D 欄六格**實測全為 0**（§3.3 整節六個詞也全為 0）。
> **舊表述的用意仍然成立**（它想指出「本文件絕大多數內容是治理散文，不是使用者文案」），
> **被權衡掉的是它的窮舉性** —— 而窮舉性正是它唯一多說的那部分。

**⭐ 總管裁決（2026-09-14）——「禁用語」的射程是「面向使用者的輸出」，不含內部治理文件。**

- **理由 1（不是新發明，是母法自己已經這樣做的）**：母法 §6.3.1 用來量測 §6.2.2 的掃描器，
  本身就是 **AST 掃描、且明文區分「使用者看得到的字串」vs「註解／docstring」**，
  其三顆自測探針是 `planted_user_string → 必須 HIT`、`comment_only → 必須 MISS`、
  `docstring_only → 必須 MISS`。**「使用者可見」這個限定詞是母法自己下的。**
- **理由 2**：「**總管推薦方案**」是 `CLAUDE.md §-1.5.1b 裁決二` **強制要求**的治理用語 ——
  請示**必須**附推薦、**不得**只丟選項。若禁用語掃到治理文件，
  **母法會與 `CLAUDE.md` 直接互相違反**：一邊強制要寫，一邊禁止出現。
- **理由 3**：這六個詞禁的是**促使使用者做出買賣動作**（母法 §6.1 G1~G3：只給偏離提示、
  客觀對照、情境試算）。「總管推薦把 `v2_holdings` 物化」**不會讓任何人去買一檔基金**。

⛔ **對階段 2 的硬性要求（寫在這裡，免得守衛一上線就誤報）**：
**若階段 2 要建禁用語的機械守衛，其掃描對象必須限定在「面向使用者的輸出」**
（production `.py` 的 user-facing 字串、UI 文案、AI prompt 產出），
**⛔ 不得掃治理文件**（`CLAUDE.md`／`EXCEPTIONS.md`／`docs/v2/*.md`／PR 描述／commit message）。
⚠️ 母法 §6.2.2 已實測「六個詞在 production `.py` 的使用者可見字串命中 **3 個字串**，
**3/3 全是誤報**」（兩個是否定句「不推薦」「不會被推薦」，一個是匯入方式的操作提示）——
**誤報率已知不是 0，守衛上線時必須同時帶豁免條款**，否則它會逼人把誠實的否定句刪掉。
> 📌 **2026-09-14 第三輪就地更正之三（量詞，有意識的更正，不是漏刪）**：
> 本段原本引母法作 ~~「命中 **3 處**」~~／~~「兩**處**是否定句」~~。
> **母法自己已經就地把量詞由「處」改為「字串」並標明理由**（見其 §6.2.2 該格的刪除線註記
> 「⚠️ 量詞由 ~~「處」~~ 改為「**字串**」，理由見 §6.4.2 的更正」）。
> **本文件沿用的是被撤下的那個版本。** 內容其餘部分（3 個、3/3 全是誤報、兩個否定句 ＋
> 一個操作提示）**逐字比對完全正確，數字與判讀一字未改**；**改的只有量詞**。
> ⚠️ **為什麼量詞值得改**：「處」讀起來像「出現位置數」，會讓人以為可以拿
> 一條字面 grep 的行數來對帳；母法量到的是 **AST 取出的 user-facing 字串個數**，
> **兩者不同源**（母法 §6.3.1 的第 2／3 顆探針正是在證明「註解／docstring 不算」）。

> ⚠️ **本小節引用的母法條文位於 `docs/v2/CONSTITUTION.md`，該檔在量測日
> 於分支 `origin/docs/v2-constitution-governance` 上，尚未合併進 `origin/main`**
> **實測（repo 根目錄，2026-09-14 實跑）**：
> `git ls-tree -r --name-only 9cbf0377 | grep 'docs/v2'` → **0 行（exit 1）** ——
> base 上**整個 `docs/v2/` 目錄都還不存在**（本文件是它的第一個檔）。
> **正對照**：同一條指令把 pattern 換成 `'^docs/'` 回 **17 行**，證明它不是恆回 0。
> 本文件**唯讀引用**該分支內容，**未動它一個字**（它是另一組的檔案邊界）。
> ⚠️ **若該檔在合併前被改寫，本小節的引用需重驗。**

---

> 📌 **一則過程揭露（`CLAUDE.md §-2` 規則 6）**：本任務的**第一版派工單**要求一併盤點姊妹 repo
> `my-stock-dashboard`，該指示**事後被總管撤回**（客戶明示本 session 只負責基金儀表板）。
> 撤回前姊妹 repo 已被 clone 至 `/home/user/linchen-20200325/my-stock-dashboard`，
> **本文件未讀取、未量測、未引用該 repo 任何內容**。本文件所有數字**一律出自 `my-Fund-dashboard`**。

---

## §1. 量測方法與其射程（先講怎麼量的，再看數字）

本文件的每一個數字都附「怎麼量的」。**量不到的一律寫「量不到」並說明射程，不估數字**（`CLAUDE.md §1` Fail Loud）。

### 1.1 環境限制（決定了哪些東西量得到）

| 限制 | 後果 |
|---|---|
| ⛔ 禁止打任何外部 API（TDCC／FundClear／MoneyDJ／FinMind／FRED／Yahoo…） | **所有「實際回應延遲」皆無法量測**。§2.4 的延遲一律是**程式碼宣告值**（timeout／retries／backoff），**不是實測牆鐘時間** |
| ⛔ 禁止對 Google Sheets 做任何寫入；且本環境無憑證 | **Google Sheets 上的實際資料列數、實際缺漏率無法量測**（見 §2.3.3） |
| ⛔ 禁止 `pip install`；環境無 `pandas`／`pyarrow`／`numpy`／`snappy` | `data_cache/*.parquet` 無法用標準工具讀取 → 本文件**自行以純 Python 實作 snappy + thrift-compact + parquet 解碼器**取得數字（驗證方式見 1.2） |

### 1.2 parquet 解碼器的正確性驗證（為什麼可以信這些數字）

`CLAUDE.md` 記載本專案累計十次以上「假檢查」，形狀一律是**工具沒量到它宣稱在量的東西**。
故本文件對自製解碼器做了**四道獨立驗證**，四道全過才採用其輸出：

| # | 驗證 | 結果 |
|---|---|---|
| 1 | 解碼器回報的 `num_rows` vs `data_cache/metadata.json` 宣告的 `row_count` | ✅ 四檔全部一致 |
| 2 | 解碼出的 `max(date)` vs `metadata.json` 的 `last_updated` | ✅ 一致（vix/spx/twii = 2026-09-11；fred = 2026-09-10） |
| 3 | **外部世界事實**：VIX 歷史最高收盤 | ✅ 解碼得 **82.69 於 2020-03-16** —— 與真實 COVID 紀錄相符 |
| 4 | **holiday 形狀**：TWII 的長缺口是否落在農曆年 | ✅ **`≥ 12` 天的缺口共 9 個**（1 個 13d ＋ **8 個並列 12d**），**9 個全部落在農曆春節**（逐一列於下方） |

**驗證 4 的完整清單（2026-09-14 實測，`twii_history.parquet` 全 3726 列日期序列）**：

| # | 缺口 | 天數 | 落點 |
|---|---|---|---|
| 1 | 2023-01-17 → 2023-01-30 | **13d** | 農曆春節 |
| 2 | 2012-01-18 → 2012-01-30 | 12d | 農曆春節 |
| 3 | 2013-02-06 → 2013-02-18 | 12d | 農曆春節 |
| 4 | 2016-02-03 → 2016-02-15 | 12d | 農曆春節 |
| 5 | 2019-01-30 → 2019-02-11 | 12d | 農曆春節 |
| 6 | 2021-02-05 → 2021-02-17 | 12d | 農曆春節 |
| 7 | 2022-01-26 → 2022-02-07 | 12d | 農曆春節 |
| 8 | 2025-01-22 → 2025-02-03 | 12d | 農曆春節 |
| 9 | 2026-02-11 → 2026-02-23 | 12d | 農曆春節 |

> ⚠️ **2026-09-14 就地更正：「最長 5 個」這個選法是不可複跑的（由獨立稽核抓出）**
> （**有意識的更正，不是漏刪**）。原文列的那 5 個缺口**逐一重量後全部真實存在、天數全部正確、
> 也全部是春節** —— 錯的不是事實，是**「最長 5 個」這個取法本身沒有定義**：
> **12d 有 8 個並列**，「取前 5 名」必須在 8 個並列者中挑 4 個，而**挑法沒寫**。
> 換一種 tie-break（例如按年份倒序）就會列出**另外 4 個**，同樣全部正確 ——
> ⇒ **兩份都對、但互相對不上，讀者無從複驗。**
> **現改為門檻式敘述（`≥ 12` 天，共 9 個，全部列出）**，沒有 tie-break、可以逐一複跑。
> 📌 **這條教訓可以推廣**：凡是「最長／最大的前 N 個」，只要**可能並列**，就必須改寫成
> **門檻 ＋ 全部列出**，否則那個 N 是一個沒有定義的數字。

> ⚠️ **一次真實的假檢查，就地記錄（這比上面的數字更值得讀）**
> 本文件的**第一版** FRED 涵蓋度檢查，用「4-byte 小端長度前綴 + 字串」去比對 parquet bytes，
> 並跑了**負向對照**（`ZZZZFAKE`／`NAPM`／`DGS10_NOT_REAL` 全部回 `False`）→ 看起來很嚴謹，
> 結論是「41 個宣告 series 中 **7** 個在快取裡」。
> **那個 7 是錯的，正確答案是 9。**
> **成因**：dictionary page 是 **snappy 壓縮**的，`DGS2`／`DGS3MO` 的長度前綴被壓成了 back-reference，
> 字面上不存在 → 檢查恆假。
> ⛔ **關鍵教訓**：**負向對照只能證明「沒有偽陽性」，永遠證不出「沒有偽陰性」。**
> 抓到它的不是負向對照，是一個**矛盾**：`strings` 看得到 `DGS2`，而我的檢查說看不到。
> → 本文件其餘所有「N 個之中有 M 個」的數字，一律附**正向對照 + 矛盾交叉檢查**，不只附負向對照。

### 1.3 本文件明確**未**涵蓋的範圍（誠實揭露，不是免責）

- **未讀** `SPEC.md` / `ARCHITECTURE.md` / `STATE.md` / `BACKLOG.md` / `TODO.md` 全文（僅針對性查證）。
- **未讀**姊妹 repo 任何內容（§0 已述）。
- **未執行**任何測試、未啟動任何 UI、未做任何 runtime 量測。
- **未查證** Google Sheets 上的實際資料（無憑證，且禁止寫入）。
- 本文件所有盤點**均為單組產出，未經第二組獨立複驗**（`CLAUDE.md §-2` 規則 6）。
  ⛔ 在獨立稽核完成前，**不得**把本文件任何一句當成「已查證的事實」去支撐下一步實作決策。

⚠️ **本文件刻意不寫「只有 N 處」「全部都是 X」這類能被一條 grep 推翻的全稱句**
（`CLAUDE.md §-1.5.1c 判定 2` 的方法教訓）。凡是盤點，一律寫成**分類敘述 ＋ 明列未涵蓋範圍**。

---

## §2. 第 1 項｜可用資料庫白皮書

### 2.1 實體來源總表

**權威分級沿用 `CLAUDE.md §2.1` 的 5-Tier**（衝突時上層贏，**禁止平均**）。
⚠️ `CLAUDE.md §2.1` 那張表的多處 evidence 路徑**已知過期並就地更正過**；
下表路徑為**本輪重新量測**（`git grep` + `ls` 實跑，量測日 2026-09-14），**未照抄該表**。

| Tier | 來源 | 基金側用途 | 現行實作位置（本輪實測） | 更新頻率 |
|---|---|---|---|---|
| T1 | **FundClear** 境外基金資訊觀測站 | 境外 NAV／meta／配息 | `repositories/fund/sources.py::_src_fundclear_nav`／`_src_fundclear_meta`／`_src_fundclear_div`；另 `repositories/fundclear_offshore.py` | T+1 |
| T1 | **TDCC** 集保 OpenAPI | 境內 NAV／基金清單／meta | `repositories/fund/sources.py::_src_tdcc_meta`／`_tdcc_get`（3-2／3-4 兩個 endpoint） | T+1 |
| T1 | **SITCA** 投信投顧公會 | 境內 meta（`fund_name`／`nav_latest`） | `repositories/fund/sources.py::_src_sitca_meta`／`_src_sitca_nav` | T+1 |
| T1 | **FRED** | 總經指標、無風險利率來源 | `repositories/macro/fred.py::fetch_fred`／`fetch_fred_batch` | 各 series 不同（見 `CLAUDE.md §2.3`） |
| T2 | **FinMind** | TW 總經（NDC 景氣）、外資買賣超 | `repositories/macro_tw_local_repository.py`、`repositories/hot_money_repository.py` | T+1 ～ 月 |
| T2 | **Yahoo Finance** | FX、指數、基準（SPY／QQQ） | `repositories/macro/yf.py::fetch_yf_close`／`fetch_benchmark_close` | EOD |
| T3 | **MoneyDJ**（主站 + `tcbbankfund` + `chubb` 等子網域） | NAV 歷史、績效 wb01、風險 wb07、配息 wb05、持股 | `repositories/fund/nav_metrics.py`（`fetch_nav`／`fetch_performance_wb01`／`fetch_risk_metrics`／`fetch_holdings`） | T+1 ～ T+3；wb01/wb05/wb07 為**月更** |
| T3 | **Cnyes 鉅亨** | NAV／配息／持股 fallback | `repositories/fund/sources.py::fetch_nav_cnyes`／`fetch_div_cnyes`／`fetch_holdings_cnyes` | T+1 |
| T3 | **Morningstar** | NAV／持股／secid 解析 fallback | `repositories/fund/sources.py::_src_morningstar_nav`／`fetch_holdings_morningstar` | T+1 |
| T3 | **保單發行商子網域**（Allianz／台灣人壽／富蘭克林／JPMorgan…） | 保單連結基金 NAV | `sources.py::_src_allianzgi_nav`／`_src_taiwanlife_nav`／`_src_franklin_nav`／`_src_jpmorgan_nav` | T+1 |
| T5 | **Google Sheets** | 保單政策、交易帳、NAV 歷史、選股池、組合績效 | `repositories/policy/`、`repositories/ledger_repository.py`、`services/nav_history_gs.py`、`repositories/pool_repository.py`、`repositories/portfolio_perf_repository.py` | 使用者寫入即時 |

⚠️ **本表是「本輪查到的」，不是窮舉。** 未涵蓋：`repositories/external_market_repository.py`（stooq／cboe，風險雷達用）、
`repositories/news_repository.py`（RSS，非數值）、`repositories/ai_cache.py`、`repositories/snapshot_repository.py` 的上游。

### 2.2 欄位字典（逐儲存體）

#### 2.2.1 `_Ledgers`（v1 交易帳，Google Sheets）— **v2_transactions 的直接前身**

SSOT：`repositories/ledger_repository.py::LEDGER_COLS`（實測 9 欄）

| 欄位 | 型別 | 必填 | 語意 | 幣別 | v2 對應 |
|---|---|---|---|---|---|
| `policy_id` | str | ✅ | 保單識別碼 | — | `v2_transactions.account_id` |
| `date` | str(ISO) | ✅ | 交易日 | — | `trade_date` |
| `code` | str | ✅ | 基金代碼 | — | `instrument_code` |
| `action` | str | ✅ | `buy`／`sell`／`dividend`／`fee`／`fx` | — | `txn_type`（需擴充，見 §4.1） |
| `units` | float | ✅ | 單位數 | 單位 | `units` |
| `nav_at_action` | float | 選填 | 當日淨值 | **原幣** | `price_orig` |
| `twd` | float | 選填 | 台幣金額 | **TWD** | `amount_twd` |
| `fee` | float | 選填 | 費用 | ⚠️ **未宣告幣別** | `fee_orig` ＋ `fee_ccy`（見 §5 缺口 G-4） |
| `note` | str | 選填 | 備註 | — | `note` |

- **主鍵（程式碼自陳）**：`(policy_id, code, date, action, units)`
- `KNOWN_ACTIONS = ("buy","sell","dividend","fee","fx")`；程式碼自陳**不在列表內不攔截**（「呼叫端自由」）→ ⚠️ 這是 v2 必須收緊的點（見 §4.1）。

#### 2.2.2 保單政策表（v1，Google Sheets，每保單一個 worksheet）

SSOT：`docs/POLICY_SHEETS_SETUP.md`（9 欄）＋ `repositories/policy/v2.py`

| 欄位 | 型別 | 必填 | 語意 | 幣別 |
|---|---|---|---|---|
| `policy_id` | str | ✅ | 保單唯一識別碼 | — |
| `policy_name` | str | ✅ | 顯示名稱 | — |
| `fund_url` | str | ✅ | 基金代碼或 MoneyDJ URL（程式自動萃取代碼） | — |
| `invest_twd` | int | ✅ | 台幣投入**金額**（**不是權重**；空白視為 0） | **TWD** |
| `invest_date` | str | 選填 | 進場日 | — |
| `currency` | str | 選填 | 計價幣別 | — |
| `fx_at_buy` | float | 選填 | **進場匯率** | TWD/原幣 |
| `notes` | str | 選填 | 備註 | — |
| `policy_tier` | str | 選填 | `core`／`satellite`；空→退基金名啟發 | — |

- ⚠️ **複合主鍵 `(policy_id, fund_url)`**，同一保單同一檔基金分多筆買 → `invest_twd` **加總**（`CLAUDE.md §4.6` 已就地更正過此處的舊錯誤描述）。
- ⚠️ **權重是算出來的、不是存的**：核心／衛星比例 = Σ `invest_twd` 加權。Sheet 端**不存任何 0~1 權重**。

#### 2.2.3 `nav_history`（v1，獨立一本 Google Sheet）

SSOT：`services/nav_history_gs.py::_NAV_HEADERS`（實測 7 欄）

`code` | `date` | `nav` | `fund_name` | `source` | `recorded_at` | `currency`

- ⚠️ 程式碼自陳既有分頁可能只有 **6 欄**（`currency` 為後加），有「只補缺的那幾格」的 header 修補邏輯 → **v2 ETL 必須容忍 6 欄與 7 欄兩種歷史形狀**（見 §2.5）。

#### 2.2.4 `snap.json`（v1 本地快照，repo 根目錄）

實測：8 檔基金，`dumped_at = 2026-08-10T18:50:54Z`。
每檔 **7 個 key**：`fund_name`／`category`／`inception_date`／`nav_points`／`metrics`／`perf`／`perf_source`。
`metrics` **8/8 檔皆為 11 個 key**。

> ⚠️ **2026-09-14 就地更正（有意識的更正，不是漏刪；由獨立稽核抓出）**：
> 本行原寫 ~~`perf`(8)~~ —— **那個 8 只對 8 檔中的 2 檔成立**，且**與本文件 §2.3.3 自己寫的
> 「`perf` 5/8 無資料」直接矛盾**。**實測（`json.load` 逐檔數 key，量測日 2026-09-14）**：
>
> | `perf` key 數 | 檔數 | 代碼 |
> |---|---|---|
> | **0**（`perf_source = None`） | 5 | `ACCP138`／`ACDD01`／`ACDD19`／`ACTI71`／`ACTI94` |
> | **8** | 2 | `JFZN3`／`TLZF9`（`1M`/`3M`/`6M`/`1Y`/`2Y`/`3Y`/`fetched_at`/`source`） |
> | **7** | 1 | `ALBT8`（同上但**無 `3Y`**） |
>
> ⇒ **`perf` 的 key 數不是一個定值，所以「`perf` ＋ 一個括號數字」這種標註本身就錯**
> —— 不管括號裡填幾，它都在宣稱一個不存在的定值。
> ⚠️ 對照：`metrics` **可以**這樣標，因為它**真的 8/8 檔都是 11 個 key**（已重量）。
> **「每檔 7 個 key」同樣經重量正確。兩者未改。**

### 2.3 歷史缺漏率統計（**實測**）

> **量測方法**：對 `data_cache/*.parquet` 以自製解碼器（驗證見 §1.2）取出完整 `date` 欄，
> 以 **Mon–Fri 平日**為分母計算涵蓋率。
> ⚠️ **分母不排除市場假日與國定假日** → 因此「涵蓋率」是**下界**、「缺漏率」是**上界**。
> ⚠️ **量測日 2026-09-14。此為會漂移的量測值 —— 引用前請現場重量，不要引用本表。**

#### 2.3.1 指數／波動度序列

| 資料集 | 列數 | 期間 | 平日數 | 涵蓋率（下界） | 缺漏率（上界） | null | 最長缺口 |
|---|---|---|---|---|---|---|---|
| `vix_history` | 3841 | 2011-06-07 ～ 2026-09-11 | 3984 | 96.41% | **3.59%** | 0 | 5d |
| `spx_history` | 3839 | 2011-06-07 ～ 2026-09-11 | 3984 | 96.36% | **3.64%** | 0 | 5d |
| `twii_history` | 3726 | 2011-06-07 ～ 2026-09-11 | 3984 | 93.52% | **6.48%** | 0 | **13d** |

**判讀（這才是重點，不是三個百分比）**：
- TWII 缺漏率（6.48%）顯著高於 SPX（3.64%），**差值 ≈ 2.84 個百分點 ≈ 每年 7 個交易日** ——
  與台灣多出的**農曆春節連假**吻合（§1.2 驗證 4 已逐一列出那 9 個 `≥ 12` 天缺口）。
- ⇒ **這三個數字幾乎全部是「正常休市」，不是「抓取失敗」。**
  ⛔ **不得**把它們當成資料品質指標直接搬進 v2 的告警門檻。
- ⚠️ **要得到真正的「抓取失敗率」，必須有交易日曆**；而 `CLAUDE.md §4.5` 明載本專案
  **不使用**任何第三方 trading calendar lib（`requirements.txt` 無 `pandas_market_calendars`／`exchange_calendars`）。
  → **本文件量不到「排除假日後的真實缺漏率」**，這是 v2 的待決缺口（見 §5 缺口 G-6）。

#### 2.3.2 FRED 指標快取（`fred_indicators.parquet`，13654 列）

**涵蓋度**：`shared/fred_series.py` 宣告 **41** 個 unique series ID，快取內實際出現 **9** 個。
> **量測方法**：對 41 個宣告值逐一做 raw bytes 比對；
> **正向對照** `DGS10` → 命中；**負向對照** `ZZZZFAKE`／`NAPM`／`ISPMANPMI`／`T10Y2Y`／`ICSA` → 全部未命中；
> **偽陽性審計**：程式檢查「任一 ID 是否為另一 ID 的子字串」→ 無警告，故 raw 比對在此安全。
> （第一版用長度前綴比對得到 7，**已證實為偽陰性**，成因與教訓見 §1.2。）

| series | 列數 | 期間 | null | 推得頻率 |
|---|---|---|---|---|
| `DGS10` | 3816 | 2011-06-07 ～ 2026-09-10 | 0 | 日（交易日） |
| `DGS2` | 3816 | 2011-06-07 ～ 2026-09-10 | 0 | 日（交易日） |
| `DGS3MO` | 3816 | 2011-06-07 ～ 2026-09-10 | 0 | 日（交易日） |
| `BAMLH0A0HYM2` | 858 | **2023-06-05** ～ 2026-09-10 | 0 | 日（交易日） |
| `WALCL` | 797 | 2011-06-08 ～ 2026-09-09 | 0 | 週 |
| `UNRATE` | 181 | 2011-06-01 ～ **2026-08-01** | 0 | 月 |
| `M2SL` | 179 | 2011-06-01 ～ **2026-04-01** | 0 | 月 |
| `CPIAUCSL` | 178 | 2011-06-01 ～ **2026-04-01** | 0 | 月 |
| `DTWEXBGS` | **13** | **2026-06-05** ～ 2026-09-04 | 0 | 週 |

**判讀**：
- **快取內 0 個 null cell** —— 這個快取是「只存成功結果」的（與 `CLAUDE.md §-1.5.1c 判定 4` 記載的
  positive-only 快取設計一致）。⇒ **缺漏在此快取中不可見，它被表達為「那一列根本不存在」。**
  ⛔ 這代表**不能**用 null 率衡量此資料源的品質。
- **三條月頻序列的最後一期落差很大**：`UNRATE` 到 2026-08，`M2SL`／`CPIAUCSL` 只到 **2026-04** ——
  相對量測日 2026-09-14 已落後約 **5 個月**，遠超 `CLAUDE.md §2.4` 的月度 🔴 門檻（> 75 天）。
  ⚠️ **本文件不宣稱這是 bug** —— 它可能是「這份離線快取不是 production 取數路徑」。
  **未查證**：production 是否改走即時 FRED API 而非此快取。列為 §5 缺口 G-7。
- `DTWEXBGS` 僅 13 列、起自 2026-06-05 → **明顯是近期才加入的 series**。

#### 2.3.3 基金 NAV 的缺漏率 —— ⚠️ **量不到，且原因必須寫清楚**

**實測**：`cache/nav/` 目錄下**只有 1 個檔案**：`cache/nav/TLZF9.json`。
其內容為 `count: 10`，10 個點的日期為
2026-04-23、2026-04-22、2020-10-01、2020-02-03、2015-03-18、2013-05-02、2013-03-01、2012-10-16、2012-10-15、2011-11-18
（`source: "cache_only"`）。

⛔ **這不是一份可用來統計缺漏率的語料**：10 個點橫跨 15 年，是**稀疏降級快取**，不是日頻 NAV 序列。
**拿它算出來的任何「缺漏率」都會是一個沒有意義的數字。**

**基金 NAV 的真實歷史存放在 Google Sheets（`nav_history` 本）**，而本環境
**無憑證且被禁止寫入** → **本文件無法量測基金 NAV 的歷史缺漏率**。

**替代量測（這個量得到，且更有價值）** —— 用 `snap.json` 這份真實 v1 快照量**指標層級的缺漏**：

| 指標 | 8 檔中為 `None` 的檔數 | 缺漏率 |
|---|---|---|
| `ret_3y` / `ret_3y_ann` / `ret_3y_cum` | **8/8** | **100%** |
| `ret_5y` / `ret_5y_ann` / `ret_5y_cum` | **8/8** | **100%** |
| `max_drawdown` | **8/8** | **100%** |
| `sharpe` / `std_1y` / `nav` / `inception_date` | 0/8 | 0% |
| `perf`（wb01 績效區塊） | **5/8 無資料**（`perf_source = None`） | **62.5%** |

**成因（實測，非推測）**：該快照中 **8/8 檔的 `nav_points` 都剛好是 30 筆**，
實際日期跨度僅約 **43 個日曆日**（例：`TLZF9` 2026-06-26 ～ 2026-08-07）。
- 3Y／5Y 指標需要 3～5 年序列 → 30 筆必然算不出來 → 全部 `None`。**這是正確的 Fail Loud 行為，不是 bug。**
- ⚠️ **但它對 v2 是承重的**：`services/fund_service.py::MIN_OBS_SHARPE_SORTINO = 250`
  要求 **250 個交易日**才准自算 Sharpe/Sortino，而預設取數路徑只給 30 筆。
  ⇒ **v2 若要自算風險指標，必須先解決「長序列從哪來」**，見 §5 缺口 G-1。

#### 2.3.4 一個實測到的 v1 資料品質缺陷（直接影響第 2 項的「同類中位數」）

`snap.json` 的 `category` 欄位，**8 檔中有 5 檔存的不是類別，而是公開說明書的投資範圍段落**：

| 代碼 | `category` 長度 | 內容判定 |
|---|---|---|
| `ACCP138` | 266 字 | ⛔ 說明書段落（「1.本基金投資於國內證券投資信託事業…」） |
| `ACDD01` | 383 字 | ⛔ 說明書段落 |
| `ACDD19` | 12 字 | ⛔ 說明書片段（「中華民國境內之有價證券。」） |
| `ACTI71` | 268 字 | ⛔ 說明書段落 |
| `ACTI94` | 762 字 | ⛔ 說明書段落 |
| `JFZN3` | 3 字 | ✅ `平衡型` |
| `TLZF9` | 3 字 | ✅ `平衡型` |
| `ALBT8` | 3 字 | ✅ `股票型` |

**分布**：5 檔**境內**代碼（`ACxx`）全部污染；3 檔**境外／保單**代碼全部正常。
⚠️ **本文件不宣稱「境內代碼一律污染」** —— 樣本只有 8 檔，且**只有這一份快照**。
這是**分類敘述**：在這份 2026-08-10 的快照中，污染與「境內代碼」100% 共現。

⛔ **對 v2 的承重後果**：客戶指定「基金淨值與中位數採**同類**中位數」——
**同類分組的鍵就是 `category`**。在 5/8 的樣本上這個鍵是一段說明書文字，
**任何依它做的分組都會把每一檔基金分成自己一類，中位數 = 它自己**。
→ 見 §3.1.2 與 §5 缺口 G-2。

### 2.4 冷／熱載入延遲標註

> ⛔ **以下全部是「程式碼宣告值」，不是實測牆鐘時間。**
> 理由：本階段禁止打外部 API（§1.1）。**任何實測延遲數字都必須在解禁後重新量。**
> **量測方法**：讀 `infra/proxy.py`、`shared/ttls.py`、`shared/backoff_policy.py`、
> `infra/cache.py` 與各 fetcher 的裝飾器宣告（量測日 2026-09-14）。

#### 2.4.1 熱載入（cache hit）

| 快取型態 | 實作 | 存活時間 | 適用 |
|---|---|---|---|
| `@_ttl_cache(ttl_sec=N)` | `infra/cache.py`，自製 | `shared/ttls.py` SSOT：60／300／600／900／1800／3600 秒 | FRED、Yahoo、FX、流動性引擎 |
| `@_daily_cache` | `infra/cache.py` | **保存當日（TW UTC+8），隔日 00:00 自動 miss** | `fetch_nav`／`fetch_div`／`fetch_performance_wb01`／`fetch_risk_metrics`／`fetch_holdings` |
| `@st.cache_data` | Streamlit | 依 `ttl` 參數 | L1 `hot_money_repository`；L3 見 `EXCEPTIONS.md EX-UICACHE-1` |

**熱載入延遲**：cache hit **0 次 HTTP**（`infra/cache.py` 對 `_daily_cache` 的自陳：「同日多次呼叫：cache hit，0 HTTP」）。
實際耗時為 dict 查表，**本文件未量測，但可視為與網路無關**。

⚠️ **失敗結果不入快取**（`_daily_cache` 的 `cache_if`，v19.253 R23）：
空 Series／空 list／`{}`／`source` 含 `all_failed` 的 dict **不入 cache**。
⇒ **失敗路徑沒有熱載入，每次都會重新付出冷載入成本。** 這是 v2 做延遲預算時最容易漏掉的一項。

#### 2.4.2 冷載入（cache miss）—— 單次 HTTP 的宣告上界

**這裡有兩支不同的函式，v1 把它們併成一個引用過，務必分清楚**：

| 函式 | 住哪 | 預設參數（實測簽章） |
|---|---|---|
| **`fetch_url`** | **`infra/proxy.py`** | `timeout=20`、`retries=3`、`backoff_on_429=True`、`bypass_backoff=False` |
| **`fetch_url_with_retry`** | **`fund_fetcher.py`**（**不在 `infra/proxy.py`**） | `timeout=20`、`retries=3`、**`sleep_sec=2`** —— **沒有 `backoff_on_429` 這個參數** |

**`fetch_url_with_retry` 是 MoneyDJ 特化薄殼**：它加上 `Referer` 與 Big5 解碼後，
轉呼 `infra.proxy.fetch_url(url, headers=..., params=..., timeout=timeout, retries=retries)` ——
**沒有傳 `backoff_on_429`，因此吃 `fetch_url` 的預設 `True`**。
其 docstring 自陳 **`sleep_sec` 已不使用**（退避由 infra 內部處理），保留只為 signature 向後相容。

⇒ **429 退避在 NAV 路徑上確實生效**，但**生效的機制是「薄殼吃了下游預設值」，不是薄殼自己有這個參數**。

> ⚠️ **2026-09-14 就地更正（有意識的更正，不是漏刪；由獨立稽核抓出）**：
> 本段原寫 ~~「`infra/proxy.py::fetch_url_with_retry` 預設：`timeout=20`、`retries=3`、`backoff_on_429=True`」~~
> —— **一句話裡錯了兩件事**：(1) 該符號**不在** `infra/proxy.py`（`git grep -n "^def fetch_url_with_retry"`
> 的唯一命中是 `fund_fetcher.py`）；(2) 它的介面**沒有** `backoff_on_429`。
> **`timeout=20` / `retries=3` 兩個數字碰巧兩支都對** —— 這正是它沒被發現的原因：
> **數字對了，不代表引用對了。**
> ⚠️ **這一項承重**：§2.4.2 是整份延遲預算的基礎，而 `nav_metrics.py::fetch_nav`
> （實測 `from fund_fetcher import ... fetch_url_with_retry ...`）呼叫的是**薄殼那一支**。
> **延遲上界的結論不變**（薄殼把 `timeout`／`retries` 原樣轉下去），改的是它的出處與介面描述。

**`fetch_url`（真正發 HTTP 的那一支）的行為**：
- **timeout 實際被拆成 `(connect, read) = (min(5, timeout), timeout)`**
  —— 程式碼自陳理由：proxy 半死時 20s TCP 握手太久，曾是「總經載入卡 10 分鐘」的放大器之一。
- **429 退避序列**：`_RATE_LIMIT_BACKOFF_SEC = (2.0, 4.0, 8.0)` 秒

**NAV 取數的冷載入上界（`repositories/fund/nav_metrics.py::fetch_nav`，實測其呼叫參數）**：
該函式以 `timeout=25, retries=2` 逐一嘗試一個 URL 清單：

| 情境 | URL 數 | 宣告上界 |
|---|---|---|
| 境內基金（`_is_domestic_code` 為真） | 2～3 | 3 URL × 2 retries × 25s ≈ **150 秒** |
| 境外基金 | 4～5 | 5 URL × 2 retries × 25s ≈ **250 秒** |

⚠️ **這是最壞情況的宣告上界，不是預期值。** 實際會因 connect timeout 5s 快速失敗而遠低於此。
⛔ **本文件量不到預期值**（需實際打 API）。

#### 2.4.3 來源失敗冷卻（跨呼叫）

SSOT：`shared/backoff_policy.py`（實測）

| 失敗類型 | 冷卻秒數 |
|---|---|
| `unreachable` | 60 |
| `server_error` | 300 |
| `blocked` | 900 |
| `rate_limited` | 1800 |
| `not_found`(404)／`proxy_auth`(407) | **不退避**（`NO_COOLDOWN_KINDS`） |

上限 `BACKOFF_MAX_COOLDOWN_SEC = 1800`。

#### 2.4.4 零快取路徑

`services/ledger_service.py` 檔頭自陳「**§4 零快取（無 `@st.cache_data`）**」
⇒ **帳務計算每次都重算**。對 v2 的意義：`v2_holdings` 若由 `v2_transactions` 即時推導，
**延遲正比於交易筆數**，需要在 §4.2 決定是否物化（materialize）。

### 2.5 v1 → v2 遷移路徑（ETL vs 手動）

| v1 資料 | 位置 | v2 目標 | 路徑 | 理由 |
|---|---|---|---|---|
| `_Ledgers` 交易帳 | Google Sheets | `v2_transactions` | **ETL（自動）** | 9 欄對 9 欄，語意一一對應（§2.2.1），`action` 需做值域映射 |
| 保單政策表 | Google Sheets（每保單一分頁） | `v2_transactions`（推導初始買進）＋帳戶維度 | **ETL（自動）＋人工覆核** | `invest_twd` 是**金額**不是權重；但**無 `units`、無 `nav_at_buy`** → 無法單獨還原單位數，見下方 ⚠️ |
| `nav_history` | 獨立 Google Sheet | v2 價格表 | **ETL（自動）** | 需容忍 **6 欄／7 欄**兩種歷史 header 形狀（§2.2.3） |
| `snap.json` | repo 根目錄 | 不遷移 | **丟棄** | 為 2026-08-10 的一次性 debug 快照，非權威來源 |
| `cache/nav/*.json` | repo | 不遷移 | **丟棄** | 稀疏降級快取（§2.3.3），非權威 |
| `data_cache/*.parquet` | repo | 總經快取 | **可選 ETL** | 僅 9/41 series，且月頻序列已落後數月（§2.3.2） |
| 選股池 `pool_repository` | Google Sheets | v2 watchlist | **ETL（自動）** | 本輪**未逐欄盤點**（射程外） |
| 組合績效 `portfolio_perf_repository` | Google Sheets | v2 績效快照 | **ETL（自動）** | 本輪**未逐欄盤點**（射程外） |

⚠️ **保單政策表無法純自動遷移，這是本節最重要的一句**：
政策表有 `invest_twd`（台幣金額）、`fx_at_buy`（進場匯率）、`invest_date`，
但**沒有 `units`（單位數）也沒有 `nav_at_buy`（進場淨值）**。
而 `v2_transactions` 的加權移動平均成本法**需要 `units`**。
- 若用 `units = invest_twd / (fx_at_buy × nav_at_invest_date)` 回推 → **需要當日 NAV**，
  而該 NAV 必須來自 `nav_history`，**且該日可能沒有資料**（T+1／假日）。
- ⇒ **判定：政策表遷移為「ETL 回推 ＋ 人工覆核」**，且回推失敗者**必須標記，不得靜默估值**（`CLAUDE.md §1`）。
- ⇒ 這是 §5 缺口 **G-3**。

### 2.6 多幣別：原幣／台幣儲存格式與匯率結算點

#### 2.6.1 幣別正規化（v1 已有 SSOT，v2 沿用）

`services/currency.py::normalize_ccy` / `CCY_NORMALIZE`（實測）：
中文與 ISO 皆統一回 **ISO 4217 三碼**；未知值回原值大寫。
- 支援 alias：美元/美金→USD、日圓/日元/日幣→JPY、台幣/新台幣/新臺幣→TWD、人民幣→CNY 等。
- **`mode="yf"` 覆寫**：`CNY → CNH`（程式碼自陳離岸人民幣在 yfinance 較可靠）。
  ⚠️ **這是一個真實的單位陷阱**：**同一檔基金在「儲存」與「報價」時幣別碼不同**。
  ⇒ v2 **必須分開存** `ccy_iso`（帳務用）與 `ccy_quote`（報價用），**不得共用一欄**。

#### 2.6.2 儲存格式規範（v2 硬規則）

依 `CLAUDE.md §4.1` 單位陷阱與 §2.2.1 實測到的 `fee` 未宣告幣別問題，v2 一律採：

> **每一個金額欄位，都必須與一個幣別欄位成對出現；且欄名必須編碼單位。**

| 規範 | 說明 |
|---|---|
| 原幣金額 | `*_orig` ＋ 必要的 `*_ccy`（例：`amount_orig` ＋ `amount_ccy`） |
| 台幣金額 | `*_twd`（**幣別隱含為 TWD，不另設欄**） |
| 匯率 | `fx_<base>_twd`，語意固定為 **「1 單位原幣 = N 台幣」**（TWD per unit of original currency） |
| 單位數 | `units`（無幣別） |
| 比率 | `*_ratio`（0~1）；百分比 `*_pct`（0~100）。**禁止混用**（`CLAUDE.md §4.1`：混用 = 100× 誤差） |

⚠️ **`fx_avg` 的方向必須釘死**：v1 `services/ledger_service.py` 的 CHUBB 公式
`net_investment_twd = cost_unit × units × fx_avg` ⇒ `fx_avg` 為 **TWD per 原幣**。
v2 沿用此方向，**不得**存倒數（`CLAUDE.md §4.4` 已列 FX 倒數為精度與 ÷0 陷阱）。

#### 2.6.3 匯率結算點（settlement point）

**這是客戶明確要求「明定」的項目。** v1 現況（實測）：

| 場景 | v1 用哪個匯率 | 位置 |
|---|---|---|
| 買進（申購） | **交易當日即期匯率**，存入 `fx_avg` 加權平均 | `ledger_service.subscribe(fx_rate=...)` |
| 配息（現金） | **除息當日匯率** | `ledger_service.dividend_cash(fx_rate=...)` |
| 配息（再投資） | `fx_avg` **不變**（只增單位數） | `ledger_service.dividend_reinvest` |
| 轉換（同幣別） | **嚴格繼承** A 端 `fx_avg` | `SwitchResult.fx_avg_inherited` |
| 轉換（跨幣別） | **當日 B 幣對 TWD 即期**，並記錄 `cross_rate` | 同上 |
| 現值評價 | **當下即期** `fx_current`（呼叫端傳入） | CHUBB 公式 (7)(8) |

**v2 規範（沿用 v1 且補上 v1 沒寫死的部分）**：

1. **成本側匯率錨定點 = 交易日即期匯率**，寫入該筆 `v2_transactions.fx_rate`，**永久凍結、不可回溯改寫**
   （`CLAUDE.md §2.3` Point-in-Time：禁止用未來匯率回填過去決策）。
2. **評價側匯率 = 評價當下即期**，**不入 `v2_transactions`**，只在 `v2_holdings` 的衍生欄即時取用。
3. **同幣別轉換繼承 `fx_avg`**；跨幣別轉換以 **TWD 歷史成本守恆**反推 B 端成本
   （v1 已實作：`cost_unit_b = (n_redeem × cost_unit_a × fx_avg_a) / (n_added × fx_avg_b)`）。
4. ⚠️ **交易日無匯率報價時（假日／來源失敗）**：**必須 Fail Loud**，
   標記 `fx_is_imputed = true` ＋ `fx_source`，**禁止靜默用前一日**（`CLAUDE.md §1`）。
   ⇒ v1 **未實作**此旗標 → §5 缺口 **G-5**。

**匯率來源與 fallback（實測 `repositories/fund/fx_and_main.py::get_latest_fx`）**：

| pair 類型 | fallback chain |
|---|---|
| **TWD pair**（USDTWD／EURTWD…） | Yahoo → `open.er-api.com` |
| **非 TWD pair** | Yahoo → FRED `DEX*` → `open.er-api.com` → Frankfurter(ECB) |

⚠️ 程式碼自陳：**TWD pair 刻意跳過 FRED 與 Frankfurter** ——
理由是 FRED `DEXTWUS` 已停發、ECB 無 TWD 報價，對 TWD 場景**全是 dead path**。
⇒ **v2 不得「為了對稱」把這兩條加回 TWD 路徑**，那會是一次無意義的延遲放大。

---

## §3. 第 2 項｜指標 SSOT 附錄

### 3.1 客戶逐字指定的四條（照辦，不改寫）

#### 3.1.1 Sharpe Ratio

**客戶指定（逐字照錄）**：
> 年化 252 日；台股無風險利率採「台灣央行 1 年期定存利率」、海外標的採「美國 3 個月國債殖利率（DTB3）」；
> **台幣投海外資產統一以 DTB3 為主、台幣定存為 fallback 並標註**。

**v2 規格**：

| 項目 | 規格 |
|---|---|
| 公式 | `Sharpe = (r̄ − rf) / σ × √252`，`r̄`／`σ` 取自**日對數報酬** |
| 年化 | **252 交易日**（**非** 365 日曆日） |
| 幣別 | 報酬以**原幣** NAV 計算；rf 依標的屬性選取（見下） |
| rf（台股標的） | **台灣央行 1 年期定存利率** |
| rf（海外標的） | **美國 3 個月國債殖利率 `DTB3`** |
| rf（台幣投海外資產） | **`DTB3` 為主**；台幣定存為 **fallback**，且**必須標註**採用了哪一個 |
| 最小樣本 | **250 個交易日**（沿用 v1 `MIN_OBS_SHARPE_SORTINO`） |
| 不足樣本 | 回 `N/A`，**不得**用短窗年化冒充（見 §3.3） |

⛔ **實測到的三個 gap（這一節最重要的部分）**：

**(a) `DTB3` 在本 repo 完全不存在。**
> **量測（可複跑；量測日 2026-09-14）**：
> ```
> git grep -n "DTB3" 9cbf0377 -- '*.py' '*.md' ':!docs/v2/DATA_DICTIONARY.md'
> ```
> → **0 命中**（exit 1）。**正對照**：把 `DTB3` 換成 `DGS3MO`，同一條指令回 **30 命中**
> —— 證明這條指令不是恆回 0 的假檢查。
>
> ⚠️ **2026-09-14 就地更正（有意識的更正，不是漏刪；由獨立稽核抓出）**：
> 本行原寫 ~~`git grep -n "DTB3" -- '*.py' '*.md'` → **0 命中**~~。
> **那條指令不會回 0，因為它沒有把本文件排除掉** —— 本文件自己就反覆寫著這個字串
> （§3.1.1 的客戶原文、規格表、本段、§5 G-8…）。
> ⇒ **讀者照抄複跑，會得到與結論相反的輸出，然後合理懷疑整段更正。**
> **結論本身不變**（`DTB3` 確實不存在於任何程式碼），修的是**那條指令量錯了範圍**：
> 現版本**釘死 rev `9cbf0377`（base）** ＋ **明文排除本文件自身**，兩種寫法都能複跑。
> ⛔ 這是一個「**在文件裡寫一個 token，就會讓量那個 token 的指令失真**」的自我污染陷阱 ——
> 本文件凡是「某某在 repo 裡 0 命中」的量測，**一律必須排除自身或釘 base rev**。
>
> ⛔ **2026-09-14 第三輪就地更正（有意識的更正，不是漏刪；由獨立稽核抓出）**：
> **上面這段第二輪的更正，自己也寫了一個沒有量過的數字。**
> 它原寫 ~~「那條指令今天在本分支上會回 **10**，不是 0 —— 因為這個字串**在本文件裡出現了 10 次**」~~。
> **兩個「10」都不對，而且它們量的還是兩個不同的東西**：
>
> | 宣稱 | 它實際在數什麼 | 第三輪實測 |
> |---|---|---|
> | 「那條指令會回 10」 | `\| wc -l` ＝ **命中行數** | **17 行**（rev ＝本 PR head；全部落在本文件內，`.py` 端 0 行） |
> | 「在本文件裡出現了 10 次」 | `str.count` ＝ **出現次數** | **18 次**（同一 rev；有一行內含兩次，故次數 > 行數） |
>
> **「行數」與「次數」是兩個母體，原句把同一個 10 同時當成兩者用。**
>
> ⚠️ **更要緊的是：`10` 在被寫下的那一秒就已經過期。** 逐 commit 回溯（皆本輪實跑）：
> `d9a2da2`（寫下這句**之前**那一顆）＝ **10 行 / 11 次** ⇒ 「10 行」在那一刻為真；
> **`2114839`（寫下這句的**那一顆**）＝ 15 行 / 16 次** —— 同一顆 commit 一邊新增這段文字、
> 一邊讓它引用的數字增加了 5。**作者量的是自己改之前的檔案。**
>
> ⛔ **這一句就長在 §7.5.3 的同一份 diff 裡，而 §7.5.3 教的正是**
> 「**任何描述本文件自身的計數，必須在定稿後重量一次**」。
> 那條紀律**確實**被套用在 §7.5.2 的三個數字上（每改一次就重量，跑到收斂才定稿），
> **唯獨沒有套用在這一句**。
> ⇒ **教訓第三條，補在 §7.5.3 那兩條後面**：
> **紀律要對「同一份 diff 裡的每一個自我計數」一起套用，不能只套在寫紀律的那一節上。**
> **一條只保護自己那一段的紀律，等於沒有紀律。**
>
> ⚠️ **上表兩個數字同樣是「會漂移的自我計數」**：它們隨本節每一次改寫而變動，
> 本輪已照 §7.5.2 的辦法**改到宣告值 ＝ 實測值才定稿**。
> **引用前請自行重跑**（母體：rev ＝ 本 PR head，範圍 `-- '*.py' '*.md'`，不做自我排除）。
>
> `shared/fred_series.py` 宣告的 3 個月期 series 是 **`DGS3MO`**（3-Month Treasury *Constant Maturity*），
> **不是** `DTB3`（3-Month Treasury Bill, Secondary Market）。**兩者是不同的 FRED series。**
⇒ v2 必須**新增** `FRED_DTB3 = "DTB3"` 至 `shared/fred_series.py`。

**(b) 台灣央行 1 年期定存利率 —— 本 repo 無任何取數來源。**
> **量測**：`git grep -niE "定存|deposit_rate|TW_RF|rediscount|重貼現" -- '*.py'`
> → 命中全部為 UI 說明文字（如「定存替代品」）或**子字串偽陽性**
> （`一定存在` 這個詞包含 `定存`，在 `sources.py`／`tests/` 命中多次）。
> **逐一人工判讀後，無任何一處是台灣利率取數。**
> 另：`CLAUDE.md §2.1` 已記載 CBC `ms1.json` 取數實作**已於 Phase 1.4 實體刪除**，
> 且刪除後「全 repo 已無 CBC ms1.json / EF15M01 的取數實作」。
⇒ v2 必須**新建**一個台灣利率 L1 fetcher。**來源未定** → §5 缺口 **G-8**（需客戶或架構組拍板）。

**(c) v1 現行 rf 用的是 `FEDFUNDS`，且是單一全域值。**
> **量測**：`services/fund_service.py::_RF_ANNUAL`，預設 `0.04`，
> 由 `app.py` / `ui/tab1_macro.py` 呼叫 `set_risk_free_rate(FED_RATE/100)` 注入。
> 程式碼自陳「注入即時無風險利率（**FEDFUNDS**/100）」。
⇒ 與客戶指定的 `DTB3` / 台灣定存**皆不符**。
⇒ 更關鍵：**`_RF_ANNUAL` 是 module-level 全域變數，全站所有基金共用同一個 rf**，
  而客戶要求的是**依標的屬性分流**（台股 vs 海外）。
  ⇒ **v2 必須把 rf 從全域變數改為「每檔標的解析一次」的參數**，這是結構性變更，不是換個常數。
  ⚠️ v1 程式碼自陳此全域變數曾造成**跨測試污染**（測試塞 `value: 50.0` → rf = 50%/年 →
  同 process 內所有 Sharpe 分子被扣 50%），並已加 `[0, 0.25]` 值域防護。
  **v2 的 per-asset 設計同樣必須保留此值域防護。**

#### 3.1.2 基金淨值與同類中位數

**客戶指定（逐字照錄）**：
> 採還原權值（含息），同類中位數錨定公會／晨星標準並標註更新週期。

**v2 規格**：

| 項目 | 規格 |
|---|---|
| NAV | **還原權值（含息）** —— 即配息再投資還原後的序列 |
| 同類中位數 | 錨定**公會（SITCA）／晨星（Morningstar）**的分類標準 |
| 標註 | **必須標註更新週期** |

**v1 現況（實測）**：

- ✅ **還原權值已有實作**：`services/fund_service.py` 自陳
  「把配息『再投資複利』還原進 NAV 序列，供風險指標（σ / Sharpe / Sortino / max_drawdown）用」，
  理由是**除息日 NAV 跳空會被誤判為暴跌** → 高估波動、放大 max_drawdown、壓低 Sharpe。
  ⇒ **v2 沿用，並明定：風險指標一律吃還原序列，顯示用淨值吃原始序列。**

- ⛔ **同類中位數：本 repo 無任何實作。**
  > **量測**：`git grep -niE "同類中位|category_median|peer_median|類別中位" -- '*.py'` → **0 命中**。

- ⛔ **`_src_sitca_meta` 不回傳任何分類或同類統計**（逐行讀該函式確認）。
  它實際寫入的 key 是 **`fund_name`／`nav_latest`**，
  **再加上 provenance 的 `source`（`"SITCA:IN2213.aspx:meta"`）與 `fetched_at`**
  —— 後兩者只在 `fund_name` 有抓到時才寫入（F-PROV-1 phase 15 v19.101）。
  > ⚠️ **2026-09-14 就地更正（由獨立稽核抓出）**：原寫 ~~「只回傳 `fund_name` 與 `nav_latest`」~~，
  > **漏了 provenance 兩欄**。**承重結論（不回傳分類 ⇒ 同類中位數的分組鍵不可能來自 SITCA）完全不受影響**；
  > 但「**只**回傳 X 與 Y」是一句**封閉全稱句**，而它為假 —— 依 §1.3，本文件不該寫這種句子。

- ⚠️ **現有最接近的東西是 `services/peer_rank.py`，但它不是「公會／晨星標準」**：
  它對**「持倉 ∪ 選股池」這個本地小 universe** 做四分位排名，
  程式碼自陳這是「用持倉 ∪ 選股池的同類小 universe 呼叫」。
  ⇒ **分母是使用者自己的基金清單，不是全市場同類** → **不符客戶指定的錨定標準**。

- ⛔ **且 §2.3.4 已實測出 `category` 欄位在 5/8 樣本上是說明書段落而非類別**
  ⇒ 即使接上中位數演算法，**分組鍵本身是壞的**。

⇒ 綜合 §5 缺口 **G-2**：同類中位數需要 (i) 一個乾淨的 category SSOT、(ii) 一個全市場同類 universe 來源、
(iii) 該來源的更新週期。**三者本 repo 皆無。**

**`peer_rank.py` 既有的樣本量誠實規則（v2 應保留，實測）**：

| 同類檔數 n | 輸出 |
|---|---|
| n < 2 | **不給名次**（無從比較） |
| 2 ≤ n ≤ 3 | **只給相對排名 X/n，不分四分位**（程式碼自陳「3 檔捏不出 Q1~Q4，硬分就是造假」） |
| n ≥ 4（`PEER_QUARTILE_MIN_N`） | 真四分位 ＋ **揭露分母「同類 n 檔」** |

另：`PEER_MIN_OBS = 50`（一檔要參與排名的最低有效 NAV 點數）、
`PEER_MIN_SPAN_RATIO = 0.6`（實際跨越年數需 ≥ 視窗 × 0.6）。

#### 3.1.3 本益比（TTM）—— ⚠️ **基金側目前不使用，照客戶更正後的射程處理**

**客戶指定（逐字照錄）**：
> 近四季 EPS 總和；**EPS ≤ 0 統一標註 `N/A（虧損）`**。

**基金側實測結果**：

> **量測 1**（⚠️ **先讀 scope，再讀結論**）：
> ```
> git grep -niE "本益比|forward_pe|pe_ttm|per_ttm|trailing_pe" 9cbf0377 \
>   -- 'services/*.py' 'repositories/*.py' 'repositories/**/*.py'
> ```
> **⛔ 這條指令的 scope 只有 `services/` 與 `repositories/`，不含 `shared/`、不含 `ui/`。**
> 在**該 scope 內**唯一命中是 `repositories/external_market_repository.py` 的一行**退役註解**：
> 「⚠️ 2026-08-28 退役（**有意識的移除，不是漏刪**）：`fetch_yf_forward_pe` / …」
> （與 `CLAUDE.md §2.2` 記載的「兩 fn 已整段刪除」一致）。
>
> **量測 2**：`repositories/financial_repository.py` 是本 repo 唯一抓個股財報的模組，
> 逐行讀其公開 API → `resolve_ticker` 與 `fetch_stock_three_ratios`（**毛利率／營益率／淨利率** QoQ），
> **不含 EPS、不含本益比**。

> **量測 3（2026-09-14 補，把 scope 補齊）**：同一條 pattern 掃 `shared/**` 與 `ui/**`：
> ```
> git grep -niE "本益比|forward_pe|pe_ttm|per_ttm|trailing_pe" 9cbf0377 -- 'shared/**' 'ui/**'
> ```
> → `ui/**` **0 命中**；`shared/**` **1 命中**：
> `shared/macro_buckets.py` 的 `DangerSpec("forward_pe", "Forward P/E (S&P 500)", …, yellow=19.5, red=22.5)`
> （`source="DESIGN:FactSet/Yardeni 25Y 統計 PE_MEAN=16.5 σ=3.0"`，與 §3.2 表中
> 「Forward P/E μ=16.5, σ=3.0」同源）。
>
> ⚠️ **「它是不是活的」—— 據實分三層講，不要含混成一個字**（本輪實測；
> 初稿在這裡寫過「**而且它是活的**」，**那是本組自己的過度宣稱，已撤下**）：
> 1. ✅ **該筆定義存在且未被註解／未被劃掉** —— 它是 `BUCKET_DANGER_SPECS` 這個 list 的一個成員。
> 2. ✅ **它所屬的表確實被 production 消費** —— `BUCKET_DANGER_SPECS` 推導出
>    `SPECS_BY_KEY`，而後者被 `ui/helpers/chart/danger.py`、`ui/helpers/macro/beginner_view.py`、
>    `ui/tab1_macro.py` **真 import**（非註解）。
> 3. ⛔ **但「`forward_pe` 這一列有沒有真的被讀到」本組沒有驗，也不宣稱** ——
>    實測字面 `forward_pe` 在全 repo `*.py` 只有 **2 處**：這筆定義本身，
>    以及 `external_market_repository.py` 的那行退役註解。**沒有任何一處以字面 key 查它**；
>    查表走的是 `SPECS_BY_KEY.get(key)` 這種**執行期動態 key**，**grep 結構上看不到**。
> ⇒ **可說的是「這筆定義在一張活的表裡」，不能說「這筆定義是活的」。** 兩者差一層。
>
> ⚠️ **2026-09-14 就地補（由獨立稽核抓出）**：本節原本**只跑了量測 1、卻沒有寫出它的 scope**，
> 於是一句「在基金儀表板側無實作」讀起來像掃了全 repo。
> **結論的方向不變** —— `forward_pe` 是 **Forward P/E（前瞻，分母用預估 EPS）**，
> 與客戶指定的**本益比 TTM（近四季 EPS 總和）不是同一個指標**，
> 且 `shared/macro_buckets.py` 那一條服務的是**總經面板的 S&P 500 估值燈號**，不是個股／基金持股。
> **但「唯一命中是一行退役註解」這句話，只在原 scope 內為真；補齊 scope 後並不是唯一。**
> ⛔ **一個沒有寫出 scope 的 grep 結論，讀者無從判斷它涵蓋多少** —— 這是本文件 §1.3 自己的規則。

⇒ **判定：客戶指定的「本益比（TTM）」在基金儀表板側無實作、無消費端**
（`shared/macro_buckets.py` 的 `forward_pe` 是**前瞻本益比的總經燈號**，不是 TTM，也不在基金／持股路徑上）。
依 §0 射程，**本文件不為它定義規格** —— 它屬股票／ETF 戰情室。

⚠️ **但有一個真實的交界，必須具名列出，不得當作不存在**：
基金的**持股明細**（`fetch_holdings`）內容**就是個股**，
且 `financial_repository` 已在為這些持股抓財報三率。
⇒ **若 v2 要在基金的持股明細上顯示本益比，那一刻它就落入基金側。**
⇒ 列為 §4.7 跨儀表板待協調項 **X-3**（**本文件不單方決定**）。

#### 3.1.4 配息殖利率

**客戶指定（逐字照錄）**：
> 近一年累計已除息總額 / 最新收盤價；**不配息標的顯示 `N/A`**。

**v2 規格**：

| 項目 | 規格 |
|---|---|
| 公式 | `div_yield_pct = Σ(近一年已除息金額) / 最新淨值 × 100` |
| 分子 | **近一年累計「已除息」總額** —— 只算已過除息日者，**未來配息不計** |
| 分母 | **最新收盤價（淨值）** |
| 幣別 | 分子分母**同為原幣**（比率，故單位無關；但**禁止**跨幣別混算） |
| 不配息標的 | **`N/A`**（不得顯示 0%） |

**v1 現況（實測，與客戶指定一致）**：
- `services/fund_service.py`：`div_yield_pct = round(annual_div / nav_current * 100, 2)`，
  就地註解自陳「殖利率：配息 ÷ **現值**（定義）」 ⇒ **分母定義與客戶一致**。
- **來源優先序**：`services/health/dividend.py` 自陳
  「1. **MoneyDJ wb05 官方** `moneydj_div_yield`」為主，**本算為 fallback**
  （`services/fund_invest_calc.py` 就地自陳「本算 fallback；主源 moneydj_div_yield wb05」）。
- ✅ **已有雙演算法對帳**：`services/reconcile.py::reconcile_dividend_yield`，
  `services/fund_service.py` 注入 `div_yield_reconcile`，
  判準為「絕對 0.1 個百分點／相對 5%」（`fund_invest_calc.py` 自陳）。
  ⇒ **v2 沿用此對帳，並在 UI 顯示 agree／disagree 四態**（v1 已有此 chip）。

⚠️ **一個 v1 與客戶指定的潛在落差，具名列出但不自行拍板**：
客戶寫「近一年**累計已除息總額**」，而 v1 主源是 **MoneyDJ wb05 掛牌的 `moneydj_div_yield`**
（`fund_invest_calc.py` 自陳「不是掛牌值」指的是本算 fallback）。
**掛牌殖利率的定義可能是「年化配息率」而非「近一年實際累計」** —— 兩者在配息頻率變動時會不同。
⛔ **本文件未查證 MoneyDJ wb05 的確切定義**（需打外部 API，本階段禁止）→ §5 缺口 **G-9**。

### 3.2 其餘基金側指標（本輪盤點到的）

> ⚠️ **本節是分類敘述，不是窮舉。** 未涵蓋：`services/` 底下約 50 個模組中未被本輪讀取者。

| 指標 | 公式／規則 | 來源 | 頻率 | 幣別 | fallback |
|---|---|---|---|---|---|
| **Sortino** | `(r̄ − MAR) / σ_D × √252`，`σ_D = √((1/N)·Σ[min(0, rₜ−MAR)]²)`，**MAR = rf（與 Sharpe 分子相同）** | 自算 | 日 | 原幣 | MoneyDJ wb07 |
| **σ（年化波動）** | 日報酬標準差 × √252 | 自算（**吃配息還原序列**） | 日 | 原幣 | wb07 |
| **max_drawdown** | 峰谷最大跌幅 | 自算（**吃配息還原序列**） | 日 | 原幣 | wb07 |
| **1Y 含息報酬** | 四層 fallback（見下） | `services/fund_total_return.py` | 日 | 原幣 | 見下 |
| **四分位排名** | 同類年化報酬排序 → 四分位 | `services/peer_rank.py` | 日 | 原幣 | 樣本不足則降級 |
| **吃本金判定** | `real_return_pct = total_return_pct − div_yield_pct`；含息報酬 < 配息率 → 配息來自本金 | **`services/health/dividend.py::classify_eating_principal`**（canonical；`services/fund_service.py` 是 **caller**，lazy import 後呼叫，**不是定義處**）| 日 | 原幣 | — |

**1Y 含息報酬的四層 fallback（`services/fund_total_return.py` 自陳，權威→次選）**：
1. `perf["1Y"]` —— wb01 真 1Y／本地還原淨值法注入
2. `ret_1y_total` —— 本地含息計算（可能短窗年化）
3. `ret_1y` —— 純 NAV 變化率（**不含息**）
4. NAV 序列年化 —— **最後手段**，跨度須 ≥ `RET_1Y_EXTRAPOLATE_MIN_DAYS`，scale cap 2×

⚠️ **v1 就地記載的事故（v2 必須保留此防線）**：
> 2026-08-14 稽核 E1：第 4 層原本 **30 天就敢 ×12 外推**，大表因此印出 **+201%** 的台幣基金。
> 現在跨度不足半年直接回 `(None, SRC_TOO_SHORT)`。

⇒ **v2 規範：任何外推必須有最小跨度閘門 ＋ scale cap，且來源標籤必須自己講話。**
v1 已把「來源標籤」做成**會印給使用者看的字串**（官方值以「MoneyDJ 官方」開頭、自算值以「自算」開頭），
程式碼自陳理由是「使用者完全無從判斷這個報酬率到底是官方公布的還是本站推算的」。**v2 沿用。**

### 3.3 `N/A` 觸發條件完整表

> **這是客戶明確要求的「各指標觸發 `N/A` 的完整條件表」。**
> ⚠️ 下表為**本輪從程式碼與客戶指令彙整**；**未涵蓋**未被本輪讀取的模組（§3.2 前言）。

| 指標 | `N/A` 觸發條件 | 顯示 | 依據 |
|---|---|---|---|
| **Sharpe** | 有效觀測 < **250** 交易日 | `N/A（樣本不足 n/250）` | `MIN_OBS_SHARPE_SORTINO` |
| **Sharpe** | rf 解析失敗或超出 `[0, 0.25]` | `N/A（無風險利率不可用）` | `_RF_ANNUAL_MAX` 防護 |
| **Sortino** | 同 Sharpe，**且**低於 MAR 的樣本 < 5 筆 | `N/A（下檔樣本不足）` | v1 docstring |
| **σ / max_drawdown** | NAV 序列 < 最小點數 | `N/A（序列過短）` | — |
| **任何年化指標** | NAV 來自 `cache/nav/` 稀疏快取且 `supports_annualized = False` | `N/A（序列稀疏，年化不可信）` | `fetch_nav` 就地判定 |
| **本益比 TTM** | **EPS ≤ 0** | **`N/A（虧損）`** | **客戶逐字指定** |
| **本益比 TTM** | 近四季 EPS 不足四季 | `N/A（季數不足）` | 客戶指定的延伸 |
| **配息殖利率** | **標的不配息** | **`N/A`**（**不得顯示 0%**） | **客戶逐字指定** |
| **配息殖利率** | 最新淨值 ≤ 0 或缺值 | `N/A（無淨值）` | `CLAUDE.md §4.4` 大數除小數 guard |
| **同類中位數／四分位** | 同類 n < 2 | `N/A（無同類可比）` | `peer_rank.py` |
| **四分位** | 2 ≤ n ≤ 3 | **只給 X/n，不給四分位** | `peer_rank.py`（非 N/A，是降級） |
| **四分位** | 該檔有效 NAV 點數 < **50** | 該檔不參與排名 | `PEER_MIN_OBS` |
| **1Y 含息報酬** | 四層全敗，或跨度 < 最小外推門檻 | `N/A（期間不足）`＋`SRC_TOO_SHORT` | `fund_total_return.py` |
| **任何指標** | 上游全部 fallback 失敗 | **`raise` 或回 `None` ＋ 來源旗標**，⛔ **禁止 `fillna(0)`** | `CLAUDE.md §1` |

**v2 硬規則（三條，來自 `CLAUDE.md §1`）**：
1. `N/A` **必須帶原因**。光一個 `N/A` 不合格 —— 使用者無從判斷是「還沒載入」還是「算不出來」。
2. **`N/A` ≠ 0 ≠ 空白**。三者在 UI 上必須可區分（v1 已有 `⬜ 資料不足` 慣例，實測 `services/`／`shared/` 下
   `資料不足` 113 處、`⬜` 83 處）。
3. **「未點擊載入」用灰色、「系統真出錯」才用紅色**（`CLAUDE.md §-1.5.1c` v3 `02`）。

---

## §4. 第 5 項｜持倉與交易資料模型

### 4.1 `v2_transactions`

**定位**：append-only 事件流水帳。**唯一的事實輸入**；`v2_holdings` 由它推導。

| 欄位 | 型別 | 必填 | 語意 | 來源 |
|---|---|---|---|---|
| `txn_id` | str (UUID) | ✅ | 主鍵 | 新生成 |
| `account_id` | str | ✅ | 保單／帳戶識別碼 | v1 `policy_id` |
| `asset_class` | str | ✅ | **`fund`**（基金側只寫此值） | ⚠️ 完整列舉見 §4.7 X-1 |
| `instrument_code` | str | ✅ | 基金代碼 | v1 `code` |
| `txn_type` | str | ✅ | 見下方值域 | v1 `action` 映射 |
| `trade_date` | date | ✅ | 交易日（**除息以除息日為準**） | v1 `date` |
| `units` | float | 條件 | 單位數（±） | v1 `units` |
| `price_orig` | float | 條件 | 成交淨值（**原幣**） | v1 `nav_at_action` |
| `price_ccy` | str | ✅ | `price_orig` 的 ISO 幣別 | v1 政策表 `currency` |
| `fx_rate` | float | ✅ | **交易日即期，TWD per 原幣**（**凍結，不可回溯改寫**） | v1 `fx_avg` 輸入 |
| `fx_is_imputed` | bool | ✅ | 匯率是否為補值 | ⛔ **v1 無此欄**（§5 G-5） |
| `fx_source` | str | ✅ | 匯率來源（`yahoo`／`er_api`…） | `get_latest_fx` |
| `amount_twd` | float | 條件 | 台幣金額 | v1 `twd` |
| `fee_orig` | float | 選填 | 費用（原幣） | v1 `fee` |
| `fee_ccy` | str | 條件 | 費用幣別 | ⛔ **v1 未宣告**（§5 G-4） |
| `div_per_unit` | float | 條件 | 每單位配息（原幣） | v1 `models/ledger.Transaction` |
| `note` | str | 選填 | 備註 | v1 `note` |
| `source` | str | ✅ | provenance | `CLAUDE.md §2.2` |
| `recorded_at` | datetime | ✅ | 寫入時間（UTC） | — |

**`txn_type` 值域（v2，封閉列舉）**：

| v2 值 | 語意 | v1 對應 |
|---|---|---|
| `buy` | 申購／買進 | `buy`、`subscribe` |
| `sell` | 贖回／賣出 | `sell` |
| `dividend_cash` | 現金配息 | `dividend`、`dividend_cash` |
| `dividend_reinvest` | 配息再投資 | `dividend_reinvest` |
| `switch_out` | 轉換出 | `switch_out` |
| `switch_in` | 轉換入 | `switch_in` |
| `fee` | 單獨收取的費用 | `fee` |
| `import` | 期初匯入（遷移用） | 無（新增） |

⚠️ **v1 有兩套並存的型別命名，v2 必須收斂成一套**（實測）：
- `repositories/ledger_repository.py::KNOWN_ACTIONS` = `buy`／`sell`／`dividend`／`fee`／`fx`
- `models/ledger.py::_TXN_TYPES` = `subscribe`／`dividend_cash`／`dividend_reinvest`／`switch_out`／`switch_in`

**兩套不一致**：Sheets 端有 `fx` 但無 switch；dataclass 端有 switch 但無 `fx`／`sell`。
⛔ 且 `ledger_repository` 自陳「**不在列表內視為自訂類型（不會被攔截**，但統計時可能漏算）」
⇒ **v2 必須改為封閉列舉 ＋ 寫入時 reject**（`models/ledger.Transaction.__post_init__` 已有 `raise` 前例，沿用該做法）。
⇒ 列為 §5 缺口 **G-10**（`fx` 這個 v1 類型的語意本文件**未查證**，不自行映射）。

### 4.2 `v2_holdings`

**定位（母法明訂）**：**全系統持倉單一事實來源**，由 `v2_transactions` 推導；
基金與 ETF **皆寫入此表**，以 `asset_class` 區分。**⛔ 嚴禁在各儀表板端各自算一套。**

| 欄位 | 型別 | 語意 | 推導自 |
|---|---|---|---|
| `account_id` | str | ┐ 複合主鍵 | — |
| `asset_class` | str | │ | — |
| `instrument_code` | str | ┘ | — |
| `units` | float | 持有單位數 | Σ 交易 |
| `cost_unit_orig` | float | **加權移動平均**單位成本（原幣） | §4.3 |
| `cost_ccy` | str | 成本幣別 | — |
| `fx_avg` | float | **加權移動平均**買入匯率（TWD per 原幣） | §4.3 |
| `cost_unit_with_div` | float | 含息平均單位成本（原幣） | §4.4 |
| `net_investment_twd` | float | 淨投資額 = `cost_unit_orig × units × fx_avg` | CHUBB (4) |
| `dividends_received_twd` | float | 累計已領現金配息（TWD） | Σ 配息 |
| `realized_pnl_twd` | float | 已實現損益（TWD） | §4.3 |
| `last_txn_date` | date | 最後一筆交易日 | max |
| `derived_at` | datetime | 推導時間 | — |

**衍生欄（不落地，評價時即時算）**：
`nav_current`(5)／`value_orig`(6) = `units × nav_current`／`fx_current`(7)／
`value_twd`(8) = `value_orig × fx_current`／`roi_price`(9) = (8)/(4) − 1／
`roi_total`(11) = (8) / (`units × fx_avg × cost_unit_with_div`) − 1

> **這 11 條編號直接沿用 v1 `services/ledger_service.py` 檔頭自陳的「CHUBB 安達人壽 11 欄位公式（圖片實證）」**，
> **未改寫**。v1 已完整實作，v2 的工作是**把它從 service 層的記憶體物件變成持久化的表**。

⚠️ **物化 vs 即時推導（需拍板，本文件給推薦但不單方決定）**：
v1 `ledger_service` **零快取**，每次重算（§2.4.4）。
**總管推薦：物化 `v2_holdings` ＋ 由 `v2_transactions` 的寫入觸發重算。**
理由：(a) 母法要求它是「單一事實來源」，一個每次重算的記憶體物件不構成「來源」；
(b) 延遲正比於交易筆數，隨帳齡線性劣化。
⚠️ **代價**：物化引入「表與流水帳不同步」的風險 → **必須有一致性檢查**（重算並比對）。

### 4.3 成本計算：加權移動平均法（客戶定死）

**客戶指定**：成本計算統一強制採「**加權移動平均法**」，已實現／未實現損益演算法全站統一。

✅ **v1 已完整實作此法**（實測 `services/ledger_service.py`），v2 **沿用公式、不重新發明**：

**買進（增加單位）** —— 三個量同時做單位數加權平均：
```
cost_unit_new        = (old_units × cost_unit_old        + new_units × nav) / (old_units + new_units)
fx_avg_new           = (old_units × fx_avg_old           + new_units × fx_rate) / (old_units + new_units)
cost_unit_with_div_new = (old_units × cost_unit_with_div_old + new_units × nav) / (old_units + new_units)
```
> ⚠️ 首次買入時 `cost_unit` 與 `cost_unit_with_div` **必相等**（v1 docstring 自陳）。

**賣出（減少單位）**：
```
cost_unit / fx_avg / cost_unit_with_div  →  【不變】   （加權平均按比例贖回保持）
units                                     →  減少
realized_pnl_twd += units_sold × (nav_sell × fx_sell − cost_unit × fx_avg)
```
> **這是加權移動平均法與 FIFO 的分水嶺**：賣出**不消耗特定批次**，只按比例縮減部位，
> 單位成本**維持不變**。⇒ 見 §4.6 對帳差異。

**轉換（switch）**：
- **同幣別**：B 端 `fx_avg` **嚴格繼承** A 端 `fx_avg`（TWD 視角損益不失真）
- **跨幣別**：B 端 `fx_avg` 採當日 B 幣對 TWD 即期，並記錄 `cross_rate`
- **A 端**：`cost_unit` / `fx_avg` / `cost_unit_with_div` **皆不變**，`units` 減少
- **B 端成本反推（TWD 歷史成本守恆）**：
  ```
  cost_unit_b = (n_redeem × cost_unit_a × fx_avg_a) / (n_added × fx_avg_b)
  ratio = cost_unit_with_div_a / cost_unit_a
  cost_unit_with_div_b = cost_unit_b × ratio
  ```

### 4.4 除息（現金 vs 成本扣減）與配息再投資滾入

**客戶要求「明定」**，v1 已有實作（CHUBB 規範），v2 照錄：

#### (a) 現金配息 `dividend_cash`
```
dividends_received_twd += div_per_unit × units × fx_rate
units                   →  【不變】
cost_unit               →  【不變】          ← 帳面成本不動
cost_unit_with_div      →  【下調】          ← 只動含息成本
```
**下調公式（CHUBB 規範，v1 逐字實作）**：
```
virtual_units      = (div_per_unit × units) / nav_at_div      ← 虛擬再投資單位數
new_cost_with_div  = old_cost_with_div × units / (units + virtual_units)
```
⚠️ **`nav_at_div` 為 `None` 時**：v1 **只累計 TWD 配息、不下調 `cost_unit_with_div`**。
⇒ **v2 必須在此加旗標**（否則含息報酬會偏高卻無人知道），見 §5 G-11。

> **語意**：現金配息**不扣減帳面成本**（`cost_unit` 不變），
> 但**會扣減含息成本**（`cost_unit_with_div` 下調）——
> 因此 `roi_price`(9) 與 `roi_total`(11) **刻意給出不同的數字**，這是設計，不是 bug。

#### (b) 配息再投資 `dividend_reinvest`
```
new_units          = (div_per_unit × units) / nav_at_div
units              += new_units
cost_unit          →  加權平均滾入（以 nav_at_div 為新單位成本）
cost_unit_with_div →  加權平均滾入（同上）
fx_avg             →  【不變】                ← 再投資不涉及新的台幣匯入
```
> ⚠️ **`fx_avg` 不變是關鍵**：再投資沒有新的台幣換匯行為，
> 若在此更新 `fx_avg`，`net_investment_twd` 會憑空變大。

### 4.5 多幣別換算匯率錨定點

見 **§2.6.3**（成本側＝交易日即期並凍結；評價側＝當下即期；轉換依同幣別／跨幣別分流）。

### 4.6 與券商常見 FIFO 對帳單的差異說明（**文案草稿**）

> **以下為要顯示給使用者看的文案草稿**。客戶指定要附，此處為初稿，**待 UI 線框階段定版**。

---
**為什麼這裡的成本和你的對帳單不一樣？**

我們用的是「**加權平均成本法**」，而多數券商／保險公司的對帳單用「**先進先出法（FIFO）**」。
**兩種算法都是對的，只是看事情的角度不同。**

**差在哪裡**

假設你分兩次買進同一檔基金：
- 第 1 次：100 單位，每單位 10 元
- 第 2 次：100 單位，每單位 20 元

接著你賣掉 100 單位，當時淨值 25 元。

| | 加權平均法（本站） | FIFO（常見對帳單） |
|---|---|---|
| 賣出時認定的成本 | 每單位 **15 元**（(10+20)÷2） | 每單位 **10 元**（先買的先賣） |
| 這筆已實現損益 | (25−15) × 100 = **1,000 元** | (25−10) × 100 = **1,500 元** |
| 剩下 100 單位的成本 | 每單位 **15 元** | 每單位 **20 元** |

**重點：兩邊的「總損益」最後會一樣，差的只是「什麼時候認列」。**
FIFO 會讓你在早期賣出時看到比較大的已實現獲利，但留下成本比較高的部位；
加權平均法則讓每一次賣出都反映你的**平均持有成本**。

**為什麼本站選加權平均法**

1. 你的部位常常來自**定期定額**與**配息再投資**，批次多到難以逐筆追蹤，
   平均成本更能回答「我這檔基金平均買在哪裡」。
2. 你的保單帳戶本來就是用平均成本結算的（安達 CHUBB 格式），**與你的保單對帳單一致**。
3. 跨幣別時，平均匯率（`fx_avg`）能讓「台幣投入 vs 台幣現值」的比較不失真。

**所以你該看哪一個？**
- 想核對**券商／保險公司帳務** → 看對方的對帳單。
- 想知道**自己買得好不好、現在賺賠多少** → 看本站。

⚠️ **本站不會、也不應該用來報稅。** 稅務認列請以發行機構出具的正式文件為準。

---

> ⚠️ **文案草稿的一項未查證事項**：上文宣稱「你的保單帳戶本來就是用平均成本結算的（安達 CHUBB 格式）」。
> 此句依據為 v1 `services/ledger_service.py` 檔頭自陳「對齊 CHUBB 安達人壽 11 欄位公式（**圖片實證**）」。
> **本文件未見到該圖片，未獨立查證**（`CLAUDE.md §-2` 規則 6）。
> ⛔ **定版前必須向客戶確認**，否則這是一句對使用者講的、沒有出處的話。

### 4.7 跨儀表板待協調項（⛔ 本文件不單方決定）

> 母法明訂 `v2_holdings` 是**全系統**單一事實來源，基金與 ETF 皆寫入。
> 以下欄位**跨儀表板才能拍板**，本文件**只列出基金側的需求與不能單方決定的理由**。

| ID | 項目 | 基金側的需求 | 為什麼不能由我們單方決定 |
|---|---|---|---|
| **X-1** | `asset_class` **完整列舉** | 基金側只需寫入 `fund` 一個值；需要它是**封閉列舉**且**基金側的值不會被改名** | 完整列舉必須涵蓋股票／ETF 側的所有類別（`stock`／`etf`／…）。本文件**未讀**股票側，列舉若由我們定，必然遺漏 |
| **X-2** | **ETF 專屬欄位** | 基金側**不需要**，但需保證這些欄位對 `asset_class='fund'` 列**可為 NULL**、且不影響基金側推導 | ETF 需要哪些欄位只有股票側知道 |
| **X-3** | 基金**持股明細**上的個股指標（本益比 TTM 等） | 若 v2 要在基金持股明細顯示個股本益比，需要股票側的 EPS／PE SSOT | 基金側**無 EPS／PE 實作**（§3.1.3 實測）。重複實作一套 = 違反母法「嚴禁各自算一套」 |
| **X-4** | `instrument_code` **命名空間** | 基金代碼形態多樣（6 碼數字境內、英數保單商代碼如 `TLZF9`、MoneyDJ 複合 key `xxx-yyy`） | 與股票 ticker（`2330.TW`／`SPY`）**可能碰撞**。需要跨側的唯一鍵策略（前綴？複合鍵？） |
| **X-5** | **已實現損益的統一演算法** | 基金側採加權移動平均（客戶定死，§4.3） | 母法要求「已實現／未實現損益演算法**全站統一**」⇒ 股票／ETF 側**必須採同一法**。需確認股票側不是 FIFO |
| **X-6** | `v2_holdings` **寫入權責** | 基金側需要「基金列由基金側推導寫入」 | 若兩側各自寫同一張表，需要明確的寫入邊界與衝突處理（`CLAUDE.md` `PROCESS.md §3` 寫入端序列化） |

**基金側的唯讀引用方式（母法：基金儀表板只以「收益視角摘要卡片」唯讀引用 `v2_holdings`，點擊 Deep Link 跳轉）**：

| 項目 | 規格 |
|---|---|
| 讀取 | 只讀 `asset_class IN ('fund', …)`；**摘要卡片不寫入** |
| 欄位 | 只需 `instrument_code`／`units`／`net_investment_twd`／`value_twd`／`roi_total` |
| Deep Link | 由基金側提供 `instrument_code` → 基金詳情頁的連結；**跨側跳轉的 URL 契約需 X-1 先定案** |
| ⛔ 禁止 | **不得**在摘要卡片端重算任何損益（母法：嚴禁各自算一套） |

---

## §5. 缺口清單（需拍板／需另行派工）

> **本節是本文件最重要的輸出之一。** 每一列都是「客戶指定的規格與 repo 實況對不上」的具名落差。
> ⛔ **本節不構成動工授權**（`CLAUDE.md §-1`）。

| ID | 缺口 | 證據（本輪實測） | 性質 |
|---|---|---|---|
| **G-1** | 自算風險指標需 **250** 交易日，但預設取數只給 **30** 筆 | `MIN_OBS_SHARPE_SORTINO=250`；`snap.json` 8/8 檔 `nav_points=30` | 架構（長序列來源） |
| **G-2** | **同類中位數無實作、無來源、且分組鍵 `category` 已污染** | `同類中位\|category_median\|peer_median` → 0 命中；`_src_sitca_meta` **不回傳任何分類**（只有 `fund_name`/`nav_latest` ＋ provenance 兩欄，見 §3.1.2）；`snap.json` 5/8 `category` 為說明書段落 | **客戶指定項無法實現** |
| **G-3** | 保單政策表**無 `units`／無 `nav_at_buy`**，無法純自動遷移 | `docs/POLICY_SHEETS_SETUP.md` 9 欄 | 遷移 |
| **G-4** | v1 `fee` 欄**未宣告幣別** | `LEDGER_COLS` 9 欄無 `fee_ccy` | 資料模型 |
| **G-5** | 匯率補值**無旗標** | v1 無 `fx_is_imputed` | 違 `CLAUDE.md §1` |
| **G-6** | 無交易日曆 → **算不出真實缺漏率** | `CLAUDE.md §4.5` 自陳無 calendar lib | 量測能力 |
| **G-7** | `data_cache` 月頻序列落後約 5 個月 | `M2SL`／`CPIAUCSL` 最後一期 2026-04-01 vs 量測日 2026-09-14 | **未查證**是否為 production 路徑 |
| **G-8** | **台灣央行 1 年期定存利率無任何取數來源** | `DTB3` 0 命中；`定存` 命中全為 UI 文案或 `一定存在` 偽陽性；CBC 取數已刪除 | **客戶指定項無來源** |
| **G-9** | MoneyDJ wb05 `moneydj_div_yield` 的**確切定義未查證** | 需打外部 API，本階段禁止 | 定義風險 |
| **G-10** | v1 交易型別**兩套並存且不一致**，且**不攔截未知值** | `KNOWN_ACTIONS` vs `_TXN_TYPES`；`ledger_repository` 自陳不攔截 | 資料完整性 |
| **G-11** | 現金配息在 `nav_at_div=None` 時**不下調含息成本且無旗標** | `ledger_service` 自陳 | 違 `CLAUDE.md §1` |
| **G-12** | rf 是 **module 全域**，無法 per-asset 分流 | `_RF_ANNUAL`；客戶要求台股／海外分流 | 結構性 |

---

## §6. 母法修正提案單

**本階段無母法修正提案。**

本文件的產出**未觸及任何既有檔案** —— 只新增 `docs/v2/DATA_DICTIONARY.md`。
§5 的 12 個缺口**全部可以在階段 2 之後、於母法現行條文內處理**，**不需要修改母法**。

⚠️ 惟 **G-2** 與 **G-8** 是「**客戶逐字指定的規格，在本 repo 沒有可實現的資料來源**」，
**不是**母法問題，而是**需要客戶裁決的業務需求衝突**
（`CLAUDE.md §-1.5.1c` v3 `03`-2 ②「核心付費資料源永久失效的替代方案」的同型情境）。

**總管推薦方案（依 `CLAUDE.md §-1.5.1b` 裁決二，請示必須附推薦，不得只丟選項）**：

- **G-8（台灣無風險利率）**：**建議先以 FRED 可取得的台灣利率替代序列上線，並在 UI 明確標註「非央行定存牌告利率」**，
  待央行來源接上後替換。理由：Sharpe 對 rf 的敏感度遠低於對 σ 的敏感度，
  但「**完全沒有 rf**」會讓台股標的的 Sharpe 整條算不出來，代價更大。
  ⚠️ **本推薦未查證 FRED 是否真有合適的台灣利率 series**（需打 API），**屬待驗事項**。
- **G-2（同類中位數）**：**建議階段 2 先交付「四分位排名（本地 universe）＋ 明確標註分母」**，
  **不冒充公會／晨星中位數**；同時另案評估 SITCA／Morningstar 的分類與同類統計取得方式。
  理由：`peer_rank.py` 已有樣本量誠實規則，可立即用；
  而冒充一個沒有來源的「同類中位數」正是 `CLAUDE.md §1` 明禁的造假。

---

## §7. 交件自陳：做了什麼／刻意沒做什麼／沒量到什麼

### 7.1 做了什麼

- 盤點基金側資料源（§2.1）、逐儲存體欄位字典（§2.2）、實測歷史缺漏率（§2.3）、
  冷熱載入延遲（§2.4）、v1→v2 遷移路徑（§2.5）、多幣別與匯率錨定點（§2.6）。
- 指標 SSOT：客戶逐字指定的四條逐條落規格（§3.1）、其餘基金側指標（§3.2）、`N/A` 完整條件表（§3.3）。
- `v2_transactions` 完整欄位（§4.1）、`v2_holdings` 與 CHUBB 11 式（§4.2）、
  加權移動平均法（§4.3）、除息與再投資滾入（§4.4）、FIFO 差異文案草稿（§4.6）、
  跨儀表板待協調項 6 項（§4.7）。
- 具名缺口 12 項（§5）。
- **自行實作 pure-python parquet 解碼器**並做四道驗證（§1.2），否則 `data_cache/` 的數字全部拿不到。

### 7.2 ⛔ 刻意沒做什麼

- **沒有建立任何 `.py`／`src/`／`v2_migrations/`**，沒有動任何資料庫。
- **沒有繪製高保真視覺稿，沒有寫任何前端代碼。**
- **沒有修改任何既有檔案** —— 本 PR 只新增 `docs/v2/DATA_DICTIONARY.md` 一個檔。
- **沒有動 16 個 `ui/tab*.py`，沒有動五個 `ui/views/page_0*.py`**（已實測確認五頁均被 `app.py` import ＝ 線上 UI）。
- **沒有對 Google Sheets 做任何操作**（含唯讀 —— 本環境無憑證）。
- **沒有打任何外部 API。**
- **沒有讀取姊妹 repo** `my-stock-dashboard` 任何內容（scope 更正後，clone 留置未動）。
- **沒有替股票／ETF 側決定任何欄位**（改列 §4.7 待協調）。
- **沒有為本益比 TTM 定義基金側規格**（實測其無基金側消費端，§3.1.3）。

### 7.3 ⚠️ 沒量到什麼（以及為什麼）

| 沒量到 | 為什麼 |
|---|---|
| **實際網路延遲**（冷／熱載入的牆鐘時間） | 禁止打外部 API。§2.4 全部是**程式碼宣告值** |
| **Google Sheets 上的實際列數與缺漏率** | 無憑證，且禁止寫入 |
| **基金 NAV 的歷史缺漏率** | 唯一本地語料 `cache/nav/` **只有 1 檔、10 個點橫跨 15 年**，不是可統計的語料（§2.3.3） |
| **排除假日後的真實抓取失敗率** | 無交易日曆（G-6）。§2.3.1 的百分比是**含假日的上界** |
| `fred_indicators.parquet` 是否為 production 路徑 | 未查證（G-7） |
| MoneyDJ wb05 殖利率的確切定義 | 需打 API（G-9） |
| v1 `action='fx'` 的語意 | 未查證，故 §4.1 **未自行映射**（G-10） |
| CHUBB「圖片實證」的原始出處 | 未見到該圖片（§4.6 末） |
| `pool_repository` / `portfolio_perf_repository` 逐欄 schema | 射程外，§2.5 標為「未逐欄盤點」 |

### 7.4 ⚠️ 本文件的效力限制

- **單組產出，未經第二組獨立複驗**（`CLAUDE.md §-2` 規則 6）。
- 所有量測值**標日期、標範圍**；**引用前請現場重量**（姊妹 repo `my-stock-dashboard` §8.2.A.0
  規則 4 的同一精神；⚠️ **該節不在本 repo 的 `CLAUDE.md` 裡**，出處見 §7.5.6）。
- 本文件**刻意不寫**「只有 N 處」「全部都是 X」這類可被一條 grep 推翻的全稱句；
  凡盤點一律為**分類敘述 ＋ 明列未涵蓋範圍**。
- ⛔ 在獨立稽核完成前，本文件任一句**不得**被當成「已查證的事實」去支撐實作決策。

### 7.5 本文件自身的路徑引用：已逐一驗證，但**無機器守衛**

本 repo 有一支守衛 `tests/test_constitution_file_refs.py`，會讓「引用了不存在的檔案」在 CI 轉紅燈。
**但本文件不在它的射程內** —— 詳見下方「這支守衛實際上是什麼」。

#### 7.5.1 這支守衛實際上是什麼（**比原稿寫的更強，這一點對 v2 是好消息**）

它**不只是**一份寫死的清單。實測（rev `9cbf0377`）它有**兩道**互相咬合的機制：

| # | 機制 | 實作（實測符號名） |
|---|---|---|
| 1 | **寫死的登記清單** | `CONSTITUTION_FILES`（tuple，實測**只有兩個成員**：`CLAUDE.md`、`EXCEPTIONS.md`） |
| 2 | **全 repo 標記掃描 ＋ 雙向綁定** | 掃全 repo markdown 找檔頭標記 `<!-- CONSTITUTION-FILE -->`，與 `CONSTITUTION_FILES` **兩份名單必須完全相等**；**帶標記卻沒登記** 紅、**登記了卻沒標記** 也紅 |

> ⚠️ **2026-09-14 就地更正（有意識的更正，不是漏刪；由獨立稽核抓出）**：
> 原稿寫 ~~「（實測其 `_CONST_FILES`）」~~ —— **`_CONST_FILES` 這個符號全 repo 不存在**。
> **實測**：`git grep -n "_CONST_FILES" 9cbf0377` → **0 命中**；
> 在本分支上跑同一條指令，**唯一命中就是原稿那句話自己**。真正的符號是 **`CONSTITUTION_FILES`**。
> ⛔ **這正是 `CLAUDE.md` 反覆記載的那個失效模式的教科書版本**：
> **grep 一個不存在的符號名 → 回 0 命中 → 把「查不到」寫成「我實測過」。**
> **「查錯地方的空輸出」與「真的沒有」長得一模一樣**，而原稿沒有跑正對照去分辨這兩者。
> **實質結論（那個 tuple 確實只有 `CLAUDE.md` ＋ `EXCEPTIONS.md`）經重量後正確** ——
> 錯的是「實測」二字所指的**對象**。
> **本輪的正對照**：`CLAUDE.md` 與 `EXCEPTIONS.md` 檔頭前 20 行各含 **1** 行獨立的
> `<!-- CONSTITUTION-FILE -->`；本文件 **0** 行 —— 三個數字一起印出來，才分得出「0」是哪一種 0。

⇒ **本文件不在其射程內**（未登記、也未帶標記），**它的路徑引用沒有任何機器在守。**

📌 **但機制 2 給了 v2 一條現成的出路（原稿完全沒提到）**：
若日後要讓某份 v2 文件受這支守衛保護，**不需要改寫守衛**，只要做**兩件事**：
**(1)** 在該檔**檔頭前 20 行**加一行獨立的 `<!-- CONSTITUTION-FILE -->`；
**(2)** 把它登記進 `CONSTITUTION_FILES`，**並同步在 `_MIN_LIVE_TIER1_PER_FILE` 與
`_MIN_BYTES_PER_FILE` 兩個字典各補一個 key**（實測另有一條 `test_per_file_floor_keys_match_registered_files_exactly`
要求三者的 key 完全一致，漏補會紅）。
⚠️ **這兩件事必須在同一個 PR 內做完**：雙向綁定意味著**只做 (1) 會紅、只做 (2) 也會紅**。
⛔ **本輪刻意沒有做這件事** —— 它要改 `tests/test_constitution_file_refs.py`，
**在本次的檔案邊界外**（本 PR 只准新增 `docs/v2/DATA_DICTIONARY.md` 一個檔）。**登記 ≠ 動工**（`CLAUDE.md §-1`）。

#### 7.5.2 path-like token 的定義（原稿從未寫明，本輪補上）

⚠️ **原稿寫了「共 58 個」卻沒有定義什麼叫 path-like token，因此那三個數字無法被獨立複跑。**
獨立稽核實測：只有在「**排除本文件自身路徑**」時才得到 58/48/10，直觀讀法得 59/49/10 ——
**同一份文件、兩個讀法、兩組數字，而文件沒說它用的是哪一個。**

**本輪把定義寫死成一支可複跑的腳本**（下方 7.5.4 逐字附上）。該定義下的實測結果：

> **總計 `77` 個 unique path-like token —— `63` 個直接存在，`14` 個不存在。**
> **量測日 2026-09-14；量測對象是本文件的最終定稿；存在性判準 rev ＝ 本 PR head。**
>
> ⚠️ **這三個數字是「收斂」出來的，不是量一次就寫下的**：本輪每改一次文字就重量一次，
> 直到**宣告值 ＝ 實測值**才定稿（實際跑了 **3 輪** —— 每一輪都因為新寫的句子裡又多了路徑而變動）。
> **這是 7.5.3 那條教訓的可執行版本**：計數若不做這一步，**寫下它的那個動作本身就會讓它失真**。
>
> 📌 **2026-09-14 第三輪定稿後已重跑，三個數字未變（依 7.5.3 教訓 (3)，本輪的每一個自我計數
> 都在定稿後重量了一次，不只重量寫紀律的那一節）**：第三輪只改敘述、未新增任何反引號路徑，
> 故 `77`／`63`／`14` 與 MISSING 十四項清單**逐項相同**；腳本的三顆正／負對照亦照舊 PASS。

那 `14` 個逐一判讀後**全部成立**：

- **9 個是「只寫檔名」的簡寫**，各自唯一解析到一個真實檔案（**逐一驗過唯一性**）：
  `fred_indicators.parquet`→`data_cache/`、`metadata.json`→`data_cache/`、
  `twii_history.parquet`→`data_cache/`、`sources.py`／`nav_metrics.py`→`repositories/fund/`、
  `external_market_repository.py`→`repositories/`、
  `peer_rank.py`／`fund_total_return.py`／`fund_invest_calc.py`→`services/`。
  ⚠️ **唯一性是驗過的，不是假設的** —— 負對照：同樣的解析法對套件初始化檔
  （每個 package 目錄下那個 dunder-init 檔，此處刻意不以反引號寫出檔名，理由見下方自我污染註）
  會回 **25** 個命中，所以這個檢查分得出「唯一」與「撞名」。
- **3 個是「刻意引用一個不存在的東西」**，且本文件正是在陳述它不存在：
  `src/`（階段 1 禁止建立）、`v2_migrations/`（同上）、`ms1.json`（CBC 取數已被刪除）。
- **1 個是本節自己引用的負向對照** `repositories/DOES_NOT_EXIST.py` —— 它**本來就該不存在**，
  存在才是出錯。
- **1 個是「存在，但不在這個 tree 上」**：`docs/v2/CONSTITUTION.md`（§0.1 引用的 v2 母法）——
  它在分支 `origin/docs/v2-constitution-governance` 上，**尚未合併進 `origin/main`**。
  ⚠️ **這一類是新出現的，原稿沒有** —— 它提醒一件事：
  **「檔案不存在」與「檔案不在我量的那個 rev 上」是兩件事**，本表把它們分開列。

> ⚠️ **本節在本輪又踩了一次同一個自我污染陷阱，就地記下來（比修掉它更有用）**：
> 本輪把計數腳本**逐字附進文件**時，腳本 docstring 裡那個反引號包起來的範例路徑
> （`<目錄>/<檔名>.py` 形態的假路徑）**被自己的抽取器抓成了一個真實 token**，
> 於是 MISSING 憑空多一個 —— **一支腳本被貼進它自己要量的文件裡，就會開始量到自己。**
> ⚠️ **而且它遞迴了一層**：本段第一版在解釋這件事時，**又把那個假路徑用反引號寫了一次**，
> 於是修掉腳本之後**數字仍然沒降** —— **連「描述這個污染」的句子本身都會造成同一個污染。**
> ⇒ 故本段刻意**不以反引號書寫任何假路徑**。
> 修法是把 docstring 裡的範例路徑去掉反引號，並**實跑確認這個改動對輸出零影響**
> （改動前後對同一份文件都回 `TOTAL=66 EXISTS=56 MISSING=10`）。
> 📌 **這與 §3.1.1(a) 的 `DTB3` 是同一個病的第二個實例** ——
> 本文件**兩次**因為「在文件裡寫下某個 token，就污染了量那個 token 的工具」而出錯。

⚠️ **本輪的數字與原稿的 58/48/10 不同，原因是「定義不同」，不是「事實改變」**：
本輪的定義**把目錄型 token（如 `repositories/fund/`、`shared/`）也算進去，且不排除本文件自身路徑**。
**⛔ 不要把這兩組數字拿來相減** —— 它們量的不是同一個母體。
**真正可攜的是定義與腳本，不是數字。**

#### 7.5.3 ⭐ 原稿對「數字為什麼改過」的解釋，本身從來沒有被量過

原稿在此寫了一段方法論教訓，說那三個數字 ~~由 54/45/9 改成 58/48/10~~ 的成因是：
~~「**寫下這一節的動作本身，又替文件添了 4 個新的 path token**」~~。

**⛔ 那個成因是編出來的。實測推翻它，而且推翻了兩層**（量測日 2026-09-14）：

| 量測 | 結果 |
|---|---|
| 把 §7.5 整段切掉重算 | §7.5 實際新增的 unique token 是 **3 個**（`repositories/DOES_NOT_EXIST.py`、`repositories/fund/`、`tests/test_constitution_file_refs.py`），**不是 4 個**（獨立稽核用它自己的定義算是 **2 個** —— 兩種定義都不是 4） |
| **第一顆 commit `b19e071` vs 第二顆 `d9a2da2` 的 token 集合** | **完全相同，增減皆為 0** |

**第二列才是致命的那一列。** `§7.5` **在 `b19e071` 就已經存在了**，
而 `b19e071` 與 `d9a2da2` 的 token 集合**一模一樣**。
⇒ **`54/45/9` 從來就不是「加進 §7.5 之前」的計數** —— 它只是**同一份文件的一次錯誤計數**。
⇒ 那段「寫這一節的動作把數字撐大了」的故事**在時序上不可能成立**。

> ⚠️ ⭐ **這一則的反諷必須留著，它比任何一個數字都值錢**：
> **那一整段的用意，就是要教「任何描述本文件自身的計數，必須在定稿後重量一次」** ——
> 而它給出的**成因本身，從頭到尾沒有被量過一次**。
> ⇒ **教訓升級為兩條，不是一條**：
> **(1)** 描述自己的**計數**要定稿後重量（原稿已寫，仍然成立）；
> **(2)** 描述自己的**成因**同樣要量 —— **「我知道為什麼會錯」是一句需要證據的話，
> 而它比錯誤的數字更難被發現**，因為它讀起來像反省。
>
> ⚠️ **2026-09-14 第三輪再升級為三條（有意識的增補，不是漏刪；由獨立稽核抓出）**：
> **(3) 這條紀律必須對「同一份 diff 裡的每一個自我計數」一起套用，不能只套在寫紀律的那一節上。**
> **實證就在同一顆 commit 裡**：`2114839` 一邊寫下上面 (1)(2) 兩條、一邊把 §7.5.2 的三個數字
> 認真收斂到宣告值 ＝ 實測值，**卻讓 §3.1.1(a) 的 `DTB3` 自我計數維持在「改之前」的值**
> —— 而那個值**正是被同一顆 commit 自己推翻的**（詳見 §3.1.1(a) 的第三輪更正）。
> ⇒ **一條只保護自己那一段的紀律，等於沒有紀律。**
> 📌 **同輪第二個實例**：§0.1 的禁用語表六格全為假，成因同樣是「母體沒寫 ＋ 定稿後沒重量」。
> 📌 **順帶一提，同一個病在本 PR 的交件回報裡又犯了一次**：該回報寫「本文件 977 行」，
> 而 head 實際是 **988 行**（`b19e071` 才是 977）—— **在寫下上述教訓的同一份交付物裡，
> 又用了一個寫作途中的數字。** 已於 PR 描述就地更正。

#### 7.5.4 計數腳本（逐字附上，**任何人可複跑**）

**跑法**（repo 根目錄，rev 自填）——
把下方那支腳本存成 tokens.py（⚠️ **它不在 repo 內**，是本節隨文附上的驗證工具，
**刻意不進 repo**：本 PR 只准新增一個 `.md`）：

```
git show <rev>:docs/v2/DATA_DICTIONARY.md > /tmp/doc.md
git ls-tree -r --name-only <rev> > /tmp/tree.txt
python3 tokens.py /tmp/doc.md /tmp/tree.txt
```

```python
#!/usr/bin/env python3
"""§7.5 "path-like token" 抽取器 —— **本腳本就是該詞的定義**（可獨立複跑）。

定義（五條，缺一不可）：
  1. 取所有**單層反引號** span：`...`（不跨行）。
  2. 正規化：先砍 ::symbol 起的尾段（a/b.py::fn -> a/b.py）；
     再砍第一個空白起的尾段（CLAUDE.md §2.1 -> CLAUDE.md）。
  3. path-like 的**充要條件**：結尾是已知副檔名，**或**結尾是 `/`（目錄）。
  4. 排除：glob（含 `*`）／絕對路徑（`/` 開頭）／URL／含 CJK 或全形字元
     （擋 `N/A（虧損）` 這類）／stem 為空的裸副檔名（如 `.py`）。
  5. unique 去重後即為母體。**含本文件自身路徑**（不做自我排除）。
存在性判準：token 屬於 `git ls-tree -r --name-only <rev>`，或等於由該清單推導的目錄前綴。
"""
import re, sys

EXTS = (".py", ".md", ".json", ".parquet", ".yml", ".yaml", ".txt", ".toml", ".cfg", ".ini")
CJK = re.compile(r'[　-〿一-鿿＀-￯]')

def extract(text):
    out = []
    for s in re.findall(r'`([^`\n]+)`', text):
        t = s.strip()
        if "::" in t:
            t = t.split("::", 1)[0]
        parts = t.split()
        if not parts:
            continue
        t = parts[0]
        if t.startswith(("http://", "https://")):
            continue
        if CJK.search(t) or "*" in t or t.startswith("/"):
            continue
        if not (t.endswith(EXTS) or t.endswith("/")):
            continue
        if t.startswith(".") and "/" not in t:      # 裸副檔名 `.py`，不是路徑
            continue
        out.append(t)
    return out

def classify(doc_text, tree_lines):
    tree = set(tree_lines.split())
    dirs = set()
    for p in tree:
        seg = p.split("/")
        for i in range(1, len(seg)):
            dirs.add("/".join(seg[:i]) + "/")
    toks = sorted(set(extract(doc_text)))
    ex = [t for t in toks if t in tree or t in dirs]
    ms = [t for t in toks if not (t in tree or t in dirs)]
    return toks, ex, ms

if __name__ == "__main__":
    doc = open(sys.argv[1], encoding="utf-8").read()
    toks, ex, ms = classify(doc, open(sys.argv[2], encoding="utf-8").read())
    print(f"TOTAL={len(toks)}  EXISTS={len(ex)}  MISSING={len(ms)}")
    for m in ms:
        print("  MISSING:", m)
    # ⭐ 正／負對照 —— 沒有這三條，本腳本可能恆真或恆假而無人察覺
    assert "CLAUDE.md" in ex, "正對照 1 失敗：`CLAUDE.md` 必須判為存在"
    assert "services/fund_service.py" in ex, "正對照 2 失敗：帶目錄的真實檔必須判為存在"
    assert "repositories/DOES_NOT_EXIST.py" in ms, "負對照失敗：`repositories/DOES_NOT_EXIST.py` 必須判為不存在"
    print("[control] PASS", file=sys.stderr)
```

> ⚠️ **那三顆 assert 不是裝飾品，它們真的擋過事**：本輪把 §7.5 整段切掉重算時（7.5.3 第一列），
> 負對照那一顆**當場 fire** —— 因為 `repositories/DOES_NOT_EXIST.py` 只出現在 §7.5 裡面，
> 切掉之後它自然消失。**那一次 fire 正好證明這顆 assert 不是恆真的。**
> **每一支自製腳本都該有一顆這樣的斷言**，否則「綠燈」只代表「它沒炸」，不代表「它有在看」。

#### 7.5.5 這個檢查驗不到什麼

> ⚠️ **它只驗「檔案存不存在」，不驗「那個符號是不是它自稱的東西」** ——
> 這正是 `CLAUDE.md §2.1` 記載的、該守衛自己登記的射程外缺口。
> **本輪的 B1／B3／B4 三個錯（`_CONST_FILES` 不存在、`fetch_url_with_retry` 指錯檔、
> `classify_eating_principal` 指錯檔）沒有一個是這個檢查抓得到的** ——
> 因為 `tests/test_constitution_file_refs.py`、`infra/proxy.py`、`services/fund_service.py`
> **三個檔案全部真實存在**，錯的是掛在它們後面的符號。
> ⇒ **讀者請據此打折信任本文件的符號引用：路徑經機器驗過，符號只經人工判讀。**
> ⚠️ **本文件刻意不寫任何行號**（沿用姊妹 repo `my-stock-dashboard` §8.2.A.0 規則 1 的精神；
> ⚠️ **該節不在本 repo 的 `CLAUDE.md` 裡**，出處見 §7.5.6）：
> 行號在任何一次重構後就失效，而**重構不會觸發本文件更新**。
> ⚠️ **本節全部為單組實測，未經第二組獨立複驗**（`CLAUDE.md §-2` 規則 6）。

#### 7.5.6 ⚠️ `§8.2.A.0` 的出處更正：它不在本 repo 的 `CLAUDE.md` 裡

> ⛔ **2026-09-14 第三輪就地更正（有意識的更正，不是漏刪；由獨立稽核抓出）**：
> 本文件有**兩處**把那條「不寫行號／量測值標日期」的規則寫成 ~~`CLAUDE.md §8.2.A.0`~~
> （§7.4 與 §7.5.5，兩處**均已就地改掉**）。**本 repo 的 `CLAUDE.md` 沒有這一節。**
>
> **實測（量測日 2026-09-14，rev ＝ 本 PR head，指令與輸出照抄）**：
>
> | # | 指令 | 輸出 |
> |---|---|---|
> | 1 | `git grep -nE "^#+ *8\.2\.A" <rev> -- 'CLAUDE.md'` | **無輸出（exit 1）** —— 該檔沒有任何 `8.2.A*` 標題 |
> | 2 | **正對照**：`git grep -nE "^#+ *8\.[0-9]" <rev> -- 'CLAUDE.md'` | **6 行**（`8.1`／`8.2`／`8.3`／`8.3.P`／`8.4`／`8.5`）—— 證明指令 1 的空輸出**不是**指令壞掉 |
> | 3 | `git grep -c "8\.2\.A\.0" <rev> -- 'CLAUDE.md'` | **6 行**，但**全部是引用**，沒有一行是定義 |
> | 4 | 同上，`-- 'EXCEPTIONS.md'` | **4 行**，同樣全部是引用；`^#+ *8\.2\.A` 在該檔亦**無輸出（exit 1）** |
>
> ⚠️ **`CLAUDE.md` 自己早就做過這個更正，而本文件等於把它重新寫回去**：
> 片語「**本檔無 §8.2.A.0 一節**」在 `CLAUDE.md` 出現 **1 次**、在 `EXCEPTIONS.md` 出現 **4 次**
> （實測 `git grep -n -o "本檔無 §8\.2\.A\.0 一節" <rev> -- 'CLAUDE.md' 'EXCEPTIONS.md'`；
> **負對照**：同一條指令把片語換成一個不存在的節號 → **無輸出（exit 1）**）。
> `EXCEPTIONS.md` 另有一行逐字寫著「**`§8.2.A.0` 從來就不在 `CLAUDE.md` 裡**」
> 並接著說明它出自姊妹 repo，且該檔的待判定登記簿另有一列 `P-PHANTOMSEC-1`
> 專門處理「**被大量引用、卻從來沒有被定義過的節號**」這一類問題。
> ⇒ **本文件犯的是一個已經被本 repo 明文撤下過、而且撤下了不只一次的宣稱。**
>
> ⚠️ **這一處與本輪的 B1（`_CONST_FILES` 不存在）是同一個形狀**：
> 都是**引用一個不存在的名字**，而**本文件的機器守衛（§7.5.1）看不到它** ——
> 該守衛只驗「檔案存不存在」，`CLAUDE.md` 這個**檔案**當然存在，
> 錯的是掛在它後面的**節號**。**這是 §7.5.5 已登記的那個射程外缺口的又一個實例**
> （該節已列 B1／B3／B4 三個，本處是同一形狀的再一個；⛔ **刻意不寫序數也不宣稱窮舉** ——
> 「總共幾個」取決於有沒有漏看，正是本文件 §7.4 明文禁止書寫的那種句子）。
>
> ✅ **規則本身的效力不受影響，本文件照舊沿用它** ——
> 改的只有**出處標籤**：它是**姊妹 repo `my-stock-dashboard`** 的條文，
> 本 repo 的 `CLAUDE.md` 與 `EXCEPTIONS.md` 是**引用方**，不是出處。
> ⛔ **且本文件依 §1.3 從未讀取姊妹 repo 任何內容** ——
> 故本文件對該規則的引用**一律只到「同一精神」為止，不宣稱逐字複述其原文**。

### 7.6 第三輪回修的射程與其未驗事項（2026-09-14）

**本輪只改敘述，不動任何實質結論。** 三個 Blocker ＋ 三個 Advisory，全部落在「一句話說錯了」這一層：

| # | 改了什麼 | 實質結論有沒有動 |
|---|---|---|
| B-a | §0.1 禁用語表六格全為假 → 改成**四個母體各一欄**，並就地寫出**正／負對照與空檔防護** | ⛔ **沒有。** 裁決（禁用語射程 ＝ 面向使用者的輸出）、B 欄那 5 個治理用語的逐一判讀、對階段 2 的硬性要求，**一字未改** |
| B-b | §3.1.1(a) 的自我計數宣告 10、實測不是 10，且**寫下當時就已過期** → 改為**行數／次數分列 ＋ 逐 commit 回溯成因** | ⛔ **沒有。** 該 series 不存在於任何程式碼、必須新增至常數檔，**不變** |
| B-c | 兩處把規則出處寫成本 repo 的 `CLAUDE.md` → 改標**姊妹 repo**，並新增 §7.5.6 記載實測 | ⛔ **沒有。** 規則本身照舊沿用 |
| A-1 | §0.1 只寫「含正／負對照」四個字、從未寫出那兩個對照 → 逐一寫出，**外加第三項空檔防護** | ⛔ 沒有 |
| A-2 | §0.1 欄名的「**唯一**要顯示給使用者看的文案草稿」是全稱句 → 撤下量詞，並**把 §3.3「顯示」欄實際量成 D 欄** | ⛔ **沒有。** D 欄六格實測全 0 |
| A-3 | 引母法 §6.2.2 的量詞沿用了**已被母法自己撤下**的「處」→ 改「字串」 | ⛔ **沒有。** 3 個、3/3 全是誤報、兩否定句 ＋ 一操作提示，一字未改 |

**⛔ 本輪刻意沒有碰的（與前兩輪相同的檔案邊界）**：
`.py` 一個字都沒動；`CLAUDE.md`／`EXCEPTIONS.md`／v2 母法／UI 規格與線框稿**一個 byte 都沒動**
（後三者是別組的檔案邊界）。**本 PR 仍然只新增一個檔。**
**parquet 數字、缺漏率、FRED 逐格、程式常數、CHUBB 公式那一層，本輪完全未重算，也未改寫。**

> 📌 **本節刻意不寫出「那個 3 個月期國庫券 series 代號」與那個禁用語的字面**（上表 B-a／B-b 兩列）。
> **理由不是修辭，是算術**：§0.1 的 B 欄與 §3.1.1(a) 的兩個數字**都把本節算進母體**，
> 在這裡寫一次字面，那兩處的宣告值就會當場失真、連帶讓 §0.1 那份「5 個逐一判讀」的清單少列一項。
> **這是 §7.5.2 已經立過的辦法**（該節為了同一個理由，刻意不以反引號書寫任何假路徑）。
> ⚠️ **據實揭露，這是一個取捨**：好處是兩處自我計數穩定、清單與數字對得上；
> 代價是**本節的可讀性被犧牲了一點**。**另一條路是讓數字浮動、每次都回頭改清單** ——
> 本輪選前者，是因為後者會給下一個人留一個「寫到那個詞就踩雷」的隱形陷阱。

### 7.6.1 ⚠️ 第三輪沒有驗到什麼（照實寫，不寫「全都查過了」）

| 沒驗到 | 為什麼 |
|---|---|
| **§2～§6 的實質數字**（parquet 統計、缺漏率、FRED 逐格、程式常數、CHUBB 11 式） | **不在本輪射程**。前兩輪稽核各以獨立實作重算過，本輪**未重跑、未複驗**，因此**也不為它們背書** |
| **本文件對姊妹 repo 那條規則的內容是否逐字正確** | 依 §1.3 本文件**從未讀取姊妹 repo**；本輪同樣沒讀。故 §7.4／§7.5.5／§7.5.6 一律只宣稱「**同一精神**」，**不宣稱逐字複述** |
| **「§0.1 的禁用語表是本文件唯一算錯的自我計數」** | ⛔ **本輪不作此宣稱。** 本輪只重量了**被點名的那幾個**，加上 §7.5.2 的 `77`／`63`／`14`；**沒有逐節掃過每一個自我計數** —— 那取決於有沒有漏看 |
| **本文件其餘章節的符號引用** | 同 §7.5.5：**路徑經機器驗過，符號只經人工判讀**，本輪未擴大該人工判讀的範圍 |
| **母法 §6.2.2 以外的母法條文是否也已被改寫** | 本輪只比對了本文件實際引用到的那幾條；母法**整份未逐條重讀** |

⚠️ **本節與本輪所有更正同樣是單組產出，未經第二組獨立複驗**（`CLAUDE.md §-2` 規則 6）。
⛔ **在獨立稽核完成前，本輪任一句不得被當成「已查證的事實」去支撐實作決策**（同 §7.4 末條）。
