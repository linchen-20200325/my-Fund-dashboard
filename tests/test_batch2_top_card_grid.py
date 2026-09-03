"""2026-09-03 批次二 — 總表 Section 02「5 卡快覽網格」接線驗證。

`ui/tab1_macro.py::_render_top_card_grid` 插在①結論與②依據之間(客戶拍板
線框批次二)。本檔覆蓋 CLAUDE.md §6 要求的四類邊界：

  (a) 5 張卡在真實(但注入的)資料下能渲染完、不拋例外。
  (b) 3 張本輪明確不做的卡「資產水位建議 / 新聞情緒 / 總經燈號全表」
      **沒有**被建成假卡片(§1:不補假資料佔位)。
  (c) VIX / macro_action_light 的 🔴 走 business_alert()，不是 st.error()
      (三態顏色分離,ui/helpers/render_state.py)。
  (d) 熱錢卡與既有 ARCHIVED expander 共用同一顆 L2 cache function + 同一組
      default 參數(180d)，不重抓(§2.1/§3.3 SSOT — 同一資料源只准抓一次)。

只測「呼叫端有沒有接對」，不測外部網路 / FinMind / Yahoo（那些已有
`tests/test_hot_money.py` / `tests/test_risk_radar.py` 等既有純函式測試）。
"""
from __future__ import annotations

import ast
import inspect
from unittest.mock import patch

import pandas as pd
import pytest
import streamlit as st

import ui.tab1_macro as tab1_macro
from ui.tab1_macro import (
    _action_light_renderer,
    _business_alert_action_light,
    _MACRO_CARD_LIGHT_COLOR,
    _render_top_card_grid,
)


# ────────────────────────────────────────────────────────────────────────
# 共用 fixture：一組「五卡全部算得出來」的最小輸入
# ────────────────────────────────────────────────────────────────────────
def _fake_phase() -> dict:
    """對齊 `services.macro.us_indicators.calc_macro_phase` 的真實輸出 schema。"""
    return {
        "score": 6.8,
        "phase": "擴張",
        "phase_color": "#4caf50",
        "advice": "股優於債：核心高股息 ETF + 衛星 AI/半導體",
        "trend_arrow": "↗",
        "trend_label": "向上轉折（加速）",
    }


def _fake_indicators() -> dict:
    return {
        "VIX": {"value": 15.0, "weight": 1, "score": 1},
        "YIELD_10Y2Y": {"value": 0.8, "weight": 2, "score": 2},
        "PMI": {"value": 55.0, "weight": 2, "score": 2},
    }


def _fake_radar_dict() -> dict:
    return {
        "vix_level": {
            "signal": "🟢 平靜", "color": "#4caf50", "value": 15.0, "prev": 14.5,
            "note": "VIX=15.0（單日 +3.4%）", "label": "Yahoo ^VIX 日線",
            "trend": [14.0, 14.2, 14.5, 15.0, 14.8, 15.1, 14.9, 15.0],
        },
        "hy_oas_delta": {
            "signal": "🟢 平靜", "color": "#4caf50", "value": 3.2, "prev": 3.1,
            "note": "HY OAS=3.20%（單日 +10bp）", "label": "FRED BAMLH0A0HYM2 日線",
            "trend": [3.0, 3.1, 3.15, 3.2, 3.18, 3.2, 3.19, 3.2],
        },
    }


def _fake_flow_fx_signal():
    dates = pd.bdate_range("2026-08-01", periods=10)
    flow_df = pd.DataFrame({"date": dates, "foreign_net_yi": [80.0] * 10})
    fx_df = pd.DataFrame({"date": dates, "usdtwd": [31.0 - 0.02 * i for i in range(10)]})
    return flow_df, fx_df


class _FakeSecrets(dict):
    """`st.secrets.get(...)` 之後 `hasattr(st, "secrets")` 為 True 即可。"""


@pytest.fixture(autouse=True)
def _clean_session_state():
    """每個測試前後清一次 `_radar_v1921_top`，避免測試互相污染。"""
    st.session_state.pop("_radar_v1921_top", None)
    yield
    st.session_state.pop("_radar_v1921_top", None)


