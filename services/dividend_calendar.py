"""services/dividend_calendar.py — 基金除息基準日/配息行事曆推估(v19.530)。L2 純函式,零 IO。

用途:吃每檔基金的**配息歷史**,推估「本月**除息基準日** + 配息入帳日」,產生月曆結構供 L3 渲染。
資料由 L1 抓好傳入(reuse `repositories.fund` 的 dividends);本層不碰網路、不 import streamlit。

⚠️ **推估目標量 = 除息基準日**(v19.530 §0;§4.1 語意陷阱):MoneyDJ 配息表三欄語意不同 ——
`col[0] 配息基準日 → date`(**本層目標**,基金公司照名冊那天,節奏最穩)、`col[1] 除息日 → ex_date`
(基準日 +1~2 個營業日,多一層作業抖動)、`col[2] 發放日 → pay_date`。v19.529 以前錨在除息日,
5 檔真實 MoneyDJ 配息表 walk-forward 命中率僅 52%。

推估方法(誠實:是**推估**,非官方公告;輸出帶 confidence + provenance):
  1. 判頻率  : **近 12 筆**相鄰間隔中位數 → 月配(≈30)/季配(≈90)/半年(≈182)/年配(≈365)/不規則;
               gap 標準差 > 0.25×med_gap 或「同月多筆」佔比 > 0.15 → irregular(漂移/雙配息)。
  2. 找錨    : 四個假說擇一(MONTH_END / NTH_WEEKDAY / NTH_WEEKDAY_FROM_END / FIXED_DAY),
               以「**能重現自身歷史的比例** s」選模;s < 0.80 或筆數 < 3 → **不預測**(§1)。
  3. 校正方向: 落非營業日時往前或往後,方向**從歷史推**(ρ ≥ 0.8),推不出 → 保守回退且壓 low。
  4. 推入帳日: 基準日 + 歷史「基準→發放」間隔中位數(缺 pay_date → None,不硬編)。
  5. confidence: s + 擬合筆數 k + 預測地平線 h。**`day_std` 已從公式移除**(對星期錨定無資訊)。

§1 Fail-Loud:無配息紀錄(累積型/查無)→ cadence="none" → caller 落「已排除」,不偽造日期;
             錨定假說重現不了歷史 → 回 None 落 unpredictable,**寧可說不知道也不給看似合理的日期**;
             pay_date 缺 → 入帳日 None(標「約」窗或留白,不捏造)。
"""
from __future__ import annotations

import calendar as _calendar
import datetime as _dt
import math as _math
import statistics as _stats
from collections import Counter as _Counter
from typing import Any

# 頻率判定的間隔(天)容忍窗
_CADENCE_BANDS = [
    ("monthly", 20, 40),
    ("quarterly", 75, 105),
    ("semiannual", 160, 200),
    ("annual", 320, 400),
]
_RECENT_N = 12          # 推估視窗:錨定假說 / gap / 相位**同一視窗**只看近 12 筆(§6 稽核 A7)
# cadence → 一個週期幾個日曆月(逐月推進,不加固定 91 天以免月底漂移錯月)
_CADENCE_MONTHS = {"monthly": 1, "quarterly": 3, "semiannual": 6, "annual": 12}

# ── 錨定假說推估核心(v19.530 規格 §1~§8)——— 門檻全為 module 具名常數(§3.3 禁 inline)──
ANCHOR_MONTH_END = "MONTH_END"                        # 每月最後營業日(0 參數)
ANCHOR_FIXED_DAY = "FIXED_DAY"                        # 固定日號 D(1 參數)
ANCHOR_NTH_WEEKDAY = "NTH_WEEKDAY"                    # 每月第 j 個星期 w(2 參數)
ANCHOR_NTH_WEEKDAY_FROM_END = "NTH_WEEKDAY_FROM_END"  # 每月倒數第 j 個星期 w(2 參數)

ROLL_FOLLOWING = "following"                      # 非營業日 → 往後找
ROLL_PRECEDING = "preceding"                      # 非營業日 → 往前找
ROLL_MODIFIED_FOLLOWING = "modified_following"    # 往後,跨月則往前(方向未定時的保守回退)

# §3 平手時取「參數較少」者(少參數 = 少過擬合)
_ANCHOR_PARAM_COUNT = {ANCHOR_MONTH_END: 0, ANCHOR_FIXED_DAY: 1,
                       ANCHOR_NTH_WEEKDAY_FROM_END: 2, ANCHOR_NTH_WEEKDAY: 2}
# 分數 + 參數數皆相同時的決選序(deterministic,避免同分時輸出隨字典序漂移)。
# FROM_END 排在 NTH_WEEKDAY 前:兩者只在「該月有 5 個星期 w」時分歧,而基金作業慣例錨在月底側。
_ANCHOR_ORDER = [ANCHOR_MONTH_END, ANCHOR_FIXED_DAY,
                 ANCHOR_NTH_WEEKDAY_FROM_END, ANCHOR_NTH_WEEKDAY]

_ANCHOR_ACCEPT_MIN = 0.80        # §3 復現率 s⁽¹⁾ 未達 → 回 None(§1 不硬給)
_ANCHOR_TIE_DELTA = 0.10         # §3 前二名差距 < 此值 → 取參數少者,且信心上限壓 medium
_ANCHOR_MIN_RECORDS = 3          # §3 k < 3 → None
_ROLL_DIR_MIN_RATIO = 0.80       # §5 ρ₊ / ρ₋ 認定「單向校正」的門檻
_KEEP_MONTH_MAX_SHIFT_DAYS = 3   # §5 τ:跨月回退的距離上限(日曆日),超過 → 該月無合理錨定日
_CONF_HIGH_MIN_SCORE = 0.95      # §4 high 三條件
_CONF_HIGH_MIN_N = 6
_CONF_HIGH_MAX_HORIZON = 1
_CONF_MED_MIN_SCORE = 0.85       # §4 medium 三條件
_CONF_MED_MIN_N = 4
_CONF_MED_MAX_HORIZON = 3
_PHASE_MIN_RATIO = 0.80          # §6 相位眾數一致率下限
_GAP_DRIFT_MAX_RATIO = 0.25      # §6 近 k 筆 gap 標準差 / med_gap 上限(漂移偵測)
_DUP_MONTH_MAX_RATIO = 0.15      # §6 「同月出現次數 != 1」佔比上限(雙配息偵測)
_DAYS_PER_MONTH = 30.44          # §7 平均日曆月長(365.25 / 12)
_STALE_MAX_PERIODS = 3           # §7 距 ref 超過 3 個週期 → 疑停配
_STALE_ABS_MAX_MONTHS = 15       # §7 絕對上限(年配基金不得靜默 36 個月仍給日期)
_STALE_LOW_PERIODS = 2           # 距 ref >= 2 個週期 → 信心壓 low
# §7 的 ref_date:caller 只給 (ref_year, ref_month) 沒給「日」,取**月中**當該月的代表時點 ——
# 取月初/月底會系統性低估/高估陳舊度 15 天(半個月配週期);月中是無偏的中點估計。
_REF_DAY_OF_MONTH = 15

