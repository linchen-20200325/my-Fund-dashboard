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

五種鎖，各守一個不同的失效模式（每一種都有實測過的突變）
--------------------------------------------------------
- **結構鎖** :func:`test_detail_zone_keys_are_derived_from_bucket_order`
  —— 順序的唯一出處是 `BUCKET_ORDER`，本檔與產品碼都不手抄第二份。
- **行為鎖** :func:`test_detail_zone_renders_its_five_sections_in_order_and_contiguous`
  —— 錄下**真的渲染出來的**一級標題序列。抓得到「序列長得很正確、
  但根本沒有人呼叫它」與「中間插了別的一級區塊」。
- **接線鎖** :func:`test_the_mid_cycle_block_really_delegates_to_the_shared_renderer`
  —— 防「真區塊被悄悄換回灰態佔位卡」而其他鎖照樣綠。
- **字面值錨** :func:`test_detail_section_titles_match_the_wireframe_literals`
  —— 五塊的名字對線框字面值，防「期望值與畫面同源、一起改名」。
- **故障隔離鎖** :func:`test_one_failing_block_does_not_take_down_the_rest_of_the_zone`
  —— 一塊爆炸不得帶走其餘四塊與那句指路。

⚠️ **為什麼行為鎖不可省（結構鎖擋不住的那一半）**：
   `_DETAIL_ZONE` 是一個 module-level tuple。**一個沒有被呼叫的序列，
   同樣可以長得完全正確** —— 把 `_render_detail_zone()` 整句從
   `_render_deferred_blocks()` 刪掉，結構鎖仍然全綠。

⚠️ **為什麼字面值錨不可省（其餘各鎖擋不住的那一半）**：
   其餘各鎖刻意**從產品碼推導期望值**（不抄第二份順序），代價是
   **全部同源 ＝ 一起漂移**。2026-09-05 稽核實測：改掉一個灰態區塊的名字
   → 當時全部 8 條**照樣綠**。名字這一項因此必須有一根不動的樁。

⚠️ **本檔守得到什麼、守不到什麼**：詳見 :func:`_render_and_record` 的
   那兩份 bullet。**本檔不宣稱「所有插入一級區塊的寫法都擋得住」** ——
   ~~只宣稱下列五種實測擋得住~~ → **2026-09-05 A779-b：清單已由 5 種擴為 13 種**
   （新增 `st.title` 是原本**低估**自己；`info`/`success`/`warning`/`error`/
   `caption`/`html` 六種是原本**漏掉**、當時各 10 passed 全綠，同輪補進字表）。
   **真正的界線是 `_RECORDED_APIS` 那份字表**，不是「有沒有經過 DeltaGenerator」。