# ────────────────────────────────────────────────────────────────────────
# (a) 5 張卡在真實資料下渲染完、不拋例外，且真的是 5 張（wiring 對得上）
# ────────────────────────────────────────────────────────────────────────
def test_all_five_cards_render_without_raising_and_wire_to_the_shared_component():
    """五張卡都呼叫同一顆既有的 `_render_macro_indicator_card`（不是另起爐灶的
    卡片樣式，見任務要求「reuse the existing card-rendering pattern」）。"""
    st.session_state["_radar_v1921_top"] = (_fake_radar_dict(), {"level": "平靜"})
    flow_df, fx_df = _fake_flow_fx_signal()

    _recorded_calls = []

    def _spy_card(**kwargs):
        _recorded_calls.append(kwargs)

    with patch.object(tab1_macro, "_render_macro_indicator_card", side_effect=_spy_card), \
         patch("services.hot_money_service.fetch_hot_money_frames",
               return_value=(flow_df, fx_df, "", "")):
        _render_top_card_grid(_fake_indicators(), _fake_phase())

    assert len(_recorded_calls) == 5, (
        f"應有 5 張卡呼叫 _render_macro_indicator_card，實際 {len(_recorded_calls)}："
        f"{[c.get('title') for c in _recorded_calls]}"
    )
    _titles = {c["title"] for c in _recorded_calls}
    assert _titles == {
        "📊 景氣位階", "🌊 波動與信用", "🌡️ 通膨與利率",
        "💰 熱錢動向", "⚠️ 極端風險警語",
    }
    # 每張卡都必須帶完整 schema（title / signal / value_str / note / label /
    # trend / spark_key）—— 這正是 `_render_macro_indicator_card` 既有 callers
    # （長期／中期桶）的呼叫慣例，見任務要求「check its existing callers」。
    _required_keys = {"title", "signal", "color", "value_str", "note", "label",
                      "trend", "spark_key"}
    for _c in _recorded_calls:
        assert _required_keys <= set(_c.keys()), f"卡片缺欄位：{_c['title']} → {_c.keys()}"


def test_phase_card_reuses_the_caller_supplied_phase_not_recomputed():
    """景氣位階卡必須直接讀呼叫端傳入的 `phase`（① 已算好的 `calc_macro_phase`
    輸出），不得自己重算 —— 用一個 `phase.get("score")` 讀不到就會露餡的假值
    來驗證：把 phase 改成一個真實函式算不出來的分數，卡片必須原樣印出它。
    """
    _weird_phase = dict(_fake_phase())
    _weird_phase["score"] = 9.9  # 真實 calc_macro_phase 極少見的極端值，用來當指紋
    _recorded = []
    with patch.object(tab1_macro, "_render_macro_indicator_card",
                      side_effect=lambda **kw: _recorded.append(kw)), \
         patch("services.hot_money_service.fetch_hot_money_frames",
               return_value=(pd.DataFrame(), pd.DataFrame(), "無資料", "無資料")):
        _render_top_card_grid(_fake_indicators(), _weird_phase)
    _phase_card = next(c for c in _recorded if c["title"] == "📊 景氣位階")
    assert _phase_card["value_str"] == "9.9/10"


def test_a_single_card_failure_does_not_block_the_others():
    """§1 區塊隔離：熱錢卡的資料源炸掉，另外 4 張卡仍要正常渲染。"""
    _recorded = []
    with patch.object(tab1_macro, "_render_macro_indicator_card",
                      side_effect=lambda **kw: _recorded.append(kw)), \
         patch("services.hot_money_service.fetch_hot_money_frames",
               side_effect=RuntimeError("network down")):
        _render_top_card_grid(_fake_indicators(), _fake_phase())
    _titles = {c["title"] for c in _recorded}
    assert "💰 熱錢動向" not in _titles, "炸掉的卡不該被硬塞進畫面"
    assert _titles == {"📊 景氣位階", "🌊 波動與信用", "🌡️ 通膨與利率", "⚠️ 極端風險警語"}


