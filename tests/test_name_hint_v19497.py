"""v19.497:名稱三段 fallback(真名 → name_hint → 代號)。

user 2026-08-20 回報 ALZF9 顯示成代號:"AL" 系保單平台代碼線上抓不到真名(6 個
meta 源全命不中,前綴不在境內表也不在保單子網域提示),原本只有「真名 or 代號」,
於是把**代號當名字**顯示。本組守新加的 name_hint 中間層:呼叫端已知名(選股池 /
政策表)在真名抓不到時勝過代號,§1 不臆測(都沒有才退代號)。

覆蓋:
- process_one_fund:真名優先 / 真名空退 name_hint / 都空退代號 / 源把名字填成代號時視同無真名
- _build_fund_dict:同三段
- build_batch_unified_row:抓取失敗列也帶 name_hint(非 None / 非代號)
全程 TWD 短路(fx=1.0)+ fd 直餵,零網路。
"""
import datetime as _dt

import pandas as pd
import pytest

from services.fund_row import process_one_fund


def _today():
    return _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8))).date()


def _nav(periods=30, freq="B", start=10.0):
    idx = pd.date_range(end=_today(), periods=periods, freq=freq)
    return pd.Series([start + i * 0.01 for i in range(len(idx))], index=idx, dtype=float)


def _fd(code, *, fund_name):
    """process_one_fund 可直接消化的 TWD fd(fx=1.0、零網路);full_key=代號(fallback 源)。"""
    return {
        "series": _nav(),
        "dividends": [],
        "currency": "TWD",
        "fund_name": fund_name,
        "full_key": code,
        "inception_date": "2018-01-01",
        "metrics": {"div_freq_n": 12},
    }


# ── process_one_fund:名稱三段 ─────────────────────────────────────────────
def test_pof_real_name_beats_hint():
    r = process_one_fund("ALZF9", 1_000_000.0,
                         fd=_fd("ALZF9", fund_name="安聯收益成長基金"), name_hint="池自填名")
    assert r["ok"] and r["基金名"] == "安聯收益成長基金"      # 真名優先,忽略 hint


def test_pof_empty_name_uses_hint():
    r = process_one_fund("ALZF9", 1_000_000.0,
                         fd=_fd("ALZF9", fund_name=""), name_hint="安聯收益成長基金")
    assert r["ok"] and r["基金名"] == "安聯收益成長基金"      # 抓不到真名 → 用 hint,非代號


def test_pof_empty_name_no_hint_falls_back_to_code():
    r = process_one_fund("ALZF9", 1_000_000.0, fd=_fd("ALZF9", fund_name=""))
    assert r["ok"] and r["基金名"] == "ALZF9"                # 都沒有 → 退代號(§1 不臆測)


def test_pof_fetched_name_equal_code_treated_as_no_name():
    # 某源把 fund_name 填成代號本身 → 視同無真名,續退 name_hint(防「代號當名字」)
    r = process_one_fund("ALZF9", 1_000_000.0,
                         fd=_fd("ALZF9", fund_name="alzf9"), name_hint="安聯收益成長基金")
    assert r["ok"] and r["基金名"] == "安聯收益成長基金"


# ── _build_fund_dict:同三段 ──────────────────────────────────────────────
def test_build_fund_dict_name_hint():
    from ui.helpers.fund_grp_health._utils import _build_fund_dict
    fd_real = {"fund_name": "安聯收益成長基金"}
    fd_empty = {"fund_name": ""}
    assert _build_fund_dict(fd_real, "ALZF9", 0, name_hint="池名")["name"] == "安聯收益成長基金"
    assert _build_fund_dict(fd_empty, "ALZF9", 0, name_hint="池名")["name"] == "池名"
    assert _build_fund_dict(fd_empty, "ALZF9", 0)["name"] == "ALZF9"       # 無 hint → 代號


# ── build_batch_unified_row:失敗列也帶 hint ──────────────────────────────
def test_batch_failed_row_carries_hint(monkeypatch):
    # process_one_fund 在 build_batch_unified_row 內部 `from services.fund_row import`,
    # 故 patch 源頭模組屬性(函式呼叫時才 import,會取到 patch 後的物件)。
    import services.fund_row as _FR
    import ui.helpers.fund_grp_health.unified as U
    monkeypatch.setattr(_FR, "process_one_fund",
                        lambda code, principal_twd, **kw: {"code": code, "ok": False, "error": "NAV 抓不到"})
    row = U.build_batch_unified_row("ALZF9", name_hint="安聯收益成長基金")
    assert row["狀態"].startswith("❌")
    assert row["基金名"] == "安聯收益成長基金"          # 失敗也顯示已知名,不留白也不顯代號


def test_batch_failed_row_no_hint_is_blank(monkeypatch):
    import services.fund_row as _FR
    import ui.helpers.fund_grp_health.unified as U
    monkeypatch.setattr(_FR, "process_one_fund",
                        lambda code, principal_twd, **kw: {"code": code, "ok": False, "error": "x"})
    row = U.build_batch_unified_row("ALZF9")
    assert row["基金名"] is None                        # 無 hint → 留白(不把代號當名字)


def test_batch_exception_row_carries_hint(monkeypatch):
    import services.fund_row as _FR
    import ui.helpers.fund_grp_health.unified as U

    def _boom(code, principal_twd, **kw):
        raise RuntimeError("boom")
    monkeypatch.setattr(_FR, "process_one_fund", _boom)
    row = U.build_batch_unified_row("ALZF9", name_hint="安聯收益成長基金")
    assert row["基金名"] == "安聯收益成長基金"
