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

### §3-Z 「存檔無含息來源」§5 除錯協議（v18.189 新增）

**症狀①**（user 確認）：Google Sheet 保單分頁存完沒有「含息成本」欄。

**完整追蹤（不盲改）**：user 走 per-policy 分頁路徑（tab 名 = policy_id，如 QL19676552）。寫：`upsert_fund_in_policy` 偵測表頭缺 ALL_COLS 任一欄 → `ws.update("A1:K1", [list(ALL_COLS)])` 升級成 11 欄、`_row_to_list(row, ALL_COLS)` 依序輸出 11 值（`avg_nav_with_div` = K 欄）。讀：`load_policy_worksheet` reindex ALL_COLS、`sync_policies_to_portfolio_funds` 有值才帶。**全鏈正確**；legacy 單表 `upsert_policy_row` 才不強制升表頭（非 user 路徑）。此症狀已修 3 次（v18.180/183/184）。

**依 §5「同錯 2 次即停機」→ 改做除錯協議（instrument，不盲改邏輯）**：
1. `dump_all_to_sheet` 原 `except (PolicySheetError, OAuthError): continue` **靜默吞**掉 per-fund 寫入失敗 → 改成收集 `(pid/code + 原因)` 進 `out["warnings"]`。下次「📦 全部寫入」若真有寫失敗（配額 429 / 權限 / 表頭升級失敗），畫面直接顯示根因，而非默默漏欄。
2. **釐清關鍵盲點**：v1 保單分頁的表頭是**英文 key**（`avg_nav_with_div`、`div_cash_pct`），不是中文「平均買入含息單位成本」（中文欄名只存在於 v2 schema 的 `ZH_HEADERS_V2`）。user 若在 Sheet 找中文欄名，會誤判「沒有這欄位」。

**待 user 驗證（§5 雙重確認）**：① 在保單分頁找**英文** `avg_nav_with_div`（K 欄）；② 確認部署的 Streamlit app 已更新到含 v18.183 的 main（必要時 reboot）；③ 重按「全部寫入」看是否冒出新的 ⚠️ 寫入失敗提示。

**驗證**：AST PASS、ruff clean、新增 1 test、`test_cloud_io` 13 PASSED 零回歸。

---

### §3-Y 移除「多帳本管理」區塊，改用存取/讀取管理多帳本（v18.188 新增）

**決策**（user）：「取消多帳本管理，帳本管理改用存取、讀取的方式，就不用切換」。經歷切換帳本的 stale bug（v18.185 auto-load、v18.187 t7_ledgers 清空）後，user 決定不要獨立的「切換到此帳本」流程，改以「挑一本 Sheet → 讀回」的存取模式管理多帳本。

**移除**：`ui/tab3_portfolio.py` 內整個「📁 多帳本管理（不同人/帳戶各自一本）」區塊（建立另一本 / 改名目前帳本 / 切換到別本三個 tab，共 123 行）+ 只此處用到的 `rename_sheet` import。

**替代路徑**（皆既有，零新功能）：
- 切換帳本 → 「📥 雲端讀取」面板的「📂 從 Drive 挑帳本」挑一本 → 自動讀回（v18.185 auto-load 觸發）。
- 建立新帳本 → 頂部快捷面板「✨ 新增帳本」。
- 改名 → 直接在 Google Drive 操作。

**保留**：v18.185（挑帳本後自動讀回 + 同 code 共用基金資訊）、v18.187（t7_ledgers 空→清、清 auto-restore 旗標）對「挑帳本」路徑同樣生效，因為它們是綁在 `policy_sheet_id` 變動、而非綁在已移除的切換按鈕。

**驗證**：AST PASS；ruff F821 無未定義名、無殘留變數、`rename_sheet` import 清除；`test_app_smoke + test_tab3_portfolio` 99 PASSED 零回歸；無 test 引用被移除的 widget key。

---

### §3-X 修「切換帳本後帳本無法更新」+ 含息來源 §5 anti-loop（v18.187 新增）

**問題場景**（user）：①「存檔無含息來源」；②「切換帳本後，帳本那些都無法更新」。

**#2 根因**：`load_all_from_sheet`（`ui/helpers/cloud_io.py`）原本只在新帳本的 `_T7_State` 快照非空時才覆蓋 `t7_ledgers`。切換到「沒有 `_T7_State`」的帳本時 `t7_ledgers` 殘留**前一本**——持倉（portfolio_funds）已換、T7 帳本面板卻顯示舊本。v18.185 把切換改成自動讀回後，此 stale 每次切換都暴露。

