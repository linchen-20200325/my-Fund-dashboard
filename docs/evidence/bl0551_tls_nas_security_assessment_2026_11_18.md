# BL-0551 TLS 驗證與 NAS 中繼站：唯讀離線安全評估（2026-11-18）

> **單組作者，尚待兩組獨立稽核（資安級）。** 本文所有結論未經非作者複驗；全稱句（「只有／沒有／全部」）皆為單組 `git grep` 與讀碼結論，**不是**窮舉。
> **不構成授權、不是客戶裁示、不改任何程式、設定、secrets、NAS 或連線策略。** 授權來源為客戶限縮授權（經對話提示語轉達，待核）：唯讀、離線；本文作者沒有發出任何網路請求，也沒有讀取任何真實 secrets。
> 基準：main `9e714861`（本分支 `batch-a`）。符號以「檔案::符號」定位，不寫行號。
> 證據標記：**FACT**＝讀碼或讀文件可複驗（附出處）；**INFERENCE**＝由事實推得、可被推翻；**RECOMMENDATION**＝建議；**NOT VERIFIED**＝本沙箱無法驗證（多為部署事實）。
> 前置：`docs/BACKLOG.md` 的 BL-0550（NAS 診斷頁待裁示）、BL-0551（本題登記）、BL-0555（Gate-D 路徑 B 依賴 BL-0551 揭露）。

---

## 0　AI 總管推薦（結論先行）

**RECOMMENDATION**

1. **正式接線不採「停用 TLS 驗證」。** 現況的停用是歷史上為了「Squid CONNECT 相容」留下的設定，這個前提本身**沒有被驗證過**，而 repo 內有反向線索（見第 2 節 E1、E3）。把一個未驗證的相容性假設升格成正式資料路徑的預設，等於讓 NAV、匯率、總經序列的真實性（CLAUDE.md §1）建立在「路徑上沒有人改資料」的信任上。
2. **先收證據、後談改碼。** 能否保留驗證，取決於一個部署事實：**NAS 上的 Squid 是單純的 CONNECT 隧道，還是會 ssl_bump／改寫的 TLS 終結代理**。這個事實本沙箱驗不到，必須由 NAS 持有人用第 8 節的唯讀方式取得（建議先做 D1～D5，不需改任何東西）。
3. **依證據分支，最小可逆的第一步是「以主機為單位、預設不變、可關閉」的驗證開關**（第 9 節）。優先順序：先開**帶有金鑰在網址參數的主機**（FRED、FinMind），再開 Yahoo，最後才碰被指稱不相容的 MoneyDJ。
4. **與驗證無關、可獨立處理的兩件事**（不需等相容性結論）：(a) 代理腿是明文 HTTP＋Basic 帳密（文件化設定），任何路徑上的觀察者都能取得帳密；(b) 舊版側欄與資料守衛頁的遮罩寫法對含 `@` 的密碼會漏尾段、且側欄直接顯示 NAS 的 host:port。

### 最重要的三個發現

| # | 發現 | 證據等級 |
|---|---|---|
| 1 | **三個來源的 TLS 政策不一致，且「有 proxy 就不驗」是全站預設。** `infra.proxy.fetch_url`（MoneyDJ、FundClear 的主要取數路徑，也是 FRED／FinMind／Yahoo 的路徑）在有 proxy 設定時 `verify=False`；FundClear 離岸 API 與多處 `requests` 呼叫以 `_ssl_verify()` 繼承同一規則；**TDCC 走 `urllib.request.urlopen`，程式碼沒有任何關閉驗證的動作**（但實際是否在 NAS 之後成功取數，NOT VERIFIED）。FX 備援與兩個診斷按鈕更是**寫死** `verify=False`，連直連模式也不驗。 | FACT |
| 2 | **「Squid CONNECT 與 MoneyDJ 憑證不相容」的前提沒有證據，反向線索反而存在。** (a) repo 內的 NAS 設定文件只有 `http_port` 與 CONNECT 允許規則，沒有 `ssl_bump`，依此設定 TLS 是端到端的；(b) 2026-10-14 MoneyDJ 探測報告是 **GitHub runner 直連、`verify=True`**，兩個 MoneyDJ 主機都完成 TLS 並回 HTTP 狀態；(c) BL-0214 自己登記「NAS Squid 是否 ssl_bump 未驗」。 | FACT（a）（b）（c）；「所以驗證可以保留」為 INFERENCE |
| 3 | **代理憑證的暴露面大於 TLS 驗證本身。** 文件化的 NAS 設定是明文 HTTP 代理＋Basic 驗證＋路由器對外轉發 3128；憑證同時存在於 Streamlit secrets 與至少 7 個 workflow 的環境變數。UI 端：舊側欄顯示 NAS 的 host:port；側欄與資料守衛頁的遮罩寫法，對**含 `@` 的密碼**會把尾段原樣顯示（本機用假值驗證）。 | FACT（程式與文件）；實際部署是否照文件 NOT VERIFIED |

---

## 1　方法與範圍

**FACT**：只讀 repo 檔案。讀過的主要檔案：`infra/proxy.py`、`fund_fetcher.py`（`fetch_url_with_retry`）、`repositories/fund/{sources,declared_profile,fund_orchestration,nav_metrics,fx_and_main}.py`、`repositories/fundclear_offshore.py`、`services/v2_tables/{fund_keys,exp_profile,masking}.py`、`ui/sidebar.py`、`ui/tab5_data_guard.py`、`ui/helpers/settings_diag/fetch_diag_section.py`、`scripts/fetch_nav_cache.py`、`NAS_PROXY_GUIDE.md`、`NAS_PROXY_FOR_AI.md`、`secrets.toml.example`、`.streamlit/`、`requirements.txt`、`.github/workflows/`、`docs/BACKLOG.md`（BL-0214／0550／0551／0555）、`docs/evidence/gate_d_two_paths_card_2026_11_17.md`、`docs/evidence/probe_moneydj_basic/`（含解壓後的報告 JSON）。

