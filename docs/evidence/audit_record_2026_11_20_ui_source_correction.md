# 獨立治理稽核紀錄｜UI 設計來源校正（docs-only）｜2026-11-20

稽核者：fund-independent-qa（非作者；唯讀 Read/Grep/Glob；無寫入、無法執行測試、無法查 GitHub／CI）
被稽核物：8 檔 docs diff（PROJECT_RULES.md §0.4 新增；docs/v2/80、71、55；docs/design/vnext_visual_blueprint.md；docs/BACKLOG.md BL-0536；docs/HANDOFF.md 第 38 行；docs/evidence/code_data_boundaries_readonly_audit_2026_11_05.md）
基準／head SHA：未提供（NOT VERIFIED）；CI／測試日誌：未提供（NOT VERIFIED）
獨立性聲明：與主 session 共享派工來源；僅 context 隔離與無寫入權限，不等於人類層級獨立

## 結論：PASS-WITH-FIXES（Must-Fix 0；Should-Fix 5；Nit 4）
未見：刪歷史、動 frozen 44、改程式、切正式入口、偷渡網址、「已驗收／已確認」宣稱。

## FACT
F1  8 檔皆 docs；每個 '-' 行均有等義保留之 '+' 行或加註（目視；非機械比對）。
F2  PROJECT_RULES §0.4 新增 11 行；標題自述「總管整理，客戶裁示以各 DEC 為準」；無新增授權。
F3  registry.py::IA_PAGES 僅 mkt registered；app_preview.py::main renderers 僅 mkt；nav.py：MOBILE_MAX_PX=768、TOUCH_MIN_PX=48、手機頁首五格、手機隱藏側欄；tests/ui_v3/test_ui_v3_navigation_shell.py:300 斷言無 .st-key-uv3-bottom-nav。
F4  DEC-2026-11-06-01（頁首橫向五頁籤）、DEC-2026-11-07-02（S1：全可見、不橫滑、48px；自述 LEGAL／INDEPENDENT QA UNVERIFIED）已讀；DEC-2026-10-27-11 僅被取代「手機導覽位置形式」。
F5  台股 HTML：DEC-2026-11-09-05 與 fund_newui2_vs_stock_html_visual_gap_2026_11_10.md 均禁止套入基金；PROJECT_RULES REFERENCE ONLY 列忠實。
F6  HANDOFF.md 120 行 ＝ HANDOFF_MAX_LINES(120)，零餘裕；BL-0536 列 7811–7910 bytes ＜ 8000。
F7  71/55 之 B 線 URL＝ui_v2：vf_config.py 註解「B 線預覽站」、55 §1 主檔 ui_v2/app_preview.py。
F8  diff 全文無 URL；ui_v3 Cloud URL／部署 SHA／Cloud 像素驗收均標 NOT VERIFIED。

## Should-Fix
S1 CURRENT 列來源指標超出來源：81 無導覽內容（Grep 0 命中）；80 §18 與兩 DEC 未寫「無左側抽屜」；深色側欄來自 DEC-2026-10-27-09／ui_v3/design/tokens.py。blueprint 指標同樣把「無左側抽屜」歸給兩 DEC。→ 拆來源；「無左側抽屜」標為「程式現況＋使用者 2026-11-20 確認」。
S2 CURRENT 未帶 44 適用性 Gate／獨立 QA 未驗之但書。→ 補一句，避免 CURRENT 被讀成已驗收。
S3 80 §17 註記漏 §17.5 表「可視高度 784」列與結論段「深色模式底部列」（INFERENCE）。
S4 「依實測」措辭過強（實為讀檔）；改「依 nav.py 與守衛測試內容（讀檔；未執行）」。
S5 BL-0536 (c) 插入「改驗頁首導覽配色」為總管重新界定客戶待驗項；加「總管讀法，可被客戶推翻」。

## Nit
N1 「B 線」與 PROJECT_RULES 13.6 的「B（app.py [新] 分頁）」撞名。
N2 「左側抽屜」SUPERSEDED 與 44 約 :5627 帳號抽屜／浮層用詞相近（inventory 已列須客戶定位）；註明僅指主導覽。
N3 六問為新檢查清單，無 DEC 出處；註明「依使用者要求，非 DEC」；第 11、15 節不含這六問本身。
N4 new_ui2_responsive_login 第 72 行「nav.py 目前為底部導覽」為時態落差（檔頭已有 supersession 指標）。

## (f) 仍可能誤導的現行入口
- docs/evidence/bl0536_shell_h5_2026-11-03/README.md（底部列時代結論，無過期註記）
- tests/visual_fidelity/vf_config.py::CLOUD_PREVIEW_URL 與 .github/workflows/pr-check.yml 的 cloud_capture 步驟（B 線 URL 為 Visual Fidelity Cloud 擷取預設；docs-only 不得改，建議登記缺口）

## INFERENCE
I1 HANDOFF 已無餘裕，下次改動須覆寫而非累加。
I2 80 §17.5「可視高度 784」列亦屬底部列時代。
I3 Visual Fidelity 的 Cloud 擷取是 B 線 URL 被誤用為 ui_v3 驗收入口的機械路徑。

