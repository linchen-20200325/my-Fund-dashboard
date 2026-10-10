# -*- coding: utf-8 -*-
"""級別（核心／衛星）停止以基金名稱猜測、寫回只寫客戶設定（客戶 2026-10-10 裁示）。

守的是四條路徑：
1. 載入（`ui/helpers/portfolio/load.py`）不覆寫讀回的級別、不跨保單沿用級別；
2. 寫回 Sheet（`ui/helpers/cloud_io.py` v1／v2、`repositories/snapshot_repository.py`、
   T7「套用起始部位」、④ 批次加入）一律走 `shared.policy_tier.fund_tier_sheet_value`
   —— 客戶明示的值照原樣寫回、未設定寫空白；
3. 新增基金的入口（③「➕ 加入組合」、④ 批次加入、T7 新基金、v2 首次使用精靈）不寫猜測；
4. v2 讀回清掉殘留的 v1 `policy_tier`。

突變驗證寫在各條 docstring（實跑）。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

# 台灣基金名稱依法幾乎都帶的揭露字樣；舊的名稱關鍵字表含「配息」且先檢查 ⇒ 一律猜成核心。
_DISCLAIMER = "(基金之配息來源可能為本金)"
_TECH_FUND_WITH_DISCLAIMER = f"貝萊德世界科技基金A6穩定配息(美元){_DISCLAIMER}"


# ══════════════════════════════════════════════════════════════════
# shared.policy_tier
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("fund, expect", [
    ({"policy_tier": "core"}, "core"),
    ({"policy_tier": " Core "}, "core"),
    ({"policy_tier": "SATELLITE"}, "satellite"),
    ({"policy_tier": "", "is_core": True}, "core"),
    ({"policy_tier": "", "is_core": False}, "satellite"),
    ({"policy_tier": "", "is_core": None}, None),
    ({}, None),
    (None, None),
    ({"is_core": 0}, None),
    ({"is_core": 1}, None),
    ({"is_core": "yes"}, None),
    ({"policy_tier": "中性", "is_core": True}, "core"),
    ({"policy_tier": "satellite", "is_core": True}, "satellite"),
])
def test_resolve_tier_three_states(fund, expect):
    from shared.policy_tier import resolve_tier
    assert resolve_tier(fund) == expect


def test_numpy_bool_is_not_treated_as_a_setting():
    """`is_core` 只認 Python 的 True／False；`np.bool_(True)` 不是客戶設定的值（第二組 X2）。"""
    np = pytest.importorskip("numpy")
    from shared.policy_tier import resolve_tier
    assert resolve_tier({"is_core": np.bool_(True)}) is None


def test_unset_writes_back_blank_not_satellite():
    from shared.policy_tier import fund_tier_sheet_value
    assert fund_tier_sheet_value({}) == ""
    assert fund_tier_sheet_value({"is_core": None}) == ""
    assert fund_tier_sheet_value({"is_core": False}) == "satellite"
    assert fund_tier_sheet_value({"policy_tier": "core", "is_core": False}) == "core"


# ══════════════════════════════════════════════════════════════════
# 1. 載入路徑
# ══════════════════════════════════════════════════════════════════
class _Ph:
    def info(self, *a, **k): pass
    def success(self, *a, **k): pass
    def progress(self, *a, **k): pass


class _SS(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError as _e:  # pragma: no cover
            raise AttributeError(k) from _e

    def __setattr__(self, k, v):
        self[k] = v


class _FakeSt:
    def __init__(self, funds):
        self.session_state = _SS({"portfolio_funds": funds})

    def empty(self, *a, **k): return _Ph()
    def progress(self, *a, **k): return _Ph()
    def write(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def rerun(self, *a, **k): pass


def _run_load(monkeypatch, funds, fund_name):
    import services.fund_service as _fs
    import ui.helpers.data_registry as _dr
    import ui.helpers.portfolio.load as _load

    monkeypatch.setattr(_dr, "_update_data_registry", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(
        _fs, "fetch_fund_from_moneydj_url_enriched",
        lambda code: {"fund_name": fund_name, "currency": "USD", "series": None,
                      "dividends": [], "metrics": {}, "risk_metrics": {}},
        raising=False)
    _fake = _FakeSt(funds)
    monkeypatch.setattr(_load, "st", _fake)
    _load.batch_load_unloaded_funds()
    return _fake.session_state["portfolio_funds"]


def test_loading_keeps_a_blank_tier_blank(monkeypatch):
    """載入一次不得把未設定變成猜測值。

    突變：把 `load.py` 的 `"is_core": is_core_fund(...)` 那一行加回去 → 本條紅
    （名稱含「配息」⇒ 被猜成 True）。
    """
    funds = [{"code": "BGF", "policy_id": "P1", "is_core": None,
              "loaded": False, "invest_twd": 100}]
    out = _run_load(monkeypatch, funds, _TECH_FUND_WITH_DISCLAIMER)
    assert out[0]["loaded"] is True, "前提：真的載入了"
    assert out[0]["is_core"] is None, f"未設定被猜成 {out[0]['is_core']!r}"


def test_loading_keeps_an_explicit_satellite(monkeypatch):
    funds = [{"code": "BGF", "policy_id": "P1", "is_core": False,
              "loaded": False, "invest_twd": 100}]
    out = _run_load(monkeypatch, funds, _TECH_FUND_WITH_DISCLAIMER)
    assert out[0]["is_core"] is False


def test_tier_does_not_travel_across_policies_by_code():
    from ui.helpers.portfolio.load import _FUND_INFO_KEYS, reuse_fund_info_by_code
    assert "is_core" not in _FUND_INFO_KEYS
    prev = [{"code": "X1", "policy_id": "P1", "loaded": True,
             "name": "某基金", "is_core": True, "currency": "USD"}]
    merged = [{"code": "X1", "policy_id": "P9", "loaded": False, "currency": ""}]
    reuse_fund_info_by_code(merged, prev)
    assert merged[0].get("name") == "某基金", "前提：其他基金資訊照常沿用"
    assert "is_core" not in merged[0], "P1 的級別被搬進了 P9"


# ══════════════════════════════════════════════════════════════════
# 2. 寫回 Sheet
# ══════════════════════════════════════════════════════════════════
def _v1_written_tier(monkeypatch, ss) -> str:
    from ui.helpers import cloud_io
    _rows: list = []
    monkeypatch.setattr(cloud_io, "upsert_fund_in_policy",
                        lambda c, s, pid, row: _rows.append(row))
    monkeypatch.setattr(cloud_io, "save_all_ledgers_snapshot", lambda *a, **k: 0)
    monkeypatch.setattr(cloud_io, "save_holdings_overview", lambda *a, **k: 0)
    monkeypatch.setattr(cloud_io, "detect_sheet_schema_version",
                        lambda *a, **k: "v1", raising=False)
    out = cloud_io.dump_all_to_sheet("fake_client", "sheet_x", ss)
    assert out["error"] is None, out["error"]
    assert len(_rows) == 1
    return _rows[0]["policy_tier"]


def _v2_written_tier(monkeypatch, ss) -> str:
    from ui.helpers import cloud_io
    _seen: list = []
    monkeypatch.setattr(cloud_io, "write_policy_v2",
                        lambda c, s, pid, df: (_seen.append(df), 1)[1])
    out = cloud_io._dump_all_to_sheet_v2("fake_client", "sheet_x", ss)
    assert out["error"] is None, out["error"]
    assert len(_seen) == 1
    return _seen[0]["tier"].tolist()[0]


def _ss(fund):
    return {"portfolio_funds": [{"code": "F1", "policy_id": "P1", "invest_twd": 100,
                                 "currency": "USD", **fund}], "t7_ledgers": {}}


def test_v1_writeback_keeps_the_customers_explicit_tier(monkeypatch):
    """v1 讀回只寫 `policy_tier`；舊寫回式只讀 `is_core` ⇒ 會用猜測（停猜後是空白）蓋掉客戶的值。

    突變：v1 寫回式改回只讀 `is_core` 的三元式 → 本條紅（寫出 "satellite"）。
    """
    assert _v1_written_tier(monkeypatch, _ss({"policy_tier": "core", "is_core": False})) == "core"
    assert _v1_written_tier(monkeypatch, _ss({"policy_tier": "satellite"})) == "satellite"


def test_v2_writeback_keeps_the_customers_explicit_tier(monkeypatch):
    assert _v2_written_tier(monkeypatch, _ss({"policy_tier": "core", "is_core": False})) == "core"


def test_unset_round_trips_as_blank_through_load_then_save(monkeypatch):
    """讀回空白 → 載入 → 全部寫入（v1 與 v2）：寫回的仍是空白。"""
    for _writer in (_v1_written_tier, _v2_written_tier):
        funds = [{"code": "F1", "policy_id": "P1", "is_core": None,
                  "loaded": False, "invest_twd": 100, "currency": "USD"}]
        out = _run_load(monkeypatch, funds, _TECH_FUND_WITH_DISCLAIMER)
        assert _writer(monkeypatch, {"portfolio_funds": out, "t7_ledgers": {}}) == ""


class _FakeWS:
    def __init__(self): self.rows = None
    def clear(self): pass

    def update(self, *a, **kw):
        _v = kw.get("values")
        if _v is None and len(a) >= 2:
            _v = a[1]
        if _v:
            self.rows = _v


def _overview_tier(monkeypatch, fund) -> str:
    import repositories.snapshot_repository as _sr
    _ws = _FakeWS()
    monkeypatch.setattr(_sr, "_ensure_overview_worksheet", lambda c, s: _ws)

    class _Led:
        def to_dict(self):
            return {"fund_code": "F1", "currency": "USD",
                    "position": {"units": 1.0, "cost_unit": 10.0, "cost_unit_with_div": 10.0,
                                 "fx_avg": 32.0, "dividends_received_twd": 0.0}}

    _sr.save_holdings_overview("c", "s", {"P1::F1": _Led()}, {"P1::F1": fund})
    assert _ws.rows
    return _ws.rows[-1][4]


def test_holdings_overview_tier_column(monkeypatch):
    assert _overview_tier(monkeypatch, {"policy_tier": "core", "is_core": False,
                                        "name": "X", "invest_twd": 1}) == "核心"
    assert _overview_tier(monkeypatch, {"name": "X", "invest_twd": 1}) == ""
    assert _overview_tier(monkeypatch, {"is_core": False, "name": "X", "invest_twd": 1}) == "衛星"


def test_v2_read_clears_a_stale_v1_policy_tier(monkeypatch):
    """Sheet 上是 satellite，session 殘留 v1 的 `policy_tier="core"` ⇒ 讀回後以 Sheet 為準。"""
    from shared.policy_tier import resolve_tier
    from ui.helpers import cloud_io

    _ss_ = {"portfolio_funds": [{"code": "F1", "policy_id": "P1", "policy_tier": "core",
                                 "is_core": True, "invest_twd": 100, "currency": "USD"}]}

    class _DF:
        empty = False
        columns = ["policy_id", "fund_code", "tier"]

        def iterrows(self):
            yield 0, {"policy_id": "P1", "fund_code": "F1", "fund_name": "某基金",
                      "currency": "USD", "tier": "satellite", "invest_twd": 100,
                      "div_cash_pct": 100, "units": 0, "avg_nav": 0, "avg_fx": 0}

        def __getitem__(self, k): return ["P1"]

    monkeypatch.setattr(cloud_io, "load_all_policies_v2", lambda c, s: _DF())
    monkeypatch.setattr(cloud_io, "load_all_ledgers_snapshot", lambda *a, **k: {})
    out = cloud_io._load_all_from_sheet_v2("c", "s", _ss_)
    assert out["error"] is None, out["error"]
    assert resolve_tier(_ss_["portfolio_funds"][0]) == "satellite"


# ══════════════════════════════════════════════════════════════════
# 3. 新增基金的入口
# ══════════════════════════════════════════════════════════════════
def test_add_to_portfolio_button_does_not_decide_the_tier():
    """③ 單檔研究「➕ 加入組合」：舊碼寫 `is_core: True`（系統替客戶決定核心）。

    突變：把 `"is_core": True` 加回 `linkage.py` → 本條紅。
    """
    from streamlit.testing.v1 import AppTest

    def _script():
        import streamlit as st
        from ui.helpers.portfolio.linkage import render_fund_portfolio_membership
        render_fund_portfolio_membership(st.session_state, fund_codes=["NEW001"],
                                         fund_name="某新基金")

    _at = AppTest.from_function(_script, default_timeout=60)
    _at.session_state["portfolio_funds"] = [{"code": "OLD001", "invest_twd": 0}]
    _at.run()
    _btn = [b for b in _at.button if b.label == "➕ 加入組合"]
    assert _btn, "前提：按鈕存在"
    _btn[0].click().run()
    _new = [f for f in _at.session_state["portfolio_funds"] if f.get("code") == "NEW001"]
    assert len(_new) == 1, "前提：真的加進去了"
    assert "is_core" not in _new[0] and "policy_tier" not in _new[0], _new[0]


def test_first_use_wizard_autofill_never_guesses_a_tier(monkeypatch):
    """v2 首次使用精靈的自動帶入：只帶名稱／幣別，級別恆為空白。"""
    import services.fund_service as _fs
    from ui.helpers import v2_editor

    monkeypatch.setattr(_fs, "fetch_fund_from_moneydj_url_enriched",
                        lambda code: {"fund_name": _TECH_FUND_WITH_DISCLAIMER,
                                      "currency": "USD", "metrics": {}},
                        raising=False)
    _name, _ccy, _tier = v2_editor._autofill_from_moneydj("BGF")
    assert _name == _TECH_FUND_WITH_DISCLAIMER and _ccy == "USD", "前提：自動帶入有跑"
    assert _tier == ""


_NO_GUESS_FILES = (
    "ui/helpers/portfolio/load.py",
    "ui/helpers/portfolio/linkage.py",
    "ui/helpers/cloud_io.py",
    "repositories/snapshot_repository.py",
    "ui/helpers/v2_editor.py",
    "ui/tab3_portfolio.py",
    "ui/tab3_t7_ledger.py",
)


def _tree(rel):
    return ast.parse((ROOT / rel).read_text(encoding="utf-8"), filename=rel)


@pytest.mark.parametrize("rel", _NO_GUESS_FILES)
def test_no_name_heuristic_is_called_on_portfolio_paths(rel):
    """結構守衛：持倉的載入／寫回／新增路徑不得呼叫基金名稱啟發式（AST，註解不算）。

    ⚠️ 只擋直接呼叫（含 `as` 別名）；`importlib` 之類的繞法擋不住 —— 行為面由上面幾條守。
    突變：在 `ui/tab3_t7_ledger.py` 新基金條目加回 `"is_core": _is_core_fund(...)` → 本條紅。
    """
    _t = _tree(rel)
    _names = {"is_core_fund"}
    for _n in ast.walk(_t):
        if isinstance(_n, ast.ImportFrom):
            for _a in _n.names:
                if _a.name == "is_core_fund":
                    _names.add(_a.asname or _a.name)
    _hits = [n.lineno for n in ast.walk(_t)
             if isinstance(n, ast.Call)
             and ((isinstance(n.func, ast.Name) and n.func.id in _names)
                  or (isinstance(n.func, ast.Attribute) and n.func.attr in _names))]
    assert not _hits, f"{rel} 行 {_hits} 以基金名稱猜級別"


@pytest.mark.parametrize("rel", ("ui/tab3_portfolio.py", "ui/tab3_t7_ledger.py"))
def test_sheet_writes_of_policy_tier_go_through_the_ssot(rel):
    """④ 批次加入與 T7「套用起始部位」寫進 Sheet 的 `policy_tier` 一律走 SSOT。

    舊寫法只讀 `is_core` —— v1 讀回只寫 `policy_tier`，停猜後會把客戶明示的級別寫成空白。
    """
    _bad = []
    for _n in ast.walk(_tree(rel)):
        if not isinstance(_n, ast.Dict):
            continue
        for _k, _v in zip(_n.keys, _n.values):
            if isinstance(_k, ast.Constant) and _k.value == "policy_tier":
                if not (isinstance(_v, ast.Call) and isinstance(_v.func, ast.Name)
                        and _v.func.id == "_fund_tier_sheet_value"):
                    _bad.append(_k.lineno)
    assert not _bad, f"{rel} 行 {_bad}：policy_tier 沒有走 `fund_tier_sheet_value`"
