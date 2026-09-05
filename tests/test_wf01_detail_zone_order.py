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


#: 五塊各自**該由哪一支函式渲染**。
#:
#: ⚠️ **2026-09-05 批次三-B：本條由「灰態清單」改成「接線清單」。**
#: ~~舊版是 `_expected_pending = {"long", "short", "inflection", "ai"}`，
#: 斷言那四塊**還是** `_detail_pending`（灰態佔位）。~~
#: 四塊搬真之後那份期望值只剩下 `set()`，而舊版 docstring 自己就寫過
#: 「**一條『什麼都沒斷言』的測試會一直是綠的**」—— 空集合正是那個形狀。
#: **有意識的改寫，不是漏刪**：斷言方向從「它們還是灰的」改成
#: 「**它們各自接到了自己那一支渲染器**」，強度是**上升**的：
#: 舊版只擋得住「灰態被換成別的東西」，新版連「A 塊被接到 B 塊的渲染器」
#: （畫面上兩塊長一樣、順序鎖照樣全綠）都擋得住。
#: ⚠️ **`_detail_pending` 本身沒有被刪**：它仍是每一塊「總經還沒載入」時的出口
#: （`_page._detail_not_loaded()` 會呼叫它那條路徑的等價灰態）。
_EXPECTED_RENDERERS: dict = {
    "long":                "_detail_long",
    "mid":                 "_detail_mid",
    "short":               "_detail_short",
    "inflection":          "_detail_inflection",
    _page._DETAIL_AI_KEY:  "_detail_ai",
}


def test_each_section_is_wired_to_its_own_renderer():
    """五塊各自接到自己那一支渲染器，**沒有任何一塊還是灰態佔位**。

    **突變會紅（每一種都實測過）**：
      - 把任一塊換回 `partial(_detail_pending, …)` → 本條紅（「退回佔位」）；
      - 把 `long` 接到 `_detail_short` → 本條紅（「兩塊共用一支」）；
      - 把某一支渲染器改名而忘了更新 `_DETAIL_RENDERERS` → 那一塊會 fall back 成
        `_detail_pending` → 本條紅。

    ⚠️ **期望值是函式名的字面值，不是從 `_DETAIL_RENDERERS` 取的** —— 同
    `_WIREFRAME_TITLES` 的理由：兩邊同源就會一起漂移。本檔前一版實測過那個坑
    （期望值與畫面同源 → 改名 8 passed 全綠）。
    """
    _got = {}
    for _k, _t, _r in _page._DETAIL_ZONE:
        _fn = getattr(_r, "func", _r)      # `partial` 剝殼
        _got[_k] = getattr(_fn, "__name__", repr(_fn))

    assert _got == _EXPECTED_RENDERERS, (
        "詳細區的接線變了。\n"
        f"  期望：{_EXPECTED_RENDERERS}\n  實際：{_got}\n"
        "⛔ **`_detail_pending` 出現在這裡 ＝ 那一塊退回灰態佔位了。**\n"
        "   若這是刻意的（例如某塊的服務層被下架），請連同本表一起改，"
        "並在 PR 描述寫明為什麼一塊已經上線的內容要退回去。")

    assert len(set(_got.values())) == len(_got), (
        f"有兩塊共用同一支渲染器：{_got} —— "
        "畫面上會出現兩塊一模一樣的內容，而順序鎖對此是全綠的。")


def test_no_section_falls_back_to_the_placeholder_renderer():
    """`_DETAIL_RENDERERS` 必須覆蓋 `_DETAIL_ZONE` 的每一個 key。

    ⚠️ 產品碼那邊刻意寫成 `_DETAIL_RENDERERS.get(_k) or partial(_detail_pending, …)`
    —— **沒登記的 key 退回灰態而不是 `KeyError`**，否則整頁會被 `app.py` 的
    分頁級 try 換成一個紅框。那個 fallback 是對的，但它會**靜默**吞掉一次漏登記，
    所以需要本條把它變成紅燈。
    """
    _zone_keys = [_k for _k, _t, _r in _page._DETAIL_ZONE]
    _missing = [_k for _k in _zone_keys if _k not in _page._DETAIL_RENDERERS]
    assert not _missing, (
        f"這幾塊沒有登記渲染器，會靜默退回灰態佔位：{_missing}")


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


