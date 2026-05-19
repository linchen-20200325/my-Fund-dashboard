"""test_tab5_data_guard.py — ui/tab5_data_guard.py smoke 測試（v18.125 B-C.3）

驗證 B-C.3 抽出後 Tab5 render 函式：
- module import 不報錯
- render_data_guard_tab 是 callable + 無位置 arg（與 B-C.1/B-C.2 同設計）
- 內部 _now_tw / _calc_data_health helper 各自獨立可呼叫
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
    """_calc_data_health(ind) 應 delegate 給 ui.helpers.session.calc_data_health。"""
    import fund_fetcher  # noqa: F401
    from ui import tab5_data_guard as t5
    ind = {"PMI": {"value": 50.0}}   # 1/16 = 6.25%
    pct, traffic = t5._calc_data_health(ind)
    assert pct == 6   # round(1/16*100) = 6
    assert traffic == "🔴"   # < 50%


def test_parse_indicator_date_reexport_works():
    """B-C.3 move：_parse_indicator_date 應從 ui.helpers.session 正確 re-import。"""
    import fund_fetcher  # noqa: F401
    from ui.tab5_data_guard import _parse_indicator_date
    idate, errs = _parse_indicator_date({"date": "2026-05-15"})
    assert idate is not None
    assert errs == []


def test_app_py_shim_for_parse_indicator_date_still_works():
    """app.py 仍提供 _parse_indicator_date shim（向後相容）— 純 source 驗證。

    不直接 import app（會觸發 Streamlit runtime + 全部 module body 副作用），
    只看 source code 內是否有 `_parse_indicator_date` re-export。
    """
    from pathlib import Path
    src = (Path(__file__).parent / "app.py").read_text(encoding="utf-8")
    # B-C.3 後應該有 re-export line
    assert "from ui.helpers.session import parse_indicator_date as _parse_indicator_date" in src
    # 也應該還能找到 _parse_indicator_date 這個名字（caller 可用）
    assert "_parse_indicator_date" in src
