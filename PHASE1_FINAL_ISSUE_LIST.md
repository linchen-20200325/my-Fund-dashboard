# 基金戰情室 — 第一階段最終問題清單

> **狀態：一行程式碼都還沒改。** 本清單為修復前的最終確認版。
> 基準：本機 clone `D:\01.Github\20260813\基金`（= GitHub main HEAD）+ 部署站台六輪實機驗證
> 日期：2026-08-14

## 驗證狀態圖例

| 標記 | 意義 |
|---|---|
| 🔬 | **實機證實** —— 在部署站台上親眼看到 |
| 📄 | **程式碼證實** —— 本機逐行 Read/Grep 確認，附行號 |
| 🔬📄 | 兩者皆有 |
| ⚠️ | **待驗收** —— 程式碼證據成立，實機未證（列於 §5） |

---

# §1. P0-CRITICAL — 讓 App 不能用，或直接給錯數字

## 1-A 🔴🔴🔴 連線中斷（最高優先，必須第一個修）

| # | 問題 | 位置 | 狀態 | 工作量 |
|---|---|---|---|---|
| **N1** | **25 檔真實持倉下，任一觸發 rerun 的互動 → 17 秒後 `WebSocket onclose` → 畫面永久凍結** | 見下方四個成因 | 🔬 **兩次獨立重現** | — |
| N1-a | AI snapshot 在使用者按 AI 按鈕**之前**就全算完（`fetch_usdtwd_frame` 網路 + 25× `compute_max_drawdown` + 相關性矩陣 + 每幣別一次 `get_latest_fx`） | `ui/tab3_portfolio.py:2694 → 2745-2839` | 📄 | 1-2d |
| N1-b | 持倉健診 `ThreadPoolExecutor(4)` × 25 檔 `process_one_fund`，唯一守門是 `if _loaded_pf:` | `ui/tab3_portfolio.py:2559-2626` | 📄 | 含上 |
| N1-c | 60 月 expanding window 回測，**無 cache、藏在收合 expander 內** | `ui/tab5_data_guard.py:793` + `services/macro/causal_sankey.py:317` | 📄 | 0.5d |
| N1-d | 兩次 Google Sheets 網路讀取，**無 cache、無 expander、無條件執行** | `ui/tab5_data_guard.py:1371, 1407` | 📄 | 0.5d |
| N1-e | `_update_data_registry` 對 25 檔全量 `sort_index()`，並把**排序後完整 Series** 塞 session_state | `ui/helpers/io/data_registry.py:260, 291, 325` | 📄 | 0.5d |

> `app.py:205` 註解自承「**st.tabs 單次 run 渲染全部分頁**」→ 以上全部在每次互動都跑，不管使用者停在哪一頁。
> **證據**：`09:46:00 INITIAL -> RUNNING` → `09:46:17 WebSocket onclose`。另一次 1 檔基金切「參考/診斷」→ `WebSocket onerror`。

## 1-B 🔴🔴 幣別誤判 → 金額差 32 倍

| # | 問題 | 位置 | 狀態 | 工作量 |
|---|---|---|---|---|
| **J1** | **台幣基金被判為 USD**：ACDD01「安聯台灣大壩基金-A累積型**(台幣)**」與 ACDD19 顯示計價幣別 USD，單位數 95.86（正確 907.8）→ **低估 32.1 倍** | 根因 ↓ | 🔬📄 | — |
| J1-a | **根因**：Sheet `currency` 欄空白 → `str(r.get("currency","") or "USD")` **無中生有**。同函式相鄰兩行 `fund_name`/`tier` 都是 `or ""`，**獨獨這行編值** | `ui/helpers/v2_editor.py:85` | 📄 | **XS（單行）** |
| J1-b | FX 曝險摘要**獨立第二條汙染路徑**，雙重 fallback → 產出錯誤警語「組合 100% 為 USD 計價」 | `ui/tab3_portfolio.py:266` | 🔬📄 | XS |
| J1-c | 全站 `or "USD"` 共 **17 處**（v2_editor ×2、tab3_portfolio ×1、d_mode ×3、cloud_io ×2、**t7_ledger ×11**、ai_service ×1、ledger_service ×2） | 多檔 | 📄 | M |
| J1-d | `normalize_ccy` 的 `default` 預設值就是 `"USD"` | `services/currency.py:40` | 📄 | S |

> ✅ **下游守門是對的，不要改**：`services/fund_row.py:81,90-94` 與 `ui/helpers/fund/checkup.py:328,365` 都用 `default=""` 且抓不到就報錯／顯示 `—`。問題在**上游先把值填好了**，讓下游的「有沒有值」檢查失效。
> ⚠️ **修法取決於 Sheet 實際內容**（見 §6 待你確認）。

## 1-C 🔴 假成功 / 假綠燈（12 條）

