"""test_cloud_io — v18.162 PR：雲端讀寫 helper 純函式單元測試。

涵蓋（用 monkeypatch 模擬 gsheets API，不打網路）：
- dump_all_to_sheet：normal / skipped_no_pid / _T7_State warning 不致命 / exception 收口
- load_all_from_sheet：refresh_only / full load / restored_ct / warning
"""
from __future__ import annotations

import pandas as pd


# ──────────────────────────────────────────────────────────────────
# dump_all_to_sheet
# ──────────────────────────────────────────────────────────────────


def test_dump_all_to_sheet_success(monkeypatch):
    from ui.helpers import cloud_io

    _calls = []
    def _fake_upsert(client, sid, pid, row):
        _calls.append((pid, row["fund_url"]))

    monkeypatch.setattr(cloud_io, "upsert_fund_in_policy", _fake_upsert)
    monkeypatch.setattr(cloud_io, "save_all_ledgers_snapshot",
                         lambda c, s, t, f: 7)
    monkeypatch.setattr(cloud_io, "save_holdings_overview",
                         lambda c, s, t, f: 5)

    ss = {
        "portfolio_funds": [
            {"code": "F1", "policy_id": "P1", "invest_twd": 100000, "currency": "USD"},
            {"code": "f2", "policy_id": "P1", "invest_twd": 50000, "currency": "TWD"},
        ],
        "t7_ledgers": {"P1::F1": object()},
    }
    out = cloud_io.dump_all_to_sheet("fake_client", "sheet_x", ss)
    assert out["ok"] is True
    assert out["error"] is None
    assert out["written"] == 2
    assert out["skipped_no_pid"] == 0
    assert out["n_state"] == 7
    assert out["n_overview"] == 5
    assert out["warnings"] == []
    # 確認 code 大寫化
    assert _calls[1][1] == "F2"


def test_dump_all_to_sheet_skips_funds_without_policy_id(monkeypatch):
    from ui.helpers import cloud_io
    monkeypatch.setattr(cloud_io, "upsert_fund_in_policy",
                         lambda *a, **kw: None)
    monkeypatch.setattr(cloud_io, "save_all_ledgers_snapshot",
                         lambda *a, **kw: 0)

    ss = {
        "portfolio_funds": [
            {"code": "F1", "policy_id": "P1", "invest_twd": 1},
            {"code": "ORPHAN", "policy_id": "", "invest_twd": 2},
            {"code": "", "policy_id": "P2", "invest_twd": 3},  # 空 code 也略過
        ],
        "t7_ledgers": {},
    }
    out = cloud_io.dump_all_to_sheet("c", "s", ss)
    assert out["ok"] is True
    assert out["written"] == 1
    assert out["skipped_no_pid"] == 1


def test_dump_all_to_sheet_t7_state_failure_is_warning_not_error(monkeypatch):
    from ui.helpers import cloud_io
    from repositories.policy_repository import PolicySheetError

    monkeypatch.setattr(cloud_io, "upsert_fund_in_policy",
                         lambda *a, **kw: None)

    def _fail_save(*a, **kw):
        raise PolicySheetError("quota exceeded")
    monkeypatch.setattr(cloud_io, "save_all_ledgers_snapshot", _fail_save)
    # v18.182：隔離 _T7_State 失敗的斷言，把 _持倉總覽 寫入 patch 成功
    monkeypatch.setattr(cloud_io, "save_holdings_overview",
                         lambda *a, **kw: 1)

    ss = {
        "portfolio_funds": [{"code": "F1", "policy_id": "P1", "invest_twd": 1}],
        "t7_ledgers": {"P1::F1": object()},
    }
    out = cloud_io.dump_all_to_sheet("c", "s", ss)
    assert out["ok"] is True   # 整體仍 ok
    assert out["written"] == 1
    assert out["n_state"] == 0
    assert len(out["warnings"]) == 1
    assert "quota exceeded" in out["warnings"][0]


def test_dump_all_to_sheet_unexpected_exception_caught(monkeypatch):
    from ui.helpers import cloud_io

    def _explode(*a, **kw):
        raise ValueError("boom")
    monkeypatch.setattr(cloud_io, "upsert_fund_in_policy", _explode)

    ss = {"portfolio_funds": [{"code": "F1", "policy_id": "P1"}],
          "t7_ledgers": {}}
    out = cloud_io.dump_all_to_sheet("c", "s", ss)
    assert out["ok"] is False
    assert "ValueError" in out["error"]
    assert "boom" in out["error"]


