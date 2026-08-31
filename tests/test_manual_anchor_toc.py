"""📖 說明書（`ui/tab6_manual.py`）「10 個子分頁 → 單頁錨點目錄」的守衛。

線框（客戶 2026-08-31 拍板）：`docs/wireframes/fund-wireframe-final.html`
§03 PAGE 5「E · 📖 說明書」，逐字兩項：

> **改法**：「10 個主題改為錨點目錄……頁首的『📊 資料來源完整地圖』置頂不動」
> **gone**：「說明書內的三套編號 —— 子分頁用 `1.~10.`、內文用 `①~⑨`
>           （第 10 個沒編號）、頁首另有 `⓪` —— 同一頁三套。改用純標題階層」

## 方法（沿用本 repo 已實證的兩把尺）

1. **AST（結構）** —— 「有沒有再開一層 `st.tabs`」「每一章有沒有被畫」這種
   **只有形狀能表達**的規則。⚠️ 一律 **alias 不敏感**：本 repo 有
   `import streamlit as _st_mod` 這種寫法（`ui/helpers/macro/ndc.py`），
   寫死 `st.tabs` 的字串 grep **結構上掃不到它**。
2. **行為（sentinel 渲染）** —— 「目錄列的錨點」與「實際畫出來的 `st.subheader`
   錨點」是不是同一組。AST 在這裡不夠：目錄是 for-loop 產生的，
   靜態看不出它最後吐出哪幾個連結。

## ⚠️ 一件必須誠實講的事：**本檔的守衛涵蓋不到「章名與目錄短標漂移」**

~~`ui/tab6_manual.py::_CHAPTERS` 是**單一出處** —— 目錄由它 for-loop 產生、~~
~~標題由 `_chapter()` 讀它產生。也就是說「改了章節名卻忘了改目錄」這個 bug~~
~~**在結構上已經不可能發生**，因此**沒有對應的突變可以讓任何一條轉紅**。~~

→ **2026-08-31 就地更正：上面那句絕對語是假的，已被突變證偽**
（**有意識的更正，不是漏刪** · 決策者：**AI 總管** · 依據：**實測突變**）。
**舊表述有一半是對的，那一半保留**：`_CHAPTERS` 確實是單一出處，目錄與標題確實
都從它產生，繞過它另寫一份 `st.subheader(..., anchor=...)` 確實會被本檔擋下。
**錯的是它把「一張表」等同於「一套字」**：`_CHAPTERS` 的**第 2 欄（目錄短標）**
與**第 3 欄（章節標題）本來就是兩套不同的字**，同一列改一欄不改另一欄，
在結構上**完全做得到**。

**突變實證（2026-08-31 實跑）**：只把 `("weather", …)` 那列的**第 3 欄**改成
`"🛰️ 完全不同的一章"`、**第 2 欄仍寫「🌤️ 景氣天氣」** → 目錄與實際章名當場對不起來，
而 `tests/test_manual_anchor_toc.py` + `tests/test_tab6_manual.py` **12 passed, 1 skipped 全綠**。

→ **正確的說法**：**結構上不可能漂移的是 `anchor` / `key`**（它們由同一欄 `key` 導出，
`_anchor()` 對未知 key 直接 `KeyError`）；**人看的標籤（目錄短標 ⇄ 章節標題）沒有這個保證**。
本檔對後者是**未涵蓋**，既不是「設計上已消除」，也不是「守衛上有涵蓋」——**就是沒守**。
⚠️ 本輪**刻意不為它加守衛**（那是另一個 scope，`CLAUDE.md §8.4 步驟 4`）；
本次只把敘述改成真的。**留著那句絕對語，會讓下一個人以為這裡有保護。**

本檔能擋的是**復辟形態**：有人繞過 `_CHAPTERS` 另外手寫一個
`st.subheader(..., anchor=...)`，或把某一章的 `_chapter()` 呼叫刪掉／漏掉。
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANUAL = ROOT / "ui" / "tab6_manual.py"


def _tree() -> ast.Module:
    return ast.parse(MANUAL.read_text(encoding="utf-8"))


def _docstring_ids(tree: ast.Module) -> set:
    """module / class / function 的 docstring 節點 id —— 掃描一律排除。

    理由與 `tests/test_wpf_five_tab_wiring.py` 同：docstring 與註解是**講歷史**的
    地方（本 repo 慣例「舊條文保留不刪 + 加刪除線 + 兩邊理由並陳」），
    把它們算進掃描等於禁止記錄歷史。註解不進 AST，天然排除。
    """
    _out: set = set()
    for _n in ast.walk(tree):
        if isinstance(_n, (ast.Module, ast.FunctionDef,
                           ast.AsyncFunctionDef, ast.ClassDef)):
            _b = getattr(_n, "body", None)
            if (_b and isinstance(_b[0], ast.Expr)
                    and isinstance(_b[0].value, ast.Constant)
                    and isinstance(_b[0].value.value, str)):
                _out.add(id(_b[0].value))
    return _out


def _live_strings(tree: ast.Module):
    _docs = _docstring_ids(tree)
    for _n in ast.walk(tree):
        if (isinstance(_n, ast.Constant) and isinstance(_n.value, str)
                and id(_n) not in _docs):
            yield _n.value, _n.lineno


# ══════════════════════════════════════════════════════════════════
# 1) 巢狀分頁不得復辟
# ══════════════════════════════════════════════════════════════════
def test_manual_has_no_nested_tabs():
    """`ui/tab6_manual.py` 內 `tabs(...)` 呼叫數必須是 **0**。

    為什麼這條是本批的核心：說明書是**全站唯一的三層巢狀分頁**（線框原文）。
    ⑤ 合併頁已經把 `st.tabs` 鎖成 0（`tests/test_settings_diag_merge.py`），
    但那條**只看 `ui/tab_settings_diag.py`** —— 說明書自己再開一層它抓不到。

    ⚠️ **alias 不敏感**：比對的是「屬性名叫 `tabs`」與「裸呼叫 `tabs(...)`
    且 `tabs` 是從 streamlit import 進來的」，**不比對模組別名**。
    寫死 `st.tabs` 的檢查會被 `import streamlit as _st_mod` 整個繞過
    （本 repo 真的有這種寫法，見 `ui/helpers/macro/ndc.py`）。

    突變實驗：在本檔任何位置加一行 `_x = st.tabs(["a", "b"])`
    或 `_st2 = streamlit; _x = _st2.tabs(["a"])` → **本條轉紅**。
    """
    _t = _tree()
    # `from streamlit import tabs [as X]` → 裸呼叫也要抓
    _bare: set = set()
    for _n in ast.walk(_t):
        if isinstance(_n, ast.ImportFrom) and (_n.module or "").startswith("streamlit"):
            for _a in _n.names:
                if _a.name == "tabs":
                    _bare.add(_a.asname or _a.name)

    _hits: list[str] = []
    for _n in ast.walk(_t):
        if not isinstance(_n, ast.Call):
            continue
        _f = _n.func
        if isinstance(_f, ast.Attribute) and _f.attr == "tabs":
            _hits.append(f"{MANUAL.name}:{_n.lineno} {ast.unparse(_f)}(...)")
        elif isinstance(_f, ast.Name) and _f.id in _bare:
            _hits.append(f"{MANUAL.name}:{_n.lineno} {_f.id}(...)")

    assert not _hits, (
        "說明書又開了子分頁：\n  " + "\n  ".join(_hits) +
        "\n線框（客戶 2026-08-31 拍板）要求說明書是**單頁 + 錨點目錄**；"
        "在 ⑤ 之下再開一層 = 把三層巢狀分頁原封裝回去。")


# ══════════════════════════════════════════════════════════════════
# 2) 目錄 ⇔ 章節：雙向對得上（行為面）
# ══════════════════════════════════════════════════════════════════
class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _ColumnConfig:
    def __getattr__(self, _name):
        return lambda *a, **k: None


class _FakeSt:
    """寬鬆的假 streamlit：記錄呼叫，其餘一律 no-op 並回可當 context 的物件。

    刻意用 `__getattr__` 全包而不是逐一列舉 API —— 本檔渲染路徑會用到
    `markdown / caption / subheader / dataframe / divider / expander /
    container / warning / info / plotly_chart / session_state / column_config`，
    逐一列舉的清單日後一定漏（那正是本 repo 白名單守衛失效的同一種病）。
    """

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.session_state: dict = {}
        self.column_config = _ColumnConfig()

    def __getattr__(self, name):
        def _f(*a, **k):
            self.calls.append((name, a, k))
            return _Ctx()
        return _f


@pytest.fixture()
def rendered(monkeypatch):
    """把 `ui/tab6_manual.py` 整頁渲染一次，回傳呼叫紀錄。"""
    import ui.helpers.render_state as _rs
    import ui.tab1_macro as _t1
    import ui.tab6_manual as _m

    _fake = _FakeSt()
    monkeypatch.setattr(_m, "st", _fake)
    # `not_ready()` 住在 render_state，它自己 import streamlit → 一起換掉，
    # 否則 ⬜ 灰字會打到真 streamlit（測不到，也可能噴 runtime warning）。
    monkeypatch.setattr(_rs, "st", _fake)
    # 第 9 章復用 Tab1 的指標地圖；本檔不測它，換成 sentinel 避免拉起整頁。
    monkeypatch.setattr(_t1, "render_indicator_map",
                        lambda: _fake.calls.append(("indicator_map", (), {})))
    _m.render_manual_tab()
    return _fake


def _toc_anchors(fake: _FakeSt) -> list[str]:
    _toc = [a[0] for n, a, _k in fake.calls
            if n == "markdown" and a and isinstance(a[0], str) and "📑 目錄" in a[0]]
    assert len(_toc) == 1, f"目錄應該恰好畫一次，實際 {len(_toc)} 次"
    return re.findall(r"\]\(#([^)]+)\)", _toc[0])


def _subheader_anchors(fake: _FakeSt) -> list[str]:
    return [k["anchor"] for n, _a, k in fake.calls
            if n == "subheader" and k.get("anchor")]


def test_toc_and_sections_agree(rendered):
    """目錄列的每個 anchor 都要有對應的 `st.subheader(anchor=...)`，**且反之亦然**。

    這條擋的是兩個方向：
    - **目錄有、章節沒有** → 使用者點了不會動（最惡劣：畫面沒有任何錯誤訊息）；
    - **章節有 anchor、目錄沒列** → 一個進不去的章節（新增章節時最常見的漏）。

    突變實驗 A：把 `_render_toc()` 的 for-loop 改成 `_CHAPTERS[:-1]`（少列一章）
    → **本條轉紅**（章節有 anchor、目錄沒列）。
    突變實驗 B：把任一 `_chapter("...")` 呼叫刪掉 → **本條轉紅**（目錄有、章節沒有）。
    """
    from ui.tab6_manual import _CHAPTERS, _anchor

    _toc = _toc_anchors(rendered)
    _sub = _subheader_anchors(rendered)
    _want = [_anchor(_k) for _k, _, _ in _CHAPTERS]

    assert _toc == _want, f"目錄的 anchor 與 `_CHAPTERS` 不符\n目錄={_toc}\n應為={_want}"
    assert _sub == _want, (
        "實際畫出來的 `st.subheader` anchor 與 `_CHAPTERS` 不符 —— "
        f"有章節沒畫、或有人手寫了額外的 anchor\n畫出={_sub}\n應為={_want}")


def test_chapter_titles_are_rendered_verbatim(rendered):
    """`_CHAPTERS` 的第三欄（章節標題）必須逐字出現在 `st.subheader` 的第一個參數。

    突變實驗：把 `_chapter()` 改成 `st.subheader(key, anchor=...)`（畫 key 不畫標題）
    → **本條轉紅**。
    """
    from ui.tab6_manual import _CHAPTERS

    _titles = [a[0] for n, a, _k in rendered.calls if n == "subheader" and a]
    for _k, _, _title in _CHAPTERS:
        assert _title in _titles, f"章節 {_k!r} 的標題沒有被畫出來：{_title!r}"


def test_data_map_stays_pinned_above_the_toc(rendered):
    """「📊 資料來源完整地圖」必須**置頂**，排在目錄之前（線框：「置頂不動」）。

    突變實驗：把 `_render_toc()` 搬到資料地圖之前 → **本條轉紅**。
    """
    _order = [(_i, _n, _a) for _i, (_n, _a, _k) in enumerate(rendered.calls)]
    _map_at = next(_i for _i, _n, _a in _order
                   if _n == "subheader" and _a and "資料來源完整地圖" in _a[0])
    _toc_at = next(_i for _i, _n, _a in _order
                   if _n == "markdown" and _a and isinstance(_a[0], str)
                   and "📑 目錄" in _a[0])
    assert _map_at < _toc_at, (
        f"資料來源完整地圖（第 {_map_at} 個呼叫）跑到目錄（第 {_toc_at} 個）後面了 —— "
        "線框逐字要求它「置頂不動」。")


# ══════════════════════════════════════════════════════════════════
# 3) 每一章都要真的被畫（AST，擋「加了 `_CHAPTERS` 卻忘了呼叫」）
# ══════════════════════════════════════════════════════════════════
def test_every_chapter_key_is_called_once_in_order():
    """原始碼裡的 `_chapter("<key>")` 呼叫，必須與 `_CHAPTERS` 同集合、同順序、各一次。

    與上面的行為條**不重複**：行為條驗「跑起來畫了什麼」，本條驗「原始碼長什麼樣」。
    兩者的差別在有人用迴圈／條件式把某一章藏在 `if` 底下時會分岔 ——
    那時行為條在某些狀態下仍會綠，本條當場紅。

    突變實驗：把 `_chapter("weather")` 改成 `_chapter("macro-score")`（重複一章）
    → **本條轉紅**。
    """
    from ui.tab6_manual import _CHAPTERS

    _calls = [_n.args[0].value for _n in ast.walk(_tree())
              if isinstance(_n, ast.Call)
              and isinstance(_n.func, ast.Name) and _n.func.id == "_chapter"
              and _n.args and isinstance(_n.args[0], ast.Constant)]
    _want = [_k for _k, _, _ in _CHAPTERS]
    assert _calls == _want, (
        f"`_chapter()` 的呼叫序列與 `_CHAPTERS` 不符\n呼叫={_calls}\n應為={_want}")


# ══════════════════════════════════════════════════════════════════
# 4) 三套編號不得復辟
# ══════════════════════════════════════════════════════════════════
#: 線框點名的三套編號用到的圈號（`⓪` 頁首、`①~⑨` 內文、`1.~10.` 子分頁）。
_CIRCLED = "⓪①②③④⑤⑥⑦⑧⑨⑩"


def test_no_circled_numbering_on_manual_headings():
    """章節標題（`_CHAPTERS` 第 2、3 欄）與頁首標題不得帶圈號或 `N.` 編號。

    ⚠️ 掃描範圍**刻意只到標題**，不到內文：內文的圈號很多是**列表項的一部分**
    （例：第 ⑧ 章表格內的「① 上傳 CSV ② 補全 ③ 累積狀態」），
    那是敘述，不是線框要收的「頁面編號體系」。把內文一起掃會逼出一堆假紅。

    ⚠️ **`where_to_find()` 產生的站號 `①~⑤` 不在此列** —— 那是**頂層分頁站號**，
    線框第 04 節明說要保留（「頂層：① ~ ⑤ 決策站號」），收掉的是**頁內**那幾套。
    本條只看 `_CHAPTERS` 的字面值與 `st.subheader` 的字面第一參數，
    站號來自函式回傳值、掃不到，兩者天然分開。

    突變實驗：把 `_CHAPTERS` 任一標題改回 `"### ① 🧮 AI Macro Score …"` 形式
    （或只是加回 `①`）→ **本條轉紅**。
    """
    from ui.tab6_manual import _CHAPTERS

    _bad: list[str] = []
    for _k, _toc, _title in _CHAPTERS:
        for _label, _txt in (("目錄短標", _toc), ("章節標題", _title)):
            if any(_c in _txt for _c in _CIRCLED):
                _bad.append(f"{_k} 的{_label}帶圈號：{_txt!r}")
            if re.match(r"^\s*\d+\.\s", _txt):
                _bad.append(f"{_k} 的{_label}帶 `N.` 編號：{_txt!r}")

    # 頁首那張表的標題（`st.subheader` 的字面第一參數）同樣不准帶編號。
    for _n in ast.walk(_tree()):
        if (isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
                and _n.func.attr == "subheader" and _n.args
                and isinstance(_n.args[0], ast.Constant)
                and isinstance(_n.args[0].value, str)):
            _t = _n.args[0].value
            if any(_t.lstrip().startswith(_c) for _c in _CIRCLED):
                _bad.append(f"{MANUAL.name}:{_n.lineno} subheader 帶圈號：{_t!r}")

    assert not _bad, (
        "說明書的頁內編號又長回來了：\n  " + "\n  ".join(_bad) +
        "\n線框 §03/§04：頁內改用**純標題階層**，圈號只保留給頂層分頁站號。")


# ══════════════════════════════════════════════════════════════════
# 5) 空狀態的顏色語意（🔵 藍框不得裝「未載入」）
# ══════════════════════════════════════════════════════════════════
#: 「未載入／未設定」這一族的字樣。命中即代表那句話屬 ⬜ 灰色說明，
#: 不該住在 `st.info()`（🔵）裡（`ui/helpers/render_state.py` 五態 SSOT）。
_NOT_READY_WORDS = re.compile(r"尚未載入|未載入|請先載入|尚未設定|還沒載入")


def _string_args(call: ast.Call):
    """一個 Call 的所有**字面字串**參數（含 f-string 內的字面片段）。"""
    for _a in list(call.args) + [_k.value for _k in call.keywords]:
        for _s in ast.walk(_a):
            if isinstance(_s, ast.Constant) and isinstance(_s.value, str):
                yield _s.value


def test_st_info_does_not_carry_not_ready_semantics():
    """`st.info()`（🔵）不得裝 ⬜ 標記、也不得裝「未載入」這一族的句子。

    客戶 2026-08-28 拍板（空狀態線框 §03「顏色：三態統一規則」）：
    **「未載入／未設定」一律改灰色說明**。本條把它在說明書這一頁上機器化。

    兩個判準是**互補**的，不是同義：
    - 帶 `⬜` → 同一句話同時穿兩件衣服（🔵 的框 + ⬜ 的標記），本身就是矛盾；
    - 帶「未載入」字樣 → 就算沒寫 ⬜，語意仍屬 ⬜ 那一族。
      （本批修掉的**三個訊息**裡，有兩個是這一種 —— 只驗 ⬜ 會漏掉它們。）

    ⚠️ **「三處」是三個「訊息」，不是三個「呼叫點」（2026-08-31 就地精確化）**：
    `cc37709` 上是 **4 個 `st.info` 呼叫點 / 3 個相異訊息** ——
    `_no_data_msg` 這一個訊息**被兩個呼叫點共用**（§ C 歷史對照圖、§ D 加扣分明細），
    另兩個是「📡 請先載入總經資料以顯示歷史對照圖」與「⬜ 沒有可用的指標資料」。
    **本條掃的是呼叫點**（AST 走訪每一個 `*.info(...)`），所以兩種算法都不影響它會不會紅；
    寫清楚只是為了讓「三處」不再需要讀者自己猜是哪一種計數。

    突變實驗：把 `not_ready("沒有可用的指標資料")` 改回
    `st.info("⬜ 沒有可用的指標資料")` → **本條轉紅**（⬜ 判準）。
    突變實驗：把 `not_ready(_no_data_msg, where=_no_data_where)` 改回
    `st.info("📡 尚未載入總經資料 …")` → **本條轉紅**（字樣判準）。
    """
    from ui.helpers.render_state import NOT_READY_MARK

    _bad: list[str] = []
    for _n in ast.walk(_tree()):
        if not (isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
                and _n.func.attr == "info"):
            continue
        for _s in _string_args(_n):
            if NOT_READY_MARK in _s:
                _bad.append(f"{MANUAL.name}:{_n.lineno} st.info 帶 {NOT_READY_MARK}：{_s[:50]!r}")
            elif _NOT_READY_WORDS.search(_s):
                _bad.append(f"{MANUAL.name}:{_n.lineno} st.info 裝「未載入」語意：{_s[:50]!r}")

    assert not _bad, (
        "🔵 藍框裝了 ⬜ 的東西：\n  " + "\n  ".join(_bad) +
        "\n改走 `ui.helpers.render_state.not_ready(...)`（⬜ 灰色說明）。")


def test_not_ready_messages_do_not_double_the_mark():
    """`not_ready()` 自己會加 ⬜ → 訊息本體不得再自帶一個（否則畫面上兩個 ⬜）。

    突變實驗：把 `not_ready("沒有可用的指標資料")` 改成
    `not_ready("⬜ 沒有可用的指標資料")` → **本條轉紅**。
    """
    from ui.helpers.render_state import NOT_READY_MARK

    _bad: list[str] = []
    for _n in ast.walk(_tree()):
        if not (isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name)
                and _n.func.id == "not_ready"):
            continue
        for _s in _string_args(_n):
            if NOT_READY_MARK in _s:
                _bad.append(f"{MANUAL.name}:{_n.lineno} {_s[:50]!r}")
    assert not _bad, "not_ready() 的訊息自帶 ⬜（會變成兩個）：\n  " + "\n  ".join(_bad)


# ══════════════════════════════════════════════════════════════════
# 6) 死指路：**粗體**分頁名 —— #744 兩條守衛都掃不到的形態
# ══════════════════════════════════════════════════════════════════
#: `**X** 分頁 / **X** Tab` —— markdown 粗體當引號用的指路寫法。
#: ⚠️ **這個形態 `tests/test_wpf_five_tab_wiring.py` 的兩條守衛都抓不到**（實測）：
#:   - 黑名單向比對的是完整標籤子字串，而「📊 總經」**從來不是任何一版的分頁名**
#:     （不在 `_TAB_LABELS`、不在 `RETIRED_TAB_LABELS`、不在 `MISWRITTEN_TAB_NAMES`）；
#:   - 形態向的 `_NAV_SHAPES` 三個 pattern **只認 `「」`／`『』` 引號**，
#:     `**📊 總經** Tab` 一個都不命中。
#: 這正是那份守衛 docstring 自己登記的盲點（「本檔 20 筆 `TabN` 過期指涉」）的一種。
#: ~~本條**只掃 `ui/tab6_manual.py`**（本批的檔案邊界）；把它全 repo 化屬另一批。~~
#: → **2026-08-31 已全 repo 化（`ui/**` + `app.py`）。有意識的政策變更，不是漏刪**
#:   （日期 **2026-08-31** · 決策者：**AI 總管**，屬 `CLAUDE.md §8.4 步驟 4` 的 scope 拍板，
#:    **不是執行組自行擴大**）。
#:   **舊範圍的理由仍然成立**：一批只動自己的檔案邊界，是 File Boundary 紀律。
#:   **被權衡掉的原因有三**：
#:   (a) **成本實測為零** —— 擴大後 `ui/**` + `app.py` 共 112 檔、**命中 0 處**，
#:       不需要任何豁免機制就是綠的（量測日 2026-08-31，指令見下方 docstring）；
#:   (b) 這個守衛補的是 #744 兩條守衛的**已知盲點**（粗體 markdown 形態），
#:       而那個盲點**存在於全 repo**，不只說明書；
#:   (c) 留在單檔＝下一個長在**別的 UI 檔**的死指路仍然沒人守。
#:   ⚠️ **不得**因此去改 #744 那兩條守衛的字表 —— 那份「誠實揭露 > 硬改字表」的判斷未被推翻。
_BOLD_NAV = re.compile(r"\*\*[^*\n]{1,24}\*\*[^\S\n]{0,2}(?:分頁|頁籤|Tab)(?![a-zA-Z0-9])")

#: 掃描範圍：`ui/**/*.py` + `app.py`（頂層 orchestrator 也會寫指路文案）。
_BOLD_NAV_ROOTS: tuple[pathlib.Path, ...] = tuple(
    sorted(ROOT.glob("ui/**/*.py"))) + (ROOT / "app.py",)


def test_no_bold_hardcoded_tab_name_in_manual():
    """`ui/**` 與 `app.py` 內不得用 `**X** 分頁 / **X** Tab` 的形式手寫分頁名。

    本批修掉的兩處就是這個形態（`**📊 總經** Tab`）——
    分頁列上從來沒有「📊 總經」，而 #744 的兩條守衛都掃不到它。

    ⚠️ **2026-08-31 就地更正：本條並沒有豁免機制**（**有意識的變更，不是漏刪** ·
    日期 **2026-08-31** · 決策者：**AI 總管**）。
    ~~舊寫法：「若某處確實不是指路（例如在講一張表的欄名），請具名豁免並寫理由」~~
    —— **實測：本測試的 `_bad` 沒有任何 allowlist，「具名豁免」在程式碼裡不存在。**
    **舊寫法的用意仍然成立**（不要為了讓一處誤判過關就放鬆 pattern）；
    **被權衡掉的是它的事實面** —— 它承諾了一個做不到的動作，
    而**第一個真誤判撞上時，最省事的路正好就是它自己下一句明文禁止的那條
    （把 pattern 改鬆）**。文件承諾一個不存在的機制，等於替違規鋪了唯一一條路。

    **真誤判撞上時的正確順序（三步，不得跳過第 1 步）**：
    1. **先判斷它到底是不是誤判** —— 這個 pattern 的設計就偏嚴，多數命中是真死指路；
    2. 確定**不是**指路（在講一張表的欄名、Google Sheet 的工作表、瀏覽器分頁、
       鍵盤 Tab 鍵）→ **那一刻才**建具名清單常數，比照
       `tests/test_wpf_five_tab_wiring.py::_LEGIT_EXEMPT` 的三欄形態
       （檔案 + needle + **理由**），並在 PR 描述寫理由；
    3. 若只是文案寫法不佳 → **改那句文案**，不是改守衛。
    ⛔ **三步之中沒有任何一步是放鬆 `_BOLD_NAV` 的 pattern** ——
       放鬆等於讓下一個同型 bug 也一起漏掉。
    ⚠️ 依 `CLAUDE.md §-1`（沒觸發不動工）**現在不預先建那個空清單**：
       量測日 2026-08-31 全射程 **0 命中、0 誤判**，先建一個空機制屬範圍擴大。

    **射程證據 A｜同字碰撞三族（2026-08-31 實測，目前皆未命中）**
    —— 之所以沒命中，**不是因為隔得遠，而是因為 pattern 在粗體與關鍵字之間
    只允許 0~2 個「空白字元」**：夾任何一個非空白字元（含全形標點）就不成立。
    - **Google Sheet 的「工作表」在本 repo 文案裡也叫「分頁」** ——
      `ui/helpers/v2_editor.py:299`（隔 7 字）、`ui/tab6_manual.py:617`（隔 7 字）、
      同檔 `:622`（同一段內最近的一處**只隔 3 字**：`…資料**：其他分頁`）；
    - **瀏覽器分頁** —— `ui/tab_batch_analysis.py:293`（隔 4 字，`**每檔即時存磁碟** → 關分頁`）、
      `:201`（隔 15 字）、`:372`（隔 34 字）；
    - **全 repo 最接近的一次** —— `ui/helpers/story_nav.py:238` 的
      `**頁內分區**不是分頁`：**只差「不是」兩個非空白字元**。

    **射程證據 B｜假想合法用法的實跑（稽核設計 11 例，本組 2026-08-31 逐例重跑）**
    —— **5 例會誤判**：`按 **Shift** Tab 回上一格`（鍵盤鍵）／
    `按 **Ctrl** + **Tab** 切換`／`匯出成 **CSV**Tab-separated 格式`／
    `這張表的 **來源** 分頁欄位說明`／`Google Sheet 的 **_policy_v2** 分頁`；
    **不誤判者包括**：`**重要**：請先按上方按鈕`／`**注意**：…`／`已載入 **12** 檔基金`。

    ⚠️ **A 與 B 是寫下來當射程證據，不是待辦事項。**
    2026-08-31 稽核已判定 B5 全 repo 化**沒有實質提高誤判率**
    （判準一字未改，且誤判密度最高的 `ui/tab6_manual.py` 本來就在射程內）。
    **不要為了讓上面那幾例不誤判而改 pattern** —— 那正是本段第一句在禁的事。

    ⚠️ **docstring 與註解天然不在射程內**（`_live_strings` 已排除 docstring；
    註解不進 AST）—— 本 repo 慣例「舊表述加刪除線保留」需要那個空間。

    **突變驗證（2026-08-31 實跑，兩條都轉紅）**：
    - 說明書內把 caption 改回 `"…需先在 **📊 總經** Tab 按…"` → 轉紅（原始突變）；
    - **在另一個 UI 檔**（`ui/sidebar.py`）塞一句 `"請到 **📊 總經** 分頁看"` → **轉紅**
      —— 這一條證明「全 repo 化」真的生效，不是只換了個寫法。

    **範圍量測（量測日 2026-08-31）**：`ui/**/*.py` + `app.py` 共 112 檔、**0 命中**。
    ⚠️ 「112 檔 / 0 命中」是**單組實測的快照**，會隨 repo 漂移；
    要複驗請直接跑本測試，**不要引用這行數字**。
    """
    _bad: list[str] = []
    for _path in _BOLD_NAV_ROOTS:
        if not _path.exists():          # app.py 若日後改名，測試不該假死
            continue
        _tree_p = ast.parse(_path.read_text(encoding="utf-8"))
        _rel = _path.relative_to(ROOT)
        for _txt, _ln in _live_strings(_tree_p):
            _m = _BOLD_NAV.search(_txt)
            if _m:
                _bad.append(f"{_rel}:{_ln} {_m.group(0)!r} in {_txt[:60]!r}")
    assert not _bad, (
        "用粗體手寫了分頁名（#744 的兩條守衛掃不到這個形態）：\n  "
        + "\n  ".join(_bad) +
        "\n改吃 `ui.helpers.story_nav.where_to_find()` / `tab_label()`。")
