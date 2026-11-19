# 未結案工作完整盤點（唯讀；2026-11-19）

> **檔頭註記（落檔時補）**：單組盤點員產出，**未經第二組獨立複驗**；全稱句與機械統計未逐列核實；其中「建議的唯一新對話接手點」為推論【I】，非授權。本檔為 2026-11-19 的盤點快照，落檔時 `#1287` 已合併（main `da000022`），下方凡寫「#1287 open／僅在 #1287」處為撰寫時狀態。
> **落檔時回查（單組，main `da000022`；非窮舉）**：X1 `services/ai_prompts.py` 仍含「該減碼」與「25%+」字樣（已確認）；X2 BL-0217 內冬令窗口約 2026-11-24（上限約 11-26）字樣（已確認；「無人負責」＝repo 無具名承接人，其餘**未能確認**）；X3 HANDOFF §2 與 BL-0491 舊句（已確認）；X4(a)(d)(e) 已確認、(b) 未重查、**(c) 已失效**（#1287 合併後 #1286 卡檔頭已標「已由 v2 取代作廢原 A1a」）；X5～X9、X11 引自 repo 文字，未逐項重查；X10 分支現況：`docs-gate-v2-1119` 已隨 #1287 合併，遠端另有 `ccr-docs-assets-d2-2026-11-14`、`ccr-edfff0d2-q7vs0q`、`push-assets`、`data`、`probe/*`，ahead／behind 數字**未重查**；X12 BL-0537 仍為「未建置」，單組 `ls tests` 未見對應守衛檔（非窮舉）。

> 盤點員：唯讀，未改 repo／未 push／未開 PR・issue・comment／未讀 secrets。單組、未經第二組複驗。
> 基準（GitHub 實查，2026-11-19）：main `eb08c5fc`（#1286 merge；其 push CI 「PR Check」run 2026-11-19T15:26Z = success，只代表 CI 綠、不是驗收）。Open PR 僅 **#1287**（`docs-gate-v2-1119`，head `bf9ba122`，+1 commit、behind 0；Fast／Schema／Visual success，**Slow in_progress**；reviews 0）。Open Issue 僅 **#1228**（無 assignee）；#1278 為 CLOSED 的 ARCHIVE（不派工）。近 100 筆 closed PR 中 **0 筆「關閉未合併」**。
> 標記：【F】repo／GitHub 可查證；【I】推論；「未能確認」＝本組查不到。
> 來源讀取：`docs/BACKLOG.md`（512 列；機械統計）、`docs/HANDOFF.md`、`docs/DECISIONS.md`（DEC-2026-11-14～11-19-10）、`docs/evidence/` 11-17～11-19 各 Gate 卡、GitHub PR／branch／issue／actions。
> **通則【F】**：所有 11-17 之後的客戶裁示（DEC-2026-11-17-05、11-18-01～-04、11-19-01～-10）皆載明「客戶經 ChatGPT 轉達〔待核〕、非逐字、repo 無逐字存檔」；每筆「不授權施工」。因此下表「下一步」多半是**客戶（經 ChatGPT）須先核准某 Gate**，不是執行組可直接開工。
> 負責者慣例【F】（DEC-2026-11-07-04）：決策＝客戶；產品／UI／語意／契約＝ChatGPT 總管；施工與非作者 QA＝專案 AI（Claude Code）。除 #1228 外，沒有任何 BL 登記具名個人負責者 → 以下「無負責者」＝repo 未指定具名承接人（只有角色）。

---

## 總覽（數字，【F】腳本統計，BACKLOG 狀態欄；機械分類未逐列核實）
| 狀態 | 列數 | 說明 |
|---|---|---|
| open | 312＋少數混合態 | 其中 ~260 筆為 2026-10-27 之前登記的舊債（見附錄 A，只列 ID） |
| 待客戶裁示 | 79（另有數筆 Decision Gate 候選混合態） | |
| deferred | 50 | |
| 待確認 | 35 | |
| blocked | 10 | 0019 0201 0251 0313 0386 0387 0388 0389 0480 0481 |
| fixed 待稽核 | 1 | BL-0411 |
| in progress／進行中 | 3 | BL-0536、BL-0520、BL-0521（BL-0549 進行中但已 FAIL，見異常） |
> 注意【F】：BACKLOG 快速索引自陳「〈待客戶裁示〉〈blocked〉〈待確認〉彙總未隨後續批次完整同步，僅供參考」。故上表以「各列狀態格」為準。

---

## A　UI 主線（市場頁、💼、🔍、⚙️、🤖；Gate-M／Gate-D／M-2／S-AST-M1）

