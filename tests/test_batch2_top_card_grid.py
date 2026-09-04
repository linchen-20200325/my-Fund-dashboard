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
import pathlib
from unittest.mock import patch

import pandas as pd
import pytest
import streamlit as st

import ui.tab1_macro as tab1_macro
from services.macro import macro_action_light as _real_action_light
from ui.tab1_macro import (
    _action_light_renderer,
    _business_alert_action_light,
    _MACRO_CARD_LIGHT_COLOR,
    _render_top_card_grid,
)


# ────────────────────────────────────────────────────────────────────────
# 共用 fixture：一組「五卡全部算得出來」的最小輸入
# ────────────────────────────────────────────────────────────────────────
def _fake_growth_inflation(n_growth: int = 3, n_inflation: int = 3) -> dict:
    """對齊 `calc_growth_inflation_axis` 的真實輸出 schema（含 n_* 觀測筆數）。"""
    return {
        "growth_score": 0.33, "inflation_score": -0.33,
        "growth_up": True, "inflation_up": False,
        "quadrant": "復甦/擴張", "quadrant_en": "Goldilocks",
        "quad_color": "#00c853", "quad_icon": "🌱",
        "quad_desc": "成長↑ 通膨↓ — 黃金期，積極持有風險資產",
        "quad_alloc": "衛星成長型↑  核心配息↑  現金↓",
        "n_growth": n_growth, "n_inflation": n_inflation,
    }


