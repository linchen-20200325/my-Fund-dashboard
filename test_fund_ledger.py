"""fund_ledger.py 單元測試（v18.0 Phase 1）

CHUBB 安達人壽圖片實數復現：
  Fund: BGUPC029 瀚亞多重收益優化組合基金B類型-美元-(配現金)
  ──────────────────────────────────────────
  Units            (2)  = 3,645.73145
  Cost_unit        (1)  = 8.2179
  FX_avg           (3)  = 31.1498
  Cost_with_div    (10) = 6.4401
  NAV_current      (5)  = 8.31
  FX_current       (7)  = 31.4265
  ──────────────────────────────────────────
  期望輸出：
  Net_investment   (4)  ≈ 933,256 TWD
  Value_orig       (6)  ≈ 30,296.03
  Value_twd        (8)  ≈ 952,098.13
  ROI_price        (9)  ≈ 2.019%
  ROI_total        (11) ≈ 30.1815%
"""
from datetime import date

from models.ledger import FundPosition
from services.ledger_service import Ledger, GhostPortfolio, Switch, calculate_xirr


def assert_close(actual: float, expected: float, tol: float = 0.01, msg: str = "") -> None:
    diff = abs(actual - expected)
    if diff > tol:
        raise AssertionError(
            f"{msg}: expected {expected}, got {actual} (diff={diff:.6f}, tol={tol})"
        )


def test_chubb_11_fields_reproduction() -> None:
    """直接構造 FundPosition（模擬已抓取保單帳戶資料）→ 復現 11 欄位。"""
    p = FundPosition(
        fund_code="BGUPC029",
        currency="USD",
        units=3645.73145,
        cost_unit=8.2179,
        fx_avg=31.1498,
        cost_unit_with_div=6.4401,
    )
    assert_close(p.net_investment_twd, 933256.0, tol=2.0, msg="(4) net_investment_twd")
    assert_close(p.value_orig(nav=8.31), 30296.03, tol=0.5, msg="(6) value_orig")
    assert_close(p.value_twd(nav=8.31, fx=31.4265), 952098.13, tol=2.0, msg="(8) value_twd")
    assert_close(p.roi_price(nav=8.31, fx=31.4265), 0.02019, tol=0.0001, msg="(9) ROI_price")
    assert_close(
        p.roi_total_chubb(nav=8.31, fx=31.4265), 0.301815, tol=0.001, msg="(11) ROI_total"
    )
    print("✅ CHUBB 11 欄位數字全部對齊（誤差皆在容忍範圍內）")


def test_subscribe_first_buy() -> None:
    """單筆首次買入：cost_unit / fx_avg / cost_unit_with_div 應 = 買入價。"""
    led = Ledger(fund_code="TEST", currency="USD")
    new_u = led.subscribe(amount_twd=311498.0, fx_rate=31.1498, nav=10.0, txn_date=date(2026, 1, 15))
    # 311498 TWD / 31.1498 FX = 10000 USD / 10 NAV = 1000 units
    assert_close(new_u, 1000.0, msg="returned units")
    assert_close(led.position.units, 1000.0, msg="units")
    assert_close(led.position.cost_unit, 10.0, msg="cost_unit")
    assert_close(led.position.fx_avg, 31.1498, msg="fx_avg")
    assert_close(led.position.cost_unit_with_div, 10.0, msg="cost_unit_with_div")
    assert len(led.transactions) == 1
    print("✅ subscribe_first_buy")


def test_subscribe_weighted_average() -> None:
    """兩筆買入加權平均：成本與匯率正確加權。"""
    led = Ledger(fund_code="TEST", currency="USD")
    led.subscribe(amount_twd=300000.0, fx_rate=30.0, nav=10.0, txn_date=date(2026, 1, 15))
    # 1000 單位 @ NAV 10, FX 30
    led.subscribe(amount_twd=192000.0, fx_rate=32.0, nav=12.0, txn_date=date(2026, 2, 15))
    # 192000/32 = 6000 USD / 12 = 500 單位
    assert_close(led.position.units, 1500.0, msg="units")
    # cost_unit = (1000×10 + 500×12) / 1500 = 16000/1500 ≈ 10.6667
    assert_close(led.position.cost_unit, 10.6667, tol=0.001, msg="cost_unit weighted avg")
    # fx_avg = (1000×30 + 500×32) / 1500 = 46000/1500 ≈ 30.6667
    assert_close(led.position.fx_avg, 30.6667, tol=0.001, msg="fx_avg weighted avg")
    print("✅ subscribe_weighted_average")


def test_dividend_cash_drops_cost_with_div() -> None:
    """配現金：cost_unit_with_div 下調，cost_unit / units 不變，dividends_received_twd 累加。"""
    led = Ledger(fund_code="TEST", currency="USD")
    led.subscribe(amount_twd=300000.0, fx_rate=30.0, nav=10.0, txn_date=date(2026, 1, 15))
    # 配 0.5 USD/unit @ NAV 11
    cash_twd = led.dividend_cash(
        div_per_unit=0.5, fx_rate=31.0, txn_date=date(2026, 3, 15), nav_at_div=11.0
    )
    # virtual_units = 1000 × 0.5 / 11 ≈ 45.4545
    # new_cost_with_div = 10.0 × 1000 / (1000 + 45.4545) ≈ 9.5652
    assert_close(led.position.cost_unit, 10.0, msg="cost_unit unchanged")
    assert_close(led.position.cost_unit_with_div, 9.5652, tol=0.001, msg="cost_unit_with_div")
    assert_close(led.position.units, 1000.0, msg="units unchanged")
    # cash_twd = 1000 × 0.5 × 31 = 15500
    assert_close(cash_twd, 15500.0, msg="returned cash_twd")
    assert_close(led.position.dividends_received_twd, 15500.0, msg="累計 TWD 配息")
    print("✅ dividend_cash_drops_cost_with_div")


