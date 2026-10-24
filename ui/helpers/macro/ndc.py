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


def ndc_status_from_result(res) -> dict:
    """BL-0441:fetch_ndc_signal_history 結果 → {score, status, detail}。純函式,離線可測。

    status 三態(皆不改門檻,只揭露為何退預設):
    - 'ok'          :拿到 9~45 分數。
    - 'unavailable' :來源不可用(fetcher 回報 API 失敗 / 回傳非 dict)。
    - 'no_data'     :來源有回應但真的沒有可用分數(筆數不足 / 無資料 / 超域)。
    ('fetch_error' 由 get_ndc_status 在本層例外時給。)
    """
    if not isinstance(res, dict):
        return {"score": None, "status": "unavailable", "detail": "景氣來源回傳格式異常"}
    _sc = ndc_score_from_result(res)
    if _sc is not None:
        return {"score": _sc, "status": "ok", "detail": res.get("source") or ""}
    _err = str(res.get("error") or "")
    if "失敗" in _err:
        return {"score": None, "status": "unavailable", "detail": _err}
    return {"score": None, "status": "no_data", "detail": _err or "景氣來源無可用分數"}


NDC_STATUS_TEXT = {
    "ok": "景氣燈號取得",
    "fetch_error": "景氣燈號取數失敗",
    "unavailable": "景氣來源不可用",
    "no_data": "景氣來源無資料",
}


def get_ndc_status() -> dict:
    """BL-0441:{score, status, detail};status ∈ ok / fetch_error / unavailable / no_data。

    無 streamlit(headless)→ unavailable;本層抓取/快取例外 → fetch_error。
    """
    try:
        import streamlit as st  # noqa: PLC0415,F401
    except ImportError:
        return {"score": None, "status": "unavailable", "detail": "無 streamlit 執行環境"}
    try:
        _r = _cached_ndc_score()
    except Exception as _e:  # noqa: BLE001 — 取數失敗要可見,不冒充「無資料」
        return {"score": None, "status": "fetch_error", "detail": type(_e).__name__}
    return _r if isinstance(_r, dict) else {"score": None, "status": "unavailable",
                                            "detail": "景氣狀態格式異常"}


def get_ndc_score() -> Optional[int]:
    """台灣景氣對策信號最新分數(9~45)。抓不到 / 無 streamlit → None(退預設門檻)。

    BL-0441:為何是 None 請改用 get_ndc_status() 取得(三態可見);本函式保留舊介面。
    """
    return get_ndc_status().get("score")


def _fetch_ndc_score() -> dict:
    """實際抓取(未快取):讀 FINMIND_TOKEN → fetch_ndc_signal_history → 狀態 dict(BL-0441;名稱沿用以免牽動快取登記)。"""
    from repositories.macro_tw_local_repository import fetch_ndc_signal_history  # noqa: PLC0415

    # 2026-09-04 稽核 F3:改走 `infra.config.get_secret`(§2.1 SSOT)。
    # 本呼叫點餵的是**另一顆** fetcher(`fetch_ndc_signal_history`,自己的 cache key
    # 家族),所以它**不會**與熱錢卡的 `(days, token)` 撞在一起 —— 也就是說,
    # 這一處**不是** F3 所指的那個 cache key 分岔。仍然一併收進來的理由有三:
    #   (a) 它有 F3 的**另一半**病:token 只存在於 `os.environ` 時,裸 `st.secrets`
    #       讀不到 → 靜默退成 FinMind 匿名額度(有授權卻不用),是真的行為差異;
    #   (b) `get_secret` 內部已含同一組 try/except + `os.environ` fallback,
    #       換過來之後這裡的 try/except 是純粹重複,行為嚴格不劣;
    #   (c) 更要緊的是**守衛的完整性**:F3 的守衛掃的是「全 repo 還有沒有裸讀
    #       FINMIND_TOKEN」。若在這裡留一個「因為它接的是別顆 fetcher 所以豁免」
    #       的洞,那個豁免條件本身就得靠人記住、且會被下一輪拿來論證第三個站點 ——
    #       本 repo 已經因為「這個站點沒關係」連錯兩輪(P2 漏 tab5、F3 才補)。
    #       **不留但書,守衛才守得住。**
    from infra.config import get_secret as _ndc_get_secret  # noqa: PLC0415
    _tok = str(_ndc_get_secret("FINMIND_TOKEN", "") or "")   # 空 → FinMind 匿名額度
    # BL-0441:回 {score, status, detail}(保留失敗原因三態),不再只回 score。
    return ndc_status_from_result(fetch_ndc_signal_history(token=_tok))


try:
    import streamlit as _st_mod

    from shared.ttls import TTL_15MIN as _TTL

    @_st_mod.cache_data(ttl=_TTL, show_spinner=False)
    def _cached_ndc_score() -> dict:
        return _fetch_ndc_score()
except Exception:  # noqa: BLE001 — 無 streamlit(headless/測試)→ 提供無快取版,get_ndc_score 已擋
    def _cached_ndc_score() -> dict:
        return _fetch_ndc_score()


__all__ = ["ndc_score_from_result", "ndc_status_from_result", "NDC_STATUS_TEXT",
           "get_ndc_status", "get_ndc_score"]
