# BL-0545 Phase 1｜唯讀五維覆蓋探針：用法與協定對照（2026-11-07）

> **真實 Active Sheet 覆蓋率：NOT VERIFIED。**
> 本文件與探針輸出**不含**任何覆蓋率百分比或命中檔數當作事實；fixture／使用者自備清單的輸出
> **不是**真實 Active Sheet 覆蓋率，也**不是**准入判定。

- **授權**：客戶於 PR #1167 留言「核准唯讀探針」（`DEC-2026-11-07-03`）。
- **協定出處**：`docs/evidence/bl0545_active_sheet_coverage_probe_status_2026_11_07.md` 第 4 節（schema `bl0545_probe_output_v1`）。
- **獨立性**：本批為施工者單組作業，**未經第二組獨立稽核**（`CLAUDE.md` §-2 規則 6）。

## 1. 檔案

| 檔案 | 說明 |
|---|---|
| `scripts/bl0545_coverage_probe.py` | 單檔、獨立、**本檔不直接 import streamlit**（匯入 production 模組時，若環境有 streamlit 會被載入）、**沒有任何 production 呼叫端** |
| `tests/test_bl0545_coverage_probe.py` | T1～T10 與語意護欄測試（全離線） |
| `docs/DECISIONS.md` | 新增 `DEC-2026-11-07-03` |

## 2. 用法

```
python scripts/bl0545_coverage_probe.py --codes-file codes.txt            # 只做身份去重（無每檔資料 → not_attempted）
python scripts/bl0545_coverage_probe.py --fixture fixture.json --out out.json
python scripts/bl0545_coverage_probe.py --codes-file codes.txt --fixture fixture.json --main-sha <sha>
```

- `--codes-file`：一行一個 `fund_code`；亦允許兩欄 CSV `policy_id,fund_code` 以保留保單列。空行與 `#` 開頭略過。
- `--fixture`：離線 JSON，`schema` 必須是 `bl0545_probe_fixture_v1`：
  `holdings`（`policy_id`／`fund_code` 列，僅在未給 `--codes-file` 時使用）、`mapping`（可選；有給才注入 `resolve_full_keys`，含給空物件＝空表；未給則走下方預設對照表）、
  `as_of`（可選）、`funds`（以 production 主鍵 `full_key` 為鍵）。每檔：
  `{"status": "ok", "inputs": {tr1y_pct, adr_pct, sharpe, sigma_pct, ma_dir, fund_ccy, fx_cv_pct}, "dimension_meta": {<維度>: {proxy, obs_date, source_tag}}}`
  或 `{"status": "failed", "reason": "<snake_case 代碼>"}`。
- `--main-sha`：由使用者提供；探針不推斷。
- 結束碼：0＝輸出有效；2＝輸入錯誤（含 fixture 的 holding 缺 `fund_code`）；4＝輸出被洩漏檢查拒絕（未寫檔）；3＝輸出標 `valid: false`（T7／T9 守恆不成立或與 `compute_4d_health` 覆蓋欄不一致，**不補數**）。

## 3. 設計決策

