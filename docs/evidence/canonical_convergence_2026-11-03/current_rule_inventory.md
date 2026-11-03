# 現行規則盤點（Canonical Rule Convergence，唯讀稽核）

- 量測基準：origin/main `4d8c07dd`（Merge #1131，2026-11-03）；全部以 `git show origin/main:<path>` 讀取，未碰工作樹。
- 位置寫法：章節／DEC／BL 編號／符號名，不寫行號。檔案大小為 2026-11-03 於 `4d8c07dd` 量測（bytes，會漂移）：`docs/DECISIONS.md` 645,676（155 個 `### DEC-`）、`docs/BACKLOG.md` 608,416（568 列 `| BL-`）、`docs/HANDOFF.md` 264,657、`PROJECT_RULES.md` 163,266、`CLAUDE.md`（只讀）、`PROCESS.md` 57,993、`STATE.md` 458,534、`SPEC.md` 139,992、`ARCHITECTURE.md` 108,521。
- 本檔由單組寫成，**未經第二組獨立驗證**；全稱句一律標註（見 f 節）。
- 配套檔：`/tmp/claude-0/-home-user-my-Fund-dashboard/29852a98-88f0-5ee2-99d9-4eecc492bfa0/scratchpad/inventory/current_rule_inventory_guards_and_checks.md`（d 凍結清單、e 機械檢查、f 未查證、g 守衛測試）。
- 狀態代號：CUR＝CURRENT、SUP＝SUPERSEDED、HIST＝HISTORICAL EVIDENCE ONLY、CONF＝CONFLICT-NEEDS-GATE。

## 0. 先講最重要的五個結構性發現

1. **疊層追加式寫法是「現行區混有舊規則」的根因，不是個別漏改。** 全 repo 慣例是「舊條文保留不刪＋刪除線＋就地追加指標」（`CLAUDE.md` §-1.5 體例；`PROJECT_RULES.md` 0.5 Supersession hygiene (1)(2)）。結果：`docs/HANDOFF.md` 檔頭 Resume Checkpoint 疊了 40 則「就地追加」bullet；§2 疊了 24 個「第 N 次現況」框；§3「下一步」仍是 2026-10-16～10-22 Phase 3 B 線驗收時代的文字；`BL-0536` 一列 33,551 bytes。**要達成「只在現行區讀到最新規則」與現行 hygiene (1)(2) 字面衝突，這是需要客戶裁示的真 Gate（見 c 節 G-1）。**
2. **客戶 2026-11-03 新方向多數尚未落進 origin/main**：`此圖目前沒有可畫的資料` 0 命中、`資料健康度` 0 命中、`Chart SPEC` 0 命中、`chart-first` 0 命中、`簡單但不失判讀` 0 命中、「工程資訊不得進一般 UI」無對應現行條文（`traceback`／`module path` 0 命中；`env var` 只在 DECISIONS 兩處且非此意）。🌍 字樣在 main 上全部仍標 PENDING（`docs/v2/81`、`BL-0536`、`HANDOFF`、`ui_v3/viewmodels/preview_wording.py`、守衛 `tests/ui_v3/test_ui_v3_preview_wording_guard.py`）。若另一組正在落地，本檔 b 節 C2／C3／C8 視為「待該批取代」；落地時須同步改上列四處＋守衛測試，否則會自己製造新衝突。
3. **`HANDOFF` 的 live「唯一下一接手點」已過期**：檔頭第一則仍寫「BL-0536 🌍 Preview rendering…commit 未推送、PR 待總管開…唯一下一接手點＝獨立稽核→PR→CI→合併」，但 main 已是 Merge #1131；`HANDOFF`／`BACKLOG`／`DECISIONS` 全文 `#1131` 0 命中。`BL-0536` 狀態欄也寫「批 2a／2b…同一 PR 待開」。
4. **`PROJECT_RULES.md` 13.2 第 1 點仍以現行口吻寫舊五頁**：「🌍 市場與趨勢、⚖️ 資產配置、💼 我的持股、🔍 找基金、⚙️ 設定」，只靠句尾兩個指標（2026-10-27、2026-10-29）更正；正式 IA 已是 🌍／💼 我的資產／🔍／🤖／⚙️（`DEC-2026-10-29-06`、`DEC-2026-10-29-07`、`docs/v2/79`、`docs/v2/80`、`ui_v3` 頁序守衛）。
5. **同一規則多處成文**：HANDOFF §0 第 6～10 點（1384／430／690／923／458 bytes）各自重述 Silent Cruise、Context Efficiency、接手檢查、UI 暴露檢查、方案比較檢查，與 `PROJECT_RULES` 3.2／11.1／5.1／13.2／9.2 平行成文——第二套 SSOT 風險。

---

## (a) 規則清單表（依議題）

### 議題 1｜五頁 IA 與頁名

