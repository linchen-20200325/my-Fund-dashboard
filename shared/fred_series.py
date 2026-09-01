"""v19.70 FRED Series ID SSOT — 34 個 series 散落 8 production 檔，集中為語意常數.

對稱 `shared/ttls.py` Fund-only 設計（NOT sync to Stock，因 Stock 域不消費 FRED）。
Replace pattern：`fetch_fred("DGS10", ...)` → `fetch_fred(FRED_DGS10, ...)`。

例外保留：
  - `test_*.py` fixture：依測試契約保留字面值。
  - 註解/docstring 提及：純文件描述，不需 import。

未來新增 FRED series 流程：本檔加常數 → call site `from shared.fred_series import FRED_<NAME>`。
"""
from __future__ import annotations

# ── Treasury yields / Rates curve ──────────────────────────────────
FRED_DGS10: str = "DGS10"          # 10Y Treasury yield
FRED_DGS2: str = "DGS2"            # 2Y Treasury yield
FRED_DGS3MO: str = "DGS3MO"        # 3M Treasury yield
FRED_T10Y2Y: str = "T10Y2Y"        # Yield curve spread (10Y - 2Y)
FRED_T10Y3M: str = "T10Y3M"        # Yield curve spread (10Y - 3M)
FRED_T5YIE: str = "T5YIE"          # 5Y breakeven inflation
FRED_FED_FUNDS: str = "FEDFUNDS"   # Fed Funds Rate

# ── Money supply / Liquidity ───────────────────────────────────────
FRED_M2: str = "M2SL"              # M2 monthly (seasonally adjusted)
FRED_M2_WEEKLY: str = "WM2NS"      # M2 weekly (non-seasonal)
FRED_FED_BS: str = "WALCL"         # Fed balance sheet (Wed level)
FRED_RRP: str = "RRPONTSYD"        # Overnight reverse repo
FRED_TGA: str = "WTREGEN"          # Treasury General Account (TGA, weekly Wed, USD mn)

# ── Credit spreads ─────────────────────────────────────────────────
FRED_HY_SPREAD: str = "BAMLH0A0HYM2"   # High yield OAS

# ── FX ─────────────────────────────────────────────────────────────
FRED_DXY: str = "DTWEXBGS"         # USD trade-weighted (broad)
FRED_JPY_USD: str = "DEXJPUS"      # JPY per USD
FRED_CHF_USD: str = "DEXSZUS"      # CHF per USD
FRED_CNH_USD: str = "DEXCHUS"      # CNY per USD (CNH proxy)
FRED_EUR_USD: str = "DEXUSEU"      # USD per EUR (inverse)

# ── Inflation / Prices ─────────────────────────────────────────────
FRED_CPI: str = "CPIAUCSL"         # CPI all urban consumers
FRED_PPI: str = "PPIACO"           # PPI all commodities

# ── Labor / Employment ─────────────────────────────────────────────
FRED_UNRATE: str = "UNRATE"        # Unemployment rate
FRED_PAYEMS: str = "PAYEMS"        # Nonfarm payrolls
FRED_ICSA: str = "ICSA"            # Initial jobless claims
FRED_CCSA: str = "CCSA"            # Continued jobless claims
FRED_SAHM: str = "SAHMREALTIME"    # Sahm rule recession indicator (realtime)
FRED_SAHM_CURRENT: str = "SAHMCURRENT"  # Sahm rule current vintage
FRED_PAYEMS_MANEMP: str = "MANEMP"  # Manufacturing employment (PMI proxy)

# ── Activity / Sentiment ───────────────────────────────────────────
FRED_CFNAI: str = "CFNAI"          # Chicago Fed national activity index
FRED_UMCSENT: str = "UMCSENT"      # U Michigan consumer sentiment
FRED_DRTSCILM: str = "DRTSCILM"    # Senior loan officer C&I lending standards
FRED_HSN1F: str = "HSN1F"          # New home sales
FRED_PERMIT: str = "PERMIT"        # Building permits
FRED_AMTMNO: str = "AMTMNO"        # Manufacturing new orders
FRED_MNFCTRIRSA: str = "MNFCTRIRSA"  # Manufacturing inventory ratio
FRED_GDPNOW: str = "GDPNOW"        # Atlanta Fed GDPNow