**本文做過的本機動作**（皆不連網）：`git grep` 與讀檔；用**假值**在本機跑兩行純字串 regex，確認第 6 節 R3 的遮罩缺陷；解壓並讀取已保存的探測報告。沒有執行任何會發請求的程式、沒有跑測試以外的 Python 專案程式碼。

**掃描範圍的誠實限制**：用的字表為 `verify=`、`ssl.`、`SSLContext`、`CERT`、`urlopen`、`HTTPSHandler`、`proxies=`、`HTTP(S)_PROXY`、`install_global_urllib_proxy`、`disable_warnings` 與若干變體。**動態組出的呼叫、經第三方 SDK（`yfinance`、`gspread`、`google-auth`）內部發出的請求、別名包裝，這組字表看不到**（BL-0551 與 CLAUDE.md §-1.5.1c 判定 2 記載過同型缺陷）。以下「沒有」一律只代表「這組字表沒命中」。

---

## 2　程式事實：TLS 與 proxy 的共通機制

### 2.1　`infra/proxy.py`

| 項目 | FACT | 出處（檔案::符號） |
|---|---|---|
| proxy 設定來源 | 讀 `st.secrets["PROXY_URL"]`，否則組 `http://{username}:{password}@{endpoint}`（舊 `[proxy]` 區段）；`http` 與 `https` 兩鍵填同一個 URL，**scheme 是 `http`**；快取 300 秒；任何例外一律回「無 proxy」（靜默降級為直連） | `infra/proxy.py::get_proxy_config` |
| `_ssl_verify()` | 有 proxy 設定回 `False`，沒有回 `True`；單元測試把「有 proxy 時為 False」釘成契約 | `infra/proxy.py::_ssl_verify`；`tests/test_proxy_infra.py::test_ssl_verify_false_when_proxy_enabled` |
| `fetch_url` 的 TLS | proxy 路徑 `verify=not bool(proxy)`＝`False`；**降級直連**以 `proxies={}`、`verify=True` 重打 | `infra/proxy.py::fetch_url` |
| 降級直連的觸發 | 只有 `ProxyError`、累計兩次 403、`Timeout`；**通用例外（含 `SSLError`）走 `except Exception: break`，不觸發降級**；407 立即回 `None`、不降級 | `infra/proxy.py::fetch_url` |
| 全域警告抑制 | 模組載入即 `urllib3.disable_warnings(InsecureRequestWarning)`：關掉驗證時不會有任何警告，營運上看不到「這批流量沒驗證」 | `infra/proxy.py`（模組層） |
| urllib 全域 opener | 模組載入即 `install_global_urllib_proxy()`：有 proxy 設定就 `install_opener(build_opener(ProxyHandler(...)))`，之後所有裸 `urlopen` 走 NAS；**無設定時也標記「已安裝」**（負向快取），之後 secrets 才出現也不會補裝 | `infra/proxy.py::install_global_urllib_proxy` |
| 日誌遮罩 | `fetch_url` 印網址一律 `_url_log`（砍掉 `?` 之後）；三處印例外物件改印 `_exc_log(e)`（砍掉例外文字中的查詢字串）。**只限 `fetch_url` 內三處**；測試鎖住 | `infra/proxy.py::_exc_log`；`tests/test_proxy_log_no_query_secret.py` |
| 全站 `verify=False` 寫死處 | `repositories/fund/fx_and_main.py`（`get_latest_fx` 的 open.er-api 與 Frankfurter、`diagnose_fx_sources` 同兩源，共 4 處，**不論有無 proxy**）；`ui/sidebar.py`（測試 Proxy 連線按鈕）；`ui/tab5_data_guard.py`（測速按鈕）；`scripts/fetch_nav_cache.py`（有 proxy 時 `SESSION.verify = False`）；`scripts/probe_twse_eps.py`、`scripts/probe_moneydj_nav_equivalence.py`（同型）。單組 grep，基準 `9e714861` | `git grep -nE "verify\s*=\s*False"` 的命中 |
| 沒有的東西 | repo 內沒有 `ssl.`／`SSLContext`／`_create_unverified_context`／`CERT_NONE`／`check_hostname`／`REQUESTS_CA_BUNDLE`／自訂 CA bundle 的命中（字表限制見第 1 節） | 同上 |
| 套件版本 | `requirements.txt` 對 `requests` 只有下限（`>=2.31.0`）；`urllib3`、`certifi` 沒有列；Python 版本由 Streamlit Cloud 平台決定（檔內註解稱平台遷移到 3.14） | `requirements.txt` |

**INFERENCE**（函式庫行為，未在本沙箱驗證）：
- `requests` 的 `merge_environment_settings` 會把環境變數 `HTTP(S)_PROXY` 以 `setdefault` 併入 `proxies`；因此 `fetch_url` 降級直連傳 `proxies={}` 時，若執行環境有這些變數，**「直連」不一定是直連**。`infra/gspread_retry.py` 的註解對 `gspread` 描述了同一機制。部署端有沒有這些變數：NOT VERIFIED。
- `requests` 預設信任 `certifi`，標準庫 `urllib` 用系統 CA 儲存區，**兩條路徑的信任錨不同**。若日後要加自訂 CA，兩邊要各加。
- 開啟驗證後，驗證失敗在 `requests` 內是歸為 `SSLError` 還是被包成 `ProxyError`，與 `urllib3` 版本有關；若被包成 `ProxyError`，會觸發降級直連。施工前須在鎖定版本下以本機測試伺服器實測（第 9 節驗收條件）。
- Python 3.13 起標準庫預設驗證旗標較嚴格（背景知識，未在本沙箱驗證），可能影響走標準庫 `urllib` 的 TDCC 路徑對部分憑證的接受度。

### 2.2　證據 E1～E3：「Squid 相容」前提的線索

