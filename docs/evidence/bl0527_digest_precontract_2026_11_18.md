# BL-0527 Decision Digest 前置契約補強（五種缺語意、既有承載、六段／四區對應、已決／待裁示分離）

> **單組作者，尚待非作者獨立稽核。** 屬 AI decision semantics 等級（`DEC-2026-10-16-05`），合併前須至少 1 組真正獨立稽核。
> **性質：docs-only 補充，不是客戶裁示、不是 Digest Schema、不是 prompt、不是施工授權。** 登記不構成動工授權（`CLAUDE.md` §-1）。
> **與既有決策包的關係**：本檔**補**同目錄 `onebrain_digest_decision_pack_2026_11_18.md`（下稱「既有包」），**不重複**其內容；既有包已涵蓋的項只引用其節號。基準 `origin/main` `09ed82ba`（2026-11-18）。
> 路徑一律寫「檔案::符號」，不寫行號。分段：**FACT**＝可由指令或文件重現；**INFERENCE**＝推得；**RECOMMENDATION**＝AI 推薦，可被客戶推翻。
> **DEC 轉述規則**：標「經對話提示語轉達〔待核〕」者，本組未讀該 DEC 原文，僅引用既有文件（67／79／80／既有包／規則表註解）對它的轉述；標「已讀」者，本組實際讀到所引文字所在的文件，但轉述仍是要點、非逐字。

---

## 0. 對照題目五項：既有包已有什麼、本檔補什麼

| 題目項 | 既有包 | 缺口判斷（FACT） | 本檔處置 |
|---|---|---|---|
| 1 逐域 R／O／E 候選與證據 | 第 2.1 節九域表＋第 3 節 D1～D10 | **已涵蓋**，且證據欄完整 | 不重複；僅在第 5 節決策包引用 |
| 2 Missing／unavailable／not evaluated／stale／conflict 五種語意差異 | 只散見（2.3 談 stale；5.4 一句 Missing 保持 Missing） | **沒有把五種放在同一張表比較**；`unavailable`、`not evaluated`、`conflict` 在規則表**沒有對應鍵** | 第 1 節 |
| 3 as_of／Provider／Rule ID／Evidence trace 的既有承載（檔案符號） | 2.2、2.4、2.5、2.6 談語意與缺口，但**承載符號列得少** | 缺「檔案::符號」逐項清單 | 第 2 節 |
| 4 OneBrain 六段輸出與四區版面對應待決 | **完全沒有**（既有包只提 67 8.9 一次） | 發現**三套**「六」與一套「四區」並存，且 80 第 16.4 節明寫對映待客戶確認（BL-0540） | 第 3 節 |
| 5 最小正式契約決策包（已決／待裁示分開） | 第 4 節 Q1～Q7 是序列，第 5 節是 OB-B 方案表 | 沒有把「已決」整理成一張附出處的清單，也沒有「五種語意」與「六段／四區」兩題的方案表 | 第 4 節 |

---

## 1. 五種「缺」的語意差異

**FACT 前提**：客戶原話層級已定的是**禁止互相等同**：`missing ≠ 0`、`unavailable ≠ neutral`、`not evaluated ≠ safe`、`unknown ≠ HOLD`（`docs/v2/67` 第 5.4 節第 1 點、第 6 節第 5 點；`docs/v2/79` 第 11 節附近，`PROJECT_RULES.md` 第 13 節；本組讀到 67 與 79 引文）。`docs/v2/67` 第 8.5 節 schema 把 `missing／unavailable／error` 列為「三種不同的缺」，但**未逐一定義**。

下表「規則表鍵」讀自 `shared/ui_semantics/rules.py::ENTRIES`，「程式內承載」為字面 `git grep` 結果。

