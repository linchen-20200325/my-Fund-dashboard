"""v19.138 — render smoke test(AppTest 實際 render,擋 production runtime bug)

背景:這輪改動有兩個 bug 是線上才現形(v19.137 UnboundLocalError 物理重排、
v18.282 key 名臆測錯),純 compile + 單元測試擋不住。本檔用 streamlit.testing.v1.AppTest
把改動的 render 函式真的跑一遍,catch uncaught exception。

涵蓋(全改動 render 路徑):
- render_macro_tab(tab1_macro 四桶 + sparkline + Z-Score 矩陣)
- render_data_guard_tab(tab5 資料診斷 + API Key 遮罩)
- render_manual_tab(tab6 系統說明書 + 原理教室)

策略:
- monkeypatch 掉所有網路 fetcher(detect_turning_points / detect_risk_radar / fetch_market_news)
- 灌入真實 shape 的 session_state(indicators / phase_info / alloc dict)
- 容忍 secrets.toml 缺失造成的 st.error(環境性,production 有)
- 失敗即印出 traceback 方便定位

§3.3 SSOT — 測資 shape 對齊 production(alloc 為 dict / indicators 各 key 真實名)
§1 Fail Loud — 任何 uncaught exception 直接 fail
"""
from __future__ import annotations

import sys
import pytest

# 真實 indicators(對齊 services/macro_service 回傳 shape)
_REAL_INDICATORS = {
    # 拐點桶 War Room
    "SAHM": {"value": 0.3, "series": [0.1, 0.2, 0.3]},
    "SLOOS": {"value": 15.0},
    "ADL": {"value": -1.5},
    # 中期 / 情境
    "PMI": {"value": 48.0, "prev": 49.0},
    "CPI": {"value": 3.2},
    "CPI_YOY": {"value": 3.2},
    "UNRATE": {"value": 4.1},
    # 短線雷達
    "VIX": {"value": 22.0},
    "HY_SPREAD": {"value": 5.5, "prev": 5.3},
    "MOVE": {"value": 105.0},
    "PCR": {"value": 1.1},
    # 拐點
    "YIELD_10Y2Y": {"value": -0.3},
    "YIELD_10Y3M": {"value": -0.5},
    "CFNAI": {"value": -0.4},
    # 長期
    "M2": {"value": 3.5},
    "FED_BS": {"value": -2.0},
    "DXY": {"value": 104.0},
    "COPPER": {"value": 1.5},
    # Z-Score 矩陣其餘(避免空表)
    "PPI": {"value": 2.0},
    "FED_RATE": {"value": 4.5},
    "INFL_EXP_5Y": {"value": 2.3},
    "UNEMPLOYMENT": {"value": 4.1},
    "CONT_CLAIMS": {"value": 180},
    "CONSUMER_CONF": {"value": 100},
    "JOBLESS": {"value": 22},
    "M2_WEEKLY": {"value": 3.4},
    "PERMIT_HOUSING": {"value": 1400},
}

# 真實 phase(alloc 為 dict,對齊 services.macro_service:1085 等)
_REAL_PHASE = {
    "phase": "高峰",
    "score": 4.5,
    "alloc": {"股票": 40, "債券": 40, "現金": 20},
    "advice": "謹慎",
}


def _stub_radar():
    """產生 10 燈 stub(對齊 services.risk_radar 回傳 shape)"""
    return {k: {"signal": "🟢 平靜", "color": "#3fb950", "value": 1.0,
                "note": "stub", "label": "stub",
                "trend": [1.0, 1.2, 1.1, 1.3, 1.0, 1.2, 1.1, 1.0]}
            for k in ["vix_level", "vix_term_struct", "hy_oas_delta",
                      "yield_10y_shock", "move_level", "spx_trend_break",
                      "sox_drop", "sector_rotation", "put_call_ratio",
                      "asia_overnight"]}


def _stub_tp():
    """產生拐點偵測 stub"""
    return {k: {"signal": "🟢", "color": "#3fb950", "value": 0.1, "prev": 0.0,
                "trend": [0.1, 0.2, 0.1, 0.0, 0.1, 0.2, 0.1],
                "note": "stub", "label": "stub"}
            for k in ["pmi_diff", "yield_curve", "hy_spread",
                      "sahm_rule", "lei_cfnai"]}


