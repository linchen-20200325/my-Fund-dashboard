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
Streamlit Cloud 部署的機構級共同基金監控儀表板，整合總經指標、事件驅動分析、單一基金深度診斷、投資組合管理與轉申購試算，透過 NAS Proxy 穿透抓取 MoneyDJ / TDCC 境內資料。（v18.176 移除回測 Tab；v18.178 連同 `services/backtest_service.py` + `test_backtest_engine.py` 一併刪除 dead code。下方 §4.5b 等歷史 backtest_engine 段落為 pre-existing drift，本次未重寫。）

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

> 🆕 **v18.147 / 2026-05-19** — Tab3 expander「📋 保單管理（Google Sheets）」內部順序對齊標題承諾：`Sheet 設定 → 保單清單 → 多帳本管理 → 一鍵存讀 → 本機 JSON 備份`。新增 `list_user_folders()` 走 Drive v3 API（`client.http_client.request('get', ...)` 不依賴 googleapiclient），`list_user_sheets()` 加 `folder_id=''` kwarg（gspread 6.x 原生支援）。OAuth wizard 加 redirect_uri 自動正規化（缺 scheme 補 `https://`、缺 path 補 `/`）。

> 🆕 **v18.148 / 2026-05-20** — `ui/helpers/oauth_state.py` 加 `refresh_oauth_state()`：把 `_oauth_cfg` / `_oauth_configured` 從 module-import-time snapshot 改成 per-render refresh。`render_portfolio_tab()` 開頭 + `app.py` sidebar 渲染前各呼叫一次，並 local 重 `from ... import` 拿 fresh 值。修補 wizard「💾 套用設定」按了沒反應的 bug（原本 session_state 寫入後 `st.rerun()` 不會重 run module body → snapshot 永遠 stale）。Streamlit Secrets `[google_oauth]` 永久設定路徑不受影響。

> 🆕 **v18.149 / 2026-05-20 (PR A)** — Schema v2 後端 + migration 工具上線。新 schema 把舊三 tab（保單分頁 + `_T7_State` + `_Ledgers`）的「**目前持倉**」內聯到單張保單 worksheet，砍掉「同筆資料散三 tab」的舊架構。`repositories/policy_repository.py` 新增 `ALL_COLS_V2`（11 欄）+ `detect_sheet_schema_version` / `load_policy_v2` / `write_policy_v2` / `load_all_policies_v2` / `is_v2_worksheet` / `copy_sheet_as_backup`。`scripts/migrate_v149_schema.py` 提供 `migrate_sheet(with_backup=True)` 一次性升級工具：safety net 先 `client.copy(src_sheet_id, copy_permissions=False)` 備份整本 Sheet → 才轉換各保單分頁；冪等對已 v2 的 worksheet 自動跳過。Tab3 加偵測 + 升級按鈕；舊 v1 寫讀路徑完整保留，PR B 才接 v2 編輯 UI。

> 🆕 **v18.150 / 2026-05-20 (PR B)** — v2 native 編輯 UI 上線。新模組 `ui/helpers/v2_editor.py` 提供 `render_v2_section(client, sheet_id)`：偵測 v2 schema 時自動接管編輯路徑；每張保單一個 expander 區塊內含 fund / cash 兩個 `st.data_editor`（dynamic rows）+ 個別 [💾 存到雲端] 按鈕（dirty tracking、推 `write_policy_v2`）。Empty sheet 顯示「🚀 第一次使用」按鈕跳 3-step wizard（保單名 + 第一檔基金 + 現金可跳過）。T7 模組 `tab3_t7_ledger.py` 開頭偵測 v2 → 紅字 banner 提示「T7 為純模擬器、真實加碼/贖回請至 v2 編輯介面或直接改 Sheet」。本 PR 不動 v1 路徑、不切換「📦 全部寫入/讀回」主路徑（留 PR C）。

> 🆕 **v18.151 / 2026-05-20 (PR B.1)** — 載入按鈕上移 + 未綁基金快捷。`ui/helpers/portfolio_load.py` 把 `tab3_portfolio.py:1656` 原本散在 batch-add 表單下方的 ~70 行 fetch 邏輯抽出（含 cache clear / dedupe / status+progress / broadcast / errors），改為 `count_unloaded_funds()` + `batch_load_unloaded_funds()` 兩個 module-level helper。「🗂️ 保單分組視圖」expander 頂部加 prominent 載入按鈕（user 不用滾到底）；「📂 未分組基金」區塊加 inline `[📡 載入這 N 檔]` 與 v2 用戶獨享的 `[🔗 綁到保單 ▾]` selectbox（一鍵 set `policy_id`）。

> 🆕 **v18.152 / 2026-05-20 (PR B.2)** — Google Sheets 429 quota 退避 + 60s cache + 友善訊息。`repositories/policy_repository.py` 加 `_QUOTA_BACKOFFS` / `_is_quota_error` / `_with_quota_retry`（與 `snapshot_repository` 一致，1s→2s→4s→8s 共 4 次），所有 v2 read/write 函式包進去。`ui/helpers/v2_editor.py` 加 `st.cache_data(ttl=60)` wrapper（`_cached_list_policies` / `_cached_load_policy_v2`），client 參數用 `_client` 底線前綴避 Streamlit hash；寫入/刪除/重讀後 `_invalidate_cache(sheet_id)`。`_show_quota_friendly()` 偵測 429 → 顯示「⏳ Google Sheets API 配額暫時超載...請等 30-60 秒」與重試按鈕，取代 raw stack trace。

> 🆕 **v18.155 / 2026-05-20 (PR B.5)** — `list_user_sheets` 過濾已刪除 Sheets。原本 gspread `list_spreadsheet_files()` 會回傳 trashed sheets（user 截圖出現重複 / 殭屍項目）。改成自己打 Drive v3 API（mirror `list_user_folders`）帶 `q='mimeType="...spreadsheet" and trashed=false'`，外加 `supportsAllDrives` / `includeItemsFromAllDrives` 與 paging。

