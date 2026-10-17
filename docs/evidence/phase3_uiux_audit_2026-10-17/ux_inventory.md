# B 線 `ui_v2/` 五頁現況 UX Inventory（唯讀稽核，2026-10-17，HEAD `57f03c9`）

## 0. 方法、環境、證據檔（先讀這段）

- **repo 未改一個字**：所有執行都在 scratchpad 的 repo 複本（`git ls-files` 逐檔複製，無 `.git`）裡跑；真 repo `git status --short` 執行前後皆 0 行（實測）。
- **環境**：系統 `python3` 與 `/root/.local/bin/pytest` 的 venv 都沒有 streamlit（實測）。在 scratchpad 另建 venv（`uv`，streamlit 1.59.2 ＋ `requirements.txt` 全部 ＋ playwright 1.64），Chromium 用 `/opt/pw-browsers/chromium-1194`。**這不是 CI 的環境**。
- **三種渲染模式**（AppTest `from_string`，每頁一個獨立行程）：
  1. `harness_*`：正式模式路徑（`page.render(load_live=...)`）＋各頁 fixtures 當資料。腳本逐字取自 `tests/ui_v2/test_live_390_page.py::_SCRIPTS`，等於「資料齊全的正式畫面」。
  2. `unconf_*`：與 `ui_v2/app_preview.py` 相同的呼叫（真 `source.load_live`），**沒有任何 secrets**。等於「新部署、還沒設定」。mkt 會真的連一次 Yahoo，被代理擋下（403）。
  3. `demo_*`：示範模式（`page.render()`，預設情境）。
- **390px 實測**：自寫 playwright 腳本（viewport 390×844）＋實跑既有 `tests/ui_v2/test_live_390_page.py`。
- **既有測試**：在複本裡跑完整 `tests/ui_v2`：**3072 passed、4 failed、33 skipped**（374 秒）。4 個 failed 全在 `test_hld_logic.py`（2）與 `test_hld_read_failure_logic.py`（2），都是黃金雜湊比對（例：`holdfail/HLD-2` `4b599a9f2b3f != 6347d81de348`）。**原因沒查**，可能和日期或環境有關，未驗證。
  - ⚠ 第一次在真 repo 跑出 952 errors，這次作廢：跑到一半我在同一個 venv 裝了 playwright 和整份 requirements。改在複本重跑才得到上面的數字。
- **標記**：「實測」＝跑出來的輸出。「讀碼」＝看程式碼得出。「推論」＝由前兩者推出、沒有直接驗證。
- **證據檔**（scratchpad 內）：`dumps/{harness,unconf,demo}_<頁>.txt`（AppTest 元素樹）、`dumps/jargon_counts.txt`、`dumps/controls.txt`、`m390/*.json|png`、`m390b/*.json`、`tools/*.py`、`scripts/*.py`。
- **行號**以 `57f03c9` 實測為準。

---

## A. 現況 UX Inventory（首屏由上而下）

**五頁共同骨架（讀碼＋實測）**：每頁由上而下依序是：

1. 頁名
2. 提問句（副標）
3. `層 1　結論` 標籤 ＋ `*-0` 結論燈
4. `層 2　核心卡` 標籤 ＋ 3 張卡（`st.columns(3)`）
5. `層 3　操作（預設收合）` 標籤 ＋ 2 個 expander
6. `層 4　佐證（預設收合）` 標籤 ＋ 2～3 個 expander
7. 頁尾「本頁不負責什麼」＋ `G1†/G2†/G3†` 徽章

- 所有 expander 預設都收合（AppTest `proto.expanded=False`，五頁 `harness` 實測）。
- 頁面全部用 `st.markdown(unsafe_allow_html)` 自繪 HTML 卡片。`page.py` 裡**沒有** `st.error/warning/info/metric/dataframe/plotly`（讀碼：靜態 grep）。

