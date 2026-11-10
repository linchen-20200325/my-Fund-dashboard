# FRED 增量演算法、Parquet 版本相容性與快取完整性：純離線驗證與最小修復方案（2026-11-10）

> **性質聲明（先讀）**
>
> - 本文是**離線驗證與設計**，**不是**任何正式修復的核准（`DEC-2026-11-10-05`）。不修改正式 `data_cache`／`metadata.json`／workflow／UI／production fetcher／金融公式；無外部抓取；不解除 `ui_v2`／`services` 凍結；不切換 New UI 資料來源；不變更 FX Gate（`FX_OBS_DATE_RULE_VERIFIED` 維持 `False`）、Eligibility、OneBrain。
> - 不用推論補資料、缺值不填 0、**不把快取當已驗證**。「能讀」不等於「可用於正式 UI」；「合成世界機制成立」不等於「對真實 FRED 成立」。
> - 標籤：**機制成立（合成）**＝本批離線測試在自設合成世界下重現；**真實資料異常**＝直接觀察 `data_cache` 快取副本（含 git 歷史版本）；**推論**＝由上述推得、未直接驗證；**NOT VERIFIED**＝真實 FRED 回傳、發布延遲真值、vintage 修訂、Actions 執行日誌、Streamlit Cloud 行為。
> - 來源：三份單組離線草稿（B1 增量演算法、B2 Parquet 版本相容、B3 資料完整性），由專案 AI 整合並自行抽查 12 項關鍵宣稱（§7.1），抽查之外**沒有第二組獨立驗證**。客戶授權經總管轉達，無逐字存檔。
> - 本文刻意不寫程式行號；定位一律用「檔案＋符號」。量測基準：`origin/main` 的 `ab821fd0`，快取內容為 `8ca33547`（`metadata.updated_at` 為 2026-11-08）；模擬日固定常數 2026-11-10。
> - 引用不重做：`actions_cache_newui_wiring_gap_2026_11_10.md`、`cache_quality_check_a1_report_2026_11_10.md`、`cache_quality_intraday_freeze_study_2026_11_10.md`、`secrets_recovery_verification_2026_11_10.md`；`DEC-2026-11-09-10`（Q1–Q5）、`DEC-2026-11-10-01`～`-04`。

---

## 0. 推薦結論與最小 Decision Gate（推薦在前；**未經客戶裁示，專案 AI 讀法，可被推翻**）

**一句話**：快取今天**不能**當已驗證資料；缺口的根因有一組在合成世界下可重現的機制（共同增量起點），且有三類真實快取觀察與它一致，但**真實成因未證實**（NOT VERIFIED）。推薦的最小路線是：**先看見、再修**——

1. 先做**方案 D（A1 唯讀擴充：per-series 缺口報告）**，不碰 production；**但它是否在 `DEC-2026-11-10-02` 授權內，本文判定「不在」，須另獲小額裁示**（§5）。
2. 修復方向推薦**方案 A（per-series 起點，只插入不覆寫）＋ per-series metadata**；**不推薦**先做受控重疊窗口（B／B2，涉及修訂值覆寫語意）、**不推薦**現行 `--bootstrap`（會整表重寫）、**不可做**消費端守衛（凍結範圍）。
3. 任何會改 `scripts/update_macro_history.py`、workflow、`data_cache` 的步驟，以及首次回補的外部抓取，**都必須另行裁示**；本批只交付證據、離線測試與設計。