> 🆕 **v18.201 / 2026-05-24** — yfinance 走 proxy（v5.0 spec Task1 連線防護）。稽核發現 `fund_repository.get_latest_fx`（USDTWD=X）/ `get_latest_nav`（NAV）直連 `yf.Ticker` 未走 proxy → Cloud IP 被 Yahoo 擋 403/限流（AppTest test_tab3_kpi 的 0050/USDTWD=X 即此）。改用 `macro_repository.fetch_yf_close`（Yahoo Chart REST API + `infra.proxy.fetch_url` + 10min TTL，總經層已驗證可行），lazy import 避循環；Morningstar/Cnyes fallback 不動。`financial_repository` 三率（季財報無 Chart API）維持優雅降級。新增 guard test，596 passed。

> 🆕 **v18.200 / 2026-05-24** — 429 治本（承 v18.199）。`load_all_policy_worksheets` 原本 `list_policy_worksheets`（open+worksheets）後**逐分頁再 open_by_key**，N 保單 ≈2+3N 讀。重構：抽 `_records_to_policy_df()`（load_policy_worksheet 與 load_all 共用解析）；load_all 改 **open 一次 → `sh.worksheets()` 一次拿所有分頁物件（清單+讀取 handle 二合一）→ 逐物件 get_all_records**，降到 ≈2+N（4 保單 14→6）。配合 v18.199 一次切換 ~18→8 讀。所有 gspread 呼叫包 `_with_quota_retry`。mock `_make_sh_with_worksheets` 改回真 ws 物件。85 + 595 passed 零回歸。

> 🆕 **v18.199 / 2026-05-24** — 修「切換/重讀帳本」429 Quota exceeded。Google Sheets 60 reads/min/user，切換帳本觸發 auto-load(v18.185)+手動讀回各跑一次 `load_all_from_sheet`（多次 open_by_key + list + per-policy + `_T7_State`）→ 爆配額、`_with_quota_retry` 15s 救不回。Fix：(1) `load_all_from_sheet` 不再額外 `list_policy_worksheets`（`load_all_policy_worksheets` 內部已 list），改從回傳 DataFrame 的 `policy_id` 欄推 `policy_tabs`，省一次讀；(2) 偵測 `_is_quota_error` → 友善訊息「等 30-60 秒再讀回」取代 raw APIError。改 5 test，595 passed。後續治本：load_all_policy_worksheets open 一次重用 handle / 短 TTL 快取。

> 🆕 **v18.198 / 2026-05-24** — 保單分頁「存全」。痛點「存檔資料沒有全部」：v1 保單分頁缺成本基礎（avg_nav/fx_avg/units，只在 `_T7_State`/`_持倉總覽`）。`OPTIONAL_COLS` 純追加 `avg_nav`/`fx_avg`/`units`（ALL_COLS 11→14、表頭升級自動 A1:N1）。寫入（`dump_all_to_sheet` + T7 套用）成本基礎優先取 `t7_ledgers[pk].position`、缺退 portfolio_funds；T7 submit 也把 cost 寫進 portfolio_funds。讀回 `sync_policies_to_portfolio_funds` 帶 avg_nav/fx_avg/units（有值才帶、空欄不覆蓋），配合 v18.191 reconcile 雙保險。既有 test 因用 `list(ALL_COLS)` 自動相容；新增 3 test，595 passed。

> 🆕 **v18.197 / 2026-05-24** — hotfix「全部讀回」ValueError + v5.0 收尾驗收。user 按讀回 → `ValueError: truth value of a Series is ambiguous`。根因（v18.185 潛伏）：`reuse_fund_info_by_code` 的 `if v not in (None, "")` 對 `series`（pandas Series）做相等判斷 → 回 Series → bool() 爆。Fix：逐欄判斷（None 跳過、空字串才跳過、series/dict/list 直接複製）+ 加真 pd.Series 回歸 test。收尾驗收跑 `pytest -m "not slow"` 抓到 2 個潛伏失敗：`test_tab6_manual` 仍假設 8 sub-tabs（Tab6 早已 10）→ 修 test expect 10。全綠 592 passed / 1 skipped。

> 🆕 **v18.196 / 2026-05-24** — Task3 AI 解盤補完。`repositories/news_repository.py` 加 `ASSET_CLASS_KEYWORDS` + `infer_asset_class(text)` + `filter_news_by_asset_class(news, cls)`（純過濾、零網路、systemic 永留、空回退、中文別名）+ `fetch_macro_news(asset_class, max_per_feed)`（spec 接口 = fetch_market_news + filter）。接線：Tab2 AI 摘要依該基金類別、Tab3 依組合主類別過濾**已快取**的 `session_state.news_items`（不在 render 路徑重抓 RSS）；Tab1 本即總經=macro（不過濾），無需改。AI widget 本就在 Tab1/2/3，本次補的是「新聞依資產類別」。新增 6 test，114 PASSED。

> 🆕 **v18.195 / 2026-05-24** — Task2.2-step2b 組合 Tab 故事站標題。發現配置總覽核心（健康儀表+戰情室）已在頂部、且自動讀回埋在頂部 expander → 中段顯示區塊無法上移（load→display 順序），大區塊搬移風險高且沙箱無法驗畫面。改採 user 選的「加故事站標題」：在既有結構加 4 個 `###` 標題標示動線 — ① 📊 配置總覽 / ② ➕ 加入與管理 / ③ 💼 持倉戰情(T7) / ④ 🔬 重疊度診斷(T5)，呼應頂部 tab 麵包屑。純 markdown 加/改、零區塊搬移、零變數變動、各 header 縮排正確且非巢狀 expander。99 PASSED。