**#2 修法**：
- `ss["t7_ledgers"] = _restored or {}`：新本無快照時清空（不殘留舊本）。
- `_t7_auto_restore_done` / `_t7_auto_estimate_done` 旗標**一律**清（移出 `if _restored`）→ 新本無快照時 T7 區塊（`tab3_t7_ledger.py:200`）對新本重跑 auto-restore，t7_ledgers 維持空（正確）。
- `_sync_invest_twd_from_ledgers()` 仍只在有快照時呼叫（避免空帳本把 invest_twd 歸零）。

**#1 含息來源（§5 anti-loop）**：完整追蹤寫+讀 round-trip（T7 表單→portfolio_funds 參照 + cost_unit_with_div + 保單分頁；`dump_all_to_sheet` / `upsert_fund_in_policy`（ALL_COLS 含欄 + 表頭自動升級）/ `load_policy_worksheet`（reindex ALL_COLS）/ `sync`（有值才帶））**全部正確**。此症狀已在 v18.180/183/184 修過 3 次仍被回報 → 依 CLAUDE.md §5「同錯 2 次即停機」**不再盲改**，待 user 給精確重現步驟（哪個存檔鈕、看哪裡為空：Google Sheet 欄位 / T7 顯示 / JSON）。v18.187 的 staleness 修復可能順帶修好「切換後含息成本顯示舊本」。

**驗證**：AST PASS、ruff clean、新增 2 regression test、119 PASSED 零回歸。

---

### §3-W 連線健檢 #1：RSS 新聞走 NAS Proxy + 友善空狀態（v18.186 新增）

**背景**（v5.0 Task1）：Streamlit Cloud 易被來源 IP 封鎖，所有外部抓取需走 NAS Proxy 並具 timeout / try-except / 友善降級。

**稽核**：互動元件（button/selectbox/slider）逐一驗證皆 LIVE，無幽靈按鍵；`tab5 _snap_sel`（`tab5_data_guard.py:301`）為誤報——實際有消費（算 head5 表）且已有空狀態提示。

**唯一缺口**：`repositories/news_repository.py` 的 RSS 抓取（`feedparser.parse(url)`）沒走 proxy、無 timeout、`except: pass` 靜默——是 fund_fetcher / fund_repository（全局 urllib opener）/ macro_repository 之外最後一條裸連路徑，正中使用者擔心的 Cloud IP 封鎖風險。

**修法**：
- RSS 改用 `infra.proxy.fetch_url(url, timeout=12, retries=2)` 抓 bytes，再 `feedparser.parse(bytes)`（fetch_url 內含 407 立即停 / 403×2 降級直連 / ProxyError 降級）。無 `infra.proxy` 時退回 feedparser 直連（向後相容）。
- 失敗來源累計 `failed`，不再靜默 pass。
- 結果為空回友善提示：有失敗 → 「⚠️ 暫時無法取得財經新聞（可能 Proxy 斷）」；無失敗但無命中 → 「ℹ️ 目前沒有符合追蹤條件的財經新聞」。

**未動**：`fetch_market_news(max_per_feed)` 簽名不變（callers Tab1/2/3 + data_registry 零修改）；`fetch_macro_news(asset_class)` 分類接口留待 Task3 AI 解盤補完。

**驗證**：AST PASS、ruff clean、新增 4 test（全失敗 / 無命中 / systemic 排前 / 確有走 fetch_url）、109 PASSED 零回歸。

---

### §3-V 切換帳本自動讀回 + 跨帳本共用基金資訊（v18.185 新增）

**問題場景**（user）：①切換帳本（多帳本管理「🔁 切換到此帳本」）後「沒有載入鍵與計算」——持倉與分析都不更新，要自己滾回頂部按「📥 雲端讀取」；②同一檔基金在不同帳本（不同人/保單）會被當成全新標的，重抓 MoneyDJ（每檔約 30 秒）。

**根因**：
- 切換按鈕（`tab3_portfolio.py:757`）只 `st.session_state["policy_sheet_id"]=新id` + `st.rerun()`，沒有任何自動讀回；既有讀回是手動按鈕（`load_all_from_sheet`）。
- `sync_policies_to_portfolio_funds` 的 dedupe 鍵是 `(policy_id, fund_code)` 複合鍵。換帳本時 policy_id 幾乎都不同 → 同一檔 `fund_code` 落在「added / loaded=False」骨架 → 被當新標的重抓。但基金的 NAV 歷史與指標**只跟 `fund_code` 有關、與保單無關**，可跨帳本共用。

**設計決策**（user 確認）：①切換後**自動讀回**（零按鈕）；②真正不同的新標的**用既有「📡 載入未載入基金」按鈕**抓（不在切換時卡 30s×N）。