| 語意 | 本檔建議的區分問法（INFERENCE，非契約） | 規則表鍵與已核准字樣（FACT） | 程式內承載（FACT；字面搜尋，未窮舉） | 缺口 |
|---|---|---|---|---|
| **Missing（資料未備）** | 該項該有、但**沒有取到值**，且沒有「取數失敗」證據（來源缺、沒有觀測） | `missing` → `◇ 資料未備`（灰；`MISSING_TEXT`）；`ok` 刻意不寫字 | `ui_v3/viewmodels/common.py::STATUS_MISSING`；`ui_v3/viewmodels/components.py::MissingItem`（`what`＋`reason_code`） | 與 `undetermined` 的分界只在 79 第 11 節（`◇` 是「缺」，`⬜` 是「無法判定」）；Digest 要記哪一個、記什麼原因碼**未定** |
| **Unavailable（不可得）** | 資料**應可取得但這次取不到**（取數失敗、設定沒設、來源整體不可用） | **沒有叫 `unavailable` 的鍵。** 最接近：`fetch_failed` → `⛔ 取數失敗`（紅）；`not_configured` → `⛔ 尚未設定`（紅，成因是設定沒設、沒有執行取數）；`APPROVED_WORDING["reason_no_source"]`＝「來源資料無法使用」 | `common.py::STATUS_FAILED`；`rules.py::STATUS_TO_KEY["failed"]`、`REASON_NOT_CONFIGURED`；另有 AI 面向的「AI 分析暫不可用」（75 第 12 節、80 第 7.4 節），**那是 AI runtime 不可用，不是資料不可得，是另一個物件** | 「Missing」與「Unavailable」在 Digest 是否分兩態、還是 Unavailable＝`failed`＋原因碼，**未定**；`unavailable` 一詞沒有核准畫面字樣 |
| **Not evaluated（未評估）** | **前置條件不足，根本沒有去算**（不是算出「沒事」） | **沒有鍵、沒有核准字樣。** 原則存在（`not evaluated ≠ safe`），畫面上落在 `undetermined`（`⬜ 無法判定`，79 稱「含不適用、未設定」）或 `threshold_pending`（`⬜ 門檻待裁示`） | 內部碼已存在、**僅供內部、無畫面字**：`services/v2_domain/allocation_evidence.py` 的 `NOT_EVALUATED`、`NAV_STATE_NOT_EVALUATED`（檔內註解自陳 "no wording"、"never defines or owns"）；`scripts/bl0545_coverage_probe.py::NOT_EVALUATED_STATES`＝`("stale","conflict")`（探針把這兩項標為「未評估」，計數為 null 不是 0）；`ui_v3/viewmodels/action_slot.py`（`ACTION_SLOT_SOURCES_ENABLED = False`，恆無法判定） | `not evaluated` 與 `undetermined` 是否同一個 Digest 狀態未定；內部碼不得被升格為 Digest 契約（`allocation_evidence` 檔頭自稱 not approved vocabulary，見既有包 2.1） |
| **Stale（不是最新）** | 有值、有 `as_of`，但**依正式門檻判為舊** | `stale` → `◷ 不是最新`（黃；規則表註明「只有正式門檻判為舊才用」）；`threshold_pending` → `⬜ 門檻待裁示`（灰，tone 為推論）；`FRESHNESS_TO_KEY`：`fresh` 不加標記、`stale`→`◷`、`undetermined`→門檻待裁示 | `common.py::FRESH_FRESH／FRESH_STALE／FRESH_UNDETERMINED`、`STATUS_STALE`；`rules.py::entry_for_freshness` | **`stale_after` 無任何已裁值**（既有包 V7）；三條 stale 觸發來源沒有端到端核准鏈（`data_state_vocabulary_crosswalk_d3a_2026_11_08.md` 第 4 點，單組作者判定）；`market_page.py::_meta_status` 對 `ok／missing／failed` 以外一律降為 `undetermined`（crosswalk B4，單組作者判定，本組未複驗） |
| **Conflict（來源衝突）** | **兩個以上來源給出不一致的值**，且無法依既定優先序裁決 | **沒有鍵、沒有核准字樣。** `DEC-2026-11-08-04` Q4 依既有包轉述：不新增「過期／衝突」正式詞、不改門檻（**經對話提示語轉達〔待核〕**——本組未讀該 DEC 全文） | `services/v2_tables/exp_profile.py::STATUS_INCONSISTENT = "inconsistent"`（Cell 層，兩源不一致時 `value` 為 None，測試 `tests/test_v2_tables_exp_profile.py` 鎖）；`scripts/bl0545_coverage_probe.py::NOT_EVALUATED_STATES` 含 `conflict`（未評估） | 容差、「同 as-of 不一致」的判定規則未定（既有包 2.3 缺口 3）；`inconsistent` 只存在於 Cell 層，`ui_v3` 的 `STATUSES` 五值**沒有**它（`common.py::STATUSES`＝ok／missing／failed／stale／undetermined） |