| # | 問題 | 位置 | 狀態 | 工作量 |
|---|---|---|---|---|
| A1 | 批次部分失敗標 `✅ 成功`（①失敗留白 13 欄／②7 欄／③22 欄+7 欄降級）。**健診端同情境有完整揭露** → 落差證實 | `ui/helpers/fund_grp_health/unified.py:403-422, 436-437` | 🔬📄 | ~30 行 |
| A2 | 帳本雲端寫入失敗被吞，`st.success` 照常顯示（C 分頁 `:2468` 有正確寫法可照抄） | `ui/tab3_t7_ledger.py:451-454` | 📄 | 1h |
| A3 | `except: pass` 讓 **HWM σ 卡**與 **4D 健康總覽卡**整張靜默消失 | `ui/tab2_single_fund.py:1066-1067, 1138-1139` | 📄 | 0.5h |
| A4 | 資料源總覽 5 列共用 `_fund_n`（與該來源是否真被呼叫無關）；第 10 列硬寫 `False` | `ui/tab5_data_guard.py:436-461` | 📄 ⚠️ | 1-2d |
| A5 | **雷達 10 燈完全不走 `_freshness`**，value 非 None 就 🟢，`latest_date` 偽造成字串「今日」 | `ui/helpers/io/data_registry.py:451-453` | 📄 | M |
| A6 | 4 條路徑缺 provenance → 回 `"本月"/"年度"` + 硬編 🟢 → **永遠不可能亮紅燈** | `data_registry.py:553, 586, 603, 656` | 📄 | M |
| A7 | `clean` 分支把 `⬜ 未知日期`（解析失敗）算進「狀態全數正常」 | `ui/tab5_data_guard.py:1495` | 📄 | S |
| A8 | NAV/FX 抓不到 → 市值退回成本 → 損益恆 0、報酬恆 0.00%（**而帳本表同情境歸 0 → −100%，兩套相反語意**） | `ui/tab3_t7_ledger.py:936-947` vs `:2634` | 📄 | 0.5d |
| A9 | B 分頁 % 模式檔無 NAV/FX 前置過濾 → 不落帳但**無條件顯示「應買 TWD」**，且無警告 | `ui/tab3_t7_ledger.py:1530-1570` | 📄 ⚠️ | 0.5d |
| A10 | 清快取 `except: pass` 後仍設 `_do_load=True` → 使用者拿舊資料卻被告知成功。**同型兩處** | `ui/tab1_macro.py:947-948`、`ui/tab1_macro_longterm.py:249-250` | 📄 | 1h |
| A11 | `get_latest_fx` 失敗 → 所有非台幣基金落成「資料不足」，**不說是匯率抓不到** | `ui/tab_manage.py:658-659` | 📄 | S |
| A12 | `except: continue` — 壞掉的 checkpoint 從救援清單無聲消失 | `repositories/batch_checkpoint.py:121-122` | 📄 | XS |

## 1-D 🔴 假綠測試（正在幫 bug 背書）

| # | 問題 | 位置 | 狀態 | 工作量 |
|---|---|---|---|---|
| B1 | fixture 寫死 `"release 期已到 +2 天"` —— **生產端從不產生此字串**。這是 C1 能存活至今的直接原因 | `tests/test_data_guard_anomaly_state.py:47, 85` | 📄 | S |
| B2 | 只比對裸 `pass`，**加一句註解就過關** → A3 那兩處是「被測試蓋章的違憲」 | `tests/test_review_fixes_v19_346.py:142-151` | 📄 | S |

> **修 A3 / C1 時必須同批改這兩個 fixture**，否則改對了反而測試變紅。

## 1-E 🔴 死控制項（使用者以為在控制，實際沒有）

| # | 問題 | 位置 | 狀態 | 工作量 |
|---|---|---|---|---|
| C1 | `anomaly_view_state` 用 `"release 期已到" not in label` 判定，但實際 label 是 `"release lag N 天（預期 …）"` → **條件恆真**，每月 FRED 發布後誤報一批正常 🟡；而 `:1505` 明文承諾「已自動排除」 | `ui/tab5_data_guard.py:127` | 📄（窮舉 14 種 label 全比對） | **<1h** |
| C2 | **slider「吃本金閾值 %」對畫面零影響**。它產出的 `div_health_light_🧮` production **0 consumer**；help 承諾「> 此值 → 標 🔴」 | `ui/tab_fund_grp_health.py:185-190` | 📄 ⚠️ | 1h |
| C3 | **「投入方式」selectbox 死碼**：form 外算好的 `_a_new_mode_key` 在 form 內被無條件洗成 `"twd"` → 「🎯 目標單位數」兩處分支恆為 False | `ui/tab3_t7_ledger.py:1091` | 📄 ⚠️ | **5 分鐘** |
| C4 | **換標建議 4 條規則只剩 1 條可用**：(a)(c) 因未傳 `holding_years` 恆 False；(b) 因 `adr = eat_result.get("annual_div_rate_pct")` **key 不存在** → 無 Sharpe 的基金 grade 恆 `—` | `services/health/replacement.py:126` + 4 個 caller | 📄 | 2h |

## 1-F 🔴 硬編碼 fallback → 產生「看起來像真的」的錯誤數字

