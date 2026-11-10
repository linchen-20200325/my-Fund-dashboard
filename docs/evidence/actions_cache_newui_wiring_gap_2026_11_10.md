# GitHub Actions → Cache → New UI 唯讀接線差距盤點（2026-11-10）

> **性質聲明（先讀）**
>
> - 本文是**研究與架構方向**的 docs-only 證據檔，**不是**准許切換 production 的授權（`DEC-2026-11-10-04`）。客戶方向是「Actions 已能穩定取得的資料，優先由 Streamlit 讀已驗證快取」；本文只盤點離這個方向還差什麼，並比較三種接線方式。
> - **不核准**：Eligibility、正式母集合、涵蓋率分母、日期轉換規則、FX Gate（`FX_OBS_DATE_RULE_VERIFIED` 維持 `False`）、任何金融公式或門檻、OneBrain。**不建立第二套資料 SSOT**；本文提到的任何「讀取器」「欄位」「標示」都只是候選，未核准。
> - 缺值就是缺值（missing ≠ 0）；proxy 不是真資料；**觀測日 ≠ 公布日 ≠ 取得日**；「有原料／可讀／具備正式金融語意／允許 UI 使用」四層證據**互不推論**（前一層 YES 推不出下一層）。
> - 標籤：**FACT**＝本批讀碼、讀檔或實跑所見；**INFERENCE**＝由 FACT 推得；**NOT VERIFIED**＝未驗。快取內容的列數與日期是 2026-11-10 在基準 `c11aca98` 實讀的結果。
> - 本批**未**修改任何 `.py`／workflow／`data_cache`／UI，**未**發出任何外部請求，**未**觸發 workflow，**未**輸出任何 Secret。測試腳本的 Key 是執行期組成的假字串。
> - 本文由專案 AI 整合兩份單組唯讀盤點草稿並自行抽查（附錄 B）；抽查之外**沒有第二組獨立驗證**。客戶指示經總管轉達，無逐字存檔。
> - 引用既有證據不重做：`cache_quality_check_a1_report_2026_11_10.md`、`cache_quality_intraday_freeze_study_2026_11_10.md`、`secrets_recovery_verification_2026_11_10.md`、`yahoo_indices_sp_probe_result_2026_11_09.md`；決策 `DEC-2026-11-09-10`（Q1–Q5）、`DEC-2026-10-27-41`～`-44`、`DEC-2026-11-10-01`～`-03`。
> - 本文刻意不寫程式行號（會漂移），一律用「檔案＋符號」定位；數字都附量測基準。

---

## 0. 推薦結論與最小 Decision Gate（推薦在前；**未經客戶裁示，總管讀法，可被推翻**）

**一句話**：快取今天**還不能**當 New UI 的主來源；最小、最安全的第一步是**方案 α 的最窄版**——只對 DGS10／DGS2，且**只在即時取數失敗時**回退讀快取（**不含缺 Key**：缺 Key 仍維持現有「尚未設定」畫面，避免遮蔽客戶正在驗證的 Cloud 端 FRED Secrets 訊號），並明標「來源＝Actions 快取＋快取最後觀測日＋已落後 N 天」；成功路徑行為零變更。它不能直接達成「優先讀快取」的方向，但可以用最低風險驗證兩個目前 NOT VERIFIED 的前提（Streamlit Cloud 讀不讀得到檔、stale 怎麼標），再決定要不要升到 β。

**為什麼不是 β／γ**（細節見第 5 節）：

1. 快取目前缺 New UI 現有契約所依賴的欄位（取得時間、交易所時區、公布日），且 FRED 表有 series 級缺口（CPI／M2 停在 2026-04-01、PPIACO／PCOPPUSDM 零列、DTWEXBGS 僅 21 列）；β／γ 會把這些原樣顯示給使用者。
2. HY OAS、T10Y2Y、FEDFUNDS 在 New UI 走 vintage（要首次公布日），快取**結構上不能替代**，γ 在九項上不可完整達成。
3. 生產端「全表最大日期＋1」增量起點的缺陷**在合成資料下機制成立**（第 2 節），所以「快取能穩定取得」這個前提本身還沒成立。

**前置條件（皆為候選，未核准，各自需 Gate）**：

- **P1 生產端先修**（任一項都屬 production 資料取得行為變更）：per-series 增量起點、series 完整性檢查、metadata 補 `fetched_at`／`source`／per-series 狀態（候選細節見 5.5）。對 α 最窄版（只讀 DGS10／DGS2，日頻、落後 0 天）**不是硬前提**，但對 CPI／M2／UNRATE／DTWEXBGS／HY 是**進入任何接線之前的前提**。
- **P2 離線守衛先固定**：用既有 `scripts/check_cache_quality.py`（A1）把「讀取前守衛」的判準固定下來（離線、零風險；是否擴充仍屬另案）。
- **P0 缺 Key 不回退**：α 不涵蓋缺 `FRED_API_KEY`（維持「尚未設定」畫面），以免遮蔽客戶正在驗證的 Cloud 端 Secrets 訊號。
- **P3 部署面實測**：Streamlit Cloud 實際部署分支、bot push 後是否重新拉取、New UI 的正式入口——目前 repo 內無證據（第 4 節 W8）；α 最窄版正好可以順帶驗證。

### 最小 Decision Gate 表（請客戶裁示；每題附總管建議）

| # | 要客戶裁示的事 | 為什麼是 Gate | 總管建議 |
|---|---|---|---|
| G1 | 是否准許「Actions 快取」作為 New UI 的**明標備援來源**（僅 DGS10／DGS2、僅即時失敗時） | `PROJECT_RULES.md` 第 4 節「新／替換 production data source」：資料血緣仍是 FRED，但**取得路徑是新的 production 路徑**，且帶來新失效模式（cron 沒跑、快取停更）。**這個「算新來源」是總管讀法，客戶可裁示不算**——若不算，G1 消失，只剩 G2 的分層問題 | **准許，限最窄版**；不准許則維持現狀（無備援） |
| G2 | 是否解除 `services/v2_tables/market_view.py` 檔頭的「不新增 L1 函式」硬邊界，允許新增一支唯讀 L1 讀取器 | 該邊界出自檔頭自述，承接 `DEC-2026-10-27-41` 的條件式「若既有 source 已有」與 `-42`（a）（c）；**repo 內未見專屬的解除條件**（第 6 節）。parquet 讀取是 I/O，依 `CLAUDE.md` §8.2 只能放 L1，所以 α／β／γ 都繞不過 | **准許且僅限一支唯讀讀取器**（回 `(frame, error)`，沿用 `*_with_error` 慣例） |
| G3 | 快取路徑的**日期與標示語意**：`obs_date`＝FRED 觀測日；「已落後 N 天」的基準日（今天的哪個時區）；不得把檔案 `updated_at` 當取得時間；是否准許新增狀態詞或原因碼 | `DEC-2026-11-09-10` ③ 明列「不新增狀態詞」「不批准日期轉換規則」；新使用者文案另受 `APPROVED_WORDING` Gate | 沿用既有四態，用現有 `ok` ＋明確的來源字串與落後天數字樣；**不新增狀態詞**；文案由客戶另行核可 |
| G4 | 是否授權**生產端修補**（P1）：授權哪一項、是否先做 | 觸及資料取得語意；「重疊窗口自癒」會覆寫既有列，與 `DEC-2026-11-09-10` Q4（不覆寫快取）相鄰，另需明示 | 先授權**最小兩項**：(a) per-series 起點、(b) 離線完整性檢查；metadata 變更與覆寫類候選另案 |
| G5 | （僅 β 才需要）「過期」門檻、Old UI／New UI 同指標數值一致性 | 自創新鮮度門檻是 Stop Gate 內容；`PROJECT_RULES.md` 13.3 Cross-View 一致性 | α 階段**不問**；升 β 時再送 |
| G6 | **凍結面與 `ui_v2` maintenance-only 是否有例外適用於 α**（及 P1 的 metadata／檔案格式變更） | 本批讀 `PROJECT_RULES.md` 13.2 確認：`ui_v2`＝maintenance-only、不新增新版面、不公開到正式 Streamlit（`DEC-2026-11-02-05`／`-06`）；`BL-0537` 登記了凍結清單機械守衛（待客戶裁示、未建置），其列舉的例外類別為安全／正確性修補、`BL-0532` 缺資料字樣統一、PORT shim，**未含「新增資料備援路徑」**（FACT）。另母法凍結令 `docs/v2/CONSTITUTION.md` 的 F4＝`services/**`、F5＝資料表 Schema（含 `data_cache/` 檔案格式），`docs/v2/20_ui_spec.md` 引用之。α 的候選變更會改既有 `services/v2_tables/market_view.py` 並新增 L1 讀取器（觸 F4），若同批改 metadata 欄位則觸 F5。**凍結令是否涵蓋 `services/v2_tables/` 內的增修與新增唯讀 L1：本批未查得裁示（NOT VERIFIED），因此不能判定「不適用」** | 設計上**先避開 `ui_v2`**：把回退做成 `build_market_view` 的 opt-in 參數（預設關），只由 `ui_v3/adapters/market_page.py::load` 開啟，`ui_v2/mkt/source.py` 不改；並請客戶確認 F4／F5 是否涵蓋上述增修，若涵蓋須走母法修正提案單（`docs/v2/CONSTITUTION.md` §5），P1 的 metadata 變更同理 |