**INFERENCE（為什麼這五種不能合併）**：五者對下游推理的含意不同——Missing／Unavailable 是「沒資料」，Stale 是「有資料但可能過時」，Not evaluated 是「沒算」，Conflict 是「有資料但互相打架」。若 Digest 把它們壓成同一個「缺」，OneBrain 就無法依 67 第 8.3 節的 Constraint Precedence 與第 5.4 節禁止項區分「該停手」與「該降級」。**這是推論，不是已核准語意。**

**FACT（目前已有的最小公約數）**：`ui_v3` 層共同欄位 `status` 五值＋`freshness_state` 三值已落地並由測試鎖（`ui_v3/viewmodels/common.py`，一致性由測試鎖，本組未重跑該測試）；它們是**呈現契約**，80 第 16.3 節明寫「UI ViewModel≠Decision Digest」，不得直接當 Digest 狀態集。

---

## 2. as_of、Provider、Rule ID、Evidence trace：既有承載與缺口

`docs/v2/67` 第 5.3 節已有一張概念→承載表（基準較舊）；本節補**檔案::符號**並以 `09ed82ba` 為準，只列本組讀到的。

| 概念 | 既有承載（檔案::符號；FACT） | 缺口（FACT／INFERENCE） |
|---|---|---|
| **as_of（觀測日）** | `services/v2_tables/market_indicator.py`：`obs_date`、`release_date`（註解：同一觀測日的每個修正版次各寫一列，`is_revised`；`rows_from_fred_vintages`）；`services/v2_tables/nav_dividend.py`：每列帶 `fetched_at`（取 `attrs["cache_updated_at"]`），`nav_date`；`ui_v3/viewmodels/common.py` 共同欄位 `as_of`（80 第 6 節）；`services/v2_tables/exp_profile.py` Cell `observed_at` | 欄名不統一（67 5.3）；PIT 取哪一欄未定；`services/v2_domain/allocation_evidence.py` 無根層 as_of／產生時間（既有包 2.2）；國發會兩鍵 `PENDING_NDC_NO_RELEASE_DATE`（`market_indicator.py`）＝來源不提供公布日 |
| **retrieved_at** | 各表 `fetched_at`；`market_indicator.py` 註解的 `fetched_at`；共同欄位 `retrieved_at`（80 第 6 節，來源 `fetched_at`） | 形狀不一（67 5.3） |
| **Provider（資料供應者）** | `services/v2_tables/market_indicator.py::INDICATOR_SPECS`（各鍵 `source` 二元組，見既有包 V6）；`nav_dividend.py` 回傳 `provenance[fund_code]`（含 `ccy_source`，**不寫進 `nav` 表欄**；44 的 `nav` 只有 `source_tier`）；`exp_profile` Cell 的 `sources`／`failed_sources` | 無逐項 Provider 契約；`DEC-2026-11-17-06` 依既有包 2.4 轉述明寫 NAV 域**不新增 Provider 欄**、不核准旁路 `provenance[fund_code].source` 與 `chain.data_source`（**經對話提示語轉達〔待核〕**） |
| **Provider（AI Provider，另一件事）** | `infra/llm.py::_DEFAULT_CHAIN`＝gemini→anthropic→openai（既有包 V5） | 無 typed interface／Fake Provider（既有包 V3）；本檔不處理 |
| **Rule ID／rule_version** | `ui_v3/viewmodels/components.py::EvidenceItem.rule_ref`（Optional，「只有正式規則存在才填；不得自造 Rule ID」，批 1 fixtures 一律不填）；`services/v2_domain/allocation_evidence.py` 的 `RuleRef(NOT_DEFINED)`（`rule_ref: RuleRef`，目前恆為 not defined） | `rule_version` 在 `.py` 只出現一處「斷言沒有」的測試（既有包 V1）；編碼格式、版本格式、門檻引用格式未定（79 UI-10 另走格式 Gate）；現存「規則結果」只有使用者門檻比較，住在呈現層 |
| **Evidence trace（資料血緣）** | 67 第 8.7 節固定鏈 `AI sentence → Digest fields → Rule Result → Rule ID → Canonical Data → source／as_of`（文件，無程式實作）；`ui_v3/viewmodels/components.py::ProvenanceTag`（`source`、`as_of`、`fallback_used`） | 句子→依據對映格式（規格 `AI-3`）未定；「AI 不讀畫面／不回寫」兩條守衛無專門測試（67 第 6 節第 6 點，BL-0527 自述） |
| **Evidence trace（分析 trace）** | 75 第 7 節欄位清單（文件）；無程式 | 與 Digest schema version／rule version 的銜接要等這兩者存在（既有包 2.6） |

