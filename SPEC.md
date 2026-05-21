# 基金戰情室 — 系統需求規格書 (SPEC.md)
> **版本**: v10.1 機構級事件防護與組合層級重分配專業版
> **最後更新**: 2026-05-05
> **核心禁令**: 🚫 全面排除 ETF，本系統專注**共同基金**，嚴禁引入任何 ETF 相關模組、折溢價計算或 ETF Ticker 操作。

---

## §0 系統概述與 AI 開發者強制守則

本系統為專注於「國內外**共同基金**」的機構級量化 AI 儀表板。

### ⚠️ AI 開發者強制遵守事項（v10.0 更新）

1. **ETF 絕對禁令**：不得新增任何 ETF 相關程式碼、折溢價計算、ETF Ticker（`0050.TW`, `SPY` 等非基金標的）。發現舊版 ETF 殘留程式碼一律刪除。

2. **新聞情緒強制交叉比對**：每次 AI 分析時，必須將抓取到的重大新聞事件與基金底層持股/債種進行交叉比對，確認是否觸發地緣/事件警報。不得跳過此步驟直接輸出配置建議。

3. **資料更新頻率強制檢查**：動用任何指標前，必須先確認其更新頻率（日/週/月/季），並在 AI Prompt 中標注「落後天數」。月度指標超過 40 天未更新，自動於 Prompt 加入「[STALE: XX 天]」標記。

4. **資料對齊**：台美股休市或頻率落差，全面採用 `df.ffill()`，**嚴禁 `dropna()` 刪除列**。

5. **拒絕黑箱與虛擬資料**：所有 DataFrame 必須連接外部 API 即時產生，禁止硬寫模擬數字。

6. **效能與防封鎖**：所有外部 HTTP 請求必須透過 `fetch_url_with_retry()` 或 `proxy_helper.fetch_url()` 統一入口，加入 User-Agent 偽裝與 NAS Proxy 支援。

7. **自我審核**：每次功能完成後強制輸出 `[邏輯]`、`[邊界]`、`[效能]`、`[Debug]` 四項報告。

8. **σ 策略強制使用絕對位階**：買賣點計算必須採用「HWM - Nσ」絕對位階，禁止用相對百分位取代。

---

## §1 數據來源對照表（v10.0 版）

| 數據類別 | 具體指標 | FRED Series ID / API Endpoint | 抓取套件/函數 | 更新頻率 |
| :--- | :--- | :--- | :--- | :--- |
| **總經領先** | ISM 製造業 PMI | `NAPM` / `ISPMANPMI` | `fredapi` → `_fred()` | 月 |
| **總經領先** | 10Y-2Y 公債利差 | `DGS10` - `DGS2` | `fredapi` → `_fred()` | 日 |
| **總經領先** | 10Y-3M 公債利差 | `DGS10` - `TB3MS` | `fredapi` → `_fred()` | 日 |
| **總經領先** | HY 信用利差 OAS | `BAMLH0A0HYM2` | `fredapi` → `_fred()` | 日 |
| **總經領先** | SLOOS 放貸標準 | `DRTSCILM` | `fredapi` → `_fred()` | 季 |
| **信用壓力** | OAS 即時監控（彌補 SLOOS 落後） | `BAMLH0A0HYM2`（每日更新） | `fredapi` | 日 |
| **總經同步** | 市場廣度 ADL | RSP/SPY 比值 | `yfinance` | 日 |
| **總經同步** | 美元指數 DXY | `DX-Y.NYB` | `yfinance` | 日 |
| **總經同步** | 恐慌指數 VIX | `^VIX` | `yfinance` | 日 |
| **總經同步** | 銅博士 | `HG=F` | `yfinance` | 日 |
| **總經落後** | CPI 通膨年增率 | `CPIAUCSL` | `fredapi` | 月 |
| **總經落後** | 聯準會利率 | `FEDFUNDS` | `fredapi` | 月 |
| **總經落後** | M2 貨幣供給 YoY | `M2SL` | `fredapi` | 月 |
| **總經落後** | PPI 生產者物價 | `PPIACO` | `fredapi` | 月 |
| **總經落後** | 薩姆規則 | `SAHMREALTIME` | `fredapi` | 月 |
| **總經落後** | Fed 資產負債表 YoY | `WALCL` | `fredapi` | 週 |
| **共同基金** | NAV / 配息 / 績效 / 持股 | MoneyDJ wb01/wb05/wb07 | `requests+bs4` → `fetch_url_with_retry()` | 日(NAV)/月(配息) |
| **基金搜尋** | 境外基金代碼查詢 | TDCC openapi / FundClear | `requests` | 即時 |
| **新聞事件** | 財經新聞 RSS | Reuters / Bloomberg / WSJ / Yahoo Finance RSS | `feedparser` → `fetch_market_news()` | 即時 |

