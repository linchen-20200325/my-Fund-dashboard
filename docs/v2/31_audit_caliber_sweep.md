# 同型口徑問題全檔盤掃（`DB_INVENTORY.md` §1~§6）

**掃描對象**：`scratchpad/inv/DB_INVENTORY.md`（870 行 / 40 單位 / 264 欄列）**全檔**，**唯讀，一個字都沒改**。
**基準**：`origin/main = 9cbf03776f2a0ee6bdb5a649efb93352c40baba6`（開工時 `git rev-parse origin/main` 實測，與盤點表自稱一致）。
工作樹 HEAD `d0c2a8d` **全程未碰**；`pr829`~`pr834` 六個本地分支未碰。
本組的唯讀快照：`/home/user/fund-caliber`（`git archive origin/main`，747 檔；`repositories/policy/v2.py`／
`services/macro/weights_store.py`／`scripts/update_macro_history.py` 三檔 md5 與 `git show` 逐一比對相符）。
**掃描日**：2026-09-16　**產出者**：盤點稽核組（單組產出）
**零寫入**：未改 repo 任何檔案、未 commit／push／merge、未 `git fetch`、未跑任何 workflow、
未連任何外部 API、**未讀寫任何 Google Sheets（連唯讀都沒有）**。git 只用了 `show` / `grep` / `rev-parse` / `ls-tree` / `archive`。
**未列出任何 token、金鑰、sheet id、帳號或其片段。**

**方法註記（2026-09-16 補）**：負控字串不得寫進文件；掃描時須排除自身檔案。

---

## ⚠️ 版本聲明（**先讀這一段，否則下面的盤點表行號會對不上**）

**本輪掃描的是 `inv/DB_INVENTORY.md` 的 870 行 / 70,978 bytes 版本**（開工時 `wc` 實測）。
掃描期間**另一組正在同檔編輯**，收工時（2026-09-16 02:10 實測）該檔已成長為 **1,114 行 / 98,052 bytes**。
**本組全程唯讀，一個字都沒改。**

- **本報告引用的「盤點表第 N 行」一律指 870 行那一版**，在現行版本上**會位移**。
  → 因此本報告每一條命中都**原文照抄**了被引用的句子；**以引文為準，行號只是當時的座標**。
- **收工時逐條回掃現行版本，10 條命中的關鍵句有 9 條仍在**（`grep -cF` 逐句實測）：
  A1／A2／A3(`indicators` 那一列)／A4／A5／A6／A7／B1／B2／B3 的原句**全部命中**。
- **唯一已被那一組改掉的半條**：A3 的**節標題**部分。
  舊：`## 3. 只活在記憶體、沒有落地的（st.session_state）`；
  現行（實測 `:688`）：`## 3. 走 st.session_state 的表格狀結構（60 列中 **32 列另有落地**、28 列重繪即消失）`。
  ⚠️ **A3 的另一半沒有被改**：`| `indicators` | 未落地 |` 那一列仍在，
  而本報告 A3 指的是**它對照 `data_cache/*.parquet` ／ `fund.db::fred_macro` 這個落地儲存體**，
  與節標題改不改是兩件事。
- **本報告引用的程式碼行號**（`origin/main` 上的 `.py` / `.yml` / `.gitignore`）**與盤點表的編輯無關**，
  且已全數自我檢核：**124 筆引用、123 筆「檔案存在且行號在界內」、0 筆超界**，
  另 1 筆是**原文照抄盤點表**時帶進來的 `json_backup.py:22`（repo 內有兩個同名檔，無法唯一解析；
  那是盤點表的引文，不是本組的宣稱）。

---

## 結論

**命中 10 條**：方向 A（低估）**7 條**、方向 B（高估）**3 條**。
另有 **3 條同型條目上一輪稽核已記錄**（本節交叉引用，不重複計數）。
**查了沒問題的：40 個單位全查過，其中 30 個單位未命中**（名單見 §3）。

**⛔ 本報告不裁決任何一條。** 每條都寫成「A 說 X（出處）／B 說 Y（出處）／兩者不能同時為真」。

---

## 0. 我用了什麼方法（每條附正控與負控，並寫明它結構上看不到什麼）

### 先校準尺：把客戶點名的原型（第 8 條）自己跑一次

| 步驟 | 指令（repo 根或快照根執行） | 真實輸出 |
|---|---|---|
| 宣告端 | `awk 'NR>=63&&NR<=76' scripts/update_macro_history.py` | `FRED_SERIES_IDS` 11 個，`:72 "PPIACO"`、`:73 "PCOPPUSDM"` |
| 另一條路徑（PPI） | `grep -rn 'FRED_PPI' .`（排除 tests） | `shared/fred_series.py:42 FRED_PPI = "PPIACO"`；`services/macro/us_indicators.py:907 df = _fred_iso(FRED_PPI, fred_api_key, 144)`；`:415` 在 `fetch_fred_batch` 預熱清單內；`ui/helpers/io/data_registry.py:176 "PPI": FRED_PPI` |
| 另一條路徑（銅價） | `grep -rniE '銅\|copper' --include='*.py' .` | **不是 FRED**：`services/macro/us_indicators.py:925 s_cu = _yf_iso("HG=F","5y")` → `:930 R["COPPER"] = dict(name="銅博士（月漲跌）", … weight=0.5)` |
| 負控 | 同兩條指令換成 `<負控串>` | 0 命中（exit=1） |

→ **原型成立，而且比客戶說的更寬**：PPI 的活路徑走 FRED；**銅價的活路徑走 Yahoo `HG=F`，完全不是 FRED**。
也就是「在 FRED 相關的儲存體裡找不到」這件事，**結構上根本看不到銅價那條路徑**。
**這一點決定了本輪的查法：一律從「資料概念」出發，不從「檔案／來源名」出發。**

### 四種機制

