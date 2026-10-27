# 探測報告：TWSE／MOPS 公開端點（BL-0509 EPS Data Source Probe）

**目前沒有放任何報告檔**（先不放）。本目錄只說明報告怎麼產生、欄位意義。**本探測只做 probe／spec，不接正式 signal、不接 AI Brain；actual／trailing 不得冒充 forward。**

## 怎麼產生

- 腳本：`scripts/probe_twse_eps.py`（只發 HTTPS GET，主機限 `openapi.twse.com.tw`、`www.twse.com.tw`、`mopsov.twse.com.tw`、`mops.twse.com.tw`）。
- Workflow：`.github/workflows/twse_eps_probe.yml`。手動 `workflow_dispatch`，或把 main 推到按鈕分支 `probe/twse-eps-trigger`；**無排程**。執行的永遠是 main 上的腳本（`checkout ref: main`）。
- 報告推到專用分支 `probe/twse-eps-results`，路徑 `results/<時間戳>_run<id>/report.json.gz`（**不推 main**）。
- 本機執行：`python scripts/probe_twse_eps.py --out probe_out/twse_eps_report.json.gz`。開發沙箱連不到 TWSE，也沒有 NAS 的 `PROXY_URL`，**真實報告只能由 Actions 產生**。

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
- 離線測試：`tests/test_probe_twse_eps.py`。
