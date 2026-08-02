"""4D 評等「資料不足守衛」+ σ≤0 排除(v19.422,稽核 Bug1 修正)。

Bug1:資料稀疏基金(只有 σ 一個維度)被平均成 90 → 評 A「健康優質」,排在完整分析的
B 級之上。修:需 ≥ GRADE_4D_MIN_FACTORS 維度 且 至少一核心維度(配息 or Sharpe),否則
「資料不足以評等」;σ ≤ 0(無效/偽造)不計分。
"""
from services.health.grade import _score_volatility, compute_4d_health


def test_volatility_only_is_insufficient():
    """僅 σ 一個維度 → 資料不足以評等(原本 → A/90)。"""
    r = compute_4d_health(sigma_pct=5.0)
    assert r["grade"] == "—" and r["score"] is None
    assert r["verdict"] == "資料不足以評等"


def test_sigma_zero_or_negative_excluded():
    """σ ≤ 0 = 無效/偽造(真實 σ 恆 > 0)→ 不計分。"""
    assert _score_volatility(0.0) is None
    assert _score_volatility(-3.0) is None
    assert _score_volatility(5.0) == 90            # 正常 σ 照舊


def test_sigma_zero_fund_insufficient():
    """σ fallback=0 的無歷史基金 → volatility None → 資料不足(不再 90/A)。"""
    r = compute_4d_health(sigma_pct=0.0)
    assert r["factors"]["volatility"] is None
    assert r["grade"] == "—"


def test_two_factors_without_core_insufficient():
    """走勢 + 波動兩維度但無核心(配息/Sharpe)→ 資料不足。"""
    r = compute_4d_health(sigma_pct=5.0, ma_dir="up")   # trend=70, vol=90, 無 core
    assert r["factors"]["trend"] == 70 and r["factors"]["volatility"] == 90
    assert r["grade"] == "—" and r["score"] is None


def test_single_core_factor_insufficient():
    """只有配息一個維度(tr1y 不觸發走勢)→ < 2 維度 → 資料不足。"""
    r = compute_4d_health(tr1y_pct=3.0, adr_pct=2.0)    # coverage=95;tr1y=3 不觸發 trend
    assert r["factors"]["coverage"] is not None
    assert r["factors"]["trend"] is None
    assert r["grade"] == "—"


def test_core_plus_second_grades_normally():
    """Sharpe(核心)+ 波動 = 2 維度含核心 → 正常評等。"""
    r = compute_4d_health(sharpe=1.2, sigma_pct=5.0)
    assert r["score"] == 85.0 and r["grade"] == "A"


def test_full_four_factors_regression():
    """完整 4 維(對應 user 截圖 B/78.75)不受守衛影響。"""
    r = compute_4d_health(tr1y_pct=10.0, adr_pct=6.0, sharpe=0.56, sigma_pct=5.0)
    assert round(r["score"], 2) == 78.75 and r["grade"] == "B"