| # | 機制 | 正控（應該命中） | 負控（應該不命中） | **結構上看不到什麼** |
|---|---|---|---|---|
| **M1** | **盤點表否定/肯定結論字表普查**（自寫 parser 掃 `查不到`／`只寫不讀`／`只讀不寫`／`未落地`／`已停用`／`死碼`／`零 caller`／`沒有任何`／`打不開`／`沒有入口`／`改不了`／`永遠 fallback`／`從來沒被` 等 26 個詞） | 掃出 **146 行**帶否定結論的行，含 §2.8 那一行（客戶點名的原型） | 字表外的詞 → 0 | **「意思到了但用詞不同」的結論**（例如只寫「這條線已經斷了」而不含字表任一詞的句子），本組另以人工通讀 §6 十五條發現補救 |
| **M2** | **自寫 token-stream 普查**（`tokcensus.py`，**不是** AST walk、**不是**單純 grep；追 `import X as Y` 別名鏈，另掃 STRING／COMMENT 以覆蓋 `getattr` 動態取用） | `save_holdings_overview` → def 1 ＋ **2 個非測試呼叫**（`ui/tab3_t7_ledger.py:461`、`ui/helpers/cloud_io.py:289`）；`list_cache_codes` 抓到**別名**呼叫 `ui/tab_manage.py:633 (_nh_codes)` | `<負控串>` → def/import/call/attr_call/name_other/str_or_comment **全部 n=0** | **動態組出的名字**（`getattr(mod, "fetch_" + x)`）只會落在 `str_or_comment`，**不保證判得出來**；**跨檔案的間接封裝**（A 包 B、B 包 C）要人工逐層追 |
| **M3** | **「被引用的那一行是不是註解」機械檢核**（自寫 regex 抽出盤點表全部 `file:line`，逐一印出原文，旗標開頭是 `#` 或含 `~~` 的） | **563 筆引用**，解析成功 555、正常 545、**旗標 10**、無法唯一解析 8（同名檔 `_helpers.py`／`data_registry.py`／`json_backup.py`） | — | ⚠️ **這個機制漏掉了本輪最大的一條（B1）**：`ui/helpers/nav_history_hook.py:138` 本身是**活的程式碼**，死掉的是**它上一層的兩個呼叫點**。**M3 只驗被引用的那一行，不驗它所在函式還有沒有人叫得到。** |
| **M4** | **從消費端反查可達性**（把盤點表「寫：／讀：／消費端：」那些行裡的識別字全部抽出 → 28 個符號 → M2 逐一普查 → 對每個「非測試呼叫 0」的再往上追一層） | 18 個端點符號全部查出非測試呼叫點（見 §3 表） | `calc_macro_score_series` → **非測試呼叫 0**（8 個呼叫全在 `tests/`）；`get_history_df` → **非測試呼叫 0**（13 個全在 `tests/`） | **只追到「有沒有人叫」，不追「runtime 走不走得到」** —— 有 `if` 分支保護（OAuth 登入、`_gs_enabled()`）的呼叫，本組只能說「程式碼路徑存在」 |

**子字串陷阱的處置**：M2 比對的是 **token 整體**，不是子字串（所以 `TER` 不會命中 `MATERIAL_RED`）。
掃中文詞（`銅`／`copper`）時額外人工逐行判讀，命中含 `NETFLIX` 這類假陽性時就地剔除。

**本組自己踩到的一個坑，就地記一筆（因為它正是本報告在講的那種病）**：
初稿裡 `repositories/snapshot_repository.py` 的三個行號（`lookup` / `f = lookup.get` / `str(f.get("name"))`）
是**從一段 `awk` 區塊輸出裡「用數的」**推出來的，寫成 `:237` / `:248` / `:257`；
逐行 `awk 'NR==N'` 單獨印出後，**正確值是 `:236` / `:246` / `:255`，三個全錯**。
已就地更正。**「在一段輸出裡數序號」和「把那一行單獨印出來」不是同一件事** —— 前者會錯，而且錯得很安靜。

**沒有跑 app、沒有跑 pytest、沒有 `pip install`**（預設 python3 無 pandas；M3 的 parquet 判讀**本輪未做**，直接沿用盤點表與上一輪稽核的數字，見 §5）。

---

## 1. 命中清單（10 條）

> 每條格式固定：`單位／欄位`（盤點表行號 ＋ **原文照抄**）→ `局部事實`（哪個儲存體 ＋ 實測指令與真實輸出）
> → `被推出的全稱結論`（原文照抄）→ `另一條路徑`（出處，或「查不到」）→ `方向`。
> ⛔ **不寫「應該怎麼改」。**

---

### A1｜`portfolio_funds[].series` 標「未落地」，而它就是 `nav_history` 的輸入 —— 方向 **A**

- **單位／欄位**：§3.2（盤點表 **第 596 行**）
  原文照抄：`| `portfolio_funds[].series` | **未落地** | `ui/helpers/portfolio/load.py:237` | NAV 序列；`json_backup.py:22` 明文剝掉 |`
  另 §3 節標題（**第 544 行**）原文照抄：`## 3. 只活在記憶體、沒有落地的（`st.session_state`）`
- **局部事實（成立，對「JSON 備份」這個儲存體）**：`ui/helpers/io/json_backup.py` 的匯出 payload 刻意剝掉 `series`。
  `ui/helpers/portfolio/load.py:237` 實測為 `"series": pf_raw.get("series"),`（`git show origin/main:ui/helpers/portfolio/load.py | awk 'NR==237'`）。
- **被推出的全稱結論**：該欄狀態欄寫 **未落地**；§0 對「未落地」的定義（**第 19 行**）原文照抄：
  `| **未落地** | 算得出來但沒有持久化（只活在 session） |`
- **另一條路徑（實測，同一個 `series` 物件）**：
  - `ui/helpers/nav_history_hook.py:51 _extract_points(fd)` → `:65 series = fd.get("series")` → `:78~86` 逐點組成
    `{code, nav, nav_date, fund_name, currency}` → `:138 res = append_points(fresh)` → **`nav_history` 分頁**。
  - `repositories/fund/nav_metrics.py::_nav_history_cache_save`（M2 census：**非測試呼叫 5 個** ——
    `nav_metrics.py:535/546/557/568/577`）→ **`cache/nav_history/{CODE}.json`**（盤點表 §2.2 標「活的」）。
  - `services/nav_history_store.py::_save_cache_series`（非測試呼叫 3 個：`:273/:447/:919`）→ 同一個目錄。
  - 而盤點表 §1.6（**第 176 行**）自己寫：`⚠️ **本表是唯一不可再生的資料**（`ui/tab6_manual.py:652` 明文）`。
- **兩者不能同時為真**：同一個 `series` 欄位，在 §3.2 是「算得出來但沒有持久化」，
  在 §1.6／§2.2 是「持久化到全 repo 唯一不可再生的那張表 ＋ 兩個本地 cache」。
- **方向**：**A（低估）**。
- ⚠️ **一個必須同時講的事實（與 B1 相扣）**：上列第一條路徑的 App 端入口目前是關的（見 **B1**）；
  第二、三條（`cache/nav_history/`）與 cron 那條（`scripts/weekly_nav_backfill.py`，workflow `weekly_nav_backfill.yml`）**是開的**。

---

### A2｜`portfolio_funds[].name` 標「未落地」，而盤點表自己在 §1.5 說它被寫進 Sheet —— 方向 **A**

- **單位／欄位**：§3.2（盤點表 **第 595 行**）
  原文照抄：`| `portfolio_funds[].name` | **未落地** | `ui/helpers/portfolio/load.py:236` | 抓回來的基金名；只在 JSON 備份會被帶走（§2.19） |`