**不需要客戶裁示、可直接做的**：無。本文是 docs-only；任何程式、workflow、快取、UI 變更都需上列 Gate 或另行授權。

---

## 1. 生產端盤點（Actions → data_cache）

### 1.1 流程（FACT，讀碼；基準 `c11aca98`）

| 項目 | 內容 |
|---|---|
| 取數腳本 | `scripts/update_macro_history.py`：`update_one`（每個 dataset 一次）→ `FETCHERS`；FRED 走 `fetch_fred_indicators`（逐 series 呼叫 `_fred_get_single`，間隔 1 秒，任一 series 失敗只 `continue`）；Yahoo 三指數走 `_yf_fetch_close` |
| workflow | `.github/workflows/update_macro_history.yml`：`cron: "0 0 * * 0"`（週日 UTC 00:00）＋ `workflow_dispatch`；`permissions: contents: write`；Python 3.11；`pip install pandas pyarrow requests urllib3`（**未釘版本**）；`FRED_API_KEY`／`PROXY_URL` 以 Actions secrets 注入該步驟；有 diff 才 commit（訊息帶 `[skip ci]`）並 `git push` 到觸發分支（排程＝預設分支） |
| 匯出（消費者，非取數者） | `.github/workflows/export_db.yml` ＋ `scripts/export_fund_db.py`：每日讀**已 commit** 的 parquet（免 Key、免網路）寫 `fund.db`，force-push 到 `data` 分支；沿用上游缺口 |
| 離線檢查 | `scripts/check_cache_quality.py`（A1，唯讀）；不在運行時層 |
| Secrets 分離 | `FRED_API_KEY` 在 Actions secrets；Streamlit 端另由 `app.py` 讀 Streamlit secrets 寫入環境。兩處各自設定，互不共享（FACT） |

### 1.2 四份 parquet＋metadata（FACT，2026-11-10 以 pyarrow 實讀；不寫檔）

| 檔 | 來源 | 欄位／dtype | 範圍／列數 | 日期語意 |
|---|---|---|---|---|
| `fred_indicators` | FRED `series/observations`；腳本宣告 11 個 series，快取僅 9 個有列 | `date`（Python `date`）、`series_id`、`value`（float64）；`attrs` 空 | 2011-06-01～2026-11-05；13,829 列 | **observation_date**（觀測所屬日）；不是公布日、不是取得日；FRED 的 `.` 缺值列被丟棄、不補 |
| `vix_history` | Yahoo `^VIX` 日線 | `date`、`close`；`attrs` 空 | 2011-06-07～2026-11-06；3,881 列；週末列 0 | `datetime.fromtimestamp(t).date()`＝**執行機器本地時區**的列日期（GitHub 託管 runner 預設 UTC 為 INFERENCE） |
| `spx_history` | Yahoo `^GSPC` | 同上 | 同起點～2026-11-06；3,879 列；週末列 0 | 同上 |
| `twii_history` | Yahoo `^TWII` | 同上 | 同起點～2026-11-06；3,762 列；**週末列 1**（2026-09-20，A1 已登記） | 同上 |
| `metadata.json` | 腳本 | `updated_at`（UTC 執行時間）；各 dataset `{name,last_updated,row_count,last_error}` | `updated_at`＝2026-11-08T04:07Z | `last_updated`＝**該表最大資料日期**（不是取得時間）；`last_error` 為**資料集層級** |

FRED 各 series（FACT，同次實讀）：

| series | 列數 | 起 | 迄 | 落後全表最大日期（天） |
|---|---|---|---|---|
| DGS10／DGS2／DGS3MO | 3,855 | 2011-06-07 | 2026-11-05 | 0 |
| BAMLH0A0HYM2 | 898 | **2023-06-05** | 2026-11-05 | 0 |
| WALCL | 805 | 2011-06-08 | 2026-11-04 | 1 |
| M2SL | 179 | 2011-06-01 | **2026-04-01** | 218 |
| CPIAUCSL | 178 | 2011-06-01 | **2026-04-01** | 218 |
| UNRATE | 183 | 2011-06-01 | 2026-10-01 | 35 |
| DTWEXBGS | **21** | **2026-06-05** | 2026-10-30 | 6 |
| PPIACO／PCOPPUSDM | **0** | — | — | 宣告了但快取無列 |

### 1.3 更新策略與可追溯性缺口（FACT）

- 預設增量：`start = _last_date(整表) + 1 天`；`observation_start=start`、`observation_end=今天`。`fred_indicators` 是**一張長表**，`_last_date` 取的是**所有 series 共用的一個最大日期**。
- bootstrap 或缺檔：`start = 今天 − years×365`，且 `existing=None` → 整表覆寫，非合併。
- 合併：`_merge_dedupe` 以 (date, series_id) `keep="last"`；但增量從 last+1 起，**舊列不會被重抓**（無重疊窗口）。
- 單一 series 失敗：只印 log、`continue`，其餘照寫；`metadata` 沒有 per-series 狀態。`update_one` 只有「整個資料集抓取為空」才記 `last_error`，所以單一 series 失敗**不會**反映在 `last_error`。
- `main()` 在有 dataset 錯誤時仍 `return 0`；workflow 不會因 series 失敗而變紅。`metadata.updated_at` 每次執行都重寫為當下時間，所以**每次排程都會有 diff、都會 commit**，commit 本身不代表有新資料（FACT，讀碼）。
- 快取檔沒有 `fetched_at`／`source`／run id；唯一的取得時間證據是 git commit 時間（INFERENCE：晚於實際取數）與訊息中的 UTC 日期。
- `years` 預設不一致（FACT）：workflow 輸入預設 `'15'`、腳本 `--years` 預設 `35`。`years` 只影響 bootstrap／缺檔路徑；快取最早日期 2011-06 與 15 年 bootstrap 一致（INFERENCE：快取最初由 `years=15` 的 bootstrap 建立，約 2026-06-02～03，研究文件所載）。

### 1.4 metadata 語意陷阱（FACT＋INFERENCE）

`metadata.updated_at`＝**批次執行時間**；各 dataset 的 `last_updated`＝**該表最大資料日期**。兩者都不是逐 series 的取得時間。例：CPIAUCSL／M2SL 的資料停在 2026-04-01，但檔案 `updated_at` 是 2026-11-08——**若有人把 `updated_at` 當 `fetched_at`，會得到「看起來剛更新、實際停更七個月」的錯誤結論**（INFERENCE，由上列 FACT 推得）。因此任何接線都應以「最後觀測日＋落後天數」為主，`updated_at` 最多標為「快取檔寫入時間」。

---

## 2. 「全表最大日期增量起點」造成個別 series 漏抓？——唯讀機制測試

**問題**：`start = 全表最大日期 + 1` 是否會讓個別 series 永久漏抓？
**方法**：`import` 真實的 `update_one`／`fetch_fred_indicators`／`_merge_dedupe`／`_last_date`，只 monkeypatch `_fred_get_single`（記憶體假資料，模擬 `observation_start/end` 過濾）與快取目錄（暫存）。無網路、假 Key、不寫 repo。腳本全文見附錄 A，**本批重新執行 7 項檢查全數通過；其中 4 項（S1 兩項、S2、S3 各以生產碼 `update_one` 驗證機制）驗生產碼機制，另 3 項（`S4.*`）為測試內模擬的對照模型，不驗生產碼**。

### 2.1 結果（FACT：合成資料下的機制；對真實 FRED 行為 NOT VERIFIED）