**實作**：
- **共用基金資訊（依 code）**：新增純函式 `ui/helpers/portfolio_load.py:reuse_fund_info_by_code(merged, previous_funds)`。從上一本帳本已 `loaded=True`（且無 `load_error`）的條目建 `code → fund-info` 表，把 merged 內未載入、同 code 的條目補回 fund-info 欄（`name/series/dividends/metrics/moneydj_raw/risk_metrics/is_core/currency`，set `loaded=True`），**空值不覆蓋**（保住保單帶來的 currency）。持倉（policy_id/units/invest_twd/級別）仍走新帳本。`load_all_from_sheet`（`ui/helpers/cloud_io.py`）在 sync 後呼叫它、report 新增 `reused`（被沿用的 code 清單）。
- **自動讀回**：`render_portfolio_tab` 早段（cloud client closure 之後）以 `st.session_state["_last_loaded_sheet_id"]` 追蹤。當 sheet id 改變且雲端可達 → 自動跑一次 `load_all_from_sheet`（持倉切換 + 基金資訊沿用、**零 MoneyDJ 呼叫**）並 `st.toast` 報告「持倉 N 檔／沿用 M 檔免重抓／K 檔新標的待載入」。
- **新標的**：真正不同的 code 仍 `loaded=False`，由既有「📡 載入未載入基金（N 檔）」一鍵抓（v18.151 helper）。

**防呆**：本次 session「第一次進入」（`_last_loaded_sheet_id` 還是 None）**且已有本地持倉**（如剛還原 JSON）→ 只記下 sheet id、**不自動讀回**，避免 sync 把本地狀態洗掉；只有真正切換 id 才自動讀回。自動讀回失敗也會記下 id（不重試迴圈），user 可手動再按「📥 雲端讀取」。

**驗證**：AST PASS；ruff clean；新增 6 個 `reuse_fund_info_by_code` 單元測試；212 PASSED 零回歸。

---

### §3-U T7 持倉明細表加「含息成本 + 累積已配息率」欄（v18.184 新增）

**問題場景**（user）：①「含息來源沒在存檔（Google Sheet / JSON）」；②「之前說含息來源有資料就能算含息率，但分析資料沒看到」。

**釐清**：
- 「含息來源」是表單上的 **A/B 輸入方式**（A 直接抄對帳單欄(10) 含息成本 / B 用累積配息反推），它本身不持久化（user 同意不存）；真正持久化的是**結果含息成本** `avg_nav_with_div`（JSON v18.180 / 保單分頁 v18.183 / ledger `cost_unit_with_div` v18.180 皆已存）。
- 真正的 gap：`cost_unit_with_div` 一直被收集 + 存檔，但**從沒在任何顯示分析中使用**（dangling input）。app 內唯一的「含息報酬率」來自 MoneyDJ 基金層市場資料（tab6 手冊 / tab5），與 user 對帳單含息成本無關。

**Fix（user 選「累積已配息率」、不需即時 NAV）**：T7 持倉明細表（`tab3_t7_ledger.py` `_snap_rows`）新增兩欄：
- **含息成本** = `position.cost_unit_with_div`（含息成本 < 淨值成本時顯示，否則「—」）。
- **累積已配息率** = (平均買入淨值 − 含息成本) / 平均買入淨值 × 100%，代表成本已透過配息回收幾%（例 ACTI71 = (8.67−6.9655)/8.67 = 19.66%）。純成本面、不依賴即時 NAV；未填含息成本（`cuwd >= cu0`）顯「—」。併入紅綠著色 subset；units≤0 分支同步補欄保持 DataFrame 對齊。

純顯示層改動，`test_app_smoke + test_fund_ledger + test_tab3_portfolio` 共 128 PASSED 零回歸。

---

### §3-T div_cash_pct/avg_nav_with_div 加進 v1 保單分頁 schema（v18.183 新增）

**問題場景**（user）：「div_cash_pct 存檔不在 google sheet」。前情：v18.180 已把 `div_cash_pct`/`avg_nav_with_div` 補進 JSON 備份、v18.182 補進 `_持倉總覽` 顯示分頁，但 **v1 保單分頁本身（user 實際讀寫、`全部讀回` 的來源）沒有這兩欄**。

**根因**：v1 `ALL_COLS = REQUIRED_COLS + (policy_tier,)` 無 `div_cash_pct`/`avg_nav_with_div` → upsert 從不寫、`sync_policies_to_portfolio_funds` 讀回也沒有 → 重整 / 全部讀回後歸零（只 JSON 留得住）。v2 schema（`ALL_COLS_V2`）早有這兩欄，但 user 走 v1 + T7 流程。

