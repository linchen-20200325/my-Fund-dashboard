# 53｜`nav` 表接來源（「重新取數」淨值層）：盤點與規劃

> 總藍圖 #3（`docs/handover_2026_09_26_latest.md:295`）。基準 commit：**`c15073d`**；本檔的 `檔案:行號` 以 `git show c15073d:<path>` 量測，行號會漂移，引用前請現場重跑。

## §0 性質與授權邊界

- **本檔只是盤點＋規劃，不是動工授權**（`CLAUDE.md §-1`）。客戶 2026-10-09 只授權「盤點＋規劃」；**未授權修改 L3、接新資料來源或不可逆變更**（交接本:295 同列原文）。
- §3 的每一步都要另取授權才能開工；§4 的題目要客戶先裁。
- 本檔不提議任何新資料來源；§3 所列取數路徑皆指向 repo 內既有的 L1（`nav_metrics.py::fetch_nav_with_error`）。

## §1 現況盤點

### 1.1 規格面（`docs/v2/44_fund_ui_ssot.md`）

| 項目 | 現況 | 出處 |
|---|---|---|
| `nav` 表欄位 | 7 欄：`fund_code`、`nav_date`、`nav_orig_ccy`（>0）、`ccy`（ISO 4217）、`source_tier`（`淨值`／`配息`／`市場指標`／`其他`）、`is_estimated`、`fetched_at`（世界協調時間）；主鍵（`fund_code`, `nav_date`）；不補列 | 44:1791-1805；程式鏡像 `services/v2_tables/contract.py::NAV_FIELDS`（contract.py:92） |
| 讀 `nav` 的塊 | HLD-1/2/3/5/6/8；EXP-2/3/6；ALO-2、ALO-6；SET-1（mkt 無） | 各塊「來源」列：44:513、531、542、706、717、760、1066、1089、1189、1321、1455、1629（指令見 §6） |
| SET-5 重新取數 | 層級可選 `淨值`／`配息`／`市場指標`／`其他`；「取數只寫入資料表與 `fetch_log`」；但同塊「來源」欄只寫「寫入對象為 `fetch_log` 全欄」 | 44:1707-1716 |
| §5.3 按鈕禁令 | 「持倉、淨值、配息、保單四張表的內容不由本儀表板產生，本儀表板只讀它們」；元件判準：沒有按鈕的 `action_kind` 會寫入 `holding`、`policy`、`nav`、`dividend` | 44:2288-2294 |
| §3.5 set 頁 | 「本頁可以重新取一次來源，把取回的列寫進資料表與 `fetch_log`」 | 44:1584-1590 |

### 1.2 程式面

| 項目 | 現況 | 出處 |
|---|---|---|
| L2 接線狀態 | `PENDING_TABLES = ("nav", "dividend")`；`WIRED_TIERS = (mi.SOURCE_TIER,)`（只有市場指標） | `services/v2_tables/settings_store.py:69`、`:71`；註記「`nav`、`dividend` 等到 hld 階段再裁」:66-67 |
| hld | 每次開頁即時取淨值、不寫表：`ui_v2/hld/source.py:71` 解代碼 → `:73` `nav_dividend.build_nav_table` → `services/v2_tables/nav_dividend.py:487` 呼叫 L1 `repositories/fund/nav_metrics.py::fetch_nav_with_error`（nav_metrics.py:257）；檔頭明寫「不另疊快取、不寫任何試算表」 | nav_dividend.py:7-9 |
| L1 快取 | `fetch_nav` 掛 `@_daily_cache`（台灣日曆日為界） | nav_metrics.py:158-159 |
| 幣別 | nav_dividend 檔頭：「`fetch_nav` 目前**從不**自報幣別，實務上 `nav.ccy` 只會來自持倉列」 | nav_dividend.py:14 |
| 舊序列退回 | 即時網址全敗退回預存序列時，`fetched_at` 改取 `attrs["cache_updated_at"]`，無則整批不寫；不寫進 `is_estimated` | nav_dividend.py:22-26 |
| alo | `nav` 寫死空列表 | `ui_v2/alo/source.py:116` |
| set | `nav` 寫死空列表；`refetch()` 非 `WIRED_TIERS` 一律 `ValueError` | `ui_v2/set/source.py:120`、`:149-152` |
| exp | 只有假資料入口，無 `ui_v2/exp/source.py` | `ui_v2/app_exp.py:4`；`git ls-tree -r --name-only c15073d ui_v2 \| grep exp` |
| 寫表端 | 設定試算表 `TAB_SPECS` 為四個分頁（`user_setting_log`、`market_indicator`、`fetch_log`、`fetch_log_open`），無 nav 分頁；`git show c15073d:repositories/settings_sheet_repository.py \| grep -n "^def "` 的清單內無 nav 寫入函式；`SOURCE_TIER_VALUES` 含「淨值」 | `repositories/settings_sheet_repository.py:61-64`、`:97-102`、`:105` |
| 淨值層 fetch_log | `open_fetch_log` 已支援任何 `SOURCE_TIER_VALUES` 值（:699-705）；非測試呼叫點只有 `settings_store.py:312`，傳的是 `mi.SOURCE_TIER` | `git grep -n "open_fetch_log(" c15073d -- '*.py'`，排除 `tests/` 後 2 行（定義＋該呼叫點） |
| 既有累積本 | `services/nav_history_gs.py`（`NAV_SHEET_ID`）；nav_dividend 明寫不讀它 | nav_history_gs.py:69-77；nav_dividend.py:9 |
| 匯率 | `FX_OBS_DATE_RULE_VERIFIED = False` ⇒ `fx_twd_per_usd` 不取數、不寫列；alo 市值基準就算有 nav 也缺匯率 | `services/v2_tables/market_indicator.py:63-68` |
| set 文案 | SET-0 `TEXT_PENDING_NAV_DIVIDEND`（:28，只在 nav 與 dividend 都 pending 時印，:348-349）；SET-1 `TEXT_REASON_KIND_PENDING`（:29）；SET-2 `TEXT_REASON_TIER_PENDING`（:30）；SET-5 `TEXT_TIER_NOT_WIRED`（:47）、`TEXT_SET5_NOTE`「目前只有市場指標可以重新取數…」（:54） | `ui_v2/set/live.py` |
| 驗收登記 | ACCEPTANCE 第十一節：SET-0 暫留，等 #3 後 SET-0 與 SET-1／SET-2 一起處理；**未點名 SET-5** | `ACCEPTANCE.md:809-814` |