| # | 問題 | 位置 | 狀態 | 工作量 |
|---|---|---|---|---|
| D1 | 手動匯率預設 `32.0`。JPY 真值 ≈0.21 → **152 倍誤差**。最嚴重的是 4 處「📐 完整計算公式」`st.code` 把 `32.0000` 當**裸數字印進算式**，該區塊零「手動」字樣 | `ui/tab2_single_fund.py:1929` + `:2009/2024/2149/2165` | 📄 | 1h |
| D2 | `_FX_FALLBACK` 12 幣別硬編匯率，流進「組合當前市值」KPI；**「最新 FX」欄的 help 寫「最新即時匯率」= 說謊** | `ui/tab3_t7_ledger.py:322-326` | 📄 ⚠️ | 2h |
| D3 | 借用基金憑空造值 `NAV=10.0` / `FX=31.0`，建立**可落帳**的買方候選。且與 `_FX_FALLBACK["USD"]=32.0` **兩個不同的硬編 USD 匯率** | `ui/tab3_t7_ledger.py:1731-1739` | 📄 | 2h |
| D4 | 無風險利率捏造 `4.0`（SSOT 是 `fund_service.py:43 _RF_ANNUAL=0.04`，兩處都沒 import）。且 `value=None` 時 `None/100` → **TypeError**，該段不在任何 try 內 | `ui/tab1_macro.py:1028-1029` + `app.py:130` | 📄 | 0.5h |
| D5 | 批次「~5s/檔」估算 → **實測 45s/檔**。400 檔宣稱 30-40 分，實際約 **5 小時**（差 7.5 倍） | `ui/tab_batch_analysis.py:222` | 🔬📄 | XS |

## 1-G 🔴 資料真實性其他

| # | 問題 | 位置 | 狀態 | 工作量 |
|---|---|---|---|---|
| E1 | **兩檔台幣基金 1Y 含息顯示 +201.65% / +190.64%**。`CLAUDE.md §3.2` 合理性檢查表**沒有基金 1Y 報酬的上下界** | ACDD01 / ACDD19 | 🔬 | S（補 sanity gate） |
| E2 | **第一屏 KPI 自相矛盾**：「組合基金數 **8 檔**」與「核心 **17** 檔 / 衛星 **8** 檔（=25）」並排，FX 曝險寫 25 檔，sidebar 寫 25 檔。**畫面零解釋** | `ui/tab3_portfolio.py` hero KPI | 🔬 | S |
| E3 | `dividend_safety(nav_change=tr1y)` **把含息報酬當淨值變化傳** → 配息愈高、NAV 崩跌警示愈不可能觸發（與設計目的相反）。正確值 `_tr1y_meta["nav_change_pct"]` **就在同函式 local scope** | `services/health/dividend.py:449, 475` | 📄 | **0.5h** |
| E4 | `_tw_specs` 三處顯示**不存在的 API 名稱** `TaiwanMacroEconomics`（v19.342 已查證不存在）。四個 fetcher **都已回傳正確 `source`**，改讀即可 | `ui/helpers/io/data_registry.py:398-410` | 📄 | **0.5h** |
| E5 | **捏造 / 錯誤的端點字串**：`yp401000/yp405000/yp407000.djhtm`（全 repo 零命中）；`wh06_3`（零命中）；`yp004002`（**是 NAV 歷史頁不是持股頁**）。真實為 `yp013000/yp013001` + `wq06` | `tab5:435`、`tab6:86`、`data_registry:559` | 🔬📄 | 1h |
| E6 | `nav_history` 寫入**零確認、零預覽、無 dry_run、無 rollback**。去重鍵僅 `(code,date)` → **錯級別寫入後正確資料永遠寫不進**。而該分頁被說明書標「🚨 絕對不要刪…無法從任何來源重建」 | `ui/tab_manage.py:884-891` | 📄 | 2-3h |
| E7 | `portfolio_funds` 靜默覆蓋，且 `_build_fund_dict` 只產 9 key → **抹掉 `policy_id`**，破壞 `(policy_id, code)` 複合鍵 | `ui/tab_manage.py:746` | 📄 | 2h |
| E8 | 通報預覽宣稱「和 NAS 週報同一套邏輯」，實測 **6 項差異**。其中 (b) macro composite 讓成長型賣出訊號**在 NAS 端結構性永不觸發**；(e) `skipped` **恆為 0** | `ui/tab_manage.py:463` | 📄 | 文案 10min／治本 4-6h |
| E9 | `_loaded` 未排除 `load_error`（**全 repo 唯一漏網**，其他 8 處都對） | `ui/tab_manage.py:428` | 📄 | XS |
| E10 | LINE 燈號**假陰性**：只檢查 `LINE_CHANNEL_TOKEN`，但 `line_push.py:58` 支援別名 `LINE_CHANNEL_ACCESS_TOKEN`；且短路讓**測試按鈕整顆不渲染** | `ui/tab_manage.py:422, 433` | 📄 | XS |
| E11 | 雷達 5 組門檻手抄且 **3 組已漂移**：VIX 黃 25 vs SSOT **22**；PCR 紅 1.5 vs **1.2**；sector_rotation **值錯+量綱錯**（比值 vs 百分點，實機值 −0.84 證實） | `ui/tab1_macro.py:149-172` | 🔬📄 | 2-3h |
| E12 | 6 個 `st.stop()` 在分頁內 → **中止整個 script**，A 分頁忘填金額會讓 B/C 分頁、帳本面板、AI 區、以及後面所有分頁**全部空白** | `ui/tab3_t7_ledger.py:1177/1184/1190/1219/1269/1498` | 📄 ⚠️ | 2h |
| E13 | **emoji 前綴決定「模擬 vs 真寫入主帳本」**：`startswith("💡")` 失敗 → 靜默走 else = **真的寫進主帳本 + 寫 Google Sheet**。文案改一個字就會發生 | `ui/tab3_t7_ledger.py:1270, 1455, 2116` | 🔬📄 | 3h |
| E14 | sidebar 三處指路指向**不存在的分頁名**（「Tab3「📊 組合基金」」）。SSOT `story_nav.tab_label()` 已存在，`app.py` 已 migrate，**sidebar 漏網** | `ui/sidebar.py:204, 208-209, 240` | 🔬📄 | 0.5h |

