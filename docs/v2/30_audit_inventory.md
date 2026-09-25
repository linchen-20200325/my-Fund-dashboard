# `DB_INVENTORY.md` 稽核報告（盤點稽核組）

**稽核對象**：`/tmp/claude-0/-home-user-my-Fund-dashboard/c73da973-7365-568e-a156-e35eacf720bd/scratchpad/inv/DB_INVENTORY.md`（870 行 / 70,978 bytes）
**基準**：`origin/main = 9cbf03776f2a0ee6bdb5a649efb93352c40baba6`（開工時 `git rev-parse origin/main` 實測，與盤點表自稱一致）
**工作樹 HEAD** `d0c2a8d`，**全程未碰**。稽核用唯讀快照 `/home/user/fund-audit-a`（`git archive origin/main`，747 檔，逐檔 md5 抽驗與 `git show` 相符）。
**稽核日**：2026-09-16　**產出者**：盤點稽核組（單組產出，沒有第三組看過）
**零寫入**：未改 repo 任何檔案、未 commit／push／merge、未碰 `pr829`~`pr834`、未 `git fetch`（`origin/data` 用既有 ref）、未連外部 API、未讀寫任何 Google Sheets。

**方法註記（2026-09-16 補）**：負控字串不得寫進文件；掃描時須排除自身檔案。

---

## 結論

**矛盾 7 條。**（外加 file:line 錯 3 處、不精確 2 處、漏盤下界 5 項。）

**⛔ 本報告不裁決任何一條。** 每條都寫成「A 說 X（出處）／B 說 Y（出處）／兩者不能同時為真」，由客戶決定哪一邊對。

---

## 0. 我用了什麼方法（每條附正對照）

| 方法 | 與生產組的差別 | 正對照 |
|---|---|---|
| **A. 全量 `file:line` 機械檢核** — 自寫 regex 抽出盤點表全部引用，逐一驗「檔案在不在／行號超不超過檔尾」 | 生產組是人工逐條 `awk`；本組是全量自動 | 467 筆引用（415 unique）全數抽出；刻意不過濾，34 筆裸檔名（如 `v2.py:282`）另以上下文解析後重驗 |
| **B. 逐條「宣稱 vs 實際行」比對** — 對每一筆引用，抓出盤點表同一行的反引號識別字，檢查有沒有出現在被引用的那一行（或 ±2 行） | 生產組無此步 | 415 unique 全跑：356 自動命中、59 旗標後**逐條人工讀出原始行**（全部印出核對） |
| **C. 自寫 `tokenize` 識別字普查**（`_tok.py`）— 不用 AST walk，用 token 流數 NAME token，另掃 STRING／COMMENT 抓 `getattr` 動態取用；自動追 `import X as Y` 別名鏈 | **刻意不用生產組的 `refmap.py`**（同工具驗同結論等於沒驗）；失效模式不同 | 正對照 `save_holdings_overview` → def ＋ import ＋ **2 個真呼叫**（`cloud_io.py:289`／`tab3_t7_ledger.py:461`）；`append_ledger_row` → def ＋ import ＋ **1 個真呼叫**（`tab3_t7_ledger.py:699`）。負對照 `<負控串>` → **0** |
| **D. 自寫純 Python parquet footer 解析器 ＋ 自寫 snappy 解壓**（`_parq.py` / `_dict.py`）— 真的解 Thrift compact metadata、真的解壓字典頁 | 生產組用 `strings` 掃位元組；本組**真的解碼**。無 pandas／pyarrow（未 `pip install`） | 同一支解碼器在 `fred_indicators.parquet` 解出 **9 個真實 series 名**（含 `CPIAUCSL`／`WALCL`）—— 非零輸出本身就是正對照 |
| **E. SQLite 實查**（`python3 sqlite3`，`mode=ro`）— 直接從既有 `origin/data` ref 取出 `fund.db`（**未 fetch**） | 生產組亦查 SQLite；本組副本 md5 與其一致（`993fa87d…`），確認查的是同一顆 | `PPIACO`／`PCOPPUSDM` 各 0 列，同一條 SQL 對 `CPIAUCSL` 回 **178**、`WALCL` 回 **797** |
| **F. gspread 讀寫原語全量列舉** — 掃全 repo 每一個 `.worksheet(` / `.worksheets(` / `get_all_records` / `get_all_values` / `.acell(` / `add_worksheet` / `append_row(s)` | 生產組用分頁名字串 grep（`持倉總覽\|HOLDINGS_TAB\|HOLDINGS_COLS`）；本組**從呼叫端反查**，不依賴分頁名拼法 | 掃出 7 個具名分頁常數 ＋ 保單分頁 ＋ `Policies`，與 §1 的 11 個單位一一對得上 |
| **G. 自寫 session_state key 普查**（`_sess.py`）— 除字面量 key 外，**另外**掃屬性式 `st.session_state.NAME` 與非字面量 key | 生產組只掃 `[...]`／`.get`／`.setdefault`／`.pop` | 字面量 key **82** 個（與生產組相符）；另抓到屬性式 18 個、非字面量 key site 147 個 |

