# `spec/UI_SPEC.md` 第二輪獨立稽核（R2）

> **受檢**：`scratchpad/spec/UI_SPEC.md`（重寫後版本）
> **基準**：`origin/main` ＝ `9cbf03776f2a0ee6bdb5a649efb93352c40baba6`
> ⚠️ **工作樹 HEAD 是 `d0c2a8d`，不是 `origin/main`** —— 本組把 `origin/main` 以
> `git archive` 展開到自己的目錄（`/home/user/r2main`，`md5sum app.py` 與
> `git show origin/main:app.py` 逐 byte 相同），**全程未碰共用工作樹的工作區**。
> ⛔ 本組**未改任何 `.py`**、**未改任何 UI**、**未 commit**、**未開 PR**、
> **未動 `spec/` `inv/` 與上一輪的 `audit/UI_SPEC_AUDIT.md`**、**未打任何外部 API**、
> **未碰 Google Sheets**、**未觸發任何 workflow**。本檔是本組唯一新建的檔案。
> ⛔ **本報告不裁決。** 每一條矛盾只寫「A 說 X／B 說 Y／兩者不能同時為真」。

**方法註記（2026-09-16 補）**：負控字串不得寫進文件；掃描時須排除自身檔案。

---

## 0. 方法（含正控、負控，以及這把尺結構上看不到什麼）

### 用了哪幾種機制

| # | 機制 | 正控（該有的有出現） | 負控 | 它**看不到**什麼 |
|---|---|---|---|---|
| **M1** | **規格機械解析**（自寫 parser：`^### ` 切塊、`^- (來源\|規則\|空狀態\|回答)：` 抽四件、bold 標籤逐塊計數） | 21 個 UI 區塊全部解出、四件全部抽到 | 第五種小標 → 0 | 只看得到「有沒有填」，看不出填的**內容對不對** |
| **M2** | **盤點表機械解析**（表頭定位欄位，`~~...~~` 先整段丟掉再去 `**`，再取「狀態」與「誰讀它」兩欄） | 解出 **231** 列，與盤點表 §0.3 自陳的 231/231 相符；`狀態` 分布 89/73/28/20/10/5/4/2、`誰讀它` 分布 UI 113 ／內部 63 ／無 55 | `<負控串>` → 0 命中 | 群組列（一列代表一整組欄位）**藏得住逐欄差異**，盤點表 §0.3 自己已登記 |
| **M3** | **消費端反查**（從渲染端往回讀：`st.*` 呼叫、`render_cards([...])` 的 builder 清單、`dict(zip(...))` 的欄名），不只正向 grep 欄名 | 六張卡的 builder 清單在 `page_01_macro.py:2157-2164` 逐行讀出 | — | 只讀得到**字面呼叫**，`getattr` / `asdict()` / 動態組鍵一律看不到 |
| **M4** | **別名 import 先列再掃**（`from x import y as z`） | `page_05_settings.py:323` `coverage_status as fetch_nav_coverage`、`page_01_macro.py:167` `summarize_radar` 都是先列 import 才掃 | — | 本地變數別名（`f = foo` 後 `f()`）仍掃不到 |
| **M5** | **行號一律單獨印**（`git show origin/main:<path> \| awk 'NR==N'`，不經 `grep -v` 數序號） | `app.py` 581/587/636/648/662/673/688/720/728/752/776 逐行印出 | — | 只驗「那一行是不是它自稱的東西」，不驗那段程式**跑不跑得到** |
| **M6** | **token 邊界比對**（`grep -oE "\b<w>\b"`）避開子字串陷阱 | `\bvalue\b`=35、`\bsignal\b`=5、`\bunit\b`=8 | `\b<負控串>\b` → 0 | 中文詞沒有 word boundary，中文一律逐行人工判讀 |
| **M7** | **位元組層 parquet 比對**（本機無 `pandas`／`pyarrow`，且**不得 `pip install`**） | 11 個 series id 中 9 個在 `data_cache/fred_indicators.parquet` 的位元組裡明文命中 | `<負控串>` → 0 | **這是位元組推論，不是讀表**；壓縮或字典編碼理論上可能藏字 |

### ⚠️ 負控本身踩到的坑（就地登記）

第一次用的負控字串是上一輪稽核用過的 `<負控串>` ——
**它在 `inv/DB_INVENTORY.md` 命中 10 次**（上一輪把它寫進報告、盤點表引用了）。
**一個在目標檔裡命中 10 次的負控，等於沒有負控。**
本輪改用**本輪自訂的隨機串**（`<負控串>`，依規則不寫進文件），實測在 `spec/UI_SPEC.md`、`inv/DB_INVENTORY.md`、
全 repo `*.py` **三處皆 0**，之後全程使用。

### ⚠️ 本組自己在落筆時犯的兩個行號錯（就地登記，不是別人抓的）

初稿有兩處行號**是從 `sed -n 'A,Bp' | cat -n` 的「偏移量」換算出來的，不是單獨印出來的**，
出稿前自查時逐一重印，兩處都錯：

| 初稿寫的 | 實際 | 差 |
|---|---|---|
| `inv/DB_INVENTORY.md:1133`（「本節 15 列中 10 列翻成只寫不讀」） | **`:1132`** | 1 行 |
| `inv/DB_INVENTORY.md:1156`（「這條帳等於一本沒有人翻的流水帳」） | **`:1154`** | 2 行（`:1156` 其實是 §3.2 的標題） |

**成因與本報告 §0 M5 那條紀律要防的**完全是同一件事**：只要行號是「數出來」而不是「印出來」的，
它就會錯。**兩處已改，並在此留痕。**
出稿前另跑了一支機械檢查，把本報告全部 **71 個 `檔案:行號` 引用**逐一對回檔案：
**70 個在界內**，剩下 1 個是 `oauth_state.py` 這個 basename 在 repo 裡有兩份
（`ui/helpers/oauth_state.py` 只有 12 行的 shim ／ `ui/helpers/io/oauth_state.py` 161 行），
**已在該處補上完整路徑**。
⚠️ **那支檢查只驗「檔案在不在、行號在不在界內」，不驗「那一行是不是它自稱的東西」** ——
內容那一層是本組逐行 `awk 'NR==N'` 印出來人工核對的（`app.py` 11 行、
`page_01/02/04/05` 共 31 行、盤點表 6 行）。

### 本方法**結構上看不到**的（誠實劃界）

1. **不跑任何測試、不啟動 Streamlit。** 所有「到得了畫面」都是靜態讀碼推論，
   不是 AppTest 實測。條件分支下永遠走不到的渲染點，本方法看不出來。
2. **不讀 parquet**（無 pandas，且不得 `pip install`）→ §2 (4) 的 PPI／銅價只能做位元組層推論。
3. **未讀 `docs/wireframes/ia-wireframe.html`** —— 規格多處宣稱「線框逐字」，
   本組**沒有回頭比對線框本身**，只比對 repo 內自稱引用線框的常數。
4. **未重驗上一輪 M1~M20 的原始判定是否正確**，只驗「新版有沒有修掉它指出的那件事」。
5. **窮舉句一律不宣稱**。下面任何「N 塊」「N 欄」都是**分類敘述**，
   涵蓋範圍就是各該條寫出來的那條指令；**「沒有第 N+1 個」本組不宣稱**。

---

## 1. 九件事逐項結論

| # | 項目 | 結論 |
|---|---|---|
| **(1)** | 四件是否真的齊全（21 塊） | **21 塊四件全部抽得到，且全部是可解析的具體物件，未發現佔位** ✓ |
| **(2)** | 三個標籤是否照定義、逐欄判 | **⛔ 4 條矛盾**：④-4 標「沿用」但其 8 個具名欄在盤點表全是「只寫不讀／內部」（**R1**）；②-1／②-2 標「沿用（部分）」卻自陳「全部到得了」（**R3／R4**）；④-6 標「沿用（部分）」但**沒有逐欄列**（**R5**）。①-2／①-3／②-3／①-5／⑤-2 的逐欄列**做對了** ✓ |
| **(3)** | 那 6 塊的處置站不站得住 | 補回的 4 塊（M1 影子基金重疊／M3 四塊／M6 資料來源健康度／M2 配息月曆）**來源全部在 `origin/main` 上實測存在** ✓；換理由的 **M5（乙-2）實測完全成立** ✓；**M4（乙-1）的理由只成立一半 → R7** |
| **(4)** | M7–M20 是否真的修掉 | **14 條逐條查完：12 條修掉 ✓、1 條（M16）以就地但書處理（見 R11 附記）、1 條（M9）新版換了說法但被實測推翻（R6）**。M12／M13／M20 三條逐字驗過，**全部修掉** ✓ |
| **(5)** | 自陳「六條裁示以外的一處」的三個事實 | **(a) `_fund_pool` 0 命中 → 事實成立 ✓；(b) `load_series` 0 命中 → 事實成立 ✓；(c) 檔頭那句**逐字不符**：原文是「四塊全部是真資料**或誠實的空狀態**」，轉述漏了後半** |
| **(6)** | 裁示 6 那段是否正確 | **11 個行號逐行印出，全部對上** ✓。唯一問題是兩份行號清單**並列時的配對順序**會誤導（**R12**） |
| **(7)** | 母法禁令（獨立重掃） | **關鍵字 23 個詞逐一掃，命中 5 個詞共 6 處，逐行讀後 0 條違規** —— 全在禁令句或排除清單裡。**語意閱讀亦未發現沒踩關鍵字的買賣建議句。** ④ 再平衡試算**確實寫死「三欄皆使用者填」「⛔ 不出執行鈕」** ✓（裁示 4 落實）。⚠️ 另有一個**規格自訂規則**被規格自己違反 → **R8** |
| **(8)** | 排除清單是否誠實 | 甲 8 條**逐條實測、8 條的事實基礎全部成立** ✓；乙 3 條**出處全部找得到**（乙-1 的推論半段見 R7）；丙 11 塊**逐一回溯上一版排除清單，11 塊全部對得上** ✓；bullet 數 ＝ 區塊數 ＝ 11 ✓（M18 的病沒有復發）。**但**：甲-8 的缺項不是四件之一（**R10**）；且有一批**線上真的在渲染**的區塊**兩份清單都沒有**（**R9**） |
| **(9)** | 尺寸 | `wc -l` **149**／`LC_ALL=C.UTF-8 wc -m` **7000**／`python3 len()` **7000**／`wc -c` **13964**。**是 7,000，不是 7,001** ✓。上限 180 行 / 7,000 字元 → **兩項都在界內，字元數剛好貼齊上限** |

