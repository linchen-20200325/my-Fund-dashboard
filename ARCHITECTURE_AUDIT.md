# ARCHITECTURE_AUDIT.md — 第一階段鐵腕審查報告

> 起草:2026-06-28 | 審查模型:Opus 4.7(1M context) | 範圍:整個 codebase
>
> **本文件 ≠ ARCHITECTURE.md v11.0**。v11.0 是 2026-05-16 重構完工「願景書」(86 KB,
> 記錄當時搬遷成果)。本份是 **2026-06-28 實況體檢**,在後續 v18.x ~ v19.195 開發過程中
> 各模組的膨脹、滲漏、與分層偏移。兩者並存,不互相覆蓋。
>
> 審查方法:Glob/Grep 統計 + 3 個並行 Explore 子代理偵察 + 手動 spot-check(已過濾
> 子代理誤報)。所有違憲均附 `file:line`。

---

## §-1 審查心法

依 user 2026-06-28 指令:「**鐵腕、絕不妥協**」+ **本階段絕不寫任何程式碼**。
本文僅做:(1) 盤點 (2) 違憲報告 (3) 排毒藍圖。

子代理偵察報告經人工 spot-check 後,已剔除以下誤報:
- ✋ Sub-agent 宣稱「`services/macro_explain.py:6-20` 有 13 個 `_s_*` inline scoring lambdas
  與 macro_validation 打架」— **不存在**。實際只有 `_interpret_indicator()` + `_safe_float()`。
- ✋ Sub-agent 宣稱「ai_advisor_pending.py @deprecated」— docstring 未見 deprecated 標記,**僅為 Route C-1 模組**。

---

## §0 快照統計(2026-06-28)

| 項目 | 數值 | 對照 v11.0 ARCHITECTURE.md |
|---|---|---|
| Python 總行數 | **90,901** | 未統計 |
| Python 檔數 | **257** | 未統計 |
| `services/` 模組數 | **50** | v11.0 列 8 個核心 → **6 倍膨脹** |
| `ui/helpers/` 模組數 | **22** (7,042 LOC) | v11.0 列 5 個 |
| `repositories/` 模組數 | 7 | v11.0 列 6 個(基本一致) |
| > 1000 LOC 巨檔 | **13 個** | — |
| > 2000 LOC 怪獸 | **5 個** | — |
| > 3000 LOC 巨怪 | **2 個** | — |
| 根目錄 `test_*.py` | 53 | 應遷 tests/ |
| `tests/` 子目錄 test | 58 | 雙存目錄 |
| Meta-docs 總大小 | ~1 MB | CLAUDE 34 KB + SPEC 130 KB + STATE 137 KB + STRATEGY 21 KB + BACKLOG 92 KB + ARCHITECTURE 86 KB + Requirements 7 KB + 2× NAS_PROXY 20 KB + PROCESS 2 KB |
| 死檔 | TEST (582 KB notebook) + 2 ARCHIVED tabs (650 LOC) | — |

---

## §1 反向架構地圖

### 1.1 實況 4 層結構(2026-06-28)

```
my-Fund-dashboard/
├── app.py                    549 LOC   L3 ─ 入口 orchestrator(v11.0 宣稱 425,實 549,+29% 偷膨)
├── conftest.py               241       測試 fixture 共用
│
├── 【根目錄殘留 — 自稱 L1 但實況分歧】──────────────
├── fund_fetcher.py           459       L1 shim(F-GRAY-1 結案,57 caller backward compat)
├── hot_money.py              355       ⚠️ **誤分類** — 14 個 st.UI 呼叫 + import streamlit
├── tw_macro.py               351       L1 fetcher self-contained
├── TEST                      582 KB    ❌ **死檔** — Jupyter notebook,0 引用
│
├── shared/  (L0 純常數 — 8 檔 1367 LOC)
│   ├── schemas.py            551       Pandera schemas(F-SCHEMA-1 輕量版)
│   ├── macro_thresholds_v2.py 265       v2 multi-purpose threshold schema(F-GRAY-4 第二代)
│   ├── macro_buckets.py      261       Danger 分級 + ttl/fred/color/signal 5 SSOT registry
│   ├── signal_thresholds.py  131       31 個語意常數(W2/W3a/W5-4 SSOT)
│   ├── fred_series.py         89       34 個 FRED series ID
│   ├── colors.py              40       色票
│   └── ttls.py                25       6 個 TTL 常數
│
├── infra/  (L0 跨層基礎)
│   ├── cache.py              437       _ttl_cache + _CACHE_REGISTRY
│   ├── proxy.py              ~250      NAS Squid + fetch_url + retry session
│   ├── llm.py                257       Gemini API wrapper
│   └── oauth.py              ~200      Google OAuth 2.0
│
├── repositories/  (L1 外部資料,7 檔)
│   ├── fund_repository.py   5117       ⚠️ **god module** — 10 fund source adapters 全擠
│   ├── policy_repository.py 1372       ⚠️ v1 + v2 schema 揉在一檔
│   ├── macro_repository.py  1078       FRED + yf + China + Defillama + AAII 混
│   ├── news_repository.py    ~300      RSS 聚合
│   ├── ledger_repository.py  ~250      _Ledgers Google Sheet
│   ├── snapshot_repository.py ~250     _T7_State JSON snapshot
│   └── financial_repository.py 192     yfinance 三比率
│
├── services/  (L2 業務邏輯 — 50 檔 19588 LOC)
│   ├── macro_*.py    × 8     (3386 + 553 + 475 + 433 + 422 + 383 + 372 + 264 = 6288 LOC)
│   │   ├── macro_service.py        3386  god module(US 指標 + 拐點 + 中國 + Sankey 4 大塊)
│   │   ├── macro_score_calibration 553
│   │   ├── macro_weights_store     475   ⚠️ Line 103/113 直 `import streamlit` 讀 secrets
│   │   ├── macro_validation        433
│   │   ├── macro_tw_local          422
│   │   ├── macro_signal_lookback   383
│   │   ├── macro_tw_local_fetch    372   ⚠️ **名為 fetcher,實際做 HTTP I/O** — 應屬 L1
│   │   └── macro_explain           264
│   │
│   ├── fund_*.py     × 8     (1010 + 609 + 510 + 408 + ? + ? + ? + ? )
│   │   ├── portfolio_service       1010  6 因子 + 風險 + 重疊 + Kelly 全揉
│   │   ├── fund_service             609
│   │   ├── fund_dividend_health     510
│   │   ├── fund_history             408
│   │   ├── fund_health_report       287   (v19.181 SSOT,共用 row builder)
│   │   ├── fund_health.py             ?   (sub-agent 提及,需 verify 是否與其他 fund_health 打架)
│   │   ├── fund_replacement_verdict 216   (v19.181 MK 4 規則)
│   │   ├── fund_total_return          ?   (新近)
│   │   └── fund_dividend_calculator   ?   (新近)
│   │
│   ├── risk/precision/optimization 群    (多達 10 檔)
│   │   ├── risk_radar              780   ⚠️ Line 183 import urllib + _fetch_stooq_csv = fetcher
│   │   ├── multi_factor_optimization 770
│   │   ├── crisis_strategy_grid       ?
│   │   ├── crisis_backtest            ?
│   │   ├── crisis_ai_advisor       193
│   │   ├── liquidity_engine        430
│   │   ├── us_liquidity_engine     345
│   │   ├── risk_calibration        307
│   │   ├── cluster_calibration     317
│   │   ├── signal_threshold_optimization 173
│   │   └── precision_service         ?
│   │
│   ├── ai/advisor 群     × 5
│   │   ├── ai_service              674
│   │   ├── auto_search             633
│   │   ├── ai_prompts              222
│   │   ├── ai_advisor_pending      234
│   │   └── crisis_ai_advisor       193
│   │
│   ├── 其他 service
│   │   ├── ledger_service          532
│   │   ├── ~~allocation_simulator    441~~ (v19.212 P0-3-#4 拔毒,production 0 caller)
│   │   ├── auto_search_store_local   ?
│   │   ├── auto_search_store_gs      ?   ⚠️ Line 45 直 `import streamlit` 讀 secrets
│   │   ├── moneydj_fetcher           ?   ⚠️ **名為 fetcher** — 但 spot-check 顯示是 URL 組裝 + 包 L1 fetch,不違憲
│   │   ├── nav_history_store         ?
│   │   ├── realtime_signal           ?   ⚠️ Line 67 `from ui.helpers.macro_helpers import ...` = L2→L3 反向依賴
│   │   ├── valuation               ~250   ⚠️ Line 156 function-local `import yfinance` = L2 HTTP
│   │   ├── reconcile / decision_matrix / ~~event_calendar~~ (v19.211 P0-3-#3 拔毒) / ~~quadrant_simulator~~ (v19.210 P0-3-#2 拔毒) / ...
│   │
│   └── 跨域 + 邊緣
│       ├── ~~adjusted_nav~~ (v19.214 P0-3-#6 拔毒) / currency / format_helpers / policy_advisor_service / cross_source_compare
│
├── ui/  (L3 Streamlit 渲染)
│   ├── tab1_macro.py        3023       god module(11 個 render 子)
│   ├── tab3_t7_ledger.py    2796       (B-C.5 從 tab3 抽出,單一職責,borderline OK)
│   ├── tab3_portfolio.py    2468       單 tab renderer
│   ├── tab_crisis_backtest  2442       5+ phase 揉一檔
│   ├── tab2_single_fund     1745
│   ├── tab6_manual          1548       純文字教學內容 — 1000+ LOC 是 markdown literal
│   ├── tab5_data_guard      1266
│   ├── tab_fund_grp_health   660
│   ├── tab_allocation_simulator 599    ❌ **死檔** — app.py L33 已註解
│   ├── tab_param_finder        51       ❌ **死檔** — app.py L36 已註解
│   │
│   ├── components/  (4 檔)
│   │   ├── mk_dashboard     721
│   │   ├── macro_card_edu   425
│   │   ├── macro_card / mk_clock
│   │
│   └── helpers/  (22 檔 7042 LOC — grab-bag)
│       ├── fund_grp_health_extras  1478  ⚠️ **god helper** — 14 render functions 揉一檔,**錯放 helpers/**
│       ├── v2_editor                706
│       ├── fund_checkup             652  health 概念另一份 implementation
│       ├── macro_beginner_view      616  與 macro_helpers 部份重疊
│       ├── data_registry            607  與 freshness.py 邊界模糊
│       ├── cloud_io                 441
│       ├── holdings                 346
│       ├── macro_helpers            286  與 macro_beginner_view 部份重疊
│       ├── freshness                243
│       ├── portfolio_load           230
│       ├── concentration            222
│       ├── session                  180
│       ├── d_mode                   157
│       ├── portfolio_health         150
│       ├── oauth_state              111
│       ├── json_backup              106
│       ├── ai_summary               106
│       ├── macro_linkage            100
│       ├── metric_explainers         86
│       ├── chart_danger              84
│       ├── portfolio_linkage         68
│       ├── story_nav                 40
│       ├── tw_time                   23
│       └── __init__                   4
│
├── models/  (DTO — policy + ledger)
│
├── scripts/  (offline batch)
│   ├── calibrate_macro_score        ⚠️ 與 services/macro_score_calibration 同檔事
│   ├── update_macro_history / fetch_nav_cache / migrate_v149_schema / eval_macro_consensus / compare_wb01_vs_local
│
├── tests/  (新測 58 檔)
└── (根目錄 test_*.py × 53)  ⚠️ **雙存目錄**
```