| Gate | 待客戶裁示事項 | 推薦（未經裁示） | 不裁示時的預設 |
|---|---|---|---|
| **G1** | 是否授權 A1 腳本做 per-series 缺口報告擴充（方案 D；唯讀、離線） | 授權（最小成本、零資料風險） | 不做；缺口維持只靠人工離線盤點 |
| **G2** | 是否授權改寫入端（方案 A：per-series 起點；方案 C：per-series metadata） | 授權 A＋C 的設計與離線測試升格為對 production 函式的測試；實際改碼另獲授權 | 不改；增量語意維持現況 |
| **G3** | 與既有列衝突的語意：保留既有、採最新、或兩者並存並記錄 | 保留既有並記錄差異（B2 的 keep_old 變體） | 不得覆寫既有列 |
| **G4** | 是否授權一次性回補（涉及外部抓取與寫入 `data_cache`）及回補視窗年數（15 或 35） | 先不授權；待 G1／G2 之後依缺口報告再議 | 不回補、不抓取 |
| **G5** | `DTWEXBGS` 頻率與已遺失觀測的處置（週頻現況保留，或回補日觀測） | 待 G4 的取數證據；現況保留並標示 | 保留現況 |
| **G6** | Actions 與 production 依賴版本不一致（workflow 未釘版、requirements 有上下界）要不要對齊 | 先只登記；對齊須改 workflow，另裁 | 不改 workflow |

---

## 1. B1：增量演算法方案×情境矩陣與真實副本起點

**重述（置頂）：以下矩陣是自設合成世界的結果；對真實 FRED 的回傳、發布延遲真值、vintage 修訂，全部 NOT VERIFIED。**

### 1.1 被驗證的生產語意（機制成立，合成）

`scripts/update_macro_history.py::update_one` 對 `fred_indicators` 以「全表最大日期＋1」作所有 series 共同的 `observation_start`；`fetch_fred_indicators` 逐 series 呼叫 `_fred_get_single`，失敗與無新資料**都回空表**，不記錄失敗的 series；`metadata.json` 只有 `name／last_updated／row_count／last_error` 四欄。獨立離線測試 `tests/test_fred_incremental_offline_b1.py`（71 項）以 production 的 `update_one`（只替換取數函式）重現：

- 單一 series 某週失敗：該週 `last_error` 為 `None`、`last_updated` 照樣前進，該週觀測永久缺。
- 後加入的 series：不回補歷史。
- 月頻觀測日（假設 05-01 於 05-20 公布）早於全表最大日期（05-29）：永不取到。結構性原因：月頻觀測日在公布當下必然早於日頻 series 的最大日期。
- 零列 series（宣告但從未寫入）：只取得 ≥ 共同起點的列。
- 同日重跑或無新觀測：表不變，但 `last_error` 被設為「抓取結果為空」（誤報）。
- `_merge_dedupe` 為 `keep="last"`：現行起點不重疊，所以平時不觸發覆寫；任何重疊窗口方案都會啟動它。

### 1.2 方案×情境矩陣（機制成立，合成；候選方案為 `tests/_fred_incremental_sim.py` 內的模擬，非 production）

PASS＝修復或無害；FAIL；PARTIAL；DETECT＝只偵測不修復。方案：baseline＝現行；A＝per-series 起點（最大日＋1，零列＝視窗起點）；B＝重疊窗口（最大日−N，N：日 7／週 21／月 100，候選）；B2＝B＋重疊區差異清單；C＝完整性診斷（不改起點）。baseline 與 C 的表由 production `update_one` 產生。

| 情境 | baseline | A | B | B2 | C |
|---|---|---|---|---|---|
| S1 單週失敗後恢復 | FAIL | PASS | PASS | PASS | DETECT |
| S1b 連兩週失敗後恢復 | FAIL | PASS | PASS | PASS | DETECT |
| S2 後加入 series | FAIL | PASS | PASS | PASS | DETECT |
| S3 月頻發布延遲 | FAIL | PASS | PASS | PASS | FAIL（落後 59 天未達門檻 75 天） |
| S5 零列 series | FAIL | PASS | PASS | PASS | DETECT |
| S6 部分成功 metadata | FAIL（無 per-series 欄位） | PARTIAL（失敗與無新資料難分） | PASS（重疊錨點使存活 series 必回至少 1 列，空＝失敗；前提 NOT VERIFIED） | PASS | FAIL |
| S7 重疊區修訂值 | PASS（不重疊，但永不採修訂值） | PASS（同左） | **FAIL（靜默覆寫舊值）** | PASS（保留舊值並記錄差異） | PASS（不改表） |
| S8 冪等（重跑） | PARTIAL（位元組相同，但重跑 `last_error` 誤報） | PARTIAL（同左） | PASS | PASS | PARTIAL |
| S9 既有表缺頭（`DTWEXBGS` 型） | FAIL | FAIL | FAIL | FAIL | DETECT |
| S10 既有內部空洞（90 天前） | FAIL | FAIL | PASS（N=100；N=60 則 FAIL） | PASS | DETECT |