- **局部事實**：`load.py:236` 實測為 `"name": pf_raw.get("fund_name") or pf_item["code"],`。
- **被推出的全稱結論**：狀態 **未落地**，備註 **「只在 JSON 備份會被帶走」**。
- **另一條路徑（實測，出處就在盤點表自己的 §1.5）**：
  - 盤點表 §1.5（**第 139 行**）原文照抄：`| `_持倉總覽.基金名稱` | 只寫不讀 | `repositories/snapshot_repository.py:42` | 來源 `portfolio_funds[].name` |`
  - 程式碼實測：`repositories/snapshot_repository.py:222 def save_holdings_overview(client, sheet_id, ledgers_dict, funds_lookup=None)`；
    `:236 lookup = funds_lookup or {}`；`:246 f = lookup.get(pk_str, {}) or {}`；**`:255 str(f.get("name", "")),`** —— 就是這一欄。
    呼叫端 `ui/helpers/cloud_io.py:289 out["n_overview"] = save_holdings_overview(client, sheet_id, _t7_dict, _funds_lookup)`（M2 正控同一筆）。
  - 另有 `nav_history.fund_name`（§1.6，經 `nav_history_hook.py:63 fund_name = str(fd.get("fund_name") or "")`）
    與 `保單分頁v2.fund_name`（§1.2b，AUTO）。
- **兩者不能同時為真**：§3.2 說 `name` 只進 JSON 備份；§1.5 說 `_持倉總覽.基金名稱` 的**來源就是它**、而且每次 T7 落帳整張覆寫。
- **方向**：**A（低估）**。
- 📌 **同一列的相鄰觀察（強度較低，另記不另計）**：同節 `metrics`／`risk_metrics`（**第 598、600 行**）標「未落地」，
  而「每檔基金算完的指標」在 `data_cache/batch/batch_*.json` 的 `rows` 內**有落地**（§2.11／§3.3 標「活的」，
  欄位 SSOT 為 `ui/helpers/fund_grp_health/unified.py:387 BATCH_UNIFIED_COLUMNS`，含健診列 ＋ 配息摘要 ＋ σ／風險）。
  **落地的鍵不同**（批次 run_id vs 持倉），所以本組把它記成相鄰觀察，不列為獨立命中。

---

### A3｜§3 節標題「沒有落地」與 `indicators`，對照 `data_cache/*.parquet` ＋ `fund.db::fred_macro` —— 方向 **A**

- **單位／欄位**：§3.5（盤點表 **第 636 行**）
  原文照抄：`| `indicators` | 未落地 | `app.py:378` 等 14 處 | 總經指標全集，Tab ① 的資料源 |`
  ＋ §3 節標題（**第 544 行**）與 §5.1 分類名（**第 710 行**）原文照抄：`| §3 **只活在 session** 的表格狀結構 | **6** | 60 |`
- **局部事實**：`ui/tab1_macro.py:2095 st.session_state.indicators = ind`（唯一寫入端，實測 `grep -rnE 'session_state\["indicators"\]\s*=|session_state\.indicators\s*='`），
  `ind` 來自 `services/macro/us_indicators.py:399 def fetch_all_indicators(fred_api_key)`。重繪即消失，這一點成立。
- **被推出的全稱結論**：狀態 **未落地**，節標題 **「只活在記憶體、沒有落地的」**。
- **另一條路徑（實測）**：
  - `services/macro/validation.py:146 def load_indicators_from_parquet(...)`，其 docstring **第 149 行**原文照抄：
    `"""從 data_cache/*.parquet 重組 indicators dict（鏡像 fetch_all_indicators 結構）.` ——
    **repo 自己有一個模組，職責就是把這個 dict 從落地的 parquet 重建回來。**
  - 落地實體：`data_cache/fred_indicators.parquet`（盤點表 §2.8 實測 9 個 series）、`vix_history` / `spx_history` / `twii_history.parquet`，
    **四檔都已 commit 進 repo**；以及 `fund.db::fred_macro` 13,654 列 ＋ `global_index` 11,406 列（§2.18）。
  - `.gitignore` 實測只擋 `data_cache/batch/`（`:36`）與 `data_cache/ai_cache.json`（`:38`），**parquet 不在擋的範圍內**。
- **兩者不能同時為真**：同一組總經指標，在 §3 是「只活在記憶體、沒有落地」，在 §2.8／§2.18 是「cron 累積、已 commit、25,068 列」。
- **方向**：**A（低估）**。
- ⚠️ **兩個必須同時講的限制**：(a) parquet 只有 **9 個 series**，而 `indicators` 的鍵數遠多於此（本組**沒有**逐鍵比對，見 §5）；
  (b) 那條「重建回 indicators dict」的路徑**目前叫不到**（見 **B2**）。
- 📌 **同一節已被上一輪稽核記過一次**：上一輪「矛盾 6」指的是 §3.1／§3.3 自陳有落地、節標題沒跟著改。
  **本條是不同的列**（`indicators`，§3.5），而且它指向的是**另一個儲存體**（parquet／SQLite），不是 §3.1 那兩個。

---

### A4｜「FundClear 回填整條鏈沒有入口」，而 FundClear 淨值走另一個模組進得了 `nav_history` —— 方向 **A**

- **單位／欄位**：§2.6（盤點表 **第 338 行**）與 §6 發現 14（**第 798~801 行**）
  原文照抄（第 338 行）：`→ **FundClear 回填整條鏈（含 `download_and_store` `:237` 那條會寫 `nav_history` 的路）目前沒有入口。**`
  原文照抄（第 800~801 行）：`` `download_and_store`（`:237`）零 caller → `cache/fundclear/` 這層快取從來不會被寫到，`` ／
  `` `download_and_store` 裡那條會寫 `nav_history` 的路徑也打不開。``
- **局部事實（成立，對 `repositories/fundclear_offshore.py` 這個模組）**：
  `grep -rn 'fundclear_offshore' --include='*.py' .`（排除 tests）→ 非自身檔案的引用只有
  `services/fundclear_backfill.py:77/:100/:259` 三處 `from repositories import fundclear_offshore as fc`，
  而那三處所在的 `find_fund_candidates`／`list_classes_for`／`download_and_store` 依盤點表為零 caller。
- **被推出的全稱結論**：`FundClear 回填整條鏈 …… 目前沒有入口`。
- **另一條路徑（實測，完全不經過 `fundclear_offshore.py`）**：
  - `repositories/fund/sources.py:103 def _src_fundclear_nav(code)`（打 `fundclear.com.tw/SmartFundAPI/...GetFundNAV`，`:115`）
    ← `repositories/fund/fund_orchestration.py:361 nav_s = _src_fundclear_nav(_code)`
    （所在函式 `:298 def _fetch_fund_single(...)`；該行上方 `:359` 註解逐字 `# 2a. FundClear（境外最穩）`）。
  - `repositories/fund/nav_metrics.py:408 def _fetch_nav_fundclear(code)` ← 同檔 `:564 s = _fetch_nav_fundclear(code)`。
  - 這條抓回來的序列進 `nav_history` 的路：`services/nav_history_store.py:558 def backfill_to_gs(...)`，
    其 docstring **第 562 行**原文照抄：`` 補齊並存進 Google Sheet(重開不丟)。抓取走 `auto_fetch_moneydj` **完整來源鏈** ``；
    `:637 from services.moneydj_fetcher import auto_fetch_moneydj`。
    `backfill_to_gs` 的呼叫端 `scripts/weekly_nav_backfill.py:246`，而 **`weekly_nav_backfill.yml` 是 8 個 workflow 之一**
    （`ls .github/workflows/` 實測 8 檔；`grep -hn 'python scripts/' .github/workflows/*.yml` 實測該 yml 第 46 行 `python scripts/weekly_nav_backfill.py`）。