def _build_driver(body: str) -> str:
    """共用 driver:sys.path + stub 網路 fetcher + 灌 session_state"""
    return f'''
import sys
sys.path.insert(0, "/home/user/my-Fund-dashboard")
import os
os.environ["FRED_API_KEY"] = "x" * 32

# stub 所有網路 fetcher(避免 CI 卡住、避免本機環境差異)
import services.risk_radar as _rr
import services.macro_service as _ms
import fund_fetcher as _ff
_rr.detect_risk_radar = lambda *a, **k: {_stub_radar()!r}
_rr.summarize_radar = lambda *a, **k: {{"level": "平靜", "color": "#3fb950",
                                         "red": 0, "yellow": 0, "green": 10, "gray": 0}}
_ms.detect_turning_points = lambda *a, **k: {_stub_tp()!r}
_ms.detect_systemic_risk = lambda *a, **k: {{"score": 0, "level": "低", "factors": []}}
_ff.fetch_market_news = lambda *a, **k: []

import streamlit as st
{body}
'''


def _assert_no_uncaught(at, label: str):
    """確認 AppTest run 後無 uncaught exception。
    容忍 st.error / st.warning(降級展示,§1 Fail Loud 該行為)。
    """
    if at.exception:
        msgs = []
        for e in at.exception:
            msgs.append(f"{e.type}: {str(e.value)[:300]}")
        pytest.fail(f"{label} 有 uncaught exception:\n" + "\n".join(msgs))


@pytest.mark.slow
class TestRenderSmoke:
    """v19.138 — 改動 render 路徑 smoke test"""

    @classmethod
    def setup_class(cls):
        # streamlit.testing.v1 在 streamlit 1.30+ 才有,缺則 skip
        try:
            from streamlit.testing.v1 import AppTest  # noqa: F401
        except ImportError:
            pytest.skip("streamlit.testing.v1.AppTest 不可用(streamlit < 1.30)")

    def test_render_macro_tab_four_horizons(self):
        """tab1_macro:v19.134 物理重排後 4 桶完整 render"""
        from streamlit.testing.v1 import AppTest
        drv = _build_driver(f'''
st.session_state["macro_done"] = True
st.session_state["indicators"] = {_REAL_INDICATORS!r}
st.session_state["phase_info"] = {_REAL_PHASE!r}
st.session_state["macro_last_update"] = None
st.session_state["portfolio_funds"] = []
from ui.tab1_macro import render_macro_tab
render_macro_tab()
''')
        at = AppTest.from_string(drv, default_timeout=90)
        at.run()
        _assert_no_uncaught(at, "render_macro_tab")
        # 應該有相當量的 markdown 元素(4 桶 + Z-Score + 雷達)
        assert len(at.markdown) > 10, "render 元素數量太少,可能短路"

    def test_render_data_guard_tab(self):
        """tab5:v19.135 API Key 遮罩 + Section ⓪ 覆蓋率表"""
        from streamlit.testing.v1 import AppTest
        drv = _build_driver(f'''
st.session_state["indicators"] = {_REAL_INDICATORS!r}
from ui.tab5_data_guard import render_data_guard_tab
render_data_guard_tab()
''')
        at = AppTest.from_string(drv, default_timeout=60)
        at.run()
        _assert_no_uncaught(at, "render_data_guard_tab")

    def test_render_manual_tab(self):
        """tab6:v19.136 系統說明書 + 原理教室 sub-tab"""
        from streamlit.testing.v1 import AppTest
        drv = _build_driver('''
from ui.tab6_manual import render_manual_tab
render_manual_tab()
''')
        at = AppTest.from_string(drv, default_timeout=60)
        at.run()
        _assert_no_uncaught(at, "render_manual_tab")
        # 12 個 sub-tab 內容應展開(>30 markdown)
        assert len(at.markdown) > 30, "說明書 render 元素太少"

    def test_render_macro_tab_unbound_regression(self):
        """v19.137 回歸:物理重排不該再出現 UnboundLocalError"""
        from streamlit.testing.v1 import AppTest
        # 用最小 indicators(只給 ADL 觸發 < -2 走入情境判斷區)
        _min_ind = {"ADL": {"value": -3.0}, "PMI": {"value": 45.0}, "SAHM": {"value": 0.2}}
        drv = _build_driver(f'''
st.session_state["macro_done"] = True
st.session_state["indicators"] = {_min_ind!r}
st.session_state["phase_info"] = {_REAL_PHASE!r}
st.session_state["macro_last_update"] = None
st.session_state["portfolio_funds"] = []
from ui.tab1_macro import render_macro_tab
render_macro_tab()
''')
        at = AppTest.from_string(drv, default_timeout=90)
        at.run()
        _assert_no_uncaught(at, "render_macro_tab(UnboundLocal 回歸)")
