# 54｜Phase 7 設計方向登記（Design Backlog / Research Hypotheses）

> 本文件為 Design Backlog / Research Hypotheses，不是 Production Specification。除非客戶在 Phase 5 Data Gap Audit 後正式核准，任何 Agent 不得因本文件存在而直接實作其中模型、threshold、API/MCP、directional signal 或資料來源變更。

## §00 性質、出處與用詞

- **性質**：純文件、Non-Production。本檔是登記，**不構成動工授權**（`CLAUDE.md` §-1）；本檔的存在本身不是任何一個 Phase 的開工條件。
- **出處**：客戶已確認的「Phase 7 設計方向」，經總管 2026-10-15 派工轉達（對話中，repo 內無原文）。本檔是**客戶原話的整理，不是逐字稿**；唯一逐字的是檔頭那一段警語。整理時不增刪語意；文件組自己加的東西（各節「與現行規格的關係」、§19 張力表、§18 狀態欄的初判）一律就地標明是文件組加的。
- **與 repo 內其他「Phase 7」無關**：本檔所稱 Phase 7，與 `BACKLOG.md` 的「phase 7 (v19.93)」（F-PROV-1 provenance 分期）、`repositories/fund/sources.py` 註解裡的「F-PROV-1 phase 7」**無關**，只是同名。
- **「股份級別」不是「級別」**：本檔「Share Class／股份級別」指同一檔基金的不同股份類別（幣別、配息或累積、避險與否等）；repo 慣用的「級別」指**核心／衛星 tier**（`shared/policy_tier.py`），**兩者不同義**。本檔一律寫「股份級別」或 Share Class，不單寫「級別」。
- **標記慣例**：本檔中任何具體數字、公式或門檻，一律在旁標 `Candidate / Unvalidated / Non-production`。帶這個標記的東西是**研究假說**，不是規則、不是預設值、不得寫進程式當常數。
  - 路線圖（§0）裡的批量與寬度（Phase 4 每批上限、Phase 3 的 390px）是客戶描述的驗收／施工方式，本檔只記錄；它們何時生效，以各該 Phase 的正式核准為準。
- **權重、門檻、veto 條件、分數**：本檔一律**未核准、未定值**。本檔出現的任何數字都不是它們的值。
- **禁詞**：本檔遵守交接本第 7 節〈客戶 2026-10-05 接手訊息：禁詞〉（劃線裡的字也算），不寫那八個詞的字面；需要時改用中性說法（例：「調整方向」「增加／降低曝險」「候選」）。

## §0 路線圖

| Phase | 內容 | 本檔角色（文件組加註） |
|---|---|---|
| 1 | #966（exp 正式頁接上 C2 資料層）。✅ 已完成（#966 merge `dbb629c`） | 無 |
| 1.5 | 移除舊「全面禁止方向性投資建議」規則。**獨立 PR，只做契約／文件／tests 一致性。** | 本檔 §7 標出的張力待此處理（依客戶方向）；§19 其餘張力是否一併處理，未定；在 1.5 完成並經客戶核准前，現行紅線照舊有效 |
| 2 | B 線五頁真資料 preview | 無 |
| 3 | 客戶實際使用／視覺／390px 手機 UX 驗收 | 無 |
| 4 | 修驗收問題（每批 ≤3） | 無 |
| 5 | **Read-only Data Gap Audit**：只盤點、不接來源（見 §0.1） | 本檔各節「需要 Data Gap Audit」欄的輸入 |
| 6 | 客戶決定補哪些資料／API／MCP | 無 |
| 7 | 依 Data Gap Audit 結果＋本 backlog，制定正式 Production Specification | **本檔在這一步才被正式使用** |
| 8 | 核准後分小批實作 | 依 Phase 7 正式規格，不依本檔 |

### §0.1 Phase 5 Data Gap Audit 的範圍（只盤點，不接來源）

- **盤點清單（17 項）**：
  1. NAV／基本資料
  2. Fund／Share Class／ISIN／Currency／Dist-Acc／Hedge 等 identity capability
  3. Top holdings／partial holdings
  4. 官方產業配置
  5. Benchmark
  6. peer／fund universe
  7. USD/TWD 現貨與歷史
  8. manager／strategy
  9. company fundamentals
  10. company → industry／theme mapping
  11. macro
  12. policy／regulation evidence
  13. fund flows
  14. historical data／backtest capability
  15. transaction／switching／settlement 資料能力
  16. distribution／return-of-capital 類資料能力
  17. 各資料來源 publication cadence／publication lag
  - Audit 要如實回答：目前可取得的是 full holdings、partial／Top holdings、official industry allocation，或完全沒有。
  - 出處：客戶原文，經總管 2026-10-15 第二次派工照錄轉達（第一次派工漏給，見交接本第 2 節〈總管錯誤紀錄〉2026-10-15）。
  → **2026-10-15 補入，狀態更新，不是漏刪**：本節初版寫「清單本體未隨本次派工轉達，本檔不自行補列」，在寫下當時為真。
