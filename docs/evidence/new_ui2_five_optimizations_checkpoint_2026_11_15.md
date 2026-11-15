# New UI2 五項防返工優化｜產品規劃接手與最小 Gate（2026-11-15）

> **性質：客戶同意保存的規劃方向／下一批候選工作，不是新的施工、正式金融契約或治理規則生效。**
> 本文件記錄 2026-11-15 對話中提出的五項優化，以及 GitHub-first 審查後的限縮方案。**本檔為 docs/evidence 計畫證據，不是第二套 SSOT，不取代** `docs/v2/44_fund_ui_ssot.md`、`docs/v2/67_ai_action_vocabulary.md`、`docs/v2/75_onebrain_ai_architecture.md`、`docs/v2/79_final_ui_contract_freeze.md`、`docs/v2/80_new_ui2_architecture_proposal.md`、`docs/v2/82_new_ui2_assets_ui_data_evidence_proposal.md`、`docs/DECISIONS.md`、`docs/BACKLOG.md`、`docs/HANDOFF.md` 或 `PROJECT_RULES.md`。
> **觀測快照（不是永久最新狀態）**：2026-11-15，main `816e6c816ceeb2d58c46e450351cd1de3419cf04`；當時 Open PR＝0，最新 main push CI success。使用前重新核實 GitHub main／PR／head／diff／CI／QA／branch。
> **使用者關切**：不要「原本的問題未結案、又一直提出新問題」；優先可見且可驗收的 💼 畫面、低返工、少 Token、額度中斷可無記憶接續。

## 0. 不變的目標與安全邊界

- New UI2 正式五頁固定：🌍 市場與趨勢（mkt）、💼 我的資產（ast）、🔍 找基金（exp）、🤖 AI 投資總結（ai）、⚙️ 設定（set）；只以 `ui_v3/` 為新版實作主線。Old UI 唯讀參考；`ui_v2` maintenance-only，正式切換與刪除另 Gate。
- 資料層／確定性規則／ViewModel／AI 嚴格隔離：**Missing ≠ 0、UNAVAILABLE ≠ SAFE、未評估 ≠ 正常**。UI 不能自行計算金融值；資料與 Provenance 完整、摘要簡潔、明細可展開。
- 💼 Stage 1 的 S-VM（PR #1248）已合併，但**尚未有已授權的可見 💼 renderer、registry 或真實資料接線**。`DEC-2026-11-14-06` Q1／Q2 授權僅限既有 Stage 1 基準及五個新增純函式檔。22 項 S-VM 暫行判斷不等於正式規則。
- D2 17 列中**只有 4 列契約文字核准**（R-ID-1、R-NAV-1、R-NAV-2、R-NAV-5）；其他 13 列 Pending，R-NAV-3 明示暫緩；契約文字核可 ≠ Schema／producer／FX／UI 接線授權（`DEC-2026-11-14-07`）。
- 🔍 S2-T0 採 B 暫緩；X1／`pool_not_cloud` 其他語意仍循各自 Gate。BL-0545 真實資料外部輸入仍 BLOCKED，使用者暫不提供。OneBrain／Digest schema／Claude API／Phase 7 仍未取得動工授權。
- 本計畫不修改 frozen 44、`PROJECT_RULES.md`、正式狀態字樣／映射、Risk Cap、FX Gate、金融公式、來源／Schema、`ui_v3` 程式、任何 workflow。新施工或正式治理政策修改皆須後續明確裁示。

## 1. 五項優化：採納方向、既有資產與實作 Gate

