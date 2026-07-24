"""v19.402 §1 — 吃本金 verdict SSOT 收斂回歸測試(Phase 1)。

守住兩件事:
1. `tag_health_check` 的「吃本金」判定吃**含息總報酬**(compute_1y_total_return SSOT),
   而非純 NAV(`m['ret_1y']`)。修的是:同一檔基金在「單一基金」頁 KPI 橫幅顯示 🟢,
   但正下方警示框 / 戰情室卻 🔴 的自打臉 bug(根因:警示框餵純 NAV 進「應吃含息」的槽)。
2. `tag_principal_erosion` 正名:它其實是「淨值連續下跌動能」訊號,非配息覆蓋。
   verdict 文字不再用「吃本金」字樣,避免與真吃本金判定撞名。
"""
from __future__ import annotations

from ui.components.mk_dashboard import tag_health_check, _verdict_text


def _fund(*, perf_1y=None, ret_1y_total=None, ret_1y=None, div=6.0,
          sharpe=1.0, nav=10.0, ma60=9.0, ma20=9.5):
    """建 fund fixture。

    perf_1y 走 moneydj_raw.perf['1Y'](wb01 含息,compute_1y_total_return 最權威層)。
    ret_1y 為純 NAV(不含息),用來證明「吃本金」判定不再讀它。
    """
    mj = {}
    if perf_1y is not None:
        mj = {"perf": {"1Y": perf_1y}, "perf_source": "wb01"}
    return {
        "moneydj_raw": mj,
        "metrics": {
            "ret_1y_total": ret_1y_total,
            "ret_1y": ret_1y,
            "annual_div_rate": div,
            "sharpe": sharpe,
            "nav": nav, "ma60": ma60, "ma20": ma20,
        },
        "series": None,
    }


def test_health_check_uses_total_return_not_pure_nav_v19402():
    """純 NAV(ret_1y=3%)< 配息率 6%,但**含息總報酬**(perf 1Y=9%)> 配息率
    → 不該標 Warning(吃本金)。修前 bug:讀 ret_1y=3 → 假 Warning 🔴。"""
    f = _fund(perf_1y=9.0, ret_1y=3.0, div=6.0)
    assert tag_health_check(f) == "Healthy"


def test_health_check_genuine_eating_warning_v19402():
    """含息總報酬(perf 1Y=2%)< 配息率 6% → 真吃本金 → Warning(正確 🔴)。"""
    f = _fund(perf_1y=2.0, ret_1y=3.0, div=6.0)
    assert tag_health_check(f) == "Warning"


def test_health_check_missing_total_return_na_v19402():
    """無 perf / ret_1y_total / ret_1y → 無含息總報酬 → 誠實 N/A,不假判定(§1)。"""
    f = _fund(perf_1y=None, ret_1y_total=None, ret_1y=None, div=6.0)
    assert tag_health_check(f) == "N/A"


def test_health_check_sharpe_warning_still_wins_v19402():
    """夏普<0 仍優先回 Sharpe_Warning(§1 修未動到 A 條)。"""
    f = _fund(perf_1y=9.0, div=6.0, sharpe=-0.5)
    assert tag_health_check(f) == "Sharpe_Warning"


def test_principal_erosion_verdict_relabeled_no_eating_wording_v19402():
    """tag_principal_erosion="Eroding" → verdict 正名為淨值動能,不再用「吃本金」。"""
    txt = _verdict_text("Core", "Healthy", "OK", "zone", principal="Eroding")
    assert "吃本金" not in txt
    assert ("動能" in txt) or ("下跌" in txt)
