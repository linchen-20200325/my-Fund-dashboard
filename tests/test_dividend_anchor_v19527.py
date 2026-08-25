"""除息基準日錨定引擎(SPEC v19.527 §0~§12)—— **規格驅動**測試。

本檔由測試組獨立於實作撰寫:每條 assert 對應規格的一條條文,合成 fixture 一律
自己按規格算出「應該長什麼樣」,不從 `services/dividend_calendar.py` 反推。
最後一段是 user 提供的 5 檔真實 MoneyDJ 配息表 walk-forward 回歸(§11 驗收基準)。

⚠️ 兩個刻意保留的外部相依(既有基礎設施,不在本次規格範圍):
  - `is_business_day()` —— 合成歷史用它產生「營業日校正後」的日期,這樣不論假日表
    有沒有 TW 假日,fixture 與引擎看到的是同一個世界(否則測試會變成在測假日表)。
  - `has_holiday_calendar()` —— §8 provenance 對照用。

⚠️ 三個規格未明定、本檔採用的解讀(壞掉時請先看這裡,不要直接改 assert):
  1. §3/§4 的 `k` = 近 k 筆視窗筆數;本檔所有信心測試的歷史長度都 <= 14 筆,
     故 k == len(history)(既有慣例視窗為近 12 筆)。
  2. §4 的 `h` 由 `ref_year`/`ref_month` 決定,本檔一律顯式傳入,不吃「今天」。
  3. §7 門檻採「_stale > 門檻 → None」;需要兩解都成立的地方(日差測試)改用
     「兩檔只差 last_ex 的日 → 失效月份必不同」的相對斷言,不綁絕對邊界。
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
    infer_schedule,
    is_business_day,
    predict_ex_for_month,
    project_anchor,
)

_DAY = _dt.timedelta(days=1)
_ANCHOR_TYPES = {"MONTH_END", "NTH_WEEKDAY", "NTH_WEEKDAY_FROM_END", "FIXED_DAY"}
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
    a = detect_anchor(hist)
    assert a is not None and a["type"] == "NTH_WEEKDAY"
    assert tuple(a["params"]) == (2, 2)
    assert a["score"] >= 0.95
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


def test_tie_broken_anchor_cannot_reach_high_confidence():
    """§3:平手決選出來的錨,信心上限壓 medium(不管 s / k / h 多漂亮)。

    平手代表「有兩個同樣能解釋歷史、但未來會分岔的假說」,這種不確定性
    不該被 s=1.0 洗成 high —— §11 的驗收條件是「錯了就不准掛 high」。
    """
    sched = infer_schedule(_recs(_hist_fixed(2026, 7, 8, D=10)))
    base = predict_ex_for_month(sched, 2026, 8, ref_year=2026, ref_month=7)
    assert base is not None and base["confidence"] == "high", "前提:未平手時本例為 high"
    assert isinstance(sched.get("anchor"), dict), "§12:infer_schedule 須帶 anchor dict"
    sched["anchor"]["tie_broken"] = True
    got = predict_ex_for_month(sched, 2026, 8, ref_year=2026, ref_month=7)
    assert got is not None and got["confidence"] in ("medium", "low")


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
    """§4:k>=6 才可能 high;k 在 4~5 之間退 medium;k=3 只能 low。

    筆數是 s 的可信度本身 —— 3 筆全中的 s=1.0 與 12 筆全中的 s=1.0 不是同一回事。
    """
    hi = predict_ex_for_month(_clean_sched(n=6), 2026, 8, ref_year=2026, ref_month=7)
    mid = predict_ex_for_month(_clean_sched(n=5), 2026, 8, ref_year=2026, ref_month=7)
    lo = predict_ex_for_month(_clean_sched(n=3), 2026, 8, ref_year=2026, ref_month=7)
    assert hi is not None and hi["confidence"] == "high"
    assert mid is not None and mid["confidence"] == "medium"
    assert lo is not None and lo["confidence"] == "low"


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


def test_roll_direction_preceding_is_inferred_from_history():
    """§5:ρ₋ >= 0.8 → preceding(安聯型:15 號遇六日往前抓 13/14)。"""
    hist = _hist_fixed(2026, 7, 24, D=15, mode="preceding")
    dev, fwd = _dev_stats(hist, 15)
    assert dev >= 3 and fwd == 0, "fixture 失效:應全部往前校正"
    a = detect_anchor(hist)
    assert a is not None and a["roll_convention"] == "preceding"


def test_roll_direction_mixed_falls_back_to_modified_following_and_low_confidence():
    """§5:兩個方向都沒到 0.8 → modified following,且**信心壓 low**。

    方向認不出來,代表這檔基金的順延規則本身不穩;此時就算 s 很高也只是「日號猜對」,
    真正的除息日仍可能差好幾天 —— 這種不確定性必須顯示在信心上,不能藏起來。
    """
    hist, flip = [], 0
    for y, m in _months_ending(2026, 7, 24):
        nom = _dt.date(y, m, 15)
        if is_business_day(nom):
            hist.append(nom)
            continue
        hist.append(_roll(nom, "following" if flip % 2 == 0 else "preceding"))
        flip += 1
    for window in (24, 12, 8):
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


def test_keep_month_backward_shift_never_exceeds_tau():
    """§5:keep_month 回退距離上限 τ=3 日曆天;超過就是「該月沒有合理錨定日」。

    稽核 A4 實測最惡 -7 天且完全靜默:連假把整個月尾吃掉時,舊版會安靜地把除息日
    拉到一週前,畫面上看起來一樣理直氣壯。這條 property 掃 7 年份的每個月來鎖住上限。
    """
    for y in range(2024, 2031):
        for m in range(1, 13):
            nom = _dt.date(y, m, min(31, _md(y, m)))
            got = project_anchor(dict(_MODF_31), y, m)
            if got is None:
                continue
            assert is_business_day(got), f"{y}-{m} 投影落在非營業日 {got}"
            assert got.month == m and got.year == y, f"{y}-{m} keep_month 破功:{got}"
            assert (nom - got).days <= 3, f"{y}-{m} 回退 {(nom - got).days} 天 > τ=3"


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
    grid = [_fixed(y, m, 15) for y, m in _months_ending(2025, 11, 12, step=3)]  # 2/5/8/11
    special = _fixed(2025, 12, 20)                                              # off-cycle
    sched = infer_schedule(_recs(sorted(grid + [special])))
    on_grid = predict_ex_for_month(sched, 2026, 2, ref_year=2025, ref_month=12)
    rotated = predict_ex_for_month(sched, 2026, 3, ref_year=2025, ref_month=12)
    assert on_grid is not None, "2 月仍在原網格上,不該因一筆特別配息而消失"
    assert rotated is None, "3 月不在原網格上;有值代表網格被 last_ex(12 月)旋轉了"


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
    """§6:「出現次數 != 1 的月份」佔比過高 → irregular → None。

    現行 by_day 每檔每月只掛 1 筆(§9 明說本次不做雙配息資料結構),
    所以偵測到就必須誠實回 None,而不是silently 只顯示其中一筆。
    """
    dates = []
    for i, (y, m) in enumerate(_months_ending(2026, 7, 9)):
        dates.append(_fixed(y, m, 10))
        if i % 3 == 0:
            dates.append(_fixed(y, m, 25))
    dup = sum(1 for _, c in Counter((d.year, d.month) for d in dates).items() if c != 1)
    assert dup / 9 > 0.15, "fixture 失效:雙配息月份佔比不夠"
    sched = infer_schedule(_recs(sorted(dates)))
    assert predict_ex_for_month(sched, 2026, 8, ref_year=2026, ref_month=7) is None


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


def test_annual_fund_beyond_absolute_cap_returns_none():
    """§7:門檻加絕對上限 `min(3*step, 15)` 個月。稽核 A11:年配基金可靜默 36 個月仍給日期。

    年配 step=12,3 個週期 = 36 個月 —— 三年沒配息還照推,基本上就是把「已清算/已停配」
    的基金畫在月曆上。絕對上限 15 個月把這種情況擋在信心系統之外。
    """
    dates = [_fixed(y, 5, 20) for y in (2019, 2020, 2021, 2022, 2023)]
    sched = infer_schedule(_recs(dates))
    assert predict_ex_for_month(sched, 2026, 5, ref_year=2026, ref_month=5) is None


def test_fresh_history_is_not_flagged_stale():
    """§7 反向:剛配完就推下個月,不可被陳舊度誤殺(否則整個月曆會空掉)。"""
    sched = _clean_sched(n=12)
    assert predict_ex_for_month(sched, 2026, 8, ref_year=2026, ref_month=7) is not None


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
                wrong_high.append((code, tgt.isoformat(), got["ex_date"].isoformat()))
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


def test_real5_no_wrong_prediction_carries_high_confidence():
    """§11 核心(比命中率更重要):推錯且信心 = high 的筆數必須是 **0**。

    「可以不知道,不可以錯還說有把握」。稽核 A2 的實測是 85~91% 錯誤率全掛 high ——
    user 是照著 high 的日期在調度資金的,這種錯會直接變成真金白銀的決策錯誤。
    """
    _hit, _pred, _total, wrong_high, _pf = _walk_forward()
    assert wrong_high == [], (
        f"有 {len(wrong_high)} 筆推錯卻掛 high(前 5 筆 code/實際/推估):{wrong_high[:5]}")


def test_real5_coverage_not_gamed():
    """§11 反向護欄:不准靠「幾乎全部棄權」把命中率洗到 100%。

    §1 允許不給答案,但月曆的價值就是覆蓋;若引擎只敢推兩三筆,命中率再高也沒用。
    """
    _hit, predicted, total, _wh, per_fund = _walk_forward()
    assert predicted / total >= 0.5, (
        f"只對 {predicted}/{total} 筆敢給日期,覆蓋率過低;逐檔 "
        f"{ {k: f'{v[1]}/{v[2]}' for k, v in per_fund.items()} }")
