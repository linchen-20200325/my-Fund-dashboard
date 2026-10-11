# -*- coding: utf-8 -*-
"""級別三態（核心／衛星／未設定）—— 客戶 2026-10-10 裁示的方案 B。

規則：
* 核心＝明確核心；衛星＝明確衛星；未設定＝第三種獨立狀態，**不得被說成衛星**。
* 核心／衛星比例的分母只算已設定級別的本金（核心＋衛星）；未設定另列、不進比例。
* 未設定不得觸發只屬於核心／衛星的搬移、停利、保單建議、戰情室判斷或 AI 標籤。
* 全部未設定 → 不算比例。全部已設定 → 與舊定義**逐位元**相同。

突變驗證（實跑）寫在各條 docstring。
"""
from __future__ import annotations

import ast
import pathlib
import random
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

C, S, U = "core", "satellite", None


def _f(tier, amt, code=None, **kw):
    _d = {"code": code or f"F{random.randint(0, 10**9)}", "invest_twd": amt, **kw}
    if tier == C:
        _d["policy_tier"] = "core"
    elif tier == S:
        _d["is_core"] = False
    return _d


# ══════════════════════════════════════════════════════════════════
# 舊定義（2026-10-10 之前 `ui/helpers/portfolio/allocation.py` 的本體，逐字）——
# 只用來驗「全部已設定時新舊逐位元相同」（第二組 X1）。
# ══════════════════════════════════════════════════════════════════
def _old_resolve_core_flag(fund):
    _f_ = fund or {}
    _tier = str(_f_.get("policy_tier") or "").strip().lower()
    if _tier == "core":
        return True
    if _tier == "satellite":
        return False
    return bool(_f_.get("is_core"))


def _old_summarize(funds, *, target_pct=None):
    out = {
        "total_twd": 0.0, "core_twd": 0.0, "sat_twd": 0.0,
        "core_pct": None, "sat_pct": None,
        "n_funds": 0, "n_core": 0, "n_sat": 0,
        "n_tier_from_sheet": 0, "n_missing_amount": 0,
        "is_amount_weighted": False,
        "target_pct": target_pct, "diff_pct": None,
    }
    if not funds:
        return out
    for _x in funds:
        _x = _x or {}
        try:
            _amt = float(_x.get("invest_twd", 0) or 0)
        except (TypeError, ValueError):
            _amt = 0.0
        _amt = max(_amt, 0.0)
        _is_core = _old_resolve_core_flag(_x)
        out["n_funds"] += 1
        if _amt <= 0:
            out["n_missing_amount"] += 1
        if str(_x.get("policy_tier") or "").strip().lower() in ("core", "satellite"):
            out["n_tier_from_sheet"] += 1
        if _is_core:
            out["n_core"] += 1
            out["core_twd"] += _amt
        else:
            out["n_sat"] += 1
            out["sat_twd"] += _amt
        out["total_twd"] += _amt
    if out["total_twd"] > 0:
        out["is_amount_weighted"] = True
        out["core_pct"] = out["core_twd"] / out["total_twd"] * 100.0
        out["sat_pct"] = 100.0 - out["core_pct"]
        if target_pct is not None:
            out["diff_pct"] = out["core_pct"] - float(target_pct)
    return out


_OLD_KEYS = ("total_twd", "core_twd", "sat_twd", "core_pct", "sat_pct", "n_funds",
             "n_core", "n_sat", "n_tier_from_sheet", "n_missing_amount",
             "is_amount_weighted", "target_pct", "diff_pct")


def _summ(funds, t=75.0):
    from ui.helpers.portfolio.allocation import summarize_core_satellite
    return summarize_core_satellite(funds, target_pct=t)


