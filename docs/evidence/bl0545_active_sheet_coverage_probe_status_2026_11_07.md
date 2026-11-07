# BL-0545｜五維健康評級資料覆蓋：Active Sheet 探針現況與可重現協定（2026-11-07）

> **Active Sheet 真實覆蓋率：NOT VERIFIED（原因：無合法使用者憑證／持倉清單）**
>
> 本文件**不含**任何覆蓋率百分比、命中檔數或「X 檔中有 Y 檔」之類的數字當作事實；
> 凡是需要使用者持倉才能得出的數字，一律標 NOT VERIFIED。

- **性質**：唯讀調查現況（重驗 #1157 靜態稽核的承重事實＋盤點合法取得路徑＋可重現探針協定）。**不是**持倉實測報告、**不是**新公式／門檻／准入規則、**不是**新產品規格、**不是**任何 UI 動工授權。
- **基準 main SHA**：`b0ca4b949e969165570c693a24e9f23f51952ac1`（2026-11-07 `git fetch` 後確認）。
- **對照的既有稽核**：`docs/evidence/health_4d_coverage_static_audit_2026_11_06.md`（稽核 SHA `861628cc`，單組）。本文件不修改它。
- **依據**：`DEC-2026-11-06-02`（保留原 Grade，另外顯示覆蓋率與正式准入）、`docs/BACKLOG.md` 的 BL-0545、`docs/v2/82` 第 10 節。
- **獨立性**：本批為單組唯讀調查，**未經第二組獨立複驗**（`CLAUDE.md` §-2 規則 6）。下列「成立」判定是本組讀碼加既有測試的結果，不是第二雙眼睛的結論。
- **未改動**：任何 `.py`、Grade 公式、權重、門檻、UI、OAuth、Risk Cap、資料來源、`docs/HANDOFF.md`、`docs/BACKLOG.md`、`docs/DECISIONS.md`、#1157 的檔案。

## 1. NOT RUN／NOT VERIFIED 清單（先看這個）

| # | 項目 | 狀態 | 原因 |
|---|---|---|---|
| 1 | Active Sheet 全體唯一基金數與身份去重結果 | **NOT VERIFIED** | 本環境無使用者 Google 登入 session，也無使用者提供的持倉代號清單；不得用服務帳戶、`POLICY_SHEET_ID` 或沙箱基礎設施身分代讀 |
| 2 | 成功取得資料的基金數 | **NOT VERIFIED** | 同上（沒有輸入清單，就沒有分母） |
| 3 | 五維各自 `applicable_n`／`scored_n`／缺值原因分佈 | **NOT VERIFIED** | 同上 |
| 4 | `scripts/audit_6d_coverage.py` 實跑 | **NOT RUN** | 沒有輸入代號；且該腳本抓取 MoneyDJ 需經外部網路，本批無持倉清單可抓，未以任意代號充數 |
| 5 | 公開基金樣本探針 | **NOT RUN** | 非必做；為避免任何人把公開樣本誤讀成使用者持倉覆蓋率，本批不做 |
| 6 | 全套 pytest／pre-commit 完整跑 | **NOT RUN** | 本批只跑下方第 6 節列出的子集；`pre-commit` 本環境未安裝（以其判定邏輯人工複核檔尾換行與行尾空白，見第 6 節） |
| 7 | 在「依賴齊全」環境下 streamlit 相關測試 | **NOT RUN** | 本環境沒有 `streamlit`；四個依賴它的測試未能收集（第 6 節），其結論只能由 CI 驗 |
| 8 | 「第二組獨立複驗」 | **NOT VERIFIED** | 單組作業 |
| 9 | production 路徑的去重鍵實際行為（`fund_keys.resolve_full_keys` 對真實 Sheet 值） | **NOT VERIFIED** | 只讀了函式說明與既有測試，沒有以真實 Sheet 值驅動 |

## 2. #1157 稽核承重事實在目前 main 的重驗

判定標籤：**成立**＝目前 main 的原始碼與該稽核敘述一致；**已變**＝敘述與目前 main 不一致；**無法確認**＝本批無法以讀碼確認。

