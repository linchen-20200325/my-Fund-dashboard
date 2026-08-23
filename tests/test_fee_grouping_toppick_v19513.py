"""v19.513:換扣款決策 —— 保單分組正規化容錯 + 引擎 top_pick(組內最適標的)。

user 2026-08-23 兩決策:
  1. **同一張保單要一起比**:政策表 policy_id 被打成 'P1'/'p1'/'　P1 '/全形 等相近字串時,
     分組須容錯併回同一組(大小寫/空白/全半形不分),美元+台幣標的才能一起比。
  2. **一律點名組內最適標的**:引擎輸出 top_pick = 組內最高 S(依匯率×淨值)足額標的。
"""
from ui.helpers.portfolio.fee_deduction import (
    _group_funds_by_policy,
    _norm_policy_key,
)


def _f(pid, code="A", name=None, pname="", ccy="TWD"):
    return {"policy_id": pid, "policy_name": pname, "code": code,
            "name": name or code, "currency": ccy}


# ── _norm_policy_key:大小寫/空白/全半形容錯 ─────────────────────────────────
def test_norm_key_case_space_fullwidth():
    base = _norm_policy_key("P1")
    assert _norm_policy_key("p1") == base            # 大小寫
    assert _norm_policy_key("  P1 ") == base          # 頭尾空白
    assert _norm_policy_key("Ｐ１") == base           # 全形 → 半形(NFKC)
    assert _norm_policy_key("P  1") == _norm_policy_key("P 1")  # 內部空白收斂


def test_norm_key_distinct_ids_stay_distinct():
    assert _norm_policy_key("P1") != _norm_policy_key("P2")
    assert _norm_policy_key("國泰A") != _norm_policy_key("國泰B")


def test_norm_key_empty():
    assert _norm_policy_key("") == ""
    assert _norm_policy_key(None) == ""
    assert _norm_policy_key("   ") == ""


# ── _group_funds_by_policy:相近 policy_id 併回一組(美元+台幣一起比)─────────────
def test_group_merges_near_identical_ids():
    usd = _f("P1", code="US", ccy="USD")
    twd = _f("p1", code="TW", ccy="TWD")            # 只差大小寫 → 應同組
    groups, untagged = _group_funds_by_policy([usd, twd])
    assert untagged == []
    assert len(groups) == 1
    g = groups[0]
    assert len(g["funds"]) == 2                      # 美元 + 台幣一起比
    assert set(g["raw_ids"]) == {"P1", "p1"}         # 原字串都留存(供 UI 提示統一)


def test_group_distinct_policies_not_merged():
    a = _f("P1", code="A")
    b = _f("P2", code="B")
    groups, _ = _group_funds_by_policy([a, b])
    assert len(groups) == 2


def test_group_untagged_separated():
    tagged = _f("P1", code="A")
    untag = _f("", code="B")
    groups, untagged = _group_funds_by_policy([tagged, untag])
    assert len(groups) == 1 and len(untagged) == 1
    assert untagged[0]["code"] == "B"


# ── display:有 policy_name 用之;皆空 → 代表 policy_id(**非**「未命名保單」)──────
def test_group_display_prefers_policy_name():
    f = _f("P1", pname="國泰人壽變額A")
    groups, _ = _group_funds_by_policy([f])
    assert groups[0]["display"] == "國泰人壽變額A"


def test_group_display_falls_back_to_policy_id_not_placeholder():
    f = _f("MY_POLICY_9", pname="")                  # policy_name 空白
    groups, _ = _group_funds_by_policy([f])
    assert groups[0]["display"] == "MY_POLICY_9"     # 顯示實際 id,不再「未命名保單」
    assert "未命名" not in groups[0]["display"]


def test_group_preserves_input_order():
    groups, _ = _group_funds_by_policy([_f("Z"), _f("A"), _f("Z")])
    assert [g["raw_ids"][0] for g in groups] == ["Z", "A"]   # 保序,Z 先出現


