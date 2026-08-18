# 基金戰情室 — 第一階段診斷提案報告 **v2（本機驗證版）**

> **狀態：提案，尚未動任何一行程式碼。** 依指示第一階段只診斷。
> 稽核基準：本機 clone `D:\01.Github\20260813\基金`（= GitHub `main` HEAD，`STATE.md` v19.433+，檔內註記最新 v19.456）
> 部署：https://my-fund-dashboard-ca8spcltzv6rvgo575fkgp.streamlit.app/

---

## 0. 團隊編組與本版與 v1 的差異

### 0.1 專家 Agent 編組

| 角色 | 職責 | 本階段產出 |
|---|---|---|
| **產品經理 / UI-UX 設計師** | 視覺層級、新手友善度、RWD、導覽邏輯、控制項瘦身 | 每 Tab 控制項全清單 + `help=` 覆蓋率 + RWD 風險點 |
| **資深資安與資料稽核師** | 假資料 / 硬編碼 / 靜默失敗 / provenance / 假綠測試 | 逐條真偽判定 + 端點字串真實性核對 |
| **資深 Python / Streamlit 工程師** | 重構、快取、rerun 成本、SSOT、分層違規、死碼 | 重複計算次數、API 呼叫量、死碼盤點 |
| **金融與投資分析師** | 指標語意、計算式驗算、單位陷阱、白話文 | 數學式驗算 + 量綱檢查 + 名詞缺口 |
| **獨立稽核 Agent**（第二階段） | **不參與實作**，只驗收 `git diff` | 見 §5 驗收關卡 |

八條並行稽核線：7 個頂層 Tab + 側邊欄，全部以**本機檔案**逐行 Read/Grep 核對。

### 0.2 ⚠️ v1 有 9 條結論被本機驗證推翻 — 必讀

v1 是在**沒有本機副本**時逐檔 HTTP 抓取產出的，而 `raw.githubusercontent.com` 會回傳過期 CDN 快取（你的 `PROCESS.md §4` 已記載此坑）。以下 v1 結論**不成立**，已從本版移除或降級：

| # | v1 說 | 實際 | 根因 |
|---|---|---|---|
| 1 | 健診 FX 在配息計算中被數學抵消 | **v19.449 已修** — `services\fund_row.py:103` 有傳 `fx_rate_by_date`，抵消只在 Yahoo 抓不到的 fallback 路徑成立 | 讀到舊快照 |
| 2 | 健診比較圖用 `or 0` 把 None 偽造成 0.00% | **v19.387 已修** — 改走 `safe_num`，Plotly 留缺口。僅 `tab:846` KPI 加總殘留 | 同上 |
| 3 | `process_one_fund` 住 `ui/` 造成 L2→L3 反向依賴 | **v19.413 已下沉** `services\fund_row.py`，現為合法 L3→L2 | 同上 |
| 4 | `build_dividend_summary_row(principal_twd)` 是死參數 | **不是** — 它驅動「每月配息 (TWD)」「每月配息單位數」兩欄 | 誤判 |
| 5 | Tab2 `compute_1y_total_return` 有兩個 import 來源造成 SSOT 分裂 | **整條撤回** — `ui\helpers\macro_helpers.py` 是 12 行 shim，兩條 path 指向**同一個 function object** | 誤判 |
| 6 | Tab2 `tdcc_search_fund` 未登記 L1 直呼例外 | **已登記** `CLAUDE.md:518` EX-PASSTHRU-1。真問題只是行號過時 + 檔內缺註解 | 未查例外表 |
| 7 | 管理室與 Tab④ 文案矛盾、「照管理室做就發現不了 Tab④ 有編輯器」 | **v19.451 已改唯讀** — `ui\helpers\v2_editor.py:334 disabled=True`、`:262` 標題直寫「唯讀」。**兩頁文案一致，不矛盾** | 讀到舊快照 |
| 8 | 管理室 429 錯誤被吞成看不出原因 | **錯** — `session.py:138-150` 主訊息帶例外型別+訊息且鏡射 stderr；`policy\_helpers.py:85-86` 對 429 明確回「配額超載，等 30~60 秒」 | 未追 helper |
| 9 | Tab1 `set_risk_free_rate` 形成 L1/L2 同功能雙路徑 | **不成立** — `fund_fetcher.py:316` 是 `# noqa: F401` re-export shim，同一 function object | 誤判 |

**這 9 條的教訓已寫進本版方法論**：所有結論附 `檔名:行號` + 原文摘錄，且標注驗證狀態。

### 0.3 v2 新增的「比 v1 更嚴重」發現

| # | 問題 | 為何比原判嚴重 |
|---|---|---|
| A | **Tab1 雷達門檻不是「註解行號錯」而是真的漂移了** | VIX 黃線 UI 畫 25、SSOT 是 22；PCR 紅線 UI 畫 1.5、services 判 1.2 → **同一張卡上燈號與警戒線互相打架**；sector_rotation 連量綱都錯（比值 vs 百分點） |
| B | **兩個「假綠測試」在幫 bug 背書** | `tests\test_data_guard_anomaly_state.py:47,85` 的 fixture 寫死生產端從不產生的字串；`tests\test_review_fixes_v19_346.py:142-151` 只比對裸 `pass`，**加一句註解就過關** |
| C | **換標的建議 4 條規則實際只有 1 條穩定可用** | `replacement.py:126` 取不存在的 key → adr 恆 None → 沒 Sharpe 的基金 grade 恆 `—` → rule (b) 完全失效；加上 (a)(c) 靜默停用 |
| D | **Tab5 有捏造的端點字串** | `:435` 的 `yp401000/yp405000/yp407000.djhtm` **全 repo 零命中**；`data_registry` 的 `yp004002` 是 NAV 歷史頁**不是持股頁** |
| E | **Tab6 天氣表描述的是一組死碼** | `us_indicators.py:1492-1500` 的 `alloc.get(..., 60)` 預設值永不觸發；畫面「☀️ 晴天」實際顯示的是**擴張的 60/30/10**，說明書寫的是那組死掉的預設值 |
| F | **Tab2 手動匯率的污染面比想像廣** | 不只 metric——`:2009/2024/2149/2165` 的「📐 完整計算公式」`st.code` 把 `32.0000` 當**裸數字印進算式**，該區塊完全沒有「手動」字樣。JPY 場景 152 倍誤差 |

### 0.4 現行 Tab 拓撲（`app.py:196-199` 確認）

```
sidebar (ui/sidebar.py, 241 行)
└─ st.tabs × 7 —— 分頁名已收 ui/helpers/story_nav.tab_label() SSOT
   ① 🌐 市場定調      ui/tab1_macro.py (1435) + 5 個 section 子模組
   ② 💊 組合健診      ui/tab_fund_grp_health.py + services/health/dividend_calc.py
   ②-B 📦 批次分析    ui/tab_batch_analysis.py (401) + helpers/fund_grp_health/unified.py (445)
   ③ 🔍 個基深掘      ui/tab2_single_fund.py (2450)
   ④ 📊 配置 & 帳本   ui/tab3_portfolio.py (2953) + ui/tab3_t7_ledger.py (2947)
   ④-B 📋 我的管理室  ui/tab_manage.py (928)
   ⑤ 📖 參考 / 診斷   巢狀：tab5_data_guard.py (1547) + tab6_manual.py (833)
```

### 0.5 先講結論：這份程式碼的資料誠實度高於一般專案

- **全站 `fillna(0)` 幾乎為零**；`ffill` 只有 1 處（`tab3_portfolio.py:1875`）且有計數與 log
- **缺值一律顯示 `—` 不填 0**，`tab2:1528-1540` 明寫「0% 會被誤讀成『這檔不配息』」
- **主動刪過假資料並留下理由**：TER 同類均值表（`tab2:1656-1669` 14 行說明）、說明書「台股 TPI」整章、`allocation_simulator.py` 866 LOC
- **雙演算法對帳 chip** 已上線；**pandera schema + CI gate** 已落地
- **`shared/converters.safe_num` 已全面取代 `or 0`**（Tab1 全檔 0 個 fillna/ffill）

下面 60 條是在這個基礎上的下一輪。

---

## 1. 全域發現（跨 Tab 共通，建議當獨立工作項先處理）

### G1 🔴 「假成功 / 假綠燈」是全站最大系統性風險

`CLAUDE.md §1` 寫著「**Fail Loud, Never Fake — 錯誤的數字比沒有數字更危險**」。以下是**會偽綠或偽成功**的位置（已排除「只會落到 ⬜ 未知」的良性靜默）：

| # | 位置 | 現象 |
|---|---|---|
| 1 | `unified.py:403-422` + `:436-437` | 批次三段 `except` 只 print stderr，之後無條件寫 `✅ 成功`。**①失敗留白 13 欄 / ②失敗 7 欄 / ③失敗 22 欄 + 7 欄降級成 ⬜** |
| 2 | `tab3_t7_ledger.py:451-454` | 帳本雲端寫入失敗被吞，`:459-465` `st.success("⚡ 自動估算…")` 完全不提同步狀態 |
| 3 | `tab2_single_fund.py:1066-1067`、`:1138-1139` | `except: pass` 讓 **HWM σ 位階卡**與 **4D 健康總覽卡（大大的 A/B/C/D/F）**整張靜默消失 |
| 4 | `tab5_data_guard.py:436-461` | 資料源總覽 **5 列共用 `_fund_n`**（載入幾檔基金），與該來源是否真被呼叫無關；第 10 列硬寫 `False` |
| 5 | `data_registry.py:451-453` | **雷達 10 燈完全不走 `_freshness`**，value 非 None 就綠，`latest_date` 直接偽造成字串「今日」 |
| 6 | `data_registry.py:553/586/603/656` | 缺 provenance 時回 `"本月"/"年度"` + 硬編 🟢 → 這 4 條路徑**永遠不可能亮紅燈** |
| 7 | `tab5_data_guard.py:1495` | `clean` 分支把 `⬜ 未知日期`（日期解析失敗）算進「狀態全數正常」 |
| 8 | `tab3_t7_ledger.py:936-947` | NAV/FX 抓不到 → 市值退回成本 → 未實現損益恆 0、報酬率恆 0.00%（呈現「不賺不賠」而非「資料缺失」） |
| 9 | `tab3_t7_ledger.py:1530-1570` | B 分頁 NAV/FX 缺時不落帳，但結果表**無條件**顯示「應買 TWD 123,456」 |
| 10 | `tab1_macro.py:947-948` | 清快取失敗被吞後仍設 `_do_load=True` → 使用者按「強制重抓」拿到舊資料且被告知成功。**同型第二處** `tab1_macro_longterm.py:249-250` |
| 11 | `tab_manage.py:658-659` | `get_latest_fx` 失敗 → 所有非台幣基金落成「資料不足」，**不說是匯率抓不到** |
| 12 | `batch_checkpoint.py:121-122` | `except: continue` — 壞掉的 checkpoint 從救援清單**無聲消失** |

**統一修法**：建立 UI 層三態約定 `✅ 成功` / `⚠️ 部分成功（附缺哪幾組）` / `❌ 失敗`，並規定**任何 `except` 都必須在畫面上留痕**。已有正確樣板可抄：`tab1_macro.py:875-884 _safe_section`、`ui\helpers\session.py:118-152 friendly_error`（含 stderr 鏡射 + traceback expander）。

### G2 🔴 兩個「假綠測試」正在幫 bug 背書

| 測試 | 問題 |
|---|---|
| `tests\test_data_guard_anomaly_state.py:47, :85` | fixture 寫死 `_meta("🟡", "release 期已到 +2 天")` —— **這個字串生產端從不產生**。兩個測試長綠但守著一份幻覺契約，這是 G3 的 bug 能存活至今的直接原因。**修 code 時必須同步改 fixture，否則改對了反而測試變紅** |
| `tests\test_review_fixes_v19_346.py:142-151` | 只比對 `ln.strip()=="except Exception:"` 且下一行 `strip()=="pass"` —— **加任何一句註解就能過關**。`# smoke-allow-pass` 是無實質效力的通行證，`tab2:1066` 與 `:1138` 是**被測試蓋章的違憲** |

這比單純漏改嚴重，因為它會讓後續稽核誤以為已治理。

### G3 🔴 三個「死控制項」— 使用者以為在控制，實際沒有

| 位置 | 控制項 | 現象 |
|---|---|---|
| `tab_fund_grp_health.py:185-190` | `slider「吃本金閾值 %」` | **對畫面 100% 無效**。它產出的 `div_health_light_🧮` 全 repo **production 0 consumer**（只有 2 個測試檔）；畫面燈號走 SSOT `NEAR_DIVIDEND_WARNING_PCT=2.0`。而 slider 的 help 明確承諾「> 此值 → 標 🔴 吃本金」= **說謊** |
| `tab3_t7_ledger.py:1091` | `selectbox「投入方式」` | form 外 `:1073/:1082` 依選擇算好 `_a_new_mode_key`，`:1091` 在 form 內**無條件洗成 `"twd"`** → `:1135` 與 `:1224` 兩處「🎯 目標單位數」分支**恆為死碼** |
| `tab_fund_grp_health.py:762` 等 4 個 caller | 換標的建議「 4 規則」 | 全部不傳 `holding_years` → rule (a)(c) eligible 恆 `False`；加上 `replacement.py:126` 取不存在的 key 讓 rule (b) 對無 Sharpe 基金恆不觸發 → **4 條 hard trigger 只剩 (d) 一條穩定可用**，「🟢 保留 —  4 規則全未中」被系統性高發 |

### G4 🔴 硬編碼 fallback 會產生「看起來像真的」的錯誤金額

| 位置 | 值 | 後果 |
|---|---|---|
| `tab2_single_fund.py:1929` | 手動匯率 `value=32.0` | 只對 USD 合理。**JPY 真值 ≈0.21 → 152 倍誤差**。污染 3 條路徑，最嚴重的是 `:2009/2024/2149/2165` 的「📐 完整計算公式」把 `32.0000` 當裸數字印進算式且**零旗標** |
| `tab3_t7_ledger.py:322-326` | `_FX_FALLBACK` 12 幣別硬編匯率 | 流進「組合當前市值」KPI；帳本表「最新 FX」欄的 help 寫「**最新即時匯率**」= 直接說謊 |
| `tab3_t7_ledger.py:1731-1739` | 借用基金 `NAV=10.0` / `FX=31.0` | 憑空造值建立**可落帳**的買方候選。且與 `_FX_FALLBACK["USD"]=32.0` **兩個不同的硬編 USD 匯率** |
| `tab1_macro.py:1029` + `app.py:130` | 無風險利率 `4.0` | SSOT 是 `fund_service.py:43 _RF_ANNUAL=0.04`，兩處都沒 import。**另有潛在 crash**：`value` 為 `None` 時 `None/100` → TypeError，且該段不在任何 try 內 |
| `tab_batch_analysis.py:222` | `~5s/檔` 估算 | 400 檔估「30-40 分」，實際 13 分～3.3 小時 |

### G5 🟠 rerun 成本 — Streamlit 兩個特性被系統性忽略

**特性 A**：`st.tabs` 每次 rerun 渲染全部分頁（`app.py:205` 註解自己講明）。
**特性 B**：`st.expander` body 即使收合也會執行。

| 位置 | 每次 rerun 都跑 | 有無 cache |
|---|---|---|
| `tab5:793-794` `backtest_sub_cycle_lights(window=60)` | 7 子領域 × 60 月 expanding z-score，包在收合 expander | ❌ `causal_sankey.py:317` 無 decorator |
| `tab5:1371-1372` `nav_history_gs.status()` | 讀 secrets + 建 SA client，**連 expander 都沒有** | ❌ |
| `tab5:1407-1409` `coverage_status()` | **一次 Google Sheets 網路讀取（讀整張 nav_history）** | ❌ |
| `tab3_portfolio.py:2694 → :2745-2839` | AI snapshot 在按鈕之前全算完： df + checkup + **`fetch_usdtwd_frame` 網路** + 組合回撤 + 逐檔 maxDD + 相關性矩陣 + **每幣別一次 `get_latest_fx`** | ❌ |
| `tab3_portfolio.py:2559-2626` | 持倉健診 ThreadPool(4) 對每檔跑 `process_one_fund`，**唯一守門是 `if _loaded_pf:`** | ❌ |
| `data_registry._update_data_registry()` | `app.py:273` 在 Tab5 渲染前呼叫 → **使用者停在 Tab1 也照跑**。25 指標 + N 檔基金全量 `sort_index()` 並把排序後**完整 Series** 塞進 session_state | 冷 cache 下 **16 key × 2 = 32 次 FRED HTTP** |
| `tab_manage.py:293-296` | gating 首次載入後失效 → 每 rerun 重打 `load_all_policies_v2`（無 TTL）+ `list_pool()`（無 cache） | ≈ **10-11 reads/rerun**，`policy\_helpers.py:93` 記載上限 60 reads/min → **5-6 次 rerun 撞頂** |
| `tab1_macro_inflection.py:442-447` | `backtest_turning_points` 抓 30 年 FRED + `^GSPC` 全歷史，在收合 expander body 內 | ❌ `turning_points.py:366` 無 decorator。**Tab1 唯一真效能瓶頸** |

> ⚠️ **v1 誤判修正**：`_fred_chip` ×10（無 I/O）與 `fetch_us_liquidity_snapshot` ×2（有 30min TTL cache）**都不是效能問題**，屬程式碼重複。

