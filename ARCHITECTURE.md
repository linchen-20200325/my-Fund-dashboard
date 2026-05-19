# 基金戰情室 — 技術架構書 (ARCHITECTURE.md)
> 版本：v11.0（v18.109 分層架構重構**已完工**）| 更新：2026-05-16 | 分支：`claude/fix-data-retrieval-4BX3v`
> **核心禁令**：🚫 全面排除 ETF，本系統專注**共同基金**。

---

## §0 v11.0 分層架構（v18.109 完工總結）

> 經 30 個 commit（A-1 → E-30）完成分層重構，根目錄業務 Python 檔從 **18 個降至 2 個**
> （`app.py` 入口 + `fund_fetcher.py` 過渡層），fast tier **357 → 359 passed 零回歸**。

### 重構成績總覽

| 階段 | 工程量 | 內容 |
|------|--------|------|
| **A 葉節點** | 4 commits | infra/proxy + oauth + cache / models/policy + ledger |
| **B 倉儲** | 12 commits | repositories/ 7 檔（fund 4216 行 / macro / ledger / snapshot / policy / news） |
| **C 服務** | 8 commits | services/ 8 檔（macro / fund / ledger / portfolio / precision / backtest / ai / policy_advisor） |
| **D UI** | 2 commits | ui/components/ 4 檔 + ui/helpers/session.py |
| **E 收尾** | 3 commits | 53 行 import 改新路徑 / 刪 17 shim / 文件更新 |
| **小計** | **30 commits** | |

### v11.1 後續優化（v18.117 → v18.140，2026-05-17 同日衝刺）

| 階段 | PR 數 | 內容 |
|------|-------|------|
| **AI 強化** | 7 | Phase 4/3-B 修 + AI-1/2/3/4 + 持股×新聞交叉（PR #165-170, #193） |
| **B-C 6 Tab 抽出** | 6 | Tab1-6 全部抽到 `ui/tab*.py`（PR #173, 181-185） |
| **Cloud crash hotfix** | 7 | NameError 連環修 / `sys.modules` 棄用 / Tab2-Tab3 fallback chain 統一（PR #186-192） |
| **Helper 收口** | 3 | _zh_holding / _update_data_registry / OAuth 搬 `ui/helpers/`（PR #194 + v18.139 + v18.140） |
| **User 反饋修** | 7 | PMI / partial 阻擋 / NAS Proxy / page_type fallback / calc_metrics（PR #174-180） |
| **小計** | **32+ commits** | app.py **9643 → 425 行（−95.6%）**；Tab1/2/3 **徹底脫離 `sys.modules['__main__']` hack** |

### 體積變化（行數，原始 → 現在）

| 模組 | 原始 | 現在 | 變化 |
|------|------|------|------|
| fund_fetcher.py | 5290 | 593 | **-89%** |
| macro_engine.py | 2128 | 0（已刪 shim） | 整檔搬 services/macro_service.py |
| portfolio_engine.py | 534 | 0 | services/portfolio_service.py |
| precision_engine.py | 403 | 0 | services/precision_service.py |
| ai_engine.py | 857 | 0 | services/ai_service.py |
| fund_ledger.py | 604 | 0 | models/ledger.py + services/ledger_service.py |
| backtest_engine.py | 174 | 0 | services/backtest_service.py |
| policy_advisor.py | 239 | 0 | services/policy_advisor_service.py |
| policy_store.py | 656 | 0 | repositories/policy_repository.py |
| ledger_store.py | 235 | 0 | repositories/ledger_repository.py |
| ledger_snapshot_store.py | 246 | 0 | repositories/snapshot_repository.py |
| macro_core.py | 721 | 0 | repositories/macro_repository.py |
| proxy_helper.py | 132 | 0 | infra/proxy.py |
| oauth_helper.py | 200 | 0 | infra/oauth.py |
| policy_keys.py | 96 | 0 | models/policy.py |
| mk_dashboard.py | 682 | 0 | ui/components/mk_dashboard.py |
| mk_clock.py | 260 | 0 | ui/components/mk_clock.py |
| shared/macro_card*.py | 678 | 0 | ui/components/macro_card*.py |

### 新分層結構（最終）

```
┌─────────────────────────────────────────────┐
│  Presentation (UI)    — Streamlit only      │  ← 使用者
│  app.py（425 行）+ ui/tab*.py + ui/components/+ ui/helpers/│
│   ├─ ui/tab1_macro.py ~ ui/tab6_manual.py   │
│   ├─ ui/tab3_t7_ledger.py (T7 帳本子模組)   │
│   ├─ ui/components/macro_card.py            │
│   ├─ ui/components/macro_card_edu.py        │
│   ├─ ui/components/mk_dashboard.py          │
│   ├─ ui/components/mk_clock.py              │
│   ├─ ui/helpers/session.py                  │
│   ├─ ui/helpers/macro_helpers.py            │
│   ├─ ui/helpers/holdings.py (_HOLDING_ZH)   │
│   ├─ ui/helpers/data_registry.py            │
│   │   （_update_data_registry +             │
│   │    _sync_invest_twd_from_ledgers）      │
│   └─ ui/helpers/oauth_state.py              │
│       （_oauth_configured / _gsa_secret /   │
│        _resolve_oauth_cfg / _get_oauth_client）│
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  Service (Business Logic) — 純運算 / 編排    │
│   ├─ services/macro_service.py (2128 行)    │
│   ├─ services/fund_service.py (481 行)      │
│   ├─ services/ledger_service.py (502 行)    │
│   ├─ services/portfolio_service.py (534 行) │
│   ├─ services/precision_service.py (403 行) │
│   ├─ services/backtest_service.py (174 行)  │
│   ├─ services/ai_service.py (857 行)        │
│   └─ services/policy_advisor_service.py     │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  Repository (Data Access) — 純 I/O / 持久化 │
│   ├─ repositories/fund_repository.py (4216) │
│   ├─ repositories/macro_repository.py (721) │
│   ├─ repositories/news_repository.py        │
│   ├─ repositories/ledger_repository.py      │
│   ├─ repositories/snapshot_repository.py    │
│   └─ repositories/policy_repository.py      │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌──────────────┐  ┌────────────────────────┐
│  Models      │  │  Infra (Cross-cutting) │
│  ├─ policy.py│  │  ├─ proxy.py           │
│  └─ ledger.py│  │  ├─ oauth.py           │
└──────────────┘  │  └─ cache.py (234 行)  │
                  └────────────────────────┘
```

