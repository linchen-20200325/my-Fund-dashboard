# A1 離線唯讀快取品質檢查：腳本、範例報告與既知發現對照（2026-11-10）

> **聲明（先讀）**
> - 本文件是 **A1 離線報告的證據檔**，不是正式資料契約、不是健康狀態、不是監控資料，也不是施工授權。腳本內的 CONFIRMED／SUSPECTED／INSUFFICIENT_EVIDENCE 三級分類只是腳本內部的報告用列舉，**不是**新 Schema、狀態詞或欄位。
> - **未發現不等於正常。** 腳本只檢查下列有限項目；沒被檢查到的東西沒有任何結論。
> - **不判成因、不判誰對。** 報告只描述「檔案裡有什麼」與「與此參考不同」；2026-06-03 兩列「與參考不同」不等於「盤中值」，也不等於「快取錯了」。
> - 不核准 Eligibility、日期轉換規則、正式收盤判準、FX Gate（`FX_OBS_DATE_RULE_VERIFIED` **維持 `False`**）。
> - 授權依據：客戶 2026-11-10 核准 A1（經總管轉達，**要點轉述，非逐字，無逐字存檔**），登記於 `DEC-2026-11-10-02`：一支唯讀腳本、必要測試與文件。承接 `DEC-2026-11-10-01`、研究文件 `cache_quality_intraday_freeze_study_2026_11_10.md`（下稱「研究文件」）、`DEC-2026-11-09-10`（Q4 不覆寫快取、不更改計算）與 `yahoo_indices_sp_probe_result_2026_11_09.md`。
> - **本批沒有任何網路請求、沒有觸發 workflow、沒有修改 `data_cache`／`metadata.json`／結果分支／既有 scripts／workflow／services／ui／repositories。** 新增檔案只有：`scripts/check_cache_quality.py`、`tests/test_check_cache_quality.py`、本文件，以及 `DECISIONS`／`BACKLOG`／`HANDOFF` 的登記與索引。
> - 作者：專案 AI 單組；**未經第二組獨立驗證**。範例報告是以**自製 parquet 讀取器**（單組自製、未對拍 pyarrow）產生，見第 2 節限制。

## 1. 腳本做什麼、不做什麼

`scripts/check_cache_quality.py`（約 960 行含 docstring；零網路、零寫入 cache）：

| 區塊 | 檢查（皆為離線） | 分級 |
|---|---|---|
| 指數快取 `spx`／`vix`／`twii` | 日期可解析、遞增、無重複；`close` 缺值或非有限、`<= 0`；`metadata.row_count`／`last_updated` 與檔案一致 | 違反者 CONFIRMED（可由檔案本身機械重現） |
| 同上（啟發式） | 週六日列；`close` 等於前一列；**盤中凍結的歷史證據**（唯讀 `git log`／`git show`：該列首次出現的提交時間若落在該市場「當日」常規盤內） | SUSPECTED |
| 參考檔（選用 `--reference`） | 解開探測 `report.json` 的 `raw_gzip_b64`，與快取重疊日逐日比對（容差 0.006，沿研究文件 §3.3 的單精度判準） | 值不同者 CONFIRMED，僅證實「與此參考不同」 |
| `fred_indicators`（長格式） | 各 series 起訖、列數、推定頻率（相鄰間距中位數）、缺漏區間、宣告在 `FRED_SERIES_IDS` 卻零列、最新日期落後「共同最大日期」、列數過少、起點晚於同批 | 零列者 CONFIRMED；其餘 SUSPECTED |
| 觀測（不分級） | VIX 與 SPX 的日期集合差；日頻 FRED 的週末／月底週末；宣告 11 vs 快取 9 的 series 數；參考視窗內單邊有的日期 | 各市場假日性質只記為觀測，**不判定資料錯誤** |
| 讀不到的東西 | 缺檔、缺欄、空表、缺 metadata、git 淺層或不可用、參考檔損毀、缺 pyarrow | INSUFFICIENT_EVIDENCE（缺資料不補 0、不當正常） |

