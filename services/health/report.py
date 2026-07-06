"""v19.181 services — 「健康分析 / 配息相關」共用 row builder SSOT(L2 純函式,zero-IO)。

設計目的
========
Tab3「組合配置管理」與「基金組合健診 Tab」3 表渲染共用:
  ① 健康分析表(build_health_analysis_row)
  ② 配息相關表(build_dividend_summary_row)
  ③ 實際購買結果表 — 仍走既有 `tab_fund_grp_health.process_one_fund`(不動)

每個 row builder 走所有指標的既有 L2 SSOT helper(不重複實作),只負責「組欄位」。

對外 API
========
- ``build_health_analysis_row(fd, code, holding_years=None, ...)`` 健康分析行
- ``build_dividend_summary_row(fd, code, principal_twd, holding_years=None, ...)`` 配息相關行
- ``HEALTH_COLUMNS`` / ``DIVIDEND_COLUMNS`` — UI column_config keys 列表
"""
from __future__ import annotations

from typing import Optional


# v19.222 P1-1:_safe_float 收口至 shared/converters.py SSOT
from shared.converters import safe_float as _safe_float  # noqa: E402



def _compute_holding_years(fd: dict) -> Optional[float]:
    """從 inception_date metadata 或 NAV 序列推算「成立至今」年數(MK 3-3-3 用)。
    注意:這是「基金成立年數」非「user 持有年數」。
    user 持有年數應由 caller 從 ledger 傳入。
    """
    # v19.308：改走 SSOT services.fund_screening.fund_inception_years（優先 MoneyDJ
    # 現成成立日，缺則 NAV 序列推算），與 3-3-3 篩選 / 戰情室同源，不再各自實作。
    try:
        _mj = fd.get("moneydj_raw") or {}
        _inception = (fd.get("inception_date")
                      or (fd.get("metrics") or {}).get("inception_date")
                      or _mj.get("inception_date"))
        s = fd.get("series")
        if s is None:  # 顯式 None 判斷，避免 pandas Series.__bool__ ambiguous
            s = _mj.get("series")
        from services.fund_screening import fund_inception_years
        return fund_inception_years(_inception, s)
    except Exception as e:
        # v19.184 F-MED:加 stderr log 不靜默(§3.3 反捏造)
        import sys as _sys
        print(f'[fund_health_report] _compute_holding_years fail: '
              f'{type(e).__name__}: {e}', file=_sys.stderr)
        return None