| 頁 | 提問句（副標） | 首屏順序與元件（390 寬實測：塊頂端 y 座標，首屏＝y<844） | 入口函式 |
|---|---|---|---|
| 市場總覽 mkt | 現在的市場環境，和我上次看的時候比，變了哪裡 | 頁名 → 副標 → `層 1 結論` → MKT-0「環境結論燈」(y266；只有燈色＋文字＋右側代號) → `層 2 核心卡` → MKT-1 風險情緒卡(y394：波動度指數、高收益信用利差各帶「T2 延遲 3 日」徽章＋「⬜ 不適用：尚未設定觀察窗」) → MKT-2(y710) → MKT-3(y1006) → 層 3：MKT-4 觀察窗輸入、MKT-5 指標清單(expander) → 層 4：MKT-6 明細、MKT-7 新鮮度與來源(expander) | `ui_v2/mkt/page.py::render`:481；燈 `_render_light`:162；卡 `_render_card`:208；MKT-4 `_render_mkt4`:335；MKT-5 :383；MKT-6 :417；MKT-7 :441 |
| 持倉體檢 hld | 我手上這些基金，哪幾檔偏離了我自己設的門檻 | 頁名 → 副標 → `層 1` → HLD-0「體檢結論燈」(y270，⚠/⛔/⬜ ＋「狀態：…」) → 兩行說明（「哪幾檔…看下面的偏離提示卡」「黃燈說的是…」） → `層 2` → HLD-1 偏離提示卡(y452，HTML 表：基金名/實際值/門檻值/差額) → HLD-2 績效與風險(y746) → HLD-3 配息與本金(y1228) → 層 3：HLD-4 區間與門檻、HLD-5 單檔展開 → 層 4：HLD-6/7/8 | `ui_v2/hld/page.py::render`:882；燈 `_render_lamp`:267；卡 `_card_shell`:289、`_render_hld1`:304、`_render_core_card`:351；HLD-4 `_render_hld4`:513；HLD-5 :592；HLD-6 :656；HLD-7 :721；HLD-8 :741 |
| 標的探索 exp | 符合我輸入條件的基金有哪些，它們彼此差在哪 | 頁名 → 副標 → `層 1` → EXP-0「篩選結果結論列」(y260) → 3 行說明，其中 1 行是「⚠ 44 的來源欄只授權讀列數…」 → `層 2` → EXP-1 條件輸入卡(y593：欄位/比較方向/數值 三個 text_input ＋ 清除/新增條件/存檔) → **EXP-2 候選清單在 y1341，不在首屏** → EXP-3 並排對照在 y4358 | `ui_v2/exp/page.py::_render_live`:950；EXP-0 `_render_exp0`:301；EXP-1 `_render_exp1_live`:632；EXP-2 `_render_exp2`:349；EXP-3 :405；EXP-4 :440/:662；EXP-5 :477；EXP-6 :685；EXP-7 :701 |
| 資產配置 alo | 我目前的分布，和我自己寫下的目標，差多少 | 頁名 → 副標 → `層 1` → ALO-0「差距結論燈」(y267) → 「⚠ 44 沒有寫燈上的差距帶不帶正負號…」 → `層 2` → 「以下依序：目標 → 對照 → 試算」 → ALO-1 目標輸入卡(y469，每類別 2 個 text_input，3 類＋容許帶共 7 個) → **ALO-2 目標對照在 y1195，不在首屏** → ALO-3 試算(y1444) | `ui_v2/alo/page.py::render`:527；ALO-0 `_render_alo0`:282；ALO-1 :297；ALO-2 :323；ALO-3 :340；ALO-4 :375；ALO-5 :425；ALO-6 :444；ALO-7 :469 |
| 設定與診斷 set | 畫面上的數字現在可不可信，不可信是卡在哪一段 | 頁名 → 副標 → `層 1` → SET-0「可信度結論燈」(y312) → 3 行說明 → `層 2` → SET-1 資料新鮮度卡(y519，表：資料類/最近取得時間/距今日數（days_calendar）/與上限比較) → SET-2 來源健康(y913) → SET-3 規則參數卡(y1103，18 個 raw 鍵名表) | `ui_v2/set/page.py::render`:471；SET-0 `_render_set0`:257；SET-1 :273；SET-2 :293；SET-3 :311；SET-4 :335；SET-5 :376；SET-6 :418；SET-7 :432 |

**每塊的「回答什麼問題」**：寫在每塊的 `answers` 欄，畫成卡內 caption 或小字（實測：harness dump 各塊都有，例：MKT-1「市場的緊張程度，跟我選的那個起點比，是拉開了還是收回去了」）。

**頁高（390 寬實測，單位＝螢幕數，844px 一屏）**：

| 頁 | 全部收合 | 全部展開 |
|---|---|---|
| mkt | 2.3 | 3.8 |
| hld | 2.9 | 7.0 |
| exp | 6.3 | 8.4 |
| alo | 3.1 | 5.4 |
| set | 3.6 | 12.2 |

---

## B. Data Health 重複 inventory

**各頁有哪些 data-health 載體（讀碼＋實測）**：

- **mkt**
  - MKT-0 燈：只讀三卡的狀態，是資料完整度（`mkt/logic.py::conclusion_light`:785），但標題叫「環境結論燈」。
  - 每個值都帶「T1/T2 延遲 N 日」徽章（`logic` :512-528）。
  - 失敗時每張卡各掛一顆停用的「重新取數」，help 寫冷卻秒數（`page.py` :226-232）。
  - MKT-4/MKT-5 各自寫一次「⛔ 設定讀不到：…」。
  - MKT-6、MKT-7 的摘要與內文再寫一次「設定讀不到，暫時列出全部指標」。
  - MKT-7 是新鮮度與來源表。
- **hld**
  - HLD-0 燈。
  - 每張核心卡各自的「⛔ 取數失敗：…」＋「訊息原文照印，不改寫成安撫語句。」（`hld/logic.py` :420/:439）。
  - 每檔「延遲 N 日」徽章、「淨值取自預存序列…」備註（`hld/live.py` :282-297、:336-420）。
  - HLD-1 卡尾「N 檔淨值取自預存序列」。
  - HLD-4/5/8 的 expander 標題與內文再各寫一次。
- **exp**
  - EXP-0 逐塊列出失敗。
  - 每張卡開頭「`user_setting：⛔…`」「`fund_profile：⛔…`」（`_error_lines`:242、`_fetch_fail_lines`:253）。
  - 每張卡尾有佔位符「〔來源層級〕 〔新鮮度〕」（harness 實測 3 處）。
  - EXP-2 每一格都附來源標籤（MoneyDJ、`FundClear:GetFundNAV`…）。
