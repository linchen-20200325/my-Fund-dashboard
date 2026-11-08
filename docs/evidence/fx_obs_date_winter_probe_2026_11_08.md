# D8 FX 冬令觀測日探測：證據分析與歸檔（2026-11-08，docs-only）

| 項目 | 內容 |
|---|---|
| 性質 | 唯讀證據分析，只新增本檔；未改任何程式、workflow、排程、閘門、來源、分支 |
| 分析對象 | 探測報告 `results/20261108T063652Z_run42455423910/report.json`（分支 `probe/fx-obs-date-results`，commit `6b180d6fd3d77f255df8bcebbcf470027abf79c3`） |
| 對應登記 | BL-0217；`docs/v2/49_data_integration_plan.md` 第 8 節 (i)「開閘前尚需」(a)～(e)；`onebrain_decision_gate_route_and_risk_check_2026_11_08.md` 的 D8 |
| 標籤 | **FACT**＝直接讀自報告或 repo 且附指令；**INFERENCE**＝依 FACT 推論，可被推翻；**NOT VERIFIED**＝未驗；**NOT RUN**＝本批沒跑 |
| 作者揭露 | 本檔由單組（作者）寫成，**沒有第二組獨立複驗**；之後的獨立 QA 不得把「作者自驗」當成通過 |

## 0. 結論先行

| # | 結論 | 標籤 |
|---|---|---|
| 1 | 2026-11-08 的探測在 `main` `15538a57` 上真跑成功：6 個代號 `status=ok`、`rejected_tickers=[]`、各 `fetch_log=[]`。**取數成功不等於驗證通過**，本檔沒有任何一格因取數成功而寫 PASS | FACT |
| 2 | `FX_OBS_DATE_RULE_VERIFIED` 在 `origin/main` 為 `False`（`services/v2_tables/market_indicator.py` 第 107 行），報告 `fx_obs_date_rule_verified_at_run` 亦為 `False`。本檔不改它 | FACT |
| 3 | 美元：日 K 的 close 與「UTC 當日 00:00 起點的小時價」最一致，而且在三個時區制度期（倫敦夏令／倫敦冬令紐約夏令／兩地皆冬令）都是同一個 UTC 時刻，不隨倫敦或紐約的夏令切換移動。樣本小（13／5／5 日）、小時解析度，**只是一致性，不是已證明的收盤時間規則** | INFERENCE |
| 4 | 歐元、日圓：本報告**不支持**把美元的結果外推。歐元日 K 與小時價有約 +0.13% 的系統差，且 45 根日 K 的 close 比 open 低 1% 以上（42 根是週一）；日圓日 K 與小時價有約 −1.08% 的系統差 | FACT（數字）／INFERENCE（不能外推） |
| 5 | 人民幣 CNY、離岸人民幣 CNH：`range=2y` 只回 1 根，正式路徑一列都不寫，**不能判定，也不能由美元外推** | FACT |
| 6 | 開閘前條件 (a)～(e)：**沒有一項可以寫成「已完成」**。(a) 已跑一次但是否足夠未驗；(b) 容差未定，不能判定；(c) 有支持證據但未正式驗；(d) 本報告的小時 K 區間沒涵蓋，NOT RUN；(e) 假日映射未解 | 見第 7 節 |
| 7 | 是否足以支持開閘決策：**否，目前不能。** 本檔不推薦開閘，只列下一個 Decision Gate 所需證據與缺口（第 7 節） | INFERENCE |
| 8 | 新疑點（舊文件未見登記）：歐元週一日 K 異常、日圓水位偏差、「10-14 前收」參照時刻與日 K 值對應時刻不同（第 4 節） | FACT／NOT VERIFIED（成因） |

## 1. 執行紀錄

| 欄位 | 值 | 依據（報告 JSON 路徑或指令） | 標籤 |
|---|---|---|---|
| GitHub Actions run | `42455423910` | `github_run_id` | FACT |
| 事件 | `workflow_dispatch` | `event_name` | FACT |
| trigger／executed／github SHA | 三者皆 `15538a571f62dfdc6c7b1ef00d5538d47b869bf6`；與本檔作業時 `git rev-parse origin/main` 相同 | `trigger_sha`、`executed_sha`、`github_sha` | FACT |
| 報告產生時間 | `2026-11-08T06:36:50.569726+00:00`（週日；最新日 K 為週五 11-06） | `generated_at_utc` | FACT |
| 報告提交 | 分支 `probe/fx-obs-date-results` 上 `6b180d6f`，2026-11-08 06:36:53Z，訊息含 `[skip ci]` | `git log -1 origin/probe/fx-obs-date-results` | FACT |
| 報告檔 | 908102 bytes；sha256 `8fe1aca5de4236847ee24c9c8abc736b828c4d25a81f7074948a4c9d001be5a9`（分支上檔案與本檔分析所用複本相同） | `sha256sum`；`git show origin/probe/fx-obs-date-results:<路徑> \| sha256sum` | FACT |
| 工具 | `scripts/probe_fx_obs_date.py`，由 `.github/workflows/fx_obs_date_probe.yml` 執行（Python 3.11，`ref: main`） | workflow 檔；報告頂層鍵 | FACT |
| 端點／參數 | `https://query1.finance.yahoo.com/v8/finance/chart`；日 K `range=2y interval=1d`；小時 K `interval=60m range=1mo`，只取 USD、EUR、JPY | 報告 `endpoint`、`range`、`interval`、`tickers[*].hourly` | FACT |
| 代理 | `proxy_env_set` ＝ `True`，`proxy_used_by_infra` ＝ `False`（只記布林值） | 報告頂層 | FACT |
| 敏感字串檢查 | 以不分大小寫的樣式掃 `bearer／authorization／crumb／cookie／ghp_／github_pat／AKIA／api key／passw／token／secret／credential／PROXY_URL／squid` 與 `@`、內網位址：**0 命中**；報告內唯一網址是上列端點。⚠️ 這是樣式掃描，不是保證 | `grep -ciE`、`grep -oE "https?://[^\" ]+"` | FACT（掃描範圍有限） |
| 本批沒做的 | 沒有重跑探測、沒有連 Yahoo、沒有呼叫 `rows_from_daily_close`／`_obs_date` 等正式函式（第 3 節用的是報告自帶欄位與本檔附錄的重現腳本） | — | NOT RUN |