---

## §1-A 核心需求一：事件驅動影響分析引擎 (Event-Driven Impact Analysis)

### 架構概述

```
RSS / Google News 抓取
        │
        ▼
 fetch_market_news()  →  近半年重大事件清單
        │
        ▼
 detect_systemic_risk()  →  關鍵字語意掃描
        │
        ▼
 AI 語意映射（ai_engine.py）
        │  比對：新聞事件 × 基金底層持股/債種
        ▼
 event_impact_analysis()  →  衝擊評級 + 強制警報
```

### 實作規格

**1. 新聞抓取（`fetch_market_news()`）**
- 來源：Reuters RSS、Yahoo Finance RSS、Bloomberg（備援）
- 抓取範圍：近 180 天重大事件標題 + 摘要
- 分類標籤：`[geopolitical]` / `[tariff]` / `[rate]` / `[credit]` / `[currency]`

**2. AI 語意映射規則**

| 新聞事件類型 | 比對目標 | 觸發條件 |
|------------|---------|---------|
| 戰爭/地緣衝突 | 高收益債、新興市場債基金 | 持有比例 > 20% 立即觸發 |
| 關稅升高 | 特定供應鏈（科技/製造）相關基金 | 前十大持股含受影響產業 |
| 大選結果 | 醫療/能源/金融類基金 | 政策敏感行業 > 15% |
| Fed 升息加速 | 長天期債券基金（Duration > 7 年） | 自動評估 Duration 風險 |
| 信用評級下調 | 投資等級債/高收益債基金 | 降評標的在持股名單內 |

**3. 強制警報輸出格式**

觸發條件成立時，AI 必須在面板強制輸出：

```
⚠️ 重大地緣/新聞衝擊警報
━━━━━━━━━━━━━━━━━━━━━━━
事件：[新聞標題]（[日期]）
衝擊評級：🔴 致命 / 🟡 重大 / 🟢 輕微
受影響基金：[基金名稱]
受影響持倉：[底層持股/債種]（佔比 X%）
潛在淨值衝擊：預估 -X% ~ -X%（依歷史類似事件回推）
建議行動：[具體操作建議]
━━━━━━━━━━━━━━━━━━━━━━━
```

---

## §1-B 核心需求二：新手/老手兼顧 UI/UX（漸進式揭露）

### 設計原則

每個量化指標必須同時提供：
1. **Tooltip `(?)`**：滑鼠 hover 顯示 30 字以內白話文解釋
2. **白話文解說區**（新手模式）：用天氣比喻，禁用 Z-Score 等術語
3. **量化推演區**（老手模式）：數據背離、乖離分析、σ 絕對位階

### AI 輸出雙軌格式

```markdown
### 🟢 新手行動指引（白話結論）
> 用一句話說清楚：現在應該做什麼、不做什麼。
> 禁用：Z-Score、Alpha、Beta、Duration 等術語。
> 必用：天氣比喻、紅綠燈比喻、家庭理財語境。
例：「目前市場像陰天轉晴，你的基金還在低點，可以考慮小額加碼，但不要全押。」

### 🔴 老手量化推演（數據背離分析）
> Z-Score 目前位於 XX，相較 HWM 下方 Xσ（絕對位階）
> 近 3 個月乖離率：±X%，與大盤相關係數：X.XX
> 信用壓力 OAS：X.XX%（vs 5年均值 X.XX%，Z-Score = +X.XX）
```

### Tooltip 實作規範

- 使用 `st.help()` 或自訂 HTML `title` 屬性
- 每個 Gauge / 指標卡片右上角必須有 `ℹ️` 按鈕
- 點擊展開「為什麼這個指標重要？」說明卡

---

## §2 核心需求三：資料診斷中控台 Data Guard 3.0

### 獨立 Tab（Tab5）檢核表規格

| 欄位 | 說明 |
|------|------|
| 資料名稱 | 指標中文名稱（如：ISM製造業PMI） |
| 抓取狀態 | ✅ 成功 / ❌ 失敗 / ⚠️ 部分 |
| 更新頻率 | 日 / 週 / 月 / 季（依 `_FREQ` 對照表） |
| 最新數據日期 | 實際 API 回傳的最後一筆日期 |
| 過期檢核 | 🟢 正常 / 🟡 延遲 / 🔴 過舊（超過容忍天數） |
| 新鮮度 | 距今天數，自動三色燈號 |

**過期閾值（強制亮黃燈條件）**：

