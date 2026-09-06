"""AST 綁定／session 寫入偵測 —— **三頁 form 閘門守衛 ＋ ⑤ 設定頁守衛共用的那一份**。

⚠️ **檔名刻意不以 `test_` 開頭**：這是工具模組，不是測試檔（pytest 不會收集它）。
   也**刻意不放進 `tests/conftest.py`** —— 那個檔是 fixture 的家，
   把工具函式混進去會讓「誰負責什麼」糊掉。

為什麼要有這一份（不要再寫第五份）
----------------------------------
2026-09-05 之前，repo 裡同時有**四份**各自為政的 AST 掃描：

===================================================== ======================================
`tests/test_settings_diag_merge.py::_reassigned_names` 綁定形態最完整，但看不到 `key=`
`tests/test_wpg_portfolio_health_link_20260831.py`     session 寫入四條管道最完整
②③④ 三頁的 `test_downstream_reads_the_applied_*`       **只認 `ast.Assign` ＋ `Subscript`**
===================================================== ======================================

最後那三份的實測後果（2026-09-05 本組跑的基線，三頁 × 四管道 × 兩種順序皆一致）：
**只有「下標賦值」抓得到，屬性賦值／`update()`／widget `key=` 三條全部無聲通過。**
其中**屬性賦值**是本 repo `ui/**` production 跨 6 檔 27 處的主流寫法 ——
下一個人照家風往那三頁寫一行，守衛不會出聲。

設計原則（照 `_reassigned_names` 贏的那兩點）
--------------------------------------------
1. **明列多種節點型別**，不要只認 `ast.Assign`。
2. **對 target 再跑一次** :func:`ast.walk` —— tuple／starred 解包因此自動涵蓋，
   不必逐一列舉 `ast.Tuple` / `ast.List` / `ast.Starred`。
"""
from __future__ import annotations

import ast

__all__ = ["bound_names", "const_str_values", "dotted", "gate_guarded_ids",
           "gate_ifs", "guarded_key_names", "session_writes"]


def dotted(node: ast.AST) -> str:
    """`st.session_state.k` → ``"st.session_state.k"``；認不得的形狀回 ``""``。

    只走 `Name` / `Attribute` 這條鏈；`f()[0].k` 這種中間有呼叫或下標的一律回 ``""``
    （**寧可認不得，也不要拼出一個假的路徑**）。
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        head = dotted(node.value)
        return f"{head}.{node.attr}" if head else ""
    return ""


# ── 1. 綁定形態 ──────────────────────────────────────────────────────────
def bound_names(tree: ast.AST, *, include_imports: bool = True) -> set[str]:
    """整棵樹裡**被綁過**的名字。

    涵蓋（每一種都實測過）::

        X = ...            ast.Assign          X: T = ...   ast.AnnAssign
        X += ...           ast.AugAssign       (X := ...)   ast.NamedExpr
        for X in ...       ast.For / AsyncFor  with ... as X ast.withitem
        a, (b, *c) = ...   ← 對 target 再 walk 一次，自動涵蓋
        import a.b [as X]  ast.Import          ← include_imports=True 才收
        from m import X    ast.ImportFrom      ← 同上

    **明確不涵蓋**（讀者請據此打折信任）：

    * ``globals()["X"] = ...`` / ``setattr(mod, "X", ...)`` / ``exec``
      —— 動態綁定，靜態上追不到，本函式**看不到**；
    * ``def X()`` / ``class X`` / 函式參數 —— 它們是綁定，但不是「重新指派」，
      刻意不收（收了會讓 :func:`_resolved_guard_flags` 那類 fail-closed 檢查全炸）；
    * ``del X``、`try/except ... as X`、`match` 的 capture pattern。

    :param include_imports:
        ``True``（預設）＝ 連 import 綁定一起收，適合「這個名字**從哪來**都算」的場景。
        ``False`` ＝ **只收重新指派**，給 ``tests/test_settings_diag_merge.py`` 用 ——
        那裡的語意是「import 綁定**是否被遮蔽**」，兩者必須分得開；
        收了 import 會讓它每一個 guard 引數都被判成「被重新指派過」。
        **2026-09-05 實測**（不是推論）：不帶這個開關直接改，
        `test_settings_diag_merge.py` 由 **26 passed** 變成 **5 failed / 21 passed**。
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        targets: list[ast.AST] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            targets = [node.target]
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            targets = [node.target]
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            targets = [node.optional_vars]
        elif include_imports and isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name == "*":       # `from m import *` —— 綁了什麼靜態上不知道
                    continue
                names.add(alias.asname or alias.name.split(".")[0])
            continue
        for t in targets:
            for sub in ast.walk(t):
                if isinstance(sub, ast.Name):
                    names.add(sub.id)
    return names


