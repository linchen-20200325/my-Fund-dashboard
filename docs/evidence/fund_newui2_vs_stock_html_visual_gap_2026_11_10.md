# 基金 New UI2 × 使用者台股 HTML 參考稿：視覺差異與最小驗收路線（2026-11-10）

> **性質**：僅 docs-only、唯讀視覺差距盤點；**不是**新的正式 UI SSOT、不得覆蓋已裁示設計、不得據此啟動 UI、資料、OAuth、OneBrain 或金融演算施工。本檔依客戶「沿用既有基金設計＋本次台股 HTML 逐項對照，不重做五頁」的方向整理。來源為使用者在對話提供的 `index(1).html`（台股 AI 戰情室五頁 HTML 概念草稿；**未存入本 repo**），不把該稿視為基金規格或正式資料。比對基準 main `3c463408`；文件與程式若變更須重驗。

## 1. 權威邊界（先於視覺參考）

- **基金正式依據**：`PROJECT_RULES.md` §13.2；`docs/v2/80_new_ui2_architecture_proposal.md`（已核准部分）、`docs/v2/81_new_ui2_wireframe_01_market.md`（🌍 已裁示）、`docs/v2/82_new_ui2_assets_ui_data_evidence_proposal.md`（部分已核准）、`docs/design/new_ui2_full_implementation_blueprint_2026_11_05.md`（歷史候選，**不是整份已核准**）；後續 `DEC-2026-11-06-01`、`DEC-2026-11-03-10` 等較新裁示優先。
- **基金五頁**：🌍 市場與趨勢／💼 我的資產／🔍 找基金／🤖 AI 投資總結／⚙️ 設定。🤖 Phase 7 前不註冊或啟用；只有 🌍 在 `ui_v3/shell/registry.py` 為 `registered=True`。不得為了畫面完整而顯示假資料或空白可用頁。
- **目前 Preview 路徑**：`ui_v3/app_preview.py` 是獨立預覽入口，不等於正式 Cloud cutover。不能因本文件修改正式 App Main、OAuth、正式導航或資料來源。Cloud 實際環境與版本尚無本批實測。
- **股票 HTML 使用範圍**：只參考視覺節奏、卡片層級、mobile-first、顏色候選、可讀性與導覽呈現；**不引用**股票 Risk Cap、EPS×PE、法人籌碼、台股候選公式、股票五頁名稱、買賣訊號；不可讓 DEMO 文案或假資料成為基金正式字樣。

## 2. 逐項差距（不是立即施工清單）

