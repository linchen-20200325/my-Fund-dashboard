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

### §3-BA D 模式「🔍 自動抓取」— 按代碼自動填基金 metadata（v18.234 新增）

**痛點**：v18.233 的 D 模式要 user 手動填 6 個欄位（代碼/名稱/幣別/NAV/FX/有配息），實務上 user 通常只記得代碼。

**設計**（user 拍板：保留微調 + cache 1 小時）：
- expander 上排：`代碼` text_input + `🔍 自動抓取` button + 訊息區（3 欄）
- 抓取流程：
  - `_t7d_fetch_fund_meta(code)` (cache TTL=3600) → `repositories/fund_repository.py:fetch_fund_multi_source(code)`
  - 回 `{fund_name, currency, series, dividends, metrics, ...}` 多源聚合（FundClear/TDCC/MoneyDJ/Cnyes/Morningstar）
  - FX 用 `_fx_now(f"{ccy}TWD")` fallback，再不行 → 31.0 預設
- expander 下排：5 個欄位（名稱/幣別/NAV/FX/有配息）value 從 staging 預填，user 可微調
- staging 結構：`session_state["t7d_stage__{pid}"] = {name, ccy, nav, fx, has_div}`
- **version 控制**：`session_state["t7d_ver__{pid}"]` 每次抓取/新增後 +1；widget key 含 `__v{ver}` 觸發 Streamlit widget 重置，讓 staging 預填生效（繞過 widget value 一旦初始化不會被 value= 覆蓋的限制）

**失敗 fallback**：
- 抓不到（meta error 或 series 為空）→ red error 訊息「⚠️ 抓不到 X，請手動填」+ widget 維持空白
- 抓到部分（NAV 有 FX 沒）→ 已抓到的預填、缺的留 user 補

**cache helper**（module-level）：
```python
@st.cache_data(ttl=3600, show_spinner=False)
def _t7d_fetch_fund_meta(_code: str) -> dict:
    try:
        from repositories.fund_repository import fetch_fund_multi_source
        return fetch_fund_multi_source(_code.strip().upper())
    except Exception as e:
        return {"error": str(e), ...}
```

**位置** `ui/tab3_t7_ledger.py`：
- module-level cached helper `_t7d_fetch_fund_meta` L82-93
- expander 上排（代碼 + 抓取 + 訊息）L1604-1672
- expander 下排（預填 5 欄 + 新增按鈕）L1674-1740

**引擎零變動**：自動抓取結果存進原本的 fund dict 結構（v18.233 設計），Switch 引擎完全感知不到差別。

**驗證**：AST OK；`pytest -m "not slow"` **640 passed**；ruff 零新增。

---

### §3-AZ C 區 D 模式（C 內 toggle）— 允許新增「自訂基金」作買方候選（v18.233 新增）

**痛點**：投資型保單實務中偶爾會出現「**買方標的不在系統 portfolio_funds 內**」的情境（user 想試算「如果換成這檔新基金、其他配置不變的試算」、或者基金代碼系統還沒收錄）。

**設計**（user 選的方案：「C 內 toggle」）：
- C 區頂部加 `🆕 啟用 D 模式` checkbox（不開新 tab、不複製 600 行）
- D 模式 on → 顯示「➕ 新增自訂基金」expander，widget：代碼／名稱／幣別／NAV／FX→TWD／是否有配息（checkbox）
- session 端 isolation：`session_state.t7d_custom_funds[保單] = {pk: fund_dict}`
- fund dict 結構：`{code, name, currency, fx_rate, series=pd.Series([nav]), dividends=[...], policy_id, _is_custom_d=True}`
- 已新增列表顯示在 expander 內，每筆右側有 🗑️ 移除按鈕

**local merge（只在 _tC scope）**：
- `_fund_by_pk[custom_pk] = custom_fund`
- `_name_lookup_t7[custom_pk] = custom_name`
- `_dy_lookup_t7[custom_pk] = 0.0`
- `_c_all_pks_pid.append(custom_pk)` → 自動進「買方標的（複選）」候選
- 自動進「目的」selectbox 預設邏輯（dividends 非空 → 預設 💰，空 → 🌱）

**引擎零變動**：
- `_ledger_for(pk)` 對找不到的 pk 自動建空 ledger（既有 fallback）
- `Switch.switch_same/cross_currency` 對空 buyer 正常工作（首次當 buyer 會建 position）
- `_latest_nav_fx_t7` 的 `series.dropna().iloc[-1]` fallback 自動拿到 user 輸入的 NAV；`fx_rate` 提供 FX fallback

**不寫回主資料庫**（避免汙染）：
- custom 不 upsert 進 portfolio_funds
- ledger position 只活在 session
- dual-write Sheet 行的 note 加 `[D 自訂]` 標記方便人工辨識後正式建檔

**位置** `ui/tab3_t7_ledger.py`（C 區頂部插入）：
- D mode checkbox + 自訂基金 expander L1574-1665
- local merge custom 進 lookup dicts L1667-1672
- dual-write note `[D 自訂]` 標記 L2094-2096 / L2106 / L2117

**驗證**：AST OK；`pytest -m "not slow"` **640 passed**；ruff 零新增。

---

### §3-AY C 區買方端「目的」維度（配股/配息/⚖️ 同時拆兩段）（v18.232 新增；簡化 §3-AX）

**痛點 + user 修正**：v18.230（§3-AX）把 A/B/C 都加了「% / 單位」mode，但 user 截圖反饋「**非單位數，只留百分比，但這百分比可以選擇配股數或是配現金**」——`📊 % vs 🎯 單位` 不是 user 要的維度；user 要的是「**% 額度的去向：配股（累積）或配息（領現金）**」，同一標的還可拆兩段。

**設計**（C 區重做）：
- 移除 C 賣方端 `sell_mode` selectbox → 純「賣出 %」
- 移除 C 買方端「分配模式 (% / 單位)」selectbox → 純「% 權重」+ ≈100% 校驗
- **新增** 每買方「目的」selectbox `🌱 配股` / `💰 配息` / `⚖️ 同時`，預設依基金 `dividends` 屬性自動帶（非空 → 💰，空 → 🌱）
- **「⚖️ 同時」** 即時展開兩 % 欄（該檔內部 配股 % + 配息 % 應 = 100%）
- 試算結果加「目的」欄；摘要新增 3 metric「🌱 配股總額 / 💰 配息總額 / 📐 配股/配息比」
- dual-write sell/buy 兩筆 sheet note 標記「（{purpose_disp}）」

**引擎不動**：仍呼叫同一個 `Switch.switch_same/cross_currency`；配股/配息為**顯示與記帳標記**，「同時」拆兩段在「TWD 成本搬移」層級按 `%_split` 拆累計（`_stock_total_twd` / `_income_total_twd`），不分裂 transaction。

**理論銜接 §3-A**：原「Σ Weight_j = 100%」實體鎖**完全恢復**（移除 v18.230 混搭退化）。目的標記層獨立、與 Σ Weight 守恆不衝突。「同時」拆兩段在標記層加 sub-校驗（單檔內 `stock_split + income_split = 100%`）。

**位置** `ui/tab3_t7_ledger.py`（C 區）：
- 賣方 widget（純 %）L1632-1641
- 買方 % 權重 widget L1707-1720
- 目的 selectbox L1681-1701
- 「⚖️ 同時」拆分展開 L1722-1746
- 校驗 L1777-1804
- 計算（純 %）L1853-1893
- result row「目的」欄 L2019-2034
- 摘要 3 metric L2189-2219

**A/B 暫不動**（待 user 確認範圍）：A 新投入仍保留「TWD 金額 / 目標單位數」；B 投入再平衡保留「% / 目標單位」。

**驗證**：AST OK；`pytest -m "not slow"` **640 passed**；`test_app_smoke + apptest` 通過；ruff 零新增。

---

### §3-AX A/B/C 試算支援「目標單位數」模式（新標的可配股數、舊持倉可混搭）（v18.230 新增；C 區已被 §3-AY 簡化覆蓋）

**痛點**：A/B/C 三組試算只能填 TWD 金額／% 權重——但「新標的」（例：安達）規格是直接配「股數（單位）」，無持倉時 % 算不出來；舊持倉（例：安聯）則該保留 %／TWD 直覺。

**設計**（單一節點變更，引擎零動）：
- UI 加「分配模式」selectbox 群：`📊 % / 💵 TWD` vs `🎯 目標單位數`
- 新標的（`_t7_has_position(pk) == False`）→ 預設「🎯 目標單位數」；舊持倉 → 預設「📊 % / 💵 TWD」；皆可手動切換
- mode selectbox 放 **form 外** 讓 widget 即時 reactive（form 內 selectbox 切換不會 rerun 重畫 widget）
- submit 時用 helper `_t7_units_to_twd(units, nav, fx) → float` 換算 TWD，餵舊 `Ledger.subscribe(amt_twd, fx, nav, date)` / `Switch.switch_same_currency(units_to_redeem, ...)` / `Switch.switch_cross_currency(...)`，**引擎介面零變動**

**混搭規則**（同一賣方 / 同一投入下，多檔可混 % 與單位）：
1. 單位模式檔先吃固定金額：`fixed_amt_i = units_i × NAV_i × FX_i`
2. 剩餘金額 = 總投入（B）／賣方贖回 TWD（C）− Σ fixed_amt
3. % 模式檔按缺口比例分配剩餘金額（B 維持「投入後總市值 × Weight − 目前市值」缺口比例）；C 按「% 模式檔群」內權重攤分剩餘
4. 校驗：若單位模式檔總額 > 投入／賣方贖回 → `❌` 並中止；% 模式檔仍需總和 ≈ 100% ± 0.5%（單獨群內，不含單位模式檔）

**C 賣方端**：賣方獨立 mode selectbox `💱 賣出 %` vs `🎯 賣出單位數`；單位模式上限 = 持倉 units，超出立報錯。

**理論銜接 §3-A**：原「Σ Weight_j = 100%」實體鎖在「全部 % 模式」場景下仍嚴格適用；混搭模式下退化為「**% 模式檔群內**的 Σ Weight = 100%」，單位模式檔不參與權重校驗（其目標單位直接給定）。Σ Net_Switch_Value = Σ fixed_amt + Σ pct_amt 守恆。