# ── L2 引擎 top_pick:組內最高 S 足額標的(依匯率×淨值)────────────────────────
def _efund(fid, ccy, nav, cost_nav, units, cost_rate=None):
    d = {"id": fid, "name": fid, "currency": ccy,
         "current_nav": nav, "units": units, "cost_nav": cost_nav}
    if cost_rate is not None:
        d["cost_rate"] = cost_rate
    return d


def test_top_pick_is_highest_score_eligible():
    from services.policy_fee_optimizer import optimize_policy_fee
    # 美元 score 1.375(高)、台幣 score 1.05 → top_pick 應為美元(組內最高 S)
    usd = _efund("US", "USD", nav=25.0, cost_nav=20.0, units=1000.0, cost_rate=30.0)
    twd = _efund("TW", "TWD", nav=10.5, cost_nav=10.0, units=10000.0)
    out = optimize_policy_fee(1000.0, {"USD": 33.0}, [usd, twd])
    assert out["top_pick"] is not None
    assert out["top_pick"]["id"] == "US"
    assert out["top_pick"]["currency"] == "USD"
    # top_pick 帶匯率×淨值拆解供 UI 點名理由
    assert out["top_pick"]["return_factor"] is not None
    assert out["top_pick"]["fx_factor"] is not None


def test_top_pick_none_when_no_eligible():
    from services.policy_fee_optimizer import optimize_policy_fee
    tiny = _efund("TINY", "TWD", nav=10.0, cost_nav=9.0, units=50.0)   # 市值 500 < 費 1000
    out = optimize_policy_fee(1000.0, {}, [tiny])
    assert out["scenario"] == "C"
    assert out["top_pick"] is None


def test_top_pick_below_cost_still_named():
    from services.policy_fee_optimizer import optimize_policy_fee
    # 唯一標的略低於成本(score 0.95)→ 仍為 top_pick(user 要一律點名);UI 依帶標示虧損
    twd = _efund("DIP", "TWD", nav=9.5, cost_nav=10.0, units=10000.0)
    out = optimize_policy_fee(1000.0, {}, [twd])
    assert out["top_pick"] is not None and out["top_pick"]["id"] == "DIP"
    assert out["top_pick"]["score"] < 1.0


def test_top_pick_json_safe():
    import json
    from services.policy_fee_optimizer import optimize_policy_fee
    twd = _efund("TW", "TWD", nav=11.0, cost_nav=10.0, units=10000.0)
    out = optimize_policy_fee(1000.0, {}, [twd])
    json.dumps(out)                                  # top_pick 為 dict/None → 可序列化


# ── §1 排名護欄:推定 S=1.0(成本未知)不得蓋過已知略低於成本的真實標的 ──────────────
def test_top_pick_prefers_real_cost_over_imputed():
    from services.policy_fee_optimizer import optimize_policy_fee
    real = _efund("REAL", "TWD", nav=9.5, cost_nav=10.0, units=10000.0)   # 真實 score 0.95
    est = {"id": "EST", "name": "EST", "currency": "TWD",                 # cost 缺 → 推定 1.0
           "current_nav": 10.0, "units": 10000.0}
    out = optimize_policy_fee(1000.0, {}, [real, est])
    # 假平價 1.0 不得勝過已知 0.95 的真實標的 → top_pick 應為 REAL
    assert out["top_pick"]["id"] == "REAL"
    assert out["top_pick"]["is_cost_estimated"] is False
    assert out["top_pick"]["score"] < 1.0


def test_top_pick_falls_back_to_imputed_when_no_real_cost():
    from services.policy_fee_optimizer import optimize_policy_fee
    est = {"id": "EST", "name": "EST", "currency": "TWD",
           "current_nav": 10.0, "units": 10000.0}                         # 唯一足額但成本未知
    out = optimize_policy_fee(1000.0, {}, [est])
    assert out["top_pick"]["id"] == "EST"            # 無真實成本標的 → 退推定
    assert out["top_pick"]["is_cost_estimated"] is True