**Fix（user 選「兩欄都加」）**：
1. `OPTIONAL_COLS` 尾端追加 `div_cash_pct` + `avg_nav_with_div`（純追加，既有欄位位置不變；`ALL_COLS` 9 → 11 欄）。
2. **寫**：`upsert_fund_in_policy`（per-policy 分頁、user 路徑）寫入前若表頭缺 `ALL_COLS` 任一欄 → `ws.update("A1:K1", [ALL_COLS])` 升級表頭（既有資料列尾端補空、不錯位），cols 固定 `ALL_COLS`；寫入端（`tab3_t7_ledger.py` v18.179 全量回寫區塊 + `cloud_io.dump_all_to_sheet`）的 row dict 帶上這兩欄。`upsert_policy_row`（legacy 單一 `Policies` 表）改成 `cols = tuple(c for c in ALL_COLS if c in header) or REQUIRED_COLS`（只寫表頭實際有的欄、避免孤兒欄）、不強制升級（向後相容）。
3. **讀回**：`sync_policies_to_portfolio_funds` 把兩欄讀進 `portfolio_funds`（`_normalize_float`；**有值才帶**，空欄/舊表不覆蓋記憶體既有設定）→ 全部讀回後現金給付%/含息成本不再歸零，真正在 Sheet round-trip。

**驗證**：改 1 舊 test（`test_upsert_writes_*` 9→11 欄）+ 新增 3 test（升級表頭 / sync round-trip / 空欄不覆蓋記憶體），共 269 PASSED 零回歸。

---

### §3-S 新增「人看得懂的完整成本帳本」分頁 _持倉總覽（v18.182 新增）

**問題場景**（user 截圖 + JSON 備份）：v18.180/181 驗證 OK，但 user 反映「看不到 T7、帳本資料沒在 Excel，JSON 也是」。釐清：
1. user 開 Google Sheet 看到的是預設空白分頁 `工作表1`（資料其實在保單分頁 `00031611267318` 等，user 確認「有資料」）。
2. 完整帳本（單位數/平均成本/含息成本…）只存在 `_T7_State`（一格 `Ledger.to_dict()` JSON blob、人看不懂），且 user 的 Sheet 連這分頁都沒有；保單分頁只有 `invest_twd`，沒有 position。

**方案**（user 選「只存成本帳本」、暫不含市值）：新增 `repositories/snapshot_repository.py`：
- `HOLDINGS_TAB = "_持倉總覽"`（`_` 開頭 → `list_policy_worksheets` / `detect_sheet_schema_version` 的 `startswith("_")` 過濾自動排除，不會被誤認成保單分頁）。
- `HOLDINGS_COLS`（13 欄中文表頭）：保單號碼/基金代碼/基金名稱/幣別/級別/持有單位數/平均成本淨值/平均含息成本/平均匯率/投資金額(TWD)/現金給付%/累積已領配息(TWD)/更新時間。
- `save_holdings_overview(client, sheet_id, ledgers_dict, funds_lookup)`：t7_ledgers（position：units/cost_unit/cost_unit_with_div/fx_avg/dividends）⨝ portfolio_funds（name/is_core/div_cash_pct/invest_twd），每檔一列；clear + 1 batch update（同 `_T7_State` 防 429 模式）。更新時間用固定 UTC+8（repo 層不依賴 `ui.helpers.tw_time`，避免 repo→ui 反向依賴）。**只存成本面、不存市值**（市值隨 NAV 過時，由 app 即時算）。

**接線**：`_t7_save_snapshot_to_sheets()`（所有 T7 落帳的共同出口）與 `dump_all_to_sheet()`（全部寫入）寫完 `_T7_State` 後一併呼叫；後者 `out` 加 `n_overview`、Tab3 成功訊息加「_持倉總覽 +N 筆」。`test_ledger_snapshot_store` 新增 3 test（空/可讀列驗證/級別+pid fallback），共 236 PASSED 零回歸。

---

### §3-R 「上次寫入/讀回」時間戳顯示 UTC → 統一台灣時間 UTC+8（v18.181 修補）

**問題場景**（user 截圖）：「📦 全部寫入 Sheet」面板「上次寫入：2026-05-23 13:26」看起來「不會動」，且對不上 Google Drive 的「晚上9:25」。

**根因**：所有 wall-clock 時間戳用 bare `datetime.now()`，Streamlit Cloud 伺服器跑 **UTC** → 比台灣慢 8 小時（13:26 UTC = 21:26 台灣，與 Drive 的 9:25PM 其實同一刻）。`t3_last_save_at` 每次寫入都有更新（無 reset），純粹是顯示時區問題。

**Fix（全部統一台灣時間）**：新增 `ui/helpers/tw_time.py` — `tw_now()`（aware datetime, UTC+8）/ `tw_now_str(fmt)`，採固定 `timezone(timedelta(hours=8))`（台灣無 DST、不依賴 tzdata 最穩）。改 5 處：`tab3_portfolio.py` 上次寫入(`t3_last_save_at`)/上次讀回(`t3_last_load_at`)/JSON 備份檔名、`ui/helpers/json_backup.py` `exported_at`、`ui/tab3_t7_ledger.py` 方案 `created_at`；順手刪掉 inline `import datetime as _dt_q/_dt_top` dead import。

