"""test_cloud_io — v18.162 PR：雲端讀寫 helper 純函式單元測試。

涵蓋（用 monkeypatch 模擬 gsheets API，不打網路）：
- dump_all_to_sheet：normal / skipped_no_pid / _T7_State warning 不致命 / exception 收口
- load_all_from_sheet：refresh_only / full load / restored_ct / warning
"""
from __future__ import annotations

import pandas as pd
import pytest


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


# ──────────────────────────────────────────────────────────────────
# load_all_from_sheet
# ──────────────────────────────────────────────────────────────────


def test_load_all_from_sheet_refresh_only_oauth(monkeypatch):
    from ui.helpers import cloud_io

    _pdf = pd.DataFrame([{"policy_id": "P1", "fund_url": "F1"}])
    monkeypatch.setattr(cloud_io, "load_all_policy_worksheets",
                         lambda c, s: _pdf)
    monkeypatch.setattr(cloud_io, "list_policy_worksheets",
                         lambda c, s: ["P1", "P2"])

    ss: dict = {}
    out = cloud_io.load_all_from_sheet("c", "s", ss,
                                        oauth_mode=True, refresh_only=True)
    assert out["ok"] is True
    assert out["refresh_only"] is True
    assert out["added"] == []   # refresh_only 不算 diff
    assert ss["policy_tabs"] == ["P1", "P2"]
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
    monkeypatch.setattr(cloud_io, "list_policy_worksheets",
                         lambda c, s: [])
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
    monkeypatch.setattr(cloud_io, "list_policy_worksheets", lambda c, s: [])
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


def test_load_all_from_sheet_unexpected_exception_caught(monkeypatch):
    from ui.helpers import cloud_io

    def _explode(c, s):
        raise RuntimeError("network down")
    monkeypatch.setattr(cloud_io, "load_all_policy_worksheets", _explode)

    out = cloud_io.load_all_from_sheet("c", "s", {}, oauth_mode=True)
    assert out["ok"] is False
    assert "RuntimeError" in out["error"]
    assert "network down" in out["error"]