| # | #1157 的承重事實 | 位置（檔案＋符號） | 判定 | 說明 |
|---|---|---|---|---|
| F1 | `compute_4d_health` 名為 4D、實為五維（coverage／sharpe／trend／volatility／fx_risk） | `services/health/grade.py::compute_4d_health` | **成立** | 內部 `_dims` 字典五鍵；`n_total` 為字典長度 |
| F2 | 最低維度規則：`GRADE_4D_MIN_FACTORS` 且須有 coverage 或 Sharpe 至少一個核心維度才輸出字母等第 | `services/health/grade.py::compute_4d_health`；常數 `shared/signal_thresholds.py::GRADE_4D_MIN_FACTORS` | **成立** | 條件為「已算出維度數不少於該常數」且「coverage 或 sharpe 至少一個非 None」。本文件**不引述該常數的數值**，不重述門檻 |
| F3 | 2/5 的字母不可被說成 5/5 | 同上；回傳值內 `coverage` 子字典含 `n_scored`／`n_applicable`／`n_total`／`missing`／`ratio` | **已變（方向為補強）** | #1157 當時寫「原始覆蓋 … 必須外露」；目前 main 已有揭露欄位：`services/health/report.py::_grade_coverage_label`（「評分覆蓋」欄）、`services/health/action.py` 的覆蓋旗標、`ui/tab2_single_fund.py` 的覆蓋顯示。**但**這些揭露只涵蓋 scored／missing／N/A 三態，見 F9 |
| F4 | 批次報表路徑 `ma_dir=None`，trend 維只能靠 1Y 報酬回退 | `services/health/report.py::build_health_analysis_row` | **成立** | 呼叫 `compute_4d_health` 時 `ma_dir=None` |
| F4b | （#1157 未提）其他 `compute_4d_health` caller 同樣不傳 MA 方向 | `services/health/replacement.py`（替換判定內部呼叫）、`ui/tab2_single_fund.py`（個基卡） | **新增發現（成立）** | 兩處呼叫亦為 `ma_dir=None`。依目前讀碼，production 內**沒有任何 caller 傳入實際 MA 方向**；`_score_trend` 的 `up`／`down` 分支在 production 路徑上是否曾被觸發：**NOT VERIFIED**（只確認了這三個 production 呼叫點的引數，未做全 repo 動態追蹤） |
| F5 | FX 歷史波動提供器只支援 USD | `services/fx_regime_service.py::SUPPORTED_FX`；`fx_regime_by_ccy` | **成立（附註）** | 常數內容為單一 USD。附註：`SUPPORTED_FX` 在 production 程式碼中**只有定義、沒有被 `fx_regime_by_ccy` 引用來做把關**；實際限制來自該函式內寫死只填 `_CACHE["USD"]`。兩者目前一致，但**常數本身不是守門條件**（若日後只擴充常數而不改函式，不會生效） |
| F6 | 非 USD 外幣的 fx_risk 走 missing；TWD 為 N/A 不進分母 | `services/health/grade.py::score_fx_risk` | **成立** | 台幣計價回 `(None, "n/a")`，`n_applicable` 扣 1；外幣取不到 CV 回 `(None, "missing")` |
| F7 | 稽核腳本 `_probe_fx_risk` 用**即期**匯率判斷「可算」 | `scripts/audit_6d_coverage.py::_probe_fx_risk` | **成立** | 呼叫 `services.fund_service.get_latest_fx`（`{幣別}TWD=X`）；與健康評分的 `fx_regime_by_ccy`（歷史 std／mean）**不是同一個依據** |
| F8 | 稽核腳本的分母為「抓取成功數」，並以此計算百分比 | `scripts/audit_6d_coverage.py::main` | **成立** | 分母為輸入代號數扣抓取失敗數；抓取失敗數另印出但「未計入分母」。該腳本的評估維度是費用率、基金規模、匯率風險三項「6D 候選」，**不是**目前五維的 coverage／sharpe／trend／volatility／fx_risk |
| F9 | 五個互斥狀態（not_applicable／unsupported／missing／stale／conflict）是**本次稽核標籤**，不是現行程式的輸出 | `services/health/grade.py`、`services/health/report.py` | **成立** | 兩檔內沒有任何 stale／conflict／unsupported 的產出或欄位；現行程式只區分 scored、missing、n/a（僅 fx_risk）。**含意**：stale、conflict、unsupported 三個狀態在現行 production 中會被歸入 missing 或根本不被偵測 |
| F10 | 其他 `services/health/` 入口是否另有覆蓋率計算 | `services/health/` 全部檔案 | **成立（無新增）** | 含 `n_scored`／`n_applicable` 的 production 檔案只有 `grade.py`（產生）、`report.py`（顯示標籤）、`action.py`（旗標）以及 `ui/tab2_single_fund.py`（顯示）。沒有另一套獨立的覆蓋率分母計算。此為單組 grep 結論，屬「有沒有漏看」型全稱句，**未經第二組驗證** |
| F11 | 1Y 含息報酬須達最小歷史窗口，否則 coverage 維不可算 | `services/fund_total_return.py`；常數 `shared/signal_thresholds.py::RET_1Y_RESTORED_MIN_WINDOW_DAYS` | **無法確認（未逐行重驗）** | 本批只確認該常數存在且被 `services/fund_service.py` 引用；#1157 描述的「配息型且窗口無配息紀錄不得硬算」分支，本批未逐行重驗 |
| F12 | 重複計算風險：`n_applicable` 僅在 fx_risk 為 N/A 時扣減 | `services/health/grade.py::compute_4d_health` | **成立（新增細節）** | 其餘四維在任何情況下都算進適用分母；也就是「不適用」目前只有 fx_risk 一種機制，coverage 對「非配息型基金」並無 N/A 處理（缺值即 missing）。這是現況描述，不是修改建議 |

