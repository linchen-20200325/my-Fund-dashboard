"""每月除息行事曆 LINE 摘要 headless(scripts/dividend_calendar_notify,v19.443)。

守:main 退出碼(無代碼→2 / 全抓失敗→1 / 缺憑證未送→1 / dry-run→0 印摘要)、
持倉∪追蹤去重、dry-run 不觸網。全 monkeypatch。
"""
from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fund_fetcher  # noqa: F401,E402  (prime latent 互 import)
from scripts import dividend_calendar_notify as M  # noqa: E402


def _divs(day=14, n=12):
    y, m, out = 2025, 1, []
    for _ in range(n):
        out.append({"ex_date": _dt.date(y, m, day).isoformat(),
                    "pay_date": _dt.date(y, m, day).isoformat(), "amount": 0.05, "yield_pct": 6.0})
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def _patch_readers(monkeypatch, *, held, watch):
    import scripts.weekly_switch_notify as W
    monkeypatch.setattr(W, "_load_client_and_sheet", lambda: ("client", "sid"))
    monkeypatch.setattr(W, "_read_holdings", lambda c, s: held)
    monkeypatch.setattr(W, "_read_watchlist", lambda: watch)


def test_main_no_codes_exit2(monkeypatch):
    _patch_readers(monkeypatch, held=[], watch=[])
    assert M.main([]) == 2


def test_main_all_fetch_fail_exit1(monkeypatch):
    _patch_readers(monkeypatch, held=["AAA"], watch=[])
    monkeypatch.setattr(M, "_fetch_divs", lambda codes: [])
    assert M.main([]) == 1


def test_main_all_fetch_returned_none_does_not_send(monkeypatch):
    """稽核 H1:auto_fetch 失敗回 dict(dividends=None)→ funds 非空但無 list →
    不可送「本月無除息」誤導訊息 → exit 1、完全不 push(§1)。"""
    _patch_readers(monkeypatch, held=["AAA", "BBB"], watch=[])
    monkeypatch.setattr(M, "_fetch_divs",
                        lambda codes: [{"code": c, "name": c, "house": "", "dividends": None}
                                       for c in codes])
    import infra.line_push as LP
    _sent = []
    monkeypatch.setattr(LP, "push_text", lambda *a, **k: _sent.append(1) or {"sent": True})
    assert M.main([]) == 1 and _sent == []


def test_main_dry_run_prints_summary(monkeypatch, capsys):
    _patch_readers(monkeypatch, held=["TLZF9"], watch=["TLZF9", "JFZN3"])   # TLZF9 重複
    seen = {}

    def _fake_fetch(codes):
        seen["codes"] = codes
        return [{"code": c, "name": f"{c}基金", "house": "", "dividends": _divs()} for c in codes]
    monkeypatch.setattr(M, "_fetch_divs", _fake_fetch)
    rc = M.main(["--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert seen["codes"] == ["TLZF9", "JFZN3"]          # 持倉∪追蹤去重保序
    assert "基金除息行事曆" in out and "推估非官方" in out


def test_main_missing_creds_returns_1(monkeypatch):
    _patch_readers(monkeypatch, held=["TLZF9"], watch=[])
    monkeypatch.setattr(M, "_fetch_divs",
                        lambda codes: [{"code": "TLZF9", "name": "安聯", "house": "安聯",
                                        "dividends": _divs()}])
    import infra.line_push as LP
    monkeypatch.setattr(LP, "push_text",
                        lambda text, **k: {"sent": False, "reason": "缺 LINE_USER_ID"})
    assert M.main([]) == 1                               # 有內容但未送 → 失敗(§1)