### G6 🟠 手機 RWD — 問題集中在「自刻 HTML」而非 Streamlit 元件

`use_container_width=True` 覆蓋率極高（plotly / dataframe 幾乎 100%）。壞在三類：

| 型態 | 位置 | 問題 |
|---|---|---|
| 自刻 CSS grid 固定欄數（無 `minmax()` / 無 media query） | `tab2:1131-1132` `repeat(4,1fr)`；`tab5` 6 處（`:292/:468/:551/:989/:1511`，其中 `:468` 是 6 欄且第 4 欄塞 200+ 字元 monospace endpoint）；`tab6:115` 5 欄 | **Streamlit 響應式管不到**。4D 總覽卡（本頁最重要的結論卡）在手機壓成 4 條窄柱 |
| `st.columns(N)` N≥4 | `tab5` 5 處 `columns(4)`（Section ⑤ 每檔 20 格）；`t7:663` 與 `:2723` **6 欄**；`tab1` radar/midcycle/inflection 各 1 處 `columns(5)`；`tab2` 3 處 `columns(4)` + `:528` 動態常 6-7 | 窄螢幕堆疊成 N 列 → 頁面長度暴增 |
| `components.html` 固定高 | `tab_manage.py:572` `height=900, scrolling=True` | 不吃 `use_container_width` → **巢狀雙捲軸** |
| 超寬表格 | 批次 **75 欄**、健診大表 **72 欄**（含 1 個恆 True 的 `ok` 欄）、體檢 PK 21 欄、T7 帳本 18 欄 | 批次表橫捲約 15 個螢幕寬 |

### G7 🟡 名詞解釋：字典寫好了卻沒被呼叫

`ui\helpers\chart\metric_explainers.py:41-45` 有 `"mdd"`、`:53-58` 有 `"div_coverage"`，但 `tab2:1508` 的 `render_metric_explainer(["sharpe","sigma","alpha","beta"])` **沒帶這兩個**。

而「最大回撤」與「配息覆蓋率」正是這頁對新手最重要的兩個字（最多會虧多少、配息有沒有吃本金），且同頁 `:1329` 就有 `Max DD %` metric、整段吃本金 KPI 卡。**改一行即可。**

`help=` 覆蓋率總表：

| 檔案 | 控制項數 | 有 `help=` | 覆蓋率 |
|---|---|---|---|
| `tab_manage.py` | 31 | 2 | **6.5%** |
| `tab3_portfolio.py` + `tab3_t7_ledger.py` | 45 | 17 | 38%（破壞性操作 7 顆中只有 2 顆有，**0 顆有二次確認**） |
| `tab_batch_analysis.py` | 7 | **0** | 0% |
| `tab2_single_fund.py` | 9 | 2 | 22% |
| `tab_fund_grp_health.py` | 10 | 1（**且內容不實**） | 10% |
| `tab5_data_guard.py` | 15 | 2 | 13% |
| `sidebar.py` | 8 | 2 | 25% |
| `tab6_manual.py` | 5 | 1 | 20% |

全站尚無解釋的名詞：Max DD、Coverage、Sortino、Calmar、3Y/5Y 年化、追蹤誤差 TE、Sahm Rule、CFNAI、HY OAS、**VIX 期限結構**、MOVE、Put/Call Ratio、sector rotation、Z-Score、σ / HWM、「代理值 proxy」、pp（百分點）。

### G8 🟡 文件與程式脫鉤 — 且有捏造的端點字串

| 項目 | 說明書 (tab6) | 診斷頁 (tab5 / data_registry) | **實際** |
|---|---|---|---|
| 配息 endpoint | `wh06_4` ✅ 真實（子網域平台路徑） | `wb05` ✅ 真實 / tab5 `yp405000.djhtm` ❌ **捏造** | 兩條真路徑並存；**三方都漏了境內走 `funddividend`** |
| 持股 endpoint | `wh06_3` ❌ **全 repo 零命中** | `yp004002` ❌ **那是 NAV 歷史頁** | `nav_metrics.py:977` `yp013000`/`yp013001` + 替代頁 `wq06` |
| 績效/風險 endpoint | — | tab5 `yp401000` / `yp407000` ❌ **捏造** | `/w/wb/wb01.djhtm`、`/yp/wb07.djhtm` |
| 美國總經 12 指標 | 列 `UMCSENT`、**不列 SAHM/SLOOS** | `D5_FRED_KEYS` 有 SAHM/SLOOS、**無 UMCSENT** | 方向完全相反；且 tab6 同頁 `:307-308` 的 warning 自己寫「包含權重最高的 SAHM 與 SLOOS」→ **同一頁表格與警語互相矛盾** |
| USDTWD | refresh **10 min** / fallback 2 源 | `Yahoo→FRED→er-api→Frankfurter`（4 源） | `fx_and_main.py:115` TTL **300s（5 分）**；`:145-147` 明說對 TWD pair **FRED 與 Frankfurter 是 dead path** |
| TW 總經來源 | `TaiwanBusinessIndicator` ✅ 已更正 | `_tw_specs` 三處仍寫 `TaiwanMacroEconomics` ❌ **該 dataset 不存在**（v19.342 查證） | **方向相反的脫鉤：文件對、程式錯** |

**根因**：`tab6_manual.py` 全檔**沒有任何一個數字綁到 `shared/` 常數**（唯一例外 `:759 coerce_weight`）。而 `GRADE_CUTOFFS_4D` 這種 SSOT **明明存在**（`shared\signal_thresholds.py:91`），隔壁 `columns.py:142-146` 已正確 f-string 注入，**只有說明書沒做**。

---
## 2. 逐 Tab 診斷提案

---

### 📌 ① 🌐 市場定調（`ui/tab1_macro.py` 1435 行 + 5 個 section 子模組）

**結構**：無次頁籤（v19.42 刻意消滅 tab strip）。兩層 —— **總表區**（① 結論 → ② 依據 → ③ 例外 → ④ 可信度 → 資料新鮮度條）+ **詳細區**（🌳長期 → 📈中期 → 🎯短線 → ⚠️拐點 → 📋決策矩陣 → 🇨🇳中國副盤 → 🤖AI）。

#### 1. 現狀診斷與問題點

**資料稽核問題**

| 嚴重度 | 位置 | 問題 |
|---|---|---|
| 🔴 | `:1028-1029` + `app.py:130` | `set_risk_free_rate(ind["FED_RATE"].get("value",4.0)/100)` — 缺值捏造 4% 流進全站 Sharpe/Sortino。**SSOT 是 `fund_service.py:43 _RF_ANNUAL=0.04`，兩處都沒 import**。且 `value=None` 時 `None/100` → TypeError，該段不在任何 try 內 |
| 🔴 | `:149-172` | **5 組雷達門檻手抄 `services/risk_radar.py`，其中 3 組已漂移**：VIX 黃 **25 vs SSOT 22**（`risk_radar.py:105-107` 註解自承「v19.157 統一 22」— UI 就是那次漏網，與 `CLAUDE.md §8.3` 宣稱矛盾）；PCR 紅 **1.5 vs 1.2**（此組 trend 非空，**錯線真的畫在畫面上，與同卡燈號互相打架**）；sector_rotation **1.00/1.20（比值）vs 實際 gap≥2/≥4（百分點）**— 值錯 + 量綱錯。5 條 `# services L###` 註解**沒有一條對得上** |
| 🟠 | `:1049-1050` | 系統性風險計算失敗 → 靜默寫 `None`，**無 UI 提示、無 log**。（v1 點名的 `:1044 "LOW"` default 因服務層恆給 `risk_level` 而**永不觸發**；真洞在這裡。另 `tab1_macro_ai.py:140` 同型且**餵給 Gemini**） |
| 🟠 | `:947-948` | 清快取 `except: pass` 後仍 `_do_load=True` → 使用者拿舊資料卻被告知成功。**同型第二處 `tab1_macro_longterm.py:249-250`** |
| 🟠 | `:1305` vs `:1336` | 45/75 與 40/70 兩套月頻門檻**渲染在同一個 markdown 區塊**（`:1365-1377`），使用者看到同列兩顆 🟠 代表不同天數。註解有解釋語意差，但兩套都是 inline magic |
| 🟡 | `:520-522` | Sankey `value=[5,5,4,3,4,3]` 編造。**但 v1 說「UI 無標註」不成立** — 本 Tab 0 呼叫，唯一 caller `tab6:620` 已標「靜態教學示意」。**新問題**：`tab6:630` 指路「Tab1 動態權重版」，該功能已於 2026-08-07 移除 |
| 🟡 | `:853-863` | 動作對照表 100/130/50/0% 與 σ 規則。**SSOT 是 `services/decision_matrix.py:43` 不是 `realtime_signal`；且目前值全對** → 屬「未接線的漂移風險」非已發生 bug。唯一缺漏：`decision_matrix.py:82-85` 的 `σ≤-2 + 中性 → HOLD 升 ADD` 分支 markdown 沒寫 |
| 🟡 | `:597` | `_dyld = float(... or 0)` 漏網（上兩行已 `safe_num`）。但下游 `if _dyld > 0` 會整段 skip，**不產生被顯示的假數字** |

✅ **全 6 檔 0 個 `fillna` / `ffill` / `bfill` / `interpolate`。** 缺值一律走 `safe_num` 保留 None + `⬜ 資料不足` 誠實佔位。

**UI/UX 與操作體驗問題**

- **控制項極簡但有 1 對真冗餘**：全 Tab（含子模組）只有 **5 個 button，0 個 selectbox/slider/checkbox/radio/toggle**。
  - **真重疊**：`:933`「🆕 強制重抓最新（清快取）」與 `longterm.py:243`「🔄 強制重抓」呼叫**同一個** `clear_tab1_macro_caches`，且**可同時出現在畫面上**。
  - **v1 誤判**：`radar.py:204/218` 那兩顆是 `if show_l3 and not _liq_score` vs `if _liq_score and show_l3` — **條件互斥，任一時刻只有一顆可見**。同時可見上限是 4 顆不是 5 顆。
- **資訊過載（v1 低估了）**：實際渲染約 **43 張圖**（開流動性引擎 ~49）、**17 個 metric**、**~45+ 張手刻 HTML 卡**、3 張 dataframe。v1 的「33 圖 / 20 metric / 35 卡」中，圖與卡都低估。
  > 開發者自己在 `app.py` sticky tab bar CSS 註解記錄：「**Tab1 從頂捲到底需 60+ 次滾輪**」。
- **44 個 `except` 只有 3 處寫 stderr**（`:879/:973/:982` 走 `_friendly_error`）；**24 處完全靜默**（無 UI 無 log），其中最危險的 3 個：`:183-184`（門檻 import 失敗 → 長期桶 4 張卡警戒線靜默消失）、`:606-607`（**該處註解自承先前一個 broken import 就是被它吞掉，導致吃本金訊號長期 dead**）、`:728-729`（整個決策矩陣區塊靜默消失，連 `_safe_section` 都接不到）
- **名詞缺口**：Sahm Rule（只畫一條「衰退鎖定 0.5」線）、CFNAI、HY OAS、**VIX 期限結構**（只顯示「倒掛 1.00」這種黑話）、MOVE、Put/Call、Z-Score、σ/HWM/`lookback=252`、「代理值 proxy」
- **RWD**：`radar.py:120` / `midcycle.py:360` / `inflection.py:464` 三處 `columns(5)`；自繪卡字級 9-10px + `letter-spacing:1px`；`:1341-1345` hover tooltip 用 HTML `title`，**觸控裝置沒有 hover**

✅ **`:1107-1124` ① 結論層是本次稽核看到最好的資訊架構**：一句話結論 + 理由條列 + 免責 + 指路，`_action_light_renderer`（`:345-358`）未知燈色一律落 warning **不下假綠燈**。
✅ `:707-711` China Drag caption 主動防誤讀（「BCI 基準 100 ≠ PMI 50 榮枯線」）—— 這種寫法應複製到其他指標。

**程式碼問題**

- **UI 直呼 L1**：`:60-63` `from fund_fetcher import fetch_market_news, set_risk_free_rate`。**v1 的「同功能雙路徑」不成立**（`fund_fetcher.py:316` 是 re-export shim）。真問題：`CLAUDE.md` EX-PASSTHRU-1 登記的行號 `:1188` **已失效**（實際 `:961`）
- **死 import 精準命中**：`:65 backtest_turning_points`（0 呼叫）、`:71 render_mk_clock_section`（0 呼叫）、`:498 render_indicator_map`（本 Tab 0 呼叫）、`shared.colors` **恰好 14 個常數 0 引用**
- **雙向循環依賴是 4 個不是 5 個**（`tab1_macro_ai.py` 對本檔零 import）。且雙向皆為函式內 lazy import → **module graph 上是真環，但 import time 永不觸發**，屬架構氣味非執行期 bug
- **唯一真效能瓶頸**：`inflection.py:442-447` `backtest_turning_points(fred_key)` 在收合 expander body 內，`turning_points.py:366` **無任何 cache decorator** → 抓 30 年 FRED T10Y2Y 日頻 + `^GSPC` 全歷史，每次 rerun 全跑

#### 2. 具體改善優化方案

**新手友善化調整**
1. ①②③④ 四層總表**原封不動保留**（本站最成功的設計）。
2. 新增一鍵 toggle「📖 白話模式」，開啟後在每個指標卡下方以 `st.caption` 插入白話（例：「Sahm Rule = 失業率三個月平均比過去一年最低點高出 0.5 個百分點就代表衰退已開始。現在 0.23，還沒觸發。」）。文案存 `shared/glossary.py` 供全站共用。
3. `:1341-1345` HTML `title` hover 改 `st.popover`（Streamlit 1.59 可用），手機可點。

**介面排版與按鈕瘦身計畫**
1. **`:933` 與 `longterm.py:243` 二選一**（同一個清快取函式）。保留頂部那顆，子模組改 `st.caption("資料由頂部『強制重抓』統一更新")`。
2. **詳細區四時域改 `st.tabs` 或預設收合 expander** —— 直接解掉「60+ 次滾輪」。總表區維持全展開。
3. `columns(5)` 三處在窄螢幕改 2 欄。

**數據呈現與進階分析保留方式**
- **零刪除**。43 張圖、45 張卡全保留，只從「同時全開」改為「四時域分頁 / 收合」。
- ④ 可信度層的 proxy 標記與缺漏指標清單**必須留在第一屏**（這是判讀前提）。

#### 3. 程式碼重構建議

| # | 動作 | 檔案:行 | 工作量 |
|---|---|---|---|
| 1 | `set_risk_free_rate` 改 `safe_num`，`None` 則**不呼叫**並寫 stderr；同時 import `fund_service._RF_ANNUAL` 消除第三份 4.0 | `tab1_macro.py:1028-1029` + `app.py:127-130` | S 0.5h |
| 2 | **5 組雷達門檻改 import `services.risk_radar` 常數**（需 service 端先 export）；刪除所有 `# services L###` 行號註解。**特別注意 VIX 25→22、PCR 1.5→1.2 是真的要改數值，會改變畫面** | `tab1_macro.py:149-172` + `risk_radar.py` | M 2-3h |
| 3 | `backtest_turning_points` 加 `@_ttl_cache` 或帶 `_ts` 的 session stash | `turning_points.py:366` / `inflection.py:442` | S-M 2h |
| 4 | 兩處清快取 `except: pass` 改 `st.warning` + stderr，且失敗時**不要**續設 `_do_load=True` | `:947-948`、`longterm.py:249-250` | S 1h |
| 5 | `:1049-1050` 與 `ai.py:140` 缺值改 ⬜「無法判定」，不以 LOW 代替 | 2 檔 | S 1h |
| 6 | 24 處完全靜默 except 至少補 stderr（優先 `:183/:606/:728`） | `tab1_macro.py` | M 2h |
| 7 | 4 個共用 helper 下沉 `ui/components/macro_card.py`，5 個 section 改正規 top-level import | 6 檔 | S-M 3-4h |
| 8 | 刪 3 個死 import + 14 個未用色票；更新 `CLAUDE.md` EX-PASSTHRU-1 的過時行號 | — | XS |

---

### 📌 ② 💊 組合健診（`ui/tab_fund_grp_health.py` + `services/health/dividend_calc.py`）

**這是全站金額計算最集中的 Tab。**

#### 1. 現狀診斷與問題點

**資料稽核問題**