### 1.3 決策紀錄面

| 項目 | 現況 | 出處 |
|---|---|---|
| 49 Q12 | 客戶 2026-09-26 同意：`market_indicator`、`fetch_log` 先落地；`nav`、`dividend` 等到 hld 階段再裁 | `docs/v2/49_data_integration_plan.md:510` |
| 50 | 設定試算表只有三張表，明寫「`nav`、`dividend` 不在本本試算表裡」 | `docs/v2/50_settings_sheet_design.md:26` |
| 交接本 Q12 | 「選 A（不另存，每次開頁即時抓，有快取）」，自陳「repo 內無原文」 | 交接本:2177 |
| B 句 | 客戶核准 set 頁改成「配息尚未接取數來源；淨值即時取得」；在本機分支 `e7f05bd`，未 push；`c15073d` 內查無此句（見 §6） | 交接本:2176 |
| hld 重新取數鈕 | 客戶 2026-10-09 裁示正式畫面拿掉，隨 #905 合併 | 交接本:332 |
| #1 | 已完成（100%） | 交接本:293 |

## §2 未裁缺口

| 代號 | 缺口 | 依據 |
|---|---|---|
| G1 | `nav` 要不要落地、落在哪，規格與決策紀錄都沒有可引用的原文 | 49:510「等到 hld 階段再裁」；之後無裁示原文 |
| G1′ | 交接本「Q12 選 A」是唯一的「不落地」紀錄，但自陳 repo 內無原文；nav_dividend.py:7 已把它當依據寫進程式 | 交接本:2177；nav_dividend.py:7 |
| G2 | 44 內部衝突：SET-5／§3.5「取回的列寫進資料表」vs §5.3「不寫入 `nav`」；SET-5 自己的「來源」欄又只寫 `fetch_log` | 44:1712、1584、2288-2294、1711 |
| G3 | 若落地，存哪一本試算表沒有規格（50 明文不收） | 50:26 |
| G4 | 不落地時，set 頁拿不到 hld 行程內的即時值 ⇒ SET-1 淨值列結構上永遠空，除非 set 自己取 | 推論，見 §4 Q-C |
| G5 | 淨值層重新取數要對哪些基金取，沒定 | 44 SET-5 只定層級 |
| G6 | 淨值層 `fetch_log` 的顆粒度（一次一列或一檔一列）與部分失敗時的 `outcome` 沒定 | 44 SET-5 判準只要求「新增一列」 |
| G7 | 重新取數後端用 `clear_all_caches` 還是 `global_refresh_all` 未定，兩者都會解除來源冷卻 | 49:539（T5）、49:398 |
| G8 | 舊序列（`cache_updated_at`）的列若寫入或上畫面，怎麼標示 | 49:537（T3）；nav_dividend.py:22-26 |
| G9 | #867（`nav`／`dividend` L2 轉換層）算不算 #3 進度，未判定 | 交接本:339 |
| G10 | 總藍圖 #3 依賴欄「卡在 #1」已過時（#1 已完成） | 交接本:295、293 |

## §3 實作步驟（依依賴排序；每一步都需另取動工授權）

