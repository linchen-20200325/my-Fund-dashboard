"""tests/test_bl0428_dg_rulings.py — BL-0428 客戶裁示落地守衛(2026-10-23,`DEC-2026-10-23-11`)。

客戶裁示:DG-1 A / DG-2 A / DG-3 C / DG-4 C / DG-5 A(盤點見 `docs/v2/64_v2_ssot_convergence.md` §9)。

本檔守:
- **DG-1 A**:行動類 consumer 遇基金位置 ⬜ 不得讀成中性／安全／HOLD／續抱／未觸發／健康;
  沿用既有「資料不足／無法判定」措辭並列出 ⬜ 檔數(不新增狀態)。
- **DG-2 A**:配置回測權重與數字**不變**(golden),只把 ⬜ 與「觀望」分開列示並計檔數。
- **DG-3 C**:`advise_fund` / `recommend_policy` / `decision_matrix` 不再由 HWM σ 產生行動文字
  (AST ＋ 行為雙守)。
- **§9.8**:四捨五入字串重新分類(已確認 bug)—— 行動類 consumer 讀 SSOT 正式數值。
DG-4 C(calc_metrics 買賣點 / 布林卡 / ladder235)與 DG-5 A(不新增低波動門檻)= 本批不動,
不在本檔加守衛(BL-0438 另案)。
"""
from __future__ import annotations

import ast
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent


# ── 共用 fixture ─────────────────────────────────────────────────────────────

def _idx(n=300):
    return pd.bdate_range("2023-01-02", periods=n)


def _far_fund(code="FAR"):
    """非配息、位置可判定且「遠離高點」(漲 250 天後回落)。"""
    rng = np.random.default_rng(3)
    v = np.concatenate([np.linspace(10, 12, 250), np.linspace(12, 10.5, 50)]) + rng.normal(0, 0.02, 300)
    return {"code": code, "name": "FarFund", "series": pd.Series(v, index=_idx()), "dividends": []}


def _near_fund(code="NEAR"):
    rng = np.random.default_rng(4)
    v = np.linspace(10, 12, 300) + rng.normal(0, 0.02, 300)
    return {"code": code, "name": "NearFund", "series": pd.Series(v, index=_idx()), "dividends": []}


def _unknown_fund(code="UNK"):
    """歷史太短 → SSOT ⬜。"""
    rng = np.random.default_rng(5)
    return {"code": code, "name": "ShortFund",
            "series": pd.Series(10 + rng.normal(0, 0.01, 20), index=_idx(20)), "dividends": []}


def test_fixture_premises():
    from services.fund_position import compute_fund_position
    assert compute_fund_position(_far_fund())["position"] == "far_from_high"
    assert compute_fund_position(_near_fund())["position"] == "near_high"
    assert compute_fund_position(_unknown_fund())["status"] == "unavailable"


class _FakeSt:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def _rec(*a, **k):
            self.calls.append((name, a))
        return _rec


# ═══ DG-1 A:Missing ≠ 中性 ═══════════════════════════════════════════════════

def _pol(invest, is_core, sig):
    return {"invest_twd": invest, "is_core": is_core, "sigma_info": sig}


@pytest.mark.parametrize("unk_sig", [None, {"error": "⬜ 無法判定"},
                                     {"sigma_rank": None, "error": "x"}, {"label": "x"}])
def test_dg1_recommend_policy_unknown_never_green(unk_sig):
    from services.policy_advisor_service import INSUFFICIENT_DATA, recommend_policy
    r = recommend_policy([_pol(750_000, True, {"sigma_rank": -0.2}),
                          _pol(250_000, False, unk_sig)], target_core_pct=75.0)
    assert r["color"] != "green" and "配置健康" not in r["text"]
    assert r["code"] == INSUFFICIENT_DATA and r["color"] == "grey"
    assert "資料不足" in r["text"] and "1 檔基金位置無法判定" in r["text"]