| 嚴重度 | 位置 | 問題 |
|---|---|---|
| 🔴 | `:185-190` | **`slider「吃本金閾值 %」` 是死控制項**（見 G3）。它產出的 `div_health_light_🧮` production **0 consumer**；help 承諾的判定完全沒發生 |
| 🔴 | `services/health/dividend.py:475` | `dividend_safety(total_return=tr1y, dividend_yield=adr, **nav_change=tr1y**)` — **把含息報酬當淨值變化傳**。驗算：NAV −6%、配息 8% → tr1y=+2% → `+2.0 > -5.0` **不觸發**；正確傳 −6.0 應觸發。**配息愈高、NAV 崩跌警示愈不可能出現** —— 與該警示「配息可能來自本金」的設計目的完全相反。而 `_tr1y_meta["nav_change_pct"]`（純 NAV 漲跌）**就在同一個函式的 local scope 內**（`:449`） |
| 🔴 | `services/health/replacement.py:126` | `adr = eat_result.get("annual_div_rate_pct")` — **該 key 不存在** → adr 恆 None → `grade.py:165 _score_coverage` 回 None → 規則 (b) 用的 4D 少一維，**與大表顯示的 4D 不同源**。驗算：某檔 cov=15/sh=15/tr=45/vol=55 → 大表 (15+15+45+55)/4=**32.5→F**，rule(b) (15+45+55)/3=**38.3→D** → 大表印 F、建議只給 🟡 觀察。且 `grade.py:175 _core_present` 讓**無 Sharpe 的基金 grade 恆 `—`，rule(b) 完全失效** |
| 🔴 | `:762` 等 4 caller | **換標的建議 4 條規則有 2 條靜默停用**（未傳 `holding_years`）。合併上一條 → **4 條 hard trigger 只剩 (d)**。而 caption `:776` 明確承諾「 4 規則觸發」 |
| 🟠 | `ui/helpers/fund/checkup.py:325,336` + `fund_row.py:128` | **「換匯資訊 🧮」標籤說謊**：前綴寫死 `1M TWD`，但金額用真實本金算。驗算：本金 500,000、fx=32.40 → 畫面顯示 `1M TWD→15,432 USD @ 32.40`（1M 應是 30,864）→ **一句話裡兩個差 2 倍的金額**。另 `tab:130` caption 也寫死「100 萬」，與 `number_input`（1萬~1000萬）衝突 |
| 🟠 | `dividend_calc.py:365-369` vs `report.py:156` | **線性年化 vs 幾何年化同表並排**。驗算：3 年累計 +33.10% → `3Y 年化 %`（幾何）**10.00%**、`淨值% (年化)`（線性）**11.03%**，差 1.03pp；+100%/3年 → 25.99% vs 33.33%，差 **7.34pp**。欄名都叫「年化」，兩欄 help 都沒說口徑不同 |
| 🟠 | `:918-926` caption | 宣稱「年化配息率用 **MoneyDJ 官方公布值**」，實際 adr 有 3 層 fallback。**加碼**：`dividend.py:481` 已算好 `_adr_source` 血緣，但 **production 0 consumer** —— 算了卻從不顯示（對比 tr1y 有「1Y 來源」欄照實顯示） |
| 🟠 | `dividend_calc.py:280` | **買進日 = NAV 序列第一天**（抓取視窗產物，常 5-15 年前），UI 無輸入、無 tooltip；該表 8 欄 `column_config` **全部無 `help=`**。持有年數、全期三軸、累積配息、換匯資訊全建立在這個未揭露假設上 |
| 🟠 | `dividend_calc.py:285-318` | **手續費 / 保管費 / 信託管理費完全未建模**。`費用率 %` 與 `最高經理費%` 只進評分不扣一塊錢。對境外保單基金，100 萬本金首年 1~3 萬的前收費用在「累積 TWD 配息 / 含息%」裡完全看不到 |
| 🟡 | `fund_service.py:863-866` | 配息頻率由配息間隔 auto-detect（門檻 45/100/200 天 inline），格值**無 🧮 標記**。但欄位 help 已誠實揭露「本站從實際配息記錄歸納」→ 格內像官方、tooltip 誠實 |
| 🟡 | `:356-357` | `_eats_principal_flag` 吞例外 → 回 None → 「🎯 選基金」表把「算爆了」渲染成「❓ 未知」，且 `_only_eat=True`（預設）會把它**整檔濾掉** → 計算失敗 = 該檔從進場候選消失，畫面零提示 |
| 🟡 | `:846` | `sum(float(r.get("累積 TWD 配息 🧮", 0) or 0) ...)` — KPI 加總把缺值當 0 併入分子，未揭露 |

> ❌ **v1 三條撤回**：FX 抵消（v19.449 已修）、`or 0` 偽造（v19.387 已修）、L2→L3 反向依賴（v19.413 已修）。`principal_twd` 也**不是**死參數。

**UI/UX 與操作體驗問題**

- **資訊密度遠超 v1 估計**：一次完整健診渲染 **≥14 張 `st.dataframe`**，光前 8 張就 **≈149 欄**，其中健診大表單表 **72 欄**（含一個恆為 `True`、無中文欄名、無 help 的 `ok` 欄 —— 這正是 `unified.py:266` 漏排除造成的實害）。手機實務上不可讀。
- **10 個控制項只有 1 個有 `help=`，而那一個內容不實**（死 slider）。
- **缺一句話總結**：按下健診後第一眼是新鮮度 banner + 5 個數字，不是「你這 3 檔裡有 2 檔正在吃你的本金：ACCP138、ACUSI23」。
- **🔴 缺「期末市值 / 淨結果」**：這個 Tab 的核心提問是「我拿 100 萬買這檔，結果如何？」，**只回答了一半**。`units_held_🧮` / `last_nav` / `fx_spot` / `total_twd_div_🧮` / `principal_twd` **全部已在 `row["_detail"]` 裡**，差三行乘法。驗算範例：units 3,607.97 × last_nav 9.42 × fx 32.38 = 期末市值 **1,100,542**；+ 累積配息 8,178 − 本金 1,000,000 = **淨賺 108,720**。使用者現在看得到「累積配息 48 萬」卻**看不到任何一個「我現在總共有多少錢」的絕對金額**。
- **4 個「配息率」定義並存**（yield-on-cost 全期 / 年化 / yield-on-price / 單期÷除息日NAV），分母各不相同，頁面**沒有一句話說明為什麼**。
- **標題與內容錯位**：`:453` 印「#### 📦 ③ 實際購買配息結果」後才呼叫 `_render_health_table`，而該函式先印新鮮度 banner + KPI + 整個「基金體檢表」expander。

**程式碼問題**

- **重複計算（DRY 問題，非效能問題）**：`check_eating_principal_1y_mk` **每檔 6 次**、`compute_1y_total_return` **每檔 ≥13 次**、`check_333_principle` ≈4 次、`build_health_analysis_row` 整包 2 次。全是無快取純函式；10 檔 ≈ 60 次全 NAV 序列走訪（O(n), n 常 >1000）。**無網路成本，純 CPU 浪費 + 一致性風險**。
- **cum→ann 開根公式 3 份 copy**（`tab:227-228` / `report.py` / `replacement.py`），而 `fund_service` 已有 SSOT `_annualize_cum_pct`。
- **每檔打 2 輪 MoneyDJ**：`moneydj_fetcher.py:74` 依序試 `yp010000` → `yp010001`，**只有 `complete` 才早退**（境外基金常態 `partial` → 必跑第二輪）。且每輪是**多頁抓取**不是 1 次 HTTP。10 檔 = 最多 20 輪。並行度 4（`:307`）。
- **死碼**：`_DEFAULT_CCY`（`:22`）、`ccy_hint` 參數（恆傳 `""`、函式內 0 使用）、`_process_one_fund` alias（`:282`）。
- `tab:573` `marker_color="#f0883e"` 硬編（同 figure 另兩條用 `shared.colors`）。

#### 2. 具體改善優化方案

**新手友善化調整**
1. **KPI 列上方插入一句話總結**（`st.success` / `st.error`）：
   > 「你的 3 檔中有 2 檔正在吃本金：**ACCP138、ACUSI23**。這 100 萬總共領回 **48.2 萬**配息，目前市值 **71.5 萬**，淨**賠 19.6 萬**（−19.6%）。」
2. 新增「配息率為什麼有四個數字？」`st.expander`，用一張小表對照四種分母與適用情境。
3. slider **建議移除**（而非接回），改 `st.caption(f"判定門檻：缺口 > {NEAR_DIVIDEND_WARNING_PCT}pp（SSOT）")` —— 避免給假的控制感。
4. 「吃本金燈號」欄補來源標記（顯示 `🟢 (30d 外推)` 而非只有 🟢）。
5. 「買進日」欄補 `help=`：「= 本站能抓到的最早一筆淨值日期，不是你的實際買進日」。

**介面排版與按鈕瘦身計畫**
1. 加 `st.radio("顯示模式", ["精簡（結論）", "完整（全欄）"], horizontal=True)`。精簡模式 6 欄：代號 / 基金名 / 燈號 / 累積配息 / **期末市值** / **淨結果**。
2. 修正「③ 實際購買配息結果」標題與內容錯位。
3. 本金 `number_input` 加 `help=` 說明作用範圍（在 checkup 修好前至少誠實揭露）。
4. render 階段補進度提示（10 檔時目前 UI 長時間空白，`prog.empty()` 在抓取階段就結束）。

**數據呈現與進階分析保留方式**
- 149 欄**全數保留**在「完整」模式。
- **新增 3 欄**（輸入全部已在記憶體）：`期末市值 TWD 🧮` / `淨結果 TWD 🧮` / `淨結果 % 🧮`。
- 線性年化改幾何後，help 註明「配息採單利攤平、淨值採幾何年化」。

#### 3. 程式碼重構建議

| # | 動作 | 檔案:行 | 嚴重度/工作量 |
|---|---|---|---|
| 1 | `dividend_safety` 的 `nav_change` 改傳 `_tr1y_meta["nav_change_pct"]`（值就在 local scope） | `health/dividend.py:449,475` | 高 / **S 0.5h** |
| 2 | `replacement.py:126` 改用正確 key 或直接吃已算好的 adr；補測試斷言 rule(b) 的 4D 與大表同源 | `health/replacement.py` | 高 / S 1h |
| 3 | 4 個 caller 傳 `holding_years`（值已算好） | `tab:762` / `fund_batch.py:212` / `unified.py:409` / `tab2:1273` | 高 / S 1h |
| 4 | slider 移除 + caption 顯示 SSOT 常數 | `tab:185-190` | 高 / S 1h |
| 5 | `build_checkup_dataframe(..., principal_twd=)` 加參數一路透傳；`fund_row.py:128` 改動態 f-string；`tab:130` caption 改吃變數 | 3 檔 | 高 / 0.5d |
| 6 | 新增期末市值/淨結果 3 欄 + 頂端白話總結 + 精簡模式 radio | `fund_row.py` + `tab` | 中高 / 1.5d |
| 7 | `dividend_calc.py:365` 改幾何年化；同步更新兩欄 help | `dividend_calc.py` | 中 / 1d（含回歸） |
| 8 | `_adr_source` 接出到「配息來源」欄（血緣已算好只差顯示） | `unified.py` + `columns.py` | 中 / S |
| 9 | `unified.py:266` 補排除 `"ok"`（消除恆 True 幽靈欄）；並把 `_unified_columns` 收成單一實作 | `unified.py:151-163,264-273` | 中 / M |
| 10 | `:356` `_eats_principal_flag` 補 stderr + 讓「計算失敗」與「未知」在篩選器可區分 | `tab:356-357` | 中 / S |
| 11 | cum→ann 統一走 `fund_service._annualize_cum_pct`（消 3 份 copy）；刪 3 處死碼 | 4 檔 | 低 / S |

---

### 📌 ②-B 📦 批次分析（`ui/tab_batch_analysis.py` 401 行 + `unified.py` 445 行）

#### 1. 現狀診斷與問題點

**資料稽核問題**

| 嚴重度 | 位置 | 問題 |
|---|---|---|
| 🔴 | `unified.py:403-422` + `:436-437` | **部分失敗被標「✅ 成功」**。①健康分析失敗 → **13 欄留白**；②配息失敗 → **7 欄**；③σ/風險/失敗 → **22 欄留白 + 7 欄降級成 ⬜**（看起來像「這檔本來就判不出」）。stderr 在 Streamlit Cloud 上使用者看不到，UI 端零揭露。**對照：健診 Tab 對同一失敗會 `st.caption` 明講「整組計算失敗，不是資料沒有」** |
| 🔴 | `:35` + `:93-94` | `_CODE_RE = ^[A-Z0-9]{3,20}$`，不符即無聲 `continue` —— 無計數、無警告。`0050.TW`、`B-07`、2 字元代號被靜默吃掉。使用者上傳 420 行看到「解析到 380 檔」只會以為自己重複了 |
| 🟠 | `unified.py:443` | **`淨值新鮮度` 凍結說謊** —— 建列當下算好存進 checkpoint，讀回時**不重算**。30 天前的存檔仍顯示「🟢 1d」。而 `columns.py:409` 的 help 白紙黑字寫「**今天**（台北時間）距離上面那個淨值日期幾天」= 對讀回存檔是錯的敘述 |
| 🟠 | `unified.py:168` | **CSV 無抓取時間**。`fund_row.py:237` 確實回 `_fetched_at`（上游 `fund_orchestration.py:677` 有寫入，非空），被底線前綴過濾掉。`:441-442` 已示範顯式撈回 `_nav_date` |
| 🟠 | `:121` | **續跑產生混齡 CSV**：`_K_RUN_AT` 每輪開頭覆寫，但 rows 保留舊輪結果；checkpoint 無 per-row 時間戳 → 混齡不可事後還原 |
| 🟡 | `unified.py:371` | `principal_twd=1_000_000.0` 寫死，批次 UI 無欄位可改（健診有 `number_input`） |
| 🟡 | `:58-61` | 舊 schema 提示只看「淨值新鮮度」。**v1 說「零提示」不成立** —— 該欄是 2026-08-06 最新欄，晚於所有策略欄 → 缺後加欄的舊存檔**必定也缺它**，提示會觸發。真問題是**訊息低估**（只講 2 欄，實際可能缺 9 欄）+ 單欄當世代旗標的設計脆弱 |

✅ **整檔失敗的處理是全專案最誠實的一段**：`_blank()` 全設 None → `to_numeric(errors="coerce")` → CSV 空白不是 0；`:306-309` caption 明講「**不會偷偷丟掉、也不會填假數字**」。0 個 `fillna` / 0 個裸 `except:` / 0 個 mock。

**UI/UX 與操作體驗問題**

- **75 欄**（實測：4 + 2 + `_UNIFIED_FRONT` 51 + `remaining_base` 18）。而註解**四處全錯**：`:4`「40 欄」、`:152`「40 欄」、`:314`「48 個中文欄名」、`columns.py:6`「48 個」，另 `STATE.md:372` 也寫 40 → **低報 36%~47%**。
- **`help=` 出現 0 次**（7 個控制項全裸）。欄位 tooltip 全來自 `columns.py`（品質很高，有 `test_help_plain_language.py` 把關），但**控制項本身**零說明。
- **無代號數量上限**（健診有 `_MAX_CODES=10`）；貼 5000 行照跑。
- **無中止按鈕**；進度只有 `i/total`，**無 ETA、無即時成功/失敗計數**。
- **摘要只有 3 個 metric**，但表裡已有「吃本金燈號」「4D Grade」「基期」「策略燈號」「淨值新鮮度」可彙總（健診有 5 個 KPI）。
- **死設定**：`columns.py:334` 的 `"吃本金燈號 (1Y·)"`（`·` 兩側無空格）與實際欄名 `"吃本金燈號 (1Y · )"` 不符 → **永遠 0 consumer**。

**程式碼問題**

- **400 檔序列跑**（`:141-146` 單純 for），而 ≤10 檔的健診是 `ThreadPoolExecutor(max_workers=min(n,4))`。
  > ⚠️ **但「序列跑」目前是唯一的 rate-limit 保護**。實測估算：每檔 6-25 requests（失敗檔走完整 fallback chain 貴 2-3 倍），400 檔 ≈ **2,400-10,000 次請求**壓縮在 30-40 分鐘 = **1-5 req/s 持續**打向 moneydj.com。`CLAUDE.md §4.6` 已載明保單子網域已知 403 → 403 檔請求量再放大，形成正回饋。**直接改 4-worker = 速率 ×4，且 `signal_thresholds.py` 記載你 2026-08-11 拍板「不增加對 MoneyDJ 的請求數」。此項必須你拍板。**
- **checkpoint O(N²)**：`_persist` 每檔呼叫 `bc.save`，`save` 每次全量 dump。400 檔 → **Σ(1..400) = 80,200 次 row 序列化、~100-140 MB 累計寫入、400 次 mkstemp+rename**。`list_recent` 為取 4 個 meta 欄而 `json.load` 整份檔案（最多 10 × 1.2MB），且在「尚未輸入代號」畫面每次 rerun 都跑。
- **run_id = 整份清單 hash** → 清單增刪一檔 → rows 清空重跑 30-40 分；且**舊 checkpoint 永不回收**（`limit=10` 只限制顯示，無 retention/GC）。
- **`:335-336` `render_rotation_section_from_df(df)` 裸呼無 try**，而它上下兩個同性質 section（`:340-343`、`:347-350`）都包了 try。
  > ⚠️ v1 說「`app.py` 的 `with tab_batch:` 無 try 隔離（對照 macro/manage 都有）」是**框架誤導** —— 7 個 tab 只有 2 個有隔離，批次是多數派。真正可證明的不一致是本檔內部這一處。
- **欄序推導寫兩遍**（`unified.py:151-163` vs `:264-273`），且**已造成實害**：`:266` 漏排除 `ok` → 健診大表多一個恆 True 幽靈欄。
- `df.to_dict("records")` 呼叫兩次未複用（`:341`、`:348`；健診端 `:952/:959` 同款）。
- **`batch_checkpoint.py:121-122` `except: continue` 是 5 個檔案中唯一完全靜默的吞例外**。
- 部分 `print` 走 stdout 非 stderr（`batch_checkpoint.py:92`、`fund_row.py:143/205`）→ Streamlit Cloud log 撈不到。

