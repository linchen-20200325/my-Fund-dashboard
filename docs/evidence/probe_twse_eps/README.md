# 探測報告：TWSE／MOPS 公開端點（BL-0509 EPS Data Source Probe）

~~**目前沒有放任何報告檔**（先不放）。~~ → 已存一份報告（見下方「已存報告」；狀態更新，不是漏刪）。本目錄也說明報告怎麼產生、欄位意義。**本探測只做 probe／spec，不接正式 signal、不接 AI Brain；actual／trailing 不得冒充 forward。**

## 怎麼產生

- 腳本：`scripts/probe_twse_eps.py`（只發 HTTPS GET，主機限 `openapi.twse.com.tw`、`www.twse.com.tw`、`mopsov.twse.com.tw`、`mops.twse.com.tw`）。
- Workflow：`.github/workflows/twse_eps_probe.yml`。手動 `workflow_dispatch`、把 main 推到按鈕分支 `probe/twse-eps-trigger`，或 **固定排程（2026-10-27 起，見下方「多日排程」）**。執行的永遠是 main 上的腳本（`checkout ref: main`）。
- 報告推到專用分支 `probe/twse-eps-results`，路徑 `results/<時間戳>_run<id>/report.json.gz`（**不推 main**）。
- 本機執行：`python scripts/probe_twse_eps.py --out probe_out/twse_eps_report.json.gz`。開發沙箱連不到 TWSE，也沒有 NAS 的 `PROXY_URL`，**真實報告只能由 Actions 產生**。

## 多日排程（2026-10-27 客戶裁示 A；BL-0509 shadow probe）

- **性質**：僅 BL-0509 唯讀 shadow probe。checkout main、不接正式 signal／AI Brain／正式資料層、不新增付費來源、不暴露 secret（`PROXY_URL` 仍只在「Run probe」步驟 env）、結果仍只推 `probe/twse-eps-results`。
- **時間**（只週一至週五，分鐘避開整點／半點）：`37 11 * * 1-5` ＝ 台北週一至週五 19:37（當日盤後）；`43 22 * * 1-5` ＝ 台北週二至週六 06:43（前一交易日的隔日清晨）。GitHub 排程可能延遲或偶爾漏跑，以報告內 `generated_at_utc` 為準。cron 不知道休市日，休市日也會跑（得到「來源日期沒推進」的觀察）。
- **預計**收集 3～5 個交易日（約 2026-10-28 ～ 2026-11-03）後，由客戶裁示是否停用。
- **如何停用**：刪除 `.github/workflows/twse_eps_probe.yml` 中 `on:` 下的整個 `schedule:` 區塊（兩行 cron）並開 PR 合併進 main；同時把 `tests/test_twse_eps_probe_workflow.py` 的 `test_schedule_*` 與 `test_push_trigger_only_button_branch` 內的 `schedule` 斷言改為「無排程」。手動與按鈕分支觸發不受影響。
- **請求量**：每次 run 約 16 個端點 × 2 路徑 ＋ 條款頁（含 swagger 內最多 2 條連結、最多 3 跳）；請求間隔 1 秒、單請求最多重試 1 次、只發 GET。每日 2 次、僅週一至週五。

## 條款研究（`terms_reach` 群組與 swagger 條款連結）

- 資料端點一律不跟隨 redirect。只有 `terms_reach` 群組與 swagger `info.description`／`info.termsOfService` 內出現的條款連結，允許最多 3 跳；**每一跳目標的 scheme 與主機都必須在白名單內**，否則停並記 `blocked_redirect`（目標從不被請求）。
- 每跳只記（遮蔽後）host、status、path、content-type、body 長度與 sha256；頁面文字只計「使用條款／授權／著作權／商業」的**出現次數**，**不存整頁文字**。swagger 內條款連結的完整 URL 與 host 存在 `terms_research.swagger_description.links`（前次只存截斷摘要）。
- **不下授權結論**。報告恆標 `⬜ 授權條款尚未完成驗證`；「頁面存在、含關鍵詞」不等於已讀懂條款、更不等於可商用。正式條款內容須由人閱讀後判定。

## 新增報告欄位（schema_version 2）

- 每個資料端點的 `timeseries`：`row_count`、`schema_hash`（欄位名清單 hash，含欄位順序）、`top_level_date_raw`（rwd 頂層 `date` 原字串）、`latest_source_date`（與 `freshness` 同口徑）、`latest_row_date`／`row_date_min`／`row_date_max`、前後各 5 筆的日期 min/max、`row_order`、空字串／`-`／null 格數與各欄計數（`missing_by_field`）。**只計數，不補 0、不補值。**
- 頂層 `openapi_vs_rwd`：MI_INDEX、FMTQIK、BWIBBU 三組 openapi 與 rwd 的 `latest_source_date` 差（天，rwd − openapi）；任一側缺值則 `diff_days` 為 null 並註明原因。
- 頂層 `terms_research`（見上節）。

## 跨 run 分析：`scripts/analyze_twse_probe_series.py`

```
git fetch origin probe/twse-eps-results && git worktree add /tmp/twse_results FETCH_HEAD   # 或任何取得 results/*/report.json.gz 的方式
python scripts/analyze_twse_probe_series.py /tmp/twse_results/results docs/evidence/probe_twse_eps --out probe_out/series.md
```