# ══════════════════════════════════════════════════════════════════
# A. 比例（summarize_core_satellite）
# ══════════════════════════════════════════════════════════════════
def test_r1_unset_is_left_out_of_the_ratio():
    """突變：分母改回 `total_twd` → core_pct 變 50.0，本條紅。"""
    s = _summ([_f(C, 600_000), _f(S, 100_000), _f(U, 500_000)])
    assert s["total_twd"] == 1_200_000 and s["classified_twd"] == 700_000
    assert s["unset_twd"] == 500_000 and s["sat_twd"] == 100_000
    assert s["core_pct"] == pytest.approx(85.7142857, abs=1e-6)
    assert s["sat_pct"] == pytest.approx(14.2857143, abs=1e-6)
    assert s["diff_pct"] == pytest.approx(10.7142857, abs=1e-6)
    assert (s["n_core"], s["n_sat"], s["n_tier_unset"], s["n_in_ratio"]) == (1, 1, 1, 2)


def test_r3_all_unset_has_no_ratio():
    s = _summ([_f(U, 600_000), _f(U, 500_000)])
    assert s["core_pct"] is None and s["sat_pct"] is None and s["diff_pct"] is None
    assert s["is_amount_weighted"] is True and s["n_tier_unset"] == 2


@pytest.mark.parametrize("funds, core, sat, diff, classified", [
    ([_f(C, 600_000), _f(U, 500_000)], 100.0, 0.0, 25.0, 600_000),        # R4
    ([_f(S, 100_000), _f(U, 500_000)], 0.0, 100.0, -75.0, 100_000),       # R5
    ([_f(C, 600_000), _f(S, 100_000), _f(U, 0)], 600/7, 100/7, 600/7 - 75, 700_000),  # R7
])
def test_r4_r5_r7(funds, core, sat, diff, classified):
    s = _summ(funds)
    assert s["core_pct"] == pytest.approx(core)
    assert s["sat_pct"] == pytest.approx(sat)
    assert s["diff_pct"] == pytest.approx(diff)
    assert s["classified_twd"] == classified


def test_r6_r8_no_ratio_when_nothing_classified_has_money():
    s6 = _summ([_f(C, 0), _f(U, 0)])
    assert s6["is_amount_weighted"] is False and s6["core_pct"] is None
    assert s6["n_missing_amount"] == 2
    s8 = _summ([_f(C, 0), _f(U, 500_000)])
    assert s8["is_amount_weighted"] is True and s8["core_pct"] is None


@pytest.mark.parametrize("fund", [
    {"is_core": None}, {}, {"is_core": 0}, {"is_core": 1}, {"is_core": "yes"},
    {"policy_tier": ""}, {"policy_tier": "中性"},
])
def test_r9_these_are_all_unset(fund):
    s = _summ([{"invest_twd": 100, **fund}])
    assert s["n_tier_unset"] == 1 and s["n_core"] == 0 and s["n_sat"] == 0


def test_r10_policy_tier_wins_over_is_core():
    s = _summ([{"invest_twd": 100, "policy_tier": "satellite", "is_core": True}])
    assert s["n_sat"] == 1 and s["n_core"] == 0


def test_all_classified_is_bit_identical_to_the_old_definition():
    """第二組 X1：全部已設定時，舊 13 個鍵必須與舊定義 `==`（不是 isclose）。

    用**非整數**金額 —— 整數金額守不住累加順序造成的末位浮點差。
    突變：把 `core_pct` 的分母寫成 `core_twd + sat_twd`（而不是迴圈內同序累加的
    `classified_twd`）→ 本條紅（實跑）。
    """
    rng = random.Random(20261010)
    for _ in range(2_000):
        funds = []
        for _ in range(rng.randint(1, 8)):
            _amt = rng.choice([0, 0.0, None, -5, "x", rng.uniform(0, 3e6),
                               rng.uniform(0, 1) * 10 ** rng.randint(0, 7)])
            _kind = rng.choice(["pt_core", "pt_sat", "pt_core_case", "ic_t", "ic_f",
                                "pt_sat_ic_t"])
            _d = {"invest_twd": _amt}
            if _kind == "pt_core":
                _d["policy_tier"] = "core"
            elif _kind == "pt_sat":
                _d["policy_tier"] = "satellite"
            elif _kind == "pt_core_case":
                _d["policy_tier"] = " CoRe "
            elif _kind == "ic_t":
                _d["is_core"] = True
            elif _kind == "ic_f":
                _d["is_core"] = False
            else:
                _d.update(policy_tier="satellite", is_core=True)
            funds.append(_d)
        _t = rng.choice([None, 50, 75, 90, 62.5])
        new, old = _summ(funds, _t), _old_summarize(funds, target_pct=_t)
        for k in _OLD_KEYS:
            assert new[k] == old[k], (k, funds, _t, new[k], old[k])