**邊界**：方案 id 的 `.timestamp()`（epoch 絕對值、tz 無關）與 ledger 交易 `.today()`（日期）不在範圍。`test_json_backup + test_app_smoke + test_policy_store + test_cloud_io + test_fund_ledger` 共 222 PASSED 零回歸。

---

### §3-Q T7 含息成本不生效 + JSON 備份漏存含息/現金給付%（v18.180 修補）

**問題場景**（user 反饋）：T7「💾 套用為起始部位」後 ①ledger「看起來沒變」 — `cost_unit_with_div` 永遠等於 `cost_unit`，對帳單欄(10) 含息成本沒生效；②下載的 JSON 備份檔沒有「🟨 現金給付 %」（`div_cash_pct`）與「📋 含息來源 / 含息成本」（`avg_nav_with_div`）。

**Bug A — 含息成本不生效**（`ui/tab3_t7_ledger.py:676`）：建 ledger 時 `_new_led.subscribe(_amount_twd, _fx, _cu, …)` 傳的是 `_cu`（平均買入淨值）而非 `_anw`（含息成本）；`Ledger.subscribe()` 首買時把 `cost_unit_with_div = nav`，覆蓋掉 user 抄入的含息成本。**Fix**：subscribe 後加 `if _anw > 0: _new_led.position.cost_unit_with_div = float(_anw)` 校正（type A 直接抄、type B 由累積配息反推皆走 `_anw`）。

**Bug B — JSON 備份漏欄**（`ui/helpers/json_backup.py` `build_export_payload`）：slim fund 序列化用固定欄位清單，漏掉 `avg_nav_with_div` + `div_cash_pct`。**Fix**：補這兩欄；`restore_from_json_bytes` 沿用「保留 JSON 全部 key」邏輯自動還原，T7 表單 `_f.get("avg_nav_with_div", 0)` / `_f.get("div_cash_pct", 100)` 重新讀回。

**Constraint C**：v1 保單分頁 `ALL_COLS`（policy_id/policy_name/fund_url/invest_twd/invest_date/currency/fx_at_buy/notes/policy_tier）**無含息成本/現金給付% 欄位** → 這兩欄唯一持久化途徑是 JSON 備份（Bug B 修好）。user 選「含息+JSON 兩修」、暫不擴充 v1 schema。`test_json_backup + test_fund_ledger + test_app_smoke + test_policy_store + test_cloud_io` 共 222 PASSED 零回歸。

---

### §3-P T7「套用為起始部位」存檔全量回寫保單分頁（v18.179 修補）

**問題場景**：User 截圖反饋 — 在 T7「✏️ 編輯持倉」表單輸入各基金淨投資金額後按「💾 套用為起始部位（覆蓋 T7 帳本）」存檔，新增/編輯的項目不會回寫到使用者實際讀寫的保單分頁（如 `QL19676552`），只能每次下載手改。

**根因**（`ui/tab3_t7_ledger.py` submit handler）：存檔寫四處中只缺最關鍵的一處 —
①本地 `t7_ledgers`（session）✅　②`_T7_State` 快照分頁 ✅　③`_Ledgers` 交易分頁 ✅（有 pid 才寫）　④**保單分頁基金列（含 invest_twd）只在 `_pid_changes`（保單號碼改變）時才 `upsert_fund_in_policy`** ❌。同保單內編輯金額（pid 未變）的基金列永遠不更新。

**Fix（全量同步保單分頁，user 選定）**：
1. 新增 `_funds_to_sheet: list[tuple]` 收集每一檔已套用且 `_pid_new` 非空的基金 `(pid, code, fund_obj)`。
2. OAuth 區塊條件改 `if _per_policy_rows or _pid_changes or _funds_to_sheet:`；把原本只跑 `_pid_changes` 的 upsert 迴圈改成跑 `_funds_to_sheet`，全量 `upsert_fund_in_policy`（帶 `invest_twd` / `currency` / `policy_tier`）。
3. notes 區分：pid 變更標 `T7 pid migrate`、其餘標 `T7 套用起始部位`；成功訊息加「+ 保單分頁回寫 N 檔」；`policy_tabs` cache 改在 `_funds_to_sheet` 非空時刷新。

**邊界**：無 pid 基金（未綁保單）仍不寫（無分頁可寫，正確）；未登入 OAuth / 無 sheet_id 時整段略過僅更新本地；`_f_obj` 為 `{}` 時 upsert 用 `.get` 預設值安全。`test_app_smoke + test_policy_store + test_cloud_io` 185 PASSED 零回歸。

---

### §3-O T7 KPI 拆「現金配息 / 配股」+ 鬼列 filter 補修大寫（v18.172 新增）