---

# §2. P1 — 效能與體驗（使用者有感）

| # | 問題 | 位置 | 狀態 | 工作量 |
|---|---|---|---|---|
| F1 | **`render_metric_explainer` 缺 `mdd` / `div_coverage`** —— 字典早就寫好卻沒被呼叫，而 Coverage 實機出現 **−3.92** 這種最需要解釋的值 | `ui/tab2_single_fund.py:1508` | 📄 | **一行** |
| F2 | **搜尋 → 分析斷點**：搜到 242 檔 → selectbox → 只給一行「代碼：AGIF-FF1 → 在上方輸入框貼入代碼即可分析」，**整區零按鈕** | `ui/tab2_single_fund.py:348-353` | 🔬📄 | 1h |
| F3 | 管理室 gating 首次載入後失效 → 每 rerun ≈ **10-11 次 Google Sheets reads**，上限 60/min → **5-6 次 rerun 撞頂** | `ui/tab_manage.py:293-296` | 📄 | 3-4h |
| F4 | `backtest_turning_points` 抓 30 年 FRED + `^GSPC` 全歷史，**無 cache**，在收合 expander 內 | `services/macro/turning_points.py:366` | 📄 | 2h |
| F5 | `record_fund_nav_point` **同步阻塞在「🚀 分析」路徑上**：首次最多 append 2000 列，且每次 `get_all_values()` 拉**整張** nav_history 做去重 | `nav_history_hook.py:100` + `nav_history_gs.py:187` | 📄 | 1d |
| F6 | batch checkpoint **O(N²)**：400 檔 → 80,200 次 row 序列化、~100-140MB 累計寫入、400 次 mkstemp+rename | `repositories/batch_checkpoint.py` | 📄 | S-M |
| F7 | `_is_preset()` **每個代號重讀一次 JSON**（`_DEFAULT_FUNDS` 模組層快取就在旁邊沒接上） | `ui/tab_manage.py:202` | 📄 | XS |
| F8 | Tab④ **3 顆「📡 載入」綁同一函式** + **2 顆「🔐 用 Google 登入」** + **2 處「請至左側 sidebar」文案（按鈕就在正下方）** | `ui/tab3_portfolio.py:1412/1623/2252、717/907/1008、708/898/1001` | 🔬📄 | 0.5d |
| F9 | 總經載入 **4 個入口**（市場定調 ×2、長期座標 ×1、資料診斷「🔁 重新載入總經」×1），其中兩顆呼叫同一個 `clear_tab1_macro_caches` | 多檔 | 🔬📄 | 0.5d |
| F10 | Tab1 資訊過載：一頁 **~43 張圖 + 17 metric + ~45 張卡**。開發者自己在 `app.py` CSS 註解記錄「**從頂捲到底需 60+ 次滾輪**」 | `ui/tab1_macro.py:1397+` | 🔬📄 | 1-2d |
| F11 | 健診大表 **72 欄**（含恆 `True` 的 `ok` 幽靈欄）、批次 **75 欄**（註解四處寫「40 欄」「48 欄」全錯）；全頁 ≥14 張表 ≈149 欄 | 2 檔 | 📄 | 1d（加精簡模式） |
| F12 | **健診大表未揭露序列長度** —— 個基深掘會寫「淨值 30 筆 · 跨度 42 天」，健診大表 7 欄 `None` 卻零提示 | `ui/tab_fund_grp_health.py` | 🔬 | S |
| F13 | 批次頂端只有 3 metric（健診有 5）。表裡已有「吃本金燈號」「4D Grade」「策略燈號」可彙總，**成本極低** | `ui/tab_batch_analysis.py:302` | 📄 | S |
| F14 | 批次 **無代號數量上限**（健診有 10）、**無中止按鈕**、進度**無 ETA**；`_parse_codes` **靜默丟棄**不符格式的輸入 | `ui/tab_batch_analysis.py:35, 75-98` | 📄 | S |
| F15 | 自刻 CSS grid 固定欄數（`repeat(4,1fr)` 等 8 處，無 `minmax()`）+ `st.columns(N≥4)` 多處 + `components.html(height=900)` | `tab2:1131`、`tab5` ×6、`tab6:115`、`tab_manage:572` | 📄 ⚠️ | 3h |
| F16 | **`help=` 覆蓋率**：管理室 2/31（6.5%）、批次 **0/7**、健診 1/10（**且內容不實**）、Tab5 2/15、sidebar 2/8、Tab2 2/9。破壞性操作 7 顆中只有 2 顆有 help、**0 顆有二次確認** | 全站 | 🔬📄 | 1-2d |

