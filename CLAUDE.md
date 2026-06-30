# CLAUDE.md — 資料完整性憲法（my-Fund-dashboard）

> 本檔為 AI 協作的最高行為準則,目標:確保資料**真實、可追溯、計算正確、可重現**。
> 跨領域不變的原則已寫死;**領域相關**的部分由 §0 Bootstrap 依本專案實況填妥。
> 違反本檔任一條視同 bug,須當場修正。
>
> ⚠️ **流程治理 / state 管理 / PR 規範 / Anti-Loop** 屬另一面向,獨立於本「資料憲法」,
> 請見同目錄 `PROCESS.md`(原 Core Protocol v2.0,2026-06-22 並存策略 B 拆檔保留)。

---

## §-1. 工作準則(凌駕 §0~§8)

> 2026-06-24 user 明確要求:**「沒實際 bug / 沒具體需求 → 不要動」**

**AI 提議任何新工作前,必須先驗證**:
1. ❓ 這個項目 user 實際在用嗎?
2. ❓ 是真實 bug 觸發,還是只是 BACKLOG / CLAUDE.md 待議標籤?
3. ❓ ROI 對 user 的工作流程有具體幫助嗎?

**任一答 No → WONTFIX,不該提議**

**禁止的提議模式**:
- ❌ 因為 BACKLOG / CLAUDE.md 寫了就提議
- ❌ 因為「審計清單裡的 TODO」就推
- ❌ 機械式清 TODO list 充數
- ❌ 把「文件待議」當必做項
- ❌ 把「未完成項目?」當作要主動找事做的訊號

**允許動工的觸發**:
- ✅ user 主動要求新功能 / bug fix
- ✅ 跑測試 / 使用時遇到實際錯誤
- ✅ 既有功能維護(security / 依賴升級必要)

**標準 default 回應**:user 沒明確指派時 → **停手等指令**,不主動找事。

---

## §0. 填寫紀錄(首次填寫 2026-06-22;步驟 4 收尾 2026-06-23)

> Bootstrap 流程全 4 步完成,§0 已從「BOOTSTRAP 紀錄」改名為「填寫紀錄」。
> 完整收尾證據按時序記錄如下。

**步驟 1｜探查專案** — 已完成,三組並行 Explore agent 掃描,涵蓋:
- meta-docs(STATE/ARCHITECTURE/SPEC/STRATEGY/BACKLOG/Requirements/NAS_PROXY_GUIDE)
- 18 個外部資料來源 endpoint + 單位 + 發布延遲 + fallback chain
- 6 個 SSOT 模組 + ~15 處 inline magic + TTL inventory(100% SSOT) + 單位陷阱

**步驟 2｜填寫待填欄位** — 已完成,以下節次依現有 code 證據填妥(每條附 `file:line`):
- §2.1 SSOT 5-Tier 18 來源權威分級(對照 Stock 27 來源)
- §2.3 Point-in-Time 各源發布延遲 + 修正風險表
- §2.4 Freshness max_age 對照(依 `shared/ttls.py` v19.69 + service-level)
- §3.1 Schema 主要 DataFrame(NAV / dividend / portfolio / FX / macro)
- §3.2 範圍 / 合理性檢查(依 MACRO_THRESHOLDS v19.72 + valuation σ)
- §3.3 反捏造 — 6 類 magic number 盤點(含 SSOT vs inline 標記)
- §3.4 Benford 適用性判斷
- §4.1 6 大單位陷阱
- §4.2 不變量斷言
- §4.4 Welford 適用性判斷
- §4.5 時序對齊(**無**第三方 trading calendar lib;FundClear T+1、MoneyDJ T+1~T+3)
- §4.6 領域邊界(基金特有狀態:配息切割 / 停售 / NAV 缺週 / FX 換匯 / 子網域 403)
- §8 架構先行 — 4 層分層 + 5 條硬規則(對照 ARCHITECTURE.md v11.0)