## 2. 逐幣別狀態

判定欄用語：**FACT（描述）**＝報告上的事實，不是通過判定；**不能判定**＝比較方法在本資料上分不出答案；其餘見檔頭標籤。路徑簡寫：`T[k]` ＝ 報告 `tickers[k]`。

| 項目 | USDTWD=X | ^VIX | EURTWD=X | JPYTWD=X | CNYTWD=X | CNHTWD=X |
|---|---|---|---|---|---|---|
| 取數狀態（`T[k].status`） | ok | ok | ok | ok | ok | ok |
| 原始日 K 根數／null close／非 null（`raw_bar_count`、`null_close_count`、`subsets.non_null.bar_count`） | 523／5／518 | 523／19／504 | 523／5／518 | 523／5／518 | 1／0／1 | 1／0／1 |
| 回應自報交易所時區（`meta.exchangeTimezoneName`） | Europe/London | America/Chicago | Europe/London | Europe/London | Europe/London | Europe/London |
| 時間戳 UTC 時:分（`subsets_exchange_tz.non_null.utc_hhmm.all`） | 00:00×220、23:00×298 | 08:00×172、07:00×332（皆為芝加哥當地 02:00） | 同 USD | 同 USD | 22:26 ×1（＝`regularMarketTime`） | 22:26 ×1 |
| 舊規則（UTC 取日）與新規則（交易所時區取日）不同的根數（`obs_date_rule_diff`） | 298／518 | 0／504 | 298／518 | 298／518 | 0／1 | 0／1 |
| 舊規則：落在週末的列／缺週五的 ISO 週（`subsets...obs_date_weekday`） | 59／60 | 未列入本檔 | 59／60 | 59／60 | — | — |
| 新規則：週末列／同日重複／缺週五的 ISO 週（`subsets_exchange_tz`） | 0／0／1（2025-W16） | 0／0／5（2025-W16、2025-W27、2026-W14、2026-W25、2026-W27） | 0／0／1（2025-W16） | 0／0／1（2025-W16） | 0／0／— | 0／0／— |
| 現行語意（`production_rows.obs_date_rule`） | prev_weekday | same_day | prev_weekday | prev_weekday | prev_weekday | prev_weekday |
| 正式路徑寫出列數與觀測日範圍（`production_rows`） | 518；2024-11-05～2026-11-05 | 504；2024-11-06～2026-11-06 | 518；同 USD | 518；同 USD | **0**（`skipped` 1 筆：同一時刻只有 1 根，少於 `FX_MIN_REFERENCE_VOTES`＝20） | **0**（同左） |
| 日 K close vs 小時 K（`daily_value_check`；附錄 S3、S4） | 有取；與 UTC 當日 00:00 起點小時價中位數絕對差 0.0034%（23 日，最大 0.0624%） | **NOT RUN**（腳本不對 VIX 取小時 K） | 有取；系統差 +0.1324%（中位數） | 有取；系統差 −1.0788%（中位數） | **NOT RUN** | **NOT RUN** |
| 本報告可給的判定 | **不能判定開閘**；規則層面有支持證據（INFERENCE，見第 3 節） | 描述性一致，值對應 NOT RUN；它是已上線路徑，不受 FX 閘門管 | **不支持外推**；另有週一異常（第 4 節） | **不支持外推**；水位差 −1.08% | **不能判定** | **不能判定** |

補充（FACT，指令見附錄）：
- 新規則下美元／歐元／日圓的週末列為 0，舊規則為 59（Sunday 列）；298 根差異正好等於倫敦夏令期間（UTC 23:00）的根數。**這只描述「新規則取日不再落在週末」，不證明新規則取的日期等於「前一交易日」。**
- 空 close 的日 K（美元／歐元／日圓皆相同）：倫敦 2025-01-01、2025-04-18、2025-04-21、2025-12-25、2026-01-01；VIX 的 19 根都落在美國假日（例：2024-11-28、2025-01-09、2025-04-18、2026-07-03）。
- VIX 最後兩根：11-05 收 28.18、11-06 收 25.64；報告的 `regularMarketPrice` 25.64、`fulldayChange` −2.54（28.18−2.54＝25.64）。**INFERENCE**：VIX 標日 D 的那根確實是 D 當日收盤，只有這兩個資料點。

## 3. 比較項目

### 3.1 Yahoo 原始時間戳與交易所時區、新舊取日規則

| 比較項 | 結果 | 標籤 |
|---|---|---|
| 匯率日 K 時間戳 | 全部是倫敦當地 00:00（夏令為 UTC 23:00、冬令為 UTC 00:00）；USD 2y 內 518 根無例外 | FACT |
| VIX 日 K 時間戳 | 全部是芝加哥當地 02:00（夏令 UTC 07:00、冬令 UTC 08:00） | FACT |
| 舊規則（UTC 取日）在夏令期早一天 | 298 根取到的日期比交易所當地日早一天（例：UTC 2025-03-30 23:00 → 舊 03-30、新 03-31）；冬令 220 根相同 | FACT |
| 新規則取日 | 週末 0、同日重複 0 | FACT（一份報告上的描述，非通過判定） |
| 規則是否「等於交易日」 | **NOT VERIFIED**：取日落在平日只代表「沒有明顯錯位」，要判定是否等於「交易日／前一交易日」仍須拿值對照（3.3） | NOT VERIFIED |

