# D2 最小核准包：R-ID-1、R-NAV-1（2026-11-13）

> **本檔是核准準備包，不是客戶裁示、不是核准欄位、不是授權施工。** 基準 `origin/main` `6dcb51f8dee3af7536211b3deda4676c3439ed56`（#1226 merge）；撰稿日 2026-11-12（Asia/Taipei），擬落盤檔名日期 2026-11-13。
> **單組作者（專案 AI 研究作者）；尚待非作者獨立 QA。** 方法為唯讀讀碼＋讀文件＋字面 `git grep`；**未執行任何測試**（「有測試」＝測試檔存在且斷言可讀，不是跑綠；是否綠只能由 CI 驗）、未連網、未碰憑證與 Sheet。
> **現行事實不變**：D2 正式核准欄位數＝**0**（`DEC-2026-11-11-04` D2-G1）。本檔不新增 Schema、provider、資料來源、金融公式、門檻，不提議任何程式施工；FX、身份（DG2／ISIN／`full_key` 後綴）、cutover 一律不解開；BL-0545 維持 BLOCKED。
> 文中「推薦／擬議／總管讀法」一律**可被客戶推翻**；A／B／C 方案是縮短客戶決策的問法，**不是已核准選項**；「擬議契約文字」是**待客戶逐字修改或否決的草稿**，在客戶明確核准前不具任何效力。
> 缺值／無法判定一律寫「⬜ 資料未取得／無法判定」（本包描述用語）；呈現層的正式字樣沿用既有「資料未備／無法判定」（`DEC-2026-11-08-04` Q4，不新增正式狀態詞），**不得讀成 0、中性或正常**（`PROJECT_RULES.md` §13.1）。路徑一律「檔案::符號」，不寫行號。全稱句（「0 命中」「只有 N 處」）皆為**單組字面 grep、未經第二組驗證**，指令見附錄 A。
> 第四階段客戶任務原文為轉述，**無逐字存檔**（見 §6）。

---

## 0. 結論先行

1. **本包只涵蓋 `R-ID-1`（`fund_code`）與 `R-NAV-1`（`nav_orig_ccy`）**；其餘 12 個去重欄位維持 Pending（§1.3），本包不給核可建議。兩列證據在 17 列中最強（有 code＋有測試、不涉公式與 FX），但**「證據強」≠「已核准」**，目前核准欄位數仍為 0。
2. **`R-ID-1` 核准文字必須限定在「Google Sheet 持倉『基金代號』欄」，並明標「D2-A＝B 格式檢查尚未實作」。** 本組新發現（N5）：🔍 找基金（`exp`）路徑的 NAV `fund_code` 取自**選股池代碼欄**，不是「基金代號」欄；而 `DEC-2026-10-29-01` 逐字明寫「不得推廣成整個 repo 的所有 code」——契約若寫成「所有 `fund_code` 皆 MoneyDJ 基本代碼」就越過客戶授權。
3. **`R-NAV-1` 核准文字必須綁定同列 `ccy`、並排除 share class／配息型別／避險型態／NAV series 的等價主張**：「原幣」是否成立依賴 `ccy`（`R-NAV-5`，維持 Pending）；`DEC-2026-10-29-01` 逐字第 8 項明言同一基金代碼不代表可無條件混用不同日期、幣別、share class、NAV series。
4. **D2-B 射程**：字面標題與內容是「1Y 含息證據欄位」。兩種讀法**只影響 `R-NAV-2／3／5／6` 四列**；`R-PERF-3／6` 在兩種讀法下都維持 Pending（四項同源證據目前無法由文件證明）；`R-ID-1`、`R-NAV-1` 與此題無關。本包只研究、**不替客戶決定 Q0**。
5. 核准這兩列**不改任何程式行為**；本包所有「後續動作」限 D2 契約文件層與契約測試**草案（文字）**。

---

## 1. 權威鏈與現狀

### 1.1 「D2 核准欄位數＝0」的依據

| 依據 | 原文要點 | 位置 |
|---|---|---|
| `DEC-2026-11-11-04` D2-G1＝B 修正版 | 僅逐列審核；不得整欄升格；每列須核對既有 DEC、正式契約、New UI2 適用範圍；「未明確核准、證據不足或有衝突者維持 Pending」；「**本次沒有核准任何具體欄位（正式核准欄位數＝0）**」；遇與 `DEC-2026-11-09-01` 衝突者以後者為準、維持 Pending | `docs/DECISIONS.md` 該 DEC「決策內容摘要」「與既有 DEC 關係」欄；`docs/evidence/decisions/2026-11-11_d2_g1_g2_g3_rulings.md`（ChatGPT 轉達要點，非逐字） |
| `DEC-2026-11-11-04` D2-G2＝A／D2-G3＝A | D2 逐域契約與 Digest schema 是兩個獨立 Gate；首批只處理基金身份、NAV、績效，其餘六域延後（≠ Excluded） | 同上 |
| `DEC-2026-11-12-01` | 「影響範圍」明寫不修改 D2 Required 審核、FX Gate、金融契約 | `docs/DECISIONS.md` 該 DEC |
| `DEC-2026-11-12-02` | 「**不授權**……不核准任何 D2 欄位、不解除 FX／D2／身份／金融公式／cutover Gate」；(5) BL-0545 繼續 BLOCKED | `docs/DECISIONS.md` 該 DEC |
| 掃描 | `docs/DECISIONS.md` 最後一筆 DEC 為 `DEC-2026-11-12-02`（其後即「五、歷史索引」）；「核准欄位數／正式核准欄位」字樣只出現在 `DEC-2026-11-11-04`（單組 grep，附錄 A-1） | — |

### 1.2 兩列在 D2 Required 逐列待審表的原文

來源：`docs/evidence/d2_contract_candidates_returns_identity_holdings_2026_11_08.md` 末節「Required 逐列待審表」（逐欄照錄，只省略表格線）。

**R-ID-1**

| 欄 | 原文 |
|---|---|
| 原始候選 | 第二部 K1；A1 A1 |
| 欄位名稱 | `fund_code` |
| 現有來源 | Sheet「基金代號」欄；`nav`／`dividend`／`fund_profile` 列鍵（`services/v2_tables/contract.py::NAV_FIELDS` 等） |
| 現有 DEC／契約 | `DEC-2026-10-29-01` 第 1 項、`-03` 第 1 項（Sheet 欄＝MoneyDJ 基本代碼命名空間，已核准）；`DEC-2026-11-08-04` Q2；`DEC-2026-11-09-01` D2-A＝B（違反欄位契約須標示、保留原值、不改寫；契約文字層） |
| New UI2 適用 | 命名空間已核准；「列入 Required」**未核准**；僅 Preview |
| 既有實作 | 欄位存在；D2-A＝B 要求的格式檢查**尚未實作**（`shared/fund_identity.py::DG2_SHADOW_ENABLED = False`） |
| 衝突與缺口 | 契約文字與實作有落差，須明標；`sheet_code_contract_violation` 在 production 路徑打不出 |
| 本次狀態 | 待客戶逐列核可，正式效力 Pending |
| 建議處理（非裁示） | 證據最強，可列為優先逐列核可候選；核可時須連帶標明「格式檢查尚未實作」 |
| 後續 Gate | 實作接線另需授權；不啟用 DG2 Shadow |

**R-NAV-1**

| 欄 | 原文 |
|---|---|
| 原始候選 | A1 B1 |
| 欄位名稱 | `nav_orig_ccy` |
| 現有來源 | `services/v2_tables/nav_dividend.py::build_nav_table`（A 鏈取數；非有限／非正值不寫） |
| 現有 DEC／契約 | `DEC-2026-11-08-04` Q5（非台幣可整理原幣）；`44` 4.2 |
| New UI2 適用 | **未核准**；僅 Preview（`ui_v2` `hld`／`alo` 使用；`ui_v3` 市值基準 blocked，引 A1 B9） |
| 既有實作 | 已實作（Preview） |
| 衝突與缺口 | 原幣、無 TWD 欄；FX 閘門關閉（`FX_OBS_DATE_RULE_VERIFIED = False`）；NAV source precedence 不改 |
| 本次狀態 | 待客戶逐列核可，正式效力 Pending |
| 建議處理（非裁示） | 可列為優先候選（原幣欄，不涉 FX） |
| 後續 Gate | 無新增 Gate；不得推及 TWD 換算 |

### 1.3 其餘維持 Pending 的欄位（只列名稱與狀態，不給核可建議）

17 列去除 3 組重複＝14 個不同欄位；本包處理其中 2 個，其餘 **12 個全部維持 Pending**：

| 域 | 欄位（待審 ID） | 狀態 |
|---|---|---|
| 身份 | `full_key`（R-ID-2）、`ok`（R-ID-3） | Pending |
| NAV | `nav_date`（R-NAV-2）、`fetched_at`（R-NAV-3）、`source_tier`／`provenance.source`（R-NAV-4）、`ccy`（R-NAV-5）、`ccy_source`（R-NAV-6） | Pending |
| 績效 | `value_pct`（R-PERF-2）、`source`（R-PERF-4）、`window_days`（R-PERF-5）、`status`（R-PERF-7）、`reason`（R-PERF-8） | Pending |
| 重複列 | R-PERF-1（＝R-ID-1）、R-PERF-3（＝R-NAV-5）、R-PERF-6（＝R-NAV-2） | 不獨立計；**R-PERF-1 與 R-ID-1 的關係見 §5 決策 (5)** |

（來源：候選檔「列數統計與核可狀態」；前人準備包 `docs/evidence/d2_contract_approval_prep_2026_11_12.md` §2、§3。）

