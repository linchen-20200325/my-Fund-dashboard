# BL-0545 具體解鎖條件（2026-11-17）

> **BL-0545 維持【BLOCKED】，本檔不改其狀態欄、不升格任何 Pending、不新增 DEC。** 登記不構成動工授權（`CLAUDE.md` §-1）。
> 基準：main `0ac6c086`（2026-11-17 `git fetch` 實查）。**單組作者整理，未經獨立 QA；全稱句標「單組未驗」。** 僅 grep／讀檔，**未跑探針、未做任何 live 或網路探測。**

## 1　結論（寫最前面）

1. **BLOCKED 的本質是客戶的暫停裁示，不是純技術阻擋**：`DEC-2026-11-12-02` 摘要 (5)「BL-0545 繼續 BLOCKED，不要求客戶提供輸入」。`docs/BACKLOG.md` BL-0545 列亦載「使用者目前選擇暫不提供真實輸入」。
2. **專案 AI 可自主完成的工作，沒有一項能解鎖它**（§4）。
3. **目前不建議向客戶發問**（已裁示不要求輸入，重問等同違反該裁示的精神）。**僅在客戶主動表示要解鎖時**，先走 G-A、G-C、G-D（§5）。

## 2　缺口分類（為何「真實覆蓋率 NOT VERIFIED」）

| 類別 | 內容 | 依據（本組已核對） |
|---|---|---|
| 尚未提供 | 真實持倉輸入：**方式 A**＝使用者本人合法登入 session（Active Sheet）；**方式 B**＝使用者自願提供匿名基金代碼清單 | `docs/evidence/bl0545_active_sheet_coverage_probe_status_2026_11_07.md` §3.3；BACKLOG BL-0545 列 |
| 專案 AI 無權取得 | 不得以服務帳戶、`POLICY_SHEET_ID`、沙箱基礎設施身分代讀使用者的 Google Sheet 或冒充使用者 | 同上 evidence §3（「以其他身分代讀：禁止」）；`DEC-2026-11-07-03`「不授權」欄（不得讀取或儲存 token／密碼） |
| 尚未量測／尚未實作 | 探針 live 與每檔取數：**NOT IMPLEMENTED**；只給 `--codes-file`（無 fixture／注入 fetcher）時每檔取數為 `not_attempted`（`live_mode_not_implemented_no_fetcher`） | `scripts/bl0545_coverage_probe.py` 檔頭 docstring 與 `run_probe`（`fetcher is None` 分支）；`docs/evidence/bl0545_coverage_probe_phase1_2026_11_07.md` §3 |
| 尚未定義 | 正式 admission：**NOT DEFINED**（輸出固定 `admission: "NOT DEFINED"`）；stale／conflict 一律 `not_evaluated`；unsupported 僅為探針標籤 | 探針 docstring；`DEC-2026-11-07-03`「仍未授權」欄 |

補充事實：探針 CLI 實際只會把 `holdings_origin` 設為 `user_supplied_code_list` 或 `fixture`（`_main` 內 `origin`）；協定文字中的 `active_sheet_oauth_session` 值**目前沒有程式路徑可產生**（單組 grep 結果，未驗全 repo 無其他寫入點）。

## 3　已有、不需重做的東西

- #1166（研究）、#1168（Phase 1 唯讀探針，`scripts/bl0545_coverage_probe.py`＋`tests/test_bl0545_coverage_probe.py`）均已合併；探針授權 `DEC-2026-11-07-03` 不再重問。
- 三層分母協定（全體唯一基金／抓取成功／各維適用）與 T1～T10 驗收測試已在 `bl0545_active_sheet_coverage_probe_status_2026_11_07.md` §4。

## 4　專案 AI 可自主完成者（皆不能解鎖）