重用既有定義：`DATASETS` 與 `FRED_SERIES_IDS` 以 `ast` 讀自 `scripts/update_macro_history.py`（不 import 它：它會 import `requests`）；失敗時退回最小複本，並由測試守住與原檔一致。沒有新增資料架構。

**「首見提交時間」用的是提交者時間（`git log --format=%ct`，committer time），不是作者時間。**

**盤中時段判定的假設（INFERENCE，非事實）**：US `America/New_York` 09:30–16:00；VIX `America/Chicago` 08:30–15:15；TWII `Asia/Taipei` 09:00–13:30；僅週一至週五，含端點，以 `zoneinfo` 處理夏令。**不含**半日市、國定假日、盤前盤後。另加一條限制：只有「列日期＝提交當地日期」的列才可能是進行中的根，因此同一提交中較早日期的列不標記（避免整批 bootstrap 被誤標）。

用法與保護：

```
python scripts/check_cache_quality.py [--cache-dir data_cache] [--reference PATH] [--out PATH]
    [--format json|md] [--as-of ISO] [--no-git] [--git-ref REF | --git-all-refs] [--gap-factor N]
```

預設只印 stdout、輸出決定性（排序固定、預設不含執行時間；`--as-of` 可注入）。`--out` 若位於 cache-dir 內、已存在或父目錄不存在則拒絕（結束碼 2）。`--no-git` 時盤中凍結證據標「證據不足」。

## 2. 重現指令與環境限制

重現本文件第 3 節的報告（需 `pyarrow`；CI 與 QA 環境具備，`requirements.txt` 有 `pyarrow>=14,<25`）：

```
git fetch origin probe/yahoo-indices-sp-results
git show origin/probe/yahoo-indices-sp-results:results/yahoo_indices_sp_20261109/report.json > /tmp/yahoo_ref_report.json
# 參考檔 sha256 應為 f5d69b7d851932139dc069b46eb3a9aac6ae0567954d217a27d04c3b76d8ed0f（結果分支 commit 3e53b272）
python scripts/check_cache_quality.py --reference /tmp/yahoo_ref_report.json --git-all-refs --as-of 2026-11-10
```

- `data_cache` 內容＝提交 `8ca33547`（`metadata.json` `updated_at` 2026-11-08T04:07:01Z；`HEAD` 為 `11e732e0`，`data_cache` 自 `8ca33547` 起未變）。
- **`--git-all-refs` 為必要**：本 clone 是淺層，`HEAD` 只看得到 3 筆觸及 `spx_history.parquet` 的提交（含淺層邊界），看不到 2026-06-03 的 `47fb8985`；`--all` 才看得到全部 28 筆。不加時，這幾列的首見提交會是淺層邊界提交，腳本改標「證據不足」而非猜測（已由測試覆蓋）。結果因此**依賴本機 clone 擁有的 refs**，在別的 clone 上筆數可能不同。
- **本範例報告不是由 pyarrow 讀取產生。** 本機沒有 `pyarrow` 且不得 `pip install`；範例由放在 scratchpad（**不在 repo**）的自製 parquet 讀取器注入 `main(argv, reader=...)` 產生。該讀取器單組自製，只以列數對照（`fred_indicators` 13,829＝`metadata`；三個指數 3,879／3,881／3,762），**未與 pyarrow 對拍**。因此：腳本邏輯在本機以「假讀取器＋暫存 git repo」充分測試，但「腳本＋真 pyarrow＋真 parquet」的端到端組合**本機未驗**，須由 QA／CI 重現（第 6 節）。
- 本機測試指令（實測可行）：`PYTHONPATH=.:/usr/local/lib/python3.13/site-packages /root/.local/bin/pytest --noconftest -q -p no:cacheprovider tests/test_check_cache_quality.py`。pytest 的 uv-tool 直譯器看不到系統 site-packages，故需以 `PYTHONPATH` 指向它才 import 得到 `pandas`；測試 61 項：60 passed、1 skipped（`importorskip("pyarrow")` 的真實快取結構測試）。