_HOLIDAY_CAL_TW = "TW"                   # §8 provenance:真有國定假日表
_HOLIDAY_CAL_WEEKEND = "weekend_only"    # §8 provenance:holidays 套件缺 → 只跳週末


def _pdate(v: Any) -> "_dt.date | None":
    """'YYYY-MM-DD' / 'YYYY/MM/DD' → date;壞值 → None(§1 不猜)。"""
    s = str(v or "").strip()[:10].replace("/", "-")
    try:
        y, m, d = (int(x) for x in s.split("-"))
        return _dt.date(y, m, d)
    except (ValueError, TypeError):
        return None


def _pfloat(v: Any) -> "float | None":
    try:
        f = float(v)
        return f if f == f else None      # NaN → None
    except (TypeError, ValueError):
        return None


def _parse_records(dividends: list) -> list:
    """配息紀錄 → [{ex, pay, amount, yield_pct}](升冪、同日去重 keep-last)。

    ⚠️ **`ex` 欄承載的是「除息基準日」**(v19.530 規格 §0 改;§4.1 單位/語意陷阱):
    MoneyDJ 配息表三個日期欄語意不同,推估目標量是**第一欄**——
      ``col[0] 配息基準日 → date``(本層取用;基金公司真正「照名冊」的那一天,節奏最穩)
      ``col[1] 除息日     → ex_date``(v19.529 以前取這欄;它是基準日 +1~2 個營業日,
                                      多一層作業日抖動,錨定假說復現率明顯較差)
      ``col[2] 發放日     → pay_date``
    故取值順序改為 **`date` 優先、退 `ex_date`**。FundClear(三欄同值)/ Cnyes(只有 `date`)
    來源行為不變;只有 MoneyDJ 來源的取值會改變 —— 而那正是本次要修的對象。
    欄名 `ex` 為既有結構相容保留(下游 key 未改),語意以本 docstring 為準。

    容錯:兩欄都解析不出 → 丟該筆(§1 不猜);pay_date 缺 → None。
    """
    out: list = []
    for r in dividends or []:
        if not isinstance(r, dict):
            continue
        ex = _pdate(r.get("date") or r.get("ex_date"))     # §0:基準日優先
        if ex is None:
            continue
        pay = _pdate(r.get("pay_date"))
        out.append({"ex": ex, "pay": pay,
                    "amount": _pfloat(r.get("amount")),
                    "yield_pct": _pfloat(r.get("yield_pct"))})
    dedup: dict = {}
    for r in out:                          # 同基準日 keep-last
        dedup[r["ex"]] = r
    return [dedup[k] for k in sorted(dedup)]


def _cadence_from_gap(med_gap: "float | None") -> str:
    if med_gap is None:
        return "single"
    for name, lo, hi in _CADENCE_BANDS:
        if lo <= med_gap <= hi:
            return name
    return "irregular"


# ── §1 四個錨定假說:投影(未校正的「名目錨定日」)────────────────────────────
def _month_days(year: int, month: int) -> int:
    return _calendar.monthrange(year, month)[1]


def _scan_business(d: "_dt.date", forward: bool) -> "_dt.date | None":
    """從 d 起(不含 d)往前/往後找第一個營業日;掃不到 → None(§1 不硬給)。"""
    _step = _dt.timedelta(days=1 if forward else -1)
    cur = d
    for _ in range(_HOLIDAY_MAX_SCAN):
        cur = cur + _step
        if is_business_day(cur):
            return cur
    return None


def _to_business(d: "_dt.date | None", forward: bool) -> "_dt.date | None":
    """d 已是營業日 → 原值;否則往指定方向找第一個營業日。"""
    if d is None:
        return None
    return d if is_business_day(d) else _scan_business(d, forward)


def _last_business_day_of_month(year: int, month: int) -> "_dt.date | None":
    """L(y,m):該月最後營業日(月底往前找)。"""
    return _to_business(_dt.date(year, month, _month_days(year, month)), forward=False)


def _nth_weekday_of_month(year: int, month: int, w: int, j: int) -> "_dt.date | None":
    """該月第 j 個星期 w(w:0=一…6=日);該月不足 j 個 → None(§1 不外推到別的月)。"""
    _first_wd = _dt.date(year, month, 1).weekday()
    _day = 1 + (w - _first_wd) % 7 + 7 * (j - 1)
    return _dt.date(year, month, _day) if 1 <= _day <= _month_days(year, month) else None


def _nth_weekday_from_end_of_month(year: int, month: int, w: int, j: int) -> "_dt.date | None":
    """該月倒數第 j 個星期 w;該月不足 j 個 → None。"""
    _md = _month_days(year, month)
    _last_wd = _dt.date(year, month, _md).weekday()
    _day = _md - (_last_wd - w) % 7 - 7 * (j - 1)
    return _dt.date(year, month, _day) if 1 <= _day <= _md else None


def _anchor_nominal(a_type: str, params: Any, year: int, month: int) -> "_dt.date | None":
    """假說 + 年月 → **名目**錨定日(§5 的 a_e,未套營業日校正 R)。無合理值 → None。

    MONTH_END 依定義即「最後營業日」,故其名目值本身已是營業日(R 對它是 identity)。
    """
    if a_type == ANCHOR_MONTH_END:
        return _last_business_day_of_month(year, month)
    if a_type == ANCHOR_FIXED_DAY:
        try:
            _d = int(params)
        except (TypeError, ValueError):
            return None
        if _d < 1:
            return None
        return _dt.date(year, month, min(_d, _month_days(year, month)))
    if a_type in (ANCHOR_NTH_WEEKDAY, ANCHOR_NTH_WEEKDAY_FROM_END):
        try:
            _w, _j = int(params[0]), int(params[1])
        except (TypeError, ValueError, IndexError):
            return None
        if not (0 <= _w <= 6) or _j < 1:
            return None
        if a_type == ANCHOR_NTH_WEEKDAY:
            return _nth_weekday_of_month(year, month, _w, _j)
        return _nth_weekday_from_end_of_month(year, month, _w, _j)
    return None


