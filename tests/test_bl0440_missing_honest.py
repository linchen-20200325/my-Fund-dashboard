"""BL-0440:Missing 誠實揭露 + UI 重算收斂 + fallback 品質揭露。

客戶裁示 DEC-2026-10-24-02(PROJECT_RULES §13.1):不得把 Missing 轉成 0／中性／HOLD／
安全／未觸發。本檔對每一處修補各測四種輸入(適用者):
  Missing(缺) / 真 0(若適用) / 正常有效值 / fallback 值(`buy_mode` = 區間σ(資料不足)),
並斷言 Missing 永遠不落到可判定的狀態(Hold／區間內／正常／0 檔／未觸發)。

不新增買賣規則、門檻、公式;只驗「缺 → 明講無法判定」與「fallback → 揭露品質」。
"""
from __future__ import annotations

import ast
import importlib.util
import math
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]

from shared.data_quality import BUY_MODE_RANGE_FALLBACK  # noqa: E402

FB = BUY_MODE_RANGE_FALLBACK
DECIDABLE_ZONE_WORDS = ("區間內", "Hold", "正常", "未觸發")


# ════════════════════════════════════════════════════════════
# a. 健診大表「現價位階」 services/fund_grp_health/signals.py::mk_signal_by_code
# ════════════════════════════════════════════════════════════
def _zone(metrics: dict, mj: dict | None = None) -> str:
    from services.fund_grp_health.signals import mk_signal_by_code
    out = mk_signal_by_code([{"code": "X", "metrics": metrics, "moneydj_raw": mj or {}}], "", None)
    return out["X"]["現價位階"]


_LEVELS = dict(buy1=95.0, buy3=85.0, sell1=105.0, sell3=115.0)


def test_a_all_levels_missing_with_nav_is_undecidable_not_in_range():
    z = _zone({"nav": 100.0})
    assert z == "⬜ 無法判定（買1／賣1未取得）"
    assert not any(w in z for w in DECIDABLE_ZONE_WORDS)


@pytest.mark.parametrize("drop", ["buy1", "sell1"])
def test_a_missing_b1_or_s1_cannot_claim_in_range(drop):
    m = {"nav": 100.0, **_LEVELS}
    m.pop(drop)
    z = _zone(m)
    assert z == "⬜ 無法判定（買1／賣1未取得）", z


def test_a_normal_value_in_range_and_outer_bands_still_decidable():
    assert _zone({"nav": 100.0, **_LEVELS}) == "⚪ 區間內"
    assert _zone({"nav": 80.0, **_LEVELS}) == "🟢 ≤買3(深跌)"
    # 買1 缺,但已低於買3 —— 外側仍可判定,不被誤標無法判定
    m = {"nav": 80.0, **_LEVELS}
    m.pop("buy1")
    assert _zone(m) == "🟢 ≤買3(深跌)"


def test_a_nav_missing_stays_dash():
    assert _zone(dict(_LEVELS)) == "—"


def test_a_fallback_buy_mode_disclosed():
    z = _zone({"nav": 100.0, **_LEVELS, "buy_mode": FB})
    assert z.startswith("⚪ 區間內") and "區間σ·資料不足" in z
    # 正常模式不加註
    assert "資料不足" not in _zone({"nav": 100.0, **_LEVELS, "buy_mode": "淨值σ通道"})


def test_a_ui_wrapper_same_output():
    """UI 入口(注入 mk_fund_signal)與 L2 版位階輸出一致。"""
    from ui.helpers.fund_grp_health.signals import mk_signal_by_code as ui_fn
    out = ui_fn([{"code": "X", "metrics": {"nav": 100.0}, "moneydj_raw": {}}], "", None)
    assert out["X"]["現價位階"] == "⬜ 無法判定（買1／賣1未取得）"


# ════════════════════════════════════════════════════════════
# b. 戰情室 tag_price_zone / _verdict_text
# ════════════════════════════════════════════════════════════
def _pz(m):
    from ui.components.mk_dashboard import tag_price_zone
    return tag_price_zone({"metrics": m})