# ── 2. session 寫入的四條管道 ────────────────────────────────────────────
def const_str_values(tree: ast.AST, *names: str) -> set[str]:
    """把模組層 ``NAME = "字面值"`` 解析成 ``{"NAME", "字面值"}``。

    給 :func:`session_writes` 的 ``widget_key_names`` 用：守衛關心的 session key
    在原始碼裡可能寫成 **常數名**（``key=_SK_APPLIED``）也可能寫成 **字面值**
    （``key="health_applied_filters"``），**兩種都要認得**。

    解析不到字面值時**只回常數名**（不猜、不編一個假的值出來）。
    """
    out: set[str] = set(names)
    for node in ast.walk(tree):
        # ⚠️ `AnnAssign` 一定要在列：本 repo 三頁的寫法就是
        #    `_SK_APPLIED: str = "v02_health_applied_filters"`（帶型別註記）。
        #    只認 `ast.Assign` 會靜靜地只回常數名、拿不到字面值。
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        if not (isinstance(value, ast.Constant) and isinstance(value.value, str)):
            continue
        for t in targets:
            if isinstance(t, ast.Name) and t.id in names:
                out.add(value.value)
    return out


def guarded_key_names(tree: ast.AST, prefix: str = "_SK_") -> set[str]:
    """模組層所有 ``<prefix>*`` 常數的**名字與字面值**，餵給 `session_writes` 的
    ``widget_key_names``。

    ⭐ **為什麼是「自動收齊」而不是列舉**（2026-09-06 稽核 M-1，實測過的迴歸）：
    上一版三頁都寫死 ``const_str_values(_t, "_SK_APPLIED")`` —— **只餵一個常數名**。
    於是 ``key=_SK_PORTFOLIO``（**使用者的 live 持股**，由
    `ui/helpers/portfolio/linkage.py` 寫入、②④ 都在讀）那顆突變
    **從 `180fb93` 的 R/R/R 掉成 `d6c8cbc` 的 G/G/G**（三頁 × 三序實測）。
    一顆帶 `key=_SK_PORTFOLIO` 的 widget 擺在 form 內、閘門外，會在使用者
    **還沒按送出**時就把持股改掉 —— 而守衛看不到。

    **列舉一定會漏下一個新加的鍵**，所以改成掃前綴：**新增一個 `_SK_*` 就自動被守到**，
    方向是 fail-closed。

    ⚠️ **只掃模組層**（`tree.body`），不 `ast.walk` 進函式內 ——
    函式內的區域變數不是「這一頁的 session 鍵」，收進來會擴大射程而非收緊。
    ⚠️ **`AnnAssign` 與 `Assign` 兩種都要收**：本 repo 三頁的寫法是
    ``_SK_APPLIED: str = "…"``（帶型別註記）。只認 `Assign` 會一個都收不到。

    ⚠️ **刻意不收 `_FORM_KEY`**（它不帶 `_SK_` 前綴）：那是 form 自己的 widget 鍵，
    由 `applied_form()` 內部使用，**不是**這一頁的 session 資料鍵。

    ## ⭐ 這條命名契約必須被遵守，否則本函式的射程是假的

    **`_SK_*` ＝ 這一頁的 session 資料鍵；widget 自己的鍵不得用這個前綴。**
    ⚠️ **這推翻了 `eac2568` 當初立的分界**（「widget 寫自己的鍵不是違規」）——
    前綴一掃，「資料鍵」與「widget 自己的鍵」就**不再由用途區分，而是由命名區分**。
    下一個人若把 widget 的私有鍵取名 `_SK_MY_SLIDER`，它會被當成資料鍵、**誤紅**；
    反之若把真正的資料鍵取名 `_PORTFOLIO_KEY`（不帶前綴），它**不會被守到**。

    ## 明確**不涵蓋**（照實列，2026-09-06 稽核逐一實測，不要讀成「守死了」）

    * **模組層 `if:` / `try:` 區塊內**宣告的常數 —— 本函式只掃 `tree.body` 的
      直接子節點，不進 `body` 以外的巢狀區塊。
    * **walrus**（``_ = (_SK_X := "x")``）—— 不在 `Assign` / `AnnAssign` 兩種形態內。
    * **tuple 解包的字面值**：``_SK_A, _SK_B = "x", "y"`` 的**名字收得到**
      （上面那次修正），但 :func:`const_str_values` 不做 target↔value 配對
      ⇒ **`"x"` / `"y"` 這兩個字面值解析不到**。也就是 ``key=_SK_B`` 抓得到、
      ``key="y"`` 抓不到。
    * **`key=` 不是單純的名字或字面值**：``key=f"{_SK_X}"`` 與 ``key=_SK_X + ""``
      實測皆**漏放**（`session_writes` 的比對只吃 `ast.unparse` 全等或 `Constant` 值）。
    * **不帶 `_SK_` 前綴、卻指到同一個 session 鍵的常數** ——
      ``_PORTFOLIO_KEY = "portfolio_funds"`` 實測**漏放**。這正是上面那條命名契約
      存在的理由：**契約一破，本函式就守不到。**
    * **函式內宣告的常數**（刻意，見上）。
    """
    names: set[str] = set()
    for node in getattr(tree, "body", []):          # ← 模組層，不 walk
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        for t in targets:
            # ⚠️ **對 target 再 walk 一次** —— 本檔檔頭「設計原則」第 2 條，
            #    `bound_names()` 從一開始就這樣做，而本函式第一版**漏了**：
            #    只寫 `isinstance(t, ast.Name)` ⇒ `_SK_A, _SK_B = ...` 這種
            #    **tuple／list／starred 解包完全收不到**（2026-09-06 稽核實測：
            #    `_SK_A, _SK_B = "x", "portfolio_funds"` ＋ `key=_SK_B` → 三序全綠）。
            #    而本函式的 docstring 當時寫著「自動收齊」「fail-closed」——
            #    **一個會被下一個人當前提用的全稱句，被一行程式碼推翻。**
            for sub in ast.walk(t):
                if isinstance(sub, ast.Name) and sub.id.startswith(prefix):
                    names.add(sub.id)
    return const_str_values(tree, *names) if names else set()