def test_dg1_recommend_policy_all_known_still_green_unchanged():
    from services.policy_advisor_service import POLICY_HEALTHY, recommend_policy
    r = recommend_policy([_pol(750_000, True, {"sigma_rank": -0.2}),
                          _pol(250_000, False, {"sigma_rank": -3.0})], target_core_pct=75.0)
    assert r["code"] == POLICY_HEALTHY and r["color"] == "green"
    assert r["text"] == "核心 75.0% / 衛星 25.0%（偏差 +0.0%） → 配置健康，持續觀察 60MA 與配息覆蓋率"


def test_dg1_recommend_policy_non_sigma_rules_unchanged_but_disclose_unknown():
    from services.policy_advisor_service import POLICY_CORE_OVER, POLICY_RISK_HEAVY_RED, recommend_policy
    r = recommend_policy([_pol(1_000_000, True, None)], target_core_pct=75.0)
    assert r["code"] == POLICY_CORE_OVER and "另 1 檔基金位置無法判定" in r["text"]
    r0 = recommend_policy([_pol(1_000_000, True, {"sigma_rank": -0.1})], target_core_pct=75.0)
    assert r0["code"] == POLICY_CORE_OVER and "無法判定" not in r0["text"]
    red = {"alert_level": "red"}
    r2 = recommend_policy([{**_pol(500_000, True, None), "dividend_info": red},
                           {**_pol(500_000, False, None), "dividend_info": red}], target_core_pct=50.0)
    assert r2["code"] == POLICY_RISK_HEAVY_RED and "另 2 檔基金位置無法判定" in r2["text"]


def test_dg1_advise_fund_unknown_is_insufficient_grey():
    from services.policy_advisor_service import INSUFFICIENT_DATA, advise_fund
    for _sig in (None, {}, {"error": "x"}, {"sigma_rank": None}):
        r = advise_fund(_sig, {"alert_level": "green"}, "up", 99.0)
        assert r["code"] == INSUFFICIENT_DATA and r["color"] == "grey"


def test_dg1_decision_matrix_unknown_reason_differs_from_known():
    """B 組實跑的那條:⬜ 與 σ = −1.0 的輸出原本逐字相同。現在 ⬜ 必須揭露,動作不變。"""
    from services.decision_matrix import POSITION_UNKNOWN_TAG, verdict_to_actions
    base = {"code": "S", "policy_tier": "satellite"}
    for lv in ("極度樂觀", "樂觀", "中性", "悲觀", "極度悲觀"):
        known = verdict_to_actions(lv, 0.0, [{**base, "sigma_info": {"sigma_rank": -1.0}}])[0]
        for unk in (None, {"error": "x", "sigma_rank": None}):
            got = verdict_to_actions(lv, 0.0, [{**base, "sigma_info": unk}])[0]
            assert got["action"] == known["action"]
            assert got["reason"] != known["reason"]
            assert POSITION_UNKNOWN_TAG in got["reason"]
            assert "位置無法判定" in got["reason"]


def _adv(code, action):
    from services.switch_advisor import _ACTION_ZH
    return {"code": code, "name": code, "action": action, "action_zh": _ACTION_ZH[action],
            "underperformance": {"is_underperforming": False}}


def test_dg1_line_notify_empty_does_not_fold_unknown_into_hold():
    from services.switch_advisor import HOLD, INSUFFICIENT
    from services.switch_notify import build_notification
    res = {"advices": [_adv("A", HOLD), _adv("B", INSUFFICIENT), _adv("C", INSUFFICIENT)],
           "summary": {"n_holdings": 3, "n_switch": 0, "n_sell_cash": 0,
                       "n_underperforming": 0, "n_insufficient": 2}}
    n = build_notification(res)
    assert n["should_notify"] is False
    assert "所有標的續抱" not in n["message"]
    assert "其餘標的續抱 / 觀察中" in n["message"]
    assert "⬜ 資料不足 2 檔" in n["message"]
    assert "｜資料不足 2" in n["message"]


def test_dg1_line_all_unknown_gets_no_green_check():
    from services.switch_advisor import INSUFFICIENT
    from services.switch_notify import build_notification
    res = {"advices": [_adv("B", INSUFFICIENT)],
           "summary": {"n_holdings": 1, "n_insufficient": 1}}
    msg = build_notification(res)["message"]
    assert "✅" not in msg and "續抱" not in msg.split("標的 1 檔")[0]
    assert "⬜ 本週無法評估換股" in msg


