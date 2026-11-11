# 2026-11-11｜基金 New UI2 雙模式 T1～T5 及三項視覺待決裁示

## 客戶當次回覆（經 ChatGPT 轉貼）

> 我同意你建議的 T1～T5 及另外三項裁示。請依 GitHub Gate 正式落盤，安排隔離 PoC 與後續工作，維持原施工限制。

客戶句『我同意你建議的 T1～T5 及另外三項裁示……』為客戶逐字句，經 ChatGPT 對話轉貼，專案 AI 未見原始對話、repo 內不可核對；八項對應屬要點轉述，轉達人：ChatGPT 協作助手；V1～V3 的建議原文不在 repo（INFERENCE）；單組整理，未經第二組驗證。下述八項為該句所指向、前一則 ChatGPT 建議的**要點還原**，不是將下述細節冒充客戶逐字原話。研究依據為合併 PR #1209：`docs/evidence/fund_newui2_dual_theme_b_design_gate_2026_11_11.md`；當時 main `50e66801`、Open PR 0（歷史快照；使用前重驗）。

## 八項確認

| Gate | 本次核准／維持／延後 | 射程 |
|---|---|---|
| T1 架構 | **同意 B**：僅限 `ui_v3` scoped 雙套 token + 使用者手動切換的**隔離技術 PoC**；不碰全域 `.streamlit/config.toml` | **只授權隔離 PoC**；不是正式雙模式 UI 施工授權 |
| T2 入口 | **同意等待**：待 ⚙️ 設定頁正式線框與實作獲核准後，再配置切換入口 | 不新增設定頁空殼、不增第六頁、不先加正式 Preview UI 控制項 |
| T3 偏好 | **同意 session-only PoC**：先用 session state 驗證互動／rerun；跨重載、關閉再開、跨裝置的永久記憶**未核准** | 不可宣稱 session 永久保存；不得增加 browser storage、會員遠端設定或 Sheet 寫入 |
| T4 色票 | **同意暗色研究示例僅供隔離 PoC 測試**，不是正式色票；後續須附對比與畫面證據再裁示 | 不可將研究 HEX 值寫成正式 `ui_v3/design/tokens.py` 核准值 |
| T5 G7 | **同意延後**：等有正式 dark 實作且完成非作者 QA 後，再安排 Cloud／WebView／真機驗收 | **目前沒有** G7 真機／Cloud 施工或驗收授權；上線前仍須另行 Gate |
| V1 共用 config | **維持現況**：不統一 `.streamlit/config.toml` 與 `ui_v3` token | 避免影響 `ui_v2`／Old UI／正式入口；將來若要跨 app 統一須重新裁示 |
| V2 12px 字 | **同意改善方向**：現有 12px 輔助字在**下一個適當的已授權 UI 批次**調到 13px，且先驗證 390／768／1280 版面 | **不授權獨立開新 UI 施工批**；不可因此修改既有首屏預算、控制項尺寸／導覽 |
| V3 grey／neutral | **延後**：現行共色維持，等語意與視覺候選、對比證據備妥再裁示 | 不修改 `STATUS_TONES`、`shared/ui_semantics/rules.py`、狀態字樣、或擅自把 missing 視為 neutral |

## 隔離 PoC：明確施工邊界

**已授權的最小技術工作**：在獨立分支的非 production 測試／研究目錄，以 pinned Streamlit 1.59.x 和合成 fixture 驗證兩套色票切換、原生 `st.radio`／`st.container`／expander、hover/focus、session state、rerun、Missing／Failed／Stale 文字＋符號、390／768／1280 視覺證據，對比度由非作者重新計算。獨立 PoC 可以有自己的測試入口，但**不得由正式 Preview App 或正式入口 import／連結，不能變更正式五頁 IA**。若測試框架需要額外 dependency、外部服務或在 UI 中植入 JS，先回技術決策，不自動擴範圍。

**禁止修改／接線**：`ui_v3/app_preview.py`、`ui_v3/pages/`、`ui_v3/design/tokens.py`（**整檔禁止**，不得新增任何 dark 條目）、`ui_v3/design/theme.py`、`ui_v3/shell/`、`tests/ui_v3/ui_v3_guard_lib.py`（不得改 `LAYER_DEPS` 或放寬任何守衛）、`.streamlit/config.toml`、`ui_v2/`、Old UI、正式入口、canonical／資料來源／公式／FX Gate／Risk Cap／OneBrain、Active Sheet／系統 Sheet、正式頁面註冊／cutover。若隔離 PoC 在 repo 裡新增檔案，須標記非 production、對外不可用，並用測試防止 production import；不得用研究證據宣稱使用者已可切換。

**PoC 位置與守衛邊界（專案 AI 讀法，DEC 授權內的技術邊界決定；非客戶逐字、可被客戶推翻；2026-11-11 讀 `tests/ui_v3/test_ui_v3_import_guard.py`、`test_ui_v3_preview_not_formal_guard.py`、`ui_v3_guard_lib.py` 後作成）**：

