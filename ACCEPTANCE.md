# 驗收手冊：ui_v2 五頁

本檔寫給要驗收 `ui_v2/` 五頁的人：照哪幾條指令跑、跑出什麼數字才算基線、哪幾種跑法無效。

- 根目錄另有一份 `ACCEPTANCE_L1_L4.md`，那是舊文件，管的是別的東西，與本檔無關。
- 本檔的數字是實測值，每一個都標了量測日與 SHA。數字會漂移，要用請照第六節的規則現場重跑，不要直接引用本檔。

**本版量測條件**：量測日 **2026-09-25**；程式碼基底 `main` @ `9950e99`（PR #846 的合併提交）。
量測當下的工作樹比 `9950e99` 多兩處改動：新增本檔、重繪 `docs/v2/prototype/ui_prototype_alo.html`。
兩處都不是 `tests/ui_v2/` 或 `ui_v2/` 底下的檔，也沒有被 `tests/ui_v2/` 讀取。

---

## 一、建一個專用 venv

系統 python（`python3`）與系統 pytest（`/root/.local/bin/pytest`）都不能拿來跑 `tests/ui_v2/`，原因見第四節。
請另建一個 venv：

```bash
python3 -m venv <venv 路徑>
<venv 路徑>/bin/pip install -r requirements.txt streamlit==1.59.2 pytest playwright
```

瀏覽器不必另外下載，**不要**跑 `playwright install`。把環境變數 `UI_V2_CHROMIUM` 指向本機現成的 Chromium 執行檔：

```bash
export UI_V2_CHROMIUM=<chromium 執行檔路徑>
# 本機（2026-09-25）是 /opt/pw-browsers/chromium-1194/chrome-linux/chrome
```

**2026-09-25 實測**（基底 `9950e99`，Python 3.11.15）：上面兩行在一個全新的 venv 上執行，`pip` 結束碼 0。
裝到的版本是 streamlit 1.59.2、pytest 9.1.1、playwright 1.63.0。
（`requirements.txt` 對 streamlit 宣告的範圍是 `>=1.59.1,<1.60.0`，指令裡多寫的 `==1.59.2` 會把它釘在範圍內的這一版。）

以下指令都在 repo 根目錄執行，`<venv>/bin/python` 指上面建好的那個 venv 的 python。

---

## 二、基線

### 2.1 `tests/ui_v2/` 全跑

```bash
UI_V2_CHROMIUM=<chromium 執行檔路徑> <venv>/bin/python -m pytest tests/ui_v2/ -q -p no:cacheprovider -rs
```

~~**2026-09-25 實測（基底 `9950e99`）：`743 passed`，0 skipped，0 failed，耗時 588.61 秒。**~~
（本檔與 alo 線框改完之後又重跑一次，結果記在第 2.3 小節。）
→ ~~**2026-09-26 實測（基底 `2cfea07` ＋ 工作樹 mkt 正式入口改動，未 commit）：`803 passed`，0 skipped，0 failed，耗時 629.03 秒。**~~
變的原因：mkt 接真資料的準備工作新增 4 支測試檔共 60 條（見下方逐檔表）；既有 11 檔條數一條未變。
→ **2026-09-26 第二輪實測（基底 `12f8a9a` ＋ 工作樹稽核回修，未 commit）：`820 passed`，0 skipped，0 failed，耗時 629.55 秒。**
變的原因：`test_ui_v2_live_import_guard.py` 補擋六種動態 import 寫法，正控 13 條、負控 4 條，40 → 57；其餘各檔不變。

畫面測試是 `tests/ui_v2/` 裡標了 `slow` 的那一批，可以單獨列出來數。
CI 的 slow lane 跑的是全 repo 的 `python -m pytest -v -m "slow"`，不只 ui_v2：2026-09-25 實測（基底 `9950e99`）
`<venv>/bin/python -m pytest --collect-only -q -m slow -p no:cacheprovider` 回 ~~`155/9451 tests collected`~~，
其中 ~~127~~ 條屬於 `tests/ui_v2/`，另 28 條在 repo 其他測試。
→ 2026-09-26 實測（基底 `2cfea07` ＋ 工作樹）：~~`162/9617 tests collected`~~，其中 134 條屬於 `tests/ui_v2/`，另 28 條不變。
→ 2026-09-26 第二輪（基底 `12f8a9a` ＋ 工作樹）：`162/9635 tests collected`；slow 條數不變（新增的 18 條全是 fast）。
只數 ui_v2 的那一批：

```bash
<venv>/bin/python -m pytest tests/ui_v2/ --collect-only -q -m slow -p no:cacheprovider
```

~~**2026-09-25 實測（基底 `9950e99`）：`127/743 tests collected (616 deselected)`。**~~
→ ~~**2026-09-26 實測（基底 `2cfea07` ＋ 工作樹）：`134/803 tests collected (669 deselected)`。**~~
→ **2026-09-26 第二輪實測（基底 `12f8a9a` ＋ 工作樹）：`134/820 tests collected (686 deselected)`。**

各檔條數（~~2026-09-25 實測，基底 `9950e99`~~ → ~~2026-09-26 實測，基底 `2cfea07` ＋ 工作樹~~ → 2026-09-26 第二輪實測，基底 `12f8a9a` ＋ 工作樹；「收集」欄用 `--collect-only -q`，「slow」欄再加 `-m slow`；舊合計劃線保留在表下）：

| 檔 | 收集 | 其中 slow |
|---|---:|---:|
| `tests/ui_v2/test_alo_logic.py` | 126 | 0 |
| `tests/ui_v2/test_alo_page.py` | 21 | 21 |
| `tests/ui_v2/test_exp_logic.py` | 134 | 0 |
| `tests/ui_v2/test_exp_page.py` | 45 | 45 |
| `tests/ui_v2/test_hld_logic.py` | 144 | 0 |
| `tests/ui_v2/test_hld_page.py` | 24 | 24 |
| `tests/ui_v2/test_mkt_live_logic.py`（新增） | 8 | 0 |
| `tests/ui_v2/test_mkt_live_page.py`（新增） | 7 | 7 |
| `tests/ui_v2/test_mkt_logic.py` | 89 | 0 |
| `tests/ui_v2/test_mkt_page.py` | 9 | 9 |
| `tests/ui_v2/test_mkt_source.py`（新增） | 5 | 0 |
| `tests/ui_v2/test_set_logic.py` | 111 | 0 |
| `tests/ui_v2/test_set_page.py` | 25 | 25 |
| `tests/ui_v2/test_ui_v2_lane_guards.py` | 15 | 3 |
| `tests/ui_v2/test_ui_v2_live_import_guard.py`（新增） | ~~40~~ 57 | 0 |
| **合計** | **~~803~~ 820** | **134** |

~~合計 **743**／**127**（2026-09-25，基底 `9950e99`）~~ —— 變的原因同上：新增四檔 8＋7＋5＋40＝60 條，其中 slow 7 條。

`*_page.py` ~~五檔~~ 六檔（含新增的 `test_mkt_live_page.py`）整檔標 slow（檔內 `pytestmark = pytest.mark.slow`）；`test_ui_v2_lane_guards.py` 只有 3 條標 slow。

→ **2026-10-09 實測（S7，基底 `369628f`；依第六節第 1 條補登，上方 2026-09-26 的數字與逐檔表原樣保留）**：
2.1 指令的 `tests/ui_v2/` 部分 **`2208 passed, 2 skipped`**（與另三支根目錄測試檔同一次跑，見 12.8）；
`--collect-only -q` 為 `2210 tests collected`，加 `-m slow` 為 `225/2210 tests collected (1985 deselected)`。
變的原因：2026-09-26 之後 alo、set、hld 三頁的正式入口與接真資料各小步陸續加入測試檔（逐檔如下）。2 個 skipped 的說明見 12.8 第 1 點。

| 檔 | 收集 | 其中 slow |
|---|---:|---:|
| `tests/ui_v2/test_alo_live_logic.py` | 58 | 0 |
| `tests/ui_v2/test_alo_live_page.py` | 7 | 7 |
| `tests/ui_v2/test_alo_logic.py` | 126 | 0 |
| `tests/ui_v2/test_alo_page.py` | 21 | 21 |
| `tests/ui_v2/test_alo_source.py` | 12 | 0 |
| `tests/ui_v2/test_exp_logic.py` | 134 | 0 |
| `tests/ui_v2/test_exp_page.py` | 45 | 45 |
| `tests/ui_v2/test_hld_live_assemble.py` | 184 | 0 |
| `tests/ui_v2/test_hld_live_error_page.py` | 10 | 10 |
| `tests/ui_v2/test_hld_live_freshness.py` | 64 | 0 |
| `tests/ui_v2/test_hld_live_logic.py` | 680 | 0 |
| `tests/ui_v2/test_hld_live_page.py` | 56 | 56 |
| `tests/ui_v2/test_hld_live_settings.py` | 99 | 0 |
| `tests/ui_v2/test_hld_logic.py` | 208 | 0 |
| `tests/ui_v2/test_hld_page.py` | 27 | 27 |
| `tests/ui_v2/test_hld_read_failure_logic.py` | 55 | 0 |
| `tests/ui_v2/test_hld_source.py` | 21 | 4 |
| `tests/ui_v2/test_mkt_live_logic.py` | 8 | 0 |
| `tests/ui_v2/test_mkt_live_page.py` | 7 | 7 |
| `tests/ui_v2/test_mkt_logic.py` | 89 | 0 |
| `tests/ui_v2/test_mkt_page.py` | 9 | 9 |
| `tests/ui_v2/test_mkt_source.py` | 5 | 0 |
| `tests/ui_v2/test_set_live_logic.py` | 66 | 0 |
| `tests/ui_v2/test_set_live_page.py` | 11 | 11 |
| `tests/ui_v2/test_set_logic.py` | 111 | 0 |
| `tests/ui_v2/test_set_page.py` | 25 | 25 |
| `tests/ui_v2/test_ui_v2_lane_guards.py` | 15 | 3 |
| `tests/ui_v2/test_ui_v2_live_import_guard.py` | 57 | 0 |
| **合計** | **2210** | **225** |

~~⚠️ 第四節 4.3 末段與第六節第 1 條裡的「820」「134」本輪**沒有改字**：那幾處是 2026-09-26 的判斷基準，換成新數字屬改寫判斷句，留給下一次專門更新基線的那一輪；要用請照本段現場重跑。~~
→ **2026-10-09 同日更正（S7 獨立稽核 B 必修 2，有意識的更正，不是漏刪）**：第六節第 1 條明文要求基線變了就當場更新這幾個總數，上句的「留給下一輪」與它牴觸。4.3 末段與第六節第 1 條的「820」「134」已依本段實測就地改為 2208／2210 與 225（舊值劃線保留）；4.3「出現任何 skipped」那半句判準文字未改，2 個 skipped 是否違反待協作助手確認（見 4.3 末段補註與 12.8）。

### 2.2 文件守衛

```bash
<venv>/bin/python -m pytest tests/test_doc_counters.py tests/test_retired_exception_ids.py tests/test_constitution_file_refs.py -q -p no:cacheprovider
```

**2026-09-25 實測（基底 `9950e99`）：`91 passed`。** 逐檔：

| 檔 | 條數 |
|---|---:|
| `tests/test_doc_counters.py` | 66 |
| `tests/test_retired_exception_ids.py` | 7 |
| `tests/test_constitution_file_refs.py` | 18 |
| **合計** | **91** |

**新增本檔會不會改變守衛的結果或條數**：2026-09-25 在基底 `9950e99` 上，本檔加入前、加入後各跑一次上面那條指令，
兩次都是 `91 passed`，逐檔條數相同（→ 2026-10-09 在基底 `369628f` 上重跑，仍為 `91 passed`，66／7／18；見 12.8）。原因：`test_doc_counters.py` 只掃 `docs/v2/` 底下的 `*.md` 與 `prototype/*.html`，
另兩支只讀 `CLAUDE.md`、`EXCEPTIONS.md` 與 `*.py`，本檔（repo 根目錄的 `.md`）不在三支的讀取範圍內。

### 2.3 改完之後的重跑

本版加入本檔、重繪 alo 線框之後，用同一個 venv 把 2.1 與 2.2 各重跑一次（量測日 2026-09-25，基底 `9950e99`）：

- `tests/ui_v2/`：`743 passed`，0 skipped，0 failed。
- 文件守衛：`91 passed`（66／7／18）。

---

## 三、正控：確認這套測試真的會紅

一套永遠綠的測試等於沒有測試。驗收時請做一次正控：

1. 把一條斷言改反。例：`tests/ui_v2/test_mkt_logic.py` 第 28 行 `assert logic.STATE_OK == "ok"`
   （在 `test_四狀態的字面值就是SSOT卡片那四個` 裡），把 `==` 改成 `!=`：
   ```bash
   sed -i '28s/assert logic.STATE_OK == "ok"/assert logic.STATE_OK != "ok"/' tests/ui_v2/test_mkt_logic.py
   ```
2. 跑那一檔，預期轉紅：
   ```bash
   <venv>/bin/python -m pytest tests/ui_v2/test_mkt_logic.py -q -p no:cacheprovider
   ```
3. 改回來：
   ```bash
   sed -i '28s/assert logic.STATE_OK != "ok"/assert logic.STATE_OK == "ok"/' tests/ui_v2/test_mkt_logic.py
   git diff --stat -- tests/ui_v2/test_mkt_logic.py   # 應該沒有輸出
   ```
4. 再跑一次，確認回到綠燈。

**2026-09-25 實測（基底 `9950e99`）**：改反後 `1 failed, 88 passed`，結束碼 1，紅的是 `test_四狀態的字面值就是SSOT卡片那四個`；
改回後 `git diff --stat` 沒有輸出，該檔 md5 回到 `9fc93824921354b426d5703f64c4778c`（與改之前相同），重跑 `89 passed`。

行號會隨檔案修改而漂移。第 28 行對不上時，用內容找那一行，不要照抄行號。

---

## 四、無效的跑法

下面兩種跑法**不算驗收**。它們不是「比較慢的正確跑法」，是根本沒跑到畫面測試。

### 4.1 系統 pytest：`/root/.local/bin/pytest`

`/root/.local/bin/pytest` 是 uv tool 裝的 pytest（2026-09-25 實測為 9.0.2），
它自己的 python 裡**沒有** streamlit、playwright，連 `requests` 都沒有。

**2026-09-25 實測（基底 `9950e99`）**：

| 跑法 | 結束碼 | 收到幾條 | passed | skipped | error |
|---|---:|---:|---:|---:|---:|
| `/root/.local/bin/pytest tests/ui_v2/ -q -p no:cacheprovider -rs` | 4 | 0 | 0 | 0 | 載入 `tests/conftest.py` 時 `ImportError`（缺 `requests`），整批沒開跑 |
| 同上再加 `--noconftest` | 0 | 619（另有 5 檔在收集階段整檔跳過；pytest 回報 `collected 619 items / 5 skipped`） | 616 | 8 | 0 |

加了 `--noconftest` 的那一種最危險：**結束碼 0、畫面上一片綠點**，但 127 條畫面測試一條都沒跑到：

- 五個 `*_page.py` 在檔頭 `pytest.importorskip("streamlit", ...)` 就整檔跳過（即 `collected 619 items / 5 skipped` 裡的 5），一檔只算 1 個 skipped，
  檔內共 124 條（21＋45＋24＋9＋25）根本沒被收集；
- `test_ui_v2_lane_guards.py` 那 3 條 slow 顯示為 skipped（原因「本環境匯入不到 streamlit」）。

所以 8 個 skipped 背後其實是 127 條畫面測試沒跑。**畫面測試是被跳過，不是出錯**，而跳過不會讓結束碼變成非 0 ——
只看結束碼或只看綠點的人會把它讀成「全過」。

⚠️ 客戶先前的說法是「只跑 366 條、畫面測試被跳過」。本版在基底 `9950e99` 上實測，兩種跑法都不是 366：
不加 `--noconftest` 是 0 條（載入失敗），加了是收集 619 條、另有 5 檔整檔跳過，結果 616 條通過、8 個跳過。「畫面測試被跳過」這一半在加了 `--noconftest` 時成立。
366 這個數字的來源本版沒有查出來（可能是別的 SHA 或別的參數），**本檔只寫實測值**。