def test_dg1_line_no_unknown_message_unchanged():
    from services.switch_advisor import HOLD
    from services.switch_notify import build_notification
    res = {"advices": [_adv("A", HOLD)], "summary": {"n_holdings": 1, "n_insufficient": 0}}
    msg = build_notification(res)["message"]
    assert "✅ 本週無需換股：所有標的續抱 / 觀察中。" in msg
    assert "｜資料不足 0" in msg


def test_dg1_line_counts_insufficient_from_advices_when_summary_lacks_key():
    from services.switch_advisor import INSUFFICIENT
    from services.switch_notify import build_notification
    msg = build_notification({"advices": [_adv("B", INSUFFICIENT)], "summary": {}})["message"]
    assert "所有標的續抱" not in msg and "資料不足 1" in msg


def test_dg1_line_no_evaluated_but_skipped_gets_no_green_check():
    """稽核小修:advices=[] 且 skipped>0 → 不給 ✅、不說續抱;摘要另列「未評估 N」。"""
    from services.switch_notify import build_notification
    msg = build_notification({"advices": [], "summary": {"n_holdings": 0}}, skipped=3)["message"]
    assert "✅" not in msg and "續抱" not in msg
    assert "⬜ 本週無法評估換股:沒有任何標的完成評估。" in msg
    assert "⬜ 另有 3 檔資料不足、未評估" in msg and "｜未評估 3" in msg


def test_dg1_line_some_evaluated_plus_skipped_uses_remaining_wording():
    from services.switch_advisor import HOLD
    from services.switch_notify import build_notification
    res = {"advices": [_adv("A", HOLD)], "summary": {"n_holdings": 1, "n_insufficient": 0}}
    msg = build_notification(res, skipped=2)["message"]
    assert "所有標的續抱" not in msg
    assert "✅ 本週無需換股：其餘標的續抱 / 觀察中。" in msg
    assert "｜資料不足 0｜未評估 2" in msg


def test_dg1_far_from_high_list_partial_unknown_not_success(monkeypatch):
    import ui.helpers.fund_grp_health.risk as R
    fake = _FakeSt()
    monkeypatch.setattr(R, "st", fake)
    R._render_oversold_badges([_near_fund(), _unknown_fund()])
    names = [n for n, _ in fake.calls]
    assert "success" not in names
    cap = " ".join(str(a) for n, a in fake.calls if n == "caption")
    assert "可判定的基金中" in cap and "1 檔位置無法判定" in cap


def test_dg1_far_from_high_list_no_unknown_keeps_success(monkeypatch):
    import ui.helpers.fund_grp_health.risk as R
    fake = _FakeSt()
    monkeypatch.setattr(R, "st", fake)
    R._render_oversold_badges([_near_fund()])
    assert "success" in [n for n, _ in fake.calls]


def test_dg1_far_from_high_list_nonempty_discloses_unknown(monkeypatch):
    import ui.helpers.fund_grp_health.risk as R
    fake = _FakeSt()
    monkeypatch.setattr(R, "st", fake)
    R._render_oversold_badges([_far_fund(), _unknown_fund()])
    cap = " ".join(str(a) for n, a in fake.calls if n == "caption")
    assert "1 檔基金" in cap and "1 檔位置無法判定" in cap


def test_dg1_ai_snapshot_denominator_excludes_unknown():
    from ui.helpers.fund_grp_health.ai import _build_cross_fund_snapshot
    snap, _ = _build_cross_fund_snapshot([_far_fund(), _near_fund(), _unknown_fund()])
    assert "遠離高點(σ rank ≤ −1.5,研究候選門檻、未校準):1 檔 / 2 檔可判定" in snap
    assert "⬜ 位置無法判定(資料不足／無法判定):1 檔" in snap
    assert "平均 σ rank(可判定 2 檔)" in snap


def _rot_rows(n_unknown: int, n_mid: int):
    rows = [{"code": f"U{i}", "name": f"Unk{i}", "σ rank": "—", "sigma_rank": None}
            for i in range(n_unknown)]
    rows += [{"code": f"M{i}", "name": f"Mid{i}", "σ rank": "-1.00σ", "sigma_rank": -1.0}
             for i in range(n_mid)]
    return rows


