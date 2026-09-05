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
from ui.helpers.ia.cards import state_card as _state_card
from ui.tab1_macro import (
    _action_light_renderer,
    _business_alert_action_light,
    _MACRO_CARD_LIGHT_COLOR,
    _render_top_card_grid,
)


# ────────────────────────────────────────────────────────────────────────
# 共用 fixture：一組「五卡全部算得出來」的最小輸入
# ────────────────────────────────────────────────────────────────────────
def _fake_growth_inflation(n_growth: int = 7, n_inflation: int = 3) -> dict:
    """對齊 `calc_growth_inflation_axis` 的真實輸出 schema（含 n_* 觀測筆數）。

    ⚠️ 2026-09-04 稽核 F2：真實 schema 自本日起多了 `growth_dir` / `inflation_dir`
    （`'none'` / `'tie'` / `'up'` / `'down'`）。這裡依 `n_*` 與底下寫死的
    score 正負推出來，讓 fixture 與生產端**同構**；但**手捏的 fixture 永遠不能
    當成 F2 的證據** —— tie 這一整類正是因為所有既有測試都手捏 `n_*` 才看不見。
    F2 的守衛一律走真的 `calc_macro_phase`（見本檔末段）。

    ⚠️ 2026-09-04 第四輪稽核 R4-F1：預設值由 ~~`(3, 3)`~~ 改為 **`(7, 3)`**
    ——**有意識的 fixture 更正，不是漏改**。舊預設代表「成長軸 7 個來源只取到 3 個」，
    而所有既有測試都拿它當「正常情境」；在**重新推導過的**充足性規則下
    （淨邊際 > 沒取到的筆數）那組資料**本來就撐不住象限**（3 > 4 為假）。
    也就是說：舊 fixture 的「正常」在現實裡是「四個來源掛掉」——
    與 F2 那一輪把「3 個指標、權重 5」當正常情境是**同一個病**。
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
        # ⚠️ 2026-09-04 第四輪稽核 R4-F1：真實 schema 自本日起再多三個
        # `EvidenceSupport`（成長軸 / 通膨軸 / 象限聯合）。這裡**不手捏 bool**，
        # 而是拿產出端同一支規則函式建（`net_margin`）—— 手捏一個
        # `sufficient=True` 會讓「產出端到底回報什麼」再一次看不見，
        # 那正是 F2 那一輪的教訓（所有測試都手捏 `n_*`，於是 tie 整類沒人看到）。
        # 這裡假設「有 n 筆、全部同向」（最有利情形），故 n 夠大時才充足。
        **_axis_supports_for(n_growth, n_inflation),
    }


def _axis_supports_for(n_growth: int, n_inflation: int) -> dict:
    """用**產出端的規則函式**替 fixture 生 support（同向 n 筆的最有利情形）。"""
    from services.macro.evidence import GROWTH_AXIS_KEYS, INFLATION_AXIS_KEYS
    from shared.evidence_support import combine, net_margin
    _g = net_margin("成長軸方向",
                    signals={k: 1.0 for k in GROWTH_AXIS_KEYS[:n_growth]},
                    expected=GROWTH_AXIS_KEYS)
    _i = net_margin("通膨軸方向",
                    signals={k: -1.0 for k in INFLATION_AXIS_KEYS[:n_inflation]},
                    expected=INFLATION_AXIS_KEYS)
    return {"growth_support": _g, "inflation_support": _i,
            "support": combine("成長×通膨四象限", _g, _i)}


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


#: 一組「乾淨的平靜態」讀數 —— 每一個都**遠離**自己的觸發門檻。
#: 只列有語意要求的；其餘 key 由 `_fake_indicators()` 用中性值補齊。
_CALM_VALUES: dict = {
    "VIX": 15.0, "YIELD_10Y2Y": 0.8, "YIELD_10Y3M": 0.6, "SAHM": 0.1,
    "PMI": 55.0, "HY_SPREAD": 3.2, "M2": 4.0, "DXY": 100.0,
    "CPI": 2.5, "PPI": 2.0, "FED_RATE": 2.0,
    "ADL": 1.0, "CONSUMER_CONF": 85.0, "JOBLESS": 22.0, "COPPER": 3.0,
}
#: 各 key 的 score 圍繞的**中心值** —— 讓合成分數落在「擴張」帶(5~8)的
#: **中央**(實測 6.5)而不是邊緣。
#: ⚠️ 這一點是**測試設計**，不是隨手填的：新的充足性規則之一是
#: 「沒取到的權重的任何一種實現都必須落在同一條相位帶」——
#: 分數若貼著 8.0 邊界(舊 fixture 給出 8.4)，**拿掉任何一顆指標都會跨帶**，
#: 於是「少一個 override 輸入」那組測試會因為**分數那一半**先失敗，
#: 測不到它真正要測的「點名輸入缺一個」。
_CALM_SCORE: float = 0.3

#: ⚠️ **2026-09-04 第六輪稽核 B4：`score` 不再是「全部同一個值」。**
#: 舊版 28 顆全給 `_CALM_SCORE`，於是整批「充足」fixture 只落在**一個**合成
#: 分數上(6.5)——**而 6.5 正好是「會被灰掉的 6.4」的上面一格**，
#: F-A1 那一整類缺陷因此完全躲在 fixture 後面。
#: 現在改成繞著中心值的一組**互相抵銷**的偏移(和為 0 ⇒ 合成分數仍是 6.5，
#: 既有斷言零變更)，加上 `_fake_indicators(score_target=...)` 可以指定別的分數，
#: 並由 `test_the_card_grid_holds_across_the_whole_score_range` 掃過整條 0~10。
#: **偏移幅度刻意 ≤ 0.15**：最小權重是 0.5，`0.3 ± 0.15` 不會被生產端 clamp，
#: 否則「和為 0」會被 clamp 破壞、合成分數就不再是 6.5 了。
_CALM_SCORE_OFFSETS: tuple[float, ...] = (+0.15, -0.15, +0.05, -0.05)


def _fake_indicators(score_target: "float | None" = None) -> dict:
    """一組「資料充足」的指標 —— **28 個 key 全到齊**，由權重 SSOT 生成。

    `score_target`：想讓 `calc_macro_phase` 合成出哪個 0~10 分數。
    `None` ＝ 沿用預設(實測 6.5，落在「擴張」帶中央)。
    ⚠️ **近似,不是精確命中**:每顆的 score 會被 clamp 在 `[-w, w]`,
    所以靠近 0 / 10 兩端時實得分數會被拉回來(實測 `target=0.0 → 1.0`)。
    要用它的測試請斷言**實得**分數，不要斷言 target。

    ⚠️ 2026-09-04 **第四輪**稽核 R4-F1/F6：本 fixture 原本只有 **10 個指標、
    權重合計 12.5**，並自稱「資料充足」。在**重新推導過的**門檻下它撐不住：
      · 殖利率 10Y-2Y 與 10Y-3M 是**同一條曲線的兩個讀數**（相關族權重 **4**），
        需 `total_w > 5 × 4 = 20`，12.5 不到；
      · 而且 28 個 key 只到 10 個 → 沒取到的權重約 15.5，那些若全部反向，
        分數會橫跨好幾條相位帶 —— 「充足」二字當時就不成立。
    **這與第三輪把 fixture 從 3 個指標補到 10 個是同一件事的下一輪**：
    每一輪都以為自己補夠了，因為每一輪都拿**當時那條閘門**當標準。
    現在直接**從權重表 SSOT 生成全集**，門檻再怎麼改都不會有「fixture 剛好卡在
    邊界上」這種事，也不必再有人手動維護筆數。

    性質（測試依賴這幾點，改動前請先讀）：
      · **28 個 key 全在** → 沒取到的權重 = 0 → 相位帶與買賣燈帶的不變性都成立；
        ⚠️ **2026-09-04 第六輪稽核 B4：這一句在 `fb770b4` 上是假的。**
        F1 的加寬把可及區間的**上界**多算了一格，於是「28 顆全在、0 顆缺漏」
        的狀態照樣會被判不足(實測:合成分數 4.9 與 7.9 兩格)。
        本句今天成立，靠的是 F-A1 的修法
        (`shared/evidence_support.weighted_verdict` 裡 `_M <= 0 < _T` 那條短路，
        它把「沒取到的權重為 0 ⇒ 可及顯示值恆為 `{score}`」寫成**可證**的短路，
        而不是靠兩個端點各自 round 碰運氣)。
        ⚠️ 也**不要**把它讀成「任何充足性規則都過」——
        那是一句對**未來規則**的全稱話，本 fixture 擔保不起。
        支配性條件(單一相關族不得說了算)就與缺漏無關，是靠 28 顆的權重總量過的。
      · 四個 override 輸入（`YIELD_10Y2Y` / `YIELD_10Y3M` / `SAHM` / `VIX`）
        **全部有值且遠離門檻** → 卡 5 的綠燈有資格宣稱「均未觸發」；
      · 兩軸訊號同向 → 象限定得出方向（不是打平）。
    """
    from services.macro.evidence import MACRO_INDICATOR_SCORING_WEIGHTS as _W
    _centre = _CALM_SCORE
    if score_target is not None:
        # `norm = (earned + T) / (2T) * 10` ⇒ earned = (target/10*2-1)*T，
        # 平均分攤到 28 顆(再疊上偏移)。
        _tw = sum(_W.values())
        _centre = (float(score_target) / 10.0 * 2 - 1) * _tw / len(_W)
    _ind: dict = {}
    for _i, (_k, _w) in enumerate(_W.items()):
        # B4：偏移繞著中心值，**和為 0** ⇒ 合成分數不變，但每顆的 score 不同，
        # 「所有 fixture 都落在同一個魔術數字上」那個盲區沒有了。
        _sc = _centre + _CALM_SCORE_OFFSETS[_i % len(_CALM_SCORE_OFFSETS)]
        _sc = max(-_w, min(_w, _sc))          # 與生產端同樣先 clamp
        _node = {"value": _CALM_VALUES.get(_k, 1.0), "weight": _w, "score": _sc}
        if _k == "ADL":       # 雙軸讀的是 `prev`（月變動 %），不是 `value`
            _node["prev"] = 1.0
        _ind[_k] = _node
    return _ind


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
    assert _c["label"] == "7 個成長訊號、3 個通膨訊號"


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
from services.macro.composite_score import (
    calculate_composite_score as _real_composite_score,
)
from ui.hot_money import STATE_TEXT as _STATE_TEXT

#: 成長軸七項**全部取到且同向向上**（PMI/10Y2Y/M2/ADL/信心/初領/銅）。
#: ⚠️ 2026-09-04 第四輪稽核 R4-F1：這幾組 fixture 原本只帶 4 個指標，
#: 於是**成長軸自己就先撐不住**（7 取 2）—— 測到的其實是「成長軸資料不足」，
#: 不是它們宣稱要測的「通膨軸打平」。補齊成長軸，讓打平成為**唯一**綁住的理由。
_GROWTH_ALL_UP = {
    "PMI": {"value": 55.0}, "YIELD_10Y2Y": {"value": 0.8},
    "M2": {"value": 4.0}, "ADL": {"prev": 1.0},
    "CONSUMER_CONF": {"value": 85.0}, "JOBLESS": {"value": 22.0},
    "COPPER": {"value": 3.0},
}
#: 通膨軸打平：CPI 4.0 ≥ 3.0 → +1；PPI 1.0 < 3.0 → −1；score = 0.00
_IND_INFLATION_TIE = {**_GROWTH_ALL_UP,
                      "CPI": {"value": 4.0}, "PPI": {"value": 1.0}}
#: 成長軸打平：七項裡取到六項、三上三下 → score = 0.00
_IND_GROWTH_TIE = {"PMI": {"value": 55.0}, "YIELD_10Y2Y": {"value": 0.8},
                   "M2": {"value": 4.0},
                   "ADL": {"prev": -1.0}, "CONSUMER_CONF": {"value": 50.0},
                   "JOBLESS": {"value": 35.0},
                   "CPI": {"value": 1.0}, "PPI": {"value": 1.0},
                   "FED_RATE": {"value": 2.0}}
#: 雙軸都打平
_IND_BOTH_TIE = {"PMI": {"value": 55.0}, "YIELD_10Y2Y": {"value": 0.8},
                 "M2": {"value": 4.0},
                 "ADL": {"prev": -1.0}, "CONSUMER_CONF": {"value": 50.0},
                 "JOBLESS": {"value": 35.0},
                 "CPI": {"value": 4.0}, "PPI": {"value": 1.0}}
#: 對照組：通膨**真的**受控（三項全低）—— 與打平必須畫得不一樣
_IND_INFLATION_REALLY_DOWN = {**_GROWTH_ALL_UP,
                              "CPI": {"value": 1.0}, "PPI": {"value": 1.0},
                              "FED_RATE": {"value": 2.0}}


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
    # ⚠️ 2026-09-04 第四輪稽核：燈號由 ~~`⬜ 方向不明`~~ 改為 **`⬜ 資料不足`**
    # （**有意識的更正，不是放寬**）。理由：新的通則「淨邊際 > 沒取到的筆數」
    # **已經涵蓋打平**，而打平要成立就必須有偶數筆觀測 → 兩軸輸入數都是奇數
    # （7 / 3）→ **打平必然伴隨缺項**，於是不存在「純打平、零缺項」這個狀態。
    # 為它保留一個獨立分支＝留一段永遠走不到的碼。**判定沒有放寬**：
    # 打平依舊不得畫成象限（下面三條斷言逐條比舊版更嚴，多了「不得是彩色」）。
    assert _c["signal"] in _GREY_SIGNALS, (
        f"{tie_axis}軸訊號相抵，卡片卻下了「{_c['signal']}」定論（§1 Fail Loud, Never Fake）")
    # ⚠️ 2026-09-04 第五輪稽核 F7：**把第二輪的「打平 ≠ 沒抓到」那道分辨復原。**
    # a88f896 把 `assert _c["signal"] != "⬜ 待取得"` ＋ `assert "不是缺資料" in note`
    # 兩條併成上面那一句 `in _GREY_SIGNALS` —— 而 `_GREY_SIGNALS` 收了全部五種灰字串，
    # 於是「把打平塌成『還沒抓到，重新載入一下』」變成**沒有守衛**（實測：那個突變下
    # 整份測試檔照樣全綠）。行為今天仍是對的，但**對的行為沒有守衛＝下一輪會壞**。
    assert _c["signal"] != "⬜ 待取得", (
        f"{tie_axis}軸打平被塌成「還沒抓到」—— 使用者會去重新載入，但重新載入"
        f"不會讓相抵的訊號變成一個方向：{_c['signal']!r}")
    assert _c["color"] == _MACRO_CARD_LIGHT_COLOR["gray"]
    # note 必須逐字說出「正負相抵」——使用者要能分辨「沒抓到」與「抓到但抵銷」
    assert "正負相抵" in _c["note"], (
        f"沒說清楚是打平而不是沒抓到：{_c['note']!r}")
    for _axis_name in tie_axis.split("／"):
        assert _axis_name in _c["note"], (
            f"note 沒點名是哪一軸打平（缺 {_axis_name}）：{_c['note']!r}")
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
    assert _real["signal"] == "🌱 復甦/擴張", (
        f"對照組本身要能正常出象限（回歸）：{_real['signal']!r} / {_real['note']!r}")
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
    """回歸：零觀測（P1 那條）與打平（F2 這條）**在畫面上要分得開**。

    ⚠️ 2026-09-04 第四輪稽核：分辨點由「兩個不同的**燈號**」改為
    「同一個灰態、但 **note 逐字說出是哪一種**」（**有意識的更正，不是放寬**）。
    理由見 `ui/tab1_macro.py` 卡 3 的段落：`⬜ 方向不明` 這一格在現有輸入數下
    **永遠走不到**（打平需要偶數筆觀測，而兩軸輸入數都是奇數 → 打平必然帶缺項
    → 先被「淨邊際 > 缺項數」這條通則擋下）。留著它＝留一段死碼。
    **使用者要分辨的是「該不該按重新載入」，而那句話現在寫在 note 裡。**
    """
    _phase_zero = dict(_fake_phase())
    _phase_zero["growth_inflation"] = _fake_growth_inflation(n_growth=1, n_inflation=0)
    _zero = _card3(_fake_indicators(), _phase_zero)
    _tie = _card3_via_real_producer(_IND_INFLATION_TIE)
    assert _zero["signal"] == "⬜ 待取得"
    assert _tie["signal"] in _GREY_SIGNALS
    # F7（同上）：兩者**燈號字串本身**也不得相同，不是只有 note 不同。
    assert _tie["signal"] != _zero["signal"], (
        f"打平與零觀測畫成同一個灰燈：{_tie['signal']!r}")
    # 兩者的**理由**必須不同，且各自說對自己那一種
    assert "一項都沒取到" in _zero["note"], _zero["note"]
    assert "正負相抵" in _tie["note"], _tie["note"]
    assert _zero["note"] != _tie["note"]


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
        # `roll_n` = 這筆累計背後真的有幾個重疊交易日（2026-09-04 R4-F11 新增）。
        # 手捏 fixture 必須帶它，否則測到的是「重疊日不足 → 灰態」那條分支。
        "roll_flow": 10.0, "roll_n": 5.0, "state": state, "is_divergence": False,
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
#: ⚠️ 2026-09-04 **第四輪**稽核 R4-F9:這個常數原本是 `"載入總經資料"` ——
#: 一個**手抄的子字串**,而畫面上那顆鈕在快覽網格渲染時**根本不是那個字**
#: (網格只在 `macro_done` 為真時渲染,鈕上是「🔄 更新總經資料」;
#:  「📡 載入總經資料」只在首次載入**之前**出現,那時網格還沒畫)。
#: 也就是說:舊斷言查的是一個**使用者永遠看不到**的字串,卻長得像在守護三要素。
#: 現在直接比對 L0 SSOT `shared/ui_control_labels.py` —— 控制項改字時,
#: 渲染端與文案端**同時**改,而這條斷言拿的是同一份常數。
from shared.ui_control_labels import (  # noqa: E402
    MACRO_FORCE_REFETCH_CHECKBOX as _LBL_FORCE_REFETCH,
    MACRO_LOAD_BTN_AGAIN as _LBL_LOAD_AGAIN,
    MACRO_LOAD_BTN_FIRST as _LBL_LOAD_FIRST,
    SIDEBAR_GLOBAL_REFRESH_BTN as _LBL_GLOBAL_REFRESH,
)

_LOAD_BUTTON_LABEL = _LBL_LOAD_AGAIN


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
    assert "一項都沒取到" in _c["note"], _c["note"]


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
from services.macro.evidence import scoring_weight as _scoring_weight

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

    突變驗證:把閘門從「不變性 + 支配性」放寬成 `> 0`
    → 本條兩個格子都轉紅(那正是「只修零觀測、不修這一類」的樣子)。
    """
    # 先證明上游真的會給出那個彩色定論(否則這條測試在守一個不存在的風險)
    _phase = _real_calc_macro_phase(ind)
    assert _phase["phase"] == would_be, (
        f"前提不成立:上游給的是 {_phase['phase']!r} 不是 {would_be!r}")
    _c = _grid_via_real_producer(ind)["📊 景氣位階"]
    assert _c["signal"] in _GREY_SIGNALS, (
        f"單一指標(權重合計 {_scoring_weight(ind)})"
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

    突變驗證:把 `services/macro/evidence.py::scoring_weight` 的 `.get("weight", 1)` 改成
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
        _card_w = _scoring_weight(_ind)
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
    assert tab1_macro._phase_score_support(
        _ind, _real_calc_macro_phase(_ind)).sufficient, "前提:證據仍然充足"
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
    assert not tab1_macro._phase_score_support(
        _ind, _real_calc_macro_phase(_ind)).sufficient, "前提:證據不足"
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
    assert "沒有回報證據支撐" in _c["note"], (
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
    _ind = _IND_INFLATION_REALLY_DOWN
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

    ⚠️ 2026-09-04 第五輪:本條原本先斷言 ~~`isinstance(_MIN_W, ...) and _MIN_W > 0`~~
    （**有意識的更正，不是漏刪**）—— `MACRO_PHASE_MIN_TOTAL_WEIGHT` 已隨孤兒清理
    刪除。它驗的東西（門檻不是憑空打上去的數字）改由下面那段推導鎖承接，
    **而且比舊斷言強**：舊斷言只要求「是個正數」。
    """
    # ⚠️ 2026-09-04 第四輪稽核 R4-F6:舊斷言是 `_MIN_W == 10.0`，
    # 而 10.0 的推導前提「**單一指標最大權重是 2**」**是假的** ——
    # 殖利率 10Y-2Y / 10Y-3M 是同一條曲線的兩個讀數（族權重 **4**），
    # 美元指數與三條美元交叉匯率同理（也是 4）。
    # **舊斷言鎖的是那個假前提算出來的數字，所以它從一開始就鎖錯了東西。**
    # 現在改成**鎖推導本身**：常數必須逐項等於
    #   （10 / 最窄相位帶）× 全部到齊時的最大相關族權重
    # —— 任何一個輸入(權重表 / 族表 / 相位邊界)變了，它就會自己跟著變，
    # 而不是留在那裡當一個沒人重算的舊數字。
    from services.macro.evidence import (
        MAX_CORRELATED_FAMILY_WEIGHT as _MAXFAM,
        PHASE_NARROWEST_BAND as _NARROW,
        PHASE_SCALE as _SCALE,
        PHASE_WEIGHT_PER_BAND as _PER_BAND,
    )
    assert _PER_BAND == _SCALE / _NARROW, "每族所需倍數不是從相位帶推出來的"
    # ⚠️ 2026-09-04 第五輪：~~`assert _MIN_W == _PER_BAND * _MAXFAM`~~ 與
    # ~~`assert (..., _MIN_W) == (..., 20.0)`~~ **已移除**（有意識的更正，不是漏刪）：
    # `MACRO_PHASE_MIN_TOTAL_WEIGHT` 是第四輪改動製造出來的孤兒（production 0 caller），
    # 本輪依 GC 收尾義務實體刪除。**鎖的東西沒有變少**：下面這一行仍然逐項鎖住
    # 同一條推導，只是不再要求有一個常數把結果抄一份。
    assert _PER_BAND * _MAXFAM == 20.0, "推導結果變了（10/2 × 4）"
    # 實測值（量測日 2026-09-04）
    assert (_NARROW, _MAXFAM) == (2.0, 4.0)


def test_the_card_layer_does_not_hand_roll_its_own_sufficiency_gate():
    """漂移鎖:**卡片層不得自己判定「證據夠不夠」**(§3.3 + 本輪的整個重點)。

    ⚠️ 2026-09-04 第四輪稽核:本條取代 ~~`test_no_inline_threshold_in_the_card_grid`~~
    (**有意識的更正,不是刪測試**)。舊條驗的是「比較式右運算元必須是常數名」——
    它預設了「卡片層本來就會自己寫一個比較式」,只管那個比較式有沒有 inline 數字。
    **而本輪的結論是:卡片層根本不該有那個比較式。** 舊條在新結構下形同虛設
    (`_phase_score_support` 已經沒有任何 `Compare`,它只是讀 `.sufficient`),
    留著它只會鎖住一個已經不存在的形狀。

    新條鎖三件事,每一件都可被突變推翻:
      (1) `_phase_score_support` 內**沒有任何比較式**(有 = 又在手推閘門了);
      (2) 它**確實讀了** `.sufficient` 或呼叫產出端的 builder;
      (3) 五卡函式本體內**沒有任何數字字面值**被拿來跟權重比。
    """
    _tree = ast.parse(inspect.getsource(tab1_macro._phase_score_support))
    # `x is None` 這種**存在性**檢查是允許的(它在問「產出端有沒有給我 support」);
    # 被禁的是**數值比較**(拿權重 / 筆數去跟一個門檻比大小)—— 那就是手推閘門。
    _numeric_cmps = [
        ast.unparse(n) for n in ast.walk(_tree)
        if isinstance(n, ast.Compare)
        and not all(isinstance(o, (ast.Is, ast.IsNot)) for o in n.ops)]
    assert not _numeric_cmps, (
        f"卡片層又自己寫了充足性比較式(手推閘門):{_numeric_cmps}")
    # ⚠️ 2026-09-04 第五輪稽核 F6：舊寫法是 `assert "support" in _src` —— **恆真**，
    # 因為同一個函式的 docstring 裡就有「support」這個字（拿掉整個函式體照樣綠）。
    # 改成 AST：必須真的**讀到** `.sufficient`，或真的**呼叫**產出端那支 builder。
    _t2 = ast.parse(inspect.getsource(tab1_macro._phase_score_support))
    _reads_flag = any(isinstance(n, ast.Attribute) and n.attr == "sufficient"
                      for n in ast.walk(_t2))
    _calls_builder = any(
        isinstance(n, ast.Call) and (
            (isinstance(n.func, ast.Name) and "support" in n.func.id)
            or (isinstance(n.func, ast.Attribute) and "support" in n.func.attr))
        for n in ast.walk(_t2))
    assert _reads_flag or _calls_builder, (
        "沒有讀產出端回報的 support（既沒讀 `.sufficient`，也沒呼叫產出端 builder）")

    # 五卡本體:不得出現「跟權重比大小」的 inline 數字
    _grid = ast.parse(inspect.getsource(tab1_macro._render_top_card_grid))
    _bad = []
    for _n in ast.walk(_grid):
        if not isinstance(_n, ast.Compare):
            continue
        _txt = ast.unparse(_n)
        if any(_w in _txt for _w in ("weight", "_score_w", "total_w")) and \
                any(isinstance(c, ast.Constant) and isinstance(c.value, (int, float))
                    for c in _n.comparators):
            _bad.append(_txt)
    assert not _bad, f"卡片層出現 inline 權重門檻(§3.3):{_bad}"


def test_the_five_cards_read_the_producer_support_instead_of_recomputing():
    """**本輪的核心守衛**:五張卡的充足性判定必須來自產出端回報的 `support`。

    突變驗證(逐一實跑,見 PR 描述):把任何一張卡改回自己數筆數 / 自己比權重,
    對應的「撐不住卻上色」測試就會轉紅。這一條則是**結構性**的:它不看行為,
    看的是「卡片層有沒有再長出一個第二真相源」。
    """
    _src = inspect.getsource(tab1_macro._render_top_card_grid)
    _tree = ast.parse(_src)
    # 卡 1 / 卡 3 / 卡 5 各自讀 support 的痕跡(名稱不同、語意相同)
    for _needle in ('_phase_score_support(ind, phase)',   # 卡 1
                    '_gi.get("support")',                  # 卡 3
                    '_al5.get("support")'):                # 卡 5
        assert _needle in _src, f"這張卡沒有讀產出端的 support:{_needle}"
    # 而且**不得**再出現「自己數觀測筆數當閘門」的形態
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.Compare) and "n_growth" in ast.unparse(_n):
            raise AssertionError(
                f"卡 3 又用筆數當閘門了(F2 → R4-F1 的同一個病):{ast.unparse(_n)}")



# ════════════════════════════════════════════════════════════════════════
# 2026-09-04 **第四輪**稽核 —— 把「資料充足性」從卡片層收到**產出端**
#
# 前三輪的修法都是「在被點名的那張卡上再手推一道閘門」，於是每一輪都漏掉
# 同一個類的下一種形態。本輪的規則與漂移鎖在 `tests/test_evidence_support.py`；
# 本段驗的是**消費端有沒有照著讀**，以及第四輪點名的其餘八項。
# ════════════════════════════════════════════════════════════════════════
def test_the_phase_card_greys_out_when_one_family_could_decide_it():
    """R4-F6 的實測邊界：權重合計 10.0、殖利率兩腳都在 → 卡 1 走灰態。

    修復前（`>= 10.0` 定值門檻）：判為「充足」，
    而曲線一族單獨就能把畫面從
        「復甦 4.0/10」#64b5f6「最高勝率買點！逐步加碼…」
    推到
        「擴張 6.0/10」#00c853「股優於債…」
    突變驗證：把 `weighted_verdict` 的族規則拿掉（只留不變性檢查）→ 本條轉紅。
    """
    _base = {"YIELD_10Y3M": {"weight": 2, "score": 2},
             "PMI": {"weight": 2, "score": 2},
             "HY_SPREAD": {"weight": 2, "score": 1},
             "M2": {"weight": 1, "score": 1},
             "VIX": {"weight": 1, "score": 1}}
    _up = {**_base, "YIELD_10Y2Y": {"weight": 2, "score": 2}}
    _dn = {**_base, "YIELD_10Y2Y": {"weight": 2, "score": -2},
           "YIELD_10Y3M": {"weight": 2, "score": -2}}
    assert _scoring_weight(_up) == 10.0, "前提：剛好在舊門檻上"
    # 前提：上游**確實**會因為曲線翻向而跨帶（否則本條在守一個不存在的風險）
    assert _real_calc_macro_phase(_up)["phase"] != _real_calc_macro_phase(_dn)["phase"]
    for _ind in (_up, _dn):
        _c = _grid_via_real_producer(_ind)["📊 景氣位階"]
        assert _c["signal"] in _GREY_SIGNALS, (
            f"單一相關族就能決定的位階仍被上色：{_c['signal']!r}")


def test_the_phase_card_still_shows_the_verdict_on_a_full_healthy_set():
    """反向：28 個指標全到齊 → 照樣出彩色位階（閘門不得把正常情境一起擋掉）。"""
    _c = _grid_via_real_producer(_fake_indicators())["📊 景氣位階"]
    assert _c["signal"] not in _GREY_SIGNALS and "/10" in _c["value_str"]


# ── R4-F2（🟠）：卡 5 的**分數那一半**閘門原本一條測試都沒有 ────────────────
def test_extreme_risk_card_greys_out_when_only_the_score_half_is_insufficient():
    """卡 5 的灰態有**兩個**觸發條件，而其中「分數撐不住」那一半當時沒有任何測試。

    R4-F2 實測：把 `elif _missing5 or not _score_ok5:` 改成 `elif _missing5:`
    → 全部 153 條照樣綠燈，而那個突變會讓「四個 override 輸入齊全、
    但整體只有 6.5 權重」的情境**回到綠燈**。

    本條刻意造出那個情境：四項 override **全部有值**（所以 `_missing5` 為空），
    但**只有它們**（權重 1.5+2+2+1 = 6.5，遠低於任何門檻）。
    突變驗證：把卡 5 的判定改成只看 `_missing5` → 本條轉紅。
    """
    _only_overrides = {
        "YIELD_10Y2Y": {"value": 0.8, "weight": 2, "score": 2},
        "YIELD_10Y3M": {"value": 0.6, "weight": 2, "score": 2},
        "SAHM": {"value": 0.1, "weight": 1.5, "score": 1},
        "VIX": {"value": 15.0, "weight": 1, "score": 1},
    }
    from services.macro.action_light import OVERRIDE_INPUT_KEYS as _KEYS
    assert all(_k in _only_overrides for _k in _KEYS), "前提：四項 override 全在"
    assert _scoring_weight(_only_overrides) == 6.5
    _c = _grid_via_real_producer(_only_overrides)["⚠️ 極端風險警語"]
    assert _c["signal"] == "⬜ 資料不足", (
        f"四項齊全但整體證據撐不住，卡 5 仍下了「{_c['signal']}」")
    assert _c["color"] == _GREY_COLOR


# ── R4-F3（🟠）：卡 2 **本輪新增的兩個灰態**當時沒有「去哪補」 ────────────────
@pytest.mark.parametrize("vix_sig,hy_sig", [
    ("🟢 平靜", "⬜ 無資料"),     # 只量到一盞且為平靜 → 不下綠燈的那一格
    ("⬜ 無資料", "⬜ 無資料"),   # 兩盞都缺
])
def test_volatility_credit_new_empty_states_tell_the_user_where_to_get_the_data(
        vix_sig, hy_sig):
    """線框 Rule 04 三要素：標題 / 缺什麼 / **去哪補**。

    R4-F3：這兩個灰態是第三輪 A2 **新增**的，同一批 commit 給卡 3／卡 5 都補了
    「去哪補」，唯獨這兩格只給到兩項。舊測試 `..._already_has_a_remedy`
    render 的是「整包雷達沒載入」那條**既有**分支，結構上碰不到這兩格。

    突變驗證：把這兩格的 label 改回只有「未與另一盞比較（…）」→ 本條轉紅。
    """
    _c = _card2(vix_sig, hy_sig)
    assert _c["signal"] in _GREY_SIGNALS, "前提：這一格是灰態"
    assert "去哪補" in _c["label"], f"缺「去哪補」：{_c['label']!r}"
    assert _LBL_LOAD_AGAIN in _c["label"], (
        f"「去哪補」沒有指名畫面上真的存在的控制項：{_c['label']!r}")


# ── R4-F12（🟡）：灰態卡不得配一條走勢圖 ────────────────────────────────────
def test_a_grey_volatility_card_carries_no_sparkline():
    """`trend=_worse.get("trend") if _alarm else None` 的 `if _alarm` 是承重的。

    拿掉它 → 一張寫著「資料不足」的灰卡會長出一條走勢圖，看起來像有量測。
    突變驗證：把它改成 `trend=_worse.get("trend")` → 本條轉紅。
    """
    _grey = _card2("🟢 平靜", "⬜ 無資料")
    assert _grey["signal"] in _GREY_SIGNALS and _grey["trend"] is None, (
        f"灰態卻帶著走勢圖：{_grey['trend']!r}")
    # 反向：真的升警時 trend 必須在（不得因為修這條而把警報的圖也拿掉）
    _alarm = _card2("🔴 警報", "⬜ 無資料")
    assert _alarm["trend"] is not None, "真警報的走勢圖被一起拿掉了"


# ── R4-F11（🟡）：卡 4 的「近 5 日累計」必須真的有 5 日 ────────────────────
@pytest.mark.parametrize("roll_n,expect_grey", [(1.0, True), (4.0, True), (5.0, False)])
def test_hot_money_card_requires_the_window_it_names(roll_n, expect_grey):
    """`ui/hot_money.py::build_signals` 用 `min_periods=1`，重疊交易日不足 window 時
    `roll_flow` 只是 1~4 天的和 —— 而卡 4 的頭條與 label **點名了「近 5 日累計」**。

    生產端現在回報 `roll_n`（分母），消費端據此走灰態。
    突變驗證：把 `if not _hm_n_ok:` 那一段拿掉 → `roll_n=1` 那格轉紅。
    """
    _rows = pd.DataFrame([{
        "date": pd.Timestamp("2026-08-14"), "foreign_net_yi": 1.0,
        "roll_flow": 10.0, "roll_n": roll_n, "state": "同步流入",
        "is_divergence": False, "interpretation": "x",
    }])
    with patch("ui.hot_money.build_signals", return_value=_rows):
        _c = _card4(*_flow_fx_where_daily_and_rolling_diverge())
    if expect_grey:
        assert _c["signal"] in _GREY_SIGNALS, (
            f"只有 {roll_n:g} 個重疊交易日，卻宣稱「近 5 日累計」：{_c['signal']!r}")
        assert "重疊交易日" in _c["note"]
    else:
        assert _c["signal"] == "同步流入"


def test_the_producer_reports_the_rolling_denominator():
    """`build_signals` 必須回報 `roll_n` —— 消費端不得自己去猜有幾天。

    突變驗證：把 `df["roll_n"] = ...` 那一行刪掉 → 本條轉紅。
    """
    from ui.hot_money import build_signals
    _flow, _fx = _fake_flow_fx_signal()
    _sig = build_signals(_flow, _fx, window=5, flow_thr=50.0, fx_thr=0.5)
    assert "roll_n" in _sig.columns
    assert list(_sig["roll_n"].head(6)) == [1.0, 2.0, 3.0, 4.0, 5.0, 5.0], (
        "roll_n 不是「這筆累計背後有幾天」")


# ── R4-F8（🟡）：override key 的漂移鎖只鎖 `_val()` 呼叫點 ──────────────────
def test_the_override_key_lock_catches_a_read_that_bypasses_val():
    """`OVERRIDE_INPUT_KEYS` 的漂移鎖必須擋住**任何**指標讀取，不只 `_val(...)`。

    R4-F8 實測：加一個用 `indicators.get("HY_SPREAD")` 讀的第五個 override 輸入
    → 舊鎖（只數 `_val` 呼叫點）**照樣綠燈**，而那正是它的 docstring 說它要防的事。

    本條改成 **fail-closed 的結構檢查**：`macro_action_light` 函式體內
    **任何**以字串字面值當索引 / 參數去碰 `indicators` 的地方，
    那個字串都必須落在 `OVERRIDE_INPUT_KEYS` 裡。
    突變驗證：在 `macro_action_light` 加一行 `indicators.get("HY_SPREAD")` → 本條轉紅。
    """
    import services.macro.action_light as _al_mod
    from services.macro.action_light import OVERRIDE_INPUT_KEYS as _KEYS
    _fn = next(n for n in ast.walk(ast.parse(inspect.getsource(_al_mod)))
               if isinstance(n, ast.FunctionDef) and n.name == "macro_action_light")
    _read: set = set()
    for _n in ast.walk(_fn):
        # `_val(indicators, "KEY")` / `indicators.get("KEY")` / `indicators["KEY"]`
        if isinstance(_n, ast.Call):
            for _a in list(_n.args) + [k.value for k in _n.keywords]:
                if isinstance(_a, ast.Constant) and isinstance(_a.value, str) \
                        and _a.value.isupper():
                    _read.add(_a.value)
        if isinstance(_n, ast.Subscript) and isinstance(_n.slice, ast.Constant) \
                and isinstance(_n.slice.value, str) and _n.slice.value.isupper():
            _read.add(_n.slice.value)
    assert _read, "掃不到任何指標讀取 —— 這條鎖失效了（fail-closed：直接紅）"
    assert _read == set(_KEYS), (
        f"函式實際讀的 key 與 `OVERRIDE_INPUT_KEYS` 不一致：\n"
        f"  只在函式裡：{sorted(_read - set(_KEYS))}\n"
        f"  只在常數裡：{sorted(set(_KEYS) - _read)}")


# ── R4-F10（🟡）：session key 的字面值鎖只掃兩個檔 ──────────────────────────
def test_no_production_file_reintroduces_a_literal_session_key():
    """B2 的字面值鎖必須掃**整個 production 樹**，不只 `tab1_macro` / `tab5`。

    R4-F10 實測：在 `infra/cache.py` 或 `services/macro/_helpers.py`
    （A5 剛接上的那兩個檔）寫回字面值 → 舊鎖照樣綠燈。
    突變驗證：在 `infra/cache.py` 加一行 `_x = "_hm_card_frames"` → 本條轉紅。
    """
    from shared import session_keys as _sk
    _literals = set(_sk.HM_CARD_SESSION_KEYS)
    _offenders: list = []
    for _root in ("ui", "services", "infra", "repositories", "shared"):
        for _f in pathlib.Path(_root).rglob("*.py"):
            if _f.as_posix() == "shared/session_keys.py":
                continue          # SSOT 本人就是唯一准許持有字面值的地方
            _tree = ast.parse(_f.read_text(encoding="utf-8"))
            for _n in ast.walk(_tree):
                if isinstance(_n, ast.Constant) and isinstance(_n.value, str) \
                        and _n.value in _literals:
                    _offenders.append(f"{_f}:{_n.lineno} → {_n.value!r}")
    assert not _offenders, (
        "session 鍵名又被寫成字面值（SSOT 在 `shared/session_keys.py`）：\n"
        + "\n".join(_offenders))


# ── R4-F4（🟠）：刷新入口的列舉必須是**結構性**的，不是抄一份清單 ────────────
def test_every_place_that_resets_macro_done_also_invalidates_the_card_gate():
    """把 `macro_done` 設回 False ＝ 一個「重新載入總經」的入口 → 必須作廢卡 4 的閘門。

    R4-F4 實測：`ui/tab5_data_guard.py` 的「🔄 重新載入總經」是**第五個**入口，
    它把 `macro_done` 設 False 卻**什麼都沒清**，就在 A5 修好的那顆按鈕上方
    250 行、同一個檔案裡。而舊守衛是一份**列舉兩個入口的 parametrize** ——
    結構上不可能發現第三個。

    本條改成**結構性列舉**：掃 `ui/**` 每一個 `... .macro_done = False`，
    要求它所在的那個 `if`/函式區塊裡也有作廢卡片閘門的動作。
    突變驗證：把 tab5 那一段的 `pop(...)` 迴圈刪掉 → 本條轉紅。
    """
    _clearers = ("HM_CARD_SESSION_KEYS", "_HM_K", "clear_tab1_macro_caches",
                 "global_refresh_all")
    _bad: list = []
    for _f in pathlib.Path("ui").rglob("*.py"):
        _src = _f.read_text(encoding="utf-8")
        if "macro_done" not in _src:
            continue
        _tree = ast.parse(_src)
        for _fn in ast.walk(_tree):
            if not isinstance(_fn, (ast.FunctionDef, ast.If, ast.With)):
                continue
            _blk = ast.unparse(_fn)
            _resets = [_n for _n in ast.walk(_fn)
                       if isinstance(_n, ast.Assign)
                       and "macro_done" in ast.unparse(_n.targets[0])
                       and isinstance(_n.value, ast.Constant)
                       and _n.value.value is False]
            if not _resets:
                continue
            # 只看**最內層**那個含 reset 的區塊（`If` 通常就是按鈕的分支）
            if isinstance(_fn, ast.FunctionDef):
                continue
            if not any(_c in _blk for _c in _clearers):
                _bad.append(f"{_f}:{_resets[0].lineno}")
    assert not _bad, (
        "有「重新載入總經」的入口沒有作廢熱錢卡的 session 閘門"
        f"（使用者按了刷新，那張卡不會動）：{_bad}")


# ── R4-F9（🟡）：「去哪補」指名的控制項必須真的長那個樣子 ────────────────────
def test_every_remedy_names_a_control_that_actually_exists_on_screen():
    """三則「去哪補」當時全部指錯（指名了畫面上不存在的字串）。

    修法：控制項標籤收 L0 SSOT，渲染端與文案端讀**同一份常數**。
    本條驗兩件事：
      (1) 文案裡指名的字串，必須是 SSOT 裡的某一個標籤；
      (2) 那些標籤必須真的被拿去渲染控制項（否則 SSOT 只是換個地方寫死）。
    突變驗證：把 `_MACRO_RELOAD_REMEDY` 改回寫死「📡 載入總經資料」→ 本條轉紅。
    """
    _remedies = [tab1_macro._MACRO_RELOAD_REMEDY, tab1_macro._HM_CARD_REMEDY,
                 tab1_macro._RADAR_RELOAD_REMEDY]
    _ssot = {_LBL_LOAD_AGAIN, _LBL_LOAD_FIRST, _LBL_FORCE_REFETCH,
             _LBL_GLOBAL_REFRESH}
    for _r in _remedies:
        assert any(_lbl in _r for _lbl in _ssot), (
            f"「去哪補」沒有指名任何一個 SSOT 標籤（＝手抄的字串）：{_r!r}")
    # 快覽網格只在 `macro_done` 為真時渲染 → 鈕上必然是 `..._AGAIN`
    assert _LBL_LOAD_AGAIN in tab1_macro._MACRO_RELOAD_REMEDY
    assert _LBL_LOAD_FIRST not in tab1_macro._MACRO_RELOAD_REMEDY, (
        "指名了一個「網格渲染時畫面上不會出現」的按鈕字（R4-F9）")
    # (2) 標籤真的被拿去渲染 —— **走 AST，不比對縮排**。
    #     上一版用 `"st.checkbox(\n                _LBL_FORCE_REFETCH,"` 這種
    #     連空白數都寫死的子字串斷言，任何一次 reformat 都會誤報，而它**驗不到**
    #     真正要驗的事（那個常數有沒有被當成 widget 的 label 傳進去）。
    def _label_names_of_widgets(_path: str) -> set:
        """回傳「以 `Name` 形式出現在 widget 呼叫參數裡」的識別字集合。

        涵蓋兩種寫法：直接傳（`st.checkbox(_LBL_X, ...)`）與
        先賦值再傳（`_l = A if c else B` → `st.form_submit_button(_l)`）。
        """
        _tree = ast.parse(pathlib.Path(_path).read_text(encoding="utf-8"))
        # `applied_form` 是本 repo 的 form 包裝器，送出鈕的字走 `submit_label=`。
        _widget = {"button", "checkbox", "form_submit_button", "radio",
                   "selectbox", "toggle", "applied_form"}
        _label_kw = {None, "label", "submit_label"}
        # **先**把全檔的賦值收完，再掃呼叫 —— `ast.walk` 不保證賦值先於使用被走到。
        _assigns: dict = {}
        for _n in ast.walk(_tree):
            if isinstance(_n, ast.Assign) and len(_n.targets) == 1 \
                    and isinstance(_n.targets[0], ast.Name):
                _assigns.setdefault(_n.targets[0].id, set()).update(
                    _x.id for _x in ast.walk(_n.value)
                    if isinstance(_x, ast.Name))
        _out = set()
        for _n in ast.walk(_tree):
            if not isinstance(_n, ast.Call):
                continue
            _fn = _n.func
            _name = _fn.attr if isinstance(_fn, ast.Attribute) else (
                _fn.id if isinstance(_fn, ast.Name) else "")
            if _name not in _widget:
                continue
            for _a in list(_n.args) + [_k.value for _k in _n.keywords
                                       if _k.arg in _label_kw]:
                for _x in ast.walk(_a):
                    if isinstance(_x, ast.Name):
                        _out.add(_x.id)
                        _out |= _assigns.get(_x.id, set())
        return _out

    _t1_labels = _label_names_of_widgets("ui/tab1_macro.py")
    assert "_LBL_FORCE_REFETCH" in _t1_labels, (
        "「強制重抓」勾選框沒有讀 SSOT 常數 → 文案指名的字會漂移")
    assert "_LBL_MACRO_LOAD_AGAIN" in _t1_labels, (
        "總經送出鈕沒有讀 SSOT 常數 → 文案指名的字會漂移")
    assert "_LBL_GLOBAL_REFRESH" in _label_names_of_widgets("ui/sidebar.py"), (
        "側欄全域刷新鈕沒有讀 SSOT 常數 → 文案指名的字會漂移")
    _t1 = pathlib.Path("ui/tab1_macro.py").read_text(encoding="utf-8")
    _sb = pathlib.Path("ui/sidebar.py").read_text(encoding="utf-8")
    # 且**不得**再有第二份字面值（那就是漂移的來源）
    for _f, _lbls in ((_t1, (_LBL_GLOBAL_REFRESH,)),
                      (_sb, (_LBL_LOAD_AGAIN, _LBL_FORCE_REFETCH))):
        for _lbl in _lbls:
            assert _lbl not in _f, f"標籤被抄成第二份字面值：{_lbl!r}"


def test_the_hot_money_remedy_no_longer_names_a_button_that_is_a_checkbox():
    """R4-F9：`_HM_CARD_REMEDY` 原本寫「按上方『🔄 強制重抓』」——
    上方那個其實是**勾選框**「🆕 強制重抓最新（清快取）」，勾了還要按送出鈕。"""
    _r = tab1_macro._HM_CARD_REMEDY
    assert _LBL_FORCE_REFETCH in _r and "勾" in _r, _r
    assert _LBL_GLOBAL_REFRESH in _r, f"側欄那顆鈕的字也指錯了：{_r!r}"


def test_the_stale_comment_about_the_archived_expander_is_gone():
    """R4-F9 末項：`_HM_CARD_REMEDY` 上方的註解宣稱 ARCHIVED expander
    「清不掉本卡的 session 閘門」—— **A5 之後它清得掉**（那顆鈕呼叫
    `clear_tab1_macro_caches`，而 A5 把卡片鍵加進了它的清單）。

    本條驗三件事，缺一不可：
      (1) 那句已被推翻的斷言不得再以**未劃線**的形式留在檔案裡；
      (2) 正面驗事實 —— 那顆鈕走的 clearer 真的會清掉卡片閘門；
      (3) 那條鏈路真的存在（expander → `render_hot_money_section` → clearer），
          否則 (2) 只是驗了一個沒人走的函式。
    突變驗證：把 `~~` 拿掉、讓那句斷言變回直述 → (1) 轉紅；
    把 `services/macro/_helpers.py` 的 `HM_CARD_SESSION_KEYS` 展開拿掉 → (2) 轉紅。
    """
    _src = pathlib.Path("ui/tab1_macro.py").read_text(encoding="utf-8")
    # (1) 斷言本體仍可保留（本檔慣例：舊表述不刪），但**必須**被劃線 + 標明更正
    _claim = "expander **清不掉**"
    _hits = [_ln for _ln in _src.splitlines()
             if _claim in _ln and _ln.lstrip().startswith("#")]
    assert _hits, "舊表述被整句刪掉了 —— 本檔慣例是保留 + 劃線，不是刪除"
    for _ln in _hits:
        assert "~~" in _ln, (
            f"已被推翻的斷言仍以直述句留著（讀者會照信）：{_ln.strip()!r}")
    assert "A5 之後這句是假的" in _src, "沒有寫明它為什麼被推翻"
    # (2) 正面驗事實：expander 那顆鈕走的 clearer 真的會清掉卡片閘門
    from services.macro import clear_tab1_macro_caches as _fn
    _ss = {k: "stale" for k in _HM_SESSION_KEYS}
    _fn(_ss)
    assert not [k for k in _HM_SESSION_KEYS if k in _ss], (
        "`clear_tab1_macro_caches` 沒有清掉卡片閘門 —— "
        "那註解的更正就變成另一句假話")
    # (3) 鏈路真的存在：ARCHIVED expander 內確實呼叫 render_hot_money_section，
    #     而該函式內確實有一顆鈕呼叫 clearer
    _lt = pathlib.Path("ui/tab1_macro_longterm.py").read_text(encoding="utf-8")
    assert "render_hot_money_section" in _lt
    _hm = pathlib.Path("ui/hot_money.py").read_text(encoding="utf-8")
    assert "clear_tab1_macro_caches" in _hm, (
        "expander 那顆鈕不再呼叫 clearer → 註解的更正過期，須重寫")


# ── ①結論 / ②依據：客戶明示授權的行為變更 ──────────────────────────────────
def test_the_conclusion_line_has_a_grey_renderer_that_is_not_the_amber_one():
    """①結論的灰態**不得**落到 `st.warning` —— 琥珀在本頁是「🟡 持有」這個**定論**
    的顏色，把「我不知道」畫成「持有」正是本輪要根除的那個類。"""
    assert _action_light_renderer("⬜") is st.info
    assert _action_light_renderer("🟡") is st.warning
    assert _action_light_renderer("⬜") is not _action_light_renderer("🟡")


def test_the_conclusion_line_goes_grey_under_a_total_outage():
    """①結論：完全斷線 → 灰態，且**不得**印那句「均未觸發」。

    ⚠️ 本條是**行為測試**，不是字串搜尋。前一版寫的是
    `assert '_al.get("support")' in inspect.getsource(render_macro_tab)` ——
    那種寫法擋不住 `if not _al_ok:` → `if False:` 這種突變（實測：改成
    `if False:` 之後整份測試檔照樣全綠）。故本輪把「印什麼」抽成純函式
    `_conclusion_line_state()`，這裡直接驗它的輸出。
    突變驗證：把 `_conclusion_line_state` 的灰態分支條件改成恆假 → 本條轉紅。
    """
    _al = _real_action_light(_TOTAL_OUTAGE_IND, _real_calc_macro_phase(
        _TOTAL_OUTAGE_IND)["score"])
    assert not _al["support"].sufficient, "前提：完全斷線時 support 撐不住"
    # ⚠️ 2026-09-04 第五輪稽核 F2：舊前提是
    # ~~`assert "均未觸發" in "；".join(_al["reasons"])`~~（**有意識的更正，不是刪測試**）
    # —— 它斷言「產出端仍然吐那句假話，所以灰態必須不印它」。F2 之後那句假話
    # **在產出端就被扣掉了**（四項缺一項就不印），前提結構上不再成立。
    # 換成更強的版本：產出端**必須**已經把它換成一句誠實的話。
    assert "均未觸發" not in "；".join(_al["reasons"]), (
        "產出端仍然在四項全缺時吐「均未觸發」")
    assert not _al["all_clear_support"].sufficient, "前提：那句話撐不住"
    assert _al["all_clear_support"].reason in "；".join(_al["reasons"]), (
        "產出端沒有把缺了哪幾項寫進 reasons")

    _light, _lines = tab1_macro._conclusion_line_state(_al)
    _txt = "\n".join(_lines)
    assert _light == "⬜", f"完全斷線卻給了定論燈：{_light!r}"
    assert tab1_macro._action_light_renderer(_light) is st.info, (
        "灰態落到了 st.warning（琥珀＝「🟡 持有」這個定論的顏色）")
    assert "撐不起任何結論" in _txt, _txt
    assert "均未觸發" not in _txt, (
        "灰態仍然照抄了 `reasons` 裡那句「四項均未觸發」—— 那四項一項都沒取到")
    assert _al["action"] not in _txt, "灰態仍然給了加碼／減碼建議"
    assert tab1_macro._MACRO_RELOAD_REMEDY in _txt, "灰態沒有「去哪補」（線框 Rule 04）"
    assert _al["support"].reason in _txt, "灰態沒有寫「缺什麼」（線框 Rule 04）"


def test_the_conclusion_line_is_untouched_when_the_evidence_stands():
    """反向：證據夠時①結論**一字不改**照舊（本輪只改「不足時怎麼辦」）。"""
    _ind = _fake_indicators()
    _al = _real_action_light(_ind, _real_calc_macro_phase(_ind)["score"])
    assert _al["support"].sufficient, "前提：資料夠時 support 撐得住"
    _light, _lines = tab1_macro._conclusion_line_state(_al)
    _txt = "\n".join(_lines)
    assert _light == _al["light"] and _light != "⬜"
    assert _al["action"] in _txt and all(_r in _txt for _r in _al["reasons"])


def test_a_red_alarm_is_never_greyed_out_even_on_partial_evidence():
    """規則 3（不對稱）在①結論上的落地：**半套證據可以升警，不可以解除警報**。

    `override=True` 的 🔴 由實際越線的觀測作證 → 產出端回報充足 → 走不到灰態。
    突變驗證：把 `action_light_support()` 的 witnessed 規則改成也看 missing
    → 本條轉紅（警報被自己的缺資料閘門吃掉）。
    """
    # 只有 VIX，而且是恐慌值 —— 其餘 17 項全缺
    _ind = {**_TOTAL_OUTAGE_IND, "VIX": {"value": 45.0, "weight": 1, "score": -2}}
    _al = _real_action_light(_ind, _real_calc_macro_phase(_ind)["score"])
    assert _al.get("override") and _al["light"] == "🔴", _al
    assert _al["support"].sufficient, "警報被缺資料閘門吃掉了（規則 3 反了）"
    _light, _ = tab1_macro._conclusion_line_state(_al)
    assert _light == "🔴", f"警報被灰掉：{_light!r}"


def test_the_evidence_table_greys_the_composite_verdict_when_it_cannot_stand():
    """②依據的 🩺 綜合健康度列：撐不住 → 不給等級、不給行動，但**分數照印**。

    ⚠️ 同上，本條驗的是抽出來的純函式 `_composite_verdict_cells()` 的**輸出**，
    不是 `render_macro_tab` 的原始碼字串。
    突變驗證：把 `_composite_verdict_cells` 的灰態分支條件改成恆假 → 本條轉紅。
    """
    from ui.helpers.macro.beginner_view import build_evidence_rows
    _prov: dict = {}
    _score = _real_composite_score(_TOTAL_OUTAGE_IND, provenance_out=_prov)
    _sup = _prov.get("support")
    assert _sup is not None and not _sup.sufficient, "前提：完全斷線時撐不住"

    _icon, _level, _action, _note = tab1_macro._composite_verdict_cells(_score, _sup)
    assert (_icon, _level, _action) == ("⬜", "資料不足", ""), (_icon, _level, _action)
    assert _sup.reason in _note and tab1_macro._MACRO_RELOAD_REMEDY in _note
    # 分數照印（它是真的加總，不是捏造的）
    _rows = build_evidence_rows(None, composite_score=_score,
                                composite_icon=_icon, composite_level=_level,
                                composite_action=_action, n_indicators=0)
    _strength = [r for r in _rows if "強度" in str(r)][0]
    assert "⬜ 資料不足" in str(_strength) and f"{_score:+.1f}" in str(_strength)


def test_the_evidence_table_is_untouched_when_the_evidence_stands():
    """反向：證據夠時 🩺 那一列一字不改（含行動建議）。"""
    _ind = _fake_indicators()
    _prov: dict = {}
    _score = _real_composite_score(_ind, provenance_out=_prov)
    _sup = _prov.get("support")
    assert _sup is not None and _sup.sufficient, "前提：資料夠時撐得住"
    from ui.helpers.macro.helpers import composite_verdict
    _icon, _level, _, _action = composite_verdict(_score)
    assert tab1_macro._composite_verdict_cells(_score, _sup) == (
        _icon, _level, _action, "")


def test_a_pessimistic_composite_verdict_is_never_greyed_out():
    """規則 3 在②依據上的落地：悲觀／極度悲觀是**警訊**，不得被缺資料灰掉。

    突變驗證：把 `COMPOSITE_ALARM_LEVELS` 清空 → 本條轉紅。
    """
    from services.macro.composite_score import COMPOSITE_ALARM_LEVELS
    from ui.helpers.macro.helpers import composite_verdict
    # 28 項只取到 3 項（分母極小）但三項全是深度負向 → 結論是「警訊」
    # ⚠️ 這組數字是**實測挑出來的**，不是猜的：`PMI` 一項（-4.0）只到「中性」，
    # 測不到本條要測的東西。挑一組真的落在警訊區間的，否則本條會 skip 成擺設。
    _ind = {**_TOTAL_OUTAGE_IND,
            "PMI": {"value": 38.0, "weight": 2, "score": -2},
            "VIX": {"value": 45.0, "weight": 1, "score": -2},
            "HY_SPREAD": {"value": 9.0, "weight": 2, "score": -2}}
    _prov: dict = {}
    _score = _real_composite_score(_ind, provenance_out=_prov)
    _level = composite_verdict(_score)[1]
    assert _level in COMPOSITE_ALARM_LEVELS, (
        f"前提不成立：這組輸入落在「{_level}」，測不到規則 3（請換一組，不要 skip）")
    assert _prov["support"].sufficient, "警訊被缺資料閘門吃掉了（規則 3 反了）"
    assert tab1_macro._composite_verdict_cells(_score, _prov["support"])[1] == _level
    # 反向對照：同樣的分母、但分數落在「中性」→ 就該被灰掉（證明不是全部放行）
    _mild = {**_TOTAL_OUTAGE_IND, "PMI": {"value": 38.0, "weight": 2, "score": -2}}
    _prov2: dict = {}
    _s2 = _real_composite_score(_mild, provenance_out=_prov2)
    assert composite_verdict(_s2)[1] not in COMPOSITE_ALARM_LEVELS
    assert not _prov2["support"].sufficient, "非警訊的結論也被放行了（規則 3 過寬）"


#: 讀 `support` 的消費端檔案 —— 守衛掃這些檔，**新增消費端請一併加進來**。
#: ⚠️ 2026-09-04 第五輪稽核：a88f896 的守衛只掃 `ui/tab1_macro.py` 一個檔，
#: 而 `ui/helpers/macro/beginner_view.py` 也有一個消費端在自己讀 `.sufficient`
#: （而且刻意在 `support is None` 上與 SSOT 走相反的分支）—— 整個在射程外。
_SUPPORT_CONSUMER_FILES = ("ui/tab1_macro.py", "ui/helpers/macro/beginner_view.py")


def test_no_consumer_rewrites_the_sufficiency_gate_by_hand():
    """**每一個**消費端都必須走 L0 的 `is_sufficient()`，不得各抄一份。

    R4 前三輪的實證：每一份手刻的閘門都錯了或不完整。收成一個函式之後，
    「有沒有人自己重寫」才變成一條機器規則。
    ⚠️ 第五輪：SSOT 從 `ui/tab1_macro.py` 搬到 `shared/evidence_support.py`（L0），
    守衛也從「掃一個檔」擴成「掃全部消費端」——**判斷式住在 L0，守衛才掃得到
    別的層的消費端**。
    突變驗證：把任一處改回 `bool(_x is not None and _x.sufficient)` → 本條轉紅。
    """
    _bad = []
    for _f in _SUPPORT_CONSUMER_FILES:
        _tree = ast.parse(pathlib.Path(_f).read_text(encoding="utf-8"))
        _bad += [f"{_f}:{_n.lineno}" for _n in ast.walk(_tree)
                 if isinstance(_n, ast.Attribute) and _n.attr == "sufficient"]
    assert not _bad, (
        "有消費端自己讀 `.sufficient` 重寫閘門"
        f"（SSOT 是 `shared.evidence_support.is_sufficient`）：{_bad}")


def test_the_sufficiency_gate_ssot_lives_in_l0_and_there_is_only_one():
    """SSOT 只有一份，而且住在 L0（否則守衛必然掃不到某一層的消費端）。"""
    import shared.evidence_support as _es
    assert tab1_macro._support_is_sufficient is _es.is_sufficient, (
        "`ui/tab1_macro` 又長出第二份判斷式")
    from ui.helpers.macro import beginner_view as _bv
    assert _bv._is_sufficient is _es.is_sufficient, (
        "`beginner_view` 又長出第二份判斷式")
    # `support is None` → 不足（沒有支撐可讀就不下定論，§1）
    assert _es.is_sufficient(None) is False


def test_the_long_bucket_greys_out_when_the_phase_cannot_stand():
    """②依據的 🌳 長期列與卡 1 是**同一顆分數** —— 同一個閘門。

    完全斷線時 `score` 恆為 5.0（分母為零時的預設值）→ 舊版落在 `yellow`
    「轉折中」，而那是缺資料造出來的。
    突變驗證：把 `_long_sup ... not sufficient` 那一段刪掉 → 本條轉紅。
    """
    from ui.helpers.macro.beginner_view import compute_five_bucket_summary
    _phase = _real_calc_macro_phase(_TOTAL_OUTAGE_IND)
    assert _phase["score"] == 5, "前提：生產端仍然吐 5.0（本輪未動它）"
    _long = compute_five_bucket_summary(_TOTAL_OUTAGE_IND, _phase)["long"]
    assert _long["level"] == "gray" and _long["headline"] == "—", _long
    # 反向：資料夠時照樣出等級
    _ok = compute_five_bucket_summary(
        _fake_indicators(), _real_calc_macro_phase(_fake_indicators()))["long"]
    assert _ok["level"] != "gray", _ok


# ════════════════════════════════════════════════════════════════════════
# 2026-09-04 **第五輪**獨立稽核 F2（🔴）：不對稱在①結論上被反過來用了
#
# `macro_action_light` 的 🔴 有**兩個**來源：override，以及**位階分數偏弱**。
# 舊版把「四項均未觸發」的 `all_of` 和位階的 support `combine` 成一份，
# 於是那四項缺任何一項 → 整份 support 不足 → `_conclusion_line_state` 灰掉，
# **連同產出端已經認證過的那半邊（位階偏弱 ⇒ 減碼）一起灰掉**。
#
# 實測（`a88f896`，27/28 全空頭、只缺 VIX）：
#     phase 0 衰退 | phase support sufficient: True   ← 產出端認證了空頭判讀
#     action support sufficient=False（缺 VIX，未檢查）
#     RENDERED ⬜ **這次的資料撐不起任何結論**
# 而它替換上去的灰字寫著「半套證據可以升警，不可以解除警報」——
# **它自己正在做相反的事。** 且這是**對 `2a7fad1` 的回歸**：那時候同一個狀態印 🔴。
#
# ⚠️ 兩個方向都要釘：**認證過的警報要活下來，沒認證的「解除警報」不准活**。
#    第五輪稽核實測：在 `a88f896` 上插入一個 override-first 分支後，
#    整份測試套件照樣 `324 passed` —— 也就是**兩個方向當時都沒有守衛**。
# ════════════════════════════════════════════════════════════════════════
#: override 那四項的「沒有越線」讀數 —— 讓燈號完全由位階分數決定。
_CALM_OVERRIDE_VALUES = {"YIELD_10Y2Y": 0.5, "YIELD_10Y3M": 0.5,
                         "SAHM": 0.0, "VIX": 15.0}


def _bearish_ind(missing=()) -> dict:
    """28 項全空頭（每一項 score = −weight），扣掉 `missing` 那幾項。"""
    from services.macro.evidence import MACRO_INDICATOR_SCORING_WEIGHTS as _W
    return {_k: dict(value=_CALM_OVERRIDE_VALUES.get(_k, 1.0),
                     weight=_W[_k], score=-_W[_k])
            for _k in _W if _k not in set(missing)}


def test_a_phase_derived_red_survives_when_one_override_input_is_missing():
    """**F2 的具名實例**：27/28 全空頭、只缺 VIX → 必須印 🔴，不得灰掉。"""
    _ind = _bearish_ind(missing=("VIX",))
    _phase = _real_calc_macro_phase(_ind)
    assert (_phase["score"], _phase["phase"]) == (0, "衰退"), _phase["score"]
    assert _phase["support"].sufficient, "前提：產出端認證了這個空頭判讀"

    _al = _real_action_light(_ind, _phase["score"])
    assert _al["light"] == "🔴" and not _al["override"], (
        "前提：這是**位階造成的**紅燈，不是 override 紅燈")
    _light, _lines = tab1_macro._conclusion_line_state(_al)
    assert _light == "🔴", (
        f"產出端認證過的警報被灰掉了（不對稱反了）：{_light!r}")
    _txt = "\n".join(_lines)
    assert _al["action"] in _txt, "警報活下來了，但沒印減碼建議"
    # 「均未觸發」那一句沒有支撐 —— **只扣掉那一句**，不是連警報一起扣掉（卡 5 的形狀）
    assert "均未觸發" not in _txt, "留下了那句沒有支撐的全稱話"
    assert "缺 VIX" in _txt, f"沒有告訴使用者少檢查了哪一項：{_txt!r}"


def test_an_all_clear_without_every_named_input_does_not_survive():
    """反方向：🟢/🟡 是**解除警報**，四項缺一項就不准出燈（否則就是放寬）。"""
    from services.macro.evidence import MACRO_INDICATOR_SCORING_WEIGHTS as _W
    _ind = {_k: dict(value=_CALM_OVERRIDE_VALUES.get(_k, 1.0),
                     weight=_W[_k], score=+_W[_k])
            for _k in _W if _k != "VIX"}          # 全多頭、缺 VIX
    _al = _real_action_light(_ind, _real_calc_macro_phase(_ind)["score"])
    assert _al["light"] in ("🟢", "🟡") and not _al["override"], _al["light"]
    assert not _al["support"].sufficient, "缺一項點名輸入，卻宣告解除警報成立"
    _light, _lines = tab1_macro._conclusion_line_state(_al)
    assert _light == "⬜", f"沒認證的「解除警報」照樣出了燈：{_light!r}"
    assert "均未觸發" not in "\n".join(_lines)


def test_the_conclusion_line_asymmetry_holds_by_enumeration():
    """**列舉**，不是抽查 —— 第三輪就是用列舉驗乾淨的，遷移時掉了。

    兩個方向各自列舉一片狀態空間：
      (A) 位階造成的 🔴 且產出端認證了那顆分數 → **一個都不准**被灰掉
      (B) 🟢/🟡 但 support 撐不住                → **一個都不准**出燈
    實測（`a88f896`）：(A) 461 / 1382 = 33.4% 被灰掉；(B) 0。修復後兩者皆 0。
    """
    import itertools
    import random
    from services.macro.evidence import MACRO_INDICATOR_SCORING_WEIGHTS as _W
    _rng = random.Random(20260904)
    _special = {"SAHM": (-1.5, 0.0, 1.5), "SLOOS": (-1.5, 0.0, 1.5)}
    _keys = list(_W)
    _swallowed, _leaked, _n_alarm, _n_clear = [], [], 0, 0
    _subsets = [s for r in (0, 1, 2) for s in itertools.combinations(_keys, r)]
    for _miss in [s for s in _subsets for _ in range(3)]:
        _scores = {_k: _rng.choice(_special.get(_k, (-_W[_k], 0.0, _W[_k])))
                   for _k in _keys if _k not in _miss}
        _ind = {_k: dict(value=_CALM_OVERRIDE_VALUES.get(_k, 1.0),
                         weight=_W[_k], score=_s) for _k, _s in _scores.items()}
        _phase = _real_calc_macro_phase(_ind)
        _al = _real_action_light(_ind, _phase["score"])
        if _al["override"]:
            continue                     # override 紅燈由規則 3 涵蓋，另有測試
        _light, _ = tab1_macro._conclusion_line_state(_al)
        if _al["light"] == "🔴" and _phase["support"].sufficient:
            _n_alarm += 1
            if _light != "🔴":
                _swallowed.append((list(_miss), _phase["score"], _light))
        if _al["light"] in ("🟢", "🟡") and not _al["support"].sufficient:
            _n_clear += 1
            if _light != "⬜":
                _leaked.append((list(_miss), _al["light"]))
    assert _n_alarm > 100 and _n_clear > 100, (
        f"前提：兩個方向都要有夠多樣本（警報 {_n_alarm} / 解除 {_n_clear}）")
    assert not _swallowed, (
        f"{len(_swallowed)} / {_n_alarm} 個認證過的警報被灰掉：{_swallowed[:3]}")
    assert not _leaked, (
        f"{len(_leaked)} / {_n_clear} 個沒認證的解除警報照樣出燈：{_leaked[:3]}")


def test_the_producer_withholds_the_all_clear_sentence_instead_of_the_whole_verdict():
    """那句「均未觸發」由**產出端**扣掉 —— 消費端不必（也不得）自己挑句子。"""
    _ind = _bearish_ind(missing=("VIX",))
    _al = _real_action_light(_ind, _real_calc_macro_phase(_ind)["score"])
    assert not _al["all_clear_support"].sufficient
    _joined = "；".join(_al["reasons"])
    assert "均未觸發" not in _joined, "產出端還在吐那句沒有支撐的全稱話"
    assert _al["all_clear_support"].reason in _joined, (
        f"扣掉了，但沒說為什麼扣：{_joined!r}")
    # 四項齊全時照印原句（沒有把好的那一支一起改掉）
    _full = _real_action_light(_bearish_ind(), _real_calc_macro_phase(_bearish_ind())["score"])
    if not _full["override"]:
        assert "均未觸發" in "；".join(_full["reasons"])


#: 買賣燈三段切點的**獨立**字面值 —— 出處是 `services/macro/action_light.py`
#: 的模組 docstring（「≥ 6.5 → 🟢 可加碼；4.0~6.5 → 🟡 持有；< 4.0 → 🔴 減碼」，
#: user 2026-07-05 批准的草案）。**刻意不 import `_BUY_SCORE_10` / `_HOLD_SCORE_10`**：
#: 漂移鎖的兩邊必須是兩個真相源，否則它鎖不住任何東西（見下方測試的更正註）。
#: 要改切點 ⇒ 常數、docstring、本 tuple 三者一起改，改一個就轉紅。
_DECLARED_LIGHT_CUTS: tuple[float, float] = (4.0, 6.5)


def test_the_action_light_band_matches_its_own_if_chain():
    """漂移鎖：`action_light_band()` ≡ **獨立宣告的**三段切點 ≡ 產出端實際發的燈。

    ⚠️ **2026-09-04 第六輪稽核 F-A4：本條原本是套套邏輯，已就地改寫**
    （有意識的更正，不是漏刪）。舊版寫
        ~~`assert _al["light"] == action_light_band(_s)`~~
    而 `macro_action_light` 產生 `_al["light"]` 的方式**就是呼叫 `action_light_band`**
    —— 迴圈在拿函式跟它自己比。舊版最後那句 `ACTION_LIGHT_NARROWEST_BAND == min(...)`
    同樣是把生產端的推導式在測試裡**再算一次**，兩邊永遠相等。
    舊 docstring 宣稱「把 `_BUY_SCORE_10` 改成別的數 → 轉紅」，**實測不會**
    （稽核 M13：四個批次測試檔 372 passed 全綠）。
    ⚠️ 那個常數**本來就有**守衛（`tests/test_macro_action_light.py` 用 7.2 / 5.0 / 2.0
    三個獨立字面值釘住三段），所以本條的問題是**假守衛**，不是漏了守衛。

    現行：兩邊各自獨立 ——
      · `_DECLARED_LIGHT_CUTS` 是從模組 docstring / 客戶拍板草案抄下來的字面值；
      · `action_light_band` 與 `macro_action_light` 是實作。
    突變驗證：把 `_BUY_SCORE_10` 或 `_HOLD_SCORE_10` 改成別的數 → 本條轉紅。
    """
    from services.macro.action_light import (
        ACTION_LIGHT_BAND_EDGES, ACTION_LIGHT_NARROWEST_BAND, action_light_band,
    )
    from services.macro.evidence import MACRO_INDICATOR_SCORING_WEIGHTS as _W
    _hold, _buy = _DECLARED_LIGHT_CUTS

    def _declared(_s: float) -> str:
        """獨立參考實作 —— 只吃 `_DECLARED_LIGHT_CUTS`，不碰生產端常數。"""
        return "🟢" if _s >= _buy else ("🟡" if _s >= _hold else "🔴")

    assert tuple(ACTION_LIGHT_BAND_EDGES) == _DECLARED_LIGHT_CUTS, (
        f"生產端切點 {tuple(ACTION_LIGHT_BAND_EDGES)} 與宣告的 "
        f"{_DECLARED_LIGHT_CUTS} 分岔 —— 若這是有意的改動，"
        f"請同步改 `action_light.py` 的模組 docstring 與本測試的 tuple")
    # 邊界本身（含切點上那一格）逐點釘死，不只掃 0.1 格
    for _s in (0.0, 3.9, 3.99, _hold, 4.01, 5.0, 6.49, _buy, 6.51, 10.0):
        assert action_light_band(_s) == _declared(_s), (
            f"score={_s}: 帶函式給 {action_light_band(_s)}，"
            f"宣告的切點給 {_declared(_s)}")
    for _i in range(0, 101):
        _s = _i / 10.0
        # 走真的 `macro_action_light`（override 四項全部遠離門檻 → 燈完全由位階決定）
        _al = _real_action_light({"PMI": {"value": 1.0, "weight": _W["PMI"],
                                          "score": 0.0}}, _s)
        assert _al["light"] == _declared(_s), (
            f"score={_s}: if-chain 給 {_al['light']}，宣告的切點給 {_declared(_s)}")
    assert ACTION_LIGHT_NARROWEST_BAND == min(
        _hold, _buy - _hold, 10.0 - _buy), (
        f"最窄帶 {ACTION_LIGHT_NARROWEST_BAND} 與宣告切點導出的不符")


# ════════════════════════════════════════════════════════════════════════
# 第五輪 F8（🟠）：②依據表其餘三列仍然在「一項就宣告全部沒事」
#
# 實測（`a88f896`，只取到 PMI 一項）：
#   -- long -> {"level":"gray","label":"資料不足"}                      ← 已遷移
#   -- mid  -> {"level":"green","label":"循環健康",
#               "headline":"PMI 皆未越線；CPI／失業 未取得"}
# **文字誠實、燈號說謊**，而使用者先看到的是燈號與顏色。
# 「都沒越線」是點名了輸入的全稱宣稱 ⇒ 依本批自己的 `all_of` 規則，缺一項就不能講。
# ⚠️ 紅 / 黃（有東西越線）是**存在性**宣稱，照舊由半套證據就能升警 —— 一項都沒改。
# ════════════════════════════════════════════════════════════════════════
def test_the_evidence_rows_need_every_named_input_before_going_green():
    """📈中期 / 🎯短線 / ⚠️拐點：缺任何一顆點名輸入 → 不得出綠燈。"""
    from ui.helpers.macro.beginner_view import compute_four_horizon_summary
    _one = compute_four_horizon_summary({"PMI": {"value": 55.0}})
    assert _one["mid"]["level"] == "gray", (
        f"三顆只取到一顆，卻宣告「循環健康」：{_one['mid']}")
    assert _one["mid"]["label"] == "資料不足"
    # headline 本來就誠實（它點名了缺哪幾顆）—— 燈號現在跟它同一個口徑
    assert "未取得" in _one["mid"]["headline"]

    # 兩顆裡只有一顆的短線桶、五顆裡只有一顆的拐點桶，同樣不得出綠燈
    _short = compute_four_horizon_summary({"VIX": {"value": 15.0}})
    assert _short["short"]["level"] == "gray", _short["short"]
    _inf = compute_four_horizon_summary({"SAHM": {"value": 0.1}})
    assert _inf["inflection"]["level"] == "gray", _inf["inflection"]


def test_the_evidence_rows_still_go_green_when_every_named_input_is_there():
    """反向：點名輸入**全在**且都沒越線 → 照樣出綠燈（沒有把桶灰死）。"""
    from ui.helpers.macro.beginner_view import compute_four_horizon_summary
    _all = compute_four_horizon_summary({
        "PMI": {"value": 55.0}, "CPI": {"value": 2.0},
        "UNEMPLOYMENT": {"value": 3.8},
        "VIX": {"value": 14.0}, "HY_SPREAD": {"value": 3.0},
        "SAHM": {"value": 0.1}, "YIELD_10Y2Y": {"value": 0.5},
        "YIELD_10Y3M": {"value": 0.5}, "LEI": {"value": 0.1, "ma3": 0.1},
        "SLOOS": {"value": 10.0},
    })
    assert _all["mid"]["level"] == "green", _all["mid"]
    assert _all["short"]["level"] == "green", _all["short"]
    assert _all["inflection"]["level"] == "green", _all["inflection"]


def test_an_alarm_in_those_rows_still_fires_on_partial_evidence():
    """規則 3 在這三列上**沒有**被本輪的收緊碰到：半套證據照樣升警。"""
    from ui.helpers.macro.beginner_view import compute_four_horizon_summary
    # 只取到 PMI 一顆，而且它收縮 → 仍須亮黃（不是灰）
    _mid = compute_four_horizon_summary({"PMI": {"value": 45.0}})["mid"]
    assert _mid["level"] == "yellow", f"半套證據的警訊被灰掉了：{_mid}"
    # 只取到 VIX 一顆，而且是恐慌值 → 仍須亮紅
    _short = compute_four_horizon_summary({"VIX": {"value": 45.0}})["short"]
    assert _short["level"] == "red", f"半套證據的警訊被灰掉了：{_short}"


def test_the_alarm_carve_out_does_not_leak_into_the_extreme_risk_card():
    """**F2 的連帶**：①結論留下警報，**卡 5 仍然不准說「四項都沒觸發」**。

    兩個消費端問的不是同一句話：
      · ①結論   問「我正在印的這盞燈撐不撐得住」→ 位階偏弱的 🔴 是警報，撐得住
      · 卡 5    問「**四項都檢查過、都沒觸發**」→ 缺 VIX 就不能講
    本輪實作 F2 時**一度讓卡 5 讀了同一份 support**，實測重現第三輪 A1 那個缺陷：
        [⚠️ 極端風險警語] '🟢 未觸發' / '0 項觸發'
        note：「景氣位階 0.0/10；⬜ …（缺 VIX，未檢查）」
    —— VIX 根本沒抓到，卡片卻宣告四項都沒事。故產出端回報**兩份** support。
    突變驗證：把卡 5 的 `_al5.get("no_trigger_support")` 改回 `_al5.get("support")`
    → 本條轉紅（而①結論那幾條仍綠，證明兩者真的是兩個問題）。
    """
    _ind = _bearish_ind(missing=("VIX",))
    _phase = _real_calc_macro_phase(_ind)
    _al = _real_action_light(_ind, _phase["score"])
    assert _al["light"] == "🔴" and not _al["override"], "前提：位階造成的紅燈"
    assert _al["support"].sufficient, "前提：那盞燈本身撐得住（警報豁免）"
    assert not _al["no_trigger_support"].sufficient, (
        "「四項都沒觸發」在缺 VIX 時竟然撐得住")

    _c5 = _grid_via_real_producer(_ind)["⚠️ 極端風險警語"]
    assert _c5["signal"] in _GREY_SIGNALS, (
        f"缺 VIX 卻宣告四項都檢查過：{_c5['signal']!r} / {_c5['value_str']!r}")
    assert "缺 VIX" in _c5["note"], _c5["note"]
    # 同一個狀態下，①結論的警報**仍然活著**（兩件事互不吃掉）
    assert tab1_macro._conclusion_line_state(_al)[0] == "🔴"


# ════════════════════════════════════════════════════════════════════════
# 2026-09-04 **第六輪**稽核 F-A3（🟠）：這一批的招牌新機制**零行為守衛**
#
# 把 `action_light_support` 的 `combine(...)` 裡的 `_light_band` 整條刪掉 ——
# 也就是**移除本批新增的買賣燈帶條件** —— 四個批次測試檔 372 passed、
# fast lane 6975 passed，與乾淨版**逐字相同**。而那個突變在行為上是活的。
#
# 前五輪每一個缺陷都是在**這個條件**下走到稽核手上的：一個活的機制，
# 整套測試感覺不到它。故補一條真的會被它翻掉的行為守衛。
#
# ⚠️ 判別狀態要挑對：`_light_band`（切點 4.0 / 6.5）與 `phase_support`
#    （相位帶 3 / 5 / 8）**只有在一個帶內、另一個帶外**時才分得出來。
#    `_HOLD_SCORE_10 = 4.0` 落在相位帶「復甦」(3~5) 的**內部**，
#    所以「可及區間 3.9～4.4」正好：相位帶全在「復甦」，燈卻從 🔴 橫跨到 🟡。
# ⚠️ 第五輪 F1 的例子（顯示 6.4）在第六輪 F-A1 修好之後**不再是判別狀態**
#    （28 顆全到齊時可及顯示值恆為 `{6.4}`，兩條帶都不變）—— 本檔改用下面
#    這個「缺一顆 LEI」的狀態，它在 F-A1 修好之後依然活著。
# ════════════════════════════════════════════════════════════════════════
#: 缺 `LEI` 一項、其餘 27 項如下 → 顯示 `4.1 復甦`、燈 🟡。
#: 可及區間 3.9～4.4：**相位帶不變**（全在「復甦」）、**買賣燈帶會翻**（🔴↔🟡）。
_LIGHT_BAND_ONLY_SCORES: dict = {
    "PMI": -2.0, "NFP": -1.0, "PERMIT_HOUSING": -0.5, "NEW_HOME": -0.5,
    "CONSUMER_CONF": -0.5, "CPI": -0.36,
}


def _light_band_only_ind() -> dict:
    from services.macro.evidence import MACRO_INDICATOR_SCORING_WEIGHTS as _W
    return {_k: dict(value=_CALM_OVERRIDE_VALUES.get(_k, 1.0), weight=_W[_k],
                     score=_LIGHT_BAND_ONLY_SCORES.get(_k, 0.0))
            for _k in _W if _k != "LEI"}


def test_the_action_light_band_condition_is_the_only_thing_holding_this_state():
    """**F-A3**：買賣燈帶那條新條件被刪掉 → 本條轉紅。

    這個狀態裡另外兩半**都成立**（四項點名輸入全在、相位帶不變），
    唯一擋住它的就是買賣燈自己的帶。所以它是那條件的**充分必要**見證：
      · 條件在 → ①結論 ⬜、卡 5 讀的 `no_trigger_support` 不足；
      · 條件刪掉 → 兩者都變成「撐得住」，畫面照出 🟡 持有。
    突變驗證：`services/macro/evidence.py::action_light_support` 的
    `combine(...)` 拿掉 `_light_band` → 本條轉紅。
    """
    from services.macro.action_light import (
        ACTION_LIGHT_NARROWEST_BAND, action_light_band,
    )
    from services.macro.evidence import (
        action_light_score_support, phase_support as _phase_support,
    )
    _ind = _light_band_only_ind()
    _phase = _real_calc_macro_phase(_ind)
    assert (_phase["score"], _phase["phase"]) == (4.1, "復甦"), (
        f"前提不成立（換一組，不要 skip）：{_phase['score']} {_phase['phase']}")

    _al = _real_action_light(_ind, _phase["score"])
    assert _al["light"] == "🟡" and not _al["override"], (
        f"前提：這要是一盞由位階決定的 🟡（實得 {_al['light']}，"
        f"override={_al['override']}）")
    # ── 另外兩半都成立，所以擋住它的只可能是買賣燈帶那一條 ──
    assert _al["all_clear_support"].sufficient, "前提：四項點名輸入全在"
    assert _phase_support(_ind, _phase["score"]).sufficient, (
        "前提：相位帶（3/5/8）在這個狀態下不變 —— 它擋不住這一格")
    _lb = action_light_score_support(
        _ind, _phase["score"], band_of=action_light_band,
        narrowest_band=ACTION_LIGHT_NARROWEST_BAND)
    assert not _lb.sufficient, (
        f"前提：買賣燈帶（4.0/6.5）在這個狀態下會翻 —— 實得 {_lb.detail}")

    # ── 真正的斷言：兩個消費端都必須因此收手 ──
    assert not _al["support"].sufficient, (
        "缺一顆 LEI 就能把這盞燈從 🟡 打成 🔴（可及 "
        f"{_lb.detail['reachable_low']}～{_lb.detail['reachable_high']}），"
        "①結論卻宣告證據充足 —— 買賣燈帶那條件沒有接上")
    assert not _al["no_trigger_support"].sufficient, (
        "卡 5 讀的那份 support 也必須收手（同一個帶）")
    _light, _lines = tab1_macro._conclusion_line_state(_al)
    assert _light == "⬜", (
        f"①結論照樣出了 {_light}，而那盞燈缺一顆指標就會翻色")
    # ⚠️ 不能用「文字裡有沒有 🟡」判斷：灰態的理由句**本來就會**寫
    # 「橫跨「🔴」到「🟡」」—— 那是在解釋為什麼撐不住，不是在下判讀。
    # 要驗的是**沒有把那盞燈當成結論端出去**：不給行動建議。
    _txt = "\n".join(_lines)
    assert _al["action"] not in _txt, f"灰態卻照樣印了加減碼建議：{_txt!r}"
    assert "撐不起任何結論" in _txt, _txt


# ════════════════════════════════════════════════════════════════════════
# 2026-09-04 **第六輪**稽核 F-A2（🟠）：政策豁免的 🔴 印了一句沒有支撐的分數
#
# 實測（`fb770b4`，只取到 PMI = −2.0 一項）：
#     displayed score 0 衰退 | phase support sufficient: False
#     ①結論: 🔴 減碼 —— 景氣位階偏弱,拉高現金水位
#            - 景氣位階 0.0/10                 ← 沒有支撐，照印
#            - ⬜ 這句話點名了 4 項輸入，實際只取到 0 項（缺 …）
#     卡 1  : ⬜ 資料不足                       ← 同一顆分數，就在正下方拒絕印
# **同一個畫面上兩個標準。**
# 🔴 本身是對的（政策豁免，第五輪 F2 明白要求留下警報）——
# 要扣掉的只有引用了那顆分數的**那一句**，正是本批自己寫的原則。
# ════════════════════════════════════════════════════════════════════════
def test_a_carved_out_red_does_not_print_a_phase_score_it_cannot_support():
    """**F-A2**：警報留著，但沒有支撐的「景氣位階 N/10」不准印。

    突變驗證：把 `macro_action_light` 的 `_reasons[0]` 改回無條件
    `f"景氣位階 {phase_score_10:.1f}/10"` → 本條轉紅。
    """
    from services.macro.evidence import (
        MACRO_INDICATOR_SCORING_WEIGHTS as _W, phase_support as _phase_support,
    )
    _ind = {"PMI": dict(value=1.0, weight=_W["PMI"], score=-2.0)}
    _phase = _real_calc_macro_phase(_ind)
    assert (_phase["score"], _phase["phase"]) == (0, "衰退"), _phase["score"]
    _sup = _phase_support(_ind, _phase["score"])
    assert not _sup.sufficient, "前提：這顆分數撐不住（28 取 1）"

    _al = _real_action_light(_ind, _phase["score"])
    assert _al["light"] == "🔴" and not _al["override"], (
        f"前提：位階偏弱造成的 🔴（實得 {_al['light']}）")
    # (1) 警報要活下來 —— 第五輪 F2 的方向不得被本修正逆轉
    _light, _lines = tab1_macro._conclusion_line_state(_al)
    assert _light == "🔴", f"把警報一起扣掉了（F2 回歸）：{_light!r}"
    _txt = "\n".join(_lines)
    assert _al["action"] in _txt, "警報活下來了，但沒印減碼建議"
    # (2) 那一句沒有支撐的分數不准印
    assert "景氣位階 0.0/10" not in _txt, (
        f"印了一個卡 1 就在正下方拒絕印的分數：{_txt!r}")
    assert not any(_r.startswith("景氣位階 ") and "/10" in _r
                   for _r in _al["reasons"]), _al["reasons"]
    # (3) 要說得出為什麼扣掉，而且用的是**產出端同一份 reason**（不得自己編一句）
    assert _sup.reason in _txt, f"扣掉了，但沒說為什麼：{_txt!r}"


def test_a_supported_phase_score_is_still_printed():
    """反方向：撐得住的時候照印 —— 本修正不得把好的那一支一起關掉。"""
    _ind = _bearish_ind()                      # 28 項全在、全空頭
    _phase = _real_calc_macro_phase(_ind)
    from services.macro.evidence import phase_support as _phase_support
    assert _phase_support(_ind, _phase["score"]).sufficient, "前提：28 項全在"
    _al = _real_action_light(_ind, _phase["score"])
    assert _al["light"] == "🔴" and not _al["override"], _al["light"]
    assert any(_r == f"景氣位階 {_phase['score']:.1f}/10" for _r in _al["reasons"]), (
        f"撐得住卻不印分數了：{_al['reasons']}")


# ════════════════════════════════════════════════════════════════════════
# 2026-09-04 **第六輪**稽核 F-A5（🟠）：F8 的「三列一起遷移，不留第二個標準」
#                                        漏掉了②依據表的第 4 列（📰 新聞）
#
# 實測（`fb770b4`，RSS 全斷）：`fetch_market_news` 回的**不是空 list**，
# 是一則 `source="system"` 的佔位訊息，而新聞桶把它當成一則新聞數進去：
#     news bucket -> {'level':'green','label':'無系統風險',
#                     'headline':'1 則新聞掃描,無系統性風險'}
#     ②依據 news row -> ['📰 新聞', '🟢 無系統風險', '1 則新聞掃描,無系統性風險']
# **零觀測換來一盞綠燈，外加一個捏造的則數。**
#
# 機制早於本批，但「不留第二個標準」是本批的宣稱，而這是那張表上唯一沒遷移的一列。
# **處置：遷移**（不是修正宣稱）—— 同一張表、同一條 `all_of` 規則、同一份客戶授權，
# 而且它正是本批存在的理由那一類（從零觀測宣告安全）。
# ════════════════════════════════════════════════════════════════════════
#: `fetch_market_news` 全斷時回的那一則佔位訊息（逐字對齊 L1 的字面值）。
_NEWS_OUTAGE_PLACEHOLDER: list = [{
    "title": "⚠️ 暫時無法取得財經新聞",
    "summary": "已嘗試 5 個來源、5 個無回應（可能 NAS Proxy 斷線或來源暫時不可用），稍後重試。",
    "source": "system", "published": "", "url": "", "is_systemic": False,
}]


def test_the_news_row_does_not_go_green_on_zero_observations():
    """**F-A5**：RSS 全斷 → 不得出綠燈，也不得報「1 則新聞掃描」。

    突變驗證：把 `compute_five_bucket_summary` 的 `_real_items` 過濾條件
    改成恆真（`n.get("source") != "__never__"`）→ 本條轉紅。
    """
    from ui.helpers.macro.beginner_view import compute_five_bucket_summary
    _n = compute_five_bucket_summary({}, None, news_items=_NEWS_OUTAGE_PLACEHOLDER)["news"]
    assert _n["level"] == "gray", f"零觀測卻出了 {_n['level']} 燈：{_n}"
    assert "無系統風險" not in _n["label"], _n
    assert "1 則" not in _n["headline"], f"捏造了則數：{_n['headline']!r}"
    # 使用者要看得到**為什麼**沒得掃（用 L1 佔位訊息自己寫的理由，不自己編）
    assert "暫時無法取得財經新聞" in _n["headline"], _n["headline"]


def test_the_news_row_is_also_grey_on_an_empty_list():
    """同一個形狀的另一半：`news_items=[]`（0 則）舊版也是綠燈。"""
    from ui.helpers.macro.beginner_view import compute_five_bucket_summary
    _n = compute_five_bucket_summary({}, None, news_items=[])["news"]
    assert _n["level"] == "gray", f"0 則觀測卻出了 {_n['level']} 燈：{_n}"


def test_the_news_row_still_goes_green_and_still_raises_alarms_on_real_items():
    """反方向 ×2：真的有新聞時綠燈照出；存在性警報一個字都沒改。"""
    from ui.helpers.macro.beginner_view import compute_five_bucket_summary
    _real = [{"title": "Fed holds rates", "source": "MarketWatch", "is_systemic": False},
             {"title": "Yields drift", "source": "CNBC Economy", "is_systemic": False}]
    _g = compute_five_bucket_summary({}, None, news_items=_real)["news"]
    assert _g["level"] == "green" and "2 則新聞掃描" in _g["headline"], _g
    # 警報：半套證據照舊升警（規則 3），且**佔位訊息不會稀釋則數**
    _mixed = _NEWS_OUTAGE_PLACEHOLDER + [
        {"title": "bank run spreads", "source": "BBC World", "is_systemic": True}]
    _y = compute_five_bucket_summary({}, None, news_items=_mixed)["news"]
    assert _y["level"] == "yellow" and "1 則系統性風險新聞" in _y["headline"], _y
    _r = compute_five_bucket_summary({}, None, news_items=_NEWS_OUTAGE_PLACEHOLDER + [
        {"title": "bank run", "source": "BBC World", "is_systemic": True},
        {"title": "contagion", "source": "CNBC Finance", "is_systemic": True}])["news"]
    assert _r["level"] == "red", _r


def test_the_outage_placeholder_still_looks_like_this_upstream():
    """漂移鎖：L1 的佔位訊息**仍然**用 `source="system"` 標記自己。

    本列的遷移靠這個結構欄位判別（**刻意不解析標題的表情符號**）。
    L1 哪天改用別的標記，本條就要轉紅，而不是讓綠燈悄悄回來。
    """
    _src = pathlib.Path("repositories/news_repository.py").read_text(encoding="utf-8")
    _tree = ast.parse(_src)
    _fn = next(_n for _n in ast.walk(_tree)
               if isinstance(_n, ast.FunctionDef) and _n.name == "fetch_market_news")
    def _literal_pairs(_d: ast.Dict) -> dict:
        return {_k.value: _v.value
                for _k, _v in zip(_d.keys, _d.values)
                if isinstance(_k, ast.Constant) and isinstance(_v, ast.Constant)}

    # 佔位訊息 ＝ `is_systemic` 寫死成 `False` 的那幾個 dict；
    # 真的新聞那一個寫的是變數 `_is_sys`，所以不會被選中（**不是**靠 source 篩選，
    # 否則這條測試就變成套套邏輯 —— 只挑出符合的再宣稱它符合）。
    _placeholders = [_d for _d in ast.walk(_fn)
                     if isinstance(_d, ast.Dict)
                     and _literal_pairs(_d).get("is_systemic") is False]
    assert len(_placeholders) >= 2, (
        f"找不到 L1 的佔位訊息 dict（找到 {len(_placeholders)} 個）—— "
        f"結構變了，請重新確認本列的判別方式")
    for _d in _placeholders:
        _pairs = _literal_pairs(_d)
        assert _pairs.get("source") == "system", (
            f"佔位訊息不再用 source='system' 標記自己：{_pairs}")


def test_the_card_grid_holds_across_the_whole_score_range():
    """**B4**：整批 fixture 不得只落在**一個**合成分數上。

    `fb770b4` 的每一個「充足」fixture 都給出 6.5 —— 而 6.5 正好是
    「會被灰掉的 6.4」的上面一格，F-A1 那一整類因此完全躲在 fixture 後面。
    本條把整條 0~10 掃一遍：28 顆全在時，**每一格**都必須撐得住，
    而且卡 1 要照出位階、①結論不得退成 ⬜。
    突變驗證（**逐一實跑過**）：用 `fb770b4` 的 `shared/evidence_support.py` 跑
    → 本條轉紅。⚠️ **拿掉 F-A1 修法的任一半本條都不會轉紅**（兩半互相遮蔽）——
    逐半的守衛在 `tests/test_evidence_support.py` 的
    `test_nothing_missing_means_the_reachable_display_set_is_exactly_the_score`
    與 `test_the_reachable_upper_bound_is_half_open_not_closed`。
    """
    from services.macro.evidence import phase_support as _phase_support
    _seen_scores, _bad = set(), []
    for _t in [round(_i / 10.0, 1) for _i in range(0, 101)]:
        _ind = _fake_indicators(score_target=_t)
        _phase = _real_calc_macro_phase(_ind)
        _seen_scores.add(_phase["score"])
        if not _phase_support(_ind, _phase["score"]).sufficient:
            _bad.append((_t, _phase["score"], _phase["support"].reason))
            continue
        _al = _real_action_light(_ind, _phase["score"])
        _light, _ = tab1_macro._conclusion_line_state(_al)
        if _light == "⬜":
            _bad.append((_t, _phase["score"], "①結論退成 ⬜"))
    assert len(_seen_scores) >= 20, (
        f"fixture 只產得出 {len(_seen_scores)} 個不同分數 —— 掃不到什麼")
    assert not _bad, (
        f"28 顆全到齊卻有 {len(_bad)} 格撐不住（fixture 只驗一個魔術數字時看不到）："
        f"{_bad[:3]}")


def test_the_calm_fixture_no_longer_puts_the_same_score_on_every_indicator():
    """**B4 的結構面**：一個魔術數字不得再蓋住一整類。"""
    _ind = _fake_indicators()
    _scores = {round(float(_v["score"]), 6) for _v in _ind.values()}
    assert len(_scores) >= 3, f"28 顆只有 {len(_scores)} 種 score：{_scores}"
    # 但合成分數要與舊 fixture 一致（偏移和為 0）—— 既有斷言零變更
    assert _real_calc_macro_phase(_ind)["score"] == 6.5, (
        "偏移沒有互相抵銷，合成分數變了 —— 既有測試的前提會跟著飄")


# ══════════════════════════════════════════════════════════════════════════
# Lane E · 「去哪補」全域射程 —— 從 3 個字面值擴到全 `ui/**` 的 `where=`
# ══════════════════════════════════════════════════════════════════════════
# 為什麼要有這一段（讀之前先看，否則會以為只是把舊規則抄大一號）
# ------------------------------------------------------------------
# 本檔既有的 `test_every_remedy_names_a_control_that_actually_exists_on_screen`
# 只檢查 `ui/tab1_macro.py` 裡的**三個模組級常數**，對上一個 4 個常數的 SSOT 集合。
# 而全 `ui/**` 實測有 **47 個** `not_ready()` / `empty_state()` 呼叫點
# （量測日 2026-09-04：`not_ready` 44 + `empty_state` 3），**其餘 44 個一條規則都沒有**。
#
# 那 44 個裡實測有 3 個指名了畫面上不存在的東西、3 個連 `where=` 都沒有：
#
# | 位置 | 文案指名的 | 畫面上實際是什麼 |
# |---|---|---|
# | `ui/tab2_single_fund.py` 空狀態 | 「🔍 找代號」 | `st.button("🔍 搜尋基金代號")`；「🔍 找代號」只在 `safe_section` 的區塊名裡，**那個字只有在該區塊炸掉時才會被印出來** |
# | `ui/helpers/portfolio/policy_admin_section.py` | 「OAuth 設定」expander | 該檔**只有一個** expander（保單管理），OAuth 那塊是 `st.markdown("##### 🧙 OAuth Client 設定引導（5 分鐘完成）")` —— **型態與名字都不同** |
# | `ui/components/allocation_donut_card.py` | 「編輯初始持倉」 | 真正的收合區叫「✏️ 編輯持倉（手動微調 — 從 CHUBB 對帳單抄入精確值）」，**全 repo 沒有任何控制項叫「編輯初始持倉」** |
#
# ⚠️ **這三個都不是「SSOT 常數被抄成第二份」**，所以既有規則的做法（比對 4 個常數）
#    結構上抓不到它們 —— 它們指名的控制項**從來就沒有進過 SSOT**，而且也不該全部進去
#    （`shared/ui_control_labels.py` 自己寫著「本模組不是全站按鈕字典」）。
#    本段換一個方向：**不要求文案指名 SSOT 常數，而是要求它指名的東西
#    真的被某個 widget 渲染出來** —— 對照組直接從原始碼 AST 抽。
#
# ⚠️ **本段刻意不驗「那句話通不通順、使用者照做有沒有用」** —— 那是人要看的。
#    機器能守的只有「它指名的那個字串，畫面上找不找得到」。據實寫在這裡，
#    不要把它讀成「文案已經被驗過了」。

from shared.ui_control_labels import (  # noqa: E402
    DATA_GUARD_HOT_MONEY_BTN as _LBL_D5_HOT_MONEY_BTN,
    DATA_GUARD_RELOAD_MACRO_BTN as _LBL_D5_RELOAD_MACRO_BTN,
)

#: `where=` 裡「指名一個控制項」的寫法：用 `「」` 括起來。
#: 選 `「」` 而不是「整句比對」的理由：`where=` 是一整句話
#: （「本頁上方「基金代號」欄位（多貼幾檔後重按「🩺 開始健診」）」），
#: 整句永遠不會等於任何 widget label；真正需要對得上畫面的是**被括起來的那一段**。
import re  # noqa: E402

_WHERE_QUOTED = re.compile(r"「([^「」]+)」")

#: 被視為「畫面上的控制項」的 streamlit 呼叫。
#: 只收**真的會把 label 印在畫面上**的；`st.caption` / `st.info` / `st.write` /
#: 一般 `st.markdown` 散文**刻意不收** —— 收了就退化成「這幾個字有沒有出現在
#: 某段文字裡」，而那正是 `shared/ui_control_labels.py` docstring 點名的、
#: 在兩邊都改壞時照樣綠燈的那種斷言。
#: ⚠️ **這句理由 2026-09-04 就地更正（有意識的更正，不是漏刪 · 決策者：AI 總管 ·
#:    依據：獨立稽核指出後本組重跑）。** 原文寫
#:    ~~「（實測：把 `caption`/`info`/`write` 收進來，「編輯初始持倉」這個死指路
#:    會因為別處一句散文提到它而被判成合格。）」~~ —— **那句在現行版本下不可重現。**
#:    本組照做實測：對照組由 **716 → 3475**（加寬確實生效），但
#:    `編輯初始持倉` 的 **exact-equality = False、bracket-prefix = False、
#:    僅「包含」它的字串 6 個** → **在現行比對器下仍然轉紅**。
#:    **原因**：最終比對器只認「等於」與「止於括號的前綴」，**明文不認子字串**，
#:    所以散文只會「包含」、永遠不會「等於」—— 加寬 widget 集合改變不了這一點。
#:    **那句話描述的是本規則的【初版原型】**（當時用子字串比對），
#:    被寫成了現行版本的實測 —— 30 行後的另一句「曾……**在初版原型裡**被判成合格」
#:    才是對的。**同一個檔裡兩個互相矛盾的說法，而被當成事實的那個不成立。**
#: ✅ **設計決定本身沒有被推翻，不收散文仍然正確** —— 理由改為下面這一條
#:    （它不依賴那個不成立的實測，而且本身可重跑）：
#:    加寬會讓對照組從 **716 暴增到 3475**（含大量散文），
#:    於是「畫面上找不找得到」這個問題會退化成「這幾個字有沒有在某段文字裡出現過」。
#:    ⚠️ 稽核已用突變證明那個方向**真的能造出假綠**：加寬 `_SCREEN_WIDGETS`
#:    ＋ 把某個 `where=` 指向一段純散文 caption → **全綠**（見 `test_where_rules_are_not_scanning_air`
#:    的「本錨點守不到的方向」段）。
_SCREEN_WIDGETS = frozenset({
    "button", "checkbox", "expander", "form_submit_button", "radio", "selectbox",
    "toggle", "text_input", "file_uploader", "number_input", "date_input",
    "multiselect", "slider", "text_area", "link_button", "download_button",
    "metric", "applied_form", "tabs", "popover", "status", "segmented_control",
    "pills", "color_picker", "time_input", "camera_input", "chat_input",
})
#: 標題型呼叫（`st.markdown` 只在字串以 `#` 開頭時才算標題，見 `_screen_strings`）。
_SCREEN_HEADINGS = frozenset({"subheader", "header", "title"})
#: 哪些參數位置會成為畫面上的字：第一個位置引數，或這幾個具名參數。
_SCREEN_LABEL_KW = frozenset({"label", "submit_label"})
#: 允許「只寫到括號為止」的括號字元 —— 見 `test_every_where_names_something_that_exists_on_screen`
#: 的「前綴匹配」段。**只有這幾個**，不含空白、冒號、破折號。
_BRACKETS = ("（", "(", "[", "【", "〔", "{")


def _lane_e_ui_sources() -> list:
    return sorted(pathlib.Path("ui").rglob("*.py"))


def _str_consts(node) -> set:
    """`node` 底下所有字串字面值（含 f-string 的字面片段）。"""
    return {_x.value for _x in ast.walk(node)
            if isinstance(_x, ast.Constant) and isinstance(_x.value, str)}


def _call_name(node: ast.Call, alias: dict) -> str:
    """呼叫點的**正規化**名字（穿過 `import X as _y` 的別名）。

    ⚠️ 不能只看呼叫點寫什麼：`ui/tab_fund_grp_health.py` 寫的是
    `from ui.helpers.ia import applied_form as _applied_form` 之後
    `with _applied_form(..., submit_label="🩺 開始健診")` ——
    只比對字面名字會漏掉它（本規則初版就漏了，是突變探針抓出來的）。
    """
    _f = node.func
    _n = _f.attr if isinstance(_f, ast.Attribute) else (
        _f.id if isinstance(_f, ast.Name) else "")
    return alias.get(_n, _n)


def _import_alias(tree: ast.AST) -> dict:
    _a: dict = {}
    for _n in ast.walk(tree):
        if isinstance(_n, (ast.Import, ast.ImportFrom)):
            for _nm in _n.names:
                if _nm.asname:
                    _a[_nm.asname] = _nm.name.rsplit(".", 1)[-1]
    return _a


def _name_bindings(tree: ast.AST) -> dict:
    """`{識別字: [被指派過的運算式, ...]}`（含 `from M import N as A` 的來源）。

    存在的理由：widget 的 label 常常是先組好再傳
    （`_btn_label = f"📡 載入所有未載入基金（{n} 條…）"` → `st.button(_btn_label)`），
    也常常是 SSOT 常數的別名（`st.button(_LBL_D5_RELOAD_MACRO)`）。
    只看直接傳進去的字面值會漏掉這兩種，而那正是**做對了的**寫法。
    """
    _b: dict = {}
    for _n in ast.walk(tree):
        if isinstance(_n, ast.Assign):
            for _t in _n.targets:
                if isinstance(_t, ast.Name):
                    _b.setdefault(_t.id, []).append(_n.value)
        elif isinstance(_n, ast.AnnAssign) and isinstance(_n.target, ast.Name) \
                and _n.value is not None:
            _b.setdefault(_n.target.id, []).append(_n.value)
        elif isinstance(_n, ast.ImportFrom) and _n.module:
            for _nm in _n.names:
                _b.setdefault(_nm.asname or _nm.name, []).append(
                    ("__import__", _n.module, _nm.name))
    return _b


def _resolve_strings(node, bindings: dict, depth: int = 0) -> set:
    """把一個 label 運算式攤成「它可能印出來的字串片段」集合。"""
    _out = set(_str_consts(node)) if not isinstance(node, tuple) else set()
    if isinstance(node, tuple) and node[0] == "__import__":
        try:
            _m = __import__(node[1], fromlist=[node[2]])
            _v = getattr(_m, node[2], None)
            if isinstance(_v, str):
                _out.add(_v)
        except Exception:                                    # noqa: BLE001
            pass
        return _out
    if depth < 3:
        for _x in ast.walk(node):
            if isinstance(_x, ast.Name):
                for _v in bindings.get(_x.id, []):
                    _out |= _resolve_strings(_v, bindings, depth + 1)
    return _out


def _screen_strings() -> set:
    """全 `ui/**` **真的會被印在畫面上當標籤／標題**的字串集合。

    三個來源，缺一不可：
      1. widget 的 label（含穿過區域變數與 SSOT 常數別名，見 `_name_bindings`）；
      2. `st.subheader` / `header` / `title`，以及 `st.markdown("### …")` 這種標題；
      3. `story_nav` 與 `shared/ui_control_labels` 這兩份 **SSOT** ——
         它們是「指路文案該指的名字」的權威來源，即使某個值當下沒有 widget
         直接用字面值渲染（例如 `where_to_find()` 是執行期組出來的）。
    """
    from ui.helpers import story_nav as _sn
    import shared.ui_control_labels as _ucl

    _out: set = {_v for _k, _v in vars(_ucl).items()
                 if isinstance(_v, str) and not _k.startswith("__")}
    _out |= set(_sn._TAB_LABELS.values()) | set(_sn._SECTION_LABELS.values())
    _out |= {_sn.where_to_find(_k)
             for _k in list(_sn._TAB_LABELS) + list(_sn._SECTION_LABELS)}

    for _p in _lane_e_ui_sources():
        _tree = ast.parse(_p.read_text(encoding="utf-8"))
        _alias, _bind = _import_alias(_tree), _name_bindings(_tree)
        for _n in ast.walk(_tree):
            if not isinstance(_n, ast.Call):
                continue
            _nm = _call_name(_n, _alias)
            if _nm in _SCREEN_WIDGETS:
                _targets = list(_n.args)[:1] + [
                    _k.value for _k in _n.keywords if _k.arg in _SCREEN_LABEL_KW]
                for _a in _targets:
                    _out |= _resolve_strings(_a, _bind)
            elif _nm in _SCREEN_HEADINGS:
                for _a in list(_n.args)[:1]:
                    _out |= _resolve_strings(_a, _bind)
            elif _nm == "markdown":
                for _a in list(_n.args)[:1]:
                    for _s in _str_consts(_a):
                        if _s.strip().startswith("#"):
                            _out.add(_s.strip().lstrip("#").strip())
    return {_s.strip() for _s in _out if _s and _s.strip()}


#: `state_card()` 的參數名 —— **從真簽章推導，不手抄**。
#: 手抄就會多一份真相源，而本檔自己就有一條規則在罵那件事
#: （`test_tab5_does_not_hand_copy_the_labels_it_already_imports`）。
_STATE_CARD_PARAMS: frozenset = frozenset(
    inspect.signature(_state_card).parameters)


def _is_card_spec_dict(node: ast.Dict) -> bool:
    """這個 dict 字面值是不是一份「等著被 `state_card(**card)` 展開」的卡片規格？

    判準：**所有 key 都是字串字面值，且全部落在 `state_card()` 的參數名集合裡**。
    這是 `ui/helpers/ia/cards.py::render_cards()` 對它做的事所隱含的契約 ——
    只要有一個 key 不是 `state_card()` 的參數，那個 dict 一旦被展開就會
    `TypeError`，也就不可能是卡片規格。

    ⚠️ 刻意**不**用「有沒有 `title` 欄位」這種形狀猜測當判準：那是猜。
    跟著**被呼叫的那個函式的簽章**走，`state_card()` 改簽章時本判準自動跟上。
    ⚠️ 帶 `**other` 的 dict（`node.keys` 會有 `None`）**不算**：那種寫法下
    key 集合是執行期才知道的，靜態判不了。**登記為本判準看不到的形狀。**
    """
    _keys = [_k.value for _k in node.keys
             if isinstance(_k, ast.Constant) and isinstance(_k.value, str)]
    return (len(_keys) == len(node.keys)
            and bool(_keys)
            and set(_keys) <= _STATE_CARD_PARAMS)


def _where_sites() -> list:
    """全 `ui/**` 帶「去哪補」的站點 —— **直接呼叫與卡片 dict 兩條路都收**。

    四種形狀：
      1. `not_ready(...)`   —— 連**沒帶** `where=` 的也收（`test_where_is_mandatory` 要看）；
      2. `empty_state(...)` —— 同上；
      3. `state_card(..., where=...)`；
      4. **卡片 dict 字面值 `{"where": …}`** 與事後補的 `card["where"] = …`
         —— 它們最後都會被 `render_cards()` 展開成 `state_card(**card)`。

    ## ⚠️ 3 與 4 是 2026-09-05 補上的射程；補之前那兩條路**完全隱形**

    突變實測（對象：新架構 `ui/views/page_01_macro.py`，**補之前**的樹）：

    | 突變 | 結果 |
    |---|---|
    | 把一個畫面上**不存在**的按鈕字（還故意帶分頁站號 `①`）手抄進某張卡的 `{"where": …}` | `-k "where or remedy"` **13 passed 全綠** |
    | 把該頁 **14 處** dict 帶的 `where` **整個刪光** | 本檔 ＋ `test_render_state_color_separation` ＋ `test_ia_kit` ＋ `test_macro_tab_section_isolation` 合計 **705 passed**，一條都沒響 |
    | **對照組**：同一個字串改放進 `not_ready(..., where=…)` | **2 failed** |

    —— 規則本身有牙（對照組證明），只是**咬不到新架構的正規寫法**
    （dict → `render_cards()`）。同一個字串放 A 處被抓、放 B 處放行。

    修法選**擴大射程**而不是要求產品碼改回直接呼叫：dict → `render_cards()`
    是新架構的正規寫法，為了遷就守衛去改產品碼是本末倒置。

    ⚠️ **`system_error()` 刻意不收** —— 它**根本沒有 `where=` 這個參數**
    （簽章是 `system_error(what, exc, *, hint="", degraded=False)`，見
    `ui/helpers/render_state.py`）。把它列進「必須帶 where=」的規則，
    等於發明一條永遠不可能被滿足的要求。**這一點是實測，不是推論。**

    ⚠️ **3 與 4 只在「真的帶了 `where`」時才登記**，故它們對
    `test_where_is_mandatory` 是中性的 —— 那條問的是「`not_ready`/`empty_state`
    有沒有漏寫 `where=`」，而 `state_card()` 的 `where` **只有
    `state=STATE_NOT_READY` 時才用得到**，對一張 `STATE_OK` 的卡要求 `where=`
    會製造整片假紅。「NOT_READY 卻沒帶 where」那一半由
    :func:`test_not_ready_cards_carry_a_remedy_too` 單獨守。

    ⚠️ **本函式看不到的形狀（誠實列出，不要讀成「dict 路徑已經全守住」）**：
      - `where` 的值是**執行期算出來的**（`_where_to_load()` 這種函式呼叫）——
        登記得到站點，但 `「」` 那條規則抓不到字面值，等於只驗了「有沒有帶」。
        **這正是 `ui/views/page_01_macro.py` 目前 14 處 dict 的實況**
        （量測日 2026-09-05），也是它們**擴大射程後仍然全綠**的原因 ——
        **全綠不等於守到了，只等於它們沒有手抄字面值可供比對。**
      - 卡片清單先組成變數再傳（`_cards = [...]` → `render_cards(_cards)`）
        且 dict 是在別的函式裡建的 —— 跨函式的資料流本函式不追。
      - `card["where"] = …` 這一支**沒有**先確認那個 `card` 真的是卡片規格
        （靜態判不了）；方向上是**多收**，多收會誤判成紅、不會假綠。
    """
    _sites = []
    for _p in _lane_e_ui_sources():
        _rel_p = str(_p).replace("\\", "/")
        _tree = ast.parse(_p.read_text(encoding="utf-8"))
        _alias = _import_alias(_tree)
        for _n in ast.walk(_tree):
            if isinstance(_n, ast.Call):
                _nm = _call_name(_n, _alias)
                if _nm in ("not_ready", "empty_state"):
                    _kw = {_k.arg: _k.value for _k in _n.keywords if _k.arg}
                    _sites.append((_rel_p, _n.lineno, _nm, _kw.get("where")))
                elif _nm == "state_card":
                    _kw = {_k.arg: _k.value for _k in _n.keywords if _k.arg}
                    if _kw.get("where") is not None:
                        _sites.append((_rel_p, _n.lineno, _nm, _kw["where"]))
            elif isinstance(_n, ast.Dict) and _is_card_spec_dict(_n):
                for _k, _v in zip(_n.keys, _n.values):
                    if isinstance(_k, ast.Constant) and _k.value == "where":
                        _sites.append((_rel_p, _v.lineno, "card-dict", _v))
            elif isinstance(_n, ast.Assign):
                for _t in _n.targets:
                    if (isinstance(_t, ast.Subscript)
                            and isinstance(_t.slice, ast.Constant)
                            and _t.slice.value == "where"):
                        _sites.append(
                            (_rel_p, _n.lineno, "card-dict-item", _n.value))
    return _sites


# ── 豁免表（形狀抄本 repo 慣例：站點集合 ＋ 反向斷言，見 `tests/test_ui_grid_contract.py`）
#: `where=` 可以缺席的呼叫點。**目前是空的，而且應該保持空的。**
#: 三個原本缺席的（`mutual_exclusion` / `rotation` / `tab6_manual`）已在本批修好。
#: ⚠️ 空表**不是**裝飾：`test_where_is_mandatory` 的第二條斷言會在有人「修好一個卻
#:    忘了把它從表裡拿掉」時轉紅，所以表一旦被加東西進去，就必須真的降回來。
WHERE_MISSING_EXEMPT: frozenset = frozenset()

#: `where=` 裡 `「」` 指名了一個**畫面上找不到**的字串，但暫時不修的站點。
#: 格式：`"檔案::行為描述::「被指名的字串」"`（**不寫行號** —— 行號在任何一次
#: 重構後就失效，而重構不會觸發本表更新，`CLAUDE.md §8.2.A.0 規則 1`）。
#: ⚠️ 理由欄必須寫「**為什麼這個位置是對的**」（`§8.2.A.0 規則 5`）；
#:    如果理由其實是「還沒修」，就照實寫「**待修**」，不要包裝成設計決定。
WHERE_NAME_EXEMPT: dict = {
    # —— 量測日 2026-09-04：本表**目前是空的**。 ——
    # 本批把實測到的 3 處全部修掉了（`tab2_single_fund` / `policy_admin_section` /
    # `allocation_donut_card`），所以這裡沒有東西可登記。
    #
    # ⚠️ **但「本規則掃到 0 個違規」不等於「全站指路都對了」** —— 據實登記兩批
    #    本規則**結構上看不到**的既有債，它們不在這裡是因為**規則射不到**，
    #    不是因為它們是對的：
    #
    #    (1) **死字串「編輯初始持倉」另有 8 處活字串**（量測日 2026-09-04，以 AST
    #        只數活字串、排除註解與 docstring）：`ui/tab3_t7_ledger.py` ×5、
    #        `ui/tab3_portfolio.py` ×1、`ui/helpers/portfolio/allocation.py` ×1，
    #        另 `services/policy_advisor_service.py` ×1 在 L2 不在 `ui/` ——
    #        ⚠️ 本組初稿曾把它寫成「6 處（`tab3_t7_ledger` ×4）」，**那是沒數過就寫的**；
    #        AST 重數後為 8 / ×5。就地更正並留痕 —— 一節在講「文件不該說謊」的規則，
    #        自己的計數必須先為真（`CLAUDE.md §-2` 規則 6）。
    #        它們全部是 `st.caption` / `st.info` / 一般散文，**不是 `where=`**，
    #        本規則射不到。三檔皆不在本批的檔案邊界內（`CLAUDE.md §8.4 step 4`：
    #        不擴大範圍），已在 PR 描述登記。
    #    (2) 既有指路債另有兩批（一批 7 條、一批 15 檔 65 筆）由前組登記，
    #        本組**未複驗**其數字，不在此複述（`CLAUDE.md §-2` 規則 6）。
    #
    #    (3) **「已 import SSOT 卻仍手抄一份」的既有債**（2026-09-04 獨立稽核指出後
    #        本組以 AST 逐一實測；`test_tab5_does_not_hand_copy_the_labels_it_already_imports`
    #        **只守 `ui/tab5_data_guard.py` 一個檔**，射不到下列任何一處）：
    #        - `ui/tab1_macro.py` —— 已 import 五個常數，仍有 **3 處**手抄變體：
    #          `:1811` 「🔄 更新總經資料」（與 SSOT 逐字相同，屬**尚未**漂移的第二份真相源）、
    #          `:2165` 「更新總經資料」（**已漂移**：掉了 🔄）、
    #          `:2710` 「載入總經資料」（**已漂移**：掉了 📡）。
    #        - `ui/tab3_t7_ledger.py:3268` —— `→ 📡 載入總經資料` 逐字手抄
    #          `MACRO_LOAD_BTN_FIRST`，而**該檔連 `ui_control_labels` 都沒 import**；
    #          它同時是 `test_every_where_names_something_that_exists_on_screen`
    #          docstring 甲類 5 處中的一處（沒有 `「」` → 那條也看不到）。
    #        ⛔ **兩檔皆不在本批的檔案邊界內，登記不修**（`CLAUDE.md §8.4 step 4`）。
    #        ⚠️ 本組實測數與稽核轉述的「`tab1_macro` 2 處」不同（本組數到 3 處）——
    #           差在 `:1811`，它**目前與 SSOT 逐字相同**、還沒漂移，稽核只列已漂移的兩處。
    #           以「**有沒有第二份字面值**」為準則應計 3 處，故本表記 3。
}

#: `_where_sites()` 收得到的站點數下限。錨點用：掉到下限以下代表那些 helper
#: 被換成別的寫法，本段規則正在對空氣生效。
#: ⚠️ 量測日 2026-09-05：**67**（`not_ready` 48 ＋ `empty_state` 5
#: ＋ `card-dict` 13 ＋ `card-dict-item` 1）。
#: ⚠️ **上一版這裡記的「47」在寫下之後就漂掉了**：2026-09-05 以**擴大射程前**的
#: 舊 `_where_sites()` 重量，實際是 **53**（`not_ready` 48 ＋ `empty_state` 5）——
#: 檔案一直在長，而**這個數字不會自己跟上**。留著錯的量測值比不留更糟
#: （`CLAUDE.md §8.2.A.0 規則 4`：會漂移的量測值一律標日期）。
#: 故下限刻意留寬，**真正防「射程退回去」的是下面那條 `card-dict` 形狀斷言**，
#: 不是這個數字。
WHERE_ANCHOR_MIN_SITES = 50
#: 同上，`「」` 指名段落的總數下限（規則真的有東西可比對）。
WHERE_ANCHOR_MIN_QUOTED = 12


# ══════════════════════════════════════════════════════════════════
# 📌 待判定登記（形狀抄 `CLAUDE.md §8.3.P`：**待答問題／由誰查／觸發點**）
#
# ⚠️ **為什麼登記在這裡而不是 `CLAUDE.md §8.3.P`**：本批的檔案邊界只到
#    `tests/**`（＋必要時 `ui/views/page_01_macro.py`），**動不了 `CLAUDE.md`**。
#    依本專案自己的話：**待查證沒有出口 ＝ 實質永久豁免** —— 所以寧可先登記在
#    規則旁邊，也不要讓它只以「誠實揭露」的形式留在 PR 描述裡然後消失。
#    **請總管把本列搬進 `CLAUDE.md §8.3.P`**（那裡才是它的正式住所）。
#
# ── `P-WHERECONTENT-1` ─────────────────────────────────────────────
# **待答問題**：`where=` 的**內容對不對**，目前只驗得到**字面值**。
#   `ui/views/page_01_macro.py` 的 20 個站點裡，14 個 dict-carried 與 4 個直接呼叫
#   用的是 `_where_to_load()` / `where_to_find("diag")` 這種**執行期組出來的值**
#   （量測日 2026-09-05），`test_every_where_names_something_that_exists_on_screen`
#   對它們**只驗到「有帶」，沒驗到「指得對」**。
#   → 該不該補一條「執行期指路」的驗法（例如在 AppTest 下渲染後比對畫面上真有那顆鈕），
#     還是就承認靜態規則到此為止、改用別的手段？
#   ⚠️ **本批擴大射程後那 14 處全綠，但那不是「守住了」** —— 只是「那裡沒有手抄字串」。
# **由誰查**：**獨立一組**（`CLAUDE.md §-2` 規則 4）；
#   **不得**由 2026-09-05 補這條射程的同一組（＝ GUARD-W1）承接。
# **觸發點**（任一命中即應派工）：
#   (1) 有任務碰到 `_where_to_load()` 或 `ui/helpers/story_nav.py` 的指路產生邏輯；
#   (2) 出現「灰卡指到一顆當下不存在的按鈕」的實際回報
#       （`_where_to_load()` 的 docstring 記載 2026-09-05 修過**一次**同型 bug，
#        當時是靠 AppTest 實測抓到的，不是靠本檔任何一條規則）；
#   (3) 有人要把 `where=` 從執行期組值改回字面值（那會讓本條規則突然「看得到」）；
#   (4) user 直接點名。
# ══════════════════════════════════════════════════════════════════


def test_where_is_mandatory():
    """`not_ready()` / `empty_state()` **一律要帶 `where=`**，除非具名登記。

    線框 Rule 04 的三要素是「標題 / 缺什麼 / **去哪補**」，而
    `ui/helpers/render_state.py` 的 docstring 自己寫著：
    **「沒有它，占位只是把『消失』換成『灰色的消失』。」**
    ——「去哪補」是最容易省掉、也最有價值的一項，所以它需要一條規則，
    不能靠每個作者自己記得。

    ⚠️ 本條**不驗** `system_error()`：它沒有 `where=` 這個參數（見 `_where_sites`）。
    """
    _missing = sorted(
        f"{_f}::{_fn}" for _f, _ln, _fn, _w in _where_sites() if _w is None)
    _new = [_m for _m in _missing if _m not in WHERE_MISSING_EXEMPT]
    assert not _new, (
        "以下 `not_ready()` / `empty_state()` 沒有「去哪補」（`where=`）：\n  "
        + "\n  ".join(_new)
        + "\n請補上一個**使用者照著做真的能解決**的指路；"
          "真的無處可指請加進 `WHERE_MISSING_EXEMPT` 並在 PR 描述寫理由。")
    _fixed = sorted(set(WHERE_MISSING_EXEMPT) - set(_missing))
    assert not _fixed, (
        "以下站點已經補上 `where=`（或改名／被刪），但 `WHERE_MISSING_EXEMPT` 還留著它 ——\n"
        "請把表一起降下來。**這條紅燈是提醒不是責備。**\n  " + "\n  ".join(_fixed))


#: 卡片規格「`STATE_NOT_READY` 卻不帶 `where`」的具名豁免。
#: **目前是空的，而且應該保持空的**（形狀與 `WHERE_MISSING_EXEMPT` 一致，含反向斷言）。
NOT_READY_CARD_MISSING_EXEMPT: frozenset = frozenset()

#: 量測日 2026-09-05：`ui/**` 掃得到的卡片規格站點數為 **22**
#: （卡片 dict 21 ＋ 直接 `state_card()` 呼叫 1）。錨點用：掉到下限以下代表
#: 卡片改用別種寫法組出來，本條正在對空氣生效。
NOT_READY_CARD_ANCHOR_MIN = 15


def _mentions_not_ready(node, bindings: dict, funcs: dict, depth: int = 0) -> bool:
    """這個 `state=` 運算式**有沒有可能**是 `STATE_NOT_READY`？

    刻意做成「**提到就算**」而不是「求值等於」：實際寫法多半是
    `STATE_OK if _phase.get("phase") else STATE_NOT_READY` 這種三元式，
    靜態求不出值，但**只要它可能變灰，就該有「去哪補」**。

    三種穿透，缺一就有繞道：
      1. **區域變數** —— `_state = STATE_NOT_READY` → `{"state": _state}`；
      2. **本檔函式的回傳值** —— `{"state": _worst_state(ind, (...))}`，
         而 `_worst_state()` 內有 `return STATE_NOT_READY`；
      3. 常數別名（`from … import STATE_NOT_READY as X` 由 `bindings` 帶進來）。

    ⚠️ **第 2 種是 2026-09-05 獨立稽核打穿本規則的那一條，不是假想**：
    初版只走 `Assign`/`AnnAssign`/`ImportFrom` 綁定，**不追函式回傳值**，
    於是 `ui/views/page_01_macro.py::_card_vol_credit` 這種
    「一般 dict 字面值 ＋ 走正規 `render_cards()` ＋ `state` 委派給 helper」
    的**主力寫法**整個隱形 —— 稽核把它的 `"where"` 刪掉，
    四個測試檔 **706 passed 全綠**。
    量化（量測日 2026-09-05）：22 個卡片站點裡初版看得見 12、看不見 9；
    那 9 個有 7 個本來就不可能變灰（`STATE_OK`／`STATE_ERROR`）→ 正確排除，
    **剩下 2 個是真的會變灰的 `_worst_state`** —— 它們當時有 `where`，
    但**不是這條規則在保護它們**。本次補上第 2 種穿透後 14/14 全部看得到。

    ⚠️ `depth` 上限同時擋掉遞迴函式（`f()` 的 return 又呼叫 `f()`）。
    """
    if node is None:
        return False
    for _x in ast.walk(node):
        if isinstance(_x, ast.Name) and _x.id == "STATE_NOT_READY":
            return True
        if isinstance(_x, ast.Attribute) and _x.attr == "STATE_NOT_READY":
            return True
        if isinstance(_x, ast.Constant) and _x.value == "not_ready":
            return True
        if isinstance(_x, ast.Name) and depth < 3:
            for _v in bindings.get(_x.id, []):
                if not isinstance(_v, tuple) and \
                        _mentions_not_ready(_v, bindings, funcs, depth + 1):
                    return True
            # ⭐ 名字綁的是**本檔的函式** → 掃它的每一個 `return`。
            _fn = funcs.get(_x.id)
            if _fn is not None:
                for _r in ast.walk(_fn):
                    if isinstance(_r, ast.Return) and _r.value is not None \
                            and _mentions_not_ready(_r.value, bindings, funcs,
                                                    depth + 1):
                        return True
    return False


def _card_spec_sites() -> list:
    """全 `ui/**` 的卡片規格站點 `(檔案, 行號, 形狀, 可能變灰嗎, 帶不帶 where)`。

    第 4 欄是**已經判好的布林**（不是 AST 節點）——「這張卡的 `state=`
    有沒有可能是 `STATE_NOT_READY`」，判法見 :func:`_mentions_not_ready`。

    ⚠️ **「帶不帶 where」把事後補的那一支也算進來**：
    `ui/views/page_01_macro.py::_card_exception` 的寫法是先建 dict、
    再 `if _state == STATE_NOT_READY: _card["where"] = _where_to_load()` ——
    只看 dict 字面值會**誤判它漏寫**，而它其實是對的。
    判定粒度取**函式**：該函式內只要出現任一 `…["where"] = …`，
    該函式內的卡片 dict 就算已覆蓋。
    ⚠️ 這是**刻意放寬**的方向（少報，不多報）：同一個函式裡如果有兩張卡、
    只有一張補了 `where`，本條看不到漏掉的那張。**登記，不修** ——
    多報會讓作者為了消紅去加假的 `where=`，那比漏報更糟。

    ## ⚠️ 本函式**看不到的形狀**（誠實列出，不要讀成「卡片路徑已全守住」）

    - **`dict(...)` 建構式** —— `dict(title=…, state=STATE_NOT_READY)` 是
      `ast.Call` 不是 `ast.Dict`，`_is_card_spec_dict()` 與本函式**都看不到**。
      2026-09-05 稽核實測：改成這種寫法 → **706 passed 全綠**，
      而它產生的正是一張 `where=""` 的灰卡。
      **登記，本批不支援** —— 現行樹沒有任何一處這樣寫（量測日 2026-09-05），
      加了等於為一個不存在的寫法擴大規則；但**它是一條真的繞道**，
      哪天有人這樣寫，本規則不會出聲。
    - **帶 `**other` 的 dict**（`node.keys` 會有 `None`）—— key 集合執行期才知道，
      靜態判不了，見 `_is_card_spec_dict()`。
    - **卡片 dict 在別的函式建好再傳進來** —— 跨函式資料流本函式不追。
    """
    _out = []
    for _p in _lane_e_ui_sources():
        _rel_p = str(_p).replace("\\", "/")
        _tree = ast.parse(_p.read_text(encoding="utf-8"))
        _alias, _bind = _import_alias(_tree), _name_bindings(_tree)
        #: 本檔的函式定義 —— 給 `_mentions_not_ready()` 追 `return` 用（F1）。
        _funcs = {_f.name: _f for _f in ast.walk(_tree)
                  if isinstance(_f, (ast.FunctionDef, ast.AsyncFunctionDef))}
        _deferred: set = set()
        for _fn in ast.walk(_tree):
            if not isinstance(_fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if any(isinstance(_x, ast.Assign)
                   and any(isinstance(_tg, ast.Subscript)
                           and isinstance(_tg.slice, ast.Constant)
                           and _tg.slice.value == "where" for _tg in _x.targets)
                   for _x in ast.walk(_fn)):
                _deferred |= {id(_d) for _d in ast.walk(_fn)
                              if isinstance(_d, ast.Dict)}
        for _n in ast.walk(_tree):
            if isinstance(_n, ast.Dict) and _is_card_spec_dict(_n):
                _kv = {_k.value: _v for _k, _v in zip(_n.keys, _n.values)
                       if isinstance(_k, ast.Constant)}
                _out.append((
                    _rel_p, _n.lineno, "card-dict",
                    _mentions_not_ready(_kv.get("state"), _bind, _funcs),
                    "where" in _kv or id(_n) in _deferred))
            elif isinstance(_n, ast.Call) and _call_name(_n, _alias) == "state_card":
                _kw = {_k.arg: _k.value for _k in _n.keywords if _k.arg}
                _out.append((
                    _rel_p, _n.lineno, "state_card",
                    _mentions_not_ready(_kw.get("state"), _bind, _funcs),
                    "where" in _kw))
    return _out


def test_not_ready_cards_carry_a_remedy_too():
    """一張**會變灰的卡**也要說「去哪補」，不是只有 `not_ready()` 直接呼叫要。

    ## 為什麼要有這條（`test_where_is_mandatory` 補不到的那一半）

    `test_where_is_mandatory` 只看 `not_ready()` / `empty_state()` 的呼叫點。
    但新架構的正規寫法是**卡片 dict → `render_cards()` → `state_card(**card)`**，
    而 `state_card()` 的灰分支就是 `not_ready(note or "尚未載入", where=where)` ——
    dict 裡漏掉 `"where"` 的後果**與直接呼叫漏掉 `where=` 一模一樣**：
    使用者拿到一張灰卡，卻沒有任何一句話告訴他去哪裡把它變回來。
    線框 Rule 04 的三要素是「標題 / 缺什麼 / **去哪補**」，
    `ui/helpers/render_state.py` 的 docstring 也自己寫著
    **「沒有它，占位只是把『消失』換成『灰色的消失』。」**

    ⚠️ **這條規則是 2026-09-05 的突變實測逼出來的**：把
    `ui/views/page_01_macro.py` **14 處** dict 帶的 `where` 整個刪光，
    四個測試檔合計 **705 passed**，**沒有一條出聲**。

    ## 判準與它的兩個方向

    - **只對「可能變灰」的卡要求**（`state=` 提到 `STATE_NOT_READY`）。
      對一張 `STATE_OK` 的卡要求 `where=` 會製造整片假紅 ——
      `state_card()` 的 `where` 在非灰分支根本用不到。
    - **少報優於多報**：事後補的 `card["where"] = …` 算數（見 `_card_spec_sites`）。
      多報會讓作者為了消紅去加一個假的 `where=`，那比漏報更糟。

    ## 本條**守不到**的（誠實列出）

    - `where` 的**內容對不對** —— 那是
      `test_every_where_names_something_that_exists_on_screen` 的事，
      而**那條只看得到字面值**：`where=_where_to_load()` 這種執行期組出來的
      指路，兩條規則都只驗到「有帶」，沒驗到「指得對」。
      **這一半有登記出口**：`P-WHERECONTENT-1`（見本檔末尾的待判定登記）。
    - **`dict(...)` 建構式寫成的卡片**、**帶 `**other` 的 dict**、
      以及**在別的函式建好再傳進來的 dict** —— 三種形狀本條都看不到，
      逐一列在 `_card_spec_sites()` 的 docstring 裡。
    - ⚠️ **`state` 委派給本檔函式**（`_worst_state(...)`）**初版看不到，
      2026-09-05 已補**（見 `_mentions_not_ready` 第 2 種穿透）——
      那是獨立稽核用 706 passed 打穿本規則的那一條。
    """
    _sites = _card_spec_sites()
    assert len(_sites) >= NOT_READY_CARD_ANCHOR_MIN, (
        f"只掃到 {len(_sites)} 個卡片規格站點（量測日 2026-09-05 為 22："
        f"`card-dict` 21 ＋ `state_card` 1，錨點下限 {NOT_READY_CARD_ANCHOR_MIN}）"
        "—— 本條可能正在對空氣生效。")
    # ⭐ 形狀鎖：`_card_spec_sites()` 的**兩個**收集分支都要還看得見。
    #    純數字下限擋不住「只關掉其中一支」—— `state_card` 分支現行樹只有 1 個站點，
    #    關掉它數量只掉 1，下限完全不會響。
    _shapes = {_s for _, _, _s, _, _ in _sites}
    assert {"card-dict", "state_card"} <= _shapes, (
        f"`_card_spec_sites()` 少收了分支：現有 {sorted(_shapes)}，"
        "應含 `card-dict` 與 `state_card` —— 收集器退化了，本條會對半瞎。")
    _missing = sorted(
        f"{_f}::{_s}::line {_l}" for _f, _l, _s, _nr, _w in _sites
        if _nr and not _w)
    _new = [_m for _m in _missing if _m not in NOT_READY_CARD_MISSING_EXEMPT]
    assert not _new, (
        "以下卡片可能渲染成 `STATE_NOT_READY`（灰態），卻沒有「去哪補」：\n  "
        + "\n  ".join(_new)
        + "\n灰卡沒有指路，只是把『消失』換成『灰色的消失』。"
          "請補 `\"where\"`（走 `story_nav.where_to_find()`，不要手抄分頁名）。")
    _fixed = sorted(set(NOT_READY_CARD_MISSING_EXEMPT) - set(_missing))
    assert not _fixed, (
        "以下站點已經補上 `where`，但 `NOT_READY_CARD_MISSING_EXEMPT` 還留著它 ——\n"
        "請把表一起降下來。**這條紅燈是提醒不是責備。**\n  " + "\n  ".join(_fixed))


def test_every_where_names_something_that_exists_on_screen():
    """`where=` 用 `「」` 指名的每一個控制項／區塊，畫面上都要真的找得到。

    ## 判準（一段話講完）

    對每一個 `not_ready()` / `empty_state()` 的 `where=`（含 f-string 的字面片段），
    抓出所有 `「…」` 括起來的段落；每一段都必須**等於**「全 `ui/**` 某個 widget 的
    label / 某個標題 / `story_nav` 或 `ui_control_labels` 的某個 SSOT 值」，
    或者是其中某一個的**止於括號的前綴**（見下）。都不是 → 紅。

    ## 前綴匹配：允許，但只允許「止於括號」的那一種（本條最需要說清楚的決定）

    Streamlit 的 label 常常在名字後面掛一段括號說明
    （`📥 上傳 NAV CSV（格式:**代號 ｜ 日期 ｜ 淨值**，無表頭亦可；…）` 有 60 幾個字）。
    要求文案逐字抄整串，只會逼作者去改 label 或乾脆不寫 `where=` —— 規則會把
    「寫得好」變成成本。所以**允許只寫到括號為止**：
    `「📥 上傳 NAV CSV」` 對上 `📥 上傳 NAV CSV（格式:…）` → **綠**。

    ⚠️ **為什麼這不會讓「🔍 找代號 vs 🔍 搜尋基金代號」那種真錯溜過去**，兩層：
      1. **它根本不是前綴** —— `🔍 找代號` 不是 `🔍 搜尋基金代號` 的前綴，
         連寬鬆的前綴匹配都判它紅。這一層與括號規則無關。
      2. **就算是前綴也不一定放行** —— 剩下的那一截必須以 `（([【〔{` 之一開頭。
         `「🔍 搜尋」` 對上 `🔍 搜尋基金代號` 的剩餘是 `基金代號`，**不是括號**
         → **紅**。也就是「把名字砍一半」不會被當成合法縮寫。
         （這正是本批突變探針 3 驗的那一條，實測轉紅。）
    ⚠️ 反過來說，**子字串比對一律不算**：`「編輯初始持倉」` 曾因為別處一句散文提到
       它而在初版原型裡被判成合格 —— 那就是 `CLAUDE.md` 記載的
       「只驗關鍵詞在不在、不驗那句話是不是真的」失效模式。本條只認「等於」與
       「止於括號的前綴」，**不認子字串**。

    ## 本條**守不到**的（據實寫明，不要讀成「指路已經全對」）

    - ⭐ **最重要的一條：本規則是「以 `「」` opt-in」的 —— 不寫 `「」` 就自動豁免。**
      實測（量測日 2026-09-04）：47 個呼叫點裡 **只有 14 個帶 `「」`、本條看得到**，
      **其餘 33 個本條完全掃不到**。
      ⚠️ **2026-09-04 就地更正（有意識的更正，不是漏刪 · 依據：獨立稽核 + 本組重跑）**：
      本段原本寫 ~~「那些指的是 App 外部的東西，畫面上本來就沒有對應 widget」~~ ——
      **那是假的**。本組把 33 個逐一分類後：

      | 類別 | 數 | 說明 |
      |---|---|---|
      | 甲 · **整段裡就含著一個真實 widget/SSOT 標籤** | **5** | **會漂移，而且本條看不到** |
      | 乙 · Secrets／GCP console／sidebar 等 App 外部 | 11 | 畫面上確實沒有對應 widget |
      | 丙 · 兩者皆非（相對位置、泛指某個面板…） | 17 | 無從機器判定 |

      甲的 5 處（實測，逐一列名，**全部不在本批檔案邊界內**）：
      `ui/helpers/portfolio/policy_admin_section.py` ×3 → `🔐 用 Google 登入`、
      `ui/helpers/settings_diag/fetch_diag_section.py` → `🚀 分析`、
      `ui/tab3_t7_ledger.py` → **`📡 載入總經資料`（逐字手抄 `MACRO_LOAD_BTN_FIRST`，
      而該檔連 `ui_control_labels` 都沒 import）**。
      ⚠️ **最後那一筆與本批在 `ui/tab6_manual.py` 修掉的是同一個缺陷，它還活著，
      而五條新規則沒有一條看得到它**（沒有 `「」` → 本條跳過；不是 `tab5` → 那條跳過）。
      ⛔ **刻意不把本條擴大到非 `「」` 的情形** —— 那要改成「整段掃所有已知標籤」，
      誤判率會暴增（實測：分區名「批次掃描」「資料診斷」都是合法按鈕字的子字串），
      且屬擴大範圍（`CLAUDE.md §8.4 step 4`）。**登記，不動。**
    - **乙類那 11 個**（`Streamlit Cloud → Settings → Secrets 的 `FRED_API_KEY`` 等）
      —— 指的是 App 外部的東西，畫面上本來就沒有對應 widget。
    - **`where=` 以外的指路**（`st.caption` / `st.info` 裡的「請到 X」）—— 那是
      另一批既有債，見 `WHERE_NAME_EXEMPT` 的登記。
    - **`where=` 整段由 SSOT 組出來時**（`f"{where_to_find('macro')} → …"`）
      —— 內插進來的部分不是字面值，本條看不到，但它也**不可能漂移**（那正是走 SSOT 的用意）。
    - **文案通不通順、使用者照做有沒有用** —— 那要人看。
    """
    _screen = _screen_strings()
    #: 目前**真的解析不出來**的站點（先不看豁免表）—— 形狀抄
    #: `tests/test_ui_grid_contract.py`：先算 `found`，再與豁免表做**雙向**差集。
    #: ⚠️ 刻意不在迴圈裡 `continue` 掉豁免項：那樣 `_fixed` 就只能回答
    #:    「這個字串還在不在」，回答不了「它是不是已經不再違規了」——
    #:    有人把 **widget 改名成配合文案**時，豁免表會靜靜留著一筆假債。
    _failing: dict = {}
    _quoted_n = 0
    for _f, _ln, _fn, _w in _where_sites():
        if _w is None:
            continue
        for _s in _str_consts(_w):
            for _seg in _WHERE_QUOTED.findall(_s):
                _quoted_n += 1
                if _seg in _screen:
                    continue
                if any(_lab.startswith(_seg)
                       and _lab[len(_seg):][:1] in _BRACKETS for _lab in _screen):
                    continue
                _near = sorted((_l for _l in _screen if _seg[:3] and _seg[:3] in _l),
                               key=len)[:2]
                _failing[f"{_f}::{_fn}::「{_seg}」"] = (
                    f"{_f}:{_ln} 「{_seg}」（畫面上最接近的：{_near or '無'}）")
    assert _quoted_n >= WHERE_ANCHOR_MIN_QUOTED, (
        f"只抓到 {_quoted_n} 個 `「」` 指名段落（量測日 2026-09-04 為 19，"
        f"錨點下限 {WHERE_ANCHOR_MIN_QUOTED}）—— 本條可能正在對空氣生效。")
    _bad = sorted(_v for _k, _v in _failing.items() if _k not in WHERE_NAME_EXEMPT)
    assert not _bad, (
        "以下「去哪補」指名了**畫面上不存在**的控制項／區塊 —— 使用者照著找會找不到：\n  "
        + "\n  ".join(_bad)
        + "\n請改成畫面上真正的那個字（或改吃 `ui/helpers/story_nav` /"
          " `shared/ui_control_labels` 的 SSOT）。"
          "\n真的不修請加進 `WHERE_NAME_EXEMPT` 並寫**為什麼這個位置是對的**；"
          "理由若其實是「還沒修」，就照實寫「待修」。")
    _fixed = sorted(set(WHERE_NAME_EXEMPT) - set(_failing))
    assert not _fixed, (
        "以下站點已經不再違規（文案改對了、widget 改名了，或整段被刪），"
        "`WHERE_NAME_EXEMPT` 還留著它 ——\n"
        "請把表一起降下來。**這條紅燈是提醒不是責備。**\n  " + "\n  ".join(_fixed))


def test_where_does_not_hardcode_a_tab_ordinal():
    """`where=` 裡不准出現手寫的分頁站號（①②③④⑤…）。

    站號是 `_TAB_LABELS` **順序**的函數，`story_nav._tab_ordinal()` 存在的唯一理由
    就是不要有人手寫它（該檔原文：「線框點名的『Tab2＝個基深掘（實際第 4）』正是
    寫死站號在分頁增刪後留下的地雷」）。

    實測命中並在本批修掉的：`ui/components/mutual_exclusion.py` 的
    `where="⑤ 資料診斷"` —— **站號與名字都是手寫的**，而 ⑤ 的分區其實叫
    「🔭 資料診斷」、分頁叫「⚙️ 設定與診斷」，兩個都對不上。

    ⚠️ **與 `tests/test_wpf_five_tab_wiring.py::test_no_live_string_hardcodes_a_tab_name`
    不重疊**：那條比對的是**完整分頁標籤**（含 emoji），而「⑤ 資料診斷」裡的
    「資料診斷」是**分區**名不是分頁名，站號又是它字表裡沒有的東西 ——
    所以那條結構上抓不到它。本條補的是那個縫，不是它的複本。
    ⚠️ 本條**不擋**「分區名寫成字面值」：實測那樣會誤傷兩個合法的按鈕
    （「📦 載入批次掃描面板」/「🔭 載入資料診斷」都含分區名當子字串），
    誤判率高於它抓到的東西。那一半留給上面那條的「畫面上找不找得到」去守。

    ## ⚠️ 只看 `「」` **之外**的圈號（本規則初版的誤判，就地記錄）

    初版對整串比對，結果**當場誤傷本批自己寫的一則合法文案**：
    `ui/helpers/fund_grp_health/rotation.py` 的
    `where="…「② 或直接貼上(每行一檔,逗號/換行皆可)」…"` ——
    那個 `②` 是 `ui/tab_batch_analysis.py` 那個 `st.text_area` **label 自己的字**
    （面板內的步驟編號），不是分頁站號。

    修法不是加豁免，是**把判準寫對**：`「」` 裡面的東西**已經由上一條驗過
    「畫面上真的有這個標籤」**，圈號是那個標籤的一部分，不可能因為分頁增刪而過期；
    真正會過期的是**散在句子裡、沒有任何 widget 撐著**的那種站號（`"⑤ 資料診斷"`）。
    故本條先把所有 `「…」` 段落挖掉，再看剩下的句子裡有沒有圈號。
    ⚠️ 代價據實寫明：有人把站號塞進 `「」` 就能繞過本條 —— 多數情況它會落到
    上一條手上（`「⑤ 資料診斷」` 不等於任何 widget label / SSOT 值 → 紅）。
    ⚠️ **但「兩條合起來就封閉」是過強的說法，2026-09-04 就地放寬（依據：獨立稽核）**：
    把 `where_to_find()` 的**當前輸出逐字硬抄**進 `「」`
    （`「⑤ ⚙️ 設定與診斷 → 🔭 資料診斷」`）—— **本條與上一條都會過**
    （它確實「等於」一個 SSOT 值），可是它一樣會在分頁改名時過期。
    抓到它的是**既有的** `tests/test_wpf_five_tab_wiring.py::test_no_live_string_hardcodes_a_tab_name`。
    → **系統整體有守住，但守住的不是這兩條。** 據實寫明，不要把功勞算到本條頭上。
    """
    _ord = "①②③④⑤⑥⑦⑧⑨⑩"
    _bad = [f"{_f}:{_ln} {_s!r}"
            for _f, _ln, _fn, _w in _where_sites() if _w is not None
            for _s in _str_consts(_w)
            if any(_o in _WHERE_QUOTED.sub("", _s) for _o in _ord)]
    assert not _bad, (
        "以下「去哪補」手寫了分頁站號 —— 分頁一增刪／改順序就會指錯：\n  "
        + "\n  ".join(_bad)
        + "\n請改用 `ui.helpers.story_nav.where_to_find(<key>)`，站號由它推導。")


def test_where_rules_are_not_scanning_air():
    """錨點：上面三條規則還看得見東西嗎？

    少了這條，只要有人把 `not_ready` 包進一層看不見的 helper、或把
    widget 換成自訂元件，前三條就會在**掃到 0 個站點**的情況下天天全綠 ——
    一條對空氣生效的規則比沒有規則更危險，因為它看起來有在守。
    （形狀抄 `tests/test_ui_grid_contract.py::test_grid_anchor_streamlit_columns_still_detectable`。）

    ✅ **這條真的擋過一次**（2026-09-04 獨立稽核實測）：稽核從錯的 CWD 跑，
    `test_where_is_mandatory` 掃到 0 個站點而**靜靜通過** —— 是本條把它抓紅的。

    ## ⛔ 本錨點**守不到**的方向：**過度收集**（2026-09-04 登記，本批不修）

    三個下限（站點數 / `「」` 段落數 / 對照組大小）擋的都是「**縮到看不見**」；
    **沒有任何一條擋「對照組膨脹到什麼都對得上」**。
    稽核用突變證明這個方向**真的能造出假綠**：加寬 `_SCREEN_WIDGETS`（把
    `caption`/`info`/`write` 收進來）＋ 把某個 `where=` 指向一段純散文 caption
    → **203 passed 全綠、四個錨點也全綠**。
    ⚠️ **本檔自己的 docstring 早就寫出這個風險**（下面那句「或（**若同時放寬**）
    全部誤判成綠」），**但程式沒有守它** —— 寫出來卻沒守，比沒寫更容易讓人以為守過了。
    → **本批只登記、不加上限**：加一條「對照組不得超過 N」屬新規則設計，
    要先量清楚 `ui/**` 正常成長會不會自然撞上限，那是下一批的事。

    ## ⚠️ `_screen_strings()` 的一個安全方向偏差（O-2，登記即可）

    `_resolve_strings()` 為了解析 `from M import X as _y` 會**真的 import M** ——
    測試期會載入 `infra.oauth` / `infra.llm` / `repositories.policy.*` /
    `services.ai_service` 等。那裡包著 `except Exception: pass`，
    **某個環境 import 失敗 → 對照組會靜默縮小**。
    **方向是安全的**（縮小 ⇒ 誤判成**紅**，不會假綠），且上限錨點會先叫；
    本組與稽核各重跑兩次、數字完全相同（716）。**登記，不修。**
    """
    _n = len(_where_sites())
    assert _n >= WHERE_ANCHOR_MIN_SITES, (
        f"只掃到 {_n} 個帶「去哪補」的站點"
        f"（量測日 2026-09-05 為 67：`not_ready` 48 ＋ `empty_state` 5 ＋ "
        f"`card-dict` 13 ＋ `card-dict-item` 1，錨點下限 {WHERE_ANCHOR_MIN_SITES}）—— "
        "規則可能正在對空氣生效。")
    # ⭐ 形狀斷言：**比上面那個數字重要**。純數字下限擋不住「射程退回去」——
    #    把 `_where_sites()` 改回只收 `not_ready`/`empty_state`，站點從 67 掉到 53，
    #    **仍然在下限之上**，數字錨點不會響。而 dict → `render_cards()` 這條路
    #    正是新架構的正規寫法，它一旦重新隱形，本檔 2026-09-05 補的射程就白補了。
    #
    # ⚠️ **用集合包含、不要只釘一個**（2026-09-05 獨立稽核指出）：初版只寫
    #    `"card-dict" in _kinds`，於是**只關掉 `card-dict-item`（`Assign`）那一支
    #    → 204 passed 全綠**。射程可以「退一半」而無聲，而這條鎖存在的唯一理由
    #    就是防這件事。**一條只鎖住三分之一的鎖，會讓人以為三個都鎖了。**
    _kinds = {_fn for _, _, _fn, _ in _where_sites()}
    assert {"card-dict", "card-dict-item"} <= _kinds, (
        f"`_where_sites()` 少收了分支：現有 {sorted(_kinds)}，"
        "應含 `card-dict`（dict 字面值）與 `card-dict-item`（`card[\"where\"] = …`）。\n"
        "dict → `render_cards()` → `state_card(**card)` 是新架構的正規寫法；"
        "它隱形的時候，手抄一個過期按鈕字進去是**全綠**的"
        "（2026-09-05 突變實測：13 passed）。")
    # ⚠️ **`_where_sites()` 的第三支 `state_card(where=…)` 在這裡釘不住** ——
    #    現行樹 `ui/**` 唯一那個直接 `state_card(...)` 呼叫**沒有帶 `where=`**
    #    （量測日 2026-09-05），所以它在 `_kinds` 裡根本不會出現，
    #    寫進上面的集合會**當場紅**、變成一條假規則。
    #    那一支改由 `test_not_ready_cards_carry_a_remedy_too` 的形狀鎖看著
    #    （`_card_spec_sites()` 不論帶不帶 `where` 都收 `state_card`，故釘得住）。
    #    **據實寫在這裡，是為了不讓後人以為三支都被這一條鎖住了。**
    _screen = _screen_strings()
    assert len(_screen) >= 300, (
        f"畫面字串集合只有 {len(_screen)} 個（量測日 2026-09-04 為 716）—— "
        "widget 抽取可能壞了，那會讓「指名的東西存不存在」那條**全部誤判成紅**"
        "或（若同時放寬）全部誤判成綠。")
    # 抽取器真的看得懂「穿過別名／區域變數」的那兩種寫法（各一個實例，取自現行樹）
    assert "🩺 開始健診" in _screen, (
        "`applied_form as _applied_form` 的 `submit_label=` 沒被抽到 —— "
        "別名解析壞了（本規則初版就是漏了它，由突變探針抓出來）。")
    assert any(_s.startswith("📡 載入所有未載入基金") for _s in _screen), (
        "先組成區域變數再傳給 `st.button()` 的 label 沒被抽到 —— 區域變數解析壞了。")


def test_tab5_does_not_hand_copy_the_labels_it_already_imports():
    """`ui/tab5_data_guard.py` 已經 import 了控制項標籤 SSOT，就不准再抄一份。

    形狀與本檔既有
    `test_every_remedy_names_a_control_that_actually_exists_on_screen`
    末段的「不得再有第二份字面值」相同，只是換一個檔案。

    實測（修掉之前）：該檔 import 了 `DATA_GUARD_RELOAD_MACRO_BTN`
    並拿它渲染那顆鈕，但 ⓪ 診斷總表第一列的「排查」欄卻手抄了
    `"若 < 85% → 按上方「重新載入總經"` —— **而且抄漏了 🔄**，
    兩份當時已經不一樣了。這正是 `shared/ui_control_labels.py` 整篇要防的形狀。

    ⚠️ 只掃**活字串**（AST 的 `ast.Constant`），註解與 docstring 天然不在其中 ——
    本 repo 的慣例是「舊條文保留不刪 + 註明理由」，把註解算進來等於禁止記錄歷史。
    """
    _p = pathlib.Path("ui/tab5_data_guard.py")
    _tree = ast.parse(_p.read_text(encoding="utf-8"))
    _docs = {id(_b[0].value) for _n in ast.walk(_tree)
             if isinstance(_n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                                ast.ClassDef))
             and (_b := getattr(_n, "body", None))
             and isinstance(_b[0], ast.Expr)
             and isinstance(_b[0].value, ast.Constant)
             and isinstance(_b[0].value.value, str)}
    _live = [_n.value for _n in ast.walk(_tree)
             if isinstance(_n, ast.Constant) and isinstance(_n.value, str)
             and id(_n) not in _docs]
    for _lbl in (_LBL_D5_HOT_MONEY_BTN, _LBL_D5_RELOAD_MACRO_BTN):
        # 去 emoji 的變體也要擋 —— 上面那個實測案例抄漏的正是 emoji。
        _bare = _lbl.split(" ", 1)[-1]
        _hit = [_s for _s in _live if _bare in _s and _s != _lbl]
        assert not _hit, (
            f"標籤 {_lbl!r} 被抄成第二份字面值（含去 emoji 變體）：{_hit}\n"
            "本檔已經 import 了它的 SSOT 常數，請直接內插那個常數。")
