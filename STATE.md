# STATE.md — 基金戰情室 (Fund Dashboard)

> 極簡熱資料檔。完整 roadmap 見 `BACKLOG.md`；技術細節見 `ARCHITECTURE.md` / `SPEC.md` / `STRATEGY.md`。

## 🧹 2026-07-22 全域排毒 Wave A3(slice 1):portfolio_service 百分比 parser 收 SSOT v19.373

- **病灶(SSOT 查緝 #3,parser 分歧)**:`services/portfolio_service.py` 自帶 `_parse_pct`(僅 strip '%')
  + 2 處 raw inline `float(str(x).replace("%",""))`,與 SSOT `shared.converters.safe_num`(_safe_num_ps,
  另 strip ',' + 擋 bool/inf/nan)分歧。
- **修**:3 處全收斂 `_safe_num_ps`(`_parse_pct` 改別名 + 2 inline 直呼)。費用率域輸出等價且更穩,
  缺/髒值仍回 None → 下游 graceful fallback 不變。本檔 inline 百分比 parser **0 殘留**。
- **驗**:`test_expense_ratio_custody` + `test_real_ter_fundclear` + `test_factor_availability_ssot`
  32 綠。**唯一改動檔:`services/portfolio_service.py`**。
- **A3 未竟(後續逐檔續收)**:`fund_fetcher.py:113 safe_float` 重複定義(30+ caller,大 blast radius,
  需獨立謹慎處理)、`nav_metrics` / `policy/v2` / `fund_orchestration` / ui 的 inline replace 鏈。

## 🧹 2026-07-22 全域排毒 Wave A2:fund_service max_dd ÷0 guard v19.372

- **A2 病灶(SSOT 查緝 #4,真 bug)**:`services/fund_service.py:491 calc_metrics` inline max_dd
  `(cum-cummax)/cummax` **無 ÷0 guard**(對比 SSOT `portfolio_service.compute_max_drawdown` 有
  `(s<=0)` 防線)。停售/剛成立/資料異常使 cum≤0(§4.6 邊界)→ 產生 >100% 假回撤(實測 -163%)
  或 inf/NaN 灌入 KPI + 連動污染 calmar。
- **修(behavior-preserving)**:加 `len>=2 & (cum>0).all() & (cummax>0).all()` guard,退化回 None
  (對齊本函式 Sharpe/Sortino/Calmar 既有 §1 防線;calmar:516 已 None-safe;跨檔消費全走
  `.get`+`_safe_float`)。非退化算式逐位元相同(cummax 只算一次)→ max_dd 數值零變化。
- **為何不直接改呼 compute_max_drawdown**:本函式 max_dd 建於 `cum=(1+log_ret).cumprod()`
  (log_ret 為 log 報酬),與 SSOT 直接吃 NAV 序列 **basis 不同**,swap 會改數值 → §-1/§req1 不做,
  只補 guard(SSOT 收口留待 basis 統一的獨立議題)。
- **驗**:`test_fund_service_advanced_metrics` + `test_fund_load_enriched` 17 綠;等價驗算
  normal old==new(-8.84)、degenerate old -163% → new None。**唯一改動檔:`services/fund_service.py`**。

## 🧹 2026-07-22 全域排毒 Wave A1:multi_factor z-score 收 SSOT v19.371

- **背景**:4 維並行深掃(架構越權 / SSOT / 死碼 / 肥大 god-file)後 user 同意藍圖,進實作階段,
  嚴守「一次一檔」。動刀順序 A(真 bug+SSOT)→ B(分層越權)→ C(邏輯下沉)→ D(死碼)。
- **A1 病灶(SSOT 查緝 TOP-1,真 bug)**:`services/calibration/multi_factor.py:250 _zscore` 自帶一份
  z-score,std=0 時回 `0.0`,與 SSOT `repositories/macro/math_utils.zscore`(回 `NaN` + log)**分歧** →
  退化因子被靜默中性化,違 §1 Fail-Loud。
- **修(behavior-preserving)**:`_zscore` 委派 SSOT 計算。因本 composite 用 `sum(skipna=False)`
  (單一 NaN factor 會清空整條 composite),退化因子(std=0 = 零資訊 = 無 tilt)**顯式**中性化 0
  (§1 填補三要件:顯式呼叫 + SSOT 已寫 log + 語意註明);非退化路徑逐位元相同 → composite 數值零變化。
  另 raw `252` → `shared.signal_thresholds.TRADING_DAYS_PER_YEAR` SSOT。
- **驗**:`test_multi_factor_optimization` 50 綠;退化因子 sanity(flat→全 0 / composite 含退化因子仍
  非空 len 29 不被清空 / 正常因子 z std≈1;SSOT 現對 std=0 寫 log)。
- **分層**:`_zscore` lazy import `repositories.macro.math_utils.zscore`(L2→L1 純 util,macro_service
  同 precedent),無新違憲。**唯一改動檔:`services/calibration/multi_factor.py`**(+ app.py 版號 + 本檔)。

## 💰 2026-07-22 真實 TER(FundClear fetcher)v19.370 —(user 點名續做「真實 TER」)

- **背景**:v19.368 費用率僅到「經理+保管」估計(mgmt+custody_est),缺官方揭露的年度
  **總費用率(TER / 經常性費用 / OCF)**。此項原標「⏸️ 卡環境(需台灣網路)」,user 明確
  點名續做 → §-1 允許動工。
- **關鍵洞察(比照 v19.368)**:真 TER 若有揭露,就在**已抓回的同一份回應**裡——FundClear
  `GetFundBasicInfo` JSON 或 MoneyDJ 基本頁 `rows_map`——只是沒抽。**零新增 HTTP**。
- **L1 抽(5 點,additive)**:
  - `_src_fundclear_meta`:JSON 多候選欄位(`TotalExpenseRatio`/`OngoingCharges(Figure)`/
    `TER`/`OCF`/… + camelCase + `總費用率`/`經常性費用`)→ `meta["expense_ratio"]`(比照
    既有 `inception_date` 7 變體防禦式抓法);§3.2 (0,10]% 才收。
  - 3 個 `rows_map` 站點(sources.py MoneyDJ ×2 + AllianzGI)+ 1 orchestration →
    `total_expense_ratio`(key 變體 總費用率(%)/總開支比率(%)/經常性費用(%))。
- **L2 消費**:`calc_fund_factor_score` 費用率優先序插入「揭露 TER」層(§2.1 官方揭露 > 估計):
  顯式/metrics → **disclosed_ter(top-level expense_ratio 或 moneydj_raw.total_expense_ratio,
  (0,10]% guard)** → mgmt+custody_est → mgmt_only_est。`get_factor_availability` 同步鏡射
  (✅/❌ ↔ 納入 1-1)。
- **§1 誠實降級**:欄位缺(最常見)/ 髒值 / 越界 → 一律 graceful fallback 回估計,零回歸;
  沙盒 403 打不到 fundclear.com.tw,**欄位名為多候選推測**,實機由台灣網路驗證(命中即真 TER,
  未命中維持 v19.368 估計)。
- **測試** `tests/test_real_ter_fundclear.py` 11(揭露優先 ×2 / metrics 仍最高 / 越界+0+髒值
  退估計 / v19.368 行為不變 / 百分比非 ratio / availability 鏡射 / L1 source-lock)。
- **分層**:L1 抽 + L2 純函式消費,零新模組 / 零新 EX-* / 無 L1→L2。§8.2 零違憲。

## ✅ 2026-07-22 F-SCHEMA-1 餘量 + CPI 文件更正 v19.369 —(序列 8/8,**未結案序列全數完成**)

- **CPI「剩 2 處 inline」查證 = 過時記載**:(1) score lambda 現於
  `services/calibration/macro_score.py:75 _s_cpi`,:58-60 已吃 `CPI_YOY_THRESHOLDS` SSOT
  (v19.202 P2-2);(2) `ui/helpers/macro/helpers.py:187` 已用 `_CPI_BULL_HIGH`(:28 SSOT)。
  → **無 code 待辦**,CLAUDE.md §8.3 CPI 條目更正為 ✅ 全收(文件與現實對齊)。
- **F-SCHEMA-1 餘量輕量驗證**(v19.189 輕量版同精神,不加 pandera):
  新 `external_market_repository._validate_market_series`(§4.2:空放行;非空必須 DatetimeIndex
  單調 + 無重複日 + 全有限值;違反 raise → 外層 except 轉空 + log → fallback chain 走下一源,
  壞資料不靜默流入)。接線 4 點:stooq 兩回傳點 / cboe / defillama(defillama 顯式 try 防外洩)。
- **測試** `tests/test_market_series_validation.py` 7(空放行 / 合法原樣 / 重複日 / 未排序 /
  inf / 非 DatetimeIndex 各 raise + 三 fetcher 接線 source lock)。
- **未結案序列 8/8 全完成**(v19.362-369):①狀態燈 → ③NAS 累積 → CI 停排程 → ④儲存收斂 →
  純累積救援 → 健康度對帳(F-RECON-1 全結)→ 費用率 est → SCHEMA 餘量+CPI 文件。
  LLM 兩項(AI 結構化 / LLM-as-judge)依 user 指示不做。

## 💸 2026-07-22 費用率升級:經理+保管 TER 估計 v19.368 —(序列 7/8)

- **現況**:費用率鏈 = 顯式 expense_ratio → metrics(從未產生)→ `mgmt_fee`(v19.191)。
  但經理費 ≠ 總開銷比率(TER 還含保管費等)。
- **發現**:MoneyDJ 基本頁 `rows_map` **整表已抓回**,只抽了「最高經理費」——「保管費」同表在手
  沒抽 → **零新增 HTTP** 補抽即可。
- **修**:4 個抽取點補 `custody_fee`(sources.py 基本頁 ×2 + AllianzGI meta + orchestration;
  key 變體 最高保管費(%)/保管費(%)/保管費);`portfolio_service` 費用率因子升級:
  兩費齊 → `er = mgmt+custody`(source="mgmt+custody_est",TER 兩大主成分,比單經理費準)、
  僅經理 → 原行為(source="mgmt_only_est")、顯式真值恆優先(source="metrics")。
  factors 加 `source` key(schema-additive provenance)。
- **§1 誠實界定**:est = 兩個真實揭露值之和 + 顯式 source 標記,非捏造;
  **真 TER**(FundClear 年度費用資訊)端點驗證需台灣網路(沙盒 proxy 403 擋 TW 站),
  留待 user 有需求時在 App/NAS 端實測 —— 不在沙盒瞎寫沒驗過的 fetcher(§1 不猜)。
- **測試** `tests/test_expense_ratio_custody.py` 5(兩費相加 / 單費原行為 / 真值優先 /
  壞值顯式跳過 / schema-additive);advanced_metrics 迴歸 12 綠。

## ⚖️ 2026-07-22 健康度雙演算法對帳 v19.367 — F-RECON-1 最後一項收尾(序列 6/8)

- **背景**:F-RECON-1(§4.3 重算對帳)基金端 3 組對帳 v19.87-91 已落地,唯 macro health score
  一直單一 path(`calculate_composite_score` 加權淨分),CLAUDE.md §8.3 掛「等 user 點」多時。
- **第二演算法**(方法學獨立):**不加權多空方向投票** — 只數 score>0/<0 指標數,
  `net_ratio=(n_pos-n_neg)/n_valid`,**無視權重** → 專抓「單一大權重指標把總分拖向與多數指標
  相反方向」的權重配置錯誤(加權和自己驗自己驗不出這種)。
- **L2 `reconcile_composite_score(ind)`**(composite_score.py):A 向用 `get_verdict_cutoffs`
  同組語意分界(§3.3 不另造 magic)、B 向中性帶 `COMPOSITE_VOTE_NEUTRAL_BAND=0.2`(SSOT 新常數);
  status ∈ agree / neutral_mix(弱訊號非衝突)/ disagree(⚠️)/ no_data(§1)。
- **L3**:tab1 綜合健康度 hero 卡下加對帳 chip(agree ✅ / disagree ⚠️ 顯示;neutral_mix/no_data
  不佔版面);非致命 try/except。
- **測試** `tests/test_composite_reconcile.py` 6(同向 agree / **大權重拖翻 disagree 核心場景** /
  60-40 中性帶 / no_data 誠實 / 投票無視權重的獨立性 / weighted_total 與主演算法同源)。
  分數取極值,任何合理 cutoffs 下方向不變(防 active.json 改分界讓測試 flaky)。
- **F-RECON-1 至此全結案**(基金 3 組 + macro 1 組)。

## 🛟 2026-07-22 純累積序列救援 v19.366 — live 全敗 Sheet 頂上(序列 5/8)

- **問題**:v19.360 的合併只在 live series **存在**時觸發;live **全敗**(series=None,
  來源被擋/改版時的常態)→ 早退,累積再多也用不上 —— 正是「來源死了靠累積活」的核心場景缺口。
- **前置查證**:L1 **不預寫** `result["status"]`;status 由 `classify_fetch_status`(fund_fetcher:197)
  在 enriched pipeline(finalize)**之後**從內容推導(name + series≥10 + metrics)→ 救援注入
  series+metrics 後 status 自然升級 complete/partial,無 stale status 風險(PR-1 時的顧慮解除)。
- **修**:`_merge_nav_history_series` 接受 `s_live=None`(視為空序列,純累積整段頂上);
  `finalize_fund_metrics` 把合併移到 `s is None` 早退**之前** —— live 全敗但 Sheet 有累積 →
  救援(trace `nav_history_rescue`)+ 走 ② 稀疏門(累積序列必檢);Sheet 也空 → 行為與現在
  完全一致。救回但 <10 筆 → series 留(真資料)、metrics 不算(§1)。
- **測試**:consume 加 4(密集 300 筆救援成功+不稀疏 / Sheet 空行為不變 / 5 筆救回但不算 metrics /
  merge(None) 單元),16 綠。

## 🗃️ 2026-07-22 ④ 三套儲存收斂 v19.365 — Sheet 為 durable SSOT(序列 4/8)

NAV 散在三處:cache/nav(git,CI 寫,已停排程)/ cache/nav_history(本機磁碟,Tab6 CSV 匯入)/
Google Sheet nav_history(durable)。收斂原則:**寫路徑全指向 Sheet、讀路徑不動**(舊快取仍當
fallback 讀,零回歸)。§8.1 step 6 自評:不做大遷移重構,只補兩個真缺口:
- **(A) Tab6 CSV 匯入補雙寫**:原本只寫 `cache/nav_history/`(Streamlit Cloud 重啟即清空,
  = user 匯入的歷史會默默蒸發的真陷阱)。現匯入成功後同步 `nav_history_gs.import_csv_text`
  (source="tab6_csv",(code,date) 去重、GS 未啟用顯示誠實 caption、同步失敗非致命)。
- **(B) 一次性遷移腳本 `scripts/migrate_nav_caches_to_sheet.py`**:兩套舊快取(CI schema
  `history:[{date,nav}]` + Tab6 schema `dates/values`)→ 統一 point → `append_points`(冪等)。
  預設白名單過濾(`_discover_fund_codes`,擋 XYZ/CACHED01 類測試殘留),`--all` 全搬;
  壞檔顯式 skip + 列名(§1);secrets 缺 exit 2。user 在本機/NAS 跑一次即完成搬家。
- **免做確認**:cache/nav_history 殘留檔未被 git 追蹤(容器本機殘留,repo 乾淨);
  讀者(`_src_cache_files` / nav_history_store 讀路徑)不動。
- **測試** `tests/test_migrate_nav_caches.py` 5(雙 schema 解析 / 白名單擋殘留 / --all /
  壞檔顯式 skip / 目錄缺回空)。

## ⏸️ 2026-07-22 CI 每日 NAV workflow 停排程留手動 v19.364 — 空跑收斂(序列 3/8,user 選 A)

- **決策**:user 4 選 1 選「停排程、留手動」。`每日淨值快取更新` 已實證從 GitHub 美國 IP
  對台灣基金源全抓不到(run #557/#71 log),每天只產生空跑 commit + 假覆蓋警告;
  累積已由 ③ NAS cron(v19.363)接手。
- **改動**:`.github/workflows/fetch_nav_cache.yml` 拔 `schedule` cron(`30 16 * * *`),
  保留 `workflow_dispatch` 手動觸發 + 註解說明恢復方法(可逆)。YAML 驗證通過。
- **不動**:`cache/nav/*.json` 保留(app `_src_cache_files` fallback 仍讀);
  `scripts/fetch_nav_cache.py` 保留(手動觸發用)。

## ⏰ 2026-07-22 ③ 台灣端每日累積(NAS cron)v19.363 — 封「覆蓋靠使用習慣」致命傷(序列 2/8)

- **新 `scripts/accumulate_nav_tw.py`**:台灣 IP 端(NAS/本機)每天自動抓一次最新 NAV 寫
  `nav_history`,不靠 user 開 App。與 CI 腳本(美國 IP、精簡依賴、平行實作)不同 —— 本腳本裝
  **完整 requirements**、直接走 app 已驗證抓取鏈 `services.moneydj_fetcher.auto_fetch_moneydj`
  (tab2/健診同一條),**不做第二份抓取實作**(SSOT)。
  - 代碼清單復用 `fetch_nav_cache._discover_fund_codes`(importlib,避免第二份清單漂移);fallback env `NAV_CODES`
  - 取值復用 `nav_history_hook._extract_point`(series 末點 SSOT,同 App 端規則;scripts/ 為 ops 入口不受層級 import 約束)
  - §1:secrets 缺 → exit 2、全抓失敗 → exit 1(cron 信可見);單檔失敗顯式 skip + 計數不拖累整批(§4.6)
  - §5:同日重跑 (code,date) 冪等
- **L2 修 NAS 相容坑**:env fallback 的 `google_service_account` 是 **JSON 字串**(非 dict)→
  舊 `status()`/`_get_sheet` 會誤判未啟用。新 `_sa_to_dict`(dict 原樣 / JSON 字串→dict / 壞值→{});
  `is_enabled()` 改委派 `status()`(單一判斷源,Streamlit 端行為不變);`_get_sheet` 解析後仍無
  client_email → raise(§1)。
- **NAS 設定**(user 動作):`pip install -r requirements.txt` + env 兩把
  (`google_service_account`=SA JSON 字串 / `macro_weights_sheet_id`)+ cron
  `30 18 * * 1-5 cd <repo> && python scripts/accumulate_nav_tw.py`(台灣時間傍晚,NAV T+1 多傍晚更新)。
- **測試** `tests/test_accumulate_nav_tw.py` 7(happy path nas_cron 標記 / 單檔失敗不拖批 /
  冪等 dup 計數 / 空清單 / _sa_to_dict 5 型 / env 字串 SA status 啟用);nav_history 全家 **59 綠**。

## 💡 2026-07-22 ① NAV 累積狀態燈 v19.362 — 終結「以為在累積其實沒有」(未結案序列修復 1/8)

user 指示:未結案項目除 LLM 兩項(AI 結構化輸出 / LLM-as-judge)外按序逐一修。本項為第 1 件。
- **問題**(體檢瑕疵 #6):GS secrets 沒設時累積是「安靜略過」——設計上不干擾 local,但雲端漏設
  secrets 時 user 會以為在累積、其實沒有(靜默失敗,違 §5 可觀測精神)。
- **L2 `nav_history_gs.status()`**(新,可測):回 `{"enabled": bool, "missing": [缺的 secret 名]}`,
  檢查 `google_service_account`(需含 client_email)+ `macro_weights_sheet_id`。
- **L3 兩處亮燈**:
  - Tab5 「🗂️ NAV 歷史匯入」expander 頂部:🟢 已啟用 / 🔴 未啟用(列缺哪些 secrets + 修法)
  - `nav_history_hook._record`:未啟用時**一次性** caption 提示(session 旗標 `_nav_hist_disabled_warned`
    防洗版),不再純靜默 return。
- **測試**:test_nav_history_gs 加 3(測試環境無 secrets → disabled + missing 列名 / monkeypatch
  secrets 齊 → enabled / status 與 is_enabled 同向),34 綠。
- **序列待辦**:③ NAS 每日累積 → CI workflow 去留 → ④ 儲存收斂 → 純累積救援 → macro 對帳 →
  費用率 → F-SCHEMA-1 餘量 → CPI inline。

## 📥 2026-07-22 PR-2(A) 保單對帳單 CSV 匯入 nav_history v19.361 — 立刻補回數年歷史(B+A+② 組合完結)

B+A+② 最後一塊:v19.360 裝好引擎(消費端接線)後,本 PR 給「油」——user 從保險公司對帳單
下載歷史淨值 CSV,一次灌入 `nav_history` → **不必等每日累積,馬上解鎖 3Y/5Y/低基期**。
- **L2 `nav_history_gs.import_csv_text(code, csv_text)`**:CSV → 解析 → `append_points`
  (§1 過濾 + §5 (code,date) 去重,重跑不灌水)。欄位偵測 header 關鍵字(日期/淨值/date/nav),
  無 header 退第 1 欄=date、第 2 欄=nav;**ROC 民國(113/03/15)與西元都吃**(復用
  `nav_history_store._parse_roc_or_western_date`);千分位逗號 nav OK;壞列顯式 skip + 計數回報。
  **真 bug 抓到**:「淨值日期」欄同時含「淨值」→ nav 欄誤中 date 欄,`_pick_col` 加 `exclude` 防呆
  (ROC 測試紅→修→綠,測試先行價值實證)。
- **L3 Tab5**:`### ⑥` 前加「🗂️ NAV 歷史匯入」expander(代碼 + 名稱 + file_uploader + 匯入鈕;
  utf-8-sig 解碼吃 Excel BOM;GS 未設 secrets → 誠實紅字不靜默;成功顯示 解析/新寫入/重複/壞列 四計數)。
- **測試** `tests/test_nav_history_import.py` 7(header 西元 / ROC / 無 header / 千分位+壞列計數 /
  對既有列去重 / GS 未啟用誠實 / 空文字);nav_history 三檔共 **50 綠**。
- **使用法**:Tab5 → 🗂️ NAV 歷史匯入 → 輸代碼(如 TLZF9)→ 上傳 CSV → 按匯入;
  下次分析該基金,v19.360 的合併器自動把匯入歷史併進 Sortino/Calmar/3Y/5Y/低基期計算。
- **B+A+② 全落地**。剩餘(等 user 點):③ 台灣端自動每日累積(NAS cron)/ ① 累積狀態燈 / ④ 三套儲存收斂。

## 🔌 2026-07-22 Increment B+② 累積序列接回 metrics v19.360 — 消費端總開關(user 核准 B+A+② 組合的 PR-1)

策略體檢(artifact 610d949e)後 user 核准「B 引擎 + A 油 + ② 安全帶」。本 PR = B+②;A(CSV 匯入)為 PR-2。
- **B 消費端接線**(§8.2 改掛 **L2**,避免 gap-scan 原建議掛 L1 `fund_orchestration` 重蹈 EX-L1ORCH-1 上行違憲):
  - `nav_history_gs.load_series(code)`(新):Sheet 累積點 → pd.Series(昇冪+同日 keep-last+provenance attrs)
  - `fund_service._merge_nav_history_series`:union keep-last、**live 優先**(撞日不被舊累積蓋);
    Sheet 空/未啟用 → 行為與現在完全一致;讀失敗 → **fail-soft** 退 live-only + source_trace 記錄(§4.6 降級鏈)
  - 掛在 `finalize_fund_metrics` **len<10 gate 之前** → 短 live 序列可被累積歷史救回進 metrics
- **② 缺口偵測 + 誠實降級**:`assess_series_coverage`(coverage=點數/預期交易日 span×252/365;max_gap 日曆日);
  門檻 SSOT `shared/signal_thresholds.py`:`NAV_HIST_COVERAGE_MIN=0.6` / `NAV_HIST_MAX_GAP_DAYS=14`(台灣長假 ~9-10 天)。
  稀疏 → **只砍自算年化值**(sortino/calmar 恆自算、sharpe 僅 `sharpe_source=self_calc`、std 僅 `std_source=nav`),
  **wb07 權威值保留**(MoneyDJ 用完整日資料算,不受我們序列稀疏影響);metrics 加 `nav_coverage`/`is_sparse`/`sparse_reason`(§1)。
  **只在真的併入累積歷史時啟動** → 純 live 序列零回歸風險。
- **測試** `tests/test_nav_history_consume.py` 12(load_series 排序去重 provenance / coverage 密集·低覆蓋·大缺口·短序列 /
  merge live優先·空hist·讀失敗 fail-soft / 端到端:短live被救回·稀疏砍自算·live-only 不變);
  鄰近迴歸全跑(load_enriched/total_return/review_fixes 341+344/sigma_band/advanced_metrics)共 **83 綠**。
  ⚠️ 測試 import 序需 prime `fund_fetcher`(既有 fund_service↔fund_fetcher latent 循環,同 test_fund_load_enriched 註記)。
- **效果**:v19.359 累積 + 未來 PR-2 匯入的歷史,現在**真的會流進** Sortino/Calmar/3Y/5Y/低基期計算。
- **PR-2(A)待做**:CSV(保單對帳單歷史)→ `nav_history_gs.append_points` 批次匯入 + Tab5 上傳介面。

## 🗂️ 2026-07-22 Track 2 App 端 NAV 累積到 Google Sheets v19.359 — 從現在累積(user 選 Track 2)

**Track 1 驗證後轉向**:run #557 log 實證 v19.358 修對了 TDCC 3-2(0→5251 筆),但 **3-4 淨值端點
回 0 筆** + 這些是**保單內部標的碼非 TDCC 統一編號** → 5 檔境外 TDCC 救不了(0/11 fresh)。
CI 精簡腳本重寫的獨立來源(AllianzGI/CnYES/MoneyDJ)從 GitHub 美國 IP 全掛。**但 App 端**
(完整 `sources.py` + NAS 代理)使用者實際查詢時**抓得到當日最新淨值**(user 於 App 確認淨值日期是最近的)。
- **§7/§8 對齊後動工**(user 選 Track 2 + 確認 App 抓得到 + 核准掛兩個點):把 App 顯示成功那筆
  `(code, date, nav)` append 進 Google Sheet `nav_history` 分頁,靠日常使用**從現在累積**歷史序列。
- **L2 新模組 `services/nav_history_gs.py`**(比照 `auto_search_store_gs.py`,複用 `macro_weights_sheet_id`
  那本 workbook + `_gs_enabled` + `get_gspread_client`):`append_points`(讀一次去重 + 一次 `append_rows`
  省 quota)/ `append_point` / `load_points` / `is_enabled` / `NavHistoryError`。**§5 (code,date) 冪等去重**;
  **§1 Fail Loud**:nav<=0/date 壞/code 空 → 不寫(不偽造),真 GS I/O 失敗 → raise;GS 未設 → 安靜 no-op。
- **L3 掛鉤 `ui/helpers/nav_history_hook.py`**(L3→L2,§8.2 乾淨,不擴 EX-CRUD-1 —— 走 L2 有
  auto_search_store_gs 先例):Tab2 抓成功(`tab2_single_fund.py:257`)+ 健診批次(`tab_fund_grp_health.py:154`,
  一鍵累積全部持倉)。`st.session_state['_nav_hist_written']` 防每次 rerun 重寫;錯誤顯示非致命 caption。
- **§4.1 SSOT 取值**:nav 與 date 一律取「同一條 series 的最後一點」(避免 metrics['nav'] 與
  nav_latest wb01-scrape 不同日錯位);series 缺才退 metrics['nav']+nav_date。
- **測試** `tests/test_nav_history_gs.py`(31:寫入/去重×3/建分頁/§1 不足不寫×6/no-op/raise/norm_date×9/
  load/L3 _extract_point SSOT×3+None×5);+ fund_grp_health_dedup 迴歸 7 全綠 = 38。
- **⏳ 回本很慢(user 已知會)**:每天 1 筆 → Sortino/Sharpe ~60 交易日(約 3 月)、3Y ~756 日、5Y ~1260 日。
- **Increment B(未做,分開)**:把累積的 Sheet 序列接回 metrics(`fund_orchestration._span_extend_insurance_nav`
  加 `google_sheet` 候選,「只在更長時才換」)——等真的累積出資料再做。
⚠️ **前提**:僅在 App 能 live 抓到當日 NAV 時有效(Streamlit Cloud 也靠 NAS 代理);proxy 死時該次不累積(§1 不偽造)。

## 🩹 2026-07-22 Track 1 修 CI TDCC 欄位名 v19.358 — 5 檔境外 NAV 每天累積一筆(user「做 Track 1」)

背景:歷史 NAV 挖不到(run #71 證實 AllianzGI/CnYES/MoneyDJ/Yahoo 在 GitHub 美國 IP 全掛),
user 決策改「從現在累積」。診斷發現 `scripts/fetch_nav_cache.py` 的 **CI 精簡實作**(不能 import
sources.py 免拉 streamlit)解析 **TDCC 3-x** 時用**錯欄位名** → 政府 API(TDCC OpenAPI,無 IP 封鎖、
境外基金)雖成功回應卻**恆 0 筆**,cache 停滯:
- `fetch_tdcc_all` / `fetch_tdcc_basic`:code 用 `基金代號`(號)→ 應為 **`基金代碼`**(碼);
- main() TDCC 解析:date 用 `淨值日期` / nav 用 `單位淨值` → 應為 **`日期`** / **`基金淨值`**。
- 三者對齊 app 已驗證的 `repositories/fund/sources.py:_src_tdcc_meta`(2717 / 2732-2733)。
- **效果**:5 檔境外(TLZF9/ANZ89/JFZN3/CTZP0/FLFM1)每天由 TDCC 補 **1 筆最新 NAV**,
  既有 `merge_history`(按日期去重 + 降冪 + [:750] ~2 年)累積不洗舊 → 長期自養歷史序列,
  解鎖 Sortino/Calmar/3Y/5Y/3-3-3。§1:抓不到仍回空不偽造;§5 冪等:同日重跑覆蓋不灌水。
- **6 檔境內不在 TDCC**(TDCC OpenAPI 僅境外)→ Track 2(app 端每日 snapshot 寫 Google Sheet
  `nav_history` 分頁)另案待 user 決策,本次不做。
- **測試**:`tests/test_nav_cache_coverage_alert.py` 加 3 測(TDCC 用「基金代碼」key 得到 /
  merge_history 累積新日期不洗舊 / 同日去重冪等)。全 17 測綠(含 CI 精簡依賴守門)。
- ⚠️ **版本號**:並行 feature 線(07-18/07-20)已用掉 v19.353-357,本 NAV 線改跳 v19.358 避碰撞。

## 📝 2026-07-20 CLAUDE.md RSS 數目校正 v19.357 — 3 處漂移收齊(user 核准 SSOT)

實際 `news_repository.FEEDS` 現為 **5 個**(MarketWatch / Yahoo Finance / CNBC Economy /
CNBC Finance / BBC World;Reuters(3)/FT/Investing/Bloomberg 已於 v19.293~297 下架移除),
但 CLAUDE.md 有 3 處未同步:§2.1 T4 範例列(8 名含已下架源)、§2.1 News 條「8 個」、
EX-PASSTHRU-1「11 RSS feeds」。v19.354 已修 news_repository docstring,當時 CLAUDE.md 屬
governance-sensitive 留待 user 明示 — 本次 user 核准後 3 處全收齊為 5。純憲法文件校正,無 code 改動。

## 🧮 2026-07-18 配息還原淨值供風險指標 v19.356 — 除息跳空不再算假回撤(判斷正確)

user「未完成項目」查證後點名開工(項4)。配息型基金**除息日 NAV 下跳一個配息額**,
這**不是**真實下跌(持有人領到現金),但 `services/fund_service.py:calc_metrics` 的
`log_ret = np.log(s / s.shift(1))` 走**原始 NAV** → 把除息跳空當成一次暴跌:
**高估 σ、放大 max_drawdown、壓低 Sharpe/Sortino**。而 wb07(MoneyDJ 官方風險表)本就含息 →
自算 fallback 與 wb07 **不同基準**(對帳失真)。
- **§8.1 設計核准後動工**(user 選預設案:max_dd 一併含息化,4 指標同基準內部一致)。
- **新增純函式 `_total_return_nav(s, divs)`**(L2,放 `calculate_fund_total_return` 與 `calc_metrics` 之間):
  複用 **SSOT `calculate_fund_total_return()`**(Factor 還原法:`Factor=1+Div/NAV → Cum_Factor.cumprod()
  → Adj_NAV`)+ 既有 `divs→div_df` 轉換規則(對齊 ret_1y_total 路徑:skip amount<=0、日期斜線正規化)。
  回傳與 `s` **同 index 同長度**的還原序列。
- **改動範圍極小(1 處污染點)**:`calc_metrics` 內 `s_tr = _total_return_nav(s, divs)`,
  `log_ret` 改吃 `s_tr` → σ / Sharpe / Sortino / max_drawdown 全走還原序列。
  **顯示值 `now`、買賣點(_sig_win σ通道)、高低點(_hl)、布林、純 NAV 報酬(_ret / ret_1y_total)一律仍用原始 `s`**。
- **§1 Fail Loud 降級**:divs 空/全 amount<=0/日期壞 → 逐點等於 s(**純累積型基金 log_ret 位元相同、零變化**);
  還原後長度/正值不變量不符(如重複除息日使 left-merge 膨脹)→ stderr log + **回退原始 s**(寧可未還原,不回錯位序列)。
- **測試**:新增 `test_total_return_nav_v19_356`(13:降級×4 / golden 還原×2 / 3 個易錯輸入 /
  property 不變量×2 / calc_metrics 整合含息 max_dd 顯著小於 raw / **純累積型零變化對帳** / wiring source-scan)。
  相關迴歸 27 + schema-gate/reconcile/provenance 103 全綠。
⚠️ **副作用(user 已知會)**:配息型基金的 max_drawdown 會「含息化」變小(除息假回撤被消掉);
  這正是修正目的 — 反映持有人真實經歷(含再投資)而非帳面淨值跳空。

## 🔌 2026-07-18 出口 YoY 接海關 opendata v19.355 — 取代不存在的 FinMind dataset(數據正確)

user「未完成項目」查證後點名開工(項3)。`repositories/macro_tw_local_repository.py:fetch_tw_export_yoy`
原掛 FinMind `TaiwanMacroEconomics`(v19.342 診斷此 dataset 在 FinMind 不存在)→ 出口卡片**恆無資料**。
- **§7 對齊後動工**:移植股票 repo 已驗證穩定源 **海關 opendata 6053**
  (`opendata.customs.gov.tw/data/6053/csv.csv`,新臺幣出口總值,民國年月降序)。
- **公式(同月對齊,非 iloc)**:西元年 = 民國年 + 1911;`YoY% = (值[Y,M] / 值[Y-1,M] − 1) × 100`。
  抽純函式 `_customs_export_yoy_points(text)`(可單測),延伸為近 6 月 trend + prev + inflection。
  sanity:base>0、民國年≥50、月∈[1,12]、YoY∈[-80,200];fail-loud(來源死/解析空 → error 不腦補)。
- **§4.1 單位誠實**:新臺幣計價(與財政部美元頭條有匯率落差),source `Customs:Export6053(海關新臺幣
  出口總值)` 明標;dict contract(value/prev/trend/inflection/date_latest/source)不變 → UI 端 `_safe_tw()`
  + `validate_tw_export_yoy_dict` 無感。validator 加 `Customs:` 前綴白名單(F-PROV-1)。
- **清理**:移除死 `_EXPORT_YOY_KEYS`(原指向死 dataset);更新檔頭診斷註。
- **測試**:新增 `test_export_yoy_customs_v19_355`(7:同月對齊/缺 base/不足列/欄位不符/base=0/整合成功/
  來源死)+ 改寫 `test_macro_tw_local_fetch` 出口 4 測(改建海關 CSV)+ fuzzy 測改直測 `_finmind_macro_series`
  + provenance 測改 `Customs:Export6053`。schema-gate + 相關 234 passed。
⚠️ **項5(次要源 schema)查證後撤下**:`validate_stooq/cboe/defillama_series` 其實**已 wire 在 consumer**
  (`services/risk_radar.py:143/152` + `liquidity_engine.py:244`)— 資料進計算前已驗,fetcher 端再加 = 冗餘
  (§8.1 step 6),不寫。

## 📝 2026-07-18 文件校正 v19.354 — news_repository docstring RSS 數目漂移

user 批次4「順手把文件小修也做了」。`repositories/news_repository.py` docstring 寫「抓 **11 個**
RSS feed」,但實際 `FEEDS` 現為 **5 個**(MarketWatch / Yahoo Finance / CNBC Economy /
CNBC Finance / BBC World)— Reuters(3)/FT/Investing/Bloomberg 已於 v19.293~297 陸續下架移除,
docstring 未同步。純 docstring 校正,無 code 行為改動。
⚠️ **另註(未動,governance-sensitive)**:`CLAUDE.md §2.1` 寫「8 個 RSS feed」、EX-PASSTHRU-1 條
寫「11 RSS feeds」,兩處與實際 5 個亦不一致 — 屬憲法檔,留待 user 明示再校正。

## ⚡ 2026-07-18 單一基金分析 v19.353 — 移除每次分析冷清全站快取（下載速度大贏面）

user 批次2 大贏面②。`ui/tab2_single_fund.py:212` 「🚀 分析」按鈕每次點都先
`clear_all_caches()` 冷清**全站** TTL cache,再 `auto_fetch_moneydj` 冷抓。
- **根因**:原 v18.60 註解「載入前清 fetch 快取,確保用最新 calc_metrics 邏輯」——但
  (1) calc 是 **code**(部署即重啟自然清快取,不需每次點清);(2) NAV 走 `@_daily_cache`
  (T+1 公布,日內序列不變)。原行為 = **同一基金重複分析、或任何 rerun 後再點,都冷抓
  2000 天 NAV(MoneyDJ HTML 爬,慢)+ 全站 fetcher** → 這是單檔分析頁最大的下載速度痛點。
- **修**:移除 `clear_all_caches()` blanket 冷清(連帶移除只為註冊順序而放的
  `import repositories.macro_repository` — 該模組另有 5+ caller,module cache 照常註冊)。
  「🚀 分析」改吃既有快取 → 同基金再分析走 daily cache 即時回。
- **freshness escape hatch 已存在(非移除唯一路徑)**:sidebar「🧹 全域刷新」
  (`global_refresh_all`,ui/sidebar.py:159)清全站 + 落地檔;tab1 亦有「🆕 強制重抓最新」;
  且 `@_daily_cache` 跨日自動失效。無 lookahead / 無資料正確性風險(cache key 含基金識別,
  無跨基金污染)。
- **同批次查證後略過(§-1,非真 bug)**:orchestrator cache(sub-fetcher 已 `@_daily_cache`,
  再加層 = 過度設計)、並行 NAV cascade(`fetch_fund_by_key` 是 fallback chain cnyes→MoneyDJ,
  並行會改語意 fire-all)、縮 2000d NAV 窗(v19.291 為修 MK 3-3-3「成立 0.1 年」保單代碼誤判
  **刻意**延窗,縮回會 regress)。
- **測試**:`test_tab2_single_fund` 加 `test_analyze_does_not_blanket_clear_caches` 迴歸鎖。16 passed。

## 🐞 2026-07-18 總經判讀 sign 反向修正（v19.352,判斷正確）

user「聽你的建議 都修吧」批次1 第②項。稽核發現**兩處總經白話/橫幅判定 sign 反了**:
- **根因**:`us_indicators.fetch_all_indicators` 全 ~25 指標 score 慣例為 **🟢 正分=偏多/風險降、
  🔴 負分=偏空/風險升**(如 PMI≥50→+2🟢、VIX 恐慌→-2🔴、Sahm 觸發→-2🔴、殖利率倒掛→-2🔴)。
- **`services/macro/explain.py:_interpret_indicator`**:寫成「正分→🔴強烈偏空」,與**同檔** `_verdict_for`
  (`total_score>10→🟢極度樂觀`)自相矛盾。唯一 live consumer(今日關鍵橫幅 chip hover detail)因此顯示
  反向白話。→ 改為正分=偏多、負分=偏空(色碼:偏多🟢/中性⚪/偏空 🟡→🟠→🔴 escalate)。
- **`services/macro/daily_key_alerts.py:_indicator_items`**:判定 `score ≥ SIGMA` → 把**偏多**指標
  當紅色警示置頂,真正**風險側**(負分)指標反被 continue 跳過。→ 改吃負分側:`score ≤ -SIGMA_HIGH`
  紅級、`≤ -SIGMA_LOW` 黃級、`≥ -SIGMA_LOW`(偏多/中性)非事件。|score×weight| 排序不變。
- **測試**:`test_macro_explain.py` 2 個 interpretation 測試(原編碼反向慣例:score=2.0 期望「偏空」)修正
  sign;`test_daily_key_alerts_v19_349.py` 4 個訊號層 fixture 翻負分 + 新增 `test_signal_layer_bullish_
  score_not_surfaced` 迴歸鎖(偏多不進橫幅、風險才進、detail 白話為偏空)。38 passed;broader macro 108 passed。
- **純 sign bug fix**,函式簽名/呼叫圖/資料流全不變,不觸發 §8。

**同版第③項 — 配息日斜線漏算修正**:`services/health/dividend.py:compute_1y_total_return_mk_simple`
Step 5 窗內配息累計,`_date_raw` 未做 `.replace("/","-")` 正規化(dict + tuple 兩分支皆缺),
但**同檔 :358 + `dividend_calc.py:95` + `fund_service.py:501` 三個 sibling 都有**。MoneyDJ 常給
`"YYYY/MM/DD"`,與 dash-ISO 窗界(`_start/_end_date_str` 來自 NAV items,fromisoformat 驗證過)做
字典序比較時 `'/'(0x2F) > '-'(0x2D)` → 窗內配息被誤判超出上界漏算,`div_sum` 少計 → 殖利率/含息
總報酬**靜默偏低**。修:兩分支各補 `.replace("/","-")`(對齊 sibling 慣例)。加 2 golden test
(dict + tuple 斜線日期落窗內算入)。28 passed。純單行防禦式修正。

## 🛡️ 2026-07-13 Put/Call staleness gate（v19.351,外部稽核 C2 查證後唯一真項）

user 上傳外部「雙儀表板終極重構說明書」,逐條查證後**幾乎全是效能/UX/架構升級提案、非 bug**
(且多前提過時:Stock app.py 稱 1178 實際 763、引用不存在的 `ARCHITECTURE_AUDIT.md`、@cache 已普遍、
融資維持率 ÷0 已 v19.91 修)。user 核准唯一值得做的 **C2 後半**。

- **真問題**:`_signal_put_call_ratio` 只取 `s.iloc[-1]` 算 level,**從不看最新資料點日期**。CBOE PCR
  源常過時(v19.141/v19.277 已多次換源),一個數週前的舊值仍會算成 🔴/🟡 塞進 `summarize_radar`
  系統性風險計數 → **用過時值污染風險分數**(違 §1 + §2.4)。
- **修**(§2.4 日頻 🔴>7d + §1):最新點 > `_PCR_STALE_DAYS`(7)天 → 回 `_empty` ⬜。`summarize_radar`
  本就不計 gray → **等同退出風險加權**,附誠實 note「N 天前過時→已退出風險加權」。**沿用既有 gray
  機制,零新架構**。
- **「換 CBOE 官方源」= 稽核誤判(已做)**:v19.277(2026-06-30)已加官方 `volume_and_call_put_ratios`
  (total/equity)為末層源,比稽核早兩週。
- **回歸網**:`test_pcr_staleness_v19_351`(過時→gray / 過時極端值不污染 / 新鮮正常計分 / 7d 邊界 /
  summarize 排除 gray / 常數對齊 §2.4)6 test;`test_risk_radar` 3 個 PCR level 測試改用 `_FRESH_BASE`
  (否則被新 gate 判過時)。**102 passed / 2 skipped 全綠**,新碼 ruff 淨。
- **其餘稽核項全部不做**(§-1):async 重寫/app.py 下沉(已達標)/safe_divide 全案/FinMind 熔斷/
  9 個視覺新功能 → 要嘛已做、要嘛需 §8.1 核准的架構/新功能,user 未點名不動。

## 🗂️ 2026-07-12 Tab5 資料診斷「分類分組」(v19.350,user 要求「參考台股」)

user 看台股 Tab5 診斷表(依類別收合 +「台灣總經（6 筆｜🟢3 🟡1 🔴2）」rollup)後要求基金端比照。原基金 ② 全域資料健康總表為單張平面表 + 三篩選器,無分類。

- **新純模組** `ui/helpers/io/registry_classify.py`(L3 UI helper,**不 import streamlit**、純函式 dict→list):`classify_registry(reg)` 依 key 前綴(總經_/雷達_/新聞_/基金_/組合_)分組 + 算每類 🟢🟡🔴⚪ rollup;`DIAG_CATEGORIES` 中繼 SSOT(前綴→顯示名→未載入提示 Tab);`rollup_caption()` 生成「🟢3　🟡1　🔴2」字串。未知前綴收「其他」群組(§1 不讓已登記資料消失)。
- **Tab5 ② 改造**:平面 rows 迴圈 → 依類別分組渲染。**rollup 反映全類真實健康**(不受篩選,同台股語義);既有三篩選器改為「隱藏列」,謂詞複用既有 `_reg_filtered`(單一真相零重複);整類未載入 → ⚪「請至 TabX 載入」誠實提示。filter/snapshot viewer 保留不動。
- **範圍誠實聲明(§8.1 step 6)**:只做「分組 + rollup + 類別級 ⚪ 未載入提示」= 類別級缺席可見性。**不做逐指標「應有而無」**:總經引擎(us_indicators.fetch_all_indicators)實際輸出 25 鍵與 data_registry `_FREQ` 30 鍵不一致(含 CHN_* 核心迴圈未設),無乾淨正典 SSOT 可比對,硬湊會誤報(違 §1);雷達 10 燈既有 code 本就迴圈跑滿全登記(缺的以 N/A 紅燈現身,不消失),無缺席問題。升級觸發:總經引擎日後抽正典 indicator SSOT → 再加逐指標缺席列。
- **§8.2 分層**:純函式 co-locate `ui/helpers/io/`(與 data_registry 同域 L3);無新資料流、無外部抓取、無跨層違憲。
- **回歸網**:`tests/test_registry_classify_v19_350.py` 7 test(空 registry 五類全未載入/分組+rollup+紅黃綠排序/未知前綴進其他/非dict+缺icon不炸/key 欄注入/rollup_caption 省略 0 燈/多段 key 前綴只取首段)。registry 子集 65 passed。ruff 三檔全淨。

## ⚡ 2026-07-12 「今日關鍵」異常橫幅(v19.349,第 4 步;股票 v19.108 同構)

未完成清單第 4 步(user「第四步 基金端」)。Tab1 頁首置頂橫幅列「今天最需要看的異常」;基金版兩層**零新計算,純消費既有 SSOT 輸出**(對照股票版門檻/急變兩層):

- **訊號層**:吃 `indicators`(fetch_all_indicators,23 keys)各 block 的 `score`(SCORE_RULES SSOT 已算好;fund 慣例正=偏空)。分級沿用 `_interpret_indicator` 同組 `SIGMA_*_CUTOFF`(shared SSOT):≥HIGH(0.8) 紅級/≥LOW(0.3) 黃級,不另造第二套門檻;白話 detail 直接用 `_interpret_indicator(score)`。**同級內依 |score×weight| 降冪** — active.json 校準權重自然決定誰排前面。
- **拐點層**:吃 `detect_turning_points` 輸出(session `_tp_v1948_top`,5 組拐點 signal/icon/note 已判定)。icon {🔴,🔻,⚠️}→紅級/{🟡,🚀}→黃級(利多拐點同樣該看)/{🟢,📊,⬜}=非事件;`source_ok=False`(抓取失敗)不進橫幅。note 作 hover 白話。
- **分層**:L2 `services/macro/daily_key_alerts.py`(純函式,零 I/O 零 streamlit,單項 try 收窄)→ L3 `ui/helpers/macro/key_alerts.py`(純 HTML,股票 v19.108 同構、色票走本 repo shared/colors)→ tab1 標題區後、載入按鈕前掛載。**未載入(兩源皆空)不渲染** — 防誤導性「無異常」(股票版有載入 gate 擋,fund 版無 gate 故由掛載端自守)。
- **回歸網**:`tests/test_daily_key_alerts_v19_349.py` 10 test(全空/σ 分級/校準權重排序/垃圾 score 跳過/拐點 icon 映射+source_ok 守門/跨層紅先/L2 純度/橫幅三態/掛載位置+未載入守門鎖)。相關子集 96 passed。ruff tab1 22=22 零新增,新檔 0 錯。

## 🇹🇼 2026-07-12 TW PMI 接 9 源並行賽跑 — 恆空指標復活（v19.348,設計 B）

user 對「基金端要不要台灣 PMI」答**要**,核准設計 B(§7/§8.1 先設計後動工)。原 `fetch_tw_pmi_local` 掛 FinMind `TaiwanMacroEconomics`(v19.342 判定 dataset 不存在)→ **恆無資料**;本包移植 Stock repo 9 源賽跑讓它復活。

- **新 L1 `repositories/tw_pmi_repository.py`**(~530 行):自 Stock `macro_core.py:932-1353` 移植 9 個解析器 + `PMI_SOURCE_REGISTRY` + `fetch_tw_pmi_race()`(ThreadPool 並行,依優先序取第一命中,**禁止平均** §2.1)。適配:`infra.proxy.fetch_url`(attempts→retries)/log 前綴/`[tw_pmi_repo]`。**不含** Stock 的 90 天檔案 stale-cache 層(§8.1 step 6 先不做;升級觸發:9 源常態全敗需兜底時)。
- **fund 端擴充(超越 Stock 版)**:dgtw(data.gov.tw dataset/6100)CSV 天然含全月度歷史 → 解析器記住命中欄名掃全表回 `series`(升冪,壞列顯式跳過 §1);其餘 8 源單點。
- **`fetch_tw_pmi_local` 改寫**(合約/裝飾器/UI 零改動):吃賽跑結果 → series 源(dgtw)填 trend(6)/prev/inflection(既有 6 分支邏輯原樣);單點源 → value/date/source 有值、trend=[value]、prev=None、inflection 誠實「⬜ 資料不足」;全敗 → error 合約。provenance source 沿用命中源(F-PROV-1 動態血緣)。
- **validator 演進**:`shared/schemas._validate_tw_macro_common` 原寫死「source 必 FinMind: 前綴」(單源時代)→ 加 `TW_PMI_RACE_SOURCES` 白名單(shared SSOT,維持反捏造嚴格度:不收任意字串);**漂移鎖測試**釘 registry 來源名 ⊆ 白名單,兩邊改其一 CI 即紅。
- **舊測試重釘 3+2**:`test_macro_tw_local_fetch` 4 case 自 FinMind mock 改 patch 賽跑(其中 http_fail 改 patch 賽跑 repo fetch_url=None **端到端**跑 9 源全敗 — 原寫法靠沙箱斷網僥倖過,有網 CI 會真打外部源);`test_provenance_phase2` 2 處 source-scan 改驗動態血緣寫法+假 dataset 不得回歸。
- **回歸網**:`tests/test_tw_pmi_race_v19_348.py` 8 test(優先序贏/低位遞補/全敗誠實 error/dgtw series 抽取+壞列跳過/合約映射三態含 validator 原樣通過/SSOT 漂移鎖)。相關子集 274 passed。CLAUDE.md §2.1 裁決表同步更新(PMI 條目改 9 源;出口 YoY 誠實留待)。

## ⚡ 2026-07-12 大工程清單 🟢 ⑯:追蹤誤差 Tracking Error 接 UI（v19.347）

user 核准大工程清單「先做你推薦的三項」(⑯基金/⑨①a股票),本包為基金側 ⑯:

- **現況**:wb07 風險表解析本就把「Tracking Error」收進 risk_table(`clean_risk_table` NUMERIC 集含此鍵),但 `_risk_1y_rows_html`(1Y 風險列共用 renderer,v19.336 M9 抽出,short/long 兩視圖共用)從未顯示 — 抓了不給看。
- **修**:helper 補「追蹤誤差」列 — short 視圖 `追蹤誤差(1Y)` 值原樣;long 視圖 `追蹤誤差 TE(1Y)` 數值型加 %(對齊同視圖標準差既有格式)。缺值誠實顯「—」(§1),字串(N/A)不硬加 %。兩處 caller(partial :428 / complete :1082)零改動自動生效。
- **回歸網**:`tests/test_review_fixes_v19_347.py` 4 test(short 含值/long 加 %/缺值顯—/N/A 字串不加 %)。

## 🧾 2026-07-12 第九份外部 review 落地(基金側):查證屬實 6 組修復（v19.346）

user 上傳第九份深度 review,指示「看是否需要修改讓資料更完整,不修的提供清單」。逐條對 origin/main 查證後基金側屬實 6 組本次修;誤判/已修過/待核准清單見對話/PR 描述。

- **連線層 2 修(nav_metrics)**:①`fetch_nav` MoneyDJ 迴圈 raw `requests.get`(無重試/無 403 降級直連/無 Big5 解碼)→ `fetch_url_with_retry`(infra 統一鏈,同檔 wb01 v14.1 既有慣例;helper 僅 200 回 Response,失敗 None → log 後跳下一源) ②`fetch_div` 同病同修。cnyes/fundrich/fundclear 等 `_fetch_nav_*` 的 raw requests.get 為**不同源不同語意**(JSON API),非本次查證範圍,§-1 不擴 scope。
- **解析 sanity 2 增(nav_metrics)**:③`fetch_holdings` sector_alloc Σpct 檢查 — rows[2:] 定位法版型漂移時比例會悄悄失真;Σ∉[95,105]% → 掛 `sector_alloc_sum_suspect` 旗標+記 `sector_alloc_sum_pct`+log,**不丟資料**(多重資產/部分揭露可合法超帶,§1 不掩蓋不誤殺) ④`fetch_risk_metrics` 核心鍵檢查 — metric 鍵直取 cols[0],MoneyDJ 改標籤時 `clean_risk_table` NUMERIC 集與 UI 查「標準差/Sharpe」靜默落空;缺核心鍵(標準差/Sharpe/夏普值)→ 掛 `risk_table_missing_core` 旗標+log。
- **§3.3 log 6 補(tab2_single_fund)**:⑤無註解裸 `except Exception: pass` 全清 — 新鮮度條/組合聯動/配息型試算/累積型試算/AI 吃本金檢查/AI σ位階 6 處補 stderr log(比照同檔 :1757 慣例);其餘帶 `smoke-allow-pass` 註解者為既核准沉默,不動。
- **診斷頁 2 修(tab5_data_guard)**:⑥`_d5_cell` `fmt` 參數從 v16.5「保留兼容」死參數轉實作 — 狀態判定不變,fmt 有給且值非空時附加實際數值(`✅ 已取得 · 12.3456`),16 個 caller 的 lambda 全部活化,診斷表從「有/無」升級為可肉眼對值(user 本輪「讓資料更完整」指示,fmt 失敗留 log 退回純狀態) ⑦§⑤ 基金資料診斷加誠實 caption — 本區只讀 session_state 快取非即時重抓,原無說明易誤讀為當下狀態(§2.4 精神)。
- **回歸網**:`tests/test_review_fixes_v19_346.py` 11 test — fetch_nav/div 源掃(排除註解行)、holdings Σ 兩態 runtime(monkeypatch + `__wrapped__` 繞 `@_daily_cache` 防測試資料入 production cache,§3.3 隔離)、risk 核心鍵兩態 runtime、tab2 無註解裸 pass 掃零+6 tag、tab5 fmt/caption 掃描。ruff:3 個改動檔 103→102(淨 −1),新測試檔 0 錯。

## 💰 2026-07-11 核心戰情室「含息總報酬(1Y%)」全 None 修復（v19.345）

user 實機截圖回報 核心戰情室 5 檔基金（ACCP138/ACTI71/ACTI94/JFZN3/TLZF9）「含息總報酬(1Y%)」欄全 None,但同表 夏普/年化波動/年化配息率/便宜超跌停利價 都有值。

- **根因（診斷屬實,非資料源故障）**:`ui/components/mk_dashboard.py:243` 該欄直讀 `m.get("ret_1y")`,而 `ret_1y = _ret(252)`（fund_service.py:609）**硬性要求 NAV 序列 ≥252 交易日**（`_ret(n)`:`len(s)>=n` 才算,否則 None）。這些配息型基金本地 NAV 序列 <252 日 → `ret_1y` 恆 None;而 夏普只需 60+ 筆、`std_1y` 退 wb07、`ret_1y_total` 有短窗分支 → 那幾欄照樣有值。**雙重 bug**:① 欄名「含息」卻讀「不含息」的純 NAV `ret_1y`（語意錯）;② 繞過全 app 一致的 SSOT `compute_1y_total_return`（4 層 fallback:perf['1Y'] wb01 → ret_1y_total 含息 → ret_1y → NAV 序列年化）——戰情室是**唯一**沒走 SSOT 的視圖（checkup/dividend/portfolio_health 全走）。
- **修**:戰情室欄改呼 `compute_1y_total_return(f)`（L3 UI → L2 service,合法方向）。有 MoneyDJ perf 者顯示官方 1Y 含息（tier 1）;僅短序列者走年化 fallback（tier 4,≥30d）;真的全無來源才誠實 None（§1）。欄位 help 補述 fallback 鏈（優先官方 1Y／本地含息;不足 1 年以區間年化估算）＝§1 標記。
- **非資料源問題**:user 原以為要「上網找解法」,實為內部 SSOT 不一致（戰情室繞過 fallback 鏈）,非 MoneyDJ/資料源故障 → 純內部修,不需外部研究。
- **回歸網**:`tests/test_mk_dashboard.py` +3 test（ret_1y=None 但 perf 有值 → 取 perf；短序列無 perf → 年化非 None；全無來源 → 誠實 None）。mk_dashboard/app_smoke/portfolio_health 113 passed;全套零破。ruff 對 mk_dashboard 零新增（既有 5 個 E702 分號非本次）。

## 📉 2026-07-11 A~E backlog 批次3(c)（行為改善）：MA60 圖表資料不足提示（v19.344）

user 核准「1~4 陸續慢慢做」。3(c) 取風險最低的行為改善型先做（只修壞掉/靜默的情況,不動已正確訊號）:

- **基金 MA60 圖表靜默消失（修）**:tab2 `s.rolling(60).mean()` 對 <60 NAV 點的新基金全 NaN → `.dropna()` 後 trace 空 = MA60 均線靜默消失、無提示（同檔 MA20/布林已有「資料不足」caption,唯 MA60 漏了）。修:對齊既有 §1 Fail-Loud 模式,<60 點時明講「MA60 均線未繪製 — NAV 僅 N 點,需 ≥60」而非默默省略。**不用動態縮窗偽裝**（縮到 30 點的線標「MA60」會誤導,且與 MA20 概念重疊）。`calc_metrics` 的 MA60 早有 `if len(s)>=60 else None` 守衛,只圖表 trace 漏 — 本修補齊。
- **金融股判定（誤判,不動）**:第八份說股票端「用代號前綴猜金融股」— 實為誤判。`data_loader._is_financial_stock` 已是「`taiwan_stock_info` 產業別欄優先(比對 金融/保險/金控/銀行/證券)→ 28/58 前綴 fallback」,v19.80 N5 還補強過。故 3(c) 僅基金 MA60 一項。
- **回歸網**:`tests/test_review_fixes_v19_344.py` 3 test（MA60 圖表閘門 source-scan + calc_metrics 短序列回 None/長序列回 float 回歸鎖）。
- **A~E 進度**:批次1(止血)✅ / 批次3(c)本次 ✅ / 下一步批次2 時效閘(§8 先設計) → 批次3(a) 標準公式(RSI Wilder/ATR TR,§7 先給數學式) → 批次3(b) 語意項 → 批次4 架構。

## 🔒 2026-07-11 A~E backlog 批次1（止血）：CLAUDE.md §2.1 dataset 正名（A-3）

user 核准「A~E 陸續修復」。基金端本批唯一適用項為文件校正（NAS SSRF 屬股票 repo 的 nas_server.py，基金 infra/proxy.py 僅為 NAS 消費端無 relay server；死碼 fetch_tw_pmi_local/export 有 tab1 caller 不可刪）：

- **A-3 文件正名**：CLAUDE.md §2.1 把已證實不存在的 `TaiwanMacroEconomics` 更正為 `TaiwanBusinessIndicator`（NDC fetcher 已於 v19.342 改走此 dataset）；PMI/出口 fetcher 同掛不存在 dataset、FinMind 無替代集 → 註明現況恆無資料、新源待評估。憲法漂移收斂。
- **A~E 後續**：基金端待落地項為 MA60 min_periods（批次3 公式，§7 先給數學式）、staleness 閘（批次2，§8 先設計）、Put/Call OCC 替代層（卡 user 提供 250 字診斷 trace）、裸 urllib×3 統一連線層、monitored 診斷登錄（批次4 架構）。與股票端同步排程。

## 🛰️ 2026-07-11 資料異常實診修復 + 第八份建議書查證（v19.342）

user 實機截圖回報 tab5 三筆異常(外資買賣超 ARCHIVED 106天 / 雷達9 Put-Call 全源失敗 / SLOOS 延遲 101天 fallback),同輪併入第八份建議書(595 行全面稽核)查證。

- **SLOOS 101 天「延遲」= 季頻靜態閾值算錯(修)**:FRED 季頻 obs 標在季首(SLOOS Q2 調查標 04-01、5 月中旬才發布)→ 下一筆發布前正常最大 age ≈ 92+43 ≈ 135 天;原 95/140 把每季發布前 ~5 週的正常空窗誤判 🟡(101 天實為正常節奏)。修:135/170+推導註(`ui/helpers/io/data_registry.py`)。「fallback」標籤=FRED next_release 對 DRTSCILM 回 None 落靜態閾值 — 動態路徑本身參數正確(`include_release_dates_with_no_data=true` 在場),疑為 FRED 端 SLOOS 排程公布視窗短,不動。
- **外資買賣超 ARCHIVED 永久紅(修,設計補洞)**:根因=v19.47 面板收 ARCHIVED expander 後 fetch 綁在 render 內,不點開就永不更新(v19.152 只補了 tab5 手動鈕)。修:抽 `ui/hot_money.refresh_hot_money_data()` data-only helper(tab5 鈕改薄殼共用)+ `hot_money_is_stale()`(>30 天=AI prompt 排除閾值)+ tab1 長期桶 render 時自動補抓一次(每 session 至多一次,成敗皆標記 — v19.340 AppTest refused-retry 教訓);面板維持封存(v19.47 user 決策不變)。tab5 診斷字串同步改「自動補抓+手動重試」指引。
- **雷達9 Put/Call(據實回報+診斷力修復)**:六層上游確認全死 — Yahoo ^CPC/^CPCE 已下架(production trace「empty len=0」)、stooq 無此標的、CBOE `volume_and_call_put_ratios/*.csv` 為封存檔(資料止於 2019-10,WebSearch 佐證);v19.277 已加的官方 CSV 層在 production 的失敗原因**被 tab5 note 100 字截斷吃掉**(截斷點恰在 stooq trace)→ 修:截斷 100→250,下輪報異常時能看到 CBOE 層真因(HTTP 碼或過舊拒收)再決定 OCC 替代層(未驗證端點不盲上,列待核准)。
- **NDC fetcher 假 dataset 正名(修,§3.3)**:`TaiwanMacroEconomics` 在 FinMind 不存在(SDK 2.0.4 枚舉+官方文件皆無;真名 `TaiwanBusinessIndicator` 寬表含 monitoring 分數/燈號/leading)→ `fetch_ndc_signal_history` 改走新 `_finmind_business_indicator()`,additive `color_latest` 官方燈號欄(schema 驗證僅驗 score/trend,安全);`fetch_tw_pmi_local`/`fetch_tw_export_yoy` 同病但 FinMind 無 PMI/出口 dataset 可換 — 檔頭如實標註,新源設計列待核准。與 stock v19.85 同根因同修法(該 repo 憲法 §2.1 還寫著「TW PMI/NDC:FinMind TaiwanMacroEconomics」— 文件漂移待 user 更新)。
- **第八份屬實項(修)**:app.py `_calc_data_health` thin wrapper 0 呼叫者(真 caller 在 tab1_macro 自帶;tab5 版 v19.339 已刪)→ 刪;tab2 TER 卡「費用每降 1%,20 年後終值多 ~25%」無依據 → 改「~22%＝1.01²⁰ 複利」。
- **第八份不適用清單(證據)**:AUM `fund_scale` 無寫入者=誤判(sources.py:2149/2466+orchestration:705 從 MoneyDJ 基本資料寫入,tab5:1129 有渲染);tab5 §① yfinance 列 hard-wired ⬜=與現行碼不符(已是 `_yf_ok` 動態計數;rows 3-8 共用 `_fund_n` 屬粗粒度「來源已用」表,per-source 健康在 §② registry);positional NAV 解析複製 5 次=已修過(v19.339 起 `_parse_nav_html` 在 sources.py 被引用 9 處);`_FRED_KEYS` 死列=v19.195 已 SSOT 化;holdings/risk 未 import 假綠燈=v19.287-288 已修(報告引用自家 STATE);折溢價/追蹤誤差不適用開放式基金=報告自我校正正確;基金 MA60 min_periods/Sharpe σ 短史=前輪已列待核准。
- **第八份大項待核准**:⭐Put/Call OCC 替代層(等 250 字 trace 看到 CBOE 真因後設計)、⭐裸 urllib ×3(bank_platform/morningstar/yahoo)統一走 fetch_url 連線層、⭐TER 真源(現僅 Allianz 經理費+內建參考均值)、⭐NAV freshness banner 上游值缺(nav_date/_moneydj_fetched_at)、⭐monitored 裝飾器強制診斷登錄(P4 家族)、staleness 閘/data_manager/並行化/UX(前輪已列)。
- **回歸網**:`tests/test_review_fixes_v19_342.py` 15 test(季頻閾值+note 250 掃描 ×2、hot_money stale 判定 ×4、refresh helper 成功寫 stash/失敗保舊 ×2、tab1 once-flag+tab5 共用掃描 ×2、NDC TBI 功能 ×3、app 死 wrapper+TER 依據 ×2)。

## 🔍 2026-07-03 全面稽核待修清單（跨 Tab 稽核）

> Claude 逐檔讀取所有 Tab 後彙整，對照 2026-07-03 真實市場數值確認。
> 修完一項請在前面改為 ✅，並在括號內標版本號。

### 🔴 HIGH（影響判斷正確性）

- ✅ **[H1] Bloomberg RSS 靜默死亡** (v19.295) — `repositories/news_repository.py:61`：移除 `feeds.bloomberg.com/markets/news.rss`，加版本移除說明。

- ✅ **[H2] USDJPY 綠燈 2 年以上沒亮** (v19.295) — `repositories/macro/fred.py:171`：`green_below: 140→148`、`yellow_above: 150→153`、`red_above: 155→158`，反映日銀升息後新均衡。

- ✅ **[H3] Investing.com RSS 封鎖** (v19.295) — `repositories/news_repository.py:54`：移除 `www.investing.com/rss/news_14.rss`。

### 🟡 MEDIUM（資料品質或門檻偏差）

- ✅ **[M1] EURUSD 門檻偏保守** (v19.295) — `repositories/macro/fred.py:170`：`green_above: 1.15→1.10`、`yellow_below: 1.10→1.05`、`red_below: 1.05→1.00`，對齊 2022 後實際區間。

- ✅ **[M2] 中國副盤 CHN_PMI 標籤錯誤** (v19.295) — `services/macro/china.py` `classify_china_regime()` reason 字串全改為 BCI；`ui/tab1_macro.py` China Drag caption 加 BCI 刻度說明。

- ✅ **[M3] AAII 情緒調查抓取脆弱** (v19.296) — `ui/tab1_macro_longterm.py`：AAII.com 因 Cloudflare/JS 渲染持續攔截為已知 best-effort 問題；改善卡片錯誤標籤從 32 字截斷改為明確說明「⚠️ aaii.com Cloudflare 攔截（best-effort，非嚴重）」，底層抓取架構不變（3 段 fallback 已正確 fail-loud）。

- ✅ **[M4] FT RSS 需訂閱** (v19.295) — `repositories/news_repository.py:53`：移除 `www.ft.com/rss/home/uk`（免費版空內容）。

- ✅ **[M5] Tab5 stale 燈號與 Tab1 不同步** (v19.296) — `ui/tab1_macro.py`：Tab1 底部月頻資料截止日列表（PMI/10Y-2Y/HY/CPI/UNRATE）加上 🟢/🟠/🔴 staleness emoji，閾值 ≤45天🟢 / ≤75天🟠 / >75天🔴（對齊 CLAUDE.md §2.4），與 Tab5 資料診斷信號一致。

### ⚪ LOW（邊界設計或 UX 微調）

- ✅ **[L1] MoneyDJ NAV 延遲標示不清** (v19.297) — `ui/helpers/io/freshness.py`：freshness banner 說明文字補充「⚠️ 基金 NAV T+1~T+3 公布屬正常，燈號顯示淨值日期非抓取時間」，消除「🟢剛更新」誤解。



## 專案定位
- **產品**：境外共同基金（保險型保單）戰情室 — TWD 換匯後績效 + 總經訊號 + 危機回測 + AI 策略建議
- **技術棧**：Streamlit + pandas + plotly/altair + FRED / Yahoo / FundClear / Cnyes + Google Sheets + Gemini API + NAS Squid Proxy
- **入口**：`app.py`（Streamlit Cloud 部署）
- **核心禁令**：🚫 全面排除 ETF / 個股，本系統專注共同基金

## 目錄速覽
- `app.py` — Streamlit 主入口
- `services/` — 業務邏輯純函式層（macro / fund / portfolio / AI advisor / screener / risk）
- `repositories/` — 資料抓取層（FundClear / Cnyes / Yahoo / FRED / GSheet）
- `ui/` — Streamlit Tab 渲染層（總經 / 組合 / 單一基金 / 配置模擬 / 組合健診 / 資料診斷 / 說明書）
- `infra/` — OAuth / Proxy / 基礎建設
- `models/` — Pydantic / 領域物件
- `tests/` + 根 `test_*.py` — 單元測試
- `cache/` + `data_cache/` — 落地快取（NAV / FX / 政策 / MJ 快照）
- `scripts/` — 工具腳本（`quick_merge.sh` 等）
- `docs/`、`ARCHITECTURE.md`、`SPEC.md`、`BACKLOG.md`、`STRATEGY.md` — 技術文檔

## 當前版本

- **v19.352 境外基金 NAV 加 CnYES + 安聯境外走 AllianzGI(user 要求「非安聯標的也找源」,2026-07-22)**:
  - **背景**:接 v19.351 後,run #70 顯示 5 檔**境外**(ANZ89/CTZP0/FLFM1/JFZN3/TLZF9)仍全掛 —— Yahoo 用的 Morningstar secId `.F` feed 全 404、MoneyDJ 回 0。`MORNINGSTAR_SECID_MAP` 註解揭露:**TLZF9/ANZ89 是安聯(Allianz)境外、JFZN3 是摩根(JPMorgan)**;CTZP0/FLFM1 未知公司。
  - **修法**:`scripts/fetch_nav_cache.py` 新增 `fetch_cnyes_history`(鏡像 app `_fetch_nav_cnyes`:api.cnyes.com 4 endpoint + `_cnyes_walk_nav_items`/`_cnyes_parse_items` 遞迴解析、寬容欄位名 + Unix ms/s timestamp;**直接用內部碼,無需 ISIN**)——CnYES 為 app 標定的**境外主要來源**,涵蓋 5 檔。境外路由:TDCC → **CnYES(新)** → **安聯境外(TLZF9/ANZ89)走 AllianzGI 原廠 API** → Yahoo → MoneyDJ...。常數 `_ALLIANZ_OFFSHORE_CODES={"TLZF9","ANZ89"}`。
  - **§1/§ SSOT**:抓不到回 [](不偽造);CI 精簡環境不能 import sources.py(拉 streamlit)→ 平行精簡實作(同 v19.351 AllianzGI pattern)。
  - **測試**:`tests/test_nav_cache_coverage_alert.py` 加 3 tests(_cnyes_parse_items 欄位變體+ms timestamp+去重 / fetch 遞迴 nested JSON + 直接用內部碼 / 全空回 [])。**14 tests 全綠**、ci_deps 守門過(無新重依賴)。
  - **待驗**:沙盒測不了 CnYES/安聯站(擋非台灣 IP);需 NAS 代理真實 run 確認。成功則境外 5 檔 NAV 補上,連同 v19.351 境內 6 檔 = 11 檔全解鎖。

- **v19.351 境內基金 NAV 改走 AllianzGI 安聯官網(SITCA 確認死路後換源,user 選 B,2026-07-22)**:
  - **確診(v19.350 探針 run #70)**:`[SITCA] ACTI71 form診斷 … 欄位名=['…ddlQ_YM','ddlQ_Comid','ddlQ_CLASS','BtnQuery'…] 填入(code=False,begin=False,end=False)`。→ **SITCA IN2213 是「投信公司 + 年月 + 類別」下拉月報表頁,根本沒有單檔代碼查詢欄位**——我先前 GET/POST 方向從頭就錯。SITCA 這條**確定死路**。
  - **換源(Explore agent 查證)**:app 抓這些境內基金(ACTI/ACCP/ACDD)的**主力是安聯官網 `_src_allianzgi_nav`**——`https://tw.allianzgi.com/api/sitecore/fund/GetFundNav` POST `{"FundCode":code,"Days":2000}`,**直接用內部碼,無需 ISIN**(CnYES 反而要先 search 解析、較脆)。這些碼是保單平台內部碼,repo 內**無任何 ISIN 對映表**。
  - **修法**:`scripts/fetch_nav_cache.py` 新增 `fetch_allianzgi_history`(鏡像 app 解析:安聯 JSON API 多 body + MoneyDJ yp004002 境內 yp010000;**CI 精簡環境不能 import sources.py——會拉 streamlit——故平行精簡實作**)。境內路由改走它;`fetch_sitca_history` 收成有註記的 skip(記錄「IN2213 公司/月份下拉頁」結論,不再無謂打壞端點)。
  - **測試**:`tests/test_nav_cache_coverage_alert.py` 換掉 3 個 moot 的 SITCA-POST 測試 → 加 3 tests(SITCA 現在 skip / 安聯 JSON API 解析 + 直接用內部碼 / 全空回 [])。**9 tests 全綠**、`test_fetch_nav_cache_ci_deps` 守門過(無新重依賴)。
  - **待驗**:沙盒測不了安聯站(擋非台灣 IP);需經 NAS 代理的真實 run 確認。成功則境內 6 檔長 NAV 解鎖(Sortino/Calmar/3Y/5Y/3-3-3 連帶補上)。

- **v19.350 SITCA POST 觸發 server error → 硬化診斷(接續 v19.349 真實 run,2026-07-22)**:
  - **v19.349 POST 真實 run 結果**:`[SITCA] ACTI71 失敗: 404 …GenericError.html?aspxerrorpath=/ROC/Industry/IN2213.aspx`。→ POST **觸發 ASP.NET server 端未處理例外**(customErrors 轉址 GenericError)——**典型 EventValidation/VIEWSTATE 卡控**(送的欄位組合不被 server 接受)。且因走頂層 except,**沒印到真實欄位名**,仍無法精修。
  - **修法(§5 硬化,不再盲猜)**:`fetch_sitca_history` (1) submit 鈕改**保留頁面 rendered value**(不亂填「查詢」,少一個 EventValidation 破口);(2) **POST 前無條件 dump 真實 form 結構**(action/submit/欄位名);(3) POST 用**獨立 try 接住**,server error 不再吞掉 form 診斷。→ **下次 run 直接拿到真實控制項名**,才能一次修對(或判定 SITCA 太脆換源)。
  - **測試**:`tests/test_nav_cache_coverage_alert.py` 加 1 test(POST server error 仍 dump form 欄位名),**9 tests 全綠**。
  - **決策待 user**:SITCA ASP.NET postback 脆弱;拿到真實欄位名後若仍難搞,**替代方案 = 境內改走 FundClear / CnYES 淨值頁**(app NAV chain 本來就有這兩源在 SITCA 之前)。**app 已顯示這些基金**(靠 MoneyDJ 預算指標),故本 CI 預熱失敗**不影響 app 使用**——優先度由 user 定。

- **v19.349 SITCA 境內基金 NAV:GET→ASP.NET POST 修復(接續 v19.348 探針確診,2026-07-22)**:
  - **確診(v19.348 探針 run #68)**:`[SITCA] ACTI71: 0 筆 status=200 len=36547 __VIEWSTATE=有 日期命中=0 body=SITCA查詢表單首頁`。→ **SITCA 沒擋(status 200)**,是 GET query 參數**不觸發查詢**,回空表單(§確定根因,非猜測)。
  - **修法**:`scripts/fetch_nav_cache.py::fetch_sitca_history` 改標準 ASP.NET postback —— GET 表單頁拿隱藏欄位(`__VIEWSTATE`/`__EVENTVALIDATION`)→ 依「欄位名含 fundcode/begindate/enddate」**通用匹配**填值(自動吃 `ctl00$ContentPlaceHolder1$` 前綴,不寫死)+ submit 鈕 → POST → `_parse_sitca_rows` 解析結果表。抽 `_parse_sitca_rows` helper。
  - **§1 誠實**:抓不到仍回 `[]`(不偽造);**0 筆時 dump form 欄位名 + POST 診斷**供下次精修(§5)。**沙盒無法驗(SITCA 擋非台灣 IP,WebFetch 403),需經 NAS 代理的真實 run 確認欄位匹配命中** —— 不盲稱修好。
  - **測試**:`tests/test_nav_cache_coverage_alert.py` 換掉舊 GET 探針測試 → 加 2 tests(POST 成功解析 + 基金代碼填進 ctl00 前綴欄位 + 隱藏欄位帶回 / POST 後 0 筆 dump 欄位名),**8 tests 全綠**。
  - **待驗 + SSOT 註記**:(1) 下次真實 run 若 SITCA 有料 → 境內 6 檔(ACTI/ACCP/ACDD)長 NAV 解鎖(連帶 Sortino/Calmar/3Y/5Y);(2) app 端 `repositories/fund/sources.py::_src_sitca_nav` **同一個 GET bug**(SITCA 為其 NAV chain 最末 fallback),POST 修法驗證有效後應同步套用(SSOT)。

- **v19.348 NAV cache 診斷:誤導警告修正 + SITCA 探針(user 查 fetch_nav_cache 為何 11 檔幾乎全 0,2026-07-21)**:
  - **背景**:讀 workflow「每日淨值快取更新」(=`fetch_nav_cache.yml`)最新 run(#67)log 發現:PROXY_URL **有設也有生效**(`[proxy] ✅ 啟用 NAS proxy 中繼 chen10021.synology.me:3128`),但 11 檔抓取結果仍幾乎全 0(SITCA 境內 6 檔 0、MoneyDJ 0、Yahoo 404 錯 symbol、僅 TLZF9 10 筆)。**app 本身正常**(用 repository 自己的抓取路徑,與此獨立 script 不同套)——壞的是這支預熱 cache script。
  - **(A) §1 誠實警告**:`scripts/fetch_nav_cache.py::_emit_coverage_alert` 舊版**不論代理有無開都無腦印「PROXY_URL 未生效」**(誤導,proxy 明明啟用)。改為依 `_PROXY_URL` 分流:代理已開→指向「NAS 可達性 / 來源端點改版(SITCA GET→需POST?)」;未開→才提示設 PROXY_URL。return dict 加 `proxy_on`。
  - **(B) §5 SITCA 診斷探針**:`fetch_sitca_history` 0 筆時印真因線索(HTTP status / body len / 是否 `__VIEWSTATE`(ASP.NET postback→GET 恐不觸發查詢) / 是否「查無資料」/ 日期樣式命中數 / body 樣本)。**行為/回傳不變,純觀測**——讓下次真實 run(透過 NAS 代理)定位「空表單需 POST」vs「版型改需換 regex」vs「仍被擋」,再據實精準修。**沙盒無法測 SITCA(WebFetch 也 403),故不盲改硬稱修好(§1)。**
  - **測試**:`tests/test_nav_cache_coverage_alert.py` 加 3 tests(代理 on/off 訊息分流 + SITCA 0 筆診斷探針),7 tests 全綠。

- **v19.347 新功能「🎯 選基金（低基期進場點）」(user 需求,2026-07)**:
  - **需求**:快速找「低基期(現價 ≤ 期間高點 − N×標準差)且不吃本金」的進場候選,幣別/類別可自選。
  - **L2 純函式(`services/fund_screening.py`)**:`compute_low_base(nav, n_sigma, lookback)` 算「高點−N×std」低基期 + σ 深度;`screen_funds(items, ...)` 套低基期/不吃本金/幣別/類別濾鏡 + 去重 + σ 排序。常數 SSOT(`LOW_BASE_LOOKBACK_DEFAULT/MIN_POINTS/STD_EPS`,不 inline)。
  - **§1 Fail Loud**:`std≈0`(NAV 幾乎不動/停售)→ 不判定回 None(不誤判全部低基期);樣本 <60 → reliable=False 旗標。
  - **L3(`ui/tab_fund_grp_health.py`)**:新增 `_render_low_base_screener` + `_eats_principal_flag`(走 `dividend_safety.alert_level` red/green/yellow 語意欄位,不解析 emoji);`_render_health_3tables` 加 `show_screener` 參數——**僅健檢 Tab 顯示**(Tab3 持倉健診不放,避免互動 widget key 撞 + §8.1 不過度設計)。**重用組合健診已抓的 NAV**,零新增外部抓取。
  - **輸出**:σ 倍數(1/2)+回看(1/2/3年)+幣別/類別多選+『只留不吃本金/低基期』勾選;可排序表格(代號/名稱/類別/幣別/現價/高點/門檻/低幾σ/低基期/吃本金/樣本/可信度)+ CSV 下載。
  - **測試**:`tests/test_fund_screener_low_base.py` 14 tests(低基期 True/False、std≈0 不判定、短樣本、空/None/DataFrame、N=2 更嚴、σ 深度、screen_funds 各濾鏡 + 去重 + 排序)全綠。

- **v19.346 修 v2 編輯 UI crash「Expanders may not be nested inside other expanders」(user 回報截圖,2026-07-12)**:
  - **根因**:`ui/helpers/v2_editor.py` 有 2 處巢狀 expander——① `_render_policy_block` 每張保單一層 `st.expander`,而 `render_v2_section` 從 `ui/tab3_portfolio.py:473`「保單管理」`st.expander` **內**呼叫(docstring 明載);② `_render_div_split_estimate` 配息估算 expander 又在保單區塊 expander 內。Streamlit 規則:expander 內任何深度都不得再有 expander → 整個 v2 編輯 UI 載入失敗。只在**有 v2 保單**時觸發(空帳本走 wizard 路徑不含 expander,故先前沒炸)。
  - **修法**:v2 編輯器**整段**都在 tab3 expander 內渲染,故本模組不該用 expander。兩處 `st.expander(...)` 全改 `st.container(border=True)` + 粗體/`####` 標題。外層「📋 保單管理」維持可收合;代價=每張保單改常開外框卡片(不再各自收合)。
  - **架構**:純 L3 UI render 元件替換,零業務邏輯改動;無跨層。
  - **守門**:`tests/test_v2_editor.py::test_v2_editor_uses_no_st_expander` 原始碼層級斷言全模組無 `st.expander(`,防未來再塞回巢狀 expander。11 測試全綠。
  - **備註**:本 container clone 時 main 停在 v19.330,期間 main 已推進至 v19.345(PR #537/#538 等);本修復重置分支到最新 main 後重做,版本接續 v19.346。

- **v19.341 第七份外部 review 查證後修復(Sharpe 分母防 0;多數主張已修過 — 快照在 v19.337/340 前)**:
  - **Sharpe std guard(3-2,真)**:`calc_metrics` 同函式 Sortino(1e-12)/Calmar(1e-9)
    皆有分母防護,**唯 Sharpe 漏** — 常數 NAV(停售/剛成立填平值,§4.6 邊界)
    std=0 → inf/nan 直流 UI。對齊 Sortino 既有 1e-12 門檻,不足回 None(§1)。
    `_ret(n)` 分母同補 >0 guard(第二道防線;入口 pandera 已擋 nav<=0)。
  - **已修過/誤判(證據)**:fetch_nav/fetch_div/fetch_performance「無快取(死 import)」
    =**v19.337 已修**(`@_daily_cache` 三處在場,report 快照舊);「零快取註解矛盾」
    =v19.333 F10 已修;持股/配置「占位式硬寫 🟢 本月」=大部分已修(現行
    `_freshness(monthly)` 真新鮮度路徑在場,僅無日期 fallback 誠實標「已取得
    (無資料日期)」— fallback 用 ⚪ 取代 🟢 屬顯示政策列待核准);
    `calc_hwm_sigma_levels` sqrt(len)=設計而非 bug(precision_service:215 inline
    註解明載「對應 lookback 期間 σ」,改 sqrt(252)=語意變更)→ 待核准;
    組合配置 Tab 序列 vs 健診 ThreadPool=屬實的效能一致性缺口 → 待核准
    (行為/效能變更);reconcile 不阻斷 verdict=屬實但為 v19.9x 設計決策
    (「不影響原 lvl」註解在場)→ assert_reconciled 列待核准;
    turning_points 日曆日 vs 252=語意辯論 → 待核准。
  - **回歸網**:`tests/test_review_fixes_v19_341.py` 4 test(常數 NAV Sharpe=None
    不出 inf / 正常序列不誤殺 / 兩 guard 源掃描)。
  - **大項待核准(§-1 不擅動;⭐=本輪新增)**:⭐`assert_reconciled`(對帳 disagree/
    過期 → 燈降級 🟡,把 reconcile 接進決策鏈)、⭐組合配置 Tab 複用健診
    ThreadPool 模式、⭐診斷主動巡檢+source_trace 一級欄位+保單 ledger/FX
    常態列(P4)、⭐含息雙口徑(複利 vs MK 單利)UI 並列標註、⭐ISM PMI 補
    @_ttl_cache(快取失敗語意需先對齊 v19.337「失敗不快取」原則)、
    ⭐shim 債務 codemod 純刪+normalize_fund_shape 抽共用+risk_radar
    spec-driven(P5)、⭐DataManager(P5 §8 架構案)、⭐surface_anomalies/
    term_glossary(P6)、Session 池化/串行→平行(前輪已列)— 詳 PR 描述。

- **v19.340 第六份外部 review 查證後修復(主聚合入口 NameError + 掃描網 F821 補盲區;UI 崩潰類主張 4 條全已修過或誤判)**:
  - **核心(真,報告 Bug 6 同病灶第三次現形)`fetch_fund_multi_source` NameError**:
    v19.248 拆檔後 `_fetch_fund_single` 已搬 `fund_orchestration.py`,`sources.py`
    頂層從未 import(fund_orchestration L34 頂層 star-import sources → 循環,不能
    頂層補)。**runtime 證實**:呼叫即 `NameError: name '_fetch_fund_single' is not
    defined` — **多來源聚合主入口**每呼叫必炸,被 caller `except Exception: print`
    吞掉 → `fetch_fund_from_moneydj_url`(v2 編輯器新增/更新基金流程)的 Step 2
    多來源聚合 + alt page_type 重試(境內↔境外 mapping 錯誤自救)自 v19.248 全滅。
    修:呼叫端 lazy import(同 v19.339 `_parse_nav_html` 解法)。
  - **掃描網盲區(防再犯的根修)**:`test_undefined_name_scan`(v19.291 user 點名建的網)
    只選 **F405**(star-import 歧義)— F405 僅在模組有 star-import 時觸發,`sources.py`
    無任何 star-import → 本病灶是純 **F821**,防護網完全看不見。擴 `--select F405,F821`
    (F821=確定未定義,直接列違規不需 hasattr 動態驗證);ruff 本來就在
    requirements-dev(v19.291 裝的),0 新依賴。
  - **F821 掃出另 2 顆**:(a) `ui/tab3_t7_ledger.py:2142` 換匯率=0 的 raise ValueError
    f-string 引用懸空名 `_bc`(全檔 0 定義)→ 觸發時先炸 NameError 診斷訊息全毀,改
    `_Bd['ccy']`;(b) `repositories/policy/v1.py` 型別註解 `Iterable` 漏 import(靠
    future-annotations 延遲求值才沒炸)→ 補 `from collections.abc import Iterable`。
  - **已修過/誤判(證據)**:Bug 7 `float("N/A")` 崩潰=v19.331 起 `_safe_float`
    (shared/converters)已鋪 tab5:1083/tab2:414;Bug 8 tab3 資產曲線崩潰=現行整段
    try/except + `len(_s.dropna())<2` 守衛(v18.43 歷史強化);Bug 9 sparkline duplicate
    key=誤判(v19.187 卡片 key 各桶有 `us_`/`zs_` 命名空間前綴,不重複);Bug 10 nan 顯示
    =大宗已由 safe_float 覆蓋,殘餘 `:+.2f` 皆計算分數非抓取值;尾段 18 條 `_fred()` 無
    try=已修過(`_fred_iso`/`_yf_iso` 隔離 wrapper 全鋪);app.py「零快取」docstring=
    v19.333 F10 已更正;tab5 `_FRED_KEYS`/`_calc_data_health` 死碼=**上輪 v19.339 剛刪**
    (報告基準舊);tab5 個股財報監控=已修過(`inactive_label="僅個股查詢觸發"` 非死燈);
    wb01/holdings NameError=v19.287/288 已修(報告自己也註明);FX 4 源診斷/外資
    pandera/breadth 三層備援=報告自評「良好」無主張。
  - **回歸網**:`tests/test_review_fixes_v19_340.py` 7 test(主入口 lazy import scan+
    monkeypatch 跑通 complete/failed 兩路 + provenance / policy v1 Iterable 解析 /
    掃描網 F405,F821 meta-pin / production F821=0 健檢);`test_undefined_name_scan`
    擴選後全綠。
  - **大項待核准(§-1 不擅動)**:例外分類 runtime re-raise(NameError/ImportError fail
    loud — F821 gate 已靜態涵蓋同類,runtime 版有把資料型 AttributeError 誤殺成崩潰的
    風險,建議維持靜態網);`infra/proxy.py` Session 單例池化;基金 13-16 源串行→平行
    競速(5-8× 提速,涉 thread-safety 與快取寫入順序);專題 A 保單代碼優先接
    `fetch_nav_history_long` 6 級長史補 ≥365d 再算含息(資料流變更);1Y 含息 None →
    stale dict(`{"value":None,"stale":True,"reason":...}`)顯示層分級;Sortino 改教科書
    定義/MDD 改還原 NAV 直算(指標語意變更);tab5 FX cache-miss 即時抓取唯讀破口;
    indicator taxonomy 三軸 + `render_smart_metric` + 異常置頂橫幅;術語白話化;
    Tab2/Tab3 合併與健診表格收斂 — 詳 PR 描述。

- **v19.339 第五份外部 review 查證後修復(5 條 Bug 主張:3 修 / 2 已修過或半誤判;另 UI/效能項列待核准)**:
  - **Bug 4(真,本輪最高價值)`_parse_nav_html` NameError 潛伏 ×3**:v19.248 P1-5 拆檔後
    `sources.py` 頂層從未 import 該 fn(定義在 `nav_metrics.py`,且 nav_metrics 頂層
    star-import sources → 循環,不能頂層補)。動態驗證 `hasattr(sources,'_parse_nav_html')
    =False` — `_src_bank_platform_nav`(wb 近30日 fallback)/`_src_tcb_nav`/
    `_src_insurance_subdomain_nav` 三條 NAV 備援一走到解析就 NameError 被外層 except
    吞掉,**拆檔後從未生效**(v19.287 同 class)。修:三函式各補呼叫端 lazy import。
  - **Bug 5(真)Morningstar secId 暫時性失敗永久負快取**:`_morningstar_search_secid`
    except 路徑落到 `_ms_secid_cache[query]=""` — 一次 timeout/403 就讓該基金的
    Morningstar 長史救援(v19.281 span-extend)整個 process 存活期失效,且該 dict 不在
    `_CACHE_REGISTRY`(全域刷新清不到)。修:失敗 return 不入快取(對齊 v19.337
    `_daily_cache` 失敗不快取原則);HTTP 200 查無結果=確定性負結果,保留合法負快取。
  - **Bug 3(半真)DXY 月變化除零**:`us_indicators` DXY 區塊 `(v-m1)/m1` 無守衛且無
    try — m1=0(病態源資料)會炸掉後面所有指標。補 `if m1 else 0.0`(同檔 COPPER/
    cross-rate 既有 pattern)。報告連帶點名的 ADL 其實整塊有自己的 try/except,誤判。
  - **死碼 ×2(tab5)**:16 元素 `_FRED_KEYS` 清單(v19.195 SSOT 遷移殘留,定義後 0 引用)
    + `_calc_data_health` wrapper(本檔 0 呼叫,tab1/2/3 各有自用 wrapper)刪除。
  - **Bug 1 防再犯**:v19.287 根因(star-import 漏綁 → NameError 被 except 吞)已修過;
    本輪補 smoke test 釘住 orchestration 7 個關鍵名字可解析+可呼叫,再漏綁立即紅燈。
  - **已修過/誤判(證據)**:Bug 2 `.iloc[-2]` IndexError — CPI 守衛 round-1 已修,其餘
    指標塊全有 `if len(df)>=2` 前置守衛或 `_fred_iso`/`_yf_iso` 隔離 wrapper,「殺光
    後續指標」結構不存在;「基金 entrypoint 零快取 ~20 round-trip」— v19.337 已把重
    子源(nav/div/perf/risk+holdings)全上 `_daily_cache`,瀑布大頭已消;入口
    `fetch_fund_from_moneydj_url`/`_fetch_fund_single` 本身有 `force_refresh` 參數,
    盲加 TTL 會破壞強制刷新語意 → 列待核准。
  - **回歸網**:`tests/test_review_fixes_v19_339.py` 11 test(TCB/保險子域端到端跑通
    NameError 路徑 / 負快取兩態 / DXY 守衛 / 死碼歸零 / orchestration smoke);
    `test_tab5_data_guard` 原 wrapper delegate 測試改直測 SSOT 純函式(數值斷言不變)。
    全套件 **2,433 passed / 0 failed**。
  - **大項待核准(§-1 不擅動)**:入口 TTL(需定義與 force_refresh 交互)、NAV 瀑布
    ThreadPool race、fetch cycle 級 Session 複用、COPPER/VIX/RRP/TGA 進預熱 pool、
    診斷盲區(AI 呼叫成敗/Sheet 帳本內容/RSS 逐源/熱錢新鮮度燈)、指南針自動抓取、
    Tab2/Tab3 合併、健診表格收斂、sidebar 開發者功能移診斷頁、配息幣別多源 fallback
    — 詳 PR 描述。

- **v19.338 M9 回歸 hotfix:Tab2 `_sh1` NameError(merge 前 CI slow lane 抓到)**:
  v19.336 M9 抽 `_risk_1y_rows_html` 時,`_sh1`(Sharpe 1Y)的定義隨 inline 區塊移入 helper,
  但下游「Sharpe 持久性說明(孫慶龍框架)」仍引用 → NameError(`except (ValueError,
  TypeError)` 接不住)→ Tab2 完整視圖整段炸。補回
  `_sh1 = (risk_tbl.get("一年",{}) or {}).get("Sharpe","—")`。
  驗證:2 個原紅 AppTest(`test_tab2_loaded_fund_with_macro_*` / `test_tab2_nav_source_banner_*`)
  轉綠;全套件 2,422 passed。教訓:slow AppTest 不在本機預設 suite(`-m "not slow"`),
  UI 級重構(抽 helper / 搬區塊)後應主動跑 slow lane 再收工。

- **v19.337 第四份外部 review 查證後修復(4 條新主張:3 修 / 1 誤判;另 ≥4 條已修過/過時)**:
  - **F NAV/配息/績效/風險 4 fetcher 零快取(本輪最高價值)**:`fetch_nav`/`fetch_div`/
    `fetch_performance_wb01`/`fetch_risk_metrics` 每次 render 逐 URL 序列即時抓(每支 25s
    timeout)→ 補 `@register_cache + @_daily_cache`(同 R20 持股先例):NAV T+1、績效/風險/
    配息月更,日內序列不變;R23 cache_if 失敗結果(空 Series/list/dict)不入 cache 無失敗
    黑洞;「全域刷新」經 registry 可清。不選 `_ttl_cache` 因其無條件快取失敗結果
    (§2.4 TTL 對照 trade-off 記於 fetch_nav docstring)。
  - **D cnyes `"data": null`**:key 存在但值為 null 時 `.get("data", {})` 回 None(default
    不生效)→ `None.get()` AttributeError 被寬 except 吞 → fallback 鍵(items)永遠讀不到,
    失敗誤判為無資料。`_cnyes_resolve_code` + `fetch_nav_cnyes` 兩處先判型再取,
    data=null 時 items 可達(測試驗證舊行為丟資料/新行為取回)。
  - **E registry 淨值 source 硬寫 MoneyDJ**:實際可能由 Cnyes 等供應(F-PROV-1 attrs 已帶
    真實來源)→ 基金_/組合_淨值兩處改讀 `s.attrs["source"]`,無 attrs fallback 舊字樣。
  - **誤判(證據)**:4-B-4「真值判斷丟棄合法 0.0 NAV」— §3.1 `nav > 0` 鐵則,NAV=0 非合法
    值(=缺值語意),`0.01<v<100000` 為 §3.2 範圍檢查 by-design;改 `is not None` 反使 0.0
    假值入序列(§1 造假)。**已修過/過時**:tab5 `float()` 崩潰(v19.333 `_safe_float`)/
    yahoo `quote[0]` IndexError(v19.333)/「零快取」話術(v19.333 docstring 已改)/
    持股・績效靜態綠燈無真日期(v19.336 M3 真新鮮度)。
  - **回歸網**:`tests/test_review_fixes_v19_337.py` 8 test(daily_cache 失敗不入快取機制 /
    data=null fallback 可達 / attrs source);全套件 **2,422 passed / 0 failed**。
  - **大項待核准(§-1 不擅動)**:逐基金 ThreadPoolExecutor 平行化、fallback 分級 timeout、
    IndicatorMeta 三軸 SSOT、異常分數引擎、NAV/持股/配息多來源逐源診斷 — 詳 PR 描述。

- **v19.336 第三份外部 review 查證後修復(9 條新主張:6 修 / 1 駁回 / 2 低 ROI 不動)**:
  - **M6 `_src_jpmorgan_nav`**:d_j 為 list 時第一個 `.get()` 先炸 AttributeError,尾端
    isinstance list 分支因短路**永遠執行不到**(dead code)→ 先判型再取;ISIN 取得同守衛。
  - **M7 `search_fundclear`**:裸 `float()` 在單筆 nav="N/A" 時 ValueError **中斷整批**
    (外層 except 包整個迴圈)→ `safe_float` 逐筆容錯,測試:好/壞/好 3 筆 → 舊 1 筆/新 3 筆。
  - **M3 registry 子資料真新鮮度**:前十大持股/產業配置/TER/績效/風險指標 5 條目原
    latest_date 寫死「本月/年度」+硬編 🟢(過期永不亮紅)→ holdings 走 MoneyDJ `data_date`
    (YYYY/MM)真判 monthly、績效/風險走 provenance `fetched_at` 真判 nav(7/14 天);
    無日期時保留原「已取得」行為(§1 不造日期)。
  - **M2 診斷盲點補登記**:(a) `總經_FX_USDTWD` 進 registry 總表(走與 Tab5 標頭同一
    L2 cached 服務,失敗顯 🔴 非靜默缺席);(b) `_進階風險`(maxDD/Sortino/Calmar)
    進 Section② 總表(Section⑤ 逐檔卡 v19.332 已有,總表原缺),NAV 最新日真判。
    (c) AAII/穩定幣註冊 → 列待核准(需跨 3 檔 stash 管線,併入「fetcher 自我登記」架構案)。
  - **M9 tab2 風險卡去重**:partial 視圖 vs complete 視圖兩套同款 flex-div 卡 →
    抽 `_risk_1y_rows_html()` 共用 helper,label_style 保留兩處原標籤差異(行為 0 改)。
  - **駁回/不動(證據)**:M1 tab2 硬索引 KeyError — `mk_fund_signal`/`compute_4d_health`
    皆單一 return 鍵恆全,無缺鍵分支;M4 nav 門檻 10/50/100 不一致 — 屬實但
    `fetch_nav_history_long` **production 0 caller**(v19.314 危機回測退役後懸空),
    §-1 WONTFIX;M5 cache 命中重跑 finalize — docstring 自承 ms 級;M8 Sheets sleep —
    按鈕路徑非 render 熱路徑,auto-load 已有 sheet-id 守衛。
  - **回歸網**:`tests/test_review_fixes_v19_336.py` 9 test;全套件 2,414 passed / 0 failed。
- **v19.335 雲端倒站 hotfix(2026-07-10 11:50 UTC 平台事故)**:
  - **事故**:Streamlit Cloud 平台重啟潮強制 Python 3.14 + **pyarrow 25.0.0 當日發布** →
    本 app 死釘的 `streamlit==1.45.1`(早於 py3.14 支援,啟動即 import pyarrow)
    **進程秒殺 Segmentation fault**(app 程式碼零行執行;股票儀表板同時段同源事故)。
  - **requirements**:`streamlit==1.45.1` → `>=1.59.1,<1.60.0`(**本地全套件 2,404 tests
    本就在 1.59.1 上執行 = 升級預驗證**;連帶把 protobuf/tornado 拉到 cp314 原生 wheel);
    顯式 `pyarrow>=14,<25` cap 回 24.x(當日新版=兇手;解禁條件=25.x 在 cp314 穩定數週)。
  - **回歸網**:`tests/test_hotfix_v19_335.py` 3 test(pin 守護+本地環境=部署目標版本);
    沙盒 pyarrow 對齊 24.0.0 後全套件 2,404 passed / 0 failed。
  - 註:`use_container_width` ×136 處在 1.59 為 deprecation warning 非錯誤,遷移
    留待 user 點(§-1,非本次事故範圍)。
- **v19.334 Tab3 空組合歡迎卡縮小(user 2026-07-10 截圖指示「說明縮小,不需要這麼大」)**:
  - `ui/tab3_portfolio.py` 空組合引導畫面:48px 大圖示+置中 20px 大標+28px padding 整屏卡
    + 3 個 st.info 步驟框 → 收成**單張緊湊卡**(14px 標題行+12px 兩行說明,padding 10px);
    三步驟指引(Tab2 搜尋加入/下方輸入載入/自動出現分析)併入卡內文字,資訊不減、高度約原 1/4。
- **v19.333 第二份外部 review 查證後修復(user 2026-07-10 指派第二份建議書;12 條主張逐條查證:5 修/1 已修過/2 誤判/其餘部分屬實)**:
  - **F2 `_src_yahoo_finance_nav`**:`.get("quote", [{}])[0]` 在 API 回 `"quote": []`(key 在但空)時 IndexError 被外層吞,錯誤訊息誤導 → 顯式判空;`if ts and cl` 的 0 跳過為 by-design(NAV>0 不變量 §3.2)加註。
  - **F4 `_src_alphavantage_nav`**:`float(ohlc.get(...))` 遇 JSON null → TypeError 不在 `(ValueError, KeyError)` 內 → 冒泡丟**整段**序列 → 改 `safe_float`(SSOT),null 只跳該筆。測試:11 筆有效+1 null → 舊 len 0 / 新 len 11。
  - **F5 Allianz MM/DD 年份**:review 主張「12 月資料年初錯置去年」為**誤判**(該語意本來正確),但查證挖出真 bug:`date.today()` 在 Streamlit Cloud 為 UTC,TW 已跨日、UTC 未跨日的 8 小時窗會把當日條目推回**去年同日**(≈365 天錯置)→ 改 TW 時區今日(§4.5),抽 `_infer_year_for_mmdd` 純函式可測;`except pass` 補 log(§1)。
  - **F6 `infra/proxy.fetch_url` session 複用**:原每呼叫 new Session → 連線池零複用,跨國 RTT+TLS handshake 逐請求重付(單基金 fallback 鏈十幾請求)→ thread-local 單例 `_get_thread_session()`(同緒共池/異緒隔離;proxies/verify 逐請求傳入不影響降級直連)。`make_retry_session` API 不變;`test_proxy_infra.py` 加 autouse fixture 清 TLS 快取讓 patch 生效。
  - **F1 tab5 Section ⑤ 裸 float() 防禦**:`float(_d5_nav or 0)`/`float(_d5_adr or 0)` eager 求值,逐檔迴圈無 try 包覆 → 一檔炸=整個 Tab5 炸;現行餵入為強型別(metrics/resolver 皆 float|None)故 review 稱的崩潰**打不到**,防禦性改 `_safe_float`(SSOT)。
  - **F8 完整率語意**:原只數 🟢 → 3🟢1🟡 與 3🟢1🔴 同顯 3/4 → 🟡 以 ½ 計入(0.5 為顯示語意權重)。
  - **F9 Section ⑤ 補 Row 5**:3Y/5Y 年化+6M 報酬(`calc_metrics` 已算未列)+TER 費用率(原僅 Section① 聚合計數);歷史不足顯 N/A(ℹ️)非「缺失」(⚠️),用 `TRADING_DAYS_PER_YEAR` SSOT 判 3Y=756/5Y=1260 門檻(§4.6 新發行基金語意)。review 稱 YTD「已算未列」誤判 — 根本沒算,不動。
  - **F10 app.py docstring**:「零快取」與 `@_ttl_cache`/`@_daily_cache` 事實矛盾 → 更正為實際快取策略描述。
  - **已修過確認**:F3 `_div_n` 複製貼上(v19.331 已修);**誤判確認**:F7 tab5 `_calc_data_health` 有測試 consumer 非純死碼(不刪);F11 組合健診「逐檔序列」stale — v18.219 起已 ThreadPoolExecutor(4) 平行。
  - **回歸網**:`tests/test_review_fixes_v19_333.py` 18 test;全套件 2,402 passed / 0 failed。
- **v19.332 review B 類監控盲區收斂(user 2026-07-10 核准「B+C+D 請繼續」,A 類大重構不動)**:
  - **B6 tab5 Section ⑤ 補 Row 4 診斷格**:最大回撤 / Sortino / Calmar / 基金規模。前三者 `calc_metrics` 一直有算(fund_service.py:599/404/433)只是診斷沒列格;規模為 MoneyDJ `fund_scale` 基本資料字串(原樣顯示前 18 字)。缺值顯 N/A 紅格,不造假。
  - **B7 持股物件統一取值路徑**:新 `_get_holdings(fd)` helper(頂層 `holdings` 優先 → `moneydj_raw.holdings` 補位,對齊 dividends 雙路徑既有精神)。原 Section ⓪(只看頂層)/①(pf 看 moneydj_raw、cf 看頂層)/⑤(只看 moneydj_raw)三處判定不一致 → 同檔基金各 section 計數可能不同(統計偏差),3 呼叫點全收斂。
  - **C 類複查(review 判定不成立項,附證據)**:C9 健康卡 rm NameError main 已修(tab2:791 `_rm` 已定義);C11 投資試算 FX 非每次 rerun 打網路(`repositories/fund/fx_and_main.py` `_FX_CACHE_TTL=300` positive-only cache,5 分內純 dict lookup);C12 診斷 ping verify=False 僅測速場景維持。
  - **回歸網**:`tests/test_review_bcd_v19_332.py` 7 test(helper 三態/頂層優先/None 安全/三呼叫點源碼守衛/Row4 四格與 metrics 契約鍵)+ tab5 相關 29 test 全綠。
- **v19.331 外部 code review P0/P1 修正(user 2026-07-10 指派 dashboard_code_review.md)**:
  - **P1 tab2 partial 視圖 float 崩潰**:`ui/tab2_single_fund.py` MoneyDJ 失敗時 `nav_latest` 常為 "—"/"N/A"/"查無資料"(非 None),原裸 float() 轉型 ValueError 炸整頁 → 改 SSOT `shared/converters.safe_float`(非數值顯示 N/A);同段買賣點 `m.get("nav")`/`near_threshold_pct` 一併防護(數值輸入行為不變)。**review Bug 1(健康卡 rm NameError)已在 main 先修**(現行 791 行已定義 `_rm`),本次無需動。
  - **P1 us_indicators per-series 隔離**:單一 FRED series 例外(pandera SchemaError / IO)原本炸掉 `fetch_all_indicators` → 該指標之後全滅(UI 大面積空白)。新 `_fred_iso`/`_yf_iso` 把 v19.171 五條並行 pool 的 per-future 容錯慣例擴及其餘 16 處 sequential `_fred()` + 2 處 `_yf_s()`(VIX/銅)— 失敗回空 + stderr log,只犧牲該格;repository 層 fail-loud 驗證不動(§1 分層:來源炸、編排局部降級)。
  - **P1 CPI `.iloc[-2]` IndexError**:守衛檢查原始 df 長度(≥14)但 shift(12)+dropna 後 s24 可能 <2 筆 → 補 `len(s24)>=1/2` 雙守衛(對齊同檔 PPI 既有模式),prev 缺時回 None 不造假。
  - **perf RRP/TGA 補進 batch**:`fetch_fred_batch` 清單加 (FRED_RRP,2000)+(FRED_TGA,312)(n 與呼叫點一致 → 同 cache key 命中),淨流動性路徑冷啟動省 2 次串行往返。
  - **次要 tab5 `_div_n` dead fallback**:`_src_cf.get("dividends") or _src_cf.get("dividends")` 對同 key or 自身(筆誤)→ 對齊上一行 pf_loaded 雙路徑語意(頂層 or moneydj_raw)。
  - **回歸網**:`tests/test_review_fixes_v19_331.py` 9 test(單 series 炸不連坐/CPI 病態序列不炸/正常路徑不誤傷/RRP+TGA 進 batch/占位字串防護/源碼守衛);schema gate + tab2/tab5/macro 相關 161 test 全綠。
- **v19.330 修「核心/衛星配置檢查看不到」— 下沉共用 render,兩 tab 齊顯示(user 回報,2026-07-07)**:
  - **根因**:v19.329 只把配置檢查 inline 在**組合配置 Tab3 持倉健診**(需先載入組合);user 在**基金組合健診 Tab**看 → 沒加到 → 看不到。
  - **修法**:配置檢查下沉共用 `ui/tab_fund_grp_health._render_health_3tables`(基金健檢 Tab + Tab3 持倉健診皆呼此)→ 兩 tab 齊顯示。順手把 `_health_rows`(核心/衛星 label 來源)提前建一次,供「配置檢查」+ ① 表共用不重算(原 ① 表段內另建一份,現移除)。Tab3 inline 版移除(改由共用 render 出)。
  - **架構**:分類 label 複用 `build_health_analysis_row`(SSOT),比例走 `summarize_core_satellite_allocation`;純 L3 render 位置調整,無新邏輯。健檢 Tab 全檔 100 萬 = 等權(≈檔數佔比),caption 註明。
  - **回歸網**:asset_class 32 test 全綠(比例邏輯不變);health+report+fund_grp 211 test 全綠。
- **v19.329 組合 Tab3 加「核心/衛星配置檢查」(依投入金額加權 vs 目標 核心 50~80%,user 貼核心-衛星策略表要求,2026-07-07)**:
  - **背景**:v19.327/328 已標每檔核心/衛星;user 貼「核心持股 50~80% / 衛星持股 20~50%」策略表要求對照組合實際配置比例。
  - **算法(SSOT `services/health/asset_class.summarize_core_satellite_allocation`)**:各檔 label(核心/衛星/待定)× weight(投入金額 invest_twd)→ 加權算核心/衛星/待定佔比 → 對照目標(`CORE_TARGET_MIN/MAX_PCT` = 50/80)。燈號:待定 > 30% → ⚪(不可靠);核心 < 50% → 🔴(衛星過重);核心 > 80% → 🟡(過保守);50~80% → 🟢(穩健)。
  - **修法**:(1) `asset_class.py` 加 `CORE_TARGET_MIN/MAX_PCT` + `UNDETERMINED_UNRELIABLE_PCT` 常數 + `summarize_core_satellite_allocation`(L2 純函式,weight≤0/非數略過)。(2) `ui/tab3_portfolio.py` 持倉健診渲染前加「🧭 核心/衛星配置檢查」metric row(核心%/衛星%/待定%/評估燈)+ caption;label 走現成 `build_health_analysis_row`「核心/衛星」欄(SSOT,與 ① 表同源),weight 走 `_principal_twd`。
  - **架構**:L2 純函式 + L3 render,無越權;分類複用現成 SSOT 不重寫。**基金健檢 Tab 未加**(該 tab 全檔統一 100 萬 = 等權,配置比例意義有限);僅組合 Tab3(真實 invest_twd 加權)顯示。
  - **回歸網**:`tests/test_asset_class_core_satellite.py` 加 7 test(加權/綠燈區間/衛星過重紅/過保守黃/待定多白/略過非正權重/空集)累計 32;相關 health+report 全綠。
- **v19.327 健檢 ① 表加「核心/衛星資產」+「基金類別」分類(user 回報「基金總類核心還衛星沒顯示」,2026-07-06)**:
  - **背景**:user 要每檔顯示核心 or 衛星資產。原擬單用 MK 3-3-3(挑核心),但 user 指出「3-3-3 很多檔抓不到」(保單子網域封鎖 → 成立日/3年報酬缺 → 資料不足)。改**兩層 + 來源標記**(對齊 v19.325 配息來源精神)補涵蓋率。
  - **判定順序(SSOT `services/health/asset_class.classify_core_satellite`)**:① 類別命中衛星關鍵字(產業/科技/新興/單一國/高收益…集中主題型)→ 🟠 衛星(角色由類別決定,覆蓋 3-3-3);② MK 3-3-3 通過 → 🟦 核心;③ 類別命中核心關鍵字(全球/平衡/多重資產/投資級債…廣泛分散)→ 🟦 核心;④ 皆無法判 → ⬜ 待定(§1 不亂扣)。關鍵字對照為可調 SSOT。
  - **修法**:(1) 新 L2 純函式 `services/health/asset_class.py`(`SATELLITE_KEYWORDS`/`CORE_KEYWORDS` SSOT + `classify_by_category` + `classify_core_satellite`)。(2) `report.build_health_analysis_row` 讀 `category`(MoneyDJ 投資標的)+ 呼叫分類 → row 加「基金類別」「核心/衛星」「分類依據」3 欄 + `HEALTH_COLUMNS`(排基金名後)。(3) `tab_fund_grp_health` ① 表 column_config 加 3 欄 TextColumn。組合 Tab3 共用同路徑自動同步。
  - **架構**:L2 純函式(zero-IO)+ L3 column_config,無越權。3-3-3 通過但集中型 → 仍歸衛星(角色正確);年輕廣泛型(3-3-3 未達)由類別歸核心(涵蓋率修補)。
  - **回歸網**:`tests/test_asset_class_core_satellite.py`(22:類別判定/衛星覆蓋3-3-3/廣泛型補涵蓋/待定不亂扣/row builder 整合/schema);相關 health+report 212 test 全綠。
  - **v19.328 補**:user 指定「美國成長 = 衛星」→ `成長`(風格)加入 `SATELLITE_KEYWORDS`(成長型追報酬歸衛星);`美國成長` / `科技成長` 等成長型自動歸衛星。剩單一國非成長類(如純「美國股票」)仍待定,可後續再標。
- **v19.326 健檢 ② 表補回「每月配息 (TWD)」金額欄(user 回報「沒看到每月配息金額」,2026-07-06)**:
  - **背景**:v19.324/325 只放了「每月配息**單位數**」,user 貼圖指出沒看到每月配息**金額(TWD)**。SSOT `monthly_dividend_from_records` 早已算出 `mon_div_twd`(= 最近一筆實配 × 持有單位 × 匯率),只是 row builder 沒取出。
  - **修法**:`report.build_dividend_summary_row` 取 `_mdiv["mon_div_twd"]` → row 加「每月配息 (TWD)」欄(排在「年化配息率 %」後、「每月配息單位數」前)+ `DIVIDEND_COLUMNS`;`tab_fund_grp_health` column_config 加 NumberColumn(format `%.0f`)+ numeric coercion。金額與單位共用同一 `source`(配息來源欄真實/估算),缺資料同顯「—」。零新增計算(SSOT 現成值)。
  - **回歸網**:`tests/test_monthly_dividend_units.py`(28)加每月配息(TWD)算式斷言 + column schema 順序(年化→TWD→單位→來源→吃本金);相關 dividend+health+report+portfolio+tab2 377 test 全綠。
- **v19.325 每月配息真實記錄缺 → 年化配息率估算 fallback + 來源標記(user 回報,2026-07-06)**:
  - **背景**:v19.324 全改真實逐筆配息記錄後,user 指出「拿不到就用年化配息率吧,只是要註記來源」—— 加雙層 fallback + 血緣標記,避免保險子網域封鎖時大量顯示「—」。
  - **修法**:(1) `dividend_calc.monthly_dividend_from_records()` 加 `adr_pct` 參數 + 回傳 `source` 欄:真實記錄有 → `source="records"`(最近一筆實配 × 持有單位);無記錄但有年化配息率 → `source="estimate"`(原幣本金 × adr/12,= 持有單位 × adr/1200,nav 約掉);皆無 → None(§1 不捏造)。(2) `report.build_dividend_summary_row` 傳 `adr_pct` + 新增「配息來源」欄(真實/估算/—)進 `DIVIDEND_COLUMNS`。(3) 健檢 ② 表 column_config 加「配息來源」TextColumn。(4) Tab2 投資試算 + `investment.py` 依 `source` 顯示「📊 真實記錄 / 〜 年化估算」註記(估算註明季配/年配某些月實際為 0);Tab2 詳細公式展開 + AI stash 仍限真實記錄(`_has_rec`)。
  - **血緣(§2.2)**:每筆月配數字帶 source 標記,UI 一眼分辨真實 vs 估算,不混用。
  - **回歸網**:`tests/test_monthly_dividend_units.py` 加 source/estimate fallback/nav 無關性/row builder 配息來源 共 8 test(累計 30);相關 dividend+health+report+portfolio 352 test 全綠。
- **v19.324 每月配息改「最近一筆真實配息記錄」— 取代年化÷12 估算(單一基金 / 組合基金 / 基金健檢 三處一併,user 回報,2026-07-06)**:
  - **背景**:v19.323 先以「年化配息率 ÷ 12」前瞻估算加了「每月配息 (TWD)」欄;user 指此估算不夠誠實(季配基金某些月實際=0 卻報平均),要求改**抓最近一筆真實配息記錄**算配息單位數,且**全站三處**(單一基金 Tab2 / 組合基金 Tab3 / 基金健檢)一併換。v19.323 估算路徑整段退役(僅存在分支未進 main)。
  - **算式(真實記錄,SSOT)**:最近一筆實配 d = `dividends[]`(MoneyDJ wh06 真實每筆配息額,原幣/單位)依日期最新一筆;持有單位 u = (本金TWD/fx)/NAV;`每月配息單位數 = d × u / NAV`(A 案);`每月配息(TWD) = d × u × fx`(Tab2 投資試算用)。無配息記錄 → 顯式「—」(§1 Fail Loud,不用 adr 估算矇混)。
  - **修法**:(1) `services/health/dividend_calc.py` 新兩純函式 `latest_dividend_per_unit()`(日期降序取最新 + slash 正規化)+ `monthly_dividend_from_records()`(回 latest/ccy/twd/units 四軸);移除 v19.323 `estimate_monthly_dividend_twd`。(2) `services/health/report.py:build_dividend_summary_row` 加 `fx` 參數 + 算「每月配息單位數」,`DIVIDEND_COLUMNS` 換欄(每月配息 (TWD)→每月配息單位數)。(3) `ui/tab_fund_grp_health.py`:`_render_health_3tables` 傳 `fx=row["fx_spot"]` + column_config。(4) `ui/helpers/fund_grp_health/investment.py` + `ui/tab2_single_fund.py` 投資試算月配息 / 每月配息單位數改真實記錄(含公式展開 + AI stash 同步,無記錄顯示「—」)。
  - **同源覆蓋**:組合基金 Tab3「持倉健診」共用 `process_one_fund` + `_render_health_3tables`(同基金健檢路徑)→ 自動吃到新欄,一改三處齊。
  - **範圍 / 架構**:L2 純函式(zero-IO,fx 以純數傳入)+ L3 傳參,無越權。
  - **回歸網**:`tests/test_monthly_dividend_units.py`(22:latest 取數 / d×u/NAV 算式 / 邊界缺值→None / row builder 整合 / column schema / 舊估算函式已移除);`tests/test_tab2_single_fund.py` metric 卡斷言同步改「每月配息單位數」+ 真實記錄 SSOT。相關 dividend+health+report+tab2 全綠。
- **v19.322 基金組合健診代號去重 — 修「配息事件（多檔合併）」重複列(user 回報,2026-07-05)**:
  - **背景**:user 貼圖「配息事件（多檔合併）」同一基金重複出現。根因:`ui/tab_fund_grp_health.py` 代號清單**無去重** —— 同基金若被多張保單持有,`portfolio_funds`(session)出現同 code 多筆;「🔗 從我的組合帶入」或手動貼多次 → `_run_batch_health` 逐檔各算一次 → 持有 meta / 配息事件 / 比較圖三表全部重複列。
  - **修法(SSOT,兩層互補)**:(1) 新純函式 `_dedup_upper(seq)`(order-preserving + 大寫 + 去空)接在**代號輸入端** —— `_pf_codes`(組合帶入,line 76)+ `codes`(手動處理 chokepoint,line 109);兼省重複網路抓取。(2) 新 `_dedup_rows_by_code(rows)` 接在**顯示層 chokepoint** `_render_health_3tables` 入口 —— 此函式同時被健診 Tab 與 Tab3 組合 embed 呼叫,rows 去重一次覆蓋兩條路徑。本 Tab 輸入僅「代號 + 單一本金」,同 code = 完全相同計算 = 真重複,去重安全。
  - **範圍 / 架構**:純 L3 UI(`tab_fund_grp_health.py`)加 2 純 helper + 3 處接線,無跨層、無資料流改動。
  - **回歸網**:`tests/test_fund_grp_health_dedup.py`(7:代號去重 order-preserving / 大寫去空 / generator 接受 / rows 去重留第一筆 / 空 code 不誤刪 等)。既有 health 103 test 全綠。
  - **驗證**:pre-commit `--all-files` 全綠。

- **v19.321 NAV 快取 Action 覆蓋過低發 GitHub warning — 終結靜默綠勾(user #2 深挖,2026-07-05)**:
  - **深挖結論(修正先前誤判)**:user 問「怎麼讓 NAV 快取涵蓋全部基金」。查證發現**種子機制早已存在** —— `scripts/fetch_nav_cache.py:_discover_fund_codes()` = `FUND_CODES`(11 檔)∪ 既有 cache ∪ Sheet(有 SA 憑證時)。真根因**不是缺種子**:`git log cache/nav/` 顯示每日 Action **數週來只 commit `TLZF9.json` 一檔、且 `source=cache_only`(count 10)** = **fetch 全敗、只重存舊快取,卻仍回綠勾**。因 GitHub Actions 美國 IP 被台灣站點(TDCC/SITCA/MoneyDJ)封鎖,`PROXY_URL` secret 未生效;唯一美國可直取源 `MORNINGSTAR_SECID_MAP` 只涵蓋 3 檔(TLZF9/ANZ89/JFZN3)。
  - **程式修法(§1 Fail-Loud / §5 可觀測)**:新增 `_emit_coverage_alert(summary)` —— 本次抓到新資料(fresh)比例 <50% → 發 **GitHub Actions `::warning::` annotation** + 寫 `$GITHUB_STEP_SUMMARY`,明講「疑似 IP 封鎖 / PROXY_URL 未設」。loop 每檔記 `fresh=bool(new_rows)`。**不 hard-fail**(仍保留既有快取),只讓「每天綠勾卻 0 抓取」的靜默失敗**被看見**。
  - **⚠️ 真正的 unblock 是 user 設定(非程式可解)**:repo Settings → Secrets and variables → Actions 設 `PROXY_URL`(NAS Squid,與 app 同一把)→ Action 走台灣 IP → 11 檔全部抓得到 → v19.319 fallback 才真正有料可退。或補 `MORNINGSTAR_SECID_MAP`(需 user 提供已驗證 secId,不可腦補 §1)。
  - **範圍**:`scripts/fetch_nav_cache.py`(+1 helper、summary 加 fresh、main 尾呼叫)。非 app runtime 路徑,不影響 Streamlit。
  - **回歸網**:`tests/test_nav_cache_coverage_alert.py`(4:低覆蓋發 warning / 高覆蓋不發 / 空 summary 不炸 / 有 GITHUB_STEP_SUMMARY 寫檔)。
  - **驗證**:pre-commit `--all-files` 全綠。

- **v19.320 BTC 流通量常數改「時變（減半發行時程）」— 取代 stale 19.8M(user 檢查選 B,2026-07-05)**:
  - **背景**:user 請檢查 `services/liquidity_engine.py` 的 BTC 供給量常數。診斷:`_BTC_SUPPLY_APPROX = 19_800_000`(註解「~固定」)偏低約 1%、且是 ~1.5 年前(≈2025 初)的值;BTC 供給實為**持續增發**(~+1.6%/年),2026 中約 20.0M。**但**:`build_ssr` 走 Z-score,固定倍率在 `(SSR−均值)/標準差` 中會**被約掉** → 對紅綠燈**訊號零影響**;常數只漏到「顯示的 SSR 絕對值」(~1% 縮放)。屬 §3.3 灰色 + 註解語意誤導。user 選 B(改真實供給)。
  - **修法(B,但用純函式非 API)**:live API 需新 L1 fetcher + 網路 + fallback,且 `liquidity_engine.py` 為 L2(§8.2 不得 I/O)。改以 **Bitcoin 減半發行時程純函式** `_btc_circulating_supply(index)` 推算時變流通量(協定事實、無 I/O、可重現 §5):供給(date)= 最近減半錨點供給 + 天數×該時期日發行量。`build_ssr` 的 BTC 市值改 `btc × 時變供給`(positional 相乘避 tz 對齊問題),推算失敗才退 `_BTC_SUPPLY_FALLBACK`(§1 不靜默)。
  - **效果**:2021→2026 供給曲線 18.75M→20.05M(4th halving 錨點 19.6875M 精確),取代單一 stale 常數。訊號幾乎不變(供給緩增被 Z-score 大幅抵消),但顯示絕對值 + 供給語意變正確。
  - **回歸網**:`tests/test_btc_supply.py`(5:單調且≤21M上限 / 減半錨點值 / 減半後 450/日 / 2026 落 19.9–20.2M / tz-aware index 不炸)。
  - **範圍 / 架構**:純 L2(`services/liquidity_engine.py`)加 1 純函式 + 改 1 處相乘,無新依賴、無跨層 I/O(§8.2 clean)。誠實面:live API 版(即時流通量)未做,ROI 對訊號 ~0,如需再議。

- **v19.319 修 `_src_cache_files` 路徑 bug + 接進 fetch_nav 當 IP 封鎖最終保障(user 指名 item 6,2026-07-05)**:
  - **背景**:GitHub Actions(`scripts/fetch_nav_cache.py`)每日把 NAV 存到 repo 根 `cache/nav/{CODE}.json`,設計為「Streamlit Cloud IP 被 MoneyDJ 封鎖時的最終保障」。但 `repositories/fund/sources.py:_src_cache_files` 有兩個問題:(1) **路徑算錯** —— `__file__.parent` 指到 `repositories/fund/cache/nav`(不存在),永遠讀不到;(2) **死接線** —— 只在 sources `__all__` re-export,沒接進任何 fetch chain(原唯一潛在消費者 `fetch_nav_history_long` 也因危機回測 v19.314 拔除而孤立)。等於這層防護整條沒作用。
  - **修法**:(1) `sources.py` 路徑改 `_Path(__file__).resolve().parents[2]`(= repo 根);(2) `nav_metrics.py:fetch_nav` 在**所有 live URL 失敗後、return 空之前**加快取 fallback —— `_src_cache_files((mj_short or full_key).upper())`,只在 live 全敗時觸發、不覆蓋任何 live 資料,快取自帶 `source`/`fetched_at` provenance(§2.2)。
  - **範圍 / 架構**:純 L1 內修(`repositories/fund/` 同層,`fetch_nav` 呼 `_src_cache_files` 走既有 `sources import *`);additive fallback、live 正常時零行為變化(§8 不改主資料流、只補降級鏈)。
  - **回歸網**:`tests/test_cache_nav_fallback.py`(4 test:路徑指 repo 根讀得到 / 缺檔回空不炸 / live 全敗退快取 / 無快取仍回空)。
  - **⚠️ 現況限制(誠實揭露)**:`cache/nav/` 目前僅 1 檔(TLZF9),Action 用 `glob("*.json")` 只更新既有檔,新基金需先有種子檔才會被每日快取 —— 種子機制為另一獨立議題,本次不處理(§-1)。另 `fetch_nav_history_long` 現已無 live caller(危機回測拔除後孤立),未動,留記錄。
  - **驗證**:pre-commit `--all-files` 全綠。

- **v19.318 標準差買賣點 σ 大改 v3.2「回歸中樞 ± kσ」— 真統計標準差(user A+B,2026-07-05)**:
  - **背景**:user 回報「標準差的圖還沒有修好」(附三合一趨勢圖)。深挖兩個疊加問題:(1) **v19.313(v3.1)有重疊 bug** —— 買點錨年高、賣點錨年低 + σ=(年高-年低)/3 → 數學上 買1=賣2、買2=賣1,6 條線塌成 4 條(程式驗證確認);(2) 螢幕顯示的仍是**舊 v3.0 寬 band**(部署/cache 未刷新),band 橫跨整年高低區間、遠離現價。
  - **修法(user 選 A+B)**:`services/fund_service.py:calc_metrics` σ 公式改 v3.2 ——
    **B**:σ 改「近 1 年淨值的**統計標準差**」(真 standard deviation,`s.tail(252).std(ddof=1)`,隨實際波動縮放,平靜期自動變窄貼價);
    **A**:以「回歸中樞(近 1 年均值)」為中心 **± kσ 對稱佈局** → 6 條線天然不重疊、對稱。買/賣點均錨定中樞;年高/年低改在 Tab2 圖上以**參考線**呈現(區間脈絡,非 band 錨點)。資料<20 筆 fallback 區間中點 ±(年高-年低)/6(仍對稱)。
  - **效果**(平靜基金實測 NAV~75.5):中樞 75.56 / σ 0.48 → band 總寬 **2.87**(舊版年區間式 ~22),6 條線 74.12→76.99 對稱貼價,現價落「正常波動區」。訊號語意:現價偏離中樞幾個 σ → 幾檔買/賣。
  - **連動**:Tab2 圖 hline 標籤 `年高-Nσ`→`中樞-Nσ`、加年高/年低參考線 + y 軸範圍納入;Tab2 σ 卡標題 `v3.1 σ=(年高-年低)÷3`→`v3.2 σ=近1年淨值標準差 中樞±kσ`;`fund_grp_health/signals.py` + `tab1_macro_inflection.py` 標籤/註解同步。倉位 guard 標籤「資料待更新」→「波動極低/待更新」。`std_1y`(年化%)仍供 Sharpe/波動顯示不動。
  - **回歸網**:`tests/test_sigma_band_range.py`(3 test:σ=真統計 std / **6 條不重疊+對稱** / 三檔等距)+ `tests/test_fund_metrics.py`(3 test 改 v3.2 中樞基準 + 不重疊斷言 + 倉位標籤走中樞±kσ)。
  - **⚠️ user 端注意**:部署後需**強制刷新**(側邊欄重抓 / Streamlit「Rerun」或 Clear cache)才會看到新 band,基金指標有 TTL cache。

- **v19.317 系統說明書瘦身 — 砍 4 段純教學區塊(−679 LOC,功能盤點 #3,2026-07-05)**:
  - **背景**:功能盤點 #3 —— user 是專家自用,`ui/tab6_manual.py`(1548 LOC)90% 是真參考文件(公式口徑/資料來源地圖/Sheet 結構,該留),但夾雜大量「新手教學」佔行數大宗又最不會查。user 選力度 A(大瘦身)。
  - **砍除(option A,4 段純教學 + 1 客觀過時)**:section 11 §A「為什麼是這位階」(與總經 tab 重複渲染同一份 `build_beginner_payload`)+ §B「23 指標教學手冊」+ §E「變數重要性 Top-N」;section 12「總經原理教室」整段 render + `_PRINCIPLE_CHAPTERS` 10 章資料(438 行)+ st.tabs 第 12 標籤 + `_PMI_TEXTBOOK`/`PMI_THRESHOLDS` import(砍後無 caller)。**保留** section 11 §C 景氣循環歷史圖 + §D 加扣分明細(即時數據參考)。
  - **客觀修正**:`line 757` 過時引用「之後**危機回測**會優先讀 cache」(v19.314 已拔危機回測)→ 改「系統計算長期報酬 / 健診時會優先讀 cache」。
  - **連動退役**:orphan test `tests/test_manual_classroom.py`(測 `_PRINCIPLE_CHAPTERS`)刪;`tests/test_macro_thresholds_v2.py::test_pmi_tab6_manual_uses_ssot`(守 tab6 PMI SSOT,對象消失)退役;`test_render_..._12_subtabs`→`11_subtabs`;`conftest.py` `_STUB_INSTALLER_FILES` 移除該檔(8→7)。
  - **範圍**:純 L3 UI 減法 + test 同步。無新邏輯、無資料流改動。**驗證**:py_compile + import OK;pre-commit `--all-files`(2287 passed / 8 skipped)。

- **v19.316 總經加「現在能不能買」總結燈(改進 #4-①,2026-07-05)**:
  - **背景**:功能盤點改進 —— 總經頁子視圖多(即時/中期/短線/長期/拐點),user 要「確認位階可買/賣」的一句話結論。既有「雙速合議結論大卡」是分數式,**缺硬衰退訊號安全層**。
  - **修法(user 批准草案)**:新 L2 純函式 `services/macro/action_light.py::macro_action_light(indicators, phase_score_10)` → 🟢 可加碼 / 🟡 持有 / 🔴 減碼 + 理由。邏輯:(1) **硬衰退/恐慌 override** —— 殖利率曲線倒掛(10Y-2Y/10Y-3M<0)/ Sahm≥0.5 / VIX≥30 任一亮 → 強制 🔴(位階再高也蓋,分數卡缺的安全層);(2) 無 override → 依景氣位階 0-10(≥6.5🟢 / 4~6.5🟡 / <4🔴);(3) 位階缺 → 🟡 資料不足(§1 不假綠燈)。`ui/tab1_macro.py::_render_beginner_dashboard` 頂部(結論大卡之前)加彩色 `st.success/warning/error` 一句話燈,純顯示失敗不擋。
  - **門檻 provenance**:`SAHM_RECESSION_THRESHOLD` 走 signal_thresholds SSOT;VIX panic 30 對齊 C2 v19.160 universal;倒掛=利差<0;位階 6.5/4.0 cutoff 為 self-contained 可調常數。
  - **回歸網**:`tests/test_macro_action_light.py`(8 test)守 3 種 override 各自觸發 / 位階 3 級 / 缺分數 unknown / 空 indicators 不炸。
  - **範圍**:新 L2 純函式 + macro `__init__` 匯出 + L3 tab1 頂部渲染 + test。誠實面:位階/機率非精準擇時(燈都附理由)。

- **v19.315 健診加「淘汰候選紅區」— 把 MK 4 換標規則提到最上面(改進 #4-②,2026-07-05)**:
  - **背景**:功能盤點改進項 —— user 要「單一/多檔基金挑出體質差的」,但既有 `check_replacement_recommendation`(MK 4 規則:吃本金≥1年 / 4D Grade F / 3-3-3 未過≥3年 / Sharpe<0且maxdd<-30%)的 verdict 只藏在 ② 配息表「換標的建議」欄裡,不夠醒目。
  - **修法(零新邏輯,只露出既有 SSOT)**:(1) `services/health/report.py` `build_dividend_summary_row` 加曝露 `_verdict`(raw verdict,`_` 前綴不進表格欄);(2) `ui/tab_fund_grp_health.py` `_render_health_3tables` **頂部**加「🔴 淘汰候選 N 檔」`st.error` 紅區,篩 `_verdict=="replace"` 的基金 + 觸發原因,提到 ① ② 表之前。`_div_rows` 上移一次算、紅區與表 ② 共用不重算(SSOT)。
  - **範圍**:L2 report(+1 欄)+ L3 health tab(紅區 + 去重算)+ test。因 `_render_health_3tables` 同時被健診 tab 與組合配置內嵌呼叫,紅區兩處皆顯示(一致)。
  - **回歸網**:`tests/test_replacement_red_zone.py`(3 test)守 `_verdict` key 不消失 / Sharpe<0+maxdd<-30% → replace / 指標全缺 → unknown(不假綠燈)。
  - **驗證**:實測 build row(壞基金→replace、空基金→unknown);pre-commit `--all-files`。

- **v19.314 拔除危機回測室(死功能,−3693 LOC)— 功能盤點第 1 刀(2026-07-05)**:
  - **背景**:user 拿當初 4 個設計初衷(總經位階/單基金體質/多基金金流/組合配置)回頭檢視儀表板,請我點出該改進/刪除的功能。盤點發現 `ui/tab_crisis_backtest.py`(2316 LOC)的 import 自 v19.31 起即**註解停用、進不去**,全 codebase 無第二個掛載點 = **死功能**,且不在 4 目標內。user 確認不用 → 整功能拔除。
  - **刪除(7 檔,−3693 LOC)**:`ui/tab_crisis_backtest.py` + `services/crisis_strategy_grid.py`(291,唯一 caller=死 UI)+ `services/crisis_ai_advisor.py`(191,唯一 caller=死 UI)+ 4 orphan test(`test_crisis_strategy_grid` / `test_crisis_ai_advisor` / `test_tab_crisis_backtest_gating` / `test_dual_signal_routing` —後者測的 AutoSearch routing helper 全數只存在於死 UI,無 live caller)。
  - **保留**:`services/crisis_backtest.py`(`CrisisEvent`/`detect_crisis_events`)—macro `signal_lookback` + calibration `multi_factor`/`signal_threshold` 仍共用,**非**危機回測專屬。
  - **doc-sync**:`app.py` 註解、`shared/converters.py` 過時註解、`ARCHITECTURE.md`(services + ui 樹刪 3 行)、`CLAUDE.md §2.3`(crisis_strategy_grid 參照更新)、`§8.2.A EX-PASSTHRU-1`(2 條 tab_crisis_backtest 例外退役)。歷史 changelog(STATE 舊條目 / BACKLOG F-PIT-1)為史料不動。
  - **驗證**:全庫 0 殘留真 import;保留的 crisis_backtest + 3 消費者 import smoke OK;pre-commit `--all-files`。

- **v19.313 修 MK 買賣點 σ 過寬 — 改「區間基準」(年高-年低)/3(2026-07-05)**:
  - **背景**:user 回報「策略3 標準差買賣點」的 -3σ 買點離現價 18.73%,「怎麼可能差異那麼大」。根因 `services/fund_service.py:325`:`std_amt = 年高 × std_1y/100`,`std_1y` = wb07「一年標準差」=**年化波動率**(~5.5~6.2%)→ 3σ ≈ 年高×3×年化σ% ≈ 18%,**常超出 2 年高低區間** → 買3/賣3 掉出真實區間(買3 比史低還低,永遠觸不到)。同檔註解 `L292`(σ=(年高-年低)/3)+ fallback(/4)本就是區間基準,主路徑卻偷換成年化 σ 才爆。
  - **修法(user 選 ①)**:`std_amt` 改 `(年高-年低)/3`(v3.0→v3.1)→ 買3=年低、賣3=年高,3 檔均分區間,band 必落區間內、訊號必觸得到。`std_1y` 仍保留供 Sharpe/波動顯示。Tab2 標籤 `σ 來源:wb07` → `σ=(年高-年低)÷3`(移除誤導,連帶清 `_m_std_src` unused)。
  - **回歸網**:`tests/test_sigma_band_range.py`(2 test)守 買3≈年低 / 賣3≈年高 / band 不掉出區間 / 三檔等距=σ。
  - **範圍**:L2 `fund_service`(1 公式)+ L3 `tab2`(標籤)+ test;wb07 σ 值計算不動(只是不再拿來當 band σ)。

- **v19.312 布林通道畫不出時明講「資料不足」— §1 Fail-Loud(2026-07-05)**:
  - **背景**:user 回報「布林通道不見了」。排查確認**非 code regression**(布林計算 `fund_service.py:359` / 繪圖 `tab2_single_fund.py:493` 近期均未動,最後改為 v19.283)。根因=該檔 **NAV 序列太短**:布林為 20 日 rolling ±2σ,`rolling(min(20,len)).std().dropna()` 在序列 <21 點時只剩 ≤1 個帶點 → `tonexty` 填色無法成線 → **靜默消失**(淨值線仍在),與健診 4 表同一條「NAV 序列抓太短」根。
  - **修法**:`ui/tab2_single_fund.py` 加 `_bb_drawable = len(_bb_up) >= 2 and len(_bb_dn) >= 2` guard —— 畫得出才畫;畫不出改 `st.caption("⚠️ 布林通道無法繪製 — NAV 歷史僅 N 點,需 ≥21 點…資料不足非故障")`。turns 靜默消失 → 明確告知(§1 Fail-Loud)。
  - **範圍**:L3 UI 單檔;無邏輯/資料改動。真正讓布林回來仍需 NAV 歷史補足(proxy 資料管線)。

- **v19.311 修 NAV 快取 Action 寫檔缺檔尾換行 → 擋後續 PR 的 CI(2026-07-05)**:
  - **背景(連鎖自 v19.309)**:v19.309 bs4 修好後,`fetch_nav_cache` Action **真的成功跑了**並 commit 新 NAV 快取進 main(`1cf6bea`)。但 `scripts/fetch_nav_cache.py:386` `save_cache` 用 `json.dumps(...)` 寫檔**沒補檔尾 `\n`** → `cache/nav/*.json` 缺檔尾換行。Action commit 帶 `[skip ci]` 自己不跑 pre-commit,卻讓**下一個 PR** 的 `pre-commit run --all-files` 判 `cache/nav/TLZF9.json` 缺換行而紅(PR #514 CI 連兩次卡此)。
  - **修法**:(1) 根因 —— `save_cache` 改 `json.dumps(...) + "\n"`(對齊 `update_macro_history.py:367` 既有正確寫法);(2) 修現存 malformed `cache/nav/TLZF9.json`(補檔尾換行)。
  - **範圍**:script + 1 cache 檔;無邏輯改動。與 v19.310 同 PR。

- **v19.310 修健診 4 表多年期/進階欄位全空 — wb01/wb07 保單子網域 + 解耦(2026-07-05)**:
  - **背景**:user 貼健診 4 表(① 健康分析 / ② 配息 / 三籃子 / MK3-3-3 明細),多年期 & 進階欄位(3Y/5Y 年化、3年年化、Sortino、Calmar、同儕排名、Price_Zone/Health_Check/Principal_Erosion)**全 None/N/A/?**。Sharpe 1Y / 成立年 / 1Y 含息**有值** → 證明近一年 NAV + MoneyDJ meta 抓得到,只是 **wb01(3Y/5Y 績效)+ wb07(Sortino/Calmar/排名)沒抓到**,連鎖讓下游全空。
  - **根因**:程式的 fallback 其實都在(`report.py` 已有 wb01 3Y/5Y fallback、`calc_fund_factor_score` 吃 `risk_metrics`),卡在**資料沒進來**。挖到 2 個真 code bug:
    - **Bug A(耦合)** `fund_orchestration.py:427`:wb01 績效巢狀在 `if risk_data:` 內 → wb07 風險一失敗,3Y/5Y 也跟著不抓(即使 wb01 本抓得到)。→ 解耦成兩個獨立 try 區塊。
    - **Bug B(子網域)** `nav_metrics.py`:`fetch_performance_wb01`/`fetch_risk_metrics` 只試 `tcbbankfund`+`www` 兩 host,非合庫保單基金(JF/TL/ANZ/FL 前綴 + 走安達/Chubb 平台的 AC*)全 miss。→ 抽 `_wb_page_urls(code, page)` 比照已驗證的 `fetch_holdings`(L906+)展開:baseline host(tcbbankfund/chubb/taishinlife + www)+ `_INSURANCE_SUBDOMAIN_HINTS` 前綴 portal,路徑用 tcbbankfund 既有 proven 的 `/w/wb/{page}.djhtm`(**不發明 URL**,只把 proven pattern 套到 proven host 集)。
  - **回歸網**:`tests/test_wb_page_urls.py`(8 test)守 baseline host / page 名 / JF·TL·ANZ·FL 前綴展開 / 去重 / 空代碼不炸 / proven path pattern。
  - **⚠️ 覆蓋範圍誠實標註**:Bug B 直接命中 **JFZN3/TLZF9/ANZ89/FLFM1**(前綴有 hint);**ACTI71/ACCP138/ACDD01/ACDD19/ACTI94(AC\*)+ ALBT8(AL)** 前綴不在 `_INSURANCE_SUBDOMAIN_HINTS`,只能靠 `chubb` baseline 碰(AC\* 多走安達/Chubb 平台)。若 AC\*/AL 仍空,需後續識別其 MoneyDJ 子網域再補 hint。
  - **驗證限制**:sandbox 連不到 MoneyDJ,僅驗「邏輯 + URL 展開 + import + pre-commit 綠」;**數字是否真的回填,須在有 NAS proxy 的環境(部署站/本機掛 proxy)驗**。
  - **範圍**:L1 fetcher(`nav_metrics.py`)+ orchestrator 解耦(`fund_orchestration.py`)+ test;無 L2/L3 改動、無 SSOT 新增。

- **v19.309 修每日 NAV 快取 Action `ModuleNotFoundError: bs4`(CI-only,2026-07-05)**:
  - **背景**:user 貼 GitHub Action `fetch_nav_cache.yml` 失敗 run — `scripts/fetch_nav_cache.py:301` 的 Yahoo fallback `from repositories.fund.sources import YF_MORNINGSTAR_CHART_URL` 會拉入整個 `repositories/fund` package,其 module-load 即 `from bs4 import BeautifulSoup`(用 `"lxml"` parser);但 workflow 只裝 `requests pandas gspread google-auth`,漏 bs4/lxml → 半夜 cron 每日炸。根因=排毒重構後 import 鏈長出來、但 workflow 的精簡裝套清單沒跟上。
  - **修法(尊重既有設計,不搬 SSOT)**:`shared/api_endpoints.py` docstring 明定此 URL 常數**留在 `repositories/fund/sources.py`(L1 source-local SSOT)、script 從那 import**(single-caller URL 不上 shared)。故正解=workflow 補裝 import 鏈需要的 `beautifulsoup4 lxml`,**非**改 import 來源。`fetch_nav_cache.yml` pip install 補兩套 + 註解說明為何。
  - **診斷嚴謹度**:模擬 CI 直譯器(擋掉 streamlit/feedparser/yfinance/scipy/… 等 CI 沒裝的重依賴)確認完整缺集=`bs4`+`lxml` 兩個(streamlit 為 `infra/proxy.py:40` try/except 選配、feedparser/yfinance 不在 module-load 鏈)→ **不打地鼠**。另驗 sibling `update_macro_history.yml`(跑 `update_macro_history.py`,import `repositories.macro.fred/yf`)**無同類洞**。
  - **回歸網**:`tests/test_fetch_nav_cache_ci_deps.py`(2 test)— (1) 靜態驗 workflow pip install 含 bs4+lxml;(2) 子行程模擬 CI 精簡依賴驗關鍵 import 仍解析 → 未來 import 鏈長出**新硬依賴**會紅提醒同步 workflow,不等半夜 cron 才發現。
  - **範圍**:純 CI/infra(workflow yaml + test);app runtime 0 改動(APP_VERSION 仍隨版號 lockstep bump 便於書記)。

- **v19.308 成立年改抓 MoneyDJ 現成成立日 — SSOT 一條龍(2026-07-04)**:
  - **背景**:承 v19.307，成立年 / 5Y / Sortino 等仍 None,因 Cloud IP 被 MoneyDJ 擋、本地 NAV 只抓到近 1 月(成立年用 `series.index[0]` → 算成 0.1 年、MK 3-3-3 ① 全誤判)。user 明確要求「**不抓 NAV 歷史,抓 MoneyDJ 已算好的指標**」。
  - **關鍵發現**:MoneyDJ 頁面「成立日期」**部分路徑早已在抓**(`sources.py` Allianz meta),但 (1) 主 moneydj 路徑(yp010000/yp010001,即 user 那幾檔)**沒抓**;(2) 成立年計算用序列而非成立日;(3) `report._compute_holding_years` 已優先讀 inception_date 但沒人餵。
  - **修法(SSOT 一條龍,5 處)**:
    1. `repositories/fund/fund_orchestration.py`:moneydj meta table 補抓「成立日期/設立日期/成立日/基金成立日」→ `result["inception_date"]`(抓不到不設,自動 fallback)。
    2. `services/fund_service.py::finalize_fund_metrics`:`inception_date` 複製進 `metrics`,讓只吃 metrics 的 consumer 也讀得到。
    3. `services/fund_screening.py`:新增 **SSOT 純函式 `fund_inception_years(inception_date, series)`**(成立日優先、序列 fallback、<90 筆且 <0.5 年 → None 不硬報);`check_333_fund` C1 改讀 `metrics["inception_date"]`。
    4. `ui/components/mk_dashboard.py::_fund_age_years` 改 delegate 同 helper。
    5. `services/health/report.py::_compute_holding_years` 改 delegate 同 helper(消除第三份重複實作)。
  - **SSOT 保證**:成立年**只剩一個演算法** `fund_inception_years()`,3 consumer(3-3-3 / 健診 / 戰情室)全走它;成立日只從 fetcher 抓一次進 result→metrics。
  - **安全 / Fail Loud**:抓不到成立日 → fallback 回序列(= v19.307 現狀,不更糟);序列過短且無成立日 → None(顯示「資料不足」而非誤導的「0.1 年 ❌」)。
  - tests:新增 `tests/test_fund_inception_years.py`(8 tests:成立日優先 / ISO 解析 / 長序列 fallback / 短序列 None / 壞格式 fallback / 雙缺 None / check_333 短序列+成立日→通過 / 短序列無成立日→資料不足)。既有 dedup + enriched 測試續綠(17 全綠)。
  - **⚠️ 需 live 驗證**:MoneyDJ 頁面「成立日期」欄是否存在、Cloud 上抓不抓得到,sandbox(403)無法測。程式照現有 pattern 寫 + fallback 安全,最終須 user reboot 後在線上確認成立年有無跑出真值。
  - **下一步**:merge main + user reboot + 重載 → 成立年應顯示真實年數(3-3-3 ① 對老基金通過);若仍 None 代表該頁無成立日欄,再評估改抓 wb07 風險頁 Sharpe/標準差。

- **v19.307 Tab3 分析表大量 None 根治 — 載入改走 L2 enriched wrapper(2026-07-04)**:
  - **背景**:user 截圖回報「組合配置 / 組合健診」多張分析表大量欄位 None、與現實不符——核心戰情室連「目前市價」都 None;① 健康分析表 Sharpe/Sortino/Calmar/MaxDD/5Y 全 None;3-3-3 成立年全 0.1 年。
  - **根因(regression)**:R8(commit `fdbfb55` / PR #457)把 L1 orchestrator 的 `calc_metrics` 上提 L2 `finalize_fund_metrics`,只有 `_enriched` wrapper 會呼叫它。但 **Tab3 批次載入器 `ui/helpers/portfolio/load.py:172` 與 `ui/helpers/d_mode.py:100` 這兩個 caller 漏遷移**,仍呼叫 raw `fetch_fund_from_moneydj_url`(`result["metrics"]` 永遠 `{}`)→ 所有讀 `metrics` 的欄位 None。**「目前市價」None 是鐵證**(有 series 一定算得出,除非 metrics dict 空)。
  - **修法**:兩 caller 改 import `services.fund_service.fetch_fund_from_moneydj_url_enriched`(= raw + `finalize_fund_metrics`)。方向 L3 UI→L2 service(比原 L3→L1 直呼更合規);`finalize_fund_metrics` 無 `st.*`、thread-safe,可在 ThreadPoolExecutor 內跑。**同時實現 user 要的「MoneyDJ 優先、無資料才自算」**:`finalize` 用 `risk_override`(=MoneyDJ risk_metrics)覆蓋自算值。
  - **仍為 None 的部分(§1 Fail Loud,非本次可解)**:成立年 / 5Y年化 / Sortino(需≥60筆) / Calmar(需3Y) 需**長 NAV 歷史**;Streamlit Cloud IP 被 MoneyDJ/子網域封鎖 → 長歷史源全敗、退到近 ~30 日 nav 頁(series ~0.1 年)。這些欄位無足夠資料時顯示 None/資料不足是**正確的、不該假造**。若要根治需讓 Cloud 端抓到長歷史(NAS proxy)或改讀 MoneyDJ 成立日/wb07 預算值——屬後續資料源工作,已與 user 對齊。
  - tests:新增 `tests/test_fund_load_enriched.py`(7 tests:2 caller 走 enriched 守門 + `finalize_fund_metrics` 正常 series 產 metrics(含 nav) / 短 series 不假造 / None series 安全)。既有 `test_portfolio_load.py` 15 tests 續綠。
  - **下一步**:merge main + user reboot + 重新載入 → 核心戰情室「目前市價/波動/σ 帶」、健診表 Sharpe(資料夠時)恢復;長歷史欄位視 Cloud 能否抓到長 NAV 而定。

- **v19.306 MK 3-3-3 批次篩選明細表去重 — SSOT 一檔一列(2026-07-04)**:
  - **背景**:user 截圖回報 Tab3「MK 3-3-3 原則批次篩選 → 展開 3-3-3 評估明細」表出現重複列(JFZN3 / ACCP138 各兩次),底部「共 25 檔」統計含重複。
  - **根因**:同一基金可跨多張保單存在於 `st.session_state.portfolio_funds`(policy schema 主鍵為 `(policy_id, fund_url)`,同基金不同保單合法各一筆)。`services/fund_screening.py:batch_333_funds()` 逐檔建列**未去重** → 明細列 + 「共 N 檔」統計灌水。
  - **修法(SSOT 去重)**:在 `batch_333_funds()` 迴圈加 `_seen_codes` set,以 code 一檔一列、保留首次出現順序。3-3-3 評估的是**基金內在屬性**(成立年 / 3年年化 / 同儕排名),同基金跨保單重複列 = 完全相同的雜訊,收斂為 SSOT 一檔一列。
  - **為何去重放 L2 服務層而非 UI / 源頭**:(1) `batch_333_funds` 是產出這張表的唯一 SSOT,去重放這裡則所有 caller 自動乾淨,不散落 UI;(2) **不可**在 `portfolio_funds` 源頭去重——組合層投入金額 / 配置需保留跨保單重複,只有基金內在分析才去重。
  - **架構合規**:純 L2 service 內部邏輯,公開 signature / 回傳欄位不變;唯一 caller `ui/tab3_portfolio.py` 無需改動。
  - tests:新增 `tests/test_fund_screening_dedup.py`(4 tests:重複收斂+順序保留 / 統計反映去重檔數 / 無重複行為不變 / 空 list)。4 綠。
  - **下一步**:merge main + user reboot → 3-3-3 明細表一檔一列,「共 N 檔」統計正確。

- **v19.305 Google 登入迴圈根治 — OAuth state 檢查放寬(2026-07-04)**:
  - **背景**:user 回報「已登入卻顯示沒登入、一直迴圈」,並指證「掃毒減肥前都能登入,之後才壞」。git 歷史逐 commit 比對確認為 **regression**:本檔 `852cfb1`(第四階段 deep refactor 建檔)登入邏輯**無 state 檢查、可正常登入**;`dff0c41`(v19.301「fix OAuth state strict check」)加上嚴格檢查後才壞。
  - **真根因**:v19.301 把守門改為「只要 URL 帶 state 就必須與本 session 的 `_oauth_state` 完全相符」。但 **Streamlit Cloud 在「整頁導去 Google 再導回」時會把本 session 重置成全新 session** → `_oauth_state` 遺失成 `None` → 回傳 state 與 None 永遠不符 → `handle_oauth_callback()` 每次都 early-return、不換 token → `gsheet_tokens` 永遠沒設 → 側邊欄一直顯示「用 Google 登入」→ 無限迴圈。(**訂正 v19.304 note**:當時判為「純平台攔截、程式端無可再改」,實為此 code regression,可修。)
  - **修法(中間解,可用性優先 — user 明確選擇)**:守門判斷抽成純函式 SSOT `_should_reject_oauth_code(expected, got)`,規則改為 `bool(got and expected and got != expected)` —— **只有「本 session 確實記得發起過 OAuth(expected 有值)且 state 不符」才拒**;`expected` 為 None(session 於導回遺失)時**放行**換 token。仍保留 session_state 存活時的跨 session 防搶碼保護。
  - **取捨(已向 user 揭露並取得同意)**:放行 None 會重新打開「殘留/多分頁互相搶授權碼」窗口(v19.301 的修補對象)。但單一使用者情境下最壞只是自我踢除、可重按,遠優於「永遠登不進去」。
  - **SSOT / 架構合規**:決策收斂單一純函式 `_should_reject_oauth_code()`(可單元測試、不需 streamlit);純 L3/helper 層改動,無跨層 import、無新 §8.2.A 例外。
  - tests:新增 `tests/test_oauth_callback_state.py`(7 tests:失憶放行 / 相符放行 / 雙值不符拒 / 無 got 放行 / 雙 None 放行 / 空字串放行 + wiring 守門接上 callback)。既有 `test_app_apptest.py` oauth/refresh 2 tests 續綠。
  - **下一步**:merge main + user reboot app → 重按「用 Google 登入」即可成功進 Tab3 讀 Google Sheet。(Service Account 仍是更穩的長期選項,但非必要;user 選擇留用既有 OAuth。)

- **v19.304 多基金績效比較圖「資料都是 0」根治 — 圖表基準自適應(2026-07-04)**:
  - (版號說明:原記為 v19.303,因 main 平行 UI 線已用 v19.303「trend arrows」,依本 session 撞號改號慣例 bump v19.304 避免混淆。)
  - **背景**:user 截圖回報組合健診 Tab「📊 多基金績效比較」圖 + 比較表三軸(配息率/含息/淨值)全 0.00%,但上方②③健診表同 3 檔(TLZF9/JFZN3/ACTI71)明明有值(全期實際配息率 4.62%/5.53%/4.79%、年化配息率 9.09%/11.01%/9.49%)。user 誤以為資料來源掉了(「請連上網找資料來源」),實為內部欄位讀錯。
  - **真根因**:v19.180 把績效欄拆「(年化)」+「(全期實際)」兩套;比較圖 `ui/tab_fund_grp_health.py` **寫死只讀「(年化)」**欄。年化欄依 `dividend_calc.MIN_YEARS_FOR_ANNUALIZE`(SSOT=`shared/signal_thresholds.py`=0.5)在**持有 < 0.5 年**時一律回 `None`(防「短期配息 × 倍數」年化幻象,§1 Fail Loud)。同保單同期買進的多檔常整排短歷史(截圖 3 檔配息 6 次 ≈ 5-6 個月)→ 年化全 None → 圖表 `float(None or 0)` 畫成**全 0 空圖**。資料一直都在(全期實際欄),只是圖讀了「合法為空」的那欄。
  - **修法(基準自適應,§1 不造假)**:新增純函式 SSOT `_pick_comparison_basis(rows)` — 全檔都有年化值(皆 ≥ 0.5 年)→ 用「年化」(跨檔可比、原設計);**任一檔短歷史 → 全圖退「全期實際」**(100% 真實累計、永遠有值、不年化)。基準對整張圖統一(不同圖混基準),標題/圖例/新增 caption 明示當前基準;< 0.5 年時 caption 說明「改以全期實際呈現真實數據」。比較表同步跟隨基準。
  - **SSOT / §3.3 反捏造**:基準決策收斂為單一 `_pick_comparison_basis()` 純函式(可單元測試,不需 streamlit);0.5 年門檻續留 `shared/signal_thresholds.py` 不複製;無 inline magic number。
  - **架構合規**:純 L3 UI 層改動;L2 `dividend_calc` 欄位契約不動(仍同時吐兩套欄);無跨層 import、無新 §8.2.A 例外。
  - tests:`tests/test_grp_health_bugfixes.py` 改 `TestPerfChartKeys`(對齊 f-string 自適應鍵)+ 新增 `TestComparisonBasisPicker`(3 純函式 test:全年化→年化 / 任一短歷史→全期實際 / 單檔部分 None→全期實際)。9 + 44(dividend_calc)測試全綠。
  - **下一步**:部署後 user 重看多基金比較圖,短歷史組合會顯示「全期實際」真實數據(不再全 0),並有 caption 說明基準。
  - **另 Google Sheet 登入迴圈**:user 本輪同時反饋「已登入但 Google Sheet 一直迴圈」。此為 **Streamlit Cloud 平台自身登入 vs app 內 OAuth 先天衝突**——OAuth 導回 `*.streamlit.app` 被平台攔截,token 存不進 session → 面板一直顯示「尚未登入」→ 迴圈(main v19.301 嚴格 state 驗證修的是 token 被別 session 搶,非本迴圈)。**唯一可靠解仍是 Service Account**(headless、免登入),需 user 完成 4 步平台設定:① GCP 建 SA + 下載 JSON;② 把 Sheet 分享給 SA `client_email`(編輯者);③ Streamlit secrets 加 `[google_service_account]` + `POLICY_SHEET_ID`;④ reboot。程式碼端(Tab3 優先 SA)已備妥,無可再改處。

- **v19.301(2026-07-04)**:修復 OAuth 搶帳號漏洞（嚴格 state 驗證）:
  - **根因**:`handle_oauth_callback()` 舊版「若本 session 無 `_oauth_state` 則退回放行」邏輯，會讓任何未啟動 OAuth 的分頁（全新 tab / server 重啟後殘留 session）接受別的 session 的 `?code=` 授權碼，導致擁有者帳號登入後被其他 session 搶走 token。
  - **修法**:`ui/helpers/io/oauth_state.py` — 條件 `if _expected_state and _got_state and _got_state != _expected_state:` 改為嚴格版 `if _got_state and _got_state != _expected_state:`：只要 URL 帶了 state 參數，就必須與本 session 的 `_oauth_state` 完全相符，不再有「無 state 時放行」的 fallback 漏洞。
  - **退化處理**：server 重啟後 session 遺失 → user 重按登入按鈕即可，是可接受行為。
  - `app.py` APP_VERSION 更新至 v19.301。

- **v19.298(2026-07-03)**:MK 3-3-3 殘留根因修復 — inception_date 優先 + wb01 3Y fallback:
  - **背景**:user 反饋「某基金成立超過 3 年但 MK 3-3-3 仍顯示不行」。v19.291 已修 timedelta 窗口(400→2000天),但仍有 2 個獨立根因未解:
    1. **`tab_fund_grp_health.py` 成立年數計算只用 NAV 序列首日**:保險子網域代碼（如 JFZN3）在 Streamlit Cloud 上因 IP 封鎖拿不到 MoneyDJ 保險子網域歷史 NAV → 序列短 → 首日偏新 → `_yrs_inc` 算出 < 3 年，即使 inception_date metadata 已在 FundClear/AllianzGI 抓到正確成立日也完全沒用到。
    2. **`ret_3y_ann` 沒有 wb01 fallback**:NAV 序列 < 756 筆時（序列太短），`calc_metrics` 算不出 `ret_3y_ann`，但 MoneyDJ wb01 的 "3Y" 欄位（三年累計報酬率）早已抓到且存在 `fd["perf"]["3Y"]`，卻從未被 `tab_fund_grp_health.py` / `services/health/report.py` / `services/health/replacement.py` 讀取當 fallback。
  - **修法（三處一致）**:
    - `ui/tab_fund_grp_health.py`：成立年數加 Priority 1 = `fd.inception_date` / `fd.moneydj_raw.inception_date`（鏡像 `_compute_holding_years` SSOT 邏輯），原 NAV 首日計算降為 Priority 2 fallback；`_ann_3y` 在 metrics + ret_3y_cum 兩段 fallback 後再加 `fd.perf["3Y"]` 累計→年化 (1+c)^(1/3)-1。
    - `services/health/report.py`：`ret_3y_ann` 在 metrics + ret_3y_cum fallback 後再加 wb01 `fd.perf["3Y"]` fallback（同公式）。
    - `services/health/replacement.py`：`_ret_3y_ann` 同樣加 wb01 `fd.perf["3Y"]` fallback，確保換標的建議規則 (c) 使用相同的 3Y 年化數字。

- **v19.297(2026-07-03)**:LOW 稽核修正 + 全面重新確認:
  - **[L1] NAV 延遲標示**：`ui/helpers/io/freshness.py` freshness banner 補充「⚠️ 基金 NAV T+1~T+3 公布屬正常，燈號顯示淨值日期非抓取時間」說明。
  - **[新發現] Yahoo Finance RSS 死亡**：`repositories/news_repository.py` 舊 URL `rss/2.0/headline?s=%5EGSPC`（回傳空）→ 改用 `news/rssindex`（實測有效）。
  - **[新發現] USDCNH 門檻更新**：`repositories/macro/fred.py` `green_below: 7.0→7.1 / yellow_above: 7.15→7.3 / red_above: 7.3→7.45`，與 Stock USDCNY 門檻更新同步對齊離岸人民幣實際區間。
  - 全面重新確認：RSS feeds 5 來源（MarketWatch/Yahoo/CNBC×2/BBC），Reuters/Bloomberg/Investing/FT 已正確移除；USDJPY/EURUSD 門檻（v19.295 已修）；CHN_BCI 標籤（v19.295 已修）；Tab1 staleness emoji（v19.296 已修）。

- **v19.296(2026-07-03)**:稽核修正（AAII 錯誤標籤 + Tab1 staleness emoji）

- **v19.295(2026-07-03)**:HIGH + MEDIUM 稽核項目修正:
  - 移除死亡 / 封鎖 RSS：Bloomberg Markets / Investing.com / FT Markets（`repositories/news_repository.py`）
  - USDJPY 門檻更新：`green_below: 140→148`（日圓 2022 年後不再低於 140）
  - EURUSD 門檻更新：`green_above: 1.15→1.10`（2022 後歐元走弱新均衡）
  - 同步更新 Tab5 / Tab6 / data_registry.py 來源描述（移除已刪 feeds，8→5 來源計數）
  - **[M2] CHN_PMI→CHN_BCI**：`services/macro/china.py` reason 字串全改 BCI；`ui/tab1_macro.py` China Drag caption 加 OECD 刻度說明
  - **[M4] FT RSS**：已含在 v19.295 同批移除

- **v19.294(2026-07-03)**:Stale description strings — Tab5 / Tab6 / data_registry.py 仍顯示「Reuters」於 RSS 來源說明:
  - `ui/tab5_data_guard.py`:RSS 來源描述更新為 "MarketWatch / FT / Yahoo / Investing / CNBC × 2 / BBC / Bloomberg"
  - `ui/tab6_manual.py`:同步移除 Reuters，補上 BBC / Bloomberg
  - `ui/helpers/io/data_registry.py`:source 字串 "Reuters/MarketWatch/FT/Yahoo/Investing/CNBC" → "MarketWatch/FT/Yahoo/Investing/CNBC/BBC/Bloomberg"

- **v19.293(2026-07-03)**:Bug fixes — dead Reuters RSS 移除 + Tab5 build_signals kwarg 修正 + APP_VERSION 字串更新:
  - `repositories/news_repository.py`:移除 3 個 `feeds.reuters.com` RSS feed (Reuters Business / Reuters Markets / Reuters Top News),自 2020 年 6 月起全部 404,每次新聞抓取白費 timeout
  - `ui/tab5_data_guard.py`:修正 `build_signals()` 呼叫的 kwarg 名稱 (`flow_thr_yi`→`flow_thr`, `fx_thr_pct`→`fx_thr`)，消除 TypeError
  - `app.py`:APP_VERSION 字串從 `v19.45_MacroNavigator` 更新為 `v19.293_MacroNavigator`

- **v19.291 MK 3-3-3「成立 0.1 年」誤判根因 + 全站自動掃描機制(2026-07-01)**:
  - **背景**:user 截圖 JFZN3(摩根投資基金-多重收益基金 A 股)在本站 MK 3-3-3 顯示「❌ 成立 0.1 年 <3 年」,但同時提供 MoneyDJ 官網截圖證實該基金淨值歷史實際橫跨 2021/10/15~2026/06/29(近 5 年)。user 另外要求:「額外寫一個『自動檢查』的機制,以後如果又有人漏搬東西,測試會直接抓出來,不用等到你在正式環境上踩到才發現」(涵蓋資料一致性 + 程式碼健康兩面向)
  - **真根因**:v19.281 曾把 cnyes(`_src_cnyes_nav`)/ Morningstar(`_src_morningstar_nav`)的查詢窗口從 400 天(~13 月)延伸到 2000 天(~5.5 年),但**直接對 MoneyDJ 本身**(`yp004002.djhtm` 帶日期 A/B/C 三參數)的呼叫點漏做同樣延伸。實際 grep 全站 `timedelta(days=400)` 共 9 處全部殘留短窗口:`repositories/fund/sources.py` 7 處(`_src_fundclear_nav` / `_src_bank_platform_nav` / `_src_taiwanlife_nav` / `_src_franklin_nav` / `_src_tcb_nav` / `_src_sitca_nav` / `_src_insurance_subdomain_nav`)+ `repositories/fund/fund_orchestration.py` 2 處(`_fetch_fund_single` 的「2d. www.moneydj.com 主站」分支 + `fetch_fund_from_moneydj_url` 的「再查詢整年歷史」分支)。保單代碼(如 JFZN3)常見經這些直接 MoneyDJ 路徑取數,查詢窗口太短 → 只抓到近 1 個月資料 → `_compute_holding_years` 算出 0.1 年
  - **修法**:9 處 `timedelta(days=400)` 全改 `timedelta(days=2000)`,對齊 v19.281 cnyes/Morningstar 已做的窗口延伸,每處附註解說明沿革
  - **自動檢查機制(user 明確要求,兩面向都要)**:
    1. **資料/邏輯回歸網**(`tests/test_nav_history_window.py::test_direct_moneydj_nav_fetchers_use_2000d_window_not_400d`):直接檢查 9 個已知呼叫點的原始碼,任一處殘留 `timedelta(days=400)` 就 fail,防止之後重構/合併衝突時被意外改回短窗口
    2. **全站程式碼健康掃描**(新檔 `tests/test_undefined_name_scan.py`):v19.287/288 那 6 個真 bug(`fetch_holdings`/`fetch_risk_metrics`/`fetch_performance_wb01`/`fetch_nav`/`_BANK_PLATFORM_CODES`/`_MORNINGSTAR_SECID_MAP`)本質都是「模組內呼叫了某個名字,但這個模組從未真的 import 這個名字」——`NameError` 被外層 `except Exception: print(...)` 吞掉,production 上只看到資料靜默消失。新測試用 `ruff --select F405`(possibly-undefined-name-from-star-import)全站掃 `repositories/services/ui/infra/shared/app.py/fund_fetcher.py`,對每筆命中動態驗證該名字是否真能在對應模組命名空間解析(`hasattr`),解析不到就直接 fail 並列出檔名+行號+名字
    - **開發過程 2 個自我驗證抓到的實作 bug**(用「刻意打壞已知正確檔案 → 確認新測試真的抓到 → 修正 → 再確認正確」流程驗證,不只是理論上寫完就信任):① `ruff` 在本環境是獨立編譯執行檔(console_script entry point),`python -m ruff` 會印「No module named ruff」到 stderr、stdout 留空,若沒接住這個 failure mode,`json.loads("" or "[]")` 會靜默當「0 個 finding」,整個測試形同虛設——改直接呼叫 `ruff` binary(靠 PATH),並加 `if not proc.stdout.strip(): raise AssertionError(...)` 明確區分「ruff 沒真的跑」vs「真的 0 個 finding」(後者 ruff 實際輸出非空字串 `"[]"`)。② 一開始用 `importlib.import_module()` + `importlib.reload()` 驗證,但 `reload()` 會就地替換 `sys.modules` 裡的真實模組物件,導致其他模組手上舊的 function reference 跟 reload 後的新物件不再是同一個 object,直接弄壞既有測試 `test_fetch_holdings_is_actually_importable_in_fund_orchestration` 的 `O.fetch_holdings is NM.fetch_holdings` 身分斷言——改用 `importlib.util.spec_from_file_location` 建一份「用完即丟」的隔離模組,驗證完不論成功失敗都把 `sys.modules[modname]` 還原成呼叫前狀態,對其他測試完全無副作用
    - `requirements-dev.txt` 新增 `ruff>=0.15`(CI 環境需要能 `ruff check` 才能跑這個測試)
  - tests:`tests/test_undefined_name_scan.py`(新檔,1 test)+ `tests/test_nav_history_window.py` +1。組合套件(`test_undefined_name_scan.py` + `test_nav_history_window.py` + `test_fetch_holdings_fallback_chain.py` + `test_fund_health_report.py`)35 個全綠;用「刻意打壞 `fund_orchestration.py` 的 import → 確認新測試正確抓到 7 個壞點且不波及其他測試 → 還原 → 確認全綠」流程驗證過偵測能力與零副作用。Lint baseline 比對(stash 前後跑 `ruff check` 同 3 個檔案):111 → 111,確認未新增 lint 錯誤(既有 baseline 錯誤不在本次範圍)
  - **架構合規**:純資料層數值修正(`repositories/fund/`)+ 新增測試檔(`tests/`),無跨層 import、無新 SSOT 常數需登錄
  - **下一步**:user 需在 production 重新查詢 JFZN3,確認 MK 3-3-3 不再顯示「成立 0.1 年」而是反映實際 ~5 年歷史;若「還有部分指標沒有看到」的問題仍存在,需要新的截圖才能進一步定位。資料一致性檢查(user「兩者都要」裡的另一半)目前由散落在 v19.287~291 各輪新增的 regression test 個別涵蓋,尚未有單一集中的資料一致性掃描機制——若之後還有類似「漏搬東西」但屬於資料層(而非程式碼層)的 bug,需與 user 進一步討論範圍再開工

- **v19.290 Alpha % 永遠 None 的真根因 — perf["1Y"] 沒接到已算好的 tr1y_pct(2026-07-01)**:
  - **背景**:v19.287/288 修完 fetch_holdings/fetch_risk_metrics/fetch_performance_wb01 的 import 後,production 截圖證實 Sharpe 1Y 已經抓到真實數字(0.32),但 Alpha % 仍固定顯示「—」。**user 敏銳發現**:同一頁下方「風險指標」表格另外顯示 `Alpha(1Y) = -0.12`,質疑「上下兩區塊有共同資料,為什麼一個有一個沒有」
  - **先排除誤判**:查證後這兩個 Alpha 其實是**不同定義的指標**——下方是 MoneyDJ 官方 CAPM 型 Alpha(對大盤超額報酬),上方「健康分析」的 Alpha % 則是本專案設計的「真實收益 = 含息報酬 - 配息率」(抓「配息配得比成長還多」的吃老本警訊)。兩者不能互相替代,直接複製會變成掛錯標籤的數字(違反 §3.3 反捏造)
  - **真根因(agent 追蹤到精確行號)**:`services/health/report.py:92` 已經用 `compute_1y_total_return()` 的完整 SSOT fallback chain(`perf["1Y"] → ret_1y_total → ret_1y → NAV 外推`)算出 `tr1y_pct`(這正是畫面上「1Y 含息報酬 2.11%」的來源),但 **line 128 組給 `calc_fund_factor_score()` 的 `_pf` dict 完全沒有重用這個已經算好的值**,只檢查 `fd.get("perf")`/`mj.get("perf")`——保單代碼短窗基金的兩條 `perf["1Y"]` 寫入路徑(wb01 注入 / 本地 ≥350 天窗口注入)都不滿足,`_pf.get("1Y")` 永遠是 None,Alpha 因此永遠算不出來,即使 `tr1y_pct` 在同一個函式的上面幾行就已經是實數
  - **修法(SSOT,借用既有已算好的值,不重算、不新增分支)**:`services/health/report.py:128` 補一行 `if _pf.get("1Y") is None and tr1y_pct is not None: _pf = {**_pf, "1Y": tr1y_pct}`
  - tests:`tests/test_fund_health_report.py` +1(`perf["1Y"]` 缺但 `metrics.ret_1y_total` 有值時,Alpha 仍應 fallback 算出來,鎖住數值 = tr1y - 配息率)。45 個 health_report/factor_availability/portfolio_service 相關測試全綠
  - **本輪 v19.287→v19.290 完整脈絡**:同一個「進階指標全部顯示 None」症狀,實際疊了 3 層獨立根因——① `fetch_holdings` 從未 import(v19.287)② `fetch_risk_metrics`/`fetch_performance_wb01`/`fetch_nav` 等 5 個同病灶(v19.288)③ `perf["1Y"]` 沒接到已算好的 `tr1y_pct`(v19.290)。三層都修完後,Sharpe/持股應該都已正常,Alpha 這次應該也會正常顯示

- **v19.289 相關性矩陣加漲跌幅相關係數(2026-07-01)**:
  - **背景**:user 反饋「相關性矩陣幫我多加漲跌幅相關係數」。查核發現 `services/portfolio_service.py::calc_correlation_matrix()`(NAV Pearson 相關係數,自適應月→週→日頻,|r| ≥ 0.85 警示)**早已存在**,但目前只在「持股/產業資料完全缺」時才當 fallback 使用——只要有任何持股資料,NAV 相關係數就完全不會被算、也不會顯示
  - **修法(對齊 user 確認)**:`ui/helpers/fund_grp_health/correlation.py::_render_correlation_matrix` 從「二選一(fallback)」改成「兩個面板都恆算、獨立顯示」:
    1. 面板 1(不變):Jaccard(持股)×0.6 + Cosine(產業)×0.4,重疊度 ≥ 0.70 警示
    2. 面板 2(新增,恆算):NAV Pearson 漲跌幅相關係數,|r| ≥ 0.85 警示 —— 即使持股完全不同,若同受單一總經因子驅動導致走勢同步,也能被抓出來
    - 兩個門檻獨立判定、獨立顯示警示,不合併成單一分數(語意不同:持股重疊 vs 走勢同步)
  - **SSOT**:新增 `SHADOW_FUND_NAV_CORR_THRESHOLD_RATIO = 0.85` 到 `shared/signal_thresholds.py`,收斂原本 inline 在 `calc_correlation_matrix()` 內的 magic number;抽共用 `_render_one_matrix()` helper 避免兩面板各寫一份熱力圖 + 影子基金警示渲染邏輯(DRY)
  - tests:`tests/test_fund_grp_health_extras_p0.py` +1(鎖住「持股資料齊全時 `calc_correlation_matrix` 也必須被呼叫」,防止之後改回舊的二選一邏輯)。63 個相關 regression 測試全綠

- **v19.288 全站掃描 — F405 揪出另外 5 個同病灶的未 import bare name(2026-07-01)**:
  - **背景**:v19.287 修完 `fetch_holdings` 後,user 問「還有沒有其他類似這種一直抓不到的 function?請幫我掃所有程式找出並 list 出來」。截圖同時證實 Tab2/Tab3 健康分析表 Sharpe/Sortino/Calmar/Alpha 全部顯示 `None`——正是本次掃到的其中兩個 bug 的直接後果
  - **掃描方法**:`ruff check --select F405`(可能未定義,或來自 star import)全站掃 → 71 個命中,幾乎全集中在 `repositories/fund/` 子套件;逐一動態驗證(import 模組後 `hasattr` 檢查)區分真 bug vs 假警報
  - **確認 5 個真 bug**(全部在 `repositories/fund/fund_orchestration.py`,病灶與 v19.287 完全相同——名字定義在 `nav_metrics.py`/`sources.py`,但本模組從未 import):
    - `fetch_risk_metrics` / `fetch_performance_wb01`(兩條 pipeline 皆呼叫)— 有 `except Exception` 接住,靜默失敗;`result["risk_metrics"]`/`result["perf"]` wb01 覆蓋從未真的執行過 → **Sharpe/Sortino/Calmar/Alpha/wb01 報酬率全站顯示 None 的根因之一**
    - `fetch_nav`(legacy pipeline「最終備援:完整 TCB 多路徑爬取」)— 同樣被吞掉,這條號稱的救援機制從未真的執行過
    - `_BANK_PLATFORM_CODES` / `_MORNINGSTAR_SECID_MAP`(兩個 dict 常數,`sources.py` 定義了但沒列進 `__all__`)— 呼叫點**沒有** try/except 包住,只要 `len(nav_s) < 10`(NAV 筆數不足,常見情況)就會直接拋出未捕捉例外
  - **1 個假警報**:`nav_metrics.py:109` 的 `Path` 是 `X if False else Y` 死路(False 分支永遠不求值),下一行才是真正的 import,非真 bug,不動
  - **修法(SSOT)**:`fund_orchestration.py` 頂部 import 擴充為 `from repositories.fund.nav_metrics import (fetch_holdings, fetch_nav, fetch_performance_wb01, fetch_risk_metrics)`;`_BANK_PLATFORM_CODES`/`_MORNINGSTAR_SECID_MAP` 補進 `sources.py` 的 `__all__`(對齊該檔既有其他 `_src_*`/`_is_domestic_code` 等 underscore 常數的匯出模式)
  - tests:`tests/test_nav_history_window.py` +1(綜合鎖住 6 個名字 — 含 v19.287 的 `fetch_holdings` — 都能在 `fund_orchestration` 模組正確解析,防止之後重構誤刪 import 又回到同一種 silent-failure 模式)。再次跑 F405 掃描確認全站只剩 `Path` 這個已知假警報
  - **下一步**:部署後 user 重新整理 Tab2/Tab3 健康分析表,Sharpe/Sortino/Calmar/Alpha 應該不再是 None(除非該基金本身資料源真的沒有 wb07/wb01 頁面);持股區塊也應該能看到真正的抓取結果

- **v19.287 真根因 —「持股」全站從未真正被抓過:fetch_holdings 從未被 import(2026-07-01)**:
  - **背景**:v19.285/v19.286 兩輪修正上線、user 也確認 production 已重新部署 + 清過所有快取,持股區塊卻**一字不差**顯示跟修之前一樣的「三源持股全抓不到」+「來源=—(若無 diag 表示線上仍為舊版)」。部署、快取兩個假說都被 user 提供的證據排除,代表根因在別處
  - **真根因(直接在 sandbox 執行程式碼複現,非猜測)**:`repositories/fund/fund_orchestration.py` 內兩個呼叫「持股」的地方,呼叫的是 bare name `fetch_holdings(code)`,但**這個模組從未 import 這個名字**——`from repositories.fund.sources import *` 不含它、模組內也沒有其他 import 路徑。實際執行 `exec('fetch_holdings("X")', fund_orchestration.__dict__)` 直接復現:`NameError: name 'fetch_holdings' is not defined`。這個 NameError 被兩處呼叫點外層的 `except Exception as e: print(...)` 完整吞掉,`result["holdings"]` 因此永遠停在初始化模板的空 dict `{}`,從未真正呼叫到 `nav_metrics.fetch_holdings()` 本體——v19.285/v19.286 對這顆函式做的所有診斷強化完全沒有機會執行到
  - **另一個缺口**:`fetch_fund_from_moneydj_url`(legacy pipeline,TLZF9 這類保單代碼實際使用的路徑)裡**從頭到尾根本沒有呼叫持股抓取**,連壞掉的呼叫都沒有——這條 pipeline 對持股完全空白
  - **修法(SSOT)**:`fund_orchestration.py` 頂部補 `from repositories.fund.nav_metrics import fetch_holdings` 明確 import;`fetch_fund_from_moneydj_url` 補上與 `_fetch_fund_single` 同款的呼叫(`try: result["holdings"] = fetch_holdings(code) except Exception as e: print(...)`),兩條 pipeline 現在都會真正呼叫到同一顆共用函式
  - tests:`tests/test_nav_history_window.py` +2(`fetch_holdings` 可在 `fund_orchestration` 模組命名空間正確解析且與 `nav_metrics.fetch_holdings` 是同一物件;legacy pipeline 原始碼確實含 `fetch_holdings(code)` 呼叫)。87+ 個 fund_orchestration/moneydj/nav_metrics/holdings 相關測試全綠
  - **這是整個「找不到持股」系列(v19.280→v19.287)真正的根因** — 前面幾輪對 `nav_metrics.fetch_holdings()` 診斷機制的強化雖然本身沒錯,但因為這顆函式從未被成功呼叫過,所有強化都無從發揮作用。這次修完後,production 重新整理 Tab2 應該會看到**真正**的抓取結果(成功持股 / 詳細 diag),不會再是一模一樣的「來源=—」

- **v19.286 fetch_holdings 外層 bare except 補 diag(2026-07-01)**:
  - **背景**:v19.285 上線後,user 截圖 Tab2 持股區塊仍顯示「三源持股全抓不到」+「來源=—(若無 diag 表示線上仍為舊版,請 Manage app → Reboot)」——這句提示文字本身就是 v19.280 程式碼的一部分,代表 production **已經**跑在有 diag 機制的版本,矛盾點在於:診斷機制存在,但 diag 依然是空的
  - **真根因(讀 code 找到)**:`fetch_holdings()` 整個函式本體包在一個大 `try:` 裡,外層 `except Exception as e: print(...); return {}` —— 只要函式本體任何一處拋出未預期例外(不是逐 URL 迴圈內、已個別 try/except 保護的那種,而是例如 BeautifulSoup 解析、字串處理等),就會被這個 bare except 整個吞掉,直接回傳空 `{}`,連 v19.280/v19.285 辛苦建立的 diag 機制都完全繞過。這正是「有 diag 機制、但 diag 是空的」這個矛盾的解釋:不是版本舊,是真的中途拋了例外
  - **修法**:外層 except 也帶 `diag`(含例外類型 + 訊息)+ `source="MoneyDJ:exception"`,讓例外訊息本身變成 UI 可見、可 audit 的線索,不再是完全空白的「—」
  - tests:`tests/test_fetch_holdings_fallback_chain.py` +1(patch `BeautifulSoup` 拋例外,驗證 diag/source 仍被填入)。70 個 holdings/nav_metrics/moneydj 測試全綠
  - **下一步**:user 需在 production 重新整理 Tab2,若這次 diag 顯示出具體例外訊息(例如某個 parse 邏輯真的壞了)→ 直接對症修;若 diag 顯示逐 URL 明細但全部連不到 → 回到 v19.285 原本設想的「資料源覆蓋率限制」路線

- **v19.285 持股抓取診斷補逐 URL 明細(PR #498,2026-07-01)**:
  - **背景**:user 給 2 個實際 MoneyDJ 網址(境內 `yp010000.djhtm?a=acdd01` / 境外 `yp010001.djhtm?a=jfzn3`)反饋持股仍有缺,要求「製作爬蟲補齊」。查核發現本專案**早已有成熟爬蟲**涵蓋這兩種格式(`services/moneydj_fetcher.py::auto_fetch_moneydj` 自動偵測境內/境外互換;`nav_metrics.py::fetch_holdings` 14 組候選 URL,依代碼前綴展開保險平台子網域),非從零開始
  - **真缺口(讀 code 找到)**:`fetch_holdings()` 內部已算出每個候選 URL 的逐一結果(`_attempts`:host/status/len),但傳給 UI 的 `diag` 只塞一行「N 候選 URL 全失敗」摘要,`_attempts` 細節被丟棄——`render_holdings_diag`(v19.280 建立)因此看不到任何可 audit 的細節,user 截圖回報時無從分辨「完全連不上」vs「連上但表格結構 parser 沒涵蓋」
  - **修法(SSOT,擴充既有欄位,不新增邏輯分支)**:
    1. 全失敗分支:`diag` 改逐 URL 列出 host + 狀態 + 長度(原本算好的 `_attempts` 直接攤平進去)
    2. 頁抓到但 parser 0 命中分支:`diag` 點名成功抓到頁的 host + table 數量
  - tests:`tests/test_fetch_holdings_fallback_chain.py` +2(全失敗逐 URL 列出 / 0 命中標明 host+table 數)。69 個 holdings/nav_metrics/moneydj 相關測試全綠
  - **架構合規**:純 L1 Repository 內部欄位擴充(`repositories/fund/nav_metrics.py`),無跨層 import、無新 SSOT 常數、無新例外需登錄 §8.2.A
  - **下一步**:user 需在 production 重查 ACDD01/JFZN3,截圖 Tab2 持股診斷 banner(這次含逐源明細)回報,才能看出具體卡在哪一關,對症修正(而非在 sandbox 猜測 HTML 結構——`www.moneydj.com` 與 `m.moneydj.com` 同樣被本 sandbox 出口政策擋下,無法直接驗證)

- **v19.284 真根因修復 — 第二條 legacy NAV pipeline 補 span-extend(2026-07-01)**:
  - **背景**:v19.283 banner 上線後,user 截圖 TLZF9 顯示「淨值 30 筆 ‧ 配息 24 筆 ‧ 來源:—」—— 30 筆、無 `data_source`,證實 v19.281 的 span-extend **完全沒被觸發**
  - **真根因(追蹤 code 找到)**:`repositories/fund/fund_orchestration.py` 內其實有**兩條平行的 NAV pipeline**:
    1. `_fetch_fund_single`(多來源 waterfall,v19.281 已加 span-extend)—— 由 `fetch_fund_multi_source` 呼叫
    2. `fetch_fund_from_moneydj_url` 函式**自己內建的第二套 legacy 直接爬蟲**(「Step 3+ 原始流程」,~250 行,含近30日/yp004002 歷史查詢/`fetch_nav()`最終備援)—— 當 pipeline 1 的 `_s_ok`/`_m_ok` 判斷失敗時才會 fallback 到這裡
    - TLZF9 走的正是 pipeline 2(「近30日」分支命中 30 筆,與截圖數字吻合),而 v19.281 的 span-extend **只補在 pipeline 1**,pipeline 2 完全沒有、也從未設 `data_source`/`nav_span_days` —— 這就是 banner 顯示「來源:—」的真正原因,也是 v19.281 對 TLZF9 這個 case 實際上「沒生效」的原因
  - **修法(SSOT 收斂,而非各補一份)**:抽出模組級共用函式 `_span_extend_insurance_nav(code, nav_s, nav_source, fund_name, is_insurance_code)`(+`_nav_span_days` helper),原本巢狀在 `_fetch_fund_single` 內的 span-extend 邏輯改呼此共用函式;**同時**在 `fetch_fund_from_moneydj_url` legacy pipeline 的 NAV 組裝完成點(`fetch_nav()` 最終備援之後、`len<10` 錯誤判斷之前)也呼叫同一份函式 —— 兩條 pipeline 共用同一份 span-extend,不再各寫一份(對齊 user 要求的 SSOT)
  - **額外效果**:即使 Morningstar/cnyes 對某檔基金真的沒有長歷史(span-extend 未命中),legacy pipeline 現在也會標出 baseline `data_source`(如 `moneydj_legacy_scrape`)—— banner 不會再顯示完全空白的「—」,至少能看出「這是哪條 pipeline 產出的」
  - tests:`tests/test_nav_history_window.py` +5(`_span_extend_insurance_nav` 直接單元測試:短跨度救援命中 / 未命中保留 baseline label / 非保單代碼跳過 / 已夠長跳過 / legacy pipeline import 存在性防重構誤刪)。104 orchestration/nav/holdings 測試 + 3 Tab2 AppTest 全過,0 regression
  - **下一步**:部署後看 TLZF9 banner —— 若 `來源:tcb_moneydj`(或其他短源,無 span-extend 字樣)且跨度仍短 → 代表 Morningstar/cnyes 對 TLZF9 在 production 確實查無資料,是資料源本身的限制,不再是程式邏輯漏洞;若顯示 `morningstar(span-extend)` 且跨度 > 300 天 → 這次真的修好了

- **v19.283 Tab2 NAV 來源 + 跨度診斷 banner(2026-07-01)**:
  - **背景**:user 截圖 TLZF9「MK 3-3-3 ❌ 成立 0.1 年」在 v19.281(NAV 窗口擴展 + span-extend)合併後**依然存在**,並問「請確定資料存放位置找到對的地方修改」
  - **根因定位(讀 code 追蹤,非猜測)**:
    - `_compute_holding_years`(`services/health/report.py`)讀 `fd["series"]` 算年數 — 這條鏈路正確,問題不在計算端
    - `_fetch_fund_single`(`repositories/fund/fund_orchestration.py`,v19.281 已加 span-extend + `nav_span_days`/`data_source` 欄位)**是正確的資料存放位置**,但這兩個欄位算完後**從未在 UI 顯示** — user 和我都看不到「到底哪個來源贏、跨度多長、span-extend 有沒有觸發」,只能盲猜
    - 額外發現:`_fetch_fund_single` 中 www.moneydj.com 400 天窗口(step 2d)只在 `len(nav_s)<10` 才觸發 — 若更早的短源(如 insurance_subdomain,~1 月)以 `≥10` 筆數過關,連這條路徑都會被跳過,更凸顯「筆數把關無跨度檢查」是系統性設計缺口(v19.281 span-extend 已補在最後一關堵住,但無法補救「用哪個源」的可見性問題)
  - **修法(v19.283,純 UI 唯讀顯示,不重算,SSOT 合規)**:`ui/tab2_single_fund.py`「① 基本資料」banner 追加顯示 `mj_raw.get("data_source")` + `mj_raw.get("nav_span_days")`(換算年數)— 兩者皆 L1 orchestrator 已算好的既有欄位,L3 純讀取渲染,無新業務邏輯、無重複計算
  - tests:`tests/test_app_apptest.py::test_tab2_nav_source_banner_shows_data_source_and_span` 端到端(AppTest 真渲染)守 banner 顯示 `data_source` + `nav_span_days`。既有 Tab2 apptest 3 個全過
  - **下一步**:部署後 user 看 Tab2 banner「來源:`X` ‧ 跨度 Y 天」即可判讀:若來源顯示 `morningstar(span-extend)`/`cnyes` 但 MK 3-3-3 仍錯 → 另有 bug;若來源仍是短源(如 `insurance_subdomain`)且跨度 < 300 天 → span-extend 在 production 未命中(可能 Morningstar/cnyes 對 TLZF9 在該環境查無資料),需要真實 production log 才能繼續往下修,而非在 sandbox 繼續猜測(proxy 403 無法驗證真實抓取)

- **v19.282 持股明細 SSOT 共用 render + Tab2 常駐(2026-07-01)**:
  - **背景**:user 要求「單一基金也放持股資訊」+ 提醒守 SSOT。查核發現 Tab2(`tab2_single_fund` L1100)與 組合健檢(`fund_grp_health/investment` L156)**各有一份 byte-identical 的持股渲染** → 既有 SSOT 違規;且 Tab2 只在 `if _sectors or _tops` 才顯示,空持股靜默(user 誤以為沒功能)
  - **修法**:抽共用 `ui/helpers/holdings.render_holdings_detail`(產業配置 + 前10大持股)+ `render_holdings_diag`(空持股攤三源診斷),兩處 + Tab5 news 空狀態全改呼共用
  - Tab2 持股 expander 改**常駐**(空時顯示 diag,不再靜默);investment.py / ai.py 去重複
  - 純 L3 UI render:僅依 streamlit + shared.colors(L0)+ 同模組 `_zh_holding`,無 IO、無上行 import
  - **回歸**:AppTest `test_tab2_loaded_fund_...` 抓到 `_sectors` NameError(移除定義但下游 AI snapshot 仍用)→ 已補回;`test_holdings_render_ssot.py` 4 例守共用契約
  - investment.py 清 4 個孤兒 color import(F401)。141 passed / 1 skipped

- **v19.281 NAV 歷史修復 — 保單代碼「成立 0.1 年」根因(2026-07-01)**:
  - **背景**:user 截圖 TLZF9 —— MoneyDJ 有 3-5 年 NAV(3Y 報酬 39.31%)+ 完整前十大持股(NVIDIA/APPLE…),但本站顯示「成立 0.1 年」、3Y/5Y 全 —。**資料嚴重缺少**
  - **根因(讀 code 確認)**:`fund_orchestration._fetch_fund_single` NAV 來源鏈**只用筆數把關**(`len(nav_s) < 10/20`),**無跨度檢查**。保單代碼(cnyes/FundClear 解析不到)落到近期短源(insurance_subdomain / tcb ~1 月,≥10 筆)就鎖定,把長歷史 Morningstar(TLZF9 硬編 secId=0P0001J5YG)整條 `if len<10` skip → 只剩 ~1 月 → 成立 0.1 年
  - **修法**:
    1. cnyes `fetch_nav_cnyes` + Morningstar `_src_morningstar_nav` 窗口 **400d → 2000d(~5.5 年)**,讓 3Y/5Y 可算
    2. `_fetch_fund_single` 加 **span-extend**:若選定 nav_s 跨度 < 300 天且為保單代碼 → 顯式試 Morningstar / cnyes 長歷史,取跨度更長者(additive,只換更長不退步);`result["nav_span_days"]` + source_trace 記 span
  - tests:`test_nav_history_window.py` 3 例(cnyes/Morningstar 窗口 ≥5 年 + span-extend 決策)。56 既有 orchestration/nav 測試 0 regression
  - **⚠️ sandbox 無法驗證**(proxy 403)→ 邏輯 additive + guarded,production 部署後看 TLZF9「成立年數」是否轉正 + 3Y/5Y 是否出數

- **v19.280 持股抓取診斷 UI 可視化(2026-06-30)**:
  - **背景**:user 回報 TLZF9 等仍抓不到,問「能不能用 print 確認有沒有抓到資料」。根因 stderr log 藏在 Streamlit Cloud 後台 user 看不到 → 改**把逐源診斷攤在 UI**
  - `fetch_holdings_cnyes` / `fetch_holdings_morningstar` 加 opt-in `diag` list 參數,逐步記錄(代碼解析候選 / secId / 每端點 HTTP+keys / ✅命中)
  - `nav_metrics.fetch_holdings` 串 `_diag`,**所有空結果 return 路徑都掛 `out["diag"]`**(MoneyDJ→cnyes→Morningstar 三源逐一結果)
  - `ui/helpers/fund_grp_health/ai.py` 持股新聞 empty-state 改顯示 `st.code(diag)` —— user 直接在 app 看「試了哪些源、各回什麼 keys」;無 diag → 提示「線上仍舊版,Reboot+強刷」
  - tests +3(diag 掛載 / cnyes keys / ms no-secId);call-arg assert 補 `diag=ANY`。40 passed
  - **用途**:部署後 user 一看 UI diag 就知卡在哪(代碼沒解析到？secId 找不到？端點 200 但 keys 不認得？)→ 貼回來即可精修,不用再猜

- **v19.278 持股 Morningstar fallback — 保單/FoF 代碼第二替代源(2026-06-30)**:
  - **背景**:user 回報 v19.276 cnyes fallback **部署後仍抓不到**(ACTI71/JFZN3/ACCP138/TLZF9)。⚠️ **關鍵診斷**:Tab5 Put/Call trace 只有 Yahoo+stooq、**無 CBOE 嘗試** → 證實**線上仍跑舊 deploy**,v19.276/277 根本還沒生效。但這些保單平台多重資產/FoF 代碼即使 cnyes 生效也未必有 → user 要求再找替代源
  - **研究結論**:這幾檔在 Morningstar **有**資料(如 Allianz Income&Growth = ISIN LU0689472784);本專案已有 secId 基建(`_MORNINGSTAR_SECID_MAP` TLZF9=0P0001J5YG / JFZN3=0P0001N4II + `_morningstar_search_secid` + token-free `tools.morningstar.co.uk`)
  - `repositories/fund/sources.py:fetch_holdings_morningstar(code)` — `_resolve_ms_secid`(硬編表→TDCC 名稱橋接搜尋)+ `_ms_parse_holdings`(防禦式多 viewId×多欄位 parse;多重資產主抓**資產配置** 股/債/可轉債/現金 %)
  - wire 進 `nav_metrics.fetch_holdings` cnyes 之後(MoneyDJ→cnyes→Morningstar 三層 fallback)
  - F-PROV-1 `Morningstar:holdings:{secid}:{view}`;失敗回 {} + log keys(§1)
  - `tests/test_fetch_holdings_cnyes.py` +7 例;既有 fallback test patch Morningstar 維持確定性。33 passed
  - **⚠️ 誠實限制**:Morningstar holdings viewId / JSON shape 開發環境(proxy 403)無法實測 → 防禦式;且 FoF granular 個股本就稀少,主要拿到資產類別配置(夠 shadow-fund overlap 用)。**真正未驗的是「線上有沒有部署到」**——需 user 確認 redeploy + 硬刷新後看 production log

- **v19.276+277 資料抓不到修復 — 持股 cnyes fallback + Put/Call CBOE 官方源(2026-06-30)**:
  - **背景**:user 截圖資料診斷回報兩個真實「抓不到資料」故障,要求修復(§-1 真 bug 觸發)
  - **v19.276 持股 cnyes fallback**(`579a4ab`):
    - **故障**:Tab2 ACTI71(聯博多元資產收益,FoF)/ JFZN3(摩根多重收益)等「MoneyDJ 未提供持股,無法抓新聞」(yp013xxx 子網域限制 / multi-asset / FoF 透明度不足)
    - `repositories/fund/sources.py:fetch_holdings_cnyes(code)` — L1 純 fetcher,鏡像 `fetch_div_cnyes`,多 endpoint(portfolio/holding/holdings/asset)× 多候選代碼;`_cnyes_parse_holdings` 防禦式多 shape 解析(top_holdings + sector/asset/region allocation,多欄位名 fallback)
    - wire 進 `nav_metrics.fetch_holdings` 兩處空結果 exit(MoneyDJ 全 URL 失敗 / 抓到頁但 parser 0 命中)
    - F-PROV-1 provenance `Cnyes:{res}:{code}`;失敗回 {} + log 真實 keys(§1 Fail Loud)
    - `tests/test_fetch_holdings_cnyes.py` 14 例 + 既有 fallback_chain/multi_asset patch cnyes 維持確定性
  - **v19.277 Put/Call CBOE 官方源**(`18a0df8`):
    - **故障**:雷達 9 Put/Call「全源失敗」(Yahoo ^CPC/^CPCE 回空 + stooq ^cpc 無法解析;v19.141 移除的 CBOE daily_prices/CPC_History.csv 確下架)
    - `repositories/external_market_repository.py:fetch_cboe_pcratio_csv(kind)` — 接 CBOE **另一現用**官方目錄 `cdn.cboe.com/resources/options/volume_and_call_put_ratios/{total,equity}pc.csv`(與死路徑不同 endpoint;MacroMicro/Alphacast 皆源於此)。parser 不寫死 skiprows,自動偵測 header 行
    - `services/risk_radar.py:_resolve_put_call` 末層加 CBOE total→equity(total 語意對齊 ^CPC >1.0/>1.2 閾值);過 `validate_cboe_series`(source `CBOE:pcratio:`)
    - **⚠️ CI 實證 + Freshness guard(關鍵)**:GitHub CI(有真網路)抓 `totalpc.csv` 末筆**停在 2019-10-04** → 該公開 CDN 檔為**凍結歷史檔**,非當期 feed。加 `_CBOE_PC_MAX_AGE_DAYS=30` 守門:末筆 > 30 日 → 拒用回空(§1 寧炸不假,**絕不把 2019 當現值**),並讓 chain 由凍結 total 落到較新 equity。**誠實結論**:若 CBOE 公開 CDN 全凍結,Put/Call 仍誠實顯示「全源失敗」(不退步、不造假);真要當期值需付費/帶 key 源(CBOE DataShop 等)
    - `tests/test_risk_radar.py`:`TestCboePcRatioCsv` 7 例(含 stale-reject,日期相對 today 防 flaky)+ fallthrough;更新 v19.141 死路徑守門 test(禁 daily_prices/CPC + .json,允許 volume_and_call_put_ratios);修 2 既有 test patch 新 CBOE 層維持確定性
  - **架構/SSOT 合規**:兩 fetcher 皆 L1,僅依 L0 `infra.proxy`(L2→L1 import 合法方向);無 inline magic / 無偽造 / 無新例外需登錄。資料診斷 data-driven 自動轉綠,0 UI 改動
  - **⚠️ sandbox 限制**:local proxy 403 無法驗證 cnyes /portfolio 與 CBOE CSV 真實 body → 防禦式解析(production NAS Squid 連得上,VIX3M 同 CDN 已成功)。猜錯欄位 = 回空 + log 真實 shape 供下一輪精修,絕不崩潰
  - **驗證**:155 passed / 2 skipped(risk_radar + holdings + schema gate + data_guard)

- **v19.275 深度死碼掃描 + 清理 A+B(2026-06-30,PR #488,squash `1175073`)**:
  - **背景**:user 要求「深度檢查是否還有雜亂的程式碼與死碼讓系統拖累跟膨脹」
  - **方法論**:4 路並行 Explore agent(殭屍函式 / 死 import / legacy檔+scripts / 大檔膨脹)+ **逐一 adversarial 驗證**
  - **關鍵:raw scan 偽陽性率高,驗證救回 4 個誤判**(若直接刪會炸 production):
    - `backtest_turning_points` / `backtest_sub_cycle_lights` — agent 報 0-caller,實際 inflection.py:445 / tab3_t7_ledger:2743 / tab5:715 有呼叫
    - `_helpers.py` dead imports — re-export hub(`# noqa: F401` 刻意 shim)
    - `migrate_v149_schema.py` — tab3:864 有 live UI 按鈕
  - **A — 刪 3 孤兒 SSOT 常數**(`shared/macro_buckets.py`):`LEVEL_EMOJI` / `LEVEL_RANK` / `BUCKET_LEVEL_LABEL` 全站 0 ref(連 test 都沒)。成因:P3 拆 tab1_macro 5 section 前的「5 桶視覺 registry」,section 改手寫未接 → 孤兒。**誠實縮範圍 5→3**(`BUCKET_ORDER`/`BUCKET_META` 守 live `BUCKET_DANGER_SPECS` taxonomy 保留;`LEVEL_COLOR` danger.py 消費保留)
  - **B — 刪 2 dev throwaway script + 1 test**:`scripts/compare_wb01_vs_local.py`(108)+ `scripts/eval_macro_consensus.py`(323)+ `tests/test_eval_macro_consensus.py`。runtime 從不 import,非運行系統膨脹,純 repo 整潔度
  - **淨 -758 LOC**
  - **系統健康結論**:整體很乾淨——debt markers 僅 3(全 benign)、v19.261-274 新增碼 0 死碼、前 4 階段 + PHASE1/Phase2 已把真違規清光。本次只挖到 1 個 production 孤兒常數 cluster + 2 個 dev script 雜物
  - **驗證**:CI Fast + Schema gate + Slow tests 三項全綠

- **v19.274 Phase 2 收尾 — mk_clock 第4 chrome + #111 chip bg 2 保留項 SSOT(2026-06-30,PR #487,squash `61c6bdf`)**:
  - **背景**:user 指示深挖 PHASE1_AUDIT_DELTA.md 2 個保留項,深挖後確認都是真 SSOT gap(非單純 cosmetic)
  - **mk_clock 第 4 處 chrome**(`f62fe89`):`ui/components/mk_clock.py:237` 三面向訊號 cell 卡外框收斂至 `gh_card`(byte-identical)。**全站 4 個 GitHub-style 卡片 chrome 100% 收斂至 `ui/components/cards.gh_card`**
  - **`#111` chip bg**(`3dabe0e`):**深挖修正**——先前 TOP 2 標為「單一 site 範疇外」是低估,實為 3 處 cross-file 真重複(`tab2:573` + `tab2:1013` + `tab3:1998`)且無 SSOT 常數。新 `shared/colors.py:CHIP_BG_NEAR_BLACK = "#111"`,3 site 收斂,grep `ui/` `#111` = 0 殘留
  - **驗證**:CI Fast + Schema gate + Slow tests 三項全綠,0 regression
  - **Phase 2 完整收尾**:TOP 1/2/3 + 2 保留項全部 SSOT gap 清空,排毒真正達穩態

- **v19.273 Phase 2 TOP 2+3 — gh_card chrome SSOT + EX-PASSTHRU-1 補登(2026-06-30,PR #486,squash `098796f`)**:
  - **背景**:user 指示「做 TOP 2 / TOP 3」,依 `PHASE1_AUDIT_DELTA.md` 收完最後 2 個候選
  - **TOP 2 — GitHub-style 卡片外框 chrome SSOT**:
    - **審查修正**:原 audit 建議收斂到 `_render_macro_indicator_card` 為誤判——3 site 形狀全不同(策略訊號 banner / σ 買賣點表卡 / empty-state),都不是 metric card。正確 SSOT 為「卡片外框 chrome」
    - 新檔 `ui/components/cards.py`:`gh_card(inner, *, radius, padding, margin, extra)` 純字串 helper(零 streamlit/plotly/pandas 依賴,只 shared.colors L0),**byte-identical 輸出設計**(margin/extra 空時省略宣告)
    - 5 commits 小步快跑:helper + `test_cards_chrome.py` 6 case 守門(`52dfa81`)→ Site 1 tab2:359 banner(`09b19bb`)→ Site 2 tab2:564 σ卡(`5a1d93d`)→ Site 3 tab1_macro_inflection:248 empty-state(`18b2a51`)
    - 第 4 處(`mk_clock.py`)等該檔下次觸碰順手收
  - **TOP 3 — EX-PASSTHRU-1 補登**(`e4a5aeb`,純文件):
    - CLAUDE.md §8.2.A 補第 6 組 entry:`ui/tab1_macro.py:821` UI 直呼 4 個 TW 本地總經 self-contained L1 fetcher(v19.197 P1-4 下沉後既有 pattern)
    - callsite 加 3 行註解指回例外表
  - **驗證**:CI Fast + Schema gate 雙綠;test_cards_chrome 6 + tab2 16 + tab1_macro 13 + app_smoke 96 = 131 passed / 2 skipped
  - **Phase 2 全收**:TOP 1(PR #485 ADR SSOT)+ TOP 2(card chrome)+ TOP 3(EX-PASSTHRU-1)= PHASE1_AUDIT_DELTA.md 3 大候選 100% 清空。排毒達穩態,§-1 停手等指令

- **v19.272 Phase 2 TOP 1 — Tab3/Tab5 ADR fallback SSOT 收斂(2026-06-30,PR #485,squash `4ce2bf4`)**:
  - **背景**:user 啟動 Phase 2「精準打擊與實作」,依 `PHASE1_AUDIT_DELTA.md` TOP 1 收斂 3 個 ADR callsite
  - **方法論**:小步快跑(1 site → test → 1 commit × 3),每步 0 regression,鐵血鐵律(SSOT 收斂 / 拒絕狗皮膏藥 / 增量修改)
  - **Site 1**(`a65171b`):`ui/tab3_portfolio.py:1250` div_safety_check 入點,原 2-layer → `_resolve_adr_with_fallback` SSOT 3-layer
  - **Site 2**(`3da899e`):`ui/tab3_portfolio.py:2041-2067` 健診總表 _div,**抽掉 22 LOC inline 完整 SSOT 複製**(原本 UI 層逐行重做 datetime parse + 12M 累積 + nav 換算)→ 1 行 SSOT call
  - **Site 3**(`919e379`):`ui/tab5_data_guard.py:1019` _d5_adr,原 2-layer → SSOT 3-layer
  - **淨收斂**:+14/-29 = **-15 LOC**
  - **語意升級**:Tab2(v19.177 已 SSOT)/ Tab3 / Tab5 三 tab 顯示 ADR 完全對稱;當「wb05 缺 + metrics 缺但有 dividends 歷史」時 Tab3/5 可多救一筆
  - **驗證**:CI Fast + Schema gate + Slow tests 三項全綠(Site 1 後 100 / Site 2 後 145 / Site 3 後 114 passed)
  - **剩餘 Phase 2 候選**:TOP 2(HTML card pattern,~10 LOC 純視覺)/ TOP 3(EX-PASSTHRU-1 補登,~5 LOC 純文件),等 user 點

- **v19.266-270 C #1~8 8-項一鍋燴(2026-06-30,PR #484,squash `0f2bec3`)**:
  - **背景**:user 指示「C #1~8」對全部 doc + schema + scoring 一鍋掃。風險梯度從低到高分 5 phase
  - **Phase 1 v19.266 doc-sync**:CLAUDE.md F-PROV-1 / F-GRAY-4 / F-RECON-1 status 更新
    - F-PROV-1:13 L1 fetcher 已收 v19.82~v19.221,2 個 by-design 不可收,1 個 macro 融合缺口(Phase 5 補)
    - F-GRAY-4:HY 90% / CPI 部份 / PMI WONTFIX(user 2026-06-26 撤銷 v19.147)
    - F-RECON-1 新章節:v19.91 phase 6 全 3 chip 渲染落地(Sharpe/配息殖利率/1Y 報酬)
  - **Phase 2 v19.267 D8 #5+#6**:`validate_defillama_series`(共用 YahooCloseSchema)+ `validate_aaii_sentiment`(dict 雙 path),caller wiring(us_liquidity_engine + liquidity_engine)
  - **Phase 3 v19.268 D8 #7**:`validate_ndc_signal_dict` / `validate_tw_pmi_dict` / `validate_tw_export_yoy_dict` / `validate_foreign_consec_dict` 4 個 TW dict validator + `ui/tab1_macro.py` `_safe_tw()` 4 sites
  - **Phase 4 v19.269 D8 #3**:CPI 2 處 logic inline 收口 → SSOT(`services/calibration/macro_score.py:_s_cpi` + `ui/helpers/macro/helpers.py:183`)。0 行為變化
  - **Phase 5 v19.270 D8 #8**:`calculate_composite_score(ind, *, provenance_out=None)` opt-in side-car dict(設計 E:避 NamedTuple 改 signature)
  - **Fixup `005e22d`**:`test_tab1_tw_local_section.py` 4 fixture 加 source 全名 + ISO fetched_at + `today_net`(對齊 Phase 3 schema 驗證)
  - **F-SCHEMA-1 surface 升級**:7 → 15 validator(7 起點 → 9 v19.265 → 11 v19.267 → 15 v19.268)
  - **驗證**:CI Fast + Schema gate 雙綠,phase_d 41 case + composite_score_provenance 9 case + 既有 test 全綠
  - **C deep-dive 後續(workflow 結果)**:`#2 HY education docstring` / `#4 PMI WONTFIX` / `#9 yf_forward_pe 包裝` 三項經 3 agent audit + adversarial verify 一致確認 **WONTFIX 成立**,皆無 1-PR 行動建議。CLAUDE.md §8.3 + §2.2 文字微調防再 audit

- **v19.265 D7 F-SCHEMA-1 Tier 2/3 — stooq + CBOE Series validators(2026-06-30,PR #483,squash `771d256`)**:
  - **背景**:user honest-scoping 後決定推進 D7(4 個 D epic 中,D6 純 docstring 低 ROI、D8/D9 經實地核對發現大都已 v19.86~v19.221 默默收完,只剩 D7 真有實質工作)
  - **新增 shared/schemas.py 2 validator**(共用 YahooCloseSchema 結構契約,Series 形狀相同):
    - `validate_stooq_series(s)` — 結構 + `'stooq:'` source prefix + ISO `fetched_at`
    - `validate_cboe_series(s)` — 結構 + `'CBOE:'` source prefix + ISO `fetched_at`
  - **Caller wiring**(`services/risk_radar.py`):
    - `_safe_validate_stooq` / `_safe_validate_cboe` wrapper:schema 違反 → 回空 Series + log,fallback chain 不鎖
    - `_resolve_vix3m` chain 3 處(CBOE+stooq×2)+ `_resolve_put_call` chain 2 處(stooq×2)接入
  - **CI gate**:`tests/test_schemas_phase_d.py` 加入 `.github/workflows/pr-check.yml` schema-gate job
  - **設計理由**:
    - **共用結構契約**:stooq/CBOE/Yahoo 三 source Series 形狀相同(datetime → float > 0),YahooCloseSchema 直接複用避免重複 Schema 物件
    - **fallback chain 防鎖**:strict raise 會中斷 chain(失去 fallback 意義),改用 _safe_validate_* wrapper 回空 → caller 跳下一層。同時 print log,符合 §1 Fail Loud
    - **長尾擴展 pattern**:後續 dict-return fetcher(AAII / DefiLlama / Taiwan locals)可依此 pattern 增量加
  - **F-SCHEMA-1 surface 升級**:7 → 9 validator(5 Schema + 9 validator + 7 test file,CI gate 7 test)
  - **驗證**:phase_d 13 + phase_b 12 + app_smoke 96 = **121 passed**,CI Fast + Schema gate 雙綠

- **v19.263-264 P3 long-tail SSOT 收口(2026-06-30,PR #482,squash `9efb297`)**:
  - **背景**:P3 拆檔(PR #480/#481)後 5 sibling files 殘留 9 處 inline hex,user 指示「請繼續深挖」+「C 項目補上」深挖到底
  - **方法論**:cardinality scan(各 hex 跨檔出現次數)→ 跨檔重複高 ROI 直接收 SSOT;單檔/單用按 user 要求一起收完
  - **v19.263**(5 跨檔重複):
    - `MD_ORANGE_A200 = "#ffab40"`(Z-Score 警示,3 處 / 2 檔)
    - `BG_DARK_GREEN_2 = "#061a06"`(success deep,3 處 / 3 檔)
    - `BG_DARK_GREEN_3 = "#0a3a1a"`(雙確認買 badge,2 處 / 2 檔)
    - `BG_DARK_RED_3 = "#3a0a0a"`(雙確認賣 badge,2 處 / 2 檔)
    - `BG_DARK_AMBER_3 = "#1a1500"`(σ 小跌小買 alert,2 處 / 2 檔)
  - **v19.264**(2 單檔/單用,user 指示一併收):
    - `BG_DARK_GREEN_GAUGE = "#0a2a0a"`(gauge safe zone tuple,3 處同檔)
    - `BG_DARK_PURPLE_1 = "#1a0a2a"`(大跌大買訊號 bg,1 處)
  - **總計**:**7 新 SSOT 常數 / 15 hex literal 收回 / 0 inline hex 殘留**
  - **Caller 收口**:6 production 檔(`ui/tab1_macro.py` + 4 sibling + `services/precision_service.py`)+ `shared/colors.py` SSOT 註冊
  - **架構**:§8.2 0 違憲新增;BG/MD 常數屬 L0 Shared,跨層被全層 import 為預期 pattern;L2 service `precision_service.py` 用 `shared.colors` 既存 pattern
  - **驗證**:CI Fast checks + Schema gate 雙綠,131 passed / 2 skipped

- **v19.261-262 P3 tab1_macro.py 5 section 拆檔完整收口(2026-06-30,PR #480 + #481,squash `c783ee3` + `0fc6ef0`)**:
  - **背景**:`ui/tab1_macro.py` 2963 LOC monolith,5 大 section(長期/中期/短線/拐點/AI)全擠在一個 `render_macro_tab()` 函式,closure-heavy 難維護
  - **方法論**:每 section 抽到 sibling file(`ui/tab1_macro_<section>.py`),參數注入(`ind`/`phase`/`fred_key`/`show_l3`)取代 closure local,module-level helper(`_render_macro_indicator_card` 等)lazy import 避循環
  - **P3-A2**(`c783ee3` v19.261 PR #480):🤖 AI 景氣判斷 → `ui/tab1_macro_ai.py`(-289 LOC,含 `_build_macro_ai_snapshot` 9 章節)
  - **P3-A3~A6**(`0fc6ef0` v19.262 PR #481 一單 4 commits + 1 fixup):
    - A3 📈 中期循環 → `ui/tab1_macro_midcycle.py`(-176 LOC,含 Z-Score 矩陣 23 指標 + L3 情境判斷卡)
    - A4 🎯 短線雷達 → `ui/tab1_macro_radar.py`(-245 LOC,10 燈雷達 + 流動性壓力預警引擎)
    - A5 🌳 長期座標 → `ui/tab1_macro_longterm.py`(-293 LOC,美股流動性 6 卡 + MK 時鐘 + 資本防線 + 新聞)
    - A6 ⚠️ 拐點警報 → `ui/tab1_macro_inflection.py`(-484 LOC,戰情室三儀表 + 持倉紅綠燈 + 拐點偵測中心 + 倒掛 SPX 回測)
    - fixup:3 source-string regression test(`test_grp_health_bugfixes` / `test_net_liquidity` / `test_tab1_no_unbound`)path 改新 sibling + 檔尾 EOF trim
  - **總計**:`ui/tab1_macro.py` **2963 → 1475 LOC(-1488, -50%)**,5 新檔(AI/中期/短線/長期/拐點)
  - **架構**:0 §8.2 違憲新增,4 EX 例外清單(EX-CACHE-1 / EX-AI-1 / EX-CRUD-1 / EX-PASSTHRU-1)無新增 entry;sibling 全屬 L3 UI helper(允許讀寫 session_state + lazy import)
  - **SSOT**:既有 `shared.colors`(50+ 常數)+ `shared.macro_thresholds_v2`(_PMI_SITUATION_BELOW)完全延用,0 新 SSOT,0 新 hex literal
  - **驗證**:13 + 109 tests passed(test_tab1_macro + test_app_smoke),CI Fast + Schema + Slow tests 全綠

- **v19.253-257 Phase 4 全 SSOT 收口 — B1+B2+B3+B4+B5 一鍋燴(2026-06-30,PR #477,squash `bef2426`)**:
  - **背景**:User 主動要求 B1-5 全做。深度盤點發現 720+ hex literal 散落 ~50 production 檔,2 hour 連續 5 batch 收口完成
  - **B2**(`dc8a4bc` v19.253):`#888` 短寫全站 → `TRAFFIC_NEUTRAL`,165 處 / 26 檔,0 新 SSOT(用既有)
  - **B1**(`e8ea6cf` v19.254):GitHub Dark Theme palette → `GH_BG_PRIMARY/CARD/HOVER/BORDER` + `GH_FG_PRIMARY/SECONDARY/MUTED` + `STREAMLIT_BG`,238 處 / 27 檔,**8 個新 SSOT 常數**
  - **B5**(`8f7e369` v19.255):Dark accent BG → `BG_DARK_NAVY_1/2/3/4` + `BG_DARK_RED_1/2` + `BG_DARK_AMBER_1/2` + `BG_DARK_GREEN_1`,60 處 / 8 檔,**9 個新常數**
  - **B4**(`09f9e35` v19.256):Material extended palette → `MD_BLUE_300/500` + `MD_GREEN_A200/A400` + `MD_DEEP_ORANGE_400` + `MD_AMBER_300` + `MD_ORANGE_300` + `MD_PURPLE_500`,99 處 / 21 檔,**8 個新常數**
  - **B3**(`4313663` v19.257):灰調漸層短寫 + 純白 → `GRAY_44/55/66/AA/BB/CC` + `WHITE`,158 處 / 22 檔,**7 個新常數**
  - **修補**(`9de1c3d`):Slow tests 失敗 14 處 NameError → 根因 B1/B3 script import-merge 邏輯對 inline trailing comment 處理有 bug → `app.py:23` 補 `GH_FG_PRIMARY` + `ui/sidebar.py:19` 修 WHITE 漏在 comment 內
  - **總計**:**32 個新 SSOT 常數** / **720+ hex literal 收口** / **~50 production 檔** / **0 視覺變化**(SSOT 值 = 原 hex)
  - **方法論**:Bulk Python script(per-hex per-file replace_all + AST-aware import 處理 + smart f-string detection + short-hex 精確匹配),B5 學到教訓後 B4/B3 改進
  - **驗證**:Targeted tests 各 cluster 全綠(B2:94 / B1:98 / B5:86 / B4:103 / B3:91 = 472 tests),CI Fast+Schema+Slow 全綠
  - **架構**:0 L1→streamlit / 0 L2→I/O / 32 新常數全有 caller / 0 違憲新增
  - **跳過長尾**:各 cluster < 5 出現 hex(~50 處)留 BACKLOG,屬 component-specific,擴 SSOT ROI 不對等

- **v19.252 Phase 4A v19.68 TRAFFIC SSOT 升級補完(2026-06-30,PR #476,squash `3a50309`)**:
  - 背景:`shared/colors.py:17` docstring 宣告 v19.68 已升級 TRAFFIC 4 色 GitHub-style → Tailwind-style,但深掃發現 production 還散 104 處舊 hex(`#f85149`/`#d29922`/`#3fb950`/`#6e7681`),屬「升級半途而廢」
  - 收口:88 處 production literal + 13 處 test assertion → `TRAFFIC_RED/YELLOW/GREEN/NEUTRAL` SSOT
  - 動 13 production 檔(`ui/tab1_macro.py` 36 處 hotspot)+ 3 test 檔(2/2/3 assertion)
  - 0 新 SSOT 常數(全用既有);test assertion 改鎖 SSOT 而非 literal,未來再改色不撕 test
  - 視覺色變化:Tailwind 比 GitHub 更鮮豔(`#f85149` 暗紅 → `#ef4444` 亮紅 等),v19.68 已決定,本 PR 讓 production 真的用新色
  - Tests:全測 2258 passed,本地 + CI 雙綠
  - 詳:PR #476 / 16 files / +237 / -102

- **v19.251 深層稽核排毒 — Phase 1+2+3 一次到位(2026-06-30,PR #475,squash `62b6e82`)**:
  - User 指派《逆向工程稽核》— 深層稽核發現 ARCHITECTURE.md 文件 drift、3 個 0-/低-caller dead/shim 檔、5 個 UI→L1 facade 未登錄例外
  - Phase 1 doc-sync:ARCHITECTURE.md v11.0 → v12.0(新增 §0' 反映 6 個新 subpackage)+ CLAUDE.md 5 處對齊
  - Phase 2:`services/valuation.py` 整檔退役(-342 LOC,0 production caller)+ tests + provenance smoke + macro_buckets source 字串 + external_market docstring
  - Phase 3:`services/macro_weights_store.py` shim 拔除(9 production caller + 3 test patch migrate `services.macro_weights_store` → `services.macro.weights_store`) + `services/risk_calibration.py` shim 拔除(3 test migrate)
  - 例外清單同步:EX-PASSTHRU-1 補登 3 fn(`fetch_fund_by_key` / `fetch_nav_history_long` / `diagnose_fx_sources`)
  - Net diff:**−161 LOC**(18 檔 / +237 / -398),3 production file deleted + 1 test orphan
  - Tests:2258 passed / 8 skipped / 1 deselected(pre-existing 網路 flaky)
  - 詳:PR #475 / squash commit `62b6e82`

- **v19.250 B Route C-1 pending review ceremony 整批拔毒(2026-06-30)**:
  - User 訊號:總經 Tab 顯示「X 筆新權重待審核」橘色 banner,User 確認該 ceremony 已不再使用 → 選方案 B 拔 pending UI,保留 active.json 注入機制讓 production scoring 正常運作(可手動編輯 active.json)
  - 退役:`services/macro/weights_store.py` 的 pending 6 fn(load_pending / save_pending / approve_pending / reject_pending / has_pending / build_payload_from_multifactor)+ pending helper + GS pending CRUD + PENDING_MODES 常數 + dual-mode 路由,4 個 active fn(load_active / apply_weight_overrides / get_verdict_cutoffs / get_weight_override / get_phase_thresholds)100% 保留
  - 退役:`services/ai_advisor_pending.py::explain_pending_weights` + 3 helper(pending 事後 AI 解讀);**保留**`recommend_weights` + 3 helper(AutoSearch top-5 winners 仍 reuse)
  - 退役:`ui/tab1_macro.py` 的 `_render_one_pending_banner` + `_render_pending_weights_banner` + render_macro_tab caller + 2 處 stale docstring
  - 退役:`ui/tab_crisis_backtest.py` 的 `_render_ai_recommendation_section`(事前 AI 提交建議) + `_render_pending_submit_section`(📌 提交按鈕)+ 兩處 caller
  - 退役:`services/config/macro_weights_pending.json`(active.json 留)
  - 退役:`tests/test_macro_weights_store.py` 的 40 個 pending 系列 test(留 23 個 active 系列)
  - 保留:6 個 production scoring consumer 全 0 改動 — `composite_score` / `explain` / `causal_sankey` / `realtime_signal` / `calibration/macro_score` / `ui/helpers/macro/helpers`
  - 保留:AutoSearch AI 比對線 `_render_autosearch_ai_section` + `recommend_weights` 完整不動
  - Net diff:**−857 LOC**(115 insertions / 972 deletions across 5 檔 + 1 JSON 刪)
  - Tests:2266 passed / 0 regression(全 fast suite)
  - 4 例外清單對齊:EX-CACHE-1 / EX-AI-1 / EX-CRUD-1 / EX-PASSTHRU-1 全不受影響

- **v19.249 R25 doc-sync — CLAUDE.md §8.2「白話名 / 3 鐵盒」對照欄(2026-06-30)**:
  - User 上個 turn 把 SaaS audit template 套進來提議「植入 DataFetcher / CalcEngine / ComponentUI 三鐵盒架構」;深挖發現 3 鐵盒模型 = 既有 L1/L2/L3 100% 對齊,且 L0 Infra/Shared 在 3 鐵盒沒有對應位(塞進任一鐵盒都違 §8.2 硬規則第 3 條)
  - 取代「植入第二份架構」(A 改名 / B 包大 class / C 加 facade,3 條都負 ROI),改純 doc 加白話對照欄
  - `CLAUDE.md §8.2`:既有 4 層表加第 2 欄「白話名」;表前加 1 段對照敘述(`DataFetcher = L1` / `CalcEngine = L2` / `ComponentUI = L3`,L0 標「跨層基底」)
  - 強調「3 鐵盒只當捷思詞,實際 import path 仍走 `repositories/` / `services/` / `ui/`」防誤解
  - 0 production code 改動;0 layer violation 復查維持(R12/R15/R16 4 例外全 valid)

- **v19.248 R22+R23+R24 fetch_holdings 抓取鏈完整修補(2026-06-29)**:
  - **R22** — `fetch_holdings` 依 `_INSURANCE_SUBDOMAIN_HINTS` 展開保險平台 portal 子網域(JF→jpmorgan/jpmf/jpmfund 等 10 prefix × 1-5 portal × yp013xxx+wq06 兩頁);JFZN3 fallback chain 6 → 12 URL,TLZF9/FLFM1 等保險代碼同理覆蓋
  - **R23** — `_daily_cache` 加 `cache_if` predicate,失敗結果(empty dict / `source: *all_failed*` / None / 空 Series / 空 list)**不入 cache**;修 R20 引入的「當日第一次失敗鎖整天」鎖死現象;`cache_info` 加 `uncached_fail` 計數供 audit
  - **R24** — pre-commit `end-of-file-fixer` 對 23 個歷史檔尾巴空行清掃 + 2 JSON 加 final newline(non-functional,修 PR #472 CI Fast checks 紅)
  - 完整 chain:R18 結構性偵測 → R19 fallback msg → R20 daily cache → R21 6 URL → **R22 insurance portal 展開** → **R23 失敗不入 cache** → R24 CI 修補
  - Tests:27/27 全綠(R22 4 新 + R23 7 新 + R20 8 + R21 4 + R18 4)
  - 詳:PR #472 / squash commit `c61ef8e`

- **v19.247 R16 EX-PASSTHRU-1 部分升級 — get_latest_fx 走 L2 facade(2026-06-29)**:
  - 新增 L2 facade `services/fund_service.py::get_latest_fx`(thin wrapper 呼 L1 實作)
  - 9 UI caller migrate import path L1 → L2(investment.py / checkup.py / v2_editor.py / d_mode.py / tab_fund_grp_health / tab2 / tab5 / tab3_portfolio / tab3_t7_ledger)
  - EX-PASSTHRU-1 對象縮減 3 → 2 fn(`tdcc_search_fund` + `fetch_market_news` 維持,caller 數少升級 ROI 不對等)
  - test 守門 `tests/test_tab2_single_fund.py:103` regex L1→L2 path 對齊
  - L1 業務 0 改動(`diagnose_fx_sources` internal use 保留),架構意義:UI 不再直接 bypass L2 對 FX data 取得
  - 50 守門 test 全綠 + 2258 broader test(R15)0 regression

- **v19.246 R15 4 例外二輪深挖 — EX-PASSTHRU-1 framing 重大修正(2026-06-29)**:
  - **EX-AI-1**:caller 從 str 萃取數字違規復查 0 處(grep `re.search/json.loads/float(resp)` 全網 0 hit)→ 維持
  - **EX-CRUD-1**:三個 repo(policy / snapshot / ledger)0 HTTP I/O / 0 cache / 純資料層 → 維持
  - **EX-CACHE-1**:hot_money_repository 仍唯一適用(`@st.cache_data` ×2)→ 維持
  - **EX-PASSTHRU-1 重大發現**:**原 doc framing 錯誤** — 3 fn 實際是 **L1 facade** 不是 pass-through:
    * `get_latest_fx`:4 源 fallback chain(Yahoo → FRED → open.er-api → Frankfurter)+ positive-only `_FX_CACHE` TTL_300 + currency normalize
    * `tdcc_search_fund`:多 endpoint 整合(TDCC 3-2 + 3-4)+ dedup + nav merge
    * `fetch_market_news`:11 RSS feeds + keyword filter + systemic risk classify + sort
    * 升級觸發條件「多源 fallback / 結果後處理 / 自帶 cache」**理論上 3 fn 全達標**
    * 但實務評估:3 fn ≥1 年穩定 + blast radius 大(get_latest_fx 9 caller / tdcc 1 / news 2)+ 升級需完整重寫 fallback chain(R8 EX-L1ORCH-1 規模)→ §-1 不主動推進
    * doc framing 修正:從「pass-through 用 + 無 L2 業務值」改為「L1 facade(multi-source orchestration + cache + 後處理 + 業務分類)」,升級觸發條件改寫為「user 明確指派 / 第 5 個 source / 後處理 bug」
  - 0 code change,純 doc framing 對齊

- **v19.244 R12 4 例外復查 + EX-PASSTHRU-1 doc 漂移修(2026-06-29)**:深挖 EX-CACHE-1 / EX-AI-1 / EX-CRUD-1 / EX-PASSTHRU-1 4 例外:
  - **EX-AI-1**:R7 清死碼後 public fn 4(`assign_asset_role` / `analyze_portfolio_mk_advisor` / `get_gemini_keys` / `gemini_generate`),caller 全用 markdown 渲染,無從 str 萃取數字違規 → 維持
  - **EX-CRUD-1**:三個 repo(policy / snapshot / ledger)caller 全在 ui/ + 1 處 scripts/(migration),符合 EX-CRUD-1 範圍 → 維持
  - **EX-CACHE-1**:scope 縮窄 — 實際適用 `repositories/hot_money_repository.py`(`@st.cache_data` ×2),`news_repository.py` docstring 明說「不 cache」;`ledger_repository.py` + `snapshot_repository.py` docstring 明說「純資料層不 import streamlit」,非 EX-CACHE-1 對象。doc audit 註明
  - **EX-PASSTHRU-1 doc 嚴重漂移**:`get_latest_fx` doc 寫 1 處 caller(`tab3_portfolio.py:2216`),**實際 9 caller files / 18 call sites**(R4 後沒更新),範圍急速擴散但**升級觸發條件未達到**(無多源 fallback / 結果後處理 / cache 集中已自帶);doc 更新完整 caller list,例外維持有效
  - 0 code change,純文件對齊 + 例外規則復查
  - 4 例外全部 valid,無升級觸發

- **v19.243 R11 Welford 顯式 深挖維持 WONTFIX + 副產品 §4.3 浮點 == 違憲修(2026-06-29)**:
  - **Welford 深挖確認 ROI=0**:`rolling().std()` 4 處(BB band 3 + liquidity z-score 1)+ `series.std()` 12 處,全部單序列小 N(<1000 點),pandas 內部已 Welford-friendly C-level loop。**0 處 N×T 大序列場景** / **0 處 manual sum-of-squares** / **0 處 catastrophic cancellation**。WONTFIX 維持
  - **副產品 — §4.3 浮點 == 違憲修**:`scripts/calibrate_macro_score.py:234` 原 `xr.std() == 0 or yr.std() == 0` 違 CLAUDE.md §4.3「浮點比較禁止 ==」,改 `np.isclose(..., 0.0, atol=1e-12)`(degenerate spearman 同 deterministic 行為)
  - WONTFIX 清單從 1 → 0(全部 active WONTFIX 復查完成);僅留**半結等 user 觸發**項(F-GRAY-4 PMI/CPI/HY harmonize + SPEC §16.2 macro_thresholds_v2 migration + check_eating_principal_1y_mk Phase B caller 統一)

- **v19.242 R10 F-PROV-1 sentinel 深挖 + dead chain 拔除(2026-06-29)**:F-PROV-1 sentinel WONTFIX 復核維持(schema-additive 已 100% pass,改 dataclass ROI=0),但深挖 audit 工具發現 bug 後重跑找到 **dead code chain** 拔除:
  - `fetch_fund_structure` 整 fn(132 LOC,0 production caller,fund_fetcher.py:467 re-export shim 列名但實際 0 call site)
  - `STRUCTURE_PAGES` constant(9 LOC,獨 caller = fetch_fund_structure)
  - `_parse_pct_table` helper(30 LOC,獨 caller = fetch_fund_structure)
  - `fund_fetcher.py:460-470` re-export shim 11 LOC
  - 對應 `repositories/fund/fx_and_main.py` 模組 docstring 更新
  - **總計 -183 LOC**(repositories/fund/fx_and_main.py -183 / fund_fetcher.py -8)
  - 39 個 fetcher 全部覆蓋 source/fetched_at (F-PROV-1 audit 真正 0 MISS,我的初版 audit 工具 100-line window 太窄漏看)
  - WONTFIX 清單從 2 → 1(剩 Welford 顯式,確認 ROI=0)

- **v19.241 R9 F-SCHEMA-1 全結案 文件漂移修(2026-06-29)**:深挖 Phase C/D 發現**早已落地**,CLAUDE.md §3.1 過時:
  - **Phase C v19.164 已落地**:`shared/schemas.py` 增 `validate_fund_nav_data_only` + `validate_fund_dividends_data_only`(服務層 data-only,不驗 provenance attrs,允許 cache/test fixture 反序列化序列)
  - **Phase D v19.165 已落地**:`.github/workflows/pr-check.yml::schema-gate` job 跑 6 個 schema test 檔(test_schemas_phase_a/b/b2/b3/b_foreign_flow/c.py)91 tests,failure 阻擋 merge
  - 0 code change,純文件對齊:CLAUDE.md §3.1 從「Phase C/D 留待 user 觸發」改為「全 4 phase 落地」
  - **剩餘 ~10 個 Tier 2/3 fetcher 未驗 schema**(stooq / cboe / defillama / TW macro / news)為次要源,§-1 不主動推進
  - F-SCHEMA-1 從 ⚠️ 半結 → ✅ 全結;WONTFIX 從 3 → 2(剩 F-PROV-1 sentinel + Welford 顯式)

- **v19.240 R8 EX-L1ORCH-1 升級退役(2026-06-29)**:深挖發現升級觸發條件實質達標:
  - 違憲 3 個 L2 symbol(`calc_metrics` + `reconcile_fund_annual_return` + `reconcile_dividend_yield`)
  - 80+ LOC L2 業務判斷(perf 注入 / window 閾值 / 對帳 % vs decimal)push 回 L1
  - 觸發條件 (a)+(b) 都達標 → 採方案 (b) 拆 return + L2 wrapper
  - **新增 L2 SSOT** `services/fund_service.py::finalize_fund_metrics(result)` + 2 enriched wrapper(`fetch_fund_by_key_enriched` / `fetch_fund_from_moneydj_url_enriched`)
  - **L1 純化**:`repositories/fund/fund_orchestration.py::_finish_metrics` 從 100 LOC → 22 LOC(只剩 source_trace + normalize_result_state);`fx_and_main.py::fetch_fund_by_key` 移除 calc_metrics 收尾;`fund_orchestration.py::fetch_fund_from_moneydj_url` 移除 inline calc_metrics + perf 注入
  - **Caller migrate** 4 處:`ui/helpers/v2_editor.py:695` + `services/moneydj_fetcher.py:65, 68, 76`(3 sites 共用同一 enriched alias)
  - **L1→L2 violation**:3 → 0(完全清零)
  - **EX-L1ORCH-1 退役**(CLAUDE.md §8.2.A 標 strikethrough,§0 收尾紀錄同步)
  - **副產品**:test_realtime_signal.py 3 處 patch path 從 R2 stale `services.macro_service.*` 改 `services.macro.*`;test_ai_prompts.py 3 dead test 補清(R7 漏網)
  - 2254 broader tests 全綠

- **v19.239 R7 EX-AI-1 死碼清(2026-06-29)**:5 個 WONTFIX 深挖,4 個確認維持,EX-AI-1 找到 4 個真死碼:
  - `services/ai_service.py` -216 LOC:`_build_snapshot`(124)+ `analyze_global`(25)+ `build_stale_flags`(31)+ `event_impact_analysis`(34)+ 連動 import / docstring 清理
  - `services/ai_prompts.py` -70 LOC:`build_global_prompt`(46)+ `build_event_impact_prompt`(24)兩個 dead prompt builder + 對應 section header + docstring 公開 API 清單更新
  - **EX-AI-1 例外規則(LLM 回 str)維持有效**:本輪只清死碼,不動 caller 介面
  - 全 113 守門 test 綠燈;0 caller 殘留 dead reference;Surviving public API:`assign_asset_role` / `analyze_portfolio_mk_advisor` / `get_gemini_keys` / `gemini_generate` / `_gemini` / `_format_fund_holdings` + `build_mk_advisor_prompt` / `build_structured_summary_prompt`

- **v19.238 EX-L1ORCH-1(2026-06-29)**:架構違憲深挖 — `repositories/fund/` 4 處 L1→L2 `calc_metrics` import 復查:
  - **2 處死 re-export 清除**:`_helpers.py:64` + `nav_metrics.py:28`(純 `noqa: F401` 0 內部 caller)+ 連動清 `_helpers.py` 過時 `_finish_metrics` 註解(`_finish_metrics` 已於 P1-5 搬 `fund_orchestration.py`)
  - **2 處真呼叫登錄例外 EX-L1ORCH-1**:`fx_and_main.py:27`(於 `fetch_fund_by_key` 收尾呼叫)+ `fund_orchestration.py:30`(於 `_finish_metrics` + `fetch_fund_from_moneydj_url` 收尾)— L1 orchestrator(1766 LOC)抓 NAV+配息後即時 packaging `result["metrics"]` dict;三條替代路徑(整檔搬 L2 反向違憲 / 拆 return 改公開 API 10+ caller / lazy import 純 cosmetic)皆更差,§8.1 step 6 例外正解
  - **緩解規則**:本例外僅限 `calc_metrics` 單一 symbol;同檔嚴禁追加其他 L2 import;升級觸發 = orchestrator 需呼 ≥2 個 L2 symbol 或 L2 push 業務判斷回 L1
  - 86 守門 test 全綠;CLAUDE.md §0 收尾紀錄 + §8.2.A 例外清單 + 對應檔註解三同步

- **v19.112 DeadCodeWave3(2026-06-24 session 收尾)**:本 session 累計 5 PR(#348-352)merged → main、無 open PR。
  - **PR #348 v19.108 F-RECON-1 macro_health 雙演算法**:`services/macro_service.py` 新增 `calc_macro_phase_zpct(indicators)` Z-score 百分位演算法(對稱主路徑 `calc_macro_phase`,使用 `math.erf` 實作 Φ(z) 無需 scipy);新建 `services/reconcile.py:reconcile_macro_health` 處理 score-disagree-but-phase-agree 場景(回 `phase_agree` 狀態);加 `_ZPCT_REVERSE_KEYS` SSOT + 14 unit tests(`test_macro_health_zpct.py`)
  - **PR #349 v19.109 立 §-1 工作準則**:CLAUDE.md 新增 §-1「沒實際 bug / 沒具體需求 → 不要動」最高鐵律,凌駕 §0~§8;標準 default = 等指令不主動找事;3 項 WONTFIX 結案(F-SCHEMA-1 pandera / F-PROV-1 phase 22+ / F-RECON-1 phase B/C)
  - **PR #350 v19.110 Wave 1 死碼清理**:12 處 F401 unused imports + 4 處 F841 dead 賦值,-24 LOC,行為 0 改
  - **PR #351 v19.111 Wave 2 死碼清理**:4 處 F841 真 dead 賦值(經 grep / caller 驗證),-5 LOC
  - **PR #352 v19.112 Wave 3 死碼清理**:刪 v19.36/v19.37 確認拒絕的 screener 5 模組(`tab_fund_screener.py` + `tab_fund_screener_v2.py` + `fund_screener.py` + `screener_v2.py` + `dividend_health_discoverer.py`)+ 對應 3 個 test,-2,224 LOC
  - **累計成效**:~2,253 LOC 死碼清理(Wave 1+2+3 含 1,943 LOC 退役 screener)+ §-1 工作準則建檔 + F-RECON-1 phase A 落地;14 個 test 全綠;無 open PR 待 merge

- **v19.74 Fund-Const-1 W1+W2 @ <merge>**：資料完整性憲法 v3 導入(Stage 1+2 已合)+ 全庫稽核 ~155 條(高 88/中 50/低 17)+ W1 機械修正 26 處 + W2 SSOT 收斂 ~30 處(11 檔 +200/-95 含新 `shared/signal_thresholds.py`)。**前置**:v19.73 PR `<merge>` 完成 Stage 1+2 — 新 CLAUDE.md(440 行,§0-§8 + EX-CACHE-1/EX-AI-1 已知例外)+ PROCESS.md(原 Core Protocol v2.0 並存策略 B 拆檔)。**Stage 2 audit**(7 並行 Explore agent,1 commit 不修):§1 Fail Loud 104(87 高 / 17 中)+ §2 SSOT 38 + §3 magic 27 + §4 units 19 + §4 lookahead 8(3 高:macro_score_calibration.py:202 shift(-horizon)、multi_factor_optimization.py:354 shift(-fwd_days)、crisis_strategy_grid.py:158 reindex ffill 無 limit)+ §8 架構 37+(R4 UI→L1 28 處最重)+ §6 cross 48,去重後高嚴重度 ~88。**Wave 1 機械修正**:(1) W1-A 19 處 bare `except:` → `except Exception:`(`repositories/fund_repository.py` 18 + `services/fund_service.py` 1,行為等價只縮窄 catch 排除 KeyboardInterrupt/SystemExit);(2) W1-D 6 處 `datetime.utcnow()` → `datetime.now(timezone.utc)`(`services/auto_search.py`,修 Python 3.13 deprecation);(3) W1-E 1 處 `score == 0.0` → `math.isclose`(`services/macro_explain.py:139`,§4.3 容差比較)。**Wave 2 SSOT 收斂**:新 `shared/signal_thresholds.py`(20 常數,對稱 Stock 端 17 常數)— TRADING_DAYS_PER_YEAR / SAHM_RECESSION_THRESHOLD / CFNAI_RECESSION_THRESHOLD / RECESSION_LOGIT_COEF_SPREAD&INTERCEPT / SHADOW_FUND_THRESHOLD&JACCARD&COSINE / NEAR_DIVIDEND_WARNING_PCT / RISK_SCORE_(VIX/HY/YIELD)_WEIGHT / LIQUIDITY_(XCCY/CARRY/MOVE)_WEIGHT / TPI_(BUSINESS/FINANCIAL/MONETARY)_WEIGHT / SIGMA_(VERY_HIGH/HIGH/LOW)_CUTOFF / HOLDINGS_NAV_SANITY_(LOWER/UPPER)_RATIO。8 caller 檔遷移:fund_service.py(10× 252 + NEAR_PCT + 4× holdings sanity)+ macro_service.py(SAHM ×3 + CFNAI + logit ×2 + TPI 3-weight)+ portfolio_service.py(shadow 3 sites)+ precision_service.py(risk 3-weight)+ risk_calibration.py(risk 3-weight 與 precision 同步)+ liquidity_engine.py(liquidity 3-weight)+ macro_explain.py(σ 6-cutoff)+ fund_dividend_calculator.py(NEAR)。**驗證**:11 module import smoke OK(production entry `fund_fetcher` 先 load 才能繞 §8 R5 既有循環)+ grep `^\s*except:$` audit 範圍零殘留 + `252` 殘留僅 1 處(comment 註解)+ pytest 既有測試未跑(quick check)。**Wave 3-5 延後**(獨立提案需設計決策):W3 §8 架構 R4/R5/R1/R2(34 處,需服務層擴展+反向 import 拔除);W4 §1 Type E `return None` 71 處 → raise(需逐 caller 評估 try/except 包裹);W5 vintage data path 實作(`realtime_start` 對齊回測 macro)。**[邏輯]** W1 行為等價(except 縮窄、datetime API 等價、math.isclose 對 default 0.0 等價);W2 數值字面值與 SSOT 常數值完全相同 → 零數值漂移。**[邊界]** 量綱單位都帶後綴(`_RATIO` / `_PCT` / `_DAYS` / `_THRESHOLD` / `_CUTOFF`)避免 §4.1 陷阱;`fund_service.py` 還原 NAV 序列 + `_window_actual_days = 365`(calendar)保留不動(原本就是日曆日)。**[效能]** 純 module-level Name reference,編譯後與字面值等價,0 新 IO,既有 cache 不 invalidate。**[Debug]** 未來改 SAHM threshold 只動 1 處;`shared/signal_thresholds.py` 提供未來新 signal/score 常數的單一登錄處;對稱 Stock 端 `shared/signal_thresholds.py`(17 常數)+ ttls + fred_series + colors 四檔 SSOT 集中。**架構意義**:Fund-Const-1 三階段循環(Stage 1 填寫 → Stage 2 稽核 → Stage 3 Wave 1+2 修正)完整收尾;對照 Stock-Const-3 v18.241 同套流程,Fund 端 SSOT 紀律已超前(ttls + fred_series + colors + MACRO_THRESHOLDS + signal_thresholds = 5 檔集中,Stock 端 4 檔)。

- **前一版 refactor(thresholds) v19.72 PR @ <merge>**：MACRO_THRESHOLDS dict 補完 13 entries。**根因**：dual SSOT audit Fund #5 — `repositories/macro_repository.py:180-195` MACRO_THRESHOLDS dict 13 entries 但 production `services/macro_service.py` 對應的 16+ 指標散落 inline conditional（`v<4.5` / `v>6` 等 hardcoded），dict 僅 test 引用形同 dead doc，無 SSOT consumption。**修法**（1 檔 +18/-3）：純加 13 entries 對應 inline 等價閾值 — FED_RATE / UNEMPLOYMENT / PPI / COPPER / CONSUMER_CONF / JOBLESS / SAHM / SLOOS / LEI / CONT_CLAIMS / M2_WEEKLY / INFL_EXP_5Y / PERMIT_HOUSING；保留 inline 不動（行為零變更）。**例外**：FED_RATE 只記 red_above=5（green=v<prev 動態，schema 不容）；NEW_HOME / ADL（動態）+ NFP（5 級多階）暫不收錄。**驗證**：26 entries 完整 + red/yellow 反序檢查全綠 + 既有 test_macro_core 子集 assert 不破。**[邏輯]** 純加 dict entry, services/macro_service.py inline 0 改 → 行為等價零回歸；dict 從「test-only doc」變「production-grade SSOT 文件」。**[邊界]** 既有 13 entries 不動（VIX/CPI/PMI/HY_SPREAD/Yield curves/M2_YOY/FED_BS_YOY/cross-rates），新 13 entries 命名與 inline R[key] 對齊。**[效能]** 0 新 IO；dict literal eval ns 級；既有 cache pattern 不變。**[Debug]** 未來 macro_service.py refactor consume dict 走 `MACRO_THRESHOLDS["UNEMPLOYMENT"]["green_below"]` 鋪好基礎；M2_YOY vs production R["M2"] / FED_BS_YOY vs R["FED_BS"] 命名差異留作下次 rename PR；CPI 1.5% vs L595 邏輯 1% 不一致已 audit 標記，但本 PR 不動行為。

- **refactor(colors) v19.71 PR #308 @ 0a14ecd**：MATERIAL_* hex SSOT 收斂 251 處 / 18 production 檔。**根因**：dual SSOT audit Fund #1 — `shared/colors.py` 已定義 `MATERIAL_GREEN/RED/ORANGE` 但 macro_card.py 之外 18 檔散落 251 處 `"#00c853"/"#f44336"/"#ff9800"` 字面值 import。**修法**（18 檔 +273/-238）：(1) services 6 檔（macro_service 77 / fund_service 11 / precision_service 10 / liquidity_engine 5 / cluster_calibration 3 / macro_explain 2）+ ui 7 檔（tab1_macro 18 / tab2_single_fund 33 / tab3_portfolio 27 / tab3_t7_ledger 5 / tab5_data_guard 16 / tab6_manual 4 / tab_crisis_backtest 2）+ ui/helpers 4 檔（macro_helpers 15 / data_registry 24 / fund_grp_health_extras 10 / fund_checkup 6）+ ui/components/mk_clock 1。(2) `replace_all "#00c853"` → `MATERIAL_GREEN` 等 standalone-quoted literal 安全替換（CSS 嵌入 hex 不會誤觸，外圍 quote char 隔離）。**例外**：22 處 CSS 字串嵌入式 hex（如 `<div style='border:1px solid #ff9800;...'>`）需轉 f-string interpolation，留作 phase 2 獨立 PR；5 處 test fixture 保留字面值。**驗證**：ast.parse 19 檔全綠 + 6 service modules runtime import OK（UI 走 streamlit 跳過）+ grep 殘留 production standalone-quoted = 0。**[邏輯]** 251 hex 字面值 → 1 SSOT 收斂；常數值 `#00c853/#f44336/#ff9800` 字面不變，行為完全等價。**[邊界]** CSS 嵌入 hex 保留 inline 不動；test fixture / shared/colors.py 定義不動。**[效能]** 0 新 IO；module-level Name reference 編譯後與字面值等價。**[Debug]** 未來改 palette 只動 1 處（`shared/colors.py`），18 module 自動同步；對稱 v19.70 fred_series + v19.69 ttls + v19.68 traffic 三棒 shared/ SSOT 集中模式。

- **refactor(fred_series) v19.70 PR #307 @ 046b359**：FRED Series ID magic string SSOT 收斂 40 處 / 10 production 檔。**根因**：dual SSOT audit Fund #3 — `fetch_fred("DGS10", ...)` / `fetch_fred("BAMLH0A0HYM2", ...)` 等 FRED series ID magic string 散落 21 處直接 call + 25 條 `fetch_fred_batch` + 3 個 `_FRED_SERIES_MAP` / `_FRED_FX_MAP` lookup dict + 22 個 FactorSpec series_id field 共 ~40 處；34 unique series 跨 8 module 並存，未來 series rename / version migration 需散修。**修法**（11 檔 +267/-89）：(1) 新建 `shared/fred_series.py` 40 個 `FRED_*` 語意常數，分 11 類別（Treasury yields / Money supply / Credit spreads / FX / Inflation / Labor / Activity / ISM-PMI / Regional Fed / Financial conditions / Volatility）；對稱 `shared/ttls.py` Fund-only 設計（NOT sync to Stock，Stock 端不消費 FRED）。(2) 替換 10 production 檔：`services/us_liquidity_engine.py`（4 calls）+ `services/liquidity_engine.py`（DXY + JPY/CHF loop 2 sites）+ `services/risk_radar.py`（3 calls）+ `services/valuation.py`（GDPNOW）+ `services/multi_factor_optimization.py`（22 FactorSpec series_id + 1 direct call）+ `services/macro_service.py`（25-series batch + 7 individual calls）+ `services/macro_score_calibration.py`（_FRED_SERIES_MAP 10 entries）+ `repositories/macro_repository.py`（PhilFed/OECD proxies 2 calls）+ `repositories/fund_repository.py`（_FRED_FX_MAP × 2，5 FX pairs each）+ `ui/helpers/data_registry.py`（_FRED_SERIES_MAP 20 entries）；(3) 刻意排除 `test_macro_core.py` / `test_liquidity_engine.py` / `test_macro_validation.py` / `test_update_macro_history.py` 5 檔 fixture literal（test contract）+ `shared/fred_series.py` docstring 範例代碼（純文件）。**驗證**：ast.parse 11 檔全綠 + 9 production modules import smoke OK + `from shared.fred_series import FRED_*` 40 常數 value-asserted（`FRED_DGS10=='DGS10'` / `FRED_HY_SPREAD=='BAMLH0A0HYM2'` / `FRED_FED_BS=='WALCL'` / `FRED_DXY=='DTWEXBGS'` / `FRED_PHILLY_FED=='GACDFSA066MSFRBPHI'`）+ AST scan macro_score_calibration._FRED_SERIES_MAP 10 entries 全部走 FRED_* 引用零 literal + grep `fetch_fred\("` 排除 test/docstring 後零 production 殘留 + `FACTOR_POOL` 26 specs / `FACTOR_POOL_BY_KEY['HY_SPREAD'].series_id == 'BAMLH0A0HYM2'` 驗證 dataclass 引用語意完全等價。**[邏輯]** 40 處 → 1 SSOT 收斂；40 語意常數涵蓋 11 類別；單一字串值改動只需動 1 處（FRED 罕見但有過 rename，例如 `SAHMCURRENT` vs `SAHMREALTIME`，已有兩 vintage 共存）。**[邊界]** 純常數 module-level eval 零 IO；FactorSpec `@dataclass(frozen=True)` 改 string 為 module-level Name reference 完全等價；lookup dict 引用 module 常數編譯後與 literal 完全等價。**[效能]** 0 新 IO；ns 級初始化；FRED IDs 完全不變 → 既有 `fetch_fred @_ttl_cache(1800/32)` cache 不會 invalidate；既有 `fetch_fred_batch` 並行模式不受影響。**[Debug]** 改 FRED series ID 只動 1 檔 1 行（例如 `T10Y3M` deprecated → 切回 `T10Y3MFF` 只需 `shared/fred_series.py:FRED_T10Y3M` 改值）；10 module 自動同步；對稱 `shared/ttls.py` v19.69 同質設計，shared/ 目錄至此 4 檔（`__init__.py` + `colors.py` + `ttls.py` + `fred_series.py`）。**架構意義**：dual SSOT audit 10 條中第 7 條交付（Fund #3 fred_series），累計 5 Stock + 2 Fund = 7/10。下一步候選：Stock #3（PMI/M2 fetcher 重構 ~200 行）/ Fund #1（MATERIAL_* hex codes macro_card sparkline）/ Fund #5（MACRO_THRESHOLDS dict 不完整 — FED BS/M2 thresholds inline at macro_service.py:652-654, 737-739）。

- **前一版 refactor(ttls) v19.69 PR #306 @ 7fff19c**：快取 TTL magic number SSOT 收斂 22 處 / 9 production 檔。**根因**：dual SSOT audit Fund #2 — `@_ttl_cache(ttl_sec=N)` / `@st.cache_data(ttl=N)` literal 散落 22 處 9 檔，7 unique 值（1/60/300/600/900/1800/3600）無集中常數；對稱 Stock #1 v18.236（已交付 60+ 處 / 20 檔 / 8 常數）。**修法**（10 檔 +57/-22）：(1) 新增 `shared/ttls.py` 6 常數 `TTL_1MIN=60` / `TTL_5MIN=300` / `TTL_10MIN=600` / `TTL_15MIN=900` / `TTL_30MIN=1800` / `TTL_1HOUR=3600`（Fund-only，**不**進 `sync_to_stock.sh`，與 `health_thresholds.py`/`thresholds.py` 同類 Stock-only 對稱）；(2) 22 處替換：`hot_money.py` 2 / `ui/helpers/v2_editor.py` 2 / `repositories/fund_repository.py` 3 / `repositories/macro_repository.py` 5 / `services/liquidity_engine.py` 1 / `services/macro_tw_local_fetch.py` 4 / `services/screener_v2.py` 2 / `services/us_liquidity_engine.py` 1 / `services/valuation.py` 2；(3) 刻意排除 `test_fetch_cache.py` 11 處 fixture literal（test contract）+ `infra/cache.py:13` docstring code example。**驗證**：ast.parse 10 檔 OK + `from shared.ttls import *` smoke 數值對齊 + 改後 grep `ttl(_sec)?=\d+` 排除 test/docstring 後零殘留 + Stock 端 `shared/ttls.py` 不受影響（單向獨立）。**[邏輯]** 22 處 → 1 SSOT 收斂；6 常數涵蓋短尾 TTL（1min ~ 1hour），與 Stock 8 常數覆蓋長尾（15min ~ 7day）互補。**[邊界]** 純常數 module-level eval 零 IO；IEEE 754 完全等價（cache 不會 invalidate）；test fixture literal 為刻意行為不動；infra/cache.py docstring example 不需動。**[效能]** 0 新 IO；6 常數 ns 級；TTL 值不變 → 既有 `_ttl_cache` / `st.cache_data` miss/hit pattern 不變。**[Debug]** 未來改 TTL（例如 1800→3600）只動 1 檔 1 行；9 module 自動同步；對稱 Stock #1 v18.236 同質設計，跨 repo cognitive overhead 最小。**架構意義**：dual SSOT audit 10 條中第 6 條交付（Fund #2 ttls），累計交付 5 Stock + 1 Fund = 6/10；shared/ 目錄至此 3 檔（`__init__.py` + `colors.py` + `ttls.py`，後者 Fund-only）。下一步候選：Stock #3（PMI/M2 fetcher 重構 ~200 行）/ Fund #1（MATERIAL_* hex codes macro_card sparkline）/ Fund #3（FRED Series ID 重複）/ Fund #5（MACRO_THRESHOLDS dict 不完整）。
- **refactor(colors) v19.68 PR #305 @ f461186**：TRAFFIC_* SSOT 升級 Tailwind 色板 + services 3 檔 import 統一。**根因**：dual SSOT audit Fund #4 — `services/valuation.py` + `event_calendar.py` 各定義 5 個 local `GREEN/YELLOW/ORANGE/RED/GRAY` hardcoded hex（Tailwind 系 #22c55e/#eab308/#fb923c/#ef4444/#888888），與 `shared/colors.py` 既有 `TRAFFIC_*` GitHub-style 系 (#3fb950/#d29922/#f85149/#6e7681) 並存兩套色板；`services/risk_radar.py` 同樣 4 個本地 hardcoded hex。**統一決策（user 選 B）**：把 `TRAFFIC_*` 升級至 Tailwind-500 系（與 services 對齊），全倉 traffic-light 由沉穩色 → 亮色，**Stock 端 unified_decision / tab_etf_margin_simulator / tab_stock 跟著 sync 變色**。**修法**（4 檔 +29/-24）：(1) `shared/colors.py`：TRAFFIC_GREEN/YELLOW/RED/NEUTRAL 4 hex 升級 + 新增 `TRAFFIC_ORANGE = "#fb923c"`（services 4 級色階用）+ docstring 從「GitHub-style 主用三色」改「Tailwind-style 五色」；(2) `services/valuation.py` + `event_calendar.py` + `risk_radar.py` 移除 14 個本地 hardcoded hex 改 alias-import `from shared.colors import TRAFFIC_GREEN as GREEN, TRAFFIC_YELLOW as YELLOW, ...`（保留 local symbol 不動 caller 8+6+2=16 處 usage）；(3) `scripts/sync_to_stock.sh` 推送 `shared/colors.py` + `__init__.py` 至 Stock 端（Stock PR #243 同步交付）。**驗證**：AST parse 4 檔 OK + import propagation 實測 `services.valuation.GREEN == TRAFFIC_GREEN (#22c55e)` / `event_calendar.RED == TRAFFIC_RED (#ef4444)` / `risk_radar.YELLOW == TRAFFIC_YELLOW (#eab308)` 全 True + `_badge_for(2)` 回紅 / `compute_forward_pe_verdict(15.0)['color']` 回 GREEN。**[邏輯]** 4 → 1 SSOT 收斂（shared.colors.py 唯一來源）+ TRAFFIC_ORANGE 補位完成 5 級色階。**[邊界]** Stock 端 unified_decision / tab_etf_margin_simulator / tab_stock 跟著 sync 變色已 user 確認 OK；TRAFFIC_NEUTRAL 也升至 #888888（services 用作 GRAY 同義）。**[效能]** import 解析 import-time once；0 runtime overhead。**[Debug]** 未來只動 `shared/colors.py` 一處 hex，services 三檔 + 跨倉 Stock UI 自動同步；徹底終結兩套色板共存。**架構意義**：dual SSOT audit 10 條中第 2 條交付（Fund #4 colors + 加 risk_radar.py 完整收斂）；與 Stock PR #243（bare_etf_code 12 處 bypass + colors sync）同梯出貨。下一步候選：Fund #1（colors 更廣 — macro_card sparkline 等 MATERIAL_* 是否也統一）/ Fund #2（TTL 6 值散落 10+ 函式）/ Fund #5（MACRO_THRESHOLDS dict 不完整）/ 等 user 新方向。

- **前一版 perf(macro) v19.67 PR #304 @ 3d7a232**：P1-F2 batch 清單擴 3 條 liquidity FRED — `DTWEXBGS(800)` / `DEXJPUS(400)` / `DEXSZUS(400)` 覆蓋 `services/liquidity_engine.py` 兩 builder（build_xccy_proxy / build_carry_unwind）。**修法**（1 檔 +4/-1）：純擴 `fetch_all_indicators` v19.66 batch 清單從 22 條 → 25 條；無新函數、無 import 變動、邏輯 0 改動。py_compile + AST(batch list 25 specs，3 新 series 標記正確) 雙段驗證通過；`fetch_fred_batch` 機制本身已於 v19.66 (PR #303) 5 case 全綠驗證。**[邏輯]** 純擴清單，sequential cold start ~1~2s → 8-worker batch 並行預熱共享 `fetch_fred @_ttl_cache(30min)`。**[邊界]** 三條 FRED series 命名已查證為合法 FRED ID（DTWEXBGS=美元廣義指數 / DEXJPUS=日圓 / DEXSZUS=瑞郎日匯）；fetch_fred_batch 對單條 series 例外有隔離不中斷其他。**[效能]** `fetch_liquidity_factors` 頂層 30min TTL 過期時，3 子層 FRED 從 sequential ~1~2s → batch ~ms 級；每次 rerun 後續呼叫自然 hit cache。**[Debug]** 與 v19.66 batch 預熱 + v19.65 頂層聚合 cache 連動 — 深水區流動性兩 builder 冷啟動 IO 收斂；STATE.md 維持 v19.66 cache 集中模式註記。**架構意義**：完成 P1-F2 + 與 Stock v18.231 對稱 — Stock + Fund cache 集中模式 6 棒（Stock v18.227/228/229/231 + Fund v19.64/65/66/67）整體交付閉環。下一步候選：等 Streamlit Cloud Fund app rebuild 驗證深水區流動性 tab 載入下降。

- **前一版 perf(macro) v19.66 PR #303 @ b095efa**（commit/code 因撞號保留 v19.65 標籤）：P1-F1 `fetch_all_indicators` 21 條 FRED 批次預熱。**根因**：v19.64 P0 補完 leaf fetcher cache + v19.65 補頂層聚合 cache 後，仍存在「同一 rerun 內 16 條 sequential FRED 首次 cache miss」的冷啟動慢因 — `services/macro_service.py:fetch_all_indicators` 內 21 條 FRED 中只有 5 條（DGS10/DGS2/DGS3MO/HY/M2）走 ThreadPoolExecutor，剩 16 條（ISPMANPMI/WALCL/CPIAUCSL/FEDFUNDS/UNRATE/PPIACO/UMCSENT/ICSA/HSN1F/SAHMREALTIME/DRTSCILM/CFNAI/CCSA/WM2NS/T5YIE/PERMIT/PAYEMS）為 sequential `_fred()` 呼叫，首次冷啟動各 0.2~0.5s × 16 ≈ 3~8s。**修法**（2 檔 +57/-1）：(1) `repositories/macro_repository.py` 新增 `fetch_fred_batch(specs: list[tuple[str, int]], api_key, max_workers=8)` 並行預熱器，內部直接調用既有 `fetch_fred`（已有 `@_ttl_cache(1800/32)`），**不加自己的 cache** 避免雙層失準；異常單條 series 隔離（不中斷其他 series）。(2) `services/macro_service.py:fetch_all_indicators` 入口插入 21 條 FRED 批次預熱（cover 5 條已並行 + 16 條原 sequential = 全部 22 條一次 batch），後續所有 `_fred()` / `fetch_fred()` 呼叫點自然 hit `@_ttl_cache(30min)`，**0 改動現有邏輯**。py_compile 2 檔 + AST 簽章驗證（`fetch_fred_batch: line=254 args=['specs','api_key','max_workers']`）+ Smoke **5 case** 全綠（batch 5 series 並行 73ms / fetch_url 後續 calls 不變 cache hit verified / empty specs+api_key 防呆 / 異常 series 隔離 GOOD1/BAD/GOOD2 → 1/0/1 / **sequential 270ms vs batch 69ms speedup 3.9x**）三段驗證通過。**[邏輯]** batch 不持有自己的 cache、純呼叫包裝 `fetch_fred` 並行調用 → 結果寫入 fetch_fred 的 `@_ttl_cache(1800/32)`；後續 16 處 `_fred()` 自然 hit cache 跳網路 IO；`max_workers=8` 對 FRED API 公開 rate limit (~120 req/min) 安全。**[邊界]** `specs=[]` 或 `api_key=""` → `return {}`（防呆短路）；單條 series fetch_url 例外 → print log + 該 series 進 result 為空 DataFrame，其他 series 不受影響；fetch_fred 既有 cache invalidation 全程沿用 `clear_caches_by_names({"fetch_fred"})`；不依賴 streamlit 約束維持（純 ThreadPoolExecutor + dict）。**[效能]** Fund 首頁總經 tab 載入估 **-3~6s**（16 條 sequential ~3~8s → 8-worker batch ~0.5~1s）；ttl 過期自動重抓；register_cache 沿用「全域刷新」按鈕一鍵清。**[Debug]** v19.65 perf(cache) 補頂層聚合 cache + v19.66 batch 預熱兩棒組合解決「冷啟動 16 條 sequential FRED」根因；後續同 rerun 內 `_fred()` 呼叫 0 改動仍 hit cache（向後相容）；版本撞號註記：merge 時 origin/main 已存在另一筆 v19.65 perf(cache) PR #302（liquidity_engine 頂層 cache，Copilot 2026-06-21 開），commit msg / source code 註解保留 v19.65 標籤，STATE.md 統一以 v19.66 紀錄區別。**架構意義**：完成 P1-F1（Fund FRED 集中入口），延續 Stock v18.228（ETF batch）+ v18.229（yf batch）「cache key 集中 + 並行預熱」三棒對稱模式；P0（v18.227 + v19.63/64）+ P1-S1/S2/F1 整體交付完整。下一步候選：等 Streamlit Cloud Fund app rebuild 驗證 macro tab 載入 -3~6s / 等 user 新方向。

- **前一版 perf(cache) v19.65**：P1 補 cache 給兩個 FRED 頂層聚合函式。**根因**：v19.64 P0 補完 4 個 leaf fetcher，但 `services/us_liquidity_engine.py::fetch_us_liquidity_snapshot`（6 指標 × FRED: BAMLH0A0HYM2/RRPONTSYD/M2SL/WALCL）與 `services/liquidity_engine.py::fetch_liquidity_factors`（DTWEXBGS/CARRY_UNWIND/FRED series）兩個頂層聚合函式本身無 cache，tab1 每次 rerun 仍各觸發一次 `ThreadPoolExecutor` 多 FRED 呼叫。**修法**（2 檔 +4/-0）：兩函式各加 `from infra.cache import _ttl_cache, register_cache` import + `@register_cache @_ttl_cache(ttl_sec=1800, maxsize=2)` decorator。**SSOT 維持**：100% 沿用既有 `infra.cache` 機制，簽章 0 改動，自動加入 `_CACHE_REGISTRY` 共享「全域刷新」總開關。py_compile 2 檔 + dynamic import（`_CACHE_REGISTRY` 新增 2 entries: fetch_us_liquidity_snapshot / fetch_liquidity_factors）+ pytest **1872 passed / 4 skipped / 0 failed**（零回歸）三段驗證通過。**[邏輯]** 聚合層 rerun TTL 30min 命中後直接回 dict，子 FRED fetcher 的 _ttl_cache 仍保留作第二層防護（ttl 過期時頂層 miss + 子層 hit 仍可節省）。**[邊界]** fred_api_key 為 cache key 一部分，不同 key 不互混；失敗 dict（含 `_err` 鍵）也會被 cache 30 min 避免 retry storm；ttl 過期自動重抓。**[效能]** macro tab 美股流動性 + 深水區流動性兩大板塊 rerun IO 從「每次 ThreadPoolExecutor 6+4 並行請求」→「30 min TTL cache hit O(1)」；「全域刷新」按鈕自動清。**[Debug]** `clear_all_caches()` 觸發後兩函式 cache 清空，下次 rerun 重抓；cache_info 可查命中率。下一步候選：等 Streamlit Cloud Fund app rebuild 驗證 macro tab 載入下降 / 等 user 新方向。

- **前一版 perf(cache) PR #297 @ fbe7603 v19.64**：User 訴求「基金跟股票資料下載的很慢，是不是還有沒有執行 SSOT 的指標？」**雙 Explore 盤點**：Fund 找出 3 違規 + 多 fetcher 無 cache（fetch_fred 在 macro_service/liquidity_engine/us_liquidity_engine 各自獨立 15+ 次呼叫、fetch_holdings 無 cache、fetch_yf_latest/fetch_forward_pe/fetch_gdpnow 無 cache）；核心慢因「fetcher 沒套 cache」非真正 SSOT 違規。**修法**（3 檔 +10/-0）：(1) `services/valuation.py` 加 `from infra.cache import _ttl_cache, register_cache` + `fetch_forward_pe` 套 `@register_cache @_ttl_cache(ttl_sec=1800, maxsize=2)`（^GSPC info 偶發失敗 → 30 min 鎖住好值）+ `fetch_gdpnow` 套 1800s/4（FRED 系列）；(2) `repositories/macro_repository.py::fetch_yf_latest` 套 `@register_cache @_ttl_cache(ttl_sec=300, maxsize=16)`（盤中 ticker 需鮮度 5 min）；(3) `repositories/fund_repository.py::fetch_holdings` 套 1800s/64（MoneyDJ 月更新源）。**SSOT 維持**：100% 沿用既有 `infra.cache` 機制（與 macro_repository 其他 fetcher 一致），fetcher 簽章 0 改動，自動加入 `_CACHE_REGISTRY` 共享 v19.59 sidebar「全域刷新」總開關。py_compile 3 檔 + AST（4/4 decorator 全帶 ttl + reg）+ dynamic import（註冊表 0 → 10 entries 含 4 新 fetcher）三段驗證通過。**[邏輯]** 4 fetcher rerun 命中 ttl 跳網路 IO；cache key 自動 hash args/kwargs；unhashable bypass 走原 fn 安全；wrapper 暴露 cache_clear / cache_info。**[邊界]** fetch_holdings 入參 code:str 安全 / fetch_yf_latest 入參 tickers:tuple 安全 / fetch_forward_pe 無參 / fetch_gdpnow 接 fred_api_key 安全；失敗結果也會被 cache 30 min（避免 ^GSPC info / MoneyDJ retry storm）；ttl 過期自動重抓。**[效能]** macro tab 首屏 -2~4 秒；ETF/基金 rerun IO -40~60%；cache hit O(1) ns 級；register_cache 進註冊表後 `clear_all_caches()` 一鍵清。**[Debug]** 「全域刷新」按鈕（v19.59 C2 sidebar）按下會自動清新加 4 fetcher；補完後同檔基金 N 次 render 不再 N 次重抓 MoneyDJ；^GSPC info 偶發失敗時 30 min 鎖好值不會讓估值頁紅燈閃爍。**架構意義**：與 Stock #234 v18.227（5 fetcher stdlib cache）同步交付「P0 IO 慢因清掃」；P1（fetch_all_indicators 變單一 FRED 集中入口、9+ 處 fetch_fred 收斂）待 P0 驗證後評估。下一步候選：等 Streamlit Cloud Fund app rebuild 驗證 macro tab 載入下降 / 等 user 新方向（P1 集中還是新題目）。

- **前一版 feat(diagnostic) PR #296 @ 86e5968 v19.63**：User 訴求「請幫我檢查是否所有指標 總經 個股 ETF 基金 從網路上抓下來的，都有在資料診斷中被監控，如果有缺少，請幫忙補上，記得維持 SSOT」。**Explore Agent 雙路盤點**：data_registry 已監控 22 個 FRED 總經 auto-loop + 基金淨值/配息/持股/TER + RSS 新聞；漏監控 4 大孤兒：(a) 台灣本地總經（PMI / 景氣燈號 / 出口 YoY / 外資連續日數，`services/macro_tw_local_fetch.py` + `tw_macro.fetch_foreign_consecutive_days` 已抓但 tab1_macro 局部變數不進 session）；(b) hot_money 外資/投信 × USDTWD（`_macro_hot_money` 已 stash 但 data_registry 未讀）；(c) 基金績效 wb01（`raw['perf']` 1Y/3Y/5Y 已抓但未進 registry）；(d) 風險指標 wb07（`raw['risk_metrics']['risk_table']` 已抓但未進 registry）。**修法**（2 檔 +103/-0）：(1) `ui/tab1_macro.py:621` fetcher block 之後 stash `_macro_tw_local`（4 子 dict：tw_pmi/ndc_signal/tw_export/fi_streak 各 value+date_latest），try/except 吞錯不波及 happy path；(2) `ui/helpers/data_registry.py` 加 §4a 區塊 — 讀 `_macro_tw_local` 透過 `_tw_specs` list（4 tuples: key/label/source/value/date/freq）loop 寫入 reg（任一 value None 或 date 空跳過該行）；加 §4b 區塊 — 讀 `_macro_hot_money` 寫入 `總經_HOT_MONEY_FX` daily 監控行；擴充 `_register_fund_subdata` §5e 績效 + §5f 風險指標 — 讀 `raw['perf']` any 1Y/3Y/5Y 非空就 register monthly 監控、讀 `raw['risk_metrics']['risk_table']` 非空 dict 就 register monthly 監控。**SSOT 維持**：fetcher 0 改動、session_state stash 加新 key（不覆蓋 existing）、registry 只在唯一 `_update_data_registry()` 函數內擴充。AST + py_compile + 動態 import ✓ 三段驗證通過。**[邏輯]** 純讀 session_state 寫 reg，沿用 `_freshness(date, freq)` 既有判斷邏輯；TW 4 項與 hot_money 1 項走 dynamic registration（資料抓到才註冊，跟 FRED loop 同款）；per-fund 績效/風險走 prefix scheme（基金_<name>_績效 / 組合_<name>_風險指標）。**[邊界]** `_macro_tw_local` 任一子 dict 缺 → 該行跳過（不爆）；`_macro_hot_money.date` 空 → 整段跳過；`raw.perf` 非 dict 或 1Y/3Y/5Y 全 None → 跳過；`risk_table` 非 dict 或空 → 跳過；既有 22 FRED indicators / 配息 / 持股 / 產業 / TER / RSS 0 行為改動。**[效能]** 零新增 IO（讀 session_state in-memory ns 級）；`_freshness` 純函式無 FRED API 呼叫（TW/hot_money 非 FRED-backed）；`_kpi_cache` 等既存 cache 不受影響。**[Debug]** user 「資料診斷」表預期新增 5 行（4 TW + 1 hot_money）+ per-fund 加 2 子行（績效 + 風險指標）；補完後 SSOT 「fetcher 抓 = registry 監控」雙端對齊；下次 fetcher 故障可即時在診斷表看到 🔴 標記。**架構意義**：與 Stock #233 v18.226（外資連續日數）同步收尾「資料診斷孤兒項」清單；雙 repo 監控覆蓋率從 ~85% → 100%。Stock 改動 1 處（health_inspector 加 1 監控行）；Fund 改動 3 區塊（tab1 stash + registry 2 新區塊 + 2 子函數擴充）。下一步候選：等 Streamlit Cloud Fund app rebuild 驗證新 5+ 監控行顯示 / 等 user 新方向。

- **前一版**：fix(checkup) PR #295 @ fa0d44b v19.62：User 訴求「基金錢的計算，小數點保持 2 位」— 截圖體檢表「每月100萬配息(TWD)」/「月配息🧮(本金TWD)」/「年配息🧮(本金TWD)」3 欄與健診摘要表「月配息(TWD)」顯示原始 float 17 位小數（如 `10791.666666666666`），未套用 `column_config` `NumberColumn` format。**根因**：`Styler.apply(_row_color)` 包覆後 `column_config` `NumberColumn` format 在某些 Streamlit 版本對混 `None` 的 `object` dtype 欄位失效（v19.60 已含金額欄但格式只生效一半）。**雙保險修法**（1 檔 +31/-25）：(1) `_CHECKUP_COL_CONFIG` 7 處金額欄 format `%,.0f` → `%,.2f`（每月100萬配息(TWD) / 月配息🧮(本金TWD) / 年配息🧮(本金TWD) + 健診摘要表「月配息(TWD)」）；(2) `build_checkup_dataframe` row 端加 `_r2(v) = round(v, 2) if v is not None else None` 純函式 + 摘要表 `_sum_rows` 加 `_r2s` 同款 round（防 `None+float` 混 dtype 漂移，None 保留 None 顯示 —）；NAV/FX 維持 `%.4f`（換匯精度需求）。改動 1 檔 +31/-25。py_compile ✓ / ruff All checks passed / T2 smoke：ALBT8「每月100萬配息(TWD)」= `10791.67`（從 17 位截斷至 2 位）。**[邏輯]** 純顯示精度收斂，不動 `_compute_fund_health_kpis` SSOT 計算邏輯；caller 行為等價（17 位 → 2 位，round-half-to-even 銀行家進位）；NAV/FX 維持 4 位精細度。**[邊界]** None → None（Streamlit 「—」顯示）；NaN/inf 在 `_safe_num` 已過濾；`round(0.0, 2)` 不爆；混 None+float 欄 dtype `object` 後 round 仍生效（Python 原生 round 不依 numpy dtype）。**[效能]** 純 in-memory `round()` Python 內建 ns 級；零新增 IO / cache。**[Debug]** 配對 Stock #231 v18.224 三件齊發（user 3 訴求 Stock 2 件 + Fund 1 件）；建立「Styler + column_config 失效」反模式 SOP — 抓金額顯示精度漂移時要雙保險（column_config format + row 端 round），不可只信 NumberColumn format。**架構意義**：v19.58 → v19.59 → v19.60 → v19.61 → v19.62 五棒體檢表精度收斂終局：v19.58 加月配息欄、v19.59 抽 5 欄、v19.60 補 3 欄、v19.61 加摘要表、v19.62 補 2 位精度規範；user 從「逐檔卡 17 位 float」→「橫向 PK 2 位整潔表」UX 階段任務結案。下一步候選：等 Streamlit Cloud Fund app rebuild 驗證 / 等 user 新方向。

- **前一版**：feat(checkup) PR #294 @ 3543628 v19.61：User 訴求「3 檔基金各自獨立卡片不便橫向比較，加上表格」— `ui/helpers/fund_checkup.py` `render_fund_checkup` L509-580 在「逐檔財務健診」上方加 SSOT 健診摘要表 8 欄（代號 / 基金名 / 吃本金狀態 / 1Y 含息% / 年化配息率% / Coverage / 月配息(TWD) / 最高經理費%）。**零新算法** — 100% 沿用 v19.54 `_compute_fund_health_kpis` SSOT；迴圈走訪呼叫一次後資料同時餵摘要表與下方逐檔卡（`_kpi_cache` dict 避免雙重計算 KPI）；吃本金狀態 icon 鏡像 `_render_fund_health_card` L241-247（red 🔴 / yellow 🟡 / green 🟢 / 其他 ⬜）+ alert_level fallback `"不適用"`(adr None) / `"資料不足"`(ret_1y None)。column_config 8 個 NumberColumn/TextColumn 配 tooltip 解釋公式與閾值。改動 1 檔 +67/-3。py_compile ✓ / ruff All checks passed / SSOT smoke 3 case（ACCP138 紅 cov 0.23 月配 8133 / ACDD19 ⬜ 不適用 / ALBT8 紅 cov 0.88 月配 10792）數字 100% 對齊 user 截圖。**[邏輯]** 純 UI 新增，不動 `_compute_fund_health_kpis` 與 `_render_fund_health_card` 簽名；caller 行為等價（下方逐檔卡保留作 drill-down）；摘要表與下方卡 100% 同源（同個 `_kpi_cache[code]` tuple）。**[邊界]** `_compute_fund_health_kpis` 例外 → 該檔列「⚠️ 計算失敗 [ErrType]」其餘欄 None / 不入 `_kpi_cache`（下方卡不重複報錯）；adr=None → status="不適用" + cov=None；ret_1y 缺 → cov=None；無 invest_twd → 月配息=None；無 `mgmt_fee` → 最高經理費=None；空 portfolio_funds → 整段跳過；`_sum_rows` 空 → 摘要表不渲染（保留下方卡）。**[效能]** `_kpi_cache` dict 避免逐檔卡重算 KPI（原本 KPI 迴圈 + 卡迴圈各算一次 → 現在合併單一迴圈）；純 in-memory pandas DataFrame 構造 ms 級；零新增 IO / cache。**[Debug]** 健診摘要表完成「逐檔卡→多檔表」橫向 PK 收斂終局 — user 從 3 個獨立紅框卡片無法一眼比較，升級為單張 8 欄並排表 + 保留卡作詳情。**架構意義**：v19.58「每月100萬配息」→ v19.59「5 欄上抽」→ v19.60「實際本金 3 欄完成」→ v19.61「吃本金健診表化」完成「投資試算 + 體檢 + 健診」全 3 軸 SSOT 收斂；user 從 v19.55 的「點 N 個 expander」UX → v19.61 的「橫向滾單張表」UX 終局。下一步候選：等 Streamlit Cloud Fund app rebuild 驗證 / 等 user 新方向。

- **前一版**：fix(checkup+partial) PR #293 @ 4c279dc v19.60 兩件齊發：User 訴求兩件：(1) **體檢表完整投資試算 SSOT**：v19.59 上抽 5 欄（計價幣別/NAV/FX/可申購單位數/月配股）已 cover 部分試算；本次補完最後 3 欄「原幣本金🧮(本金) / 月配息🧮(本金TWD) / 年配息🧮(本金TWD)」吃 `fund.invest_twd` 實際本金（sidebar），公式與 `_render_investment_calc` L194-283 100% 同源：`_amt_local_inv = invest_twd / FX`（TWD 計價短路 FX=1）/ `_mon_div_inv = invest_twd × adr / 100 / 12` / `_ann_div_inv = invest_twd × adr / 100`。`_DISPLAY_COLS` 從 18 → 21 欄；`_CHECKUP_COL_CONFIG` 加 3 NumberColumn `%,.2f` / `%,.0f` 配 tooltip 解釋公式。`fund.invest_twd <= 0` 或 FX/adr 缺 → 3 欄全 None → Streamlit 顯示 —（不爆）。**現在 user 看「投資試算」核心數字可橫向 PK 所有基金而不用點開 N 個逐檔深度卡 expander**。(2) **ABI051 partial 紅 → 黃**：`ui/tab2_single_fund.py:167` `_status_fd == "partial"` 路徑 `st.error` → `st.warning`，文案改「⚠️ 部分數據已取得（歷史淨值序列未取得）」。partial 本就是 MoneyDJ wb05 績效/風險指標 fetch 成功 + 淨值序列 fetch 失敗的混合態（雙獨立 fetch path：series 走 yp004002 易封 IP / risk_metrics 走 wb07 獨立），紅色 `st.error` 與上方成功顯示的 6 期風險指標表 + perf 卡自相矛盾，user 視覺體感「為什麼有資料又紅字失敗」混淆。改黃 + 文案明示「下方可繼續查看」消除視覺矛盾。改動 2 檔 +36/-3。py_compile ✓ / ruff 64 errors（pre-existing baseline 自 git stash 對比確認 0 增量、本 PR 未引入）。**[邏輯]** 3 欄計算 100% 同 `_render_investment_calc` 同源公式零重複實作；caller `build_checkup_dataframe(portfolio_funds)` 簽名不變；`fund.invest_twd` 既有 sidebar 注入（v19.54 `_compute_fund_health_kpis:192` 已用）；partial 純文案/顏色變更不動 status 判定鏈。**[邊界]** `invest_twd <= 0` → 3 欄全 None（user 不填本金時不顯示誤導試算）；FX 缺 → 3 欄全 None；adr 缺 → 月/年配息 None 但原幣本金仍算（user 仍看跨幣別轉換）；partial 文案保留「重新下載/MoneyDJ 代碼正確/FundClear 備援」3 建議不變。**[效能]** 零新 API；FX 5min 手動 cache 共享 v19.59 既有 `_safe_fx`；純算術 ns 級；ruff 64 errors 全 pre-existing baseline。**[Debug]** 體檢表完整呈現投資試算 SSOT — user 從 v18.213「同類 PK」→ v19.54「4 大健診」→ v19.58「每月100萬配息」→ v19.59「5 欄上抽」→ v19.60「實際本金 3 欄完成終局」漸進完整化；partial 視覺矛盾消除（紅字+成功表格的 UX 違和感斷源）。**架構意義**：完成「投資試算」從「逐檔卡單顯示」→「總表多檔 PK」的 SSOT 收斂終局，**21 欄體檢表覆蓋同類 PK 比較 + 試算量化 + 買賣點燈號完整三軸**；partial 狀態 UX 修正示範「graceful degradation 視覺一致性」原則 — 部分資料時表格還顯示就不該用 error 紅字否定。下一步候選：等 Streamlit Cloud Fund app rebuild 驗證 / 等 user 新方向。

- **前一版**：fix(tab5+checkup) PR #292 @ acd3f9e v19.59 三件齊發：User 訴求兩件：(1) **移除原幣別 fallback**：`ui/tab_fund_grp_health.py:36-54` 移除人工 `st.selectbox("原幣別 fallback", ["USD","EUR","ZAR","AUD","JPY","GBP","CNY","HKD","TWD"])` selectbox 改三欄 c1/c2/c3 為兩欄 c1/c2；`_process_one_fund` 刪掉 `normalize_ccy(ccy_hint)` fallback 改 `if not ccy_auto: return error "幣別未知（MoneyDJ wb05 未提供「計價幣別」欄）"`；幣別 SSOT 嚴格走 MoneyDJ 網路抓（既有 `fund_repository.fetch_fund_from_moneydj_url` L2960 `result["currency"] = rows_map.get("計價幣別", "USD")` 已抓），不再用人工 USD 矇混。`_run_batch_health` 仍接 `ccy_hint` 參數（傳空字串 `""`，向後相容無 caller 異動）。(2) **體檢表加 5 欄橫向 PK**：user 訴求「基金每百萬的配息，請整理在上方的表格中做比較」；從 `ui/helpers/fund_grp_health_extras.py:194-283` 逐檔「投資試算」card 上抽 5 欄到 `ui/helpers/fund_checkup.py` 比較表 — `計價幣別` / `NAV(原幣)` / `即時匯率(FX)` / `可申購單位數` / `月配股(單位)`，**100% 沿用同源公式**：`amt_local = 1,000,000 ÷ FX`（TWD 計價短路 FX=1）→ `units = amt_local ÷ NAV` → `月配股 = (amt_local × adr/100/12) ÷ NAV`。新增 2 helper `_norm_ccy()` 走 SSOT `services.currency.normalize_ccy(mode="yf")` + `_safe_fx()` 走 `repositories.fund_repository.get_latest_fx` 既有 5min positive-only 手動 cache（零新 API、零新 cache）；`_CHECKUP_COL_CONFIG` 加 5 個 NumberColumn/TextColumn 配 tooltip 解釋公式。`_DISPLAY_COLS` 從 13 欄擴至 18 欄。改動 2 檔 +85/-14。py_compile ✓ / ruff 1 error（E402 pre-existing 自 K3 v19.76 `services.moneydj_fetcher` import 位置 line 88，`git stash`-baseline 對比確認非本 PR 引入）。**[邏輯]** 幣別 SSOT 走 MoneyDJ 網路抓；5 欄全部沿用 `_render_investment_calc` 同源公式零重複實作；caller 行為等價。**[邊界]** NAV/FX 缺一→ units/月配股顯示 None → Streamlit 自動 —；TWD 計價短路 FX=1；MoneyDJ 無 currency 該檔 error 不再矇 USD（用戶可從 error 訊息知道是 MoneyDJ 抓不到）；ccy_hint="" 向後相容無 caller 異動。**[效能]** 零新 API；FX 5min 手動 cache 同檔 N 次無增量成本；build_checkup_dataframe 複雜度從 O(N×k) 到 O(N×(k+5)) 常數因子；NAV/units 純算術 ns 級。**[Debug]** 比較表從 13 → 18 欄；user 可直接 PK 同類型基金的「NAV / 即時匯率 / 可申購單位數 / 月配股 / 每月配息現金流」5 維；逐檔卡保留作 expand drill-down 場景。**架構意義**：基金體檢表完成「逐檔 → 多檔比較」UX 升級終局 — 從 v19.58「月配息單欄」擴 v19.59「投資試算全 5 欄上抽」，user 不用點 N 個 expander 就能橫向 PK 所有量化投資指標；同時收緊「人工 fallback 矇混」反模式，所有數據強制走網路抓 SSOT。下一步候選：等 Streamlit Cloud Fund app rebuild 驗證 / 等 user 新方向。

- **前一版**：fix(tab1+checkup) PR #291 @ 88d2a38 v19.58 P0 hotfix：兩件齊發：(1) **美股流動性 nested expander 修**：`ui/tab1_macro.py:2188` 內層 `st.expander("🔍 載入失敗詳情")` 巢在 L2132 美股流動性 expander 內 → `[StreamlitAPIException] Expanders may not be nested inside other expanders.` 紅色 fallback 「美股流動性監測渲染失敗」（任一 FRED/AAII/Yahoo fetcher fail 觸發）；改用原生 HTML `<details>` block — 保留 fold UX、零 Streamlit 巢狀限制、HTML escape `<` 字元 + 截 120 字防 XSS。(2) **基金體檢表加「每月100萬配息(TWD)」欄**：user 訴求「方便橫向 PK 現金流量化能力」；`ui/helpers/fund_checkup.py` `_DISPLAY_COLS` 新增欄位 + `build_checkup_dataframe` 填值（公式 `1,000,000 × adr% / 12 = 10000 × adr / 12`，`adr` 沿用 `_compute_fund_health_kpis` 同源路徑 — MoneyDJ wb05 `moneydj_div_yield` 優先 → `metrics.annual_div_rate` fallback，**零重複實作**）；`_CHECKUP_COL_CONFIG` 加 `NumberColumn` 格式 `%,.0f` + tooltip 解釋計算口徑；bullet 說明補一行。改動 2 檔 +32/-5。py_compile ✓ / ruff All checks passed（僅 pre-existing 5 warnings 非本 PR 引入）。**[邏輯]** HTML `<details>` 與 `st.expander` UX 等價；adr 算法 100% 共用既有 helper。**[邊界]** 無配息／`adr<=0` 顯示 None → Streamlit 自動 —；HTML escape 防 `_err` 含 `<script>`。**[效能]** 零新 API、零新 fetch；建表複雜度不變。**[Debug]** `_us_liq` 任一 fetcher 失敗就會觸發 `_errs` 不空 → 巢狀爆，K-Py314 後 Streamlit Cloud 重新部署時暴露。下一步候選：等 Streamlit Cloud Fund app rebuild 驗證 / 等 user 新方向。

- **前一版**：feat(shared) PR #290 @ ce3199a v19.81 K4b-4b：K4b-4b 跨 repo `shared/colors.py` SSOT 建構 — Fund-side 從零建 7 hex 常數（4 TRAFFIC + 3 MATERIAL）鏡像 Stock，`ui/components/macro_card.py` 9 hex 收斂（`#f44336/#ff9800/#00c853` × 3+3+1 → `MATERIAL_RED/ORANGE/GREEN`）+ 加 `from shared.colors import MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED`；`scripts/sync_to_stock.sh` 同步清單從 `macro_card.py` 改為 `colors.py`（K4b-4b 起雙端 `macro_card.py` 脫鉤各自演化，配色 SSOT 仍 Fund→Stock 單向）。改動 4 檔 +60/-13：新建 `shared/__init__.py` 5 行 + `shared/colors.py` 39 行 + `ui/components/macro_card.py` +9/-9 hex 替換 + sync 腳本 +7/-4。py_compile ✓ / smoke import OK（`from shared.colors import MATERIAL_*` + `from ui.components.macro_card import _z_color`）/ `bash scripts/sync_to_stock.sh` 雙檔成功推 Stock 端（colors.py + __init__.py 加 DO NOT EDIT 警告）/ grep Material hex regex re-scan `ui/components/macro_card.py` = 0。**[邏輯]** 純常數參考替換；caller 行為等價（`_z_color(3, True) == "#f44336"` 編譯期與原 hex 一致）。**[邊界]** brand 藍 `#64b5f6` / yellow marker `#ffeb3b`/`#000` / dark theme chrome `#11161e/#1f2933/#e6edf3` 保留 inline（非 Material 範疇，避免 scope creep）；`color == "#64b5f6"` default 比較邏輯字面保留。**[效能]** SSOT 常數 module-level 載入零 runtime overhead；無新增 IO / cache。**[Debug]** 改 palette 仍只改 `shared/colors.py` 3 行（Fund canonical）+ 跑 sync 腳本；雙 repo SSOT pipeline 重建完成。**架構意義**：與 Stock #226 @ 46a95c4 雙 PR 配對解決 Stock v18.217 STATE.md 標記的「跨 repo sync 腳本路徑漂移」根因 — Fund 端從零建 `shared/` SSOT、修 sync 腳本同步清單、雙端 9 hex 收斂；**Fund 端首次有 colors.py SSOT 入口**，未來 palette 調整單向同步收斂；macro_card.py 兩端脫鉤後維護模型清楚（colors 一處 SSOT、macro_card 各 repo 自演化）。下一步候選：等 user 新方向（K4b 系列收官 / Fund K6/K6b/K9 全綠基線維持）。

- **前一版**：refactor(fund) PR #289 @ e5cfd55 v19.80 K6b：Phase 1 audit `fmt_twd()` SSOT 收尾棒 — `ui/tab3_t7_ledger.py` 52 處 `NT$...:,.0f` Python f-string 批量遷移到 K6 抽出的 SSOT（`services/format_helpers.fmt_twd`）。**audit 校正**：K6 entry 預估 tab3_t7_ledger 51 處，K6b 實際 grep 為 52 處（多算到含 sign 變體點位）。**遷移分類**（52 sites）：45 處純千分位 `NT${x:,.0f}` → `fmt_twd(x)`；7 處 sign 變體 `NT${x:+,.0f}`（損益 / 月差 7 點位：`_ann_diff` / `_delta` / `_pl_twd` / `_pl_total` / `unrealized_pl_twd` ×2 / `ann_diff/12`）→ `fmt_twd(x, sign=True)`；7 處 division 算式 `NT${x/12:,.0f}`（年→月配息 7 點位：`_total_div_twd/12` / `_b_ann_total/12` / `_ann_diff/12` / `_ann_cash/12` / `_ann_reinv/12` ×2 / `_cash_total_twd/12`）→ `fmt_twd(x / 12)`。**plotly hovertemplate 全程不動**：tab3_t7_ledger 內 0 處 plotly `%{value:,.0f}` 模板語法（K6 entry 提到的 4 處在 tab3_portfolio.py），符合 K6 SSOT 設計界線。改動 1 檔 +53/-52（+1 為 import 那行）：唯一性 assert 51 edits 全部 `file.count(old) == 1` 通過（1264+1265 metric value+help 合併為一個 multi-line edit、實際改 2 sites）。py_compile ✓ / ruff：baseline 5 errors == K6b 5 errors（5 errors 為 pre-existing E741/E731 lambda 等非本 PR 引入，`git stash`-baseline 對比確認）/ pytest **1863 passed / 5 skipped / 0 failed**（436.09s，**zero regression**，維持 v19.78 K9 + v19.79 K6 達成的 1863 全綠基線）。**[邏輯]** 51 edits Python 腳本 + 唯一性 assert 防範失誤替換；sign / division / embedded 三類變體各對應 fmt_twd 旗標或前置算式抽出；caller 行為等價。**[邊界]** None / NaN / inf / 非數值 → "—"；負數正常；sign=True 強制 +/- 含 `+0`；division 走 round-half-to-even 銀行家進位（Python `:,.0f` 默認）；1264+1265 metric 雙欄一次替換避免半完成狀態。**[效能]** 純 in-memory format → 函式呼叫；零新增 IO / cache；fmt_twd 純函式無 import 依賴；Tab3 T7 帳本面板 render 路徑（多次呼叫）穩定。**[Debug]** 全 repo `grep 'NT\$\{[^}]*:[+]?,?\.0f\}'` 結果為 0（K6 首棒 9 處 + K6b 52 處 = 61 處全清；plotly 4 處不算數）；後續若全站切換貨幣風格（NT$ → TWD prefix）或精度調整（預設改 precision=1），僅改 SSOT 一處全 64 處同步；K6 + K6b 兩棒共 +178/-61 達成「Fund 端 TWD 格式化 SSOT 100% 收斂」。**架構意義**：K6 / K6b 鏡像 Stock K4（v18.210 `shared/colors.py` 6 hex SSOT）→ K4b 漸進式 SSOT 模式（先抽 SSOT + 小檔遷移、再 bulk migration），Fund 端首次達成「全 repo 格式化 SSOT 100% 收斂」；K6b 用「Python 腳本 + 唯一性 assert」處理 52 處批量遷移，建立「>10 sites bulk migration 走腳本而非 N 次 Edit」精準替換新範式。User 上線驗證：reboot → Tab3 T7「📈 A 加碼」「⚖️ B 投入再平衡」「🔄 C 複合轉換」「💼 帳本即時面板」「方案比較區」所有 NT$ 顯示應與 PR 前等價。下一步候選：K4b-2（Stock 中小檔 173 處 colors 批量遷移）/ K4b-3（Stock 小檔 109 處）/ K4b-4（Stock Material legacy 16 處）/ K8（Stock thread-safe yfinance）/ 等 user 新方向。

- **前一版**：refactor(fund) PR #288 @ fd6d6a1 v19.79 K6：`fmt_twd()` SSOT 首棒（9 站遷移）— Phase 1 audit 找到 `NT$...:,.0f` 散落 64 處（tab3_t7_ledger 51 / tab3_portfolio 12 / portfolio_linkage 1），本 PR 為 K6 首棒，建 SSOT + 遷移 13 處中可遷移 9 站（4 站為 plotly `hovertemplate` 模板語法、不可用 Python 函式取代）；留 `tab3_t7_ledger.py` 51 處給 K6b。**SSOT 設計**（`services/format_helpers.fmt_twd`）：純函式、零 import 依賴；`fmt_twd(amount, *, sign=False, precision=0, prefix="NT$") -> str`；None / NaN / inf / 非數值 → "—"（codebase 標準缺失符號）；sign=True 強制 +/- 號（損益/月差場景）；precision 可調小數位；prefix="" 純千分位（HTML 拼接場景）。**遷移範圍**：`ui/tab3_portfolio.py` 8 處（保單級投入金額 L976 / 個股投入 L1118 / 總資產 KPI L1245 / 預估月配息 L1260 / 曲線高低今 3 行 L1354-1356 / 配置總覽合計 L1390）+ 1 import；`ui/helpers/portfolio_linkage.py` 1 處（組合持倉金額 L53）+ 1 import。改動 4 檔 +125/-9：新建 `services/format_helpers.py` 57 行 + `tests/test_format_helpers.py` 56 行（10 case：整數、浮點、負數、None、NaN、inf、非數值字串、sign 強制、precision 自訂、prefix=""、sign+precision 組合）+ tab3_portfolio +9/-8 + portfolio_linkage +2/-1。py_compile ✓ / ruff（新檔 + portfolio_linkage）All checks passed；tab3_portfolio 24 errors 為 pre-existing lambda 違規（自 K3 以前即存在，**非本 PR 引入**）/ pytest **1863 passed / 5 skipped / 0 failed**（基線 1853 + 新 10 fmt_twd tests，**zero regression** 維持 v19.78 K9 達成的 1853 全綠基線**）/ smoke 5 case（整數/None/NaN/sign/prefix=""）全綠。**[邏輯]** 純常數函式抽取，UI 端 import 後 inline 等價替換；caller 行為等價（NT$ + 千分位）。**[邊界]** None/NaN/inf/非數值 → "—"；負數正常顯示；sign 強制 +/-；precision 自訂。**[效能]** 純 in-memory format，零新增 IO/cache。**[Debug]** 後續若全站要改貨幣顯示風格（如 NT$ → TWD），僅改 SSOT 一處兩 callers 同步。**UX 註記**：4 站原有 "NT$ "（NT 後空格）規範化為 "NT$"（金融顯示標準如 Bloomberg），若 user 偏好保留空格可在 fmt_twd 加 `space` 參數。**架構意義**：K6 鏡像 Stock K4（v18.210 `shared/colors.py`）→ K4b 漸進式 SSOT 模式（先建 SSOT + 小檔遷移、再 bulk migration）；K1-K3-K6 連三棒收斂 user「跨 Tab 散落公式」根因，**Fund 端格式化首次有 SSOT 入口**。下一步候選：K6b（Fund `tab3_t7_ledger.py` 51 處批量遷移、含 sign 變體與 division 算式）/ K4b-2（Stock 中小檔 173 處 colors 批量遷移）/ K8（Stock thread-safe yfinance 評估）/ 等 user 新方向。

- **前一版**：fix(test) PR #287 @ 581e9f7 v19.78 K9：消除 pre-existing pytest 紅旗 — `test_fetch_fred_goes_through_proxy_helper` 補 `realtime_start` 欄位斷言。**根因**：v19.60 D1 後 `repositories/macro_repository.fetch_fred()` 統一保證輸出含 `realtime_start` 欄（API 無回則填 NaT，line 242-245 `if "realtime_start" in df.columns: df[...] = pd.to_datetime else df[...] = pd.NaT`），但本測試的 mock observations 不含該欄、且 expected columns 仍停留在 v19.60 之前的 `["date", "value"]` → 自 v19.60 D1 起 1853 套件中 1 個紅燈持續至 K3/L1。改動 1 檔 +2/-1：`test_macro_core.py:116` 單行 expected list 加 `"realtime_start"` + 補 1 行行內註解標 v19.60 D1 由來。py_compile ✓ / pytest test_macro_core.py **42/42 pass** / pytest 全套 **1853 passed / 5 skipped / 0 failed**（前 1852+1fail → 1853+0fail，**zero regression 且消除紅旗**）/ ruff 既有 E741 line 463/466 pre-existing 非本 PR 引入。**[邏輯]** 純測試端 expected 對齊 production 行為，不動 fetch_fred()/macro_core 任何邏輯。**[邊界]** 不改 production，零 caller 影響。**[效能]** 零新增 IO，測試本身 < 2s。**[Debug]** STATE.md K3/L1 entry 一直記著「K9 pre-existing」紅旗，K9 一棒收尾消除自 v19.60 D1 以來持續至今的測試紅燈，**Fund 端 pytest 套件首次 1853 全綠**。**架構意義**：clean main 維持綠燈是 §4 鋼鐵自省的底線，K9 屬「最輕量極速收尾」類，PR diff 2 行 → 風險為零、價值為「未來新 PR 的測試基線從 1852+1fail 升級為 1853+0fail，避免新 dev 看到紅燈誤判為自己引入」。下一步候選：K6（Fund 同 repo — `fmt_twd()` SSOT 27+ 處）/ L2（Stock 端對應呈現改善鏡像 L1 多檔表格化）/ K4b-2（Stock 中小檔 173 處遷移）/ K7（Stock health_grade 閾值對齊）。

- **前一版**：feat(fund) PR #286 @ e22f5b6 v19.77 L1：組合健診多檔表格化（user 訴求「基金的組合健檢，多檔請用表格的方式呈現」）。Tab5 `_render_health_table` 三點純 UI 局部改寫（不動 `_process_one_fund` 契約）：(1) **L302-307 主表 column_config**：`NumberColumn` 百分號（年化配息率/含息年化/年化淨值/最高經理費 `.2f%%`）+ 千分位（principal_ccy/units/累積 TWD 配息/年均配息 `,.0f` 或 `,.2f`）+ 欄寬調整（small/medium），密集 19 欄變整齊；(2) **L310-332 後**：plotly 多檔比較圖之後加精簡比較表 — 4 數值欄（代號/含息年化%/年化配息率%/年化淨值%）對照圖看精確值；(3) **L335-353 整段改寫**：N 個 `st.expander` → 兩張多檔合併表 — ①「持有 meta」每檔一列（買進日/NAV/FX/原幣本金/持有單位/末日/末日NAV/持有年數）取代 N 個 expander 的 meta json，②「配息事件多檔合併」首欄補 code 後 concat 各檔 `_detail.events`，取代 N 張單檔配息表。改動 1 檔 +87/-19（淨 +68）。py_compile ✓ / pytest **1852 passed / 5 skipped / 1 pre-existing K9 fail 零回歸**（fail = `test_fetch_fred_goes_through_proxy_helper` v19.60 D1 `realtime_start` 欄位未更新，與 K3 PR 確認非本次引入）/ Smoke **6 case** 全綠（主表 column_config 含百分號千分位 / 精簡比較表 2檔 5欄 / 持有 meta 2檔 11欄 / 配息事件 3 events from 2 funds / 單檔邊界跳過比較圖 + 精簡表 / 空 events 容錯走 st.info）。**[邏輯]** 純 UI 內局部編輯；不動 worker 契約；單檔/多檔同邏輯（精簡比較表 ≥2 才出）。**[邊界]** 空 events → `st.info("所有檔於買進日後皆無配息事件")`；單檔 → 跳過 plotly + 精簡表；`isinstance(ev, dict)` 過濾髒項；`detail or {}`/`summary or {}` 兩層 fallback。**[效能]** 純 in-memory df 構造 ms 級；`column_config` dict 只 import 一次；現有 `_process_one_fund` ThreadPoolExecutor 並行不變。**[Debug]** 多檔對比一眼掃完表，不用逐一點 N 個 expander；精簡表搭配比較圖讓 user 既看分布又看精確值；持有 meta 表方便比較「不同檔買進日 / 持有年數 / FX 差異」。**架構意義**：完成 L 系列首棒「多檔呈現一致化」— 從「單檔導向」（expander 一檔一塊）改為「多檔導向」（合併表橫向比較），呼應 Fund 戰情室「組合層級決策」定位。User 上線驗證：reboot → Tab5 貼多檔代號 → 健診結果應全表格呈現：①主表（column_config 整齊格式化）→ ②plotly 比較圖 → ③精簡比較表（4 欄對照精確值）→ ④持有 meta 多檔表 → ⑤配息事件多檔合併表。下一步候選：L2（Stock 端對應呈現改善）/ K4b-2（Stock 中小檔 173 處遷移）/ K6（Fund `fmt_twd()` SSOT 27+ 處）/ K9（Fund pytest K9 修復）。

- **前一版**：refactor(fund) PR #285 @ 8fdb08f v19.76 K3：Phase 1 audit 證據驅動排毒第二棒 — `_auto_fetch_moneydj` 在 Tab2（38 行）+ Tab5（32 行）兩處 inline 收斂到 `services/moneydj_fetcher.py` SSOT。**邏輯審查**：兩處邏輯近似但不等價（tab2 回 tuple/支援 URL 直傳/fallback 含 partial-no-series 中間層；tab5 回 dict/僅純代碼/fallback 缺中間層），同檔基金可能走不同路徑 — 與 K1 含息報酬 / K2 currency 同類「跨 Tab 數據打架」事故源。**K3 解法**：新 helper `auto_fetch_moneydj(raw, *, return_page_type=False)` 統一 fallback chain（複用 tab2 較完整版本：complete > with_series > partial-no-series > last），`return_page_type` 旗標相容兩種 caller 場景；tab5 用 alias import `auto_fetch_moneydj as _auto_fetch_moneydj` 保留舊名零 caller 異動。改動 3 檔 +120/-78（淨減 ~70 行真實邏輯）：(1) 新建 `services/moneydj_fetcher.py` 110 行含 docstring + `build_moneydj_url` + `auto_fetch_moneydj`；(2) `tab2_single_fund.py` 刪 inline 44 行 + 順手清掉 unused `fetch_fund_from_moneydj_url` import（§2 大掃除）；(3) `tab_fund_grp_health.py` 刪 inline 32 行 + alias 保留舊名。py_compile ✓ / pytest **1852 passed** / 5 skipped（1 fail 為 pre-existing v19.60 D1 `test_fetch_fred_goes_through_proxy_helper` 未更新 `realtime_start` 欄位，clean main 重現確認**非 K3 引入**）/ K3 SSOT smoke **7 case** 全綠（URL builder / URL 直傳單次 fetch / complete first try 短路 / partial-no-series 試下一 page_type 拿 with_series — v18.120 修法核心 / return_page_type=False 只回 dict tab5 場景 / 空 None 容錯 / fetch 例外 catch 後繼續）。**[邏輯]** tab2 較完整 fallback 升級為 SSOT；tab5 caller 行為等價或更好。**[邊界]** 空/None→`{}` 或 `({}, "")`；fetch 例外 catch 後繼續下一 page_type；URL 直傳路徑 page_type 從字面探測。**[效能]** 零新增 IO；module-level import 共享；MoneyDJ `_ttl_cache(900)` 不受影響；tab5 caller 零 import 異動（alias 機制）。**[Debug]** K1（含息報酬）→ K2（currency）→ K3（MoneyDJ 偵測）連三棒收斂 user「跨 Tab 數據打架」根因。**架構意義**：K3 示範「對外簽名差異 → 加旗標 backward-compat」漸進式 SSOT 模式（同 K2 的 mode 參數設計），避免一次破壞所有 caller。K4~K7 排毒清單：K4 Stock `shared/colors.py`（已 v18.210 啟動，3 caller / 6 hex；K4b 待 12 檔 ~100 hex）/ K5 Stock yfinance proxy（已 v18.209）/ K6 Fund `fmt_twd()` helper（27+ inline scattered）/ K7 Stock health_grade 閾值對齊。User 驗證：reboot → Tab2 單檔（純代碼 / URL 直傳）+ Tab5 組合健診多檔，行為應與 PR 前一致。

- **前一版**：refactor(fund) PR #284 @ 00b498d v19.75 K2：Phase 1 audit 證據驅動排毒第一棒 — 3 處 `_CCY_NORMALIZE` inline 遷移到 services/currency SSOT。**邏輯審查**：v19.71 K3 抽 SSOT 但 grep 證實 3 caller 未遷移（`tab2_single_fund:1224` + `tab3_t7_ledger:240` + `fund_grp_health_extras:204`），三 dict 對「人民幣」對應 ISO 碼衝突（Tab2/extras→CNH yfinance偏好 vs T7→CNY ISO標準）— 這就是 user 抱怨「跨 Tab 數據打架」實證。**K2 解法**：`services/currency.normalize_ccy` 加 `mode` 參數（不破壞 ISO 標準前提下保留 yfinance 偏好）— mode="iso"（預設）人民幣→CNY、mode="yf" 人民幣→CNH；union 所有 alias。改動 5 檔 +62/-84（淨減 22 行真實消滅代碼膨脹）：Tab2/extras 用 `mode="yf"` 保留原 CNH 行為、T7 用預設 iso 保留原 CNY 行為；`test_tab2_ccy_normalize` 從「驗 Tab2 含 inline dict 字串」改為「驗 SSOT migration + 雙模式」。py_compile ✓ / pytest **449 passed**（原 443 + 新 6 雙模式驗證）/ smoke **6 case** 全綠。**[邏輯]** SSOT mode 參數 backward-compat 雙標域；遷移後行為等價。**[邊界]** None/空→default；未知中文→回原值大寫；mode 未知→走 iso 安全默認。**[效能]** O(1) lookup；零新增 IO；三 caller 共享記憶體 dict。**[Debug]** grep `_CCY_NORMALIZE` 在 Fund 只剩 services/currency 與 ledger_service alias 兩處，「3 個 inline copy」事故源頭根除。**架構意義**：Phase 1 audit 證據驅動（不憑記憶重寫）— 找衝突、選 mode 參數避免「ISO vs yfinance」強迫統一、淨減 22 行驗證「消重=真實消膨脹」。K3~K7 排毒清單：K3 `_auto_fetch_moneydj` 抽 helper / K4 Stock `shared/constants.py` 顏色 emoji / K5 Stock yfinance proxy（解 403）/ K6 Fund `fmt_twd()` / K7 Stock health_grade 閾值對齊。User 驗證：reboot → Tab2/T7/Tab5 人民幣計價基金行為應與 PR 前一致。

- **前一版**：feat(fund) PR #283 @ 817a8c5 v19.74 I7：穿透式產業集中度摘要（延伸 I3 個股集中度設計到 sector 維度，完成 I 系列兩 repo 對稱 — Fund I1/I2/I3/I7 + Stock I4/I5/I6）。改動 2 檔 +107：(1) `ui/helpers/concentration.py` +98 — `compute_lookthrough_sectors(portfolio_funds)` 鏡像 I3 純函式（吃 `moneydj_raw.holdings.sector_alloc`，由 fund_repository L4221+ 解析），穿透曝險（某產業）= Σ_基金( 基金佔組合權重 × 該產業佔基金% )，權重用 invest_twd / 全缺則等權，by-name 正規化聚合，top 5 + max；`render_sector_concentration_summary` 三色 banner，閾值 🔴≥30% / 🟠≥20% / 🟢<20%（比 I3 個股 🔴≥10% / 🟠≥6% 寬鬆，因產業數本來就少）。(2) `ui/tab3_portfolio.py` +9 — I3 個股 banner 後並列呼叫 I7 sector banner（同 try/except 容錯模式），Tab3 配置總覽顯示順序：新鮮度條 → 🎯 個股集中度 → 🏭 產業集中度。py_compile ✓ / pytest **443 passed 零回歸** / smoke **5 case**（兩檔加權聚合資訊科技 36% 跨2檔 / 無 sector_alloc 空 / 等權 fallback B 40% / 髒項過濾 / 空輸入）全綠。**[邏輯]** 與 I3 個股算法同構（加權聚合 + by-name 正規化 + top 5），閾值依「產業數遠少於個股數」放寬 3 倍；零新 IO。**[邊界]** 空組合/無 sector_alloc → 靜默；髒項過濾；invest_twd 全 0 → 等權；try/except 外層。**[效能]** 純 dict 聚合 + HTML markdown ~ms 級。**[Debug]** 與 I3 並列讓 user 一眼看「重押個股 vs 重押產業」兩維度。**架構意義**：I7 示範「同構算法延伸」— 不重寫，把 I3 純函式骨架 copy 改聚合 key（top_holdings.name → sector_alloc.name）；I 系列七棒收官兩 repo 高度對稱。User 上線驗證：reboot → Tab3 載入組合 → 個股集中度下方應顯示「🏭 穿透式產業集中度」banner。下一步候選：等 user 新方向 / 兩 repo cross-platform 個股↔基金深化。

- **前一版**：fix(fund) PR #282 @ 5cf07b9 v19.73 K1：Tab2/Tab3「含息報酬率/1Y 總報酬」4 處漏接 SSOT 補接（user 17:55 定位「Tab2 vs Tab3 數字打架」根因修復）。**邏輯審查**：v18.134 已抽 `compute_1y_total_return` SSOT (`ui/helpers/macro_helpers.py:284`)，4 級 fallback chain（perf["1Y"] wb01 > ret_1y_total > ret_1y > NAV 年化），但 grep 找到 4 處保留舊散落算法繞過 SSOT：(a) `tab2_single_fund.py:L1440` 投資試算累積型估市值 `m.get("ret_1y_total") or m.get("ret_1y")` — **缺 perf['1Y'] 優先級**，重現 v18.65 JFZN3 51%→15% bug；(b)(c)(d) `tab3_portfolio.py:L1021/L1070/L1670` 三處配息覆蓋率 / div_safety_check `_mj.get("perf",{}).get("1Y") or _m.get("ret_1y") or 0` — 缺 ret_1y_total 中間層與 NAV fallback。改動 2 檔 +24/-11：四處統一改 `compute_1y_total_return({"metrics", "moneydj_raw"})` 取 tuple `(_tret_v, _)`，`_tret = float(_tret_v or 0)`。**K2 cache 驗證**：`fetch_fund_from_moneydj_url` 已有 `@_ttl_cache(ttl_sec=900)` + `@register_cache`（module-level dict 跨 Tab 共享），Tab2/Tab3/Tab3-T7 caller 都直接傳 URL，同 URL cache hit。**不需新增 `@st.cache_data`**。py_compile ✓ / pytest **443 passed 零回歸** / smoke **5 case**（perf wb01 優先 / ret_1y_total fallback / 短窗口 100d 註記 / 全空 None / JFZN3 51%→15% 修復）全綠。**[邏輯]** SSOT 4 級 chain 統一所有 caller，從「散落算法」收斂成「單一函式」；K2 cache 已正確跨 Tab 共享。**[邊界]** helper 全空→None caller 用 `or 0`；perf 部分缺欄→fallback 下一級；短窗口加註記；跨 schema（Tab2 fund_data + Tab3 portfolio_funds[i]）統一讀 metrics + moneydj_raw。**[效能]** O(1) dict lookup × 4 漏接點 = 微秒級；MoneyDJ ttl_cache 已共享，零新增 IO。**[Debug]** v18.134 抽 SSOT 但未一次補完所有 caller，散落 4 處在 user 體感「Tab2 vs Tab3 數字不同」中暴露 — 提醒：抽 SSOT 後必須 grep 完全替換，否則「半 SSOT」比沒抽更糟。**架構意義**：user 反映「數據打架」實證 — 不是新算法，是漏接已有 SSOT；不是重複造輪子，是用了不同「輪子」（perf chain vs ret_1y chain）。User 上線驗證：reboot → 同檔在 Tab2「投資試算 1Y 預估」應等於 Tab3「KPI 卡 1Y 含息報酬」。下一步候選：等 user 新方向 / I6 ETF 投組↔總經 / 兩 repo 深化。

- **前一版**：fix(fund) PR #281 @ 69d43d3 v19.72：恢復「原幣別 fallback」selectbox（user 反對 v19.71 寫死 USD）。真正修截圖 bug 的是 `_process_one_fund` 套 `normalize_ccy()` 中文→ISO，selectbox 僅在 MoneyDJ 完全無 currency 欄位才 fallback，非 hardcode。改動 1 檔 +13/-4：恢復 3-col 佈局；selectbox 新增 TWD 為可選項；help 文字明示「中文 currency 自動 normalize 不靠這」。443 pytest passed / py_compile ✓。**架構教訓**：UI 簡化要看 user 真實 workflow，不能把 user-control 當「代碼膨脹」誤砍 — selectbox 是邊界情況的 escape hatch（MoneyDJ 完全無 currency 時）。

## 📋 待辦：K 系列（user 17:55 定位完成，下次接續）
**目標**：架構審查 — Tab2 ↔ Tab3 數字打架 + MoneyDJ 重複抓取
- **K1 數據打架**：Tab2 單一基金 vs Tab3 組合基金「含息報酬率 / 1Y 總報酬」算法不一致。執行：grep `含息報酬|ret_1y|1y_total|perf.*1Y` 在 `ui/tab2_single_fund.py` 與 `ui/tab3_portfolio.py`，找出各自計算路徑 → 若兩處各自算則抽 SSOT 到 `services/fund_metrics.py` 共用 `compute_ret_1y_total(nav_series, dividends)`。
- **K2 效能**：同一檔基金在多 Tab 重複抓 MoneyDJ。執行：驗證 `fetch_fund_from_moneydj_url` 的 `_ttl_cache(ttl_sec=900)` module-level dict 是否真的跨 Tab 共享（理論上 process 內共享）。若有漏接 → 加 `@st.cache_data(ttl=3600)` 層。
- 三步：grep → 抽 SSOT → 驗 cache 共享 → PR + merge + STATE.md

- **前一版**：fix+refactor(fund) PR #280 @ 5b60ae0 v19.71 J3：修 ACCP138 FX 截圖 bug + 抽 currency normalize 共用 SSOT。**根因**：MoneyDJ 對部分保單基金（ACCP138 等）回傳 `currency='美元'`（中文）而非 ISO `'USD'`，組合健診 `_process_one_fund:153` 直接拼 `get_latest_fx('美元TWD=X')` → Yahoo/FRED/open.er-api 三鏈全敗 → 錯誤訊息洩露中文「FX 美元TWD 抓不到」。**user 實證「重複造輪子」**：3 個 Tab 各自寫了同款 `_CCY_NORMALIZE`（services/ledger_service:43 + ui/tab3_t7_ledger:241 + ui/tab2_single_fund v18.278），組合健診（Tab5）漏接 → bug。改動 3 檔 +64/-38：(1) 新增 `services/currency.py` SSOT — `CCY_NORMALIZE` dict + `normalize_ccy(raw, default="USD")` 純函式（純 dict O(1) lookup，零 IO/依賴），17 個中文→ISO 映射（美元/歐元/日圓/澳幣/紐幣/南非幣/瑞郎/新幣/加幣/英鎊/港幣/人民幣/台幣 各含正體別名）。(2) `services/ledger_service` 改 alias import 共用版（既有 `_CCY_NORMALIZE` / `_norm_ccy_pure` 名稱保留作向後相容，caller 零異動）。(3) `tab_fund_grp_health.py`：移除「原幣別 fallback」selectbox（user 要求），改 3-col → 2-col；`_process_one_fund` 套用 `normalize_ccy(fd.get("currency"))`；TWD 基金短路 `fx=1.0` 不打 API（鏡像 tab2 v18.278 設計）；fallback 寫死 `USD`。py_compile ✓ / pytest **443 passed 零回歸** / smoke **7 case**（normalize_ccy 中文+ISO+空+None+未知+default 覆蓋 / ledger_service 向後相容 / ACCP138 bug repro 確認 ccy=美元→USD）。**[邏輯]** SSOT 單一字典；組合健診中文→ISO；TWD 短路免抓 FX；fallback USD。**[邊界]** None/空→default USD；未知中文→回原值大寫不誤判；TWD 基金 fx=1.0 不誤觸 API；ledger_service alias 維持。**[效能]** O(1) dict lookup；TWD 基金省一次 HTTP；同上游 cache 不變。**[Debug]** 錯誤訊息現在顯示 ISO 碼便於排查；TWD 短路日誌清楚。**架構意義**：user 反映「資料打架/重複爬蟲」的擔憂在 currency normalize 這個小點得到實證與修復；但「請給完整 Streamlit 代碼版本」的請求被婉拒 — 兩 repo 共數百 .py 從記憶重寫必然大量幻覺且違背 user 自己提的「精準局部編輯」原則。下次撞到類似 SSOT 漏接時，先 grep 確認是否已有共用 helper 再決定抽出。User 上線驗證：reboot → 組合健診貼 ACCP138 多檔 → 應正常顯示而非 FX 抓不到。下一步候選：I5 跨 Tab 聯動延伸 / I6 ETF 投組↔總經 regime / 等 user 提新方向。

- **前一版**：feat(fund) PR #279 @ 587a1e6 v19.70 J2：組合健診加入 MK 倉位 + 1Y 快算吃本金燈（user 要求「1+2：方法 A 快照吃本金 + MK 買點」雙吃本金判斷視圖）。改動 1 檔 +40/-4：(1) `_process_one_fund` 從 `fd.metrics.pos_label` 直讀 MK 倉位（大跌大買🔥/急跌穩買📈/小跌小買✅/正常波動區/小漲停利💰/急漲停利⚠️/大漲停利🔔），由 calc_metrics 既有計算（年高低 ÷ 3σ 加碼買點）；(2) 從 `nav_dict` 抓接近 365 天前 NAV 作 `nav_1y_ago`（找 ≤ 上次同期日期最近的點），`divs[0].amount` 作 `div_per_unit`，`dividend_freq` 字串映射 `_freq_map={"月配":12,"季配":4,"半年":2,"年配":1}` fallback 12，呼叫 `services.fund_service.calc_health_from_manual` 取 `health` 字串作「快算燈號（1Y）」；(3) 原「燈號 🧮」改名「燈號（全期 🧮）」，KPI 統計 `n_eat/n_warn/n_good` 同步改 key。py_compile ✓ / pytest **443 passed 零回歸**。**[邏輯]** 雙視圖互補：「燈號（全期）」= 完整持有期 TWD 回測（compute_dividend_twd_series，gap>2% 吃本金）；「快算（1Y）」= 1年快照 NAV 漲跌+配息率 vs 配息率（calc_health_from_manual，含息<配息→吃本金）；「MK 倉位」= 買賣時機（非吃本金）。**[邊界]** divs 空 / nav_1y_ago 無 / 例外 → ⚪ 資料不足（不爆）；dividend_freq 缺 → fallback 12；MK 倉位缺 → "—"；全程 try/except wrap。**[效能]** 純 in-memory dict 查找 + 既有 metrics 讀取 ~ms 級，零新增 IO。**[Debug]** 雙燈號讓 user 比對「最近 1Y 配息健康度」vs「整段持有期 TWD 損益」，MK 倉位明示是否在買賣點。設計沉澱：J 系列回應 user 對組合健診實用性疑慮，J1 補欄位（費用率/換匯/年均配息），J2 補吃本金雙視圖+MK 倉位，組合健診從「單一判斷」升級為「多角度比較」。User 上線驗證：reboot → 組合健診貼多檔代號 → 表格含「燈號（全期 🧮）」「快算燈號（1Y）」「MK 倉位」三個獨立燈號欄。下一步候選：H2 Stock 端 cold-start 效能 / I5 跨 Tab 聯動。

- **前一版**：fix+feat(fund) PR #278 @ a969967 v19.69 J1：macro KeyError 修復 + 組合健診欄位擴充。(1) Bug Fix：`tab1_macro.py:991` `phase["phase"]` KeyError 防衛 — 改 `phase = st.session_state.get("phase_info") or {}`，加 `if "phase" not in phase: st.warning + return`，消除 `phase_info` 為 None 或 `{}` 時整個 app 崩潰（此為 KeyError Traceback 截圖呈現的根因）。(2) Feat J1：組合健診 `_process_one_fund` 加 5 新欄位：`最高經理費%`（`fd.get("mgmt_fee")`，MoneyDJ 最高經理費(%)）、`配息頻率`（`fd.get("dividend_freq")`）、`年均配息 TWD🧮`（累積配息 ÷ 持有年數）、`年化淨值%🧮`（NAV 年化漲跌）、`換匯資訊🧮`（"1M TWD→X CCY @ rate"，顯示買入換匯方向）。`_render_health_table` 加 plotly 分組柱狀圖（≥2 檔才顯示）：年化配息率% / 含息年化% / 年化淨值% 三柱並排，zero 基線，容錯 try/except。改動 2 檔 +43 行。443 tests passed / py_compile ✓ / AST ✓。**[邏輯]** mgmt_fee/dividend_freq 從 fd 直讀（MoneyDJ 解析已有）；年均配息 = total_twd / max(years, 0.01)；換匯資訊用 buy_fx + principal_ccy；圖只在 ≥2 檔才渲染。**[邊界]** mgmt_fee/dividend_freq 缺 → "—"；years=0 → 除以 0.01 防炸；圖渲染失敗 → caption 不爆；phase_info None → warning + return 不爆。**[效能]** 純 in-memory 加欄 + plotly HTML ~ms 級。**[Debug]** 換匯資訊欄讓 user 一眼看「100萬TWD換多少外幣 / 用什麼匯率」；費用率 + 配息頻率對多基金橫向比較。User 上線驗證：Streamlit Cloud reboot → 總經 Tab 不再 KeyError 崩潰 → 組合健診貼多檔代號 → 表格含 5 新欄 + 比較圖。J1 收官（兩 issue 一 PR）。下一步候選：H2 Stock 端效能。

- **前一版**：perf(fund) PR #277 @ ce11ec4 v19.68：H — 組合健檢 N 檔基金並行化（cold-start 效能極致化）。Tab5 組合健檢 `_run_batch_health` 原逐檔序列迴圈，每檔序列跑 `_auto_fetch_moneydj`（MoneyDJ 2-30s）+ `get_latest_fx`，10 檔可達數十秒。改 ThreadPoolExecutor 並行（鏡像 Tab3 portfolio_load + macro 4-way 既有模式）。改動 1 檔 +33/-9 淨：(1) 抽 `_process_one_fund(code, principal_twd, ccy_hint, warn_gap)` worker — 把原 per-fund body verbatim 抽出，回傳 row dict（與舊版完全一致零行為變化）；無任何 `st.*` 呼叫故 thread-safe。(2) `_run_batch_health` 改用 `ThreadPoolExecutor(max_workers=min(n,4))` 提交所有 codes，`as_completed` 在主執行緒更新進度條；by-index 收集保留輸入順序與重複代碼；`finally prog.empty` 確保清理。並行安全性：`_auto_fetch_moneydj`/`get_latest_fx`/`compute_dividend_twd_series` 皆無 st 呼叫（純 repository/service），Tab3 portfolio_load 已證實 MoneyDJ 並行抓取 thread-safe；進度條僅主執行緒操作。py_compile ✓ / ruff baseline **622 → 622 零新增**（All checks passed）/ functional smoke **5 case**（monkeypatch worker 模擬 IO：並行保序 + 實測 0.41s vs 序列 1.0s（5檔×0.2s/4worker）/ 重複代碼保留 by-index / 失敗檔+worker 例外各自容錯不影響其他 / 空 codes→[] / principal_twd 參數正確傳入）全綠 / pytest test_app_smoke **96 passed 零回歸**。**[邏輯]** worker 回傳 row dict 結構完全等價舊序列版；ThreadPoolExecutor + as_completed 並行 IO，主執行緒更新進度；by-index slot 保序保重複。**[邊界]** n=0 → 早回 []；worker 例外 → future.result() 拋出在主執行緒 catch 成錯誤列；任一 slot 未填 → 防呆補錯誤列；finally 確保 prog.empty。**[效能]** N 檔 wallclock 從 Σ(每檔) → max(每檔)×ceil(N/4)；10 檔 MoneyDJ 序列數十秒 → 並行約 1/4；max_workers=4 對 NAS proxy 友善不過載。**[Debug]** 進度條改顯「已完成 X/N」（並行無單檔順序）；錯誤列保留 code + 例外型別便於排查。效能系列沉澱：H 延續 v19.46-49 macro 並行化策略到 Tab5 組合健檢，剩餘 cold-start 大瓶頸（逐檔 MoneyDJ 序列）收斂；worker 抽取 + ThreadPoolExecutor 為本專案標準並行重構模式（Tab3/macro/Tab5 三處一致）。User 上線驗證：reboot → 組合健檢貼多檔代號 → 按「🩺 開始健診」→ 載入應明顯加快（進度條顯「已完成 X/N」），結果與序列版一致。**🎉 G + H（user 同批點選）兩棒收官。** 下一棒候選：H2 Stock 端對應效能（個股 6 IO 已並行，找剩餘序列點）/ G2 Stock 端資料異常 AI 解讀（鏡像 G 到 sidebar_health）/ I5 更多跨 Tab 聯動。

- **前一版**：feat(fund) PR #276 @ bca7db5 v19.67：G — 資料異常 AI 解讀按鈕（Gemini AI，user 授權 API 額度）。在 v19.63 F sidebar「全局資料健康」panel 偏舊（🔴/🟠）時，新增「🤖 AI 解讀資料異常」按鈕，按需呼叫 Gemini 生成白話解釋「哪些資料偏舊/失敗 + 可能原因 + 建議動作」。**成本控制**：純按需觸發 — 只有 user 主動點按鈕才打 Gemini，零自動 API 消耗；結果存 session_state 避免重複呼叫。改動 1 檔 +40：`ui/helpers/freshness.py` 新增 `_render_data_health_ai(session_state, lines)` — **重用既有** `services.ai_service.gemini_generate(prompt, max_tokens, keys, start)`（多 key 輪替，L660）+ `get_gemini_keys()`（L623），不自造 API 呼叫；prompt 由 sidebar 健康摘要 lines 組裝，要求繁中 3-4 句白話（資料偏舊判斷 / 原因 API額度·網路·上游延遲 / 建議動作），max_tokens=500；`render_sidebar_data_health` 在 🔴/🟠 偏舊 caption 後 call helper（`_lines`/`session_state` 在 scope）。py_compile ✓ / ruff baseline **622 → 622 零新增**（freshness All checks passed）/ functional smoke **4 case**（mock st.button + gemini_generate：按鈕未按→零 API 呼叫無回覆 / 按鈕按下→呼叫+存 session+顯示 / 快取回覆按鈕未按也顯示避免重複呼叫 / gemini import 失敗→容錯訊息）全綠 / pytest test_app_smoke **96 passed 零回歸**。**[邏輯]** 按需觸發：st.button 未按時純顯示快取回覆（若有），按下才組 prompt 呼叫 gemini_generate；prompt 吃 sidebar 已算的健康摘要 lines。**[邊界]** 僅 headline 🔴/🟠 時整段渲染（🟢 健康時不顯按鈕）；gemini import/呼叫例外 → session 存「⚠️ AI 解讀失敗」；無 key → gemini_generate 自回「未設定 Gemini API Key」。**[效能]** 零自動 API 消耗（按鈕才打）；結果 session_state 快取避免重複；max_tokens=500 控制單次成本。**[Debug]** 回覆存 `_data_health_ai_resp` 持久顯示；help text 明示「消耗 API 額度，點了才打」讓 user 知情。設計理念：AI 戰情室定位的 G 系列，把 Gemini 從「總經 AI 裁決」延伸到「資料健康 AI 解讀」，按需觸發控制成本符合 user 授權範圍。User 上線驗證：reboot + 設 GEMINI_API_KEY → 載入各 Tab 讓資料偏舊 → sidebar panel 偏舊時出現「🤖 AI 解讀資料異常」按鈕 → 點擊顯示 AI 白話解讀。下一步：H — cold-start 效能極致化（user 同批點的第二棒）。

- **前一版**：feat(fund) PR #275 @ 4294c67 v19.66：I3 — 穿透式持股集中度摘要（跨 Tab/跨區塊 訊號聯動第三棒）。把 Tab3 配置總覽補上「穿透式持股集中度」摘要，與下方 T5 兩兩基金重疊度互補：T5 說「基金 A 與 B 持股 70% 相似」（pairwise，lazy 按鈕觸發）、I3 說「你的組合實際 12% 集中在 NVIDIA（跨 3 檔）」（look-through，即時顯示於配置總覽）。改動 2 檔 +129：(1) 新增 `ui/helpers/concentration.py` `compute_lookthrough_concentration(portfolio_funds)` 純函式 — 穿透曝險（某股）= Σ_基金( 基金佔組合權重 × 該股佔基金% )，權重用 invest_twd 全缺則等權；回傳 top5 個股 (顯示名, 曝險%, 出現檔數) + max_exposure + n_with_holdings；`render_concentration_summary` 渲染 🔴≥10% 高度集中 / 🟠≥6% 偏集中 / 🟢 相對分散，附 `_zh_holding` 中文名 + 跨 N 檔標記，🔴 時 caption 警示並導引下方 ④ T5 持股重疊度診斷。(2) `ui/tab3_portfolio.py:L1275` E3 新鮮度條後插入（`_pf_loaded` 在 scope）。**差異化設計**：選穿透集中度而非鏡像 T5 矩陣 — 更便宜（純 dict 聚合非 NxN 矩陣）、更直接回答「我實際押在哪些個股」、零新 IO（吃已載入 `moneydj_raw.holdings.top_holdings`）。py_compile ✓ / ruff baseline **622 → 622 零新增**（新檔 All checks passed）/ functional smoke **7 case**（穿透曝險聚合 NVIDIA 12% 跨 2 檔 / 無金額等權 fallback 15% / 無 holdings 空 / render 高度集中 🔴+caption / render 分散 🟢 無警示 / 無持股靜默 / 髒項+無 name holding 過濾）全綠 / pytest test_app_smoke **96 passed 零回歸**。**[邏輯]** 穿透曝險 = 基金權重 × 該股佔基金%，跨基金 by name(upper/strip) 聚合；同股在同基金只計一次檔數（`_seen_in_fund`）；top5 排序顯示。**[邊界]** 無組合/無 holdings → 靜默 return；非 dict 髒項 + 無 name holding 過濾；pct 非數值 → 0；invest_twd 全 0 → 等權；Tab3 呼叫端 try/except 不擋主畫面。**[效能]** 純 dict 聚合（非矩陣）+ HTML markdown ~ms 級，零新增 fetch/cache。**[Debug]** 🔴/🟠/🟢 三級 + 跨 N 檔標記讓 user 一眼看重押個股；caption 導引下方 T5 看兩兩重疊細節，兩區塊互補不重複。I 系列設計沉澱：I1 總經→組合（推送 regime）、I2 單檔↔組合（持倉成員）、I3 組合內穿透集中度（聚合 holdings）— 三棒皆零新 IO 純既有資料 reuse，從「跨 Tab」延伸到「跨區塊」聯動；I3 刻意與既有 T5 互補而非重複（look-through vs pairwise），呼應 §1/§2「動工前確認既有邏輯」。User 上線驗證：Fund Streamlit Cloud reboot → Tab3 載入組合 → 配置總覽（新鮮度條下方）應出現「🎯 穿透式持股集中度」摘要，列跨基金重押前 5 大個股 + 集中度燈號；重押同股時 🔴 + 警示導引下方 T5。下一步候選：I4 — Stock 端跨 Tab 聯動（個股↔總經 regime，鏡像 I1 概念到 Stock）/ G — Gemini AI 異常解釋（需授權）/ H — cold-start 效能。

- **前一版**：feat(fund) PR #274 @ 3fa008e v19.65：I2 — 單檔↔組合持倉聯動 banner（跨 Tab 訊號聯動第二棒）。**設計轉折（§1 防幻覺價值）**：原構想「鏡像 I1 macro 聯動到 Tab2」經 re-read 發現冗餘 — Tab2 L345 已有 `mk_fund_signal(fd, phase, score)` 做總經→單檔聯動（asset_class + 自動配比建議 + 操作訊號），故改交付真正缺的跨 Tab 訊號：Tab2 單檔 ↔ Tab3 組合持倉。研究單檔基金時讀 Tab3 `portfolio_funds`（session_state），顯示「此基金是否已在你的組合 / 佔多少權重」，避免重複加碼、看清現有曝險。改動 2 檔 +77：(1) 新增 `ui/helpers/portfolio_linkage.py` `render_fund_portfolio_membership(session_state, fund_codes, fund_name)` — 比對 `portfolio_funds`（item: code/name/invest_twd/is_core），命中顯「✅ 已在組合佔 X%（NT$ Y）｜核心/衛星」、未命中顯「➕ 尚未加入 N 檔組合」、無組合則靜默（不打擾只用單檔的 user）。(2) `ui/tab2_single_fund.py:L343` E3 新鮮度條後插入，傳 `fund_codes=[fk, fund_code, full_key]` + `fund_name=name`（多識別碼交集 + name fallback 比對，upper/strip 正規化）。py_compile ✓ / ruff baseline **622 → 622 零新增**（新檔 All checks passed）/ functional smoke **7 case**（無組合靜默 / 命中 code 不分大小寫 60% 核心 / 命中衛星 40% / 未命中尚未加入 2 檔 / name fallback 命中 / 命中但金額 0 無權重 / 髒項過濾）全綠 / pytest test_app_smoke **96 passed 零回歸**。**[邏輯]** 純讀 Tab3 已寫入 session_state 的 portfolio_funds；code 多識別碼交集比對 + name fallback；權重 = 該檔 invest_twd / 組合總額 ×100。**[邊界]** 無組合 / portfolio_funds 非 list → 靜默 return；髒項（非 dict）isinstance 過濾；invest_twd 0 → 顯成員但不顯權重；Tab2 呼叫端 try/except 不擋主畫面。**[效能]** 純讀 session_state + HTML markdown ~ms 級，零新增 fetch/cache（reuse Tab3 已載入結果）。**[Debug]** 命中綠框顯權重 + 核心/衛星定位，未命中黃框提示可加入；無組合靜默避免洗版。跨 Tab 聯動系列設計沉澱：I1=Tab1總經→Tab3組合（推送 regime）、I2=Tab2單檔↔Tab3組合（持倉成員/權重），皆零新 IO 純 session_state reuse；I2 的 §1 re-read 避免冗餘是治理協議實效範例（mk_fund_signal 早已覆蓋總經→單檔，硬做會重複）。User 上線驗證：Fund Streamlit Cloud reboot → 先在 Tab3 載入組合 → 切 Tab2 查組合內某檔 → 應顯「🔗 ✅ 已在你的組合 權重 X%」；查組合外基金 → 顯「🔗 ➕ 尚未加入」。下一步候選：I3 — 組合重疊基金 ↔ 持股集中度跨區塊提示（Tab3 內 T5 持股重疊度 ↔ 配置總覽）/ G — Gemini AI 異常解釋（需授權）/ H — cold-start 效能。

- **前一版**：feat(fund) PR #273 @ 3d6fb2d v19.64：I1 — 總經→組合曝險聯動 banner（新系列「跨 Tab 訊號聯動」首棒，user 點選方向 I）。Tab3（組合基金）配置總覽讀 Tab1（總經）已算好的 `phase_info`/`systemic_risk_data`（session_state），把景氣 regime + 建議資產配置 + 系統性風險疊加到組合視圖，讓 user 不切 Tab 即看到「總經 → 建議配置」聯動。改動 2 檔 +107：(1) 新增 `ui/helpers/macro_linkage.py` `render_macro_exposure_link(session_state, core_pct)` — 讀 `phase_info`（`calc_macro_phase` 機構級評分 0-10 結果：`phase` 衰退/復甦/擴張/高峰、`score`、`alloc{股票,債券,現金}`、`advice`、`rec_prob` 衰退機率、`alerts`、`trend_arrow`/`next_phase` 拐點）+ `systemic_risk_data`（risk_level/risk_icon/risk_score），渲染景氣聯動 banner：景氣階段 + 評分 + 轉折箭頭 + 衰退機率 + 系統性風險 + 建議股債現金配置 + advice + 前 2 條風險警報。(2) `ui/tab3_portfolio.py:L1252` KPI 字卡後插入 banner（傳 `_core_pct_kpi` 作 context）。**誠實性設計**：`phase_info.alloc` 是「股/債/現金」資產類別軸（calc_macro_phase 輸出），與組合「核心/衛星」軸不同 → banner 分開呈現不硬湊等號（核心 context 加註「與股債配置不同」）；僅在防禦 regime（衰退/高峰）或系統性風險 HIGH **且** 核心比例 <50% 時給輕量 nudge「可考慮提高核心、降衛星曝險」。py_compile ✓ / ruff baseline **622 → 622 零新增**（新檔 All checks passed）/ functional smoke **6 case**（macro 未載入→提示 / phase_info 空→容錯 / 擴張期完整聚合+無 nudge+alert / 衰退期+核心低 35%→nudge 觸發 / 衰退期+核心高 80%→不 nudge / core_pct=None→不顯 context）全綠 / pytest test_app_smoke **96 passed 零回歸**。**[邏輯]** 純讀 Tab1 已寫入 session_state 的 `phase_info`（calc_macro_phase 加權評分 → 四階段 + alloc）；core_pct 作 context 不與 alloc 等號；nudge 僅防禦 regime + 高風險 + 核心偏低觸發。**[邊界]** macro 未載入 / phase_info 空 → 容錯提示「載入總經 Tab」；rec_prob/core_pct 非數值 → try/except 跳過；alerts 取前 2 條避免洗版；Tab3 呼叫端 try/except 不擋主畫面。**[效能]** 純讀 session_state + HTML markdown ~ms 級，零新增 fetch/cache（complete reuse Tab1 已算結果）。**[Debug]** banner 標「來自 Tab1」明示資料源；核心 context 加註「與股債配置不同」避免誤解兩軸；nudge 文字含實際核心%便於 user 對照。設計理念：跨 Tab 聯動把 Tab1 的 macro regime 訊號「推送」到 Tab3 portfolio 決策現場，避免 user 來回切 Tab 對照；首棒選最自然的「總經→組合配置」契約點，零新 IO 純 session_state reuse 降低風險。User 上線驗證：Fund Streamlit Cloud reboot → 先載入 Tab1 總經 → 切 Tab3 組合 → KPI 卡下方應出現「🧭 總經景氣聯動」banner（景氣階段 + 建議配置 + 風險）；未載入總經時顯「載入總經 Tab 後顯示」提示。下一步候選：I2 — 單一基金 Tab2 同款總經聯動 / I3 — 組合重疊基金 ↔ 持股集中度跨區塊提示 / G — Gemini AI 異常解釋（需授權）/ H — cold-start 效能。

- **前一版**：feat(fund) PR #272 @ a60f41f v19.63：F — Sidebar 全局資料健康總覽（新系列「全局聚合監控」首棒）。把散落各 Tab 的資料新鮮度（Tab1 總經 FRED / Tab3 組合基金 NAV / Tab2 單一基金）聚合到 sidebar，讓 user 一眼看出哪些資料源已過期、該按全域刷新，補齊 C2（v19.59）全域刷新按鈕旁的「刷新前先看哪舊」動線，直接服務 user 根本訴求「保證面板資料是新的」。改動 2 檔 +128：(1) `ui/helpers/freshness.py`：(a) 抽出 `nav_age_emoji(nav_date, today)` 共用 traffic-light（🟢≤2d/🟠≤7d/🔴>7d/⬜未知，回 `(emoji, age|None)`），banner 與 sidebar 共用；(b) `_nav_counts(nav_dates, today)` → `(headline=最差燈, {green/yellow/red/unknown})`；(c) `render_sidebar_data_health(session_state, now_tw)` 聚合 `_fred_sources`（命中率 X/Y）+ `macro_last_update`（抓取 age `Nh前`，>4h 把綠降橙）+ `portfolio_funds`（組合 NAV 紅綠燈統計，過濾非 dict 髒項）+ `fund_data`（單檔 NAV），各域一行 emoji 摘要 + 整體 headline=各域最差燈號（紅>橙>綠>未知）；全空 → 「尚未載入」提示；偏舊（🔴/🟠）→ 提示按全域刷新。(2) `app.py:L264` C2 全域刷新區「之前」插入「📊 全局資料健康」panel（sidebar 先於 Tab render，全 key 容錯；except 加 `# noqa: smoke-allow-pass` 白名單過 `test_no_silent_except_pass`）。py_compile ✓ / ruff baseline **622 → 622 零新增** / functional smoke **6 case**（nav_age_emoji 5 態 / _nav_counts headline=worst / 空 session→尚未載入 / 完整三域聚合+提示 / macro_done fallback / portfolio 髒項過濾）全綠 / pytest test_app_smoke **96 passed 零回歸**。**[邏輯]** sidebar 讀 session_state 已被各 Tab 填入的新鮮度 metadata（`_fred_sources`/`macro_last_update`/`portfolio_funds`/`fund_data`）；headline 取各域最差燈號；macro age >4h 把綠降橙呼應 tab1_macro 既有閾值。**[邊界]** sidebar 先於 Tab render → 首次全 key 未填 → 「尚未載入」；`portfolio_funds` 含非 dict 髒項 → isinstance 過濾；`macro_last_update` tz-aware datetime → `now_tw()` 算 age 例外容錯；整 panel 包 try/except 不擋主畫面。**[效能]** 純讀 session_state + in-memory 聚合 + HTML markdown ~ms 級，零新增 fetch/cache。**[Debug]** 一眼掃三域健康，紅/橙時主動提示按全域刷新，形成「先看哪舊→再刷新」閉環，與 C2 全域刷新按鈕上下相伴。設計理念：A~E 系列做「per-Tab 新鮮度可視化」，F 是 capstone「全局聚合」，把分散訊號收斂到 sidebar 單一視窗。User 上線驗證：Fund Streamlit Cloud reboot → sidebar 應出現「📊 全局資料健康」panel（在 🧹 全域刷新上方）；切換各 Tab 載入資料後重整 sidebar，panel 顯示三域聚合紅綠燈 + 偏舊提示。下一步候選：F2 — Stock 端對應 sidebar 全局資料健康（鏡像 F，聚合 K線/籌碼/融資/財報/總經各源）/ G — Gemini AI 摘要整合（資料源異常時主動 AI 解釋）/ H — cold-start 效能極致化。

- **前一版**：feat(fund) PR #271 @ a509db8 v19.62：E3 — Tab2/Tab3 MoneyDJ 資料新鮮度 banner 補完。鏡像 Stock v18.197 個股新鮮度條，延伸 v19.61 E1 從 Tab5 到 Tab2（單一基金）+ Tab3（組合基金），讓 Fund 端三個基金 Tab 都有資料新鮮度可視化，與 Stock 端對齊。改動 4 檔 +113/-60（淨 +53）：(1) **新增 `ui/helpers/freshness.py`（78 行）** `render_mj_freshness_banner(items, title)` 共用 helper — item 格式統一 `{code, name, nav_date, fetched_at}`（缺則容錯）；traffic-light 🟢≤2d / 🟠≤7d / 🔴>7d；hover tooltip 三層資訊（`code ｜ NAV ｜ 抓取於 ｜ 延遲 Nd`）；summary chip `🟢 X | 🟠 Y | 🔴 Z | ⬜ W`。(2) `ui/tab_fund_grp_health.py` `_render_mj_freshness_banner` 改薄包裝 call 共用版（向後相容；**§2 大掃除清掉 60 行 dead code**，從 60→9 行 wrapper）。(3) `ui/tab2_single_fund.py:L331` 「① 基本資料」success 訊息後插入單檔新鮮度條，直讀 `fd` 的 `nav_date` / `_moneydj_fetched_at`。(4) `ui/tab3_portfolio.py:L1253` KPI 字卡組合後插入組合層級新鮮度條，迭代 `_pf_loaded` 從 `moneydj_raw` 取欄位（注意 Tab3 portfolio_funds 結構：`_moneydj_fetched_at` 包在 `moneydj_raw` 內，需 `_f.get("moneydj_raw").get("_moneydj_fetched_at")` 兩層取）。py_compile ✓ / ruff baseline **622 → 622 零新增** / functional smoke **5 case**（4-item mixed traffic-light / 空 list early-return / 缺欄位 graceful / 異常日期格式 catch ValueError → ⬜ / Tab5 舊呼叫者 `_render_mj_freshness_banner` 向後相容）全綠 / pytest test_app_smoke **96 passed 零回歸**。**[邏輯]** 純顯示 helper 從 v19.61 E1 抽出泛化（item key 標準化 `code/name/nav_date/fetched_at`、title 參數化讓三 Tab 可客製）；Tab2 餵單 item 顯單檔 chip + summary、Tab3 迭代 `_pf_loaded` 餵多 item、Tab5 包裝層轉舊鍵（`基金名` → `name`、`_nav_date` → `nav_date` 等）到新格式。**[邊界]** 空 list → early return 不渲染；item 缺欄位 → unknown(⬜)；`nav_date` 異常格式 → `try/except (ValueError, TypeError)` → ⬜；三 Tab 呼叫端各自 `try/except Exception:pass` 包覆，import 失敗或運行異常不擋主畫面。**[效能]** 純 in-memory iter + HTML markdown ~ms 級，零新增 fetch/cache；共用 helper DRY 避免三 Tab 重複維護同一段 60 行 UI code。**[Debug]** hover tooltip 完整時戳，三 Tab 共用 banner UI 視覺一致；Tab5 舊呼叫者繼續用 `_render_mj_freshness_banner` 不需改其他呼叫端；helper 可未來再延伸給 ETF / 配置模擬器等 Tab 共用。設計差異 vs E1：E1 在 Tab5 內定義 60 行 banner 邏輯，E3 抽到 `ui/helpers/freshness.py` 共用模組，三 Tab 統一呼叫；E3 也展示了**「Tab5 包裝層 → 共用 helper」漸進式重構模式**避免 breaking change。User 上線驗證：Fund Streamlit Cloud reboot → Tab2 查單檔基金 → success 訊息下方應出現「📊 MoneyDJ 資料新鮮度」banner（單檔 chip + summary `🟢 1 / 🟠 0 / 🔴 0 / ⬜ 0`）；Tab3 組合 → KPI 字卡下方應出現組合層級 banner（多檔聯合統計 + summary chip）；Tab5 既有 banner 維持不變。**🎉 E 系列三 PR 全部收官**（E1/E2/E3 全綠），A/B/C/D/E 五大系列完整關閉，等 user 點題新方向。

- **前一版**：feat(fund) PR #270 @ 5e184c8 v19.61：E1 — MoneyDJ NAV 資料新鮮度 banner 整合。開新系列「跨 repo 對稱補完」首棒。鏡像 Stock v18.201 D2 (FinMind `last_update`) 同款設計理念，補上 Fund 端 MoneyDJ 資料源「抓取時戳」可見化。問題：Fund 端 Tab2/Tab3/Tab5 目前**完全沒有資料新鮮度 chip**（Stock 端已建立完整框架但 Fund 端缺一塊），user 在組合健檢查多檔基金時無從得知哪檔 NAV 較舊、何時抓的，可能誤用過期資料做判斷。改動 2 檔 +77/-1：(1) `repositories/fund_repository.py:2768` `fetch_fund_from_moneydj_url` result dict 加 `_moneydj_fetched_at` = `datetime.now().strftime("%Y-%m-%d %H:%M:%S")`，純新增欄位、零影響既有 caller（讀不到的就跳過）；(2) `ui/tab_fund_grp_health.py` (a) `_run_batch_health` row 多帶 `_nav_date`（從 `fd.get("nav_date")` 截取前 10 字元 YYYY-MM-DD）+ `_fetched_at`（從 `fd.get("_moneydj_fetched_at")`），`_` 開頭自動被 `_render_health_table` pandas DataFrame 過濾排除表格；(b) 新增 `_render_mj_freshness_banner(ok_rows)` helper — KPI 卡之前 banner，逐檔顯示 `[🟢/🟠/🔴] fund_name | nav_date/fetch_HH:MM/Nd`，hover tooltip 三層 `code ｜ NAV ｜ 抓取於 ｜ 延遲 Nd`，summary chip `🟢 X | 🟠 Y | 🔴 Z | ⬜ W`，traffic-light: 🟢≤2d / 🟠≤7d / 🔴>7d（NAV 發布 T+1~2 + 週末放寬）。py_compile ✓（**先有 f-string backslash SyntaxError** — Python f-string 不允許 expression part 含 `\` 跳脫，預先計算變數 `_nav_show` / `_fetched_show` / `_nav_inline` 後修復）/ ruff baseline **622 → 622 零新增** / functional smoke 4 case：今日/2d/5d/10d → 🟢🟢🟠🔴 全綠 / pytest test_app_smoke **96 passed 零回歸**。**[邏輯]** NAV 日期距今天數決定 traffic-light，週末/連假最新交易日自然落 2-3 天區（仍 🟢），規則寬鬆避免誤報；hover tooltip 用 HTML `title` attr 純前端，無 JS；`_moneydj_fetched_at` 用 result dict 初值方式注入，所有 return path 自動帶到。**[邊界]** `_nav_date` 解析失敗 → ⬜未知；`_fetched_at` 空 → 短碼顯「—」；`_` 開頭 keys 純為 metadata，pandas DataFrame 自動排除；舊 cache pickle 沒有此欄位時 `fd.get(...)` 回 `""` 不爆。**[效能]** 純 metadata + HTML markdown ~ms 級，零新增 fetch / cache；`datetime.now().strftime` 微秒級。**[Debug]** hover tooltip 三層資訊與 banner 內 inline 三段（nav/fetch/age）對應，user 排查資料延遲時清楚區分「MoneyDJ 後台未更新」vs「客戶端 cache 命中」vs「網路抓取失敗」。設計對齊 D 系列對照：D1 (FRED realtime_start) DataFrame 多欄 → D2 (FinMind last_update) Module dict → E1 (MoneyDJ) result dict 多欄 + UI banner inline，三者反映各 data source 的粒度差異。User 上線驗證：Fund Streamlit Cloud reboot → 組合健檢 Tab 貼 ACCP138 / ALBT8 等代號 → 按「🩺 開始健診」→ KPI 卡上方應出現「📊 MoneyDJ 資料新鮮度」banner，含每檔 emoji + 三段 inline 資料 + hover tooltip 完整時戳。下一步候選：**E2** — Stock 端財報三段 fallback chip 標籤化（月營收 / 季財報 / 季財報-extra 鏡像 B1 設計）或 **E3** — Fund Tab2/Tab3 資料新鮮度 chip 補完（鏡像 Stock v18.197）。

- **前一版**：feat(macro) PR #269 @ e18927e v19.60：D1 — FRED `realtime_start` 整合，chip 改用真實發布日。解決 v19.56 B2 FRED 5-chip「資料月份延遲」與「真實發布日延遲」混淆。問題：原 chip 顯示「DGS10:🟢4d」算的是 observation date 距今天數（資料對應的月份/週期日），但 FRED 序列實際發布有 lag — DGS 日頻債券殖利率發布日 ≈ 觀察日（lag ~ 0），M2SL / CPI 月頻則 5 月份資料 BLS 通常 6 月 12 日才公佈（**lag ~ 42 天**），user 看到「M2:🟠40d」會誤以為「M2 過期 40 天」，其實 BLS 才剛發布 4 天前。改動 3 檔 +58/-12：(1) `repositories/macro_repository.py:202` `fetch_fred` DataFrame return 從 `['date', 'value']` 加一欄 `'realtime_start'`（從 observations[].realtime_start 轉 Timestamp，缺欄補 NaT），query string 不動（沿用既有 sort_order=desc/limit=n），呼叫端 `.iloc[-1]["date"]` 零變動；(2) `services/macro_service.py:296` `_fred_sources` 寫入每 series 多帶 `realtime_start` (YYYY-MM-DD) + `publish_lag_days`（observation 與 publish 差距），用 `pd.notna()` 容錯缺欄；(3) `ui/tab1_macro.py:1017` `_fred_chip()` traffic-light 改吃 `realtime_start`，fallback 回 observation date（若 rt 缺）；HTML title hover tooltip 顯示「資料月份 / 發布 / 延遲 Nd」三層資訊；chip 文字尾巴標 `(發布)` 或 `(obs)` 讓 user 一眼看出當前 chip 是用哪個日期算的。py_compile ✓ / ruff baseline **622 → 622 零新增** / functional smoke：DGS 日頻 rt=obs lag=0、CPI 月頻 obs=2026-05-01 rt=2026-06-12 **lag=42d**、realtime_start 缺欄補 NaT 邊界 OK / pytest test_app_smoke **96 passed 零回歸**。**[邏輯]** FRED API observations 已自帶 `realtime_start` 欄位 — 該筆觀測首次進入 FRED database 的日期 ≈ BLS/FED 真實發布日；無需追加額外 API call，純擴充既有 response 解析。**[邊界]** `realtime_start` 欄位缺 → 補 NaT；`pd.notna` 容錯空值；hover tooltip 用 HTML `title` attr 純前端不需 JS。**[效能]** 零新增 API call、零新增 cache；fetch_fred return DataFrame 多一欄 ~ 微秒級開銷；chip 計算多 1-2 行 dict.get。**[Debug]** chip 尾巴 `(發布)` vs `(obs)` 讓 user 一眼看出當前用哪個日期源；hover tooltip 同時顯示三層資訊（資料月份 / 發布 / 延遲）方便排查。User 上線驗證：Fund Streamlit Cloud reboot → 總經 Tab 載入後「📡 FRED 命中」5-chip → hover 應顯示「DGS10 ｜ 資料月份 YYYY-MM-DD ｜ 發布 YYYY-MM-DD ｜ 延遲 Nd」；M2SL chip 尾巴應標 `(發布)` 而非 `(obs)`，距今天數應該更小、更貼近 BLS 真實發布時間。下一步候選：**D2** Stock FinMind dataset `last_update`（Stock dashboard 對應功能）。

- **前一版**：feat(cache) PR #268 @ 85b12e7 v19.59：C2 — Sidebar 全域刷新總開關 4 層清理。補齊 v19.57 C1（Tab1 精準清）後唯一缺口：全 app 一鍵總清。改動 2 檔 +130 行：(1) `infra/cache.py` 新增 `clear_disk_cache() -> dict` 清 `_CACHE_DIR`（/tmp/fund_cache 或 /content/fund_cache）下 *.csv / *.json (NAV/DIV/META) + 清 `_FUND_SNAPSHOT` 記憶體最後一道防線；新增 `global_refresh_all(session_state) -> dict` 統一入口 4 層 — ① `clear_all_caches()` 清全 TTL；② hot_money 兩個 `@st.cache_data.clear()`；③ `clear_disk_cache()` 清 /tmp 落地；④ pop `_GLOBAL_REFRESH_SESSION_KEYS`（10 個跨 Tab macro/portfolio/health 殘留 keys：`_radar_v1921_top` / `_tp_v1948_top` / `indicators` / `phase_info` / `news_items` / `systemic_risk_data` / `_fred_sources` / `macro_done` / `macro_last_update` / `_t3_cur_sheet_title` / `_t3_groups_cache` / `fund_grp_health_codes`）；`_GLOBAL_REFRESH_KEEP_KEYS` frozenset 永遠保留 OAuth 三核心 keys（`gsheet_tokens` / `policy_sheet_id` / `active_policy_id`）避免用戶被踢出。(2) `app.py:264` Streamlit Reboot link 後新增「🧹 全域刷新（清所有快取 + 落地檔）」按鈕，按下 call `global_refresh_all` → `st.toast` 顯示 5 層統計（TTL X 條 / st_cache Y 條 / 落地檔 Z 個 / snapshot W 筆 / session V 鍵）→ `st.rerun()` 強制全 app reload；附警示 caption「會清掉所有快取，下次載入會重打 API；OAuth 登入保留」。**關鍵設計**：嚴禁清 `data_cache/` — 那是上游 cron 排程歷史資料倉（SPX/TWII/VIX/FRED 8 series parquet），砍了要等下個 cron 才補，user 看到的「歷史指標長期趨勢」會瞬間缺資料。py_compile ✓ / ruff baseline **622 → 622 零新增** / functional smoke：4 個 csv/json 被清、`.txt` 保留（驗證 extension filter）、OAuth 三 keys 確認保留、whitelist 3 keys 精準 pop、`random_user_key` 不在白名單未動 / pytest test_app_smoke **96 passed 零回歸**。**[邏輯]** 兩個 frozenset 白名單：`_SESSION_KEYS` 是 pop 列表，`_KEEP_KEYS` 是覆蓋保護（即使 _SESSION_KEYS 誤含 OAuth 也不會被砍）；`clear_disk_cache` 只比對 `.csv` / `.json` extension，使用者放的雜檔（.txt 等）一律保留。**[邊界]** `_CACHE_DIR` 不存在 → `dir_existed=False` 直接 return；hot_money import 失敗 → silent skip；每個 `_os.remove` 各自 try/except；session_state=None 跳過 ④。**[效能]** 4 層各自 try/except 獨立失敗不擋其他層；磁碟清理走 `_os.listdir` + `_os.remove` 純檔案 IO ms 級。**[Debug]** toast 5 層統計即時告知 user「清了什麼」避免 silent action；user 可從統計值區分「TTL miss」vs「落地檔被清」vs「session 殘留」。User 上線驗證：Fund Streamlit Cloud reboot → sidebar 應出現「🧹 全域刷新」按鈕（在 Streamlit Reboot 連結與 Google 帳號之間）→ 按下後 toast 顯示「🧹 全域刷新：TTL X / st_cache 2 / 落地檔 N / snapshot M / session V」→ 各 Tab 進入會重新打 API（OAuth 登入保留不被踢出）。下一步候選：D1 Fund FRED `realtime_start`（publish 精確到 day）/ D2 Stock FinMind dataset `last_update`。

- **前一版**：feat(grp_health) PR #267 @ 10755f5 v19.58：組合健檢 Tab 移植「組合基金」5 大貼圖區塊 — 回應 user request「組合健檢 copy 組合基金內容，但只要貼圖」。改動 2 檔 +469 行：(1) 新增 `ui/helpers/fund_grp_health_extras.py`（420 行）內含 `_build_fund_dict(fd_raw, code, principal_twd)` 把 `_auto_fetch_moneydj` raw 包成 portfolio_funds 標準結構（含 `moneydj_raw / metrics / series / dividends / loaded / invest_twd`）給既有 fund_checkup 直接吃 + `render_fund_grp_health_extras(funds, principal_twd)` entry 依序渲染 5 區塊；(2) 修 `ui/tab_fund_grp_health.py` 2 處：`_run_batch_health` 多保留 `row["_fund_raw"]=fd`（`_` 開頭自動排除表格），`_render_health_table(rows)` 後接 `render_fund_grp_health_extras`。5 大區塊：① 基金體檢 PK 表（與同類型 PK，揪優等生 / 汰弱候選 — 直接 call `render_fund_checkup`）+ ② 逐檔財務健診 4 大功能（吃本金 / 月配息 TWD / 年化配息率 / TER — `render_fund_checkup` 內已含）+ ③ 真實收益 vs 配息率 健康矩陣（Plotly Bar + 紅虛線吃本金警示 — 從 `tab3_portfolio.py:1796-1921` inline 移植）+ ④ 投資試算 — 投入金額 → 單位數 / 月配 TWD（從 `tab2_single_fund.py:1195-1400` 精簡，本金共用 sidebar 輸入）+ ⑤ TER 費用率分析 + 持股分析（產業配置橫條 / 前10大持股 — 從 `tab2_single_fund.py:994-1076` inline 移植）。逐檔深度分析包在 expander（💎 fund_name · code）內，user 可逐檔展開查看。AST ✓ / py_compile ✓ / ruff baseline **622→622 零新增**（新增 6 條 F541 純樣板字串 → `--fix` autofix 全清）/ functional smoke `_build_fund_dict` 結構/邊界 case 通過 / pytest test_app_smoke **96 passed 零回歸**。**[邏輯]** 零重複計算 — fund_checkup / macro_helpers 全部 reuse；`_build_fund_dict` 比對 tab3_portfolio:L1522-1533 portfolio_funds 標準結構；FX 來源用 `repositories.fund_repository.get_latest_fx`。**[邊界]** fd_raw 空 → 回 `{}`；render entry 每區塊獨立 try/except 不擋其他區塊；TER 缺 mgmt_fee 顯⬜ caption；holdings 缺 sector_alloc/top_holdings 顯⬜ caption；FX 失敗時投資試算顯⬜ caption。**[效能]** zero 新增 fetch — 全部吃 `_run_batch_health` 已抓的 fd 結果；逐檔 expander 預設 collapsed 不渲染 → 視覺載入即時。**[Debug]** 5 區塊獨立 try/except 失敗顯短 caption；逐檔分析包在 expander 避免一次渲染 N 檔造成卡頓。User 上線驗證：Fund Streamlit Cloud reboot → 組合健檢 Tab 貼 ACCP138 / ALBT8 / 其他保單代號 → 按「🩺 開始健診」→ 既有 KPI 卡 + 健診總表 + 逐期配息明細之後應出現「🔬 進階分析」標題 + 5 大區塊（基金體檢 PK 表 / 逐檔財務健診 4 大功能 / 真實收益矩陣 / 逐檔深度分析 expander）。下一步候選：C2 Sidebar 全域刷新總開關（含 /tmp pickle + data_cache/）/ D1 Fund FRED `realtime_start` / D2 Stock FinMind dataset `last_update`。

- **前一版**：feat(cache) PR #266 @ 57a95b8 v19.57：C1 — Tab1 精準清快取 helper（不誤殺 Tab2~Tab5）— 收 user 反覆關切的「強制重抓會把其他 Tab 拖下水」副作用。問題：3 個全域「強制重抓」按鈕（總經 header / 流動性區 / 熱錢三角）皆呼叫 `st.cache_data.clear()`，連帶清掉 Tab2 基金詳情 (`fetch_fund_from_moneydj_url` 900s / `get_latest_nav` 300s)、Tab3 GSheet 政策帳本 (`_cached_list_policies` / `_cached_load_policy_v2` 60s)、Tab4 模擬器 / Tab5 健診相關快取，跨 Tab API 配額一次燒光。改動 4 檔 +95/-9：(1) `infra/cache.py` 新增 `clear_caches_by_names(names) -> int` 按函式名精準清 `_CACHE_REGISTRY`；(2) `services/macro_service.py` 新增 `clear_tab1_macro_caches(session_state) -> dict` 統一入口 — 清 Tab1 owned 8 條 TTL cache (`fetch_fred`/`fetch_yf_close`/`fetch_defillama_stablecoin_mcap`/`fetch_macro_compass`/`fetch_ndc_signal_history`/`fetch_tw_pmi_local`/`fetch_tw_export_yoy`/`fetch_foreign_consecutive_days`) + 清 hot_money 兩個 `@st.cache_data` (`fetch_foreign_flow_series`/`fetch_usdtwd_series`) + pop 7 個 Tab1 session keys (`_radar_v1921_top`/`_tp_v1948_top`/`indicators`/`phase_info`/`news_items`/`systemic_risk_data`/`_fred_sources`)；(3) `ui/tab1_macro.py:868` 「🆕 強制重抓最新」改呼叫 helper + `st.toast` 顯示清理數量（TTL X 條 / st_cache Y 條 / session Z 鍵）；(4) `ui/tab1_macro.py:2204` 流動性區 + `hot_money.py:251` 熱錢三角同樣換為 helper。AST ✓ / py_compile ✓ / ruff baseline **131→131 零新增** / functional smoke `{'ttl_cleared':8,'st_cache_cleared':2,'session_keys_popped':2}` 精準命中（驗證 Tab2~Tab5 共用的 `fetch_fund_from_moneydj_url`/`get_latest_nav` **沒被清**）/ pytest test_app_smoke **96 passed 零回歸**。**[邏輯]** `_TAB1_TTL_CACHE_NAMES` frozenset 白名單比對 `_CACHE_REGISTRY` 每個 wrapper 的 `__name__`，命中才 `cache_clear()`；hot_money 兩個 `@st.cache_data` 走自己的 `.clear()` API；session keys 純 in-list 比對 pop。**[邊界]** import `clear_tab1_macro_caches` 失敗 → `try/except pass` 不擋按鈕；session_state=None 時跳過 (3)；每個 `cache_clear()` 各自 try/except；hot_money import 失敗 → 跳過 (2)。**[效能]** 精準清平均省 ~10 條跨 Tab cache 重抓（粗估每條 fund API 500ms~2s → 跨 Tab session 切換省 5~20s）。**[Debug]** toast 即時告知 user「清了多少」，避免 silent action 疑惑；`clear_caches_by_names` 回傳命中數量便於後續加 logging。User 上線驗證：Fund Streamlit Cloud reboot → Tab2 查一檔基金 → 切 Tab1 按「🆕 強制重抓最新」→ toast 出現「TTL 8 條 / st_cache 2 條 / session ≥1 鍵」→ 回 Tab2 該基金詳情應 instant 載入（cache 未被清） / Tab3 政策帳本應 instant 顯示。下一步候選：C2 Sidebar 全域刷新總開關（含 /tmp pickle + data_cache/）/ D1 Fund FRED `realtime_start` / D2 Stock FinMind dataset `last_update`。

- **前一版**：feat(macro) PR #265 @ 9f33edb v19.56：B2 — 5 條 FRED 序列個別命中標籤化（DGS10/DGS2/DGS3MO/HY OAS/M2SL — v19.57 同套 toast 改造延伸）— 延續 Stock B1 (v18.200) 同套「靜默 fallback 可見化」模式，轉戰 Fund 總經 Tab。問題：5 條 FRED 並行池任一失敗或過期 → 依賴指標（YIELD_10Y2Y/YIELD_10Y3M/HY_SPREAD/M2）整個消失，UI 空白且無提示，user 無法區分「FRED API 故障 vs 網路延遲 vs 新鮮數據」。改動 2 處：(1) `services/macro_service.py:225-296` 5 條 FRED 並行池 `.result()` 後新增 `R["_fred_sources"]` 字典記錄 series_id → {success, last_date, rows}；(2) `ui/tab1_macro.py:1010+` 既有 v19.50 資料新鮮度條第三行新增「📡 FRED 命中」5-chip（DGS10/DGS2/DGS3MO/HY/M2）+ traffic-light（日頻 🟢≤4 / 🟠≤14 / 🔴>14 天，月頻 M2SL 🟢≤40 / 🟠≤70 / 🔴>70 天），任一 🔴（API miss / 太舊）→ 下方 🟠 caption 提示「部分 FRED 序列失敗或過期…建議按上方『🆕 強制重抓最新』」。AST ✓ / py_compile ✓ / ruff baseline **127→127 零新增** / pytest test_app_smoke **96 passed 零回歸**。**[邏輯]** `_fred_sources` 從並行池 `.result()` DataFrame `.empty` 反推命中／空回；chip 顏色由 `last_date` 距今天數決定，準確不受 cache hit 影響。**[邊界]** `.empty` / 例外 → `success=False` + `last_date=""` → ⬜未知；ind 缺 `_fred_sources` → chip 不渲染但其他新鮮度資訊照常；舊 session_state cache 容錯。**[效能]** 純 metadata dict + HTML markdown ~ms 級，零新增 fetch / cache。**[Debug]** 5 chip 一覽哪條序列降級，避免 user 截圖逐項對比。User 上線驗證：Fund Streamlit Cloud reboot → 總經 Tab 載入完成 → 「📊 資料新鮮度」條第三行應出現「📡 FRED 命中：DGS10:🟢4d ｜ DGS2:🟢4d ｜ ...」，FRED key 缺/network 掛時相關 chip 轉 🔴 + 出現降級 caption。下一步候選：C1 Per-Tab 精準 `.clear()` / C2 Sidebar 全域刷新總開關 / D1 Fund FRED `realtime_start` / D2 Stock FinMind dataset `last_update`。

- **前一版**：feat(crisis) PR #264 @ 27bf696 v19.55：A5 危機回測室資料新鮮度條 — 完成 A 系列面板新鮮度可視化最後一棒（A1 ETF→A2 台股熱錢→A3 美股流動性→A4 MJ 趨勢分數→**A5 危機回測**）。問題：危機回測讀**市場(SPX/TWII)＋基金 NAV 歷史時序**，user 反覆關切的「看到舊資料」在此具體形態＝**序列截止日太舊**（市場 API 失敗沿用舊收盤 / NAV 來源只回近期短序列），回測結果看似正常但底層時序已過期無從驗證。改動單檔 `ui/tab_crisis_backtest.py`（+~52 行）：(1) 新增純顯示 helper `_render_crisis_freshness_bar(mkt_series, market_label, fund_nav_latest, fund_display_name, st)` — 市場＋基金 NAV 各自「資料截止日」＋ traffic-light（市場日頻 🟢≤4 含週末/🟡≤10/🔴>10；NAV 發布 T+1~2＋假日放寬 🟢≤7/🟡≤21/🔴>21）＋ TW 載入時戳（`pd.Timestamp.now(tz="Asia/Taipei")`）＋ 最舊序列 >30 天追加 ⚠️ 提示按「開始回測」清快取重抓；內層 `_light(latest, green, yellow)` 用 `index.max().normalize()` 與當日 tz-naive 午夜算距今天數。(2) `fund_nav` 序列原本**沒進 Phase1 cache**（L339 只存 `fund_nav_available` boolean）→ 補 `fund_nav_latest`（`fund_nav.index.max()` 最新日期）。(3) render 段 L361 `st.divider()` 後、事件總覽 header 前掛上新鮮度條，讀 cache 用 `.get` 容舊 session cache 無此鍵。設計差異 vs A1~A4：A1 render-time fetched_at / A2 單一 date / A3 6 指標取最舊 / A4 MJ 快照季別落後；**A5 雙序列異源**（市場 vs NAV 更新頻率與 lag 不同）→ 各自獨立閾值，全程 try/except 純顯示絕不擋回測主流程。AST ✓ / py_compile ✓ / ruff **All checks passed**（零 errors）/ `_light` traffic-light smoke 7/7 / pytest `test_app_smoke` **96 passed 零回歸**。**[邏輯]** `index.max()` 取序列最新交易日，距今天數決定燈色，準確不受快取影響。**[邊界]** `mkt_series` 空→直接 return 不顯示；NAV 未選→⬜「未選基金」；舊 session cache 缺 `fund_nav_latest`→`.get` 回 None；計算全程 try/except 容錯。**[效能]** 純 markdown ~ms 級、零新增 fetch / cache。**[Debug]** 週末/連假市場最新交易日自然落黃區（≤10 天）不誤報紅；NAV 閾值放寬避開假日誤報。user 上線驗證：危機回測室 → 設參數按「開始回測」→ 事件總覽上方應出現「📅 資料截止日」條（市場 + 基金 NAV 各自燈號 + 距今天數 + TW 時戳）。下一步候選：B1 Stock K 線 fallback / B2 Fund FRED 個別指標 fallback / C1-C2 強制重抓粒度 / D1-D2 上游時間戳。

- **前一版**：feat(checkup) PR #263 @ dc94c62 v19.54：組合健檢 4 大功能（吃本金 / 月配息 / 配息率 / TER）— 完成 user 要求「修復組合健檢」三 PR cycle 第 3 棒。改動 `ui/helpers/fund_checkup.py` +188 行（單檔新檔案編輯）：新純函式 `_compute_fund_health_kpis(fund) → dict`（無 st 依賴便於單測，取 `mj.moneydj_div_yield` wb05 官方優先 / fallback `metrics.annual_div_rate`；月配息 = `invest_twd × adr / 100 / 12`；`div_safety_check` 從 `services.portfolio_service.dividend_safety` 引入計算吃本金燈號；TER 解 `mj.mgmt_fee` + `_TER_AVG_MAP` 對照從 tab2_single_fund:L1004-1009 移植 11 個 category 估值）+ 新 render `_render_fund_health_card(fund, kpis)` 仿 tab2 L866-883（吃本金卡綠/黃/紅 emoji × Coverage × 1Y 含息 × 月配息 TWD）+ L1024-1036（TER 子卡含同類均值對照）。wire 進 `render_fund_checkup` PK 表後 `st.divider()` + 「💊 逐檔財務健診」標題 + 逐檔 try/except 包覆避免單檔渲染崩潰擴散。AST ✓ / py_compile ✓ / ruff **All checks passed**（零 errors）/ pytest test_app_smoke 96 passed 零回歸 / 純函式 smoke 三 case 驗證（累積型→全 None；100 萬×4.95%→月配 4125 TWD 精準對齊 user 投資試算面板螢幕；TER 2.3% vs 科技均 1.6%→diff +0.7%）。**[邏輯]** pure fn 無 st 依賴；adr 優先 wb05 官方；月配息公式對齊 single-fund 試算；ter 對照表 substring 比對防 category 文字格式飄動。**[邊界]** `_adr<=0` / 缺 `invest_twd` / 缺 `mgmt_fee` 三條 fallback 路徑；try/except 包單檔卡渲染。**[效能]** 純 in-memory dict 操作零新增 fetch / cache；逐檔卡 ~ms 級。**[Debug]** 失敗單檔顯短 caption 不擋其他檔。下一步候選：A4 MJ 體檢 / A5 危機回測 / B1-B2 fallback 警示 / C1-C2 強制重抓粒度 / D1-D2 上游時間戳。

- **前一版**：feat(macro) PR #262 @ d22fe48 v19.53：A3 美股流動性新鮮度條 — `ui/tab1_macro.py:2126` 「⑥ 💵 美股流動性 × 熱錢監測」expander 6 chips（M2/WALCL/RRP/HY-OAS/HYG-LQD/AAII）+ fail-trace 之後、`except` 之前插入新鮮度條：📅 最舊指標截止日 + traffic-light（綠 ≤2 / 黃 ≤7 / 紅 >7 天，取 6 指標 date 最小值 = 最弱環節可見）+ 🕐 本次載入時戳 TW timezone + 📡 來源 FRED / Yahoo / AAII + 🔄 強制重抓鈕 `st.cache_data.clear()` + `st.rerun()`。設計差異 vs A1（render-time fetched_at）/A2（單一 date 距今天數）：A3 多指標異源（FRED 平日 + AAII 週度），顯示「最舊」確保最弱環節可見；週末/連假最舊 date 自然落黃區不誤報紅。AST ✓ / py_compile ✓ / ruff zero new errors（pre-existing 12 不在 patch line）/ pytest test_app_smoke 96 passed 零回歸。

- **前一版**：fix(tab3) PR #261 @ 7d79acb v19.52：P0 Hotfix `_sheet_id` UnboundLocalError — user 反映組合 Tab Streamlit Cloud 崩潰 traceback：`File "ui/tab3_portfolio.py", line 1133, in render_portfolio_tab if _oauth_configured and _sheet_id and \`。根因：`_sheet_id` 僅在 `if _logged_in:` 分支（L640）內賦值，但 L1133 在 `if _ungrouped:` 分支內（與 `if _logged_in:` 互不從屬），未登入時讀未綁變數 → 整 Tab 崩潰。修法：L538（`_logged_in = ...` 那行前）補一行函式級初值 `_sheet_id = ""`，未登入路徑短路為 falsy，登入路徑 L640 照常覆寫，零行為改動，1 行修復。AST ✓ / py_compile ✓ / ruff zero new errors at L538-541（pre-existing 23 errors 不在 patch line）/ pytest test_app_smoke 96 passed。

- **前一版**：feat(hotmoney) PR #260 @ d41bde8 v19.51：台股熱錢監測資料新鮮度條（尚未完成候選清單 A2）。延續 v19.50 新鮮度可視化，補上熱錢面板（外資快取 30min `fetch_foreign_flow_series` ttl=1800 / USDTWD 快取 10min `fetch_usdtwd_series` ttl=600）。**設計差異 vs Stock A1**：A1 在 render 捕捉 `fetched_at`，cache hit 不準（永遠顯示「剛抓」）；本面板 traffic-light 改掛「資料截止日距今天數」——日頻市場資料的「舊」= 最新交易日太久遠，這信號準確不受快取影響。改動 `hot_money.py` 純 UI 新增（零 logic 變動）：「📍 最新判讀」box 後插入「📊 資料新鮮度條」— 📅 資料截止日（`_hm_days_old = (今天 - latest['date']).days`，綠≤1天/黃≤4天/紅>4天）+ 🕐 本次載入時間 TW（`pd.Timestamp.now(tz="Asia/Taipei")`）+ 📡 來源快取說明 + 🔄 強制重抓鈕（`st.cache_data.clear()` + `st.rerun()`，slider 靠 key 保留）。AST ✓ / py_compile ✓ / ruff 僅 1 pre-existing F541@:135 baseline 本次零新增 / pytest test_hot_money 17 + test_app_smoke 96 passed 零回歸。**[邏輯]** `latest['date']` 是 signal 最後交易日準確不受快取影響；顏色由距今天數決定。**[邊界]** `_hm_days_old<=0` 顯「今日」；TW 時區用 `pd.Timestamp.now(tz="Asia/Taipei")`；`.clear()` 包 try/except。**[效能]** banner 純 HTML markdown ~ms 級。**[Debug]** 週末/連假最新交易日自然落黃區（≤4 天）不誤報紅。下一步候選：A3 流動性引擎 / A4 MJ 體檢 / A5 危機回測。

- **前一版**：v19.50（PR #259 @ 7e8bb86）：總經資料新鮮度可視化（強制重抓鈕 + 新鮮度條 + 過期警示）— User 反映「之前有看過資料是舊的」轉軸：「可以存放（不砍快取保速度）但要保證面板資料是新的」。Explore 確認 5 種「看到舊資料」根因：① FRED API 失敗 fallback 舊值無提示；② `@st.cache_data` 內回舊；③ FRED 月頻指標本身就有 lag；④ NAS proxy 失敗沿用 session 殘留；⑤ `/tmp/*.pkl` + `data_cache/` 跨 session 殘留。改動 2 處：(1) `tab1_macro.py:858` 載入按鈕拆雙鈕 — 左「📡 載入 / 🔄 更新」(吃既有 cache) + 右「🆕 強制重抓最新（清快取）」(`st.cache_data.clear()` + 清 6 個 session_state key 包括 `_radar_v1921_top` / `_tp_v1948_top` / `indicators` / `phase_info` / `news_items` / `systemic_risk_data` + macro_done=False + 走同一 spinner block)；(2) `tab1_macro.py:984` macro_done 區後插入「📊 資料新鮮度條」— 顯示總抓取時間 (`macro_last_update`) + age (< 1h 綠 / 1-4h 黃 / >4h 紅) + 5 個關鍵 FRED 月頻指標截止日（PMI / 10Y-2Y / HY / CPI / UNRATE）+ 雷達+拐點 cache 狀態；age > 4h 自動 `st.warning` 提示按強制重抓。AST ✓ / py_compile ✓ / ruff 12 baseline 持平 / pytest test_app_smoke 96 passed 零回歸。**[邏輯]** age 用 `_now_tw()` 與 `macro_last_update` 計算；FRED 截止日從 ind[KEY].date 取月頻字串；雷達/拐點 cache 狀態從 session_state 直接判 truthy；強制重抓清快取 + 重置 macro_done 後 `_do_load=True` 走同一 spinner block。**[邊界]** macro_last_update=None 時 banner 不顯示；ind 為空時 src_dates 空 list 顯「—」；雷達 cache_data 是 (None, None) 時顯「⬜ 未載入」；st.cache_data.clear() 包 try/except 容錯。**[效能]** banner 純 HTML markdown ~ms 級；強制重抓清整個 app cache_data → 其他 Tab 下次進去要重抓（user 主動點按鈕的場景，副作用可接受）。**[Debug]** age 顏色 traffic light 一目了然；雷達/拐點 cache 狀態直接顯示「🟢 已載入 / ⬜ 未載入」便於 user 確認是否要按強制重抓。下一步候選：台股熱錢監測 / 流動性引擎 / 危機回測 4 個面板若 user 反映也有舊資料疑慮，比照同套機制補上。

- **前一版**：v19.49_MacroFreshness（PR #258 @ 62ad804）：4-way spinner 合併 + DGS pool 擴 5 + yf pool 3 + navigator 撈 cache — 總經 Tab 再省 5-8s + 視覺順序穩定。User 第三輪反饋「面板仍慢 + 出現順序奇怪」。Explore 確認 3 處剩餘瓶頸與順序熱點：(1) `tab1_macro.py:865-933` 兩個 spinner 序列（`fetch_all_indicators` → `fetch_market_news` + `detect_systemic_risk`）；(2) `tab1_macro.py:287-356` `_render_macro_navigator` 4 卡內部 cache miss 時又重抓 `detect_risk_radar` + `detect_turning_points` 與下方 ④② 區塊重複；(3) `services/macro_service.py` `fetch_all_indicators` 內 HY/M2/RSP-SPY 仍序列 fetch。改動 4 處：(a) 載入按鈕 — 2 spinner 合併成 1 spinner + `ThreadPoolExecutor(max_workers=4)` 並行抓 indicators / news / radar / turning_points 四大 IO；radar+tp 結果寫入 `session_state['_radar_v1921_top']` + `['_tp_v1948_top']` 供下游共享；`detect_systemic_risk(_news)` 在 news result 後計算（<100ms 無需 spinner）；(b) `_render_macro_navigator` radar/turning_points 區塊改成只撈 session_state，cache miss 顯示「等待按鈕完成」不重抓；(c) 下方 ② 拐點區塊優先撈 session_state cache，cache miss 才呼叫 `detect_turning_points`；(d) `macro_service.py` 內 DGS pool 從 3 worker 擴成 5（加入 HY `BAMLH0A0HYM2` + M2 `M2SL`），原序列 5 條 FRED → max(t)；新增 SPY/RSP/DXY 3-worker yfinance 並行池，原 3× yfinance 序列 → max(t)。AST ✓ / py_compile ✓ / ruff 127=127 持平 baseline / pytest 44 passed + 1 pre-existing `test_trend_arrow_recent_rebound` baseline 持平。**[邏輯]** 4 future submit 同時開跑，detect_systemic_risk 依賴 _news result 但 CPU 計算極快不阻斷；session_state cache key `_radar_v1921_top` (radar) + `_tp_v1948_top` (turning_points) 統一供 navigator + 下方面板共享；FRED key 不足時 radar/tp future = None，跳過寫入 cache。**[邊界]** FRED key < 30 字元時 radar/tp future skip；ind 失敗回 {} → st.error；news 失敗 → silent ack + 空 list；radar/tp 失敗寫入 (None, None) 不污染下游；navigator cache miss 時顯示 placeholder action 文字。**[效能]** 預估 cold-start wallclock 再省 5-8s（spinner 4 IO max vs sum + 5+3 worker pool 擴張）；navigator 不再重複呼叫 detect_*，下方面板 cache hit instant。**[Debug]** session_state cache 統一，navigator 與下方面板永遠一致。下一步：user 上線確認總經 Tab 載入體感 < 15s + navigator 4 卡與下方面板同時填入無順序錯亂。

- **前一版**：perf(macro) PR #257 @ 151c8eb v19.48：雷達 10 燈 + 拐點 5 燈並行化 — 總經 Tab 省 6-10s。User 反饋 v19.47 後總經 Tab 整頁仍慢，明確拒絕用 `@st.cache_data` 暫存方案。Explore 二次確認兩處序列瓶頸：① `services/risk_radar.py:498-509` `detect_risk_radar` 10 個 `_signal_*` dict 直接賦值全序列（估 4-8s）② `services/macro_service.py:1380-1538` `detect_turning_points` 5 拐點各 try/except inline `fetch_fred` + 計算全序列（估 2-4s）。改動：(1) risk_radar.py — `_jobs` dict 包 10 個 _signal_*，`ThreadPoolExecutor(max_workers=10)` 並行 submit + 15s timeout per 燈，單燈例外回 `_empty(...)` 不阻斷其他 9 燈；(2) macro_service.py — 5 拐點 inline try 抽成 5 個 inner func `_calc_pmi_diff` / `_calc_yield_curve` / `_calc_hy_spread` / `_calc_sahm` / `_calc_lei`，各回 `(key, payload_dict)`，`ThreadPoolExecutor(max_workers=5)` 並行 + 25s timeout per 拐點，主迴圈 `out[key].update(payload)` merge 結果，回傳結構/欄位/行為完全不變。效益：雷達 wallclock 4-8s → max 單燈 ~1-2s（省 ~5s）；拐點 2-4s → max 單拐點 ~1-2s（省 ~2-3s）；總經 Tab 整頁省 6-10s。AST ✓ / py_compile ✓ / ruff risk_radar All checks passed（macro_service 116 個 pre-existing baseline 持平）/ pytest 109 passed (test_risk_radar + test_us_liquidity_engine + test_macro_service_inflection) 零回歸。**[邏輯]** 5 inner func closure 抓 fred_api_key；payload 空 dict 表示資料不足→保留 default _empty 不污染；**[邊界]** 並行 framework 異常 print log 但不阻斷，至少回 default payload；**[效能]** wallclock = max 單燈/單拐點 而非 sum；**[Debug]** 109 既有測試全綠保證行為等價。下一步：user 上線確認總經 Tab 載入體感 < 20s；若仍慢可進一步並行化 `fetch_liquidity_factors`（已 button on-demand）或 `_render_macro_navigator` 4 卡內部呼叫。

- **feat(macro) PR #256 @ 4b6c3de v19.47**：美股流動性 × 熱錢監測 + 台股熱錢降級 archive。User 反饋兩點：① Fund 以美股美元為主，⑥ 台股熱錢監測放錯位置（USD 計價境外美股基金台股本土訊號影響有限）② 詢問「美股熱錢是不是 FED 升降息？」澄清：美股熱錢 ≠ FED 升降息，FED 升降息是政策利率（上游因），美股熱錢是資金流向結果（下游果）= 流動性 + 信用 + 情緒三軸。改動：(1) 新增 `services/us_liquidity_engine.py` 220 行 + 24 case tests：6 指標 ThreadPoolExecutor 並行 — 流動性 (M2 YoY/WALCL/RRP) × 信用 (HY OAS BAMLH0A0HYM2/HYG-LQD 比) × 情緒 (AAII bull-bear scrape)；每 fetcher 獨立 try/except 失敗回 `{'_err': '...'}`；`fetch_us_liquidity_snapshot(api_key)` 一次回 6 指標 dict。(2) `ui/tab1_macro.py:1982+` 新增 ⑥ 美股流動性 × 熱錢監測 expander（6-chip 2×3 grid + 失敗 fetcher 詳情 expander 仿 Stock v18.194 fail trace）+ 既有台股熱錢從 ⑥ 編號降級為「📦 ARCHIVED — 台股熱錢監測（境外美股基金可略過）」+ caption 說明降級原因（hot_money 模組保留磁碟）；AI 摘要 caption 同步 ⑥ 台股熱錢 → ⑥ 美股流動性熱錢。AST ✓ / py_compile ✓ / ruff 新檔 All checks passed（tab1_macro 12 個 pre-existing baseline 不變動）/ pytest 24 new + 102 regression (macro_service_inflection + macro_explain + macro_score_calibration + eval_macro_consensus) 全綠。**[邏輯]** 6 指標三角獨立計算，色彩分級依各指標歷史 percentile 經驗閾值；**[邊界]** AAII regex 對頁面格式變動敏感→失敗回 `_err` 不阻斷其他 5 指標、FRED key 缺則所有 FRED 指標 silent fail；**[效能]** ThreadPoolExecutor max_workers=6 每 task 20s timeout 總 wallclock ≈ max ~3-5s；**[Debug]** 失敗詳情 expander 列每個 `_err` 讓 user 截圖直接定位 FRED key 缺/Yahoo timeout/AAII 頁面改版。下一步：user 上線確認 6 chip 渲染正常 + AAII scrape 命中率（不行 → 候選備援源 investing.com / MarketWatch）。

- **perf(macro) PR #255 @ 36b68d3 v19.46**：`fetch_all_indicators` 內 DGS 3 條 + forex 3 對並行化（省 ~12s）。問題：user 反饋總經面板載入慢；Explore 確認 `services/macro_service.py` 內 26+ FRED ID + forex 全是序列抓取無並行。改動：加 `from concurrent.futures import ThreadPoolExecutor as _TPE_macro`；DGS10/DGS2/DGS3MO 三條 FRED 用 `ThreadPoolExecutor(max_workers=3)` submit→result（原 3× ~3s → 並行 max ~3s）；3 個 forex pair (EURUSD/JPY/CNH) dict-comprehension submit + 預抓 `_fx_cache` dict 餵下游 for-loop 業務邏輯不動（同省 ~6s）。函數簽名 / 回傳結構 / 呼叫端介面均不變。pytest 78 passed in 14.16s (test_macro_service_inflection + test_macro_explain + test_macro_score_calibration + tests/test_eval_macro_consensus)。預估 `fetch_all_indicators` 總時間 ~10-20s → ~5-10s（省 ~50%）。跳過項目（Explore 二次確認後撤回）：① `fetch_all_indicators` 加 `@st.cache_data` — 已是 button 觸發 + session_state 存結果，rerun 不會重打；② 雷達 ↔ 拐點 dedup — `tab1_macro.py:288/460` 已有 `_radar_v1921_top` session_state 快取已 dedup。
- **feat(macro) PR #254 @ 0a0cbc4 v19.45**：總經導航卡 — 上方 4 欄 verdict 摘要（仿台股「震盪整理｜謹慎觀望」UX）。新增 `_render_macro_navigator(ind, phase, fred_key)` ~145 行，渲染 4-col 卡：🌍 總經 / ⚡ 短線雷達 / 🎯 拐點偵測 / 🕐 美林時鐘。資料源 zero new IO：總經=`phase_info`、短線=`summarize_radar()` via `_radar_v1921_top` cache、拐點=`detect_turning_points()` 5 訊號計票、MK=`classify_phase(ind)` 四象限。4 個 try/except 獨立 graceful；FRED key 不足 → 短線+拐點 ⬜「等待 FRED 載入」。零既有功能變動：① / ② / ④ / MK 4 個 full panel 完整保留供細節查看。tests test_risk_radar 79 passed；AST/py_compile/ruff 49=49 baseline 持平。下一步：user 上線後確認 4 卡顯示正常 → 可選後續加 sparkline / 點擊滾動到對應面板。
- **feat(macro) PR #253 @ 26b9e16 v19.44**：上方 4 面板 reorder — MK 時鐘上移至 ② 拐點後（純切片重排 6 個 indent-12 區塊，行數 2114 持平）。新順序：① 戰情室 → ④ 短線雷達 → ② 拐點偵測 → MK 時鐘 → ⑤ 流動性 → ⑥ 熱錢 → ③ 即時 → AI。對齊 user spec「總經 / 短期 / 拐點 / 美林時鐘」。pytest 419 passed。
- **feat(radar) PR #252 @ 68e143f v19.43**：短線雷達 fail trace 寫入 UI note → user 無需 log 即可看根因。問題：VIX 期限結構 + Put/Call 兩個 stress 早期訊號 4 層 fallback 全掛（Yahoo ^VIX3M/^VXV/^CPC/^CPCE deprecated + CBOE/stooq 失敗），Streamlit Cloud 免費版只給 build log，user 無從查根因 → 8 綠 2 ⬜ 被判平靜疑似誤判。改動：`_fetch_cboe_csv` / `_fetch_stooq_csv` 加 `trace: list[str] | None` 收集 HTTP code / 欄位不符 / No data；`_resolve_vix3m` / `_resolve_put_call` 回傳 3-tuple `(series, src, trace)`；`_signal_vix_term_struct` / `_signal_put_call_ratio` 全源失敗時把 trace join 進 note。零行為變化（fallback 順序與閾值完全保留）。tests：4 個既有 _resolve 測試 unpack 改 3-tuple + 新增 `TestFailTraceSurfacedInNote` 2 條。79 passed。下一步：user 截 ⬜ card → 看到 4 層真實失敗碼 → 對症補第 5 層備援源。
- **feat(macro) PR #251 @ fb4622d v19.42**：拆除單一 tab 包裝 → ① 戰情室（總經）成為頁面首屏。user v19.41 後仍反饋「上方仍沒有總經 短期 拐點面板」— 根因：Streamlit 單一 tab strip + roadmap caption 擋在 ① 戰情室上方。改動：`(tab_main,) = st.tabs([...])` 改用 `contextlib.nullcontext()`，所有 `with tab_main:` 區塊保持縮排不變（零功能變動）；roadmap caption 移除，由 ①②③④⑤⑥ 編號 heading 隱含順序。新視覺流：資料 banner → ① 戰情室（總經）→ ④ 短期 → ② 拐點 → ⑤⑥ → ③ → MK 時鐘。
- **feat(macro) PR #250 @ 016dd63 v19.41**：總經面板上移至 tab 首屏 — ③ 🔬 即時訊號決策矩陣 從戰情首頁 tab 外（L799）下移至 tab 內結尾（MK 時鐘前），讓 ① 戰情室（總經）成為 tab 首屏。新順序：① 總經 → ④ 短期 → ② 拐點 → ⑤ 流動性 → ⑥ 台股熱錢 → ③ 即時決策。caption 同步更新；指標教學手冊指引改指 📖 說明書 Tab §11 宏觀教學文獻。
- **feat(macro) PR #249 @ 8293d62 v19.40 PR2**：教學面板搬遷至 📖 說明書 Tab §11 宏觀教學文獻（tab1 −361 行 / 2465→2104；tab6 +381 行 / 578→959）— §A 🎯 為什麼是這位階 / §B 📊 23指標教學手冊 / §C 📈 歷史對照圖 / §D 👉 加扣分明細（_macro_23items stash）/ §E 📊 變數重要性（_macro_var_importance stash）。stash 契約：tab1 寫入 _macro_ind，tab6 讀取並重現面板；stash 空 → 友善提示。1826 passed / 5 skipped。roadmap PR1→PR2 全部完成。
- **feat(macro) PR #247 @ 13026cc v19.39 PR1C**：archive 8 inline 面板（−830 行 / 3296→2466）— 🌡️ 風險溫度計 4 cards / V4 複合 / 🎯 風險評分校準 / 🧮 景氣分數校準 / 🧭 景氣羅盤 / 📅 Tier A / 🔗 因果鏈 Sankey / 📊 細項燈號回測。Stash 介面契約完整保留（_macro_compass / _macro_sankey / _macro_subsector_bt / _cal_*）— AI 摘要 widget 繼續吃齊。Cleanup：移除 3 個 unused imports + sc/ph_c 變數；2 個 archive-dependent tests 改 @pytest.mark.skip。
- **feat(macro) PR #245 @ a991f4f v19.38 PR1B**：archive 10+ inline 面板（−477 行 / 3772→3295）— 7 維獨立合議 / 7 子領域燈號 / 四大類別 / Hero 卡 / 景氣時鐘 / 天氣 / 風險警示 / 美林時鐘 / T1 事件衝擊。
- **feat(macro) PR #243 @ 91da530 v19.38 PR1**：總經 Tab 矛盾修正 — archive 雙速合議 + 台股本地視角；6 KEEP 面板按熊市驗證 ROI 重新編號（① 戰情室 / ② 拐點 / ③ 即時決策 / ④ 短線雷達 / ⑤ 流動性 / ⑥ 台股熱錢）；AI 景氣判斷總結加 caption 明示涵蓋同源資料。
- **fix(fund-health) PR #241 @ f791ba2**：保單體系代碼用 Tab2 同款 `fetch_fund_from_moneydj_url` 取 series + dividends + currency + fund_name。
- 初始化基準：協議 v2.0 Auto-Ship 套用，歷史版本紀錄詳見 `git log`。

## 下一步

- **refactor(dead-code) 第四階段深層拔毒(2026-06-28 進行中,v19.209+)**:User 「深層稽核 → 同意全部」授權。3 個 Explore 平行掃描出 SSOT 7 類 / 架構越權 2 處 / Dead code 30 條 fn。一檔一刀策略執行 P0-3-#1~#N。
  * **F-PROV-1 cluster C 補洞**(v19.233):User「WONTFIX 兩項深挖」授權。原 audit 標籤「3 個 MISS scalar」實際是 **12 個** MISS,深挖分三類:**A. 真 scalar 5 處**(`Optional[float]` 結構性無 .attrs,改 dict 包裹爆破 caller blast radius)+ **B. Thin wrapper passthrough 3 處**(upstream 已 v19.188 phase 23 stamp,本層 re-stamp 反而干擾) + **C. Dict orchestrator 4 處可動**(漏網)。**動 4 處 Cluster C**(對齊 v19.105 phase 19 既有 `_provenance` 模式):(1) `repositories/fund/nav_metrics::_fetch_domestic_perf` dict 加 `_source` + `_fetched_at`(2) `repositories/macro/yf::fetch_yf_latest` 加 `_provenance.sources/fetched_at`(3) `services/liquidity_engine::fetch_liquidity_factors` 加 `_provenance.sources/fetched_at/aggregator`(4) `services/macro/us_indicators::fetch_tw_market_tpi` 加 `_provenance.sources`(3-factor 各標 TWSE / FinMind / CBC tier-aware) + `aggregator="fetch_tw_market_tpi:TPI_v15.3"`。**audit 從 12 MISS → 8 MISS**(剩 8 真結構性)。**test 修補**:`tests/test_liquidity_engine::test_fetch_liquidity_factors_aggregates` 改 `set(out)` → `{k for k in out if not k.startswith("_")}` 排除 _provenance schema-additive key。test_macro_core + test_liquidity_engine + test_provenance_smoke + test_app_smoke 169 passed / 0 failed
  * **A+B doc cleanup**(v19.232 後):
    - A:CLAUDE.md §3.1 `⚠️ 待議 pandera` → `✅ 已結案 v19.189`(F-SCHEMA-1 過時標籤更新)
    - B:12 檔 14 處 historical `services.fund_X.*` docstring/comment refs 改 `services.health.*`
  * **#9 D Fund Health subpackage 完整搬遷**(v19.232):User 質疑「最小可行版違反規則 / 檔案太大則分階段做」→ 從 facade 模式升級為**真正搬檔的 subpackage**(5 子模組 + facade re-export)。**搬遷對應**:fund_health.py → grade.py / fund_dividend_calculator.py → dividend_calc.py / fund_dividend_health.py → dividend.py / fund_replacement_verdict.py → replacement.py / fund_health_report.py → report.py。**git mv 保 history**(5 檔)+ subpackage 內部互相 import 4 處改 services.health.X(report 3 + replacement 2 + dividend_calc 1)+ 13 caller 27 處 import 改新路徑(`ui/tab2_single_fund` 4 / `ui/tab_fund_grp_health` 4 / `ui/helpers/fund/checkup` 1 / `ui/helpers/fund_grp_health/ai` 1 / `services/fund_service` 1 / `services/portfolio_service` 1 + 7 test 14 + tests/test_fund_health_report 等)。**不留 shim**(P2-7 shim 不穿透 sub-module 風險,且全 caller 已同步更新)。**facade __init__.py 升級**:re-export 從 sub-module 路徑(`from services.health.grade import compute_4d_health` 等)讓新 caller 可選 `from services.health import compute_4d_health` cleaner pattern。test_app_smoke + test_provenance_smoke + test_fund_health_report + test_fund_dividend_calculator + test_fund_replacement_verdict + test_fund_dividend_health + test_fund_service_advanced_metrics + test_mk_simple_formula + test_mk_ssot_unification 261 passed / 0 failed
  * **#9 D Fund Health subpackage facade**(v19.231,中繼版 → v19.232 升級為完整搬遷):User 重申「#7-#9」執行三項。深挖確認大改造涉 16 caller import 重寫(F-GRAY-1 同等 cosmetic ROI 反例)→ 改採**最小可行 facade 模式**:新增 `services/health/__init__.py` 僅 re-export 4 模組的核心 fn,**0 caller 變更**,新 caller 自選用 `from services.health import X` cleaner pattern。**User 後續反饋「最小可行版違反規則」**→ v19.232 升級為真正搬檔(見上條)
  * **#8 E URL 深挖第二輪**(v19.230):**12 個 single-source URL 經逐一 grep audit,P1-2 結論「11 個確實各 1 caller」正確,深挖補 2 處漏網**。(A)**GEMINI_URL @ services/ai_service.py:28 dead constant 拔毒**:0 production caller(實際 production fetcher 在 `infra/llm.py:111` 用 f-string inline 拼接),P0-3-#10 漏網。刪 1 行 const + 維修 module docstring。(B)**YF query2 Morningstar URL 真 dupe 收 SSOT**:`repositories/fund/sources.py:830-835`(`_src_yahoo_finance_nav`) ↔ `scripts/fetch_nav_cache.py:299-303`(`fetch_morningstar_via_yf`)同字串 template `https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2y&includePrePost=false`。加 `YF_MORNINGSTAR_CHART_URL` const 到 sources.py 模組 top(對齊 source-local SSOT 原則)+ scripts lazy import `from repositories.fund.sources import YF_MORNINGSTAR_CHART_URL`(對齊 P1-2 設計原則「scripts dupe 從 production 拿」)+ shared/api_endpoints.py docstring 更新含本輪深挖補刀紀錄。**深挖證據**:每個 URL grep 確認 caller list,proxy 測試 endpoint list(sidebar / tab5_data_guard)雖部分 URL 字串相同但語意是「不同 feature 各自選 endpoint」,不收 SSOT。test_app_smoke + test_provenance_smoke + test_fund_url_canonicalize + test_proxy_infra + test_schemas_phase_b2_fund_nav 165 passed / 0 failed
  * **C #7 sidebar 抽出**(v19.229):**`ui/sidebar.py` 從 app.py 抽出 sidebar 渲染**。`with st.sidebar:` block(L172-365,194 LOC)→ `render_sidebar(*, app_version, engine_version, fred_key, gemini_key, now_tw_fn)` fn(228 LOC,含 docstring + lazy import)。**app.py 472 → 289 LOC(−183, −39%)** 已**超越 ARCHITECTURE.md v11.0 願景 425 LOC**(beats by 136 LOC)。**OAuth 處理**:5 個 oauth_state vars(`_oauth_configured` / `_oauth_cfg` / `_gsa_secret` / `_sheet_id_secret` / `_get_oauth_client`)從 module-level 改 fn 內 lazy `from ui.helpers.io import oauth_state as _os` + `_os.refresh_oauth_state()` 拿 fresh snapshot(規避 P2-7 shim 不穿透 sub-module issue)。**設計原則**:5 kwargs 注入 app-level vars(無 import-cycle 風險);`_now_tw` 改名 `now_tw_fn` 強調 callable;OAuth 5 vars 內部 lazy 解析(caller 不需傳)。test_app_smoke + test_app_apptest + test_provenance_smoke 115 passed / 0 failed
  * **P1-2**(v19.223):**`shared/api_endpoints.py` SSOT 收口 5 caller**(7 處真 URL 重複消除)。新增 SSOT(36 LOC docstring + 1 LOC `FINMIND_BASE`)。3 FinMind callers(hot_money_repository:25 / macro_tw_local_repository:35 / tw_macro_repository:40,**同字串**)+ 2 scripts dupes(update_macro_history.py:60/61 `FRED_URL` + `YF_CHART_BASE`)全改 SSOT alias import。Scripts dupe 改從 production fetcher(`repositories.macro.fred.FRED_BASE` + `repositories.macro.yf.YF_CHART_BASE`)拿,不到 shared(L1 fetcher 自帶 source-local SSOT)。**設計原則**:本 SSOT 只收「真實重複 ≥ 2 處同字串」,12 個 single-source URL 保留各檔 source-local(如 FRED_BASE / YF_CHART_BASE / TWSE_MI_INDEX / GEMINI_URL / OAUTH / 等)讀 caller 即見 SSOT。test_app_smoke + test_macro_core + test_provenance_smoke + test_tw_macro 152 passed / 0 failed
  * **P1-1**(v19.222):**`shared/converters.py` SSOT 收口 11 caller**(Tier 4 SSOT 收口首發)。新增 SSOT(64 LOC):`safe_float(v, default=None)` / `safe_num(v)` / `fmt_pct(v, plus, decimals, ratio)`。8 個 `_safe_float` callers(`services/fund_dividend_calculator` / `fund_dividend_health` / `fund_health` / `fund_health_report` / `fund_replacement_verdict` / `macro/explain` 含 default=0.0 變體 / `macro/tw_local` / `ui/components/mk_dashboard`)+ 2 個 `_safe_num` callers(`ui/helpers/fund/checkup` / `fund_grp_health/_utils`)+ 1 個 `_fmt_pct`(`crisis_ai_advisor`)全部改 `from shared.converters import safe_X as _safe_X` alias 模式,**inner code 0 改動**。Python script 一次性 mass migrate。test_app_smoke + test_macro_core + test_provenance_smoke + test_fund_dividend_calculator + test_fund_health_report 200 passed / 0 failed。**`portfolio_service:612 _safe_num_ps`** 名字 _ps 後綴(非 audit 列),`tab2_single_fund.py:836 _fmt_pct` inline closure 行為不同(non-ratio),兩處留 backlog
  * **P1-3 + P1-4**(v19.220-221):**架構越權 N2+N3 修補**。
    - **P1-4**(v19.220):FRED_BASE dead chain 4 處清(L2 services 不應定義 production HTTP URL)。services/macro/_helpers.py:88 刪 def + 3 個 caller(services/macro_service / macro/__init__ / macro/us_indicators)全 dead import 移除。SSOT 在 L1 `repositories/macro/fred.py:28`。142 passed
    - **P1-3**(v19.221):CBOE fetcher 下沉 `repositories/external_market_repository.py`(對稱 stooq P1-3 v19.197 wrapper 模式)。`services/risk_radar.py:125-166 _fetch_cboe_csv`(42 LOC)改 7 LOC thin wrapper,`from infra.proxy import fetch_url` 從 L2 services 移除。新增 `fetch_cboe_csv` 到 external_market_repository.py。N2 架構越權 close。188 passed / 2 skipped
  * **P0-3-#10**(v19.219):**散批 11 fn 拔毒**(8 production 檔)+ **6 dead test + 4 orphan imports/comments 連動清**。dead fn:`shared/colors.py:emoji_to_hex`(5) / `services/reconcile.py:reconcile_macro_health`(56) / `services/precision_service.py:risk_score_gauge_html`(34) / `repositories/news_repository.py:filter_news_by_keywords`(18) / `repositories/ledger_repository.py:load_ledgers_for_policy`(11) / `services/fund_history.py` 3 fn(`delete_fund` 19 + `delete_funds_bulk` 29 + `history_size` 3) / `ui/components/macro_card_edu.py` 2 fn(`get_macro_edu` 3 + `macro_edu_count` 2) / `scripts/calibrate_macro_score.py:bootstrap_ci_diff`(29)。Python script 批次刪 fn,**修補 1 個 regression bug**:script boundary 邏輯誤刪 `_GOOGLE_NEWS_RSS` module-level const(由 fetch_stock_news 用)→ 補回。test_news_repository + test_ledger_store + test_calibrate_macro_score + test_fund_history + test_macro_health_zpct + test_app_smoke + test_provenance_smoke 175 passed / 0 failed。net **−240 LOC**(11 fn 約 −210 + 6 test 約 −50 + 4 orphan ~20,扣 補 _GOOGLE_NEWS_RSS 1 行)
  * **P0-3-#9**(v19.218):`shared/macro_buckets.py` **4 fn 拔毒**(261 → 206)+ `tests/test_macro_buckets.py` 7 dead test 連動清(140 → 85)。`specs_for_bucket` / `classify_danger` / `aggregate_level` / `fmt_value` production 0 caller。**module-level constants 保留 active**(被 7 個 production 檔 import:beginner_view / chart/danger / macro/_helpers / macro/validation / risk_radar / scripts/calibrate_macro_score)。test_macro_buckets + test_app_smoke 101 passed / 0 failed。net −110 LOC
  * **P0-3-#8**(v19.217):`services/calibration/macro_score.py` **4 fn 拔毒 + 連動清 _FRED_SERIES_MAP / _TRUTH_RULES / 10 個 FRED imports**(net −241 LOC,553 → 312)+ `tests/test_macro_score_calibration.py` 連動清 4 test(net −40 LOC,163 → 123)。dead fn:`phase_accuracy`(L225-249) / `overall_accuracy`(L252-265) / `grid_search_phase_thresholds`(L268-289) / `fetch_real_macro_factors_monthly`(L378-490)production 0 caller。**深掃連動**:`_FRED_SERIES_MAP` const(L325-)+ `_TRUTH_RULES` const(L212-217)+ `shared.fred_series` 10 個 FRED_* imports(L34-45)全 dead 一併清。test_macro_score_calibration + test_app_smoke 119 passed / 0 failed。net −281 LOC
  * **BUG-FIX-C3**(v19.216,db0413b):修 C3 留下的 `_compass_fetch_btn` 重複 key — `ui/components/macro_compass_top.py:89` 多餘 module-level `render_macro_compass()` 呼叫(component 應只 def 不執行),`app.py:411` 是唯一呼叫站。test_tab3_empty_portfolio_shows_welcome_card 從 fail → pass
  * **P0-3-#7**(v19.215):`services/portfolio_service.py` **2 fn 拔毒 + scipy 依賴清除**(net −119 LOC,1010 → 891)。`optimize_portfolio`(L365-435,70 LOC) + `calc_kelly`(L961-1010,50 LOC)production 0 caller。**連動清** scipy try-except import block(L32-37)+ module docstring 2 行提及。STRATEGY.md L314/L328 仍有業務戰略提及不動(屬戰略文件層)。test_app_smoke + test_provenance_smoke + portfolio 100 passed / 0 failed(test_tab3_empty_portfolio_shows_welcome_card pre-existing fail 為 C3 留下的 `_compass_fetch_btn` 重複 key,git stash verified non-P0-3-#7)
  * **P0-3-#6**(v19.214):`services/adjusted_nav.py` **整檔拔毒**(185 LOC)+ `tests/test_adjusted_nav.py` 連動刪除(178,test 孤兒)。3 step verify pass(`adjust_nav_for_dividends` / `is_nav_likely_dividend_adjusted` 2 fn production 0 caller)。AUDIT line 138 strikethrough。test_app_smoke + test_macro_core + test_provenance_smoke 142 passed / 0 failed。net −363 LOC
  * **P0-3-#5**(v19.213):`services/calibration/cluster.py` **整檔拔毒**(317 LOC)+ `services/cluster_calibration.py` P2-3 shim(8)+ `tests/test_cluster_calibration.py`(178,test 孤兒)+ `cache/cluster_calibration.json`(落地 cache)。3 step verify pass(5 fn 全 production 0 caller:compute_cluster_f1 / run_cluster_calibration / save_calibration / get_cached_calibration / f1_to_grade)。**獨立性驗證**:`tests/test_cluster_signals.py` 測 `macro_service.compute_cluster_signals`(完全不同模組),0 reference,保留。`services/calibration/__init__.py:6` strikethrough。test_app_smoke + test_macro_core + test_provenance_smoke + test_cluster_signals 155 passed / 0 failed。net −503 LOC + cache JSON
  * **P0-3-#4**(v19.212):`services/allocation_simulator.py` **整檔拔毒**(441 LOC)+ `tests/test_allocation_simulator.py`(277)+ `tests/test_allocation_simulator_presets.py`(148)連動刪除。**深度 verify 修正 Agent 3 誤判** — Agent 3 只列 3 fn dead,實際 6/6 fn 全 dead(`build_preset_matrix_df` / `get_preset_phase_script` / `validate_and_normalize` / `run_single_simulation` / `summarize_simulation` / `run_monte_carlo` 全 production 0 caller)。**EX-POLICY-1 例外退役** — `ui/tab_allocation_simulator.py` consumer 早在 P0-2 v18.x 刪除,例外對象失效,CLAUDE.md §8.2.A 標 strikethrough。AUDIT line 128 同步。test_app_smoke + test_macro_core + test_provenance_smoke 142 passed / 0 failed。net −866 LOC
  * **P0-3-#3**(v19.211):`services/event_calendar.py` **整檔拔毒**(161 LOC)+ `tests/test_event_calendar.py` 連動刪除(193 LOC,test 孤兒)。3 步 verify pass(`detect_event_calendar` / `summarize_calendar` 2 fn production 0 caller,app.py 0 reference,STATE 歷史紀錄 immutable 不動)。AUDIT doc line 135 strikethrough 標「v19.211 拔毒」。test_app_smoke + test_macro_core + test_provenance_smoke 142 passed / 0 failed。net −354 LOC
  * **P0-3-#2**(v19.210):`services/quadrant_simulator.py` **整檔拔毒**(286 LOC)+ `tests/test_quadrant_simulator.py` 連動刪除(213 LOC,test 是孤兒)。3 步 verify pass(production grep 0 caller / 4 fn 名 0 production refs / app.py 無 ARCHIVED marker)。BACKLOG + AUDIT doc 歷史提及改 strikethrough 標「已拔毒」。test_app_smoke + test_tw_macro + test_provenance_smoke 110 passed / 0 failed。net −499 LOC
  * **P0-3-#1**(v19.209):`repositories/tw_macro_repository.py::fetch_tw_market_snapshot` 整合 API 拔毒 — production 0 caller(深層 audit verify,只有 1 個 test 是孤兒)。C2 v19.208 為它加的 orchestrator-level provenance(source/fetched_at)同步拔除。連動刪 `tests/test_tw_macro.py::test_snapshot_returns_three_factors`。3 個 sub-fetcher(twse_breadth / finmind_foreign_investor / cbc_m1b_m2)保留獨立可用。test_tw_macro + test_app_smoke 106 passed / 0 failed

- **refactor(arch) 第三階段排毒(2026-06-28 完工,v19.202-208)**:User 「B+C → D1+D2+B3」分批授權,把第二階段 P2-1/P2-4/P2-5 revert backlog 用「直接搬位置 + `_*` 集中 + 改 test patch path」策略重做成功。
  * **A1**(v19.202 `61af3e0`):清空殼目錄 + 修 2 過時 SSOT-guard test(129 passed)
  * **B1**(v19.205 `b9eab84`):`repositories/macro_repository.py` 1078 LOC 拆 5 子檔(`fred / yf / china / alternate / math_utils`)+ 28 處 test patch path 規避 v19.199 shim 不穿透(485 passed,P2-5 backlog close)
  * **B2**(v19.206 `b35dcbd`):`repositories/policy_repository.py` 1372 LOC 拆 3 子檔(`_helpers / v1 / v2`),共用 `_*` 集中 `_helpers.py` 規避 v19.199 `from X import *` 不取 `_*` 死結(239 passed,P2-4 backlog close)
  * **C3**(v19.207 `5b32618`):app.py 542 → 471 LOC(−13%),抽 `_render_compass_card + render_macro_compass` 78 LOC 至 `ui/components/macro_compass_top.py`(89 LOC)。Sidebar 抽取 abort(over-engineering)
  * **C2**(v19.208 `b7eb171`):F-PROV-1 補洞 9 fetcher(5 實質 + 4 docstring 標明),audit OK 23 → 31(+35%),PARTIAL 全清。news ×3 / fund_orchestrator / tw_market_snapshot 實質補,`_now_iso_utc` helper 新增
  * **C1 / B3 標誤判**:6 檔 Fund Health + fund_checkup 均職責不同,v19.150/181 SSOT 抽取後已 aligned(同 P2-8 SCORE_RULES 案例)
  * **D1+D2**:audit / BACKLOG / STATE 三檔同步完工
  * 體積:god module 0(已拆完並維持)/ P2 backlog 3 → 0 / app.py −13% / `repositories/` 子套件 1 → 3(+200%)

**perf(radar) PR v19.65 P0 完成**：VIX3M + Put/Call 第 6/7 層備援源新增。

- **VIX3M 第 6 層**：`_resolve_vix3m(fred_api_key)` → FRED `VXVCLS`（CBOE S&P 500 3-Month Volatility 官方序列，與 HY OAS / DGS10 同走 fetch_fred 路徑，NAS Squid proxy 已白名單）。`_signal_vix_term_struct(fred_api_key)` + `detect_risk_radar` lambda 傳遞 key；fred_api_key=None 時跳過（向後相容零 caller 異動）。
- **Put/Call 第 7 層**：新 `_fetch_cboe_json(symbol)` helper → `https://cdn.cboe.com/api/global/delayed_quotes/charts/historical/{enc}.json`（JSON API，與既有 CSV 端點同源但不同路徑，部分 NAS proxy 的 .csv 與 .json 封鎖策略不同）。`_resolve_put_call` 在所有 Yahoo + CBOE CSV + stooq 全失敗後嘗試 JSON API。
- +12 tests（`TestFredVxvclsFallback` 4 case + `TestCboeJsonFallback` 5 case + CBOE JSON 全鏈 1 case）；pytest tests/test_risk_radar.py **87 passed / 0 failed**（zero regression）。

下一步候選：P1 fetch_fred SSOT 收斂（fetch_all_indicators 集中入口）/ 等 user redeploy 驗證 VIX 期限結構卡是否從 ⬜ 轉亮。