### 3.2 DST 邊界：報告實際涵蓋哪些根、是否跨過邊界

| 項目 | 結果 | 標籤 |
|---|---|---|
| 日 K（2y）倫敦時間戳 UTC 時:分翻轉點 | 2025-03-31（00:00→23:00）、2025-10-27（23:00→00:00）、2026-03-30（00:00→23:00）、**2026-10-26（23:00→00:00）**：四個倫敦切換都在日 K 範圍內 | FACT |
| 日 K（2y）VIX 翻轉點 | 2025-03-10、2025-11-03、2026-03-09、**2026-11-02**（皆為切換後的第一個週一） | FACT |
| 小時 K 範圍 | 2026-10-06T23:00Z～2026-11-06T23:00Z（`daily_value_check.hourly_first_utc／hourly_last_utc`），**跨過**倫敦 2026-10-25 與紐約 2026-11-01 兩個切換 | FACT |
| 與日 K 可比的日數 | 報告 `compared`＝22（`daily_value_check.bars[0]` 為倫敦 10-08）；本檔附錄多算 10-07 一日，共 23 日，分三個制度期：P1 倫敦夏令／紐約夏令 10-07～10-23 共 13 日；P2 倫敦冬令／紐約夏令 10-26～10-30 共 5 日；P3 兩地皆冬令 11-02～11-06 共 5 日 | FACT |
| 美元：日 K close 與小時價的最一致時刻 | 以「該根標的倫敦 00:00＋k 小時」的小時價比較，**最佳 k 在 P1 是 +1、在 P2／P3 是 0**；換算成 UTC 都是「UTC 當日 00:00」。以 UTC 當日 00:00 起點小時價比：P1 中位數絕對差 0.0034%（最大 0.0249%）、P2 0.0028%（最大 0.0624%）、P3 0.0037%（最大 0.0251%）；若改用倫敦當地 00:00：P1 0.0323%、P2 0.0028%、P3 0.0037% | FACT（數字） |
| 上一點的意義 | 值對應的時刻**沒有跟著倫敦夏令移動**（否則 P1 應是 k＝0），也**沒有跟著紐約夏令移動**（若固定在紐約 19:00／20:00，P3 應比 P2 晚一小時）。固定的 UTC 00:00 與固定的台北 08:00 在本資料上**分不出來**（兩者同一個瞬間、台北無夏令） | INFERENCE |
| 報告自帶的合併掃描 | `fixed_offset_scan` 把三個制度期混在一起，美元最佳 k＝+1（中位數絕對差 0.0051%，n＝22），k＝0 為 0.0081%（終點版 n＝18）。因 13／23 日是夏令，混合後 +1 勝出，**分制度期才看得到 P2／P3 其實是 k＝0**；舊稽核 X 的「美元最佳 k＝+1」是夏令期為主的結果 | FACT（數字）／INFERENCE（解讀） |
| 與 2026-10-14 登記字句的關係 | 舊登記寫「約 UTC D 日 00:00、台北 08:00；夏令早一小時」。本報告 P1 的結果是夏令期**仍然**對應 UTC D 日 00:00（k＝+1），不是 UTC 23:00。舊句可能指的是「時間戳」而非「值對應時刻」；本檔不改舊句，交由獨立 QA 判讀 | INFERENCE |
| 切換日當天附近的單日行為 | 倫敦切換發生在週日，日 K 沒有週日根；10-23（週五，夏令）與 10-26（週一，冬令）是切換前後相鄰的兩根，10-23 以 UTC 00:00 比為 −0.0031%；**10-26（切換後第一根，週一）以 UTC 00:00 比為 −0.0362%**（k＝+1 則為 +0.0006%），比其他日大，是週一重開市首小時的價格波動或切換後的偏移，本檔無法分辨（NOT VERIFIED）。**切換日本身沒有根可比，NOT RUN** | FACT／NOT RUN |

### 3.3 現行「前一交易日收盤」語意（`production_rows.obs_date_rule`＝prev_weekday）

| 比較項 | 結果 | 標籤 |
|---|---|---|
| 位移後觀測日範圍 | USD／EUR／JPY：2024-11-05～2026-11-05；最新一列的觀測日是週四 11-05（週五 11-06 那根是最後一根日 K） | FACT |
| 週一那根的值是否等於上週五收盤 | **不完全**。美元週一日 K close 與上週五最後一根小時價的差：10-12 +0.0191%、10-19 **−0.1264%**、10-26 +0.0025%、11-02 +0.0043%。10-19 那根的值（32.387）等於週一 UTC 00:00 起點小時價（32.386），不等於週五最後小時價（32.428）；也就是說，位移成「上週五」寫入的是**週日重開市後的價格**，不是上週五收盤。歐元同樣：10-19 −0.3777%（另有 10-26、11-02 的 −3.13%、−2.88%，見第 4 節） | FACT（數字）／INFERENCE（語意） |
| 與客戶 10-14 裁示的關係 | 裁示核准的是「前一交易日收盤」語意；本報告顯示日 K 值對應「UTC 當日 00:00 的價格」（第 3.2 節，INFERENCE），週一四個樣本的差見上列（最大 −0.1264%）；平日根沒有做同型比較（NOT RUN）。**這個差距是否可接受，容差未定，屬下一個 Decision Gate** | INFERENCE／NOT VERIFIED |
| 取數當日的盤中值 | 報告以週日取數；`last_bar` 與 `regularMarketTime`：美元最後一根日 K 是倫敦週五 00:00 的根（UTC 11-06 00:00），不是盤中即時根（`last_bar.equal`＝False），**週五收盤價 32.765 不在日 K 序列內**（它是 `regularMarketPrice`；週一的根尚不存在）。對應舊登記 N4：最新一列觀測日 ＝ 取數日往前約兩個交易日 | FACT |