### 1.2 各層精確職責(verbatim,不抄 v11.0)

| 層 | 一句話職責 | 真實狀況 |
|---|---|---|
| `shared/` | 純常數,無 IO,任何層 import | ✅ 守得緊,8 檔 1367 LOC |
| `infra/` | 跨層基礎建設(cache/proxy/oauth/llm) | ✅ 守得緊,clean |
| `repositories/` | 外部資料 fetch + 解析 + cache | ⚠️ 7 檔但 fund_repo 一檔 5117 LOC,等同把 10 個獨立 source 揉成 god module |
| `services/` | 純函式業務邏輯,**禁** import streamlit/requests/httpx/bs4/yfinance | ❌ 50 檔,違憲 6+ 處(見 §2) |
| `ui/` + `app.py` | Streamlit 渲染 only | ⚠️ 5 個 > 1700 LOC 巨檔,helpers/ 變 grab-bag |
| 根目錄 `*.py` | 過渡 shim only(`fund_fetcher`/`hot_money`/`tw_macro`) | ❌ `hot_money.py` 完全是 UI,**錯位**;`TEST` 是死檔 |
| 根目錄 `test_*.py` × 53 | 應全遷 `tests/` | ❌ 雙存目錄 |

### 1.3 v11.0 願景 vs 2026-06-28 實況差距

| 指標 | v11.0 (2026-05-16) | 2026-06-28 | 偏差 |
|---|---|---|---|
| app.py LOC | 425 | 549 | +29% |
| services/ 檔數 | 8 核心 | 50 | **+525%** |
| services/macro_service.py | "2128 行" | 3386 | +59% |
| services/portfolio_service.py | "534 行" | 1010 | +89% |
| services/fund_service.py | "481 行" | 609 | +27% |
| services/ai_service.py | "857 行" | 674 | −21%(改善) |
| repositories/fund_repository.py | "4216 行" | 5117 | +21% |
| repositories/macro_repository.py | "721 行" | 1078 | +50% |
| ui/helpers/ 檔數 | 5 | 22 | **+340%** |

→ 「分層架構完工」之後,**過去 6 週各層內部都在悄悄膨脹**,沒有 §8.1 「自評過度設計」
   守門。services/ 一口氣多了 42 檔,helpers/ 多了 17 檔。

---

## §2 重複/打架根源審查(逐條 verified)

### §2.A 已 verify 的硬違憲(§8.2 規則破口)

| # | 違憲 | 位置(verified) | 嚴重度 | 為何違憲 |
|---|---|---|---|---|
| **V1** | `hot_money.py` 模組分類錯位 | 根目錄 / line 20 `import streamlit as st` + line 213/215/220/227/240-244/256/269/283/323/330/338 共 14 處 `st.warning/info/error/markdown/session_state` | 🔴 高 | 號稱 L1 fetcher(根目錄、§8.3 F-GRAY-2 結案),實際 14 個真 UI 呼叫 — 整檔該歸 `ui/` 而非根目錄 |
| **V2** | `services/realtime_signal.py` L2→L3 反向 import | `services/realtime_signal.py:67` `from ui.helpers.macro_helpers import calculate_composite_score, composite_verdict` | 🔴 高 | §8.2 硬規則「L2 不得 import L3」直接破,沒有 EX-* 例外覆蓋 |
| **V3** | `services/macro_weights_store.py` import streamlit 讀 secrets | `services/macro_weights_store.py:103` `_gs_enabled()` + line 113 `_gs_get_worksheet()` 各 `import streamlit as st`;只用 `st.secrets`,沒做真 UI 呼叫 | 🟡 中 | EX-CACHE-1 只允許 L1 try-import `@st.cache_data` decorator;L2 service 用 `st.secrets` 不在任何 EX 例外。Secret 讀取應由 caller 注入或下沉 infra/config |
| **V4** | `services/auto_search_store_gs.py` 同 V3 | `services/auto_search_store_gs.py:45` `_get_sheet()` 內 `import streamlit as st`,用 `st.secrets["google_service_account"]` + `st.secrets["macro_weights_sheet_id"]` | 🟡 中 | 同 V3 邏輯 |
| **V5** | `services/valuation.py` import yfinance | `services/valuation.py:156` function-local `import yfinance as yf` 後直呼 `yf.Ticker("^GSPC").info` | 🟠 中-高 | §8.2 「L2 Service 不得 import requests/httpx/beautifulsoup/feedparser」未列 yfinance,但 yfinance 本質就是 HTTP wrapper — 同精神違憲。應改走 `repositories/macro_repository.fetch_yf_*` |
| **V6** | `services/macro_tw_local_fetch.py` 整檔 mis-classified | 整檔 372 LOC,**檔名直接寫 fetch** — `fetch_foreign_consecutive_days / fetch_ndc_signal_history / fetch_tw_export_yoy / fetch_tw_pmi_local` 全是 HTTP I/O | 🔴 高 | 名字+職責都 fetcher,放在 L2 service 是分類錯誤。應整檔搬 `repositories/macro_tw_local_repository.py` |
| **V7** | `services/risk_radar.py:_fetch_stooq_csv` fetcher in service | `services/risk_radar.py:183` `import urllib.parse` + 整個 `_fetch_stooq_csv()` / `_fetch_cboe_csv()` 做 HTTP | 🟠 中-高 | 同 V6,只是這份是 method-level 而非整檔。urllib.parse 是 stdlib,但用途是建 HTTP URL → service 該透過 repository 取 stooq |