def session_writes(fn_node: ast.AST, receiver: str = "st.session_state",
                   *, widget_key_names: set[str] | None = None) -> list[ast.AST]:
    """`fn_node` 本體內所有**寫進 session** 的節點，依行號排序、去重。

    回傳的是**可定位的節點**（`.lineno` / `ast.unparse()` 都能用）：
    賦值類回傳那一個陳述式，呼叫類回傳 `ast.Call`。

    ## 認得出來的四條管道（缺一條就等於沒守）

    ==== ================================ ==========================================
    #    管道                              例
    ==== ================================ ==========================================
    1    下標賦值                          ``st.session_state["k"] = v``
    2    **屬性賦值**                      ``st.session_state.k = v``
    3    **`update()` / `setdefault()`**   ``st.session_state.update(k=v)``
    4    **widget 的 `key=`**              ``st.selectbox(..., key="k")``
    ==== ================================ ==========================================

    第 4 種最陰：**streamlit 會代呼叫端把 widget 值寫進 `session_state`**，
    AST 上是一個普通 `ast.Call`，**任何「找賦值節點」的手段都收不到它**。

    第 1／2 種的賦值形態不只 `ast.Assign` —— `AnnAssign`（``st.session_state["k"]: dict = v``
    是合法 Python）、`AugAssign`、`for` target、`with ... as` target 全部涵蓋，
    且對 target 再 walk 一次，所以 tuple 解包（``st.session_state["a"], x = ...``）也算。

    ## ⭐ `widget_key_names` —— 管道 4 **必須**收窄，否則它是一條無解的偽陽性

    ``applied_form`` 的結構是**寫死的**（見 `ui/helpers/ia/gated_form.py`）::

        with applied_form(KEY) as _gate:
            ...widget 一定建在這裡（送出鈕在 yield 之後才建立）...
        if _gate:                      # ← 閘門一定在 with **之外**
            st.session_state[K] = ...

    ⇒ **帶 `key=` 的 widget 在結構上永遠不可能落在閘門 `if` 的 body 裡**，
    ``None``（預設，任何 `key=` 都算命中）會讓三頁**沒有任何合法擺法可以轉綠**。
    ⚠️ **一條永遠無法滿足的守衛比沒有守衛更糟** —— 下一個人只會做兩件事之一：
    把自己合法的 `key=` 刪掉（損失功能），或加一條豁免（守衛開始被侵蝕）。
    **`git grep -oE '\bkey=' -- 'ui/**' | wc -l` ＝ 231（量測日 2026-09-05）**，
    帶 `key=` 是本 repo 的家風，不是例外。

    傳入 ``widget_key_names`` 後，管道 4 **只在 `key=` 指到守衛真正在乎的那個
    session key 時才算命中** —— ``st.checkbox(..., key=_SK_APPLIED)`` 才是真違規
    （streamlit 會拿 widget 值蓋掉已套用值）；widget 寫**自己的**鍵不是違規。
    比對同時吃**常數名**與**字面值**（見 :func:`const_str_values`）。

    ⚠️ **這個判準刻意不依賴任何 streamlit runtime 語意** ——
    「form 內互動不觸發 rerun」那句**本組沒有實跑驗證過**，
    **不拿未驗的語意去支撐守衛**（那等於把一個未驗宣稱寫進規則）。
    本判準只用「這個 key 是不是守衛在乎的那個」這件**純靜態、可自驗**的事實。

    ## 明確**不**涵蓋（照實列，不要讀成「守死了」）

    * **不遞迴進被呼叫的函式** —— 只看 `fn_node` 這一個函式本體。
      把 `st.session_state` 傳給別的函式、由那邊寫，本函式看不到。
    * ``setattr(st.session_state, name, v)`` / ``globals()`` / ``exec`` 等動態寫法。
    * ``del st.session_state["k"]``（那是刪不是寫）、以及
      ``st.session_state |= {...}``（`AugAssign` 的 target 是 receiver 本身而非下標）、
      ``.pop()`` / ``.clear()``（它們改動 session 但不是「寫入一個值」）。
      **全 repo 目前 0 命中**（量測日 2026-09-05），登記待日後出現再評估。
    * `key=` 這條的 alias 判定靠「這個函式裡 `session_state` 用的是哪個模組名」推導；
      若某函式**完全沒碰 session_state**、又用非 `st` 的 alias 呼叫 widget，`key=` 那條會漏。

    :param receiver:
        session 容器的路徑。比對方式**對模組 alias 不敏感** ——
        只要 dotted 路徑的**最後一段**是 ``session_state``（取自本參數的最後一段），
        ``import streamlit as _s`` 之後的 ``_s.session_state`` 一樣抓得到。
        **另外**：函式內 ``_ss = st.session_state`` 這種**把容器接到本地名字**的寫法，
        其後的 ``_ss["k"] = v`` / ``_ss.update(...)`` 也算 —— 見下方 ``recv_aliases``。
    """
    attr = receiver.rsplit(".", 1)[-1]           # "session_state"
    root = receiver.split(".", 1)[0]             # "st"

    # 本地別名：`_ss = st.session_state` 之後，`_ss` 就是同一個容器。
    # ⚠️ 這一格是 2026-09-05 稽核挖出來的 before/after **覆蓋率倒退**：
    #    舊實作（「任何 target 含 Subscript 的 Assign」）會紅掉它，但那是**意外撿到的** ——
    #    同一條舊規則也會紅掉 `_cur["zzz"] = 1` 這種完全無關的本地 dict（實測 main 為 RED，
    #    是**偽陽性**）。把 receiver 收緊成真的 `*.session_state` 修掉了那個偽陽性，
    #    代價是連帶失去這一格；本函式在此把它**精準地**補回來，兩邊都要。
    recv_aliases: set[str] = set()

    def _dotted_is_receiver(node: ast.AST) -> bool:
        d = dotted(node)
        return bool(d) and d.rsplit(".", 1)[-1] == attr

    for node in ast.walk(fn_node):
        if isinstance(node, ast.Assign) and _dotted_is_receiver(node.value):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    recv_aliases.add(t.id)

    def _is_receiver(node: ast.AST) -> bool:
        if isinstance(node, ast.Name) and node.id in recv_aliases:
            return True
        return _dotted_is_receiver(node)

    # widget `key=` 那條要知道「streamlit 在這個函式裡叫什麼」。
    aliases = {root}
    for n in ast.walk(fn_node):
        d = dotted(n)
        if d.endswith(f".{attr}"):
            aliases.add(d.split(".", 1)[0])

    def _key_is_guarded(kw: ast.keyword) -> bool:
        """`key=` 指到的東西，是不是守衛在乎的那個 session key。"""
        if widget_key_names is None:
            return True                      # 舊行為：任何 key= 都算（見 docstring 警告）
        try:
            if ast.unparse(kw.value) in widget_key_names:
                return True
        except Exception:                    # 極少見的節點形狀，寧可認不得
            pass
        return (isinstance(kw.value, ast.Constant)
                and kw.value.value in widget_key_names)

    found: dict[int, ast.AST] = {}

    def _hit(node: ast.AST) -> None:
        found.setdefault(id(node), node)

    for node in ast.walk(fn_node):
        # 管道 1 / 2：各種賦值形態的 target
        targets: list[ast.AST] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            targets = [node.target]
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            targets = [node.target]
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            targets = [node.optional_vars]
        for t in targets:
            for sub in ast.walk(t):
                # `x = st.session_state.get(...)` 是**讀**，target 是 Name → 不會命中。
                if isinstance(sub, (ast.Subscript, ast.Attribute)) and _is_receiver(sub.value):
                    _hit(node)

        if isinstance(node, ast.Call):
            d = dotted(node.func)
            # 管道 3：`.update(...)` / `.setdefault(...)`
            if (isinstance(node.func, ast.Attribute)
                    and node.func.attr in ("update", "setdefault")
                    and _is_receiver(node.func.value)):
                _hit(node)
            # 管道 4：widget 帶 `key=` —— streamlit 代寫
            # `st.text_input(...)` 與 `st.sidebar.text_input(...)` 都算。
            if (d.count(".") >= 1 and d.split(".", 1)[0] in aliases
                    and not _is_receiver(node.func)
                    and any(kw.arg == "key" and _key_is_guarded(kw)
                            for kw in node.keywords)):
                _hit(node)

    return sorted(found.values(),
                  key=lambda n: (getattr(n, "lineno", 0), getattr(n, "col_offset", 0)))