def test_vix_data_unavailable_boundary_shows_grey_not_a_fabricated_number():
    """CLAUDE.md §6 邊界：VIX / 風險雷達資料不可用時，卡片要誠實顯示灰態，
    不得捏造一個數字（§1 Fail Loud, Never Fake）。"""
    st.session_state.pop("_radar_v1921_top", None)  # 本次沒有雷達快取
    _recorded = []
    with patch.object(tab1_macro, "_render_macro_indicator_card",
                      side_effect=lambda **kw: _recorded.append(kw)), \
         patch("services.hot_money_service.fetch_hot_money_frames",
               return_value=(pd.DataFrame(), pd.DataFrame(), "", "")):
        _render_top_card_grid(_fake_indicators(), _fake_phase())
    _vc = next(c for c in _recorded if c["title"] == "🌊 波動與信用")
    assert _vc["signal"] == "⬜ 待取得"
    assert _vc["value_str"] == "—"
    assert _vc["color"] == _MACRO_CARD_LIGHT_COLOR["gray"]


def test_empty_indicators_and_hot_money_fetch_failure_stay_boundary_safe():
    """空 indicators + 熱錢來源回傳空 df/err：五張卡不拋例外，各自誠實降級。"""
    _recorded = []
    with patch.object(tab1_macro, "_render_macro_indicator_card",
                      side_effect=lambda **kw: _recorded.append(kw)), \
         patch("services.hot_money_service.fetch_hot_money_frames",
               return_value=(pd.DataFrame(), pd.DataFrame(), "FinMind 402", "")):
        _render_top_card_grid({}, {"score": None, "phase": "—"})
    _hm = next(c for c in _recorded if c["title"] == "💰 熱錢動向")
    assert _hm["note"] == "FinMind 402"
    _risk = next(c for c in _recorded if c["title"] == "⚠️ 極端風險警語")
    assert _risk["signal"] == "⬜ 資料不足"  # score=None，不下假綠燈也不下假紅燈


# ────────────────────────────────────────────────────────────────────────
# (b) 3 張本輪明確不做的卡，不得以假資料佔位混進網格
# ────────────────────────────────────────────────────────────────────────
def test_the_three_blocked_cards_are_never_built_with_fake_data():
    """靜態 + 動態雙重驗證：函式原始碼裡沒有把這三個當 `title=` 卡片欄位建出來
    （出現在待審查 caption 的說明文字裡沒關係——那正是 §-2 要求的揭露），
    且任何真實情境下渲染出的卡片數都不超過 5。"""
    _tree = ast.parse(inspect.getsource(_render_top_card_grid))
    _title_values = {
        n.value for n in ast.walk(_tree)
        if isinstance(n, ast.keyword) and n.arg == "title"
        and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)
    }
    _title_strs = {n.value for n in _title_values}
    for _blocked in ("資產水位建議", "新聞情緒", "總經燈號全表"):
        assert not any(_blocked in t for t in _title_strs), (
            f"「{_blocked}」不應被建成 title= 卡片欄位"
            "（客戶線框標示為待審查，本輪明確不做）"
        )
    assert len(_title_strs) == 5, f"應恰好 5 個 title= 卡片欄位，實際 {_title_strs}"
    # 待審查說明必須存在（§-2 揭露義務：不能悄悄消失不提），且必須「用文字提到」
    # 這三個被擋下的卡（不是消失不提），與上面「不建成卡片」剛好互補。
    _src = inspect.getsource(_render_top_card_grid)
    assert "待審查" in _src and "BACKLOG.md" in _src
    for _blocked in ("資產水位建議", "新聞情緒", "總經燈號全表"):
        assert _blocked in _src, f"待審查 caption 必須提到「{_blocked}」，不得悄悄消失"

    _recorded = []
    flow_df, fx_df = _fake_flow_fx_signal()
    st.session_state["_radar_v1921_top"] = (_fake_radar_dict(), {"level": "平靜"})
    with patch.object(tab1_macro, "_render_macro_indicator_card",
                      side_effect=lambda **kw: _recorded.append(kw)), \
         patch("services.hot_money_service.fetch_hot_money_frames",
               return_value=(flow_df, fx_df, "", "")):
        _render_top_card_grid(_fake_indicators(), _fake_phase())
    assert len(_recorded) <= 5