---

## 2. 逐項實測（指令與真實輸出）

### (9) 尺寸 —— 先放，因為它最短而且四個數字都要

```
$ wc -l   spec/UI_SPEC.md                   → 149
$ wc -c   spec/UI_SPEC.md                   → 13964
$ LC_ALL=C.UTF-8 wc -m spec/UI_SPEC.md      → 7000
$ wc -m   spec/UI_SPEC.md   (LANG 為空)     → 13964      ← 靜默退化成位元組數
$ echo "LANG=[$LANG] LC_ALL=[$LC_ALL]"      → LANG=[] LC_ALL=[]
$ python3: len(chars)=7000  len(bytes)=13964  len(splitlines())=149  endswith \n = True
```

**四個量法互相對得起來**：`LC_ALL=C.UTF-8 wc -m` 與 python `len()` **都是 7000**，
`wc -c` 與**預設 `wc -m`** 都是 13964 —— 也就是上一輪那個「8,845 位元組被當成字元數」的坑，
**本輪沒有復發**。**7,000 是剛好貼齊，不是 7,001。**

### (6) 裁示 6 那段 —— 11 個行號逐行印出

```
$ git show origin/main:app.py | awk 'NR==N'
581  (tab_macro, tab_health, tab_research, tab_portfolio, tab_settings,
582   tab_preview_health, tab_preview_settings, tab_preview_research,
583   tab_preview_portfolio) = st.tabs(
584     [_tab_label("macro"), _tab_label("health"), _tab_label("research"),
585      _tab_label("portfolio"), _tab_label("settings"),
586      _preview_tab_label("health"), _preview_tab_label("settings"),
587      _preview_tab_label("research"), _preview_tab_label("portfolio")])
636             render_market_overview()            ← ① 正式格
648             render_fund_grp_health_tab()        ← ② 正式格（舊）
662             render_fund_research_tab()          ← ③ 正式格（舊）
673             render_portfolio_tab()              ← ④ 正式格（舊）
688             render_settings_diag_tab()          ← ⑤ 正式格（舊）
720             render_holdings_health()            ← ⑥ 預覽（＝新 ②）
728             render_settings_and_diagnostics()   ← ⑦ 預覽（＝新 ⑤）
752             render_fund_research()              ← ⑧ 預覽（＝新 ③）
776             render_asset_allocation()           ← ⑨ 預覽（＝新 ④）
$ grep -n "render_market_overview" app.py
156:from ui.views.page_01_macro import render_market_overview      ← ① 確為新頁
```

**九格 ＝ 5 個 `_tab_label` ＋ 4 個 `_preview_tab_label` ✓；`:581-587` ✓；
`:636` ① 跑新頁 ✓；`:648/662/673/688` ②③④⑤ 跑舊版 ✓；`:720/728/752/776` 是預覽格 ✓。**
**11 個行號一個都沒錯。** 唯一的問題是配對順序 → **R12**。

### (5) 生產組自陳「六條裁示以外的一處」的三個事實

```
$ grep -c "_fund_pool"  ui/views/page_03_research.py        → 0     ✓ 事實成立
$ grep -c "load_series" ui/views/page_03_research.py        → 0     ✓ 事實成立
  正控（兩個符號在別處都還活著，所以 grep 沒壞）：
  $ grep -rn "_fund_pool"  --include=*.py . | grep -v ^./tests/  → repositories/pool_repository.py:26 _WS_POOL = "_fund_pool" 等 8 行
  $ grep -rn "load_series" --include=*.py . | grep -v ^./tests/  → services/nav_history_gs.py:818 def load_series( ／ services/fund_service.py:1095 s_hist = load_series(...)
  負控：$ grep -c "<負控串>" ui/views/page_03_research.py → 0
```

**第三個事實（檔頭「四塊全部是真資料」）—— 逐字印出後不符**：

```
$ git show origin/main:ui/views/page_03_research.py | awk 'NR==8'
   **同一批恢復線框的「選定後展開」gate** —— 本頁**四塊全部是真資料或誠實的空狀態**，
```

**原文是「四塊全部是真資料**或誠實的空狀態**」。** 轉述把後半句拿掉了。
「四塊」與「已接真資料」兩件事**成立**；**「全部是真資料」這個沒有但書的版本不成立**。
⛔ 依指派，本組**不判定該不該換掉舊 ③-1／③-2**，只驗事實。

**附帶查證（新 ③ 的來源符號是否真的存在，含別名 import 先列）**：

```
$ grep -n "^from \|    from " ui/views/page_03_research.py
281:from services.moneydj_fetcher import auto_fetch_moneydj      ✓
286:from services.fund_search import (  ... search_funds ... )    ✓
305:from services.fund_invest_calc import ( ... )                 ✓
327:from services.health.dividend_calc import latest_dividend_per_unit   ✓
2453:    from ui.helpers.fund_grp_health.unified import build_batch_unified_row  ✓
```
盤點表 §3.3 亦有 `v03_research_batch_rows`（`ui/views/page_03_research.py:669`）✓

### (1) 四件是否真的齊全

自寫 parser 對 24 個 `###` 標題切塊（21 個 UI 區塊 ＋ 3 個排除清單小標），
逐塊抽 `- 來源：/ - 規則：/ - 空狀態：/ - 回答：`：

```
21 個 UI 區塊：四件缺 = 無   ×21
3 個排除清單小標（甲/乙/丙）：四件缺 = 全部（預期內，它們不是區塊）
```

**逐塊人工判讀「有沒有真的填」**：21 塊的「來源」全部具體到
`表.欄位` / `模組.函式` / `常數名`，**沒有一塊寫「持倉資料」「依情況顯示」這種佔位** ✓。
最接近佔位的兩塊本組逐一讀過：
- **②-2 空狀態**「標的都沒持股／產業資料 → 灰態列缺料代碼」——
  指名了行為（列出缺料的**代碼**），實作對得上（`page_02_health.py:1314,1321` 的 `_blind` 清單）→ **不算佔位**
- **①-3 空狀態**「表下註記『⬜ 綜合健康度只印分數、不給等級』」——
  它其實是**註記**不是空狀態，但內容具體 → **不算佔位**

### (2)「三個標籤」是否照定義、而且逐欄判

**標籤計數（扣掉第 10~12 行的定義句本身）**：

```
$ grep -o "\*\*沿用\*\*"        spec/UI_SPEC.md | wc -l  → 11   （含 L10 定義） ⇒ 內文 10
$ grep -o "\*\*沿用（部分）\*\*" spec/UI_SPEC.md | wc -l  →  9   （含 L11 定義） ⇒ 內文  8
$ grep -o "\*\*新建\*\*"        spec/UI_SPEC.md | wc -l  →  6   （含 L12 定義） ⇒ 內文  5
```

**⚠️ 生產組自稱「新建 6」，檔內實測是 5**（`①-1` / `③-1` / `③-2` / `③-3` / `④-2` 各一）。
10 ＋ 8 ＋ 5 ＝ 23 個標籤分佈在 21 塊上（①-1 與 ④-2 各帶兩個標籤）→ **內部自洽**。
**「6」這個數字只有把 L12 的定義句一起數進去才成立。**

**逐塊回盤點表對「誰讀它」（M2 解析的 231 列）**：

