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
兩次都是 `91 passed`，逐檔條數相同。原因：`test_doc_counters.py` 只掃 `docs/v2/` 底下的 `*.md` 與 `prototype/*.html`，
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

**判斷一次跑法有沒有效**：看輸出最後一行。基線是 ~~`743 passed`~~ → ~~`803 passed`~~ → `820 passed`（2026-09-26 第二輪，基底 `12f8a9a` ＋ 工作樹；見 2.1）、0 skipped。出現任何 skipped，或總數不是 ~~743~~ ~~803~~ 820，就不是有效的驗收。

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

1. **每次跑完，基線有變就當場更新本檔。** 包括 ~~743、127~~ ~~803~~ 820、134、91 三個總數（2026-09-26 更新，理由見 2.1）、第 2.1 與 2.2 兩張逐檔表、第四節的實測表。
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
| `SETTINGS_SHEET_ID`（設定與取數紀錄試算表的 ID；2026-09-26 新增；**有意識的更正，不是漏刪**；決策者：客戶） | 整個值 | `repositories/settings_sheet_repository.py::settings_sheet_id`；遮蔽鍵表 `services/v2_tables/masking.py::MASKED_WHOLE_VALUE_KEYS`。理由：`docs/v2/50_settings_sheet_design.md` 第 2 節定案這一本的 ID 只放 secret、不寫進 repo（repo 公開，寫出 ID 等於公開客戶會被寫入的那本試算表位址）；它與下方丙類其餘五個試算表 ID 的處置刻意不同 |

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
| `POLICY_SHEET_ID`、`NAV_SHEET_ID`、`POOL_SHEET_ID`、`macro_weights_sheet_id`、`SHEET_ID` | ~~**建議：不遮，理由：試算表 ID 不是憑證，沒有被分享的人拿到 ID 也打不開；而且 `49` §4.1 要求設定頁顯示「目前讀的是哪一本」，遮掉就無法除錯。**~~ → **2026-09-26 更正（有意識的更正，不是漏刪；決策者：客戶）：不遮的範圍只到本列這五個鍵名，不是「試算表 ID 一律不遮」。** `SETTINGS_SHEET_ID` 已改列甲類遮蔽（見甲表）。本列五個鍵照舊不遮，理由照舊：它們不是憑證，沒有被分享的人拿到 ID 也打不開；`49` §4.1 要求設定頁顯示「目前讀的是哪一本」，遮掉就無法除錯。**舊句的用意仍然成立**（試算表 ID 本身不是憑證）；**被權衡掉的是它的射程** —— 舊句寫成「試算表 ID」這個類別，而 `SETTINGS_SHEET_ID` 那一本依 `50` 第 2 節刻意不公開，與本列五本的處置不同。⚠️ 本列只涵蓋這五個鍵名；日後新增的試算表 ID 鍵，不得援引本列預設為不遮，要逐鍵決定 |
| `google_service_account.client_email`、`client_id`；`google_oauth.client_id`、`redirect_uri` | **建議：不遮，理由：這些不是憑證；「權限不足」時使用者要知道該把試算表分享給哪一個服務帳戶信箱，遮掉 `client_email` 就給不出這個指引。** |
| `WATCH_CSV_URL` | **不在 Q13 射程內，不送客戶。** 查證：`git grep -n WATCH_CSV_URL 7f564aa -- '*.py' ':!tests/**'` 的命中逐行判讀後，讀值的是 `scripts/watchlist_push.py::main` 與 `scripts/weekly_switch_notify.py::_read_watchlist`（`scripts/dividend_calendar_notify.py` 經匯入後者使用；值由 `.github/workflows/` 的工作流程注入環境變數）；`ui/tab_manage.py` 的命中只在註解與說明字串裡，不讀值（正控：同一條指令命中 `scripts/weekly_switch_notify.py` 讀環境變數的那一行）。App 執行期不讀它，它也不經過 `fetch_log` 與 ui_v2 的畫面 —— Q13 管的是寫進 `fetch_log` 與上畫面的失敗訊息，碰不到它。⚠️ 若日後 App 或 ui_v2 開始讀它，性質接近憑證（公開 CSV 連結，知道網址就讀得到），屆時改列甲類遮蔽。 |
| `LINE_USER_ID`、`GITHUB_REPOSITORY`、`NAV_GATE0_MODE`、`NAV_CODES`、`US_STOCK_IDS`、`FUND_DB`、`GOOGLE_APPLICATION_CREDENTIALS`（檔案路徑）、`CHROMIUM_EXECUTABLE_PATH`、`GITHUB_STEP_SUMMARY` | 不遮：設定值或路徑，不是可單獨拿去呼叫服務的憑證。 |

~~丙表原版把試算表 ID、`client_email`、`WATCH_CSV_URL` 三項寫成「列為客戶裁示事項」~~ → 2026-09-26 稽核後改為本檔直接定案（決策者：AI 總管；有意識的更正，不是漏刪）。理由：三項都不是 Q13 裁示範圍內的新業務規則 —— 前兩項是「不遮會不會讓憑證外洩」的技術判斷，答案是不會；第三項根本不經過 Q13 管的兩個寫出點。⚠️ 2026-09-26 補註：這裡的「試算表 ID」指丙表列出的五個鍵名，不含 `SETTINGS_SHEET_ID`（客戶同日裁示該鍵要遮，見甲表）。

### 7.3 替換記號與替換規則

- **固定記號**：`‹已遮蔽›`（前後是單書名號 U+2039、U+203A，中間三個字）。一個秘密值被換成**一個**記號，不論原值多長。
- **其餘字元逐字保留**：不刪、不改寫、不截斷、不調整空白與換行。遮蔽前後，只有秘密值那幾段字元不同。
- **每一次出現都換**：同一個值在訊息裡出現幾次，就換幾次。
- **要一併遮的寫法**（同一個值在錯誤訊息裡常以別的形態出現）：
  1. 原值；
  2. 網址百分比編碼後的值（`urllib.parse.quote(值, safe="")` 與 `quote_plus(值)` 兩種）——金鑰進了查詢字串，例外訊息印的是編碼後的網址；
  3. 服務帳戶 `private_key`：原值（含真實換行），以及換行被跳脫成反斜線加 n 的寫法（JSON 字串內的形態）。
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
| M11 | `tests/ui_v2/test_mkt_live_page.py::test_M11_MKT版_畫面上的訊息與遮蔽後字串逐字相同_下一行加註` | **只做了 MKT 版**（畫面字串與遮蔽後字串逐字相同、下一行有「已遮蔽憑證」）。`fetch_log` → `SET-2`／`SET-6` 那兩條路要等 `fetch_log` 落地（`49` Q12）才做得了 |
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