**別名陷阱**：C 方法自動追別名，實測抓到 `record_fund` 的兩個別名呼叫（`_rec_fh`＠`ui/tab2_single_fund.py:384`、`_rec_fh3`＠`ui/tab3_portfolio.py:1566`），與盤點表所述完全一致。
**根目錄 shim ＋ 別名**：全 repo 掃 `from fund_fetcher import`，命中 `ui/helpers/portfolio/policy_admin_section.py:774` 的 `from fund_fetcher import get_all_cache_info as _gci`（同時走根目錄 shim ＋ 別名）；另 `fund_fetcher.py:523` 有 PEP 562 模組級 `__getattr__` 動態轉發 —— 本組對本次所有「0 呼叫」判定都另掃 STRING／COMMENT 以覆蓋動態取用，結果為 0。
**子字串陷阱**：C 方法比對的是 token 整體，不是子字串；SQLite 的否定測試同時跑 `=` 與 `LIKE '%PPI%'`／`'%COPP%'` 兩種。

---

## 1. 矛盾清單（7 條）

### 矛盾 1｜`cache/nav/*` 標「活的」，但它唯一的寫入端依盤點表**自己的定義**不算 production

- **A 說**（盤點表 §0，第 14 行（活的定義）與第 21~22 行（production 定義））：「『production』＝ 從 `app.py` 可達的 UI 路徑，或 `.github/workflows/` 有排程的 script。**手動 CLI script**（沒有 workflow 掛它）另行註明，**不當 production**」；「**活的** ＝ 有 production 寫入 **且** 有 production 讀取」。
- **B 說**（盤點表 §2.1，第 260~267 行（8 列）與第 269~270 行）：`cache/nav/*` **8 列全標「活的」**；同一節又寫「寫：`scripts/fetch_nav_cache.py:539`（`save_cache`）—— ⚠️ **`.github/workflows/fetch_nav_cache.yml` 不存在** … → **只剩手動觸發**」。
- **本組實測**：`git ls-tree -r --name-only origin/main | grep '^.github/workflows/'` → **8 個 workflow**，無 `fetch_nav_cache.yml`；`git grep -n "fetch_nav_cache" -- '.github/workflows/*'` → 只有 `update_macro_history.yml:4` 一行**註解**提到它，無任何 workflow 呼叫它。`cache/nav/` 的唯一寫入端為 `scripts/fetch_nav_cache.py:552`（`cache_file.write_text`），讀取端為 `repositories/fund/sources.py:1221`（production ✅）。
- **兩者不能同時為真**：若 §0 的定義成立，寫入端不是 production，該 8 列應落在「只讀不寫」；若 8 列的「活的」成立，§0 那條定義就不成立。
- **旁證（同一把尺在別處是往另一邊倒的）**：盤點表對 `data_cache/macro_thresholds_global.json`（§2.12）與 `snap.json`（§2.17）**確實**套用了「手動 CLI 不算 production」，分別標成「只讀不寫」與「查不到（production）」。**同一條規則在 §2.1 沒有套用。**

### 矛盾 2｜`scripts/accumulate_nav_tw.py` 被列在「寫（CI 排程）」，但 repo 裡沒有任何 CI 排程掛它

- **A 說**（盤點表 §1.6，第 173 行）：「寫（CI 排程）：`scripts/weekly_nav_backfill.py`（`.github/workflows/weekly_nav_backfill.yml`）、`scripts/accumulate_nav_tw.py`」。
- **B 說**（repo）：`git grep -n "accumulate_nav_tw" -- '.github/workflows/*'` → **0 命中**（正對照：同一條指令對 `export_fund_db` 命中 `export_db.yml:39`）。該腳本在 repo 內被記載為**使用者自己 NAS／本機的 crontab**：`docs/NAV_NAS_CRON_SETUP.md:89`「`30 18 * * 1-5  cd /path/to/my-Fund-dashboard && python scripts/accumulate_nav_tw.py`」、`STATE.md:1404` 同一句、`scripts/accumulate_nav_tw.py:18` 自己的 docstring 也是同一句。
- **兩者不能同時為真**：它要嘛是 repo 的 CI 排程，要嘛是 repo 外的 NAS cron。
- **為什麼這條重要**：`nav_history` 是盤點表自己標為「**唯一不可再生**」的那張表（§1.6 第 176 行，引 `ui/tab6_manual.py:652`，本組實測該行逐字相符）。它每天到底有沒有在累積，取決於使用者 NAS 上那條 cron 有沒有在跑 —— 那不在 repo 裡、也不在 GitHub Actions 裡。

### 矛盾 3｜`_Ledgers` 標「活的」，但它唯一的讀取端餵給一個 repo 自陳「無人讀」的 session key；而同一個測試在 §2.3 得到的是「只寫不讀」

- **A 說**（盤點表 §1.4，第 128~130 行）：`_Ledgers` **9 列全標「活的」**；「讀：`ui/helpers/portfolio/policy_admin_section.py:825`（`load_all_ledgers`，`ledger_repository.py:111`）」。
- **B 說**（程式碼）：`ui/helpers/portfolio/policy_admin_section.py:825-832` 只取 `_led_ct = len(_led_df)` 塞進 `st.session_state["_sheet_stats"]`；**同一個檔案 `:843-845` 的註解逐字寫著**：「本處寫入的 `_sheet_stats` **全 repo 沒有任何讀取端**（AST + grep 窮舉：只有這一行寫、無人讀）—— 它的 3 個 `st.metric` 消費者已於 v18.169 隨「📋 保單清單」區塊移除」。
  **本組獨立驗證**：`git grep -n "_sheet_stats" -- .` → `.py` 內只有 `policy_admin_section.py` 的 `:819`(註解)／`:820`(def)／`:829`(**唯一寫入**)／`:843`(註解)／`:871`(呼叫 `_refresh_sheet_stats`)，**零讀取**；另兩筆在 `ARCHITECTURE.md:1046`／`SPEC.md:1312,1321`（文件）。
  另：`ui/tab3_portfolio.py:42` 也 `import load_all_ledgers`，但該檔**只有這一行**提到它，**從未呼叫**。