---

# §3. P2 — 架構債與 SSOT

| # | 項目 | 工作量 |
|---|---|---|
| G1 | **新增 `shared/data_sources.py`** 資料源 SSOT（說明書 ⓪ + Tab5 ① + `data_registry` 三方共讀）→ 同時解掉 E4/E5 與文件脫鉤 | 3-5d |
| G2 | fetcher fallback chain 回寫 `_fetch_provenance`，Section ① 依它點燈（**NAV 已用 `series.attrs["source"]` 做到，推廣即可**） | 1-2d |
| G3 | canonical indicator SSOT 收斂 `_FREQ`(29) / `D5_KEYS`(16) / 引擎輸出(25)；**列了沒抓 5 個**（CHN_×4+USDCNY）、**抓了沒列 1 個**（NFP）、**不計入完整率 9 個** | 3-5d |
| G4 | `render_t7_section()` **單一函式 2798 行 / 19 個內部函式 / 最深 13 層縮排** → 拆分 | 1-2d |
| G5 | OAuth client 取得 **6 條路徑**（4 份逐字複製），**只有 `_t3_sheet_client()` 是 SA-first** → `tab3_portfolio.py:2141` 讓 SA-only 部署**靜默不寫回 Sheet** | 3h |
| G6 | `unified.py` 欄序推導**寫兩遍**（`:151-163` vs `:264-273`），已造成 `ok` 幽靈欄 | M |
| G7 | 說明書位階分界(8/5/3) vs 天氣分界(7/4) **自相矛盾**；`GRADE_CUTOFFS_4D` SSOT 存在但說明書沒 import（隔壁 `columns.py:142-146` 已做對） | M |
| G8 | `us_indicators.py:1492-1500` 天氣 `alloc.get(..., 60)` **預設值全是死碼** —— 畫面「☀️ 晴天」實際顯示的是擴張的 60/30/10 | S |
| G9 | 健診線性年化 vs 幾何年化**同表並排**（3 年 +33.10% → 10.00% vs 11.03%，欄名都叫「年化」） | 1d |
| G10 | 健診缺「期末市值 / 淨結果」—— `units_held_🧮` / `last_nav` / `fx` **全在記憶體，差三行乘法** | 1.5d |
| G11 | 刪死碼：`tab_manage` 80 行 + `v2_editor` ~100 行 + `t7:995` + Tab1 3 個 import + 14 個未用色票 + `columns.py:334` 欄名空格 | S |
| G12 | 顏色 inline hex 收 `shared.colors`（Tab2 14 處 + Tab3/T7 17 處 + 其他） | S-M |
| G13 | 說明書加**詞彙表** + `shared/glossary.py` 全站共用（17 個名詞零解釋） | 1d |
| G14 | `render_indicator_map` 抽到 `ui/components/`（解 UI→UI 交叉 import）；6 處過期 Tab 指路 | S |
| G15 | 逐列寫 Sheets 無 batch：`append_ledger_row` 雙層迴圈、`upsert_fund_in_policy` 逐檔 | 3h |
| G16 | 兩檔共 **~77 個 `except`，只有 3 個寫 stderr（3.9%）** | M |

---

# §4. 實機新發現的小問題（報告 v2 沒有）

| # | 問題 | 狀態 |
|---|---|---|
| H1 | **分頁名 vs 頁面標題不一致 ×2**：「配置 & 帳本」vs「組合基金管理」、「個基深掘」vs「單一基金深度分析」 | 🔬 |
| H2 | **死指標文案「🎣 全量抓取」** —— 市場定調頁沒有這顆按鈕（只有「📡 更新總經資料」「🆕 強制重抓最新」） | 🔬 |
| H3 | **死指標文案「🎣 從 Sheet 同步」** —— 保單分組視圖叫使用者按這顆，畫面上找不到 | 🔬 |
| H4 | 「🔴 吃本金 1」與「沒有急需換掉的標的」同頁並存。**邏輯正確且有解釋，但新手必然困惑** → 建議 KPI 卡加指路 | 🔬 |
| H5 | 體檢表 8 檔中 **5 檔「同類資料不足」= 62.5% 無法 PK** | 🔬 |
| H6 | sidebar 全局資料健康：**25 檔全部 ⬜ 未知** | 🔬 |
| H7 | sidebar 版本顯示 **2 次**；`Fetcher v6.24` 硬編字串；`♻️ 強制同步 GitHub` 在雲端**實質無效**（`PROCESS.md:65` 已記載） | 🔬📄 |
| H8 | sidebar **資訊架構倒置**：登入 + 選帳本（使用前提）排最後，測試 Proxy / GitHub 同步（雲端無效）排最前 | 🔬📄 |

---

# §5. ⚠️ 留到最後驗收的 5 項（依你指示）