## 3. 合法取得 Active Sheet 持倉的現有路徑與憑證前提

### 3.1 現有路徑（只描述，不新增程式）

| 路徑 | 檔案＋符號 | 憑證前提 | 與 BL-0545 的關係 |
|---|---|---|---|
| 個人 OAuth 登入 | `infra/personal_oauth.py`（`begin_authorization`／`complete_authorization`／`confirm_pending_login`／`ensure_fresh`／`logout`） | 部署 secrets 內的 Google OAuth client 設定（`load_client_config`）；使用者本人在瀏覽器完成授權；scope 為最小唯讀 | token 只存在使用者 session 的 runtime；不寫檔、不寫 Sheet |
| Active Sheet 狀態機 | `shared/active_sheet.py`（`set_pending`／`activate_pending`／`get_active`） | 需要同一 session 已有正式登入帳號 sub；驗證成功才成為 Active；換帳號即失效 | 持倉資料來源的唯一合法選定入口；未選定時不得自動用 `POLICY_SHEET_ID`、不得自動選第一本、不得沿用舊 session（J-13） |
| 個人 Active Sheet 唯讀讀取 | `repositories/personal_policy_reader.py::load_workbook_tables`（目標由呼叫端注入 `(sheet_id, access_token)` 與 `account_sub`） | 需要上述 session 的 access token；本檔不讀設定、不讀環境變數、不讀服務帳戶，無 fallback | 回傳保單分頁列（含 `fund_code` 等欄）；只有讀取呼叫 |
| session 組裝 | `services/v2_tables/personal_session.py`、`services/v2_tables/alo_holdings.py`、`ui_v3/adapters/assets_source.py` | 同上 | 組出 `fund_code` 對照與持倉表給資產頁；皆為既有唯讀消費者 |
| 服務帳戶＋部署固定 Sheet | `repositories/policy_supplement_repository.py`（`POLICY_SHEET_ID`）、`repositories/policy/*` | 服務帳戶金鑰＋部署 secret | **不是** Active Sheet 路徑；依 J-7／J-13 不得作為個人持倉的替代或 fallback。**不可**用於 BL-0545 的 Active Sheet 覆蓋率 |
| 使用者自備代號清單 | `scripts/audit_6d_coverage.py --from-file`（亦支援 `--from-checkpoint`、命令列代號） | 無需 Google 憑證；需要可連 MoneyDJ 的網路 | 該腳本刻意**不**讀 Google Sheet 政策；它抓的是三個 6D 候選維度，不是五維健康評分，**不能直接當五維覆蓋率探針** |

### 3.2 在沒有使用者登入下，哪些步驟不可能

1. 取得 Active Sheet 的 `sheet_id`：只能由使用者在登入後的 session 內選定（`activate_pending`），本環境不存在該 session。
2. 呼叫 `load_workbook_tables`：需要使用者的 access token 與 `account_sub`；本環境沒有。
3. 以其他身分代讀：**禁止**。本環境雖有沙箱基礎設施身分（用於 git／雲端 CLI 的代理），那是基礎設施憑證，不是使用者的 Google 帳號授權，**不得**用來讀使用者的 Google Sheet 或冒充使用者；也不得用 `POLICY_SHEET_ID` 猜測哪一本是使用者的 Active Sheet。
4. 臆造持倉：持倉代號是使用者私人資料，不可猜測、不可用公開熱門基金代替。
5. 另查：本環境 `.streamlit/` 僅有 `config.toml` 與 `secrets.toml.example`，沒有實際 secrets 檔（NOT VERIFIED 的是 Streamlit Cloud 部署端另行注入的 secrets，本環境看不到）。