| 規則摘要 | 所在位置 | 狀態 | 建議動作 | 建議唯一 SSOT |
|---|---|---|---|---|
| 現行 IA＝🌍 市場與趨勢／💼 我的資產／🔍 找基金／🤖 AI 投資總結（Phase 7 前不掛導覽）／⚙️ 設定；資產配置併入💼為頁內區段；不得第六頁 | `DEC-2026-10-29-06`（Gate 1 A）、`DEC-2026-10-29-07`（BL-0526 C）、`docs/v2/44` 之二十、`docs/v2/79` §9／頁序、`docs/v2/80` §7、`ui_v3/shell/registry.py` | CUR | 保留；選定一處為頁名／頁序正文 | **`PROJECT_RULES.md` 13.2 第 1 點改寫為「現行五頁＋職責」並指向 `DEC-2026-10-29-06`／`docs/v2/80` §7**；頁內規格由各頁 wireframe 承接 |
| 舊五頁（🌍／⚖️ 資產配置／💼 我的持股／🔍／⚙️） | `PROJECT_RULES.md` 13.2 第 1 點本文；`DEC-2026-10-27-02`；`DEC-2026-10-24-02` 頁序；`docs/v2/44` 第 2、3 節表頭（95 處「資產配置」）；`STATE.md`、`SPEC.md`、`ARCHITECTURE.md` | SUP（頁名與頁數）／HIST | 13.2 本文改現行；其餘凍結檔不動本文，走合法標示（見 d） | 同上 |
| 「不輕易增第六頁」（客戶原字非絕對禁止）與 `docs/v2/80`「不得新增第六頁」 | `DEC-2026-10-26-01` (1)；`PROJECT_RULES.md` 13.2 提示；`docs/v2/79`、`80` | CUR（措辭兩版） | 統一為客戶原字「不因單一新功能輕易增加第六頁」；「不得新增」標為執行組讀法 | 13.2 第 1 點 |
| 「設定與診斷」頁名 | `docs/v2/44`（85 處）、`docs/v2/65`、`STATE.md` | SUP（頁名現為 ⚙️ 設定） | 44 內不改字；在頁名指標表標 successor | 13.2 第 1 點 |

### 議題 2｜Old UI／ui_v2／ui_v3 三層邊界、formal 顯示、cutover、Preview

| 規則摘要 | 所在位置 | 狀態 | 建議動作 | 建議 SSOT |
|---|---|---|---|---|
| 正式 Streamlit 只顯示最新正式 UI；Old UI read-only、`ui_v2` maintenance-only、`ui_v3` 唯一未來正式；Preview 平行驗收；cutover 守衛 BL-0535 | `PROJECT_RULES.md` 13.2「正式 Streamlit 顯示規則」（`DEC-2026-11-02-06`）；`DEC-2026-11-02-02`／`-03`／`-05`／`-06`；`BL-0533`／`BL-0535`／`BL-0537` | CUR | 保留 | **`PROJECT_RULES.md` 13.2「正式 Streamlit 顯示規則」** |
| 「New UI 是唯一正式產品線…Final UI 以既有 New UI 為視覺 baseline」（`DEC-2026-11-02-02`） | `PROJECT_RULES.md` 13.2 已劃線＋指標；`DECISIONS` 該條 | SUP（by `-03`／`-05`） | 13.2 內劃線舊句移歷史區，只留 New UI2 現行句 | 同上 |
| 正式 App 現況推定為 Old UI（Streamlit Cloud 設定 repo 內不可驗） | `HANDOFF` §0 第 9 點 | CUR（含「推定」） | 保留並維持「無法查證」標示 | 13.2 |
| 「cutover 前 PR 不得…把 Old UI 暴露」原句已被更正 | `HANDOFF` §0 第 9 點同行含劃線舊句 | SUP | 劃線舊句移歷史區 | — |
| ui_v2 時期版面規格（72／73／76／78 的 Layout、D1～D12 容器排列、側欄視覺） | 各 wireframe 檔；`DEC-2026-10-30-01`、`-02`、`DEC-2026-10-31-01`／`-02`、`DEC-2026-11-01-02` | **版面＝SUP（NG-5 標明須由 New UI2 wireframe 重新核准；🌍 已重核准，💼／🔍／⚙️ 未）；語意＝CUR** | 每份檔檔頭加「版面僅供 ui_v2 reuse／語意仍有效」索引列；不可只標「已核准」現行口吻 | 各頁現行規格指標表（見 c-G-4） |

### 議題 3｜Missing／proxy／freshness 與 Missing 字樣