@pytest.mark.parametrize("m", [
    {"nav": 100.0},
    {"nav": 100.0, "buy1": 95.0},                  # bb_upper 缺
    {"nav": 100.0, "bb_upper": 110.0},             # buy1 缺
    {"nav": 100.0, "buy1": float("nan"), "bb_upper": 110.0},
    {"nav": 100.0, "buy1": 95.0, "bb_upper": float("nan")},
])
def test_b_missing_buy1_or_bb_upper_is_na_not_hold(m):
    assert _pz(m) == "N/A"


def test_b_normal_values():
    base = {"nav": 100.0, "buy1": 95.0, "buy2": 90.0, "bb_upper": 110.0}
    assert _pz(base) == "Hold"
    assert _pz({**base, "nav": 94.0}) == "Buy_Zone"
    assert _pz({**base, "nav": 89.0}) == "Buy_Zone_Deep"
    assert _pz({**base, "nav": 111.0}) == "Take_Profit"
    # 缺 buy1 但已破 buy2 → 仍可判定
    assert _pz({"nav": 89.0, "buy2": 90.0}) == "Buy_Zone_Deep"


def test_b_verdict_na_zone_does_not_claim_hold():
    from ui.components.mk_dashboard import _verdict_text
    for cls in ("Core", "Satellite"):
        v = _verdict_text(cls, "Healthy", "OK", "N/A")
        assert v == {"Core": "✅ 核心健康（⬜ 價位區間無法判定）",
                     "Satellite": "✅ 衛星健康（⬜ 價位區間無法判定）"}[cls]
        assert "續抱" not in v and "等待訊號" not in v
    # 既有語意不變
    assert _verdict_text("Core", "Healthy", "OK", "Hold") == "✅ 核心健康，續抱領息"
    assert _verdict_text("Satellite", "Healthy", "OK", "Hold") == "✅ 衛星健康，等待訊號"
    # 紅燈仍優先
    assert _verdict_text("Core", "Sharpe_Warning", "OK", "N/A").startswith("🔴")


# ════════════════════════════════════════════════════════════
# c. 首頁 KPI compute_health_kpis / render_hero_kpi_cards
# ════════════════════════════════════════════════════════════
def _funds(n=2):
    return [{"code": f"F{i}", "loaded": True, "metrics": {}} for i in range(n)]


@pytest.mark.parametrize("mk_df", [None, pd.DataFrame()])
def test_c_tag_table_unavailable_is_none_not_zero(mk_df):
    from ui.helpers.portfolio.health import compute_health_kpis
    k = compute_health_kpis(_funds(), mk_df)
    assert k["n_buy"] is None and k["n_warn"] is None and k["n_take"] is None
    assert k["tags_unavailable"] is True


def test_c_true_zero_stays_zero_and_na_disclosed():
    from ui.helpers.portfolio.health import compute_health_kpis
    df = pd.DataFrame([
        {"MK_Class": "Core", "Price_Zone": "Hold", "Health_Check": "Healthy", "Principal_Erosion": "OK"},
        {"MK_Class": "Satellite", "Price_Zone": "N/A", "Health_Check": "Healthy", "Principal_Erosion": "OK"},
    ])
    k = compute_health_kpis(_funds(), df)
    assert k["n_buy"] == 0 and k["n_take"] == 0 and k["n_warn"] == 0   # 真 0
    assert k["n_zone_na"] == 1
    assert not k.get("tags_unavailable")


def test_c_empty_portfolio_keeps_zero_contract():
    from ui.helpers.portfolio.health import compute_health_kpis
    k = compute_health_kpis([], None)
    assert k["n_buy"] == 0 and k["n_funds"] == 0


class _Col:
    def __init__(self, log):
        self.log = log

    def metric(self, label, value, **kw):
        self.log.append((label, value, kw.get("help", "")))


def _render(kpis, monkeypatch):
    import streamlit as st
    log: list = []
    monkeypatch.setattr(st, "columns", lambda n: [_Col(log) for _ in range(n)], raising=False)
    monkeypatch.setattr(st, "info", lambda *a, **k: log.append(("info", a)), raising=False)
    from ui.helpers.portfolio.health import render_hero_kpi_cards
    render_hero_kpi_cards(kpis)
    return {r[0]: r for r in log if len(r) == 3}