| 代號 | 內容 | 等級 |
|---|---|---|
| E1 | `docs/evidence/probe_moneydj_basic/` 的報告：`network_path` 欄明載為 GitHub runner IP 直連、`proxy_used_by_infra=False`；取數呼叫為 `declared_profile.fetch_url_with_retry`（直連時 `verify=True`）。報告中 `tcbbankfund.moneydj.com` 與 `www.moneydj.com` 兩個主機都得到 HTTP 回應（前者 404、後者 200），即 TLS 握手與憑證驗證在那一次通過。單一時間點（2026-10-14）、單一網路路徑 | FACT；「MoneyDJ 憑證本身可被 `certifi` 驗證」為 INFERENCE |
| E2 | 走標準庫 `urllib` 的來源（TDCC 與 `sources.py` 內約 16 個 `urlopen` 呼叫點）在程式碼裡**沒有關閉驗證**；若這些來源在部署端經 NAS 能正常取數，就表示該 Squid 的隧道與驗證相容。repo 內沒有「它們在 NAS 之後成功」的證據；Gate-D 卡也把 TDCC 的執行期行為標為未驗 | FACT（程式未關）；部署結果 NOT VERIFIED |
| E3 | `NAS_PROXY_GUIDE.md` Q3 記載過 `SSL: CERTIFICATE_VERIFY_FAILED`，歸因於「proxy 模式的 verify=False 未正確套用」；沒有記錄是哪個主機、哪個憑證、發行者是誰。`NAS_PROXY_FOR_AI.md` 與 `NAS_PROXY_GUIDE.md` 的 Squid 設定都只有 `http_port 3128`＋Basic 驗證＋CONNECT 允許，**沒有 `ssl_bump`、沒有 `https_port`** | FACT；失敗根因 NOT VERIFIED |

**INFERENCE**：若 NAS 依文件部署，Squid 只做隧道，原站憑證不會被替換，開啟驗證理應可行；當年遇到的驗證失敗較可能來自 (H1) 後來啟用過 `ssl_bump`／內部 CA，或 (H2) 特定主機的憑證鏈或 Python／函式庫版本的嚴格度，或 (H3) 單純為了方便而全面關閉。三者在 repo 內無法區分，第 8 節的 D2～D4 可以區分。

---

## 3　逐來源事實：MoneyDJ／FundClear／TDCC

| 項目 | MoneyDJ | FundClear | TDCC |
|---|---|---|---|
| **本題路徑（路徑 B／宣告值）取數函式** | `declared_profile::_fetch_moneydj_basic_fields_cached`：依代碼境內外選頁型，最多 4 個網址（`tcbbankfund.moneydj.com`、`www.moneydj.com` 各兩種頁型），逐一 `fetch_url_with_retry(url, timeout=20, retries=1)` | `declared_profile::_fetch_fundclear_declared_ccy_cached`：`fetch_url_with_retry` 打 `SmartFundAPI/api/FundAjax` 的基本資料端點（timeout 12、retries 2） | `declared_profile::_fetch_tdcc_listing_cached`：呼叫 `sources::_tdcc_get("3-2")` 取清單；手動接 `infra.source_backoff` |
| **舊 NAV 瀑布其他取數** | `sources.py` 內十餘個 `fetch_url_with_retry` 呼叫（`infra/proxy.py` 註解稱 17 個，本組未重數）與 `requests` 直呼（`verify=_ssl_verify()`）；另有多個 `urlopen` 呼叫點打 MoneyDJ 之外的來源 | `sources::_src_fundclear_nav/_meta/_div`（`fetch_url_with_retry`）；`sources::tdcc_search_fund_with_error` 內 FundClear 備援搜尋（`requests.post`，`verify=_ssl_verify()`）；`repositories/fundclear_offshore.py::_post_json`（`requests.Session`，自帶 proxy 與驗證邏輯，見下） | `sources::_tdcc_get`（3-1／3-2／3-4）、`_src_tdcc_meta`、`tdcc_search_fund*` |
| **HTTP client** | `requests`（`infra.proxy` 的 thread-local `Session`，掛 5xx `Retry`）；回應強制 Big5 解碼 | `requests`（同上；離岸 API 為另建 `Session`） | **標準庫 `urllib.request.urlopen`**（`Request` 帶 User-Agent／Accept／Referer，`timeout=8`，未傳 `context`） |
| **TLS：直連（無 proxy 設定）** | 驗證（`verify=True`） | 驗證（`fetch_url` 與 `_post_json` 皆 True） | 標準庫預設（驗證；INFERENCE：因未傳 `context` 且 repo 內無覆寫） |
| **TLS：proxy 模式** | **不驗證**（`fetch_url` 的 `verify=False`） | **不驗證**（`fetch_url`；`_post_json` 的 `verify=not bool(proxy)`；備援搜尋的 `_ssl_verify()`） | 標準庫預設（驗證），經全域 opener 的 `ProxyHandler` 走 NAS。**部署端是否成功：NOT VERIFIED** |
| **proxy 路徑** | `get_proxy_config` → 逐請求傳 `proxies=`（requests）；`http://user:pwd@host:3128`，Basic 驗證在 CONNECT 上 | 同左；離岸 API 自行讀 `get_proxy_config` 傳 `proxies=` | 全域 opener（`install_global_urllib_proxy`，模組載入時安裝一次）；`ProxyHandler` 同一 URL |
| **fallback 順序** | 同一頁型內 tcbbankfund → www；頁型境內外互換；`fetch_url` 內 proxy 失敗再直連一次；host 級冷卻（`infra.source_backoff`） | `fetch_url` 內 proxy → 直連；離岸 `_post_json`：`ProxyError` 時改直連（`_proxy=None`、`_verify=True`）；NAV 瀑布序為 FundClear → 鉅亨 → TCB MoneyDJ → SITCA（`fetch_fund_multi_source` 文件字串） | 路徑 B 無跨來源 fallback：三來源平行判定，`PARTIAL_FAILURE_POLICY="accept"`；`_tdcc_get` 失敗回 `[]` 並可交出例外原文；非清單回應被永久快取成 `[]`（既有已知限制） |
| **fallback 時 TLS 是否改變** | 會：proxy（不驗）→ 直連（驗）。**只有「由不驗變驗」的方向**，沒有由驗變不驗的路徑 | 同左 | 不適用（無 proxy 降級；失敗即失敗） |
| **憑證／token 的來源與傳遞** | 本路徑沒有原站金鑰；只有 `Referer`。唯一祕密是 NAS 代理帳密：`st.secrets`（`PROXY_URL` 或 `[proxy]`）→ URL userinfo → `Proxy-Authorization: Basic`，**經明文 HTTP 送到 NAS** | 同左；離岸 API 以 `Session` 先 GET 首頁取 cookie（非祕密） | 本路徑沒有原站金鑰；同一組代理帳密經全域 opener |
| **例外訊息與日誌** | `declared_profile` 把 `type(e).__name__: e` 與逐網址結果寫進 `attempts`／`error`，另 `print` 到 stdout；網址為公開頁面，含基金代碼，不含祕密。上畫面前由 `ui_v2/*/source.py` 以 `masking.mask_message` 遮蔽 | `declared_profile` 同左；`fundclear_offshore` 用 `FundclearError(f"... {_last_exc}")` 重拋原文；`sources` 內多處 `print(f"[src_fundclear] {code}: {e}")` | `_tdcc_get`：`print(f"[_tdcc_get] {ep} 失敗:{e}")`，並把 `f"{type(e).__name__}: {e}"` 交給呼叫端 |
| **遮罩函式與測試** | `services/v2_tables/masking.py::mask_message`＋`secret_values`（含 `PROXY_URL` 的帳號與密碼、`proxy` 區段的 `username`／`password`、各金鑰與編碼形態）；`tests/test_v2_tables_masking.py` 鎖住含 407 的實際 requests 例外 | 同左 | 同左 |
| **未被遮罩測試覆蓋（單組 grep）** | L1 的 `print`（不經 `mask_message`）、`fundclear_offshore` 重拋的訊息、`_tdcc_get` 的 `print`；側欄與資料守衛頁的 proxy 顯示遮罩（regex）找不到對應測試 | 同左 | 同左 |