| 情境 | 設定 | 結果 | 判定 |
|---|---|---|---|
| S1 單一 series 失敗 | X、Y 週頻；某週 X 取數回空、Y 成功使全表最大日期前進；下週 X 恢復 | 該週 `last_error=None`、`last_updated` 前進；X 的 2026-05-06 觀測**永久缺**（下次起點已晚於該日） | 機制成立：失敗被 metadata 掩蓋、且永不回補 |
| S2 後加入 series | 已有 DGS 至 06-01；之後把 NEW（世界有約 787 列歷史）加入宣告再增量 | NEW 只得 4 列、起 2026-06-03，歷史不回補 | 機制成立 |
| S3 月頻觀測日早於全表最大日期 | 全表最大日 05-29，CPI 至 04-01；其後 05-01 觀測公布，此時全表最大日已 06-05 | CPI 05-01 **永不取到** | 機制成立 |
| S4 對照（每 series 用自己的最大日期＋1） | 僅測試內模擬 | S1、S3 完全回補；S2 改善（52 列）但缺列起點受 `今天−365` 限制，仍非完整歷史 | 在合成資料下有效；**不是已核准的修法** |

### 2.2 機制與真實快取是否一致（INFERENCE，並含一個未解反例）

與機制**一致**的觀察：CPIAUCSL／M2SL 停 2026-04-01；PPIACO／PCOPPUSDM 零列；DTWEXBGS 只有 21 列且起於 2026-06-05（快取以 15 年 bootstrap 建立，若這三個 series 在 bootstrap 當次沒有取到，之後都只能從當時的全表最大日期往後補）。

**未解反例（本批用 git 歷史補強，原因仍未知）**：UNRATE 最新到 2026-10-01，比 CPI／M2 新六個月，但機制預測月頻 series 在初建後都不該再前進（UNRATE 另缺 2026-05，與 CPI／M2 的「停更」不同，同屬未解）。本批在淺層 clone 可見的三筆 `data_cache/fred_indicators.parquet` 提交（`b816df1c`、`20bf6442`、`8ca33547`）上做集合比對（唯讀，`git show` 進記憶體）：

- 11-01 提交（`20bf6442`）：前次全表最大日 2026-10-22，新增 22 列，全部日期 ≥ 10-23；UNRATE 無新增。
- 11-08 提交（`8ca33547`）：前次全表最大日 2026-10-29（所以預期 `observation_start`＝2026-10-30），新增 23 列、**刪除 0 列、重疊列數值變動 0**；除 UNRATE 外所有新增列日期皆 ≥ 10-30，**唯獨 UNRATE 新增了觀測日 2026-10-01**（早於預期起點）。
- 因此「手動 bootstrap／整表覆寫」可以排除作為這一筆的解釋（bootstrap 會整表重寫，不會只多一列）。`cache_quality_intraday_freeze_study_2026_11_10.md` 已記載 UNRATE 在 07-05、08-09、09-06、10-04、11-08 五次排程各前進一個月（引用，本批只重驗最後一次）。
- **本批無法解釋**：是 FRED 對該 series 的 `observation_start` 行為與假設不同、還是執行紀錄有其他起點，皆 NOT VERIFIED（Actions 執行紀錄與 FRED 真實回應本批未查）。

**結論**：「全表最大日期＋1」缺陷的**機制已被合成資料證明**，且與 CPI／M2／PPIACO／PCOPPUSDM／DTWEXBGS 的觀察一致；但**不是**已證成的成因，且 UNRATE 的反例使「月頻 series 結構上取不到新值」這個較強說法不成立（只能說「CPI／M2 與模型一致」）。DTWEXBGS 近 12 列全是每週五（FACT）、且每次排程只新增 1 列，與「日頻」假設不符（頻率 NOT VERIFIED）。

### 2.3 離線算術：下次增量會被起點截掉的 series（純算術，不預測值）

全表最大日期 2026-11-05 → 下次增量 `observation_start`＝2026-11-06。頻率為本批假設（NOT VERIFIED）。

| series | 最新觀測日 | 假設頻率 | 下一個預期觀測 | 依模型是否被截掉 | 近期實際 |
|---|---|---|---|---|---|
| DGS10／DGS2／DGS3MO／BAMLH0A0HYM2 | 11-05 | 日 | 11-06 | 否 | 與模型一致 |
| WALCL | 11-04 | 週 | 11-11 | 否 | 與模型一致 |
| M2SL／CPIAUCSL | 04-01 | 月 | 05-01 起所有已發布月 | **是** | 與模型一致（仍停 04-01） |
| UNRATE | 10-01 | 月 | 11-01 | 是 | **反例**：10-01 當初也「應被截掉」卻出現了 |
| DTWEXBGS | 10-30 | 週（觀察）／日（腳本註解） | 11-06（週）／10-31（日） | 週頻否；日頻**是** | 頻率未定 |
| PPIACO／PCOPPUSDM | — | 月 | 任何早於 11-06 的觀測 | **是**（整段歷史） | 零列 |

---

## 3. 九項指標四層矩陣（有原料／可讀／具備正式金融語意／允許 UI 使用）

**欄位定義**：(1) 有原料＝Actions 快取有列。(2) 可讀＝現有程式能讀出，**且**能符合 New UI 現有序列契約。(3) 具備正式金融語意＝repo 內有正式裁示或契約說明觀測日、單位、日界線、公布日語意。(4) 允許 UI 使用＝已有客戶裁示或 Eligibility 准許進 New UI。**四欄各自獨立標註，不互相推論。**「New UI」指 `ui_v2`／`ui_v3` 目前接線的來源（皆為**即時 L1**，不讀快取）。

| 指標 | (1) 有原料 | (2) 可讀／符合契約 | (3) 具備正式金融語意 | (4) 允許 UI 使用 |
|---|---|---|---|---|
| **DGS10** | **YES／FACT**：3,855 列，2011-06-07～2026-11-05，落後 0 | **部分／FACT**：pyarrow 讀得出（`date`／`series_id`／`value`）；**但**餵給 `fred_yield_domain_from_l1` 會因無 `fetched_at` 欄而整批判「資料未備」（本批 30 列實測），須轉接補欄，而補什麼值＝語意爭點 | **部分／FACT**：`market_view` 檔頭明示 `obs_date`＝FRED 觀測日、非公布日，單位 `%`，缺值不補 0；**「從快取讀」的語意無任何裁示** | **即時版 YES／快取版 NO**：`DEC-2026-10-27-41`（客戶條件式裁示）＋`-44`（執行組讀法，非客戶裁示）→ 已接線即時 L1；快取來源無 DEC。`DEC-2026-11-09-06` G1 僅是候選監控清單，非 Eligibility |
| **DGS2** | 同 DGS10 | 同 DGS10 | 同 DGS10 | 同 DGS10 |
| **HY OAS**（BAMLH0A0HYM2） | **部分／FACT**：898 列，起 **2023-06-05**；週末列 12（A1 記為月底日），成因 NOT VERIFIED | **NO（契約）／FACT**：New UI 走 vintage（`fetch_fred_vintages`），需每期間 `release_date` 與 `realtime_floor`，快取只有 `date`／`value` → 無法產生 `credit_spread_pct` 列 | **部分**：單位 FRED Percent，B 線標 `pp`；Old UI 另以 `×100` 轉 bp（pp／bp 並存）；vintage 首次公布日語意為契約說明，**真實 FRED 回應 NOT VERIFIED** | **即時 vintage 版 YES／快取版 NO** |
| **VIX**（^VIX） | **YES／FACT**：3,881 列，→2026-11-06；含 A1 已證實的 2026-06-03 與參考不同（絕對差 0.2） | **NO（契約）／FACT**：無 bar 時間、無 `exchange_tz`、無 `fetched_at`；`rows_from_daily_close` 對本批以真實形態餵入的 30 列回「0 列＋取得時間缺」 | **部分**：`DEC-2026-11-09-10` Q1（休市日保留）、Q3（日界線**暫行**，非正式收盤判準）、Q4（06-03 證據保留、不覆寫、凍結風險後續研究）、Q5（維持 Yahoo 標示）；VIX 無 FRED 備援（`CLAUDE.md` §2.1） | **即時版 YES／快取版 NO** |
| **SPX**（^GSPC） | **YES／FACT**：3,879 列，→2026-11-06；A1 已證實 06-03 異常（快取 7595.98 vs 參考 7553.68，疑似盤中凍結，啟發式） | 同 VIX | 同 VIX；`^GSPC` 時區字串樣態**無證據**（探測清單未含） | **即時版 YES／快取版 NO** |
| **TWII**（^TWII） | **YES／FACT**：3,762 列，→2026-11-06；**週末列 1**（2026-09-20，與前一交易日同值） | 同 VIX | `DEC-2026-10-27-43`（客戶裁示）：僅 Yahoo `^TWII` 作指數價格／歷史，標示固定 `Yahoo Finance (^TWII)`；Q2：週末排除只是現行行為，**不擴大為已驗證交易日規則**，補班日待證據 | **即時版 YES／快取版 NO** |
| **FEDFUNDS** | **NO／FACT**：**不在**腳本 `FRED_SERIES_IDS`（宣告的 11 項不含），parquet 無此 series | **NO**（無資料可讀） | **部分**：月頻（月均）、`%`；New UI 取首次公布日；FRED 日期慣例真實回應 NOT VERIFIED | **即時 vintage 版 YES／快取版不存在** |
| **CPI**（CPIAUCSL） | **部分／FACT**：178 列，→**2026-04-01**（落後 218 天）；缺 2025-10（與 UNRATE 同月缺，來源端缺為 INFERENCE） | **YES（讀得出）／FACT**；日期多落在週六日＝月初觀測日，**正常**，不可套 Q2 週末排除 | **部分**：YoY 在 Old UI 以列數位移 `shift(12)` 自算（假設無缺月；缺 2025-10 使其後基期錯位，引自既有研究文件、本批未重算）；發布約月後 13 日（`CLAUDE.md` §2.3）；回測須用 release_date | **NO（New UI）／FACT**：`ui_v2`／`ui_v3`／`services/v2_tables`／`services/v2_domain` 對 `CPIAUCSL` 與 `M2SL` 命中 0（範圍＝這四個目錄的 `*.py`）；僅 Old UI 使用；無任何准許進 New UI 的裁示 |
| **M2**（M2SL） | **部分／FACT**：179 列，→2026-04-01（落後 218 天），無缺月 | 同 CPI | **部分**：十億美元→YoY%（Old UI 自算）；發布約月後 7–30 天（§2.3） | **NO（New UI）**；僅 Old UI |