# ────────────────────────────────────────────────────────────────────────
# (c) VIX / macro_action_light 的紅燈：business_alert，不是 st.error
# ────────────────────────────────────────────────────────────────────────
def test_business_alert_action_light_calls_business_alert_not_st_error():
    """`_action_light_renderer("🔴")` 回傳的 callable 實際執行時，走
    `business_alert()`，不是 `st.error()`（三態顏色分離,見 render_state.py）。"""
    with patch("ui.tab1_macro.business_alert") as _mock_ba, \
         patch("streamlit.error") as _mock_err:
        renderer = _action_light_renderer("🔴")
        assert renderer is _business_alert_action_light
        renderer("**🔴 現在能不能買 ── 減碼**\n\n- 理由一\n- 理由二")
    _mock_ba.assert_called_once()
    _mock_err.assert_not_called()
    _title_arg, _lines_arg = _mock_ba.call_args.args[:2]
    assert "現在能不能買" in _title_arg
    assert _lines_arg == ["- 理由一", "- 理由二"]


def test_green_and_yellow_action_lights_are_unaffected_by_the_fix():
    """回歸：🟢/🟡 兩支這次沒有動，維持原生元件（避免「順手改壞旁邊」）。"""
    assert _action_light_renderer("🟢") is st.success
    assert _action_light_renderer("🟡") is st.warning


# ────────────────────────────────────────────────────────────────────────
# (d) 熱錢卡不得對同一資料源重抓：與既有 ARCHIVED expander 共用
#     同一顆 L2 facade + 同一組 default 參數（180d），才會命中同一把
#     `@st.cache_data` cache key。
# ────────────────────────────────────────────────────────────────────────
def test_hot_money_card_calls_the_shared_l2_facade_with_the_existing_default_days():
    """卡片呼叫 `fetch_hot_money_frames` 時用的 `days` 引數，必須與
    `ui/hot_money.py::refresh_hot_money_data`（既有的、長期桶自動補抓已在用的
    那一條路）的 default 完全相同 —— 這樣兩處才會命中同一把 `@st.cache_data`
    key，而不是各自抓一次不同天數窗口的資料（那就是變相的重複抓取）。
    """
    from ui.hot_money import refresh_hot_money_data
    _existing_default_days = inspect.signature(refresh_hot_money_data).parameters["days"].default

    with patch("services.hot_money_service.fetch_hot_money_frames",
              return_value=(pd.DataFrame(), pd.DataFrame(), "", "")) as _mock_fetch:
        _render_top_card_grid(_fake_indicators(), _fake_phase())

    _mock_fetch.assert_called_once()
    _called_days = _mock_fetch.call_args.args[0]
    assert _called_days == _existing_default_days == 180, (
        "熱錢卡的 days 引數與既有 refresh_hot_money_data default 對不上，"
        "會打到不同的 cache key，等於重抓（違反 §2.1/§3.3 SSOT：同一資料源只准一處取數）"
    )


def test_hot_money_card_calls_the_l2_facade_exactly_once_per_render():
    """一次渲染只呼叫一次 L2 facade（不會因為要同時填 signal/value/label/trend
    等好幾個欄位就分開呼叫好幾次 fetch）。"""
    flow_df, fx_df = _fake_flow_fx_signal()
    with patch("services.hot_money_service.fetch_hot_money_frames",
              return_value=(flow_df, fx_df, "", "")) as _mock_fetch:
        _render_top_card_grid(_fake_indicators(), _fake_phase())
    assert _mock_fetch.call_count == 1


def test_hot_money_card_does_not_import_the_l1_repository_directly():
    """§8.2 硬規則 4:L3 UI 不得直呼 L1 repository fetcher —— 熱錢卡必須走
    L2 facade（`services.hot_money_service.fetch_hot_money_frames`），
    不得在 `_render_top_card_grid` 原始碼裡直接 import
    `repositories.hot_money_repository.fetch_foreign_flow_series`。
    """
    _src = inspect.getsource(_render_top_card_grid)
    assert "repositories.hot_money_repository" not in _src
    assert "services.hot_money_service" in _src


# ────────────────────────────────────────────────────────────────────────
# 固定 3 欄網格契約（呼應 tests/test_ui_grid_contract.py 的 fail-closed 規則：
# 只有整數字面 3 才合格，這裡從行為面覆蓋一次，不只是 AST 面）
# ────────────────────────────────────────────────────────────────────────
def test_grid_uses_literal_three_columns():
    _src = inspect.getsource(_render_top_card_grid)
    assert "st.columns(3)" in _src, "Section 02 網格必須是固定 3 欄字面（客戶拍板）"