### 3.4 日 K close 與小時 K 的比較，以及「最接近值」法的不可判定性

| 比較項 | USD | EUR | JPY | 標籤 |
|---|---|---|---|---|
| `compared`（可比日數） | 22 | 22 | 22 | FACT |
| 最接近值法：`ties_gt_1`（最近的小時價不只一個的日數） | 7 | 1 | 11 | FACT |
| 最接近值法：容差 1e-6 內的日數／分布 | 1／`{}` | 1／`{"+1 23:00": 1}` | 0／`{}` | FACT |
| 最接近值法：容差 1e-4 內的日數 | 20 | 10 | 2 | FACT |
| 固定位移掃描最小中位數絕對差（終點版） | k＝+1，0.0051%，n＝22 | k＝0，0.1148%，n＝17 | k＝+26（掃描範圍邊界），0.7827%，n＝17 | FACT |
| 以 UTC 當日 00:00 起點小時價比的中位數（帶正負號，小時價減日 K） | −0.0031% | **+0.1324%** | **−1.0788%** | FACT |

- **「最接近值」法不可判定（FACT 數字＋INFERENCE 解讀）**：美元 22 日中有 7 日在容差內有多個同樣近的小時價；放寬到 1e-4 後 20 日都「命中」，但分布散落在不同時刻。這是舊稽核已點名的限制（價格在相鄰幾小時常常幾乎相同）。**本檔不以它判定時刻**；上表第 3.2 節的分制度期比較用的是「所有日用同一個 k」的固定位移法，不挑根。
- 歐元、日圓的小時價與日 K 之間有固定的水位差（+0.13%、−1.08%），比「時刻錯位」造成的差大很多，所以**這兩個幣別的位移掃描沒有一個清楚的最小值**（日圓的最小值落在掃描邊界 +26 就是徵兆）。**本報告無法對歐元、日圓判定時刻**。
- 小時 K 時間戳慣例（條件 c）：報告把「時間戳＝區間起點」列為假設（`hourly_timestamp_convention`）。本檔另看到：(i) 美元五個週五中，**四個**的最後一根小時 K 是四價相同（high＝low＝open＝close）的零區間根——10-16 21:00、10-23 21:00、10-30 22:00、11-06 22:00（UTC）；10-09 那週最後一根（21:00）不是零區間，且該日 03:00～11:00 的小時 K 為 null；(ii) 11-06 22:00 那根的值 32.765 等於 `regularMarketPrice`，而 `regularMarketTime` 恰為 22:00:00。**INFERENCE**：這與「時間戳＝區間起點、該根只含收市瞬間」一致，與「時間戳＝區間終點」不一致；但只有「週五收市根」這一類資料點（4／5 週），**不是正式驗證（NOT VERIFIED）**。
- 週五收市時刻：10-16、10-23（倫敦夏令）為 UTC 21:00，10-30（倫敦冬令、紐約仍夏令）與 11-06 為 UTC 22:00。**INFERENCE**：10-30 那週收市在 UTC 22:00＝倫敦 22:00、紐約 18:00（夏令），**不是紐約 17:00**（那會是 UTC 21:00）。這回答了舊登記「紐約 17:00 與倫敦 22:00 同週無法區分」的一部分；但日 K 值對應的是 UTC 00:00 而非收市時刻，所以不能反推為日 K 的收盤規則。週日重開市：10-11、10-18 為 UTC 23:00（倫敦週一 00:00 夏令），10-26、11-02 為 UTC 00:00（倫敦週一 00:00 冬令）。

### 3.5 週末、假日、null、跨日

| 比較項 | 結果 | 標籤 |
|---|---|---|
| 週末列 | 新規則 0（6 個代號）；舊規則美元／歐元／日圓各 59 | FACT |
| null close（假日） | 匯率 5 根、VIX 19 根，已列於第 2 節；腳本分析只用非 null 根，正式 `fetch_yf_close` 也 `.dropna()` | FACT |
| 取數當日盤中根 | 美元／歐元／日圓：週日取數，日 K 最後一根是週五 00:00 倫敦、已完成根，`excluded_not_closed_bars` 為空；CNY／CNH 唯一的一根時間戳＝`regularMarketTime`（週五 22:26:32Z），是盤中值形狀 | FACT |
| 跨日 | 倫敦夏令的根在 UTC 前一日 23:00（新規則已取交易所當地日期）；本報告的跨日現象只出現在這一類 | FACT |
| 同日重複 | 0 | FACT |

## 4. 2026-10-13～14 舊報告疑點，本次是否獲解

舊報告：`20261013T185433Z_run38450455092`、`20261014T041819Z_run38510633247`、`20261014T064729Z_run38524215912`（三份原始檔 sha256 與 `docs/evidence/probe_fx_obs_date/README.md` 記載一致，本檔用 `git show` 唯讀取得）。