- **同一把尺在 §2.3 是往另一邊倒的**：盤點表把 `cache/fund_history.json` 6 列標成「**只寫不讀**」，理由逐字是「唯一讀到檔案內容的是 `record_fund` 自己的 read-modify-write，**沒有任何下游消費者**」。
- **兩者不能同時為真**：同一條「有沒有下游消費者」的判準，在 §2.3 產出「只寫不讀」，在 §1.4 產出「活的」。

### 矛盾 4｜`fund.db` 8 列標「活的」，但盤點表同一節與「發現 8」都說本 repo 沒有讀取端

- **A 說**（盤點表 §2.18，第 503~510 行）：`global_index`／`fred_macro`／`fund_universe` 共 **8 列標「活的」**。
- **B 說**（同一節第 514~515 行 ＋ §6 發現 8，第 775 行）：「⚠️ 消費者是**下游另一個 repo**（`export_fund_db.py:4` 明文「供下游 2026_strategy_0719 多智能體系統讀取」），**本 repo 的 UI 不讀它**」。
- **本組實測**：全 repo（排除 `tests/`）搜 `fund\.db|FUND_DB|sqlite3` → 只有 `scripts/export_fund_db.py`（生產者）與 `infra/asset_publish.py:15`（一行註解）。`mcp_server/` 5 個檔**零**資料存取原語（無 `open`／`read_text`／`json.load`／`parquet`／`worksheet`），不構成讀取端。`scripts/export_fund_db.py:4` 逐字相符。
- **兩者不能同時為真**：依 §0 的「活的 ＝ 有 production 寫入 **且** 有 production 讀取」，而 §0 的 production 界定在**本 repo** 之內（`app.py` 可達或本 repo workflow），本 repo 內查不到讀取端 → 該 8 列應為「只寫不讀」；若「活的」成立，那 production 的定義就必須擴到別的 repo。

### 矛盾 5｜`env.ANTHROPIC_API_KEY` / `env.OPENAI_API_KEY` 標「查不到（本 repo 無消費路徑）」，但它自己引的那兩行就是一條 UI 走得到的讀取

- **A 說**（盤點表 §4.2 最後一列，第 690 行）：狀態「**查不到（本 repo 無消費路徑）**」，出處 `infra/llm.py:71,72`，備註「只在 `infra/llm.py` 內取；本 repo 的 AI 走 Gemini」。§0 定義「**查不到** ＝ 兩端都查不到」。
- **B 說**（程式碼，本組逐段追）：
  `infra/llm.py:69-73` — `keys = {"gemini": … , "anthropic": anthropic_key or os.environ.get("ANTHROPIC_API_KEY",""), "openai": … os.environ.get("OPENAI_API_KEY","")}`；
  `infra/llm.py:33` — `_DEFAULT_CHAIN = ["gemini", "anthropic", "openai"]`（gemini 失敗後**會輪到** anthropic／openai）；
  `services/ai_service.py:22` — `from infra.llm import _call_gemini, call_llm`；
  `services/ai_service.py:341` — `return call_llm(prompt, max_tokens=5000, gemini_key=api_key)`，位於 `analyze_portfolio_mk_advisor`（def ＠`:130`）內；
  `ui/tab3_t7_ledger.py:3355` — 呼叫 `analyze_portfolio_mk_advisor`（`ui/tab3_t7_ledger.py:59` import）。`ui/tab3_t7_ledger.py` 由 Tab3 掛載，`app.py` 可達。
- **兩者不能同時為真**：讀取端存在且在 production 路徑上（每次 AI 顧問都會執行那兩行 `os.environ.get`），與「兩端都查不到」互斥。「key 沒設定」與「沒有消費路徑」是兩件事。

### 矛盾 6｜§3 的節標題與 §5.1 的分類名稱，被 §3.1／§3.3 自己的內容推翻

- **A 說**：§3 節標題（第 544 行）「**只活在記憶體、沒有落地的**（`st.session_state`）」；§5.1 統計表（第 710 行）把該節命名為「§3 **只活在 session** 的表格狀結構｜6｜60」。
- **B 說**：§3.1 標題（第 549 行）「`t7_ledgers` — ⚠️ **這一項要更正：它其實有落地**」，其 **15 列狀態全為「活的（有落地）」**；§3.3 標題（第 605 行）「`batch_codes` / `batch_rows` — 批次分析（**有落地**，見 §2.11）」，其中 3 列為「活的」。
- **本組重數**：§3 共 60 列，其中 **18 列**（15 ＋ 3）標為活的／有落地 ＝ 30%。
- **兩者不能同時為真**：一個叫「沒有落地」的分類裡，30% 的列自陳有落地。§3.1 就地加了更正標記，但**節標題與 §5.1 的分類名沒有跟著改**，而 §5.1 是給人抄的摘要表。

