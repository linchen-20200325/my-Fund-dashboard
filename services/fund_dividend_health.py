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
        except Exception as _e_div_parse:
            # F-MED v19.170: silent pass → stderr log
            import sys as _sys_dp
            print(f'[fund_dividend_health] dividend parse fail: {type(_e_div_parse).__name__}: {_e_div_parse}', file=_sys_dp.stderr)
            # NAV 部分仍可繼續

    meta["div_sum_per_unit"] = round(div_sum, 6)
    meta["div_count"] = div_count

    # Step 6:套 MK 公式
    nav_change_pct = (nav_end - nav_start) / nav_start * 100.0
    div_total_pct = (div_sum / nav_start) * 100.0 if div_sum > 0 else 0.0
    ret_pct = nav_change_pct + div_total_pct

    meta["nav_change_pct"] = round(nav_change_pct, 4)
    meta["div_total_pct"] = round(div_total_pct, 4)
    return round(ret_pct, 4), meta


def _resolve_adr_with_fallback(fund: dict) -> tuple[Optional[float], str]:
    """年化配息率(adr)3 層 fallback chain SSOT(v19.177)。

    將原本散在 `check_eating_principal_1y_mk`(2 層)與 `tab2_single_fund.py`
    KPI banner(3 層)的 adr 取數邏輯合一,確保跨 Tab 同檔基金顯示同一 adr 值。

    precedence(最權威 → 次選):
        1. **MoneyDJ wb05 官方** `moneydj_div_yield`(支援 nested moneydj_raw 與 flat shape)
        2. **本地自算** `metrics.annual_div_rate`
        3. **歷史推算** `divs[]` 12 個月累積配息 / `metrics.nav`(或 `moneydj_raw.nav_latest`)

    Args
    ----
    fund : dict
        支援兩種 shape:
        - Nested: `{moneydj_raw: {moneydj_div_yield, dividends, nav_latest}, metrics: {...}}`
        - Flat: `{moneydj_div_yield: ..., dividends: ..., metrics: {...}}`

    Returns
    -------
    (adr_pct, source_label)
        adr_pct: float (%) 或 None(全 fallback 皆失敗)
        source_label: 'moneydj_wb05' / 'metrics_annual_div_rate' / 'divs_12m_sum' / '—'
    """
    # 解析兩種 shape
    if "moneydj_raw" in fund:
        _mj = fund.get("moneydj_raw") or {}
    else:
        _mj = fund
    _metrics = fund.get("metrics") or {}

    # Layer 1: MoneyDJ wb05 官方
    _mj_dy = _safe_float(_mj.get("moneydj_div_yield"))
    if _mj_dy and _mj_dy > 0:
        return _mj_dy, "moneydj_wb05"

    # Layer 2: metrics.annual_div_rate(本地自算 N×freq/NAV)
    _local = _safe_float(_metrics.get("annual_div_rate"))
    if _local and _local > 0:
        return _local, "metrics_annual_div_rate"

    # Layer 3: divs[] 12 個月累積 / 現價(歷史推算 fallback)
    _divs = fund.get("dividends") or _mj.get("dividends")
    if _divs:
        try:
            import datetime as _dt
            _cutoff = _dt.datetime.now() - _dt.timedelta(days=365)
            _sum = 0.0
            for _dd in _divs:
                if not isinstance(_dd, dict):
                    continue
                _dt_str = (_dd.get("date") or "").replace("/", "-")
                try:
                    _dt_p = _dt.datetime.strptime(_dt_str[:10], "%Y-%m-%d")
                except (ValueError, TypeError):
                    continue
                if _dt_p >= _cutoff:
                    try:
                        _sum += float(_dd.get("amount", 0) or 0)
                    except (TypeError, ValueError):
                        continue
            _nav = _safe_float(_metrics.get("nav")) or _safe_float(_mj.get("nav_latest"))
            if _sum > 0 and _nav and _nav > 0:
                return (_sum / _nav) * 100.0, "divs_12m_sum"
        except Exception as _e:
            # §1 Fail Loud(降級):log + 走 None,不偽造
            import sys as _sys
            print(f'[_resolve_adr_with_fallback] divs 12M fallback fail: '
                  f'{type(_e).__name__}: {_e}', file=_sys.stderr)

    return None, "—"