# ── 3. 「哪個 if 才是送出閘門」 ──────────────────────────────────────────
def gate_ifs(fn_node: ast.AST, opener: str = "applied_form") -> list[ast.If]:
    """`fn_node` 內**真正的送出閘門** `if`，不是「隨便哪個 `if`」。

    判準（只有這一條，寫死在這裡讓它可以被讀出來）：

        該 `if` 的 **test 運算式裡出現的名字**，包含
        ``with <opener>(...) as <name>:`` 綁出來的那個 `<name>`。

    也就是說 ``if _gate:`` / ``if _gate and _ok:`` / ``if _gate.submitted:`` 都算閘門，
    而 ``if not _funds: return`` 這種**與閘門無關的 `if` 不算** ——
    這正是原本三頁那份「在**任何** `ast.If` 底下就算被 gate 住」要修掉的洞：
    只要有人往 form 函式加第二個 `if`，藏在它底下的裸寫入就會被算成「已被閘門包住」。
    （**實測**：本輪之前 ②③④ 的 form 函式各自都只有 `_gate` 這一個 `if`，
    所以那個洞**尚未發作** —— 修的是「下一個人加第二個 `if` 就會中」。）

    ## 擋不掉什麼（照實列）

    * ⭐ **判準是「test 裡出現 gate 名字就一律認它是閘門」，不是「test 的語意等於 gate」。**
      所以**任何**把 gate 名字包進一個更大運算式的寫法都分不出來，
      **不是只有 `if not _gate:` 一個例子**（2026-09-05 稽核實測，逐一跑過）::

          if _gate or True:      if _gate is False:     if _gate == False:
          if not not _gate:      if _gate and True:     if _gate is not None:

      **唯一的例外是純粹的 `not` 鏈**（``not _gate`` / ``not not _gate``）——
      :func:`gate_guarded_ids` 會數 `not` 的層數並據以決定該收 `body` 還是 `orelse`，
      那一種**是真的判對了**，不在本清單內。其餘一律「認得出是閘門、認不出語意」，
      要靠 AppTest 行為測試（③④ 各有兩條）去驗。
    * **閘門一旦轉手給中間變數就認不到**：``_ok = _gate`` 之後 ``if _ok:`` ——
      `_ok` 不是 `with ... as` 綁出來的名字 ⇒ 不算閘門 ⇒ 底下的寫入判為裸寫入。
      **這個方向是 fail-closed（誤紅、不是漏放）**，且斷言訊息已就地指名
      「請同步 `gate_ifs()` 的判準」，故**登記不修**。
    * ``if True:`` 之類與閘門無關、卻把寫入包起來的 `if` —— 本函式**不**認它是閘門，
      所以底下的寫入會被判成裸寫入（**這個方向是 fail-closed，安全**）。
    * `<opener>` 換名字、或 gate 不是用 `with ... as` 取得（例如 `g = form(...)`）→ 認不到，
      回空 list ⇒ 所有寫入都算裸寫入（**同樣 fail-closed**）。
    """
    gate_names: set[str] = set()
    for node in ast.walk(fn_node):
        if isinstance(node, ast.withitem) and node.optional_vars is not None:
            call = node.context_expr
            if isinstance(call, ast.Call) and dotted(call.func).rsplit(".", 1)[-1] == opener:
                for sub in ast.walk(node.optional_vars):
                    if isinstance(sub, ast.Name):
                        gate_names.add(sub.id)
    if not gate_names:
        return []
    out: list[ast.If] = []
    for node in ast.walk(fn_node):
        if isinstance(node, ast.If) and any(
            isinstance(s, ast.Name) and s.id in gate_names for s in ast.walk(node.test)
        ):
            out.append(node)
    return out