**問題場景**：User 截圖反饋 T7 帳本下方 KPI 卡「💵 預估年配息 NT$1,250,792 / 📅 每月被動現金流 NT$104,233」**沒套用 `div_cash_pct`** — 即使在 T7「📝 編輯持倉」設定部分配股（如現金給付% = 60），KPI 仍顯示全額年配息，配股估算也沒分開呈現。

**根因**：`ui/tab3_t7_ledger.py:1898` 只算 `_ann = 市值 × 配息率`，沒乘 `div_cash_pct/100`；KPI3/KPI4 直接用 `_ann_total_twd` 顯示。

**Fix A — 算式拆分**（`ui/tab3_t7_ledger.py`）：
- L1860-1865 新增 `_cash_total_twd = 0.0` / `_reinvest_total_twd = 0.0`
- L1898 起：取 `_dcp_f = clip(div_cash_pct, 0, 100)`，算 `_ann_cash = _ann × _dcp_f/100` 與 `_ann_reinv = _ann - _ann_cash` 累加
- per-row 加「預估月配股 (TWD)」欄（normal + no-ledger 兩 branch 同步）

**Fix B — KPI 卡 6 columns**（`ui/tab3_t7_ledger.py:1951+`）：
```
st.columns([2,2,2,2,1])  →  st.columns([2,2,2,2,2,1])
```
- KPI3「💵 預估年現金配息 (TWD)」= `_cash_total_twd`
- KPI4「📅 每月被動現金流」= `_cash_total_twd / 12`（cash-only）
- KPI5「🪙 預估年配股 (TWD)」= `_reinvest_total_twd`
- 重置按鈕移到 `_pc6`

**Fix C — 鬼列 filter 補修 case-insensitive**（`repositories/policy_repository.py:516-528`）：v18.171 filter `fund_url=='fund_url'` 只擋小寫，但 `cloud_io.dump_all_to_sheet:47` 把 `code .upper()` 後鬼列回寫變 `FUND_URL`（大寫）繞過 filter。改 `df["fund_url"].astype(str).str.lower() == "fund_url"` 三欄全 case-insensitive。

**Test 變更**：新增 `test_load_policy_worksheet_filters_uppercase_ghost_rows` regression case 用 `FUND_URL/INVEST_DATE/CURRENCY` 全大寫 record 斷言被過濾掉。

---

### §3-N 保單分頁「schema 鬼列」append_row bug fix（v18.171 修補）

**問題場景**：User 截圖「📋 保單分頁清單」存檔後 `QL19676552` tab 出現 3 列 `policy_name / fund_url / invest_date / currency / notes` 等 schema 英文 key 字串當資料值的鬼列。

**根因**：`repositories/policy_repository.py` 三處 `ws.append_row(list(ALL_COLS))` 補表頭的寫法：
- `:276` — `upsert_policy_row` 補表頭分支
- `:474` — `ensure_policy_worksheet` 既有 worksheet 但 row 1 讀成空時補表頭
- `:480` — `ensure_policy_worksheet` 新建 worksheet 後寫表頭

gspread `append_row` 是**追加到資料末列**而非插入 row 1。當 worksheet 已存在但 row 1 被讀成空（user 手動清過 / gspread 偶發空回應），表頭被塞到資料底部成為鬼列；user 多次「全部寫入」累積 3 列。

**Fix A**（3 處）：`append_row(list(ALL_COLS))` → `ws.update("A1", [list(ALL_COLS)])` 強制 row 1。

**Fix B 防禦過濾**（`load_policy_worksheet:516-525`）：DataFrame 過濾 `(fund_url=='fund_url') & (invest_date=='invest_date') & (currency=='currency')` 的鬼列；現存髒資料畫面立刻乾淨。三欄都比對是為避免「真實基金代碼剛好叫 fund_url」的極端誤刪。

**Test 變更**：
- `test_ensure_policy_worksheet_creates_when_missing` 改斷言 `update.assert_called_once_with("A1", [list(ALL_COLS)])`
- 新增 `test_ensure_policy_worksheet_existing_with_empty_row1_writes_header_to_A1_not_append` — 模擬「row 1 空、row 2-3 有資料」場景，斷言不准 `append_row`
- 新增 `test_load_policy_worksheet_filters_schema_ghost_rows` — 2 個鬼列 record + 1 個真實 record，斷言 load 後只剩 1 列且 `fund_url == "ACTI71"`

---

### §3-M T7 編輯持倉表單暴露 div_cash_pct + 月配息估算（v18.170 新增）

**問題場景**：T7「📝 編輯持倉（手動微調 — 從 CHUBB 對帳單抄入精確值）」表單僅 5 欄（淨投資金額／淨值／匯率／含息來源／保單號碼）。User 反映保單實際支援「部分配息+部分配股」，希望用「資金的百分比」算每月配息與配股。