"""
from __future__ import annotations

import re
from contextlib import ExitStack as _ExitStack
from unittest.mock import patch

import pytest
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from shared.macro_buckets import BUCKET_ORDER

import ui.views.page_01_macro as _page

#: markdown 形式的一級區塊標題 = H2~H4。
#: ⚠️ **刻意不含 H5** —— `ui/tab1_macro_midcycle.py` 的
#: `##### 🧭 L3 情境判斷` 是**中期循環自己的子標題**，不是一個平行的一級區塊；
#: 把它算進來會讓「連續」永遠不成立。
_OPENER_RE = re.compile(r"^#{2,4}\s")

#: 要側錄的渲染 API。**在 `DeltaGenerator` 類別上攔截，不是在 `streamlit` 模組上。**
#:
#: ⚠️ **這一行是 2026-09-05 稽核打穿本檔之後改的，理由必須留著**：
#: 本檔前一版用 `patch.object(st, "markdown")`，只攔得到 **module-level** 的
#: `st.markdown`。獨立稽核拿**同一個**「在五塊中間插一個外來一級區塊」的突變，
#: 只換拼法就全部繞過（每一種都實測過）：
#:
#:   | 寫法 | 前一版 | 現在 |
#:   |---|---|---|
#:   | `st.markdown("### …")`   | 2 failed ✅ | 紅 ✅ |
#:   | `st.subheader("…")`      | **8 passed ⛔** | 紅 ✅ |
#:   | `st.header("…")`         | **8 passed ⛔** | 紅 ✅ |
#:   | `st.write("### …")`      | **8 passed ⛔** | 紅 ✅ |
#:   | `col.markdown("### …")`  | **8 passed ⛔** | 紅 ✅ |
#:
#: **後三種不是刁鑽寫法**：`subheader`/`header` 是 Streamlit 標準 API；
#: **欄位控制代碼（`col.markdown`）在本 repo `ui/` 底下已有多處在用**，
#: 而 📈 中期循環那些指標卡自己就是走這條路 —— 也就是說，
#: **前一版對這個 repo 的主流寫法是盲的。**
#:
#: **兩層都要攔，只攔一層會漏掉一半 —— 這一點是本輪實測出來的，不是推論：**
#:
#:   ```
#:   with patch.object(DeltaGenerator, "markdown", rec):
#:       st.markdown("via-st-module")          # ← 錄不到
#:       st.columns(1)[0].markdown("via-col")  # ← 錄得到
#:   # 實際輸出：[('CLASS', 'via-column-handle')]
#:   ```
#:
#: 原因：`st.markdown` 是 **import 時就綁好的 bound method**
#: （`type(st.markdown).__name__ == "method"`、有 `__self__`）——
#: 那個 method 物件抓住的是**當時**的函式，事後換掉類別屬性影響不到它；
#: 反過來，容器控制代碼是**呼叫當下**才做屬性查找，所以只吃類別那一層。
#: → 故本檔 `patch.object(DeltaGenerator, api, …)` **與**
#:   `patch.object(st, api, …)` **兩個都下**。
_RECORDED_APIS: tuple[str, ...] = (
    "markdown", "write", "subheader", "header", "title",
    # 2026-09-05 A779-b 擴充：這六個原本整組漏掉（各 10 passed 全綠）。
    "info", "success", "warning", "error", "caption", "html",
)

#: 這幾個 API 只要被呼叫就是一級區塊標題（它們本身就是標題元件，沒有 `#` 前綴可比對）。
#: ⚠️ **`_RECORDED_APIS` 與本集合是兩件事，不要混為一談**：
#: 進 `_RECORDED_APIS` 只代表「這個 API 會被錄下來」；**只有**進本集合的才會
#: 「一被呼叫就算成區塊開頭」。其餘被錄下來的（`markdown` / `write` / `info` /
#: `caption` …）**還要文字本身長得像標題**才算 —— 所以
#: `st.caption("資料源　FRED ＋ FinMind。")` 這種**不會**被誤認成一級區塊。
_ALWAYS_OPENER: frozenset = frozenset({"subheader", "header", "title"})

#: HTML 形式的一級標題（`st.html("<h2>…</h2>")`、或 `unsafe_allow_html` 的 `<h2>`）。
#: ⚠️ **2026-09-05 A779-b：這一條是實測逼出來的，不是預先設計的。**
#: 把 `html` 加進 `_RECORDED_APIS` **之後它仍然逃掉**（`10 passed`）——
#: 因為它的內容是 `<h2>…`，**不長得像 `## `**，`_OPENER_RE` 對它無效。
#: 「加進字表就擋得住」這個推論**對 `st.html` 不成立**，故另立一條樣式。
#: 誤紅風險已實測：整頁跑完（兩種載入狀態）符合本樣式的呼叫 **各 0 次**。
_HTML_OPENER_RE = re.compile(r"^\s*<h[1-6][^>]*>(.*?)</h[1-6]\s*>", re.IGNORECASE | re.DOTALL)

#: 認出「指向 ② 的那句指路」用的關鍵詞。
#:
#: ⚠️ **刻意是測試檔裡的字面值，不是從產品碼 import 過來的** —— 同 `_WIREFRAME_TITLES`
#: 的理由：兩邊同源就一起漂移。文案若真的改寫到不含這幾個字，本條**應該**紅一次，
#: 讓人回來確認「那句指路還在不在」，而不是靜靜地跟著改。
#: （2026-09-05 實測：把「已搬到」改成中性時態「請到」時，本標記就擋下來過一次。）
_SIGNPOST_MARK: str = "加減碼建議"


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

    ⚠️ **攔截點是 `DeltaGenerator` 類別方法**（見 `_RECORDED_APIS` 的說明）——
    這樣 `st.markdown(...)`、`st.subheader(...)`、`col.markdown(...)`
    走的都是同一個被攔下來的函式。

    ⚠️ **界線在哪：`_RECORDED_APIS` 那份字表，不是 patch 的層數。**

    ~~舊表述第三條寫「完全不經 `DeltaGenerator` 的渲染路徑（若日後出現）」~~
    → **2026-09-05 A779-b 就地更正（有意識的更正，不是漏刪）：那個心智模型是錯的。**
    **實測**：`st.info` / `st.success` / `st.warning` / `st.error` / `st.caption` /
    `st.html` **六個全都是 `DeltaGenerator` 方法**（`hasattr(DeltaGenerator, n)` 逐一為 True），
    卻在補進字表之前**六種各 10 passed 全綠**。
    → 也就是說：**漏掉它們與「經不經過 DeltaGenerator」無關，純粹是字表沒列。**
    舊表述會讓後人以為「只要它走 DeltaGenerator 就被蓋到了」——**那是假的安全感。**

    **實測擋得住（每一項都各自跑過一次突變，各 2 failed）**：
      `st.markdown` / `st.write` / `st.subheader` / `st.header` / `st.title` /
      `st.info` / `st.success` / `st.warning` / `st.error` / `st.caption` /
      `st.html`（`<h2>…</h2>`）/ `st.markdown(..., unsafe_allow_html=True)` 的 `<h2>`，
      以及**容器控制代碼**形式（`col.markdown("### …")`）。

    ⚠️ **仍然看不到的（誠實列出，不要讀成「已經全包」）**：
      - **任何不在 `_RECORDED_APIS` 裡的渲染 API** —— 這是本錄影機唯一的真界線。
        新增一個沒列進去的 API，本鎖就對它是盲的。
      - `st.expander("…")` **刻意不算**一級區塊 —— 📈 中期循環自己就有一個
        （Z-Score 完整矩陣），算進去會讓「連續」永遠不成立。**這是取捨，不是疏漏。**
      - 被錄下來、但**文字既不像 `## ` 也不像 `<h2>`** 的假標題
        （例如用 `<div style="font-size:32px">` 假裝標題）——
        錄得到那段字串，但不會被認成區塊開頭。
    """
    _ss = _FakeSessionState({_page._SK_IND: {}} if loaded else {})
    _seen: list[tuple[str, str]] = []

    def _make(_api: str):
        """類別方法版：第一個參數是 `self`（容器控制代碼）。"""
        def _rec(_self, *a, **_kw):
            _txt = a[0] if a and isinstance(a[0], str) else ""
            _seen.append((_api, _txt))
        return _rec

    def _bind(_fn):
        """模組層版：`st.markdown(...)` 不帶 `self`，包一層把它補掉。"""
        return lambda *a, **k: _fn(None, *a, **k)

    with patch.dict("os.environ", {"FRED_API_KEY": "test-key"}), \
            patch.object(st, "session_state", _ss):
        with _ExitStack() as _stack:
            for _api in _RECORDED_APIS:
                # 兩層都要攔，缺一漏一半（理由見 `_RECORDED_APIS` 下方的「兩層」段）。
                _stack.enter_context(
                    patch.object(DeltaGenerator, _api, _make(_api)))
                _stack.enter_context(
                    patch.object(st, _api, _bind(_make(_api))))
            _page.render_market_overview()

    _out: list[str] = []
    for _api, _txt in _seen:
        if _api in _ALWAYS_OPENER:
            _out.append(_txt.strip())
        elif _OPENER_RE.match(_txt):
            _out.append(_OPENER_RE.sub("", _txt).strip())
        else:
            _m = _HTML_OPENER_RE.match(_txt)
            if _m:
                _out.append(re.sub(r"<[^>]+>", "", _m.group(1)).strip())
    return _out


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
      (b) 五塊之間**沒有夾別的一級區塊** —— ⚠️ **這句要照「受限版本」讀**：
          本條只擋得住 :data:`_RECORDED_APIS` 字表涵蓋的那些渲染 API
          （逐一實測過的清單見 :func:`_render_and_record` 的兩份 bullet）。
          ~~不是「任何寫法都擋得住」~~ —— **2026-09-05 A779-b 就地更正
          （有意識的更正，不是漏刪）**：稽核用 `st.info` / `st.success` /
          `st.warning` / `st.error` / `st.caption` / `st.html` 六種寫法，
          當時**各 10 passed 全綠**。六種已於同輪補進字表（`st.html` 另需
          `_HTML_OPENER_RE`，見該處），但**字表以外的寫法本條依然看不到**。
          ⚠️ 這句話在 PR 描述裡撤回過、**在這裡沒有撤** —— 而這裡是那條行為鎖
          **自己的 docstring**，是後人最會拿來當前提的地方。本輪補上；
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
        "⛔ **先確認這一塊是不是線框 section 03 那五塊之一**"
        "（`_WIREFRAME_TITLES`）——\n"
        "   是：把它從本條的 `_expected_pending` 移除即可（它被搬真了，正常）。\n"
        "   否：**不要改本條的期望值** —— 那會讓一個未經客戶拍板的新區塊直接上畫面。\n"
        "       線框沒有的區塊要先走 UI 草稿先行，拍板後才動 `_DETAIL_ZONE`。")


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

    _hits = [_c for _c in _caps if _SIGNPOST_MARK in _c]
    assert len(_hits) == 1, (
        f"指向 ② 的那句指路應恰好一句，實際 {len(_hits)} 句。"
        "（0 句 ＝ 被刪掉了；2 句以上 ＝ 有人抄了第二份）")
    assert where_to_find("health") in _hits[0], (
        f"指路沒有走 `where_to_find('health')` SSOT（期望含 "
        f"{where_to_find('health')!r}）：{_hits[0]!r}")


