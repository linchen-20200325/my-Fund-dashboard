# -*- coding: utf-8 -*-
"""BL-0536-H2：`services/v2_domain/market_summary.py`（🌍 首屏期間漲跌＋新鮮度事實）的契約守衛。

規則出處：客戶 `DEC-2026-11-03-04`（H2 期間漲跌與圖表同一基準與資料視窗）；`DEC-2026-11-03-01` Q4 A（首屏重要依據＝
兩序列期間漲跌，基準同圖、隨期間切換、不放日期）、Q5 B（首屏只一枚 `⬜ 門檻待裁示`；日期與經過天數只在圖卡）；
`docs/v2/81` 第 2.3 節 G3、第 3.1、4、4.1 節。

四組：
(a) 契約：期間漲跌 ＝ `normalize_pair` 該序列的 `period_change` ＝ `last_normalized - 100`（pair 與退回單序列被畫那條）；
    沒畫線（被排除／不足／缺／withheld）→ None ＋ 真正原因代碼，從不為 0；隨期間參數變動；首屏結構沒有日期；
(b) 新鮮度：狀態恆為 `threshold_pending`（與規則表鍵一致）；經過天數是事實、逐序列、對應自身最後觀測日；
(c) 與 ui_v2 `period_return` 的口徑差異（81 G3，by design）只作記錄，ui_v2 行為不動；
(d) property：固定種子隨機序列下，投影與 `normalize_pair` 逐欄一致。
分層守衛由 `tests/test_v2_domain_port.py` 套件級守衛涵蓋（已把本模組列入母體）。
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib
import random
import re
import sys
from datetime import date, timedelta, timezone

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:  # 本機以 `--noconftest` 跑
    sys.path.insert(0, str(_ROOT))

from services.v2_domain import freshness as fr  # noqa: E402
from services.v2_domain import market_summary as ms  # noqa: E402
from services.v2_domain import normalization as nz  # noqa: E402
from services.v2_domain import periods  # noqa: E402

TAIPEI = timezone(timedelta(hours=8))


def P(day, value):
    return {"obs_date": day, "value_num": value}


# 與 tests/test_v2_domain_normalization.py golden 同一組（手算：taiex 期間漲跌 +50、sp500 +25；3M；基準日 2026-01-14）。
TAIEX = [
    P("2026-01-09", 80.0), P("2026-01-12", 100.0), P("2026-01-13", None),
    P("2026-01-14", 200.0), P("2026-01-15", 250.0), P("2026-01-16", 150.0), P("2026-04-10", 300.0),
]
SP500 = [
    P("2026-01-12", 999.0), P("2026-01-13", 40.0), P("2026-01-14", 40.0),
    P("2026-01-15", None), P("2026-01-16", 30.0), P("2026-04-13", 50.0),
]
SHORT = [P("2026-02-02", 1.0), P("2026-04-10", 2.0)]                       # B2：真正歷史不足
STALE = [P("2025-08-01", 1.0), P("2025-10-01", 2.0), P("2025-12-01", 3.0)]  # C2：停更超過期間


def changes(summary):
    return {c.key: c for c in summary.period_changes}


def series_of(comparison):
    return {s.key: s for s in comparison.series}


def assert_tied_to_chart(comparison, summary):
    """首屏漲跌必須就是圖上那條線的末點歸一化值減 100（同一個 SeriesResult）。"""
    assert summary.period == comparison.period and summary.mode == comparison.mode
    assert [c.key for c in summary.period_changes] == [s.key for s in comparison.series]
    for c, s in zip(summary.period_changes, comparison.series):
        assert c.status == s.status
        if s.status == nz.STATUS_OK:
            assert c.period_change == s.period_change == s.last_normalized - nz.BASE_VALUE
            assert s.points[-1].value == s.last_normalized and s.points[-1].obs_date == s.last_obs_date
        else:
            assert c.period_change is None and s.period_change is None


# ═══════════════════════ (a) 契約 ═══════════════════════


def test_pair_期間漲跌等於圖上末點歸一化值減100_可比較():
    r = nz.normalize_pair({"taiex": TAIEX, "sp500": SP500}, "3M")
    s = ms.first_screen_summary(r)
    assert_tied_to_chart(r, s)
    assert (s.period, s.mode, s.comparable, s.freshness_state) == ("3M", nz.MODE_PAIR, True, ms.FRESHNESS_THRESHOLD_PENDING)
    assert {k: (c.status, c.period_change) for k, c in changes(s).items()} == {
        "taiex": (nz.STATUS_OK, 50.0), "sp500": (nz.STATUS_OK, 25.0)}


def test_B2退回單序列_被畫那條等於圖上那條_被排除那條None加原因_不可比較():
    r = nz.normalize_pair({"taiex": SHORT, "sp500": SP500}, "3M")
    s = ms.first_screen_summary(r)
    assert_tied_to_chart(r, s)
    assert (s.mode, s.comparable) == (nz.MODE_FALLBACK, False)
    c = changes(s)
    assert (c["taiex"].status, c["taiex"].period_change) == (nz.STATUS_INSUFFICIENT, None)
    # sp500 退回單序列：自身視窗首筆 01-13 ＝ 40 → 04-13 ＝ 50 → 125 − 100 ＝ 25
    assert (c["sp500"].status, c["sp500"].period_change) == (nz.STATUS_OK, 25.0)


def test_C2停更_停更那條None加真正原因_另一條等於圖上那條():
    r = nz.normalize_pair({"a": STALE, "b": SP500}, "3M")
    s = ms.first_screen_summary(r)
    assert_tied_to_chart(r, s)
    c = changes(s)
    assert (c["a"].status, c["a"].period_change) == (nz.STATUS_NO_COMMON_BASE, None)
    assert c["b"].period_change == 25.0 and s.comparable is False


def test_缺一條_single_缺的那條None加missing_不是0():
    r = nz.normalize_pair({"taiex": None, "sp500": SP500}, "3M")
    s = ms.first_screen_summary(r)
    assert_tied_to_chart(r, s)
    assert (s.mode, s.comparable) == (nz.MODE_SINGLE, False)
    assert (changes(s)["taiex"].status, changes(s)["taiex"].period_change) == (nz.SERIES_MISSING, None)


@pytest.mark.parametrize("series, expected", [
    # 兩條都缺
    ({"a": None, "b": None}, {"a": nz.SERIES_MISSING, "b": nz.SERIES_MISSING}),
    # 兩條都不足
    ({"a": [P("2026-04-01", 1.0), P("2026-04-10", 2.0)], "b": [P("2026-04-02", 1.0), P("2026-04-10", 2.0)]},
     {"a": nz.STATUS_INSUFFICIENT, "b": nz.STATUS_INSUFFICIENT}),
    # 兩條都停更（日期錯開）→ withheld
    ({"a": [P("2026-01-01", 1.0), P("2026-04-10", 2.0)], "b": [P("2026-01-01", 1.0), P("2026-04-09", 2.0)]},
     {"a": nz.SERIES_WITHHELD, "b": nz.SERIES_WITHHELD}),
    # 單序列視窗內只有一個有效點
    ({"a": [P("2026-01-01", 1.0), P("2026-02-02", None), P("2026-04-10", 2.0)], "b": []},
     {"a": nz.STATUS_TOO_FEW_POINTS, "b": nz.SERIES_MISSING}),
])
def test_沒畫線一律None加原因代碼_從不為0(series, expected):
    r = nz.normalize_pair(series, "3M")
    s = ms.first_screen_summary(r)
    assert_tied_to_chart(r, s)
    assert {k: (c.status, c.period_change) for k, c in changes(s).items()} == {k: (v, None) for k, v in expected.items()}
    assert s.comparable is False


def _daily(start, days, f):
    return [P((start + timedelta(days=i)).isoformat(), f(i)) for i in range(days)]


def test_隨期間參數變動_每個期間都等於該期間圖上那條():
    start = date(2022, 1, 3)
    a = _daily(start, 1500, lambda i: 100.0 + i * 0.25)
    b = _daily(start, 1500, lambda i: 50.0 + (i % 97) * 0.5)
    seen = {}
    for period in periods.PERIODS:
        r = nz.normalize_pair({"a": a, "b": b}, period)
        s = ms.first_screen_summary(r)
        assert_tied_to_chart(r, s)
        assert s.period == period and s.comparable is True
        seen[period] = changes(s)["a"].period_change
    # 單調遞增序列：期間越長、基準越早、漲幅越大 → 四個期間的值彼此不同（跟著期間切換，不是固定值）
    assert seen["3M"] < seen["6M"] < seen["1Y"] < seen["3Y"]


_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")


def _flatten(value):
    if dataclasses.is_dataclass(value):
        for f in dataclasses.fields(value):
            yield from _flatten(getattr(value, f.name))
    elif isinstance(value, (tuple, list)):
        for v in value:
            yield from _flatten(v)
    else:
        yield value


def test_首屏摘要結構沒有任何日期欄位也沒有日期值():
    for cls in (ms.MarketFirstScreen, ms.PeriodChange):
        names = {f.name for f in dataclasses.fields(cls)}
        assert not any("date" in n or n in {"as_of", "window_start", "fetched_at"} for n in names), names
    for series in ({"taiex": TAIEX, "sp500": SP500}, {"taiex": SHORT, "sp500": SP500}, {"a": STALE, "b": SP500},
                   {"a": None, "b": None}):
        s = ms.first_screen_summary(nz.normalize_pair(series, "3M"))
        values = list(_flatten(s))
        assert not any(isinstance(v, (date,)) or (isinstance(v, str) and _ISO.search(v)) for v in values), values


def test_不是NormalizedComparison_大聲失敗():
    with pytest.raises(TypeError):
        ms.first_screen_summary({"status": "ok"})
    with pytest.raises(TypeError):
        ms.series_freshness(None, {})


def test_不變量破壞_大聲失敗():
    r = nz.normalize_pair({"taiex": TAIEX, "sp500": SP500}, "3M")
    bad = dataclasses.replace(r, series=(dataclasses.replace(r.series[0], period_change=None), r.series[1]))
    with pytest.raises(RuntimeError):
        ms.first_screen_summary(bad)


def test_回傳不可變():
    s = ms.first_screen_summary(nz.normalize_pair({"taiex": TAIEX, "sp500": SP500}, "3M"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.freshness_state = "fresh"
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.period_changes[0].period_change = 0.0


# ═══════════════════════ (b) 新鮮度 ═══════════════════════


def test_新鮮度狀態值等於規則表門檻待裁示的鍵_且與view_model詞彙對應一致():
    from shared.ui_semantics import rules
    from ui_v3.viewmodels import common
    assert ms.FRESHNESS_THRESHOLD_PENDING == "threshold_pending"
    assert rules.FRESHNESS_TO_KEY[common.FRESH_UNDETERMINED] == ms.FRESHNESS_THRESHOLD_PENDING
    assert rules.entry(ms.FRESHNESS_THRESHOLD_PENDING).wording == "⬜ 門檻待裁示"
    assert rules.entry_for_freshness(common.FRESH_UNDETERMINED) is rules.entry(ms.FRESHNESS_THRESHOLD_PENDING)


@pytest.mark.parametrize("series", [
    {"taiex": TAIEX, "sp500": SP500}, {"taiex": SHORT, "sp500": SP500}, {"a": STALE, "b": SP500},
    {"a": None, "b": SP500}, {"a": None, "b": None},
])
def test_門檻未裁示_首屏狀態恆為threshold_pending(series):
    for period in ("3M", "1Y"):
        assert ms.first_screen_summary(nz.normalize_pair(series, period)).freshness_state == "threshold_pending"


def test_經過天數是事實_逐序列_對應自身最後觀測日():
    r = nz.normalize_pair({"taiex": TAIEX, "sp500": SP500}, "3M")
    f = ms.series_freshness(r, {"taiex": "2026-04-14T09:00:00+00:00", "sp500": "2026-04-14T09:00:00+00:00"})
    assert [(x.key, x.last_obs_date, x.elapsed_days, x.state) for x in f] == [
        ("taiex", "2026-04-10", 4, ms.FRESHNESS_THRESHOLD_PENDING),
        ("sp500", "2026-04-13", 1, ms.FRESHNESS_THRESHOLD_PENDING),
    ]
    for x, s in zip(f, r.series):
        assert x.last_obs_date == s.last_obs_date
        assert x.elapsed_days == fr.delay_days(s.last_obs_date, "2026-04-14T09:00:00+00:00")


def test_經過天數_給時區時照delay_days換日():
    r = nz.normalize_pair({"taiex": TAIEX, "sp500": SP500}, "3M")
    # 2026-04-13T20:00Z ＝ 台北 04-14 04:00 → taiex 4 日、sp500 1 日；不給時區則取前 10 碼 → 3 日、0 日。
    stamp = "2026-04-13T20:00:00+00:00"
    with_tz = ms.series_freshness(r, {"taiex": stamp, "sp500": stamp}, tz=TAIPEI)
    no_tz = ms.series_freshness(r, {"taiex": stamp, "sp500": stamp})
    assert [x.elapsed_days for x in with_tz] == [4, 1]
    assert [x.elapsed_days for x in no_tz] == [3, 0]
    with pytest.raises(fr.NaiveTimestampError):
        ms.series_freshness(r, {"taiex": "2026-04-14T09:00:00", "sp500": None}, tz=TAIPEI)


def test_經過天數_缺序列或未取得為None_不補0():
    r = nz.normalize_pair({"taiex": None, "sp500": SP500}, "3M")
    f = ms.series_freshness(r, {"taiex": "2026-04-14T00:00:00Z", "sp500": None})
    assert [(x.key, x.last_obs_date, x.elapsed_days) for x in f] == [("taiex", None, None), ("sp500", "2026-04-13", None)]
    # 沒畫線但序列在（不足／停更）仍有自身最後觀測日與經過天數 —— 事實與是否可比較無關
    r2 = nz.normalize_pair({"a": STALE, "b": SP500}, "3M")
    f2 = ms.series_freshness(r2, {"a": "2026-04-14T00:00:00Z", "b": "2026-04-14T00:00:00Z"})
    assert [(x.last_obs_date, x.elapsed_days) for x in f2] == [("2025-12-01", 134), ("2026-04-13", 1)]


@pytest.mark.parametrize("stamp, expected", [
    ("2026-04-13T00:00:00Z", 0), ("2026-04-14T00:00:00Z", 1), ("2029-01-07T00:00:00Z", 1000),
    ("2026-04-12T00:00:00Z", -1),   # 資料不一致（觀測日晚於取得日）照實回報，不改 0、不改 None
])
def test_任何經過天數_狀態都不判新舊(stamp, expected):
    r = nz.normalize_pair({"a": None, "b": SP500}, "3M")
    b = ms.series_freshness(r, {"a": None, "b": stamp})[1]
    assert (b.elapsed_days, b.state) == (expected, ms.FRESHNESS_THRESHOLD_PENDING)


@pytest.mark.parametrize("fetched", [
    None, [], {"taiex": None}, {"taiex": None, "sp500": None, "x": None}, {"taiex": 1, "sp500": None},
])
def test_fetched_at格式錯誤_大聲失敗(fetched):
    r = nz.normalize_pair({"taiex": TAIEX, "sp500": SP500}, "3M")
    with pytest.raises(ValueError):
        ms.series_freshness(r, fetched)


def test_模組不產生fresh或stale等新鮮度判定代碼():
    tree = ast.parse((_ROOT / "services" / "v2_domain" / "market_summary.py").read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docstrings.add(id(first.value))
    consts = {n.value for n in ast.walk(tree)
              if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings}
    assert not {c for c in consts if c.lower() in {"fresh", "stale", "ok_fresh", "expired", "outdated", "normal"}}


# ═══════════════════════ (c) 與 ui_v2 period_return 的口徑差異（81 G3；by design，ui_v2 不動） ═══════════════════════


def test_記錄_ui_v2_period_return以各序列自己視窗首筆為起點_與H2不同():
    from ui_v2.mkt import market_section
    cut = periods.slice_period(TAIEX, "3M")
    old = market_section.period_return(cut["points"])
    # ui_v2：taiex 自身視窗（01-10 起）首筆有效 01-12 ＝ 100 → 04-10 ＝ 300 → +200%
    assert old["status"] == "ok" and old["pct"] == 200.0
    # H2：與圖同一基準日（共同基準日 01-14 ＝ 200）→ +50
    new = changes(ms.first_screen_summary(nz.normalize_pair({"taiex": TAIEX, "sp500": SP500}, "3M")))["taiex"]
    assert new.period_change == 50.0 != old["pct"]


# ═══════════════════════ (d) property ═══════════════════════


def test_property_投影與normalize_pair逐欄一致():
    rng = random.Random(20261103)
    start = date(2025, 1, 1)
    for _ in range(300):
        series = {}
        for key in ("a", "b"):
            if rng.random() < 0.1:
                series[key] = None
                continue
            first = rng.randint(0, 400)
            length = rng.randint(0, 200)
            pts = []
            for i in range(length):
                day = start + timedelta(days=first + i * rng.randint(1, 3))
                v = rng.choice([None, rng.uniform(1.0, 500.0), rng.uniform(1.0, 500.0), rng.uniform(1.0, 500.0)])
                pts.append(P(day.isoformat(), v))
            uniq = {p["obs_date"]: p for p in pts}
            series[key] = list(uniq.values())
        period = rng.choice(periods.PERIODS)
        r = nz.normalize_pair(series, period)
        s = ms.first_screen_summary(r)
        assert_tied_to_chart(r, s)
        assert s.freshness_state == ms.FRESHNESS_THRESHOLD_PENDING
        assert s.comparable == (r.mode == nz.MODE_PAIR and r.status == nz.STATUS_OK)
        f = ms.series_freshness(r, {"a": "2026-12-31T00:00:00Z", "b": None})
        assert f[1].elapsed_days is None
        assert f[0].elapsed_days == (None if r.series[0].last_obs_date is None
                                     else fr.delay_days(r.series[0].last_obs_date, "2026-12-31T00:00:00Z"))