- **兩者不能同時為真**：「FundClear 的歷史淨值目前進不了 `nav_history`」與上列這條每週跑的 cron 路徑不能同時成立。
  （**如果把結論讀成只講 `download_and_store` 那一個函式**，局部事實那半邊不受影響 —— 本組把兩種讀法並列，不裁決。）
- **方向**：**A（低估）**。

---

### A5｜「總經權重校準要生效，使用者得自己去 Google Sheet 手填 B3」—— 方向 **A**

- **單位／欄位**：§6 發現 4（盤點表 **第 759~761 行**）
  原文照抄：`**發現 4｜`_macro_weights` 與 `services/config/macro_weights_active.json` 都是唯讀。**` ／
  `總經權重校準要生效，使用者得**自己去 Google Sheet 手填 B3 那一格**——UI 上沒有任何寫入入口。`
- **局部事實（成立，對 Google Sheets 這個儲存體）**：`services/macro/weights_store.py:124 def _gs_get_worksheet(*, for_write: bool = False)`
  的 docstring 自陳（實測逐字）：`⚠️ **本模組今日沒有 production 寫入端**(2026-09-07 AST 實測…)`、
  `` **`for_write=True` 因此目前只有守衛測試會走到。** ``。M2 census 對 `save_active` → def 0。
- **被推出的全稱結論**：`要生效，使用者得自己去 Google Sheet 手填 B3 那一格`。
- **另一條路徑（實測，就在盤點表自己的 §2.16）**：`weights_store.py:239 def load_active()` 是**嚴格二擇一**：
  ```
  if _gs_enabled():
      data = _gs_load("active");  return data if data is not None else _empty_active()
  if not _ACTIVE_PATH.exists():   return _empty_active()
  data = json.loads(_ACTIVE_PATH.read_text(encoding="utf-8"))
  ```
  而 `:60 def _gs_enabled()` 實測為 `return bool(sa.get("client_email") and sid)`（兩個 secret 都要有）。
  → **沒有那兩個 secret 的部署，`load_active()` 根本不看 Google Sheet**，讀的是
  `services/config/macro_weights_active.json`；盤點表 §2.16（**第 477 行**）自己寫
  `repo 內實測只有一項 `VIX_DELTA_5D.weight = 0.8``。
- **兩者不能同時為真**：在該分支下，「手填 B3」不會生效，而「一個校準已經在生效」是既成事實。
- **方向**：**A（低估）**。

---

### A6｜`env.ANTHROPIC_API_KEY` / `env.OPENAI_API_KEY` 標「查不到（本 repo 無消費路徑）」—— 方向 **A**

> 📌 **這一條與上一輪稽核的「矛盾 5」是同一件事。** 本輪**獨立重測**後仍列入，
> 因為它是本次任務要找的那個形狀的標準樣本（局部事實「本 repo 的 AI 走 Gemini」→ 全稱「無消費路徑」）。

- **單位／欄位**：§4.2（盤點表 **第 690 行**）
  原文照抄：`| `env.ANTHROPIC_API_KEY` / `env.OPENAI_API_KEY` | 查不到（本 repo 無消費路徑） | `infra/llm.py:71,72` | 只在 `infra/llm.py` 內取；本 repo 的 AI 走 Gemini |`
  §0 定義（**第 17 行**）原文照抄：`| **查不到** | 兩端都查不到 |`
- **局部事實**：本 repo 的 AI 主線確實走 Gemini。
- **被推出的全稱結論**：`查不到（本 repo 無消費路徑）`。
- **另一條路徑（本組實測，四行逐行 `awk` 印出）**：
  - `infra/llm.py:33 _DEFAULT_CHAIN = ["gemini", "anthropic", "openai"]`
  - `infra/llm.py:69~72` `keys = { "gemini": …, "anthropic": anthropic_key or os.environ.get("ANTHROPIC_API_KEY",""), "openai": … os.environ.get("OPENAI_API_KEY","") }`
  - `infra/llm.py:39 def call_llm(...)` ← M2 census：非測試呼叫 **1**：`services/ai_service.py:341 return call_llm(prompt, max_tokens=5000, gemini_key=api_key)`
  - `services/ai_service.py:130 def analyze_portfolio_mk_advisor(...)` ← `ui/tab3_t7_ledger.py:3355 _mk_txt = analyze_portfolio_mk_advisor(`（`:59` import），Tab3 由 `app.py` 掛載。
- **兩者不能同時為真**：那兩行 `os.environ.get(...)` 每次 AI 顧問都會執行，且 `_DEFAULT_CHAIN` 會在 gemini 失敗時輪到它們；
  這與「兩端都查不到」互斥。「key 沒設定」與「沒有消費路徑」是兩件事。
- **方向**：**A（低估）**。

---

### A7｜`macro_thresholds_global.json`：「repo 裡沒有這個檔」→「實務上永遠 fallback」—— 方向 **A**（本輪強度最低的一條，如實標明）

- **單位／欄位**：§2.12（盤點表 **第 420~423 行**）
  原文照抄：`**檔案不在 repo**（`git ls-tree origin/main -- data_cache/` 只有 4 parquet ＋ metadata.json）。` ／
  `讀取在 **module import 時就執行**（`services/macro/validation.py:104`）→ 實務上永遠 fallback 到` ／
  `` `DEFAULT_VIX_CRISIS`／`DEFAULT_VIX_WARNING`。`` ／
  `` 唯一寫入端 `scripts/calibrate_macro_score.py:589`（`--emit-json` 預設值 `:685`）是**手動 CLI，沒有任何 workflow 掛它** ``
- **局部事實（成立）**：`services/macro/validation.py:104 _VIX_CRISIS, _VIX_WARNING = _load_vix_calibrated_thresholds()`
  （實測 `awk 'NR==104'`）確實在 module import 時執行；該檔確實不在 `git ls-tree origin/main`。
  `ls .github/workflows/` 實測 8 檔，`grep -hn 'python scripts/' .github/workflows/*.yml` 的輸出裡**沒有 calibrate** —— 這半邊也成立。
- **被推出的全稱結論**：`實務上永遠 fallback`。
- **另一條路徑**：`scripts/calibrate_macro_score.py:589 path.write_text(json.dumps(payload, …))`，
  預設輸出 `:685 p.add_argument("--emit-json", default="data_cache/macro_thresholds_global.json")` —— **盤點表自己在下兩行寫出這個寫入端**。
  且 `.gitignore` 實測**沒有**擋這個檔（只有 `:36 data_cache/batch/`、`:38 data_cache/ai_cache.json`），
  也就是「repo 裡沒有」＝「沒人把它 commit 上去」，**不等於**「執行環境的檔案系統上沒有」。