| 規格區塊 | 標籤 | 規格寫的來源 | 盤點表「狀態／誰讀它」 | 判定 |
|---|---|---|---|---|
| ①-1 | 沿用 | `indicators` | §3.5 未落地 ／ **UI** | ✓（走 L14 但書） |
| ①-1 | 新建 | `_macro_weights.B` | §1.9 只讀不寫 ／ **UI** | ✓（理由是「無寫入口」＝定義第二支「需新建讀寫路徑」） |
| ①-2／①-3／①-5 | 沿用（部分） | `indicators` 逐欄 | 同上 | ✓ 有逐欄列；但 `prev` 那一欄 → **R6** |
| ①-4 | 沿用 | `_SK_RADAR` | **盤點表 0 命中** | **R11** |
| ②-1 | 沿用（部分） | `moneydj_raw.*`／`.metrics.*`／`.dividends` | §3.2 未落地 ／ **UI** | 欄位對；**標籤與自述互斥 → R3** |
| ②-2 | 沿用（部分） | `.moneydj_raw.holdings.*` | 同上 | 同上 → **R4** |
| ②-3 | 沿用（部分） | `HEALTH_TABLE_COLUMNS` 9 欄 | — | ✓ 逐欄列（8 到得了／1 到不了） |
| ③-1／③-2／③-3 | 新建 | 即時取數，不屬盤點表 | — | ✓ 已就地聲明 |
| ④-1 | 沿用 | `invest_twd`／`policy_tier`／`is_core` | §3.2 三欄皆 **活的 ／ UI** | ✓ |
| ④-2 | 新建 | session `portfolio_core_pct` 預設 75 | 盤點表 0 命中（已標） | **鍵與預設值與新 ④ 不符 → R2** |
| ④-3 | 沿用 | `<保單分頁v2>` 6 欄 | §1.2b 六欄皆 **活的 ／ UI** | ✓ |
| ④-4 | 沿用 | `ledger_json → transactions[]` | §3.1 八欄皆 **只寫不讀 ／ 內部** | **⛔ R1** |
| ④-5 | 沿用 | `portfolio_funds[].dividends` | §3.2 未落地 ／ **UI** | ✓（走 L14 但書） |
| ④-6 | 沿用（部分） | `.moneydj_raw.top_holdings`／`.sector_alloc` | 同上 | **無逐欄列 → R5** |
| ④-7 | 沿用 | ① 位階 ＋ `summarize_core_satellite` | 衍生值 | ✓ |
| ⑤-1 | 沿用 | `nav_history.code`／`.date`／`.nav` | §1.6 三欄皆 **活的 ／ UI** | ✓ **且刻意避開了同表 3 個「只寫不讀／內部」欄** |
| ⑤-2 | 沿用（部分） | `secrets.*` 9 欄 | §4 刻意未填「誰讀它」 | ✓ 逐欄列（7／2），另以 grep 實測 |
| ⑤-3 | 沿用 | `data_registry` | §3.5 未落地 ／ **UI** | ✓（走 L14 但書） |

**⑤-1 值得單獨記一筆（這是本輪看到最明顯的「真的有逐欄判」的證據）**：
盤點表 §1.6 的 `nav_history` 有 7 欄，其中 `fund_name`／`source`／`recorded_at`
是「只寫不讀 ／ 內部」。**規格只列了 `code`／`date`／`nav` 三個「活的 ／ UI」欄，
一個「內部」欄都沒有被當成「沿用」拖進來。** 那不是碰巧對的形狀。

### (3) 那 6 塊的處置站不站得住

**補回的（M1／M3／M6／M2）—— 來源逐一實測存在**：

```
M1 ②影子基金重疊 → ui/views/page_02_health.py:1317-1319
     _h = _mj(_f).get("holdings") or {}
     _tops = _clean_holdings(_h.get("top_holdings"))
     _sects = _h.get("sector_alloc") or []
   :1333  from services.portfolio_service import calc_holdings_overlap           ✓
M3 ①-4 ⚡③例外  → page_01_macro.py:817 def _card_exceptions(ev: dict) -> dict:  ✓
   ①-5 🔍④可信度 → 同檔 :922 _v.get("is_proxy") / :923 _prov.get("sources")      ✓
   ④-6 穿透式    → page_04_portfolio.py:2523-2524 (_f.get("moneydj_raw") or {}).get("top_holdings"/"sector_alloc")  ✓
   ④-7 總經曝險  → :2786-2787 st.markdown(f"#### {BLOCK_MACRO_LINK}") / safe_section(...)  ✓
M6 ⑤-3 資料來源健康度 → page_05_settings.py 委派鏈；grep -rl "_update_data_registry" → prod 10 檔 ✓
M2 ④-5 配息月曆 → DIVCAL_GATE_LABEL: str = "載入本月配息月曆（要算幾秒）"（page_04_portfolio.py:802） ✓
```

**⭐ 一個生產組自己發現、而且本組複跑確認的真差異（值得記）**：
規格 ④-6 就地註「⚠️ 與 ②-2 形狀不同，那邊走 `.holdings.*`」——
**實測兩邊真的不同形狀**：② 走 `moneydj_raw.holdings.{top_holdings,sector_alloc}`
（`page_02_health.py:1311` docstring 逐字「持股／產業住在 `moneydj_raw.holdings`」），
④ 走 `moneydj_raw.{top_holdings,sector_alloc}`（`page_04_portfolio.py:2523-2524`）。
**上一輪沒有人指出這件事。**

**換理由的 M5（乙-2）—— 本組獨立複跑，完全成立**：

```
$ git show origin/main:ui/views/page_01_macro.py | awk 'NR==767'
def _card_allocation(ev: dict) -> dict:                                  ← 規格寫 :767 ✓
$ ... awk 'NR==770'
    ⚠️ **`ndc_score` 一律傳 `None`**：...
$ ... awk 'NR==785'
    _al = allocation_from_composite(ev.get("score"), None)                ← ndc_score 恆 None ✓
$ ... awk 'NR==811'
        "note": ("錢該放在哪一類資產的建議（不是「核心／衛星」那種角色分配）。"   ← 規格引的那句 ✓
$ services/allocation_ladder.py:45-48
    _light, _ = ndc_light(ndc_score)
    if _light is None:
        return {"stop_gain_z": ZSCORE_STOP_GAIN_DEFAULT, "add_z": ZSCORE_ADD_DEFAULT, ...}
$ shared/signal_thresholds.py:409  ZSCORE_STOP_GAIN_DEFAULT: float = 1.75
$ shared/signal_thresholds.py:410  ZSCORE_ADD_DEFAULT: float = -1.0
```

→ `ndc_score` 恆 `None` ⇒ `ndc_light` 回 `(None, None)` ⇒ **門檻恆走 1.75／−1.0 的 default 分支**。
**規格的「門檻又恆固定」是一條完整的因果鏈，三個環節本組逐一印出，全部成立 ✓**

**換理由的 M4（乙-1）—— 出處有，但推論被實測推翻一半 → R7**（詳見矛盾清單）。

### (4) M7–M20 逐條

