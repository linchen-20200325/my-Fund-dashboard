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


def _render_parts(session: dict, *, gemini_keys: tuple = ("fake-key",)) -> list:
    """跑真的 `render_market_overview()`，回傳畫面上出現過的字（**有序**）。

    `st.dataframe(df)` 的內容以 `df.to_string()` 併入 —— 否則大表裡的每一列
    （雷達 10 燈、原始讀數表）對本節是隱形的。

    ⚠️ **2026-09-05 稽核 F2：回傳「有序清單」而不是一坨字串，是被迫改的。**
    前一版回傳 `"\n".join(...)`，於是所有斷言都變成**整頁全域存在性檢查**
    （「畫面上某處有 ⬜」），而**單一塊的誠實度完全沒被守到** ——
    只要任何一塊還有 ⬜，其餘四塊被改成 `st.caption("—")`
    甚至 `st.success("✅ …一切正常")` 都照樣全綠（稽核實跑證明）。
    有序清單才切得出「哪一段字是哪一塊印的」，見 :func:`_render_segments`。
    """
    _ss = _FakeSessionState(session)
    _blob: list[str] = []

    def _make(_api: str):
        def _rec(_self, *a, **kw):
            if _api == "metric" and a and isinstance(a[0], str):
                # ⛔ **合格態的卡片走 `st.metric`，畫面上沒有任何可切段的標記。**
                #    灰態卡走 `st.markdown(f"**{title}**")`（有標記），
                #    於是「三張卡裡把**中間那張**換成捏造的合格態」時，
                #    那張卡的字會併進**前一張**的單位 —— 而前一張還有 ⬜ → 不紅。
                #    實測（2026-09-05，補這行之前）：捏造第 1 張 `1 failed`、
                #    **捏造第 2 張 `21 passed`**。
                #    這裡補一個側錄專用的分段標記，讓每一張 metric 卡自成一個單位。
                _blob.append(f"{_METRIC_MARK}{a[0]}")
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
    return _blob


def _render_all_text(session: dict, **kw) -> str:
    """:func:`_render_parts` 的整頁串接版（給「整頁至少要有某某」那類斷言用）。

    ⚠️ **不要拿它做「某一塊有沒有 ⬜」的斷言** —— 那正是稽核 F2 打穿的形狀。
    逐塊的斷言一律走 :func:`_render_segments`。
    """
    return "\n".join(_render_parts(session, **kw))


#: 一級標題的樣式（H2~H5 都收）—— 切段用，不是本檔別處那個 `_OPENER_RE`。
#: ⚠️ **這裡要收 H2**：📈 中期循環的標題是由 `ui/tab1_macro_midcycle.py` 自己印的
#: `## 📈 中期循環`（比其餘四塊高兩級）。不收 H2 的話，中期循環那一整段內容
#: 會被算進**它前面那一塊**（🌳 長期座標）的段落裡，讓 F2 的逐塊斷言失真。
_SEG_OPEN_RE = re.compile(r"^#{2,5}\s+(.*)$")


def _render_segments(session: dict, **kw) -> dict:
    """把畫面切成「**每一塊各自印了哪些字**」。

    切點是五塊的標題本身（不論它用第幾級標題，見 :data:`_SEG_OPEN_RE`）。
    區頭 `### 🔎 詳細資料與說明` 之前的東西不屬於任何一塊，直接丟掉。

    ⛔ **最後一塊的段落必須有下界，否則本函式會說謊。**
    🤖 AI 總結是詳細區的最後一塊，它後面緊接著 `_render_matrix_signpost()`
    與 `_render_deferred_blocks()` 的「總經燈號全表」空狀態 —— 而**那個空狀態
    自己就帶著 ⬜ 與「（請先到：」**。沒有下界的話，AI 那一塊會**無條件繼承**
    它們，於是「AI 塊有沒有自己的灰態」這個問題永遠答 True。
    ⚠️ **這不是假想** —— 本組把 AI 的灰態換成 `st.success("✅ 資料狀況良好…")`
    做自驗突變，**第一版切段器回報 21 passed**（應該紅）。下界是那一次抓出來的。
    收尾用 `_SIGNPOST_MARK`：`_render_detail_zone()` 的迴圈跑完，
    **下一句就是那條指路**，所以它正好是詳細區的結束標記。
    """
    _segs: dict = {}
    _cur = None
    for _p in _render_parts(session, **kw):
        if not isinstance(_p, str):
            continue
        if _cur is not None and _SIGNPOST_MARK in _p:
            _cur = None                      # 詳細區到此為止（見上方 ⛔）
            continue
        _m = _SEG_OPEN_RE.match(_p)
        _title = _m.group(1).strip() if _m else None
        if _title in _WIREFRAME_TITLES:
            _cur = _title
            _segs[_cur] = []
        elif _cur is not None:
            _segs[_cur].append(_p)
    return {_k: "\n".join(_v) for _k, _v in _segs.items()}


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


#: 塊內小節（`#####`）的樣式。**刻意只收 H5** —— 塊標題是 H4（📈 中期循環是 H2），
#: 收到它們會讓「塊」和「小節」變成同一層。
_SUB_OPEN_RE = re.compile(r"^#{5}\s+(.*)$")

#: **卡片**的標題。`ui/helpers/ia/cards.py::state_card()` 的灰態分支印的就是
#: `st.markdown(f"**{title}**")`，所以整行剛好是一個粗體標題。
#: ⚠️ 這一層是 2026-09-05 稽核 R3 逼出來的，見 :func:`_grey_units` 的 ⛔。
_CARD_OPEN_RE = re.compile(r"^\*\*(.+)\*\*$")

#: 側錄器替 `st.metric` 補的分段標記（**只存在於側錄結果，不是畫面上的字**）。
#: 理由見 `_render_parts()` 內 `_api == "metric"` 那段 ⛔：
#: 合格態的卡片沒有任何可切段的標記，不補的話「中間那張被捏造」抓不到。
_METRIC_MARK: str = "\u27e6metric\u27e7"


def _grey_units(block: str, seg: str) -> list:
    """把一塊切成「要各自驗灰態的**最小**單位」：小節（`#####`）**再切到卡片**（`**標題**`）。

    回傳 `[(給人看的標籤, 那一段的字), ...]`；**空白段落自動略過**
    （例如 🌳 長期座標在無資料時根本還沒印到 `#####`，那就只有一段）。

    ⛔ **2026-09-05 稽核 R3：只切到「小節」是不夠的，而且今天就能被觸發。**
    ~~上一版只切到 `#####`，並在呼叫端 docstring 寫「同一個小節裡有兩份以上灰態
    …**今天沒有這種小節**」~~ —— **那句話是假的**。
    ⚠️ 拐點警報的 `##### ① 🎯 全域導航塔` **一個小節裡就有三張卡**
    （薩姆／SLOOS／市場廣度）。稽核實跑：把薩姆那張換成捏造的
    `0.00 / ✅ 未觸發衰退門檻，勞動市場正常。`、另兩張維持誠實 ⬜
    → **683 passed，零紅燈**。也就是在**完全沒有資料**的情況下畫出
    「衰退機率 0.00、勞動市場正常」，而守衛全綠 —— 那是客戶明示的紅線。
    **它不是「下一個人可能寫出來」，是現在的形狀。**
    → 故本函式再往下切一層到**每一張卡**。

    ⚠️ **一個已被證偽卻留在永久記錄裡的限定詞，比沒有那句話更危險** ——
    「今天沒有這種小節」正是總管用來判斷「要不要現在補」的那句話。
    本輪把它換成實測結果（見呼叫端 docstring）。
    """
    _units: list = []
    # ⚠️ **小節與卡片分開記，不要從 `_cur_label` 續接**（2026-09-05 稽核第 2 項）。
    #    上一版做 `_cur_label.split("的小節", 1)` 去撈「目前在哪個小節」，
    #    但那時的 `_cur_label` **已經含上一張卡的後綴** → 標籤逐張累積：
    #      第 2 張 → …的卡片「薩姆規則…」的卡片「SLOOS…」
    #      第 3 張 → …的卡片「薩姆規則…」的卡片「SLOOS…」的卡片「市場廣度…」
    #    也就是第 N 張會**宣稱它巢狀在前 N−1 張裡面** —— 那是假的。
    #    （最後一個名字仍是對的，所以斷言訊息還指得動；但它與本函式自己寫的意圖
    #      「訊息才指得出哪一小節的哪一張卡」不符。）
    _sec_label = ""                      # 目前所在小節（不含卡片）
    _cur_label, _cur = f"「{block}」", []

    def _flush() -> None:
        if any(_x.strip() for _x in _cur):
            _units.append((_cur_label, "\n".join(_cur)))

    for _ln in seg.split("\n"):
        _m_sub = _SUB_OPEN_RE.match(_ln)
        if _m_sub:
            _flush()
            _sec_label = f"的小節「{_m_sub.group(1).strip()}」"
            _cur_label, _cur = f"「{block}」{_sec_label}", []
            continue
        _m_card = _CARD_OPEN_RE.match(_ln)
        if _ln.startswith(_METRIC_MARK):
            # 合格態卡片：用側錄器補的標記切段（見 `_METRIC_MARK`）。
            _m_card = re.match(r"(.+)$", _ln[len(_METRIC_MARK):])
        if _m_card:
            _flush()
            # 卡片標籤 ＝ 塊 ＋ **當下所屬小節** ＋ 這一張卡；不從上一張卡續接。
            _cur_label = (f"「{block}」{_sec_label}"
                          f"的卡片「{_m_card.group(1).strip()}」")
            _cur = []
            continue
        _cur.append(_ln)
    _flush()
    return _units