| 頻率 | 🟡 延遲警示 | 🔴 過舊強制標注 |
|------|-----------|--------------|
| 日 | > 3 天 | > 7 天 |
| 週 | > 10 天 | > 21 天 |
| 月 | > **40 天** | > 75 天 |
| 季 | > 95 天 | > 140 天 |

**月度指標超過 40 天**：於 AI Prompt 中強制注入：
```
[STALE: 該指標已 XX 天未更新，存在落後延遲風險，AI 推論結果請保守解讀]
```

### 持倉數據完整度檢核

```
持倉穿透度報告：
  ├─ 前十大持股：已取得 / 未取得
  ├─ 經理費：X.XX% / 未知
  ├─ 保管費：X.XX% / 未知
  ├─ 總費用率 TER：X.XX% / 未知
  └─ 隱形成本預警：若 TER > 1.5% → 🔴「費用吃掉配息」警示
```

---

## §3 核心需求四：轉申購與機會成本模組 (Policy Switch)

### 雙層級設計（v10.1 升級）

| 模式 | 函式 | 適用場景 |
|------|------|---------|
| **單筆 A → B**（保留） | `calc_switch_cost()` | 使用者僅將某一檔 A 換為 B，計算單筆 FX 損益（符合 §6-4 原始規範） |
| **組合層級重分配**（v10.1 新增） | `calc_portfolio_reallocation()` | 投資型保單實務：依「組合當下總淨值」對整個帳戶重新洗牌 |

> 單筆函式為組合函式的子集，UI（Tab3）以 Radio Button 切換兩種模式，達成「漸進式揭露」教育目的。

---

### §3-A 組合基金層級轉換演算法 (Portfolio-Level Reallocation)

**核心精神**：在投資型保單實務中，轉換是基於「組合基金當下的總淨值」進行重新分配，而非單純的 A 標的換 B 標的。

#### 1. 結算現有組合總淨值 (Calculate Current Portfolio Total Value)

系統必須先將保單內現有投資組合（Current Portfolio）的所有標的，依據當下淨值與匯率，折算為台幣總帳戶價值：

```
Total_Value_current = Σ (Units_i × NAV_i(t) × FX_i(t))
                       i=1..n
```

#### 2. 扣除保單隱形成本與摩擦費用 (Deduct Policy Fees & Switching Costs)

在進行轉換打散前，必須從總淨值中預先扣除投資型保單特有的費用（如帳戶管理費、超過免費次數的轉換費）：

```
Net_Switch_Value = Total_Value_current - Policy_Fees - Switching_Costs
```

#### 3. 依新目標權重重新分配 (Allocate to Target Portfolio)

將扣除成本後的純淨值，依據使用者設定的「新組合權重 (Weight_j)」，重新計算各新標的（Target Fund j）所能獲取的單位數：

```
New_Units_j = (Net_Switch_Value × Weight_j) / (NAV_j(t) × FX_j(t))
```

> **實體鎖 A**：`Σ Weight_j` 強制校驗 = 100%。若浮點誤差 ≤ 0.5%，於最後一檔以「殘餘 NTD 反推單位數」吸收尾差；若誤差 > 0.5% 拋 `ValueError`。

#### 4. 組合層級機會成本覆盤 (Portfolio Opportunity Cost Analysis)

AI 戰術大腦評估轉換效益時，必須對比『原投資組合 (Original Portfolio)』與『新投資組合 (New Portfolio)』的整體含息總報酬與組合標準差 (σ_portfolio)。

**強制警告觸發條件**（架構師核准閾值）：
- σ 增幅 > 10% 且 報酬增幅 < 0.5% → 必輸出
  ```
  ⚠️ 組合轉換效益過低警告：扣除保單內扣費用後，總帳戶淨值增長受限
  ```
- 費用佔總淨值 > 1% → 輸出「保單費用已侵蝕近期報酬，建議延後轉換時點」
- FX 曝險上升 > 20pp → 輸出「匯率風險顯著增加」

---

### §3-B 拆解輸出格式（組合層級）

```
組合重分配試算：原組合 → 新組合
━━━━━━━━━━━━━━━━━━━━━━━━
① 現有組合總淨值：       NT$ 2,500,000
② 扣除保單帳戶管理費：   - NT$  3,000
② 扣除超額轉換費：       - NT$  1,500
━━━━━━━━━━━━━━━━━━━━━━━━
③ 可分配淨值：           NT$ 2,495,500

④ 新組合單位數分配（New_Units）：
   FundA (40%)：1,000.0000 units @ NAV 998.20 (FX 1.00)
   FundB (35%)：  291.5400 units @ NAV  29.95 (FX 31.85)
   FundC (25%)：  183.6800 units @ NAV  85.10 (FX  1.00) ← 尾數對齊

⑤ 組合層級覆盤：
   報酬增幅：    +0.32%（< 0.5% 門檻）
   σ 增幅：      +12.40%（> 10% 門檻）
   FX 曝險變化： +24.50pp
━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 組合轉換效益過低警告（強制）
⚠️ FX 曝險上升 +24.50pp，匯率風險顯著增加
```