| # | 上一輪指控 | 新版怎麼處理 | 本組複驗 |
|---|---|---|---|
| **M7** | ②-1 被列為區塊且規則已定，但新 ② 說那是未答覆的業務規格 | **移進排除清單 甲-1**，理由逐字改用 repo 自己的說法 | ✅ 修掉。`page_02_health.py:11-15` 逐字「該用哪一個屬**業務規格**，已送客戶、尚未答覆」 |
| **M8** | ②-1 來源列 `.policy_tier`，新 ② 0 命中 | 新 ②-1 來源換成三層配息率鏈，**不再提 `.policy_tier`** | ✅ 修掉。`grep -c policy_tier ui/views/page_02_health.py` → **0**（正控 `invest_twd` → 15、負控 → 0） |
| **M9** | ①-2 用 `color`／`series`，新 ① 兩個都沒讀 | 改成「到得了 `value`／`unit`／`signal`；到不了 `color`／`series`／`prev`」 | ⚠️ `color`／`series` **修對了**（`\bcolor\b`=1 在註解、`\bseries\b`=0）；**但 `prev` 被實測推翻 → R6** |
| **M10** | ①-3 規則與那 5 欄對不上 | 改成「欄位＝`EVIDENCE_COLUMNS` 5 欄」「逐桶一列…**非逐指標、無「前值」欄**」 | ✅ 修掉。`beginner_view.py:795` 5 欄逐字相符；`:856` 逐字「🌳 長期 → 🩺 綜合健康度 → 📈 中期 → 🎯 短線 → ⚠️ 拐點 → 📰 新聞」＝規格寫的六列 |
| **M11** | ④-1 要印目標％，但來源不含目標，且誰填須裁決 | ④-1 改「＋目標比例（使用者填，見 ④-2）」；④-2 改「由使用者輸入」 | ✅ 上呈那半修掉（裁示 4 落實）；**但 ④-2 指的那個 session key 不是新 ④ 用的那個 → R2** |
| **M12** | ④-3 給 8 欄清單，守衛禁止 | 改成「⛔ **本規格不列欄位清單**…守衛 `test_the_ledger_invents_no_column_list`」 | ✅ 修掉。守衛逐行印出：`tests/test_wf04_portfolio_skeleton.py:2571 def test_the_ledger_invents_no_column_list():`；規格全檔已無該欄位清單 |
| **M13** | ①-1 手抄「📡 載入總經資料」 | 改引 `MACRO_LOAD_BTN_AGAIN`（並註明現值「🔄 更新總經資料」） | ✅ 修掉，**而且引對了那一個**：`shared/ui_control_labels.py:30 MACRO_LOAD_BTN_FIRST = "📡 載入總經資料"` / `:31 MACRO_LOAD_BTN_AGAIN = "🔄 更新總經資料"`，該檔 `:28-29` 逐字「卡片的「去哪補」**必須**指名下面那個 `AGAIN` 版本」 |
| **M14** | ⑤-2 說 9 欄全沿用，2 欄查不到顯示面 | 改成「沿用（部分）：到得了 7／到不了 2」 | ✅ 修掉。實測見下方表 |
| **M15** | ②吃本金的第 1 層來源沒列 | 新 ②-1 三層全列，順序也對 | ✅ 修掉。`services/health/dividend.py:317-350` 逐字 1.`moneydj_div_yield` → 2.`metrics.annual_div_rate` → 3.`divs[]` |
| **M16** | 「沿用＝盤點表判活」vs 盤點表標「未落地」 | 加 L14 但書：「盤點表『未落地』量的是持久化、不是到不到得了畫面」，並點名 5 個鍵 | ⚠️ **但書涵蓋了「到得了畫面」那一半，沒有涵蓋「判活」那一半**（盤點表狀態欄的值仍是「未落地」，不是「活的」）→ 見 R11 附記。**5 個被點名的鍵本組逐一對過，誰讀它全部是 UI** ✓ |
| **M17** | ①-1 第二個來源沒有標籤 | 改成「`_macro_weights.B`（**新建**，無寫入口）」 | ✅ 修掉。且「無寫入口」屬實：`services/macro/weights_store.py:154-157` 逐字「**本模組今日沒有 production 寫入端**…active payload 由使用者**手動編輯**該分頁的 B3 儲存格」 |
| **M18** | 「以下才是四件不齊的」對至少 3 條不成立 | 改成 甲（四件不齊 8）／乙（四件齊、另有理由 3）／丙（已補回 11）三段 | ✅ 結構性修掉，**且「逐筆交易流水」已正確移進乙**。⚠️ 但甲-8 的缺項不是四件之一 → **R10** |
| **M19** | `_Ledgers`「無現成讀取路徑」兩份上游寫法相反 | 硬約束 2 改成「`load_all_ledgers` **整張讀得回**，消費端只取 `len()`」＋標明客戶裁定 | ✅ 修掉，**兩半都寫進去了**。實測 `ui/helpers/portfolio/policy_admin_section.py:825-826` 逐字 `_led_df = load_all_ledgers(...)` / `_led_ct = len(_led_df)`，`:844` 自陳 `_sheet_stats` **全 repo 無讀取端** |
| **M20** | 「離線倉 0 列」字面與 13,654 列衝突 | 改成「`PPIACO`／`PCOPPUSDM` **兩支** 0 列（不是「倉 0 列」：`fred_indicators` 13,654 列）」 | ✅ 修掉，兩個數字都驗過（見下） |

**M14 的實測（⑤-2 的 7 vs 2）**：

```
key                     page_05  tab5_data_guard  settings_diag
FRED_API_KEY               1          13               0
GEMINI_API_KEY             0           4               0
FINMIND_TOKEN              0           2               0
NAV_SHEET_ID               1           0               0
macro_weights_sheet_id     0           3               0
google_service_account     1           5               0
PROXY_URL                  0           2               1
POLICY_SHEET_ID            0           0               0   ← 到不了
POOL_SHEET_ID              0           0               0   ← 到不了
<負控串>                   0           0               0   （負控）
```
⚠️ **就地標明射程**：規格寫「（皆 0 命中）」——**那個 0 是「在 ⑤ 與它委派的對象裡是 0」**，
不是全 repo。全 `ui/` 內 `POLICY_SHEET_ID` 仍有 3 處（`ui/helpers/io/oauth_state.py:40` 是真讀取）、
`POOL_SHEET_ID` 2 處（都是文案）。**在 ⑤ 的射程內規格是對的**；本組登記這個射程差，不裁決。

**M20 的實測**：

```
$ python3 -c "...json.load('data_cache/metadata.json')..."
fred_indicators -> 13654 (2026-09-10)   ← 規格寫 13,654 ✓
vix_history -> 3841 / spx_history -> 3839 / twii_history -> 3726
$ scripts/update_macro_history.py:65-74  FRED_SERIES_IDS = 11 個
$ grep -c "<id>" data_cache/fred_indicators.parquet   （位元組層）
  DGS10=1 DGS2=1 DGS3MO=1 BAMLH0A0HYM2=3 M2SL=1 WALCL=3 CPIAUCSL=1 UNRATE=1 DTWEXBGS=1
  PPIACO=0   PCOPPUSDM=0        ← 規格寫「兩支 0 列」✓
  <負控串>=0                    （負控）
$ grep -c PPI services/macro/validation.py     → 0
$ grep -c -i copper services/macro/validation.py → 0     ← 「無此分支」✓
```
⚠️ **這是位元組層推論，不是讀表**（本機無 pandas 且不得 `pip install`）。

### (7) 母法禁令 —— 獨立重掃，未引用生產組的自掃

⚠️ **下面這串是「被掃描的禁用詞清單」的引文，不是任何動作建議。**

```
$ for w in 建議買進 立即出清 應該加碼 推薦 必漲 目標價 一鍵再平衡 最佳配置 買進 賣出 出清
           加碼 減碼 停利 停損 換股 執行鈕 一鍵 建議 應該 提高現金 降低 配置建議 <負控>; do ...
命中：推薦 1 ／ 一鍵再平衡 1 ／ 最佳配置 1 ／ 執行鈕 1 ／ 一鍵 1 ／ 建議 2   （其餘 17 詞皆 0；負控 0）
```

**逐行讀完 6 處命中，全部在禁令句或排除清單裡**：

| 行 | 逐字 | 判讀 |
|---|---|---|
| L81（④-1） | `⛔ **不出買賣動作、無一鍵再平衡鈕**` | **禁令句**，不是建議 |
| L86（④-2） | `⛔ **不出執行鈕**` | **禁令句** |
| L111（④-7） | `⛔ **不出買賣動作**` | **禁令句** |
| L145（乙-2） | `note 印「錢該放在哪一類資產的**建議**」＝母法⛔嚴禁的預設最佳配置推薦` | **在描述被排除的理由**，且是引述 `origin/main` 的字 |

**語意閱讀（主要手段）—— 21 塊逐塊讀完，沒有找到「沒踩關鍵字但實質是買賣建議」的句子。**
逐塊的「回答」欄全部是**診斷式問句**（「有沒有基金在拿本金發配息」「哪一檔哪一項在拖後腿」
「真正押在哪幾檔個股」「離目標差多少錢」），**沒有一句是「你應該怎麼做」**。

**④ 再平衡試算的專項檢查（裁示 4）**：
L86 逐字「**三欄皆使用者填**：目標核心比例（滑桿）／可動用金額（0＝不試算）／只調衛星；
拖滑桿當下不觸發取數或重算，按「試算」才算。**輸出只有現況／目標／偏離與差額**。
⛔ **不出執行鈕**」→ **裁示 4 的兩件事（目標使用者填、不出執行鈕）都寫死了 ✓**

⚠️ **本組另行登記一個邊界，不裁決**：④-2 的「差額」是一個金額數字。
它**完全由使用者自己填的目標推導**，不含任何系統推薦的目標，
因此**不落在「預設最佳配置推薦」的射程內**；但它離那條線最近，**登記給客戶看一眼**。

⚠️ **反過來掃到的那一條不是母法問題，是規格自訂規則被規格自己違反 → R8。**

### (8) 排除清單是否誠實

**甲 8 條逐條實測（8 條的事實基礎全部成立）**：