**FACT 補充**：`ui_v2/exp/source.py::_load_funds` 與其他 `ui_v2/*/source.py` 都在「寫出點」遮蔽（`mask_message(message, _secret_values())`）；`masking.py` 自述「遮蔽只在寫出點做一次」。因此**stdout／Streamlit Cloud log 不在遮蔽範圍**，只靠各 L1 自己不印祕密。

---

## 4　其他與本題相關的程式事實

| 項目 | FACT | 出處 |
|---|---|---|
| 金鑰在網址參數 | FRED `api_key`、FinMind `token` 都放在 `params`，經 `fetch_url` 發送；proxy 模式下這些請求的 TLS 未驗證。Alpha Vantage 的 `apikey` 直接拼在網址字串，走 `urlopen`（驗證） | `repositories/macro/fred.py::fetch_fred`、`repositories/hot_money_repository.py`、`repositories/fund/sources.py::_src_alphavantage_nav` |
| UI 顯示 NAS 位址 | 舊側欄在有 proxy 設定時顯示「🔒 {`@` 之後的字串}」＝NAS 的 host:port；資料守衛頁與設定診斷顯示「密碼遮蔽後的 proxy URL」 | `ui/sidebar.py`、`ui/tab5_data_guard.py`、`ui/helpers/settings_diag/fetch_diag_section.py` |
| 新 UI 的設計意圖 | `ui_v3` 的 NAS 診斷頁設計與測試明載「不顯示 proxy 主機、帳密、完整網址、標頭、例外文字」；且禁用「關閉驗證」「verify=False」字樣 | `ui_v3/pages/nas_diag.py`、`tests/ui_v3/test_ui_v3_nas_diag_viewmodel.py` |
| CI 使用代理帳密 | 至少 7 個 workflow 以 `env: PROXY_URL: ${{ secrets.PROXY_URL }}` 傳入（另 1 個只在註解提及）；`twse_eps_probe.yml` 檔頭已自述「能推按鈕分支、能改 workflow 的人可讀取該 secret」的風險 | `.github/workflows/*.yml` |
| 文件化 NAS 設定 | `http_port 3128`＋`basic_ncsa_auth`＋`http_access allow CONNECT authenticated`＋`http_access allow authenticated`；**沒有** `Safe_ports`／`SSL_ports`／目的地限制（如禁止 localhost、私有網段）的規則；要求「路由器開通 Port 3128 TCP 對外轉發」 | `NAS_PROXY_GUIDE.md`、`NAS_PROXY_FOR_AI.md` |
| 設定範本 | `secrets.toml.example` 為 `[proxy]` 區段（`username`／`password`／`endpoint`）；`.streamlit/secrets.toml` 在 `.gitignore`；repo 內沒有真實值（僅範本佔位） | `secrets.toml.example`、`.gitignore` |

**FACT（本機驗證，假值）**：對形如「帳號:含 `@` 的密碼@主機:埠」的 URL，(a) 側欄用的 `@(.+)` 取到的是「密碼 `@` 之後的尾段＋`@主機:埠`」；(b) 資料守衛頁與設定診斷用的 `//[^:]+:[^@]+@` 取代後，輸出為 `//****:****@尾段@主機:埠`。兩者都把密碼尾段原樣顯示。`urllib3` 對 userinfo 以最後一個 `@` 切分，所以含 `@` 的密碼在實際連線上可以成立。是否有人真的使用含 `@` 的密碼：NOT VERIFIED。

---

## 5　風險矩陣

嚴重度＝若條件成立的衝擊；「程式事實」欄是本 repo 內可驗證的部分，「部署事實」欄是成立條件（本沙箱無法驗，一律 NOT VERIFIED）。