---

### §3-C 實作函式（`portfolio_engine.py`）

```python
def calc_switch_cost(                          # 保留（單筆 A→B，§6-4 規範）
    redeem_amount: float,
    fee_a_pct: float = 0.0,
    fee_b_pct: float = 3.0,
    fx_spread_pct: float = 0.1,
    same_currency: bool = True,
) -> dict:
    """單筆 A→B 轉換成本拆解（FX 損益單獨列出）"""

def calc_portfolio_reallocation(               # v10.1 新增（組合層級）
    current_portfolio: list[dict],   # [{code, units, nav, fx, currency}, ...]
    target_weights:    dict,         # {code: weight_pct}（總和 = 100，誤差 ≤ 0.5% 自動對齊）
    target_navs:       dict,         # {code: {nav, fx, currency}}
    policy_fees:       float = 0.0,  # 保單帳戶管理費（NTD）
    switching_costs:   float = 0.0,  # 超額轉換費（NTD）
    orig_return_pct:   float = None, # 原組合預期報酬（覆盤對比）
    new_return_pct:    float = None,
    orig_sigma:        float = None,
    new_sigma:         float = None,
) -> dict:
    """
    回傳 {
      total_value_current, net_switch_value, deductions{},
      new_units{}, weight_check{},
      portfolio_diff{return_diff_pct, sigma_diff_pct, fx_exposure_change},
      warnings[]
    }
    """
```

> **實體鎖 B**：所有 NAV / FX 必須由呼叫端從既有 `df_nav` 快照提取，禁止在 `portfolio_engine.py` 內引入任何虛擬淨值。

---

### §3-D 保單基金配息現金/單位拆分（v18.160 新增）

**規格背景**：保險公司 APP 允許 user 為每檔保單基金設定配息「現金給付% / 增加單位數%」（例：USDEQ5110 設 80% 現金 + 20% 新增單位）。Dashboard 須對應紀錄該設定並估算年化現金流。

**Schema 規格**：v2 schema 第 13 欄 `div_cash_pct`（中文 header「現金給付%」）。
- 型別：`float`，值域 `[0, 100]`，預設 `100`（全現金給付，符合多數保單預設行為）
- 單位數% = `100 - div_cash_pct`（derived，不存）
- `repositories.policy_repository._normalize_div_cash_pct`：缺值/空字串/garbage → 100；超界 clip；容錯帶 `%` 符號
- **向後相容**：舊 12 欄 Sheet 載入時自動補欄、補預設 100；`is_v2_worksheet` 偵測不變

**估算公式**（`policy_repository.estimate_dividend_split`）：
```
annual_div_twd  = invest_twd × annual_div_rate_pct / 100
cash_twd        = annual_div_twd × div_cash_pct / 100
reinvest_twd    = annual_div_twd − cash_twd
new_units       = reinvest_twd / (avg_nav × avg_fx)    # denom ≤ 0 → 0
```

**UI 規格**（`ui/helpers/v2_editor.py`）：
- data_editor 新增 NumberColumn「🟨 現金給付 %」(min 0 / max 100 / step 10 / format `%d`)
- 下方 caption「💡 配息拆分均值：現金 X% / 新增單位 Y%」即時顯示
- expander「📊 配息估算」：user 填年配息率假設 (預設 5%) → 表格列每檔基金的 `現金% / 單位% / 年配息(TWD) / 年現金(TWD) / 年再投入(TWD) / 年新增單位數` + 3 個彙總 metric

**AI 整合**：Tab3 末「🤖 AI 白話文總結」snapshot 從 `_v2_buf` × `portfolio_funds.metrics.annual_div_rate` 算估算，加入「📊 年配息現金/單位拆分估算」段（總彙總 + 每檔細節）。

---

### §3-E Tab3 IO toolbar 互動式快捷面板（v18.161 新增 / v18.162 雲端動作改真執行）

**問題演進**：
- v18.159 4 顆按鈕做成 toast 跳轉提示，user 仍要狂滑
- v18.161 升級為 toggle + 雲端「狀態 + 請往下捲」提示牌；user 截圖反饋仍「不太順」
- **v18.162 終態**：4 顆按鈕全部**真執行**，雲端讀寫一鍵到位

**設計**：