# ══════════════════════════════════════════════════════════════════
# B. 搬移與偏離（⑨ `_gap_action_text`）
# ══════════════════════════════════════════════════════════════════
def _gap(funds, t=75.0):
    from ui.views.page_04_portfolio import _gap_action_text
    return _gap_action_text(_summ(funds, t))


def test_g1_g4_g5_move_amount_stays_inside_the_classified_side():
    """突變：⑨ 搬移金額改回 `× total_twd` → G1 印 NT$128,571、G5 印 NT$450,000，本條紅。"""
    g1 = _gap([_f(C, 600_000), _f(S, 100_000), _f(U, 500_000)])
    assert g1.startswith("從核心移 NT$75,000 到衛星"), g1
    assert "（只算已設定級別且已填本金的 2 檔）" in g1
    assert _gap([_f(C, 600_000), _f(U, 500_000)]).startswith("從核心移 NT$150,000 到衛星")
    g5 = _gap([_f(S, 100_000), _f(U, 500_000)])
    assert g5.startswith("從衛星移 NT$75,000 到核心"), g5
    assert _gap([_f(U, 600_000), _f(U, 500_000)]) == ""


def test_g2_all_classified_keeps_the_old_scope_sentence():
    g = _gap([_f(C, 620_000), _f(S, 380_000), _f(S, 0)])
    assert "（只算已填本金的 2 檔）" in g and "已設定級別" not in g


def test_g7_move_never_exceeds_the_explicit_side_and_ignores_unset():
    """性質測試（第二組 X 系列）：核心不足 → 搬移 ≤ 明確衛星；核心過多 → 搬移 ≤ 明確核心；
    未設定的金額不影響搬移金額。目標 t ∈ [0, 100]（production slider 為 50~90）。
    """
    rng = random.Random(7)
    for _ in range(3_000):
        c = rng.choice([0, rng.uniform(1, 5e6)])
        s = rng.choice([0, rng.uniform(1, 5e6)])
        u = rng.uniform(0, 5e6)
        t = rng.uniform(0, 100)
        funds = [_f(C, c), _f(S, s), _f(U, u)]
        sm = _summ(funds, t)
        if sm["diff_pct"] is None:
            assert c + s == 0
            continue
        need = -sm["diff_pct"] / 100.0 * sm["classified_twd"]
        if need > 0:
            assert need <= s * (1 + 1e-9) + 1e-6, (c, s, u, t, need)
        else:
            assert -need <= c * (1 + 1e-9) + 1e-6, (c, s, u, t, need)
        sm2 = _summ([_f(C, c), _f(S, s), _f(U, u * 3 + 1)], t)
        assert sm2["diff_pct"] == sm["diff_pct"]
        assert sm2["classified_twd"] == sm["classified_twd"]


# ══════════════════════════════════════════════════════════════════
# C. 說明 caption（S1／S2／S3／S3b／S4）
# ══════════════════════════════════════════════════════════════════
def _cap(funds):
    from ui.helpers.portfolio.allocation import format_core_satellite_caption
    return format_core_satellite_caption(_summ(funds))


