"""headless 週報 cron 編排(scripts/weekly_switch_notify,v19.432)。

守:row 組裝欄位對映(σ/類別/型態/nav_series)+ 類別 fallback、表現差 dict str 鍵、
main 退出碼(缺 secret→2 / 無持倉→2 / 全抓失敗→1 / 無建議→0 不推 / 有建議→推)。
重依賴全 monkeypatch,不觸網。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fund_fetcher  # noqa: F401,E402  (prime 既有 latent 互 import)
from scripts import weekly_switch_notify as M  # noqa: E402


class _PE:
    def __init__(self, code, category="", type_override=""):
        self.code = code
        self.category = category
        self.type_override = type_override


# ── _assemble_rows ────────────────────────────────
def test_assemble_rows_maps_fields(monkeypatch):
    import services.health.dividend as D
    import services.health.report as R
    import ui.helpers.fund_grp_health.unified as U
    monkeypatch.setattr(U, "build_merged_extra_columns",
                        lambda funds, phase, score: ([], {"AAA": {"σ rank": "-1.50σ",
                                                                   "距 HWM %": "-18%", "操盤評分": 72}}))
    monkeypatch.setattr(R, "build_health_analysis_row", lambda fd, code: {"基金類別": "股票", "4D Grade": "B"})
    monkeypatch.setattr(D, "check_eating_principal_1y_mk", lambda fd: {"status": "🟢 健康"})

    funds = [{"code": "AAA", "name": "基金A", "series": pd.Series([1.0, 2.0]), "moneydj_raw": {}}]
    r = M._assemble_rows(funds, {"AAA": _PE("AAA", type_override="震盪")})[0]
    assert r["σ rank"] == "-1.50σ" and r["操盤評分"] == 72
    assert r["基金類別"] == "股票" and r["4D Grade"] == "B" and r["吃本金燈號"] == "🟢 健康"
    assert r["type_override"] == "震盪" and r["nav_series"] is not None


def test_assemble_rows_category_falls_back_to_pool(monkeypatch):
    import services.health.dividend as D
    import services.health.report as R
    import ui.helpers.fund_grp_health.unified as U
    monkeypatch.setattr(U, "build_merged_extra_columns", lambda funds, phase, score: ([], {}))
    monkeypatch.setattr(R, "build_health_analysis_row", lambda fd, code: {})   # 無類別
    monkeypatch.setattr(D, "check_eating_principal_1y_mk", lambda fd: {})

    funds = [{"code": "BBB", "name": "b", "series": None, "moneydj_raw": {}}]
    r = M._assemble_rows(funds, {"BBB": _PE("BBB", category="平衡型")})[0]
    assert r["基金類別"] == "平衡型"                       # health 無 → 退 pool 類別


# ── _underperf_by_code ────────────────────────────────
def test_underperf_by_code_keys_str_and_flags(monkeypatch):
    import services.fund_total_return as T
    import ui.helpers.fund_grp_health.capture as C
    monkeypatch.setattr(C, "capture_by_code",
                        lambda funds: {"AAA": {"vs 大盤%": -8.0, "vs 大盤期間": "近1年"}})
    monkeypatch.setattr(T, "compute_1y_total_return", lambda f: (5.0, ""))   # 不虧(紅燈另判)

    funds = [{"code": "AAA", "currency": "USD", "metrics": {"sharpe": 1.0}, "risk_metrics": {}}]
    out = M._underperf_by_code(funds)
    assert "AAA" in out and out["AAA"]["is_underperforming"] is True   # 跑輸 -8 < -5
    assert out["AAA"]["benchmark_used"] == "SPX"


# ── main() 退出碼 + 推播 ────────────────────────────────
def _rich(code):
    return {"code": code, "name": code, "series": pd.Series([1.0, 2.0]),
            "currency": "USD", "metrics": {}, "risk_metrics": {}, "moneydj_raw": {}}


def _patch_main_common(monkeypatch, *, held, rich):
    import repositories.pool_repository as P
    monkeypatch.setattr(M, "_load_client_and_sheet", lambda: ("client", "sid"))
    monkeypatch.setattr(P, "list_pool", lambda: [])
    monkeypatch.setattr(M, "_read_holdings", lambda c, s: held)
    monkeypatch.setattr(M, "_fetch_rich", lambda codes: rich)
    monkeypatch.setattr(M, "_assemble_rows", lambda funds, pbc: [{"code": f["code"]} for f in funds])
    monkeypatch.setattr(M, "_underperf_by_code", lambda funds: {})
    monkeypatch.setattr(M, "_fx_label", lambda: None)


def test_main_no_secrets_exit2(monkeypatch):
    monkeypatch.setattr(M, "_load_client_and_sheet", lambda: (None, None))
    assert M.main([]) == 2


def test_main_no_holdings_exit2(monkeypatch):
    _patch_main_common(monkeypatch, held=[], rich={})
    assert M.main([]) == 2


def test_main_all_fetch_fail_exit1(monkeypatch):
    _patch_main_common(monkeypatch, held=["AAA"], rich={})
    assert M.main([]) == 1


def test_main_no_actionable_returns0_and_no_push(monkeypatch):
    _patch_main_common(monkeypatch, held=["AAA"], rich={"AAA": _rich("AAA")})
    import services.switch_advisor as SA
    import services.switch_notify as SN
    import infra.line_push as LP
    monkeypatch.setattr(SA, "advise_switches", lambda *a, **k: {"advices": [], "summary": {}, "caveat": ""})
    monkeypatch.setattr(SN, "build_notification",
                        lambda res, **k: {"should_notify": False, "message": "無", "n_actionable": 0})
    _sent = []
    monkeypatch.setattr(LP, "push_text", lambda *a, **k: _sent.append(1) or {"sent": True, "reason": "ok"})
    assert M.main([]) == 0
    assert _sent == []                                    # 無建議 → 不推


def test_main_exit1_when_should_notify_but_not_sent(monkeypatch):
    """稽核 FINDING 1:正式跑(非 dry-run)有建議卻沒送出(缺憑證)→ exit 1(不得誤判成功)。"""
    _patch_main_common(monkeypatch, held=["AAA"], rich={"AAA": _rich("AAA")})
    import infra.line_push as LP
    import services.switch_advisor as SA
    import services.switch_notify as SN
    monkeypatch.setattr(SA, "advise_switches", lambda *a, **k: {"advices": [], "summary": {}, "caveat": ""})
    monkeypatch.setattr(SN, "build_notification",
                        lambda res, **k: {"should_notify": True, "message": "有", "n_actionable": 1})
    monkeypatch.setattr(LP, "push_text",
                        lambda msg, **k: {"sent": False, "reason": "缺 LINE_CHANNEL_TOKEN"})
    assert M.main([]) == 1                                  # 非 dry-run + 有建議 + 未送 → 失敗


def test_main_pool_code_case_normalized(monkeypatch):
    """稽核 FINDING 5:選股池小寫代碼與帳本大寫代碼須合一(不重複抓、對得到 type_override)。"""
    import repositories.pool_repository as P
    monkeypatch.setattr(M, "_load_client_and_sheet", lambda: ("c", "s"))
    monkeypatch.setattr(P, "list_pool", lambda: [_PE("b1234", type_override="震盪")])   # 小寫
    monkeypatch.setattr(M, "_read_holdings", lambda c, s: ["B1234"])                    # 大寫
    _got: dict = {}

    def _fr(codes):
        _got["codes"] = codes
        return {}
    monkeypatch.setattr(M, "_fetch_rich", _fr)
    M.main([])
    assert _got["codes"] == ["B1234"]                      # 合一,不出現 ['B1234','b1234']


def test_main_actionable_dry_run_pushes(monkeypatch):
    _patch_main_common(monkeypatch, held=["AAA"], rich={"AAA": _rich("AAA")})
    import services.switch_advisor as SA
    import services.switch_notify as SN
    import infra.line_push as LP
    monkeypatch.setattr(SA, "advise_switches", lambda *a, **k: {"advices": [], "summary": {}, "caveat": ""})
    monkeypatch.setattr(SN, "build_notification",
                        lambda res, **k: {"should_notify": True, "message": "有建議", "n_actionable": 1})
    _calls = []
    monkeypatch.setattr(LP, "push_text",
                        lambda msg, **k: _calls.append((msg, k)) or {"sent": False, "reason": "dry-run"})
    assert M.main(["--dry-run"]) == 0
    assert _calls and _calls[0][0] == "有建議" and _calls[0][1].get("dry_run") is True