- **兩者不能同時為真**：「永遠 fallback」是一句關於**執行時檔案系統**的話；
  而「有一支手動 CLI 會在 `data_cache/` 產生這個檔」也是實測事實。兩句在「使用者跑過那支 CLI 的那台機器」上不能同時成立。
- **方向**：**A（低估）**。
- ⚠️ **本條的強度低於 A1~A6**：它成立與否取決於**部署環境**，而本組**沒有跑 app、沒有看任何部署環境的檔案系統**（見 §5）。

---

### B1｜`nav_history` 的「寫（production）」列了一個**兩個入口都被註解掉**的模組 —— 方向 **B**

- **單位／欄位**：§1.6（盤點表 **第 168 行**）
  原文照抄：`寫（production）：`ui/helpers/nav_history_hook.py:138`、`ui/tab_manage.py:615`（**別名匯入 `_gs_append`**，`:614`）、`
- **局部事實（成立）**：`ui/helpers/nav_history_hook.py:138 res = append_points(fresh)` 確實是活的程式碼（`awk 'NR==138'` 逐字印出）。
- **被推出的結論**：它被列為 **production 寫入端**。§0（**第 21~22 行**）定義 production 為
  「從 `app.py` 可達的 UI 路徑，或 `.github/workflows/` 有排程的 script」。
- **另一條路徑／可達性（實測，三種機制交叉）**：
  - 該模組 `__all__`（`:161`）只有 4 個名字：`record_fund_nav_point` / `record_batch_nav_points` / `_extract_point` / `_extract_points`；
    `:138` 住在私有的 `_record`（`:107`），只被前兩個公開函式呼叫。
  - **M2 census**：`record_fund_nav_point` → def 1、**真呼叫 0**；`record_batch_nav_points` → def 1、**真呼叫 0**。
  - **逐行印出那兩個「呼叫點」**：
    `ui/tab2_single_fund.py:405` 實測為 `` # ~~    from ui.helpers.nav_history_hook import record_fund_nav_point~~ `` ——
    **是註解**；同檔 `:401` 起的標頭逐字 `# ── 2026-09-06:查一檔基金**不再**回寫 Google Sheet ────`，
    `:410` 逐字 `# **有意識的政策變更,不是漏刪**(日期 **2026-09-06** · 決策者:**客戶**)。`
    `ui/tab_fund_grp_health.py:334` 實測為 `` # ~~    from ui.helpers.nav_history_hook import record_batch_nav_points~~ `` ——
    **也是註解**；`:330` 逐字 `# ── 2026-09-06:健診批次跑完**不再**回寫 Google Sheet ──`。
  - `grep -rn 'nav_history_hook' --include='*.py' .`（排除 tests）→ **唯一非註解的引用**是
    `scripts/accumulate_nav_tw.py:68 from ui.helpers.nav_history_hook import _extract_points` ——
    它只拿**純函式** `_extract_points`，**沒有拿寫入路徑**（同檔 `:74` 另外自己 `from services.nav_history_gs import append_points`）；
    而 `grep -hn 'python scripts/' .github/workflows/*.yml` 的輸出裡**沒有 `accumulate_nav_tw`**。
- **兩者不能同時為真**：`:138` 被列為「production 寫入端」與「它的兩個唯一入口在 `origin/main` 上都是註解」不能同時成立。
- **方向**：**B（高估）**。
- ✅ **同一行的另外兩個寫入端本組查過，是活的**：`ui/tab_manage.py:615 _g = _gs_append(_mr["points"], oauth_client=_oauth_csv)`（非註解，M2 census 真呼叫 1）；
  `ui/tab5_data_guard.py:1851 _ni_res = import_csv_text(_ni_code.strip().upper(), _ni_text,`（非註解）。
  **所以 `nav_history` 這張表本身仍有 production 寫入端**；本條命中的是**那一個被列錯的端點**。

---

### B2｜`data_cache/*.parquet` 9 列標「活的」，而它列在第一個的讀取端住在一個零呼叫的函式裡 —— 方向 **B**

- **單位／欄位**：§2.8（盤點表 **第 371~373 行**）
  原文照抄：`` 讀：`services/macro/validation.py:33`（`DEFAULT_PARQUET_CACHE_DIR`）→ `load_indicators_from_parquet`（`:239`）； `` ／
  `` `scripts/export_fund_db.py:61,70`；`scripts/calibrate_macro_score.py:97` ``
  ＋ §2.8 九列狀態全為 **活的**；§0（**第 14 行**）定義：`| **活的** | 有 production 寫入 **且** 有 production 讀取 |`
- **局部事實（成立）**：`services/macro/validation.py:33 DEFAULT_PARQUET_CACHE_DIR = Path("data_cache")` 確實存在；
  `:146 def load_indicators_from_parquet(` 確實存在，內部確實讀 `:172 fred_path = cache_dir / "fred_indicators.parquet"`、
  `:218 vix_path = cache_dir / "vix_history.parquet"`。
- **被推出的結論**：九列 **活的**，且讀取端清單的**第一個**是 `services/` 層（＝ 看起來 app 讀得到）。
- **另一條路徑／可達性（實測，兩種機制交叉）**：
  - `grep -rn 'load_indicators_from_parquet' .` → 非測試呼叫**兩個**：
    `services/macro/validation.py:259 sources.update(load_indicators_from_parquet(cache_dir))`
    與 `scripts/calibrate_macro_score.py:692 indicators = load_indicators_from_parquet(CACHE_DIR)`。
  - `:259` 住在 `:234 def calc_macro_score_series(`（`awk` 逐行印出確認 `:234` 是 def、`:259` 在其內）。
    **M2 census：`calc_macro_score_series` → def 1、非測試呼叫 0**（8 個呼叫全在 `tests/test_macro_validation.py`）。
    同檔 `:333 def verify_score_vs_crises(` 亦為非測試呼叫 0。
    `scripts/calibrate_macro_score.py:152` 的註解逐字寫著
    `為避免循環依賴 services/macro_validation，這裡複製 calc_macro_score_series` —— **它是複製，不是呼叫**。
  - `scripts/calibrate_macro_score.py` **沒有任何 workflow 掛它**（8 個 workflow 的 `python scripts/` 行逐一看過）。
    依 §0 第 22 行「手動 CLI script（沒有 workflow 掛它）……**不當 production**」。
  - 剩下唯一的 production 讀取端是 `scripts/export_fund_db.py:50/60/70`（workflow `export_db.yml:39 python scripts/export_fund_db.py --no-live --output fund.db`），
    而盤點表 §6 發現 8（**第 775 行**）原文照抄：`**發現 8｜`fund.db` 是給別的 repo 用的，本 repo UI 不讀。**`
  - 窮舉性補強：`grep -rn 'fred_indicators\|vix_history\|spx_history\|twii_history\|\.parquet' .`（排除 tests／STATE.md／data_cache）
    的完整輸出裡，**除上列三處外沒有第四個讀取實作**（另有 `services/us_liquidity_engine.py:50`、`scripts/compare_inception_years.py:43`，兩者都是註解）。