### 矛盾 7｜`templates/` 4 列標「只讀不寫」，但它自己的節標題說「程式不讀」

- **A 說**：§0 定義「**只讀不寫** ＝ 有 **production** 讀取，查不到寫入端」。
- **B 說**：§2.20 節標題（第 533 行）「範本 CSV／JSON（`templates/`，供使用者複製，**程式不讀**）」，4 列狀態為「只讀不寫（人讀）」。
- **本組實測**：`git grep -n "nav_history_sample\|preset_funds_sample\|portfolio_backup_sample\|fund_history_sample" -- .` → 排除 `tests/` 後只剩 `templates/README.md:10-14`（文件表格）。**無任何 production 讀取端**（正對照：同型指令對 `preset_funds.json` 在 `.py` 有 5 行命中）。唯一會讀 `templates/` 的是 `tests/test_preset_funds_drift.py`。
- **兩者不能同時為真**：若「程式不讀」成立，依 §0 這 4 列應為「查不到」；若「只讀不寫」成立，就得有一個 production 讀取端。（括號「（人讀）」是盤點表自創的補充，§0 的封閉集合沒有授權這種放寬。）

---

## 2. `file:line` 抽驗

**抽了幾個、怎麼抽的**：
- **全量，不是抽樣**：用自寫 regex 抽出盤點表**全部** `file:line` 引用 —— **467 筆出現、415 個 unique**。34 筆是裸檔名（前文已交代全路徑後的簡寫，如 `v2.py:282`），逐一以章節上下文解析成全路徑後一併驗（另註：`data_registry.py` 與 `json_backup.py` 在 repo 內**各有兩個同名檔**，已確認 §2.7／§2.19 指的是 `ui/helpers/io/` 那一份 —— `ui/helpers/data_registry.py` 只有 12 行、是 v19.204 shim，行號 139 根本不存在）。
- **第一關（機械）**：檔案存不存在 ＋ 行號有沒有超過檔尾 → **467/467 通過，0 失敗**。
- **第二關（內容）**：對 **415 個 unique** 逐一取出真正的原始行，與盤點表同一行的反引號識別字比對 → 356 自動命中；**59 筆旗標後逐條人工讀出原始行核對**（全數印出）。
- **第三關（承重項加驗）**：另對五條承重宣稱相關的約 120 個引用行逐行 `git show origin/main:<path> | awk 'NR==N'` 印出核對（`v2.py`／`_helpers.py`／`ledger_repository.py`／`snapshot_repository.py`／`ledger_service.py`／`infra/cache.py`／`export_fund_db.py`／`fred.py`／`ai_cache.py`／`batch_checkpoint.py`／`config.toml`／§4 的 21 個檔）。
- **全程未經任何 `grep -v` 過濾**，一律 `awk 'NR==N'` 直接印。

**結果：415 個 unique 引用，錯 3 個（0.7%），另 2 個不精確。**

| # | 盤點表位置 | 它寫的 | 實際 | 性質 |
|---|---|---|---|---|
| **E1** | §1.1 讀取端（第 60 行） | `repositories/policy/v1.py:39`（`load_policies`） | `def load_policies` 在 **`:37`**；`:39` 是 docstring 內文「讀回 DataFrame；REQUIRED_COLS 缺欄丟 PolicySheetError，」 | 指到函式內文，差 2 行 |
| **E2** | §4.3（第 698 行） | `config.browser.gatherUsageStats` → `.streamlit/config.toml:11-12` | `:11` 是**空行**、`:12` 是 `[browser]`、該欄實際在 **`:13`**（`gatherUsageStats = false`）。同表 `theme` 的 `:1-6` 與 `server` 的 `:8-10` **都對** | 整段位移 1 行 |
| **E3** | §2.19（第 523 行） | `backup.portfolio_funds[].{12 欄}` → `ui/helpers/io/json_backup.py:28-39` | 12 欄實際在 **`:25-38`**（`:25` `"code"` … `:38` `"div_cash_pct"`）。`:28` 是第 4 欄 `"policy_id"`、`:39` 是 `})` | 範圍起訖各位移 3 行；**欄位數 12 正確** |
| **E4** | §2.19／§3.2（第 523、596、599 行） | 「`json_backup.py:22` 明文剝掉 `series`／`moneydj_raw`」 | `:22` 是 `_slim_funds = []`；那句話在 **`:20`**（docstring「剝掉 series / moneydj_raw 等大物件」） | 不精確（同一錯出現 3 次） |
| **E5** | §2.11（第 410 行） | 消費端 `scripts/audit_6d_coverage.py:143` | `:143` 是「找不到任何批次分析存檔」的**錯誤訊息 print**；真正的消費在 `:141`（`bc.list_recent`）與 `:149`（`bc.load`） | 不精確 |

**沒有出現任務提醒的那兩種形態**：(a) 沒有任何一批行號是「過濾後的序號」；(b) 沒有任何檔案不存在或行號超出檔尾。稿內部也沒有自相矛盾的行號。