**步驟 3｜回溯稽核** — 已完成,違憲清單分高/中/低三級;以下 W 系列 + F-H 系列 PR 逐一收斂:
- W1+W2(#310):3 處 except:pass + fillna 補 log + 業務語意註明
- W5-1(#313):3 處 except:pass 補 log + fund_service fillna
- W5-2(#314):4 處 ffill/dropna 補 log + 註明
- W5-3(#315):shadow fund docstring SSOT + FII fillna 補 log
- W3a(#312):macro_repository recession_probability 收 SSOT
- F-H3(#316):CPI YoY+MoM zones 收 SSOT(signal_thresholds.py v19.75)
- F-H5(#317):zscore DRY 合一 + std=0 改 NaN(§1 Fail Loud)
- F-H4(#318):allocation matrix EX-POLICY-1 例外登記
- F-H1(#319):AAII sentiment 下沉 L1 repository
- F-H2(#320):ai_service Gemini I/O 下沉 infra.llm
- F-H6(#321):moneydj 走 L2 + EX-CRUD-1 / EX-PASSTHRU-1 例外登記

**步驟 4｜收尾** — 已完成。
- §3.3 反捏造 ❌ 0 項 / ⚠️ 0 項(F-H4 EX-POLICY-1 例外收結)
- §8.2 高項違憲 0 項(F-H1/H2/H4/H6 全結案)
- §8.2.A 例外清單:EX-CACHE-1 / EX-AI-1 / ~~EX-POLICY-1~~(v19.212 P0-3-#4 退役) / EX-CRUD-1 / EX-PASSTHRU-1 / ~~EX-L1ORCH-1~~(v19.238 登錄 → v19.240 R8 升級退役)
- 證據:全部 commit history + PR description 保留於 origin/main。

---

## §1. 最高原則:Fail Loud, Never Fake(寧可炸掉,不可造假)

凌駕一切的鐵律。錯誤的數字比沒有數字更危險。

當缺資料、外部呼叫失敗、值異常、或假設無法成立時:

- ✅ **一律 `raise` 並清楚說明**(哪個來源、哪幾筆、為什麼)
- ❌ **禁止**用以下手段讓流程「看起來成功」:
  - `fillna(0)` / 填入任意預設值
  - 無說明的 `ffill` / `bfill`
  - 回傳 dummy / example / 範例資料
  - `except: pass` 或吞掉例外
  - 自行「估一個合理值」當常數
- ⚠️ 任何填補**必須**:(1) 顯式呼叫、(2) 寫入 log、(3) 在輸出帶旗標(如 `is_imputed`)

> **判斷準則**:若你正打算寫一段「讓程式不報錯」的程式碼,先問:
> 「這是在**解決**問題,還是在**掩蓋**問題?」掩蓋 = 違憲。

**Fund 特殊脈絡**:基金 NAV 為 T+1~T+3 公布,週末/假日無新資料 = **正常**,不可 ffill 偽造每日值;
**MoneyDJ 子網域 403** 走 fallback chain(yp010000 → yp010001 → TDCC → FundClear → Cnyes),失敗時須保留來源旗標。

---

## §2. 資料層(Data Integrity)

### 2.1 SSOT — 單一權威來源

**來源註冊清單 SSOT**:`shared/fred_series.py`(v19.70, 34 FRED series IDs)+ `ui/helpers/data_registry.py`(L62-120, freshness lag table)+ `repositories/moneydj_fetcher.py:36-108`(MoneyDJ 多 page_type fallback chain)。

**5-Tier 權威分級**(衝突時上層贏,**禁止平均**):

| Tier | 等級 | 來源範例 | Evidence |
|---|---|---|---|
| **T1** | 官方政府/央行 API | FRED, TDCC OpenAPI, FundClear SmartFundAPI, CBC ms1.json, MOF | macro_repository.py:52-54, fund_repository.py:80-187,2043-2242, repositories/tw_macro_repository.py:41-45(v19.224 D 步驟更新路徑)|
| **T2** | 商用聚合 API(帶 token 或 stable IP) | FinMind, Yahoo Finance query1, Gemini API | repositories/tw_macro_repository.py:40, repositories/hot_money_repository.py:38, macro_repository.py:311-344(v19.224 D 步驟更新路徑)|
| **T3** | 第三方網站(HTML 抓) | MoneyDJ(主 + TCB + Chubb 子網域), SITCA, Allianz 官網, Morningstar, Insurance subdomains(TL/FL/CT/JF/NN etc) | fund_fetcher.py:79-106, fund_repository.py:1061-1306,1467+,1926-2043,196-265,713-1060 |
| **T4** | News RSS(非數值,僅文本) | Reuters, MarketWatch, FT, Yahoo Finance, Investing, CNBC, BBC, Bloomberg | news_repository.py:15-55 |
| **T5** | User config / AI | Google Sheets(policy/portfolio), Gemini API(synthesis only) | services/auto_search_store_gs.py, services/ai_service.py |

**關鍵衝突裁決**:
- **基金 NAV**:FundClear(境外)主、TDCC(境內)主、MoneyDJ 補強(績效/風險/持股),Cnyes / Morningstar 為最末 fallback(evidence: fund_repository.py:2352+)
- **MoneyDJ 子網域**:依保單發行商選對應子網域(合庫→tcbbankfund / 安達→chubb),**不混用**(evidence: fund_fetcher.py:94-106)
- **TW PMI / NDC**:FinMind TaiwanMacroEconomics(evidence: macro_tw_local_fetch.py:35)
- **TW 外資買賣超**:FinMind TaiwanStockTotalInstitutionalInvestors(evidence: hot_money.py:38)
- **VIX**:Yahoo `^VIX` 主,FRED VIXCLS 備
- **News**:8 個 RSS feed 並聯,**不去重後平均**,以情緒詞典關鍵字命中為準(evidence: news_repository.py:15-55)

### 2.2 Provenance — 血緣追蹤

**現況**:本專案以 `DataFrame + meta dict` + cache decorator(`@_ttl_cache` / `@st.cache_data`)承載血緣。
- fund_repository.py 多 fetcher 回傳 dict 含 `source`、`fetched_at`、`page_type` 等欄位
- `infra/proxy.py` 走 NAS Squid 時附 `X-Cache-*` header 供 audit
- `infra/cache.py` `_CACHE_REGISTRY` 集中註冊所有 cache 函式,supports「clear all」
- ✅ **F-PROV-1 主要 fetcher 全收**(v19.82 → v19.221 逐步):
  - **L1 fetcher 已收**(各帶 `source` + `fetched_at`):`fetch_fred` v19.82 / `fetch_yf_close` v19.83 / `fetch_defillama_stablecoin_mcap` v19.84 / `fetch_aaii_sentiment` v19.84 / `fetch_foreign_flow_series` v19.151 / `fetch_twse_breadth` + `fetch_finmind_foreign_investor` + `fetch_cbc_m1b_m2` v19.94 / `fetch_ndc_signal_history` + `fetch_tw_pmi_local` v19.151 / `fetch_ism_pmi` v19.156(7 個 return 點) / `fetch_macro_compass` v19.86 / `fetch_stooq_csv` v19.197 / `fetch_cboe_csv` v19.221(`s.attrs["source"]/"fetched_at"`)
  - **WONTFIX(v19.271 C 深挖確認)**:`fetch_yf_forward_pe` / `fetch_multpl_pe` 兩 fn **production 0 caller**(`services/valuation.py` v19.251 已退役,Forward P/E 改 `shared/macro_buckets.py:150-153` inline literal),且 fn 內部 `print(f"[external_market/...]")` console log 已具 audit trail。包 NamedTuple/dict 雖技術可行但 0 caller = ROI 0,§-1 不主動推。**未來條件**:若 V5 修補復活並接入 orchestrator,再評估 NamedTuple 包裝。
  - ✅ **macro 融合層 v19.270 D8 #8 落地**:`calculate_composite_score(ind, *, provenance_out=None)`
    opt-in side-car dict pattern。既有 caller 傳 None 行為零變化;新 caller 傳 dict 取得
    `sources` / `fetched_at_latest` / `contributions[indicator]` / `n_indicators`。設計選 E
    (側車容器)避免 dataclass 改 signature 連帶 6+ caller 全 migrate 的 churn。

### 2.3 Point-in-Time — 防 Lookahead

本專案**回測場景受限**:`services/crisis_backtest.py` + `crisis_strategy_grid.py` + `backtest_turning_points()` 為**歷史拐點驗證**,**非**滾動 walk-forward,但仍**必須**遵守 PIT 對齊(evidence: STATE.md v18.20)。

**各來源發布延遲 + 修正風險**:

| 來源 | 指標 | 發布延遲 | 修正風險 | PIT 對齊鍵 |
|---|---|---|---|---|
| FRED | PMI(NAPM) / CPI / NFP | 月後 ~13 天 | **是**(隨後 1-2 月常修) | release_date,**禁止**用 observation_date |
| FRED | M2 / Fed Rate | 月後 ~7-30 天 | 低 | release_date |
| FRED | ICSA / CCSA(初/續請失業金) | 週 +3 天 | 極低 | release_date |
| FundClear | 境外基金 NAV | T+1 | 無 | 淨值公布日 |
| TDCC | 境內基金 NAV / 清單 | T+1 | 無 | 淨值公布日 |
| MoneyDJ | NAV / 績效 / 風險 / 持股 | T+1 ~ T+3 | 低 | 淨值公布日 |
| FinMind | TW PMI / NDC | 月後 ~5-10 天 | 低 | 公告日 |
| FinMind | 外資買賣超 | T+1 | 無 | 交易日 |
| CBC | M1B/M2 | 月後 ~5-7 天 | **未明**(待 audit) | 公告日 |
| Yahoo Finance | OHLCV(VIX/DXY/USDTWD) | EOD 16:00 ET ≈ 翌日 04:00 TW | 無 | 交易日 |
| RSS | 即時 | 數秒~分鐘 | N/A | 不參與計算 |

**回測對齊規則**:
- FRED CPI 用 `release_date` 而非 `observation_date`(修正後值不可回填到過去決策)
- 月頻 macro vs 日頻 NAV:`merge_asof` direction="backward" + tolerance("40d" or 月底)
- FX 換匯(USDTWD)用**當日**收盤率,**禁止**用未來率回填

✅ **F-PIT-1 v19.81 audit 結果**:`services/crisis_backtest.py` 與 `crisis_strategy_grid.py` **PIT-safe**:
- `detect_crisis_events`:單序列時序順序掃描(走訪 + 維護 HWM),無未來索引存取
- `attach_fund_drawdown`:嚴格時間窗 `>= peak_date & <= trough_date` 切片,recovery `> trough & <= recovery_date`
- `crisis_strategy_grid.py:176`:`position = raw_pos.shift(1).fillna(1.0)` — 訊號於 t 計算、部位於 t+1 生效,防止 same-bar lookahead
- 無 `merge_asof` 跨頻運算,無需 tolerance 對齊

### 2.4 Freshness — Max Staleness

依 `shared/ttls.py` v19.69 + service-level 額外常數:

| TTL 常數 | 數值 | 適用範圍 | Evidence |
|---|---|---|---|
| `TTL_1MIN` | 60 s | 政策編輯器(寫後立即讀) | shared/ttls.py, ui/helpers/v2_editor.py:256,262 |
| `TTL_5MIN` | 300 s | FRED 短期指標 / Yahoo intraday | shared/ttls.py |
| `TTL_10MIN` | 600 s | USDTWD FX series | shared/ttls.py, hot_money.py:151 |
| `TTL_15MIN` | 900 s | FinMind TW macro / NDC | shared/ttls.py |
| `TTL_30MIN` | 1800 s | 外資買賣超 / 基金 NAV / 持股 | shared/ttls.py, hot_money.py:102 |
| `TTL_1HOUR` | 3600 s | 基金 meta / 績效 / 風險表 | shared/ttls.py |
| `data_registry.py` dynamic | - | FRED `next_release_date` 動態 TTL | ui/helpers/data_registry.py |

**Data Freshness Thresholds**(per SPEC §2):
- Daily 指標:🟢 ≤ 3 days / 🟡 ≤ 7 days / 🔴 > 7 days
- Monthly 指標:🟢 ≤ 45 days / 🟡 ≤ 75 days / 🔴 > 75 days
- **STALE 注入**:月度指標 > 40 days → AI Prompt 附 `[STALE: XXd]` 標籤(防 AI 把過期資料當當期講)

**規則**:超過 TTL 應**重新抓取**;若上游全敗,過期 cache 回傳須帶 `is_stale` 旗標,**禁止**靜默返回。

---

## §3. 驗證層(Validation)

### 3.1 邊界契約(Schema)

**現況**:requirements.txt **無 pandera**,現有資料 schema 散落於各 repository 的 dict / df parse 邏輯(`fund_repository.py`、`macro_repository.py`、`news_repository.py`)。

**規範**:新增資料流入 / 流出系統的點,**必須**附等效斷言(即使尚未引入 pandera):

```python
# nav_df (基金淨值序列 — FundClear / TDCC / MoneyDJ 共通)
{
    "date":    DatetimeIndex, ascending=True, unique=True (週末/假日缺值為正常),
    "nav":     float > 0, non-null (NaN 必須顯式 skip,不可填 0),
    "source":  str ∈ {"fundclear","tdcc","moneydj","cnyes","morningstar"},
}

# dividend_df (基金配息 — MoneyDJ wh06_4 為主)
{
    "ex_date":      DatetimeIndex, ascending,
    "div_amount":   float >= 0 (元/原幣),
    "currency":     str ∈ ISO 4217,
}

# portfolio_df (Google Sheet 政策)
{
    "fund_code":    str (6 digits or alpha-prefixed insurance code),
    "weight":       float ∈ [0,1] (NOT 0~100 整數),
    "snapshot_at":  datetime,
}

# macro_df (FRED / FinMind / CBC 通用)
{"date": ..., "value": float, "source": str, "as_of": date}

# fx_df (USDTWD spot)
{"date": ..., "rate_twd_per_usd": float > 0 (TWD/USD 不混用倒數)}
```

✅ **全結案 v19.241**(F-SCHEMA-1):pandera 已 pin `requirements.txt` (>=0.20,<1.0)。**全 4 phase 落地**:
- **Phase A**(pilot v19.155)— `MacroFredSchema` + `validate_fred` 模板建立
- **Phase B**(v19.161-163)— `YahooCloseSchema` / `FundNavSchema` / `FundDividendSchema` + 對應 validator,5 production fetcher 接入
- **Phase B5**(v19.186)— `ForeignFlowSchema` + `validate_foreign_flow` 新增 hot_money fetcher 接入
- **Phase C**(v19.164)— 服務層 data-only validators `validate_fund_nav_data_only` + `validate_fund_dividends_data_only`(對比出口 validator,不驗 provenance attrs,讓 cache/test fixture 反序列化序列也能驗業務契約)
- **Phase D**(v19.165)— **CI gate** 落地:`.github/workflows/pr-check.yml::schema-gate` job 跑 6 個 schema test 檔(`test_schemas_phase_a/b/b2/b3/b_foreign_flow/c.py`)91 tests 全綠,failure 即阻擋 merge,獨立 job 讓 schema regression 在 PR 視圖一眼可見

**最終 surface**:5 Schema + 7 validator(4 出口含 attrs + 2 data-only + 1 foreign_flow)+ 6 test file 91 tests + CI gate。**剩餘未驗 fetcher**(stooq / cboe / defillama / TW macro fetchers 等 ~10 個)為 Tier 2/3 次要源,§-1 等實際 bug 觸發再加,**不主動推進**(§8.1 step 6)。

### 3.2 範圍 / 合理性檢查

| 指標 | 合理範圍 | Evidence |
|---|---|---|
| PMI(採購經理指數) | [30, 70] | services/macro_validation.py SCORE_RULES |
| VIX | [5, 100] | services/macro_validation.py:35-84(crisis=30, warning=18) |
| CPI YoY (%) | [-5, 20] | services/macro_tw_local.py:150-157 SSOT (CPI_YOY_*_MAX_PCT) |
| US10Y (%) | [0, 20] | repositories/macro_repository.py:180-195 MACRO_THRESHOLDS |
| DXY(美元指數) | [70, 130] | MACRO_THRESHOLDS |
| HY OAS (%) | [1, 25] | MACRO_THRESHOLDS |
| 殖利率差 10Y-2Y / 10Y-3M (%) | [-3, 5] | MACRO_THRESHOLDS |
| Sahm Rule | ≥ 0.5 危機 | services/macro_service.py:216-218 |
| CFNAI | ≤ -0.7 衰退 | services/macro_service.py:226 |
| Forward P/E | μ=16.5, σ=3.0 | shared/macro_buckets.py:150-153(DESIGN literal,v19.251 valuation.py 退役) |
| ~~GDP Trend (%)~~ | ~~μ=2.3, σ=1.5~~ | ~~services/valuation.py:33-38~~(v19.251 退役;production 0 caller) |
| NAV(基金) | > 0 | (停售/清算時應為 NaN 而非 0) |
| Weight(權重) | [0, 1] ratio,非 0~100 | services/portfolio_service.py |
| Shadow fund 相似度 | > 0.70 警示 | services/portfolio_service.py:424(jaccard×0.6+cosine×0.4) |
| NEAR_PCT(接近警戒) | 2.0 % | services/fund_service.py:279, fund_dividend_calculator.py:23 |
| Holdings YoY sanity | NAV 比 [0.3x, 3.0x] | services/fund_service.py:239-240 |

**領域不變量**(calculation-side):
- NAV: `nav > 0`,週末/假日缺值不可 ffill 偽造,date 軸單調遞增
- 配息: `div_amount >= 0`,ex_date 不重複
- 權重: `sum(weights) ≈ 1.0`(健康評分、portfolio 配置)
- σ thresholds: 一致 sign convention(負 = 下檔,正 = 上檔)

### 3.3 反捏造(Anti-Fabrication)

**禁止 inline magic number**,以下常數**必須**從 SSOT 引入,絕不可腦補:

| 常數類別 | 值 | SSOT 位置 / 現況 | 違憲狀態 |
|---|---|---|---|
| `TTL_*`(6 個語意常數) | 60/300/600/900/1800/3600 s | shared/ttls.py v19.69 | ✅ SSOT(9 production 檔已遷移) |
| `FRED_*`(34 個 series ID) | FRED API key 字串 | shared/fred_series.py v19.70 | ✅ SSOT(8 production 檔已遷移) |
| `MATERIAL_*`(色票) | hex 字串 | shared/colors.py v19.71 | ✅ SSOT(18 production 檔已遷移) |
| `MACRO_THRESHOLDS`(26 entries) | 各 indicator zone 邊界 | repositories/macro_repository.py:180 v19.72 | ⚠️ **僅文件參考**(F-GRAY-4 v19.80 audit:dict 與 inline 條件**語意不同源**,inline 服務多用途有不同閾值,不可機械式 swap;詳見 macro_repository.py:199-212 註解) |
| `SCORE_RULES`(macro evaluation) | weights + lambdas | services/macro_validation.py:35-84 | ✅ SSOT + JSON override(macro_thresholds_global.json) |
| Verdict cutoffs `(10,5,-5,-10)` + phase `(8,5,3)` | 5/4 級分類 | services/macro_weights_store.py:363-364 | ✅ SSOT + active.json override |
| ~~Valuation `FORWARD_PE_MEAN/STD`、`GDP_TREND/_STD`~~ | ~~16.5/3.0/2.3/1.5~~ | ~~services/valuation.py:33-38~~ | **v19.251 退役**(0 production caller,Forward P/E 改 shared/macro_buckets.py:150-153 inline literal) |
| `signal_thresholds.*`(31 個語意常數) | 252 / 0.5 / -0.7 / σ cutoffs / 各 weight / NEAR_PCT / CPI YoY+MoM zones 等 | shared/signal_thresholds.py v19.75 | ✅ SSOT(W2+W3a+W5-4 已遷移 12 consumer:fund_service / macro_service / precision_service / portfolio_service / liquidity_engine / macro_explain / fund_dividend_calculator / risk_calibration / macro_repository.recession_probability / macro_tw_local CPI zones) |
| ~~Allocation phase params~~ | ~~DRIP/CASH/STAY 4×3 matrix~~ | ~~services/allocation_simulator.py:34-97~~ | ~~EX-POLICY-1~~ **v19.212 P0-3-#4 整檔拔毒**(866 LOC,production 0 caller) |

❌ 標記 **0 項**(W3b/W5-4 已收斂)、⚠️ **0 項**(F-H4 v19.76 結案,v19.212 EX-POLICY-1 對象拔毒退役)。

**其他規則**:
- `fillna` / `ffill` / `dropna` 必須顯式呼叫 + log 受影響筆數
- 測試資料與正式路徑物理隔離(`test_*.py` fixtures 不可流入 production cache)
- `except: pass` 一律違憲;`except Exception as e:` 至少要 log + 往上拋或回傳 fail token

### 3.4 統計異常偵測

- **IQR**(穩健,優先用):**適用** — VIX / HY spread / 個基 vol 為厚尾資料
- **Z-score**(近常態時):**部分適用** — CPI、PMI 近常態,適用;個基 NAV 報酬率非常態,**不適用**
- **Benford's Law**:**不適用** — 本專案資料皆官方 API + HTML 抓取,**無人為申報原始資料**(FundClear/TDCC 為政府/聚合,MoneyDJ 為二手呈現),且當前無此偵測需求

---

## §4. 計算層(Computation Correctness)

### 4.1 量綱 / 單位陷阱

| 陷阱 | 描述 | Evidence |
|---|---|---|
| **百分比 vs 小數** | weights 用小數(0.6=60%)vs allocation_simulator `drip_pct=80`(整數%),呼叫端混用 = 100× 誤差 | services/portfolio_service.py:424 vs services/allocation_simulator.py:180,188-190 |
| **TWD vs USD vs 原幣** | 基金 NAV 為**原幣**,績效報表 TWD 換匯,FX series `rate_twd_per_usd`;**禁止**跨幣別直接平均 | services/currency.py, services/allocation_simulator.py:267-269 |
| **YoY vs MoM vs MTD** | CPI 用 YoY;NAV 報酬可日/週/月;Sharpe 用 252 日年化 | services/fund_service.py:180-345 |
| **σ sign convention** | -1.5σ/-1.0σ/+0.3σ/+1.5σ/+2.0σ 散落,正/負必須意義一致(下檔=負,上檔=正) | services/macro_explain.py:66-75 |
| **交易日 vs 日曆日** | `252` 為交易日年化,非 365;windows(1Y=252 交易日 ≈ 365 日曆日) | services/fund_service.py 散落 8+ 處 |
| **TW 時區 vs UTC** | FundClear / TDCC / MoneyDJ 為 TW 時間(UTC+8);Yahoo Finance EOD 為 UTC;Streamlit Cloud 預設 UTC | infra/proxy.py, services/fund_service.py |

**命名規範**:新增變數**必須**編碼單位,例:`rate_pct` / `rate_ratio` / `amount_twd` / `amount_orig_ccy` / `qty_shares` / `days_trading` / `days_calendar`。

### 4.2 不變量斷言

```python
# NAV 鐵則
assert (df["nav"] > 0).all() or df["nav"].isna().all(), "NAV 應為正或全 NaN"
assert df.index.is_monotonic_increasing, "時序未排序"
assert df.index.is_unique, "日期重複"

# 配息
assert (div_df["div_amount"] >= 0).all(), "配息不可為負"
assert div_df["ex_date"].is_unique, "除息日重複"

# 權重
assert math.isclose(weights.sum(), 1.0, abs_tol=1e-9), "權重未歸一"
assert (weights >= 0).all() and (weights <= 1).all(), "權重越界"

# Macro 範圍(對應 §3.2)
assert df["pmi"].between(30, 70).all() or df.empty
assert (df["us10y_spread"].abs() < 5).all(), "yield spread 異常"

# FX
assert (fx_df["rate_twd_per_usd"] > 0).all(), "FX 必為正"
assert (fx_df["rate_twd_per_usd"] < 50).all(), "USDTWD 不應 >50"
```

### 4.3 重算對帳(Reconciliation)

**現況雙源備援**已在 §2.1 衝突裁決列明(NAV: FundClear/TDCC/MoneyDJ 三源,VIX: Yahoo/FRED)。**雙演算法**待落地:
- **基金 1Y 報酬**:`(nav[-1]/nav[-252])-1` vs MoneyDJ wb01 顯示值 對帳(evidence: services/cross_source_compare.py)
- **Sharpe**:自算(`mean/std * sqrt(252)`)vs MoneyDJ wb07 對帳
- **配息殖利率**:`sum(12M div)/current_nav` vs MoneyDJ 顯示值
- **macro health score**:目前單一 path(`services/macro_service.py`),缺對照演算法 → 步驟 3 audit 後補

**浮點比較**:**禁止 `==`**,一律:
```python
math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
np.isclose(a, b, rtol=1e-9, atol=1e-12)
```

### 4.4 數值穩定性

- **log 空間連乘**:cumulative NAV return((1+r1)(1+r2)...)建議改 `exp(sum(log(1+ri)))`,本專案 crisis_backtest 路徑須檢查
- **災難性抵消**:yield spread (10Y-2Y) 兩值尺度接近,計算精度要保留 float64
- **Welford 變異數**:**部分適用** — 現用 pandas `rolling().std()`(內部 Welford-friendly 實作),**單序列**無需顯式;批次 N×T 大序列可考慮顯式 Welford
- **大數除以小數**:配息殖利率(`12M_div / current_nav`)當 NAV 接近 0 時須 guard(return NaN 或 inf,不可 silent ÷0)
- **FX 倒數**:`rate_twd_per_usd` ↔ `rate_usd_per_twd` 互轉時要小心 ÷0 與精度損失

### 4.5 時序對齊

**日曆 / 時區決策**:
- **不使用**第三方 trading calendar lib(無 pandas_market_calendars / exchange_calendars 在 requirements.txt)
- 用 Python std `datetime.timezone(timedelta(hours=8))` 統一表示 TW 時間
- **本地時區**:Asia/Taipei (UTC+8)
- **存儲規則**:時間戳一律 UTC(或 TZ-aware UTC+8),顯示時轉本地

**業務時點**:
- FundClear / TDCC 境外境內 NAV ≈ T+1(部分至 T+3)
- MoneyDJ 同步爬取 T+1~T+3
- FinMind 外資 T+1
- FRED ICSA 週四 +1 天
- Yahoo Finance EOD ≈ 16:00 ET → 翌日 ~04:00 TW
- CBC ms1 monthly 月後 ~5-7 天

**resample 安全性**:
- 已用 `"ME"`(月底)/ `"QE"`(季底)/ `"YE"`(年底)/ `"W"`(週)
- 預設 `closed=right, label=right` — **不會**引入未來資料
- audit 須驗證所有 resample 呼叫的 label/closed 是否一致(尤其月 NAV 對齊月 macro)

**跨頻 merge_asof**:
- 月 macro vs 日 NAV 用 direction="backward" + tolerance("40d")
- 缺對齊 tolerance 容易吃到未來月分

⚠️ **無業務還原調整**:本專案不涉及股本回填 / 借券稅後還原,但**配息切割**(ex-date NAV 下跳)為基金特有業務調整,須評估是否做還原 NAV 序列(目前未實作,直接用源數據)。

### 4.6 邊界條件

**通用**:空資料集 / 單筆 / 全空值 / 欄位剛建立。

**基金 / Macro 領域特有**(必測):
- **新發行基金**:歷史不足 1Y → Sharpe / σ band 應降可信度旗標
- **停售 / 清算基金**:連續 N 天無 NAV → **不可** ffill,旗標 `is_halted=True` 並顯式 skip
- **配息切割(ex-date 跳空)**:NAV 跳空 → 視業務需求做還原 NAV 或保留原序列(目前保留原序列,但 Sharpe / σ 計算須警示)
- **NAV 週末缺值**:基金不交易 → 計算 daily return 時跳過,**禁止**填 0
- **FX 重大波動**:USDTWD 單日 > 1% → 影響 TWD 換匯績效顯著,應旗標
- **MoneyDJ 子網域 403**:Insurance/TCB/Chubb 子域故障 → fallback chain(yp010000 → yp010001 → TDCC → FundClear → Cnyes)須完整(evidence: repositories/moneydj_fetcher.py:36-108)
- **FRED 月頻指標未發布**:next_release_date 未到 → 用上期值帶 `as_of` 標籤,**禁止**填當期日期
- **proxy 失效 / 直連 / 407**:`infra/proxy.py` NAS Squid → 直連 → fail 降級鏈
- **Google Sheet 政策衝突**:同 fund_code 多筆 weight → 取最新 snapshot,**禁止**平均

---

## §5. 流程層(Process)

- **冪等性**:同輸入重跑得同結果;重抓不產生重複筆。
- **可重現性**:固定隨機種子、pin 套件版本(注意 requirements.txt 多為 floor-only,backtest 場景須補版本 pin);歷史運算用**凍結快照**(`data_cache/` parquet)而非即時來源。
- **可觀測性**:每次 pipeline 輸出資料品質指標(缺失率、被填補筆數、outlier 數),異常告警。
- **效能**:向量化運算,避免隱性逐列迴圈;說明複雜度。

---

## §6. AI 自審清單(每寫完一段主動執行,勿等問)

```
□ SSOT;關鍵數值帶 provenance(source / fetched_at / as_of)
□ 無 inline magic number;常數從 shared/* 或 services/* SSOT 引入
□ 缺值顯式處理且 log;無 fillna(0) / 沉默 ffill / except:pass
□ 邊界已測:空集 / 單筆 / 全空值 / 新基金 / 停售 / 配息切割 / NAV 週末缺值 / FX 波動 / MoneyDJ 子網域 403 / proxy 降級
□ 量綱一致:% vs ratio / TWD vs USD vs 原幣 / 252 交易日 vs 365 日曆日 / TW vs UTC / σ sign convention
□ 無 lookahead:FRED CPI 用 release_date 非 observation_date;merge_asof tolerance="40d"
□ 時序對齊:FundClear/TDCC T+1 / Yahoo EOD 翌日 / resample label 右閉
□ 浮點比較用容差(math.isclose / np.isclose),非 ==
□ 關鍵指標有第二種算法對帳(基金 1Y 報酬 vs MoneyDJ wb01 / Sharpe vs MoneyDJ wb07 / 配息殖利率)
□ 不變量斷言(NAV>0 / date monotonic / 權重和=1 / PMI∈[30,70] / FX>0)
□ 向量化,無隱性逐列迴圈
```

最後另外提供:**3 個最容易讓這段程式出錯的輸入**,並寫成測試(單元 + property-based + golden test)。

---

## §7. 新功能動工前對齊

我交付新功能時,你**動手寫程式前**先回答:

1. 資料來源是哪個 endpoint?欄位單位是什麼?(對照 §2.1 表格 + §4.1 單位陷阱)
2. 這資料有發布延遲 / 回溯修正嗎?該用哪個「可用日」對齊?(對照 §2.3 表格)
3. 有哪些邊界要處理?(對照 §4.6 + §3.2 範圍表)
4. 計算式先用**數學式**寫給我確認,再寫程式。

先別寫 code,我們先對齊這四點。

---

## §8. 架構先行 — 涉及新模組 / 多檔案 / 改變資料流時

§7 對齊的是「資料」;本節對齊的是「架構」(模組怎麼切、誰依賴誰、資料怎麼流)。

**觸發條件**:新增模組、跨多檔案、或改變資料流。
**不觸發**:單檔小修、純 bug fix、改字串、typo、版本字串 bump — 直接做,避免儀式性開銷。

### 8.1 通則 — 先設計、自評過度設計、經核准才寫

動工前先提交架構規劃(文字 + 簡單流程圖),**這一步禁止寫 code**:

1. 這個功能 / 模組的**單一職責**一句話講完。
2. 該切成哪幾個模組 / 檔案?各自職責?
3. **資料流向**:從哪進 → 經過哪幾層 → 從哪出。
4. **依賴方向**:誰依賴誰?有無違反分層?
5. **失敗降級**:外部來源失敗時這個架構怎麼辦(fail loud 還是有備援)?
6. **自評過度設計**:對「當前需求的規模」會不會太重?用不到的抽象 / 分層標「**先不做,等真的需要再加**」。

### 8.2 本專案分層與依賴硬規則(evidence: ARCHITECTURE.md v11.0)

**4 層架構**(Clean Architecture,UI → service → repository → infra,~單向):

**白話對照(3 鐵盒 v19.249 加,純認知 alias,不是另一份架構)**:`DataFetcher = L1 Repository`、`CalcEngine = L2 Service`、`ComponentUI = L3 UI`。**L0 Infra / Shared 不在 3 鐵盒模型**(它們是跨層被全層 import 的基底,塞進任一鐵盒都違 §8.2 硬規則第 3 條)。3 鐵盒只當「找東西時的捷思詞」,實際 import path 仍走 `repositories/` / `services/` / `ui/`。

| 層 | 白話名 | 職責 | 代表檔案 |
|---|---|---|---|
| **L0 Infra** | (跨層基底) | OAuth / Proxy / Cache / 跨層公用 | `infra/proxy.py`、`infra/oauth.py`、`infra/cache.py`(+ `_CACHE_REGISTRY`) |
| **L0 Shared** | (跨層基底) | 常數 / TTL / FRED IDs / 色票(無 IO 純常數) | `shared/ttls.py`、`shared/fred_series.py`、`shared/colors.py` |
| **L1 Repository** | **DataFetcher** | 外部資料抓取 / HTTP / 解析 / 快取(`@_ttl_cache`) | `repositories/macro_repository.py`、`repositories/fund_repository.py`、`repositories/moneydj_fetcher.py`、`repositories/news_repository.py`、`fund_fetcher.py`(根目錄,legacy shim)、`repositories/hot_money_repository.py`(P0-4-A 搬入)、`repositories/tw_macro_repository.py`(P0-4-B 搬入)|
| **L2 Service** | **CalcEngine** | 業務邏輯純函式 / 評分 / 策略 / 模擬 / AI | `services/macro/` (11 子模組)、`services/health/` (5 子模組)、`services/calibration/` (4 子模組)、`services/fund_service.py`、`services/portfolio_service.py`、`services/ai_service.py`、`services/crisis_backtest.py`、`services/macro_validation.py` 等 ~25 檔(v19.212 退 allocation_simulator,v19.251 退 valuation) |
| **L3 UI** | **ComponentUI** | Streamlit Tab 渲染 + components + helpers | `app.py`(425 LOC,僅 orchestrator)+ `ui/tab*.py` + `ui/components/` + `ui/helpers/` |

**硬規則(violation = 違憲)**:
- ❌ **L1 Repository 不得 import streamlit 真 UI 呼叫**(`st.session_state` / `st.error()` / `st.markdown()`),允許 `@st.cache_data` 走 EX-CACHE-1 例外
- ❌ **L2 Service 不得 import** `requests` / `httpx` / `beautifulsoup` / `feedparser` — 純函式,無 I/O,需資料時走 L1 repository
- ❌ **L0 Infra / Shared 不得依賴任何 L1+** — 被全層 import,須無迴圈依賴
- ❌ **L3 UI 不得直呼 L1 Repository fetcher** — 透過 L2 Service 取數(cache 才能集中)
- ❌ **跨層上行 import**:L1 不得 import L2/L3、L2 不得 import L3

**已落地範例**(ARCHITECTURE.md v11.0):17 個 shim 刪除消滅舊架構迴圈 import,services 全純函式,repositories 全 I/O。

**8.2.A 已知例外清單**(豁免 §8.2 硬規則的特定模式,需明確標註理由):

| ID | 檔:行 | 例外規則 | 理由 |
|---|---|---|---|
| **EX-CACHE-1** | L1 全層(實際適用 v19.244 R12 audit:1 fetcher `repositories/hot_money_repository.py` `@st.cache_data(ttl=TTL_30MIN)` ×2;`news_repository.py` docstring 明說「不在這層 cache」,純 fetcher) | `@st.cache_data` / `@_ttl_cache` 條件 import | Streamlit Cloud cache 是部署架構核心,提供跨 session 共享 + TTL 自動失效,functools.lru_cache 不等價。**允許**在 L1 模組頂部寫 `try: import streamlit as st / except ImportError: 定義 no-op fallback decorator`,前提:**完全不用** `st.session_state` / `st.error()` / `st.markdown()` 等真 UI 呼叫。Fund 端 `@_ttl_cache(ttl_sec=N)` 為 custom 實作不依賴 streamlit,本例外主要適用 `@st.cache_data` 直接用法。 |
| **EX-AI-1** | `services/ai_service.py` 全檔 public 函式 | LLM 輸出回 **str** 而非 dataclass | 既有 multiple caller 全部以 st.markdown 渲染字串,改 dataclass 需大規模 migration。**緩解措施**:所有 AI 字串強制帶視覺旗標(`### 🧬 AI ... **使用模型**: <model>`),caller 可用 string prefix 偵測;module docstring 強制宣告「禁止從 LLM 字串萃取數字當 data input」。違反此 caller 規則 = §2.2 反捏造違憲,須立刻修。 |
| ~~**EX-POLICY-1**~~(v19.212 P0-3-#4 退役) | ~~`services/allocation_simulator.py:34-97`~~ | ~~`DEFAULT_PHASE_SCRIPT` + `STRATEGY_PRESETS` 保 inline~~ | **退役原因**:`ui/tab_allocation_simulator.py` consumer 已在 P0-2 v18.x 刪除,`services/allocation_simulator.py` 6/6 fn 全 dead(production 0 caller),v19.212 整檔 866 LOC 拔毒(含 2 test 孤兒)。EX-POLICY-1 例外對象消失,退役。 |
| **EX-CRUD-1** | UI 直呼以下 L1 repository:`policy_repository` / `snapshot_repository` / `ledger_repository`(Google Sheets / 本地 JSON 持久化) | L3 UI 可直接 import L1 CRUD repository | §8.2 規則「L3 不得直呼 L1 — cache 才能集中」的核心理由是**外部 HTTP fetcher 的 TTL cache 須集中管理**。本三個 repository 為**本地持久化**(read+write 同檔),**無 `@_ttl_cache` / `@st.cache_data` 裝飾**,亦無外部 HTTP I/O — 不存在「cache 分散」問題。為純 CRUD 加 L2 pass-through wrapper = §8.1 step 6「用不到的抽象」反例。`ui/helpers/cloud_io.py` / `v2_editor.py` / `oauth_state.py` + `ui/tab3_portfolio.py` / `tab3_t7_ledger.py` 直接 import 為允許用法。F-H6 v19.79 決策。 |
| **EX-PASSTHRU-1**(v19.251 補登 3 + v19.273 補登 1 entry) | UI 直呼以下 L1 facade fetcher(共 6 組):<br>- `repositories.fund.tdcc_search_fund`(`ui/tab2_single_fund.py:147`)— 多 endpoint(TDCC 3-2 + 3-4)整合 + dedup + nav merge + keyword match<br>- ~~`repositories.fund.get_latest_fx`~~ **(v19.247 R16 升級)**:9 caller files / 18 call sites 全 migrate 至 L2 `services.fund_service.get_latest_fx`(thin facade 呼 L1 實作,L1 業務 0 改動)<br>- `repositories.news_repository.fetch_market_news`(`ui/tab1_macro.py:1188` / `ui/tab3_t7_ledger.py:2710`)— 11 RSS feeds 並聯 + keyword filtering + systemic risk classify + dedup + sort<br>- **`repositories.fund.fetch_fund_by_key`**(`ui/tab_crisis_backtest.py:331` lazy)— 危機回測取 raw series(不需 metrics),L1ORCH-1 退役註腳已認可,v19.251 正式登錄<br>- **`repositories.fund.fetch_nav_history_long`**(`ui/tab_crisis_backtest.py:331` lazy)— 多年歷史 NAV(CnYES + MoneyDJ 歷史頁 + 24h disk cache),L1 完整 fetcher,UI 直呼 ROI 高<br>- **`repositories.fund.diagnose_fx_sources`**(`ui/tab5_data_guard.py:832` lazy)— Tab5 資料看板 diagnostic,L1 內部用 + UI 直呼合理<br>- **`repositories.macro_tw_local_repository.{fetch_ndc_signal_history,fetch_tw_pmi_local,fetch_tw_export_yoy,fetch_foreign_consecutive_days}`**(`ui/tab1_macro.py:821` lazy,4 fn 一組)— TW 本地總經 self-contained L1 fetcher(FinMind 單源),v19.197 P1-4 從 `macro_tw_local_fetch.py` 下沉 repositories,UI 直呼取數後在 L3 端 regime 判讀。**v19.268 D8 #7 後**:UI 端 `_safe_tw()` wrapper 已加 schema 驗證(`validate_ndc_signal_dict` 等),取數即驗,純 fetch facade 無 L2 業務需上提。 | L3 UI 直接 import L1 facade(共 6 組);v19.247 R16 後 `get_latest_fx` 已上提 L2 wrapper | **v19.273 Phase 2 TOP 3 補登原因**:`tab1_macro.py:821` 4 個 TW macro local fetcher UI 直呼為 v19.197 P1-4 下沉後的既有 pattern,屬「self-contained L1 fetcher + UI 直呼取數」(F-GRAY-2 同精神),原僅有 v19.197 commit 紀錄未在例外表登錄,PHASE1_AUDIT_DELTA.md TOP 3 點名補登避免讀例外表者誤判為違憲。**v19.251 補登原因**:R8 EX-L1ORCH-1 退役註腳口頭認可 `tab_crisis_backtest.fetch_fund_by_key`,但未在例外表正式登錄;另 `fetch_nav_history_long` / `diagnose_fx_sources` 同屬 lazy import + 單一 caller pattern,一併補登。**v19.247 R16 部分升級記錄**:9 UI caller 全 migrate `from services.fund_service import get_latest_fx`,L2 thin facade 呼 L1 實作(允許 L2→L1 方向)。L1 業務 0 改動。**升級觸發條件**:user 明確要求集中 cache、新增 source、後處理 bug。F-H6 v19.79 原決策 + R15/R16 對齊。 |
| ~~**EX-L1ORCH-1**~~(v19.240 R8 升級退役) | ~~L1 fund orchestrator import L2 `calc_metrics`~~ | ~~抓 + 打包 facade~~ | **退役原因**:v19.240 深挖發現實際違憲 3 個 L2 symbol(`calc_metrics` + `reconcile_fund_annual_return` + `reconcile_dividend_yield`)+ 大量 L2 業務判斷(perf 注入決策 / window 閾值 / % vs decimal 換算 / 對帳)push 回 L1,**升級觸發條件 (a)+(b) 均達標**。R8 採方案 (b) 拆 return + L2 wrapper:`services.fund_service.finalize_fund_metrics()` + `fetch_fund_by_key_enriched` / `fetch_fund_from_moneydj_url_enriched` 兩 wrapper 上提 L1 業務邏輯,L1 純化為 raw fetch + packaging。L1→L2 violation 從 3 → 0。Migrate 4 個 caller site(`ui/helpers/v2_editor.py` / `services/moneydj_fetcher.py` x3),其餘 `tab_crisis_backtest.py` 用 raw `fetch_fund_by_key`(只取 series 不需 metrics)。 |

**符合 EX-CACHE-1 的標準寫法**:
```python
try:
    import streamlit as st
except ImportError:
    class _NoOpST:
        @staticmethod
        def cache_data(*args, **kwargs):
            if args and callable(args[0]):
                return args[0]
            return lambda f: f
        cache_resource = cache_data
    st = _NoOpST()  # noqa
```

新增例外**必須**:(1) 在此表登錄、(2) 對應檔案加註解指回此表、(3) PR 描述附理由。**禁止**未經登錄的潛在「軟例外」。

### 8.3 灰色地帶(step 3 audit 確認結果)

- ✅ **F-GRAY-1 v19.81 audit 結案**:`fund_fetcher.py`(根目錄,459 LOC)**保留根目錄**。檔內 18 條 `noqa: F401` re-export shim(infra.cache / infra.proxy 等)+ 57 個 caller import 線。內容已是「向後相容 shim 容器」,搬至 `repositories/` 為純 cosmetic 改動且需動 57 個 caller 介面,違反 §8.1 step 6「用不到的抽象先不做」。
- ✅ **F-GRAY-2 v19.81 audit 結案 → P0-4 完成搬遷**:原 `hot_money.py`(344 LOC,5 callers)/ `tw_macro.py`(334 LOC,2 callers)F-GRAY-2 結論為「self-contained L1 fetcher,根目錄 vs `repositories/` 為純 cosmetic 不視為違憲」。**後續第二階段 P0-4-A/B v19.x 已完成搬遷**:`repositories/hot_money_repository.py`(P0-4-A 拆 2 檔 + UI 上層)+ `repositories/tw_macro_repository.py`(P0-4-B 整檔搬)。
- ✅ **F-GRAY-3 v19.81 audit 結案**:`app.py`(568 LOC)— 已是 orchestrator,主要功能為 `_now_tw`/`_load_keys`/`_check_secrets`/`_calc_data_health`(thin session-aware wrapper)/`render_macro_compass`(UI)。無顯著業務邏輯需下沉。同步刪除 1 處 dead code `_unused_old_calculate_composite_score`(deprecated placeholder, 0 callers)。
- ⚠️ **F-GRAY-4 v19.80 audit 部份結案,VIX 子題 C2 v19.160 完全收斂**:
  - **VIX(已收)**:user 2026-06-26 撤銷 v19.147 multi-cutoff,接受 trade-off。
    C2 series(v19.157 risk_radar / v19.158 macro_beginner_view / v19.159 macro_validation
    + calibration JSON bounds / v19.160 macro_service alert + SPEC §16.1 結案)全站 yellow
    統一 SSOT 22 / panic 30。`tests/test_cross_site_cutoffs.py` 守 3 site 全員 22 + universal 30。
  - **HY_SPREAD(已收 90%)**:`shared/macro_thresholds_v2.py:HY_SPREAD_THRESHOLDS` schema 落地,
    5 個 multi-purpose section(stoplight / score_function / portfolio_advisor / beginner_panic /
    inflection_detection)各自 SSOT;`ui/helpers/macro/beginner_view.py` 用 `_HY_THR` import;
    `services/macro_score_calibration.py` 用 `score_function`;v19.245 R13 inflection 收口。
    **剩 `ui/components/macro_card_edu.py:300-304` 教學文(<4% 樂觀 / 4-6% 中性 / >6% 走擴 /
    >10% 崩潰)**:**by-design 不收**,屬「threshold story 文檔」而非「inline 邏輯」,
    若 threshold 改 narrative 也需重寫,SSOT 化反而綁死敘事(§8.1 step 6 反例)。
    v19.271 C 深挖確認:`macro_card_edu.py` 共 25 個 `how_to_read` 表(VIX/PMI/CPI/HY/Sahm/SLOOS
    /yield spread/Fed rate/NFP/ICSA/CCSA/Consumer Sentiment/DXY/LEI 等),全為 `(str, str)`
    documentation literal 不參與 calculation;HY 4 級含「>10% 崩潰」與 stoplight 3 級**層級不對齊**,
    強收會遺失教學資訊;VIX 教學表 22/30 與 v19.160 SSOT 數值巧合相同但 5 級結構仍應 inline。
    本檔語意分離為 feature 不是 bug。
  - **CPI(部份收)**:`shared/macro_thresholds_v2.py:CPI_YOY_THRESHOLDS` schema 落地(stoplight /
    score_function / inflection_detection / regime_classification / beginner_panic 5 section);
    `services/macro_validation.py` SCORE_RULES 已對齊 score_function。
    **剩 2 處 logic inline**(`services/macro/macro_score.py:69` lambda + `ui/helpers/macro/helpers.py:183` 3.0 check)
    需 caller migrate,中風險(動 core scoring path),等實際 bug / user 需求觸發。
  - **PMI(WONTFIX 二段澄清,v19.271 C 深挖確認)**:user 2026-06-26 撤銷的是**「harmonize 統一值」**
    (50.0 / 52.0 / 45.0 不同源 trade-off),**不是「SSOT 化(下沉但不統一值)」**。後者已 v19.179 PR-1~3
    完整落地:`shared/macro_thresholds_v2.py:141-203` PMI_THRESHOLDS schema 8 sub-dict 完整 +
    10 production consumer 全 migrate import + `tests/test_macro_thresholds_v2.py` lock(含 TW_PMI_THRESHOLDS
    line 266 同步 SSOT)。剩餘 inline 命中皆為**文件 / 註解 / 教學字串 / UI slider default**,非邏輯 inline,
    屬 §8.1 step 6「文檔 SSOT 化反綁死敘事」反例,**by-design 不收**。**最小行動:無**。
  - ✅ **Architecture proposal v19.168 已落地**:`shared/macro_thresholds_v2.py` schema 已生效
    (HY/CPI/PMI 三 dict 註冊);SPEC §16.2 設計案 + per-indicator migration phases 已寫入。

- ✅ **F-RECON-1 雙演算法對帳全 phase 落地**(v19.87 → v19.91):
  - **服務層**:`services/reconcile.py` 5 fn 全實裝(`reconcile_pair` 通用 + `reconcile_us10y_yield` /
    `reconcile_fund_annual_return` / `reconcile_sharpe` / `reconcile_dividend_yield`)
  - **L2 wiring**:`services/fund_service.py:_reconcile_sharpe_pair` + `finalize_fund_metrics` 3 處
    對帳 dict 注入(`sharpe_reconcile` / `ret_1y_reconcile` / `div_yield_reconcile`)
  - **UI 渲染**:`ui/tab2_single_fund.py:913+968+981` 3 個對帳 chip(Sharpe / 配息殖利率 / 1Y 報酬)
    v19.91 phase 6 完整渲染(agree / disagree / a_missing / b_missing 四態 + 色碼)。
  - **未補**:macro health score 雙演算法 — `calculate_composite_score()` 單一 path,缺對標演算法。
    需架構設計第二套評分方案,**未實作**。等 user 點。

### 8.4 做到一半的新增功能 — 先盤點再動

新增功能前 audit pipeline:
1. 現有程式大致分成哪幾塊?資料怎麼流?(對照 §8.2 四層)
2. 哪裡**違反分層**?列檔名 + 行號(§8.3 灰色地帶已點名 4 處,audit 時補上更多)
3. 這次的新功能該放哪一塊?會不會被現有壞結構卡住?
4. 若需要先重構才好加,**分開提案**:「為這次必須改」vs「建議但可延後」,讓我決定範圍,**禁止**自作主張大重構。

核准範圍後才動;一次改一塊,貼 diff + 說明為何不破壞既有行為。

### 8.5 共同收尾

核准後**一次只寫 / 改一個模組**,每完成一個跑 §6 自審。
**禁止中途偏離已核准的架構**;若發現架構需要改,先停下來問。
