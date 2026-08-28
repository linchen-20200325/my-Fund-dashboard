# TODO.md — 專案進度追蹤清單

> **用途**：把客戶（2026-08-28）交辦的三階段工作，逐項對照本 repo 的**實測現況**後，
> 落成一份可逐格打勾的階層式進度表。它是「**現在做到哪、下一步卡在誰身上**」的單一看板，
> **不是**規格書（規格看 `CLAUDE.md` / `PROCESS.md` / `SPEC.md`），也**不是**授權書
> （動工授權看 `CLAUDE.md §-1`：沒有 user 指派、沒有實際 bug 觸發 → 停手等指令）。

**建立日期：2026-08-28**

⚠️ **本檔內的量測值會漂移（檔案大小、檔數、分頁數、分支是否存在、grep 命中數），引用前請現場複驗。**
本檔所有「現況」欄位均標明取得證據的**指令或路徑**，就是為了讓後人能自己重跑一次，而不是相信這張表。

---

## 維護規則

1. **每完成一小項才打勾**（`- [ ]` → `- [x]`）。父項只有在**所有子項都打勾**之後才能打勾。
2. **未完成不得跳級**：不得因為「下一項比較好做」就先勾下一項；有 `阻擋者` 的項目，
   在阻擋者未打勾前一律維持 `- [ ]`。
3. **每一項都必須有三欄資訊**：`現況`（實測 + 證據）／`裁決或待辦`／`阻擋者`。
   三欄缺一，該項視為**尚未可動工**。
4. **不得把「客戶原文」直接當現況填進來**。客戶清單有數項對不上本 repo（見下方「§0 客戶清單校正」），
   照抄等於把姊妹 repo 的狀態寫成本 repo 的狀態。
5. **改狀態時要附證據**：把 `現況` 一欄換掉時，同時換掉它後面的指令／路徑／commit hash。
   只改結論不改證據 = 讓這張表開始說謊。
6. **不確定就寫「待查證」**，不要猜一個狀態填進去。對照 `CLAUDE.md §1`：
   **錯誤的數字比沒有數字更危險**；對照 `§-2` 規則 6：**沒查證的宣稱比沒有宣稱更危險**。
7. **全稱句要自標**（「只有這一處」「全都查過了」「沒有其他地方受影響」）——
   依 `CLAUDE.md §-2` 規則 6，這類句子要嘛派一組獨立驗，要嘛就地標明「單組結論，未經第二組驗證」。

---

## §0 客戶清單校正（動工前必讀）

**總管實測發現：客戶交辦的 Phase 1 清單，有數項源自姊妹 repo `my-stock-dashboard`，不是本 repo 的實況。**
以下為逐項對照，**證據均為本組實測**：

| 客戶清單項目 | 實測結果 | 證據 |
|---|---|---|
| 1.1 建立 `src/data/{macro, stock, fund, portfolio}` | **本 repo 無 `src/` 目錄**。姊妹 repo `my-stock-dashboard` **已有** `src/data/`，其子目錄為 `core daily etf macro news notify portfolio proxy sector_flow stock` —— 客戶點名的 macro / stock / portfolio 都在裡面。本 repo 的對應物是 **`repositories/`**（已有 `fund/` `macro/` `policy/` 三個領域子目錄） | 本 repo：`ls -d src` → `No such file or directory`；`ls -d repositories/*/` → `repositories/fund/ repositories/macro/ repositories/policy/`。姊妹 repo：`ls src/data/` |
| 1.4 刪除 `stock_etf_dashboard/`（2,658 行） | **兩個 repo 都沒有這個目錄。** 姊妹 repo 的 git 歷史顯示它**已被刪除**；本 repo **從未有過** | 本 repo：`ls -d stock_etf_dashboard` → `No such file or directory`。姊妹 repo：同樣不存在，且 commit `e4e03f6`「刪除 stock_etf_dashboard/：先驗後刪，附可達性硬證明」 |
| 1.4 `services/fund_batch.py` | **本 repo 確實存在**（10161 bytes，量測日 2026-08-28）。憲法 `§8.2` 記載為「v19.406 批次攤平器；v19.413 RETAINED-LEGACY」 | `ls -l services/fund_batch.py`；`CLAUDE.md §8.2` L2 Service 列 |
| 1.4 「29 個無效測試模組」／「停用的 3 個總經指標模組」 | **待查證** —— 正由**獨立稽核組**實測中，本組手上**沒有清單**。⚠️ 客戶給的是**數量**不是**清單** | `ls tests/*.py \| wc -l` → **326**（量測日 2026-08-28）。此為總數，**不是**無效數 |

