"""v19.132 tests — _tp_threshold_lines helper 守 SSOT 對齊."""
from __future__ import annotations

import sys
import types


def _stub_modules():
    """Stub plotly + streamlit so ui.tab1_macro 可 import."""
    if "plotly" not in sys.modules:
        class _F:
            def __getattr__(self, n):
                return lambda *a, **k: None
        sys.modules["plotly"] = _F()
        sys.modules["plotly.graph_objects"] = _F()
        sys.modules["plotly.subplots"] = _F()
    if "streamlit" not in sys.modules:
        class _S:
            def __getattr__(self, n):
                return lambda *a, **k: None
            session_state = {}
        sys.modules["streamlit"] = _S()


# v19.174:module-top stub call 拿掉 — 改由 conftest._switch_streamlit_module_per_test
# fixture per-test 裝(避免 stub 污染後續 collect 的 test,例如 AppTest)。
# _stub_modules()


class TestTpThresholdLines:
    """v19.132 sparkline threshold 對齊 SSOT 守衛"""

    def test_sahm_uses_ssot(self):
        from shared.signal_thresholds import SAHM_RECESSION_THRESHOLD
        from ui.tab1_macro import _tp_threshold_lines
        lines = _tp_threshold_lines("sahm_rule")
        assert len(lines) == 1
        assert lines[0][0] == SAHM_RECESSION_THRESHOLD

    def test_cfnai_uses_ssot(self):
        from shared.signal_thresholds import CFNAI_RECESSION_THRESHOLD
        from ui.tab1_macro import _tp_threshold_lines
        lines = _tp_threshold_lines("lei_cfnai")
        assert len(lines) == 1
        assert lines[0][0] == CFNAI_RECESSION_THRESHOLD

    def test_hy_has_two_levels(self):
        from ui.tab1_macro import _tp_threshold_lines
        lines = _tp_threshold_lines("hy_spread")
        assert len(lines) == 2
        # warn 在 crit 之下
        assert lines[0][0] < lines[1][0]
        # warn = 6%, crit = 8%
        assert lines[0][0] == 6.0
        assert lines[1][0] == 8.0

    def test_pmi_yield_at_zero(self):
        """擴散 / 倒掛指標都用零點"""
        from ui.tab1_macro import _tp_threshold_lines
        assert _tp_threshold_lines("pmi_diff")[0][0] == 0.0
        assert _tp_threshold_lines("yield_curve")[0][0] == 0.0

    def test_unknown_key_returns_empty(self):
        from ui.tab1_macro import _tp_threshold_lines
        assert _tp_threshold_lines("nonexistent") == []

    def test_each_line_has_4_fields(self):
        """確保 tuple 結構 (y, dash, color, annotation) 不被破壞"""
        from ui.tab1_macro import _tp_threshold_lines
        for k in ["pmi_diff", "yield_curve", "hy_spread", "sahm_rule", "lei_cfnai"]:
            for line in _tp_threshold_lines(k):
                assert len(line) == 4
                _y, _dash, _color, _txt = line
                assert isinstance(_y, (int, float))
                assert _dash in ("dot", "dash", "solid")
                assert _color.startswith("#")
                assert _txt