**表尾（硬規則）**：**任一欄的 YES 不推出下一欄。** 例：DGS10 有原料（1）與讀得出（2）不代表快取版具備正式金融語意（3），更不代表允許進 UI（4）；VIX／SPX／TWII 的即時版已被允許（4）不代表快取版被允許；CPI／M2「有舊值」不代表更新可信（落後 218 天）。

另：B 線 `term_spread_pct` 用 FRED **T10Y2Y**（不在快取）。`services/macro/validation.py::load_indicators_from_parquet` 的 `YIELD_10Y2Y`＝DGS10−DGS2 是**另一種自算**，與 T10Y2Y 是否一致**未驗**；任何「用 DGS10−DGS2 取代 T10Y2Y」都是新公式／語意決定，**本文不建議**。

---

## 4. 接線差距清單（「New UI 讀快取」要補什麼；編號 W1～W12，與第 0 節的 Gate G1～G6 不同）

| # | 差距 | 現況（標籤） | 影響／需要 |
|---|---|---|---|
| W1 | **日期語意** | 快取 Yahoo 日期＝runner 本地時區的列日期；即時 L1 的觀測日＝來源自報的交易所時區的當地日期，且受「取得時刻界線」約束（FACT）。快取沒存 `exchange_tz`；A1 與參考檔在參考窗內日期相符，與無位移相容，但窗有限（引用） | 快取無法重現「交易所時區」判定；若硬編時區＝違反 `rows_from_daily_close`「不推定」原則→需裁示（G3） |
| W2 | **進行中 bar／凍結列** | 寫入端不過濾進行中的根；2026-06-03 的 SPX、VIX 疑似盤中凍結（啟發式），且增量起點使其永不回頭修正（引用 A1／研究文件）。`DEC-2026-11-09-10` Q4：不覆寫快取、不改計算 | 讀快取＝把已知可疑列原樣顯示，且 L2 現有規則看不到它（無 bar 時間）。故 α 最窄版**不納入 Yahoo 三指數** |
| W3 | **週末／假日列** | VIX／SPX 週末列 0、TWII 1；HY 有月底週末列；月頻序列的觀測日多為週末（正常）（FACT） | Yahoo 轉接可套週末規則；**FRED 序列不得套 Q2 週末排除**（會誤刪月頻與 HY 月底列）。Q2 明示不擴大為已驗證交易日規則 |
| W4 | **歷史長度** | DGS 自 2011（約 15 年）；HY 自 2023-06；`market_view` 需 Yahoo 5y／FRED 1500 筆（FACT） | DGS 足夠；HY 覆蓋 3Y 視窗只勉強；FEDFUNDS 無 |
| W5 | **時效與 stale 標示** | 排程每週一次；DGS 最壞可落後約一週加部署延遲（INFERENCE）。`metadata.updated_at` 是批次時間（第 1.4 節） | 以「最後觀測日＋落後天數」為主；**不得用 `updated_at` 當 `fetched_at`**；「過期」門檻屬 Stop Gate，本文不訂 |
| W6 | **缺 series fail-loud（missing≠0）** | `load_indicators_from_parquet` 缺檔／壞檔只 `print`、該 key 不存在，無原因碼，且非運行時用（FACT） | 新讀取器必須回 `(frame, error)`，分別處理：檔缺、檔壞、series 缺、零列、過舊；**不得沿用 print＋吞例外風格** |
| W7 | **與 vintage 路徑不相容** | HY／T10Y2Y／FEDFUNDS 在 New UI 走 `fetch_fred_vintages`；快取只有 `date`／`value`，且增量不重抓舊期間，**修正版次永不更新**（FACT／INFERENCE） | 快取**不能替代**這三鍵；最多服務 `market_view` 的日頻序列 |
| W8 | **部署面** | `data_cache/*.parquet`＋`metadata.json` 受 git 追蹤，cron 以 bot 身分 push 到預設分支（FACT）。**Streamlit Cloud 如何取得快取：repo 內無證據（NOT VERIFIED）**——無部署設定檔可證主檔、分支、是否重新拉取。New UI 入口為獨立的 `ui_v2/app_*_live.py`／`ui_v3/app_preview.py`，`app.py` 並不 import `ui_v2`／`ui_v3`（FACT，範圍：`app.py` 與 `ui/`） | 運行中的 process 看到的是**最近一次部署時的檔案**，不是即時；實際新鮮度＝cron＋Cloud 重拉延遲，無上限證據 |
| W8b | **寫入端與讀取端版本不一致（新發現）** | 快取檔的 parquet 中繼資料：`created_by` 為 pyarrow **26.0.1**，pandas 中繼為 **3.1.1**（四檔皆然，FACT）。但 `requirements.txt` 釘 `pyarrow>=14,<25`、`pandas>=2.3.3,<3.0`（雲端 py3.14 當機史）；寫入的 workflow 是未釘版本的 `pip install pandas pyarrow`（FACT） | 讀取端在受釘版本下能否讀這四檔：**NOT VERIFIED**（本批環境無法安裝 pandas 2.x／pyarrow 24.x）。這是任何「Streamlit 讀快取」方案的 P0 實測項 |
| W9 | **分層（新增 L1 函式）** | parquet 讀取是 I/O：L2 不得 I/O（`CLAUDE.md` §8.2）；`market_view` 檔頭禁止新增 L1 函式；`ui_v3` adapters 自述不直接 import L1（FACT） | 需新增一支唯讀 L1 讀取器（建議置於 `repositories/macro/`）＋ L2 轉接；屬 Gate G2。可重用：`build_market_view` 已接受注入式 `fetch_fred`（簽名 `(series_id, api_key, n)`），純函式 `fred_yield_domain_from_l1` **不可原樣重用**：它要求 UTC 帶時區的 `fetched_at` 欄，缺則整批判「資料未備」（本批實測），而本文禁止以批次時間或現在時間補（W10）。需新增專用轉接純函式（如 `fred_yield_domain_from_cache`，名稱為候選）或修改該函式契約，二者皆屬 Gate G2／G3（見 5.1 α 變更清單） |
| W10 | **契約欄位缺口** | `fred_yield_domain_from_l1` 要 `date`、`value`、`fetched_at`（UTC 帶時區）；快取只有前兩欄（FACT，本批實測） | 補 `fetched_at` 的值＝W5 與 Gate G3 的語意爭點；不得以現在時間補 |
| W11 | **原因碼與文案** | 現有：缺 Key→`not_configured`、L1 錯誤→`fetch_failed`、缺 fetched_at→`資料未備`。讀快取後出現新失效模式：檔缺／壞／cron 沒跑／某 series 停更／含凍結列 | 新原因碼同步 `shared/ui_semantics/rules.py`（adapters 不得 import shared，故另存並以測試鎖）；新文案受 `APPROVED_WORDING` Gate，**本文不擬文案** |
| W12 | **公式一致性** | `load_indicators_from_parquet` 的 YoY 用列數位移；Old UI `us_indicators` 另有自己的 YoY（FACT） | 接線**不得**順手把這些公式併進 New UI（金融公式屬 Stop Gate；`PROJECT_RULES.md` 13.1「禁止第二套平行金融計算 SSOT」） |

