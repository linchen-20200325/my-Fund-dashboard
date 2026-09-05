"""① 市場總覽「🔎 詳細資料與說明」五塊的**順序鎖**（新架構 `ui/views/page_01_macro.py`）。

為什麼要有這個檔（先看這段，否則會以為它跟既有那條重複）
--------------------------------------------------------
本 repo **已經有**一條四時域順序鎖：
`tests/test_audit_20260805_tab1_ui.py::test_the_four_horizon_sections_stay_in_order_and_contiguous`。
**它守的是舊頁 `ui/tab1_macro.py`，而且完全守不到新頁** —— 三個錨全在舊檔上：

1. `_TAB1 = _ROOT / "ui" / "tab1_macro.py"` —— 只讀舊檔的原始碼；
2. `_HORIZON_RENDERERS` 是**寫死在測試檔裡的 tuple**，不是從
   `shared.macro_buckets.BUCKET_ORDER` 推導的；
3. 判定方式是 **AST 掃原始碼行號**，看的是「呼叫寫在第幾行」，
   不是「執行期真的照什麼順序畫出來」。

⚠️ **兩條的分工（不要刪掉任何一條）**：
  - **舊那條** → 守 `ui/tab1_macro.py`。客戶方針第 3 條要舊 tab 留到五頁驗收完成，
    **舊檔還活著，它就還要守**。本檔**不碰它、不取代它**。
  - **本檔** → 守 `ui/views/page_01_macro.py`。舊那條在新頁上結構性失效
    （錨全在舊檔），新頁在本檔出現之前**沒有任何順序保護**。

三條規則，各守一個不同的失效模式
--------------------------------
- :func:`test_detail_zone_keys_are_derived_from_bucket_order`
  —— **結構鎖**。順序的唯一出處是 `BUCKET_ORDER`，本檔與產品碼都不手抄第二份。
- :func:`test_detail_zone_renders_its_five_sections_in_order_and_contiguous`
  —— **行為鎖**。錄下**真的渲染出來的**一級標題序列。
  這條才抓得到「序列長得很正確、但根本沒有人呼叫它」與「中間插了別的一級區塊」。
- :func:`test_the_mid_cycle_block_really_delegates_to_the_shared_renderer`
  —— **接線鎖**。防「真區塊被悄悄換回灰態佔位卡」而前兩條照樣綠。

⚠️ **為什麼行為鎖不可省（結構鎖擋不住的那一半）**：
   `_DETAIL_ZONE` 是一個 module-level tuple。**一個沒有被呼叫的序列，
   同樣可以長得完全正確** —— 把 `_render_detail_zone()` 整句從
   `_render_deferred_blocks()` 刪掉，結構鎖仍然全綠。
"""
from __future__ import annotations

import re
from unittest.mock import patch

import pytest
import streamlit as st

from shared.macro_buckets import BUCKET_ORDER

import ui.views.page_01_macro as _page

#: 一級區塊標題 = markdown 的 H2~H4。
#: ⚠️ **刻意不含 H5** —— `ui/tab1_macro_midcycle.py` 的
#: `##### 🧭 L3 情境判斷` 是**中期循環自己的子標題**，不是一個平行的一級區塊；
#: 把它算進來會讓「連續」永遠不成立。
_OPENER_RE = re.compile(r"^#{2,4}\s")


class _FakeSessionState(dict):
    """`st.session_state` 的替身（同 `tests/test_audit_20260805_tab1_ui.py` 的做法）。"""

    def __getattr__(self, k):
        return self.get(k)

    def __setattr__(self, k, v):
        self[k] = v


def _render_and_record(*, loaded: bool) -> list[str]:
    """跑**真的** `render_market_overview()`，回傳它實際印出的一級標題序列。

    回傳的是**去掉 `#` 前綴的標題字**，不是原始 markdown ——
    本檔守的是「哪五塊、什麼順序」，**不是**「標題用第幾級」。
    標題級數在批次三把其餘四塊搬過來時本來就會被統一，
    鎖住它只會製造一條與版面演進作對的假紅。
    """
    _ss = _FakeSessionState({_page._SK_IND: {}} if loaded else {})
    _seen: list[str] = []

    def _rec(*a, **_kw):
        if a and isinstance(a[0], str):
            _seen.append(a[0])

    with patch.dict("os.environ", {"FRED_API_KEY": "test-key"}), \
            patch.object(st, "session_state", _ss), \
            patch.object(st, "markdown", side_effect=_rec):
        _page.render_market_overview()

    return [_OPENER_RE.sub("", _t).strip()
            for _t in _seen if _OPENER_RE.match(_t)]


def _zone_openers(openers: list[str]) -> list[str]:
    """從詳細區的區頭那一格起，取到最後 —— 區內與區後不得再冒出別的一級區塊。"""
    assert _page._DETAIL_HEADING in openers, (
        f"畫面上找不到詳細區的區頭「{_page._DETAIL_HEADING}」；"
        f"實際印出的一級標題：{openers}")
    return openers[openers.index(_page._DETAIL_HEADING):]