## 3. 範例報告（完整輸出，Markdown，未刪節）

````text
# 離線唯讀快取品質檢查報告（A1）

> 本報告是 A1 離線唯讀檢查輸出，不是正式資料契約、健康狀態或監控資料。
> 未發現不等於正常：本腳本只檢查下列有限項目，沒被檢查到的東西沒有任何結論。
> 只描述檔案內容與「與參考不同」，不判成因、不判誰對；不核准 Eligibility、日期規則或 FX Gate（FX_OBS_DATE_RULE_VERIFIED 維持 False）。
> SUSPECTED 為啟發式；CONFIRMED 指可由檔案本身或參考檔機械重現的事實，不代表成因已查明。

- cache-dir：`data_cache`
- as-of：2026-11-10
- 常數來源：ast（`update_macro_history.py` 的 `DATASETS`／`FRED_SERIES_IDS`）
- 參考檔：`report_ref_yahoo.json`（sha256 `f5d69b7d851932139dc069b46eb3a9aac6ae0567954d217a27d04c3b76d8ed0f`；probe yahoo_indices_sp_20261109；run_id 42656242596；狀態 ok）
- 參數：gap_factor=1.5、min_rows=50、late_start_days=365、tolerance=0.006、git=on ref --all

## 摘要

| 資料集 | 已證實異常 | 疑似異常 | 證據不足 | 未發現 |
|---|---|---|---|---|
| fred_indicators | 1 | 8 | 0 | 0 |
| spx_history | 1 | 2 | 0 | 0 |
| twii_history | 0 | 2 | 0 | 0 |
| vix_history | 1 | 2 | 0 | 0 |
| **合計** | 3 | 14 | 0 | 0 |

## 各資料集事實

### fred_indicators（13829 列、9 個 series、共同最大日期 2026-11-05）

| series | 列數 | 起 | 迄 | 中位間距(天) | 推定頻率 | 落後共同最大日期(天) | 週末日期數 |
|---|---|---|---|---|---|---|---|
| BAMLH0A0HYM2 | 898 | 2023-06-05 | 2026-11-05 | 1.0 | 日頻 | 0 | 12 |
| CPIAUCSL | 178 | 2011-06-01 | 2026-04-01 | 31.0 | 月頻 | 218 | 52 |
| DGS10 | 3855 | 2011-06-07 | 2026-11-05 | 1.0 | 日頻 | 0 | 0 |
| DGS2 | 3855 | 2011-06-07 | 2026-11-05 | 1.0 | 日頻 | 0 | 0 |
| DGS3MO | 3855 | 2011-06-07 | 2026-11-05 | 1.0 | 日頻 | 0 | 0 |
| DTWEXBGS | 21 | 2026-06-05 | 2026-10-30 | 7.0 | 週頻 | 6 | 0 |
| M2SL | 179 | 2011-06-01 | 2026-04-01 | 31.0 | 月頻 | 218 | 52 |
| UNRATE | 183 | 2011-06-01 | 2026-10-01 | 31.0 | 月頻 | 35 | 53 |
| WALCL | 805 | 2011-06-08 | 2026-11-04 | 7.0 | 週頻 | 1 | 0 |

- **spx_history**：{"close_dtype": "float64", "date_dtype": "object", "first_date": "2011-06-07", "last_date": "2026-11-06", "readable": true, "reference_equal_days": 498, "reference_overlap_days": 499, "reference_symbol": "^GSPC", "reference_tolerance": 0.006, "reference_window": ["2024-11-11", "2026-11-06"], "rows": 3879, "unique_dates": 3879}
- **twii_history**：{"close_dtype": "float64", "date_dtype": "object", "first_date": "2011-06-07", "last_date": "2026-11-06", "readable": true, "reference_equal_days": 483, "reference_overlap_days": 483, "reference_symbol": "^TWII", "reference_tolerance": 0.006, "reference_window": ["2024-11-11", "2026-11-06"], "rows": 3762, "unique_dates": 3762}
- **vix_history**：{"close_dtype": "float64", "date_dtype": "object", "first_date": "2011-06-07", "last_date": "2026-11-06", "readable": true, "reference_equal_days": 500, "reference_overlap_days": 501, "reference_symbol": "^VIX", "reference_tolerance": 0.006, "reference_window": ["2024-11-11", "2026-11-06"], "rows": 3881, "unique_dates": 3881}