- **alo**
  - ALO-0 燈，每張卡各寫一次錯誤行。
  - ALO-4 的摘要。
  - **本頁沒有淨值新鮮度的位置**：過期、預存、推估的淨值直接不納入（`alo/live.py` :340-360；`alo/logic.py` :238 的 `ALO-GAP-過期淨值不納入`）。
- **set**：整頁就是 data health。
  - SET-0、SET-1 新鮮度、SET-2 來源健康、SET-6 取數紀錄。
  - 說明句「取數紀錄只記從 set 頁觸發的取數；市場總覽頁開頁時自己的取數不記在這裡。」同頁出現 **3 次**（實測：`harness_set`、`unconf_set` 各 3）。

**同一錯誤在同一頁重複次數**（實測：`unconf_*` dump，整頁含 expander 內文／標題；按鈕 help 另計）：

| 頁 | 同一句錯誤 | 次數 | 出現位置 |
|---|---|---|---|
| hld | 「未設定保單試算表 ID（POLICY_SHEET_ID），不讀取」 | **6** | HLD-1 卡、HLD-3 卡、HLD-5 標題＋內文、HLD-8 標題＋內文 |
| hld | 「未設定試算表 ID，暫停寫入」 | **3** | HLD-2 卡、HLD-4 標題＋內文 |
| hld | 「訊息原文照印，不改寫成安撫語句。」 | **6** | 跟在每一處錯誤後面 |
| hld | 「取數失敗」字樣 | 13 | — |
| exp | 「未設定試算表 ID，暫停寫入」 | **6** | EXP-0、EXP-1、EXP-2、EXP-4、EXP-5、EXP-7 |
| exp | 「選股池未設定雲端來源（沒有服務帳戶憑證）…」 | **5** | EXP-0、EXP-2、EXP-3、EXP-6、EXP-7 |
| exp | 「取數失敗」字樣 | 18 | — |
| alo | 「未設定保單試算表 ID（POLICY_SHEET_ID）」 | **5** | ALO-0、ALO-2、ALO-3、ALO-4、ALO-6 |
| alo | 「未設定試算表 ID，暫停寫入」 | **2** | ALO-1、ALO-7 |
| set | 「未設定試算表 ID，暫停寫入」 | **9**（其中 1 次在 help） | SET-0、SET-1 表內 2 格＋卡尾、SET-2、SET-3、SET-4 內文＋help、SET-6 |
| mkt | 「未設定 FRED_API_KEY」 | 2 | MKT-1、MKT-3 |
| mkt | 「未設定試算表 ID，暫停寫入」 | 2 | MKT-4、MKT-5 |
| mkt | 「設定讀不到」 | 1 次錯誤行 ＋ 4 次衍生句 ＋ 6 次 help | 4 個勾選框 help、2 顆存檔鈕 help |
| mkt | 「來源冷卻中：query1.finance.yahoo.com，約剩 60 秒」 | 3（全在 help） | 3 張卡各一顆「重新取數」 |

- **跨頁重複（實測）**：同一個「未設定試算表 ID」，五頁全部各自畫一輪。所以使用者每換一頁，都會再看到 2～9 次同一句。
- **用字錯置（讀碼＋實測）**：`repositories/settings_sheet_repository.py:125` 的 `NOT_CONFIGURED_MESSAGE = "未設定試算表 ID，暫停寫入"` 被原樣拿來當**讀取**失敗訊息（例：HLD-2「績效與風險卡」在 `unconf_hld` 顯示「⛔ 取數失敗：未設定試算表 ID，暫停寫入」）。這是讀取情境，卻寫「暫停寫入」。

---

## C. Engineering jargon inventory

分類計數由 `tools/analyze.py` 掃 dump 得出（實測）。「可見」＝不在 expander 內，首屏或卡片上就看得到。「收合」＝在 expander 標題或內文。注意：計數裡的 `text_input`／`number_input` 等是 dump 自己的標籤，**不是**畫面字串，已排除。