⚠️ **關於數量的硬規則**：客戶寫的 29 / 3 是**目標數字，不是驗收標準**。
**實際找到幾個就報幾個，不得為湊數字而刪。** 一個「為了湊到 29」而被刪掉的活檔案，
比留著 29 個死檔案嚴重得多（`CLAUDE.md §-1.5.1c 判定 3`：判「孤兒」要拿 caller 實測，
不能靠檔名或註解自稱）。

### 總管裁決：本 repo 做「取數抽離集中」，但**不改目錄名**

**裁決內容**：Phase 1.1 的「建立 `src/data/...`」在本 repo **不執行**；Phase 1 真正要做的是 **1.2 取數抽離集中**。

**理由（三條）**：
1. **三層架構本 repo 已經有**：`repositories/`（取數層）／`services/`（純計算層）／`ui/`（視圖層）。
   客戶要的分層目標已達成，差別只在**命名**。
2. **改名的代價與效益不成比例**：改目錄名要動數百個 import，**零使用者可見效益**；
   而真正的問題（**取數邏輯散在分頁裡**）改完名之後**依然存在**。
3. **憲法依據**：`CLAUDE.md §-1.5.1c 判定 1` 已就此裁定 —— v3 條文中的 `src/data/` 是
   **分層概念，不是字面路徑**。依據是 v3 條文**首句自陳「AI 總管不寫死硬編碼目錄」**，
   且其路徑列舉處寫的是「**例如**」。

⚠️ **此為總管裁決，客戶可推翻。** 若客戶的本意是「字面改目錄名」，那是一個 **scope 決定**，
走 `CLAUDE.md §8.4 步驟 4`（總管推薦方案：**不改**，理由如上）。請客戶裁示。

---

## Phase 1：資料庫管理、死碼清理與架構解耦（最優先）

