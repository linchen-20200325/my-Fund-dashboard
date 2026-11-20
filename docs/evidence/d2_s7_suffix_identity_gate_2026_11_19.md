# S7「通路後綴身分規則」最小 Decision Gate 卡（D2 身份域：R-ID-2／R-ID-3 之前置）

> **卡狀態（2026-11-20 起）**：單組草稿；稽核 1 組（與作者共享派工來源）；修正後未複驗。稽核結果與更正見文末「2026-11-20 獨立稽核後修正」節。
> ~~**單組作者（執行組）草稿，尚待非作者獨立稽核。**~~（2026-11-20 有意識的更正，不是漏刪：「尚待稽核」已過時，稽核已做 1 組；舊句當時為真。） 屬 data identity 等級（`DEC-2026-10-16-05`、`PROJECT_RULES.md` 第 4 節「data identity 規則」＝須停下問客戶；第 8 節＝至少 1 組真正獨立稽核）。
> **docs-only 候選；不是客戶裁示、不是契約核准、不是施工授權**（`CLAUDE.md` §-1）。基準 `origin/main` `eb08c5fc`（2026-11-19，唯讀 `git show`）。路徑寫「檔案::符號」不寫行號。
> 標記：**[F]**＝可由檔案／文件重現；**[I]**＝推論；**[R]**＝推薦，可被客戶推翻。全稱句一律「單組未驗」。
> **方向來源**：「D2 Q-ID 採方案 1，先釐清 S7 再核 R-ID-2／3；不採方案 2；本批不改 resolver、別名表、Schema，不升格 DG2」為 ChatGPT 總管裁示（客戶經 ChatGPT 轉達〔待核〕，非逐字，~~repo 無對應 DEC~~——〔2026-11-20 有意識的更正，不是漏刪：舊句在寫卡時為真；其後 `docs/DECISIONS.md` 已有 `DEC-2026-11-19-10`，要點轉述、來源待核，記「D2 Q-ID 採方案 1（先釐清 S7）」方向，**S7 規則本身未裁**。兩邊理由：舊句提醒「此方向無逐字」仍成立；被推翻的是「repo 無對應 DEC」〕）。本卡不把它寫成客戶逐字規格。已回答事項（R-ID-1、R-NAV-1／2／4／5 契約文字、`-19-02`／`-19-05` 方向、#1286 卡內已問過者）不重提。

## 0. 白話：要客戶回答什麼
系統裡有一個「取數用的基金代碼」（`full_key`）。有些輸入帶「通路／商品後綴」（例：`TLZF9-AL001`、`ACDD01-EQTAL005`）。**現在系統遇到帶後綴的代碼會直接放行、不標記**，但已核准的 R-ID-1 又說 Sheet「基金代號」欄帶後綴＝違反契約（**R-ID-1 的來源 `DEC-2026-11-13-06` 為要點轉述：客戶經總管轉達、非逐字、repo 無逐字存檔；其所依的 `DEC-2026-10-29-01` 第 4 項則有客戶逐字存檔**）。兩邊說法相反，所以 R-ID-2／3 沒法照現況寫成契約。（2026-11-20 補：「兩邊相反」須區分**標示違反**與**阻擋取數**兩件事，見 §i M2；R-ID-1 只要求前者。）
~~**要問的唯一一題**~~（2026-11-20 **有意識的更正，不是漏刪**；兩邊理由：舊句想讓客戶只面對一個明確問題，這個簡化意圖成立；但它把「規則」與「範圍」合成一題，會讓客戶以為答「不可以」就已決定範圍，被權衡掉的是「唯一」。更正：實為**兩個子題**——子題 1「規則」＝取數代碼可不可以帶後綴；子題 2「範圍」＝若不可，適用哪些入口（見 §i M3）。舊句把兩題合成一題，會讓客戶以為答「不可以」就已決定範圍）：「取數用基金代碼」可不可以帶後綴？**執行組推薦（可被推翻）：不可以——取數用代碼只收「基本代碼」；（2026-11-20 補：此推薦同時含「判失敗」效果，超出 R-ID-1 只標示的範圍，見 §i M2。）（2026-11-20 第三次複驗補：此「不可以＝判失敗」推薦已被 §3 劃線更正，現推薦為 §i 草稿的 A0〔只標示、不阻擋〕；本 §0 句保留為歷史。）後綴屬於另一層（商品／通路層），日後另開 Gate。注意：R-ID-1 明文只管 Sheet 基金代號欄、不得推廣；這個推薦對 Sheet 入口是延續、對其他入口（選股池、🔍 查詢等）是『R-ID-1 之外的新增推廣』，客戶須明確接受這一點。** 代價：帶後綴的輸入將從「靜默放行」變成「明確判不通過」，現行靠放行在跑的輸入~~（若有）~~（2026-11-20 **有意識的更正，不是漏刪**：很可能有、比例未知〔BL-0545 BLOCKED〕；舊「若有」在寫卡時合理，被推翻的是「是否存在」這個不確定度——客戶已提過實例，見 §i Should-Fix 5）會變成取不到資料（符合 Fail Loud，但實際影響多大，目前**無法查證**，見 §6）。