其他已測（機制成立，合成）：A／B／B2 無重複 (date, series_id)、失敗 series 的既有列逐列不變、輸出每列皆出自世界觀測（不填 0、不插補）、永久無資料的 series 在 A／B 每輪重抓整個視窗（成本）但不產生列、模擬器的 baseline 與 production `update_one` 逐列相同、C 的落後門檻無法區分合法發布延遲與漏抓。

### 1.3 真實副本起點表（真實資料；僅算術，不預測值；視窗 15 年＝2011-11-14，模擬日固定 2026-11-10）

副本＝`data_cache/fred_indicators.parquet`（記憶體唯讀）。cadence 為依副本間距的推論。B 的 N：日 7／週 21／月 100（候選）。起點格式為月-日（同年 2026）或完整日期。

| series | 列數 | 起～迄 | cadence | baseline | A | B | C 旗標 |
|---|---|---|---|---|---|---|---|
| DGS10／DGS2／DGS3MO | 3855 | 2011-06-07～11-05 | D | 11-06 | 11-06 | 10-29 | 無 |
| BAMLH0A0HYM2 | 898 | 2023-06-05～11-05 | D | 11-06 | 11-06 | 10-29 | head_gap |
| WALCL | 805 | 2011-06-08～11-04 | W | 11-06 | 11-05 | 10-14 | 無 |
| M2SL | 179 | 2011-06-01～2026-04-01 | M | 11-06 | 2026-04-02 | 2025-12-22 | stale |
| CPIAUCSL | 178 | 2011-06-01～2026-04-01 | M | 11-06 | 2026-04-02 | 2025-12-22 | stale, internal_gap |
| UNRATE | 183 | 2011-06-01～2026-10-01 | M | 11-06 | 2026-10-02 | 2026-06-23 | internal_gap |
| DTWEXBGS | 21 | 2026-06-05～10-30 | W | 11-06 | 10-31 | 10-09 | head_gap, internal_gap |
| PPIACO／PCOPPUSDM | 0 | — | — | 11-06 | 2011-11-14 | 2011-11-14 | zero_rows |

這張表的數值隨每週 Actions 提交而變；測試只斷言結構性不變量（baseline 起點全相同、A 起點＝各自最大日＋1、零列者取視窗起點、讀取前後檔案 sha256 不變）。

---

## 2. B2：Parquet 版本相容矩陣（離線隔離環境，唯讀）

### 2.1 原檔完整性（真實資料，已由本批重算）

四個 parquet 與 `metadata.json` 的 sha256 與 git 版本（`HEAD`）逐一相同，`git status` 無異動（前 12 碼）：`spx_history` 686e841d5ee9、`vix_history` 278155e127e4、`twii_history` 57ffc3915325、`fred_indicators` 2de56ea25eff、`metadata.json` 8aa60381754b。完整雜湊以 `sha256sum` 重算即可。所有版本相容實驗都在複本或記憶體進行，未覆寫、未移動 `data_cache`。

### 2.2 四檔事實（寫出端 pyarrow 26.0.1＋pandas 3.0.5，B2 實測）

列數與 `metadata.json` 的 `row_count` 一致（spx 3879、vix 3881、twii 3762、fred 13829）；指數檔 `date`＝date32、`close`＝double；fred 的 `date`＝date32、`series_id`＝large_string、`value`＝double；鍵唯一、無 NaN；`created_by` 為 parquet-cpp-arrow 26.0.1。

### 2.3 版本組合矩陣（B2 實測；標「本批重驗」者已由本批在 B2 的隔離環境重跑）