### 1.4 本包不得解開的事項

| 事項 | 現況證據 |
|---|---|
| FX／TWD 換算 | `services/v2_tables/market_indicator.py` `FX_OBS_DATE_RULE_VERIFIED = False`（附錄 A-2）；`DEC-2026-11-08-02`；nav 表無 TWD 欄 |
| 身份：DG2 Shadow、canonical key | `shared/fund_identity.py` `DG2_SHADOW_ENABLED: bool = False`；`DEC-2026-10-28-05` Stage-2 須另一次 Gate |
| 身份：ISIN | `DEC-2026-10-28-05`：ISIN 非 canonical key（`DEC-2026-11-01-01` 僅在「🔍 找基金」搜尋入口範圍升為 alternate lookup key，本包不處理） |
| 身份：`full_key` 後綴（S7） | `R-ID-2` 維持 Pending；`DEC-2026-10-29-01` 第 4 項 |
| cutover／production 啟用 | `DEC-2026-11-11-04`、`-11-12-02` 不授權清單 |
| BL-0545 | `docs/BACKLOG.md` BL-0545 列＋第 64 行 blocked 清單；`DEC-2026-11-12-02` (5) |
| NAV 10 日規則 | `DEC-2026-11-05-03`：不得升格；`NAV_NOT_READY_DAYS = 10` 不動 |

---

## 2. R-ID-1｜`fund_code` 逐列證據包

### 2.1 欄位與金融語意

- 字串，非空；作為基金身份鍵，同時是 `nav` 表主鍵之一（`fund_code`＋`nav_date`，`docs/v2/44_fund_ui_ssot.md` §4.2「主鍵」）。
- **無單位、無日期語意**（身份鍵沒有 as_of）。
- 不是 ISIN、不是通路後綴碼、**不是持倉鍵**：持倉鍵為（`policy_id`, `fund_code`）（44 §4.1「業務唯一鍵」），基金身份與保單持倉身份分開（`DEC-2026-10-29-01` 第 2 項；逐字檔 `docs/evidence/decisions/2026-10-29_dg2_final_ruling.md` 第 2 節）。
- 本包涉及的是 **data identity 語意**（`PROJECT_RULES.md` §4 停下條件之一）：核准的是**既有已裁示語意的契約化**，不新增身份規則。

### 2.2 正式契約依據（引用位置）

| 依據 | 內容 | 位置／狀態 |
|---|---|---|
| `DEC-2026-10-29-01` 第 1 項（客戶裁示，逐字存檔） | Sheet「基金代號」欄現在及未來均為 MoneyDJ 基本基金代碼；**「這項裁示只適用於客戶確認的 Sheet 基金代號欄，不得推廣成整個 repo 的所有 "code"、所有 Sheet 或所有外部 API 都屬 MoneyDJ」**；不改 Sheet schema | `docs/evidence/decisions/2026-10-29_dg2_final_ruling.md` 第 1 節（本組已讀原文） |
| 同上 第 4 項 | 「Sheet 基本代碼不需要後綴剝除」；「未來若 Sheet 出現不符合基本代碼契約的輸入，應標記資料驗證問題，不得靜默截斷、剝除或改寫原值」 | 逐字檔第 4 節第 2、6 點 |
| `DEC-2026-11-09-01` ①(1) D2-A＝B（客戶回覆，**要點轉述非逐字**） | 契約文字：遇網址、帶後綴代碼或格式異常，標示違反欄位契約、保留原始輸入、不靜默截斷／剝除／改寫、不擴張至其他來源／欄位／代碼命名空間；「**尚未實作**」，契約與實作暫有落差須明標 | `docs/DECISIONS.md` 該 DEC；`docs/evidence/d2_contract_candidates_...` 題一 |
| `44` §4.2 | `fund_code` 字串、不可空、語意「基金代碼」 | frozen；`contract.NAV_FIELDS` 為鏡像 |
| `DEC-2026-10-28-05` | Unknown 不猜；currency／share class／platform suffix 分開；ISIN 不依賴 | `docs/DECISIONS.md`；逐字檔 `docs/evidence/decisions/2026-10-28_dg2_identity_ruling.md`（本組未再開讀） |

### 2.3 目前資料來源與實作

| 路徑 | 說明 | 證據 |
|---|---|---|
| 💼 持倉路徑（`hld`／`alo`） | Sheet「基金代號」欄 → `services/v2_tables/alo_holdings.py::_key_text`（只去前後空白；非字串回 None）→ `holding[*]["fund_code"]` → `ui_v2/{hld,alo}/source.py` 呼叫 `fund_keys.resolve_full_keys([h["fund_code"] ...])`，**只留 `ok is True` 的檔**；NAV 呼叫的 `fund_code` **原樣沿用 Sheet 值**（`full_key`／`chain_code` 另帶，供取數） | `ui_v2/hld/source.py`（`resolved = {r["input"]: r ...}` 與 `build_nav_dividend_tables` 的 dict）；`ui_v2/alo/source.py` 同型 |
| 🔍 找基金路徑（`exp`）【N5】 | `ui_v2/exp/source.py` 母體＝選股池代碼（`exp_universe.load_pool_codes`，**「只取代碼」**）→ `resolve_full_keys(list(codes))` → `exp_nav.load_nav_dividend`；NAV 的 `fund_code` 是**選股池代碼欄**的值，**不是「基金代號」欄** | `ui_v2/exp/source.py` 檔頭與 `_load_funds`；`docs/v2/70_dg2_canonical_identity_proposal.md` §15.2（引） |
| v1 格式 Sheet | 分頁沒有「基金代號」欄時，代碼由 `fund_url` 推出（`repositories/policy/v1.py::_extract_code_from_url`）——**這一支的 `fund_code` 不是 Sheet 欄值** | `docs/v2/70` §15.2（引，本組未再讀該函式） |
| NAV 列 `fund_code` | `services/v2_tables/nav_dividend.py::_group_funds` 要求 `fund_code` 為前後無空白的非空字串，否則 `ValueError`（呼叫端錯誤，不靜默）；列內原值寫出，**不轉大寫、不替換為 `full_key`** | `nav_dividend.py::_group_funds`、`_rows_from_segment`（`"fund_code": fund_code`） |
| 欄位契約 | `services/v2_tables/contract.py::NAV_FIELDS` 第一欄 `("fund_code", "字串", False)`；`_problem_for` 對字串欄：非字串或空白字串→問題 | `contract.py` |
| 可達性 | Preview：`ui_v2/{hld,alo,exp}`；`app.py`／`ui/`／`ui_v3` 對 `resolve_full_keys` **0 命中**（附錄 A-3）；`ui_v3` 對 `build_nav_table`／`nav_dividend` 0 命中（A-4）。Old UI 另有自己的代碼處理，不是本欄產出者 | 附錄 A |

### 2.4 已驗證證據與缺漏

**證據（均為「檔案存在且斷言可讀」，未跑）**

| 證據 | 說明 |
|---|---|
| `tests/test_v2_tables_nav_dividend.py::test_契約_nav與44逐欄相同_source_tier值域相同` | `contract.NAV_FIELDS` 與 44 §4.2 逐欄相同（含 `fund_code` 字串、不可空），`len(fields) == 7` 防空掃 |
| `tests/test_v2_tables_nav_dividend.py::test_nav_沒給full_key_當場炸_不拿fund_code去猜` | 不用 `fund_code` 猜取數鍵 |
| `tests/test_v2_tables_fund_keys.py`（44 個 `def test_`，含參數化） | 解析鏈行為；含 `test_mapping_miss_passes_through`（帶後綴 `acdd01-eqtal005`→`ACDD01-EQTAL005`）、`test_url_extracts_code`、`test_fallback_is_error`、`test_non_ascii_is_error` |
| `tests/test_fund_identity_dg2.py`（60 個 `def test_`） | Shadow 解析器的 Sheet 契約違反例（`docs/v2/70` §15.5）；**屬 shadow，與 production 路徑無關** |
| 客戶逐字裁示 | 命名空間（第 1 項）與「不符契約須標記、不改寫」（第 4 項第 6 點）本組已讀逐字原文 |

**缺漏**