**順帶查證：盤點表自己指控既有文件行號漂移那兩筆，本組複驗成立** —— `ui/helpers/io/data_registry.py:139` 實測是一個 `}`；`ui/tab5_data_guard.py:1237` 實測是 `where=_key_where)`；而現行真正的呼叫點 `:208`（`from repositories.macro_repository import fred_get_next_release_date as _fred_next_rel`）與 `:1512`（`… as _diag_next_rel`）**逐字相符**，且兩處確為別名匯入。

---

## 3. 計數複核（本組自己重數）

**全部相符，一個不差。**

| 項目 | 生產組自報 | 本組重數 | 結果 |
|---|---|---|---|
| 盤點單位 | 40 | 40（§1 的 11 個小節 ＋ §2.1~§2.20 的 20 ＋ §3 的 6 ＋ §4 的 3） | ✅ |
| 資料列數 | 264 | **264** | ✅ |
| §1 / §2 / §3 / §4 列數 | 89 / 82 / 60 / 33 | **89 / 82 / 60 / 33** | ✅ |
| 活的 | 183 | **183**（含「活的（有落地）」15） | ✅ |
| 未落地 | 28 | **28** | ✅ |
| 只寫不讀 | 24 | **24**（§1.5 十三 ＋ §2.3 六 ＋ §2.9 五） | ✅ |
| 只讀不寫 | 16 | **16**（含「（人讀）」4） | ✅ |
| 查不到 | 11 | **11**（§2.13 三 ＋ §2.17 四 ＋ §2.15 一 ＋ §2.6 一 ＋ `preset_funds._comment` 一 ＋ §4.2 一） | ✅ |
| 已停用 | 2 | **2** | ✅ |
| session key（字面量） | 82 | **82** | ✅（但見下方漏盤 O2） |
| `fund.db` 總列數 | 25,068 | **25,068**（11,406 ＋ 13,654 ＋ 8） | ✅ |

**方法**：自寫 parser 解析盤點表全部 markdown 表格列，只認 §0 那六個封閉狀態值（含括號變體），跳過 §5 統計表本身。

**一則不算計數錯、但值得記的**：§1.2b 的正文（第 96 行）說 `item_type`／`avg_nav_with_div`／`amount` 三個退役欄是「**已停用**」，而 §5.2 的「已停用 2 列」只涵蓋 `fund.db::us_market` 與 `fund.db::fx`。那三欄沒有被列成表格列，所以 **2 這個數字沒有錯**；但讀正文的人會數到 5。

---

## 4. 五條承重宣稱 —— 本組全部自己驗過一次

### ① 「逐筆帳本有完整落地，而且落兩份」→ **本組實測成立**

- **第一份（`_T7_State.ledger_json`）**：`services/ledger_service.py:158` `def to_dict`，其 `:163-175` 的 `"transactions": [ … ]` 是一個 list comprehension，逐筆吐出 **8 個欄位**（`txn_type`/`txn_date`/`amount_twd`/`fx_rate`/`nav`/`div_per_unit`/`new_units`/`note`）；`:176-182` 的 `"position"` 帶 5 欄。`repositories/snapshot_repository.py:152` `_json.dumps(led_dict, …)` 整串寫入。`:296` `load_all_ledgers_snapshot` → `services/ledger_service.py:186` `from_dict`，`:192-200` 逐筆還原 `Transaction`。
- **第二份（`_Ledgers` 分頁，本組奉命特別查）**：**成立**。`repositories/ledger_repository.py:34` `LEDGER_COLS` 確為 **9 欄**（`:35` policy_id ／ `:36` date ／ `:37` code ／ `:38` action ／ `:39` units ／ `:40` nav_at_action ／ `:41` twd ／ `:42` fee ／ `:43` note —— **逐行實測，九個行號全對**）。**每筆交易一列**：`ui/tab3_t7_ledger.py:674` 的 `_sync_actions_to_sheet(rows_by_pid)`，`:695-701` 雙層迴圈 `for _pid_w, _rows_w in rows_by_pid.items(): for _r_w in _rows_w: append_ledger_row(…)`，每筆一次 `append_ledger_row` → `ledger_repository.py:165` `ws.append_row(_row_values(clean))`。該函式在 UI 有 **3 個上游收集點**（`:1595`／`:1919`／`:2808`，分別對應 A／B／C 三種落帳），另一條 `:1030` 走 `replace_ledgers_for_policy`。
- **本組補一句盤點表沒寫的事實**：`_Ledgers` 那兩個寫入端**都在 OAuth 登入分支內**（`:693`／`:1027` 先 `get_gspread_client_from_oauth`）—— 盤點表 §1.4 有寫，本組複驗逐字成立。**沒登入就只有第一份（`_T7_State` 走 service account 也寫得成），不是兩份。**

### ② 「`_持倉總覽` 只寫不讀」→ **本組用不同方法驗，成立**