def test_dividend_cash_no_nav_only_accumulates() -> None:
    """配現金未提供 nav_at_div：僅累加 TWD 配息、不下調 cost_unit_with_div。"""
    led = Ledger(fund_code="TEST", currency="USD")
    led.subscribe(amount_twd=300000.0, fx_rate=30.0, nav=10.0, txn_date=date(2026, 1, 15))
    led.dividend_cash(div_per_unit=0.5, fx_rate=31.0, txn_date=date(2026, 3, 15))
    assert_close(led.position.cost_unit_with_div, 10.0, msg="cost_unit_with_div 未下調")
    assert_close(led.position.dividends_received_twd, 15500.0, msg="僅累加")
    print("✅ dividend_cash_no_nav_only_accumulates")


def test_dividend_reinvest() -> None:
    """配單位：units 增加，cost_unit / cost_unit_with_div 加權平均，fx_avg 不變。"""
    led = Ledger(fund_code="TEST", currency="USD")
    led.subscribe(amount_twd=300000.0, fx_rate=30.0, nav=10.0, txn_date=date(2026, 1, 15))
    led.dividend_reinvest(new_units=50.0, nav_at_div=11.0, txn_date=date(2026, 3, 15))
    # tot = 1050; cost = (1000×10 + 50×11) / 1050 = 10550/1050 ≈ 10.0476
    assert_close(led.position.units, 1050.0, msg="units")
    assert_close(led.position.cost_unit, 10.0476, tol=0.001, msg="cost_unit weighted avg")
    assert_close(led.position.fx_avg, 30.0, msg="fx_avg unchanged")
    print("✅ dividend_reinvest")


def test_ghost_portfolio_b_wins() -> None:
    """影子投組：B 的價值 > Ghost A → 創造超額報酬。"""
    actual_b = FundPosition(
        fund_code="B", units=1000.0, cost_unit=10.0, fx_avg=30.0, cost_unit_with_div=10.0
    )
    ghost_a = FundPosition(
        fund_code="A", units=900.0, cost_unit=10.0, fx_avg=30.0, cost_unit_with_div=10.0
    )
    cmp = GhostPortfolio.compare(
        actual_b, nav_b=12.0, fx_b=31.0,    # B value = 1000 × 12 × 31 = 372,000
        ghost_a=ghost_a, nav_a=11.0, fx_a=31.0,  # A value = 900 × 11 × 31 = 306,900
    )
    assert cmp.value_actual_twd > cmp.value_ghost_twd, "B 應跑贏"
    assert cmp.excess_pct > 0, "excess_pct 應為正"
    assert "創造超額" in cmp.verdict, f"verdict={cmp.verdict}"
    print(f"✅ ghost_portfolio_b_wins: excess={cmp.excess_pct:+.2%}")


def test_ghost_portfolio_a_wins() -> None:
    """影子投組：B 的價值 < Ghost A → 機會成本損失。"""
    actual_b = FundPosition(
        fund_code="B", units=1000.0, cost_unit=10.0, fx_avg=30.0, cost_unit_with_div=10.0
    )
    ghost_a = FundPosition(
        fund_code="A", units=900.0, cost_unit=10.0, fx_avg=30.0, cost_unit_with_div=10.0
    )
    cmp = GhostPortfolio.compare(
        actual_b, nav_b=9.0, fx_b=31.0,     # B = 1000 × 9 × 31 = 279,000
        ghost_a=ghost_a, nav_a=12.0, fx_a=31.0,  # A = 900 × 12 × 31 = 334,800
    )
    assert cmp.excess_pct < 0, "B 應落後"
    assert "機會成本損失" in cmp.verdict, f"verdict={cmp.verdict}"
    print(f"✅ ghost_portfolio_a_wins: excess={cmp.excess_pct:+.2%}")


def test_ghost_portfolio_with_dividends() -> None:
    """影子投組：含已領配息正確加總到雙邊。"""
    actual_b = FundPosition(
        fund_code="B", units=1000.0, cost_unit=10.0, fx_avg=30.0, cost_unit_with_div=10.0,
        dividends_received_twd=20000.0,
    )
    ghost_a = FundPosition(
        fund_code="A", units=900.0, cost_unit=10.0, fx_avg=30.0, cost_unit_with_div=10.0,
        dividends_received_twd=15000.0,
    )
    cmp = GhostPortfolio.compare(
        actual_b, nav_b=10.0, fx_b=31.0,    # B = 310,000 + 20,000 = 330,000
        ghost_a=ghost_a, nav_a=10.0, fx_a=31.0,  # A = 279,000 + 15,000 = 294,000
    )
    assert_close(cmp.value_actual_twd, 330000.0, msg="B 含息總值")
    assert_close(cmp.value_ghost_twd, 294000.0, msg="A 含息總值")
    print(f"✅ ghost_portfolio_with_dividends: B={cmp.value_actual_twd:,.0f} vs A={cmp.value_ghost_twd:,.0f}")