五頁現況【F，`ui_v3/shell/registry.py` 讀碼＋HANDOFF】：僅 🌍 `registered=True`（Preview-only，非正式入口）；💼／🔍／⚙️ `registered=False`（`REASON_WIREFRAME_PENDING`）；🤖 `registered=False`＋建構時強制 `REASON_PHASE7`。`poc/` 有 5 個隔離 FAKE：`assets_fixture_preview`、`fund_search_fixture_preview`、`fund_lookup_component_preview`、`nas_diag_preview`、`dual_theme_isolated`。

| # | 項目（編號） | 負責者 | 最新狀態＋證據 | 未完成功能／驗收標準 | 受「UI＋OneBrain 主線優先」影響 | 下一個具體動作／解阻條件 |
|---|---|---|---|---|---|---|
| A1 | 🌍 市場頁 BL-0536／BL-0544／BL-0516～0518 | 無負責者 | 🌍 Preview rendering 等已合併（#1124～#1136、#1164…）；BL-0544 S1 #1164 已 merged；fixture 層 PASS，Cloud 390／1280、真機、WebView、讀屏、非作者最後 head QA **NOT VERIFIED／NOT RUN**（`docs/evidence/bl0544_acceptance_audit_2026_11_17.md`；BACKLOG BL-0544 列） | 正式 Cloud／真機視覺驗收；BL-0539 closed；BL-0369 `◷` 不是最新（open）；BL-0532 Missing 語彙統一為「◇ 資料未備」（open，未動工） | **是**（主線頁；任何 Shell／守衛改動會碰到它） | 使用者提供 Cloud 實機證據→唯讀驗收（區分 PASS／NOT VERIFIED／NOT RUN）。BL-0532 須客戶「開實作批」 |
| A2 | 💼 S-AST-M1（C 線；BL-0536／BL-0542；DEC-2026-11-19-09） | 無負責者（專案 AI 待指派） | 原 Gate 卡已在 main（#1286，`c_assets_s_ast_m1_gate_card_2026_11_19.md`，**含已作廢的 A1a 固定⑤**）；v2 Gate 僅在 **#1287**（`c_assets_s_ast_m1_gate_v2_2026_11_19.md`，單組草稿，未稽核）。DEC-09 方向為轉述〔待核〕，不核准字樣、不授權施工 | v2：改固定情境③（作者推薦【R】，非客戶核准）；新增 `PageSlot.data_mode`、nav/chrome 標記、`app_preview._render_ast`；**需調整 ≥8 條守衛**（v2 §c：突變實跑僅 2 條轉紅，其餘 6 條為讀碼推論未執行）；Chromium 五格量測**未實測**；標記字樣（FAKE／示範）未核准 | **是**（直接動 registry／守衛／nav） | ① #1287 合併（需 Slow 綠＋獨立稽核）→ ② 客戶核准 v2 §g 清單（情境、字樣、S-a(7) 例外形狀、Shell 呈現落差）→ ③ 才可開程式 PR；Model／Effort Change Gate |
| A3 | 💼 資產頁其餘：BL-0542 G-1～G-5、BL-0534（44 `pay_date` amendment）、BL-0420／0427／0428／0524（SSOT／公式 Gate）、BL-0522 | 無負責者 | G-1 方案 C＋S2-Lite 方向已核准（DEC-2026-11-04-03，僅授權 G1-① Golden Baseline）；G-2～G-5 仍待；BL-0534 amendment 文字未起草；A50／A60 僅 FAKE（DEC-2026-11-16-01、-17-01） | 真資料接線、FX、金額、可用列門檻、A51／T6 皆未授權；D8 FX 閘門維持關閉（見 C5） | **是** | 客戶逐題裁示；先起草 BL-0534 最小 amendment 文字（送客戶）。公式類不得自行改 |
| A4 | 🔍 找基金：BL-0553／BL-0554（Gate-M）／BL-0557／C 線 G-A（DEC-2026-11-19-03／-04） | 無負責者 | 離線 FAKE 預覽（`poc/fund_search_fixture_preview`，#1267／#1268／#1270）＋單檔元件（`poc/fund_lookup_component_preview`，#1279）已合併；**客戶（轉述）選 G-A：不搬模組、不改守衛、不新增正式頁**；S2-T0 暫緩（DEC-2026-11-14-08）；`ALLOWED_PREFIX`（`tests/poc_fund_search_preview/test_fund_search_guards.py`）純加法須客戶明文准 | 正式頁掛載（Gate-M）、真資料（Gate-D＋BL-0551）、frozen 44 Amendment P1～P4 逐字註記（EX-AM，須獨立 QA＋正式 DEC） | **是** | 目前無切片可動（G-A）。解阻＝客戶開 Gate-M 逐頁 Gate（M-2：P1／S-a，DEC-2026-11-19-01）；排序建議 🔍→⚙️→💼【R】 |
| A5 | Gate-D 路徑 B 單檔查詢契約（BL-0555；DEC-2026-11-19-02／-05／-06；evidence `gate_d_path_b_min_contract_scope_2026_11_19.md` 等） | 無負責者 | 方向已核准（轉述）；A1／A2／A3／A6／A7／A8 為候選逐字條款、A4／A5 僅方向；Q5-B 暫行；組合後五欄契約**仍須再過最小 Decision Gate** | Pending：A4 佔位字歸屬、G1 頁面例外、G4 標記名稱字樣、Q4 O1／O2、Q6、配息值域；真取數須 BL-0551＋客戶核准 | **是** | 客戶一次逐字核准五欄契約文字（不等於核准 Schema／Provider／L1／L2／接線）；另待 Q0（A 線 Gate 通過定義）、Q3、Q8～Q11 |
| A6 | ⚙️ 設定／診斷 BL-0550（NAS 中繼站診斷）、BL-0489（設定頁批次 6）、BL-0483（頁序）、BL-0402、BL-0392 | 無負責者 | 離線 FAKE Preview 已合併（`poc/nas_diag_preview`；**無核准線框**「未查到」，M-2 卡 §7）；BL-0550 N1～N9 待客戶；`registered=False` | 真實探測（目標／timeout／頻率／授權）；Google 登入／Sheet 切換（BL-0402 客戶痛點「不知怎麼登入 Google」仍 open）；設定頁頁序仍舊序（BL-0483） | **是** | 客戶裁 BL-0550 九項；⚙️ 掛載須 M-2 逐頁 Gate |
| A7 | 🤖 AI 投資總結（Phase 7／BL-0527／BL-0495／BL-0496） | 無負責者 | **無核准線框**【F，five_page_status】；`registry.py` 建構時擋 `ai` registered；Phase 7 前不得掛（DEC-2026-10-29-07） | Risk Cap 正式定義、減碼 deterministic trigger（均 repo 未定義）；Digest 契約 N1～N5 | **是（屬 B 線交界）** | 不可進；見 B |
| A8 | Gate-M／M-2 政策（BL-0554；DEC-2026-11-19-01） | 無負責者 | P1（逐頁獨立 Gate、預設不掛載）＋S-a 暫行為轉述；**導覽層 FAKE 辨識（S-b／S-c）、FAKE 最終字樣、各頁 Gate 啟動時機皆未裁** | 掛載 PR 與搬模組 PR 分開；回滾＝revert 單一 commit | **是** | 客戶回答 M-2 卡 Q1／Q2 之外的 (b)(c)(d)（DEC-01 待確認欄）；Gate-M 與 S2-T0 分開（DEC-2026-11-19-04，轉述） |
| A9 | New UI2 cutover 守衛 BL-0535、Old UI 凍結機械守衛 BL-0537、BL-0538／0541（Latest-Rule-Only） | 無負責者 | BL-0535 cutover 後守衛「仍無法存在」；BL-0537 待客戶裁示（未建置）；BL-0538／0541 待客戶確認讀法（位階張力） | cutover 時正式入口不暴露 Old UI／`ui_v2` 的測試＋Cloud 設定紀錄 | **是**（cutover 前置） | BL-0537：客戶裁示要不要建；BL-0538：客戶確認讀法，否則 BL-0541 不動 |