### 已知技術債（未來 v12.0 處理）

1. **fund_fetcher.py 殘留 593 行** — `safe_float / fetch_url_with_retry / is_valid_moneydj_page / classify_fetch_status` 等 utility。
   為避免「services → fund_fetcher → services」三角依賴，暫保留作為過渡 utility module。
   未來可拆 `infra/http.py`（HTTP utility）+ 各 service 內 helper。
2. **app.py 仍 ~600 KB** — Tab1~Tab6 拆檔受限於 Streamlit `with tab:` closure 設計。
   v12.0 可探索 streamlit-pages 或 multi-page app 模式分檔。
3. **PrecisionStrategyEngine.fetch_stock_three_ratios** — yfinance 直連 I/O 未走 NAS proxy；
   與 class state 緊耦合留 services/precision_service.py。可拆 `repositories/financial_repository.py`。

---

## §1 專案概覽（保留舊版以下，僅 §0 章節改寫）



### 新分層結構

```
┌─────────────────────────────────────────────┐
│  Presentation (UI)    — Streamlit only      │  ←── 使用者
│  ui/tab1~6_*.py + components/ + helpers/    │
└──────────────────┬──────────────────────────┘
                   │ 只能向下呼叫
                   ▼
┌─────────────────────────────────────────────┐
│  Service (Business Logic) — 純運算 / 編排    │
│  services/macro / fund / portfolio /        │
│  precision / backtest / ai / ledger /       │
│  policy_advisor                             │
│  禁: import streamlit                       │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  Repository (Data Access) — 純 I/O / 持久化 │
│  repositories/fund / news / macro /         │
│  ledger / policy / snapshot                 │
│  禁: 業務規則 / Streamlit                    │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌──────────────┐  ┌────────────────────────┐
│  Models      │  │  Infra (Cross-cutting) │
│  fund/ledger │  │  proxy/oauth/cache/http│
│  macro/policy│  │                        │
└──────────────┘  └────────────────────────┘
```

### 嚴格依賴規則

| 來源 → 目標 | 允許？ | 理由 |
|-------------|--------|------|
| `ui/` → `services/` | ✅ | UI 透過 service 取資料 |
| `ui/` → `repositories/` | 🚫 | 必須走 service 收口業務語意 |
| `services/` → `repositories/` | ✅ | service 編排 I/O |
| `services/` → `ui/` | 🚫 | service 不依賴 Streamlit |
| `repositories/` → `services/` | 🚫 | 反向依賴 |
| 任何層 → `models/` / `infra/` | ✅ | 共享元件可被任何層使用 |

### 搬遷檔對檔地圖

| 現有檔案 | 新位置 | 策略 |
|---------|--------|------|
| `app.py` (588 KB) | `app.py` slim (<10 KB) + `ui/tab[1-6]_*.py` | **拆 6 個 Tab** |
| `mk_dashboard.py` | `ui/components/mk_dashboard.py` | 直搬 |
| `mk_clock.py` | `ui/components/mk_clock.py` | 直搬 |
| `shared/macro_card*.py` | `ui/components/macro_card*.py` | 直搬 |
| `macro_engine.py` (103 KB) | `services/macro_service.py` + `models/macro.py` | **拆業務 vs DTO** |
| `macro_core.py` | `repositories/macro_repository.py` | 直搬 |
| `fund_fetcher.py` (249 KB) | `repositories/fund_repository.py` + `repositories/news_repository.py` + `services/fund_service.py` | **拆三段** |
| `ai_engine.py` | `services/ai_service.py` | 直搬 |
| `portfolio_engine.py` | `services/portfolio_service.py` | 直搬 |
| `precision_engine.py` | `services/precision_service.py` | 直搬 |
| `backtest_engine.py` | `services/backtest_service.py` | 直搬 |
| `fund_ledger.py` | `services/ledger_service.py` + `models/ledger.py` | **抽 dataclass** |
| `policy_advisor.py` | `services/policy_advisor_service.py` | 直搬 |
| `policy_store.py` | `repositories/policy_repository.py` | 直搬 |
| `policy_keys.py` | `models/policy.py` | 直搬 |
| `ledger_store.py` | `repositories/ledger_repository.py` | 直搬 |
| `ledger_snapshot_store.py` | `repositories/snapshot_repository.py` | 直搬 |
| `proxy_helper.py` | `infra/proxy.py` | 直搬 |
| `oauth_helper.py` | `infra/oauth.py` | 直搬 |
| 17 個 `test_*.py` | 保留根目錄 | 僅改 `from` 路徑 |

### Backward-compat 策略

搬遷期間原檔保留 shim：

```python
# 例：proxy_helper.py（舊位置）
# v11.0 Phase A: 已搬至 infra/proxy.py
from infra.proxy import *  # noqa: F401,F403 legacy shim
# Phase E 收尾後本檔將被刪除
```

Phase E 收尾才一次性刪除所有 shim，確保中途任何 commit 都可 rollback。

---

## §1 專案概覽


