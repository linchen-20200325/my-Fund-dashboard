"""景氣位階適配標籤(v19.425)。驗:資產 bucket、捕捉精修、順/逆/全景氣/無法判定、regime 正規化、邊界。"""
from services.regime_fit import asset_bucket, normalize_regime, tag_regime_fit


def _fit(cat, role, up, dn, reg):
    return tag_regime_fit(cat, role, up, dn, reg)["fit_vs_current"]


def _best(cat, role, up, dn, reg):
    return set(tag_regime_fit(cat, role, up, dn, reg)["best_fit_regimes"])


# ── 正規化 ──────────────────────────────────────────────
def test_normalize_regime():
    assert normalize_regime("🔴 衰退期") == "衰退"
    assert normalize_regime("減速") == "高峰"
    assert normalize_regime("🟢 成長期") == "擴張"
    assert normalize_regime("復甦/擴張") == "擴張"
    assert normalize_regime("未知") is None and normalize_regime("") is None and normalize_regime(None) is None


# ── 順/逆風 ─────────────────────────────────────────────
def test_equity_headwind_in_recession():
    assert "復甦" in _best("美國科技基金", "🟠 衛星", 110, 95, "衰退")
    assert _fit("美國科技基金", "🟠 衛星", 110, 95, "衰退") == "⚠️ 逆風"


def test_equity_tailwind_in_expansion():
    assert _fit("美國科技基金", "衛星", 110, 95, "擴張") == "✅ 順風"


def test_investment_grade_bond_tailwind_recession():
    assert _best("全球投資等級債券", "衛星", 40, 60, "衰退") == {"高峰", "衰退"}
    assert _fit("全球投資等級債券", "衛星", 40, 60, "衰退") == "✅ 順風"


def test_money_market_recession():
    assert _best("貨幣市場基金", "衛星", None, None, "衰退") == {"衰退"}
    assert _fit("貨幣市場基金", "衛星", None, None, "衰退") == "✅ 順風"


def test_commodity_peak_tailwind():
    r = tag_regime_fit("原物料能源股票", "衛星", 120, 110, "高峰")
    assert r["asset_bucket"] == "原物料資源" and r["fit_vs_current"] == "✅ 順風"


def test_reits_recovery():
    assert _fit("全球不動產REITs", "衛星", 90, 85, "復甦") == "✅ 順風"


def test_high_yield_before_defensive_bond():
    # 「非投資等級債券」= 高收益(風險資產)→ 復甦/擴張,不是防禦債
    r = tag_regime_fit("非投資等級債券", "衛星", 70, 60, "復甦")
    assert r["asset_bucket"] == "高收益債" and r["fit_vs_current"] == "✅ 順風"


def test_commodity_before_equity_ordering():
    r = tag_regime_fit("原物料股票型", "衛星", 100, 90, "擴張")
    assert r["asset_bucket"] == "原物料資源"


# ── 全景氣 / 無法判定 ───────────────────────────────────
def test_multi_asset_all_weather():
    r = tag_regime_fit("全球多重資產", "衛星", None, None, "衰退")
    assert r["best_fit_regimes"] == ["ALL"] and r["fit_vs_current"] == "⚪ 全景氣"


def test_core_role_all_weather():
    assert _fit("全球股票", "🟦 核心", 100, 90, "衰退") == "⚪ 全景氣"


def test_missing_category_na():
    assert _fit("", "衛星", 100, 90, "擴張") == "⬜ 無法判定"


def test_unmatched_category_na_no_forced_equity():
    assert _fit("其他", "衛星", 100, 90, "擴張") == "⬜ 無法判定"


def test_regime_undetected_na_but_best_returned():
    r = tag_regime_fit("科技股票", "衛星", 100, 90, "未知")
    assert r["fit_vs_current"] == "⬜ 無法判定" and r["best_fit_regimes"]


# ── 邊界 ────────────────────────────────────────────────
def test_nan_capture_no_crash():
    r = tag_regime_fit("美國科技基金", "衛星", float("nan"), float("nan"), "擴張")
    assert r["fit_vs_current"] == "✅ 順風"       # 捕捉略過,仍由資產 bucket 判


def test_rationale_transparent():
    r = tag_regime_fit("全球投資等級債券", "衛星", 40, 60, "衰退")
    assert "適配" in r["rationale"] and "衰退" in r["rationale"] and "非買賣建議" in r["rationale"]


def test_never_raises_on_garbage():
    for args in [(None, None, None, None, None), (123, [], "x", {}, object()), ("股", "核心", "a", "b", "z")]:
        r = tag_regime_fit(*args)
        assert r["fit_vs_current"] in ("✅ 順風", "⚠️ 逆風", "⚪ 全景氣", "⬜ 無法判定")