---

## B　OneBrain（OB-B、D2、Digest、Risk Cap、Phase 7）

| # | 項目 | 負責者 | 最新狀態＋證據 | 未完成／驗收標準 | 受主線影響 | 下一步／解阻 |
|---|---|---|---|---|---|---|
| B1 | OB-B 離線 Typed Interface／Fake Provider（`DEC-2026-11-18-03`；DEC-2026-11-19-10；`obb_bc_gate_and_offline_application_2026_11_19.md`） | 無負責者 | **BLOCKED**：DEC-18-03 自設條件＝客戶本人以可存檔文字確認 (a)(b)(c)(c′)(c″)＋本 DEC 落 main＋獨立治理稽核 Must-Fix 清零，才可開程式 PR；DEC-19-10 為又一則轉述，**不能當作 (a)(b)(c) 的客戶確認**【F，該卡 §0】 | 7 檔白名單離線型別／Fake／注入測試（草稿 §3）；不碰 Digest、正式 Provider、LLM runtime | **是** | 客戶以可存檔文字確認 §2-D（或改寫版）→ 總管／使用者核准施工申請 → Model／Effort 確認 |
| B2 | D2 逐域契約（BL-0420 系、`DEC-2026-11-13-06`、`-14-07`、`-17-06`、DEC-2026-11-19-10；`d2_next_domain_gate_card`、`d2_s7_suffix_identity_gate_2026_11_19.md`〔後者僅在 #1287〕） | 無負責者 | 正式核准欄位僅 R-ID-1／R-NAV-1／-2／-4／-5（-3 暫緩）；客戶（轉述）選 Q-ID **方案 1＝先釐清 S7（取數用代碼可否帶通路後綴）**；S7 卡為單組草稿尚待稽核 | S7 一題；R-ID-2／3 與 D2 其餘 ~12 列（R-PERF-1～8 等）；其餘六域延後。D2 未完成 Digest 不可啟動（D2-G2＝A） | **是** | 客戶答 S7（推薦：取數用代碼只收基本代碼，但屬 R-ID-1 之外的新增推廣，須明確接受）；**注意**：S7 若選「禁止」是行為變更＋identity Stop Gate，非純契約題 |
| B3 | Digest（BL-0527；`bl0527_digest_precontract_2026_11_18.md`；`onebrain_digest_decision_pack_2026_11_18.md`） | 無負責者 | open；N1～N5 待客戶；as_of／stale／rule_version 無 repo 定義；AI 不讀畫面、輸出不回寫 canonical 的守衛 repo 查無（Phase 7 實作批前補） | Digest schema Gate（須 D2 後）、O-D3b＋O-D7a～e（stale_after／conflict／NAV 10 日／PIT）為最前阻擋 | **是** | 客戶先裁 O-D3b／O-D7（`open_decisions_ledger` §0.2 名次 1） |
| B4 | Risk Cap／減碼 trigger（BL-0495、BL-0496） | 無負責者 | 待客戶裁示；repo 內無定義 | 屬 investment meaning；`DEC-2026-10-27-22`：trigger 未定前 AI 不得決定減碼 | 是（延後，路由文件：不阻擋 C 路線） | 客戶 Decision Gate；不得發明 threshold |
| B5 | OneBrain 後續階段（BL-0529、BL-0490；DEC-2026-10-31-03） | 無負責者 | deferred；僅 Phase A 文件；`docs/v2/79` UI-7、UI-14 為輸入 | fake provider→shadow→整合→評估→production，每階段另裁 | 是 | 無（不得動） |
| B6 | BL-0521／0520／0519／0522／0523（DG-2 canonical identity、Cross-View） | 無負責者 | BL-0521 in progress：Stage-1 shadow 已落地（`shared/fund_identity.py`，`DG2_SHADOW_ENABLED=False`）；BL-0520 特徵化測試已落地、待稽核合併；BL-0519／0522 待客戶 | DG-2 contract、第二條 NAV 路徑收斂、AI 快照指紋 | 可能（與 D2 identity／Digest 輸入重疊） | 不得升格 DG2（DEC-2026-11-19-10 明文） |
| B7 | BL-0528 的 OneBrain 關係（A 線 AI 與 OneBrain「唯一動作權威」張力） | — | 見 C1 | — | 見 C1 | — |