# ══════════════════════════════════════════════════════════════
# 1) 結構鎖 —— 順序只有一個出處
# ══════════════════════════════════════════════════════════════
def test_detail_zone_keys_are_derived_from_bucket_order():
    """四時域的 key 與順序**必須**等於 `BUCKET_ORDER` 去掉新聞桶，第五項是 AI 總結。

    **突變會紅**：把 `_DETAIL_ZONE` 的任兩項對調 → 本條紅。

    ⚠️ 期望值在這裡是**從 `BUCKET_ORDER` 算出來的**，不是抄一份
    `["long", "mid", "short", "inflection"]` 進測試檔 ——
    抄了就變成第二份順序表，正是既有那條
    （`_HORIZON_RENDERERS` 寫死 tuple）失效的原因之一。
    """
    _want_horizons = [_k for _k in BUCKET_ORDER if _k != "news"]
    _got = [_k for _k, _t, _r in _page._DETAIL_ZONE]

    assert _got[:len(_want_horizons)] == _want_horizons, (
        f"四時域順序與 BUCKET_ORDER 對不上；"
        f"期望 {_want_horizons}、實際 {_got[:len(_want_horizons)]}")
    assert _got[len(_want_horizons):] == [_page._DETAIL_AI_KEY], (
        f"第五項應該是 🤖 AI 總結（key={_page._DETAIL_AI_KEY!r}）；實際 {_got}")
    assert len(_got) == len(set(_got)), f"詳細區出現重複的 key：{_got}"


def test_the_news_bucket_is_not_a_detail_section():
    """📰 新聞桶在 `BUCKET_ORDER` 裡，但**不屬於詳細區**。

    線框 section 03 的五塊沒有它；本頁的新聞在上方的「新聞情緒」卡。
    **突變會紅**：把 `_DETAIL_HORIZON_KEYS` 改成 `BUCKET_ORDER` 全取 → 本條紅。
    """
    assert "news" in BUCKET_ORDER, "前提變了：BUCKET_ORDER 已經沒有新聞桶"
    assert "news" not in [_k for _k, _t, _r in _page._DETAIL_ZONE], \
        "📰 新聞桶被畫進詳細區了 —— 線框 section 03 的五塊沒有它"


# ══════════════════════════════════════════════════════════════
# 2) 行為鎖 —— 錄下真的畫出來的順序
# ══════════════════════════════════════════════════════════════
@pytest.mark.parametrize("loaded", [False, True], ids=["未載入", "已載入"])
def test_detail_zone_renders_its_five_sections_in_order_and_contiguous(loaded):
    """五塊**依序且連續**畫出來 —— 兩種載入狀態都要成立。

    **這是本檔最重要的一條。** 它守三件結構鎖守不到的事：
      (a) `_render_detail_zone()` **真的被呼叫**（序列存在 ≠ 有人用它）；
      (b) 五塊之間**沒有夾別的一級區塊**；
      (c) 兩種狀態下**都**畫（「還沒載入」不是骨架消失的理由，鐵則 04）。

    ⚠️ 「連續」的判定一路取到**畫面結尾**，不只取到第五塊 ——
       否則有人把一個新區塊接在 🤖 AI 總結後面，這條不會響，
       而詳細區就不再是本頁的最後一段了。
    """
    _zone = _zone_openers(_render_and_record(loaded=loaded))
    _want = [_page._DETAIL_HEADING] + [_t for _k, _t, _r in _page._DETAIL_ZONE]

    assert _zone == _want, (
        "詳細區的一級區塊序列跑掉了（順序、缺塊、或中間/後面夾了別的一級區塊）。\n"
        f"  期望：{_want}\n  實際：{_zone}")


def test_detail_zone_heading_is_the_wireframe_name():
    """區頭必須是線框 section 03 用的那個名字。

    ⚠️ **這條是一則已上線錯誤的回歸鎖，不是裝飾**：本區塊先後被叫成
    「🔎 詳細五時域」（自創、九份線框 0 命中）與「🔎 詳細區（四時域＋決策矩陣＋AI）」
    （逐字抄對了，但抄自 section 01「**現況**盤點」而不是 section 03「**重組後**版面」）。
    拍板的名字從頭到尾都是「🔎 詳細資料與說明」，而**舊頁 `ui/tab1_macro.py`
    渲染的也正是這個字**（`st.markdown("## 🔎 詳細資料與說明")`）。
    """
    assert _page._DETAIL_HEADING == "🔎 詳細資料與說明"