**FACT（承載邊界）**：`ui_v3` 層明寫「view model 不得 import 下層」，`EvidenceItem` 只擋空字串、不驗 `rule_ref` 是否存在於正式登錄（`components.py` docstring）。**這表示目前沒有任何程式層保證 Rule ID 指向真實規則。**

---

## 3. OneBrain 六段輸出與四區版面：對應待決

### 3.1 FACT：同一主題有幾套「六」，以及一套「四區」

| 名稱 | 內容 | 出處 | 性質 |
|---|---|---|---|
| **六項固定輸出 v-a（`DEC-2026-10-27-18`）** | 市場／配置／持股／候選基金／主要風險／本期最多 3 項行動 | `docs/v2/67` 第 3.2 節（引為客戶原話） | 已決（客戶原話） |
| **六段輸出 v-b（`DEC-2026-10-29-07`，方案 C）** | 市場一句／我的資產與配置一句／持股一句／候選基金一句／主要風險 1～3 點／本期行動至多 3 項；每項可「查看依據」 | `docs/v2/67` 第 6.1 節第 3 點；第 6 節第 3 點 | 已決。67 讀法：第 2 項「配置」＝「我的資產」整頁 slice（執行組讀法，可推翻） |
| **六項未來輸出 v-c（`DEC-2026-11-03-08`，H 段要點轉述）** | 系統狀態／AI 投資總結／主要依據／最強反證／風險與不確定性／Evidence trace | `docs/v2/80` 第 16.4 節 | **80 明寫：「此六項與 67 6.1 六段（內容）／8.9 四區（版面）的對映待客戶確認（BL-0540），本節不擇一、不改 67。」** |
| **四區（UI-14 A，`DEC-2026-11-02-07`）** | System State（deterministic）／OneBrain Interpretation（AI）／Maximum Falsification／Evidence（可展開「查看依據」） | `docs/v2/67` 第 8.9 節、`docs/v2/79` 第 9.4 節 | 方向核准；精確版面於 Phase 7 出線框再定；Maximum Falsification 超出 6.1 固定輸出 |

**FACT**：BL-0540 三子項中（本組只讀其首段）列有「三項 New UI2 規則交界待確認」，狀態為「待客戶裁示」（`docs/BACKLOG.md`）；本組**未讀完 BL-0540 全文**，不確定「六項對映」是否即其中一子項。

### 3.2 INFERENCE：兩套「內容」與四區如何可能對應（AI 試排，非契約）