| # | 缺漏 | 證據／狀態 |
|---|---|---|
| G1 | **D2-A＝B 的「標示違反欄位契約」在 production 路徑無任何輸出**：`sheet_code_contract_violation` 字面只出現在 `services/fund_identity.py`、`services/fund_identity_shadow.py`、`shared/fund_identity.py`；`DG2_SHADOW_ENABLED = False`；hook 的 `log_shadow_for_fund_keys(fund_codes, out, *, alias_mapping=None)` 沒有 `input_source` 參數（`services/v2_tables` 內 `input_source` 0 命中） | 附錄 A-5、A-6；讀碼，未跑 |
| G2 | 現行 `resolve_full_keys` 對**帶後綴代碼、合格網址**判 `ok=True` 並產出 `full_key`（測試 `test_mapping_miss_passes_through`、`test_url_extracts_code` 釘住此行為）；對「格式異常」（如含空白、超長）判 `ok=False` 且該檔在 `hld`／`alo` 路徑被 `ok is True` 濾掉。**兩類都不會產生「違反欄位契約」標記** | `fund_keys.py::_resolve_one`；`ui_v2/{hld,alo}/source.py` |
| G3 | `ok=False` 的檔被濾出 NAV 呼叫後，**畫面是否、如何揭露其失敗原因＝NOT VERIFIED**（`hld/source.py` 只讀到過濾，未追到呈現層） | 單組讀碼 |
| G4 | 大小寫不正規化：NAV 列 `fund_code` 保留 Sheet 原值（僅去前後空白）；`acti71` 與 `ACTI71` 會成為兩個不同的列鍵，而取數鍵 `full_key` 兩者相同。**未見專門鎖定此行為的測試** | `_key_text`、`_group_funds`；測試 grep（A-7，單組） |
| G5 | `fund_code` 空白／前後有空白時 `build_nav_table` 拋 `ValueError`（`_group_funds`）——**未見直接測試此 raise**（現有 raise 測試針對 `full_key`：`test_nav_沒給full_key_當場炸…`、`test_7_full_key前後帶空白就raise`） | 測試 grep（A-7，單組） |
| G6 | N5：`exp` 路徑 NAV 的 `fund_code` 來自選股池代碼欄；其命名空間**沒有客戶裁示**（`DEC-2026-10-29-01` 明言只限「基金代號」欄；`DEC-2026-11-01-02` G-E1 另明言不得以選股池手填 isin 欄作 identity authority——**本組只在 `docs/v2/70` §15 引文中讀到，未開 DEC 全文**） | `ui_v2/exp/source.py`；NOT VERIFIED |
| G7 | 真實 Active Sheet 中帶後綴／網址／異常格式代碼的實際分布＝**NOT VERIFIED**（BL-0545 BLOCKED，使用者未提供合法輸入） | `docs/BACKLOG.md` BL-0545 |
| G8 | `ok` 旗標只代表「可解析」，不代表基金存在或取得 NAV（`fund_keys.py` 不取數）——屬 `R-ID-3`，此處僅為避免誤讀 | 前人準備包 N4 |

### 2.5 Missing／Unavailable 語意

| 情境 | 契約應有的語意 | 現況 |
|---|---|---|
| Sheet 欄空、非字串 | 該持倉無法掛到基金→⬜ 資料未取得／無法判定；**不補預設代碼、不以名稱／URL／ISIN 補** | `_key_text` 回 None；`holding_row_problems` 要求 `fund_code` 非空字串（`contract.py`） |
| 解析失敗（`ok=False`） | 不補 `full_key`、不截斷、不猜（`fund_keys.py` 檔頭、`_fail`） | `ok=False`＋`error` 字串；`hld`／`alo` 濾出（見 G3） |
| 違反 Sheet 欄契約（網址／後綴／異常） | **應**標示違反、保留原值、不改寫（D2-A＝B） | **未實作**（G1、G2）——契約須明標落差 |
| Unknown | 未知屬性不猜、不視為相同／不同／安全／已確認（`DEC-2026-10-28-05`） | shadow 層實作；production 不涉 |

### 2.6 核准的範圍

**若客戶核准 R-ID-1，核准的是下列文字（擬議，總管讀法，客戶可逐字改；未核准前不具效力）：**

> **T-ID1｜身份域 `fund_code`**
> 1. 型別：字串，不可空。語意：Google Sheet 持倉「基金代號」欄所填的 MoneyDJ 基本基金代碼（命名空間固定 MoneyDJ，**只限該欄**，`DEC-2026-10-29-01` 第 1 項）；為 `nav` 表主鍵之一（`fund_code`＋`nav_date`）。
> 2. 取用規則：原值保留（僅去前後空白）；不轉大小寫、不截斷、不剝後綴、不改寫、不補值。大小寫正規化**不在本契約內**。
> 3. 無日期語意；不是 ISIN、不是通路後綴碼、不是持倉鍵（持倉鍵為 `policy_id`＋`fund_code`，另域）。
> 4. 缺值：Sheet 欄空或非字串→該持倉不產生 `nav`／績效列，呈現層為「⬜ 資料未取得／無法判定」；不得補預設代碼。
> 5. **已知落差（D2-A＝B）**：Sheet 欄遇網址、帶後綴代碼或格式異常時，契約要求「標示違反欄位契約、保留原始輸入、不靜默截斷／剝除／改寫」；**目前尚未實作**——現行解析鏈對此類輸入可能判 `ok=True` 並產出 `full_key`，且不產生任何違反標記（`DG2_SHADOW_ENABLED = False`）。
> 6. 本核准**不**構成對任何 1Y 輸出欄位的核准（1Y 輸出無 `fund_code` 鍵，它是呼叫端的 join key）。

**不含（核准文字須同時寫明）：**

| 不含 | 原因 |
|---|---|
| `full_key`、`ok`（R-ID-2／3）、S7 後綴規則 | 維持 Pending；identity 規則屬 Stop Gate |
| `canonical_key`／`base_fund_code`／ISIN／share class／currency 身份屬性 | Shadow、Stage-2 另一次 Gate |
| `exp`（🔍 找基金）路徑的選股池代碼命名空間（N5） | 無客戶裁示；見 §5 決策 (6) |
| `dividend`、`fund_profile` 的 `fund_code` | 屬 D2-G3 延後之域 |
| 啟用 `DG2_SHADOW_ENABLED`、改 resolver／consumer、改 Sheet schema | 不授權 |
| 實作 D2-A＝B 的標示 | 「實作接線另需授權」（候選檔本列「後續 Gate」） |

### 2.7 核准與不核准的風險

| 情境 | 後果 | 可逆性 | 緩解 |
|---|---|---|---|
| **核准** — 契約先於實作 | 契約宣稱「違反須標示」而 production 不做，讀者可能誤以為已受保護 | 高（純文件，新 DEC 即可撤回／修正） | 擬議文字第 5 點明標「尚未實作」（D2-A＝B 本身要求明標） |
| **核准** — 範圍外溢 | 被讀成 repo 內所有 `fund_code`（`exp` 選股池碼、v1 由 URL 推得碼、`dividend`／`fund_profile`）皆 MoneyDJ 基本碼，越過客戶「只限該欄」的授權 | 高 | 擬議文字第 1 點限定「Sheet 基金代號欄」；§2.6 不含表列出 N5 |
| **核准** — 大小寫語意被默認 | 若契約不寫「不正規化」，後人可能補一個大寫轉換＝新身份規則 | 高 | 擬議文字第 2 點明寫 |
| **核准** — 被當成 identity 規則升格 | 屬 data identity 等級；合併前須 ≥1 組真正獨立稽核（`PROJECT_RULES.md` §8） | — | 本包標明待非作者 QA |
| **不核准** — D2 核准欄位數維持 0 | 逐列審核流程無法演練；後續各列（`nav_date`、`ccy` 等）引用的列鍵沒有契約錨點 | 高（隨時可再提） | — |
| **不核准** — 契約落差無處承載 | D2-A＝B 已核准的「契約文字方向」只存在於 DEC 與 evidence，`44` §4.2 的「基金代碼」一語過寬，後人易讀成任何代碼 | 高 | 可改以「只在 DEC 登記補註」處理（決策 (1) 方案 B） |
| 兩種情境共通 | 對現行程式行為**零影響**（純文件） | — | — |

### 2.8 若核准後的最小後續動作（只限文件層＋契約測試草案；不接資料、不改 Schema／provider）

**文件層**

1. 候選檔 `R-ID-1`「本次狀態」改記核准日與 DEC 編號（舊句劃線保留，沿用本檔體例）。
2. `docs/DECISIONS.md` 登記一筆（要點轉述／逐字依客戶回覆而定，標明「核准欄位數：1」「其餘 Pending」）。
3. 契約文字（T-ID1）放入核准後的 D2 契約文件，含第 5 點落差註記。

**契約測試草案（文字；未寫入 `tests/`，需另行授權才實作）**

| 草案 | 意圖 | 現況對照 |
|---|---|---|
| T-ID1-a | `contract.NAV_FIELDS` 第一欄＝`fund_code`／字串／不可空（鏡像 44 §4.2） | 已有：`test_契約_nav與44逐欄相同_source_tier值域相同` |
| T-ID1-b | `nav` 列 `fund_code` ＝呼叫端原值（去前後空白），不轉大小寫、不替換為 `full_key` | 未見專門測試（A-7，單組） |
| T-ID1-c | `fund_code` 空字串／前後有空白／非字串→`build_nav_table` 拋 `ValueError` | 未見直接測試（A-7） |
| T-ID1-d | 特徵化：Sheet 欄帶後綴（`acdd01-eqtal005`）→`ok=True`、`full_key=ACDD01-EQTAL005`、**無違反標記**（記錄已知落差，非期望行為） | 行為已被 `test_mapping_miss_passes_through` 釘住；落差說明尚無對應測試 |
| T-ID1-e | D2-A＝B 驗收（Sheet 欄遇後綴／網址／異常→標示違反、保留原值） | **production 無此行為**；屬 D2-A＝B 實作授權後才有意義，**不得先寫成會紅的測試進 CI** |

---

## 3. R-NAV-1｜`nav_orig_ccy` 逐列證據包

### 3.1 欄位與金融語意

- 浮點，單位「原幣／單位」，不可空；語意「當日單位淨值，大於 0」（44 §4.2）。
- 數值取來源序列所報值，`float()` 後原樣：**不換算、不四捨五入、不調整、不年化**（`test_數值_淨值保留原精度不四捨五入`）；字串可轉數字者會被收（`float("10.5")`），布林、非有限、溢位不收（`_rows_from_segment`）。
- **表內無 TWD 欄**（nav 表 7 欄固定，由鏡像測試鎖定）；不提供任何新臺幣換算（FX 閘門關閉）。
- **日期語意由 `nav_date`（R-NAV-2，Pending）帶**；**幣別由同列 `ccy`（R-NAV-5，Pending）帶**——`nav_orig_ccy` 單獨存在時只是一個沒有幣別、沒有日期的數字。
- 公式：無。

