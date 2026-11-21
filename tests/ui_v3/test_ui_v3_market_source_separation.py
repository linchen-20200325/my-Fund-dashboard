# -*- coding: utf-8 -*-
"""🌍 頁同快照資料來源分離負控：一條序列失敗／缺資料，其他（健康）序列仍各自保有值、source、as_of、fetched_at；失敗序列不帶資料日／取得時間／點。
判定函式 `_violations` 檢查：失敗序列的日期與點、健康序列的 source／as_of／fetched_at 與「不補 0」；不檢查失敗序列自身的 source 標籤。

只用測試端替身（`market_stubs`）與真的 L2 形狀；不接任何真資料。⚠️ 數值與日期是人造的。
"""
from __future__ import annotations

import copy
import dataclasses
import math

import pytest

import market_stubs as ms
from ui_v3.adapters import market_page as a
from ui_v3.viewmodels.common import STATUS_FAILED, STATUS_MISSING, STATUS_OK

TW_FETCHED = "2026-11-03T05:00:00+00:00"
US_FETCHED = "2026-11-03T07:00:00+00:00"
US_LAST = "2026-10-30"   # 與台股最後一筆（2026-11-02）刻意不同日


def _view(**kw):
    tdates = ms.long_tw_dates()
    udates = ms.weekdays("2021-06-01", US_LAST)
    tw = kw.pop("tw", None) or (ms.taiex(tdates, ms.wave(len(tdates), 15000, 3.0, 400), fetched_at=TW_FETCHED), None)
    us = kw.pop("us", None) or (ms.sp500(udates, ms.wave(len(udates), 4000, 1.5, 150), fetched_at=US_FETCHED), None)
    return ms.view(tw=tw, us=us, us_dates=udates, **kw)


def _build(**kw):
    return a.build_market_page(_view(**kw), ms.table(), period="1Y")


def _notes(model):
    return {n.key: n for n in model.primary_notes}


def _violations(model, failed_key, healthy_key, healthy_ref):
    """回傳違反分離的清單：失敗序列帶任何資料日／取得時間／點；或健康序列的值被改動。"""
    bad = []
    notes = _notes(model)
    f, h = notes[failed_key], notes[healthy_key]
    if f.as_of is not None or f.fetched_at is not None or f.elapsed_days is not None:
        bad.append("failed_series_has_dates")
    if (h.as_of, h.fetched_at, h.source) != healthy_ref:
        bad.append("healthy_series_metadata_changed")
    series = {s.label: s for s in model.primary_card.series}
    label = {"taiex": "台股", "sp500": "S&P 500"}
    if series[label[failed_key]].points:
        bad.append("failed_series_has_points")
    if any(p.value in (0, 0.0) for p in series[label[healthy_key]].points):
        bad.append("zero_filled")
    return bad


_TW_REF = ("2026-11-02", TW_FETCHED, "Yahoo Finance (^TWII)")
_US_REF = (US_LAST, US_FETCHED, "Yahoo Finance (^GSPC)")


def test_baseline_two_series_keep_their_own_dates_and_fetched_at():
    notes = _notes(_build())
    assert (notes["taiex"].as_of, notes["taiex"].fetched_at) == ("2026-11-02", TW_FETCHED)
    assert (notes["sp500"].as_of, notes["sp500"].fetched_at) == (US_LAST, US_FETCHED)


@pytest.mark.parametrize("state", ["error", "missing"])
def test_us_series_down_does_not_touch_taiex(state):
    model = _build(us=state)
    assert _violations(model, "sp500", "taiex", _TW_REF) == []
    n = _notes(model)["sp500"]
    assert n.status == (STATUS_FAILED if state == "error" else STATUS_MISSING)
    base = _build()   # 注意：跨模式比對 period_change 依賴兩次建構的基準日相同（同一組固定日期的合成資料）；改動日期參數時須一併檢視
    keep = {c.key: c.period_change for c in base.evidence_changes}["taiex"]
    now = {c.key: c.period_change for c in model.evidence_changes}
    assert math.isclose(now["taiex"], keep) and now["sp500"] is None   # 缺值不補 0、不變成 0.0


@pytest.mark.parametrize("state", ["error", "missing"])
def test_taiex_down_does_not_touch_sp500_and_its_older_date(state):
    model = _build(tw=state)
    assert _violations(model, "taiex", "sp500", _US_REF) == []
    assert _notes(model)["sp500"].as_of == US_LAST   # 不被台股較新的 2026-11-02 污染
    now = {c.key: c.period_change for c in model.evidence_changes}
    assert now["taiex"] is None and now["sp500"] is not None


def test_vix_failure_leaves_primary_series_and_rates_intact():
    model = _build(vx="error")
    notes = _notes(model)
    assert notes["taiex"].status == notes["sp500"].status == STATUS_OK
    assert (notes["taiex"].as_of, notes["sp500"].as_of) == ("2026-11-02", US_LAST)
    rates = [c for c in model.secondary if c.key.endswith("_pct")]
    assert rates and all(c.status == STATUS_OK and c.value is not None for c in rates)


def test_negative_control_contaminated_model_is_detected():
    """變異：把失敗序列塞回健康序列的資料日／取得時間；判定函式必須報得出來。"""
    model = _build(us="error")
    assert _violations(model, "sp500", "taiex", _TW_REF) == []
    healthy = _notes(model)["taiex"]
    polluted = tuple(dataclasses.replace(n, as_of=healthy.as_of, fetched_at=healthy.fetched_at, elapsed_days=healthy.elapsed_days)
                     if n.key == "sp500" else n for n in model.primary_notes)
    assert "failed_series_has_dates" in _violations(dataclasses.replace(model, primary_notes=polluted), "sp500", "taiex", _TW_REF)
    shifted = tuple(dataclasses.replace(n, as_of=US_LAST) if n.key == "taiex" else n for n in model.primary_notes)
    assert "healthy_series_metadata_changed" in _violations(dataclasses.replace(model, primary_notes=shifted), "sp500", "taiex", _TW_REF)
    # 以下兩個變異繞過 viewmodel 建構檢查（它本身會擋失敗序列帶點、畫線序列數不符），直接在深拷貝上改欄位
    def mutated(fn):
        m = copy.deepcopy(model)
        fn({s.label: s for s in m.primary_card.series})
        return m
    # 變異：失敗序列塞回健康序列的點 → failed_series_has_points
    m1 = mutated(lambda sr: object.__setattr__(sr["S&P 500"], "points", sr["台股"].points))
    assert "failed_series_has_points" in _violations(m1, "sp500", "taiex", _TW_REF)
    # 變異：健康序列的點被補成 0 → zero_filled
    m2 = mutated(lambda sr: object.__setattr__(sr["台股"], "points", tuple(dataclasses.replace(pt, value=0.0) for pt in sr["台股"].points)))
    assert "zero_filled" in _violations(m2, "sp500", "taiex", _TW_REF)