#: 逐塊灰態斷言的對象。
#:
#: ⚠️ **📈 中期循環刻意不在內** —— 它是**委派**給 `ui/tab1_macro_midcycle.py`
#: 的既有實作，那個檔不在本批的檔案邊界內（客戶方針第 1 條：不在舊 tab 上修補）。
#: 對一個本批管不到的模組斷言它的灰態文案，只會產生一條**改不動的紅燈**。
#: 它的骨架仍由下方 `_WIREFRAME_TITLES` 那一圈斷言守著（標題不得消失）。
_GREY_BLOCKS: tuple = ("🌳 長期座標", "🎯 短線雷達", "⚠️ 拐點警報",
                       "🤖 AI 景氣判斷總結")


def test_a_block_with_nothing_to_show_goes_grey_and_says_where():
    """反面：**每一塊各自**在服務層什麼都沒回來時，都要灰態 ＋ 帶「去哪補」。

    ⚠️ 這一條守的是客戶 2026-09-05 明示的「不接受假資料、不接受會影響判斷的
    缺資料」：沒有讀數時必須看得出「沒抓到」，**不得**留白、不得畫 0、
    也不得因為「沒有紅燈」就顯示成一切正常。

    ⚠️ **2026-09-05 稽核 F2：本條前一版的斷言是假的，而且它的 docstring
    保證了一個實測不成立的突變結果。** ~~舊版寫「**突變會紅**：把任一塊的空值分支
    改成 `st.caption("—")` → 本條紅」~~ —— **實跑是 18 passed，不紅。**
    原因：舊版兩條斷言都是**整頁全域存在性檢查**
    （`assert NOT_READY_MARK in _blob` / `assert where_to_find("macro") in _blob`），
    而 `_blob` 是整頁的字。**只要任何一塊還有 ⬜，其餘四塊被改掉都照樣綠。**
    稽核用兩個突變打穿它，兩次都全綠：
      - 🌳 長期座標的灰態換成 `st.caption("—")` → `18 passed`
      - 換成 `st.success("✅ 美股流動性、信用與情緒均在正常區間，無異常。")`
        → 本檔 18 passed、`test_batch2` ＋ `test_render_state_color_separation`
        合計 **662 passed** —— **把「沒抓到」畫成「一切正常」，零紅燈。**

    **現行做法**：走 :func:`_render_segments` 逐塊切段、再走 :func:`_grey_units`
    切到**塊內每一個 `#####` 小節**，逐單位斷言。

    **突變會紅（本輪逐項實跑，輸出照抄自 PR 描述）**：

    ====================== ================================================
    突變                     結果
    ====================== ================================================
    🌳 長期座標 → `st.caption("—")`   `1 failed`（舊版：`18 passed`）
    🌳 長期座標 → `st.success(…)`     `1 failed`（舊版：`682 passed` 全綠）
    🎯 短線雷達 ④ → `st.success(…)`   `1 failed`，指名小節「④ ⚡ 短線風險雷達」
    ⚠️ 拐點警報 ② → `st.success(…)`   `1 failed`，指名小節「② 🎯 拐點偵測中心」
    🤖 AI 總結 → `st.success(…)`      `1 failed`
    ====================== ================================================

    ⚠️ **切到小節這一層，是本組自驗時被自己的突變逼出來的，不是一開始就有的。**
    只驗到「塊」的那一版：🎯 短線雷達與 ⚠️ 拐點警報**各自有兩個小節、兩份灰態**，
    拔掉其中一個另一個還在 → **兩者都是 `21 passed`**。
    ⚠️ 同一輪還抓到切段器自己的洞：🤖 AI 是最後一塊，沒有下界時它會**繼承**
    後面「總經燈號全表」空狀態的 ⬜ → 拔掉它自己的灰態也不紅（見 :func:`_render_segments`）。

    ⛔ **仍然守不到的（誠實列出，不要讀成「已經全包」）**：
      - ~~**同一個小節裡有兩份以上灰態時，拔掉其中一份**仍不會紅……
        今天沒有這種小節，但沒有任何東西阻止下一個人寫出來。~~
        → **2026-09-05 稽核 R3：那句話是假的，而且今天就能觸發。**
        `##### ① 🎯 全域導航塔` **一個小節裡就有三張卡**；稽核只捏造其中一張
        （薩姆 `0.00 / ✅ 未觸發衰退門檻，勞動市場正常。`，另兩張維持誠實 ⬜）
        → **683 passed 零紅燈**。**現已把單位下沉到「每一張卡」**
        （:func:`_grey_units` 再切 `**標題**` 一層），該突變現在會紅。

        ⚠️ **修 R3 的時候本組又抓到一個它沒點名、但同型的洞，一併修掉**：
        只切 `**標題**` 時，**只擋得住三張卡裡的第一張** ——
        合格態的卡片走 `st.metric()`，**畫面上沒有任何可切段的標記**，
        於是被捏造的第 2／3 張會併進**前一張**的單位，而前一張還有 ⬜。
        實測（補救之前）：捏造第 1 張 `1 failed`、**捏造第 2 張 `21 passed`**。
        → 側錄器改為替每個 `st.metric` 補一個分段標記（:data:`_METRIC_MARK`），
        現在**三張各捏造一次都是 `1 failed`**。
        ⚠️ **這一筆值得記**：R3 的原始形狀「只驗到上一層」在被修一次之後，
        **在下一層原封重現**。修分層的斷言時，要問的不是「這一層夠不夠細」，
        而是「**這一層的每一個成員都有自己的邊界嗎**」。

        ⚠️ **殘留的是更窄的一條**：同一張卡／同一個沒有任何邊界標記的段落裡
        有兩份灰態時，拔掉其中一份仍不會紅。**本輪實測今天沒有這種段落**
        （每個葉單位最多一個 `not_ready()`），但這句話**與上面那句是同一種形狀** ——
        **請把它當成待驗，不要當成保證**；上面那次就是這樣被證偽的。
      - **📈 中期循環不在斷言範圍內**（見 :data:`_GREY_BLOCKS` 的說明）。
      - 本條只驗「有沒有 ⬜ 與指路」，**不驗那句話講得對不對** ——
        灰態文案寫錯內容（例如指到別頁）本條看不到；
        指路內容的既有缺口見 `CLAUDE.md §8.3.P` 的 `P-WHERECONTENT-1`。
      - **側錄器沒攔的渲染 API 一律隱形**（真界線是 :data:`_TEXT_APIS`）。
        `assert _units` 擋得住「整段因此空掉」，**擋不住**「同一單位裡另有 ⬜、
        但那段假話是用沒列進字表的 API 印的」。
    """
    from ui.helpers.render_state import NOT_READY_MARK

    # ⚠️ **`ind` 用空 dict，不是 `{"VIX": {"value": None}}`。**
    #    後者會在**服務層**炸掉（實測 2026-09-05：
    #    `services/macro/us_indicators.py::calc_macro_phase` 內的
    #    `indicators.get("VIX", {}).get("value", 18) > _MB_VIX_YELLOW`
    #    —— key 在、值是 `None` 時 `.get(..., 18)` 的預設值救不到，直接 `TypeError`）。
    #    ⚠️ **2026-09-05 稽核 F3 更正函式名**：~~`detect_systemic_risk`~~ 是錯的，
    #    那一支吃的是 `news_items: list`、根本碰不到 `indicators`。**機制對，名字錯。**
    #    那是**既有的服務層脆弱點**，依客戶方針第 2 條本批不反向修底層；
    #    此處據實登記並改用不會踩到它的輸入。**本條要驗的是 UI 的灰態，不是它。**
    _segs = _render_segments({_page._SK_IND: {}})

    # 骨架不因為沒資料而消失（鐵則 04）—— 五塊都要在，含委派的那一塊。
    for _t in _WIREFRAME_TITLES:
        assert _t in _segs, (
            f"沒有資料時「{_t}」整塊消失了 —— 骨架不得跟著不見。"
            f"\n實際切到的塊：{list(_segs)}")

    for _t in _GREY_BLOCKS:
        # ⚠️ **粒度是「塊 ＋ 塊內每一個 `#####` 小節」，不是只有塊。**
        #    🎯 短線雷達（④／⑤）與 ⚠️ 拐點警報（①／②）**一塊裡有兩個小節、
        #    各自有自己的灰態**；只驗到塊的話，拔掉其中一個小節的灰態，
        #    另一個還在 → 照樣綠。**本組自驗突變實測過這個洞**：
        #    只驗塊時，那兩塊各自被改成 `st.success("✅ 一切正常")` 都是 `21 passed`。
        #    切到小節之後兩者都會紅（見 PR 描述的逐塊表）。
        _units = _grey_units(_t, _segs[_t])
        # ⛔ **2026-09-05 稽核 R2：沒有這一行，下面那個 `for` 可以一次都不跑。**
        #    `_grey_units()` 會略過空白段落，所以「一塊只剩標題」或「內容用了
        #    側錄器沒攔的 API」時它回 `[]` → 迴圈空轉 → **綠**。
        #    那正是本檔自己警告過的形狀（「一條什麼都沒斷言的測試會一直是綠的」）。
        #    稽核實跑兩種繞法，補這行之前**都是 21 passed**：
        #      (a) 灰態換成假的綠色小節標題 `st.markdown("##### ✅ …一切正常")`
        #          → 該塊 grey units ＝ `[]`；
        #      (b) 灰態改用未側錄的 API `st.text("✅ …一切正常")`
        #          → 該塊 segment 完全空白。
        #    ⚠️ (b) 也順帶說明本檔的真界線仍是 `_TEXT_APIS` 那份字表：
        #       本行擋得住「整段消失」，**擋不住**「用沒列進字表的 API 印出一段假話
        #       但同一單位裡另外還有 ⬜」。那一半沒有便宜的解，據實留在下方 ⛔ 清單。
        assert _units, (
            f"「{_t}」在沒有資料時切不出任何內容單位 —— "
            "整塊只剩標題（或內容走了側錄器沒攔的 API）。\n"
            "⛔ 沒有內容 ＝ 使用者看不出「這裡缺什麼、去哪補」，"
            "與畫一句「一切正常」一樣違反鐵則 04。\n"
            f"該塊 segment 原文：{_segs[_t][:400]!r}")
        for _label, _seg in _units:
            assert NOT_READY_MARK in _seg, (
                f"{_label} 沒有資料，卻沒有印出任何 ⬜ 灰態 —— "
                "留白／`—`／「一切正常」都是把『沒抓到』說成別的東西（§1）。\n"
                f"該段實際印出的內容：{_seg[:400]!r}")
            # `not_ready()` 的輸出格式是 `⬜ {訊息}（請先到：{where}）`，
            # 所以「有沒有指路」看得到這個前綴就成立 —— 不比對指到哪裡
            # （🤖 AI 那一塊在沒金鑰時指的是 Secrets，不是本頁的載入鈕）。
            assert "（請先到：" in _seg, (
                f"{_label} 的灰態沒有帶「去哪補」—— "
                "線框 Rule 04 的三要素少了最有價值的那一項。\n"
                f"該段實際印出的內容：{_seg[:400]!r}")