def build_health_analysis_row(
    fd: dict,
    code: str,
    holding_years: Optional[float] = None,
) -> dict:
    """健康分析 row(SSOT):4D Grade + Sharpe + Sortino + Calmar + Alpha + Expense + Max DD + 3Y / 5Y 年化 + 3-3-3 篩。

    所有指標走 L2 既有 SSOT,不重複計算。

    Args:
        fd: 基金 dict(平坦 / 嵌套均接,內部 normalize)
        code: 基金代號(顯示用)
        holding_years: user 持有年數 — None 則用「成立至今年數」(3-3-3 用)

    Returns:
        dict — UI 直接 render 成 dataframe row
    """
    # ─── shape normalize(對齊 v19.178 SSOT 模式)──
    if "moneydj_raw" not in fd and "perf" in fd:
        fd = {
            "moneydj_raw": fd,
            "metrics": fd.get("metrics") or {},
            "series": fd.get("series"),
            "perf_source": fd.get("perf_source"),
        }
    m = fd.get("metrics") or {}
    mj = fd.get("moneydj_raw") or {}

    # ─── 4D Grade SSOT ─────────────────────────────────────
    from services.health.grade import compute_4d_health
    from services.fund_total_return import compute_1y_total_return
    from services.health.dividend import (
        _resolve_adr_with_fallback,
        check_333_principle,
    )
    # v19.184 F-MED:silent except 全改加 stderr log(§3.3 反捏造)
    import sys as _sys
    try:
        tr1y_pct, _ = compute_1y_total_return(fd)
    except Exception as e:
        print(f'[fund_health_report] health_row compute_1y_total_return fail: '
              f'{type(e).__name__}: {e}', file=_sys.stderr)
        tr1y_pct = None
    try:
        # v19.177 _resolve_adr_with_fallback 回 (value, source) tuple
        adr_pct, _adr_src = _resolve_adr_with_fallback(fd)
    except Exception as e:
        print(f'[fund_health_report] health_row _resolve_adr_with_fallback fail: '
              f'{type(e).__name__}: {e}', file=_sys.stderr)
        adr_pct, _adr_src = None, "—"
    sharpe = _safe_float(m.get("sharpe"))
    sigma = _safe_float(m.get("std_1y"))
    try:
        _4d = compute_4d_health(
            tr1y_pct=tr1y_pct, adr_pct=adr_pct,
            sharpe=sharpe, sigma_pct=sigma, ma_dir=None,
        )
    except Exception as e:
        print(f'[fund_health_report] health_row compute_4d_health fail: '
              f'{type(e).__name__}: {e}', file=_sys.stderr)
        _4d = {}

    # ─── 6F 進階指標 SSOT(走 calc_fund_factor_score)──────
    # 註:calc_fund_factor_score grade deprecated for grading(走 4D),
    # 但 factors[*] 個別 value 仍是 Sortino/Calmar/Alpha/Expense SSOT。
    from services.portfolio_service import calc_fund_factor_score
    try:
        # v19.182 FIX:calc_fund_factor_score 需 {metrics, perf} 兩個 sub-dict。
        # 舊版 `_fdata = fd if "perf" in fd else mj` 在「內部已 normalize」後 fd 變 nested
        # (有 moneydj_raw 但無 top-level perf)→ 走 else 拿 mj(無 metrics)→
        # 抓不到 sortino/calmar/expense → 3 Tab 全顯示「—」。
        # 修法:無論 normalize 與否,顯式組 {metrics, perf} dict。perf 從 fd 或 mj 拿。
        # v19.191:加 moneydj_raw 透傳,讓 portfolio_service 的 expense_ratio mgmt_fee fallback
        # 找得到(否則 fallback 永遠 dead code)。
        _pf = (fd.get("perf") if "perf" in fd else mj.get("perf")) or {}
        # v19.290:_pf["1Y"] 常缺(wb01/本地 350d+窗口兩條寫入路徑都有各自的
        # gate,保單代碼短窗基金兩條都不滿足)→ Alpha(= tr1y - 配息率)永遠算
        # 不出來。tr1y_pct 在上面第 92 行已經走 compute_1y_total_return()
        # 的完整 SSOT fallback chain(perf.1Y → ret_1y_total → NAV 外推)算好,
        # 這裡直接借用,不重算、不新增分支。
        if _pf.get("1Y") is None and tr1y_pct is not None:
            _pf = {**_pf, "1Y": tr1y_pct}
        _fdata = {"metrics": m, "perf": _pf, "moneydj_raw": mj}
        risk_table = mj.get("risk_metrics") or fd.get("risk_metrics") or {}
        _6f = calc_fund_factor_score(_fdata, risk_table=risk_table)
        _factors = _6f.get("factors") or {}
    except Exception as e:
        print(f'[fund_health_report] calc_fund_factor_score fail: '
              f'{type(e).__name__}: {e}', file=_sys.stderr)
        _factors = {}
    sortino_v = (_factors.get("Sortino") or {}).get("value")
    calmar_v = (_factors.get("Calmar") or {}).get("value")
    alpha_v = (_factors.get("Alpha") or {}).get("value")
    expense_v = (_factors.get("ExpenseRatio") or {}).get("value")

    # ─── Max DD / 3Y / 5Y(metrics SSOT)─────────────────
    max_dd = _safe_float(m.get("max_drawdown"))
    ret_3y_ann = _safe_float(m.get("ret_3y_ann"))
    ret_5y_ann = _safe_float(m.get("ret_5y_ann"))
    if ret_3y_ann is None:
        # 舊 schema fallback:ret_3y_cum → 開根
        _cum3 = _safe_float(m.get("ret_3y_cum") or m.get("ret_3y"))
        if _cum3 is not None:
            ret_3y_ann = ((1.0 + _cum3 / 100.0) ** (1.0 / 3.0) - 1.0) * 100.0
    # v19.298 FIX: 最終 fallback — MoneyDJ wb01 perf["3Y"] 累計 → 年化
    # NAV 序列 < 756 筆時（保險子網域封鎖或短窗口），wb01 三年期總報酬為唯一替代來源。
    if ret_3y_ann is None:
        _perf_report = (fd.get("perf") or (fd.get("moneydj_raw") or {}).get("perf") or {})
        _wb01_3y = _safe_float(_perf_report.get("3Y"))
        if _wb01_3y is not None:
            try:
                ret_3y_ann = round(((1.0 + _wb01_3y / 100.0) ** (1.0 / 3.0) - 1.0) * 100.0, 2)
            except (ValueError, ZeroDivisionError, OverflowError):
                pass
    if ret_5y_ann is None:
        _cum5 = _safe_float(m.get("ret_5y_cum") or m.get("ret_5y"))
        if _cum5 is not None:
            ret_5y_ann = ((1.0 + _cum5 / 100.0) ** (1.0 / 5.0) - 1.0) * 100.0
    # v19.299 FIX: 最終 fallback — MoneyDJ wb01 perf["5Y"] 累計 → 年化
    # NAV 序列 < 1260 筆時（保險子網域封鎖），wb01 五年期總報酬為唯一真實替代來源。
    # wb01 已在 fetch_fund_details() 拉取，非捏造值。
    if ret_5y_ann is None:
        _perf_report5 = (fd.get("perf") or (fd.get("moneydj_raw") or {}).get("perf") or {})
        _wb01_5y = _safe_float(_perf_report5.get("5Y"))
        if _wb01_5y is not None:
            try:
                ret_5y_ann = round(((1.0 + _wb01_5y / 100.0) ** (1.0 / 5.0) - 1.0) * 100.0, 2)
            except (ValueError, ZeroDivisionError, OverflowError):
                pass

    # ─── 3-3-3 篩(成立年數 + 3Y 年化)SSOT ─────────────
    years_inception = holding_years if holding_years is not None else _compute_holding_years(fd)
    try:
        _333 = check_333_principle(years_inception, ret_3y_ann)
    except Exception as e:
        print(f'[fund_health_report] check_333_principle fail: '
              f'{type(e).__name__}: {e}', file=_sys.stderr)
        _333 = {}
    _333_passed = _333.get("passed")
    _333_emoji = "✅" if _333_passed is True else ("❌" if _333_passed is False else "⬜")
    _333_msg = (_333.get("message") or "")[:36]

    return {
        "code": code,
        "基金名": (fd.get("fund_name") or mj.get("fund_name") or code)[:24],
        "4D Grade": _4d.get("grade") or "—",
        "4D Score": _4d.get("score"),
        "Sharpe 1Y": sharpe,
        "Sortino": sortino_v,
        "Calmar": calmar_v,
        "Alpha %": alpha_v,
        "費用率 %": expense_v,
        "Max DD %": max_dd,
        "3Y 年化 %": ret_3y_ann,
        "5Y 年化 %": ret_5y_ann,
        "MK 3-3-3": f"{_333_emoji} {_333_msg}".strip(),
    }