| ID | 面向 | 風險 | 程式事實（FACT） | 部署事實（NOT VERIFIED） | 嚴重度 |
|---|---|---|---|---|---|
| R1 | 中間人 | proxy 模式下 `fetch_url` 與離岸 API 不驗證原站憑證；路徑上（app 到 NAS 的公網段、NAS 本身、NAS 到原站）任何能終止 TLS 的人，都可替換 NAV、匯率、總經序列，且程式不會報錯；FRED／FinMind 金鑰在同一條未驗證通道上 | 第 2.1、4 節 | 取決於 NAS 位置、是否 `ssl_bump`、app 到 NAS 的路徑可否被觀察或劫持（DDNS 名稱被劫持也算） | **高**（衝擊：資料真實性＋金鑰；可能性未知） |
| R2 | 中間人 | 代理腿為明文 HTTP；即使原站 TLS 完整驗證，代理帳密（Basic）仍可被路徑上的觀察者取得；驗證只保護資料真實性，不保護代理帳密 | `get_proxy_config` 的 scheme 為 `http`；文件化設定無 `https_port` | 路由器是否對全網開放 3128；是否有來源限制 | **高**（若 3128 對外開放） |
| R3 | 代理憑證洩漏 | (a) 側欄顯示 NAS host:port；(b) 側欄與資料守衛頁／設定診斷的遮罩 regex 對含 `@` 密碼漏尾段；(c) 同一組帳密同時存在 Streamlit secrets、7 個以上 workflow 的環境變數（影響面大、輪替成本高）；(d) `masking.py` 刻意不遮 `proxy.endpoint`，且沒有涵蓋 Basic 驗證標頭的 Base64 形態（INFERENCE：僅在標頭被印出時才有影響，本組未找到印標頭的程式） | 第 3、4 節；regex 缺陷以假值本機驗證 | app 的檢視者是誰（側欄是否對外可見）；密碼是否含 `@`；secret 是否同一組 | **中**（(b) 條件成立時為中；(a) 取決於 app 是否公開） |
| R4 | 代理濫用／橫向 | 文件化的 Squid 設定允許通過驗證者對**任意目的地與任意埠**做 CONNECT／代理，沒有私有網段與埠限制；若代理帳密外洩，攻擊者可用 NAS 當跳板，甚至探測 NAS 所在內網 | 文件化設定（非部署設定） | 實際 `squid.conf` 是否含 `Safe_ports`、`SSL_ports`、私有網段 deny | **中至高**（取決於 R2／R3 與實際設定） |
| R5 | 錯誤訊息洩漏 | `fetch_url` 的三處例外輸出已去查詢字串且有測試；但其他 L1 例外直接 `print(f"...{e}")`（stdout，進 Streamlit Cloud log）。`requests` 例外一般含目標網址（含 query）；本路徑三個來源網址不含金鑰，風險主要在 FRED／FinMind 類呼叫若繞過 `fetch_url`。側欄對 `requests` 例外 `str(e)[:120]` 直接顯示到畫面（含 `ProxyError` 文字，是否含 proxy 主機：NOT VERIFIED） | 第 3 節；`ui/sidebar.py` | log 的檢視者範圍（程式註解稱 collaborator 可見） | **低至中** |
| R6 | fallback 降級 | **方向性好**：程式內沒有任何「由驗證改為不驗證」的路徑；proxy 失敗只會改為直連＋驗證。殘餘風險：(a) 路徑上攻擊者可誘發 `ProxyError`／逾時，迫使流量走直連，MoneyDJ 因境外 IP 被擋而變成**缺資料**（可用性，非完整性）；(b) 直連受環境變數 `HTTP(S)_PROXY` 影響（INFERENCE）；(c) 全域 urllib opener 為一次性負向快取，secrets 較晚可用時，標準庫路徑會長期停在直連，造成同一程序內各來源路由不一致；(d) 開啟驗證後 `SSLError` 與 `ProxyError` 的歸類不確定（INFERENCE），可能產生非預期降級 | 第 2.1 節 | 部署端環境變數；平台 Python／套件版本 | **低至中** |
| R7 | 寫死的不驗證 | 匯率備援（open.er-api、Frankfurter）與兩個診斷按鈕在**直連模式也不驗證**，與 proxy 是否存在無關；匯率首選為經 `fetch_url` 的 Yahoo，備援被中間人改寫時才影響換算 | `fx_and_main.py` | — | **中** |
| R8 | 可觀測性 | 全域關閉 `InsecureRequestWarning`；日誌沒有「這次請求有無驗證」欄位；診斷頁（舊）只測連通性，不區分 TLS 失敗；新 UI 診斷頁設計有 `tls` 分類但目前只是 FAKE 預覽 | 第 2.1 節；`ui_v3/viewmodels/nas_diag.py` | — | **低** |
| R9 | 供應鏈／環境漂移 | `requests` 只有下限、`urllib3`／`certifi` 未固定、Python 由平台決定；TLS 行為（嚴格度、信任錨、例外歸類）可能隨一次重新部署改變 | `requirements.txt` | 實際解析出的版本 | **低至中** |

**區分提醒**：R1、R2、R4 的「成立條件」都在部署端，**程式碼只決定「如果條件成立，後果是否被放大」**（目前被放大：驗證關閉，攻擊者不需要受信任的憑證）。

---

## 6　保留 TLS 驗證的可行方案

**前提**：所有方案都以「保留 TLS 驗證」為不可退讓前提；「停用驗證」只列為現況與被排除方案（第 7 節）。以下各方案的成立條件分支，取決於第 8 節 D2～D4 的結果：

- **分支 P（plain CONNECT）**：Squid 只做隧道，原站憑證原樣到達 app。
- **分支 T（TLS 終結／攔截）**：Squid 啟用 `ssl_bump` 或有人／程序替換憑證，app 看到的是 NAS 簽的憑證。
- **分支 U（未知）**：證據不足以區分。此時不應施工。

