# S7 帶後綴基金代碼：Sheet 持倉與找基金兩入口的離線追蹤（docs-only 證據）

單組產出（C 線，Claude），未經獨立複驗；**不是**裁示、不是契約核准、不是施工授權；登記不構成動工授權（`CLAUDE.md` §-1）。
承接 `docs/evidence/d2_s7_suffix_identity_gate_2026_11_19.md` §i（S7 決策卡）；不改 resolver、別名表、Schema、任何 production 檔。
基準 main `eb886922941cb3950bd197a3bfe0f7c1eb62ff7f`。標記：**[實測]**＝本資料夾 `trace.py` 離線執行的輸出（`output.json`）；**[靜讀]**＝讀原始碼；**[推演]**＝包裝或假設後的模擬，**不是實作、不是現況**；**NV**＝NOT VERIFIED。

## 重現
`python docs/evidence/d2_s7_two_entry_trace_2026_11_21/trace.py > output.json`（需 pandas，不需 streamlit；純離線、不寫檔；從不同工作目錄跑，輸出逐位元相同）。
輸入用同一組**合成**代碼：基本碼 `ZZ9999`（對照組）、帶後綴 `ZZ9999-SFX01`；別名表注入空表，排除 csv／內建表影響。三個 L1 來源與 A 鏈皆以離線替身取代，**沒有任何真實取數**。

## 兩入口對照（現行行為）
| 步驟 | 入口 1b：Sheet 持倉 → hld／alo／refetch_nav 取數鏈 | 入口 1a：Sheet 持倉 → 💼 `assets_source`（Preview） | 入口 2：🔍 找基金（`fund_lookup`） |
|---|---|---|---|
| 原始輸入保留 | `fund_code` 原值進 `resolve_full_keys` | `fund_code` 原值進 `holding_row`，通過 `contract.holding_row_problems`（`problems=[]`） | `screen_input` 放行（純代碼格式允許一個 `-`＋2–20 碼後綴），`loader` 以原字串呼叫 |
| resolver（`fund_keys`） | `ok=True`、`full_key`＝`ZZ9999-SFX01`、`mapping_hit=False`，**無任何違反標記** [實測] | **不經 resolver**（`assets_source` 不 import `fund_keys`）[靜讀＋實測：基本碼與後綴碼結果同形] | 同左：`ok=True`、`full_key` 原樣 [實測] |
| 下一步 | A 鏈以 `chain_code＝ZZ9999-SFX01`、`full_key＝ZZ9999-SFX01` 呼叫 [實測，替身] | 成本基準：`nav_state=not_required` [實測]；市價基準由設計 `blocked`、不呼叫生產者 [靜讀：`assets_source.py` 檔頭，本腳本未跑市價基準] | 三來源 L1 皆以 `ZZ9999-SFX01` 呼叫 [實測，替身] |
| NAV／Evidence | 淨值列兩檔各寫出（替身序列）；`nav_errors={}` [實測，替身] | `status=evaluated`，Evidence 的 `fund_code` 為原值 [實測] | 無 NAV；替身回「查無」→ `page_unmatched／no_page`（與基本碼相同）[實測] |
| **實際最早中止點** | **程式碼內沒有**：帶後綴碼一路通到取數層。唯一可能的中止在真實取數端（NV）；以及 F11 核對——若真實 A 鏈回傳的 `full_key` 與 resolver 的不同則該檔淨值不寫（見下列推演） | **沒有**（後綴碼未被察覺，也不影響成本基準的任何輸出） | **程式碼內沒有**；中止只在來源端（NV） |

結論（[實測]）：**三條路徑都不標示後綴碼**；resolver 層沒有任何一處對後綴「說話」。DG-2 shadow 的 `_sheet_contract_violation` 雖有判準，但 `DG2_SHADOW_ENABLED=False`，不在 production。

### 靜讀補充（A 鏈會不會把後綴去掉？）
`repositories/fund/fund_orchestration.py`（約 `:1365-1395`）：A 鏈的 `full_key` ＝ `parse_moneydj_input(輸入)` 的 code，經別名表命中才改為 `public_code`，無命中即輸入整段（含後綴）→ 與 resolver 的 `full_key` 相等、通過 F11 核對。**真實 A 鏈對未知後綴碼實際回什麼＝NV（需真取數）**。
[推演] 若真實 A 鏈會去後綴：該檔淨值不寫，`nav_errors` 出現「A 鏈回傳的 full_key 'ZZ9999' 與代碼對照（fund_keys）的 full_key 'ZZ9999-SFX01' 不同」（`output.json` 的 `1b_hld_chain_INFER`）。