class TestRadarThresholdLines:
    """v19.133 短線雷達 10 燈 sparkline threshold 守衛。

    ⚠️ 2026-08-14 稽核 E11 改寫:本組原本**把數字抄在測試裡**,docstring 卻寫著
    「services/risk_radar.py L103-L105 用 cur >= 30 / 25」—— 那句話當時是真的,
    但 v19.157 把全站 VIX 黃燈統一成 22 之後,services 改了、UI 沒改、測試也沒改,
    於是這組測試**反過來把錯誤值鎖死**:畫面畫 25、燈號用 22,線與燈不同步,
    使用者看到「線還沒碰到但燈已經黃了」。sector_rotation 更嚴重 —— services 比的是
    防禦減攻擊的**百分點差**(實機約 −0.84),UI 卻當成比值畫在 1.00 / 1.20,量綱都不對。

    改法:一律 import `services.risk_radar` 的 `RADAR_*` 常數比對。這樣以後
    services 一改,UI 沒跟上就會紅 —— 這才是本組 docstring 一直宣稱在做的事。
    **禁止**再把數字抄回測試裡。
    """

    def test_vix_level_uses_service_thresholds(self):
        """VIX 線必須等於燈號實際用的門檻(v19.157 起黃燈為 22,不是 25)。"""
        from services.risk_radar import RADAR_VIX_RED, RADAR_VIX_YELLOW
        from ui.tab1_macro import _radar_threshold_lines
        lines = _radar_threshold_lines("vix_level")
        assert len(lines) == 2
        assert lines[0][0] == RADAR_VIX_YELLOW
        assert lines[1][0] == RADAR_VIX_RED

    def test_vix_term_struct_uses_service_thresholds(self):
        from services.risk_radar import RADAR_VIX_TS_RED, RADAR_VIX_TS_YELLOW
        from ui.tab1_macro import _radar_threshold_lines
        lines = _radar_threshold_lines("vix_term_struct")
        assert lines[0][0] == RADAR_VIX_TS_YELLOW
        assert lines[1][0] == RADAR_VIX_TS_RED

    def test_move_uses_service_thresholds(self):
        from services.risk_radar import RADAR_MOVE_RED, RADAR_MOVE_YELLOW
        from ui.tab1_macro import _radar_threshold_lines
        lines = _radar_threshold_lines("move_level")
        assert lines[0][0] == RADAR_MOVE_YELLOW
        assert lines[1][0] == RADAR_MOVE_RED

    def test_sector_rotation_uses_service_thresholds(self):
        """量綱守門:這條線是**百分點差**,不是 XLP/XLY 比值。

        舊測試鎖 1.00 / 1.20(比值),而 services 判的是 2pp / 4pp。實機 gap 約 −0.84,
        畫在 1.00 的線上永遠碰不到 —— 一個永遠不會亮的警戒線比沒有線更危險。
        """
        from services.risk_radar import (
            RADAR_SECTOR_GAP_RED_PP,
            RADAR_SECTOR_GAP_YELLOW_PP,
        )
        from ui.tab1_macro import _radar_threshold_lines
        lines = _radar_threshold_lines("sector_rotation")
        assert lines[0][0] == RADAR_SECTOR_GAP_YELLOW_PP
        assert lines[1][0] == RADAR_SECTOR_GAP_RED_PP

    def test_hy_radar_matches_tp_thresholds(self):
        """HY 在短線雷達與拐點桶用同一組 threshold(6/8%)避免顯示不一致"""
        from ui.tab1_macro import _radar_threshold_lines, _tp_threshold_lines
        radar_lines = _radar_threshold_lines("hy_oas_delta")
        tp_lines = _tp_threshold_lines("hy_spread")
        assert radar_lines[0][0] == tp_lines[0][0]
        assert radar_lines[1][0] == tp_lines[1][0]

    def test_pcr_thresholds_present(self):
        """Put/Call 紅線舊值 1.50 比燈號門檻(1.20)還高 —— 燈亮了線還沒到。"""
        from services.risk_radar import RADAR_PCR_RED, RADAR_PCR_YELLOW
        from ui.tab1_macro import _radar_threshold_lines
        lines = _radar_threshold_lines("put_call_ratio")
        assert lines[0][0] == RADAR_PCR_YELLOW
        assert lines[1][0] == RADAR_PCR_RED

    def test_every_radar_line_matches_its_signal_constant(self):
        """漂移總鎖:凡是有 RADAR_*_YELLOW/RED 常數的雷達鍵,線一律 == 常數。

        逐條寫的斷言只守得住今天列出的這幾個鍵;這條掃全表,
        新增雷達燈時只要常數命名照慣例,就自動被守住(PROCESS §4)。
        """
        import services.risk_radar as _RR
        from ui.tab1_macro import _radar_threshold_lines

        _pairs = {
            "vix_level": ("RADAR_VIX_YELLOW", "RADAR_VIX_RED"),
            "vix_term_struct": ("RADAR_VIX_TS_YELLOW", "RADAR_VIX_TS_RED"),
            "move_level": ("RADAR_MOVE_YELLOW", "RADAR_MOVE_RED"),
            "sector_rotation": ("RADAR_SECTOR_GAP_YELLOW_PP", "RADAR_SECTOR_GAP_RED_PP"),
            "put_call_ratio": ("RADAR_PCR_YELLOW", "RADAR_PCR_RED"),
        }
        for _key, (_y, _r) in _pairs.items():
            _lines = _radar_threshold_lines(_key)
            assert len(_lines) == 2, f"{_key} 應有黃/紅兩條線,實得 {len(_lines)}"
            assert _lines[0][0] == getattr(_RR, _y), f"{_key} 黃線與 {_y} 不同步"
            assert _lines[1][0] == getattr(_RR, _r), f"{_key} 紅線與 {_r} 不同步"

    def test_unsupported_radar_keys_empty(self):
        """trend=level 但判斷=delta 的 indicators 不加 hline"""
        from ui.tab1_macro import _radar_threshold_lines
        for k in ("yield_10y_shock", "spx_trend_break", "sox_drop", "asia_overnight"):
            assert _radar_threshold_lines(k) == []

    def test_radar_sparkline_handles_empty_trend(self):
        """空 / 單筆 trend → None,不 raise"""
        from ui.tab1_macro import _make_radar_sparkline
        assert _make_radar_sparkline([], "vix_level", "#ff0000") is None
        assert _make_radar_sparkline(None, "vix_level", "#ff0000") is None
        assert _make_radar_sparkline([1.0], "vix_level", "#ff0000") is None