def test_zero_division_guard() -> None:
    """空持倉 / 零投資 → ROI 應為 0、不 crash。"""
    p = FundPosition(fund_code="EMPTY", currency="USD")
    assert p.net_investment_twd == 0.0
    assert p.roi_price(nav=10.0, fx=30.0) == 0.0
    assert p.roi_total_chubb(nav=10.0, fx=30.0) == 0.0
    assert p.roi_total_cashflow(nav=10.0, fx=30.0) == 0.0
    print("✅ zero_division_guard")


def test_subscribe_invalid_args() -> None:
    """負金額 / 零匯率 / 零 NAV 應 raise ValueError。"""
    led = Ledger(fund_code="T")
    for bad in [
        dict(amount_twd=-1, fx_rate=30, nav=10),
        dict(amount_twd=100, fx_rate=0, nav=10),
        dict(amount_twd=100, fx_rate=30, nav=0),
    ]:
        try:
            led.subscribe(**bad, txn_date=date(2026, 1, 1))
        except ValueError:
            continue
        raise AssertionError(f"應 raise ValueError: {bad}")
    print("✅ subscribe_invalid_args")


def test_dividend_on_empty_position_raises() -> None:
    """無持倉時配息應 raise ValueError。"""
    led = Ledger(fund_code="T")
    try:
        led.dividend_cash(div_per_unit=0.5, fx_rate=31.0, txn_date=date(2026, 1, 1))
    except ValueError:
        print("✅ dividend_on_empty_position_raises")
        return
    raise AssertionError("應 raise ValueError")


def test_full_chubb_lifecycle() -> None:
    """完整生命週期：兩筆買入 + 一筆配現金 → 確認 cost_unit_with_div < cost_unit。"""
    led = Ledger(fund_code="LIFE", currency="USD")
    led.subscribe(amount_twd=300000.0, fx_rate=30.0, nav=10.0, txn_date=date(2026, 1, 1))
    led.subscribe(amount_twd=350000.0, fx_rate=31.0, nav=10.5, txn_date=date(2026, 4, 1))
    cash = led.dividend_cash(
        div_per_unit=0.6, fx_rate=31.5, txn_date=date(2026, 7, 1), nav_at_div=10.8
    )
    pos = led.position
    assert pos.cost_unit_with_div < pos.cost_unit, (
        f"含息成本應低於不含息成本：cost={pos.cost_unit:.4f}, with_div={pos.cost_unit_with_div:.4f}"
    )
    assert pos.dividends_received_twd > 0
    assert cash > 0
    assert len(led.transactions) == 3
    # 含息 ROI 應 > 不含息 ROI（因配息加分）
    nav_now, fx_now = 11.0, 32.0
    assert pos.roi_total_cashflow(nav_now, fx_now) > pos.roi_price(nav_now, fx_now)
    print(
        f"✅ full_chubb_lifecycle: units={pos.units:.4f}, "
        f"cost={pos.cost_unit:.4f}, with_div={pos.cost_unit_with_div:.4f}, "
        f"div_twd={pos.dividends_received_twd:,.0f}"
    )


# ═══ Phase 2 測試：Switching ════════════════════════════════════════════


def test_switch_same_currency_basic() -> None:
    """同幣別 switch（無費用）：B 端 fx_avg 嚴格繼承 A 的 fx_avg，TWD 成本守恆。"""
    led_a = Ledger(fund_code="A", currency="USD")
    led_b = Ledger(fund_code="B", currency="USD")
    led_a.subscribe(amount_twd=300000.0, fx_rate=30.0, nav=10.0, txn_date=date(2026, 1, 1))
    # A: 1000 units, cost_unit=10, fx_avg=30, twd_cost=300,000
    res = Switch.switch_same_currency(
        ledger_from=led_a, ledger_to=led_b, units_to_redeem=None,
        nav_from_redeem=12.0, nav_to_buy=6.0, fee_orig=0.0,
        txn_date=date(2026, 6, 1),
    )
    # redeem 1000 × 12 = 12000 USD → / 6 = 2000 units in B
    assert_close(res.units_redeemed_from, 1000.0, msg="redeemed")
    assert_close(res.units_added_to, 2000.0, msg="added")
    assert_close(res.fx_avg_inherited, 30.0, msg="B fx_avg 繼承 A")
    # TWD 成本守恆：300,000
    assert_close(res.twd_cost_basis_transferred, 300000.0, msg="TWD 成本守恆")
    # B cost_unit = 300000 / (2000 × 30) = 5.0
    assert_close(res.cost_unit_to_basis, 5.0, msg="B cost_unit 反推")
    # A 端歸零
    assert_close(led_a.position.units, 0.0, msg="A 歸零")
    # B 端 net_investment_twd = 300,000（與 A 原始相同）
    assert_close(led_b.position.net_investment_twd, 300000.0, tol=0.5, msg="B net_inv = A 原 net_inv")
    # B ROI_price @ NAV 7, FX 31 = (2000 × 7 × 31) / 300000 - 1 = 434000/300000-1 = 44.67%
    assert_close(led_b.position.roi_price(7.0, 31.0), 0.4467, tol=0.001, msg="B ROI_price")
    print("✅ switch_same_currency_basic: A→B 後 fx_avg 繼承 + TWD 成本守恆")