def _render_rot_empty(monkeypatch, rows):
    import ui.helpers.fund_grp_health.rotation as RO
    fake = _FakeSt()
    monkeypatch.setattr(RO, "st", fake)
    RO._render_pairs_body(rows, [], -0.5, -1.5, key_prefix="t_", offer_download=False)
    return " ".join(str(a) for n, a in fake.calls if n == "info")


def test_dg1_rotation_empty_all_unknown_not_said_no_near_high(monkeypatch):
    info = _render_rot_empty(monkeypatch, _rot_rows(3, 0))
    assert "沒有貼近高點" not in info
    assert "無法判定" in info and "3 檔" in info


def test_dg1_rotation_empty_partial_unknown_discloses(monkeypatch):
    info = _render_rot_empty(monkeypatch, _rot_rows(1, 2))
    assert "可判定的基金中沒有貼近高點" in info and "1 檔位置無法判定" in info


def test_dg1_rotation_empty_no_unknown_text_unchanged(monkeypatch):
    info = _render_rot_empty(monkeypatch, _rot_rows(0, 2))
    assert info.startswith("('目前**沒有貼近高點的「高基期」持有基金** → 沒有需要輪動賣出的標的。可把")


# ═══ DG-2 A:配置回測 —— 數字不變,只分開列示 ═══════════════════════════════

_BT_D = pd.date_range("2021-01-04", periods=520, freq="B")


def _bt_ser(mu, sig, seed):
    rng = np.random.default_rng(seed)
    return pd.Series(100.0 * np.exp(np.cumsum(rng.normal(mu, sig, 520))), index=_BT_D)


def _bt_fx():
    rng = np.random.default_rng(7)
    return pd.Series(30.0 + np.cumsum(rng.normal(0.0, 0.03, 520)), index=_BT_D).clip(lower=1.0)


def _bt_run():
    from services.allocation_backtest import backtest_allocations
    nav = {"A": _bt_ser(0.0004, 0.012, 11), "B": _bt_ser(-0.0002, 0.015, 12),
           "C": _bt_ser(0.0001, 0.01, 13), "U": _bt_ser(0.0002, 0.011, 14)}
    ccy = {"A": "TWD", "B": "USD", "C": "TWD", "U": "USD"}
    return backtest_allocations(nav, ccy, _bt_fx(), meta_by_code={"A": {}, "B": {}, "C": {}})


#: Golden = 本批改動**前**(main 027078e2)同一輸入實跑的值(BL-0428 DG-2 A:不得改任何回測數字)。
_GOLDEN_EQ_LAST = {"S0": 1.2950167573372275, "S1": 1.2950167573372275, "S2": 1.297907362645517,
                   "S3": 1.305539305195911, "S4": 1.1390247390993633}
_GOLDEN_SHARPE = {"S0": 1.41, "S1": 1.41, "S2": 1.42, "S3": 1.48, "S4": 0.56}
_GOLDEN_S3_W = {"A": 1 / 6, "B": 1 / 3, "C": 1 / 6, "U": 1 / 3}
_GOLDEN_S4_W = {"A": 0.02845622647168056, "B": 0.2824320209462693,
                "C": 0.5991006872823742, "U": 0.09001106529967602}


def test_dg2_backtest_numbers_unchanged_golden():
    res = _bt_run()
    assert res["ok"] and res["ranking"] == ["S3", "S2", "S0", "S1", "S4"] and res["winner"] == "S3"
    for sid, v in _GOLDEN_EQ_LAST.items():
        assert math.isclose(float(res["results"][sid]["equity_curve"].iloc[-1]), v,
                            rel_tol=1e-12, abs_tol=1e-12), sid
        assert res["results"][sid]["metrics"]["sharpe"] == _GOLDEN_SHARPE[sid]
    for c, w in _GOLDEN_S3_W.items():
        assert math.isclose(res["results"]["S3"]["final_weights"][c], w, rel_tol=1e-12)
    for c, w in _GOLDEN_S4_W.items():
        assert math.isclose(res["results"]["S4"]["final_weights"][c], w, rel_tol=1e-9)
    assert res["actions"]["target_weights_pct"] == {"A": 16.67, "B": 33.33, "C": 16.67, "U": 33.33}
    # ⬜ 的 tier 仍是 watch(S3)/ na(S1、S2)—— 權重路徑不動
    assert res["results"]["S3"]["final_signals"]["U"]["tier"] == "watch"
    assert res["results"]["S1"]["final_signals"]["U"]["tier"] == "na"