### 4.2 `python3 -m pytest`

**2026-09-25 實測**：`python3 -m pytest tests/ui_v2/ -q` 回 `No module named pytest`，結束碼 1，一條都沒跑。
系統 python 沒有裝 pytest（pytest 在 uv tool 的獨立環境裡，見 4.1）。

### 4.3 為什麼這些跑法無效

- 畫面測試要 streamlit（本 repo 釘 1.59.2）與 playwright；系統環境兩者都沒有。
- 找不到 streamlit 時，skip 有兩個來源（2026-09-25 實測，基底 `9950e99`）：(a) 五個 `*_page.py` 檔頭的模組層 `pytest.importorskip("streamlit", ...)`（`test_alo_page.py` 第 22 行、`test_exp_page.py` 第 25 行、`test_hld_page.py` 第 21 行、`test_mkt_page.py` 第 20 行、`test_set_page.py` 第 23 行），整檔跳過；(b) `test_ui_v2_lane_guards.py` 第 202 行的 `_need_streamlit()`（第 203 行呼叫同一個 `importorskip`），由兩個標 slow 的測試呼叫，其中一個參數化成兩條，合計 3 條 skip，就是 4.1 表格裡除了五個整檔以外的那 3 個 skipped。兩者都不分本機或 CI。
  `tests/ui_v2/_ui_v2_chromium.py` 只管 playwright 與瀏覽器：本機（環境變數 `CI` 不是 `true`）找不到時 **skip**，CI 上則 fail。
  skip 不會讓 pytest 的結束碼變成非 0，於是「沒跑」會被誤讀成「綠燈」。
- CI 上（`CI=true`）找不到瀏覽器會 fail、不 skip。但 CI 的 slow lane 設了 `continue-on-error: true`
  （`.github/workflows/pr-check.yml`），它紅了也不擋合併，要點進那一條 job 看結果才知道。

**判斷一次跑法有沒有效**：看輸出最後一行。基線是 ~~`743 passed`~~ → ~~`803 passed`~~ → ~~`820 passed`（2026-09-26 第二輪，基底 `12f8a9a` ＋ 工作樹；見 2.1）~~ → `2208 passed`（2026-10-09，基底 `369628f`；出處：2.1 的 2026-10-09 實測與 12.8）、0 skipped。出現任何 skipped，或總數不是 ~~743~~ ~~803~~ ~~820~~ 2210，就不是有效的驗收。
（2026-10-09 補註，上句判準文字未改：該次實跑另有 2 個 skipped，都在 `tests/ui_v2/test_hld_live_logic.py:128`，是測試內依參數排除空持倉情境（`[empty]`、`[emptyfail]` 兩組），不是缺 streamlit／playwright 的環境跳過；是否違反本條判準，待協作助手確認。見 12.8 第 1 點。）

---

## 五、五頁對照表

| 頁名 | 代號 | ui_v2 進入點 | HTML 原型檔 | 畫面測試檔 |
|---|---|---|---|---|
| 市場總覽 | MKT | `ui_v2/app_mkt.py` | `docs/v2/prototype/ui_prototype_today.html` | `tests/ui_v2/test_mkt_page.py` |
| 持倉體檢 | HLD | `ui_v2/app_hld.py` | `docs/v2/prototype/ui_prototype_hld.html` | `tests/ui_v2/test_hld_page.py` |
| 標的探索 | EXP | `ui_v2/app_exp.py` | `docs/v2/prototype/ui_prototype_exp.html` | `tests/ui_v2/test_exp_page.py` |
| 資產配置 | ALO | `ui_v2/app_alo.py` | `docs/v2/prototype/ui_prototype_alo.html` | `tests/ui_v2/test_alo_page.py` |
| 設定與診斷 | SET | `ui_v2/app_set.py` | `docs/v2/prototype/ui_prototype_set.html` | `tests/ui_v2/test_set_page.py` |

- ⚠️ **市場總覽的原型檔是 `ui_prototype_today.html`，不是 `ui_prototype_mkt.html`**。後者不存在
  （2026-09-25 在基底 `9950e99` 上看 `docs/v2/prototype/` 只有表中五個 `.html`）。`ui_prototype_today.html` 的頁面標題是「今天頁線框原型」。
- 市場總覽頁的程式與測試註解引用的線框是文字版 `docs/v2/47_fund_wireframe_mkt.md`，不是那個 HTML；兩者都在，驗收時兩份都可以對。
- 各頁的規格以 `docs/v2/44_fund_ui_ssot.md` 為準；原型與 44 不一致時照 44。
- 各頁啟動：`<venv>/bin/streamlit run ui_v2/app_<代號小寫>.py`。進入點檔案的第 1 行是編碼宣告，第 2 行是 docstring 的開頭，寫的就是這一條指令（2026-09-25 實測，基底 `9950e99`）。
- 每頁的邏輯測試是同目錄的 `test_<代號小寫>_logic.py`，第二節的逐檔表裡有條數。
- 配息頻率對照表：見 `docs/v2/49_data_integration_plan.md` §6.1 Q6 下的「配息頻率對照表（客戶 2026-09-26 定案）」。左欄寫法為推測、未實測（repo 內沒有 MoneyDJ「配息頻率」欄的真實樣本），每季回查一次並補表。

---

## 六、維護規則

1. **每次跑完，基線有變就當場更新本檔。** 包括 ~~743、127~~ ~~803~~ ~~820、134~~ 2210、225、91 三個總數（2026-09-26 更新，理由見 2.1；2026-10-09 依 2.1 當日實測改為 2210、225，基底 `369628f`，舊值劃線保留）、第 2.1 與 2.2 兩張逐檔表、第四節的實測表。
2. **更新時帶上量測日與 SHA。** 寫「量測日 YYYY-MM-DD，基底 `<SHA>`」；不要寫「目前」「現在」「HEAD」這種會移動的字。
3. 數字變少時，先查是不是有人把測試刪了或標成 skip，再更新；不要只改數字讓它對上。
4. 被取代的舊數字不要直接刪掉，劃線保留並寫一句為什麼變（本 repo 的慣例）。
5. 更新完再跑一次本節下面的兩條檢查，確認本檔沒有帶進禁用詞或識別碼。

### 本檔自身的兩條檢查

禁用詞共 8 個。為了不讓本檔自己命中，詞表用 Unicode 跳脫碼寫，不寫字面：

```bash
python3 -c "import sys;W=['\u4e00\u9375','\u6700\u4f73','\u63a8\u85a6','\u6700\u9069','\u8cb7\u9032','\u8ce3\u51fa','\u52a0\u78bc','\u6e1b\u78bc'];t=open(sys.argv[1],encoding='utf-8').read();print(sum(t.count(w) for w in W))" ACCEPTANCE.md
```

正控（確認這條指令會命中）：拿同一份詞表在你自己的暫存目錄（下面寫成 `<暫存目錄>`，不要用共用的 `/tmp`）產生一個含禁用詞的檔，用同一條指令掃它，做完刪掉：

```bash
python3 -c "W=['\u4e00\u9375','\u6700\u4f73','\u63a8\u85a6','\u6700\u9069','\u8cb7\u9032','\u8ce3\u51fa','\u52a0\u78bc','\u6e1b\u78bc'];open('<暫存目錄>/acc_ctl.txt','w',encoding='utf-8').write('x'.join(W))"
python3 -c "import sys;W=['\u4e00\u9375','\u6700\u4f73','\u63a8\u85a6','\u6700\u9069','\u8cb7\u9032','\u8ce3\u51fa','\u52a0\u78bc','\u6e1b\u78bc'];t=open(sys.argv[1],encoding='utf-8').read();print(sum(t.count(w) for w in W))" <暫存目錄>/acc_ctl.txt
rm <暫存目錄>/acc_ctl.txt
```

識別碼：

```bash
grep -cE 'session_[0-9A-Za-z]{16,}|claude\.ai/code/session' ACCEPTANCE.md
grep -ciE 'O[p]us|S[o]nnet|H[a]iku' ACCEPTANCE.md   # 模型名，不分大小寫
```

正控：把一個假的識別碼（`session_` 後接 16 個以上英數字）與一個全小寫的模型名寫進 `<暫存目錄>` 裡的暫存檔，用同樣兩條指令掃它，兩條都應該命中；做完刪掉。

**2026-09-25 實測（本版定稿後，稽核回修後重跑）**：禁用詞 0；禁用詞正控 8；識別碼 0、模型名（不分大小寫）0；兩條正控皆命中；暫存檔已刪。

**2026-09-28 重跑（alo 讀表第 15 輪，基底 `60ff5cd`）**：禁用詞 **1**；識別碼 0、模型名（不分大小寫）0；
三條正控皆命中（正控字串現編、不寫進本檔，理由見下）；暫存檔已刪。

⚠️ **那個 1 是子字串誤判，不是真的帶進推銷用語 —— 扣掉這一處之後為 0。**
- **命中的詞**：禁用詞表的第 1 個（本檔一律以 Unicode 跳脫碼指稱，不寫字面）。
- **出處**：第 8.4 節開頭那一句引自 `44` 4.1 的欄位術語（`\u696d\u52d9\u552f\u4e00\u9375`；
  依本節體例以跳脫碼指稱，字面只留在 8.4 那一句本身）。
  那個禁用詞是它的**子字串**，而該句是**逐字引 `44` 4.1 的欄位術語**，不是推銷用語。
- **為什麼不改掉那個詞**：`docs/v2/44_fund_ui_ssot.md` 已凍結，且那個術語本來就是正確用語；
  為了閃避一條子字串檢查而改寫規格原詞，是把檢查修成綠燈、不是把文件修對。
- **為什麼不改那條指令**：它是**本檔自身的手動檢查**，不是 CI 守衛（2026-09-28 實測：
  `tests/` 與 `.github/` 沒有任何守衛在掃本檔的禁用詞）。改指令會讓它與第三節「按鈕四禁詞」那套
  原始碼層級的掃描分岔。
- **repo 內已有同型前例，體例照它**：`tests/ui_v2/test_alo_logic.py` 在原始碼層級掃描時，
  就是把同一個詞從詞表裡拿掉並就地寫明理由（理由寫的正是 `44` 4.1 那個術語），而**按鈕標籤那一層照掃不誤**。
- ⛔ **下一次跑這條檢查時，三個條件要同時成立才視同 0**：
  **(1) 數量恰為 1；(2) 命中處只有 8.4 那一句；(3) 命中的詞是詞表第 1 個**
  （`W[0]`，本節體例以跳脫碼指稱：`\u4e00\u9375`；**不要把字面寫進本檔，否則這一段自己就會再命中一次**）。
  **任一條不成立 → 是真的帶進禁用詞，要修文件。**
  ⚠️ **第 (3) 條是 2026-09-28 第 16 輪補的（稽核 A 指出的窄縫）**：原規則只綁「數量」與「位置」，
  萬一哪天 8.4 那一句裡出現**別的**禁用詞，數量仍是 1、位置仍是 8.4，**照字面會被誤放行**。
  **查命中詞的做法**（不印字面，只印它是詞表第幾個）：
  ```bash
  python3 -c "import sys;W=['\u4e00\u9375','\u6700\u4f73','\u63a8\u85a6','\u6700\u9069','\u8cb7\u9032','\u8ce3\u51fa','\u52a0\u78bc','\u6e1b\u78bc'];t=open(sys.argv[1],encoding='utf-8').read();print([(i,t.count(w)) for i,w in enumerate(W) if t.count(w)])" ACCEPTANCE.md
  ```
  **2026-09-28 第 16 輪實測（基底 `b8a590e` ＋ 本輪改動）**：輸出 `[(0, 1)]` —— 只有詞表第 1 個、命中 1 次，三條件齊備。

---

## 七、失敗訊息遮蔽規則（客戶 2026-09-26 裁示 Q13）

**量測日 2026-09-26，基底 `main` @ `7f564aa`。** 本節是**實作時的驗收規則**，不是動工授權（`CLAUDE.md` §-1）。
出處：`docs/v2/49_data_integration_plan.md` §4.9（風險）與 §6.1 Q13（裁示與附帶條件）。

### 7.1 為什麼寫在本檔、不寫進 `44`

`docs/v2/44_fund_ui_ssot.md` 已凍結，不得加附註。`44` 的 `fetch_log` 表（§4.5）規定 `message`「存來源回傳的原始字串，不換成安撫語句，也不截斷」，
而原始字串可能帶 API 金鑰或代理帳密（見 7.6 的實測）。客戶裁示：**遮蔽規則的落點改為實作時寫進本檔**。
本節就是那個落點；`44` 一個字都沒有動。

讀法：本節只在「原文」這一條上加一道**替換**，其餘仍照 `44`：不改寫、不換成安撫語句、不截斷。

### 7.2 遮蔽對象：已知 secrets 的值

只遮**值**，不遮鍵名。下表是本組在 `7f564aa` 上查到的**已知讀點**（分類敘述，不是窮舉；查法與沒查到的形態見 7.7）。
「路徑＋符號」指讀取該值的位置；**本表不寫任何值**。

**甲、App（Streamlit）執行期會讀到的憑證 —— 一律遮蔽**

| 鍵名 | 遮哪些值 | 讀取位置（路徑＋符號） |
|---|---|---|
| `FRED_API_KEY` | 整個值 | `app.py::_load_keys`（鏡射到環境變數）；`ui/views/page_01_macro.py::render_market_overview` 讀環境變數（2026-09-26 以 AST 走訪確認：該檔讀 `FRED_API_KEY` 字面值的函式是 `render_market_overview`；同檔 `_load_everything` 讀的是 `FINMIND_TOKEN`）；`mcp_server/tools_macro.py::build_macro_snapshot` |
| `FINMIND_TOKEN` | 整個值 | `ui/helpers/macro/ndc.py::_fetch_ndc_score`；`ui/tab1_macro.py::_render_top_card_grid`；`ui/tab1_macro_longterm.py::render_long_term_section`；`ui/tab5_data_guard.py::render_data_guard_tab`；`ui/views/page_01_macro.py::_load_everything` |
| `ALPHAVANTAGE_API_KEY` | 整個值 | `repositories/fund/sources.py::_src_alphavantage_nav` |
| `GEMINI_API_KEY`、`GEMINI_API_KEYS`（逗號分隔多把）、`GEMINI_API_KEY_1`～`GEMINI_API_KEY_10` | 每一把各自的值（`GEMINI_API_KEYS` 拆開後逐把） | `app.py::_load_keys`；`services/ai_service.py::get_gemini_keys` |
| `ANTHROPIC_API_KEY`、`OPENAI_API_KEY` | 整個值 | `app.py::_load_keys`；`infra/llm.py::call_llm` |
| `PROXY_URL` | 網址裡的**帳號**與**密碼**兩段（`http://帳號:密碼@主機:埠` 的 userinfo）；主機與埠不遮 | `infra/proxy.py::get_proxy_config` |
| `[proxy]` 區段 | `username`、`password` 兩個值；`endpoint` 不遮 | `infra/proxy.py::get_proxy_config`（`PROXY_URL` 不存在時的舊格式） |
| `[google_service_account]`（TOML 表格或 JSON 字串兩種寫法都收） | `private_key`、`private_key_id` | `repositories/pool_repository.py::_sa_present`；`services/nav_history_gs.py::status`、`services/nav_history_gs.py::_sa_to_dict`；`services/macro/weights_store.py::_gs_enabled`；`ui/helpers/io/oauth_state.py` 模組層的 `_gsa_secret`；`repositories/policy/_helpers.py::get_gspread_client` |
| `[google_oauth]` 區段，以及同形的 `st.session_state["custom_oauth_cfg"]` | `client_secret` | `ui/helpers/io/oauth_state.py::_resolve_oauth_cfg` |
| OAuth 執行期權杖（不在 secrets 檔，登入後才有） | `access_token`、`refresh_token`、`id_token` | 產生：`infra/oauth.py::exchange_code_for_tokens`、`infra/oauth.py::refresh_access_token`；存放：`st.session_state["gsheet_tokens"]`（`ui/helpers/io/oauth_state.py` 讀寫） |
| `SETTINGS_SHEET_ID`（設定與取數紀錄試算表的 ID；**2026-09-26 新增列**；決策者：總管自決，客戶核准） | 整個值 | `repositories/settings_sheet_repository.py::settings_sheet_id`；遮蔽鍵表 `services/v2_tables/masking.py::MASKED_WHOLE_VALUE_KEYS`。理由：`docs/v2/50_settings_sheet_design.md` 第 2 節定案這一本的 ID 只放 secret、不寫進 repo（repo 公開，寫出 ID 等於公開客戶會被寫入的那本試算表位址）；它與下方丙類其餘五個試算表 ID 的處置刻意不同 |