def test_dump_all_to_sheet_empty_portfolio(monkeypatch):
    from ui.helpers import cloud_io
    monkeypatch.setattr(cloud_io, "upsert_fund_in_policy",
                         lambda *a, **kw: None)
    monkeypatch.setattr(cloud_io, "save_all_ledgers_snapshot",
                         lambda *a, **kw: 0)
    out = cloud_io.dump_all_to_sheet("c", "s", {})
    assert out["ok"] is True
    assert out["written"] == 0
    assert out["n_state"] == 0


def test_dump_all_to_sheet_surfaces_per_fund_write_failure(monkeypatch):
    """v18.189：upsert 失敗不再靜默 → 收進 warnings（含息成本沒寫進去能被看到）。"""
    from ui.helpers import cloud_io
    from repositories.policy_repository import PolicySheetError

    def _fail_upsert(client, sid, pid, row):
        raise PolicySheetError("header upgrade failed")
    monkeypatch.setattr(cloud_io, "upsert_fund_in_policy", _fail_upsert)
    monkeypatch.setattr(cloud_io, "save_all_ledgers_snapshot", lambda *a, **k: 0)
    monkeypatch.setattr(cloud_io, "save_holdings_overview", lambda *a, **k: 0)

    ss = {"portfolio_funds": [{"code": "F1", "policy_id": "P1", "invest_twd": 1,
                               "avg_nav_with_div": 7.83}],
          "t7_ledgers": {}}
    out = cloud_io.dump_all_to_sheet("c", "s", ss)
    assert out["ok"] is True          # 整體不致命
    assert out["written"] == 0
    assert len(out["warnings"]) == 1
    assert "寫入保單分頁失敗" in out["warnings"][0]
    assert "P1/F1" in out["warnings"][0]


def test_dump_pulls_cost_basis_from_ledgers_v198(monkeypatch):
    """v18.198：保單分頁寫入時，avg_nav/fx_avg/units 從 t7_ledgers 帶出。"""
    import types

    from ui.helpers import cloud_io
    captured: list = []
    monkeypatch.setattr(cloud_io, "upsert_fund_in_policy",
                         lambda c, s, pid, row: captured.append(row))
    monkeypatch.setattr(cloud_io, "save_all_ledgers_snapshot", lambda *a, **k: 0)
    monkeypatch.setattr(cloud_io, "save_holdings_overview", lambda *a, **k: 0)

    _pos = types.SimpleNamespace(cost_unit=8.67, fx_avg=32.35, units=1780.94)
    _led = types.SimpleNamespace(position=_pos)
    ss = {"portfolio_funds": [{"code": "ACTI71", "policy_id": "P1", "invest_twd": 1}],
          "t7_ledgers": {"P1::ACTI71": _led}}
    out = cloud_io.dump_all_to_sheet("c", "s", ss)
    assert out["ok"] is True
    assert captured[0]["avg_nav"] == 8.67
    assert captured[0]["fx_avg"] == 32.35
    assert captured[0]["units"] == 1780.94


# ──────────────────────────────────────────────────────────────────
# load_all_from_sheet
# ──────────────────────────────────────────────────────────────────


def test_load_all_from_sheet_refresh_only_oauth(monkeypatch):
    from ui.helpers import cloud_io

    _pdf = pd.DataFrame([{"policy_id": "P1", "fund_url": "F1"}])
    monkeypatch.setattr(cloud_io, "load_all_policy_worksheets",
                         lambda c, s: _pdf)

    ss: dict = {}
    out = cloud_io.load_all_from_sheet("c", "s", ss,
                                        oauth_mode=True, refresh_only=True)
    assert out["ok"] is True
    assert out["refresh_only"] is True
    assert out["added"] == []   # refresh_only 不算 diff
    assert ss["policy_tabs"] == ["P1"]   # v18.199：從 DataFrame policy_id 推（非再列 worksheets）
    assert ss["policies_df"] is _pdf
    # 確認沒動 portfolio_funds
    assert "portfolio_funds" not in ss


def test_load_all_from_sheet_sa_mode_uses_load_policies(monkeypatch):
    from ui.helpers import cloud_io

    _pdf = pd.DataFrame([{"policy_id": "P1"}])
    monkeypatch.setattr(cloud_io, "load_policies", lambda c, s: _pdf)
    ss: dict = {}
    out = cloud_io.load_all_from_sheet("c", "s", ss,
                                        oauth_mode=False, refresh_only=True)
    assert out["ok"] is True
    assert ss["policies_df"] is _pdf
    assert "policy_tabs" not in ss   # SA 模式不用