| 按鈕 | 面板顯示 | 動作 | 真執行？ |
|------|---------|------|---------|
| 📥 雲端讀取 | `📂 帳本：sheet name ｜ 本地持倉：N 檔 ｜ 上次讀回：時間` | 「📥 立即全部讀回」按鈕 → `load_all_from_sheet` | 是（v18.162） |
| 📦 雲端存檔 | `📂 帳本：sheet name ｜ 待寫入持倉：N 檔 ｜ 上次寫入：時間` | 「📦 立即全部寫入」按鈕 → `dump_all_to_sheet`（無持倉時 disabled） | 是（v18.162） |
| 💾 下載 JSON | `含 N 檔 + M ledger + K 方案` | `download_button` 即時序列化 | 是（v18.161） |
| 📂 上傳 JSON | 檔案上傳區 | `restore_from_json_bytes` 即時還原 | 是（v18.161） |

**未登入/無 sheet_id 時** 雲端 panel 顯示友善 warning：「⚠️ 尚未登入 Google 或未指定 Sheet ID。請先在下方『📂 從 Drive 列出 Sheets』挑一本」。

**helper 抽離（雙 helper 上下方共用）**：

```python
# ui/helpers/cloud_io.py（v18.162 新增）
dump_all_to_sheet(client, sheet_id, ss) -> dict
# {ok, written, skipped_no_pid, n_state, warnings, error}

load_all_from_sheet(client, sheet_id, ss, *, oauth_mode, refresh_only=False) -> dict
# {ok, refresh_only, added, kept, removed, restored_ct, warnings, error}

# ui/helpers/json_backup.py（v18.161 新增）
build_export_payload(ss) -> dict
restore_from_json_bytes(raw, ss) -> {ok, n_funds, n_ledgers, error}
```

**設計原則**：
- helper **streamlit-agnostic** ── warning / error 透過 return dict 帶出，由 caller 顯示
- 致命錯誤（`error`）vs 非致命警告（`warnings`）分離 ── 例：`_T7_State` 寫入 quota error 走 warnings 不擋主流程
- sheet name 快取 `session_state["_t3_cur_sheet_title"]` ── 避免每次 panel rerun 都打 `get_sheet_title` API

**timestamp 紀錄**：上下方雙入口寫入成功後皆寫 `t3_last_save_at` / `t3_last_load_at`（`%Y-%m-%d %H:%M`），供上方快捷面板顯示。

**下方 L863+「🧰 一鍵存讀」段瘦身**：呼叫同一 helper，移除 ~120 行重複邏輯，作雙入口備援 + 提供「只刷新分頁清單」與快取管理。

---

---

### §3-F Tab3 組合健康儀表 hero + sub-tab segmented_control（v18.163 新增）

**問題場景**：user 截圖反饋「上面資料跟下方有差異 是否保留一個 另外有很多重複資料 很占版面」。Tab3 內：
- 上方 `mk_war_room` 4 卡 KPI（撿便宜 / 留校 / 停利 / 配置比）
- 下方真實收益矩陣 4 卡 KPI（基金數 / 現金流健康 / 吃本金 / 資料不足）
- 三個 sub-tab（核心戰情室 / 波段觀測站 / 3-3-3 篩選器）視覺上像「同一份基金清單顯示三次」

**設計**：合併兩段 KPI 成 Tab3 頂部 hero 6 卡 + sub-tab 改用按鈕組切換。

**6 卡 hero KPI**（`ui/helpers/portfolio_health.py:render_hero_kpi_cards`）：

| 卡片 | 顯示 | 來源 |
|------|------|------|
| 📊 組合基金數 | `N 檔` | `portfolio_funds` 去重後 |
| ⚖️ 配置比例 | `核心 X% / 衛星 Y%` + delta vs 80/20 | `mk_df.MK_Class` |
| 💵 現金流安全 | `健康/(健康+吃本金) 檔` + delta `-N 吃本金` inverse + tooltip `N 檔資料不足` | `compute_1y_total_return` |
| 🟢 撿便宜雷達 | `N 檔` | `mk_df.Price_Zone == Buy_Zone*` |
| 🔴 留校查看 | `N 檔` + delta inverse | `mk_df.Health_Check + Core 吃本金` |
| 💰 停利提醒 | `N 檔` | `mk_df.Price_Zone == Take_Profit & Satellite` |

**KPI helper 介面**：

```python
# ui/helpers/portfolio_health.py
compute_health_kpis(portfolio_funds, mk_df=None) -> dict
# 12 個 field：n_classed / pct_core / pct_sat / ratio_label / ratio_delta /
#             n_buy / n_warn / n_take / n_funds / n_cash_ok / n_eat / n_na
# 去重 by code（同 code 跨多保單只算一次），mk_df=None 時 MK 維度回 0

render_hero_kpi_cards(kpis) -> None
# 渲染 6 卡（2 排 × 3 卡）；kpis["n_funds"]=0 時顯示提示「待載入基金」
```

