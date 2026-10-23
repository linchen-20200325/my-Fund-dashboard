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
- `services.health.dividend_calc.div_health_light_for_pair` — 3 色燈 tuple
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


# v19.222 P1-1:_safe_float 收口至 shared/converters.py SSOT
from shared.converters import safe_float as _safe_float  # noqa: E402



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
# v19.148 → v19.149 — 老師 1Y 吃本金檢查(歷史:嚴格單利版)
#   方法論:近一年含息報酬率 vs 年化配息率(老師體檢邏輯)
#   v19.149 曾把含息報酬改為嚴格單利(NAV 漲跌幅% + 累計配息率%);
#   2026-10-23 裁示 1B 後唯一算法改為配息還原淨值法(見 check_eating_principal_1y_mk)。
# ════════════════════════════════════════════════════════════════
def compute_1y_total_return_mk_simple(
    nav_series: Any,
    dividends: Any,
    as_of_date: Optional[str] = None,
) -> tuple[Optional[float], dict]:
    """v19.149 — 老師嚴格單利 1Y 含息報酬率計算。

    ⚠️ **2026-10-23 起無 production caller**(裁示 1B:1Y 含息唯一算法 = 配息還原淨值法
    `fund_service.calc_metrics.ret_1y_total`;本函式的「對照欄」與短窗替補路徑已自
    `check_eating_principal_1y_mk` 移除)。函式本體保留供 BL-0422 退休流程,**不得**
    再被接回燈號判定。

    公式(老師體檢邏輯):
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
                    # v19.352:配息日正規化斜線→破折號(對照 dividend.py:358 /
                    # dividend_calc.py:95 / fund_service.py:501 慣例)。MoneyDJ 常給
                    # "YYYY/MM/DD",與 dash-ISO 窗界做字典序比較時 '/'(0x2F)>'-'(0x2D)
                    # → 窗內配息被誤判超出上界而漏算,div_sum 少計 → 殖利率/總報酬偏低。
                    _date_raw = str(_d.get("date") or _d.get("ex_date") or "")[:10].replace("/", "-")
                    _amt = _d.get("amount")
                    if _amt is None:
                        _amt = _d.get("div_per_unit")
                elif isinstance(_d, (tuple, list)) and len(_d) >= 2:
                    _date_raw = str(_d[0])[:10].replace("/", "-")   # v19.352 同上正規化
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

    # Step 6:套 公式
    nav_change_pct = (nav_end - nav_start) / nav_start * 100.0
    div_total_pct = (div_sum / nav_start) * 100.0 if div_sum > 0 else 0.0
    ret_pct = nav_change_pct + div_total_pct

    meta["nav_change_pct"] = round(nav_change_pct, 4)
    meta["div_total_pct"] = round(div_total_pct, 4)
    return round(ret_pct, 4), meta


# ── 年化配息率(adr)SSOT ─────────────────────────────────────────────────────
ADR_SRC_DIVS_12M = "divs_12m_sum"            # 唯一有值的來源:近 12 個月實際配息合計 ÷ 最新淨值
ADR_LABEL_DATA_MISSING = "⬜ 配息資料未備"    # 有配息跡象但窗內 0 筆 / 缺淨值 → 不判
ADR_LABEL_NO_DIVIDEND = "—"                  # 完全無配息跡象(非配息基金)


def resolve_dividend_rate_12m(fund: dict) -> dict:
    """年化配息率 SSOT 解析(2026-10-23 裁示 1B,**唯一算法**)。

    公式:近 12 個月**實際**配息合計 ÷ 最新淨值 × 100;窗口 (anchor − 365 天, anchor],
    anchor = 最後一筆 NAV 日(有 series),否則今天。

    取數順序(同一公式的兩個住址,不是兩種算法):
      1. `metrics.annual_div_rate`(`calc_metrics` 已以同公式產出;鍵存在即採用,
         值 None 表示窗內無紀錄)
      2. metrics **無此鍵**時,以 `dividends` + `metrics.nav` / `moneydj_raw.nav_latest` 現算
    **不再**讀 `moneydj_div_yield`(wb05 官方)當值 —— 它只放 `official_wb05_pct` 供對帳。

    Returns
    -------
    {
      "value_pct": float | None,
      "status": "ok" | "unavailable",
      "reason": None | "dividend_data_missing" | "nav_missing" | "no_dividend",
      "div_count": int | None,          # 12M 窗內配息筆數
      "window_end": str | None,         # anchor ISO 日期
      "official_wb05_pct": float | None,
      "label": ADR_SRC_DIVS_12M | ADR_LABEL_DATA_MISSING | ADR_LABEL_NO_DIVIDEND,
    }
    `dividend_data_missing`:`moneydj_div_yield > 0` 或有歷史配息紀錄,但 12M 窗內 0 筆
    (停配 / 紀錄缺)→ 不能當 0% 也不能拿官方值頂 → 誠實不判。
    `no_dividend`:完全無配息跡象 → 非配息基金,吃本金概念不適用(既有契約)。
    """
    import datetime as _dt
    if "moneydj_raw" in fund:
        _mj = fund.get("moneydj_raw") or {}
    else:
        _mj = fund
    _metrics = fund.get("metrics") or {}
    _official = _safe_float(_mj.get("moneydj_div_yield"))
    if _official is None and _mj is not fund:
        _official = _safe_float(fund.get("moneydj_div_yield"))
    _divs = fund.get("dividends")
    if _divs is None:
        _divs = _mj.get("dividends")
    _divs = _divs or []

    def _has_any_dividend_record() -> bool:
        for _dd in _divs:
            if isinstance(_dd, dict):
                _a = _safe_float(_dd.get("amount") if _dd.get("amount") is not None
                                 else _dd.get("div_per_unit"))
            elif isinstance(_dd, (tuple, list)) and len(_dd) >= 2:
                _a = _safe_float(_dd[1])
            else:
                continue
            if _a is not None and _a > 0:
                return True
        return False

    def _unavail(reason: str, *, div_count=None, window_end=None) -> dict:
        _lbl = (ADR_LABEL_NO_DIVIDEND if reason == "no_dividend"
                else ADR_LABEL_DATA_MISSING)
        return {"value_pct": None, "status": "unavailable", "reason": reason,
                "div_count": div_count, "window_end": window_end,
                "official_wb05_pct": _official, "label": _lbl}

    _has_signal = (_official is not None and _official > 0) or _has_any_dividend_record()

    # 1) metrics 已算好(同公式)
    if "annual_div_rate" in _metrics:
        _v = _safe_float(_metrics.get("annual_div_rate"))
        _cnt = _metrics.get("annual_div_rate_div_count")
        _wend = _metrics.get("annual_div_rate_window_end")
        if _v is not None and _v > 0:
            return {"value_pct": _v, "status": "ok", "reason": None,
                    "div_count": _cnt, "window_end": _wend,
                    "official_wb05_pct": _official, "label": ADR_SRC_DIVS_12M}
        # 值 None / 0 → 窗內無紀錄;有配息跡象 → 資料未備,否則非配息基金
        return _unavail("dividend_data_missing" if _has_signal else "no_dividend",
                        div_count=_cnt, window_end=_wend)

    # 2) metrics 無此鍵 → 以 dividends + nav 現算
    _anchor = None
    _series = fund.get("series")
    if _series is None:
        _series = _mj.get("series")
    try:
        if _series is not None and hasattr(_series, "index") and len(_series) > 0:
            _last = _series.index[-1]
            _anchor = _dt.datetime.strptime(str(_last)[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        _anchor = None
    if _anchor is None:
        _anchor = _dt.datetime.now()
    _window_end = _anchor.date().isoformat()
    _cutoff = _anchor - _dt.timedelta(days=365)
    _sum = 0.0
    _cnt = 0
    for _dd in _divs:
        if isinstance(_dd, dict):
            _dt_raw = _dd.get("date") or _dd.get("ex_date") or ""
            _a = _dd.get("amount") if _dd.get("amount") is not None else _dd.get("div_per_unit")
        elif isinstance(_dd, (tuple, list)) and len(_dd) >= 2:
            _dt_raw, _a = _dd[0], _dd[1]
        else:
            continue
        _dt_str = str(_dt_raw or "").replace("/", "-")
        try:
            _dt_p = _dt.datetime.strptime(_dt_str[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            continue
        _af = _safe_float(_a)
        if _af is None or _af <= 0:
            continue
        if _cutoff < _dt_p <= _anchor:
            _sum += _af
            _cnt += 1
    if _cnt == 0:
        return _unavail("dividend_data_missing" if _has_signal else "no_dividend",
                        div_count=0, window_end=_window_end)
    _nav = _safe_float(_metrics.get("nav"))
    if _nav is None or _nav <= 0:
        _nav = _safe_float(_mj.get("nav_latest"))
    if _nav is None or _nav <= 0:
        return _unavail("nav_missing", div_count=_cnt, window_end=_window_end)
    return {"value_pct": (_sum / _nav) * 100.0, "status": "ok", "reason": None,
            "div_count": _cnt, "window_end": _window_end,
            "official_wb05_pct": _official, "label": ADR_SRC_DIVS_12M}


def _resolve_adr_with_fallback(fund: dict) -> tuple[Optional[float], str]:
    """年化配息率(adr)SSOT 入口 —— `resolve_dividend_rate_12m` 的薄包裝(簽名不變)。

    2026-10-23 裁示 1B:原 3 層 fallback(wb05 官方 → metrics.annual_div_rate → divs 12M)
    收斂為**單一方法**「近 12 個月實際配息合計 ÷ 最新淨值 × 100」;wb05 官方值不再當值。

    Returns
    -------
    (adr_pct, source_label)
        ok          → (float, "divs_12m_sum")
        資料未備    → (None, "⬜ 配息資料未備")  — 有配息跡象但窗內 0 筆 / 缺淨值
        非配息基金  → (None, "—")
    """
    _r = resolve_dividend_rate_12m(fund)
    return (_r["value_pct"] if _r["status"] == "ok" else None), _r["label"]


# v19.480 稽核 2b 的「還原含息替補」最短窗口。2026-10-23 裁示 1B 後替補邏輯已移除
# (窗口門檻統一走 `shared.signal_thresholds.RET_1Y_RESTORED_MIN_WINDOW_DAYS`),
# 本常數**無 production caller**,只為相容保留(BL-0422 退休流程一併處理)。
_EATING_RESTORE_MIN_WINDOW_DAYS = 300

EATING_STATUS_UNAVAILABLE = "⬜ 資料未備／無法判定"

_EATING_GREY_MESSAGE = {
    "dividend_data_missing": ("這檔有配息跡象,但近一年窗口內沒有任何配息紀錄 —— "
                              "**不是它不吃本金,是我們沒有足夠的配息資料去判斷**。"
                              "請先補齊配息紀錄,或改看基金官方績效頁"),
    "window_short": ("這檔的淨值歷史不足一年,無法算出可靠的一年含息報酬 —— "
                     "**不是它沒有配息或不吃本金,是我們還沒有足夠的資料去判斷**。"
                     "請改看基金官方績效頁的含息報酬"),
    "window_unknown": ("這檔的還原含息值沒有窗口天數證據,無法確認它涵蓋一年 —— 無法判定,"
                       "不拿它冒充一年報酬"),
    "nav_missing": "這檔近一年有配息紀錄,但抓不到最新淨值,算不出年化配息率 —— 無法判定",
    "no_series": "這檔沒有淨值序列,無法還原一年含息報酬 —— 無法判定",
    "no_restored_value": ("這檔有淨值序列但無法還原出一年含息報酬(筆數不足或資料異常)—— "
                          "無法判定,不拿別的數字頂替"),
}


def _eating_grey(reason: str, *, tr1y_label=None, adr_source=None, adr_pct=None,
                 window_days=None) -> dict:
    """吃本金「資料未備／無法判定」灰色結果。`eating_principal` 一律 None(missing ≠ False)。"""
    return {
        "status": EATING_STATUS_UNAVAILABLE, "alert_level": "grey",
        "reason": reason,
        "message": _EATING_GREY_MESSAGE.get(reason, "資料未備,無法判定"),
        "coverage": None, "gap_pct": None, "eating_principal": None,
        "_tr1y_method": tr1y_label, "_adr_source": adr_source,
        "_adr_pct": adr_pct,
        "_tr1y_meta": None, "_tr1y_window_days": window_days,
    }


def check_eating_principal_1y_mk(fund: dict) -> Optional[dict]:
    """老師 1Y 吃本金檢查 SSOT 入口(2026-10-23 裁示 1B:唯一判定)。

    依老師體檢邏輯:
        近一年含息總報酬率 < 年化配息率 → 🔴 吃本金(2pp 黃燈帶走 `dividend_safety`)

    支援兩種 fund dict shape:
    - **Nested**(tab3_portfolio / fund_checkup):`{moneydj_raw: {...}, metrics: {...}}`
    - **Flat**(`_auto_fetch_moneydj` 直回):`{moneydj_div_yield: ..., metrics: {...}}`

    兩個輸入各只有一個來源(§2.1):
      - adr  = `_resolve_adr_with_fallback`(近 12 個月實際配息合計 ÷ 最新淨值)
      - tr1y = `resolve_1y_total_return`(本地配息還原淨值法,窗口 ≥ 350 天)
    任一缺 → 回灰色 dict(`status="⬜ 資料未備／無法判定"`、`reason`、`eating_principal=None`),
    **不**退回官方 wb01 / wb05、**不**外推、**不**拿純淨值。
    `nav_change` 傳 `metrics.ret_1y`(純淨值 1Y 變化)供 `dividend_safety` 的淨值下跌交叉警語。

    Returns
    -------
    dividend_safety 3 色結果 dict + 欄位:
      - `_tr1y_method`:tr1y 來源標籤(resolve 的 label)
      - `_tr1y_window_days`:還原窗口天數
      - `_tr1y_meta`:保留欄位,恆 None(mk_simple 對照路徑已移除)
      - `_adr_source` / `_adr_pct`:adr 來源標籤與值
    或 None(非配息基金:adr 來源為「—」,既有契約:不判)
    """
    from services.fund_total_return import resolve_1y_total_return

    _ar = resolve_dividend_rate_12m(fund)
    adr, _adr_source = (_ar["value_pct"] if _ar["status"] == "ok" else None), _ar["label"]
    if adr is None:
        if _ar["reason"] == "no_dividend":
            return None
        # 透傳 resolve 的 reason(dividend_data_missing / nav_missing),不寫死
        return _eating_grey(_ar["reason"], adr_source=_adr_source, adr_pct=None)
    if adr <= 0:
        return None

    _r = resolve_1y_total_return(fund)
    if _r["status"] != "ok":
        return _eating_grey(_r["reason"], tr1y_label=_r["label"], adr_source=_adr_source,
                            adr_pct=adr, window_days=_r["window_days"])
    tr1y, _tr1y_method = _r["value_pct"], _r["label"]

    from services.portfolio_service import dividend_safety
    # nav_change = 純淨值 1Y 變化(metrics.ret_1y),只驅動「淨值下跌 X%」交叉警語;缺 → None
    _nav_chg = _safe_float((fund.get("metrics") or {}).get("ret_1y"))
    out = dividend_safety(total_return=tr1y, dividend_yield=adr,
                          nav_change=_nav_chg)
    if isinstance(out, dict):
        out["_tr1y_method"] = _tr1y_method
        out["_tr1y_window_days"] = _r["window_days"]
        out["_tr1y_meta"] = None
        out["_adr_source"] = _adr_source
        out["_adr_pct"] = adr
    return out


# v19.148 — 3-3-3 原則(老師長線核心資產挑選輔助,非吃本金主判定)
#   成立滿 3 年 + 過去 3 年平均年化報酬 > 7% → 通過長線核心資產篩
THREE_THREE_THREE_MIN_YEARS = 3
THREE_THREE_THREE_MIN_ANN_RETURN_PCT = 7.0


def check_333_principle(years_since_inception: Optional[float],
                        ann_return_3y_pct: Optional[float]) -> dict:
    """老師 3-3-3 原則 — 長線核心資產挑選輔助判定(輔助,非主吃本金).

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

    三態語意(§1:缺資料 ≠ 未通過)
    ------------------------------
    - True  = 兩條件皆有值且皆達標
    - False = **有明確反證**(成立年數不足,或 3 年年化有值但未達門檻)
    - None  = 缺成立年數 / 缺 3 年年化 → 無法判定,UI 顯示 ⬜ 而非 ❌

    這是**長線核心資產篩選**輔助,不是吃本金判定。
    短線吃本金以 check_eating_principal_1y_mk 為準。
    """
    _yrs = _safe_float(years_since_inception)
    _ret = _safe_float(ann_return_3y_pct)
    if _yrs is None and _ret is None:
        return {"passed": None, "years_ok": None, "return_ok": None,
                "message": "資料不足(缺成立年數 + 3 年平均年化)"}
    # 缺成立年數 → 無法判斷是否成立 ≥ 3 年，passed=None（顯示 ⬜）而非 False（❌）
    if _yrs is None:
        return {"passed": None, "years_ok": None, "return_ok": None,
                "message": "資料不足(缺成立年數)"}
    _y_ok = (_yrs >= THREE_THREE_THREE_MIN_YEARS)
    # 缺 3 年平均年化 → 「報酬 > 7%」無從判定,只能是 None;不可折成 False。
    _r_ok = (None if _ret is None
             else _ret > THREE_THREE_THREE_MIN_ANN_RETURN_PCT)
    # 成立年數已達標、但 3 年平均年化抓不到(MoneyDJ wb01 三年期常缺)→ 整條原則無法判定,
    # 與上方「缺成立年數」路徑同樣回 passed=None(⬜ 資料不足),不得回 False(❌ 未通過)。
    # 下游 `services/health/asset_class.py` 只在 passed is False 時附註「未達 3-3-3」並
    # 把此檔推向「待定」,因此這裡的三態必須嚴格區分,否則核心/衛星佔比會被灌水。
    if _y_ok and _r_ok is None:
        return {"passed": None, "years_ok": True, "return_ok": None,
                "message": "資料不足(缺 3 年平均年化)"}
    # 到此:_y_ok 為 False(成立年數已足以否決,不需 3 年報酬)或 _r_ok 已有明確布林值。
    _passed = bool(_y_ok and _r_ok)
    if _passed:
        _msg = f"通過 3-3-3 ✅({_yrs:.1f} 年成立、3 年平均年化 {_ret:.1f}%)"
    elif not _y_ok:
        _msg = f"成立 {_yrs:.1f} 年 < 3 年( 3-3-3 要求 ≥ 3 年)"
    else:
        _msg = f"3 年平均年化 {_ret:.1f}% ≤ 7%( 3-3-3 要求 > 7%)"
    return {"passed": _passed, "years_ok": _y_ok, "return_ok": _r_ok, "message": _msg}


# ── v19.485 稽核 PR-2:3-3-3 兩個輸入的 SSOT 推導(消滅 fund_row / compare 複本)──────
#   check_333_principle 的三態邏輯本就正確;bug 全在**餵進去的輸入**(成立年數 proxy、
#   3Y 用純NAV)。這裡把輸入推導收成單一權威,三個消費端(fund_row / report verdict /
#   compare 診斷)共用,parity 自動成立。

def _annualize_cum_pct(cum_pct, n_years: float):
    """累積報酬%(如 3 年 +33%)→ 年平均年化%。P3:cum ≤ −100% → None(全損 → 年化無定義,
    避免 `(1+cum)^(1/n)` 落入複數 / NaN)。§4.1:輸入輸出皆為 **百分數**(非小數)。"""
    if cum_pct is None:
        return None
    try:
        _c = float(cum_pct) / 100.0
        if _c <= -1.0:                       # P3:≤ −100% → 年化無定義(複數保護)
            return None
        return ((1.0 + _c) ** (1.0 / float(n_years)) - 1.0) * 100.0
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return None


def clamp_333_proxy_years(years, from_proxy: bool,
                          *, min_years: float = THREE_THREE_THREE_MIN_YEARS):
    """H3(§1:短 NAV ≠ 年輕基金)。NAV 首日 proxy 是「基金年齡」的**下界**:
    - proxy 且 years ≥ min_years → 一定 ≥ 門檻 → 照回(安全下界)
    - proxy 且 years <  min_years → **無法反證** <3 年(可能只是本地 NAV 太短)→ None(⬜ 非 ❌)
    - 真成立日(非 proxy)→ 精確值,原樣回。"""
    if years is None:
        return None
    if from_proxy and float(years) < float(min_years):
        return None
    return years


def derive_years_for_333(inception_iso, nav_first_iso, *, today=None):
    """3-3-3 成立年數(fund_row / compare 共用;report 走自己 richer 來源 + clamp)。

    回 (years|None, from_proxy)。成立日 meta 優先(精確);缺則 NAV 首日 proxy(下界,
    已套 H3 clamp:proxy < 3 年 → None)。today 可注入(測試 / 重現)。
    """
    import datetime as _dt333
    _today = today or _dt333.date.today()
    if inception_iso:
        try:
            _d = _dt333.date.fromisoformat(str(inception_iso)[:10])
            return (_today - _d).days / 365.25, False
        except (ValueError, TypeError):
            pass                              # 格式異常 → 落 NAV proxy
    if nav_first_iso:
        try:
            _d = _dt333.date.fromisoformat(str(nav_first_iso)[:10])
            _y = (_today - _d).days / 365.25
            return clamp_333_proxy_years(_y, True), True
        except (ValueError, TypeError):
            pass
    return None, False


def derive_ann_3y_for_333(fd: dict, metrics: Optional[dict] = None):
    """3-3-3 的「3 年平均年化報酬」——**含息優先**(H4,§4.1)。回 (ann_pct|None, basis)。

    老師 3-3-3 的「報酬 > 7%」語意是**含息總報酬**(定存替代品)。純 NAV 年化會漏掉配息、
    對配息型基金系統性偏低 → 假 ❌。優先序:
      1. 含息:MoneyDJ wb01 `perf["3Y"]` 累積(含配息再投資)→ 年化 → basis="含息(wb01)"
      2. 純NAV fallback:`metrics.ret_3y_ann` / `ret_3y_cum`(標 basis="純NAV(偏低)")
      3. 皆缺 → (None, "—")→ check_333 回 ⬜(§1 不硬判)
    P3 複數保護走 `_annualize_cum_pct`(cum ≤ −100% → None)。
    """
    _m = metrics if metrics is not None else (fd.get("metrics") or {})
    _mj = fd.get("moneydj_raw") or fd
    # 1) 含息優先(wb01 三年期累積 → 年化)
    _perf = fd.get("perf") or _mj.get("perf") or {}
    _ann_tr = _annualize_cum_pct(_safe_float(_perf.get("3Y")), 3)
    if _ann_tr is not None:
        return round(_ann_tr, 2), "含息(wb01)"
    # 2) 純NAV fallback(偏低,標註)
    _price_ann = _safe_float(_m.get("ret_3y_ann"))
    if _price_ann is not None:
        return round(_price_ann, 2), "純NAV(偏低)"
    _ann_price = _annualize_cum_pct(_safe_float(_m.get("ret_3y_cum") or _m.get("ret_3y")), 3)
    if _ann_price is not None:
        return round(_ann_price, 2), "純NAV(偏低)"
    return None, "—"
