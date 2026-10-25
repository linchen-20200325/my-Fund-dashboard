"""BL-0449 / BL-0450 / BL-0451(2026-10-25 客戶授權):Missing / Error 不得變成 0 / False / 安全。

- BL-0449:App 端換股區 `_underperf_by_code` 吃本金判定例外 → 補 log,退值 "" 不變,
  且 "" 不被當成「沒有吃本金」(不會變紅燈、也不會變成任何「健康」字樣)。
- BL-0450:紅燈三態 —— RED → True、明確非紅 → False、GRAY(資料不足)→ None;
  App helper 與週報 script 兩個呼叫端都覆蓋;`is_underperforming` 判法不變。
- BL-0451:T7 帳本 KPI 組合總報酬率,總成本 ≤0 / 缺 → None(⬜),真 0 損益仍為 0.00%。

重依賴全 monkeypatch,不觸網。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fund_fetcher  # noqa: F401,E402  (prime 既有 latent 互 import,同 test_weekly_switch_notify)


# ───────────────────────── 共用 fixture:三種紅燈情境 ─────────────────────────
# A 紅:含息 1Y < 0 且 Sharpe < 0 → switch_signal RED
# B 明確非紅:含息 > 0、Sharpe > 0 → 🟢/🟡
# C 資料缺:Sharpe 缺 → switch_signal GRAY
_CASES = {
    "A": dict(tr=-3.0, sharpe=-0.5, expect=True),
    "B": dict(tr=5.0, sharpe=1.0, expect=False),
    "C": dict(tr=5.0, sharpe=None, expect=None),
}


def _funds():
    return [{"code": k, "currency": "USD", "metrics": {"sharpe": v["sharpe"]}, "risk_metrics": {}}
            for k, v in _CASES.items()]


def _patch_common(monkeypatch, capture_mod, eat=lambda f: {"status": "🟢 健康"}):
    import services.fund_total_return as T
    import services.health.dividend as D
    monkeypatch.setattr(capture_mod, "capture_by_code",
                        lambda funds: {k: {"vs 大盤%": 1.0, "vs 大盤期間": "近1年"} for k in _CASES})
    monkeypatch.setattr(T, "compute_1y_total_return", lambda f: (_CASES[f["code"]]["tr"], ""))
    monkeypatch.setattr(D, "check_eating_principal_1y_mk", eat)


def _app_under(monkeypatch, **kw):
    import ui.helpers.fund_grp_health.capture as C
    from ui.helpers.fund_grp_health import switch_advisor_section as S
    _patch_common(monkeypatch, C, **kw)
    return S._underperf_by_code(_funds())


def _script_under(monkeypatch, **kw):
    import services.fund_grp_health.capture as C
    from scripts import weekly_switch_notify as M
    _patch_common(monkeypatch, C, **kw)
    return M._underperf_by_code(_funds())


# ───────────────────────── BL-0450 ─────────────────────────

def test_redlight_from_signal_tristate():
    from services.switch_advisor import redlight_from_signal
    from services.switch_strategy import GRAY, GREEN, RED, YELLOW
    assert redlight_from_signal(RED, "") is True
    assert redlight_from_signal(GREEN, "🟢 健康") is False
    assert redlight_from_signal(YELLOW, "") is False
    assert redlight_from_signal(GRAY, "") is None
    # eat_is_red 的 OR 語意保留:吃本金紅 → True,即使燈號為 GRAY
    assert redlight_from_signal(GRAY, "🔴 吃本金") is True


@pytest.mark.parametrize("runner", [_app_under, _script_under], ids=["app", "script"])
def test_redlight_tristate_both_callers(monkeypatch, runner):
    out = runner(monkeypatch)
    for k, v in _CASES.items():
        assert out[k]["redlight"] is v["expect"], k
    # is_underperforming 判法不變:只有 A 觸發;None(C)與 False(B)都不觸發
    assert out["A"]["is_underperforming"] is True
    assert out["B"]["is_underperforming"] is False
    assert out["C"]["is_underperforming"] is False
    # C 不得被記成確認非紅
    assert out["C"]["redlight"] is not False


def test_assess_recompute_does_not_wash_none_back_to_false():
    """呼叫端傳 redlight=None 且吃本金燈號非空時,assess 重算不得把 GRAY 洗回 False。"""
    from services.switch_advisor import assess_underperformance
    u = assess_underperformance(excess_pct=1.0, eat_status="🟢 健康", redlight=None)
    assert u["redlight"] is None and u["is_underperforming"] is False


def test_gray_row_disclosed_in_underperf_column(monkeypatch):
    """C(資料缺)在表現差欄顯示 ⬜ 絕對虧損未判定,不是「—」。"""
    out = _app_under(monkeypatch)
    from ui.helpers.fund_grp_health import switch_advisor_section as S
    import inspect
    src = inspect.getsource(S._render_advice)
    assert out["C"]["redlight"] is None and not out["C"]["is_underperforming"]
    assert '"⬜ 絕對虧損未判定"' in src and 'u.get("redlight") is None' in src
    # help 已加回「資料不足」(BL-0450)
    assert "這一半資料不足、計算失敗或未評估" in src


# ───────────────────────── BL-0449 ─────────────────────────

def test_app_eat_success_path_unchanged(monkeypatch):
    out = _app_under(monkeypatch, eat=lambda f: {"status": "🔴 吃本金"})
    # plain 吃本金紅 → 三檔都紅(OR 語意)
    assert all(out[k]["redlight"] is True for k in _CASES)


def test_app_eat_failure_logs_and_stays_missing(monkeypatch, capsys):
    def _boom(f):
        raise ValueError("secret-ish detail")
    out = _app_under(monkeypatch, eat=_boom)
    err = capsys.readouterr().err
    for k in _CASES:
        assert f"{k} 吃本金判定失敗:ValueError" in err
    assert "secret-ish detail" not in err          # 只記例外類別(同週報慣例)
    # 退值 "" 不變:不會變紅、不帶任何吃本金 reason
    for k in ("B", "C"):
        assert not any("吃本金" in r for r in out[k]["reasons"])
    # C 仍為 Missing(None),不是確認非紅
    assert out["C"]["redlight"] is None


# ───────────────────────── BL-0451 ─────────────────────────

@pytest.mark.parametrize("pl,cost,expect", [
    (100.0, 1000.0, 10.0),
    (-50.0, 1000.0, -5.0),
    (0.0, 1000.0, 0.0),
])
def test_t7_total_return_pct_positive_cost(pl, cost, expect):
    from ui.tab3_t7_ledger import _t7_total_return_pct
    v = _t7_total_return_pct(pl, cost)
    assert v is not None and abs(v - expect) < 1e-12


def test_t7_true_zero_renders_0_00():
    from ui.tab3_t7_ledger import _t7_total_return_pct
    v = _t7_total_return_pct(0.0, 1000.0)
    assert f"{v:+.2f}%" == "+0.00%"


@pytest.mark.parametrize("pl,cost", [(0.0, 0.0), (10.0, -5.0), (10.0, None),
                                     (10.0, float("nan")), (None, 100.0)])
def test_t7_total_return_pct_unable(pl, cost):
    from ui.tab3_t7_ledger import _t7_total_return_pct
    v = _t7_total_return_pct(pl, cost)
    assert v is None
    assert v != 0.0                                  # 算不出來 ≠ 真 0


def test_t7_kpi_uses_helper_and_discloses():
    src = (Path(__file__).resolve().parents[1] / "ui/tab3_t7_ledger.py").read_text(encoding="utf-8")
    assert "_pl_total_pct = _t7_total_return_pct(_pl_total, _cost_total_twd)" in src
    assert "⬜ 報酬率無法計算（總成本基礎 ≤0）" in src
