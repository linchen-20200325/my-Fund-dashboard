"""除息基準日錨定引擎(SPEC v19.527 §0~§12)—— **規格驅動**測試。

本檔由測試組獨立於實作撰寫:每條 assert 對應規格的一條條文,合成 fixture 一律
自己按規格算出「應該長什麼樣」,不從 `services/dividend_calendar.py` 反推。
最後一段是 user 提供的 5 檔真實 MoneyDJ 配息表 walk-forward 回歸(§11 驗收基準)。

⚠️ 兩個刻意保留的外部相依(既有基礎設施,不在本次規格範圍):
  - `is_business_day()` —— 合成歷史用它產生「營業日校正後」的日期,這樣不論假日表
    有沒有 TW 假日,fixture 與引擎看到的是同一個世界(否則測試會變成在測假日表)。
  - `has_holiday_calendar()` —— §8 provenance 對照用。

規格 v2(§13)已定案原本三處未明定之處,本檔據此改寫:§13.1 陳舊度公式改單位、
§13.2 新增第 5 個假說 `MONTH_END_OFFSET` 與 deterministic 決選序、§13.3 ρ 的 0/0、
§13.4 每假說各估自己的 ρ、§13.5 雙配息分母、§13.6 驗收三口徑、§13.7 六條採納。

⚠️ 本檔仍有一個外部假設(壞掉時請先看這裡):§13.7.6 的 `_RECENT_N` 視窗大小未在規格
   給定數值。本檔所有信心測試的歷史長度 <= 18 筆,讓 k == len(history) 在 12~18 任一
   視窗值下都成立;唯一依賴視窗的 `test_fit_uses_recent_window_not_whole_history`
   用「近 18 筆乾淨 + 更早 12 筆換過錨」的組合,對 _RECENT_N <= 18 皆成立。
"""
from __future__ import annotations

import calendar as _calmod
import datetime as _dt
import math
import re
from collections import Counter

import pytest

import services.dividend_calendar as _dc
from services.dividend_calendar import (
    build_month_calendar,
    build_summary_text,
    detect_anchor,
    estimate_error_band,
    infer_schedule,
    is_business_day,
    predict_ex_for_month,
    project_anchor,
)

_DAY = _dt.timedelta(days=1)
_ANCHOR_TYPES = {"MONTH_END", "MONTH_END_OFFSET", "NTH_WEEKDAY",
                 "NTH_WEEKDAY_FROM_END", "FIXED_DAY"}
# §13.2 決選序:參數少者優先,同參數數依此序(deterministic)
_TIE_ORDER = ["MONTH_END", "MONTH_END_OFFSET", "FIXED_DAY",
              "NTH_WEEKDAY_FROM_END", "NTH_WEEKDAY"]
_ROLLS = {"following", "preceding", "modified_following"}


# ══════════════════════════════════════════════════════════════════════
# fixture 產生器 —— 全部按 SPEC §1 / §5 的定義自己算,不呼叫被測邏輯
# ══════════════════════════════════════════════════════════════════════
def _md(y: int, m: int) -> int:
    return _calmod.monthrange(y, m)[1]


def _roll(d: _dt.date, mode: str) -> _dt.date:
    """SPEC §5 的 R:following 往後 / preceding 往前 / modified_following 往後但不跨月。"""
    if is_business_day(d):
        return d
    if mode == "preceding":
        while not is_business_day(d):
            d -= _DAY
        return d
    if mode == "following":
        while not is_business_day(d):
            d += _DAY
        return d
    fwd, m = d, d.month
    while not is_business_day(fwd):
        fwd += _DAY
    if fwd.month == m:
        return fwd
    bwd = d
    while not is_business_day(bwd):
        bwd -= _DAY
    return bwd


def _months_ending(y: int, m: int, n: int, step: int = 1) -> list[tuple[int, int]]:
    """回傳 n 個 (年,月),最後一個是 (y, m),由舊到新。"""
    out = []
    for _ in range(n):
        out.append((y, m))
        m -= step
        while m < 1:
            m += 12
            y -= 1
    return list(reversed(out))


def _bdays(y: int, m: int) -> list[_dt.date]:
    return [_dt.date(y, m, d) for d in range(1, _md(y, m) + 1)
            if is_business_day(_dt.date(y, m, d))]


def _nth_last_bd(y: int, m: int, k: int) -> _dt.date | None:
    """該月倒數第 k 個營業日(k=1 → 最後一個)。不足 k 個 → None。"""
    b = _bdays(y, m)
    return b[-k] if len(b) >= k else None


def _last_bd(y: int, m: int) -> _dt.date:
    """SPEC §1 L(y,m):該月最後營業日。"""
    return _roll(_dt.date(y, m, _md(y, m)), "preceding")


def _nth_wd(y: int, m: int, w: int, j: int) -> _dt.date | None:
    """該月第 j 個星期 w(w:0=一)。"""
    off = (w - _dt.date(y, m, 1).weekday()) % 7
    day = 1 + off + 7 * (j - 1)
    return _dt.date(y, m, day) if day <= _md(y, m) else None


def _nth_wd_from_end(y: int, m: int, w: int, j: int) -> _dt.date | None:
    """該月倒數第 j 個星期 w。"""
    last = _dt.date(y, m, _md(y, m))
    off = (last.weekday() - w) % 7
    day = _md(y, m) - off - 7 * (j - 1)
    return _dt.date(y, m, day) if day >= 1 else None


def _fixed(y: int, m: int, D: int, mode: str = "following") -> _dt.date:
    """SPEC §1 FIXED_DAY:R(min(D, md(y,m)))。"""
    return _roll(_dt.date(y, m, min(D, _md(y, m))), mode)


def _hist_fixed(y, m, n, D=10, mode="following", step=1) -> list[_dt.date]:
    return [_fixed(yy, mm, D, mode) for yy, mm in _months_ending(y, m, n, step)]


def _hist_month_end(y, m, n, step=1) -> list[_dt.date]:
    return [_last_bd(yy, mm) for yy, mm in _months_ending(y, m, n, step)]


def _hist_month_end_offset(y, m, n, offset=1, step=1) -> list[_dt.date]:
    """§13.2 MONTH_END_OFFSET(offset):每月倒數第 (offset+1) 個營業日。"""
    return [_nth_last_bd(yy, mm, offset + 1) for yy, mm in _months_ending(y, m, n, step)]


def _recs(dates, pay_gap: int | None = None) -> list[dict]:
    """Cnyes 型:只有 `date`(SPEC §0 說此形態行為不變)。"""
    out = []
    for d in dates:
        r = {"date": d.isoformat(), "amount": 0.05}
        if pay_gap is not None:
            r["pay_date"] = (d + _dt.timedelta(days=pay_gap)).isoformat()
        out.append(r)
    return out


def _recs_fundclear(dates) -> list[dict]:
    """FundClear 型:三欄同值。"""
    return [{"date": d.isoformat(), "ex_date": d.isoformat(),
             "pay_date": d.isoformat(), "amount": 0.05} for d in dates]


def _recs_moneydj(dates, ex_shift_days: int = 8) -> list[dict]:
    """MoneyDJ 型:col[0] 配息基準日 != col[1] 除息日(SPEC §0 要改吃 col[0])。"""
    return [{"date": d.isoformat(),
             "ex_date": (d + _dt.timedelta(days=ex_shift_days)).isoformat(),
             "pay_date": (d + _dt.timedelta(days=ex_shift_days + 7)).isoformat(),
             "amount": 0.05} for d in dates]


def _no_anchor_dates() -> list[_dt.date]:
    """8 筆「四個假說都解釋不了」的歷史:全營業日、日號全不同、星期分散、無月底。"""
    days = [3, 7, 24, 13, 20, 21, 2, 23]
    return [_dt.date(y, m, d) for (y, m), d in zip(_months_ending(2026, 7, 8), days)]


def _wd_mode_share(dates) -> float:
    c = Counter(d.weekday() for d in dates)
    return max(c.values()) / len(dates)


# ══════════════════════════════════════════════════════════════════════
# §0 目標量改吃「除息基準日」(date 優先於 ex_date)
# ══════════════════════════════════════════════════════════════════════
def test_target_quantity_is_record_date_not_ex_date():
    """§0 核心:MoneyDJ 的 col[0]=配息基準日 才是要推的量,col[1]=除息日 只是衍生欄。

    錨錯欄位是這次要修的**本體 bug**:MoneyDJ 的除息日常被基準日 + 1~3 個營業日推開,
    月底型基金(如瀚亞)的除息日甚至落到下個月 1 號,錨在它身上整個月份網格會偏一格。
    """
    dates = _hist_fixed(2026, 7, 12, D=7)          # 基準日序列 = 每月 7 號(往後校正)
    sched = infer_schedule(_recs_moneydj(dates, ex_shift_days=8))   # 除息日 ≈ 15 號
    got = predict_ex_for_month(sched, 2026, 8, ref_year=2026, ref_month=7)
    assert got is not None, "乾淨的每月 7 號基準日序列不該推不出來"
    assert got["ex_date"] == _fixed(2026, 8, 7), (
        f"應錨在 date(7 號)得 {_fixed(2026, 8, 7)},實得 {got['ex_date']};"
        f"若接近 {_fixed(2026, 8, 15)} 代表仍錨在 ex_date")


def test_fundclear_and_cnyes_record_shapes_behave_identically():
    """§0:FundClear(三欄同值)與 Cnyes(只有 date)兩種來源行為必須不變。

    §0 只准 MoneyDJ 的目標量改變;若改欄位優先序時把「沒有 ex_date」的來源弄壞,
    境內基金與 Cnyes fallback 會整批消失在月曆上,而且是靜默消失。
    """
    dates = _hist_fixed(2026, 7, 12, D=10)
    a = predict_ex_for_month(infer_schedule(_recs(dates)), 2026, 8, ref_year=2026, ref_month=7)
    b = predict_ex_for_month(infer_schedule(_recs_fundclear(dates)), 2026, 8,
                             ref_year=2026, ref_month=7)
    assert a is not None and b is not None
    assert a["ex_date"] == b["ex_date"] == _fixed(2026, 8, 10)
    assert a["confidence"] == b["confidence"]


# ══════════════════════════════════════════════════════════════════════
# §1 四個錨定假說:參數估計 + 投影
# ══════════════════════════════════════════════════════════════════════
def test_anchor_month_end_estimated_and_projected():
    """§1 MONTH_END:0 參數,投影 = 該月最後營業日。

    這是聯博/瀚亞這類「月底結帳」基金的骨幹形態;認錯成固定日號會在 2 月(28/29 天)
    與月底遇六日的月份系統性早推 1~3 天。
    """
    hist = _hist_month_end(2026, 7, 14)
    a = detect_anchor(hist)
    # §13.2:倒數第 0 個營業日仍歸 MONTH_END(0 參數),不得被 MONTH_END_OFFSET(1 參數)吃掉,
    # 否則「純月底型」會失去 0 參數的優先權,平手時反而輸給比較會過擬合的假說。
    assert a is not None and a["type"] == "MONTH_END"
    assert a["params"] is None
    assert a["score"] >= 0.95
    assert project_anchor(a, 2026, 8) == _last_bd(2026, 8)
    assert project_anchor(a, 2027, 2) == _last_bd(2027, 2)   # 短月也要落在月內