> 🆕 **v18.194 / 2026-05-24** — Task2.2-step2a 組合 Tab 內部故事線。`render_portfolio_tab()` 原順序「收益矩陣 → T5 重疊診斷 → T7 持倉帳本 → AI」把持倉排在診斷之後、違反敘事；將 `render_t7_section()` 移到 T5 之前 →「… → T7 持倉戰情 → T5 重疊診斷 → AI」。先以 Explore 全函式 mapping 驗證依賴：T7 為自含函式（讀 session_state）、置於所有載入/加入區塊後、與 T5 的 `_t5_groups`/series 無交叉 → 零 use-before-define 風險（全檔僅 1 處呼叫）。配置總覽上移等多區塊大搬動延後（沙箱無法驗畫面）。99 PASSED。

> 🆕 **v18.193 / 2026-05-24** — Task2.2-step1 故事化動線。`app.py` `st.tabs` 重排為 **總經→組合→單一基金→資料診斷→說明書**（原單一基金在組合前、違反 spec 敘事；變數改語意名、render 函式不變）。新增 `ui/helpers/story_nav.py`（`story_nav_markdown` 純函式 + `render_story_nav`），三敘事 tab 標題下加「① 🌐 總經環境 → ② 📊 核心/衛星配置 → ③ 🔍 單一基金深掘」麵包屑（目前站藍色 highlight）。偏視覺故分階段：tab 內部區塊重排留作逐 tab 後續。新增 4 test，99 PASSED（含 full app.py exec）。

> 🆕 **v18.192 / 2026-05-24** — Task2.1 教學化 expander。新增 `ui/helpers/metric_explainers.py`（`METRIC_EXPLAINERS` 8 條指標白話文 + 實戰意義；純函式 `explainer_markdown` + `render_metric_explainer` 渲染 `st.expander`、內容/渲染分離）。Tab2 風險指標（σ/Sharpe/Alpha/Beta）與 Tab3 核心/衛星 Hero 下方就近加「💡 這些數據代表什麼？」收合說明，**不動既有數據顯示、純加法**。兩 call site 經查非在 expander 內（不觸發巢狀 crash）。新增 5 test，109 PASSED。

> 🆕 **v18.191 / 2026-05-24** — 讀取齊全。user「讀取資料時帳本一直缺資料」。以 user 實際 JSON 備份驗證：portfolio_funds(19)⨝t7_ledgers(19) pk 100% 對得上、`Ledger.from_dict` 19/19 含完整成本 → JSON 還原本身齊全；缺料發生在 Sheet 讀回（表單/帳本表以 portfolio_funds 為 spine 迭代、用 `fund_pk_str` 取 t7_ledgers 成本，保單分頁與 `_T7_State` 漂移時只在快照的基金看不到）。Fix：新增純函式 `reconcile_funds_with_ledgers`（`ui/helpers/portfolio_load.py`）— 帳本有但 spine 缺的部位用 `parse_pk` 補成 portfolio_funds 條目 + 回填 avg_nav/fx_avg/units/avg_nav_with_div（缺值才補）。接 `load_all_from_sheet` 與 `restore_from_json_bytes` 兩讀取路徑。實證模擬漂移 5/19→補回 19。新增 4 test，132 PASSED 零回歸。

> 🆕 **v18.190 / 2026-05-24** — log 降噪。user Cloud log 兩類噪音：① `Styler.applymap` FutureWarning（`tab3_t7_ledger.py:1995` + `tab3_portfolio.py:2053`；pandas 2.1 deprecate、3.0 移除）→ 兩處改 `.style.map(`，`requirements.txt` pandas floor 2.0.0→2.1.0；② `precision_service.py` 兩處 `logger.warning`（宏觀資料對齊後 <20 → 回中性 0.0/空 df）每 rerun 刷屏 → 降為 `logger.debug`（Tab1 UI 已另顯友善提示）。宏觀資料實際 0 筆為部署端 FRED/yfinance 可用性問題、非本次 scope。126 PASSED 零回歸。

> 🆕 **v18.189 / 2026-05-24** — 「存檔無含息來源」§5 除錯協議。user 回報「保單分頁存完沒有含息成本欄」。完整追蹤 per-policy 寫+讀路徑（`upsert_fund_in_policy` 表頭自動升級成 ALL_COLS 11 欄 `A1:K1`、`_row_to_list` 含 `avg_nav_with_div`、`load_policy_worksheet` reindex、sync 有值才帶）**全部正確**，已修 3 次（v18.180/183/184）→ 依 §5 不盲改第 4 次。改做除錯協議：(1) `dump_all_to_sheet` 原 `except: continue` 靜默吞 per-fund 寫入失敗 → 改收集 (pid/code+原因) 進 `warnings`，根因可見；(2) 釐清 v1 保單分頁表頭是**英文 key**（`avg_nav_with_div`），非中文「平均買入含息單位成本」（只在 v2）→ user 找中文欄名會誤判「沒有」。待 user 驗證英文欄名 / 部署是否更新 / 重存看 ⚠️。新增 1 test，13 PASSED 零回歸。

> 🆕 **v18.188 / 2026-05-24** — 移除「📁 多帳本管理」區塊（`ui/tab3_portfolio.py`，建立/改名/切換三 tab 共 123 行）。user 決定改用「📥 雲端讀取（從 Drive 挑帳本）」+「📦 雲端存檔」以存取/讀取方式管理多帳本，不再需要獨立「切換到此帳本」流程（建立新帳本見「✨ 新增帳本」、改名在 Drive 操作）。順手刪只此處用到的 `rename_sheet` import。v18.185 auto-load / v18.187 t7_ledgers 空→清 仍適用於挑帳本路徑（`policy_sheet_id` 改變即觸發）。99 PASSED 零回歸。