| 組合 | 能 import／讀四檔 | dtype／數值 | 備註 |
|---|---|---|---|
| pyarrow 14.0.2＋numpy 2.4.6＋pandas 2.3.3（requirements 範圍內的下限組合） | **pyarrow 無法 import**（`_ARRAY_API not found`；本批重驗）；`pandas.read_parquet` 因此失敗 | — | 見 §2.4 |
| pyarrow 14＋numpy 1.26.4（超出 numpy 下限） | 可讀 | 僅 fred `series_id` 為 object | 超出 requirements |
| pyarrow 15.0.2＋numpy≥2.3.2 | 解析即不可裝（pyarrow 15 要求 numpy<2；本批重驗） | — | 與 requirements 衝突 |
| pyarrow 16.1.0／17.0.0／18.1.0／20.0.0／24.0.0＋pandas 2.3.3（py3.11／3.12） | 可讀 | 同上（object `series_id`）；數值逐位元一致 | 16.1.0、24.0.0 本批重驗讀取與列數、dtype、摘要 |
| pyarrow 26.0.1＋pandas 3.1.1（py3.13；亦為 workflow 不釘版安裝的實際結果） | 可讀 | 完全一致 | 本批重驗 |

可 import 的組合讀回的 `date` 欄在 pandas 2.x 與 3.x 皆為 object（Python `date`），`_last_date` 與 `_merge_dedupe` 的純函式行為一致；唯一 dtype 差異是 fred `series_id` 在 pandas 2.x 為 object、3.x 為 str。寫入端相容：以腳本相同參數（snappy、`index=False`）寫出原資料與模擬增量合併檔，10 個寫端×9 個讀端交叉讀 180 格，0 失敗，逐位元摘要一致（B2 實測，本批未全數重跑）。

### 2.4 發現與後果

1. **requirements 的 pyarrow 下限在 numpy≥2.3.2 下不可用（真實，已重驗）**：`requirements.txt` 宣告 `pyarrow>=14,<25`、`numpy>=2.3.2,<2.6`、`pandas>=2.3.3,<3.0`；以 constraint 鎖下限會得到無法 import 的環境，實務最低約 pyarrow 16.1.0。一般 `pip install -r` 解最高版（24.x）不會觸發。**已收窄**：B2 草稿稱「連 pandas 也 import 失敗」；本批實測**純 `import pandas` 成功**，失敗的是 pyarrow 的 import 與 `read_parquet`。
2. **workflow 與 requirements 不一致（真實，已重驗）**：`update_macro_history.yml` 為 `pip install pandas pyarrow requests urllib3`、`export_db.yml` 為 `pip install pandas pyarrow`，兩者皆未釘版；`cache: "pip"` 只是快取下載，不釘版。現況 Actions 解到 pandas 3.1.1／pyarrow 26.0.1（B2 以本機 proxy 模擬，Actions 當日實際解析結果 NOT VERIFIED），超出 requirements 的 pandas<3.0、pyarrow<25。後果：快取由 pandas 3／pyarrow 26 寫出；production 釘版環境（pandas 2.3.3）在 B2 矩陣內讀得到，但 series_id dtype 隨大版本變動（object／str），下游若有 `dtype == object` 判斷會有差異（B2 僅驗腳本純函式，其他消費端未驗）。
3. **明寫：能讀≠可用於正式 UI。** 讀得到只代表檔案層相容；未跑 Streamlit、`services/macro/validation.py`、`scripts/export_fund_db.py`、`scripts/calibrate_macro_score.py` 的實際行為（只讀碼確認它們用 `pandas.read_parquet`）。

### 2.5 NOT VERIFIED（B2）

pyarrow 25.x（requirements 排除）、pyarrow 19／21／22／23 與 pandas 3.0.x 的逐版組合、Python 3.14、Windows／macOS wheel、pandas 2.x 讀 timestamp 型 date 欄、Streamlit 與消費端實際行為、Actions 當日 pip 解析結果。

---

## 3. B3：六個 series 逐項缺口與 `last_error` 掩蓋證據

### 3.1 逐項缺口表（真實資料；快取版本 `8ca33547`；全表最大日期 2026-11-05）