**位置** `ui/tab3_t7_ledger.py`：
- helper：`_t7_has_position` / `_t7_units_to_twd`（module-level，可單測）
- A 既有：form 外 mode L943-961；form 內 widget L1008-1031；submit L1196-1217
- A 新增：form 外 mode L963-973；form 內 widget L1054-1068；submit L1148-1162
- B：form 外 mode（expander）L1289-1308；form 內 widget L1322-1351；submit 拆分 + 缺口分配 L1389-1500
- C：賣方 widget L1538-1577；買方 widget L1620-1689；校驗 L1714-1746；計算 L1797-1893；result row 顯示 L1980-1998

**驗證**：AST OK；`pytest -m "not slow"` **640 passed**；`test_app_smoke + apptest` 通過；ruff `tab3_t7_ledger` 零新增（既有 12 errors 不變）。

---

### §3-AW 多 Gemini key 自動輪替：分散免費額度 + 防斷（v18.217 新增）

**需求**（user）：手上有多個 Google 帳號的 Gemini API key，想分流 token / 免費額度。拍板「自動輪替」（撞配額自動換把）而非各 Tab 固定分配。

**核心** `services/ai_service.py`：
- `get_gemini_keys() -> list[str]`：從環境變數收齊所有 key，去重保序。來源 = `GEMINI_API_KEY`（主）＋ `GEMINI_API_KEYS`（逗號/分號分隔）＋ `GEMINI_API_KEY_1..10`（編號）。
- `gemini_generate(prompt, max_tokens, keys, start)`：從 `start` 起 round-robin 試 key；撞 429（配額）就立刻換下一把（`retry=0` 不空等），全部撞配額才回 429 訊息；撞 **5xx 忙線／逾時**（換 key 無助於修復）改在**原 key 指數退避重試**（`retry=2`，5s→10s），仍忙線回友善 503 訊息而非原始 JSON（v18.228 修；舊行為是「不換 key 直接噴原始錯誤」）；其他錯誤直接回；**單把 key 時退化成原 `_gemini`**（保留預設 retry 容錯）。
- `_is_quota_error(text)`：以 `"429"` / `"配額已達上限"` 判定。
- `_is_transient_error(text)`（v18.228）：以 `HTTP 500/502/503/504` / `逾時` / `忙線` 判定 → 觸發原 key 退避重試。`_gemini` 5xx 分支同步改 `5s,10s` 退避，503 耗盡後回友善訊息（單 key 路徑亦受惠）。

**接線** `ui/helpers/ai_summary.py`（三 Tab 共用 widget）：傳入 key 優先、其餘從池補上；用跨 Tab 的 `st.session_state["_gemini_key_cursor"]` 當 round-robin 起點（即使沒撞 429 也輪流，平均分散負載）；footer caption 顯示「N 把 key 輪替」。

**Secrets 寫法**（任一即可，可混用；單把 = 維持原樣）：
```toml
# .streamlit/secrets.toml（或 Streamlit Cloud → App settings → Secrets）
GEMINI_API_KEY = "主帳號key"               # 主／向後相容
GEMINI_API_KEYS = "帳號2key, 帳號3key"      # 逗號分隔多把
# 或編號式：
GEMINI_API_KEY_1 = "帳號2key"
GEMINI_API_KEY_2 = "帳號3key"
```
`app.py:_load_keys` 會把上述全部從 secrets 鏡像到 env 供 `get_gemini_keys` 讀。

**驗證**：`test_ai_service.py` 11 passed（解析/去重/輪替/全429/offset/單key/空池＋v18.228：5xx 同 key 退避 `[(A,0),(A,2)]`／其他錯誤不換 key／`_is_transient_error` 偵測）；`pytest -m "not slow"` 640 passed/1 skipped；ruff 零新增；向後相容（單 key 行為不變）。

---

### §3-AV Tab1 總經 AI 也改白話總體檢、刪舊七節 macro AI（v18.215 改版）

**需求**（user 連兩次強調 + 附截圖）：每個 Tab 的 AI「不要選單、整合成單一結構化完整摘要、逐章節結論+時事、減少金融術語直接白話」。截圖證實線上仍是舊 4 視角 selectbox → 純屬**部署未更新**（看到的是 v18.208 舊 deploy，非程式碼問題）。

**拍板**（AskUserQuestion）：Tab1 也改白話摘要、刪舊 AI（接受拿掉「老手量化推演」深度，換全白話 + 三 Tab 一致）。

**改動**：
- `ui/tab1_macro.py`：移除「🤖 AI 結構化總經摘要」按鈕 + `analyze_macro_structured` 呼叫；改掛通用 `render_ai_summary_widget`（無選單、單鍵、`expanded=True`）。新增 `_build_macro_ai_snapshot(ind, phase, score, srd, news)` → 組「全資料」快照（景氣位階/分數/配置/系統性風險+觸發字/全部總經指標/領先指標排名 top3/當下子領域燈號/新聞）+ 6 章節清單。
- **刪除** `services/ai_service.py:analyze_macro_structured`（最後一個函式，~184 行）與 `services/ai_prompts.py:build_macro_structured_prompt`（七節、含 Z-Score/σ/乖離率 老手術語）；連帶清 import + docstring + `test_ai_prompts.py` 2 個 macro 測試。

**結果**：Tab1/2/3 三個 Tab 現在都用同一個「🤖 AI 白話總體檢」widget（無選單、逐章節【白話結論】+【時事】、強白話風格）。

**部署**：須 merge → `main` 並重新部署/Reboot 才會在線上生效。

**驗證**：AST/import/dangling-ref 全清；ruff 自控檔全綠、tab1 零新增、ai_service −3；`pytest -m "not slow"` 602 passed/1 skipped；mock 驗 Tab1 快照產出完整。

---

### §3-AU 三 Tab AI 統一「白話總體檢」：吃全章節快照、逐章節結論+時事（v18.214 改版）

**需求**（user）：Tab1/2/3 每個 Tab 的 AI 都要**讀該 Tab 全部資料**、**逐章節**給結論＋**時事**；不適用的就刪掉改成「結構化完整摘要」。追加：**很白話、盡量不用專業金融術語**。

**拍板**（AskUserQuestion）：①「重寫通用 widget、保留專用 AI」（不動成熟的 macro / mk_advisor，只換掉不符需求的 4 視角散文 widget）；②「每 Tab 一個主 AI」。

**改寫核心** `ui/helpers/ai_summary.py:render_ai_summary_widget`：
- 介面新增 `sections: list[str]`（章節清單，依顯示順序）。
- 移除 4 視角 selectbox / `PERSPECTIVES` / `_build_prompt`；改單一「🤖 AI 白話總體檢」按鈕。
- 結果存 `session_state[f"{tab_key}_ai_struct"]`，重開 expander 顯示快取、不重打 API；「🔄 重新生成」可覆寫。max_tokens 3500。

**新 prompt** `services/ai_prompts.py:build_structured_summary_prompt(tab_label, snapshot, sections, headlines, stale_note)`：
- 強白話風格守則：像跟新手朋友聊天、術語用括號補生活化解釋、多用天氣/體檢/紅綠燈比喻。
- 逐章節輸出 `### <章節>`，每節含【白話結論】+【最近新聞影響】；末段 `### ✅ 一句話總結 & 下一步`。
- 嚴格只引用快照＋新聞、缺資料就老實說。
- **刪除** v18.159 的 4 散文 builder（`build_trend_action_prompt` / `build_allocation_diagnosis_prompt` / `build_beginner_guide_prompt` / `build_news_driven_prompt`）。

**各 Tab 接線**：
- **Tab1**：保留 `analyze_macro_structured`（7 段結構化＋新聞，已吃全 macro 資料）；移除重複的散文 widget；macro prompt 補白話風格守則。
- **Tab2**：沿用既有完整 10 段快照，傳 `sections`（基本/績效/風險/配息/買賣點/持股產業/總經/新聞）切結構化。
- **Tab3**：`_render_tab3_ai_summary` 快照由稀疏 4 段擴成全章節 — 加組合健康度 KPI（`compute_health_kpis`）、各檔 MK 體檢結論（`build_mk_dataframe`）、同類 PK 優等生/汰弱（`build_checkup_dataframe`），續接配息現金流＋新聞。

**未動**：LLM 仍走既有 Gemini（`_gemini`，未換供應商）；T7 `analyze_portfolio_mk_advisor` 保留為「深入版」。

**測試/驗證**：`test_ai_prompts.py` 刪 5 個舊 builder 測試、加 3 個 `structured_summary` 測試；ruff 自控檔全綠、tab1/2/3 零新增錯誤；`pytest -m "not slow"` 604 passed/1 skipped。沙箱無瀏覽器+無 GEMINI_KEY → AI 實際文字未親驗，僅 prompt/流程/快照層驗證。

---

### §3-AT 基金體檢表：郭老師「挑三揀四」PK 同類型（v18.213 新增）

**需求**（user）：依郭老師「挑三揀四」法則，逐檔把基金含息報酬與**同類型平均** PK，打敗同類＝🏆 優等生（抱緊滾雪球）、明顯落後＝⚠️ 汰弱候選。

**放置 / 判定基準**（user 拍板）：Tab3 expander（MK 戰情室下方，`tab3_portfolio.py:render_mk_war_room` 後）；優等生判定「以同類 1Y 為主」。

**新檔** `ui/helpers/fund_checkup.py`（純函式 + 單一 render，無 `@st.cache_data`）：

```python
build_checkup_dataframe(portfolio_funds) -> pd.DataFrame  # 依 code 去重；12 欄
_extract_peer_1y(fund) -> (peer_ret|None, label)          # 取 risk_metrics.peer_compare「同類型平均」首個數值
_ret_1y_total(fund) -> float|None                          # 沿用 compute_1y_total_return，退 perf["1Y"]/metrics
_period_ret(fund, perf_key, metric_key)                    # perf 優先退 calc_metrics（1M/3M/6M）
_grade(ret_1y, peer_1y) -> (excess|None, 判定文字)         # 超額≥+2🏆 / ±2內🟡 / ≤−2⚠️ / 缺資料⬜
_style_checkup(df)                                         # 🏆綠底 / ⚠️紅底 / 超跌價深綠底
render_fund_checkup(portfolio_funds) -> None               # expander：caption + 白話文 + 統計列 + dataframe（依超額降序）
```