**編號對照（避免誤讀）**：ChatGPT 總管裁示的「採方案 1、不採方案 2」指的是**上一張 D2 Gate 卡 `docs/evidence/d2_next_domain_gate_card_2026_11_19.md` 的 Q-ID 方案**（方案 1＝先裁 S7；方案 2＝把現況如實寫成契約）。本卡 §2 的 **S1～S4 是 S7 這一題自己的規則選項**，與那兩套編號不同：本卡 S4（維持現況）＝上一卡方案 2 的內容；**「不採方案 2」≠ 不採本卡 S2**。

## 1. 現行行為事實（[F]；已實讀 `eb08c5fc` 檔案，未執行程式、未跑測試）

| # | 事實 | 出處 |
|---|---|---|
| F1 | resolver 對照鏈：輸入須 ASCII → `strip()` → `upper()` → `parse_moneydj_input` → 別名表 → 最終 `_is_pure_code`。`_is_pure_code`／`PURE_CODE_PATTERN` ＝ `^[A-Z0-9]{3,30}(?:-[A-Z0-9]{2,20})?$`，**允許一個 `-` 加 2–20 碼後綴**；別名表未命中則原樣用 `code`；`portal` 恆 `""`。 | `services/v2_tables/fund_keys.py`（檔頭、`PURE_CODE_PATTERN`、`_is_pure_code`） |
| F2 | 帶後綴輸入現行 `ok=True`、`mapping_hit=False`、`full_key` 原樣（`acdd01-eqtal005` → `ACDD01-EQTAL005`），**無任何違反標記**；此行為被測試釘住。 | `tests/test_v2_tables_fund_keys.py::test_mapping_miss_passes_through` |
| F3 | 舊單檔頁（L1 編排）另有 `canonicalize_moneydj_url`：**只對行動版網址樣式**把 `a=` 值截到第一個 `-` 之前；新 resolver 刻意不含此步，故「行動版網址＋後綴」舊頁得主碼、新 resolver 得整段（檔頭自述，且稱兩邊**還有其他差異、未逐一比對**）。 | `fund_keys.py` 檔頭「少掉的一步」；`repositories/fund/fund_orchestration.py` |
| F4 | **R-ID-1 的「違反」定義**（客戶裁示 `DEC-2026-10-29-01` 第 4 項、`-03` 第 1 項〔均有客戶逐字存檔，摘要由執行組整理〕；`T-ID1` 經 `DEC-2026-11-13-06` 核准〔要點轉述，非逐字〕）。**範圍：`T-ID1` 第 1 項與 `DEC-2026-10-29-01` 第 1 項明文只適用 Sheet「基金代號」欄、不得推廣到其他 code／欄位／來源。**Sheet「基金代號」欄只接受 MoneyDJ 基本代碼；網址／`-` 後綴／格式異常＝`sheet_code_contract_violation`，**原值保留、不剝不截不改寫、只標記**。shadow 版 `_sheet_contract_violation` 的判準：非字串、空白、非 ASCII、網址、含 `-`、不合 `[A-Z0-9]{3,30}` 任一即違反。 | `DEC-2026-10-29-01`／`-03`；`services/fund_identity.py::_sheet_contract_violation`（共用原則見其 docstring；其中「大小寫／前後空白沿用 `fund_keys`」是執行組讀法，未經客戶逐條確認） |
| F5 | **`T-ID1` §5 已知落差**：契約要求違反須標示，**production 尚未實作**——現行解析鏈對帶後綴輸入可能判 `ok=True` 並產出 `full_key`，且不產生違反標記；`DG2_SHADOW_ENABLED = False`。**方向＝契約（應標示）高於實作（沒標示）。** | `DEC-2026-11-13-06` 附一 `T-ID1` 第 5 點；`shared/fund_identity.py::DG2_SHADOW_ENABLED` |
| F6 | **DG-2 shadow 已有後綴分類，但不在 production**：只在「已驗證 mapping」（注入的通路表，或 L0 `CUSTOMER_CONFIRMED_SUFFIXES`，目前僅 `ACDD01`＋`EQTAL005` 一組，`nav_equivalence=UNVERIFIED`）命中時才剝後綴；MoneyDJ 證據有但後綴未驗 → `moneydj_suffix_unverified_not_stripped`；FundClear `AGIF-HT5`／`AGIF-HTG` 任何命名空間都不剝。唯一 hook 在 `resolve_full_keys` 尾端，flag 關時連 import 都不做。 | `shared/fund_identity.py`；`services/fund_identity.py`；`docs/v2/70` 第 15 節 |
| F7 | **客戶已裁的身分語意**（`DEC-2026-10-29-03` 第 1 項；摘要為執行組整理，逐字在 `docs/evidence/decisions/2026-10-29_dg2_fund_product_holding_ruling.md`，本組**只讀 DEC 摘要、未讀逐字檔**）：身分分三層——Fund（MoneyDJ 基本碼）／Insurance Product-Channel（`ACDD01-EQTAL005`：`ACDD01`＝基金碼、`EQTAL005`＝保險商品代碼，**不是** share class、另一檔基金或另一條 NAV 序列）／Holding；**Identity／NAV／Product Mapping／Holding 四種 resolver 不得混用**。 | `DEC-2026-10-29-03` |
| F8 | **NAV 等價性未證**：`TLZF9`／`-AL001`／`-24A7` 同日同 NAV 8.4121 僅為「strong observational evidence」，不得寫成 strictly comparable；`CUSTOMER_CONFIRMED_SUFFIXES` 標 `nav_equivalence=UNVERIFIED`。 | `DEC-2026-10-29-02`／`-03`；`shared/fund_identity.py` |
| F9 | **別名表跨部署非確定性**：別名表＝內建 `_DEFAULT_MAPPING`（12 筆）＋可選 `fund_code_mapping.csv`；`git ls-tree` 查無此 csv（部署端有無＝未驗）；`mapping_source` 只分 `builtin`／`csv+builtin`／`injected`，且 `builtin` **分辨不出「csv 不存在」與「csv 讀取失敗而退回內建」**；同輸入在不同部署可得不同 `full_key`。D2-C＝B（`DEC-2026-11-09-01`）：別名內容不升格，只收 `mapping_source` 追溯。 | `fund_keys.py` 檔頭 provenance 段；`repositories/fund/sources.py::_DEFAULT_MAPPING`；`d2_contract_approval_prep` R-ID-2 ④ |
| F10 | **通路後綴在 L1 有真實用途**：`_BANK_PLATFORM_CODES` 以「基本碼 → 各通路（domain, 完整帶後綴碼, page_type）」記錄，例 `TLZF9` → `TLZF9-1180`／`TLZF9-24A7`…。即後綴不是雜訊，舊 L1 取數路徑用它去不同通路網域取頁。新 resolver 的 `full_key` 是否被用來走這條路徑＝**未驗**。 | `repositories/fund/sources.py::_BANK_PLATFORM_CODES` |
| F11 | NAV 鏈對 `full_key` 有核對：A 鏈回傳的 `full_key` 與 `fund_keys` 的不同或缺失 → 該檔淨值不寫（`TEXT_KEY_MISMATCH`／`TEXT_KEY_MISSING`）。故 `full_key` 的語意變動會直接影響 NAV 是否寫出。`NAV_FIELDS` 無 `full_key`／mapping 欄。 | `services/v2_tables/nav_dividend.py`；`services/v2_tables/contract.py::NAV_FIELDS` |
| F12 | `-19-02` Q2(4)(6)：路徑 B 專屬——`ok` 只代表格式通過、不升格 R-ID-2／3、不授權 ISIN resolver／別名表／**後綴碼正式語意（Q3②／S7）**。`-18-01` 只授權 R-ID-2／3「最小必要內部取數鍵語意」的**研究**，明列不核准 R-ID-2／3。 | `DEC-2026-11-19-02`；`DEC-2026-11-18-01` |
| F13 | **`fund_keys.resolve_full_keys` 的呼叫端不只 Sheet 入口**（`git grep` 已核；結果為單組、未驗是否窮舉）：`ui_v2/hld/source.py`、`ui_v2/alo/source.py`、`services/v2_tables/settings_store.py`（以上取自持倉 `fund_code`＝Sheet 入口）；`ui_v2/exp/source.py`（選股池／EXP 代碼，命名空間另案，`-13-06` (4)）；`ui_v3/adapters/fund_lookup.py`／`viewmodels`（🔍 路徑 B 單檔查詢，loader 由呼叫端注入，目前離線）；`services/v2_tables/exp_profile.py`（消費 `resolve_full_keys` 回傳）；`services/fund_identity.py`、`services/fund_identity_shadow.py`（DG-2 shadow，flag 關）；`scripts/bl0545_coverage_probe.py`（離線探針）。`resolve_full_keys` 本身**沒有 `input_source` 參數**，無法區分入口；`docs/v2/70` 第 15.2 節自述其 hook 因「輸入混有其他來源」不宣告 Sheet 來源。 | 同欄各檔 `import`／呼叫處（非 tests） |

