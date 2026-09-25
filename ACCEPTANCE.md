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

**2026-09-25 實測（基底 `9950e99`）：`743 passed`，0 skipped，0 failed，耗時 588.61 秒。**
（本檔與 alo 線框改完之後又重跑一次，結果記在第 2.3 小節。）

畫面測試是 `tests/ui_v2/` 裡標了 `slow` 的那一批，可以單獨列出來數。
CI 的 slow lane 跑的是全 repo 的 `python -m pytest -v -m "slow"`，不只 ui_v2：2026-09-25 實測（基底 `9950e99`）
`<venv>/bin/python -m pytest --collect-only -q -m slow -p no:cacheprovider` 回 `155/9451 tests collected`，
其中 127 條屬於 `tests/ui_v2/`，另 28 條在 repo 其他測試。只數 ui_v2 的那一批：

```bash
<venv>/bin/python -m pytest tests/ui_v2/ --collect-only -q -m slow -p no:cacheprovider
```

**2026-09-25 實測（基底 `9950e99`）：`127/743 tests collected (616 deselected)`。**

各檔條數（2026-09-25 實測，基底 `9950e99`；「收集」欄用 `--collect-only -q`，「slow」欄再加 `-m slow`）：

| 檔 | 收集 | 其中 slow |
|---|---:|---:|
| `tests/ui_v2/test_alo_logic.py` | 126 | 0 |
| `tests/ui_v2/test_alo_page.py` | 21 | 21 |
| `tests/ui_v2/test_exp_logic.py` | 134 | 0 |
| `tests/ui_v2/test_exp_page.py` | 45 | 45 |
| `tests/ui_v2/test_hld_logic.py` | 144 | 0 |
| `tests/ui_v2/test_hld_page.py` | 24 | 24 |
| `tests/ui_v2/test_mkt_logic.py` | 89 | 0 |
| `tests/ui_v2/test_mkt_page.py` | 9 | 9 |
| `tests/ui_v2/test_set_logic.py` | 111 | 0 |
| `tests/ui_v2/test_set_page.py` | 25 | 25 |
| `tests/ui_v2/test_ui_v2_lane_guards.py` | 15 | 3 |
| **合計** | **743** | **127** |

`*_page.py` 五檔整檔標 slow（檔內 `pytestmark = pytest.mark.slow`）；`test_ui_v2_lane_guards.py` 只有 3 條標 slow。

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

**判斷一次跑法有沒有效**：看輸出最後一行。基線是 `743 passed`、0 skipped。出現任何 skipped，或總數不是 743，就不是有效的驗收。

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

---

## 六、維護規則

1. **每次跑完，基線有變就當場更新本檔。** 包括 743、127、91 三個總數、第 2.1 與 2.2 兩張逐檔表、第四節的實測表。
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