def test_switch_same_currency_with_fee() -> None:
    """同幣別 switch 含費用：費用造成 B 端 units 減少 → ROI 反映費用。"""
    led_a = Ledger(fund_code="A", currency="USD")
    led_b = Ledger(fund_code="B", currency="USD")
    led_a.subscribe(amount_twd=300000.0, fx_rate=30.0, nav=10.0, txn_date=date(2026, 1, 1))
    # 1000 units × 12 NAV = 12000 USD redeem; fee 100 USD → 11900 USD / 6 NAV = 1983.33 units
    res = Switch.switch_same_currency(
        ledger_from=led_a, ledger_to=led_b, units_to_redeem=None,
        nav_from_redeem=12.0, nav_to_buy=6.0, fee_orig=100.0,
        txn_date=date(2026, 6, 1),
    )
    assert_close(res.units_added_to, 11900.0 / 6.0, tol=0.01, msg="費用造成 units 減少")
    # B net_inv 仍是 300,000（成本守恆，不扣費）
    assert_close(led_b.position.net_investment_twd, 300000.0, tol=1.0, msg="B 成本守恆（不扣費）")
    # 對比：若沒轉，1000 units @ NAV 12, FX 31 = 372,000；ROI=24.0%
    # 轉後 B @ NAV 6, FX 31 = 1983.33 × 6 × 31 = 368,899；ROI=22.97%
    # 差距約 1% = 100 USD / 1000 USD ≈ 1%
    no_switch_value = 1000.0 * 12.0 * 31.0  # 假設 A 沒轉的價值
    switch_value = led_b.position.value_twd(6.0, 31.0)
    fee_drag_pct = (no_switch_value - switch_value) / no_switch_value
    assert 0.005 < fee_drag_pct < 0.015, f"費用拖累應約 1%（實際 {fee_drag_pct:.2%}）"
    print(f"✅ switch_same_currency_with_fee: 費用拖累 {fee_drag_pct:.2%}")


def test_switch_partial_redeem() -> None:
    """部分贖回：A 端剩餘 units 的 cost_unit/fx_avg 不變。"""
    led_a = Ledger(fund_code="A", currency="USD")
    led_b = Ledger(fund_code="B", currency="USD")
    led_a.subscribe(amount_twd=300000.0, fx_rate=30.0, nav=10.0, txn_date=date(2026, 1, 1))
    res = Switch.switch_same_currency(
        ledger_from=led_a, ledger_to=led_b, units_to_redeem=400.0,
        nav_from_redeem=12.0, nav_to_buy=6.0, fee_orig=0.0,
        txn_date=date(2026, 6, 1),
    )
    assert_close(res.units_redeemed_from, 400.0, msg="redeemed partial")
    assert_close(led_a.position.units, 600.0, msg="A 剩 600")
    # A 剩餘部位的 cost_unit/fx_avg/cost_unit_with_div 不變
    assert_close(led_a.position.cost_unit, 10.0, msg="A cost_unit 不變")
    assert_close(led_a.position.fx_avg, 30.0, msg="A fx_avg 不變")
    # A 剩餘 net_inv = 600 × 10 × 30 = 180,000
    assert_close(led_a.position.net_investment_twd, 180000.0, tol=0.5, msg="A 剩餘 net_inv")
    # B 收到的 TWD 成本 = 400 × 10 × 30 = 120,000
    assert_close(res.twd_cost_basis_transferred, 120000.0, msg="B 收到的 TWD 成本")
    print("✅ switch_partial_redeem: A 部分贖回後成本基底守恆")


def test_switch_cross_currency() -> None:
    """跨幣別 switch：USD → EUR，B 端 fx_avg 採當日 EUR/TWD 即期。"""
    led_a = Ledger(fund_code="A_USD", currency="USD")
    led_b = Ledger(fund_code="B_EUR", currency="EUR")
    led_a.subscribe(amount_twd=300000.0, fx_rate=30.0, nav=10.0, txn_date=date(2026, 1, 1))
    # 1000 USD × 0.92 (USD→EUR) = 920 EUR; fee 0; / nav_b 5 = 184 units
    res = Switch.switch_cross_currency(
        ledger_from=led_a, ledger_to=led_b, units_to_redeem=100.0,
        nav_from_redeem=12.0, nav_to_buy=5.0,
        cross_rate=0.92,
        fx_to_at_switch_twd=33.0,
        fee_orig=0.0, txn_date=date(2026, 6, 1),
    )
    # redeem 100 × 12 = 1200 USD; → 1200 × 0.92 = 1104 EUR; / 5 = 220.8 EUR units
    assert_close(res.proceeds_after_fee_orig, 1200.0, msg="proceeds USD")
    assert_close(res.proceeds_in_to_currency, 1104.0, msg="proceeds EUR")
    assert_close(res.units_added_to, 220.8, tol=0.01, msg="B units")
    assert_close(res.fx_avg_inherited, 33.0, msg="B fx_avg 採當日 EUR/TWD")
    # TWD 成本基底 = 100 × 10 × 30 = 30,000
    assert_close(res.twd_cost_basis_transferred, 30000.0, msg="TWD 成本基底")
    # B cost_unit = 30000 / (220.8 × 33) = 4.118
    expected_cu = 30000.0 / (220.8 * 33.0)
    assert_close(res.cost_unit_to_basis, expected_cu, tol=0.001, msg="B cost_unit 反推")
    # B net_inv 守恆 = 30,000
    assert_close(led_b.position.net_investment_twd, 30000.0, tol=1.0, msg="B net_inv 守恆")
    print(f"✅ switch_cross_currency: USD→EUR cross_rate=0.92, B units={res.units_added_to:.2f}")