**[I] 小結**：現況有三層不一致——(1) 契約層：R-ID-1 說後綴＝違反；(2) 實作層：resolver 對後綴靜默放行；(3) 影子層：DG-2 shadow 早有「已驗證才剝、未驗證不剝」的分類，但未接 production。S7 要裁的是：**取數鍵這一層要跟哪一層對齊。**

## 2. 規則選項（本批只問「規則」；「需改程式」欄全屬**日後施工**，本批不改 resolver／別名表／Schema，不升格 DG2）

| 選項 | 規則內容 | 優點 | 缺點 | 風險（[I]） | 與 R-ID-1 一致性 | 日後是否需改程式 |
|---|---|---|---|---|---|---|
| **S1（[R]）禁止** | `full_key`＝MoneyDJ **基本代碼**（經別名表者取其 `public_code`）；帶後綴（或網址帶後綴）輸入判「未通過」（`ok=False`，原值保留，附原因），**不剝不截不改寫**。〔2026-11-20 提醒：`ok=False`／`full_key=None` 會使持倉下游取不到 NAV（F11），這是「阻擋取數」，不只是「標示」，見 §i M2；另 F4 的大小寫／空白沿用 `fund_keys`（輸入先 `upper()`）與 `T-ID1` 第 2 點「不轉大小寫」有字面落差，S1 若成規則須一併釐清。〕後綴歸商品／通路層，另開 Gate | 規則最簡、可機測；對 Sheet 入口與 R-ID-1 同向；符合 F7「resolver 不得混用」；與 `-10-29-01` 第 4 項「未知後綴不得盲目處理」同向；不需先建通路表 | 原本靠放行的帶後綴輸入會改為判失敗（Fail Loud，非錯值）；若 `full_key` 實際用於走通路頁（F10），該路徑須另有出口（商品／通路層，本批不做）；與 L1 舊頁行為差更大；**會在 `full_key` 層關掉 `DEC-2026-10-29-01` 第 4 項第 3 點客戶已裁的路徑（已驗證 mapping 命中者可辨識通路後綴）**；`full_key` 層沒有入口維度（F13），規則套在 resolver 就是套到**所有**呼叫端 | **未知（不可查證，BL-0545 BLOCKED）**：受影響入口＝F13 所列的 hld／alo／settings（Sheet）、exp（選股池）、🔍 路徑 B、shadow、探針；真實輸入有多少帶後綴無法得知；屬 identity 規則變更（Stop Gate） | ~~**Sheet 入口一致；**~~ **方向相同、效果超出**（2026-11-20 更正：R-ID-1 只要求標記並保留原值，S1 的「判失敗」另含阻擋取數；非 Sheet 入口＝R-ID-1 之外的新增推廣，R-ID-1 明文只限 Sheet 欄、不得推廣；舊句的「一致」過強，被權衡掉的是「效果相同」之說） | **需**（resolver 加「不含 `-`」判定或等價並補違反標示；若只想限 Sheet 入口，另須新增 `input_source` 類參數＝介面變更；日後施工） |
| S2 已驗證才放行 | 僅「已驗證 mapping」命中者（通路表／客戶確認表）可帶後綴，且須附 `suffix_verified` 標記；其餘同 S1 | 保留已知通路用途；沿 `DEC-2026-10-29-01` 第 4 項第 3、4 點精神 | 「已驗證」名單來源未定（`docs/v2/70` 第 15 節自述：把整張 `_BANK_PLATFORM_CODES` 當已驗證是執行組讀法，客戶確認的只有 `TLZF9-AL001`、`TLZF9-24A7`、`ACDD01-EQTAL005` 三個）；`CUSTOMER_CONFIRMED_SUFFIXES` 僅 1 組；同一 Sheet 輸入在 R-ID-1 為違反、在 `full_key` 為通過（需明寫「輸入來源」維度）；契約複雜度升高 | **中至高**：等於把 DG-2 shadow 規則帶進 production（接近升格 DG2，與本批「不升格 DG2」張力） | **部分一致**（僅非 Sheet 入口） | **需**（較大：接 mapping 與標記） |
| S3 不透明放行＋必標 | 後綴一律當不透明字串放行，但輸出必帶「後綴未驗證」旗標，不剝不判斷 | 不拒絕任何輸入；滿足「不得靜默」 | 與 R-ID-1 方向仍相反（Sheet 帶後綴＝違反 vs 這裡＝通過加旗標）；旗標屬新欄位＝Schema 變更；把「後綴語意未裁」寫進契約 | **高**（新旗標＝Schema 題；易被讀成採信後綴） | **不一致（有旗標緩衝）** | **需**（含 Schema 變更，超出本批） |
| S4 維持現況（不標） | ~~即 prep ⑦ 的 A／上一張 D2 卡的 Q-ID 方案 2（「不採方案 2」所指）~~（2026-11-20 有意識的更正，不是漏刪：二者**不等價**——上一卡方案 2＝現行接受後綴＋明寫已知缺口＋S7 未裁；S4＝維持現況**不標**也不寫缺口。兩邊理由：舊句把二者畫等號有簡潔之利，且二者都「維持放行」；但差在是否明寫已知缺口，畫等號會讓「不採方案 2」被誤讀為「S5 也不採」，被權衡掉的是簡潔，見 §i Should-Fix 4） | 零程式 | 把靜默放行升格為契約；與 R-ID-1 直接矛盾；跨部署非確定性被寫進契約 | **高** | **矛盾** | 否 |