---

## C　其他（平行修復）

| # | 項目 | 負責者 | 最新狀態＋證據 | 未完成／驗收標準 | 受主線影響 | 下一步／解阻 |
|---|---|---|---|---|---|---|
| C1 | **BL-0528**（Old UI AI 輸出與 DEC-2026-10-27-14／-22／-40 牴觸；MCP `build_macro_snapshot` 舊行動欄位） | 無負責者 | 待客戶裁示；**main 現碼仍牴觸**【F，本組 grep `services/ai_prompts.py`：仍有「列出 2-3 檔該減碼」「明確要求提高現金比例至 25%+」】。Gate：`bl0528_prompt_fix_gate_2026_11_19.md`（#1287 內）＋`bl0528_g3a_mcp_compat_2026_11_19.md`（G3a 結論**無法確認**）＋`bl0528_min_fix_gate_card`（main）。DEC-2026-11-19-08（方案 B 方向，轉述） | 只處理 Prompt (1)（`ai_service.py::analyze_portfolio_mk_advisor`／`ai_prompts.py::build_mk_advisor_prompt`）；MCP (2) 因 G3a 擱置、G3b 另案；§8 十項待核（含超出 P-1 字面的刪除項、揭露字樣、**是否違反「不得修改線上正常運作舊版 Tab」** 之 DEC-2026-11-01-02 G-E7） | **可能**（改動 Old UI 輸出；與 UI 主線檔案無交集，但與 BL-0537 缺機械守衛有關） | 客戶核准 Gate §8 最小差異＋Change Gate（Opus／Plan／High 或另定）→ 專案 AI 施工（白名單：`ai_prompts.py`、`ai_service.py`、`tests/test_ai_prompts.py` 等；MCP 檔不碰）→ 獨立稽核 |
| C2 | BL-0545 真實覆蓋率（全域 NEXT 名義） | 無負責者（使用者暫不提供輸入） | BLOCKED；`DEC-2026-11-12-02` 維持暫停；Phase 1 離線探針 `scripts/bl0545_coverage_probe.py` 已合併（#1168）；live NOT IMPLEMENTED | 需方式 A（本人合法 Google session）或 B（匿名代碼清單）；真實覆蓋率 NOT VERIFIED | 否（與主線無衝突；但佔著「唯一 NEXT」名義） | 使用者提供合法輸入。**見異常 X3** |
| C3 | BL-0551 TLS／NAS 安全（A 線） | 無負責者；持有人**尚未指定**（DEC-2026-11-19-07） | BLOCKED：客戶選 G1-1（僅 G0 最小證據包，限使用者指定持有人自行操作）；D4／D8 不得啟動；執行組不探測／不索取帳密 | G0 證據 D1～D5（Squid 版本、攔截與否、流量分類、原站憑證比對、埠開放）；G2 白名單過渡不得當終態；G3 翻轉預設 | **是**（阻擋所有真實取數＝Gate-D） | 使用者**指定持有人與書面記錄形式** |
| C4 | BL-0548／0547／0546／0524／0420／0427／0428（公式、1Y 窗口、缺值補 0 的 Gate 候選） | 無負責者 | 全部「待客戶裁示（Decision Gate 候選）」；BL-0547：`calc_metrics` 直讀 raw `ret_1y_total` 繞 350 天閘門；BL-0546：舊 UI／MCP 缺值被補 0、「中性／HOLD」 | 不得改公式／門檻／重錄 Golden | 可能（New UI2 接 1Y 績效前須先裁） | 客戶逐點裁示 |
| C5 | BL-0217 FX 閘門（D8；`FX_OBS_DATE_RULE_VERIFIED=False`） | 無負責者 | 客戶 2026-11-08 裁示：維持關閉、不以相同方法重跑（DEC-2026-11-08-02）；冬令探測 run 42455423910 證據不足；補證表 M1-b 是否算「相同方法」待判 | **有到期日**：冬令窗約 2026-11-02～11-24（上限 ~11-26），錯過等明年 3 月 | 是（阻擋 💼 非 TWD 市值、MKT-3） | 見異常 X2 |
| C6 | BL-0549／#1228 品質補強（Batch 1～3） | **無 assignee** | BL-0549 PR-1 #1231、PR-2 已合併；A/B 量測＝無節省證據；零記憶驗收整體 **FAIL**；`DEC-2026-11-13-05` 已裁 (i)～(vi)；Issue #1228 仍 open，作者評論「不得標全完成」 | 失敗歸因（ZM-01／02／05／06b）未做；#1228 未結 | 否 | 客戶決定是否結 #1228；歸因屬唯讀 |
| C7 | 資料來源／狀態管理：BL-0509（TWSE／MOPS 多日 probe 排程啟用）、BL-0501／0504（EPS／財報 Data Source Gate）、BL-0480／0481（blocked：待客戶教材與公式來源）、BL-0530（ISIN research-only）、BL-0392／0402／0333（Google 登入／Sheet 切換／OAuth）、`secrets_recovery_verification_2026_11_10.md`（Cloud Secrets 恢復 **NOT VERIFIED**） | 無負責者 | probe workflows 仍 active 並於 11-18／11-19 成功執行【F，actions】；新來源一律 Decision Gate | 新資料源核准、Cloud secrets 恢復驗證 | 可能（MKT 趨勢圖與 💼 資料依賴） | 客戶／持有人提供事實 |
| C8 | 舊 UI（Old UI／`ui_v2`）：BL-0537、BL-0532、BL-0483、BL-0411（fixed 待稽核）、BL-0342／0453（Py3.13 黃金檔）、BL-0446 系 | 無負責者 | Old UI「不修改」、`ui_v2` maintenance-only 為永久規則，**無機械守衛**；BL-0342／0453：`tests/ui_v2` 在 3.13 本機紅、CI（3.11）綠，root cause 未查 | 見各列 | 可能（改 Shell／守衛可能波及 ui_v2；Golden 不可重錄） | BL-0411：補獨立稽核證據；BL-0342／0453 僅在證明影響 production／CI 時派工 |
| C9 | 技術債／文件治理：BL-0543（清理線剩餘範圍是否結案）、BL-0541（Latest-Rule-Only 第二階段）、BL-0538、BL-0552（Pending 收斂）、BL-0556、BL-0557（12 題待客戶）、舊債 ~260 open | 無負責者 | 見附錄 A；BL-0557＋`open_decisions_ledger_2026_11_18.md`（68 KB，單組、待稽核）為最新待裁基準 | — | 否～可能 | 客戶一次確認 RE1（`DEC-2026-11-18-01`／`-02` 確為本人裁示）可一次消除一批列的來源不確定；**未能確認已完成**（DECISIONS／HANDOFF 內查無 RE1 結案紀錄） |
| C10 | 安全修復 | — | 本組在 BACKLOG／HANDOFF 內**未發現**獨立「待修的安全漏洞」列；安全相關僅 C3（TLS）、C1（AI 行動邊界）、secrets 恢復 | — | — | 未能確認（未做安全稽核） |
| C11 | #1287 本身（三線 Gate 整合＋DEC-2026-11-19-08～-10） | 無負責者（作者＝執行組） | open，head `bf9ba122`；CI：Fast／Schema／Visual success、**Slow in_progress**；無 review；DEC 為轉述〔待核〕；DEC 條文需 PR 階段治理稽核 | 合併前須獨立治理稽核＋Slow 綠 | 是（承載 v2 Gate 與三筆 DEC） | 等 Slow、做稽核、再合併（Auto-Ship 條件不可省） |