| 疑點 | 本次狀態 | 依據 | 標籤 |
|---|---|---|---|
| 10-14 的寫入值與 Yahoo 前收對不上（−0.61%／−1.11%／+0.30%） | **舊解釋（值錯開一個交易日）與本次一致、未被推翻**；現行 prev_weekday 之下，本報告沒有再看到「整體錯開一日」的證據。但這不等於已證明 | 第 3.2、3.3 節 | INFERENCE |
| 條件 (b)：10-14 日 K 值應落在 Yahoo 前收 ≈32.124 | 該根（倫敦 10-14，新語意下觀測日 10-13）現已完成：close **32.10499954**，與 32.124 差 **−0.0591%**；容差「未定」→ **不能判定**。⚠️ 參照點本身有時刻差：32.124 約等於 10-13 UTC 22:00 的小時價（22:00 起點 32.126），而日 K 值對應 UTC 10-14 00:00（小時價 32.113）。**兩者不是同一個瞬間**，差 2 小時、0.04% 左右。同型檢查：本次 11-06 那根 close 33.1093 對 `previousClose` 33.098 為 +0.0341% | 附錄 S3b；小時 K 逐根（10-13 21:00～10-14 01:00 UTC） | FACT（數字）／不能判定 |
| 09-15～09-17 日 K 值與小時 K 對不上 | **NOT RUN**：本報告小時 K 起於 2026-10-06T23:00Z，不涵蓋 09-15～09-17，**無法重現也無法排除**。唯一能說的：這三天的日 K close 在新舊兩份報告完全相同（USD／EUR／JPY；兩份報告重疊的 505 根，差 0 根），所以不是 Yahoo 事後改值 | 附錄 S10 | FACT／NOT RUN |
| 舊報告「最接近值」在 09-15～09-17 落在不同時刻（USD 為終點 18:00／19:00／21:00 倫敦） | 本報告的新資料（10-07～11-06）上，固定位移法沒有出現「各日落在不同時刻」的現象（第 3.2 節），但那是另一段區間、另一種方法，**不能據此說舊疑點已解** | 第 3.2、3.4 節 | INFERENCE／NOT VERIFIED |
| 已完成的歷史根是否被 Yahoo 事後改值 | 與 2026-10-14 報告重疊的 505 根：USD／VIX／EUR／JPY 皆 0 根改值；唯一變化是 10-14 那一根由 null（當時是盤中根）變成有值（USD 32.105、EUR 35.966、JPY 0.20277） | 附錄 S10 | FACT |

### 本次新發現的疑點（舊文件未見登記；成因 NOT VERIFIED）

1. **歐元週一日 K 異常**：歐元 523 根日 K 中 45 根 `|close/open−1|>1%`，其中 **42 根是週一**（`2024-11-11`～`2026-11-02`，close 比 open 低 1.66%～3.41%）。觀測窗內兩根：10-26（日 K 35.388，同日 UTC 00:00 小時價 36.586）、11-02（35.377 對 36.428）。位移後這些值會被寫成上週五的觀測日。美元 0 根，日圓 3 根（週二、三、四各 1）。成因 **NOT VERIFIED**。
2. **日圓水位差**：日 K 與同時刻小時價差 −1.0788%（23 日全為負）；最後一根日 K 0.210287 對 `previousClose` 0.2077（+1.25%）。報告自己的 `meta_snapshot`（日 K 請求）與小時 K 的 `fulldayChange` 一致，所以差異在「日 K 序列」與「即時／小時價」之間。成因 **NOT VERIFIED**；舊稽核 X 已有「日 K 與小時 K 像是不同序列」的登記，本報告**再次**看到。
3. **美元 10-14 單日偏差**：UTC 00:00 對照下，10-14 是 P1 偏差最大（0.0249%）的日子。其餘 P1 日 ≤0.0121%。該根是上次探測時的盤中根、這次才完成。這是描述，不下結論。

## 5. 假日映射（條件 e）

| 項目 | 結果 | 標籤 |
|---|---|---|
| 本報告是否驗證了假日映射 | **否**。報告沒有任何欄位在檢驗假日；`production_rows` 只回列數與首末觀測日 | FACT |
| 以 prev_weekday 重現（附錄 S7；**不是**呼叫正式函式） | 美元／歐元／日圓皆得 518 列、首 2024-11-05、末 2026-11-05，與 `production_rows` 的列數與首末相同 | FACT |
| 被寫成觀測日、但當天 Yahoo 沒有收盤的日期 | 2025-01-01、2025-04-21、2025-12-25、2026-01-01（觀測日恰等於一根 null 日 K 的日期）；另 2024-12-25 為日曆假日但當天 Yahoo 有值，**以日曆而非資料判定**，未經權威假日表驗證 | FACT／INFERENCE |
| 平日卻沒有列的日期 | 2024-12-31、2025-04-17、2025-04-18、2025-12-24、2025-12-31。與 10-14 登記（4 個）相比多 2025-04-18（耶穌受難日，其下一根日 K 為 null，所以該日本身無列，屬假日而非錯置）。⚠️ 上述兩點的差異是本檔重現邏輯與 10-14 稽核邏輯對「假日」的處理不同，**未經第二組比對** | FACT／NOT VERIFIED |
| 結論 | **條件 (e) 仍未解**：程式在本 SHA 沒有假日映射（`rows_from_daily_close` 說明與 49 第 8 節已登記），本報告只是**再次確認問題存在**，不是驗證 | NOT VERIFIED |

## 6. 人民幣 CNY／CNH 的限制