### 定位
Streamlit Cloud 部署的機構級共同基金監控儀表板，整合總經指標、事件驅動分析、單一基金深度診斷、投資組合管理、轉申購試算與回測，透過 NAS Proxy 穿透抓取 MoneyDJ / TDCC 境內資料。

### 核心設計原則

| 原則 | 實作方式 |
|------|---------|
| **零快取** | 全域禁用 `@st.cache_data`，每次操作即時抓取 |
| **模組隔離** | UI（app.py）與運算引擎（`*_engine.py`）嚴格分離 |
| **多來源容錯** | 每項資料最多 5 層備援來源（MoneyDJ → TCB → Fundclear → cnyes → Morningstar） |
| **事件驅動** | 新聞事件強制與持股交叉比對，觸發衝擊警報 |
| **資料頻率管控** | `data_registry` 統一追蹤所有資料更新頻率，月度 > 40 天自動注入 STALE 標記 |
| **σ 絕對位階** | 所有買賣點以 HWM 為基準計算絕對 σ 跌幅，禁用相對百分位 |

### 技術棧

```
Python 3.11+
Streamlit 1.45.1     — UI 框架
Plotly 5.x           — 互動圖表
pandas / numpy       — 資料處理
yfinance             — 美股行情（共同基金 NAV 備援）
FRED API             — 總經數據（需 FRED_API_KEY）
Gemini API           — AI 分析（需 GEMINI_API_KEY）
requests + bs4       — MoneyDJ/TDCC 爬取
feedparser           — RSS 新聞事件抓取
scipy                — 投資組合最佳化（SLSQP）
```

---

## §2 目錄結構

```
my-fund-dashboard/
├── app.py                  # UI 主程式 — 6 Tabs 入口，呼叫各引擎
├── macro_engine.py         # 總經引擎 — FRED/yfinance + OAS 即時信用壓力
├── fund_fetcher.py         # 基金抓取 — 多來源 NAV/配息/持股爬取（v18.23 模組層 _install_global_urllib_proxy）
├── ai_engine.py            # AI 引擎 — Gemini prompt + 事件衝擊分析
├── portfolio_engine.py     # 組合引擎 — 六因子評分/單筆轉申購/組合重分配(v10.1)/相關性矩陣
├── backtest_engine.py      # 回測引擎 — Sharpe/Sortino/MaxDD
├── precision_engine.py     # 精準策略引擎 — σ絕對位階/複合風險溫度計
├── fund_ledger.py          # 通用型基金帳務引擎 (v18.0 Phase 1+2) — Ledger + FundPosition + GhostPortfolio + Switch + XIRR
├── proxy_helper.py         # NAS Proxy 可移植模組
├── mk_dashboard.py         # MK 智能戰情室 — 核心戰情室/波段觀測站/3-3-3 篩選器（v18.34 dedupe by code）
├── policy_keys.py          # 保單視圖複合鍵 (policy_id, fund_code) ↔ pk_str 工具
├── policy_advisor.py       # 保單視圖純規則建議 — σ × 配息覆蓋 × 60MA × VIX + recommend_policy()
├── policy_store.py         # gspread 儲存層 — Service Account / OAuth、每保單一 worksheet API
├── oauth_helper.py         # Google OAuth 2.0 web flow（refresh_token + auto-refresh）
├── ledger_store.py         # `_Ledgers` 系統 tab — append-only 交易帳
├── ledger_snapshot_store.py # `_T7_State` 系統 tab — T7 帳本 JSON snapshot 跨刷新還原
├── requirements.txt        # 依賴清單
├── CLAUDE.md               # AI 協作規範（Core Protocol v2.0）
├── STATE.md                # 專案進度追蹤器
├── ARCHITECTURE.md         # 本文件
├── SPEC.md                 # 系統需求規格書
├── NAS_PROXY_GUIDE.md      # NAS 中繼站人類說明書
├── NAS_PROXY_FOR_AI.md     # NAS 中繼站 AI 移植說明書
└── .streamlit/
    └── secrets.toml        # API Keys（FRED_API_KEY, GEMINI_API_KEY, PROXY_URL）
```

### 各模組職責一覽

| 模組 | 對外暴露 | 不做的事 |
|------|---------|---------|
| `app.py` | Tab UI、sidebar、session state 管理、`_update_data_registry()` | 不直接呼叫 HTTP |
| `macro_engine.py` | 總經指標 dict、景氣評分、OAS Z-Score、`detect_systemic_risk()` | 不操作 UI |
| `fund_fetcher.py` | NAV Series、配息 list、holdings dict、metrics dict | 不呼叫 AI |
| `ai_engine.py` | Gemini 回傳 markdown、`event_impact_analysis()`（v10 新增） | 不抓資料、不操作 UI |
| `portfolio_engine.py` | 評分 dict、警示 list、最佳權重、相關性矩陣、Kelly | 不抓資料 |
| `backtest_engine.py` | 績效指標 dict（Sharpe/MaxDD/…） | 不抓資料 |
| `precision_engine.py` | σ 絕對位階買賣點、複合風險溫度計 | 不操作 UI |
| `fund_ledger.py` | `FundPosition`、`Ledger`、`GhostPortfolio`、`Switch`、`Transaction`、`calculate_xirr`（v18.0 Phase 1+2 + JSON round-trip） | 不抓資料、不操作 UI、純帳務 |
| `proxy_helper.py` | `get_proxy_config()`、`fetch_url()`、`make_retry_session()` | 純 HTTP 工具 |

---

## §3 資料流向

### 3.1 全域啟動流

```
Streamlit 啟動
  → _load_keys()                    讀取 secrets.toml / env
  → st.session_state 初始化          含 data_registry: {}
  → sidebar 渲染                     API 狀態 / Proxy 狀態
  → st.tabs(6)                       分發至各 Tab
```

### 3.2 Tab1 — 總經儀表板 + 事件驅動