- **現有守衛掃描範圍（FACT，已讀）**：`test_ui_v3_import_guard.py` 的母體是 `ui_v3/**/*.py`，未知層目錄一律紅，故 PoC **放在 `ui_v3/` 內會被判違規**。`test_ui_v3_preview_not_formal_guard.py` 掃根目錄 `*.py`、`ui`／`ui_v2`／`services`／`repositories`／`shared`／`infra`／`scripts`／`mcp_server`／`models` 的 `.py`（含字串常數）以及 `.streamlit`／`.github`／`.devcontainer` 的文字檔，只要含 `ui_v3` 就紅；另有「根目錄出現 `pages/` 即紅」。這些掃描都**不涵蓋**新的頂層非 production 目錄。
- **P1 合法位置**：PoC 程式放 `poc/dual_theme_isolated/`（新增頂層、非 production）；PoC 測試放 `tests/poc_dual_theme/`。該目錄**允許有 PoC 專用的 Streamlit 入口檔**（例如 `poc/dual_theme_isolated/app_poc.py`），但**目錄內不得有名為 `pages/` 的子目錄**，根目錄也不得新增 `pages/`（避免 Streamlit 自動長出導覽、也避免觸發上述守衛）。`tests/` 沒有 `__init__.py`，PoC 測試檔名須在全 `tests/` 內唯一（建議 `test_poc_dual_theme_*.py`）。實際落點於 PoC 批動工前再以守衛掃描清單複核，守衛清單若有變動以當時為準。
- **P2 不得放進 `ui_v3/`、不得改守衛**：PoC 不得位於 `ui_v3/` 之內；不得修改 `ui_v3_guard_lib.py` 的 `LAYER_DEPS` 或放寬任何既有守衛。
- **P3 PoC 自帶守衛測試**：須證明 `app.py`、`ui/`、`ui_v2/`、`ui_v3/`、`scripts/`、`.github/` 沒有任何模組 import 或引用 PoC 目錄；且 PoC 不寫入 `ui_v3` 的 token（`ui_v3/design/tokens.py` 不含 PoC 的 dark 條目、PoC 程式沒有對 `ui_v3/` 路徑的寫入）。PoC **可以唯讀 import `ui_v3`**（現有守衛不掃 `poc/`，故不會擋；唯讀 import `ui_v3.design.tokens` 時不得觸發副作用，也不得因此在 `.github/`、`.streamlit/`、`.devcontainer/` 或正式路徑留下 `ui_v3` 字串）；若 PoC 批判斷唯讀 import 有耦合風險，改為把 light 值複製成 PoC 內 fixture。PoC 的 dark 候選色只存在於 PoC 目錄內。
- **P4 禁止清單補充**：`ui_v3/design/theme.py` 加入禁止修改；`ui_v3/design/tokens.py` 由「不改既有核准值」收緊為**整檔不動**（不得新增 dark 條目）。
- **P5**：此 PoC **沒有 BL 編號**；「適當時機」由專案 AI 總管在本 DEC 授權內決定開批，**不需客戶再行動**；PoC 完成後停止，正式雙模式仍需另 DEC。

**技術注意**：PR #1209 QA 已查 Streamlit 1.59.1／1.59.2：`st.context.theme.type` 不反映 `ui_v3` scoped CSS 的深色，**不得**用它作使用者目前模式的狀態權威；PoC 應以自身受控的 theme state 為權威，不得讀取 UI 的顏色反推資料語意。

**交付順序**：本次文件 PR → 適當時機由專案 AI 在不與現有工作衝突下開**單一最小隔離 PoC** → 非作者 QA＋CI／必要 browser test → Auto-Ship Gate → 文件留證／停止。**PoC 成功不等於正式 UI 施工授權**；後續需新的正式視覺及持久化 Decision Gate。

## 不在本次裁示範圍

- BL-0545 仍為唯一全域 NEXT；既有使用者暫不提供真實 Active Sheet 輸入的邊界維持。
- 先前股票專案的 Coverage／Digest／OneBrain 建議僅作基金後續缺口研究方向；不得照搬股票規則、Risk Cap 或額外新增工程批次。研究時須以基金既有 `docs/v2/67`、`75`、BL-0527、BL-0545 為依據。
- 靜默巡航失效根因稽核已同意於**下次適當文件治理批次**處理；本次不修改 `PROJECT_RULES.md` 或 `CLAUDE.md`，也不額外開一個治理 PR。
- 即使 PoC 在進行中，回報仍遵守「只有完整 Batch 完成／真正需要客戶裁示／真正 blocker／Model-Effort Change Gate 才出聲」，不得回報 CI／agent 等中間狀態。

## 證據級別

- 客戶確認句：客戶逐字句，經 ChatGPT 對話轉貼，專案 AI 未見原始對話、repo 內不可核對；轉達人：ChatGPT 協作助手。
- 八項細節：**要點轉述**，由客戶明示同意 ChatGPT 前一則八項建議後歸納；V1～V3 的建議原文不在 repo（INFERENCE）；單組整理，未經第二組驗證；方案推薦本身不等於先前已有權的 DEC。
- GitHub／Streamlit：研究 #1209、QA 與 CI 記錄；Cloud／WebView／真機 NOT VERIFIED，隔離 PoC NOT RUN（截至建立本檔時）。