| S5（2026-11-20 新增）明標已知缺口、S7 未裁 | 現行接受後綴不變；R-ID-2／3 契約文字明寫「後綴行為未裁、跨部署非確定性為已知缺口」，不判失敗、不標示 | 零程式；不把缺口寫成規則；＝上一卡方案 2 的實質內容 | 仍與 R-ID-1 方向相反；缺口持續存在 | 中（以文件標示取代處置） | 不一致，但誠實標註 | 否 |

**不在本題**：別名表是否關閉（GD-Q3①）、入口是否放行後綴碼為不透明字串（GD-Q3②，路徑 B 入口，`-19-02` 不授權清單）、ISIN、canonical identifier／DG-2 轉正（BL-0527 第 5 項）。S7 的答案**可能影響**但**不決定**這些題；本卡不替它們作答。

## 3. 總管推薦（[R]，可被客戶推翻；執行組推薦，非客戶裁示）
~~**推薦 S1。**~~（2026-11-20 **有意識的更正，不是漏刪**：現行推薦轉為 §i 最小 Gate 草稿的 **A0**——Sheet 入口只標示違反、保留原值、**不阻擋取數**；A0 與 A 的差異＝是否阻擋取數（A 令 `ok=False`／`full_key=None`，帶後綴持倉取不到 NAV；A0 照舊產出 `ok`／`full_key`，另附違反標記）。兩邊理由：S1 的優點（規則簡單、可機測、與 F7 同向）仍成立；被權衡掉的是它的阻擋效果超出 R-ID-1 只標示的字面、且套到所有入口。**`DEC-2026-11-19-10` 區分欄 3 記載的「S7 卡推薦 S1」是歷史記錄（當時卡的推薦），現推薦已轉 A0；該 DEC 不改。**）以下為舊推薦理由，保留作對照。理由：(i) 對 Sheet 入口與 R-ID-1 ~~同向~~方向相同（效果超出，見 §i M2）〔2026-11-20 **有意識的更正，不是漏刪**：兩邊理由——「同向」在方向上仍成立，但 S1 判失敗＝阻擋取數，效果超出 R-ID-1 只標示；被權衡掉的是「完全同向」之說〕、且不需先決定「誰是已驗證通路」的規則（**對非 Sheet 入口則是新增推廣，需客戶明確接受**）；(ii) 客戶 `-10-29-03` 已把後綴歸到商品／通路層並要求 resolver 不混用，S1 只是讓取數鍵層遵守同一條；(iii) 不依賴別名表／DG-2 轉正，與「本批不改別名表、不升格 DG2」相容；(iv) 規則可一句話寫成契約文字、可機測。
**代價（須告知客戶）**：(a) S1 是 identity 規則變更，後續須施工才會真正生效（本批只定規則）；(b) 影響面無法在現況查證（BL-0545），且會關掉 `-10-29-01` 第 4 項第 3 點在 `full_key` 層的已裁路徑；(c) 若真有需要用後綴走通路取數的流程（F10），須另開商品／通路層 Gate，S1 不替它解決；(d) 在施工前，契約文字與 production 行為仍有落差（同 `T-ID1` §5 的方向：契約高於實作），須據實標「尚未實作」。
**若客戶偏好保留通路用途**：選 S2，但請先指定「已驗證」名單來源與「是否因此升格 DG2」——這兩件事 S2 都繞不開。