---

## 5. 三種接線方案比較

**共同前提**：不動 FX Gate、Eligibility、金融公式、OneBrain；B 線 vintage（HY／T10Y2Y／FEDFUNDS）三方案皆**維持即時取數**；Old UI（`ui/`、`services/macro/us_indicators.py`）三方案皆不改（它不經 `market_view`／`market_indicator`，INFERENCE，範圍：`ui/` 與 `app.py` 對 `market_view` 無 import）。速度、Token、維護成本為相對估計（INFERENCE）。

### 5.1 比較表

| 項目 | **α 備援（失敗才讀快取）** | **β 快取為主、即時為輔** | **γ 全改快取** |
|---|---|---|---|
| 做法 | 即時 L1 成功→行為完全不變；僅當 domain 為「系統錯誤」**且原因不是缺 Key**（`MISSING_FRED_API_KEY` 路徑不回退、維持「尚未設定」）才改讀快取，並明標「來源＝Actions 快取、快取最後觀測日、已落後 N 天」。**最窄版只含 `us10y`／`us2y`** | 先讀快取；快取缺、過期（需定義）或使用者要求重新整理時才打即時 L1 | `market_view` 不再呼叫 L1 Yahoo／FRED |
| 具體變更檔案與符號（候選） | 新增 `repositories/macro/` 下唯讀讀取器（回 `(frame, error)`）；`services/v2_tables/market_view.py`：`build_market_view` 殖利率迴圈加回退分支（新增注入參數）；**必要轉接**：新增專用純函式（候選 `fred_yield_domain_from_cache`，收讀取器的 `(frame, error)`、快取最後觀測日與「現在」由呼叫端傳入，不補 `fetched_at`）或改 `fred_yield_domain_from_l1` 契約；其測試（缺 `fetched_at` 時不得冒充、不補 0、落後天數計算）；Gate：G2（`market_view` 檔頭禁止新增 L1 函式）、G3（不得新增狀態詞，`DEC-2026-11-09-10` ③）、G6（凍結面）。**接線位置**：設計成 `build_market_view` 的 opt-in 參數（預設關），只由 `ui_v3/adapters/market_page.py::load` 開啟，使 `ui_v2/mkt/source.py` 不必改動（G6 建議）；若改為由 `ui_v2/mkt/source.py::load_live` 傳入則需 G6 例外；`ui_v3/adapters/market_page.py::load` 與 `domain_state`（若需新原因碼→`shared/ui_semantics/rules.py`）；測試；`docs/DECISIONS.md` | α 全部＋`build_market_view` 流程反轉、`ui_v2/mkt/source.py`、shell 的 refresh 流程（現為 `refresh_not_wired`）、Yahoo 三指數的「快取列」收盤／時區處置規則 | β 全部＋移除即時支路與其冷卻／Key 邏輯；B 線 vintage 無法由快取取代→要嘛九項不可完整達成，要嘛改 44 資料契約（`release_date` 不可空） |
| 測試 | 缺檔／壞檔／零列／缺 series；不得補 0；不得標成即時；來源字串與最後觀測日與落後天數；L2 不 I/O 的分層守衛；**「即時成功時完全不讀快取」的突變測試**（拿掉回退，行為必須不變） | α 全部＋兩來源不一致時的優先序、凍結列顯示、快取與即時混用時 `obs_date` 連續性、批次時間作 `fetched_at` 時的落後天數語意 | β 全部＋移除即時路徑後的回歸；「cron 沒跑」情境；Old／New 一致性 |
| 正確性／風險 | **低**。成功路徑零變更；風險＝把停更快取當可用資料（CPI／M2 型態）；另若回退涵蓋缺 Key，會遮蔽 Cloud 端 FRED Secrets 失效訊號——故最窄版不含缺 Key（見 5.3）→以最後觀測日與落後天數揭露、不訂門檻。DGS 內部缺口（S1 型）仍不揭露（INFERENCE） | **中高**。需先裁示「過期」定義、快取與即時 `obs_date` 等價語意（W1）、凍結列處置（W2）、部署新鮮度（W8）；使用者看到的最新值可能落後即時一週以上 | **高**。凍結列、停更序列、台股週一延遲直接成為使用者所見；失敗模式變成「cron 沒跑」且使用者端無法重取；Old／New 不一致加劇；移除即時路徑的驗證成本不可逆 |
| 速度 | 不變（仍每次打 L1），只提高可用性 | 明顯加速（免 Yahoo／FRED 往返、免 429 冷卻、免 Key） | 最快 |
| Token（維護 AI 的脈絡成本） | 低 | 中高（兩套語意並存） | 最高（含契約修訂與回歸） |
| 維護成本 | 低（一支讀取器＋一個分支） | 中高 | 最高 |
| Old UI 是否不變 | **是** | 程式不變，但同一指標 Old（即時）與 New（快取）可能出現不同日期或數值→觸及 `PROJECT_RULES.md` 13.3 | 程式不變，落差最大 |
| 達成客戶方向「優先讀快取」 | 最低（僅備援） | 達成 | 完全達成但九項不可完整 |
| 所需 Decision Gate | G1（新 production 資料路徑）、G2（新增 L1 函式與轉接純函式）、G3（日期語意／標示、不新增狀態詞）、G6（凍結面／`ui_v2` maintenance-only）；G4 視是否先修生產端 | α 全部＋G5（過期門檻、一致性）＋正式日期語意；Eligibility **不可**藉此解鎖（`DEC-2026-11-09-06` ④） | 新／替換 production data source、44 資料契約（`release_date`）、日期語意、新鮮度語意——全部觸發 |

### 5.2 推薦（**未經客戶裁示；總管讀法，可被推翻**）

**推薦 α 最窄版（只含 DGS10／DGS2），作為通往 β 的第一步而非終點。** 理由：(1) 唯一不改變任何現有成功路徑；(2) DGS10／DGS2 欄位契約最乾淨、無 bar 時間問題；(3) 避開 Yahoo 快取的已證實可疑列與暫行日界線；(4) 不碰 vintage、FX Gate、Eligibility；(5) 可用它實測 W8、W8b、W5 這幾個目前 NOT VERIFIED 的前提，再決定是否升級。

### 5.3 α 最窄版的設計邊界（候選，未核准）

- 只覆蓋 `us10y`／`us2y`；Yahoo 三指數、B 線三鍵、其餘 domain 不碰。
- **不涵蓋缺 Key**（S3）：缺 `FRED_API_KEY` 時維持現行 `not_configured`（「尚未設定」）畫面，不改讀快取。理由：若缺 Key 也回退，Cloud 端 FRED Secrets 失效（`MISSING_FRED_API_KEY`）會被快取資料遮蔽成「看似有資料」，客戶目前正需要這個訊號來驗證 Secrets 是否生效。回退只對「有 Key 但取數失敗」這一種錯誤；兩種畫面必須可區分，並以測試鎖住（缺 Key→不讀快取）。風險：遮蔽 Secrets 失效訊號已列入 5.1「正確性／風險」。
- 顯示欄位僅：值與其觀測日（FRED 觀測日；最新一點的觀測日即「快取最後觀測日」，不重複列兩個欄位）、「已落後 N 天」、固定來源字串（不得沿用 `FRED (DGS10)` 讓人誤以為即時）。不顯示、不暗示新鮮度判定。
- 不新增狀態詞；用現有 `ok` 加來源字串（G3 待裁）。
- 缺檔／壞檔／series 缺／零列各有原文，**不補 0、不回傳假資料**；缺 `fetched_at` 時的 `fetched_at` 不得以批次時間或現在時間冒充。

### 5.4 不選 β／γ 的條件