### 3.3 合法的唯讀探針執行方式（兩種擇一，皆不新增程式碼）

- **方式 A：使用者在自己的登入 session 內執行。** 由使用者以自己的帳號登入、選定 Active Sheet 後，在該 session 內以既有唯讀路徑取得持倉列，再由使用者本人（或使用者授權的當下工作階段）執行探針協定（第 4 節）。最小授權即現有 J-1 的唯讀 scope，**不得**新增寫入 scope、不得持久化 token。
- **方式 B：使用者自行提供匿名化基金代號清單。** 使用者自行從自己的 Sheet 匯出「基金代號」欄（可去除保單編號、金額等其他欄位），一行一個，交由 `scripts/audit_6d_coverage.py --from-file` 或等價的唯讀探針消費。此方式不需要任何 Google 憑證，但產出的**身份去重與「保單持倉列」對應需由使用者提供對照**（匿名化後無法還原 `policy_id`）。
- 兩種方式都需要：可連到 MoneyDJ 等既有合法來源的網路；以及探針的**輸入、輸出、時間戳**留存為 Evidence（第 4 節）。

## 4. 可重現的探針協定（調查協定，不是新產品規格，不新增門檻）

### 4.1 輸入

1. **原始持倉列**（保留，不丟棄）：每列至少 `policy_id`、`fund_code`（Sheet「基金代號」欄原值），其餘欄位視使用者匿名化需求而定。
2. **基金身份去重**：以 `(policy_id, fund_code)` 保留原始保單持倉列；再把 `fund_code` 對應到 canonical 基金身份。去重規則**引用 repo 既有規則，不自創**：
   - Sheet「基金代號」欄的代號依 `DEC-2026-10-28-05`／`DEC-2026-10-29-01`，以 `services/fund_identity.py::resolve_fund_identity(..., input_source="sheet_fund_code_column")` 的語意判定：只有 `verification_status` 為 `base_resolved_attributes_unverified` 的結果才有 `canonical_key`，可據以合併；`unresolved`、`namespace_unknown_suffix_not_stripped`、`moneydj_suffix_unverified_not_stripped`、`sheet_code_contract_violation`、`exception_distinct_series_needs_decision` 等狀態**一律不合併**，以完整原始代碼（逐字相同才算同一檔）各自計為獨立身份並標明原因。
   - 禁止用名稱相似性合併；禁止從後綴、幣別、名稱推斷屬性（沿用 DG2 裁示：未知就是 Unknown）。
   - 注意：`DG2_SHADOW_ENABLED` 目前為關閉；production 路徑的對照鍵為 `services/v2_tables/fund_keys.py::resolve_full_keys`（Sheet `fund_code` → MoneyDJ `full_key`，對不上回錯誤、不截斷、不猜）。探針去重應採**哪一個鍵**作為「唯一基金」的最終定義，是**需要客戶或總管明確指定的點**（見第 7 節），本文件不替它選。
3. **探針執行時點**：記錄 `fetched_at`（探針實際執行時間，UTC，含時區）。

### 4.2 輸出 JSON 結構（欄位定義；所有計數皆為整數，缺值用 null，不用 0 代替）

```json
{
  "schema": "bl0545_probe_output_v1",
  "source": {
    "holdings_origin": "active_sheet_oauth_session | user_supplied_code_list",
    "active_sheet_id_hash": "<單向雜湊或 null；不輸出原始 sheet id>",
    "account_sub_hash": "<單向雜湊或 null>"
  },
  "as_of": "<持倉資料讀取時間 ISO8601>",
  "fetched_at": "<探針執行時間 ISO8601>",
  "formula_version": {
    "health_module": "<services/health/grade.py 的 git blob SHA 或 commit SHA>",
    "main_sha": "<執行時 main SHA>"
  },
  "population": {
    "holding_rows": null,
    "unique_funds": null,
    "identity_unresolved": null,
    "fetch_success": null,
    "fetch_failed": null,
    "not_attempted": null
  },
  "dimensions": {
    "coverage|sharpe|trend|volatility|fx_risk": {
      "applicable_n": null,
      "scored_n": null,
      "not_applicable": null,
      "unsupported": null,
      "missing": null,
      "stale": null,
      "conflict": null
    }
  },
  "per_fund": [
    {
      "canonical_key_or_raw_code": "<去重後身份>",
      "identity_status": "<DG2 verification_status>",
      "policy_rows": ["<policy_id, 僅序號或雜湊>"],
      "fetch_status": "ok | failed | not_attempted",
      "fetch_failure_reason": "<代碼或 null>",
      "dimensions": {
        "<維度>": {
          "status": "scored | not_applicable | unsupported | missing | stale | conflict",
          "reason_code": "<原因代碼>",
          "proxy": false,
          "obs_date": "<該維所用資料的觀測日或 null>",
          "source_tag": "<來源標記或 null>"
        }
      }
    }
  ]
}
```