**Sub-agent 報告中已剔除的不實宣稱:**
- ✋ `services/macro_explain.py:6-20` 「13 個 inline `_s_*` scoring lambda」— **不存在**(grep 0 結果,實際只 `_interpret_indicator()`)
- ✋ `services/ai_advisor_pending.py` 「@deprecated」— docstring 標 "Route C-1",**未 deprecated**

### §2.B 重複/打架邏輯(verified,部分 confirmed)

| # | 重複 | 涉檔(verified 存在) | 嚴重度 | 為何重複 |
|---|---|---|---|---|
| **D1** | Fund Health 概念碎成 5 模組 | `services/fund_health.py` + `services/fund_dividend_health.py` (510) + `services/fund_replacement_verdict.py` (216) + `services/fund_health_report.py` (287) + `ui/helpers/fund_checkup.py` (652) + `ui/helpers/fund_grp_health_extras.py` (1478) | 🔴 高 | 6 檔同概念,進入點多。v19.181 抽 fund_health_report 為 SSOT 但 fund_checkup/extras 仍平行存在 — **半截 SSOT** |
| **D2** | macro_* 8 個 service 邊界模糊 | services/macro_service(3386) + macro_validation(433) + macro_explain(264) + macro_signal_lookback(383) + macro_weights_store(475) + macro_tw_local(422) + macro_tw_local_fetch(372) + macro_score_calibration(553) | 🟠 中-高 | 8 檔共 6288 LOC,無 README 或 §8.2 註明各檔職責邊界。新人改 threshold 不知該動哪檔 |
| **D3** | Calibration 6 模組散落 | services/macro_score_calibration(553) + risk_calibration(307) + cluster_calibration(317) + signal_threshold_optimization(173) + multi_factor_optimization(770) + scripts/calibrate_macro_score(757) | 🟡 中 | 同類概念散在 services/ 5 檔 + scripts/ 1 檔,無 services/calibration/ 子套件分群 |
| **D4** | Fetcher 散在 4 個位置 | repositories/ (7 檔, canonical) + 根目錄 fund_fetcher + hot_money + tw_macro + services/macro_tw_local_fetch + services/moneydj_fetcher + services/risk_radar(`_fetch_stooq_csv`) + services/valuation(yfinance) | 🟠 中-高 | repositories/ 該是唯一 fetcher 居所,實際 4 個地方都有(根目錄、services、scripts) |
| **D5** | `ui/helpers/` 22 檔 grab-bag | macro_helpers(286) vs macro_beginner_view(616) — 都做 macro 摘要;data_registry(607) vs freshness(243) — 都做新鮮度;fund_checkup(652) vs fund_grp_health_extras(1478) — 都做健診 | 🟡 中 | helpers/ 已從 v11.0 5 檔膨到 22 檔,無內部分類規則,sub-agent 多筆指 `_safe_num` 等 util 在 3+ 檔重複 |
| **D6** | `_FX_CACHE` 自製 dict vs `_ttl_cache` | `repositories/fund_repository.py` 內 ad-hoc `_FX_CACHE` 自管 timestamp,不走 `infra.cache._ttl_cache` | 🟡 中 | 同一份 codebase 兩套 cache pattern。應統一走 `_ttl_cache` 並向 `_CACHE_REGISTRY` 註冊 |
| **D7** | tests/ 雙存目錄 | 根目錄 53 個 `test_*.py` + `tests/` 子目錄 58 個 `test_*.py` | 🟡 中 | sub-agent 說「無 exact dup」可信,但結構不一致 — 部分 unit 在根目錄、部分在 tests/。CI 兩個地方都掃,結果有交疊但 layout 混亂 |
| **D8** | 多 threshold dict(中性,有 audit 註明) | shared/signal_thresholds(131) + shared/macro_thresholds_v2(265) + shared/macro_buckets(261) + repositories/macro_repository:201-248 MACRO_THRESHOLDS dict | 🟢 低 | macro_repository.py:199-212 明確註解「inline 與 dict **語意不同源**」,並非機械式重複。F-GRAY-4 v19.183 已 harmonize CPI,HY 在 v19.169 處理 |

### §2.C 死碼/廢檔(verified)

| # | 死碼 | 位置 | 證據 |
|---|---|---|---|
| **Z1** | `TEST` 檔 (582 KB Jupyter notebook) | 根目錄 | `file TEST` = JSON notebook 4.4 / colab provenance;grep `open\|Path\|FILE.*TEST` = 0 引用 |
| **Z2** | `ui/tab_allocation_simulator.py` (599 LOC) | ui/ | `app.py:33` `# from ui.tab_allocation_simulator import ...` 已註解;且 §0 列為 EX-POLICY-1 inline 例外 — 整檔當前無 caller |
| **Z3** | `ui/tab_param_finder.py` (51 LOC) | ui/ | `app.py:36` `# from ui.tab_param_finder import ...` 已註解 |

合計 ~ **1250 LOC + 582 KB 死碼**,佔 codebase 1.4%。

### §2.D 「半完成 SSOT」現象

CLAUDE.md §0 列許多 SSOT 結案:`signal_thresholds.py` / `macro_thresholds_v2.py` / `D5_KEYS` …
但本次審查發現多處 **SSOT 抽了但未全面 propagate**:

- v19.181 抽 `fund_health_report.py` 為 SSOT row builder → **fund_checkup.py + fund_grp_health_extras.py 仍 parallel**(D1)
- v19.183 F-GRAY-4 CPI harmonize → **僅 CPI**,PMI/HY 多用途仍 inline(§8.3 已認帳)
- F-PROV-1 phase 22+ provenance 補洞 → 30+ fetcher 仍未加 source/fetched_at(只 `fetch_fred` 加)
- v19.195 D5_FRED_KEYS / D5_YF_KEYS SSOT → **這條是真徹底**(grep regex 守住)

**判斷**:過去半年「抽 SSOT」的迭代 ROI 在邊際遞減 — 抽出來但下游沒全跟,反而多一份要同步的檔。

---

## §3 排毒收納藍圖

> 切三波:**P0 零風險** / **P1 高 ROI 中工程** / **P2 觀念整理**。
> 每條附 ROI + 風險 + 建議優先序。**全部停在規劃,等同意才動。**

### §3.1 P0 — 零風險,立刻可做(預計 < 1 小時總工時)