## 已證實異常（CONFIRMED，3 筆）

- **[fred_indicators] declared_series_zero_rows**：宣告於 FRED_SERIES_IDS（11 項）但快取零列的 series：2 項
  - 明細：[PCOPPUSDM, PPIACO]
- **[spx_history] reference_mismatch**：1 個重疊日的 close 與參考檔不同（只證實『與此參考不同』，不判誰對、不判成因）
  - 明細：[{"abs_diff": 42.299805, "cache_close": 7595.97998, "date": "2026-06-03", "reference_close": 7553.680176}]
- **[vix_history] reference_mismatch**：1 個重疊日的 close 與參考檔不同（只證實『與此參考不同』，不判誰對、不判成因）
  - 明細：[{"abs_diff": 0.200001, "cache_close": 16.26, "date": "2026-06-03", "reference_close": 16.059999}]

## 疑似異常（SUSPECTED，14 筆）

- **[fred_indicators／BAMLH0A0HYM2] late_start**：起點 2023-06-05 晚於同批最早起點 2011-06-01 達 4387 天
  - 明細：{"dataset_min_start": "2011-06-01", "start": "2023-06-05"}
- **[fred_indicators／CPIAUCSL] gaps**：間距超過 max(1.5×中位數, 7) = 46.5 天的缺漏區間 1 個（頻率為推定）
  - 明細：[{"days": 61, "from": "2025-09-01", "to": "2025-11-01"}]
- **[fred_indicators／CPIAUCSL] lag_behind_common_max**：最新日期 2026-04-01 落後共同最大日期 2026-11-05 達 218 天（> 46.5）；候選：『全表最大日期＋1』增量起點盲點（成因不判）
  - 明細：{"lag_days": 218, "threshold_days": 46.5}
- **[fred_indicators／DTWEXBGS] few_rows**：僅 21 列（< 50）
  - 明細：{"min_rows": 50, "rows": 21}
- **[fred_indicators／DTWEXBGS] gaps**：間距超過 max(1.5×中位數, 7) = 10.5 天的缺漏區間 1 個（頻率為推定）
  - 明細：[{"days": 14, "from": "2026-06-26", "to": "2026-07-10"}]
- **[fred_indicators／DTWEXBGS] late_start**：起點 2026-06-05 晚於同批最早起點 2011-06-01 達 5483 天
  - 明細：{"dataset_min_start": "2011-06-01", "start": "2026-06-05"}
- **[fred_indicators／M2SL] lag_behind_common_max**：最新日期 2026-04-01 落後共同最大日期 2026-11-05 達 218 天（> 46.5）；候選：『全表最大日期＋1』增量起點盲點（成因不判）
  - 明細：{"lag_days": 218, "threshold_days": 46.5}
- **[fred_indicators／UNRATE] gaps**：間距超過 max(1.5×中位數, 7) = 46.5 天的缺漏區間 2 個（頻率為推定）
  - 明細：[{"days": 61, "from": "2025-09-01", "to": "2025-11-01"}, {"days": 61, "from": "2026-04-01", "to": "2026-06-01"}]
- **[spx_history] flat_rows**：1 列 close 等於前一列（相同值連續出現不必然是錯誤，單獨不足以判異常）
  - 明細：[2017-01-10]
- **[spx_history] intraday_freeze**：1 列的首次出現提交落在該市場當日常規盤內（疑似凍結盤中值；啟發式，非證實）
  - 明細：[{"commit_local": "2026-06-03 09:35:13 EDT", "commit_utc": "2026-06-03T13:35:13Z", "date": "2026-06-03", "first_seen_commit": "47fb8985", "market_tz": "America/New_York"}]