| 步 | 內容 | L1 | L2 | L3 | 動 44 | 新來源 | 需客戶裁 |
|---|---|---|---|---|---|---|---|
| 0 | 客戶裁 Q-A～Q-D（§4） | — | — | — | — | 否 | **是** |
| 1 | 依 Q-A／Q-B 把 44 的 G2 衝突就地更正（SET-5 規則與來源欄、§5.3 禁令、§3.5 一句）；交接本 G10 依賴欄更正 | 否 | 否 | 否 | **是** | 否 | 依裁示落字 |
| 2 | L2 新增淨值層重新取數：對 Q-C 指定的基金經 `fund_keys::resolve_full_keys` 解代碼（現成，hld/source.py:71）→ 清快取 → `nav_dividend.build_nav_table` 重取 → `open_fetch_log("淨值")` 寫 fetch_log（Q-D 語意）。清快取方式（G7／T5）總管自決 | 否（`open_fetch_log` 現成） | **是** | 否 | 否 | 否 | Q-C、Q-D |
| 3 | L2：`WIRED_TIERS` 加淨值；`PENDING_TABLES` 是否移除 `nav` 由總管依 Q-A 決定（連動 alo，見 §5） | 否 | **是** | 否 | 否 | 否 | 否（總管自決） |
| 4 | L3：set `refetch()` 接淨值層；SET-1 淨值列依 Q-C 讀該次 `fetched_at`；alo `nav` 是否改即時取（市值基準仍缺匯率） | 否 | 否 | **是**（目前未授權） | 否 | 否 | 否（但需 L3 授權） |
| 5 | SET-0/1/2/5 新文案出草稿送客戶（Q-E） | 否 | 否 | **是** | 否 | 否 | **是** |
| 6 | 改測試（§5）＋獨立稽核 | 否 | — | — | 否 | 否 | 否 |

**若 Q-A 改選落地**：另加「L1 `settings_sheet_repository.TAB_SPECS` 或另一本新增 nav 分頁與寫入函式」「改 50」「G3、G8 須先定」三項，且屬寫入客戶試算表的變更，須逐項授權。本檔不展開。

## §4 待客戶裁示

### Q-A　淨值存不存、存哪

- **為何 SSOT 決定不了**：44 自相矛盾（G2）；49 Q12 把它延到 hld 階段（49:510）；交接本的「選 A」無 repo 原文（G1′）。
- **總管推薦 (1) 不落地，各頁需要時即時取（L1 有日快取）**。理由：與 hld 現況一致（nav_dividend.py:7-9）、不觸發 §5.3 禁令、不必新開試算表分頁、不必定 G3／G8。代價：G4（set 頁要自己取）、無歷史累積。
- (2) 落地到設定試算表新分頁 —— 要改 50:26 的明文排除。
- (3) 落地到其他試算表 —— G3 無規格。

### Q-B　淨值層「重新取數」寫不寫 `nav`

- **為何 SSOT 決定不了**：SET-5 規則寫「寫入資料表」，SET-5 來源欄與 §5.3 只容許 `fetch_log`（G2）。
- **總管推薦 (a) 不寫 `nav`，只清快取重取並寫 `fetch_log`**。理由：與 Q-A (1) 一致；SET-5 判準（44:1716：`fetch_log` 新增一列、`user_setting` 列數不變）在 (a) 下可驗。
- (b) 寫入 `nav` —— 前提是 Q-A 選落地。

### Q-C　set 頁淨值層對哪些基金取、SET-1 從哪讀

- **為何 SSOT 決定不了**：44 SET-5 只定層級，沒定對象（G5）；不落地時 SET-1 無表可讀（G4）。
- **總管推薦 (i) 取持倉表上的基金；SET-1 淨值列填該次重新取數的 `fetched_at`**（未按過則照現況顯示未取得）。理由：持倉是 hld 已在用的清單，代碼解析現成。
- (ii) 取持倉＋關注清單 —— exp 尚無正式入口，清單來源未定。

### Q-D　部分失敗的燈號語意

- **為何 SSOT 決定不了**：44 只要求失敗原文寫進 `fetch_log.message`（44:1712），沒定一次取多檔時部分失敗怎麼記（G6）。
- **總管推薦：一次重新取數記一列；任一檔失敗 `outcome` 記 `failed`，`message` 逐檔列原文（經遮蔽）**。理由：與市場指標層一次一列的現行寫法同形；記 `failed` 不會把部分失敗講成成功。
- 另一選項：一檔一列 —— 列數隨持倉數放大，SET-2 顯示也要跟著改。

### Q-E　SET-0/1/2/5 新文案