- [ ] **Phase 1 總項**（所有子項打勾後才可勾此項）

  - [x] **1.1 動態資料庫分類**　→ **N/A（架構已符合，只是命名不同）**
        - **現況**：本 repo 已有 `repositories/{fund,macro,policy}/` 領域子目錄，
          外加 `services/`（純計算）與 `ui/`（視圖）。**無 `src/` 目錄**。
          證據：`ls -d src` → No such file；`ls -d repositories/*/`。
        - **裁決**：**不改目錄名**（總管裁決，理由見 §0；`§8.4 步驟 4` scope，**客戶可推翻**）。
          依 `CLAUDE.md §-1.5.1c 判定 1`，v3 的 `src/data/` 是分層概念不是字面路徑。
        - **實際要做**：**無**。本項標 `[x]` 的意思是「**已判定不需動工**」，不是「已完成搬遷」。
        - **阻擋者**：無。
        - ⚠️ 若客戶推翻此裁決 → 本項退回 `- [ ]`，並重新走 `§8.1` 架構規劃。

  - [ ] **1.2 取數抽離集中**　⭐ **這是 Phase 1 真正要做的事**
        - **現況**：憲法 `§8.3.P` 已登記 **5 項待判定**（實測 `CLAUDE.md` 該節，量測日 2026-08-28），
          其中與本項直接相關的是：
          - **`P-UIHTTP-1`** —— `ui/components/mk_dashboard.py::_get_benchmark_series`
            在 **UI 層用 `yfinance` 直抓外部行情**（實測該檔第 201–202 行
            `import yfinance as yf` / `yf.Ticker(ticker)`）＋ **`st.session_state` 自建快取**
            （實測第 195 行 `cache_key = "mk_bench_cache"`）。
            它產出的 `Benchmark_Lag` 是**顯示給使用者的業務標籤**，不是連線診斷 ping。
            → **這是 v3 `01`-1「主動搬遷」在本 repo 唯一已確認的適用對象。**
          - **`P-UIGSPREAD-1`** —— `ui/**` 多處直呼 gspread client，
            **是否等同 EX-CRUD-1 的「本地持久化 CRUD」而受豁免，尚未裁決**。
          - **`P-UISUBPROC-1`** —— `ui/sidebar.py` 以 `subprocess` 跑 `git ls-remote origin main`
            對外往返，**算不算「私有資料抓取」尚未裁決**。
        - **待辦**：
          1. **`P-UIHTTP-1` 搬遷方案設計**（取數下沉 `repositories/`、快取歸屬哪一層、
             `bench_ticker` 介面怎麼切）→ 依 `§8.1` 出架構規劃，**這一步禁止寫 code**。
          2. **`P-UIGSPREAD-1` 裁決**（獨立一組；憲法明訂**不得**由補登／回修 `EX-UICACHE-1` 的組承接）。
          3. **`P-UISUBPROC-1` 裁決**（獨立一組；憲法明訂**不得**由登記 C 類的同一組承接）。
        - **阻擋者**：無（可立即開始）。
          ⚠️ 但 **`EX-UICACHE-1` 整列掛在 `P-UIGSPREAD-1` 上**（憲法原文），
          故 `P-UIGSPREAD-1` **未裁決前，不得把新成員收進 `EX-UICACHE-1`**。
        - ⚠️ **`P-UIHTTP-1` 的搬遷屬架構改動，動工前須過 `§8.1`；若同時改到畫面結構，
          另須先出 UI 線框草稿送客戶拍板**（`§-1.5.1c 03`-2 ①）。本組判斷：純取數下沉
          **不改變畫面**，故應**不觸發**草稿 gate —— 但**此為本組單組判斷，未經第二組驗證**，
          實作組動工前須自行複核。

  - [ ] **1.3 核心計算純化**
        - **現況**：`services/` 依憲法 `§8.2` 已明定「L2 Service 不得 import
          `requests` / `httpx` / `beautifulsoup` / `feedparser`」。
          **本組實測**：`grep -rnE "(^|[[:space:]])(import (requests|httpx|feedparser|bs4)|from (requests|httpx|feedparser|bs4)[. ])" services/ --include=*.py`
          → **僅 2 行命中，且兩行都是註解／docstring**
          （`services/fx_regime_service.py:17`、`services/fund_screening.py:6`，內容是
          「不 import requests / httpx / bs4」這種自述句），**無任何真實 import 陳述**。
        - ⚠️ **單組結論，未經第二組驗證。** 且該指令**明確未涵蓋**：
          `urllib` / `socket` / `subprocess` / 第三方 SDK（`yfinance` / `gspread` / `feedparser` 以外者）／
          `importlib` 動態載入／經 `infra.proxy` 等本 repo 內部封裝再包一層的間接呼叫。
          **不得**把「這條 grep 跑過了」讀成「`services/` 已確認純淨」。
          （方法論教訓見 `CLAUDE.md §-1.5.1c 判定 2`：同一個字表缺陷在該節連錯兩次。）
        - **待辦**：派**獨立一組**用**涵蓋所有網路形態**的字表重掃 `services/`，
          並比對是否有經內部封裝的間接 I/O。**在該複掃完成前，本項不得打勾。**
        - **阻擋者**：無（查證可立即開始）；但若查出違反者，其修復**排在 1.2 之後**
          （同屬架構解耦，避免兩組同時改 `services/` 撞檔 —— `§-1.5.1c 00` 多 Agent 派工防撞）。

  - [ ] **1.4 死碼實體刪除**
        - [x] **1.4-a `stock_etf_dashboard/`（2,658 行）→ N/A，本 repo 不存在**
              - **現況**：`ls -d stock_etf_dashboard` → `No such file or directory`（本 repo）。
                姊妹 repo `my-stock-dashboard` **同樣不存在**，且其 git 歷史有
                commit `e4e03f6`「刪除 stock_etf_dashboard/：先驗後刪，附可達性硬證明」。
              - **裁決**：**本項在本 repo 無適用對象，標 N/A。** 客戶此項源自姊妹 repo。
              - **阻擋者**：無。
        - [ ] **1.4-b `services/fund_batch.py` → 待稽核**
              - **現況**：**檔案存在**（10161 bytes，量測日 2026-08-28）。
                憲法 `§8.2` L2 Service 列記載「v19.406 批次攤平器；**v19.413 RETAINED-LEGACY**」。
              - **待辦**：由**獨立一組**實測 production caller 數，判定是活碼還是孤兒。
                ⚠️ 依 `CLAUDE.md §-2` 規則 5，「這個檔**還有** caller 嗎」屬**取決於有沒有漏看**的問題
                → **一律派工，且不可自己查自己**。
                ⚠️ 「RETAINED-LEGACY」是**自稱**，依 `§-1.5.1c 判定 3`：
                **「已自稱 Archive」不是免驗證的通行證**，實際過期與否要靠 caller 實測。
              - **阻擋者**：無（查證可立即開始）；**刪除動作**須等 caller 實測完成。
        - [ ] **1.4-c 「29 個無效測試模組」→ 清單待稽核組回報**
              - **現況**：**本組沒有清單。** 僅知 `tests/*.py` 共 **326 個檔**
                （`ls tests/*.py | wc -l`，量測日 2026-08-28）—— 這是**總數**，不是無效數。
              - **待辦**：等獨立稽核組回報**具名清單**（檔名逐一列出）。
              - ⚠️ **不得憑「29」這個數字動手。** 實際找到幾個就報幾個。
              - **阻擋者**：**獨立稽核組的清單**。清單未到 → **不動工**。
        - [ ] **1.4-d 「停用的 3 個總經指標模組」→ 清單待稽核組回報**
              - **現況**：**本組沒有清單，也未查證是哪三個。**
              - **待辦**：同 1.4-c，等具名清單。
              - **阻擋者**：**獨立稽核組的清單**。
        - ⚠️ **1.4 全項共同的動工紅線**（`CLAUDE.md §-1` ＋ `§-1.5.1c 判定 3`）：
          - GC（垃圾清理）是「**任務內的收尾義務**」，**不是主動巡邏授權**。
            ⛔ **不得**引用本項發動「全 repo 掃孤兒檔」的巡邏。
          - **刪程式碼／死碼／Archive 檔 → 內部自決**（git 保留完整歷史 ＝ 可逆）。
          - **刪正式生產資料**（Google Sheets 帳本／保單、歷史快照、線上 DB 表）→ **必須請示客戶**。
          - **正式下架仍在被使用的既有功能** → **必須請示客戶**（「孤兒 ≠ 沒人用」）。

  - [x] **1.5 FundClear / TDCC 官方淨值路線保留**
        - **現況**：兩條路線的實作**都在**：`repositories/fundclear_offshore.py`、
          `repositories/tdcc_nav_opendata.py`（`ls repositories/`，量測日 2026-08-28）。
          憲法 `§2.1` 亦記載 FundClear（境外主）／TDCC（境內主）為 T1 官方來源。
        - **裁決**：**本項是「不動」** —— 官方淨值路線暫留、排入備援接線。故直接標 `[x]`。
        - ⚠️ **一處據實揭露**：總管交辦時把本項出處寫為「**憲法決定二**」，
          但本組實測 `grep -rn "決定二" *.md docs/*.md` → **0 命中**。
          故本項的出處目前只能記為「**總管口述交辦**」，**未在 repo 文件中查得該編號**。
          若「決定二」另有出處（非 `.md` 檔、或在 PR / commit 描述內），請補上；
          在補上之前，**不得**把「憲法決定二」當成可引用的條文編號。
        - **阻擋者**：無。