def test_switch_invalid_currency_pairs() -> None:
    """同幣別函式拒絕不同幣別、跨幣別函式拒絕同幣別。"""
    led_a_usd = Ledger(fund_code="A", currency="USD")
    led_b_eur = Ledger(fund_code="B", currency="EUR")
    led_a_usd.subscribe(amount_twd=300000.0, fx_rate=30.0, nav=10.0, txn_date=date(2026, 1, 1))
    try:
        Switch.switch_same_currency(led_a_usd, led_b_eur, None, 12.0, 5.0, 0.0, date(2026, 6, 1))
    except ValueError:
        pass
    else:
        raise AssertionError("應 raise: 同幣別函式不能用於不同幣別")
    led_b_usd = Ledger(fund_code="B", currency="USD")
    try:
        Switch.switch_cross_currency(
            led_a_usd, led_b_usd, None, 12.0, 5.0,
            cross_rate=1.0, fx_to_at_switch_twd=30.0, fee_orig=0.0,
            txn_date=date(2026, 6, 1),
        )
    except ValueError:
        pass
    else:
        raise AssertionError("應 raise: 跨幣別函式不能用於相同幣別")
    print("✅ switch_invalid_currency_pairs")


def test_switch_preserves_with_div_ratio() -> None:
    """轉換後 B 的 cost_unit_with_div / cost_unit 比例 = A 的（含息折扣傳承）。"""
    led_a = Ledger(fund_code="A", currency="USD")
    led_b = Ledger(fund_code="B", currency="USD")
    led_a.subscribe(amount_twd=300000.0, fx_rate=30.0, nav=10.0, txn_date=date(2026, 1, 1))
    led_a.dividend_cash(div_per_unit=2.0, fx_rate=31.0, txn_date=date(2026, 3, 1), nav_at_div=10.0)
    # virtual_units = 1000 × 2 / 10 = 200; cost_with_div = 10 × 1000 / 1200 = 8.3333
    ratio_a = led_a.position.cost_unit_with_div / led_a.position.cost_unit
    assert_close(ratio_a, 8.3333 / 10.0, tol=0.001, msg="A 含息折扣 ratio")
    Switch.switch_same_currency(
        led_a, led_b, None, nav_from_redeem=11.0, nav_to_buy=5.5,
        fee_orig=0.0, txn_date=date(2026, 6, 1),
    )
    ratio_b = led_b.position.cost_unit_with_div / led_b.position.cost_unit
    assert_close(ratio_b, ratio_a, tol=0.001, msg="B 應繼承 A 的含息折扣比例")
    print(f"✅ switch_preserves_with_div_ratio: ratio={ratio_b:.4f}")


# ═══ Phase 2 測試：XIRR ═════════════════════════════════════════════════════


def test_xirr_simple_one_year() -> None:
    """單筆投資、一年後翻倍 → XIRR ≈ 100%。"""
    led = Ledger(fund_code="T")
    led.subscribe(amount_twd=100000.0, fx_rate=30.0, nav=10.0, txn_date=date(2025, 1, 1))
    # 一年後 NAV 漲 → value_twd = 200,000
    irr = calculate_xirr(led.transactions, current_value_twd=200000.0, today=date(2026, 1, 1))
    assert_close(irr, 1.0, tol=0.01, msg="一年翻倍 XIRR")
    print(f"✅ xirr_simple_one_year: {irr:+.2%}")


def test_xirr_with_dividends() -> None:
    """含現金配息：XIRR 應反映時間價值，>= 簡單帳面 ROI。"""
    led = Ledger(fund_code="T")
    led.subscribe(amount_twd=100000.0, fx_rate=30.0, nav=10.0, txn_date=date(2025, 1, 1))
    # 半年後配 5000 TWD
    # cost_unit_at_buy = 10 USD, units = 100000/30/10 = 333.333
    # div_per_unit = 5000 / (333.333 × 30) = 0.5 USD/unit
    led.dividend_cash(
        div_per_unit=0.5, fx_rate=30.0, txn_date=date(2025, 7, 1), nav_at_div=10.0
    )
    # 一年後價值 100,000（NAV 不變）→ XIRR ≈ 5%
    irr = calculate_xirr(led.transactions, current_value_twd=100000.0, today=date(2026, 1, 1))
    # 100k 投入 + 5k 半年回 + 100k 一年取 → IRR 應約 5%
    assert 0.03 < irr < 0.07, f"含息 XIRR 應約 5%，實際 {irr:+.2%}"
    print(f"✅ xirr_with_dividends: {irr:+.2%}")


def test_xirr_two_subscriptions() -> None:
    """兩筆買入 + 終值：XIRR 加權考量資金時間。"""
    led = Ledger(fund_code="T")
    led.subscribe(amount_twd=100000.0, fx_rate=30.0, nav=10.0, txn_date=date(2025, 1, 1))
    led.subscribe(amount_twd=100000.0, fx_rate=30.0, nav=10.0, txn_date=date(2025, 7, 1))
    # 一年後總價值 220,000
    irr = calculate_xirr(led.transactions, current_value_twd=220000.0, today=date(2026, 1, 1))
    # 第一筆 100k 持 1 年（10% 絕對報酬 ≈ 10% IRR）
    # 第二筆 100k 持 0.5 年（10% 絕對報酬 ≈ 21% 年化 IRR）
    # 加權後 XIRR ≈ 13-14%（驗算：100k×1.1344 + 100k×1.1344^0.5 ≈ 220k）
    assert 0.10 < irr < 0.18, f"雙筆 XIRR 應約 13-14%，實際 {irr:+.2%}"
    print(f"✅ xirr_two_subscriptions: {irr:+.2%}")