- **每一項要記錄的屬性**：
  1. authority／reliability
  2. license／ToS
  3. cost／quota
  4. update frequency
  5. publication cadence
  6. publication lag
  7. historical coverage
  8. missing semantics
  9. timezone
  10. trading-day semantics
  11. freshness
  12. provenance
  13. cross-check
  14. fallback
  15. failure behavior
- **分類**：已有且可靠／已有但品質不足／完全缺少／有重複來源／應保留／候選替換／需要客戶裁示。
- **不預設**需要 100% 全持股；**不自訂** coverage threshold。
- 與現行規矩的關係（文件組加註）：本盤點同時落在交接本第 7 節〈永久規則：資料缺口／公式疑義 → 協作助手外部資料源評估 Gate（客戶 2026-10-10）〉的射程內；該 Gate 的禁止事項（不補 0、不猜資料、不自行更換 production 資料源、不自行修改具投資判斷意義的公式）在 Phase 5 照舊有效。

## §1 永久原則：資料歸資料、AI 分析歸 AI 分析

- **三層職責**：
  - **Data Layer**：取得、保存、標示來源與時間的客觀事實（NAV、FX、財報、持股、政策事實、產業數字）。
  - **Deterministic Analytics**：對 Data Layer 的事實做可重現的計算。
  - **AI Layer**：解釋、歸納、推論。
- **AI 不得**：
  - 猜 NAV／FX／財報／持股／政策事實／產業數字；
  - 以搜尋摘要冒充 production data；
  - 自行替換來源；
  - 把 missing 補 0。
- **AI 推論與 objective facts 分開保存**；AI 推論**不得寫回 Data Layer**。
- **不得僅憑單篇質化文本觸發 production directional signal。**
- 與現行規格的關係（文件組加註）：與 `CLAUDE.md` §1（Fail Loud, Never Fake）同向；本節不放寬 §1 任何一條。

## §2 四層決策架構（不是 8 個 Gate 全 AND）

決策不是把一串 Gate 全部 AND 起來，而是分四層：

1. **Hard Safety／Veto**：critical freshness、identity mismatch、critical source conflict、thesis invalidation、data-quality failure。
2. **Evidence Score**（加減分、權重未定）：fund quality、Benchmark／peer RS、structural trend、quantitative proxy、partial look-through、price position、FX、portfolio overlap、allocation fit、transaction cost、cash opportunity cost。
3. **Execution Layer**：分開「應不應調整」與「怎麼執行」。涉及 TWD Cash／USD Cash／Fund A／Fund B、switching、same-umbrella、channel、成本、settlement、Pending、In-Transit、capital destination、FX conversion、cash drag。**不得假設「降低曝險＝換回 TWD」。**
4. **Confidence／Explanation**：completeness、missing、stale、source failure、evidence conflict、look-through coverage、confidence、invalidation、supporting evidence。資料不足時顯示「⬜ 無法形成可靠判斷」。

- **具體的 veto 條件、score、weight、threshold 一律未核准。**

## §3 標的身分鏈

- 身分鏈：**Fund Identity → Share Class → ISIN → Currency → Dist／Acc → Hedged／Unhedged → Channel Holding Identity**。
- ISIN 重要，但**不寫成唯一 SSOT**。
- **現在不改 production schema。**

## §4 NAV／Return Series 契約

- 三條序列分開：**Raw NAV**／**Distribution Series**／**Total Return（Reinvested）**。
- **不假設**各家 Adjusted NAV 的定義相同。
- Z-score、Drawdown、backtest 用哪一條序列，**待資料契約與回測決定**。

## §5 Look-through 降級

依資料完整度由高到低降級：

1. **Full／High Coverage**。
2. **Partial**：只有 Top holdings。須標 Partial；不得稱為完整 exposure；coverage 無法可靠計算時就不得估。
3. **Industry Allocation Fallback**：保留 source、as-of、publication lag、scope；不得假裝是 security-level。
4. **No Data**：「⬜ 無法判定（持股／產業資料未備）」。

- **引用既有規格與程式（不重抄）**：
  - `docs/v2/52_ui_design_spec.md` B-10（持股重疊）、B-11（穿透透視）、B-13（甜甜圈圖穿透資產）。
  - `ui/helpers/portfolio/concentration.py`（現行穿透曝險的落後與覆蓋標示）。
  - `shared/signal_thresholds.py` 的 `LOOKTHROUGH_*` 常數。