**欄位**：代碼 / 標的名稱 / 近1M / 近3M / 近6M / 近1Y含息 / 同類平均(1Y) / 超額(pp) / 夏普 / 年化波動 / 買點（重用 `mk_dashboard.tag_price_zone` 燈號）/ 體檢判定。

**資料邊界（誠實告知，§4）**：
- 同類平均取自 MoneyDJ 績效評比頁 `risk_metrics.peer_compare`，約 3 成基金抓不到 → ⬜ 不評（不臆造）。
- 郭老師另兩標準（成分股 ROE>15%/EPS 成長、規模流動性）資料源無法取得 → **未納入**並於 UI 白話文標明；買賣點細節仍在 MK 戰情室。
- 同類平均可能為年平均報酬、與本基金含息基準略有差異 → tooltip 註明「僅供方向參考」。

**驗證**：AST + import + ruff `All checks passed`；mock 邏輯測試（分級門檻 / peer 抽取 / 去重 / styler html 上色）全綠；`pytest -m "not slow"` 606 passed / 1 skipped 零回歸（沙箱無瀏覽器、表格視覺未親驗）。

---

### §3-AS 程式碼健康度：清除 dead `analyze_fund_json` 及連帶孤兒（v18.209 新增）

**動機**（user 選「清 analyze_fund_json dead code」）：§3-AQ（v18.207）把 Tab2 三 AI 整併為唯一 widget 後，`analyze_fund_json` 已無任何 live caller，屬死碼。

**範圍盤點（先 grep 全 blast radius 再動手）**：
- `services/ai_service.py:analyze_fund_json`（~128 行）→ 删（唯一 caller 已於 v18.207 移除、無 test 直接覆蓋）。
- `_format_news_for_fund_ai`（~26 行）→ 連帶删（grep 確認僅 `analyze_fund_json` 使用）。`_format_fund_holdings` 因 `analyze_portfolio_mk_advisor` 共用 → **保留**。
- ai_service 孤兒 import：`FUND_JSON_SCHEMA_HINT` / `fund_analysis_to_markdown` / `parse_llm_json` / `build_fund_json_prompt` / `build_fund_json_structured_prompt` → 删 ai_service 的 import（這些函式本體仍在 `ai_models`/`ai_prompts`、且 `test_ai_models.py`/`test_ai_prompts.py` 仍覆蓋，**未動本體與 test**）。
- **Bonus**：`app.py` 的 `from services.ai_service import (...)` 整段 5 個名稱（analyze_fund_json / analyze_macro_structured / analyze_portfolio_mk_advisor / event_impact_analysis / build_stale_flags）在 425 行收口後**全未使用**、且無從 app re-export（tabX 模組各自直接 import）→ 同類 dead import 整塊移除。

**安全核對**：删前 grep 確認 (1) 無外部模組 `from services.ai_service import` 上述符號、(2) `_format_news_for_fund_ai` 無其他 caller/test、(3) 5 個 prompt/model 符號的 test 是從來源模組 import 而非 ai_service。

**驗證**：AST PASS（ai_service.py / app.py）、ai_service.py 無 dangling ref、`pytest -m "not slow"` 606 passed / 1 skipped、slow AppTest 全綠。

**後續候選**(v19.245 R13 復查:**已自動下架**,SPEC 文件漂移):`build_fund_json_prompt` / `build_fund_json_structured_prompt` + `FUND_JSON_SCHEMA_HINT` / `fund_analysis_to_markdown` / `parse_llm_json` 五個 symbol 早於 v18.238 整檔 `services/ai_models.py` 移除時連帶下架,grep 全網 0 caller / 0 module 殘留。`tests/test_ai_models.py` 同步下架。本段歷史紀錄保留。

---

### §3-AR Tab2 唯一 AI 快照加料：σ絕對位階 / 賣點 / 吃本金 / 經理費（v18.208 新增）

**需求**（user 選「強化 ④ AI 解盤內容」）：v18.207 整併後的唯一 AI，快照再補進 Tab 內已顯示、但 AI 先前看不到的旗艦訊號。

**新增 4 項（接在 v18.207 `_snap` 之上）**：
- **σ絕對位階(HWM)**：AI 區重算 `calc_hwm_sigma_levels(s, lookback=252)`（`s`=淨值序列），帶 `label / dist_to_hwm_pct / sigma_rank` → AI 才知「現價相對歷史最高點的絕對位階」。
- **賣點 sell1-3**：原快照只有 buy1-3/bb/ma60，補 sell1/2/3（停利點）。
- **吃本金 coverage**：配息行重算 `dividend_safety(total_return=ret_1y_total, dividend_yield=annual_div_rate, nav_change=ret_1y_total)`，帶 `coverage + alert_level`（Core Protocol Ch.3.2 旗艦檢查：含息報酬 vs 配息率）。
- **經理費**：基本行補 `mj_raw.mgmt_fee`（隱形成本）。

**邊界**：σ位階以 `if s is not None` + try 守（短序列/`{"error":...}`）；吃本金以 try 守（累積型不配息 / dividend_yield 為字串時 `<=0` 比較例外）。皆「有值才帶」、空則省略。

**驗證**：AST PASS、簽名核對相符、`pytest -m "not slow"` 606 passed / 1 skipped、`test_tab2_single_fund.py` 5 passed、Tab2 AppTest 渲染。

---

### §3-AQ Tab2 三 AI 整併為唯一 `render_ai_summary_widget`（吃全章節快照）（v18.207 新增）

**需求**（user 截圖）：「單一基金深度分析有很多個 AI，請幫我只留一個，且該 AI 需要抓取這 Tab 所有章節的資料作資料分析與總結」。

**現況**：Tab2 散落 3 個 AI——① v18.135 `analyze_fund_json` 紅綠燈按鈕、② v18.205 個股新聞面 AI（sibling widget）、③ v18.159 末端 `_render_tab2_ai_summary` widget。彼此快照各看片段、且按鈕式 AI 與白話文 widget 並存讓使用者困惑。

**修法（user 選「留統一 widget」）**：
- 刪除 `analyze_fund_json` 按鈕區、個股新聞面 AI、末端 `_render_tab2_ai_summary` 函式 → 「### ④ AI 深度解盤」單一 `render_ai_summary_widget(tab_key="tab2", tab_label="單一基金（…）", snapshot, headlines, gemini_api_key)`。
- **全章節快照 `_snap`**：基本(類別/幣別/淨值)＋績效(1m/3m/6m/1y/1y_total/ytd)＋風險1Y(σ/Sharpe/Alpha/Beta，取 `mj_raw.risk_metrics.risk_table.一年`)＋配息(年化率+筆數)＋買賣點/技術(buy1-3/bb/ma60)＋前10大持股(`_zh_holding`)＋產業配置＋持倉三率穿透(`shield_{fk}`)＋總經位階(`phase_info_s`)。
- **新聞**：優先逐股 `_stknews_{fund}`（v18.206，最多 15 則），無則退資產類別過濾廣義新聞（最多 8 則）。
- widget 本身自帶 `st.expander`，置於 ④ 區頂層（非巢狀）→ 不觸發 v18.156 巢狀 crash。

**清理**：移除 now-unused `from services.ai_service import (analyze_fund_json, event_impact_analysis)`（後者為 main 既有 dead import）。

**邊界**：無 GEMINI_KEY → 不渲染 AI 區；快照各段「有值才帶」（空段省略）；新聞兩來源皆空 → headlines=[]，widget 仍可生成。

**驗證**：AST PASS、ruff 與 main 同基準、`pytest -m "not slow"` 606 passed / 1 skipped、`test_tab2_single_fund.py` 5 passed、Tab2 AppTest 渲染。沙箱無 GEMINI_KEY 故 AI 分支不執行 → 逐一 grep 確認快照引用變數皆在 scope。

---

### §3-AP 個股新聞面升級：逐股 Google News 搜尋（v18.206 新增）

**問題**：v18.205 的「📰 個股新聞面」只**過濾既有廣義 RSS 新聞**（`filter_news_by_keywords`），對台股/債券/冷門持股難命中 → user 實際看到「命中持股 0 則」。

**修法（user 選「Google News 逐股搜尋」）**：
- 新接口 `news_repository.fetch_stock_news(query, max_items=3, lang="zh-TW", region="TW")`：用 **Google News RSS 搜尋**（`https://news.google.com/rss/search?q=<持股名>&hl=zh-TW&gl=TW&ceid=TW:zh`）走 `infra.proxy.fetch_url` 抓 bytes → feedparser 解析。中/英文持股名皆可、回該股近期新聞；失敗回 `[]`。
- Tab2 個股新聞面改 **按鈕觸發**：「📡 抓個股新聞」→ 對前 6 大持股（`_zh_holding` 中文名優先）逐一查（progress bar）→ 結果存 `st.session_state["_stknews_{fund}"]`（重整不重抓）→ 顯示真實個股新聞（標注持股/來源/連結）；命中時於 expander **外**（sibling，避 v18.156 巢狀 crash）掛 `render_ai_summary_widget(tab2_stknews)`。

**設計權衡**：逐股 = N 次網路呼叫 → 按鈕觸發（不自動拖慢頁面）+ session 快取 + top 6 限制；feedparser 解析 bytes（不裸連、走 proxy）。

**邊界**：空 query → []；Proxy 斷 / 抓取失敗 → [] + 友善提示；未抓 → 提示點按鈕；沙箱擋 Google → 抓取本身須真機/proxy 驗（解析邏輯以 mock feedparser 測）。

**驗證**：AST PASS、ruff clean、新增 4 test（解析 / 空 query / 抓取失敗 / max_items）、`pytest -m "not slow"` 606 passed / 1 skipped + Tab2 AppTest。

---

### §3-AO 單一基金「📰 個股新聞面」：持股名匹配新聞 + AI 新聞面分析（v18.205 新增）

**需求**：單一基金（Tab2）想多加「個股新聞面分析」，針對基金實際持有的個股。

**現況**：Tab2 的 AI 基金分析（v18.135）已做「持股×新聞」、AI summary widget（v18.196）依資產類別過濾——但都是**廣義財經新聞**，沒聚焦前10大持股。