> 🆕 **v18.187 / 2026-05-24** — 修「切換帳本後帳本無法更新」。`load_all_from_sheet`（`ui/helpers/cloud_io.py`）原只在新帳本有 `_T7_State` 快照時才覆蓋 `t7_ledgers`，切換到無快照的帳本時殘留前一本（v18.185 自動讀回放大此 stale）。改 `ss["t7_ledgers"] = _restored or {}`（空→清）+ 一律清 `_t7_auto_restore_done`/`_t7_auto_estimate_done` 旗標 → 新本無快照時 T7 重跑 auto-restore、維持空（正確）。`_sync_invest_twd_from_ledgers` 仍只在有快照時呼叫（避免空帳本歸零 invest_twd）。含息來源存檔（user 另一抱怨）經追蹤寫+讀全正確、已修 3 次，依 §5 不盲改待精確重現。新增 2 regression test，119 PASSED 零回歸。

> 🆕 **v18.186 / 2026-05-24** — 連線健檢 #1：`repositories/news_repository.py` RSS 改走 `infra.proxy.fetch_url`（timeout=12 + 407/403×2 自動降級直連），feedparser 改解析 bytes；抓取失敗不再 `except: pass` 靜默而累計來源，結果為空回友善提示（⚠️ Proxy 斷 vs ℹ️ 無命中）。補上 fund_fetcher / fund_repository（全局 urllib opener）/ macro_repository 之外最後一條沒走 proxy 的抓取路徑。互動元件稽核：Explore 標的 8 個可疑元件全驗為 LIVE（含 `tab5 _snap_sel` 誤報），無死按鍵。`fetch_market_news` 簽名不變。新增 4 test，109 PASSED 零回歸。

> 🆕 **v18.185 / 2026-05-24** — 切換帳本自動讀回 + 跨帳本共用基金資訊。User 反映 ①切換帳本後沒載入鍵與計算 ②同一檔基金在不同帳本會被重抓 MoneyDJ。根因：「🔁 切換到此帳本」只 set `policy_sheet_id`+rerun（無自動讀回）；`sync_policies_to_portfolio_funds` 以 `(policy_id, fund_code)` 複合鍵 merge → 換帳本 policy_id 不同 → 同 code 變 `loaded=False` 全部重抓（但 NAV/指標只跟 fund_code 有關）。Fix：(a) 新增純函式 `ui/helpers/portfolio_load.py:reuse_fund_info_by_code(merged, previous_funds)`，把上一本已 `loaded` 條目依 code 補回 fund-info 欄（空值不覆蓋），`load_all_from_sheet` sync 後呼叫、report 加 `reused`；(b) `render_portfolio_tab` 早段加 `_last_loaded_sheet_id` 追蹤，id 變且雲端可達就自動 `load_all_from_sheet`（持倉切換+資訊沿用、零 MoneyDJ）+ `st.toast`；(c) 新標的留給既有「📡 載入未載入基金」按鈕抓。防呆：首次進入且已有本地持倉（剛還原 JSON）只記 id 不自動讀回，避免覆蓋本地。212 PASSED 零回歸。

> 🆕 **v18.184 / 2026-05-23** — T7 持倉明細表加「含息成本 + 累積已配息率」欄。User 反映 ①含息來源沒在存檔 ②之前說含息成本可算含息率但分析沒看到。釐清：「含息來源」是 A/B 輸入方式（不持久化）、其結果含息成本(`avg_nav_with_div`/`cost_unit_with_div`)有存；真 gap 是 `cost_unit_with_div` 一直被收集+存檔卻從沒在任何顯示分析用過（dangling input）。Fix（user 選「累積已配息率」）：`tab3_t7_ledger.py` 持倉明細 `_snap_rows` 加兩欄 — 含息成本 + 累積已配息率 =(平均買入淨值−含息成本)/平均買入淨值（純成本面、不需即時 NAV；未填顯「—」）；併入綠色著色 subset，units≤0 分支同步補欄。純顯示層，128 PASSED 零回歸。

> 🆕 **v18.183 / 2026-05-23** — `div_cash_pct` + `avg_nav_with_div` 加進 v1 保單分頁 schema。User 反映「div_cash_pct 存檔不在 google sheet」：根因 v1 `ALL_COLS` 無這兩欄 → 從不寫進保單分頁、`全部讀回` 歸零（只 JSON 留得住）；v2 schema 早有、但 user 走 v1+T7。Fix：`OPTIONAL_COLS` 尾端追加 `div_cash_pct`/`avg_nav_with_div`（純追加、既有欄位位置不變、`ALL_COLS` 9→11）。`upsert_fund_in_policy`（per-policy 分頁、user 路徑）寫入前表頭缺新欄就 `update("A1:K1", ALL_COLS)` 升級（既有列尾端補空、不錯位），cols 固定 ALL_COLS；寫入端（T7 套用 v18.179 區塊 + `dump_all_to_sheet`）row 帶兩欄。`upsert_policy_row`（legacy Policies 單表）改寫「表頭實際有的欄交集」避免孤兒欄、不強制升級（向後相容）。`sync_policies_to_portfolio_funds` 讀回兩欄進 portfolio_funds（有值才帶、空欄不覆蓋記憶體）→ 全部讀回不歸零。改 1 舊 test + 新增 3 test，269 PASSED 零回歸。

> 🆕 **v18.182 / 2026-05-23** — 新增「人看得懂的完整成本帳本」分頁 `_持倉總覽`。User 反饋「看不到 T7、帳本資料沒在 Excel」：釐清後 ①user 在看 Google 預設空白 `工作表1`（資料其實在保單分頁、user 確認有資料）②完整帳本（單位數/含息成本…）只存 `_T7_State`（JSON blob、人看不懂）且 user 的 Sheet 沒這分頁。新增 `repositories/snapshot_repository.py` `save_holdings_overview()`：t7_ledgers ⨝ portfolio_funds 組「每檔基金一列」可讀表格寫進 `_持倉總覽`（`_` 開頭→不被 `list_policy_worksheets`/`detect_sheet_schema_version` 誤認成保單分頁；clear+batch 同 `_T7_State` 模式）。欄位：保單號碼/基金代碼/基金名稱/幣別/級別/單位數/平均成本/含息成本/匯率/投資金額(TWD)/現金給付%/累積已領配息/更新時間（台灣時間）；只存成本面、不存市值（市值隨 NAV 過時）。接 `_t7_save_snapshot_to_sheets()` + `dump_all_to_sheet()` 兩處（寫完 `_T7_State` 後）。repo 層用固定 UTC+8（不 import ui，避免反向依賴）。新增 3 test，236 PASSED 零回歸。

