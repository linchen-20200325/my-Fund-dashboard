# HANDOFF — 基金 New UI2 現行零記憶接手點

> **CURRENT／GitHub-first；觀測日期：2026-11-08（Asia/Taipei）**。本檔是「最後一次查到什麼」的**導航快照**，不是現在的 GitHub 查詢結果，更不是完成、CI 或獨立 QA 證明。任何新對話、長對話 compact、排程巡檢、Claude Code 接手、合併前都必須重新讀 GitHub。
>
> 舊版錯誤將 #1163 當 Draft 且否認 S1 Code 已動工。舊版原文逐字留存在 `docs/evidence/history/2026-11-07_handoff_before_cold_start_resync.md`（NOT CURRENT）；不可用舊版文件、對話記憶、PR body 或排程回報推翻即時 GitHub 證據。

## 0. 無記憶恢復順序（必須重新核查）

1. **只查基金 repo** `linchen-20200325/my-Fund-dashboard`：`main` 完整 SHA、最近 commits、已 merged PR（讀 `merged`、`merge_commit_sha`）；不要拿今天的 main SHA 不同判斷歷史 PR 沒合併。
2. **所有 Open／Draft PR**：逐一查 head/base SHA、diff/files、reviews、unresolved threads、mergeability 和 branches，確認是否已有人施工；PR 分支不等於 main，不能重開重複 PR。
3. **CI 依最新 head**：Fast、Schema、Slow、Visual 逐項查 `conclusion`。新 head 不能繼承舊 head 的 success，`mergeable=true` 不代表 CI／QA 合格；main CI 不可拿 PR CI 冒充。
4. **讀權威文件**：`CLAUDE.md` → `PROJECT_RULES.md` → 本檔 → `docs/BACKLOG.md` → `docs/DECISIONS.md` → 該批正式 SSOT／規格（frozen 44、子法 1＋57、79／80／81／82）。歷史快照不得當現行規格，HANDOFF 不能獨立宣稱完成。
5. **判斷與交接**：標明 NOW／NEXT、owner、可動工 Gate、實際 CI／QA／視覺證據和未驗項；遇到文件與 GitHub 不一致，以即時 GitHub 為準，文件另由安全治理批修正，不重做已合併功能。不具備工具／證據就寫 NOT VERIFIED，禁止猜測。

## 1. 最近一次 GitHub 實查快照（歷史觀測，必須重新查）

| 項目 | 2026-11-07 查到的狀態 | 對應證據 |
|---|---|---|
| main | `7ac7c9354f27831ad936b9f19f747526f750ca39`（#1170 merge；2026-11-08 歷史快照；前一快照為 `b0e2636f`） | 當前使用前仍須重查 GitHub |
| #1163 | **merged=true**；**歷史 merge SHA `025922382ef3921fc7b6858cb733084935fbf066`**（是 #1164 之前的 commit，不是當前 main HEAD） | [PR #1163](https://github.com/linchen-20200325/my-Fund-dashboard/pull/1163)；B／S1 設計文件已進 main |
| Open PR | ~~2026-11-08 查得 Open PR 僅 #1171（未合併，見 §3）；#1166 merge `b227ae5c`、#1168 merge `b34dd2eb`、#1167 merge `861add40` 均已完成~~（2026-11-08 更正，有意識，非漏刪）**#1171 已於 2026-11-08 merge（`5d8050df`），Open PR 為 0**（合併當時查得；使用前須重查 GitHub）；#1166 merge `b227ae5c`、#1168 merge `b34dd2eb`、#1167 merge `861add40` 均已完成 | ~~[#1171](https://github.com/linchen-20200325/my-Fund-dashboard/pull/1171)（Open）；不把此列視為即時狀態，使用前重查~~（2026-11-08 更正，有意識，非漏刪）[#1171](https://github.com/linchen-20200325/my-Fund-dashboard/pull/1171)（merged）；不把此列視為即時狀態，使用前重查 |
| #1164 已合併 head CI | [run 42359253829](https://github.com/linchen-20200325/my-Fund-dashboard/actions/runs/42359253829)：Fast／Schema／Slow／Visual **success** | 最後 head `4f045c26` 的結論；**不是 merge commit 的 main CI** |
| Code | ≤768px 五格同列頁首／無橫滑／≥48px；769px+ 原側欄；僅 🌍 可進、🤖 不開放；無效 sticky 已修 | #1164 **已 merged 到 main**，但 Preview-only ≠ Cloud 正式上線 |
| 視覺證據 | #1164 已合入 Chromium 合成 fixture 的 374／375／390／768／769／1280 及 190% 模擬 JSON／PNG | `docs/evidence/bl0544_s1_chromium_fixture_2026_11_07/`；**不代表**正式 Cloud／真機／WebView |
| QA／review | #1164 0 unresolved threads；GitHub 3 則 `COMMENTED` review 並非明確非作者 QA 核准；最新 head 完整 QA 證據 **NOT VERIFIED** | **已 merge ≠ QA 自動 PASS**；留下事後稽核缺口，不得否認合併事實 |
| main CI | #1168 merge 的 main push CI 逐 job 結論本次 NOT VERIFIED；PR head 四項 success 不能替代 main CI | 必須依最新 SHA 重新查 |
| 清理線 #1152／#1153／#1154 | 三 PR 均已合併；#1165 交接修復也已合併（`7a3ab87c`） | 不重做、也不把已 merged 的 PR 當 Open |