> ⚠️ v1 說「post-merge 執行順序不同有風險」—— 順序屬實但**風險不成立**：三個 compute 內部全走 `safe_num`/`_sigma`/`_num` 容錯轉型，上游回的本來就是 float/None。降級為「重構債」。

#### 2. 具體改善優化方案

**新手友善化調整**
1. 頂端 3 metric → 8 metric：檔數 / ✅成功 / **⚠️部分成功** / ❌失敗 / 🔴吃本金 N 檔 / 🔴策略燈號 N 檔 / 🔴疑停售 N 檔 / 平均 4D Grade。**資料都已在 df 裡，成本極低**。
2. 7 個控制項全補 `help=`（尤其「重試失敗檔」與「清除重來」的差別）。
3. 進度列補 ETA + 即時成功/失敗計數 + 一顆「⏸ 停止」按鈕。

**介面排版與按鈕瘦身計畫**
1. 75 欄加「精簡 / 完整」切換。精簡預設 12 欄。
2. 三個下游區塊的局部結論往上提一行到頂端 KPI 區。
3. 控制項本身無冗餘，不需瘦身。

**數據呈現與進階分析保留方式**
- 75 欄全保留在「完整」模式與 CSV。
- CSV 補 `抓取時間` 欄；`淨值新鮮度` 改**顯示時重算**而非存 checkpoint。

#### 3. 程式碼重構建議

| # | 動作 | 工作量 |
|---|---|---|
| 1 | 三段 `except` 收集 `_degraded` list → `狀態="⚠️ 部分成功"` + `備註="以下欄組計算失敗留白：…"`；`batch_column_config()["狀態"]` help 補三態；`:424-443` 包進 try | S ~30 行 |
| 2 | `_parse_codes` 回 `(codes, dropped)` + `st.warning` 列出被忽略行；加 `_MAX_CODES_BATCH`（建議 500） | S |
| 3 | `:335-336` 補 try（照抄 `:340-343`）；`batch_checkpoint.py:121` 補 log | XS |
| 4 | `_persist` 改每 10 檔或每 T 秒落地；`save` 額外寫 `.meta.json`，`list_recent` 只讀 meta；加 checkpoint 保留策略 | S-M |
| 5 | checkpoint 改 **per-code**（`data_cache/batch/rows/<CODE>.json`），run_id 僅記清單成員 → 天然支援增刪 | M |
| 6 | 欄序推導合一（`_unified_columns` 為唯一實作 + 參數化），順帶修 `ok` 幽靈欄 | M |
| 7 | **需你拍板**：並行化 + `infra/proxy.fetch_url` 加 per-host token bucket（moneydj.com ≤1 req/s）+ worker 數 UI 可調（預設 1） | M-L 1d |
| 8 | `_fetched_at` 撈回 CSV（需同步加 column_config，因 `test_grp_health_audit_20260806.py:133` 強制每欄要有）；`淨值新鮮度` 改顯示時重算 | S |
| 9 | 修正 4 處欄數註解（40/48 → 75）；`columns.py:334` 欄名補空格；`to_dict` 複用 | XS |

---
### 📌 ③ 🔍 個基深掘（`ui/tab2_single_fund.py` 2450 行）

#### 1. 現狀診斷與問題點

**資料稽核問題** — 這一檔的資料誠實度是全站最高的

✅ 先講好的：**0 個 `fillna` / 0 個 `ffill` / 0 個裸 `except:` / 0 個 mock**（case-insensitive 全檔掃描）。缺值一律 `—`。6 處 `dropna` 全在繪圖路徑剝 rolling 頭部 NaN。**TER 同類均值假資料已刪除**，`:1656-1669` 留 14 行說明（「無資料源、無抓取時間、無樣本數…全都是憑印象填的常數」）+ `:1691-1697` 面向使用者的誠實留白說明。

| 嚴重度 | 位置 | 問題 |
|---|---|---|
| 🔴 | `:1926-1934` | **手動匯率 `value=32.0`**。三條污染路徑：(a) `:1942/:1988/:2127` 印「1 JPY = 32.0000，**手動**」（至少有 tag）；(b) **`:2009/:2024/:2149/:2165` 的「📐 完整計算公式」`st.code` 把 `32.0000` 當裸數字印進算式（`= 1,000,000 ÷ 32.0000`），該區塊完全沒有「手動」字樣** ← 最像真值；(c) `:1966` 月配息(TWD)、`:2106` 1Y 後預估市值 **兩個 metric 用假 FX 出數卻零旗標**。JPY 真值 ≈0.21 → **152 倍誤差** |
| 🔴 | `:1066-1067`、`:1138-1139` | `except: pass` 讓 **HWM σ 位階卡**與 **4D 健康總覽卡**整張靜默消失。同檔 24 個 except 有 4 種處置（僅 stderr 8 處／僅 caption 2 處／兩者都有 1 處／完全靜默 8 處）→ **不一致**。**且這兩處被假綠測試背書**（見 G2） |
| 🔴 | `:2003` → `:2057-2058` | **AI 快照缺整段投資試算**：income stash 的 `try:`（縮排 32）被關在 `if _has_rec:`（縮排 28）內 → 走年化估算 fallback 時 stash 不寫 → `:2370 if _calc_stash:` 整段跳過。**放大點**：`:2432-2442` 的 `sections=[...]` 是**靜態清單**，永遠含「投資試算」→ **AI 被指派寫一個快照裡零資料的章節 = 幻覺入口**。**不對稱**：累積型分支 `:2201-2215` 的 stash 是無條件寫入的 |
| 🟠 | `:1483-1488` | Sharpe 分級 `0.5` 寫死。SSOT 在 `services/health/grade.py:56-68 _score_sharpe`（1.5/1.0/**0.5**/0）。**同檔 `:431-436` / `:1366-1371` 已有正確樣板**（import `MIN_OBS_*` 再 f-string 渲染），這條是漏網 |
| 🟠 | `:1113-1114` vs `:1309` | **同一張卡兩組 cutoff**：因子格用 75/60/45/30、總分格用 `GRADE_CUTOFFS_4D`(80,65,50,35)。**分數 78 → 總分格淺綠(B)、因子格深綠(≥75)**，同一個數字兩種顏色。且 `:1309` 的文案自稱「SSOT v19.177」卻是 inline literal，**沒有 import `GRADE_CUTOFFS_4D`** |
| 🟡 | `:142` / `:145` | 3-3-3 門檻 `3.0` / `0.07` 重刻。**但 `check_333_fund` 的那兩個值是 keyword-only signature default，不是可 import 的模組級常數** → 「改成從 SSOT import」目前**無標的**，得先在 `shared/signal_thresholds.py` 新增常數。現值一致，屬潛在漂移非現存 bug |
| 🟡 | `:528-530` | `st.columns(len(_p_perf))` 開 N 欄（wb01 常 6-7 鍵）卻只填前 4 → 空欄 + 版面壓窄 |
| 🟡 | `:1613` | 講義卡寫死「2%」，而 `NEAR_DIVIDEND_WARNING_PCT=2.0` **在 `:23` 已 import 卻沒用** |

> ❌ **v1 兩條修正**：`compute_1y_total_return` 雙來源**整條撤回**（`macro_helpers.py` 是 12 行 shim，同一 function object）；`tdcc_search_fund` **已在 `CLAUDE.md:518` 登錄**（真問題只是行號 `:147` 過時 + 檔內缺 `# EX-PASSTHRU-1` 註解）。
> ⚠️ 真正未登記的只有 `:2239` 的 `infer_asset_class` / `filter_news_by_asset_class`，**但兩者是零 I/O 純函式**（`news_repository.py:438-467` 關鍵字比對），§8.2 該規則「cache 才能集中」的立論在此不適用 → **建議登例外表而非建 facade**。
> 附帶：`filter_news_by_asset_class` docstring 明寫「過濾後若為空則回原清單」→ `:2425-2427` 餵 AI 的新聞**可能與本基金資產類別完全無關且無旗標**（§1 邊緣）。

**UI/UX 與操作體驗問題**

- **🔴 搜尋→分析操作斷點**：`:348-353` 搜尋結果只 `st.info("💡 代碼：**{fc}** → 在上方輸入框貼入代碼即可分析")` —— 要使用者手動複製、捲回頁首、貼上、再按分析。而 `:256` 的 widget 有 `key="mj_url_input"`，**技術上一鍵可通**。
- **資訊密度**：`.metric(` **27 個 call site**，但**單次實際渲染最多 16 格**（配息型完整視圖）或 7 格（partial）—— v1 用 27 當密度論據會失真。**卡片實測 14 張**（13 HTML 卡 + 1 `st.container(border=True)`）不是 15。3 張 plotly、44 個 caption、6 個 expander、31 處 `unsafe_allow_html`。
- **🔴 手機 4 欄 grid**：`:1131-1132` `repeat(4,1fr)` 無 media query，4D 總覽卡（本頁最重要的結論卡）在窄螢幕擠成 4 條窄柱。
- **9 個控制項只有 2 個有 `help=`**；兩顆重操作按鈕（`:1739` 抓個股新聞最多 6 次 Google News、`:1795` 三率穿透最多 10 次 yfinance 序列）分散在兩個 expander 且無「已抓過」提示。
- **名詞缺口**：`mdd` / `div_coverage` explainer 字典已寫好卻沒被 `:1508` 呼叫（見 G7）；另 Sortino / Calmar / 3Y-5Y 年化 / 追蹤誤差 TE 零解釋。
- **inline magic 約 30 處**，其中 3 個與 SSOT 直接衝突（`:1113-1114` / `:1309` / `:1483`）、1 個已 import 卻沒用（`:1613`）。
- **繞過 `shared.colors` 的 inline hex/rgba 14 處**（`#16a085`/`#c0392b`/`#586069`/`#8b949e`×5/`rgba(33,150,243,*)`×3/`#ffd600`/`#0d2a0d`/`#1a3a1a`/`#0a0e14`），而檔頭 `:20` 已 import 40 個色票常數。

**程式碼問題**

- **🔴 `record_fund_nav_point` 同步阻塞在關鍵路徑**（`:316`，在 `st.spinner` 內、「🚀 分析」點擊路徑上）。三個放大因子：
  1. **不是單點是整段** —— `nav_history_hook.py:100 _extract_points` 遍歷 `series.items()` 全部，首次分析 2000 點基金 → 一次 append 最多 2000 列
  2. **每次都全表讀** —— `nav_history_gs.py:187 ws.get_all_values()` 拉整張 `nav_history`（所有基金所有日期）做 `(code,date)` 去重，**成本隨累積逐日惡化**
  3. 雙層 `except` 吞掉（`:317-318` + helper 內一層）
  緩解只有 `_nav_hist_written` 集合避免同 session 重寫，**首次點擊必付全額，每換一檔基金重付一次**。
- **重複計算是 DRY 問題不是效能問題**：`compute_1y_total_return` 6 個 call site（實跑 ≤5）、`_resolve_adr_with_fallback` 5 個、`calc_hwm_sigma_levels` 2 個。三者都是純 dict 查找或 ≤252 點 pandas，成本近乎 0。**真風險是 payload 不一致** —— `:2087` 的註解正記錄了曾發生「某 call site 漏帶 `series`/`perf_source` 導致同頁兩個 1Y 數字不同」的事故。
- `compute_1y_total_return` 在檔內走**兩種 import 寫法**（`:1077` 新式 vs 5 處舊式 shim）→ 純風格不一致。

✅ `:264-269` v19.353 移除了「每次按分析都 `clear_all_caches()`」，是本檔最大的效能修正。

#### 2. 具體改善優化方案

**新手友善化調整**
1. **一行改動補兩個最重要的名詞**：`:1508` → `render_metric_explainer(["sharpe","sigma","alpha","beta","mdd","div_coverage"])`
2. explainer 字典補 `sortino` / `calmar` / `tracking_error` / `annualized_return`；`:1345-1347` 補 `help=`
3.  3-3-3 那格 metric 加 `help=` 直接寫出三條件（不要求捲到 `:2225`）
4. 手動匯率模式下，**在「📐 完整計算公式」區塊頂端加一行紅字警語**，並讓 `月配息(TWD)` / `1Y 預估市值` 兩個 metric 的 label 帶 ⚠️

**介面排版與按鈕瘦身計畫**
1. **修掉搜尋→分析斷點**：selectbox 旁加「用這檔分析」按鈕（`st.session_state.mj_url_input = fc` + `st.rerun()`）
2. `:1131-1132` grid 改 `repeat(auto-fit, minmax(120px,1fr))`
3. `:528` 改 `st.columns(min(len(_p_perf), 4))`
4. 控制項只有 9 個且無冗餘 —— 真正的問題是**資訊密度**：建議 ③風險指標 / 💸近期配息 / TER / 進階指標 四區改 `st.tabs`（①②④ 保持全展開）

**數據呈現與進階分析保留方式**
- 27 個 metric、14 張卡、3 張圖**零刪除**
- ①② 兩區 + 4D 卡 + 吃本金橫幅維持第一屏全展開（決策核心）
- ③ 之後改分頁收納

#### 3. 程式碼重構建議

| # | 動作 | 檔案:行 | 工作量 |
|---|---|---|---|
| 1 | 手動匯率預設改 `value=None`（強制填）或帶入最近成功 FX 快取；`_fx_manual` 旗標貫穿到 4 個 `st.code` 公式區塊與 2 個 metric | `:1926-1934` + `:2009/2024/2149/2165` | S 1h |
| 2 | 兩處 `except: pass` 改 `print(stderr) + st.caption`（照 `:622-626` 樣板）。**同批必須改 `tests/test_review_fixes_v19_346.py:142-151` 的檢查邏輯**，否則守門測試仍是空的 | `:1066/:1138` + 1 測試 | 高 / S 1h |
| 3 | `:2057-2082` 反縮排到 indent 28（修 AI 快照缺段）；或更穩：把 stash 寫入移到 `if/else` 之外 | `:2003-2082` | S 0.5h |
| 4 | `:1508` 一行 + explainer 字典補 4 條 + 3 處 `help=` | 2 檔 | **S 1h（最高 ROI）** |
| 5 | 搜尋結果加「用這檔分析」按鈕；grid 改 auto-fit；`:528` 改 min(…,4) | `:353/:1131/:528` | S 1-2h |
| 6 | `:1113-1114` 與 `:1309` 統一 import `GRADE_CUTOFFS_4D`；`:1483` import `grade.py` 的 Sharpe 門檻；`:1613` 改用已 import 的 `NEAR_DIVIDEND_WARNING_PCT` | `:1113/1309/1483/1613` | S-M 2h |
| 7 | `record_fund_nav_point` 改背景執行或至少加「僅寫最新 N 點」上限；`get_all_values()` 改 `get(range)` 只讀該 code 區段 | `nav_history_hook.py` + `nav_history_gs.py` | M 1d |
| 8 | `:2239` 補 `# EX-PASSTHRU-1` 註解並登記 `CLAUDE.md §8.2.A`；`:25-27` 補註解 + 更新 CLAUDE.md 過時行號（`:147`→`:25`、`fetch_stock_news :1300`→`:1720`） | 2 檔 | S |
| 9 | 14 處 inline hex 收 `shared.colors`；先在 `signal_thresholds.py` 新增 3-3-3 常數再讓 `:142/:145` import | 多檔 | 低 / M |

---

### 📌 ④ 📊 配置 & 帳本（`ui/tab3_portfolio.py` 2953 行 + `ui/tab3_t7_ledger.py` 2947 行）

**全站最複雜、按鈕最多、問題最多的 Tab。**（v1 中「t7 有 1706 行」的說法是錯的，實際 2947。）

#### 1. 現狀診斷與問題點

**資料稽核問題**

