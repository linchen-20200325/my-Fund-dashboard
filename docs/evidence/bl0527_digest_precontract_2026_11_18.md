# BL-0527 Decision Digest 前置契約補強（五種缺語意、既有承載、六段／四區對應、已決／待裁示分離）

> **單組作者，尚待非作者獨立稽核。** 屬 AI decision semantics 等級（`DEC-2026-10-16-05`），合併前須至少 1 組真正獨立稽核。
> **稽核紀錄指標（後補）**：第 3 行「尚待」已過時；本檔已歷經非作者稽核回修（`f9910396`）與增量複審（`91326841`），摘要見 `docs/evidence/audit_record_2026_11_18.md`（原始報告 repo 內無存檔，仍非 GitHub review）。
> **性質：docs-only 補充，不是客戶裁示、不是 Digest Schema、不是 prompt、不是施工授權。** 登記不構成動工授權（`CLAUDE.md` §-1）。
> **與既有決策包的關係**：本檔**補**同目錄 `onebrain_digest_decision_pack_2026_11_18.md`（下稱「既有包」），**不重複**其內容；既有包已涵蓋的項只引用其節號。基準 `origin/main` `09ed82ba`（2026-11-18）。
> **與 Gate 的關係（S1）**：`DEC-2026-11-11-04`（已讀原文）D2-G2＝A 明定「D2 逐域契約與 Digest schema 是兩個獨立 Gate；D2 逐域正式契約完成後才另行提 Digest schema Gate；不得因 D2 方向核准就啟動 Digest schema 研究／施工／OneBrain」，且其不授權清單含 Digest schema 研究／施工與任何正式資料契約欄位升格。BL-0527 是**缺口登記**。故本檔**只是缺口盤點與請示題整理，不是 Digest schema 預備授權**；第 1～3 節的對照與第 4.2 節的方案，皆不得被讀成「已開始 Digest schema 研究」。第 4.2 節各題是否現在就可向客戶提出，本身也受 D2-G2 順序約束（見 4.3）。
> 路徑一律寫「檔案::符號」，不寫行號。分段：**FACT**＝可由指令或文件重現；**INFERENCE**＝推得；**RECOMMENDATION**＝AI 推薦，可被客戶推翻。
> **DEC 轉述規則（第二版，修稽核 M1）**：第 4.1 節的每個 DEC 本版已直接讀 `docs/DECISIONS.md` 原文，並照錄該 DEC 自身的 provenance 等級（逐字／要點轉述／自稱客戶〔待核〕）。「經對話提示語轉達〔待核〕」一律只用於本組**仍未讀原文**者。DEC 自身是要點轉述者，其內容不因本檔引用而升格為逐字。

---

## 0. 對照題目五項：既有包已有什麼、本檔補什麼

| 題目項 | 既有包 | 缺口判斷（FACT） | 本檔處置 |
|---|---|---|---|
| 1 逐域 R／O／E 候選與證據 | 第 2.1 節九域表＋第 3 節 D1～D10 | **已涵蓋**，且證據欄完整 | 不重複；僅在第 5 節決策包引用 |
| 2 Missing／unavailable／not evaluated／stale／conflict 五種語意差異 | 只散見（2.3 談 stale；5.4 一句 Missing 保持 Missing） | **沒有把五種放在同一張表比較**；`unavailable`、`not evaluated`、`conflict` 在規則表**沒有對應鍵** | 第 1 節 |
| 3 as_of／Provider／Rule ID／Evidence trace 的既有承載（檔案符號） | 2.2、2.4、2.5、2.6 談語意與缺口，但**承載符號列得少** | 缺「檔案::符號」逐項清單 | 第 2 節 |
| 4 OneBrain 六段輸出與四區版面對應待決 | **完全沒有**（既有包只提 67 8.9 一次） | 發現**兩套實質不同的清單**（v-a／v-b 為更名關係算一套，v-c 另一套）與一套「四區」並存，且 80 第 16.4 節明寫對映待客戶確認（BL-0540） | 第 3 節 |
| 5 最小正式契約決策包（已決／待裁示分開） | 第 4 節 Q1～Q7 是序列，第 5 節是 OB-B 方案表 | 沒有把「已決」整理成一張附出處的清單，也沒有「五種語意」與「六段／四區」兩題的方案表 | 第 4 節 |

---

## 1. 五種「缺」的語意差異

**FACT 前提（S3：依來源拆開，不再合併成一句）**：
- `docs/v2/67` 第 5.4 節第 1 點（標為客戶原話）逐字是：「不得 Missing → 0；Missing → neutral；not evaluated → safe；unavailable → HOLD」。
- `unavailable ≠ neutral` **不在**該句；見 `docs/v2/67` 第 6 節第 5 點與 `PROJECT_RULES.md` 第 13 節（表第 3 列，約第 781 行）。
- `unknown ≠ HOLD` 見 `docs/v2/79` 約第 511 行（該行同列 `missing ≠ 0；unavailable ≠ neutral；not evaluated ≠ safe`）。
- 即：「`unavailable` 不得被當成 HOLD」與「`unavailable` 不得被當成 neutral」是兩個出處的兩句，本檔不把它們寫成同一句客戶原話。`docs/v2/67` 第 8.5 節 schema 把 `missing／unavailable／error` 列為「三種不同的缺」，但**未逐一定義**。

