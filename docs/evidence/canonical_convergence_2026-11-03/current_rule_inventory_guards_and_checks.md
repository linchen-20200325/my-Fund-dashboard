# 現行規則盤點（續）：d 凍結清單、e 機械檢查、f 未查證、g 守衛測試

基準：origin/main `4d8c07dd`（2026-11-03）。單組寫成，未經第二組驗證。主檔：`current_rule_inventory.md`（同目錄）。

## (d) frozen／append-only 文件清單與合法標示方式

| 文件 | 性質（依據） | 禁止 | 合法的 successor 標示方式 |
|---|---|---|---|
| `docs/v2/CONSTITUTION.md`（子法 1） | 逐位元組存檔；`tests/test_constitution_archive_integrity.py` 釘 sha256 | 任何位元組改動 | 只能經修正案檔（`docs/v2/57`）；現行索引在 `PROJECT_RULES.md`／`DECISIONS` 指向 57 |
| `docs/v2/57_amendment_8_directional_judgment.md` | `tests/test_amendment_8_integrity.py`（引文逐字比對、sha 與 CONSTITUTION 綁定、`PROJECT_RULES`／`DECISIONS` 必須引用 57 路徑） | 改引文區塊、刪被引用路徑 | 只能新增另一份修正案；不改 57 引文 |
| `docs/v2/44_fund_ui_ssot.md` | 凍結 SSOT；有限解凍＋重新凍結的紀錄（第七節第三小節各「之 N」）；全文 0 命中 `ui_v3`／`New UI2`／`DEC-2026-11` | 直接改本文頁名、表格；任何 amendment 須走客戶 G-44 Gate | 已有的合法形式：新增「之 N」小節＋行尾加註＋`DEC` 逐筆列 supersede 範圍；建議用同形式只加一個「New UI2 successor 指標」小節（仍屬 amendment，需 Gate），**或**不動 44、改在 `PROJECT_RULES.md` 0.4 新增「頁面→現行規格」索引（推薦，c-G-4） |
| `docs/evidence/decisions/*.md`（約 50 檔） | 客戶裁示逐字存檔；`docs/evidence/decisions/README.md` 逐檔登記 sha256／大小。**無測試鎖 sha**（本組只在 tests 找到 README 以外沒有直接鎖 evidence sha 的守衛；見 f） | 任何改動、刪除 | 不改本文。若新裁示取代舊裁示，在新 evidence 檔與 `DECISIONS` 新條寫 supersedes；舊檔不動 |
| `docs/DECISIONS.md` | 追加式；「歷史以索引指回原處」；舊條原字保留 | 改寫舊條實質內容 | 新條的 `supersedes／superseded by` 欄；若要機械可查，在檔頭新增「被取代清單」索引（新增段落，不改舊條） |
| `docs/handover_2026_09_26_latest.md`、`handover_2026_09_26.md`、`handover_2026_09_24.md`、`docs/v2/40_handover_2026-09-17.md` | 歷史交接；第 0 節「永遠不准刪」（客戶 2026-09-28） | 刪第 0 節、續寫 | 不動；`HANDOFF` 已指為歷史 |
| root `STATE.md`、`BACKLOG.md`、`TODO.md`、`PHASE1_*.md`、`ARCHITECTURE_AUDIT.md` | 歷史（0.4）；`BACKLOG.md` 檔名被 `ui/tab1_macro.py` 字樣與 `tests/test_batch2_top_card_grid.py` 引用 | 改檔名、刪 | 檔頭加一行歷史指標（`STATE.md` 已有） |
| `ARCHITECTURE.md`（v12.0）、`SPEC.md`（v10.1） | 0.4 未分類；實質為 Old UI 時期規格。`CLAUDE.md` §8.2 引用 `ARCHITECTURE.md v11.0` 作分層證據 | 勿改分層章節（憲法引用） | 檔頭加「Old UI 時期參考；現行 UI 規格見 PROJECT_RULES 0.4」；是否動需客戶同意（屬現行/歷史分類，建議低風險自驗＋1 組稽核） |
| `docs/wireframes/*.html`、`docs/design/*` | 「客戶拍板原件區」（`docs/v2/72` 檔頭自述）；`docs/wireframes/README.md` **不存在** | 改原件 | 不動 |
| `docs/v2/prototype/*.html`（6 檔） | 在 `tests/test_doc_counters.py` 射程；baseline 有 7 筆線框項 | 改句子（baseline 以「檔＋正規化句」為 key，改句＝新違規紅燈） | 不動 |
| `CLAUDE.md`、`PROCESS.md`、`EXCEPTIONS.md` | 位階凌駕（任務已指示 CLAUDE.md 只讀）；`EXCEPTIONS.md` 由 `tests/test_retired_exception_ids.py` 等解析 | — | 不建議改條文；`PROJECT_RULES.md` 已用指標管轄 |
| `docs/v2/79`、`80` | 檔頭自述 Proposal→已裁示並凍結（80：architecture／Reuse Matrix／migration boundary 凍結，五頁 wireframe 與 presentation DEC 由 New UI2 wireframe 重核） | 對「已凍結」部分改語意 | 檔頭已有裁示狀態；加一行「正式條文 successor＝67 §8／PROJECT_RULES」即可（81 同理，81 非 frozen） |
| `docs/v2/72`、`73`、`76`、`78` | 已核准 wireframe，但版面依 NG-5 須由 New UI2 重核；語意保留 | 把版面當現行 | 檔頭加「版面僅 ui_v2 reuse、語意仍有效、successor：<各頁新 wireframe>」；這些檔在 `test_doc_counters` 射程，改句要小心（見 g） |