# ── §5 營業日校正 R(方向從歷史推,不硬編;跨月回退帶 τ 上限)────────────────
def _apply_roll(nominal: "_dt.date | None", convention: str,
                year: int, month: int) -> "_dt.date | None":
    """名目錨定日 → 校正後日期;會**跨出目標月**或回退距離 > τ → None(§1 不給錯月/被拉開的值)。

    - following / modified_following:先往後找營業日;preceding:先往前找。
    - 主方向跨出目標月 → 反向回退(= 現行 `keep_month` 行為),但回退距離 > τ=3 日曆日
      視為「該月無合理錨定日」→ None(稽核 A4:原本會靜默給一個被拉開 7 天的值)。
    """
    if nominal is None:
        return None
    _fwd = convention != ROLL_PRECEDING
    _d = _to_business(nominal, forward=_fwd)
    if _d is not None and (_d.year, _d.month) == (year, month):
        return _d
    _back = _to_business(nominal, forward=not _fwd)
    if _back is None or (_back.year, _back.month) != (year, month):
        return None
    if abs((_back - nominal).days) > _KEEP_MONTH_MAX_SHIFT_DAYS:
        return None
    return _back


def _infer_roll_convention(dates: list, a_type: str, params: Any) -> tuple:
    """§5:從歷史推校正方向 → (convention, inferred)。

    ρ₊ = |{e: e > a_e}| / |{e: e != a_e}|;ρ₊ ≥ 0.8 → following、ρ₋ ≥ 0.8 → preceding,
    其餘(含**完全沒有偏移樣本**,即歷史從未落在非營業日 → 方向無從觀測)→ modified following
    且 `inferred=False`,由呼叫端把信心壓 low(§5 明文:方向未定 → 不宣稱有把握)。
    """
    _up = _dn = 0
    for e in dates:
        _a = _anchor_nominal(a_type, params, e.year, e.month)
        if _a is None or _a == e:
            continue
        if e > _a:
            _up += 1
        else:
            _dn += 1
    _tot = _up + _dn
    if _tot == 0:
        return ROLL_MODIFIED_FOLLOWING, False
    if _up / _tot >= _ROLL_DIR_MIN_RATIO:
        return ROLL_FOLLOWING, True
    if _dn / _tot >= _ROLL_DIR_MIN_RATIO:
        return ROLL_PRECEDING, True
    return ROLL_MODIFIED_FOLLOWING, False


def _anchor_score(dates: list, a_type: str, params: Any, convention: str) -> float:
    """§2 復現率 s:該假說能重現自身歷史的比例。

    ⚠️ **先套 R 再比對**(不套的話月底型會被系統性低估:月底常遇六日)。
    """
    if not dates:
        return 0.0
    _hit = 0
    for e in dates:
        if _apply_roll(_anchor_nominal(a_type, params, e.year, e.month),
                       convention, e.year, e.month) == e:
            _hit += 1
    return _hit / len(dates)