# ══════════════════════════════════════════════════════════════
# 5) 字面值錨 —— 五塊的名字不得同源漂移
# ══════════════════════════════════════════════════════════════
#: 五塊標題的**字面值**，逐字取自已拍板線框
#: `docs/wireframes/wireframe-macro-health.html` **section 03「重組後版面」**的
#: 「🔎 詳細資料與說明〈保留 · 順序不動〉」那一行，
#: 且與**舊頁各子模組實際渲染的 `## ` 標題逐字相同**
#: （`ui/tab1_macro_longterm.py` / `_midcycle.py` / `_radar.py` /
#:  `_inflection.py` / `_ai.py`）。
#:
#: ⚠️ **為什麼一定要有這份字面值（2026-09-05 稽核指出，本檔實測確認）**：
#: 本檔前一版的期望值是 `_DETAIL_TITLES`，而畫面上的字**也是** `_DETAIL_TITLES`
#: —— **兩邊同源，一起動就一起錯**。實測：把 `_DETAIL_TITLES["long"]` 改成
#: 任意名字 → **8 passed，一條都沒響**。
#:
#: ⛔ **這正是本 PR 自己在修的那一類錯**：區塊名一度被改成自創的「詳細五時域」，
#: 而九份線框對它 0 命中。**沒有字面值錨，那個錯可以在這四塊上原封再犯一次。**

