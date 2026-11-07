# 基金健康評分資料覆蓋准入｜唯讀稽核（2026-11-06）

> **性質**：原始程式與現有測試的靜態查核，**不是持倉實測報告、不是新公式／門檻、不是 New UI2 動工授權**。
> **稽核 main SHA**：`861628cc377352c4f651ddc1172e13ab07e4d90d`。本批未修改計算、資料來源、UI、歷史持倉、任何正式規格或生產資料。
> **獨立性**：本批單組讀碼，未完成第二組獨立稽核或 runtime 等價測試。
> **邊界**：Old UI read-only logic reference；New UI2 應遵守 `docs/v2/44_fund_ui_ssot.md`、`docs/v2/57_amendment_8_directional_judgment.md`、`docs/v2/67_ai_action_vocabulary.md` 與 `docs/v2/80_new_ui2_architecture_proposal.md`。

## 1. 已證實的程式行為與排除候選

| 指標 | 現行計算／取得契約 | 稽核發現 | 靜態判定與建議 |
|---|---|---|---|
| 近一年配息覆蓋（coverage） | `services/health/grade.py::_score_coverage` 需要 1Y 含息報酬與年化配息率；`services/fund_total_return.py` 現行唯一回報來源為配息還原淨值法，須達 `RET_1Y_RESTORED_MIN_WINDOW_DAYS`（原始碼註明 350 天）；配息型且窗口無配息紀錄不得硬算 | 短期 NAV／缺配息序列時不可算，屬**條件性缺值** | **保留有效時的客觀計算**；無合法數值保持 Missing，不能推成「不吃本金」。公式風險訊號 ≠ 官方「配息來源含本金」揭露 |
| 風險調整報酬（Sharpe） | `services/health/report.py` 使用 `metrics.sharpe`；`services/fund_grp_health/unified.py` 標示可能來自 MoneyDJ 官方 1Y、官方 6M 或自算 N 天 | **期間／來源可能不同**，即使有數字也不必然可以跨檔等同比較 | 保留，但准入需核實期間、定義、無風險利率／年化與來源；6M 不得無註記冒充 1Y |
| 走勢（trend） | `services/health/grade.py::_score_trend`：MA 方向或單靠 1Y 報酬的回退；`services/health/report.py::build_health_analysis_row` 呼叫時 `ma_dir=None` | **該批次報表路徑不提供實際 MA 方向**；仍可能因 1Y 報酬超過 ±5% 給走勢分 | 不得把該報表 `trend` 稱為「已驗 MA60 走勢」；保留 1Y 報酬證據，MA60 方向進入正式判斷前另查全體 caller 與有效 NAV |
| 年化波動（volatility） | `metrics.std_1y` → `_score_volatility`；`sigma_pct <= 0` 排除 | 曾發現缺 NAV 將 σ 回退為 0，誤獲 90 分；現在有守衛（`tests/test_grade_4d_guard.py`） | **保留**合格歷史波動值；不足期／σ≤0 回 Missing；σ 是風險／價格位置證據，不等同基金品質惡化 |
| 外幣 FX 波動（fx_risk） | `services/health/report.py` 從 `fx_regime_by_ccy` 取 std／mean，再算 CV；`services/fx_regime_service.py::SUPPORTED_FX = ("USD",)` | **目前該歷史波動提供器只支援 USD**；EUR、JPY、ZAR 等外幣走 Missing；TWD 計價基金為 N/A，不進分母 | 對非 USD／TWD 的外幣，**暫不納入 FX 維度評分**直到獲核准有效 FX 歷史與觀測日；不得把 USD 代替其他幣別；TWD 維持 N/A |
| 總費用率 TER（非現行健康五維） | `scripts/audit_6d_coverage.py::_probe_expense`；`services/health/grade.py` 記錄歷史稽核 | 2026-08-14 兩檔歷史樣本中官方 TER **0/2**；其他命中可能只是經理費估算，不能等同總費用率 | **維持不納入正式分數**；僅保留有真實出處的明細。不是宣稱全部基金永遠拿不到 TER |
| 基金規模（非現行健康五維） | `_probe_scale` 讀 `fund_scale` 字串 | 歷史兩檔示例包含「億(美元)」與「百萬歐元」，單位／貨幣未標準化直接比大小不安全 | **維持不納入正式分數及跨幣別排名**；保留原文 Evidence，未來若有 verified normalize 契約再評估 |

## 2. 最重要的「稽核工具與正式評分」不一致

1. `scripts/audit_6d_coverage.py::_probe_fx_risk` 對外幣使用 `get_latest_fx("{ccy}TWD=X")` 確認**即期匯率**能否讀到；這不代表 `fx_regime_by_ccy` 已有**歷史匯率 std／mean 序列**，也不代表健康評分的 FX 維能計分。**不得直接用舊報表的「匯率可算率」當 5D FX 覆蓋率**。
2. 舊稽核總表採 `n = len(codes) - n_fetch_fail` 作成功抓取分母。該比例可用來觀察**成功抓取後的欄位命中率**，但不能取代「所有唯一基金的端到端有效覆蓋率」；需**同時揭露抓取失敗率**。
3. `compute_4d_health` 名稱維持 4D，實際為 **5 維**（coverage／sharpe／trend／volatility／fx_risk）；`GRADE_4D_MIN_FACTORS=2` 且須有 coverage 或 Sharpe 任一核心維度，即可輸出字母等第。**2/5 的 A 不可被前端或 OneBrain 說成 5/5 的 A**。原始覆蓋 `n_scored/n_applicable`、`missing`、FX N/A 必須外露，不可僅傳 Grade。
4. 以上不構成修改最低評等維度數、權重或等第切點的許可；新 UI 顯示與准入規則需另過正式 Gate。