def _fake_phase() -> dict:
    """對齊 `services.macro.us_indicators.calc_macro_phase` 的真實輸出 schema。

    ⚠️ `growth_inflation` 是 `calc_macro_phase` return dict 的既有 key
    （`services/macro/us_indicators.py`：算好 `calc_growth_inflation_axis(indicators)`
    之後原樣掛進 return）。卡 3 自 2026-09-04 起**讀這一份、不重算**，故 fixture
    必須帶上它，否則測到的是「呼叫端沒給 → 灰態」那條分支而不是正常路徑。
    """
    return {
        "score": 6.8,
        "phase": "擴張",
        "phase_color": "#4caf50",
        "advice": "股優於債：核心高股息 ETF + 衛星 AI/半導體",
        "trend_arrow": "↗",
        "trend_label": "向上轉折（加速）",
        "growth_inflation": _fake_growth_inflation(),
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
    st.session_state["_radar_v1921_top"] = (_fake_radar_dict(), {"level": "平靜"})
    _recorded = []
    with patch.object(tab1_macro, "_render_macro_indicator_card",
                      side_effect=lambda **kw: _recorded.append(kw)), \
         patch("services.hot_money_service.fetch_hot_money_frames",
               side_effect=RuntimeError("network down")):
        _render_top_card_grid(_fake_indicators(), _fake_phase())
    _titles = {c["title"] for c in _recorded}
    assert "💰 熱錢動向" not in _titles, "炸掉的卡不該被硬塞進畫面"
    assert _titles == {"📊 景氣位階", "🌊 波動與信用", "🌡️ 通膨與利率", "⚠️ 極端風險警語"}


# ── P4：五張卡**逐張**都要能單獨失敗（2026-09-04 稽核）─────────────────
#
# 稽核實測：上面那條測試只打得到熱錢卡；把卡 2 的 `except` 整段拿掉，
# 全 suite 依然全綠 —— 而該處的失敗是真的會往上炸的
# （`AttributeError: 'str' object has no attribute 'get'`）。
# 加上 `_render_top_card_grid` 的呼叫端當時是裸呼叫，唯一的接應是
# `app.py` 的分頁級 except，它會把**整個 Tab ①** 換成 friendly_error ——
# 也就是卡 1/2/3/5 的隔離一旦回歸，代價是整個總經分頁。
#
# 每張卡各自挑一個**只有它會讀**的來源去炸，才驗得到「逐張隔離」：
#   卡 1 `phase["phase_color"]` / 卡 2 session 的 `_radar_v1921_top` /
#   卡 3 `phase["growth_inflation"]` / 卡 4 L2 facade / 卡 5 `macro_action_light`。
# （不能用 `phase["score"]`：卡 1 與卡 5 都讀它，一炸炸兩張，證不出逐張隔離。）
class _PhaseRaisingOn(dict):
    """一個只在讀某個 key 時炸掉的 phase mapping（模擬單一來源壞掉）。"""

    def __init__(self, base: dict, bad_key: str):
        super().__init__(base)
        self._bad_key = bad_key

    def get(self, key, default=None):  # noqa: D102
        if key == self._bad_key:
            raise RuntimeError(f"phase source down: {key}")
        return super().get(key, default)


_ALL_CARD_TITLES = {
    "📊 景氣位階", "🌊 波動與信用", "🌡️ 通膨與利率",
    "💰 熱錢動向", "⚠️ 極端風險警語",
}


@pytest.mark.parametrize("broken_title", sorted(_ALL_CARD_TITLES))
def test_each_of_the_five_card_sources_can_fail_alone(broken_title):
    """五張卡逐一炸掉自己的資料源，其餘四張**都**必須照樣渲染出來。"""
    flow_df, fx_df = _fake_flow_fx_signal()
    _phase = _fake_phase()
    _radar = (_fake_radar_dict(), {"level": "平靜"})
    _hm_ret = dict(return_value=(flow_df, fx_df, "", ""))
    _mal_kw: dict = {}

    if broken_title == "📊 景氣位階":
        _phase = _PhaseRaisingOn(_fake_phase(), "phase_color")
    elif broken_title == "🌊 波動與信用":
        _radar = object()  # truthy 但不可 subscript → `_radar_cache[0]` TypeError
    elif broken_title == "🌡️ 通膨與利率":
        _phase = _PhaseRaisingOn(_fake_phase(), "growth_inflation")
    elif broken_title == "💰 熱錢動向":
        _hm_ret = dict(side_effect=RuntimeError("FinMind down"))
    elif broken_title == "⚠️ 極端風險警語":
        _mal_kw = dict(side_effect=RuntimeError("action light down"))

    st.session_state["_radar_v1921_top"] = _radar
    _recorded = []
    with patch.object(tab1_macro, "_render_macro_indicator_card",
                      side_effect=lambda **kw: _recorded.append(kw)), \
         patch("services.hot_money_service.fetch_hot_money_frames", **_hm_ret), \
         patch("services.macro.macro_action_light",
               **(_mal_kw or dict(side_effect=_real_action_light))):
        _render_top_card_grid(_fake_indicators(), _phase)

    _titles = {c["title"] for c in _recorded}
    assert broken_title not in _titles, (
        f"「{broken_title}」的來源炸了，不該被硬塞一張假卡進畫面（§1）")
    assert _titles == _ALL_CARD_TITLES - {broken_title}, (
        f"「{broken_title}」失敗時連坐了其他卡片：實際渲染 {_titles}"
    )


def test_one_cards_render_failure_does_not_take_out_the_rest_of_the_grid():
    """P4 第二半：資料算得出來、但**渲染**那一步炸掉，也只能掉那一張。

    上面每張卡各自的 try/except 只包住「算資料」；`_render_macro_indicator_card`
    先前是在迴圈裡裸呼叫的，一張卡的 HTML / sparkline 渲染失敗會連坐整個網格。
    """
    flow_df, fx_df = _fake_flow_fx_signal()
    st.session_state["_radar_v1921_top"] = (_fake_radar_dict(), {"level": "平靜"})
    _rendered = []

    def _boom_on_hot_money(**kw):
        if kw["title"] == "💰 熱錢動向":
            raise RuntimeError("plotly blew up while drawing this card")
        _rendered.append(kw["title"])

    with patch.object(tab1_macro, "_render_macro_indicator_card",
                      side_effect=_boom_on_hot_money), \
         patch("services.hot_money_service.fetch_hot_money_frames",
               return_value=(flow_df, fx_df, "", "")):
        _render_top_card_grid(_fake_indicators(), _fake_phase())

    assert set(_rendered) == _ALL_CARD_TITLES - {"💰 熱錢動向"}, (
        f"一張卡渲染失敗連坐了其他卡：實際畫出來的是 {_rendered}")


def test_the_grid_call_site_is_isolated_from_the_rest_of_tab_one():
    """P4 第三半：網格**整體**炸掉時，接應的必須是 section 級 except，
    而不是 `app.py` 的分頁級 except（後者會把整個 Tab ① 換成 friendly_error）。

    以 AST 驗證呼叫點被 `try` 包住 —— 行為面測不到（要跑起整個
    `render_macro_tab()` 才會經過那一行）。
    """
    _tree = ast.parse(inspect.getsource(tab1_macro.render_macro_tab))
    _guarded = [
        n for n in ast.walk(_tree) if isinstance(n, ast.Try)
        for _b in ast.walk(n)
        if isinstance(_b, ast.Call) and isinstance(_b.func, ast.Name)
        and _b.func.id == "_render_top_card_grid"
    ]
    assert _guarded, (
        "`_render_top_card_grid(...)` 的呼叫點沒有被 try/except 包住 —— "
        "網格失敗會沿著 app.py 的分頁級 except 把整個 Tab ① 一起帶走"
    )


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
# P1（2026-09-04 稽核 🔴）：卡 3「通膨與利率」不得從零筆觀測捏造彩色定論
#
# `calc_growth_inflation_axis` 的 `sum(signals) / max(len(signals), 1)` 在
# 「一筆觀測都沒有」時回 0.0，而 `inflation_up = 0 > 0 = False` 會被四象限
# 映射當成「通膨受控」。稽核在 FRED 掛掉／Yahoo 還活著的偏斷情境實測到：
#     signal='🌱 復甦/擴張'  color='#00c853'（綠燈）
#     value='成長 +1.00 ｜ 通膨 +0.00'  label='1 個成長訊號、0 個通膨訊號'
# —— 一個 `.get('inflation_score', 0)` 的預設值被印成量測值，而且據以放綠燈。
# 對照標準：`services/macro/action_light.py` docstring「位階缺 → 🟡 資料不足，
# 不下假綠燈（§1 Fail-Loud）」，以及卡 1/2/4/5 早就有的充足性閘門。
# ────────────────────────────────────────────────────────────────────────
def _card3(ind: dict, phase: dict) -> dict:
    _recorded = []
    with patch.object(tab1_macro, "_render_macro_indicator_card",
                      side_effect=lambda **kw: _recorded.append(kw)), \
         patch("services.hot_money_service.fetch_hot_money_frames",
               return_value=(pd.DataFrame(), pd.DataFrame(), "", "")):
        _render_top_card_grid(ind, phase)
    return next(c for c in _recorded if c["title"] == "🌡️ 通膨與利率")


def test_inflation_card_greys_out_when_the_inflation_axis_has_zero_observations():
    """FRED outage（CPI/PPI/FED_RATE 全缺、Yahoo 還在）→ 不得出現綠燈定論。"""
    _phase = dict(_fake_phase())
    _phase["growth_inflation"] = _fake_growth_inflation(n_growth=1, n_inflation=0)
    _c = _card3(_fake_indicators(), _phase)
    assert _c["signal"] == "⬜ 待取得", (
        f"通膨軸 0 筆觀測卻下了「{_c['signal']}」定論（§1 Fail Loud, Never Fake）")
    assert _c["color"] == _MACRO_CARD_LIGHT_COLOR["gray"] == "#888888"
    assert _c["value_str"] == "—", (
        f"灰態不得印任何數字，實際 {_c['value_str']!r}"
        "（`+0.00` 是 dict 預設值不是量測值）")
    # 尤其不得把「0 筆觀測」印成 `通膨 +0.00`
    assert "+0.00" not in _c["value_str"] and "0.00" not in _c["value_str"]


def test_inflation_card_greys_out_when_both_axes_are_empty():
    """全部指標都缺 → 也不得退成 `🌧️ 衰退` 橘燈（那同樣是憑空定論）。"""
    _phase = dict(_fake_phase())
    _phase["growth_inflation"] = _fake_growth_inflation(n_growth=0, n_inflation=0)
    _c = _card3({}, _phase)
    assert _c["signal"] == "⬜ 待取得"
    assert _c["color"] == _MACRO_CARD_LIGHT_COLOR["gray"]
    assert _c["value_str"] == "—"


def test_inflation_card_greys_out_when_the_axis_was_never_computed():
    """呼叫端根本沒給 `growth_inflation`（舊 phase schema / 算到一半失敗）→ 灰態，
    **不得**退路重算一次（重算會讓下面的 reuse 守衛失效）。"""
    _phase = {k: v for k, v in _fake_phase().items() if k != "growth_inflation"}
    _c = _card3(_fake_indicators(), _phase)
    assert _c["signal"] == "⬜ 待取得"
    assert _c["value_str"] == "—"


def test_inflation_card_still_shows_the_verdict_when_both_axes_have_data():
    """回歸：兩軸都有觀測時，卡 3 照樣印出四象限定論（不是被改成永遠灰）。"""
    _c = _card3(_fake_indicators(), _fake_phase())
    assert _c["signal"] == "🌱 復甦/擴張"
    assert _c["color"] == "#00c853"
    assert _c["value_str"] == "成長 +0.33 ｜ 通膨 -0.33"
    assert _c["label"] == "3 個成長訊號、3 個通膨訊號"


def test_inflation_card_reuses_the_caller_supplied_axis_not_recomputed():
    """P5：卡 3 必須讀 `phase["growth_inflation"]`（呼叫端 `calc_macro_phase` 已算好
    的同一份），不得自己再呼叫一次 `calc_growth_inflation_axis` —— 這正是
    `test_phase_card_reuses_the_caller_supplied_phase_not_recomputed` 對卡 1
    禁止的同一個 pattern，也是本函式 docstring 自稱「零新運算」的內容。

    雙重驗證：(1) 指紋 —— 塞一份 `ind` 絕對算不出來的軸，卡片必須原樣印它；
    (2) 硬守衛 —— 把 `calc_growth_inflation_axis` 換成一炸就爆的 mock，
        卡 3 仍要正常渲染（真的重算的話這裡會掉進 except 而消失）。
    """
    _phase = dict(_fake_phase())
    _phase["growth_inflation"] = dict(
        _fake_growth_inflation(),
        quadrant="過熱", quad_icon="🔥", quad_color="#ff6d00",
        growth_score=0.77, inflation_score=0.99,  # `_fake_indicators()` 產不出的指紋
        quad_desc="指紋：這一份只可能來自呼叫端傳進來的 phase",
    )
    with patch("services.macro.calc_growth_inflation_axis",
               side_effect=AssertionError("卡 3 不得重算 growth/inflation 軸")):
        _c = _card3(_fake_indicators(), _phase)
    assert _c["signal"] == "🔥 過熱"
    assert _c["value_str"] == "成長 +0.77 ｜ 通膨 +0.99"
    assert _c["note"].startswith("指紋：")


# ────────────────────────────────────────────────────────────────────────
# P3（2026-09-04 稽核 🟠）：卡 5 的頭條數字要與它的標籤同義
#
# 舊寫法 `value_str=f"{len(_reasons5)} 項訊號"` 數的是 `reasons`，但非 override
# 分支的 `reasons` 是一組**固定 2 則的說明文字**（「景氣位階 X/10」＋「無硬衰退／
# 恐慌訊號（…均未觸發）」），不是訊號。稽核實測：
#     CALM  （零觸發）：'🟢 未觸發'  value='2 項訊號'
#     PANIC （2 個真觸發）：'🔴 已觸發'  value='2 項訊號'   ← 同一個數字
#     score=None      ：'⬜ 資料不足' value='1 項訊號'   ← 一邊說沒資料一邊報訊號
# ────────────────────────────────────────────────────────────────────────
def _card5(ind: dict, score) -> dict:
    _recorded = []
    with patch.object(tab1_macro, "_render_macro_indicator_card",
                      side_effect=lambda **kw: _recorded.append(kw)), \
         patch("services.hot_money_service.fetch_hot_money_frames",
               return_value=(pd.DataFrame(), pd.DataFrame(), "", "")):
        _render_top_card_grid(ind, {"score": score, "phase": "—"})
    return next(c for c in _recorded if c["title"] == "⚠️ 極端風險警語")


_CALM_IND = {"VIX": {"value": 15.0}, "YIELD_10Y2Y": {"value": 0.8}}
#: 兩個真觸發：VIX ≥ 30（恐慌）＋ 10Y-2Y < 0（倒掛）
_PANIC_IND = {"VIX": {"value": 42.0}, "YIELD_10Y2Y": {"value": -0.5}}


def test_extreme_risk_card_headline_differs_between_calm_and_panic():
    """平靜與恐慌**不得**印出同一個頭條數字。"""
    _calm, _panic = _card5(_CALM_IND, 6.8), _card5(_PANIC_IND, 6.8)
    assert _calm["signal"] == "🟢 未觸發" and _panic["signal"] == "🔴 已觸發"
    assert _calm["value_str"] != _panic["value_str"], (
        f"平靜與恐慌的頭條數字相同（皆為 {_calm['value_str']!r}）—— "
        "那個數字數的是說明文字則數，不是觸發訊號數"
    )


def test_extreme_risk_card_counts_triggered_signals_not_explanation_lines():
    """數字必須是**真的觸發**的訊號數：平靜 0、恐慌 2。"""
    assert _card5(_CALM_IND, 6.8)["value_str"] == "0 項觸發"
    assert _card5(_PANIC_IND, 6.8)["value_str"] == "2 項觸發"


def test_extreme_risk_card_claims_no_signal_while_declaring_insufficient_data():
    """`score is None` 的灰態不得同時報「N 項訊號」（自相矛盾）。"""
    _c = _card5({}, None)
    assert _c["signal"] == "⬜ 資料不足"
    assert _c["value_str"] == "—", (
        f"資料不足卻報 {_c['value_str']!r} —— 一邊說沒資料一邊報訊號數")
    assert "項" not in _c["value_str"]


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


# ── P2（2026-09-04 稽核 🟠）：cache key 的另一半 —— token ─────────────────
#
# L1 `fetch_foreign_flow_series(days, token)` 的 `@st.cache_data` key 是
# **`(days, token)` 兩個**。上面那條測試（含它自己的 docstring 宣稱「命中同一把
# cache key」）只驗了 `call_args.args[0]`＝days，token 那一半從來沒被驗過 ——
# 稽核實測：把卡片的 token 讀取換成一個字面字串，測試照樣全綠。
#
# 而 token 是**真的會分岔**的那一半：卡片走 `infra.config.get_secret`（st.secrets
# 讀不到會 fallback `os.environ`），`ui/tab1_macro_longterm.py` 的自動補抓與
# ARCHIVED expander 原本走裸 `st.secrets.get`（**不看** os.environ）。token 只存在
# 於環境變數時，兩邊算出不同 token → 兩把不同的 cache key → 同一個視窗被抓兩次，
# 一次帶授權一次沒帶，同一頁上同一個量可能出現兩個值。
def test_hot_money_card_reads_its_token_through_the_shared_secret_accessor():
    """卡片傳給 L2 facade 的 `token` 必須是 `infra.config.get_secret` 讀出來的值。

    突變驗證：把卡片裡的 token 讀取改成任何字面字串 → 本測試必須轉紅。
    """
    _sentinel = "TOKEN-FROM-THE-SHARED-ACCESSOR-0xC0FFEE"
    with patch("infra.config.get_secret", return_value=_sentinel) as _mock_secret, \
         patch("services.hot_money_service.fetch_hot_money_frames",
               return_value=(pd.DataFrame(), pd.DataFrame(), "", "")) as _mock_fetch:
        _render_top_card_grid(_fake_indicators(), _fake_phase())

    _mock_secret.assert_any_call("FINMIND_TOKEN", "")
    _mock_fetch.assert_called_once()
    _called_token = _mock_fetch.call_args.args[1]
    assert _called_token == _sentinel, (
        f"熱錢卡傳出去的 token 是 {_called_token!r}，不是 `infra.config.get_secret` "
        "讀到的值 —— 與 ARCHIVED expander 的 cache key 會分岔（等於重抓）"
    )


def test_the_archived_expander_side_reads_its_token_through_the_same_accessor():
    """cache key 的兩端要**同時**釘住：`ui/tab1_macro_longterm.py` 那一側
    （自動補抓 + ARCHIVED expander）也必須走 `infra.config.get_secret`，
    不得留裸 `st.secrets.get("FINMIND_TOKEN", ...)`。

    用 AST 驗證：行為面要驗得跑起整個長期桶（吃 session_state + 一堆外部資料）。
    """
    import ui.tab1_macro_longterm as _lt
    _src = pathlib.Path(_lt.__file__).read_text(encoding="utf-8")
    _tree = ast.parse(_src)
    _bad = [
        n for n in ast.walk(_tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == "get"
        and ast.unparse(n.func.value).endswith("secrets")
        and n.args and isinstance(n.args[0], ast.Constant)
        and n.args[0].value == "FINMIND_TOKEN"
    ]
    assert not _bad, (
        "`ui/tab1_macro_longterm.py` 仍有裸 `st.secrets.get(\"FINMIND_TOKEN\", ...)`："
        f"第 {[n.lineno for n in _bad]} 行 —— 它不看 os.environ，會與熱錢卡的 "
        "cache key 分岔（同一視窗抓兩次）"
    )
    assert "FINMIND_TOKEN" in _src, "sanity：token 讀取整段消失了？"
    assert "get_secret" in _src, (
        "`ui/tab1_macro_longterm.py` 沒有走 `infra.config.get_secret`")


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
    """⚠️ 2026-09-04 稽核：本測試原本是 `assert "st.columns(3)" in _src` ——
    那個字面在本函式裡出現**兩次**，其中一次在註解（「`st.columns(3)` 字面用滿」）。
    也就是把真正的 `st.columns(3)` 改成 `st.columns(_n)` 之後，測試靠註解裡的那
    一份**照樣全綠** —— 一個測不到東西的假守衛。本 repo 已在
    `tests/test_render_state_color_separation.py` 就地記過同一個坑（字串比對看不到
    程式結構），故改用 AST：只認**真的呼叫**，註解與字串裡的同名字面一概不算。

    （突變是不是本來就有人守？有 —— `tests/test_ui_grid_contract.py` 的
    fail-closed 規則會抓到；所以本條的價值不是「補上沒人守的洞」，而是把一條
    宣稱守著卻守不到的假測試變成真的。刻意留著而不是刪掉，是因為它從**行為所在
    的那個函式**這一端釘住，與 `test_ui_grid_contract` 的全域掃描互為佐證。）
    """
    _tree = ast.parse(inspect.getsource(_render_top_card_grid))
    _col_calls = [
        n for n in ast.walk(_tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == "columns"
    ]
    assert _col_calls, "Section 02 網格裡找不到任何 `.columns(...)` 呼叫"
    for _c in _col_calls:
        assert len(_c.args) == 1 and isinstance(_c.args[0], ast.Constant) \
            and _c.args[0].value == 3 and isinstance(_c.args[0].value, int) \
            and not isinstance(_c.args[0].value, bool), (
            f"欄數必須是整數字面 3，實際 `{ast.unparse(_c)}`（第 {_c.lineno} 行）"
            "—— 客戶拍板的固定 3 欄自適應網格；變數／len()／函式呼叫一律不算"
            "（同 tests/test_ui_grid_contract.py 的 fail-closed 判定）"
        )


# ────────────────────────────────────────────────────────────────────────
# 真元件煙霧測試（2026-09-04 稽核 🟡）
#
# 上面幾乎每條測試都 `patch.object(tab1_macro, "_render_macro_indicator_card")`，
# 於是**真正的卡片元件從頭到尾沒被跑過一次** —— 五張卡餵給它的 kwargs 若有型別
# 不合（例如 `trend` 給了 DataFrame、`color` 給了 None），現有測試全綠也照樣在
# 畫面上炸。這裡不 patch，讓五張卡走完真的 `_render_macro_indicator_card`
# （含 HTML 組字串與 `_make_radar_sparkline`）。
# ────────────────────────────────────────────────────────────────────────
def test_the_real_card_component_renders_all_five_cards_for_real():
    """不 patch 卡片元件：五張卡的 kwargs 要真的能被它吃下去，不拋例外。"""
    flow_df, fx_df = _fake_flow_fx_signal()
    st.session_state["_radar_v1921_top"] = (_fake_radar_dict(), {"level": "平靜"})

    _drawn: list[str] = []
    _real_component = tab1_macro._render_macro_indicator_card

    def _spy_through(**kw):
        _out = _real_component(**kw)   # ← 真的跑元件
        # ⚠️ 必須在真元件**回來之後**才記錄。記在呼叫前，等於只驗「有沒有被呼叫到」——
        # 真元件內部炸掉時，新的逐張渲染隔離（P4）會把例外收進 `system_error`，
        # 這份清單卻仍然是滿的 → 測試全綠。（2026-09-04 突變實測抓到：把真元件改成
        # 對某一張卡 raise，記在呼叫前的版本 30 passed，什麼都沒看見。）
        _drawn.append(kw["title"])
        return _out

    with patch.object(tab1_macro, "_render_macro_indicator_card",
                      side_effect=_spy_through), \
         patch("services.hot_money_service.fetch_hot_money_frames",
               return_value=(flow_df, fx_df, "", "")):
        _render_top_card_grid(_fake_indicators(), _fake_phase())

    assert set(_drawn) == _ALL_CARD_TITLES, (
        "真元件跑起來之後有卡片掉了 —— 新的逐張渲染隔離把例外吞進 system_error，"
        f"實際畫出：{_drawn}"
    )