- **兩者不能同時為真**：讀取端清單把 `services/macro/validation.py` 排在第一個，與「那條路徑的入口函式非測試呼叫 0」不能同時成立；
  若只認 `export_fund_db.py` 那條，則這 9 列的 production 讀取全部發生在**離線 script**、且其產物依 §6 發現 8 不被本 repo 讀。
- **方向**：**B（高估）**。
- 📌 **與客戶點名的第 8 條互為鏡像，值得並看**：§2.8 同一節裡，
  「PPI／銅價」被**低估**（說沒有資料可畫，其實有活的線上路徑），
  「parquet 有 15 年歷史」被**高估**（列了一個叫不到的 services 層讀取端）。兩個錯把讀者推向相反的兩邊。

---

### B3｜`config/preset_funds.json` 標「只讀不寫」並列兩個 production 讀取端，其中一個讀回來沒人用 —— 方向 **B**

- **單位／欄位**：§2.14（盤點表 **第 447~448 行**與 **第 450~452 行**）
  原文照抄：`| `preset_funds.funds[].code` | 只讀不寫 | 讀 `services/fund_history.py:46`、`scripts/export_fund_db.py:80` | 強制大寫；空則跳過 |` ／
  `**讀取端（兩個，都是 production）**：` ／
  `` (a) `_load_default_funds`（`:37`），在 **module import 時**就跑（`:59` `_DEFAULT_FUNDS = _load_default_funds()`）； ``
- **局部事實（成立）**：`services/fund_history.py:37 def _load_default_funds()`、`:46 code = str(d.get("code","") or "").strip().upper()`、
  `:59 _DEFAULT_FUNDS: list[dict] = _load_default_funds()` 逐行印出確認；
  且該模組在 production 確實會被 import（`record_fund` 於 `ui/tab2_single_fund.py:384`／`ui/tab3_portfolio.py:1566` 別名呼叫），
  所以**檔案的 bytes 真的會被讀**。