- **本組方法（F）刻意不 grep 分頁名**：改從呼叫端反查，列出全 repo（排除 tests）每一個 gspread 讀取原語。結果每一處開的分頁都指向具名常數：`LEDGER_TAB`（`ledger_repository.py:91,115`）、保單分頁 `tab`（`policy/v2.py:93,167,313,345`、`_helpers.py:230`）、`_WS_POOL`（`pool_repository.py:372`）、`_WS_PERF`（`portfolio_perf_repository.py:273,300`）、`T7_STATE_TAB`（`snapshot_repository.py:306,336`）、`_GS_WORKSHEET`（`weights_store.py:181`）、`_WS_NAV`（`nav_history_gs.py:427,764`）。**沒有任何一處開 `HOLDINGS_TAB`。**
- **兩條可能的「隱性讀取」也堵掉了**：`repositories/policy/v2.py:203-205` 的 `load_all_policy_worksheets` 以 `not ws.title.startswith(_RESERVED_TAB_PREFIX)`（`:45` ＝ `"_"`）把底線開頭分頁**濾掉**；`scripts/migrate_v149_schema.py:237-238` 同樣濾 `_` 開頭。所以沒有「讀全部分頁時順便讀到它」的路徑。
- `repositories/snapshot_repository.py` 全檔 `def` 清單實測為：`_with_quota_retry`(67)／`ensure_state_worksheet`(75)／`save_all_ledgers_snapshot`(113)／`_ensure_overview_worksheet`(192)／`save_holdings_overview`(222)／`load_all_ledgers_snapshot`(296)／`get_state_metadata`(332) —— **沒有任何 `load_holdings_*`**。
- C 方法正對照：`save_holdings_overview` → def ＋ import ＋ **2 個真呼叫**（`ui/helpers/cloud_io.py:289`、`ui/tab3_t7_ledger.py:461`）。

### ③ 「同一種保單分頁有兩套 schema、兩個主鍵，兩條路徑都活著」→ **本組逐字複驗成立**

- **v1 那套**：`repositories/policy/_helpers.py:50` `ALL_COLS = REQUIRED_COLS + OPTIONAL_COLS` ＝ `:25-34` 的 8 欄 ＋ `:39-48` 的 6 欄 ＝ **14 欄**。**逐欄行號 14 個全對**（`:26` policy_id … `:47` units）。**`ALL_COLS` 內沒有 `fund_code`** ✅。
- **v2 那套**：`repositories/policy/v2.py:506-517` `ALL_COLS_V2` ＝ **10 欄**。**逐欄行號 10 個全對**（`:507` policy_id … `:516` avg_fx）。**`ALL_COLS_V2` 內沒有 `fund_url`** ✅。
- **`upsert_fund_in_policy` 以 `fund_url` 為主鍵寫 14 欄**：def ＠`:240`；`:244` docstring 逐字「以 fund_url 為主鍵」；`:249` `url = str(row.get("fund_url",""))`；`:251` 沒給就 raise；`:265` `url_idx = header.index("fund_url")`，`:267` 表頭缺 `fund_url` 就 raise；`:272-278` 表頭缺 `ALL_COLS` 任一欄就 `ws.update(f"A1:{_hdr_last}1", [list(ALL_COLS)])` **把表頭改寫成 v1 的 14 欄**；`:282` `cols = ALL_COLS`；`:288` 以 `line[url_idx] == url` 比對定位。
- **`write_policy_v2` 以 `fund_code` 為主鍵寫 10 欄**：def ＠`:794`；v2 偵測鍵見 `:624` `return "fund_code" in cells or "基金代號" in cells`。
- **兩條路徑都活著 —— 本組另外查到一件盤點表沒寫、但讓這條更嚴重的事實**：`ui/helpers/cloud_io.py` 的 `dump_all_to_sheet` **有** schema 分流（`:213` `detect_sheet_schema_version` → `:216-217` 是 v2 就轉走 `_dump_all_to_sheet_v2`），所以那條入口是二擇一；**但 `ui/tab3_portfolio.py:1575` 那個 `upsert_fund_in_policy` 沒有任何 schema 檢查** —— 它位於「➕ 手動加入基金（支援多檔批次）」expander 內（區塊起於 `:1421`），唯一的守衛是 `:1573` 的 `if _pid_b and _client_b:`；該檔的 `_schema_ver == "v2"` 判斷在 `:1012`，屬於另一個不相干的「綁到既有保單」區塊。`ui/tab3_t7_ledger.py:1043` 同樣在 OAuth 分支內、無 schema 檢查。
- ⚠️ **本組只陳述這個事實，不判斷它會不會真的把 v2 分頁的表頭改寫成 v1 14 欄** —— 那取決於 runtime 的表頭內容，本組沒有跑 app（見 §6）。

### ④ 「`PPIACO`（PPI）與 `PCOPPUSDM`（銅價）一列資料都沒有」→ **本組用兩種與生產組不同的方法驗，成立**

- **宣告端**：`scripts/update_macro_history.py:65-74` `FRED_SERIES_IDS` 共 **11** 個，`:72` `"PPIACO"`、`:73` `"PCOPPUSDM"`（逐行實測相符）。
- **parquet 端（本組自寫解碼器，不是 `strings`）**：解 `data_cache/fred_indicators.parquet` 的 Thrift compact footer → `num_rows = 13654`、1 個 row group、schema `date(INT32) / series_id(BYTE_ARRAY) / value(DOUBLE)`、codec **SNAPPY**。自寫 snappy 解壓 `series_id` 的字典頁（offset 35360）→ `page_type=2 (DICTIONARY_PAGE)`、`num_values=9`、PLAIN 編碼，解出 **9 個值**：`BAMLH0A0HYM2 / CPIAUCSL / DGS10 / DGS2 / DGS3MO / DTWEXBGS / M2SL / UNRATE / WALCL`。**無 `PPIACO`、無 `PCOPPUSDM`。**
  **為什麼字典就是全集（本組另外檢掉了一個逃生口）**：走訪該 column chunk 的資料頁 → 只有**一個** `DATA_PAGE`，`num_values=13654`、encoding **`RLE_DICTIONARY`**，**沒有任何 PLAIN 回退頁**。字典編碼沒有 fallback ⇒ 字典即該欄的完整值域。
  **正對照**：同一支解碼器在同一檔吐出 9 個真實 series 名 —— 非零輸出本身就是它會命中的證明。