```
使用者按「載入總經」
  → fetch_all_indicators(fred_api_key)         macro_engine
      ├─ FRED API (14+ 指標，含 OAS 日頻)
      └─ yfinance (VIX / DXY / ADL / COPPER)
  → calc_macro_phase(indicators)               macro_engine
  → calc_oas_z_score(indicators["HY_SPREAD"])  macro_engine (v10 新增)
  → fetch_market_news(max_per_feed=10)         fund_fetcher
  → detect_systemic_risk(news_items)           macro_engine
  → detect_turning_points(fred_api_key)        macro_engine **(v18.20 新增)**
      ├─ PMI 新訂單擴散：FRED AMTMNO − MNFCTRIRSA YoY
      └─ 10Y-2Y 倒掛翻正：FRED T10Y2Y 穩定翻正去抖
  → _update_data_registry()                   app.py helper
  → st.session_state 寫入:
      indicators, phase_info, news_items,
      systemic_risk_data, macro_last_update,
      data_registry
  → UI 渲染:
      ├─ 天氣卡 / 指標表 / 雷達圖
      ├─ OAS 即時信用壓力燈號 (v10 新增)
      ├─ ⚠️ 事件衝擊警報卡（若觸發）(v10 新增)
      ├─ 📡 景氣拐點監控（雙卡 + sparkline + 解讀 caption）(v18.20 新增)
      └─ 📊 歷史回測 expander（lazy load）— 倒掛翻正 × SPX 6/12/18M (v18.21 新增)
            └─ backtest_turning_points(fred_api_key)  macro_engine
  → [可選] analyze_macro_structured(api_key, …)   ai_engine → Gemini API
      輸出：六章節（含新手指引 + 老手推演）
```

### 3.3 Tab2 — 單一基金深度診斷

```
使用者輸入 MoneyDJ URL / 代碼
  → fetch_fund_from_moneydj_url(url)           fund_fetcher
      ├─ MoneyDJ wb01/wb05/wb07（透過 NAS Proxy）
      ├─ fetch_performance_wb01(code)
      ├─ fetch_risk_metrics(code)
      └─ fetch_holdings(code)  → 前十大持股 + TER
  → calc_metrics(nav_series, divs)             fund_fetcher
  → calc_hwm_sigma_levels(nav_series)          precision_engine (v10)
      → {HWM, buy1(-1σ), buy2(-2σ), buy3(-3σ), sell1(+1σ)}
  → event_impact_analysis(holdings, news_items) ai_engine (v10 新增)
  → _update_data_registry()                   app.py helper
  → st.session_state.fund_data 寫入
  → UI 渲染:
      ├─ NAV 折線圖（含 σ 絕對位階標線）(v10 升級)
      ├─ σ 絕對位階卡片（強制顯示）(v10 新增)
      ├─ 配息記錄 + 吃本金警示
      ├─ 持股完整度 + TER 隱形成本
      ├─ ⚠️ 事件衝擊標注（若持股受新聞影響）(v10 新增)
      └─ 新手/老手雙軌 AI 輸出 (v10 新增)
```

### 3.4 Tab3 — 組合基金

```
使用者加入基金（代碼 + 金額 + 核心/衛星）
  → fetch_fund_by_key(full_key)               fund_fetcher
  → calc_fund_factor_score(fund_data)         portfolio_engine
  → calc_correlation_matrix(portfolio_funds)  portfolio_engine (v10 新增)
      → 任兩基金相關係數 > 0.85 → shadow_fund_warning
  → calc_holdings_overlap(portfolio_funds)    portfolio_engine (v10 新增)
      → 持股重疊度 > 40% → concentration_warning
  → _update_data_registry()                  app.py helper
  → UI 渲染:
      ├─ 核心/衛星比例圓餅圖
      ├─ 持股相關性熱力圖 (v10 新增)
      ├─ 🔴 影子基金/集中度警告 (v10 新增)
      ├─ risk_alert(drawdown, coverage, …)    portfolio_engine
      └─ T7: 帳務與再平衡試算 (v1.0 A/B/C，加權平均會計，v18.1 最簡 UI)
              ├─ 自動 NAV/FX：fund_fetcher.get_latest_nav / get_latest_fx（即時抓取）
              ├─ 帳本載體：st.session_state.t7_ledgers（in-memory，重整即清空）
              ├─ A 新投入 → Ledger.subscribe()                      # 加權平均合併
              ├─ B 投入再平衡 → 缺口比例分配 + Ledger.subscribe()
              └─ C 轉換再平衡：
                    ├─ 同幣別 → Switch.switch_same_currency()       # fx_avg 繼承
                    └─ 跨幣別 → Switch.switch_cross_currency(       # 即期立帳
                                  cross_rate = FX_A_TWD / FX_B_TWD)
```

### 3.5 Tab4 — 回測

```
使用者選取基金 + 時間區間 + 權重
  → fetch_nav(full_key)                      fund_fetcher
  → backtest_portfolio(nav_df, weights)       backtest_engine
  → calc_performance_metrics(equity, returns) backtest_engine
  → compare_with_benchmark(port, bench)      backtest_engine
  → UI 渲染: 資產曲線 / 績效表
```

### 3.6 Tab5 — 資料診斷中控台 Data Guard 3.0

```
Tab5 開啟（唯讀 + 動態計算）
  → _update_data_registry()                  app.py（掃描 session_state）
  → 全域資料健康總表（HTML Grid）
      ├─ 資料名稱 / 來源 / 頻率 / 最新日期 / 新鮮度 / 筆數
      ├─ 🟢🟡🔴 三色燈號（依頻率閾值）
      └─ 🔴 過舊警告 → AI Prompt 注入 [STALE: XX天]
  → 持倉完整度報告 (v10 新增)
      ├─ 前十大持股：已取得/未取得
      ├─ TER（經理費+保管費）：已取得/未取得
      └─ TER > 1.5% → 🔴「費用吃掉配息」警示
  → Snapshot Viewer（selectbox 抽查任一 DataFrame head(5)）
  → 14 指標燈號表（FRED/yfinance 詳細狀態）
  → API 金鑰狀態（FRED / Gemini / Proxy）
  → API 延遲趨勢折線圖
```