> 🐛 **v18.181 / 2026-05-23** — 修「上次寫入/讀回」時間戳顯示 UTC（應為台灣 UTC+8）。User 截圖：雲端存檔面板「上次寫入：13:26」看起來「不會動」、對不上 Google Drive 的「晚上9:25」。實為時區 bug — 13:26 UTC = 21:26 台灣，同一刻差 8 小時；`t3_last_save_at` 每次寫入都有更新（無 reset），只是 bare `datetime.now()` 在 Streamlit Cloud 跑 UTC。Fix：新增 `ui/helpers/tw_time.py`（`tw_now()` / `tw_now_str()`，固定 UTC+8 offset、不依賴 tzdata、台灣無 DST），改 5 處 wall-clock 時間戳（`tab3_portfolio.py` 上次寫入/讀回/JSON 備份檔名、`json_backup.py` `exported_at`、`tab3_t7_ledger.py` 方案 `created_at`），順手清 inline `import datetime as _dt_q/_dt_top` dead import。方案 id 的 `.timestamp()`（epoch）與 ledger `.today()`（日期）tz 無關不動。222 PASSED 零回歸。

> 🐛 **v18.180 / 2026-05-23** — 修 T7 含息成本不生效 + JSON 備份漏存含息/現金給付%。User 反饋套用起始部位後 ①ledger 看起來沒變（`cost_unit_with_div` 永遠 = `cost_unit`）②下載的 JSON 沒有「現金給付 %」「含息來源」。Bug A（`ui/tab3_t7_ledger.py:676`）：建 ledger 時 `subscribe(_amount_twd, _fx, _cu, …)` 傳淨值 `_cu` 非含息成本 `_anw`，`subscribe()` 首買把 `cost_unit_with_div = nav` → 對帳單欄(10) 含息成本被覆蓋；Fix：subscribe 後 `if _anw > 0: _new_led.position.cost_unit_with_div = float(_anw)`。Bug B（`ui/helpers/json_backup.py`）：`build_export_payload` slim fund 欄位漏 `avg_nav_with_div` + `div_cash_pct`；Fix：補兩欄，restore 沿用「保留 JSON 全部 key」自動還原。背景：v1 保單分頁 `ALL_COLS` 無此兩欄，JSON 備份是唯一持久化途徑（user 選「含息+JSON 兩修」、暫不擴充 v1 schema）。222 PASSED 零回歸。

> 🐛 **v18.179 / 2026-05-23** — 修 T7「💾 套用為起始部位（覆蓋 T7 帳本）」存檔不回寫保單分頁。User 截圖反饋：在「✏️ 編輯持倉」表單輸入各基金淨投資金額後存檔，新增/編輯的項目不會回寫到實際讀寫的保單分頁（如 `QL19676552`），只能每次下載手改。根因（`ui/tab3_t7_ledger.py` submit handler）：存檔只寫 ①本地 `t7_ledgers` ②`_T7_State` 快照 ③`_Ledgers` 交易分頁；保單分頁的 `upsert_fund_in_policy` **只在 `_pid_changes`（保單號碼改變）時觸發** → 同保單內編輯金額（無 pid 變更）的基金列永遠不更新。Fix（全量同步）：新增 `_funds_to_sheet` 收集每一檔已套用且有 pid 的基金 `(pid, code, fund_obj)`；OAuth 區塊改成全量 `upsert_fund_in_policy`（帶 invest_twd / currency / policy_tier），涵蓋「新增 + 同保單編輯」；notes 對 pid 變更標 `T7 pid migrate`、其餘 `T7 套用起始部位`；成功訊息加「+ 保單分頁回寫 N 檔」；`policy_tabs` cache 改在 `_funds_to_sheet` 非空時刷新。無 pid 的基金（未綁保單）仍不寫（無分頁可寫）。`test_app_smoke + test_policy_store + test_cloud_io` 185 PASSED 零回歸。

> 🐛 **v18.172 / 2026-05-22** — T7 KPI 拆「現金配息 / 配股」+ 鬼列 filter 補修大寫。User 截圖反饋 T7 帳本 KPI「💵 預估年配息 / 📅 每月被動現金流」沒套用 `div_cash_pct`（即使設部分配股，現金流仍顯全額），且配股估算未分開顯示；同時截圖底部又冒出 `FUND_URL` 大寫鬼列。Fix（`ui/tab3_t7_ledger.py`）：累計變數 `_ann_total_twd` 之外新增 `_cash_total_twd / _reinvest_total_twd` 依各檔 `div_cash_pct` 拆分；per-row 加「預估月配股 (TWD)」欄；KPI 5→6 columns，KPI3 改「💵 預估年現金配息 (TWD)」用 cash-only、KPI4「📅 每月被動現金流」用 cash-only/12、新增 KPI5「🪙 預估年配股 (TWD)」、重置按鈕移到 _pc6。鬼列補修（`policy_repository.py:516-528`）：v18.171 filter `fund_url=='fund_url'` 只擋小寫，但 `dump_all_to_sheet:47` 把 `code .upper()` 後鬼列回寫變 `FUND_URL` 大寫繞過；改 `.str.lower()` case-insensitive 並加 regression test。10 個 test PASSED 零回歸。