def test_c_render_shows_undecidable_not_zero(monkeypatch):
    from ui.helpers.portfolio.health import compute_health_kpis
    k = compute_health_kpis(_funds(), None)
    rows = _render(k, monkeypatch)
    for lbl in ("🟢 撿便宜雷達", "🔴 留校查看", "💰 停利提醒"):
        assert rows[lbl][1] == "⬜ 無法判定", rows[lbl]
        assert "0 檔" not in rows[lbl][1]


def test_c_render_true_zero_and_na_help(monkeypatch):
    k = {"n_funds": 2, "n_na": 0, "n_cash_ok": 2, "n_eat": 0, "ratio_label": "—",
         "ratio_delta": None, "n_buy": 0, "n_warn": 0, "n_take": 0, "n_zone_na": 1}
    rows = _render(k, monkeypatch)
    assert rows["🟢 撿便宜雷達"][1] == "0 檔"
    assert "1 檔" in rows["🟢 撿便宜雷達"][2] and "無法判定" in rows["🟢 撿便宜雷達"][2]


# ════════════════════════════════════════════════════════════
# d. 體檢 PK 表「買點」
# ════════════════════════════════════════════════════════════
def test_d_hold_and_na_distinguishable():
    from ui.helpers.fund.checkup import _zone_cell, _ZONE_LABEL
    na = _zone_cell({"metrics": {"nav": 100.0}})
    hold = _zone_cell({"metrics": {"nav": 100.0, "buy1": 95.0, "bb_upper": 110.0}})
    assert na == "⬜ 無法判定"
    assert hold == "⚪ 未觸發"
    assert na != hold
    assert _ZONE_LABEL["Hold"] != _ZONE_LABEL["N/A"]
    assert "—" not in (_ZONE_LABEL["Hold"], _ZONE_LABEL["N/A"])


def test_d_normal_and_fallback():
    from ui.helpers.fund.checkup import _zone_cell
    m = {"nav": 94.0, "buy1": 95.0, "buy2": 90.0, "bb_upper": 110.0}
    assert _zone_cell({"metrics": m}) == "🟢 便宜(-1σ)"
    fb = _zone_cell({"metrics": {**m, "buy_mode": FB}})
    assert fb.startswith("🟢 便宜(-1σ)") and "區間σ·資料不足" in fb


# ════════════════════════════════════════════════════════════
# g. Tab2 −2σ 卡:SSOT bb_lower 與 UI 重算公式逐項相同
# ════════════════════════════════════════════════════════════
def _ensure_schemas_importable(monkeypatch):
    """CI 有 pandera,走真的 shared.schemas;本機缺 pandera 時只打樁那兩個 data-only validator。"""
    if importlib.util.find_spec("pandera") is not None:
        return
    stub = types.ModuleType("shared.schemas")
    stub.validate_fund_nav_data_only = lambda s: s
    stub.validate_fund_dividends_data_only = lambda d: d
    monkeypatch.setitem(sys.modules, "shared.schemas", stub)


@pytest.mark.parametrize("n", [8, 19, 25, 300])
def test_g_ssot_bb_lower_equals_ui_formula_rounded(monkeypatch, n):
    _ensure_schemas_importable(monkeypatch)
    import fund_fetcher  # noqa: F401  (先 prime,避開 fund_service ↔ fund_fetcher 既有循環)
    from services.fund_service import calc_metrics
    idx = pd.bdate_range("2025-01-01", periods=n)
    s = pd.Series([10 + 0.37 * math.sin(i / 3.0) + 0.01 * i for i in range(n)], index=idx)
    m = calc_metrics(s, [])
    _p = min(20, len(s))
    ui_dn = (s.rolling(_p).mean() - 2 * s.rolling(_p).std()).dropna()
    assert m["bb_lower"] == pytest.approx(round(float(ui_dn.iloc[-1]), 4), abs=1e-12)
    # n<20 的 σ 通道走 fallback,buy_mode 必須是同一個具名常數(下游靠它揭露)
    if n < 20:
        assert m["buy_mode"] == FB