| # | 項目 | 為什麼還沒驗 |
|---|---|---|
| V1 | Tab5 Section ① 燈號誤綠（A4） | 條件成立過兩次，**兩次都撞上 N1 凍結** |
| V2 | T7「目標單位數」死碼（C3）／`_FX_FALLBACK` 無標記（D2）／`st.stop()` 炸整頁（E12） | 需要建測試持倉，且 N1 未修前操作不下去 |
| V3 | 我的管理室：`portfolio_funds` 覆蓋（E7）／通報 6 項差異（E8）／LINE 燈號（E10） | 同上 |
| V4 | 健診大表「換匯資訊 🧮」欄前綴 | Streamlit 表格橫向捲動自動化拉不動，**需你手動捲** |
| V5 | 健診 slider 死控制項（C2） | 25 檔的缺口是 9.19 / 8.46 / 6.16 / −3.02 pp，**沒有一檔落在滑桿範圍 0.5~5.0 內** |

**驗收時機**：N1（連線）修好之後，重新載入 25 檔，這 5 項一併驗收。

---

# §6. 🔴 需要你先確認 / 拍板

| # | 項目 | 為什麼需要你 |
|---|---|---|
| **Q1** | **Sheet 裡 ACDD01 / ACDD19 的 `currency` 欄實際填什麼？** | 三種情況修法不同：**空白** → 改 `v2_editor.py:85` 單行／**「台幣」** → 同時要補 `normalize_ccy`／**「USD」** → 是 Sheet 資料錯，程式沒問題 |
| **Q2** | **批次分析要不要並行化？** | 現況「序列 + 45s/檔」**就是唯一的限流器**。400 檔 ≈ 2,400-10,000 requests。而 `signal_thresholds.py` 記載你 2026-08-11 拍板「**不增加對 MoneyDJ 的請求數**」 |
| **Q3** | **雷達門檻 VIX 25→22、PCR 1.5→1.2 要不要改？** | **會改變畫面上警戒線的位置**。且 app 已有 caption 揭露此差異 |
| **Q4** | **批次分析要不要併進組合健診？** | 批次頁自承「與『組合健診』**同一張大表**」。合併的是**入口**不是資料，但踩到你「去重 ≠ 合併」的紅線邊緣 |
| **Q5** | **Tab1 詳細區改分頁 / Tab④ 保單管理改巢狀 tabs？** | 最動你的工作流。`STATE.md` v19.405 明講留給你決定 |
| **Q6** | **健診 slider 移除還是接回？** | 移除 = 誠實但少一功能；接回 = 多一欄但要解釋兩套燈號差異 |
| **Q7** | **sidebar 開發者功能收 expander 還是搬 Tab5？** | 屬 `STATE.md` v19.336 **待核准清單**，不是新提案 |

---

# §7. 建議修復順序

```
第 0 批（半天）── 必須最先，否則後面驗不了
  N1-a  AI snapshot 改 lazy（按鈕 callback 內才算）
  N1-b  持倉健診加按鈕守門 / session 快取
  N1-c  60 月回測加 cache 或改按鈕觸發
  N1-d  兩處 Google Sheets 加 cache
  N1-e  data_registry 只存 latest_date/count，用 s.index.max() 取代全量 sort
  → 修完請 user 重新載入 25 檔驗收「不再斷線」

第 1 批（半天）── 全部是改幾行或改文案
  J1-a  v2_editor.py:85 單行（**待 Q1 確認**）
  E4    _tw_specs 假 API 名
  C1    anomaly_view_state + B1 fixture
  E5    三組捏造端點字串
  E3    dividend_safety nav_change 參數
  D4    無風險利率 4.0（2 份副本）
  E14   sidebar 三處舊 Tab 名
  E9    _loaded 未排除 load_error
  E8    通報文案（治本另議）
  D5    批次估算改實測值
  C3    t7:1091 刪一行
  F1    explainer 補 mdd/div_coverage（一行）
  H1-H3 分頁名 + 兩處死指標文案

第 2 批（3 天）── 假成功 / 死控制項清乾淨
  A1-A12、B2、C2、C4、D1-D3、E1-E2、E6-E7、E10-E13
  → 收尾：把「✅/⚠️/❌ 三態約定」寫進 CLAUDE.md

第 3 批（1 週）── P1 效能與 UX
第 4 批（依需求）── P2 架構債，建議 G1 shared/data_sources.py 優先
```

---

# §8. 已撤回的判定（透明紀錄）

驗證過程中，**我自己推翻了 11 條**先前的結論。列出以免誤導：

| 原判 | 實際 |
|---|---|
| 健診 FX 在配息計算被數學抵消 | v19.449 已修（`fund_row.py:103` 有傳 `fx_rate_by_date`） |
| 健診比較圖 `or 0` 偽造 None | v19.387 已修（改 `safe_num`） |
| `process_one_fund` 造成 L2→L3 反向依賴 | v19.413 已下沉 `services/` |
| `build_dividend_summary_row(principal_twd)` 是死參數 | 不是，驅動兩個顯示欄 |
| Tab2 `compute_1y_total_return` 雙來源 SSOT 分裂 | `macro_helpers.py` 是 12 行 shim，**同一 function object** |
| Tab2 `tdcc_search_fund` 未登記例外 | 已登記 `CLAUDE.md:518` |
| 管理室與 Tab④ 文案矛盾 | v19.451 已改唯讀，兩頁一致 |
| 管理室 429 被吞成看不出原因 | `friendly_error` 帶型別+訊息+stderr |
| Tab1 `set_risk_free_rate` 同功能雙路徑 | `fund_fetcher.py:316` 是 re-export shim |
| checkup 本金寫死 1M | 「每月100萬配息(TWD)」是**刻意的 PK 口徑**，caption 有解釋 |
| PCR 錯誤警戒線畫在畫面上 | 全源失敗顯示「無資料」，**線畫不出來** |
| 策略選股引擎門檻與大表分歧，需重建 | **2026-08-07 已收斂**。`services/fund_screening.py:299-343` 已統一走 HWM σ rank，門檻取 `shared/signal_thresholds`；`tests/test_fund_screener_low_base.py:260` 的 `test_screener_and_big_table_always_agree` 就是我想補的那條跨畫面一致性鎖，早就存在。依 §-1 不重建。 |