## 4. 裁示後 R-ID-2／R-ID-3 如何接續（只寫契約文字層，**不施工**）
S7 裁示後，才另開「R-ID-2／R-ID-3 契約文字」候選與最小 Decision Gate（逐字核准另行）。**僅示例、非候選條款**：`full_key`＝MoneyDJ 取數用代碼，可能經別名表映射（D2-C＝B，僅留 `mapping_source`）；`ok`＝僅表示格式通過、不表示基金存在（`-19-02` Q2(4)，僅路徑 B 已核；擴到全域＝〔I〕新問題）；後綴條款依 S7 結論而定並明標「尚未實作」；別名跨部署非確定性列為已知缺口。NAV 取用的「`full_key` 不一致則不寫」屬 `T-NAV1` 之外新增，另須 Gate。Digest 層角色不在此預判。

## 5. 仍不授權（本卡與 S7 裁示皆不觸及）
改 resolver／`fund_keys`／別名表／`fund_code_mapping.csv`／Schema／`NAV_FIELDS`；啟用或升格 DG2（`DG2_SHADOW_ENABLED` 維持 `False`）；ISIN resolver、share class mapping；實作 D2-A＝B 違反標示；Gate-D 路徑 B 的 Q3①②、Q0、Q6～Q11、X1～X5；R-NAV-3／6、R-PERF；真實取數與探測（MoneyDJ／TDCC／FundClear）；BL-0545 輸入、BL-0551；frozen 44；FX；任何 UI／Digest／OneBrain 施工。