| 嚴重度 | 位置 | 問題 |
|---|---|---|
| 🔴 | `t7:1731-1739` | **借用基金憑空造值 `NAV=10.0` / `FX=31.0`**。來源缺 series/avg_nav/fx_avg 時建立**可落帳**的買方候選（`:1859-1867` merge → `:2207-2219` 真的落帳）。且與 `_FX_FALLBACK["USD"]=32.0` **兩個不同的硬編 USD 匯率** |
| 🔴 | `t7:322-326` → `:359-360` → `:2610/2634/2725` | `_FX_FALLBACK` 12 幣別硬編匯率，流進「組合當前市值」KPI。**帳本表「最新 FX」欄 `:2666` 無任何估算旗標，而 `_T7_SNAP_COL_CONFIG` 的 help 寫「最新即時匯率」= 直接說謊** |
| 🔴 | `t7:451-454` | 雲端寫入失敗被吞，`:459-465` `st.success` 完全不提同步狀態。**v1 說「兩處」高估** —— ⚡按鈕路徑（`:632/:637`）其實是**正確的**（有接回傳訊息）。只有自動估算路徑這一處，且 C 分頁 `:2468` 有正確寫法可照抄 |
| 🔴 | `t7:1530-1570` | B 分頁 **% 模式檔無 NAV/FX 前置過濾**（單位模式檔 `:1479-1481` 有）→ NAV/FX=0 時不 subscribe、不寫 Sheet，但 `:1555` **無條件** append 顯示「應買 TWD」，且**無警告列出被跳過的檔** |
| 🔴 | `t7:1069/1082/1270/1387/1455/1700/2005/2006/**2116**` | **emoji 前綴當狀態判斷共 11 處**。其中 `:1270`/`:1455`/`:2116` 決定「模擬 vs 真寫入主帳本」—— 選項字串 `"💡 暫存為方案（不動主帳本）"` **改一個字 → `startswith("💡")` 失敗 → 靜默走 else = 真的寫進主帳本 + 寫 Google Sheet**。全檔風險最高的一條 |
| 🔴 | `t7:1177/1184/1190/1219/1269/1498` | **6 個 `st.stop()` 在分頁內**。Streamlit `st.stop()` 中止**整個 script run** → 使用者在 A 分頁忘填金額，`:2478` 帳本面板、`:2786` AI 區、以及 `app.py` 中 Tab④ 之後的**所有分頁全部空白** |
| 🟠 | `t7:936-947` vs `:2634` | NAV/FX 抓不到時，「方案比較表」退回**成本**（損益恆 0）、「帳本表」歸 **0**（報酬 −100%）→ **同一份資料兩套相反的缺值語意** |
| 🟠 | `t7:599/605/627` vs `:424-435` | 「⚡ 自動估算填入」按鈕**完全沒吃 `invest_date`** → 成本 NAV = 今日 NAV → P&L 恆 0。而另一條自動路徑已修正為用投資日期當天 NAV。**同檔兩條路徑一修一未修** |
| 🟠 | `t7:649` / `:1464` | 幣別未正規化就寫 ledger（`str(...).upper()`，中文「美元」upper 後仍是「美元」）。同檔 `_norm_ccy` 在其他 8 處都用了，**只有這 2 處漏網**；且 `:774` 直接 `_LedT7(...)` 建構，不經 `_ledger_for` → `:374-379` 的補救碰不到 |
| 🟠 | `portfolio:1874-1877` | `ffill` 有計數但 **(a) `print` 走 stdout 非 stderr、(b) UI 完全無揭露**。且 `portfolio_service.py:718` docstring 明寫「**禁止 ffill 偽造**週末值」→ 同一份資料兩套規則 |
| 🟡 | `t7:439-446` vs `:773-775` | 成本 SSOT 定義相反（自動路徑 units round 後回推金額 vs 手動「invest_twd 是 source of truth」）。**但實際誤差 <0.02 TWD**，屬 SSOT 問題非金額問題（v1 隱含的「可觀差距」不成立） |
| 🟡 | `portfolio:1-18` | docstring **五項全過期**：v18.128（實際 v19.449）、3897 行（實際 2953）、T6（**已不存在**）、T7（已抽到獨立檔）、「6 個 tab」（`:404` 自己寫 5 分頁） |

✅ **兩檔 `fillna` 皆 0 處**；19 處 `dropna` 全為讀取端 guard。
✅ **權重無 100 倍誤差風險**。但 v1「全站一致 0~100 且一律 /100.0」的前提**不成立** —— 實際三種語意並存：(a) 率值 0~100 一律 `/100.0` ✅、(b) `core_pct` 展示用從不除、(c) `_weights` 是**原始 TWD 金額**由 `portfolio_service.py:727` 內部歸一。**各自正確**。
✅ 跨幣別 switch 邏輯正確（`:2243-2270`），買方匯率為 0 時 `raise ValueError`，且有守恆檢查。
✅ `portfolio:2577-2634` `_DEFAULT_PRINC` 有完整揭露鏈 —— 硬編碼常數的正確做法。

**UI/UX 與操作體驗問題**

**🔴 按鈕重複是全 App 最嚴重的：**

| 重複組 | 位置 | 說明 |
|---|---|---|
| **3 顆「📡 載入」** | `portfolio:1412` / `:1623` / `:2252` | 3 個不同 alias 綁**同一個** `batch_load_unloaded_funds()`。`:1626` 的 help 自承「跟頂部同效果」 |
| **3 顆「🔐 用 Google 登入」** | `:717` / `:907` / `:1008` | 各自重建 URL，且**三處都被 `except: pass` 包住** → 生不出 URL 時畫面什麼都不出現，使用者只看到「請至左側 sidebar」卻連按鈕都沒有 |
| **3 處「請至左側 sidebar 登入」** | `:708` / `:898` / `:1001` | **下一行就是快捷登入 button**（v19.296 加的），指路句沒跟著更新。另有 3 處變體（`:738/:778/:942`） |
| **3 組「落帳目標 + 方案名稱」** | `t7:1158/1164`、`:1430/1435`、`:2071/2077` | A/B/C 分頁各一組完全相同，**只有 A 有 help** |
| 死指標 | `portfolio:894` | 「請至**下方 expander** 設定」—— OAuth wizard 在**同一個 expander** 的 `:1014-1102` |

- **45 顆按鈕只有 17 顆有 `help=`（38%）**；**破壞性操作 7 顆中只有 2 顆有 help、0 顆有二次確認**（`t7:2766`「🗑️ 重置帳本」單擊即清空全部持倉、`portfolio:1154`「🚀 升級到 v2」、`:1371`「🗑️ 刪除此列」、`t7:740`「💾 套用為起始部位（**覆蓋** T7 帳本）」）
- **表格 help 兩極**：`t7:76-129` `_T7_SNAP_COL_CONFIG` **17 欄每一欄都有公式說明**；但 `t7:1555-1570` B 分頁 11 欄與 `:2346-2374` C 分頁 15 欄**零 column_config、零 help**
- **RWD**：`t7:663` **6 欄** × 每檔一列（19 檔 = 19 組）、`t7:2723` **6 欄**（5 metric + 重置鈕擠同排）、`portfolio:611` 5 欄
- **SA-only 部署被鎖住**：`portfolio:1124 if _oauth_configured and _sheet_id:` → 純 Service Account 部署**永遠看不到 v2 schema 偵測/升級/編輯 UI**，即使 `_t3_sheet_client()` 明確支援 SA 讀 v2 sheet（`:168-170` 註解自承）

✅ **白話文說明是這個 Tab 的強項**：`:1789-1798`「💡 這四格的基數」、`:1933-1941`「**它不是你戶頭現在的錢**」、`:1884-1888` 圖表改名「淨值成長模擬曲線」並在註解說明理由、`t7:2769-2783` KPI vs 表格差額來源說明。

**程式碼問題**

- **🔴 OAuth client 取得 6 條路徑**，其中**三步序列逐字複製 4 份**（`portfolio:2141-2146`、`t7:246-251`、`t7:488-493`、`t7:822-827`），只有 `_t3_sheet_client()`（`:171-216`）實作 **SA-first**。
  **實質後果**：`portfolio:2135-2149` 批次加入路徑是**純 OAuth gate** → SA-only 部署 `_toks_b=None` → `_client_b=None` → `:2184 if _pid_b and _client_b:` 恆 False → **批次加入的基金靜默不寫回 Sheet，摘要也不顯示，使用者完全無感**。
- **🔴 `render_t7_section()` 單一函式 2798 行**（佔全檔 94.9%）、**19 個內部函式**、**最深縮排 13 層**（52 空格，73 行落在此深度）。
- **逐列寫 Sheets 無 batch**：`t7:495-501` 雙層迴圈 `append_ledger_row`，每列 = 1 次 Sheets write API（`ledger_repository.py:163-165`）。**v1 把此項歸在 `tab3_portfolio.py` 是錯的**；portfolio 的同型問題在 `:2151-2203`（`upsert_fund_in_policy` 逐檔）。
- **白建的 cache 沒被用**：`t7:1275` `_t7_build_navfx_cache()` 對全部基金預抓，`:1286` 迴圈內仍 `_latest_nav_fx_t7` 重抓再覆寫 → **整輪預抓形同純浪費**。C 分頁 `:2151/2208` 是正確的 cache-first 寫法。
- **兩檔 ~77 個 `except`，寫進 stderr 的只有 3 個（3.9%）**。
- **顏色 SSOT 違規 17 處**，其中 `portfolio:532-536`（重疊度 5 級語意色階）與 `:2521-2522`（`rgba(244,67,54,*)` = 已 import 的 `MATERIAL_RED` 的 RGB）影響資料判讀。
- **新發現**：`t7:1553` 讀 `_ann_acc` 但它定義在 `:1572`（靠閉包晚綁定僥倖成立）；`_bweights`/`_wn` 變數名跨 B/C 分頁重用（執行路徑互斥才沒炸）；`t7:995-1008 _t7_run_in_scenario` **0 caller 死碼**。

#### 2. 具體改善優化方案

**新手友善化調整**
1. B/C 分頁兩張無 column_config 的表，照抄 `_T7_SNAP_COL_CONFIG` 的 help 品質補齊
2. `_FX_FALLBACK` 生效時該列加 ⚠️ + `help="此列使用估算匯率，非即時報價"`；同步修正「最新 FX」欄的說謊 help
3. `t7:2766` 「🗑️ 重置帳本」加 `st.checkbox("我確認要清空整本帳本")` 才 enable；`t7:740`「覆蓋」按鈕同理

**介面排版與按鈕瘦身計畫**（本次瘦身重點）
1. **3 顆載入鈕 → 1 顆**：保留 `:2252`（在「加入與管理基金」區內符合動線），`:1412`/`:1623` 改 `st.caption` 指路
2. **3 顆登入鈕 → 1 顆**：只保留 `:1008`；且**移除三處 `except: pass`**（登入 URL 生不出來必須說）
3. **移除 `:708/:898/:1001` 的「請至 sidebar」文案**（登入鈕就在旁邊）
4. **修正 `:894`** 為「請展開下方『🧙 OAuth Client 設定引導』」
5. T7 三組重複的「落帳目標 + 方案名稱」抽成單一 helper（同時解掉「只有 A 有 help」）
6. **保單管理 expander（800 行）改巢狀 `st.tabs`**：`帳本 / 認證 / Schema / 進階工具`

**數據呈現與進階分析保留方式**
- 所有圖表、KPI、健診表、方案比較表**零刪除**
- T7 的 A/B/C 三分頁結構保留（正確的資訊架構）
- 「淨值成長模擬曲線」與「這四格的基數」說明**必須保留**，是本 Tab 最有價值的防誤讀設計

#### 3. 程式碼重構建議

| # | 動作 | 檔案:行 | 嚴重度/工作量 |
|---|---|---|---|
| 1 | **刪 `t7:1091` 一行** → 修復死掉的「🎯 目標單位數」selectbox（同時驗證 `:1135`/`:1224` 兩分支恢復後正確） | `t7:1091` | 高 / **5 分鐘** |
| 2 | 11 處 emoji `startswith` 改語意 key + `format_func`（優先 `:1270/:1455/:2116` 三處決定寫入主帳本的） | `t7` | 高 / M 3h |
| 3 | 6 個 `st.stop()` 改 `st.error(...) + return`／旗標 | `t7` 6 處 | 高 / M 2h |
| 4 | `t7:1734/1739` 移除 NAV=10.0/FX=31.0 造值，改「拒絕加入並列出缺哪些資料」 | `t7:1731-1739` | 高 / 2h |
| 5 | `t7:451-454` 接回 `_t7_save_snapshot_to_sheets()` 訊息（照抄 `:2468`）；`portfolio:1635` 改 `st.warning` + print | 2 處 | 高 / 1h |
| 6 | `t7:1551-1570` 移進 `:1535` 的 `if` 內，`else` append「⬜ NAV/FX 缺 — 未落帳」；`f"應買 {_ccy}"` 改固定欄名 + 獨立幣別欄 | `t7:1530-1570` | 高 / 0.5d |
| 7 | AI snapshot 改 lazy（按鈕 callback 內才組）；持倉健診加 session 快取或「🔄 重新計算」按鈕；`_latest_nav_fx_t7`/`fetch_usdtwd_frame` 加 `@st.cache_data(ttl=300)` | `portfolio:2559-2839` | 高 / 1-2d |
| 8 | OAuth client 統一為 `_t3_sheet_client()` 單一入口（**`portfolio:2140-2146` 是重點，它讓 SA-only 部署靜默不寫回**） | 4 處複製 | 中 / 3h |
| 9 | `portfolio:1124` / `:997-1013` / `:1105` 的 gate 改吃 `_t3_sheet_client()`，解鎖 SA-only 的 v2 UI | `portfolio` | 中 / 2h |
| 10 | 按鈕瘦身（上述 6 項） | `portfolio` | 中 / 0.5d |
| 11 | `t7:649`/`:1464` 改 `_norm_ccy`；`t7:1286` 改讀 `:1275` 的 cache；`t7:599-627` 補投資日期 NAV | `t7` | 中 / 3h |
| 12 | `append_ledger_row` 逐列改 batch；`upsert_fund_in_policy` 同理 | `t7:495` / `portfolio:2186` | 中 / 3h |
| 13 | `portfolio:1875` ffill 改 stderr + UI 揭露補值筆數 | `portfolio` | 中 / S |
| 14 | `render_t7_section()` 拆成 6 個 `_render_t7_*` | `t7:150-2947` | 中 / 1-2d |
| 15 | 更新 `portfolio:1-18` docstring；刪 `t7:995` 死碼；17 處 hex 收 `shared.colors` | — | 低 / S |

---

### 📌 ④-B 📋 我的管理室（`ui/tab_manage.py` 928 行，v19.433 最新 Tab）

#### 1. 現狀診斷與問題點

**資料稽核問題**

| 嚴重度 | 位置 | 問題 |
|---|---|---|
| 🔴 | `:746` | **靜默覆蓋跨 Tab 全域狀態**。`st.session_state["portfolio_funds"] = _funds`，覆蓋前**零檢查、零警告**，成功訊息完全不提會蓋掉原本的。**v1 低估了**：寫入的 `_build_fund_dict` 只產 **9 個 key**，而 Tab④ 正規 entry 含 `policy_id`/`policy_name`/`load_error`/`avg_nav`/`fx_avg`/`units`/`is_core` → **這顆按鈕會把保單歸屬整批抹掉**，破壞 `models/policy.py` 的 `(policy_id, code)` 複合鍵語意。全 repo 只有 3 個 `portfolio_funds` 寫入點，這是**唯一「不在組合管理流程內卻能整批換掉全域持倉」**的 |
| 🔴 | `:463` | **「和 NAS 週報同一套邏輯」不實陳述，6 項差異全部成立**（詳見下表）。其中 (b) 最嚴重：App 傳 macro composite、NAS 預設 `None` → `switch_advisor.py:225-226` 讓**成長型賣出訊號在 NAS 端結構性永不觸發** |
| 🔴 | `:884-891` | **`nav_history` 寫入零確認**：無 checkbox、無 preview、無 dry_run（`fundclear_backfill.py:104` 簽章**無此參數**）。`nav_history_gs.py:202` 純 append **無 rollback**，去重鍵僅 `(code, date)` → **錯級別寫入後正確資料永遠寫不進去**（同日已佔位）。而 `:761-764` 自己的警告就寫「級別/幣別對不上 → 跳空 → 報酬失真」，說明書 §8 標該分頁「🚨 絕對不要刪 … 無法從任何來源重建」 |
| 🟠 | `:428` vs `:505` | `_loaded` **未排除 `load_error`**，而同檔 `:505` 有（標「稽核 H2」）。**全 repo 其他 8 處消費者全部用 `loaded and not load_error`，`:428` 是唯一漏網**。而 `portfolio/load.py:219-221` 明確會寫入 `{"loaded": True, "load_error": …}` → 抓失敗的基金 `loaded` 就是 True |
| 🟠 | `:422` | **LINE 燈號假陰性**：只檢查 `LINE_CHANNEL_TOKEN`，但 `line_push.py:58` 支援別名 `LINE_CHANNEL_ACCESS_TOKEN`（`:57` 註解自承「GitHub secret 常用後者」）。且 `:433 if _ok and st.button(...)` **短路 → 測試按鈕整顆不渲染**。功能完好卻顯示 🔴 且無從測試 |
| 🟠 | `:587` | **`from repositories.macro.yf import fetch_yf_close` 違憲**。該檔是外部 HTTP fetcher，`CLAUDE.md §8.2.A` **無任何例外登記**（EX-CRUD-1 6 項全是本地持久化、EX-PASSTHRU-1 8 組不含它）。而**同一函式 `:641` 用的是正確的 L2 facade** `services.fund_service.get_latest_fx` |
| 🟠 | `:658-659` | `get_latest_fx` 失敗 → `_usd=None` → `portfolio_csv.enrich_returns` 讓所有非台幣基金 `cur_val=None` → **整組顯示「資料不足」，不說是匯率抓不到** |
| 🟠 | `:741-742` | 餵 `portfolio_funds` 的載入迴圈 `except: pass`，只剩 `:747` 的 `N/M` 計數 —— **哪一檔失敗、為什麼，完全無跡可循** |
| 🟡 | `:702` vs `portfolio_csv.py:164` | 覆蓋率門檻 `0.6` 兩份硬編碼、無 import 關係 |
| 🟡 | `:337/:349/:391/:404` | **80 行死碼**（production 0 caller）。且 `:383-384` 的 `clear_load_all_ws_cache()` 清的是 `load_all_policy_worksheets` 的快取，**本檔用的 `load_all_policies_v2` 根本沒有快取機制** → 清了也不生效 |

**App 預覽 vs NAS 週報 —— 6 項差異逐條核對**