- **SQLite 端**：從既有 `origin/data` ref 取出 `fund.db`（md5 `993fa87d…`，與生產組副本一致）。`fred_macro` 13,654 列、`2011-06-01`~`2026-09-10`，`GROUP BY series_id` 回 **9 種**、各自列數 `BAMLH0A0HYM2 858 / CPIAUCSL 178 / DGS10 3816 / DGS2 3816 / DGS3MO 3816 / DTWEXBGS 13 / M2SL 179 / UNRATE 181 / WALCL 797`。
  **負測試 ＋ 正對照同批跑**：`series_id='PPIACO'` → **0**、`='PCOPPUSDM'` → **0**、`LIKE '%PPI%'` → **0**、`LIKE '%COPP%'` → **0**；同一批 `='CPIAUCSL'` → **178**、`='WALCL'` → **797**、`LIKE '%CPI%'` → **178**。
- **順帶複驗 §2.18 其餘數字**：`sqlite_master` 只有 **3 張表**（`global_index`／`fred_macro`／`fund_universe`）—— **`us_market` 與 `fx` 不存在** ✅；`global_index` 11,406 列、`2011-06-07`~`2026-09-11`、symbol 恰為 `SPX`(3839)／`TWII`(3726)／`VIX`(3841) ✅；`fund_universe` 8 列 ✅。`export_db.yml:39` 逐字 `python scripts/export_fund_db.py --no-live --output fund.db` ✅、cron `0 21 * * *` ✅。

### ⑤ 「`/tmp/fund_cache/*` 那整組 disk cache 是死碼」與「`fund.db` 本 repo UI 不讀」→ **兩條本組都驗，成立**

- **`/tmp/fund_cache/*`**：C 方法（tokenize ＋ 別名鏈 ＋ STRING／COMMENT 掃描）對 6 個函式普查 → **36 筆命中，全部是定義或 re-export import**：定義在 `infra/cache.py:856/882/894/913/926/945`；re-export 在 `fund_fetcher.py:340-345` 與 `repositories/fund/{sources,nav_metrics,fx_and_main,fund_orchestration}.py` 的 import 清單。**零呼叫點、零 STRING 命中（＝沒有 `getattr` 動態取用）。** 正對照見 §0 表格；負對照回 0。
  另：`fund_fetcher.py:523` 的模組級 `__getattr__` 對這 6 個名字不會觸發 —— 它們在 `:336-346` 是**靜態 import**。
  §2.13 的行號本組逐行印出核對，**全對**：`:845` `_CACHE_DIR = "/content/fund_cache" if … else "/tmp/fund_cache"`、`:851` `_cache_path`、`:870` 讀 nav（`_pd.read_csv`）、`:888` 寫 nav（`s.to_csv(fp, header=["nav"])`）、`:903` 讀 div、`:919` 寫 div、`:947-950` 的 meta 13 個 key（本組實數 **13** 個）。
- **`fund.db` 本 repo UI 不讀**：見矛盾 4 的 B 段 —— 全 repo 只有生產者與一行註解，`mcp_server/` 也不碰。**這條宣稱本身成立**；它與「該 8 列標活的」之間的張力，見矛盾 4。

---

## 5. 漏盤（**下界，不是窮舉** —— 本組找不到不代表沒有）

| # | 漏了什麼 | 出處 | 為什麼算漏 |
|---|---|---|---|
| **O1** | **`ui/helpers/session.py:66` `INITIAL_SESSION_STATE`** —— 17 個 session key 的啟動預設值 SSOT（`:87` `init_session_state` 逐個補值）。整份盤點**一次都沒提到這個檔**。其中至少 **2 個是表格狀、但 §3 沒有列**：`tdcc_results`（TDCC 查詢結果清單；key 常數在 `ui/helpers/fund_research/code_finder.py:58` `RESULTS_KEY = "tdcc_results"`，`ui/views/page_03_research.py:1051` 自陳「之後的 rerun 讀 session」）、`phase_history`（`ui/tab1_macro.py:2086-2090` 逐輪 append 的 list） | `ui/helpers/session.py:66-84` | §3 自陳「只列**表格狀**的那幾個 —— 它們才是畫 UI 會用到的資料」，這兩個符合該標準 |
| **O2** | **「82 個 session key」是下界不是總數。** 本組用盤點表所述方法重跑，字面量 key 確實 **82**（相符）；但該法**結構上看不到**屬性式寫入：`st.session_state.prev_phase = old_phase`（`ui/tab1_macro.py:2096`，預設值在 `ui/helpers/session.py:72`）—— 本組另掃到 18 個屬性式存取，其中 `prev_phase` 是字面量掃描完全看不到的。另有 **147 處非字面量 key**（如 `_HM_CARD_TRIED_KEY`／`_title_cache_key`）。 | `ui/tab1_macro.py:2096`；`ui/helpers/session.py:72` | 與盤點表自己在別處記的教訓同型：「字表選錯 → 結構上掃不到」 |
| **O3** | **3 個 UI 下載型 CSV 匯出未列入**：`ui/helpers/fund_grp_health/rotation.py:209`、`ui/tab_fund_grp_health.py:687`、`ui/tab_batch_analysis.py:505`（皆為 `st.download_button(…, df.to_csv(…).encode("utf-8-sig"), …)`）。而**同性質**的 §2.19「使用者下載／上傳的 JSON 備份」**有**列入 | 同左 | 邊界不一致：JSON 下載算一個盤點單位，CSV 下載不算 |
| **O4** | `scripts/calibrate_macro_score.py:722` `--emit-proposal` 另寫一份 JSON 檔，未列入（§2.12 只列 `:589` 的 `--emit-json`） | 同左 | 同一支腳本的第二個輸出檔 |
| **O5** | `scripts/compare_inception_years.py:459` 與 `scripts/diagnose_ret_3y_fallback.py:591` 的 `--out` 報告檔未列入（§2.17 只列 `snap.json`） | 同左 | 同上 |