## (e) 可機械檢查的一致性規則建議（供 canonical consistency test）

> 建議新增單一測試檔（例 `tests/test_canonical_rule_consistency.py`），範圍僅限「現行區」，並**以標記界定現行區**（例 `<!-- CANONICAL:BEGIN -->`／`<!-- CANONICAL:END -->`，或把歷史區移到獨立檔），否則掃描必撞到合法的歷史劃線。每條規則先在 `4d8c07dd` 上跑一次並登記現況命中數，避免上線即紅（參考 `test_doc_counters` 的 baseline 做法與其警告）。

1. **HANDOFF 只有一個 live「唯一下一接手點」**：現行區內「唯一下一(安全)?接手點」出現在未被 `~~…~~` 包住的位置恰好 1 次。（現況：檔頭 40 則中 39 行字樣，僅第一則未劃線——需先清歷史。）
2. **HANDOFF 現行 checkpoint 單則**：Resume Checkpoint 區塊 bullet 數＝1（`PROJECT_RULES.md` 6.1.2「覆蓋、不累加」）。
3. **HANDOFF 的 main SHA 可驗**：檔內「latest verified main＝`<sha>`」所指 sha 必須是 `origin/main` 的祖先（需 git；在 CI 淺 clone 可能不可用，須 skip 並明示）。
4. **現行區不得出現舊頁名當現行口吻**：現行區內「⚖️ 資產配置」「💼 我的持股」只能出現在 `~~…~~` 內或標「HIST／SUP」行；頁名清單必須恰為 `🌍 市場與趨勢／💼 我的資產／🔍 找基金／🤖 AI 投資總結／⚙️ 設定` 的集合與順序（對照 `ui_v3/shell/registry.py::IA_PAGES`，`tests/ui_v3/test_ui_v3_page_registry_guard.py` 已守程式側，這條守文件側）。
5. **現行區不得含 PENDING 字樣**：`擬：`／`PENDING`／`待客戶定字`／`暫時字樣` 於現行區 0 次（`docs/v2/81`、`HANDOFF`、`BACKLOG` BL-0536 列），並與 `ui_v3/viewmodels/preview_wording.py` 空集合對齊。（待新字樣落地後才能啟用。）
6. **Missing 字樣單一來源**：現行區中「資料未備」「資料不足」「無法判定」「此圖目前沒有可畫的資料」的符號前綴組合必須是 `shared/ui_semantics/rules.py` 規則表的字樣子集（沿用 `test_ui_v3_preview_wording_guard` 的作法：文件字樣 ⊆ 規則表）。
7. **一般 UI 禁字**（對 `ui_v3/**` 輸出與 wireframe 的「一般畫面」欄）：`Traceback`、`Exception`、`os.environ`、`module`、`.py`、`reason_code` 原始值、環境變數名（大寫底線 token）不得出現在一般畫面字樣。程式側已有「未知原因代碼不輸出原始代碼」守衛（commit `78060f7a`），文件側待通則落地後補。
8. **每條規則一個權威位置**：建立 `rule → 權威檔#節` 小表（機器可讀，例 `docs/canonical_rule_index.json` 或 `PROJECT_RULES.md` 0.5 表），測試以「規則特徵句」（例「主動回報只有四種」）在 `PROJECT_RULES.md`／`HANDOFF.md`／`BACKLOG.md` 全文只許出現於權威位置；其他位置該句不得出現（偵測 HANDOFF §0 重述）。注意 `CLAUDE.md` §-2.A 第 8 款：**特徵句不得寫進被掃描檔**，應放在測試內並排除測試檔自身。
9. **DECISIONS 取代關係完整**：每個 `supersedes：`欄列出的 `DEC-ID` 必須存在，且該舊條（或檔頭被取代清單）能機械找到 `superseded by`；`DEC-ID` 無孤兒。
10. **BACKLOG 狀態欄單一狀態**：狀態欄第一個詞必須屬 `open／blocked／待客戶裁示／待確認／deferred／in progress／closed`，不得以 `~~…~~ →` 疊層起頭（現況 568 列中 BL-0531／0533／0536 等多列疊層）；列長上限（例 4 KB）以防 BL-0536 式 33.5 KB 單列。
11. **Evidence 唯讀**：`docs/evidence/decisions/*.md` 的 sha256 與 `README.md` 登記一致（目前無守衛，建議補；既有 `README` 已登 sha）。
12. **review 日期戳**：現行區內「latest verified」「Open PR」「CI」類句必須帶日期＋SHA（`PROJECT_RULES.md` HANDOFF §0 第 5 點）。
13. **索引不抄條文**：`PROJECT_RULES.md` 0.5 表內每格長度上限（現況設計即「只放指標、不抄條文」）。