| 編號 | 優化 | 採納方向／重用與限制 | 決策 Gate |
|---|---|---|---|
| O1 | 跨頁共用 UI 元件／狀態呈現 | **先重用再抽取**：現有 `ui_v3/viewmodels/components.py`（StatusChip／MetricCard／MissingItem）、`ui_v3/design/theme.py`（card_css／tone_css）、`shared/ui_semantics/rules.py`（唯一正式字樣來源）；盤點 🌍 頁的 chip／卡片／CSS 是否真有重複。**不直接新建第二套規則表或 CSS；不在 Batch 1 偷加 `ui_v3/components/`。** | 確有兩頁共通、且實作授權／測試範圍明確時，才考慮最小抽取；不可發明「⬜ 資料未取得」當通用核准字樣 |
| O2 | Fixture Matrix | 💼 可見切片的四個**最低情境**：① TWD＋USD 多幣別原幣事實（不跨幣別合計）；② 來源成功完整但有效列為空的 (c)（不假稱取數失敗、資產歸零）；③ FX Gate blocked（不開 FX、不畫假數值）；④ 局部 Missing（例如 NAV／配息／1Y 含息輸出欠缺，其他合法事實仍可見）。此外保留「根本未取得、取數失敗、部分略過／衝突」的反例。 | 只用 fake／fixture、標示 FAKE；不得由 fixture 推導或宣稱正式資料、金融公式與真實覆蓋；缺值來源與字樣仍受既有 Decision Gate |
| O3 | 自動化＋真機／Cloud DoD | **每個已授權可見切片**做 Playwright／headless 390×844，並對照 768／1280 尺寸，檢查水平溢出、入口可達、內容不遮擋、首屏已核准計數口徑、AppTest／fixture；同一最後 head 的 CI／獨立 QA。**首次有合格隔離 Preview URL 或重大版面改動**再做使用者手機實際滑動、點擊、展開及遮擋觀察。 | CI screenshot ≠ Cloud／真機；沒有合格部署環境時寫 NOT VERIFIED，不設「每兩個純文件／VM batch 都必須部署」的假硬門檻 |
| O4 | OneBrain 介面預留 | 先在版面**設計層**預留可收合的 AI 洞察／反證空間，尊重既有 `docs/v2/80` 的 AI boundary 與 `ui_v3/viewmodels/action_slot.py`。**不新增 `ai_summary_stub` 正式 VM 欄位、不顯示假的 AI 結果／信心、不註冊 ai 頁、不引入 Provider。** | D2 → Evidence／Digest → OB-B Fake Provider → Shadow → 評估 → Phase 7 各自另行核准；何時新增 typed interface 由正式 Digest Gate 決定 |
| O5 | HANDOFF SHA 更新循環 | **提前做治理決策，不順手改治理規則**。客戶治理 `DEC-2026-10-16-12`、`PROJECT_RULES.md` §6.1.2 等既有條款仍要求 HANDOFF 以已核實 main SHA 作 checkpoint。比較 A 每 merge 新 PR（循環）、**B 保留上次已驗證 SHA＋驗證時間／PR 錨點，而「即時 main」唯獨以 GitHub 查詢為準（推薦候選）**、C 自動化 workflow（權限／成本高）。 | 若正式選 B，需先由客戶裁示上位義務的**適用方式**，再依規範更新 `PROJECT_RULES.md`／HANDOFF 與必要 DEC；**不可直接取消 SHA 或聲稱已豁免** |

## 2. 後續實施順序：最多三項／Batch，完整驗收才算結案

### Batch 1｜最小 UI Decision Gates 與重用核查（**候選，尚非施工授權**）

1. **首屏計數**：A10 入口、原因句、SPEC、限制是否占 `≤5` 的預算；列 DOM／視覺計數與 390px 影響；未裁前不把「排除後＝5」宣稱通過。
2. **空持倉 (c) 與 FX blocked**：來源完整但無有效列 ≠ 未取數／失敗，也不等於計算口徑未核准。決定缺資料原因分類、來源狀態、A50 入口與市值基準遭封鎖時已驗證的原幣事實能否顯示；`assets_source.py` 暫 blocked，不能為 UI 偷開 FX。任何正式語意／門檻仍要客戶裁示。
3. **共用元件 + 治理最小稽核包**：唯讀盤點現有共用 primitive 實作和重用可行性；列 HANDOFF SHA 循環三方案與最小規範變更範圍；分別標出需要新 code／治理 Gate 的切片。不得在這一項順手施工 `ui_v3/components` 或改 `PROJECT_RULES.md`。

每批先確認 GitHub main／Open PR／CI／獨立 QA 與正式 DEC，針對以上三項提出一份精確裁示卡，**不得重做已合併 #1246～#1250**。

### Batch 2｜第一個可見 💼 Preview（**收到明確 renderer／視覺施工授權後才做**）