def test_load_all_from_sheet_full_load_with_sync_report(monkeypatch):
    from ui.helpers import cloud_io

    _pdf = pd.DataFrame([{"policy_id": "P1"}])
    monkeypatch.setattr(cloud_io, "load_all_policy_worksheets",
                         lambda c, s: _pdf)
    _report = {"added": ["FNEW"], "kept": ["F1"], "removed": ["FOLD"]}
    monkeypatch.setattr(cloud_io, "sync_policies_to_portfolio_funds",
                         lambda pdf, funds: ([{"code": "merged"}], _report))
    monkeypatch.setattr(cloud_io, "load_all_ledgers_snapshot",
                         lambda c, s, L: {})   # 空 ledger snapshot

    ss = {"portfolio_funds": [{"code": "F1"}]}
    out = cloud_io.load_all_from_sheet("c", "s", ss, oauth_mode=True)
    assert out["ok"] is True
    assert out["added"] == ["FNEW"]
    assert out["kept"] == ["F1"]
    assert out["removed"] == ["FOLD"]
    assert out["restored_ct"] == 0
    assert ss["portfolio_funds"] == [{"code": "merged"}]


def test_load_all_from_sheet_ledger_load_failure_is_warning(monkeypatch):
    from ui.helpers import cloud_io
    from repositories.policy_repository import PolicySheetError

    monkeypatch.setattr(cloud_io, "load_all_policy_worksheets",
                         lambda c, s: pd.DataFrame())
    monkeypatch.setattr(cloud_io, "sync_policies_to_portfolio_funds",
                         lambda pdf, funds: ([], {"added": [], "kept": [], "removed": []}))

    def _fail_load(*a, **kw):
        raise PolicySheetError("snapshot 404")
    monkeypatch.setattr(cloud_io, "load_all_ledgers_snapshot", _fail_load)

    ss: dict = {}
    out = cloud_io.load_all_from_sheet("c", "s", ss, oauth_mode=True)
    assert out["ok"] is True
    assert out["restored_ct"] == 0
    assert len(out["warnings"]) == 1
    assert "snapshot 404" in out["warnings"][0]


def test_load_all_from_sheet_clears_stale_ledgers_when_new_book_empty(monkeypatch):
    """v18.187：切換到「無 _T7_State 快照」的帳本 → 清掉前一本殘留的 t7_ledgers。"""
    from ui.helpers import cloud_io

    monkeypatch.setattr(cloud_io, "load_all_policy_worksheets",
                         lambda c, s: pd.DataFrame([{"policy_id": "P9"}]))
    monkeypatch.setattr(cloud_io, "sync_policies_to_portfolio_funds",
                         lambda pdf, funds: ([{"code": "NEW"}],
                                             {"added": ["NEW"], "kept": [], "removed": []}))
    monkeypatch.setattr(cloud_io, "load_all_ledgers_snapshot",
                         lambda c, s, L: {})   # 新帳本沒有快照

    ss = {
        "portfolio_funds": [{"code": "OLD"}],
        "t7_ledgers": {"PA::OLD": object()},      # 前一本殘留
        "_t7_auto_restore_done": True,            # 前一本設過的旗標
    }
    out = cloud_io.load_all_from_sheet("c", "s", ss, oauth_mode=True)
    assert out["ok"] is True
    assert ss["t7_ledgers"] == {}                 # 已清空，不再殘留舊本
    assert out["restored_ct"] == 0
    assert "_t7_auto_restore_done" not in ss       # 旗標清掉 → 新本重跑 auto-restore


def test_load_all_from_sheet_replaces_ledgers_when_new_book_has_snapshot(monkeypatch):
    """v18.187：新帳本有快照 → t7_ledgers 換成新本的（非殘留舊本）。"""
    import sys
    import types

    from ui.helpers import cloud_io

    monkeypatch.setattr(cloud_io, "load_all_policy_worksheets",
                         lambda c, s: pd.DataFrame([{"policy_id": "P9"}]))
    monkeypatch.setattr(cloud_io, "sync_policies_to_portfolio_funds",
                         lambda pdf, funds: ([{"code": "NEW"}],
                                             {"added": [], "kept": [], "removed": []}))
    _new_snap = {"P9::NEW": object()}
    monkeypatch.setattr(cloud_io, "load_all_ledgers_snapshot",
                         lambda c, s, L: _new_snap)
    # 避免拉進真實 tab3_t7_ledger（重、需 streamlit session）→ 注入假模組
    _fake = types.ModuleType("ui.tab3_t7_ledger")
    _fake._sync_invest_twd_from_ledgers = lambda: None
    monkeypatch.setitem(sys.modules, "ui.tab3_t7_ledger", _fake)

    ss = {"portfolio_funds": [{"code": "OLD"}],
          "t7_ledgers": {"PA::OLD": object()}}
    out = cloud_io.load_all_from_sheet("c", "s", ss, oauth_mode=True)
    assert ss["t7_ledgers"] is _new_snap
    assert out["restored_ct"] == 1