| 甲 | 規格說 | 本組實測 |
|---|---|---|
| 1 | ②組合健康總分 — 缺規則，屬業務規格已送客戶未答覆 | ✅ `ui/views/page_02_health.py:11-15` 逐字相符 |
| 2 | ②衛星連續落後 — `tag_benchmark_lag` 要 L1，該頁禁 import，services 無替代 | ✅ 同檔 `:16-20` 逐字相符 |
| 3 | ②「🧾 ② 依據」區頭 — 只有 docstring、全檔無渲染 | ✅ `grep -n "② 依據" ui/views/page_02_health.py` → **只有 `:57` 一行，在 module docstring 內**；`EVIDENCE_HEADING` 該檔 0 命中；對照 `CONCLUSION_HEADING`（`:623`）有被 `st.markdown` 渲染（`:932`） |
| 4 | ①PPI／銅價歷史值 — `load_indicators_from_parquet` 無此分支；兩支 0 列 | ✅ 見上方 M20 |
| 5 | 全站最近查過的基金 — 在寫，但 `get_history_df` 非測試呼叫 0 | ✅ `grep -rn get_history_df --include=*.py . \| grep -v ^./tests/` → **只有 `services/fund_history.py:158` 的 `def` ＋ `:10` 的 docstring**；寫入端確實存在（`ui/tab2_single_fund.py:383`、`ui/tab3_portfolio.py:1565` 呼叫 `record_fund`） |
| 6 | 全站 15 年總經歷史／回測 — `data_cache/*.parquet` 只有離線 script 讀 | ✅ **而且比規格寫的更強**：讀 parquet 的 L2 函式 `services/macro/validation.py:234 calc_macro_score_series` 本身 **production 0 caller**（`grep -rn calc_macro_score_series` → 1 個 `def` ＋ 1 行 scripts 註解 ＋ 11 行 tests） |
| 7 | 全站預設基金清單 — `config/preset_funds.json` 零消費者 | ✅ `_load_with_defaults` 唯一 caller 是 `get_history_df`（見甲-5，零 caller）；`add_preset_fund` / `export_preset_funds_json` 模組外 0 caller。與盤點表 §2.14 同結論 |
| 8 | 全站總經權重編輯 — `_macro_weights` 無 App 入口，只能手填 | ✅ `services/macro/weights_store.py:154-157` 逐字相符。**但「缺寫入端」不是四件之一 → R10** |

**乙 3 條的出處**：

| 乙 | 出處 | 本組實測 |
|---|---|---|
| 1 | `REASON_PERF`（`page_04_portfolio.py:1102-1106`） | 出處逐字存在 ✓；底層「一渲染就打一次匯率 API」屬實（`ui/helpers/portfolio_perf.py:37` 無條件呼叫 `fetch_usdtwd_frame`）；**但「每次互動一次網路往返」被 `@st.cache_data(ttl=TTL_10MIN)` 推翻 → R7** |
| 2 | `page_01_macro.py:767/785/811` ＋ `shared/signal_thresholds.py:409-410` | ✅ 三個環節逐行印出，**完全成立** |
| 3 | 硬約束 2（`_Ledgers`） | ✅ 見 M19 |

**丙 11 塊逐一回溯上一版排除清單**：

```
①-4 ⚡③例外        ← 舊 L106   ✓      ①-5 🔍④可信度   ← 舊 L106  ✓
②-2 影子基金重疊    ← 舊 L107   ✓      ②-3 逐檔體檢表   ← 舊 L98   ✓（裁示 5）
③-1 搜尋結果        ← 舊 L103   ✓      ③-3 批次分析     ← 舊 L104  ✓
④-2 再平衡試算      ← 舊 L105   ✓（裁示 4）
④-5 配息月曆        ← 舊 L107   ✓      ④-6 穿透式持股   ← 舊 L106  ✓
④-7 總經曝險聯動    ← 舊 L106   ✓      ⑤-3 資料來源健康度 ← 舊 L108  ✓
共 11 塊，11/11 都在上一版的排除清單裡。
bullet 數 = 11 = 區塊數（甲 8 + 乙 3）→ 上一輪 M18「14 條 bullet 卻點名 20 個區塊」的病沒有復發 ✓
```

**⑤-2 那個 `HEALTH_TABLE_COLUMNS` 也順帶驗了（裁示 5 的落實）**：

```
$ git show origin/main:ui/views/page_02_health.py | awk 'NR>=278 && NR<=281'
HEALTH_TABLE_COLUMNS: tuple[str, ...] = (
    "代碼", "名稱", "幣別", "近 1 年", "Sharpe",
    "最大回撤", "配息覆蓋", "五桶評等", "資料日期",
)
$ ... awk 'NR==1399'      五桶評等  **無來源** —— 見下
$ ... awk 'NR==1402'   ⛔ **「五桶評等」整欄恆為 `⬜`，這是刻意的，不是還沒接。**
$ ... awk 'NR==1408'      欄位本身**不刪**（線框是客戶拍板的，增刪欄位屬客戶 gate）
```
**9 欄逐字相符、到不了的那 1 欄指認正確、「欄位不增不刪」也對得上 ✓**

---

## 3. 矛盾清單（14 條，**一律不裁決**）

> 格式固定：**A 說 X（出處）／B 說 Y（出處）／兩者不能同時為真**。
> 行號一律 `git show origin/main:<path> \| awk 'NR==N'` 單獨印出後照抄。

### R1｜④-4 標「沿用」且自稱「§3.1 全活」，而盤點表 §3.1 那 8 個欄位全部是「只寫不讀／內部」

- **A 說**（`spec/UI_SPEC.md:95` 逐字）：
  `- 來源：`_T7_State.ledger_json` → `transactions[]`（**沿用**，§3.1 全活）；session `t7_ledgers``
- **A2 說**（同檔 `:10` 逐字，標籤定義）：
  `- **沿用**＝盤點表判活、且本區塊要用的每一欄都到得了畫面`
- **B 說**（`inv/DB_INVENTORY.md:1103-1110`，8 列逐列）：
  `| `t7_ledgers{pk_str}.transactions[].txn_type` | ~~活的~~ → **只寫不讀** | **內部** | …`
  `| `.transactions[].txn_date` | ~~活的~~ → **只寫不讀** | **內部** | …`（`amount_twd` / `fx_rate` / `nav` / `div_per_unit` / `new_units` / `note` 同形）
  同節 `:1132` 逐字：`> 📌 **2026-09-16 顆粒度輪：本節 15 列中 10 列由 ~~「活的（有落地）」~~ 翻成「只寫不讀」**`
  同節 `:1154` 逐字：`> **這條帳等於一本沒有人翻的流水帳。**`
- **兩者不能同時為真。**
- 📌 **這正是客戶裁示 1（看欄，不看表）要打出來的那一格**：`_T7_State.ledger_json`
  這個**容器欄**在盤點表 §1.3 確實是「活的 ／ UI」，但它**裡面**的 `transactions[]` 八欄
  在同一份盤點表裡已被逐欄翻成「只寫不讀 ／ 內部」。
  **規格取的是容器的狀態，寫的是內容的名字。**

### R2｜④-2 指名的 session key 與預設值，都不是新 ④ 用的那一個

- **A 說**（`spec/UI_SPEC.md:85` 逐字）：
  `- 來源：目標比例**由使用者輸入**（**新建**：session `portfolio_core_pct` 預設 75，**盤點表 0 命中**、不落地，要留存得新建寫入路徑）＋④-1 現況（**沿用**）`
- **A2 說**（同檔 `:5`）：本規格寫的是**預覽格**（`:720/728/752/776`）＝ `ui/views/page_0*.py`
- **B 說**（`ui/views/page_04_portfolio.py:555-560` 逐字）：
  `# ⚠️ 刻意**不**沿用舊 ④ 的鍵：舊頁依方針第 3 條仍在磁碟上、且仍接在 `app.py`，`
  `#    共用鍵會讓兩套 View 互相覆寫對方的狀態，而 payload 形狀並不相同。`
  `_FORM_KEY: str = "v04_portfolio_rebalance_form"`
  `_SK_APPLIED: str = "v04_portfolio_applied_plan"`
  同檔 `:574-575` 逐字：`#: 線框：「目標核心比例　70%」。理由與那個張力見模組 docstring。` / `_DEFAULT_CORE_PCT: int = 70`
- **B2 說**（實測）：`grep -n "portfolio_core_pct" ui/views/page_04_portfolio.py` → **2 行，`:1294` 與 `:1476`，兩行都是註解**，描述的是**舊 ④**；
  `grep -rc "portfolio_core_pct" ui/views/*.py` → 其餘四頁皆 **0**。
  該鍵的 75 來自 `ui/helpers/session.py:79` `"portfolio_core_pct": 75,`（舊 ④ 那條路）。
- **兩者不能同時為真**（鍵名不同、預設值 75 vs 70 也不同）。

### R3｜②-1 標「沿用（部分）」，同一行卻寫「三層都到得了」

- **A 說**（`spec/UI_SPEC.md:11` 逐字，標籤定義）：
  `- **沿用（部分）**＝有欄位到得了畫面，但不是每一欄都到得了 → 逐欄列`
- **B 說**（同檔 `:50` 逐字）：
  `- 來源（**沿用（部分）**，三層都到得了）：①`.moneydj_raw.moneydj_div_yield`（主）→②`.metrics.annual_div_rate`→③`.dividends``
- **兩者不能同時為真**（若三層都到得了，依 `:10` 的定義應為「沿用」而非「沿用（部分）」）。

### R4｜②-2 標「沿用（部分）」，同一行卻寫「兩欄都到得了」

- **A 說**：同 R3 的 `spec/UI_SPEC.md:11`
- **B 說**（同檔 `:55` 逐字）：
  `- 來源：`.moneydj_raw.holdings.top_holdings`／`.sector_alloc`（**沿用（部分）**：兩欄都到得了）`
- **兩者不能同時為真。**

### R5｜④-6 標「沿用（部分）」，但沒有逐欄列出到得了／到不了

