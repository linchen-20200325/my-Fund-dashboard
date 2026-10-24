"""PR1a 獨立稽核回修(2026-10-23 裁示 1B,3 必修 + 3 順手修)守衛。

必修 1:吃本金灰 dict 不是換標的訊號(Missing ≠ HOLD)。
必修 2:相對品質分「配息」因子走 SSOT(350 天窗口 + 配息閘門),短窗基金退出分母。
必修 3:`compute_dividend_twd_series` 不再產第二套三色吃本金燈。
順手 4:還原值無窗口天數 → unavailable `window_unknown`。
順手 5:吃本金 adr 缺時透傳 `resolve_dividend_rate_12m` 的 reason(nav_missing 原因要對)。
順手 6:配息紀錄存在但無一筆對齊淨值日 → 白話原因改講「無一筆對齊到淨值日」。
"""
from __future__ import annotations

import ast
import pathlib

import pandas as pd

from services.fund_total_return import (
    SRC_UNAVAILABLE_PREFIX,
    UNAVAILABLE_REASON_TEXT,
    resolve_1y_total_return,
)
from services.health.dividend import (
    EATING_STATUS_UNAVAILABLE,
    check_eating_principal_1y_mk,
    resolve_dividend_rate_12m,
)
from services.health.replacement import check_replacement_recommendation

_ROOT = pathlib.Path(__file__).resolve().parent.parent


# ── 必修 1 ─────────────────────────────────────────────────────────────────
def test_grey_eating_dict_is_not_a_signal_verdict_stays_unknown():
    """只有 wb05、無序列 / 無還原值 / 無其他指標 → 吃本金灰 dict → verdict 必須是 unknown,不是 keep。"""
    fd = {"metrics": {}, "moneydj_raw": {"moneydj_div_yield": 5.0}}
    eat = check_eating_principal_1y_mk(fd)
    assert eat is not None and eat["alert_level"] == "grey" and eat["eating_principal"] is None
    r = check_replacement_recommendation(fd, holding_years=2)
    assert r["verdict"] == "unknown" and r["emoji"] == "⬜", r
    assert r["triggered_rules"] == [] and r["observe_signals"] == []


def test_real_eating_verdict_still_counts_as_signal():
    """對照:真的判得出來(綠燈)→ 有訊號 → keep,不被上一條誤殺成 unknown。"""
    # DG-6（DEC-2026-10-24-12）：(1) 分類未判定 → ⬜ 不給換／留，故補可對應的基金類別；
    # (2) 「判不動時不得 🟢 保留」—— 原 fixture 無 Sharpe → 規則 (d) 判不動 → 不得 keep。
    # 本測試原本守的「真吃本金燈號算訊號（不走 no_signal 的 ⬜ 資料不足）」改由 status 斷言守住；
    # 補 Sharpe 後 4 規則都判得動 → 仍為 keep。
    fd = {"category": "全球股票型",
          "metrics": {"ret_1y_total": 9.0, "ret_1y_window_days": 365, "ret_1y_div_count": 12,
                      "annual_div_rate": 3.0}, "moneydj_raw": {}}
    r0 = check_replacement_recommendation(fd, holding_years=2)
    assert r0["verdict"] == "unknown" and r0["status"] == "rules_incomplete", r0
    fd["metrics"]["sharpe"] = 1.0
    r = check_replacement_recommendation(fd, holding_years=2)
    assert r["verdict"] == "keep", r


# ── 必修 2 ─────────────────────────────────────────────────────────────────
def _qfund(code, tr, wd, adr, sharpe=1.0):
    return {"code": code, "series": None, "dividends": [],
            "metrics": {"sharpe": sharpe, "std_1y": 10.0, "ret_1y_total": tr,
                        "ret_1y_window_days": wd, "annual_div_rate": adr},
            "moneydj_raw": {"mgmt_fee": 1.0}}


def test_quality_coverage_factor_excludes_short_window_funds():
    from services.fund_grp_health.quality import _assemble_factor_pcts
    funds = [_qfund("OK1", 12.0, 365, 6.0), _qfund("OK2", 6.0, 365, 6.0),
             _qfund("OK3", 3.0, 365, 6.0), _qfund("SHORT", 99.0, 200, 6.0)]
    pcts, n = _assemble_factor_pcts(funds, None)
    assert n == 4
    assert pcts["SHORT"]["配息"] is None, "200 天短窗的還原值不得進配息覆蓋分母"
    assert pcts["OK1"]["配息"] is not None and pcts["OK3"]["配息"] is not None
    assert pcts["OK1"]["配息"] < pcts["OK3"]["配息"]        # 覆蓋高 → percentile 小(0 最佳)