---

## 異常項目（共 12 項）

| # | 類別 | 內容 | 證據 |
|---|---|---|---|
| X1 | 可能功能退化／合規 | **BL-0528 牴觸仍在 production 靜態可達**：prompt 仍要求 AI 列「該減碼」標的並「提高現金比例至 25%+」，與 DEC-2026-10-27-14／-22／-40 牴觸，登記自 2026-10-29 至今 3 週無處置；修法本身要動「線上正常運作的舊版 Tab」（Gate §8 第 9 項待客戶確認）→ 修與不修都有風險 | `services/ai_prompts.py`（本組 grep 命中）；BACKLOG BL-0528；`bl0528_prompt_fix_gate_2026_11_19.md` §0、§8 |
| X2 | 時效／無負責者 | **FX 冬令重跑窗口約 2026-11-24（上限 ~11-26）將關閉**；客戶 11-08 已裁不以相同方法立即重跑，補證是否算「相同方法」待判；窗口一過需等明年 3 月，目前**無人負責判定** | BACKLOG BL-0217（L367）；`docs/evidence/fx_d8_gap_and_supplementary_plan_2026_11_08.md` |
| X3 | 無負責者／文件矛盾 | **「全域唯一 NEXT」BL-0545 實質無人可動**（使用者暫不提供輸入；DEC-2026-11-12-02），HANDOFF §2 仍把它寫成唯一下一接手點；同時 BL-0491 寫「本列是目前唯一的下一個安全動作」（2026-10-27 舊句）。新對話若照 HANDOFF 讀會停在一個被阻擋的點 | HANDOFF §2／§3；BACKLOG BL-0491、BL-0545 |
| X4 | 文件互相矛盾（多處） | (a) HANDOFF 頂部「觀測日期 2026-11-18」，但第一則已是 2026-11-19 第十三次同步；同檔並存 eb08c5fc／e07c6722（11-14）等多個「main 最新觀測基準」；(b) BACKLOG 快速索引自陳彙總「未完整同步」；(c) **💼 A1a**：main 上的 #1286 卡仍寫 A1a（固定⑤），v2 卡（僅在 #1287）說「原 A1a 作廢、不得直接施工」→ 合併 #1287 前 main 上有一張已被作廢卻未標註的 Gate 卡；(d) Gate-M 卡基準寫 main `58652da1`（舊）；(e) HANDOFF 的 `§1 快照` 標「2026-11-07 查到」卻含 11-13 內容 | HANDOFF 頂部與 §1；BACKLOG L59-L71；`c_assets_s_ast_m1_gate_card…`（eb08c5fc）；`gate_m_m2…` 檔頭 |
| X5 | 授權鏈單點 | 11-17-05、11-18-01～-04、11-19-01～-10 **全為轉述〔待核〕**，部分註明「是否客戶本人〔待核〕」；`open_decisions_ledger` 提議的 RE1「一次確認」**查無完成紀錄**；稽核（subagent）原文多半「不在 repo，來源：總管轉述」 | DECISIONS 各 DEC「日期／決策者」欄；HANDOFF 第八～十三次同步；ledger §0.3 |
| X6 | 完成≠驗收（以 CI 綠代替使用者 UI 驗收） | (a) BL-0544／🌍 Preview 已 merged 且 CI 四綠，但 Cloud 390／1280、真機、WebView、非作者最後 head QA **NOT VERIFIED／NOT RUN**；(b) BL-0250 Phase 3 客戶實際使用驗收「待客戶裁示」未見完成，連帶 BL-0251（Phase 4）blocked；(c) #1279（🔍 單檔元件）、nas_diag／assets poc 皆為 FAKE fixture 層 PASS，非使用者驗收；(d) BL-0549 #1231 已 merged 但零記憶驗收 FAIL；(e) BL-0411「fixed（待獨立稽核）」且 DEC-2026-10-30-04 要求 P3 production 前必修，稽核完成證據**未能確認**；(f) #1287 Slow lane 尚未完成 | BACKLOG BL-0544／0250／0251／0411／0549；`bl0544_acceptance_audit_2026_11_17.md`；PR #1287 check-runs |
| X7 | 可能功能退化（新工作會碰到的既有守衛） | 💼 v2 須改 ≥8 條守衛：`registered_pages()` slugs `== ["mkt"]`、`shell_*` 19 鍵限定、`render_navigation` 原始碼斷言、nav CSS 字串斷言…，**僅 2 條實跑轉紅，6 條為推論**；`PageSlot` 新增欄位；🔍 `ALLOWED_PREFIX` 純加法；`ai` 不得 registered 的建構時檢查；Py3.13 黃金檔（BL-0342／0453）不得重錄；BL-0528 改 prompt 會動 `tests/test_ai_prompts.py` | `c_assets_s_ast_m1_gate_v2…` §b／§c；`tests/poc_fund_search_preview/test_fund_search_guards.py`；`ui_v3/shell/registry.py` |
| X8 | 已中止／暫緩（需知悉，勿誤啟動） | S2-T0 暫緩（DEC-2026-11-14-08）；🔍 C 線 G-A 不搬移（DEC-2026-11-19-04）；BL-0545 暫停；D8 FX 維持關閉；B2／B3／`CLAUDE.md` 瘦身未授權（BL-0538 不延伸）；DG2 不得升格；Phase 7／🤖 不得掛；BL-0481／0480 blocked | HANDOFF §2／§3；各 DEC |
| X9 | WIP 可能遺失（未入 repo 的成果） | (a) HANDOFF §3：Context Efficiency A1／A2／A3 研究「未落盤，僅對話交付」；(b) 多筆 subagent 獨立稽核結果「原文不在 repo、來源：總管轉述」（第七～十一次同步）；(c) 客戶原始裁示文字與 ChatGPT 提示語無 repo 存檔；(d) BL-0549 A/B「原始量測檔未入 GitHub」 | HANDOFF §3 GATE 列、第八～十一次同步；Issue #1228 comment |
| X10 | 分支／PR 狀態 | 本組比較結果【F】：`ccr-docs-assets-d2-2026-11-14`、`ccr-edfff0d2-q7vs0q` ahead 0（已併入 main，無 WIP）；`docs-gate-v2-1119` ahead 1＝#1287；**`push-assets` ahead 7／behind 2081，末 commit 2026-10-28（除息月曆）**，與 main 嚴重分岔；`data`（2026-11-19 02:23 每日 fund.db 匯出）與 `probe/*-results`（TWSE 2026-11-19、MoneyDJ NAV 2026-11-18 仍更新）為孤立歷史資料分支。DEC-2026-11-08-01 客戶裁示全部保留、不停 cron、不清分支。未發現「有 unique commits 的未合併 WIP 開發分支」（除 #1287） | GitHub compare／commits API |
| X11 | 無負責者 | 全盤點中僅 Issue #1228 有「Issue」形態且**無 assignee**；BACKLOG 無任何具名承接人；11-19 九張 Gate 卡皆「單組作者、尚待非作者獨立稽核」 | issues API；各卡檔頭 |
| X12 | 缺機械守衛 | Old UI／`ui_v2` 凍結清單無機械守衛（BL-0537）；BL-0528 修 Old UI Tab 時無自動偵測；`bl0528` Gate 自承「docstring 不得碰」為執行組讀法非客戶裁示 | BACKLOG BL-0537；`bl0528_prompt_fix_gate…` §0 |