| 方案 | 做法 | 優點 | 缺點 | 相容性風險 | 需要的部署證據 | 可逆性 |
|---|---|---|---|---|---|---|
| **A　以主機為單位逐步開驗證（預設信任鏈）** | 在 `infra.proxy` 加一份「proxy 模式下需驗證的主機」清單（預設空＝現況），逐步加入；驗證用既有 `certifi`，不新增信任錨。**分支 P 才適用** | 變動最小；單一函式與一份清單；逐主機上線、逐主機回滾；先保護帶金鑰的主機 | 契約測試要有意識地改；驗證失敗時資料缺口會變成可見的錯誤（這是優點也是營運成本）；需決定 `SSLError` 的分類（目前會被歸為 `unreachable`） | 分支 P：低（E1 顯示 MoneyDJ 兩主機可被 `certifi` 驗證）。分支 T：必失敗。`SSLError`／`ProxyError` 歸類與版本有關（INFERENCE） | D1～D4（分支判定）、D6（版本）、D8（各原站憑證鏈） | 高：清單改回空即回到現況；無資料遷移 |
| **B　自訂信任錨（NAS 內部 CA bundle）** | 分支 T 專用：把 NAS 使用的內部 CA **公開憑證**（不含私鑰）放入 repo 或 secrets 檔，requests 以 `verify=<bundle 路徑>`、urllib 以對應 `ssl` context 載入；仍驗證，只是信任 NAS 的 CA | 在 `ssl_bump` 已存在的現實下仍能「驗證」；可擋住 NAS 以外的攻擊者 | **驗證只證明「這是 NAS 簽的」，不證明「這是原站」**；NAS 能讀寫全部明文；CA 私鑰成為高價值目標；兩條信任路徑（`certifi`／系統）要各配一份；憑證輪替要流程 | 中：要同時改 requests 與 urllib 兩條路；bundle 管理增加複雜度 | D2、D3、D4（證實有 bump 與 CA 發行者）、CA 私鑰保管說明 | 中：撤回 bundle 即回到現況，但 NAS 若已依賴 bump，回滾前要先處理 NAS 端 |
| **C　憑證釘選（指紋或公鑰釘選）** | 對少數主機（MoneyDJ 兩主機、FundClear、TDCC）在 `HTTPAdapter` 設 `assert_fingerprint` 或比對公鑰雜湊 | 即使信任鏈被濫用也能擋；分支 P／T 皆可用（T 時釘 NAS 的 CA 或葉憑證） | 原站換憑證就全斷；維運負擔最高（需監看到期與輪替）；釘錯等於自造停機 | 高：政府與商用站台換憑證不一定預告 | D8（各站憑證輪替歷史與到期）、輪替監看責任人 | 中：移除釘選即回到方案 A 的狀態 |
| **D　代理腿加密／縮小暴露（與驗證互補，不取代）** | 讓 app 到 NAS 這一段受保護：Squid `https_port` 搭配 NAS 上由公開 CA 簽發的受信憑證（DSM 憑證管理），或改用受限網路（VPN／來源 IP 限制）；同時補上 `Safe_ports`／`SSL_ports`／私有網段 deny | 解 R2、R4；若 NAS 持有受信憑證，app 端可**驗證 NAS 身分**，使「DDNS 被劫持／路徑上冒充 NAS」失效 | 本身不解決「NAS 以內與以後」的原站驗證，需搭配 A；標準庫 `urllib` 的 `ProxyHandler` 對 `https://` 代理的支援不完整（INFERENCE，須實測），TDCC 路徑可能要改寫；Streamlit Cloud 無法自行裝 VPN 客戶端（INFERENCE，平台文件未查） | 中至高：requests 較有彈性，urllib 路徑受限 | D1、D2、D5、D9（受信憑證可得性） | 高（NAS 端設定可回復），但要有 NAS 變更紀錄 |
| **E　每來源獨立策略（含部分直連）** | 依來源實測結果分流：可直連且未被擋的來源（可能是 TDCC 開放 API；FundClear 待測）走直連並驗證，只有被境外 IP 擋的（MoneyDJ）走 NAS | 縮小經 NAS 的流量與暴露；直連路徑的 TLS 本來就是端到端驗證 | 需要實測 Streamlit Cloud 出口 IP 對各站的直連可達性（現有探測報告量的是 GitHub runner，不是 Streamlit Cloud）；路由規則增加維護；MoneyDJ 仍需 A／B | 中：取決於各站對境外 IP 的政策變動 | D7（出口 IP 直連可達性）、D8 | 高 |
| **F　NAS 端受信憑證的固定上游中繼（TLS 終結但受控）** | 條件：NAS 持有公開 CA 簽的憑證。在 NAS 上以反向代理只轉發白名單上游（MoneyDJ、FundClear、TDCC），NAS 對上游做完整驗證，app 對 NAS 做完整驗證 | 白名單縮小濫用面；不依賴 Squid 的 CONNECT 任意目的地；app 端可驗證到一個固定身分 | 新元件、新維運面；請求要改寫成對 NAS 的路徑（`docs/v2/49` 已記載代理改寫網址的雙向風險）；信任鏈變成「信任 NAS」；觸及「新增／替換資料來源路徑」，屬 Decision Gate | 高：URL 改寫、cookie、編碼、`final_url` 檢查都要重驗 | D1、D5、D9；BL-0550 明示不得要求對外開放 NAS 管理介面 | 中：切換回 Squid 路徑即可，但需保留兩套 |

**條件分支一覽**

| 若 NAS … | 優先方案 | 說明 |
|---|---|---|
| 是 plain CONNECT（分支 P） | A，並行 D | 先用 A 保護帶金鑰主機；D 處理明文代理腿與濫用面 |
| 是 TLS 終結／攔截，且持有**可被信任**的憑證（可由公開 CA 驗證） | D＋F 的方向；A 對 NAS 憑證可用 | NAS 憑證可驗證，但原站驗證由 NAS 負責，信任模型要由客戶明示接受 |
| 是 TLS 終結／攔截，憑證為**內部 CA** | B（次選 C） | 必須明示「驗證的是 NAS，不是原站」，並要求 NAS 對上游完整驗證 |
| 證據不足 | 不施工 | 先完成第 8 節 |

---

## 7　被排除的方案與理由

| 方案 | 狀態 | 理由 |
|---|---|---|
| **維持現況：proxy 模式一律 `verify=False`，並把它當作正式接線的預設** | **排除**（客戶限縮授權明示不接受） | 其相容性前提未驗證；放大 R1；FRED／FinMind 金鑰在同一通道；`disable_warnings` 使它無聲；與 CLAUDE.md §1「錯誤的數字比沒有數字更危險」衝突 |
| **用 `REQUESTS_CA_BUNDLE`／`SSL_CERT_FILE` 全域指向某個 bundle 但保留 `verify=False`** | 排除 | 顯式 `verify=False` 優先，bundle 不會生效，形同沒做 |
| **驗證失敗時自動重試 `verify=False`（「先驗證、失敗就不驗」）** | 排除 | 這是降級攻擊的標準形狀：攻擊者只要讓驗證失敗就能回到不驗證。任何方案的驗收都必須證明不存在這條路 |
| **把 `ssl_bump` 打開再信任 NAS 的 CA 當成「更安全」** | 不單獨採用 | 等於讓 NAS 成為能讀寫全部流量的中間人；只有在客戶明示接受該信任模型、且 NAS 對上游完整驗證時才是方案 B 的條件式版本 |