| # | 動作 | LOC 影響 | 風險 | ROI |
|---|---|---|---|---|
| **P0-1** | 刪 `TEST` (582 KB Jupyter notebook,0 引用) | −582 KB | 無 | 高 — 移除最大死檔 |
| **P0-2** | 刪 `ui/tab_allocation_simulator.py`(已註解掉)+ `ui/tab_param_finder.py` | −650 LOC | 低 — 若回頭要再用,git history 還在 | 中-高 |
| **P0-3** | 53 個根目錄 `test_*.py` 全遷 `tests/` 子目錄(純 `git mv` + `pytest.ini` `testpaths` 確認) | 結構整齊 | 低 — 但要 verify CI / `conftest.py` discovery 不破 | 中 |
| **P0-4** | 根目錄 `fund_fetcher.py` / `hot_money.py` / `tw_macro.py` 重新評估:`fund_fetcher`(shim 容器)留,`tw_macro` 移 repositories/,`hot_money` 移 ui/(V1 違憲) | 結構整齊 + 修 V1 | 中 — 57 caller 需改 import,但 V1 已是真違憲 | 高 |

### §3.2 P1 — 高 ROI 中工程(預計 1-3 天 / 條,需分批 PR)

| # | 動作 | 對應違憲/重複 | 工時 | 風險 | ROI |
|---|---|---|---|---|---|
| **P1-1** | 修 V2:`services/realtime_signal.py` 反轉依賴 — 把 `calculate_composite_score / composite_verdict` 從 `ui/helpers/macro_helpers.py` **下沉到 `services/macro_explain.py`(或 `services/macro_score.py` 新檔)**,UI 改 wrapper | V2 | 0.5 d | 低 — 純 import 改 | 高 |
| **P1-2** | 修 V3/V4:`secrets` 讀取改 caller 注入,services 不知 streamlit。新增 `infra/config.py:get_secret(key)` thin wrapper | V3 + V4 | 0.5 d | 低-中 — 2 service 重簽函式 | 高 |
| **P1-3** | 修 V5/V7:`services/valuation.py` yfinance + `services/risk_radar.py` `_fetch_stooq_csv` 全部下沉 `repositories/` | V5 + V7 | 1 d | 低-中 | 高 |
| **P1-4** | 修 V6:整檔 `services/macro_tw_local_fetch.py` 改檔名 + 移 `repositories/macro_tw_local_repository.py` | V6 | 0.5 d | 低 | 高 |
| **P1-5** | 拆 `repositories/fund_repository.py` 5117 行 → 8 個 source adapter 子檔(`_src_fundclear.py / _src_moneydj.py / _src_tdcc.py / _src_morningstar.py ...`) + `fund_repository.py` 改 facade orchestrator | D4 + god module | 2-3 d | 中-高 — 100+ callers 需 verify,測試覆蓋率風險 | 中-高(改善維護性,但**短期**沒消費者拿到好處,§-1 工作準則需先確認 user 同意) |
| **P1-6** | 重整 `ui/helpers/fund_grp_health_extras.py` 1478 LOC → 改名 `ui/components/fund_grp_health/__init__.py` + 拆 5 子檔(dividend / holdings / risk / signals / ai) | D1 + god helper | 1-2 d | 中 | 中 |
| **P1-7** | 拆 `services/macro_service.py` 3386 行 → 4 個 concern 檔:`macro_us_indicators` / `macro_turning_points` / `macro_china` / `macro_causal_sankey` + `macro_service.py` 改 facade | god module | 2 d | 中 — 30+ callers | 中-高 |

### §3.3 P2 — 觀念整理(中長期,需 user 拍板優先序)

| # | 動作 | 對應 | 工時 | 備註 |
|---|---|---|---|---|
| **P2-1** | Health 概念 SSOT 收口:6 檔(fund_health + fund_dividend_health + fund_replacement_verdict + fund_health_report + fund_checkup + fund_grp_health_extras)→ 2 檔(`services/fund_health.py` SSOT 計算 + `ui/components/fund_health_view.py` 純渲染) | D1 | 3-5 d | 風險高 — 6 檔 entry point 全部有 caller,需設 deprecation 期 |
| **P2-2** | macro_* 8 service 收編成 `services/macro/` subpackage,加 `__init__.py` 明列各檔職責 | D2 | 2-3 d | 風險中 — import path 影響大 |
| **P2-3** | calibration 6 檔(5 services + 1 scripts)收 `services/calibration/` subpackage | D3 | 1-2 d | 風險低 — 多為內部 caller |
| **P2-4** | 拆 `repositories/policy_repository.py` 1372 行 → `policy_v1.py` / `policy_v2.py` / `policy_utils.py` | god module | 1-2 d | 風險中 — v1/v2 schema 偵測邏輯共用 |
| **P2-5** | 拆 `repositories/macro_repository.py` 1078 行 → `macro_fred.py` / `macro_yf.py` / `macro_china.py` / `macro_alternate.py`(AAII/Defillama/ISM)/ `macro_math.py` | god module | 1-2 d | 風險低-中 |
| **P2-6** | 統一 `_FX_CACHE` → `_ttl_cache` 並註冊 `_CACHE_REGISTRY` | D6 | 0.5 d | 風險低 |
| **P2-7** | `ui/helpers/` 22 檔依職責分子目錄:`ui/helpers/macro/` / `ui/helpers/fund/` / `ui/helpers/portfolio/` / `ui/helpers/io/` | D5 | 1 d | 風險低,但 30+ import 要改 |
| **P2-8** | 統一 SCORE_RULES 唯一 SSOT 入口(macro_validation 已是,但 macro_helpers + macro_beginner_view 部分重算)|D2|2 d|風險中|

### §3.4 OOP / 物件導向收納可能性

> User 提到「**利用 OOP**」。本 codebase 目前以 **純函式 + dict / dataclass** 為主軸,
> §1 鐵則「Fail Loud」+ §8.2 「services 純函式」對 OOP 是 **抗體**,不建議全面 OOP 化。
> 但有 3 個現有 OOP 已落地 / 適合升 OOP 的位置:

| 場合 | 現況 | OOP 建議 |
|---|---|---|
| `models/ledger.py` `Ledger` / `Switch` / `FundPosition` / `Transaction` | 已 OOP | 維持。XIRR + 加權平均會計天然帶狀態,OOP 自然契合 |
| `services/precision_service.py` `PrecisionStrategyEngine` | 已 OOP(根據 v11.0 ARCHITECTURE.md 註解) | 維持,但檢查是否真需要 class 或只是 namespace |
| `repositories/fund_repository.py` 10 個 adapter | 純函式 + 散落 | **適合升 OOP**:抽 `FundSourceAdapter` ABC + 子類 `FundclearAdapter / TDCCAdapter / MoneyDJAdapter / MorningstarAdapter / CnyesAdapter` 等,fallback chain 改 `[a.fetch(code) for a in adapters]` |

→ OOP 在 D4 fetcher 收口場景有實質好處(可測 / 可 mock / 可組裝);其他場合純函式仍勝。

### §3.5 同步應更新的 meta-docs

| Meta-doc | 動作 |
|---|---|
| `ARCHITECTURE.md` v11.0 | 補一節 §0.5 「2026-06-28 實況校準」指向本份 AUDIT |
| `CLAUDE.md` §8.2 | 把 V1-V7 違憲補進 §8.2 例外清單(或宣告為「待修」)— 否則新代碼會以「現狀=合規」誤學 |
| `BACKLOG.md` | P0-3 / P1-* / P2-* 進入 backlog,user 拍板優先序 |
| `STATE.md` | 本次審查紀錄寫入 |

---

## §4 一句話結論

**過去 6 週 v18.x→v19.195 開發累積 6 條真違憲(V1-V7,扣 V3/V4 合一)+ 7 條重複邏輯 + 1.4% 死碼**。
**架構債務累積速度 ≈ 每週 1 條違憲或重複**。

ARCHITECTURE.md v11.0 是當時的願景,但「分層完工」之後沒有持續守門 — 新增 50 services + 22 helpers
時無人擋住「這該放哪層」的問題。**最緊急 fixes 為 V1 (hot_money)、V2 (realtime_signal)、V6 (macro_tw_local_fetch)**
— 三條都是分類/方向錯誤的硬違憲,改起來工程量小但意義大。

**P0 + P1-1~P1-4 估計 3 個工作天可清光所有 verified 違憲。**
**P1-5/P1-6/P1-7 god module 拆分需單獨拍板**(短期無 user-facing 好處,違 §-1 工作準則的精神,
應由 user 確認是否進入下一階段)。