### 3.2 正式契約依據

| 依據 | 內容 | 位置／狀態 |
|---|---|---|
| `44` §4.2 | `nav_orig_ccy` 浮點、原幣／單位、不可空、大於 0；「**不補列**」：週末、假日、停止交易日沒有列，不以前一筆補一列；「可空為否的欄位取不到值，該筆不寫入，不以零或空字串補」 | frozen UI SSOT（不是 D2 核准） |
| `DEC-2026-11-08-04` Q5（要點轉述） | 非台幣基金仍可整理原幣資料，只把無法可靠換算者標「無法判定」，不得整檔判不可用 | `docs/DECISIONS.md` |
| `DEC-2026-10-29-01` 第 8 項（逐字檔） | Identity 與 NAV 必須分開；同一基本基金代碼不代表可無條件混用不同日期、幣別、share class、配息／累積型、避險型態、NAV series；「Same verified instrument / share class + same metric + same as-of + same currency = same canonical value」 | `docs/evidence/decisions/2026-10-29_dg2_final_ruling.md` 第 8 節 |
| `DEC-2026-11-05-03` | NAV 10 日規則不得升格為正式全頁產品規則 | `docs/DECISIONS.md` |
| `DEC-2026-11-08-02`、`DEC-2026-11-11-04` | FX 閘門維持關閉；不改 NAV source precedence | `docs/DECISIONS.md` |

### 3.3 目前資料來源與實作

| 項 | 說明 | 證據 |
|---|---|---|
| 取數 | 淨值走 A 鏈 `services/moneydj_fetcher.py::auto_fetch_moneydj`（客戶 2026-10-13 裁示復用既有多來源鏈，**來源與優先序不改**），經 `services/v2_tables/nav_dividend.py::fetch_nav_chain_with_error` 轉接；**每次開頁即時抓、不持久化** | `nav_dividend.py` 檔頭；前人準備包 R-NAV-1 ③ |
| 列組裝 | `nav_dividend.py::_rows_from_segment`：同日有無效值→該日全不寫；同日多個不同有效值→該日全不寫；同日同值併一列；`number <= 0` 不寫；寫列前再過 `contract.nav_row_problems` | 同檔；測試 `test_nav_同一日期同值只寫一列_不同值該日全不寫` |
| 幣別閘（與「原幣」直接相關） | 標籤只用持倉手填（hld）或 meta 自報（exp）；**A 鏈回報的 `currency` 一律不採用當標籤**；序列／累積點宣告與標籤不同→整檔不寫；非原生報價來源（晨星／Yahoo／AlphaVantage 前綴，`_NAV_NON_NATIVE_PREFIXES`）未宣告幣別→整檔不寫 | `nav_dividend.py::_chain_ccy_gate`、檔頭「幣別閘」段 |
| 累積序列 | `NAV_HISTORY_PROVENANCE_VERIFIED = False`：Sheet 累積點一律不寫，只剩累積點的檔整檔不寫 | `nav_dividend.py` |
| 可達性 | Preview：`ui_v2/{alo,hld}/{live,source}.py`、`exp` 經 `services/v2_tables/exp_nav.py`；`ui_v3` 對 `nav_dividend` 0 命中；Old UI 另有 `repositories/fund/*`、`services/fund_service.py` 第二條淨值路徑（`get_latest_nav`，`docs/v2/69` G-NAV-3，引，本組未重驗） | 附錄 A-4、A-8 |

### 3.4 已驗證證據與缺漏

**證據（檔案存在且斷言可讀，未跑）** —— 均在 `tests/test_v2_tables_nav_dividend.py`，除另註：

| 測試 | 鎖定什麼 |
|---|---|
| `test_契約_nav與44逐欄相同_source_tier值域相同` | 7 欄、無 TWD 欄、型別與可空與 44 相同 |
| `test_nav正例_逐欄照44_幣別取持倉手填_provenance記來源` | 正例逐欄 |
| `test_nav_零與負淨值不寫`、`test_nav_全NaN_一列都不寫_理由寫明`、`test_nav_部分NaN_只略過那幾筆_不ffill`、`test_小修4_4_溢位數值不寫_理由寫明` | 非正／非有限／溢位不寫、不 ffill |
| `test_nav_週末與假日沒有列_不補列`、`test_nav_停售基金_最後一筆之後沒有列`、`test_nav_新基金只有幾筆_照寫不補` | 不補列 |
| `test_nav_同一日期同值只寫一列_不同值該日全不寫` | 同日處理 |
| `test_數值_淨值保留原精度不四捨五入` | 不改寫數值 |
| `tests/test_nav_table_golden_c3a.py`（4 個 `def test_`）、`tests/test_nav_dividend_golden_c3a.py`（3 個） | 黃金檔，防行為漂移 |

**缺漏**

| # | 缺漏 | 狀態 |
|---|---|---|
| N-1 | **「原幣」依賴 `ccy`**：hld 路徑的幣別＝使用者持倉手填，經 `_chain_ccy_gate` 檢查「不與序列宣告衝突」；沒有獨立證明數值確實以該幣別計價（只能排除已宣告的衝突）。`ccy` 的契約（R-NAV-5）未核准 | 讀碼；見 §4 |
| N-2 | **無 share class／配息型別／避險型態／NAV series 欄位**；帶後綴的取數鍵其 NAV 與基本代碼的 NAV 是否同一序列＝**UNVERIFIED**（`docs/v2/70` §15.4、`DEC-2026-10-29-02`；`ACDD01-EQTAL005` 在客戶確認表中 `nav_equivalence="UNVERIFIED"`）。故 `nav_orig_ccy` 不得被讀成「該基金唯一 NAV」 | 引文＋`shared/fund_identity.py::CUSTOMER_CONFIRMED_SUFFIXES` |
| N-3 | 來源優先序／跨來源一致性：本列不證明；舊站另有第二條淨值路徑（G-NAV-3）、序列合併 Sheet 累積點（G-NAV-2）；BL-0524 待客戶裁示 | `docs/BACKLOG.md` BL-0524；69 引 |
| N-4 | 非原生報價來源「未宣告幣別一律整檔不寫」的真實覆蓋率＝NOT VERIFIED（BL-0545） | `TEXT_CCY_NON_NATIVE_UNDECLARED` |
| N-5 | 各 NAV adapter 在 Cloud 上的 live 可達性＝NOT VERIFIED；僅 Preview | 前人準備包 |
| N-6 | `is_estimated` 在 nav 列恆為 `False`（「來源給的是公布淨值」）；它屬 A1 B5「選備」，**不在 17 列內**，本核准不涵蓋 | `_rows_from_segment`；`d2_draft_A1_...` B5 |

### 3.5 Missing／Unavailable 語意

| 情境 | 契約應有的語意 | 現況 |
|---|---|---|
| 週末、假日、停止交易日 | 沒有列；**不 ffill、不補 0、不以前值補** | 已實作＋測試 |
| 該筆非有限／非正／布林／溢位 | 該筆不寫；同日有無效值→該日全不寫 | 已實作＋測試 |
| 同日不同值 | 該日全不寫（不猜哪個對） | 已實作＋測試 |
| 幣別缺或衝突 | **整檔淨值不寫**（`ccy_missing`／`ccy_conflict`），不補 USD；注意：這是因「幣別不明」，**不是**因「非台幣」（Q5） | 已實作＋測試（`test_nav_幣別缺_整批不寫_不猜不預設USD`） |
| 整檔無列 | 呈現層「⬜ 資料未取得／無法判定」；原因在旁路 `errors`／`withheld`／`skipped`，**不在表內** | 旁路已實作 |
| 要 TWD 值 | ⬜ 無法判定（FX 閘門關閉）；**不得整檔判不可用** | nav 表本就無 TWD 欄 |

### 3.6 核准的範圍

**若客戶核准 R-NAV-1，核准的是下列文字（擬議，總管讀法，客戶可逐字改；未核准前不具效力）：**

> **T-NAV1｜NAV 域 `nav_orig_ccy`**
> 1. 型別：浮點，有限且大於 0，不可空。語意：該基金於同列 `nav_date` 當日的**單位淨值**，採來源序列所報數值（`float()` 後原樣，不換算、不四捨五入、不調整、不年化）；**計價幣別以同列 `ccy` 為準**。
> 2. **表內無 TWD 欄**；不提供新臺幣換算；FX 閘門維持關閉。
> 3. 取不到值不寫列，不以 0、前一筆或估算值補；週末、假日、停止交易日沒有列屬正常；同日有無效值或同日不同值→該日全不寫；同日同值併一列。
> 4. 本欄**不代表**：share class、配息／累積型、避險型態、NAV series 的等價（同一基金代碼不隱含這些屬性相同）；亦不代表來源優先序或跨來源一致性已核准。
> 5. `ccy`（含其驗證方式與出處）、`nav_date`、`fetched_at` 的契約**另案**，本核准不含；`nav_orig_ccy` 的「原幣」解讀受同列 `ccy` 約束。

**不含（核准文字須同時寫明）：**

| 不含 | 原因 |
|---|---|
| `ccy`／`ccy_source`（R-NAV-5／6）、`nav_date`（R-NAV-2）、`fetched_at`（R-NAV-3） | 維持 Pending；與 D2-B 射程（§4）相關 |
| `source_tier`／供應者（R-NAV-4）、`is_estimated` | 維持 Pending／選備 |
| 任何 TWD 換算、FX | 閘門關閉 |
| NAV 來源優先序、`get_latest_nav`、累積序列閘門 | 不改 NAV source precedence；`NAV_HISTORY_PROVENANCE_VERIFIED` 維持 `False` |
| NAV 10 日規則、新鮮度門檻、PIT 取欄 | `DEC-2026-11-05-03`；D3(b)／D7 |
| 1Y 含息報酬（`value_pct`） | 公式層，BL-0427／BL-0524 未裁 |