# ══════════════════════════════════════════════════════════════
# 8) prompt 鎖 —— 餵給 LLM 的那一份也不得說「平靜」
# ══════════════════════════════════════════════════════════════
# ⚠️ **本節是 2026-09-05 稽核 F1 逼出來的，理由必須留著。**
#    第 7 節的側錄器只攔 `st.*` 渲染 API，而**交給 LLM 的 prompt 字串
#    完全不經過任何 `st.*`** —— 於是 `_ai_snapshot()` 這個消費端
#    對整份守衛是**結構性隱形**的。前一版因此漏掉它：
#    10 燈全滅時它把「整體 平靜」寫進 prompt，而 prompt 開頭就寫著
#    「【嚴格規則】**只能根據下面的『資料快照』來講**」。
#    → **畫面誠實、AI 卻被告知市場平靜。** 這比畫面說謊更難發現。

def test_the_ai_snapshot_never_calls_the_market_calm_when_nothing_was_fetched():
    """10 燈全滅時，**交給 LLM 的快照**不得出現「平靜」。

    **突變會紅**：拿掉 `_ai_snapshot()` 裡的 `if not _radar_lit(_s):` → 本條紅。

    ⚠️ 本條**不看畫面**，直接呼叫 `_ai_snapshot()` 取那一份字串 ——
    因為它就是不經過畫面的那條路。
    """
    _all_grey = {f"sig{_i}": {"signal": "⬜ 無資料", "value": None, "prev": None,
                              "note": "來源暫時無法取得", "label": "—", "trend": []}
                 for _i in range(10)}
    _ind = {"VIX": {"name": "VIX 恐慌指數", "value": 24.1, "unit": ""}}
    _ss = _FakeSessionState({_page._SK_IND: _ind, _page._SK_RADAR: _all_grey})

    with patch.object(st, "session_state", _ss):
        _snap = _page._ai_snapshot(_ind, {"phase": "擴張中段", "score": 6},
                                   {"score": 6.5, "level": "樂觀"})

    assert "[短線雷達]" in _snap, (
        "雷達那一行整個從快照消失了 —— 應該是**改口**，不是**消音**："
        "AI 需要知道「這一項沒抓到」，而不是完全不提它")
    assert "平靜" not in _snap, (
        "10 盞燈一盞都沒抓到，交給 LLM 的快照卻寫著「平靜」。\n"
        "prompt 開頭是「只能根據下面的資料快照來講」——"
        "這等於直接告訴模型市場平靜（§1）。\n"
        f"實際快照：\n{_snap}")