| 項 | App | NAS (`scripts/weekly_switch_notify.py`) | 後果 |
|---|---|---|---|
| (a) 觀察集合 | `:427` 只看 session `portfolio_funds` | `:298-306` Sheet 持倉 ∪ `WATCH_CSV_URL` 追蹤清單 | 標的集合根本不同 |
| (b) macro composite | `:467` 傳 `_macro_composite()` | `:328` 預設 `None`（除非 `--with-macro`） | **`SELL_CASH` 與成長型 `WARN` 在 NAS 結構性永不觸發**。App 說「該賣」，NAS 永遠不送 |
| (c) `source_by_code` | 不傳 | `:338-339` 有傳 | App 預覽看不到 `[持倉]/[觀察]` 標籤 |
| (d) pool key | `:465` `{e.code: e}` **無 `.upper()`** | `:296` 有（且標「稽核修」） | App 保留了 NAS 已修的 bug → 小寫代號對不到 `type_override`/`category` |
| (e) `skipped` | `:470` `max(0, len(funds)-len(_held))`，而 `_assemble_rows` **無任何 continue** → **恆為 0** | `:337` 真實過濾後計算 | **不是低報是該欄位完全失效** |
| (f) rows 組法 | `rotation._assemble_rows`（讀 session 取 phase/score） | `:157-188` 本地重製，`phase="" score=None` | 換股配對結果可能分歧 |

> ❌ **v1 兩條撤回**：與 Tab④ 的「文案矛盾」**不成立**（v19.451 已改唯讀，`v2_editor.py:334 disabled=True`，兩頁一致）；429 錯誤「看不出原因」**錯誤**（`friendly_error` 帶型別+訊息+stderr，`_helpers.py:85-86` 對 429 明確回提示）。
> ⚠️ 但新發現：`v2_editor.py:402 _render_new_policy_section` + `:434 render_first_use_wizard` 已 **0 caller** 且**內含 `write_policy_v2` 呼叫**，約 100 行 —— 與本檔 80 行同屬唯讀化殘留。

✅ **通報「送出失敗但顯示成功」的路徑不存在**。`_test_send`（`:478-490`）+ `infra/line_push.py` 乾淨：只在 HTTP 2xx 回 `sent=True`，非 2xx `raise LinePushError` → `st.error`。且 `:479` import 刻意移出 try（標「稽核 FINDING 3」）避免 `NameError`。
✅ **無 `fillna` / `ffill` / dummy**。「不新增儲存、重用既有 L1/L2/L0」在**持久化層面屬實**。

**UI/UX 與操作體驗問題**

- **31 個控制項只有 2 個有 `help=`（6.5%）**，全站最低。15 button / 4 selectbox / **6 text_input**（v1 說 5，少算一個）全無。
- **`:293-296` gating 首次載入後失效** → 每 rerun 重打 Google API。實測 ≈ **10-11 reads/rerun**（v1 說 17，高估），而 `policy/_helpers.py:93` 記載上限 **60 reads/min** → **5-6 次 rerun 撞頂**。頁面有 15+3+4+6+2 = 30 個 rerun 觸發源。
- **危險操作零確認 3 處**：`:158`「🗑️ 清空紀錄」（直接刪 `cache/fund_history.json`）、`_render_pool_editor` 的「🗑️ 從池移除」（動 GS）、`:884`（不可逆寫入）。
- **三份清單概念擠同一區**：選股池 + 「曾經查過的清單」+「⭐ 升等為預設」（第三份 `config/preset_funds.json`）。
- **兩顆按鈕呼叫同一個 `load_all_policies_v2` 卻寫進兩份互不共用的 session**：`:293` → `_manage_pf_loaded`；`:767` → `navbf_holdings`。**打兩次 Google API**。
- **UX 陷阱 `:790-798`**：按過「載入持倉清單」後 `navbf_holdings` 非空 → 走 selectbox 分支 → `:798`「① 基金名稱」text_input **永久消失**，再也不能手打不在持倉裡的基金。
- **整頁沒有一句「所以你現在該做什麼」**。`:472-473` 的 caption 是 `該通知=True｜換股/表現差建議 3 檔` —— **內部欄位名直出**。
- `:572` `components.html(height=900, scrolling=True)` → 巢狀雙捲軸；`:179-184` 每 4 代號一列 `st.columns(4)`（手機表現無法由原始碼證實，建議實機確認）。
- `:202` `_is_preset()` **每個代號重讀一次 JSON**（`fund_history.py:352-357`），而 `_DEFAULT_FUNDS` 模組層快取**就在旁邊沒接上**。50 檔 = 50 次讀檔 + 50 次 parse / rerun。

**三份「持倉真相」並存、零交叉校驗**：(A) `load_all_policies_v2`（同檔呼叫**兩次**：`:305` + `:774`）(B) `_polcsv_holdings` CSV (C) `portfolio_funds` session。(B) 可經 `:746` 單向覆蓋 (C)，但 (A) 永遠不參與。

#### 2. 具體改善優化方案

**新手友善化調整**
1. 通報區補白話結論：把 `該通知=True｜…3 檔` 改成「本週會通報 3 檔：**ACCP138**（連 2 週表現落後）、…。預計每週一 09:00 由 NAS 送出。」
2. `:719` 最差組合後補行動建議 + 指路到「換股顧問」
3. 31 個控制項全補 `help=`（照 `_render_pool_editor` 的 `column_config` 品質）
4. LINE 燈號改用 `line_push._resolve` 同一套別名解析；並標示「此燈號檢查 App 端；每週實送跑在 NAS，兩者設定不同」

**介面排版與按鈕瘦身計畫**
1. **三份清單收成 `st.tabs`**：`選股池 / 查詢紀錄 / 預設清單`，頁首一句話講清三者關係
2. `:293` 與 `:767` **合併成一顆**，共用同一份 session
3. `:833`/`:845` 改單一按鈕 + `st.radio(["先試我的機構", "掃描全部機構（~1-2 分）"])`
4. **修 `:790-798` 陷阱**：selectbox 分支下方永遠保留「或手動輸入基金名稱」
5. `:572` 改 Streamlit 原生元件重繪除息月曆，或至少 height 依內容動態計算

**數據呈現與進階分析保留方式**
- 六大區塊**零刪除**，只做內部收納
- 「📊 保單組合分析」上傳 CSV 後**加一行對照**：「你 Google Sheet 裡有 M 張保單 / N 檔基金，這份 CSV 有 M′ / N′」，不一致就標警示 —— 直接解掉「三份真相」的困惑

#### 3. 程式碼重構建議

| # | 動作 | 檔案:行 | 嚴重度/工作量 |
|---|---|---|---|
| 1 | **`:463` 文案立即改正**（10 分鐘）誠實揭露 6 項差異。**治本**：把 `weekly_switch_notify.py` 的 `_assemble_rows` / `_underperf_by_code` / `_pool_rows` 抽成 streamlit-free 的 `services/switch_pipeline.py`，App 與 NAS 共用 | `:463` + 新檔 | 高 / 文案 10min，治本 4-6h |
| 2 | `:884` 加確認 checkbox + 寫入前 preview（「即將寫入 {code}：N 筆、{ccy}、{起}~{迄}；該代號目前已有 M 筆、幣別 {existing}」，幣別不一致直接 `st.error` 擋）；`download_and_store` 加 `dry_run` | `:884` + `fundclear_backfill.py` | 高 / 2-3h |
| 3 | `:746` 覆蓋前檢查既有值 → `st.warning` + 二次確認；記 `portfolio_funds_source`；**且 `_build_fund_dict` 要保留 `policy_id`** | `:727-748` + `_utils.py` | 高 / 2h |
| 4 | `:428` 加 `and not f.get("load_error")`；`:465` 加 `.upper()` | `:428/:465` | 高 / XS |
| 5 | `:422` 改用 `line_push._resolve` 同一套別名 | `:422` | 中 / XS |
| 6 | `:293-296` 改 `if st.button(...) or session 無快取 df:`，df 存 session；`load_all_policies_v2` 加 60s TTL；`list_pool()` 單次 run memoize；`is_preset` 改先建 set | 3 檔 | 中→高 / 3-4h |
| 7 | `:587` `_yf_1y_return` 移進 `services/`（或改用既有 benchmark facade） | `:584-595` | 中 / 1h |
| 8 | 刪 `:337-416` 80 行死碼 + `v2_editor.py:402/434` ~100 行；更新本檔 docstring `:7-8`（已描述不存在的能力） | 2 檔 | 中 / S |
| 9 | `:158` 與「🗑️ 從池移除」加二次確認 | 2 處 | 中 / 1h |
| 10 | 5 處 `except: pass` 補 stderr（優先 `:658` FX、`:741` 載入迴圈）；`:702` 改 import `_COVERAGE_MIN` | `:385/509/651/658/741/822` | 中 / S |

---

### 📌 ⑤ 📖 參考 / 診斷（巢狀：`tab5_data_guard.py` 1547 行 + `tab6_manual.py` 833 行）

#### 1. 現狀診斷與問題點

**資料稽核問題 — 🔭 資料診斷**

| 嚴重度 | 位置 | 問題 |
|---|---|---|
| 🔴 | `tab5:127` | **`anomaly_view_state` 的字串比對永不成立**。窮舉驗證：`_freshness` 所有 return label（共 14 種字面值）**沒有任何一個含「release 期已到」**，🟡 的實際字串是 `release lag {N} 天（預期 …）` → 條件恆為 True → **每次 FRED 月度指標發布後 +2~+5 天，一批完全正常的 🟡 被列入異常清單**，且 `st.success("全數正常")` 永遠不出現。而 `:1505` **明文向使用者承諾「release window 內的 🟡 已自動排除」** = 畫面文字宣稱做了一件程式沒做的事 |
| 🔴 | `tests/test_data_guard_anomaly_state.py:47,:85` | **假綠測試**：fixture 寫死生產端從不產生的 `"release 期已到 +2 天"`。這是上一條能存活至今的直接原因。**修 code 必須同步改 fixture** |
| 🔴 | `tab5:436-461` | **5 列燈號共用 `_fund_n`**（3️⃣MoneyDJ wb01/05/07、5️⃣TDCC、6️⃣Fundclear、7️⃣cnyes、8️⃣Allianz-Chubb），`_fund_n` 只是「載入了幾檔基金」，與該來源是否真被呼叫無關；第 🔟 列硬寫 `_src_status(False, 0)` 永遠 ⬜。**v1 說「4 列」是錯的，且第 4️⃣ 列其實用 `_nav_n` 不是 `_fund_n`**。而 `_div_n`/`_hold_n`/`_ter_n` 已算出來卻只丟到 caption 文字，沒回饋到燈號 |
| 🔴 | `tab5:435` | **捏造的端點字串**：`yp401000.djhtm (wb01) / yp405000.djhtm (wb05) / yp407000.djhtm (wb07)` —— 這三個檔名**全 repo 只出現在這一行**。真實是 `/w/wb/wb01.djhtm`、`/yp/wb05.djhtm`、`/yp/wb07.djhtm` |
| 🔴 | `data_registry.py:451-453` | **雷達 10 燈完全不走 `_freshness`**：value 非 None 就 🟢，`latest_date` 直接偽造成字串「今日」→ **10 盞燈的新鮮度從未被檢查過** |
| 🟠 | `data_registry.py:553/586/603/656` | 4 條路徑缺日期時回 `"本月"/"年度"` + 硬編 🟢 → **永遠不可能亮紅燈** |
| 🟠 | `tab5:1495` | `clean` 分支把 `⬜ 未知日期`（解析失敗）算進「狀態全數正常」；配合 `data_registry` 三處 `except: pass` + `dropna` → 形成**「解析失敗 → ⬜ → 併入『全數正常』」的完整漂白路徑** |
| 🟠 | `tab5:204-239` | **完整率是存在性檢查不是健康度檢查**：Tab1 只驗 `value is not None`（不看新鮮度）；Tab2 **Meta 是送分題**（`_src_cf` 非空的前提就是已載入 → 恆 ✓）；Tab3 只看 `loaded` flag；**Tab4 Sheet 政策只驗憑證存在，完全沒讀 Sheet** |
| 🟠 | 三處清單 | `_FREQ` **29** 鍵（`registry_classify.py:15` docstring 寫 30，也錯）/ `D5_KEYS` **16** / 引擎實際輸出 **25**。**列了沒抓 5 個**（`CHN_CLI/CHN_PMI/CHN_CPI/CHN_M2/USDCNY` —— 中國總經走獨立路徑 `china.py`，從不寫進 `indicators`）；**抓了沒列 1 個**（`NFP`）；**不計入完整率 9 個**（含 `LEI`(Phase 4 的 target_key)、`SLOOS`、`JOBLESS`…）→ 顯示「16/16 完整」時實際有 9 個引擎抓的指標沒被檢查 |
| 🟡 | `tab5:227/:237/:1130/:915/:702` | 5 處 `except` 完全無訊息（FX 失敗、Sheet 政策失敗直接讓 Tab4 燈變紅**不說原因**） |
| 🟡 | `tab5:408-411` vs `:1266` | **TER 取值三處三種語意**，且**沒有任何一處呼叫已統一的 `_get_holdings()`**（`:96-108` B7 v19.332 的正確樣板）。`:1265` 註解自稱「鏡像 Section① `_ter_n`」但它鏡像到的是 pf 那一半，與 cf 那一半相反 |

> ⚠️ **v1 修正**：`TGA` 的死因**不是**「靠 `.get(key,'monthly')` 預設值」—— 它確實吃預設值並通過 gate，真正走不到是因為 `indicators` **從無 `"TGA"` 這個 key**（TGA 被吃進 `FED_BS` 淨流動性）。與 `HY_SPREAD` 等「freq=daily 被 gate 擋掉」是**兩種不同的死法**。

**資料稽核問題 — 📖 說明書**

| 嚴重度 | 位置 | 問題 |
|---|---|---|
| 🔴 | `tab6:86` + `data_registry.py:559` | **持股 endpoint 兩邊都錯**：`wh06_3` **全 repo 零命中**（純捏造）；`yp004002` **是 NAV 歷史頁不是持股頁**（更誤導 —— 指向真實但用途完全不同的端點）。真實是 `nav_metrics.py:977` `yp013000`/`yp013001` + 替代頁 `wq06` |
| 🔴 | `us_indicators.py:1492-1500` | **天氣表描述的是一組死碼**：`alloc.get("股票", 60)` 的預設值 60/30/10、50/40/10、30/50/20 **全部永不觸發**（`alloc` 早在 `:1393-1478` 被位階設定）。畫面「☀️ 晴天」實際顯示**擴張的 60/30/10**、「⛅ 多雲」顯示**復甦的 40/40/20**。tab6 天氣表「建議配置」欄寫的是那組死掉的預設值 |
| 🟠 | `tab6:316-320` vs `:334-338` | **位階表與天氣表自相矛盾**：Score=7 同時是「🟢 擴張（股60）」與「☀️ 晴天（股多債少）」；Score=4 是「🔵 復甦」卻是「⛅ 多雲（股債均衡）」→ 一邊叫加碼一邊叫均衡。**兩張表數字都與程式碼一致，矛盾是程式碼自帶的** |
| 🟠 | `tab6:53-54` vs `session.py:28-30` | 「美國總經 12 指標」列 `UMCSENT` **不列 SAHM/SLOOS**；`D5_FRED_KEYS` 相反。且 tab6 **同頁 `:307-308` 的 warning 自己寫「包含權重最高的 SAHM 與 SLOOS」** → 同一頁表格與警語互相矛盾 |
| 🟠 | `tab6:89-92` | USDTWD 三項全錯：refresh「10 min」（實際 `fx_and_main.py:115` **300s**）、fallback 2 源（實際 4 源且 **FRED/Frankfurter 對 TWD 是 dead path**，`:145-147` 明說） |
| 🟠 | `tab6:423-426` | **假數據掛真實基金名**：「**實例** — 安聯收益成長：含息1Y=+5.2%，配息率=9.6%」硬寫虛構數字，而「安聯收益成長」是 `session.py:101 _CORE_WHITELIST` 的真實白名單標的，且標題用「實例」不是「假設數字」 |
| 🟡 | `tab6:2-4` | docstring 宣稱「純靜態 / **零 runtime 狀態依賴（不讀 session_state、不呼叫 services）**」—— **四項全違反**（`:641` 讀、`:809` 寫、`:154-160/:205/:759` 呼叫 services、`:176/:235/:217/:220` 有副作用 widget） |
| 🟡 | `tab6:542-545` | 四分位描述**不完整**：`helpers.py:162-167` 另有**無 peer 資料時的絕對值 fallback**（Sharpe>1.5→Q1 …），**完全沒跟同類比卻仍顯示「第1四分位🏆(前25%)」**，說明書未提 |

**應綁 SSOT 而未綁**：Macro Score 14 項權重、位階分界 8/5/3 + 配置矩陣、天氣分界 7/4、**4D Grade cutoff（`GRADE_CUTOFFS_4D` SSOT 存在、隔壁 `columns.py:142-146` 已正確 f-string 注入，只有說明書沒做，且同檔重複寫兩次）**、`GRADE_4D_MIN_FACTORS`、再平衡 5%/10%（同檔重複兩次）、汰弱 ±2pp、`portfolio_core_pct` 75%（碰巧一致，無機制保證）。