## 「標示但保留取數」（A0）與「標示並阻擋」（A）：實測與推演分列
| | 現行（[實測]） | A0 標示但保留取數（[推演]：包裝 resolver 只附標記） | A 標示並阻擋（[推演]：包裝 resolver 令後綴碼 `ok=False`） |
|---|---|---|---|
| 入口 1b 取數鏈 | 兩檔皆取數、皆寫 NAV 列 | 與現行逐項相同（標記沒有任何下游讀它） | 帶後綴檔進 `key_failed`、**不呼叫 A 鏈、無 NAV 列**；基本碼檔不受影響 |
| Evidence（市價基準，NAV 列缺）| — | 同現行 | 該檔 `nav_state=failed`、`nav_cause.key_failed=true`；若無此標記則為 `no_data`、`key_failed=false`（[實測]，直接呼叫既有生產者；兩者 `value_twd=None`、`reason=nav_absent`）|
| 入口 1a 💼 | 不經 resolver | **不受影響**：resolver 層的標記到不了 💼 | **不受影響**：同上（💼 不呼叫 resolver）|
| 入口 2 🔍 | 三來源取數 | 與現行相同 | `BLOCKED／key_rejected`，**0 次來源呼叫**；🔍 並非 Sheet 入口，但 `resolve_full_keys` 沒有 `input_source` 參數，resolver 層規則會一併擋下 🔍（與 `DEC-2026-11-13-06` (4)：EXP 命名空間另案、不外推，須先處理）|

三個必須講明的發現：
1. **💼 Sheet 入口根本不經 resolver**。任何「改 resolver」的規則（A 或 A0）都**碰不到 💼**；要在 💼 標示後綴，需要另一個掛點（例如持倉列建構或 `assets_source` 側）——那是新的介面／契約變更，需另授權。
2. **A0 的標記目前沒有任何消費者**：`_resolve_one` 回傳字典欄位固定，新增標記＝resolver 介面變更，且下游（hld live、`allocation_evidence`、🔍）都不讀它；單加標記，使用者畫面上不會有任何差別，除非另做呈現（UI Gate）。
3. **A 在 Evidence 上是「看得見的失敗」**（`failed`＋`key_failed`），代價是帶後綴持倉**取不到 NAV**；是否真有此類持倉＝NV（BL-0545 BLOCKED，無法查證）。

## 一題可裁示的 Sheet 規則（只問 Sheet「基金代號」欄；不問 EXP、🔍、別名表、DG2）
**問題**：Sheet「基金代號」欄出現帶通路後綴的代碼（例 `TLZF9-AL001`）時，系統應——
| 方案 | 內容 | 優點 | 缺點 | 風險 |
|---|---|---|---|---|
| **A0（推薦）標示、保留取數** | 該列標記「後綴違反」、原值保留；仍照現行取數與寫 NAV | 與 R-ID-1 字面一致（標示、保留、不剝不截不改寫）；不傷可能存在的帶後綴持倉；不替 EXP／🔍 作答 | 需新增標記欄位（resolver 介面／Schema 變更，另授權）；💼 不經 resolver，須另有掛點才看得到；現況沒人讀標記 | 若僅加標記而不呈現，等於沒有改善；F4 大小寫落差（`T-ID1` 第 2 點 vs resolver 先 `upper()`）仍待釐清 |
| A 標示並阻擋 | 判未通過（`ok=False`），不取數 | 規則簡單；失敗在 Evidence 上看得見 | 超出 R-ID-1 只標示的範圍；帶後綴持倉取不到 NAV；resolver 層會連帶擋 🔍／EXP；實作＝D2-A＝B，另授權 | 影響面無法查證（BL-0545）；漂移鎖須同步改 L1 `parse_moneydj_input` |
**AI 推薦：A0**。**已知答案不重問**：R-ID-1／`T-ID1`（Sheet 欄只收基本碼、違反＝標記並保留原值）；`DEC-2026-10-29-01` (4)；S7 規則本身**未裁**；本證據**不替**客戶作答。
**不授權**：改 resolver／`fund_keys`／別名表／Schema／`NAV_FIELDS`、升格 DG2、真實取數、任何 UI／Digest／OneBrain 接線；C-13（`assets_source` 證據轉接）與 NAV stale／FX missing 穿透**維持原 Gate**，本證據只在上表引用其現況，不修。

## 未查證與限制
- 全部為合成碼與離線替身；**真實 MoneyDJ／TDCC／FundClear 對帶後綴碼的行為、真實 A 鏈回傳的 `full_key`、`_BANK_PLATFORM_CODES` 通路頁是否被這條鏈使用＝NV**。
- 單組、未經獨立複驗；「三條路徑都不標示」是對本腳本涵蓋之路徑的觀察，**不是** repo 全稱句（`resolve_full_keys` 其他呼叫端如 `ui_v2/exp`、`settings_store.refetch_nav` 本批只靜讀其形狀）。
- A0／A 的欄為包裝 resolver 的**推演**，沒有任何 production 檔被改。