def test_every_summarize_radar_consumer_goes_through_the_lit_guard():
    """`summarize_radar()` 有幾個呼叫點，`_radar_lit()` 就要有幾個。

    ⚠️ **這是本檔唯一一條「結構完整性」鎖，存在的理由是 F1 那次漏網。**
    前一版把那道防線各自 inline 寫在消費端，於是**第三個消費端整個漏掉**，
    而且**沒有任何一條守衛看得到它**（它不印在畫面上）。
    逐一為每個消費端寫行為斷言是好的，但**擋不住「有人新增第四個消費端」** ——
    本條擋得住：數量對不上就紅。

    **突變會紅**：在本檔任一處新增一個 `summarize_radar(...)` 而不配一個
    `_radar_lit(...)` → 本條紅。**含 `import … as` 的別名寫法**（R1 修好之後）。

    ⚠️ **本條守的是「有沒有配對」，不是「配對得對不對」** —— 有人寫
    `_radar_lit(_s)` 卻不用它的結果，本條照樣綠。**那一半由上面兩條行為鎖守。**

    ⚠️ **能擋什麼／擋不到什麼，寫在 `page_01_macro.py::_radar_lit()` 的 docstring**
    （**已知擋得住 2 種、已知擋不住 4 種，非窮舉**；不在這裡抄第二份）。
    重點只有一句：**它是「少一道人為疏漏」，不是「不可能再漏」。**

    ⛔ **2026-09-05 稽核 R1：本條初版按「裸名字」計數，別名 import 可整個繞過。**
    ~~`_names.count("summarize_radar")`（直接讀 `func.id` / `func.attr`）~~ ——
    稽核實跑，在 `_detail_ai()` 內加：

    ```python
    from services.risk_radar import summarize_radar as _sr2
    _stale += f"（附註：短線雷達整體研判為 {_sr2(_r4).get('level')}。）"
    ```

    → 本條數到 `summarize_radar: 3 / _radar_lit: 3`（**別名隱形**）→ **225 passed
    零紅燈**，而「平靜」照樣進 prompt。
    ⚠️ **本 repo 已經踩過並寫下來了**：同一個測試套組的
    `tests/test_batch2_top_card_grid.py::_call_name()` 註解逐字寫著
    「只比對字面名字會漏掉它（**本規則初版就漏了，是突變探針抓出來的**）」。
    **新的結構鎖重蹈同一個坑**，本輪照那支的做法修好。

    ⚠️ **`_call_name` / `_import_alias` 直接 import 既有實作，不另寫一份** ——
    另寫一份就會變成第二個 SSOT，而那正是 `CLAUDE.md §2.1` 明文禁止、
    且被引用的那個檔自己也寫過的事。
    """
    import ast as _ast
    import pathlib as _pl

    # 穿過 `import X as _y` 的別名解析：復用既有實作（§2.1 SSOT，不另寫一份）。
    from test_batch2_top_card_grid import _call_name, _import_alias

    _src = (_pl.Path(_page.__file__)).read_text(encoding="utf-8")
    _tree = _ast.parse(_src)
    _alias = _import_alias(_tree)
    _names = [_call_name(_n, _alias)
              for _n in _ast.walk(_tree) if isinstance(_n, _ast.Call)]
    _n_sum = _names.count("summarize_radar")
    _n_lit = _names.count("_radar_lit")

    assert _n_sum >= 3, (
        f"前提變了：`summarize_radar()` 的呼叫點只剩 {_n_sum} 個（原本 3 個）。"
        "少了消費端不是壞事，但請確認本條還守得到東西。")
    assert _n_sum == _n_lit, (
        f"`summarize_radar()` 有 {_n_sum} 個呼叫點，但 `_radar_lit()` 只有 {_n_lit} 個"
        " —— 有消費端沒有過「全 ⬜ 不得說平靜」那道防線。\n"
        "⛔ 特別注意**不印在畫面上的消費端**（例如寫進 AI prompt 的那個）："
        "它們對本檔第 7 節的側錄器是結構性隱形的，只有本條看得到。")