**新接口**：`repositories/news_repository.py:filter_news_by_keywords(news, keywords)`——純過濾、回傳 title/summary 命中**任一**關鍵字者（case-insensitive）；**無 fallback**（不命中即回空，與 `filter_news_by_asset_class` 會回退全部刻意不同，避免顯示無關新聞）。

**Tab2 新區塊**（持股分析 expander 之後、indent 16）：
- 取前10大持股 `name`（英文）+ `_zh_holding(name)`（中文）+ 英文公司名首 token 當關鍵字。
- 比對**快取** `st.session_state["news_items"]`（Tab1 抓一次，**零額外網路**）。
- 「📰 個股新聞面」expander 列出命中的個股新聞（標注哪檔持股 + 來源 + 連結 + systemic 🚨）；不命中顯示友善「暫無相關個股新聞」。
- 命中時，在該 expander **之外**（sibling）掛 `render_ai_summary_widget(tab_key="tab2_stknews", ...)` 做 AI 新聞面分析——**刻意不放 expander 內**，因該 widget 本身是 expander，巢狀會觸發 v18.156 crash。

**邊界**：RSS 為廣義國際財經新聞 → 大型權值股（Apple/NVIDIA/台積電）命中率高、冷門/債券基金低 → 友善提示；零持股 → 不顯示區塊。

**驗證**：AST PASS、ruff clean、新增 3 test（命中任一 / 空 keywords / 無命中不 fallback）、`pytest -m "not slow"` 602 passed / 1 skipped + AppTest tab2。

---

### §3-AN 故事化 Tab1/Tab2 內部故事站標題（v18.204 新增）

**背景**：先前只有 Tab3 做完整內部故事站（v18.195）；Tab1/Tab2 只有頂部敘事麵包屑（v18.193）。本次補 Tab1/Tab2 的內部 `###` 故事站標題，使三個敘事 tab 一致（純加/改 markdown、零區塊搬移）。

**Tab2 單一基金**（success path 為 flat、indent 16，4 站，全新插入）：
- `### ① 基本資料 & 淨值趨勢`（淨值 success 卡前）
- `### ② 買賣點信號（標準差策略）`（MK 標準差買賣點前）
- `### ③ 風險指標 & 配息`（`col_a/col_b` 雙欄前）
- `### ④ AI 深度解盤`（AI 區 `st.divider()` 前）

**Tab1 總經**（內部有子分頁 `tab_main, tab_edu = st.tabs(...)`；戰情內容在 `with tab_main:` indent 12，3 站）：
- insert `### ① 總經位階評估`（tab_main 頂）
- **prefix 既有 header**（零風險、不新增節點）：`### ② 🎯 全域導航塔（戰情室）`、`### ③ 📡 景氣拐點監控`
- AI 解盤 widget 本身即「🤖 AI 白話文總結」expander，已是獨立章節，不另加

**刻意不做**：Tab1 的「資本防線/含息」「四大類別」等子段落深埋 `with col:` column layout → 在欄內塞 `###` 會被擠壓/不一致、且沙箱無法驗視覺 → 不硬塞。Tab5 資料診斷 / Tab6 說明書為工具/說明性質，不在「總經→配置→單一」敘事主線。

**驗證**：AST PASS、Tab1 3 站 / Tab2 4 站就位、`test_app_smoke + test_tab1_macro + test_tab2_single_fund` 105 passed、`pytest -m "not slow"` 599 passed / 1 skipped + AppTest。

---

### §3-AM 程式碼健康度：修 fund_repository 3 個潛伏 NameError/UnboundLocal（v18.203 新增）

**背景**（健康度清理）：ruff F821 掃 `repositories/fund_repository.py` 出多個「未定義名稱」。逐一查證**皆為潛伏 bug**——平時被 `and` 短路 / `try-except` / 從不觸發的 edge case 遮蔽，故 app 平時不發作，但特定情境會 NameError/UnboundLocalError。

**#1 缺 `import re`**：13 處 HTML 解析 `re.findall/search/sub`（L3358-4146，抓基金頁/三率）所在函式無 local `import re` → 被呼叫時 NameError → 解析靜默失敗、資料抓不全。修：模組層加 `import re`。

**#2 缺 `import requests`**：3 處 `requests.get(..., proxies=_proxies(), verify=_ssl_verify())`（L341/406/434）→ NameError → 落後續 fallback。修：模組層加 `import requests`（呼叫本就 proxy-aware，活化後即走 NAS proxy）。

**#3 `_is_insurance_code` use-before-assign**：`_fetch_fund_single()` 內，`nav<10` 短資料的 Morningstar/TDCC fallback（L2484+）引用 `_is_insurance_code`，但其賦值在 L2581（更後面）→ Python 視為 local → 短資料時 **UnboundLocalError**（正中「查無資料 / 新基金 / 抓取失敗」edge case）。修：提前到函式開頭（`_code` 設定後）計算一次、移除後段重複賦值。

**CI 註**：`test_app_apptest`（含 `test_tab3_kpi`）為 `@pytest.mark.slow` → **不在 pr-check fast lane**；其 yfinance 403「Host not in allowlist」是沙箱網路限制（GitHub Actions slow lane 有網路），非程式 bug、無需 mock。

**驗證**：AST PASS、ruff F821 fund_repository 13→**0**、correct-order import OK、新增 import-guard test、`pytest -m "not slow"` 598 passed / 1 skipped。

---

### §3-AL NAV 快取代碼自動彙整：self-heal + Sheet 選用同步（v18.202 新增）

**痛點**：`scripts/fetch_nav_cache.py`（GitHub Actions 每日抓 NAV 存 `cache/nav/{CODE}.json`）的 `FUND_CODES` 寫死 → 使用者新增基金時常忘了補 → 該基金無 cache → T5 相關係數矩陣 / 歷史 NAV 算不出。

**限制**：CI workflow `fetch_nav_cache.yml` 目前**無 Google Sheet 憑證**，無法直接全自動讀保單分頁。

**修法（務實、漸進）**：新增 `_discover_fund_codes()`，抓取目標代碼 = 三來源聯集：
1. 硬編碼 `FUND_CODES`（baseline）。
2. **既有 cache 檔（self-heal）**：掃 `cache/nav/*.json`（排除 `_` 開頭），一旦某代碼被快取過就持續刷新，即使被移出 `FUND_CODES`。
3. **Sheet（選用）**：`_codes_from_sheet()` 僅當 CI 提供 `GOOGLE_SERVICE_ACCOUNT_JSON` + `POLICY_SHEET_ID`（env）時，才 lazy import gspread 讀保單分頁 `fund_url` → 代碼；無憑證回空集合、零副作用。

**效益**：新基金一旦進過 cache 就不再漏；使用者日後在 CI 加 SA secret 即全自動從保單分頁同步、不需再改 code。

**邊界/相容**：無憑證 → 不 import gspread；Sheet 讀取失敗 → try/except 略過不擋；沙箱擋 MoneyDJ/Yahoo 403 → 抓取本身仍須真機/CI 跑（本次只驗代碼彙整純邏輯）。

**驗證**：AST PASS、新增 `test_fetch_nav_cache.py` 2 test（無憑證 Sheet 略過 / self-heal+baseline 彙整）、`pytest -m "not slow"` 598 passed / 1 skipped。

---

### §3-AK yfinance 走 proxy：FX/NAV 改打 Yahoo Chart API（v18.201 新增）

**動機**（v5.0 spec Task1「所有對外 API 強制套用 nas_proxy」）：稽核發現 `repositories/fund_repository.py` 的 `get_latest_fx`（`USDTWD=X`）與 `get_latest_nav`（基金 NAV）**直連 `yf.Ticker`、未走 proxy** → Streamlit Cloud IP 被 Yahoo 擋（`403 Host not in allowlist`）/ 限流（AppTest `test_tab3_with_mock_fund_renders_kpi_cards` 的 0050/USDTWD=X 403 即此）。總經層（macro_repository / macro_service / tw_macro）早已避開 yfinance、改打 Yahoo Chart REST API 經 proxy。

**修法（user 選「Chart API 走 proxy」）**：FX/NAV 的 `yf.Ticker` 區塊 → 改用既有且驗證可行的 `macro_repository.fetch_yf_close(ticker, range_, interval)`（Yahoo Chart REST API + `infra.proxy.fetch_url` + timeout + 10min TTL），取最後一筆收盤；**lazy import 避免循環依賴**；既有 Morningstar/Cnyes fallback 鏈完全保留。

**未動**：`financial_repository.fetch_stock_three_ratios`（個股季財報）無 Chart API 對應，yfinance 失敗已回 None 優雅降級 → 維持。

**邊界**：sandbox 無 proxy 設定 + Yahoo 全擋 → Chart API 仍 403（AppTest test_tab3_kpi 續紅、屬環境非程式）；真機有 NAS proxy → 走台灣 IP 出口穩定。FX/NAV 失敗仍 fallback/None 不崩。

**驗證**：AST PASS、correct-order import 無循環、新增 guard test（fund_repository 無 `yf.Ticker`、FX/NAV 走 `fetch_yf_close`）、`pytest -m "not slow"` 596 passed / 1 skipped。

---

### §3-AJ 429 治本：load_all_policy_worksheets open 一次（v18.200 新增）

**承 v18.199**（429 緩解：友善訊息 + 砍 cloud_io 重複 list）。本次真正治本：減少讀取數。

**舊讀取模式**：`load_all_policy_worksheets` 先 `list_policy_worksheets`（open_by_key + worksheets = 2 讀）→ 再對每個 tab 呼叫 `load_policy_worksheet`（**每分頁又 open_by_key + worksheet + get_all_records ≈ 3 讀**）→ N 保單 ≈ **2 + 3N** 讀。`open_by_key` 本身就是一次 read，是配額大戶。

**重構**：
1. 抽出 `_records_to_policy_df(records)`：gspread records → 正規化 + 鬼列過濾的 DataFrame，由 `load_policy_worksheet`（單分頁）與 `load_all_policy_worksheets` 共用（DRY）。
2. `load_all_policy_worksheets` 改 **`open_by_key` 一次 → `sh.worksheets()` 一次拿到所有分頁物件**（同時當「清單」與「讀取 handle」）→ 逐物件 `get_all_records`。讀取數降到 ≈ **2 + N**（4 保單 14→6）。
3. 所有 gspread 呼叫包 `_with_quota_retry`（open/worksheets/get_all_records）。