def test_load_all_from_sheet_unexpected_exception_caught(monkeypatch):
    from ui.helpers import cloud_io

    def _explode(c, s):
        raise RuntimeError("network down")
    monkeypatch.setattr(cloud_io, "detect_sheet_schema_version",
                         lambda c, s: "v1")   # 走 v1 path 撞 _explode
    monkeypatch.setattr(cloud_io, "load_all_policy_worksheets", _explode)

    out = cloud_io.load_all_from_sheet("c", "s", {}, oauth_mode=True)
    assert out["ok"] is False
    assert "RuntimeError" in out["error"]
    assert "network down" in out["error"]


# ══════════════════════════════════════════════════════════════════
# v18.250 PR C：schema-aware routing — v2 走專屬 helper
# ══════════════════════════════════════════════════════════════════
def test_dump_routes_to_v2_when_detected(monkeypatch):
    """detect=v2 → 呼叫 write_policy_v2，不呼叫 v1 helpers。"""
    from ui.helpers import cloud_io

    _v2_calls = []
    _v1_calls = []
    monkeypatch.setattr(cloud_io, "detect_sheet_schema_version",
                         lambda c, s: "v2")
    monkeypatch.setattr(cloud_io, "write_policy_v2",
                         lambda c, s, pid, df: (_v2_calls.append((pid, len(df))),
                                                  len(df))[1])
    monkeypatch.setattr(cloud_io, "upsert_fund_in_policy",
                         lambda *a, **k: _v1_calls.append(a))
    monkeypatch.setattr(cloud_io, "save_all_ledgers_snapshot",
                         lambda *a, **k: _v1_calls.append("snapshot"))

    ss = {
        "portfolio_funds": [
            {"code": "F1", "policy_id": "P1", "name": "Fund 1",
              "invest_twd": 100000, "currency": "USD",
              "units": 1000, "avg_nav": 10.0, "fx_avg": 30.0},
            {"code": "F2", "policy_id": "P1", "name": "Fund 2",
              "invest_twd": 50000, "currency": "TWD",
              "units": 500, "avg_nav": 100.0, "fx_avg": 1.0},
            {"code": "F3", "policy_id": "P2", "name": "Fund 3",
              "invest_twd": 75000, "currency": "USD",
              "units": 2500, "avg_nav": 12.5, "fx_avg": 30.0},
        ],
        "t7_ledgers": {},
    }
    out = cloud_io.dump_all_to_sheet("c", "s", ss)
    assert out["ok"] is True
    assert out["error"] is None
    # v2 path 被呼叫，v1 完全沒
    assert len(_v2_calls) == 2   # 2 policies (P1, P2)
    assert _v1_calls == []
    # P1 含 2 檔、P2 含 1 檔
    _by_pid = dict(_v2_calls)
    assert _by_pid == {"P1": 2, "P2": 1}
    assert out["written"] == 3