### 3.7 核准與不核准的風險

| 情境 | 後果 | 可逆性 | 緩解 |
|---|---|---|---|
| **核准** — 與 `ccy` 脫鉤 | 契約說「原幣」，但幣別契約未核准、現況為使用者手填標籤＋衝突檢查，讀者可能以為幣別已被獨立證明 | 高（純文件） | 擬議文字第 1、5 點綁定同列 `ccy`、列為另案 |
| **核准** — 被讀成「該基金唯一 NAV」 | 後綴碼／不同 share class 的 NAV 被當成同一數字，違反逐字裁示第 8 項 | 高 | 擬議文字第 4 點排除等價主張 |
| **核准** — 被延伸到 TWD | 以為核可原幣就可換算 | 高 | 第 2 點明寫無 TWD 欄、FX 關閉 |
| **核准** — 被當成來源優先序背書 | 把「這個數字」連同「為何是這個來源」一併背書 | 高 | 第 4 點排除；`DEC-2026-11-11-04` 不授權改 NAV source precedence |
| **不核准** — NAV 域沒有任何非 Pending 欄位 | 後續 `nav_date`／`ccy` 等列缺少「值」這一欄的契約參照；NAV 域進度為 0 | 高 | — |
| 兩種情境共通 | 對現行程式行為**零影響** | — | — |

### 3.8 若核准後的最小後續動作（只限文件層＋契約測試草案）

**文件層**：候選檔 `R-NAV-1` 列改記核准日與 DEC 編號（舊句劃線保留）；`docs/DECISIONS.md` 登記；契約文字（T-NAV1）放入核准後的 D2 契約文件。**不新增 schema、不改 44。**

**契約測試草案（文字；未寫入 `tests/`，需另行授權才實作）**

| 草案 | 意圖 | 現況對照 |
|---|---|---|
| T-NAV1-a | nav 表欄位集合不含任何 TWD 欄（7 欄固定） | 已有：鏡像測試 `len(fields) == 7` 與 `NAV_FIELDS == fields` |
| T-NAV1-b | 非有限／非正／布林／溢位→不寫；不 ffill | 已有（§3.4 清單） |
| T-NAV1-c | 數值不被四捨五入 | 已有：`test_數值_淨值保留原精度不四捨五入` |
| T-NAV1-d | 同日不同值全不寫；同日同值一列 | 已有：`test_nav_同一日期同值只寫一列_不同值該日全不寫` |
| T-NAV1-e | 幣別缺或衝突→整檔不寫，不補 USD | 已有：`test_nav_幣別缺_整批不寫_不猜不預設USD`、`test_nav_同一檔多列持倉幣別互相不同_整批不寫` |
| T-NAV1-f | 文件—程式一致性：契約文字第 4 點「不代表 share class／NAV series 等價」為文字聲明，**無可測行為**，不寫測試，只在契約註記 | — |

---

## 4. D2-B 射程研究（不擴大至 NAV 全域；先研究 1Y 證據適用範圍）

> 本節**只研究**。結論一律標「總管讀法，可被客戶推翻」，**不替客戶決定 Q0**。

### 4.1 D2-B 字面原文（逐字，僅去除粗體標記）

出處：`docs/DECISIONS.md` `DEC-2026-11-09-01` ①(2)。該 DEC 的決策者欄寫明「客戶裁示，經總管轉達（repo 內無逐字存檔，**要點轉述，非逐字**；客戶可推翻）」，且「① 的各項內容為文件組依 `d2_contract_candidates` 該檔『下一批最值得核准事項』三題之方案 B／C／B 及總管派工單整理，不是客戶逐字」。

> **(2) D2-B＝收緊後的 C（1Y 含息證據欄位）**：不把 `as_of`、幣別直接列為新 Required。僅當同時成立：①基金身份與取數鍵可一致對應；②NAV 序列與計算使用資料一致；③日期與幣別來源可追溯；④無未解釋的跨來源／跨 share class／期間衝突，才可把 NAV 的日期／幣別當 1Y 含息輸出的同源證據。證據不足則對應欄位維持 Pending／無法判定：不由 `window_days` 推測窗口起日、不以讀檔當下時間冒充 `fetched_at`、不自行補幣別或資料末端日期。窗口起訖日、取得時間、算法版本仍依原 Gate 保留 Pending。此裁示只處理證據欄位與文件語意，不代表核准舊站 1Y 含息算法延伸至 New UI2；BL-0427 公式與日期窗口未決事項照舊，不改 350 天門檻或任何計算。

候選檔「題二」的題目是「**1 年含息輸出缺的欄位，契約要先認哪幾個？**」，其方案 C（被收緊的對象）原文為：「先認 as_of 與幣別（由 NAV 契約同一基金的 `nav_date`／`ccy` 組合，契約註明來源、不改輸出）」。

### 4.2 候選檔把「與 D2-B 衝突」套到 NAV 域的依據

| 位置（候選檔「Required 逐列待審表」） | 原文 | 套用方式 |
|---|---|---|
| 節前說明「與已裁示的衝突處理」 | 「上文原列（#3 `ccy`、#8 `as_of`、A1 B2／A9 等）仍標 Required／必備，但 `DEC-2026-11-09-01` D2-B 已規定 `as_of`、幣別不直接列 Required……原列與來源保留不刪，本表標 Pending，以正式 DEC 為準」 | 把 A1 B2（NAV `nav_date`）、A1 A9（NAV `ccy`）一併視為受 D2-B 降級 |
| R-NAV-2 `nav_date` | 「**與 D2-B 衝突**：`as_of` 不直接列 Required」 | 以 `nav_date`＝as_of 對映 |
| R-NAV-3 `fetched_at` | 「`DEC-2026-11-09-01` D2-B（不以讀取時間冒充觀測時間）」 | 引 D2-B 末段 |
| R-NAV-5 `ccy` | 「**與 D2-B 衝突**：幣別不直接列 Required」 | 同上 |
| R-PERF-3／R-PERF-6 | 「**與 D2-B 衝突**」；與 R-NAV-5／R-NAV-2「重複」 | 1Y 側欄位 |
| `DEC-2026-11-11-04` 「與既有 DEC 關係」(3) | 「本筆逐列審核時遇與其衝突者，一律以 `-09-01` 為準、維持 Pending」 | 把「是否衝突」的判斷交給逐列作者 |

**讀法依據的弱點**（總管讀法）：D2-B 的主詞是「**1Y 含息證據欄位**」；其四項條件①～④描述的是「**NAV 欄位被借用當 1Y 證據**」的前提（條件②「NAV 序列與計算使用資料一致」中的「計算」指 1Y 計算）。把它套到 NAV 表自己的 `nav_date`／`ccy` 欄位定義，需要再多一步推論（「NAV 的欄位定義若被借用就也要先過四項」），這一步**不在 D2-B 字面內**。

### 4.3 兩種讀法與後果

| 讀法 | 內容 |
|---|---|
| **A** | D2-B **只**約束「1Y 含息輸出引用 NAV 的日期／幣別當證據」與 1Y 輸出本身的缺欄（`as_of`、`ccy`、窗口起訖日、`fetched_at`、算法版本）。NAV 表自己的 `nav_date`／`fetched_at`／`ccy`／`ccy_source` 欄位定義，依各自的證據與其他 Gate 逐列審 |
| **B** | D2-B **也**使 NAV 域自己的 `nav_date`／`fetched_at`／`ccy`／`ccy_source` 須先通過四項同源證據才可進 Required（候選檔現行讀法接近此項） |

| 欄位 | 讀法 A 的走向 | 讀法 B 的走向 | 與讀法無關、仍存在的阻擋 |
|---|---|---|---|
| `R-NAV-2` `nav_date` | 可獨立逐列審「資料日」欄位定義 | Pending，直到四項證據成立 | `DEC-2026-11-05-03` 待決 (a)–(e)（若契約不含 10 日規則則不阻擋欄位定義）；PIT 取哪一欄未定；新鮮度門檻 D3(b)／D7 |
| `R-NAV-3` `fetched_at` | 可獨立逐列審；但「預存退回時取 `cache_updated_at`」語意與新鮮度綁在一起，前人準備包推薦等 D3(b) | Pending | `stale_after` 未裁（D3(b)） |
| `R-NAV-5` `ccy` | 可獨立逐列審；須如實標「驗證僅為三字母形狀檢查」 | Pending | `contract._is_iso_4217` 僅形狀檢查；非原生來源未宣告幣別整檔不寫的覆蓋率 NOT VERIFIED |
| `R-NAV-6` `ccy_source` | 隨 `R-NAV-5` | Pending | 旁路欄位，是否進契約欄未定 |
| `R-PERF-3` 1Y 的 `ccy` | **Pending**（D2-B 直接管轄；1Y 輸出無此欄） | **Pending** | 四項證據目前無法由文件證明（見 §4.4.4） |
| `R-PERF-6` 1Y 的 `as_of` | **Pending** | **Pending** | 同上 |
| `R-ID-1`、`R-NAV-1`、`R-NAV-4` | **不受影響** | **不受影響** | 非日期／幣別欄 |