> 🐛 **v18.171 / 2026-05-22** — 修保單分頁「schema 鬼列」append_row bug。User 反饋「📋 保單分頁清單」存檔後 `QL19676552` tab 出現 3 列 `policy_name / fund_url / invest_date / currency / notes` 等 schema 英文 key 字串當資料值的鬼列。根因：`policy_repository.py:474 & :480 & :276` 用 `ws.append_row(list(ALL_COLS))` 補表頭，gspread `append_row` 是**追加到資料末列**而非插入 row 1；當 worksheet 已存在但 row 1 被讀成空（user 在 Sheets 手動清過 header），表頭就漂到資料底部變成鬼列；多次「全部寫入」累積 3 列。Fix：3 處 `append_row(list(ALL_COLS))` → `ws.update("A1", [list(ALL_COLS)])` 強制 row 1；`load_policy_worksheet` 加防禦過濾 `(fund_url=='fund_url') & (invest_date=='invest_date') & (currency=='currency')` 鬼列，現存髒資料畫面立刻乾淨。更新既有 test + 新增 2 個 regression test（worksheet 已存在但 row 1 空 / load 過濾鬼列），`test_policy_store.py` 79/79 PASSED 零回歸。

> 🆕 **v18.170 / 2026-05-22** — T7 編輯持倉表單暴露 `div_cash_pct`（配息現金給付%）+ 月配息估算（部分配息+部分配股新功能）。User 反映保單實際支援部分配息+部分配股，希望用「資金百分比」算每月配息與配股。v18.160 已建好 `div_cash_pct` schema / `estimate_dividend_split` / v2 editor 欄位 / 年度估算 expander，但 T7「📝 編輯持倉」表單未暴露此欄位、估算只有年度。`tab3_t7_ledger.py:564` `st.columns([1,1,1,1,1])` → `st.columns([1,1,1,1,1,1])`；L615+ 新增 `ic6.number_input("🟨 現金給付 %", 0-100, step=5, default=100)`；`_init_inputs` tuple 加 `_dcp` 第 11 個元素；submit handler 寫入 `_f_obj["div_cash_pct"] = max(0, min(100, float(_dcp)))` 同步存回 Sheet。`v2_editor.py:151-204` `_render_div_split_estimate` 加 `st.segmented_control(["📅 年估算", "📆 月估算"])` toggle；月模式下 `annual_div_rate_pct / 12` 傳給 `estimate_dividend_split`，表格欄位與 3 個 metric 標題隨 `_label="月"/"年"` 動態切換。`estimate_dividend_split` 函式簽名未變、既有 4 個測試 case 零回歸。

> 🆕 **v18.169 / 2026-05-22** — 「📋 保單清單」說明區塊從 Tab3 expander 搬到 Tab6 說明書（§9 Sheet 資料結構）。User 截圖反饋：Tab3 expander 內「📋 保單清單（這本 Sheet 內的保單分頁與輔助 tab）」屬於使用說明性質、不該占動作面板版面。`tab3_portfolio.py:644-675` 刪除整個 `if _sheet_id:` 區塊（32 行：markdown 標題 + caption 說明 + 3 個 `st.metric`（保單分頁 / `_T7_State` / `_Ledgers` 計數）+ 可選的 `last_sync` caption），改 1 行 v18.169 註解；動態 metric 數字（`_sheet_stats`）user 決定捨棄不重現（Tab6 為靜態說明書）。`tab6_manual.py` `_t6 = st.tabs([...])` 從 8 個加到 9 個、新增「📋 9. Sheet 資料結構」sub-tab；內容為純靜態 markdown：4 欄表格（Tab 類型 × 命名規則 × 用途 × 同步來源）涵蓋保單分頁 / `_T7_State` / `_Ledgers` 三類 + 4 個重點觀念（底線開頭系統保留 / 保單分頁可自由增減 / `_T7_State` 是快照 / `_Ledgers` 是流水）+ 多帳本管理引導。module docstring 同步「8 sub-tab」→「9 sub-tab」標註 v18.169。

> 🆕 **v18.168 / 2026-05-22** — 📥 雲端讀取面板上下半對調（先挑帳本後讀回）。v18.166 面板上半「全部讀回」、下半「從 Drive 挑帳本」，user 截圖紅框 + 紅箭頭反饋要對調符合操作順序（先挑後讀）。`tab3_portfolio.py:271-396` 上下兩段順序交換：上半「📂 從 Drive 挑帳本」整段（OAuth + 已登入恆顯示）+ 末端加 `st.markdown("---")` 分隔、下半「📥 全部讀回」（需有 `_sheet_id_q`，加 `**📥 全部讀回（雲端 → 本地）**` 標題；無 ID 時改顯示 info 引導去上方挑）。info 文案「下方挑一本」→「上方挑一本」對齊新版型。widget key 不變、純 UI 順序調整。

> 🆕 **v18.167 / 2026-05-21** — 刪除「🧰 一鍵存讀」「📁 本機 JSON 備份」雙入口，瘦身成「🛠️ 進階工具」。頂部 5 顆按鈕已完整覆蓋全部存讀，下方 expander 內 v18.50「🧰 一鍵存讀」(📦 全部寫入 + 📥 全部讀回 + 🔄 只重新整理 + 🗑️ 清空快取) 與 v18.70「📁 本機 JSON 備份」(💾 下載 + 📂 上傳) 兩段重複占版面，user 反饋「保留單一上方五個按鈕的功能」。`tab3_portfolio.py:895-1001` 移除 `btn_dump_all_v18_50` / `btn_load_all_v18_50` 兩顆按鈕 + 對應 `_dump_all_clicked` / `_load_all_clicked` handler block；header rename「🧰 一鍵存讀」→「🛠️ 進階工具」；保留兩個頂部沒有的小工具（🔄 refresh-only + 🗑️ 清空快取）改 `st.columns(2)` 並列、`use_container_width=True`；handler 簡化只剩 `if _refresh_clicked:` 走 `load_all_from_sheet(refresh_only=True)`。`tab3_portfolio.py:1003-1050` 刪除「📁 本機 JSON 備份」整段 47 行（與頂部 💾/📂 完全重複）。引導文字「下方「🧰 一鍵存讀」」→「頂部「🚀 快速存讀面板」」。Tab3 expander 瘦身 ~100 行。