- **被推出的結論**：`讀取端（兩個，都是 production）`。
- **另一條路徑／下游（實測，M2 census）**：`_DEFAULT_FUNDS` 的非測試消費點只有三個：
  - `services/fund_history.py:129`（住在 `:120 def _load_with_defaults()`）—— **盤點表自己在 §2.3（第 311 行）判它是死碼**，
    原文照抄：`` `_load_with_defaults`（`:120`）唯一 caller 是 `get_history_df`（`:161`），一併是死碼。``
    本組 M2 獨立複驗：`get_history_df` → def 1、**非測試呼叫 0**（13 個呼叫全在 `tests/test_fund_history.py`）。
  - `services/fund_history.py:331~332`（`global _DEFAULT_FUNDS` / 重載），住在 `:281 def promote_to_preset(` ——
    盤點表自己在 **第 454 行**寫 `**寫入端：`promote_to_preset`（`services/fund_history.py:281`…）—— 零 caller。**
  - → **讀取端 (a) 讀回來的值，在 production 沒有任何消費者。**
  - 讀取端 (b) `scripts/export_fund_db.py:76 path = _ROOT / "config" / "preset_funds.json"` → `:80 rows = [...]`
    **是活的**（workflow `export_db.yml`），其產物 `fund.db::fund_universe` 依 §6 發現 8 本 repo 不讀。
- **兩者不能同時為真**：「兩個都是 production 讀取端」與「其中一個的產物只被兩段死碼消費」不能同時成立。
  同一把「有沒有下游消費者」的尺，盤點表在 §2.3 用來把 `cache/fund_history.json` 判成「只寫不讀」，在 §2.14 沒有再用一次。
- **方向**：**B（高估）**。

---

## 2. 同型、但上一輪稽核已經記過的（交叉引用，不計入本輪 10 條）

| 上一輪編號 | 單位 | 形狀 | 方向 | 本輪做了什麼 |
|---|---|---|---|---|
| 矛盾 1 | §2.1 `cache/nav/*` 8 列標「活的」，唯一寫入端 `scripts/fetch_nav_cache.py` 無 workflow | 局部「有寫入實作」⇒「活的」 | **B** | 本輪獨立複驗 workflow 清單：`ls .github/workflows/` 實測 **8 檔**，`grep -hn 'python scripts/' *.yml` 的輸出**沒有 `fetch_nav_cache`**；M2 census `save_cache` 的非測試呼叫只有 `scripts/fetch_nav_cache.py:744,749`（自身內部） |
| 矛盾 3 | §1.4 `_Ledgers` 9 列標「活的」，唯一讀取端餵給零讀取的 `_sheet_stats` | 局部「有讀取呼叫」⇒「活的」 | **B** | 本輪獨立複驗：`grep -rn '_sheet_stats' --include='*.py' .`（排除 tests）→ `ui/helpers/portfolio/policy_admin_section.py` 的 `:819`(註解)／`:820`(def)／`:829`(唯一寫入)／`:843`(註解)／`:871`(呼叫 `_refresh_sheet_stats`)，**零讀取** |
| 矛盾 4 | §2.18 `fund.db` 8 列標「活的」，本 repo 無讀取端 | 局部「有 cron 產出」⇒「活的」 | **B** | 本輪未重新查 SQLite（無 pandas，且不重複上一輪已做的事）；但 B2 的推導**依賴**「本 repo 不讀 fund.db」這句，本組是引用 §6 發現 8 與上一輪稽核，**本輪沒有自己重掃 `fund.db` 讀取端** |

---

## 3. 查了但沒問題的（40 個單位逐一，**只寫命中不寫清白，看不出這把尺有沒有往內用**）

**40 個單位全部過了一次 M1（否定/肯定結論字表）；其中 18 個端點符號另跑了 M2 逐一 census。**
下表的「本輪查法」寫明每一個到底查到什麼程度。

| 單位 | 狀態（盤點表） | 本輪查法與結果 | 判定 |
|---|---|---|---|
| §1.1 `Policies` | 活的 ×14 | M2：`load_policies` 非測試呼叫 1（`ui/helpers/cloud_io.py:458`）、`sync_policies_to_portfolio_funds` 非測試呼叫 1（`cloud_io.py:466`） | 未命中 |
| §1.2a 保單分頁 v1 | 活的 | M2：`upsert_fund_in_policy` def 1、非測試呼叫 **3**（`ui/tab3_portfolio.py:1575`、`ui/tab3_t7_ledger.py:1043`、`ui/helpers/cloud_io.py:243`） | 未命中 |
| §1.2b 保單分頁 v2 | 活的 ×10 | M2：`write_policy_v2` 非測試呼叫 **5**（`cloud_io.py:88,186`、`v2_editor.py:455,529`、`scripts/migrate_v149_schema.py:178`） | 未命中 |
| §1.3 `_T7_State` | 活的 ×6 | M2：`load_all_ledgers_snapshot` 非測試呼叫 2（`tab3_t7_ledger.py:476`、`cloud_io.py:477`） | 未命中 |
| §1.4 `_Ledgers` | 活的 ×9 | M2：`append_ledger_row` 1、`replace_ledgers_for_policy` 1、`load_all_ledgers` 1 | 同型問題**上一輪已記**（矛盾 3），本輪不重複計數 |
| §1.5 `_持倉總覽` | 只寫不讀 ×13 | **盤點表自己在 §6 發現 2（第 752~754 行）就寫出了另一條路徑**：「資料要從 `_T7_State.ledger_json` 或 session 的 `t7_ledgers` 取」 → **沒有把局部事實外推成系統做不到** | 未命中（**這一條是本輪的反面樣本**） |
| §1.6 `nav_history` | 活的 ×7 | 見 **B1**（寫入端列錯一個）；表本身有活的寫入端與讀取端 | **命中 B1** |
| §1.7 `_fund_pool` | 活的 ×10 | M2：`list_pool` def 5（含後端分派）、抓到別名呼叫 `ui/tab3_portfolio.py:1983 (list_pool as _lp_h)` | 未命中 |
| §1.8 `_portfolio_perf_history` | 活的 ×15 | M2：`append_snapshot` 非測試呼叫 2、`load_snapshots` 3；消費端 `switch_advisor_section` 由 `ui/tab3_portfolio.py:2241` 活呼叫（`ui/tab_fund_grp_health.py:420` 那一處是註解，但不是唯一入口） | 未命中 |
| §1.9 `_macro_weights` | 只讀不寫 ×3 | 表格三列的「只讀不寫」本身**成立**（`weights_store.py:124` docstring 自陳無 production 寫入端）；命中的是 §6 發現 4 的那句話 | **命中 A5** |
| §1.10 watchlist CSV | 只讀不寫 | 消費者 `scripts/weekly_switch_notify.py`／`dividend_calendar_notify.py`，兩支都有 workflow（實測 `weekly_switch_notify.yml:50`、`dividend_calendar_notify.yml:113`） | 未命中 |
| §2.1 `cache/nav/*` | 活的 ×8 | 見 §2 交叉引用（矛盾 1） | 上一輪已記 |
| §2.2 `cache/nav_history/*` | 活的 ×3 | M2：`_nav_history_cache_save` 5 / `_nav_history_cache_load` 1 / `_save_cache_series` 3，全部非測試 | 未命中 |
| §2.3 `cache/fund_history.json` | 只寫不讀 ×6 | M2 獨立複驗 `get_history_df` → 非測試呼叫 **0**（與盤點表一致）。**相鄰路徑登記於 §4 第 2 則**（`list_cache_codes` 有畫面），但資料概念不同，不列命中 | 未命中 |
| §2.4 `cache/fund_pool/pool.json` | 活的 | `get_pool_store` 二擇一分派，兩支都是活的程式碼 | 未命中 |
| §2.5 `cache/portfolio_perf/perf_history.json` | 活的 | 同上（`get_perf_store`）；M2 `append_snapshot` / `load_snapshots` 在 `repositories/portfolio_perf_repository.py` 內有本地後端呼叫 | 未命中 |
| §2.6 `cache/fundclear/*` | 查不到 | 見 **A4** | **命中 A4** |
| §2.7 `cache/fred_release/*` | 活的 ×3 | 逐行印出兩個讀取端：`ui/helpers/io/data_registry.py:208`、`ui/tab5_data_guard.py:1512`，**都是活的程式碼、都是別名 lazy import**（非註解） | 未命中 |
| §2.8 `data_cache/*.parquet` | 活的 ×9 | 見 **B2** | **命中 B2** |
| §2.9 `data_cache/metadata.json` | 只寫不讀 ×5 | 盤點表的查法只掃 `-- '*.py'`，本組改掃**全檔案類型**：`grep -rn 'metadata\.json' .`（排除 tests）→ 只有 `scripts/update_macro_history.py:14/58/362`，**沒有 workflow 或文件在讀** | 未命中（**盤點表的射程比它自己寫的窄，但結論不變**） |
| §2.10 `data_cache/ai_cache.json` | 活的 ×2 | 讀寫端 `ui/helpers/ai_summary.py:87/:129`；`render_ai_summary_widget` 有 **5 個活的 UI 呼叫端**（`tab1_macro_ai.py:85`、`tab2_single_fund.py:2698`、`tab3_portfolio.py:2306,2558`、`fund_grp_health/ai.py:239`） | 未命中 |
| §2.11 `data_cache/batch/*` | 活的 ×5 | `ui/tab_batch_analysis.py` 為活的消費端；欄位 SSOT `unified.py:387 BATCH_UNIFIED_COLUMNS` 逐行印出確認 | 未命中 |
| §2.12 `macro_thresholds_global.json` | 只讀不寫 ×3 | 見 **A7** | **命中 A7（強度最低）** |
| §2.13 `/tmp/fund_cache/*` | 查不到 ×3（死碼） | **本組另查一條盤點表沒查的路**：`get_all_cache_info`（唯一經 `fund_fetcher` shim ＋ 別名被 UI 用到的 cache 檢視函式，`policy_admin_section.py:774`）—— 逐行印出 `infra/cache.py:646~710` 全文，**它只走訪 `_CACHE_REGISTRY`，完全不碰 `/tmp/fund_cache`** | 未命中（**本組試圖推翻它，推不翻**） |
| §2.14 `config/preset_funds.json` | 查不到 ×1 ＋ 只讀不寫 ×2 | 見 **B3** | **命中 B3** |
| §2.15 `config/macro_weights_active.json`（repo 根） | 查不到 | 本組另查**路徑組合式**引用（盤點表只做字面 grep）：`scripts/calibrate_macro_score.py` 的兩個輸出參數逐行印出 —— `:685 --emit-json` → `data_cache/macro_thresholds_global.json`、`:686 --emit-proposal` → `MACRO_SCORE_CALIBRATION_PROPOSAL.md`，**都不是 repo 根那一份** | 未命中（**本組試圖推翻它，推不翻**） |
| §2.16 `services/config/macro_weights_active.json` | 只讀不寫 ×11 | `weights_store.py:248~256` 逐行印出，二擇一分支確認 | 未命中（它反而是 **A5** 的另一條路徑） |
| §2.17 `snap.json` | 查不到（production）×4 | 兩支 script 皆無 workflow（8 個 workflow 逐一看過） | 未命中 |
| §2.18 `fund.db` | 活的 ×8 ＋ 已停用 ×2 | 見 §2 交叉引用（矛盾 4） | 上一輪已記 |
| §2.19 JSON 備份 | 活的 ×6 | M2：`build_export_payload` 1（`policy_admin_section.py:481`）、`restore_from_json_bytes` 1（`:509`） | 未命中 |
| §2.20 `templates/` | 只讀不寫（人讀）×4 | 本組獨立掃 `grep -rn 'templates/' --include='*.py' .`（排除 tests）→ **0 行**；再掃四個 sample 檔名（不限副檔名、排除 `templates/` 自身）→ **0 行**。**「程式不讀」成立**（其與 §0 定義的張力上一輪已記為矛盾 7） | 未命中（**新增的只有一則備註錯，見 §4 第 1 則**） |
| §3.1 `t7_ledgers` | 活的（有落地）×15 | 上一輪已逐條驗過，本輪未重做 | 未命中 |
| §3.2 `portfolio_funds` | 未落地 ×9 ＋ 活的 ×13 | 見 **A1**、**A2** | **命中 A1／A2** |
| §3.3 `batch_codes` / `batch_rows` | 活的 ×3 ＋ 未落地 ×3 | `BATCH_UNIFIED_COLUMNS` 逐行印出；落地端 `repositories/batch_checkpoint.py` 為活 | 未命中 |
| §3.4 `t7_scenarios` | 未落地 ×8 | 本組掃「再平衡方案」的其他儲存體 → **查不到**第二條落地路徑（`_T7_State` 存的是 ledger，不是 scenario） | 未命中 |
| §3.5 其他 session 表 | 未落地 | 見 **A3**（`indicators` 那一列）；`news_items`／`api_latency_log`／OAuth 狀態等本組**查不到**第二條落地路徑 | **命中 A3（僅 `indicators` 一列）** |
| §4.1 `st.secrets` | 活的 ×13 | 逐項對應到活的讀取點；**未列任何值** | 未命中 |
| §4.2 環境變數 | 活的 ×13 ＋ 查不到 ×1 | 見 **A6**（最後一列） | **命中 A6** |
| §4.3 `.streamlit/config.toml` | 活的 ×3 | 純設定，無外推 | 未命中 |

**未命中合計 30 個單位；命中 8 個單位（10 條，§3.2 一個單位出兩條、§2.8 與 §1.6 各一條）；上一輪已記 3 個單位（其中 §1.4／§2.18 與本輪未命中不重複計）。**

---

## 4. 順帶抓到、但**不是**口徑問題的（另記，不計入 10 條）

1. **§2.20 的一則備註指錯函式**（盤點表 **第 539 行**）
   原文照抄：`| `templates/fund_history_sample.csv.{代號,名稱,來源,查詢次數,首次查詢,最近查詢}` | 只讀不寫（人讀） | `templates/fund_history_sample.csv:1` | ＝ §2.3 的匯出版（`services/nav_history_store.py:387` 產 CSV bytes） |`
   **實測**：`services/nav_history_store.py:378 def export_nav_csv(code: str) -> bytes:`，其 `:383~386` 組的欄位是
   `"date"` / `"nav"`，`:387 return df.to_csv(index=False).encode("utf-8-sig")` —— **那是 `nav_history_sample.csv` 的形狀，不是 `fund_history_sample.csv`**。
   那六個中文欄名實際產生於 `services/fund_history.py:160 cols = ["代號", "名稱", "來源", "查詢次數", "首次查詢", "最近查詢"]`，
   住在 `:158 def get_history_df()` —— 而 §2.3 自己說它零 caller（本組 M2 複驗：非測試呼叫 0）。
   **同一份表在 §2.3 說那條線斷了，在 §2.20 把它接到一支活函式上。**

2. **§6 發現 12 的設計建議旁邊，另有一條已經在畫面上的相鄰路徑**（登記，非命中）
   發現 12（**第 791~792 行**）原文照抄：`要在新 UI 做「最近查過的基金」，資料**現成就有**，只要接上 `get_history_df()` 即可 —— 不必新寫抓取。`
   **實測**：`services/nav_history_store.py:370 def list_cache_codes()` → `:372~373 return sorted(p.stem for p in _CACHE_DIR.glob("*.json"))`，
   M2 抓到**別名呼叫** `ui/tab_manage.py:562 (list_cache_codes as _nh_codes)` → `:633 _codes = _nh_codes()` →
   `:635` 渲染 selectbox「已建立的 cache（選一檔做增量更新 / 下載備份 / 清除）」。
   **兩者的欄位不同**（`cache/fund_history.json` 有查詢次數／首次／最近查詢／來源；`list_cache_codes` 只有代號清單），
   所以本組**不**把它列為口徑命中，只登記「相鄰路徑已在畫面上」。

3. **客戶原型的一處事實補充**：第 8 條說 PPI 與銅價「另有一條活的線上取數路徑（走 FRED API）」——
   **PPI 走 FRED（`us_indicators.py:907`），銅價走 Yahoo `HG=F`（`us_indicators.py:925`），不是 FRED。**
   本組把這一點寫出來，是因為它決定了查法：**用「來源名」去掃，結構上永遠掃不到銅價那條。**

---

## 5. 我沒查到什麼（一律寫「查不到」）

1. **真實 Google Sheets 上的實際內容，查不到。** 本輪**沒有讀寫任何 Google Sheets**（連唯讀都沒有）。
   所有 Sheets 相關判斷都是從程式碼常數推出來的。
2. **runtime 可達性，查不到。** 沒有跑 app、沒有跑 pytest、沒有 `pip install`。
   凡是有 `if` 分支保護的（OAuth 登入分支、`_gs_enabled()` 分支、`prefer_parquet` 參數），
   本組只能說「程式碼路徑存在／不存在」，**使用者實際走不走得到，查不到**。
   特別是 **A5／A7** 兩條，它們成立與否取決於部署環境的 secrets 與檔案系統 —— 那些**查不到**。
3. **部署環境的檔案系統，查不到。** `data_cache/macro_thresholds_global.json`（A7）、`snap.json`、
   `cache/fundclear/` 在使用者機器或 Streamlit Cloud 上到底存不存在 —— **查不到**。
4. **parquet 與 SQLite 的內容，本輪沒有自己重解。** 沒有 pandas／pyarrow、未 `pip install`，
   §2.8／§2.18 的列數與 series 名一律沿用盤點表與上一輪稽核的數字，**本輪沒有自己重測**。
   因此 **B2** 的推導裡「`fund.db` 本 repo 不讀」這一句，出處是 §6 發現 8 與上一輪稽核的矛盾 4，**不是本組自己掃的**。
5. **`indicators` 的鍵與 parquet 的 9 個 series 到底重疊多少，查不到。** A3 只證明「同一個資料概念有落地」，
   **沒有**逐鍵比對，也**沒有**量「落地涵蓋了幾成」。
6. **本檔的命中清單是分類敘述，不是窮舉。** 本組用了四種機制，每一種的射程外已寫在 §0 表格最後一欄；
   其中 **M3 漏掉 B1**（它只驗被引用的那一行，不驗那行所在函式還有沒有人叫得到）就是現成的證明。
   **「盤點表沒有第 11 條同型問題」這句話，本組沒有查證、也不宣稱。**
7. **動態組出的符號名，查不到。** M2 只能把它們丟進 `str_or_comment`；
   本輪對每一條「非測試呼叫 0」的判定都另外看過 STRING／COMMENT 命中，但**那不等於窮舉**。
8. **本報告是單組產出，沒有第三組看過。**