**乙、推播與發佈用的憑證 —— 一律遮蔽**（~~只在排程腳本或推播用到的憑證~~：分類名不成立，`ui/tab_manage.py::_sec_notify` 在 App 執行期就會讀 LINE 憑證，見下表第一列；2026-09-26 稽核指出，本組以 AST 確認後更正）

| 鍵名 | 讀取位置（路徑＋符號） |
|---|---|
| `LINE_CHANNEL_TOKEN`、`LINE_CHANNEL_ACCESS_TOKEN` | **App 執行期**：`ui/tab_manage.py::_sec_notify`（經 `infra/line_push.py::_resolve`，判斷 LINE 是否已設定）；推播時：`infra/line_push.py::_post_messages`（經同檔 `_resolve`） |
| `GITHUB_TOKEN` | `infra/asset_publish.py::publish_asset`（經同檔 `_resolve`） |

**乙之二、只在排程腳本讀的憑證 —— 同樣遮蔽（它們若進入同一支遮蔽函式的輸入，也要被遮）**

| 鍵名 | 讀取位置（路徑＋符號） |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON`、`GSPREAD_SA_JSON`（服務帳戶 JSON 字串；遮其中 `private_key`、`private_key_id`） | `scripts/fetch_nav_cache.py::_codes_from_sheet` |
| `PROXY_URL`（環境變數版） | `scripts/fetch_nav_cache.py` 模組層的 `_PROXY_URL` |

**丙、讀到了、但本規則不遮的值（處置在本檔定案，不另送客戶）**

| 鍵名 | 處置 |
|---|---|
| `POLICY_SHEET_ID`、`NAV_SHEET_ID`、`POOL_SHEET_ID`、`macro_weights_sheet_id`、`SHEET_ID` | ~~**建議：不遮，理由：試算表 ID 不是憑證，沒有被分享的人拿到 ID 也打不開；而且 `49` §4.1 要求設定頁顯示「目前讀的是哪一本」，遮掉就無法除錯。**~~ → **2026-09-26 更正（有意識的更正，不是漏刪；決策者：總管自決，客戶核准）：不遮的範圍只到本列這五個鍵名，不是「試算表 ID 一律不遮」。** `SETTINGS_SHEET_ID` 列在甲表遮蔽（見甲表）。本列五個鍵照舊不遮，理由照舊：它們不是憑證，沒有被分享的人拿到 ID 也打不開；`49` §4.1 要求設定頁顯示「目前讀的是哪一本」，遮掉就無法除錯。**舊句的用意仍然成立**（試算表 ID 本身不是憑證）；**被權衡掉的是它的射程** —— 舊句寫成「試算表 ID」這個類別，而 `SETTINGS_SHEET_ID` 那一本依 `50` 第 2 節刻意不公開，與本列五本的處置不同。⚠️ 本列只涵蓋這五個鍵名；日後新增的試算表 ID 鍵，不得援引本列預設為不遮，要逐鍵決定 |
| `google_service_account.client_email`、`client_id`；`google_oauth.client_id`、`redirect_uri` | **建議：不遮，理由：這些不是憑證；「權限不足」時使用者要知道該把試算表分享給哪一個服務帳戶信箱，遮掉 `client_email` 就給不出這個指引。** |
| `WATCH_CSV_URL` | **不在 Q13 射程內，不送客戶。** 查證：`git grep -n WATCH_CSV_URL 7f564aa -- '*.py' ':!tests/**'` 的命中逐行判讀後，讀值的是 `scripts/watchlist_push.py::main` 與 `scripts/weekly_switch_notify.py::_read_watchlist`（`scripts/dividend_calendar_notify.py` 經匯入後者使用；值由 `.github/workflows/` 的工作流程注入環境變數）；`ui/tab_manage.py` 的命中只在註解與說明字串裡，不讀值（正控：同一條指令命中 `scripts/weekly_switch_notify.py` 讀環境變數的那一行）。App 執行期不讀它，它也不經過 `fetch_log` 與 ui_v2 的畫面 —— Q13 管的是寫進 `fetch_log` 與上畫面的失敗訊息，碰不到它。⚠️ 若日後 App 或 ui_v2 開始讀它，性質接近憑證（公開 CSV 連結，知道網址就讀得到），屆時改列甲類遮蔽。 |
| `LINE_USER_ID`、`GITHUB_REPOSITORY`、`NAV_GATE0_MODE`、`NAV_CODES`、`US_STOCK_IDS`、`FUND_DB`、`GOOGLE_APPLICATION_CREDENTIALS`（檔案路徑）、`CHROMIUM_EXECUTABLE_PATH`、`GITHUB_STEP_SUMMARY` | 不遮：設定值或路徑，不是可單獨拿去呼叫服務的憑證。 |

~~丙表原版把試算表 ID、`client_email`、`WATCH_CSV_URL` 三項寫成「列為客戶裁示事項」~~ → 2026-09-26 稽核後改為本檔直接定案（決策者：AI 總管；有意識的更正，不是漏刪）。理由：三項都不是 Q13 裁示範圍內的新業務規則 —— 前兩項是「不遮會不會讓憑證外洩」的技術判斷，答案是不會；第三項根本不經過 Q13 管的兩個寫出點。⚠️ 2026-09-26 補註：這裡的「試算表 ID」指丙表列出的五個鍵名，不含 `SETTINGS_SHEET_ID`（該鍵要遮；決策者：總管自決，客戶核准。見甲表）。

### 7.3 替換記號與替換規則

- **固定記號**：`‹已遮蔽›`（前後是單書名號 U+2039、U+203A，中間三個字）。一個秘密值被換成**一個**記號，不論原值多長。
- **其餘字元逐字保留**：不刪、不改寫、不截斷、不調整空白與換行。遮蔽前後，只有秘密值那幾段字元不同。
- **每一次出現都換**：同一個值在訊息裡出現幾次，就換幾次。
- **要一併遮的寫法**（同一個值在錯誤訊息裡常以別的形態出現）：
  1. 原值；
  2. 網址百分比編碼後的值（`urllib.parse.quote(值, safe="")` 與 `quote_plus(值)` 兩種）——金鑰進了查詢字串，例外訊息印的是編碼後的網址；
  3. ~~服務帳戶 `private_key`：原值（含真實換行），以及換行被跳脫成反斜線加 n 的寫法（JSON 字串內的形態）。~~
     → **2026-10-09 更正（有意識的更正，不是漏刪；出處：遮蔽缺口可達性實測＋分支 `claude/fund-dashboard-v2-maskrepr-3b9no8`）**：換行跳脫形態**不再只限 `private_key`**，凡秘密值皆遮；另加「`\n`、`\r`、`\t` 一起跳脫」的寫法（`\r\n` 結尾的私鑰會出現這種形態）。只跳脫換行的舊寫法照遮。**舊句的用意仍然成立**（私鑰在 JSON 字串裡就是這個形態）；**被權衡掉的是它的射程**：任何含換行、CR、tab 的值都會以跳脫形態出現。
  4. **（2026-10-09 新增，出處同上）Python repr 形態**：`repr(值)` 去掉頭尾引號的內容，以及「強制以單引號定界」的 repr 內容（值只含 `'` 時 Python 改用雙引號、不跳脫 `'`；別處以單引號定界時寫成 `\'`）。理由：值含反斜線、引號、`\t` `\r` `\n`、不可印字元（如 `\x7f`）時，經 `repr(值)`、list／tuple 字串化（`str([值])`）、多參數例外（`str(Exception(值, 1))`）帶進訊息就與原值不同。實證：`repositories/settings_sheet_repository.py::_check_header`、`repositories/policy_supplement_repository.py::_check_header` 的訊息 `試算表 {header}` 是 list repr，整句遮蔽前會漏出。
  5. **（2026-10-09 新增，出處同上）JSON 字串內容**：`json.dumps(值)` 去掉頭尾引號（預設 `ensure_ascii=True`：反斜線與 `"` 加跳脫，`\x7f` 與非 ASCII 寫成 `\uXXXX`）。
  - **仍遮不到的已知形態（2026-10-09 登記；本組推導、非窮舉、未經第二組驗證）**：repr 再套一層 repr（反斜線再加倍）；`json.dumps(值, ensure_ascii=False)`（值含非 ASCII 時與上列第 5 點不同）；~~強制以雙引號定界的 repr（值含 `"` 又含 `\x7f` 或非 ASCII 時，第 5 點也對不上）~~（**2026-10-09 同日劃掉，有意識的更正，不是漏刪**：Python 的 repr 只在字串含 `'` 且**不含** `"` 時才用雙引號定界；值含 `"`，任何包含它的字串也含 `"`，於是一律單引號定界、`"` 不跳脫，已由第 4 點蓋住。本組實跑 2 萬組隨機「前綴＋值＋後綴」，雙引號定界 0 次。**這一項經 Python repr 不可達**；其他語言或函式庫自行以雙引號跳脫的寫法不在此推論內）；`ascii(值)` 與 f-string `!a`（含其 list 形態）：值含 U+0080～U+00FF 字元時寫成 `\xNN`、含 BMP 以外字元時寫成 `\UXXXXXXXX`，第 4、5 點都對不上（本組 2026-10-09 實跑確認；其他 BMP 非 ASCII 字元因與第 5 點同為 `\uXXXX` 而碰巧遮得到。紅隊以替身在四頁重現，grep 未找到正式路徑產生此形態）；`requote_uri` 等只部分百分比編碼的網址；網址解析失敗、或以別的切法才出現的帳密片段；bytes 的 repr（`b'…'`）；秘密值被截斷或折行；base64 與 HTTP Basic 授權標頭。
  - **非字串型秘密值不遮（2026-10-09 登記；紅隊讀碼指出，本組實跑確認）**：`services/v2_tables/masking.py::secret_values` 只收 `str`。TOML 裡寫成數值的秘密（例如 `FRED_API_KEY = 12345678901234`、`[proxy] password = 98765432101`）經 `tomllib` 讀成 `int`，`secret_values` 回空清單，訊息裡的那串數字原樣保留。本輪只登記，不改程式。
- **由長到短替換**：多個秘密值互為子字串時，先換長的，避免短的先換掉一半、長的就對不上。
- **空值不參與**：鍵存在但值為空字串的，不拿去替換（否則會在每個字元之間插記號）。
- **比對大小寫敏感、完全相同才換**：不做模糊比對，不猜「看起來像金鑰的字串」。沒有列在 7.2 的值，本規則不處理。
- **遮蔽只在寫出點做一次**：寫進 `fetch_log.message` 之前、送上畫面之前。畫面與 `fetch_log` 用**同一份**遮蔽後的字串，不各自遮。

### 7.4 「已遮蔽」要同時進 `fetch_log` 與畫面

- **`fetch_log`**：`message` 欄存**遮蔽後**的字串，記號 `‹已遮蔽›` 本身就留在字串裡。這樣不必在 `44` 的七個欄位之外另加一欄，也保住 `44` §4.5 `fetch_log` 的表判準：把 `message` 與 `SET-2` 畫面上顯示的字串逐字比對，兩者相同。
- **畫面**：`SET-2`（來源健康卡，顯示各層級最近一次的 `message`）與 `SET-6`（取數紀錄，顯示 `fetch_log` 全欄，含 `message`）兩處都顯示同一份字串（含記號），並在訊息**旁邊**（不是訊息字串裡面）加一行註記「已遮蔽憑證」。只有字串裡確實含記號時才加；沒有遮任何東西時不加。
- 沒有秘密值出現的訊息，遮蔽前後逐字相同，也不出現記號與註記。

**7.4-a　延伸到市場總覽（MKT）的正式入口**（2026-09-26；決策者：客戶（核准正式入口文字線框草稿第 2 處）／AI 總管（延伸射程））

上面兩點原本只點名 `SET-2`、`SET-6`。本輪起，同一條規則也套用到市場總覽正式入口 `ui_v2/app_mkt_live.py` 的下列區塊（示範入口 `ui_v2/app_mkt.py` 不套用，它沒有真的取數）：

| 區塊 | 顯示位置 | 註記位置 |
|---|---|---|
| `MKT-1` 風險情緒卡 | 主值 `系統錯誤` 那一格：`⛔ 取數失敗：<遮蔽後的訊息>` | 同一格的**下一行**，灰色小字「已遮蔽憑證」 |
| `MKT-2` 景氣位置卡 | 同上 | 同上 |
| `MKT-3` 資金與匯率卡 | 同上 | 同上 |

- `MKT-0`（結論燈只寫卡名與狀態字面值）、`MKT-4`～`MKT-7` 不顯示失敗訊息原文，所以不在射程內。
- 寫出點：`ui_v2/mkt/source.py::load_live` 在交給頁面之前遮一次（秘密值在這一層從 `st.secrets`、環境變數與登入權杖讀出）；遮蔽函式是 `services/v2_tables/masking.py::mask_message`（L2，不讀秘密、不 import streamlit）。
- `fetch_log` 尚未落地（`49` Q12），所以 MKT 這一條目前只有「畫面」一個寫出點；落地之後，`fetch_log.message` 必須與畫面用同一份遮蔽後的字串。

**7.4-a 續　射程補含持倉體檢（HLD）的正式入口**（2026-10-09 登記，基底 `main` @ `51ae661`；決策者：AI 總管（S6b-4 派工，延伸射程）；出處：交接本〈登記待辦〉「hld S6b 開工前盤點」第 5 條）

上面只寫到 MKT。持倉體檢正式入口 `ui_v2/app_hld_live.py`（PR #905 合併後上線）同樣把失敗訊息原文印上畫面，本條起一併套用 7.3 的遮蔽規則（示範入口 `ui_v2/app_hld.py` 不套用，它沒有真的取數）。

- **畫面上印原文的地方**：`ui_v2/hld/logic.py` 以「⛔ 取數失敗：<訊息原文>」模板寫出的各處（表層級、逐檔、設定讀取失敗），以及入口層例外的整頁錯誤畫面（`ui_v2/hld/page.py::_render_live_error`）。
- **寫出點（本組 2026-10-09 讀碼核對）**：
  - `ui_v2/hld/source.py::load_live`：持倉讀表失敗（`holding_error`）、設定讀表失敗（`settings_error`）在本層以 `alo_holdings.masker(秘密值)` 遮過再交出；
  - `ui_v2/hld/live.py::assemble_live_load`：逐檔淨值取數失敗（放進 `fund_errors["nav"]` 的那幾筆）與部分分頁讀不到（`skipped_tabs` → `errors["holding"]`）由本函式以同一個 `mask` 遮；
  - `ui_v2/hld/source.py::mask_error`：整頁錯誤畫面的例外型別名與訊息，經 `page.render(mask_error=...)` 遮過才上畫面。
  - 秘密值來源與 alo 相同（`masking.secret_values`：`st.secrets`、環境變數、`gsheet_tokens`、`custom_oauth_cfg`）。
- ⚠️ **與 7.4 第二點的差距，據實登記（本輪不改）**：7.4 要求訊息含記號時在**旁邊**加一行「已遮蔽憑證」；hld 正式版目前**沒有**這一行（`ui_v2/hld/` 底下 0 處出現該字串，本組 2026-10-09 實查）。加這一行屬新增畫面元素，依客戶 2026-10-09 裁示（S6b-4 只做不改畫面文案的收尾）本輪不做，待另送客戶。
- 驗收（現有）：`tests/ui_v2/test_hld_source.py` 的 `test_持倉與設定讀取失敗_各進對應錯誤_訊息經遮蔽`、`test_淨值取數失敗訊息經遮蔽`、`test_mask_error遮掉秘密值`、`test_正式入口_讀取拋例外_畫錯誤畫面_秘密值經遮蔽_不是示範模式`、`test_秘密值來源_st_secrets以外三處也收進遮蔽`；`tests/ui_v2/test_hld_live_assemble.py::test_T4a_某檔取數失敗_fund_errors放遮蔽後的原文_端到端全頁印出同一句且不含原文`。
- `fetch_log` 尚未落地，hld 這一條同樣只有「畫面」一個寫出點。