# ════════════════════════════════════════════════════════════
# e / g / h / i:大型 render 函式 —— 用 AST/原始碼鎖住修補點(不跑 streamlit)
# ════════════════════════════════════════════════════════════
def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_e_tab3_mini_card_no_default_normal():
    t = _src("ui/tab3_portfolio.py")
    assert 'm_i.get("pos_label","正常")' not in t
    assert 'm_i.get("pos_label") or "⬜ 無法判定"' in t
    assert "策略3 訊號：⬜ 無法判定" in t
    assert "_BUY_MODE_FALLBACK_T3" in t


def test_g_h_tab2_reads_ssot_and_discloses_missing():
    t = _src("ui/tab2_single_fund.py")
    assert "float(_bb_dn.iloc[-1])" not in t, "−2σ 卡不得再讀 UI 重算的 _bb_dn"
    assert '_boll_latest_low = _safe_float(m.get("bb_lower"))' in t
    assert "-2σ 超跌機會卡：⬜ 無法判定" in t
    assert "標準差買賣點：⬜ 無法判定" in t
    assert "_BUY_MODE_FALLBACK_T2" in t
    ast.parse(t)


def test_i_ai_prompts_disclose_missing():
    t2 = _src("ui/tab2_single_fund.py")
    assert "買賣點/技術資料未取得（不得推測）" in t2
    t3 = _src("ui/tab3_portfolio.py")
    tree = ast.parse(t3)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_render_tab3_ai_summary")
    # 該函式內不得再有「except: pass」(BL-0440 i 修補點)
    for h in ast.walk(fn):
        if isinstance(h, ast.ExceptHandler):
            assert not (len(h.body) == 1 and isinstance(h.body[0], ast.Pass)), \
                f"_render_tab3_ai_summary:{h.lineno} 仍是 except: pass"
    seg = ast.get_source_segment(t3, fn)
    assert "無法判定（資料未取得，不得推測）" in seg


def test_fallback_constant_is_the_value_calc_metrics_writes():
    """常數收口不改值:calc_metrics 寫入的字串仍是原本的「區間σ(資料不足)」。"""
    assert FB == "區間σ(資料不足)"
    t = _src("services/fund_service.py")
    assert "buy_mode     = BUY_MODE_RANGE_FALLBACK" in t


# ════════════════════════════════════════════════════════════
# 稽核回修 N1 / N2 / N4
# ════════════════════════════════════════════════════════════
def test_n1_nav_nan_is_na_not_hold():
    base = {"buy1": 95.0, "buy2": 90.0, "bb_upper": 110.0}
    assert _pz({**base, "nav": float("nan")}) == "N/A"
    assert _pz({**base, "nav": None}) == "N/A"
    assert _pz({**base, "nav": 100.0}) == "Hold"          # 正常值不受影響


def _mk(zones, cls="Satellite"):
    return pd.DataFrame([{"MK_Class": cls, "Price_Zone": z, "Health_Check": "Healthy",
                          "Principal_Erosion": "OK"} for z in zones])


def test_n2_all_zone_na_is_undecidable_not_zero(monkeypatch):
    from ui.helpers.portfolio.health import compute_health_kpis
    k = compute_health_kpis(_funds(), _mk(["N/A", "N/A"]))
    assert k["n_buy"] is None and k["n_take"] is None and k["zone_all_na"] is True
    assert k["n_warn"] == 0          # 留校查看不由價位區間推得
    rows = _render(k, monkeypatch)
    assert rows["🟢 撿便宜雷達"][1] == "⬜ 無法判定"
    assert rows["💰 停利提醒"][1] == "⬜ 無法判定"
    assert "2 檔" in rows["🟢 撿便宜雷達"][2]          # help 保留 N/A 檔數


def test_n2_partial_zone_na_keeps_counts_with_disclosure(monkeypatch):
    from ui.helpers.portfolio.health import compute_health_kpis
    k = compute_health_kpis(_funds(), _mk(["N/A", "Take_Profit"]))
    assert k["n_buy"] == 0 and k["n_take"] == 1 and not k.get("zone_all_na")
    rows = _render(k, monkeypatch)
    assert rows["🟢 撿便宜雷達"][1] == "0 檔" and "1 檔" in rows["🟢 撿便宜雷達"][2]


