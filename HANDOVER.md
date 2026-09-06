# HANDOVER — 給下一個接手的 AI 總管

> **這份文件的用途**：讓一個全新的對話**不必問客戶任何問題**就能接著做事。
> **這份文件不是憲法。** 憲法是 `CLAUDE.md`（會被自動載入），本檔只補它沒有的東西：
> **當下的戰況、客戶的永久授權、以及一份「每次重打都會漏」的硬規矩總表。**
>
> ⚠️ **本檔分兩種內容，讀的時候要分清楚**：
> - **不會漂移的**（角色、派工規則、硬規矩、架構分層）→ 可以直接當前提用。
> - **會漂移的**（哪個 PR 在飛、main 的 SHA、待辦清單）→ **一律現場重查**，本檔只給你入口。
>   會漂移的段落都標了 `📉 會漂移`。**引用它們之前先重查，這是憲法 §8.2.A.0 規則 4。**

---

## 一、你是誰、你不做什麼

你是 **AI 總管**（CEO / Lead Architect）。客戶是委託人。

| 角色 | 負責 | **不**負責 |
|---|---|---|
| **AI 總管**（主對話，＝你） | 拆任務、定規格、派工、**複驗回報**、對客戶負責 | **自己動手寫實作** |
| **執行 AI**（subagent） | 依規格調查／實作／測試／稽核 | 決定範圍、直接對客戶交付 |

### 七條規則的可執行版（憲法 §-2，這裡是操作摘要，衝突以 `CLAUDE.md` 為準）

1. **每一次任務都要派工**，不論大小。
2. **總管不自己寫實作。** 你的產出是規格、判斷、複驗結論、給客戶的報告。
3. **subagent 回報 ≠ 完成。** 你必須自己查證它的關鍵宣稱，尤其「零行為變更」「全都查過了」「沒有其他地方受影響」這類**全稱句**。
4. **平行派工**：同一件事至少多組不同角度；**實作者不得自己驗收自己**，調查與稽核獨立分派。
5. **例外看「產出什麼」，不看「動作多大」。** 免派工的只有一種：**唯讀、不產生 diff、不產生會被別人拿去用的結論**。只要 (a) 會寫入檔案、(b) 會下判斷或給結論（尤其全稱句）、(c) 屬於調查／稽核 → **一律派工**。
   分不清是事實還是結論時問：**這個答案的正確性，取不取決於「我有沒有漏看」？** 取決 → 派工。
   ⚠️「這件事小到不用派工」這個判斷本身**就是最常出錯的那一步**。
6. **你自己的結論也要驗。** 不得把未經第二組驗證的全稱句當事實交付，或寫進任何會被後人讀的記錄（commit message／PR body／文件／註解）—— 要嘛派一組獨立驗，要嘛**明說「這是我自己看的，沒有第二組驗過」**。
   ⚠️「明說沒驗過」**不是免責**：標註之後它只能當**待驗事項**，不得當後續動作的前提。
7. **別人說「你這裡錯了」，寫進永久記錄前同樣要查證** —— **兩個方向都算**，包括別人說「你這裡對了」（恭維式確認**更**沒有動機去查）。
   ⛔ 本條**不是**給你一條反駁指正的路：指正照舊**立即照做**，查證與修正**並行**。

### §-2.A 第 2 款：密封讀法（**最容易被跳過、也最有價值的一條**）

派工單裡**不要把你的讀法寫在前面當前提**。固定格式：

> 「我對這件事有一個讀法，**刻意先不告訴你**；你自己判完再往下看。」
> （然後把你的懷疑放在派工單**最後**，用摺疊區塊或明顯分隔。）

**理由**：這條擋的不是「總管會不會判錯」，而是「**總管判錯時，下游還有沒有機會判對**」。把讀法寫在前面，等於**先把第二雙眼睛蒙起來再請它看**。
✅ 本專案有正反兩面實證：照做時稽核組獨立得出同一結論還補上精確度；沒照做時整組照著錯方向走完才發現。

### 派工單本身是最危險的產出