下表「規則表鍵」讀自 `shared/ui_semantics/rules.py::ENTRIES`，「程式內承載」為字面 `git grep` 結果。**（N-2）規則表另有與五態相鄰、但本表未逐列比較的鍵：`not_applicable`（`⬜ 不適用`，無法判定族）、`attention`（`◆ 需要注意`，規則判出的注意事項）、`user_param_unset`（`⬜ 未設定`）、`ok`、`neutral`。** 其中 `not_applicable` 會與 Not evaluated 在畫面上同落灰色 `⬜` 族，Digest 是否需要區分它們（「不適用」≠「沒算」）也是 N1 的一部分，但本檔未展開。

| 語意 | 本檔建議的區分問法（INFERENCE，非契約） | 規則表鍵與已核准字樣（FACT） | 程式內承載（FACT；字面搜尋，未窮舉） | 缺口 |
|---|---|---|---|---|
| **Missing（資料未備）** | 該項該有、但**沒有取到值**，且沒有「取數失敗」證據（來源缺、沒有觀測） | `missing` → `◇ 資料未備`（灰；`MISSING_TEXT`）；`ok` 刻意不寫字 | `ui_v3/viewmodels/common.py::STATUS_MISSING`；`ui_v3/viewmodels/components.py::MissingItem`（`what`＋`reason_code`） | 與 `undetermined` 的分界只在 79 第 11 節（`◇` 是「缺」，`⬜` 是「無法判定」）；Digest 要記哪一個、記什麼原因碼**未定** |
| **Unavailable（不可得）** | 資料**應可取得但這次取不到**（取數失敗、設定沒設、來源整體不可用） | **沒有叫 `unavailable` 的鍵。** 最接近：`fetch_failed` → `⛔ 取數失敗`（紅）；`not_configured` → `⛔ 尚未設定`（紅，成因是設定沒設、沒有執行取數）；`APPROVED_WORDING["reason_no_source"]`＝「來源資料無法使用」 | `common.py::STATUS_FAILED`；`rules.py::STATUS_TO_KEY["failed"]`、`REASON_NOT_CONFIGURED`；另有 AI 面向的「AI 分析暫不可用」（75 第 12 節、80 第 7.4 節），**那是 AI runtime 不可用，不是資料不可得，是另一個物件** | 「Missing」與「Unavailable」在 Digest 是否分兩態、還是 Unavailable＝`failed`＋原因碼，**未定**；`unavailable` 一詞沒有核准畫面字樣 |
| **Not evaluated（未評估）** | **前置條件不足，根本沒有去算**（不是算出「沒事」） | **沒有鍵、沒有核准字樣。** 原則存在（`not evaluated ≠ safe`），畫面上落在 `undetermined`（`⬜ 無法判定`，79 稱「含不適用、未設定」）或 `threshold_pending`（`⬜ 門檻待裁示`） | 內部碼已存在、**僅供內部、無畫面字**：`services/v2_domain/allocation_evidence.py` 的 `NOT_EVALUATED`、`NAV_STATE_NOT_EVALUATED`（檔內註解自陳 "no wording"、"never defines or owns"）；`scripts/bl0545_coverage_probe.py::NOT_EVALUATED_STATES`＝`("stale","conflict")`（**S5：這是 BL-0545 探針內部的計數約定——此探針尚未評估這兩項，計數寫 null 不是 0；不是 stale／conflict 的語意定義，也不表示「stale／conflict 屬於 not evaluated」**）；`ui_v3/viewmodels/action_slot.py`（`ACTION_SLOT_SOURCES_ENABLED = False`，恆無法判定） | `not evaluated` 與 `undetermined` 是否同一個 Digest 狀態未定；內部碼不得被升格為 Digest 契約（`allocation_evidence` 檔頭自稱 not approved vocabulary，見既有包 2.1） |
| **Stale（不是最新）** | 有值、有 `as_of`，但**依正式門檻判為舊** | `stale` → `◷ 不是最新`（黃；規則表註明「只有正式門檻判為舊才用」）；`threshold_pending` → `⬜ 門檻待裁示`（灰，tone 為推論）；`FRESHNESS_TO_KEY`：`fresh` 不加標記、`stale`→`◷`、`undetermined`→門檻待裁示 | `common.py::FRESH_FRESH／FRESH_STALE／FRESH_UNDETERMINED`、`STATUS_STALE`；`rules.py::entry_for_freshness` | **`stale_after` 無任何已裁值**（既有包 V7）；三條 stale 觸發來源沒有端到端核准鏈（`data_state_vocabulary_crosswalk_d3a_2026_11_08.md` 第 4 點，單組作者判定）；`market_page.py::_meta_status` 對 `ok／missing／failed` 以外一律降為 `undetermined`（crosswalk B4，單組作者判定，本組未複驗） |
| **Conflict（來源衝突）** | **兩個以上來源給出不一致的值**，且無法依既定優先序裁決 | **沒有鍵、沒有核准字樣。** `DEC-2026-11-08-04`（已讀原文；決策者欄：客戶裁示經總管派工單轉達，要點轉述、非逐字）Q4：缺資料沿用既有「資料未備／無法判定」，**不新增「過期／衝突」正式詞、不改門檻**；其「不授權事項」欄再次列出「不新增『過期』『衝突』正式狀態詞」 | `services/v2_tables/exp_profile.py::STATUS_INCONSISTENT = "inconsistent"`（Cell 層，兩源不一致時 `value` 為 None，測試 `tests/test_v2_tables_exp_profile.py` 鎖）；BL-0545 探針另將 `conflict` 與 `stale` 計為尚未評估（僅探針內部計數約定，見 Not evaluated 列 S5，非語意定義） | 容差、「同 as-of 不一致」的判定規則未定（既有包 2.3 缺口 3）；`inconsistent` 只存在於 Cell 層，`ui_v3` 的 `STATUSES` 五值**沒有**它（`common.py::STATUSES`＝ok／missing／failed／stale／undetermined）。（S4）依 `data_state_vocabulary_crosswalk_d3a_2026_11_08.md` 的單組作者判定（本組未複驗），`inconsistent` 目前畫面以 `⬜` 呈現，即已實質落在無法判定族，而非沒有畫面 |