| 類別 | 一般畫面可見（不在 expander） | 收合在 expander（標題算半可見） | 證據 |
|---|---|---|---|
| **Block ID**（MKT-0、HLD-3…） | 五頁全部：燈右側「MKT-0　環境結論燈」、每張卡頭「MKT-1」等。內文也有：「本塊不自取數：只讀 EXP-2 的列數與 EXP-1 的條件列數」、「本燈只讀 SET-1 的逾期筆數與 SET-2 的失敗來源數」、「第三個值「最大回撤」移到層 4 的 HLD-8」、「⬜ 資料未備：HLD-1 與 HLD-2 與 HLD-3 與 HLD-8 尚無資料」（HLD-7） | 每個 expander 標題都是「`<ID>　<名稱>　—　<摘要>`」（mkt:336/384/418/442、hld:379、exp:435、alo:370、set:330）。SET-4 每個鍵下有「改這個鍵會影響：ALO-1、ALO-7」。SET-7 欄位對照表內 152～180 個 ID | 卡頭：mkt:171/216、hld:277/293、exp:279/308、alo:274/289、set:239/264 |
| **「層 1／層 2…」** | 五頁各 4 個層標籤（mkt:560/563/571/582、hld:958-983、exp:908-937/980-1010、alo:603-618、set:517-532）。hld/exp 內文另有「移到層 4 的 HLD-8」、「本塊在層 4，44 的層 4 不放使用者輸入」 | — | 實測 |
| **POLICY_SHEET_ID／FRED_API_KEY**（secret 鍵名） | hld 可見 2 處；alo 3 處；mkt「未設定 FRED_API_KEY」2 處（在 MKT-1/MKT-3 主值位置，1.32rem 粗紅字） | hld：expander 標題 2 ＋內文 2；alo：內文 2 | 文字由 L1 帶上來：`repositories/policy_supplement_repository.py:86` |
| **SETTINGS_SHEET_ID** | 畫面字串未出現（訊息寫的是「未設定試算表 ID」，沒有鍵名） | — | 實測：dump 0 命中 |
| **raw schema／設定鍵** | <ul><li>exp：「依 fund_code 字面值排列」、表頭 `fund_code`、`ccy`、「最近淨值（nav_orig_ccy，原幣）」、「可選欄位取自 fund_profile 的欄位名清單：fund_code、fund_name、ccy、inception_on、dividend_policy、mgmt_fee_rate_pct、fetched_at」；EXP-1「欄位」text_input 要使用者直接打 `fund_code`</li><li>hld：HLD-1「依 fund_code 字面值排列」</li><li>alo：輸入欄標籤「目標比重 weight_ratio」「金額 amount_twd」</li><li>set：SET-1 欄名「距今日數（days_calendar）」、「⬜ 未設定（set_max_age_days）」；SET-3 18 個 raw 鍵（`alo_basis`…）及「型別（value_kind）」</li><li>mkt（`unconf`）：MKT-7 指標鍵 `credit_spread_pct` 等</li></ul> | <ul><li>mkt：MKT-4「觀察窗長度（days_calendar）」；MKT-5 勾選框標籤就是 raw 鍵 `vol_index`、`credit_spread_pct`…（mkt:387）；MKT-7 第一欄 `indicator_key`（mkt:450）；「market_indicator 尚無資料」</li><li>exp：EXP-4 勾選「ccy」、`user_setting`、`exp_watchlist`、`action_kind`</li><li>alo：ALO-4 radio「成本（cost_twd）」「美元依 fx_twd_per_usd 換算」、ALO-7 `alo_target_weights`</li><li>hld：HLD-6「nav 與 dividend 尚無資料」</li><li>set：SET-4 每欄標籤「`alo_basis（list）`」等 18 個、SET-6「依 started_at」、SET-7 整張 `holding.fund_code` 表</li></ul> | jargon_counts.txt |
| **Python／實作名、raw 錯誤原文** | mkt `unconf`：MKT-1 主值顯示「⛔ 取數失敗：**fetch_url returned None: ^VIX (kind=unreachable)**」（1 處，粗紅字，390 寬折 2 行；截圖 `m390/unconf_mkt_390_first.png`）。來源 `repositories/macro/fred.py:290`、`fred_vintage.py:95` 同型 | — | 實測 |
| **例外型別名** | hld 正式模式 load 失敗時整頁顯示「⛔ 取數失敗：**RuntimeError**：<訊息>」（`hld/page.py::_live_error_line`:805、`_render_live_error`:830；實測注入 RuntimeError）。alo `_error_line`:513 同型，但只包 `ValueError` | — | 實測／讀碼 |
| **raw exception／stack** | **mkt、exp、alo、set** 的 `load_live()` 沒包 try（mkt:503、exp:952、alo:558、set:494）。注入 `RuntimeError` 後四頁都出現 Streamlit `st.exception` 元素（AppTest `exceptions=1`，實測），訊息原文含我放進去的伺服器路徑。`.streamlit/config.toml` 沒設 `showErrorDetails`，所以本機會顯示完整 traceback（推論：Streamlit 預設值；Cloud 端行為未驗）。hld 有 try，不會露 stack。⚠ 「`source.load_live` 實際會拋哪些未包裝例外」沒有逐一驗證 | — | 實測（注入）／推論 |
| **規格／內部記號**：`G1†/G2†/G3†`、「44」、「草稿」、「決策者是 AI 總管」 | <ul><li>`G#†` 可見：exp 13、hld 4、alo 4、mkt 1、set 2</li><li>「44」可見：exp 4、alo 2、set 4</li><li>「⚠ 44 …」開頭的整句規格落差說明：exp 7、alo 4、set 1（例 EXP-0 首屏「⚠ 44 的來源欄只授權讀列數…」、ALO-0 首屏「⚠ 44 沒有寫燈上的差距帶不帶正負號…」）</li><li>「〔來源層級〕〔新鮮度〕」佔位字 exp 3</li><li>「紅線說明區：…」mkt 2</li><li>「訊息原文照印，不改寫成安撫語句。」hld 最多 6、set 1</li></ul> | exp expander 內 14 處「44」；EXP-4 有一整段寫「…那一句 44 自己標的決策者是「AI 總管，本輪派工指定」，不是客戶裁示…」 | 實測 |
| **來源實作名／層級** | <ul><li>exp：EXP-2 每格附 `MoneyDJ`、`MoneyDJ+TDCC`、`FundClear:GetFundNAV`（harness 74 處）</li><li>mkt：「T1/T2 延遲 N 日」（6 處）</li><li>exp：「〔來源層級〕」</li></ul> | mkt：MKT-7「來源層級」欄 | 實測 |
| **示範模式專屬** | mkt：「user_setting 已存檔，updated_at ＝ …（本輪的 user_setting 替身是一個 in-memory dict）」（mkt:375-378，`load_live is None` 才畫） | — | 讀碼 |