def gate_guarded_ids(fn_node: ast.AST, opener: str = "applied_form") -> set[int]:
    """真正**被閘門擋住**的節點 id —— 只算閘門 `if` 的 **body（真分支）**。

    ⚠️ **為什麼不是 `ast.walk(gate_if)`**（2026-09-05 品管組實測補的洞）：
    `ast.If` 節點底下**同時掛著 `body` 與 `orelse`**，整棵 walk 下去會把
    ``else:`` / ``elif`` 分支一起算成「被閘門包住」—— 而那兩個分支**正好是
    閘門為假時才跑的路徑**，也就是「沒按送出鈕卻寫進 session」的那個 bug 本身。

    **實測（三頁 × `else:`／`elif` × 三種測試順序，共 18 格）**：
    改用本函式之前，六格全部 **GREEN（守衛看不見）**；改用之後六格全部 **RED**。
    ⚠️ 這個洞**不是本輪重寫造成的** —— `origin/main` 的舊寫法
    （「任何 `ast.If` 底下的 `ast.Assign` 都算 guarded」）同樣看不見它，
    實測 before/after 兩邊皆綠。本輪是**沒有把它一起修掉，也沒有寫下來**，故補上。

    ⭐ **2026-09-05 第二輪：`not` 鏈現在判得對了。**
    ``if not _gate: pass / else: <寫入>`` 與 ``if _gate: <寫入>`` **語意完全等價**，
    但前者原本三頁皆誤紅（稽核 FP-2），而斷言訊息還說「每次 rerun 都會覆寫已套用值」——
    **那句話對那段程式碼是假的**。本函式改為**數 `not` 的層數**來決定收 `body` 還是
    `orelse`，順帶也讓 ``if not _gate: <寫入>``（真正的違規）**從綠變紅**。

    ⚠️ **只處理純粹的 `not` 鏈。** 剝完 `not` 之後若不是 gate 名字本身
    （``_gate and _ok`` / ``_gate or True`` / ``_gate is False`` …）**一律退回 `body`** ——
    那些仍然分不出語意，見 :func:`gate_ifs` 的「擋不掉什麼」。
    """
    gate_names: set[str] = set()
    for node in ast.walk(fn_node):
        if isinstance(node, ast.withitem) and node.optional_vars is not None:
            call = node.context_expr
            if isinstance(call, ast.Call) and dotted(call.func).rsplit(".", 1)[-1] == opener:
                for sub in ast.walk(node.optional_vars):
                    if isinstance(sub, ast.Name):
                        gate_names.add(sub.id)

    def _branch(gate: ast.If) -> list[ast.stmt]:
        """這個 `if` 的哪一半才是「閘門為真」那一半。

        數 `not` 的層數：``if _gate:`` → body；``if not _gate:`` → **orelse**；
        ``if not not _gate:`` → body。剝完之後**必須剛好是 gate 名字本身**，
        否則（``_gate and _ok`` / ``_gate or True`` / ``_gate is False`` …）
        一律退回 `body` —— 認不出語意時**不要自作聰明反轉**。
        """
        node, negations = gate.test, 0
        while isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            node, negations = node.operand, negations + 1
        if isinstance(node, ast.Name) and node.id in gate_names and negations % 2 == 1:
            return gate.orelse
        return gate.body

    ids: set[int] = set()
    for gate in gate_ifs(fn_node, opener):
        for stmt in _branch(gate):
            for node in ast.walk(stmt):
                ids.add(id(node))
    return ids