**綜效**：配合 v18.199（砍 cloud_io 重複 `list_policy_worksheets`），一次切換的 `load_all_from_sheet` 讀取數約 **18 → 8**（4 保單），正常切換可穩在 60 reads/min 配額內；仍超載時 v18.199 友善提示接手。

**驗證**：AST PASS、ruff clean、mock `_make_sh_with_worksheets` 改回真 ws 物件（worksheets() 帶 title）、`test_policy_store` 85 + `pytest -m "not slow"` 595 passed / 1 skipped 零回歸。

---

### §3-AI 修「切換/重讀帳本」429 Quota exceeded（v18.199 新增）

**問題場景**（user）：有資料後重新讀取另一個帳本 → `❌ Sheet 操作失敗：列 worksheets 失敗：APIError [429] Quota exceeded ... 'Read requests per minute per user'`。

**根因**：Google Sheets 每 user 每分鐘 60 reads。切換帳本會觸發 v18.185 auto-load + 使用者手動「全部讀回」各跑一次 `load_all_from_sheet`，每次包含多次 `open_by_key` + `list worksheets` + per-policy `get_all_records` + `_T7_State` 讀取，短時間爆配額；`_with_quota_retry`（1+2+4+8=15s 退避）救不回硬性超額。

**修法**：
1. **砍重複讀取**：`load_all_from_sheet` 原本在 `load_all_policy_worksheets`（內部已 list worksheets）之外，又額外呼叫 `list_policy_worksheets` 一次設 `policy_tabs` → 改從已讀回的 DataFrame 的 `policy_id` 欄推導 `policy_tabs`，省一次 `open_by_key` + `worksheets`。
2. **友善 429**：外層 except 偵測 `_is_quota_error` → 顯示「⏳ Google Sheets 讀取配額暫時超載（每分鐘上限），等 30~60 秒再按『立即全部讀回』（資料沒壞）」取代 raw APIError 紅字。

**後續（真正治本，需真機驗）**：`load_all_policy_worksheets` 改「`open_by_key` 一次、重用 spreadsheet handle 讀各分頁」省掉 N 次 open（最大讀取來源）；或對讀取結果加短 TTL 快取。

**驗證**：AST PASS、ruff clean、改 5 test（移除 cloud_io `list_policy_worksheets` mock、`policy_tabs` 改從 DataFrame 推）、`pytest -m "not slow"` 595 passed / 1 skipped。

---

### §3-AH 保單分頁「存全」：avg_nav/fx_avg/units 加進 schema（v18.198 新增）

**痛點**（user 反覆回報「存檔資料沒有全部」）：v1 保單分頁只存 invest_twd / 含息成本 / 現金給付%，**缺平均買入淨值（avg_nav）/ 平均買入匯率（fx_avg）/ 持有單位數（units）**——這三個成本基礎原本只在 `_T7_State`（機器 JSON blob）與 `_持倉總覽`。v18.191 只補了讀取端（用帳本回填記憶體），寫入端的保單分頁仍半套。

**Schema**：`OPTIONAL_COLS` 尾端純追加 `avg_nav` / `fx_avg` / `units`（`ALL_COLS` 11→14）。`upsert_fund_in_policy` 表頭升級範圍自動由 A1:K1 → A1:N1；既有 11 欄表頭下次 upsert 自動升級、舊資料列尾端補空不錯位（同 v18.183 模式）。

**寫入**（成本基礎權威來源 = 帳本）：`dump_all_to_sheet`（全部寫入）與 T7「套用起始部位」upsert 兩路徑，`avg_nav/fx_avg/units` **優先取 `t7_ledgers[pk].position`（cost_unit/fx_avg/units），缺則退 portfolio_funds**。T7 表單 submit 也把 `_cu/_fx/_u` 寫進 `portfolio_funds`（供 dump + JSON 一致）。

**讀回**：`sync_policies_to_portfolio_funds` 把三欄讀回 `portfolio_funds`（**有值才帶、空欄不覆蓋記憶體**），配合 v18.191 reconcile（帳本回填）成讀取端雙保險。

**相容**：既有 test 用 `list(ALL_COLS)`/`len(ALL_COLS)` 動態斷言 → 自動相容；`upsert_policy_row`（legacy 單表）仍只寫「表頭交集」不強制升級（向後相容）。

**驗證**：AST PASS、ruff clean、新增 3 test、`pytest -m "not slow"` 595 passed / 1 skipped + AppTest。

---

### §3-AG hotfix「全部讀回」ValueError + v5.0 收尾驗收（v18.197 新增）

**user 阻斷 bug**：按「立即全部讀回」→ `❌ [ValueError] The truth value of a Series is ambiguous`，讀取整個失敗。

**根因**（v18.185 潛伏）：`reuse_fund_info_by_code`（`ui/helpers/portfolio_load.py`）用 `if v not in (None, "")` 過濾要沿用的欄位，但 `_FUND_INFO_KEYS` 含 `series`（pandas Series）。`Series == None`／`Series == ""` 回傳的是 Series，`in`/`bool()` 對 Series 做真值判斷即拋 ValueError。v18.185 的單元測試用 `list` 當 `series`，沒測到真 Series → 漏網。

**Fix**：逐欄安全判斷 —
```python
if k not in src: continue
v = src[k]
if v is None: continue
if isinstance(v, str) and v == "": continue   # 只保護字串空值（如 currency）
entry[k] = v                                    # series/dict/list 直接複製
```
新增 `test_reuse_handles_pandas_series_value`（真 `pd.Series` 不拋錯）。

**v5.0 收尾驗收**：跑完整 `pytest -m "not slow"`，抓到 2 個與本次無關的潛伏失敗 —`test_tab6_manual` 仍假設 8 sub-tabs，但 Tab6 早已 10 個（v18.169 第 9、v18.174 第 10）→ 修 test：expect 10 + mock `range(10)` + 補 2 標題關鍵字。

**驗證**：`pytest -m "not slow"` 全綠 **592 passed / 1 skipped**；AppTest 14 passed（1 為 sandbox yfinance 403 環境問題）。

---

### §3-AF Task3 AI 解盤補完：fetch_macro_news(asset_class) + 新聞依資產類別（v18.196 新增）

**目標**（v5.0 Task3）：spec 要的「`fetch_macro_news(asset_class)` 接口 + 每 Tab AI 解盤接該資產類別新聞」。釐清：AI 解盤 widget（`render_ai_summary_widget`）早已在 Tab1/2/3，本次補的是**分類接口** + **新聞依該 Tab 資產類別過濾**。

**新接口**（`repositories/news_repository.py`）：
- `ASSET_CLASS_KEYWORDS`：stock / bond / fx / commodity / macro（macro=不過濾）。
- `infer_asset_class(text)`：從基金名稱/類別字串推類別（偵測序 bond→stock→commodity→fx；多重資產/無法判別→macro）。
- `filter_news_by_asset_class(news, asset_class)`：**純過濾既有清單、零網路**；systemic 永遠保留；過濾後空→回原清單；macro/未知→不過濾；吃中文別名（股/債/匯/原物料/總經）。
- `fetch_macro_news(asset_class="", max_per_feed=5)`：spec 接口 = `fetch_market_news` + `filter_news_by_asset_class`。

**接線（關鍵：用快取、不在 render 路徑重抓 RSS）**：
- Tab2 `_render_tab2_ai_summary`：`infer_asset_class(基金名+類別)` → `filter_news_by_asset_class(session_state.news_items, cls)` 當 AI「新聞連動」headlines。
- Tab3 `_render_tab3_ai_summary`：統計 loaded 各檔類別取最多數（混合→macro）→ 同樣過濾快取新聞。
- Tab1：本身即總經 → macro（全部新聞），無需改。

**效能**：UI 端只過濾已快取的 `news_items`（Tab1 抓一次），不重打網路；`fetch_macro_news` 僅供需主動抓取的場景。

**驗證**：AST PASS、ruff clean、新增 6 test、114 PASSED 零回歸 + AppTest。

---

### §3-AE Task2.2-step2b 組合 Tab 故事站標題（v18.195 新增）

**發現（先讀 code，不盲搬）**：(1) 配置總覽核心（組合健康儀表 + 策略3 戰情室）**已在 Tab 頂部**（L154-193，loaded 時顯示）；(2) 自動讀回埋在頂部 Google-Sheets expander（L266），Streamlit 由上而下執行 → 中段顯示區塊**不能**搬到比該 expander 更高（否則首次 render 空白）；(3) 區段未乾淨切分（plumbing 與內容交錯）。故大區塊搬移風險高、報酬低、且沙箱無法驗證畫面。

**方案（user 選「加故事站標題」）**：不搬大區塊，只在既有結構加 4 個 `###` 故事站標題，把「由上而下一條故事線」明確標示出來、呼應頂部 tab 麵包屑：
- ① 📊 配置總覽 — 你的組合現況（KPI/成長/核心衛星圈之前，gated `if _pf_loaded`）
- ② ➕ 加入與管理基金（手動加入 expander 之前）
- ③ 💼 持倉戰情（T7 帳本）（`render_t7_section()` 之前）
- ④ 🔬 持股重疊度診斷（T5）（沿用原 T5 header 改名）

**安全**：純 markdown 加/改、**零區塊搬移、零變數變動**；各 header 縮排正確（① 在 `if _pf_loaded`、②③ base indent、④ 在 `if _t5_groups`）、非巢狀於 expander。**效能**：O(1)。

**後續**：若 user 部署後想調整某區塊順序，指定「把 X 搬到 Y 之前」→ 做精確、可驗證的單一搬移（而非盲搬）。

**驗證**：AST PASS、4 標題就位、99 PASSED（含 full app.py exec）+ AppTest。

---

### §3-AD Task2.2-step2a 組合 Tab 內部故事線：T7 移到 T5 之前（v18.194 新增）

**目標**：組合 Tab 內部由上而下理成「① 配置總覽 → ② 加入/載入 → ③ 持倉戰情(T7) → ④ 重疊診斷(T5)」。

**本次（step2a，最安全一步）**：`render_portfolio_tab()` 原順序「收益矩陣 → **T5 重疊診斷 → T7 持倉帳本** → AI」——持倉(③) 竟排在診斷(④) 之後。把 `render_t7_section()` 從 T5 之後移到 **T5 之前**：「收益矩陣 → **T7 → T5** → AI」。