- **390 首屏（y<844）實測帶到的工程字樣**：
  - mkt：`MKT-0`、`MKT-1`、`MKT-2`、`T1`/`T2`、「層 1」「層 2」；`unconf` 下另有 `fetch_url returned None`、`FRED_API_KEY`
  - hld：`HLD-0`、`HLD-1`、`HLD-2`、`G2†`、「依 f[und_code]…」
  - exp：`EXP-0`、`EXP-1`、`EXP-2`（說明句）、「⚠ 44…」、`G1†`，以及 text_input 值 `fund_code`
  - alo：`ALO-0`、`ALO-2`、「⚠ 44…」、`weight_ratio`
  - set：`SET-0`、`SET-1`、`SET-2`、`days_calendar`、`set_max_age_days`

---

## D. Controls／CTA inventory

元件數量由 `tools/controls.py` 從 dump 統計（實測）。「頂層」＝不在 expander 內；「exp」＝在 expander 內。括號裡是其中停用的數量。

| 頁（模式） | button | checkbox | text_input／area | 其他 | 主要 CTA 觀察 |
|---|---|---|---|---|---|
| mkt harness | exp 3（3 停用） | exp 7 | — | number_input 1、date_input 1 | 套用（正式模式恆停用：「正式結果只讀已存設定」）、存檔 ×2（MKT-4、MKT-5 各一）。harness 沒傳 save_live，所以也停用 |
| mkt unconf | 頂層 3（3 停用）＋ exp 3（3 停用） | exp 4（4 停用） | — | 同上 | **每張核心卡各掛一顆「重新取數」**（mkt:226-232），正式版永遠停用（`mkt/live.py:37 RETRY_DISABLED_REASON="重新取數尚未接上"`，或顯示冷卻秒數）＝ 3 顆看得到、按不了的按鈕 |
| hld harness | exp 8（1 停用） | — | exp 8 | — | 套用（停用）、存檔、新增一列、清除這一列 ×N 門檻列、**展開 ×N 檔**（HLD-5，每檔一顆，hld:610）。「比較方向」是自由文字 text_input（hld:519/532），不是選單 |
| exp harness | 頂層 3 ＋ exp 2（1 停用） | **頂層 20** ＋ exp 5 | 頂層 3 | selectbox 1 | **checkbox 海**：EXP-2 每檔一列 `[代碼][對照][觀察清單]`，10 檔 ＝ 20 個勾選框（exp:375/383）。390 寬時每列被 CSS 堆成 3 行（推論＋頁高 6.3 屏實測）。存檔分成 EXP-1、EXP-4 兩顆，另有「加入觀察清單」。EXP-1「欄位」要使用者打 raw 欄名 |
| alo harness | 頂層 2（2 停用）＋ exp 2（1 停用） | — | **頂層 11** ＋ exp 3 | radio 1、download 1 | 存檔 ×3（ALO-1、ALO-3、ALO-4）、前往 Sheets、匯出。ALO-3 存檔恆停用（「存檔寫入端尚未接上，這一輪只讀不寫」）。⚠ `unconf_alo`：ALO-1、ALO-4 的存檔在設定試算表根本沒設時**仍是啟用**（實測 disabled=False）。mkt、exp、set 同情境都停用 |
| set harness | exp 2（1 停用） | — | exp 18（text_input 8、text_area 10） | radio 1 | SET-4 一個存檔管 18 個欄位；SET-5 radio ＋ 重新取數（沒選層級時停用） |

- **st.form**：`ui_v2` 全部 0 處（讀碼：grep `st\.(form|fragment|spinner|status|progress)` 只命中 `set/page.py:397 st.empty`）。所以每次改一個欄位都會整頁重跑，正式模式每次重跑都重呼叫 `load_live()`。L1 有 TTL 快取（`app_preview.py` 檔頭、`49` §4.4），**每次重跑都打外部來源**這件事沒有實測（推論：命中快取）。
- **每頁主要 CTA 個數**（讀碼）：全部是次要樣式，沒有 `type="primary"`。
  - mkt：存檔 ×2（＋恆停用的套用、3 顆停用的重新取數）
  - hld：存檔 ×1（＋停用的套用）
  - exp：存檔 ×2 ＋ 加入觀察清單
  - alo：存檔 ×3（其中 1 顆恆停用）＋ 匯出
  - set：存檔 ×1 ＋ 重新取數 ×1
- **「看得到但永遠按不了」的按鈕**（實測，正式模式）：mkt 套用、mkt 3 顆重新取數、hld 套用、alo ALO-3 存檔。

---

## E. Error／空值／未設定／loading 四態