def test_dg2_unknown_listed_separately_from_watch():
    act = _bt_run()["actions"]
    al = act["action_lists"]
    # ~~watch = ["B", "U"]~~(⬜ 併入觀望)→ ⬜ 另列
    assert al["watch"] == ["B"] and al["unknown"] == ["U"] and al["switch"] == ["A", "C"]
    assert act["counts"] == {"buy": 0, "switch": 2, "watch": 1, "unknown": 1}


def test_dg2_current_actions_na_and_unknown_separated():
    from services.allocation_backtest import current_actions_from_signals
    sig = {"W": {"tier": "watch", "nav_level": "mid"},
           "N": {"tier": "na", "nav_level": "unknown"},
           "S": {"tier": "watch", "nav_level": "unknown"},
           "H": {"tier": "hold"}}
    a = current_actions_from_signals(sig, {"W": 0.25, "N": 0.25, "S": 0.25, "H": 0.25})
    assert sorted(a["action_lists"]["unknown"]) == ["N", "S"]
    assert sorted(a["action_lists"]["watch"]) == ["H", "W"]
    assert a["target_weights_pct"] == {"W": 25.0, "N": 25.0, "S": 25.0, "H": 25.0}


def test_dg2_backtest_ui_shows_unknown_count_text_only():
    src = (ROOT / "ui/helpers/fund_grp_health/backtest_section.py").read_text(encoding="utf-8")
    assert "⬜ 無法判定（{len(_unk)} 檔，不是觀望；維持基準權重）" in src
    # 不新增元件:三欄 columns 仍是 3、沒有新的 st.columns(4)
    assert "st.columns(4)" not in src


# ═══ DG-3 C:HWM σ 不再產生行動文字 ═════════════════════════════════════════

_DG3_FUNCS = {
    "services/policy_advisor_service.py": ("advise_fund", "recommend_policy"),
    "services/decision_matrix.py": ("_action_after_individual_signals", "verdict_to_actions"),
}


def _fn(path, name):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    raise AssertionError(f"{path}::{name} 不存在")


def _is_num_const(n):
    return isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) \
        and not isinstance(n.value, bool)


@pytest.mark.parametrize("path,name", [(p, f) for p, fs in _DG3_FUNCS.items() for f in fs])
def test_dg3_no_sigma_threshold_compare_in_action_functions(path, name):
    """AST:這四個函式內不得出現「σ / rank 與數字比大小」(σ 驅動行動門檻)。"""
    fn = _fn(path, name)
    for n in ast.walk(fn):
        if not isinstance(n, ast.Compare):
            continue
        operands = [n.left, *n.comparators]
        if not any(_is_num_const(o) or (isinstance(o, ast.UnaryOp) and _is_num_const(o.operand))
                   for o in operands):
            continue
        txt = ast.unparse(n).lower()
        assert "sigma" not in txt and "rank" not in txt and "_r " not in f"{txt} ", (
            f"{path}::{name} 仍有 σ 門檻比較:{ast.unparse(n)}")


def test_dg3_decision_matrix_override_does_not_read_sigma_param():
    fn = _fn("services/decision_matrix.py", "_action_after_individual_signals")
    loads = [n for n in ast.walk(fn) if isinstance(n, ast.Name) and n.id == "sigma_rank"
             and isinstance(n.ctx, ast.Load)]
    assert not loads, "σ 覆寫已退休,函式內不得讀 sigma_rank"


def test_dg3_advise_fund_output_invariant_to_sigma_value_except_label():
    from services.policy_advisor_service import POSITION_EVIDENCE_ONLY, advise_fund
    for r in np.linspace(-4.0, 0.0, 41):
        out = advise_fund({"sigma_rank": float(r)}, {"alert_level": "red"}, "down", 50.0)
        assert out["code"] == POSITION_EVIDENCE_ONLY and out["color"] == "grey"
        for w in ("加碼", "停利", "承接", "換強", "持有", "接刀", "跌了就買"):
            assert w not in out["text"]