**sub-tab 改 segmented_control**（`ui/components/mk_dashboard.py:732+`）：

```python
_view_options = [
    f"🛡️ 核心戰情室（{n_core} 檔）",
    f"⚡ 波段觀測站（{n_sat} 檔）",
    f"🔍 3-3-3 篩選器（{n_total} 檔池）",
]
_view_pick = st.segmented_control("選擇分析視角", _view_options,
                                    default=_view_options[0],
                                    key="mk_view_pick")
# 內容渲染邏輯一字不動，只換切換器
```

**為何不用 expander 收合配息矩陣**：圖表本體（紅虛線 vs 長條高度視覺化每檔吃本金）有獨立資訊量，下方 4 卡 KPI 才是真重複；圖表保留、4 卡 KPI 砍掉即解決 user 痛點。

**T5 重疊矩陣不動**：原本就是 per-policy `st.expander(expanded=False)` 收合（`tab3_portfolio.py:2195`），無重複問題。

---

### §3-H 快捷面板加第 5 顆「✨ 新增帳本」button（v18.165 新增）

**問題場景**：v18.164 把「✨ 新增帳本」做成 expander 內小標題，但功能（自動建立 + Drive 挑）仍埋在下方需要捲動。user 截圖紅框 + 紅箭頭明確要求：頂部「🚀 快速存讀面板」加第 5 顆 button，點下去直接顯示互動面板（與其他 4 顆 toggle 行為一致）。

**設計**：

```python
# tab3_portfolio.py:212
_io_c1, _io_c2, _io_c3, _io_c4, _io_c5 = st.columns(5)
# 順序：📥 雲端讀取 / 📦 雲端存檔 / ✨ 新增帳本 / 💾 下載 JSON / 📂 上傳 JSON

# tab3_portfolio.py:340  新增第 5 個 elif
elif _io_panel == "new":
    st.markdown("**✨ 新增帳本（建立新 Sheet 或從 Drive 挑一本）**")
    if not _oauth_configured: <警告>
    elif not _logged_in_q:    <警告>
    else:
        # 上半：自動建立 Sheet（無條件顯示，user 已點 button）
        [新 Sheet 名稱] [🚀 自動建立 Sheet]
        ---
        # 下半：從 Drive 挑
        [🔄 載入資料夾清單]
        [📁 限定資料夾 下拉]
        [📂 從 Drive 列出 Sheets]
        [清單下拉] [✅ 使用此 Sheet]
```

**關鍵點**：
- v18.164 hoist 到 expander 的「✨ 新增帳本」段已整段移除（L630-770），只留 `_sheet_id = session_state.get(...)` 一行，避免 widget key 衝突
- 6 個 widget key（`btn_auto_create_sheet` / `btn_load_drive_folders` / `sel_drive_folder` / `btn_list_drive_sheets` / `sel_my_sheets` / `btn_pick_my_sheet`）唯一存在於 quick panel `elif new` 分支
- 自動建立成功 / Drive 挑選成功 → `del session_state["inp_sheet_id"]` + `pop("_t3_cur_sheet_title")` 讓 rerun 從 `policy_sheet_id` 重新初始化 sidebar 顯示

---

### §3-G Sheet ID 輸入 hoist sidebar +「✨ 新增帳本」面板（v18.164 新增）

**問題場景**：user 截圖紅框反饋 — Tab3「📋 保單管理」expander 內，OAuth 登入狀態 + Sheet ID 輸入欄位並列在快捷面板下方占大半版面；底下「🆕 自動建立 Sheet」與「📂 從 Drive 挑」中間夾「**或者**」字眼、層次斷裂、且 Drive 挑那段被埋得很深要往下捲。

**設計**：把 Sheet ID 輸入搬到 sidebar 與「🔐 Google 帳號」並列；Tab3 expander 內把兩個「取得 / 切換 Sheet」入口合併為一個「✨ 新增帳本」互動式面板（上下並列）。

**Sidebar 工作中帳本**（`app.py:280+`）：

```python
if _logged_in_sb or (_gsa_secret and _sheet_id_secret):
    st.markdown("##### 📋 工作中帳本")
    _sid_raw_sb = st.text_input("Sheet ID 或完整 URL", value=_sid_default_sb,
                                  key="inp_sheet_id")
    _m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", _sid_raw_sb)
    _sid_sb = _m.group(1) if _m else _sid_raw_sb
    if _sid_sb != _sid_default_sb:
        st.session_state["policy_sheet_id"] = _sid_sb
    # 顯示當前帳本標題（_t3_cur_sheet_title:<sid> 快取，避免重複 API call）
```