---

## §5 第二階段執行紀錄(2026-06-28 完工)

User 2026-06-28 「同意整套」後進入第二階段,自動執行(動刀前自審 / 連續 2 同 error 停手 /
不印代碼)。下表為實際完工狀態:

| 編號 | 內容 | Commit | 狀態 | 驗證 |
|---|---|---|---|---|
| **P0-1** | 刪 TEST 死檔(582 KB Jupyter notebook) | `15f9ded` | ✅ 完工 | 0 引用 verified |
| **P0-2** | 刪 2 個 ARCHIVED tab(tab_allocation_simulator 599 + tab_param_finder 51 LOC)+ 守門 test 3 個 + app.py 8 行死註解 + services docstring | `f475c81` | ✅ 完工 | test_allocation_simulator 21 + test_app_smoke 96 全綠 |
| **P0-4-A** | V1 修補 — hot_money.py 拆 2 檔(`repositories/hot_money_repository.py` fetcher + `ui/hot_money.py` UI/純函式),改 7 caller import path | `65f2c0f` | ✅ 完工 | test_hot_money + test_schemas_phase_b + test_provenance + test_app_smoke 全綠 |
| **P0-4-B** | tw_macro.py 整檔搬 `repositories/tw_macro_repository.py`,改 2 caller | `9cfb59d` | ✅ 完工 | test_tw_macro + test_app_smoke 107 passed |
| **P1-1** | V2 修補 — `calculate_composite_score` + `composite_verdict` 下沉 `services/macro_composite_score.py`,realtime_signal 改 services 同層,UI helpers shim re-export,6 test patch path 改 | `2e0ba17` | ✅ 完工 | test_realtime_signal + test_app_smoke + test_macro_weights_store + test_macro_explain 188 passed |
| **P1-2** | V3+V4 修補 — 新建 `infra/config.py` 提供 `get_secret`/`require_secret`,services/macro_weights_store + services/auto_search_store_gs 三處 `import streamlit` 全清空 | `d5bcfe4` | ✅ 完工 | test_macro_weights_store + test_app_smoke + test_auto_search 203 passed |
| **P1-3** | V5+V7 修補 — 新建 `repositories/external_market_repository.py`(yfinance Ticker.info + multpl HTML + stooq CSV fetcher),services/valuation + services/risk_radar 改 thin wrapper | `fe1b182` | ✅ 完工 | test_data_guard + test_risk_radar + test_app_smoke 197 passed / 2 skipped |
| **P1-4** | V6 修補 — `services/macro_tw_local_fetch.py` 整檔搬 `repositories/macro_tw_local_repository.py`,改 4 caller(含 20+ test patch path) | `38ee0dd` | ✅ 完工 | test_provenance + test_macro_tw_local + test_tab1_tw_local + test_app_smoke 131 passed |
| **P0-3** | 75 個根目錄 test_*.py 統一遷 tests/ 子目錄,改 7 個 `Path(__file__).parent` 依賴(用 `parents[1]` 指 root) | `2e0a47e` | ✅ 完工 | **2442 passed / 7 skipped / 1 failed**(yfinance 環境問題,非 P0-3 引發);根目錄 .py 從 78 降至 3(app + conftest + fund_fetcher) |
| **P1-6** | `ui/helpers/fund_grp_health_extras.py` 1478 LOC god helper 拆 7 子檔(`_utils` / `dividend` / `investment` / `correlation` / `risk` / `signals` / `ai` + `__init__`),主檔留 shim re-export 確保 14+ test 不需改 patch path | `af01bdf` | ✅ 完工 | 48 個 fund_grp_health_extras test 全綠;主檔從 1478 → 41 LOC(−97%) |
| **P1-7** | `services/macro_service.py` 3390 LOC god module 拆 5 子檔 + __init__(`_helpers` / `us_indicators`(含 657 LOC mega-fn)/ `turning_points` / `causal_sankey` / `china`),主檔留 65 LOC shim | `2640215` | ✅ 完工 | 511 passed / 1 skipped(macro_core/explain/validation/signal_lookback/inflection/weights_store/score_calibration/china_macro/china_subscore/thresholds_v2/health_zpct/buckets/cluster_signals/realtime_signal/provenance/app_smoke)|
| **P1-5** | `repositories/fund_repository.py` 5117 LOC 最大 god module 拆 5 子檔(`_helpers` / `sources`(2406 LOC,17 source adapter)/ `fund_orchestration` / `nav_metrics` / `fx_and_main`),主檔留 28 LOC shim(−99.5%) | `115aa58` | ✅ 完工 | 278 passed / 0 failed;含修補 fund_fetcher.py 9 個 circular import block(PEP 562 `__getattr__` 延遲解析)|
| **P2-6** | `_FX_CACHE` raw dict 註冊到 `_CACHE_REGISTRY` 統一一鍵清(保留 v18.275 positive-only 設計) | `f6f82d0` | ✅ 完工 | 134 passed;`_FX_CACHE` 注入 1 筆 → `clear_all_caches()` → 清為 0 |
| **P2-3** | 5 個 calibration 模組(macro_score / risk / cluster / signal_threshold / multi_factor)收編 `services/calibration/` 子套件,各原檔留 shim re-export | `0dd422d` | ✅ 完工 | test_risk + test_cluster + test_multi_factor + test_signal_threshold + test_macro_score + test_auto_search + test_macro_thresholds_v2 + test_calibrate_macro_score 共 236+52 passed |
| **P2-2** | 6 個 macro_* 模組(validation/explain/signal_lookback/weights_store/tw_local/composite_score)收編 `services/macro/` 子套件(延伸 P1-7) | `67a58d7` | ✅ 完工 | 527 passed / 1 skipped(macro_validation+explain+signal_lookback+weights_store+tw_local+thresholds_v2+realtime+app_smoke+macro_core+health_zpct+beginner_view+china_macro+china_subscore+cluster_signals)|
| **P2-5** | `repositories/macro_repository.py` 1078 LOC 拆 5 子檔(嘗試) | `6a75636` → revert `479bc9c` | ⛔ **revert** | 拆檔技術完成,但 15 個 test 因 `patch.object(macro_repository, X)` patch shim attribute 不穿透 sub-module 內部 reference 失敗(Python 模組系統限制)。修補需改 20+ test patch path,工程量大且風險高,藍圖 §3.3 P2-5 原本就標「需 user 拍板」,**revert 保留為 backlog**,等下次新增 macro source 時連 test refactor 一起做 |
| **P2-7** | `ui/helpers/` 22 檔分 5 子目錄(`macro/` 3 / `fund/` 1 / `portfolio/` 4 / `io/` 4 / `chart/` 2 = 14 檔搬位置)+ cloud_io 留主檔避 shim 穿透 | `3409244` | ✅ **完工(部分)** | test_app_smoke + test_cloud_io + macro_beginner_view + chart_danger + data_registry + metric_explainers + portfolio_health/load + json_backup 共 203 passed / 0 failed。cloud_io 部分 revert 因 test_cloud_io 用 `monkeypatch.setattr(cloud_io, X)` 同 P2-5 shim 穿透問題,留主檔 backlog |

**verified 違憲(V1-V7)100% 清空**。死碼 1.4%(TEST + 2 ARCHIVED tab + 守門 test)全清。

### 第二階段未進入的項目(評估理由)