**另有 6 處 tab6 自身的過期 Tab 指路**（`:482/:500/:576/:578/:588/:596` 寫「Tab3 / Tab5 / Tab6」，現行分頁名無此稱呼）。`:47/:142` 的「🔭 資料診斷（「參考 / 診斷」分頁內）」是已更新的正確寫法，可作修正樣板。

**UI/UX 與操作體驗問題**

- ✅ `tab5:155-161` 開頭 `st.info`「本頁大部分是維運診斷…**一般使用只需要看 ⓪ 與 ⑥**」是最有效的降噪設計
- ❌ 仍勸退新手：「Phase 4 變數重要性 / Phase 3-B 燈號回測」「expanding window」「min_overlap=24 + lag=3」；freshness 標籤外洩內部語彙 `本/上月（35天前 / **fallback**）`；`📦 ARCHIVED · 92 天前（…）` **一格塞 90 字維運手冊**；Section ⑤ 欄名直接用爬蟲代號 `wb01報酬資料`
- **tab5 15 個控制項 2 個有 help；tab6 5 個控制項 1 個有 help**
- **RWD**：tab5 5 處 `columns(4)`（Section ⑤ 每檔 20 格）；**6 處手刻 CSS grid 全部固定欄數無 `minmax()`**，其中 `tab5:468` 是 6 欄且第 4 欄塞 200+ 字元 monospace endpoint → **窄螢幕撐爆或不可讀**
- tab6 **10 個橫向 tab 在窄螢幕會水平溢出**，第 8/9/10 章實質被藏起來；**無搜尋、無目錄、無詞彙表**

✅ **tab6 的「防脫鉤自覺」極高**（docstring 鐵律「說明書寫了但系統沒實作，比沒有說明書更糟」、台股 TPI 整章刪除留 8 行理由、`:307-311` warning「不要拿它自己加總對答案」、§D expander 標題不寫死項數）。**缺的不是自覺，是機制** —— 所有防護靠人工註解與 review，沒有一行程式強制文件與常數綁定。

**程式碼問題**

- **收合 expander 每 rerun 重跑**：`tab5:793` `backtest_sub_cycle_lights`（`causal_sankey.py:317` 無 cache）；`:1371` `nav_history_gs.status()` **連 expander 都沒有**；`:1407` `coverage_status()` **無 cache、無 expander、無條件執行 → 每次 rerun 一次 Google Sheets 網路讀取**
- **`_update_data_registry` 由 `app.py:273` 在渲染前呼叫 → 使用者停在 Tab1 也照跑**：25 指標 + N 檔基金全量 `sort_index()` + 把排序後**完整 Series** 塞 session_state（唯一消費端是 Snapshot Viewer 的 `.head(5)`）；冷 cache **16 key × 2 = 32 次 FRED HTTP**
- `get_latest_fx("USDTWD")` 一次 rerun 打兩次
- UI import service 私有函式：`tab5:1113` `_resolve_adr_with_fallback`、`:230-233` `_gsa_secret`/`_oauth_configured`
- **tab5 19 個 except 只有 1 個寫 stderr；tab6 5 個 0 個**（含 `:816` 裸 `pass` 讓 AI snapshot 少資料無人知曉）
- `tab6:619` UI→UI 交叉 import `from ui.tab1_macro import render_indicator_map`

#### 2. 具體改善優化方案

**新手友善化調整**
1. tab5 維運術語加白話副標；`fallback` → 「（用備援判斷）」；`📦 ARCHIVED` 那格 90 字改一行 + `st.popover` 展開細節
2. **說明書新增第 11 章「名詞速查」**，把 G7 列的 17 個名詞一次收齊，並讓全站 `render_metric_explainer` 讀同一份 `shared/glossary.py`
3. tab6 10 個橫向 tab 改 `st.selectbox("章節")` 或 `st.pills`（1.59 可用）避免水平溢出

**介面排版與按鈕瘦身計畫**
1. tab5 把 ⓪ 與 ⑥ **移到頁面最上方**，其餘全部收進單一「🔧 維運診斷」expander（延伸 `:155-161` 已有的降噪意圖）
2. tab5 6 處手刻 CSS grid 改 `st.dataframe`（可排序、可複製、原生 RWD）；tab6 ⓪ 資料地圖同上

**數據呈現與進階分析保留方式**
- tab5 所有診斷區塊、tab6 全 10 章**零刪除**，只做兩層收納

#### 3. 程式碼重構建議

| # | 動作 | 檔案:行 | 嚴重度/工作量 |
|---|---|---|---|
| 1 | **`anomaly_view_state` 不要用中文字串做流程控制**：在 registry entry 加結構化欄位 `"release_window": bool`，改判該欄位（最小修補是 `startswith("release lag")` 但仍脆弱）。**同批必改 `test_data_guard_anomaly_state.py:47,:85` 的 fixture** | `tab5:127` + `data_registry` + 1 測試 | 高 / **S <1h** |
| 2 | **fetcher fallback chain 命中時寫 `session_state["_fetch_provenance"]`**，Section ① 依它點燈，無紀錄顯示 ⬜「本 session 未呼叫」。**NAV 已用 `series.attrs["source"]` 做到（v19.337），推廣即可** | `repositories/fund/*` + `tab5:436-461` | 高 / M 1-2d |
| 3 | **修 3 處捏造/錯誤端點字串**：`tab5:435` `yp40*` → 真實路徑；`tab6:86 wh06_3` 與 `data_registry:559 yp004002` → `yp013000/yp013001`；`data_registry._tw_specs` 三處 `TaiwanMacroEconomics` → **改讀 fetcher 已回傳的 `source`**（`macro_tw_local_repository` 四個 fetcher 都有回） | 3 檔 | 高 / **S 1h** |
| 4 | `data_registry.py:451-453` 雷達 10 燈改走 `_freshness`；4 條缺 provenance 路徑改回 ⬜ 而非 🟢（`registry_classify.rollup_caption` 已支援 `⚪` 只是沒人餵值） | `data_registry` | 高 / M |
| 5 | **新增 `shared/data_sources.py`**：dataclass 定義每個資料源（`id/顯示名/endpoint/ttl/publish_lag/fallback_chain/used_by_tabs`），三方共讀 —— tab6 ⓪ 由它產表、tab5 ① 的 `_RAW_TABLE` 由它產列、`data_registry.source` 由它取名。**這是根治文件脫鉤的唯一方法** | 新檔 + 3 檔 | 高 / M-L 3-5d |
| 6 | `:793` / `:1371` / `:1407` 三處改按鈕觸發或 `@st.cache_data(ttl=)` 或 `st.fragment`；`_update_data_registry` 只存 `latest_date`/`count`，用 `s.index.max()` 取代全量 sort；合併兩次 `get_latest_fx` | `tab5` + `data_registry` | 中高 / M 2-3d |
| 7 | 完整率判準改 `有值 AND freshness != 🔴`；`_cf_have_meta` 改檢查實質欄位；`_gs_policy` 改實際 read probe（cache 5 分） | `tab5:204-239` | 中 / M |
| 8 | 讓 `services/macro/us_indicators` 匯出 canonical indicator SSOT，收斂 `_FREQ`(29)/`D5_KEYS`(16)/引擎(25) 三份 | 3 檔 | 中 / L 3-5d |
| 9 | tab6 位階/天氣分界收同一組常數（**順便就會發現內部矛盾**）；4D Grade 改 import `GRADE_CUTOFFS_4D`（照抄隔壁 `columns.py:142-146`）；修 `us_indicators.py:1492-1500` 的死碼預設值 | 3 檔 | 中 / M |
| 10 | TER 取值抽 `_get_ter()`（照 `_get_holdings()` 樣板）；`render_indicator_map` 抽到 `ui/components/`；更新 tab6 docstring + 6 處過期 Tab 指路 | 多檔 | 低 / S |

---

### 📌 側邊欄（`ui/sidebar.py` 241 行）

#### 1. 現狀診斷與問題點

**資料稽核問題**
- 無假資料、無 `fillna`（純顯示層）
- `:45` **`Fetcher v6.24` 硬編字串**（App/Engine 由 `app.py:164-165` 注入，只有 Fetcher 寫死在 f-string 內）→ 會 drift 卻不會有人發現
- `:180-181` 全域刷新失敗**只顯示 `type(_e).__name__`** —— 無訊息、無 stderr、無 traceback。依 `PROCESS.md` 「Streamlit Cloud log 只顯示 stderr」→ **這個失敗在雲端等於查不到原因**
- `:143-147` `except: pass` 讓資料健康總覽整塊壞掉**完全靜默**（使用者只看到兩條 divider 中間一片空白）
- `:117` `_git()` 的 `except: return ""` 全靜默 → **這正是 GitHub 按鈕永遠回 unknown 卻查不出原因的根因**
- `:233` Sheet 標題讀取失敗靜默降級成顯示 ID
- `:87` `verify=False`（Proxy 測試關閉 TLS 驗證）

**UI/UX 與操作體驗問題**
- **🔴 資訊架構倒置**（實測順序）：品牌 → **版本** → **版本（第 2 次）** → 金鑰 → **維運工具** → **維運工具** → 資料健康 → **危險操作** → **登入** → **帳本**。
  **使用頻率最高、且是一切功能前提的「登入 + 選帳本」排在最末**；**雲端根本無效的 GitHub 同步排在第 6**。
  > 這重演了 v18.75 的問題（當時把登入從 Tab3 expander 搬到 sidebar，理由正是「登入入口太深」）。
- **🔴 三處指路文案指向不存在的分頁名**：`:204`「登入後 Tab3 即可…」、`:208-209`「請至 Tab3「**📊 組合基金**」」、`:240`「至 Tab3「✨ 新增帳本」」。
  **而 SSOT 早已備妥**：`ui/helpers/story_nav.py:25-38 tab_label()`，且 `story_nav.py:19-21` 的註解**自己寫著**「2026-08-05 稽核 必修 2：三處指路文案指向不存在的分頁名，根因就是『標籤沒有 SSOT』」—— **SSOT 建好了、`app.py:196-199` 已改吃它，sidebar 這三處是漏網**。
- **`♻️ 強制同步 GitHub` 在雲端實質無效**，`PROCESS.md:65` **已明文記載**：「只查版本、不能觸發部署」。Streamlit Cloud 容器無 `.git` → `_local = "(unknown)"` → 恆走 `:123-124` 的 warning 分支。按鈕唯一作用是印那行 warning。
- **8 個控制項只有 2 個有 `help=`**（v1 說 3 個，**多算一個**），且全域刷新的 help 是純開發者語言（版本號、`@st.cache_data`、`/tmp/fund_cache`、「上游 cron」）；成功後的 toast 同樣是 `TTL {N} 條 / st_cache {N} 條 / snapshot {N} 筆`
- **金鑰狀態沒有任何說明**「這是什麼、❌ 了會怎樣、去哪設定」→ 新手看到 ❌ 無法行動
- **4 個控制項缺 `key=`**（`:65` Proxy 測試、`:106` GitHub 同步、`:134`/`:202` 兩個 link_button）→ 未來複用會踩 `DuplicateWidgetID`（v19.433 剛踩過一次）
- `st.sidebar.xxx` 與 `st.xxx` 兩種寫法混用（已在 `with st.sidebar:` 內卻仍寫 `st.sidebar.button`）

#### 2. 具體改善優化方案

**新手友善化調整**
1. 金鑰狀態加 `help=`：「FRED 是美國聯準會資料庫，缺少時「市場定調」的 12 個美國總經指標會全部抓不到。設定：Streamlit Cloud → Settings → Secrets」
2. 全域刷新 help 改白話：「清掉所有暫存資料，下次載入會全部重抓（會變慢，但保證最新）。不會動到你的歷史資料倉。」

**介面排版與按鈕瘦身計畫**
1. **重排資訊層級**（本 Tab 最高 ROI）：
   ```
   品牌 + 版本（合成一行，刪掉重複的 beacon）
   ── 🔐 Google 帳號（登入 / 登出）
   ── 📋 工作中帳本
   ── 資料健康總覽（+ AI 解讀）
   ── 🧹 全域刷新（checkbox + button）
   ── 🔧 開發者工具 expander（金鑰狀態 / Proxy 測試 / GitHub 同步）
   ```
   > ⚠️ **「sidebar 開發者功能移診斷頁」已在 `STATE.md` v19.336 待核准清單**，不是新點子。本項應以「推進既有待核准項」提案。我建議的變體是**收進 expander** 而非搬到 Tab5 —— 保留隨手可用，但不佔第一屏。
2. 刪掉 `♻️ 強制同步 GitHub` 或改成 `st.caption` 顯示版本比對結果（不做成按鈕），因為它在雲端無效
3. `:45` 的 `Fetcher v6.24` 改注入或直接刪

**數據呈現與進階分析保留方式**
- 所有既有功能**零刪除**，只做順序調整與 expander 收納
- **「全局資料健康」不要與 Tab5「資料診斷」合併** —— 你在 v19.403 DUP-3 已判 B/C 為 WONTFIX（「不同資料，不併…合併會毀掉區別」）

#### 3. 程式碼重構建議

| # | 動作 | 檔案:行 | 工作量 |
|---|---|---|---|
| 1 | 三處指路文案改吃 `story_nav.tab_label()` SSOT（**SSOT 已存在，只差 migrate**） | `:204/:208/:240` | S 0.5h |
| 2 | `:180-181` 補完整訊息 + `print(..., file=sys.stderr)` + traceback | `:180` | XS |
| 3 | `:143-147` 改 `st.caption("⬜ 健康總覽載入失敗：…")` + stderr（「異常不擋主畫面」的理由不成立，caption 同樣不擋） | `:143` | XS |
| 4 | sidebar 區塊重排 + 開發者工具收 expander | 全檔 | S-M 2-3h（**需你核准，屬 v19.336 待核准項**） |
| 5 | 刪重複版本顯示；`Fetcher v6.24` 改注入或刪 | `:45/:47-55` | XS |
| 6 | 4 個控制項補 `key=`；5 個缺 `help=` 的補上（白話版） | 全檔 | S 1h |
| 7 | `st.sidebar.xxx` / `st.xxx` 寫法統一 | 全檔 | XS |

---
## 3. ⛔ 禁區清單 — 以下絕對不提案

逐條比對 `CLAUDE.md` / `STATE.md` / `PROCESS.md` 後，以下已由你拍板或判定 WONTFIX，本報告刻意迴避：

### 3.1 已凍結（比 WONTFIX 更強）
**境內基金「含息 3 年年化」**（`ACCP138/ACDD01/ACDD19/ACTI71/ACTI94` 的  3-3-3 恆 ⬜）。`STATE.md` 2026-08-11 原文：「**狀態：凍結，不是待辦。沒有解凍條件成立之前不要重新開挖** —— 這一項被重複調查了三次」。根因是來源不存在，已有 `tests/test_domestic_perf_frozen.py` 守「不得偷偷解凍」。

### 3.2 已退役 —— 提「加回來」等於違反已決事項
危機回測室（2798 LOC）、總經指南針、`🎯 選基金（低基期）` screener、配置模擬器、param finder、`_render_beginner_dashboard` / `_render_macro_navigator` / `_render_tw_local_dashboard`（v19.401 Phase 0，−499 行）。

> ⚠️ **「beginner_dashboard」已被刪過一次**。本報告的「新手友善化」提案**一律是在既有元件上加 tooltip / 白話 caption / 分層收納**，沒有任何一條是「做一個新的新手儀表板」。

### 3.3 by-design 不收
`macro_card_edu.py` 25 個 `how_to_read` 教學表 threshold、PMI harmonize 統一值（你 2026-06-26 撤銷）、VIX `_VIX_SNAPSHOT_CALM=18.0`（你 2026-07-23 拍板刻意嚴於全站 22，**「非漏網，稽核勿逕改」**）、`fund_fetcher.py` 保留根目錄（F-GRAY-1）、`app.py` 不再下沉（F-GRAY-3）、Bucket 2 數字牆改圖表、6 個 height 不一致、批次表加 AI 評論、LLM 結構化輸出。
**`PHASE1_AUDIT_DELTA.md` 的 TOP 1/2/3 已於 v19.272-274 全部完成**，該文件應標記為「已完成，勿當待辦」。

### 3.4 硬規則
- **「去重 ≠ 合併資料」**（你 2026-08-07 親口定）。DUP-3 的 B/C 已判 WONTFIX。本報告所有「收攏」提案都是**收攏控制項與版面**，**沒有一條是合併兩份不同的資料**
- **不可在一般操作路徑上加 `clear_all_caches()`**（v19.353 剛從 Tab2「🚀 分析」拔掉並加了回歸鎖）
- **CSS/DOM hack 必須優雅失效**（不寫 JS、選不到就什麼都不發生）
- **`PROCESS.md §4` 0-consumer 條款**：新增旗標/欄位必須同批附一條「production caller 真的讀到它」的測試，且該測試在「產生端正確但沒接出去」時要變紅
- **診斷訊息必須寫 `stderr`**，`print()` 的 stdout 在 Streamlit Cloud 看不到
- **測試因環境缺件無法執行時必須 fail 而非 skip**

### 3.5 正當的切入點
`STATE.md` v19.405 明確留了一道門：
> 「本 PR 只做『重排 + 命名 + 參考合區』(結構層)，**未**做 5,400-LOC 決策分頁間的深度 section 搬移 —— 該部分最動 user 工作流，**留給 user 看過 5-tab 成果後再決定是否續做**」