| 維度 | 本次台股 HTML 視覺參考（FACT：使用者檔） | 基金 repo 現況／已裁示（FACT：檔案與契約） | 判斷／最小後續 |
|---|---|---|---|
| 色彩／質感 | 深海軍藍 `#0b1020` 背景、深藍漸層卡片、細邊框、淺字；dark-only | `ui_v3/pages/mkt.py` 是**暫用** CSS；`ui_v3/design/tokens.py` token 僅命名、value=None；深色側欄有既有視覺決策 | **待視覺 Gate**：僅比對 contrast／輔助狀態、產生 token 候選；不得直接複製色票成正式 token |
| 頂層導覽 | 桌機與手機同為頂端雙層橫向五頁籤；手機 `overflow-x:auto` | 基金桌機**左側欄**已裁示；手機方向改為**頁首橫向五頁籤**，目前 `ui_v3/pages/chrome.py` 畫出五格，另有 390px／不橫滑／48px Gate | **部分參考，不搬股票導覽**；桌機維持 sidebar；手機嚴守既有 S1/44 及觸控條件，不把股票的可橫滑做法取代不橫滑規則 |
| 首屏資訊層級 | 首屏大狀態卡＋主要風險＋下一步 CTA，次級指標後置 | `docs/v2/81` 已核准 🌍 首屏 chip／核心數字預算及主比較圖；`docs/v2/80` 17 節規定 shell 與 CTA | **KEEP**：只比較可讀性／視覺密度，不重畫 🌍 內容或改文案門檻 |
| 卡片 | 12-column desktop、單欄 mobile、16px 圓角、層級卡、留白 | `ui_v3/pages/mkt.py` 暫用 `.uv3-card` 8px 圓角及現有間距；正式設計 token 未填值 | **候選**：做 390／768／1280 截圖，對比卡片曲率、行距、密度；不碰金融內容 |
| Primary 圖表 | 大圖卡、註明資料日期；空資料保持空槽不畫假線 | 🌍 正式線框為 TAIEX／S&P 500 比較圖及逐來源／觀測日限制；SVG/缺資料行為有獨立守衛 | **KEEP**：參考圖卡標題／邊框／detail 體驗；不可改共同基準日、歸一化或數值 |
| 狀態與缺值 | `⬜ 無法判定`、`尚未接線`，不填 0；視覺以 pill、empty 等呈現 | `shared/ui_semantics/rules.py` 為正式用字／tone 權威；首屏 chip 名額限制 | **沿用原則**，但詞句必須取基金規則表，不逐字移植股票字詞 |
| 登入／Active Sheet | 頂端 Account／Active Sheet 槽位（均 DEMO） | 基金已有 responsive Google 帳號設計，登入狀態、Active Sheet、資料健康分離；不得臆測已登入 | **不能複製股票假 account**；使用基金現有 OAuth／Session 契約，等待合法施工 Gate |
| 資產頁 | 股票持股表、Risk Cap 卡 | 基金 💼 主配置圖、持有基金／NAV、健康評估、A/B/C 情境等已在 82／藍圖與 handoff 分別標核准／候選 | **僅採卡片節奏**，不移植股票 Risk Cap 或持股演算 |
| 找基金 | 股票兩軌標的與搜尋互動 | 基金 🔍 仍須基金自己的母集合／MoneyDJ／NAV／證據資格；全頁線框未核准 | **只參考搜尋／結果主次層級**，不拿股票候選模型當正式基金選擇規則 |
| AI／診斷 | 股票 OneBrain 獨立呈現、資料健康獨立頁 | 基金 OneBrain Phase 7 前不啟用；⚙️ 集中資料健康；UI ViewModel ≠ Decision Digest | **KEEP 隔離**，不能因參考稿新增第六頁或提前開啟 OneBrain |

## 3. 三條路線（正確性／速度／Token）

| 方案 | 正確性／風險 | 速度／Token | 結論 |
|---|---|---|---|
| A. 把股票 HTML/CSS 直接貼入 `ui_v3` | **高風險**：桌機導航、正式字樣、chip 名額、凍結規格可能衝突 | 表面快／返工高 | 不選 |
| **B. 現有基金版規格 + 股票參考稿做逐元件 visual-only delta，先驗收 🌍** | **低風險**：保留已核准資訊架構與來源語意 | **快／低** | **推薦** |
| C. 五頁全部重新畫稿 | 中高風險：重複設計、失去既有裁示 | 慢／高 | 不選 |

## 4. 最小下一批（僅候選，須另行授權後方能施工）

1. **🌍 視覺驗收**：以 390／768／1280 桌機／手機 Preview 截圖或等效可核對證據，標示 Reference／Current／Delta；先做字級、留白、卡片、圖卡、導覽、首屏 CTA 的**視覺差距清單**。不要因本文件宣稱已測過真實 Cloud、iOS、WebView。
2. **視覺 token 提案**：若需要深藍風格，提出正式 token mapping、contrast、light/dark 限制與兩種外觀對照，獨立視覺 Gate 核准再改 `ui_v3/design/tokens.py`；保持顏色不是唯一狀態載體。
3. **其他頁的施工順序**：以既有 `docs/design/new_ui2_full_implementation_blueprint_2026_11_05.md` 候選為起點；💼／🔍／⚙️ 先完成各頁正式 wireframe Gate 才進 renderer。🤖 留到 Phase 7。不得以「股票模板很完整」推定基金五頁已核准。

## 5. 驗收與停止條件

- 本文件只說「可參考／既有核准／候選待裁示」，**不創造**正式金額、門檻、狀態、日期、資料來源或新 DEC。
- 不修改 `app.py`、`ui_v2/`、`ui_v3/`、`services/`、`data_cache/`、`requirements.txt`、workflow；不碰 OAuth、FX Gate、Eligibility 或 OneBrain。
- 新 UI 程式必須另經凍結文件／44 Amendment Gate、非作者 QA、CI、Cloud 及真機視覺驗收；docs-only merge ≠ UI 已上線。
- **與 FRED P1 資料修復 G2/G3/G4 分批**：本檔既不授權，也不取代 P1 客戶裁示。BL-0545 原唯一 NEXT 保持不變。