| 四區 | 可承載的 v-a／v-b 內容 | 可承載的 v-c 項 | 待決點 |
|---|---|---|---|
| **System State（deterministic）** | 「本期行動 ≤3」（唯一動作權威是 System Action State，67 8.2 C-1） | 系統狀態 | v-b 把「本期行動」列為 OneBrain 輸出，與 C-1「OneBrain 只能引用、不能產生 action」**字面有張力**：行動是放 System State 區（引用）還是 Interpretation 區（敘述）？ |
| **OneBrain Interpretation（AI）** | 市場／我的資產／持股／候選基金各一句；主要風險 1～3 點 | AI 投資總結；風險與不確定性 | 「主要風險」（v-b，1～3 點）與 v-c「風險與不確定性」是否同一項、是否都屬 Interpretation 區 |
| **Maximum Falsification** | v-a／v-b **都沒有**這一項（67 8.9：新增內容） | 最強反證 | 「最大反證」定義未裁（D5） |
| **Evidence** | 每項「查看依據」展開內容 | 主要依據；Evidence trace | v-c 的「主要依據」與「Evidence trace」是否同區、是否同一件事；展開粒度（每句／每區） |

**INFERENCE 觀察**：
1. v-b 的 6 個**內容槽**與四區的 4 個**版面區**不是同一個維度（內容 vs 版面），不是一對一對映問題；真正待決的是「每個內容槽落在哪個版面區、哪些版面區對應 Digest 的哪些欄位」。
2. 「Maximum Falsification」與「Missing／uncertainty 清單」在 67 第 8.7 節要求「每次正式輸出至少含」，但**沒有指定落在哪一區**；v-c「風險與不確定性」可能是它的承載，**未定**。
3. 四區方向已核准，故此題**不是**「要不要四區」，而是「v-a／v-b／v-c 三套內容怎麼收斂成一套、各落哪一區」。

**未查證**：本組未讀 79 第 9.4 節以外的上下文與 UI-14 的完整裁示文字（只讀到 67 轉錄與 79 該列），未讀 80 第 7.4 節以外的 🤖 線框全貌；v-c 為 H 段要點轉述（80 第 16.4 節自陳客戶逐字原文本組未見）。

---

## 4. 最小正式契約決策包

分兩塊：**4.1 已決**（附出處）；**4.2 需客戶裁示**（附方案表與推薦）。已決與待決**不混寫**。

### 4.1 已決（可作為後續工作的前提；出處標註讀取狀態）

