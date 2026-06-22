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
FRED_ISM_PMI: str = "ISPMANPMI"    # ISM manufacturing PMI
FRED_NAPM: str = "NAPM"            # NAPM manufacturing (legacy)
FRED_BSCICP02: str = "BSCICP02USM460S"  # OECD business confidence US

# ── Regional Fed surveys ───────────────────────────────────────────
FRED_PHILLY_FED: str = "GACDFSA066MSFRBPHI"  # Philadelphia Fed manufacturing

# ── Financial conditions / Leading indicators ─────────────────────
FRED_NFCI: str = "NFCI"            # Chicago Fed National Financial Conditions
FRED_LEI: str = "USSLIND"          # St. Louis Fed leading index (deprecated; legacy ref)

# ── Volatility ─────────────────────────────────────────────────────
FRED_VXVCLS: str = "VXVCLS"        # CBOE 3M volatility