def check_eating_principal_1y_mk(fund: dict) -> Optional[dict]:
    """MK 老師 1Y 吃本金檢查 SSOT 入口(v19.175 回歸 wb01 業界複利優先)。

    依郭俊宏(MK)老師體檢邏輯:
        近一年含息總報酬率 < 年化配息率 → 🔴 吃本金

    MK 老師核心精神是「善用免費理財網站直接查找數據,不要自己算複雜的數學」,
    系統應以 MoneyDJ wb01 官方數字為絕對優先(SSOT),只在抓不到時才自算 fallback,
    與使用者上網查到的數字一致,避免信任危機。

    支援兩種 fund dict shape:
    - **Nested**(tab3_portfolio / fund_checkup):`{moneydj_raw: {...}, metrics: {...}}`
    - **Flat**(`_auto_fetch_moneydj` 直回):`{moneydj_div_yield: ..., metrics: {...}}`

    含息報酬(tr1y) precedence(v19.175 — 對齊 Tab2/Tab3 SSOT):
        統一委派 `services.fund_total_return.compute_1y_total_return()`:
            1. perf["1Y"] (wb01 MoneyDJ 官方,業界複利)— 最權威
            2. ret_1y_total (本地含息計算)
            3. ret_1y (純 NAV,不含息)
            4. NAV 序列年化外推 (≥30d 才用,scale cap 12x)

        v19.149 的 MK 嚴格簡單單利路徑改為「對照欄」備援(`_tr1y_mk_simple_meta`),
        不再參與燈號判定 — 避免 Tab2(wb01)/ 健診總表(mk_simple)同檔結論相反。

    年化配息率(adr)precedence:
        moneydj_div_yield(MoneyDJ wb05 官方,優先)→ metrics.annual_div_rate(fallback)

    Returns
    -------
    dividend_safety 3 色結果 dict + v19.175 欄位:
      - `_tr1y_method`: tr1y 來源(從 compute_1y_total_return 取得 source label)
      - `_tr1y_window_days`: 仍保留欄位(對齊舊 caller),compute_1y_total_return 路徑為 None
      - `_tr1y_meta`: 仍保留欄位,內含 MK 嚴格單利對照值(若可算)便於 UI「業界 vs MK」對照顯示
    或 None(資料不足:adr 缺/tr1y 缺/adr ≤ 0)
    """
    # adr v19.177:統一走 SSOT _resolve_adr_with_fallback(3 層 chain)
    # 與 tab2_single_fund.py KPI banner 同源,免「Tab2 算得出但健診表回 None」散落
    adr, _adr_source = _resolve_adr_with_fallback(fund)
    if adr is None or adr <= 0:
        return None

    # tr1y v19.175:統一走 SSOT compute_1y_total_return(wb01 業界複利優先)
    from services.fund_total_return import compute_1y_total_return
    tr1y, _tr1y_method = compute_1y_total_return(fund)
    if tr1y is None:
        return None

    # 對照欄:MK 嚴格簡單單利(若 series + dividends 可用)仍計算供 UI 對照顯示,
    # 但 不再 參與燈號判定。
    # v19.181 Bug 4 fix: pd.Series 的 `or` 會觸發 ambiguous truth value ValueError —
    # 改用顯式 None 檢查(`fund.get("series")` 可能回傳 pd.Series 物件)
    _tr1y_meta: Optional[dict] = None
    _series = fund.get("series")
    if _series is None:
        _series = (fund.get("moneydj_raw") or {}).get("series")
    _divs = fund.get("dividends")
    if _divs is None:
        _divs = (fund.get("moneydj_raw") or {}).get("dividends")
    if _series is not None and _divs is not None:
        try:
            _mk_v, _mk_meta = compute_1y_total_return_mk_simple(_series, _divs)
            if _mk_v is not None and isinstance(_mk_meta, dict):
                _tr1y_meta = {**_mk_meta, "mk_simple_value": _mk_v}
        except Exception as _e_mk:
            # F-MED v19.170: silent pass → stderr log;對照欄缺失不影響燈號
            import sys as _sys_mk
            print(f'[fund_dividend_health] mk_simple compare-only calc fail: '
                  f'{type(_e_mk).__name__}: {_e_mk}', file=_sys_mk.stderr)

    from services.portfolio_service import dividend_safety
    out = dividend_safety(total_return=tr1y, dividend_yield=adr, nav_change=tr1y)
    if isinstance(out, dict):
        out["_tr1y_method"] = _tr1y_method
        out["_tr1y_window_days"] = (_tr1y_meta.get("window_days")
                                    if _tr1y_meta else None)
        out["_tr1y_meta"] = _tr1y_meta
        out["_adr_source"] = _adr_source  # v19.177 — adr 來源 SSOT 標記
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
