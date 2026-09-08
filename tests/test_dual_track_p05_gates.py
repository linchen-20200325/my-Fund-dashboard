"""雙軌並行第二輪：新 ⑦ 與舊 ⑤ 同一次 run 還會不會撞、還會不會安靜地畫兩份。

⚠️ **本檔的 AppTest 斷言全部由 CI 產生，本機一次都沒有跑過** —— 這個容器沒有
   streamlit、也沒有 pytest（環境規則禁止 `pip install`）。**不假裝跑過。**
   本機唯一跑得動、而且真的跑過的，是下方 **A 段的純 AST 守衛**
   （`python3` 直接執行，不需要任何第三方套件）。

   **CI 實跑紀錄**：run `34167952135`（commit `ffb37a5`）——
   Fast checks / Schema gate / Slow tests **三條 lane `conclusion` 逐條皆 `success`**
   （⛔ 本 repo 紀律：不看 `mergeable_state`；`cancelled` / `skipped` 皆 ≠ `success`）。

⭐ **「全綠」怎麼證明不是「全部被 skip 掉」**（這一段刻意寫在最前面）：
   本檔有**兩條正向斷言**，harness 沒跑起來時它們會**紅**而不是綠 ——
   :func:`test_the_gate_labels_this_file_hardcodes_are_really_on_screen`
   （畫面上必須真的有那四顆 checkbox）與
   :func:`test_ticking_the_manual_gate_brings_the_collision_straight_back`
   （勾下去必須**真的**噴出那個紅框）。
   **它們綠 ⇒ AppTest 真的跑了、app 真的渲染了、那個衝突真的還在**。
   ⛔ 一整檔都是「不准有 X」的斷言時，`importorskip` 跳過與「全部通過」長得一模一樣 ——
   那是本 repo 記過的失效模式，故本檔刻意各留一條正向的。

本檔與 `tests/test_dual_track_widget_key_collision.py`（#819）的分工
------------------------------------------------------------------
#819 **只把事實釘成證據、不修任何東西**；本檔是**修完之後的守衛**。
⛔ **本檔不改 #819 一個字** —— 那是它的檔案邊界。

#819 量到四種現象（訊息逐字出自 CI）：

====  ==================  ================================================
編號   幾次點擊             現象
====  ==================  ================================================
①     **0（打開就有）**    `StreamlitDuplicateElementId` — 指標地圖（**紅框**）
②     1（勾維護區）        `StreamlitDuplicateElementKey: key='divcal_gen'`（**紅框**）
                          ＋ `pool_add_form`（**黃框**，被 `_friendly` 降級）
③     1（勾手動補資料）     `StreamlitAPIException` — `navhist_import_form`（**紅框**）
④     **0**              「🔍 抓取診斷細節」被畫兩份 —— **不噴任何錯**
====  ==================  ================================================

⭐ **本檔的檢查刻意能區分那三種嚴重度**，因為只驗一種必然漏掉另外兩種：

- **紅框** → :func:`_errors`（`at.error`）
- **黃框** → :func:`_warnings`（`at.warning`）—— ② 的 `pool_add_form` 只長這樣
- **沒有任何提示、但畫了兩份** → :func:`_count_in_stream`（數畫面上出現幾次）——
  ④ 只長這樣，**前兩種檢查對它結構上不可見**

修法（全部落在新頁側，舊 `ui/tab*.py` **一個位元組都沒動**）
-----------------------------------------------------------
客戶 2026-09-07 明令「絕對禁止直接覆寫、修改或破壞現有線上正常運作的舊版 Tab 代碼」，
所以 ①④ 的修法**不是**去幫舊模組的元素補 `key=`，而是在
`ui/views/page_05_settings.py` 給那兩塊也加上 Checkbox Gate
（②③ 本來就有 gate，本輪改的是**它們的灰態本文** —— 舊文字把「勾下去」講成解法，
實際上勾下去正是撞的那一刻，見 :func:`test_the_grey_notes_say_what_ticking_actually_does`）。
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_PY = REPO_ROOT / "app.py"
NEW_P05 = REPO_ROOT / "ui/views/page_05_settings.py"
OLD_TAB5 = REPO_ROOT / "ui/tab_settings_diag.py"

#: 新 ⑦ 四顆 gate 的標籤。**刻意手抄**，不從被測模組 import ——
#: 從被測模組取值會讓標籤改掉時測試跟著改、跟著綠（自證）。
#: 由 :func:`test_the_gate_labels_this_file_hardcodes_are_really_on_screen` 守不漂移。
GATE_LABELS: tuple[str, ...] = (
    "🗄️ 載入資料維護與通報",
    "🗄️ 載入手動補資料",
    "📖 載入使用手冊",
    "🔍 載入抓取診斷細節",
)
MANUAL_GATE_LABEL = "📖 載入使用手冊"

#: 「🔍 抓取診斷細節」在**沒有抓取紀錄**時畫的那句灰字（`fetch_diag_section.py`）。
#: 它是 ④ 唯一的可觀測痕跡：畫兩份時畫面上會有**兩句一模一樣的**這個。
FETCH_DIAG_FINGERPRINT = "尚無抓取紀錄可診斷"


# ══════════════════════════════════════════════════════════════════
# A 段｜純 AST 守衛（不需要 streamlit，本機真的跑過）
# ══════════════════════════════════════════════════════════════════
_PKGS = frozenset({"ui", "services", "repositories", "shared", "infra"})
#: 會讓後面的 body「要使用者動一下才會跑」的呼叫。
_GATE_CALLS = frozenset({"checkbox", "button", "toggle", "form_submit_button"})
#: `merge_context` 的旗標查詢 —— `app.py` 只持有 `FETCH_DIAG`，
#: 其餘旗標（例如 `POLICY_ADMIN`）底下的分支在 production 根本到不了。
_FLAG_CALLS = frozenset({"owned_by_settings_page"})
#: 會拿到「自動產生 element ID」的元素：兩份參數相同 ⇒ ID 相同 ⇒ Streamlit 拒絕。
#: ⚠️ **這是白名單，不是窮舉** —— Streamlit 新增的元素不會自動進來（見檔尾射程聲明）。
_AUTOID_ELEMS = frozenset({
    "plotly_chart", "dataframe", "data_editor", "table", "altair_chart",
    "vega_lite_chart", "pydeck_chart", "graphviz_chart", "line_chart",
    "area_chart", "bar_chart", "scatter_chart", "map", "metric", "image",
    "audio", "video", "form", "download_button", "button", "checkbox",
    "toggle", "radio", "selectbox", "multiselect", "slider", "select_slider",
    "text_input", "number_input", "text_area", "date_input", "time_input",
    "file_uploader", "color_picker", "camera_input", "link_button",
    "page_link", "chat_input", "feedback", "pills", "segmented_control",
})

_TREE_CACHE: dict[str, ast.Module | None] = {}


def _mod_path(mod: str) -> Path | None:
    _p = REPO_ROOT / (mod.replace(".", "/") + ".py")
    if _p.exists():
        return _p
    _p2 = REPO_ROOT / mod.replace(".", "/") / "__init__.py"
    return _p2 if _p2.exists() else None


def _tree(mod: str) -> ast.Module | None:
    if mod not in _TREE_CACHE:
        _p = _mod_path(mod)
        _TREE_CACHE[mod] = (ast.parse(_p.read_text(encoding="utf-8"))
                            if _p is not None else None)
    return _TREE_CACHE[mod]


def _names(mod: str) -> dict[str, tuple[str, str]]:
    """本地名字 → (模組, 原名)。**含函式內的 lazy import**（本 repo 主流寫法）。"""
    _t = _tree(mod)
    _out: dict[str, tuple[str, str]] = {}
    if _t is None:
        return _out
    for _n in ast.walk(_t):
        if isinstance(_n, ast.ImportFrom) and _n.module and _n.level == 0:
            for _a in _n.names:
                _local = _a.asname or _a.name
                # `from ui import tab6_manual` —— 名字本身就是一個模組
                _out[_local] = ((f"{_n.module}.{_a.name}", "*module*")
                                if _mod_path(f"{_n.module}.{_a.name}")
                                else (_n.module, _a.name))
    return _out


def _funcs(mod: str) -> dict[str, ast.AST]:
    _t = _tree(mod)
    return {} if _t is None else {
        _n.name: _n for _n in ast.walk(_t)
        if isinstance(_n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _has_gate_call(node: ast.AST) -> bool:
    for _c in ast.walk(node):
        if isinstance(_c, ast.Call) and isinstance(_c.func, ast.Attribute) \
                and _c.func.attr in _GATE_CALLS:
            return True
        if isinstance(_c, ast.Call) and isinstance(_c.func, ast.Name) \
                and _c.func.id in _FLAG_CALLS:
            return True
    return False


def _gate_vars(fn: ast.AST) -> set[str]:
    """`x = st.checkbox(...)` 這種先存進變數、下一行才 `if not x:` 的寫法。

    ⚠️ **少了這一段，本頁與舊 ⑤ 的資料診斷 gate 都會被判成「沒有 gate」** ——
       兩邊都是先賦值再判斷。本組第一版就是這樣多抓了 `ui/tab5_data_guard.py` 一整批。
    """
    _out: set[str] = set()
    for _n in ast.walk(fn):
        _val = getattr(_n, "value", None)
        if isinstance(_n, ast.Assign) and _val is not None and _has_gate_call(_val):
            _out |= {_t.id for _t in _n.targets if isinstance(_t, ast.Name)}
        elif isinstance(_n, (ast.AnnAssign, ast.NamedExpr)) and _val is not None \
                and _has_gate_call(_val) and isinstance(_n.target, ast.Name):
            _out.add(_n.target.id)
    return _out


def _ungated(fn: ast.AST):
    """`fn` 裡「使用者一次都不必點就會跑到」的節點。

    兩種 gate 都認：
      * `if <gate>:` → 整段 body 略過；
      * `if not <gate>: … return` → **它之後的所有東西**都要點一下才跑得到。
    """
    _gv = _gate_vars(fn)

    def _is_gate_if(node: ast.If) -> bool:
        if not (_has_gate_call(node.test) or any(
                isinstance(_x, ast.Name) and _x.id in _gv
                for _x in ast.walk(node.test))):
            return False
        # ⛔ **fail-closed：條件被布林字面值短路掉的，不算 gate。**
        #    `if False and st.checkbox(...)` 形狀完美、擋不到任何東西 ——
        #    `tests/test_wf05_settings_golive.py` 的同名守衛就是被這一招活過去的，
        #    本掃描器第一版也被它騙過（本組實測，見 PR 描述）。
        #    checkbox 自己的 `value=False` 是合法的，故**整棵 checkbox 子樹排除**。
        _cb_ids = {id(_x) for _c in ast.walk(node.test)
                   if isinstance(_c, ast.Call)
                   and getattr(_c.func, "attr", None) in _GATE_CALLS
                   for _x in ast.walk(_c)}
        return not [_x for _x in ast.walk(node.test)
                    if isinstance(_x, ast.Constant) and isinstance(_x.value, bool)
                    and id(_x) not in _cb_ids]

    def _walk(body):
        for _st in body:
            if isinstance(_st, ast.If) and _is_gate_if(_st):
                if any(isinstance(_x, ast.Return)
                       for _b in _st.body for _x in ast.walk(_b)):
                    return                      # 提前 return 型 gate：後面全擋住
                continue                        # 純分支型 gate：略過 body
            yield _st
            for _sub in ("body", "orelse", "finalbody"):
                if isinstance(getattr(_st, _sub, None), list):
                    yield from _walk(getattr(_st, _sub))
            for _h in getattr(_st, "handlers", []):
                yield from _walk(_h.body)
            if not isinstance(_st, (ast.With, ast.AsyncWith, ast.Try,
                                    ast.For, ast.While, ast.If)):
                yield from ast.walk(_st)

    yield from _walk(fn.body)


def _reexport_home(mod: str, fname: str) -> tuple[str, str] | None:
    """`mod` 只是**把 `fname` 從別處轉出來**時，回傳它真正的家；否則 `None`。

    ⭐ **這一支是 2026-09-08 補的，補的是一個會讓守衛說謊的 fail-open 盲點。**

    在它之前，:func:`_reach` 追到 **re-export shim** 就斷 —— `_funcs(mod).get(fname)`
    對一個「只有 docstring ＋ `from X import a, b, c`」的檔案回 `None`，
    於是整條呼叫鏈在那裡無聲地結束。**本 repo 真的有這種檔**：
    `ui/helpers/fund_grp_health_extras.py`（**38 行、`FunctionDef` 0 個**，
    v19.198 P1-6 拆子套件後留下的向後相容 shim）。

    追法**刻意是通則、不是具名列舉**：任何模組只要
    「`fname` 不是它自己定義的」＋「它有 `from <pkg> import <fname>`」，
    就往那個 `<pkg>` 續追。所以日後新長出來的 shim **會自動被涵蓋**，
    不必回頭改本檔（具名列舉會有這個問題，故不採用）。

    **終止性**：續追走的是 :func:`_reach` 既有的 ``seen`` 集合，
    `(mod, fname)` 進去之後才續追 ⇒ ``A→B→A`` 這種互轉在第二次就被 ``seen`` 擋下。
    **不會無限遞迴。**

    ⚠️ **這是刻意的過度近似（over-approximation），方向是 fail-closed**：
    :func:`_names` 連**函式內的 lazy import** 都收，所以「模組 M 的某個函式裡
    `from X import helper`」也會被當成 M 轉出了 `helper`。那不精確 ——
    但它只會讓候選**變多**，不會讓候選**變少**。
    掃描器寧可多抓是本檔一貫的立場（見 :func:`test_the_known_static_candidates_...`
    內「候選 ≠ 一定會撞」那一段），**不得**為了乾淨把它改成窄的。
    """
    if _tree(mod) is None or _funcs(mod).get(fname) is not None:
        return None
    _tgt = _names(mod).get(fname)
    if _tgt is None or _tgt[1] == "*module*":
        return None
    return _tgt if _mod_path(_tgt[0]) else None


def _reach(mod: str, fname: str, seen: set[tuple[str, str]] | None = None):
    """從 (mod, fname) 出發、**不必點任何東西**就跑得到的函式集合。

    ⚠️ 連 **函式參考** 也追（`safe_section(label, _render_x)`）—— 本頁六個區塊
       全部是這樣掛上去的，只追 `Call` 會一個都追不到。

    ⚠️ 也追 **re-export shim**（見 :func:`_reexport_home`）—— 少了那一段，
       舊 ② 經 `ui/helpers/fund_grp_health_extras.py` 轉出去的整批委派
       **對本掃描器結構上不可見**，守衛會安靜地放行。
    """
    seen = set() if seen is None else seen
    if (mod, fname) in seen:
        return seen
    seen.add((mod, fname))
    _fn = _funcs(mod).get(fname)
    if _fn is None:
        # 追不到函式本體 ⇒ 可能是純轉出的 shim，續追它真正的家。
        _home = _reexport_home(mod, fname)
        if _home is not None and _home[0].split(".")[0] in _PKGS:
            _reach(_home[0], _home[1], seen)
        return seen
    _nm, _local = _names(mod), _funcs(mod)

    def _go(target: tuple[str, str] | None) -> None:
        if target and target[0].split(".")[0] in _PKGS and _mod_path(target[0]):
            _reach(target[0], target[1], seen)

    for _n in _ungated(_fn):
        if isinstance(_n, ast.Name) and isinstance(getattr(_n, "ctx", None), ast.Load):
            _go(_nm.get(_n.id) or ((mod, _n.id) if _n.id in _local else None))
        elif isinstance(_n, ast.Call):
            if isinstance(_n.func, ast.Name):
                _go(_nm.get(_n.func.id)
                    or ((mod, _n.func.id) if _n.func.id in _local else None))
            elif isinstance(_n.func, ast.Attribute) \
                    and isinstance(_n.func.value, ast.Name) \
                    and _nm.get(_n.func.value.id, ("", ""))[1] == "*module*":
                _go((_nm[_n.func.value.id][0], _n.func.attr))
    return seen


def _st_aliases(mod: str) -> set[str]:
    """`mod` 裡綁到 streamlit 的名字（`import streamlit as _st_mod` 也算）。

    ⚠️ **刻意不寫死 `st.`** —— `ui/helpers/macro/ndc.py` 用的是 `@_st_mod.cache_data`，
       寫死模組名的掃描器對它結構上不可見（`CLAUDE.md §8.2.A.1` 記過同一個病）。
    """
    _t, _out = _tree(mod), {"st"}
    if _t is not None:
        for _n in ast.walk(_t):
            if isinstance(_n, ast.Import):
                _out |= {(_a.asname or _a.name) for _a in _n.names
                         if _a.name == "streamlit"}
    return _out


def _keyless_elems(mod: str, fname: str) -> set[tuple[str, str, int]]:
    """(模組, 元素, 行號) —— `fn` 內**不必點就會畫、而且沒有帶 `key=`** 的元素。"""
    _fn = _funcs(mod).get(fname)
    if _fn is None:
        return set()
    _al = _st_aliases(mod)
    return {(mod, _n.func.attr, _n.lineno) for _n in _ungated(_fn)
            if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
            and _n.func.attr in _AUTOID_ELEMS
            and isinstance(_n.func.value, ast.Name) and _n.func.value.id in _al
            and not any(_k.arg == "key" for _k in _n.keywords if _k.arg)}


def _collision_candidates(old: tuple[str, str],
                          new: tuple[str, str]) -> set[tuple[str, str, int]]:
    _shared = _reach(*old) & _reach(*new)
    _out: set[tuple[str, str, int]] = set()
    for _m, _f in _shared:
        _out |= _keyless_elems(_m, _f)
    return _out


_OLD5 = ("ui.tab_settings_diag", "render_settings_diag_tab")
_NEW7 = ("ui.views.page_05_settings", "render_settings_and_diagnostics")
_OLD2 = ("ui.tab_fund_grp_health", "render_fund_grp_health_tab")
_NEW6 = ("ui.views.page_02_health", "render_holdings_health")
#: ⑧ `[新] 標的探索`（#820，2026-09-07 合併進 `main`）—— **第三對雙軌**。
#: ⚠️ 本檔在 `ac7050e` 上開工時它還不存在；合併 `main` 之後補掃，**不是原本就有**。
_OLD3 = ("ui.tab_fund_research", "render_fund_research_tab")
_NEW8 = ("ui.views.page_03_research", "render_fund_research")


def test_no_keyless_element_is_drawn_by_both_old_five_and_new_seven():
    """⭐⭐ **本檔最重要的一條：不只治那四處，而是治那個「族」。**

    #814 雙軌之後的結構性代價是：**任何**沒有 `key=` 的元素，只要新舊兩頁在同一次
    run 都畫得到它，自動產生的 element ID 就會撞。先前兩輪的盤點只比對**具名
    `key=`**（literal key 交集 0），**結構上看不到這一類** —— ① 正是這樣漏掉的。

    本條改成掃「**不必點就跑得到、而且沒有 key** 的元素」，
    所以它抓得到的是**還沒發生的那些**，不只是已經回報的四處。

    ⚠️ **本條的射程有邊界，逐條列在檔尾**（`_AUTOID_ELEMS` 是白名單、
       靜態分析看不到 runtime 的資料分支……）—— **不得**把本條轉綠讀成
       「⑦ 已經沒有任何重複」。
    """
    _hits = _collision_candidates(_OLD5, _NEW7)
    assert not _hits, (
        "下列元素**沒有 `key=`**，而且舊 ⑤ 與新 ⑦ 在同一次 run 都畫得到 —— "
        "它們的自動 element ID 會撞：\n"
        + "\n".join(f"  {_m}:{_ln}  st.{_e}" for _m, _e, _ln in sorted(_hits))
        + "\n\n修法：在**新頁側**（`ui/views/page_05_settings.py`）給那一塊加 "
          "Checkbox Gate。⛔ 不得去改舊 `ui/tab*.py`（客戶 2026-09-07 紅線）。")


def test_the_scanner_really_catches_a_reintroduced_ungated_delegate():
    """突變驗證：把使用手冊的 gate 拆掉 → 上面那條必須看得到 `plotly_chart`。

    硬性要求逐條落地
    ----------------
    - **不寫任何檔案** —— 突變只發生在**記憶體裡的 AST**，production 檔連開都不開寫。
      （#819 那條要跑真的 app 才有意義，所以它必須落地成 tmp 檔；本條不必。）
    - 突變體先 `ast.parse` 過（語法錯 ＝ 當機紅，不算守衛紅）。
    - 用 `str.replace` 換一段**含縮排的唯一字串**；⛔ 不用 `ast.col_offset` 切 ——
      那是 **UTF-8 位元組**位移，本檔與被測檔滿是中文，用字元索引切會讓突變
      **根本沒套上卻回報綠**。
    - 斷言突變體**位元組真的變了**、錨點真的消失。
    - 事後 `sha256` 逐位元組確認 production 檔沒有被碰過。
    """
    _before = hashlib.sha256(NEW_P05.read_bytes()).hexdigest()
    _src = NEW_P05.read_text(encoding="utf-8")

    _anchor = "        if not st.checkbox(\n                _manual_gate_label(),"
    assert _src.count(_anchor) == 1, (
        f"突變錨點出現 {_src.count(_anchor)} 次，不是 1 —— 錨點已漂移，"
        "請更新本測試而不是放寬它。")
    # 讓 gate 恆為 True（＝ 永遠不 return ＝ 委派照跑），語法合法。
    _mutated = _src.replace(_anchor, "        if not True and st.checkbox(\n"
                                     "                _manual_gate_label(),")
    assert _mutated.encode() != _src.encode(), "替換沒套上，這一輪不算驗過"
    assert _anchor not in _mutated, "錨點仍在突變體裡 —— 替換不完整"
    ast.parse(_mutated)

    _TREE_CACHE["ui.views.page_05_settings"] = ast.parse(_mutated)
    try:
        _hits = _collision_candidates(_OLD5, _NEW7)
    finally:
        _TREE_CACHE.pop("ui.views.page_05_settings", None)
    assert any(_e == "plotly_chart" for _, _e, _ in _hits), (
        "把使用手冊的 gate 短路掉之後，掃描器**看不到**那張沒有 key 的 "
        "`plotly_chart` —— 代表上面那條是假的守衛。"
        f"實際命中：{sorted(_hits)}")
    assert hashlib.sha256(NEW_P05.read_bytes()).hexdigest() == _before, \
        "本測試污染了 production 檔"


def test_the_third_dual_track_pair_has_no_keyless_collision_either():
    """⭐ **第三對（舊 ③ ↔ 新 ⑧，#820 剛合併）也掃一次 —— 不是「只治我這一頁」。**

    雙軌並行是**結構性代價**：每多掛一格 `[新]` 預覽，就多一組「兩頁委派同一批舊模組」。
    ①（指標地圖那張圖）之所以漏掉兩輪，正是因為先前的盤點**只比對具名 `key=`**，
    對「沒有 key、自動 ID 撞在一起」這一類**結構上看不見**。

    **本組實測（量測日 2026-09-07，於本分支合併 `origin/main` 之後）：命中 0。**
    ⚠️ **0 是本輪的量測值，不是保證** —— 這一條的作用是：⑧ 哪天長出一個沒有 key
    的共用元素，**這裡會紅**，而不是等使用者打開網站才看到紅字。

    ⛔ **本輪不動 `ui/views/page_03_research.py` 一個位元組**（不在本批檔案邊界內）。
       本條只讀不寫；真的紅了請**回報總管**，由 ⑧ 那一組決定修在哪一側。
    """
    _hits = _collision_candidates(_OLD3, _NEW8)
    assert not _hits, (
        "舊 ③ ↔ 新 ⑧ 出現沒有 `key=`、而且兩頁都畫得到的元素：\n"
        + "\n".join(f"  {_m}:{_ln}  st.{_e}" for _m, _e, _ln in sorted(_hits))
        + "\n→ 這是提醒不是責備：**回報總管**，由 ⑧ 那一組決定修在哪一側"
          "（`ui/views/page_03_research.py` 不在本批邊界內）。")


def test_the_known_static_candidates_between_old_two_and_new_six_are_registered():
    """⚠️ **⑥ 的靜態候選：2026-09-08 已由 #822 閘門化，本條隨之換方向釘。**

    ## 本條原本登記的是什麼（原文保留，因為它是這條測試存在的理由）

    本組的掃描器（A 段）在 **舊 ② ↔ 新 ⑥** 之間找到 **4 個**沒有 key、
    而且兩頁都跑得到的元素，全部在
    `ui/helpers/fund_grp_health/backtest_section.py::render_allocation_backtest_section`
    （`st.dataframe` ×3、`st.plotly_chart` ×1）。當時 `ui/views/page_02_health.py`
    不在該批的檔案邊界內，所以**只登記、不修**，並寫明「清單一變就該回頭判一次」。

    ## 清單真的變了，而且是因為**它被修好了**

    #822 在 `ui/views/page_02_health.py::_render_delegated_sections` 加了
    **Checkbox Gate**（`st.checkbox(..., value=False)`、無 `key=`、在 form 外），
    於是那七支委派全部落到閘門之後 —— :func:`_reach` 只走 :func:`_ungated` 的節點，
    **候選集合因此變成空的**。這正是本條要求的「回頭判一次」，已經判完。

    ⛔ **所以本條改成 `== []`，但這不是把它放寬，是把它換一個方向釘死**：
    今天它守的是「**那道閘門不准消失**」。
    ~~有人拿掉閘門、或在閘門之外重新委派
    任何一支會畫無 key 元素的舊模組，候選集合就會再度非空，**本條立刻轉紅**。~~
    （突變實測：把閘門的 `if not _open: … return` 拿掉 → 本條轉紅。）

    ⚠️ **2026-09-08 就地更正：上面劃掉那句的後半是假的。有意識的更正，不是漏刪。**
    **決策者：AI 總管**（依 #822 獨立稽核實測；本組**已自行重現**，不是照收）。

    **舊表述在寫下當天是善意的、而且前半仍然為真** ——「拿掉閘門會紅」本組重現確認。
    **被推翻的是它的後半**：「**任何**一支」。**它的射程被高估成三倍。**

    ⭐ **三顆突變逐一注入的實測結果（在閘門之【前】各插一行委派，其餘不動）**::

        注入的委派                                          修正前     修正後
        ────────────────────────────────────────────────  ────────  ────────
        backtest_section.render_allocation_backtest_section   RED ✅    RED ✅
        correlation._render_correlation_matrix                GREEN ❌  RED ✅
        dividend._render_dividend_matrix                      GREEN ❌  RED ✅
        （控制組：不注入）                                    GREEN     GREEN

    **為什麼只有一顆紅 —— 根因不在閘門那一側，在 :func:`_reach` 追不進 shim**：
    舊 ② 觸及那三支的路徑**不一樣**。`ui/tab_fund_grp_health.py` 對
    `backtest_section` 是**直接 import**，所以 :func:`_reach` 追得到；
    另兩支它走的是 `from ui.helpers.fund_grp_health_extras import
    render_fund_grp_health_extras`，而那個檔是 **38 行、`FunctionDef` 0 個的純
    re-export shim** ⇒ `_funcs(mod).get(fname)` 回 `None` ⇒ **整條追蹤在那裡無聲斷掉**
    ⇒ `_reach(舊 ②)` 裡根本沒有那兩支 ⇒ 交集恆空 ⇒ **守衛安靜地放行**。

    ⚠️ **這是 merge-base 就有的盲點，不是誰在 #822 弄壞的** ——
    它同時解釋了另一件當時看不懂的事：本掃描器當初**只登記到 `backtest_section`
    一個模組**，而姊妹檔 `tests/test_dual_track_plotly_id_collision.py`
    數出來的危險模組是**三個**。兩邊對不起來的原因就是這個 shim
    （那個檔**有**橋接它，見該檔 `test_the_gate_still_has_a_reason_to_exist`
    裡的 `bridge = ROOT / "ui" / "helpers" / "fund_grp_health_extras.py"`）。

    ⭐ **括號裡那句「拿掉閘門 → 轉紅」本組也重跑過，它仍然為真** ——
    而且它現在**多說了兩件事**：把閘門短路掉（`if False and not _open:`，
    語法合法、`ast.parse` 過）之後，候選命中的模組
    **修正前只有 `backtest_section` 一個，修正後是三個全到**。
    ⇒ 同一顆突變，**紅的顏色沒變，但它照出來的模組從一個變成三個**。
    這就是「射程」與「宣稱」的差別：舊守衛不是不會紅，是**紅得不夠寬**，
    而那句「任何」把不夠寬的說成了全覆蓋。

    ✅ **2026-09-08 已補**：:func:`_reexport_home` ⇒ 上表右欄三顆全紅。
    ⛔ **但仍然不得寫成「任何」** —— 這條守衛看得到什麼、看不到什麼，逐條寫在檔尾
    射程聲明（第 6 項專講 shim 的殘留邊界）。**下面這句才是現在成立的版本**：

    ✅ **成立的宣稱**：閘門被拿掉、或有人在閘門之外重新委派一支
    **「本掃描器追得到、而且會畫 `_AUTOID_ELEMS` 白名單內無 `key=` 元素」**
    的舊模組 ⇒ 本條轉紅。
    ⛔ **不成立的宣稱**：「任何舊模組都會紅」。**動態組出的呼叫、白名單外的元素、
    以及本檔檔尾第 1／2／6 項所列的形態，本條結構上看不見。**

    ## ⚠️ 兩件必須一起讀的事，否則本條的 `== []` 會被誤讀成「這件事沒問題了」

    1. **`== []` 只代表「新 ⑥ 這一側關著」，不代表那些元素安全。**
       舊 ② 仍然無條件畫它們；閘門一勾，兩份就同時存在。
       灰態本文因此明寫「勾下去會發生什麼」，**不把勾選講成解法**。
    2. **真正危險的只有 `st.plotly_chart`，`st.dataframe` 不會撞** ——
       上面原文寫的「4 個」是本掃描器的候選數（它保守地把兩種都算進來）。
       實測 streamlit 1.59.1：`plotly_chart.py` **無條件**
       `compute_and_register_element_id(...)`；而 `arrow.py`（`st.dataframe`）
       的同一支呼叫**包在 `if is_selection_activated:` 裡**
       （`= on_select != "ignore"`，預設 `"ignore"`）⇒ **不註冊 id、撞不了**。
       ⇒ 真正的 collision surface 是 **3 個 `plotly_chart`**
       （`backtest_section` / `correlation` / `dividend`），
       **不是** `backtest_section` 那 4 個。
       ⛔ 本條**不改**上面那個保守的掃描器 —— 掃描器寧可多抓，那是對的；
       這一段只是把「候選 ≠ 一定會撞」講清楚，免得下一個人照著 4 這個數字去修錯地方。

    **完整機制、逐模組清單與突變表**：見 `tests/test_dual_track_plotly_id_collision.py`
    與 #822 的 PR 描述。**閘門的前提守衛**（舊 ② 一旦不再畫同一批圖就轉紅、
    並指明正解是拿掉閘門）在該檔的
    `test_the_gate_still_has_a_reason_to_exist`。
    """
    _hits = _collision_candidates(_OLD2, _NEW6)
    _by_mod = sorted({_m for _m, _, _ in _hits})
    assert _by_mod == [], (
        "舊 ② ↔ 新 ⑥ 之間又出現「不必點就跑得到、而且沒有 key」的元素：\n"
        + "\n".join(f"  {_m}:{_ln}  st.{_e}" for _m, _e, _ln in sorted(_hits))
        + "\n→ #822 的 Checkbox Gate 應該讓這個集合維持空的。"
          "\n   要嘛閘門被拿掉了，要嘛有人在閘門**之外**新增了委派。"
          "\n   ⛔ 正解是把新的委派移到閘門之後，**不是**把本條的期望值改成非空。")


#: 本 repo 的 **re-export shim** 實例，用來釘住 :func:`_reexport_home` 不再退化。
#: ⚠️ **這是「已知實例」，不是掃描器的判準** —— 判準是通則（見 :func:`_reexport_home`），
#:    所以新長出來的 shim 會自動被涵蓋，**不必**回頭加進本 tuple。
#:    本 tuple 只負責：這一個已經害守衛說過謊的檔案，不准再讓它靜靜地斷掉。
_KNOWN_REEXPORT_SHIM = ("ui.helpers.fund_grp_health_extras",
                        "render_fund_grp_health_extras")


def test_the_scanner_can_see_through_a_pure_reexport_shim():
    """⭐ **這條守的是「守衛的射程」本身 —— 2026-09-08 補。**

    在它之前，:func:`_reach` 追到純 re-export shim 就**無聲斷掉**，
    於是本檔另一條守衛的 docstring 寫著「**任何**一支……都會轉紅」，
    而實測 3 支只有 1 支會紅（表在
    :func:`test_the_known_static_candidates_between_old_two_and_new_six_are_registered`）。
    **一條宣稱涵蓋「任何」、實際只涵蓋三分之一的守衛，比沒有守衛更危險** ——
    下一個人會信它，然後停止自己檢查。本條就是那句話的機器版本。

    ⚠️ **本條紅了有兩種可能，訊息裡分開講**：
    (a) shim 追蹤壞掉了 → 修 :func:`_reexport_home`，**不要放寬本條**；
    (b) 那個 shim 被刪掉／改寫成真函式了（v19.198 留下的相容層總有一天會走）
        → 那是好事，**把本條連同 `_KNOWN_REEXPORT_SHIM` 一起刪掉**，不要留一條指著
        不存在的檔案的測試。
    """
    _mod, _fn = _KNOWN_REEXPORT_SHIM
    if _mod_path(_mod) is None:                       # (b) shim 已經不在了
        pytest.skip(f"`{_mod}` 已不存在 —— 見本條 docstring 的 (b)，"
                    "請刪掉本條與 `_KNOWN_REEXPORT_SHIM`，不要留著空轉。")

    # 前提：它真的是「純轉出」——一個 FunctionDef 都沒有。前提變了要有人知道。
    _t = _tree(_mod)
    assert _t is not None
    _own = [_n for _n in ast.walk(_t)
            if isinstance(_n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    assert not _own, (
        f"`{_mod}` 已經不是純 re-export shim 了（它自己定義了 {[_n.name for _n in _own]}）"
        " —— 本條的前提變了，請回來重新判斷，不要直接放寬。")

    _home = _reexport_home(_mod, _fn)
    assert _home is not None, (
        f"`{_reexport_home.__name__}` 追不到 `{_mod}::{_fn}` 的家 —— "
        "shim 追蹤壞了。⛔ 正解是修 `_reexport_home`，不是放寬本條。")

    _seen = _reach(_mod, _fn)
    assert _home in _seen, f"追到了家 {_home} 卻沒有把它收進可達集合"
    # 真正的重點：**經過 shim 之後還要能繼續往下追**，不是只跳一格。
    _downstream = {
        ("ui.helpers.fund_grp_health.correlation", "_render_correlation_matrix"),
        ("ui.helpers.fund_grp_health.dividend", "_render_dividend_matrix"),
    }
    _missing = sorted(_downstream - _seen)
    assert not _missing, (
        f"穿過 shim 之後追不到 {_missing} —— 追蹤只跳了一格就停了。\n"
        "這正是 2026-09-08 修掉的那個 fail-open：交集恆空 ⇒ 守衛安靜地放行。")


#: ⭐ **驗收表**：在閘門**之前**各注入一行委派，本檔的候選守衛必須**每一顆都紅**。
#: 2026-09-08 之前只有第一顆會紅（後兩顆走 re-export shim，掃描器看不見）。
_UNGATED_DELEGATE_MUTANTS: tuple[tuple[str, str], ...] = (
    ("ui.helpers.fund_grp_health.backtest_section",
     "render_allocation_backtest_section"),
    ("ui.helpers.fund_grp_health.correlation", "_render_correlation_matrix"),
    ("ui.helpers.fund_grp_health.dividend", "_render_dividend_matrix"),
)

_P02 = REPO_ROOT / "ui/views/page_02_health.py"
#: 閘門那一行。注入點在它**之前**（＝閘門之外）。
_GATE_LINE = ("    _open = st.checkbox(DELEGATE_GATE_LABEL, value=False, "
              "help=_delegate_gate_help())")


def test_every_ungated_redelegation_really_turns_the_candidate_guard_red():
    """⭐⭐ **把上面那句宣稱釘成可執行的驗收表 —— 三顆全紅，控制組綠。**

    突變紀律逐條落地（與 :func:`test_the_scanner_really_catches_a_reintroduced_ungated_delegate`
    同一套）：**不寫任何檔案**（只換記憶體裡的 AST）、突變體先 `ast.parse` 過
    （語法錯 ＝ **當機紅**，不是**守衛紅**，不計）、用 `str.replace` 而**不用
    `ast.col_offset` 切字串**（那是 **UTF-8 位元組**位移，本 repo 的檔案滿是中文，
    用字元索引切會讓突變**根本沒套上卻回報綠**）、斷言位元組真的變了、
    事後 `sha256` 逐位元組確認 production 檔沒被碰過。

    ⚠️ **控制組（不注入必須綠）是這一條的另一半** —— 少了它，一條恆紅的斷言
    也會讓上面三個 `assert` 全過，那等於什麼都沒驗。

    ⛔ **不要「優化」它 —— 本條刻意每一輪都重呼叫 :func:`_collision_candidates`。**
    本機實測（暖快取）約 **7.8s**，其中約 4 × 1.8s 花在重算 `_reach(*_OLD2)` 上，
    而 `_reach(*_OLD2)` **實測不含任何 `ui.views.*`**（＝突變 `page_02_health`
    影響不到它），所以把它提到迴圈外**在今天是正確的**。
    **不那樣做的理由**：那必須把 :func:`_collision_candidates` 的內容抄一份到本條裡，
    於是「被驗的那個判準」與「驗它的那條測試」就變成**兩份會各自漂移的東西** ——
    而本檔整個 2026-09-08 這一輪，修的正是「守衛與它的宣稱對不起來」。
    ⇒ **省 5 秒不值得換一個會靜靜分岔的判準。** fast lane 現況約 5 分鐘，本條約 +2.7%。
    ⛔ 也**不得**改用 `@pytest.mark.slow` 搬到 slow lane —— 那條 lane 掛
    `continue-on-error: true`，紅了不會擋 merge，等於把守衛降級。
    """
    _before = hashlib.sha256(_P02.read_bytes()).hexdigest()
    _src = _P02.read_text(encoding="utf-8")
    assert _src.count(_GATE_LINE) == 1, (
        f"注入錨點出現 {_src.count(_GATE_LINE)} 次，不是 1 —— 錨點已漂移，"
        "請更新本測試而不是放寬它。")

    def _candidates() -> set[tuple[str, str, int]]:
        return _collision_candidates(_OLD2, _NEW6)

    assert not _candidates(), "控制組就已經非空 —— 這一輪的紅綠都不算數"

    _blind: list[str] = []
    for _mod, _fn in _UNGATED_DELEGATE_MUTANTS:
        _inj = (f"    from {_mod} import {_fn} as _probe_delegate\n"
                f"    _probe_delegate([])\n" + _GATE_LINE)
        _mut = _src.replace(_GATE_LINE, _inj)
        assert _mut.encode() != _src.encode(), "替換沒套上，這一輪不算驗過"
        assert _mut.count("_probe_delegate") == 2, "注入不完整"
        ast.parse(_mut)                      # 語法先過，否則是當機紅不是守衛紅
        _TREE_CACHE["ui.views.page_02_health"] = ast.parse(_mut)
        try:
            _hits = _candidates()
        finally:
            _TREE_CACHE.pop("ui.views.page_02_health", None)
        if not _hits:
            _blind.append(f"{_mod}::{_fn}")

    assert not _blind, (
        "在閘門**之外**重新委派下列舊模組，候選守衛**沒有轉紅** —— 它對這些是瞎的：\n"
        + "\n".join(f"  {_x}" for _x in _blind)
        + "\n\n2026-09-08 的根因是 :func:`_reach` 追不進 re-export shim"
          "（`ui/helpers/fund_grp_health_extras.py`）。\n"
          "⛔ 正解是把追蹤補起來（`_reexport_home`），**不是**把本條的期望值改掉。")

    assert hashlib.sha256(_P02.read_bytes()).hexdigest() == _before, \
        "本測試污染了 production 檔"


#: 舊 ⑤ **無條件**（一次都不必點）就會呼叫的委派 —— 新 ⑦ 的四顆 gate 全部靠它成立。
_OLD_FIVE_UNCONDITIONAL: tuple[str, ...] = (
    "render_manual_tab",
    "render_manage_tab",
    "render_nav_manual_section",
    "render_fetch_diag_from_session",
)


def test_the_premise_behind_every_gate_still_holds():
    """⭐ **四顆 gate 的前提是「舊 ⑤ 無條件畫同一份」。前提沒了，gate 就是純損失。**

    雙軌是**過渡狀態**：舊 ⑤ 哪天下架，這四顆 gate 會從「防撞」變成
    「無緣無故要使用者多點四下」。本條就是那一天的**紅燈**——
    它一紅，正解是**把 gate 拿掉**，不是放寬本條。

    ⚠️ 這也是本輪四個修法**可逆**的憑據：改動全部集中在新頁側、全部繫於這個前提。
    """
    _reached = _reach(*_OLD5)
    _got = {_f for _, _f in _reached}
    _missing = [_d for _d in _OLD_FIVE_UNCONDITIONAL if _d not in _got]
    assert not _missing, (
        f"舊 ⑤ 已經不再無條件呼叫 {_missing} —— 新 ⑦ 對應的 Checkbox Gate "
        "失去存在理由（它們是為了防撞才加的）。\n"
        "→ 正解：把 `ui/views/page_05_settings.py` 那幾顆 gate 拿掉，"
        "並同步刪掉本條與它的灰態本文。**不要放寬本條。**")


def test_the_gates_carry_no_key_and_sit_outside_any_form():
    """⭐ 本 repo 在同一個閘門上踩過的兩顆雷，逐一釘住。

    - ⛔ **不得帶 `key=`**：streamlit 會代為寫 `session_state`，命中
      `tests/test_wf05_settings_skeleton.py::test_the_page_writes_only_its_own_session_key`
      （本頁只准寫 `_SK_DIAG_GATE` 一個鍵）。
    - ⛔ **不得放進 `st.form`**：form 內的 checkbox 要按送出鍵才生效，
      gate 會變成兩段式；而 `st.form` 本身正是本輪在解的衝突源之一。
    """
    _t = _tree("ui.views.page_05_settings")
    assert _t is not None
    _forms = [_n for _n in ast.walk(_t) if isinstance(_n, ast.With)
              for _i in _n.items
              if isinstance(_i.context_expr, ast.Call)
              and getattr(_i.context_expr.func, "attr", None) == "form"]
    _in_form = {_x.lineno for _f in _forms for _x in ast.walk(_f)}

    _gate_calls = [_n for _n in ast.walk(_t)
                   if isinstance(_n, ast.Call)
                   and getattr(_n.func, "attr", None) == "checkbox"]
    assert len(_gate_calls) >= len(GATE_LABELS), (
        f"本頁的 `st.checkbox` 只有 {len(_gate_calls)} 個，少於四顆 gate —— "
        "有 gate 被拿掉了？")
    for _c in _gate_calls:
        _keys = [_k for _k in _c.keywords if _k.arg == "key"]
        if _keys:
            # 只有資料診斷那一顆准帶 key（`_SK_DIAG_GATE`，本頁自己的命名空間）。
            assert all(getattr(_k.value, "id", None) == "_SK_DIAG_GATE"
                       for _k in _keys), (
                f"L{_c.lineno} 的 checkbox 帶了不是 `_SK_DIAG_GATE` 的 `key=` —— "
                "那會寫進 session_state，命中本頁的「只准寫自己的鍵」守衛。")
        assert _c.lineno not in _in_form, (
            f"L{_c.lineno} 的 gate checkbox 落在 `st.form` 裡 —— "
            "form 內的 checkbox 要按送出鍵才生效，gate 會變成兩段式。")


#: 四則灰態本文各自**必須**講出「勾下去會發生什麼」。
#: ⚠️ 比對的是**機制關鍵字**（會撞到什麼、變成什麼），不是整句文案 —— 釘文案等於
#:    每次改字就紅一次（本 repo 明令不釘文案）。
_TICK_CONSEQUENCE: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("_maintain_not_loaded_note", ("勾上面那個選項，這一塊就會變成紅色錯誤",
                                   "divcal_gen")),
    ("_backfill_not_loaded_note", ("勾上面那個選項，這一塊就會變成紅色錯誤",
                                   "navhist_import_form")),
    ("_manual_not_loaded_note", ("指標地圖", "紅字")),
    ("_fetch_diag_not_loaded_note", ("兩塊一模一樣", "不會報錯")),
)


def test_the_grey_notes_say_what_ticking_actually_does():
    """⭐ **§1：畫面不准把「按下去就壞」講成「按下去就好」。**

    ⚠️ **這一條擋的是一個真的發生過、而且很難看出來的謊**：
    修改前的兩則灰態本文寫的是

        「…載入兩份會撞到 Streamlit 的重複元件鍵…那一塊會整塊變成紅色錯誤。
          **勾上面那個選項，本頁才會載入自己的一份**；功能沒有少…」

    每一句話單獨看都是真的，**合起來卻把「勾」講成解法** —— 讀者的結論是
    「勾了就有我自己的一份」，而實際上**勾下去正是撞的那一刻**。
    ⛔ 這比「只寫在 `help=` tooltip 裡」更糟：tooltip 是**沒說**，這是**說反**。

    ⚠️ 本條驗的是**本文字串**（AST 取 `Constant`），不是畫面 ——
       畫面那一層由 `test_wf05_settings_skeleton.py` 的灰態守衛負責。
    """
    _t = _tree("ui.views.page_05_settings")
    _defs = {_n.name: _n for _n in ast.walk(_t)
             if isinstance(_n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for _fname, _segs in _TICK_CONSEQUENCE:
        assert _fname in _defs, (
            f"`{_fname}` 不見了 —— 本條正指著一個不存在的名字。")
        _body = "".join(_n.value for _n in ast.walk(_defs[_fname])
                        if isinstance(_n, ast.Constant) and isinstance(_n.value, str))
        for _seg in _segs:
            assert _seg in _body, (
                f"`{_fname}` 的灰態本文沒有講出「勾下去會發生什麼」——"
                f"缺少 {_seg!r}。\n"
                "⛔ 只講機制、不講後果，等於讓使用者勾了才發現壞掉（§1）。\n"
                f"現有本文：{_body[:400]}")


# ══════════════════════════════════════════════════════════════════
# B 段｜AppTest（需要 streamlit —— **本機跑不了，數字全部來自 CI**）
# ══════════════════════════════════════════════════════════════════
streamlit_testing = pytest.importorskip(
    "streamlit.testing.v1", reason="streamlit < 1.28 不支援 AppTest")
AppTest = streamlit_testing.AppTest


@pytest.fixture(scope="module", autouse=True)
def _hermetic():
    """AppTest 只驗 UI 渲染，不外連（沿用 `tests/test_app_apptest.py` 的既有做法）。"""
    _mp = pytest.MonkeyPatch()
    for _pv in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        _mp.setenv(_pv, "http://127.0.0.1:9")
    _mp.delenv("NO_PROXY", raising=False)
    _mp.delenv("no_proxy", raising=False)
    import ui.hot_money as _hm
    _orig = _hm.refresh_hot_money_data
    _hm.refresh_hot_money_data = lambda *a, **k: (False, "skipped in AppTest")
    yield
    _hm.refresh_hot_money_data = _orig
    _mp.undo()


def _boot() -> Any:
    _at = AppTest.from_file(str(APP_PY), default_timeout=90)
    _at.secrets["FRED_API_KEY"] = "test-fred-key"
    _at.secrets["GEMINI_API_KEY"] = "test-gemini-key"
    _at.run()
    return _at


def _texts(elements) -> list[str]:
    return [str(getattr(_e, "value", _e) or "") for _e in elements]


def _errors(at: Any) -> list[str]:
    """畫面上所有**紅框**（嚴重度 1）。"""
    return _texts(at.error)


def _warnings(at: Any) -> list[str]:
    """畫面上所有**黃框**（嚴重度 2）。

    ⚠️ **非有不可**：`ui/tab_manage.py::_sec_pool` 用自己的 `try` →
    `_friendly(...)`（**預設 `level="warning"`**）把 `pool_add_form` 的重複
    降級成一則黃字 —— **任何只驗 `st.error` 的檢查對它結構上不可見**。
    """
    return _texts(at.warning)


def _count_in_stream(at: Any, needle: str) -> int:
    """整個畫面（markdown / caption / text / 各式框）出現 `needle` 幾次（嚴重度 3）。

    ⭐ **這是第三種嚴重度唯一抓得到的方式** —— ④「安靜地畫兩份」既不是紅框
       也不是黃框，**只能靠數次數**。
    """
    _parts: list[str] = []
    for _attr in ("markdown", "caption", "text", "info", "warning", "error",
                  "success", "subheader", "header", "title"):
        try:
            _parts += _texts(getattr(at, _attr))
        except Exception:                      # noqa: BLE001 — 該版沒有這個取值器
            continue
    return sum(_p.count(needle) for _p in _parts)


@pytest.fixture(scope="module")
def at_default(_hermetic) -> Any:
    """預設狀態：七格全渲染，使用者**一次都沒有點**。"""
    return _boot()


def test_the_gate_labels_this_file_hardcodes_are_really_on_screen(at_default: Any):
    """本檔手抄的四個閘門標籤，必須真的在畫面上。

    ⚠️ 沒有這一條，下面「勾起來會怎樣」的測試會在標籤改名之後**靜默地什麼都沒勾到**
       然後回報綠 —— 那是**守衛失去對象**，不是守衛通過。
    """
    _labels = [_c.label for _c in at_default.checkbox]
    assert _labels, "畫面上一個 checkbox 都沒有 —— harness 壞了，不是 app 乾淨"
    for _want in GATE_LABELS:
        assert _want in _labels, (
            f"手抄的閘門標籤 {_want!r} 不在畫面上；現有標籤：{_labels}")


def test_default_load_draws_the_fetch_diag_panel_exactly_once(at_default: Any):
    """⭐ **④「安靜地畫兩份」** —— 紅框黃框都看不到它，只能數次數。

    修改前：舊 ⑤ `_render_conn_section` 與新 ⑦ `_render_keys` **都無條件**呼叫
    `render_fetch_diag_from_session()` → 畫面上兩塊一模一樣，Streamlit 一聲不吭。
    （③ 個基頁那一份由 `app.py` 持有的 `FETCH_DIAG` 旗標壓住，不在這裡算。）

    修改後：新 ⑦ 那一份收進 Checkbox Gate，預設不畫 → 全站恰好一份（舊 ⑤ 的）。
    """
    _n = _count_in_stream(at_default, FETCH_DIAG_FINGERPRINT)
    assert _n == 1, (
        f"「🔍 抓取診斷細節」在預設載入時出現 {_n} 次，應該恰好 1 次。\n"
        "  0 次 → 舊 ⑤ 那一份也不見了（那是功能消失，不是修好）；\n"
        "  2 次 → 新 ⑦ 的 gate 沒擋住，使用者會看到兩塊一模一樣的面板。")


def test_default_load_has_no_visible_error(at_default: Any):
    """⭐ **① 零點擊紅框** —— 這一條在 `origin/main` 是紅的（#819 已釘死）。

    根因：`render_manual_tab()` 被舊 ⑤ 與新 ⑦ **各畫一次**，而
    `ui/tab1_macro.py::render_indicator_map` 的 `st.plotly_chart` **不帶 key**。
    修法：新 ⑦ 那一份加 Checkbox Gate（⛔ 不改舊 `ui/tab*.py`）。

    ⛔ **不得**為了轉綠而放寬、加白名單或 skip 本條 —— 那會把一個
       **使用者今天打開就看得到**的紅框重新藏起來。
    """
    _errs = _errors(at_default)
    assert not _errs, (
        f"預設載入出現 {len(_errs)} 個紅框（使用者一打開、什麼都還沒點就會看到）：\n"
        + "\n".join(f"  [{_i}] {_e[:400]}" for _i, _e in enumerate(_errs)))


def test_default_load_has_no_duplicate_key_warning(at_default: Any):
    """⭐ **② 的另一半：黃框。** 只驗 `st.error` 的檢查對它結構上不可見。"""
    _hit = [_w for _w in _warnings(at_default)
            if "pool_add_form" in _w or "DuplicateElement" in _w]
    assert not _hit, (
        "預設載入出現重複元件鍵的**黃框**（被 `_friendly` 降級成 warning，"
        f"紅框檢查看不到它）：\n{[_w[:300] for _w in _hit]}")


def test_default_load_has_no_uncaught_exception(at_default: Any):
    """對照組：證明本檔的 harness 與既有 slow lane 那條看到的是同一個 app。

    ⚠️ 這一條**在修好之前就已經是綠的** —— 那正是問題所在：①②③④ 全部被
    `safe_section` / 分頁級 `try` 接住，`at.exception` 對它們**永遠是空的**。
    """
    assert not at_default.exception, \
        f"app.py 未捕捉例外：{[str(_e) for _e in at_default.exception]}"


def _tick(at: Any, label: str) -> Any:
    """依**標籤**勾起一個 checkbox 並重跑。

    ⛔ 不用 `at.checkbox[i]` —— 索引會隨畫面漂移，勾錯一顆而測試照樣綠。
    """
    for _c in at.checkbox:
        if _c.label == label:
            _c.check()
            at.run()
            return at
    raise AssertionError(
        f"畫面上找不到標籤為 {label!r} 的 checkbox；"
        f"現有：{[_c.label for _c in at.checkbox]}")


def test_ticking_the_manual_gate_brings_the_collision_straight_back(_hermetic):
    """⭐⭐ **突變驗證的 runtime 版：把同一顆「植」回去，紅框必須回來。**

    ⚠️ **這裡不需要改任何一行程式碼** —— 勾起使用手冊那顆 gate，
    就是把「兩頁同時畫 `render_manual_tab()`」原封還原。紅框回來 ＝
    :func:`test_default_load_has_no_visible_error` 抓得到的是**真的東西**，
    而不是一條恆綠的裝飾。

    ⚠️ **這也是灰態本文承諾的事實檢查**：`_manual_not_loaded_note()` 逐字寫著
    「勾上面那個選項……「指標地圖」那一小塊會變成紅字」。
    **如果這一條紅了（勾了卻沒有紅框），那句話就是在說謊**，必須改本文，不是改本條。
    """
    _at = _tick(_boot(), MANUAL_GATE_LABEL)
    _errs = _errors(_at)
    _hit = [_e for _e in _errs
            if "指標地圖" in _e or "DuplicateElementId" in _e]
    assert _hit, (
        "勾起使用手冊 gate 之後**沒有**看到指標地圖的重複 element ID 紅框 —— "
        "要嘛守衛是假的，要嘛灰態本文那句承諾已經不成立（兩種都要處理）。\n"
        f"實際紅框：{[_e[:300] for _e in _errs]}")


# ── ⑥（新 ②）：前組只做靜態盤點、沒跑過，本檔實際跑 ────────────────────
def test_the_health_preview_tab_is_clean_on_default_load(at_default: Any):
    """⭐ **⑥ 那一格也要看** —— 前一輪只比對 literal key（交集 0）就收工，
    而 ① 正是**靜態掃不到、跑起來才現形**的那一類。

    本條與上面幾條共用同一次 `_boot()`：`st.tabs` 一次 run 會把**七格全部**執行過，
    所以 ⑥ 的問題會出現在同一份 `at.error` / `at.warning` 裡。

    ⚠️ **本條的精度上限，就地寫明**：AppTest 的元素樹是**攤平**的，
       拿不到「這個紅框屬於哪一格 tab」。本條靠**訊息內容**判斷歸屬 ——
       所以它抓得到「⑥ 那一格整個炸掉」與「訊息點名 backtest 那些符號」，
       **抓不到**「⑥ 裡某塊安靜地畫了兩份」。後者由下方的靜態候選清單登記。
    """
    _bad = [_m for _m in _errors(at_default) + _warnings(at_default)
            if "持倉體檢" in _m or "DuplicateElement" in _m
            or "StreamlitAPIException" in _m]
    assert not _bad, (
        "⑥/② 那一對在預設載入時出現紅框或黃框：\n"
        + "\n".join(f"  {_m[:400]}" for _m in _bad))


# ══════════════════════════════════════════════════════════════════
# ⚠️ 本檔**沒有**涵蓋的範圍（據實列出，不要把「沒測到」讀成「沒問題」）
# ══════════════════════════════════════════════════════════════════
# 1. **`_AUTOID_ELEMS` 是白名單，不是窮舉。** Streamlit 新增的元素、
#    以及本 repo 自己包一層的 helper（例如 `ui/helpers/ia/*` 內部再呼叫 `st.*`）
#    只有在該 helper 本身被追到時才看得見；**動態組出來的呼叫一律看不見**。
# 2. **靜態分析看不到 runtime 的資料分支。** `render_allocation_backtest_section`
#    在「沒有持倉」時可能整段 return —— 掃描器**照樣把它列為候選**（寧可多抓）。
#    反過來，`if len(df) > 0:` 底下才畫的元素，掃描器**看得到**但 CI **跑不到**。
# 3. **CI 沒有 Google 憑證、沒有持倉。** `_sec_pool` / nav_history / 保單管理
#    走的都是「未登入」分支。**有憑證的使用者可能撞到更多。**
#    已知例子：`ui/helpers/portfolio/policy_admin_section.py` 有一整批
#    帶 key 與不帶 key 的元素，兩頁都委派得到，但它整段在
#    `merge_context.POLICY_ADMIN` 旗標後面，而 `app.py` **一次都沒有持有過它**
#    → 今天到不了。**旗標一開就會撞**，接線批次必須先處理。
# 4. **兩顆同名的「🔭 載入資料診斷」**（舊 ⑤ 一顆、新 ⑦ 一顆）同時勾 —— 要
#    **兩次點擊**，本檔沒有跑過（`_tick()` 依標籤找，兩顆同名只會勾到第一顆）。
#    #819 檔尾也記了同一項，狀態未變。
# 5. ~~**③④ 兩格（`page_03_research` / `page_04_portfolio`）本檔完全沒有掃** ——
#    它們目前沒有掛上雙軌預覽格，但這是**本組沒有查證**的印象，不是實測。~~
#    → **2026-09-07 就地更正（有意識的更正，不是漏刪 · 決策者：AI 總管 · 依據：實測）**：
#    **那個「印象」是錯的**，而且在寫下它的**同一天**就被推翻 —— #820 已把
#    `ui/views/page_03_research.py` 掛成第 **⑧** 格（`app.py` 的 `tab_preview_research`），
#    也就是說本檔開工時（`ac7050e`）為真的事，在合併 `origin/main` 之後不再為真。
#    **這正是本檔在講的那件事：憑印象寫下的全稱句，撐不過一次 merge。**
#    現況：**⑧ 已補掃**（見 `test_the_third_dual_track_pair_has_no_keyless_collision_either`，
#    命中 0）；**`page_04_portfolio` 仍未掛預覽格，本檔未掃**（實測 `app.py` 的
#    `st.tabs(...)` 目前是八格，沒有 ④ 的 `[新]` 那一格）。
# 6. **re-export shim：2026-09-08 補了追蹤，但只補到「純轉出」這一種。**
#    `_reach` 現在會經 :func:`_reexport_home` 穿過
#    `from X import a, b, c` 這類純轉出檔（本 repo 實例：
#    `ui/helpers/fund_grp_health_extras.py`、`ui/helpers/ia/__init__.py`、
#    `services/health/__init__.py`）。**沒有涵蓋的形態，逐一列出**：
#      (a) `from X import *` —— :func:`_names` 會把它存成一個**叫 `*` 的鍵**，
#          而沒有任何呼叫點叫 `*`，所以**永遠查不到、等於看不見**
#          （姊妹檔 `tests/test_wf02_health_golive.py::_resolve` **有**追 `*`；
#          本檔沒有，因為本 repo 的委派鏈上目前沒有 `*` shim，**但那是現況不是保證**）；
#      (b) 相對匯入 `from . import x` —— :func:`_names` 明文 `_n.level == 0` 才收；
#      (c) `x = X.y` 這種**賦值式**別名、`globals().update(...)`、`getattr` 等
#          動態轉出 —— 靜態一律看不見；
#      (d) `__all__` 與實際匯入不一致時，本掃描器以**實際 `ImportFrom`** 為準。
#    ⚠️ **也要知道它多抓了什麼**：:func:`_names` 連**函式內的 lazy import** 都收，
#    所以「模組 M 的某個函式裡 `from X import helper`」也會被當成 M 轉出 `helper`。
#    那是刻意的 over-approximation（fail-closed），**只會多抓、不會漏抓**。