β 要等：P1 生產端修補完成並經 A1 守衛重驗、W8／W8b 實測有結果、G5 過期定義獲裁示。γ 在 HY／T10Y2Y／FEDFUNDS 仍需即時 vintage 的前提下，**不應成為目標**，除非客戶改裁 44 資料契約。

### 5.5 生產端候選修補（僅列出，**未核准、非建議動工**）

| 候選 | 改什麼 | 新外部請求 | Stop Gate 風險 |
|---|---|---|---|
| per-series 增量起點（各 series 自己的最大日期＋1；缺列者用 bootstrap 起點） | `update_one`／`fetch_fred_indicators` | 之後執行時多取少量歷史 | 觸及資料取得語意；需 Gate 判定是否算 production data source 行為變更 |
| 重疊窗口自癒（每次重抓最近 N 期並覆蓋） | 同上，`_merge_dedupe` 已 `keep="last"` | 是（同源，量小） | 覆寫既有列＝改歷史列語意；與 `DEC-2026-11-09-10` Q4 相鄰，需另行明示 |
| series 完整性檢查（宣告 vs 實際、落後天數、失敗即非零結束碼或寫狀態） | 離線檢查可擴充 A1；改結束碼＝改 workflow 行為 | 否 | 離線版低；改 workflow 行為需授權 |
| metadata 補 `fetched_at`／`source`／per-series 狀態 | `main()` 的 metadata 輸出 | 否 | 低～中；目前非測試的 metadata 讀取者只有 A1 的 `load_metadata`（FACT，範圍：`*.py` 非測試） |
| workflow `years` 預設 15 與腳本 35 不一致 | workflow 或腳本 | 否 | 低，僅文件化亦可 |
| 讓 workflow 釘 pandas／pyarrow 版本 | workflow `pip install` | 否 | 低～中（W8b） |

---

## 6. market_view 檔頭「不新增 L1 函式」的出處與解除條件（抽查 d）

- **原文**（FACT）：`services/v2_tables/market_view.py` 檔頭「硬邊界」段：「不新增 L1 函式、不新增 host / API、不新增 FRED series、不新增 `INDICATOR_SPECS` 鍵；只用 B 線已經在打的同一個 Yahoo 端點與同一個 FRED 端點」。
- **出處**：該段承接 `DEC-2026-10-27-41`（客戶裁示，條件式「若既有 source 已有…可以盤點並接入新的 Data View」，且該筆明寫「本筆不授權新增未核准 API／新 host」）、`DEC-2026-10-27-42`（c）（執行組讀法：不改 `INDICATOR_SPECS`／`market_indicator` 表，改為另建唯讀 L2 Data View；改表屬 44 資料契約變更）與 `-44`（執行組讀法：通道盤點確認屬既有通道）。
- **解除條件**：repo 內**未見專屬的解除條件**，也未見單獨一筆 DEC 訂出「禁止新增 L1 函式」。本淺層 clone 看不到引入該句的提交（可見最早提交即為 `b816df1c`）。INFERENCE：它是上述客戶條件式裁示的實作層落字，所以解除應走客戶裁示（G2）而不是總管單方放寬。
- 另：`docs/v2/44` 已凍結，其 `market_indicator` 表 `release_date` 可空為「否」；快取版不能產生這類列（第 3 節 HY）。`docs/v2/57`（子法 1 修正案 #8）與本題無實質關聯（以 market／市場／指標來源／L1／新增函式／fetch 關鍵字檢索，無命中）；`docs/v2/69` 的 G-CACHE-1／G-CACHE-2 與 Cross-View 規則見 G5／5.1。

---

## 7. 未涵蓋與限制

- **未連網**：FRED／Yahoo 真實回應（含 `observation_start` 對各 series 的實際過濾行為）、Streamlit Cloud 實際部署分支與重拉行為、cron 實際執行延遲、Actions 執行紀錄，皆 NOT VERIFIED。
- 合成資料測試只證明**機制**，不證明真實成因；UNRATE 反例與 DTWEXBGS 頻率未解。
- git 歷史限本 clone 淺層可見的三筆 `fred_indicators.parquet` 提交；更早的提交（含 bootstrap 當次）本批看不到。
- 讀取端受釘版本（pandas 2.x／pyarrow 24.x 以下）讀這四檔的結果未驗（W8b）。
- 未讀 `shared/ui_semantics/rules.py` 全文；`docs/v2/69` 僅讀快取相關列。
- 九項指標的「具備正式金融語意」欄只依 repo 內已有裁示與契約文字判定，不代表金融上已被核准；任何升級都需 Gate。
- 本文的所有計數（列數、起訖日、落後天數）是 2026-11-10 在基準 `c11aca98` 的量測值，會漂移；引用前請重跑。
- 未做：任何寫入、重抓、探測、修補、接線實作。

---

## 附錄 A：測試與探針腳本（全文）

### A.1 `test_fred_incremental_mechanism.py`（機制測試；7 項檢查）

用法（repo 工作樹根目錄；`PYTHONPATH` 需含本機可用的 pyarrow 路徑，不需網路）：

```
PYTHONPATH=.:<site-packages>:<含 pyarrow 的路徑> python3 test_fred_incremental_mechanism.py
```