def test_dg3_recommend_policy_invariant_to_sigma_value():
    from services.policy_advisor_service import recommend_policy
    outs = {(o["code"], o["color"], o["text"]) for o in (
        recommend_policy([_pol(500_000, True, {"sigma_rank": float(r)}),
                          _pol(500_000, False, {"sigma_rank": float(r)})], target_core_pct=50.0)
        for r in np.linspace(-4.0, 0.0, 41))}
    assert len(outs) == 1


def test_dg3_sigma_thresholds_not_promoted_to_actions():
    """−0.5 / −1.5(SSOT 三態切點)沒有被升格成行動門檻:跨過切點,動作 / 建議不變。"""
    from services.decision_matrix import verdict_to_actions
    from services.policy_advisor_service import advise_fund
    base = {"code": "S", "policy_tier": "satellite"}
    for cut in (-0.5, -1.5):
        for lv in ("樂觀", "中性", "悲觀"):
            a = verdict_to_actions(lv, 0.0, [{**base, "sigma_info": {"sigma_rank": cut + 0.01}}])[0]
            b = verdict_to_actions(lv, 0.0, [{**base, "sigma_info": {"sigma_rank": cut - 0.01}}])[0]
            assert a["action"] == b["action"] and a["reason"] == b["reason"]
        assert advise_fund({"sigma_rank": cut + 0.01}, None)["code"] == \
            advise_fund({"sigma_rank": cut - 0.01}, None)["code"]


# ═══ §9.8:四捨五入字串重新分類 → 讀 SSOT 正式數值 ═════════════════════════════

def _fake_position(rank):
    def _f(fund, *a, **k):
        return {"status": "ok", "sigma_rank": rank, "current_nav": 10.0, "hwm_tr": 11.0,
                "dist_to_hwm_pct": -9.0, "label": "x", "position": None}
    return _f


@pytest.mark.parametrize("rank,disp,num_state,str_state", [
    (-0.503, "-0.50σ", "mid", "high"),     # 盤點 A 組實跑的那組
    (-1.496, "-1.50σ", "mid", "low"),      # 低切點附近(SSOT σ rank 為 3 位小數,−1.496 可產生)
    (-0.4996, "-0.50σ", "high", "high"),   # 同字串、兩邊一致的對照
])
def test_s98_numeric_vs_string_boundary(monkeypatch, rank, disp, num_state, str_state):
    import services.fund_position as FP
    from services.fund_grp_health.risk import hwm_sigma_with_numeric
    from services.rotation import classify_base, row_sigma_rank
    monkeypatch.setattr(FP, "compute_fund_position", _fake_position(rank))
    d, num = hwm_sigma_with_numeric([{"code": "X"}])
    assert d["X"]["σ rank"] == disp                 # 顯示字串不變
    assert num["X"] == rank
    assert classify_base(d["X"]["σ rank"]) == str_state       # 舊路徑(bug 所在)
    row = {"σ rank": d["X"]["σ rank"], "sigma_rank": num["X"]}
    assert classify_base(row_sigma_rank(row)) == num_state     # 新路徑 = SSOT 數值


def test_s98_row_sigma_rank_numeric_key_wins_and_unknown_stays_unknown():
    from services.rotation import row_sigma_rank
    assert row_sigma_rank({"σ rank": "-2.00σ", "sigma_rank": None}) is None   # ⬜ 不得從字串復活
    assert row_sigma_rank({"σ rank": "-2.00σ"}) == -2.0                         # 無數值鍵 → 退回字串
    assert row_sigma_rank({"sigma_rank": float("nan")}) is None
    assert row_sigma_rank({"sigma_rank": True}) is None