1. **live 抓取模式：NOT IMPLEMENTED。** 不新增來源、不改 production、本環境無網路與使用者憑證，未實測；每檔資料只來自 fixture 或呼叫端注入的 `fetcher`（`run_probe(..., fetcher=...)`）。沒有 fetcher 時，該檔 `fetch_status = not_attempted`、原因 `live_mode_not_implemented_no_fetcher`。
2. **Active Sheet 讀取：本批不實作、不呼叫**；輸出固定 `real_active_sheet_coverage: "NOT VERIFIED"`、`admission: "NOT DEFINED"`、`live_mode: "NOT IMPLEMENTED"`。`active_sheet_id_hash`／`account_sub_hash` 恆為 null。
3. **主鍵 vs shadow**：主分組＝`resolve_full_keys`。**預設對照表**：未注入時沿用 production 預設（內建表加執行當下 cwd 的 `fund_code_mapping.csv`；L1 只做本機讀取，無網路、不寫檔，其 stdout 訊息被攔截以免污染 JSON），並在 `identity.primary_provenance` 揭露 `mapping_source`（固定列舉 builtin／csv+builtin／injected）、`mapping_size`、`parser`（程式常數），以及 cwd 的 csv 是否存在（`cwd_mapping_csv_present`）與內容 sha256（僅存在時，不輸出路徑）。**結果受執行時 cwd 的 `fund_code_mapping.csv` 影響，與 production 相同**；注入對照表（fixture `mapping` 或 `run_probe(mapping=...)`）可完全離線覆寫。逐檔 `identity_status` 只有 `primary_resolved`／`primary_unresolved`（主鍵結果）；DG2 的 `verification_status` 在 `shadow_verification_status`。`shadow_diff.primary_ok_dg2_not_base_n` 為「主解析成功但 DG2 非 base_resolved」的代碼數（不改主分組）。`identity.shadow_diff` 為 DG2 `resolve_fund_identity(..., input_source="sheet_fund_code_column")` 的平行比較（以連通分量列出兩邊分組不一致的代碼、各自 `verification_status`）。DG2 失敗或例外只記錄 `shadow_error`，不影響主結果；探針不讀不寫 `DG2_SHADOW_ENABLED`。
4. **維度狀態**：由唯讀呼叫 `compute_4d_health` 的 `factors`／`fx_risk_status`／`coverage` 導出，不自行重算分數；探針另以 `coverage` 欄交叉核對，不一致即 `valid: false`。狀態集合：`scored`／`not_applicable`／`unsupported`／`missing`。
5. **`unsupported`（探針標籤）**：非 USD 外幣且 production 為 missing → `unsupported`，`reason_code = probe_label_fx_provider_usd_only`，並以 `production_status: "missing"` 保留 production 原樣。USD 取不到 CV、幣別缺漏仍為 `missing`。`unsupported` 計入 `applicable_n`（協定約定）。
6. **`not_evaluated`**：stale／conflict 沒有裁示的判定依據，探針不自訂日期或差距門檻；頂層 `not_evaluated_states: ["stale","conflict"]`、維度計數 `stale`／`conflict` 為 null（不是 0）、逐檔維度 `stale_status`／`conflict_status` 為 `"not_evaluated"`。
7. **null 規則**：`fetch_success = 0`（含空清單）時五維計數全為 null；`proxy_scored_n` 為相對協定的**增補欄位**（僅為區分 proxy，不改變計數定義）。
8. **輸出衛生**：自由字串一律走白名單（代號、原因代碼、ISO 日期、sha、標籤），其餘以固定占位符取代（標籤上限 40 字元，過長為 `reason_code_too_long` 並另記長度）；不輸出例外訊息、原始 URL、policy_id（改為序號）；序列化後再過一道洩漏檢查，命中即拒絕輸出。
9. **本探針沒有「ok/PASS」之類的總結**：逐檔 `fetch_status` 沿用協定字面（`ok`／`failed`／`not_attempted`），其餘只有計數與原因代碼（缺值 `reason_code` 是**探針依輸入有無推斷**的標籤，不是 production 輸出；輸入若為 0 或被上游標成缺值，會被標為 absent，探針無法分辨），另附 `coverage_disclosure.text`（例如 `2/5`＝scored_n／applicable_n）。

## 4. 與協定第 4.4 節對照

| 協定 | 本批處理 | 測試（`tests/test_bl0545_coverage_probe.py`） |
|---|---|---|
| T1 空清單 | unique_funds 0、各維 null、無比率 | `test_t1_*` |
| T2 同碼兩保單 | holding_rows 2、unique 1、policy_rows 2（序號）、只抓一次 | `test_t2_*` |
| T3 canonical 合併 | **依本次限定改為 shadow 比較**：主分組不變、差異於 `shadow_diff` 揭露；DG2 預設關閉時探針仍可平行比較且不改旗標 | `test_t3_*` |
| T4 TWD | `not_applicable`，不進 applicable_n、不進 missing | `test_t4_*` |
| T5 其他外幣 | `unsupported`（探針標籤）＋`production_status: missing` | `test_t5_*` |
| T6 2 維 | 顯示 `2/5` 與缺哪幾維 | `test_t6_*` |
| T7 抓取失敗 | 記 `fetch_failed`，不進維度計數；守恆檢查；不重試 | `test_t7_*` |
| T8 proxy | `proxy` 旗標＋`proxy_scored_n`；探針不推斷 | `test_t8_*` |
| T9 守恆 | 不等即 `valid: false`、CLI 結束碼 3、不補數 | `test_t9_*` |
| T10 輸出衛生 | 記憶體現編負控（email／長 id／bearer 樣式／內網位址／URL）不得出現在輸出 | `test_t10_*` |
| 補充 | missing≠0；無 PASS／SAFE／OK 字樣；stale／conflict 為 null；不改動 `compute_4d_health`；靜態檢查（不 import streamlit／os／網路套件、無環境變數讀取）；無 production 模組 import 本探針；CLI | 其餘 `test_*` |

## 5. NOT VERIFIED／NOT RUN 清單

| 項目 | 狀態 |
|---|---|
| 真實 Active Sheet 覆蓋率（唯一基金數、抓取成功數、五維命中） | **NOT VERIFIED** |
| live 抓取模式 | **NOT IMPLEMENTED**（因此亦 NOT RUN） |
| Active Sheet 讀取／OAuth 路徑 | **NOT RUN**（本批不實作、不呼叫） |
| `resolve_full_keys` 對真實 Sheet 值的行為 | **NOT VERIFIED**（只以合成代號驅動） |
| stale／conflict 判定 | **NOT EVALUATED**（無裁示門檻） |
| 第二組獨立稽核 | **NOT VERIFIED** |
| Streamlit 相關測試與完整 CI | 以 CI 為準；本機只跑第 6 節列出的子集 |
| `pre-commit` 真工具 | **NOT RUN**（本環境未安裝；以其判定邏輯人工複核） |

## 6. 本批本機驗證

見 PR／最終回報的測試數字；本文件不寫入測試輸出，以免文件內數字與實跑漂移。