---

# §9. Layer 2 施工紀錄（2026-08-14）

全套測試 **4163 passed / 0 failed**（`test_undefined_name_scan` 那 2 條既有失敗一併修掉，見下）。

| 編號 | 問題 | 修法 | 檔案 |
|---|---|---|---|
| A1 | 批次列部分失敗無條件標「✅ 成功」（①失敗留白 13 欄／②7 欄／③22 欄）；post-merge 三組欄不在任何 try 內，一拋例外整個 App 從批次分頁往下全白 | 收集 `_degraded` → 「⚠️ 部分成功」+ 備註列出缺哪組；post-merge 包 try；摘要改四態；`_is_retryable` 讓部分成功進得了重試 | `unified.py` / `tab_batch_analysis.py` / `columns.py` |
| E1 | 大表印出 +201.65% / +190.64% 的**台幣**基金 | 根因 = 30 天漲幅 ×12 外推。門檻 → `RET_1Y_EXTRAPOLATE_MIN_DAYS`(180)、倍數 → 2.0，未達門檻回 `(None, SRC_TOO_SHORT)`；四條 fallback 全加合理性帶標記（不改值不丟值） | `fund_total_return.py` / `signal_thresholds.py` |
| F12 | 大表不揭露樣本量：30 筆淨值的列，σ/Sharpe/MaxDD 留白但 4D 照樣給分，與正常列同形 | 新增「淨值樣本」欄（`⚠️ 30 筆 · 42 天`），排在 4D Grade **之前** | `report.py` / `unified.py` / `columns.py` |
| C4 | 換標建議規則 (b) 撈 `annual_div_rate_pct` —— **這個 key 從未存在** → adr 恆 None → 4D 少一維 | 產生端補回傳 `_adr_pct`，消費端改吃它；並補 tr1y 早退路徑（否則 E1 剛好把流量灌進沒有 adr 的那條） | `dividend.py` / `replacement.py` |
| D1 | 手動匯率預填 32.0，日圓/南非幣基金一進來就帶美元匯率 | 改 `value=None` + placeholder；**並把試算區 gate 加上 `_fx_ready`** —— 只改預設值會讓非台幣基金在留空時用 fx=1.0 算完照印，而畫面寫著「暫不計算」 | `tab2_single_fund.py` |
| E11 續 | 4 條雷達門檻測試把**錯誤值**鎖住（VIX 25 vs 燈號 22；PCR 線 1.50 高於門檻 1.20；sector_rotation 用比值 1.00 鎖住百分點制 → **永遠不會亮的警戒線**） | 全改 import `RADAR_*` 常數 + 補一條掃全表的漂移總鎖 | `test_tab1_threshold_lines.py` / `test_audit_20260805_tab1_wiring.py` |
| — | `test_undefined_name_scan` 兩條長期紅，訊息是 `'NoneType' has no attribute 'strip'`，看起來像 production 有未定義名稱 | 實為 `subprocess.run(text=True)` 未指定 encoding → Windows cp950 解不了 ruff 的 UTF-8 輸出（本 repo 註解皆中文）→ **全站 F821/F405 掃描一直在空轉**。補 `encoding="utf-8"` + None 的誠實錯誤訊息 | `test_undefined_name_scan.py` |

**E1 的取捨（user 2026-08-14 拍板「照修、留白」）**：只抓得到「近 30 日淨值表」那批基金（保單專屬網頁被擋時常見），其 4D Grade / Alpha / 換標策略分會從有值變 `—`，也不再進換標候選池。理由：那些分數本來就是把一個月的漲跌乘十二得到的，不是量出來的。新增的「淨值樣本」欄負責讓使用者看懂留白的原因。

**獨立稽核**：第一輪**駁回**（2 🔴 + 8 🟠）。其中 1 🔴 是 D1 修一半造成的新漏洞，1 🔴 是 E1 打爆既有的 ACTI71 護欄；🟠 含一條我自己寫的假綠測試（docstring 裡剛好有常數名，把 import 刪掉改寫死數字照樣通過 → 已改走 AST）。全數修畢。

---

# §10. Layer 3 施工紀錄（2026-08-14）

全套 **4212 passed / 0 failed**。

## 10-A 六條監控/評分層 bug