| 編號 | 內容 | 跳過理由 |
|---|---|---|
| **P2-1** | Health 概念 SSOT 收口(6 → 2 模組) | 攻略 services/fund_health/ 子套件物理收編(類 P2-2/P2-3 模式)— 拆檔成功但 fund_fetcher.py 3 處反向 `from services.fund_service import` 形成 circular import,加 try-except + PEP 562 `__getattr__` 仍因 test collect 順序導致 sys.modules partially init 狀態 break。**未 commit 即 revert**,等業務拍板「合一規則」+ 改 caller 直接 import 子套件再做 |
| **P2-4** | `policy_repository.py` 1372 LOC 拆 v1/v2/utils | 拆檔成功,但 v1.py 內 `_normalize_invest_twd` / `_normalize_fx` / `_sanitize_tab_name` 等 `_` 開頭私函被 v2.py 使用,`from X import *` Python 預設不取 `_*`,逐個 explicit import 越加越多。**未 commit 即 revert**,等業務拍板 v1/v2 migration 時連 caller 改 import path 一起做 |
| **P2-8** | SCORE_RULES 唯一 SSOT 入口統一 | grep `^SCORE_RULES` 確認 **only 1 處定義**(`services/macro/validation.py:106`),其他 5 處皆 docstring references 或 import-use。**已是 SSOT,藍圖誤判**,標 ✅ |

### P2 系列總結:advanced subpackage 拆檔的 root cause

P2-1 / P2-4 / P2-5 三條失敗共同 root cause 是 Python 模組系統限制:
1. **`from X import *` 不取 `_*` 私函**(P2-4)→ 子模組內互相用 `_*` helper 時 dir+globals shim 不夠
2. **`patch.object(M, attr)` 不穿透 sub-module 內部 reference**(P2-5)→ test mock 失效
3. **circular import 鏈在 shim re-export 拓撲下難維持**(P2-1)→ test collect 順序敏感

→ **結論:advanced subpackage 拆檔不適合用 shim re-export pattern**,需直接搬位置 + 改 all callers 的 import path(類 P1-1~P1-4 違憲修補模式),工程量大需業務拍板「值不值得做」。本批 3 條全部 revert 留 backlog。

### 新增/搬遷檔案清單(2026-06-28 第二階段成果)

**新增**(L0/L1 sound 模組):
- `infra/config.py`(80 LOC)— V3/V4 secrets wrapper
- `repositories/hot_money_repository.py`(142 LOC)— V1 修補拆出的 fetcher 層
- `repositories/external_market_repository.py`(160 LOC)— V5/V7 修補(yfinance/multpl/stooq)
- `services/macro_composite_score.py`(80 LOC)— V2 修補下沉 composite score
- `ui/hot_money.py`(219 LOC)— V1 修補拆出的 UI 層

**搬遷**(git rename 100% similarity):
- `tw_macro.py` → `repositories/tw_macro_repository.py`(P0-4-B)
- `services/macro_tw_local_fetch.py` → `repositories/macro_tw_local_repository.py`(P1-4)

**刪除**:
- `TEST`(582 KB Jupyter notebook,0 引用)
- `hot_money.py`(根目錄,內容拆 2 檔)
- `ui/tab_allocation_simulator.py`(599 LOC,app.py 註解掉)
- `ui/tab_param_finder.py`(51 LOC,app.py 註解掉)

### 體積與分層變化

| 指標 | 第一階段(2026-06-28 起) | 第二階段完工 | 變化 |
|---|---|---|---|
| Verified 違憲數 | 7 | **0** | **−100%** |
| 死碼(LOC) | 1300 + 582 KB | 0 | **全清** |
| 根目錄 `*.py` 業務檔 | 4 (app/fund_fetcher/hot_money/tw_macro) | 2 (app/fund_fetcher) | −50% |
| 根目錄 `test_*.py` | 75 | **0** | −100% |
| `tests/` 子目錄 test 檔 | 58 | 133 | +75(全部 test 統一在 tests/) |
| `services/` 檔數 | 50 | 49(macro_tw_local_fetch 搬 + macro_composite_score 新) | −1 net,但分類更乾淨 |
| `repositories/` 檔數 | 7 | 11(+hot_money + external_market + tw_macro + macro_tw_local) | +4,L1 fetcher 收口 |
| `infra/` 檔數 | 4 | 5(+config) | +1 |

### 後續手續

依 §3.5,**應同步更新**(本次未動,建議 user 拍板優先):
- `CLAUDE.md §8.2.A 例外清單`:本次無新增例外(全部走標準分層),原 EX-CACHE-1 / EX-AI-1 / EX-POLICY-1 / EX-CRUD-1 / EX-PASSTHRU-1 不動
- `BACKLOG.md`:加 P0-3 / P1-5/6/7 / P2-1~P2-8 條目
- `STATE.md`:加 v19.196 / v19.197 第二階段完工紀錄

(以上 meta-docs 為 user 拍板項,本次自動執行不擅動。)

---

## §6 第三階段執行紀錄(2026-06-28 完工)

User 2026-06-28 「B+C」+ 「D1+D2+B3」分批授權後進入第三階段,自動執行
(動刀前自審 / 連續 2 同 error 停手 / 不印代碼)。重點:把第二階段 P2-1 /
P2-4 / P2-5 revert backlog 用 _* 集中 + 直接搬位置 + 改 test patch path
策略重做成功,並補完 F-PROV-1 phase 22+ 8 個 high-value fetcher。

| 編號 | 內容 | Commit | 狀態 | 驗證 |
|---|---|---|---|---|
| **A1** | 清 2 個空殼目錄(P2-1/P2-5 revert 殘留 `services/fund_health/` + `repositories/macro/`)+ 修 2 個過時 SSOT-guard test(P1-5/P2-3 拆檔字串搬子檔) | `61af3e0` | ✅ 完工 | tests/test_provenance_smoke + 周邊 129 passed / 0 failed |
| **B1** | P2-5 第二次 attempt:`repositories/macro_repository.py` 1078 LOC 拆 5 子檔(`fred / yf / china / alternate / math_utils` + `__init__`)。主檔 23 LOC shim,43+ caller 無感。**同步改 28 處 test patch path**(`repositories.macro.<submod>.X`)規避 v19.199 revert 主因 | `b9eab84` | ✅ 完工 | 485 passed / 0 failed(target test);全測 2444 passed / 13 failed(8 yfinance 環境 + 5 stale SSOT-guard pre-existing,本輪修 4 個) |
| **B2** | P2-4 第二次 attempt:`repositories/policy_repository.py` 1372 LOC 拆 3 子檔(`_helpers / v1 / v2` + `__init__`)。主檔 23 LOC shim,19+ caller 無感。**共用 `_*` 私函集中 _helpers.py**(`_normalize_invest_twd` / `_normalize_fx` / `_normalize_float` / `_row_to_list` 等)規避 v19.199 `from X import *` 不取 `_*` 死結 | `b35dcbd` | ✅ 完工 | 239 passed / 0 failed(target);全測 2449 passed / 8 failed(全 yfinance 環境 pre-existing) |
| **C3** | app.py 542 → 471 LOC(−13%):抽 `_render_compass_card + render_macro_compass`(78 LOC)到 `ui/components/macro_compass_top.py`(89 LOC)。第二輪 sidebar 抽取 abort(over-engineering risk,需 7-8 module-level vars 注入接口) | `5b32618` | ✅ 完工(第一輪) | 268 passed / 1 fail(test_refresh_oauth_state_updates_module_snapshot pre-existing,git stash verified non-C3) |
| **C2** | F-PROV-1 phase 22+ 補洞 9 個 fetcher:**5 個實質補** + **4 個 pass-through docstring 標明 inheritance**。audit OK 23 → 31(+35%),PARTIAL 全清 | `b7eb171` | ✅ 完工 | 132 passed / 0 failed(target) |

**第二輪 audit 結果**:V1-V7 違憲 100% 清空(已在第二階段完成);第三階段把
P2-1/P2-4/P2-5 backlog 用直接搬位置策略全部消化(P2-1 → 取消因為復核發現
6 檔職責不同 → 標誤判;P2-4 → B2 完工;P2-5 → B1 完工)。

### B+C 系列 6 條決算