| series | 列數 | 迄 | 觀察到的缺口 | 22 次週日排程的新增列 | 成因（皆推論或 NOT VERIFIED） |
|---|---|---|---|---|---|
| CPIAUCSL | 178 | 2026-04-01 | 缺 2025-10-01；迄日落後全表最大日 218 天 | **0**（已重驗） | 機制（共同起點）與觀察一致；2025-10 缺值可能是上游當月未發布（推論，未驗） |
| M2SL | 179 | 2026-04-01 | 迄日落後 218 天；無缺月 | **0**（已重驗） | 同 CPI |
| UNRATE | 183 | 2026-10-01 | 缺 2025-10-01、2026-05-01 | 5 次各 +1（觀測日 06-01、07-01、08-01、09-01、10-01；已重驗） | 增量起點嚴格濾日模型解釋不了；B3 假說 H-U（起點所在資料月份的值會被取到）擬合 6／6 個月份，**推論、未驗** |
| PPIACO | **0** | — | 從未出現 | 27 個含 fred parquet 的提交皆 0 列（已重驗） | 宣告於 2026-06-08 才加入，且之後從未再 bootstrap；是否另有 series 級取數失敗離線不可辨 |
| PCOPPUSDM | **0** | — | 從未出現 | 同 PPIACO | 同上；若公布節奏使其應被抓到而仍為 0，則可能有獨立取數失敗（推論） |
| DTWEXBGS | 21 | 2026-10-30 | 起於 2026-06-05（缺頭）；缺 2026-06-29 週（06-26→07-10 間隔 14 天，已重驗） | 21 次各 +1、1 次 0 列（07-12 排程） | 每次新增的觀測日恰等於當次起點；頻率未定（週頻或日頻皆可能），若為日頻則已系統性遺漏起點前的日觀測（推論） |
| **DGS10／DGS2／DGS3MO（新發現）** | 3855 | 2026-11-05 | 2026-06-01～11-05 的缺平日為 06-19、07-02、07-03、09-07、10-12（已重驗）；除 07-02 外皆為美國假日／債市休市日（推論，本批未引入交易日曆） | — | 07-05 排程時 `BAMLH0A0HYM2` 把全表最大日推到 07-02，下次起點 07-03 越過 07-02（推論）。`BAMLH0A0HYM2` 同期無缺平日；A1 現行門檻（日頻 7 天）看不到 1～4 天的洞 |

快取歷史限制：本批可見的 git 歷史為 27 個觸及 `fred_indicators.parquet` 的提交（`git log --all`；淺層 clone 不加 `--all` 只看得到 3 個），結論限本 clone 可見者。

### 3.2 dataset-level `last_error` 掩蓋 series-level 失敗：證據清單

讀碼（真實）：`last_error` 只在三種情況被設——缺 `FRED_API_KEY`、`fn()` 丟例外、取回結果整體為空；`fetch_fred_indicators` 對任一 series 失敗只印日誌後略過，只要有任何 series 有新列，整個 dataset 的 `last_error` 就是 `None`；`metadata.json` 沒有 per-series 欄位；「已是最新」分支亦回 `None`。

| # | 證據 | 類型 |
|---|---|---|
| 1 | 首份 FRED 快取（`611fbe6e`）只含 4／8 個當時宣告的 series，`last_error` 為 null | 真實（已重驗：該版 4 個 series） |
| 2 | PPIACO、PCOPPUSDM 自宣告後 22 次排程（06-14～11-08）0 列，各版 `last_error` 皆 null（本批逐版重讀 27 個版本，結果皆 None） | 真實 |
| 3 | CPIAUCSL、M2SL 自 2026-04-01 起 218 天無新列，`last_error` 皆 null | 真實 |
| 4 | 07-05 排程後 DGS10／DGS2／DGS3MO 缺 2026-07-02，`last_error` null | 真實 |
| 5 | 06-29 週 DTWEXBGS 缺列，`last_error` null | 真實 |
| 6 | **反向誤報**：`2a96a4fb`（06-03）的 `last_error`＝「抓取結果為空」發生在沒有任何 series 失敗的一次無新資料執行（已重驗 metadata 內容） | 真實 |
| 7 | **本批另發現的重跑誤報**：production 函式對同日重跑或無新觀測，表不變卻設 `last_error`＝「抓取結果為空」 | 機制成立（合成） |
| 8 | 取數層對「失敗」與「無新資料」都回空表，事後無法區分 | 機制成立（合成）＋讀碼 |