---

## Phase 2：介面動線整併與元件化

- [ ] **Phase 2 總項**

  - [ ] **2.1 分頁動線整併**
        - **現況（重要校正）**：客戶原文稱「5 大分頁」，**實測是 7 個頂層分頁**：
          `app.py` 的 `st.tabs(...)` 解出 **7 個** —— `tab_macro` / `tab_health` / `tab_batch` /
          `tab_single` / `tab_portfolio` / `tab_manage` / `tab_ref`。
          **另有巢狀第二層**：`tab_ref` 之內再開 `st.tabs(["🔭 資料診斷", "📖 說明書"])`。
          證據：`grep -n "st.tabs" app.py`；`app.py` 該處上方註解自陳
          「故 **7 個分頁名**全部收進 `story_nav._TAB_LABELS`」。
        - **待辦**：**任何**分頁合併／拆分／改名／欄位增減 → 依 `CLAUDE.md §-1.5.1c 03`-2 ①
          **動工前必須先出文字線框草稿（Wireframe）送客戶拍板**。
          ⛔ **不得**以「v3 禁止重複分頁」或「這只是小改動」為由跳過草稿 gate。
        - **阻擋者**：**客戶對線框草稿的拍板**。草稿未拍板 → 不得寫任何 UI 程式碼。

  - [ ] **2.2 UI 元件化（6 個新元件）**
        - **現況**：已有 **6 個新 UI 元件**的工作在進行中，總管交辦時指為分支
          `claude/fund-ui3b-components-sn42bh`。
          ⚠️ **實測校正**：`git ls-remote --heads origin | grep -iE "ui3b|sn42bh"`
          在 origin 上**只找到 `claude/fund-wireframe-docs-sn42bh` 一個分支**，
          **`claude/fund-ui3b-components-sn42bh` 尚未推送到 origin**（量測日 2026-08-28）。
          → 該工作目前應存在於**某個 agent 的本地 clone**，尚未上遠端。
          **本組未查證其內容**（本任務只新增 `TODO.md`，不讀他組工作區）。
        - **裁決（總管明訂）**：**壓著不合併** —— **等 Phase 1 全部通過測試才放行**。
        - **阻擋者**：**Phase 1 全項打勾 ＋ 測試通過**。
        - ⚠️ 依 `CLAUDE.md §4`（Auto-Ship 常設授權的三道邊界）：merge 免請示，
          但 **CI 綠 ＋ 獨立稽核通過是硬前提**，「不必再問一次」不等於「不必先驗」。

  - [ ] **2.3 Streamlit 效能防護**（防重繪 `st.form`、Checkbox Gate 延遲載入）
        - **現況**：**待查證。** 本組**未跑任何 UI 稽核**，不宣稱本 repo 現況符合或不符合。
          （憲法 `§-1.5.1c 判定 7` 亦把本 repo 的 3 欄網格／Checkbox Gate 現況
          **登記為待稽核項**，明訂「不得在未稽核前宣稱本 repo 已符合」。）
        - **待辦**：派獨立一組做 UI 效能稽核，產出**具名清單**（哪些分頁無 gate、哪些重運算無 form 包）。
        - **阻擋者**：無（稽核可立即開始）；**修復**排在 Phase 1 之後（同 2.2 的放行條件）。
        - ⚠️ **手段自決，版面問客戶**：「用 Checkbox Gate 把重運算擋在點擊之後」屬**內部自決**
          （畫面結構不變）；「把分頁改排成 3 欄網格」屬**版面異動 → 先出草稿**。