| 項目 | 結果 | 標籤 |
|---|---|---|
| 日 K 根數 | `range=2y` 只回 1 根（其他匯率 523 根）；時間戳 2026-11-06 22:26:32Z，等於 `regularMarketTime`；CNY close 4.9128、CNH 4.9124 | FACT |
| 正式路徑 | 寫 0 列，`skipped`：同一時刻只有 1 根，少於 `FX_MIN_REFERENCE_VOTES`＝20，「無法自證日界」。**這表示 A1 門檻按設計擋下了單根盤中值**，不表示 CNY／CNH 通過 | FACT |
| CNH meta | `firstTradeDate` 為 `null`；CNY 有值（1471474800） | FACT |
| 為何只有 1 根 | Yahoo 行為，成因 **NOT VERIFIED**；也 **NOT RUN**：本批沒有換 range 或 interval 去試 | NOT VERIFIED／NOT RUN |
| 外推 | 單一根的資料無法做任何日界、值對應、DST 判定。**不得由美元結果外推到 CNY／CNH**，也不得推估或換來源（客戶 2026-10-14 裁示） | INFERENCE |

## 7. 是否足以支持開閘決策

**結論：不足。本檔不推薦開閘，不宣稱「美元通過即其他通過」。** 以下是條件 (a)～(e) 目前狀態，與下一個 Decision Gate 所需證據清單。

| 條件 | 目前狀態 | 缺口 | 標籤 |
|---|---|---|---|
| (a) 冬令錯位期再跑 | 已跑一次（run `42455423910`），涵蓋錯位週 10-26～10-30（5 日）與兩地皆冬令 11-02～11-06（5 日） | 樣本很小；是否足夠、是否要補跑（BL-0217 窗口約 11-24、上限約 11-26；報告為週日取數，尚未含 11-09 起的資料）需獨立稽核與決策者定 | 已執行／足夠與否 NOT VERIFIED |
| (b) 10-14 值對前收 | 差 −0.0591%，容差未定 | 容差由誰、依何來源訂；參照「Yahoo 前收」與日 K 值對應時刻不同（約差 2 小時）要先決定比哪兩個量 | 不能判定 |
| (c) 小時 K 時間戳慣例 | 週五收市根零區間、值＝`regularMarketPrice` 且 `regularMarketTime` 恰為整點，支持「起點」 | 只有收市根這一類證據；需非收市時段的獨立證據或來源文件 | INFERENCE／NOT VERIFIED |
| (d) 09-15～09-17 成因 | 本報告小時 K 不涵蓋 | 需要涵蓋該段的小時資料（Yahoo `1mo` 窗口已過，是否取得 NOT VERIFIED）或改以其他方式說明 | NOT RUN |
| (e) 假日映射 | 未解；本報告重現問題 | 映射設計＋獨立稽核；需要權威假日表或以資料自證的規則 | NOT VERIFIED |
| 獨立稽核 | 本檔作者單組，未有第二組複驗 | 獨立稽核報告 | NOT RUN |

下一個 Decision Gate 所需證據清單（只列清單，不裁示）：
1. 獨立稽核者對本報告（含本檔附錄重現腳本）的複驗結論，特別是第 3.2 節「值對應時刻固定在 UTC 00:00」的分制度期比較。
2. 美元的接受標準：(b) 的容差與比較對象、週末跳空（本報告 10-19 的 −0.126%）可否接受，由決策者在「前一交易日收盤」語意下表態。
3. 假日映射的設計與稽核（條件 e）；以及舊登記 N4 的最新列延遲向客戶說明。
4. 逐幣別閘門：`FX_OBS_DATE_RULE_VERIFIED` 目前是全部匯率共用的單一旗標（程式註解與 G3 稽核第 6 節皆已記載）；美元單獨開放前須有分幣別閘門，**本批沒有也不得新增**。
5. 歐元、日圓、人民幣各自的驗證方法：歐元的週一異常與 +0.13% 水位差、日圓的 −1.08% 水位差須先有成因說明；CNY／CNH 須先有可驗的資料量。
6. 舊登記 `get_fx_rate_by_date` 以 UTC 取日、夏令可能前視一天的另案（只有機制推演、未實測）是否處理。
7. 本報告只存在於 `probe/fx-obs-date-results` 分支，**沒有**保存到 main（`docs/evidence/probe_fx_obs_date/` 目前只有三份舊報告）。該分支屬 `DEC-2026-11-08-01` 保留的 10 條之一；是否另行保存本報告是決策者的事，本批沒做。

## 8. 本批未驗項、限制與單組揭露

| # | 項目 | 狀態 |
|---|---|---|
| 1 | 本檔所有判讀由單組作者完成，無第二組複驗；附錄重現腳本與報告同源，**不構成獨立驗證** | 單組揭露 |
| 2 | 沒有呼叫 `rows_from_daily_close`、`_obs_date`、`yahoo_ticker_obs_date_rule` 等正式函式；`production_rows` 取自報告，S7 是以 prev_weekday 的文字描述重現 | NOT RUN |
| 3 | 「UTC 當日 00:00」的一致性建立在 23 日（13／5／5）、小時解析度、單次取數上；價格在午夜附近若恰好平穩，k 的相鄰值不易區分（k＝0 與 k＝+1 在 P1 之外差距大，在 P1 內 k＝+1 的 0.0034% 對 k＝0 的 0.0323%） | INFERENCE |
| 4 | 無法區分「固定 UTC 00:00」與「固定台北 08:00」 | NOT VERIFIED |
| 5 | Yahoo 日 K 的 close 欄位定義（收盤、快照、或前一收盤）沒有來源文件；本檔只描述它與小時價的關係 | NOT VERIFIED |
| 6 | 歐元週一異常、日圓水位差、CNY／CNH 單根的成因 | NOT VERIFIED |
| 7 | 假日以日曆與資料中的 null 判定，沒有權威假日表 | NOT VERIFIED |
| 8 | VIX 的值對應（日 K close 是否＝該日收盤）只有最後兩個資料點；沒有 VIX 小時 K | NOT RUN |
| 9 | 敏感字串檢查為樣式掃描；`proxy_env_set`、`proxy_used_by_infra` 只寫布林值 | 限制 |
| 10 | 舊報告取自 `probe/fx-obs-date-results` 分支（`git show`，唯讀）；其中 `run38524215912` 的 sha256 與保存檔 README 記載一致，另兩份舊報告本檔只引用 49 與 README 已登記的數字、**未重算** | 限制 |
| 11 | 本批沒有改 BL-0217、49、HANDOFF、BACKLOG 或任何閘門；狀態同步是後續工作 | NOT RUN |
| 12 | 本檔提到的 DEC／BL 編號只作指標，是否仍現行未逐條複驗 | 限制 |