| 狀態 | 呈現方式（實測／讀碼） | 一致性 |
|---|---|---|
| **錯誤** | 統一模板「⛔ 取數失敗：<原文>」（`44` 5.5）。hld 每處後面再接「訊息原文照印，不改寫成安撫語句。」。顏色：hld、exp、mkt、set 是紅；**alo 的 ALO-0 燈在取數失敗時用灰色**，只把圖示換成 ⛔（`alo/logic.py`:988-990「ALO-GAP-無紅燈」、:463）。mkt 的錯誤寫在主值位置，用大字號 | 四頁紅、alo 灰：**不一致** |
| **資料未備／空值** | 「⬜ 資料未備：<鍵> 尚無資料」或「⬜ 資料未備 原因：…」，灰。<鍵> 是 raw 表名（`market_indicator`、`nav 與 dividend`） | 五頁同模板 |
| **不適用（業務例外）** | 「⬜ 不適用：<原因>」，2026-10-16 起改灰（各 logic `_TONE_BY_STATE`） | 與「資料未備」同一個 ⬜ 加灰 |
| **未設定（使用者還沒輸入）** | 「尚未設定門檻」「尚未設定目標」「尚未選定任何指標，請在指標清單勾選並存檔」（灰）。SET「⬜ 未設定（set_max_age_days）」 | 與資料未備同色同圖示，只能靠文字區分 |
| **loading** | **沒有 spinner 或骨架**。只有 SET-5 按下重新取數後畫「取數中」並停用按鈕（`set/page.py::_live_refetch`:394）。初次載入只有 Streamlit 內建的右上角 running 指示（推論） | — |

- **錯誤有沒有告訴使用者下一步**：已知有給下一步的只有這幾處（讀碼 grep「請到／請按／請確認／請在」）：
  - hld 存檔被擋時的 help「…請到設定與診斷頁確認」（`hld/live.py:65`）
  - set 存檔 403/404 提示「服務帳戶可能只有檢視權限，需要編輯者」「請確認試算表 ID，以及已分享給服務帳戶」（`set/live.py:42-43`）
  - mkt「尚未選定任何指標，請在指標清單勾選並存檔」（`mkt/logic.py:239`）
  - 「套用」help「請按「存檔」…」

  其餘所有「⛔ 取數失敗：未設定…」都只說「什麼壞了」，沒說「去哪設」（例：沒指向設定與診斷或 Secrets）。而且 set 頁自己也沒有一塊叫「設定 secrets」的引導。上面是 grep 規則下的已知清單，不宣稱窮舉。
- **raw error 直接露出**：
  - mkt L1 原文 `fetch_url returned None: ^VIX (kind=unreachable)`（實測）
  - hld、alo 的例外型別名（實測／讀碼）
  - 四頁未攔的例外走 `st.exception`（實測，見 C）

---

## H. 390px mobile problem inventory

- **CSS 位置（讀碼）**：五頁的 CSS 和 media query 都在各頁 `page.py::_grid_css/_base_css`（mkt:36/68、hld:38/68、exp:74/119、alo:54/83、set:49/76）。`theme.py` 只放色票；`exp/theme.py:98 SOURCE_TAG_CSS` 有一小段 CSS。
- **欄寬規則（讀碼）**：全域規則讓每一個 `stHorizontalBlock` 的子欄都 `flex:1 1 100%`，只有層 2、層 3 的標記之後才以 `@media (min-width)` 改成多欄。斷點來自 `logic.layer_columns`：≥1280 三欄、769–1279 兩欄、≤768 一欄。**所以 390 寬下全部單欄**，連塊內巢狀的 `st.columns` 也一樣，例如 exp 每檔的「代碼／對照／觀察清單」三欄（推論）。
- **既有守衛（實測）**：`tests/ui_v2/test_live_390_page.py` 在本機實跑 **20 passed**（要指定 `UI_V2_CHROMIUM`）。五頁正式模式在 390 都不會整頁橫捲、燈在首屏、沒有 stCode。但它只跑 harness 資料，沒跑「未設定」或「錯誤」情境。
- **已知問題（實測，390×844）**：
  1. **EXP-2 候選表預設可見、容器內橫捲**：容器 358px、內容 674px。已登記在 `_DEFAULT_VISIBLE_INNER_SCROLL`（客戶 2026-10-16 暫接受）。表頭還帶 raw 欄名（`fund_code`、`ccy`、`nav_orig_ccy`）、每格附來源標籤。
  2. **expander 內寬表**：MKT-6/7 是 `.mkt-scroll` 加 `white-space:nowrap`（mkt:120-126），324 對 352/476px。HLD-6/7/8 是 `.hld-scroll`，`nowrap` 加 `max-height:26rem` 的雙向捲動（hld:137-143），324 對 382～954px。HLD-6 一次把 **1020 列**淨值畫成 HTML 表（harness）。
  3. **頁很長**：exp 收合狀態 6.3 屏（EXP-2 在 y1341、EXP-3 在 y4358），set 全展開 12.2 屏，hld 全展開 7 屏。
  4. **核心結果被輸入表單擠出首屏**：exp 首屏是 EXP-0 ＋ 3 行說明 ＋ EXP-1 表單，候選清單不在首屏。alo 首屏是 ALO-1 的 7 個 text_input，對照表 ALO-2 在 y1195。
  5. **燈的右側「代號＋標題」佔版面**：`.mkt-light-code { margin-left:auto }`（mkt:92）讓主文案在 390 被擠成 2～3 行（截圖 `m390/unconf_mkt_390_first.png`、`harness_exp_390_first.png`）。
  6. **長原文字串用大字號**：MKT 主值 1.32rem 粗體顯示 `fetch_url returned None: ^VIX (kind=unreachable)`，佔 2 行。
  7. **SET-4**：18 個輸入欄連續排列（expander 內）。