**既有 v18.160 基礎**：`div_cash_pct`（0-100）已有 schema、`estimate_dividend_split` 函式、v2 編輯表格欄位、**年度**估算 expander；T7 編輯持倉表單**未暴露此欄位**，估算函式只有年度模式。

**設計**：
1. **T7 表單第 6 欄**（`ui/tab3_t7_ledger.py:564, 615-628`）：`st.columns([1,1,1,1,1])` → 6 個 columns；最末加 `ic6.number_input("🟨 現金給付 %", 0-100, step=5, default=100)`。
2. **submit handler 同步寫回**（`ui/tab3_t7_ledger.py:627, 646, 689`）：`_init_inputs` tuple 加 `_dcp`；`_f_obj["div_cash_pct"] = max(0, min(100, float(_dcp)))` 寫入 portfolio_funds → 後續存回 Sheet。
3. **月配息估算 toggle**（`ui/helpers/v2_editor.py:151-204`）：`_render_div_split_estimate` 加 `st.segmented_control(["📅 年估算", "📆 月估算"])`；月模式下 `annual_div_rate_pct / 12` 傳給既有 `estimate_dividend_split`（函式簽名不變），表格欄位與 3 個 metric 標題隨 `_label="月"/"年"` 動態切換。

```
| 模式  | rate 傳入                  | 表格欄位                       | metric 標題     |
|------|--------------------------|--------------------------------|----------------|
| 年估算 | `rate_pct`                | 年配息總額 / 年現金 / 年再投入 | 📦 年配息總額   |
| 月估算 | `rate_pct / 12`           | 月配息總額 / 月現金 / 月再投入 | 📦 月配息總額   |
```

**語意定義（div_cash_pct）**：100 = 全現金給付；0 = 全部轉單位（配股）；介於兩者 = 部分配股（如 80=80% 現金 + 20% 單位）。

---

### §3-L 「📋 保單清單」說明區塊搬到說明書 §9（v18.169 新增）

**問題場景**：Tab3「📋 保單管理」expander 內「📋 保單清單（這本 Sheet 內的保單分頁與輔助 tab）」區塊（3 行說明 + 3 個動態 metric）屬於「使用說明」性質，user 截圖反饋不該占 Tab3 動作面板版面，要求搬到「📖 說明書」tab。

**設計**：
1. **Tab3 刪除整段**（`tab3_portfolio.py:644-675` 共 32 行）：包含 markdown 標題、caption 說明、3 個 `st.metric`（保單分頁 / `_T7_State` / `_Ledgers` 計數）、可選的 `last_sync` caption；改 1 行 v18.169 註解。
2. **Tab6 新增第 9 個 sub-tab**（`tab6_manual.py`）：`_t6 = st.tabs([...])` 從 8 個加到 9 個，新增「📋 9. Sheet 資料結構」；內容為純靜態 markdown 4 欄表格（Tab 類型 × 命名規則 × 用途 × 同步來源）+ 4 個重點觀念 bullet + 多帳本管理引導。
3. **動態 metric 數字捨棄**：原 `_sheet_stats` 的 tabs / t7_state / ledgers 計數依 user 決定不在說明書重現（靜態文件不放動態數字）。

```
| 區塊        | v18.168（舊位置）           | v18.169（新位置）          |
|------------|----------------------------|---------------------------|
| 說明文字     | Tab3 expander 內            | Tab6 §9 sub-tab           |
| 3 個 metric | Tab3 expander 內 metric 卡片 | （捨棄，靜態文件不放）       |
```

`_sheet_stats` 在 v18.169 後仍由「🔄 只重新整理分頁清單」按鈕更新（不影響其他消費者）。

---

### §3-K 📥 雲端讀取面板上下半對調（v18.168 新增）

**問題場景**：v18.166 面板「全部讀回」在上、「從 Drive 挑帳本」在下，user 截圖紅框 + 紅箭頭反饋要對調 — 先挑帳本（前置動作）再讀回（後續動作）才符合操作順序。

**設計**：上下半順序交換，下半的「全部讀回」加 `**📥 全部讀回（雲端 → 本地）**` 標題對稱上半的「📂 從 Drive 挑帳本」標題。

```
| 操作順序     | v18.166（舊）             | v18.168（新）             |
|------------|---------------------------|---------------------------|
| 上半（先做）  | 📥 全部讀回（雲端 → 本地）  | 📂 從 Drive 挑帳本         |
| 下半（後做）  | 📂 從 Drive 挑帳本         | 📥 全部讀回（雲端 → 本地） |
```

info 文案微調：「請從下方挑一本」→「請從上方挑一本」對齊新版型。widget key 不變。

---