def test_xirr_no_solution_returns_zero() -> None:
    """單向現金流（沒有正反現金流）→ 回傳 0.0。"""
    led = Ledger(fund_code="T")
    led.subscribe(amount_twd=100000.0, fx_rate=30.0, nav=10.0, txn_date=date(2025, 1, 1))
    irr = calculate_xirr(led.transactions, current_value_twd=0.0, today=date(2026, 1, 1))
    assert irr == 0.0, f"無正向現金流應回 0，實際 {irr}"
    print("✅ xirr_no_solution_returns_zero")


def test_xirr_ignores_internal_transfers() -> None:
    """switch_* / dividend_reinvest 不算外部現金流，XIRR 不受影響。"""
    led_a = Ledger(fund_code="A", currency="USD")
    led_b = Ledger(fund_code="B", currency="USD")
    led_a.subscribe(amount_twd=100000.0, fx_rate=30.0, nav=10.0, txn_date=date(2025, 1, 1))
    Switch.switch_same_currency(
        led_a, led_b, None, nav_from_redeem=11.0, nav_to_buy=5.5,
        fee_orig=0.0, txn_date=date(2025, 7, 1),
    )
    # 把 A+B 的 transactions 合起來算 XIRR（合併視為「整體投資人視角」）
    all_txns = led_a.transactions + led_b.transactions
    # B 終值 @ NAV 6, FX 31 = (100000/30/10 × 11 / 5.5) × 6 × 31 = 666.666 × 6 × 31 = 124000
    n_b = (100000.0 / 30.0 / 10.0) * 11.0 / 5.5
    final_value = n_b * 6.0 * 31.0
    irr = calculate_xirr(all_txns, current_value_twd=final_value, today=date(2026, 1, 1))
    # 一年回報 24% → XIRR ~ 24%
    assert 0.20 < irr < 0.30, f"含 switch 的 XIRR 應約 24%，實際 {irr:+.2%}"
    print(f"✅ xirr_ignores_internal_transfers: {irr:+.2%}")


# ═══ Phase 3 測試：JSON round-trip + SQLAlchemy ORM ════════════════════════


def test_json_roundtrip_simple() -> None:
    """to_dict() → from_dict() → 等價（無 switch 場景）。"""
    import json
    led = Ledger(fund_code="JSON_T", currency="USD")
    led.subscribe(amount_twd=300000.0, fx_rate=30.0, nav=10.0, txn_date=date(2025, 1, 1))
    led.dividend_cash(div_per_unit=0.5, fx_rate=31.0, txn_date=date(2025, 4, 1), nav_at_div=11.0)
    led.dividend_reinvest(new_units=20.0, nav_at_div=12.0, txn_date=date(2025, 7, 1))
    payload = json.dumps(led.to_dict())  # 確認可序列化為 JSON 字串
    restored = Ledger.from_dict(json.loads(payload))
    assert_close(restored.position.units, led.position.units, msg="units")
    assert_close(restored.position.cost_unit, led.position.cost_unit, msg="cost_unit")
    assert_close(restored.position.fx_avg, led.position.fx_avg, msg="fx_avg")
    assert_close(
        restored.position.cost_unit_with_div, led.position.cost_unit_with_div,
        msg="cost_unit_with_div",
    )
    assert_close(
        restored.position.dividends_received_twd, led.position.dividends_received_twd,
        msg="div_twd",
    )
    assert len(restored.transactions) == 3
    print("✅ json_roundtrip_simple")


def test_json_roundtrip_with_switch() -> None:
    """含 switch_in/out 的完整生命週期：to_dict round-trip 必須完全等價。"""
    import json
    led_a = Ledger(fund_code="A", currency="USD")
    led_b = Ledger(fund_code="B", currency="USD")
    led_a.subscribe(amount_twd=300000.0, fx_rate=30.0, nav=10.0, txn_date=date(2025, 1, 1))
    led_a.dividend_cash(div_per_unit=0.3, fx_rate=31.0, txn_date=date(2025, 3, 1), nav_at_div=10.5)
    Switch.switch_same_currency(
        led_a, led_b, units_to_redeem=500.0,
        nav_from_redeem=11.0, nav_to_buy=5.5, fee_orig=10.0,
        txn_date=date(2025, 6, 1),
    )
    # B 端 round-trip
    b_restored = Ledger.from_dict(json.loads(json.dumps(led_b.to_dict())))
    for f in ("units", "cost_unit", "fx_avg", "cost_unit_with_div", "dividends_received_twd"):
        a, b = getattr(b_restored.position, f), getattr(led_b.position, f)
        assert_close(a, b, tol=1e-6, msg=f"B.{f}")
    # A 端 round-trip
    a_restored = Ledger.from_dict(json.loads(json.dumps(led_a.to_dict())))
    for f in ("units", "cost_unit", "fx_avg", "cost_unit_with_div", "dividends_received_twd"):
        a, b = getattr(a_restored.position, f), getattr(led_a.position, f)
        assert_close(a, b, tol=1e-6, msg=f"A.{f}")
    print("✅ json_roundtrip_with_switch（含 switch_in/out 完全等價）")


