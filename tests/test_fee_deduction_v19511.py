"""v19.511:持股頁換扣款標的建構器(ui/helpers/portfolio/fee_deduction.build_fee_inputs)。

純函式:持倉 + T7 帳本 → 引擎輸入 + 誠實排除清單。nav/fx 由測試注入(零 I/O)。
決策(user 2026-08-22):無帳本 → 標「需 T7 帳本」排除;缺 nav/匯率/幣別 → 各自誠實排除。
"""
from ui.helpers.portfolio.fee_deduction import build_fee_inputs


class _Pos:
    def __init__(self, units, cost_unit, fx_avg):
        self.units = units
        self.cost_unit = cost_unit
        self.fx_avg = fx_avg


class _Led:
    # 預設對齊真實 models.ledger.FundPosition:units/cost_unit/fx_avg 皆 float 預設 0.0(**非 None**)。
    def __init__(self, units, cost_unit=0.0, fx_avg=0.0):
        self.position = _Pos(units, cost_unit, fx_avg)


def _fund(code="US_A", name="美股基金", ccy="USD", pid="POL1"):
    return {"code": code, "name": name, "currency": ccy, "policy_id": pid}


def _pk(f):
    from models.policy import fund_pk_str
    return fund_pk_str(f)


# ── 正常:有帳本 + nav/fx → engine_funds 帶帳本 units/成本,rate_map 帶匯率 ──────
def test_with_ledger_builds_engine_fund():
    f = _fund()
    leds = {_pk(f): _Led(units=1000.0, cost_unit=16.0, fx_avg=30.0)}
    ef, exc, rates = build_fee_inputs([f], leds, lambda _f: (20.0, 33.0))
    assert exc == []
    assert len(ef) == 1
    g = ef[0]
    assert g["currency"] == "USD" and g["units"] == 1000.0
    assert g["current_nav"] == 20.0 and g["cost_nav"] == 16.0 and g["cost_rate"] == 30.0
    assert rates["USD"] == 33.0 and rates["TWD"] == 1.0


# ── 決策②:無帳本 → 需 T7 帳本排除 ─────────────────────────────────────
def test_no_ledger_excluded_needs_t7():
    f = _fund()
    ef, exc, _ = build_fee_inputs([f], {}, lambda _f: (20.0, 33.0))
    assert ef == [] and len(exc) == 1
    assert "需 T7 帳本" in exc[0]["reason"]


def test_ledger_zero_units_excluded():
    f = _fund()
    leds = {_pk(f): _Led(units=0.0)}
    ef, exc, _ = build_fee_inputs([f], leds, lambda _f: (20.0, 33.0))
    assert ef == [] and "需 T7 帳本" in exc[0]["reason"]


# ── 缺 nav → 誠實排除 ─────────────────────────────────────────────────
def test_missing_nav_excluded():
    f = _fund()
    leds = {_pk(f): _Led(units=100.0, cost_unit=16.0, fx_avg=30.0)}
    ef, exc, _ = build_fee_inputs([f], leds, lambda _f: (None, 33.0))
    assert ef == [] and "淨值" in exc[0]["reason"]


# ── 外幣缺匯率 → 誠實排除 ──────────────────────────────────────────────
def test_missing_fx_excluded():
    f = _fund()
    leds = {_pk(f): _Led(units=100.0, cost_unit=16.0, fx_avg=30.0)}
    ef, exc, _ = build_fee_inputs([f], leds, lambda _f: (20.0, None))
    assert ef == [] and "匯率" in exc[0]["reason"]


# ── TWD 標的:免匯率,rate_map 走 1.0 ──────────────────────────────────
def test_twd_needs_no_fx():
    f = _fund(code="TW_0050", name="台股高股息", ccy="TWD")
    leds = {_pk(f): _Led(units=100.0, cost_unit=50.0, fx_avg=1.0)}
    ef, exc, rates = build_fee_inputs([f], leds, lambda _f: (55.0, None))  # fx None 也 OK
    assert exc == [] and len(ef) == 1 and ef[0]["currency"] == "TWD"
    assert rates["TWD"] == 1.0


# ── 缺幣別 → 誠實排除 ─────────────────────────────────────────────────
def test_missing_currency_excluded():
    f = _fund(ccy="")
    leds = {_pk(f): _Led(units=100.0, cost_unit=16.0, fx_avg=30.0)}
    ef, exc, _ = build_fee_inputs([f], leds, lambda _f: (20.0, 33.0))
    assert ef == [] and "幣別" in exc[0]["reason"]


# ── 建構器防禦:若成本欄真是 None(非 T7 帳本來源)→ 原樣傳 None(引擎走 is_cost_estimated)。
#    註:真實 T7 FundPosition 成本預設 0.0 非 None,故此為建構器泛用防禦路徑,見下一測反映實況。
def test_none_cost_passes_through_defensively():
    f = _fund()
    leds = {_pk(f): _Led(units=100.0, cost_unit=None, fx_avg=None)}
    ef, _, _ = build_fee_inputs([f], leds, lambda _f: (20.0, 33.0))
    assert ef[0]["cost_nav"] is None and ef[0]["cost_rate"] is None


# ── 反映實況:真實帳本成本預設 0.0(非 None)。units>0 但 cost_unit=0.0(異常/未落買入)
#    → 建構器傳 cost_nav=0.0 → 引擎誠實排除為「資料異常」(§1 不假裝真實基期,也不當「成本未知」)。
def test_prod_zero_cost_ledger_excluded_by_engine():
    from services.policy_fee_optimizer import optimize_policy_fee
    f = _fund()
    leds = {_pk(f): _Led(units=100.0, cost_unit=0.0, fx_avg=0.0)}   # 真實預設形狀
    ef, _, rates = build_fee_inputs([f], leds, lambda _f: (20.0, 33.0))
    assert ef and ef[0]["cost_nav"] == 0.0
    out = optimize_policy_fee(1000.0, rates, ef)
    assert out["funds"][0]["error"] is not None                    # cost<=0 → error,非 is_cost_estimated
    assert out["funds"][0]["is_cost_estimated"] is False


# ── 端到端:建構器 → 引擎 → 推薦(高基期 USD → 情境 A)──────────────────────
def test_end_to_end_with_engine():
    from services.policy_fee_optimizer import optimize_policy_fee
    f = _fund()
    leds = {_pk(f): _Led(units=1000.0, cost_unit=16.0, fx_avg=30.0)}
    ef, _, rates = build_fee_inputs([f], leds, lambda _f: (20.0, 33.0))
    out = optimize_policy_fee(3000.0, rates, ef)
    assert out["recommendation"] == "FUND_DEDUCTION" and out["scenario"] == "A"
    assert abs(out["funds"][0]["score"] - 1.375) < 1e-6


# ── 混合:一檔有帳本、一檔沒 → 分流正確 ─────────────────────────────────
def test_mixed_ledger_and_no_ledger():
    f1 = _fund(code="A", name="有帳本")
    f2 = _fund(code="B", name="沒帳本")
    leds = {_pk(f1): _Led(units=100.0, cost_unit=16.0, fx_avg=30.0)}
    ef, exc, _ = build_fee_inputs([f1, f2], leds, lambda _f: (20.0, 33.0))
    assert len(ef) == 1 and ef[0]["name"] == "有帳本"
    assert len(exc) == 1 and exc[0]["name"] == "沒帳本"