| 規則摘要 | 所在位置 | 狀態 | 建議動作 | 建議 SSOT |
|---|---|---|---|---|
| Missing≠0／False／HOLD／中性／正常／安全；顏色不是唯一語意 | `PROJECT_RULES.md` 13.2 第 3 點、第 13 節第 2～4 條、13.1 | CUR | 保留 | 第 13 節 |
| 正式模式 Missing 字樣＝`◇ 資料未備`；示範模式照舊 `⬜ 資料未備` | `DEC-2026-11-02-01`（甲）(四)；`BL-0532`；`shared/ui_semantics/rules.py`；`docs/v2/44` 之七其四／之十九其五第 4 條 | CUR（至 2026-11-03 新字樣裁示落地前）／部分 CONF | 見 b-C2 | 規則表 `shared/ui_semantics/rules.py` ＋ `docs/v2/81` §4 為單一正文 |
| `資料不足`（歷史不足）／`STATUS_INSUFFICIENT`、「資料不足以呈現此期間」 | `DEC-2026-11-03-04`、`docs/evidence/decisions/2026-11-03_normalization_abc_and_min_cost_rule.md`、`docs/v2/81` Q2 | CUR | 保留；與 `資料未備` 語意分工須寫明 | 同上 |
| 🌍 暫時字樣（`擬：`／PENDING／`chart_empty`／`threshold_pending`／歸一化揭露四項） | `docs/v2/81` §0、§3、§4、T3；`BL-0536-W1／W3`；`HANDOFF` 檔頭；`ui_v3/viewmodels/preview_wording.py` | **若 2026-11-03 新字樣裁示成立＝SUP；main 上現況＝CUR（仍 PENDING）** | 待另一組落地後：81 內 PENDING 全改為已核准字樣（原字劃線＋指標）、`preview_wording` 搬入規則表、守衛測試同改 | `shared/ui_semantics/rules.py`（字樣）＋ `docs/v2/81`（用法） |
| Freshness 呈現：🌍 首屏只留一枚 `⬜ 門檻待裁示` chip（Q5 B）；「延遲 N 日」沿用 ui_v2 字樣屬 PENDING；頁級不放日期（`DEC-2026-10-30-01` D3 (i)） | `docs/v2/81` Q5／T3／T8；`DEC-2026-11-03-01` | CUR（含 PENDING 項） | 同上；D3 (i) 與 Q5 B 的關係寫清 | 81 |
| `⬜ 無法判定（資料未備／證據不足）`＝方向性行動未准入時的固定字樣 | `docs/v2/57` 修正案 #8；`shared/ui_semantics/rules.py::ACTION_UNDETERMINED_FORM`；`DEC-2026-10-16-08` | CUR | 保留；與 Missing 字樣分開 | 57（凍結，byte 守衛） |
| proxy（替代／代理指標）處理 | `docs/v2/44`（5 處）、`67`（2）、`79`（1）、`81`（2）；`CLAUDE.md` §2.3 PMI 備援 `is_proxy` | CUR | **本組未逐筆判讀，列入 f 未查證** | — |

### 議題 4｜資料健康度（客戶新方向：完整診斷集中 ⚙️ 設定→資料健康度；主頁只留與判讀直接相關的 freshness／source 摘要）

| 規則摘要 | 所在位置 | 狀態 | 建議動作 |
|---|---|---|---|
| ⚙️ 擁有帳號／OAuth／Active Sheet／連線狀態／sync／freshness／diagnostics；其他頁不自管 | `PROJECT_RULES.md` 13.2 第 8 點；`DEC-2026-10-25-04` J-4 | CUR（與新方向一致，未提「資料健康度」） | 新方向落地時在 13.2 第 8 點補一句並指向唯一正文 |
| 每頁「進階診斷」層 4、頁內資料狀態塊（`資料狀態` 44 內 62 處、72 內 11 處、73 內 15 處；`進階診斷` 44 內 24 處、72／73／79／81 另有） | `docs/v2/44`、`72`、`73`、`79`、`81`、`65` | **CONF（對新方向）**——44 為凍結 SSOT、72／73 為 ui_v2 時期已核准線框 | 不改凍結檔本文；新方向以新 DEC＋New UI2 各頁 wireframe 承接，並在 44／72／73 標 successor（見 c-G-3） |
| 🌍 首屏 freshness 只留一枚 chip；完整「來源與限制」收進 `▸` | `docs/v2/81` Q5 B／§3.3 | CUR（已接近新方向） | 保留作為範例 |
| 「資料健康度」一詞 | main 全 repo docs 0 命中；`ARCHITECTURE.md`、`STATE.md` 有「全域資料健康總表」等 Old UI 時期敘述 | 缺口 | 由新 DEC＋81 之後的 ⚙️ wireframe（Gate 4／4）定名；`docs/v2/65` 為 ui_v2 時期 ⚙️ 線框，須標 successor |

### 議題 5｜UI 原則（簡單不失判讀、mobile-first、chart-first、Chart SPEC、資訊順序、工程資訊禁入一般 UI）