def test_captions_for_each_state():
    s1 = _cap([_f(C, 600_000), _f(S, 100_000), _f(U, 500_000)])
    assert s1.startswith("分母 = 已設定級別的投入本金") and "⬜ 未設定 1 檔" in s1
    assert "NT$500,000" in s1 and "41.7%" in s1 and "設定後比例可能改變" in s1
    s2 = _cap([_f(C, 600_000), _f(S, 200_000)])
    assert s2 == "分母 = Σ 投入本金（**金額**加權，非檔數）；級別已設定 2 檔。"
    s3 = _cap([_f(U, 600_000), _f(U, 500_000)])
    assert s3.startswith("⬜ 2 檔級別皆未設定") and "`tier`／`policy_tier`" in s3
    s3b = _cap([_f(C, 0), _f(U, 500_000)])
    assert s3b.startswith("⬜ 目前沒有「已設定級別且已填本金」的基金")
    s4 = _cap([_f(C, 0), _f(U, 0)])
    assert s4.startswith("⚠️ 2 檔皆未填投入本金") and "⬜ 未設定 1 檔" in s4
    for _c in (s1, s2, s3, s3b, s4):
        assert "推定" not in _c and "關鍵字" not in _c


# ══════════════════════════════════════════════════════════════════
# D. 保單建議句（services/policy_advisor_service.recommend_policy）
# ══════════════════════════════════════════════════════════════════
def _rec(funds, t=75.0):
    from services.policy_advisor_service import recommend_policy
    return recommend_policy(funds, target_core_pct=t)


def test_t3_unset_does_not_push_core_under():
    """突變：`recommend_policy` 改回 `if f.get("is_core")` 且分母用全部金額 → P2「從衛星轉核心」，本條紅。"""
    r = _rec([{"invest_twd": 600_000, "is_core": True},
              {"invest_twd": 100_000, "is_core": False},
              {"invest_twd": 500_000, "is_core": None}])
    assert r["code"] == "POLICY_CORE_OVER", r
    assert r["text"].startswith("核心配置 85.7% 高於目標 75%（+10.7%）")


def test_t4_x8_whole_policy_unset_is_grey_and_not_healthy():
    r = _rec([{"invest_twd": 600_000}, {"invest_twd": 500_000, "is_core": None}])
    assert r["code"] == "POLICY_TIER_UNSET" and r["color"] == "grey"
    assert r["text"] == "此保單沒有已設定級別且已填本金的基金，未判斷核心／衛星配置"
    assert "60MA" not in r["text"]


def test_x9_classified_without_money_is_also_not_judged():
    r = _rec([{"invest_twd": 0, "is_core": True}, {"invest_twd": 500_000}])
    assert r["code"] == "POLICY_TIER_UNSET"


def test_t5_unset_funds_still_count_for_deep_drop():
    r = _rec([{"invest_twd": 100, "sigma_info": {"sigma_rank": -2.5}},
              {"invest_twd": 100, "sigma_info": {"sigma_rank": -2.1}}])
    assert r["code"] == "POLICY_RISK_HEAVY_DROP"


def test_all_classified_policy_keeps_the_old_sentence():
    r = _rec([{"invest_twd": 600_000, "is_core": True}, {"invest_twd": 200_000, "is_core": False}])
    assert r["code"] == "POLICY_HEALTHY"
    assert r["text"] == "核心 75.0% / 衛星 25.0%（偏差 +0.0%） → 配置健康，持續觀察 60MA 與配息覆蓋率"


# ══════════════════════════════════════════════════════════════════
# E. AI 提示（services/ai_service.analyze_portfolio_mk_advisor）
# ══════════════════════════════════════════════════════════════════
def _pf_snap(monkeypatch, funds):
    import services.ai_service as _ai
    _seen = {}
    monkeypatch.setattr(_ai, "build_mk_advisor_prompt",
                        lambda **kw: (_seen.update(kw), "p")[1])
    monkeypatch.setattr(_ai, "call_llm", lambda *a, **k: "")
    _ai.analyze_portfolio_mk_advisor("k", funds, {"phase": "擴張"})
    return _seen["pf_snap"]