**結論**：讀法差異只改變 **4 列**（`R-NAV-2／3／5／6`）的走向；**前人準備包 §4 把 `R-PERF-3／6` 也列入 Q0 涵蓋列，需修正**——該兩列在兩種讀法下結果相同（見 §6 補正表）。另，`R-ID-1` 一旦核准，只提供 D2-B 條件①的**契約錨點**，並不證明條件①。

### 4.4 1Y 證據適用範圍研究

#### 4.4.1 `resolve_1y_total_return` 輸出實有的鍵與分類

出處：`services/fund_total_return.py::resolve_1y_total_return`、`_unavailable`（本組逐行讀；回傳 dict 鍵恰為下列 8 個，無 `ccy`／`as_of`／`fund_code`／`fetched_at`／窗口起訖日／算法版本）。

| 鍵 | 值域 | 類別 | 何時為 `None`／缺 | 與 D2-B 的關係 | 17 列中的位置 |
|---|---|---|---|---|---|
| `value_pct` | 百分點 `round(,2)`｜`None` | 報酬值（非證據欄位，是被證據說明的值） | `status=unavailable` | — | R-PERF-2 |
| `status` | `ok`／`unavailable` | 狀態 | 恆有 | 字彙歸 D3(a)／(b) | R-PERF-7 |
| `reason` | 5 種碼｜`None` | 缺漏原因 | `status=ok` 時 `None` | — | R-PERF-8 |
| `source` | `自算（還原含息淨值）`／`—` | 計算口徑證據（≠供應者） | 無值時為 `—` | 口徑辨識 | R-PERF-4 |
| `window_days` | 整數日曆天｜`None` | 涵蓋期間證據 | 窗口未建／無窗口證據 | D2-B：**不由它推窗口起日** | R-PERF-5 |
| `div_count_in_window` | 整數｜`None` | 配息閘門證據 | 窗口未建（`None`≠0）；計數失敗 | — | 候選檔 E1 §1 #13（Optional），**不在 17 列** |
| `official_1y_pct` | 百分點｜`None` | 對帳證據（僅 `perf_source=="wb01"`） | 非 wb01 | 1B：**只對帳、不當主值** | 候選檔 #15（Optional），**不在 17 列** |
| `label` | 字串 | 呈現 | 恆有 | 呈現層；候選檔 #12 Excluded | **不在 17 列** |

**D2-B 所說「缺的證據欄位」（輸出沒有）**：`as_of`、`ccy`、窗口起訖日、`fetched_at`、算法版本、`fund_code`——共 6 項；其中 D2-B 明文處理前兩項（及不得冒充 `fetched_at`、不得推起日），其餘「維持 Pending」。

#### 4.4.2 窗口建立與 350 天門檻

出處：`services/fund_service.py::calc_metrics`（`ret_1y_total` 建窗區段，本組逐行讀）、`shared/signal_thresholds.py::RET_1Y_RESTORED_MIN_WINDOW_DAYS = 350`（註解自述「值 350 自既有 inline 搬入 SSOT，值未改」；**核准依據 NOT VERIFIED**）。

| 條件 | 結果 |
|---|---|
| `len(s) < 20` 或 `now <= 0` | 不建窗，`ret_1y_window_days=None`、`ret_1y_total=None` |
| `len(s) >= 252`（`shared/signal_thresholds.py::TRADING_DAYS_PER_YEAR`） | 窗首＝倒數第 252 **列**；`window_days`＝該列淨值日到末筆的日曆天；還原淨值法 `round((adj_end/adj_start − 1)×100, 2)` |
| `len(s) < 252` 且序列跨度 ≥ 30 天 | 窗首＝第一列；`window_days`＝整段跨度（**可遠大於一年**，稀疏／週頻序列） |
| `len(s) < 252` 且跨度 < 30 天 | 不建窗 |
| 窗口建立後 | `Adj_NAV`＝NAV×累積因子（因子＝1＋配息／當日 NAV），配息以日期 left-join，落在非淨值日的配息不加回（BL-0427 (1)） |

`resolve_1y_total_return` 的判定順序與「⬜ 資料未取得／無法判定」矩陣（輸出鍵恆為 8 個）：

| 順序 | 條件 | `status` | `reason` | `value_pct` | `window_days` | 測試（皆在 `tests/`） |
|---|---|---|---|---|---|---|
| 1 | `window_days` 有值且 < 350 | unavailable | `window_short` | None | 原值 | `test_compute_1y_total_return.py::test_short_window_is_unavailable_not_a_partial_value`（含 350／349 邊界）、`::test_window_short_takes_precedence_over_dividend_gate` |
| 2 | `ret_1y_total` 有值但 `window_days` 缺 | unavailable | `window_unknown` | None | None | `test_pr1a_audit_fixes.py::test_restored_value_without_window_days_is_window_unknown` |
| 3 | 配息型基金（`is_dividend_fund`）且 `div_count == 0` | unavailable | `dividend_data_missing`（文字變體 `dividend_data_missing_unaligned`） | None | 原值 | `test_compute_1y_total_return.py::test_dividend_fund_with_zero_dividends_in_window_is_unavailable`；`test_pr1a_audit_fixes.py::test_dividend_data_missing_text_says_unaligned_when_records_exist` |
| 4 | `ret_1y_total` 缺且有序列 | unavailable | `no_restored_value` | None | 原值 | `test_official_only_without_restored_value_is_unavailable` |
| 4' | `ret_1y_total` 缺且無序列 | unavailable | `no_series` | None | 原值 | `test_all_missing_is_no_series` |
| 5 | 值無法轉數字 | unavailable | `no_restored_value`（stderr 記錄） | None | 原值 | `test_non_numeric_restored_value_is_unavailable_not_ok` |
| 6 | 其餘 | ok | None | 數值（超出 [−95, 150] 只在 `label` 加警語，值照回） | 原值 | `test_restored_value_is_the_only_source`、`test_implausible_restored_value_is_flagged_not_dropped` |

**何時 1Y 回「資料未備」的歸納**：窗口 < 350 天、窗口無證據、配息型基金窗內無配息（或配息未對齊淨值日）、還原值缺（序列不足、計算例外、壞值）、無序列。**官方 `perf["1Y"]` 永不當主值**（`test_official_perf_1y_never_used_as_value_even_when_present`）。

#### 4.4.3 讀碼觀察（單組、未實跑）

1. **`value_pct` 不可脫離 `window_days` 解讀**：350 只是下限（BL-0427 (4)）；`len(s) >= 252` 的週頻序列 252 列≈4.8 年也可 `ok`，標籤仍是「1Y」。契約若收 `value_pct`，必須同時收 `window_days`。
2. **`reason=no_restored_value` 混合多種成因**：序列不足、`calc_metrics` 內計算例外（只 stderr `print`）、壞值，輸出不可區分。
3. **N1 實際可達性比前人準備包所述小**（修正前人 N1）：
   - (i) `len(s) >= 252` 時，窗口天數的 `try` 內只做 `pd.to_datetime(s.index[...])` 與相減；失敗才用 365。但同一函式後面還要 `pd.to_datetime(s.index)` 轉整條序列，**索引不可解析時後者同樣失敗→`ret_1y_total=None`→回 `unavailable`**，此時報出的 `window_days=365` 是未量測值但**不會伴隨 `ok` 值**。唯一可同時有 `ok` 值與 365 的情境是 `_window_actual_days == 0`（倒數第 252 列與末列同日，被 `or 365` 取代），需要資料已嚴重損壞。
   - (ii) `_days_span` 估算（`max(int(len(s)*1.4), 14)`）只在「索引跨度 < 7 天」時啟用，影響 `len(s) < 252` 分支的 `window_days`；要通過 350 門檻需 ≥ 250 列都落在 7 天內，真實 NAV 不可能；較可能的影響是在 `window_short` 的白話原因裡顯示一個估算的天數。
   - 因此 N1 是「**不得自行估一個合理值**」（CLAUDE.md §1）的違反疑慮，但讀碼推得**實際造成錯誤 `ok` 值的路徑極窄**。仍屬公式層，**本包不判、不修、不作為核准前提**；建議另派獨立組讀碼＋實跑。
4. 配息計數例外時 `ret_1y_div_count=None`，配息閘門（`div_count == 0`）不觸發，若 `ret_1y_total` 仍算出則回 `ok`（極窄路徑）。

#### 4.4.4 1Y 與 D2-B 四項條件的現況

| D2-B 條件 | 現況（讀碼／引文，單組） |
|---|---|
| ① 基金身份與取數鍵可一致對應 | `R-ID-1` 提供契約錨點；一致性本身依 `full_key` 規則（S7 未裁）與別名表（部署端可能不同，`mapping_source` 無法分辨 csv 不存在或讀取失敗），**未證明** |
| ② NAV 序列與計算使用資料一致 | **目前無法成立**：1Y 的輸入序列來自舊站 `calc_metrics`（`services/fundclear_backfill.py` 檔頭自述 Sheet 累積序列被 `fund_service._merge_nav_history_series` 併入後餵 1Y 計算），而 vNext `nav` 表因 `NAV_HISTORY_PROVENANCE_VERIFIED = False` 不讀累積點；且 `ui_v2`／`ui_v3`／`services/v2_tables`／`services/v2_domain` 對 1Y 函式 **0 命中**（A-9），New UI 路徑根本沒有 1Y 輸出 |
| ③ 日期與幣別來源可追溯 | nav 列有 `fetched_at`、旁路 `provenance`；1Y 輸出無任何日期／幣別 |
| ④ 無未解釋的跨來源／跨 share class／期間衝突 | 無機制判定；`check_cross_view_nav` 為 shadow、production 0 呼叫端（引 A1 B13，本組未重驗） |
| 機械化 | 四項是**逐基金的執行期性質**；`git grep` 未見任何程式判定這四項（A-10，字面 grep，單組）。如何機械判定＝NOT VERIFIED |