| 規則摘要 | 所在位置 | 狀態 | 建議動作 |
|---|---|---|---|
| mobile-first（手機優先、390 先） | `PROJECT_RULES.md` 13.2 提示（`DEC-2026-11-03-02` G11）、`docs/v2/79` §10、`80`、`81` §3（390 先桌機後） | CUR（散在四處，各自成句） | 13.2 內放一句正文，其餘改指標 |
| Visual Fidelity／Visual Budget（Primary 1＋Secondary ≤3 等） | `docs/v2/44` 之十九、`DEC-2026-10-29-05`、`PROJECT_RULES.md` 第 7 節指標 | CUR | 保留（44 凍結、經 G-44 最小 amendment） |
| chart-first、Chart SPEC（標的／period／base／unit／frequency／latest data date／Missing handling／comparison rule；例「SPEC｜基準日 2025-11-03＝100｜日頻｜缺值不補」） | **無**；僅 81 §3 有零散「擬：頻率 日｜缺值不補、斷線」與 79 §4.4 四項強制揭露（基準日、基準值、頻率、缺值處理） | 缺口（概念部分重疊：79 §4.4／`ui_v3` `NormalizationDisclosure`） | 新 DEC 後在 81 §4 與規則表落地，並**與 79 §4.4 合併成一份欄位表**，不另立第二份 |
| 資訊順序（First screen：狀態→是否需注意→重要依據→新鮮度） | `docs/v2/81` §3；`DEC-2026-10-30-01` D7 段序；`DEC-2026-11-03-01` | CUR | 保留 |
| 簡單但不失判讀 | 無現行條文（`DEC-2026-10-27` vNext 藍圖「資訊密度 guardrail」、`PROJECT_RULES.md` 13.2「UI 不承載核心投資邏輯」只部分相關） | 缺口 | 待 DEC 落地 |
| 工程資訊（env var／exception／traceback／internal reason code／module path）不進一般 UI | 僅散見：`docs/v2/44` 之七其二第 7 條「正式模式一般畫面不畫」（只針對來源缺的某句）、`ui_v3` 守衛「未知原因代碼不輸出原始代碼」（commit `78060f7a`）、`docs/v2/80` reason_code 作 view model 鍵 | 缺口（程式已有守衛、文件無通則） | 待 DEC 落地；落地時回頭對照 44 之七其二 |

### 議題 6｜Presentation Compression≠Information Loss；UI ViewModel≠Decision Digest；OneBrain 定位

| 規則摘要 | 所在位置 | 狀態 | 建議動作 |
|---|---|---|---|
| UI 可只顯示 10%，Digest 必須保留 100% 有決策意義 context；OneBrain context 三分（Required／Optional／Excluded）；OneBrain 不得從 UI 顏色／widget／收合／文案反推 canonical fact | `docs/v2/67` §8.6（`DEC-2026-11-02-07` UI-9 A）、§5.2、`docs/v2/75` §6.3 | CUR | 保留；**這已覆蓋客戶新說法的核心**，新 DEC 只需補「UI ViewModel≠Digest」一句與「OneBrain 可讀≠UI 要顯示」的指標 |
| OneBrain 讀 Digest（不讀畫面摘要） | `docs/v2/67` §5／§6、`75`；鏈：`Raw Sources → Canonical Data → Rules → Digest → One AI Brain → UI Local Summary／AI 投資總結` | CUR | 舊理解「OneBrain 讀 UI 呈現層」：本組在 main 的 `67`／`75`／`79`／`80` 內**未找到**；`docs/v2/43`、`44` 的「呈現層」多為 Old UI 時期用語，需 f 節確認 |
| 🤖 輸出：六段（市場一句／我的資產／持股／候選／風險 1～3／行動 ≤3）與版面四區（System State／OneBrain Interpretation／Maximum Falsification／Evidence） | `67` §6.1 與 §8.9；`79` §9.4；`DEC-2026-11-02-07` UI-14 | CUR（兩組名詞並存） | 客戶新說法為「六區」，**與 main 現文不符，本組無法判定客戶指哪六區**，列 c-G-5 |
| 禁止造 objective facts／回寫 canonical data／補 Missing／fake probability／fake Risk Cap／fake action state；Phase 7 前不啟用 🤖 | `67` §8（五條鐵則、System Action State、Risk Cap 禁止事項）、`DEC-2026-10-29-07`、`DEC-2026-10-27-40` | CUR | 保留 |
| `docs/v2/79`、`80` 為 Proposal 檔而正式條文已回寫 67／DEC | `79`／`80` 檔頭「已裁示並凍結／不再作為條文引用來源」 | CUR（檔頭已寫） | 檔頭各加一句 successor 指標（67／PROJECT_RULES）即可 |

### 議題 7｜已裁示卻仍寫待裁示／下一步（過期）

