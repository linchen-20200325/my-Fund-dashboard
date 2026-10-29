# -*- coding: utf-8 -*-
"""共用 presentation primitives 的畫面測試（BL-0525 Batch A；T10 的畫面半邊；slow lane，AppTest）。

用最小腳本直接畫 `ui_v2/presentation_view.py` 的三個函式（不經任何頁面、不打網路），驗：
圖表在卡內且在 detail 之前、detail 預設收合、巢狀時不開第二層展開區、Missing 卡不畫數字、內容完整可取得。
"""

from __future__ import annotations

import pathlib
import sys

import pytest

pytestmark = pytest.mark.slow

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

_HEAD = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
import streamlit as st
from ui_v2 import presentation as P, presentation_view as V
"""

_CHART = _HEAD + """
detail = P.detail_model(why=["近三個月波動偏低，是因為……"], source=["Yahoo:^VIX，取得 2026-10-28"],
                        limits=["缺值日不補值"], where=["⚙️ 設定與診斷"])
chips = [P.chip("資料日 2026-10-28"), P.chip("近三月 -4.2%"), P.chip("◷ 延遲 3 日", "黃")]
model = P.chart_card_model("VIX", chips, "近三個月波動偏低", detail=detail)
V.render_chart_card(model, draw_chart=lambda: st.markdown("CHART_SENTINEL"))
"""

_CHART_NESTED = _HEAD + """
detail = P.detail_model(source=["來源甲"])
model = P.chart_card_model("VIX", [P.chip("a"), P.chip("b"), P.chip("c")], "一句", detail=detail)
with st.expander("外層", expanded=False):
    V.render_chart_card(model, draw_chart=lambda: st.markdown("CHART_SENTINEL"), nested=True)
"""

_CHART_NO_DETAIL = _HEAD + """
model = P.chart_card_model("VIX", [P.chip("a"), P.chip("b"), P.chip("c")], "一句")
V.render_chart_card(model, draw_chart=lambda: st.markdown("CHART_SENTINEL"))
"""

_MISSING = _HEAD + """
m = P.missing_model("信用利差", "尚未接上正式來源", detail=P.detail_model(where=["資料來源決策待客戶裁示"]))
V.render_missing_placeholder(m)
"""


def _run(script):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(script, default_timeout=60)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _all_markdown(at) -> str:
    return "\n".join(m.value for m in at.markdown)


def test_圖卡_標題chips摘要外露_圖表在卡內_detail預設收合且內容完整():
    at = _run(_CHART)
    md = _all_markdown(at)
    for needle in ("VIX", "資料日 2026-10-28", "近三月 -4.2%", "◷ 延遲 3 日", "近三個月波動偏低"):
        assert needle in md, needle
    # 長說明（為什麼／來源／限制／去哪補）不在圖表之前的外露段，只在預設收合的展開區裡。
    exp = [e for e in at.expander]
    assert len(exp) == 1 and exp[0].label == "▸ 為什麼‧來源‧限制‧去哪補" and exp[0].proto.expanded is False
    inside = "\n".join(m.value for m in exp[0].markdown)
    for needle in ("近三個月波動偏低，是因為", "Yahoo:^VIX，取得 2026-10-28", "缺值日不補值", "⚙️ 設定與診斷"):
        assert needle in inside, needle
    outside = md.replace(inside, "")
    assert "缺值日不補值" not in outside and "Yahoo:^VIX" not in outside
    # 圖表是外露的（不在展開區內）。
    assert "CHART_SENTINEL" in md and "CHART_SENTINEL" not in inside


def test_圖卡_巢狀時不開第二層展開區_內容仍完整():
    at = _run(_CHART_NESTED)
    assert [e.label for e in at.expander] == ["外層"]
    assert "來源甲" in "\n".join(m.value for m in at.expander[0].markdown)


def test_圖卡_沒有detail內容就不放空殼展開區():
    at = _run(_CHART_NO_DETAIL)
    assert len(at.expander) == 0


def test_Missing卡_灰色資料未備chip_一句原因_detail有去哪補_沒有任何數字欄():
    at = _run(_MISSING)
    md = _all_markdown(at)
    assert "◇ 資料未備" in md and "尚未接上正式來源" in md and "信用利差" in md
    assert [e.label for e in at.expander] == ["▸ 去哪補"]
    assert at.expander[0].proto.expanded is False
    assert "資料來源決策待客戶裁示" in "\n".join(m.value for m in at.expander[0].markdown)
    assert len(at.metric) == 0
    card = "\n".join(m.value for m in at.markdown if "<style>" not in m.value)
    assert not any(ch.isdigit() for ch in card), card   # 沒有任何數字（不會被畫成 0）


def test_畫錯模型種類_轉紅():
    from ui_v2 import presentation as P
    from ui_v2 import presentation_view as V

    with pytest.raises(ValueError):
        V.render_chart_card(P.missing_model("x", "原因"), draw_chart=lambda: None)
    with pytest.raises(ValueError):
        V.render_missing_placeholder(P.chart_card_model("x", [P.chip("a"), P.chip("b"), P.chip("c")], "一句"))