### 7.5 驗收：實作時必須有的測試

以下每一條都是**實作時**要寫出來、且要在 CI 跑的測試。它們**不打外部網路**：需要真實例外字串的，一律連本機迴路位址（`127.0.0.1`）。

| # | 測試 | 輸入 | 通過條件 |
|---|---|---|---|
| M1 | 含金鑰的網址，連線失敗的例外字串 | 對本機一個沒有在聽的埠發請求，查詢字串帶一把假金鑰（當作 `FRED_API_KEY` 的值），取 `str(例外)` | 遮蔽後不含假金鑰；含 `‹已遮蔽›`；把記號換回假金鑰後與原字串逐字相同 |
| M2 | 407 代理驗證失敗 | 在本機起一個一律回 407 的假代理，`PROXY_URL` 帶假帳號與假密碼，經它發 HTTPS 請求（查詢字串帶假金鑰），取 `str(例外)` | 遮蔽後不含假密碼、假帳號、假金鑰；其餘字元逐字保留 |
| M3 | 代理帳密直接出現在訊息裡 | 一段含完整 `PROXY_URL` 的字串（含帳密的原值與百分比編碼兩種） | 帳號、密碼兩段都被換掉；主機與埠保留 |
| M4 | 金鑰以百分比編碼出現 | 假金鑰含 `+`、`/`、`=` 等字元，以 `quote` 與 `quote_plus` 各編一次後放進訊息 | 兩種編碼形態都被換掉 |
| M5 | 服務帳戶私鑰 | 訊息含假 `private_key`（真實換行版與反斜線加 n 版）與假 `private_key_id` | 三者都被換掉 |
| M6 | OAuth 敏感欄 | 訊息含假 `client_secret`、`access_token`、`refresh_token` | 都被換掉；`client_id`、`redirect_uri` 保留（依 7.2 丙） |
| M7 | 沒有秘密值的訊息 | 一段不含任何 7.2 值的錯誤字串（含全形字、換行、很長） | 輸出與輸入逐字相同；不出現記號；畫面不出現「已遮蔽憑證」 |
| M8 | 空值 | 某鍵存在但值為空字串 | 輸出與輸入逐字相同 |
| M9 | 互為子字串 | 兩把假金鑰，一把是另一把的前綴 | 長的整段被換成一個記號，不殘留尾巴 |
| M10 | 多次出現 | 同一把假金鑰在訊息裡出現三次 | 三次都被換掉 |
| M11 | `fetch_log` 與畫面逐字相同 | 以 M1 的例外走完「寫 `fetch_log` → `SET-2` 顯示」與「寫 `fetch_log` → `SET-6` 顯示」兩條路 | 兩處畫面上的訊息字串都與 `fetch_log.message` 逐字相同，且都含 `‹已遮蔽›`；兩處訊息旁都出現「已遮蔽憑證」 |
| M12 | 突變（正控） | 把遮蔽函式換成「原樣回傳」 | M1～M6、M9～M11 必須轉紅。沒有轉紅就代表測試沒有守到東西 |

**7.5-a　實作狀態（2026-09-26，工作樹，基底 `2cfea07`）**

| # | 在哪裡 | 狀態 |
|---|---|---|
| M1～M10 | `tests/test_v2_tables_masking.py` | 已寫、fast lane。M1、M2 只連 `127.0.0.1`（M2 是本機起的回 407 假代理） |
| M11 | `tests/ui_v2/test_mkt_live_page.py::test_M11_MKT版_畫面上的訊息與遮蔽後字串逐字相同_下一行加註` | **只做了 MKT 版**（畫面字串與遮蔽後字串逐字相同、下一行有「已遮蔽憑證」）。`fetch_log` → `SET-2`／`SET-6` 那兩條路要等 `fetch_log` 落地（`49` Q12）才做得了 → **2026-10-09 補（S7；原句在寫下當時為真，未改）**：`369628f` 上已有 SET 版 `tests/ui_v2/test_set_live_page.py::test_M11_SET版_取數失敗訊息與fetch_log逐字相同_SET2與SET6下一行加註`，該次實跑通過（見 12.8）。它是在哪一個 PR 加入的，本組未查 |
| M12 | 突變腳本：把 `mask_message` 換成原樣回傳 | 2026-09-26 已跑：`test_v2_tables_masking.py`、`test_mkt_source.py`、`test_mkt_live_page.py` 三檔合計 11 條轉紅（含 M1～M6、M9、M10、MKT 版 M11）；不是常駐測試 |
| 鍵名表比對範本 | `tests/test_v2_tables_masking.py::test_兩張範本的每個鍵都落在遮或不遮的表裡` | 已寫 |

- 假金鑰、假帳密一律在測試裡**現場隨機產生**，不寫死成固定字串，也不寫進任何文件（`CLAUDE.md` §-2.A 第 8 款）。
- M1、M2 要放行本機迴路位址；`49` §4.7 第 3 點的網路阻斷 fixture 同樣要放行 loopback。

### 7.6 實測：金鑰確實會出現在例外字串裡

**2026-09-26 實測**（基底 `7f564aa`；requests 2.34.2、urllib3 2.8.0，驗收用 venv；只連本機迴路位址，不打外部網路）：

| 情境 | 例外型別 | 假金鑰在 `str(例外)` 裡 | 假代理密碼在 `str(例外)` 裡 |
|---|---|---|---|
| 對本機沒在聽的埠發請求，查詢字串帶假金鑰 | `ConnectionError` | **在**（例外字串含 `...?api_key=<假金鑰>`） | 不適用 |
| 經回 407 的本機假代理發 HTTPS 請求 | `ProxyError` | **在** | **不在** |
| 經同一個假代理發 HTTP 請求 | 沒有例外，回應狀態 407 | 回應物件的 `url` 屬性含假金鑰 | 不適用 |

- 所以 `49` §4.9 原本「依套件行為推論、沒有實測」的那一句，**金鑰那一半已經實測成立**：`infra/proxy.py::fetch_url` 在其他錯誤分支直接印例外物件，而例外字串帶完整查詢字串。
- **代理密碼那一半在這一版套件、這一種情境下不成立**，但這**不是**不遮的理由：別的套件版本、別的錯誤路徑（例如自己組字串把代理網址印出來）仍可能帶出來，所以 7.2 照樣遮。
- 另一個已知的外洩形態，本組讀程式碼看到、**沒有實測**：`infra/oauth.py::exchange_code_for_tokens` 在回應缺 `access_token` 時把整個回應內容放進例外訊息。

### 7.7 7.2 是怎麼查的、查不到什麼

在 `7f564aa` 上用兩條指令列出 `*.py`（不含 `tests/`）裡的讀點，再逐一讀上下文判定：

```bash
git grep -nE 'st\.secrets|os\.environ|os\.getenv|get_secret\(|_secret\(' 7f564aa -- '*.py' ':!tests/**'
git grep -nE '_resolve\("[A-Z_]+"' 7f564aa -- '*.py'
```

- 第一條在 `7f564aa` 上命中 142 行、39 檔；**正控**：`infra/proxy.py::get_proxy_config` 讀 `PROXY_URL` 的那幾行在命中裡。
- 第二條補第一條抓不到的間接讀法：`LINE_*` 與 `GITHUB_TOKEN` 是經 `_resolve` 讀的，第一條的字表不含它們的鍵名。第二條在 `7f564aa` 上命中 7 行，其中 3 行在 `ui/tab_manage.py`（它以別名 `_line_resolve` 匯入，字串照樣含 `_resolve("`）。⚠️ 初版把這 3 行漏歸類，於是乙表寫成「只在排程腳本或推播用到」；**指令當時就掃到了，錯在逐行判讀**（2026-09-26 稽核指出，已更正）。
- 另有兩類是**讀程式碼補上、不是指令掃出來的**：`GEMINI_API_KEY_1`～`_10`（鍵名由 f-string 組出）、`[proxy]` 區段的 `username`／`password`（以下標讀取）。
- **查不到的形態**（誠實揭露）：鍵名由變數動態組出、經別的包裝函式轉手、或在 `tests/` 以外但不是 `.py` 的檔（例如工作流程 YAML 注入的環境變數）讀取的，這兩條指令都掃不到。**「7.2 就是全部」這句話本組沒有查證，也不宣稱。**
- 實作時遮蔽函式的輸入**不應**是一份寫死的鍵名表，而應在執行期從 secrets 與環境變數讀出這些鍵的**值**；鍵名表本身要有一條測試比對 `secrets.toml.example` 與 `.streamlit/secrets.toml.example` 的鍵，範本多了新鍵而表沒跟上就紅。

### 7.8 已知限制：秘密值很短時會連帶遮到一般字元（2026-09-26 稽核登記；只登記，不改程式）

- 7.3 規定「完全相同才換」，所以遮蔽函式（`services/v2_tables/masking.py::mask_message`）把訊息裡**每一段**與秘密值相同的字元都換成記號，不看它在訊息裡是不是真的是那把金鑰。
- 秘密值很短時（例如代理帳號只有幾個字、或剛好是常見英文字），訊息裡碰巧出現同樣的一般字元也會被換掉 —— 錯誤類型、主機名、狀態碼裡的片段可能因此變成 `‹已遮蔽›`，除錯資訊變少。
- 方向上是**多遮不漏遮**（不會外洩），代價是可讀性。本輪不改程式；若要處理（例如只在查詢字串、網址 userinfo 等位置比對，或對過短的值另訂規則），屬規則變更，要先改本節 7.3 再改程式。

⚠️ **本節由文件組單組產出，未經第二組獨立複驗**（`CLAUDE.md` §-2 規則 6）。7.6 的實測是本組自己跑的；7.2 的分類是本組讀程式碼判定的。

---

## 八、資產配置頁讀表：推定值與已知差異（R1 客戶裁示；U9 客戶裁示；R2 總管裁定；總管推導；規格組讀法；另有總管暫定一項）

**量測日 2026-09-27，基底 `main` @ `2ac1394`**（8.1～8.3）；
**8.4／8.5 為 2026-09-28 新增，基底 `41ca5de`**；**8.4／8.5 的回修為 2026-09-28，基底 `60ff5cd`**；
**8.1 末段與 8.3 的更正為 2026-10-09（S6b-4），基底 `51ae661`**
（依第六節第 2 條：更新時帶上量測日與 SHA）。
本節是**讀表程式的驗收規則**，不是動工授權（`CLAUDE.md` §-1）。
程式：`repositories/policy_supplement_repository.py`（L1）、`services/v2_tables/alo_holdings.py`（L2）。
寫在本檔而不寫進 `44` 的理由同 7.1：`docs/v2/44_fund_ui_ssot.md` 已凍結，不得加附註。

**出處逐項分開標註**（交接本＝`origin/docs/handover-latest` @ `885b71a` 的 `docs/handover_2026_09_26_latest.md`，行號在該 SHA 上核對過）：

| 項目 | 性質 | 出處 |
|---|---|---|
| 最後核對日換成當日 12:00 台灣時間 | **客戶裁示**（R1＝B，2026-09-27） | 交接本 :38；scratchpad 規格 `alo_sheet_tabs_spec.md` 6.2 節 R1（**該規格檔不在 repo 內（總管工作區草稿），repo 內無法查證**） |
| DIRECT 列照讀；這三欄不寫入；警示字樣「DIRECT 列暫不支援，該筆不計入配置」 | **客戶裁示**（U9，2026-09-27） | 交接本 :129～:134（U9 原文只寫「這三欄」，沒有列出欄名） |
| 「這三欄」所指為 `policy` 的 `issuer`、`ccy`、`opened_on`（`44` 4.4 沒有給 `DIRECT` 值的三欄） | **規格組讀法**，`docs/v2/49_data_integration_plan.md` 附錄第 9e 輪由總管更正（第 9d 輪曾誤讀為 `_持倉補充` 的三欄） | scratchpad 規格 `alo_sheet_tabs_spec.md` 2.2 節（**該規格檔不在 repo 內（總管工作區草稿），repo 內無法查證**）；`49` 附錄第 9e 輪（`origin/main` @ `2ac1394`，**這一半在 repo 內查得到**） |
| `44` HLD-5「直接持有」與 ALO 的 DIRECT 列不是同一件事、不可混用 | **客戶裁示紀錄**（U9） | 交接本 :133 |
| 「DIRECT 列」兩種都算：`_保單資料` 的 DIRECT 列＋保單分頁 `policy_id` 為 DIRECT 的持倉列 | **R2 總管裁定**（交接本） | 交接本 :42 |
| DIRECT 不進 `ALO-2` 的分子與分母 | **R2 總管裁定** | 交接本 :42（原文「不計入 ALO-2」） |
| 判斷 DIRECT 大小寫敏感：只有去掉前後空白後恰為 `DIRECT` 才算，`direct`、`Direct` 當一般保單編號 | **第 2 輪總管裁定 8**（與 R2 分開） | alo 讀表第 2 輪總管派工單（不在交接本）；測試 `test_裁定8_` 開頭 |
| `44` 4.4「`DIRECT` 這一列固定存在」那條表判準暫停驗收 | **總管依 R2 推導**（規格 6.2 R2 建議方案 (1)，**該規格檔不在 repo 內（總管工作區草稿），repo 內無法查證**；規格原文用詞屬本檔禁用詞，此處改寫） | 交接本 :42 的 R2 原文只寫「把『DIRECT 列暫不開放、不計入 ALO-2』這兩處與 44 的差異寫進 ACCEPTANCE」，**沒有逐字寫「暫停驗收」**；「暫停驗收」出自 scratchpad 規格 `alo_sheet_tabs_spec.md` 6.2 R2 建議方案 (1)（**該規格檔不在 repo 內（總管工作區草稿），repo 內無法查證**；規格原文用詞屬本檔禁用詞，此處改寫）；:95 另登記「U9 與 44 第 4.4 節衝突，待 44 解凍時處理」 |
| DIRECT 持倉不產生 `holding` 列 | **總管暫定**（2026-09-27 第 2 輪，**不是客戶裁示**） | 見 8.3 |