**INFERENCE（為什麼這五種不能合併）**：五者對下游推理的含意不同——Missing／Unavailable 是「沒資料」，Stale 是「有資料但可能過時」，Not evaluated 是「沒算」，Conflict 是「有資料但互相打架」。若 Digest 把它們壓成同一個「缺」，OneBrain 就無法依 67 第 8.3 節的 Constraint Precedence 與第 5.4 節禁止項區分「該停手」與「該降級」。**這是推論，不是已核准語意。**

**FACT（目前已有的最小公約數）**：`ui_v3` 層共同欄位 `status` 五值＋`freshness_state` 三值已在 `ui_v3/viewmodels/common.py` 定義；規則表 `rules.py` 註解稱一致性由測試鎖，**本組未重跑該測試，NOT VERIFIED**；它們是**呈現契約**，80 第 16.3 節明寫「UI ViewModel≠Decision Digest」，不得直接當 Digest 狀態集。

---

## 2. as_of、Provider、Rule ID、Evidence trace：既有承載與缺口

`docs/v2/67` 第 5.3 節已有一張概念→承載表（基準較舊）；本節補**檔案::符號**並以 `09ed82ba` 為準，只列本組讀到的。

| 概念 | 既有承載（檔案::符號；FACT） | 缺口（FACT／INFERENCE） |
|---|---|---|
| **as_of（觀測日）** | `services/v2_tables/market_indicator.py`：`obs_date`、`release_date`（註解：同一觀測日的每個修正版次各寫一列，`is_revised`；`rows_from_fred_vintages`）；`services/v2_tables/nav_dividend.py`：每列帶 `fetched_at`（取 `attrs["cache_updated_at"]`），`nav_date`；`ui_v3/viewmodels/common.py` 共同欄位 `as_of`（80 第 6 節）；`services/v2_tables/exp_profile.py` Cell `observed_at` | 欄名不統一（67 5.3）；PIT 取哪一欄未定；`services/v2_domain/allocation_evidence.py` 無根層 as_of／產生時間（既有包 2.2）；國發會兩鍵 `PENDING_NDC_NO_RELEASE_DATE`（`market_indicator.py`）＝來源不提供公布日 |
| **retrieved_at** | 各表 `fetched_at`；`market_indicator.py` 註解的 `fetched_at`；共同欄位 `retrieved_at`（80 第 6 節，來源 `fetched_at`） | 形狀不一（67 5.3） |
| **Provider（資料供應者）** | `services/v2_tables/market_indicator.py::INDICATOR_SPECS`（各鍵 `source` 二元組，見既有包 V6）；`nav_dividend.py` 回傳 `provenance[fund_code]`（含 `ccy_source`，**不寫進 `nav` 表欄**；44 的 `nav` 只有 `source_tier`）；`exp_profile` Cell 的 `sources`／`failed_sources` | 無逐項 Provider 契約；`DEC-2026-11-17-06` 已讀原文明寫 NAV 域**不新增 Provider 欄**、不核准旁路 `provenance[fund_code].source` 與 `chain.data_source`（該 DEC 自述：經對話提示語轉達自稱客戶之選擇，是否客戶本人〔待核〕，QA 無法核對 NOT VERIFIED） |
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