# ══════════════════════════════════════════════════════════════
# 7) 內容鎖 —— 四塊「搬真」之後，各自真的畫得出東西
# ══════════════════════════════════════════════════════════════
# ⚠️ **為什麼接線鎖不夠**：接線鎖只驗「`_DETAIL_ZONE` 指到 `_detail_long`」。
#    把 `_detail_long()` 的**函式體掏空**（只留標題）之後，接線鎖、順序鎖、
#    字面值錨、故障隔離鎖**全部照樣綠** —— 畫面上那一塊會變成一個孤零零的標題。
#    本節就是為了讓「掏空」轉紅。
#
# ⚠️ **本節的斷言對象是「畫面上出現的字」，不是「呼叫了哪個函式」。**
#    斷言函式呼叫會讓實作換一個等價寫法就紅（假紅）；斷言畫面上的字才對得上
#    使用者真正會看到的東西。代價是**字被改寫時本節會紅** —— 那是刻意的：
#    這幾個字是線框點名的區塊名與服務層自己的欄位，改動應該被看見一次。
#
# ⚠️ **本節直接把 payload 塞進 session，不跑取數。** 理由：blocks 的契約就是
#    「從 session 讀 `_load_everything()` 放好的東西」。取數那一半由
#    :func:`test_the_loader_fills_every_detail_zone_payload` 單獨守 ——
#    **兩條缺一不可**：只有前者，刪掉 loader 那三段照樣綠（畫面永遠灰）；
#    只有後者，掏空 render 照樣綠（畫面永遠只剩標題）。

#: 側錄「畫面上出現的字」用的 API —— 比 `_RECORDED_APIS` 更寬（多了 `metric`
#: 與 `dataframe`），因為卡片的正常態走 `st.metric`、大表走 `st.dataframe`。
_TEXT_APIS: tuple[str, ...] = (
    *_RECORDED_APIS, "metric", "dataframe", "form_submit_button",
)


def _render_all_text(session: dict, *, gemini_keys: tuple = ("fake-key",)) -> str:
    """跑真的 `render_market_overview()`，把畫面上出現過的字全部串成一坨。

    `st.dataframe(df)` 的內容以 `df.to_string()` 併入 —— 否則大表裡的每一列
    （雷達 10 燈、原始讀數表）對本節是隱形的。
    """
    _ss = _FakeSessionState(session)
    _blob: list[str] = []

    def _make(_api: str):
        def _rec(_self, *a, **kw):
            for _x in (*a, *kw.values()):
                if isinstance(_x, str):
                    _blob.append(_x)
                elif hasattr(_x, "to_string"):
                    # ⚠️ **不是 `except: pass`**（§1）：側錄失敗會留下一個看得見的
                    #    標記，斷言因此會少掉那張表的指紋而轉紅 —— 側錄壞掉不得
                    #    偽裝成「那張表沒畫出來」以外的任何結果。
                    try:
                        _blob.append(_x.to_string())
                    except Exception as _rec_exc:   # noqa: BLE001 — 見上
                        _blob.append(f"<<側錄失敗 {type(_rec_exc).__name__}>>")
            return False                          # form_submit_button → 未送出
        return _rec

    def _bind(_fn):
        return lambda *a, **k: _fn(None, *a, **k)

    # 🤖 AI 總結的前置是「有沒有 Gemini 金鑰」。**在這裡給一把假的**，
    # 否則本節永遠只驗得到「沒金鑰 → 灰態」那一條路，AI 那一塊的內容鎖就是空的。
    with patch.dict("os.environ", {"FRED_API_KEY": "test-key"}), \
            patch.object(st, "session_state", _ss), \
            patch("ui.views.page_01_macro.get_gemini_keys",
                  return_value=list(gemini_keys)):
        with _ExitStack() as _stack:
            for _api in _TEXT_APIS:
                if hasattr(DeltaGenerator, _api):
                    _stack.enter_context(
                        patch.object(DeltaGenerator, _api, _make(_api)))
                if hasattr(st, _api):
                    _stack.enter_context(
                        patch.object(st, _api, _bind(_make(_api))))
            _page.render_market_overview()
    return "\n".join(_blob)