def test_anchor_nth_weekday_estimated_and_projected():
    """§1 NTH_WEEKDAY:(w, j) 兩參數,投影 = 該月第 j 個星期 w。

    「每月第二個星期三」型基金的日號在 8~14 之間跳,固定日號假說永遠對不上;
    沒有這個假說就只能落 unpredictable 或硬給錯日期。
    """
    months = _months_ending(2026, 7, 24)
    hist = [_nth_wd(y, m, 2, 2) for y, m in months]           # 每月第 2 個星期三
    assert all(d is not None for d in hist)
    # 前提:倒數版索引不是常數,否則兩個 2 參數假說會平手(規格未定平手時誰贏)
    fe = {(-(-(_md(d.year, d.month) - d.day + 1) // 7)) for d in hist}
    assert len(fe) > 1, "fixture 失效:倒數索引若固定,NTH_WEEKDAY_FROM_END 會同分"
    assert all(is_business_day(d) for d in hist), "fixture 前提:24 筆全是營業日 → 零偏移"
    a = detect_anchor(hist)
    assert a is not None and a["type"] == "NTH_WEEKDAY"
    assert tuple(a["params"]) == (2, 2)
    assert a["score"] >= 0.95
    # §13.3:零偏移 → ρ 分母為 0 → 預設 following,並標記非從歷史推得
    assert a["roll_convention"] == "following"
    assert a["roll_inferred"] is False
    assert project_anchor(a, 2026, 8) == _nth_wd(2026, 8, 2, 2)


def test_anchor_nth_weekday_from_end_estimated_and_projected():
    """§1 NTH_WEEKDAY_FROM_END:施羅德型「每月最後一個星期三」。

    真實資料(SD080)18 筆全是星期三、且 15/18 是該月最後一個 —— 從月初數會在
    4 個星期三與 5 個星期三的月份之間跳格,只有從月底數才穩。
    """
    months = _months_ending(2026, 7, 24)
    nominal = [_nth_wd_from_end(y, m, 4, 1) for y, m in months]  # 每月最後一個星期五
    assert all(d is not None for d in nominal)
    fs = {(-(-d.day // 7)) for d in nominal}
    assert len(fs) > 1, "fixture 失效:從月初數的索引若固定,NTH_WEEKDAY 會同分"
    hist = [_roll(d, "preceding") for d in nominal]              # 撞連假的往前校正(真實世界)
    a = detect_anchor(hist)
    assert a is not None and a["type"] == "NTH_WEEKDAY_FROM_END"
    assert tuple(a["params"]) == (4, 1)
    assert a["score"] >= 0.90
    assert a["roll_inferred"] is True, "此 fixture 有 4 筆撞連假往前 → 方向是推得的"
    assert a["roll_convention"] == "preceding"
    tgt = _nth_wd_from_end(2026, 8, 4, 1)
    assert is_business_day(tgt), "fixture 失效:目標月的錨定日本身要是營業日,兩種校正才會同解"
    assert project_anchor(a, 2026, 8) == tgt


def test_anchor_fixed_day_estimated_and_projected():
    """§1 FIXED_DAY:單參數 D,投影 = R(min(D, 該月天數))。

    摩根型「每月 7 號」;短月要夾擠(min)、遇假日要校正(R),兩件事都不能漏。
    """
    hist = _hist_fixed(2026, 7, 12, D=10)
    a = detect_anchor(hist)
    assert a is not None and a["type"] == "FIXED_DAY"
    assert a["params"] == 10
    assert a["score"] >= 0.95
    assert project_anchor(a, 2026, 8) == _fixed(2026, 8, 10)


def test_anchor_month_end_offset_estimated_and_projected():
    """§13.2 新假說 MONTH_END_OFFSET(n):每月倒數第 (n+1) 個營業日,1 參數。

    聯博(ACTI71)的配息基準日就是這型(倒數第 2 個營業日,實測復現率 90%);
    四假說版本對它 12/12 全棄權 —— 不是推錯,是整檔基金從月曆上消失。
    固定日號解釋不了它:月長 28~31 天、月底遇六日與連假時日號會在 25~30 之間跳。
    """
    hist = _hist_month_end_offset(2026, 7, 18, offset=1)
    assert all(d is not None for d in hist)
    a = detect_anchor(hist)
    assert a is not None and a["type"] == "MONTH_END_OFFSET"
    assert a["params"] == 1
    assert a["score"] >= 0.95
    assert project_anchor(a, 2026, 8) == _nth_last_bd(2026, 8, 2)
    assert project_anchor(a, 2027, 2) == _nth_last_bd(2027, 2, 2)   # 短月照樣落在月內


def test_month_end_offset_projection_is_not_rolled_again():
    """§13.2:投影本身已落在營業日 → **不再套 R**(避免二次校正)。

    若實作寫成「月最後一天往前推 n 個日曆日再套 R」,遇到月尾連假就會整個歪掉:
    2025-01 的倒數第 2 個營業日是 1/23(離月底 8 個日曆日),二次校正版會落在別處,
    更糟的是會誤觸 §13.7.1 的 τ=3 而回 None —— 一整個農曆年月份的配息就此消失。
    """
    anchor = {"type": "MONTH_END_OFFSET", "params": 1, "score": 1.0, "runner_up": 0.0,
              "roll_convention": "preceding", "tie_broken": False, "roll_inferred": True}
    far = 0
    for y in range(2024, 2031):
        for m in range(1, 13):
            want = _nth_last_bd(y, m, 2)
            got = project_anchor(dict(anchor), y, m)
            assert got == want, f"{y}-{m} 應為倒數第 2 個營業日 {want},實得 {got}"
            if (_md(y, m) - want.day) > 3:
                far += 1
    assert far > 0, "fixture 失效:沒有任何月份的倒數第 2 營業日離月底 > 3 天"


def test_month_end_offset_returns_none_when_month_lacks_enough_business_days():
    """§13.2:該月營業日不足 n+1 個 → None(不可回退成「最後一個營業日」蒙混)。

    台股月曆最少也有 14 個營業日,n ∈ {1,2,3} 時這條分支在真實日曆下踩不到;
    但 `project_anchor` 會吃到外部傳入 / 反序列化的 anchor,越界時必須誠實回 None
    而不是 IndexError,也不是悄悄夾到最後一個營業日。
    """
    assert min(len(_bdays(y, m)) for y in (2025, 2026) for m in range(1, 13)) >= 5
    anchor = {"type": "MONTH_END_OFFSET", "params": 40, "score": 1.0, "runner_up": 0.0,
              "roll_convention": "preceding", "tie_broken": False, "roll_inferred": True}
    assert project_anchor(dict(anchor), 2026, 8) is None


def test_fixed_day_param_uses_half_up_median_not_bankers_rounding():
    """§1:`D* = floor(median + 0.5)`,**不可**用 `round()`。

    Python 的 `round(14.5) == 14`(banker's rounding)會讓「日號中位數落在 .5」的基金
    系統性偏早一天;偏早的那一天若不是營業日還會再被 R 拉走,錯得更遠。
    此處刻意造 median = 14.5:half-up → 15(能完美重現歷史),banker's → 14(只重現一半,
    直接掉到 §3 的 0.80 閘門以下 → 整檔變成推不出來)。
    """
    hi, lo = [], []                                    # 15 號是營業日 / 15 號被往前校正到 14
    for y, m in _months_ending(2027, 12, 36):
        d = _fixed(y, m, 15, "preceding")
        (hi if d.day == 15 else lo).append(d)
    if len(hi) < 2 or len([d for d in lo if d.day == 14]) < 2:
        pytest.skip("此假日表下找不到 median=14.5 的樣本")
    hist = sorted(hi[:2] + [d for d in lo if d.day == 14][:2])
    days = sorted(d.day for d in hist)
    assert days == [14, 14, 15, 15]                    # median 恰為 14.5
    a = detect_anchor(hist)
    assert a is not None, "half-up 應得 D*=15 並完美重現歷史;拿到 None 代表用了 banker's"
    assert a["type"] == "FIXED_DAY" and a["params"] == 15
    assert a["score"] >= 0.95


# ══════════════════════════════════════════════════════════════════════
# §2 復現率 s:必須「先套營業日校正 R 再比對」
# ══════════════════════════════════════════════════════════════════════
def test_score_applies_business_day_correction_before_comparing():
    """§2 ⚠️ 條:不套 R 就比對,月底型會被系統性低估(月底常遇六日/連假)。

    月底型基金的名目錨定日(月最後一天)有近 3 成落在非營業日;若拿名目值直接比對歷史,
    s 會掉到 0.7 上下 —— **正好卡在 §3 的 0.80 閘門下方**,整批月底型基金會被誤判成
    「找不到錨」而全部落 unpredictable(現有真實資料裡聯博/瀚亞兩檔就是這型)。
    """
    hist = _hist_month_end(2026, 7, 24)
    naive = sum(1 for d in hist if d.day == _md(d.year, d.month)) / len(hist)
    assert naive < 0.80, "fixture 失效:此樣本沒有足夠的月底非營業日"
    a = detect_anchor(hist)
    assert a is not None and a["type"] == "MONTH_END"
    assert a["score"] >= 0.95, (
        f"套 R 後 s 應接近 1.0,實得 {a['score']:.3f};"
        f"若接近未校正命中率 {naive:.3f} 代表比對前沒套 R")


def test_score_is_the_reproduction_ratio_of_history():
    """§2:s 是「能重現自身歷史的比例」,不是相關係數也不是分數化的擬合度。

    數字要能直接讀成「8 筆裡對 7 筆」,否則 §3 的 0.80 / §4 的 0.95 兩個閘門
    全部失去意義(門檻與量綱脫鉤 = §4.1 單位陷阱)。
    """
    hist = _hist_fixed(2026, 7, 8, D=10)
    hist[-1] = hist[-1] + _dt.timedelta(days=4)        # 動最新一筆,製造 1/8 不可重現
    while not is_business_day(hist[-1]):
        hist[-1] += _DAY
    a = detect_anchor(hist)
    assert a is not None and a["type"] == "FIXED_DAY" and a["params"] == 10
    assert math.isclose(a["score"], 7 / 8, abs_tol=0.02), (
        f"8 筆中 7 筆可重現 → s 應為 0.875,實得 {a['score']}")


# ══════════════════════════════════════════════════════════════════════
# §3 選模閘門:s < 0.80 / k < 3 / 平手
# ══════════════════════════════════════════════════════════════════════
def test_gate_returns_none_when_best_score_below_accept_min():
    """§3 + §1 Fail Loud:四個假說都解釋不了歷史 → 回 None,不硬給最不爛的那個。

    「最高分」不等於「夠好」。沒有這道閘門,亂數般的配息史也會被硬塞一個 FIXED_DAY,
    而且照 §4 的 k/h 條件還可能掛 medium —— 那正是這次要修的「錯還說有把握」。
    """
    hist = _no_anchor_dates()
    assert _wd_mode_share(hist) <= 0.30, "fixture 失效:星期眾數太集中,NTH_* 可能過關"
    assert all(is_business_day(d) for d in hist), "fixture 失效:配息日應落在營業日"
    assert not any(d == _last_bd(d.year, d.month) for d in hist), "fixture 失效:混到月底型"
    assert len({d.day for d in hist}) == len(hist), "fixture 失效:日號應全不同"
    assert detect_anchor(hist) is None


def test_gate_needs_at_least_three_records():
    """§3:k < 3 → None。兩筆資料可以完美擬合任何假說,s=1.0 完全沒有資訊量。

    這是 overfitting 的下限保護:新發行基金只配過 1~2 次時,任何錨都是巧合。
    """
    hist = _hist_fixed(2026, 7, 12, D=10)
    assert detect_anchor([]) is None
    assert detect_anchor(hist[-1:]) is None
    assert detect_anchor(hist[-2:]) is None
    assert detect_anchor(hist[-3:]) is not None        # k = 3 是可用的下界,不可連它也擋


def test_tie_prefers_fewer_parameters_and_flags_tie_broken():
    """§3:s⁽¹⁾-s⁽²⁾ < 0.10 → 取參數少者(MONTH_END 0 < FIXED_DAY 1 < NTH_* 2)。

    月底型與「固定 31 號 + 夾擠 + 往前校正」在歷史上完全同分,只有參數數能分勝負。
    選到參數多的那個不是無害的:它會在下一個 2 月或連假月份分岔,而且分岔時沒人看得出來,
    所以規格另外要求平手時信心上限壓 medium。
    """
    cand = [_dt.date(y, m, 31) for y, m in _months_ending(2027, 12, 48)
            if _md(y, m) == 31 and is_business_day(_dt.date(y, m, 31))]
    hist = sorted(cand[:6])
    assert len(hist) == 6, "fixture 失效:找不到 6 個 31 號為營業日的月份"
    assert _wd_mode_share(hist) <= 0.60, "fixture 失效:星期太集中會讓 NTH_* 也同分"
    a = detect_anchor(hist)
    assert a is not None
    assert a["score"] - a["runner_up"] < 0.10, "此 fixture 前提就是平手"
    assert a["tie_broken"] is True
    assert a["type"] == "MONTH_END" and a["params"] is None


def test_tie_order_prefers_month_end_offset_over_fixed_day():
    """§13.2 決選序:同為 1 參數時 MONTH_END_OFFSET 排在 FIXED_DAY 前。

    理由是月底相對錨跨不同月長更穩:選到 FIXED_DAY(30)的話,2 月(28/29 天)與
    月底遇連假的月份就會分岔,而歷史上這兩個假說一模一樣,分岔時沒有任何訊號。
    fixture 取「倒數第 2 個營業日恰為 30 號」的月份,兩者歷史復現率都是 1.0。
    """
    hist = sorted(d for d in (_nth_last_bd(y, m, 2)
                              for y, m in _months_ending(2027, 12, 60)) if d.day == 30)[:6]
    assert len(hist) == 6, "fixture 失效:找不到 6 個「倒數第 2 營業日 = 30 號」的月份"
    assert all(_md(d.year, d.month) == 31 for d in hist)
    assert not any(d == _nth_last_bd(d.year, d.month, 1) for d in hist), "不得同時是月底型"
    a = detect_anchor(hist)
    assert a is not None
    assert a["score"] - a["runner_up"] < 0.10, "此 fixture 前提就是平手"
    assert a["tie_broken"] is True
    assert a["type"] == "MONTH_END_OFFSET" and a["params"] == 1


def test_tie_order_prefers_from_end_over_nth_weekday():
    """§13.2 決選序:同為 2 參數時 NTH_WEEKDAY_FROM_END 排在 NTH_WEEKDAY 前。

    兩者只在「該月有 5 個星期 w」時分歧;fixture 取恰有 4 個星期三的月份,
    第 2 個星期三 == 倒數第 3 個星期三,歷史上完全同分。基金作業慣例錨月底側,
    所以規格定 FROM_END 勝 —— 重點是**有一個確定答案**,不是每次選模擲骰子。
    """
    cand = [_nth_wd(y, m, 2, 2) for y, m in _months_ending(2026, 7, 48)
            if sum(1 for d in range(1, _md(y, m) + 1)
                   if _dt.date(y, m, d).weekday() == 2) == 4]
    hist = sorted(d for d in cand if is_business_day(d))[:6]
    assert len(hist) == 6, "fixture 失效:找不到 6 個「恰 4 個星期三」的月份"
    assert {(-(-d.day // 7)) for d in hist} == {2}
    assert {(-(-(_md(d.year, d.month) - d.day + 1) // 7)) for d in hist} == {3}
    a = detect_anchor(hist)
    assert a is not None
    assert a["score"] - a["runner_up"] < 0.10, "此 fixture 前提就是平手"
    assert a["tie_broken"] is True
    assert a["type"] == "NTH_WEEKDAY_FROM_END"
    assert tuple(a["params"]) == (2, 3)


def test_tie_broken_anchor_cannot_reach_high_confidence():
    """§3:平手決選出來的錨,**且兩個假說對該月分岔時**,信心上限壓 medium。

    平手代表「有兩個同樣能解釋歷史、但未來會分岔的假說」,這種不確定性
    不該被 s=1.0 洗成 high —— §11 的驗收條件是「錯了就不准掛 high」。

    ⚠️ v19.531 修正 1 後本條是「**分岔**」那一半:封頂的觸發條件由「有平手旗標」
    收緊成「有平手旗標 **且** top-2 對該目標月投影出不同日期」。本 fixture 的對手
    (NTH_WEEKDAY_FROM_END)在目標月投影到別天,所以封頂**仍須**成立。
    「平手但同日」那一半見下一條 —— 兩條必須同時綠,少一條都會讓封頂邏輯偏向一邊。
    """
    sched = infer_schedule(_recs(_hist_fixed(2026, 7, 8, D=10)))
    base = predict_ex_for_month(sched, 2026, 8, ref_year=2026, ref_month=7)
    assert base is not None and base["confidence"] == "high", "前提:未平手時本例為 high"
    assert isinstance(sched.get("anchor"), dict), "§12:infer_schedule 須帶 anchor dict"
    sched["anchor"]["tie_broken"] = True
    got = predict_ex_for_month(sched, 2026, 8, ref_year=2026, ref_month=7)
    assert got is not None and got["confidence"] in ("medium", "low")
    _rival = sched["anchor"].get("runner_up_anchor")
    assert isinstance(_rival, dict), "v19.531:平手封頂要能比對投影,anchor 須帶得走對手假說"
    assert project_anchor(_rival, 2026, 8) != got["ex_date"], (
        "fixture 前提:本條測的是**分岔**那一半;若對手投影同日,壓的就不該是這條")


def test_tie_with_identical_projection_is_not_capped():
    """v19.531 修正 1:平手的兩個假說對**該目標月投影出同一天** → **不封頂**。

    §3 封頂要罰的是「兩個假說未來會分岔」;兩個模型指到同一天是**互相印證**,
    當成「不確定」處罰方向剛好相反。實證(user 5 檔真實資料,總管複驗):瀚亞 ACCP138
    的 MONTH_END 與 FIXED_DAY(31) 在近 12 筆視窗上 s 皆為 1.00、對 2026-09 同為 09/30,
    walk-forward 12/12 全中,舊版卻只給 medium;同一批資料 low 桶命中率 94% 反而高過
    medium 桶 85%,信心標籤成了反指標。

    本 fixture 用「每月最後營業日」的合成歷史重現同一個結構:MONTH_END(0 參數)與
    「31 號 + 往前校正」歷史上完全同分,但對這個目標月投影出同一天。
    """
    sched = infer_schedule(_recs(_hist_month_end(2026, 7, 12), pay_gap=7))
    a = sched.get("anchor")
    assert isinstance(a, dict), "§12:infer_schedule 須帶 anchor dict"
    assert a["tie_broken"] is True, "fixture 前提:這組歷史必須落在平手決選"
    assert a["score"] - a["runner_up"] < 0.10, "fixture 前提:前二名差距在平手窗內"
    rival = a.get("runner_up_anchor")
    assert isinstance(rival, dict), "v19.531:須回傳 top-2 中未被採用的那個假說供比對"
    got = predict_ex_for_month(sched, 2026, 8, ref_year=2026, ref_month=7)
    assert got is not None
    assert project_anchor(rival, 2026, 8) == got["ex_date"], (
        "fixture 前提:本月兩個假說必須投影同一天,否則測不到「同意」這件事")
    assert got["confidence"] == "high", (
        "兩個假說對本月指到同一天 = 互相印證,不該被平手封頂成 medium;"
        f"實得 {got['confidence']}(s={a['score']}, k={a['n']}, h={got['horizon_months']})")


def test_medium_score_cut_is_calibrated_ten_of_twelve_is_medium():
    """§4 + v19.531 修正 2:s = 10/12 = 0.833(12 筆對 10 筆)必須是 **medium**,不是 low。

    舊門檻 0.85 剛好切在 10/12=0.833 與 7/8=0.875 之間,把「穩定但視窗內帶 1~2 個
    舊離群值」的基金全掃進 low —— 5 檔真實資料實測那一格 15 筆 100% 命中,
    卻與「每 8 次錯 3 次」的爛錨共用同一個 low 標籤。門檻改由實測校準(網格通過區間
    med ∈ (9/11, 10/12]),本條鎖住區間上界:10/12 必須進得了 medium。

    ⚠️ 這條**不是**把門檻放寬到好看 —— 區間下界由 §13.6 硬門檻頂住
    (`test_real5_high_confidence_error_never_exceeds_one_day`),high 桶一筆都不准多塞。
    """
    hist = _hist_fixed(2026, 7, 12, D=10)
    for i in (2, 7):                       # 12 筆裡讓 2 筆偏離錨 → s 恰為 10/12
        d = hist[i] + _dt.timedelta(days=4)
        while not is_business_day(d):
            d += _DAY
        hist[i] = d
    sched = infer_schedule(_recs(hist, pay_gap=7))
    a = sched["anchor"]
    assert a is not None and math.isclose(a["score"], 10 / 12, rel_tol=1e-9), (
        f"fixture 失效:s 應為 10/12,實得 {a and a['score']}")
    got = predict_ex_for_month(sched, 2026, 8, ref_year=2026, ref_month=7)
    assert got is not None
    assert got["confidence"] == "medium", (
        f"s=10/12、k=12、h=1 應為 medium(v19.531 校準),實得 {got['confidence']}")


def test_gate_thresholds_live_in_module_constants():
    """§3.3 反捏造:0.80 / 0.10 兩個門檻必須是 module 常數 SSOT,不可 inline。

    這兩個數字決定「敢不敢給日期」,散在函式內部就無法被校準、被稽核、被一眼看見。
    """
    consts = {n: v for n, v in vars(_dc).items()
              if re.fullmatch(r"_?[A-Z][A-Z0-9_]*", n)
              and isinstance(v, (int, float)) and not isinstance(v, bool)}
    accept = [n for n, v in consts.items()
              if math.isclose(float(v), 0.80, abs_tol=1e-9)
              and re.search(r"ANCHOR|ACCEPT|SCORE|MIN", n)]
    tie = [n for n, v in consts.items()
           if math.isclose(float(v), 0.10, abs_tol=1e-9)
           and re.search(r"TIE|DELTA|ANCHOR", n)]
    assert accept, f"找不到 0.80 的接受門檻常數(建議 _ANCHOR_ACCEPT_MIN);現有常數={sorted(consts)}"
    assert tie, f"找不到 0.10 的平手門檻常數(建議 _ANCHOR_TIE_DELTA);現有常數={sorted(consts)}"


# ══════════════════════════════════════════════════════════════════════
# §4 信心 = s + 筆數 k + 地平線 h(day_std 退場)
# ══════════════════════════════════════════════════════════════════════
def _clean_sched(n=8, D=10, end=(2026, 7)):
    return infer_schedule(_recs(_hist_fixed(end[0], end[1], n, D=D), pay_gap=7))


def test_confidence_high_needs_score_count_and_horizon():
    """§4:high = s>=0.95 且 k>=6 且 h<=1。三個條件同時成立才准說「有把握」。

    high 是唯一會讓 user 照著日期進出場的等級,§11 要求它的錯誤率必須是 0。
    """
    got = predict_ex_for_month(_clean_sched(n=8), 2026, 8, ref_year=2026, ref_month=7)
    assert got is not None and got["confidence"] == "high"


def test_confidence_drops_to_medium_when_score_below_high_cut():
    """§4:s 掉到 0.95 以下(這裡 7/8 = 0.875)→ 最多 medium,即使 k 與 h 都很漂亮。

    「八次裡有一次不照錨走」就是每年會錯一次;錯一次而掛 high,比不給日期還糟。
    """
    hist = _hist_fixed(2026, 7, 8, D=10)
    hist[-1] = hist[-1] + _dt.timedelta(days=4)
    while not is_business_day(hist[-1]):
        hist[-1] += _DAY
    got = predict_ex_for_month(infer_schedule(_recs(hist)), 2026, 8,
                               ref_year=2026, ref_month=7)
    assert got is not None and got["confidence"] == "medium"


def test_confidence_count_boundaries():
    """§4 的 k 門檻 + **v19.532 阻斷 1**:k < 8 一律 low,k >= 8 才回到 §4 的 s/h 分級。

    ⚠️ **行為變更改斷言,不是放寬**:本條原本斷言 k=6 → high、k=5 → medium(照 §4 字面)。
    v19.532 對「每月從同一個 5 天窗內隨機挑一個營業日」的**純雜訊**歷史各跑 400 次,實測
    改動前 k=5 有 11 筆 medium、k=7 有 2 筆 high + 22 筆 medium —— 105 組候選參數擬 3~7 個點,
    窮舉本來就能「完美重現」一段沒有規律的歷史。s 高在小 k 只證明候選夠多,證明不了節奏存在。
    故 k < `_CONF_MIN_RECORDS_FOR_TRUST` 一律壓 low(仍**給日期**,只是誠實說沒把握)。
    改後同一實驗 k∈{3,5,7} 的 high 與 medium 皆為 **0 筆**。

    筆數是 s 的可信度本身 —— 3 筆全中的 s=1.0 與 12 筆全中的 s=1.0 不是同一回事。
    """
    trust = _dc._CONF_MIN_RECORDS_FOR_TRUST
    assert trust >= 4, "本條前提:門檻至少要蓋掉 §4 的 medium 下界(k>=4),否則測不到東西"
    got = {n: predict_ex_for_month(_clean_sched(n=n), 2026, 8, ref_year=2026, ref_month=7)
           for n in (3, 5, 6, 7, trust, trust + 1)}
    for n in (3, 5, 6, 7):
        assert got[n] is not None, (
            f"k={n} 不該整檔消失 —— §1 的誠實是『仍顯示但壓低信心』,不是全部隱藏"
            "(所以擋小 k 的是信心門檻,不是 `_ANCHOR_MIN_RECORDS`)")
        assert got[n]["confidence"] == "low", (
            f"k={n} < {trust}:純雜訊在這個筆數就能刷出 s=1.0,不准掛 medium/high")
    # k 到門檻就回到 §4 的分級(s=1.0、h=1 → high),證明壓低的是**筆數**而不是整條公式壞掉
    assert got[trust] is not None and got[trust]["confidence"] == "high"
    assert got[trust + 1] is not None and got[trust + 1]["confidence"] == "high"


def test_confidence_horizon_boundaries():
    """§4:h<=1 才可能 high、h<=3 可 medium、h>=4 一律 low(h 由 ref 與目標月算)。

    地平線是唯一會隨「看得多遠」單調惡化的變數:同一組歷史推下個月與推半年後,
    不該給同一個信心;現行版本沒有這個維度,才會出現「明年 3 月也掛 high」。
    """
    s = _clean_sched(n=12)
    got = {h: predict_ex_for_month(s, 2026, 7 + h, ref_year=2026, ref_month=7)
           for h in (1, 2, 3, 4)}
    assert all(v is not None for v in got.values()), "月配每個月都該有值,不該因 h 大就消失"
    assert got[1]["confidence"] == "high"
    assert got[2]["confidence"] == "medium"
    assert got[3]["confidence"] == "medium"
    assert got[4]["confidence"] == "low"
    assert [got[h]["horizon_months"] for h in (1, 2, 3, 4)] == [1, 2, 3, 4]


def test_day_std_no_longer_affects_confidence():
    """§4:`day_std` 從信心公式**完全移除**(稽核 A2:85~91% 錯誤率全掛 high)。

    7 個連續整數的母體標準差恆為 2.0,永遠低於舊的 `<=4` 閘門 —— 對星期錨定型基金
    這個條件恆真,等於白送 high。這裡直接把欄位灌成極端值:信心若跟著動,代表它還在公式裡。
    """
    s = _clean_sched(n=8)
    base = predict_ex_for_month(s, 2026, 8, ref_year=2026, ref_month=7)
    assert base is not None and base["confidence"] == "high"
    for poisoned in (99.0, 0.0, 4.0001):
        s2 = dict(s)
        s2["day_std"] = poisoned
        got = predict_ex_for_month(s2, 2026, 8, ref_year=2026, ref_month=7)
        assert got is not None and got["confidence"] == "high", (
            f"day_std={poisoned} 改變了信心 → 它仍在公式中")


def test_day_std_and_ex_day_fields_retained_for_compat():
    """§12:`ex_day` / `day_std` 欄位保留(相容),只是不再參與信心計算。

    直接刪欄會炸掉既有 caller 與既有測試;規格要的是「退役」不是「移除」。
    """
    s = _clean_sched(n=8)
    assert "ex_day" in s and "day_std" in s


# ══════════════════════════════════════════════════════════════════════
# §5 營業日校正方向從歷史推 + keep_month τ=3
# ══════════════════════════════════════════════════════════════════════
def _dev_stats(dates, D):
    """回傳 (偏移筆數, 往後筆數) —— 用來確認 fixture 真的能定出方向。"""
    dev = fwd = 0
    for d in dates:
        nom = _dt.date(d.year, d.month, min(D, _md(d.year, d.month)))
        if d != nom:
            dev += 1
            fwd += int(d > nom)
    return dev, fwd


def test_roll_direction_following_is_inferred_from_history():
    """§5:ρ₊ >= 0.8 → following。方向是**觀察**出來的,不是硬編的。

    摩根型基金遇六日往後遞延、施羅德型往前提,硬編任一方向都會讓另一型每逢連假就錯,
    而且錯的方向固定 = 系統性偏差。
    """
    hist = _hist_fixed(2026, 7, 24, D=10, mode="following")
    dev, fwd = _dev_stats(hist, 10)
    assert dev >= 3 and fwd == dev, "fixture 失效:應全部往後校正"
    a = detect_anchor(hist)
    assert a is not None and a["roll_convention"] == "following"
    assert a["roll_inferred"] is True, "§13.3:有偏移可推 → 旗標須為 True(以別於預設值)"


def test_roll_direction_preceding_is_inferred_from_history():
    """§5:ρ₋ >= 0.8 → preceding(安聯型:15 號遇六日往前抓 13/14)。"""
    hist = _hist_fixed(2026, 7, 24, D=15, mode="preceding")
    dev, fwd = _dev_stats(hist, 15)
    assert dev >= 3 and fwd == 0, "fixture 失效:應全部往前校正"
    a = detect_anchor(hist)
    assert a is not None and a["roll_convention"] == "preceding"
    assert a["roll_inferred"] is True


def test_zero_deviation_history_defaults_to_following_without_confidence_penalty():
    """§13.3:ρ 分母為 0(歷史零偏移)→ following,且**不壓信心**。

    原規格會把這種最規律的基金丟進「其餘」→ modified following + 壓 low,
    等於懲罰完美 —— 零偏移代表該假說完美,不是資訊不足。與 §4 的 high 直接衝突。
    """
    hist = [_nth_wd(y, m, 2, 2) for y, m in _months_ending(2026, 7, 14)]
    assert all(is_business_day(d) for d in hist), "fixture 前提:零偏移"
    a = detect_anchor(hist)
    assert a is not None and a["roll_convention"] == "following"
    assert a["roll_inferred"] is False
    got = predict_ex_for_month(infer_schedule(_recs(hist)), 2026, 8,
                               ref_year=2026, ref_month=7)
    assert got is not None and got["confidence"] == "high", "零偏移不該被壓信心"


def test_winning_hypothesis_supplies_the_roll_convention():
    """§13.4:每個假說各自估自己的 ρ,`roll_convention` 取**勝出假說**的那一個。

    月底型的名目錨定日 L(y,m) 本身就是營業日 → MONTH_END 自己的偏移數為 0 → 依 §13.3
    應回 following/roll_inferred=False;但同一批歷史若改用 FIXED_DAY(31) 的名目日
    (該月最後一個日曆日)去看,偏移全部朝後 → 會得到 preceding。兩者不同,
    正是「ρ 要跟著假說走」的證據 —— 拿錯那一個,未來投影就會被錯誤方向再校正一次。
    """
    hist = _hist_month_end(2026, 7, 18)
    nominal_dev = sum(1 for d in hist if d.day != _md(d.year, d.month))
    assert nominal_dev >= 6, "fixture 前提:以月最後一個日曆日為名目時偏移很多"
    a = detect_anchor(hist)
    assert a is not None and a["type"] == "MONTH_END"
    assert a["roll_inferred"] is False, "MONTH_END 自己的名目日就是營業日 → 零偏移"
    assert a["roll_convention"] == "following"


def test_roll_direction_mixed_falls_back_to_modified_following_and_low_confidence():
    """§5:兩個方向都沒到 0.8 → modified following,且**信心壓 low**。

    方向認不出來,代表這檔基金的順延規則本身不穩;此時就算 s 很高也只是「日號猜對」,
    真正的除息日仍可能差好幾天 —— 這種不確定性必須顯示在信心上,不能藏起來。
    """
    hist, flip = [], 0
    for y, m in _months_ending(2026, 7, 30):
        nom = _dt.date(y, m, 15)
        if is_business_day(nom):
            hist.append(nom)
            continue
        # 撞長連假的月份強制往前:往後會位移 > τ=3(§13.7.1 下那筆誰也解釋不了),
        # 混進來只會讓 s 被連假雜訊拖垮,不是本條要測的東西。
        forward = _roll(nom, "following")
        mode = ("preceding" if (forward - nom).days > 3
                else ("following" if flip % 2 == 0 else "preceding"))
        flip += 1
        hist.append(_roll(nom, mode))
    for window in (30, 12, 8):
        dev, fwd = _dev_stats(hist[-window:], 15)
        assert dev >= 2 and 0.2 <= fwd / dev < 0.8, (
            f"fixture 失效:近 {window} 筆的 ρ₊={fwd}/{dev} 不夠混,方向會被判成單向")
    a = detect_anchor(hist)
    assert a is not None and a["roll_convention"] == "modified_following"
    got = predict_ex_for_month(infer_schedule(_recs(hist)), 2026, 8,
                               ref_year=2026, ref_month=7)
    assert got is not None and got["confidence"] == "low"


_MODF_31 = {"type": "FIXED_DAY", "params": 31, "score": 1.0, "runner_up": 0.0,
            "roll_convention": "modified_following", "tie_broken": False}


def test_roll_shift_never_exceeds_tau_in_any_direction():
    """§13.7.1:**任何方向**的校正位移 > τ(3 日曆日)→ 該月無合理錨定日 → None。

    稽核 A4 實測最惡 -7 天且完全靜默:連假把整個月尾吃掉時,舊版會安靜地把除息日
    拉到一週前,畫面上看起來一樣理直氣壯。原規格只寫在 keep_month(modified following),
    但安聯型(preceding)碰到農曆年一樣被拉 7 天 —— v2 把上限擴到三個方向。
    這條 property 掃 7 年 84 個月 × 3 種 convention。
    """
    for conv in ("modified_following", "preceding", "following"):
        anchor = dict(_MODF_31, roll_convention=conv)
        for y in range(2024, 2031):
            for m in range(1, 13):
                nom = _dt.date(y, m, min(31, _md(y, m)))
                got = project_anchor(dict(anchor), y, m)
                if got is None:
                    continue
                assert is_business_day(got), f"{conv} {y}-{m} 投影落在非營業日 {got}"
                assert abs((got - nom).days) <= 3, (
                    f"{conv} {y}-{m} 位移 {(got - nom).days} 天,超過 τ=3")
                if conv == "modified_following":
                    assert (got.year, got.month) == (y, m), f"{y}-{m} keep_month 破功:{got}"


def test_preceding_roll_beyond_tau_returns_none():
    """§13.7.1:preceding 型也要受 τ 管。實測 2025-01 月底遇農曆年需回退 **7 天**。

    這是測試組回報、v2 才補上的洞:原規格只擋 keep_month,安聯這種「往前抓」的基金
    每逢農曆年就會被安靜地拉走一週,而且信心照樣掛得很高。
    """
    victims = []
    for y in range(2024, 2031):
        for m in range(1, 13):
            nom = _dt.date(y, m, _md(y, m))
            if is_business_day(nom):
                continue
            bwd = nom
            while not is_business_day(bwd):
                bwd -= _DAY
            if (nom - bwd).days > 3:
                victims.append((y, m, (nom - bwd).days))
    assert victims, "fixture 失效:此假日表下找不到回退 > 3 天的月份"
    for y, m, dist in victims:
        anchor = dict(_MODF_31, roll_convention="preceding")
        assert project_anchor(anchor, y, m) is None, (
            f"{y}-{m} preceding 需回退 {dist} 天(> τ=3),應回 None")


def test_keep_month_beyond_tau_returns_none():
    """§5:回退超過 τ → 回 None,寧可空著也不給一個被拉開的日期(§1 Fail Loud)。"""
    victims = []
    for y in range(2024, 2031):
        for m in range(1, 13):
            nom = _dt.date(y, m, _md(y, m))
            if is_business_day(nom):
                continue
            fwd = nom
            while not is_business_day(fwd):
                fwd += _DAY
            if fwd.month == m:
                continue
            bwd = nom
            while not is_business_day(bwd):
                bwd -= _DAY
            if (nom - bwd).days > 3:
                victims.append((y, m, (nom - bwd).days))
    for y, m, dist in victims:
        assert project_anchor(dict(_MODF_31), y, m) is None, (
            f"{y}-{m} 月尾連假需回退 {dist} 天(> τ=3),應回 None")


def test_project_returns_none_when_month_has_no_such_weekday_slot():
    """§5/§12:該月沒有第 5 個星期一 → None,不可退而求其次給第 4 個。

    「倒數第一個」與「第五個」在只有 4 個該星期的月份意義完全不同,退位等於換了一個錨。
    """
    anchor = {"type": "NTH_WEEKDAY", "params": (0, 5), "score": 1.0, "runner_up": 0.0,
              "roll_convention": "following", "tie_broken": False}
    short = [(y, m) for y in (2026, 2027) for m in range(1, 13)
             if _nth_wd(y, m, 0, 5) is None]
    assert short, "fixture 失效:找不到只有 4 個星期一的月份"
    for y, m in short:
        assert project_anchor(dict(anchor), y, m) is None


# ══════════════════════════════════════════════════════════════════════
# §6 cadence 視窗、相位眾數、漂移/雙配息
# ══════════════════════════════════════════════════════════════════════
def test_med_gap_uses_recent_window_not_whole_history():
    """§6:med_gap 改取近 k 筆(與 days 同視窗)。稽核 A7:兩個視窗不一致 = 每年吞/捏 8 筆。

    這檔基金五年前是季配、最近 14 個月改月配。用全史中位數會判成季配 →
    一年只列 4 個月、吞掉 8 次真實配息;user 看到的月曆會少一大半而且完全無聲。
    """
    dates = ([_fixed(y, m, 10) for y, m in _months_ending(2025, 3, 20, step=3)]
             + [_fixed(y, m, 10) for y, m in _months_ending(2026, 7, 14)])
    sched = infer_schedule(_recs(dates))
    assert sched["cadence"] == "monthly", f"近期已改月配,實得 {sched['cadence']}"
    got = predict_ex_for_month(sched, 2026, 8, ref_year=2026, ref_month=7)
    assert got is not None and got["ex_date"] == _fixed(2026, 8, 10)


def test_phase_is_mode_not_last_ex_month():
    """§6:相位取眾數 φ*(一致率 >= 0.8),**不可**取 last_ex.month。

    稽核 A8:一筆特別配息(年終加發)就會把整個季度網格旋轉一格 —— 2/5/8/11 變成
    3/6/9/12,之後每一季都推錯月份,而且錯得很整齊、看起來很合理。
    """
    grid = [_fixed(y, m, 10) for y, m in _months_ending(2025, 11, 12, step=3)]  # 2/5/8/11
    special = _fixed(2025, 12, 10)                                              # off-cycle
    sched = infer_schedule(_recs(sorted(grid + [special])))
    assert sched["anchor"] is not None, (
        "fixture 前提:特別配息與網格同日號,錨不受影響 —— 本條要隔離的是**相位**,"
        "不是錨;若錨也跟著壞,回 None 就不知道是哪一關擋的")
    on_grid = predict_ex_for_month(sched, 2026, 2, ref_year=2025, ref_month=12)
    rotated = predict_ex_for_month(sched, 2026, 3, ref_year=2025, ref_month=12)
    assert on_grid is not None, "2 月仍在原網格上,不該因一筆特別配息而消失"
    assert rotated is None, "3 月不在原網格上;有值代表網格被 last_ex(12 月)旋轉了"
    for off_grid in (2026, 4), (2026, 6), (2026, 9):
        assert predict_ex_for_month(sched, off_grid[0], off_grid[1],
                                    ref_year=2025, ref_month=12) is None, (
            f"{off_grid} 不在 2/5/8/11 網格上")


def test_phase_inconsistency_returns_none():
    """§6:相位一致率 < 0.8 → None。月份漂來漂去的基金沒有可用的「下一次」。"""
    months = [(2025, 1), (2025, 4), (2025, 7), (2025, 10), (2025, 12),
              (2026, 3), (2026, 6), (2026, 8), (2026, 11), (2027, 2)]
    dates = [_fixed(y, m, 15) for y, m in months]
    share = max(Counter(m % 3 for _, m in months).values()) / len(months)
    assert share < 0.8, "fixture 失效:相位其實很一致"
    sched = infer_schedule(_recs(dates))
    assert predict_ex_for_month(sched, 2027, 5, ref_year=2027, ref_month=2) is None


def test_irregular_cadence_returns_none_even_with_perfect_anchor():
    """§6:節奏不規則 → None,即使日號錨完美。

    這是本節最容易被實作漏掉的一半:錨(哪一天)與節奏(哪個月)是兩個獨立問題,
    s=1.0 只保證「若這個月有配,會配在 15 號」,不保證「這個月會配」。
    """
    months = [(2025, 1), (2025, 2), (2025, 5), (2025, 6), (2025, 9),
              (2025, 11), (2025, 12), (2026, 3), (2026, 4), (2026, 7)]
    dates = [_fixed(y, m, 15) for y, m in months]
    assert detect_anchor(dates) is not None, "前提:錨本身是乾淨的(全部 15 號)"
    sched = infer_schedule(_recs(dates))
    assert predict_ex_for_month(sched, 2026, 8, ref_year=2026, ref_month=7) is None


def test_double_dividend_month_detected_as_irregular():
    """§6 + §13.5:分母 = cadence 網格上**預期有配息的月份數**,分子 = 其中出現次數 != 1 者。

    現行 by_day 每檔每月只掛 1 筆(§9 明說本次不做雙配息資料結構),
    偵測到就必須誠實回 None,而不是靜默只顯示其中一筆。
    這個 fixture 刻意讓**錨仍然乾淨**(s≈0.84,穩穩過 §3 的 0.80):
    若實作只靠 §3 的 s 閘門而沒做雙配息偵測,這條就會紅 —— 兩個閘門不可互相頂替。
    """
    dates, doubled = [], 0
    for i, (y, m) in enumerate(_months_ending(2026, 7, 16)):
        base = _fixed(y, m, 10)
        dates.append(base)
        if (15 - i) % 5 == 0:                       # 由新到舊每 5 個月一次雙配息
            extra = base + _DAY
            while not is_business_day(extra):
                extra += _DAY
            dates.append(extra)
            doubled += 1
    assert doubled / 16 > 0.15, "fixture 失效:網格月份中的雙配息佔比不足"
    recent = sorted(dates)[-12:]
    recent_months = Counter((d.year, d.month) for d in recent)
    assert (sum(1 for v in recent_months.values() if v != 1) / len(recent_months)) > 0.15, (
        "fixture 失效:近 12 筆視窗內的雙配息佔比也要過門檻")
    sched = infer_schedule(_recs(sorted(dates)))
    assert sched["cadence"] == "irregular", "§6 原文:偵測到雙配息 → cadence 判 irregular"
    assert predict_ex_for_month(sched, 2026, 8, ref_year=2026, ref_month=7) is None


def test_quarterly_grid_is_not_misjudged_irregular():
    """§13.5 反向護欄:乾淨的季配基金**不得**被判 irregular。

    這是原分母定義會踩的坑:若分母算成「歷史跨越的所有年月」,季配基金有 8/12 個月
    是 0 次 → 佔比 0.67 → 每一檔季配都會被判不規則而整批消失。改成網格月份後,
    季配的 12 個網格月份每個都恰好 1 次 → 佔比 0。
    """
    grid = [_fixed(y, m, 10) for y, m in _months_ending(2025, 11, 12, step=3)]
    sched = infer_schedule(_recs(grid))
    assert sched["cadence"] == "quarterly"
    got = predict_ex_for_month(sched, 2026, 2, ref_year=2025, ref_month=11)
    assert got is not None, "乾淨季配被誤判成不規則 → 整批季配基金會從月曆上消失"


def test_fixed_30_day_interval_is_never_silently_predicted():
    """§6/稽核 A10:固定 30 天間隔型(非月配)現行 100% 錯誤且全掛 high。

    30 天不是一個月:日號每月往前漂約 0.44 天,一年漂掉 5 天。任何「月 + 日號」的錨
    都會逐月失準,§3 的 s 閘門必須把它擋下來 —— 這裡只要求「不准靜默給日期」。
    """
    start = _dt.date(2024, 1, 3)
    dates = [start + _dt.timedelta(days=30 * i) for i in range(36)]
    sched = infer_schedule(_recs(dates))
    last = dates[-1]
    got = predict_ex_for_month(sched, last.year + (last.month == 12),
                               last.month % 12 + 1,
                               ref_year=last.year, ref_month=last.month)
    assert got is None, f"30 天間隔型不該給出日期,實得 {got}"


# ══════════════════════════════════════════════════════════════════════
# §7 陳舊度:日差 + 絕對上限
# ══════════════════════════════════════════════════════════════════════
def test_stale_uses_day_difference_not_month_difference():
    """§7:`_stale` 改用日差。現行忽略 last_ex 的「日」,月初與月底算出同一個 _stale。

    兩檔同樣「最後一次配息在 10 月」的基金,一檔是 10/1 一檔是 10/31,真實陳舊度差 30 天
    (整整一個月配週期)。用月份差會讓它們同時失效/同時不失效 —— 也就是有一檔一定判錯。
    此處不綁絕對邊界(> 或 >= 兩種解讀都成立),只鎖「兩者的失效月份必不同」。
    """
    early = infer_schedule(_recs(_hist_fixed(2025, 10, 8, D=1)))
    late = infer_schedule(_recs(_hist_month_end(2025, 10, 8)))
    e_last = _fixed(2025, 10, 1)
    l_last = _last_bd(2025, 10)
    assert e_last.month == l_last.month == 10
    assert (l_last - e_last).days >= 29, "fixture 失效:兩者的日差不夠大"

    def _first_none(sched):
        for y, m in _months_ending(2027, 4, 18):
            if (y, m) <= (2025, 10):
                continue
            if predict_ex_for_month(sched, y, m, ref_year=y, ref_month=m) is None:
                return (y, m)
        return None

    fe, fl = _first_none(early), _first_none(late)
    assert fe is not None and fl is not None, "兩檔都該在掃描區間內因陳舊而失效"
    assert fe < fl, (
        f"月初({e_last})應比月底({l_last})更早判定陳舊;實得 {fe} vs {fl} "
        "→ 代表 _stale 仍只吃月份差")


def test_annual_fund_silent_35_months_returns_none():
    """§13.1:`stale_months = floor(日差 / 30.44)`,None 條件 `stale_months > min(3*step, 15)`。

    這是原公式**單位不一致**放行的那一格:靜默 1095 天,原式 `floor(1095/(30.44*12))` = 2
    去對門檻 15 → 放行,稽核 A11 原封不動。改成月為單位後 35 > 15 → 擋下。
    年配基金靜默三年還照推,等於把已清算/已停配的基金畫在月曆上。
    """
    dates = [_fixed(y, 5, 20) for y in (2019, 2020, 2021, 2022, 2023)]
    sched = infer_schedule(_recs(dates))
    last = _fixed(2023, 5, 20)
    for ref in ((2026, 4), (2026, 5)):
        gap_days = (_dt.date(ref[0], ref[1], 1) - last).days
        assert gap_days // 31 >= 33, "fixture 前提:靜默約 35 個月"
        assert predict_ex_for_month(sched, ref[0], 5, ref_year=ref[0],
                                    ref_month=ref[1]) is None


def test_quarterly_two_stale_periods_is_capped_low():
    """§13.1:`stale_periods = floor(stale_months / step) >= 2` → 信心壓 low(但仍給日期)。

    季配基金漏掉兩次配息(約 8~9 個月)還在門檻 9 個月之內,所以不該消失;
    但「連續兩期沒出現」本身就是異常訊號,不可再用 h<=1 的理由掛 high。
    """
    grid = [_fixed(y, m, 10) for y, m in _months_ending(2025, 11, 12, step=3)]
    sched = infer_schedule(_recs(grid))
    got = predict_ex_for_month(sched, 2026, 8, ref_year=2026, ref_month=8)
    assert got is not None, "8~9 個月 < 門檻 9 個月 → 不該回 None"
    assert got["confidence"] == "low"


def test_fresh_history_is_not_flagged_stale():
    """§7 反向:剛配完就推下個月,不可被陳舊度誤殺(否則整個月曆會空掉)。"""
    sched = _clean_sched(n=12)
    assert predict_ex_for_month(sched, 2026, 8, ref_year=2026, ref_month=7) is not None


# ══════════════════════════════════════════════════════════════════════
# §13.7 採納測試組點名的規格漏洞
# ══════════════════════════════════════════════════════════════════════
def test_project_anchor_raises_on_unknown_type():
    """§13.7.2:不認得的 `type` → **raise ValueError**,不可靜默回 None。

    回 None 會與「該月無合理錨定日」撞語意:前者是程式壞了(例如舊版序列化的錨、
    打錯字的常數),後者是業務上正常的空月。混在一起 = §1 的「讓程式不報錯」典型違憲。
    """
    bogus = {"type": "LAST_FRIDAY_ISH", "params": (4, 1), "score": 1.0, "runner_up": 0.0,
             "roll_convention": "following", "tie_broken": False, "roll_inferred": True}
    with pytest.raises(ValueError):
        project_anchor(bogus, 2026, 8)


def test_past_month_backfill_is_capped_low():
    """§13.7.3:h < 0(回填過去月份)允許,但信心上限壓 low。

    過去的月份應以**實際紀錄**為準;推估值放進歷史區間卻掛 high,會讓人分不清
    畫面上的是「真的發生過」還是「我們猜的」。允許顯示、但必須標成最低可信度。
    """
    sched = _clean_sched(n=12)
    got = predict_ex_for_month(sched, 2026, 5, ref_year=2026, ref_month=7)   # h = -2
    assert got is not None, "回填過去月份應允許(不是回 None)"
    assert got["horizon_months"] == -2
    assert got["confidence"] == "low"


def test_detect_anchor_does_not_assume_sorted_unique_input():
    """§13.7.4:函式內須自行排序去重,不得假設呼叫端給的順序。

    MoneyDJ 配息表是 newest-first,偶爾還有重複列;`detect_anchor` 是 public 純函式,
    未來會被別的 caller 直接呼叫。順序敏感的 bug 只會在特定來源上出現,極難追。
    """
    hist = _hist_fixed(2026, 7, 12, D=10)
    base = detect_anchor(list(hist))
    shuffled = list(reversed(hist)) + [hist[3], hist[0]]        # 倒序 + 重複兩筆
    got = detect_anchor(shuffled)
    assert base is not None and got is not None
    assert got["type"] == base["type"] and got["params"] == base["params"]
    assert math.isclose(got["score"], base["score"], abs_tol=1e-9)
    assert got["roll_convention"] == base["roll_convention"]


def test_irregular_fund_lands_in_unpredictable_with_reason():
    """§13.7.5:判 irregular 回 None 時,須落 unpredictable 桶並帶 `reason` 文字。

    UI 靠 reason 顯示「為什麼沒有日期」;靜默消失會讓 user 把「算不出來」
    誤讀成「這個月沒有配息」,那是 §1 明令禁止的假成功。
    """
    months = [(2025, 1), (2025, 2), (2025, 5), (2025, 6), (2025, 9),
              (2025, 11), (2025, 12), (2026, 3), (2026, 4), (2026, 7)]
    funds = [{"code": "IRR2", "name": "節奏不規則基金", "house": "",
              "dividends": _recs([_fixed(y, m, 15) for y, m in months])}]
    cal = build_month_calendar(funds, 2026, 8)
    assert cal["counts"]["unpredictable"] == 1 and cal["counts"]["excluded"] == 0
    reason = cal["unpredictable"][0].get("reason")
    assert isinstance(reason, str) and reason.strip(), "unpredictable 須帶非空 reason"


def test_fit_uses_recent_window_not_whole_history():
    """§13.7.6:k 與擬合都只吃近 `_RECENT_N` 筆視窗,不是全史。

    基金改配息日是常態(投信換作業窗口)。若拿全史擬合,改制後的新錨永遠被舊資料
    稀釋:此處近 18 筆全在 10 號、更早 12 筆全在 25 號 —— 全史 s = 18/30 = 0.6
    會掉出 §3 的 0.80 閘門 → 整檔變成推不出來,明明最近 18 次都準時在 10 號。
    """
    old = [_fixed(y, m, 25) for y, m in _months_ending(2025, 1, 12)]
    new = [_fixed(y, m, 10) for y, m in _months_ending(2026, 7, 18)]
    sched = infer_schedule(_recs(old + new))
    got = predict_ex_for_month(sched, 2026, 8, ref_year=2026, ref_month=7)
    assert got is not None, "近 18 筆乾淨卻推不出來 → 擬合吃到了視窗外的舊制"
    assert got["ex_date"] == _fixed(2026, 8, 10)
    assert got["confidence"] == "high"


# ══════════════════════════════════════════════════════════════════════
# §8 provenance 五個 key
# ══════════════════════════════════════════════════════════════════════
def test_provenance_keys_present_and_sane():
    """§8 + §2.2 血緣:推估結果要能自證「是哪個錨、多少分、怎麼校正、看多遠」。

    沒有這五個欄位,UI 與稽核只能看到一個日期和一個 high/medium/low,
    出錯時無從判斷是錨選錯、假日表缺、還是地平線太遠。
    """
    got = predict_ex_for_month(_clean_sched(n=12), 2026, 9, ref_year=2026, ref_month=7)
    assert got is not None
    for k in ("anchor_type", "anchor_score", "roll_convention",
              "holiday_calendar", "horizon_months"):
        assert k in got, f"§8 provenance 缺 key: {k}"
    assert got["anchor_type"] in _ANCHOR_TYPES
    assert 0.0 <= float(got["anchor_score"]) <= 1.0
    assert got["roll_convention"] in _ROLLS
    assert got["holiday_calendar"] in ("TW", "weekend_only")
    assert got["horizon_months"] == 2
    assert got["anchor_type"] == "FIXED_DAY"
    assert math.isclose(float(got["anchor_score"]), 1.0, abs_tol=0.06)


def test_holiday_calendar_provenance_matches_helper():
    """§8 ⚠️:假日表缺失時除息日準確度掉 10.2pp,但畫面一字不改(稽核 A12)。

    降級必須對 caller 可見 —— 這欄就是那面旗子,值要跟 `has_holiday_calendar()` 同步。
    """
    got = predict_ex_for_month(_clean_sched(n=12), 2026, 8, ref_year=2026, ref_month=7)
    assert got is not None
    helper = getattr(_dc, "has_holiday_calendar", None)
    if helper is None:
        pytest.skip("has_holiday_calendar 不存在(§8 evidence 指向 services/dividend_calendar)")
    assert got["holiday_calendar"] == ("TW" if helper() else "weekend_only")


# ══════════════════════════════════════════════════════════════════════
# §12 向後相容:既有 key 一個都不准少
# ══════════════════════════════════════════════════════════════════════
def _cal_funds():
    return [
        {"code": "TLZF9", "name": "安聯收益成長", "house": "安聯",
         "dividends": _recs(_hist_fixed(2026, 7, 12, D=14, mode="preceding"), pay_gap=30)},
        {"code": "ACDD01", "name": "安聯台灣大壩累積", "house": "安聯", "dividends": []},
        {"code": "IRR", "name": "不規則配息", "house": "",
         "dividends": _recs([_dt.date(2025, 1, 10), _dt.date(2025, 2, 20),
                             _dt.date(2025, 6, 5)])},
    ]


def test_build_month_calendar_keys_unchanged():
    """§12 硬性要求:`build_month_calendar` 輸出結構不可改。

    `ui/helpers/dividend_calendar_render.py` 與 `scripts/dividend_calendar_notify.py`
    都在消費它;少一個 key 就是 LINE 推播當場 KeyError,而且是在排程裡炸、沒人在看。
    """
    cal = build_month_calendar(_cal_funds(), 2026, 8)
    for k in ("year", "month", "by_day", "events", "excluded", "unpredictable", "counts"):
        assert k in cal, f"build_month_calendar 少了既有 key: {k}"
    for k in ("events", "excluded", "unpredictable"):
        assert k in cal["counts"], f"counts 少了既有 key: {k}"
    assert cal["year"] == 2026 and cal["month"] == 8
    assert all(isinstance(d, int) for d in cal["by_day"]), "by_day 的 key 仍須為 int 日號"
    ev = cal["events"][0]
    for k in ("code", "name", "house", "ex_date", "confidence"):
        assert k in ev, f"event 少了既有 key: {k}"
    assert isinstance(ev["ex_date"], _dt.date)
    assert cal["excluded"][0]["code"] == "ACDD01"
    assert "reason" in cal["unpredictable"][0]
    assert isinstance(build_summary_text(cal), str)


def test_infer_schedule_keys_unchanged_plus_anchor():
    """§12:`infer_schedule` 既有 key 全保留,新增 `anchor`(dict 或 None)。"""
    s = _clean_sched(n=12)
    for k in ("cadence", "confidence", "n", "ex_day", "day_std", "pay_gap_days"):
        assert k in s, f"infer_schedule 少了既有 key: {k}"
    assert "anchor" in s
    assert s["anchor"] is None or isinstance(s["anchor"], dict)
    if isinstance(s["anchor"], dict):
        for k in ("type", "params", "score", "runner_up", "roll_convention", "tie_broken"):
            assert k in s["anchor"], f"§12 anchor 契約缺 key: {k}"
    assert infer_schedule([])["anchor"] is None


def test_predict_keys_unchanged():
    """§12:`predict_ex_for_month` 既有三個 key(ex_date / pay_date_est / confidence)全保留。"""
    got = predict_ex_for_month(_clean_sched(n=12), 2026, 8, ref_year=2026, ref_month=7)
    assert got is not None
    for k in ("ex_date", "pay_date_est", "confidence"):
        assert k in got, f"predict_ex_for_month 少了既有 key: {k}"
    assert isinstance(got["ex_date"], _dt.date)
    assert got["confidence"] in ("high", "medium", "low")


def test_no_anchor_fund_lands_in_unpredictable_not_excluded():
    """§3 + §12:找不到錨 → 落 unpredictable(有配息史但推不出),不是 excluded(累積型)。

    兩個桶子的語意完全不同:excluded 在 UI 上整段移除,unpredictable 必須留著揭露,
    否則 user 會把「算不出來」誤讀成「這個月沒事」。
    """
    dates = _no_anchor_dates()
    cal = build_month_calendar(
        [{"code": "NOANCHOR", "name": "無錨基金", "house": "", "dividends": _recs(dates)}],
        2026, 8)
    assert cal["counts"]["excluded"] == 0
    assert cal["counts"]["events"] == 0
    assert cal["counts"]["unpredictable"] == 1


# ══════════════════════════════════════════════════════════════════════
# §11 真實資料回歸(user 2026-08-25 提供的 5 檔 MoneyDJ 配息表,逐列人工轉錄)
#     每列 = (配息基準日, 除息日, 發放日),newest-first
# ══════════════════════════════════════════════════════════════════════
_REAL_FUNDS = {
    "JFZN3 摩根": [
        ("2026/08/11", "2026/08/12", "2026/08/19"), ("2026/07/07", "2026/07/08", "2026/07/15"),
        ("2026/06/08", "2026/06/09", "2026/06/16"), ("2026/05/07", "2026/05/08", "2026/05/15"),
        ("2026/04/07", "2026/04/08", "2026/04/15"), ("2026/03/09", "2026/03/10", "2026/03/17"),
        ("2026/02/09", "2026/02/10", "2026/02/20"), ("2026/01/07", "2026/01/08", "2026/01/15"),
        ("2025/12/08", "2025/12/09", "2025/12/16"), ("2025/11/07", "2025/11/10", "2025/11/17"),
        ("2025/10/09", "2025/10/10", "2025/10/17"), ("2025/09/08", "2025/09/09", "2025/09/16"),
        ("2025/08/07", "2025/08/08", "2025/08/18"), ("2025/07/07", "2025/07/08", "2025/07/15"),
        ("2025/06/10", "2025/06/11", "2025/06/18"), ("2025/05/07", "2025/05/08", "2025/05/16"),
        ("2025/04/07", "2025/04/08", "2025/04/15"), ("2025/03/07", "2025/03/10", "2025/03/17"),
        ("2025/02/07", "2025/02/10", "2025/02/18"), ("2025/01/07", "2025/01/08", "2025/01/15")],
    "ACTI71 聯博": [
        ("2026/07/30", "2026/07/31", "2026/08/07"), ("2026/06/29", "2026/06/30", "2026/07/08"),
        ("2026/05/28", "2026/05/29", "2026/06/05"), ("2026/04/29", "2026/04/30", "2026/05/08"),
        ("2026/03/30", "2026/03/31", "2026/04/09"), ("2026/02/25", "2026/02/26", "2026/03/06"),
        ("2026/01/29", "2026/01/30", "2026/02/06"), ("2025/12/30", "2025/12/31", "2026/01/08"),
        ("2025/11/26", "2025/11/28", "2025/12/05"), ("2025/10/30", "2025/10/31", "2025/11/07"),
        ("2025/09/26", "2025/09/30", "2025/10/08"), ("2025/08/28", "2025/08/29", "2025/09/08"),
        ("2025/07/30", "2025/07/31", "2025/08/07"), ("2025/06/27", "2025/06/30", "2025/07/08"),
        ("2025/05/27", "2025/05/28", "2025/06/06"), ("2025/04/29", "2025/04/30", "2025/05/08"),
        ("2025/03/28", "2025/03/31", "2025/04/09"), ("2025/02/26", "2025/02/27", "2025/03/07"),
        ("2025/01/23", "2025/01/24", "2025/02/07"), ("2024/12/30", "2024/12/31", "2025/01/08")],
    "ACCP138 瀚亞": [
        ("2026/07/31", "2026/08/03", "2026/08/07"), ("2026/06/30", "2026/07/01", "2026/07/07"),
        ("2026/05/29", "2026/06/01", "2026/06/05"), ("2026/04/30", "2026/05/04", "2026/05/08"),
        ("2026/03/31", "2026/04/01", "2026/04/09"), ("2026/02/26", "2026/03/02", "2026/03/06"),
        ("2026/01/30", "2026/02/02", "2026/02/06"), ("2025/12/31", "2026/01/02", "2026/01/08"),
        ("2025/11/28", "2025/12/01", "2025/12/05"), ("2025/10/31", "2025/11/03", "2025/11/07"),
        ("2025/09/30", "2025/10/01", "2025/10/08"), ("2025/08/29", "2025/09/01", "2025/09/05"),
        ("2025/07/31", "2025/08/01", "2025/08/07"), ("2025/06/30", "2025/07/01", "2025/07/07"),
        ("2025/05/29", "2025/06/02", "2025/06/06"), ("2025/04/30", "2025/05/02", "2025/05/08"),
        ("2025/03/31", "2025/04/01", "2025/04/09"), ("2025/02/27", "2025/03/03", "2025/03/07"),
        ("2025/01/22", "2025/02/03", "2025/02/07"), ("2024/12/31", "2025/01/02", "2025/01/08")],
    "TLZF9 安聯": [
        ("2026/08/14", "2026/08/17", "2026/08/19"), ("2026/07/14", "2026/07/15", "2026/07/17"),
        ("2026/06/12", "2026/06/15", "2026/06/17"), ("2026/05/13", "2026/05/15", "2026/05/19"),
        ("2026/04/14", "2026/04/15", "2026/04/17"), ("2026/03/13", "2026/03/16", "2026/03/18"),
        ("2026/02/13", "2026/02/17", "2026/02/24"), ("2026/01/14", "2026/01/15", "2026/01/20"),
        ("2025/12/12", "2025/12/15", "2025/12/17"), ("2025/11/14", "2025/11/17", "2025/11/19"),
        ("2025/10/14", "2025/10/15", "2025/10/17"), ("2025/09/12", "2025/09/15", "2025/09/17"),
        ("2025/08/14", "2025/08/18", "2025/08/20"), ("2025/07/14", "2025/07/15", "2025/07/17"),
        ("2025/06/13", "2025/06/16", "2025/06/18"), ("2025/05/14", "2025/05/15", "2025/05/19"),
        ("2025/04/14", "2025/04/15", "2025/04/17"), ("2025/03/14", "2025/03/17", "2025/03/19"),
        ("2025/02/14", "2025/02/18", "2025/02/20"), ("2025/01/14", "2025/01/15", "2025/01/17")],
    "SD080 施羅德": [
        ("2026/07/29", "2026/07/30", "2026/08/06"), ("2026/06/24", "2026/06/25", "2026/07/06"),
        ("2026/05/27", "2026/05/28", "2026/06/04"), ("2026/04/29", "2026/04/30", "2026/05/13"),
        ("2026/03/25", "2026/03/26", "2026/04/02"), ("2026/02/25", "2026/02/26", "2026/03/05"),
        ("2026/01/28", "2026/01/29", "2026/02/05"), ("2025/12/17", "2025/12/18", "2026/01/02"),
        ("2025/11/19", "2025/11/20", "2025/12/01"), ("2025/10/29", "2025/10/30", "2025/11/11"),
        ("2025/09/24", "2025/09/25", "2025/10/08"), ("2025/08/27", "2025/08/28", "2025/09/09"),
        ("2025/07/30", "2025/07/31", "2025/08/12"), ("2025/06/25", "2025/06/26", "2025/07/09"),
        ("2025/05/28", "2025/05/29", "2025/06/09"), ("2025/04/23", "2025/04/24", "2025/05/09"),
        ("2025/03/26", "2025/03/27", "2025/04/08"), ("2025/02/26", "2025/02/27", "2025/03/10")],
}

_MIN_HIST = 8          # walk-forward 起手歷史筆數(>= §3 的 k>=3,且讓 §4 的 k 門檻有意義)
_WF_CACHE: dict = {}


def _iso(s: str) -> str:
    return s.replace("/", "-")


def _walk_forward():
    """只用「過去」推「下一筆」,逐筆前進。回傳 (命中, 有推估, 全部, 錯且掛 high 的明細)。"""
    if _WF_CACHE:
        return _WF_CACHE["v"]
    hit = predicted = total = 0
    wrong_high = []
    per_fund = {}
    for code, raw in _REAL_FUNDS.items():
        recs = [{"date": _iso(a), "ex_date": _iso(b), "pay_date": _iso(c)}
                for a, b, c in raw][::-1]                       # 轉成由舊到新
        f_hit = f_pred = f_total = 0
        for i in range(_MIN_HIST, len(recs)):
            hist = recs[:i]
            tgt = _dt.date.fromisoformat(recs[i]["date"])       # 目標 = 下一筆配息基準日
            ref = _dt.date.fromisoformat(hist[-1]["date"])
            total += 1
            f_total += 1
            got = predict_ex_for_month(infer_schedule(hist), tgt.year, tgt.month,
                                       ref_year=ref.year, ref_month=ref.month)
            if not got or not got.get("ex_date"):
                continue                                        # 誠實棄權(§1)
            predicted += 1
            f_pred += 1
            if got["ex_date"] == tgt:
                hit += 1
                f_hit += 1
            elif got.get("confidence") == "high":
                wrong_high.append((code, tgt.isoformat(), got["ex_date"].isoformat(),
                                   abs((got["ex_date"] - tgt).days)))
        per_fund[code] = (f_hit, f_pred, f_total)
    _WF_CACHE["v"] = (hit, predicted, total, wrong_high, per_fund)
    return _WF_CACHE["v"]


def test_real5_walk_forward_accuracy():
    """§11 驗收:5 檔真實 MoneyDJ 配息表 walk-forward,命中率 >= 85%(現行基準線 52%)。

    分母取「實際給出日期的筆數」—— 棄權(回 None)不算錯,那是 §1 要的誠實;
    但棄權也不能拿來刷分,所以覆蓋率另有下限(見 test_real5_coverage_not_gamed)。
    命中 = 推估日期與**配息基準日**逐日相等,不給模糊比對。
    """
    hit, predicted, total, _wh, per_fund = _walk_forward()
    assert total >= 50, f"walk-forward 樣本過少({total}),無法支撐 85% 的結論"
    assert predicted > 0, "五檔真實基金一筆都推不出來"
    acc = hit / predicted
    assert acc >= 0.85, (
        f"命中率 {acc:.1%}({hit}/{predicted})低於 §11 的 85%;逐檔 "
        f"{ {k: f'{v[0]}/{v[1]}' for k, v in per_fund.items()} }")


def test_real5_high_confidence_error_never_exceeds_one_day():
    """§13.6 硬門檻:「推錯 **且** high **且** |誤差| > 1 天」須為 0 筆。

    原 §11 要求「0 筆錯且 high」與 §4 的 `s>=0.95`(字面就是容許 5% 對不上)數學上互斥;
    實測那筆(安聯 2026-05,實際 05/13、推 05/14)是視窗外的一次性作業偏移,
    該檔近 12 筆視窗內 s=1.0,門檻拉到 1.0 也擋不住。v2 改成:
    高信心可以差 **1 個營業日**(不可建模的作業抖動,誠實);**不可以差 5 天還說有把握**。

    ⚠️ 這條轉綠必須是因為口徑放寬到 1 天,**不是**因為引擎改成棄權來規避 ——
    覆蓋率下限(test_real5_coverage_not_gamed)與逐檔覆蓋數(下面的 assert)就是那道保險。
    """
    _hit, _pred, _total, wrong_high, per_fund = _walk_forward()
    over = [w for w in wrong_high if w[3] > 1]
    assert over == [], (
        f"有 {len(over)} 筆推錯、掛 high 且誤差 > 1 天(code/實際/推估/誤差):{over[:5]}")
    assert per_fund["TLZF9 安聯"][1] >= 10, (
        "安聯的覆蓋數掉下來了 —— 這條轉綠必須來自 §13.6 的 1 天寬限,"
        f"不是靠棄權規避:{per_fund['TLZF9 安聯']}")


def test_real5_coverage_not_gamed():
    """§13.6 反向護欄:覆蓋率 >= 50%,不准靠「幾乎全部棄權」把命中率洗到 100%。

    §1 允許不給答案,但月曆的價值就是覆蓋;若引擎只敢推兩三筆,命中率再高也沒用。
    """
    _hit, predicted, total, _wh, per_fund = _walk_forward()
    assert predicted / total >= 0.5, (
        f"只對 {predicted}/{total} 筆敢給日期,覆蓋率過低;逐檔 "
        f"{ {k: f'{v[1]}/{v[2]}' for k, v in per_fund.items()} }")


def test_real5_last_but_one_business_day_fund_is_covered_not_abstained():
    """§13.2 的存在理由:聯博(倒數第 2 個營業日型)必須**被涵蓋**,不是誠實棄權。

    四假說版本對這檔 12/12 全棄權 —— §1 意義上不算錯,但這檔基金會整個從月曆上消失,
    而它的節奏其實非常規律(實測復現率 90%)。「不知道」與「沒去想」是兩回事。
    """
    _hit, _pred, _total, _wh, per_fund = _walk_forward()
    hit, pred, total = per_fund["ACTI71 聯博"]
    assert pred >= total * 0.5, (
        f"聯博只推了 {pred}/{total} 筆;倒數第 n 個營業日假說沒有覆蓋到它")
    assert hit / pred >= 0.80, f"聯博命中率 {hit}/{pred} 偏低,錨可能選錯"


# ══════════════════════════════════════════════════════════════════════
# v19.532 對抗式稽核四修(阻斷 1 / 阻斷 2 / bug 3 / bug 4)
#   四條的共同精神:引擎可以說「不知道」,但**不可以錯還說有把握**,也**不可以悄悄降級**。
# ══════════════════════════════════════════════════════════════════════
def _noise_history(rng, n, window=5):
    """**純雜訊**配息史:每月從同一個 5 天窗內隨機挑一天(校正到營業日),生成過程零規律。

    任何錨定假說都不該能重現這種歷史。它是「105 組候選參數(1+3+31+35+35)擬 k 個點」
    這件事的對照組 —— 窮舉能在雜訊上刷出多高的 s,就是過擬合的量級。
    """
    start = rng.randint(3, 22)
    y, m, out = 2023, rng.randint(1, 12), []
    while len(out) < n:
        day = min(rng.randint(start, start + window - 1), _md(y, m))
        out.append(_dc.roll_to_business_day(_dt.date(y, m, day)))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def test_pure_noise_history_never_claims_medium_or_high_at_small_k():
    """**阻斷 1 驗收**:純雜訊歷史在 k∈{3,5,7} 一筆 medium / high 都不准出現(low 可以)。

    改動前實測(每組 400 次):k=3 給出日期 22~30%(全 low)、k=5 含 **11 筆 medium**、
    k=7 含 **2 筆 high + 22 筆 medium**。稽核組另在 OOS(N=30000, k∈6..9)量到雜訊發出的
    high 預測裡 **49.2% 錯超過 1 天**。根因是窮舉:候選夠多,總有一組能「完美重現」3~7 個點。
    low 出現是**誠實**的(§1:仍顯示但明講沒把握),medium/high 不是。
    """
    import random
    seen_any = 0
    for k in (3, 5, 7):
        rng = random.Random(20260825 * 1000 + k)
        bad = []
        for _ in range(150):
            ser = _noise_history(rng, k + 1)
            hist, tgt = ser[:-1], ser[-1]
            got = predict_ex_for_month(infer_schedule(_recs(hist)), tgt.year, tgt.month,
                                       ref_year=hist[-1].year, ref_month=hist[-1].month)
            if got is None:
                continue
            seen_any += 1
            if got["confidence"] != "low":
                bad.append((k, hist[-1].isoformat(), got["confidence"]))
        assert bad == [], (
            f"k={k} 的純雜訊歷史拿到了 {len(bad)} 筆 medium/high(前 5 筆 {bad[:5]});"
            "窮舉在小樣本上刷出來的 s 不是節奏,是候選數")
    assert seen_any > 0, (
        "一筆日期都沒給 → 這條測試變成恆真的空跑,無法證明門檻有在做事"
        "(引擎在雜訊上該做的是『給日期但標 low』,不是全部棄權)")


def test_small_k_is_forced_low_even_with_a_flawless_history():
    """阻斷 1 的規則本體:k < `_CONF_MIN_RECORDS_FOR_TRUST` → low,**s=1.0 也一樣**。

    完美復現在小 k 下證明不了節奏存在,只證明候選參數夠多 —— 這是本次擋雜訊的唯一有效手段
    (k 相依的**接受門檻**在 k ≤ 9 是數學上的 no-op,見 `_ANCHOR_ACCEPT_MIN` 註解)。
    """
    trust = _dc._CONF_MIN_RECORDS_FOR_TRUST
    for n in range(_dc._ANCHOR_MIN_RECORDS, trust):
        sched = _clean_sched(n=n)
        assert sched["anchor"] is not None and sched["anchor"]["score"] == 1.0, (
            f"fixture 失效:k={n} 應為完美復現(s=1.0),實得 {sched['anchor']}")
        got = predict_ex_for_month(sched, 2026, 8, ref_year=2026, ref_month=7)
        assert got is not None, f"k={n} 不該整檔消失(§1:誠實壓低信心 > 全部隱藏)"
        assert got["confidence"] == "low", f"k={n} < {trust} 卻掛 {got['confidence']}"


def test_trust_threshold_is_a_module_constant_and_does_not_hide_new_funds():
    """§3.3:新門檻必須是 module 具名常數;且它**只壓信心、不擋顯示**。

    把 `_ANCHOR_MIN_RECORDS` 從 3 提到 8 也能擋雜訊,但那會讓新基金整檔從月曆消失 ——
    §1 的誠實是「說得出自己沒把握」,不是「看不到就沒事」。這條把兩者的分工鎖住。
    """
    trust = getattr(_dc, "_CONF_MIN_RECORDS_FOR_TRUST", None)
    assert isinstance(trust, int) and trust > _dc._ANCHOR_MIN_RECORDS, (
        f"找不到可信筆數門檻常數(或它不大於 _ANCHOR_MIN_RECORDS):{trust}")
    assert _dc._ANCHOR_MIN_RECORDS == 3, "§3 的 k>=3 顯示門檻不可跟著被抬高(新基金會消失)"
    cal = build_month_calendar(
        [{"code": "NEW", "name": "新發行月配", "house": "",
          "dividends": _recs(_hist_fixed(2026, 7, 4, D=10), pay_gap=7)}],
        2026, 8, ref_year=2026, ref_month=7)
    assert cal["counts"]["events"] == 1, "4 筆歷史的新基金仍要出現在月曆上"
    assert cal["events"][0]["confidence"] == "low", "只是信心必須誠實壓到 low"


def test_build_month_calendar_event_carries_the_five_provenance_keys():
    """**阻斷 2**:§8 的 5 個 provenance key 必須活著穿過 `build_month_calendar`。

    改動前 `predict_ex_for_month` 產出的 `anchor_score` / `anchor_type` / `holiday_calendar` /
    `horizon_months` / `roll_convention` 在這一層被整包丟掉,production 消費者零命中 ——
    §8(稽核 A12)等於只做到 L2 函式邊界,「假日表缺失時 ex 側降級不可見」根本沒修到。
    §12:既有 key 一個都不准少,只能增加。
    """
    cal = build_month_calendar(_cal_funds(), 2026, 8)
    ev = cal["events"][0]
    for k in ("code", "name", "house", "ex_date", "pay_date_est", "confidence",
              "last_amount", "last_yield", "n"):
        assert k in ev, f"§12 既有 event key 被弄丟:{k}"
    for k in ("anchor_type", "anchor_score", "roll_convention",
              "holiday_calendar", "horizon_months"):
        assert k in ev, f"§8 provenance key 沒穿過 build_month_calendar:{k}"
    assert ev["anchor_type"] in _ANCHOR_TYPES
    assert 0.0 <= float(ev["anchor_score"]) <= 1.0
    assert ev["roll_convention"] in _ROLLS
    assert ev["holiday_calendar"] in ("TW", "weekend_only")
    assert isinstance(ev["horizon_months"], int)
    assert cal.get("holiday_calendar") == ev["holiday_calendar"], (
        "月曆頂層要有一份整份共用的假日表狀態(L3 不必翻 events 才知道降級)")


def test_missing_holiday_calendar_is_visible_in_every_surface(monkeypatch):
    """**阻斷 2** 的重點:假日表降級必須**看得見** —— 文字 / Flex / HTML 頁尾三處都要改口。

    實測(user 5 檔真實配息表)有 TW 假日表:覆蓋 93.7% / 命中 89.8%;
    無假日表:覆蓋 **61.9%** / 命中 **84.6%**(跌破 §13.6 的 85% 門檻)—— 而在此之前
    畫面**一字不改**。準確度悄悄少一截卻照樣自信,§1 定義下就是「讓失敗看起來像成功」。
    (§13.8 把 L3 用詞測試歸 render 檔;這裡測的不是用詞而是**旗標有沒有一路傳到底**,
     故與 L2 三個 surface 一起鎖在同一條,斷鏈時一眼看得出斷在哪一段。)
    """
    from ui.helpers.dividend_calendar_render import render_month_calendar_html

    def _surfaces():
        cal = build_month_calendar(_cal_funds(), 2026, 8)
        return (cal, build_summary_text(cal), _dc.build_summary_flex(cal),
                render_month_calendar_html(cal))

    monkeypatch.setattr(_dc._tw_holidays, "_cache", None, raising=False)
    assert _dc.has_holiday_calendar() is False, "fixture 失效:應已模擬成假日表不可用"
    warn = _dc.holiday_calendar_note()
    assert warn and "國定假日" in warn, f"降級警語不該是空的:{warn!r}"
    cal, text, flex, html = _surfaces()
    assert cal["holiday_calendar"] == "weekend_only"
    assert warn in text, "純文字摘要沒說假日表缺失"
    assert warn in str(flex["contents"]), "Flex 卡片沒說假日表缺失"
    assert warn in html, "HTML 頁尾沒說假日表缺失"
    # 還原交給 monkeypatch teardown(它會把 `_cache` 還回原本的 holidays 物件);
    # 手動再 setattr 一次只會把 None 蓋回去,反而看起來像有還原其實沒有。


def test_holiday_calendar_note_is_silent_when_calendar_is_present():
    """降級警語只在**真的降級**時出現 —— 沒事也喊狼會讓真的降級被當背景雜訊。"""
    if not _dc.has_holiday_calendar():
        pytest.skip("此環境本來就沒有 TW 假日表,測不到『有假日表 → 不警告』")
    cal = build_month_calendar(_cal_funds(), 2026, 8)
    assert cal["holiday_calendar"] == "TW"
    assert _dc.holiday_calendar_note(cal) == ""
    assert "未載入國定假日表" not in build_summary_text(cal)


def _tau() -> int:
    return _dc._KEEP_MONTH_MAX_SHIFT_DAYS


def test_reverse_direction_is_tried_when_primary_exceeds_tau():
    """**bug 3**:主方向留在月內但位移 > τ 時,舊版直接回 None,**從不試反向**。

    §13.7.1 寫的是「**任何方向**的校正位移 > τ → None」,舊實作只評估了一個方向 ——
    反向回退只在「主方向跨出月份」時觸發。掃 2025–2028 × 全假說 × 3 convention,
    **117 組**是「引擎回 None,但反方向存在 τ 內的當月營業日」。
    其中 `FIXED_DAY(14) / following / 2026-02`(名目 2/14 撞農曆年)推出的 **2026-02-13
    正是 user 安聯 TLZF9 的真實基準日**,只差 1 天卻整月消失。
    """
    a14 = {"type": "FIXED_DAY", "params": 14, "score": 1.0, "runner_up": 0.0,
           "roll_convention": "following", "tie_broken": False}
    got = project_anchor(dict(a14), 2026, 2)
    assert got == _dt.date(2026, 2, 13), f"2026-02 應回退到 2/13(user 真實基準日),實得 {got}"
    a25 = dict(a14, params=25)
    assert project_anchor(a25, 2026, 9) == _dt.date(2026, 9, 24), "2026-09 中秋同型"


def test_none_only_when_both_directions_are_impossible():
    """bug 3 的 property:回 None ⟺ **兩個方向都**沒有「當月 + τ 內」的營業日。

    掃全假說 × 3 convention × 2025–2028。回 None 必須是「真的推不出」,
    不能是「只往一個方向看了一眼」(§1:棄權要棄得有道理,否則就是靜默漏資料)。
    """
    for conv in _ROLLS:
        for a_type in _TIE_ORDER:
            for params in _dc._anchor_candidates(a_type):
                anchor = {"type": a_type, "params": params, "score": 1.0, "runner_up": 0.0,
                          "roll_convention": conv, "tie_broken": False}
                for y in range(2025, 2029):
                    for m in range(1, 13):
                        nom = _dc._anchor_nominal(a_type, params, y, m)
                        if nom is None:
                            continue
                        feasible = []
                        for sign in (1, -1):
                            cur = nom
                            for _ in range(40):
                                cur += sign * _DAY
                                if is_business_day(cur):
                                    break
                            if is_business_day(nom):
                                cur = nom
                            if (cur.year, cur.month) == (y, m) and abs((cur - nom).days) <= _tau():
                                feasible.append(cur)
                        got = project_anchor(dict(anchor), y, m)
                        if got is None:
                            assert not feasible, (
                                f"{a_type}{params} {conv} {y}-{m:02d} 回 None,但 "
                                f"{feasible} 是當月、營業日、位移 <= τ 的合理解")
                        else:
                            assert got in feasible, f"{a_type}{params} {conv} {y}-{m:02d} → {got}"


def test_primary_direction_still_wins_when_both_are_feasible():
    """bug 3 的護欄:兩邊都可行時取**主方向**,不是取位移較小者。

    convention 是 §5 從歷史 ρ>=0.8 推出來的觀察值:「週六 → 週一(+2)」對 following 型
    基金是它真實的作業行為。改成「就近取週五(-1)」= 用沒有證據的規則蓋掉有證據的規則,
    5 檔實測三個口徑同時退步(命中 89.8% → 84.0% 跌破門檻、覆蓋 93.7% → 79.4%、
    §13.6 硬門檻 0 → 1 筆)。
    """
    sat = [(y, m, d) for y in (2026, 2027) for m in range(1, 13)
           for d in [_dt.date(y, m, 14)]
           if d.weekday() == 5 and is_business_day(d + _DAY * 2) and is_business_day(d - _DAY)]
    assert sat, "fixture 失效:找不到 14 號是週六、前後皆為營業日的月份"
    for y, m, d in sat:
        fwd = {"type": "FIXED_DAY", "params": 14, "score": 1.0, "runner_up": 0.0,
               "roll_convention": "following", "tie_broken": False}
        assert project_anchor(dict(fwd), y, m) == d + _DAY * 2, f"{y}-{m} following 應往後到週一"
        assert project_anchor(dict(fwd, roll_convention="preceding"), y, m) == d - _DAY, (
            f"{y}-{m} preceding 應往前到週五")


def test_stale_ref_day_uses_caller_supplied_day_not_a_fixed_mid_month():
    """**bug 4**:`_stale_state` 的 ref 日改由 caller 給;預設仍是 15(相容)。

    production 的 cron 是 `0 0 1 * *`(每月 1 號)→ `now.day` 恆為 1,而引擎恆用 15 號
    = **每次執行都把陳舊度多算 14 天**。「月中是無偏中點」只在執行日均勻分布時成立。
    實測(cron 於 2026-09-01 觸發、月配、last=2026-05-11):真實靜默 113 天(< 122 天門檻),
    引擎算成 127 天 → 判疑停配 → **整檔基金從月曆上消失**。
    """
    last = _dt.date(2026, 5, 11)
    assert _dc._stale_state(last, 2026, 9, 1) == _dc._stale_state(last, 2026, 9, 1, 15), \
        "不給 ref_day 時必須維持舊行為(15 號),否則所有既有 caller 一起偏移"
    m15, _p15, stale15 = _dc._stale_state(last, 2026, 9, 1, 15)
    m01, _p01, stale01 = _dc._stale_state(last, 2026, 9, 1, 1)
    assert (m15, stale15) == (4, True), f"15 號口徑:4 個月、判過舊,實得 {(m15, stale15)}"
    assert (m01, stale01) == (3, False), f"1 號口徑:3 個月、未過舊,實得 {(m01, stale01)}"


def test_cron_day_one_no_longer_loses_a_monthly_fund_to_stale_gate():
    """bug 4 端對端:同一檔月配基金,傳真實日(1 號)時留在月曆上,不傳時整檔消失。"""
    hist, d = [], _dt.date(2025, 6, 11)
    while d <= _dt.date(2026, 5, 11):
        hist.append(_dc.roll_to_business_day(d))
        d = _dt.date(d.year + (d.month == 12), 1 if d.month == 12 else d.month + 1, 11)
    sched = infer_schedule(_recs(hist))
    assert sched["last_ex"] == _dt.date(2026, 5, 11) and sched["cadence"] == "monthly"
    real = predict_ex_for_month(sched, 2026, 10, ref_year=2026, ref_month=9, ref_day=1)
    assert real is not None and real["ex_date"].month == 10, (
        "cron 於 2026-09-01 執行:真實靜默 113 天 < 122 天門檻,不該判疑停配")
    assert predict_ex_for_month(sched, 2026, 10, ref_year=2026, ref_month=9) is None, (
        "fixture 前提:舊的固定 15 號口徑會把這檔算成 127 天而誤殺 —— 這正是 bug 4 的代價")
    cal = build_month_calendar(
        [{"code": "M11", "name": "月配 11 號", "house": "", "dividends": _recs(hist)}],
        2026, 10, ref_year=2026, ref_month=9, ref_day=1)
    assert cal["counts"]["events"] == 1, "build_month_calendar 也要能把 ref_day 傳下去"


def test_ref_day_out_of_range_is_clamped_not_overflowed():
    """bug 4 邊界:2 月傳 31 號 → 夾到月底,不可讓 `date()` 炸掉或溢位到 3 月(§1 不造假日期)。"""
    last = _dt.date(2025, 12, 20)
    assert _dc._stale_state(last, 2026, 2, 1, 31) == _dc._stale_state(last, 2026, 2, 1, 28)
    assert _dc._stale_state(last, 2026, 2, 1, 0) == _dc._stale_state(last, 2026, 2, 1, 1)


def test_production_callers_pass_the_real_day_down():
    """bug 4 的另一半:L2 收得到 `ref_day` 沒用,**caller 要真的傳**。

    這條鎖的是「修了但沒接線」這種最貴的假修復 —— 引擎改對了、cron 還是每月 1 號用 15 號口徑,
    測試全綠而 user 的基金照樣每隔幾個月消失一次。
    """
    import pathlib
    import re
    for rel in ("scripts/dividend_calendar_notify.py", "ui/tab_manage.py"):
        src = pathlib.Path(rel).read_text(encoding="utf-8")
        call = re.search(r"build_month_calendar\((?:[^()]|\([^()]*\))*\)", src, re.S)
        assert call, f"{rel} 找不到 build_month_calendar 呼叫"
        assert "ref_day=" in call.group(0), (
            f"{rel} 呼叫 build_month_calendar 時沒把真實日期傳下去:{call.group(0)}")


# ══════════════════════════════════════════════════════════════════════
# §15.1 `estimate_error_band` —— 逐檔誤差帶(取代畫面上的「高/中/低」三級標籤)
#   核心紅線:**每檔只准用自己的歷史**。用全站合併分布回填單一基金 = 讓一檔沒有證據的
#   基金借用別檔的準確度,那是 §1 意義下的捏造 —— 比不給數字更危險。
# ══════════════════════════════════════════════════════════════════════
def _err_divs(dates):
    """[date] → `estimate_error_band` 吃得下的 dividends(只需要基準日)。"""
    return [{"date": d.isoformat()} for d in dates]


def _clean_monthly(day, n, start=(2024, 1)):
    """n 筆「每月固定 day 號、落非營業日則校正」的乾淨月配史(誤差帶應為 0)。"""
    out, (y, m) = [], start
    for _ in range(n):
        out.append(_dc.roll_to_business_day(_dt.date(y, m, min(day, _calmod.monthrange(y, m)[1]))))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def test_error_band_none_when_history_too_short():
    """歷史 < 8 筆 → **不給數字**(回 None)。

    §15.1:8 筆是 `_CONF_MIN_RECORDS_FOR_TRUST`,同一條「這檔基金的歷史夠不夠撐一個
    有數字的宣稱」門檻。7 筆的基金畫面上顯示「僅供參考」,而不是一個看起來有把握的 ±0 天。
    """
    for _n in (0, 1, 3, 7):
        assert estimate_error_band(_err_divs(_clean_monthly(14, _n))) is None, f"n={_n}"
    assert estimate_error_band(None) is None                 # 無資料也不可回 0(§1)
    assert estimate_error_band([]) is None


def test_error_band_none_when_walk_forward_samples_too_few():
    """歷史夠長、但 walk-forward 幾乎全棄權 → 樣本 < 3 → 仍回 None。

    §1:分位數建立在 1~2 個樣本上沒有意義,那種「±0 天」是假精確。
    這裡用 10 筆**完全不規則**的歷史:每次都推不出來 → 樣本 0 → None。
    """
    rng = __import__("random").Random(915)
    _base = _dt.date(2024, 1, 3)
    _dates, _cur = [], _base
    for _ in range(10):
        _cur = _dc.roll_to_business_day(_cur + _dt.timedelta(days=rng.randint(17, 47)))
        _dates.append(_cur)
    assert estimate_error_band(_err_divs(_dates)) is None


def test_error_band_zero_for_perfectly_regular_fund():
    """每月固定日號、12 筆 → walk-forward 逐日命中 → 誤差帶 0(畫面顯示「±0 天」)。"""
    assert estimate_error_band(_err_divs(_clean_monthly(14, 12))) == 0


def test_error_band_grows_with_real_jitter():
    """同一檔基金加入作業抖動後,誤差帶**必須變大** —— 否則這個數字沒有在測量任何東西。"""
    _clean = _clean_monthly(14, 16)
    _jit = list(_clean)
    for _i in range(9, len(_jit)):                 # 只動 walk-forward 會評到的後段
        _jit[_i] = _dc.roll_to_business_day(_jit[_i] + _dt.timedelta(days=3 + (_i % 4)))
    _b0, _b1 = estimate_error_band(_err_divs(_clean)), estimate_error_band(_err_divs(_jit))
    assert _b0 == 0
    assert _b1 is None or _b1 > _b0, f"抖動後誤差帶沒變大:{_b0} → {_b1}"


def test_error_band_is_per_fund_and_stateless():
    """§15.1 紅線:**禁止**用全站合併分布回填單一基金。

    這條測的是「函式只吃這一檔的歷史,而且不帶跨呼叫的狀態」——
    先算一次弱歷史的結果,中間夾 30 次強歷史的呼叫,再算一次弱歷史:兩次必須完全相同。
    若哪天有人加了「全站誤差快取 / 全域校準」,弱檔就會被強檔的分布拉好看,這條會立刻紅。
    """
    _weak = _err_divs(_clean_monthly(14, 8))       # 剛好 8 筆 → 樣本數少
    _strong = _err_divs(_clean_monthly(9, 20))
    _first = estimate_error_band(_weak)
    for _ in range(30):
        estimate_error_band(_strong)
    assert estimate_error_band(_weak) == _first
    # 簽名只收一檔的 dividends —— 沒有第二個參數可以把別檔的資料餵進來
    import inspect
    _sig = list(inspect.signature(estimate_error_band).parameters)
    assert _sig == ["dividends"], f"簽名多了東西,可能是全站分布的入口:{_sig}"


def test_error_band_matches_acceptance_walk_forward_shape():
    """口徑 drift-lock:誤差帶的 walk-forward 必須與 §13.6 驗收同一套規則。

    起手 8 筆(`_MIN_HIST`)、只用過去推下一筆、**棄權不計入誤差樣本**。
    棄權在畫面上本來就不顯示數字,把它當成 0 天誤差會把誠實棄權洗成準確度(§1)。
    這裡用真實資料逐檔比對:自己重算一次分位數,必須與函式輸出一致。
    """
    import math as _m
    for code, raw in _REAL_FUNDS.items():
        recs = [_dt.date.fromisoformat(_iso(a)) for a, _b, _c in raw][::-1]
        errs = []
        for i in range(_MIN_HIST, len(recs)):
            tgt, ref = recs[i], recs[i - 1]
            got = predict_ex_for_month(infer_schedule(_err_divs(recs[:i])), tgt.year, tgt.month,
                                       ref_year=ref.year, ref_month=ref.month)
            if got and got.get("ex_date"):
                errs.append(abs((got["ex_date"] - tgt).days))
        if len(errs) < 3:
            assert estimate_error_band(_err_divs(recs)) is None, code
            continue
        _s = sorted(errs)
        _h = (len(_s) - 1) * 0.80
        _lo = int(_h)
        _hi = min(_lo + 1, len(_s) - 1)
        _want = int(_m.ceil(_s[_lo] + (_h - _lo) * (_s[_hi] - _s[_lo])))
        assert estimate_error_band(_err_divs(recs)) == _want, code


def test_error_band_on_real_five_funds_is_plausible():
    """user 5 檔真實配息表的誤差帶:四檔規律者 <= 2 天,施羅德(節奏最亂)明顯較大。

    §1:這條不是為了鎖死數字,是為了擋「全部回 0 天」或「全部回 None」這兩種
    看起來很乾淨、實際上沒在測量任何東西的退化。
    """
    _bands = {c: estimate_error_band(_err_divs([_dt.date.fromisoformat(_iso(a))
                                                for a, _b, _c in raw][::-1]))
              for c, raw in _REAL_FUNDS.items()}
    assert all(b is not None for b in _bands.values()), _bands   # 5 檔歷史都 >= 8 筆
    for _c in ("JFZN3 摩根", "ACTI71 聯博", "ACCP138 瀚亞", "TLZF9 安聯"):
        assert _bands[_c] <= 2, (_c, _bands)
    assert _bands["SD080 施羅德"] > 2, _bands                     # 最亂的那檔不可被美化


def test_build_month_calendar_carries_error_band_and_keeps_confidence():
    """§12 相容 + §15.1:event 多一個 `error_band`,`confidence` **一個字都不能少**。

    引擎的 confidence 仍是 §3 閘門與 §13.6 硬門檻的依據 —— 改的是「顯示什麼」,
    不是「算什麼」。把它從 event 拿掉會讓硬門檻無從量測。
    """
    funds = [{"code": "M14", "name": "月配 14 號", "house": "",
              "dividends": _err_divs(_clean_monthly(14, 12, start=(2025, 8)))}]
    cal = build_month_calendar(funds, 2026, 8, ref_year=2026, ref_month=7, ref_day=20)
    assert cal["counts"]["events"] == 1
    ev = cal["events"][0]
    assert ev["error_band"] == 0
    assert ev["confidence"] in ("low", "medium", "high")      # 保留不動


def test_unpredictable_entries_carry_house_and_last_ex():
    """§15.3:推不出的基金要**留得住** —— house(圖例顏色)+ last_ex(上次實際基準日)。

    ⚠️ `last_ex` 是「上一次的**實際**基準日」這個**事實**,不是本月預估。
    把它當本月預估擺進日期格子,月底型一猜就錯一整輪 —— 那正是本次要修的病。
    """
    funds = [{"code": "IRR9", "name": "施羅德不規則", "house": "施羅德",
              "dividends": _err_divs([_dt.date(2025, 1, 10), _dt.date(2025, 2, 20),
                                      _dt.date(2025, 6, 5)])}]
    cal = build_month_calendar(funds, 2026, 8)
    u = cal["unpredictable"][0]
    assert u["house"] == "施羅德"
    assert u["last_ex"] == _dt.date(2025, 6, 5)
    assert u["reason_code"] in ("anchor_weak", "too_few", "stale", "no_anchor_day")


def test_reason_texts_are_plain_chinese_with_numbers():
    """§15.3:四類 reason 文案改人話**且帶具體數字**,不再是術語。

    舊版四句(「錨定日」「營業日校正」「容忍範圍」「歷史復現率」)讀完仍分不出
    「停配」與「這個月剛好卡連假」—— 那兩件事對 user 的行動完全不同。
    """
    _t = _dc._reason_text
    assert _t(_dc.REASON_TOO_FEW, n=2) == "只有 2 筆配息紀錄，還看不出規律（至少要 3 筆）。"
    assert _t(_dc.REASON_STALE, last_ex=_dt.date(2025, 3, 14), stale_months=11) == (
        "上次配息是 2025/03，已經 11 個月沒動靜，可能停配或資料沒更新。")
    assert _t(_dc.REASON_NO_ANCHOR_DAY, nominal=_dt.date(2026, 2, 15)) == (
        "平常在 2/15 前後除息，但這個月碰上連假，順延後差太多，不亂猜。")
    assert _t(_dc.REASON_ANCHOR_WEAK, window=12, last_ex=_dt.date(2026, 7, 29)) == (
        "最近 12 次除息的日子跳來跳去，對不上固定規律，不硬推。上次是 7/29。")
    # §1:術語不可回流
    _all = " ".join([_t(_dc.REASON_TOO_FEW, n=2),
                     _t(_dc.REASON_STALE, last_ex=_dt.date(2025, 3, 1), stale_months=9),
                     _t(_dc.REASON_NO_ANCHOR_DAY, nominal=_dt.date(2026, 2, 15)),
                     _t(_dc.REASON_ANCHOR_WEAK, window=12, last_ex=_dt.date(2026, 7, 1))])
    for _jargon in ("錨定", "營業日校正", "容忍範圍", "復現率"):
        assert _jargon not in _all, f"reason 文案退回術語:{_jargon}"


def test_reason_text_omits_date_it_does_not_have():
    """§1:上次日期不明時**不可**掰一個 —— 整句改寫,不留半截「上次是 。」。"""
    assert _dc._reason_text(_dc.REASON_ANCHOR_WEAK, window=5, last_ex=None).endswith("不硬推。")
    assert "上次是" not in _dc._reason_text(_dc.REASON_ANCHOR_WEAK, window=5, last_ex=None)
    assert _dc._reason_text(_dc.REASON_NO_ANCHOR_DAY, nominal=None, last_ex=None) == (
        "這個月碰上連假，順延後跟平常差太多，不亂猜。")