def test_t6_ai_labels_follow_the_three_states(monkeypatch):
    snap = _pf_snap(monkeypatch, [
        {"code": "AC", "loaded": True, "invest_twd": 1, "is_core": True},
        {"code": "AS", "loaded": True, "invest_twd": 1, "is_core": False},
        {"code": "AU", "loaded": True, "invest_twd": 1},
        {"code": "AV", "loaded": True, "invest_twd": 1, "policy_tier": "core"},
    ])
    assert "[核心] `AC`" in snap and "[衛星] `AS`" in snap
    assert "[未設定] `AU`" in snap and "[核心] `AV`" in snap


def test_x6_same_code_satellite_plus_unset_is_not_merged_into_satellite(monkeypatch):
    """突變：聚合鍵改回只用 code → 合併成一行「[衛星] … NT$300」，本條紅。"""
    snap = _pf_snap(monkeypatch, [
        {"code": "X", "loaded": True, "invest_twd": 100, "is_core": False, "policy_id": "P1"},
        {"code": "X", "loaded": True, "invest_twd": 200, "policy_id": "P2"},
    ])
    assert re.search(r"\[衛星\] `X`.*投入 NT\$100 ", snap), snap
    assert re.search(r"\[未設定\] `X`.*投入 NT\$200 ", snap), snap


# ══════════════════════════════════════════════════════════════════
# F. 戰情室 MK_Class 與組合健康儀表
# ══════════════════════════════════════════════════════════════════
def test_t9_unset_take_profit_is_not_counted_as_satellite_take_profit():
    import pandas as pd
    from ui.helpers.portfolio.health import compute_health_kpis
    df = pd.DataFrame([
        {"MK_Class": "Unset", "Price_Zone": "Take_Profit", "Health_Check": "Healthy",
         "Principal_Erosion": "N/A"},
        {"MK_Class": "Satellite", "Price_Zone": "Hold", "Health_Check": "Healthy",
         "Principal_Erosion": "N/A"},
    ])
    k = compute_health_kpis([{"code": "A"}, {"code": "B"}], df)
    assert k["n_take"] == 0
    assert k["ratio_label"] == "核心 0 檔 / 衛星 1 檔 / ⬜ 未設定 1 檔"


def test_satellite_only_verdicts_are_not_given_to_unset():
    from ui.components.mk_dashboard import _verdict_text
    assert _verdict_text("Unset", "Healthy", "Weakening", "Hold", bench_lag="Lag") == "—"
    assert _verdict_text("Satellite", "Healthy", "Hold", "Hold") == "✅ 衛星健康，等待訊號"


# ══════════════════════════════════════════════════════════════════
# G. T7 衛星停利燈（實際把 `_sat_stop_label` 從原始碼抽出來執行）
# ══════════════════════════════════════════════════════════════════
def _sat_stop_label():
    from services.satellite import satellite_stop_gain
    from shared.policy_tier import resolve_tier
    _src = (ROOT / "ui" / "tab3_t7_ledger.py").read_text(encoding="utf-8")
    _fn = next(n for n in ast.walk(ast.parse(_src))
               if isinstance(n, ast.FunctionDef) and n.name == "_sat_stop_label")
    _mod = ast.Module(body=[_fn], type_ignores=[])
    _ns = {"_sat_sg": satellite_stop_gain, "_resolve_tier": resolve_tier}
    exec(compile(_mod, "tab3_t7_ledger._sat_stop_label", "exec"), _ns)
    return _ns["_sat_stop_label"]


def test_t1_t2_stop_gain_lamp_only_for_explicit_satellites():
    """突變：改回 `is_satellite=(not resolve_core_flag(fund))`（並拿掉未設定分支）→ T1 亮 🔴，本條紅。"""
    lbl = _sat_stop_label()
    assert lbl({}, 25.0) == "⬜ 未設定"
    assert lbl({"is_core": None}, 25.0) == "⬜ 未設定"
    assert "強制停利" in lbl({"policy_tier": "satellite"}, 25.0)
    assert lbl({"policy_tier": "core"}, 25.0) == "—"