- **[twii_history] flat_rows**：3 列 close 等於前一列（相同值連續出現不必然是錯誤，單獨不足以判異常）
  - 明細：[2014-07-23, 2016-07-08, 2026-09-20]
- **[twii_history] weekend_rows**：1 列日期為週六或週日（日頻指數通常無週末根；啟發式，不判成因）
  - 明細：[2026-09-20]
- **[vix_history] flat_rows**：19 列 close 等於前一列（相同值連續出現不必然是錯誤，單獨不足以判異常）
  - 明細：[2011-07-08, 2012-02-22, 2012-04-16, 2012-12-24, 2013-03-15, 2013-06-28, 2013-07-30, 2014-01-15, 2017-07-25, 2018-01-05, 2018-12-19, 2020-06-10] …（共 19 筆，完整清單見 --format json）
- **[vix_history] intraday_freeze**：1 列的首次出現提交落在該市場當日常規盤內（疑似凍結盤中值；啟發式，非證實）
  - 明細：[{"commit_local": "2026-06-03 08:35:13 CDT", "commit_utc": "2026-06-03T13:35:13Z", "date": "2026-06-03", "first_seen_commit": "47fb8985", "market_tz": "America/Chicago"}]

## 證據不足（INSUFFICIENT_EVIDENCE，0 筆）

（無）

## 未發現（不等於正常）（NO_FINDING，0 筆）

（無）

## 觀測（不分級、不判定資料錯誤）

- [fred_indicators] declared_vs_parquet_series_count：FRED_SERIES_IDS 宣告 11 項；快取內有資料的 series 9 項
  - 明細：{"declared": 11, "in_parquet": 9}
- [fred_indicators／BAMLH0A0HYM2] weekend_observations：日頻 series 有 12 個週末日期（其中月底日 12）；觀測，不判定
  - 明細：[2023-09-30, 2023-12-31, 2024-03-31, 2024-06-30, 2024-08-31, 2024-11-30, 2025-05-31, 2025-08-31, 2025-11-30, 2026-01-31, 2026-02-28, 2026-05-31]
- [twii_history] cache_only_in_reference_window：參考視窗內快取有而參考無的日期 1 個（觀測，不判定）
  - 明細：[2026-09-20]
- [vix_history] date_set_vs_spx：VIX 有而 SPX 無的日期 2 個；SPX 有而 VIX 無的日期 0 個（各市場假日性質，僅觀測，不判定資料錯誤）
  - 明細：{"spx_not_in_vix": [], "vix_not_in_spx": ["2026-05-25", "2026-09-07"]}

---
未發現不等於正常。本報告不判成因、不核准任何規則。
````

## 4. 與研究文件第 3、5 節既知發現的對照

「重現」＝腳本在本範例報告中獨立指出同一事實（不是我事後挑選報告去配合結論）。**沒有不一致項。**