| # | 已決事項 | 出處 | 讀取狀態 |
|---|---|---|---|
| A1 | 資料鏈固定：Canonical Data → Rules／Indicators／Risk Cap → Decision Digest → One AI Brain → AI 投資總結；Digest 不是 UI scrape；AI 不讀畫面、不回寫 canonical | `DEC-2026-10-29-06`；`docs/v2/67` 第 5.1～5.2、6 節 | 已讀 67 轉錄；DEC 原文經對話提示語轉達〔待核〕 |
| A2 | Missing 保持 Missing：不得 Missing→0／neutral；not evaluated→safe；unavailable→HOLD；Risk Cap、減碼 trigger 等未定義項在 Digest 只能以 Missing／未定義表示 | 客戶原話，`docs/v2/67` 第 5.4 節 | 已讀 |
| A3 | `confidence`／投資信心不納入 Digest（既有系統無正式語意） | `docs/v2/67` 第 5.3 節末列 | 已讀 |
| A4 | 決策欄位群：value／unit／source／provenance／as_of／release_date／retrieved_at／frequency／freshness_state／stale／missing-unavailable-error；來源不提供 `release_date` 就寫「來源未提供」、不虛構；global timestamp 只代表 render 時間 | `DEC-2026-11-02-07` UI-8 A；`docs/v2/67` 第 8.5 節 | 已讀 67 轉錄 |
| A5 | Freshness Policy 只定欄位（policy_id／frequency／expected_lag／stale_after／authority），**不填任何門檻值**；`stale_after` 另走 Threshold Gate | 同上 | 已讀 |
| A6 | Digest Full Context 與 OneBrain context 三分（Required／Optional／Excluded）通則；逐域清單須逐列審核、不得整欄升格 | `DEC-2026-11-02-07` UI-9 A；`DEC-2026-11-11-04` D2-G1 | 67 已讀；D2-G1 經既有包轉述〔待核〕 |
| A7 | D2 首批限基金身份、NAV、績效；D2 先於 Digest schema（D2-G2：Digest schema 為獨立 Gate） | `DEC-2026-11-11-04`（D2-G2／G3） | 經既有包轉述〔待核〕 |
| A8 | 首批 5 列契約**文字**已核（R-ID-1、R-NAV-1／2／4／5）；R-NAV-3 暫緩；「Required 升格」狀態仍待核（較嚴讀法，見既有包 2.1） | `DEC-2026-11-13-06`、`-14-07`、`-17-06` | 經既有包轉述〔待核〕 |
| A9 | Traceability 固定五段鏈；每次正式輸出至少含核心理由、使用的 Rule Result、最大反證、Missing／uncertainty 清單 | `DEC-2026-11-02-07` C-5；`docs/v2/67` 第 8.7 節 | 已讀 |
| A10 | 🤖 版面四區**方向**核准（System State／OneBrain Interpretation／Maximum Falsification／Evidence）；精確版面 Phase 7 出線框再定 | `DEC-2026-11-02-07` UI-14 A；`docs/v2/67` 第 8.9 節 | 已讀 |
| A11 | 六段內容輸出格式與入口（方案 C）；各頁 local summary 必須來自同一份 Digest slice | `DEC-2026-10-29-07`；`docs/v2/67` 第 6.1 節 | 已讀 |
| A12 | UI ViewModel≠Decision Digest；UI 精簡不得造成資料精簡 | `DEC-2026-11-03-08`（H 段要點轉述） | 已讀 80 第 16.3～16.4 節；DEC 原文經對話提示語轉達〔待核〕 |
| A13 | 畫面字樣已核准一套（`shared/ui_semantics/rules.py::ENTRIES`／`APPROVED_WORDING`）；畫面層遇 `PENDING_WORDING` 必須停下，不自造字 | `DEC-2026-11-02-01`、`BL-0532` 等（見規則表 `source` 欄） | 已讀規則表；各 DEC 原文經對話提示語轉達〔待核〕 |
| A14 | D1 採方案 C（資料契約先行）；正式 Digest 施工、Phase 7、Provider、Claude API runtime 未授權；FX 閘門維持關閉 | `DEC-2026-11-08-02` | 經既有包轉述（要點，非逐字）〔待核〕 |
| A15 | `DEC-2026-11-18-03`／`-04` 已登記（待 #1276）；`-03` 要求 OB-B 程式 PR 前客戶先確認 fake provider Gate | 既有包檔頭現況補註 | 本組**未讀**全文，NOT VERIFIED |

### 4.2 需客戶裁示（每題附方案表；推薦為執行組讀法，可被客戶推翻）

編號用 N1～N5，避免與既有包 Q1～Q7 混淆。N1～N3 是本檔新增；N4／N5 引用既有包。

#### N1：Digest 對「缺」要用幾種狀態、各叫什麼（第 1 節五種語意）

| 方案 | 內容 | 優點 | 缺點 | 風險 |
|---|---|---|---|---|
| **A（推薦）：Digest 內部五態分開，畫面字樣沿用既有、不新增** | Digest 狀態集＝`missing`／`unavailable`／`not_evaluated`／`stale`／`conflict`（命名僅為概念，格式另案）；畫面層仍只用規則表既有鍵（`◇`／`⛔`／`⬜`／`◷`）；`unavailable` 對映 `failed`／`not_configured`，`not_evaluated` 與 `conflict` 暫對映 `undetermined`，並在 Digest 保留差異 | 保留推理所需區分（第 1 節 INFERENCE）；不新增畫面字樣，不觸 `APPROVED_WORDING` Gate 與 `DEC-2026-11-08-04` Q4 | Digest 與畫面不是一對一，需要寫對照表 | 低：只定 Digest 概念不寫字；風險在對照表易被誤讀成新字樣，需明寫「不改畫面」 |
| **B：Digest 沿用 `ui_v3` 五值（ok／missing／failed／stale／undetermined）** | 不新增狀態，`not_evaluated` 與 `conflict` 併入 `undetermined` | 最小；零新增概念 | 失去區分；OneBrain 無法分辨「沒算」與「打架」；與第 8.5 節 `missing／unavailable／error` 三分已核欄位群有落差 | 中：資訊遺失不可逆，後補需改 Digest schema |
| **C：五態分開且新增畫面字樣** | 為 `not evaluated`／`conflict` 另請核准新正式詞 | 畫面與 Digest 一致 | 需受 `APPROVED_WORDING` Gate；與 Q4「不新增過期／衝突正式詞」方向相左 | 高：擴大範圍、與既有裁示衝突，且 Digest 還不存在，過早 |