- **A 說**（`spec/UI_SPEC.md:11` 逐字）：`…但不是每一欄都到得了 **→ 逐欄列**`
- **B 說**（同檔 `:105` 逐字，全行）：
  `- 來源：`.moneydj_raw.top_holdings`／`.sector_alloc`（**沿用（部分）**；⚠️ 與 ②-2 形狀不同，那邊走 `.holdings.*`）`
  —— 括號裡只有形狀提醒，**沒有任何「到得了 X／到不了 Y」的逐欄列**。
- **對照**：同一份規格的 ②-3（`:60`）與 ⑤-2（`:120`）都有逐欄列（8/1 與 7/2），①-2（`:30`）也有。
- **兩者不能同時為真。**

### R6｜①-2 寫 `prev` 到不了，但 `indicators` 的 `prev` 被讀出來、算成百分比、印在卡片上

- **A 說**（`spec/UI_SPEC.md:30` 逐字）：
  `- 來源：`indicators`（**沿用（部分）**）—**到得了**：`value`／`unit`／`signal`；**到不了**：`color`（僅註解）／`series`／`prev``
- **A2 說**（同檔 `:11`）：「到得了畫面」是這個標籤唯一的判準
- **B 說**（`ui/views/page_01_macro.py:1632-1633,1648` 逐字，逐行印出）：
  `1632	    _d = ind.get("ADL")`
  `1633	    _mom_pct = _d.get("prev") if isinstance(_d, dict) else None`
  `1648	    return {"title": "市場廣度 · RSP／SPY", "value": f"{_pct:+.2f}%",`
  該卡由 `:1546 _breadth_card(_ind),` 渲染，位在 `_render_detail_zone()` → `_render_deferred_blocks()`（`:2045`）的層 4 詳細區。
  同檔 `:1627` docstring 逐字：`而**月變動百分比**由服務層放在 `prev` 欄（同 dict 的 `unit` 也是空字串）。`
- **兩者不能同時為真。**
- 📌 **並陳另一半，不選邊**：①-2 指的是**六張指標卡**（`:2157-2164` 的
  `_card_phase` / `_card_vol_credit` / `_card_infl_rate` / `_card_hot_money` /
  `_card_risk_radar` / `_card_news`），而 `_breadth_card` **不在那六張裡**。
  **若把「到不了」讀成「這六張卡沒讀它」則 A 成立；若照 `:11` 的字面讀成「到不了畫面」則 B 成立。**
  **兩種讀法本報告一併登記。**

### R7｜乙-1 的「每次互動一次網路往返」與那支 fetcher 的 10 分鐘快取

- **A 說**（`spec/UI_SPEC.md:144` 逐字）：
  `1. ④組合績效 — **成本，不是缺規則**：算得出來，但既有那支**一渲染就打一次匯率 API**，這頁每次互動整頁重跑 ⇒ 每次互動一次網路往返（`REASON_PERF`）`
- **B 說**（`repositories/hot_money_repository.py:758-762` 逐字）：
  `@register_st_cache`
  `@st.cache_data(ttl=TTL_10MIN, show_spinner=False)`
  `def _cached_usdtwd_series(days: int) -> tuple[pd.DataFrame, str]:`
  `    """只快取成功結果:`_FetchFailed` 從這一層直接穿過去,不會被存下來。"""`
  同檔 `:804-807` 逐字：`    try:` / `        return _cached_usdtwd_series(days)` / `    except _FetchFailed as e:` / `        return _empty_usdtwd_df(), str(e)`
  呼叫鏈：`ui/helpers/portfolio_perf.py:37 _fxdf, _fxerr = fetch_usdtwd_frame(BACKTEST_FX_FETCH_DAYS)`
  → `services/hot_money_service.py:19-20 from repositories.hot_money_repository import fetch_usdtwd_series` / `return fetch_usdtwd_series(days)`
- **兩者不能同時為真**（10 分鐘內的重複互動走 `st.cache_data`，不會產生網路往返）。
- 📌 **出處照實登記**：`REASON_PERF`（`ui/views/page_04_portfolio.py:1104-1105`）在 `origin/main` 上
  逐字就是這麼寫的 ——「而這一頁每次互動都會整頁重跑 —— 接上去等於**每次互動一次網路往返**。」
  **規格是繼承方，不是發明方**（同上一輪 M19 的形狀）。
- 📌 **A 的另一半成立**：「一渲染就打一次匯率 API」屬實 ——
  `ui/helpers/portfolio_perf.py:34-37` 是**無條件**呼叫，沒有任何 gate。
  規格另外**漏掉了 `REASON_PERF` 原文的「還會落盤快取」**那半句（不影響結論，登記）。

### R8｜規格自訂「空狀態控制項一律引 `shared/ui_control_labels.py` SSOT」，而它自己引的 3 個常數都不在那個檔，還有 1 處直接手抄字面

- **A 說**（`spec/UI_SPEC.md:15` 逐字）：
  `⚠️ 空狀態指名控制項一律引 `shared/ui_control_labels.py` SSOT，**不手抄字面**。`
- **B 說**（實測，`shared/ui_control_labels.py` 全部常數只有 6 個）：
  `:30 MACRO_LOAD_BTN_FIRST` / `:31 MACRO_LOAD_BTN_AGAIN` / `:34 MACRO_FORCE_REFETCH_CHECKBOX` /
  `:37 SIDEBAR_GLOBAL_REFRESH_BTN` / `:40 DATA_GUARD_HOT_MONEY_BTN` / `:41 DATA_GUARD_RELOAD_MACRO_BTN`
  而規格引的另外三個常數**都住在別的檔**：
  `ui/views/page_04_portfolio.py:802 DIVCAL_GATE_LABEL`、
  `ui/views/page_05_settings.py:392 DIAG_GATE_LABEL`、
  `ui/views/page_05_settings.py:484 FETCH_DIAG_GATE_LABEL`
- **C 說**（`spec/UI_SPEC.md:117` 逐字，⑤-1 空狀態）：
  `- 空狀態：一檔都沒有 → 印「雲端還沒有累積」；未勾閘門 → 灰態「讀一次雲端累積狀態」`
  —— **直接寫字面，沒有引任何常數名**；該字串的 SSOT 是
  `ui/views/page_05_settings.py:411 NAV_GATE_LABEL: str = "讀一次雲端累積狀態"`
- **D 說**（同檔 `:62`，②-3 空狀態）：`- 空狀態：沒有持倉 → 空狀態取代整頁，指到保單管理`
  —— 同樣是**沒有引常數的中文指名**（新 ② 實際走 `where=where_to_find("pf_add")`，`page_02_health.py:1085`）
- **四者不能同時為真。**
- 📌 **上一輪 M13 打的就是這個病**（手抄「📡 載入總經資料」）。**M13 那一處修好了**（`MACRO_LOAD_BTN_AGAIN` 引對），
  **但同一條規則在新版另外 4 處沒有被自己套用。**

### R9｜規格自訂「四件缺一 → 改列排除清單」，而線上真的在渲染的一批區塊，兩份清單都沒有

- **A 說**（`spec/UI_SPEC.md:16` 逐字）：`四件缺一 → 改列排除清單。`
- **A2 說**（同檔 `:131` 逐字）：`**11 個區塊被排除**（甲 8 ＋ 乙 3），數字與項目對得起來。`
- **B 說**（實測，下列全部在**規格自己指定的那四個預覽格**上有渲染點，而在 21 塊與 11 條排除中**皆 0 命中**）：

  | 頁 | 區塊 | 渲染點（逐行印出） |
  |---|---|---|
  | ① | **🔎 詳細資料與說明**（層 4 整區） | `page_01_macro.py:1036 _DETAIL_HEADING: str = "🔎 詳細資料與說明"`；`:1969 st.markdown(f"### {_DETAIL_HEADING}")`；`:2045 _render_detail_zone()` |
  | ① | 其下 5 個具名小節 | `:1281 "##### 💵 美股流動性 × 熱錢 …"`／`:1365 "##### ④ ⚡ 短線風險雷達…"`／`:1408 "##### ⑤ 🌊 流動性壓力預警引擎…"`／`:1539 "##### ① 🎯 全域導航塔…"`／`:1550 "##### ② 🎯 拐點偵測中心…"` |
  | ① | 總經燈號全表（已拍板不做） | `:2046-2054 empty_state("總經燈號全表…—— 已拍板不做", …)` |
  | ② | **🧾 ① 結論** | `page_02_health.py:623 CONCLUSION_HEADING: str = "### 🧾 ① 結論 — 我手上這些，現在怎麼了"`；`:932 st.markdown(CONCLUSION_HEADING)`；`:1850 safe_section("結論", _render_conclusion)` |
  | ④ | **換股顧問** | `page_04_portfolio.py:1656 switch_block_label(), state=STATE_NOT_READY,`（由 `:2778 safe_section("動作卡", _render_action_cards)` 渲染）；理由常數 `:939 REASON_SWITCH` |
  | ⑤ | **🧾 ① 結論** | `page_05_settings.py:509 CONCLUSION_HEADING`；`:1721 safe_section("結論", _render_conclusion)` |
  | ⑤ | **🧾 ② 依據** | 同檔 `:513 EVIDENCE_HEADING: str = "### 🧾 ② 依據 — 逐項狀態"`；`:1723 st.markdown(EVIDENCE_HEADING)` |
  | ⑤ | **手動補資料 ／ 使用手冊 ／ 🗄️ 資料維護與通報** | 同檔 `:459 BACKFILL_GATE_LABEL` ／ `:472 MANUAL_GATE_LABEL` ／ `:462 MAINTAIN_GATE_LABEL`；區塊表在 `:27-30` |

  掃描指令：`grep -n "詳細區\|雷達\|流動性\|導航塔\|拐點\|燈號全表\|熱錢\|廣度\|SLOOS\|薩姆" spec/UI_SPEC.md`
  → **只有 2 行命中**（`:36` 的「拐點」是五桶桶名、`:40` 的「拐點」同）；負控 0。