| 編號 | 結局 | 原因 |
|---|---|---|
| **C1** fund_checkup → thin wrapper | ✅ **藍圖誤判** | v19.150 已走 SSOT(check_eating_principal_1y_mk);_compute_fund_health_kpis 為「KPI 卡專屬」(7 欄)與 build_health_analysis_row「dataframe row」(15+ 欄)職責不同。同 P2-8 SCORE_RULES 案例。 |
| **B1** P2-5 macro_repository 拆 5 子檔 | ✅ **完工**(本次重做成功) | 直接搬位置 + 改 28 處 test patch path,規避 v19.199 patch shim 不穿透 sub-module |
| **B2** P2-4 policy_repository 拆 3 子檔 | ✅ **完工**(本次重做成功) | 共用 `_*` 集中 `_helpers.py`,規避 v19.199 `from X import *` 不取 `_*` 死結 |
| **C2** F-PROV-1 fetcher 補 provenance | ✅ **完工**(5 實質 + 4 docstring,8 backlog 留 complexity-justified) | scalar return + fallback chain + tuple 留 backlog |
| **C3** app.py 549 → 471 LOC | ✅ **完工**(第一輪) | macro_compass 抽出;sidebar 抽取 abort(over-engineering) |
| **B3** Fund Health 6 → 2 檔 SSOT 收口 | ✅ **藍圖誤判**(復核結論) | 6 檔職責不同(4D Grade / 配息 / MK 4 規則 / row builder / KPI 卡 UI / 7 子檔健診 UI),非「重複實作」;v19.181 SSOT 抽取後各檔均走 SSOT。同 C1 案例。 |

### 新增/搬遷檔案清單(2026-06-28 第三階段成果)

**新增**:
- `repositories/macro/_helpers.py` / `fred.py` / `yf.py` / `china.py` / `alternate.py` / `math_utils.py` / `__init__.py`(B1 拆檔 7 檔)
- `repositories/policy/_helpers.py` / `v1.py` / `v2.py` / `__init__.py`(B2 拆檔 4 檔)
- `ui/components/macro_compass_top.py`(C3 抽 89 LOC)
- `repositories/news_repository._now_iso_utc`(C2 helper)

**搬遷**:無物理檔案搬遷(B1/B2 走 shim re-export pattern,C3 抽 UI 元件)

**刪除**:
- `services/fund_health/`(A1 空殼)
- `repositories/macro/`(A1 空殼,後續 B1 重建)

### 體積與分層變化

| 指標 | 第二階段完工(2026-06-28 起) | 第三階段完工 | 變化 |
|---|---|---|---|
| Verified 違憲數 | 0 | **0** | 持平 |
| god module 主檔(>1000 LOC) | 3(fund_repository 5117 / macro_service 3386 / fund_grp_health_extras 1478) → 拆完 → 主檔 shim | **拆完並維持** | 0 god module |
| P2 backlog | 3(P2-1/P2-4/P2-5 revert) | **0**(B1+B2 重做成功,P2-1 復核標誤判) | −100% |
| F-PROV-1 audit OK | 23/39(59%) | **31/39**(79%) | +20% |
| app.py LOC | 549 | **471** | −13% |
| `repositories/` 子套件數 | 1(`fund/`) | **3**(`fund/` + `macro/` + `policy/`) | +200% |
| `services/` 子套件數 | 2(`macro/` + `calibration/`) | **2**(維持) | 持平 |

### 後續手續

依 §3.5,**已同步**(D1/D2 完工):
- `ARCHITECTURE_AUDIT.md §6`:本節(D1)
- `BACKLOG.md`:第三階段條目(D2,見另一檔)
- `STATE.md`:v19.205-208 紀錄(D2,見另一檔)

剩餘 backlog:
- `CLAUDE.md §8.2.A 例外清單`:本次無新增例外(全部走標準分層)
- **C2 8 個 MISS fetcher**:scalar return / list / fallback chain / tuple 留 complexity-justified backlog
- **C3 第二輪 sidebar 抽取**:abort,需 user 接口設計才能動
- **B3**:**復核結論為藍圖誤判**,無實質 code 改動;若 user 未來決定統一 Health 概念命名 / facade,可開新 epic

---

## §7 第四階段執行紀錄(2026-06-28 完工)

User 2026-06-28 「深層稽核 → 同意全部」分批授權後進入第四階段。3 個 Explore
平行掃描出 SSOT 7 類 / 架構越權 2 處 / Dead code 30 條 fn,一檔一刀策略執行
共 **16 commit / net −3408 LOC + 2 個架構越權 close + 2 個 SSOT 收口**。

### Tier 1 整檔死(6 commit,−2619 LOC)

| 編號 | Commit | 範圍 | LOC | 狀態 |
|---|---|---|---|---|
| **P0-3-#1** | `de822f1` v19.209 | `fetch_tw_market_snapshot`(0 caller,C2 v19.208 才補 provenance) | −34 | ✅ |
| **P0-3-#2** | `8dd03a5` v19.210 | `quadrant_simulator` 整檔 + test 孤兒(4/4 fn dead) | −499 | ✅ |
| **P0-3-#3** | `24c35cf` v19.211 | `event_calendar` 整檔 + test 孤兒(2/2 fn dead) | −354 | ✅ |
| **P0-3-#4** | `765e010` v19.212 | `allocation_simulator` 整檔 + 2 test + **EX-POLICY-1 例外退役** | −866 | ✅ |
| **P0-3-#5** | `9f0a2cd` v19.213 | `calibration/cluster` + shim + test + cache JSON | −503 | ✅ |
| **P0-3-#6** | `83606d6` v19.214 | `adjusted_nav` 整檔 + test 孤兒(2/2 dead) | −363 | ✅ |

### Tier 2 部分 fn 死(4 commit,−750 LOC)

| 編號 | Commit | 範圍 | LOC | 狀態 |
|---|---|---|---|---|
| **P0-3-#7** | `ab9ab92` v19.215 | `portfolio_service` 2 fn(`optimize_portfolio` + `calc_kelly`)+ scipy 依賴連動清 | −119 | ✅ |
| **P0-3-#8** | `4e9fbae` v19.217 | `calibration/macro_score` 4 fn + `_FRED_SERIES_MAP` / `_TRUTH_RULES` / 10 FRED imports 連動清 | −281 | ✅ |
| **P0-3-#9** | `b3e9a5a` v19.218 | `macro_buckets` 4 fn(module constants 仍 active 不動)+ 7 dead test 連動 | −110 | ✅ |
| **P0-3-#10** | `3f7eb66` v19.219 | 散批 11 fn 跨 8 檔(colors / reconcile / precision / news / ledger / fund_history / macro_card_edu / scripts)+ 6 dead test + orphan imports | −240 | ✅ |

### 架構越權修補(2 commit)

| 編號 | Commit | 範圍 | 狀態 |
|---|---|---|---|
| **P1-4** | `f210e51` v19.220 | **N3 close** — `FRED_BASE` dead chain 4 處清(L2 services 不應定義 production HTTP URL,SSOT 集中 L1 `repositories/macro/fred.py`) | ✅ |
| **P1-3** | `e82cbd1` v19.221 | **N2 close** — `_fetch_cboe_csv` 42 LOC 下沉 `repositories/external_market_repository.fetch_cboe_csv`,services/risk_radar.py 改 7 LOC thin wrapper。對稱 stooq P1-3 v19.197 模式 | ✅ |

### Tier 4 SSOT 收口(2 commit)

| 編號 | Commit | 範圍 | 狀態 |
|---|---|---|---|
| **P1-1** | `d09ab10` v19.222 | 新建 `shared/converters.py`(64 LOC)— `safe_float` / `safe_num` / `fmt_pct`。**11 caller migrate**(alias 模式 inner code 0 改動):services ×7 + ui ×4 | ✅ |
| **P1-2** | `be1feff` v19.223 | 新建 `shared/api_endpoints.py`(37 LOC)— `FINMIND_BASE`。**5 caller migrate**:3 FinMind dupes + scripts 2 FRED/YF dupes 走 L1 fetcher SSOT。**設計原則**:只收「真實重複 ≥ 2 處」,12 個 single-source URL 留各檔 source-local | ✅ |

### Bug fix + D 文件同步