@pytest.mark.parametrize("nav,expect", [
    (100.0, "⚪ 未觸發"), (111.0, "🟠 停利(+2σ)"), (94.0, "🟢 便宜(-1σ)")])
def test_n4_checkup_fallback_note_on_every_decidable_zone(nav, expect):
    from ui.helpers.fund.checkup import _zone_cell
    m = {"nav": nav, "buy1": 95.0, "buy2": 90.0, "bb_upper": 110.0}
    assert _zone_cell({"metrics": m}) == expect                     # 正常模式不加註
    fb = _zone_cell({"metrics": {**m, "buy_mode": FB}})
    assert fb.startswith(expect) and "區間σ·資料不足" in fb
    # Missing 不加 fallback 註、維持無法判定
    na = _zone_cell({"metrics": {"nav": nav, "buy_mode": FB}})
    assert na == "⬜ 無法判定"


@pytest.mark.parametrize("nav,cls,prefix", [
    (100.0, "Core", "✅ 核心健康，續抱領息"),          # Hold
    (100.0, "Satellite", "✅ 衛星健康，等待訊號"),      # Hold
    (111.0, "Satellite", "🟡 觸及停利區"),               # Take_Profit
    (94.0, "Core", "🟢 進入便宜價"),                      # Buy_Zone
])
def test_n4_verdict_fallback_note_uniform(monkeypatch, nav, cls, prefix):
    import ui.components.mk_dashboard as M
    monkeypatch.setattr(M, "tag_mk_class", lambda f: cls)
    monkeypatch.setattr(M, "tag_health_check", lambda f: "Healthy")
    monkeypatch.setattr(M, "tag_momentum", lambda f: "OK")
    monkeypatch.setattr(M, "tag_principal_erosion", lambda f: "OK")
    monkeypatch.setattr(M, "compute_1y_total_return", lambda f: (None, None))
    import services.fund_screening as FS
    monkeypatch.setattr(FS, "evaluate_333_for_fund", lambda f: {
        k: None for k in ("years", "ann_pct", "basis", "years_ok", "return_ok", "passed")})
    m = {"nav": nav, "buy1": 95.0, "buy2": 90.0, "bb_upper": 110.0}
    normal = M.build_mk_dataframe([{"code": "X", "loaded": True, "metrics": m}])["體檢結論"].iloc[0]
    assert normal.startswith(prefix) and "資料不足" not in normal
    fb = M.build_mk_dataframe([{"code": "X", "loaded": True,
                                "metrics": {**m, "buy_mode": FB}}])["體檢結論"].iloc[0]
    assert fb.startswith(prefix) and fb.endswith("（⚠️ 區間σ·資料不足）")


def test_n4_verdict_red_health_and_missing_zone_get_no_fallback_note(monkeypatch):
    import ui.components.mk_dashboard as M
    monkeypatch.setattr(M, "tag_mk_class", lambda f: "Core")
    monkeypatch.setattr(M, "tag_momentum", lambda f: "OK")
    monkeypatch.setattr(M, "tag_principal_erosion", lambda f: "OK")
    monkeypatch.setattr(M, "compute_1y_total_return", lambda f: (None, None))
    import services.fund_screening as FS
    monkeypatch.setattr(FS, "evaluate_333_for_fund", lambda f: {
        k: None for k in ("years", "ann_pct", "basis", "years_ok", "return_ok", "passed")})
    monkeypatch.setattr(M, "tag_health_check", lambda f: "Sharpe_Warning")
    m = {"nav": 100.0, "buy1": 95.0, "bb_upper": 110.0, "buy_mode": FB}
    v = M.build_mk_dataframe([{"code": "X", "loaded": True, "metrics": m}])["體檢結論"].iloc[0]
    assert v.startswith("🔴") and "資料不足" not in v
    monkeypatch.setattr(M, "tag_health_check", lambda f: "Healthy")
    v2 = M.build_mk_dataframe([{"code": "X", "loaded": True,
                                "metrics": {"nav": 100.0, "buy_mode": FB}}])["體檢結論"].iloc[0]
    assert v2 == "✅ 核心健康（⬜ 價位區間無法判定）"