**為何安全**（先以 Explore 對整個 ~2000 行函式做 section + 依賴 mapping）：
- Streamlit 由上而下執行 → 載入/計算必須在顯示之前。T7 為**自含函式呼叫**（`ui/tab3_t7_ledger.render_t7_section()`，內部讀 `st.session_state`），且置於所有「載入 / 加入 / 批次」區塊（L1425–1793）之後 → portfolio_funds / t7_ledgers 已齊全。
- T5 用區塊內自建的 `_pf_for_corr_raw` / `_t5_groups` + series，與 T7 的 invest_twd sync 無關 → 互換零 use-before-define / NameError 風險；`render_t7_section()` 全檔僅 1 處呼叫。

**延後（step2b，需 user 視覺回饋）**：把「配置總覽（核心/衛星 hero + KPI + 成長曲線）」上移到最前，牽涉搬動多個 ~100 行 DISPLAY 區塊、沙箱無法驗證畫面。

**驗證**：AST PASS、ruff F-check clean、`render_t7_section` 1 呼叫、99 PASSED（含 full app.py exec）+ AppTest。

---

### §3-AC Task2.2-step1 故事化動線：tab 重排 + 敘事導覽列（v18.193 新增）

**目標**（v5.0 Task2「故事化排版」）：讓使用者順著「全球總經環境 → 核心/衛星資產配置 → 單一基金深掘」閱讀。此重構偏視覺、沙箱無法驗證畫面 → **分階段**；本次做最高槓桿/低風險的 step1，tab 內部區塊重排留作逐 tab 後續（需 user 視覺回饋）。

**tab 重排**（`app.py`）：`st.tabs` 由 `🌐 總經 → 🔍 單一基金 → 📊 組合基金 → …` 改為 **`🌐 總經 → 📊 組合基金 → 🔍 單一基金 → 🔬 資料診斷 → 📖 說明書`**（原本單一基金在組合之前，違反敘事順序）。變數改語意名 `tab_macro/tab_portfolio/tab_single`，with-block 依敘事順序排列；**render 函式完全不動**。確認無任何 test 以 tab index 取用、smoke 全 exec app.py 通過。

**敘事導覽列**：新增 `ui/helpers/story_nav.py`：
- `story_nav_markdown(current)` 純函式（組麵包屑、目前站 `**:blue[]**` highlight + 一句話提示、其餘 `:gray[]`、無效 key 不 highlight）→ 可單元測試。
- `render_story_nav(current)` 在三敘事 tab 標題下以 `st.caption` 渲染（無效 key 不渲染）。

**邊界**：無效 current → 不渲染；色彩 markdown 不支援時退純文字。**效能**：純靜態 O(1)。

**驗證**：AST PASS、ruff clean、新增 4 test、99 PASSED（含 full app.py exec）+ AppTest 渲染。

---

### §3-AB Task2.1 教學化：量化指標白話文 expander（v18.192 新增）

**目標**（v5.0 Task2「新手視角，老手深度」）：複雜量化指標旁加 `st.expander("💡 這些數據代表什麼？")`，用白話文解釋指標 + 資產配置實戰意義；**不隱藏、不移動任何既有專業數據**（純加法、收合預設）。

**集中收口**：新增 `ui/helpers/metric_explainers.py`：
- `METRIC_EXPLAINERS` dict（8 條：`sharpe`/`sigma`/`alpha`/`beta`/`mdd`/`core_satellite`/`div_coverage`/`overlap`），每條含 title + body（白話 + 實戰怎麼用）。
- `explainer_markdown(keys)` 純函式（組 markdown、未知 key 略過、空輸入回空）→ 可單元測試、不依賴 streamlit。
- `render_metric_explainer(keys, title=...)` 渲染收合 `st.expander`；無內容不渲染、不佔版面。

**接線點**：
- Tab2 `風險指標` col_a（波動σ/Sharpe/Alpha/Beta）下方 → `["sharpe","sigma","alpha","beta"]`。
- Tab3 `核心/衛星` Hero 下方 → `["core_satellite","div_coverage"]`。

**邊界/防呆**：(1) keys 空或全未知 → 不渲染；(2) 指標值缺/"—" 不影響（explainer 只講概念、不吃實際值）；(3) 兩 call site 經查皆非在 `st.expander`/`st.status` 內 → 不觸發 v18.156 巢狀 crash。**效能**：純靜態文案、O(k) 組字串，無需快取。

**驗證**：AST PASS、ruff clean、新增 5 test、109 PASSED（+ AppTest 渲染）。

---

### §3-AA 讀取齊全：讀回/還原時用帳本補齊 portfolio_funds（v18.191 新增）

**症狀**（user）：「讀取資料時帳本一直缺資料，只要讀取齊全就好」。

**以 user 實際 JSON 備份驗證**：`portfolio_funds`(19) 與 `t7_ledgers`(19) 的 pk **100% 對得上**，`Ledger.from_dict` 19/19 解析成功且含完整成本（units/cost_unit/fx_avg/cost_unit_with_div）→ **JSON 還原本身是齊全的**。缺料出在 **Sheet 讀回**：T7 表單與帳本表都以 `portfolio_funds` 為主軸（spine）迭代、再用 `fund_pk_str(f)` 去 `t7_ledgers` 取成本基礎。當保單分頁（→portfolio_funds）與 `_T7_State`（→t7_ledgers）內容漂移時，只存在於快照的基金會「看不到」。

**修法**：新增純函式 `ui/helpers/portfolio_load.py:reconcile_funds_with_ledgers(funds, t7_ledgers)`：
1. 帳本有、但 portfolio_funds 沒有的部位 → 用 `parse_pk` 還原 (policy_id, code) 補成 spine 條目（`loaded=False`），確保帳本每一檔都迭代得到。
2. 回填成本基礎 `avg_nav`/`fx_avg`/`units`/`avg_nav_with_div`（**缺值才補、不覆蓋使用者既有設定**）。

接兩條讀取路徑：`load_all_from_sheet`（`_T7_State` 讀回後，report 加 `reconciled_added`）與 `restore_from_json_bytes`（JSON 還原後）。

**實證**：模擬 Sheet 漂移（保單分頁只回 5/19）→ reconcile 後補回 14 檔、19 檔全有 spine + 完整成本。

**驗證**：AST PASS、ruff clean、新增 4 test、132 PASSED 零回歸。

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

---

## §16 總經五桶 × 危險門檻一覽（`shared/macro_buckets.py` SSOT）

> v19.144。Fund 端「總經五桶」危險門檻系統的單一參考表 — 與 Stock 端 SPEC §11 結構對齊,
> 但桶配置不同(Fund 視角:`拐點` 取代 Stock 的 `籌碼`、加 `📰 新聞`)。
> 桶燈號、未來圖表上的黃/紅標準線、本表三者**同源** — 全部讀
> `shared/macro_buckets.py::BUCKET_DANGER_SPECS`,改門檻只改一處。

**門檻來源透明度**（`DangerSpec.source`）:
- 🔵 **官方 / SSOT**:有既有常數背書(`MACRO_THRESHOLDS` 鏡像由 `tests/test_macro_buckets.py` 守漂移;或直接 import `signal_thresholds`)。
- ⚪ **系統設計**:本桶為 UI 判讀方便自訂之警示線(具名 + 文件化,§1 不適用 — 此為 UI 門檻 config,非偽造資料輸出)。

**方向**:`high_bad` = 值越高越危險｜`low_bad` = 值越低越危險｜`band` = 兩端皆危險。

### 🌳 長期（結構 / 景氣位階）
| 指標 | 單位 | 🟢 綠 | 🟡 黃線 | 🔴 紅線 | 方向 | 來源 |
|---|---|---|---|---|---|---|
| 總經健康評分 | /10 | ≥6 | 3–6 | <3 | low_bad | 🔵 macro_validation.aggregate_score |
| M2 貨幣供給 YoY | % | >5 寬鬆 | 0–5 | <0 緊縮 | low_bad | 🔵 MACRO_THRESHOLDS.M2_YOY |
| Fed 資產負債表 YoY | % | >5 擴表 | −5–5 | <−5 縮表 | low_bad | 🔵 MACRO_THRESHOLDS.FED_BS_YOY |

### 📈 中期（景氣循環 3-12 月）
| 指標 | 單位 | 🟢 綠 | 🟡 黃線 | 🔴 紅線 | 方向 | 來源 |
|---|---|---|---|---|---|---|
| ISM 製造業 PMI | — | >50 | 46–50 收縮 | <46 嚴重 | low_bad | 🔵 MACRO_THRESHOLDS.PMI |
| CPI YoY | % | <3.5 | 3.5–4.0 | ≥4 嚴峻 | high_bad | 🔵 MACRO_THRESHOLDS.CPI |
| 失業率 | % | <4.5 | 4.5–6 | ≥6 衰退 | high_bad | 🔵 SCORE_RULES.UNEMPLOYMENT |
| US10Y 殖利率 | % | <4.5 | 4.5–5 | ≥5 緊縮 | high_bad | 🔵 MACRO_THRESHOLDS.US10Y |
| Forward P/E | 倍 | <19.5(+1σ) | 19.5–22.5 | ≥22.5(+2σ) | high_bad | 🔵 valuation.FORWARD_PE_MEAN+σ |

### 🎯 短線急殺（即時 risk-off）
| 指標 | 單位 | 🟢 綠 | 🟡 黃線 | 🔴 紅線 | 方向 | 來源 |
|---|---|---|---|---|---|---|
| VIX 恐慌指數 | — | <22 | 22–30 | ≥30 危機 | high_bad | 🔵 MACRO_THRESHOLDS.VIX + macro_validation |
| HY 信用利差 OAS | % | <4 | 4–6 | ≥6 信用裂 | high_bad | 🔵 MACRO_THRESHOLDS.HY_SPREAD |
| MOVE 債市波動 | — | <100 | 100–120 | ≥120 stress | high_bad | ⚪ 對齊 macro_beginner_view._MOVE_WARNING |
| Put/Call 比率 | — | <1.0 | 1.0–1.5 | ≥1.5 散戶恐慌 | high_bad | ⚪ 對齊 macro_beginner_view._PCR_PANIC |

