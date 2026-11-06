# New UI2 手機頁首五頁籤：frozen 44 最小修正案 準備清冊（2026-11-06）

> **性質**：**盤點清冊，僅供日後 `BL-0544` 最小修正案準備使用。不是 amendment、不是授權、不是施工依據；frozen `docs/v2/44`、57、`CONSTITUTION` 本批一字未改。**
> 以下結論皆為**讀法**（單組讀取，未經第二組獨立複驗）；可驗事實已在 `origin/main`（`861628cc`）與相關 PR 分支實開檔案核對，核對不到者標「未驗」。

## 0. 關鍵發現（讀法；與既有說法的落差，不改既有文字）

- 在 `origin/main` 的 `docs/v2/44_fund_ui_ssot.md` 實跑 `grep -c "底部"` → **0**、`grep -ci bottom` → **0**。44 **沒有**任何「底部」或 bottom 字樣。
- 固定底部手機導覽的**出處**是客戶裁示 `DEC-2026-10-27-11`（Gate 4A，「五大主頁底部導航＋頁內跳轉／收合」，見 `docs/DECISIONS.md`、`docs/v2/71` G-19）與 `docs/design/vnext_visual_blueprint.md` SH-3，**不是 44 條文**。
- 44 內的 `768` 是**欄數斷點**（第二節 2.1：≤768 單欄、769–1279 兩欄、≥1280 三欄）；導覽在 768 切換側欄／底部列只見於 `ui_v3/shell/nav.py` 註解與 CSS（`MOBILE_MAX_PX = 768`，註解援引 44 第二節 2.1 的欄數斷點）。
- 因此 `DEC-2026-11-06-01`／`BL-0544`／`docs/v2/80` §18.2 第 1 點所述「44 明寫底部導覽與 768 斷點」**至少一半（底部導覽）未獲驗證**；768 一半僅在「欄數斷點」意義上成立。**本清冊不修改那些既有敘述，只記落差。**
- 讀法：修正案可能走「DEC 指標」路線（`docs/v2/80` §11／NG-5 A／`DEC-2026-11-02-05` 先例）而非改 44 正文；**倉庫對「DEC 指標是否足以構成合法 amendment」沒有明文**（見表 4 沉默處）。

## 1. 44／57／CONSTITUTION 中觸及導覽、視窗、第一屏的條款

| 條款（位置為 `origin/main` 44 內的節標／行） | 與頁首五頁籤的關係（讀法） | 備註 |
|---|---|---|
| 第二節 2.1 三斷點（≈:149–:247） | **silent**：只訂欄數，未訂導覽形式 | 768 歸單欄側已由客戶定 |
| 第七節第三小節之十七（D1 導覽殼，≈:5313）其六 1（≈:5348） | **silent**：「手機跨分類的點擊數…待實機驗證」列為未裁，未裁定手機導覽形式 | 其他項（≤2 互動）見之十七其餘段，未逐條驗 |
| 之二十（≈:5595）其一／其二 | **compatible**：🤖 僅在 Phase 7 進導覽，與頁首五頁籤的「可見不可進」不衝突 | 五頁順序由其一定 |
| 之二十其三 1（≈:5627）手機帳號入口「放進既有的導覽抽屜或精簡帳號控制，不佔主要第一屏」 | **潛在衝突／須定位**：頁首五頁籤消耗頁首高度；「導覽抽屜」字面在方案 B 無對應物 | #1150 帳號入口需與頁籤不重疊 |
| 之十八（≈:5365）其二 4（≈:5384）手機第一屏比桌機更少 | **須重驗**：頁首頁籤占用首屏高度 | 預算數字不得暗中調高（80 §18.2 第 4 點） |
| 之十九（≈:5472）其七 2（≈:5551）結論燈在 390px 首屏 | **須重驗**：同上 | 另須首屏看得到主圖或主數字 |
| 之十九其九／之十五 的截圖與 390px 驗收程序 | **compatible**：程序不綁導覽形式（未逐條驗全文） | |
| 觸控目標、safe-area、WebView、tab bar | **silent**：44 無規則 | 現行規則在 80 §18.2 與 `nav.py` |
| `CONSTITUTION.md:572`、57 §1-3（`:574`）全站底部固定「免責聲明」 | **不是導覽**，不得誤歸類 | 是頁尾固定標註；頁首導覽改版不應動它，但需驗不被遮蓋 |

## 2. 其他假設固定底部導覽的文件（位置以 grep 命中為準；僅列，不改）

