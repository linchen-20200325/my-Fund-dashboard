"""services/fund_grp_health/signals.py — ⑩ 買賣點的**逐檔資料函式**(L2,零 streamlit、零 `ui.*`)。

2026-10-13 客戶裁示(LINE 推播與舊 UI 解耦):`mk_signal_by_code`(及 `_first_num`)由
`ui/helpers/fund_grp_health/signals.py` 搬來 —— 每週換檔推播經 `build_merged_extra_columns`
依賴它,而原檔 module 頂層 `import streamlit`。唯一的差異見 `mk_signal_by_code` docstring
(`mk_fund_signal` 改由呼叫端注入)。渲染函式仍留在原檔。
"""
from __future__ import annotations

from services.fund_grp_health._utils import _safe_num
from shared.data_quality import BUY_MODE_RANGE_FALLBACK as _FALLBACK_BUY_MODE


def _first_num(*vals):
    """依序取第一個**非 None** 的數值(§1:0.0 是合法值,不可用 `or` 略過)。"""
    for _v in vals:
        _n = _safe_num(_v)
        if _n is not None:
            return _n
    return None


def mk_signal_by_code(funds: list, phase: str, score, *,
                      signal_fn=None, signal_unavailable_label: str = "") -> dict:
    """⑩ 買賣點逐檔欄位(keyed by code)。供健診總表合併 + 標準表共用(單一資料源)。

    phase/score 由呼叫端從 st.session_state.phase_info 取;缺 → 訊號欄 '—',
    但買賣水平線 / 現價位階仍計算(不依景氣)。缺項 '—' 不偽造(§1)。

    2026-10-13(LINE 推播與舊 UI 解耦)—— 本函式由 `ui/helpers/fund_grp_health/signals.py`
    原封搬來,**只有一處不同:`mk_fund_signal` 改由呼叫端注入**。
    原本這裡是 `from ui.helpers.macro_helpers import mk_fund_signal`,而該函式讀
    `st.session_state`(L3 專屬),L2 不得 import。所以:
      - `signal_fn`:等同原本 import 到的 `mk_fund_signal`;`None` = 沒有訊號函式可用。
      - `signal_unavailable_label`:等同原本 import 失敗時的 `_import_err` 字串。
    舊 UI 走 `ui/helpers/fund_grp_health/signals.py::mk_signal_by_code`(原 try/import 原樣
    留在那裡,解析完再注入),行為與搬移前逐字相同。
    排程(週報)呼叫時 `phase=""` —— 原本就**不會**呼叫 `mk_fund_signal`(下面 `and phase`),
    兩欄恆為 '—';注入與否不影響它用到的任何欄。
    """
    _import_err = signal_unavailable_label or ""
    mk_fund_signal = signal_fn

    out: dict = {}
    for _f in funds:
        _code = _f.get("code", "?")
        _m = _f.get("metrics") or {}
        _mj = _f.get("moneydj_raw") or {}

        _asset_class = "—"
        _sig_label = _import_err or "—"
        if mk_fund_signal is not None and phase:
            try:
                _sig = mk_fund_signal(_f, phase, score)
                _asset_class = _sig.get("asset_class", "—")
                _sig_label = _sig.get("label", "—")
            except Exception as _e_sig:  # noqa: BLE001
                # §1:原本靜默 pass → 「操作訊號」欄停在「—」,把**算爆了**偽裝成
                # 「這檔沒訊號」。同 `services/fund_row.py` 對 吃本金 / 3-3-3 的處置。
                import sys as _sys_sig
                print(f"[grp_health/signals] {_code} mk_fund_signal 失敗:"
                      f"{type(_e_sig).__name__}: {_e_sig}", file=_sys_sig.stderr)
                _sig_label = f"⚠️ 計算失敗({type(_e_sig).__name__})"

        # §1:`a or b` 把**合法的 0.0** 當缺值(買賣點價位理論上 >0,但 nav 由
        # metrics 或 wb05 兩路來,顯式 is None 才不會在 0 附近悄悄換來源)。
        _b1 = _first_num(_m.get("buy1"), _mj.get("buy1"))
        _b3 = _first_num(_m.get("buy3"), _mj.get("buy3"))
        _s1 = _first_num(_m.get("sell1"), _mj.get("sell1"))
        _s3 = _first_num(_m.get("sell3"), _mj.get("sell3"))
        _nav = _first_num(_m.get("nav"), _mj.get("nav_latest"))

        if _nav is None:
            _zone = "—"
        elif _b3 is not None and _nav <= _b3:
            _zone = "🟢 ≤買3(深跌)"
        elif _b1 is not None and _nav <= _b1:
            _zone = "🟢 ≤買1(小跌)"
        elif _s3 is not None and _nav >= _s3:
            _zone = "🔴 ≥賣3(大漲)"
        elif _s1 is not None and _nav >= _s1:
            _zone = "🟡 ≥賣1(小漲)"
        elif _b1 is not None and _s1 is not None:
            _zone = "⚪ 區間內"
        else:
            # BL-0440(§1 Missing ≠ 中性):「區間內」是「高於買1 且低於賣1」的宣稱,
            # 買1 或賣1 任一缺就**證不出來**(買3／賣3 只界定更外側)。原本落 else →
            # 「⚪ 區間內」,把缺料說成「價位正常」。改走 repo 既有用字「⬜ 無法判定」。
            _zone = "⬜ 無法判定（買1／賣1未取得）"
        # BL-0440 j:`calc_metrics` n<20 筆時買賣點改用「區間σ(資料不足)」fallback
        # (既有 `buy_mode` key);位階照判,但必須揭露品質,不能和正常 σ 通道同樣呈現。
        if (_m.get("buy_mode") == _FALLBACK_BUY_MODE
                and _zone != "—" and not _zone.startswith("⬜")):
            _zone += "（⚠️ 區間σ·資料不足）"

        out[_code] = {
            "基金屬性": _asset_class,
            "操作訊號": _sig_label,
            "買 3 (深跌)": f"{_b3:.2f}" if _b3 is not None else "—",
            "買 1 (小跌)": f"{_b1:.2f}" if _b1 is not None else "—",
            "現價": f"{_nav:.2f}" if _nav is not None else "—",
            "賣 1 (小漲)": f"{_s1:.2f}" if _s1 is not None else "—",
            "賣 3 (大漲)": f"{_s3:.2f}" if _s3 is not None else "—",
            "現價位階": _zone,
        }
    return out