---

## 建議的唯一新對話接手點
**接手點＝「先讓 #1287 安全合併（等 Slow 綠＋一組獨立治理稽核），再向客戶提出一次『可存檔文字』的合併確認包：RE1（11-18-01／-02 本人確認）＋ 💼 v2 §g ＋ OB-B (a)(b)(c) ＋ D2 S7 ＋ BL-0528 §8；其間不開任何程式 PR。」**
先讀：`docs/HANDOFF.md`（第十三次同步段）→ `docs/DECISIONS.md` 的 `DEC-2026-11-19-08～-10`、`-01`、`-02`、`-05`～`-07` → `docs/evidence/open_decisions_ledger_2026_11_18.md` §0 → `docs/evidence/c_assets_s_ast_m1_gate_v2_2026_11_19.md` §g → `docs/evidence/obb_bc_gate_and_offline_application_2026_11_19.md` §5 → `docs/evidence/bl0528_prompt_fix_gate_2026_11_19.md` §8 → `docs/evidence/d2_s7_suffix_identity_gate_2026_11_19.md` §0。同時重查 GitHub（main SHA、#1287 CI、Open PR）。
【I】理由：UI 與 OneBrain 兩主線目前都被「客戶需親自核准的 Gate」擋住（無可施工切片），且 BL-0545 名義上的 NEXT 被阻擋；因此新對話最有價值的單一動作是收斂並送出核准包，同時提醒 X2（~11-24 FX 窗）與 X1（BL-0528 現況）。此建議為盤點員推論，未獲授權。