1. **頁級 renderer／隔離注入**：重用 #1248 S-VM，限 fake fixture、無正式 L2 接線、不改未授權 registry、不將 Preview 偽裝 production；已有元件重用優先，新抽取需獨立範圍與測試。
2. **Fixture Matrix**：O2 四情境及取數失敗／部分來源缺漏的 fail-closed 反例；不得偷補 `0`、跨幣別金額、百分比、風險判斷、含息績效或未核准 AI 行動。
3. **可見 DoD**：390×844 等 viewport 的 Playwright／AppTest＋視覺證據、無水平溢出、首屏 CTA、獨立 QA、latest head CI；若有可安全部署的隔離 Preview，再做手機真機體感驗收並如實標明環境。只完成 VM 或 screenshot 不能宣稱正式 Cloud 驗收。

### Batch 3｜後續頁面與資料契約，視 Gate 分流

- D2 剩餘 13 列按 UI 依賴逐批核可；保留 R-NAV-3、幣別／日期／Provider 出處及公式 Gate。
- 依資料健康／授權準備程度，選擇 ⚙️ 或 🔍 下個安全可見切片；S2-T0 暫緩需新裁示才可重啟。
- OneBrain 保持 Data → Deterministic Rules → Evidence → Digest → OneBrain 的單一推理核心方向；資料完備、狀態覆蓋與反證不可為省 Token 靜默遺漏。

## 3. 每批防返工／完成定義（DoD）

- 開工前：GitHub-first（main、Open/Draft PR、head/base SHA、diff、CI、review、BACKLOG／DEC／HANDOFF）、查已授權範圍、判斷撞檔與未結 MUST-FIX。
- 執行中：**每批最多 3 項**；已解決的 bug／Gate 不因換對話而重新開案；新需求先記候選，不擠掉本批 MUST-FIX；任何新金融語意、正式 UI 元件／renderer、治理規則、schema、FX、API 都另走 Decision Gate。
- 結案：同一**最終 head**的非作者 QA 與 CI（Fast／Schema／Slow／Visual 逐一查）；測試範圍、fixture vs Cloud vs 真機分別記錄；未通過不宣稱 MERGE-READY；如需合併須按既有合併授權辦理；完成後核實 main CI；HANDOFF 只當導航，PR／CI 才是完成證據。
- 可回滾：每個切片獨立 branch／PR，明示回滾範圍；正式資料、交易、寫入與 AI runtime 未獲授權均不碰。
- Token／額度：默認靜默自主巡航；重要決策比較至少 A／B／C（正確性、速度、Token／費用）；少量精確讀檔，不全文掃描多次；額度接近耗盡就先 GitHub Save Gate，附 Model／Mode／Effort 的零記憶接手提示語。

## 4. 對話中斷／零記憶恢復指令（供下一個 Claude Code 或 ChatGPT 使用）

1. Repo：`linchen-20200325/my-Fund-dashboard`；先核實最新 main／Open PR／head／diff／CI／QA／branch。**不要照抄本檔觀測 SHA**。
2. 順序閱讀：`CLAUDE.md` → `PROJECT_RULES.md` → `docs/HANDOFF.md` → `docs/BACKLOG.md` → `docs/DECISIONS.md` 相關最新段落；再讀本檔以及 44／67／75／79／80／82 的必要條款（只讀相關節）。
3. 本檔的五項 O1～O5 是**下一階段規劃／防返工方向**。不要將 O1 建 components、O4 建 AI schema、O5 改治理規則視為已批准施工。
4. 正在進行中的 PR 優先完成原 scope 的 QA／CI／結案；不因本檔存在就中斷施工。若本檔仍在 Draft PR，先讀 Draft PR 的最新 head；**PR 存在 ≠ 文件已入 main**。
5. 下一個唯一安全動作：**核實 GitHub 實況與已授權工作，再產出 Batch 1 三題最小 Gate 裁示卡**；在客戶核准其正式語意與施工 scope 前不開新的 renderer／Provider／資料接線。
6. 交接輸出應包含：完成 vs Pending vs BLOCKED、PR／CI／QA 證據、真正 Stop Gate、下一唯一動作、建議 Model／Mode／Effort（例如 Claude Code／GitHub-first 靜默自主巡航／Medium；涉及金融語意時 High）。

**出處與限制**：依 2026-11-15 使用者提供「五項具體優化點」與後續「好，請記得存檔進 GITHUB」之意思記錄規劃方向。不是完整逐字裁示，也未自動核准變更正式 SSOT。須由非作者 QA 核查引用與禁碰邊界，並以最新 exact-head CI 驗證後才可依治理合併。