### 3.7 Data Guard 狀態機

```
               資料新鮮度評估
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
    🟢 正常      🟡 延遲       🔴 過舊
        │           │           │
   正常顯示    UI 亮黃燈    UI 亮紅燈
        │           │           │
        └─────┬─────┘           │
              ▼                 ▼
         正常 AI 分析    [STALE: XX天] 注入 Prompt
                         AI 輸出加入「落後延遲風險」警示
```

---

## §4 核心函式 I/O 定義

### 4.1 macro_engine.py（v10 新增/升級）

| 函式 | 輸入 | 輸出 | 說明 |
|------|------|------|------|
| `fetch_all_indicators(fred_api_key)` | `str` | `dict[str, dict]` | 抓取 14+ 總經指標（FRED+yfinance），每項含 `value/signal/score/series` |
| `calc_macro_phase(indicators)` | `dict` | `dict` | 加權評分 → `{score, phase, rec_prob, alloc}` |
| `calc_oas_z_score(oas_series)` | `pd.Series` | `dict` | OAS 5 年滾動 Z-Score → `{z, level, alert}` **(v10 新增)** |
| `detect_systemic_risk(news_items)` | `list[dict]` | `dict` | 關鍵字掃描 → `{level, score, triggers, summary}` |
| `identify_regime(indicators)` | `dict` | `dict` | 四象限景氣循環辨識 |
| `fetch_tw_market_tpi(fred_api_key)` | `str` | `dict` | 台股三因子 TPI |
| `detect_turning_points(fred_api_key)` | `str` | `dict` | **(v18.20 新增)** 景氣拐點即時訊號 → `{pmi_diffusion, yield_curve}` 各含 `{signal, value, history, note}` |
| `backtest_turning_points(fred_api_key, min_inversion_depth, stable_days, cooldown_days)` | `str + 3 floats` | `dict` | **(v18.21 新增)** 倒掛翻正歷史回測 → `{events, summary, spx_series, t10y2y_series, source_ok, note}` |

**`detect_turning_points` 輸出結構：**
```
{
  pmi_diffusion: {  # 製造業新訂單擴散
    signal:  "改善" | "惡化" | "—",
    value:   float,                  # AMTMNO − MNFCTRIRSA YoY 差值
    history: list[float],            # 近 12M sparkline
    note:    str,
  },
  yield_curve: {  # 10Y-2Y 倒掛翻正
    signal:  "翻正" | "倒掛中" | "正常",
    value:   float,                  # 當前 T10Y2Y %
    history: list[float],            # 近 24M sparkline
    note:    str,
  },
}
```

**`backtest_turning_points` 輸出結構：**
```
{
  events: [
    {date: Timestamp, t10y2y_min_pre: float,
     ret_6m: float|None, ret_12m: float|None, ret_18m: float|None,
     complete: bool},               # complete=False 表示 18M 窗口未到期
    ...
  ],
  summary: {
    n_events: int, n_complete_18m: int,
    median_6m/12m/18m: float, mean_6m/12m/18m: float,
    win_rate_6m/12m/18m: float,    # 僅納完整窗口
  },
  spx_series:    pd.Series,         # ^GSPC 全歷史（log 走勢用）
  t10y2y_series: pd.Series,         # FRED T10Y2Y 30Y+
  source_ok: bool,
  note: str,
}
```

**事件識別規則（三段去抖）：**
- 區段內 `min(T10Y2Y) ≤ min_inversion_depth`（預設 -0.10，去除貼地噪音）
- 翻正日 T10Y2Y ≥ 0 且後續 `stable_days` 日皆 ≥ 0（預設 5 日，去抖）
- 距上一事件 ≥ `cooldown_days`（預設 365 日，避免同週期重複觸發）
- 樣本 n=4~6（1990 / 2001 / 2007 / 2019）— UI caption 誠實標註「僅供參考」

**OAS Z-Score 輸出結構：**
```
{
  z:       float,    # 當前 Z-Score（5年滾動）
  level:   str,      # "normal" | "elevated" | "extreme"
  alert:   str,      # "🟢" | "🟡" | "🔴"
  value:   float,    # 當前 OAS %
  mean_5y: float,    # 5年均值
  std_5y:  float,    # 5年標準差
}
```

### 4.2a macro_core.py（FRED + yfinance 抽象層）

| 函式 | 輸入 | 輸出 | 說明 |
|------|------|------|------|
| `fetch_fred(series_id, api_key, n)` | 系列代碼 / API key / 筆數 | `pd.DataFrame[date,value]` | FRED observations API |
| `fetch_yf_close(ticker, range_, interval)` | yfinance ticker | `pd.Series` | yfinance Chart REST API |
| `fetch_ism_pmi(api_key, max_age_days)` | FRED key / 容忍天數 | `dict` | ISM PMI 5 段 fallback |
| `fred_get_next_release_date(series_id, api_key)` | 系列代碼 / API key | `date \| None` | **(v18.3 新增)** 查詢下次 release 日；30 天 disk cache；2 段呼叫（series/release → release/dates）；失敗回 None |

### 4.2 fund_fetcher.py