欄位規則：

- **五個互斥狀態**（`not_applicable`／`unsupported`／`missing`／`stale`／`conflict`）加上 `scored`，對每一檔、每一維**恰好屬於一個**。維度層計數必須滿足：`scored_n + not_applicable + unsupported + missing + stale + conflict` 等於 `fetch_success`（抓取成功的基金數）；`applicable_n` 為扣除 `not_applicable` 後的基金數。**抓取失敗的基金不進任一維計數，單獨記在 `fetch_failed`**，且 `fetch_success + fetch_failed + not_attempted` 必須等於 `unique_funds`（`not_attempted` 即下一條的身份無法解析者）。
- 身份無法解析的代碼：計入 `unique_funds` 並標 `identity_unresolved`，其 `fetch_status` 為 `not_attempted`，**不得**悄悄從分母移除（輸出的 `population` 需另含 `not_attempted` 計數）。
- **proxy 標記**：該維若使用替代資料（例如以 6M 數值代 1Y、以其他幣別代該幣別、以報酬回退代 MA 方向），`proxy` 必為 true 並在 `reason_code` 說明；**不得**把 proxy 計為與原生同口徑的 scored 而不揭露。
- **目前程式能自然產出的狀態**：現行 `compute_4d_health` 只輸出 scored／missing／n/a（見 F9）。`unsupported`、`stale`、`conflict` 若要在探針中出現，必須由**探針自身的判讀層**依證據標記（例如非 USD 外幣標 `unsupported`，因現行 provider 僅支援 USD），並在 `reason_code` 註明這是探針標籤，不是 production 輸出。本協定**不定義**判 stale／conflict 的日期或差距門檻；若需要，須另行請客戶裁示。
- **公式／模型版本**：記錄被探針呼叫的健康評分模組之 commit／blob 識別，不記錄也不複製門檻值。

### 4.3 判讀禁忌

1. missing 不等於 0；缺值不得以 0、預設值或其他維度補入。
2. 2/5 的字母等第不得顯示成 5/5；任何呈現等第的地方必須同時帶 `scored_n/applicable_n` 與缺哪幾維。
3. 覆蓋率不等於准入：覆蓋數字只描述「有多少維算出分數」，**不構成**「可用於正式判斷」的結論。准入條件需另經客戶裁示，本協定不定義。
4. 不得自創 PASS／SAFE／OK 之類的總結字樣或燈號；輸出僅陳述計數與原因代碼。
5. 抓取失敗率必須與欄位命中率並列揭露；不得只報告「成功抓取後」的命中率。
6. 公開樣本探針（若有人另做）必須明標「公開樣本，非 Active Sheet，不代表使用者持倉」，不得與 Active Sheet 結果合併或互相替代。
7. 單次上游錯誤先記 `fetch_failed` 並保留原因，不得據以永久歸類為 unsupported。

### 4.4 驗收測試條件（輸入到預期輸出，不含閾值設計）