---

## Phase 3：測試守衛與資料真實性

- [ ] **Phase 3 總項**

  - [ ] **3.1 突變測試（拿掉修復必須轉紅燈）**
        - **現況**：本 repo 已建立「**拿掉修復，測試必須轉紅**」的慣例
          （憲法 `§-1.5.1c 03`-1 明列「突變測試（拔掉修復邏輯必須轉為紅燈）」為內部自決項）。
        - **待辦**：對 Phase 1 / Phase 2 產出的每一個修復，補上會轉紅的守衛測試。
        - **阻擋者**：**Phase 1 與 Phase 2 的修復本體**（沒有修復就沒有可突變的對象）。

  - [ ] **3.2 四大鐵律的機器守衛**
        - **現況**：總管交辦所述 —— **四大鐵律中有三條目前零機器守衛**（已實測），
          守衛正在建，指為分支 `claude/fund-ui3b-guards-sn42bh`。
          ⚠️ **實測校正（同 2.2）**：該分支**在 origin 上不存在**
          （`git ls-remote --heads origin` 只有 `claude/fund-wireframe-docs-sn42bh`，量測日 2026-08-28），
          應仍在某個 agent 的本地 clone。
          ⚠️ **「四大鐵律有三條零守衛」是總管轉述的實測結論，本組未獨立複驗**，
          也**未查證那四條鐵律具體是哪四條**。→ **待查證**。
        - **待辦**：
          1. 由承接組**具名列出**四大鐵律各是哪一條、各自的守衛現況（有／無／部分）。
          2. 補齊零守衛者的機器守衛（CI gate）。
        - **阻擋者**：無（守衛可獨立於 Phase 1 進行）；
          但**合併順序**同 2.2 —— 依總管明訂，Phase 2/3 的分支等 Phase 1 通過測試才放行。

  - [ ] **3.3 資料真實性驗證（`§1` Fail Loud）**
        - **現況**：憲法 `§1` 已定「寧可炸掉，不可造假」；`§-1.5.1c 02` 另加四條具體要求
          （全 0 序列隱藏該欄不畫假地平線／單位混用強制標「資料疑義」／
          只快取成功結果、失敗退避／介面狀態灰 vs 紅嚴格分離）。
          `§-1.5.1c 判定 4` 已逐條登記本 repo 的符合狀態，其中
          **「失敗時退避，不連續轟炸來源」登記為「未符合 → 新增待辦」**。
        - **待辦**：**待查證** —— 憲法該處另記載有一組平行派工正在實作
          `shared/backoff_policy.py` ＋ `infra/source_backoff.py`，
          但當時**尚未提交、尚未合併、尚未經獨立 QA 稽核**。
          本組**未查證其現況**（本任務不讀他組工作區）。
          → 承接者須**現場確認該實作是否已合併**，再更新本項狀態。
        - **阻擋者**：無（查證可立即開始）。
        - ⚠️ **落地時的已知張力**（憲法就地記載，不得抹掉）：
          `repositories/fund/fx_and_main.py` 的 **positive-only 快取是 v18.275 的刻意設計**
          （`None` 不入 cache，避免 poisoning）。加失敗冷卻**等於把它反過來** ——
          落地時**必須同時滿足兩邊**（冷卻要短於成功 TTL、過期後必須真的重試），
          **不得**以「v3 要退避」為由把 v18.275 的設計理由抹掉。

