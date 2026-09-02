"""五分頁 IA 第三批守衛 —— ① 市場總覽的載入表單 ＋ ③ 標的探索的四個缺口。

對應客戶拍板線框（**規範性文件**，只讀不改）：

===== ============================================ ==========================
編號   線框依據                                      本檔守的東西
===== ============================================ ==========================
T2     `wireframe-macro-health.html` **Form ①-A**   ① 載入列收成一個 form
T9     `fund-empty-state-wireframe.html` ③ 「新增」  ③ 單檔深掘的空狀態
T13    `wireframe-fund-research.html` **決定 2/D5**  ③ 導覽只畫一次
T15    同上 **D3 / D4**                              兩模式口徑用字對齊
===== ============================================ ==========================

## 為什麼本檔盡量不寫 `"..." in src`

`tests/test_grp_health_checkup_order.py` 的兩條斷言都是字串比對，結果**被一條
永遠走不到的死分支餵飽**：綠燈綠了很久，而那個區塊在畫面上從來沒有出現過。
本檔因此一律走 **AST 結構斷言**（誰在誰的 `if` 裡、誰是不是函式 body 的直接子節點）
與 **runtime 行為斷言**（真的呼叫 `story_nav` / `classify_base` 看它回什麼），
只有在真的沒有結構可以抓時才退回字串，並就地寫明它守不到什麼。

## ⚠️ 本檔守不到的（據實列出，不要讀成已全覆蓋）

- **瀏覽器裡的實際版面**：欄寬、窄螢幕折行、`st.form` 送出後的真實 rerun 次數。
  本檔全部在 AST 與純函式層，**沒有跑起一個 Streamlit runtime**。
- **`st.form` 內的 widget 真的不觸發 rerun** —— 那是 Streamlit 的行為，
  本 repo 無法在單元測試裡驗；本檔只能驗「有沒有包」與「送出結果有沒有被拿去 gate」。
- **文案是否通順 / 使用者看不看得懂**。
- **`_want_*` 勾掉之後下游面板的實際渲染**（例如沒抓雷達時風險雷達區塊長什麼樣）——
  那要整頁 render，超出本批範圍。

⚠️ 本檔由實作組單組產出，**未經第二組獨立複驗**（`CLAUDE.md §-2` 規則 6）。
突變與反向對照的實跑輸出記在 PR 描述，**不在這裡自我宣稱**。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

TAB1 = ROOT / "ui" / "tab1_macro.py"
TAB2 = ROOT / "ui" / "tab2_single_fund.py"
TAB_RESEARCH = ROOT / "ui" / "tab_fund_research.py"
TAB_BATCH = ROOT / "ui" / "tab_batch_analysis.py"
UNIFIED = ROOT / "ui" / "helpers" / "fund_grp_health" / "unified.py"
SIGNALS = ROOT / "ui" / "helpers" / "fund_grp_health" / "signals.py"


# ── 共用小工具 ────────────────────────────────────────────────────────
def _tree(path: pathlib.Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _func(path: pathlib.Path, name: str) -> ast.FunctionDef:
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{path.name} 找不到函式 {name}() —— 是不是改名了？"
                         "改名不是壞事，但本檔的錨點要跟著更新。")


def _calls(node: ast.AST, name: str) -> list[ast.Call]:
    """子樹裡所有呼叫 `name(...)` 的節點（含 `x.name(...)` 這種屬性呼叫）。"""
    out = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            _n = getattr(sub.func, "id", None) or getattr(sub.func, "attr", None)
            if _n == name:
                out.append(sub)
    return out


def _enclosing_tests(node: ast.AST, func: ast.FunctionDef) -> list[str]:
    """`node` 外層每一個 `if` / `IfExp` 的條件，unparse 成字串。

    用來回答「這一行是被什麼條件擋住的」—— 那才是行為，字串比對答不出來。
    """
    parents: dict[int, ast.AST] = {}
    for _p in ast.walk(func):
        for _c in ast.iter_child_nodes(_p):
            parents[id(_c)] = _p
    out: list[str] = []
    cur: ast.AST = node
    while id(cur) in parents:
        parent = parents[id(cur)]
        if isinstance(parent, ast.If) and cur not in parent.orelse:
            out.append(ast.unparse(parent.test))
        elif isinstance(parent, ast.IfExp):
            out.append(ast.unparse(parent.test))
        cur = parent
    return out


# ══════════════════════════════════════════════════════════════════════
# T2 · ① 市場總覽：載入列收成一個 form（線框 Form ①-A）
# ══════════════════════════════════════════════════════════════════════
def test_macro_load_row_has_no_bare_button():
    """載入列不得再是**裸** `st.button` —— 那正是線框點名「使用者常誤按兩次」的形狀。

    ⚠️ 這條是 `==0` 而不是「不得含某個 key」：換個 key 名字就繞過的守衛沒有意義。
    `render_macro_tab()` 目前**一顆 `st.button` 都不該有**（送出鈕由
    `applied_form()` 內的 `st.form_submit_button` 產生）。
    """
    _f = _func(TAB1, "render_macro_tab")
    _btns = [ast.unparse(c)[:70] for c in _calls(_f, "button")]
    assert not _btns, (
        "`render_macro_tab()` 又出現裸 `st.button` —— 載入列必須包在 "
        "`applied_form()` 裡（線框 `wireframe-macro-health.html` Form ①-A）：\n  "
        + "\n  ".join(_btns))


def test_macro_load_is_gated_by_the_form_submit():
    """`_do_load` 必須來自 `applied_form()` 的 gate，而且**不得**在別處被設成 True。

    這條擋的是本 repo 已經實證過的那種「form 還在、但已經不 gate 了」的退化
    （`tests/test_ui_rerun_contract.py` 檔頭盲點：`if st.button(...) or True:`）。
    """
    _f = _func(TAB1, "render_macro_tab")
    _withs = [w for w in ast.walk(_f)
              if isinstance(w, ast.With)
              and any(_calls(i.context_expr, "applied_form") for i in w.items)]
    assert len(_withs) == 1, (
        f"`render_macro_tab()` 內的 `with applied_form(...)` 有 {len(_withs)} 個，"
        "預期剛好 1 個（線框：一個 form ＋ 一顆送出鈕）。")
    _gate_names = {i.optional_vars.id for i in _withs[0].items
                   if isinstance(i.optional_vars, ast.Name)}
    assert _gate_names, "`applied_form()` 的回傳 gate 沒有被 `as` 接住 —— 那就沒有東西可以 gate。"

    _assigns = [n for n in ast.walk(_f) if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "_do_load" for t in n.targets)]
    assert len(_assigns) == 1, (
        f"`_do_load` 被指派了 {len(_assigns)} 次。線框要的是「按下送出鈕才載入」；"
        "多一次指派（例如舊的 `_do_load = True`）就等於 gate 形同虛設。")
    _rhs = ast.unparse(_assigns[0].value)
    assert any(g in _rhs for g in _gate_names), (
        f"`_do_load` 的來源是 {_rhs!r}，不是 `applied_form()` 的 gate。")


@pytest.mark.parametrize("fetcher, flag", [
    ("fetch_all_indicators", "_want_ind"),
    ("fetch_market_news", "_want_news"),
    ("detect_risk_radar", "_want_radar"),
    ("detect_turning_points", "_want_tp"),
])
def test_each_macro_source_is_gated_by_its_own_checkbox(fetcher: str, flag: str):
    """四路取數各自被自己那個勾選框擋住 —— **沒勾的那一路根本不 submit**。

    ⚠️ 這是**行為**斷言不是字串比對：它問的是「這個 `submit()` 外層有哪些條件」。
    把勾選框畫出來卻不接線（四個 checkbox 一字不差、四路照樣全抓）→ **本條轉紅**。
    """
    _f = _func(TAB1, "render_macro_tab")
    _subs = [c for c in _calls(_f, "submit")
             if c.args and ast.unparse(c.args[0]) == fetcher]
    assert len(_subs) == 1, (
        f"預期 `{fetcher}` 剛好被 submit 一次，實際 {len(_subs)} 次。")
    _guards = " ".join(_enclosing_tests(_subs[0], _f))
    assert flag in _guards, (
        f"`{fetcher}` 的 submit 沒有被 `{flag}` 擋住（外層條件：{_guards!r}）——\n"
        "勾選框就變成裝飾品：使用者取消勾選，那一路照樣打出去。")


def test_freshness_stamp_only_when_indicators_were_really_refetched():
    """「上次抓取時間」只准在**真的重抓指標**時更新。

    這是本批最承重的一條：沿用舊指標卻蓋上新時間戳，上方時效列會顯示
    「✅ 已載入 · 剛剛」而數字是舊的 —— 捏造新鮮度（`CLAUDE.md §1` / §2.4）。
    """
    _f = _func(TAB1, "render_macro_tab")
    _hits = [n for n in ast.walk(_f) if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Attribute) and t.attr == "macro_last_update"
                     for t in n.targets)]
    assert _hits, "找不到 `macro_last_update` 的指派 —— 錨點失效，請更新本測試。"
    for _h in _hits:
        _guards = " ".join(_enclosing_tests(_h, _f))
        assert "_ind_fetched" in _guards, (
            "`macro_last_update` 的指派沒有被 `_ind_fetched` 擋住"
            f"（外層條件：{_guards!r}）—— 沒重抓卻蓋時間戳 ＝ 假的新鮮度。")


def test_news_session_write_is_gated_by_its_own_checkbox():
    """沒勾「新聞」時不得覆寫 `news_items` —— 覆寫成空清單會無聲清掉上次的結果。"""
    _f = _func(TAB1, "render_macro_tab")
    # ⚠️ 用**精確**的屬性名比對，不用 `endswith` —— 同一個函式裡另有一個
    # 區域變數 `_news_items`，`endswith("news_items")` 會把它一起抓進來
    # （初稿實測誤紅）。錨點寫窄一點，紅燈才代表真的有事。
    _hits = [n for n in ast.walk(_f) if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Attribute) and t.attr == "news_items"
                     for t in n.targets)]
    assert _hits, "找不到 `st.session_state.news_items` 的指派 —— 錨點失效，請更新本測試。"
    for _h in _hits:
        _guards = " ".join(_enclosing_tests(_h, _f))
        assert "_news_fetched" in _guards, (
            f"`news_items` 的指派沒有被 `_news_fetched` 擋住（外層條件：{_guards!r}）。")


def test_zero_indicator_message_separates_skipped_from_failed():
    """0 個指標時要分辨「本次沒勾」與「真的抓不到」—— 三態不得混色。

    沒勾 → ⬜ `not_ready()`（條件不足）；真的抓失敗 → 🔴 `st.error()`。
    只留一種畫法，就是把「你自己關掉的」講成「系統壞了」。
    """
    _f = _func(TAB1, "render_macro_tab")

    def _has(node, needle):
        return any(isinstance(k, ast.Constant) and isinstance(k.value, str)
                   and needle in k.value for k in ast.walk(node))

    # 找那條 if/elif 鏈：第一支必須以 `_ind_fetched` 分流，body 走 ⬜、orelse 走 🔴。
    _chains = [n for n in ast.walk(_f) if isinstance(n, ast.If)
               and "_ind_fetched" in ast.unparse(n.test)
               and any(_has(s, "沒有抓到任何總經指標") for s in n.orelse)]
    assert _chains, (
        "「0 個指標」只有一種畫法 —— 使用者自己取消勾選，卻被告知「NAS proxy 不通」。"
        "請用 `if not ind and not _ind_fetched: not_ready(...) elif not ind: st.error(...)` "
        "把「本次沒勾」與「真的抓不到」分開（三態不得混色）。")
    _chain = _chains[0]
    assert any(_calls(s, "not_ready") for s in _chain.body), (
        "「本次沒勾又沒有舊資料」那一支不是 ⬜ `not_ready()` —— 條件不足不該畫成系統故障。")
    assert any(_calls(s, "error") for s in _chain.orelse), (
        "「真的抓不到」那一支不是 🔴 `st.error()`。")


# ══════════════════════════════════════════════════════════════════════
# T9 · ③ 單檔深掘的空狀態（線框 fund-empty-state-wireframe.html）
# ══════════════════════════════════════════════════════════════════════
def _fd_if(func: ast.FunctionDef) -> ast.If:
    """函式 body **直接子節點**裡的 `if fd:`。

    刻意只找直接子節點：這同時是一個**可達性**論證 —— 它不在任何其他分支底下，
    只要 `render_single_fund_tab()` 跑起來就一定會被求值。
    （本 repo 剛被「永遠走不到的死分支餵飽字串守衛」咬過，故不接受巢狀命中。）
    """
    for stmt in func.body:
        if isinstance(stmt, ast.If) and ast.unparse(stmt.test) == "fd":
            return stmt
    raise AssertionError("`render_single_fund_tab()` 的頂層找不到 `if fd:` —— 錨點失效。")


def test_single_fund_has_a_reachable_empty_state():
    """`if fd:` **必須有 else**，而且那個 else 要走 IA 鐵則 04 的三要素元件。

    線框就地點名的現況：「`fund_data` 是 `None`（每個新 session 都是）時，
    輸入框以下**一個字都不印**」。那是每次開 App 進到 ③ 的第一個畫面。
    """
    _f = _func(TAB2, "render_single_fund_tab")
    _if = _fd_if(_f)
    assert _if.orelse, (
        "`if fd:` 又沒有 else —— 沒查過任何一檔時整頁空白，"
        "正是線框 `fund-empty-state-wireframe.html` 要補的那一塊。")
    _es = [c for s in _if.orelse for c in _calls(s, "empty_state")]
    assert len(_es) == 1, (
        f"空狀態分支裡的 `empty_state()` 有 {len(_es)} 個，預期 1 個。"
        "不要在這裡自己刻一套灰態 —— 灰色文案的 SSOT 是 `render_state.not_ready()`。")
    _kw = {k.arg for k in _es[0].keywords}
    assert len(_es[0].args) >= 2 and "where" in _kw, (
        "空狀態三要素缺一：要有**標題**、**缺什麼**（前兩個位置引數）與"
        "**去哪補**（`where=`）。少了「去哪補」，空狀態只是把消失換成灰色的消失。")


def test_empty_state_tells_the_three_steps():
    """三步驟必須真的寫出來（線框逐字：用關鍵字找代號 → 貼上網址／代碼 → 按 🚀 分析）。

    ⚠️ **這一條是字串比對，據實寫明它守不到什麼**：它只驗「三個步驟編號與三個
    關鍵動作的字出現在同一個 `empty_state()` 呼叫裡」，**不驗**文案通順、
    不驗畫面上真的長那樣。結構面（有沒有 else、有沒有走元件、三要素齊不齊）
    由上一條的 AST 斷言負責，兩條合起來才完整。
    """
    _f = _func(TAB2, "render_single_fund_tab")
    _es = _calls(_fd_if(_f), "empty_state")[0]
    _txt = " ".join(k.value for k in ast.walk(_es)
                    if isinstance(k, ast.Constant) and isinstance(k.value, str))
    for _need in ("1️⃣", "2️⃣", "3️⃣", "找代號", "MoneyDJ", "🚀 分析"):
        assert _need in _txt, f"空狀態的三步驟少了 {_need!r}：{_txt[:120]!r}"


# ══════════════════════════════════════════════════════════════════════
# T13 · ③ 導覽收成一份（線框 決定 2 / D5）
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("path", [TAB2, TAB_BATCH])
def test_modes_no_longer_draw_their_own_nav(path: pathlib.Path):
    """兩個模式都不准再自己畫導覽 —— 否則切模式時頂部會跳動（D5）。"""
    _t = _tree(path)
    _hits = [ast.unparse(c) for name in ("render_flow_nav", "render_story_nav")
             for c in _calls(_t, name)]
    assert not _hits, (
        f"{path.name} 又自己畫導覽了：{_hits} —— 導覽由 "
        "`ui/tab_fund_research.py::_render_shared_top()` 畫一次（線框 D5）。")


def test_shared_top_draws_both_navs_once_and_before_the_finder():
    """共用頂部各畫一次，且**排在找代號工具之前**（線框 SHEET 00 的順序）。"""
    _f = _func(TAB_RESEARCH, "_render_shared_top")
    _flow = _calls(_f, "render_flow_nav")
    _story = _calls(_f, "render_story_nav")
    assert len(_flow) == 1 and len(_story) == 1, (
        f"共用頂部的導覽呼叫數不對：flow={len(_flow)} / story={len(_story)}，各應為 1。")
    _order = [ast.unparse(s) for s in _f.body]
    _i_nav = max(i for i, s in enumerate(_order) if "render_flow_nav" in s
                 or "render_story_nav" in s)
    _i_finder = next(i for i, s in enumerate(_order) if "render_code_finder" in s)
    assert _i_nav < _i_finder, "導覽必須排在「🔍 找代號」之前（線框 SHEET 00）。"
    assert any(isinstance(a, ast.Constant) and a.value == "research"
               for a in _story[0].args), (
        "`render_story_nav` 應照線框用 `\"research\"`（實測與 `fund`/`batch` 輸出逐字相同）。")

    # ⚠️ **自己找到的沉默突變（初稿沒守到，就地補上）**：把這裡改成
    # `render_flow_nav("research")` 之後，`_MODE_NAV_KEY` 那張表還在、
    # 下面那條 runtime 斷言照樣全綠 —— 但畫面上會印出
    # 「本頁為支援 / 診斷用，不在決策流程的任何一層」。
    # 所以**實際傳進去的那個引數**必須自己驗一次。
    from ui.helpers.story_nav import layer_of as _layer_of
    _arg = _flow[0].args[0] if _flow[0].args else None
    assert _arg is not None, "`render_flow_nav()` 沒有傳 key。"
    if isinstance(_arg, ast.Constant):
        assert _layer_of(_arg.value) == "L2", (
            f"`render_flow_nav({_arg.value!r})` 解析到 "
            f"{_layer_of(_arg.value)!r} 而不是 L2 —— 畫出來會是"
            "「不在決策流程的任何一層」，與線框 SHEET 00 相反。")
    else:
        assert _calls(_arg, "_current_mode_nav_key"), (
            f"`render_flow_nav()` 收到的是 {ast.unparse(_arg)!r} —— "
            "既不是可驗證的常數，也不是 `_current_mode_nav_key()`。"
            "本條無法確定它會解析到 L2，請改回其中一種。")


def test_shared_top_flow_nav_key_lands_on_a_real_layer():
    """**runtime 行為斷言**：共用頂部餵給 `render_flow_nav` 的 key 必須真的解析到 L2。

    這條是本檔最重要的一條，因為線框寫的 `"research"` **不能照抄** ——
    `story_nav.layer_of("research")` 回空字串（`research` 不在 `_LAYERS`），
    畫出來會變成「本頁為支援 / 診斷用，不在決策流程的任何一層」，
    與同一份線框 SHEET 00 畫的「② 基金核心分析 高亮」互相矛盾。
    **字串比對抓不到這種錯（字都對，輸出是錯的）**，所以這裡真的去呼叫它。
    """
    from ui.helpers.story_nav import flow_nav_markdown, layer_of, story_nav_markdown
    from ui.tab_fund_research import _MODE_NAV_KEY, MODE_BATCH, MODE_SINGLE

    assert set(_MODE_NAV_KEY) == {MODE_SINGLE, MODE_BATCH}, (
        "模式 → 導覽 key 的對照表漏了某個模式，那個模式的導覽會退回預設值。")
    for _mode, _key in _MODE_NAV_KEY.items():
        assert layer_of(_key) == "L2", (
            f"模式 {_mode!r} 用的導覽 key {_key!r} 解析到 {layer_of(_key)!r}，不是 L2。")
        _md = flow_nav_markdown(_key)
        assert "不在決策流程的任何一層" not in _md, (
            f"{_key!r} 畫出來是「支援 / 診斷用」—— 那是錯的，③ 屬 L2。")
        assert "**:blue[② 基金核心分析]**" in _md, (
            f"{_key!r} 沒有把「② 基金核心分析」高亮（線框 SHEET 00 畫的就是它）。")

    # D5 的判準：兩個模式的決策動線輸出**逐字相同** —— 這才是「同一份資料畫兩次」。
    assert story_nav_markdown("fund") == story_nav_markdown("research")
    assert story_nav_markdown("batch") == story_nav_markdown("research")


def test_mode_nav_key_follows_the_selected_mode():
    """**runtime 行為斷言**：`_current_mode_nav_key()` 要跟著使用者選的模式走。

    寫死成 `"fund"` 也能讓上面那條綠燈（`fund` 也解析到 L2），
    但批次模式會看到「本層另有：📦 批次掃描」—— 他正在看的就是它。
    """
    import streamlit as st
    from ui.tab_fund_research import (
        MODE_BATCH, MODE_SINGLE, _current_mode_nav_key,
    )

    _saved = dict(st.session_state) if hasattr(st, "session_state") else {}
    try:
        st.session_state["fr_mode"] = MODE_BATCH
        assert _current_mode_nav_key() == "batch", (
            "選了批次模式，導覽 key 卻不是 `batch` —— 「本層另有」會指到他正在看的東西。")
        st.session_state["fr_mode"] = MODE_SINGLE
        assert _current_mode_nav_key() == "fund"
        st.session_state.pop("fr_mode", None)
        assert _current_mode_nav_key() == "fund", "首次進頁（尚無模式）應視為單檔深掘。"
    finally:
        st.session_state.pop("fr_mode", None)
        for _k, _v in _saved.items():
            st.session_state[_k] = _v


# ══════════════════════════════════════════════════════════════════════
# T15 · D3 兩模式「基期」用字對齊
# ══════════════════════════════════════════════════════════════════════
def _unified_base_labels() -> dict:
    """從 `unified.py` 的 `_BASE_LBL` **字面值**讀出大表的用字。

    它是函式內的區域變數（import 不到），所以只能用 AST 讀 —— 這正是
    「這組字串目前沒有 SSOT」的證據本身，不是本測試偷懶。
    """
    for node in ast.walk(_tree(UNIFIED)):
        if (isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "_BASE_LBL"
                        for t in node.targets)):
            return ast.literal_eval(node.value)
    raise AssertionError(
        "`unified.py` 找不到 `_BASE_LBL` —— 若它已被收進 SSOT（那是好事），"
        "請把本測試改成直接 import 那個 SSOT，並把 "
        "`tab2_single_fund.BASE_LABELS_FROM_MERGED_TABLE` 一起改吃它。")


def test_base_label_wording_matches_the_merged_table():
    """單檔 σ 卡片的「基期」用字必須與批次大表**逐字相同**（線框 D3）。

    ⚠️ 這是一把**漂移鎖**，不是 SSOT。這組字串在 repo 內目前有三份且無共同來源
    （`unified.py::_BASE_LBL`、`rotation.py::_lbl`、本批新增的
    `tab2_single_fund.BASE_LABELS_FROM_MERGED_TABLE`）—— 收進 `shared/` 才是正解，
    但那不在本批的檔案邊界內。**在收進去之前，任一邊改字就當場轉紅。**
    """
    from ui.tab2_single_fund import BASE_LABELS_FROM_MERGED_TABLE as _mine

    assert _mine == _unified_base_labels(), (
        "單檔卡片與批次大表的「基期」用字漂移了 —— 使用者切模式會看到兩套詞。\n"
        f"  單檔：{_mine}\n  大表：{_unified_base_labels()}")


def test_base_label_covers_every_outcome_of_classify_base():
    """`classify_base()` 的每一種回傳都要有對應標籤 —— 否則卡片會當場 KeyError。

    **runtime 斷言**：真的餵各種 σ rank 進去看它回什麼，不是讀原始碼猜。
    """
    from services.rotation import classify_base
    from ui.tab2_single_fund import BASE_LABELS_FROM_MERGED_TABLE as _mine

    _seen = {classify_base(v) for v in
             (None, float("nan"), -9.0, -3.0, -1.5, -0.9, -0.2, 0.0, 0.5, 9.0, "x")}
    assert _seen, "餵了各種 σ rank 卻一種分類都沒回 —— `classify_base` 行為變了。"
    assert _seen <= set(_mine), (
        f"`classify_base()` 會回 {sorted(_seen)}，而標籤表只有 {sorted(_mine)} —— "
        "缺的那一種在畫面上會炸成 KeyError。")


def test_sigma_card_actually_renders_the_base_label():
    """卡片要真的把「基期」畫出來，而且那個值來自 `classify_base()`。

    只有常數表對齊是不夠的 —— 表對齊了、卡片不畫，使用者一樣看不到（沉默突變）。
    """
    _f = _func(TAB2, "render_single_fund_tab")
    _subs = [n for n in ast.walk(_f) if isinstance(n, ast.Subscript)
             and isinstance(n.value, ast.Name)
             and n.value.id == "BASE_LABELS_FROM_MERGED_TABLE"]
    assert len(_subs) == 1, (
        f"`BASE_LABELS_FROM_MERGED_TABLE[...]` 取值 {len(_subs)} 次，預期 1 次。")
    assert _calls(_subs[0].slice, "classify_base") or _calls(_subs[0], "_cb_t2"), (
        "「基期」標籤不是由 `classify_base()` 決定的 —— "
        "那就不是「同一份資料的兩種呈現」，而是第二個口徑（D3 要防的正是這件事）。")
    _assigned = [n for n in ast.walk(_f) if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == "_base_lbl"
                         for t in n.targets)]
    assert _assigned, "`_base_lbl` 沒有被指派。"
    _md = [c for c in _calls(_f, "markdown")
           if any("_base_lbl" in ast.unparse(v) for v in ast.walk(c)
                  if isinstance(v, ast.FormattedValue))]
    assert _md, "算了 `_base_lbl` 卻沒有畫進卡片 —— 使用者看不到，等於沒做。"


# ══════════════════════════════════════════════════════════════════════
# T15 · D4 批次「ℹ️ 欄位說明」要講清楚只列 4 段
# ══════════════════════════════════════════════════════════════════════
def _batch_sigma_keys() -> set:
    """批次大表實際讀了哪幾段買賣點（讀 `signals.py`，不是讀說明文字）。"""
    out = set()
    # ⚠️ **只掃 `mk_signal_by_code()`** —— 同一個檔案裡的
    # `_render_bollinger_expanders()` 會讀滿 6 段（它畫的是布林通道展開區，
    # 不是大表的欄）。整檔掃會把它一起算進來，於是本條永遠紅（初稿實測）。
    # 這個窄化本身也是 D4 的證據：**同一份 metrics，不同投影。**
    for node in ast.walk(_func(SIGNALS, "mk_signal_by_code")):
        if not (isinstance(node, ast.Call)
                and getattr(node.func, "attr", None) == "get"
                and node.args and isinstance(node.args[0], ast.Constant)):
            continue
        _v = node.args[0].value
        if isinstance(_v, str) and _v[:-1] in ("buy", "sell") and _v[-1].isdigit():
            out.add(_v)
    return out


def test_batch_really_only_projects_four_bands():
    """說明文字宣稱「只列 4 段」—— 先驗那句話**現在還是真的**。

    這是本檔唯一一條「守文件不說謊」的斷言：哪天有人把 `buy2` 加進批次大表，
    說明文字就當場變成假的 —— 本條轉紅，逼他一起改文案。
    ⚠️ 它掃的是 `signals.py::mk_signal_by_code` 那條路徑，**不涵蓋**其他可能
    產生買賣欄的地方（例如 `unified.py` 若日後自己再拼一組）。
    """
    assert _batch_sigma_keys() == {"buy1", "buy3", "sell1", "sell3"}, (
        f"批次大表實際讀的買賣段是 {sorted(_batch_sigma_keys())}，不再是四段 —— "
        "`ui/tab_batch_analysis.py` 的「ℹ️ 欄位說明」那句 D4 說明已經是假的，請一起改。")


def test_batch_field_help_explains_the_four_band_projection():
    """D4：說明必須點出「只列四段、−2σ／+2σ 去單檔看」，且分區名走 SSOT。

    ⚠️ 字串比對的部分（四段的字）守不到「這句話有沒有真的被渲染出來」——
    但它與 `test_batch_really_only_projects_four_bands()` 一起看才有意義：
    前者驗**事實**、後者驗**有沒有講**。單獨任一條都不夠。
    """
    _f = _func(TAB_BATCH, "_render_existing_results")
    _md = [c for c in _calls(_f, "markdown")
           if any(isinstance(k, ast.Constant) and isinstance(k.value, str)
                  and "本表只列" in k.value for k in ast.walk(c))]
    assert _md, "批次「ℹ️ 欄位說明」找不到 D4 那句「本表只列 …」。"
    _txt = " ".join(k.value for k in ast.walk(_md[0])
                    if isinstance(k, ast.Constant) and isinstance(k.value, str))
    for _need in ("−3σ", "−1σ", "+1σ", "+3σ", "−2σ", "+2σ", "不是兩套算法"):
        assert _need in _txt, f"D4 說明少了 {_need!r}。"
    assert _calls(_md[0], "_section_label_ba") or _calls(_md[0], "section_label"), (
        "指到「單檔深掘」的那個名字是手打的 —— 分區名只准有一個來源"
        "（`story_nav.section_label`），本 repo 改名漏改已發作三次。")


def test_macro_checkbox_defaults_match_the_wireframe():
    """線框寫「（預設全選）」：四個來源勾選框預設 `True`，強制重抓預設 `False`。

    ⚠️ **這是自己找到的沉默突變**：把四個 `value=True` 改成 `False`，
    上面每一條結構斷言都還是綠的（form 在、gate 在、四路都接了線），
    但使用者按下送出鈕**什麼都不會抓**，畫面停在「尚未載入」。
    反過來把「強制重抓」預設成 `True`，則是每按一次就清一次快取。
    """
    _f = _func(TAB1, "render_macro_tab")
    _defaults = {}
    for _c in _calls(_f, "checkbox"):
        _key = next((ast.literal_eval(k.value) for k in _c.keywords
                     if k.arg == "key"), None)
        _val = next((k.value for k in _c.keywords if k.arg == "value"), None)
        assert _key is not None, f"勾選框沒給 key：{ast.unparse(_c)[:60]}"
        assert isinstance(_val, ast.Constant), (
            f"勾選框 {_key!r} 的預設值不是字面常數（{ast.unparse(_c)[:60]}）——"
            "本條只能驗字面常數，請不要把預設值藏進變數。")
        _defaults[_key] = _val.value
    _sources = {k: v for k, v in _defaults.items() if k.startswith("chk_macro_want_")}
    assert len(_sources) == 4, (
        f"四個來源勾選框只找到 {sorted(_sources)} —— 線框 Form ①-A 畫的是"
        "總經指標／新聞／風險雷達／拐點偵測四個。")
    assert all(_sources.values()), (
        f"來源勾選框預設不是全選：{_sources} —— 線框寫「（預設全選）」，"
        "預設關掉等於按了送出鈕什麼都不抓。")
    assert _defaults.get("chk_macro_force") is False, (
        "「強制重抓最新（清快取）」預設必須是 False —— 預設開啟會讓每一次送出"
        "都清一次快取。")