- **不適用**：ui_v2 沒有任何圖表（讀碼：page.py 無 plotly、chart），所以「圖表沒有文字結論」這一項不存在。

---

## 其他

### 投資燈與資料／系統狀態共用同一套符號（實測＋讀碼）

五頁共用 `TONE_HEX {中性, 灰, 黃, 紅}`（各 `theme.py`），同一個「黃 #e3b341 ＋ ⚠」在不同頁意思不同：

| 頁 | 黃燈意思 | 依據 |
|---|---|---|
| HLD-0 | 「⚠ 狀態：要多看一眼 有 2 檔超出你設定的門檻」：**投資偏離** | `hld/logic.py`:1834-1845 |
| ALO-0 | 「⚠ 要多看一眼 核心 與目標差 6.0 個百分點」：**配置偏離** | — |
| MKT-0 | 任一卡「資料未備」或「業務例外」就變黃：**資料完整度** | `mkt/logic.py`:785-830 依 `44` :310 |
| SET-0 | 「⚠ 狀態：有逾期」：**資料新鮮度** | `set/logic.py`:827-831 |
| SET 徽章 | 「推估／修正過／部分缺／未定義」：黃 | `set/logic.py`:211-219 |
| EXP-0 | **方向相反**：「◧ 有檔符合」是黃、「⬜ 條件未設／零檔符合」是灰 | `exp/logic.py`:1954-1962；程式註解自承「本塊的燈與前四枚燈方向相反」 |

- **同一顆燈上混兩種語意**：HLD-0 黃＝投資偏離、紅＝取數失敗。畫面上靠兩行說明句各自澄清：「黃燈說的是「要不要多看一眼」，不是「該調整了」。」「紅燈說的是「這一頁的數字能不能照著讀」，不是「你的持倉出事了」。」（實測）

### 「無法判定」與「正常」能不能區分（實測：`tools/lamps.py` 跑 fixtures 各情境）

- **HLD-0**：以下全部是同一個「⬜ 狀態：中性」加灰 #8b949e，只能靠後面那句話分辨：
  - `nothr`「尚未設定門檻」
  - `empty`「尚未建立任何持倉」
  - `bizexc`「⬜ 不適用」（畫面上連出兩個 ⬜）
  - HLD-1 資料未備時（讀碼 :1813-1826）
  - 真正正常「無偏離項」（讀碼 :1847-1855）
  - 另有一條 fallback：卡片不全是 ok 卻仍寫「無偏離項」（:1857-1871）
- **ALO-0**：也全部是「⬜ 狀態：中性」，例如：
  - 正常「各類別皆在容許帶內」（`inband`）
  - 「尚未建立任何持倉」（`first`、`noholding`）
  - 「尚未設定目標」（`notarget`）
  - 「尚未設定容許帶」（`notol`）
  - 「⬜ 不適用：尚未選定比重基準」（`nobasis`）
  - 「⬜ 資料未備：缺換算匯率 fx_twd_per_usd」（`nofx`）
- **MKT-0**：「三張卡的資料齊」和「本頁三張卡皆未取到資料」都是灰（`mkt/logic.py`:790-798）。
- **可區分的對照例**：
  - SET-0 用不同的狀態字：「⬜ 狀態：無逾期、無失敗來源」對「⬜ 狀態：尚不足以判定」（實測／讀碼 `set/logic.py`:827-870）。
  - EXP-0 在文字後接「；另有 M 檔無法判定」，EXP-7 有「無法判定」欄（讀碼 `exp/logic.py`:1900-1930）。

### stale／last-known-good 怎麼標（讀碼＋實測）

- **hld**：
  - 淨值日距今 ≤10 天：中性徽章「當日／延遲 N 日」（`hld/live.py`:282-283）。
  - >10 天：徽章改「⬜ 資料未備」，並附「最近一筆淨值 {day}，已超過 10 日」，該檔不再進任何計算（:291-295，門檻 `ui_v2/thresholds.py::NAV_NOT_READY_DAYS=10`）。
  - **last-known-good**：「淨值取自預存序列，不是本次取得；最近一筆 {day}」，中性（:286-287）。HLD-7 輸入欄尾巴加「 · 預存序列」，HLD-1 卡尾寫「本卡所列的檔中，N 檔的淨值取自預存序列，逐檔見 HLD-6」（:296-297、:500-520）。
  - L2 的 `stale` 旗標**不讀**，只驗形狀（:336-345 docstring）。
- **alo**：沒有新鮮度位置。`cache_fallback`、`stale`、`is_estimated`、超過 10 天的檔一律不納入市值，畫「⬜ 資料未備：最近淨值已超過 10 日」或「nav 尚無資料」（`alo/live.py`:340-360；`alo/logic.py`:238）。**last-known-good 不顯示**。
- **mkt**：每值附「T# 延遲 N 日」。刻意不加「舊資料」字樣（`mkt/live.py`:18），快取命中與即時取得在畫面上無法區分（推論）。
- **exp**：每格附來源層級與新鮮度標籤；母體延遲沿用原讀取時間（`exp/live.py`:905）。
- **set**：SET-1 表「最近取得時間／距今日數／與上限比較」，上限 `set_max_age_days` 由使用者設定，沒設時整列 ⬜。