| # | 研究文件既知發現 | 腳本是否重現 | 腳本分類與位置 |
|---|---|---|---|
| 1 | VIX 比 SPX 多 2 個日期（2026-05-25、2026-09-07；假日列） | 重現 | **觀測**（`date_set_vs_spx`），依客戶要求不判為資料錯誤；SPX 有而 VIX 無＝0 |
| 2 | TWII 週日列 2026-09-20；與前一交易日同值 | 重現 | SUSPECTED `weekend_rows`＋`flat_rows`；另有觀測：參考視窗內「快取有而參考無」＝該日 |
| 3 | 2026-06-03 的 `^GSPC` 7595.98 vs 7553.68、`^VIX` 16.26 vs 16.06 與探測不同；`^TWII` 無差異 | 重現 | **CONFIRMED** `reference_mismatch`（SPX 差 42.299805、VIX 差 0.200001；TWII 無此項）。只證實「與此參考不同」 |
| 4 | 06-03 兩列首見提交 `47fb8985` 落在美股盤內（09:35:13 EDT／VIX 08:35:13 CDT） | 重現（SPX、VIX）；TWII 未標記，與研究文件「台股已收盤」一致 | SUSPECTED `intraday_freeze`（需 `--git-all-refs`） |
| 5 | FRED `CPIAUCSL`、`M2SL` 最新停在 2026-04-01 | 重現 | SUSPECTED `lag_behind_common_max`（落後共同最大日期 2026-11-05 達 218 天；門檻 46.5 天） |
| 6 | `UNRATE` 缺 2026-05-01（及 2025-10）；`CPIAUCSL` 缺 2025-10 | 重現 | SUSPECTED `gaps`（UNRATE：2025-09-01→2025-11-01 與 2026-04-01→2026-06-01；CPIAUCSL：前者） |
| 7 | `DTWEXBGS` 只有 21 列、2026-06-05 起 | 重現 | SUSPECTED `few_rows`＋`late_start`（推定頻率為週頻） |
| 8 | `PPIACO`、`PCOPPUSDM` 在 `FRED_SERIES_IDS` 內卻零列 | 重現 | **CONFIRMED** `declared_series_zero_rows` |
| 9 | HY OAS（`BAMLH0A0HYM2`）898 列、起 2023-06-05；日頻週末列 12（皆月底日） | 重現 | SUSPECTED `late_start`；觀測 `weekend_observations`（12，其中月底日 12） |
| 10 | `FRED_SERIES_IDS` 11 項 vs parquet 9 個 series | 重現 | 觀測 `declared_vs_parquet_series_count`；零列項見 #8 |
| 11 | 值等於前一列：SPX 1（2017-01-10）、VIX 19、TWII 3 | 重現（數量與日期） | SUSPECTED `flat_rows`（單獨不足以判異常） |
| 12 | 與探測回應重疊日：SPX 499（498 相同）、VIX 501（500 相同）、TWII 483（483 相同） | 重現 | 報告「各資料集事實」的 `reference_overlap_days`／`reference_equal_days` |

**研究文件「未解釋的反例」（`UNRATE` 為何持續前進）腳本不處理**：本腳本不判成因。

## 5. 新發現

沒有推翻或新增研究文件結論的發現。僅有的細節增補（皆為描述，不判成因）：

- `DTWEXBGS` 的相鄰間距中有一個 14 天缺口（2026-06-26→2026-07-10），腳本因其超過門檻 10.5 天而列為 SUSPECTED `gaps`；研究文件只記「21 列、每週一列」，未單列此缺口。其餘非 7 天的間距未超過門檻，腳本不列。
- 腳本把 `UNRATE` 的 2025-10 缺口與 2026-05 缺口分開列出（研究文件第 5.1 節同樣兩者都有，分在不同欄）。

## 6. 限制與未涵蓋