---

## 8　必要部署證據清單（需客戶／持有人收集；本文作者不能收集）

說明：下列皆為**持有人在自己的環境手動執行的唯讀動作**，不經本 repo 的程式；BL-0550 要求「app 內的真實探測須先有明確目標、timeout、頻率、授權」，故**不建議**為了收集而在 app 內新增探測。請勿把帳密貼進任何對話、issue、PR 或 log；範例中的帳密一律以互動輸入或環境變數傳入。

| ID | 要回答的問題 | 唯讀收集方式 | 判讀 |
|---|---|---|---|
| D1 | NAS 上 Squid 的版本與編譯選項 | 在 NAS 上執行 `squid -v`，只貼版本字串與編譯選項清單 | 有無 SSL 相關編譯選項（`--with-openssl`、`--enable-ssl-crtd`）決定能否 bump |
| D2 | 設定是否有 TLS 攔截／改寫／目的地限制 | 檢視生效中的 `squid.conf`（去除註解與空行後），**只回報有無**下列指令及其摘要：`ssl_bump`、`http_port … ssl-bump`、`https_port`、`sslcrtd_program`、`url_rewrite_program`、`Safe_ports`、`SSL_ports`、私有網段與 `to_localhost` 的 deny、`auth_param` 的型態。**不要貼密碼檔路徑以外的敏感值** | 區分分支 P／T；也回答 R4 |
| D3 | 實際流量是隧道還是被 bump | 抽樣 `access.log` 中對 MoneyDJ／FundClear／TDCC 的條目（去識別來源 IP 與帳號）。隧道通常記為 CONNECT 與 `TCP_TUNNEL` 類結果、看不到 HTTPS 的完整路徑；若能看到 HTTPS 目標的完整路徑與回應碼，代表有 bump | 區分分支 P／T |
| D4 | 經 NAS 看到的原站憑證與直連看到的是否相同 | 在另一台機器上，對同一主機各執行一次 `openssl s_client -connect <主機>:443 -servername <主機> -showcerts`：一次直連、一次加上 `-proxy <NAS>:3128` 與代理帳密（帳密請用 `-proxy_pass env:變數` 或 `stdin` 形式，避免寫進 shell 歷史）。比較葉憑證的 issuer、序號、指紋與鏈長。主機：`www.moneydj.com`、`tcbbankfund.moneydj.com`、`www.fundclear.com.tw`、`openapi.tdcc.com.tw`，以及 `fred.stlouisfed.org`、`api.finmindtrade.com` 類帶金鑰的來源 | issuer／指紋一致＝隧道；不一致＝被替換，並可讀出內部 CA 名稱（B 方案所需） |
| D5 | 3128 是否對公網開放、有無來源限制、有無被掃描 | 檢視路由器的連接埠轉發與防火牆規則（截圖並遮蔽內網位址以外的敏感資訊）；統計 `access.log` 近 30 天 407／`TCP_DENIED` 的來源分布（只回報數量與是否有非預期來源） | 回答 R2／R4 的成立條件 |
| D6 | Streamlit Cloud 實際執行環境 | 平台 Manage app 的 build／runtime log：Python、`requests`、`urllib3`、`certifi`、`streamlit` 版本；secrets **只回報形態**（`PROXY_URL` 或 `[proxy]`、scheme 是 `http` 還是 `https`），不回報值；是否有 `HTTP(S)_PROXY`／`REQUESTS_CA_BUNDLE`／`SSL_CERT_FILE` 之類環境變數（只回報有／無；平台沒有 shell，若無法取得則列為 NOT VERIFIED，不為此改碼） | 回答 R6／R9 與 INFERENCE 的函式庫行為 |
| D7 | Streamlit Cloud 出口 IP 直連各站是否可達 | 現有探測量的是 GitHub runner（見 E1 的 `network_path`），不是 Streamlit Cloud。需持有人授權一次性、單次、低頻的唯讀 GET，並先寫明目標、timeout、頻率（BL-0550 的條件）。若不授權，方案 E 無法評估 | 回答方案 E |
| D8 | 三個原站的憑證鏈現況與到期 | 同 D4 的直連輸出，加 `openssl verify`（以系統 CA 與 `certifi` 各驗一次）；記錄 issuer、到期日、是否缺中繼憑證 | 判斷開啟驗證的相容性與釘選可行性 |
| D9 | NAS 能否取得公開 CA 簽發的受信憑證 | DSM 的憑證管理頁（Let's Encrypt／自有網域）是否已有涵蓋 DDNS 名稱的憑證與自動續期狀態 | 方案 D、F 的前提 |
| D10 | NAS 管理介面與系統更新 | 確認 DSM 管理介面未對公網開放；DSM 與 Squid 套件的更新狀態 | BL-0550 明示不得要求對外開放管理介面 |
| D11 | 代理帳密的使用範圍與輪替 | 列出該帳密被用在哪些地方（Streamlit secrets、各 workflow、個人機器），上次輪替日，密碼是否含 `@` 等特殊字元 | 回答 R3；輪替是 D 方案的前置動作 |

---

## 9　最小施工 Gate 建議（僅建議，不是授權）

**RECOMMENDATION**

**G0　證據關卡（不改碼）**：完成 D1～D5（必要）與 D6、D8、D11（建議）。輸出一頁結論：分支 P／T／U，與 R2／R4 是否成立。分支 U 則停在這裡。

**G1　客戶裁示（Decision Gate）**：依 CLAUDE.md §-1.5 的 v1.0 Stop／Decision Gate，凡涉及「新增或替換 production 資料來源路徑」「data identity」「正式 threshold」以外的 **TLS 信任模型**（尤其方案 B、F 的「信任 NAS」）都應由客戶明示。分支 P 且只做方案 A，屬資料來源路徑不變、只收緊驗證，但仍建議客戶知悉並同意，因為它會使部分原本「靜默成功」的取數變成可見的失敗。

