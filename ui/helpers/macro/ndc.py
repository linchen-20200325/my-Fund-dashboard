"""ui/helpers/macro/ndc.py — L3:台灣景氣對策信號(NDC monitoring)分數取數 helper。

供深度強化模組動態門檻用(v19.459):
- 模組①(allocation_ladder)動態停利/加碼 Z 門檻:綠燈放寬停利、紅燈收緊加碼。
- 模組②(zscore_engine)再平衡訊號的動態門檻。

抓 `repositories.macro_tw_local_repository.fetch_ndc_signal_history`(EX-PASSTHRU-1:UI 可直呼
此自足 TW-local fetcher)→ 取 `score_latest`(官方 NDC 綜合分數 9~45)。抓不到 → None
(呼叫端退預設門檻,§1 不假造景氣燈)。`@st.cache_data` TTL 15 分(NDC 為月頻,抓一次即可,
兩個 tab 共用同一份快取,不重複打網路)。
"""
from __future__ import annotations

from typing import Optional


def ndc_score_from_result(res) -> Optional[int]:
    """從 fetch_ndc_signal_history 結果取 score_latest(9~45)。純函式,離線可測。

    非 dict / 非數 / 超域 → None(§1 不硬歸)。
    """
    if not isinstance(res, dict):
        return None
    try:
        _s = int(res.get("score_latest"))
    except (TypeError, ValueError):
        return None
    return _s if 9 <= _s <= 45 else None


def get_ndc_score() -> Optional[int]:
    """台灣景氣對策信號最新分數(9~45)。抓不到 / 無 streamlit → None(退預設門檻)。

    快取由內層 `_cached_ndc_score`(@st.cache_data TTL_15MIN)承載;本層負責 streamlit 缺席時
    的降級(測試 / headless)。
    """
    try:
        import streamlit as st  # noqa: PLC0415
    except ImportError:
        return None
    try:
        return _cached_ndc_score()
    except Exception:  # noqa: BLE001 — 抓取/快取任何失敗 → None,呼叫端退預設門檻(不阻斷 UI)
        return None


def _fetch_ndc_score() -> Optional[int]:
    """實際抓取(未快取):讀 FINMIND_TOKEN → fetch_ndc_signal_history → score_latest。"""
    import streamlit as st  # noqa: PLC0415

    from repositories.macro_tw_local_repository import fetch_ndc_signal_history  # noqa: PLC0415
    _tok = ""
    try:
        _tok = st.secrets.get("FINMIND_TOKEN", "")           # 空 → FinMind 匿名額度
    except Exception:  # noqa: BLE001 — 無 secrets(本地/測試)→ 匿名
        _tok = ""
    return ndc_score_from_result(fetch_ndc_signal_history(token=_tok))


try:
    import streamlit as _st_mod

    from shared.ttls import TTL_15MIN as _TTL

    @_st_mod.cache_data(ttl=_TTL, show_spinner=False)
    def _cached_ndc_score() -> Optional[int]:
        return _fetch_ndc_score()
except Exception:  # noqa: BLE001 — 無 streamlit(headless/測試)→ 提供無快取版,get_ndc_score 已擋
    def _cached_ndc_score() -> Optional[int]:
        return _fetch_ndc_score()


__all__ = ["ndc_score_from_result", "get_ndc_score"]