```python
#!/usr/bin/env python3
"""唯讀機制測試：全表最大日期增量起點 vs FRED 個別 series 漏抓（合成資料，不連網，不寫 repo）。
用法（repo 工作樹根目錄，路徑為範例）：
  PYTHONPATH=<pa_site>:.:/usr/local/lib/python3.13/site-packages python3 test_fred_incremental_mechanism.py
"""
import datetime as dt, sys, tempfile, importlib
from pathlib import Path
import pandas as pd

sys.path.insert(0, ".")
M = importlib.import_module("scripts.update_macro_history") if Path("scripts/__init__.py").exists() else None
if M is None:
    import importlib.util
    spec = importlib.util.spec_from_file_location("umh", "scripts/update_macro_history.py")
    M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)

D = dt.date
FAKE_KEY = "k" * 8  # 假值，執行期組成，非真實 Key
WORLD: dict[str, list] = {}   # series_id -> [(date, value)]  模擬 FRED 當下已公布的觀測
FAIL: set = set()             # 本次取數失敗(回空)的 series

def fake_get(sid, start, end, api_key):
    if sid in FAIL or sid not in WORLD:
        return pd.DataFrame()
    rows = [(d, v) for d, v in WORLD[sid] if start <= d <= end]   # 模擬 observation_start/end 過濾
    return pd.DataFrame(rows, columns=["date", "value"]) if rows else pd.DataFrame()

def setup(tmp, ids):
    M.CACHE_DIR = Path(tmp); M.META_PATH = Path(tmp) / "metadata.json"
    M._fred_get_single = fake_get
    M._FRED_INTER_CALL_SLEEP_SEC = 0.0
    M.FRED_SERIES_IDS = tuple(ids)

def run(today, bootstrap=False, years=1):
    return M.update_one("fred_indicators", today, bootstrap, years, FAKE_KEY)

def cache():
    return pd.read_parquet(Path(M.CACHE_DIR) / "fred_indicators.parquet")

def dates(df, sid):
    return sorted(pd.to_datetime(df[df.series_id == sid].date).dt.date)

def weekly(start, end, step=7):
    out, d = [], start
    while d <= end:
        out.append((d, 1.0)); d += dt.timedelta(days=step)
    return out

def per_series_fetch(start_by, today, api_key):
    """S4 對照：每個 series 用自己的最大日期+1 當起點（僅測試內模擬）。"""
    frames = []
    for sid in M.FRED_SERIES_IDS:
        df = fake_get(sid, start_by(sid), today, api_key)
        if not df.empty:
            df = df.copy(); df["series_id"] = sid; frames.append(df[["date", "series_id", "value"]])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["date","series_id","value"])

def per_series_update(existing, today):
    def start_by(sid):
        sub = existing[existing.series_id == sid] if existing is not None else None
        if sub is None or sub.empty:
            return today - dt.timedelta(days=365)
        return pd.to_datetime(sub.date).max().date() + dt.timedelta(days=1)
    new = per_series_fetch(start_by, today, FAKE_KEY)
    return M._merge_dedupe(existing, new, key=["date", "series_id"])

results = {}
def check(name, cond, note=""):
    results[name] = bool(cond); print(("PASS " if cond else "FAIL ") + name + (" | " + note if note else ""))

# ---------- S1 ----------
with tempfile.TemporaryDirectory() as tmp:
    setup(tmp, ["X", "Y"])
    WORLD.clear(); FAIL.clear()
    WORLD["X"] = weekly(D(2026,4,1), D(2026,5,20)); WORLD["Y"] = weekly(D(2026,4,2), D(2026,5,20))
    run(D(2026,5,3), bootstrap=True)                       # run1：X、Y 皆有至 ~05-01
    FAIL.add("X"); meta2 = run(D(2026,5,10))                # run2：X 取數失敗、Y 成功並前進
    c2 = cache()
    check("S1.meta_hides_failure", meta2["last_error"] is None and meta2["last_updated"] == max(dates(c2,"Y")).isoformat(),
          f"last_error={meta2['last_error']} last_updated={meta2['last_updated']}")
    FAIL.clear(); run(D(2026,5,24))                         # run3：X 恢復
    c3 = cache(); x = dates(c3, "X"); missing = [d for d,_ in WORLD["X"] if d not in x and d <= D(2026,5,24)]
    check("S1.failed_week_never_backfilled", D(2026,5,6) in missing,
          f"X 永久缺的觀測日={[str(m) for m in missing]}")
    # S4 對照
    WORLD["X"] = weekly(D(2026,4,1), D(2026,5,20)); FAIL.clear()
    base = M._merge_dedupe(None, fake_get("X", D(2026,4,1), D(2026,5,1), ""). assign(series_id="X")[["date","series_id","value"]], ["date","series_id"])
    base = M._merge_dedupe(base, fake_get("Y", D(2026,4,1), D(2026,5,8), "").assign(series_id="Y")[["date","series_id","value"]], ["date","series_id"])  # X 當週失敗，Y 前進
    after = per_series_update(base, D(2026,5,24))
    xs = dates(after, "X")
    check("S4.per_series_start_recovers_S1", all(d in xs for d,_ in WORLD["X"] if d <= D(2026,5,24)))

# ---------- S2 ----------
with tempfile.TemporaryDirectory() as tmp:
    setup(tmp, ["DGS"])
    WORLD.clear(); FAIL.clear()
    WORLD["DGS"] = weekly(D(2011,6,6), D(2026,6,1), 1)
    run(D(2026,6,2), bootstrap=True, years=15)
    WORLD["NEW"] = weekly(D(2011,6,1), D(2026,6,26), 7) # 後加入的新 series（含完整歷史）
    WORLD["DGS"] = weekly(D(2011,6,6), D(2026,6,26), 1)
    M.FRED_SERIES_IDS = ("DGS", "NEW")
    run(D(2026,6,28))
    c = cache(); n = dates(c, "NEW")
    check("S2.new_series_history_not_backfilled", len(n) <= 4 and min(n) >= D(2026,6,2),
          f"NEW 列數={len(n)} 起={min(n)}（世界上有 ~{len(WORLD['NEW'])} 列）")
    after = per_series_update(c.iloc[0:0] if False else c[c.series_id != "NEW"], D(2026,6,28))
    # S4：NEW 無列 → 起點=今日-365 → 取 1 年（腳本內 years 邏輯）；仍非全歷史，但遠多於 S2
    n4 = dates(after, "NEW")
    check("S4.per_series_gives_more_for_new_series", len(n4) > len(n), f"S4 列數={len(n4)}（仍受『缺列起點=today-365』限制，非完整 15 年）")

# ---------- S3 ----------
with tempfile.TemporaryDirectory() as tmp:
    setup(tmp, ["DGS", "CPI"])
    WORLD.clear(); FAIL.clear()
    WORLD["DGS"] = weekly(D(2026,1,1), D(2026,5,29), 1)
    WORLD["CPI"] = [(D(2026,1,1),1.0),(D(2026,2,1),1.0),(D(2026,3,1),1.0),(D(2026,4,1),1.0)]  # 5/1 觀測尚未公布
    run(D(2026,5,31), bootstrap=True, years=1)
    WORLD["DGS"] = weekly(D(2026,1,1), D(2026,6,5), 1)
    WORLD["CPI"].append((D(2026,5,1), 1.0))               # 5/1 觀測此時已公布（觀測日 < 全表最大日期）
    meta = run(D(2026,6,7))
    c = cache(); cp = dates(c, "CPI")
    check("S3.monthly_obs_before_global_max_never_fetched", D(2026,5,1) not in cp and meta["last_updated"] == "2026-06-05",
          f"CPI 最新={max(cp)}；全表最大日期={meta['last_updated']}；增量 start=2026-06-01 之後(依 last+1)")
    after = per_series_update(c, D(2026,6,7))
    check("S4.per_series_start_recovers_S3", D(2026,5,1) in dates(after, "CPI"))

# ---------- 真實快取離線算術 ----------
real = pd.read_parquet("data_cache/fred_indicators.parquet"); real["date"] = pd.to_datetime(real.date)
gmax = real.date.max(); incr_start = gmax + pd.Timedelta(days=1)
print("\n全表最大日期", gmax.date(), "→ 下次增量 observation_start =", incr_start.date())
decl = ("DGS10","DGS2","DGS3MO","BAMLH0A0HYM2","M2SL","WALCL","CPIAUCSL","UNRATE","DTWEXBGS","PPIACO","PCOPPUSDM")
freq = {"DGS10":"D","DGS2":"D","DGS3MO":"D","BAMLH0A0HYM2":"D","DTWEXBGS":"D?","WALCL":"W","M2SL":"M","CPIAUCSL":"M","UNRATE":"M","PPIACO":"M","PCOPPUSDM":"M"}
g = real.groupby("series_id").date.agg(["count","max"])
print("series | rows | max | 落後全表(天) | 假設頻率(NOT VERIFIED) | 下一個預期觀測日 | 會被增量起點截掉?")
for s in decl:
    mx = g.loc[s,"max"] if s in g.index else None
    cnt = int(g.loc[s,"count"]) if s in g.index else 0
    f = freq[s]
    if mx is None:
        nxt = "n/a(零列：歷史永不補，只取 >= 增量起點)"; cut = "是(整段歷史)"
    else:
        if f == "M": nxt = (mx + pd.offsets.MonthBegin(1))
        elif f == "W": nxt = mx + pd.Timedelta(days=7)
        else: nxt = mx + pd.Timedelta(days=1)
        cut = "是(下一觀測日 < 增量起點，且其後所有已發布月份亦然)" if nxt < incr_start else "否(下一觀測日 >= 增量起點)"
        nxt = nxt.date()
    lag = (gmax - mx).days if mx is not None else "n/a"
    print(f"{s} | {cnt} | {mx.date() if mx is not None else '-'} | {lag} | {f} | {nxt} | {cut}")

print("\nSUMMARY", results)
sys.exit(0 if all(results.values()) else 1)
```

### A.2 `probe_contract.py`（抽查 c：真實快取形態餵入現有 L2 契約；記憶體內，不寫檔）

```python
import pandas as pd
from services.v2_tables import market_indicator as mi, market_view as mv
# --- Yahoo-shaped: 讀真實 vix parquet 的形態 (date 欄 = python date, attrs 空)
v = pd.read_parquet("data_cache/vix_history.parquet")
s = pd.Series(v["close"].values, index=pd.to_datetime(v["date"]))   # 讀者最自然的轉換
s.attrs = {}   # 與真實 parquet 相同：無 fetched_at / exchange_tz
print("attrs on loaded frame:", v.attrs)
r = mi.rows_from_daily_close("vol_index", s.tail(30), None, value_unit="index", obs_date_rule=mi.OBS_DATE_SAME_DAY)
print("rows_from_daily_close ->", "rows=%d"%len(r[0]), "error=", r[1], "skipped=", r[2])
# --- FRED-shaped: date 欄 python date, 無 fetched_at 欄
f = pd.read_parquet("data_cache/fred_indicators.parquet")
d10 = f[f.series_id=="DGS10"][["date","value"]].tail(30).copy(); d10["date"]=pd.to_datetime(d10["date"])
dom = mv.fred_yield_domain_from_l1("us10y", d10, None, source_label="FRED (DGS10)")
print("fred_yield_domain_from_l1 (no fetched_at) -> status=%s reason_code=%s reason=%s points=%d" % (dom["status"], dom["reason_code"], dom["reason"], len(dom["points"])))
# --- 補一欄 fetched_at(批次時間) 後 : 示範契約可通過，並不代表語意被核准
d10b = d10.copy(); d10b["fetched_at"]="2026-11-08T04:07:01+00:00"
dom2 = mv.fred_yield_domain_from_l1("us10y", d10b, None, source_label="FRED (DGS10)")
print("with synthetic fetched_at -> status=%s obs_date=%s points=%d (示範，非建議)" % (dom2["status"], dom2["obs_date"], len(dom2["points"])))
```