**Tab3「✨ 新增帳本」面板**（`ui/tab3_portfolio.py:485-544`）：

```
##### ✨ 新增帳本
(if not _sheet_id)
  💡 還沒有 Google Sheet？讓 app 幫你建一個
  [新 Sheet 名稱]  [🚀 自動建立 Sheet]
  ---
📂 從你 Google Drive 內既有的 Sheets 挑一個（可選擇限定資料夾）：
  [🔄 載入資料夾清單]
  [📁 限定資料夾 下拉]
  [📂 從 Drive 列出 Sheets]
  [清單下拉] [✅ 使用此 Sheet 作為投組資料庫]
```

**關鍵設計理由**：
- Sheet ID 屬於「全 app 共用設定」（Tab2 也讀），放 sidebar 合理且永久可見
- 「自動建立」與「Drive 挑」對等並列，移除「或者」措辭表達兩個對等選項
- `not _sheet_id` 條件仍套用在自動建立區（已有帳本時不顯示，避免噪音 / 引導使用者用下方多帳本管理建立另一本）
- 兩者同時顯示時才插入 `---` 分隔，視覺一致

---

## §4 核心需求五：機構級風險歸因與 σ 絕對位階策略

### 4-1 底層持股相關性矩陣

- 計算組合內各基金「前十大持股」重疊度
- 相關性矩陣：Pearson Correlation（近 1 年 NAV 日報酬率）
- **影子基金/集中度警告**觸發條件：
  - 任兩基金相關係數 > 0.85 → 🔴「資產高度同質，無法有效分散」
  - 組合前十大持股重疊度 > 40% → 🔴「影子基金警告，實際曝險等同單一持倉」

### 4-2 即時信用壓力監控（彌補 SLOOS 季度落後）

- 指標：OAS 高收益債利差（`BAMLH0A0HYM2`，日頻）
- 計算 Z-Score（5 年滾動均值/標準差）
- 警戒規則：
  - OAS Z-Score > +2σ → 🔴「信用壓力極端，高收益債/新興市場債風險急升」
  - OAS Z-Score > +1σ → 🟡「信用壓力升溫，降低高收益債配置」
  - OAS 週增幅 > 50bps → 🔴「信用市場急速惡化，強制建議移至投等債」

### 4-3 σ 絕對位階買賣策略

**定義**：以歷史最高淨值（HWM）為基準，用標準差（σ）衡量絕對跌幅位置。

| 位階 | 公式 | 意義 | 操作建議 |
|------|------|------|---------|
| HWM | 歷史最高淨值 | 頂部基準 | 停利區 |
| HWM - 1σ | `HWM × (1 - std_1y)` | 輕微回檔 | 觀察，少量加碼 |
| HWM - 2σ | `HWM × (1 - 2×std_1y)` | **大買區** | 主力加碼（凱利 50%） |
| HWM - 3σ | `HWM × (1 - 3×std_1y)` | 超跌區 | 分批承接，停損設 HWM-3.5σ |

**強制輸出格式**（每次基金分析必含）：

```
σ 絕對位階報告：[基金名稱]
  HWM（歷史最高）：XXX
  當前 NAV：XXX（在 HWM - X.Xσ 位置）
  大買區（-2σ）：XXX ← 目前距大買區 X.X%
  超跌區（-3σ）：XXX
  停利點（+1σ）：XXX
```

---

## §5 Tab 架構總覽（v10.0）

| Tab | 名稱 | 核心功能 | v10.0 新增 |
|-----|------|---------|-----------|
| Tab1 | 🌐 總經儀表板 | 14 指標 + 景氣位階 + 美林時鐘 | 事件驅動警報卡、OAS 即時信用壓力 |
| Tab2 | 🔍 單一基金深度診斷 | NAV/配息/風險/持股 | σ 絕對位階卡、新手/老手雙軌輸出、影響事件標注 |
| Tab3 | 📊 組合基金 | 六因子評分、再平衡 | 持股相關性矩陣、影子基金警告、轉申購試算 |
| Tab4 | 🔬 回測 | CAGR/Sharpe/MDD | — |
| Tab5 | 🛡️ 資料診斷中控台 | Data Guard 3.0 | 持倉完整度、更新頻率檢核、STALE 標記 |
| Tab6 | 📖 說明書 | 靜態說明 | 新增轉申購公式說明 |

---

## §6 AI 引擎規格（v10.0）

### 模型
- **Gemini 2.5 Flash**（保留 thinking 選項）
- Endpoint：`https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent`

### 輸入快照架構（< 1000 tokens）