## (f) 本組未能查證／單組結論

1. **客戶 2026-11-03 新方向的原文**（正式字樣、資料健康度、Chart SPEC、mobile-first／chart-first、工程資訊禁入、OneBrain 六區等）：不在 `origin/main`。本檔對這些只依任務描述，無法對照客戶逐字；任何與其「是否取代」的判定都是推測。
2. **BACKLOG 568 列未逐列判讀**：只讀了 BL-0520 以後與抽樣；「127 列含 ui_v2 碼的非 closed 列」是單一 grep 近似值，未判讀是否真過期。
3. **DECISIONS 155 條未逐條讀**：只讀 `DEC-2026-10-24-02`、`10-27-25`、`10-29-06`、`11-02-05`、`11-02-07`、`11-03-01～06` 等相關條。「有無被後續裁示取代但未標示」的全稱判斷**未驗**；`DEC-2026-10-27-25` 舊條本身是否有就地標示未逐字確認。
4. **`docs/v2/` 80 餘檔只讀檔頭＋grep**：`01`～`04`、`10`～`39`、`41`～`43`、`45`～`56`、`58`～`66`、`68`～`70`、`77` 未逐檔判斷其 current／historical 狀態；其中許多（`20`、`21`、`22`、`23`、`24`、`25`、`43`、`59`、`60`、`61`、`62`、`64`）從檔名看是 Old UI／B 線時代草稿，**建議另派一組逐檔分類**（每檔檔頭加「CUR/HIST」）。
5. **proxy（替代指標）治理**：只確認各檔有提及，未讀其規則是否一致。
6. **`SPEC.md`／`STATE.md`／`ARCHITECTURE.md` 內容**：只看檔頭與 grep，未逐段讀；是否有「五頁」「OneBrain」「資料健康」現行敘述——僅確認 OneBrain 0 命中、五頁名稱為 Old UI 版（資產配置 Tab）。
7. **`docs/v2/44` 是否另有與 `PROJECT_RULES` 13.2 第 1 點不同的「頁名」現行敘述**：44 第 2、3 節表頭有行級劃線＋改名（⚖️／💼我的持股），之二十定正式四頁；兩者在同一檔並存，本組未逐處核對一致。
8. **「全稱句」聲明**：本檔中「X 在 main 0 命中」皆為單一 `grep -c`（`PROJECT_RULES.md`、`DECISIONS`、`BACKLOG`、`HANDOFF`、`ARCHITECTURE`、`SPEC`、`docs/v2/4*`、`6*`、`7*`、`8*`、`docs/evidence/decisions/2026-1[01]-*`），**未跨 `ui_v2/**`、`ui_v3/**` 程式與 `tests/` 內文件字串**，未經第二組驗證；`PROCESS.md` 對新規則（Cruise 3.2 以後）的覆蓋只看了檔頭與 `2026-10-16/17` 兩則指標。
9. **README.md**：任務清單提到 `README.md`，`origin/main` 無此檔（`git show` fatal）；`docs/evidence/README.md`、`docs/evidence/decisions/README.md` 存在，後者只列檔案登記。未讀 `docs/evidence/README.md` 內容。
10. **evidence 檔不被測試鎖 sha256**：只在 tests 內做 `evidence/decisions|sha256` 的檔名級 grep，未逐檔讀測試；可能有未被我搜到的守衛。

