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
    """一組「資料充足」的指標（權重合計 12.5 ≥ `MACRO_PHASE_MIN_TOTAL_WEIGHT`）。

    ⚠️ 2026-09-04 第三輪稽核 A1：本 fixture 原本只有 **3 個指標、權重合計 5**。
    那個數量在**現實裡代表「18 支 fetcher 掛了 15 支」**，而所有既有測試都拿它
    當「正常情境」—— 於是「指標太少時卡 1／卡 5 在說什麼」這一整類，
    **在測試裡從來沒有被看見過**（正如 F2 那一輪的 tie：所有測試都手捏 `n_*`）。

    現在補齊成 producer 形狀：
      · **權重合計 12.5**，過得了卡 1／卡 5 的充足性閘門；
      · **四個 override 輸入（`YIELD_10Y2Y` / `YIELD_10Y3M` / `SAHM` / `VIX`）全部有值**，
        卡 5 的綠燈才有資格宣稱「均未觸發」；
      · 每一個值都**遠離**各自的觸發門檻（曲線正、Sahm 0.1、VIX 15），
        所以這組是**乾淨的平靜態**，不是碰巧沒觸發。
    """
    return {
        "VIX": {"value": 15.0, "weight": 1, "score": 1},
        "YIELD_10Y2Y": {"value": 0.8, "weight": 2, "score": 2},
        "YIELD_10Y3M": {"value": 0.6, "weight": 2, "score": 2},
        "PMI": {"value": 55.0, "weight": 2, "score": 2},
        "HY_SPREAD": {"value": 3.2, "weight": 2, "score": 1},
        "M2": {"value": 4.0, "weight": 1, "score": 1},
        "DXY": {"value": 100.0, "weight": 1, "score": 0},
        "SAHM": {"value": 0.1, "weight": 0.5, "score": 0.5},
        "CPI": {"value": 2.5, "weight": 0.5, "score": 0.5},
        "FED_RATE": {"value": 4.5, "weight": 0.5, "score": 0},
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
#: ⚠️ 2026-09-04 第三輪稽核 B2：本行原本是**第三份字面值**，而那條「手動更新會作廢
#: stash」的守衛比對的正是「tab5 的字面值 vs 本行」—— 兩份副本互比，
#: **從頭到尾沒有碰過生產端的常數**。改為直接引用 L0 SSOT。
from shared.session_keys import HM_CARD_SESSION_KEYS as _HM_SESSION_KEYS


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


#: 乾淨的平靜態：四個 override 輸入齊全且都遠離門檻，權重合計 12.5 過閘門。
#: ⚠️ 2026-09-04 A1 起**不能**再用 `{"VIX":…, "YIELD_10Y2Y":…}` 兩個 key 當「平靜」——
#: 那是「四項只檢查到兩項」，卡 5 依通則不得下綠燈（見 `_fake_indicators` docstring）。
_CALM_IND = _fake_indicators()
#: 兩個真觸發：VIX ≥ 30（恐慌）＋ 10Y-2Y < 0（倒掛）；其餘輸入照樣齊全。
_PANIC_IND = {**_fake_indicators(),
              "VIX": {"value": 42.0, "weight": 1, "score": -1},
              "YIELD_10Y2Y": {"value": -0.5, "weight": 2, "score": -2}}


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
    """資料不足的灰態不得同時報「N 項訊號」（自相矛盾）。

    ⚠️ 2026-09-04 第三輪稽核 A1 就地更正：本條原本寫
    ~~「`score is None` 的灰態」~~ 並以 `_card5({}, None)` 手捏一個
    `{"score": None, "phase": "—"}` —— **那是生產端吐不出來的形狀**
    （`calc_macro_phase` 最後一行 `score = round(max(0, min(10, norm)), 1)` 無條件執行，
    見 `test_the_producer_can_never_emit_a_none_score`），而卡 5 當時那條
    `elif phase.get("score") is None:` 分支因此是**生產路徑不可達的死碼**。
    改走**真的** `calc_macro_phase({})`：零指標是真的會發生的狀態，
    灰態由**真的可達**的充足性閘門觸發。
    """
    _c = _grid_via_real_producer({})["⚠️ 極端風險警語"]
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
    """5×5 嚴重度網格：**兩盞燈都在**時，卡 2 的燈號必須是較嚴的那一盞。

    突變驗證：把 `_radar_light_rank(...)` 改回 `_rank.get(str(...)[:2], 0)`
    → 所有 HY 較嚴的格子（含 🟢×🔴 那格）轉紅。

    ⚠️ 2026-09-04 第三輪稽核 A2：本條的射程**收窄成「兩盞都在」**。
    含 ⬜／空字串的 7 種組合改由 `test_a_missing_light_is_never_treated_as_benign`
    與 `test_a_single_light_can_still_raise_an_alarm` 兩條把關 —— 舊寫法把它們
    也納進來，等於**要求**「⬜ × 🟢 → 🟢 平靜」，那正是 A2 的缺陷本身。
    """
    if _SEVERITY[vix_sig] == 0 or _SEVERITY[hy_sig] == 0:
        pytest.skip("缺燈組合改由 A2 的專屬測試把關（見本條 docstring）")
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
    if _SEVERITY[vix_sig] == 0 or _SEVERITY[hy_sig] == 0:
        pytest.skip("缺燈組合改由 A2 的專屬測試把關（同上一條的射程收窄）")
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
    # ── 2026-09-04 第三輪稽核 A4：本行原為 `("HY OAS" if … else "VIX") in label` ──
    # **那是一句恆真的斷言。** label 尾端固定帶著來源說明
    # 「（Yahoo ^VIX ＋ FRED HY OAS，風險雷達 10 燈之 2）」—— **兩個 needle 都是
    # 這串固定文字的子字串**，於是 25 個 parametrize 格子裡兩個分支**無條件都成立**。
    # 實測突變：把 label 改成寫死「目前為 VIX」（HY 驅動時就是一句謊），
    # 全 suite 仍 `122 passed` —— 這條守衛什麼都沒守到。
    # 改成釘住**驅動源那一段**：`目前為 HY OAS` vs `目前為 VIX` 互不為子字串。
    _driver_phrase = f"目前為 {'HY OAS' if _hy_drives else 'VIX'}"
    assert _driver_phrase in _c["label"], (
        f"label 沒有指名驅動源：{_c['label']!r}（燈號依 {_src}）")
    _wrong_phrase = f"目前為 {'VIX' if _hy_drives else 'HY OAS'}"
    assert _wrong_phrase not in _c["label"], (
        f"label 指名了錯的驅動源：{_c['label']!r}（燈號依 {_src}）")
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
    # tab5 現在展開 L0 SSOT 的 `HM_CARD_SESSION_KEYS` 逐一 pop，不再逐字寫兩個字面值
    # （B2）。這裡驗的是「它 import 了那個 SSOT，而且真的拿它去 pop」。
    assert "HM_CARD_SESSION_KEYS" in _src, (
        "tab5 沒有引用 `shared.session_keys.HM_CARD_SESSION_KEYS` —— "
        "鍵名又寫成第二份字面值，B2 的 SSOT 收斂被改回去了")
    _pop_targets = {
        ast.unparse(n.args[0])
        for n in ast.walk(_tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == "pop"
        and ast.unparse(n.func.value).endswith("session_state") and n.args
    }
    assert any("_hm_k" in t for t in _pop_targets), (
        f"tab5 的手動更新沒有把 SSOT 鍵名拿去 pop：實際 pop 的是 {_pop_targets}")


def test_the_hot_money_session_keys_have_exactly_one_definition():
    """B2：兩個 session 鍵名只准有**一份**定義（L0 `shared/session_keys.py`）。

    ⚠️ 舊守衛比對的是 **tab5 的字面值** 與 **測試自己的字面值** —— 兩份**副本**互比，
    從頭到尾沒有碰過 `ui/tab1_macro.py` 的常數。把生產端常數改成別的字串，
    舊守衛照樣全綠。

    突變驗證：把 `ui/tab1_macro.py` 改回自己寫死 `_HM_CARD_TRIED_KEY = "..."`
    → 本條轉紅。

    ⚠️ **這條測試的第一版是假的守衛**：它用 `tab1_macro._HM_CARD_TRIED_KEY is
    _sk.HM_CARD_TRIED_KEY` 比對物件同一性，而 `"_hm_card_fetch_tried"` 是
    **identifier 形狀的字串字面值 → CPython 會 intern**，兩份獨立寫死的字面值
    `is` 比較**照樣為真**。實測突變 B2 當場抓到（改回寫死仍全綠）。
    **同一性比對在字串上不是 SSOT 守衛** —— 改為**結構性**檢查：
    生產端不得出現這兩個字串的字面值，只能 import。
    """
    from shared import session_keys as _sk
    assert _sk.HM_CARD_SESSION_KEYS == (_sk.HM_CARD_TRIED_KEY, _sk.HM_CARD_STASH_KEY)
    # 本測試檔自己也不再持有第三份字面值（B2 點名的那第三處）
    assert _HM_SESSION_KEYS is _sk.HM_CARD_SESSION_KEYS

    _literals = set(_sk.HM_CARD_SESSION_KEYS)
    for _mod_path in ("ui/tab1_macro.py", "ui/tab5_data_guard.py"):
        _src = pathlib.Path(_mod_path).read_text(encoding="utf-8")
        _tree = ast.parse(_src)
        _found = {
            n.value for n in ast.walk(_tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and n.value in _literals
        }
        assert not _found, (
            f"{_mod_path} 又把 session 鍵名寫成字面值 {_found} —— "
            f"SSOT 在 `shared/session_keys.py`，這裡只能 import")
        assert "session_keys" in _src, (
            f"{_mod_path} 沒有引用 `shared.session_keys` 這個 SSOT")


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
    """卡 5 灰態同樣要給「去哪補」。

    突變驗證：把灰態分支的 `_lab5 = "去哪補 → …"` 那一行刪掉（退回共用的規則說明）
    → 本條轉紅。

    ⚠️ 2026-09-04 A1 就地更正：同上一條，原本手捏 `{"score": None, "phase": "—"}`
    這個**生產端吐不出來的形狀**，改走真的 `calc_macro_phase({})`。
    """
    _c = _grid_via_real_producer({})["⚠️ 極端風險警語"]
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


# ════════════════════════════════════════════════════════════════════════
# 2026-09-04 **第三輪**稽核 — A1 / A2 / A3 / A5 / B1
#
# ⚠️ 這一整段的存在理由,比任何一條斷言重要:**前兩輪都只修了「被指出的那一個
# 案例」,沒有修「那一類」。**
#   · 第一輪(P1)修了卡 3 的**零觀測**;
#   · 第二輪(F2)在同一張卡上發現同一類的**打平**;
#   · 第三輪在**卡 1 與卡 5** 上發現同一類的第三張臉。
#
# 故本段一律**先寫出通則,再對五張卡逐一驗**,而不是只針對被點名的卡。
# 通則(見 `ui/tab1_macro.py::_phase_score_support` 上方的長註):
#   **一張卡只能宣稱它真的取到的那些輸入。**
#   (1) 點名了特定輸入的宣稱 → 那些輸入要全在;
#   (2) 建立在正規化聚合上的宣稱 → 聚合的分母要夠大;
#   (3) **不對稱**:半套證據可以升警,不可以解除警報。
# ════════════════════════════════════════════════════════════════════════
from services.macro.action_light import OVERRIDE_INPUT_KEYS as _AL_KEYS
from shared.signal_thresholds import MACRO_PHASE_MIN_TOTAL_WEIGHT as _MIN_W

#: 完全斷線:所有 fetcher 都失敗,但 `fetch_all_indicators` 仍**無條件**寫入
#: `_fred_sources`(`us_indicators.py` 該行在所有 `if` 之外)→ 回傳 dict 非空 →
#: 呼叫端 `elif not ind: st.error(...)` 那道守衛**永遠不會觸發**。
_TOTAL_OUTAGE_IND = {"_fred_sources": {
    _sid: {"success": False, "last_date": "", "realtime_start": "",
           "publish_lag_days": None, "rows": 0}
    for _sid in ("DGS10", "DGS2", "DGS3MO", "T10Y2Y", "T10Y3M")}}

#: 18 取 1:只有 VIX 且平靜 → 真實 `calc_macro_phase` 給 **10.0 分「高峰」**
_ONE_OF_18_CALM_VIX = {**_TOTAL_OUTAGE_IND,
                       "VIX": {"value": 12.0, "weight": 1, "score": 1}}
#: 18 取 1:只有 PMI 且深度收縮 → 真實 `calc_macro_phase` 給 **0.0 分「衰退」**
_ONE_OF_18_DEEP_PMI = {**_TOTAL_OUTAGE_IND,
                       "PMI": {"value": 41.0, "weight": 2, "score": -2}}


def _grid_via_real_producer(ind: dict) -> dict:
    """走**真的** `calc_macro_phase(ind)`,回 `{title: card}`。

    ⚠️ 刻意不手捏 phase —— F2 那一輪的教訓逐字適用:所有既有測試都手捏
    `_fake_growth_inflation()`,於是「生產端真的會吐出什麼」從來沒被看見過。
    """
    _recorded = []
    with patch.object(tab1_macro, "_render_macro_indicator_card",
                      side_effect=lambda **kw: _recorded.append(kw)), \
         patch("services.hot_money_service.fetch_hot_money_frames",
               return_value=(pd.DataFrame(), pd.DataFrame(), "上游全掛", "上游全掛")):
        _render_top_card_grid(ind, _real_calc_macro_phase(ind))
    return {c["title"]: c for c in _recorded}


#: 五張卡的灰態燈號(本 repo 現有的全部;新增第六種前請先想清楚為什麼)
_GREY_SIGNALS = {"⬜ 待取得", "⬜ 資料不足", "⬜ 方向不明", "⬜ 取數失敗", "⬜ 無資料"}
_GREY_COLOR = _MACRO_CARD_LIGHT_COLOR["gray"]


# ── A1(🔴):卡 1 / 卡 5 不得從零觀測捏造綠燈與買進建議 ────────────────────
def test_phase_card_does_not_fabricate_a_verdict_from_zero_observations():
    """完全斷線 → 卡 1 必須灰,**不得**出現分數、顏色或建議。

    修復前實測(真實網格,所有 fetcher 皆失敗):
        signal='擴張（5.0/10）' color='#00c853'
        note='股優於債：核心高股息ETF + 衛星AI/半導體，設嚴格停利點'
    —— 同一畫面另外三張卡正確顯示 ⬜ 待取得,只有這張在放行加碼。

    突變驗證:把 `if not _score_ok:` 那個分支拿掉 → 本條轉紅。
    """
    _c = _grid_via_real_producer(_TOTAL_OUTAGE_IND)["📊 景氣位階"]
    assert _c["signal"] in _GREY_SIGNALS, f"零觀測卻給了燈號:{_c['signal']!r}"
    assert _c["color"] == _GREY_COLOR, f"零觀測卻上色:{_c['color']}"
    assert _c["value_str"] == "—", f"零觀測卻印出分數:{_c['value_str']!r}"
    # 不得出現任何一句可據以行動的建議
    for _forbidden in ("股優於債", "獲利了結", "加碼", "保守為主", "買點"):
        assert _forbidden not in _c["note"], (
            f"零觀測卻給了投資建議(命中 {_forbidden!r}):{_c['note']!r}")


@pytest.mark.parametrize("ind,would_be", [
    (_ONE_OF_18_CALM_VIX, "高峰"),
    (_ONE_OF_18_DEEP_PMI, "衰退"),
])
def test_phase_card_does_not_let_one_indicator_decide_the_whole_phase(ind, would_be):
    """18 取 1 → 卡 1 必須灰。**這一半才是本輪真正的加嚴。**

    `calc_macro_phase` 的正規化分母只由**當次抓到的**指標構成,所以單一指標
    可以把分數掃過整個 0~10:
        只有 VIX(平靜)  → score=10 → '高峰' + 「適度獲利了結」
        只有 PMI(深收縮) → score=0  → '衰退' + 「保守為主」
    兩者都是「哪一支 fetcher 活著」的判讀,不是經濟的判讀。

    突變驗證:把閘門從 `>= MACRO_PHASE_MIN_TOTAL_WEIGHT` 放寬成 `> 0`
    → 本條兩個格子都轉紅(那正是「只修零觀測、不修這一類」的樣子)。
    """
    # 先證明上游真的會給出那個彩色定論(否則這條測試在守一個不存在的風險)
    _phase = _real_calc_macro_phase(ind)
    assert _phase["phase"] == would_be, (
        f"前提不成立:上游給的是 {_phase['phase']!r} 不是 {would_be!r}")
    _c = _grid_via_real_producer(ind)["📊 景氣位階"]
    assert _c["signal"] in _GREY_SIGNALS, (
        f"單一指標(權重合計 {tab1_macro._phase_scoring_weight(ind)})"
        f"就決定了整個景氣位階:{_c['signal']!r}")
    assert _c["value_str"] == "—"


def test_phase_card_still_shows_the_verdict_when_the_data_supports_it():
    """反向:資料夠時照樣出彩色位階 —— 閘門不得把正常情境一起擋掉。"""
    _c = _grid_via_real_producer(_fake_indicators())["📊 景氣位階"]
    assert _c["signal"] not in _GREY_SIGNALS, f"資料夠卻灰掉:{_c['signal']!r}"
    assert _c["color"] != _GREY_COLOR
    assert "/10" in _c["value_str"]


def test_the_card_layer_weight_matches_the_producers_own_denominator():
    """SSOT 等價:卡片層重算的權重分母,必須**逐一等於** `calc_macro_phase`
    自己用的那一個(`_provenance["total_weight"]`)。

    兩邊一旦分岔,閘門就會在守一個不存在的分母 —— 而那種錯不會有人發現,
    因為兩邊各自都「看起來合理」。

    突變驗證:把 `_phase_scoring_weight` 的 `ind.get("weight", 1)` 改成
    `ind.get("weight", 0)` → 本條轉紅（靠下面「無 weight 欄」那一格）。

    ⚠️ **這條測試第一次寫的時候是假的守衛**:所有 case 都帶明寫的 `weight`,
    於是**預設值那一支永遠沒被走到** —— 把預設從 1 改成 0,測試照樣全綠。
    實測突變 `A1-e` 當場抓到,故補上「**無 `weight` 欄**」與「**meta 混入**」兩格。
    這正是本輪 A4 在講的同一個病:**斷言看起來在守,實際上兩邊都恆真。**
    """
    _no_weight = {"PMI": {"value": 55.0, "score": 2},          # 刻意不帶 weight
                  "VIX": {"value": 15.0, "score": 1},
                  "_fred_sources": {"DGS10": {"success": False}}}   # meta 不得進分母
    for _name, _ind in [("完全斷線", _TOTAL_OUTAGE_IND),
                        ("18取1-VIX", _ONE_OF_18_CALM_VIX),
                        ("18取1-PMI", _ONE_OF_18_DEEP_PMI),
                        ("無 weight 欄 + meta 混入", _no_weight),
                        ("資料充足", _fake_indicators())]:
        _prov_w = _real_calc_macro_phase(_ind)["_provenance"]["total_weight"]
        _card_w = tab1_macro._phase_scoring_weight(_ind)
        assert _card_w == pytest.approx(_prov_w), (
            f"{_name}:卡片層算 {_card_w}、生產端算 {_prov_w} —— 分母分岔了")


def test_the_producer_can_never_emit_a_none_score():
    """釘死 A1 後半段:`calc_macro_phase` 的 `score` **不可能是 None**。

    卡 5 舊有的 `elif phase.get("score") is None:` 分支因此是**生產路徑不可達的
    死碼**,而當時「守著」它的兩條測試手捏 `{"score": None, "phase": "—"}` ——
    一個對死碼的修復,由一個跑在死碼上的測試背書(`CLAUDE.md §-2` 的 `db4c139` 形態)。

    本條把「不可能」變成可被機器檢查的事實:含**零指標**在內,
    `score` 永遠是 `round(max(0, min(10, norm)), 1)` 的數字。
    """
    for _ind in (_TOTAL_OUTAGE_IND, {}, _ONE_OF_18_CALM_VIX, _fake_indicators()):
        _s = _real_calc_macro_phase(_ind)["score"]
        assert isinstance(_s, (int, float)) and _s is not None, (
            f"score={_s!r} —— 若生產端真的能吐 None,本輪對卡 5 的判定要重來")


def test_extreme_risk_card_does_not_claim_checks_it_never_made():
    """卡 5 綠燈那句「殖利率曲線、Sahm、VIX **均未觸發**」是一句**點名輸入**的宣稱。

    完全斷線實測(修復前):
        signal='🟢 未觸發' color='#22c55e'
        note='景氣位階 5.0/10；無硬衰退/恐慌訊號（殖利率曲線、Sahm、VIX 均未觸發）'
    —— 那四項輸入**一項都沒取到**,卡片卻宣稱四項都檢查過且都沒事。

    突變驗證:把 `elif _missing5 or not _score_ok5:` 改回
    `elif phase.get("score") is None:` → 本條轉紅。
    """
    _c = _grid_via_real_producer(_TOTAL_OUTAGE_IND)["⚠️ 極端風險警語"]
    assert _c["signal"] in _GREY_SIGNALS, f"零觀測卻下了燈號:{_c['signal']!r}"
    assert _c["color"] == _GREY_COLOR
    assert "均未觸發" not in _c["note"], (
        f"宣稱檢查過四項,但一項都沒取到:{_c['note']!r}")
    # 要說清楚缺了哪些(§1:誠實揭露,不是只說「沒資料」)
    for _k in _AL_KEYS:
        assert _k in _c["note"], f"沒說明缺了 {_k}:{_c['note']!r}"


@pytest.mark.parametrize("missing", sorted(_AL_KEYS))
def test_extreme_risk_card_greys_out_when_any_single_risk_input_is_missing(missing):
    """**逐一**拔掉四個 override 輸入的任一個 → 綠燈不得成立。

    這條是「類」的驗證:不是只測「全缺」,而是測**每一個**輸入缺席時都擋得住。
    **權重仍然充足**(四個 key 拿掉任一個,合計仍 ≥ 10),所以擋住它的**只能**是
    點名輸入那道閘門,不是權重閘門。

    ⚠️ 「缺席」在此**整個 key 刪掉**,不是把 `value` 設成 `None` ——
    `fetch_all_indicators` 是「抓到才寫 key」,`{"VIX": {"value": None}}` 這種形狀
    **生產端吐不出來**(而且會在 `calc_macro_phase` 的 alerts 段直接 TypeError,
    屬本輪射程外的既有上游問題)。用生產端吐得出來的形狀測,才測得到真的東西。

    突變驗證:把 `_missing5` 的計算改成 `[]`(等於拿掉這道閘門)→ 四個格子全紅。
    """
    _ind = {k: dict(v) for k, v in _fake_indicators().items() if k != missing}
    assert tab1_macro._phase_score_support(_ind)[0], "前提:權重仍然充足"
    _c = _grid_via_real_producer(_ind)["⚠️ 極端風險警語"]
    assert _c["signal"] in _GREY_SIGNALS, (
        f"缺 {missing} 卻仍宣告安全:{_c['signal']!r}")
    assert missing in _c["note"], f"沒指出缺的是 {missing}:{_c['note']!r}"


def test_a_real_override_still_fires_even_when_the_data_is_thin():
    """**不對稱規則(3):半套證據可以升警,不可以解除警報。**

    只有 VIX=42(遠低於權重門檻)—— 位階算不出來,但「VIX ≥ 30 恐慌」是**真的
    量到的觀測跨過門檻**。閘門若把它一起吃掉,就是把真警報變灰,那比假綠燈更糟。

    突變驗證:把 `if _al5.get("override"):` 那個分支移到充足性閘門**之後**
    → 本條轉紅。
    """
    _ind = {**_TOTAL_OUTAGE_IND, "VIX": {"value": 42.0, "weight": 1, "score": -1}}
    assert not tab1_macro._phase_score_support(_ind)[0], "前提:權重不足"
    _c = _grid_via_real_producer(_ind)["⚠️ 極端風險警語"]
    assert _c["signal"] == "🔴 已觸發", f"真警報被閘門吃掉了:{_c['signal']!r}"
    assert _c["color"] == _MACRO_CARD_LIGHT_COLOR["red"]
    assert "1 項觸發" == _c["value_str"]
    # 紅燈成立,但「其餘都沒事」不成立 —— 要據實說還有幾項沒檢查
    assert "未檢查" in _c["note"], f"沒揭露其餘三項未檢查:{_c['note']!r}"


def test_no_card_paints_a_verdict_under_a_total_outage():
    """**通則的全卡驗證** —— 這一條才是「修的是類、不是案例」的證明。

    完全斷線時,**五張卡沒有任何一張**可以出現非灰的燈號或顏色。
    前兩輪的測試都只問「被點名的那一張」,所以同一類的第三張臉才會長出來。

    突變驗證:把卡 1 或卡 5 任一個閘門拿掉 → 本條轉紅。
    """
    _cards = _grid_via_real_producer(_TOTAL_OUTAGE_IND)
    assert len(_cards) == 5, f"完全斷線時掉了卡片:{sorted(_cards)}"
    _bad = {t: (c["signal"], c["color"]) for t, c in _cards.items()
            if c["signal"] not in _GREY_SIGNALS or c["color"] != _GREY_COLOR}
    assert not _bad, f"完全斷線,但這些卡仍給了彩色定論:{_bad}"


def test_the_override_input_keys_constant_matches_what_the_function_reads():
    """漂移鎖:`OVERRIDE_INPUT_KEYS` 必須**恰好等於** `macro_action_light`
    的 override 段實際讀的那些 key。

    沒有這條,常數就是「第二個真相源」—— 函式日後多讀一個指標(例如 HY_SPREAD),
    卡 5 的閘門會漏掉它而不會有人發現。

    以 AST 取 `_val(indicators, "...")` 的字串引數,**不用 grep**
    (docstring 裡也寫著那幾個字,grep 會被騙)。
    突變驗證:從常數裡拿掉 `"SAHM"` → 本條轉紅。
    """
    import services.macro.action_light as _al
    _tree = ast.parse(inspect.getsource(_al.macro_action_light))
    _read = {
        n.args[1].value
        for n in ast.walk(_tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == "_val" and len(n.args) == 2
        and isinstance(n.args[1], ast.Constant) and isinstance(n.args[1].value, str)
    }
    assert _read == set(_AL_KEYS), (
        f"常數與函式實際讀的 key 分岔了:常數 {set(_AL_KEYS)}、實際 {_read}")


# ── A2(🟠):卡 2 缺一盞燈不得被當成「最溫和的狀態」───────────────────────
@pytest.mark.parametrize("present_light", ["🟢 平靜"])
@pytest.mark.parametrize("missing_side", ["vix", "hy"])
def test_a_missing_light_is_never_treated_as_benign(missing_side, present_light):
    """`_radar_light_rank` 把 `⬜ 無資料` 排成 **0,比 🟢(1) 還低** ——
    一盞從來沒量到的燈於是變成「最溫和」。

    修復前實測(4×4 全網格):
        VIX 綠 + HY 缺 → 🟢 平靜「VIX 15.0 ｜ HY —」
        VIX 缺 + HY 綠 → 🟢 平靜「HY 15.00% ｜ VIX —」
    FRED 掛掉、Yahoo 還活著是 routine 的偏斷,而信用那半正是這張卡存在的理由。

    突變驗證:把 `elif _vix_has or _hy_has:` 分支刪掉(退回無條件 worse-of)
    → 本條兩個格子都轉紅。
    """
    _vix = "⬜ 無資料" if missing_side == "vix" else present_light
    _hy = "⬜ 無資料" if missing_side == "hy" else present_light
    _c = _card2(_vix, _hy)
    assert _c["signal"] in _GREY_SIGNALS, (
        f"只量到一盞(另一盞 ⬜)卻下了綠燈:{_c['signal']!r}")
    assert _c["color"] == _GREY_COLOR
    assert "未與另一盞比較" in _c["label"], (
        f"label 仍在宣稱一個沒發生過的比較:{_c['label']!r}")
    assert "燈號取兩者較嚴者" not in _c["label"]


@pytest.mark.parametrize("alarm", ["🟡 警戒", "🔴 警報"])
@pytest.mark.parametrize("missing_side", ["vix", "hy"])
def test_a_single_light_can_still_raise_an_alarm(missing_side, alarm):
    """不對稱規則的另一半:**只量到一盞、而它在警戒/警報 → 照實升警。**

    把真警報藏起來,比畫假綠燈更糟。這條擋的是「為了修 A2 而一律灰掉」的過度修正。

    突變驗證:把 `_alarm` 判斷改成 `False`(缺燈一律灰)→ 四個格子全紅。
    """
    _vix = "⬜ 無資料" if missing_side == "vix" else alarm
    _hy = "⬜ 無資料" if missing_side == "hy" else alarm
    _c = _card2(_vix, _hy)
    assert _c["signal"] == alarm, f"單盞警報被藏起來了:{_c['signal']!r}"
    assert _c["color"] == _LIGHT_COLOR[alarm]
    assert "未與另一盞比較" in _c["label"]
    assert "未取得" in _c["note"], f"沒揭露另一盞沒量到:{_c['note']!r}"


def test_both_lights_missing_claims_no_comparison_at_all():
    """⬜×⬜ 時 label 原本仍寫「燈號取兩者較嚴者:目前為 **VIX**」——
    兩盞都沒量到,卻指名了一個驅動源。

    突變驗證:把 `else:` 那個雙缺分支刪掉 → 本條轉紅。
    """
    _c = _card2("⬜ 無資料", "⬜ 無資料")
    assert _c["signal"] in _GREY_SIGNALS
    assert _c["color"] == _GREY_COLOR
    assert _c["value_str"] == "—"
    assert "燈號取兩者較嚴者" not in _c["label"]
    assert "目前為 VIX" not in _c["label"] and "目前為 HY OAS" not in _c["label"]
    assert "沒有做任何比較" in _c["label"]


@pytest.mark.parametrize("hy_sig", _ALL_RADAR_SIGNALS)
@pytest.mark.parametrize("vix_sig", _ALL_RADAR_SIGNALS)
def test_the_comparison_claim_appears_only_when_both_lights_exist(vix_sig, hy_sig):
    """全 5×5 網格的**單一不變量**:label 只有在兩盞都在時才准講「較嚴者」。

    這條刻意涵蓋整個網格(含被上面兩條 skip 掉的缺燈格),
    確保射程收窄之後沒有留下沒人看的格子。
    """
    _c = _card2(vix_sig, hy_sig)
    _both = _SEVERITY[vix_sig] > 0 and _SEVERITY[hy_sig] > 0
    assert ("燈號取兩者較嚴者" in _c["label"]) is _both, (
        f"VIX={vix_sig!r} × HY={hy_sig!r}:兩盞都在={_both},"
        f"但 label={_c['label']!r}")


# ── A3(🟠):缺 `*_dir` 的向後相容 fallback 必須 fail-closed ─────────────────
def test_a_payload_without_direction_fields_fails_closed():
    """舊 payload(沒有 `growth_dir` / `inflation_dir`)且 `n > 0` 時,
    舊寫法退成空字串 `""` —— 既不是 `"none"` 也不是 `"tie"`,於是直接落進
    `else` 分支,把**打平併進來的** `quad_*` 原封送上畫面。

    修復前實測(inflation_score=0.0、n_inflation=2、無 `*_dir`):
        '🌱 復甦/擴張' #00c853「成長 +1.00 ｜ 通膨 +0.00」
        「成長↑ 通膨↓ — 黃金期,積極持有風險資產」
    —— 與 F2 修復**前**的輸出逐位元組相同,是一條設計出來的、通回 blocker 的路。

    突變驗證:把 `"unknown"` 改回 `""` → 本條轉紅。
    """
    _gi = {
        "growth_score": 1.0, "inflation_score": 0.0,
        "growth_up": True, "inflation_up": False,
        "quadrant": "復甦/擴張", "quad_color": "#00c853", "quad_icon": "🌱",
        "quad_desc": "成長↑ 通膨↓ — 黃金期，積極持有風險資產",
        "n_growth": 2, "n_inflation": 2,
    }   # 刻意**不含** growth_dir / inflation_dir
    _c = _card3(_fake_indicators(), {**_fake_phase(), "growth_inflation": _gi})
    assert _c["signal"] in _GREY_SIGNALS, f"缺方向欄位卻定了象限:{_c['signal']!r}"
    assert _c["color"] == _GREY_COLOR
    assert _c["value_str"] == "—"
    assert "復甦/擴張" not in _c["signal"] and "黃金期" not in _c["note"]
    assert "沒有帶方向欄位" in _c["note"], (
        f"沒說清楚是契約問題而不是市場狀態:{_c['note']!r}")


@pytest.mark.parametrize("bogus", ["", "sideways", "UP", "unknown", "0"])
def test_any_direction_value_the_card_does_not_recognise_fails_closed(bogus):
    """**這一條才是「修類」的部分**:不只是「缺欄位」,任何本卡**不認得**的方向值
    都必須 fail-closed —— 包含未來生產端新增的第五種狀態。

    突變驗證:把 `_dir_ok = {"up", "down"}` 改成 `_g_dir != "tie"` 這種黑名單寫法
    → `""` / `"sideways"` / `"UP"` / `"0"` 全部轉紅。
    """
    _gi = {
        "growth_score": 1.0, "inflation_score": 0.0,
        "growth_dir": "up", "inflation_dir": bogus,
        "quadrant": "復甦/擴張", "quad_color": "#00c853", "quad_icon": "🌱",
        "quad_desc": "成長↑ 通膨↓ — 黃金期，積極持有風險資產",
        "n_growth": 2, "n_inflation": 2,
    }
    _c = _card3(_fake_indicators(), {**_fake_phase(), "growth_inflation": _gi})
    assert _c["signal"] in _GREY_SIGNALS, (
        f"不認得的方向值 {bogus!r} 仍被畫成象限:{_c['signal']!r}")
    assert _c["color"] == _GREY_COLOR


def test_the_real_producer_still_reaches_the_coloured_quadrant():
    """反向:真的有方向時照樣出彩色象限 —— fail-closed 不得把正常路擋掉。"""
    _ind = {"PMI": {"value": 55.0}, "YIELD_10Y2Y": {"value": 0.8},
            "CPI": {"value": 1.0}, "PPI": {"value": 1.0}}
    _c = _card3(_ind, _real_calc_macro_phase(_ind))
    assert _c["signal"] not in _GREY_SIGNALS, f"真有方向卻灰掉:{_c['signal']!r}"
    assert _c["color"] != _GREY_COLOR


# ── A5(🟠):F6 的 session 閘門必須被**每一個**刷新入口清掉 ──────────────────
@pytest.mark.parametrize("entry_point", ["tab1_force_refetch", "sidebar_global"])
def test_every_refresh_entry_point_clears_the_hot_money_card_gate(entry_point):
    """F6 那一輪建了閘門,卻只把清除接到**三個入口裡的一個**(⑤ 立即更新)。

    修復前實測:
        Tab① 強制重抓 (clear_tab1_macro_caches) -> clears card gate? False
        Sidebar 全域刷新 (global_refresh_all)    -> clears card gate? False
        Tab5 立即更新                            -> clears (the only one)
    使用者把所有總經資料重載一遍之後,唯獨這張卡還抱著上一輪的失敗結果 ——
    正是 F6 當初要消滅的症狀。

    突變驗證:把 `shared/session_keys.py` 的 `HM_CARD_SESSION_KEYS` 從
    `_TAB1_SESSION_KEYS` / `_GLOBAL_REFRESH_SESSION_KEYS` 任一處拿掉 → 對應格子轉紅。
    """
    if entry_point == "tab1_force_refetch":
        from services.macro import clear_tab1_macro_caches as _fn
    else:
        from infra.cache import global_refresh_all as _fn
    _ss = {k: "stale" for k in _HM_SESSION_KEYS}
    _fn(_ss)
    _left = [k for k in _HM_SESSION_KEYS if k in _ss]
    assert not _left, (
        f"{entry_point} 沒有清掉熱錢卡閘門 {_left} —— "
        "使用者按了刷新,Tab ① 那張卡不會動")


def test_tab5_clears_the_gate_even_when_the_refresh_itself_raises():
    """⑤ 的兩個 `pop` 原本在 `try` **裡面**、且排在 `refresh_hot_money_data(...)`
    **之後** —— 那一行拋例外時(例如 F3 記載的 `StreamlitSecretNotFoundError`),
    閘門**整個 session 都清不掉**,使用者在這一輪沒有任何復原路徑。

    以 AST 驗證:那些 `pop` 必須落在 `Try.finalbody`(`finally`)裡。
    突變驗證:把 `finally:` 改回 `try:` 內的一般語句 → 本條轉紅。
    """
    import ui.tab5_data_guard as _d5
    _tree = ast.parse(pathlib.Path(_d5.__file__).read_text(encoding="utf-8"))
    _in_finally = False
    for _node in ast.walk(_tree):
        if not isinstance(_node, ast.Try) or not _node.finalbody:
            continue
        _src = "\n".join(ast.unparse(s) for s in _node.finalbody)
        if "HM_CARD_SESSION_KEYS" in _src and ".pop(" in _src:
            _in_finally = True
    assert _in_finally, (
        "tab5 的閘門作廢不在 `finally` 裡 —— refresh 拋例外時使用者無法復原")


def test_the_common_hot_money_failure_offers_a_remedy_that_actually_works():
    """`(空 df, err)` 是 L1「內拋外譯」設計下**最常見**的失敗形狀
    (FinMind 402 quota),而它原本拿到的 label 是「展開下方 expander」——
    那個 expander **清不掉本卡的閘門**,展開一百次卡片都不會動。

    修復後:三個灰態分支一律指向真的會作廢閘門的入口。
    突變驗證:把 `_HM_CARD_REMEDY` 改回「展開下方「📦 台股熱錢監測」查看完整判讀」
    → 本條轉紅。
    """
    _empty = pd.DataFrame()
    _recorded = []
    with patch("services.hot_money_service.fetch_hot_money_frames",
               return_value=(_empty, _empty, "FinMind 402 quota", "")), \
         patch.object(tab1_macro, "_render_macro_indicator_card",
                      side_effect=lambda **kw: _recorded.append(kw)):
        _render_top_card_grid(_fake_indicators(), _fake_phase())
    _c = next(c for c in _recorded if c["title"] == "💰 熱錢動向")
    assert _c["signal"] in _GREY_SIGNALS
    # 指的三個入口,必須是本輪實測「真的會清掉閘門」的那三個
    for _needle in ("強制重抓", "全域刷新", "立即更新"):
        assert _needle in _c["label"], (
            f"失敗態沒給可用的去處(缺 {_needle}):{_c['label']!r}")
    assert "展開下方" not in _c["label"], (
        f"仍在指向清不掉閘門的 expander:{_c['label']!r}")


# ── B1(🟡):`_n_trig5` 的條件式是死的 ──────────────────────────────────────
def test_the_calm_headline_count_comes_from_a_real_count_not_a_literal():
    """`_n_trig5 = len(_reasons5) if _al5.get("override") else 0` 的 `else 0`
    **不可達** —— 該變數只在 `if _al5.get("override"):` 分支裡被讀,
    平靜卡的「0 項觸發」其實來自另一個分支的字面值。

    本條把「觸發數」釘成一個**真的隨資料變動**的量:平靜 0、單觸發 1、雙觸發 2。
    突變驗證:把紅燈分支的 `len(_reasons5)` 改成字面值 `2` → 單觸發那格轉紅。
    """
    _one = {**_fake_indicators(), "VIX": {"value": 42.0, "weight": 1, "score": -1}}
    _two = {**_one, "YIELD_10Y2Y": {"value": -0.5, "weight": 2, "score": -2}}
    assert _card5(_CALM_IND, 6.8)["value_str"] == "0 項觸發"
    assert _card5(_one, 6.8)["value_str"] == "1 項觸發"
    assert _card5(_two, 6.8)["value_str"] == "2 項觸發"


# ── B4(🟡):卡 1 必須揭露自己到底是什麼算出來的 ───────────────────────────
def test_phase_card_discloses_that_it_is_the_us_composite_not_ndc():
    """客戶拍板的線框寫「NDC 燈號 ＋ PMI ＋ 殖利率差合成」,實際跑的是
    `calc_macro_phase` 的**美國**加權評分,而 NDC **不在** `EXPECTED_INDICATOR_KEYS`
    裡(由 `ui/helpers/macro/ndc.py` 另外抓,只有 ② 依據用)。

    **本輪不改它算什麼**(那是規格變更,要客戶裁示,已登記 BACKLOG),
    但畫面必須說清楚它是什麼 —— 讓使用者以為這裡有台股 NDC 是另一種誤導。

    突變驗證:把 label 的「未含台灣 NDC 燈號」拿掉 → 本條轉紅。
    """
    _c = _grid_via_real_producer(_fake_indicators())["📊 景氣位階"]
    assert "美國" in _c["label"], f"沒揭露它是美國指標:{_c['label']!r}"
    assert "NDC" in _c["label"], f"沒揭露 NDC 不在裡面:{_c['label']!r}"


def test_expected_indicator_keys_really_does_not_contain_ndc():
    """B4 的事實前提本身也要釘住 —— 否則哪天 NDC 真的被加進去,
    卡 1 的免責聲明會變成一句新的假話。"""
    from services.macro.us_indicators import EXPECTED_INDICATOR_KEYS
    assert not any("NDC" in k.upper() for k in EXPECTED_INDICATOR_KEYS), (
        f"NDC 已進入 EXPECTED_INDICATOR_KEYS,卡 1 的 label 必須同步改:"
        f"{EXPECTED_INDICATOR_KEYS}")


def test_the_sufficiency_threshold_comes_from_the_shared_ssot():
    """§3.3 反捏造:閘門門檻不得是 inline magic number。

    突變驗證:把 `ui/tab1_macro.py` 改成 inline `10.0` → 本條仍綠(它驗的是
    常數存在與值域),但 `test_no_inline_threshold_in_the_card_grid` 會轉紅。
    """
    assert isinstance(_MIN_W, (int, float)) and _MIN_W > 0
    # 推導自 `calc_macro_phase`:單一指標最大權重 2、最窄相位間隔 2 分
    # ⇒ 20 / total_w < 2 ⇒ total_w > 10
    assert _MIN_W == 10.0


def test_no_inline_threshold_in_the_card_grid():
    """漂移鎖:卡片層必須**引用** SSOT 常數,不得自己寫死數字(§3.3)。

    ⚠️ **本條的第一版是假的守衛**:它 grep `inspect.getsource(...)` 找常數名,
    但那個名字**也出現在同一個函式的 docstring 裡** —— 把比較式改成 inline `10.0`,
    測試照樣全綠(實測突變當場抓到)。這與本 repo 憲法自己記載的教訓同型:
    **「grep 會被 docstring 騙」**。改用 AST:比較式右運算元必須是 `Name`,不是常數。

    突變驗證:把 `>= MACRO_PHASE_MIN_TOTAL_WEIGHT` 改成 `>= 10.0` → 本條轉紅。
    """
    _tree = ast.parse(inspect.getsource(tab1_macro._phase_score_support))
    _cmps = [n for n in ast.walk(_tree) if isinstance(n, ast.Compare)]
    assert _cmps, "閘門裡找不到比較式"
    _operands = {ast.unparse(c) for n in _cmps for c in n.comparators}
    assert "MACRO_PHASE_MIN_TOTAL_WEIGHT" in _operands, (
        f"閘門沒有引用 SSOT 常數、而是寫死了數字(§3.3):比較對象為 {_operands}")
    _inline = {o for o in _operands if o.replace(".", "").isdigit()}
    assert not _inline, f"閘門出現 inline magic number:{_inline}"