限制：Actions 執行日誌（記錄每個 series 的 HTTP 狀態或「無 observations」）離線不可取，故 2～5 是「未寫入」的事實，**不是**「抓取失敗」的證明（NOT VERIFIED）。結論：`last_error` 既漏報也誤報，**不能當 series 健康訊號**。

---

## 4. 修復方案比較（皆為候選，不核准、不執行）

共同前提：下游讀者只有 `services/macro/validation.py::load_indicators_from_parquet` 與 `scripts/export_fund_db.py::write_fred_macro` 讀 parquet；`metadata.json` 的 Python 讀者僅 `scripts/check_cache_quality.py`（B3 讀碼與 grep，本批未重跑）。`DEC-2026-11-09-10` Q4 為「不覆寫快取、不更改計算」（針對 Yahoo 證據）；`DEC-2026-11-10-01` 第三項已列「`update_macro_history.py` 變更、FRED 回補、重疊窗口重抓」為未核准。

| 面向 | **A per-series 起點** | **B 重疊窗口（含 B2 差異清單）** | **C per-series metadata／診斷（不改取數）** | **D A1 唯讀擴充** | **E 手動只補缺回補** | **F 消費端守衛** |
|---|---|---|---|---|---|---|
| 改動檔案與符號 | `scripts/update_macro_history.py`：`update_one`、`fetch_fred_indicators` | 同左；起點函式加 N 表；B2 另加衝突記錄 | `update_macro_history.py` 的 metadata 組裝（新增 additive 欄位） | `scripts/check_cache_quality.py`（缺平日、具體缺月清單、`last_error` 與 series 實況不一致輸出）、`tests/test_check_cache_quality.py` | 新增一次性 merge-only 模式（`scripts/`）＋ workflow_dispatch | `services/macro/validation.py::load_indicators_from_parquet` |
| 測試 | 把 `tests/_fred_incremental_sim.py` 情境升格為對 production 函式的測試（S1／S1b／S2／S3／S5／S8） | 同左＋S7／S10 | 合成 metadata 讀寫測試 | 合成 parquet 擴充 | 合成回補測試＋稽核 | 凍結，不可做 |
| 正確性／風險 | 消除共同起點機制；風險：首次補入大量歷史、覆寫語意；對已遺失的缺頭／內部空洞無效（S9／S10） | 能補 90 天內空洞與假日週；重疊區既有列以最新值覆寫（B 靜默、B2 記錄）；修訂值語意為 NOT VERIFIED | 只讓缺口可見，不修；新欄位屬資料契約變更 | 零資料風險，不修復 | 可補 CPI／M2／UNRATE 2026-05／零列歷史；補入值為「現在的 FRED」，無 vintage（PIT 風險，見 CLAUDE.md §2.3） | 改計算輸入，高風險 |
| 速度 | 請求數不變（每 series 1 次） | 同左，回應略增 | 快 | 最快 | 一次性 | — |
| Token／維護成本 | 中（需獨立稽核，改增量語意） | 低～中（頻率對照表要維護） | 低 | 低 | 中 | — |
| 需外部抓取 | 開發離線；上線後每週排程自然抓 | 同左 | 否 | 否 | 是（FRED Key 僅在 workflow 內） | 否 |
| 是否改 production | 是 | 是 | 是 | 否（不在 workflow 內） | 是（含 `data_cache`） | 是（凍結） |
| Stop Gate | production data source 行為、歷史成果覆寫 | 同左，且涉及修訂覆寫 | 資料契約 | 是否屬 A1 擴充須另裁（§5） | 外部抓取＋改快取 | 凍結＋改計算 |
| 回滾 | `git revert` 腳本；已補入列需對應 `data_cache` 提交 revert | 同左，覆寫過的舊值需靠 git 歷史還原 | `git revert`；多餘欄位無害 | 刪改動即可 | 單一用途提交 `git revert` | — |
| 與 Q4 的關係 | 只增不覆寫則相容；採「可覆寫」則相鄰，須明示 | **直接觸及**（窗口內覆寫），B2 keep_old 較接近相容 | 相容（不覆寫快取、不改計算） | 相容 | 與 Q4 精神相鄰，須明示 | 不相容（改計算） |