### ⚠️ 拐點（領先警報）
| 指標 | 單位 | 🟢 綠 | 🟡 黃線 | 🔴 紅線 | 方向 | 來源 |
|---|---|---|---|---|---|---|
| Sahm Rule | — | <0.3 | 0.3–0.5 | ≥0.5 觸發 | high_bad | 🔵 SAHM_RECESSION_THRESHOLD(0.5) + ⚪ 0.3 警戒 |
| 10Y-2Y 殖利率差 | % | >0.5 | 0–0.5 接近倒掛 | ≤0 倒掛 | low_bad | 🔵 MACRO_THRESHOLDS.YIELD_10Y2Y |
| 10Y-3M 殖利率差 | % | >0.5 | 0–0.5 接近倒掛 | ≤0 倒掛 | low_bad | 🔵 MACRO_THRESHOLDS.YIELD_10Y3M |
| CFNAI 領先指標 | — | >−0.35 | −0.7–−0.35 走弱 | ≤−0.7 衰退 | low_bad | 🔵 CFNAI_RECESSION_THRESHOLD(−0.7) + ⚪ −0.35 警戒 |
| SLOOS 銀行收緊 | % | <30 | 30–50 | ≥50 衰退級緊縮 | high_bad | ⚪ 對齊 macro_beginner_view._SLOOS_TIGHTENING |

### 📰 新聞（系統性風險掃描）
| 指標 | 單位 | 🟢 綠 | 🟡 黃線 | 🔴 紅線 | 方向 | 來源 |
|---|---|---|---|---|---|---|
| 系統性風險新聞數 | 則 | 0 | 1 | ≥2(戰爭/倒閉/崩盤關鍵字命中) | high_bad | ⚪ 命中則數規則(對齊 news_repository.SYSTEMIC_RISK_KEYWORDS)|

> 桶燈號 = 該桶所有指標分級取**最危險者**(紅 > 黃 > 綠 > 灰未載入)。
> 第 5 桶 📰 新聞需 Tab1 已抓 RSS(news_items session_state) 才有資料;未抓時 ⬜(§1 Fail Loud,不偽綠)。
>
> **與既有 4-horizon bar 的關係**:本表為 SSOT 危險門檻參考。`ui/helpers/macro_beginner_view.compute_four_horizon_summary`
> 仍為 production 四時域 bar(已運作),不破壞既有體驗。Phase B 將把 SSOT 套到 chart `add_danger_hlines`
> 視覺化危險距離,Phase C 視 user 反饋決定是否擴至 5 桶 bar。

### §16.1 VIX 全站 SSOT 統一(C2 series v19.157~v19.160 結案)

**歷史脈絡**:v19.147 曾以 "Multi-cutoff Design" 為 4 個 VIX yellow 值散落(18/20/22/25)
做合理化辯護,標 F-GRAY-4「✅ 結案」(不機械式統一)。
**2026-06-26 user 改變主意**,接受 trade-off(雷達日均閃黃 / 長期評分敏感度降 4 點 /
教學前置語意喪失 2 點 / calibration JSON 重定 bound),拍板 C2 series 全面 SSOT 收斂。

**現況(C2 完成後)**:Fund 端 VIX yellow 全站統一 **22**(`shared/macro_buckets._VIX_YELLOW`),
panic 全站統一 **30**(`_VIX_RED`)。

| 模組 | VIX yellow | VIX panic | 版本 |
|---|---|---|---|
| `shared/macro_buckets._VIX_YELLOW / _VIX_RED`(SSOT) | **22** | **30** | 鏡像 `MACRO_THRESHOLDS.VIX` |
| `services/macro_validation.DEFAULT_VIX_WARNING / _CRISIS` | **22** | **30** | C2-C v19.159(原 18 / 30) |
| `ui/helpers/macro_beginner_view._VIX_WARNING_THRESHOLD / _PANIC_THRESHOLD` | **22** | **30** | C2-B v19.158(原 20 / 30) |
| `services/risk_radar.py::_signal_vix_level` | **22**(via `_VIX_YELLOW`) | **30**(via `_VIX_RED`) | C2-A v19.157(原 25 / 30) |
| `services/macro_service.py` alert(`indicators[VIX] > _MB_VIX_YELLOW`) | **22** | — | C2-D v19.160(原 inline `> 25`) |

**HY spread 保留 intentional spread**(C2 不一併收):
- SSOT 黃線 **4**(`_HY_YELLOW`,`MACRO_THRESHOLDS.HY_SPREAD.green_below`)
- `macro_beginner_view._HY_SPREAD_WARN_THRESHOLD = 5`(教學保守)
- HY 屬慢速信用指標,提前預警 ROI 仍在;`test_hy_yellow_intentional_spread` 守。

**Calibration JSON 機制改動**(C2-C):
- `data_cache/macro_thresholds_global.json` 載入 bound 重定:`warning ∈ [14, 22]` → `[18, 26]`(對齊 SSOT 22 重心 ±4)
- `scripts/calibrate_macro_score.py` grid `[14, 16, 18, 20, 22]` → `[18, 20, 22, 24, 26]`
- 既有 JSON 校準到舊 `[14, 18)` 區 → silently fallback 至 SSOT 22(intended)
- repo 內無 production calibration JSON → 本次 deploy 無實際 fallback 觸發

**C2 series 步驟總表**:
- ✅ C2-A v19.157:`risk_radar._signal_vix_level` 25 → 22(import `_VIX_YELLOW`)
- ✅ C2-B v19.158:`macro_beginner_view._VIX_WARNING_THRESHOLD` 20 → 22
- ✅ C2-C v19.159:`macro_validation.DEFAULT_VIX_WARNING` 18 → 22 + calibration bounds 重定
- ✅ C2-D v19.160:本段 SPEC §16.1 改寫 + `macro_service.py` alert inline 25 → SSOT + CLAUDE.md F-GRAY-4 結案標記

**User-facing 影響總覽**:
1. **雷達**:`VIX ∈ [22, 25]` 區間會比舊版多閃黃(日均增 0~2 次,依市場波動)
2. **macro_validation 評分**:VIX 18~22 不再扣 -1.0(改 0.0 中性);≥22 才扣分
3. **macro_service alert**:VIX > 22 觸發 "市場恐慌升溫" 提示(原 > 25)
4. **教學卡片 + 五桶 bar + SPEC §16 表**:統一 22 顯示,user 不再有「教學黃但雷達綠」的認知衝突
5. **panic = 30** 全站不變

**守護**:`tests/test_cross_site_cutoffs.py`
- `test_vix_yellow_all_aligned_to_ssot`:3 site warning 全 22 + 全員一致
- `test_vix_panic_universal_30`:3 site panic 全 30
- `test_risk_radar_vix_source_uses_ssot`:risk_radar 必須 import `_VIX_YELLOW`/`_VIX_RED`,不可 inline 25

### §16.2 PMI / CPI / HY 多用途閾值 harmonize architecture proposal(F-GRAY-4 收尾,v19.168)

**背景**(F-GRAY-4 v19.80 audit 結論,CLAUDE.md §8.3):
- VIX 子題 v19.157~v19.160 已收(本檔 §16.1),全站 yellow=22 / panic=30 統一
- **其他指標**(PMI / CPI / HY_SPREAD 等)語意分歧,**不**一併 harmonize,需 architecture proposal

**問題**:
單一 `MACRO_THRESHOLDS` dict(`macro_repository.py:192`)為 stoplight schema(red/yellow/green 三級),
但 inline 閾值服務多種用途:
- **Signal classification**(`macro_validation.py`):買賣訊號觸發
- **Score function**(`macro_service.py`):0-10 連續分數
- **Regime ID**(`macro_explain.py`):衰退/復甦/擴張/高峰 4 級
- **Inflection detection**(`crisis_backtest.py`):拐點觸發

**範例**(PMI 為主):
| Site | 用途 | 閾值 | 業務語意 |
|---|---|---|---|
| dict | stoplight | green=52 / yellow<50 / red<46 | 純三級顏色 |
| `macro_service.py:324` | score | `>= 50` 中性,`>=52` 加分 | 連續 score 用 |
| `macro_explain.py` | regime | `< 47` 衰退 | 4 級分類 |
| 教學卡 | 教學 | `<50 收縮 ≥50 擴張` | 50 為唯一榮枯線 |

機械式 swap 會把 4 個語意不同的 path 強塞進同一 `red/yellow/green` 三槽,破壞 score function 連續性、regime 4 級分類等。

**Proposal**:**Multi-purpose threshold dict architecture**

```python
# shared/macro_thresholds_v2.py (新檔,設計案)
PMI_THRESHOLDS = {
    "stoplight": {              # 原 dict 用途(三級紅黃綠)
        "green_above": 52,
        "yellow_below": 50,
        "red_below": 46,
    },
    "score_function": {         # macro_service.py 連續 score
        "expansion_floor": 52,  # >= 52 加分
        "neutral_floor": 50,    # 50-52 中性
        "contraction_ceiling": 50,
    },
    "regime_classification": {  # macro_explain.py 4 級
        "expansion": 52,
        "neutral": 50,
        "slowdown": 47,
        "recession": 45,
    },
    "inflection_detection": {   # crisis_backtest 拐點
        "expansion_to_slowdown": 50,
        "slowdown_to_recession": 47,
    },
}
```

各 site 改 import 對應子 dict,**不**共用單一閾值,但所有閾值集中於 SSOT 檔。

**Migration phases**(per indicator):
1. **Phase 1 audit**:gather all inline thresholds for the indicator across all sites
2. **Phase 2 design**:列出每個 site 的用途、依現有實際閾值定義 sub-dict shape
3. **Phase 3 build**:在 `shared/macro_thresholds_v2.py` 加 SSOT 子 dict
4. **Phase 4 migrate**:逐 site 改 import + 驗證行為 100% 等價(對照 test 守)
5. **Phase 5 守護**:加 `tests/test_macro_thresholds_v2.py` 守 SSOT 完整性

**Out-of-scope of this proposal**:
- 改變任何 inline 閾值的數值(只搬位置,不改邏輯)
- 將不同 site 的相同指標**強制**收斂到單一閾值(VIX 為 exception,user 接受 trade-off;PMI/CPI/HY 不接受)