- **兩者不能同時為真。**
- 📌 **並陳另一半，不選邊**：規格**沒有一句話宣稱自己窮舉了 `origin/main` 的所有區塊**。
  若把 `:16` 讀成「本規格**要寫的**那些區塊，四件缺一就改列排除」，則 A 成立、B 只是射程外；
  若照字面讀成「凡不寫的就要進排除清單」，則 B 成立。**兩種讀法一併登記。**

### R10｜甲的標題是「四件不齊」，但甲-8 的缺項不是四件中的任何一件

- **A 說**（`spec/UI_SPEC.md:133` 逐字）：`### 甲、四件不齊（8 個）`
- **A2 說**（同檔 `:16`）：四件 ＝ **來源／規則／空狀態／回答**（由 `:25-128` 每塊的四個小標定義）
- **B 說**（同檔 `:141` 逐字）：
  `8. 全站總經權重編輯 — 缺**寫入端**：`_macro_weights` 無 App 入口，只能手填`
  —— `寫入端` **不是**來源／規則／空狀態／回答之中的任何一個。
- **兩者不能同時為真。**
- 📌 **這是上一輪 M18 的同一種形狀**（當時是「需新建路徑」被放進「四件不齊」）。
  **甲-1~7 的缺項本組逐條對過，全部是四件之一**（缺規則 ×1、缺來源 ×5、四件全缺 ×1）✓，
  **只有甲-8 這一條。**

### R11｜①-4 標「沿用」，它的第二個來源在盤點表 0 命中，而規格對另外兩個同型的來源都有就地標示

- **A 說**（`spec/UI_SPEC.md:40` 逐字）：
  `- 來源：①-3 五桶 summary 的拐點／新聞桶＋session `_SK_RADAR`（**沿用**）`
- **A2 說**（同檔 `:10`）：`**沿用**＝盤點表判活、且…`
- **B 說**（實測）：`_SK_RADAR` 的值是 `ui/views/page_01_macro.py:211 _SK_RADAR: str = "v01_macro_risk_radar"`；
  `grep -c "v01_" inv/DB_INVENTORY.md` → **0**（正控：`grep -c "v03_research_batch_rows"` → **2**；負控 → 0）
  → **該鍵在盤點表 0 命中，無「狀態」也無「誰讀它」可對。**
- **C 說**（同檔 `:25` 與 `:85`）：規格對另外兩個同型情形**都有就地標示** ——
  ①-1 寫「實際鍵 `v01_macro_indicators`，**盤點表未列**」；④-2 寫「**盤點表 0 命中**」。
  **①-4 沒有。**
- **三者不能同時為真。**
- 📌 **附記（M16 的殘留，一併登記）**：`:14` 的但書
  「盤點表『未落地』量的是持久化、不是『到不到得了畫面』」**解掉了「到得了畫面」那一半**，
  **但沒有解「盤點表判活」那一半** —— `indicators`／`.metrics`／`.dividends`／`.moneydj_raw`／
  `data_registry` 在盤點表的**狀態欄值仍然是「未落地」，不是「活的」**
  （`inv/DB_INVENTORY.md:1214` 等）。**兩種讀法一併登記，不選邊。**

### R12｜§0 兩份行號清單並列，但第二份的順序不是 ②③④⑤

- **A 說**（`spec/UI_SPEC.md:5` 逐字）：
  `` `app.py:581-587` 開 9 格：5 正式＋4 預覽。① 正式格跑新頁（`:636`）；②③④⑤ 正式格跑舊版（`:648/662/673/688`），本規格寫預覽格（`:720/728/752/776`）。``
- **B 說**（逐行印出）：
  `:648 render_fund_grp_health_tab()`（②）／`:662 render_fund_research_tab()`（③）／
  `:673 render_portfolio_tab()`（④）／`:688 render_settings_diag_tab()`（⑤）→ **第一份確為 ②③④⑤ 依序**；
  `:720 render_holdings_health()`（② 的預覽）／`:728 render_settings_and_diagnostics()`（**⑤** 的預覽）／
  `:752 render_fund_research()`（**③** 的預覽）／`:776 render_asset_allocation()`（**④** 的預覽）
  → **第二份的順序是 ②⑤③④。**
- **兩者不能同時為真**（若讀者照第一份的 ②③④⑤ 順序去配第二份，`:728` 會被讀成 ③、`:752` 被讀成 ④、`:776` 被讀成 ⑤，**三個都錯**）。
- 📌 **並陳另一半**：`:5` 沒有明寫「依序對應」，第二份也可以讀成一個**集合**。**兩種讀法一併登記。**

### R13｜生產組自稱「新建 6」，檔內實測 5

- **A 說**（生產組自陳，經總管轉述）：`標籤 沿用 10／沿用（部分）8／新建 6`
- **B 說**（實測）：`grep -o "\*\*新建\*\*" spec/UI_SPEC.md | wc -l` → **6**，
  其中 **1 個是 `:12` 的定義句本身**（`- **新建**＝讀得回但無畫面消費者／需新建讀寫路徑`），
  **內文只有 5 個**：`:25`（①-1）／`:65`（③-1）／`:70`（③-2）／`:75`（③-3）／`:85`（④-2）。
  **同一把尺套在另外兩個標籤上，10 與 8 都對**（`沿用` 11−1＝10、`沿用（部分）` 9−1＝8）。
- **兩者不能同時為真。**
- 📌 **本條是對生產組自述的核對，不是規格檔內部的矛盾**（規格檔自己沒有寫任何標籤總數）。

### R14｜④-1 的區塊名與線框逐字常數不同字

- **A 說**（`spec/UI_SPEC.md:79` 逐字）：`### ④-1 核心／衛星現況與偏離`
- **B 說**（`ui/views/page_04_portfolio.py:589-590` 逐字）：
  `#: 線框 Tab 04 逐字（含全形斜線）。線框 chip：「全寬」「與 01 同源」。`
  `BLOCK_MIX: str = "核心 ／ 衛星現況 vs 建議"`
- **兩者不能同時為真**（同一個區塊兩個名字；且線上那個名字裡有「建議」兩個字，而規格 ④-1 的規則是 `⛔ **不出買賣動作、無一鍵再平衡鈕**`）。
- 📌 對照：規格其餘區塊名與常數**對得上**（④-3「保單與扣款標的」＝`BLOCK_POLICY`、
  ④-4「交易帳本」＝`BLOCK_LEDGER`、④-5「配息月曆」＝`BLOCK_DIVIDEND_CAL`、
  ④-6「穿透式持股／產業集中度」≈`BLOCK_CONCENTRATION`、④-7「總經曝險聯動」＝`BLOCK_MACRO_LINK`、
  ⑤-2「連線與金鑰」＝`BLOCK_KEYS`、⑤-3「資料來源健康度」＝`BLOCK_HEALTH`）。**只有 ④-1 這一個。**

---

## 4. 查了但沒問題的（只寫命中不寫清白，看不出這把尺有沒有往內用）

**21 塊全部查過**，下列**完全沒有找到問題**：

