"""services/fund_grp_health/risk.py — ⑦ HWM σ / ⑧ 風險對比 的**逐檔資料函式**(L2,零 streamlit)。

2026-10-13 客戶裁示(LINE 推播與舊 UI 解耦):`hwm_sigma_by_code` / `risk_compare_by_code`
(及後者用到的 `_PERIOD_KEYS` / `_lookup_risk_table` / `_local_first`)由
`ui/helpers/fund_grp_health/risk.py` **原封搬來**(邏輯一字未改)—— 每週換檔推播經
`build_merged_extra_columns` 依賴它們,而原檔 module 頂層 `import streamlit`。
表格渲染(`_render_*`)仍留在原檔,改從這裡 import 同一份資料函式(SSOT,不複製)。
"""
from __future__ import annotations

from services.fund_grp_health._utils import _safe_num


def hwm_sigma_by_code(funds: list) -> dict:
    """⑦ HWM σ 逐檔欄位(keyed by code)。供「健診總表」合併 + 標準表共用(單一資料源)。

    SSOT:services/precision_service.py calc_hwm_sigma_levels。缺資料 → '—'(§1 不偽造)。
    """
    out: dict = {}
    try:
        from services.precision_service import calc_hwm_sigma_levels
    except Exception as _e_imp:  # noqa: BLE001 — 模組載入失敗 → 全檔缺值,不炸
        # 原本靜默:整組 σ/HWM 5 欄一起消失,user 只看到大表少了一整區,以為功能壞了。
        # 補 log + 讓「HWM 位階」欄自己說出是**載入失敗**,不是這些基金沒資料(§1)。
        import sys as _sys_imp
        print(f"[grp_health/risk] precision_service 載入失敗,σ/HWM 欄全缺:"
              f"{type(_e_imp).__name__}: {_e_imp}", file=_sys_imp.stderr)
        _err = f"⬜ σ 模組載入失敗({type(_e_imp).__name__})"
        return {(_f.get("code") or "?"): {
            "現價": "—", "HWM": "—", "距 HWM %": "—", "σ rank": "—", "HWM 位階": _err,
        } for _f in funds}
    for _f in funds:
        _code = _f.get("code", "?")
        _series = _f.get("series")
        _blank = {"現價": "—", "HWM": "—", "距 HWM %": "—", "σ rank": "—"}
        if _series is None or len(_series) < 30:
            out[_code] = {**_blank, "HWM 位階": "⬜ NAV 不足 30 天"}
            continue
        _r = calc_hwm_sigma_levels(_series)
        if _r.get("error"):
            out[_code] = {**_blank, "HWM 位階": f"⬜ {_r['error']}"}
            continue
        out[_code] = {
            "現價": f"{_r['current_nav']:.2f}",
            "HWM": f"{_r['hwm']:.2f}",
            "距 HWM %": f"{_r['dist_to_hwm_pct']:+.2f}%",
            "σ rank": f"{_r['sigma_rank']:+.2f}σ",
            "HWM 位階": f"{_r.get('label', '—')}",
        }
    return out


# v19.181 Bug 3 fix: MoneyDJ wb07 risk_metrics 是 **nested** 結構
# ({risk_table: {期間: {標準差/Sharpe/Alpha/Beta}}}),不是 flat dict。
_PERIOD_KEYS = ("近一年", "一年", "近1年", "1年", "近三年", "三年", "近六月", "六個月")


def _lookup_risk_table(rm: dict, *zh_keys: str):
    """從 risk_table 多期間找第一個非空值,zh_keys 對齊 MoneyDJ 中文欄位名。"""
    rt = (rm or {}).get("risk_table") or {}
    for _p in _PERIOD_KEYS:
        _row = rt.get(_p) or {}
        for _k in zh_keys:
            n = _safe_num(_row.get(_k))
            if n is not None:
                return n
    return None


def _local_first(local, rm: dict, *zh_keys):
    """本地 metrics 值優先,**只有真的缺(None)** 才退到 MoneyDJ wb07 風險表。

    §1:不用 `a or b` —— 0.0 是 falsy 但為合法值(Sharpe / Alpha 恰好 0)。
    """
    _v = _safe_num(local)
    return _v if _v is not None else _lookup_risk_table(rm, *zh_keys)


def risk_compare_by_code(funds: list) -> dict:
    """⑧ 風險指標逐檔欄位(keyed by code):σ / Sharpe / Sortino / Alpha / Beta。

    資料源:metrics(本地算)優先 → MoneyDJ wb07 risk_table nested fallback。
    缺項 '—',不偽造(§1)。供健診總表合併 + 標準表共用(單一資料源)。
    """
    def _fmt(v):
        return f"{v:.2f}" if v is not None else "—"

    out: dict = {}
    for _f in funds:
        _code = _f.get("code", "?")
        _mj = _f.get("moneydj_raw") or {}
        _m = _f.get("metrics") or {}
        _rm = _f.get("risk_metrics") or _mj.get("risk_metrics") or {}

        # §1:`a or b` 會把**合法的 0.0** 誤當缺值退到 fallback ——
        # Sharpe / Alpha 恰好 0.00(報酬等於無風險利率 / 零超額)是真實可能值,
        # 用 `or` 會改抓 MoneyDJ wb07 另一個期間的數字,兩個來源在同一格悄悄互換。
        # `_local_first` 改用顯式 `is None` 判斷,0.0 保留為 0.0。
        _sigma = _local_first(_m.get("std_1y"), _rm, "標準差", "年化標準差")
        _sharpe = _local_first(_m.get("sharpe"), _rm, "Sharpe", "Sharpe Ratio", "夏普值")
        _sortino = _safe_num(_m.get("sortino"))  # wb07 無此欄,本地未算 → —
        _alpha = _local_first(_m.get("alpha"), _rm, "Alpha", "α")
        _beta = _local_first(_m.get("beta"), _rm, "Beta", "β")

        out[_code] = {
            "σ (年化%)": _fmt(_sigma), "Sharpe": _fmt(_sharpe),
            "Sortino": _fmt(_sortino), "Alpha": _fmt(_alpha), "Beta": _fmt(_beta),
        }
    return out
