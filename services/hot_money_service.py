"""services/hot_money_service.py — 熱錢資料 L2 facade(v19.375 B2 分層歸位)。

§8.2 硬規則 4:L3 UI 不得直接 import L1 repository fetcher(cache 須集中於 L2)。
`ui/hot_money.py` 原本在 refresh / render 兩處直接 `from repositories.hot_money_repository
import ...`,屬未登錄的 L3→L1 直呼。本 facade 提供 L2 取數入口,內部走 L1
`repositories.hot_money_repository`(L2→L1 下行,合規),UI 端改呼本 facade。

純 facade,無業務轉換 — 訊號分類仍為 `ui.hot_money.build_signals` 純函式;
本層僅集中「取兩序列」的資料存取點。lazy import 避免 import-time L1 連鎖載入。
"""
from __future__ import annotations


def fetch_hot_money_frames(days: int, token: str = ""):
    """取外資淨買賣超序列 + USDTWD 匯率序列(L2 facade → L1 hot_money_repository)。

    Args:
        days:  回看天數。
        token: FinMind token(外資來源用),預設空字串。

    Returns:
        (flow_df, fx_df, flow_err, fx_err) — 沿用 L1 tuple 形狀展平,
        UI 端語意零改動(空 df + err 字串為 fail-loud 旗標,§1)。
    """
    from repositories.hot_money_repository import (
        fetch_foreign_flow_series,
        fetch_usdtwd_series,
    )
    flow_df, flow_err = fetch_foreign_flow_series(days, token)
    fx_df, fx_err = fetch_usdtwd_series(days)
    return flow_df, fx_df, flow_err, fx_err