> 🆕 **v18.166 / 2026-05-21** — 「從 Drive 挑帳本」從「✨ 新增帳本」面板移到「📥 雲端讀取」面板（職責分離）。User 截圖紅框 + 紅箭頭反饋 v18.165 把「自動建立」+「從 Drive 挑」上下並列在「✨ 新增帳本」造成困惑。「📥 雲端讀取」面板（`tab3_portfolio.py:263-405`）擴為上下並列：上半保留「全部讀回」邏輯（無 ID 時改顯示 info 引導去下方挑）、下半新增「📂 從 Drive 挑帳本」整段（資料夾清單 → 限定資料夾 → 列 Sheets → 選用，OAuth 登入時恆顯示）。「✨ 新增帳本」面板（`tab3_portfolio.py:432-490`）瘦身只剩「自動建立新 Sheet」，caption 加註「想挑 Drive 內既有的 Sheet 請改點 📥 雲端讀取」字面引導。語意對齊：「✨ 新增 = create new」「📥 雲端讀取 = pick existing + load」。6 個 widget key 移動非複製，仍唯一。

> 🆕 **v18.165 / 2026-05-21** — 快捷面板加第 5 顆「✨ 新增帳本」互動式 button。v18.164 把「✨ 新增帳本」做成 expander 內小標題（功能仍埋下方需捲），user 截圖反饋要求頂部「🚀 快速存讀面板」加第 5 顆 button 點下去直接顯示互動面板。`tab3_portfolio.py:212-237` `st.columns(4)` → `st.columns(5)`，順序 `📥 讀 / 📦 存 / ✨ 新增帳本 / 💾 下載 / 📂 上傳`，`✨ 新增帳本` 對應 `_io_panel == "new"`。新增 `elif _io_panel == "new":` 面板（`tab3_portfolio.py:340-486`）：上半「🚀 自動建立 Sheet」無條件顯示（user 已點 button = 想新增）、下半「📂 從 Drive 既有 Sheets 挑」（資料夾下拉 → 列 Sheets → 選用），未配 OAuth / 未登入顯示友善 warning。同時移除 expander 內 L630-770 v18.164 hoist 的重複區段（自動建立 + Drive 挑整段刪除避免 widget key 衝突），只留 `_sheet_id = session_state.get(...)` 一行。零作用域風險、純 UI 重組。

> 🆕 **v18.164 / 2026-05-21** — Sheet ID 輸入 hoist 到 sidebar +「✨ 新增帳本」互動式面板。User 截圖紅框反饋：Tab3「📋 保單管理」expander 內，OAuth 狀態 + Sheet ID 輸入並列占大半版面、「自動建立」與「從 Drive 挑」被「或者」分隔層次不一致。Sidebar 在「🔐 Google 帳號」之下新增「📋 工作中帳本」區塊（`app.py:280+`）：Sheet ID / URL 輸入 + 自動 regex 解析 `/spreadsheets/d/<id>/`、寫回 `policy_sheet_id`、顯示 `get_sheet_title` 取回的當前帳本名稱（快取 key `_t3_cur_sheet_title:<sid>`）。Tab3 expander（`ui/tab3_portfolio.py:485-544`）移除 `text_input("Google Sheet ID 或完整 URL")` 區塊，改為一行 `_sheet_id = session_state.get("policy_sheet_id") or _sheet_id_secret`；新增 `##### ✨ 新增帳本` header 統籌兩個子區塊，上半「自動建立 Sheet」（保留 `not _sheet_id` 條件避免噪音）、下半「從 Drive 挑」（移除「或者」措辭、僅在兩者皆顯示時加 `---` 分隔），版型上下並列。零作用域風險、純 UI hoist + 重組。

> 🆕 **v18.163 / 2026-05-21** — Tab3 KPI 合併 hero + sub-tab 改 `segmented_control`（消除上下兩段重複占版面）。抽 `ui/helpers/portfolio_health.py` 純函式：`compute_health_kpis(portfolio_funds, mk_df=None) -> dict` 整合 MK 標籤（撿便宜/留校/停利/配置比，從 `build_mk_dataframe` 結果算）+ 現金流（基金數/健康/吃本金/資料不足，從 `compute_1y_total_return` 算），`render_hero_kpi_cards(kpis)` 渲染 6 卡（基金數 / 配置比 / 現金流安全 N/M / 撿便宜 / 留校 / 停利）放在 Tab3 頂部當 hero。`mk_dashboard.render_mk_war_room` 移除 `_render_kpi_cards` 呼叫（hero 已涵蓋）+ `st.tabs` 3 sub-tab 改 `st.segmented_control`（基金池大小寫進 label：`🛡️ 核心戰情室（N 檔）`）。`tab3_portfolio.py:2148+` 移除下方重複 4 卡 KPI。T5 重疊矩陣維持 per-policy `st.expander(expanded=False)` 收合。新測 `test_portfolio_health.py` 9 cases。

> 🆕 **v18.162 / 2026-05-21** — Tab3 快捷面板雲端動作改真執行 + 抽 `ui/helpers/cloud_io.py` helper。v18.161 的 📥/📦 panel 只是「狀態 + 請往下捲」提示牌（user 三張截圖反饋「不太順」），且「目前帳本」誤讀 `active_policy_id`。本版 4 顆按鈕全部真執行：📥/📦 panel 顯示「📂 帳本：真實 sheet name（快取在 `_t3_cur_sheet_title`）｜ 持倉檔數 ｜ 上次讀寫時間」+ 「立即執行」按鈕一鍵到位；未登入/無 sheet_id 顯示友善 warning。抽 `cloud_io.py` 純函式：`dump_all_to_sheet(client, sheet_id, ss) -> {ok, written, skipped_no_pid, n_state, warnings, error}`、`load_all_from_sheet(client, sheet_id, ss, *, oauth_mode, refresh_only=False) -> {ok, refresh_only, added, kept, removed, restored_ct, warnings, error}`，streamlit-agnostic、致命錯誤與非致命 warning 分離。下方 L863+「一鍵存讀」段瘦身呼叫同一 helper，移除 ~120 行重複邏輯，加 caption「📌 主入口在頂部快捷面板」。新測 `test_cloud_io.py` 10 cases（monkeypatch 模擬 gsheets API）。