## 2. 唯一 NEXT：BL-0545 真實覆蓋率合法輸入 Gate

唯一下一接手點：使用者稍後選擇方式 A（自己的合法 Google 登入 session）或方式 B（自願提供匿名基金代碼清單），再以已合併的 Phase 1 唯讀探針取得真實三層分母；目前使用者明確指示暫不提供輸入，故維持 NOT VERIFIED，不執行 live、不得請求憑證或虛構結果。

**GitHub 已合併**：#1163（S1 設計）、#1164（S1 Preview-only Code）、#1165（零記憶 HANDOFF 修復，merge SHA `7a3ab87c268b5e8ca7c39947e37717071840cbcf`）。不重做已合併 PR；原 37 tests／sticky／JSON EOF 歷史失敗不當作現在的阻塞。

- **#1166、#1168 均已正式 merged**：#1166 merge `b227ae5c` 是研究證據；#1168 merge `b34dd2eb` 是依 `DEC-2026-11-07-03` 核准的 Phase 1 唯讀探針，最後 head `32f0a54f` 四項 PR CI success、非作者 QA 必修 0（以上為 PR 證據，不替代 main push CI）。正式 Live 模式 NOT IMPLEMENTED；真實 Active Sheet 覆蓋率 NOT VERIFIED；branch protection API 403，required checks NOT VERIFIED。
- **BL-0545 真實持倉覆蓋率 NOT VERIFIED**：沒有合法使用者 Active Sheet session、access token 或持倉清單；#1168 已依 `DEC-2026-11-07-03` 核准並合併 Phase 1 離線／匿名清單唯讀五維探針，`scripts/bl0545_coverage_probe.py` 已在 main，live 模式 NOT IMPLEMENTED。production `resolve_full_keys` 是主分組，DG2 canonical 僅 shadow_diff；真實 Active Sheet 覆蓋率及其分母 NOT VERIFIED，正式准入未定義；缺值不填 0、不以樣本冒充個人持倉。
- **#1164 合併後仍未驗**：正式 Streamlit Cloud 390/1280、真機／WebView/safe-area、OS 字放大、讀屏與實資料畫面；最後 head 的非作者完整 QA 未在 GitHub review 清楚證實。Chromium 合成 fixture 不是正式 production PASS；Preview 帳號入口 NOT IMPLEMENTED。歸於 BL-0544 post-merge evidence gap，不重開原 Code PR。
- **客戶 2026-11-08 方向裁示（要點轉述，非逐字；`DEC-2026-11-08-02`）**：D8 FX 閘門維持關閉、不以相同方法立即重跑；OneBrain 採 D1 方案 C（資料契約先行、Decision Digest 後續再建，規劃方向已核准）；D3(a) 唯讀對照表推進。**仍未授權**：正式 Digest 施工、D2 逐域契約與 Digest schema、Phase 7／Provider／Claude API runtime、FX 開閘；D2～D10 未逐項核准者保留原 Gate。**暫行下一步：D2 逐域 Required／Optional／Excluded 契約草案需客戶另行授權。** 本節「唯一 NEXT」（BL-0545 合法輸入 Gate）不變，因其為外部輸入驅動。
- **遠端分支**：2026-11-08 `git ls-remote` 查見 main 加 10 條非 main 分支（`data`、`push-assets`、`probe/{fx-obs-date,moneydj-basic,moneydj-nav,twse-eps}-{trigger,results}`），**客戶裁示全部保留**、不停用 cron、不刪證據、不改 workflow（`DEC-2026-11-08-01`）。未執行分支清理。
- **分工**：~~ChatGPT 獨立 GitHub Gate、產品／治理、文件、已授權 Auto-Ship；Claude Code 只做 Code、技術測試、實測、必要非作者技術 QA（需使用者把提示語交付給外部 Claude session）~~（→ 2026-11-08 被客戶分工裁示取代，`DEC-2026-11-07-04`：專案 AI／Claude Code 承接施工、測試、非作者獨立 QA、PR 修復、最新 head CI 查核、符合既有 Auto-Ship Gate 後的 merge、post-merge 驗證與 HANDOFF 更新，作者不可自任獨立稽核者；ChatGPT 負責產品／架構／UI／金融語意／資料契約／需求與提示語，不再主導 QA 或 merge；所有 Gate 照舊，非降低標準。）每批最多三項安全工作；不得為消除待辦擅改 frozen 44／57／CONSTITUTION、金融 Grade、資料來源、OAuth、Risk Cap、OneBrain 或 Phase 7。