# ══════════════════════════════════════════════════════════════════
# I. ③ 單檔研究「已在組合」定位 chip（D3／S5）
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("fund, tag", [
    ({}, "定位 ⬜ 未設定"),
    ({"policy_tier": "core"}, "定位 核心(穩健)"),
    ({"is_core": False}, "定位 衛星(積極)"),
])
def test_t10_membership_chip(monkeypatch, fund, tag):
    import ui.helpers.portfolio.linkage as _lk
    _out = []
    monkeypatch.setattr(_lk.st, "markdown", lambda s, **k: _out.append(s))
    _lk.render_fund_portfolio_membership(
        {"portfolio_funds": [{"code": "A1", "invest_twd": 100, **fund}]}, fund_codes=["A1"])
    assert _out and tag in _out[0], _out


# ══════════════════════════════════════════════════════════════════
# J. 說明書（⑤）
# ══════════════════════════════════════════════════════════════════
def test_t13_manual_no_longer_says_unset_goes_to_satellite():
    _t = ast.parse((ROOT / "ui" / "tab6_manual.py").read_text(encoding="utf-8"))
    _txt = "\n".join(n.value for n in ast.walk(_t)
                     if isinstance(n, ast.Constant) and isinstance(n.value, str))
    assert "都不命中 → 歸「衛星」" not in _txt
    assert "用**基金名稱關鍵字**推定" not in _txt
    assert "手動設定 > 關鍵字比對 > 預設（衛星）" not in _txt
    assert "⬜ 未設定" in _txt and "Σ(已設定級別基金的投入本金 TWD)" in _txt


# ══════════════════════════════════════════════════════════════════
# K. ④ 我的配置 —— 真的把整頁跑起來（AppTest，離線）
# ══════════════════════════════════════════════════════════════════
_OFFLINE = (
    f"import sys; sys.path.insert(0, {str(ROOT)!r})\n"
    "import socket\n"
    "def _offline(*a, **k): raise OSError('offline test')\n"
    "socket.socket.connect = _offline\n"
    "socket.create_connection = _offline\n"
)


def _reset_stack():
    """別的測試檔在 bare 模式留下的 form 標記會讓 AppTest 裡的 `st.form` 炸掉
    （機制見 `tests/test_wf04_portfolio_skeleton.py::_reset_streamlit_container_stack`）。"""
    from streamlit.delta_generator import context_dg_stack
    from streamlit.delta_generator_singletons import get_dg_singleton_instance
    _main = get_dg_singleton_instance().main_dg
    _main._form_data = None
    context_dg_stack.set((_main,))


def _flat(node, out):
    _ch = getattr(node, "children", None)
    if not isinstance(_ch, dict):
        return out
    for _, _c in sorted(_ch.items()):
        try:
            _v = getattr(_c, "value", None)
        except Exception:   # widget 的 value 在沒有 state 時會拋，這裡只要文字
            _v = None
        out.append(f"[{type(_c).__name__}] {_v if _v is not None else getattr(_c, 'label', '')}")
        _flat(_c, out)
    return out


def _run(script, session):
    from streamlit.testing.v1 import AppTest
    _reset_stack()
    _at = AppTest.from_string(_OFFLINE + script, default_timeout=180)
    for _k, _v in session.items():
        _at.session_state[_k] = _v
    try:
        _at.run()
    finally:
        _reset_stack()
    assert not _at.exception, [str(e.value) for e in _at.exception]
    return _at, "\n".join(_flat(_at._tree, []))


_TAB3 = ("from ui.tab3_portfolio import render_portfolio_tab\n"
         "render_portfolio_tab()\n")


