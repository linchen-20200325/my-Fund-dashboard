"""repositories/macro/china.py — China macro batch fetcher(B1 拆自 macro_repository v19.205).

從原 1078 LOC god module 拆出:
- _CHINA_FRED_SPECS(5 條 FRED series spec)
- fetch_china_macro(並行抓 China macro)
依賴 fred.fetch_fred_batch。
"""
from __future__ import annotations

import pandas as pd

from shared.fred_series import (
    FRED_CHN_CPI,
    FRED_CHN_M2,
    FRED_CHN_OECD_CLI,
    FRED_CHN_PMI,
    FRED_CNH_USD,
)

from .fred import fetch_fred_batch


# ════════════════════════════════════════════════════════════════════════════
# v19.113 — China macro batch(方向 B,對稱 Stock v18.270)
# 5 個 FRED series:DEXCHUS (CNY/USD) + OECD CLI + CPI + M2 + PMI proxy
# ════════════════════════════════════════════════════════════════════════════

# China FRED series specs(SSOT 從 shared/fred_series 引入,n 為各序列建議回傳筆數)
# DEXCHUS 為日頻(取 ~2y trading days);其餘 4 條為月頻(取 ~10y 月度)
_CHINA_FRED_SPECS: list[tuple[str, int]] = [
    (FRED_CNH_USD,        500),    # DEXCHUS — 日頻,FX,~2 年
    (FRED_CHN_OECD_CLI,   120),    # CHNLOLITONOSTSAM — OECD CLI 月頻
    (FRED_CHN_CPI,        120),    # CPALTT01CNM659N — OECD CPI YoY 月頻
    (FRED_CHN_M2,         120),    # MABMM301CNM189S — M2 廣義貨幣 月頻
    (FRED_CHN_PMI,        120),    # BSCICP03CNM665S — OECD 商業信心 月頻
]


def fetch_china_macro(api_key: str) -> dict[str, pd.DataFrame]:
    """並行抓 5 條 China macro FRED series。

    Returns
    -------
    dict[series_id, pd.DataFrame]
        key 為 FRED series ID,value 為 fetch_fred 結果(含 source/fetched_at)。
        失敗 series 對應空 DataFrame(caller 須 .empty 判斷);api_key 空 → 全空 dict。

    Notes
    -----
    - 對稱 Stock 端 tw_macro.fetch_china_macro 等價設計。
    - 4 條 OECD MEI 系列(CLI/CPI/PMI/M2)在 FRED 為 OECD 二手轉發,
      發布延遲 ~月後 60 天(較 US 月頻指標慢)。
    - 若 FRED 對某條 series 回 404(下架/改名),對應 DataFrame 為空,
      不偽造數值(§1 fail loud)。
    """
    if not api_key:
        return {}
    return fetch_fred_batch(_CHINA_FRED_SPECS, api_key)