#: 一份「四塊都有料」的 session。**刻意用服務層真正的欄位名與形狀**
#: （逐一對照過 `services/us_liquidity_engine.py::fetch_us_liquidity_snapshot`、
#:  `services/risk_radar.py::_build`、`services/liquidity_engine.py`、
#:  `services/macro/turning_points.py::detect_turning_points` 的回傳），
#: 這樣「服務層改欄位名」也會在這裡轉紅，而不是在使用者面前變成一片灰。
def _loaded_session() -> dict:
    return {
        _page._SK_IND: {
            "SAHM":  {"name": "薩姆規則", "value": 0.63, "unit": "pp"},
            "SLOOS": {"name": "SLOOS 放貸標準", "value": 25.0, "unit": "%"},
            "ADL":   {"name": "市場廣度 RSP/SPY", "value": 0.2931,
                      "prev": -3.14, "unit": ""},
            "VIX":   {"name": "VIX 恐慌指數", "value": 24.1, "unit": ""},
        },
        _page._SK_USLIQ: {
            "hy_oas": {"value": 5.9, "unit": "%", "label": "🔴 信用緊縮 / 熱錢撤離",
                       "date": "2026-09-04", "source": "FRED:BAMLH0A0HYM2"},
            "m2_yoy": {"value": 3.2, "unit": "%", "label": "✅ 貨幣寬鬆",
                       "date": "2026-08-31", "source": "FRED:M2SL"},
            "aaii":   {"value": -24.5, "unit": "%", "label": "✅ 散戶過度悲觀（反指標：買訊號）",
                       "date": "2026-09-03", "source": "AAII:scrape:sentiment_spread"},
            "_provenance": {"sources": {}, "fetched_at": "", "orchestrator": "x"},
        },
        _page._SK_RADAR: {
            "vix_level": {"signal": "🔴 警報", "color": "#f00", "value": 31.2,
                          "prev": 24.1, "note": "VIX=31.2（單日 +29.5%）",
                          "label": "Yahoo ^VIX 日線", "trend": [22, 31]},
            "move_level": {"signal": "🟢 正常", "color": "#0f0", "value": 88.0,
                           "prev": 90.0, "note": "MOVE=88", "label": "CBOE MOVE",
                           "trend": [90, 88]},
        },
        _page._SK_LIQ: (
            {"XCCY_PROXY": {"value": 1.8, "unit": "σ", "label": "🔴 美元荒升溫",
                            "date": "2026-09-04", "source": "FRED:DTWEXBGS"}},
            {"value": 1.4, "tier": "警戒", "signal": "🟠", "color": "#ff6d00",
             "desc": "壓力升溫", "breakdown": {}},
        ),
        _page._SK_TP: {
            "yield_curve": {"signal": "⚠️ 衰退末期反彈", "value": 0.31, "prev": -0.05,
                            "label": "10Y − 2Y 利差 (T10Y2Y)",
                            "note": "近 60 日曾倒掛且已翻正", "source_ok": True},
            "sahm_rule": {"signal": "🔴 衰退觸發", "value": 0.63, "prev": 0.52,
                          "label": "薩姆規則 (SAHMREALTIME)",
                          "note": "0.63 ≥ 0.5", "source_ok": True},
        },
        _page._SK_AI: "### AI 逐段判讀\n這是一段已經生成好的 AI 總結內容。",
        _page._SK_PHASE: {"phase": "擴張中段", "score": 6},
        _page._SK_EV: {"summary": None, "score": 6.5, "prov": {},
                       "sufficient": True, "level": "樂觀"},
    }


#: 每一塊「真的畫出來了」的指紋。
#: 每一組都必須是**只有那一塊會印**的字 —— 否則掏空 A 塊時 B 塊會替它頂罪。
_BLOCK_FINGERPRINTS: dict = {
    "🌳 長期座標": (
        "💵 美股流動性",              # 塊內 H5 分節（線框 section 01 逐字）
        "M2 年增率",                  # `_US_LIQ_ROWS` 的卡片標題
        "HY 信用利差 OAS",
        "🔴 信用緊縮 / 熱錢撤離",     # 服務層自己的判讀句，原文印出
        "FRED:BAMLH0A0HYM2",          # 原始讀數表的來源欄（§2.2 血緣）
    ),
    "🎯 短線雷達": (
        "④ ⚡ 短線風險雷達",
        "⑤ 🌊 流動性壓力預警引擎",
        "VIX 絕對值 ＋ 日變化",        # `_RADAR_ROWS` 的顯示名
        "Yahoo ^VIX 日線",             # 10 燈表的「來源」欄
        "美元荒代理（跨幣別基差）",     # `_LIQ_FACTOR_ROWS` 的顯示名
        "警戒",                        # 壓力分數的 tier
    ),
    "⚠️ 拐點警報": (
        "① 🎯 全域導航塔",
        "薩姆規則 · 衰退機率",
        "市場廣度 · RSP／SPY",
        "② 🎯 拐點偵測中心",
        "10Y − 2Y 利差 (T10Y2Y)",      # 服務層自己的 `label`，本檔不另抄一份
    ),
    "🤖 AI 景氣判斷總結": (
        "這是一段已經生成好的 AI 總結內容。",
        "生成 AI 總結",                # 送出鈕（鐵則 02：生成也走 form）
    ),
}


