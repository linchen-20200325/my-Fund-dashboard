"""services/macro_tw_local.py 完整 coverage — 34 case 鏡像 stock dashboard
tests/test_macro_helpers.py (TestDetectMkGoldenInflection + TestClassifyLongTermRegime
+ TestClassifyShortTermRegime)。

Phase v19.23：Fund 端首次取得台股本地視角總經判讀能力，與既有
services/macro_service.py::identify_regime() 並存互補。
"""
from __future__ import annotations

from services.macro_tw_local import (
    classify_long_term_regime,
    classify_short_term_regime,
    detect_mk_golden_inflection,
)
from shared.colors import TRAFFIC_GREEN, TRAFFIC_YELLOW


# ════════════════════════════════════════════════════════════════════════════
# §1 detect_mk_golden_inflection — 12 case
# ════════════════════════════════════════════════════════════════════════════
class TestDetectMkGoldenInflection:
    """MK 黃金拐點：CPI YoY × Fed Funds Rate 雙頂回落（鏡像 stock v18.169）。"""

    def test_strong_signal_cpi_drop_fed_drop(self):
        # CPI 月降 0.3ppt + Fed 月降 0.08ppt → 強訊號 ⭐
        sig = detect_mk_golden_inflection(3.0, 3.3, 5.25, 5.33)
        assert sig is not None
        assert sig['strength'] == 'strong'
        assert sig['color'] == TRAFFIC_GREEN  # v19.252 Phase 4A SSOT
        assert '⭐' in sig['icon']
        assert 'MK 黃金拐點' in sig['label']

    def test_strong_signal_cpi_drop_fed_flat(self):
        # CPI 月降 0.25ppt + Fed 持平 → 強訊號 ⭐
        sig = detect_mk_golden_inflection(3.0, 3.25, 5.33, 5.33)
        assert sig is not None
        assert sig['strength'] == 'strong'
        assert '持平' in sig['detail']

    def test_weak_signal_cpi_mild_drop_fed_drop(self):
        # CPI 月降 0.1ppt + Fed 月降 0.08ppt → 弱訊號 ✅
        sig = detect_mk_golden_inflection(3.2, 3.3, 5.25, 5.33)
        assert sig is not None
        assert sig['strength'] == 'weak'
        assert sig['color'] == TRAFFIC_YELLOW  # v19.252 Phase 4A SSOT
        assert 'MK 拐點觀察中' in sig['label']

    def test_no_signal_cpi_rising(self):
        assert detect_mk_golden_inflection(3.4, 3.0, 5.25, 5.33) is None

    def test_no_signal_fed_rising(self):
        assert detect_mk_golden_inflection(3.0, 3.3, 5.5, 5.33) is None

    def test_no_signal_cpi_flat(self):
        # CPI 持平（diff 在噪聲區 ±0.05） → 無訊號
        assert detect_mk_golden_inflection(3.32, 3.30, 5.25, 5.33) is None
        assert detect_mk_golden_inflection(3.30, 3.30, 5.25, 5.33) is None

    def test_no_signal_missing_data(self):
        assert detect_mk_golden_inflection(None, 3.3, 5.25, 5.33) is None
        assert detect_mk_golden_inflection(3.0, None, 5.25, 5.33) is None
        assert detect_mk_golden_inflection(3.0, 3.3, None, 5.33) is None
        assert detect_mk_golden_inflection(3.0, 3.3, 5.25, None) is None

    def test_invalid_data_returns_none(self):
        assert detect_mk_golden_inflection('abc', 3.3, 5.25, 5.33) is None

    def test_detail_text_includes_values(self):
        sig = detect_mk_golden_inflection(2.8, 3.3, 5.0, 5.33)
        assert sig is not None
        assert '2.80' in sig['detail']
        assert '3.30' in sig['detail']
        assert '5.00' in sig['detail']
        assert '5.33' in sig['detail']

    def test_threshold_boundary_strong_vs_weak(self):
        sig_strong = detect_mk_golden_inflection(3.0, 3.20, 5.33, 5.33)
        assert sig_strong is not None and sig_strong['strength'] == 'strong'
        sig_weak = detect_mk_golden_inflection(3.01, 3.20, 5.33, 5.33)
        assert sig_weak is not None and sig_weak['strength'] == 'weak'

    def test_boundary_cpi_just_above_noise(self):
        sig = detect_mk_golden_inflection(3.24, 3.30, 5.33, 5.33)
        assert sig is not None and sig['strength'] == 'weak'

    def test_fed_slight_uptick_within_noise_still_signals(self):
        sig = detect_mk_golden_inflection(3.0, 3.3, 5.36, 5.33)
        assert sig is not None and sig['strength'] == 'strong'