| 函式 | 輸入 | 輸出 | 說明 |
|------|------|------|------|
| `fetch_fund_from_moneydj_url(url)` | `str` | `dict` | 主要入口：完整基金資料（NAV/績效/配息/持股） |
| `fetch_holdings(code)` | `str` | `dict` | MoneyDJ 持股頁 → `{sector_alloc, top_holdings, ter}` （v10 加入 TER） |
| `fetch_market_news(max_per_feed)` | `int` | `list[dict]` | RSS 財經新聞 → `[{title, summary, source, published, url, tags}]` |
| `calc_metrics(s, divs, risk_override)` | `pd.Series, list, dict` | `dict` | MK 買點、標準差、年化配息率 |

### 4.3 ai_engine.py（v10 新增）

| 函式 | 輸入 | 輸出 | 說明 |
|------|------|------|------|
| `analyze_macro_structured(…)` | `indicators, phase, news, oas_z` | `str` | v10 六章節輸出（含事件警報/新手/老手） |
| `event_impact_analysis(holdings, news)` | `dict, list[dict]` | `dict` | **(v10 新增)** 持股 × 新聞交叉比對 → `{triggered, severity, alerts}` |
| `analyze_fund_json(…)` | 基金相關 dict | `str` | 單一基金 AI 分析（含 σ 絕對位階）|

**`event_impact_analysis` 輸出結構：**
```
{
  triggered:  bool,         # 是否觸發警報
  severity:   str,          # "fatal" | "major" | "minor"
  alerts: [
    {
      event:    str,         # 新聞標題
      impact:   str,         # 受影響持股/債種
      weight:   float,       # 在基金的佔比 %
      est_nav_impact: str,   # 預估淨值影響 "-X%~-X%"
      action:   str,         # 建議操作
    }
  ]
}
```

### 4.4 portfolio_engine.py（v10 新增）

| 函式 | 輸入 | 輸出 | 說明 |
|------|------|------|------|
| `calc_fund_factor_score(fund_data, …)` | `dict, dict, float` | `dict` | 六因子加權評分（0~100） |
| `calc_correlation_matrix(funds_list)` | `list[dict]` | `dict` | **(T5 fallback)** NAV Pearson 相關係數矩陣（持股不可得時備援） |
| `calc_holdings_overlap(funds_list)` | `list[dict]` | `dict` | **(v18.2 新增 T5 主算)** 持股 Jaccard × 0.6 + 產業 cosine × 0.4 → score；shadow 門檻 0.70；資料不齊自動降級 |
| `dividend_safety(total_return, …)` | `float, float, float` | `dict` | 吃本金診斷 |
| `risk_alert(drawdown, coverage, …)` | 各風險指標 | `list[dict]` | 即時風險預警 |

> **v18.1 移除**：`calc_switch_cost` / `calc_portfolio_reallocation` 已連同 T4 / T6 UI 一併刪除。
> 凡涉及換倉/再平衡邏輯，一律以 `fund_ledger.Ledger.subscribe` + `fund_ledger.Switch` 為唯一骨架（見 §4.5 與 §4.7）。

### 4.5 fund_ledger.py（v18.0 Phase 1+2 + JSON round-trip）

> 對齊 CHUBB 安達人壽 11 欄位公式（圖片實證）。**Event-Sourcing 流水帳**，append-only。
> Phase 1：buy / dividend / ghost。Phase 2：Switch（同幣別 fx_avg 繼承 / 跨幣別記交叉匯率）+ XIRR（scipy + bisection fallback）。
> JSON：`Ledger.to_dict()` / `Ledger.from_dict()` 完全等價 round-trip（含 switch_in/out）。
> **v18.1 起**：T7 A/B/C 是唯一帳務骨架；舊版 `calc_switch_cost` / `calc_portfolio_reallocation` 已從 portfolio_engine 永久刪除；fund_ledger_db.py 持久化層整段刪除。

| 類別 / 函式 | 輸入 | 輸出 | 說明 |
|------------|------|------|------|
| `Transaction(txn_type, txn_date, ...)` | dataclass | — | Append-only 事件記錄（subscribe / dividend_cash / dividend_reinvest） |
| `FundPosition(fund_code, currency, units, cost_unit, fx_avg, cost_unit_with_div, dividends_received_twd)` | dataclass | — | 持倉狀態（CHUBB 11 欄位 1/2/3/10） |
| `FundPosition.net_investment_twd` | property | float | (4) = (1)×(2)×(3) |
| `FundPosition.value_orig(nav)` | float | float | (6) = (2)×(5) |
| `FundPosition.value_twd(nav, fx)` | float, float | float | (8) = (6)×(7) |
| `FundPosition.roi_price(nav, fx)` | float, float | float | (9) = (8)/(4) − 1 |
| `FundPosition.roi_total_chubb(nav, fx)` | float, float | float | (11) = (8)/((2)×(3)×(10)) − 1 |
| `FundPosition.roi_total_cashflow(nav, fx)` | float, float | float | 現金流版含息報酬 = (value_twd + Σdiv_twd) / inv − 1 |
| `Ledger.subscribe(amount_twd, fx_rate, nav, txn_date)` | 4 floats | float (new_units) | 加權平均重算 cost_unit/fx_avg/cost_unit_with_div |
| `Ledger.dividend_cash(div_per_unit, fx_rate, txn_date, nav_at_div)` | 3 floats + Optional | float (cash_twd) | cost_unit_with_div 依虛擬再投資公式下調，units 不變 |
| `Ledger.dividend_reinvest(new_units, nav_at_div, txn_date)` | float, float, date | None | units 增加 + cost 加權平均；fx_avg 不變 |
| `GhostPortfolio.compare(actual_b, nav_b, fx_b, ghost_a, nav_a, fx_a)` | 2 FundPosition + 4 floats | `GhostComparison` | 含已領配息：超額 > 0.5% → ✅ / < −0.5% → ❌ / 否則 ≈ |
| `Switch.switch_same_currency(led_from, led_to, units, nav_from, nav_to, fee, date)` | 2 Ledger + 4 floats + date | `SwitchResult` | **(Phase 2)** 同幣別轉換，B fx_avg 嚴格繼承 A |
| `Switch.switch_cross_currency(led_from, led_to, units, nav_from, nav_to, cross_rate, fx_to_twd, fee, date)` | 2 Ledger + 6 floats + date | `SwitchResult` | **(Phase 2)** 跨幣別轉換，B fx_avg 採當日即期 |
| `calculate_xirr(transactions, current_value_twd, today)` | list[Transaction] + float + date | float | **(Phase 2)** 年化 IRR；scipy.brentq 主算 + pure-Python bisection fallback |