@pytest.mark.parametrize("block", sorted(_BLOCK_FINGERPRINTS))
def test_each_block_renders_real_content_not_just_a_heading(block):
    """四塊各自畫得出**內容**，不是只有一個標題。

    **突變會紅（本輪逐塊實測，見 PR 描述的突變表）**：把任一塊的函式體掏空
    （只留 `_detail_title(...)`）→ **只有那一塊**的參數化案例紅，其餘三塊仍綠。
    """
    _blob = _render_all_text(_loaded_session())
    _missing = [_m for _m in _BLOCK_FINGERPRINTS[block] if _m not in _blob]
    assert not _missing, (
        f"「{block}」這一塊少了它應該畫出來的東西：{_missing}\n"
        "⛔ 若這是刻意改寫文案：請連同本表一起改，並確認畫面上真的還有等價的內容；\n"
        "   若這一塊被掏空／退回灰態：**那是回歸，不要改本表**。")


def test_a_block_with_nothing_to_show_goes_grey_and_says_where():
    """反面：四塊的服務層什麼都沒回來時，**一律灰態 ＋ 帶「去哪補」**。

    ⚠️ 這一條守的是客戶 2026-09-05 明示的「不接受假資料、不接受會影響判斷的
    缺資料」：沒有讀數時必須看得出「沒抓到」，**不得**留白、不得畫 0、
    也不得因為「沒有紅燈」就顯示成一切正常。

    **突變會紅**：把任一塊的空值分支改成 `st.caption("—")`（不帶 ⬜／不帶指路）
    → 本條紅。
    """
    from ui.helpers.render_state import NOT_READY_MARK
    from ui.helpers.story_nav import where_to_find

    # ⚠️ **`ind` 用空 dict，不是 `{"VIX": {"value": None}}`。**
    #    後者會在**服務層**炸掉（實測 2026-09-05：
    #    `services/macro/us_indicators.py::detect_systemic_risk` 寫的是
    #    `indicators.get("VIX", {}).get("value", 18) > _MB_VIX_YELLOW`
    #    —— key 在、值是 `None` 時預設值救不到，直接 `TypeError`）。
    #    那是**既有的服務層脆弱點**，依客戶方針第 2 條本批不反向修底層；
    #    此處據實登記並改用不會踩到它的輸入。**本條要驗的是 UI 的灰態，不是它。**
    _blob = _render_all_text({_page._SK_IND: {}})

    # 四塊的標題都還在（骨架不因為沒資料而消失 —— 鐵則 04）。
    for _t in _WIREFRAME_TITLES:
        assert _t in _blob, f"沒有資料時「{_t}」整塊消失了 —— 骨架不得跟著不見"
    assert NOT_READY_MARK in _blob, "沒有資料時畫面上一個 ⬜ 灰態都沒有"
    assert where_to_find("macro") in _blob, (
        "灰態沒有帶「去哪補」—— 線框 Rule 04 的三要素少了最有價值的那一項")