- **為何 SSOT 決定不了**：現行四塊文案都是「尚未接上」語意（set/live.py:28-30、47、54）；B 句後半「淨值即時取得」只在 Q-A 選 (1) 時為真；ACCEPTANCE 十一節只點名 SET-0/1/2，但 SET-5 兩句（`TEXT_TIER_NOT_WIRED`、`TEXT_SET5_NOTE`）同樣會受影響。
- **總管推薦：Q-A、Q-B 裁定後，四塊文案一次出草稿送審**（含 SET-5），不分批改，避免同頁互相矛盾。

### 屬總管自決（不送客戶）

G7 清快取方式（T5）；G8 舊序列標示（只有要加畫面字樣時才送草稿）；`PENDING_TABLES` 與 alo 連動處理；代碼→`full_key` 沿用 `fund_keys`。

## §5 測試連動清單（靜態推論，未實跑）

拿掉 `PENDING_TABLES` 的 `nav` 或改變 set 文案時會連動：

| 測試 | 斷言 |
|---|---|
| `tests/ui_v2/test_alo_source.py:133` | `"nav" in out["notes"]["pending_tables"]` |
| `tests/ui_v2/test_hld_live_assemble.py:526` | `"nav" in _PENDING_TABLES` |
| `tests/ui_v2/test_set_live_logic.py:207`、`:214`、`:219` | SET-0／SET-1／SET-2 的 pending 文案 |
| `tests/ui_v2/test_set_live_page.py:168` | 頁面含上列文案 |

另有 `tests/ui_v2/test_alo_live_logic.py:286`、`tests/ui_v2/test_alo_live_page.py:160` 在說明字串提到 `PENDING_TABLES` 含 `nav`，是否會因此失敗**未判讀**。SET-5 文案若改，相關斷言**未盤點**。

## §6 本檔由誰產出、誰驗過、未查證處（`CLAUDE.md §-2` 規則 6）

- **產出**：文件組單組撰寫；素材來自總管轉述的兩組調查（程式碼角度、規格角度），兩組皆為單組判讀，**未經第二組驗證**。
- **本組以 `git show c15073d:<path>`／`git grep … c15073d` 抽查的 6 點**：
  - (a) 44 §4.2 `nav` 欄位：**對上**，44:1791（標題）-1805（判準）。
  - (b) `PENDING_TABLES`、`WIRED_TIERS`：**對上**，settings_store.py:69、71。
  - (c) hld 即時取、不寫表：**對上**，hld/source.py:73 → nav_dividend.py:487 → nav_metrics.py:257；nav_dividend.py 內查無試算表寫入呼叫（`grep -n "write\|gspread\|open_fetch_log\|sheet"` 只命中字串處理的 `append`）。
  - (d) 設定試算表無 nav 分頁／寫入函式、`SOURCE_TIER_VALUES` 含「淨值」：**對上**，settings_sheet_repository.py:61-64、97-102、105。
  - (e) 44 衝突：**對上，補一處**。§5.3 原文不是「淨值唯讀」字樣，而是「四張表的內容不由本儀表板產生，本儀表板只讀它們」（44:2289）與元件判準（44:2294）；另 SET-5 自己的來源欄只寫 `fetch_log`（44:1711），與同塊規則欄（44:1712）也不一致。
  - (f) 49 Q12 與交接本：**對上**，49:510、交接本:2177。
- **與調查回報不符、以實測為準處**：
  - 調查組 A 稱「Morningstar/Yahoo/FundClear 路徑可自報幣別」。本組抽查 `repositories/fund/sources.py:169`、`:236`、`:507`、`:974`，幣別欄在缺值時填預設值（`"USD"`／`"TWD"`），依 nav_dividend.py:11-13「預設值一律不收」不能當來源自報；且 `fetch_nav` 本身不帶幣別（nav_dividend.py:14）。**本檔未採用該說法。**
  - 客戶核准的 B 句「淨值即時取得」在 `c15073d` 的 `.py` 內查無（`git grep -n "淨值即時取得" c15073d -- '*.py'` 無輸出）；分支 `e7f05bd` 在本機不存在（`git show e7f05bd` 報 bad object），本組無法查證其內容。
- **讀 `nav` 的塊清單**以下列指令得出 12 塊（repo 根執行）。只抓「來源」列寫法，其他欄提到 `nav` 的塊不在其內：

  ```
  git show c15073d:docs/v2/44_fund_ui_ssot.md | awk '/^#### 塊 /{b=$3} /^\| \*\*來源\*\*/{ if ($0 ~ /`nav[.`]/) print NR": "b}'
  ```
- **未查證**：G4 為推論；§5 測試連動未實跑；`TEXT_SET5_NOTE` 等文案改動的測試面未盤點；`services/nav_history_gs.py` 的欄位語意與 44 是否對得上、是否屬未登錄的 L2 直呼 gspread 負債，本組未讀，沿用調查組 A 的說法、**不作結論**；`fetch_nav` 失敗退避與「清快取會解除冷卻」只引 49:398 原文，未實測。