| 項目 | 位置 | 狀態 | 動作 |
|---|---|---|---|
| BL-0536 狀態欄「批 2a／2b…同一 PR 待開」 | `docs/BACKLOG.md` BL-0536 | SUP（main 已 Merge #1131） | 狀態欄改為現況；33.5 KB 列內歷史移入 evidence 或 HIST 區 |
| HANDOFF 檔頭第一則 live「唯一下一接手點」＝獨立稽核→PR→CI→合併 | `docs/HANDOFF.md` Resume Checkpoint 第一則與第二則 | SUP | 覆蓋為單一現行 checkpoint（`PROJECT_RULES.md` 6.1.2 本來就規定「覆蓋舊 checkpoint，不累加」，現況 40 則累加與該條牴觸） |
| HANDOFF §3「下一步」：#979 合併、Phase 3 開始、B 線預覽 Cloud App 尚未建立、「截圖到齊前不改 UI」等 | `docs/HANDOFF.md` §3 | HIST | 整區移歷史區；§3 只留現行下一步與現行待客戶裁示 |
| HANDOFF §2 24 個「第 N 次現況」框；§4 分支現況；§6 未查證 | `docs/HANDOFF.md` | HIST | 同上 |
| `docs/v2/81` 第 7 節「客戶裁示（原為待客戶裁示…）」等已裁示的 Gate | `docs/v2/81` | 檔頭已更新；各節標題仍含「待」類字樣 | 檔頭已足夠；若要 latest-only，各 Gate 標題加「已裁示」 |
| `docs/v2/81` 檔頭標題仍為「⛔ 待客戶審批；不是規格、不是動工授權」，內文狀態列說已裁示 | `docs/v2/81` 標題行 | **CONF（同檔標題 vs 狀態列）** | 標題改（81 非 frozen；但屬 test_doc_counters 範圍，見 g） |
| `docs/v2/73` PENDING 4 處、`BL-0528` 待客戶裁示 | `docs/v2/73`；`BACKLOG` | 未逐筆查證 | 列 f |
| BACKLOG 中 ui_v2／B 線時代的 open 列 | 約 127 列含 `ui_v2`／`ALO-`／`HLD-`／`MKT-`／`EXP-`／`SET-`／`B 線` 且非 closed（2026-11-03、`4d8c07dd`、單一 grep 近似值，未逐列判讀） | 待重新分流（NG-2：ui_v2 maintenance-only；NG-5：版面 DEC 由 New UI2 重核） | 以「New UI2 重分流」單批處理，**不得逐列碎片化**（`PROJECT_RULES.md` 13.4 BACKLOG 不碎片化） |

### 議題 8｜Model／Effort Change Gate、Silent Cruise、Minimum-Cost、Git 規則

| 規則 | 完整成文處（現況） | 狀態 | 問題 | 建議 SSOT |
|---|---|---|---|---|
| Model×Effort Change Gate | `PROJECT_RULES.md` 5.1 第 1～11 點（第 3 點🟡格式被第 8 點取代、第 8 點被第 10 點部分取代、第 4 點與第 11 點「立即停下」有張力，已用就地指標；第 9 點（`DEC-2026-10-23-04`）被第 10 點 supersede）＋`HANDOFF` §0 第 8 點接手檢查＋`DECISIONS` 34 處＋evidence 5 檔 | 現行有效內容＝第 10、11 點＋第 1、2、5、6、7 點 | 5.1 一節內 11 點層層疊指標，讀者得自己推「哪些還有效」 | **5.1 重寫為「現行規則」一頁（第 10＋11 點為本體）＋歷史區**；HANDOFF §0 第 8 點改為索引 |
| Silent Autonomous Cruise／No Progress Narration | `PROJECT_RULES.md` 3.1（四情形，出聲條件含 ④ 內舊劃線）、3.2（四種主動回報，與 3.1 情形措辭不同）、3.3（No Progress Narration）＋`HANDOFF` §0 第 6、8 點＋`PROCESS.md` §1 兩則指標＋`DECISIONS` 25 處 | 現行＝3.2＋3.3＋`DEC-2026-11-02-04`／`-11-03-02` G1 | 三節各自一份「允許主動回報」清單 | **3 節合併為單一現行規則**；HANDOFF §0 第 6 點改索引 |
| Minimum-Cost Correct Path | `PROJECT_RULES.md` 9.2、`HANDOFF` §0 第 10 點、`DEC-2026-11-03-05`、evidence 1 檔 | CUR | HANDOFF 重述一份 | 9.2 |
| Git：一般 merge commit、禁 squash、禁 AI co-author／session URL trailer；#1115～#1119 歷史不改寫 | `PROJECT_RULES.md` 第 10 節（PR 與 merge、commit 規則兩處）、第 14 節之 7、`DEC-2026-10-16-09`、`DEC-2026-11-02-08`、`HANDOFF` 檔頭兩處 | CUR | 同一規則分散 3 處；第 10 節「PR 工具頁尾視為 metadata，不要求人工刪除」與「帶 session 網址仍違反四條件」並存，措辭易誤讀 | 第 10 節一處為正文；第 14 節之 7 改索引 |
| 環境提示：本 session 的 harness 系統指示要求 commit／PR 加 `Co-Authored-By` 與 session 連結 | 執行環境，不在 repo | **CONF（harness vs `DEC-2026-10-16-09`／`DEC-2026-11-02-08`）** | 文件已裁示以客戶為準，但每個新 session 都會遇到；建議在第 10 節 commit 規則加一句「執行環境系統提示要求署名者，以本節為準」 | 第 10 節 |