純標準庫、離線、唯讀；輸入目錄（遞迴找 `*.json.gz`）或檔案，只收 `probe == "twse_eps"`。輸出 Markdown：各端點跨 run 的 sha／schema_hash／列數是否變化、`latest_source_date` 推進與 lag_days、各來源日期首次被觀察到的時點（上界）、openapi vs rwd 差距序列、缺值比例、疑似 revision、direct vs nas 一致性、條款研究摘要。樣本不足（<2 份報告、<2 個不同來源日期、<3 個台北日）一律明寫「樣本不足」。`--transport nas_proxy` 可改看另一條路徑。

**多日序列可以得出（觀察，不是裁示）**：回應／schema／列數是否變動；來源日期推進節奏與落後天數；來源日期首次被觀察到時點的上界（≈ 發布延遲上界）；openapi 與 rwd 日期差是否穩定；缺值格數／比例是否變動；條款頁是否存在、是否含關鍵詞。

**不能得出**：授權／可否商用；真正的 revision（sha 不同只是線索，報告不存全表，無法比對同代號欄位值）；正式更新頻率或 SLA（3～5 個交易日涵蓋不到財報季、假期、補班日）；精確發布時點；流量是否經過 NAS（無出口 IP 證據）；市場整體 trailing PE；任何可接正式 signal／AI Brain／正式資料層的結論。

## 兩條連線路徑

每個端點各量兩次，互不降級：

| 路徑 | 意義 |
|---|---|
| `direct` | 不設 proxy 的 runner IP 直連（`trust_env=False`） |
| `nas_proxy` | `PROXY_URL` 環境變數 → requests Session proxies（比照 `scripts/fetch_nav_cache.py`）。未設則 `outcome=proxy_not_configured`，不發請求 |

不使用 `infra.proxy.fetch_url`：它的 proxy 設定只讀 Streamlit secrets，且 NAS 失敗會自動改直連，無法分辨實際走哪條。

## 報告欄位

頂層：`schema_version`、`generated_at_utc`、`run_date_taipei`、`trigger_sha`（觸發 commit）、`executed_sha`（實際執行 commit）、`proxy.enabled`（只有 true／false）、`stale_after_days`（探測用啟發式，非正式 freshness 規格）、`endpoints`、`swagger_summary`、`research_metric`、`complete`。

`endpoints[].transports.<direct|nas_proxy>`：
- `outcome`：`ok`／`empty_dataset`／`reachable`（僅 reach 類）／`http_error`／`unreachable`／`not_json`／`empty_response`／`proxy_not_configured`／`blocked_by_allowlist`。
- `http_status`、`content_type`、`latency_ms`、`response_bytes`、`body_sha256`（供比對兩路徑內容是否相同）、`error`（已遮蔽）。
- `schema`：top-level 結構、欄位名＋型別、全量筆數 `n_rows`、前 3 筆 `sample`（字串截 80 字）。
- `source_date_fields`、`freshness`：來源自帶日期欄（欄名含「日期」或 `date`）；`state` 為 `fresh`／`stale`／`no_source_date`，對比台北執行日。**沒有來源日期就是 `no_source_date`，不補值、不補 0。**

`swagger_summary`：只列與 MI_INDEX／FMTQIK／BWIBBU／t187ap05／t187ap06／t187ap14／MI_5MINS_HIST 或「本益比／每股盈餘／綜合損益／加權股價指數」相關的 path 及其 summary／description，供研究更新頻率與授權；**不做內容結論**。條款頁網址（`twse_terms_candidate`）為候選、未驗證，只記 HTTP 可達性。

`research_metric`：只記「來源是否提供市場整體 trailing PE 欄位」與計算輸入是否齊備；**不自創市場 PE，不輸出 implied_trailing_index_earnings 數值**（恆為 `null`）。universe／分母口徑標「待驗」。

## 安全

- 報告與本目錄**不含**任何 `PROXY_URL`、帳密、NAS host／port；只記 `proxy.enabled` 與各路徑結果。錯誤原文先遮蔽，落盤前整份再掃一次。
- 離線測試：`tests/test_probe_twse_eps.py`、`tests/test_twse_probe_multiday.py`；workflow 守衛：`tests/test_twse_eps_probe_workflow.py`。

## 已存報告（2026-10-27）

| 本目錄檔名 | GitHub run | 報告內 `generated_at_utc` | `trigger_sha`＝`executed_sha` | 保存來源 |
|---|---|---|---|---|
| `20261027T143156Z_run40521810949_report.json.gz` | `40521810949` | 2026-10-27T14:30:58Z | `eb272e931446f95109ea0d44e31ddbda8de6cb80` | 分支 `probe/twse-eps-results` 的 `results/20261027T143156Z_run40521810949/report.json.gz`（與本檔 sha256 相同） |

- 檔案大小 7787 bytes；sha256 `be0b4b4232df282209298f3cee3d1157f118b94d5c5d83688bc8f6d47ad469dd`（2026-10-27 實算）。
- 結果解讀與未驗證項見 `docs/v2/68_bl0509_eps_probe_result.md`；該文件不是 Data Source Decision Gate 裁示。