比較結論（推薦，未經客戶裁示）：D（若 G1 授權）→ A＋C（G2）→ E（G4，且只插入）；B／B2 不先於 A；現行 `--bootstrap` 會整表重寫、任一 series 該次失敗即從檔案消失（首份 FRED 快取即是實例），不推薦；F 不可做。

---

## 5. 可安全修改範圍 vs 必須另行裁示

**本批已完成（可安全，且已在授權內）**：純文件（本文、`DEC-2026-11-10-05`、`BACKLOG`／`HANDOFF` 索引）＋獨立離線測試（`tests/test_fred_incremental_offline_b1.py`、`tests/_fred_incremental_sim.py`）。不改任何 production 檔、不連網、不寫 `data_cache`。

**A1 腳本擴充是否在 `DEC-2026-11-10-02` 授權內：判定「不在」。** `-02` 核准的是 A1 當時定義的唯讀檢查；新增檢查項（日頻缺平日、缺月清單、狀態不一致）等於擴張其範圍，**須另獲小額裁示（G1），本批不做**。

**必須另行裁示（不得藉本批解鎖）**：

1. 改 `scripts/update_macro_history.py`（方案 A／B／C／E）。
2. 改任何 `.github/workflows/*`（含 `years`／bootstrap 預設、依賴釘版）。
3. 改／補／覆寫 `data_cache/*.parquet` 或 `metadata.json`。
4. `metadata.json` 格式變更（新增 per-series 欄位屬資料契約）。
5. 任何外部抓取或 workflow 觸發（含 dry-run、取 Actions 日誌）。
6. 解除 `services`／`ui_v2` 凍結（方案 F）。
7. FRED PIT／vintage 處理（`release_date`）。
8. 以快取當已驗證資料使用；切換 New UI 資料來源；FX Gate、Eligibility、OneBrain。

---

## 6. 最小修復設計（僅設計，未核准；若 G2 獲授權才由 production 組實作）

- **起點**：`scripts/update_macro_history.py::update_one` 的 `fred_indicators` 路徑改為每 series 以自身最大日＋1 為起點；零列或被診斷為缺頭者取視窗起點（年數待 G4）；其他三個單序列 dataset 不變。
- **取數層**：`fetch_fred_indicators` 接受 per-series 起點；`_fred_get_single` 的失敗要回可區分的錯誤（或另行記錄），不再與「無新資料」同形。
- **合併**：預設只插入、不覆寫既有列；衝突列記錄差異（G3 決定是否採用新值）。
- **metadata**：additive 欄位 per-series `last_observation`、`fetched_rows`、`status`，不改既有四欄；`last_error` 對「無新觀測」不再設錯（S8）。
- **測試**：把本批 71 項中的合成情境升格為對 production 函式的測試；保留真實副本的結構性不變量測試。
- **驗證**：獨立稽核（改增量語意屬高風險）；上線前以 A1 缺口報告前後比對；Actions 日誌核對（本批不可取）。
- **回滾**：`git revert` 程式提交；已補入的列以對應 `data_cache` 提交 revert。
- **不包含**：回補本身、workflow 改動、UI 或凍結範圍。

---

## 7. 附錄

### 7.1 抽查結果（本批自行執行，12 項）