def _tab3_funds(tiers):
    _out = []
    for i, (t, amt) in enumerate(tiers):
        _d = {"code": f"TST{i}", "name": f"測試基金{i}", "loaded": True,
              "invest_twd": amt, "policy_id": "P1", "currency": "TWD"}
        if t == C:
            _d["policy_tier"] = "core"
        elif t == S:
            _d["policy_tier"] = "satellite"
        _out.append(_d)
    return _out


@pytest.fixture(scope="module")
def tab3_all_unset():
    return _run(_TAB3, {
        "portfolio_funds": _tab3_funds([(U, 600_000), (U, 500_000)]),
        # 防禦期 —— 讓「降衛星曝險」那一句有機會出現（舊碼在這裡會印「僅 0.0%」）。
        "macro_done": True, "phase_info": {"phase": "衰退", "score": 2.0},
    })


def test_x3_tab3_all_unset_renders_without_satellite_claims(tab3_all_unset):
    """第二組 X3：全部未設定、有本金 ⇒ 不崩潰；不得出現「衛星 100」「配置健康」
    「降衛星曝險」「⚡衛星」（逐檔卡）；KPI／Hero／保單 header 顯示「—」。

    突變：④ KPI 的 None 換回 0.0 → 「衛星 100.0%」出現，本條紅。
    """
    _, txt = tab3_all_unset
    for bad in ("衛星 100", "配置健康", "降衛星曝險", "⚡衛星", "可在 Tab3 上方加入",
                "從衛星移"):
        assert bad not in txt, bad
    assert "核心 —" in txt                       # 保單 header（S10）
    assert "⬜未設定" in txt                     # 逐檔卡（S6）
    assert "⬜ 2 檔級別皆未設定" in txt          # KPI caption（S3）
    assert "此保單沒有已設定級別且已填本金的基金" in txt   # 保單建議句（S11）
    assert "⬜ 未設定 2 檔：不列入核心戰情室與波段觀測站" in txt  # 戰情室空狀態（S14）


def test_x4_x5_ai_snapshot_with_all_unset(tab3_all_unset):
    at, _ = tab3_all_unset
    snap = at.session_state["_tab3_ai_snap"]["snapshot"]
    assert "（衛星）" not in snap and "（未設定）" in snap
    assert "未填投入本金" not in snap
    assert "目前沒有「已設定級別且已填本金」的基金" in snap and "⬜ 未設定 2 檔（不計入比例）" in snap


def test_x13_ai_fingerprint_changes_when_only_the_tier_changes(tab3_all_unset):
    at_u, _ = tab3_all_unset
    at_c, _ = _run(_TAB3, {"portfolio_funds": _tab3_funds([(C, 600_000), (U, 500_000)])})
    assert at_u.session_state["_tab3_ai_snap"]["fp"] != at_c.session_state["_tab3_ai_snap"]["fp"]


def test_g1_tab3_partly_unset_uses_the_classified_denominator():
    _, txt = _run(_TAB3, {"portfolio_funds": _tab3_funds(
        [(C, 600_000), (S, 100_000), (U, 500_000)])})
    assert "85.7%" in txt and "14.3%" in txt
    assert "⚠️ 配置偏離 +10.7%（核心 85.7% vs 目標 75%）— 核心過重，可贖回轉衛星" in txt
    assert "· ⬜ 未設定 1 檔" in txt


def test_x7_war_room_satellite_tab_has_no_buy_advice_when_all_unset():
    """第二組 X7：全部未設定時，波段觀測站的空狀態不得叫人「加入科技／半導體…」。

    突變：把空狀態字串改回原句 → 本條紅。
    """
    _script = ("from ui.components.mk_dashboard import render_mk_war_room\n"
               "import streamlit as st\n"
               "render_mk_war_room(st.session_state['pf'])\n")
    at, _ = _run(_script, {"pf": _tab3_funds([(U, 1), (U, 2)])})
    at.radio(key="mk_view_pick").set_value(at.radio(key="mk_view_pick").options[1])
    _reset_stack()
    try:
        at.run()
    finally:
        _reset_stack()
    txt = "\n".join(_flat(at._tree, []))
    assert "沒有被分類為「衛星」" in txt, "前提：真的切到了波段觀測站"
    assert "科技／半導體" not in txt and "加入高股息" not in txt
    assert "⬜ 未設定 2 檔：不列入核心戰情室與波段觀測站" in txt