**`SwitchResult` 輸出結構：**
```
{
  units_redeemed_from:        float,   # A 端贖回單位數
  redeem_amount_orig:         float,   # 贖回金額（A 幣，扣費前）
  fee_orig:                   float,   # 轉換費（A 幣計）
  proceeds_after_fee_orig:    float,
  proceeds_in_to_currency:    float,   # 換到 B 幣後（同幣別 = 上式）
  units_added_to:             float,   # B 端新增單位數
  fx_avg_inherited:           float,   # B 端新單位的 fx_avg
  cost_unit_to_basis:         float,   # B 端新單位的 cost_unit（TWD 守恆反推）
  cost_unit_with_div_to_basis: float,  # B 端新單位的 cost_unit_with_div
  twd_cost_basis_transferred: float,   # 移轉的 TWD 歷史成本基底
  cross_rate:                 float,   # 同幣別 = 1.0
}
```

**會計規則（switch 兩模式共通）：**
- A 端 `cost_unit` / `fx_avg` / `cost_unit_with_div` **不變**（加權平均按比例贖回保持），`units` 減少
- 費用以 A 幣計、不影響歷史 TWD 成本 → 費用造成 B 端 `units` 變少 → ROI 自動反映費用
- B 端 `cost_unit` 反推：`(n_redeem × cost_unit_a × fx_avg_a) / (n_added × fx_avg_b)`，使 `net_investment_twd` 守恆
- B 端 `cost_unit_with_div` = `cost_unit_b × (cost_unit_with_div_a / cost_unit_a)`（保留 A 含息折扣比例）

**XIRR 現金流定義（`txn_type` 對應）：**
- `subscribe` → `−amount_twd`（流出）
- `dividend_cash` → `+amount_twd`（流入）
- `dividend_reinvest` / `switch_out` / `switch_in` → 0（內部移轉，不算外部現金流）
- 終值（`today`）→ `+current_value_twd`

**`GhostComparison` 輸出結構：**
```
{
  value_actual_twd:  float,   # B 含已領配息總值（TWD）
  value_ghost_twd:   float,   # Ghost A 含假設配息總值（TWD）
  excess_twd:        float,   # B − A
  excess_pct:        float,   # excess_twd / value_ghost_twd
  verdict:           str,     # "✅ 此次轉換創造超額報酬" | "❌ 機會成本損失" | "≈ 持平"
  action:            str,     # 行動建議
}
```

### 4.5b backtest_engine.py（v13 + v18.17 排毒）

| 函式 | 輸入 | 輸出 | 說明 |
|------|------|------|------|
| `backtest_portfolio(nav_df, weights, rebalance)` | `DataFrame, Series, str\|None` | `DataFrame` | 組合回測；weights 自動歸一化（全 0 fallback 均等）；columns: equity_curve / portfolio_return / drawdown |
| `calc_performance_metrics(equity, returns, rf, freq)` | `Series, Series, float, int` | `dict` | Sharpe / Sortino / MaxDD / Calmar；returns<3 期回 `{}`；ann_vol==0 守 0 |
| `compare_with_benchmark(port_curve, bench_curve, freq)` | `Series, Series, int` | `dict` | alpha / TE / IR；freq 預設 12，日頻傳 252；期間不重疊回 `{"error":...}` |
| `quick_backtest(nav_series, freq)` | `Series, int` | `dict` | 單基金快回測；少於 4 期回 `{"error":...}` |

**v18.17 排毒（2026-05-12）**：
- 移除 `backtest_portfolio` 內無效 `iterrows` 死碼（與向量化等價，100x 加速）
- 加 `weights.sum()==0` 防護（fallback 均等分配）
- `compare_with_benchmark` 加 `freq` 參數（原 hardcoded `*12` 對日頻錯誤）
- docstring 對齊：承認 `rebalance="ME"` 在月頻輸入下 = no-op；真正的再平衡為 TODO

**`backtest_portfolio` 輸出結構：**
```
DataFrame(index=DatetimeIndex):
  equity_curve:     float    # 累計報酬指數（起點接近 1.0）
  portfolio_return: float    # 各期組合報酬
  drawdown:         float    # 回撤（<=0）
```

**已知簡化限制**：
- `rebalance="ME"` / `"QE"` 實際只做「日報酬聚合」，**不會在期末重置權重**
- 當前 Tab4 傳入月頻 NAV → ME 聚合為 no-op，等同 buy-and-hold（語意一致）
- 若要真正再平衡，需在「期初用 w 配置 → 期內持有 → 期末贖回換倉」改寫，留 TODO

### 4.6 precision_engine.py（v10 升級）

| 函式 | 輸入 | 輸出 | 說明 |
|------|------|------|------|
| `calc_hwm_sigma_levels(nav_series)` | `pd.Series` | `dict` | **(v10 新增)** HWM 絕對位階 → `{hwm, buy1, buy2, buy3, sell1, current_position}` |
| `risk_score_strategy(score)` | `float` | `dict` | 5 級策略建議 |
| `fetch_stock_three_ratios(name)` | `str` | `dict` | yfinance 季度財報三率 QoQ diff |