**S2（FACT）**：v-a 與 v-b 的關係，`docs/v2/67` 第 6 節第 3 點自述為：第 2 項 `-18` 原稱「配置」，四頁 IA 後稱「我的資產」——即 **v-a→v-b 主要是更名與格式補述（每句可查看依據），不是兩套實質獨立的輸出**；實質上獨立的是 **v-c**。因此「三套六」應讀作「兩套實質不同的清單（v-a／v-b 一套、v-c 一套）＋四區」。另：`docs/v2/67` 第 5.4 節第 3 點與第 3.2 節（約第 117 行）明寫，Risk Cap 正式定義前，「本期行動」**只能輸出「無法判定」並寫出缺什麼**；故目前「本期行動」**無實體內容**可放進任何一區，N2 所涉的「放哪區」只是預先決定的結構位置，不是現在可呈現的內容。

**FACT**：BL-0540 三子項中（本組只讀其首段）列有「三項 New UI2 規則交界待確認」，狀態為「待客戶裁示」（`docs/BACKLOG.md`）；本組**未讀完 BL-0540 全文**，不確定「六項對映」是否即其中一子項。

### 3.2 INFERENCE：兩套「內容」與四區如何可能對應（AI 試排，非契約）

| 四區 | 可承載的 v-a／v-b 內容 | 可承載的 v-c 項 | 待決點 |
|---|---|---|---|
| **System State（deterministic）** | 「本期行動 ≤3」（現況只能是「⬜ 無法判定」＋缺什麼，見上 S2）（唯一動作權威是 System Action State，67 第 8.1 節表 C-1 列與第 8.2 節） | 系統狀態 | v-b 把「本期行動」列為 OneBrain 輸出，與 C-1「OneBrain 只能引用、不能產生 action」**字面有張力**：行動是放 System State 區（引用）還是 Interpretation 區（敘述）？ |
| **OneBrain Interpretation（AI）** | 市場／我的資產／持股／候選基金各一句；主要風險 1～3 點 | AI 投資總結；風險與不確定性 | 「主要風險」（v-b，1～3 點）與 v-c「風險與不確定性」是否同一項、是否都屬 Interpretation 區 |
| **Maximum Falsification** | v-a／v-b **都沒有**這一項（67 8.9：新增內容） | 最強反證 | 「最大反證」定義未裁（D5） |
| **Evidence** | 每項「查看依據」展開內容 | 主要依據；Evidence trace | v-c 的「主要依據」與「Evidence trace」是否同區、是否同一件事；展開粒度（每句／每區） |

**INFERENCE 觀察**：
1. v-b 的 6 個**內容槽**與四區的 4 個**版面區**不是同一個維度（內容 vs 版面），不是一對一對映問題；真正待決的是「每個內容槽落在哪個版面區、哪些版面區對應 Digest 的哪些欄位」。
2. 「Maximum Falsification」與「Missing／uncertainty 清單」在 67 第 8.7 節要求「每次正式輸出至少含」，但**沒有指定落在哪一區**；v-c「風險與不確定性」可能是它的承載，**未定**。
3. 四區方向已核准，故此題**不是**「要不要四區」，而是「v-a／v-b 一套與 v-c 一套，共兩套實質不同的內容清單怎麼收斂成一套、各落哪一區」。

**未查證**：本組未讀 79 第 9.4 節以外的上下文與 UI-14 的完整裁示文字（只讀到 67 轉錄與 79 該列），未讀 80 第 7.4 節以外的 🤖 線框全貌；v-c 為 H 段要點轉述（80 第 16.4 節自陳客戶逐字原文本組未見）。

---

## 4. 最小正式契約決策包

分兩塊：**4.1 已決**（附出處）；**4.2 需客戶裁示**（附方案表與推薦）。已決與待決**不混寫**。

### 4.1 已決（M1 重寫：每項附該 DEC 自身 provenance；本表**不是**「可作為後續工作前提」的清單，任何引用「前提需帶 provenance 揭露」）

「DEC provenance」欄為本組直接讀 `docs/DECISIONS.md` 原文所得（行號僅供定位，不構成引用格式）。