_WIREFRAME_TITLES: tuple[str, ...] = (
    "🌳 長期座標",
    "📈 中期循環",
    "🎯 短線雷達",
    "⚠️ 拐點警報",
    "🤖 AI 景氣判斷總結",
)


def test_detail_section_titles_match_the_wireframe_literals():
    """五塊標題必須逐字等於線框 section 03 的名字。

    **突變會紅**：把 `_DETAIL_TITLES` 任一個值改名 → 本條紅
    （前一版的守衛對這個突變 8 passed 全綠）。

    ⚠️ 本條是**唯一**不從產品碼推導期望值的一條 —— 它就是那根樁。
    其餘各條刻意從 `_DETAIL_ZONE` / `BUCKET_ORDER` 推導（不抄第二份順序），
    但**全部推導 ＝ 全部同源 ＝ 一起漂移**，所以名字這一項必須有字面值。
    """
    _got = tuple(_t for _k, _t, _r in _page._DETAIL_ZONE)
    assert _got == _WIREFRAME_TITLES, (
        "詳細區的區塊名與線框 section 03 對不上。\n"
        f"  線框：{list(_WIREFRAME_TITLES)}\n  實際：{list(_got)}\n"
        "若這是客戶重新拍板改名：請連同線框一起改，並在此更新字面值。")