| 工作 | 為何不能解鎖 |
|---|---|
| 離線測試維護（fixture 情境、T1～T10 回歸） | 輸出是 fixture 結果，**不是**真實覆蓋率；用 fixture 冒充真實輸入是禁止事項 |
| 文件同步（HANDOFF／BACKLOG／evidence） | 不產生新資料 |
| 承重事實重驗（例如 `compute_4d_health` 行為、`SUPPORTED_FX` 現況） | 屬靜態稽核，沒有真實持倉分母 |

## 5　必須客戶決策者（僅在客戶主動要解鎖時才問）

| Gate | 決策內容 | 推薦（總管讀法，可被客戶推翻） |
|---|---|---|
| **G-A** | 是否撤回「暫不提供輸入」（`DEC-2026-11-12-02` (5)） | **維持現狀、不重問** |
| **G-B** | 若撤回：輸入方式 A（本人 session）或 B（匿名代碼清單，代價是無法還原保單層級對應） | **B**（不經 OAuth、不碰 token，風險最低） |
| **G-C** | 是否授權「每檔取數」。兩條路：(i) 由客戶在**自己本機**執行探針，只回傳**去識別化摘要**；(ii) 專案實作 fetcher／live。**查無既有 DEC 允許「本機執行後回傳摘要」這種做法（單組 grep，未驗全稱）→ 需裁示**；(ii) 另涉新 live 模式與 Provider 邊界 | 先 (i)；(ii) 另案 |
| **G-D** | 「唯一基金」去重主鍵：DG2 canonical（`resolve_fund_identity`，旗標預設關）或 production `resolve_full_keys` | 沿用 `resolve_full_keys` 為主分組、DG2 僅 shadow 比較（`DEC-2026-11-07-03` 已如此，只需確認不變） |
| **G-E** | stale／conflict／unsupported／admission 的定義 | **維持 NOT DEFINED**（本輪不需要，解鎖不依賴它；覆蓋率可先以 `not_evaluated` 呈現） |

## 6　客觀驗收條件（解鎖後才適用；缺一不得宣稱「已量測真實覆蓋率」）

1. `holdings_origin` 為 `active_sheet_oauth_session` 或 `user_supplied_code_list` 的**真實輸入**，並留存 `as_of`、`fetched_at`、`main_sha`。
2. 具備每檔取數能力（G-C 路徑之一）。
3. 通過協定 T1～T10 的結構性條件，特別是：各維度計數合計＝`fetch_success`（T9）；`fetch_success + fetch_failed + not_attempted ＝ unique_funds`（T7）；輸出不含 token、sheet id、Email（T10）；缺值以 null 表示、**不用 0**（T1）。
4. 抓取**失敗率與命中率並列**揭露（協定 §4.3 第 5 點）。
5. 獨立 QA（非作者）。
6. admission 維持 NOT DEFINED，不自創 PASS／SAFE 總結。

## 7　禁止重述（防止下一輪重蹈）

- 不得索取客戶真實持倉或任何憑證／token；不得用服務帳戶或 `POLICY_SHEET_ID` 代讀。
- 不得以 fixture、公開樣本或合成資料冒充真實覆蓋率或填「百分比」。
- 不得做 live 探測（本環境亦無使用者憑證）。
- 不得把本檔讀成已授權 G-C(ii) 或任何新取數實作。

## 8　NOT VERIFIED

1. 「查無既有 DEC 允許本機執行並回傳摘要」為單組 grep 結論。
2. `active_sheet_oauth_session` 無程式路徑可產生：單組 grep。
3. 真實 Active Sheet 的唯一基金數、抓取成功率、各維命中率：全部無資料。
4. 探針測試本檔未重跑。

## 9　來源

`docs/BACKLOG.md` BL-0545 列；`docs/DECISIONS.md` `DEC-2026-11-06-02`、`DEC-2026-11-07-03`、`DEC-2026-11-12-02`、`DEC-2026-11-13-01`；`docs/evidence/bl0545_active_sheet_coverage_probe_status_2026_11_07.md`；`docs/evidence/bl0545_coverage_probe_phase1_2026_11_07.md`；`scripts/bl0545_coverage_probe.py`。