---

## 附錄 A　舊債 ID 清單（BACKLOG 狀態欄機械分類，未逐列核實；2026-10-27 前登記居多；不逐列展開）
blocked (10): 0019 0201 0251 0313 0386 0387 0388 0389 0480 0481
deferred (50): 0101 0109 0139 0165 0166 0199 0200 0235 0243 0248 0265 0270 0286 0292 0301 0303 0314 0315 0333 0338 0353 0354 0355 0356 0357 0358 0359 0360 0361 0376 0379 0380 0381 0382 0384 0385 0390 0391 0393 0401 0409 0418 0419 0422 0423 0432 0439 0511 0512 0529
fixed待稽核 (1): 0411
open (312): 0001 0002 0003 0004 0005 0006 0007 0008 0010 0015 0016 0017 0020 0021 0022 0025 0026 0027 0028 0029 0030 0031 0032 0033 0034 0035 0036 0037 0038 0040 0041 0042 0043 0044 0045 0046 0047 0048 0049 0050 0053 0055 0056 0057 0058 0059 0060 0061 0062 0064 0065 0066 0067 0068 0069 0070 0071 0072 0076 0077 0078 0079 0080 0081 0082 0084 0085 0086 0087 0088 0089 0090 0091 0092 0093 0094 0095 0096 0097 0098 0099 0100 0103 0104 0105 0106 0107 0110 0111 0112 0114 0115 0116 0117 0118 0119 0120 0122 0124 0125 0126 0131 0132 0133 0135 0136 0138 0141 0142 0143 0144 0145 0147 0148 0149 0150 0152 0153 0154 0156 0157 0158 0159 0160 0161 0162 0163 0164 0168 0169 0170 0171 0172 0173 0174 0175 0176 0178 0179 0180 0181 0182 0183 0184 0186 0187 0188 0189 0190 0191 0192 0193 0194 0195 0196 0197 0198 0202 0203 0204 0205 0206 0207 0208 0209 0210 0211 0213 0214 0215 0216 0217 0218 0219 0220 0225 0226 0227 0229 0230 0231 0232 0233 0238 0239 0240 0241 0242 0245 0246 0254 0257 0258 0259 0260 0261 0264 0266 0267 0273 0274 0275 0278 0279 0281 0282 0283 0284 0287 0290 0291 0293 0296 0297 0298 0300 0304 0306 0307 0308 0309 0310 0318 0321 0322 0323 0324 0325 0326 0327 0328 0329 0330 0331 0332 0334 0335 0337 0339 0340 0341 0342 0343 0344 0345 0346 0347 0348 0349 0350 0351 0352 0363 0364 0365 0367 0368 0369 0370 0372 0378 0394 0396 0412 0417 0429 0430 0431 0433 0435 0436 0437 0440 0442 0445 0446 0453 0454 0455 0456 0457 0458 0459 0465 0469 0475 0483 0485 0486 0487 0488 0489 0490 0491 0493 0508 0514 0515 0523 0525 0527 0530 0531 0532 0534 0535 0541 0544 0545 0552 0556 0557
other:in progress（new ui2 `ui_v (1): 0536
other:in progress（客戶 2026-10-28 (1): 0520
other:→ **2026-11-18 更新：契約包已交付於 (1): 0555
other:→ **2026-11-18 更新：評估已交付於  (1): 0551
other:→ 方案 a 已由客戶選定（`dec-2026-1 (1): 0553
other:候選，尚未提出（現在不建議問；decision g (1): 0554
other:多日 probe 排程已啟用（累積樣本中） (1): 0509
other:已合併（#1093，`dc0eb59c`）；客戶已 (1): 0518
other:已合併（#1094，`b7b59363`）；殘餘項 (1): 0517
other:批 1 已完成（#1091，`b14f642c`） (1): 0516
other:進行中（pr-1 已合併〔#1231，main ` (1): 0549
待客戶裁示 (79): 0102 0121 0123 0127 0223 0224 0247 0250 0253 0263 0268 0269 0271 0277 0280 0311 0312 0377 0392 0397 0398 0399 0400 0402 0403 0404 0405 0406 0407 0408 0413 0414 0415 0416 0420 0427 0428 0438 0448 0452 0460 0461 0462 0463 0464 0466 0467 0468 0470 0471 0472 0473 0474 0495 0496 0498 0499 0500 0501 0502 0503 0504 0505 0506 0507 0510 0519 0521 0522 0524 0528 0537 0538 0540 0542 0546 0547 0548 0550
待確認 (35): 0012 0013 0014 0018 0023 0024 0051 0052 0054 0075 0083 0108 0128 0129 0130 0134 0137 0140 0151 0155 0167 0237 0255 0256 0262 0288 0294 0295 0305 0319 0320 0336 0395 0410 0543

> 上列 ID 為 BL 編號（略去前綴 BL-）；「open」「待客戶裁示」「待確認」清單由腳本以狀態格關鍵字分類，含少數混合狀態／已劃線列，僅供索引。需逐列核實者請依 BACKLOG 各列。
