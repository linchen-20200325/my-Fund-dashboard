# BL-0544｜手機頁首五頁籤最小合法修正與施工 Gate 提案（2026-11-07）

> **僅為 ChatGPT 產品／治理提案，非客戶新裁示、非 44 amendment、非施工授權。** 依 main `b215d13b8def1715005d68087b266058f812046b`（PR #1162 合併後）與已合入的 `DEC-2026-11-06-01`／`-02`、`docs/v2/80` §18、`docs/evidence/new_ui2_top_tabs_44_amendment_inventory_2026_11_06.md` 整理。本檔不能取代 frozen 44／57／CONSTITUTION、DECISIONS 或精確線框核准。

## 0. 已確定／尚未確定

- **已核准產品方向**：New UI2 **手機**頁首橫向五頁籤，順序固定 🌍／💼／🔍／🤖／⚙️；僅 supersede `DEC-2026-10-27-11` 的**手機導航位置形式**（底部 → 頂部）。桌機側欄、登入／OAuth、Active Sheet、五頁 IA、🤖 Phase 7 前可見不可進都不變。
- **事實勘誤**：44 不含 `底部`／`bottom` 字面強制條款；44 第二節 2.1 的 768 是欄數斷點，不是導覽形式條款。原盤點列出 44 :5627 帳號入口「導覽抽屜或精簡帳號控制」、:5384 與 :5551 的手機第一屏條件；均須維持且重驗，**不能自行宣稱 44 已合法 amended**。
- **目前程式**：`ui_v3/shell/nav.py` 仍是手機 bottom-nav（`MOBILE_MAX_PX=768`、`TOUCH_MIN_PX=48`、`BOTTOM_NAV_HEIGHT_PX=60`），`ui_v3/pages/chrome.py` 與 `ui_v3/design/tokens.py`、navigation shell tests、visual fidelity tests 有相依；尚未改程式或測試。
- **授權邊界**：現有 B 是**設計方向裁示**；不等於 frozen 44 合法修正或 Claude Code 新一批程式施工授權。不得藉此動 Old UI、`ui_v2`、金融公式、來源、Risk Cap、配息、NAV/FX、OAuth 或 Phase 7。

## 1. 三條可行修正路線（供客戶真正需要的 Gate 核准）

| 路線 | 作法 | 正確性／風險 | 速度／Token | 結論 |
|---|---|---|---|---|
| A. 直接修 44 正文 | 正式走 44 amendment 與 md5 guard 更新；僅更動真實衝突條款 | 程序嚴謹，但現時無明文底部條款，可能無必要解凍；容易擴大測試 | 最慢／高 | 非預設 |
| **B. 最小 successor／適用性確認** | 逐條確認 44 :5627、:5384、:5551 與頂部方案不矛盾，對較早 `DEC-2026-10-27-11` 的手機位置部分以已核准的較新 DEC 為 successor；**由客戶明示確認此路線是否滿足 44 合法修正 Gate**。若確認不必修 44，保持 44 原封不動，並將裁示寫 DEC／BL／設計 spec | **最少變更，且不誤稱修改過 44；法律／治理適用性須客戶核准，不能由 AI 推定** | **最快／最低 Token** | **推薦** |
| C. 另立 44 最小 amendment 附錄 | 只加適用條款／例外與 44 hash guard，保留原文，依正式 amendment 程序 | 合規穩健，但多一層 frozen 版本變更及 tests／審查成本 | 中／中高 | 若 B 被否決時採用 |

**建議：B（先精確定位、再做單點決定）**。此處 B 指「合法修正路線」，與客戶已核准的**手機 UI 方案 B**是不同選項；不可混淆。如果客戶或上位治理指出 B 無法構成合法 44 amendment，必須回到 C 或按正式程序提案，不能逕自跳過。

## 2. 建議的最小施工授權範圍（仍待客戶核准）

只授權 **Preview-only** 的 `ui_v3` shell 導覽外觀變更：
1. 手機尺寸（以現行 `MOBILE_MAX_PX=768` 為待核查實作斷點）將固定底部五入口改為**頁首可橫向捲動五頁籤**；桌機 sidebar 保留；不註冊空殼頁。
2. 五頁名稱、順序、`🤖` 禁入、≤2 次互動、共用 routing 與 APPROVED_WORDING 不變。頁首右側精簡登入入口不得被覆蓋；不改 OAuth callback/session/token 或 Active Sheet 身分規則。
3. 避免頁面橫向溢出與首屏遮擋；顧及 safe-area／WebView／鍵盤／螢幕閱讀器，`48px` 觸控區與 active/focus 語意；只改導覽 shell 必要檔案與對應 tests、tokens；**不改頁面資料內容、任何金融邏輯或正式 Cloud cutover**。
4. 測試與驗收：390／768／769／1280px（包含 768/769 邊界）；390 首屏結論燈仍可見且不暗中調高 ≤5 預算；側欄、頁籤 scrolling、帳號入口、🤖 disabled、路由及 Visual Fidelity；真實 WebView／手機測試無法執行者標未驗，不得當 PASS。
5. 範圍外項目都不授權：`ui_v2`／Old UI、正式上線切換、UI 第六頁、新資料源、配息／NAV／FX、Risk Cap、健康准入、OneBrain/Phase 7。正式版面必須經精確線框／字樣 Gate、獨立 QA 與 CI。

## 3. 文件責任與最短路徑

- **ChatGPT**：核對 frozen 44 真實條款及 80 §18；提出本提案；記錄客戶對 B 或 C 的最小核准範圍於 `docs/DECISIONS.md`，同步 `docs/BACKLOG.md`／`docs/HANDOFF.md` 及對應 spec；合法修正與 UI 施工授權是兩個不同 Gate。
- **獨立 QA**：先核對「沒有偷偷解凍 44」「上位條款適用性」與案中完整限制（治理等級）。
- **Claude Code**：只有 Gate 真正核准且落盤、CI 合格後才做上述單切片 Preview UI 程式＋針對性測試；由非作者 QA 複核，再由 ChatGPT GitHub Gate/Auto-Ship。
- **最短依賴鏈**：#1162 已合併 → 獨立審閱最小修正路線 → 客戶只裁示**B 的合法適用性**及**限縮施工範圍** → DEC/BL/HANDOFF 落盤 → Code 單切片 → QA/CI → Preview 驗收；無須等 BL-0541 廣域清理。

## 4. 待客戶單點裁示（不是重問手機位置）

**建議核准句**：「我同意 BL-0544 走最小 successor／適用性確認 B：先由獨立稽核確認 44 真實相關條文與頁首導覽無衝突；若無直接衝突，44 不動，較新 DEC 僅取代舊 DEC 的手機導覽位置。完成合法 Gate、精確 UI 線框及獨立 QA 後，授權 Claude Code **只做 Preview 的 ui_v3 手機頁首五頁籤 shell 單切片**，不含資料、OAuth、Phase 7 或 cutover。若查到真實 44 文字衝突，停下按正式 amendment 另裁示。」

> 上述句子是**建議裁示**，未經客戶明示同意以前，不得登記為「已核准」或視為施工許可。
