"""BL-0440 補修第二批:ladder235 σ=0 誤標 + Tab3「σ+布林雙確認」徽章缺值靜默。

客戶裁示 DEC-2026-10-24-02(PROJECT_RULES §13.1):Missing ≠ 未觸發／Hold／0。
本檔只驗「既有 status／既有欄位 → 誠實文字」,不新增公式、門檻、規則。

大型 render 函式不跑 streamlit:用 AST 從原始碼抽出修補點本體(dict 字面值／徽章那段
if-elif 鏈)再執行,所以測到的是**實際上線的那幾行**,不是平行複寫的邏輯。
"""
from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
# BL-0441(DEC-2026-10-24-09):類別缺值 → 未判定不給燈;本檔 ladder 測試一律明示非 Core 類別
_NON_CORE = "科技股票型"


def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# ════════════════════════════════════════════════════════════
# 1. ladder235:σ=0(degenerate)vs 週資料不足(insufficient)
# ════════════════════════════════════════════════════════════
def _daily(values, start="2024-01-01"):
    idx = pd.bdate_range(start, periods=len(values))
    return pd.Series(values, index=idx, dtype=float)


def _ladder_label_fn():
    """抽出 tab_fund_grp_health.py 裡「lamp is None → 加碼水位文字」那個 dict 與 fallback。"""
    tree = ast.parse(_src("ui/tab_fund_grp_health.py"))
    hits = []
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "get" and isinstance(n.func.value, ast.Dict)):
            keys = [ast.literal_eval(k) for k in n.func.value.keys]
            if "core" in keys and "lowvol" in keys:
                hits.append(n)
    assert len(hits) == 1, f"加碼水位標籤 dict 應恰好 1 處,實得 {len(hits)}"
    mapping = ast.literal_eval(hits[0].func.value)
    fallback = ast.literal_eval(hits[0].args[1])
    return lambda status: mapping.get(status, fallback)


def test_ladder_constant_series_is_degenerate_not_insufficient():
    from services.ladder235 import ladder_signal
    r = ladder_signal(_daily([10.0] * 300), category=_NON_CORE)
    assert r["status"] == "degenerate"
    # BL-0443(4):未給燈的 deploy_pct 由 0.0 改 None(未判定 ≠ 0% 加碼)
    assert r["lamp"] is None and r["deploy_pct"] is None and r["weeks"] >= 20


def test_ladder_short_series_is_insufficient():
    from services.ladder235 import ladder_signal
    r = ladder_signal(_daily([10.0 + 0.1 * i for i in range(30)]), category=_NON_CORE)   # 約 6 週
    assert r["status"] == "insufficient"
    # BL-0443(4):未給燈的 deploy_pct 由 0.0 改 None(未判定 ≠ 0% 加碼)
    assert r["lamp"] is None and r["deploy_pct"] is None


def test_ladder_none_series_is_insufficient():
    from services.ladder235 import ladder_signal
    r = ladder_signal(None, category=_NON_CORE)
    assert r["status"] == "insufficient" and r["weeks"] == 0


def test_ui_label_degenerate_vs_insufficient_distinguishable():
    label = _ladder_label_fn()
    assert label("degenerate") == "⬜ 波動為 0，無法判定"
    assert label("insufficient") == "⬜ 週資料不足"
    assert label("degenerate") != label("insufficient")
    # 既有兩個狀態用字不變
    assert label("core") == "⚪ 不適用(內建配置)"
    assert label("lowvol") == "⬜ 低波不判"


def test_ui_label_end_to_end_constant_and_short_series():
    from services.ladder235 import ladder_signal
    label = _ladder_label_fn()
    assert label(ladder_signal(_daily([10.0] * 300), category=_NON_CORE)["status"]) == "⬜ 波動為 0，無法判定"
    assert label(ladder_signal(_daily([10.0 + 0.1 * i for i in range(30)]), category=_NON_CORE)["status"]) == "⬜ 週資料不足"


def test_ladder_normal_series_still_lamps_and_unchanged_zero_tolerance():
    """可判定的正常序列仍給燈(ok);σ 判斷式原樣保留(未改容差)。"""
    from services.ladder235 import ladder_signal
    rng = np.random.default_rng(7)
    s = _daily(list(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 400)))))
    r = ladder_signal(s, category=_NON_CORE)
    assert r["status"] == "ok" and r["lamp"] is not None
    assert "if not (sigma > 0):" in _src("services/ladder235.py")


# ════════════════════════════════════════════════════════════
# 2. Tab3 迷你卡「σ+布林雙確認」徽章
# ════════════════════════════════════════════════════════════
def _badge_snippet() -> str:
    """從 tab3_portfolio.py 取出「# 雙確認」到「# 6 個訊號方塊」之間的原始碼(上線那幾行)。"""
    lines = _src("ui/tab3_portfolio.py").splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.strip() == "# 雙確認：σ 觸發 + 布林同向")
    end = next(i for i in range(start, len(lines)) if lines[i].strip().startswith("# 6 個訊號方塊"))
    return textwrap.dedent("\n".join(lines[start + 1:end]))


_COLOR_NAMES = ("BG_DARK_GREEN_3", "MD_GREEN_A400", "BG_DARK_RED_3", "MATERIAL_RED",
                "CHIP_BG_NEAR_BLACK", "GRAY_66")