**`calc_hwm_sigma_levels` 輸出結構：**
```
{
  hwm:              float,   # 歷史最高淨值
  std_1y:           float,   # 1年年化標準差
  buy1:             float,   # HWM - 1σ
  buy2:             float,   # HWM - 2σ（大買區）
  buy3:             float,   # HWM - 3σ（超跌區）
  sell1:            float,   # HWM + 1σ（停利）
  current_nav:      float,   # 當前 NAV
  current_position: str,     # "超跌區" | "大買區" | "輕買區" | "合理區" | "高估區"
  sigma_from_hwm:   float,   # 當前距 HWM 幾個 σ
}
```

---

## §5 外部服務依賴（v10.0）

### 5.1 API 服務

| 服務 | 用途 | Key 位置 | 免費限制 |
|------|------|---------|---------|
| **FRED API** | 14+ 總經指標（含 OAS 日頻） | `secrets.toml: FRED_API_KEY` | 120 req/min |
| **Gemini API** | AI 分析（六章節輸出） | `secrets.toml: GEMINI_API_KEY` | 免費 tier RPM 限制 |
| **NAS Proxy** | 穿透抓取 MoneyDJ/TDCC（台灣 IP） | `secrets.toml: PROXY_URL` | 自建，無限制 |

### 5.2 資料來源（爬取，免 Token）

| 來源 | 資料類型 | 須 Proxy | 更新頻率 |
|------|---------|---------|---------|
| MoneyDJ wb01/wb05/wb07 | 含息報酬率 / 配息率 / 風險評比 / TER | ✅ | 日/月 |
| MoneyDJ NAV 頁 | 每日淨值歷史 | ✅ | 日 |
| TDCC openapi | 境外基金搜尋 | ✅ | 即時 |
| yfinance | VIX / DXY / ADL / COPPER | ❌ | 日 |
| Fundclear | 境內基金 NAV / 配息 | ❌ | 日 |
| cnyes 鉅亨 | 備援 NAV / 配息 | ❌ | 日 |
| Morningstar | 備援 NAV / 元數據 | ❌ | 日 |
| RSS（Reuters/Yahoo/WSJ）| 財經新聞事件（近 180 天）| ❌ | 即時 |

### 5.3 Python 套件（requirements.txt）

| 套件 | 版本約束 | 用途 |
|------|---------|------|
| `streamlit` | ==1.45.1 | UI 框架 |
| `pandas` | >=2.0.0 | 資料處理 |
| `numpy` | >=1.24.0 | 數值運算 |
| `plotly` | >=5.18.0 | 互動圖表 |
| `yfinance` | >=0.2.36 | 共同基金/行情 |
| `google-generativeai` | >=0.5.0 | Gemini API |
| `requests` | >=2.31.0 | HTTP 爬取 |
| `beautifulsoup4` | >=4.12.0 | HTML 解析 |
| `lxml` / `html5lib` | — | BS4 解析器 |
| `feedparser` | >=6.0.8 | RSS 新聞事件抓取 |
| `scipy` | >=1.11.0 | 投資組合最佳化（SLSQP） |
| `urllib3` | >=2.0.0 | HTTP 重試機制 |

### 5.4 Streamlit Secrets 必填欄位

```toml
# .streamlit/secrets.toml
FRED_API_KEY   = "..."    # 必填，否則總經指標全部失敗
GEMINI_API_KEY = "..."    # 必填，否則 AI 分析無法使用
PROXY_URL      = "http://user:pass@yourname.synology.me:3128"  # 必填，否則 MoneyDJ 被境外封鎖
```

> ⚠️ **環境遷移防雷（v18.146 / 2026-05-19）**：OAuth client 區段**不可**寫死 `redirect_uri = "https://<舊子網域>.streamlit.app/"`。Streamlit Cloud 重建 / 換倉 / 遷移會分配新的 hash 子網域，硬編碼會造成 `redirect_uri_mismatch`。請讓 `ui/helpers/oauth_state.py` 用 runtime URL 推導，secrets 只填 `client_id` / `client_secret`。同步 GCP Console 「已授權的重新導向 URI」白名單需含現役 streamlit.app URL（含結尾斜線）。

---

## §6 Session State Schema（v10.0）

| Key | 型別 | 預設值 | 寫入方 | 讀取方 |
|-----|------|--------|--------|--------|
| `macro_done` | `bool` | `False` | Tab1 | Tab1 防重複 |
| `indicators` | `dict[str, dict]` | `{}` | Tab1 | Tab2/3/5/AI |
| `phase_info` | `dict` | `{}` | Tab1 | Tab2/3/AI |
| `oas_z_score` | `dict` | `{}` | Tab1 **(v10)** | Tab1/2/AI |
| `macro_last_update` | `datetime\|None` | `None` | Tab1 | Sidebar |
| `macro_ai` | `str` | `""` | Tab1 AI 按鈕 | Tab1 渲染 |
| `current_fund` | `dict\|None` | `None` | Tab2 | Tab2/Tab5 |
| `fund_data` | `dict\|None` | `None` | Tab2 | Tab2 |
| `portfolio_funds` | `list[dict]` | `[]` | Tab3 | Tab3/Tab5 |
| `news_items` | `list[dict]` | `[]` | Tab1 RSS | Tab1/AI |
| `systemic_risk_data` | `dict\|None` | `None` | Tab1 | Tab1 警示卡 |
| `event_alerts` | `list[dict]` | `[]` | Tab1/2 **(v10)** | Tab1/2 警報卡 |
| `data_registry` | `dict` | `{}` | `_update_data_registry()` | Tab5 |
| `stale_indicators` | `list[str]` | `[]` | Tab5 **(v10)** | AI Prompt 注入 |
| `api_latency_log` | `list[dict]` | `[]` | Tab1/Tab5 | Tab5 延遲圖 |