| 編號 | 問題 | 修法 |
|---|---|---|
| E13 | A/B/C 三個落帳流程用 `_commit_mode.startswith("💡")` 決定這次是**試算**還是**真的寫進帳本**。那個 💡 是唯一的安全閥 —— 改成 📝 就會讓「試算」直接寫進主帳本，成功訊息照印 | 選項收 SSOT 常數 + 相等比對；認不得的值**拋錯不猜邊**（猜哪一邊都會弄壞資料） |
| D2 | 跨保單借基金時憑空給 NAV=10.0 / FX=31.0（10.0 是基金常見發行價，看起來特別像真的） | 缺就擋下並說明怎麼補（比照 v19.59 對幣別的既有決定） |
| D3 | `_FX_FALLBACK` 寫死 12 個幣別匯率，連 log 都沒有 | **行為不動**（拿掉會讓市值歸零變 −100% 假象，更糟），補 §1 要求的 log + 帳本面板旗標 |
| A8 | 抓不到報價時，總表退回成本基礎（損益 0、報酬 0.00%），帳本表卻歸零（報酬 −100%）—— **同一情境兩個相反的謊** | 兩邊都排除該部位、留白、揭露有幾檔沒計入；報酬率可為 None（「不知道」≠「0.00%」） |
| A9 | B 分頁分到錢卻沒落帳的檔照樣印「應買 30,000」 | 標「⛔ 未落帳」，不計進投入總額與預估配息；「本次投入」改顯示**實際落帳**金額 |
| E2 | 全站 10 處只判 `loaded`，但抓失敗的基金也是 `loaded=True` —— KPI 說 25 檔、表格只有 8 列的成因 | 收 `fund_is_usable` SSOT，migrate 4 處影響使用者的（組合 KPI／T7 帳本／MK AI／集中度）。T7 那處最嚴重：空殼基金原本進得了落帳試算 |
| C2 | 「吃本金閾值 %」滑桿產出的欄位全 production 0 consumer，拖動它畫面零變化 | 拆除。吃本金是既定方法論，開放成滑桿等於讓人調出一個沒有紅燈的組合 |
| E12 | 6 處 `st.stop()` 中止**整個 script run**，Tab3 以下所有分頁跟著空白 | 自訂例外 + 呼叫端攔截。**沒有**把三個 submit handler 各包一層 try（合計 810 行縮排，diff 風險高於問題本身，§8.4） |

⚠️ 過程中我自己種了一個 bug：修 D2 時加了 `st.stop()`，正是 E12 要拔的東西。已改 if/else。

## 10-B 6D → **5D**（實測後改案）

`scripts/audit_6d_coverage.py` 實測結果推翻原訂計畫：

| 候選維度 | 證據 | 決定 |
|---|---|---|
| 費用率 | 官方揭露 **0/2**，有值的都是「拿經理費當費用率」 | **不納入**。境外基金常差一倍以上，用它分 A/B 是系統性偏低 |
| 基金規模 | 2 檔撞出 2 種格式：`266.04 億(美元)` vs `58,185.32 百萬歐元` | **不納入**。單位差 100 倍 + 幣別差一層；naive 比數字誤差約 **90 倍**，且解析錯**不報錯**（§4.1） |
| 匯率風險 | 2/2 可算，資料既有且已在用（`nav_fx_switch`） | **納入** |

**第 5 維設計**：量的是**波動**不是位階（「現在匯率貴不貴」已由「匯率位階」欄負責）。
指標 = 變異係數 CV = std/mean × 100 —— USDTWD ≈ 32、JPYTWD ≈ 0.21，
同樣 3% 波動的絕對 std 差 150 倍，直接比是量綱錯誤。
**台幣基金 = N/A 不是 0 分**：沒有匯率風險是事實，給 0 分等於懲罰一個優點，分母須扣除。

**新增「評分覆蓋」欄**（排在等第**之前**）：`✅ 5/5` / `⚠️ 2/5（缺 走勢、匯率）` /
`➖ 4/4（台幣，無匯率風險）`。`GRADE_4D_MIN_FACTORS = 2` 表示湊得出 2 維就給等第 ——
沒有這一欄，2/5 的 A 和 5/5 的 A 在表上完全同形（F12 的評分版，但後果更嚴重：
F12 只是欄位留白，這裡是**一個看起來很有信心的字母**）。

**匯率快取下沉 L2**（`services/fx_regime_service.py`）：第 5 維會改變分數本身，
而 `services/fund_batch.py`（L2）也是 caller、構不到 L3 helper（§8.2）。
6 個 caller 全接同一份，parametrize 測試逐檔鎖住。

⚠️ 下沉時我**沒有跟著改 monkeypatch 靶點** —— 兩條測試的 patch 因此完全失效、會安靜地打真網路。
若不是另外幾條戳私有變數而炸出 AttributeError，這個假綠會混過去。
修正時一併：靶點改 L2、私有變數換成公開 `clear_cache()`、加一條**掃 production 原始碼**
禁止任何檔案再從 L3 import 匯率快取。

## 10-C 待辦（已識別，未動）

- 欄名「4D Grade / 4D Score」已名實不符（現為 5 維），且「4D」本身是內部術語。
  白話化需同步改 UI + 測試，屬獨立一批。
- `test_app_apptest` / `test_get_latest_fx_fred_fallback` 兩條測試**會真的連外網**
  （`open.er-api.com`，warnings 可見）。既有問題，非本輪引入。

---

*第一階段最終清單 · 2026-08-14 · 8 條並行程式碼稽核線 + 6 輪實機驗證 · Layer 1~3 已施工*
