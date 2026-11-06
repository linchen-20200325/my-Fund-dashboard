# New UI2｜Responsive Google Account Entry 設計契約（2026-11-05）

> 狀態：**客戶已同意的 UI 方向，尚未實作；純 presentation 設計**。來源為客戶 2026-11-05 提供的兩張桌機／手機參考示意圖及對話同意，經 ChatGPT 要點整理，**非逐字**。正式實作仍須獨立施工授權、實際 390／1280 驗收與 Model／Effort Gate。不得取代 frozen 44、現行 New UI2 導覽或 OAuth 合約。
>
> 主要參照：`docs/v2/80_new_ui2_architecture_proposal.md` §17、`docs/v2/82_new_ui2_assets_ui_data_evidence_proposal.md` §9.7～9.8、`ui_v3/shell/nav.py`、`ui_v3/pages/chrome.py`、`services/v2_tables/personal_session.py`、`DEC-2026-11-02-05`、`DEC-2026-11-03-11`。屬未施工的登入 UI 設計，不是登入功能現況宣告。

> ⚠️ **2026-11-06 supersession 指標**：本文所述「手機固定底部五頁導覽為未來正式目標」的前提已被較新的客戶裁示取代，見文末〈2026-11-06 狀態更新（supersession）〉；本文原文一字未改。

## 1. 使用者可見的兩種呈現

| 尺寸 | 常態呈現 | 展開／操作 | 不得破壞 |
|---|---|---|---|
| 桌機／平板（>768px） | 左側固定導覽欄最上方設精簡「Google 帳號」區；帳號區之後才是既有五頁導覽 | 依現有正式登入狀態呈現可用操作；已登入可至既有帳號／來源管理 | 固定側欄、五頁 IA 順序與可進狀態、圖表內容空間 |
| 手機（≤768px） | 主要頁面頂部右側**單一精簡帳號入口**，不要常駐大型登入卡或電子郵件 | 點擊後以可關閉的抽屜／浮層展示帳號狀態、登入或帳號操作；不推動主圖與首屏卡片 | **現行固定底部五頁導覽**、≤5 首屏核心項目預算、48px 觸控目標、safe-area、主畫面主要操作 |

- 手機既有導覽事實：`ui_v3/shell/nav.py` 目前採 **≤768px 底部五頁導覽**；**不**因新帳號入口而改成漢堡選單或改掉導航。
- 圖中的登入卡、頂欄位置及文字是**視覺參考**；不得讓靜態草稿覆蓋已核准的正式詞彙與元件數量。
- 手機頂部帳號入口與 Shell 的 Preview／資料狀態列應避免重複佔高；不得額外創造投資或資料健康度 chip；帳號圖示只代表**認證**。
- 展開層須可關閉、鍵盤可操作，適當處理焦點／螢幕閱讀器，不能遮住底部導覽或讓內容永久不可達。
- 當有效 OAuth 尚未於該部署環境開放或設定不足，登入操作不可偽裝為可用；不要因暫無配置而全域宣稱 OAuth「尚未實作」。

## 2. 認證狀態、來源狀態與資料健康度分離

權威狀態來源為既有 L2 `services/v2_tables/personal_session.status(state)`，其輸出含 `login_state`（`logged_out`／`pending_login`／`logged_in`）、`email`、`pending_login_email`、`pending_sheet`、`active_sheet`。UI 不解析 token、不自造登入判定。

| 認證／選本情境 | 畫面原則 | 防誤判 |
|---|---|---|
| `logged_out` | 帳號入口顯示未登入語意；登入是否可操作由既有部署設定／合法流程決定 | 不自動選 Active Sheet、不把持倉當 0 |
| `pending_login` | 顯示「待確認登入」的正式語意及待確認帳號，透過**既有明確確認流程**完成 | Pending 不等於已登入、不可偷換帳號 |
| `logged_in`、沒有 `active_sheet` | 顯示已登入及尚未選定來源；導向既有選本流程 | 已登入 ≠ 有持倉來源 |
| `logged_in`、有 `active_sheet` | 可顯示經既有契約核對的選定來源摘要 | 已選來源 ≠ 資料已取得或完整 |
| 認證失效／資料來源讀取失敗 | 使用既有錯誤碼與已核准顯示語意；依現行 session 清理契約 | 不吐 token、授權碼、session ID、raw error trace |