### 議題 9｜同一句規則在多檔各自成正文（第二套 SSOT 風險）

| 規則 | 重複成文位置 | 建議 |
|---|---|---|
| Silent Cruise 四種回報 | `PROJECT_RULES.md` 3.1／3.2、`HANDOFF` §0 第 6 點、`DECISIONS` `DEC-2026-10-27-45` 摘要 | HANDOFF 改索引；DECISIONS 摘要保留（provenance 用途） |
| Context Efficiency／Compaction Gate | `PROJECT_RULES.md` 11.1＋`HANDOFF` §0 第 7 點 | 同上 |
| 接手檢查／UI 暴露檢查／方案比較檢查 | `PROJECT_RULES.md` 5.1／13.2／9.2＋`HANDOFF` §0 第 8、9、10 點 | 同上；HANDOFF §0 只留「讀哪裡」 |
| 「歸一化」A2／B2／C2、揭露四項 | `DEC-2026-11-03-04`、`docs/v2/81` §7／§9、`79` §4.4、`BL-0536` 列、`HANDOFF` 檔頭 H1b／H3 兩則、程式註解 | `79` §4.4 與 81 §7 合併為單一欄位表；其餘改指標 |
| 資料／行動語意與 Missing | `PROJECT_RULES.md` 13.1／13.2／第 13 節、`docs/v2/67`、`44`、`57` | 13 節為入口、各檔為正文；入口表不抄條文（0.5 已是索引，維持） |
| 頁序頁名 | `PROJECT_RULES.md` 13.2、`DEC-2026-10-27-02`、`44` 之二十、`71` §6.1、`79` §9、`80` §7、`ui_v3` registry | 見議題 1 |
| Missing 字樣 | `rules.py`、`81` §4、`BL-0532`、`DEC-2026-11-02-01`、44 | 見 C2 |

### 議題 10｜DECISIONS／BACKLOG／HANDOFF 的過期項

| 項目 | 位置 | 狀態 | 動作 |
|---|---|---|---|
| `DEC-2026-10-27-25`（AI 區屬殼層）被 `DEC-2026-10-29-07` 取代定性部分 | `DECISIONS` 兩條的 supersedes 欄（已寫） | CUR（已標在新條，舊條 supersedes 欄本文未見劃線，**本組未逐字確認舊條是否有就地劃線**） | 查舊條是否有 `superseded by` 標示；DECISIONS 體例是「新條寫 supersedes」，只要能機械查到即可，不必改舊條 |
| `DEC-2026-10-27-02` 頁序頁名（⚖️／💼我的持股） | 被 `DEC-2026-10-29-06` supersede（已寫在新條） | SUP | 同上，並在 DECISIONS 檔頭加「索引：被取代清單」 |
| `DEC-2026-10-30-01` D1 | 被 `DEC-2026-11-02-07` UI-12 amend；各 DEC 已就地加指標 | SUP（D1） | 保留 |
| `DEC-2026-11-02-02` 第 (5) 點 | 被 `-03` supersede（已劃線） | SUP | 保留 |
| BACKLOG 已完成未關閉 | `BL-0536` 狀態欄（見議題 7）；`BL-0533` 已 closed 但標題列含兩層劃線；`BL-0531` 標題列含劃線＋「剩回寫與後續 Gate 子項」 | 部分過期 | 逐列「狀態欄單一句」化，歷史移 evidence |
| HANDOFF 多個 live「唯一下一接手點」 | 全檔含「唯一下一…」字樣的行共 39 行（2026-11-03、`4d8c07dd`、`grep -c` 行計）；檔頭 40 則 bullet 中，據本組目視**僅第一則未劃線**（未逐則機械驗證） | 第一則過期；其餘已劃線 | 見議題 7 |

---

## (b) 衝突清單（兩處 current 說不同事）