| # | 已決事項 | 出處 | DEC 自身 provenance（讀自原文） |
|---|---|---|---|
| A1 | 資料鏈固定；Digest 不是 UI scrape；AI 不讀畫面、不回寫 canonical | `DEC-2026-10-29-06`；`docs/v2/67` 第 5.1～5.2、6 節 | 決策者欄：客戶；客戶對話本身執行組未見，原文由總管轉存於 `docs/evidence/decisions/2026-10-29_presentation_contract_migration.md`（逐字存檔）。67 另標為客戶原話 |
| A2 | Missing 保持 Missing；未定義項在 Digest 只能以 Missing／未定義表示 | `docs/v2/67` 第 5.4 節（標「客戶原話」） | 67 檔內標示；本組未逐字比對原始存檔 |
| A3 | `confidence`／投資信心不納入 Digest | `docs/v2/67` 第 5.3 節末列 | 文件組整理（67 自述條件不成立），非單獨 DEC |
| A4 | 決策欄位群與「來源未提供」規則；global timestamp 只代表 render 時間 | `DEC-2026-11-02-07` UI-8 A；67 第 8.5 節 | 決策者欄：客戶；原文由總管轉存於 `docs/evidence/decisions/2026-11-02_new_ui2_ng_and_final_ui_contract_ruling.md`（標「全文逐字」）；客戶對話本身執行組未見 |
| A5 | Freshness Policy 只定欄位，不填門檻值；`stale_after` 另走 Threshold Gate | 同 A4 | 同 A4 |
| A6 | Required／Optional／Excluded 通則 | `DEC-2026-11-02-07` UI-9 A；67 第 8.6 節 | 同 A4 |
| A7 | 逐域清單須逐列審核、不得整欄升格（D2-G1＝B 修正版）；D2 逐域契約與 Digest schema 為兩個獨立 Gate（D2-G2＝A）；首批限身份／NAV／績效（D2-G3＝A）；本筆核准欄位數＝0 | `DEC-2026-11-11-04` | **決策者欄：「客戶 2026-11-11 三項 D2 Gate 裁示經 ChatGPT 對話轉達，ChatGPT 轉達的客戶要點，非逐字；repo 內無逐字存檔、專案 AI 未見客戶對話本身、不可獨立核對；客戶可推翻」**。provenance 欄另寫：單組作者、尚待非作者獨立 QA |
| A8 | 首批 5 列**契約文字**已登記（R-ID-1、R-NAV-1、R-NAV-2、R-NAV-4、R-NAV-5）；R-NAV-3 暫緩、R-NAV-6 Pending；核准的僅是契約文字，不是已實作行為 | `DEC-2026-11-13-06`、`-14-07`、`-17-06` | `-13-06`：客戶，經總管轉達，專案 AI 整理之要點，非逐字。`-14-07`：「來源是否客戶本人〔待核〕；要點轉述，非逐字」。`-17-06`：「經對話提示語轉達**自稱客戶**之選擇；原文僅存對話提示語、repo 無逐字存檔、QA 無法核對（NOT VERIFIED）；是否客戶本人〔待核〕」，且 `-17-06` 自身標「尚待非作者獨立 QA」 |
| A9 | Traceability 固定五段鏈；正式輸出至少含核心理由、Rule Result、最大反證、Missing／uncertainty 清單 | `DEC-2026-11-02-07` C-5；67 第 8.7 節 | 同 A4 |
| A10 | 🤖 版面四區**方向**核准；精確版面 Phase 7 出線框再定 | `DEC-2026-11-02-07` UI-14 A；67 第 8.9 節 | 同 A4 |
| A11 | 六段輸出格式與入口（方案 C） | `DEC-2026-10-29-07`；67 第 6.1 節 | 決策者欄：客戶；原文由總管轉存於 `docs/evidence/decisions/2026-10-29_batch_a_rulings.md`；客戶對話本身執行組未見 |
| A12 | UI ViewModel≠Decision Digest；OneBrain 定位 | `DEC-2026-11-03-08` | 決策者欄：客戶（**A～I 規則為要點轉述**；摘要由總管於派工單內轉交，客戶對話本身執行組未見）；另有「總管讀法（可被客戶推翻）」。80 第 16.4 節亦自陳 H 段為要點轉述 |
| A13 | 畫面字樣以 `rules.py` 為準；`◇ 資料未備` 為缺值字樣（依客戶第 48 節表態） | `DEC-2026-11-02-01`（已直接讀原文，約第 1951 行） | 決策者欄：客戶；原文逐字摘錄存於 `docs/evidence/decisions/2026-11-02_final_ui_contract_freeze_assignment.md`（**摘錄、非全文**）；supersedes 欄中「以 `◇ 資料未備` 為準」標為**執行組讀法，可被客戶推翻** |
| A14 | D1 採方案 C（資料契約先行）為規劃方向；正式 Digest 施工、Phase 7、Provider、Claude API runtime 未授權；FX 閘門維持關閉 | `DEC-2026-11-08-02` | 決策者欄：客戶裁示，經總管派工單轉達；**客戶指示經總管轉交的要點轉述，非逐字**，客戶可推翻 |

**M1：A15（`DEC-2026-11-18-03`／`-04`）已移出「已決」。** 本組在 worktree 的 `docs/DECISIONS.md` 以 `grep -n "^### DEC-2026-11-18-03"` 查無該標題（NOT VERIFIED：可能尚在 #1276 未合併分支）。〔#1276 合併後已落 main，本句為撰寫時舊況。〕既有包檔頭對它的敘述不得在此當成已決事項引用。見下表。