---

## 附錄 A：Agent 分工對照

客戶指定四種角色。它們對應本 repo 憲法 `CLAUDE.md §-2` 的「**執行 AI**（subagent）」編制 ——
**是編制，不是另一套與 `§-2` 平行的體系**：

| 客戶指定角色 | 憲法對應（`§-1.5.1c 00` 內部虛擬 Agent 團隊） | 本 repo 的典型工作面 |
|---|---|---|
| **資料工程** | 資料工程組 (Data Stewards) | `repositories/**` 取數、清洗、時序對齊、快取設計 |
| **計算服務** | 計算服務組 (Engineers) | `services/**` 純 Python 指標公式、評等、回測、再平衡 |
| **前端 UI** | 前端/UI 組 | `ui/**` Streamlit 視圖、防重繪 `st.form`、Checkbox Gate |
| **紅隊稽核** | 品管與紅隊稽核組 (QA/Audit) | 交付前模擬試用、邊界與相容性測試、突變測試 |

**四條不可鬆動的規則**（全部出自 `CLAUDE.md §-2`，本表只是複述，衝突時以憲法為準）：

1. **每一次任務都要派工**（規則 1）—— 不論大小，調查／實作／測試／稽核都派 subagent。
   ⚠️「這件事小到不用派工」**這個判斷本身就是最常出錯的那一步**（憲法載有三次實證）。
2. **總管不自己寫實作**（規則 2）—— 總管的產出是規格、判斷、複驗結論、給客戶的報告。
3. ⭐ **實作與稽核必須分開派工，不可同一組自己查自己**（規則 4）——
   本檔多處已就地標明「**不得由某某組承接**」（例如 `P-UIGSPREAD-1` 不得由補登／回修
   `EX-UICACHE-1` 的組承接），那些**不是客套話，是硬性限制**。
4. **總管自己的結論也要驗**（規則 6）—— 總管產出的全稱句同樣沒有第二雙眼睛，
   要嘛派一組獨立驗，要嘛**明說「這是我自己看的，沒有第二組驗過」**。
   ⚠️「明說沒驗過」**不是萬用免責**：標註後該宣稱只能當**待驗事項**，
   **不得**作為後續動作的前提，也**不得**寫進 commit message／PR 描述當成已完成的事實。

---

## 附錄 B：本檔目前標為「待查證」的項目（動工前必須先解掉）