- 與現行程式的關係（文件組加註）：上列現行程式與常數**不因本節而變動**；本節的降級分層是否取代、沿用或細化它們，屬 Phase 7 正式規格的範圍。

## §6 價格模型

- 舊「H_1Y - nσ」**不是正式規則**。`Candidate / Unvalidated / Non-production`
- 改研究兩條**分離**的量：
  - **Relative Position**：Rolling Z-score、Bollinger 類。
  - **Peak Drawdown**：Rolling／High-Water-Mark。
- **Benchmark／Peer RS** 作為 Mean-Reversion Guard 的候選（見 §7）。
- 下列皆為 **Research Hypothesis**，不是門檻：
  - 「Z ≤ -2」 `Candidate / Unvalidated / Non-production`
  - 「RS -2σ」 `Candidate / Unvalidated / Non-production`
  - 「DD -10%」 `Candidate / Unvalidated / Non-production`
  - 「DD -20%」 `Candidate / Unvalidated / Non-production`

## §7 Mean-Reversion Guard

- **價格低不等於便宜。**
- 研究對象：fundamentals、RS、holdings quality、structural trend、policy regime、style drift、manager／strategy change、market price。
- 價格可能領先落後的揭露資料；**不能只用低頻基本面當 fuse**。
- RS 可作為**候選即時 Guard**，須回測。
- ⚠️ **據實標註（客戶要求）**：本主題與現行 `docs/v2/44_fund_ui_ssot.md` §1.2（呈現層禁令）、`docs/v2/52_ui_design_spec.md` Part C（禁用清單）的紅線**衝突**。待 Phase 1.5 處理並經客戶核准；在那之前，44 §1.2 與 52 Part C 照舊有效，本節不得被引用為放寬它們的依據。

## §8 產業／政策 Evidence

- **Quantitative**：revenue／profit、CAPEX、R&D、demand、market share、RS、sector／theme index、Proxy ETF、holdings change。
- **Qualitative**：official policy、regulation、legislation、tariff、export restriction、company announcement、credible research／news。
  - 須有 source／timestamp、可追溯；
  - 原始事實與 AI interpretation 分開保存。
- **AI 不得憑單篇新聞宣布新產業時代。**
- **單一 Proxy ETF 不得等同整個產業 regime。**

## §9 基金候選／替代引擎

- **整合在 EXP、不新增頁面。**
- 三種情境：
  1. 使用者主動找；
  2. 系統發現結構性機會；
  3. 替換現有持有。
- 候選 evidence：fund quality、benchmark／peer、actual／partial holdings、industry fit、portfolio overlap、allocation fit、NAV price、FX、transaction／switching reality、data confidence。
  - 出處：客戶原文，經總管 2026-10-15 第二次派工照錄轉達。
  → **2026-10-15 補入，狀態更新，不是漏刪**：本節初版寫「細目未隨本次派工轉達，本檔不自行補列」，在寫下當時為真。
- **目標是「適合目前 portfolio 的候選」，不是熱門排行榜。**
- **AI 不得把網路上看到的基金直接加入 production universe。**

## §10 FX／Cash／Execution

- **基金決策 ≠ 換匯決策。**
- 資金路徑：
  - TWD Cash → USD Cash
  - USD Cash → Fund
  - Fund A → USD Cash
  - Fund A → Fund B
  - USD Cash → TWD Cash
- **FX 不得錯誤阻止幣別內 rotation。**
- 研究對象：USD／TWD、FX contribution、TWD total return、rate differential、cash yield、opportunity cost、成本、capital destination。
- **Cash 是合法狀態**；但**不得因美元便宜就自動建議大量建立 USD Cash** —— 須考慮 carry、opportunity cost、liquidity、expected deployment、portfolio risk。

## §11 Share Class／Switching／In-Transit

- 涉及：Acc／Dist、Hedged、channel、switching／redemption fee、same-umbrella、cross-family、settlement lag、forward pricing、Pending、In-Transit。
- **same-umbrella 可為候選因素，但不得預設加分。**
- **Pending／In-Transit** 用來避免 LINE 與 dashboard 重複提醒。

## §12 配息與本金侵蝕

- 研究對象：distribution composition、return of capital、NAV trend、total return、payout sustainability。
- 「本金配息 >30%」只是**候選研究假說**。 `Candidate / Unvalidated / Non-production`

## §13 非對稱資料更新

- 依 publication cadence／lag 分流：
  - NAV／FX、market／benchmark：較高頻；
  - holdings、industry allocation：較低頻；
  - policy evidence：event／scheduled hybrid。
- **不得現在硬寫日期或頻率。**

## §14 LINE State Machine