def _fit_hypotheses(dates: list) -> list:
    """§1 參數估計 → [(type, params)] 四個候選。

    - `D* = floor(median(day) + 0.5)` **half-up**,不可用 `round()`
      (banker's rounding 對 x.5 取偶,月底型會被系統性推早一天)。
    - `w*` 取星期眾數;`j*` / `j̄*` 只在 `wd(e)=w*` 的子集上取眾數(從月初 / 從月底數)。
    - 眾數平手 → 取較小值(deterministic,避免輸出隨插入序漂移)。
    """
    _days = [d.day for d in dates]
    _fixed = _math.floor(_stats.median(_days) + 0.5) if _days else 1
    _wc = _Counter(d.weekday() for d in dates)
    _w = max(_wc.items(), key=lambda kv: (kv[1], -kv[0]))[0] if _wc else 0
    _same = [d for d in dates if d.weekday() == _w]
    _jc = _Counter(-(-d.day // 7) for d in _same)                                   # ceil(d/7)
    _j = max(_jc.items(), key=lambda kv: (kv[1], -kv[0]))[0] if _jc else 1
    _jbc = _Counter(-(-(_month_days(d.year, d.month) - d.day + 1) // 7) for d in _same)
    _jb = max(_jbc.items(), key=lambda kv: (kv[1], -kv[0]))[0] if _jbc else 1
    return [(ANCHOR_MONTH_END, None), (ANCHOR_FIXED_DAY, _fixed),
            (ANCHOR_NTH_WEEKDAY_FROM_END, (_w, _jb)), (ANCHOR_NTH_WEEKDAY, (_w, _j))]


def detect_anchor(dates: list) -> "dict | None":
    """歷史日期序列(除息基準日)→ 最佳錨定假說(規格 §1~§3、§12 API 契約)。

    不足 3 筆(§3 k < 3)或最佳復現率 s⁽¹⁾ < 0.80 → **None**(落 unpredictable,§1 不硬給)。

    Returns:
        {
          "type": str,             # MONTH_END | NTH_WEEKDAY | NTH_WEEKDAY_FROM_END | FIXED_DAY
          "params": tuple|int|None,# NTH_* → (w, j);FIXED_DAY → D;MONTH_END → None
          "score": float,          # s⁽¹⁾(排序後最高分)
          "runner_up": float,      # s⁽²⁾
          "roll_convention": str,  # following | preceding | modified_following
          "tie_broken": bool,      # 是否因 s⁽¹⁾-s⁽²⁾ < 0.10 而依「參數較少」決選
          "roll_inferred": bool,   # 校正方向是否真的從歷史推得(False → 呼叫端壓 low,§5)
          "n": int,                # 擬合用筆數 k(§4 信心公式的 k)
        }

    ⚠️ `score` 依 §12 契約回**排序後最高分 s⁽¹⁾**。當 `tie_broken=True` 時,實際採用的假說
    是參數較少的那個(其自身分數 = `runner_up`,最多低 0.10);此時信心上限已壓 medium,
    不會出現「用較低分假說卻宣稱 high」的情形。
    """
    _ds = sorted({d for d in (dates or []) if isinstance(d, _dt.date)
                  and not isinstance(d, _dt.datetime)})
    _k = len(_ds)
    if _k < _ANCHOR_MIN_RECORDS:
        return None

    _cands = []
    for _type, _params in _fit_hypotheses(_ds):
        _conv, _inferred = _infer_roll_convention(_ds, _type, _params)
        _cands.append({"type": _type, "params": _params,
                       "score": _anchor_score(_ds, _type, _params, _conv),
                       "roll_convention": _conv, "roll_inferred": _inferred})
    _cands.sort(key=lambda c: (-c["score"], _ANCHOR_PARAM_COUNT[c["type"]],
                               _ANCHOR_ORDER.index(c["type"])))
    _best, _second = _cands[0], _cands[1]
    _s1, _s2 = _best["score"], _second["score"]
    if _s1 < _ANCHOR_ACCEPT_MIN:
        return None                       # §3 閘門:重現不了自己的歷史 → 不預測(§1)
    _tie = (_s1 - _s2) < _ANCHOR_TIE_DELTA
    _pick = _best
    if _tie and _ANCHOR_PARAM_COUNT[_second["type"]] < _ANCHOR_PARAM_COUNT[_best["type"]]:
        _pick = _second                   # §3 平手 → 取參數較少者(少過擬合)
    return {"type": _pick["type"], "params": _pick["params"], "score": _s1, "runner_up": _s2,
            "roll_convention": _pick["roll_convention"], "tie_broken": bool(_tie),
            "roll_inferred": bool(_pick["roll_inferred"]), "n": _k}


def project_anchor(anchor: dict, year: int, month: int) -> "_dt.date | None":
    """錨 + 目標年月 → **校正後**的除息基準日推估值(§12 API 契約)。

    該月無合理錨定日(假說在該月不存在、或跨月回退超過 τ=3 日曆日)→ None(§1 不硬給)。
    回傳值保證落在 (year, month) 當月且為營業日。
    """
    if not isinstance(anchor, dict):
        return None
    try:
        _y, _m = int(year), int(month)
        if not 1 <= _m <= 12:
            return None
        _nominal = _anchor_nominal(anchor.get("type"), anchor.get("params"), _y, _m)
    except (TypeError, ValueError):
        return None
    return _apply_roll(_nominal, anchor.get("roll_convention") or ROLL_MODIFIED_FOLLOWING, _y, _m)


def _grade_confidence(score: "float | None", k: int, horizon: int, *,
                      tie_broken: bool = False, roll_inferred: bool = True) -> str:
    """§4 信心 = 復現率 s + 擬合筆數 k + 預測地平線 h。**day_std 已完全移除**。

    high   : s ≥ 0.95 且 k ≥ 6 且 h ≤ 1
    medium : s ≥ 0.85 且 k ≥ 4 且 h ≤ 3
    low    : 其餘;另外 tie_broken → 上限 medium(§3)、校正方向未定 → 壓 low(§5)
    """
    if score is None:
        return "low"
    if score >= _CONF_HIGH_MIN_SCORE and k >= _CONF_HIGH_MIN_N and horizon <= _CONF_HIGH_MAX_HORIZON:
        _c = "high"
    elif score >= _CONF_MED_MIN_SCORE and k >= _CONF_MED_MIN_N and horizon <= _CONF_MED_MAX_HORIZON:
        _c = "medium"
    else:
        _c = "low"
    if tie_broken and _c == "high":
        _c = "medium"
    if not roll_inferred:
        _c = "low"
    return _c


def _phase_mode(dates: list, step: int) -> tuple:
    """§6 相位眾數 φ* = argmax_φ |{e: m_e ≡ φ (mod step)}| → (φ*, 一致率)。

    一致率 < 0.8 → φ* 回 None(稽核 A8:一筆特別配息就會旋轉整個季度網格 → 寧可不預測)。
    step=1(月配)恆為 (0, 1.0)。`m % step` 對 step ∈ {1,3,6,12} 跨年一致(12 可被整除)。
    """
    if step <= 1:
        return 0, 1.0
    if not dates:
        return None, 0.0
    _c = _Counter(d.month % step for d in dates)
    _phase, _hits = max(_c.items(), key=lambda kv: (kv[1], -kv[0]))
    _ratio = _hits / len(dates)
    return (_phase if _ratio >= _PHASE_MIN_RATIO else None), _ratio


def infer_schedule(dividends: list) -> dict:
    """配息史 → 節奏推估 dict(推估目標量 = **除息基準日**,見 `_parse_records`)。

    Returns:
        {cadence, ex_day, pay_gap_days, n, confidence, day_std,
         last_ex, last_amount, last_yield, med_gap, anchor, phase}
        cadence ∈ {none, single, monthly, quarterly, semiannual, annual, irregular}
        confidence ∈ {none, low, medium, high}
        anchor  = `detect_anchor` 的 dict 或 None(None = 節奏無穩定錨 → 不預測,§1)
        phase   = 月份相位 φ*(季/半年/年配用;月配恆 0;一致率不足 → None)

    ⚠️ **`ex_day` / `day_std` 已退役**(v19.530 §4):兩者**不再參與信心計算**,僅為相容保留。
    `day_std` 對星期錨定在結構上無資訊(連續 7 個整數的母體標準差恆為 √((7²−1)/12)=2.00,
    永遠低於舊的 `<=4` 閘門 → 實測 85~91% 錯誤率全被標成 high);`ex_day` 是「幾號」的中位數,
    對月底型 / 星期型都是錯的模型。新信心公式改由 `anchor.score` + 筆數 + 地平線決定。

    ⚠️ `last_yield` / `last_amount` **不可當年化配息率/金額顯示**(v19.524 稽核):兩者都只是
    「最近一筆」的原始值 —— (a) `yield_pct` 在 FundClear/Cnyes 來源常被上游 `or 0` 強制成 0.0,
    顯示會變成看似真實的「0.0%」(§1 捏造);(b) MoneyDJ 來源雖為年化率,但只是該筆基準日當下的
    點值,配息調整/淨值變動後即失真;(c) `last_amount` 是**原幣每單位**金額,本結構未帶 currency,
    USD/TWD 混列無法辨識(§4.1 單位陷阱)。要顯示年化配息率請用全站正典
    `services.health.dividend._resolve_adr_with_fallback`(3 層 SSOT,全站其餘頁面皆用它)。
    月曆明細表已於 v19.524 移除這兩欄(user 指示),此處保留欄位僅為相容,**新 caller 勿直接渲染**。
    """
    recs = _parse_records(dividends)
    n = len(recs)
    if n == 0:
        return {"cadence": "none", "ex_day": None, "pay_gap_days": None, "n": 0,
                "confidence": "none", "day_std": None, "last_ex": None,
                "last_amount": None, "last_yield": None, "med_gap": None,
                "anchor": None, "phase": None}

    recent = recs[-_RECENT_N:]
    _rdates = [r["ex"] for r in recent]

    # §6 med_gap 改取**近 k 筆**的 gap(與錨定 / 相位同視窗;原本 gap 用全史、days 用近 12 筆,
    # 兩視窗不一致 → 改頻率時一邊每年吞 8 筆、一邊每年捏 8 筆,稽核 A7)。
    gaps = [(_rdates[i] - _rdates[i - 1]).days for i in range(1, len(_rdates))]
    med_gap = _stats.median(gaps) if gaps else None
    cadence = _cadence_from_gap(med_gap)

    # §6 漂移 / 雙配息偵測 → irregular(稽核 A10:固定 30 天間隔型 100% 錯誤且全掛 high)
    _gap_std = _stats.pstdev(gaps) if len(gaps) > 1 else 0.0
    _mc = _Counter((d.year, d.month) for d in _rdates)
    _dup_ratio = sum(1 for v in _mc.values() if v != 1) / len(_mc) if _mc else 0.0
    if cadence in _CADENCE_MONTHS:
        if med_gap and _gap_std > _GAP_DRIFT_MAX_RATIO * med_gap:
            cadence = "irregular"
        elif _dup_ratio > _DUP_MONTH_MAX_RATIO:
            cadence = "irregular"

    # 退役欄位(相容保留,不參與信心):ex_day「幾號」中位數 + 離散度
    days = [d.day for d in _rdates]
    day_std = _stats.pstdev(days) if len(days) > 1 else 0.0
    ex_day = recs[-1]["ex"].day if (days and day_std > 8) else (
        round(_stats.median(days)) if days else None)

    pay_gaps = [(r["pay"] - r["ex"]).days for r in recs
                if r["pay"] is not None and (r["pay"] - r["ex"]).days >= 0]
    pay_gap = round(_stats.median(pay_gaps)) if pay_gaps else None

    _step = _CADENCE_MONTHS.get(cadence)
    # 錨定假說吃**全史 H**(§2 復現率定義 s = |{e in H}|/|H|、§4 的 k = |H| 皆以「歷史」為母體);
    # med_gap / 相位吃**近 12 筆**(§6 明文:頻率與相位要跟得上改配息頻率,兩者同視窗)。
    # 兩個視窗**刻意不同**:錨(幾號/第幾個星期)多筆才穩,頻率/相位則要對「近期節奏」敏感。
    anchor = detect_anchor([r["ex"] for r in recs]) if _step else None
    phase = _phase_mode(_rdates, _step)[0] if _step else None

    # 信心:節奏層先以 h=0(目標=現在)評級;`predict_ex_for_month` 會用真實地平線重算並取更保守者
    if anchor is None:
        conf = "low"
    else:
        conf = _grade_confidence(anchor["score"], anchor["n"], 0,
                                 tie_broken=anchor["tie_broken"],
                                 roll_inferred=anchor["roll_inferred"])

    last = recs[-1]
    return {"cadence": cadence, "ex_day": ex_day, "pay_gap_days": pay_gap, "n": n,
            "confidence": conf, "day_std": day_std, "last_ex": last["ex"],
            "last_amount": last["amount"], "last_yield": last["yield_pct"],
            "med_gap": med_gap, "anchor": anchor, "phase": phase}


def predict_ex_for_month(schedule: dict, year: int, month: int,
                         ref_year: "int | None" = None,
                         ref_month: "int | None" = None) -> "dict | None":
    """節奏 dict + 目標年月 → 推估 dict 或 None(當月不配息 / 無法推估,§1 不硬給)。

    Returns(既有 key 全保留;v19.530 §8 增列 provenance):
        {ex_date          : date   —— 推估**除息基準日**(非除息日、非發放日,§4.1),恆為營業日且落在目標月
         pay_date_est     : date|None —— 基準日 + 歷史「基準→發放」間隔中位數;無歷史 → None
         confidence       : "high"|"medium"|"low"
         anchor_type      : str|None  —— 命中的錨定假說(§1 四選一)
         anchor_score     : float|None—— 該假說的歷史復現率 s⁽¹⁾(§2)
         roll_convention  : str       —— 營業日校正方向(§5,從歷史推)
         holiday_calendar : "TW"|"weekend_only" —— 是否真的扣了國定假日(稽核 A12:原本 ex 側
                            降級對 caller 完全不可見,假日表缺失時準確度掉 10.2pp 卻一字不改)
         horizon_months   : int       —— 預測地平線 h = (y_tgt-y_ref)*12 + (m_tgt-m_ref)}

    §7 陳舊度以**日差**量(舊版只看月份差,月初與月底算出同一個值):
      `_stale = floor((ref月中 - last_ex).days / (30.44 * step))` 個週期;
      超過 3 個週期 **或** 超過 `min(3*step, 15)` 個月 → None(年配基金不得靜默 36 個月);
      >= 2 個週期 → 信心壓 low。

    ⚠️ `ref_year/ref_month`(v19.518):陳舊度須相對「**現在**」量,不是相對目標月;未給 → 用目標年月。

    ⚠️ **相容路徑**:若 `schedule` **完全沒有 `anchor` 這個 key**(= 非 `infer_schedule` 產出的
    手搭 dict),退回舊的「ex_day 套目標月 + 逐週期推進」邏輯,避免打死既有外部 caller。
    `infer_schedule` 一定會帶 `anchor` key(值可能為 None → 明確表示「推不出」→ 回 None)。
    """
    cad = schedule.get("cadence")
    last_ex = schedule.get("last_ex")
    step = _CADENCE_MONTHS.get(cad)
    if step is None or last_ex is None:
        return None

    _ry = ref_year if ref_year is not None else year
    _rm = ref_month if ref_month is not None else month
    _h = (year - _ry) * 12 + (month - _rm)

    # §7 陳舊度:日差 → 週期數 + 絕對月數上限(用 last_ex 的「日」,月初與月底不再同分)
    _ref_date = _dt.date(_ry, _rm, _REF_DAY_OF_MONTH)
    _days_since = max(0, (_ref_date - last_ex).days)
    _months_since = _days_since / _DAYS_PER_MONTH
    _stale = int(_days_since // (_DAYS_PER_MONTH * step))
    if _stale > _STALE_MAX_PERIODS or _months_since > min(_STALE_MAX_PERIODS * step,
                                                          _STALE_ABS_MAX_MONTHS):
        return None                        # 疑停配 / 資料過舊 → 不硬給(§1)
    if (year, month) < (last_ex.year, last_ex.month):
        return None                        # 目標月早於最後一筆 → 不回填過去

    if "anchor" in schedule:
        anchor = schedule.get("anchor")
        if anchor is None:
            return None                    # §3 閘門沒過 → 誠實回 None
        _phase = schedule.get("phase")
        if step > 1 and (_phase is None or (month % step) != _phase):
            return None                    # §6 相位不合(季/年配空月)或相位不一致 → 不列
        ex = project_anchor(anchor, year, month)
        if ex is None:
            return None                    # 該月無合理錨定日(含 §5 τ 上限)
        _conf = _grade_confidence(anchor.get("score"), int(anchor.get("n") or 0), _h,
                                  tie_broken=bool(anchor.get("tie_broken")),
                                  roll_inferred=bool(anchor.get("roll_inferred", True)))
        _prov = {"anchor_type": anchor.get("type"), "anchor_score": anchor.get("score"),
                 "roll_convention": anchor.get("roll_convention") or ROLL_MODIFIED_FOLLOWING}
    else:
        # ── 相容路徑(手搭 schedule dict):舊「ex_day + 逐月推進」邏輯 ──────────
        ex_day = schedule.get("ex_day")
        if ex_day is None:
            return None
        cy, cm = last_ex.year, last_ex.month
        for _ in range(240):               # 上限保護(240 月 = 20 年)
            if (cy, cm) == (year, month):
                break
            if (cy, cm) > (year, month):
                return None                # 越過目標月(季/年配空月)
            cm += step
            while cm > 12:
                cm -= 12
                cy += 1
        else:
            return None
        ex = roll_to_business_day(_dt.date(year, month,
                                           min(int(ex_day), _month_days(year, month))))
        _conf = schedule.get("confidence", "low")
        _prov = {"anchor_type": None, "anchor_score": None,
                 "roll_convention": ROLL_MODIFIED_FOLLOWING}

    if _stale >= _STALE_LOW_PERIODS:
        _conf = "low"                      # 距現在 >= 2 個週期 → 不宣稱有把握
    gap = schedule.get("pay_gap_days")
    pay = ex + _dt.timedelta(days=gap) if isinstance(gap, int) else None
    return {"ex_date": ex, "pay_date_est": pay, "confidence": _conf,
            "holiday_calendar": _HOLIDAY_CAL_TW if has_holiday_calendar() else _HOLIDAY_CAL_WEEKEND,
            "horizon_months": _h, **_prov}


def build_month_calendar(funds: list, year: int, month: int,
                         ref_year: "int | None" = None,
                         ref_month: "int | None" = None) -> dict:
    """多檔基金(含 dividends)+ 目標年月 → 月曆結構。

    `ref_year/ref_month`:陳舊度參考月(現在);推未來月(下月推播)時傳「本月」,避免正常月配
    被誤判低信心(v19.518)。未給 → 用目標月(App 目標=現在,零變化)。見 predict_ex_for_month。

    Args:
        funds: [{"code", "name", "house"(選填), "dividends": [...]}]
    Returns:
        {year, month, events[], by_day{day:[events]}, excluded[], unpredictable[], counts{}}
        event = {code, name, house, ex_date, pay_date_est, confidence, last_amount, last_yield, n}
        excluded     = {code, name, reason}(無配息 = 累積型/查無)
        unpredictable= {code, name, reason}(有配息史但本月無法推估:節奏不規則 / 疑停配過舊)
                       —— 稽核 M3:誠實揭露而非靜默消失。季/年配的「空月」不列此(合理不配)。
    """
    events: list = []
    excluded: list = []
    unpredictable: list = []
    for f in funds:
        code = str((f or {}).get("code") or "").strip()
        name = str((f or {}).get("name") or code)
        house = str((f or {}).get("house") or "")
        sch = infer_schedule((f or {}).get("dividends"))
        if sch["cadence"] == "none":
            excluded.append({"code": code, "name": name,
                             "reason": "無配息紀錄（累積型 / 查無配息）"})
            continue
        pred = predict_ex_for_month(sch, year, month, ref_year=ref_year, ref_month=ref_month)
        if pred is None:
            if sch["cadence"] == "monthly":          # 月配卻推不出 = 無穩定錨 或 陳舊/疑停配
                # §1 誠實:兩種成因文案分開 —— 有錨但推不出 = 陳舊;連錨都找不到 = 節奏無規律。
                unpredictable.append({"code": code, "name": name,
                                      "reason": ("最近無配息紀錄（疑停配 / 資料過舊），本月無法推估"
                                                 if sch.get("anchor") else
                                                 "配息日期無穩定規律，或最近無配息（疑停配 / 資料過舊）"
                                                 "，本月無法推估")})
            elif sch["cadence"] in ("single", "irregular"):
                unpredictable.append({"code": code, "name": name,
                                      "reason": "配息節奏不規則 / 資料不足，本月無法推估"})
            # 季/年配的空月 → 合理不配,不列也不算異常
            continue
        events.append({"code": code, "name": name, "house": house,
                       "ex_date": pred["ex_date"], "pay_date_est": pred["pay_date_est"],
                       "confidence": pred["confidence"], "last_amount": sch["last_amount"],
                       "last_yield": sch["last_yield"], "n": sch["n"]})

    events.sort(key=lambda e: (e["ex_date"], e["code"]))
    by_day: dict = {}
    for e in events:
        by_day.setdefault(e["ex_date"].day, []).append(e)
    return {"year": year, "month": month, "events": events, "by_day": by_day,
            "excluded": excluded, "unpredictable": unpredictable,
            "counts": {"events": len(events), "excluded": len(excluded),
                       "unpredictable": len(unpredictable)}}


# ── 基金公司偵測(從基金名關鍵字;供月曆分色/分組)──────────────────
_HOUSE_MAP = [
    (("聯博", "alliancebernstein"), "聯博"),
    (("安聯", "allianz"), "安聯"),
    (("摩根", "jpmorgan", "jpm", "jf "), "摩根"),
    (("施羅德", "schroder"), "施羅德"),
    (("瀚亞", "eastspring"), "瀚亞"),
    (("富蘭克林", "franklin", "坦伯頓", "templeton"), "富蘭克林"),
    (("貝萊德", "blackrock"), "貝萊德"),
    (("高盛", "goldman"), "高盛"),
    (("pimco", "品浩"), "PIMCO"),
    (("野村", "nomura"), "野村"),
    (("景順", "invesco"), "景順"),
    (("富達", "fidelity"), "富達"),
    (("法巴", "bnp"), "法巴"),
    (("m&g", "安聯m&g"), "M&G"),
    (("復華", "fh"), "復華"),
    (("國泰", "cathay"), "國泰"),
    (("群益",), "群益"),
]


def detect_house(name: str) -> str:
    """從基金名關鍵字判斷所屬投信/投顧;判不出 → ''(caller 顯示代號即可,§1 不亂猜)。"""
    _n = str(name or "").lower()
    for keys, house in _HOUSE_MAP:
        if any(k in _n for k in keys):
            return house
    return ""


# ── LINE 月初摘要文字(方式 C;純字串,零 IO)──────────────────
_CONF_ZH = {"high": "", "medium": "", "low": "（信心低）"}

# 到帳推估:除息基準日 + N 個**營業日**區間(user 2026-08-24 實際經驗 5~7 天,故給區間不給單點)。
# module SSOT,不 inline magic(§3.3)。
_PAY_BIZ_DAYS_MIN = 5
_PAY_BIZ_DAYS_MAX = 7


# ── 台灣營業日:週末 + 國定假日(user 2026-08-24「節日或是六日都要順延至工作天」)──────────
# 假日資料走 `holidays` 套件的 TW 行事曆:**農曆假日(除夕/春節/端午/中秋)逐年算出、含補假**,
# 硬編表格做不到且會逐年過期。純計算、零網路。§4.5 原「無台灣假日表」限制自此解除。
_HOLIDAY_MAX_SCAN = 40          # 順延掃描上限(連假最長遠不及此;防呆避免無窮迴圈)


def _tw_holidays():
    """回傳 TW 假日查詢物件(`date in obj`);套件不可用 → None(退化為只跳週末)。快取單例。"""
    if not hasattr(_tw_holidays, "_cache"):
        try:
            import holidays as _h
            _tw_holidays._cache = _h.country_holidays("TW")
        except Exception as _e:  # noqa: BLE001 — 套件缺 → 誠實退化(見 _pay_note 文案會跟著改)
            print(f"[dividend_calendar] 無 holidays 套件({type(_e).__name__}),"
                  "營業日僅跳週末、未扣國定假日")
            _tw_holidays._cache = None
    return _tw_holidays._cache


def has_holiday_calendar() -> bool:
    """是否真的有國定假日表可用 —— 供文案誠實描述「有沒有扣國定假日」(§1 不宣稱做不到的事)。"""
    return _tw_holidays() is not None


def is_business_day(d: "_dt.date | None") -> bool:
    """是否為台灣營業日:非週末**且**非國定假日(假日表不可用時,只判週末)。"""
    if not isinstance(d, _dt.date):
        return False
    if d.weekday() >= 5:
        return False
    _h = _tw_holidays()
    return not (_h is not None and d in _h)


def roll_to_business_day(d: "_dt.date | None", *, keep_month: bool = True) -> "_dt.date | None":
    """推估日期(除息基準日)落在**週末或國定假日** → 順延到下一個營業日(user 2026-08-24)。

    基金不會在非營業日訂基準日;推估用「幾號」套到目標月時很容易落在六/日或連假,故一律校正。

    `keep_month=True`:若順延會**跨出原月份**(如 8/31 週日 → 9/1),改往前抓上一個營業日。
    月曆以「當月」為單位,跨月會讓事件掉到別的月份格子裡。

    ⚠️ 仍是**推估**:國定假日表為套件計算值,個別基金公司實際作業日可能再有出入。
    非日期 → 原樣回傳(§1 不捏造)。純函式,零 IO / 零網路。
    """
    if not isinstance(d, _dt.date) or is_business_day(d):
        return d
    _fwd = d
    for _ in range(_HOLIDAY_MAX_SCAN):
        _fwd += _dt.timedelta(days=1)
        if is_business_day(_fwd):
            break
    else:
        return d                                   # 掃不到(異常)→ 不硬給,回原值(§1)
    if keep_month and _fwd.month != d.month:
        _back = d
        for _ in range(_HOLIDAY_MAX_SCAN):
            _back -= _dt.timedelta(days=1)
            if is_business_day(_back):
                return _back
        return d
    return _fwd


def add_business_days(d: "_dt.date | None", n: int) -> "_dt.date | None":
    """回傳 d 之後第 n 個**營業日**(跳週末 **+ 國定假日**;user 2026-08-24)。

    假日表不可用時退化為只跳週末(見 `has_holiday_calendar`,文案會跟著誠實改寫)。
    n<=0 或 d 非日期 → 原樣回傳(不調整)。純函式,零 IO。"""
    if d is None or not isinstance(n, int) or n <= 0:
        return d
    cur, added = d, 0
    while added < n:
        cur = cur + _dt.timedelta(days=1)
        if is_business_day(cur):
            added += 1
    return cur


def display_label(ev: dict) -> str:
    """事件 → 顯示名稱:**只顯示投信名**(user 2026-08-24「我只要投信名」,代號不顯示)。

    圖檔月曆 / 明細表 / LINE 文字 / Flex 四個介面**共用同一規則**(SSOT,避免各處寫法漂移)。
    §1:判不出投信 → 退代號 → 退基金名 → 全空才「—」;**絕不回空字串**,否則該筆基準日在畫面上
    等於消失(Flex 空字串 text 更會讓整則推播 400)。
    """
    return (str(ev.get("house") or "").strip()
            or str(ev.get("code") or "").strip()
            or str(ev.get("name") or "").strip()
            or "—")


_CONF_RANK = {"low": 0, "medium": 1, "high": 2}


def dedupe_events(events: list) -> list:
    """同一天 + 同投信的多檔 → 只留一筆(user 2026-08-24「這邊重複也移除」)。

    格子、明細表、LINE 文字、Flex 四處共用同一去重規則(SSOT)。保序(依原順序)。
    key = (除息基準日, 顯示名)。

    ⚠️ **這是顯示層去重,會少掉「當天該投信有幾檔」的資訊** —— user 明確要求乾淨版面
    (先移除 ×N,再要求明細表也去重)。完整逐檔資料未被更動,仍在 `cal["events"]` /
    App 內頁查得到;本函式只影響呈現。
    §1:合併後信心取**最保守**(任一檔 low → 整組 low),不把低信心洗成高信心。
    """
    out: list = []
    idx: dict = {}
    for ev in events:
        _key = (ev.get("ex_date"), display_label(ev))
        _hit = idx.get(_key)
        if _hit is None:
            idx[_key] = len(out)
            out.append(dict(ev))
        else:
            _cur = out[_hit]
            if (_CONF_RANK.get(ev.get("confidence"), 1)
                    < _CONF_RANK.get(_cur.get("confidence"), 1)):
                _cur["confidence"] = ev.get("confidence")     # 取較保守者
    return out


def pay_window(ex: "_dt.date | None") -> "tuple | None":
    """除息基準日 → (最早, 最晚) 入帳推估日 = 基準日 + 5~7 個**營業日**(user 2026-08-24 經驗值)。

    §1:ex 非日期 → None(caller 顯示「—」,不捏造日期)。僅跳週末、**未扣國定假日**,
    遇連假實際到帳會更晚 —— caller 須標「推估」。純函式,零 IO。
    """
    if not isinstance(ex, _dt.date):
        return None
    return (add_business_days(ex, _PAY_BIZ_DAYS_MIN),
            add_business_days(ex, _PAY_BIZ_DAYS_MAX))


def _pay_note() -> str:
    """到帳說明單行(text / Flex 共用,口徑 SSOT 一處改兩處同步)。

    §1:括號內文案**依實際能力誠實改寫** —— 有假日表就說已扣國定假日,沒有就說沒扣,
    不宣稱做不到的事。
    """
    _scope = "已跳過週末與國定假日" if has_holiday_calendar() else "僅跳週末、未扣國定假日"
    return (f"💰 到帳約 +{_PAY_BIZ_DAYS_MIN}~{_PAY_BIZ_DAYS_MAX} 個營業日左右"
            f"（{_scope};實際仍以基金公司作業為準）")


def build_summary_text(cal: dict) -> str:
    """月曆結構 → LINE 月初提醒文字。無事件 → 誠實說本月無推估除息基準日(§1)。

    user 2026-08-24:到帳時間**不逐檔列**,改在清單「上方」寫一句「到帳約 +5~7 個營業日左右」;
    逐檔只列**除息基準日** + 名稱。口徑與月曆圖檔「入帳(估)」欄**同源**(皆走 `pay_window`),
    不再各講各的(原本圖檔用歷史發放間隔 ≈1 個月、文字用 +5 工作天,已於 v19.524 統一)。
    """
    y, m = cal.get("year"), cal.get("month")
    _roc = (y - 1911) if isinstance(y, int) else "?"
    lines = [f"🗓️ 基金除息行事曆 · 民國{_roc}年{m}月（推估）"]
    events = cal.get("events") or []
    if not events:
        lines.append("你的基金本月無推估除息基準日（或資料不足）。")
    else:
        lines.append(_pay_note())
        for e in dedupe_events(events):                # 同日同投信只列一次(user 2026-08-24)
            _ex = e["ex_date"]
            _tag = _CONF_ZH.get(e.get("confidence"), "")
            lines.append(f"• {_ex.month}/{_ex.day} 除息基準日　{display_label(e)}{_tag}")
    # user 2026-08-24「沒有配息的整段移除」→ 不再提累積型/無配息檔數(那些本來就不會配,不需提醒)。
    # `unpredictable`(有配息史但本月推不出)**保留** —— 那是「可能有配息但我算不出來」,
    # 靜默吃掉會讓你以為當月沒事(§1 誠實揭露)。
    _unp = cal.get("unpredictable") or []
    if _unp:
        lines.append(f"（{len(_unp)} 檔節奏不規則/疑停配,無法推估）")
    lines.append("※ 推估非官方,實際以基金公司公告為準。")
    return "\n".join(lines)


# ── LINE Flex 彩色卡片(user 2026-08-24;LINE 原生渲染,不需產圖/託管)──────────────
# 顏色:LINE Flex 預設白底泡泡 → 採深字 + 綠 accent(雙主題可讀,不設 backgroundColor 避免主題陷阱)。
_FLEX_INK = "#1F2D3D"     # 主字(深板岩)
_FLEX_SUB = "#8896A6"     # 次要(灰)
_FLEX_EX = "#2E7D5B"      # 除息基準日(松綠)
_FLEX_MAX_ROWS = 30       # 稽核:Flex JSON ≤50KB;逐檔一列上限,其餘收斂「…另 N 檔」(對齊 text 路徑)


def _flex_event_row(e: dict) -> dict:
    """單檔一列(horizontal box):除息基準日 ｜ 投信名。

    user 2026-08-24:到帳時間不逐檔列(改由清單上方一句統一標)、名稱只留投信名(代號不顯示),
    故本列只有除息基準日 + 投信名。
    §1/稽核:LINE 拒絕**空字串 text**(整則 Flex 400 → 全推播失敗),`display_label` 保證非空。
    """
    _ex = e["ex_date"]
    _name = display_label(e)[:22]                     # 只顯示投信名(SSOT,與圖檔/文字一致)
    if e.get("confidence") == "low":
        _name += "（信心低）"
    _contents = [
        {"type": "text", "text": f"{_ex.month}/{_ex.day} 除息基準日", "size": "sm",
         "weight": "bold", "color": _FLEX_EX, "flex": 5, "wrap": True},
        {"type": "text", "text": _name, "size": "sm", "color": _FLEX_INK, "flex": 5, "wrap": True},
    ]
    return {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": _contents}


def build_summary_flex(cal: dict) -> dict:
    """月曆結構 → LINE Flex 彩色卡片。**純函式,零 IO**。回 {"contents": bubble, "alt_text": str}。

    無事件 → 誠實卡片說本月無推估除息基準日(§1)。內容與 build_summary_text 一致(每檔基準日 + 到帳說明)。
    """
    y, m = cal.get("year"), cal.get("month")
    _roc = (y - 1911) if isinstance(y, int) else "?"
    events = dedupe_events(cal.get("events") or [])    # 同日同投信只列一次(user 2026-08-24)
    _unp = cal.get("unpredictable") or []

    _body: list = []
    if not events:
        _body.append({"type": "text", "text": "你的基金本月無推估除息基準日（或資料不足）。",
                      "size": "sm", "color": _FLEX_SUB, "wrap": True})
    else:
        # user 2026-08-24:到帳時間改在清單「上方」寫一句(不逐檔列),與純文字/圖檔同口徑。
        _body.append({"type": "text", "text": _pay_note(),
                      "size": "xxs", "color": _FLEX_SUB, "wrap": True})
        _body.append({"type": "separator", "margin": "sm"})
        _body.extend(_flex_event_row(e) for e in events[:_FLEX_MAX_ROWS])
        if len(events) > _FLEX_MAX_ROWS:              # 稽核:超上限收斂,避免 Flex JSON 超 50KB → 400
            _body.append({"type": "text",
                          "text": f"…另 {len(events) - _FLEX_MAX_ROWS} 檔（開 App 看完整）",
                          "size": "xs", "color": _FLEX_SUB, "wrap": True})
    # 「累積型/無配息」整段移除(user 2026-08-24);`unpredictable` 保留 —— 見 build_summary_text 註解
    if _unp:
        _body.append({"type": "text", "text": f"（{len(_unp)} 檔節奏不規則/疑停配）",
                      "size": "xxs", "color": _FLEX_SUB, "wrap": True})
    _body.append({"type": "text", "text": "※ 推估非官方,實際以基金公司公告為準。",
                  "size": "xxs", "color": _FLEX_SUB, "wrap": True, "margin": "sm"})

    _bubble = {
        "type": "bubble", "size": "mega",
        "header": {"type": "box", "layout": "vertical", "spacing": "xs", "contents": [
            {"type": "text", "text": "🗓️ 基金除息行事曆", "weight": "bold", "size": "lg",
             "color": _FLEX_INK, "wrap": True},
            {"type": "text", "text": f"民國{_roc}年{m}月・推估", "size": "sm", "color": _FLEX_SUB},
        ]},
        "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": _body},
    }
    _alt = (f"🗓️ 民國{_roc}年{m}月 除息行事曆"
            f"（{len(events)} 檔・到帳=基準日+{_PAY_BIZ_DAYS_MIN}~{_PAY_BIZ_DAYS_MAX}營業日）")
    return {"contents": _bubble, "alt_text": _alt}


__all__ = ["infer_schedule", "predict_ex_for_month", "build_month_calendar",
           "detect_anchor", "project_anchor",
           "detect_house", "build_summary_text", "build_summary_flex", "add_business_days"]