### §3-J 刪除雙入口、瘦身成「🛠️ 進階工具」（v18.167 新增）

**問題場景**：頂部 5 顆按鈕已覆蓋全部存讀，但下方 expander 內仍有 v18.50「🧰 一鍵存讀」+ v18.70「📁 本機 JSON 備份」共 6 顆重複按鈕占版面。user 截圖紅框反饋「請保留單一上方五個按鈕的功能」。

**設計**：刪除重複的 4 顆 button（全部寫入 / 全部讀回 / 下載 JSON / 上傳 JSON），保留 2 顆獨家功能，rename 區塊為「🛠️ 進階工具」。

```python
# tab3_portfolio.py:895+
if _sheet_id:
    st.markdown("---")
    st.markdown("##### 🛠️ 進階工具")
    st.caption("📌 全部存讀請至頂部「🚀 快速存讀面板」；此處只放頂部沒有的小工具。")

    _tool_c1, _tool_c2 = st.columns(2)
    _refresh_clicked = _tool_c1.button("🔄 只重新整理分頁清單（不動投組）", ...)
    _clear_cache_clicked = _tool_c2.button("🗑️ 清空抓取快取", ...)
    # 快取狀態 caption（hit-rate / entries / hits-misses）

    # refresh handler 簡化：只剩 refresh_only=True
    if _refresh_clicked:
        from ui.helpers.cloud_io import load_all_from_sheet
        _res_l = load_all_from_sheet(_client, _sheet_id, ss, refresh_only=True)
        ...

    # 保單分頁清單（dataframe display, 加 ** 標題）
    _pdf_cached = st.session_state.get("policies_df")
    if _pdf_cached is not None and not _pdf_cached.empty:
        st.markdown("**📋 保單分頁清單**")
        st.dataframe(...)

# v18.167：「📁 本機 JSON 備份」整段刪除（與頂部 💾/📂 重複）
```

**移除清單**：
- `btn_dump_all_v18_50`（📦 全部寫入 Sheet）— 與頂部 📦 雲端存檔 重複
- `btn_load_all_v18_50`（📥 全部讀回）— 與頂部 📥 雲端讀取 重複
- `pm_upload_json_v18_70` + 對應 download_button — 與頂部 💾/📂 重複
- 對應 `_dump_all_clicked` / `_load_all_clicked` handler block

**保留清單**：
- `btn_policy_refresh`（🔄 只重新整理）— refresh_only=True 路徑，頂部無對應
- `btn_clear_fetch_cache_v18_58`（🗑️ 清空快取）— fund_fetcher / macro TTL 清空，頂部無對應
- `_pdf_cached` dataframe — 純顯示，加 `**📋 保單分頁清單**` 標題

---

### §3-I 「從 Drive 挑帳本」移到「📥 雲端讀取」面板（v18.166 新增）

**問題場景**：v18.165 把「自動建立」+「從 Drive 挑」上下並列在「✨ 新增帳本」面板，user 截圖紅框 + 紅箭頭反饋希望分流。

**設計**：依字面語意分流到對應 button：
- **✨ 新增 = create new** → 只放「自動建立新 Sheet」
- **📥 雲端讀取 = pick existing + load** → 同時包含「全部讀回」與「從 Drive 挑帳本」

```python
# tab3_portfolio.py:263+
if _io_panel == "load":
    st.markdown("**📥 雲端讀取（全部讀回 / 挑選帳本）**")
    # 上半：全部讀回（需 _sheet_id_q）
    if _sheet_id_q:
        [📂 帳本: 名稱 ｜ 持倉檔數 ｜ 上次讀回] + [📥 立即全部讀回]
    else:
        st.info("尚未指定 Sheet ID。請從下方挑一本，或至「✨ 新增帳本」建立")

    # 下半：從 Drive 挑帳本（OAuth + 已登入恆顯示）
    if _oauth_configured and _logged_in_q:
        st.markdown("---")
        st.markdown("**📂 從 Drive 挑帳本（切換 / 首次選用）**")
        [🔄 載入資料夾清單] [📁 限定資料夾] [📂 列 Sheets] [✅ 使用此 Sheet]

# tab3_portfolio.py:432+
elif _io_panel == "new":
    st.markdown("**✨ 新增帳本（建立全新 Google Sheet）**")
    st.caption("...想挑 Drive 內既有的 Sheet 請改點「📥 雲端讀取」")
    [新 Sheet 名稱] [🚀 自動建立 Sheet]
```

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
| ~~Tab4~~ | ~~🔬 回測~~ | ~~CAGR/Sharpe/MDD~~ | **v18.176 移除**（換基金判斷改用組合基金的汰弱留強/戰情室；回測拖速度且 NAV 歷史抓不全）。`services/backtest_service.py` 純計算保留供未來 |
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