- **LINE 是 notification consumer，不是分析 engine。**
- 涉及：state transition、cooldown、hysteresis、materiality、Pending／In-Transit mute、recovery notification、deep link。
- 「-2σ trigger／-1.7σ reset」只是**候選示例**。 `Candidate / Unvalidated / Non-production`

## §15 Decision Snapshot

- **輕量 audit trail 優先於大型 backtesting platform。**
- 欄位概念：snapshot id、timestamp、fund／share-class identity、decision state、NAV as-of、price evidence、benchmark／RS evidence、FX state、portfolio state、data completeness、confidence、rule version、evidence references。
- 事後驗證：3／6／12 個月。 `Candidate / Unvalidated / Non-production`
- **schema 格式 Phase 7 再定，不得提前固定。**

## §16 北極星

可信資料 → 精確辨識持有的 Fund／Share Class → 看懂世界與產業變化 → 判斷基金是否跟上 → portfolio 是否重疊或失衡 → 更合適的候選 → NAV／FX／Cash／execution → 證據充分時形成清楚方向 → AI 用人話解釋 → LINE 只在真正值得行動時提醒 → Pending／In-Transit 不重複干擾 → Decision Snapshot → 3／6／12 個月驗證（驗證期間 `Candidate / Unvalidated / Non-production`，同 §15）。

## §17 Backlog 更新規則

新發現的 Phase 7 問題，若**不阻塞當前 milestone**：

1. 寫入本檔；
2. 附 evidence 與 repo 位置；
3. 標狀態：**Research**／**Data Gap**／**Candidate**／**Needs Customer Decision**／**Blocked**；
4. **不施工。**

## §18 各節狀態

「是否已核准」一律為**否**。「需要 Data Gap Audit」與「需要客戶裁示」兩欄是**文件組初判**（2026-10-15），未經第二組驗證；客戶或總管裁定後以裁定為準。「需要客戶裁示」指 Phase 6／7 的正式核准。

| 節 | 主題 | 是否已核准 | 需要 Data Gap Audit | 需要客戶裁示 |
|---|---|---|---|---|
| §0 | 路線圖 | 否 | 否（它定義 Audit 本身） | 是 |
| §1 | 永久原則 | 否 | 否 | 是 |
| §2 | 四層決策架構 | 否 | 是 | 是 |
| §3 | 標的身分鏈 | 否 | 是 | 是 |
| §4 | NAV／Return Series 契約 | 否 | 是 | 是 |
| §5 | Look-through 降級 | 否 | 是 | 是 |
| §6 | 價格模型 | 否 | 是 | 是 |
| §7 | Mean-Reversion Guard | 否 | 是 | 是（另需 Phase 1.5） |
| §8 | 產業／政策 Evidence | 否 | 是 | 是 |
| §9 | 基金候選／替代引擎 | 否 | 是 | 是 |
| §10 | FX／Cash／Execution | 否 | 是 | 是 |
| §11 | Share Class／Switching／In-Transit | 否 | 是 | 是 |
| §12 | 配息與本金侵蝕 | 否 | 是 | 是 |
| §13 | 非對稱資料更新 | 否 | 是 | 是 |
| §14 | LINE State Machine | 否 | 否 | 是 |
| §15 | Decision Snapshot | 否 | 否 | 是 |
| §16 | 北極星 | 否 | 否 | 是 |
| §17 | Backlog 更新規則 | 否 | 否 | 是 |

## §19 與現行規格的已知張力（文件組辨識，非窮舉）

本節由文件組自行對照後加入，**非窮舉、未經第二組驗證**；它只是提醒 Phase 1.5 與 Phase 7 要處理哪些地方，不判定任何一方對錯。在 Phase 1.5 完成並經客戶核准前，下表左欄的現行條文照舊有效。

| 現行條文 | 本檔相關節 | 張力 |
|---|---|---|
| `docs/v2/44_fund_ui_ssot.md` §1.1 G2、G3 | §2、§9、§10、§14 | G2 限定調整只能用「偏離提示、客觀對照、情境試算」三種形式；G3 寫偏離提示不提供具體處置方向。本檔 §2 第 4 層、§16 的「證據充分時形成清楚方向」屬方向性輸出 |
| `docs/v2/44_fund_ui_ssot.md` §1.2 | §6、§7、§14 | 禁方向詞、禁顏色暗示方向、禁輸出買賣指示 |
| `docs/v2/52_ui_design_spec.md` Part C 第 2、5、6、8 條 | §2、§6、§9、§14 | AI 多空判斷、Switching Engine 的 From → To recommendation、任何預測、Explicit Action Thresholds |
| `docs/v2/52_ui_design_spec.md` Part C 第 7 條 | §11 | Intra-family free switch；本檔 §11 把 same-umbrella 列為候選因素（但不得預設加分） |