def test_switch_one_to_many_conservation() -> None:
    """T7-C 1→N 組轉換守恆性：模擬 UI 拆解邏輯。

    場景：
      A: 1000 units, cost_unit=10.0 USD, fx_avg=30.0 → net_investment = 300,000 TWD
      賣 30% A → 300 units 分配給 B1:50% / B2:30% / B3:20% (同幣別 USD)
    驗證：
      1. A.cost_unit / A.fx_avg 賣後完全不變
      2. Σ B[i].net_investment_twd ≈ 賣出 units × A.cost_unit_orig × A.fx_avg_orig
      3. A.units = 1000 - 300 = 700
    """
    led_a = Ledger(fund_code="A", currency="USD")
    led_a.subscribe(amount_twd=300000.0, fx_rate=30.0, nav=10.0,
                    txn_date=date(2025, 1, 1))
    cost_orig = led_a.position.cost_unit
    fx_orig   = led_a.position.fx_avg
    units_redeem_total = led_a.position.units * 0.30  # 300 units

    led_b1 = Ledger(fund_code="B1", currency="USD")
    led_b2 = Ledger(fund_code="B2", currency="USD")
    led_b3 = Ledger(fund_code="B3", currency="USD")
    weights = [("B1", led_b1, 0.50), ("B2", led_b2, 0.30), ("B3", led_b3, 0.20)]

    used_units = 0.0
    for idx, (name, led_b, w) in enumerate(weights):
        if idx == len(weights) - 1:
            chunk = units_redeem_total - used_units
        else:
            chunk = units_redeem_total * w
            used_units += chunk
        Switch.switch_same_currency(
            ledger_from=led_a, ledger_to=led_b,
            units_to_redeem=chunk,
            nav_from_redeem=12.0, nav_to_buy=8.0,
            fee_orig=0.0, txn_date=date(2025, 6, 1),
        )

    # 驗證 1: A.cost_unit / fx_avg 不變
    assert_close(led_a.position.cost_unit, cost_orig, tol=1e-9, msg="A.cost_unit 不變")
    assert_close(led_a.position.fx_avg,   fx_orig,   tol=1e-9, msg="A.fx_avg 不變")

    # 驗證 2: Σ B.net_investment_twd ≈ 賣出 units × cost × fx (守恆)
    expected = units_redeem_total * cost_orig * fx_orig  # 300 × 10 × 30 = 90,000
    actual = sum(b.position.net_investment_twd
                 for _, b, _ in weights)
    assert_close(actual, expected, tol=1.0, msg="TWD 成本基礎 1→N 守恆")

    # 驗證 3: A 剩餘單位
    assert_close(led_a.position.units, 700.0, tol=1e-9, msg="A 賣後 700 units")
    print(f"✅ switch_one_to_many_conservation: "
          f"3 買方 Σ TWD={actual:,.2f} ≈ 期望 {expected:,.2f}, "
          f"A.cost_unit 維持 {cost_orig}")


def test_scenario_isolation_baseline_not_polluted() -> None:
    """T7 v18.4 方案隔離：snapshot → run → restore 不污染 baseline。

    模擬 UI 暫存方案邏輯：snapshot baseline → 在 ledger 上跑 subscribe →
    再用 from_dict 還原 baseline → 主帳本應與快照前完全一致。
    """
    import json
    led_a = Ledger(fund_code="A", currency="USD")
    led_a.subscribe(amount_twd=300000.0, fx_rate=30.0, nav=10.0,
                    txn_date=date(2025, 1, 1))
    baseline_units = led_a.position.units
    baseline_cost  = led_a.position.cost_unit
    baseline_fx    = led_a.position.fx_avg

    # 1. snapshot baseline
    snap = json.loads(json.dumps(led_a.to_dict()))

    # 2. 在 ledger 上跑「方案」操作（subscribe 加碼）
    led_a.subscribe(amount_twd=500000.0, fx_rate=31.0, nav=11.0,
                    txn_date=date(2025, 6, 1))
    # 確認操作確實改變了 ledger
    assert led_a.position.units > baseline_units, "方案執行未改變 ledger"

    # 3. restore baseline
    restored = Ledger.from_dict(snap)

    # 4. 驗證 baseline 完全保持
    assert_close(restored.position.units, baseline_units,
                 tol=1e-9, msg="baseline.units 不變")
    assert_close(restored.position.cost_unit, baseline_cost,
                 tol=1e-9, msg="baseline.cost_unit 不變")
    assert_close(restored.position.fx_avg, baseline_fx,
                 tol=1e-9, msg="baseline.fx_avg 不變")
    print(
        f"✅ scenario_isolation_baseline_not_polluted: "
        f"baseline units={baseline_units:.4f} cost={baseline_cost:.4f} "
        f"fx={baseline_fx:.4f} 完全還原"
    )