### 4.5 1Y 證據欄位與 NAV 欄位邊界表

| 概念 | `nav` 表（44 §4.2） | 1Y 輸出（`resolve_1y_total_return`） | D2-B 的處理 |
|---|---|---|---|
| 身份鍵 | `fund_code` | **無**（呼叫端 join key） | — |
| 值 | `nav_orig_ccy`（單位淨值，原幣） | `value_pct`（%，原幣還原報酬） | 不同東西，不得混名 |
| 資料日 | `nav_date` | **無 `as_of`** | `as_of` 不直接列 Required；借用 `nav_date` 須四項 |
| 幣別 | `ccy`＋旁路 `ccy_source` | **無** | 幣別不直接列 Required；借用 `nav.ccy` 須四項；不自行補 |
| 取得時間 | `fetched_at` | **無** | 取得時間維持 Pending；不以讀檔當下時間冒充 |
| 窗口 | —（單日點） | `window_days`（有）；起訖日**無** | 起訖日維持 Pending；不由 `window_days` 推 |
| 算法版本 | — | **無** | 維持 Pending |
| 來源／口徑 | `source_tier`（恆「淨值」）；供應者在旁路 `provenance.source` | `source`（計算口徑標識） | **同名異義**（前人 N3），契約須分名 |
| 狀態／缺值 | 旁路 `errors`／`withheld`／`skipped` | `status`／`reason` | 狀態字彙歸 D3(a)／(b) |
| 估值旗標 | `is_estimated`（恆 `False`，選備） | — | 不涉 |
| 對帳 | — | `official_1y_pct` | 只對帳 |
| 呈現 | — | `label` | Excluded |

### 4.6 小結（總管讀法，可被客戶推翻；不替客戶決定 Q0）

1. **1Y 證據適用範圍**：`resolve_1y_total_return` 的 8 個輸出鍵＋D2-B 所指「缺的證據欄位」6 項；它只存在於舊站、New UI 路徑 0 引用；`value_pct` 只在 `window_days >= 350` 且閘門通過時有值，且須與 `window_days` 一併解讀。
2. **D2-B 字面與讀法**：字面是「1Y 含息證據欄位」，我讀為讀法 A 較貼字面；讀法 B 需多一步推論（見 §4.2 弱點），但較保守（fail closed）。
3. **第四階段任務敘述的「D2-B 不擴大至 NAV 全域」**：這句是客戶任務的**轉述**（無逐字存檔、未登記 DEC），可能指 (i) 不把 D2-B 的約束套到 NAV 域欄位（≈讀法 A），或 (ii) 不把「D2-B 的研究／證據工作」擴大到 NAV 全域。兩者都導向「先只研究 1Y 證據」，與本節作法一致；但本包**不把它當成已登記的 Q0 裁示**。建議客戶用一句話確認 (i)，才據以處理 `R-NAV-2／3／5／6`（決策 (3)）。
4. **與本包兩列的關係**：無論 A 或 B，`R-ID-1`、`R-NAV-1` 的核准與否都不受影響。

---

## 5. 客戶決策表

> 推薦一律為**總管讀法，可被客戶推翻**。「涉及新資料契約」＝是否新增欄位、Schema、provider、來源、公式、門檻——**所有方案皆為否**（本批只做文件層）。

### 決策 (1)：是否核准 R-ID-1？核准什麼文字？

| 方案 | 做法 | 優點 | 缺點 | 風險 | 涉及新資料契約 |
|---|---|---|---|---|---|
| **A** | 核准 §2.6 `T-ID1`（限「基金代號欄」＋明標 D2-A＝B 未實作＋大小寫不正規化） | 證據最強；承載已核准的 D2-A＝B 契約文字方向；D2 核准欄位數 0→1，可演練逐列流程 | 契約先於實作，有已知落差；選股池碼（N5）仍無契約 | §2.7 | 否 |
| **B** | 暫不核准，只在 DEC 登記補註「D2-A＝B 契約文字方向」，待實作另授權後再審 | 不產生「契約宣稱 vs 實作」落差 | 落差仍無處承載；D2 欄位數維持 0 | §2.7 不核准列 | 否 |
| **C** | 核准更窄文字：只核「欄位存在、為 nav 主鍵之一、值＝呼叫端原值」，不寫命名空間與 D2-A＝B | 最不易外溢 | 與已核准的命名空間／D2-A＝B 文字方向脫節；後人需再補一次 | 低 | 否 |
| **推薦** | **A**（總管讀法）。若客戶偏好零落差→C | | | | |

### 決策 (2)：是否核准 R-NAV-1？

| 方案 | 做法 | 優點 | 缺點 | 風險 | 涉及新資料契約 |
|---|---|---|---|---|---|
| **A** | 核准 §3.6 `T-NAV1`（綁定同列 `ccy`、排除 share class／NAV series 等價、無 TWD 欄） | 自足、不涉 FX 與公式；測試最完整 | 「原幣」依賴尚未核准的 `ccy`，須靠文字綁定 | §3.7 | 否 |
| **B** | 暫不核准，待 `R-NAV-5`（`ccy`）一併審 | 避免「原幣」與幣別契約脫鉤 | NAV 域進度為 0；`ccy` 又受 Q0 影響 | 進度延後 | 否 |
| **C** | `R-NAV-1` 與 `R-NAV-5` 同批核准（綁定） | 語意完整 | **超出本包「僅 R-ID-1、R-NAV-1」範圍**，須客戶另行指定；`R-NAV-5` 另有形狀檢查等缺口 | 範圍擴大 | 否 |
| **推薦** | **A**（總管讀法）。C 需客戶明示擴大範圍 | | | | |

### 決策 (3)：D2-B 射程（Q0）

| 方案 | 做法 | 優點 | 缺點 | 風險 | 涉及新資料契約 |
|---|---|---|---|---|---|
| **A** | D2-B **僅**約束 1Y 含息證據欄位與其借用 NAV 日期／幣別的條件 | 貼字面標題；與第四階段「D2-B 不擴大至 NAV 全域」一致；`R-NAV-2／3／5／6` 可逐列獨立審 | 候選檔現行讀法需改寫；NAV 欄位要靠其他 Gate（D3(b)、`DEC-2026-11-05-03`）把關 | 若客戶實意為 B，會把本應 Pending 的欄位提早審 | 否 |
| **B** | D2-B 也約束 NAV 域 `nav_date`／`fetched_at`／`ccy`／`ccy_source` | 最保守（fail closed）；與候選檔現行標註一致 | 需四項同源證據，而 1Y 與 NAV 目前無共用路徑（§4.4.4）→ 這 4 列實務上長期 Pending | NAV 域進度長期停滯 | 否 |
| **C** | 暫不裁；`R-NAV-2／3／5／6` 逐列各自判，預設 Pending | 不必先答 Q0 | 每列都要重提一次理由 | 流程拖長 | 否 |
| **推薦** | **A**（總管讀法，可被客戶推翻）；請客戶以一句話確認第四階段敘述所指為 (i) | | | | |

### 決策 (4)：核准後要不要先寫「契約測試草案」？

| 方案 | 做法 | 優點 | 缺點 | 風險 | 涉及新資料契約 |
|---|---|---|---|---|---|
| **A** | 只做文件登記（DEC＋候選檔狀態＋契約文字） | 最小 | 兩列的缺漏（G4／G5）無測試承載 | 缺漏繼續無人鎖 | 否 |
| **B** | 另落盤「契約測試草案」文字（§2.8、§3.8），**不寫入 `tests/`** | 缺漏被登記；不增加 CI 風險；可供日後授權時直接取用 | 多一份文件 | 草案可能與日後程式漂移（需標日期） | 否 |
| **C** | 直接新增特徵化測試（`tests/`） | 缺漏被機器鎖定 | **屬程式施工，超出本批授權**；`T-ID1-e` 之類不得先寫成紅燈 | 需另行授權；跑測試需完整依賴環境 | 否（但需授權） |
| **推薦** | **B**（總管讀法） | | | | |

### 附帶待決點（非本包核准項，僅避免遺漏）

| # | 問題 | 說明 | 建議 |
|---|---|---|---|
| (5) | `R-PERF-1`（＝`R-ID-1` 的績效域重複列）如何處置？ | 1Y 輸出**沒有** `fund_code` 鍵；若客戶核准 `R-ID-1`，`R-PERF-1` 可「視為隨 `R-ID-1`」或「獨立保持 Pending」 | 總管讀法：維持 Pending，註記「join key，非 1Y 輸出欄」，避免暗示 1Y 輸出已核准 |
| (6) | 🔍 找基金路徑選股池代碼欄的命名空間（N5） | 無客戶裁示；`DEC-2026-10-29-01` 明言不得推廣；若要契約化屬 data identity 規則＝Stop Gate | 本包不處理；建議另案請客戶裁示，**不得在 R-ID-1 文字中順帶包含** |

---

## 6. 盲點、NOT VERIFIED

