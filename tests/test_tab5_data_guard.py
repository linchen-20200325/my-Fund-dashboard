"""test_tab5_data_guard.py — ui/tab5_data_guard.py smoke 測試（v18.125 B-C.3）

驗證 B-C.3 抽出後 Tab5 render 函式：
- module import 不報錯
- render_data_guard_tab 是 callable + 無位置 arg（與 B-C.1/B-C.2 同設計）
- 內部 _now_tw helper 獨立可呼叫（v19.339:_calc_data_health wrapper 已刪 —
  tab5 production 0 呼叫,原 delegate 測試改直測 SSOT 純函式 calc_data_health）
- _D5_KEYS / parse_indicator_date 從 ui.helpers.session 正確 re-import
"""
from __future__ import annotations


def test_module_imports_ok():
    """ui/tab5_data_guard.py 可被 import；render_data_guard_tab callable + 無位置 arg。"""
    import fund_fetcher  # noqa: F401  解 circular
    from ui.tab5_data_guard import render_data_guard_tab
    import inspect
    assert callable(render_data_guard_tab)
    sig = inspect.signature(render_data_guard_tab)
    assert len(sig.parameters) == 0, "render_data_guard_tab 應為純無參數函式"


def test_now_tw_returns_taipei_datetime():
    """_now_tw 應回 Asia/Taipei tz-aware datetime。"""
    import fund_fetcher  # noqa: F401
    from ui import tab5_data_guard as t5
    import datetime
    now = t5._now_tw()
    assert isinstance(now, datetime.datetime)
    assert now.tzinfo is not None
    # tz offset 應為 +08:00（Asia/Taipei）
    assert now.utcoffset() == datetime.timedelta(hours=8)


def test_calc_data_health_with_explicit_indicators():
    """v19.339:tab5 死碼 wrapper 已刪 — 改直測 SSOT 純函式,數值斷言不變。"""
    import fund_fetcher  # noqa: F401
    from ui.helpers.session import calc_data_health
    ind = {"PMI": {"value": 50.0}}   # 1/16 = 6.25%
    pct, traffic = calc_data_health(ind)
    assert pct == 6   # round(1/16*100) = 6
    assert traffic == "🔴"   # < 50%


def test_parse_indicator_date_reexport_works():
    """B-C.3 move：_parse_indicator_date 應從 ui.helpers.session 正確 re-import。"""
    import fund_fetcher  # noqa: F401
    from ui.tab5_data_guard import _parse_indicator_date
    idate, errs = _parse_indicator_date({"date": "2026-05-15"})
    assert idate is not None
    assert errs == []