- **git 呼叫的安全邊界**：所有 git 子程序只允許 `rev-parse`／`log`／`show`，一律加 `--no-optional-locks`，環境設 `GIT_NO_LAZY_FETCH=1`、`GIT_TERMINAL_PROMPT=0`、不載入使用者／系統 git 設定；`--git-ref` 拒絕以 `-` 開頭、含空白或控制字元者（退出碼 2），並先以 `rev-parse --verify --end-of-options <ref>^{commit}` 解成 commit 才使用；`--git-all-refs` 為獨立旗標。**局部（partial／promisor）clone 的行為未實測**（已設 `GIT_NO_LAZY_FETCH=1` 避免延遲抓取，但缺的 blob 會使該提交版本讀不出而降級，未驗證實際表現）。
- 參考檔解壓後大小上限 `MAX_REFERENCE_BYTES`＝50 MB（**專案 AI 建議值，非客戶裁示**），超限、深層巢狀 JSON 等降級為證據不足。
- **未經 pyarrow 驗證**（見第 2 節）；`tests/test_check_cache_quality.py::test_real_cache_structure_with_pyarrow` 在本機 skip，須由 CI／QA 實跑。本機已另以注入的自製讀取器重演該測試的全部斷言，結果通過，但那不等於 pyarrow 路徑通過。
- 盤中凍結只是「首見提交時間」的啟發式；不驗實際盤中價，不查 GitHub Actions 執行紀錄（研究文件 §3.3 已指出的可證偽點仍未被驗）。時段假設見第 1 節。
- 「共同最大日期」等於 `fred_indicators` 內各 series 最新日期的最大值；落後門檻與缺漏門檻是 `max(1.5×中位數, 7 天)`、頻率為相鄰間距中位數推定，**不是**發布日曆；月頻序列的發布延遲不在模型內，門檻對特殊序列可能誤報或漏報。
- 只讀 4 個 parquet 與 `metadata.json`；不檢查 `fund.db`、下游 repo、NAV 快取或其他 `data_cache` 外的資料。未做 PIT／vintage 檢查（快取本來就沒有 release_date）。
- 參考檔只涵蓋 2024-11-11 起的 2 年窗與三個指數；窗外與 FRED 沒有參考，無法判定。
- 腳本不修改任何值、不產生旗標欄位、不寫 Sheet；報告不是可被其他程式依賴的契約。
- 本批未跑 `pre-commit`（本機未安裝），以逐條複刻判定邏輯（行尾空白、檔尾換行、衝突標記、檔案大小）代替。

## 7. 下一個 Decision Gate（**專案 AI 推薦在前，未經客戶裁示**）

| 方案 | 內容 | 專案 AI 推薦 |
|---|---|---|
| **G1：先讓 QA／CI 以 pyarrow 重現本報告，再請客戶就 B1 裁示** | 補上本批唯一缺口（端到端未驗）；通過後，報告可作為 B1 前後比對的列級基準 | **推薦（優先）** |
| G2：授權 B1（受控重抓比對 dry-run；結果寫結果分支，不碰 `data_cache`） | 需新外部請求（Yahoo＋FRED 金鑰在 workflow 內），須由客戶另列請求數與標的上限；可實測 FRED 缺口是「視窗漏抓」還是「來源無資料」 | 次選；建議在 G1 通過後再議 |
| G3：授權 B3（寫入端重疊窗口自癒）／B2（修正 06-03 兩列）／C（全量重建） | 改變增量語意或覆寫證據，與 `DEC-2026-11-09-10` Q4 相鄰 | 暫不推薦（B3、B2）；不推薦（C） |
| G4：把 A1 接上排程或 workflow | 屬新自動化與可能的新契約，本批未授權 | 不推薦現在做 |

五個方案皆不解鎖 Eligibility、日期轉換規則、FX Gate、正式母集合或涵蓋率分母；`FX_OBS_DATE_RULE_VERIFIED` 維持 `False`。

## 8. pyarrow 對拍結果（2026-11-10）

由獨立 QA 以 pyarrow 26.0.1（pandas 3.0.5）對拍（唯讀，未動 `data_cache`）：

- 列數與事實一致：spx 3879、vix 3881、twii 3762、fred 13829，皆等於 `metadata.json` 的 `row_count`。
- 以預設讀取器（pandas／pyarrow）重跑 `check_cache_quality.py --cache-dir data_cache --git-all-refs --reference <參考檔> --format md --as-of 2026-11-10`，輸出與本報告第 3 節範例**逐行零差異**（3 CONFIRMED／14 SUSPECTED）。
- `tests/test_check_cache_quality.py`：61 passed、0 skipped（真實快取結構測試由 skip 變 pass）。
- 限制：pyarrow 26.0.1 超出 `requirements.txt` 的 `pyarrow>=14,<25`，14～24 未測；未在含 `conftest` 的 CI 完整環境跑；本 clone 為淺層，git 歷史證據依本機可見 refs（他 clone 筆數可能不同）；只驗報告可重現與資料事實，未重驗 findings 語意；未碰外部資料。