| # | 宣稱（來源） | 結果 |
|---|---|---|
| 1 | 四個 parquet 與 `metadata.json` sha256 前後一致（B2） | **成立**：與 git 版本逐一相同，`git status` 乾淨 |
| 2 | `git status` 為 0 行（B2） | 成立 |
| 3 | `requirements.txt` 宣告 pyarrow>=14,<25／numpy>=2.3.2／pandas<3.0（B2） | 成立 |
| 4 | `update_macro_history.yml`、`export_db.yml` 未釘版 `pip install pandas pyarrow`；`cache: "pip"`（B2） | 成立 |
| 5 | pyarrow 14.0.2＋numpy 2.4.6 不可 import；pyarrow 15.0.2 與 numpy≥2.3.2 不可解（B2） | 成立；**收窄**：純 `import pandas` 成功，失敗在 pyarrow 與 `read_parquet`（B2 稱連 pandas 也失敗） |
| 6 | pyarrow 16.1.0／24.0.0（pandas 2.3.3）與 26.0.1（pandas 3.1.1）可讀四檔且列數、摘要一致（B2） | 成立（讀取後檔案雜湊不變） |
| 7 | PPIACO／PCOPPUSDM 22 次排程 0 列、各版 `last_error` null（B3） | 成立：27 個含 fred 的版本，PPIACO／PCOPPUSDM 皆 0 列，`last_error` 全為 None |
| 8 | CPI／M2 22 次排程 0 新列（B3） | 成立 |
| 9 | UNRATE 5 次各 +1（觀測日 06-01、07-01、08-01、09-01、10-01）；缺 2025-10 與 2026-05（B3） | 成立 |
| 10 | DGS10／DGS2／DGS3MO 缺 2026-07-02，BAMLH0A0HYM2 同日有值（B3） | 成立（缺平日五個，與 B3 相同） |
| 11 | DTWEXBGS 缺 2026-06-29 週、起於 2026-06-05（B3） | 成立 |
| 12 | `2a96a4fb` 的 `last_error`＝「抓取結果為空」；PPIACO／DTWEXBGS 於 2026-06-08 才加入宣告；A1 門檻為 max(1.5×中位數, 7)（B3） | 成立 |
| 13 | 本批 71 項測試重跑 | 全過（見交付回覆） |

### 7.2 被推翻或收窄者

- **B2 收窄**：「pyarrow 14 下連 pandas 也 import 失敗」→ 只有 pyarrow 與 `read_parquet` 失敗。
- **B1 收窄（相對先前證據檔 §2）**：先前的 per-series 對照只涵蓋 S1／S2／S3；本批補入 B／B2／C 與 S5～S10，並指出 A 單獨**不能**修既有缺頭（S9）與內部空洞（S10）。
- **B1 收窄（與 B3 對照）**：B1 的 S3 假設「嚴格以觀測日過濾」；B3 觀察到 UNRATE 的月值在增量起點之前仍被取到（5 次），顯示 FRED 對月頻 series 的 `observation_start` 行為可能不同。B1 的 S3 結論只對嚴格過濾模型成立，對真實 FRED NOT VERIFIED；CPI／M2 的觀察與該模型一致，UNRATE 與之不一致。
- **B3 未推翻但降級**：H-U（UNRATE 假說）與 DTWEXBGS 的頻率假說皆維持推論；B3 對 PCOPPUSDM 可能有獨立取數失敗的推測不得當事實。

### 7.3 測試重現

```
PYTHONPATH=<含 pyarrow 的 site 目錄>:.:/usr/local/lib/python3.13/site-packages \
  /root/.local/bin/pytest tests/test_fred_incremental_offline_b1.py --noconftest -p no:cacheprovider -q
```

環境與 venv 路徑（含 pyarrow 的 site 目錄、B2 的隔離 venv 與複本）只存在於本批 scratchpad，不入庫；`pytest` 為 uv tool 安裝，需用絕對路徑；缺 pyarrow 時整檔 skip。

### 7.4 未涵蓋

真實 FRED 回傳與 `observation_start` 對月頻 series 的語意、各 series 實際公布日與頻率、vintage 修訂、Actions 執行日誌與當日 pip 解析結果、Streamlit Cloud 行為、消費端（Streamlit、`services/macro/validation.py` 等）的實際讀取行為、`fund.db` 與 FRED 以外問題、pyarrow 25／Python 3.14／Windows／macOS、交易日曆（本批僅用資料內缺日推論）。所有 DEC 引用為要點轉述，未取得逐字原話。