def test_load_routes_to_v2_when_detected(monkeypatch):
    """detect=v2 → 呼叫 load_all_policies_v2 反推 portfolio_funds + ledger snapshot。"""
    from ui.helpers import cloud_io

    _v1_calls = []
    monkeypatch.setattr(cloud_io, "detect_sheet_schema_version",
                         lambda c, s: "v2")
    monkeypatch.setattr(cloud_io, "load_all_policy_worksheets",
                         lambda c, s: _v1_calls.append("v1_load") or pd.DataFrame())
    monkeypatch.setattr(cloud_io, "load_all_ledgers_snapshot",
                         lambda c, s, L: _v1_calls.append("snapshot_load"))
    # mock v2 load 回一張 13 欄 DataFrame
    _df_v2 = pd.DataFrame([
        {"policy_id": "P1", "item_type": "fund", "fund_code": "F1",
          "fund_name": "Fund One", "units": 1000.0, "avg_nav": 10.0,
          "avg_nav_with_div": 9.5, "avg_fx": 30.0, "currency": "USD",
          "tier": "core", "amount": 0, "invest_twd": 300000,
          "div_cash_pct": 100.0},
        {"policy_id": "P1", "item_type": "fund", "fund_code": "F2",
          "fund_name": "Fund Two", "units": 500.0, "avg_nav": 100.0,
          "avg_nav_with_div": 95.0, "avg_fx": 1.0, "currency": "TWD",
          "tier": "satellite", "amount": 0, "invest_twd": 50000,
          "div_cash_pct": 50.0},
    ])
    monkeypatch.setattr(cloud_io, "load_all_policies_v2",
                         lambda c, s: _df_v2)

    ss = {}
    out = cloud_io.load_all_from_sheet("c", "s", ss, oauth_mode=True)
    assert out["ok"] is True
    assert out["error"] is None
    # v1 helpers 完全沒被呼叫
    assert _v1_calls == []
    # portfolio_funds 反推正確
    assert len(ss["portfolio_funds"]) == 2
    _f1 = ss["portfolio_funds"][0]
    assert _f1["code"] == "F1" and _f1["policy_id"] == "P1"
    assert _f1["units"] == 1000.0
    assert _f1["avg_nav"] == 10.0
    assert _f1["fx_avg"] == 30.0
    assert _f1["div_cash_pct"] == 100.0
    assert _f1["is_core"] is True
    _f2 = ss["portfolio_funds"][1]
    assert _f2["is_core"] is False   # tier=satellite
    # ledger 重建（兩檔都 units>0）
    assert out["restored_ct"] == 2
    assert len(ss["t7_ledgers"]) == 2
    # policy_tabs 由 policy_id 推
    assert ss["policy_tabs"] == ["P1"]


def test_v1_path_unchanged_when_v1(monkeypatch):
    """detect=v1 → 走原 v1 path，v2 helper 不被呼叫（向後相容）。"""
    from ui.helpers import cloud_io

    _v2_calls = []
    _v1_upserts = []
    monkeypatch.setattr(cloud_io, "detect_sheet_schema_version",
                         lambda c, s: "v1")
    monkeypatch.setattr(cloud_io, "write_policy_v2",
                         lambda c, s, pid, df: _v2_calls.append(pid))
    monkeypatch.setattr(cloud_io, "upsert_fund_in_policy",
                         lambda c, s, pid, row: _v1_upserts.append(
                             (pid, row["fund_url"])))
    monkeypatch.setattr(cloud_io, "save_all_ledgers_snapshot",
                         lambda c, s, t, f: 0)
    monkeypatch.setattr(cloud_io, "save_holdings_overview",
                         lambda c, s, t, f: 0)

    ss = {"portfolio_funds": [
        {"code": "F1", "policy_id": "P1", "invest_twd": 100000,
          "currency": "USD"}], "t7_ledgers": {}}
    out = cloud_io.dump_all_to_sheet("c", "s", ss)
    assert out["ok"] is True
    assert _v2_calls == []   # v2 沒被叫
    assert _v1_upserts == [("P1", "F1")]


def test_v2_round_trip_keeps_13_cols(monkeypatch):
    """v2 dump 寫的 df 含 ALL_COLS_V2 全 13 欄；load 反推保留關鍵欄位。"""
    from ui.helpers import cloud_io
    from repositories.policy_repository import ALL_COLS_V2

    _captured_df = {}
    monkeypatch.setattr(cloud_io, "detect_sheet_schema_version",
                         lambda c, s: "v2")
    def _capture(c, s, pid, df):
        _captured_df[pid] = df.copy()
        return len(df)
    monkeypatch.setattr(cloud_io, "write_policy_v2", _capture)

    ss = {"portfolio_funds": [
        {"code": "F1", "policy_id": "P1", "name": "Fund Alpha",
          "invest_twd": 300000, "currency": "USD",
          "units": 1000.0, "avg_nav": 10.0, "fx_avg": 30.0,
          "avg_nav_with_div": 9.5, "div_cash_pct": 80.0,
          "is_core": True}], "t7_ledgers": {}}
    cloud_io.dump_all_to_sheet("c", "s", ss)

    _df = _captured_df["P1"]
    # 13 欄全在
    assert set(_df.columns) == set(ALL_COLS_V2)
    _r = _df.iloc[0]
    assert _r["fund_code"] == "F1"
    assert _r["fund_name"] == "Fund Alpha"
    assert _r["units"] == 1000.0
    assert _r["avg_nav"] == 10.0
    assert _r["avg_nav_with_div"] == 9.5
    assert _r["avg_fx"] == 30.0
    assert _r["currency"] == "USD"
    assert _r["tier"] == "core"
    assert _r["invest_twd"] == 300000
    assert _r["div_cash_pct"] == 80.0
    assert _r["item_type"] == "fund"