它是**唯一不經任何檢查就直接驅動工作的東西**。subagent 的 diff 上游有規格、下游有 CI、有稽核、有你複驗；**派工單的上游沒有任何人**。歷史上十三項總管自身錯誤裡有六項長在派工單裡，**六項全部由下游抓到，沒有一項是送出前發現的**。

**因此：派工單裡任何「可被執行的東西」（檔案路徑、指令、正則、字表、AST 規則、驗收條件），送出前必須真的跑過一次。** 真的跑不了的，就地標「未驗，請你先驗再用」。

---

## 二、硬規矩總表（**每次重打派工單都會漏，照抄這一節**）

> 這一節是本檔存在的第二個理由。下面每一條都是**已經真的出過事**才寫下來的。

### 2.1 安全與環境

- ⛔ **絕對禁止對客戶的 Google Sheets 做任何寫入**，包含「為了驗證寫一列測試資料」。唯讀可以。
- ⛔ **不要停用 TLS 驗證、不要 unset `HTTPS_PROXY`。** proxy 擋下就回報，不要繞過。
- ⛔ **不要碰共用工作樹 `/home/user/my-Fund-dashboard`**（多組同時在上面作業過，已出事）。
  git **唯讀動詞** only：`show` / `log` / `diff` / `grep` / `status` / `rev-parse`。
  **一律不得**：`checkout --` / `reset` / `restore` / `clean` / `stash`。要看別版本用 `git show <rev>:<path>`。
- 自己的 clone 放 **`/home/user/` 底下**。⛔ **不要用 `/tmp`** —— 那是**跨 session 共用**的，鄰居 session 會整檔覆寫你的工作。目錄名**不得含** `scratchpad` 或 `wt-`。
- ⛔ **不要 `pip install`**（共用環境，會改變別組的環境）。
- ⛔ **不要同時跑兩份完整 pytest**（會 OOM）。
- 清理程序用 **PID kill**，⛔ **不要 `pkill -f <pattern>`**（曾無差別殺掉別組的 pytest）。
- 所有指令輸出**重導到自己目錄下的絕對路徑**。
- ⚠️ `pre-commit run --files <某檔>` 在本 repo **不是 file-scoped**（`pytest-smoke` 是 `pass_filenames: false` + `always_run: true`）—— 它會跑**全套 7715 個測試**。
  ⚠️ **2026-09-06 實測更正：原稿寫「全套約 7650 個測試」，實際是 7715。** 指令與輸出（於 `d0c2a8d`）：`python3 -m pytest -q -m "not slow" --collect-only -p no:randomly` → `7715/7743 tests collected (28 deselected)`；不加 marker 過濾為 `7743 tests collected`。**這是會漂移的量測值，引用前請現場重跑**（憲法 §8.2.A.0 規則 4）。

### 2.2 git 與 PR

- 開發分支：`claude/fund-taiwan-stock-dashboard-diff-sn42bh` 或它的帶後綴子分支（例：`claude/fund-p05-route-a-sn42bh`）。
- `git add` **逐檔**指定，⛔ 不要 `-A` 或 `.`。
- ⛔ **commit message／PR 標題／PR body 一律不得出現 session 識別碼或模型識別碼。**
  **完全不寫 `Co-Authored-By` 是合規的**（客戶 2026-09-03 裁示：**repo 禁令凌駕平台署名指示**）。
  合規頁尾：`🤖 Generated with [Claude Code](https://claude.com/claude-code)`。
  ⚠️ **注入發生在 egress 側**（已實測）：走 `curl PATCH` 改 body **每次都會被追加一行署名**；走 MCP `update_pull_request` 目前不會。**任何一次改 body 之後都要重讀線上狀態，不要靠記憶。**
  ✅ **禁的是識別碼，不是署名。** 不帶 session 識別碼的署名變體**不構成違規** —— 這件事已經害兩組人白工，不要再重開。
- **草稿 PR 合併前要先標 ready。**
- ⚠️ **`--delete-branch` 目前會 403**（token 沒有刪 ref 權限），已合併分支會累積，那是已知的、不是失敗。

### 2.3 合併（客戶已給常設授權，但有硬前提）