## (g) 改文件前需注意的測試守衛

> 全部於 `origin/main` `4d8c07dd` 唯讀讀取；未執行測試。

| 守衛 | 鎖什麼 | 改文件時的風險 |
|---|---|---|
| `tests/test_doc_counters.py` ＋ `tests/doc_counters_baseline.json` | `docs/v2/*.md`（`DOCS_GLOBS`：`*.md` 至少 15 個、`prototype/*.html` 至少 5 個）：(A) 含「掃描指令＋數字＋量詞」的句段必須在同句釘 commit SHA；(B) 掃描指令不得寫進被掃檔（指令自計）；(C) 句首「每一個／所有／全部／都」斷言必須附反向檢查指令＋輸出。baseline key＝sha256(檔相對路徑＋NUL＋正規化句)，**不含行號**；「禁止用任何 SHA 重建 baseline，只准手工增補」 | **在 `docs/v2/` 內改寫、搬移、重排含上述三型句子的段落＝新違規紅燈**（已登記句被改字即失效）；新文件須在 `_MD_DOCS` 登記路徑；新增的現行規則表若含計數／全稱句，要預先釘 SHA 或避免該句型。搬移歷史段到別檔也會讓 baseline 的「檔＋句」key 失效 |
| `tests/test_constitution_file_refs.py` | `CLAUDE.md` 內活的路徑引用：存在性＋`路徑:行號` 行號界內；活的＝非刪除線 | 本任務不改 CLAUDE.md，但若把被 CLAUDE.md 引用的檔案（例 `docs/v2/44…`、`ARCHITECTURE.md`、`EXCEPTIONS.md`、`PROCESS.md`）搬動或重命名會紅燈 |
| `tests/test_retired_exception_ids.py` | production code 不得引用已退役 `EX-` ID；解析 `EXCEPTIONS.md` 表格第一格 | 不要改 `EXCEPTIONS.md` 表格第一格格式；勿在文件新增 `EX-` 開頭的第一格 |
| `tests/test_constitution_archive_integrity.py` | `docs/v2/CONSTITUTION.md` sha256 | 不得動 |
| `tests/test_amendment_8_integrity.py` | `docs/v2/57` 引文逐字、sha 綁定、含固定字樣「⬜ 無法判定（資料未備／證據不足）」；**`PROJECT_RULES.md` 與 `docs/DECISIONS.md` 必須引用 57 的路徑** | 改寫 `PROJECT_RULES.md`／`DECISIONS.md` 時不得丟掉對 `docs/v2/57_amendment_8_directional_judgment.md` 的引用；不得改 57 |
| `tests/test_public_repo_name_redaction.py` | 掃全部 `git ls-files` 文字檔，2～4 字 CJK n-gram 加鹽雜湊比對外部教材作者姓名；訊息不印原文 | 搬移／複製歷史段落時要小心不要把含姓名的舊文帶進新檔（已 redacted 者無問題）；新增檔也在掃描範圍 |
| `tests/test_batch2_top_card_grid.py` | 指 root `BACKLOG.md`（檔名） | 勿改名 root `BACKLOG.md` |
| `tests/ui_v3/test_ui_v3_page_registry_guard.py` | 頁序 `mkt／ast／exp／ai／set`；🤖 Phase 7 前不得掛導覽；頁名與 `ui_v2/app_preview.py::PAGES` 逐字一致 | 若文件改頁名，程式側守衛是現行真實來源；兩邊必須同步 |
| `tests/ui_v3/test_ui_v3_preview_wording_guard.py` ＋ `ui_v3/viewmodels/preview_wording.py` | 暫時字樣不得等於或內嵌規則表已核准字樣；畫面輸出可被機器辨識 | **新字樣落地時，這支守衛的語意要同改**（暫時字樣表清空或搬入規則表） |
| `tests/ui_v3/test_ui_v3_preview_not_formal_guard.py`、`tests/ui_v3/test_ui_v3_semantics_rules.py`（讀 `DECISIONS`／`PROJECT_RULES` 字串）、`tests/ui_v3/test_ui_v3_chart_disclosure_contract.py`、`test_ui_v3_market_page_adapter.py`、`test_ui_v3_readonly_guard.py`（皆含 `DEC-2026` 字串） | 程式內註解引用 DEC／PROJECT_RULES | 重編 DEC 號或搬移節次會讓註解引用失效（DEC 號不得回收／改號） |
| `tests/ui_v2/**` 約 70 檔含 `DEC-2026` 字串（註解／docstring 引用）；`tests/visual_fidelity/*` | 同上 | DEC 編號與 `BL-` 編號**不得回收或改號**（`BACKLOG` §2 第 4 點） |
| 其他：`tests/test_public_repo_name_redaction.py`、`tests/test_no_direct_main_push_scripts.py`、`tests/test_dual_track_*` 含 sha256／`PROJECT_RULES`／`CLAUDE.md` 字串 | 本組僅確認提及，未逐檔讀 | 改動前以 `git grep -n "<被改段落特徵字>" -- tests` 現場確認 |
| **無守衛**的現行文件 | `docs/HANDOFF.md`（tests 內 0 命中檔名）、`docs/BACKLOG.md`（只有 root `BACKLOG.md` 一支）、`docs/evidence/decisions/*`（無 sha 守衛） | 這三處改動不會被 CI 擋，反而更需要新增 e 節的一致性測試 |

另：CI 的 pre-commit hook（`trailing-whitespace`、`end-of-file-fixer`、`check-merge-conflict`、`check-added-large-files`）會處理 `.md`（`CLAUDE.md` §-2.A 登記）；`check-added-large-files` 只擋「新增檔」，對既有大檔（DECISIONS／BACKLOG）的修改無效，但**新增的 history 附錄檔若超過 500 KB 會被擋**（上限 `--maxkb=500`）；搬移約 640 KB 的內容需分檔。
