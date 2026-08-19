"""v19.479:每週 NAV 自動補齊 cron(scripts/weekly_nav_backfill.py)。

驗證:代號蒐集(持倉 ∪ 選股池,去重 upper、單邊失敗不擋)+ main 退出碼(§1 Fail Loud)。
不打真網路 / 不碰真 Sheet —— 全 monkeypatch。
"""
import types

import pytest

import scripts.weekly_nav_backfill as W


class _E:
    def __init__(self, code):
        self.code = code


def _patch_pool(monkeypatch, codes):
    import repositories.pool_repository as PR
    monkeypatch.setattr(PR, "list_pool", lambda: [_E(c) for c in codes])


def _patch_holdings(monkeypatch, fn):
    import scripts.weekly_switch_notify as SW
    monkeypatch.setattr(SW, "_read_holdings", fn)


# ── _gather_codes ───────────────────────────────────────────────────────
def test_gather_union_dedup_upper(monkeypatch):
    _patch_holdings(monkeypatch, lambda c, s: ["ACDD01", "jfzn3"])
    _patch_pool(monkeypatch, ["jfzn3", "TLZF9", " albt8 "])   # jfzn3 與持倉重複
    out = W._gather_codes(object(), "SID")
    assert out == ["ACDD01", "JFZN3", "TLZF9", "ALBT8"]       # 去重 + upper + 保序(持倉先)


def test_gather_holdings_failure_keeps_pool(monkeypatch):
    def _boom(c, s):
        raise RuntimeError("policy sheet 讀取失敗")
    _patch_holdings(monkeypatch, _boom)
    _patch_pool(monkeypatch, ["TLZF9"])
    assert W._gather_codes(object(), "SID") == ["TLZF9"]      # 持倉炸 → 仍回選股池


def test_gather_pool_failure_keeps_holdings(monkeypatch):
    _patch_holdings(monkeypatch, lambda c, s: ["ACDD01"])
    import repositories.pool_repository as PR
    monkeypatch.setattr(PR, "list_pool", lambda: (_ for _ in ()).throw(RuntimeError("pool 讀取失敗")))
    assert W._gather_codes(object(), "SID") == ["ACDD01"]     # 選股池炸 → 仍回持倉


def test_gather_no_client_skips_holdings(monkeypatch):
    _patch_holdings(monkeypatch, lambda c, s: ["SHOULD_NOT"])  # client None → 不呼叫持倉
    _patch_pool(monkeypatch, ["TLZF9"])
    assert W._gather_codes(None, None) == ["TLZF9"]


# ── main 退出碼(§1)─────────────────────────────────────────────────────
def test_main_no_client_exits_2(monkeypatch):
    monkeypatch.setattr(W, "_load_client_and_holdings_sheet", lambda: (None, None))
    assert W.main([]) == 2


def test_main_no_codes_exits_2(monkeypatch):
    monkeypatch.setattr(W, "_load_client_and_holdings_sheet", lambda: (object(), "SID"))
    monkeypatch.setattr(W, "_gather_codes", lambda c, s: [])
    assert W.main([]) == 2


def test_main_dry_run_lists_without_fetch(monkeypatch):
    monkeypatch.setattr(W, "_load_client_and_holdings_sheet", lambda: (object(), "SID"))
    monkeypatch.setattr(W, "_gather_codes", lambda c, s: ["TLZF9", "JFZN3"])
    # dry-run 不該 import/呼叫 backfill_to_gs;若呼叫則測試以 import error 或 assert 失敗
    import services.nav_history_store as NS
    monkeypatch.setattr(NS, "backfill_to_gs",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("dry-run 不該抓")))
    assert W.main(["--dry-run"]) == 0


def test_main_gs_disabled_exits_2(monkeypatch):
    monkeypatch.setattr(W, "_load_client_and_holdings_sheet", lambda: (object(), "SID"))
    monkeypatch.setattr(W, "_gather_codes", lambda c, s: ["TLZF9"])
    import services.nav_history_gs as GS
    monkeypatch.setattr(GS, "is_enabled", lambda: False)
    assert W.main([]) == 2                                    # 雲端未啟用 → exit 2


def test_main_success_returns_0(monkeypatch):
    monkeypatch.setattr(W, "_load_client_and_holdings_sheet", lambda: (object(), "SID"))
    monkeypatch.setattr(W, "_gather_codes", lambda c, s: ["TLZF9"])
    import services.nav_history_gs as GS
    import services.nav_history_store as NS
    monkeypatch.setattr(GS, "is_enabled", lambda: True)
    monkeypatch.setattr(NS, "backfill_to_gs", lambda codes: {
        "results": [{"code": "TLZF9", "fetched": 1300, "date_min": "2021-01-01",
                     "date_max": "2026-08-18", "source": "yahoo(ISIN)", "error": None}],
        "gs_enabled": True, "gs_written": 5, "gs_error": None, "n_ok": 1, "n_fail": 0,
    })
    assert W.main([]) == 0


def test_main_all_fail_exits_1(monkeypatch):
    monkeypatch.setattr(W, "_load_client_and_holdings_sheet", lambda: (object(), "SID"))
    monkeypatch.setattr(W, "_gather_codes", lambda c, s: ["TLZF9"])
    import services.nav_history_gs as GS
    import services.nav_history_store as NS
    monkeypatch.setattr(GS, "is_enabled", lambda: True)
    monkeypatch.setattr(NS, "backfill_to_gs", lambda codes: {
        "results": [{"code": "TLZF9", "fetched": 0, "date_min": None, "date_max": None,
                     "source": None, "error": "抓不到"}],
        "gs_enabled": True, "gs_written": 0, "gs_error": None, "n_ok": 0, "n_fail": 1,
    })
    assert W.main([]) == 1