**待核／未驗（不得作為前提）**

| # | 項目 | 狀態 |
|---|---|---|
| U1 | `DEC-2026-11-18-03`／`-04` 的內容（含「OB-B 程式 PR 前須客戶先確認 `DEC-2026-10-31-03` fake provider Gate」） | worktree 基底 `DECISIONS.md` 查無〔#1276 合併後已落 main〕；僅見於既有包檔頭的轉述；**未驗** |
| U2 | `DEC-2026-10-31-03`、`-11-17-05`、`-11-18-01` 等其餘引用 DEC | 本組未讀；**未驗** |
| U3 | A8 所涉的「Required 升格」是否同時核准 | 較嚴讀法（既有包 2.1）；客戶原意未確認 |

### 4.2 需客戶裁示（每題附方案表；推薦為執行組讀法，可被客戶推翻）

編號用 N1～N5，避免與既有包 Q1～Q7 混淆。N1～N3 是本檔新增；N4／N5 引用既有包。

#### N1：Digest 對「缺」要用幾種狀態、各叫什麼（第 1 節五種語意）

**先決問題（M2，客戶確認）**：`DEC-2026-11-08-04`（已讀原文）Q4 與其「不授權事項」欄寫明**不新增「過期」「衝突」正式狀態詞、不改門檻**。本題方案 A 在 Digest 內部保留 `stale`／`conflict` 的區別，**是否因此觸到 Q4，本檔不判定**——Q4 的字面對象是「正式狀態詞」（畫面／正式詞彙），而 Digest 內部概念名是否算「正式狀態詞」有兩種讀法（讀法 1：Q4 只管畫面字樣，Digest 概念不受限；讀法 2：Q4 管所有「正式狀態詞」，Digest 不得新增）。**這一點必須併入 N1 的問法，由客戶確認。**

| 方案 | 內容 | 優點 | 缺點 | 風險 |
|---|---|---|---|---|
| **A：Digest 內部五態分開，畫面字樣沿用既有、不新增** | Digest 概念 `missing`／`unavailable`／`not_evaluated`／`stale`／`conflict`（命名僅為概念）；畫面仍只用規則表既有鍵 | 保留推理所需區分；不新增畫面字樣 | Digest 與畫面不是一對一，需要對照表；**能否成立取決於客戶對 Q4 的讀法（讀法 2 下，A 的 `stale`／`conflict` 若算正式狀態詞則須退回 B 或另裁）** | 中：與 Q4 的關係未定；A 在讀法 1 下風險低、讀法 2 下與既有 DEC 衝突 |
| **B：Digest 沿用 `ui_v3` 五值（ok／missing／failed／stale／undetermined）** | 不新增概念；`not_evaluated`、`conflict` 併入 `undetermined` | 在讀法 1、2 下都不觸 Q4（`stale` 已存在於 `rules.py`）；零新增 | 失去區分；與 67 第 8.5 節 `missing／unavailable／error` 三分欄位群有落差；`conflict` 資訊遺失 | 中：資訊遺失；後補需改 Digest schema。**B 並非比 A 風險低，只是不碰 Q4** |
| **C：五態分開且新增畫面字樣** | 為 `not evaluated`／`conflict` 另請核准新正式詞 | 畫面與 Digest 一致 | 受 `APPROVED_WORDING` Gate；**直接與 Q4 字面相左，需客戶推翻或修改 Q4** | 高 |

**S4：方案 A 的對映表僅在客戶採 A 時才適用，且有替代對映。** 若採 A：

| Digest 概念 | 對映 1（本檔試排） | 替代對映 |
|---|---|---|
| `unavailable` | `failed`＋`not_configured` | 併入 `missing`（若客戶不要分「取不到」與「沒有」） |
| `not_evaluated` | `undetermined` | `threshold_pending`（若成因是門檻未裁）；或 `not_applicable`（若成因是不適用，這不是「沒算」） |
| `conflict` | `undetermined`（Cell 層 `inconsistent` 目前畫面即落 `⬜`，crosswalk 單組判定，本組未複驗） | 獨立顯示（須新字樣，落方案 C） |

**推薦（執行組讀法，可推翻）：先請客戶確認 Q4 讀法，再選 A 或 B。** 若客戶不願在此題處理 Q4 讀法，則退而求其次選 B（不碰 Q4 的零風險路徑）；A 是在讀法 1 確認後的資訊保存較佳方案。**本檔不核准任何狀態名稱。**

#### N2：兩套實質不同的「六」清單與四區怎麼收斂（第 3 節）