| 編號 | 待查證內容 | 誰來查 |
|---|---|---|
| B1 | 「29 個無效測試模組」的**具名清單**（本組只知 `tests/*.py` 共 326 檔，非無效數） | 獨立稽核組 |
| B2 | 「停用的 3 個總經指標模組」的**具名清單**（本組完全未查證是哪三個） | 獨立稽核組 |
| B3 | `services/fund_batch.py` 的 production caller 數（「RETAINED-LEGACY」是自稱，須實測） | 獨立一組，不可自己查自己 |
| B4 | `services/` 是否真的零 I/O（本組的 grep 字表**未涵蓋** `urllib` / `socket` / `subprocess` / 其他 SDK / 動態 import / 內部封裝間接呼叫） | 獨立一組 |
| B5 | `P-UIGSPREAD-1`：`ui/**` 直呼 gspread 是否等同 EX-CRUD-1 的「本地持久化 CRUD」 | 獨立一組，**不得**由補登／回修 `EX-UICACHE-1` 的組承接 |
| B6 | `P-UISUBPROC-1`：`ui/sidebar.py` 的 `subprocess` 對外往返算不算「私有資料抓取」 | 獨立一組，**不得**由登記 C 類的同一組承接 |
| B7 | Phase 2.3：本 repo UI 的 `st.form` 防重繪／Checkbox Gate 現況（本組**未跑任何 UI 稽核**） | 獨立一組 |
| B8 | Phase 3.2：「四大鐵律」具體是哪四條、哪三條零守衛（本組未獨立複驗，也未查證是哪四條） | 承接守衛工作的那一組 |
| B9 | Phase 3.3：失敗退避實作（`shared/backoff_policy.py` / `infra/source_backoff.py`）**是否已合併**（本組未查證） | 承接組現場確認 |
| B10 | 1.5「憲法決定二」的出處（本組 `grep -rn "決定二" *.md docs/*.md` → **0 命中**） | 總管補上出處，或改記為口述交辦 |
| B11 | `claude/fund-ui3b-components-sn42bh` 與 `claude/fund-ui3b-guards-sn42bh` 兩分支的內容與進度（實測 origin 上**均不存在**，應仍在本地 clone） | 各該承接組 |

---

## 附錄 C：本檔的產製方法與盲點（誠實揭露，依 `CLAUDE.md §-2` 規則 6）

**方法**：於本 repo 的獨立 clone 內實跑下列指令，逐項判讀後落筆；
凡未實跑者一律寫「待查證」，**不猜狀態**。

```
ls -d src                                   # → No such file or directory
ls -d repositories/*/                       # → fund/ macro/ policy/
ls -d stock_etf_dashboard                   # → No such file or directory
ls -l services/fund_batch.py                # → 10161 bytes
grep -n "yfinance\|yf\.Ticker\|mk_bench_cache" ui/components/mk_dashboard.py
grep -rnE "(^|[[:space:]])(import (requests|httpx|feedparser|bs4)|from (requests|httpx|feedparser|bs4)[. ])" services/ --include=*.py
grep -n "st.tabs" app.py                    # → 7 頂層 + tab_ref 內巢狀 2
ls tests/*.py | wc -l                       # → 326
git ls-remote --heads origin | grep -iE "ui3b|sn42bh"
grep -rn "決定二" *.md docs/*.md            # → 0 命中
grep -n "P-UIHTTP-1\|P-UIGSPREAD-1\|P-UISUBPROC-1\|P-NAVCACHE-1\|P-NDCCACHE-1" CLAUDE.md
```

（姊妹 repo `my-stock-dashboard` 側為**唯讀**查證：`ls src/data/`、`git log --oneline -1 e4e03f6`。）

**已知盲點（不要當成「全都查過了」）**：

1. ⭐ **本檔全部內容由單一組產出，未經第二組獨立複驗**（`§-2` 規則 6）。
2. **本組只讀 `CLAUDE.md` 的相關節次與上列指令的輸出**，
   **未通讀** `PROCESS.md` / `SPEC.md` / `ARCHITECTURE.md` / `STATE.md` / `BACKLOG.md` / `docs/*.md`。
   若那些檔另有與本表牴觸的敘述，本次**沒查到**。
3. **本組未讀任何他組的工作區**（Phase 2.2 的 6 個元件、Phase 3.2 的守衛、
   Phase 3.3 的退避實作），故那三項的內容與進度**全部是待查證**，不是「已知」。
4. **本組未跑任何測試、未跑任何 UI 稽核**。本檔一個字都不宣稱「本 repo 已符合 X」。
5. **`services/` 純淨性的 grep 字表不完整**（見 B4）。
   **能被一條 grep 推翻的全稱句，不該寫成結論** —— 故本檔在該處寫的是分類敘述加明列未涵蓋範圍，
   而不是「`services/` 已確認乾淨」。
6. **本檔不構成動工授權。** 依 `CLAUDE.md §-1`：user 沒明確指派時 → **停手等指令**。
   ⛔ **不得**因為「TODO.md 上寫了」就去做某一項 —— 那正是 `§-1` 明列的
   「❌ 機械式清 TODO list 充數」與「❌ 因為文件寫了就提議」。