# ── ISM / PMI ──────────────────────────────────────────────────────
# ⛔ 2026-09-01：下列兩條 series **自 2016-08 ISM 收回授權後停更**，
#    已從 production 取數邏輯中全數拔除（客戶指令：「已廢棄的資料源一律從資料庫與
#    取數邏輯中徹底拔除，不得留存或發起查詢」）。拔除的三個點：
#      1. `repositories/macro/alternate.py::fetch_ism_pmi` 原方案 1+2（先抓再依時效丟棄）
#      2. `services/macro/us_indicators.py::fetch_all_indicators` 的 `fetch_fred_batch` 預熱清單
#      3. 同檔 PMI 區塊的「series 補救」（補抓 ISPMANPMI 144 期）
#    ⛔ **不得用於 production 取數**。要接 PMI 一律走
#      `repositories/macro/alternate.py::fetch_ism_pmi` 的存活備援鏈。
#    守衛：`tests/test_dead_fred_pmi_series_removed.py`。
#
# ⚠️ 常數本身**保留、未刪**，理由據實寫明（不是「以防萬一」這種空話）：
#    · `FRED_NAPM` —— 仍有**一個真實 consumer**：`ui/helpers/io/data_registry.py`
#      的 `_FRED_SERIES_MAP["PMI"]`（供 `fred_get_next_release_date` 查發布日）。
#      ⚠️ 據實揭露：那條路徑查的是**同一條死 series 的發布日**，形同對死源發問。
#      本批的檔案邊界不含 `ui/`，故**只登記、未處理** —— 留給碰到該檔的下一批。
#      **不得**把「常數還在」讀成「這條 series 還能用」。
#    · `FRED_ISM_PMI` —— production 已 0 consumer；保留的原因是
#      `services/macro/_helpers.py` 仍 re-export 它（該檔在本批邊界外），
#      且 `tests/test_fred_series_ssot.py` 以它驗 SSOT 鏈。
#      **僅供歷史比對 / 跨檔 re-export，不得用於 production 取數。**
#    （consumer 盤點方法：AST walk 全 repo 600 個 .py + `git grep` 全追蹤檔交叉驗，
#      指令與輸出見本批 PR 描述。）
FRED_ISM_PMI: str = "ISPMANPMI"    # ⛔ 2016-08 停更；勿用於 production 取數
FRED_NAPM: str = "NAPM"            # ⛔ 2016-08 停更；勿用於 production 取數
FRED_BSCICP02: str = "BSCICP02USM460S"  # OECD business confidence US

# ── Regional Fed surveys ───────────────────────────────────────────
FRED_PHILLY_FED: str = "GACDFSA066MSFRBPHI"  # Philadelphia Fed manufacturing

# Phil Fed 擴散指數 → 「PMI 刻度」換算常數(唯一消費端:
# repositories/macro/alternate.fetch_ism_pmi 方案 6 替代計):
#     PMI_eq = PHILLY_FED_PMI_BASE + diffusion / PHILLY_FED_TO_PMI_DIVISOR
#
# ⚠️ 來源與侷限(§3.3 反捏造 — 據實登記,勿當成有出處的統計係數):
#   1. 這個 3.0 **不是**官方公式,也不是任何已發表的回歸估計,而是把 ±50 區間的
#      擴散指數線性壓進 33~67 這個「看起來像 PMI」的區間的刻度對映常數,**無出處可引用**。
#   2. 兩個指標母體本就不同:Phil Fed 是**單一聯準區、約 250 家廠商**對「本月 vs 上月」
#      的變化擴散指數;ISM 是**全國 16 大產業**的複合指數。相關性宣稱不可過度延伸。
#   3. 實證反例(2026-07):Phil Fed 由 10.3 跳到 41.4(+31.1),同月官方 ISM 只由
#      53.3 到 55.6(+2.3);換算值 50 + 41.4/3 = 63.8,若當成 ISM PMI 讀將是 1983 年
#      以來最高讀數 —— 與事實不符。
#   → 結論:轉換值**只能看方向,不可當 ISM PMI 的水準值讀**;消費端必須靠
#     `is_proxy=True` + label 後綴揭露,值域檢查(30~70)攔不住這類錯誤。
PHILLY_FED_PMI_BASE: float = 50.0
PHILLY_FED_TO_PMI_DIVISOR: float = 3.0

# ── Financial conditions / Leading indicators ─────────────────────
FRED_NFCI: str = "NFCI"            # Chicago Fed National Financial Conditions
FRED_LEI: str = "USSLIND"          # St. Louis Fed leading index (deprecated; legacy ref)

# ── Volatility ─────────────────────────────────────────────────────
FRED_VXVCLS: str = "VXVCLS"        # CBOE 3M volatility

# ── China macro(v19.493 退役)──────────────────────────────────────
# 中國拖累 China Drag 面板於 v19.493 移除(底層 OECD series 多已停更、且為唯讀不進主分),
# 連帶 CLI/CPI/M2/PMI 四條 China FRED 常數退役。**FRED_CNH_USD(DEXCHUS)保留**(第 37 行),
# 仍供 repositories/fund/fx_and_main.py 的 CNH/CNY→USD 匯率換算使用。