## 3. NEXT／LATER（只安排已有安全條件的批次）

| 順序 | 工作 | Gate／owner |
|---|---|---|
| NOW | 分工與分支保留裁示登記（`DEC-2026-11-07-04`、`DEC-2026-11-08-01`）docs-only PR | 專案 AI：非作者 QA、最新 head CI 逐項核證後依既有 Auto-Ship Gate 處理；#1167 已 merged，不重做 |
| NOW | 客戶 2026-11-08 裁示登記（`DEC-2026-11-08-02`）docs-only：D8 FX 閘門維持關閉、不立即以相同方法重跑；OneBrain D1 採方案 C（資料契約先行，Digest 後續再建）；推進 D3(a) 唯讀字彙對照表 | 專案 AI：登記批；非作者 QA、最新 head CI 核證後依既有 Auto-Ship Gate 處理。D8 缺口／補證方法：`docs/evidence/fx_d8_gap_and_supplementary_plan_2026_11_08.md`；D3(a) 對照表：`docs/evidence/data_state_vocabulary_crosswalk_d3a_2026_11_08.md`（兩檔由他組同批撰寫，獨立 QA 已完成一輪並已回修，見 PR #1175）。**未授權**：正式 Digest 施工、D2 逐域契約、Digest schema、Phase 7／Provider／Claude API runtime、FX 開閘 |
| NEXT | BL-0545 使用者合法輸入後取真實三層分母 | Phase 1 已合併；使用者暫不提供輸入。方式 A 本人 session／方式 B 匿名清單；live NOT IMPLEMENTED、真實覆蓋 NOT VERIFIED |
| LATER | OneBrain Evidence 覆蓋差距稽核（研究已結案） | #1170 merge `7ac7c935`；`docs/evidence/onebrain_evidence_coverage_gap_audit_2026_11_08.md`（BACKLOG 檔尾有索引）。結論：無端到端 Complete Evidence→Digest 覆蓋、Digest 無 schema；推薦路線 C 僅為研究建議、非授權；D1–D10 待客戶裁示；Phase 7／正式 Digest／OneBrain runtime／Claude API 啟用仍未授權；~~D1–D10 待客戶裁示~~（2026-11-08 更正，有意識，非漏刪：D1 已由客戶採方案 C 為規劃方向，見 `DEC-2026-11-08-02`；D2～D10 未逐項核准者仍待裁；**暫行下一步：D2 逐域 Required／Optional／Excluded 契約草案需客戶另行授權**，未授權前不起草、不施工） |
| LATER | D1–D10 Decision Gate 路線與三風險最小影響查核 | ~~在 Open PR [#1171](https://github.com/linchen-20200325/my-Fund-dashboard/pull/1171)（未合併，客戶尚未決定保留或關閉；`docs/evidence/onebrain_decision_gate_route_and_risk_check_2026_11_08.md`）；若 #1171 被關閉，成果只存在該分支；不得寫成已裁示。三風險初步結論（僅供快速定位，以 #1171 文件為準）：R1 僅 ui_v2 Preview／測試可達；R2 decision_matrix 舊線 app.py 不可達但字面與 Missing≠HOLD 衝突，屬金融語意 Gate；R3 Old UI T7「組合當前市值」取最新 NAV 無日期檢查且 app.py 可達，屬金融語意／門檻 Gate；皆未授權施工~~（2026-11-08 更正，有意識，非漏刪）#1171 已於 2026-11-08 merge（`5d8050df`），D1–D10 路線與 R1–R3 查核已入 main（`docs/evidence/onebrain_decision_gate_route_and_risk_check_2026_11_08.md`），性質為**研究提案、非客戶裁示、不構成動工授權**。~~下一步待客戶就 D8（FX 冬令探測，約 11/24 前有時效）等 Gate 裁示~~（2026-11-08 更正，有意識，非漏刪）D8 的冬令探測已於 2026-11-08 執行並歸檔（run 42455423910；`docs/evidence/fx_obs_date_winter_probe_2026_11_08.md`），結論為證據不足以開閘，`FX_OBS_DATE_RULE_VERIFIED` 仍為 `False`；~~下一步待客戶就 FX 開閘 Decision Gate 裁示，(a) 冬令補跑窗口約 11/24～11/26（見證據文件 §7），是否補跑待獨立稽核與決策者，**未授權補跑**；**本批不開閘**；BL-0545 仍 NOT VERIFIED~~（2026-11-08 更正，有意識，非漏刪：客戶 2026-11-08 已裁示 D8 FX 閘門**維持關閉**、**不使用相同方法立即重跑**，先整理缺口與補證方法，`DEC-2026-11-08-02`；缺口與補證方法見 `docs/evidence/fx_d8_gap_and_supplementary_plan_2026_11_08.md`〔獨立 QA 已完成一輪並已回修；見 PR #1175〕；D8 補跑：本次未授權（客戶僅明示不以相同方法立即重跑）；FX 開閘：未核准（兩者為獨立說法）；補證表 M1-b 等是否算「以相同方法立即重跑」待判，判定前不得執行；BL-0545 仍 NOT VERIFIED） |
| LATER | BL-0542 💼 我的資產 G-3～G-5 | UI 設計部分核准，資料／配息／整頁接線 Gate 未全授權 |
| LATER | BL-0530 找基金 ISIN → MoneyDJ deterministic identity | research-only；無已核准 source 時不得啟用 mapping |
| LATER | 設定登入、BL-0534 frozen amendment、BL-0535 cutover、OneBrain／Phase7 | 各走正式授權、獨立 QA、必要人工／法規 Gate |

## 4. 新對話／compact 後交接自驗

- [ ] 我已重新讀取 main SHA、Open／Draft PR、PR merged flag、最新 head diff、四 job conclusions、review／threads。
- [ ] 能分清 **已在 main**、**Draft PR 中**、**尚未授權**、**NOT RUN／NOT VERIFIED**，不把 fixture 當正式畫面。
- [ ] 沒有重派已合併的 #1163／#1164，也不把已合併的 Code 說成仍在 Draft；舊 head 的失敗不當成最新結果。
- [ ] 最新 PR／CI 狀態寫在 GitHub 可追溯處；下一個 owner 與單一接手點清楚；只有已核准的安全工作才繼續。
- [ ] 作者／非作者 QA 分離，`COMMENTED`／自述不冒充非作者驗收；無證據不 merge。
- [ ] 文件或聊天太長仍從 GitHub 重查；本 HANDOFF 不能取代即時核驗或現行正式 DEC／SSOT。

> 這份文件沒有創造新客戶裁示或改動高位階治理條文；詳細執行與權限一律回到 `CLAUDE.md`／`PROJECT_RULES.md`。舊交接保存在 history，僅作追溯。