**本組的漏盤搜尋方法（供後人判斷這個下界有多寬）**：(a) 全 repo 列舉每一個寫入原語（`write_text` / `to_parquet` / `to_csv` / `json.dump` / `open(...,"w"|"a")`），逐一對回 §2 的 20 個單位；(b) 全 repo 列舉每一個 worksheet 名常數與 gspread 讀寫原語，對回 §1 的 11 個單位 —— **§1 的 11 張表本組沒有找到第 12 張**；(c) `INITIAL_SESSION_STATE` 逐 key 對回 §3。
⛔ **本組沒查的**：`docs/*.md` 內描述的資料結構、`.gitignore` 白名單所指的其他 cache 目錄、以及任何在 runtime 才建立的路徑。

---

## 6. 我沒查到什麼、為什麼（一律寫「查不到」）

1. **真實 Google Sheets 上的實際欄位，查不到。** 本組**沒有**讀寫任何 Google Sheets（客戶明令禁止）。所有 Sheets 欄位都是從程式碼常數推出來的。所以「真實試算表上有沒有人手加的欄、或有沒有多出來的分頁」——**查不到**。這一點與盤點表 §9 的自述一致。
2. **runtime 可達性，查不到。** 沒有跑 app、沒有跑 pytest。所有「走得到／走不到」都是靜態（import 鏈 ＋ AST／token call site）。特別是：矛盾 3 的 `_Ledgers` 讀取、承重宣稱 ③ 的「v1 upsert 會不會真的把 v2 表頭改寫掉」、以及所有 OAuth 分支內的寫入 —— **實際執行時走不走得到，查不到**。
3. **`_持倉總覽` 有沒有被 repo 以外的東西讀（例如使用者自己開 Sheet 看、或別的 repo），查不到。** 本組只掃本 repo。
4. **`scripts/accumulate_nav_tw.py` 的 NAS cron 現在有沒有在跑，查不到。** 那條 crontab 在使用者的 NAS 上，不在 repo 內。
5. **§3 除了 O1 兩個以外還有沒有第三個表格狀 session 結構，查不到。** 147 處非字面量 key 本組沒有逐一展開判讀。
6. **`snap.json` / `cache/fundclear/` / `data_cache/macro_thresholds_global.json` 的實際檔案內容，只查到 repo 內那一份或確認不存在**；使用者本機 / 部署環境上的實際檔案 —— **查不到**。
7. **本報告是單組產出，沒有第三組驗過。** 上列 7 條矛盾、5 處 file:line 問題、5 項漏盤，都是本組自己的判讀。其中「repo 內沒有第 12 張 Sheet 分頁」「6 個 disk cache 函式零呼叫」「`fund.db` 無本 repo 讀取端」這三句是**取決於有沒有漏看**的全稱句，本組已各附兩種方法與正對照，但**不宣稱窮舉**。

---

## 7. 沒有發現問題的部分（一併記下，才看得出這把尺有往兩邊用）

- **計數**：40／264／六種狀態分布，本組獨立重數**全部相符**，一個不差。
- **`file:line`**：415 個 unique 引用，**412 個正確**（99.3%）。沒有出現「行號變成過濾後序號」那種批量錯。
- **§1 的 11 張 Sheet 分頁**：本組改從呼叫端反查，**沒有找到第 12 張**。
- **五條承重宣稱**：**五條全部成立**，本組每條都用至少一種與生產組不同的方法重驗過。
- **盤點表對既有文件的兩處指控**（`CLAUDE.md`／`EXCEPTIONS.md` 的 `EX-PASSTHRU-1` 行號漂移、`ui/tab6_manual.py:631` 說明書漏列 3 張分頁），本組複驗**都成立**。
- **敏感值處理**：盤點表對 `services/nav_history_gs.py:73` 與 `repositories/pool_repository.py:39` 的 baked sheet id **明寫「值不列出」**，本組複驗該兩行確實含實際 ID，而盤點表**沒有洩漏**。本報告同樣不列。