**Model／Effort（[R]，可被推翻）**：本卡與 S7 裁示屬文件；**日後 identity 施工（改 resolver、違反標示）屬 `PROJECT_RULES.md` 第 5 節矩陣「重大資料身分／資料契約」列（Opus 5.5／High）**，是否觸發 Change Gate 由總管依第 5.1 節判斷，本組未評估。

## 6. 未查證項
1. **單組作者**；§1 的「無／未驗」類全稱句是檔案讀取與文件比對，改名、別名、動態組字串不在內。
2. **未執行任何程式、未跑任何測試**；`test_mapping_miss_passes_through` 的行為取自讀測試原碼與 `T-ID1` §5 自述。
3. **真實 Sheet 的帶後綴輸入比例＝無法查證**（BL-0545 BLOCKED）；S1 對現行使用的實際影響未知。F13 的呼叫端清單為單組 `git grep`，未驗窮舉；`ui_v2/exp/source.py` 的 `codes` 實際來源、`settings_store` 入口是否皆為 Sheet 持倉，**僅讀註解與呼叫形狀、未追完整鏈**。
4. `full_key` 是否實際被用於走 `_BANK_PLATFORM_CODES` 通路頁（F10）：**未追呼叫鏈**；A 鏈對帶後綴 `full_key` 的實際回傳行為**未驗**（F11 只讀字面）。
5. F7 只讀 `DEC-2026-10-29-03` 摘要（執行組整理），**未讀其逐字存檔**；`fund_code_mapping.csv` 部署端有無未驗。
6. 「方向來源」之客戶裁示為 ChatGPT 轉達〔待核〕；各 DEC 的客戶來源等級（逐字存檔／要點轉述／〔待核〕）本卡未逐筆重驗，只引用原文所標。
7. 方案風險等級為作者推論，未實作驗證；S1 的「規則可機測」是設計判斷，未實測。

## i　2026-11-20 獨立稽核後修正（稽核 1 組，與作者共享派工來源；修正未經複驗）

> 標記：[F]＝讀檔／`git`／文件可重現；[I]＝推論；[R]＝推薦（可被推翻）；NV＝NOT VERIFIED。本節不是客戶裁示、不是授權；S7 規則本身**未裁**。

**M1　方向來源已有 DEC（[F]）**：見 §首「方向來源」就地更正——`DEC-2026-11-19-10`（`docs/DECISIONS.md`）以要點轉述記錄「D2 Q-ID 採方案 1，先釐清 S7」，來源待核，S7 規則本身未裁。

