"""ui/helpers/fund_grp_health/unified.py — 健診總表寬表合併器(v19.408)。

user 要求:組合健診原本對同一批基金重複畫 3 張逐檔表(HWM σ / 風險對比 / MK 買賣點),
去重複合併進「健診總表」成一張大表。本模組提供純函式合併器(無 streamlit,可單元測試):
把 3 組 by-code 欄位 join 成 (欄序, code→欄值),現價等重複欄「先到先得」去重。

資料來源仍是各表的單一 data 函式(`risk.hwm_sigma_by_code` / `risk.risk_compare_by_code` /
`signals.mk_signal_by_code`)—— 不重算、不偽造(§1);缺值由來源填 '—'。
"""
from __future__ import annotations


def build_merged_extra_columns(funds: list, phase: str = "", score=None) -> tuple:
    """回傳 (col_order, combined)。

    - col_order:list[str],新欄依 HWM σ → 風險 → MK 出現順序、去重後的欄名。
    - combined:dict[code -> {欄名: 值}],同名欄「先到先得」(如「現價」HWM 版優先,MK 版略過)。

    phase/score 給 MK 訊號用(由呼叫端從 session_state.phase_info 取);缺則 MK 訊號欄 '—'。
    """
    from ui.helpers.fund_grp_health.risk import hwm_sigma_by_code, risk_compare_by_code
    from ui.helpers.fund_grp_health.signals import mk_signal_by_code

    maps = [
        hwm_sigma_by_code(funds),
        risk_compare_by_code(funds),
        mk_signal_by_code(funds, phase, score),
    ]
    combined: dict = {}
    col_order: list[str] = []
    for _m in maps:
        for _code, _cols in _m.items():
            slot = combined.setdefault(_code, {})
            for _k, _v in _cols.items():
                if _k not in slot:          # 先到先得 → 重複欄(現價)去重
                    slot[_k] = _v
        for _cols in _m.values():
            for _k in _cols:
                if _k not in col_order:
                    col_order.append(_k)
    return col_order, combined