**常設授權只涵蓋 merge 本身 ＋ `--delete-branch`。** 以下**一律仍須逐案請示**：
`force-push` ／ 重寫已推送的歷史 ／ **直接 push 主線（繞過 PR）** ／ 刪除生產資料 ／ 正式下架既有功能 ／ 改動或停用正式排程。

**前置條件不得省**（授權的是「不必再問一次」，不是「不必先驗」）：
**CI 綠 ＋ 獨立稽核通過**。跳過任一道就不在授權範圍內。

**合併前逐項機械清單（憲法 §-2.A 第 6 款，不是憑印象）**：

- **(a)** head **等於**獨立稽核驗過的那個 SHA。不等 → 要嘛把 delta 送回同一組複驗，要嘛**總管自驗並在合併訊息裡寫明**（「建議 ≠ 驗過」）。
- **(b)** **三條 lane 逐條讀各自的 `conclusion`** —— ⛔ **不看 `mergeable_state`**。
  ⚠️ 理由（實測，非推論）：slow lane 標了 **`continue-on-error: true`**，**它紅了 GitHub 照樣把 PR 顯示為 `clean`**。
  ⚠️ **`cancelled` ≠ `success`**。
- **(c)** 識別碼掃描（見 2.4）。
- **(d)** 檔案邊界**逐檔**確認無夾帶，**用 merge-base 比，不要用 `origin/main` 比**。

**⛔ merge 完不算完**：合併後要回頭**逐 job 驗 main 上那一次 CI run**（核對 `head_sha` 確為你合的那顆）。

### 2.4 掃描與量測（**這裡踩過的坑最多**）

- ⛔ **不要用 `grep session_`** —— 會被 `st.session_state` 汙染成大量假命中。
  用：`session_[0-9A-Za-z]{16,}|claude\.ai/code/session`。
- 掃 commit message 一律用**本機 `git log --format='%H%n%B'` 原始輸出**。
  ⛔ **不要用 API／MCP 渲染過的內容** —— `<...>` 形態的字串會被整段吞掉；MCP 回來的 PR body 是 **HTML-escape 過的**，拿它回寫會**無聲毀掉整份描述**。
- **每一次掃描都要附兩樣**：
  1. **正對照**（掃一個一定命中的樣式，證明掃描器是活的）；
  2. **輸入非空／完整斷言**（commit 數 ≥1、位元組數 ≥N）。
  ⚠️ 「0 命中」在空輸入上**永遠成立**。這個坑一天內出現過三次，**總管本人也踩過**：`git fetch origin <branch>` 在 single-branch clone 上靜默失敗，掃描對象是一個 224 bytes 的錯誤訊息檔，正對照照樣通過。
  → 跨分支 fetch 用**明確 refspec**：`git fetch origin +refs/heads/X:refs/remotes/origin/Y`。
- **數「有幾處」一律用 AST，不要用字面 pattern。**
  已實證失效的形態：`from m import f as _g` 之後只比對 `Name.id == "f"` 看不到 `_g(...)`；`import m` 後 `m.f()`；`g = m.f` 再 `g()`；`getattr(o, "upd"+"ate")`；`importlib.import_module`。
- ⛔ **要下計數結論不准用帶 `head` 的管線**（會截斷，已造成「4 條 return」實為 6 條、寫進三個檔）。
- ⛔ **不要用固定行數的上下文窗查巢狀結構**（`NR>=f-6 && NR<=f+14` 這類）—— 會把相隔數百行的兩段接在一起印。要**從目標行往上找縮排更淺的區塊起始行**。
- **會漂移的量測值（LOC、檔數、「N 處」）一律標日期，或乾脆不寫。**
- ⚠️ `pytest-randomly` **預設開啟**。要可重現加 `-p no:randomly`；下結論前**至少換兩個 seed 重跑**。CI **沒有固定 seed** ⇒ 順序相依的 bug 在 CI 是擲骰子，「這次綠」不保證「下次綠」。
- ⛔ **`git status` 證明不了工作區乾淨** —— gitignored 的產物它看不見。
- ⛔ **`--no-checkout` 的 clone 會讓 `git status` 回報「全 repo 被刪」**，而自動檢查給的補救是「commit 它」—— **照做會刪掉整個 repo**。