```
[總經位階] score / phase / rec_prob / OAS_z_score
[事件警報] 近期重大新聞（最多 5 則）+ 衝擊評級
[STALE 標記] 過期指標清單（如：PMI [STALE: 42天]）
[投資組合] 基金 | NAV位階 | σ位置 | 持股重疊 | TER
[個別基金] NAV / σ絕對位階 / 吃本金check / 事件曝險
[風險預警] 🔴 紅色警示（影子基金/信用壓力/事件衝擊）
```

### 強制輸出格式（v10.0 六大章節）

```markdown
### ⚠️ 零、事件衝擊警報（若無觸發則省略）

### 📍 一、景氣位階判讀
（3 個關鍵指標 + OAS 信用壓力 + 拐點觸發條件）

### ⚖️ 二、資產配置建議
（現況 vs 目標比例 + 調整幅度）

### 🔴 三、持倉警示
（逐基金：σ絕對位階 + 影子基金 + 吃本金）

### 🎓 四、新手行動指引
（白話結論，禁用 Z-Score/Alpha/Beta 術語）

### 📐 五、老手量化推演
（Z-Score 背離、σ位階、OAS 乖離、Duration風險）

### 🔄 六、本週操作待辦清單
- [ ] 具體操作項目
```

---

## §7 設計約束（v10.0 強化版）

| 類型 | 規則 |
|------|------|
| 🚫 **絕對禁止** | ETF 模組、虛擬測試數值、硬寫模擬股價 |
| 🚫 **絕對禁止** | 跳過新聞交叉比對直接輸出 AI 建議 |
| 🚫 **絕對禁止** | 月度指標超過 40 天未標注 STALE |
| ✅ **強制要求** | σ 絕對位階（HWM 基準）用於所有買賣點 |
| ✅ **強制要求** | 轉申購必須拆解 FX 損益與隱形成本 |
| ✅ **強制要求** | 任兩基金相關係數 > 0.85 → 影子基金警告 |
| ✅ **強制要求** | 新手白話 + 老手量化雙軌 AI 輸出 |
| 📊 **圖表庫** | Plotly（禁止引入 matplotlib/seaborn 等新依賴） |
| 🔒 **邊界防呆** | < 20 筆 → DataValidationError；API null → 警告不崩潰 |

---

## §7 v15.1 介面友善化規範（新手導引）

### 7-1 設計原則：圖像化 + 解說（非省略資訊）

> 核心：傳統儀表板呈現所有數據導致「決策疲勞」；v15.1 改用「總覽 → 細節」漸進式揭露，**所有資訊保留**，但加入圖像化視覺與白話解說補強。

| 原則 | 落實 | 程式碼位置 |
|------|------|-----------|
| L1 總覽級 KPI | 4 顆字卡：💰總資產 / 📈累計報酬 / 🛡️核心% / 💵月配息 | `app.py` Tab3 開頭 |
| L2 趨勢級圖表 | 平滑資產曲線（spline），對比 2% 無風險基準（§0 禁 ETF） | `app.py` Tab3 KPI 下方 |
| L3 細節級 | 既有 T4/T5、六因子、相關矩陣等不變 | Tab3 中段 |
| 白話解說 | 每張關鍵圖表下方 `st.caption("💡 怎麼看 ...")` | Tab1 宏觀圖、Tab3 T5、資產曲線 |
| 友善錯誤 | `_friendly_error(title, exc, hint=, level=)` 統一 helper | `app.py` 頂部 |
| 空狀態引導 | Tab3 無基金時顯示「👋 新手三步驟」卡 | Tab3 開頭 |

### 7-2 強制規範

- **AI 觸發必須由按鈕觸發**：所有 Gemini 呼叫必須在 `if st.button(...)` 區塊內，禁止頁面渲染時自動執行（避免使用者未授權即消耗 API 配額）
- **基準線禁用 ETF**：資產曲線對比基準必須使用「無風險利率年化複利」，不得引入 0050.TW / SPY / QQQ 等 ETF（§0 全面排除）
- **錯誤訊息白話化**：禁止裸露 `st.error(f"... {e}")`，必須使用 `_friendly_error()` helper 將 traceback 收進可展開區塊
- **Caption 字數限制**：每張圖的「💡 怎麼看」說明限 80 字內，避免再次造成資訊過載

### 7-3 _friendly_error helper 簽名

```python
def _friendly_error(title: str, exc: Exception, *, hint: str = "", level: str = "warning"):
    """
    title : 白話標題（例：「基金 NAV 載入失敗」）
    exc   : 捕捉到的 Exception
    hint  : 給使用者的建議（例：「請確認基金代碼是否正確」）
    level : "warning" | "error" | "info"
    輸出  : st.{level}(title + hint) + st.expander("🔧 技術細節（給工程師）") with st.code(traceback)
    """
```