| 對象 | 查了什麼 | 結果 |
|---|---|---|
| **①-3 五桶證據表** | `EVIDENCE_COLUMNS` 是不是真的 5 欄、桶序是不是規格寫的那六列、新聞桶是不是恆 ⬜ | 全部屬實。`beginner_view.py:795` 五欄逐字；`:856` 桶序逐字＝「長期／綜合健康度／中期／短線／拐點／新聞」；上一輪已驗的 `news_items=None` 未變 ✓ |
| **①-4 ⚡③例外** | `summarize_radar()` 是否存在、是否真的只看 red/yellow、原始 dict 是否真的沒有那兩鍵 | 全部屬實。`page_01_macro.py:167` import；`:207-210` 逐字「存的是原始 dict，不再是 `summarize_radar()` 的摘要」；`:413` 逐字「分級**只看 `red` / `yellow` 兩個計數**」 ✓ |
| **①-5 🔍④可信度** | `is_proxy`／`prov.sources` 是否被讀、`source`／`fetched_at` 是否真的到不了 | 全部屬實。`:922 _v.get("is_proxy")`、`:923 _prov.get("sources")`；`:905` docstring 逐字「帶 `source=` 的只有 **1 個**（PMI），帶 `fetched_at=` 的 **0 個**」 ✓ |
| **②-1 吃本金三層** | 三層順序是否與 SSOT 一致 | 屬實。`services/health/dividend.py:317-350` 的 `precedence` 逐字同序 ✓ |
| **②-2 / ④-6 的形狀差異** | 兩邊真的是不同 shape 嗎 | **屬實，而且是本輪新增的正確發現**。② 走 `moneydj_raw.holdings.*`（`page_02_health.py:1311,1317-1319`），④ 走 `moneydj_raw.*`（`page_04_portfolio.py:2523-2524`） ✓ |
| **②-3 逐檔體檢表（裁示 5）** | 9 欄逐字、到不了的那 1 欄、「欄位不增不刪」 | 全部屬實（見 §2 (8) 的逐行輸出） ✓ |
| **③ 三塊的來源符號** | 5 個符號是否存在、是否真的被 `page_03` import（含別名檢查） | 全部存在且 import（`:281/286/305/327/2453`） ✓ |
| **④-3 保單與扣款標的** | `<保單分頁v2>` 那 6 欄在盤點表的狀態 | 6 欄全部「活的 ／ UI」（`inv:318-323`） ✓ |
| **④-5 配息月曆** | `DIVCAL_GATE_LABEL` 與 `build_month_calendar` 是否存在、「約五秒」有無出處 | 全部存在。`page_04_portfolio.py:802` 常數；`build_month_calendar` prod 5 檔；`REASON_DIVIDEND_CAL` 逐字「一組月配基金要算**約五秒**」 ✓ |
| **④-7 總經曝險聯動** | `summarize_core_satellite` 是否存在、「給的是股／債／現金不是核心／衛星」是否屬實 | 屬實。`page_01_macro.py:811` 逐字「（不是「核心／衛星」那種角色分配）」 ✓ |
| **⑤-1 NAV 累積狀態** | 別名 import 是否真的長那樣、三個欄位是否真的都是「活的 ／ UI」 | **逐字屬實**：`page_05_settings.py:323 coverage_status as fetch_nav_coverage`；盤點表 §1.6 三欄皆「活的 ／ UI」，**而且規格刻意沒有把同表另外 3 個「只寫不讀 ／ 內部」欄拖進來** ✓ |
| **⑤-2 的 7 個「到得了」** | 7 把金鑰在 ⑤ 或其委派對象是否真的有顯示面 | 7/7 有命中 ✓（值一律不列出） |
| **⑤-3 資料來源健康度** | `RELEASE_WINDOW_LABEL_PREFIX` 是否存在、是否真的是前綴比對而非中文比對 | 屬實。`ui/helpers/io/data_registry.py:65 RELEASE_WINDOW_LABEL_PREFIX = "release lag"` ✓ |
| **硬約束 1** | `load_holdings_overview` 是否真的 0 命中 | **0 命中**（含 tests）✓ |
| **硬約束 2** | `load_all_ledgers` 的消費端是不是真的只取 `len()` | **屬實**。唯一 production 呼叫 `policy_admin_section.py:825-826`，`_led_ct = len(_led_df)`；同檔 `:844` 自陳 `_sheet_stats` 全 repo 無讀取端 ✓ |
| **硬約束 3** | 「9 張分頁、4 本 Sheet」與「舊說明書只列 6 張」 | **逐字屬實**。`inv/DB_INVENTORY.md:1549` 逐字「說明書寫「6 種分頁、同一本 Sheet」，實際是「9 種分頁、4 本 Sheet」」 ✓ ⚠️ 射程差登記：盤點表 §1 標題寫「11 張表，分屬 4 本 Sheet ＋ 1 個外部發佈 CSV」——**9 是說明書那一節的射程，11 是盤點表的射程**，兩個數字量的不是同一件事 |
| **硬約束 4** | 級別字面不一致 | 上一輪已逐字驗過，新版一字未改 ✓ |
| **排除清單 丙 11 塊** | 11 塊是否真的都在上一版的排除清單裡 | **11/11 全部對得上** ✓（逐一回溯上一輪報告的 L98~L112） |
| **空狀態文字的來源** | 21 塊的空狀態引文有幾句在 `origin/main` 上已存在 | **5 句已存在**（「🔄 更新總經資料」`shared/ui_control_labels.py`、「這一輪一項指標都沒取到。」`page_01_macro.py`、「標的都還沒有成分股／產業配置」`page_04_portfolio.py`、「讀一次雲端累積狀態」＋「🔍 載入抓取診斷細節」＋「🔭 查一次資料來源狀態」`page_05_settings.py`），**其餘是規格新寫的**。⚠️ **本組不判定「規格新寫空狀態文字」算不算問題** —— 規格是設計文件不是抄本，但這個事實登記給客戶 |

---

## 5. 我沒查到什麼（一律寫「查不到」）

1. **線框 `docs/wireframes/ia-wireframe.html` 本身 —— 查不到（本組沒看）。**
   規格與 repo 多處自稱「線框逐字」，本組只比對到**自稱引用線框的常數**，
   **沒有回頭讀線框檔**。所有「線框逐字」的宣稱本組**未驗**。
2. **「本規格描述的是預覽版」這句對 ②③④⑤ 是否**完全**成立 —— 查不到。**
   本組驗到的是「`:720/728/752/776` 確實是預覽格、`:648/662/673/688` 確實是舊版」，
   但**沒有逐塊驗證規格寫的每一條規則描述的是預覽頁而不是舊頁的行為**。
3. **R6 的 `_breadth_card` 在真實 session 下會不會被渲染到 —— 查不到。**
   本組是靜態讀碼（`:1546` 在 `_render_detail_zone` 內），**沒有跑 AppTest**。
4. **R9 那批區塊「四件齊不齊」—— 查不到。**
   本組只驗到「它們有渲染點、而且兩份清單都沒有」，**沒有替它們判定四件齊不齊**。
5. **`data_cache/*.parquet` 的真實列內容 —— 查不到**（無 pandas／pyarrow，且不得 `pip install`）。
   PPI／銅價那兩支只有**位元組層**證據。
6. **盤點表 231 列的「誰讀它」判定本身對不對 —— 查不到。**
   本組**引用**盤點表的判定去對規格，**沒有回頭重驗盤點表自己的逐欄判定**。
7. **上一輪 M1~M20 的原始判定是否正確 —— 查不到**（只驗「新版有沒有修」）。
8. **「規格沒有第 15 條矛盾」—— 本組不宣稱。**
   上面 14 條是本節列出的那幾條指令看得到的；本方法的射程外項目見 §0。

---

## 6. 附：本報告用過的關鍵指令（可直接複跑）

```bash
# 環境（一律唯讀；origin/main 展開到自己的目錄，不碰共用工作樹）
cd /home/user/my-Fund-dashboard && git rev-parse origin/main        # 9cbf0377…
mkdir -p /home/user/r2main && git archive origin/main | tar -x -C /home/user/r2main
git show origin/main:app.py | md5sum ; md5sum /home/user/r2main/app.py   # 相同

# 尺寸（四個都跑）
wc -l spec/UI_SPEC.md ; wc -c spec/UI_SPEC.md
LC_ALL=C.UTF-8 wc -m spec/UI_SPEC.md ; wc -m spec/UI_SPEC.md
python3 -c "import io;s=io.open('spec/UI_SPEC.md',encoding='utf-8').read();print(len(s),len(s.encode()),len(s.splitlines()))"

# 行號（一律單獨印，不經 grep -v 數序號）
git show origin/main:app.py | awk 'NR==581'      # …依此類推 587/636/648/662/673/688/720/728/752/776

# 標籤計數（記得扣掉 L10~L12 的定義句）
grep -o "\*\*沿用\*\*" spec/UI_SPEC.md | wc -l
grep -o "\*\*沿用（部分）\*\*" spec/UI_SPEC.md | wc -l
grep -o "\*\*新建\*\*" spec/UI_SPEC.md | wc -l

# 負控（先確認它在三個目標檔都是 0，再拿去當負控；字串現編，不寫進文件）
grep -c "<負控串>" spec/UI_SPEC.md inv/DB_INVENTORY.md
grep -rc "<負控串>" --include=*.py /home/user/r2main | awk -F: '{s+=$2}END{print s}'
# ⚠️ 不要沿用上一輪稽核用過的那個負控串（本檔不列出）—— 它在 inv/DB_INVENTORY.md 命中 10 次

# R1 / R2 / R6 / R7 的關鍵一行
grep -n "transactions\[\]" inv/DB_INVENTORY.md | head -12
grep -n "portfolio_core_pct" /home/user/r2main/ui/views/page_04_portfolio.py
git show origin/main:ui/views/page_01_macro.py | awk 'NR==1633'
git show origin/main:repositories/hot_money_repository.py | awk 'NR==759'
```