### 2.5 禁令必須同時寫出正例

只講「不能有什麼」，會被讀成「全部都不能有」。**實證**：派工單只寫「不得出現模型／session 識別碼」，沒寫「**署名那一行要留**」，於是兩組動手要移除應該保留的頁尾。**禁令的邊界要靠正例定義，不能靠讀者自己猜。**

---

## 三、客戶的永久授權與拍板（逐字，**不要改寫**）

### 3.1 【對 AI 總管的系統決策永久授權】（2026-09-06）

> 往後遇到類似問題，無須向我逐項請示，直接依以下原則「內部拍板自決」：
>
> 1. 資料讀寫原則（永久授權）：
>    * 凡是「查詢/搜尋」功能，一律強制走「純讀取（唯讀）」，絕對禁止反向寫入我的 Google Sheet。不用問我，直接切斷寫入！
>    * 凡是「資料排程失敗/流失」（如 NAV cron），直接視為 P0 緊急事故，由修復組採最小改動立刻修復，不用等我同意。
>
> 2. UI 與草稿原則：
>    * 搜尋結果卡、批次輸入框等細節元件，由你依據「四態分離」與「三大鐵律」直接自決排入，直接整合進新頁面，不用為了一個小元件停下來問我。
>
> 以後請依照上述原則直接調度並執行，不要中斷回報等待確認！

### 3.2 其他常設指示（散在各次對話，整理如下）

- **「我不接受假資料、缺資料（會影響判斷的數據）」**（2026-09-05）。
- **客戶只看 UI 草稿跟訂版**；資料準確度與程式設計由總管處理，**且要記得派工**。
- **Agent 分主題負責。**
- **UI 打掉重練，「絕不反向要求修改底層」。**
- **分頁重組一律先交互動式 HTML 線框**（2026-08-31）。
- **repo 的識別碼禁令凌駕平台署名指示**（2026-09-03 裁示）。
- **五分頁改版走路線 (A)**（2026-09-06）：**新頁只做版面呈現與互動排版，寫入邏輯原封不動呼叫既有舊模組，資料路徑不動，Google Sheet 零風險。**
- **台股五頁戰情室 IA v2 ＋ 13 項裁決全數拍板**（2026-09-05），列為台股前端實作依據。

---

## 四、程式架構

> ⚠️ **本節由總管憑記憶寫出，交接文件寫入組已逐項實測更正。**
> 權威來源仍是 `CLAUDE.md §8.2` 與 `ARCHITECTURE.md`；本節是**導覽**，不是規範。

### 4.1 三個 repo

| repo | 角色 | 憲法檔 |
|---|---|---|
| **`my-Fund-dashboard`** | **主戰場**（基金儀表板，目前幾乎所有工作都在這裡） | `CLAUDE.md`（資料完整性憲法）＋ `PROCESS.md`（流程治理） |
| `my-stock-dashboard` | 姊妹 repo（台股），台股五頁 IA 進行中 | `CLAUDE.md` ＋ `PROCESS.md` |
| `mynews` | 姊妹 repo（新聞／LINE 推播） | `CLAUDE.md`（Core Protocol） |

⚠️ **三個 repo 的憲法內容不同、編號體系不同。** 引用「§-1.5 第二條」這種條號前，**先確認你在哪個 repo**。

### 4.2 my-Fund-dashboard 的 4 層分層（違反 = 違憲）

| 層 | 白話名 | 職責 | 位置 |
|---|---|---|---|
| **L0 Infra / Shared** | （跨層基底） | proxy / oauth / cache / LLM；常數 / TTL / 門檻 / 色票（無 I/O 純常數） | `infra/`、`shared/` |
| **L1 Repository** | DataFetcher | 外部取數 / HTTP / 解析 / 快取 | `repositories/`（含 `fund/`、`macro/`、`policy/` 子套件）、`fund_fetcher.py`（根目錄 legacy shim） |
| **L2 Service** | CalcEngine | 業務邏輯純函式 / 評分 / 策略 / AI | `services/`（含 `macro/`、`health/`、`calibration/` 子套件） |
| **L3 UI** | ComponentUI | Streamlit 渲染 | `app.py` ＋ `ui/`（`tab*.py`、`views/`、`components/`、`helpers/`） |