### 跨頁共用 context（讀碼）

- **沒有跨頁共用的投資組合、選定基金或期間**：
  - 期間各頁各存一組 user_setting 鍵：mkt 是 `mkt_window_days`、`mkt_baseline_date`；hld 是 `hld_window_start`、`hld_window_end`。
  - 選定基金：exp 的「對照」勾選與 hld 的 `hld5_open_fund` 都是頁內狀態。
- **widget 狀態一頁一份**：`app_preview.py` 檔頭有實測說明，streamlit 1.59.2 的 widget id 含頁面 hash，離開頁面就清掉。
- **`app_preview.py::_on_page` 換頁時主動 pop 的 key**（`_PAGE_STATE_TO_DROP`）：
  - `_alo_live_save_errors`、`_alo_live_pending_inputs`
  - `_mkt_applied`、`_mkt_save_results`
  - `_exp_save_results`、`_exp_live_rules`、`_exp_live_seeded_fp`
  - `_hld_save_results`
- **各頁自己寫進 `st.session_state` 的 key 清單**（grep 所得）：

| 頁 | key |
|---|---|
| mkt | `_mkt_applied`、`_user_setting`（示範模式）、`mkt4_days`、`mkt4_baseline`、`mkt5_<指標鍵>`、`_mkt_save_results` |
| hld | `_hld_applied`、`_hld4_keep_open`、`hld5_open_fund`、`_hld_save_results`、門檻列 widget key |
| exp | `_exp_live_rules`、`_exp_live_rule_seq`、`_exp_save_results`、`exp4live_sort`、`_exp_live_seeded_fp`、`_exp_live_seeded_settings`、`_col_key()`、`_rule_key()`、`_widget_key()` |
| alo | `_alo_live_save_errors`、`_alo_live_pending_inputs`、`{prefix}_{field}` |
| set | `_set_live_save_results`、`_set_live_refetch_result`、`{key}_{field}` |
| preview | `_preview_last_page` |

- 各頁 source 唯讀 `gsheet_tokens`、`custom_oauth_cfg`（只用於遮蔽）。這兩個鍵只有舊 UI（`ui/helpers/io/oauth_state.py`）會寫，預覽站永遠讀不到（推論）。

### 現有測試

- **`tests/ui_v2/`：44 檔**
  - 每頁 `*_logic`、`*_page`、`*_live_logic`、`*_live_page`、`*_source`
  - `test_preview_entry.py`、`test_preview_page.py`
  - `test_live_390_page.py`
  - `test_ui_v2_lane_guards.py`、`test_ui_v2_live_import_guard.py`
  - hld 另有 `assemble`、`freshness`、`settings`、`error_page`、`r3_rulings`、`read_failure`
  - `test_alo_r3_conflict_page.py`、`test_mkt_settings_*`、`test_exp_live_wiring_logic.py`
  - helper：`_exp_live_stub`、`_exp_wired_fixture`、`_set_live_harness`、`_ui_v2_chromium`
- **相關但屬 L2、不測 UI**：`tests/test_v2_tables_*.py`（19 檔）、`tests/test_v2_l1_error_sidecars.py`。
- **AppTest**：`tests/ui_v2` 有 18 檔用 AppTest。
- **390／窄寬測試**：
  - `test_live_390_page.py`：390 寬，正式模式五頁 ＋ 示範模式；不橫捲、燈在首屏、沒有 stCode；本機 20 passed。
  - `test_alo_page.py:392`：375 寬，alo 各情境不橫捲。
  - 各頁 `*_logic` 測 `layer_columns` 斷點（1280／…／375／374）。
- **「工程 ID、jargon 不可見」的測試：沒找到**。依據是以 `grep -E 'not in .*(MKT|HLD|EXP|ALO|SET)-|POLICY_SHEET_ID.*not in|…'` 掃 `tests/ui_v2`；`POLICY_SHEET_ID` 在測試裡只用於清環境變數。已有的禁字表只管投資建議用語：`FORBIDDEN_BUTTON_WORDS`、`FORBIDDEN_ADVICE_WORDS`、`FORBIDDEN_ARROWS`（`alo/logic.py`:296-313、`mkt/logic.py`:60-63）。
  - 不宣稱窮舉：可能有其他寫法的斷言沒被這條 grep 掃到。

### 未涵蓋範圍（誠實揭露）

- 沒跑 `unconf` 以外的真實失敗組合：設定試算表有設但 403/404、選股池有設但淨值失敗、FRED 有 key 但逾時等。
- `source.load_live` 實際會拋出哪些未包裝的例外，沒有逐一驗證。
- 沒驗 Streamlit Cloud 的 `showErrorDetails` 實際行為。
- 「每次重跑都命中 L1 快取」沒有實測。
- 4 個 hld 黃金雜湊測試失敗的原因沒查。
- 本報告由單組產出，沒有第二組獨立驗證（§-2 規則 6）。所有計數只對本次 dump 的情境成立。