def test_the_loader_fills_every_detail_zone_payload():
    """`_load_everything()` 必須把四塊要用的 payload 都放進 session。

    ⚠️ **這是內容鎖的另一半。** 內容鎖直接把 payload 塞進 session，所以
    **把 loader 那三段刪掉，內容鎖照樣全綠**（實測）——
    畫面會永遠停在灰態，而沒有任何一條測試會響。本條補那個洞。

    ⚠️ 同時鎖住「**四塊掛在同一顆送出鈕底下**」：已拍板線框
    `fund-wireframe-final.html` 明文要把「載入流動性引擎」那顆
    「按鈕的按鈕」**併入主載入**。四個 payload 由同一次 `_load_everything()`
    產出，就是那句話的機器版本。
    """
    _ss = _FakeSessionState({})
    with patch.object(st, "session_state", _ss), \
            patch("ui.views.page_01_macro.fetch_all_indicators",
                  return_value={"VIX": {"value": 1}}), \
            patch("ui.views.page_01_macro.detect_risk_radar",
                  return_value={"vix_level": {"signal": "🟢"}}), \
            patch("ui.views.page_01_macro.fetch_hot_money_frames",
                  return_value=(None, None, "", "")), \
            patch("ui.views.page_01_macro.fetch_us_liquidity_snapshot",
                  return_value={"hy_oas": {"value": 5.0}}) as _usl, \
            patch("ui.views.page_01_macro.fetch_liquidity_factors",
                  return_value={"XCCY_PROXY": {"value": 1.0}}) as _lf, \
            patch("ui.views.page_01_macro.compute_liquidity_score",
                  return_value={"value": 1.0, "tier": "警戒"}), \
            patch("ui.views.page_01_macro.detect_turning_points",
                  return_value={"sahm_rule": {"source_ok": True}}) as _tp:
        _page._load_everything("test-key")

    assert _usl.called, "🌳 長期座標的取數沒有掛在主載入底下"
    assert _lf.called, "🎯 短線雷達 ⑤ 的取數沒有掛在主載入底下"
    assert _tp.called, "⚠️ 拐點警報 ② 的取數沒有掛在主載入底下"
    for _k, _what in ((_page._SK_USLIQ, "🌳 長期座標"),
                      (_page._SK_LIQ, "🎯 短線雷達 ⑤"),
                      (_page._SK_TP, "⚠️ 拐點警報 ②"),
                      (_page._SK_RADAR, "🎯 短線雷達 ④")):
        assert _k in _ss, f"{_what} 的 payload 沒有被寫進 session（鍵 {_k}）"

    # ⚠️ 10 燈存的必須是**原始 dict**，不是 `summarize_radar()` 的摘要 ——
    #    存摘要的話詳細區就得再抓一次（同一份資料兩個取數點，§2.1）。
    assert "vix_level" in _ss[_page._SK_RADAR], (
        "`_SK_RADAR` 又變回摘要了 —— 詳細區需要原始 10 燈")


def test_an_all_grey_radar_is_never_reported_as_calm():
    """10 燈全部抓不到時，**不得**顯示成「平靜」。

    ⚠️ **這是實測出來的服務層行為，不是假想**（2026-09-05 於無網路環境實跑）：
    `summarize_radar({10 盞全 ⬜})` 回的是 `level="平靜"`、`color` 是綠的 ——
    因為它的分級只看 `red` / `yellow` 兩個計數。
    照搬那個結果會把「什麼都沒抓到」畫成「市場很平靜」，
    也就是 `_worst_state()` 已經寫過的那句：**沒有資料不等於一切正常**（§1）。

    服務層**不改**（客戶方針第 2 條：不反向修底層），在消費端擋。
    本條同時守卡片（層 1）與詳細區（層 4）兩個消費端。

    **突變會紅**：把 `_card_risk_radar()` 或 `_detail_short()` 的
    `if not _lit:` 那段拿掉 → 本條紅。
    """
    from services.risk_radar import summarize_radar as _sr

    _all_grey = {f"sig{_i}": {"signal": "⬜ 無資料", "value": None,
                              "prev": None, "note": "來源暫時無法取得",
                              "label": "—", "trend": []} for _i in range(10)}
    # 前提複驗：服務層今天真的還會說「平靜」。前提沒了本條就該重寫，不是靜靜變綠。
    assert _sr(_all_grey).get("level") == "平靜", (
        "前提變了：`summarize_radar()` 對全 ⬜ 已經不回「平靜」了 —— "
        "本條的理由消失，請重新確認消費端那道防線還需不需要")

    _sess = _loaded_session()
    _sess[_page._SK_RADAR] = _all_grey
    _blob = _render_all_text(_sess)
    assert "平靜" not in _blob, (
        "10 燈全部沒抓到，畫面上卻出現「平靜」—— "
        "那是把『沒有資料』畫成『一切正常』（§1）")