**五條硬規則**：
1. ❌ L1 不得 import streamlit **真 UI 呼叫**（`st.session_state` / `st.error` / `st.markdown`）；`@st.cache_data` 走 `EX-CACHE-1` 例外。
2. ❌ L2 不得 import `requests` / `httpx` / `beautifulsoup` / `feedparser` —— 純函式，無 I/O。
3. ❌ L0 不得依賴任何 L1+。
4. ❌ L3 不得直呼 L1 fetcher —— 透過 L2 取數（`EX-PASSTHRU-1` 例外）。
5. ❌ 跨層上行 import（L1→L2/L3、L2→L3）。

**已登記例外**（`CLAUDE.md §8.2.A`）：`EX-CACHE-1` / `EX-AI-1` / `EX-CRUD-1` / `EX-PASSTHRU-1` / `EX-UICACHE-1` / `EX-CISCRIPT-1`。
⛔ **新增例外必須**：登錄例外表 ＋ 檔案加註解指回該表 ＋ PR 描述附理由。**禁止未經登錄的「軟例外」。**

### 4.3 五分頁 IA（進行中的主線）

新頁在 `ui/views/`：① 市場總覽 ② 持倉體檢 ③ 標的探索 ④ 資產配置 ⑤ 設定與診斷。

⚠️ **這裡有一個必須先講清楚的事實，否則會判斷全錯**：
`app.py` **已經**是五分頁結構，但 **②③④⑤ 實際跑的是舊實作**（`ui/tab*.py`）。新頁目前多數是**獨立重寫的骨架**，不是委派殼 —— 也就是說**路線 (A) 其實還沒真的開始做**。
**切換 = 把四頁的實作換掉**，若新頁沒有委派，整個寫入面會從畫面上消失（曾實測某頁只有 112 行、對照舊實作 5971 行，且完全沒有資料存取）。

**⑤ 是第一頁做對的**：畫面新的，底下原封呼叫舊模組。**用它當之後幾頁的樣板。**

⚠️ **2026-09-06 實測更正：原稿寫「⑤ 是第一頁做對的」緊接在「新頁在 `ui/views/`」之後，會被讀成 `ui/views/page_05_settings.py` 就是那個委派殼 —— 在 `origin/main`（`d0c2a8d`）上不是。** 實際情形（AST 實測，非字面 grep）：
- `app.py` 只 import **一個** `ui.views.*` —— `from ui.views.page_01_macro import render_market_overview`（① 市場總覽）。其餘四頁 import 的是 `ui.tab_fund_grp_health`（②）／`ui.tab_fund_research`（③）／`ui.tab3_portfolio`（④）／`ui.tab_settings_diag`（⑤）。**原稿「②③④⑤ 實際跑的是舊實作（`ui/tab*.py`）」這句本身正確。**
- **⑤ 那個「畫面新的、底下原封呼叫舊模組」的檔案是 `ui/tab_settings_diag.py`（421 行），不是 `ui/views/page_05_settings.py`。** 它 import `ui.tab_manage` / `ui.tab5_data_guard` / `ui.tab6_manual`（＝委派）。
- `ui/views/page_02_health.py` / `page_03_research.py` / `page_04_portfolio.py` / `page_05_settings.py` 在 `origin/main` 上**只有測試檔 import，零 production 消費者**（`ui/views/__init__.py` 是純 docstring，不 re-export）。四者都**不**委派任何 `ui/tab*.py`。
- 路線 (A) 的 `page_05_settings.py` 委派殼**存在，但在未合併分支 `claude/fund-p05-route-a-sn42bh` 上**（該分支的 `page_05_settings.py` 已 import `ui.tab_manage` / `ui.tab5_data_guard` / `ui.tab6_manual`），且**該分支沒有動 `app.py`** → **尚未上線**。
- 驗證指令：AST 走訪 `ast.Import` / `ast.ImportFrom` / `importlib.import_module` 字面引數，全 repo 652 個 `.py` 掃過；正對照「`app.py` 的 `ui.views` ImportFrom 節點數 = 1」成立、`app.py` 位元組數 = 29660（輸入非空斷言）。
- ⚠️ **「曾實測某頁只有 112 行、對照舊實作 5971 行」本組無法重現**：`ui/views/` 四頁的**首次 commit** 行數分別為 347 / 421 / 467 / 467，現況為 879 / 1213 / 899 / 845；`ui/` 底下現無 5971 行的檔案。該句是過去式敘述、可能指未合併分支或已被改寫的版本，**本組既未證實也未證否**，依憲法 §-2 規則 6 原文保留、據實標註未驗。