class TestUsLiquidityCardThresholdLines:
    """v19.188 🌳 長期座標桶 美股流動性卡片 SPEC 線守 SSOT
    (與 services.us_liquidity_engine 各 fetcher 的 color cut-off 同源)。"""

    def test_hy_oas_matches_engine_cutoffs(self):
        from services.us_liquidity_engine import HY_OAS_WARN_PCT, HY_OAS_CRISIS_PCT
        from ui.tab1_macro import _radar_threshold_lines
        lines = _radar_threshold_lines("us_hy_oas")
        assert [lines[0][0], lines[1][0]] == [HY_OAS_WARN_PCT, HY_OAS_CRISIS_PCT]

    def test_m2_yoy_matches_engine_cutoffs(self):
        from services.us_liquidity_engine import M2_YOY_LOOSE_PCT, M2_YOY_HOT_PCT
        from ui.tab1_macro import _radar_threshold_lines
        lines = _radar_threshold_lines("us_m2_yoy")
        assert [lines[0][0], lines[1][0]] == [M2_YOY_LOOSE_PCT, M2_YOY_HOT_PCT]

    def test_rrp_matches_engine_cutoff(self):
        from services.us_liquidity_engine import RRP_DRAIN_BN
        from ui.tab1_macro import _radar_threshold_lines
        lines = _radar_threshold_lines("us_rrp")
        assert len(lines) == 1 and lines[0][0] == RRP_DRAIN_BN

    def test_aaii_matches_engine_cutoffs(self):
        from services.us_liquidity_engine import AAII_EUPHORIA_PCT, AAII_PANIC_PCT
        from ui.tab1_macro import _radar_threshold_lines
        lines = _radar_threshold_lines("us_aaii")
        assert [lines[0][0], lines[1][0]] == [AAII_EUPHORIA_PCT, AAII_PANIC_PCT]

    def test_delta_based_keys_no_lines(self):
        """walcl / hyg_lqd 為 delta-based,無 natural level 線。"""
        from ui.tab1_macro import _radar_threshold_lines
        assert _radar_threshold_lines("us_walcl") == []
        assert _radar_threshold_lines("us_hyg_lqd") == []

    def test_each_us_line_has_4_fields(self):
        from ui.tab1_macro import _radar_threshold_lines
        for k in ("us_hy_oas", "us_m2_yoy", "us_rrp", "us_aaii"):
            for line in _radar_threshold_lines(k):
                assert len(line) == 4
                _y, _dash, _color, _txt = line
                assert isinstance(_y, (int, float))
                assert _dash in ("dot", "dash", "solid")
                assert _color.startswith("#")
                assert _txt
