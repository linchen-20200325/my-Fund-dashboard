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
    """對齊 `calc_growth_inflation_axis` 的真實輸出 schema（含 n_* 觀測筆數）。

    ⚠️ 2026-09-04 稽核 F2：真實 schema 自本日起多了 `growth_dir` / `inflation_dir`
    （`'none'` / `'tie'` / `'up'` / `'down'`）。這裡依 `n_*` 與底下寫死的
    score 正負推出來，讓 fixture 與生產端**同構**；但**手捏的 fixture 永遠不能
    當成 F2 的證據** —— tie 這一整類正是因為所有既有測試都手捏 `n_*` 才看不見。
    F2 的守衛一律走真的 `calc_macro_phase`（見本檔末段）。
    """
    return {
        "growth_score": 0.33, "inflation_score": -0.33,
        "growth_up": True, "inflation_up": False,
        "growth_dir": "none" if n_growth == 0 else "up",
        "inflation_dir": "none" if n_inflation == 0 else "down",
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


#: 熱錢卡自 2026-09-04（稽核 F6）起「每 session 最多抓一次」，成敗都寫旗標。
#: 測試之間共用同一個 `st.session_state`，不清就會讓**第二個以後**的測試
#: 讀到前一個測試的 stash（於是 `fetch_hot_money_frames` 的 mock 一次都沒被叫到）。
_HM_SESSION_KEYS = ("_hm_card_fetch_tried", "_hm_card_frames")


@pytest.fixture(autouse=True)
def _clean_session_state():
    """每個測試前後清一次 `_radar_v1921_top` 與熱錢卡 session 旗標，避免互相污染。"""
    for _k in ("_radar_v1921_top", *_HM_SESSION_KEYS):
        st.session_state.pop(_k, None)
    yield
    for _k in ("_radar_v1921_top", *_HM_SESSION_KEYS):
        st.session_state.pop(_k, None)


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


# ════════════════════════════════════════════════════════════════════════
# F1（2026-09-04 第二輪稽核 🔴 blocker）：卡 2 的 worse-of 兩燈是死碼
#
# 舊寫法 `_rank.get(str(sig)[:2], 0)`：那些燈是**單一 code point**
# （`len("🔴") == 1`），`[:2]` 切出「emoji + 空白」，永遠對不上 1 字元的 key。
# 於是每一格 rank 都是 0、`_vix_rank >= _hy_rank` 恆真 → **HY 分支不可達**。
# 實測（修復前）25 種嚴重度組合**全部**跟著 VIX 走，其中 3 種畫錯、
# 且**全部往輕的方向錯**；最壞的一種正是這張卡存在的理由：
# 「HY 🔴 警報 × VIX 🟢 平靜」的信用先行背離 → 畫成綠燈。
#
# ⚠️ 為什麼前三輪沒抓到：本檔所有 radar fixture 的**兩盞燈都寫死 `🟢 平靜`**，
# 選擇邏輯從來沒有被兩個**不同**嚴重度餵過。故本組覆蓋完整的
# 3×3 嚴重度網格，外加 `⬜ 無資料` 與缺 key 兩種非燈狀態（5×5＝25 格）。
# ════════════════════════════════════════════════════════════════════════
_LIGHT_COLOR = {"🟢 平靜": "#4caf50", "🟡 警戒": "#ffb300",
                "🔴 警報": "#e53935", "⬜ 無資料": "#9e9e9e", "": "#9e9e9e"}
#: 生產端 `services/risk_radar.py::_signal_from` / `_empty` 的**完整**輸出集合，
#: 外加 caller 端 `.get("signal", "")` 在缺 key 時給出的空字串。
_ALL_RADAR_SIGNALS = ["🟢 平靜", "🟡 警戒", "🔴 警報", "⬜ 無資料", ""]
_SEVERITY = {"🟢 平靜": 1, "🟡 警戒": 2, "🔴 警報": 3, "⬜ 無資料": 0, "": 0}
_VIX_TREND = [14.0, 14.2, 14.5, 15.0]
_HY_TREND = [3.0, 3.1, 3.15, 3.2]


def _radar_pair(vix_sig: str, hy_sig: str) -> dict:
    return {
        "vix_level": {"signal": vix_sig, "color": _LIGHT_COLOR[vix_sig],
                      "value": 15.0, "note": f"VIX-NOTE({vix_sig})",
                      "label": "Yahoo ^VIX 日線", "trend": list(_VIX_TREND)},
        "hy_oas_delta": {"signal": hy_sig, "color": _LIGHT_COLOR[hy_sig],
                         "value": 3.2, "note": f"HY-NOTE({hy_sig})",
                         "label": "FRED BAMLH0A0HYM2 日線", "trend": list(_HY_TREND)},
    }


def _card2(vix_sig: str, hy_sig: str) -> dict:
    st.session_state["_radar_v1921_top"] = (_radar_pair(vix_sig, hy_sig), {})
    _recorded = []
    with patch.object(tab1_macro, "_render_macro_indicator_card",
                      side_effect=lambda **kw: _recorded.append(kw)), \
         patch("services.hot_money_service.fetch_hot_money_frames",
               return_value=(pd.DataFrame(), pd.DataFrame(), "", "")):
        _render_top_card_grid(_fake_indicators(), _fake_phase())
    return next(c for c in _recorded if c["title"] == "🌊 波動與信用")


@pytest.mark.parametrize("sig,rank", [
    ("🔴 警報", 3), ("🟡 警戒", 2), ("🟢 平靜", 1),
    ("⬜ 無資料", 0), ("", 0), (None, 0),
    # 前綴空白 / 未來若在燈前面加字 —— 固定切片會壞，掃描不會
    (" 🔴 警報", 3), ("【注意】🟡 警戒", 2),
])
def test_radar_light_rank_maps_every_real_producer_string(sig, rank):
    """`_radar_light_rank` 認得生產端**實際會吐出**的每一種 signal 字串。

    突變驗證：把它換回 `{"🔴":3,...}.get(str(sig)[:2], 0)` → 前 3 條全部轉紅。
    """
    assert tab1_macro._radar_light_rank(sig) == rank


@pytest.mark.parametrize("hy_sig", _ALL_RADAR_SIGNALS)
@pytest.mark.parametrize("vix_sig", _ALL_RADAR_SIGNALS)
def test_volatility_credit_card_reports_the_worse_of_the_two_lights(vix_sig, hy_sig):
    """5×5 嚴重度網格：卡 2 的燈號必須是兩盞裡**較嚴**的那一盞。

    突變驗證：把 `_radar_light_rank(...)` 改回 `_rank.get(str(...)[:2], 0)`
    → 所有 HY 較嚴的格子（含 🟢×🔴 那格）轉紅。
    """
    _c = _card2(vix_sig, hy_sig)
    _expect = hy_sig if _SEVERITY[hy_sig] > _SEVERITY[vix_sig] else vix_sig
    assert _c["signal"] == (_expect or "⬜ 無資料"), (
        f"VIX={vix_sig!r} × HY={hy_sig!r} → 卡片畫 {_c['signal']!r}，"
        f"但較嚴的是 {_expect!r}"
    )
    assert _c["color"] == _LIGHT_COLOR[_expect]


def test_the_credit_leads_equity_divergence_is_not_painted_green():
    """這張卡存在的理由那一格，單獨釘住：HY 🔴 警報 × VIX 🟢 平靜。

    修復前實測：signal='🟢 平靜' color='#4caf50' note='VIX-NOTE(🟢 平靜)'
    —— 一張綠卡，而 HY 正在警報。
    """
    _c = _card2("🟢 平靜", "🔴 警報")
    assert _c["signal"] == "🔴 警報"
    assert _c["color"] == "#e53935"
    assert _c["color"] != _LIGHT_COLOR["🟢 平靜"]


@pytest.mark.parametrize("hy_sig", _ALL_RADAR_SIGNALS)
@pytest.mark.parametrize("vix_sig", _ALL_RADAR_SIGNALS)
def test_volatility_credit_card_note_trend_and_value_follow_the_reported_light(
        vix_sig, hy_sig):
    """燈號、白話（note）、走勢圖（trend）、頭條數字排序**四者同源**。

    「一邊的結論配另一邊的走勢圖」本身就是缺陷 —— 舊寫法的 `trend` 寫死
    `_vix.get("trend")`，一旦修好 worse-of 就會變成 HY 的結論配 VIX 的圖。

    突變驗證：把 `trend=_worse.get("trend")` 改回 `_vix.get("trend")`
    → HY 較嚴的格子轉紅；把 `_driver_str/_other_str` 換回固定 VIX 在前 → 同樣轉紅。
    """
    _c = _card2(vix_sig, hy_sig)
    _hy_drives = _SEVERITY[hy_sig] > _SEVERITY[vix_sig]
    _src = "HY" if _hy_drives else "VIX"
    assert _c["note"] == f"{_src}-NOTE({hy_sig if _hy_drives else vix_sig})", (
        f"白話取自另一盞燈：卡片 note={_c['note']!r}，但燈號依 {_src}")
    assert _c["trend"] == (_HY_TREND if _hy_drives else _VIX_TREND), (
        f"sparkline 畫的是另一條序列：燈號依 {_src}，trend 卻不是它的")
    # 頭條數字：驅動源排在最前面，且 label 明說燈號依誰（兩個值都留著，都是真量測）
    assert _c["value_str"].startswith("HY " if _hy_drives else "VIX "), (
        f"驅動源沒有排在頭條最前面：{_c['value_str']!r}（燈號依 {_src}）")
    assert ("HY OAS" if _hy_drives else "VIX") in _c["label"]
    assert "燈號取兩者較嚴者" in _c["label"]
    # sparkline 的 element key 必須跟著驅動源換 —— 否則同一個 key 會被拿去對
    # 兩條不同量綱的序列（VIX ~15 vs HY OAS ~3.2%）
    assert _c["spark_key"] == ("top_vix_hy_hy" if _hy_drives else "top_vix_hy_vix")


# ════════════════════════════════════════════════════════════════════════
# F2（2026-09-04 第二輪稽核 🔴 blocker）：卡 3 不得把「打平」畫成一個方向
#
# 前一輪的 P1 閘門是 `if not _gi or _n_growth == 0 or _n_infl == 0` —— 只數
# **觀測筆數**。但生產端的方向是 `score > 0` 這個**二分**運算：正負訊號
# **筆數相抵**（score 恰為 0.0）同樣被歸進「向下」，於是
# 「CPI 4.0(+1) / PPI 1.0(-1)」渲染出 `🌱 復甦/擴張` 綠燈 +「通膨↓ 受控」，
# 與「兩個通膨指標**真的都低**」在畫面上**逐字相同**。
#
# ⚠️ 為什麼前一輪五條 P1 測試看不到：它們全部手捏 `_fake_growth_inflation()`、
# 把 `n_*` 直接寫死，**從來沒有真的跑過 `calc_growth_inflation_axis`**。
# 故本組一律走**真的** `calc_macro_phase`，由真實指標值推出打平。
# ════════════════════════════════════════════════════════════════════════
from services.macro import calc_macro_phase as _real_calc_macro_phase
from ui.hot_money import STATE_TEXT as _STATE_TEXT

#: 通膨軸打平：CPI 4.0 ≥ 3.0 → +1；PPI 1.0 < 3.0 → −1；score = 0.00
_IND_INFLATION_TIE = {"CPI": {"value": 4.0}, "PPI": {"value": 1.0},
                      "PMI": {"value": 55.0}, "YIELD_10Y2Y": {"value": 0.8}}
#: 成長軸打平：PMI 55 → +1；10Y2Y −0.5 < 0 → −1；score = 0.00
_IND_GROWTH_TIE = {"PMI": {"value": 55.0}, "YIELD_10Y2Y": {"value": -0.5},
                   "CPI": {"value": 1.0}, "PPI": {"value": 1.0}}
#: 雙軸都打平
_IND_BOTH_TIE = {"PMI": {"value": 55.0}, "YIELD_10Y2Y": {"value": -0.5},
                 "CPI": {"value": 4.0}, "PPI": {"value": 1.0}}
#: 對照組：通膨**真的**受控（兩個都低）—— 與打平必須畫得不一樣
_IND_INFLATION_REALLY_DOWN = {"CPI": {"value": 1.0}, "PPI": {"value": 1.0},
                              "PMI": {"value": 55.0}, "YIELD_10Y2Y": {"value": 0.8}}


def _card3_via_real_producer(ind: dict) -> dict:
    """走真的 `calc_macro_phase`（內含 `calc_growth_inflation_axis`），不手捏 fixture。"""
    return _card3(ind, _real_calc_macro_phase(ind))


@pytest.mark.parametrize("ind,tie_axis", [
    (_IND_INFLATION_TIE, "通膨"),
    (_IND_GROWTH_TIE, "成長"),
    (_IND_BOTH_TIE, "成長／通膨"),
])
def test_quadrant_card_does_not_render_a_tie_as_a_direction(ind, tie_axis):
    """訊號正負相抵（score 恰為 0.00）→ 不得畫成任何一個象限。

    突變驗證：把閘門改回 `if not _gi or _n_growth == 0 or _n_infl == 0`
    （只數筆數）→ 三條全部轉紅。
    """
    _c = _card3_via_real_producer(ind)
    assert _c["signal"] == "⬜ 方向不明", (
        f"{tie_axis}軸訊號相抵，卡片卻下了「{_c['signal']}」定論（§1 Fail Loud, Never Fake）")
    assert _c["color"] == _MACRO_CARD_LIGHT_COLOR["gray"]
    # 打平**不是**缺資料，燈號文字要分得開（使用者按幾次載入都不會變）
    assert _c["signal"] != "⬜ 待取得"
    assert "不是缺資料" in _c["note"]
    assert tie_axis in _c["note"]
    # 灰態不得印一個看起來像量測結論的數字
    assert _c["value_str"] == "—"
    # 尤其不得出現那句由 tie 推出來的方向敘述
    assert "通膨↓" not in _c["note"] and "成長↓" not in _c["note"]
    assert "黃金期" not in _c["note"] and "轉向長債" not in _c["note"]


def test_a_tie_and_a_genuine_downward_inflation_do_not_render_identically():
    """本缺陷的核心：打平與「真的兩個都低」在畫面上**必須**不同。

    修復前實測兩者逐字相同：
        signal='🌱 復甦/擴張' color='#00c853' value='成長 +1.00 ｜ 通膨 +0.00'
        note='成長↑ 通膨↓ — 黃金期，積極持有風險資產'
    """
    _tie = _card3_via_real_producer(_IND_INFLATION_TIE)
    _real = _card3_via_real_producer(_IND_INFLATION_REALLY_DOWN)
    assert _real["signal"] == "🌱 復甦/擴張", "對照組本身要能正常出象限（回歸）"
    assert _tie["signal"] != _real["signal"], (
        "「通膨訊號相抵」與「通膨真的受控」畫成同一張卡 —— 使用者分不出來")
    assert (_tie["signal"], _tie["color"], _tie["value_str"], _tie["note"]) != \
           (_real["signal"], _real["color"], _real["value_str"], _real["note"])


def test_the_double_tie_does_not_render_an_actionable_recession_instruction():
    """雙軸都打平 → 不得畫成 `🌧️ 衰退` 橘燈並給出「轉向長債與防禦型配置」。

    那是一句**可據以行動**的指示，而它底下是兩個 0.00。
    """
    _c = _card3_via_real_producer(_IND_BOTH_TIE)
    assert "衰退" not in _c["signal"]
    assert _c["color"] != "#ff9800"
    assert "長債" not in _c["note"] and "防禦型配置" not in _c["note"]


def test_the_producer_reports_tie_as_its_own_direction_state():
    """生產端 `calc_growth_inflation_axis` 必須把 tie 報成 `'tie'`，
    而不是靠消費端去猜 —— schema-additive，既有 key 一個都不能動。

    突變驗證：把 `_axis_dir` 的 `return "tie"` 改成 `return "down"` → 本條轉紅。
    """
    from services.macro import calc_growth_inflation_axis as _axis
    _gi = _axis(_IND_INFLATION_TIE)
    assert _gi["inflation_dir"] == "tie", (
        f"通膨 +1/−1 相抵應報 'tie'，實際 {_gi.get('inflation_dir')!r}")
    assert _gi["growth_dir"] == "up"
    assert _axis(_IND_GROWTH_TIE)["growth_dir"] == "tie"
    assert _axis({})["growth_dir"] == "none" and _axis({})["inflation_dir"] == "none"
    assert _axis(_IND_INFLATION_REALLY_DOWN)["inflation_dir"] == "down"
    # ⚠️ 既有 key **一個都不能改**（本輪刻意只做 schema-additive）：
    # `inflation_up` 在 tie 時仍為 False（＝仍把 tie 併進 down），這是**已知且已登記**
    # 的生產端缺陷（BACKLOG「成長/通膨雙軸的第五象限」），本條把它釘住，
    # 避免有人以為它已經被修好。
    assert _gi["inflation_up"] is False
    assert _gi["quadrant"] == "復甦/擴張"


def test_zero_observation_and_tie_are_told_apart():
    """回歸：零觀測（P1 那條）與打平（F2 這條）走**不同**的灰態文案，
    因為補救方式完全不同 —— 前者按載入鈕有救，後者按幾次都一樣。"""
    _phase_zero = dict(_fake_phase())
    _phase_zero["growth_inflation"] = _fake_growth_inflation(n_growth=1, n_inflation=0)
    _zero = _card3(_fake_indicators(), _phase_zero)
    _tie = _card3_via_real_producer(_IND_INFLATION_TIE)
    assert _zero["signal"] == "⬜ 待取得"
    assert _tie["signal"] == "⬜ 方向不明"
    assert _zero["signal"] != _tie["signal"]


# ════════════════════════════════════════════════════════════════════════
# F4（🟠）：卡 4 的頭條數字必須是燈號真正依據的那個量（近 5 日累計）
#
# `ui/hot_money.py::build_signals` 用 `roll_flow = foreign_net_yi.rolling(5).sum()`
# 決定 `flow_sig` → `state` → 卡片的燈與顏色；舊寫法卻印**單日**
# `foreign_net_yi`。實測：單日 −5.0、近 5 日 +235.0 → 綠色「同步流入」卡，
# 卡上唯一的數字是 −5 億。
# 客戶已拍板線框 `docs/wireframes/ia-wireframe.html` 該格逐字寫
# 「外資 +182 億／**近 5 日累計**」—— 累計值才是核准的頭條。
#
# ⚠️ 舊 fixture `foreign_net_yi: [80.0]*10` 是**常數序列**，單日與 5 日累計
# 恆同號，結構上驗不出這個缺陷。本組改用會**變號**的序列。
# ════════════════════════════════════════════════════════════════════════
def _flow_fx_where_daily_and_rolling_diverge():
    """最後一日單日 −5.0 億（負），近 5 日累計 +235.0 億（正）—— 兩者異號。"""
    dates = pd.bdate_range("2026-08-01", periods=10)
    flow_df = pd.DataFrame({"date": dates, "foreign_net_yi": [60.0] * 9 + [-5.0]})
    # 台幣連續升值 → fx_sig='appr'，配上 flow_sig='buy' 得到「同步流入」
    # （同時把 F7 那個唯一會被截斷的 state 拉進射程）
    fx_df = pd.DataFrame({"date": dates, "usdtwd": [31.0 - 0.06 * i for i in range(10)]})
    return flow_df, fx_df


def _card4(flow_df, fx_df) -> dict:
    _recorded = []
    with patch.object(tab1_macro, "_render_macro_indicator_card",
                      side_effect=lambda **kw: _recorded.append(kw)), \
         patch("services.hot_money_service.fetch_hot_money_frames",
               return_value=(flow_df, fx_df, "", "")):
        _render_top_card_grid(_fake_indicators(), _fake_phase())
    return next(c for c in _recorded if c["title"] == "💰 熱錢動向")


def test_hot_money_headline_is_the_quantity_the_light_rests_on():
    """頭條數字 = `roll_flow`（近 5 日累計），不是單日 `foreign_net_yi`。

    突變驗證：把 `_hm_latest.get("roll_flow")` 改回 `.get("foreign_net_yi")`
    → 本條轉紅（`外資 -5億` vs `外資 +235億`）。
    """
    _flow, _fx = _flow_fx_where_daily_and_rolling_diverge()
    from ui.hot_money import build_signals
    _rows = build_signals(_flow, _fx, window=5, flow_thr=50.0, fx_thr=0.5)
    _last = _rows.iloc[-1]
    # 前提：這組 fixture 真的讓單日與累計異號（否則本測試測不到東西）
    assert _last["foreign_net_yi"] < 0 < _last["roll_flow"], (
        "fixture 失效：單日與 5 日累計必須異號，否則驗不出頭條取錯量")

    _c = _card4(_flow, _fx)
    assert "流入" in _c["signal"], "前提：這組資料的燈號是流入（由 roll_flow 判定）"
    assert _c["value_str"] == "外資 +235億", (
        f"頭條數字 {_c['value_str']!r} 不是燈號依據的近 5 日累計 "
        f"（roll_flow={_last['roll_flow']:+.0f}，單日={_last['foreign_net_yi']:+.0f}）")
    # 一張綠色「流入」卡不得只印一個負數
    assert not _c["value_str"].startswith("外資 -"), (
        f"燈號說流入，卡上唯一的數字卻是負的：{_c['value_str']!r}")


def test_hot_money_label_says_which_quantity_the_number_is():
    """頭條不標期間 = 另一種誤導：label 必須寫明「近 5 日累計」。

    突變驗證：把 label 裡的 `近 {_HM_CARD_WINDOW} 日累計買賣超（燈號依此判定）`
    整段拿掉 → 本條轉紅。
    """
    _c = _card4(*_flow_fx_where_daily_and_rolling_diverge())
    assert "近 5 日累計" in _c["label"], f"label 沒說這個數字是什麼：{_c['label']!r}"
    assert "燈號依此判定" in _c["label"]


def test_hot_money_sparkline_plots_the_same_quantity_as_the_headline():
    """走勢圖畫累計、頭條也講累計 —— 不得一個講累計、一個畫單日（同 F1 的病）。"""
    _flow, _fx = _flow_fx_where_daily_and_rolling_diverge()
    from ui.hot_money import build_signals
    _expect = build_signals(_flow, _fx, window=5, flow_thr=50.0,
                            fx_thr=0.5)["roll_flow"].tail(8).tolist()
    _c = _card4(_flow, _fx)
    assert _c["trend"] == _expect, "sparkline 畫的不是頭條那個量（累計）"
    assert _c["trend"] != _flow["foreign_net_yi"].tail(8).tolist()


# ════════════════════════════════════════════════════════════════════════
# F7（🟡）：卡 4 的白話不得被 `[:70]` 截斷
#
# 8 個 state 裡只有「同步流入」超過 70 字（78 字），而它偏偏是**正向**那個：
# 截在「…但反映全 ‖ 球風險偏好上揚。」，留下前半的**負面**敘述加一個懸空的
# 「但」，且**沒有任何截斷標記** —— 語意剛好被截反。
# ════════════════════════════════════════════════════════════════════════
def test_hot_money_interpretation_is_not_truncated():
    """白話必須完整呈現，不得截斷。

    突變驗證：把 `note=str(...)` 改回 `note=str(...)[:70]` → 本條轉紅。
    """
    from ui.hot_money import STATE_TEXT
    _c = _card4(*_flow_fx_where_daily_and_rolling_diverge())
    _full = STATE_TEXT[_c["signal"]]
    assert len(_full) > 70, (
        "fixture 失效：必須挑一個真的超過 70 字的 state，否則截斷測不出來")
    assert _c["note"] == _full, (
        f"白話被截斷了（{len(_c['note'])}/{len(_full)} 字）：{_c['note']!r}")
    # 被截掉的那半必須真的在（那是整句的轉折結論）
    assert _c["note"].endswith("但反映全球風險偏好上揚。")


@pytest.mark.parametrize("state", sorted(_STATE_TEXT))
def test_every_state_text_would_survive_the_card(state):
    """全 8 個 state 的白話都不得因為卡片而被裁掉任何一個字。

    這條把「今天只有一個超過 70 字」這個**會漂移**的事實從測試裡拿掉 ——
    日後有人把某句改長，不會悄悄變成被截斷。
    """
    from ui.hot_money import STATE_TEXT
    _full = STATE_TEXT[state]
    _rows = pd.DataFrame([{
        "date": pd.Timestamp("2026-08-14"), "foreign_net_yi": 1.0,
        "roll_flow": 10.0, "state": state, "is_divergence": False,
        "interpretation": _full,
    }])
    with patch("ui.hot_money.build_signals", return_value=_rows):
        _c = _card4(*_flow_fx_where_daily_and_rolling_diverge())
    assert _c["note"] == _full, f"state={state!r} 的白話被裁掉了尾巴"


# ════════════════════════════════════════════════════════════════════════
# F6（🟠）：卡 4 每 session 最多抓一次（成敗皆標記）
#
# 本批之前 `ui/tab1_macro.py` 完全沒有熱錢取數；本卡把兩支對外抓取
# （FinMind + Yahoo）搬到 Tab ① 最上面、無閘門的位置。而 L1 那兩支是
# **只快取成功結果**的（失敗 raise 穿過 `@st.cache_data` 不入快取），
# 於是上游壞掉時**每一次 rerun 都會真的重打一次網路**。
# 兄弟路徑 `ui/tab1_macro_longterm.py` 早就記過這一課
# （`_hm_auto_refresh_tried`：「每 session 最多嘗試一次(成敗皆標記)」）。
# ════════════════════════════════════════════════════════════════════════
def test_hot_money_card_fetches_at_most_once_per_session_on_success():
    """連續三次渲染只打一次網路。

    突變驗證：把 `if not st.session_state.get(_HM_CARD_TRIED_KEY):` 拿掉
    （每次都抓）→ 本條轉紅（3 次）。
    """
    _flow, _fx = _fake_flow_fx_signal()
    with patch("services.hot_money_service.fetch_hot_money_frames",
               return_value=(_flow, _fx, "", "")) as _m, \
         patch.object(tab1_macro, "_render_macro_indicator_card"):
        for _ in range(3):
            _render_top_card_grid(_fake_indicators(), _fake_phase())
    assert _m.call_count == 1, (
        f"三次 rerun 打了 {_m.call_count} 次網路 —— 沒有 session 閘門")


def test_hot_money_card_does_not_retry_a_failing_upstream_every_rerun():
    """**失敗**也只嘗試一次 —— 這才是這條守衛真正要擋的東西。

    L1 只快取成功結果（失敗 raise 穿過 `@st.cache_data`），所以沒有 session
    閘門時，一個壞掉的上游會被逐 rerun 重打（v19.340 AppTest 教訓：
    refused 連線的 retry 會逐 rerun 累積）。

    突變驗證：把旗標改成**成功後才寫**（`成敗皆標記` → 只在成功時標記）
    → 本條轉紅。
    """
    with patch("services.hot_money_service.fetch_hot_money_frames",
               side_effect=RuntimeError("upstream down")) as _m, \
         patch.object(tab1_macro, "_render_macro_indicator_card"):
        for _ in range(4):
            _render_top_card_grid(_fake_indicators(), _fake_phase())
    assert _m.call_count == 1, (
        f"上游壞掉時 4 次 rerun 重打了 {_m.call_count} 次 —— 連線風暴")


def test_hot_money_card_stays_honest_after_a_failed_session_attempt():
    """抓取途中拋例外之後的每一次 rerun：不得假裝「還沒載入」（按了也沒用），
    要誠實說本 session 已試過並失敗，並指出去哪補。"""
    with patch("services.hot_money_service.fetch_hot_money_frames",
               side_effect=RuntimeError("upstream down")):
        _recorded = []
        with patch.object(tab1_macro, "_render_macro_indicator_card",
                          side_effect=lambda **kw: _recorded.append(kw)):
            _render_top_card_grid(_fake_indicators(), _fake_phase())   # 第一次：炸
            _recorded.clear()
            _render_top_card_grid(_fake_indicators(), _fake_phase())   # 第二次：讀 stash
    _c = next(c for c in _recorded if c["title"] == "💰 熱錢動向")
    assert _c["signal"] == "⬜ 取數失敗"
    assert _c["color"] == _MACRO_CARD_LIGHT_COLOR["gray"]
    assert "已嘗試" in _c["note"] and "失敗" in _c["note"]
    assert "去哪補" in _c["label"]


def test_the_manual_refresh_button_invalidates_the_card_session_stash():
    """⑤ 設定與診斷的「📥 立即更新外資 / USDTWD」必須清掉本卡的 session stash，
    否則使用者按了更新、切回 ① 卻沒動（F6 的 session 閘門新引進的風險）。

    AST 驗證：行為面要跑得起整個 Tab5。
    突變驗證：把 tab5 裡那兩行 `st.session_state.pop(...)` 拿掉 → 本條轉紅。
    """
    import ui.tab5_data_guard as _d5
    _src = pathlib.Path(_d5.__file__).read_text(encoding="utf-8")
    _tree = ast.parse(_src)
    _popped = {
        ast.unparse(n.args[0])
        for n in ast.walk(_tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == "pop"
        and ast.unparse(n.func.value).endswith("session_state")
        and n.args and isinstance(n.args[0], ast.Constant)
    }
    for _k in _HM_SESSION_KEYS:
        assert repr(_k) in {p.replace('"', "'") for p in _popped}, (
            f"tab5 的手動更新沒有清掉 `{_k}` —— 使用者按了更新，Tab ① 的卡片不會動")


# ════════════════════════════════════════════════════════════════════════
# F3（🟠）：FINMIND_TOKEN 一律走 `infra.config.get_secret`，全 repo 不留裸讀
#
# 前一輪（P2）只釘住 `ui/tab1_macro_longterm.py` 一個檔，於是 `tab5_data_guard.py`
# 的「📥 立即更新」按鈕（**不在 expander 裡**，它存在的理由就是「不必點開
# ARCHIVED expander」）漏網 —— 它最終打到與熱錢卡**同一顆** L1 fetcher、
# 同一組 `(days, token)` cache key。
# 本條把守衛從「一個檔」擴成「**全 repo**」，讓第三個站點不可能悄悄長出來。
# ════════════════════════════════════════════════════════════════════════
#: `infra/config.py` 是 SSOT 本身，它就是那個唯一該呼叫 `st.secrets.get` 的地方。
_SECRET_SSOT_FILE = "infra/config.py"


def test_no_bare_finmind_token_read_anywhere_in_production():
    """全 repo（production `.py`，排除 SSOT 自身與 tests/）不得再有
    裸 `st.secrets.get("FINMIND_TOKEN", ...)`。

    ⚠️ 為什麼是全 repo 而不是列一份檔案白名單：P2 那一輪就是列了名單
    （只有 `tab1_macro_longterm.py`），結果第二個站點從名單外長出來。
    **能被一個新檔案繞過的守衛，等於沒有守衛。**

    突變驗證：把 `ui/tab5_data_guard.py` 或 `ui/helpers/macro/ndc.py` 的
    `get_secret` 改回 `st.secrets.get("FINMIND_TOKEN", "")` → 本條轉紅。
    """
    _root = pathlib.Path(tab1_macro.__file__).resolve().parent.parent
    _bad: list[str] = []
    for _py in sorted(_root.rglob("*.py")):
        _rel = _py.relative_to(_root).as_posix()
        if _rel.startswith("tests/") or _rel == _SECRET_SSOT_FILE:
            continue
        try:
            _tree = ast.parse(_py.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for _n in ast.walk(_tree):
            if (isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
                    and _n.func.attr == "get"
                    and ast.unparse(_n.func.value).endswith("secrets")
                    and _n.args and isinstance(_n.args[0], ast.Constant)
                    and _n.args[0].value == "FINMIND_TOKEN"):
                _bad.append(f"{_rel}:{_n.lineno}")
    assert not _bad, (
        "仍有裸 `st.secrets.get(\"FINMIND_TOKEN\", ...)`："
        f"{_bad} —— 它不看 os.environ，也會在完全沒有 secrets.toml 時拋 "
        "StreamlitSecretNotFoundError；一律改走 `infra.config.get_secret`"
    )


def test_the_tab5_refresh_button_reads_its_token_through_the_shared_accessor():
    """`ui/tab5_data_guard.py` 的「📥 立即更新」按鈕（**不在 expander 內**）
    必須走 `infra.config.get_secret` —— 它與熱錢卡打的是同一組
    `(days=180, token)` cache key，token 分岔就是同一個視窗被抓兩次。"""
    import ui.tab5_data_guard as _d5
    _src = pathlib.Path(_d5.__file__).read_text(encoding="utf-8")
    assert "FINMIND_TOKEN" in _src, "sanity：token 讀取整段消失了？"
    assert "get_secret" in _src, (
        "`ui/tab5_data_guard.py` 沒有走 `infra.config.get_secret`")


# ════════════════════════════════════════════════════════════════════════
# F8（🟡）：空狀態三要素 —— 標題 / 缺什麼 / **去哪補**
#
# 客戶已拍板線框 `docs/wireframes/ia-wireframe.html` Rule 04：
# 「無資料…改用空狀態三要素：**標題、缺什麼、去哪補**。」
# 卡 3 的灰態 label 原本寫的是**規則**（「缺一軸不下燈號」）＝「為什麼沒有」，
# 不是「去哪補」；卡 5 的灰態 label 同樣是規則（三者任一觸發即轉紅）。
# ════════════════════════════════════════════════════════════════════════
#: 線框同一格的示意文字逐字為「未載入。點上方『載入總經資料』。」
_LOAD_BUTTON_LABEL = "載入總經資料"


def test_quadrant_card_empty_state_tells_the_user_where_to_get_the_data():
    """卡 3 零觀測灰態的 label 必須給「去哪補」，不是只講規則。

    突變驗證：把 label 改回「象限要兩軸都有觀測才成立；缺一軸不下燈號（§1 不捏造）」
    → 本條轉紅。
    """
    _phase = dict(_fake_phase())
    _phase["growth_inflation"] = _fake_growth_inflation(n_growth=1, n_inflation=0)
    _c = _card3(_fake_indicators(), _phase)
    assert _c["signal"] == "⬜ 待取得"
    assert _LOAD_BUTTON_LABEL in _c["label"], (
        f"空狀態缺「去哪補」（線框 Rule 04）：label={_c['label']!r}")
    # 「缺什麼」仍要在（三要素是三個都要，不是拿一個換一個）
    assert "0 筆觀測" in _c["note"]


def test_extreme_risk_card_empty_state_tells_the_user_where_to_get_the_data():
    """卡 5 灰態（景氣位階未取得）同樣要給「去哪補」。

    突變驗證：把灰態分支的 `_lab5 = "去哪補 → …"` 那一行刪掉（退回共用的規則說明）
    → 本條轉紅。
    """
    _recorded = []
    with patch.object(tab1_macro, "_render_macro_indicator_card",
                      side_effect=lambda **kw: _recorded.append(kw)), \
         patch("services.hot_money_service.fetch_hot_money_frames",
               return_value=(pd.DataFrame(), pd.DataFrame(), "", "")):
        _render_top_card_grid({}, {"score": None, "phase": "—"})
    _c = next(c for c in _recorded if c["title"] == "⚠️ 極端風險警語")
    assert _c["signal"] == "⬜ 資料不足"
    assert _LOAD_BUTTON_LABEL in _c["label"], (
        f"空狀態缺「去哪補」（線框 Rule 04）：label={_c['label']!r}")


def test_extreme_risk_card_keeps_the_rule_text_when_it_is_not_an_empty_state():
    """回歸：非灰態時 label 仍是那句門檻說明 —— 三要素是**空狀態**的規格，
    不是所有狀態的規格（🟢 未觸發時使用者要知道的是「依什麼判」）。"""
    _recorded = []
    with patch.object(tab1_macro, "_render_macro_indicator_card",
                      side_effect=lambda **kw: _recorded.append(kw)), \
         patch("services.hot_money_service.fetch_hot_money_frames",
               return_value=(pd.DataFrame(), pd.DataFrame(), "", "")):
        _render_top_card_grid(_fake_indicators(), _fake_phase())
    _c = next(c for c in _recorded if c["title"] == "⚠️ 極端風險警語")
    assert _c["signal"] == "🟢 未觸發"
    assert "殖利率倒掛" in _c["label"] and "Sahm" in _c["label"]


def test_volatility_credit_card_empty_state_already_has_a_remedy():
    """回歸：卡 2 的灰態 label 本來就有「去哪補」，本輪不得把它改壞。"""
    _recorded = []
    with patch.object(tab1_macro, "_render_macro_indicator_card",
                      side_effect=lambda **kw: _recorded.append(kw)), \
         patch("services.hot_money_service.fetch_hot_money_frames",
               return_value=(pd.DataFrame(), pd.DataFrame(), "", "")):
        _render_top_card_grid(_fake_indicators(), _fake_phase())   # 無 radar stash
    _c = next(c for c in _recorded if c["title"] == "🌊 波動與信用")
    assert _c["signal"] == "⬜ 待取得"
    assert _LOAD_BUTTON_LABEL in _c["label"]


# ════════════════════════════════════════════════════════════════════════
# F5（🟠）：Section 02 的規範出處必須是**版控裡真的存在**的線框檔
#
# `docs/wireframes/README.md` 開宗明義：「引用一份不在版控裡的檔案，
# 等於引用一份會消失的規範」——該目錄存在的理由就是禁止這種引用。
# 而本區塊原本引用的是「客戶拍板線框批次二」，那**不是任何一個檔名**
# （全 repo 查無此檔），等於指向一份不存在的規範。
# ════════════════════════════════════════════════════════════════════════
def test_section02_cites_a_wireframe_file_that_actually_exists():
    """`_render_top_card_grid` 附近的規範出處必須指向 `docs/wireframes/` 下的實體檔。

    突變驗證：把 `docs/wireframes/ia-wireframe.html` 改回「客戶拍板線框批次二」
    → 本條轉紅。
    """
    import re
    _root = pathlib.Path(tab1_macro.__file__).resolve().parent.parent
    _src = pathlib.Path(tab1_macro.__file__).read_text(encoding="utf-8")
    _cited = set(re.findall(r"docs/wireframes/[\w\-.]+\.html", _src))
    assert _cited, (
        "Section 02 沒有引用任何 `docs/wireframes/*.html` —— "
        "`docs/wireframes/README.md` 禁止引用不在版控裡的線框名稱"
    )
    for _rel in sorted(_cited):
        assert (_root / _rel).is_file(), f"引用了不存在的線框檔：{_rel}"
    # 這一批的規範出處就是它（客戶 2026-09-01 拍板的五分頁動線重構線框）
    assert "docs/wireframes/ia-wireframe.html" in _cited


def test_no_unversioned_wireframe_name_is_cited_as_a_spec_source():
    """「客戶拍板線框批次二」這種**不是檔名**的稱呼不得再被當成規範出處。"""
    _src = pathlib.Path(tab1_macro.__file__).read_text(encoding="utf-8")
    _root = pathlib.Path(tab1_macro.__file__).resolve().parent.parent
    _lines = [
        f"{_i}: {_l.strip()}"
        for _i, _l in enumerate(_src.splitlines(), 1)
        if "線框批次二" in _l and "不是版控裡的" not in _l and "原寫" not in _l
    ]
    assert not _lines, (
        "仍以「線框批次二」當規範出處（該名稱不對應任何版控檔案）：" + "; ".join(_lines))
    assert not list((_root / "docs" / "wireframes").glob("*批次二*")), (
        "sanity：若日後真的有一個叫「批次二」的線框檔進了版控，本條要重寫")


def test_hot_money_card_does_not_refetch_the_real_production_failure_shape():
    """⚠️ 這條測的是**真正會發生的那個形狀**，與上一條不同，兩條都要。

    上一條用 `side_effect=RuntimeError` 測「例外穿出來」那條路；但 production
    的 L1 公開 wrapper（`repositories/hot_money_repository.py::fetch_foreign_flow_series`）
    **會接住 `_FetchFailed` 並翻成 `(空 df, err)`** —— 也就是說上游壞掉時，
    L2 facade 對 caller 而言是**正常回傳**的，連線風暴發生在它**內部**
    （`_fetch_*_uncached` raise → 穿過 `@st.cache_data` 不入快取 → 每次真的重打）。

    所以「失敗」在 caller 這一端長的是 `(empty, empty, err, err)` 這個形狀，
    不是例外。session 閘門必須把**這個形狀**也擋住，否則守衛只擋到了不會發生的那條路。

    突變驗證：把 `if not st.session_state.get(_HM_CARD_TRIED_KEY):` 拿掉 → 本條轉紅。
    """
    _empty = pd.DataFrame()
    with patch("services.hot_money_service.fetch_hot_money_frames",
               return_value=(_empty, _empty, "FinMind 402 quota", "")) as _m, \
         patch.object(tab1_macro, "_render_macro_indicator_card"):
        for _ in range(5):
            _render_top_card_grid(_fake_indicators(), _fake_phase())
    assert _m.call_count == 1, (
        f"上游回 (空 df, err) 時 5 次 rerun 打了 {_m.call_count} 次 —— "
        "這才是 production 真正的失敗形狀（L1 wrapper 已把例外翻成回傳值）")


def test_hot_money_card_still_reports_the_upstream_error_after_the_gate():
    """回歸：session 閘門不得把 `err` 訊息吃掉 —— 灰卡仍要說是哪個來源掛了（§1）。"""
    _empty = pd.DataFrame()
    _recorded = []
    with patch("services.hot_money_service.fetch_hot_money_frames",
               return_value=(_empty, _empty, "FinMind 402 quota", "")), \
         patch.object(tab1_macro, "_render_macro_indicator_card",
                      side_effect=lambda **kw: _recorded.append(kw)):
        _render_top_card_grid(_fake_indicators(), _fake_phase())
        _recorded.clear()
        _render_top_card_grid(_fake_indicators(), _fake_phase())   # 第二次讀 stash
    _c = next(c for c in _recorded if c["title"] == "💰 熱錢動向")
    assert _c["signal"] == "⬜ 待取得"
    assert _c["note"] == "FinMind 402 quota", (
        f"閘門把上游錯誤訊息吃掉了：{_c['note']!r}")