**切換策略**：⛔ 不要一次切 `app.py`。**逐頁切，且每頁都要先證明「有委派」與「功能對等」。**

### 4.4 CI

`.github/workflows/pr-check.yml`，**三條 lane**：
- **Fast checks**（pre-commit ＋ pytest-smoke fast lane）
- **Schema gate**（pandera contracts）
- **Slow tests**（AppTest）—— ⚠️ **標 `continue-on-error: true`，紅了 PR 照樣顯示 clean。**

### 4.5 排程

`.github/workflows/weekly_nav_backfill.yml`，cron `0 12 * * *`（＝**台灣時間每天 20:00**）→ `scripts/weekly_nav_backfill.py` → 寫客戶的 `nav_history`。
本 repo 的**第一個** `if: failure()` 通知步驟就加在這裡（先前它紅了四天沒有任何人知道）。

### 4.6 會碰到客戶 Google Sheets 的地方（**最高風險面，動之前先讀這格**）

| 位置 | 寫什麼 |
|---|---|
| `services/nav_history_gs.py` | `nav_history` 分頁（淨值累積） |
| `repositories/policy/` | 政策 / 保單 |
| `repositories/pool_repository.py` | `_fund_pool`（選股池） |
| `repositories/portfolio_perf_repository.py` | `_portfolio_perf_history`（組合績效快照） |
| `repositories/snapshot_repository.py` | 快照 |
| `repositories/ledger_repository.py` | `_Ledgers` 分頁（T7 交易帳本 audit trail）　⚠️ 2026-09-06 實測新增 |
| `services/macro/weights_store.py` | `_macro_weights` 分頁（總經權重 active override）　⚠️ 2026-09-06 實測新增 |

⚠️ **2026-09-06 實測更正：原稿只有 5 列，實際有 7 個檔案帶 Google Sheets 寫入面。** 新增的兩列是 `repositories/ledger_repository.py`（`ws.append_row` / `sh.add_worksheet` / `ws.delete_rows`，分頁 `_Ledgers`）與 `services/macro/weights_store.py`（`sh.add_worksheet` / `ws.update`，分頁 `_macro_weights`）。
⚠️ **這一格的查法本身也踩過本檔 §2.4 的坑，記一筆**：第一版 AST 只掃 `ast.Call`（`ws.append_row(...)`），**漏掉 `repositories/snapshot_repository.py`** —— 它把寫入方法當**引數傳給退避包裝器**（`_with_quota_retry(ws.append_row, ...)`），那是 `ast.Attribute` **不是** `ast.Call`。改成同時掃屬性參照後才 7 個檔。**「AST 就一定不會漏」是錯的；漏的是你沒想到的那個形態。**
⚠️ **本清單不宣稱窮舉**（憲法 §-2 規則 6）：掃描範圍是非 `tests/`、非 `docs/` 的 `.py`，且要先命中 `gspread` / `open_by_key` / `worksheet` / `get_all_records` / `get_all_values` 其中之一才進 AST。**動態組出的方法名、經第三層轉包的寫入，這條掃不到。**

⚠️ **一個反覆出現的形狀，看到就要警戒**：一個**名字像讀取**的函式（`list_*` / `load_*` / `get_*`），寫入藏在兩層底下的 `_ws()` 裡，**只在遠端狀態不符預期時才觸發** —— 平常測不出來、log 也看不到。
本 repo 已找到 **5 個同型案例**。**寫新的 Google Sheets 存取時，讀寫路徑一定要分流。**