**推薦 A。** 理由：區分是推理需要，字樣是呈現需要，兩者可分開裁；先裁概念、不裁字樣，不碰既有字樣 Gate。**這是 Digest 概念層的語意，屬 AI decision semantics，須客戶裁示；本檔不核准任何狀態名稱。**

#### N2：三套「六」與四區怎麼收斂（第 3 節）

| 方案 | 內容 | 優點 | 缺點 | 風險 |
|---|---|---|---|---|
| **A（推薦）：兩層模型——內容槽沿用 v-b，版面區沿用四區，v-c 併入對應區** | v-b 六內容槽為「輸出什麼」；四區為「放在哪」；v-c 六項歸入四區（系統狀態→System State；AI 投資總結／風險與不確定性→Interpretation；最強反證→Max Falsification；主要依據／Evidence trace→Evidence）；「本期行動」明定引用 System Action State（放 System State 區，Interpretation 區不另產 action） | 不推翻任何已決（v-b、四區、C-1）；一次消除 BL-0540 對映題；符合 C-1 | 需客戶確認 v-c 各項併入方式與「本期行動」位置 | 中：改變「本期行動」是 OneBrain 輸出 的字面讀法，須客戶確認不違原意 |
| **B：以 v-c 為準，取代 v-b** | v-c 成為唯一輸出清單 | 單一清單、與四區較貼 | 取代已決的 `DEC-2026-10-29-07` 固定輸出；v-c 只是要點轉述，非逐字 | 高：以未逐字確認的轉述覆蓋已決裁示 |
| **C：暫不收斂，等 Phase 7 出線框一併裁** | 維持現況 | 無需現在裁示 | 三套並存繼續，Digest schema 的欄位無法定（Digest 要不要含「反證」「不確定性」欄取決於此） | 中：拖延會讓 Q6（Digest schema Gate）更難提出 |

**推薦 A。** 理由：A 不覆蓋任何已決事項，並把「內容 vs 版面」兩個維度拆開，是最小的消歧。**但「本期行動放哪區」牽涉 C-1 與 `DEC-2026-10-29-07` 字面張力，必須客戶裁示。**

#### N3：Digest 內「Evidence trace」最小欄位集（第 2 節）

| 方案 | 內容 | 優點 | 缺點 | 風險 |
|---|---|---|---|---|
| **A（推薦）：先只裁「必含欄位清單」，不裁格式** | 每個 Digest 決策欄位必含 `as_of`、`release_date`（或「來源未提供」）、`retrieved_at`、`source`（資料來源名）、`rule_ref`（有才填，否則明寫 `not_defined`）；格式（Rule ID 編碼、版本、對映）另走格式 Gate | 與 A4／A9 已決一致；不碰格式 Gate；可讓 Q3 專注於格式 | 欄位清單本身仍是契約，須客戶核准 | 低：欄位名已在 67 第 8.5 節 |
| **B：連格式一併裁（併入既有包 Q3）** | 同時定 Rule ID 編碼與引用格式 | 一次到位 | 範圍大；依賴投資規則內容，而正式規則尚不存在 | 中：格式會被空的 Registry 綁死 |
| **C：不裁，等 Digest schema Gate** | 維持現況 | 無風險 | OB-02 前置無進展 | 低，但無進展 |