| 文件 | 位置／內容 |
|---|---|
| `docs/v2/80` | §4.2 目錄示例（`:165`）、§5 mobile navigation 列（`:191`）、§17.1（`:621–:625`）、§17.2（`:633–:635`）、§17.5（`:654–:665`）、§18.1 末句「44 手機布局／導覽條款仍適用」（`:683`；**需依本清冊關鍵發現複核**） |
| `docs/v2/82` | §5 驗收第 2 點（`:139`，44 既有 budget）、§9 線框末行共用底部五格導航（`:233`） |
| #1150（`design/responsive-login-ui-20261105`） | 手機右上帳號入口 vs 頁首頁籤不得重疊；底部導覽敘述在該分支已標 superseded（`docs/DECISIONS.md` 該分支含 9 處「底部」，未逐一判讀） |
| #1151（`design/new-ui2-full-blueprint-20261105`） | 固定底部五頁籤與線框（未逐檔開讀，未驗） |
| 其他 | `DEC-2026-10-27-11`、`docs/design/vnext_visual_blueprint.md` SH-3（`:219`、`:351`）、`docs/v2/58` §9（`:192`）、`docs/v2/59` §6.5（`:768`、`:809`）、`docs/v2/71` G-19（`:165`）、`BL-0479`／`BL-0484`（BACKLOG，皆 closed） |

## 3. 已編碼底部導覽的現行守衛（僅列，不改）

- `ui_v3/shell/nav.py`：`MOBILE_MAX_PX = 768`、`TOUCH_MIN_PX = 48`、`BOTTOM_NAV_HEIGHT_PX = 60`、`shell_css()`。
- `ui_v3/pages/chrome.py`：`render_navigation`、`disabled_bottom_html`。
- `ui_v3/design/tokens.py`（`nav.bottom`、`nav.item`）與 `tests/ui_v3/test_ui_v3_design_tokens.py`。
- `tests/ui_v3/test_ui_v3_navigation_shell.py`：`test_css_switches_between_sidebar_and_bottom_nav_at_one_breakpoint`（768 切換）、`test_disabled_nav_items_are_not_links_and_say_under_development`、`test_app_has_exactly_one_navigable_page_and_no_empty_shell_pages` 等。
- 登錄表守衛（🤖 Phase 7 前不掛載）：不受頁籤形式影響（讀法）。
- `shared/ui_semantics/rules.py` 的 `shell_nav_*` APPROVED_WORDING：用字不變則不動（讀法）。
- `tests/visual_fidelity/vf_config.py` `VIEWPORTS` 僅 `1280x800`、`390x844`：**沒有 768／769**，為驗收缺口。
- 44 的 md5 鎖：`tests/ui_v2/test_alo_logic.py:262`、`tests/ui_v2/test_exp_logic.py:86` 起；任何 44 文字修改都會使其變紅（先例為更新 md5），另 `tests/test_doc_counters.py`／`tests/doc_counters_baseline.json` 亦牽涉 44。

## 4. 最小修正案必須涵蓋的事項（只列項目，不是正文）

1. 範圍；2. 受影響條款清單（表 1）；3. 路線選擇：改 44 腳註／正文 vs 加 DEC 指標；
4. 保留的語意：≤2 次互動、無空殼頁、390 實機驗證、首屏預算不暗中調高；
5. 帳號入口與頁首頁籤互不遮擋；
6. 驗收項（依 80 §18.2）：390／768／769／1280、WebView、safe-area、無橫向**頁面**溢出、頁籤列可橫向捲動、鍵盤／螢幕閱讀器、48px 觸控區、焦點與目前頁語意、🤖 不可進入；
7. 連動清單：表 2 文件、表 3 守衛與 md5 鎖；
8. 核准者：客戶裁示（`DEC-2026-11-06-01`、`BL-0544`）；先例 `DEC-2026-10-27-02`、`DEC-2026-10-29-06`（合併前需獨立稽核）。

**倉庫沉默處（未決，本清冊不裁）**：`PROJECT_RULES.md` §4 Stop Gate 寫「frozen Constitution／正式母法」但未點名 44；DEC 指標是否構成合法 amendment 未定義；`CONSTITUTION` §5 模板對 44 的適用範圍未定義；「最小」未定義。

## 5. 未驗

#1151 全文、#1150 九處「底部」逐一判讀、44 之十七其餘條款全文、之十九其九／之十五全文、`tests/test_doc_counters.py` 對 44 的具體鎖法、80 §18.1 末句是否需修正。本清冊**未**實跑 UI、未查 GitHub 保護條件。