# ══════════════════════════════════════════════════════════════
# 3) 接線鎖 —— 真區塊不得悄悄退回佔位卡
# ══════════════════════════════════════════════════════════════
def test_the_mid_cycle_block_really_delegates_to_the_shared_renderer():
    """📈 中期循環**真的**委派給 `ui/tab1_macro_midcycle.py`，而不是自己重寫或退回灰態。

    **突變會紅**：把 `_detail_mid` 換成 `partial(_detail_pending, …)`
    → 前兩條**照樣全綠**（標題還在、順序還在），本條紅。
    **這正是「畫面看起來沒事、功能已經消失」那一類漂移**，
    也是客戶方針第 3 條（舊 tab 待驗收完成才整批拔除）要防的東西。

    同時鎖住**傳進去的是 session 裡那一份 `ind`** —— 不是另外抓一次
    （那會變成同一頁對同一份資料有兩個取數點，§2.1）。
    """
    _ind = {"__probe__": object()}
    _ss = _FakeSessionState({_page._SK_IND: _ind})
    _calls: list[tuple] = []

    with patch.dict("os.environ", {"FRED_API_KEY": "test-key"}), \
            patch.object(st, "session_state", _ss), \
            patch("ui.tab1_macro_midcycle.render_mid_cycle_section",
                  side_effect=lambda *a, **k: _calls.append((a, k))):
        _page.render_market_overview()

    assert len(_calls) == 1, (
        f"📈 中期循環應該恰好委派一次 `render_mid_cycle_section`，實際 {len(_calls)} 次")
    _args, _kw = _calls[0]
    _passed = _args[0] if _args else _kw.get("ind")
    assert _passed is _ind, (
        "傳給 `render_mid_cycle_section` 的 ind 不是 session 裡那一份 —— "
        "同一頁對同一份資料出現第二個取數點")


def test_the_other_four_sections_are_still_honest_placeholders():
    """另外四塊目前是**誠實灰態**，不是空白、也不是假裝有內容。

    ⚠️ **本條會隨批次三失效，那是刻意的** —— 每搬真一塊，就要來這裡把它移出
    `_expected_pending`。**強迫搬遷的人回頭改這一行**，比讓守衛悄悄變成空集合好：
    一條「什麼都沒斷言」的測試會一直是綠的。
    """
    _expected_pending = {"long", "short", "inflection", _page._DETAIL_AI_KEY}
    _pending = {
        _k for _k, _t, _r in _page._DETAIL_ZONE
        if getattr(_r, "func", _r) is _page._detail_pending
    }
    assert _pending == _expected_pending, (
        f"詳細區的灰態塊變了；期望 {sorted(_expected_pending)}、實際 {sorted(_pending)}。\n"
        "若這是因為又搬真了一塊：請同步改本條，並在 `_DETAIL_ZONE` 補上它的 renderer。")


# ══════════════════════════════════════════════════════════════
# 4) 指路鎖 —— 線框 section 05 點名要留的那一句
# ══════════════════════════════════════════════════════════════
def test_the_decision_matrix_signpost_survives_and_uses_the_ssot():
    """「逐檔加減碼建議搬去 ② 了」這句指路**不得消失**，且**不得手抄分頁名**。

    線框 section 05「據實揭露」原文：
    「① 頁會變短、變得『只講市場』。習慣在 ① 頁底看逐檔加減碼建議的人，會找不到它
    —— 需要在 ① 的決策矩陣原位留一句指路到 ②。」
    同段並明寫這批新指路「**一律走同一支 SSOT，不得手抄**」。

    ⚠️ **為什麼要單獨守它**：它是整批搬移裡**唯一留給使用者的線索**。
    刪掉它，畫面不會壞、其他測試不會紅，只有使用者找不到東西 ——
    典型的「測試全綠、體驗全錯」。

    ⚠️ 本條**不比對字面值**，而是比對 `where_to_find('health')` 的**執行期輸出** ——
    ② 改名時這條會自己跟著改，不會變成下一個死指路
    （`ui/helpers/story_nav.py` 的 `RETIRED_TAB_LABELS` 記著三次前科）。
    """
    from ui.helpers.story_nav import where_to_find

    _ss = _FakeSessionState({_page._SK_IND: {}})
    _caps: list[str] = []
    with patch.dict("os.environ", {"FRED_API_KEY": "test-key"}), \
            patch.object(st, "session_state", _ss), \
            patch.object(st, "caption",
                         side_effect=lambda *a, **k: _caps.append(str(a[0]) if a else "")):
        _page.render_market_overview()

    _hits = [_c for _c in _caps if "逐檔加減碼" in _c]
    assert len(_hits) == 1, (
        f"指向 ② 的那句指路應恰好一句，實際 {len(_hits)} 句。"
        "（0 句 ＝ 被刪掉了；2 句以上 ＝ 有人抄了第二份）")
    assert where_to_find("health") in _hits[0], (
        f"指路沒有走 `where_to_find('health')` SSOT（期望含 "
        f"{where_to_find('health')!r}）：{_hits[0]!r}")