## 附錄：現算指令與腳本

報告複本與舊報告以 `git show origin/probe/fx-obs-date-results:results/<目錄>/report.json` 取出。以下腳本唯讀、不連網；用法：`python3 -I recompute.py REPORT.json [OLD_REPORT.json]`，輸出分節 S1～S10，本檔數字出自這些輸出。基本檢查另用：`sha256sum report.json`；`grep -ciE "<第 1 節所列樣式>" report.json`；`grep -oE "https?://[^\" ]+" report.json | sort | uniq -c`；`git show origin/main:services/v2_tables/market_indicator.py | grep -nE "^FX_OBS_DATE_RULE_VERIFIED"`。

```python
# usage: python3 -I recompute.py REPORT.json [OLD_REPORT.json]   (read-only; no network)
import json,sys,statistics as st,collections
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
R=json.load(open(sys.argv[1])); T=R['tickers']; U=timezone.utc
L=ZoneInfo('Europe/London'); C=ZoneInfo('America/Chicago')
def ut(t): return datetime.fromtimestamp(t,U)
print('## S1 per-ticker summary')
for k,v in T.items():
    m=v['meta_summary']; s=v['subsets_exchange_tz']['non_null']; dd=v['obs_date_rule_diff']; p=v['production_rows']
    print(k,'status',v['status'],'raw',v['raw_bar_count'],'null',v['null_close_count'],'nonnull',s['bar_count'],'tz',m['exchangeTimezoneName'],
          'diff',dd['diff_count'],'/',dd['total'],'weekend(new)',s['obs_date_weekday']['weekend_count'],'dup(new)',s['obs_date_weekday']['duplicate_obs_date_count'],
          'rule',p['obs_date_rule'],'rows',p['row_count'],p['first_obs_date'],p['last_obs_date'],'skipped',len(p['skipped']),'hourly' in v)
for k in ('USDTWD=X','EURTWD=X','JPYTWD=X'):
    s=T[k]['subsets']['non_null']['obs_date_weekday']; print('legacy-UTC',k,'weekend',s['weekend_count'],'weeks missing Fri',s['iso_weeks_missing_friday_count'],'| new-rule weeks missing Fri',T[k]['subsets_exchange_tz']['non_null']['obs_date_weekday']['iso_weeks_missing_friday'])
print('## S2 DST transitions seen in daily stamps (UTC hh:mm change)')
for k,z in (('USDTWD=X',L),('^VIX',C)):
    r=T[k]['raw_daily_full']['t']; prev=None
    for t in r:
        h=ut(t).strftime('%H:%M')
        if prev and prev!=h: print(k,prev,'->',h,'first bar',datetime.fromtimestamp(t,z).strftime('%Y-%m-%d %a %H:%M %Z'))
        prev=h
print('## S3 hourly window / meta (USD)')
u=T['USDTWD=X']; dv=u['daily_value_check']; print(dv['hourly_first_utc'],dv['hourly_last_utc'],'compared',dv['compared'],'ties_gt_1',dv['match_precision']['ties_gt_1'],'within_tol(1e-6)',dv['match_precision']['within_tol'])
print('## S3b bar value vs Yahoo self-reported previous close (USD)')
r=T['USDTWD=X']['raw_daily_full']
for t,c in zip(r['t'],r['close']):
    if datetime.fromtimestamp(t,L).strftime('%Y-%m-%d')=='2026-10-14': print('bar 2026-10-14 close',c,'vs 32.124 (doc 49 cond. b) pct',round((c-32.124)/32.124*100,4))
v=T['USDTWD=X']['hourly']['meta_snapshot']['values']; print('bar 2026-11-06 close',r['close'][-1],'vs previousClose',v['previousClose'],'pct',round((r['close'][-1]-v['previousClose'])/v['previousClose']*100,4))
print('## S5b Monday bar close vs prior Friday last hourly close')
for k in ('USDTWD=X','EURTWD=X'):
    r=T[k]['raw_daily_full']; h=T[k]['hourly']['raw']; H=[(t,c) for t,c in zip(h['t'],h['close']) if c is not None]
    for t,c in zip(r['t'],r['close']):
        D=datetime.fromtimestamp(t,L)
        if c is None or D.strftime('%a')!='Mon' or D.strftime('%Y-%m-%d')<'2026-10-12': continue
        f=max(x for x in H if t-80*3600<x[0]<t-12*3600); print(k,D.date(),'Mon close',round(c,4),'Fri last hourly',ut(f[0]).strftime('%a %H:%M'),round(f[1],4),'pct',round((c-f[1])/f[1]*100,4))
print('## S4 daily close vs hourly open at UTC D 00:00 (signed %, hourly-daily), by period; and vs London-midnight open')
for k in ('USDTWD=X','EURTWD=X','JPYTWD=X'):
    r=T[k]['raw_daily_full']; h=T[k]['hourly']['raw']; Ho={t:o for t,o in zip(h['t'],h['open']) if o is not None}
    rows=[]
    for t,c in zip(r['t'],r['close']):
        if c is None: continue
        D=datetime.fromtimestamp(t,L)
        u0=int(datetime(D.year,D.month,D.day,tzinfo=U).timestamp()); l0=t
        if u0 in Ho and l0 in Ho: rows.append((D.strftime('%Y-%m-%d'),(Ho[u0]-c)/c*100,(Ho[l0]-c)/c*100))
    for lab,lo,hi in (('P1 Lon BST/NY EDT','2026-10-07','2026-10-23'),('P2 Lon GMT/NY EDT','2026-10-26','2026-10-30'),('P3 both std','2026-11-02','2026-11-06'),('all','2026-10-07','2026-11-06')):
        s=[x for x in rows if lo<=x[0]<=hi]
        print(k,lab,'n',len(s),'UTC00 med|%|',round(st.median(abs(x[1]) for x in s),4),'max|%|',round(max(abs(x[1]) for x in s),4),'med signed',round(st.median(x[1] for x in s),4),'| London00 med|%|',round(st.median(abs(x[2]) for x in s),4))
print('## S5 hourly weekly gaps USD (UTC)')
h=T['USDTWD=X']['hourly']['raw']; ts=[t for t,c in zip(h['t'],h['close']) if c is not None]
for a,b in zip(ts,ts[1:]):
    if b-a>3*3600: print('last',ut(a).strftime('%a %m-%d %H:%M'),'next',ut(b).strftime('%a %m-%d %H:%M'))
z=[ut(t).strftime('%a %m-%d %H:%M') for t,o,hi,lo,c in zip(h['t'],h['open'],h['high'],h['low'],h['close']) if c is not None and o==hi==lo==c]
print('zero-range bars',z)
for k in ('USDTWD=X','EURTWD=X','JPYTWD=X'):
    v=T[k]['hourly']['meta_snapshot']['values']; hh=T[k]['hourly']['raw']
    print(k,'rmp',v['regularMarketPrice'],'rmt',ut(v['regularMarketTime']).strftime('%m-%d %H:%M:%S'),'prevClose',v['previousClose'],'rmp-fulldayChange',round(v['regularMarketPrice']-v['fulldayChange'],4),'last hourly stamp',ut(hh['t'][-2]).strftime('%m-%d %H:%M'),hh['close'][-2],'last daily',T[k]['raw_daily_full']['close'][-1])
print('## S6 daily close vs open anomalies (|c/o-1|>1%)')
for k in ('USDTWD=X','EURTWD=X','JPYTWD=X'):
    r=T[k]['raw_daily_full']; w=collections.Counter(); n=0
    for t,o,c in zip(r['t'],r['open'],r['close']):
        if o is None or c is None: continue
        if abs(c/o-1)>0.01: n+=1; w[datetime.fromtimestamp(t,L).strftime('%a')]+=1
    print(k,n,dict(w))
print('## S7 obs dates by prev_weekday replication (not the production function)')
def pw(d):
    d-=timedelta(days=1)
    while d.weekday()>=5: d-=timedelta(days=1)
    return d
for k in ('USDTWD=X','EURTWD=X','JPYTWD=X'):
    r=T[k]['raw_daily_full']; nn=[];nl=[]
    for t,c in zip(r['t'],r['close']): (nl if c is None else nn).append(datetime.fromtimestamp(t,L).date())
    obs=sorted(pw(d) for d in nn); S=set(obs); d=obs[0]; miss=[]
    while d<=obs[-1]:
        if d.weekday()<5 and d not in S: miss.append(str(d))
        d+=timedelta(days=1)
    print(k,len(obs),obs[0],obs[-1],'gaps',miss,'null-D',[str(x) for x in nl],'written=nullD',[str(o) for o in obs if o in set(nl)])
print('## S8 VIX')
v=T['^VIX']; r=v['raw_daily_full']
print('last2 closes',[(datetime.fromtimestamp(t,C).strftime('%m-%d'),c) for t,c in list(zip(r['t'],r['close']))[-2:]],'rmp',v['meta_snapshot']['values']['regularMarketPrice'],'fulldayChange',v['meta_snapshot']['values']['fulldayChange'],'nulls',v['null_close_count'])
print('## S9 CNY/CNH')
for k in ('CNYTWD=X','CNHTWD=X'):
    v=T[k]; print(k,'raw',v['raw_bar_count'],'t',ut(v['raw_daily_full']['t'][0]).strftime('%Y-%m-%d %H:%M:%S'),'close',v['raw_daily_full']['close'][0],'last==rmt',v['last_bar']['equal'],'rows',v['production_rows']['row_count'],'skipped',v['production_rows']['skipped'])
if len(sys.argv)>2:
    O=json.load(open(sys.argv[2])); print('## S10 vs old report',O.get('generated_at_utc'))
    for k in ('USDTWD=X','^VIX','EURTWD=X','JPYTWD=X'):
        a=O['tickers'][k]['raw_daily_full']; b=T[k]['raw_daily_full']; N=dict(zip(b['t'],b['close'])); same=diff=flip=0
        for t,c in zip(a['t'],a['close']):
            if t not in N: continue
            if c is None or N[t] is None: flip+= (c is None)!=(N[t] is None); same+= (c is None and N[t] is None)
            elif abs(c-N[t])<=1e-9*abs(c): same+=1
            else: diff+=1
        print(k,'overlap same',same,'diff',diff,'null<->value',flip)
```