| # | 輸入 | 預期輸出（結構性） |
|---|---|---|
| T1 | 空清單 | `unique_funds` 為 0，各維計數皆 0 或 null，不得除以 0 產生比率；不得輸出任何覆蓋比率 |
| T2 | 同一 `fund_code` 出現在兩個不同 `policy_id` | `holding_rows` 為 2、`unique_funds` 為 1；`per_fund[0].policy_rows` 含兩個項目；該基金只抓取一次 |
| T3 | 兩個 `fund_code` 字串不同但 DG2 判為同一 `canonical_key` | 合併為一檔，`identity_status` 為 `base_resolved_attributes_unverified`；若判為 `namespace_unknown…`／`…not_stripped`，則**不合併**，兩檔各自計 |
| T4 | 台幣計價基金 | fx_risk 狀態為 `not_applicable`，不進 fx_risk 的 `applicable_n`，也不進 missing |
| T5 | 非 USD 外幣基金（現行 provider 僅支援 USD） | fx_risk 標 `unsupported`（探針標籤）或 `missing`（production 原樣），`reason_code` 區分；不得以 USD 資料代打 |
| T6 | 只算出 2 維的基金 | 輸出含 `scored_n=2`、`applicable_n` 與缺哪幾維；不得被呈現成 5/5 |
| T7 | 抓取失敗的基金 | 計入 `fetch_failed`，不進任一維的 scored／missing 計數；`fetch_success + fetch_failed + not_attempted` 與 `unique_funds` 對得上 |
| T8 | 使用 proxy 資料（如 6M 代 1Y）的維度 | `proxy` 為 true；是否計入 `scored_n` 須在輸出中可區分（以 `proxy` 旗標區分，不改變計數定義） |
| T9 | 任一輸出 | 維度計數合計等於 `fetch_success`；任何不等即判探針輸出無效並停止，不得補數 |
| T10 | 輸出檔本身 | 不含 token、client secret、原始 sheet id、Email、內網位址；`active_sheet_id_hash` 為雜湊 |

## 5. 結論與限制

1. **現況事實**：#1157 的承重事實在目前 main 大致仍成立；唯一明顯的「已變」是覆蓋揭露欄位已存在於報表與個基卡（F3），但現行揭露只覆蓋 scored／missing／N/A 三態。
2. **新增發現（單組、未獨立複驗）**：F4b（三個 production 呼叫點皆 `ma_dir=None`）與 F5 附註（`SUPPORTED_FX` 只有定義、不是守門條件）。
3. **無法回答的問題（NOT VERIFIED）**：Active Sheet 內有多少唯一基金、多少抓得到、五維各自命中多少。原因單一：沒有合法的使用者憑證／持倉清單。
4. **BL-0545 的下一步**取決於使用者以第 3.3 節方式 A 或 B 提供輸入；在此之前**不得**以任何合成或猜測資料宣稱覆蓋率。

## 6. 本批執行的驗證（原樣回報）

- 環境：`/root/.local/bin/pytest` 9.1.1（uv tool，獨立 venv），以 `PYTHONPATH` 指向 repo 根目錄與系統 site-packages（該處 pandas 為 3.0.5、numpy 為 2.5.3，**高於 `requirements.txt` 的 pandas 上界 3.0 之限制**；因此下列結果為「在非 repo 釘版環境下」的結果，只能作為參考，**不能替代 CI**），並加 `--noconftest`（`tests/conftest.py` 需要完整依賴）。
- `tests/test_grade_4d_guard.py`、`tests/test_fund_health_report.py`、`tests/test_health_action.py`、`tests/test_bl0441_missing_semantics.py`：**80 passed**。
- `tests/test_flow_layer3c.py`、`tests/test_grp_health_regime_once.py`、`tests/test_fund_identity_dg2.py`、`tests/test_personal_policy_reader.py`、`tests/test_active_sheet_state.py`：**202 passed、1 skipped、2 failed、2 errors**；失敗與錯誤的原因均為 `ModuleNotFoundError: No module named 'streamlit'`（本環境未安裝，屬環境缺依賴，不是程式行為失敗）。
- 文件測試（`tests/test_doc_counters.py`、`tests/test_constitution_*.py`、`tests/test_canonical_rule_consistency.py`）：結果見本批最終回報；本文件不重複寫入測試輸出，以免文件內數字與實跑漂移。
- 檔尾恰一個換行與無行尾空白：以 `tail -c` 與 grep 人工複核（`pre-commit` 未安裝，未跑真工具）。

## 7. 需要客戶／總管裁示的點（登記，不是動工）

1. **「唯一基金」的最終去重鍵**：應採 DG2 canonical identity（目前 `DG2_SHADOW_ENABLED` 關閉、屬 shadow）還是 production 的 `resolve_full_keys` 所產生的 `full_key`？兩者在帶後綴代碼上的結果可能不同。
2. **stale／conflict／unsupported 的判定依據**：現行 production 不產出這三態；若要成為正式准入欄位，需客戶裁示定義（本協定刻意不定義日期或差距門檻）。
3. **探針由誰執行**：方式 A（使用者登入 session）或方式 B（使用者提供匿名化代號清單），以及方式 B 下是否接受「無法還原保單層級對應」。
4. **`SUPPORTED_FX` 是否應成為真正的守門條件**：目前為文件性常數；屬產品／程式行為變更，須另案，不在 BL-0545 展示方向的授權內。
