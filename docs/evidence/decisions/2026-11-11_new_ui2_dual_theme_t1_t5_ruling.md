# 2026-11-11｜基金 New UI2 雙模式 T1～T5 及三項視覺待決裁示

## 客戶當次逐字回覆

> 我同意你建議的 T1～T5 及另外三項裁示。請依 GitHub Gate 正式落盤，安排隔離 PoC 與後續工作，維持原施工限制。

此句為 ChatGPT 對話中客戶原文；**只有此句為逐字**。下述八項為該句所指向、前一則 ChatGPT 建議的**要點還原**，不是將下述細節冒充客戶逐字原話。研究依據為合併 PR #1209：`docs/evidence/fund_newui2_dual_theme_b_design_gate_2026_11_11.md`；當時 main `50e66801`、Open PR 0（歷史快照；使用前重驗）。

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

**禁止修改／接線**：`ui_v3/app_preview.py`、`ui_v3/pages/`、`ui_v3/design/tokens.py` 的既有核准值、`ui_v3/shell/`、`.streamlit/config.toml`、`ui_v2/`、Old UI、正式入口、canonical／資料來源／公式／FX Gate／Risk Cap／OneBrain、Active Sheet／系統 Sheet、正式頁面註冊／cutover。若隔離 PoC 在 repo 裡新增檔案，須標記非 production、對外不可用，並用測試防止 production import；不得用研究證據宣稱使用者已可切換。

**技術注意**：PR #1209 QA 已查 Streamlit 1.59.1／1.59.2：`st.context.theme.type` 不反映 `ui_v3` scoped CSS 的深色，**不得**用它作使用者目前模式的狀態權威；PoC 應以自身受控的 theme state 為權威，不得讀取 UI 的顏色反推資料語意。

**交付順序**：本次文件 PR → 適當時機由專案 AI 在不與現有工作衝突下開**單一最小隔離 PoC** → 非作者 QA＋CI／必要 browser test → Auto-Ship Gate → 文件留證／停止。**PoC 成功不等於正式 UI 施工授權**；後續需新的正式視覺及持久化 Decision Gate。

## 不在本次裁示範圍

- BL-0545 仍為唯一全域 NEXT；既有使用者暫不提供真實 Active Sheet 輸入的邊界維持。
- 先前股票專案的 Coverage／Digest／OneBrain 建議僅作基金後續缺口研究方向；不得照搬股票規則、Risk Cap 或額外新增工程批次。研究時須以基金既有 `docs/v2/67`、`75`、BL-0527、BL-0545 為依據。
- 靜默巡航失效根因稽核已同意於**下次適當文件治理批次**處理；本次不修改 `PROJECT_RULES.md` 或 `CLAUDE.md`，也不額外開一個治理 PR。
- 即使 PoC 在進行中，回報仍遵守「只有完整 Batch 完成／真正需要客戶裁示／真正 blocker／Model-Effort Change Gate 才出聲」，不得回報 CI／agent 等中間狀態。

## 證據級別

- 客戶確認句：**逐字**，出自 ChatGPT 對話，尚非由專案 AI 在原環境獨立取得。
- 八項細節：**要點轉述**，由客戶明示同意 ChatGPT 前一則八項建議後歸納；方案推薦本身不等於先前已有權的 DEC。
- GitHub／Streamlit：研究 #1209、QA 與 CI 記錄；Cloud／WebView／真機 NOT VERIFIED，隔離 PoC NOT RUN（截至建立本檔時）。