- **認證、Active Sheet、資料完整性為三個不同維度**。帳號控制不替代 `ShellStatus`，也不改來源健康度規則。
- 所有登入、確認、切換、登出、Picker、Pending／Active 的動作應重用 `personal_session` 與現有安全橋接／既有 Google OAuth，**不得建立第二套 OAuth 或直接操作憑證**。
- 新的畫面文字若未列入正式 `APPROVED_WORDING`，標示為**待文字 Gate**，不可因這份文件自動加入正式詞彙。

## 3. 不變條件與實作前置

1. 不改 `ui_v3/shell/registry.py` 的五頁順序、可進頁或 Phase 7 限制；不改手機底部導覽。
2. 不修改 Old UI／`ui_v2`，不啟動 `ui_v3` 正式 cutover。
3. 不直接修改 `infra/personal_oauth.py` 的安全模型；不存取、輸出或回傳敏感 token。
4. UI layout 不得變更正式基金資料契約、G1-③ Complete Evidence、Decision Digest 或 deterministic formula。
5. 與正在執行的 BL-0542 G-2 Preview 載入端工作**分開施工**；先比對 G-2 實際合併成果，再決定最小接線點，不能直接把登入動作塞進 Evidence adapter。
6. 新 UI 施工前重新檢查正式字樣、登入頁可用路徑、OAuth redirect／Preview host、實際 `personal_session.status` 型別、Session 與 Sheet Picker 行為；缺乏證據不宣稱已完成認證。
7. 這份規格**不授權**修改任何程式或測試；不修改凍結文件。

## 4. 未來最小施工／驗收契約（另批授權）

| 類型 | 應驗證 |
|---|---|
| Shell | 桌機側欄帳號區位置；手機右上帳號入口；手機浮層開關、焦點、關閉與 safe-area |
| IA | 390／768／769／1280px；五頁順序、底部導覽、可進頁、狀態列與第一屏預算不變 |
| OAuth | logged_out／pending_login／logged_in；登入確認／切換／登出沿用合法既有路徑；可用性依部署環境 |
| Source | 無 Active／有 Active／讀取失敗；帳號切換不得顯示前帳號來源 |
| 安全 | 帳號資料遮蔽、未授權操作禁用、沒有 token 或原始錯誤外漏 |
| VF | 需 production-like 的桌機與手機實際截圖；單元測試或 fixture screenshot 不能當正式目視驗收 |

施工時建議先由共用狀態 ViewModel 做 read-only 呈現，再接可用操作（同一批或分批依實際風險決定）。不必再做一輪廣域研究，也不得把 Preview 的假按鈕當成功能完成。

## 5. 狀態與接手

- **已確定**：桌機側欄頂部帳號區；手機頂部精簡帳號入口＋按需展開層；共用既有 OAuth／session；認證與 Active Sheet／資料健康度分離；現有手機底部導覽必須保留。
- **待驗收**：正式狀態文案、OAuth 的 Preview 配置、實作細節、390／1280 Visual Fidelity。
- **唯一後續工程切入點**：在 G-2 實際合併、GitHub Gate 通過後，另批授權 `ui_v3` Responsive Account Entry 的最小接線及 UI 測試。

## 6. 2026-11-06 狀態更新（supersession）

> **有意識的更正，不是漏刪**（日期 2026-11-06）。上方原文依本檔慣例保留，不刪、不改；被取代的部分在此註明。

- `DEC-2026-11-05-01` 是較早的登入入口 UI 設計裁示。其後 `DEC-2026-11-06-01`（客戶裁示，登記於開啟中的 Draft PR #1160，**尚未進入 main**）將手機 New UI2 導覽定為 **B ＝ 上方橫向五頁籤**。
- 因此本文所述「手機採現行固定**底部**五頁導覽、且須保留為未來正式目標」（第 1 節表格與「手機既有導覽事實」、第 3 節第 1 點、第 4 節 IA 列、第 5 節「已確定」中的底部導覽字樣），**由較新裁示取代，不再作為未來目標**；`ui_v3/shell/nav.py` 目前為底部導覽僅是現況事實，未被本更新改動。
- **仍然有效、不變**：桌機側欄頂部帳號區；手機帳號入口的可及性（精簡入口、可關閉展開層、鍵盤與焦點、48px、safe-area）；登入／切換／登出；Active Sheet 身分；OAuth 邊界與認證／Active Sheet／資料健康度三維分離。
- **邊界**：裁示 ≠ 修訂生效 ≠ 施工授權。frozen `docs/v2/44` 未修改（修訂待辦，BL-0544 登記於 #1160）；Streamlit Shell 未修改；本更新不新增任何正式字樣，也不授權程式或測試變更。