## 3. 判斷「永遠／必然缺值」須區分五個狀態

| 類別 | 意義 | 例子 | 決策 |
|---|---|---|---|
| `unsupported` | 現有 producer 沒支援這種資料形態 | 非 USD 外幣的 5D FX 歷史波動 | 對該類型暫停正式評分，不宣稱永久無法取得 |
| `not_applicable` | 這維對該標的不適用 | TWD 計價的外幣 FX 維度 | 從適用分母移除，不視為缺資料 |
| `missing_or_invalid` | 該標的資料缺、型態錯、值不合法 | NAV 不足、σ≤0、配息歷史不足 | 不評分，保留原因與來源 |
| `stale_or_conflicting` | 日期過期、幣別／算法口徑矛盾 | Sharpe 6M 和 1Y 不可等同；外幣 FX 不同觀測日 | 不納入需同口徑的比較，待正式契約驗證 |
| `eligible` | 來源、有效性、期間及適用性均合格 | 合格 NAV 的 σ；真實配息記錄＋合格 1Y 還原報酬 | 可列客觀證據；仍須另檢查行動規則／Risk Cap |

狀態名稱僅為**本次稽核標籤**，不是新的正式 UI 詞彙、Domain schema 或 Rule threshold。

## 4. 後續「實際持倉命中率」需要什麼證據

**本批沒有**登入使用者 Google Sheets、沒有取得 Active Sheet 的完整持倉資料，也沒有重抓 MoneyDJ／FX 或執行 `scripts/audit_6d_coverage.py`。所以目前**不能提供**每個維度在真實持倉中命中幾檔的百分比，更不能判定所有外幣的配息/NAV 都不可取得（FX 波動的限制只在特定 provider）。

正式唯讀探針建議（另批；未授權前不施工）：

1. 從**使用者指定的 Active Sheet** 唯讀取得持倉；以已驗證的基金身份／級別／幣別去重，每檔只抓一次，但**保留各保單／部位與原始來源**；禁止用名稱相似性合併。
2. 依既有 L1／L2 取數路徑產出單檔各維原始資料、來源、as-of、觀測日、樣本期間、公式版本及驗證結果；不以 0 補 None。
3. 每個維度至少同時報三個分母：全體唯一基金數、來源成功抓取基金數、該維實際適用基金數；`eligible/unsupported/N/A/missing/invalid/stale/conflict` 的合計需能對回總數。
4. 分別統計「原始資料取得」「有足夠樣本」「有效可比」「准入正式規則」四層；遇到單次上游錯誤先重試/分日複核，不立刻永久排除。
5. 評估結果與來源證據作為一份 Evidence；產出**保留／僅顯示不評分／建議退出正式評分**的候選清單，經客戶裁示後才改動正式公式及 UI。

## 5. New UI2／OneBrain 守衛建議（非實作規格）

- UI 精簡顯示狀態、有效維度與原因；**完整原始證據與缺口留在 Evidence Registry**，不得將隱藏欄位當作不存在。
- OneBrain 只讀經驗證的 Domain Results／Decision Digest。未評估 ≠ 安全；未送達 AI ≠ 資料不存在；稽核標 `unsupported` ≠ 把原始資料刪除。
- 市場普遍下跌不得直接被低 NAV／負報酬評為基金管理品質差；市場調整後與同類比較須另行驗證 benchmark 類別、期間、幣別與報酬口徑。
- 本批不改 `services/health/grade.py`、`services/fx_regime_service.py`、`scripts/audit_6d_coverage.py`、`docs/v2/44_fund_ui_ssot.md` 或任何現有測試。

## 6. 靜態證據索引（SHA 鎖定）

- [健康評分 SSOT](https://github.com/linchen-20200325/my-Fund-dashboard/blob/861628cc377352c4f651ddc1172e13ab07e4d90d/services/health/grade.py)
- [健康報表 caller（ma_dir=None）](https://github.com/linchen-20200325/my-Fund-dashboard/blob/861628cc377352c4f651ddc1172e13ab07e4d90d/services/health/report.py)
- [FX provider 僅支援 USD](https://github.com/linchen-20200325/my-Fund-dashboard/blob/861628cc377352c4f651ddc1172e13ab07e4d90d/services/fx_regime_service.py)
- [1Y 含息報酬的有效性與歷史下限](https://github.com/linchen-20200325/my-Fund-dashboard/blob/861628cc377352c4f651ddc1172e13ab07e4d90d/services/fund_total_return.py)
- [原稽核工具（spot FX、成功抓取分母）](https://github.com/linchen-20200325/my-Fund-dashboard/blob/861628cc377352c4f651ddc1172e13ab07e4d90d/scripts/audit_6d_coverage.py)
- [2 維評級護欄測試](https://github.com/linchen-20200325/my-Fund-dashboard/blob/861628cc377352c4f651ddc1172e13ab07e4d90d/tests/test_grade_4d_guard.py)
- [原歷史小樣本覆蓋證據](https://github.com/linchen-20200325/my-Fund-dashboard/blob/861628cc377352c4f651ddc1172e13ab07e4d90d/PHASE1_FINAL_ISSUE_LIST.md)
- [正式 OneBrain 輸入與 Action Gate](https://github.com/linchen-20200325/my-Fund-dashboard/blob/861628cc377352c4f651ddc1172e13ab07e4d90d/docs/v2/67_ai_action_vocabulary.md)

**驗收現況**：本批只讀原始檔案與既有測試案例、比對流程與假設；沒有執行 runtime pytest、沒有真實持倉探針、沒有獨立 QA。此 PR 即使 CI 成功，也不能替代那三項證據。