## NOT VERIFIED
- 基準／head SHA、CI 日誌、守衛實跑結果；BL-0536 逐字一致（僅目視）；
- B 線 Cloud 實際主檔設定、ui_v3 Cloud URL／部署 SHA／像素驗收；
- 使用者六問原文（無法比對）；
- DEC-2026-11-02-05／-06 與 batch_a_rulings.md 本文（僅取樣）；
- (f) 為單組字面搜尋，未經第二組驗證。

---

## 處置狀態（2026-11-20；整合者據稽核回報續修；仍 docs-only；本表由整合者單組寫成，未經第二組獨立複驗）

> 稽核紀錄全文為上方逐字轉錄（來源：稽核回報原稿）。以下只記每一項「處置於何處」或「未處置，原因」。「讀檔」＝讀 nav.py 與守衛測試內容，未於本批以瀏覽器或 CI 重新量測。

| 項 | 處置 | 位置／原因 |
|---|---|---|
| S1 CURRENT 列來源超出來源 | 已處置 | `PROJECT_RULES.md` §0.4「UI 來源與設計適用性」CURRENT 列拆成 (1) 手機頁首五格：`DEC-2026-11-06-01`／`-11-07-02`＋`docs/v2/80` §18＋`nav.py`；(2) 桌機深色側欄：`DEC-2026-10-27-09`＋`ui_v3/design/tokens.py`；(3)「無左側抽屜」標為程式現況（`nav.py` 手機隱藏側欄）＋使用者 2026-11-20 確認，非 DEC 逐字。`docs/v2/81` 已移出導覽來源（Grep 實測：81 對導覽／底部／側欄／抽屜只有 3 行命中，皆為 Status Bar 與側欄狀態區的 chip 計數，不是導覽設計）。`docs/design/vnext_visual_blueprint.md` 檔頭指標同步拆來源 |
| S2 CURRENT 缺 44 Gate／QA 但書 | 已處置 | `PROJECT_RULES.md` CURRENT 列末句與 blueprint 指標：設計方向已裁示不等於已驗收，`DEC-2026-11-07-02` 的 44 適用性 Gate 與獨立 QA 未驗項不因 CURRENT 升格 |
| S3 80 §17.5 漏「可視高度 784」列與「深色模式底部列」 | 已處置 | `docs/v2/80` §17.5 表該列與結論段，各補「歷史」註記（現行無底部列；現行對應項＝頁首導覽配色，同樣 NOT VERIFIED） |
| S4 「依實測」措辭過強 | 已處置 | `docs/v2/80` §17 首註與 §18.1 末註：改為「依 nav.py 與守衛測試內容（讀檔；未於本批執行）」；全部 8 檔 grep「依實測」於本批新增文字中已無剩餘 |
| S5 BL-0536 (c) 為總管重新界定 | 已處置 | `docs/BACKLOG.md` BL-0536 列：加「總管讀法，可被客戶推翻；頁首導覽配色同樣 NOT VERIFIED」；該列 7979 bytes（<8000，守衛上限） |
| N1 「B 線」撞名 | 已處置 | 首次出現處定義為「`ui_v2` B 線預覽，≠ `PROJECT_RULES.md` 第 13.6 節的 `app.py` `[新]` 並行預覽頁」：`PROJECT_RULES.md` SUPERSEDED 列、`docs/v2/55` 檔頭、`docs/v2/71` §7 註、`docs/HANDOFF.md` 第 38 行（仍 120 行） |
| N2 「左側抽屜」與 44 帳號抽屜用詞相近 | 已處置 | `PROJECT_RULES.md` SUPERSEDED 列與 blueprint 指標註明「僅指主導覽」，帳號抽屜／浮層用語須客戶另定位（見 `docs/evidence/new_ui2_top_tabs_44_amendment_inventory_2026_11_06.md`） |
| N3 六問無 DEC 出處 | 已處置 | `PROJECT_RULES.md` 六問標題標「依使用者要求新增，非 DEC」；原「詳細規則見第 11、15 節」改為「第 11、15 節只規範換對話與交接的一般流程，不含這六問本身」 |
| N4 `new_ui2_responsive_login` 第 72 行時態落差 | 未處置 | 屬歷史檔，且檔頭已有 supersession 指標；依「禁止刪除／改寫歷史文字」不動 |
| (f-1) `tests/visual_fidelity/vf_config.py::CLOUD_PREVIEW_URL` 與 `.github/workflows/pr-check.yml` `cloud_capture` 步驟 | 登記，未處置 | 屬程式／工作流，本批 docs-only 不得改；登記為 `docs/BACKLOG.md` 的 BL-0558（只登記，不構成動工授權），須客戶或總管授權後另開 PR |
| (f-2) `docs/evidence/bl0536_shell_h5_2026-11-03/README.md` 底部列時代結論無過期註記 | 登記，未處置 | 不在本批授權檔案清單；併入 BL-0558「可併加註」 |
| I1 HANDOFF 零餘裕 | 已遵守 | 本批只於第 38 行既有儲存格內改字，仍 120 行；下次改動須覆寫而非累加 |
| NOT VERIFIED（基準 SHA、CI 日誌、守衛實跑、BL-0536 逐字一致、B 線 Cloud 實際主檔、ui_v3 Cloud URL／SHA／像素驗收、使用者六問原文、DEC-2026-11-02-05／-06 全文） | 原狀保留 | 本批只重跑本機守衛（見回報）；其餘仍未驗，不得宣稱已驗 |