def build_dividend_summary_row(
    fd: dict,
    code: str,
    principal_twd: Optional[float] = None,
    holding_years: Optional[float] = None,
    fx: Optional[float] = None,
) -> dict:
    """配息相關 row(SSOT):adr + 1Y 含息報酬 + 吃本金燈號 (1Y·MK) + 換標的 + 每月配息單位數。

    Args:
        fd: 基金 dict
        code: 基金代號
        principal_twd: 本金 TWD(算每月配息單位數用;缺 → 該欄 None)
        holding_years: user 持有年數(換標的 verdict 用)
        fx: 1 原幣 = ? TWD(TWD 基金 = 1.0;caller 由 process_one_fund row["fx_spot"] 傳入)。
            缺 → 每月配息單位數 None(需匯率換原幣本金,§1 不估算)

    Returns:
        dict — UI 直接 render 成 dataframe row
    """
    if "moneydj_raw" not in fd and "perf" in fd:
        fd = {
            "moneydj_raw": fd,
            "metrics": fd.get("metrics") or {},
            "series": fd.get("series"),
            "perf_source": fd.get("perf_source"),
        }
    mj = fd.get("moneydj_raw") or {}

    # v19.184 F-MED:silent except 全改加 stderr log(§3.3 反捏造)
    import sys as _sys
    # ─── 1Y 含息報酬 SSOT ────────────────────────────
    from services.fund_total_return import compute_1y_total_return
    try:
        tr1y_pct, tr1y_src = compute_1y_total_return(fd)
    except Exception as e:
        print(f'[fund_health_report] div_row compute_1y_total_return fail: '
              f'{type(e).__name__}: {e}', file=_sys.stderr)
        tr1y_pct, tr1y_src = None, "—"

    # ─── adr SSOT ─────────────────────────────────────
    from services.health.dividend import (
        _resolve_adr_with_fallback,
        check_eating_principal_1y_mk,
    )
    try:
        # v19.177 _resolve_adr_with_fallback 回 (value, source) tuple
        adr_pct, _adr_src = _resolve_adr_with_fallback(fd)
    except Exception as e:
        print(f'[fund_health_report] div_row _resolve_adr_with_fallback fail: '
              f'{type(e).__name__}: {e}', file=_sys.stderr)
        adr_pct, _adr_src = None, "—"

    # ─── 吃本金燈號 1Y·MK SSOT ──────────────────────────
    try:
        eat_result = check_eating_principal_1y_mk(fd)
    except Exception as e:
        print(f'[fund_health_report] div_row check_eating_principal_1y_mk fail: '
              f'{type(e).__name__}: {e}', file=_sys.stderr)
        eat_result = None
    eat_status = (eat_result or {}).get("status", "⚪ 資料不足")

    # ─── 換標的建議 SSOT(MK 4 規則)─────────────────────
    from services.health.replacement import check_replacement_recommendation
    try:
        rep = check_replacement_recommendation(fd, holding_years=holding_years)
    except Exception as e:
        print(f'[fund_health_report] check_replacement_recommendation fail: '
              f'{type(e).__name__}: {e}', file=_sys.stderr)
        rep = {"emoji": "⬜", "label": "資料不足", "message": ""}

    # ─── 每月配息可再投入單位數 SSOT(真實記錄優先,年化估算 fallback)────
    # 真實:最近一筆實配 × 持有單位 / NAV;估算 fallback:原幣本金 × adr / 12 / NAV。
    # 持有單位 = 原幣本金(本金TWD/fx) / NAV。需 principal + fx + nav;`配息來源`欄註記
    # 真實 / 估算 / —(§2.2 血緣)。全站(Tab2/Tab3/健檢)同源走 dividend_calc。
    from services.health.dividend_calc import monthly_dividend_from_records
    _nav_ccy = _safe_float((fd.get("metrics") or {}).get("nav") or mj.get("nav_latest"))
    _divs = fd.get("dividends") or mj.get("dividends") or []
    _p = _safe_float(principal_twd)
    _fx = _safe_float(fx)
    _units_held = None
    if (_p is not None and _p > 0 and _fx is not None and _fx > 0
            and _nav_ccy is not None and _nav_ccy > 0):
        _units_held = (_p / _fx) / _nav_ccy
    _mdiv = monthly_dividend_from_records(
        _divs, _units_held, _nav_ccy, _fx, adr_pct=adr_pct)
    _mon_div_units = _mdiv.get("mon_div_units")
    _div_src = {"records": "真實", "estimate": "估算"}.get(_mdiv.get("source"), "—")

    return {
        "code": code,
        "基金名": (fd.get("fund_name") or mj.get("fund_name") or code)[:24],
        "1Y 含息 %": tr1y_pct,
        "1Y 來源": tr1y_src,
        "年化配息率 %": adr_pct,
        "每月配息單位數": _mon_div_units,
        "配息來源": _div_src,
        "吃本金燈號 (1Y·MK)": eat_status,
        "換標的建議": f"{rep['emoji']} {rep['label']}",
        "_換標的 detail": rep.get("message", ""),
        # v19.315:raw verdict 供「淘汰候選紅區」篩選(replace)。`_` 前綴 → 不進 DIVIDEND_COLUMNS 表格。
        "_verdict": rep.get("verdict", "unknown"),
    }


# UI column_config 順序常數(供 caller 用)
HEALTH_COLUMNS = [
    "code", "基金名",
    "4D Grade", "4D Score",
    "Sharpe 1Y", "Sortino", "Calmar", "Alpha %", "費用率 %",
    "Max DD %", "3Y 年化 %", "5Y 年化 %",
    "MK 3-3-3",
]

DIVIDEND_COLUMNS = [
    "code", "基金名",
    "1Y 含息 %", "1Y 來源",
    "年化配息率 %",
    "每月配息單位數",
    "配息來源",
    "吃本金燈號 (1Y·MK)",
    "換標的建議",
]