### A.3 `probe_diff.py`（抽查：提交間集合比對，`git show` 進記憶體，不寫檔）

```python
import subprocess, io
import pandas as pd
def load(c):
    raw = subprocess.run(["git","show",f"{c}:data_cache/fred_indicators.parquet"],capture_output=True,check=True).stdout
    return pd.read_parquet(io.BytesIO(raw))
for a,b in [("b816df1c","20bf6442"),("20bf6442","8ca33547")]:
    A,B = load(a),load(b)
    ka = set(zip(A.date.astype(str),A.series_id));
    new = B[[ (str(d),s) not in ka for d,s in zip(B.date,B.series_id)]]
    gm = max(pd.to_datetime(A.date)).date()
    print(a,"->",b,"prev global max",gm,"added rows",len(new),"removed",len(ka-set(zip(B.date.astype(str),B.series_id))))
    print(new.groupby("series_id").date.agg(lambda s: f"{min(s)}..{max(s)} n={len(s)}").to_string())
    # changed values on overlap
    m = A.merge(B,on=["date","series_id"],suffixes=("_a","_b")); print(" overlap value changes:", int((m.value_a!=m.value_b).sum()))
```

---

## 附錄 B：抽查結果表（本批自行執行；含被修正之處）

基準：`c11aca98`；工作樹為 `git worktree`，抽查全程唯讀。

| # | 抽查項 | 方法 | 結果 |
|---|---|---|---|
| a | 重跑機制測試 | 執行附錄 A.1 | 7 項全數 PASS（4 項驗生產碼機制、3 項為 `S4.*` 模型對照）；monkeypatch 覆蓋唯一的 FRED 網路函式，未見任何外部請求；匯入 `streamlit` 的設定警告只是副作用輸出；工作樹無變更 |
| b | 運行時 0 條路徑讀 `data_cache` parquet | `git grep` `ui`、`ui_v2`、`ui_v3`、`app.py`、`services/v2_tables` 對 `parquet`／`data_cache` | **確認**：僅 `ui/sidebar.py` 一則「嚴禁清 data_cache」說明字串；全 repo 非測試、非 `scripts` 的 `read_parquet` 只在 `services/macro/validation.py`（兩處）；`load_indicators_from_parquet` 的呼叫者＝`scripts/calibrate_macro_score.py` 與同檔 `calc_macro_score_series`，後者本身在非測試程式中無呼叫者（動態呼叫未涵蓋） |
| c | 四檔 `attrs` 空、`date` 為 Python `date`；L2 遇此型態整批不寫 | pyarrow 實讀＋記憶體呼叫現有函式 | **確認**：四檔 `attrs={}`、`date` 皆 Python `date`；`rows_from_daily_close`（VIX 末 30 列）→0 列、原因「取得時間缺」；`fred_yield_domain_from_l1`（DGS10 末 30 列、無 `fetched_at`）→`資料未備`；人工補一欄 `fetched_at` 後可通過（僅示範契約，不代表該值語意獲准） |
| d | `market_view` 檔頭禁令原文與出處 | 讀檔頭＋檢索 DEC | **確認原文**；出處為上述 DEC 的實作層落字，**無專屬解除條件**（第 6 節） |
| e | HY／FEDFUNDS 在 New UI 走 vintage | `git grep` `market_indicator`／`fred_vintage` | **確認**：`INDICATOR_SPECS` 的 `credit_spread_pct`／`policy_rate_pct`（及 T10Y2Y）經 `fetch_fred_vintages_with_error` |
| f | CPI／M2 在 New UI 0 命中 | `git grep CPIAUCSL\|M2SL\|FRED_CPI\|FRED_M2` 於 `ui_v2`、`ui_v3`、`services/v2_tables`、`services/v2_domain` | **確認 0 命中**（範圍僅此四目錄的檔案） |
| g | FEDFUNDS 不在腳本 `FRED_SERIES_IDS` | 以正則解析腳本常數 | **確認**：11 項為 DGS10／DGS2／DGS3MO／BAMLH0A0HYM2／M2SL／WALCL／CPIAUCSL／UNRATE／DTWEXBGS／PPIACO／PCOPPUSDM；`FEDFUNDS` 只出現在 `shared/fred_series.py` 常數（供 New UI 即時取數用） |
| h | `metadata.updated_at` 語意 | 讀 `main()` | **確認**：每次執行重寫為當下 UTC 時間；`last_updated` 為各表最大資料日期；兩者皆非逐 series 取得時間；且因 `updated_at` 每次改變，每次排程都有 diff |
| i | 部署面 | `git ls-files`、`git check-ignore`、讀 workflow、找部署設定 | **確認**：五個檔受 git 追蹤、未被 `.gitignore` 排除；cron 以 bot push；**Cloud 如何取得快取 repo 內無證據（NOT VERIFIED）**；repo 無 `runtime.txt`／`packages.txt`／`.python-version` |
| j | requirements 釘版 | 讀 `requirements.txt` | **確認**：`pyarrow>=14,<25`、`pandas>=2.3.3,<3.0`；**補充（草稿未查）**：四檔由 pyarrow 26.0.1／pandas 3.1.1 寫出，超出讀取端受釘範圍（W8b） |
| k | 各 series 最新觀測日 vs 全表最大日期 | pyarrow 實讀分組 | **確認**，數字同第 1.2 節表；與草稿一致 |
| l | `years` 預設 15 vs 35 | 讀 workflow 與腳本 | **確認**；**補充**：只影響 bootstrap／缺檔路徑，排程增量路徑不用 |
| m | UNRATE 反例的 git 證據（新增） | 附錄 A.3 | 11-08 提交只新增 23 列、刪除 0、重疊值變動 0；僅 UNRATE 的新增列早於預期起點；排除「整表 bootstrap」解釋；成因仍未解 |
| n | `build_market_view` 可注入 `fetch_fred`（新增） | 讀碼 | **確認**：簽名 `(series_id, api_key, n)→(frame, error)`；缺 Key 時不打 L1 |
| o | `app.py` 不 import `ui_v2`／`ui_v3`（新增） | `git grep` | **確認**（範圍：`app.py` 與 `ui/`）：New UI 為獨立入口；Cloud 主檔 NOT VERIFIED |

### 被推翻或修正的草稿宣稱

本批抽查**沒有推翻**任何一項草稿的資料數字（列數、起訖、落後天數、命中數均重現）。以下是**修正或收窄**：

1. **生產端草稿「月頻 series 增量結構上幾乎取不到新值」**：被 UNRATE 的實證反例限縮。僅能說 CPI／M2 與模型一致；UNRATE 不符。
2. **生產端草稿對 UNRATE 的猜測成因（含「手動 bootstrap」）**：以 git 集合比對**排除**最近一筆為 bootstrap；成因仍未解（草稿本就標未驗）。
3. **消費端草稿「檔案以何版 pyarrow 寫出本組未查」**：已查——pyarrow 26.0.1／pandas 3.1.1，與受釘版本不一致（新增 W8b）。
4. **消費端草稿未指出 pandas 版本**：requirements 同時釘 `pandas<3.0`，本機驗證環境為 pandas 3.x，故「讀取端相容」除 pyarrow 外還有 pandas 面向，兩者皆未驗。
5. **消費端草稿「`market_view` 禁止新增 L1 函式」**：原文成立，但草稿未交代出處；本批查明為檔頭自述、承接客戶條件式裁示，**不存在專屬解除條件**。
6. **生產端草稿 DTWEXBGS 頻率**：腳本註解稱日頻，但實測近 12 列全為週五且每次排程僅新增 1 列；本文改列「頻率未定」並兩種假設並陳。
7. **生產端草稿未指出**：metadata 每次重寫使每週必有 commit、`main()` 對 series 失敗仍回傳 0——本批補入第 1.3 節。

### 與既有文件的不一致處

- `cache_quality_intraday_freeze_study_2026_11_10.md` 已記載 UNRATE 的未解釋反例；本批以 git 證據補強該事實（最後一次排程），**未改動該研究文件任何結論**。
- `cache_quality_intraday_freeze_study_2026_11_10.md` 對快取「運行時不讀」的陳述與本批 b 項一致（其他 evidence 文件未逐一比對）。
- HANDOFF 先前的「下一個最小安全工作點」句已由本批的 `DEC-2026-11-10-04` 更新（舊句劃線保留，見 `docs/HANDOFF.md`）。
