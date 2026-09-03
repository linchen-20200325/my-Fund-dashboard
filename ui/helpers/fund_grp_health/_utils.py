"""v19.198 P1-6 fund_grp_health 子套件 utility — 從 fund_grp_health_extras 主檔抽出。

_build_fund_dict / _safe_num 兩個共用 helper,供子模組(dividend/investment/risk/signals/ai)
複用。
"""
from __future__ import annotations


def _build_fund_dict(fd_raw: dict, code: str, principal_twd: float,
                     name_hint: str = "") -> dict:
    """把 _auto_fetch_moneydj 回傳的 raw dict 包成 portfolio_funds 標準結構。

    對照 tab3_portfolio.py L1522-1533 的組合建構邏輯。
    invest_twd 欄位給 fund_checkup._compute_fund_health_kpis 算「月配息 TWD」用。

    name_hint:呼叫端已知名(選股池 / 政策表)。線上抓不到真名(如 "AL" 系代碼)時
    用它,而非把代號當名字(v19.497 ALZF9);都沒有才退代號。
    """
    if not fd_raw:
        return {}
    return {
        "code": code,
        "name": fd_raw.get("fund_name") or (name_hint or "").strip() or code,
        "series": fd_raw.get("series"),
        "dividends": fd_raw.get("dividends", []) or [],
        "metrics": fd_raw.get("metrics", {}) or {},
        "moneydj_raw": fd_raw,
        "risk_metrics": fd_raw.get("risk_metrics", {}) or {},
        "currency": (fd_raw.get("currency", "")
                     or (fd_raw.get("metrics", {}) or {}).get("currency", "")),
        "loaded": True,
        "invest_twd": float(principal_twd or 0),
    }


# v19.222 P1-1:_safe_num 收口至 shared/converters.py SSOT
from shared.converters import safe_num as _safe_num  # noqa: E402


# ── 「基期」標籤 SSOT(2026-09-02 T29)──────────────────────────────────────
# `services.rotation.classify_base()` 的四個回傳值 → 畫面用字。
#
# 為什麼要有這一份:同一組字原本**手抄了三份**,而且三份都是**函式內的區域變數**
# (`import` 不到,所以誰也沒辦法沿用誰):
#   · `ui/helpers/fund_grp_health/unified.py::build_merged_extra_columns` 的 `_BASE_LBL`
#     —— 健診大表「基期」欄;
#   · `ui/tab_fund_grp_health.py::_render_low_base_screener` 的 `_base_map`
#     —— 🎯 選基金（低基期）表;
#   · `ui/helpers/fund_grp_health/rotation.py::_render_pairs_body` 的 `_lbl`
#     —— 輪動配對「目前各檔基期」。
# 而 `_render_low_base_screener` 的 caption 還寫著「本區標 🟢 低基期的,大表『基期』欄
# 一定也是 🟢」—— 那句宣稱的前提正是三份用字一致,靠的卻是三次手抄。
#
# ⚠️ 這裡放的是**顯示用字**,不是門檻。門檻(`ROTATION_BUY_SIGMA` / `ROTATION_SELL_SIGMA`)
#    的 SSOT 在 `shared/signal_thresholds.py`,兩者不要混。
BASE_LABELS: dict[str, str] = {
    "high": "🔴 高基期",
    "low": "🟢 低基期",
    "mid": "⚪ 中性",
    "unknown": "⬜ 資料不足",
}

#: 輪動配對專用:同一組字 + 行動提示,並在「資料不足」處指明缺的是 σ。
#: **由 `BASE_LABELS` 衍生**,不是第四份手抄 —— 改上面那一份,這裡跟著動。
BASE_LABELS_ROTATION: dict[str, str] = {
    **BASE_LABELS,
    "high": f'{BASE_LABELS["high"]}(可賣)',
    "low": f'{BASE_LABELS["low"]}(可買)',
    # 「⬜ 資料不足」→「⬜ σ 資料不足」:輪動這一段缺的具體是 σ rank,
    # 講明白比較有用(下一行的 `_render_insufficient_note()` 也是這樣講)。
    "unknown": BASE_LABELS["unknown"].replace("⬜ ", "⬜ σ ", 1),
}