**G2　第一個可施工單元（僅分支 P；最小且可逆）**

- **內容**：在 `infra/proxy.py` 新增「proxy 模式下需驗證的主機」單一清單，**預設為空**（行為與現況完全相同）；`fetch_url` 的 `verify` 改為「該主機在清單內則 True，否則沿用現況」。第一批只放**帶金鑰在網址參數且憑證鏈單純**的主機（FRED、FinMind），其次 Yahoo；**MoneyDJ、FundClear 不在第一批**。
- **不做**：不改 `fx_and_main`、`ui/sidebar`、`ui/tab5_data_guard`、`scripts/*` 的寫死 `verify=False`（另案）；不動 TDCC／urllib 路徑；不改 NAS、不改 secrets；不新增探測；不改 `_ssl_verify()` 的語意（它被 30+ 呼叫點間接繼承，另案評估）。
- **前提**：G0 結論為分支 P；客戶同意；專用分支與 PR；獨立稽核（資安級，兩組）。
- **驗收條件**
  1. **正控**：對本機啟動的測試用 TLS 伺服器（測試時動態產生的自簽憑證與其 CA，**本機私有位址，不連外**），在清單內且 CA 受信時請求成功。
  2. **負控（必做）**：同一伺服器、憑證不受信時，`fetch_url` **必須失敗回 `None`、記下可辨識的失敗分類或訊息，且不得以 `verify=False` 重試、不得靜默改走另一條路徑後回報成功**；斷言同一請求過程中沒有任何 `verify=False` 的呼叫發生。負控使用測試時產生的隨機識別值，**不寫進文件或程式碼的固定字串**（CLAUDE.md §-2.A 第 8 款）。
  3. **`SSLError`／`ProxyError` 歸類**：在 `requirements.txt` 實際解析出的版本下，確認驗證失敗不會被歸為 `ProxyError` 而觸發降級直連；若會，需有明確處置並測試。
  4. **預設不變**：清單為空時，既有契約測試（`test_ssl_verify_false_when_proxy_enabled` 與 `fetch_url` 行為矩陣）一律不變；清單非空的新行為另有測試。
  5. **日誌**：驗證失敗的訊息不含代理帳密、金鑰、完整網址查詢字串（沿用 `_exc_log` 並新增斷言）。
  6. **可觀測**：至少新增一行不含祕密的日誌，標示「此主機本次請求驗證開／關」，使 R8 的盲點縮小。
  7. **不退化**：全套既有測試與 CI 綠；本單元不改任何資料語意、公式、門檻。
- **回滾**：清單改回空（或 revert 該 PR）；無資料遷移、無快取格式變更。若上線後某主機因驗證失敗造成缺資料，僅從清單移除該主機。
- **後續單元（各自另案）**：D 方案（加密代理腿與目的地限制，屬 NAS 端變更，由持有人執行）；遮罩 regex 缺陷修正；FX 備援與診斷按鈕的 `verify=False`；MoneyDJ／FundClear 納入清單；新增獨立失敗分類（例如 TLS 驗證失敗）需動 `shared/backoff_policy.py` 這個 SSOT，屬另一個決策。

---

## 10　我沒有查證的部分

- **所有部署事實**：NAS 上 Squid 的實際設定與版本、是否 `ssl_bump`、3128 是否對公網開放、路由器規則、DDNS、帳密強度與輪替、Streamlit Cloud 的實際 Python／套件版本與環境變數、側欄的檢視者範圍。
- **TDCC 與各 `urlopen` 來源在 NAS 之後是否真的成功取數**（E2 的「若成功」前提）。
- **函式庫行為**（第 2.1 節的 INFERENCE）：`requests` 對環境代理的合併、`SSLError`／`ProxyError` 歸類、Python 3.13 之後預設驗證旗標、`urllib` 對 `https://` 代理的支援。
- **E1 只代表一個時間點、一條網路路徑**；不代表 Streamlit Cloud 或 NAS 路徑上的行為。
- **只掃了 repo 內的檔案與一組字表**：第三方 SDK（`yfinance`、`gspread`、`google-auth`）內部請求、動態組出的呼叫、別名包裝、`ui_v2`／`ui_v3` 之外未列出的呼叫點可能漏看；`scripts/` 與 `.github/workflows/` 只讀了與代理相關的部分。
- **L1 各處 `print(f"...{e}")` 是否真的會含祕密**：沒有逐一審；`requests`／`urllib` 例外文字是否含 proxy 主機或帳密：NOT VERIFIED。
- **Base64 `Proxy-Authorization` 形態是否會出現在任何訊息**：沒找到印標頭的程式，但沒有窮舉。
- **側欄對含 `@` 密碼的遮罩缺陷**只用假值在本機驗證 regex；沒有執行 Streamlit 畫面，也不知道實際密碼是否含 `@`。
- **文件化 NAS 設定與實際設定的差距**：本文把文件當作「設計意圖」，不是部署事實。
- **BL-0550／0551／0555 的內容**以 `docs/BACKLOG.md` 在 `9e714861` 的文字為準；PR 與 GitHub 上的最新狀態未重查。
- **未跑**專案測試套件（只在本分支新增這一份文件並跑指定的文件守衛）。
- **本文是單組作者產出**，所有分類、嚴重度、方案優缺點都是作者判斷，尚待兩組獨立稽核（資安級）。

---

## 11　不構成授權聲明

本文是唯讀、離線的評估與建議。**不授權**：修改任何 `verify`／proxy 設定／secrets／NAS 防火牆／連線策略／程式碼；不授權任何 live 網路探測或對 MoneyDJ、FundClear、TDCC、NAS 的連線；不授權新增或替換 production 資料來源；不授權讀取或索取真實 secrets。登記與評估不等於動工許可（CLAUDE.md §-1）。第 9 節的 Gate 是供客戶裁示用的草案，**未經客戶裁示前不得施工**。本文所稱「客戶限縮授權」係經對話提示語轉達，待核。