# ════════════════════════════════════════════════════════════════════════════
# §2 classify_long_term_regime — 11 case
# ════════════════════════════════════════════════════════════════════════════
class TestClassifyLongTermRegime:
    """長期總經 12M 視角分類（景氣大循環位階）— 鏡像 stock v18.170。"""

    def test_growth_regime_full_bull(self):
        mk = detect_mk_golden_inflection(2.0, 2.5, 4.5, 4.75)
        r = classify_long_term_regime(2.0, 4.5, 4.75, 35, 56, mk)
        assert r['regime'].startswith('🟢')
        assert r['score'] >= 1.0
        assert r['suggest_pct'] == '80%+'

    def test_recovery_regime_mid_bull(self):
        r = classify_long_term_regime(3.0, 5.25, 5.25, 27, 53, None)
        assert r['regime'].startswith('🔵')
        assert 0.0 <= r['score'] < 1.0

    def test_overheat_regime_caution(self):
        # CPI 4.5% + Fed 持平 + NDC 綠 + PMI 49 + 無 MK → 🟡 過熱
        r = classify_long_term_regime(4.5, 5.5, 5.5, 25, 49, None)
        assert r['regime'].startswith('🟡')
        assert -1.0 <= r['score'] < 0.0

    def test_recession_regime_defense(self):
        r = classify_long_term_regime(5.5, 5.5, 5.0, 15, 47, None)
        assert r['regime'].startswith('🔴')
        assert r['score'] < -1.0
        assert r['suggest_pct'] == '<30%'

    def test_insufficient_data_returns_grey(self):
        r = classify_long_term_regime(None, None, None, None, None, None)
        assert r['regime'] == '⚪ 資料不足'
        assert r['score'] == 0.0
        assert r['suggest_pct'] == 'N/A'

    def test_mk_alone_not_enough(self):
        # MK 訊號獨自不該驅動 regime
        mk = detect_mk_golden_inflection(3.0, 3.3, 5.25, 5.33)
        r = classify_long_term_regime(None, None, None, None, None, mk)
        assert r['regime'] == '⚪ 資料不足'

    def test_partial_data_works(self):
        r = classify_long_term_regime(2.0, None, None, None, 56, None)
        assert r['regime'] != '⚪ 資料不足'
        assert len(r['components']) == 3  # CPI + PMI + MK 拐點(0)

    def test_components_structure(self):
        r = classify_long_term_regime(2.0, 5.0, 5.0, 27, 53, None)
        for comp in r['components']:
            assert len(comp) == 3
            name, score, weight = comp
            assert isinstance(name, str)
            assert isinstance(score, int)
            assert isinstance(weight, int)

    def test_invalid_data_graceful(self):
        r = classify_long_term_regime('bad', float('nan'), None, 'x', None, None)
        assert r['regime'] == '⚪ 資料不足'

    def test_score_range_clamp(self):
        r = classify_long_term_regime(1.5, 4.0, 4.5, 40, 58, None)
        assert -2.0 <= r['score'] <= 2.0

    def test_mk_strong_vs_weak_boost(self):
        mk_strong = {'strength': 'strong'}
        mk_weak = {'strength': 'weak'}
        r_s = classify_long_term_regime(3.0, 5.0, 5.0, 27, 50, mk_strong)
        r_w = classify_long_term_regime(3.0, 5.0, 5.0, 27, 50, mk_weak)
        assert r_s['score'] > r_w['score']


# ════════════════════════════════════════════════════════════════════════════
# §3 classify_short_term_regime — 11 case
# ════════════════════════════════════════════════════════════════════════════
class TestClassifyShortTermRegime:
    """短期總經 1Q 視角分類（對齊台股財報季偏向）— 鏡像 stock v18.170。"""

    def test_bullish_full_strong(self):
        r = classify_short_term_regime(18, 55, 14, 7, 3.0, 3.3)
        assert r['regime'].startswith('⚡')
        assert r['score'] >= 0.8

    def test_neutral_mixed_signals(self):
        r = classify_short_term_regime(3, 51, 22, 1, 3.0, 3.05)
        assert r['regime'].startswith('⚖️')
        assert -0.3 <= r['score'] < 0.8

    def test_bearish_full_weak(self):
        r = classify_short_term_regime(-10, 47, 32, -8, 3.5, 3.1)
        assert r['regime'].startswith('⚠️')
        assert r['score'] < -0.3

    def test_insufficient_data(self):
        r = classify_short_term_regime(None, None, None, None, None, None)
        assert r['regime'] == '⚪ 資料不足'

    def test_partial_data_export_only(self):
        r = classify_short_term_regime(20, None, None, None, None, None)
        assert r['regime'] != '⚪ 資料不足'
        assert r['score'] > 0

    def test_foreign_investor_streak_positive(self):
        r_buy = classify_short_term_regime(10, 52, 18, 5, 3.0, 3.1)
        r_sell = classify_short_term_regime(10, 52, 18, -5, 3.0, 3.1)
        assert r_buy['score'] > r_sell['score']

    def test_vix_threshold_boundaries(self):
        r_calm = classify_short_term_regime(0, 50, 14, 0, 3.0, 3.0)
        r_panic = classify_short_term_regime(0, 50, 35, 0, 3.0, 3.0)
        assert r_calm['score'] > r_panic['score']

    def test_components_includes_weights(self):
        r = classify_short_term_regime(10, 52, 18, 3, 3.0, 3.2)
        assert len(r['components']) == 5
        names = [c[0] for c in r['components']]
        assert '出口 YoY' in names
        assert '台 PMI' in names
        assert 'VIX 波動' in names
        assert '外資籌碼' in names
        assert 'CPI 月降' in names

    def test_invalid_data_graceful(self):
        r = classify_short_term_regime('bad', 'x', None, 'y', float('nan'), None)
        assert r['regime'] == '⚪ 資料不足'

    def test_cpi_month_drop_boosts_score(self):
        r_drop = classify_short_term_regime(5, 51, 20, 0, 3.0, 3.4)
        r_rise = classify_short_term_regime(5, 51, 20, 0, 3.4, 3.0)
        assert r_drop['score'] > r_rise['score']

    def test_action_message_present(self):
        r = classify_short_term_regime(15, 54, 15, 5, 3.0, 3.3)
        assert r.get('action') and isinstance(r['action'], str)