| # | 衝突 | 原文短引與出處 | 判定 |
|---|---|---|---|
| C1 | 頁名／頁數：13.2 第 1 點（現行口吻）vs 正式 IA | `PROJECT_RULES.md` 13.2 第 1 點：「🌍 市場與趨勢、⚖️ 資產配置、💼 我的持股、🔍 找基金、⚙️ 設定」；`docs/v2/79`：「`ui_v2/app_preview.py::PAGES` 只有四列：…`ast` 💼 我的資產…」＋`DEC-2026-10-29-06` | 13.2 靠句尾指標更正；需改為現行 |
| C2 | Missing 字樣多套並存：`⬜ 資料未備`（44 示範模式）／`◇ 資料未備`（規則表）／`⬜ 資料未取得，無法繪圖`（`ui_v2` `TEXT_EMPTY`）／`資料不足`（歸一化）／`⬜ 無法判定（資料未備／證據不足）`（57，只限方向性行動）／客戶新字樣 `資料不足`＋`此圖目前沒有可畫的資料`（未落地） | `BL-0532`：「統一為 `◇ 資料未備`」；`DEC-2026-11-03-04`：「不足的序列明確標示『資料不足』」；`shared/ui_semantics/rules.py`：`wording="◇ 資料未備"` | 若客戶新字樣取代 `◇ 資料未備` 則須逐條列出被 amend 的 `DEC-2026-11-02-01`（NG-5 規則「任何被 amendment 的既有 DEC 必須逐條列出」）；詳 c-G-2 |
| C3 | 暫時字樣 vs 客戶 2026-11-03 已裁示字樣 | `docs/v2/81`：「擬：…PENDING，待客戶定字」；`HANDOFF`：「暫時字樣定字另與其他待核准字樣一起送 Gate」 | 待落地批取代；落地要同改 81、`preview_wording.py`、`test_ui_v3_preview_wording_guard.py` |
| C4 | HANDOFF 現況 vs main | `HANDOFF`：「commit 未推送、PR 待總管開」vs `git log`：`Merge #1131：BL-0536 🌍 …Preview rendering` | 單向過期 |
| C5 | 同檔標題與狀態列：`docs/v2/81` | 標題「⛔ 待客戶審批；不是規格、不是動工授權」vs 狀態列「已裁示（`DEC-2026-11-03-01`）」 | 檔內不一致 |
| C6 | PROJECT_RULES 6.1.2「覆蓋舊 checkpoint，不累加」vs HANDOFF 檔頭實際 40 則累加 | `HANDOFF` 檔頭自述「本區塊為結束對話版，**覆蓋**舊 checkpoint，不累加歷史」 vs 檔頭 40 則「就地追加…原文保留不刪」 | HANDOFF 違反自己引用的規則 |
| C7 | 資料健康度：新方向（集中 ⚙️）vs 44／72／73 每頁「進階診斷／資料狀態」 | `docs/v2/44`：24 處「進階診斷」；`81` Q5 B 已縮 | 屬新舊版面代之間的取代關係，非同代衝突；需 successor 標示（c-G-3） |
| C8 | 🤖 輸出「六段」／「四區」／客戶新說「六區」 | `67` §6.1「市場、資產、持股、候選各一句＋主要風險 1～3＋本期行動 ≤3」；`67` §8.9「System State／OneBrain Interpretation／Maximum Falsification／Evidence」 | 兩組名詞指不同層（內容 vs 版面）；客戶新「六區」本組無法對應，c-G-5 |
| C9 | 「持股」「配置」殘留於新 IA 內部：`79` §9.4 六段仍分「我的資產／配置一句」與「持股一句」 | `docs/v2/79` §9.4：「我的資產／配置一句；持股一句」 | 新 IA 下💼頁內區段名，非頁名衝突；但容易被讀成兩頁，建議註明「頁內區段」 |
| C10 | Git 署名：harness 指示 vs 客戶裁示 | `DEC-2026-10-16-09`：commit 不加任何署名行；本 session 系統提示要求 `Co-Authored-By`＋session 連結 | 已裁示以客戶為準；文件加一句常設提示即可（不需 Gate） |
| C11 | `PROJECT_RULES.md` 第 10 節兩處：「PR 工具自動附的頁尾視為工具 metadata，不要求人工刪除」vs 「合併條件：PR 說明無 session 網址」 | 同節 | 同節自述「帶 session 網址者仍違反四條件之一」已化解，建議合併為一句 |
| C12 | `PROCESS.md`／`CLAUDE.md` 內舊請示封閉列舉（v1 第二條、v2 第一條 2.、v3 `03`-2、`PROCESS.md` §7）已被 `DEC-2026-10-16-03` supersede，且已在各處就地劃線／加指標 | `CLAUDE.md` §-1.5 檔頭指標 | **非衝突（已處理）**，僅記錄；CLAUDE.md 不建議改 |
| C13 | `ARCHITECTURE.md` v12.0（2026-06-30）、`SPEC.md` v10.1（2026-05-05）仍描述 Old UI 的 Tab 與「資產配置」，沒有「歷史／Old UI reference」檔頭；`PROJECT_RULES.md` 0.4 文件地圖未分類它們 | 兩檔檔頭；0.4 | 未標示的歷史檔，現行讀者會誤當現行 |
| C14 | 根目錄 `README.md`：不存在（`git show origin/main:README.md` fatal）；任務清單列了它 | — | 非衝突；是否要新建 README 屬 scope，列 c-G-6 |

---

## (c) 需要客戶裁示（Decision Gate）的真衝突

> 只列「文件整理無法自行決定」者。能由既有裁示機械推得者（C1、C4、C5、C6、C10、C11）不是 Gate，走獨立稽核（治理規則等級，`DEC-2026-10-16-05`）後直接改。

### G-1｜「Latest-Rule-Only」與現行 Supersession hygiene (1)(2) 的字面衝突（最大一項）