def _badge(nav, b1, s1, bbd, bbu) -> str:
    ns = {"pd": pd, "_mi_nav": nav, "_mi_b1": b1, "_mi_s1": s1,
          "_mi_bbd": bbd, "_mi_bbu": bbu, **{c: "#000" for c in _COLOR_NAMES}}
    exec(compile(_badge_snippet(), "tab3_badge", "exec"), ns)   # noqa: S102 — 測上線原始碼片段
    return ns["_badge"]


UNDECIDABLE = "⬜ 雙確認無法判定（布林資料未取得）"


@pytest.mark.parametrize("bbd,bbu", [
    (None, 110.0), (90.0, None), (None, None),
    (float("nan"), 110.0), (90.0, float("nan")),
])
def test_badge_bb_missing_is_undecidable_not_silent(bbd, bbu):
    # σ 未觸發(nav 介於買1、賣1 之間)也不得與「未觸發」一樣空白
    b = _badge(100.0, 95.0, 105.0, bbd, bbu)
    assert b != ""
    assert UNDECIDABLE in b and "雙確認買" not in b and "雙確認賣" not in b


def test_badge_not_triggered_unchanged_empty():
    assert _badge(100.0, 95.0, 105.0, 90.0, 110.0) == ""
    # σ 觸發但布林未同向 → 仍是未觸發(空白),行為不變
    assert _badge(94.0, 95.0, 105.0, 90.0, 110.0) == ""


def test_badge_triggered_unchanged():
    buy = _badge(89.0, 95.0, 105.0, 90.0, 110.0)
    assert "🟢🟢 σ+布林 雙確認買" in buy and UNDECIDABLE not in buy
    sell = _badge(111.0, 95.0, 105.0, 90.0, 110.0)
    assert "🔔🔔 σ+布林 雙確認賣" in sell and UNDECIDABLE not in sell
    # 已觸發的一側優先;另一側布林缺不蓋掉已成立的雙確認
    assert "雙確認買" in _badge(89.0, 95.0, 105.0, 90.0, None)


def test_badge_missing_and_not_triggered_are_different_states():
    assert _badge(100.0, 95.0, 105.0, None, 110.0) != _badge(100.0, 95.0, 105.0, 90.0, 110.0)


# ════════════════════════════════════════════════════════════
# 3. Missing ≠ 未觸發／Hold／0:跨入口精確值總表(正常可判定案例同列,證明未被改動)
# ════════════════════════════════════════════════════════════
_LV = dict(buy1=95.0, buy3=85.0, sell1=105.0, sell3=115.0)


@pytest.mark.parametrize("metrics,expect", [
    ({"nav": 100.0}, "⬜ 無法判定（買1／賣1未取得）"),        # Missing
    ({"nav": 100.0, **_LV}, "⚪ 區間內"),                     # 正常
    ({"nav": 94.0, **_LV}, "🟢 ≤買1(小跌)"),
    ({"nav": 80.0, **_LV}, "🟢 ≤買3(深跌)"),
    ({"nav": 106.0, **_LV}, "🟡 ≥賣1(小漲)"),
    ({"nav": 120.0, **_LV}, "🔴 ≥賣3(大漲)"),
    (dict(_LV), "—"),                                          # 淨值缺
])
def test_matrix_grp_health_zone_exact(metrics, expect):
    from services.fund_grp_health.signals import mk_signal_by_code
    out = mk_signal_by_code([{"code": "X", "metrics": metrics, "moneydj_raw": {}}], "", None)
    assert out["X"]["現價位階"] == expect


def test_matrix_missing_zone_not_equal_any_decidable():
    from services.fund_grp_health.signals import mk_signal_by_code
    def z(m):
        return mk_signal_by_code([{"code": "X", "metrics": m, "moneydj_raw": {}}], "", None)["X"]["現價位階"]
    miss = z({"nav": 100.0})
    for m in ({"nav": 100.0, **_LV}, {"nav": 94.0, **_LV}, {"nav": 106.0, **_LV}):
        assert miss != z(m)


@pytest.mark.parametrize("m,expect", [
    ({"nav": 100.0}, "N/A"),
    ({"nav": None, "buy1": 95.0, "bb_upper": 110.0}, "N/A"),
    ({"nav": float("nan"), "buy1": 95.0, "bb_upper": 110.0}, "N/A"),
    ({"nav": 100.0, "buy1": 95.0, "buy2": 90.0, "bb_upper": 110.0}, "Hold"),
    ({"nav": 94.0, "buy1": 95.0, "buy2": 90.0, "bb_upper": 110.0}, "Buy_Zone"),
    ({"nav": 111.0, "buy1": 95.0, "buy2": 90.0, "bb_upper": 110.0}, "Take_Profit"),
])
def test_matrix_price_zone_missing_is_not_hold(m, expect):
    from ui.components.mk_dashboard import tag_price_zone
    assert tag_price_zone({"metrics": m}) == expect


def test_matrix_kpi_missing_is_none_not_zero_and_true_zero_is_zero():
    from ui.helpers.portfolio.health import compute_health_kpis
    funds = [{"code": "A", "loaded": True, "metrics": {}}]
    miss = compute_health_kpis(funds, None)
    assert (miss["n_buy"], miss["n_take"], miss["n_warn"]) == (None, None, None)
    df = pd.DataFrame([{"MK_Class": "Core", "Price_Zone": "Hold",
                        "Health_Check": "Healthy", "Principal_Erosion": "OK"}])
    zero = compute_health_kpis(funds, df)
    assert (zero["n_buy"], zero["n_take"], zero["n_warn"]) == (0, 0, 0)
    assert zero["n_zone_na"] == 0