def test_s98_base_column_reads_numeric(monkeypatch):
    import services.fund_grp_health.unified as U
    import services.fund_position as FP
    monkeypatch.setattr(FP, "compute_fund_position", _fake_position(-0.503))
    import services.fund_grp_health.capture as C
    import services.fund_grp_health.quality as Q
    import services.fund_grp_health.signals as S
    monkeypatch.setattr(C, "capture_by_code", lambda funds: {})
    monkeypatch.setattr(Q, "quality_score_by_code", lambda funds, capture_map=None: {})
    monkeypatch.setattr(S, "mk_signal_by_code", lambda funds, phase, score: {})
    order, comb = U.build_merged_extra_columns([{"code": "X"}], "", None)
    assert comb["X"]["σ rank"] == "-0.50σ"
    assert comb["X"]["基期"] == "⚪ 中性"            # ~~字串解析 → 🔴 高基期~~
    assert comb["X"][U.SIGMA_RANK_KEY] == -0.503
    assert U.SIGMA_RANK_KEY not in order             # 不是表格欄


def test_s98_rotation_switch_navfx_read_numeric():
    from services.rotation import suggest_rotation_pairs
    from services.switch_advisor import advise_holding
    from ui.helpers.fund_grp_health.unified import compute_nav_fx_column
    sell = {"code": "S", "name": "S", "基金類別": "股票", "σ rank": "-0.50σ", "sigma_rank": -0.503}
    assert suggest_rotation_pairs([sell]) == []      # ~~字串判 high → 被列為賣方~~
    buy = {"code": "B", "name": "B", "基金類別": "債券", "σ rank": "-1.50σ", "sigma_rank": -1.496,
           "4D Grade": "A", "吃本金燈號": "🟢 健康", "操盤評分": 90}
    hi = {"code": "H", "name": "H", "基金類別": "股票", "σ rank": "-0.10σ", "sigma_rank": -0.1}
    pairs = suggest_rotation_pairs([hi, buy])
    assert pairs and pairs[0]["buy_code"] is None   # ~~字串判 low → 被列為買方~~
    assert pairs[0]["sell_sigma"] == -0.1
    held = {"code": "S", "name": "S", "基金類別": "股票", "σ rank": "-0.50σ", "sigma_rank": -0.503,
            "type_override": "震盪"}
    adv = advise_holding(held, [])
    assert adv["signals"]["nav_level"] == "mid"
    fx = {"USD": {"regime": "weak_twd", "robust": True}}
    row = {"ccy": "USD", "σ rank": "-0.50σ", "sigma_rank": -0.503}
    assert compute_nav_fx_column(row, fx)["淨值×匯率"] != compute_nav_fx_column(
        {"ccy": "USD", "σ rank": "-0.50σ"}, fx)["淨值×匯率"]


def test_s98_assemble_rows_carry_numeric_sigma(monkeypatch):
    import scripts.weekly_switch_notify as M
    import services.fx_regime_service as FXR
    import services.fund_grp_health.unified as U
    import services.health.dividend as D
    import services.health.report as R
    monkeypatch.setattr(U, "build_merged_extra_columns",
                        lambda funds, phase, score: ([], {"AAA": {"σ rank": "-0.50σ",
                                                                   U.SIGMA_RANK_KEY: -0.503}}))
    monkeypatch.setattr(R, "build_health_analysis_row", lambda fd, code, **kw: {})
    monkeypatch.setattr(D, "check_eating_principal_1y_mk", lambda fd: {})
    monkeypatch.setattr(FXR, "fx_regime_by_ccy", lambda *a, **kw: {})
    r = M._assemble_rows([{"code": "AAA", "series": pd.Series([1.0, 2.0]), "moneydj_raw": {}}], {})[0]
    assert r["sigma_rank"] == -0.503 and r["σ rank"] == "-0.50σ"
    src = (ROOT / "ui/helpers/fund_grp_health/rotation.py").read_text(encoding="utf-8")
    assert '"sigma_rank": _e.get(_SIGMA_RANK_KEY)' in src


def test_s98_no_action_consumer_classifies_display_string():
    """行動類 consumer 不得再對「σ rank」顯示字串直接 classify_base(批次 df 對映函式除外)。"""
    for rel in ("services/rotation.py", "services/switch_advisor.py",
                "services/fund_grp_health/unified.py", "ui/helpers/fund_grp_health/unified.py",
                "ui/helpers/fund_grp_health/rotation.py"):
        tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "classify_base" and n.args:
                assert "σ rank" not in ast.unparse(n.args[0]), f"{rel}: {ast.unparse(n)}"