**ROI 評估**:
| 指標 | inline 散落量 | 用途數 | migration cost | risk |
|---|---|---|---|---|
| PMI | ~8 處 | 4 用途 | 中 | 中(若 inline 漏抓 → 行為飄移) |
| CPI | ~5 處 | 3 用途 | 中 | 中 |
| HY_SPREAD | ~4 處 | 2 用途 | 低 | 低 |

**建議優先順序**:HY_SPREAD(最少語意,最低風險)→ CPI → PMI

**目前狀態**(v19.245 R13 復查):**proposal 已大幅落地** — `shared/macro_thresholds_v2.py` 已建立 5 SSOT(`HY_SPREAD_THRESHOLDS` / `CPI_YOY_THRESHOLDS` / `PMI_THRESHOLDS` / `FED_BS_THRESHOLDS` / `TW_PMI_THRESHOLDS`),13 consumer files 已接入(`v19.169` HY+CPI / `v19.178` CPI v2 進階 / `v19.179` PMI / `v19.184` M2+FedBS / `v19.245` HY inflection 收口)。剩餘 Tier 2/3 inline(`services/calibration/risk.py` synthetic data;`scripts/` calibration)為**模擬/校準資料,不影響 production 邏輯**,§-1 等實際 bug 觸發再加。

**§-1 對齊**:本 proposal 純文件,**不**自動觸發實作。user 明確指派某指標 → 才動工。

---

## §17 MK 老師吃本金檢查 SSOT(v19.148→v19.149)

### §17.1 方法論

依郭俊宏(MK)老師體檢邏輯:

> **近一年含息總報酬率 < 年化配息率 → 🔴 吃本金**

「含息總報酬率」採 MK 嚴格定義(教學版,**單利**):

```
含息_1Y = NAV 漲跌幅% + 累計配息率%
       = (NAV_now − NAV_1Y_ago) / NAV_1Y_ago × 100
       + Σ(divs in last 1Y) / NAV_1Y_ago × 100
```

### §17.2 SSOT 入口與優先序

`services/fund_dividend_health.check_eating_principal_1y_mk(fund)` 為**跨 tab 唯一 SSOT 入口**。

**含息報酬(tr1y)precedence**(v19.149):
1. 🥇 **MK 嚴格單利**:`compute_1y_total_return_mk_simple(series, dividends)` — 從 fund 內 raw NAV + 配息 list 直算,符合教學版定義
2. 🥈 業界複利 fallback:`metrics.ret_1y_total`(本地還原淨值法)→ `metrics.ret_1y`(純 NAV)— 當 fund 內缺 raw data 才用

**年化配息率(adr)precedence**:
1. 🥇 `moneydj_div_yield`(MoneyDJ wb05 官方)
2. 🥈 `metrics.annual_div_rate`(本地估算)

返回 dict 含 `_tr1y_method` 標記用了哪條路(`"mk_simple"` / `"metrics_fallback"`)。

### §17.3 MK 單利 vs 業界複利的差異

| 指標 | MK 單利(本系統 SSOT) | MoneyDJ wb01 / 還原淨值法(業界) |
|---|---|---|
| 公式 | NAV 漲跌 + 累計配息率(加法) | (Adj_NAV_end / Adj_NAV_start − 1) 配息再投資複利 |
| 與教科書符合 | ✅ 100% | ⚠️ 不同(複利) |
| 通常差異 | — | 通常 **高 5-15%**(複利 reinvestment 效應) |
| Verdict flip 風險 | — | borderline 基金(coverage 接近 1.0)可能在兩公式間翻轉 |

**為何選 MK 單利**:user 引述 MK 老師時很明確指向教學版,本系統優先對齊老師原意,wb01 變對帳 reference。Borderline 翻轉是 MK 觀點下的真相(複利低估了吃本金嚴重度)。

### §17.4 跨 tab SSOT 涵蓋

| Tab | 入口 | SSOT 狀態 |
|---|---|---|
| 單一基金(tab2)| `services.portfolio_service.dividend_safety`(同 canonical core)| ✅ 同源 |
| 組合基金健診-健診總表(tab_fund_grp_health)| `check_eating_principal_1y_mk` | ✅ v19.148 接 + v19.149 升級 |
| 組合基金健診-健診摘要表(fund_checkup)| `dividend_safety`(同 canonical core)| ✅ 同源 |
| 組合配置(tab3_portfolio)| `dividend_safety`(同 canonical core)| ✅ 同源 |

**Phase B 候選**(v19.245 R13 復查:fund_checkup 早於 v19.150 已 migrate 至 `check_eating_principal_1y_mk` SSOT,line 166 動態 import;原 `dividend_safety as div_safety_check` 為 dead import 已清。其餘 caller `tab1_macro` / `tab2_single_fund` / `tab3_portfolio` 仍用 `dividend_safety(_tret, _dyld)` scalar 介面,**signature 不同**,migration 會引入 reshape 複雜度違 §8.1 step 6,**WONTFIX 維持**)

### §17.5 3-3-3 原則(MK 老師長線輔助)

`check_333_principle(years_since_inception, ann_return_3y_pct)`:

- 成立 ≥ 3 年
- 過去 3 年平均年化報酬 > 7%

**用途**:挑選**新核心資產**時的長線篩選,不是吃本金主判定(短線吃本金以 §17.1 為準)。helper 已寫好,目前未接 UI,等 user 要看時可在任何 tab 加 column 顯示 ✅/❌。

### §17.6 Test 守衛

- `tests/test_mk_simple_formula.py`(v19.149):26 tests — 公式正確性 + 1Y 窗邊界 + 配息日界線 + 邊界條件 + property 加法可拆性
- `tests/test_mk_ssot_unification.py`(v19.148):15 tests — 跨 shape SSOT + canonical 守 + cross-caller import 守
- 既有 `test_portfolio_health` / `test_fund_dividend_calculator` / `test_fund_dividend_health` — 77 tests 零回歸

---

## §18 Pandera 導入設計提案(v19.154 — design only, **無 code 改動**)

> CLAUDE.md §3.1 「待議:是否將 pandera 加入 requirements 並逐 repository 落地 schema?」
> 本節為依 §8.1 「先設計、自評過度設計、經核准才寫」之**設計提案**,本 PR 不寫 code。

### §18.1 動機(為何要做)

`__init__` 與 repository 各 fetcher 回傳的 DataFrame shape 散落於 docstring + 範例,無強制驗證:
- 新加 fetcher / 改 column / dtype drift → 下游計算靜默偏移,CI 無偵測
- 同 schema 重複 assert 散落 callers(NAV>0 / date monotonic / weight sum=1 等)
- §6 自審清單條目「不變量斷言」缺工具支撐

pandera 提供宣告式 schema + 強制檢查 + 整合 pandas,在 fetcher 出口與 service 入口做門關。

### §18.2 反對方視角(自評過度設計)

| 反對理由 | 評估 |
|---|---|
| import 開銷 ~200ms(每次 streamlit reload) | 中度 — Streamlit cache 多數 fetcher 已避開 cold-path |
| 既有 assert 已涵蓋大多數 | 真 — 但散落 + 重複,且新 caller 易忘 |
| schema 修改需協同 caller 改 | 真 — 但這正是 pandera 想守的「契約」,改 = 契約變更須明示 |
| 過度約束(strict mode 反而 brittle) | 真 — 需用 `strict=False` + `coerce=True` 緩解 |

**自評結論**:**值得做但分階段**。Phase A 只在 2-3 個高 ROI 入口落地,不全面強推。

### §18.3 範圍(Phase 拆分 — user approve 後逐 phase PR)

#### Phase A — Pilot(最小可行 + 學習)
- requirements.txt 加 `pandera>=0.20,<1.0`(pin minor)
- 在 `repositories/macro_repository.fetch_fred()` 出口加 schema(date / value / source / fetched_at)
- 寫 1 個 schema 模組:`shared/schemas.py`(L0,無 IO)
- 加 5-10 個 tests 證明:合法 input 通過、illegal column drift 立擋
- **scope 上限**:1 個 fetcher + 1 個 schema 模組 + tests + 文件
- **時間預估**:1-2 個 PR

#### Phase B — 擴展到核心 fetcher(approve 後)
- `fetch_yf_close` / `fetch_fund_nav_series` / `fetch_dividends`
- 每個 fetcher 配對 schema(`NavSchema` / `DividendSchema` / `MacroSchema`)
- 補對應 tests

#### Phase C — Service 入口(approve 後)
- `compute_1y_total_return_mk_simple` / `calc_metrics` 等 L2 service 入口
- 校驗從 fetcher 流入的 DataFrame 符合契約
- 反捏造守(§3.3):不法輸入直接 raise,避免 silent drift

#### Phase D — 全面落地(approve 後)
- 所有 L1/L2 入口都用 schema
- CI 跑 schema test 作為 PR gate

### §18.4 失敗降級

- pandera schema validation 失敗 → 視為**契約違反** raise SchemaError
- 對齊 CLAUDE.md §1 Fail Loud:不偽造、不 silent fallback
- 但需 caller decorator 把 SchemaError 轉為 friendly UI 訊息(避免線上 user 看到 stacktrace)

### §18.5 §8.2 分層與依賴

- `shared/schemas.py` 屬 L0(無 IO,純 schema 宣告)
- 各 repository fetcher 在出口處 `.validate(df)`,屬 L1 自驗
- service 入口 validation 屬 L2 防禦
- pandera 只能被 L0/L1/L2 import,L3 UI 不直接呼叫

### §18.6 SSOT — schema 唯一性

- 同一資料源(NAV / Dividend / Macro)只有**一個** schema
- repository 與 service 共用,杜絕雙寫雙改
- schema 改動 = `shared/schemas.py` 唯一 commit point,**禁止** caller 端重新宣告

### §18.7 接下來的動作

**本 PR(v19.154)**:**只寫本設計提案 SPEC §18,不動 code**。

**等 user 明示「OK Phase A 啟動」之後**:
- 開新 PR v19.155 — Phase A pilot 落地(本 SPEC §18.3 Phase A 範圍)
- Phase B/C/D 各自獨立 PR,每階段都需 user re-approve

**WONTFIX 標準**(對齊 §-1):
- 若 user 不啟動 → 本提案保留為 SPEC 文件,**永不主動推**
- 唯有 user 明確說「動工」才開 Phase A PR