**推薦 A。** 理由：可獨立推進、與已決欄位群一致。**Provider 欄是否升格為契約欄仍受 `DEC-2026-11-17-06`（NAV 域不新增 Provider 欄）限制（轉述〔待核〕），不併入本題。**

#### N4／N5：引用既有包，不重複

- **N4＝既有包 Q1＋Q2**（OB-B 離線 interface＋Fake Provider 授權範圍，方案 B 推薦；及 BL-0527／0528 是否擋 OB-B）。見既有包第 4.2、5 節。
- **N5＝既有包 Q3＋Q4**（Rule ID／`rule_version` 格式；stale／conflict／NAV 10 日門檻按來源逐一定）。**N1 的 `stale`／`conflict` 概念層與既有包 Q4 的「門檻值」不同層**：N1 只問「Digest 要不要有這兩態」，Q4 才問「怎樣算 stale／conflict」。

### 4.3 建議的客戶問法順序（RECOMMENDATION）

1. N4（OB-B 授權範圍，解除 Gate 歧義）——獨立、可先問。
2. N1＋N3（概念層，無投資語意、無門檻值）——可併成一題、不依賴 Q4。
3. N2（版面／內容收斂）——建議在 N1 之後，因為 Interpretation／System State 區要引用 N1 的狀態集。
4. N5（格式與門檻）——依賴最重，放最後。
**不問**：Risk Cap、減碼 trigger、反證定義、持倉域 R／O／E（沿用既有包「延後」判斷）。

---

## 5. 範圍外（明確未做）

本檔**未**新增 Digest Schema／欄位名稱契約、正式投資 prompt、Provider runtime、Risk Cap、Action State 或任何 API 呼叫；**未**改任何程式、`DECISIONS.md`、`BACKLOG.md`、`HANDOFF.md`。第 1 節五態名稱、第 4.2 節方案內的狀態名與欄位名皆為**概念示意**，不是命名提案、不是契約。

---

## 6. 我沒有查證的部分

1. **單組作者**，未經第二組獨立驗證（`CLAUDE.md` §-2 規則 6）；全稱句（「沒有鍵」「無承載」）只代表字面搜尋，改名、動態組字串、別名不在內。
2. 第 1 節規則表鍵讀自 `shared/ui_semantics/rules.py` 的 `ENTRIES`／`STATUS_TO_KEY`／`FRESHNESS_TO_KEY`／註解；`APPROVED_WORDING["reason_no_source"]` 等為字面讀取。**各鍵的 DEC 出處本組只讀到規則表 `source` 欄與 67／79／80 的轉述，未讀 DEC 原文。**
3. crosswalk 的判定（B4、第 4 點等）取自 `data_state_vocabulary_crosswalk_d3a_2026_11_08.md` 的單組作者判定，本組未複驗。
4. 第 3 節的三套「六」：v-a 與 v-b 取自 67 的轉錄；v-c 取自 80 第 16.4 節（H 段要點轉述，客戶逐字原文本組未見）。本組未讀 79 第 9.4 節全文與 UI-14 裁示全文，未通讀 BL-0540 全文。
5. 第 3.2 節的對應表是**AI 試排**；尤其「本期行動放 System State 區」是依 C-1 推得，與 `DEC-2026-10-29-07` 字面「OneBrain 輸出本期行動 ≤3」存在張力，**不是已核准讀法**。
6. 第 2 節 `services/v2_tables/nav_dividend.py`、`exp_profile.py`、`market_indicator.py` 只讀命中片段（docstring 與符號），未通讀；未驗證實際回傳形狀與測試是否仍綠。
7. 本機缺依賴，**未執行任何業務測試**；唯一跑的是文件守衛（見提交紀錄），依賴齊全環境下是否綠只能由 CI 驗。
8. `DEC-2026-11-18-03`／`-04` 全文未讀；是否對第 4.2 節 N4 已有部分裁示 NOT VERIFIED。
9. 方案推薦的「風險低／中／高」為作者推論，未做實作驗證。
10. 是否觸發 Model／Effort Change Gate（`PROJECT_RULES.md` 第 5.1 節）：本檔為 docs-only，未評估。