| 方案 | 內容 | 優點 | 缺點 | 風險 |
|---|---|---|---|---|
| **A（推薦）：兩層模型——內容槽沿用 v-b，版面區沿用四區，v-c 併入對應區** | v-b 六內容槽為「輸出什麼」；四區為「放在哪」；v-c 六項歸入四區（系統狀態→System State；AI 投資總結／風險與不確定性→Interpretation；最強反證→Max Falsification；主要依據／Evidence trace→Evidence）；「本期行動」明定引用 System Action State（放 System State 區，Interpretation 區不另產 action） | 不推翻任何已決（v-b、四區、C-1）；一次消除 BL-0540 對映題；符合 C-1 | 需客戶確認 v-c 各項併入方式與「本期行動」位置 | 中：改變「本期行動」是 OneBrain 輸出 的字面讀法，須客戶確認不違原意 |
| **B：以 v-c 為準，取代 v-b** | v-c 成為唯一輸出清單 | 單一清單、與四區較貼 | 取代已決的 `DEC-2026-10-29-07` 固定輸出；v-c 只是要點轉述，非逐字 | 高：以未逐字確認的轉述覆蓋已決裁示 |
| **C：暫不收斂，等 Phase 7 出線框一併裁** | 維持現況 | 無需現在裁示 | 兩套清單並存繼續，Digest schema 的欄位無法定（Digest 要不要含「反證」「不確定性」欄取決於此） | 中：拖延會讓 Q6（Digest schema Gate）更難提出 |

**補註（S2）**：因 Risk Cap 未定義，「本期行動」現況只能輸出「⬜ 無法判定」＋缺什麼（67 第 5.4 節第 3 點、第 3.2 節），目前無實體內容可放；N2 決定的是**結構位置**，不是內容。另 v-a→v-b 是更名（67 第 6 節第 3 點），故真正要收斂的是「v-a／v-b 一套」與「v-c」兩套。

**推薦 A。** 理由：A 不覆蓋任何已決事項，並把「內容 vs 版面」兩個維度拆開，是最小的消歧。**但「本期行動放哪區」牽涉 C-1 與 `DEC-2026-10-29-07` 字面張力，必須客戶裁示。**

#### N3：Evidence trace 的最小欄位集——只裁「67 第 8.5 節已決欄位」之外的新增項

**S1／D2-G2 前提**：本題屬 Digest 欄位範圍，依 `DEC-2026-11-11-04` D2-G2，在 D2 逐域契約完成前，不得啟動 Digest schema 研究／施工。**因此本題在 D2 完成前只能「登記為待決」，不應現在向客戶請示為可核准的 schema 欄位。**

**欄位對照（避免重複請示已決欄位）**：

| 欄位 | 狀態 | 出處 |
|---|---|---|
| `value`、`unit`、`source`、`provenance`、`as_of`、`release_date`、`retrieved_at`、`frequency`、`freshness_state`、`stale`、`missing／unavailable／error` | **已決（欄位群層級；A4）** | 67 第 8.5 節 |
| 固定五段 Traceability 鏈；至少含核心理由、Rule Result、最大反證、Missing 清單 | **已決（A9）** | 67 第 8.7 節 |
| `rule_ref`（Rule ID／版本／門檻引用） | **未決**——67 第 8.7 節「仍待」；`ui_v3` 的 `EvidenceItem.rule_ref` 與 `allocation_evidence` 的 `RuleRef(NOT_DEFINED)` 是**內部承載**，不是契約欄 | 79 UI-10；BL-0527 第 4 項 |
| 句子→依據對映（`AI-3`） | **未決** | 67 第 8.7 節 |
| Digest id／schema version／fingerprint／policy version | **未決**（Digest schema Gate 之後） | 67 第 8.6 節 Audit 欄位群；75 第 6 節 |

**因此本題唯一的「新增項」是 `rule_ref` 與對映格式，且兩者都依賴既有包 Q3（Rule ID 格式 Gate）。** 已決欄位不重複請示。

| 方案 | 內容 | 優點 | 缺點 | 風險 |
|---|---|---|---|---|
| **A（推薦）：本題併入既有包 Q3，不獨立請示；D2 完成前僅登記** | 不另提 N3；`rule_ref` 與對映併入 Rule ID 格式 Gate | 不重複已決欄位；不違反 D2-G2 順序 | 無進展可見 | 低 |
| **B：獨立請示 `rule_ref` 的必含性（有才填／缺時寫 `not_defined`）** | 只問這一個新增項 | 範圍最小 | 仍屬 Digest 欄位範圍，須待 D2-G2 順序允許；「缺時寫 `not_defined`」是新語意 | 中 |
| **C：連同格式一併裁** | 併 Q3 | 一次到位 | 依賴投資規則內容，而正式規則尚不存在 | 中 |

**推薦 A。** **Provider 欄是否升格為契約欄仍受 `DEC-2026-11-17-06`（已讀原文：自稱客戶〔待核〕；NAV 域不新增 Provider 欄）限制，不併入本題。**