**M2　「標示違反」與「阻擋取數」是兩件事**
- [F] S1 的 `ok=False`／`full_key=None` 會令持倉下游取不到 NAV：`services/v2_tables/nav_dividend.py` 需 `full_key`，A 鏈回傳 key 與 `fund_keys` 不同或缺失則該檔淨值不寫（F11）。
- [F] `R-ID-1`／`T-ID1`／`DEC-2026-10-29-01` 只要求**標記並保留原值**（不剝、不截、不改寫），**未要求擋取數**。
- [I] 「判失敗」＝實作 D2-A＝B 違反標示的一部分，且超出標示；`DEC-2026-11-13-06` 明列不授權修改 resolver、producer、Schema 或資料接線（見 §5）。**故 S1 若要成案，需另行授權，不得視為 R-ID-1 的自然延續。**
- 原稿「延續 R-ID-1」一律改讀為：**方向相同；效果超出**（已就地更正於 S1 列與 §3）。

**M3　「適用入口」獨立成選項軸（子題 2）**
- 軸 (a)　**只對 Sheet 持倉入口**（hld／alo／settings 取自持倉 `fund_code`）判未通過、原值保留；非 Sheet 入口維持現況。
- 軸 (b)　**所有入口**（含選股池 EXP、🔍 路徑 B、shadow、探針）一律只收基本碼——**等於預先替 EXP 另案作答**。
- [F] `DEC-2026-11-13-06` (4)：「選股池（EXP）代碼命名空間：另案待裁……**不以 MoneyDJ Sheet 命名空間規則外推**」。故軸 (b) 與該條直接衝突，除非客戶先就 EXP 另案作答。
- [F] `resolve_full_keys` 無 `input_source` 參數（F13），套在 resolver＝套到所有呼叫端；軸 (a) 需新增入口維度＝介面變更（日後施工、需另授權）。

**Should-Fix**
4. **S4 與上一卡方案 2 不等價（[F]）**：上一卡方案 2＝現行接受後綴＋**明寫已知缺口**＋S7 未裁；S4＝維持現況**不標**。另列 **S5「明標已知缺口、S7 未裁」**（＝上一卡方案 2 的實質內容，含 R-ID-2／3 契約文字註明後綴行為未裁、跨部署非確定性為已知缺口）。註：S4 已被客戶方向（先釐清 S7、不採方案 2）排除，僅供對照。
5. **「若有帶後綴持倉」的證據（[F]／NV）**：`DEC-2026-10-29-01` (3) 客戶已提實例 `TLZF9-AL001`、`ACDD01-EQTAL005`（`TLZF9-24A7` 亦見同 DEC），故**很可能存在**帶後綴的持倉輸入；實際比例**無法查證**（BL-0545 BLOCKED，NV）。原稿「若有」改為「很可能有，比例未知」。
6. **測試漂移鎖（[F]）**：`tests/test_v2_tables_fund_keys.py::test_pure_code_pattern_matches_l1_source` 以 `inspect.getsource(parse_moneydj_input)` 與 `FK.PURE_CODE_PATTERN` 對拍（並檢 `_raw[:30]`），另有 `_PARITY_CASES` 與 `_is_pure_code` 對拍。**改 pattern 會牽動 L1 `repositories/fund/sources.py::parse_moneydj_input` 與舊頁**（漂移鎖要求兩邊同步），S1 施工時範圍不只 `fund_keys.py`。
7. **「唯一一題」改兩子題**：已就地更正於 §0；子題 1＝規則；子題 2＝範圍（入口軸，M3）。
- **Nit**：F4 的「大小寫／空白沿用 `fund_keys`」（輸入先 `strip()`／`upper()`）與 `T-ID1` 第 2 點「不轉大小寫」有字面落差，已在 S1 規則欄再提醒（[F]：落差存在；哪邊為準未裁）。
- **優缺點逐項標記**（S1～S4 表內各格）：優點之「規則最簡、可機測」[I]（可機測是設計判斷，未實測）；「符合 F7」「與 `-10-29-01` 第 4 項同向」[F]；缺點之「原本靠放行的輸入改判失敗」[F]（機制）、其影響量[NV]；「關掉 `-10-29-01` 第 4 項第 3 點的 `full_key` 層路徑」[F]；風險欄全為 [I]。