1. **未跑任何測試**：「有測試」＝檔案存在且斷言可讀；CI 狀態與依賴齊全環境下是否綠＝NOT VERIFIED。
2. **單組讀碼**：全稱句（「0 命中」「只有 N 處」）皆為字面 `git grep`，不含別名、動態組字、字串內嵌 import、非 `.py` 檔（附錄 A）；N1 修正（§4.4.3）與 N5 皆為讀碼推論，未實跑。
3. **客戶原話無逐字存檔**：第四階段任務敘述（含「D2-B 不擴大至 NAV 全域」）與 `DEC-2026-11-09-01`、`-11-11-04`、`-11-12-01`、`-11-12-02` 皆為要點轉述（轉達者含 ChatGPT 協作助手與總管），客戶可推翻；逐字存檔的只有 `DEC-2026-10-28-05`／`-10-29-01`／`-10-29-02`（`docs/evidence/decisions/`），本組已開讀 `2026-10-29_dg2_final_ruling.md`，**未開讀** `2026-10-28_dg2_identity_ruling.md` 與 `2026-10-29_dg2_nav_probe_ruling.md` 全文。
4. **「契約先於實作」的處理是客戶已選的方向**（D2-A＝B）；本包只是把落差明標，不評價該裁示。
5. **未開讀或僅引用**：`docs/v2/67`、`docs/v2/69`（G-NAV／G-RET 皆引）、`docs/v2/70`（僅 §15、§16 引文）、`DEC-2026-11-01-02`（只在 `docs/v2/70` 引文中見到）、`repositories/policy/v1.py::_extract_code_from_url`、`repositories/policy_supplement_repository.py`、`ui_v2/**/live.py` 的呈現層、`services/health/**`、Old UI `ui/**`。
6. **真實資料／Cloud／Active Sheet 覆蓋率**一律 NOT VERIFIED（BL-0545 BLOCKED，使用者未提供合法輸入）；帶後綴／網址代碼的實際比例未知（G7）。
7. **D2-B 四項條件如何機械判定**＝NOT VERIFIED（§4.4.4）。
8. **本包不含**：`R-ID-2／3`、`R-NAV-2～6`、`R-PERF-*` 的核可建議；NAV 10 日規則、Digest schema、其餘六域、FX。
9. **依 `PROJECT_RULES.md` §8**，涉及 data identity（R-ID-1）與 data semantics（R-NAV-1、D2-B 讀法）的內容，合併前至少需 1 組**真正獨立**稽核；本檔為單組作者產出。

### 對前人準備包（`docs/evidence/d2_contract_approval_prep_2026_11_12.md`）的補正

> 皆為本組讀碼所得、未經第二組驗證；本檔**不改**既有檔，建議由非作者 QA 複驗後再決定是否修文。

| # | 前人準備包位置 | 內容 | 本組補正 |
|---|---|---|---|
| 1 | §4 Q0「涵蓋列」含 `R-PERF-3／6` | 稱 Q0 一題決定 `R-NAV-2／3／5／6`、`R-PERF-3／6` 走向 | `R-PERF-3／6` 在兩種讀法下都 Pending；Q0 只改變 4 列（§4.3） |
| 2 | R-ID-1 ⑤ | 稱空字串／None／非字串→「該列不寫」 | 經 `build_nav_table` 路徑，`_group_funds` 對 `fund_code` 空白／前後空白**拋 `ValueError`**；「該列不寫」只適用直接呼叫 `rows_from_nav_series` 的路徑；資料層則在 `_key_text`／`holding_row_problems` 先濾 |
| 3 | R-ID-1 ③ | 稱 `fund_code` 為 `nav`／`dividend`／`fund_profile` 列鍵 | `dividend`／`fund_profile` 屬 D2-G3 延後之域；核准文字不宜涵蓋（§2.6 不含表） |
| 4 | R-ID-1 ③（及隱含） | 把 NAV `fund_code` 一律視為 Sheet「基金代號」欄值 | `exp` 路徑為選股池代碼欄（N5）；v1 格式 Sheet 為 URL 推得碼 |
| 5 | R-PERF-8 ④、R-PERF-5 ④ 的測試引用 | 稱 `window_short`、`window_unknown` 測試在 `tests/test_pr1a_audit_fixes.py` | `window_short` 測試在 `tests/test_compute_1y_total_return.py`；`test_pr1a_audit_fixes.py` 只含 `window_unknown` 與 `dividend_data_missing_unaligned` 文字測試（§4.4.2 表） |
| 6 | N1（R-PERF-5 ④） | 稱非量測路徑「列數 250～251 時估算值恰能過 350 門檻」 | 該估算僅在索引跨度 < 7 天時啟用，真實 NAV 不可達；且索引不可解析時後續計算亦失敗→不會 `ok`（§4.4.3）。N1 仍是 §1 疑慮，但實際造成錯誤 `ok` 值的路徑極窄 |

---

## 附錄 A：全稱句的驗證指令與輸出（repo 根目錄；基準 `6dcb51f8`；單組、未經第二組驗證）

| # | 指令 | 輸出 |
|---|---|---|
| A-1 | `grep -n "核准欄位數\|正式核准欄位" docs/DECISIONS.md` | 僅 `DEC-2026-11-11-04` 一筆（決策內容摘要欄）；`grep -n "^### DEC-2026-11-1[0-9]" docs/DECISIONS.md` 最後一筆為 `DEC-2026-11-12-02` |
| A-2 | `git grep -n "^FX_OBS_DATE_RULE_VERIFIED\|FX_OBS_DATE_RULE_VERIFIED *=" -- '*.py'`（排除 tests） | `services/v2_tables/market_indicator.py:107: FX_OBS_DATE_RULE_VERIFIED = False` |
| A-3 | `git grep -n "resolve_full_keys" -- app.py ui ui_v3 \| wc -l` | `0` |
| A-3b | `git grep -ln "resolve_full_keys" -- '*.py'`（非測試） | `scripts/bl0545_coverage_probe.py`、`services/fund_identity.py`、`services/fund_identity_shadow.py`、`services/v2_tables/{exp_profile,fund_keys,settings_store}.py`、`shared/fund_identity.py`、`ui_v2/{alo,exp,hld}/source.py` |
| A-4 | `git grep -n "build_nav_table\|nav_dividend" -- ui_v3 \| wc -l` | `0` |
| A-5 | `git grep -ln "sheet_code_contract_violation\|STATUS_SHEET_CONTRACT_VIOLATION" -- '*.py'`（排除 `tests/`） | `services/fund_identity.py`、`services/fund_identity_shadow.py`、`shared/fund_identity.py` |
| A-6 | `git grep -n "input_source" -- services/v2_tables \| wc -l`；`git grep -n "DG2_SHADOW_ENABLED" -- '*.py'`（排除 tests） | `0`；旗標定義 `shared/fund_identity.py:19 = False`，唯一 hook 判斷在 `services/v2_tables/fund_keys.py` |
| A-7 | `grep -n "fund_code 須為\|前後無空白" tests/test_v2_tables_nav_dividend.py`；`grep -n '"fund_code": "[a-z]' tests/test_v2_tables_nav_dividend.py` | 皆無輸出（人工判讀：未見針對 `fund_code` 空白 raise、大小寫不正規化的直接測試）；`def test_.*full_key` 類測試存在（`test_nav_沒給full_key_當場炸…`、`test_7_full_key前後帶空白就raise`） |
| A-8 | `git grep -ln "build_nav_table\|build_nav_dividend_tables" -- '*.py'`（非測試） | `services/moneydj_fetcher.py`、`services/v2_tables/{__init__,exp_nav,nav_dividend,settings_store}.py`、`ui_v2/alo/{live,source}.py`、`ui_v2/hld/{live,source}.py` |
| A-9 | `git grep -n "resolve_1y_total_return\|ret_1y_total\|compute_1y_total_return" -- ui_v2 ui_v3 services/v2_tables services/v2_domain \| wc -l` | `0` |
| A-10 | `git grep -nE "同源證據\|same_source\|same-source\|D2-B" -- '*.py'` | 僅 `tests/test_wf03_research_invest_calc.py:1287` 一個無關測試名（`..._same_source_rate_...`）；未見程式判定 D2-B 四項條件 |
| A-11 | `git grep -n "RET_1Y_RESTORED_MIN_WINDOW_DAYS" -- '*.py'`（非測試） | `shared/signal_thresholds.py:235 = 350`；消費者 `services/fund_total_return.py`、`services/fund_service.py`、`services/health/dividend.py`（註解） |
| A-12 | 讀 `services/fund_total_return.py::resolve_1y_total_return` 與 `_unavailable` 回傳 dict 鍵 | 鍵恰為 `value_pct／status／reason／source／window_days／div_count_in_window／official_1y_pct／label`；無 `ccy`、`as_of`、`fund_code`、`fetched_at` |
| A-13 | `grep -c "^def test_\|^    def test_" tests/test_v2_tables_fund_keys.py tests/test_v2_tables_nav_dividend.py tests/test_compute_1y_total_return.py tests/test_nav_table_golden_c3a.py tests/test_nav_dividend_golden_c3a.py tests/test_pr1a_audit_fixes.py tests/test_fund_identity_dg2.py` | 44／75／16／4／3／9／60 |
| A-14 | `git grep -ln "def <測試名>" -- tests`（逐一確認 §2.4、§3.4 引用的測試名） | 皆命中所述檔案 |
| A-15 | 讀逐字檔 `sed -n 1,215p docs/evidence/decisions/2026-10-29_dg2_final_ruling.md` | 第 1、2、4、8 節原文如 §2.2、§3.2 所引 |

---

> **本檔限制重申**：核准準備包、非客戶裁示；D2 核准欄位數＝0；未新增 Schema／provider／資料來源／公式；未改任何既有檔；單組作者、未實跑測試、尚待非作者獨立 QA。擬議契約文字（`T-ID1`、`T-NAV1`）為待客戶修改或否決的草稿。