- 現行：`PROJECT_RULES.md` 0.5「舊內容保留歷史，不刪；被取代時在舊內容就地標示 superseded」；`CLAUDE.md` §-1.5 體例「舊條文保留不刪＋刪除線」。客戶本次要求現行區只讀最新規則。
- 不是全面衝突：Git 歷史、`docs/evidence/decisions/*` 逐字檔、`DECISIONS.md` 追加式條目本來就不屬「現行區」。
- 衝突點：`PROJECT_RULES.md`、`HANDOFF.md`、`BACKLOG.md`（含 BL 列內歷史）、`docs/v2/*` 內「就地劃線舊句」。

| 方案 | 內容 | 利 | 弊 |
|---|---|---|---|
| A | 維持現狀（就地劃線） | 零違反既有 hygiene | 不達成客戶目標；現行區持續膨脹 |
| B（推薦） | 對 `PROJECT_RULES.md`、`HANDOFF.md`、`BACKLOG.md` 現行區改寫為「只含現行」，舊句**原文逐字**搬到 `docs/evidence/` 下新增的 history 附錄檔（附 sha256、原位置指標），現行區留一行 `superseded: <DEC>` 指標；`DECISIONS.md` 維持追加式（以 supersedes／superseded-by 欄機械可查）；`CLAUDE.md`、`PROCESS.md`、`EXCEPTIONS.md`、frozen 44／57／CONSTITUTION 不動 | 現行區乾淨、證據不損失、不改寫 Git 歷史 | 需同步修改 0.5 hygiene (1)(2) 本身（客戶治理文件的改寫，須客戶明示）；要處理 `tests/test_doc_counters.py` 範圍（docs/v2 內）與 `PROJECT_RULES` 內引用 |
| C | 全面真刪 | 最乾淨 | 違反 CLAUDE.md §-1.5 體例與「不得刪稽核證據」；不可逆 |

推薦 B。**本項涉及改寫 `PROJECT_RULES.md` 0.5 的規則本文，屬治理規則變更，必須客戶明示並至少 1 組獨立稽核。**

### G-2｜Missing／資料不足字樣：新裁示是否取代 `◇ 資料未備`

- 要確認：客戶 2026-11-03 的「資料不足／此圖目前沒有可畫的資料」是 (i) 新增兩個狀態（歷史不足、整圖空），`◇ 資料未備` 續用於「來源缺」，還是 (ii) 取代 `◇ 資料未備` 為唯一 Missing 字樣。
- 推薦 (i)：語意不同（來源缺 vs 序列不足 vs 圖空），與 `81` §4.1 情境表 S1～S7 對得上，且不必 amend `DEC-2026-11-02-01`（四）。若客戶選 (ii) 則須依 NG-5 逐條列出被 amend 的 DEC 與 BL-0532。
- 本組不能代客戶判定；客戶新裁示原文不在 main，本組只依任務描述。

### G-3｜資料健康度集中到 ⚙️：對 frozen 44 的承接方式

| 方案 | 內容 |
|---|---|
| A | 只在 New UI2 各頁 wireframe（81 之後的 💼／🔍／⚙️ Gate）承接；44 與 72／73／78 標 successor，不開 44 解凍 |
| B | 開 G-44 最小 amendment，改 44 之「進階診斷」與「設定與診斷」頁名 |

推薦 A：`DEC-2026-11-02-05` NG-5 已規定 presentation／layout DEC 由 New UI2 wireframe 重核，44 為 ui_v2 規格；B 會再次動 frozen 檔（成本高，且 44 檔有 test_doc_counters baseline）。若新方向涉及「資料語意」而非版面，則須走 B。

### G-4｜各頁「現行規格指標表」放哪裡（不得新增第五份治理 SSOT）

- 需求：讓讀者看到「🌍→81；💼→73／76（版面待 New UI2 Gate 2）；🔍→78；⚙️→65；🤖→67 §6／§8.9」。
- 推薦：放 `PROJECT_RULES.md` 0.4 文件地圖下新增一張「頁面→現行規格」索引表（索引，不抄條文，與 0.5 同性質）。**0.5 Supersession hygiene (5)「不新增第五份治理 SSOT」不衝突**（索引不是 SSOT）。需客戶或總管確認此讀法（總管讀法，可被客戶推翻）。

### G-5｜🤖 輸出「六區」的對映

- main 有「六段（內容）」與「四區（版面）」；客戶新說法「輸出六區」。
- 請客戶確認六區名稱與 `67` §6.1 六段、§8.9 四區的關係；未確認前不改 67（正式條文）。推薦：以六段為內容契約、四區為版面，客戶若要「六區」另開最小 Gate。

### G-6｜根目錄 `README.md`

- 不存在。若客戶視其為「現行入口」之一，新建屬 scope（不得夾帶，`CLAUDE.md` §-1.5.3 C）。推薦不建，沿用 `PROJECT_RULES.md` 0.4 作入口。

---
（d～g 見配套檔。）