⚠️ **2026-09-28 第 14 輪補（稽核 A 建議 1）：上表凡寫「scratchpad 規格 `alo_sheet_tabs_spec.md`」的格子，
`repo` 內都查不到那份檔案**（它是總管工作區草稿，不在任何分支上）。體例沿用
`docs/v2/49_data_integration_plan.md` 既有寫法（「規格目前不在 repo 內（總管工作區草稿）」「repo 內無法查證」）。
**在 repo 內查得到的出處是**：`49` 本身、`44`、交接本分支 `docs/handover-latest`。
⚠️ **同輪順帶查證一則、結論與派工單相反，據實寫明**：派工單轉述稽核 C 稱「實際引到的節是 0.2、2.1、3.1、6.2，
**沒有 2.2**（`git grep -c '規格 2\.2'` → 0）」。**本組實測：2.2 有被引到，至少三處**
（`ACCEPTANCE.md` 本表、`repositories/policy_supplement_repository.py` 分頁名那一行「規格 2.1、2.2」、
`tests/test_policy_supplement_repository.py` 檔頭「2.1、2.2 節」）。
`git grep -c '規格 2\.2'` 之所以回 0，是因為原文寫的是「規格 2.1、2.2」與
「規格 \`alo_sheet_tabs_spec.md\` 2.2 節」，**那條字串結構上掃不到它們** ——
同 `CLAUDE.md` §-1.5.1c 判定 2「字表選錯，掃再多次都沒用」。**本輪不依該轉述改動節號。**

### 8.1 R1：最後核對日換算時刻為推定（12:00 台灣時間），非真實對帳時刻

- `44` 4.1 規定 `holding.last_synced_at` 是**時間**（世界協調時間），而客戶在 `_持倉補充` 手填的是**日期**（U5「核對日」）。
- 讀表時把 `最後核對日` 換成**當日 12:00 台灣時間**，存 `YYYY-MM-DDT04:00:00Z`（例：填 `2001-02-03` → 存 `2001-02-03T04:00:00Z`）。
- **最後核對日換算時刻為推定（12:00 台灣時間），非真實對帳時刻。** 客戶實際核對的時刻不知道，`04:00Z` 是規則補上的。`44` 的 `holding` 沒有推估旗標欄，所以登記在這裡。
- 只收 `YYYY-MM-DD`；其他格式（`2001/02/03`、`2001-2-3`、帶時間、帶時區、沒有時區的時間、不存在的日期、全形數字）一律拒收，該列不收並寫出分頁名、列號與原文，不猜。U6（時間欄的時區規則）在 R1 下沒有套用對象，只保留為裁示紀錄。
- 不以讀取時間冒充（`49` 2.6）。
- 驗收：`tests/test_v2_tables_alo_holdings.py` 以 `test_R1_` 開頭的測試（換算邊界：月底、年底、閏年 2/29、非閏年 2/29、帶時間）；`tests/test_policy_supplement_repository.py` 以 `test_R1_` 開頭的測試（格式錯的列不收）。
- 畫面顯示：`ui_v2/hld/logic.py::_build_hld5` 以 `last_synced_at` 的前 10 個字顯示「最後對帳」，換算後與客戶填的日期相同。12:00 這個時刻不會出現在畫面上，但它仍是推定值。
  → **2026-10-09 補（S6b-4；原句未改，它對示範入口 `ui_v2/app_hld.py` 仍然為真，對正式版不完整）**：正式入口 `ui_v2/app_hld_live.py`（PR #905 合併後上線）另經 `ui_v2/hld/live.py::_relabel_sync_field`（客戶 2026-10-02 裁示 4-C）——欄名改為「最後核對日（只記日期）」，值由 `live.sync_date` 換算成**台灣日期**（帶時區的時間先轉 UTC+8 再取日期，不是截前 10 個字）；值不合格或晚於台灣的今天 → 那一格進 `系統錯誤`，整頁照常。R1 換算出的 `T04:00:00Z` 在台灣仍是同一天，所以畫面上的日期仍與客戶填的相同，12:00 仍是推定值。驗收：`tests/ui_v2/test_hld_live_logic.py::test_正式模式_HLD5欄名改為最後核對日只記日期_值只有日期`、`test_最後核對日_合格值換成台灣日期`、`test_最後核對日一格不合格_整頁不崩_那一格進系統錯誤`。

### 8.2 R2：U9 與 `44` 4.4／ALO-2 的差異

| | `44` 的規定 | 本輪讀表（U9 客戶裁示＋R2 總管裁定＋總管推導） |
|---|---|---|
| `44` 4.4 保留列 | 「`DIRECT` 這一列固定存在」，表判準「新環境初始化後，表上存在 `policy_id` 為 `DIRECT` 的那一列」 | 不產生 `DIRECT` 的 `policy` 列（U9「這三欄」不寫入（所指為規格組讀法，見出處表）⇒ 依 `44` 第四節開頭「不可空欄取不到值，該筆不寫入」，這一列寫不進去）。**該條表判準暫停驗收（總管依 R2 推導；規格 6.2 R2 建議方案 (1)；規格原文用詞屬本檔禁用詞，此處改寫）**；`44` 原文不動 |
| `44` ALO-2 | 規則沒有排除 DIRECT | DIRECT 名下的持倉不進 `ALO-2` 的分子與分母（R2 總管裁定；U9 原文「該筆不計入配置」） |
| 讀到 DIRECT 列時 | — | 照讀，逐筆警示「DIRECT 列暫不支援，該筆不計入配置」（U9 客戶裁示，逐字） |
| 哪些列算 DIRECT 列 | — | 兩種都算：`_保單資料` 保單編號為 `DIRECT` 的列、保單分頁 `policy_id` 為 `DIRECT` 的持倉列（R2 總管裁定）。另，大小寫敏感（第 2 輪總管裁定 8，不屬 R2）：只有去掉前後空白後恰為 `DIRECT` 才算 |

- **另一件事，不可混用**（出自交接本 :133 的 U9 裁示紀錄）：`44` HLD-5 的「`policy_id` 為 `DIRECT` → 保單欄位顯示『直接持有』」是 HLD-5 保單欄的顯示方式，與上表 ALO 的 DIRECT 列不是同一件事。讀表程式不產生任何「直接持有」字樣。HLD-5 那條判準照舊由 `tests/ui_v2/test_hld_logic.py::test_DIRECT保單欄位顯示直接持有而不是空白` 以示範假資料驗。
- 驗收：`tests/test_v2_tables_alo_holdings.py` 以 `test_U9_`、`test_裁定8_` 開頭的測試（含「非 `DIRECT` 列不產生警示、且輸出不含『直接持有』字樣」與「小寫 `direct` 不算」的反例）。

### 8.3 總管暫定：DIRECT 持倉不產生 `holding` 列

- **客戶只裁了「不計入配置」（U9）**，沒有裁「不產生 `holding` 列」。本輪讀表程式不產生 DIRECT 的 `holding` 列，是**總管暫定**（2026-09-27 第 2 輪）。
- ~~暫定理由：`policy` 的 DIRECT 列不產生（8.2），若仍產生 `holding` 列，該列的 `policy_id` 會懸空參照。~~
  → **2026-09-28 第 14 輪就地更正（有意識的更正，不是漏刪；決策者：AI 總管；由稽核 A 建議 5 指出，本組實測覆核）。**
  **舊理由為什麼不成立**：懸空參照**不是 DIRECT 獨有的**。本組實測（非 DIRECT 的 `P1`，`_保單資料` 缺該保單列）
  → `holding` 照樣產生（`policy_id` 為 `P1`）、`policy` 為空、`missing_profile=['P1']`、`skipped_holdings=[]`
  —— **同樣懸空，而且照樣產生 `holding` 列**。用一個對一般保單也成立、卻只拿來擋 DIRECT 的理由，
  支撐不了「只有 DIRECT 不產生 `holding` 列」這個暫定。
  ⚠️ 那個行為**本身不違反 `49`**：`49` §2.6 該列寫明「掛在那些保單下的持倉如何顯示，由 `logic.py` 既有規則決定」。
- **現行暫定理由（DIRECT 獨有、一般保單不會發生）**：`44` HLD-5 的空狀態規則是
  「`policy_id` 為 `DIRECT` → 保單欄位顯示『直接持有』」（`ui_v2/hld/logic.py::TEXT_DIRECT_HOLD`）。
  DIRECT 的 `holding` 列一旦產生，HLD-5 就會把它顯示成「直接持有」——
  那正是 8.2 末段「**另一件事，不可混用**」（U9 裁示紀錄，交接本 :133）禁止的混用，
  也是 `services/v2_tables/alo_holdings.py` 檔頭自訂的界線（「本檔不產生任何『直接持有』字樣」）。
  一般保單缺 `_保單資料` 列時**不會**觸發這條顯示規則，所以這個理由分得出 DIRECT 與一般保單。
- ⚠️ **這仍然是總管暫定，不是客戶裁示** —— 換的是理由，不是決定；客戶只裁了「不計入配置」（U9）。
- ~~連帶後果：hld 頁看不到 DIRECT 持倉。這件事掛在已登記的未定題「hld 頁遇到 DIRECT 持倉時怎麼顯示」（交接本 :94）之下，**待 hld 接真資料時送客戶裁示**。~~
  → **2026-10-09 更正（S6b-4；狀態更新，不是漏刪，上句在寫下時為真）**：客戶 2026-10-02 已裁 **3-B (ii)**（出處：`docs/wireframes/draft_hld_live.html` §G；交接本第 5 節〈已裁示（2026-10-02）〉）——正式版的 DIRECT 持倉**另外列出、不計入體檢**：仍不產生 `holding` 列、不進任何計算；HLD-5 卡尾一行「⚠ DIRECT 列暫不支援，該筆不計入體檢（N 筆）」加逐筆位置，有持倉時收合摘要尾端加「 · DIRECT N 筆未列入」（`DIRECT_SUMMARY_SUFFIX`），持倉全空時 HLD-5 摘要整句換成「DIRECT N 筆未列入」（`DIRECT_SUMMARY_ONLY`）；N 只數保單分頁的 DIRECT 持倉列（`ui_v2/hld/live.py::direct_holding_rows`、`_apply_direct`）。示範入口不經過這一段。驗收：`tests/ui_v2/test_hld_live_logic.py` 以 `test_DIRECT_` 開頭的測試。本節「不產生 `holding` 列」仍是總管暫定，客戶這次裁的是 hld 畫面怎麼呈現，不是讀表要不要產生該列。
- 驗收：~~`tests/test_v2_tables_alo_holdings.py::test_裁定4_總管暫定_DIRECT持倉不產生holding列_且不懸空參照`~~ → **`tests/test_v2_tables_alo_holdings.py::test_裁定4_總管暫定_DIRECT持倉不產生holding列`**（2026-10-09 更正，不是漏刪：劃掉的名字在該檔不存在；本組以 `grep -n 'def test_裁定4' tests/test_v2_tables_alo_holdings.py` 在 `51ae661` 實查，只有新名字與另外兩條 `test_裁定4_` 開頭的測試；出處：交接本〈登記待辦〉「hld S6b 開工前盤點」第 5 條）。

### 8.4 `44` 4.1「同鍵分多列時顯示時才加總」：本輪**沒有做**，接 UI 的那一輪要補

（2026-09-28 第 14 輪登記；稽核 A 建議 4。**登記 ≠ 動工授權**，`CLAUDE.md` §-1。）

- **`44` 4.1 的現行規定（客戶 2026-09-21 裁示，已改過一次）**：業務唯一鍵是（`policy_id`, `fund_code`），
  （⚠️ 本句那個**欄位術語**會讓第六節那條禁用詞檢查命中一次 —— **子字串誤判**，說明見第六節「本檔自身的兩條檢查」）
  「**來源端分多次投入而登記成多列時，儀表板在顯示時把金額與單位數加總成一列，不在畫面上列出第二列**」。
  表判準：「在 Sheets 端把同一張保單同一檔基金登記成兩列，儀表板讀進來之後畫面上該組合為 1 列
  且 `cost_twd` 顯示為兩列金額之和」。
- **本輪的實際行為**：L2 `services/v2_tables/alo_holdings.py` **同鍵分多列時各自一列**
  （`holding_id` 以出現序號區分），**不加總**。這一點只寫在該檔的 docstring
  （「同鍵分多列時各自一列（`44` 4.1：顯示時才加總）」），**本節先前沒有登記**。
- **本輪為什麼不算違規**：`44` 4.1 的義務落在「**顯示時**」，而本輪只做到 L1 讀取與 L2 轉換，
  **沒有接任何 UI**，那個表判準的受測對象（畫面）還不存在。
- ⚠️ **下一輪接 UI 的人必須知道這裡欠一個加總** —— 在本節登記之前，**只有讀 L2 docstring 的人才會知道**：
  兩支測試與本檔（本節寫下之前）都沒有提到這件事。
  ⚠️ **這句話刻意不寫成「`git grep 加總` → N 命中」**：本節自己就在談它，
  **一寫下計數，存檔的當下就被自己推翻**（`CLAUDE.md` §-2.A 第 8 款、§-1.5.1c 判定 2 的同一個病）。
- **接 UI 時要補的**：(a) 顯示層依（`policy_id`, `fund_code`）合併，`cost_twd` 與 `units_shares` 加總；
  (b) 補一條對得上 `44` 4.1 表判準的測試；(c) 一併決定合併後 `holding_id`、`opened_on`、
  `last_synced_at`、`bucket` 取哪一列的值 —— **那是尚未裁示的部分，`44` 4.1 沒有寫**。

### 8.5 讀取量：`read_estimate` 是軟性提醒，「每分鐘 60 次」不是驗收標準

（2026-09-28 第 14 輪；客戶裁示三-1 ＋ 紅隊 B-M1。）

- **實測關係（2026-09-28）**：沒有任何分頁讀取失敗時，**每分鐘上游讀取數 ＝ 保單分頁數 ＋ 5**
  （5 ＝ 補充分頁 `open_by_key`／`worksheets`／`values_batch_get` 各 1 ＋ 保單分頁清單
  `open_by_key`／`worksheets` 各 1）。量測點 n ∈ {50, 52, 55, 56, 58, 60, 70, 100}
  → 55／57／60／61／63／65／75／105，逐點吻合。**與畫面重跑頻率無關**（三種快取都是 60 秒）。
  有分頁讀取失敗時更高（重試與探測另計）。
- **⚠️ 那個「每使用者每專案每分鐘 60 次」未經一手查證**：2026-09-28 再查仍讀不到一手官方頁面
  （本環境的 egress proxy 擋掉 `developers.google.com`），數值取自搜尋摘要。
  **客戶 2026-09-28 明令：不得當硬門檻、不得當驗收標準。**
- **實作的做法**：`load_policy_holding_rows()["read_estimate"]`（`load_alo_tables` 原樣轉交）
  交出分頁數、預估每分鐘讀取數、參考配額值與 `reference_verified: False`。
  **不 raise、不拒讀** —— 分頁數再多也照讀。
- **驗收**：`tests/test_policy_supplement_repository.py::test_第14輪BM1_*`（參數化 n ∈ {50,55,56,60,70}，
  斷言的是**關係**不是門檻）、`tests/test_v2_tables_alo_holdings.py::test_第14輪BM1_整條路_*`。
- ⚠️ **前 13 輪的讀取量守衛把分頁數寫死在 50／51**，所以「客戶多開幾張保單分頁就超過那個參考值」
  這件事**在 CI 上完全看不見**。第 14 輪補的就是這一軸。
- 📌 **登記、本輪未做（一）**：`tests/test_policy_supplement_repository.py` 裡還有**數條**
  `max(per_minute) <= 60` 形式的上限檢查。它們是失敗情境下的「讀取量不得失控」sanity check，
  **不是**讀取量的驗收標準；第 14 輪只在該處就地標明 60 的性質，**沒有**改寫成實測 ratchet、也沒有改測試名。
  ⚠️ **這裡刻意不寫「共 N 處」**（~~原寫「8 處」，2026-09-28 第 15 輪更正：實測 `^\s*assert.*<= *60` 為 **7** 行，
  8 是把本段自己的說明一起數進去~~）—— 本段自己就在談那個形狀，**一寫下計數就會被自己推翻**，
  與 8.4 那一則自陳的病完全同型。要查請現場跑，不要引用本行。
- 📌 **登記、本輪未做（二）—— 本 repo 其他把「60 reads/min」寫成事實的地方**
  （**量測日 2026-09-28、範圍 `git grep -nE "60 reads|每分鐘 60|60 次讀取|reads/min" -- '*.py'`；
  只掃 `.py`，所以本檔自己不在母體內**）：

  | 檔案 | 命中行數 | 性質 |
  |---|---|---|
  | **`ui/helpers/v2_editor.py`** | 1 | ⭐ **使用者看得到的畫面文字**（「（每 user 每分鐘 60 reads 上限）。」）—— 紅隊建議優先序高於其餘各處 |
  | `repositories/snapshot_repository.py` | 1 | 註解 |
  | `services/fundclear_backfill.py` | 1 | docstring |
  | `services/nav_history_gs.py` | 2 | 註解／docstring |
  | `services/nav_history_store.py` | 2 | docstring／註解 |
  | `ui/helpers/cloud_io.py` | 1 | 註解 |
  | `tests/test_backfill_to_gs_gate0.py` | 1 | docstring |

  **已揭露、不在待辦內的三處**：`infra/gspread_retry.py`（自陳沒讀到一手頁面）、
  `repositories/policy_supplement_repository.py`（第 14 輪改寫）、
  `repositories/policy/_helpers.py`（**第 14 輪已在本分支修掉，不是邊界外**）。
  ⚠️ **2026-09-28 第 15 輪就地更正（有意識的更正，不是漏刪）**：~~原寫「另有 9 處……」並把上表七檔列在同一串~~
  —— **那個 9 是「命中行數」不是「檔數」**，句子卻長得像在數檔案，容易被讀成兩種意思；
  回修單轉述紅隊要改成「6 檔」，**本組實測是 7 檔（9 行）**：
  紅隊那份清單**漏掉 `tests/test_backfill_to_gs_gate0.py`**（它同樣把 60 寫成事實、同樣沒有揭露）。
  現改為**逐檔列表＋各自行數**，兩種讀法都不會再被混淆。
  ⛔ **上表七檔不在第 14／15 輪的檔案邊界內，本輪一個字都沒動，登記待派**。

⚠️ **本節由資料工程組單組產出，未經第二組獨立複驗**（`CLAUDE.md` §-2 規則 6）。

---

## 九、持倉體檢頁：結論燈的 N 改數「檔」，與 `44` 的偏離（客戶 2026-10-03 裁示）

**量測日 2026-10-03，基底 `feat/v2-hld-s6a2` @ `a5fc092`**（依第六節第 2 條：更新時帶上量測日與 SHA；
本節初版寫於 `a5fc092`，基底當時標 `e3b2a9f`；同日依稽核回修，見 9.5）。
本節是**驗收規則**，不是動工授權（`CLAUDE.md` §-1）。
寫在本檔而不寫進 `44` 的理由同 7.1：`docs/v2/44_fund_ui_ssot.md` 已凍結，不得加附註。
客戶原話（2026-10-03）：「`44` 已凍結不能改，偏離必須留在正式驗收文件；只寫交接本 = 藏起來。」

### 9.1 `44` 原文（`docs/v2/44_fund_ui_ssot.md`，行號於 2026-10-03 在 `a5fc092` 上重讀核對）

| 行 | 位置 | 原文（逐字摘錄） |
|---|---|---|
| :489 | `HLD-0` 規則欄 | 「偏離筆數大於零 → 燈為黃，文案「有 N 檔超出你設定的門檻」，N 為 `HLD-1` 算出的筆數。」 |
| :493 | `HLD-0` 判準 | 「把門檻調到兩檔超出，文案中的 N 為 2，且與 `HLD-1` 列出的列數相等；再把其中一檔的淨值整個抽掉，……N 隨之變為 1，而 N 與 `HLD-1` 的列數仍然相等」 |
| :503 | `HLD-0` 判準下方的更正註記 | 「依客戶對 `H-01` 的裁示「修 `HLD-1` 規則，缺淨值檔不計入列數，讓 N ＝ 列數」。」（同段 :502 標明日期 2026-09-22、決策者客戶） |
| :515 | `HLD-1` 空狀態欄（2026-09-22 客戶改寫） | 「某檔缺淨值 → 該檔不進本表、不佔一列、不計入列數，於是 `HLD-0` 文案裡的 N 等於本卡的列數。」 |
| :518 | `HLD-1` 判準 | 「……且 `HLD-0` 文案裡的 N 與本塊的列數相等」 |

- **:488（`HLD-0` 來源欄）**：「不自取數。只讀 `HLD-1`、`HLD-2`、`HLD-3` 三塊的狀態值與 `HLD-1` 的偏離筆數」——
  ~~此處的「偏離筆數」**依 9.2 讀作不重複的檔數**。它不是「N 與列數相等」那一類的相等句，**不算偏離規定**，照舊驗收
  （本行為 2026-10-03 規格組建議補記）。~~
  → **2026-10-03 更正（有意識的更正，不是漏刪；出處：紅隊 2026-10-03 指出）**：舊句把「偏離筆數」重新解讀成「檔數」，
  與 9.2 把 :489「N 為 `HLD-1` 算出的筆數」列為偏離自相矛盾 —— 同一個「筆數」一處算偏離、一處改讀不算。
  **現行說法（不重新解讀詞義）**：:488 規定的是**來源**：`HLD-0` 不自取數，只讀 `HLD-1` 等三塊。
  實作的 N 仍只由 `HLD-1` 的偏離列算出，故這條來源規定照舊成立、照舊驗收；N 怎麼數，由 9.2 管。

⚠️ 初版（`a5fc092`）只列了 :489、:493、:518，**漏了 :515**（總管派工單漏列；2026-10-03 規格組稽核指出），本版補登。

### 9.2 偏離內容

**可自證的事實**（`ui_v2/hld/logic.py`）：
- 結論燈文案的 N ＝ `HLD-1` 偏離表裡**不重複的 `fund_code` 個數**（`_build_page_model` 的 `deviation_count`）。
- `HLD-1` 偏離表**逐持倉、逐門檻各一列**（`deviation_rows` 對每一筆持倉的指標、每一條門檻各判一次，超出就一列）。
- 因此 **N 不大於列數**。**兩者在何種情形相等，本文不作保證。**

| | `44` 的規定 | 本頁實作（客戶 2026-10-03 裁示） |
|---|---|---|
| 結論燈文案的 N | :489「N 為 `HLD-1` 算出的筆數」 | **不重複的檔數**。文案字面「有 N 檔超出你設定的門檻」一字不改 —— 改成數檔之後，字面說的「檔」才是真的 |
| `HLD-1` 偏離表 | 逐持倉、逐門檻各一列 | **不變** |
| 「N 與列數相等」 | :493、:515、:518 三處都寫 N 與 `HLD-1` 的列數相等 | **這三處的「N 與列數相等」一律不驗收**；只保證 N 不大於列數（見上）。:515 同一格的其餘規定（缺淨值的檔不進本表、不佔一列、不計入列數、卡尾另寫一行）照舊驗收 |
| 畫面上 `HLD-1` 卡尾那一句 | — | 原為「未列入的檔不進上表、也不進偏離筆數；燈上的 N 與本卡列數因此相等。」—— 後半子句不再成立，**只刪「；燈上的 N 與本卡列數因此相等」**，前半句一字不改，現為「未列入的檔不進上表、也不進偏離筆數。」（示範版與正式版同受影響，客戶授權的唯一畫面差異） |

~~（初版 9.2 表內原寫：同一檔超出兩條以上門檻時 N 小於列數，「每一檔最多超出一條時照舊相等」。）~~
→ **2026-10-03 就地更正（有意識的更正，不是漏刪；紅隊稽核以實測推翻）**：「每一檔最多超出一條時照舊相等」**不成立**。
反例：`fixtures.dataset_full()` 裡 AAAA 再掛一張保單（`holding_id` 為 `H-AAAA-2`、`policy_id` 為 `P-001`），
門檻只設「最大回撤 低於 -10」→ 每一檔都只超出一條門檻，但 `HLD-1` 有 **2 列**（同一檔兩筆持倉各一列），燈寫「有 **1** 檔」。
本組 2026-10-03 在 `a5fc092` 上照此最小情境重跑：列數 2、N 1，與紅隊相同。
**舊句錯在把「列」當成「檔 × 門檻」**，漏了列其實是逐**持倉**。本版改寫成上面那三行可自證的事實，不另立「在某某情形下相等」的條件句。

**兩次客戶裁示，出處分開寫**：
- **2026-09-22（`H-01`）**：「修 `HLD-1` 規則，缺淨值檔不計入列數，讓 N ＝ 列數」（`44` :503 轉述；同日改寫的 :515 寫成「於是 `HLD-0` 文案裡的 N 等於本卡的列數」）。
- **2026-10-03**：燈改數不重複的檔（N1：持倉 3 檔，燈卻寫「有 4 檔超出」），並刪畫面上「N 與列數相等」那一句。
- **後一次取代前一次的範圍，只限「N 與列數是否相等」這一點**：依 2026-10-03 裁示，`H-01` 那句「讓 N ＝ 列數」**不再作為判準**。
  `H-01` 的其餘內容（缺淨值檔不進本表、不佔一列、不計入列數）**不受影響、照舊有效**。舊裁示在 `44` 原文不刪、不改（`44` 已凍結）。

- **決策者**：客戶（2026-10-03）。
- **理由**：文案說的是「檔」，數的卻是列（N1）。`44` 已凍結，不改 `44`、改實作，偏離登記在本節。
- **對應 commit**：`e3b2a9f`（燈改數不重複的檔）；`a5fc092`（刪卡尾那一句的後半子句，並寫入本節初版）；
  本節回修在 `a5fc092` 的下一個 commit（只改本檔）。

### 9.3 驗收

- `tests/ui_v2/test_hld_live_logic.py`：
  `test_S6a2_第2項_N1_結論燈數不重複的檔_偏離表列數不變`（3 檔各超出兩條：表 6 列、燈寫 3 檔）、
  `test_S6a2_第2項_N1_一檔一列時燈數仍與列數相等`（只驗假資料 `full` 這一組的現況，不是相等條件的保證）、
  `test_S6a2追加_一檔超出兩條門檻_燈寫1檔_表2列_畫面沒有列數相等`、
  `test_S6a2追加_HLD1卡尾那一句_只刪後半子句_前半句一字不改`。
- `tests/ui_v2/test_hld_live_page.py`（slow）：
  `test_S6a2_第2項_N1_畫面上燈寫不重複的檔數_偏離表照列數`、
  `test_S6a2追加_畫面_一檔超出兩條門檻_燈寫1檔_表2列_沒有列數相等`。
- ⚠️ **既有測試 `tests/ui_v2/test_hld_logic.py::test_結論燈的N等於HLD1的列數` 仍然通過、本輪未改** ——
  它只驗 `full`、`srcmiss` 兩組假資料在現況下 N 與列數剛好相等，
  **它不是在驗 `44` :493 的全稱判準，不得被引用為「該判準仍成立」的證據。**
  ~~（初版原寫：它用的假資料每一檔最多超出一條門檻，正好是「N 與列數相等」仍然成立的那一種情形。）~~
  → 2026-10-03 更正：「那一種情形」就是 9.2 被推翻的那個條件，同句一併改掉。
- `tests/ui_v2/test_hld_logic.py::test_第2件反向控制_十二情境乘九塊一百零八格逐格未變` 的 `("srcmiss", "HLD-1")`
  那一格摘要隨這一句換新值。換之前先證明：把現行模型裡的新句換回舊句再算摘要，該表與同檔另一張表共 135 格的舊值
  逐格全數重現（量測日 2026-10-03）—— 差異只有這一句。

### 9.4 登記、本節不處理

以下兩檔仍寫著「N 與列數相等」一類的字句。**兩檔都只登記、本輪不改字**：改字屬草稿／原型變更，要先回客戶。
行號為 **2026-10-03 在 `a5fc092` 上實測命中**，會漂移，要用請現場重讀。

- `docs/wireframes/draft_hld_live.html`：6 處 ——
  :354、:442、:529、:763 為卡片上的原句（4 處）；:740、:791 為說明文字裡引用那一句（2 處）。
- `docs/v2/prototype/ui_prototype_hld.html`：:501、:1809、:1846、:1849 共 4 處（總管派工單點名，本組逐行重讀確認）。
  ⚠️ 本組以 `grep -n "燈上的 N 與本卡列數\|列數相等"` 另掃到 **:991**（引用 `44` 判準「文案中的 N…與 `HLD-1` 列出的列數相等」），一併登記。
  ⚠️ 紅隊以 `grep -nE "N 等於|N ＝ 列數"` 再掃到兩處，本組現場重讀確認、一併登記：
  **:740**（「於是 `HLD-0` 的 N 等於本卡的列數，兩行判準自此可以同時通過。」）、
  **:994**（「客戶 2026-09-22 裁定：「修 `HLD-1` 規則，缺淨值檔不計入列數，讓 N ＝ 列數。」」）。
  **本組那條 grep 為什麼掃不到它們**：它只認「燈上的 N 與本卡列數」與「列數相等」兩種寫法；
  這兩行寫的是「N 等於本卡的列數」與「N ＝ 列數」，字面上兩種都不含 —— 字表選錯，掃再多次都一樣（`CLAUDE.md` §-1.5.1c 判定 2）。
  合計本檔登記的原型行號：:501、:740、:991、:994、:1809、:1846、:1849。
  ~~（初版寫「有數處」）~~ → 2026-10-03 依總管裁定改成實數。
  ⚠️ 上列行號是**量測日實測命中**，不是窮舉保證：換一種寫法（例如不含「列數」二字的同義句）掃不到。

### 9.5 修訂紀錄

- **2026-10-03（`a5fc092`）**：初版。
- **2026-10-03（`a5fc092` 的下一個 commit）**：依兩組稽核回修 ——
  9.2 刪「每一檔最多超出一條時照舊相等」並改寫為可自證的事實（紅隊必修 1）；
  9.1 補登 :515、9.2 的不驗收範圍涵蓋它（規格組必修 2）；
  9.1／9.2 補 :503 的 `H-01` 舊裁示與被取代範圍（總管裁定 3）；
  9.4 改成實數並補登原型檔（總管裁定 4）；9.3 同步更正一句同型的說法。
- **2026-10-03（`51e205f` 的下一個 commit）**：9.4 補登原型檔 :740、:994（紅隊建議），並寫明本組先前那條 grep 掃不到的原因；
  9.1 補記 `44` :488 的「偏離筆數」依 9.2 讀作不重複的檔數（規格組建議）；
  `tests/ui_v2/test_hld_live_logic.py::test_S6a2_第2項_N1_一檔一列時燈數仍與列數相等` 的 docstring 改成與 9.3 一致（只改 docstring）。
- **2026-10-03（`d59245e` 的下一個 commit）**：9.1 的 :488 補記改為不重新解讀詞義的說法（來源規定照舊驗收、N 怎麼數由 9.2 管）；
  舊句劃線保留。出處：紅隊 2026-10-03 指出舊句與 9.2 自相矛盾。

⚠️ **本節由架構與前端組單組產出，未經第二組獨立複驗**（`CLAUDE.md` §-2 規則 6）。

---

## 十、持倉體檢頁正式版（`app_hld_live.py`）與 `44` 的偏離（2026-10-09 登記）

**量測日 2026-10-09，基底 `main` @ `51ae661`**（PR #905 合併之後）。本節是**驗收規則與現況登記**，不是動工授權（`CLAUDE.md` §-1）。
寫在本檔而不寫進 `44` 的理由同 7.1：`docs/v2/44_fund_ui_ssot.md` 已凍結，不得加附註。
出處：交接本〈登記待辦〉「hld S6b 開工前盤點」第 6 條列出這些偏離；第 2 節 S6b 小節〈S6b-4 開工資格盤點〉第 3 點指出「重新取數」那一項已過期。
下表每一列由本組在 `51ae661` 上讀碼核對；`44` 行號同一基底，會漂移，要用請現場重讀。示範入口 `ui_v2/app_hld.py` 不經過 `ui_v2/hld/live.py`，下列偏離只屬正式版，另標者除外。

### 10.1 偏離清單

| # | 項目 | `44` 的規定 | 正式版現況 | 決策 | 程式出處 | 驗收 |
|---|---|---|---|---|---|---|
| 1 | HLD-4「存檔」停用 | :583 `HLD-4` 規則欄：本塊掛「存檔」，寫回 `user_setting` | 按鈕照掛、**停用**，停用原因「存檔寫入端尚未接上，這一輪只讀不寫」（與 alo 逐字相同）；HLD-4 說明區講「存檔」的兩句正式版不印 | 客戶 2026-10-02 裁示 A（文案逐字）；S6a-1 | `ui_v2/hld/live.py`：`SAVE_DISABLED_REASON`、`_DISABLED_BY_KIND`、`apply_live_notes`、`_LIVE_DROPS` | `tests/ui_v2/test_hld_live_logic.py::test_存檔一律停用_原因逐字`、`test_存檔停用原因_與alo頁逐字相同`、`test_S6a第三輪_正式版HLD4不印存檔那一句_示範版照印_其餘照舊` |
| 2 | 「重新取數」按鈕：**正式畫面拿掉** | :2009、:2011、:2323、:2326 的空狀態與錯誤模板都掛「重新取數」；:762 `HLD-8` 取數失敗時掛 | 正式版各塊的「取數」類按鈕一律不呈現，整頁錯誤畫面也不建這顆按鈕；該不該掛仍由 `logic` 判斷，示範版照掛。**不是停用＋原因**（舊說法已過期，見下方註） | 客戶 2026-10-09 裁示（PR #905） | `ui_v2/hld/live.py::apply_live_notes`（把 `_action_kind` 為「取數」的按鈕從各塊移除）；`ui_v2/hld/page.py::_render_live_error` | `tests/ui_v2/test_hld_live_logic.py::test_HLD1到3不掛重新取數_HLD8依值狀態掛_正式模式不呈現`、`test_示範模式_srcmiss與fetchfail仍掛重新取數`；`tests/ui_v2/test_hld_source.py::test_代碼對照拋L1例外_正式入口畫錯誤畫面_不印Traceback_不帶秘密值_沒有按鈕` |
| 3 | `fund_profile` 未接，成立日改用推定 | :531 `HLD-2`、:760 `HLD-8` 來源欄宣告 `fund_profile.inception_on`；:533 成立日晚於區間起點 → `⬜ 不適用：成立日晚於區間起點` | `fund_profile` 列在 `pending_tables`，`logic` **不讀**它；改用推定：該檔在 `nav` 表裡（不限區間）最早的 `nav_date` 晚於區間起點 → 區間報酬率、期間波動、最大回撤判 `⬜ 資料未備`，**不寫**「不適用：成立日晚於區間起點」（分不出是成立日晚、還是來源只給到那麼舊） | 總管 2026-10-02 S2 裁定 | `ui_v2/hld/logic.py::fund_metrics`（`nav_starts_late`）；`ui_v2/hld/live.py::assemble_live_load`（`pending_tables`） | 推定規則：`tests/ui_v2/test_hld_logic.py::test_S2_必修1_區間起點那天沒有淨值但更早還有_不觸發推定`、`test_S2_必修1_最早淨值等於區間起點_不觸發推定`；`fund_profile` 列在 `pending_tables`：`tests/ui_v2/test_hld_live_assemble.py::test_T3a_配息閘門是關的_pending_tables固定為fund_profile與dividend` |
| 4 | HLD-5 展開區的圖是佔位 | :707 `HLD-5` 規則欄：展開內容為持倉欄位、淨值折線、配息長條，共用同一條時間軸 | 兩格都是文字框（`hld-plot`），不畫真圖：淨值那一格寫「〔淨值折線〕與〔配息長條〕共用同一條時間軸」（無淨值或設定讀取失敗時改印對應訊息），配息那一格寫「〔配息長條〕照畫 · 本輪以佔位框代替，不畫真圖」。**示範版相同** | 總管 S6a 第二輪裁定：佔位框那一句保留（圖表確實還沒做，是真實資訊） | `ui_v2/hld/logic.py::_build_hld5`（`nav_plot_text`、`div_plot_text`）；`ui_v2/hld/page.py`（`hld-plot`）；`ui_v2/hld/live.py`（`_DEV_TRIMS` 上方註解） | `tests/ui_v2/test_hld_live_logic.py::test_S6a_HLD5佔位框照留`（斷言配息那一格「〔配息長條〕照畫 · 本輪以佔位框代替，不畫真圖」照留；淨值那一格的字句沒有專屬斷言） |
| 5 | HLD-0「前往 Sheets 維護持倉」按了不動 | :490 持倉表為空時掛這一枚（`導覽` 類）；:493 判準「按下那枚按鈕，畫面離開本儀表板前往 Sheets」 | 按鈕照掛、**可按**，但沒有接任何動作（`page.py` 畫 HLD-0 時不給 `on_click`），按下只重跑本頁，不離開。正式版未另做處理（「不動」＝沿用示範版現況）。**示範版相同** | 尚無裁示；交接本列為偏離登記 | `ui_v2/hld/logic.py`（`TEXT_GOTO_SHEETS`，`導覽` 類）；`ui_v2/hld/page.py::_render_lamp` → `_buttons(block, block["code"])`（無 `on_click`） | 無（`44` :493 那一步目前驗不到） |
| 6 | 同保單同基金分多列時未加總 | :1771 `44` 4.1：來源端分多次投入而登記成多列時，顯示時把金額與單位數加總成一列 | 每一筆持倉列各算一列（逐 `holding_id`），不合併、不加總；`source.py` 組 L2 輸入時也刻意不去重（去重會吃掉 `ccy_conflict`）。與 8.4（alo 讀表）是同一件事在 hld 的落點 | 未裁（8.4 已登記「接 UI 的那一輪要補」，合併後各欄取哪一列尚未裁示） | `ui_v2/hld/logic.py::all_metrics`、`_build_hld5`（展開鍵用 `holding_id`）；`ui_v2/hld/source.py` 檔頭第 2 條 | `tests/ui_v2/test_hld_source.py::test_每一筆持倉列對應一筆fund_帶holding_ccy_不去重`（驗的是不去重，不是驗 `44` 4.1 的加總判準） |

⚠️ **第 2 列的舊說法已過期**：交接本〈登記待辦〉「hld S6b 開工前盤點」第 6 條把它寫成「重新取數停用」——那是客戶 2026-10-02 裁示 A（停用按鈕原因句）、2026-10-03 再確認維持停用＋寫出原因（2420 張力結案）時的狀態（出處：交接本第 5 節〈已裁示（2026-10-02）〉A、〈已裁示（2026-10-03）〉）；客戶 2026-10-09 改裁為**正式畫面拿掉**，已隨 PR #905 落地（`926800d`；merge `5d12223`）。本表以現況為準。
⚠️ 「12:00 推定」「DIRECT 另列」兩項另見 8.1、8.3，不重複列入本表；「結論燈的 N 數檔」見第九節。

### 10.2 資料格式登記（內部自決，非畫面文案）

1. **`user_setting` 的 `hld_deviation_rules`**（總管 2026-10-03 裁定；`docs/v2/50_settings_sheet_design.md` :86 把字串格式交給各頁序列化決定）：
   - 值是 **JSON 陣列**，每個元素是**恰好**三個欄位的物件 `{"indicator", "direction", "value"}`：`indicator` 非空字串（照原字收，不去空白）；`direction` 只收「低於」「高於」（`logic.RULE_DIRECTIONS`）；`value` 是有限的數（`bool` 不算數；讀進來一律轉 `float`）。空陣列＝零條門檻，不是錯誤。
   - 值前後有空白、不是 JSON、不是陣列、元素欄位多一個少一個、JSON 物件裡同一個鍵出現兩次、`NaN`／`Infinity` → **讀取失敗**（畫面走設定讀取失敗那一支，不說「尚未設定門檻」）。
   - 寫入端停用（見 10.1 第 1 列），本頁只讀。
   - 程式：`ui_v2/hld/live.py::_parse_rules`、`_json_array`、`parse_user_settings`。驗收：`tests/ui_v2/test_hld_live_settings.py`。
   - ⚠️ `ui_v2/set/fixtures.py` 裡那筆示意值與此格式不符，屬示範資料，交接本另登記，本節不處理。
2. **hld `dataset["pending_tables"]`**：正式版**固定**為 `["fund_profile", "dividend"]`（客戶 2026-10-05 S6b-2 規則：至少列 `fund_profile`，配息閘門關閉時也列 `dividend`）；配息閘門（`nav_dividend.DIV_DATE_IS_EX_DATE_VERIFIED`）被打開 → 整頁報錯。程式：`ui_v2/hld/live.py::assemble_live_load`。
   - ⚠️ **同名不同物**：`services/v2_tables/settings_store.py` 的 ~~`PENDING_TABLES = ("nav", "dividend")` 是 set 頁與 alo 頁用的，**仍含 `nav`**，不可移除（alo 頁寫死 `nav: []`，移除會讓 `tests/ui_v2/test_alo_source.py` 轉紅；交接本〈登記待辦〉「hld S6b 開工前盤點」第 9 條，本組未實跑）~~ → **2026-10-09 狀態更新（不是漏刪）**：`PENDING_TABLES` 已改為 `("dividend",)`（客戶裁示 Q1 不存 NAV，`47406e2`）；alo 頁仍寫死 `nav: []`（alo 取淨值未獲授權），該測試已改驗新狀態。`PENDING_TABLES` 是 set 頁與 alo 頁用的。hld 的那一份不讀它。
3. **hld `dataset["fund_errors"]`**：形狀 `{"nav": {fund_code: 遮蔽後的訊息原文}}`；沒有失敗時是空字典。**放進去的**：L1 淨值取數真的失敗的那幾檔，訊息原文以 `mask` 遮過後放入（含 L1 回傳型別不符）。**不放進去的**（畫面印「⬜ 資料未備」）：淨值被扣下（`ccy_missing`、`ccy_conflict`、`fetched_at_missing`、`fetched_at_in_future` 四碼）、代碼對照查不到、來源回空（訊息恰為 `EMPTY_WITHOUT_REASON` 且未取到任何列）、L1 有回但 L2 全數拒收。扣下代碼不在四碼內（含 `input_conflict`）→ raise。程式：`ui_v2/hld/live.py::assemble_live_load`；四碼清單：`ui_v2/hld/source.py::_NAV_UNAVAILABLE_WITHHELD`。驗收：`tests/ui_v2/test_hld_live_assemble.py` 以 `test_T4` 開頭的測試、`tests/ui_v2/test_hld_source.py::test_常數注入_扣下清單恰為四碼_不含input_conflict_其餘照L2`。

---

## 十一、設定與診斷頁 SET-0：「淨值、配息尚未接取數來源」~~暫留（2026-10-09 登記）~~ → 已處理（2026-10-09，`47406e2`）

> **2026-10-09 狀態更新（不是漏刪；下列三點在寫下當時為真）**：#3 淨值層已接上（客戶 2026-10-09 裁示 Q1～Q4、文案依 `docs/v2/53_nav_source_plan.md` §7 核准），`SET-0`／`SET-1`／`SET-2`／`SET-5` 一次一致處理，`47406e2`：
> - `SET-0` 改印「配息尚未接取數來源；淨值即時取得」（`TEXT_PENDING_DIVIDEND`；配息仍待接就印，不再看 `nav`）；舊常數 `TEXT_PENDING_NAV_DIVIDEND` 已移除。
> - `SET-1` 淨值列不再印「尚未接上」原因；時間取 `fetch_log` 淨值層最近一次 `ok` 的 `started_at`，有時間時下一行印「這個時間是 set 頁最近一次重新取數淨值的時間，不是持倉頁畫面上那一份的時間」；從未成功 → 「⬜ 資料未備」。
> - `SET-2` 淨值層不再印「尚未接上」原因；配息、其他層照舊。`SET-5` 說明行換句、淨值層可按。
> - 驗收：`tests/ui_v2/test_set_live_logic.py` 以 `test_淨值` 開頭的測試、`tests/ui_v2/test_set_live_page.py::test_重新取數_淨值層按下後只記一筆fetch_log_SET1淨值列印時間與新句`、`tests/test_v2_tables_settings_store.py` 以 `test_淨值層_` 開頭的測試。

- **現況**（基底 `51ae661`）：`ui_v2/set/live.py` 的 `TEXT_PENDING_NAV_DIVIDEND`（「淨值、配息尚未接取數來源」，客戶 2026-09-26 定稿）在 `pending_tables` 同時含 `nav` 與 `dividend` 時印在 `SET-0` 說明區；set 頁的 `pending_tables` 來自 `settings_store.PENDING_TABLES`，目前仍含 `nav`，所以這一句照印。
- **與現況的落差**：持倉體檢正式版自 PR #905 起即時取淨值，「淨值……尚未接取數來源」對 hld 而言已不完整；同頁 `SET-1` 淨值列（該類沒有資料時）與 `SET-2` 淨值層（沒有紀錄時）也仍印「原因：……尚未接上」（`TEXT_REASON_KIND_PENDING` 條件看 `pending_tables`；`TEXT_REASON_TIER_PENDING` 另看 `wired_tiers`：該層沒有紀錄、不在 `settings_store.WIRED_TIERS` 裡（目前只有市場指標在內），且該層無對應表或對應表在 `pending_tables` 裡才印；`ui_v2/set/live.py` 的 SET-2 那一段）。
- **處置**：客戶 2026-10-09 裁示（甲）——**暫留不改**；等 #3 `nav` 表接上來源之後，`SET-0` 與 `SET-1`／`SET-2` 一起一致處理，避免同一頁互相矛盾。本輪不改任何 `ui_v2/` 文案常數。
- 出處：交接本第 5 節「S6b-4 的 SET-0／SET-1／SET-2 一致性」；〈登記待辦〉「S6b-3 留給 S6b-4 的登記」第 2 條。

⚠️ **第十、十一節由執行組單組產出，未經第二組獨立複驗**（`CLAUDE.md` §-2 規則 6）。

---

## 十二、五頁最終驗收清單（S7 收尾，2026-10-09）

**量測日 2026-10-09，基底 `main` @ `369628f`**（PR #911 的合併提交）。出處：客戶 2026-10-09 裁示 S7「只做五頁最終驗收文件收尾；把既有驗收清單整理成最終版；不新增使用說明、不創造新文案」（總管轉達；對話中，repo 內無原文）。
本節**只彙整**第二～十一節與交接本已有的條目，每列引用原節號；**不新增驗收標準、不寫畫面文案、不寫使用說明**。條文內容以原節為準，本節與原節不一致時照原節。
本節是驗收清單，不是動工授權（`CLAUDE.md` §-1）。

### 12.0 盤點：既有驗收條目放在哪裡

| 位置 | 內容 | 本節怎麼用 |
|---|---|---|
| 本檔第二～六節 | 基線、正控、無效跑法、五頁對照表、維護規則 | 列入「跨頁」 |
| 本檔第七節 | 失敗訊息遮蔽（MKT、HLD、SET 的畫面落點；M1～M12） | 依頁拆入各表；M1～M10 列入「跨頁」 |
| 本檔第八節 | alo 讀表（R1、U9、R2、總管暫定、加總、讀取量） | 列入 ALO；8.1 末段、8.2 末段、8.3 更正屬 hld 正式版的部分列入 HLD |
| 本檔第九～十節 | 持倉體檢頁的 N 數檔與正式版偏離 | 列入 HLD |
| 本檔第十一節 | SET-0 暫留 | 列入 SET |
| `docs/v2/44_fund_ui_ssot.md` §3.1～§3.5 各塊「判準」 | 五頁各塊的規格驗收（凍結檔） | 只引用節號；逐條判準與測試的對照**本輪沒做**，每頁一列標「未查證」 |
| 交接本 `docs/handover_2026_09_26_latest.md` | 總藍圖 #1 小步表、第 5 節裁示、〈登記待辦〉 | 只引用已合併小步與已裁示的待辦 |
| `docs/v2/51_cleanup_plan.md` §3（驗收 A／B／C） | 死碼清理的驗收，不是頁面驗收 | 不列入 |
| `docs/v2/04_design_grp_S3-S4-S5-S7.md` 第 5 節 | 舊 `ui/tab*.py` 雙軌的驗收標準，不是 `ui_v2/` 五頁 | 不列入 |
| `docs/v2/49_data_integration_plan.md` 第 8 節 (l) | 「時刻為推定」待補 | 已由本檔 8.1 補上，不重列 |

⚠️ 上表是本組以 `grep -n '驗收'` 掃 `docs/v2/*.md`、`docs/*.md` 與本檔後逐處判讀的**分類敘述**，不是窮舉；字表選錯就掃不到（`CLAUDE.md` §-1.5.1c 判定 2）。

### 12.1 狀態用語

- **通過**：本節 12.8 那一次實跑該測試通過。只代表「在 `369628f` 上這條測試是綠的」，不代表 `44` 該塊判準整條成立。
- **通過‡**：同「通過」，另帶一個條件 —— 該列引用 `tests/ui_v2/test_hld_live_logic.py` 的測試，而 12.8 那一次實跑在該檔 :128 有 2 個 skipped（測試內依參數排除空持倉情境）。這 2 個 skip 是否違反 4.3「出現任何 skipped 就不是有效的驗收」，待協作助手確認；確認前，這幾列的「通過」以該條件成立為前提。
- **通過（既有記錄）**：本輪沒有重跑，依原節記載的實跑結果。
- **偏離已登記**：與 `44` 不同、已有裁示或裁定並登記在原節。
- **待辦**：原節或交接本登記為尚未做。
- **未查證**：本輪查不到測試或實跑記錄，不推論成通過。

### 12.2 市場總覽（MKT）

| # | 驗收項目（原節） | 對應測試 | 狀態 |
|---|---|---|---|
| 1 | 示範入口 `ui_v2/app_mkt.py`（第五節） | `tests/ui_v2/test_mkt_logic.py`、`tests/ui_v2/test_mkt_page.py` 整檔 | 通過 |
| 2 | 正式入口 `ui_v2/app_mkt_live.py`（第 2.1 節逐檔表 2026-09-26 新增三檔） | `tests/ui_v2/test_mkt_live_logic.py`、`tests/ui_v2/test_mkt_live_page.py`、`tests/ui_v2/test_mkt_source.py` 整檔 | 通過 |
| 3 | `MKT-1`～`MKT-3` 失敗訊息遮蔽、同格下一行「已遮蔽憑證」（7.4-a） | `tests/ui_v2/test_mkt_live_page.py::test_M11_MKT版_畫面上的訊息與遮蔽後字串逐字相同_下一行加註` | 通過 |
| 4 | M12 突變正控（7.5-a） | 突變腳本，非常駐測試 | 通過（既有記錄：7.5-a，2026-09-26，三檔 11 條轉紅）；本輪未重跑 |
| 5 | `44` §3.1 `MKT-0`～`MKT-7` 各塊判準 | — | 未查證（逐條對照本輪沒做） |

### 12.3 持倉體檢（HLD）

| # | 驗收項目（原節） | 對應測試 | 狀態 |
|---|---|---|---|
| 1 | 示範入口 `ui_v2/app_hld.py`（第五節） | `tests/ui_v2/test_hld_logic.py`、`tests/ui_v2/test_hld_page.py` 整檔 | 通過 |
| 2 | 正式入口 `ui_v2/app_hld_live.py`：S1～S6b-4、三小塊、R-7（交接本總藍圖 #1 小步表，各列「依據」欄的合併提交） | `tests/ui_v2/` 底下 `test_hld_live_*.py` 六檔、`test_hld_read_failure_logic.py`、`test_hld_source.py` 整檔 | 通過‡（測試）；合併與協作助手複驗以交接本小步表為準 |
| 3 | 失敗訊息遮蔽（7.4-a 續） | `tests/ui_v2/test_hld_source.py` 的 `test_持倉與設定讀取失敗_各進對應錯誤_訊息經遮蔽`、`test_淨值取數失敗訊息經遮蔽`、`test_mask_error遮掉秘密值`、`test_正式入口_讀取拋例外_畫錯誤畫面_秘密值經遮蔽_不是示範模式`、`test_秘密值來源_st_secrets以外三處也收進遮蔽`；`tests/ui_v2/test_hld_live_assemble.py::test_T4a_某檔取數失敗_fund_errors放遮蔽後的原文_端到端全頁印出同一句且不含原文` | 通過 |
| 4 | 訊息旁「已遮蔽憑證」那一行（7.4-a 續，與 7.4 第二點的差距） | 無 | 偏離已登記；待辦（客戶 2026-10-09 裁示維持待辦；交接本第 5 節〈已裁示（2026-10-09）〉第 10 點） |
| 5 | 正式版「最後核對日」換算台灣日期（8.1 末段） | `tests/ui_v2/test_hld_live_logic.py` 的 `test_正式模式_HLD5欄名改為最後核對日只記日期_值只有日期`、`test_最後核對日_合格值換成台灣日期`、`test_最後核對日一格不合格_整頁不崩_那一格進系統錯誤` | 通過‡ |
| 6 | `HLD-5` 保單欄 DIRECT 顯示「直接持有」（8.2 末段） | `tests/ui_v2/test_hld_logic.py::test_DIRECT保單欄位顯示直接持有而不是空白` | 通過 |
| 7 | DIRECT 持倉另列、不計入體檢（8.3 更正段，客戶 2026-10-02 裁示 3-B (ii)） | `tests/ui_v2/test_hld_live_logic.py` 以 `test_DIRECT_` 開頭的測試 | 通過‡ |
| 8 | 結論燈 N 數不重複的檔（9.2、9.3） | 9.3 所列六條（`test_hld_live_logic.py` 四條、`test_hld_live_page.py` 兩條） | 通過‡；偏離已登記（9.2：`44` :493、:515、:518 的「N 與列數相等」不驗收） |
| 9 | 草稿與原型仍寫「N 與列數相等」（9.4） | — | 待辦（只登記、不改字；改字要先回客戶） |
| 10 | `HLD-4`「存檔」停用（10.1 第 1 列） | 10.1 第 1 列所列三條 | 通過‡；偏離已登記 |
| 11 | 「重新取數」正式畫面拿掉（10.1 第 2 列） | 10.1 第 2 列所列三條 | 通過‡；偏離已登記 |
| 12 | `fund_profile` 未接、成立日推定（10.1 第 3 列） | 10.1 第 3 列所列三條 | 通過；偏離已登記 |
| 13 | `HLD-5` 展開區圖是佔位（10.1 第 4 列） | `tests/ui_v2/test_hld_live_logic.py::test_S6a_HLD5佔位框照留` | 通過‡；偏離已登記（淨值那一格的字句沒有專屬斷言，同 10.1） |
| 14 | `HLD-0`「前往 Sheets 維護持倉」按了不動（10.1 第 5 列） | 無（`44` :493 那一步目前驗不到） | 未查證；偏離已登記（尚無裁示） |
| 15 | 同保單同基金分多列未加總（10.1 第 6 列；與 8.4 同一件事） | `tests/ui_v2/test_hld_source.py::test_每一筆持倉列對應一筆fund_帶holding_ccy_不去重`（驗的是不去重，不是 `44` 4.1 的加總判準） | 偏離已登記；待辦（未裁） |
| 16 | 資料格式：`hld_deviation_rules`、`pending_tables`、`fund_errors`（10.2） | `tests/ui_v2/test_hld_live_settings.py` 整檔；`tests/ui_v2/test_hld_live_assemble.py::test_T3a_配息閘門是關的_pending_tables固定為fund_profile與dividend`；同檔以 `test_T4` 開頭的測試；`tests/ui_v2/test_hld_source.py::test_常數注入_扣下清單恰為四碼_不含input_conflict_其餘照L2` | 通過 |
| 17 | `44` §3.2 `HLD-0`～`HLD-8` 各塊判準 | — | 未查證（逐條對照本輪沒做） |

### 12.4 標的探索（EXP）

| # | 驗收項目（原節） | 對應測試 | 狀態 |
|---|---|---|---|
| 1 | 示範入口 `ui_v2/app_exp.py`（第五節） | `tests/ui_v2/test_exp_logic.py`、`tests/ui_v2/test_exp_page.py` 整檔 | 通過 |
| 2 | 正式入口（接真資料） | — | 待辦（尚無正式入口；客戶 2026-10-09 裁示維持暫緩，交接本第 5 節〈已裁示（2026-10-09）〉第 3 點） |
| 3 | `44` §3.3 `EXP-0`～`EXP-7` 各塊判準 | — | 未查證（逐條對照本輪沒做） |

### 12.5 資產配置（ALO）

| # | 驗收項目（原節） | 對應測試 | 狀態 |
|---|---|---|---|
| 1 | 示範入口 `ui_v2/app_alo.py`（第五節） | `tests/ui_v2/test_alo_logic.py`、`tests/ui_v2/test_alo_page.py` 整檔 | 通過 |
| 2 | 正式入口 `ui_v2/app_alo_live.py`（#860，`651bd77`；交接本總藍圖依賴欄 #1 那一格） | `tests/ui_v2/test_alo_live_logic.py`、`tests/ui_v2/test_alo_live_page.py` 整檔 | 通過 |
| 3 | 讀表：最後核對日換成當日 12:00 台灣時間，推定值（8.1） | `tests/test_v2_tables_alo_holdings.py`、`tests/test_policy_supplement_repository.py` 以 `test_R1_` 開頭的測試 | 通過 |
| 4 | 讀表：DIRECT 列照讀、逐筆警示、大小寫敏感（8.2） | `tests/test_v2_tables_alo_holdings.py` 以 `test_U9_`、`test_裁定8_` 開頭的測試 | 通過 |
| 5 | `44` 4.4「`DIRECT` 這一列固定存在」表判準（8.2 表） | — | 偏離已登記（暫停驗收，總管依 R2 推導） |
| 6 | DIRECT 持倉不產生 `holding` 列（8.3） | `tests/test_v2_tables_alo_holdings.py::test_裁定4_總管暫定_DIRECT持倉不產生holding列` | 通過；總管暫定，不是客戶裁示 |
| 7 | 同鍵分多列時顯示才加總（8.4） | — | 待辦（接 UI 的那一輪要補；合併後各欄取哪一列未裁） |
| 8 | 讀取量是關係不是門檻（8.5） | `tests/test_policy_supplement_repository.py` 以 `test_第14輪BM1_` 開頭的測試、`tests/test_v2_tables_alo_holdings.py` 以 `test_第14輪BM1_整條路_` 開頭的測試 | 通過 |
| 9 | 其他檔把「60 reads/min」寫成事實（8.5 登記二） | — | 待辦 |
| 10 | 讀表秘密值在 L3 讀、遮蔽在寫出點做一次（7.3 末條「遮蔽只在寫出點做一次」） | `tests/ui_v2/test_alo_source.py` 整檔 | 通過 |
| 11 | `ALO-1`／`ALO-4` 存檔（總藍圖 #5） | — | 待辦（客戶 2026-10-09 已裁兩鍵部分失敗的處理，待實作；交接本第 5 節〈已裁示（2026-10-09）〉） |
| 12 | `44` §3.4 `ALO-0`～`ALO-7` 各塊判準 | — | 未查證（逐條對照本輪沒做） |

### 12.6 設定與診斷（SET）

| # | 驗收項目（原節） | 對應測試 | 狀態 |
|---|---|---|---|
| 1 | 示範入口 `ui_v2/app_set.py`（第五節） | `tests/ui_v2/test_set_logic.py`、`tests/ui_v2/test_set_page.py` 整檔 | 通過 |
| 2 | 正式入口 `ui_v2/app_set_live.py`（該檔於 `0062b7f` 加入；對應 PR 本組未查） | `tests/ui_v2/test_set_live_logic.py`、`tests/ui_v2/test_set_live_page.py` 整檔 | 通過 |
| 3 | `SET-2`／`SET-6` 失敗訊息遮蔽、下一行「已遮蔽憑證」，與 `fetch_log.message` 逐字相同（7.4、7.5 M11） | `tests/ui_v2/test_set_live_page.py::test_M11_SET版_取數失敗訊息與fetch_log逐字相同_SET2與SET6下一行加註`；`tests/ui_v2/test_set_live_logic.py::test_讀取失敗_訊息遮蔽_各處下一行加已遮蔽憑證` | 通過（7.5-a 原記「只做了 MKT 版」，見該處 2026-10-09 補註） |
| 4 | `SET-0`「淨值、配息尚未接取數來源」暫留（十一） | 見第十一節 2026-10-09 狀態更新 | ~~偏離已登記；待辦（等 #3 淨值來源完成後與 `SET-1`、`SET-2` 一起處理）~~ → 已處理（2026-10-09，`47406e2`；狀態更新，不是漏刪） |
| 5 | `44` §3.5 `SET-0`～`SET-7` 各塊判準 | — | 未查證（逐條對照本輪沒做） |

### 12.7 跨頁

| # | 驗收項目（原節） | 對應測試 | 狀態 |
|---|---|---|---|
| 1 | `tests/ui_v2/` 全跑基線（2.1） | 2.1 指令 | 見 12.8 |
| 2 | 文件守衛（2.2） | 2.2 指令 | 見 12.8 |
| 3 | 正控：改反一條斷言會轉紅（第三節） | — | 通過（既有記錄：2026-09-25）；本輪未重做 |
| 4 | 遮蔽 M1～M10（7.5） | `tests/test_v2_tables_masking.py` 整檔 | 通過 |
| 5 | 遮蔽仍遮不到的形態、非字串秘密值（7.3 登記） | — | 待辦（客戶 2026-10-09 裁示：正式路徑未發現可達前不動） |
| 6 | 秘密值很短時連帶遮到一般字元（7.8） | — | 待辦（只登記，不改程式） |
| 7 | 本檔禁用詞與識別碼自檢（第六節） | 第六節兩條指令 | 見 12.8 |

### 12.8 本輪實跑（量測日 2026-10-09，基底 `369628f`）

驗收用 venv：Python 3.11.17、streamlit 1.59.2、pytest 9.1.1、playwright 1.63.0；`UI_V2_CHROMIUM=/opt/pw-browsers/chromium-1194/chrome-linux/chrome`。工作樹只多本節與交接本的文件改動，沒有 `.py` 改動。

1. **頁面測試與讀表／遮蔽測試**（第 2.1 指令再加三支根目錄測試檔，一次跑完）：
   ```bash
   UI_V2_CHROMIUM=<chromium 執行檔路徑> <venv>/bin/python -m pytest tests/ui_v2/ tests/test_v2_tables_masking.py tests/test_v2_tables_alo_holdings.py tests/test_policy_supplement_repository.py -q -p no:cacheprovider -rs
   ```
   結果：`2679 passed, 2 skipped`，0 failed，耗時 870.70 秒，結束碼 0。逐段：`tests/ui_v2/` 2208 passed、2 skipped；`tests/test_v2_tables_masking.py` 71 passed；`tests/test_v2_tables_alo_holdings.py` 129 passed；`tests/test_policy_supplement_repository.py` 271 passed。
   - 2 個 skipped 都在 `tests/ui_v2/test_hld_live_logic.py:128`（`test_示範模式_同一份去字資料_照舊帶示意字樣` 的 `[empty]`、`[emptyfail]` 兩組參數），原因字串「空持倉：畫面上沒有數字，示範模式本來就沒有字尾」—— 是測試內依參數排除空持倉情境，不是缺 streamlit／playwright 的環境跳過（第四節那一種）。⚠️ 4.3 末段寫「出現任何 skipped … 就不是有效的驗收」；這 2 個算不算違反該句，待協作助手確認，4.3 判準文字不改。依這一次實跑標「通過」、且引用該檔測試的列，一律標「通過‡」（定義見 12.1）。
2. **文件守衛**（第 2.2 指令）：`91 passed`（66／7／18），與 2026-09-25 相同。
3. **本節引用的測試名**：12.2～12.6 與它們引用的 7.4-a 續、8.1～8.5、9.3、10.1、10.2 所列具名測試與「以 `test_…` 開頭」的測試，本組以腳本逐一對照 `tests/` 的 `def` 與這一次的 JUnit 結果：**全部存在，全部通過**。劃線保留的舊名（8.3 那一個）不在對照範圍。
4. **第六節自檢**（本節定稿後跑）：禁用詞只命中 8.4 那一句、詞表第 1 個，第六節三條件齊備，視同 0；識別碼 0、模型名（不分大小寫）0。本節不寫指令輸出的原始計數（寫下就會被本節自己改變，同 8.4 那一則）。

### 12.9 條目數

| 頁 | 條目數 | 通過 | 偏離已登記（含與通過並列者） | 待辦 | 未查證 |
|---|---:|---:|---:|---:|---:|
| MKT | 5 | 3 ＋ 1（既有記錄） | 0 | 0 | 1 |
| HLD | 17 | 12 | 8 | 3 | 2 |
| EXP | 3 | 1 | 0 | 1 | 1 |
| ALO | 12 | 7 | 1 | 3 | 1 |
| SET | 5 | 3 | 1 | 1 | 1 |

HLD 的 12 條「通過」中有 7 條是「通過‡」（12.1）。一列可同時算進兩欄（例：「通過；偏離已登記」），所以各欄相加不等於條目數。另有跨頁 7 條（12.7）不計入上表。

⚠️ **第十二節由執行組單組產出，未經第二組獨立複驗**（`CLAUDE.md` §-2 規則 6）。「通過」只指 12.8 那一次實跑；`44` 各塊判準的逐條對照沒有做，所以本節**不宣稱**任何一頁的規格已全部驗收。