def test_every_radar_session_read_is_summarized_in_the_same_function():
    """讀 `_SK_RADAR` 的每個函式，都要在**同一個函式裡**呼叫一次 `summarize_radar()`。

    ⛔ **這條補的是上一條結構上看不見的那個洞，2026-09-06 由一個真實 bug 逼出來。**
    上一條比對的是「`summarize_radar` 呼叫數 vs `_radar_lit` 呼叫數」——
    `_card_exceptions()` 當時**兩個都沒呼叫**，它直接對原始 dict 讀 `red` / `yellow`：

    ```python
    _radar = st.session_state.get(_SK_RADAR)
    _red = int(_radar.get("red", 0)) if isinstance(_radar, dict) else 0
    ```

    → 兩邊都是 3，**上一條全綠**；而 `_SK_RADAR` 存的是原始 10 燈
    （key 是 `vix_level` / `hy_oas_delta` / …），**沒有 `red` / `yellow`** ——
    那兩個數字**恆為 0**。實測：5 盞紅燈（`summarize_radar` 回 `level='極端警報'`、
    `red=5`）時，那張卡照樣印「🔴 0 ／ 🟡 0」，且 `_alarm` 的 `_red > 0` 那半是死碼。
    **一條「數量對得上」的鎖，擋不住「兩邊都是 0」。**

    **突變會紅**：把 `_card_exceptions()` 的 `summarize_radar(_radar)` 拿掉、
    改回直接讀 `_radar.get("red")` → 本條紅（實測，見 PR 描述的突變測試段）。

    ⚠️ **能擋什麼／擋不到什麼 —— 照 `_radar_lit()` docstring 的體例寫成
    「已知擋得住／已知擋不住」，不是能力清單。** 那份 docstring 記著本 repo 已經
    在同一個位置**把清單寫成窮舉而錯過兩次**；本條不重蹈。

    **已知擋得住**
      - 新增一個讀 `_SK_RADAR` 的函式，卻沒在同一個函式裡彙總（＝本次這個 bug 的形狀）；
      - `import … as` 的別名呼叫 —— 復用 `_call_name` / `_import_alias`（同上一條）。

    ⚠️ **2026-09-06 獨立稽核擋下：本清單原本有三格分類反了，已就地更正。**
    「本地變數別名」「`getattr` 動態取名」「讀取搬到別的函式」原本列在
    「擋不住」，**實測是會轉紅的** —— 但那是**誤報**（把對的寫法判成違規），
    不是漏放。**一份主題是「誠實寫明擋不擋得住」的清單，自己填錯三格。**
    故本清單改成三欄，不再只分兩類。

    **已知擋得住（正確地紅）**
      - 新增一個讀 `_SK_RADAR` 的函式，卻沒在同一個函式裡彙總（＝本次這個 bug 的形狀）；
      - `import … as` 的別名呼叫 —— 復用 `_call_name` / `_import_alias`。

    **已知會誤報（也會紅，但紅得沒道理 —— 寫法其實是對的；各實測一次突變）**
      - **本地變數別名**：`_sfn = summarize_radar` 之後 `_sfn(_radar)`
        → 實測 **2 failed**（`_call_name` 看到的是 `_sfn`，`_import_alias()`
        只解析 import 別名）；
      - **動態取名**：`getattr(_rr, "summarize_radar")(_radar)`
        → 實測 **2 failed**（func 是 Call，`_call_name` 回 None）；
      - **把 session 讀取搬到別的函式再傳進來** —— 本條看的是**讀取點**那個函式，
        所以那個只負責取值的 helper 會被判違規，即使消費端彙總得好好的。
      **→ 這三種若真的要用，請一併調整本條，不要靠 `# noqa` 蓋掉。**

    **已知擋不住（非窮舉 —— 真的會漏放，全綠）**
      - 🆕 **字面值 key**：`st.session_state.get("v01_macro_risk_radar")`
        （不寫 `_SK_RADAR`）。`_reads_radar()` 只認 `ast.Name` 的 `_SK_RADAR`，
        字面值對它是隱形的。**這是最可能被寫出來的一種，故逐字具名。**
        ⚠️ **但要分兩種情況講，稽核的宣稱只對了一半（本組實測推翻另一半）**：
          · **把既有消費端改成字面值** → **會紅**，由本條的**前提鎖**
            （`len(_checked) >= 4`）抓到，訊息逐字點名少了哪一個
            （實測：`assert 3 >= 4`，`['_card_risk_radar', '_detail_short', '_ai_snapshot']`）；
          · **新增一個用字面值的消費端**（既有四個原封不動）→ **真的全綠**
            —— 實測 `746 passed, 32 skipped` 零紅燈，而那個新消費端把
            原 bug 原封重現。**前提鎖看的是數量，補上來的那個它看不到。**
      - **`_k = _SK_RADAR` 之後 `st.session_state.get(_k)`** 的間接取值 —— 同上。
      - **跨檔**：本條只讀 `ui/views/page_01_macro.py` 一個檔；
      - **彙總了但沒用它的結果**（彙總完仍舊去讀原始 dict 的 `red`）——
        本條只看「同一個函式裡有沒有這個呼叫」，不看資料怎麼流。
        ⚠️ 這一種現在**另有行為測試**守著（見
        `test_the_exceptions_card_reports_the_real_radar_counts`），
        但**本條自己仍然擋不住**，故留在這一欄。
      - **模組層級的讀取**（不在任何 `def` 內）—— 本條只走函式節點。

    ⚠️ **寫入端刻意不算讀取端。** `_load_everything()` 做的是
    `st.session_state[_SK_RADAR] = detect_risk_radar(...)`，**存進去的那一端
    本來就不該彙總**（彙總是消費端的事）。初版沒分讀寫，當場誤判它違規 ——
    見 `_reads_radar()` 內的註解。

    ⛔ **所以它跟上一條一樣是「少一道人為疏漏」，不是「不可能再漏」。**
    """
    import ast as _ast
    import pathlib as _pl

    # 復用既有實作（§2.1 SSOT，不另寫一份）—— 同上一條。
    from test_batch2_top_card_grid import _call_name, _import_alias

    _src = (_pl.Path(_page.__file__)).read_text(encoding="utf-8")
    _tree = _ast.parse(_src)
    _alias = _import_alias(_tree)

    def _reads_radar(fn: _ast.AST) -> bool:
        """函式體內**讀取**（不是寫入）`_SK_RADAR`。

        ⚠️ **必須區分讀寫，否則會誤傷寫入端。** 初版只找裸名 `_SK_RADAR`，
        當場把 `_load_everything()` 判成違規 —— 它做的是
        `st.session_state[_SK_RADAR] = detect_risk_radar(...)`，
        **存進去的那一端本來就不該彙總**（彙總是消費端的事）。
        認得兩種讀法：`st.session_state.get(_SK_RADAR)`
        與 `st.session_state[_SK_RADAR]`（Load 情境，非指派目標）。
        """
        for _n in _ast.walk(fn):
            # a) `….get(_SK_RADAR)` / `….get(_SK_RADAR, 預設值)`
            if (isinstance(_n, _ast.Call)
                    and isinstance(_n.func, _ast.Attribute)
                    and _n.func.attr == "get"
                    and any(isinstance(_a, _ast.Name) and _a.id == "_SK_RADAR"
                            for _a in _n.args)):
                return True
            # b) `…[_SK_RADAR]` 且是取值（`ctx` 為 Load）而不是指派目標
            if (isinstance(_n, _ast.Subscript)
                    and isinstance(_n.ctx, _ast.Load)
                    and isinstance(_n.slice, _ast.Name)
                    and _n.slice.id == "_SK_RADAR"):
                return True
        return False

    def _summarizes(fn: _ast.AST) -> bool:
        return any(_call_name(_n, _alias) == "summarize_radar"
                   for _n in _ast.walk(fn) if isinstance(_n, _ast.Call))

    _offenders: list[str] = []
    _checked: list[str] = []
    for _fn in _ast.walk(_tree):
        if not isinstance(_fn, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            continue
        if not _reads_radar(_fn):
            continue
        _checked.append(_fn.name)
        if not _summarizes(_fn):
            _offenders.append(f"{_fn.name}（第 {_fn.lineno} 行）")

    # 前提鎖：讀取點若歸零，本條就守不到東西了，要讓人知道。
    assert len(_checked) >= 4, (
        f"前提變了：讀 `_SK_RADAR` 的函式只剩 {len(_checked)} 個"
        f"（原本 4 個：{_checked}）。少了消費端不是壞事，"
        "但請確認本條還守得到東西。")

    assert not _offenders, (
        "下列函式從 session 讀了 `_SK_RADAR`（＝ `detect_risk_radar()` 的**原始 10 燈**），"
        f"卻沒有在同一個函式裡呼叫 `summarize_radar()`：{_offenders}\n"
        "⛔ 原始 dict 的 key 是 `vix_level` / `hy_oas_delta` / … —— "
        "**沒有 `red` / `yellow` / `level`**。直接對它 `.get('red', 0)` 不會報錯，"
        "只會**恆得 0**：10 燈全紅的極端警報，畫面照樣印「🔴 0」。\n"
        "→ 要數字請先 `summarize_radar(_radar)`，並照 `_radar_lit()` 的規則"
        "擋掉「全 ⬜ 卻說平靜」。")


#: 全站斷線的 indicators —— 五個 FRED 來源全部 `success: False`，一個計分指標都沒有。
#: 形狀照抄 `tests/test_batch2_top_card_grid.py::_TOTAL_OUTAGE_IND`（同一個生產端、
#: 同一種斷線情境）。**刻意在本檔另存一份而不是 import**：那份是 batch2 的模組私有常數，
#: 跨檔 import 會讓兩個檔的守衛在對方改動時一起倒，反而看不出是誰壞了。
_P01_TOTAL_OUTAGE_IND = {"_fred_sources": {
    _sid: {"success": False, "last_date": "", "realtime_start": "",
           "publish_lag_days": None, "rows": 0}
    for _sid in ("DGS10", "DGS2", "DGS3MO", "T10Y2Y", "T10Y3M")}}


def _p01_full_ind() -> dict:
    """28 項計分指標全部在線 —— 用來驗**反方向**（資料夠時照樣出位階）。"""
    from services.macro.evidence import MACRO_INDICATOR_SCORING_WEIGHTS as _W
    return {_k: dict(value=1.0, weight=_W[_k], score=_W[_k]) for _k in _W}


def test_the_phase_card_greys_out_when_the_score_is_a_divide_by_zero_default():
    """「景氣位階」卡在**零資料**時不得印出那顆分母為零的預設分數。

    ⛔ **2026-09-06 由一個真實 bug 逼出來 —— 這張卡以前完全沒讀 `support`。**
    `calc_macro_phase(<全站斷線>)` 實跑回 `score=5`、`phase='擴張'`，
    而 `support.sufficient=False`、`reason='一個計分指標都沒取到，分數 5.0 是
    分母為零時的預設值，不是量測'`。舊版只看 `_phase.get("phase")` 是否為真
    （'擴張' 是真的）→ 印出綠色的「擴張（5/10）」。
    **那個 5 不是量到的東西，是分母為零時的預設值。**

    ⚠️ **生產端早就把判斷交過來了**：`calc_macro_phase` 內
    `support=_phase_support(indicators, score)` 上方的註解逐字寫「消費端讀
    `.sufficient`」—— 缺的從來不是資訊，是**有人去接**。

    ⚠️ **同頁當時是自相矛盾的**：① 結論與 ② 依據都已經在讀 `support`
    （`is_sufficient()`，L0 SSOT），只有本卡沒讀 —— 於是同一個畫面上
    「這次的資料撐不起任何結論」與綠色的「擴張（5/10）」並排。

    **突變會紅**：把 `_card_phase()` 的 `is_sufficient(_support)` 守門整段拿掉
    → 本條紅（實測；見 PR 描述的突變測試段）。⚠️ 拿掉守門後**全 744 條只有本條會紅**
    —— 也就是說在本條寫出來之前，這個 bug 在測試套件裡是**完全隱形**的。

    ⚠️ **本條是行為測試，不是形式測試** —— 它問「這張卡吐出什麼」，
    不問「有沒有呼叫某個函式」。所以改寫成別的等價寫法不會誤紅；
    但也因此**擋不到**：卡片以外的地方（本條只叫 `_card_phase` 一個函式）、
    以及 `support` 充足但數字本身算錯的情形（那是生產端的事）。
    """
    # ── 前提鎖：生產端仍然吐那顆假分數。它哪天改了，本條要說話，不要默默變成空測試。
    _phase = _page.calc_macro_phase(_P01_TOTAL_OUTAGE_IND)
    assert _phase["score"] == 5 and _phase["phase"] == "擴張", (
        f"前提變了：生產端不再吐『擴張 5/10』（現為 {_phase['phase']} "
        f"{_phase['score']}/10）。本條守的那個具體情境可能已不存在，請重看。")
    assert not _phase["support"].sufficient, (
        "前提變了：生產端現在認為零資料也撐得住位階判讀 —— 那是更大的問題，先查生產端。")

    # ── 正向：零資料 → 灰態，且**不得**把那顆假分數印出來。
    _card = _page._card_phase(_P01_TOTAL_OUTAGE_IND)
    assert _card["state"] == _page.STATE_NOT_READY, (
        f"零資料時「景氣位階」卡的狀態是 {_card['state']!r}，不是灰態。\n"
        "⛔ `calc_macro_phase({})` 的 5.0 是**分母為零時的預設值**，不是量測；"
        "把它畫成一張有顏色的卡，就是把「什麼都沒抓到」講成「擴張」（§1）。\n"
        "→ 請走 `is_sufficient(_phase.get('support'))`（L0 SSOT，"
        "與同頁 ① 結論、② 依據同一支），不要在這裡發明第三套判斷式。")
    _shown = f"{_card.get('value', '')}{_card.get('note', '')}"
    assert "5/10" not in _shown and "擴張" not in _shown, (
        f"灰態卡仍然把那顆假分數／假位階印出來了：{_shown!r}")
    # 灰態三要素之一：要告訴使用者去哪裡補資料（本檔第 4 節的既有規則）。
    assert _card.get("where"), "灰態卡沒有告訴使用者去哪裡補資料"

    # ── 反方向：資料夠的時候照樣出位階。**沒有這一半，「永遠回灰態」也會全綠。**
    _ok = _page._card_phase(_p01_full_ind())
    assert _ok["state"] != _page.STATE_NOT_READY, (
        f"28 項指標全部在線卻還是灰態 —— 守門過嚴，把好資料也擋掉了：{_ok!r}")
    assert "/10" in str(_ok.get("value", "")), (
        f"資料充足時卻沒印出位階分數：{_ok!r}")


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


def test_the_liquidity_caption_says_how_many_factors_it_actually_used():
    """流動性壓力分數必須說出**它是用幾個因子算的**。

    ⛔ **2026-09-06 實測**：`compute_liquidity_score()` 對缺席因子
    **自動重正規化權重**，於是

        compute_liquidity_score({"XCCY_PROXY": {"zscore": 2.5}})
        → value=2.5, tier='流動性危機', breakdown 1 筆（weight 被放大成 1.0）

        三個因子都給 2.5
        → value=2.5, tier='流動性危機', breakdown 3 筆（0.4/0.3/0.3）

    **兩者的 `value` 與 `tier` 完全相同**，而 `liquidity_verdict()` 對兩者
    印出的是**同一句**「⚠️ 美元/避險/波動率**多軌同時緊繃**……宜降槓桿、備現金」。
    一個因子的讀數，長成三軌共振的樣子 —— 使用者無從分辨，而這是他會照著做的建議。

    本條只鎖**最低限度的誠實**：畫面要看得出「N/3」。
    ⚠️ **刻意不鎖那句研判的文案語氣** —— 改它會改變使用者的行動，屬待客戶拍板事項
    （見 PR 描述）。本條不預設答案，只確保「幾分之幾」這個事實不會再消失。

    **突變實測（兩顆，結果不一樣，照實寫）**
      - 拿掉主 caption 的 `{_n_on}/{_n_all} 壓力因子在線` → **紅**
        （由反方向那半抓到：三因子全在線時整頁找不到「3/3」）。
      - **只**拿掉第二段「⚠️ 這個分數只用了 N 個」的警語 → **綠，不紅。**
        ⚠️ **這不是漏掉，是本條刻意的射程**：那時主 caption 仍印著「1/3」，
        「幾分之幾」這個事實還在畫面上，本條要鎖的東西沒有消失。
        **要連那句警語一起鎖，得先由客戶拍板它是不是最終呈現**
        —— 在那之前把它寫死，等於用測試替客戶做決定。

    ⚠️ **分母是 `STRESS_FACTORS`（3），不是 `_LIQ_FACTOR_ROWS`（4）** ——
    後者含 SSR，而 `services/liquidity_engine.py` 就地註明
    「SSR 依設計為獨立『鏈上子彈水位』對沖指標，**不計入壓力分數**」。
    拿 4 當分母會多算一個，反而變成新的假數字。

    ⚠️ **擋不到**：分數本身算得對不對（那是服務層的事）、
    以及研判文裡「多軌同時」與實際軌數是否一致（刻意留給客戶拍板）。
    """
    from services.liquidity_engine import (
        STRESS_FACTORS as _SF,
        compute_liquidity_score as _cls,
    )

    # ── 前提鎖：服務層今天真的還會把 1 因子與 3 因子算成同一個分數。
    #    這個前提沒了（例如服務層改成因子不足就回 None），本條的理由就變了，
    #    要讓人知道，不要靜靜變成一條永遠成立的空測試。
    _one = _cls({"XCCY_PROXY": {"zscore": 2.5}})
    _three = _cls({_k: {"zscore": 2.5} for _k in _SF})
    assert _one and _three and _one["value"] == _three["value"], (
        "前提變了：1 因子與 3 因子已經算不出同一個分數了 —— "
        f"（{_one and _one.get('value')} vs {_three and _three.get('value')}）。"
        "本條守的那個混淆可能已經在服務層解掉了，請重看。")
    assert len(_one.get("breakdown") or []) == 1, "前提：1 因子時 breakdown 只有 1 筆"

    # ── 正向：只有 1 個因子在線時，畫面要說出「1/3」。
    _sess = _loaded_session()
    _sess[_page._SK_LIQ] = ({"XCCY_PROXY": {"zscore": 2.5, "value": 2.5}}, _one)
    _blob = _render_all_text(_sess)
    assert f"1/{len(_SF)}" in _blob, (
        "流動性壓力只用了 1 個因子，畫面卻沒說出「1/3」——\n"
        "⛔ 缺席因子的權重被重新分配給在線因子，所以這個分數**不能**跟滿額讀數"
        "直接比大小；不揭露就等於讓一軌的讀數冒充三軌共振（§1）。\n"
        f"整頁實際印出的內容（節錄）：{_blob[:600]!r}")

    # ── 反方向：三個因子都在線時，不該再掛那句「只用了 N 個」的警語。
    #    沒有這一半，「永遠印警語」也會全綠。
    _sess2 = _loaded_session()
    _sess2[_page._SK_LIQ] = ({_k: {"zscore": 2.5, "value": 2.5} for _k in _SF},
                             _three)
    _blob2 = _render_all_text(_sess2)
    assert f"{len(_SF)}/{len(_SF)}" in _blob2, (
        f"三個因子全在線時應該印「3/3」：{_blob2[:600]!r}")
    assert "這個分數只用了" not in _blob2, (
        "三個因子全在線，卻還掛著「只用了 N 個壓力因子」的警語 —— "
        f"揭露過頭會稀釋它在真的缺因子時的份量：{_blob2[:600]!r}")


def test_a_partial_liquidity_reading_never_claims_multi_track_stress():
    """因子不全時，畫面**不得**出現那句宣稱三軌共振的研判。

    ⛔ **2026-09-06 獨立稽核擋下 + 總管裁決：加註解不等於修好。**
    前一版只在**下一段** caption 補一句更正，使用者讀到的**第一句**仍然是
    「⚠️ 美元/避險/波動率**多軌同時緊繃**……**宜降槓桿、備現金**」——
    **假前提與行動建議同在一句**，而更正在下面。

    **機制（實測）**：`compute_liquidity_score()` 對缺席因子**重正規化權重**，
    單因子在線時該因子權重被放大成 `1.0` → 分數照樣衝到 `2.5` →
    觸發 `liquidity_verdict()` 的 `val >= 2.0` 分支（服務層唯一會講「多軌同時」
    的那一支）。**一軌的讀數，講出三軌的話。**

    ⚠️ **前一版的第二段更正沒有任何守衛單獨鎖住** —— 稽核實測：把那段
    caption 拿掉 → `228 passed` 零紅燈。也就是那句唯一的反駁**可以被無聲刪掉**。
    **不印它，就沒有東西需要被反駁 —— 那個缺口一併消失。**

    **突變會紅**：把 `_partial` 那個三元運算子拿掉、改回無條件
    `liquidity_verdict(_score, _factors)` → 本條紅（實測，見 PR）。

    ⚠️ **擋不到**：`_n_on == _n_all` 時研判文的內容對不對（那是服務層的事，
    本條刻意不碰）、以及「多軌同時緊繃」以外的其他措辭若日後新增。
    """
    from services.liquidity_engine import (
        STRESS_FACTORS as _SF,
        compute_liquidity_score as _cls,
        liquidity_verdict as _lv,
    )
    _MULTI = "多軌同時緊繃"

    # ── 前提鎖：服務層今天真的還會對「單因子 z=2.5」講出那句多軌宣稱。
    _one = _cls({"XCCY_PROXY": {"zscore": 2.5}})
    assert _one and _MULTI in _lv(_one, None), (
        "前提變了：服務層對單因子高分已經不再講「多軌同時緊繃」了 —— "
        f"本條要擋的那句話可能已經在上游解掉，請重看：{_lv(_one, None)!r}")

    # ── 正向：只有 1 軌在線 → 整頁不得出現那句話。
    _sess = _loaded_session()
    _sess[_page._SK_LIQ] = ({"XCCY_PROXY": {"zscore": 2.5, "value": 2.5}}, _one)
    _blob = _render_all_text(_sess)
    assert _MULTI not in _blob, (
        f"只有 1/{len(_SF)} 軌量到，畫面卻印出「{_MULTI}」——\n"
        "⛔ 那句話**逐一點名美元／避險／波動率三軌**，而這一輪只量到一軌；"
        "它還與行動建議「宜降槓桿、備現金」同在一句。\n"
        "→ 因子不全時整句研判不要印（`_partial` 分支），"
        "不要只在下一段補一句更正 —— 使用者讀到的第一句就是假的。\n"
        f"整頁實際印出（節錄）：{_blob[:600]!r}")
    # 抑制之後仍須誠實說明「為什麼這裡沒有研判」，不能只是空白。
    assert f"1/{len(_SF)} 軌真的量到" in _blob, (
        f"抑制了研判卻沒說明原因，變成無聲省略：{_blob[:600]!r}")

    # ── 反方向：三軌全在線 → 研判照印，**一個字都不該少**。
    #    沒有這一半，「永遠不印研判」也會全綠。
    _three = _cls({_k: {"zscore": 2.5} for _k in _SF})
    _sess2 = _loaded_session()
    _sess2[_page._SK_LIQ] = ({_k: {"zscore": 2.5, "value": 2.5} for _k in _SF},
                             _three)
    _blob2 = _render_all_text(_sess2)
    assert _MULTI in _blob2, (
        f"三軌全在線時研判被連坐擋掉了 —— 抑制過頭：{_blob2[:600]!r}")


#: 回指詞 —— 一句話用這些字說「我在講上面某句」時，那句必須真的在畫面上。
_BACKREF_MARKERS = ("上面", "上述", "前面")


def test_no_sentence_points_back_at_something_the_page_no_longer_prints():
    """畫面上任何「**上面那句…「X」…**」的回指，`X` 必須真的印在畫面上。

    ⛔ **2026-09-06 由一個真實的回修副作用逼出來的。**
    同一輪把「多軌同時緊繃」那句研判改成**因子不全時不印**之後，
    第二段警語裡這半句沒有跟著撤：

        「…直接比大小；**上面那句研判裡關於「多軌同時」的描述**，
          這一輪只有 N 軌真的量到。」

    使用者往上找，**找不到那句話** —— 因為它已經不印了。
    （另一半「這一輪只有 N 軌真的量到」也與主 caption 重複。）

    📌 **這是一個形狀，不是一處筆誤**：
    **撤回一句宣稱時，「引用它的那句話」不會自動跟著撤回。**
    本次兩邊**都是文案**、都不在型別系統裡，所以**沒有任何東西會報錯** ——
    刪掉被引用的那句，引用它的那句只會安靜地變成廢話。

    **本條怎麼做到通用**：沿用本 repo 既有的 `「」` 慣例（`where=` 的
    「去哪補」內容規則用的是同一個約定 —— `「」` 裡放的是**畫面上真的看得到的東西**）。
    規則是：**任何含回指詞（上面／上述／前面）的句子，其 `「」` 內的字串
    必須在整頁其他地方也出現。**

    **突變會紅**：把第二段警語的後半兩行加回去
    （`…直接比大小；上面那句研判裡關於「多軌同時」的描述，…`）→ 本條紅（實測，見 PR）。

    ⚠️ **擋不到（非窮舉，照本檔體例寫成「已知」不是「全部」）**
      - **不用 `「」` 的回指**：「上面那句研判提到的多軌同時」—— 沒有引號可抓；
      - **不用上列三個回指詞**：「剛才那句」「稍早提到的」；
      - **語意上的回指**：「它其實只有一軌」—— 完全沒有形式標記；
      - **本條只渲染本頁**：跨頁的回指看不到；
      - **只驗「有沒有出現」，不驗「指的是不是同一個東西」**：
        同一個字串在畫面別處剛好出現，本條就放行。
    """
    import re as _re

    _sent_re = _re.compile(
        r"[^。；\n]*(?:" + "|".join(_BACKREF_MARKERS) + r")[^。；\n]*")
    _quote_re = _re.compile(r"「([^」]+)」")

    def _check(_blob: str, _what: str) -> None:
        _bad = []
        for _sent in _sent_re.findall(_blob):
            for _q in _quote_re.findall(_sent):
                # 被引用的字串必須在「這句以外」的地方也出現。
                if _blob.replace(_sent, "", 1).find(_q) < 0:
                    _bad.append((_q, _sent.strip()[:90]))
        assert not _bad, (
            f"[{_what}] 畫面上有句子回指了一個**畫面上找不到**的東西：\n"
            + "\n".join(f"  引用「{_q}」← 出自：{_s!r}" for _q, _s in _bad)
            + "\n⛔ 使用者會往上找，然後找不到。\n"
            "→ 撤回一句話時，**引用它的那句話要一起撤**；"
            "兩邊都是文案，沒有東西會替你報錯。")

    # 因子不全（研判被抑制）—— 就是踩到這個坑的那個狀態。
    from services.liquidity_engine import (
        STRESS_FACTORS as _SF, compute_liquidity_score as _cls)
    _one = _cls({"XCCY_PROXY": {"zscore": 2.5}})
    _sess = _loaded_session()
    _sess[_page._SK_LIQ] = ({"XCCY_PROXY": {"zscore": 2.5, "value": 2.5}}, _one)
    _check(_render_all_text(_sess), "因子不全")

    # 因子齊全（研判照印）—— 確認本條不是只在一種狀態下成立。
    _three = _cls({_k: {"zscore": 2.5} for _k in _SF})
    _sess2 = _loaded_session()
    _sess2[_page._SK_LIQ] = ({_k: {"zscore": 2.5, "value": 2.5} for _k in _SF},
                             _three)
    _check(_render_all_text(_sess2), "因子齊全")


def test_the_exceptions_card_reports_the_real_radar_counts():
    """「⚡ ③ 例外」卡印出來的 🔴／🟡 必須是**真的計數**，不是恆 0。

    ⛔ **2026-09-06 獨立稽核指出：修 1 是三個修復裡唯一沒有行為測試的。**
    它的保護當時**全是 AST 計數**（「讀了 `_SK_RADAR` 就要在同一個函式裡
    呼叫 `summarize_radar`」），而那條規則自己的 docstring 就寫著它擋不住
    「**彙總了但沒用它的結果**」—— 那正是一條**可以直接走回原 bug** 的路。

    **稽核的突變（實測）**：保留 `_radar_lit(_sum)` 這個呼叫但丟掉結果、
    把 `_lit` 寫死成 10 →

        MUT 全⬜ → 短線雷達 🔴 0 ／ 🟡 0（10/10 盞有讀數）。
        228 passed, 32 skipped   ← 零紅燈

    **原 bug 的輸出（🔴 0）＋ 一個全新的假數字（全 ⬜ 卻說 10/10 盞有讀數），
    全套一條都不紅。** 既有的 `test_an_all_grey_radar_is_never_reported_as_calm`
    只斷言 `"平靜" not in _blob`，看不到這個。

    **突變會紅**：把 `_card_exceptions()` 的 `summarize_radar()` 拿掉、
    改回直接讀原始 dict 的 `red` → 本條紅（正向那半）；
    把 `_lit` 寫死成非零讓全 ⬜ 也報數字 → 本條紅（反方向那半）。

    ⚠️ **擋不到**：`_card_exceptions()` 以外的消費端（本條只驗這一張卡的輸出）、
    以及 `summarize_radar()` 自己數錯的情形（那是服務層的事）。
    """
    from services.risk_radar import summarize_radar as _sr

    # ── 正向：4 紅 3 黃 3 綠 → 卡片必須印出真的計數。
    def _lamp(sig):
        return {"signal": sig, "value": None, "prev": None,
                "note": "", "label": "—", "trend": []}
    _mixed = {}
    for _i in range(4):
        _mixed[f"r{_i}"] = _lamp("🔴 危險")
    for _i in range(3):
        _mixed[f"y{_i}"] = _lamp("🟡 注意")
    for _i in range(3):
        _mixed[f"g{_i}"] = _lamp("🟢 正常")
    # 前提鎖：服務層今天真的算得出 4／3。前提沒了本條就該重寫，不是靜靜變綠。
    _sum = _sr(_mixed)
    assert (_sum["red"], _sum["yellow"]) == (4, 3), (
        f"前提變了：`summarize_radar()` 對 4 紅 3 黃已不回 (4, 3)：{_sum}")

    _sess = _loaded_session()
    _sess[_page._SK_RADAR] = _mixed
    _blob = _render_all_text(_sess)
    assert "🔴 4" in _blob and "🟡 3" in _blob, (
        "「⚡ ③ 例外」卡沒有印出真的雷達計數。\n"
        "⛔ `_SK_RADAR` 存的是**原始 10 燈**（key 是 `vix_level` / `hy_oas_delta` / …），"
        "直接對它 `.get('red', 0)` 不會報錯，只會**恆得 0** —— "
        "10 燈全紅的極端警報，畫面照樣印「🔴 0」。\n"
        f"整頁實際印出（節錄）：{_blob[:800]!r}")

    # ── 反方向：全 ⬜ → **不得**印出「🔴 0」這種看起來像讀數的數字。
    #    沒有這一半，「永遠報 0」與「永遠報一個寫死的數」都會全綠。
    _all_grey = {f"s{_i}": _lamp("⬜ 無資料") for _i in range(10)}
    _sess2 = _loaded_session()
    _sess2[_page._SK_RADAR] = _all_grey
    _blob2 = _render_all_text(_sess2)
    assert "🔴 0" not in _blob2, (
        "10 燈一盞都沒取到，畫面卻印「🔴 0」—— "
        "那是把「沒有量到」講成「量到 0 個」（§1）。\n"
        f"整頁實際印出（節錄）：{_blob2[:800]!r}")
    assert "一盞都沒有取到讀數" in _blob2, (
        f"全 ⬜ 時沒有誠實說明「沒取到」：{_blob2[:800]!r}")


def test_the_ai_remedy_names_the_button_that_is_actually_rendered():
    """🤖 AI 那一站的「去哪補」必須指到**當下真的印出來的那顆送出鈕**。

    ⚠️ **本條是 2026-09-05 稽核 F5 的替代覆蓋，不是額外裝飾。**
    F5 之前那句指路是**手抄的字面值**（`… → 上方「▶️ 生成 AI 總結」`），
    靠跨檔規則 `test_every_where_names_something_that_exists_on_screen`
    以 `「」` 內的字面值去比對。把手抄改成共用變數之後，**那條規則看不到這一站了**
    （它是字面值 opt-in）。本條把那份覆蓋補回來，而且**更強**：
    它比對的是**執行期側錄到的送出鈕字**，不是原始碼裡的字面值 ——
    有人把 `submit_label` 換成別的變數、或讓兩邊指向不同常數，本條都會紅。

    **突變會紅**：把 `where=` 裡的 `{_ai_label}` 換回任何一個寫死的字面值
    （即使今天剛好一樣），只要它與送出鈕當下的字不同就紅；
    把送出鈕的 `submit_label` 換成另一個常數而指路不動 → 也紅。
    """
    # 沒有生成過 → 送出鈕應該是「第一次」那個字，指路也該指同一個字。
    _segs = _render_segments({_page._SK_IND: {"VIX": {"value": 24.1}}})
    _ai = _segs["🤖 AI 景氣判斷總結"]

    assert _page._AI_BTN_FIRST in _ai, (
        f"沒生成過時，AI 那一塊應該印出送出鈕「{_page._AI_BTN_FIRST}」，"
        f"實際印出的內容：{_ai[:400]!r}")
    assert f"上方「{_page._AI_BTN_FIRST}」" in _ai, (
        "AI 的灰態指路沒有指到當下這一輪實際印出來的那顆鈕 —— "
        "指路與按鈕分岔了（本 repo 同型 bug 已發作三次，"
        "見 `ui/helpers/story_nav.py` 的 `RETIRED_TAB_LABELS`）。\n"
        f"該塊實際印出的內容：{_ai[:400]!r}")

    # 反向：已經生成過 → 兩邊要一起變成「重新生成」那個字。
    _segs2 = _render_segments({_page._SK_IND: {"VIX": {"value": 24.1}},
                               _page._SK_AI: "（已生成過的內容）"})
    _ai2 = _segs2["🤖 AI 景氣判斷總結"]
    assert _page._AI_BTN_AGAIN in _ai2, (
        f"已生成過時，送出鈕應該變成「{_page._AI_BTN_AGAIN}」，"
        f"實際：{_ai2[:400]!r}")
    assert _page._AI_BTN_FIRST not in _ai2, (
        "已生成過，畫面上卻還留著「第一次」那個字 —— 兩個字同時出現會讓使用者不知道按哪顆")
