"""v19.119 — Canonical 吃本金核心判定(零 IO 純函式)。

抽出三套 wrapper 散在不同檔的「核心判定」共同邏輯,集中 SSOT。

設計
----
canonical 只負責**核心數學判定** — `is_eating = total_return < dividend_yield`,
不做 3/4/5 級分類(各 wrapper UI 需求不同,合理保留)。
未來若要改判定定義(例如加 tolerance / 加 NAV 趨勢因子),只改本檔 1 處。

對外 API
========
- `EatingPrincipalCore`:dataclass,canonical 判定結果
- `classify_eating_principal(total_return_pct, dividend_yield_pct)`:核心判定函式

委派 wrapper(各自服務不同 UI 需求,output schema 不變):
- `services.portfolio_service.dividend_safety` — 5 級 + nav_warning + 字串 message
- `services.fund_service.calc_health_from_manual` — 4 級 + 自算 NAV/配息 chain
- `services.fund_dividend_calculator.div_health_light_for_pair` — 3 色燈 tuple
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class EatingPrincipalCore:
    """Canonical 吃本金判定結果。

    欄位
    ----
    is_data_missing : bool
        任一 input 為 None / NaN / 非數值 → True(caller 應顯示「資料不足」)
    is_no_dividend : bool
        dividend_yield_pct ≤ 0(無配息基金 → 不適用吃本金概念,is_eating=False)
    is_eating : bool
        核心判定:total_return_pct < dividend_yield_pct(僅當 is_data_missing=False
        且 is_no_dividend=False 時有意義;否則為 False)
    total_return_pct : float | None
        輸入透傳(資料缺失時為 None)
    dividend_yield_pct : float | None
        輸入透傳(資料缺失時為 None)
    coverage_ratio : float | None
        含息報酬 / 配息率(若 div > 0;否則 None)。
        portfolio_service.dividend_safety 用此做 5 級分類。
    gap_pct : float | None
        配息率 - 含息報酬(正數 = 吃本金深度;若任一缺則 None)。
        fund_dividend_calculator.div_health_light_for_pair 用此 vs warn_gap 做 3 級。
    real_return_pct : float | None
        含息報酬 - 配息率(= -gap_pct)。
        fund_service.calc_health_from_manual 用此做 4 級分類。

    §1 fail loud:資料缺失 → is_data_missing=True 而非偽造數值;caller 顯示「資料不足」。
    """
    is_data_missing: bool
    is_no_dividend: bool
    is_eating: bool
    total_return_pct: Optional[float]
    dividend_yield_pct: Optional[float]
    coverage_ratio: Optional[float]
    gap_pct: Optional[float]
    real_return_pct: Optional[float]


def _safe_float(v: Any) -> Optional[float]:
    """輸入 → float 或 None(None / NaN / 非數值都回 None)。"""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN guard
        return None
    return f


def classify_eating_principal(
    total_return_pct: Any,
    dividend_yield_pct: Any,
) -> EatingPrincipalCore:
    """Canonical 吃本金核心判定 — 純數學,**無分類門檻**。

    Args
    ----
    total_return_pct : 含息報酬率 %(可為 None / NaN / 非數值)
    dividend_yield_pct : 年化配息率 %(可為 None / NaN / 非數值)

    Returns
    -------
    EatingPrincipalCore: 核心判定 + 派生指標。Caller 自行用
    `coverage_ratio` / `gap_pct` / `real_return_pct` 配合自己的 UI 門檻
    做 3/4/5 級分類。

    判定邏輯
    --------
    1. 任一 input 不合法 → is_data_missing=True,其餘欄位全 None / False
    2. dividend_yield ≤ 0(無配息基金)→ is_no_dividend=True, is_eating=False
       (邏輯上「沒配息 → 不存在吃本金」)
    3. 正常 case → is_eating = (total_return < dividend_yield)
       + coverage_ratio / gap_pct / real_return_pct 全部算好供 caller 用
    """
    r = _safe_float(total_return_pct)
    d = _safe_float(dividend_yield_pct)

    # Case 1:資料缺失(§1 fail loud:不偽造數值)
    if r is None or d is None:
        return EatingPrincipalCore(
            is_data_missing=True,
            is_no_dividend=False,
            is_eating=False,
            total_return_pct=r,
            dividend_yield_pct=d,
            coverage_ratio=None,
            gap_pct=None,
            real_return_pct=None,
        )

    # Case 2:無配息基金(div ≤ 0 → 不適用吃本金概念)
    if d <= 0:
        return EatingPrincipalCore(
            is_data_missing=False,
            is_no_dividend=True,
            is_eating=False,
            total_return_pct=r,
            dividend_yield_pct=d,
            coverage_ratio=None,  # 除以 0 / 負數無意義
            gap_pct=d - r,        # gap 仍可算(雖然 caller 多半不用)
            real_return_pct=r - d,
        )

    # Case 3:正常 — 核心判定 + 全派生指標
    is_eating = r < d
    return EatingPrincipalCore(
        is_data_missing=False,
        is_no_dividend=False,
        is_eating=is_eating,
        total_return_pct=r,
        dividend_yield_pct=d,
        coverage_ratio=r / d,
        gap_pct=d - r,
        real_return_pct=r - d,
    )


# ════════════════════════════════════════════════════════════════
# v19.148 → v19.149 — MK 老師 1Y 吃本金檢查 SSOT 入口
#   方法論:近一年含息報酬率 vs 年化配息率(郭俊宏 MK 老師體檢邏輯)
#   v19.149 升級:含息報酬從業界複利(wb01)改為 MK 嚴格單利
#     含息_1Y = NAV 漲跌幅% + 累計配息率%
#   wb01/ret_1y_total/ret_1y 變成 fallback,當 fund 內 raw series + dividends
#   不可用時才使用。caller 可由 `_tr1y_method` 欄位看出實際用哪條路。
# ════════════════════════════════════════════════════════════════
def compute_1y_total_return_mk_simple(
    nav_series: Any,
    dividends: Any,
    as_of_date: Optional[str] = None,
) -> tuple[Optional[float], dict]:
    """v19.149 — MK 老師嚴格單利 1Y 含息報酬率 SSOT 計算。

    公式(MK 老師體檢邏輯):
        含息_1Y = NAV 漲跌幅% + 累計配息率%
              = (NAV_now − NAV_1Y_ago) / NAV_1Y_ago × 100
              + Σ(divs in last 1Y) / NAV_1Y_ago × 100

    與業界 wb01 複利還原淨值法不同(複利 ≈ 高 5-15%,borderline 可能 flip)。
    此公式對齊老師教學版,user 自己拿計算機算結果一致。

    Args
    ----
    nav_series: dict {iso_date: nav} 或 pandas Series(index=date, value=nav)
    dividends: list of {date: iso, amount: float} 或 list of (date, amount)
    as_of_date: 截止日 iso 字串(預設 = nav_series 最後一筆日期)

    Returns
    -------
    (ret_pct, meta) tuple:
      ret_pct: float | None — 含息報酬率%,None 表資料不足
      meta: dict {
        "nav_start": float,         # 1Y 起點 NAV
        "nav_end": float,           # 截止日 NAV
        "nav_change_pct": float,    # NAV 漲跌幅%
        "div_sum_per_unit": float,  # 1Y 窗內累計配息(每單位)
        "div_total_pct": float,     # 累計配息率%
        "window_days": int,         # 實際窗口天數(可能 < 365)
        "div_count": int,           # 1Y 窗內配息事件數
        "method": "mk_simple",
        "source": str,              # 'mk_strict' / 'mk_strict_short_window'
        "error": str | None,
      }

    §1 Fail Loud:資料缺/負值 → 回 (None, meta with error 描述);**不偽造數值**。
    """
    import datetime as _dt
    meta: dict = {
        "nav_start": None, "nav_end": None, "nav_change_pct": None,
        "div_sum_per_unit": None, "div_total_pct": None, "window_days": None,
        "div_count": 0, "method": "mk_simple", "source": "mk_strict",
        "error": None,
    }

    # Step 1:正規化 nav 成 list[(iso_str, float)] 升序
    nav_items: list[tuple[str, float]] = []
    try:
        if hasattr(nav_series, "items"):  # dict-like
            _src = nav_series.items()
        elif hasattr(nav_series, "index") and hasattr(nav_series, "values"):  # pd.Series
            _src = list(zip(nav_series.index, nav_series.values))
        else:
            meta["error"] = "nav_series 型別不支援"
            return None, meta
        for _d, _v in _src:
            try:
                _ds = str(_d)[:10]
                _vs = float(_v)
                if _vs != _vs:  # NaN guard
                    continue
                nav_items.append((_ds, _vs))
            except (TypeError, ValueError):
                continue
        nav_items.sort(key=lambda x: x[0])
    except Exception as e:
        meta["error"] = f"nav_series 解析失敗: {type(e).__name__}"
        return None, meta

    if len(nav_items) < 2:
        meta["error"] = "NAV 不足 2 筆"
        return None, meta

    # Step 2:as_of_date 處理 — 找 ≤ as_of_date 的最後一筆 NAV 為終點
    _as_of_str = (as_of_date or "")[:10] if as_of_date else nav_items[-1][0]
    _end_candidates = [(d, v) for d, v in nav_items if d <= _as_of_str]
    if not _end_candidates:
        meta["error"] = f"無 NAV ≤ as_of_date={_as_of_str}"
        return None, meta
    _end_date_str, nav_end = _end_candidates[-1]
    meta["nav_end"] = nav_end

    # Step 3:1Y 起點(as_of − 365 天,找最早 ≤ 該日期的 NAV)
    try:
        _end_date = _dt.date.fromisoformat(_end_date_str)
        _target_date = _end_date - _dt.timedelta(days=365)
        _target_str = _target_date.isoformat()
    except ValueError:
        meta["error"] = f"終點日期格式錯誤: {_end_date_str}"
        return None, meta

    _start_candidates = [(d, v) for d, v in nav_items if d <= _target_str]
    if _start_candidates:
        _start_date_str, nav_start = _start_candidates[-1]
        meta["source"] = "mk_strict"
    else:
        # 基金不滿 1 年 → 用最早一筆 NAV 為起點(短窗口)
        _start_date_str, nav_start = nav_items[0]
        meta["source"] = "mk_strict_short_window"

    if nav_start is None or nav_start <= 0:
        meta["error"] = f"起點 NAV 無效: {nav_start}"
        return None, meta
    meta["nav_start"] = nav_start

    # Step 4:窗口實際天數
    try:
        _w_start_date = _dt.date.fromisoformat(_start_date_str)
        meta["window_days"] = (_end_date - _w_start_date).days
    except ValueError:
        meta["window_days"] = None

    # Step 5:1Y 窗內累計配息(支援 dict / tuple 兩種 shape)
    div_sum = 0.0
    div_count = 0
    if dividends:
        try:
            for _d in dividends:
                if isinstance(_d, dict):
                    _date_raw = str(_d.get("date") or _d.get("ex_date") or "")[:10]
                    _amt = _d.get("amount")
                    if _amt is None:
                        _amt = _d.get("div_per_unit")
                elif isinstance(_d, (tuple, list)) and len(_d) >= 2:
                    _date_raw = str(_d[0])[:10]
                    _amt = _d[1]
                else:
                    continue
                try:
                    _amt_f = float(_amt)
                except (TypeError, ValueError):
                    continue
                if _amt_f <= 0 or not _date_raw:
                    continue
                # 落在 (start, end] 窗內才算入
                if _start_date_str < _date_raw <= _end_date_str:
                    div_sum += _amt_f
                    div_count += 1
        except Exception:
            pass  # 配息解析錯誤靜默 skip,不阻斷 NAV 部分

    meta["div_sum_per_unit"] = round(div_sum, 6)
    meta["div_count"] = div_count

    # Step 6:套 MK 公式
    nav_change_pct = (nav_end - nav_start) / nav_start * 100.0
    div_total_pct = (div_sum / nav_start) * 100.0 if div_sum > 0 else 0.0
    ret_pct = nav_change_pct + div_total_pct

    meta["nav_change_pct"] = round(nav_change_pct, 4)
    meta["div_total_pct"] = round(div_total_pct, 4)
    return round(ret_pct, 4), meta


def check_eating_principal_1y_mk(fund: dict) -> Optional[dict]:
    """MK 老師 1Y 吃本金檢查 SSOT 入口(v19.149 升級為嚴格單利)。

    依郭俊宏(MK)老師體檢邏輯:
        近一年含息總報酬率 < 年化配息率 → 🔴 吃本金

    支援兩種 fund dict shape:
    - **Nested**(tab3_portfolio / fund_checkup):`{moneydj_raw: {...}, metrics: {...}}`
    - **Flat**(`_auto_fetch_moneydj` 直回):`{moneydj_div_yield: ..., metrics: {...}}`

    含息報酬(tr1y) precedence(v19.149 — 對齊 MK 嚴格單利公式):
        1. **MK 嚴格單利**:從 fund["series"] + fund["dividends"] 直算
           `compute_1y_total_return_mk_simple()`(教學定義,user 拿計算機算得出)
        2. metrics.ret_1y_total / metrics.ret_1y(本地或 wb01,業界複利,作 fallback)

    年化配息率(adr)precedence:
        moneydj_div_yield(MoneyDJ wb05 官方,優先)→ metrics.annual_div_rate(fallback)

    Returns
    -------
    dividend_safety 5-level 結果 dict + 加 v19.149 欄位:
      - `_tr1y_method`: "mk_simple" / "metrics_fallback"
      - `_tr1y_window_days`: 實際窗口天數(MK 嚴格才有)
      - `_tr1y_meta`: dict (MK 嚴格才有,nav_start/end/div_count 等)
    或 None(資料不足:adr 缺/tr1y 缺/adr ≤ 0)
    """
    # 解析兩種 shape
    if "moneydj_raw" in fund:
        _mj = fund.get("moneydj_raw") or {}
        _mj_dy = _safe_float(_mj.get("moneydj_div_yield"))
    else:
        _mj_dy = _safe_float(fund.get("moneydj_div_yield"))

    _metrics = fund.get("metrics") or {}

    # adr:MoneyDJ wb05 優先,fallback metrics.annual_div_rate
    adr = _mj_dy if (_mj_dy and _mj_dy > 0) else _safe_float(_metrics.get("annual_div_rate"))
    if adr is None or adr <= 0:
        return None

    # tr1y precedence v19.149:
    # 1) MK 嚴格單利(從 fund 內 raw series + dividends 直算)
    # 2) metrics.ret_1y_total / metrics.ret_1y(業界複利 fallback)
    tr1y: Optional[float] = None
    _tr1y_method = "metrics_fallback"
    _tr1y_meta: Optional[dict] = None
    _tr1y_window_days: Optional[int] = None

    _series = fund.get("series") or (fund.get("moneydj_raw") or {}).get("series")
    _divs = fund.get("dividends") or (fund.get("moneydj_raw") or {}).get("dividends")
    if _series is not None and _divs is not None:
        try:
            _mk_v, _mk_meta = compute_1y_total_return_mk_simple(_series, _divs)
            if _mk_v is not None:
                tr1y = _mk_v
                _tr1y_method = "mk_simple"
                _tr1y_meta = _mk_meta
                _tr1y_window_days = _mk_meta.get("window_days")
        except Exception:
            pass  # 嚴格算失敗 → fallback metrics

    if tr1y is None:
        tr1y = _safe_float(_metrics.get("ret_1y_total")) or _safe_float(_metrics.get("ret_1y"))
    if tr1y is None:
        return None

    from services.portfolio_service import dividend_safety
    out = dividend_safety(total_return=tr1y, dividend_yield=adr, nav_change=tr1y)
    if isinstance(out, dict):
        out["_tr1y_method"] = _tr1y_method
        out["_tr1y_window_days"] = _tr1y_window_days
        out["_tr1y_meta"] = _tr1y_meta
    return out


# v19.148 — 3-3-3 原則(MK 老師長線核心資產挑選輔助,非吃本金主判定)
#   成立滿 3 年 + 過去 3 年平均年化報酬 > 7% → 通過長線核心資產篩
THREE_THREE_THREE_MIN_YEARS = 3
THREE_THREE_THREE_MIN_ANN_RETURN_PCT = 7.0


def check_333_principle(years_since_inception: Optional[float],
                        ann_return_3y_pct: Optional[float]) -> dict:
    """MK 老師 3-3-3 原則 — 長線核心資產挑選輔助判定(輔助,非主吃本金).

    通過條件:
    - 成立 ≥ 3 年
    - 近 3 年平均年化報酬 > 7%

    Returns
    -------
    {
      "passed": bool | None(None = 資料不足),
      "years_ok": bool | None,
      "return_ok": bool | None,
      "message": str,
    }

    這是**長線核心資產篩選**輔助,不是吃本金判定。
    短線吃本金以 check_eating_principal_1y_mk 為準。
    """
    _yrs = _safe_float(years_since_inception)
    _ret = _safe_float(ann_return_3y_pct)
    if _yrs is None and _ret is None:
        return {"passed": None, "years_ok": None, "return_ok": None,
                "message": "資料不足(缺成立年數 + 3 年平均年化)"}
    _y_ok = (_yrs is not None and _yrs >= THREE_THREE_THREE_MIN_YEARS)
    _r_ok = (_ret is not None and _ret > THREE_THREE_THREE_MIN_ANN_RETURN_PCT)
    _passed = _y_ok and _r_ok
    if _passed:
        _msg = f"通過 3-3-3 ✅({_yrs:.1f} 年成立、3 年平均年化 {_ret:.1f}%)"
    elif not _y_ok and _yrs is not None:
        _msg = f"成立 {_yrs:.1f} 年 < 3 年(MK 3-3-3 要求 ≥ 3 年)"
    elif not _r_ok and _ret is not None:
        _msg = f"3 年平均年化 {_ret:.1f}% ≤ 7%(MK 3-3-3 要求 > 7%)"
    else:
        _msg = "資料不足(部分缺)"
    return {"passed": _passed, "years_ok": _y_ok, "return_ok": _r_ok, "message": _msg}