# ══════════════════════════════════════════════════════════════
# 6) 故障隔離鎖 —— 一塊爆炸不得帶走其餘四塊與那句指路
# ══════════════════════════════════════════════════════════════
def test_one_failing_block_does_not_take_down_the_rest_of_the_zone():
    """任一塊拋例外時：**例外不外逃、其餘各塊照畫、指路仍在**。

    ⛔ **2026-09-05 稽核實測，前一版是真的會斷頭**（不是假想情境）：
    `_detail_mid()` 當時是裸呼叫、一路無 try/except，最近的網子是 `app.py`
    的**分頁級** try。讓 `render_mid_cycle_section` 拋例外的結果是 ——
    例外逃出 `render_market_overview`，**🎯 短線雷達 / ⚠️ 拐點警報 /
    🤖 AI 總結三塊全部消失，連那句指路也一起沒了**。

    ⚠️ 上游 `ind` 形狀變動是**會真的發生**的事（本頁不擁有 `fetch_all_indicators`
    的回傳形狀），所以這條走的是「已知會發生」而不是「防禦性加固」。

    ⚠️ 本條**同時**是那句指路的第二道保險：它自己那條守衛
    （:func:`test_the_decision_matrix_signpost_survives_and_uses_the_ssot`）
    只驗「正常路徑上它在」，**驗不到「有人爆炸時它還在不在」**。
    """
    _ss = _FakeSessionState({_page._SK_IND: {}})
    _seen: list[str] = []
    _caps: list[str] = []

    def _boom(*_a, **_kw):
        raise RuntimeError("模擬上游 ind 形狀變動")

    _escaped = None
    with patch.dict("os.environ", {"FRED_API_KEY": "test-key"}), \
            patch.object(st, "session_state", _ss), \
            patch.object(st, "markdown",
                         side_effect=lambda *a, **k: _seen.append(str(a[0]) if a else "")), \
            patch.object(st, "caption",
                         side_effect=lambda *a, **k: _caps.append(str(a[0]) if a else "")), \
            patch("ui.tab1_macro_midcycle.render_mid_cycle_section", side_effect=_boom):
        try:
            _page.render_market_overview()
        except Exception as _e:            # noqa: BLE001 — 這裡就是要抓「有沒有逃出來」
            _escaped = _e

    assert _escaped is None, (
        f"某一塊的例外逃出了 `render_market_overview()`：{_escaped!r} —— "
        "區塊級隔離沒了，整頁會被 app.py 的分頁級 try 換成一個紅框")

    _blob = "\n".join(_seen)
    for _title in ("🎯 短線雷達", "⚠️ 拐點警報", "🤖 AI 景氣判斷總結"):
        assert _title in _blob, (
            f"📈 中期循環爆炸後，排在它後面的「{_title}」沒有畫出來 —— 斷頭了")

    assert any(_SIGNPOST_MARK in _c for _c in _caps), (
        "📈 中期循環爆炸後，指向 ② 的那句指路消失了 —— "
        "它是整批搬移裡唯一留給使用者的線索，不得被別的區塊的故障帶走")