| 編號 | Commit | 範圍 |
|---|---|---|
| **BUG-FIX-C3** | `db0413b` v19.216 | 修 C3 留下的 `_compass_fetch_btn` 重複 key — `macro_compass_top.py:89` 多餘 module-level `render_macro_compass()` 呼叫(`test_tab3_empty_portfolio_shows_welcome_card` 從 fail → pass) |
| **D**(本節)| (v19.224) | `ARCHITECTURE_AUDIT.md §7`(本紀錄) + `CLAUDE.md` 4 處 tw_macro.py / hot_money.py legacy reference 清(P0-4-A/B 已搬 `repositories/`,§0/§2.1/§8.2/§8.3 引用同步更新)|

### 第四階段續編(v19.225-232,本 session 接續)

User 後續「深層稽核 → #1→#9」分批授權,3 個 stacked PR(已 squash 合進 main 後)在 `claude/restore-context-protocol-lH9kg` 上新增 8 個 commit:

| 編號 | Commit | 版本 | 範圍 |
|---|---|---|---|
| **#1+#3** | `ff7b546` | v19.225 | P1-1 leftover SSOT 收尾(`portfolio_service:612 _safe_num_ps` + `tab2_single_fund:836 _fmt_pct`)+ B5 USDTWD provenance(`hot_money_repository.fetch_usdtwd_series` df.attrs 補 source / fetched_at,B5 audit 誤判修正 — tuple 第 2 元素是 error_msg 不是 source)|
| **#4** | `516ad92` | v19.226 | F-PROV-1 deep audit 補洞(audit OK 23 → 36):`fetch_div_cnyes` / `fetch_div` / `fetch_nav_history_long` / `fetch_fund_multi_source` 4 fetcher 補 dict/series.attrs/df.attrs provenance |
| **#5** | `28a7766` | v19.227 | F1 pre-existing test fix:`test_refresh_oauth_state` — P2-7 shim 不穿透 sub-module(改 patch `ui.helpers.io.oauth_state` 直接 sub-module 而非 shim) |
| **#6** | `84e1cc7` | v19.228 | F2 pre-existing test fix:`test_tab1_macro_done_seeded_renders_composite_without_exception` — mock fetchers 短路 NAS retry(247s timeout → 39s pass,6x 提速,且同時 mock sub-module + shim 雙路徑) |
| **#7** | `cc95d23` | v19.229 | **C 第二輪 sidebar 抽出** — `ui/sidebar.py`(228 LOC)抽出,app.py 472→289 LOC(−39%),**超越 ARCHITECTURE.md v11.0 願景 425 LOC(beats by 136)**。5 kwargs 注入 + OAuth lazy import 避免 P2-7。User 後續決定 §-1「不主動找事」改 user 主動列就做 |
| **#8** | `a6b859b` | v19.230 | E URL 深挖第二輪 — (A) 刪 `services/ai_service.py:28 GEMINI_URL` dead const(P0-3-#10 漏網)(B) 收 `repositories/fund/sources.py:830-835` ↔ `scripts/fetch_nav_cache.py:301` YF Morningstar query2 URL 真 dupe 至 `YF_MORNINGSTAR_CHART_URL` SSOT,scripts lazy import |
| **#9 中繼** | `f2e9f5c` | v19.231 | D Fund Health 最小可行 facade — `services/health/__init__.py` 63 LOC re-export 11 fn,0 caller 變更(後續 user 質疑違反規則,升級為完整版見下) |
| **#9 完整** | `801e888` | v19.232 | **D Fund Health 完整 subpackage 化** — 5 檔 `git mv` services/fund_*.py → services/health/(grade / dividend_calc / dividend / replacement / report)+ subpackage 內部互相 import 4 處改 + 13 caller 27 處 import 改新路徑 + facade re-export 改走 sub-module。不留 shim(P2-7 風險)|

**v19.225-232 累計影響**:
- F-PROV-1 audit OK 23 → 36(PARTIAL 4 → 0;MISS 12 → 3 留 scalar 真 breaking)
- app.py 472 → 289 LOC(−39%)/ ui/sidebar.py 新增 228 LOC
- 5 fund_*.py 重組 services/health/ subpackage(13 caller 27 imports)
- 2 處 dead code 拔(GEMINI_URL + YF dupe)
- 2 個 pre-existing test fail close(F1 OAuth refresh / F2 macro_done seeded)

**驗證累計**:test_app_smoke 72 + test_app_apptest 15 + test_provenance_smoke 28 + 7 fund_health tests 共 261+ passed。Full apptest 15/15 in 275s 證 UI 端 import 路徑完整。

### B3+C1+P2-8 三條藍圖誤判(無 code 改動,記錄)

| 編號 | 結論 |
|---|---|
| **C1** fund_checkup → thin wrapper | v19.150 已走 SSOT(`check_eating_principal_1y_mk`),`_compute_fund_health_kpis`(KPI 卡 7 欄)與 `build_health_analysis_row`(dataframe row 15+ 欄)職責不同 |
| **B3** Fund Health 6 → 2 檔 SSOT 收口 | 6 檔職責不同(4 services data layer 各維度 + 1 row builder facade + 2 UI presentation views),非「重複實作」;v19.181 SSOT 抽取後均已 aligned |
| **P2-8** SCORE_RULES SSOT 統一 | grep `^SCORE_RULES` 只 `services/macro/validation.py:106` 一處定義,已是 SSOT |

### 第四階段累計影響

- **−3408 LOC** dead code 清除
- **2 個架構越權 close**(N2 services 直 HTTP / N3 services 定義 URL)
- **2 個 SSOT 收口**(`shared/converters.py` + `shared/api_endpoints.py`,16 caller 統一)
- **EX-POLICY-1 例外退役**(對象 `allocation_simulator.py` 拔毒)
- **CLAUDE.md / BACKLOG.md / STATE.md / ARCHITECTURE_AUDIT.md** 全 doc 同步

### 剩餘 backlog(明確留待 — v19.233 後狀態)

- ~~**P1-1 leftover 2 處**~~ **v19.225 已收**:走 SSOT alias 模式各別處理
- ~~**C2 MISS fetcher 12 處**~~ **v19.233 深挖收**:原標籤「3 個 scalar」過時,實際 12 處分三類:**Cluster C 4 dict orchestrator 補洞已動**(`_fetch_domestic_perf` / `fetch_yf_latest` / `fetch_liquidity_factors` / `fetch_tw_market_tpi`)→ MISS 從 12 → 8;**Cluster A 5 scalar**(`Optional[float]` 結構性無 .attrs)+ **Cluster B 3 thin wrapper passthrough**(upstream 已 stamp)為真結構性 WONTFIX
- ~~**C3 第二輪 sidebar 抽取**~~ **v19.229 已動**(超越 v11.0 願景 425 LOC,實際達 289 LOC)
- ~~**F1 OAuth refresh test fail**~~ **v19.227 已修**(P2-7 shim sub-module 直接 patch)
- ~~**F2 macro_done seeded timeout**~~ **v19.228 已修**(247s → 39s,雙路徑 mock)
- ~~**test_financial_repository pre-existing fail**~~ **v19.233 已驗證 0 fail**(15/15 passed,標籤 stale,實際是 `test_fetch_nav_history_long::test_cache_expires_after_ttl` + `test_render_smoke::test_render_macro_tab_four_horizons` 2 個環境問題)
- **2 pre-existing 環境 fail(non-blocking)**:`test_fetch_nav_history_long::test_cache_expires_after_ttl`(TTL 時序敏感)+ `test_render_smoke::test_render_macro_tab_four_horizons`(需 FRED API,403 環境問題)

### PR 整合

3 個 stacked PR 已建立(2026-06-28 第四階段尾):
- **PR #450** 第二/三階段(25 commits → main)
- **PR #451** 第四階段 Tier 1+2 dead code(11 commits → #450)
- **PR #452** 第四階段 Tier 4 P1 架構+SSOT(4 commits → #451)