def test_switch_many_to_many_conservation() -> None:
    """T7-C v18.5 M→N 複合轉換守恆性。

    場景：
      A: 1000 units, cost=10.0 USD, fx=30.0 → invest = 300,000 TWD
      B:  500 units, cost=20.0 USD, fx=31.0 → invest = 310,000 TWD
      A 賣 10% (100 units) → 全配給 C
      B 賣 20% (100 units) → 50% 配 D + 50% 配 E
    驗證：
      1. A.cost / fx_avg、B.cost / fx_avg 完全不變
      2. Σ 全部 buyer.net_investment_twd ≈
         (A 100×10×30) + (B 100×20×31) = 30,000 + 62,000 = 92,000 TWD
      3. A.units = 900；B.units = 400
    """
    led_a = Ledger(fund_code="A", currency="USD")
    led_b = Ledger(fund_code="B", currency="USD")
    led_a.subscribe(amount_twd=300000.0, fx_rate=30.0, nav=10.0,
                    txn_date=date(2025, 1, 1))
    led_b.subscribe(amount_twd=310000.0, fx_rate=31.0, nav=20.0,
                    txn_date=date(2025, 1, 1))
    cost_a, fx_a = led_a.position.cost_unit, led_a.position.fx_avg
    cost_b, fx_b = led_b.position.cost_unit, led_b.position.fx_avg

    led_c = Ledger(fund_code="C", currency="USD")
    led_d = Ledger(fund_code="D", currency="USD")
    led_e = Ledger(fund_code="E", currency="USD")

    # A 賣 10% 全配 C
    a_redeem = led_a.position.units * 0.10
    Switch.switch_same_currency(
        ledger_from=led_a, ledger_to=led_c,
        units_to_redeem=a_redeem,
        nav_from_redeem=11.0, nav_to_buy=8.0,
        fee_orig=0.0, txn_date=date(2025, 6, 1),
    )

    # B 賣 20% 配 D 50% / E 50%
    b_redeem_total = led_b.position.units * 0.20
    b_to_d = b_redeem_total * 0.50
    b_to_e = b_redeem_total - b_to_d  # 浮點殘差吸收
    Switch.switch_same_currency(
        ledger_from=led_b, ledger_to=led_d,
        units_to_redeem=b_to_d,
        nav_from_redeem=22.0, nav_to_buy=15.0,
        fee_orig=0.0, txn_date=date(2025, 6, 1),
    )
    Switch.switch_same_currency(
        ledger_from=led_b, ledger_to=led_e,
        units_to_redeem=b_to_e,
        nav_from_redeem=22.0, nav_to_buy=12.0,
        fee_orig=0.0, txn_date=date(2025, 6, 1),
    )

    # 驗證 1: A/B baseline cost & fx 不變
    assert_close(led_a.position.cost_unit, cost_a, tol=1e-9, msg="A.cost_unit 不變")
    assert_close(led_a.position.fx_avg,    fx_a,   tol=1e-9, msg="A.fx_avg 不變")
    assert_close(led_b.position.cost_unit, cost_b, tol=1e-9, msg="B.cost_unit 不變")
    assert_close(led_b.position.fx_avg,    fx_b,   tol=1e-9, msg="B.fx_avg 不變")

    # 驗證 2: Σ buyer.net_investment_twd ≈ 賣方端理論搬移
    expected = (a_redeem * cost_a * fx_a) + (b_redeem_total * cost_b * fx_b)
    actual = (led_c.position.net_investment_twd
              + led_d.position.net_investment_twd
              + led_e.position.net_investment_twd)
    assert_close(actual, expected, tol=1.0, msg="M→N TWD 守恆")

    # 驗證 3: 賣方剩餘單位
    assert_close(led_a.position.units, 900.0, tol=1e-9, msg="A 剩 900")
    assert_close(led_b.position.units, 400.0, tol=1e-9, msg="B 剩 400")
    print(
        f"✅ switch_many_to_many_conservation: 2→3 共 3 筆 switch，"
        f"Σ TWD={actual:,.2f} ≈ 期望 {expected:,.2f}, "
        f"A.cost={cost_a}, B.cost={cost_b} 全保持"
    )


if __name__ == "__main__":
    # Phase 1 — 引擎核心（13）
    test_chubb_11_fields_reproduction()
    test_subscribe_first_buy()
    test_subscribe_weighted_average()
    test_dividend_cash_drops_cost_with_div()
    test_dividend_cash_no_nav_only_accumulates()
    test_dividend_reinvest()
    test_ghost_portfolio_b_wins()
    test_ghost_portfolio_a_wins()
    test_ghost_portfolio_with_dividends()
    test_zero_division_guard()
    test_subscribe_invalid_args()
    test_dividend_on_empty_position_raises()
    test_full_chubb_lifecycle()
    # Phase 2 — Switching（6）
    test_switch_same_currency_basic()
    test_switch_same_currency_with_fee()
    test_switch_partial_redeem()
    test_switch_cross_currency()
    test_switch_invalid_currency_pairs()
    test_switch_preserves_with_div_ratio()
    # Phase 2 — XIRR（5）
    test_xirr_simple_one_year()
    test_xirr_with_dividends()
    test_xirr_two_subscriptions()
    test_xirr_no_solution_returns_zero()
    test_xirr_ignores_internal_transfers()
    # JSON round-trip（2）
    test_json_roundtrip_simple()
    test_json_roundtrip_with_switch()
    # T7-C 1→N（v18.3 新增 1）
    test_switch_one_to_many_conservation()
    # T7 v18.4 方案隔離（1）
    test_scenario_isolation_baseline_not_polluted()
    # T7 v18.5 M→N 守恆（1）
    test_switch_many_to_many_conservation()
    print("\n🎉 全部 29 項測試通過（Phase 1: 13 + Phase 2: 11 + JSON: 2 + 1→N: 1 + scenario: 1 + M→N: 1）")