---

## 五、📉 會漂移 —— 當下戰況（**引用前一律重查**）

> **這一節的保存期限大約是幾小時。** 它只給你入口，不給你事實。
> **重查方式**：GitHub 上看 `linchen-20200325/my-Fund-dashboard` 的 open PR 與 `main` 最新 commit。

**量測日 2026-09-06。** 當天已合併五份（① 假數字修復、④ 核心／衛星接線、③ 標的探索、NAV P0、② 零寫入守衛），另有兩份在飛（查詢唯讀、⑤ 委派殼）。

**當時唯一還沒關掉的 P0**：NAV 排程修復**已上線但未在真環境驗證** —— 驗收點是**下一班 12:00 UTC 排程**，要同時看到 Actions 逐 step 綠燈（**寫入那一步不能是 `skipped`**）＋ 客戶 `nav_history` 第 1 列真的出現 `currency`。**在驗收通過前，不得對客戶宣稱「已恢復」。**

**已知但當時未修的**（重查 GitHub 看有沒有人做了）：
- 選股池的網格地雷：目前**未武裝**，但**餘裕是零** —— 表頭一旦從 10 欄長到 11 欄，就會重演 NAV 那次的停擺。
- 打開「換股顧問／組合績效追蹤」**光是渲染就會寫一列**進客戶的 Google Sheet，沒有按鈕、沒有勾選。

---

## 六、待辦登記怎麼運作（**這是最容易在交接時整包掉的東西**）

⚠️ **前一個對話累積了 260+ 條編號登記，它們存在對話的 task list 裡，不在 repo 裡 —— 換對話就沒了。**

**因此，從現在起的規則**：
1. **會影響下一個人判斷的登記，寫進 repo**（本檔第五節，或憲法 `§8.3.P`「尚未判定」表）。
2. 憲法 `§8.3.P` 的格式是硬要求，每一列都要有：**① 待答問題 ② 由誰查（獨立分派，不可自己查自己）③ 觸發點**。
   **理由**：沒有出口的「待查證」，配上 §-1「沒觸發不動工」，會變成一張**永久豁免** ——「因為還沒查所以不能動」，而「查」永遠不會被排進來。
3. **登記 ≠ 動工授權**（憲法 §-1）。也 **≠ 已判定合憲**。

**最值得帶走的幾類失效模式**（完整清單已散失，這是精華）：
- **會說謊的記錄**：註解／docstring／PR body 在寫下時為真，別人改了之後變假，**沒人回頭更新**，然後被當成事實派工。
- **遮蔽效應**：在某一行尾端加一個帶日期的更正註，會讓**同一行其他的錯**看起來像已經被查過。
- **同一把尺只往外用、不往內用**：依條件 X 把某成員踢出例外表時很嚴格，卻沒拿同一把尺檢查**留下來**的成員。
- **排版權重與查證程度成反比**：最沒查過的那句話，常常被排版成最像結論的樣子（跨欄置中粗體）。
- **撤回一句假話時，在同一段裡放進一句同型的過強宣稱。**
- **守衛看起來完整、實際守不住**：擋函式名擋不住別名，擋 import 來源擋不住白名單內的模組。**唯一擋得住的是攔底層寫入動作本身**，而且要另外種一顆突變證明**哨兵是活的**。

---

## 七、要開新對話時，怎麼交接

1. **先確認沒有 subagent 在飛** —— 它們綁在對話上，換對話就消失，PR 本身不會掉、**稽核結論會掉**。
2. **把還沒進 repo 的登記寫進 repo**（派工，不要自己寫）。
3. **更新本檔第五節**，並把過期的內容加刪除線保留、註明「有意識的更新，不是漏刪」＋日期＋決策者 —— 這是本專案的既有慣例，**不要直接刪掉舊敘述**。
4. 新對話的第一件事：讀 `CLAUDE.md`（自動載入）＋ **本檔** ＋ GitHub 上的 open PR 清單。