def test_t8_war_room_three_states():
    from ui.components.mk_dashboard import build_mk_dataframe
    df = build_mk_dataframe(_tab3_funds([(C, 1), (S, 1), (U, 1)]))
    assert list(df["MK_Class"]) == ["Core", "Satellite", "Unset"]


# ══════════════════════════════════════════════════════════════════
# L. 結構守衛：不准再寫「二態轉衛星」（第二組 X11）
# ══════════════════════════════════════════════════════════════════
_REACHABLE = (
    "ui/tab3_portfolio.py", "ui/tab3_t7_ledger.py", "ui/views/page_04_portfolio.py",
    "ui/components/mk_dashboard.py", "ui/helpers/portfolio/allocation.py",
    "ui/helpers/portfolio/health.py", "ui/helpers/portfolio/linkage.py",
    "ui/helpers/portfolio/load.py", "ui/helpers/cloud_io.py",
    "repositories/snapshot_repository.py", "services/ai_service.py",
    "services/policy_advisor_service.py",
)
_SAT_WORDS = {"衛星", "Satellite", "⚡衛星", "衛星(積極)", "[衛星]"}


def _two_state_offenders(src: str) -> list:
    _bad = []
    for n in ast.walk(ast.parse(src)):
        # (a) `not resolve_core_flag(...)` / `not _resolve_core(...)`
        if (isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not)
                and isinstance(n.operand, ast.Call)):
            _fn = n.operand.func
            _name = getattr(_fn, "id", None) or getattr(_fn, "attr", "")
            if "core" in _name.lower() and "tier" not in _name.lower():
                _bad.append((n.lineno, "not <core flag>"))
        # (b) `X if <cond> else "衛星"`（else 直接是衛星字面值 ⇒ 判不出來就當衛星）
        if (isinstance(n, ast.IfExp) and isinstance(n.orelse, ast.Constant)
                and n.orelse.value in _SAT_WORDS):
            _bad.append((n.lineno, f"... else {n.orelse.value!r}"))
        # (c) `bool(x.get("is_core"...))` / `.get("is_core", True)`
        if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "get" and n.args \
                and isinstance(n.args[0], ast.Constant) and n.args[0].value == "is_core" \
                and len(n.args) > 1:
            _bad.append((n.lineno, ".get('is_core', <default>)"))
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "bool" and n.args \
                and isinstance(n.args[0], ast.Call) \
                and getattr(n.args[0].func, "attr", "") == "get" \
                and n.args[0].args and getattr(n.args[0].args[0], "value", None) == "is_core":
            _bad.append((n.lineno, "bool(.get('is_core'))"))
    return _bad


def test_x11_guard_actually_catches_the_old_shapes():
    """正對照：守衛本身必須抓得到舊寫法，否則它是空轉。"""
    _old = ('a = "核心" if resolve_core_flag(f) else "衛星"\n'
            'b = sat_sg(p, is_satellite=(not _resolve_core(f)))\n'
            'c = any(not f.get("is_core", True) for f in x)\n'
            'd = bool(f.get("is_core"))\n')
    assert len(_two_state_offenders(_old)) == 4


@pytest.mark.parametrize("rel", _REACHABLE)
def test_x11_no_two_state_to_satellite_shapes(rel):
    """突變：把 ④ AI 快照逐檔行改回 `'核心' if _core_flag_ai(f) else '衛星'` → 本條紅。"""
    _bad = _two_state_offenders((ROOT / rel).read_text(encoding="utf-8"))
    assert not _bad, f"{rel}：{_bad}"