> 🆕 **v18.161 / 2026-05-21** — Tab3 IO toolbar 升級為互動式快捷面板。`tab3_portfolio.py` L176+ 把 v18.159 的「toast 跳轉」4 顆 button 改成 toggle（`session_state["t3_io_panel"]`，預設 `"load"`）：點哪顆下方 placeholder 渲染哪顆面板。📥 雲端讀取 / 📦 雲端存檔仍為導引（顯示『目前帳本 + 持倉檔數 + 上次讀寫時間 + ⬇️ 完整面板提示』，因依賴 `_client / _sheet_id / _active_book_id` 仍在下方才解析）；💾 下載 JSON / 📂 上傳 JSON **直接在快捷面板真執行**（純 session_state 操作）。抽 `ui/helpers/json_backup.py` 純函式：`build_export_payload(ss)`（剝大物件）、`restore_from_json_bytes(raw, ss)`（回 `{ok, n_funds, n_ledgers, error}` 統一介面）；上方面板與下方 L1008 完整面板共用同一份序列化規則，移除 80 行重複邏輯。雲端讀寫 success path（L791 / L860）寫入 `t3_last_save_at` / `t3_last_load_at` 供上方面板顯示。`test_json_backup.py` 8 cases 驗 empty/strip/ledger/restore/garbage/round-trip。零作用域風險、純 UI 改動。

> 🆕 **v18.160 / 2026-05-21** — 保單基金配息「現金給付 % / 增加單位數 %」拆分。v2 schema 擴第 13 欄 `div_cash_pct` (0~100，預設 100=全現金；單位% = 100 - 該值)，中英 header map `現金給付%` 對映，舊 12 欄 Sheet 載入時 `_normalize_div_cash_pct` 補預設 100、`is_v2_worksheet` 不變（向後相容）。`v2_editor.py` data_editor 加 `NumberColumn(0-100 step=10)` 並新增「📊 配息估算」expander：user 填年配息率假設 → 每檔基金估算年現金流入 / 年再投入 / 年新增單位數 + 3 metric 彙總。`policy_repository.estimate_dividend_split(invest_twd, annual_div_rate_pct, div_cash_pct, avg_nav, avg_fx)` 純函式回 6 欄 dict（`avg_nav=0` 邊界安全）。Tab3 `_render_tab3_ai_summary` 從 `_v2_buf` 撈 div_cash_pct + portfolio_funds metrics 的 `annual_div_rate` → AI snapshot 加「📊 年配息現金/單位拆分估算」段（總彙總 + 每檔細節）。+10 新測試覆蓋 schema/normalize/estimate/load 預設/merge round-trip。

> 🆕 **v18.157 / 2026-05-20 (PR B.6)** — 對帳單 type B 支援（累積配息反推含息成本）。User 反饋部分保單對帳單沒有「平均買入含息單位成本」欄，但有「累積現金配息金額 (NT)」。`policy_repository.avg_nav_with_div_from_cumul_div_twd(avg_nav, avg_fx, units, cumul_div_twd)` 公式 `avg_nav − cumul_div_twd / (avg_fx × units)` clamp ≥0，user 截圖實例驗證 8.25/31.0885/3900.05/49913 → 7.838。v2 編輯介面 wizard 與 T7「編輯持倉」兩處都加 `📋 對帳單格式` radio：A 直接抄欄(10)；B 填配息金額 submit 時換算。Schema 維持 12 欄不動，純 UI 層 input mode toggle。

> 🆕 **v18.154 / 2026-05-20 (PR B.4)** — T7「編輯持倉」表單對齊 v2 schema。`ui/tab3_t7_ledger.py:537` 表單欄位 4→5：砍 `持有單位數` 輸入改 read-only 預覽（`compute_units` 自動算）、加 🟨 `淨投資金額(NT)` 與 🟨 `平均買入含息單位成本(10)`、所有 user input 加 🟨 黃色 icon。Submit 用 `_inv` 直接當 `amount_twd`（不再從 units × nav × fx 反算），同步把 `invest_twd` / `avg_nav_with_div` 寫進 `portfolio_funds[i]` 給 v2 編輯介面共用。

> 🆕 **v18.153 / 2026-05-20 (PR B.3)** — Schema 升 12 欄（加 `avg_nav_with_div` 平均買入含息單位成本，對齊對帳單公式(10)+(11)）。新增 `ZH_HEADERS_V2` 雙向翻譯層：Sheet 上 row 1 寫中文 header（保單編號 / 類型 / 基金代號 / ...），`load_policy_v2` 讀進來 rename 中→英 col name；`is_v2_worksheet` 同時認 `item_type` 與 `類型`。`USER_INPUT_COLS`（7 欄 user 填）vs `AUTO_COLS`（5 欄 MoneyDJ/公式/系統）分類；`_apply_v2_header_format()` 用 `ws.format` API 把 header 列依責任上色（user 黃 / auto 灰）。`compute_units()` 公式自動算：`units = invest_twd / (avg_nav × avg_fx)`（對帳單欄(4) 反推，截圖驗證 1781.025 對齊保險公司 1,781.025375）。Wizard 砍掉 fund_name / currency / units 欄位，存檔時 `_autofill_from_moneydj()` 自動帶；`st.data_editor` 對 auto cols 加 `disabled=True` + 🟨/⬜ icon prefix；Migration 對 v1→v2 預設 `avg_nav_with_div=0`（user 後續到對帳單抄）。

---

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
