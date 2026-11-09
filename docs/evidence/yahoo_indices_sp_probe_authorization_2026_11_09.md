# Yahoo 指數日線受控唯讀探測：授權與執行說明（方案 B「S＋P」）

> 登記：`DEC-2026-11-09-08`（見 `docs/DECISIONS.md`）。
> 性質：授權要點轉述與工具說明。**本批只建立並離線驗證工具，未執行探測、未觸發 workflow、未連網。**
> 作者：專案 AI 單組，未經第二組驗證。

## 1. 授權要點（經總管轉達，非逐字，無逐字存檔）

客戶 2026-11-09 授權方案 B「S＋P」，最多 4 次 HTTP 實際發送，串行、請求間隔至少 5 秒、禁止自動重試。
任何失敗（非 2xx、429、封鎖、例外、空回應、JSON 解析失敗、schema 異常、時間戳非單調）立即停止，不再發後續請求。
遇限流或封鎖：30 分鐘內不得重跑，再次執行須重新授權。禁止其他代號、interval、range 或額外取數；不抓 FRED 或 USD/TWD。
核准建立最小專用腳本與 GitHub Actions workflow。

## 2. 四個授權請求

端點與標頭與既有 `repositories/macro/yf.py` 取數一致（`https://query1.finance.yahoo.com/v8/finance/chart/<代號>`，
同樣的 User-Agent 與 Accept-Language），以便比較。實際 URL 會逐筆寫進報告。

| 序 | 代號 | 參數 |
|---|---|---|
| 1 | `^GSPC` | `interval=1d`、`range=2y` |
| 2 | `^VIX` | `interval=1d`、`range=2y` |
| 3 | `^TWII` | `interval=1d`、`range=2y` |
| 4 | `^VIX` | `period1=1780012800`（2026-05-29T00:00Z）、`period2=1780963200`（2026-06-09T00:00Z）、`interval=1d`；窗內含 2026-06-03 |

## 3. 硬上限與停止條件

* 四個請求硬編碼於腳本，沒有任何 CLI 參數或環境變數能增減代號、range、interval。
* 腳本用標準庫單次 GET，不 import `infra.proxy`／`fetch_url`、不用 `PROXY_URL`、不讀環境代理、不重試、不跟隨轉址（3xx 視為失敗並停止）。
* 唯一送出點在送出之前先遞增 `http_requests_attempted`，達 4 後再呼叫一律在程式層拒絕。
* 失敗後未發的請求在報告中記為 `skipped_not_attempted` 並寫明原因，不填 0、不當成功。
* 限流或封鎖（HTTP 401／403／429／999）時報告帶 `cooldown_notice`。

## 4. 執行方式與一次性保護

* workflow：`.github/workflows/yahoo_indices_sp_probe.yml`。觸發只有兩種：手動 `workflow_dispatch`（無輸入），
  或 push 到按鈕分支 `probe/yahoo-indices-sp-trigger`（內容不被執行，checkout 一律 `ref: main`）。無排程。
* 結果只推到專用分支 `probe/yahoo-indices-sp-results` 的 `results/yahoo_indices_sp_20261109/report.json`；
  不推 main、不 force，與既有 FX 探測的分支完全分開。
* 一次性保護：探測前先檢查結果分支是否已有該報告檔，已有則 workflow 失敗且不發任何請求；
  腳本內另有輸出路徑已存在即拒絕。再次執行須重新授權並更換授權代碼。
* 離線自跑：`python scripts/probe_yahoo_indices_sp.py --dry-run` 只印出四個 URL，不發請求。

### 4.1 claim 先行與「已使用授權」判定

* 發任何請求之前，workflow 先把 `results/yahoo_indices_sp_20261109/claim.json`（run id、attempt、trigger／executed SHA、UTC 時間）推到結果分支；推送失敗則整個 job 失敗且不發任何請求。
* 一次性保護檢查 `claim.json` 或 `report.json` 任一已存在即拒絕。`GITHUB_RUN_ATTEMPT` 不等於 1（re-run）一律拒絕。
* claim 存在而無 report，視為授權已使用（請求可能已發出但報告未寫出）；須人工確認並重新授權才可再跑。
* 腳本以例外保護盡力寫出失敗報告（含 `http_requests_attempted` 與遮罩後的 `unhandled_exception` 訊息）。
* 單一回應讀取與 gzip 解壓縮上限為 5 MB（**專案 AI 建議值，非客戶裁示**），超過視為 `response_too_large` 並停止。

## 5. 報告欄位（純描述）

頂層：授權參考、資料來源字樣（Yahoo Finance chart v8，非 TWSE／CBOE 官方）、`trigger_sha`、`executed_sha`、
run id 與 attempt、workflow 名稱、`http_requests_attempted`、`stop_reason`、`failed_request_index`、
`cooldown_notice`（限流時）、`skipped_not_attempted`、解讀限制文字。

每個請求：請求 URL、送出前後 UTC 時間、HTTP 狀態、白名單回應標頭（不含 set-cookie 與任何 token）、位元組數、
原始回應 gzip＋base64 與 sha256（對原始位元組）、`meta` 摘要（`exchangeTimezoneName`、`gmtoffset`、`timezone`、
`instrumentType`、`regularMarketTime`、`dataGranularity`、`validRanges`）、逐根時間戳的 UTC ISO、UTC 日期、
依 `exchangeTimezoneName` 換算的交易所本地日期與星期、close 為 null 的 index 列表，以及與原始 JSON 長度一致性自檢。
第 4 個請求另列哪些 bar 的 UTC 日期或交易所本地日期為 2026-06-03（僅描述）。
失敗請求記狀態與遮罩後的錯誤原文，不補造資料。報告與 log 經遮罩函式處理，不含 token、Authorization、cookie 或環境變數內容。

## 6. 判讀限制

* 單次探測不得判定永久日期規則。
* 不變更 Eligibility、母集合、分母、日期轉換；`FX_OBS_DATE_RULE_VERIFIED` 維持 `False`。
* 不自動啟動第二批探測。
* 重跑（含冷卻期後）一律須重新授權；限流或封鎖後 30 分鐘內不得重跑。

## 7. 本批未驗證事項

GitHub Actions 能否直連 Yahoo、Yahoo 實際回應形狀、dispatch API 是否回 403、3xx 在實際環境的表現，皆須由實跑確認，本批未驗。


## 8. 已知風險

* push 事件執行的是被推 commit 內的 workflow 檔本身。能推按鈕分支且有 workflows 權限者可改寫該檔，與既有 FX 探測相同；本 workflow 僅以 `ref: main` 限制腳本內容，擋不到這條路。
* `actions/checkout` 與 `actions/setup-python` 以版本標籤固定（`@v4`、`@v5`），未釘 commit SHA，與既有 workflow 一致。