def test_quality_coverage_factor_excludes_dividend_gate_and_missing_adr():
    from services.fund_grp_health.quality import _assemble_factor_pcts
    gated = _qfund("GATE", 5.0, 365, 6.0)
    gated["metrics"]["ret_1y_div_count"] = 0            # 配息基金、窗內 0 筆 → unavailable
    gated["moneydj_raw"]["moneydj_div_yield"] = 6.0
    noadr = _qfund("NOADR", 5.0, 365, None)             # 配息率缺 → 退出分母
    funds = [_qfund("A", 12.0, 365, 6.0), _qfund("B", 6.0, 365, 6.0), gated, noadr]
    pcts, _ = _assemble_factor_pcts(funds, None)
    assert pcts["GATE"]["配息"] is None and pcts["NOADR"]["配息"] is None
    assert pcts["A"]["配息"] is not None


# ── 必修 3 ─────────────────────────────────────────────────────────────────
def test_dividend_twd_series_no_longer_emits_a_second_eating_light():
    from services.health.dividend_calc import compute_dividend_twd_series
    nav = {f"2024-{m:02d}-15": 10.0 for m in range(1, 13)}
    nav["2025-01-15"] = 10.0
    divs = [{"date": f"2024-{m:02d}-20", "amount": 0.08} for m in range(1, 13)]
    r = compute_dividend_twd_series(nav_series=nav, dividend_events=divs, fx_rate_default=1.0,
                                    fx_rate_by_date=None, principal_twd=1_000_000, warn_gap_pct=2.0)
    assert r["ok"] is True
    s = r["summary"]
    assert s["div_health_light_🧮"] is None and s["div_health_emoji_🧮"] is None
    # 數字本身保留(持有期相對買入成本的年化)
    assert s["annual_div_rate_pct_🧮"] is not None and s["ret_1y_total_pct_🧮"] is not None


def test_compute_dividend_twd_series_does_not_call_div_health_light_for_pair():
    src = (_ROOT / "services" / "health" / "dividend_calc.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "compute_dividend_twd_series")
    calls = {getattr(c.func, "id", getattr(c.func, "attr", None))
             for c in ast.walk(fn) if isinstance(c, ast.Call)}
    assert "div_health_light_for_pair" not in calls
    # 函式本體保留(portfolio_service 註解引用其規則)
    assert any(isinstance(n, ast.FunctionDef) and n.name == "div_health_light_for_pair"
               for n in ast.walk(tree))


# ── 順手 4 ─────────────────────────────────────────────────────────────────
def test_restored_value_without_window_days_is_window_unknown():
    r = resolve_1y_total_return({"metrics": {"ret_1y_total": 5.0}, "moneydj_raw": {}})
    assert r["status"] == "unavailable" and r["value_pct"] is None
    assert r["reason"] == "window_unknown" and r["window_days"] is None
    assert r["label"] == f"{SRC_UNAVAILABLE_PREFIX}（{UNAVAILABLE_REASON_TEXT['window_unknown']}）"
    out = check_eating_principal_1y_mk({"metrics": {"ret_1y_total": 5.0, "annual_div_rate": 6.0}})
    assert out["alert_level"] == "grey" and out["reason"] == "window_unknown"
    assert out["eating_principal"] is None and out["status"] == EATING_STATUS_UNAVAILABLE
    # v 缺時不受影響:仍是 no_series
    assert resolve_1y_total_return({"metrics": {}})["reason"] == "no_series"


# ── 順手 5 ─────────────────────────────────────────────────────────────────
def test_eating_adr_reason_is_passed_through_nav_missing():
    idx = pd.bdate_range("2026-01-05", periods=10)
    s = pd.Series([1.0] * 10, index=idx)
    fd = {"metrics": {}, "series": s,
          "dividends": [{"date": idx[-2].strftime("%Y-%m-%d"), "amount": 0.1}],
          "moneydj_raw": {}}              # 有配息紀錄、無 metrics.nav / nav_latest
    ar = resolve_dividend_rate_12m(fd)
    assert ar["status"] == "unavailable" and ar["reason"] == "nav_missing"
    out = check_eating_principal_1y_mk(fd)
    assert out["alert_level"] == "grey" and out["reason"] == "nav_missing", out
    assert out["_adr_pct"] is None and out["eating_principal"] is None
    assert "淨值" in out["message"]


# ── 順手 6 ─────────────────────────────────────────────────────────────────
def test_dividend_data_missing_text_says_unaligned_when_records_exist():
    base = {"ret_1y_total": 3.0, "ret_1y_window_days": 365, "ret_1y_div_count": 0}
    unaligned = resolve_1y_total_return(
        {"metrics": {**base, "annual_div_rate_div_count": 12}, "moneydj_div_yield": 5.0})
    plain = resolve_1y_total_return(
        {"metrics": {**base, "annual_div_rate_div_count": 0}, "moneydj_div_yield": 5.0})
    nokey = resolve_1y_total_return({"metrics": base, "moneydj_div_yield": 5.0})
    for r in (unaligned, plain, nokey):
        assert r["status"] == "unavailable" and r["reason"] == "dividend_data_missing"
    assert UNAVAILABLE_REASON_TEXT["dividend_data_missing_unaligned"] in unaligned["label"]
    assert UNAVAILABLE_REASON_TEXT["dividend_data_missing"] in plain["label"]
    assert UNAVAILABLE_REASON_TEXT["dividend_data_missing"] in nokey["label"]