**本報告所有「介面排版與按鈕瘦身計畫」，就是這道門後面的那一步。**

---

## 4. 優先級總表

依「**會不會讓使用者拿到錯的數字並據此做決策**」排序。

### P0 — 產生錯誤決策，修法明確（建議先做，共約 4 個工作天）

| # | 問題 | 位置 | 工作量 |
|---|---|---|---|
| 1 | T7「目標單位數」selectbox 被無條件覆寫成死碼 | `t7:1091` | **5 分鐘** |
| 2 | `data_registry._tw_specs` 三處顯示不存在的 API 名稱 | `data_registry.py:398-410` | **0.5h** |
| 3 | `anomaly_view_state` 字串比對永不成立（+ 假綠測試 fixture） | `tab5:127` + 1 測試 | **<1h** |
| 4 | Tab5/Tab6 三組捏造或錯誤的端點字串 | `tab5:435` / `tab6:86` / `data_registry:559` | **1h** |
| 5 | 手動匯率 `32.0` 印進「完整計算公式」裸算式 | `tab2:1929` + 4 處 `st.code` | 1h |
| 6 | 無風險利率 `4.0` 捏造（2 份副本 + 潛在 TypeError） | `tab1:1029` + `app.py:130` | 0.5h |
| 7 | 4D 卡 / HWM σ 卡 `except: pass`（+ 假綠測試邏輯） | `tab2:1066/1138` + 1 測試 | 1h |
| 8 | `dividend_safety` 的 `nav_change` 參數誤用（配息愈高警示愈不觸發） | `health/dividend.py:475` | **0.5h** |
| 9 | `replacement.py` 取不存在的 key → rule(b) 失效 | `health/replacement.py:126` | 1h |
| 10 | 換標建議 4 caller 未傳 `holding_years` → rule(a)(c) 停用 | 4 檔 | 1h |
| 11 | 健診 `slider「吃本金閾值」` 死控制項 | `tab_fund_grp_health.py:185` | 1h |
| 12 | 帳本雲端寫入失敗被吞、畫面顯示成功 | `t7:451-454` | 1h |
| 13 | B 分頁「顯示應買」vs「實際落帳」不一致 | `t7:1530-1570` | 0.5d |
| 14 | 借用基金 `NAV=10.0`/`FX=31.0` 憑空造值 | `t7:1731-1739` | 2h |
| 15 | emoji `startswith` 決定「模擬 vs 真寫入主帳本」 | `t7:1270/1455/2116` | 3h |
| 16 | `nav_history` 寫入零確認（不可逆污染） | `tab_manage.py:884` | 2-3h |
| 17 | `:746` 靜默覆蓋 `portfolio_funds` 且抹掉 `policy_id` | `tab_manage.py:746` | 2h |
| 18 | 通報預覽宣稱「和 NAS 同一套」但 6 項差異 | `tab_manage.py:463` | **文案 10 分鐘** |
| 19 | 批次「部分失敗」標成 ✅ 成功（最多 22 欄留白） | `unified.py:403-437` | ~30 行 |
| 20 | `_parse_codes` 靜默丟棄輸入 + 無數量上限 | `tab_batch:75-98` | S |
| 21 | sidebar 三處指路指向不存在的分頁名（SSOT 已存在） | `sidebar.py:204/208/240` | 0.5h |
| 22 | `_loaded` 未排除 `load_error`（全 repo 唯一漏網） | `tab_manage.py:428` | XS |
| 23 | 6 個 `st.stop()` 在分頁內炸掉整頁 | `t7` 6 處 | 2h |
| 24 | 雷達 5 組門檻已漂移（VIX 25→22、PCR 1.5→1.2） | `tab1:149-172` + `risk_radar.py` | 2-3h |

### P1 — 效能與體驗，使用者有感

| # | 問題 | 位置 | 工作量 |
|---|---|---|---|
| 25 | Tab④ AI snapshot 預先全算（含網路）+ 持倉健診無守門 | `portfolio:2559-2839` | 1-2d |
| 26 | Tab5 三處無 cache 重運算（含每 rerun 一次 GS 網路讀） | `tab5:793/1371/1407` | 2-3d |
| 27 | `_update_data_registry` 全量 sort + 存完整 Series（停在 Tab1 也付） | `data_registry` | 1d |
| 28 | 管理室 gating 失效 → 5-6 次 rerun 撞 GS 配額 | `tab_manage.py:293` | 3-4h |
| 29 | `backtest_turning_points` 無 cache（Tab1 唯一真瓶頸） | `turning_points.py:366` | 2h |
| 30 | `record_fund_nav_point` 同步阻塞（整段 append + 每次全表讀） | `nav_history_hook/gs` | 1d |
| 31 | batch checkpoint O(N²)（400 檔 ~140MB 寫入） | `batch_checkpoint.py` | S-M |
| 32 | **`render_metric_explainer` 補 `mdd`/`div_coverage`** | `tab2:1508` | **一行，最高 ROI** |
| 33 | Tab④ 三顆載入鈕 + 三顆登入鈕 + 死指標文案 | `portfolio` 9 處 | 0.5d |
| 34 | Tab1 兩顆清快取鈕收攏 + 詳細區改分頁（解 60+ 次滾輪） | `tab1` + 子模組 | 1-2d |
| 35 | 健診加「期末市值 / 淨結果」3 欄 + 頂端白話總結 | `fund_row.py` + tab | 1.5d |
| 36 | 批次頂端 3 metric → 8 metric（資料都在 df 裡） | `tab_batch:302` | S |
| 37 | Tab2 搜尋→分析斷點（要人工複製貼上） | `tab2:353` | 1h |
| 38 | 手機自刻 grid 全改 `auto-fit`（tab2/tab5×6/tab6） | 3 檔 8 處 | 3h |
| 39 | 健診 / 批次加「精簡 / 完整」模式 | 2 檔 | 1d |
| 40 | sidebar 資訊架構重排（**屬 v19.336 待核准項**） | `sidebar.py` | 2-3h |

### P2 — 架構債與 SSOT

`shared/data_sources.py` 資料源 SSOT（3-5d）／`_fetch_provenance` 回寫（1-2d）／canonical indicator SSOT 收斂 29-16-25（3-5d）／健診線性年化改幾何（1d）／本金基準統一（0.5d）／OAuth client 統一單一入口（3h）／`render_t7_section` 2798 行拆分（1-2d）／Tab1 循環依賴解除（4h）／`unified.py` 欄序合一（M）／說明書分界收 SSOT（M）／刪死碼（`tab_manage` 80 行 + `v2_editor` 100 行 + `t7:995` + Tab1 3 個 import + 14 色票）／顏色 hex 收 `shared.colors`（約 45 處）／說明書加詞彙表 + `shared/glossary.py`（1d）。

### 需你拍板才能動

| # | 項目 | 為什麼要你決定 |
|---|---|---|
| **A** | **批次分析並行化** | 目前「序列 + 每檔 ~5s」**正好是唯一的 rate-limit 保護**。實測 400 檔 ≈ 2,400-10,000 requests / 1-5 req/s；改 4-worker = ×4。而 `signal_thresholds.py` 記載你 2026-08-11 拍板「**不增加對 MoneyDJ 的請求數**」。必須配套 per-host token bucket + worker 數 UI 可調（預設 1） |
| **B** | **Tab1 詳細區改分頁 / Tab④ 保單管理改巢狀 tabs** | 最動你的工作流。`STATE.md` v19.405 明講留給你決定是否續做 |
| **C** | **管理室 vs 配置&帳本 的職責切分** | 「看持倉」有 3 個入口（皆唯讀）。要收斂成哪種動線是產品決策 |
| **D** | **健診 slider 移除 vs 接回** | 移除 = 誠實但少一功能；接回 = 多一欄但要解釋兩套燈號差異 |
| **E** | **雷達門檻 VIX 25→22、PCR 1.5→1.2** | **這會改變畫面上的警戒線位置**。雖然 SSOT 明確，但屬「使用者看得到的行為改變」 |
| **F** | **sidebar 開發者功能** 收 expander vs 搬 Tab5 | v19.336 待核准項，兩種都可行 |

---

## 5. 第二階段：執行編組與交付規範

### 5.1 分工

| 階段 | 負責角色 | 產出 |
|---|---|---|
| **實作** | 資深 Python / Streamlit 工程師 | 逐項修改 + 回歸測試 |
| **同批複核** | 資料稽核師（資料類）／UI-UX（介面類）／金融分析師（計算式類） | 各自領域的 sign-off |
| **最終驗收** | **獨立稽核 Agent（不參與實作）** | 逐條驗 `git diff`，見 §5.3 |

### 5.2 每次交付的自我審核（工程師執行，附於程式碼之後）

依你的規範，每批交付必附：

1. **邏輯審查** — 是否完全符合需求、有無邏輯斷層、有無改動到未授權範圍
2. **邊界測試（Edge Cases）** — 列出 2-3 個測試場景並說明程式碼行為。本專案必測的邊界（`CLAUDE.md §4.6`）：空資料集 / 單筆 / 全空值 / **新發行基金（歷史 < 1Y）** / **停售基金（連續無 NAV）** / **配息切割 ex-date 跳空** / **NAV 週末缺值** / **FX 單日 >1% 波動** / **MoneyDJ 子網域 403** / **proxy 降級**
3. **效能評估** — 時間與空間複雜度 + Streamlit cache 應用（含「這個改動會不會增加每次 rerun 的成本」）
4. **Debug 與修正** — 發現的潛在 bug 直接在最終程式碼修正並用註解標註
5. **最終程式碼** — 完整可貼上的版本

### 5.3 🔒 最終稽核關卡（獨立 Agent，不參與實作）

每一批修改 push 前，由**未參與該批實作**的稽核 Agent 逐條驗證：

| 檢查項 | 判準 |
|---|---|
| **真的修好了嗎** | 對照本報告該條的「現狀診斷」，用 Read/Grep 確認舊行為已消失、新行為存在 |
| **有沒有改壞既有行為** | `git diff` 全覽，確認沒有順手改到未授權範圍；特別檢查是否誤刪 §6 的「值得保留的設計」 |
| **§1 Fail Loud** | 有沒有新增 `fillna(0)` / 無說明 `ffill` / `except: pass` / dummy 值 |
| **§3.3 反捏造** | 新增的常數有沒有從 `shared/*` SSOT 引入；有沒有新的 inline magic |
| **§8.2 分層** | 有沒有新的跨層違規；新增的 L1 直呼有沒有登記 `CLAUDE.md §8.2.A` 例外表 + 檔內註解 |
| **§4.1 量綱** | 新增變數名有沒有編碼單位（`_pct` / `_ratio` / `_twd` / `_days_trading`） |
| **測試是真綠還是假綠** | **本輪已發現 2 個假綠測試**。稽核 Agent 必須確認：新增的測試在「把修好的 code 改回舊行為」時**會變紅** |
| **0-consumer 條款** | 新增的欄位/旗標，`grep` 確認 production 真的有 caller 讀它 |
| **stderr** | 新增的診斷訊息有沒有寫 `file=sys.stderr`（stdout 在 Cloud 看不到） |

**稽核 Agent 有權退回**。退回時必須指出具體 `檔名:行號` + 判準，不接受籠統評語。

### 5.4 驗收流程（依 `PROCESS.md §4`）

```
實作 → 自我審核（§5.2）→ 獨立稽核（§5.3）→ 你看 git diff → 你 commit + push
   → 手動 Reboot Streamlit Cloud（自動部署對本 app 不可靠）
   → 到 Cloud log 找這批新增的 stderr 訊息，確認診斷管道真的通了
```

### 5.5 建議節奏

| Sprint | 內容 | 時間 |
|---|---|---|
| **0** | P0 #1-4, #18, #21, #22 —— 全部是改幾行或改文案，直接消滅 7 個錯數字/假訊號來源 | **半天** |
| **1** | P0 #5-17, #19-20, #23 —— 「假成功 / 死控制項 / 造假 fallback」三大類清乾淨，並把三態約定寫進 `CLAUDE.md` | 3 天 |
| **2** | P0 #24 + P1 效能（#25-31）+ #32（一行先做） | 1 週 |
| **3** | P1 版面與瘦身（#33-40）—— **需先取得決策點 B/F 核准** | 1 週 |
| **4+** | P2 架構債，建議 `shared/data_sources.py` 優先（同時解掉說明書脫鉤、Tab5 假燈號、三份指標清單三個問題） | 依需求 |

---

## 6. 附錄

### 6.1 值得保留的設計（重構時勿誤刪）

| 位置 | 為什麼 |
|---|---|
| `tab1_macro.py:1107-1124` | ①結論→②依據→③例外→④可信度 四層架構，教科書級資訊架構 |
| `tab1_macro.py:345-358` | `_action_light_renderer` 未知燈色一律落 warning，**不下假綠燈** |
| `tab1_macro.py:707-711` | China Drag 主動防誤讀（「BCI 基準 100 ≠ PMI 50」）—— 應複製到其他指標 |
| `tab1_macro.py:540-547` | `_ACTION_BADGE_BG` 硬編碼的完整裁決註解 + 升級條件登記 —— **最負責任的硬編碼處置** |
| `tab2_single_fund.py:1656-1697` | 刪除 TER 假資料並留 14 行理由 + 面向使用者的誠實留白說明 |
| `tab2_single_fund.py:431-436` | 門檻文案直接 import SSOT 常數渲染 —— **其餘 magic number 該照抄的樣板** |
| `tab_batch_analysis.py:306-309` | 「**不會偷偷丟掉、也不會填假數字**」的失敗處理 |
| `tab3_portfolio.py:1789-1798, 1933-1941` | 「這四格的基數」「**它不是你戶頭現在的錢**」 |
| `tab3_portfolio.py:2577-2634` | `_DEFAULT_PRINC` 的完整揭露鏈 —— 硬編碼常數的正確做法 |
| `tab3_t7_ledger.py:76-129` | `_T7_SNAP_COL_CONFIG` 17 欄每欄都有公式說明 |
| `tab5_data_guard.py:155-161` | 「一般使用只需要看 ⓪ 與 ⑥」—— 最有效的降噪 |
| `tab5_data_guard.py:96-108` | `_get_holdings()` 統一取值路徑 —— TER 三處該照抄 |
| `registry_classify.py` docstring | 「範圍誠實聲明」把自己**做不到什麼**寫清楚 |
| `tab6_manual.py` docstring 鐵律 | 「說明書寫了但系統沒實作，比沒有說明書更糟」 |
| `tab6_manual.py` §D expander 標題 | 不寫死項數，「寫死數字等於保證某天對不上」 |
| `ui/helpers/session.py:118-152` | `friendly_error` = 例外型別+訊息+stderr 鏡射+traceback expander，**全站錯誤處理的標竿** |
| `services/health/dividend_calc.py:357-362` | 短歷史不年化的 Fail Loud guard |
| `infra/line_push.py` | 只在 HTTP 2xx 回 `sent=True`，**無假成功路徑** |
| `tab_manage.py:479` | import 移出 try 避免 `except LinePushError` 變 `NameError`（已修過） |
| `tab_manage.py:908-916` | 六塊白話導覽，明確區分「已經買」vs「還沒買」 |
| `capture.py:36-66` / `fx_regime.py:10-30` | success-only module cache —— 失敗結果不入快取的正確實作 |

### 6.2 本次稽核的方法論說明

- **全部以本機 clone 逐行 Read/Grep 驗證**，每條結論附 `檔名:行號` + 原文摘錄
- **8 條並行稽核線**，每條被明確要求「**發現既有結論有誤要明講**」—— 結果推翻了 v1 的 9 條
- 金額與計算式相關的判定**附數學式驗算**（見 §2 各 Tab）
- 端點字串、常數值、清單長度**逐一 grep 全 repo 交叉確認**

### 6.3 誠實標註的殘留不確定性

| 項目 | 說明 |
|---|---|
| `tab_manage.py:179-184` `st.columns(4)` 的手機表現 | 屬前端 runtime 行為，**無法由原始碼證實**。Streamlit 窄視窗會垂直堆疊，實際應是「清單變 4 倍長」而非「極窄並排」。建議實機截圖確認後再定調 |
| `unified.py:266` 缺 `ok` 排除導致的幽靈欄 | **靜態推導**，未經 runtime 驗證 |
| 批次 400 檔的請求量 2,400-10,000 | **估算**（每檔 6-25 requests），非實測 |
| `APP_VERSION` 落後 | `app.py` 寫 `v19.405`，`STATE.md` 已到 v19.433，檔內註解見 v19.456 → 建議同步 |

---

## 7. 等你的決定

第一階段到此為止，**沒有動任何一行程式碼**。

請告訴我：

1. **Sprint 0 的 7 項要不要直接開始？**（半天，全部是改幾行或改文案，每項都有本機驗證過的錯誤證據）
2. **決策點 A-F 的選擇**（§4 末表）—— 其中 **E（雷達門檻 VIX 25→22、PCR 1.5→1.2）** 特別需要你確認，因為它會改變畫面上警戒線的位置
3. 有沒有哪一條你認為判斷錯誤、或屬於已決 WONTFIX 但我漏看的？

---

*v2 · 2026-08-14 · 8 條並行稽核線 · 全部以本機 clone 逐行驗證 · 涵蓋 7 個頂層 Tab + 側邊欄*