**最小 Gate 草稿（只寫入本卡，不向使用者提出；[R]可被推翻；2026-11-20 第三次複驗後重寫）**
~~第二版草稿：選項 A0／A／B／C／D／E 並列，並稱「其餘選項皆帶阻擋效果」。~~ **有意識的更正，不是漏刪**；兩邊理由：第二版補上 A0 是對的；但「其餘皆阻擋」不實——D（S5 維持放行）與 E（不採）**不**阻擋、C 只對**未驗證者**阻擋；且選項混了效果／入口範圍／規則三軸。被推翻的是該句與混軸結構。更早的第一版（A～E，推薦 A）理由同樣失真（漏了只標示不阻擋的選項），已併入此更正。
- **問題**：取數用基金代碼能不能帶通路／商品後綴？——**一題兩小問**：
  - **(1) 效果**（三選一）：**A0** Sheet 入口只標示違反、保留原值、不阻擋取數；**A** Sheet 入口判未通過（`ok=False`、原值保留，阻擋取數）；**D（＝S5）** 維持放行並明標已知缺口、S7 未裁。
  - **(2) 入口範圍**：**僅當 (1) 選 A（或日後選 B）才追問**——只 Sheet 持倉入口，或所有入口。
  - **B（所有入口只收基本碼）、C（已驗證通路表命中者可帶後綴）與「規則」本身不與 (1)(2) 同送**：B 與 `DEC-2026-11-13-06` (4)（EXP 代碼命名空間另案、不外推）直接衝突，須先裁 EXP；C 牽動 DG2（名單來源、是否升格）。E（不採）＝不作任何事，不構成選項。
- **已知答案**（不重問）：(1) R-ID-1／`T-ID1`（`DEC-2026-11-13-06`，要點轉述）：Sheet「基金代號」欄只收 MoneyDJ 基本代碼，違反＝標記並保留原值，不剝不截不改寫，僅適用該欄、不得外推；(2) `DEC-2026-10-29-01` (4)：Sheet 帶不符契約輸入＝標記資料驗證問題；未知後綴不得盲目剝除；MoneyDJ 平台 URL 可依已驗證 mapping 辨識通路後綴；(3) `DEC-2026-11-19-10` 方向：D2 Q-ID 採方案 1、先釐清 S7（要點轉述，來源待核；其區分欄 3 記「S7 卡推薦 S1」為歷史）；(4) **S7 規則本身未裁**。
- **推薦**：(1) A0（[R]，可被推翻）。**與 A 的差異＝是否阻擋取數**：A0 下 `ok`／`full_key` 照舊產出，NAV 照寫；A 令帶後綴持倉取不到 NAV（F11），且判失敗＝D2-A＝B 實作，另需授權。理由：A0 與 R-ID-1 字面一致（標示、保留原值）、不傷現行帶後綴持倉、不替 EXP 作答。
- **A0 實作面成本（不可略）**：
  - `_resolve_one` 回傳字典欄位固定（`input`／`ok`／`full_key`／`portal`／`parsed_code`／`mapping_hit`／`error`）；「另附違反標記」需新增欄位＝**resolver 介面或 Schema 變更**，需另授權。
  - 只限 Sheet 入口需新增 `input_source` 類參數（F13：`resolve_full_keys` 現無此參數）；
  - 新增鍵對「整 dict 相等」斷言的測試與下游的影響：**NV**（未逐一查）。
  - **A0 不回答 S7 本題（後綴可否進取數鍵）**；R-ID-2／3 的後綴條款仍待另開 Gate。
- **風險**：(1) 屬 identity 規則的實作面變更，Stop Gate；實作＝D2-A＝B 違反標示，另需授權；(2) A 令現行靠放行的帶後綴持倉取不到資料（很可能存在，比例未知，BL-0545 BLOCKED）；(3) 入口維度需改介面（F13）；(4) **漂移鎖須同步改 L1**：`test_pure_code_pattern_matches_l1_source` 對拍 `repositories/fund/sources.py::parse_moneydj_input`，改 pattern 牽動舊頁；(5) **F4 大小寫落差**：`fund_keys` 先 `upper()`，`T-ID1` 第 2 點「不轉大小寫」，「原值保留」以哪個為準未裁；(6) A／B 會關掉 `DEC-2026-10-29-01` (4) 第 3 點在 `full_key` 層的已驗證通路辨識；(7) 新增欄位與 `input_source` 屬介面／Schema 變更，需獨立授權。

**本節未驗事項彙總**：NV——真實 Sheet 帶後綴比例、`full_key` 是否實際用於走 `_BANK_PLATFORM_CODES`（F10）、A 鏈對帶後綴 key 的實際回傳、F13 呼叫端是否窮舉、`DEC-2026-11-19-10` 之客戶來源逐字。本節由稽核後修正組單組寫成，未經複驗。