#### N4／N5：引用既有包，不重複

- **N4＝既有包 Q1＋Q2**（OB-B 離線 interface＋Fake Provider 授權範圍，方案 B 推薦；及 BL-0527／0528 是否擋 OB-B）。見既有包第 4.2、5 節。
- **N5＝既有包 Q3＋Q4**（Rule ID／`rule_version` 格式；stale／conflict／NAV 10 日門檻按來源逐一定）。**N1 的 `stale`／`conflict` 概念層與既有包 Q4 的「門檻值」不同層**：N1 只問「Digest 要不要有這兩態」，Q4 才問「怎樣算 stale／conflict」；而 N1 還須回答 `DEC-2026-11-08-04` Q4（不新增過期／衝突正式詞）的讀法。

### 4.3 建議的客戶問法順序（RECOMMENDATION）

1. N4（OB-B 授權範圍，解除 Gate 歧義）——獨立、可先問。
2. N1（含 Q4 讀法確認）——先確認 Q4 讀法；N3 依 D2-G2 僅登記、併入既有包 Q3，不獨立請示。**N1、N2 是否現在可提，亦受 D2-G2（先 D2 後 Digest schema）順序約束；若客戶認為這些屬 Digest schema 範圍，應延到 D2 完成後。**
3. N2（版面／內容收斂）——建議在 N1 之後；注意「本期行動」現況無實體內容（S2）。
4. N5（格式與門檻）——依賴最重，放最後。
**不問**：Risk Cap、減碼 trigger、反證定義、持倉域 R／O／E（沿用既有包「延後」判斷）。

---

## 5. 範圍外（明確未做）

本檔**未**新增 Digest Schema／欄位名稱契約、正式投資 prompt、Provider runtime、Risk Cap、Action State 或任何 API 呼叫；**未**改任何程式、`DECISIONS.md`、`BACKLOG.md`、`HANDOFF.md`。第 1 節五態名稱、第 4.2 節方案內的狀態名與欄位名皆為**概念示意**，不是命名提案、不是契約。

---

## 6. 我沒有查證的部分

1. **單組作者**，未經第二組獨立驗證（`CLAUDE.md` §-2 規則 6）；全稱句（「沒有鍵」「無承載」）只代表字面搜尋，改名、動態組字串、別名不在內。
2. 第 1 節規則表鍵讀自 `shared/ui_semantics/rules.py` 的 `ENTRIES`／`STATUS_TO_KEY`／`FRESHNESS_TO_KEY`／註解；`APPROVED_WORDING["reason_no_source"]` 等為字面讀取。**僅對規則表各鍵所引的 DEC 出處成立：本組只讀到規則表 `source` 欄與 67／79／80 的轉述，未讀這些 DEC 原文；第 4.1 節所列 DEC 則已讀原文（見第 8 點）。**
3. crosswalk 的判定（B4、第 4 點等）取自 `data_state_vocabulary_crosswalk_d3a_2026_11_08.md` 的單組作者判定，本組未複驗。
4. 第 3 節的「六」清單（表列三個名稱，實質兩套）：v-a 與 v-b 取自 67 的轉錄；v-c 取自 80 第 16.4 節（H 段要點轉述，客戶逐字原文本組未見）。本組未讀 79 第 9.4 節全文與 UI-14 裁示全文，未通讀 BL-0540 全文。
5. 第 3.2 節的對應表是**AI 試排**；尤其「本期行動放 System State 區」是依 C-1 推得，與 `DEC-2026-10-29-07` 字面「OneBrain 輸出本期行動 ≤3」存在張力，**不是已核准讀法**。
6. 第 2 節 `services/v2_tables/nav_dividend.py`、`exp_profile.py`、`market_indicator.py` 只讀命中片段（docstring 與符號），未通讀；未驗證實際回傳形狀與測試是否仍綠。
7. 本機缺依賴，**未執行任何業務測試**；唯一跑的是文件守衛（見提交紀錄），依賴齊全環境下是否綠只能由 CI 驗。
8. `DEC-2026-11-18-03`／`-04` 在 worktree `docs/DECISIONS.md` 查無〔#1276 合併後已落 main〕；是否對第 4.2 節 N4 已有部分裁示 NOT VERIFIED。第二版（修稽核）已直接讀 `DEC-2026-11-11-04`、`-11-17-06`、`-11-14-07`、`-11-13-06`、`-11-08-02`、`-11-08-04`、`-11-02-01` 與 `-11-02-07`／`-10-29-06`／`-10-29-07`／`-11-03-08` 的決策者欄，但**各 DEC 的逐字存檔（`docs/evidence/decisions/*`）本組未讀**。
9. 方案推薦的「風險低／中／高」為作者推論，未做實作驗證。
10. 是否觸發 Model／Effort Change Gate（`PROJECT_RULES.md` 第 5.1 節）：本檔為 docs-only，未評估。
