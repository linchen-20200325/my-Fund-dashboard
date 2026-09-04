"""三態顏色「來源可追溯」守衛 —— 補上舊守衛 fail-open 的那一半。

客戶四大鐵律第 3 條「三態顏色分離」：
  未載入／沒點過 ＝ 灰色說明 ／ 系統真出錯 ＝ 紅色警示 ／ 業務上的壞消息 ＝ 業務色。

為什麼需要**這一個**檔案（既有守衛擋不到什麼）
------------------------------------------------
`tests/test_render_state_color_separation.py` 守的是**畫的是哪一種 widget**
（`st.caption` vs `st.error` vs `st.markdown`），**完全沒有一條規則看顏色的值**。
它的抓法是「在 except handler 裡找 `st.*` 呼叫」，於是有一個結構性的破口：

    # 只要把渲染包成自己的 helper，整條規則就看不見它
    def _render_failure_card(what, exc):                      # ← 顏色錯在這裡
        st.markdown(f"<div style='color:{業務色}'>{what}: {exc}</div>", ...)

    try:  ...
    except Exception as e:
        _render_failure_card("NAV 抓取失敗", e)                # ← handler 裡只有一個普通呼叫

`_rendering_calls()` 只收 `st.<render attr>` 與 `_FUNC_RENDERERS` 名單內的函式名；
`_render_failure_card` 兩者皆非 → **這個 handler 被判定為「沒有把例外印給使用者看」**，
而 helper 本體不在任何 except handler 裡 → 也沒有規則會去看它。

⚠️ **這不是推測，是實測（2026-08-31，本 PR 就地重現）**：
把上面那段存成 `ui/helpers/fund_grp_health/_failopen_probe.py`（該目錄是 glob 掃描範圍，
新檔會自動進 `HEALTH_SCOPE`）後跑舊守衛 ——
`428 passed` → `433 passed`：**多出來的 5 條 case 全部掃過這個檔案，而且全綠**：
  `test_caught_exception_is_reported_as_a_system_failure[_failopen_probe.py]`
  `test_b1_missing_credential_branch_is_never_alarm_coloured[_failopen_probe.py]`
  `test_b2_not_configured_wording_is_never_alarm_coloured[_failopen_probe.py]`
  `test_m2_same_grey_line_is_not_printed_twice_in_one_function[_failopen_probe.py]`
  `test_n3_degraded_is_not_a_one_way_escape_hatch[_failopen_probe.py]`
**規則有在跑、檔案有被掃、違規就在裡面，五條規則一條都沒響。** 那就是 fail-open。

本檔守什麼（形態偵測，不是白名單）
----------------------------------
「顏色來源可追溯到三個語意角色之一」在本 repo 的具體形狀是 —— 一個三態渲染路徑的顏色，
**只能**來自下列兩種來源，兩種都不是就是「追不到」：
  1. **角色常數**：`shared.colors.BUSINESS_ALERT_ON_*`（業務色是三態裡唯一由我們自己指定
     hex 的角色）；
  2. **角色入口的 widget 內建色**：`st.error()` / `system_error()`（系統紅）、
     `st.caption()` / `not_ready()`（未載入灰）—— 顏色由 Streamlit 給，我們不指定 hex。
→ 因此「在三態路徑上寫死一個 hex」＝ 追不到 ＝ 紅燈。

⛔ **刻意不做白名單。** 本 session 已兩次實證白名單的失效模式（「白名單不是窮舉」抓不到
名單外的；「歷史值清單」抓不到從沒進過清單的錯名字）。本檔三條規則都只看**形狀**：
誰painted、painted 什麼來源、那個函式是不是在報系統失敗。

⚠️ **已知邊界（照實寫，不要讀成「繞不過去」）**
- R3 的判準 (b) 是**弱證據**，只算「真的把例外帶進引數的那一個 render 呼叫」。
  所以 `def _card(what, exc): st.markdown(業務色 + what); st.code(str(exc))`
  ——標題與例外拆成兩個呼叫、標題那個不 carry 例外——**抓不到**。
  這是為了不誤傷大函式（實測：`ui/sidebar.py::render_sidebar()` body 某處有 traceback，
  第一版連一張跟錯誤無關的漸層歡迎卡都判違規）而**刻意**留的鬆度。
  判準 (a)(c)（例外從**參數**進來）沒有這個鬆度：那種函式畫的每個 render 都算。
- R3 的判準 (c)（「被 except handler 以帶例外的引數呼叫」）只做**同檔**呼叫圖。
  把 wrapper 搬到另一個檔、且該 wrapper 的簽章不帶 exception-ish 參數、body 也不格式化
  例外，(a)(b)(c) 會同時失手。要補需要跨檔呼叫圖，不在本批範圍。
  （(a)(b) 是**跨檔有效**的：它們只看 wrapper 自己的簽章與 body。）
- ⚠️ **X1｜同檔兩層 wrapper —— 上一行沒有涵蓋它，這是獨立的一條**（2026-08-31 補）。
  上一行只揭露「wrapper **搬到別的檔**會失手」，讀起來像是「**同一個檔**內一定抓得到」。
  **不是。** 實測：

      def _inner(what, detail):          # ← 顏色錯在這裡，但它從未被 seed
          st.markdown(f"<div style='color:{業務色}'>{what}{detail}</div>", ...)
      def _outer(what, exc):             # ← 判準 (c) 只標記到這一層
          _inner(what, str(exc))
      try: ...
      except Exception as e:
          _outer('NAV 抓取失敗', e)

  **根因**：`_system_failure_renderers()` 的判準 (c) 只從 **except handler 的直接 callee**
  取 seed，**taint 不傳第二跳**；而 `_outer` 自己沒有任何 render 呼叫，於是
  「被標記的函式不畫圖、畫圖的函式沒被標記」，兩邊都不報。
  ✅ **2026-09-04 已修**（**有意識的狀態變更，不是漏刪**）：判準 (c) 改為
  **迭代到不動點** —— 只要某函式收到被污染的引數，它的對應參數就被污染，
  再往下傳給它呼叫的函式，反覆直到污染集合不再變大，**同檔內任意層數都追得到**。
  ~~舊表述「屬範圍擴大，本批不做」~~ 在它寫下的當天成立（那一批的授權範圍確實不含它）；
  被推翻的是它的**前提**，不是當時的判斷。
  哨兵：`test_r3_c_taint_reaches_a_fixed_point_not_just_one_hop`（**三層** wrapper，
  拿掉固定點迴圈會轉紅，已突變驗證）。
  ⛔ **仍然只做同檔（intra-file）—— 跨檔未涵蓋，見上一條，那條缺口原封不動。**
- ⚠️ **X3｜module-level 間接呼叫（如 `functools.partial`）**（2026-08-31 補）。
  `_emit = functools.partial(_show)` 之後 `except ...: _emit(str(e))` ——
  handler 的 callee 是 `_emit`（module-level **`Name`**，不是 `FunctionDef`），
  `byname.get("_emit")` 落空 → 判準 (c) 拿不到 seed。
  ⚠️ **但它只在 (a)(b) 同時避開時才成立**：若那個 painter 的參數叫 `exc`／標註 `Exception`，
  **判準 (a) 照樣抓到**（實測：本批第一版探針就是因為參數名寫成 `exc` 而被抓到，
  重做成 `detail` 才隔離出這條繞道）。**寫探針時若不先關掉 (a)，會誤以為 (c) 沒破。**
- ✅ **X2｜`*args` 收參數 —— 曾經是繞道，2026-08-31 已修，留紀錄不留破口**：
  `def _paint(*bits)` 之下，`_paint("NAV 失敗", e)` 的 `e`（index 1）會因
  `i >= len(params)` 被**靜默跳過**，taint 遺失、整個函式不被判為系統失敗渲染。
  這是**規則自身的邏輯 bug**（不是範圍取捨）—— 位置引數吃不完時是被 vararg 收走的。
  已於 `_system_failure_renderers()` 就地修正並附回歸測試
  `test_r3_a_varargs_wrapper_is_not_a_blind_spot`（拿掉修正該測試會轉紅，已突變驗證）。
- ⚠️ **X1 的定性：未來回歸風險，不是現存漏洞。**
  2026-08-31 實測掃過全 `ui/**`（**112 檔 / 540 函式**，量測日；本數字在 #744
  七→五併頁合併後重測過一次，函式數由 534 → 540，**結論「0」未變**）：
  「被判為系統失敗渲染的函式 → 呼叫另一個同檔、自己會 render 的函式」**現存實例 0**。
  → **今天沒有任何一處在利用 X1**；揭露它是為了讓下一個人知道**這條路是通的**，
  不是宣稱現在漏了什麼。
  ⛔ **這個掃描只量了 X1 的形狀，不要把它讀成「三條都沒有現存實例」** ——
  **X3（module-level 間接呼叫）本組沒有做對應的現存實例掃描**，
  「`ui/**` 今天有沒有人用 `functools.partial` 之類的間接呼叫繞過 (c)」**本組未查證、也不宣稱**。
  （X2 已修，不需要這個問題。）
  ⚠️ 「X1 = 0 實例」是**單組掃描**的結論，未經第二組驗證。
- 本檔只掃 `ui/**` 與 `app.py`。`services/**` 不畫 UI，不在範圍。
- ⚠️ **R1 對比規則量的是「亮度」，不是「色相」——它擋得住什麼、擋不住什麼**（2026-08-31 補）：
  **擋得住**「改回系統紅」（字串規則）與「**差一個位元**」（實測 `#f44337` vs `#f44336`：
  字串規則放行，對比規則 **1.0003:1** 當場轉紅）。
  **擋不住**「換一個**亮度不同、但仍然很紅**的紅」—— 實測 `#c62828`（Material Red 800）
  對 `MATERIAL_RED` 是 **1.5267:1**、`#8b0000`（darkred）是 **2.7185:1**，
  兩者都**通過** 1.5 門檻，但沒有人會說它們不是「系統紅家族」。
  ⚠️ 且**現行餘裕很薄**：`BUSINESS_ALERT_ON_DARK` vs `MATERIAL_RED` 實測 **1.6986:1**，
  距離門檻只有 **0.199**。**動任一個值之前先重算這個數字。**
- ✅ **曾經的殘餘破口：用 `MATERIAL_RED` 手繪一個系統錯誤框 —— 2026-09-04 已由 R4-a 關掉。**
  下段是它當初的紀錄，**保留不刪**（它說明了為什麼 R3 三條腿還不夠）。

      from shared.colors import MATERIAL_RED
      def _fail_card(what, exc):
          st.markdown(f"<div style='border:2px solid {MATERIAL_RED};"
                      f"color:{MATERIAL_RED}'>{what}: {exc}</div>", ...)

  R2 只看**角色色**的 hex（`MATERIAL_RED` 不是角色色）；R3 的兩條分別看「業務色」與
  「**寫死的 hex**」，而這裡用的是**具名 SSOT 常數**、不是 inline hex → 三條都不響。
  **定性要看清楚**：它畫的是**系統紅**去報**系統錯誤**，**語意方向沒有錯** ——
  屬「**形狀違規**」（沒走 `system_error()`，少了 widget 一致性），
  **不是**本檔要抓的「**顏色違規**」（拿業務色報系統錯）。
  ✅ **2026-09-04 更新：已由 `R4-a` 關掉，且代價是 0** —— 見本檔 R4 節。
  ~~舊表述「擴大守衛範圍會掃到 34 個無關檔案，故刻意留白」~~ 的**顧慮仍然成立**
  （那正是 R4-**b** 射程只到 `HEALTH_SCOPE` 的理由），
  **但它把兩件事混成了一件**：R4-a 只在「R3 已經認定是系統失敗渲染」的路徑上生效，
  分母僅 **13 個 render 呼叫**、既有命中 **0 處** —— **零白名單、零豁免、不掃任何無關檔案。**
  「34 檔」那個數字算的是 `MATERIAL_RED` 的**所有**出現處，不是失敗路徑上的出現處；
  **拿一個較寬口徑的計數去否決一條較窄的規則，是本次更正的那個錯。**
- 顏色值若經由變數多次轉手（`c = 業務色; d = c; ...`）本檔做的是**同 scope 傳遞閉包**，
  跨函式傳參不追。
- ⚠️ 本檔規則由**單組**（前端 UI 組）設計與實作，**未經第二組獨立驗證**（`CLAUDE.md §-2` 規則 6）。
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

# ⚠️ **2026-09-04：`ROOT` / `UI_SOURCES` 改為從 hub 匯入，不再自己重寫一次 glob。**
# 在此之前本檔自己寫了 `sorted((ROOT / "ui").rglob("*.py")) + [ROOT / "app.py"]` ——
# 與 `test_render_state_color_separation.py` 那一行**逐字相同**，是同一個事實的第二份
# 真相源（`CLAUDE.md §2.1` SSOT）。兩份各自漂移的後果不是抽象風險：一邊加了掃描範圍
# 而另一邊沒加，會讓「兩個守衛都綠」看起來像雙重保險，實際上其中一個根本沒掃到那些檔。
# hub 同時是 5 個其他測試檔的共用來源，本檔沿用它即可。
# ⛔ 只**取用**既有符號，**不改**它們的名稱／簽名／回傳形狀（hub 是共用 API）。
from test_render_state_color_separation import (  # noqa: E402
    HEALTH_SCOPE,
    ROOT,
    UI_SOURCES,
)

# ── 角色常數名（值住在 shared/colors.py，本檔只認名字，避免第二個真相源）──────────
BUSINESS_TOKEN_NAMES = frozenset({"BUSINESS_ALERT_ON_LIGHT", "BUSINESS_ALERT_ON_DARK"})
# 「泛用失敗紅」：本 repo 拿來畫壞數字／系統紅的紅色家族。業務色不得是其中任何一個，
# 否則三態又退回「只靠形狀分辨」。
GENERIC_FAILURE_REDS = ("MATERIAL_RED", "TRAFFIC_RED")

_HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")

_ST_RENDER_ATTRS = frozenset({
    "caption", "info", "warning", "error", "success", "markdown", "write", "text",
    "code", "toast", "exception", "metric", "dataframe", "table", "json", "latex",
    "subheader", "title", "header", "badge",
})
_ST_CONTAINER_FACTORIES = frozenset({
    "columns", "container", "expander", "tabs", "sidebar", "empty", "form", "popover",
})
# 例外內容的間接來源（不綁 `as e` 也拿得到例外）
_EXC_DERIVED = frozenset({"format_exc", "exc_info", "print_exc", "format_exception"})
_EXC_PARAM_NAMES = frozenset({"e", "err", "exc", "error", "exception", "_e", "_err", "_exc"})
_EXC_ANNOTATIONS = frozenset({"Exception", "BaseException", "BaseExceptionGroup"})


def _rel(path: pathlib.Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _receiver_root(node: ast.AST) -> str | None:
    """把 `st` / `st.sidebar` / `_cols[2]` / `col1` 剝到最左邊的名字。"""
    while True:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            node = node.value
        elif isinstance(node, ast.Subscript):
            node = node.value
        elif isinstance(node, ast.Call):
            node = node.func
        else:
            return None


def _st_aliases(tree: ast.AST) -> frozenset[str]:
    """`import streamlit as _st_c` 這類模組別名（別名不敏感，不寫死 `st`）。"""
    out = {"st"}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name == "streamlit":
                    out.add(a.asname or "streamlit")
    return frozenset(out)


def _container_names(tree: ast.AST, aliases: frozenset[str]) -> frozenset[str]:
    """由 `st.columns()/container()/expander()` 綁出來的名字 —— 它們畫的就是 st 元件。"""
    out: set[str] = set()
    for n in ast.walk(tree):
        if not isinstance(n, (ast.Assign, ast.AnnAssign, ast.withitem)):
            continue
        value = n.value if not isinstance(n, ast.withitem) else n.context_expr
        tgts = ([n.target] if isinstance(n, (ast.AnnAssign,))
                else n.targets if isinstance(n, ast.Assign)
                else ([n.optional_vars] if n.optional_vars else []))
        if value is None or not tgts:
            continue
        if not (isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute)
                and value.func.attr in _ST_CONTAINER_FACTORIES
                and _receiver_root(value.func.value) in aliases):
            continue
        for t in tgts:
            if t is None:
                continue
            for sub in ast.walk(t):
                if isinstance(sub, ast.Name):
                    out.add(sub.id)
    return frozenset(out)


def _is_render_call(call: ast.Call, aliases: frozenset[str],
                    containers: frozenset[str]) -> bool:
    if not isinstance(call.func, ast.Attribute):
        return False
    if call.func.attr not in _ST_RENDER_ATTRS:
        return False
    root = _receiver_root(call.func.value)
    return root in aliases or root in containers


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _business_names(tree: ast.AST) -> frozenset[str]:
    """本檔內綁到業務色常數的所有名字（含 `as` 別名與同 scope 轉手）。"""
    names: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            for a in n.names:
                if a.name in BUSINESS_TOKEN_NAMES:
                    names.add(a.asname or a.name)
    # 傳遞閉包：`_c = BUSINESS_ALERT_ON_DARK` → `_c` 也算業務色
    changed = True
    while changed:
        changed = False
        for n in ast.walk(tree):
            if not isinstance(n, ast.Assign) or n.value is None:
                continue
            refs = {x.id for x in ast.walk(n.value) if isinstance(x, ast.Name)}
            refs |= {x.attr for x in ast.walk(n.value) if isinstance(x, ast.Attribute)}
            if not (refs & (names | BUSINESS_TOKEN_NAMES)):
                continue
            for t in n.targets:
                for sub in ast.walk(t):
                    if isinstance(sub, ast.Name) and sub.id not in names:
                        names.add(sub.id)
                        changed = True
    return frozenset(names)


def _mentions_business(node: ast.AST, business: frozenset[str]) -> bool:
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and n.id in (business | BUSINESS_TOKEN_NAMES):
            return True
        if isinstance(n, ast.Attribute) and n.attr in BUSINESS_TOKEN_NAMES:
            return True
    return False


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """模組／類別／函式的 docstring 節點 id。

    ⚠️ 2026-08-31 實測修正：第一版把 docstring 也當成「寫死顏色」，於是
    `ui/helpers/render_state.py` **因為說明文字裡引用了 `#f294b6` 而被判違規**。
    在文件裡講一個顏色叫什麼，跟把它 inline 畫出來是兩件事。

    ⚠️ **措辭更正（2026-08-31，有意識的更正，不是漏刪；決策者：本實作組，稽核指出）**：
    本段舊表述寫 ~~「docstring 不會被求值成任何輸出，排除它**不開後門**」~~ ——
    **那句話字面上是假的，已改為「不開**實務上的**後門」。**
    **反例（實測，新守衛 347 passed 全綠）**：

        def _paint():
            '''<div style='color:#f294b6'>業務警訊</div>'''
            st.markdown(_paint.__doc__, unsafe_allow_html=True)

    `__doc__` **確實可以被求值成輸出** —— 舊表述的前半句（「不會被求值」）就是錯的，
    後半句（「不開後門」）建立在它上面，一起垮。
    **兩邊理由並陳**：舊表述**在它要解決的問題上仍然成立** ——
    排除 docstring 是為了不把「說明文字提到一個顏色」誤判成違規，那個判斷沒有錯，
    本函式**照舊排除 docstring**，一行未改；**被權衡掉的只有那句全稱斷言**。
    **新表述勝出的理由**：實務嚴重性可忽略（沒有人把 `__doc__` 當 HTML 餵給
    `unsafe_allow_html`），**但「可忽略」跟「不存在」是兩件事** ——
    寫成「不開後門」會讓下一個人以為這裡已經封死，
    而本檔整份 docstring 的用途正是告訴後人**哪裡還是通的**（見模組 docstring 已知邊界）。
    **能被一個 6 行反例推翻的句子，就不該用全稱語氣寫進守衛。**
    """
    out = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef,
                                 ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", None)
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            out.add(id(body[0].value))
    return out


def _hexes_in(node: ast.AST) -> list[str]:
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            out.extend(_HEX_RE.findall(n.value))
    return out


# ══════════════════════════════════════════════════════════════════
# R0 — 角色常數必須存在（GC 護欄；2026-08-31 總管裁決後補）
# ══════════════════════════════════════════════════════════════════
def _role_values() -> dict[str, str]:
    """角色常數的**現值**；缺席者不列入（讓 R2 不會整片 AttributeError 級聯）。"""
    import shared.colors as C
    return {t: getattr(C, t) for t in BUSINESS_TOKEN_NAMES if hasattr(C, t)}


def test_r0_both_role_tokens_exist_even_the_one_with_no_caller():
    """**`BUSINESS_ALERT_ON_LIGHT` 今天沒有 production 消費者，但不准刪。**

    總管 2026-08-31 拍板保留。本條是它的**機器護欄** —— 沒有這條，
    未來一輪 GC（v3 §01-2「用不到即清理」）會把它當孤兒清掉，
    而 SSOT 會變成一個「只有深色底那一半」的半套：下一個人拿 `ON_DARK`
    去畫淺色底時，沒有任何東西會攔他。

    ⚠️ 這條刻意**單獨存在**、且訊息自帶理由。
    2026-08-31 實測：把常數刪掉會讓本檔 **115 條**測試轉紅，其中 112 條是
    R2 對每個 UI 檔各報一次同樣的 `AttributeError` —— **那種級聯只會把真正的
    原因埋掉**。有了本條，刪除的第一個訊號是一句講得清楚的話。
    """
    import shared.colors as C
    missing = sorted(t for t in BUSINESS_TOKEN_NAMES if not hasattr(C, t))
    assert not missing, (
        f"三態角色常數不見了：{missing}\n"
        "若這是 Garbage Collection 把「沒有 caller 的常數」當孤兒刪掉 —— **請還原**。\n"
        "`BUSINESS_ALERT_ON_LIGHT` 確實沒有 production 消費者（App 釘死深色底），\n"
        "但它是 `ON_DARK` 的**配對值**：兩者在對方的底色上都只有 2.17:1，\n"
        "留著配對值 + 對比測試，是防止有人把 ON_DARK 畫到淺底上的手段。\n"
        "刪它的前提是「本 repo 已確定不需要主題感知」—— 那個前提目前不成立。\n"
        "理由全文見 shared/colors.py 該常數上方註解。"
    )


# ══════════════════════════════════════════════════════════════════
# R1 — 三個角色必須真的分得開（M1 的守衛）
# ══════════════════════════════════════════════════════════════════
def _luminance(hex_str: str) -> float:
    h = hex_str.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def test_r1_business_colour_is_not_a_generic_failure_red():
    """業務色不得等於任何一個泛用失敗紅 —— 相等就退回「只靠形狀分辨」。

    這條擋的是本批最容易被回退的一步：把 `BUSINESS_ALERT_ON_DARK` 改回 `MATERIAL_RED`。
    """
    import shared.colors as C
    generic = {name: getattr(C, name) for name in GENERIC_FAILURE_REDS}
    for token in sorted(BUSINESS_TOKEN_NAMES):
        value = getattr(C, token)
        clashes = sorted(n for n, v in generic.items() if v.lower() == value.lower())
        assert not clashes, (
            f"{token} = {value} 與泛用失敗紅 {clashes} 同值 —— "
            "業務警訊與系統紅又變成同一個顏色，三態分離失效"
            "（差別會退回只剩形狀，那正是 2026-08-31 這批要拆掉的東西）。"
        )


def test_r1_business_colour_is_visibly_apart_from_the_system_red():
    """不只是「不同值」，還要**看起來不同**。

    `#f44335` 與 `#f44336` 是不同的字串、同一個顏色 —— 只比字串等同，
    等於留一條「改一個位元就過關」的路。這裡用 WCAG 對比公式量。

    ⚠️ **這條擋得住什麼、擋不住什麼（2026-08-31 實測，就地寫明）**
    **擋得住**「差一個位元」：`#f44337` vs `MATERIAL_RED(#f44336)` ——
    上一條的字串規則**放行**，本條算出 **1.0003:1** 當場轉紅。**兩條是縱深，不是重複。**

    ⛔ **擋不住「換一個亮度不同、但仍然很紅的紅」** —— 因為 **WCAG 對比量的是「相對亮度」，
    不是「色相」**。實測：`#c62828`（**Material Red 800**，貨真價實的系統紅家族）
    對 `MATERIAL_RED` 是 **1.5267:1**、`#8b0000`（darkred）是 **2.7185:1**，
    **兩者都通過 1.5 門檻**。把業務色改成它們，本條不會響。
    → **本條防的是「原地微調」，不是「換一個紅」**；後者目前**沒有機器護欄**，
    靠的是 `test_r1_business_alert_actually_paints_with_the_role_token` 釘住
    「必須引用角色常數」＋ code review。**不要以為這條顧到了色相。**

    ⚠️ **現行餘裕很薄，動值之前先重算**：實測四組之中最緊的是
    `BUSINESS_ALERT_ON_DARK`(#f294b6) vs `MATERIAL_RED`(#f44336) ＝ **1.6986:1**，
    距離 1.5 門檻只有 **0.199**。（其餘三組：ON_DARK vs TRAFFIC_RED 1.7359、
    ON_LIGHT vs MATERIAL_RED 2.2974、ON_LIGHT vs TRAFFIC_RED 2.2482。）
    """
    import shared.colors as C
    for token in sorted(BUSINESS_TOKEN_NAMES):
        for gen in GENERIC_FAILURE_REDS:
            ratio = _contrast(getattr(C, token), getattr(C, gen))
            assert ratio >= 1.5, (
                f"{token}({getattr(C, token)}) 與 {gen}({getattr(C, gen)}) 對比僅 "
                f"{ratio:.2f}:1 —— 值不同但肉眼是同一個紅，等於沒有分離。"
            )


def test_r1_live_business_colour_is_readable_on_the_card_it_is_painted_on():
    """實際用在卡片上的那一個，必須在卡片底色上讀得到。

    ⚠️ 這條是「用錯配對值」的守衛，不是無病呻吟：實測
    `BUSINESS_ALERT_ON_LIGHT`(#96124a) 畫在業務卡底 `BG_DARK_RED_1`(#2a0a0a) 上
    只有 **2.17:1**（WCAG AA 需 4.5:1）—— 字幾乎看不見。
    兩個值是**依底色擇一的一組**，不是深淺兩種心情。
    """
    import shared.colors as C
    ratio = _contrast(C.BUSINESS_ALERT_ON_DARK, C.BG_DARK_RED_1)
    assert ratio >= 4.5, (
        f"業務警訊卡前景 {C.BUSINESS_ALERT_ON_DARK} 在卡底 {C.BG_DARK_RED_1} 上只有 "
        f"{ratio:.2f}:1，低於 WCAG AA 4.5:1 —— 是不是把 ON_LIGHT/ON_DARK 用反了？"
    )


def test_r1_the_light_surface_pair_is_kept_usable_for_a_light_surface():
    """配對值本身要是「淺底可讀」的，否則它進 SSOT 沒有意義。"""
    import shared.colors as C
    ratio = _contrast(C.BUSINESS_ALERT_ON_LIGHT, "#ffffff")
    assert ratio >= 4.5, (
        f"BUSINESS_ALERT_ON_LIGHT({C.BUSINESS_ALERT_ON_LIGHT}) 在白底上只有 "
        f"{ratio:.2f}:1 —— 它存在的理由就是給淺色底用。"
    )


def test_r1_business_alert_actually_paints_with_the_role_token():
    """反向護欄：上面幾條可以靠「business_alert 不再用這個 token」通過。

    用 AST 檢查 `business_alert` 的 body 真的引用了角色常數，
    而不是把 token 留在檔案裡當裝飾、實際畫別的顏色。
    """
    src = (ROOT / "ui" / "helpers" / "render_state.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "business_alert"), None)
    assert fn is not None, "business_alert() 不見了 —— 業務警訊是分析成果，不是可選項（§1）。"
    business = _business_names(tree)
    assert _mentions_business(fn, business), (
        "business_alert() 的 body 沒有引用 BUSINESS_ALERT_ON_* —— "
        "角色常數必須真的被畫出來，不是擺著好看。"
    )
    # 且不得同時把泛用失敗紅畫進這張卡（那等於顏色又合流）。
    used = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
    used |= {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)}
    bad = sorted(used & set(GENERIC_FAILURE_REDS))
    assert not bad, (
        f"business_alert() body 裡出現泛用失敗紅 {bad} —— "
        "業務卡不得再引用系統紅家族。"
    )


def test_r1_business_alert_rail_is_thicker_than_a_default_rule():
    """左軌粗細是第二個辨識點（系統紅框沒有左軌），且必須具名不 inline（§3.3）。"""
    from ui.helpers.render_state import BUSINESS_ALERT_RAIL_PX
    assert BUSINESS_ALERT_RAIL_PX >= 6, (
        f"業務卡左軌 {BUSINESS_ALERT_RAIL_PX}px —— 客戶拍板的線框是 6px；"
        "顏色與形狀要同向，任一個看丟都還有另一個。"
    )


# ══════════════════════════════════════════════════════════════════
# R2 — 角色色只准從 SSOT 來（M3 的守衛）
#
# 「追不到就紅」的第一半：角色色的 hex **不准**出現在 UI 檔的字面值裡。
#
# ⚠️ **量測數字更正（2026-08-31，有意識的更正，不是漏刪；決策者：本實作組，稽核指出）**
#    舊表述寫 ~~「共 **216** 個 hex 字面值、散在 **29** 檔，其中命中角色色的 **0 個**」~~ ——
#    **那組數字用任何一種算法都不重現，而且沒有寫明是用哪種算法數的。**
#    **兩邊理由並陳**：舊表述想講的事**仍然成立**（角色色沒有被 inline，所以不需要白名單）；
#    **被權衡掉的是它的呈現方式** —— 一個沒有附算法的計數，後人無從複驗，
#    也無從發現它何時開始說謊；而「命中 0 個」在**未排除 docstring** 時**其實是 2 個**。
#
# **現行量測（本 PR 就地實跑；算法寫明，數字跟著算法走）** —— 三種算法各數一次：
#   ① 原文 grep（含註解＋docstring）        ：**227** 個 / **30** 檔；命中角色色 **2** 個
#   ② AST 字串常數（含 docstring，排除註解）：**204** 個 / **27** 檔；命中角色色 **2** 個
#   ③ AST 字串常數，**排除 docstring**      ：**195** 個 / **23** 檔；命中角色色 **0** 個
#      ↑ **③ 就是本條實際採用的口徑**（見 `_docstring_nodes()`），故本條**零白名單**成立。
#
# ⚠️ **「命中角色色 0 個」必須帶限定語：那是「排除 docstring 後」。**
#    **未排除時是 2 個**，都在 `ui/helpers/render_state.py` 的**模組 docstring** 內
#    （該 docstring 為第 1~93 行；兩處分別在第 32 行提到 `#f294b6`、第 36 行提到 `#96124a`，
#    都是**說明文字在講這個顏色叫什麼**，不是把它畫出來）。
#    **不寫這個限定語，「0 個」看起來會像是「repo 裡根本沒出現過角色色的 hex」——那是假的。**
#
# ⚠️ **本行是量測日快照，會漂移；複驗請重跑，不要引用本行** —— ①② 的數字**已被實測證明會隨
#    main 前進而變**，同一天內就變了兩次：
#      · 合併 `origin/main`(#741，動 `app.py`) 前：① 218/30、② 203/27
#      · 合併 #741 後：                          ① 220/30、② 204/27
#      · 合併 #744（七→五併頁，動 20+ 個 `ui/` 檔）後：① **227**/30、② 204/27
#    **而 ③ 在這三次之中一次都沒變（195/23，命中 0）** —— 這正是「③ 才是本條判準」的實證：
#    判準口徑穩定，另外兩個算法只是拿來對照的。**複驗請重跑三種算法，不要引用本表任何一格。**
#
# ⚠️ 本條只管**三態角色色**，不是「UI 不准出現任何 hex」：其餘那些多半是圖表／品牌／
#    badge 用色，與三態無關，把它們一起收進來屬 §8.4 step 4 明禁的自作主張擴大範圍。
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("path", UI_SOURCES, ids=_rel)
def test_r2_role_colour_hex_is_never_inlined_in_ui(path: pathlib.Path):
    """角色色一律 `from shared.colors import ...`，不得寫死 hex。"""
    # 缺席常數由 R0 專責報錯；此處容錯，避免整片 AttributeError 級聯把原因埋掉。
    role_values = {v.lower(): t for t, v in _role_values().items()}
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = _docstring_nodes(tree)
    bad = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        if id(node) in docstrings:
            continue          # 說明文字提到某個顏色 ≠ 把它 inline 畫出來
        for hx in _HEX_RE.findall(node.value):
            if hx.lower() in role_values:
                bad.append(f"line {node.lineno}: {hx} (= {role_values[hx.lower()]})")
    assert not bad, (
        f"{_rel(path)}：三態角色色被寫死成 hex —— 必須 "
        "`from shared.colors import BUSINESS_ALERT_ON_*`，否則改 SSOT 改不到這裡。\n  "
        + "\n  ".join(bad)
    )


# ══════════════════════════════════════════════════════════════════
# R3 — 間接呼叫也要抓得到（M2 的守衛；本檔存在的主要理由）
#
# 舊守衛只認「except handler 裡的 `st.*` 呼叫」，所以包一層 helper 就隱形。
# 本條反過來從 **helper 自己** 下手：先用形狀判斷「這個函式是不是在報系統失敗」，
# 是的話，它畫出來的顏色就必須追得到系統角色 —— 不得是業務色，也不得是寫死的 hex。
#
# 三個判準取**聯集**（不是三層，是三個不同方向；(a)(b) 跨檔有效，(c) 只做同檔呼叫圖）：
#   (a) 簽章帶 exception-ish 參數（名字像 exc/err/e，或標註 Exception/BaseException）
#   (b) body 直接取例外內容（format_exc / exc_info / print_exc / format_exception）
#   (c) 被同檔的 except handler 以「帶例外內容的引數」呼叫
# 要繞過必須三個方向同時避開 —— 到那個程度，很難再主張「我在畫系統錯誤」。
# ══════════════════════════════════════════════════════════════════
def _assign_pairs(node: ast.AST):
    if isinstance(node, ast.Assign):
        for t in node.targets:
            yield t, node.value
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and node.value is not None:
        yield node.target, node.value


def _tainted_names(handler: ast.ExceptHandler) -> set[str]:
    """handler 內帶著例外內容的名字（傳遞閉包，抓 `_m = f"{e}"` 這種轉手）。"""
    tainted = {handler.name} if handler.name else set()
    changed = True
    while changed:
        changed = False
        for node in ast.walk(handler):
            for tgt, value in _assign_pairs(node):
                derived = bool({n.id for n in ast.walk(value)
                                if isinstance(n, ast.Name)} & tainted) or any(
                    (isinstance(n, ast.Attribute) and n.attr in _EXC_DERIVED)
                    or (isinstance(n, ast.Name) and n.id in _EXC_DERIVED)
                    for n in ast.walk(value))
                if not derived:
                    continue
                for n in ast.walk(tgt):
                    if isinstance(n, ast.Name) and n.id not in tainted:
                        tainted.add(n.id)
                        changed = True
    return tainted


def _fn_params(fn: ast.AST) -> list[ast.arg]:
    a = fn.args
    params = [*a.posonlyargs, *a.args, *a.kwonlyargs]
    if a.vararg:
        params.append(a.vararg)
    if a.kwarg:
        params.append(a.kwarg)
    return params


def _exc_params(fn: ast.AST) -> set[str]:
    """簽章層級的證據：這個函式是被寫來「接住一個失敗」的。"""
    out = set()
    for p in _fn_params(fn):
        ann = p.annotation
        ann_name = (ann.id if isinstance(ann, ast.Name)
                    else ann.attr if isinstance(ann, ast.Attribute) else None)
        if p.arg.lower() in _EXC_PARAM_NAMES or ann_name in _EXC_ANNOTATIONS:
            out.add(p.arg)
    return out


def _taint_closure(scope: ast.AST, seeds: set[str]) -> set[str]:
    """scope 內從 seeds 出發的賦值傳遞閉包，另收 `_EXC_DERIVED` 的產物。"""
    tainted = set(seeds)
    changed = True
    while changed:
        changed = False
        for node in ast.walk(scope):
            for tgt, value in _assign_pairs(node):
                derived = bool({n.id for n in ast.walk(value)
                                if isinstance(n, ast.Name)} & tainted) or any(
                    (isinstance(n, ast.Attribute) and n.attr in _EXC_DERIVED)
                    or (isinstance(n, ast.Name) and n.id in _EXC_DERIVED)
                    for n in ast.walk(value))
                if not derived:
                    continue
                for n in ast.walk(tgt):
                    if isinstance(n, ast.Name) and n.id not in tainted:
                        tainted.add(n.id)
                        changed = True
    return tainted


def _carries_exception(args: list[ast.AST], tainted: set[str]) -> bool:
    """這個 render 呼叫的引數，是不是真的帶著例外內容？"""
    for arg in args:
        if {n.id for n in ast.walk(arg) if isinstance(n, ast.Name)} & tainted:
            return True
        if any((isinstance(n, ast.Attribute) and n.attr in _EXC_DERIVED)
               or (isinstance(n, ast.Name) and n.id in _EXC_DERIVED)
               for n in ast.walk(arg)):
            return True
    return False


def _system_failure_renderers(tree: ast.AST) -> dict[str, tuple[str, set[str], bool]]:
    """fn 名 → (判準代號, 該 fn 內帶例外內容的名字, 是否整個函式都算失敗渲染)。

    ⚠️ **歸因強度分兩級，這是 2026-08-31 實測修掉的一個過度歸因。**
    第一版只要函式裡「出現過」例外就把整個函式判為系統失敗渲染，於是
    `ui/sidebar.py::render_sidebar()` 因為 body 某處用了 traceback，
    連一張**跟錯誤完全無關的漸層歡迎卡**（`#7c3aed,#ec4899`）都被判違規。
    那是規則的錯，不是 `sidebar.py` 的錯 —— 用白名單放行它會把錯誤鎖進規則裡。

    現行兩級：
      **簽章層級**（(a) 帶例外參數 ／ (c) 被 except handler 以帶例外的引數呼叫）
        → 這個函式**是被寫來報失敗的**，它畫的每一個 render 都算在失敗路徑上。
      **body 層級**（(b) 函式內某處取了例外內容）
        → 證據較弱（大函式什麼都做），**只有真的把例外帶進引數的那一個 render 呼叫**算數。
    """
    hits: dict[str, tuple[str, set[str], bool]] = {}
    funcs = [n for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    byname: dict[str, ast.AST] = {}
    for fn in funcs:
        byname.setdefault(fn.name, fn)

    # (c)：呼叫點的 tainted 引數 → 對映到 callee 的**參數名**（用位置/關鍵字，不猜名字）
    #
    # ⚠️⚠️ **2026-09-04：這裡由「只傳一跳」改為「迭代到不動點」—— X1 破口的修正。**
    # 本檔模組 docstring 原本就登記了 X1（同檔兩層 wrapper）並寫著「本批不做」：
    # seed 只從 **except handler 的直接 callee** 取，於是
    #     `except ... as e: _outer(t, e)` → `_outer` 被標記但自己不畫
    #                                     → `_inner` 畫了卻從未被 seed
    # **兩邊都不報。** 現在改成：只要某函式收到被污染的引數，它的對應參數就被污染，
    # 再由它往下傳給它呼叫的函式，反覆直到污染集合不再變大。
    # 2026-09-04 以**三層** wrapper 的探針實測確認是固定點，不是「補到兩跳」。
    # ⛔ **只做同檔。跨檔仍未涵蓋**（`byname` 只收本檔的 FunctionDef）——
    #    模組 docstring 既有的「wrapper 搬到另一個檔」那條缺口**原封不動仍然成立**。
    c_seeds: dict[str, set[str]] = {}

    def _seed_from_call(call: ast.Call, fn: ast.AST, tainted: set[str]) -> set[str]:
        params = [p.arg for p in _fn_params(fn)]
        # `_fn_params` 的順序是 posonly → args → kwonly → vararg → kwarg，
        # 故 params[:n_pos] 正好是「能用位置傳進去」的那些參數。
        n_pos = len(fn.args.posonlyargs) + len(fn.args.args)
        vararg = fn.args.vararg.arg if fn.args.vararg else None
        seeds: set[str] = set()
        for i, arg in enumerate(call.args):
            if not ({n.id for n in ast.walk(arg) if isinstance(n, ast.Name)} & tainted):
                continue
            if i < n_pos:
                seeds.add(params[i])
            elif vararg:
                # ⚠️ 2026-08-31 修正（探針 X2）：`def _paint(*bits)` 之下 n_pos == 0，
                # 於是 `_paint("NAV 失敗", e)` 的 e（index 1）過去會因 index 超界被
                # **靜默跳過** → taint 遺失 → 整個函式沒被判為系統失敗渲染。
                # 位置引數吃不完時是被 vararg 收走的，故污染 vararg 名。
                seeds.add(vararg)
        for kw in call.keywords:
            if kw.arg and {n.id for n in ast.walk(kw.value)
                           if isinstance(n, ast.Name)} & tainted:
                seeds.add(kw.arg)
        return seeds

    def _absorb(scope: ast.AST, tainted: set[str]) -> bool:
        grew = False
        for call in [n for n in ast.walk(scope) if isinstance(n, ast.Call)]:
            name = _call_name(call)
            fn = byname.get(name) if name else None
            if fn is None:
                continue
            new = _seed_from_call(call, fn, tainted) - c_seeds.get(name, set())
            if new:
                c_seeds.setdefault(name, set()).update(new)
                grew = True
        return grew

    for handler in [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]:
        tainted = _tainted_names(handler)
        if tainted:
            _absorb(handler, tainted)

    # 固定點：c_seeds[fn] 的上界是該 fn 的參數名集合（有限）且只增不減 → 必定終止。
    changed = True
    while changed:
        changed = False
        for name in list(c_seeds):
            if _absorb(byname[name], _taint_closure(byname[name], c_seeds[name])):
                changed = True

    for fn in funcs:
        seeds = _exc_params(fn)
        why = "(a) 簽章帶例外參數" if seeds else None
        whole_fn = bool(seeds)
        if fn.name in c_seeds:
            seeds |= c_seeds[fn.name]
            why = why or "(c) 被 except handler 以帶例外的引數呼叫"
            whole_fn = True
        if why is None and any(
                (isinstance(n, ast.Attribute) and n.attr in _EXC_DERIVED)
                or (isinstance(n, ast.Name) and n.id in _EXC_DERIVED)
                for n in ast.walk(fn)):
            why = "(b) body 取用例外內容的那一個呼叫"
        if why is None:
            continue
        hits[fn.name] = (why, _taint_closure(fn, seeds), whole_fn)
    return hits


def _failure_path_renders(tree: ast.AST, aliases: frozenset[str],
                          containers: frozenset[str]):
    """走訪：(fn, render 呼叫, 判準說明) —— 只吐真正落在失敗路徑上的 render。"""
    suspects = _system_failure_renderers(tree)
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        found = suspects.get(fn.name)
        if found is None:
            continue
        why, tainted, whole_fn = found
        for call in [n for n in ast.walk(fn) if isinstance(n, ast.Call)]:
            if not _is_render_call(call, aliases, containers):
                continue
            args = [*call.args, *(k.value for k in call.keywords)]
            if not (whole_fn or _carries_exception(args, tainted)):
                continue
            yield fn, call, args, why


@pytest.mark.parametrize("path", UI_SOURCES, ids=_rel)
def test_r3_a_system_failure_renderer_never_paints_with_the_business_colour(
        path: pathlib.Path):
    """包成 helper 也要抓得到：報系統失敗的函式不得用業務色。

    這正是舊守衛的 fail-open（見本檔模組 docstring 的實測重現）：
    `except ...: _render_failure_card("NAV 抓取失敗", e)` —— handler 裡只有一個普通呼叫，
    舊規則整條看不見；本條改看 `_render_failure_card` **自己**。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    aliases = _st_aliases(tree)
    containers = _container_names(tree, aliases)
    business = _business_names(tree)
    bad = []
    for fn, call, args, why in _failure_path_renders(tree, aliases, containers):
        if any(_mentions_business(a, business) for a in args):
            bad.append(f"line {call.lineno}: {fn.name}() {why} —— 卻用業務色渲染")
    assert not bad, (
        f"{_rel(path)}：**用業務色畫系統錯誤**。\n"
        "業務色的意思是「這個數字可信，而且它很難看」；系統紅的意思是「這個數字不可信」。"
        "兩者要使用者做的事相反 —— 系統失敗請走 render_state.system_error()。\n  "
        + "\n  ".join(bad)
    )


@pytest.mark.parametrize("path", UI_SOURCES, ids=_rel)
def test_r3_a_system_failure_renderer_never_paints_an_untraceable_hex(
        path: pathlib.Path):
    """「追不到就紅」的第二半：系統失敗路徑不得自己調一個顏色出來。

    系統紅的來源只有一個合法選項 —— `st.error()` / `system_error()` 的 widget 內建色。
    在這條路徑上寫死 hex，等於在 SSOT 之外開了一個新的、沒人管的紅。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    aliases = _st_aliases(tree)
    containers = _container_names(tree, aliases)
    bad = []
    for fn, call, args, why in _failure_path_renders(tree, aliases, containers):
        hexes = sorted({h for a in args for h in _hexes_in(a)})
        if hexes:
            bad.append(f"line {call.lineno}: {fn.name}() {why} —— "
                       f"卻寫死顏色 {', '.join(hexes)}")
    assert not bad, (
        f"{_rel(path)}：系統失敗路徑寫死了顏色，追不到任何一個角色 SSOT。\n"
        "系統紅請走 render_state.system_error()（顏色由 st.error 給）；"
        "若這其實是業務警訊，請走 business_alert()。\n  "
        + "\n  ".join(bad)
    )


def test_r3_a_varargs_wrapper_is_not_a_blind_spot():
    """`def _paint(*bits)` 也要抓得到 —— 這是 2026-08-31 修掉的一個**規則自身的 bug**。

    **它不是範圍取捨，是算錯了。** 判準 (c) 把「呼叫點的第 i 個引數」對映到
    「callee 的第 i 個參數」，但 `*args` 之下宣告參數只有一個（`bits`），
    於是 `_paint("NAV 失敗", e)` 的 `e`（index **1**）撞上 `i >= len(params)`
    被**靜默跳過** → taint 遺失 → `_paint` 從未被判為系統失敗渲染 → 用業務色也不報。

    ⚠️ **當時的實測**：舊規則之下 `_system_failure_renderers()` 對本探針回傳 `{}`（空），
    新舊守衛雙綠。修正方式：位置引數吃不完時是被 vararg 收走的，故污染 vararg 名。

    ⛔ **這條是 X2 修正的突變哨兵** —— 把 `_system_failure_renderers()` 裡
    `elif vararg: seeds.add(vararg)` 那一段拿掉，本條**必須轉紅**（已突變驗證）。
    **沒有這條，那個修正沒有任何東西守著。**
    """
    probe = (
        "import streamlit as st\n"
        "from shared.colors import BUSINESS_ALERT_ON_DARK\n"
        "def _paint(*bits):\n"
        "    st.markdown(f\"<div style='color:{BUSINESS_ALERT_ON_DARK}'>{bits}</div>\","
        " unsafe_allow_html=True)\n"
        "def render_block(payload):\n"
        "    try:\n"
        "        _ = payload['nav']\n"
        "    except Exception as e:\n"
        "        _paint('NAV 抓取失敗', e)\n"
    )
    tree = ast.parse(probe)
    suspects = _system_failure_renderers(tree)
    assert "_paint" in suspects, (
        "`*args` wrapper 沒有被判準 (c) 認出來 —— 位置引數 index 超過宣告參數數量時，"
        "taint 被靜默跳過。這是 R3 的算術 bug，不是刻意留的鬆度。"
    )
    aliases = _st_aliases(tree)
    containers = _container_names(tree, aliases)
    business = _business_names(tree)
    painted = [call for fn, call, args, _why in
               _failure_path_renders(tree, aliases, containers)
               if fn.name == "_paint"
               and any(_mentions_business(a, business) for a in args)]
    assert painted, "偵測到是系統失敗渲染，卻沒認出它畫的是業務色 —— 規則只做了一半。"


def test_r3_the_failopen_shape_is_actually_caught():
    """本檔的存在理由，寫成一條會執行的測試 —— 不是只寫在 docstring 裡。

    ⚠️ 這條刻意**不掃 repo**，而是就地組一個當初繞過舊守衛的最小違規，
    確認新規則會抓到它。舊守衛對這個形狀是綠的（實測 433 passed，見模組 docstring）。
    """
    probe = (
        "import streamlit as st\n"
        "from shared.colors import BUSINESS_ALERT_ON_DARK\n"
        "def _render_failure_card(what: str, exc: Exception) -> None:\n"
        "    st.markdown(f\"<div style='color:{BUSINESS_ALERT_ON_DARK}'>{what}{exc}</div>\","
        " unsafe_allow_html=True)\n"
        "def render_block(payload):\n"
        "    try:\n"
        "        _ = payload['nav']\n"
        "    except Exception as e:\n"
        "        _render_failure_card('NAV 抓取失敗', e)\n"
    )
    tree = ast.parse(probe)
    suspects = _system_failure_renderers(tree)
    assert "_render_failure_card" in suspects, (
        "包成 helper 的系統失敗渲染沒有被判準 (a)/(b)/(c) 認出來 —— "
        "R3 對『間接呼叫』失效，等於退回舊守衛的 fail-open。"
    )
    aliases = _st_aliases(tree)
    containers = _container_names(tree, aliases)
    business = _business_names(tree)
    painted = [call for fn, call, args, _why in
               _failure_path_renders(tree, aliases, containers)
               if fn.name == "_render_failure_card"
               and any(_mentions_business(a, business) for a in args)]
    assert painted, "偵測到是系統失敗渲染，卻沒認出它畫的是業務色 —— 規則只做了一半。"


# ══════════════════════════════════════════════════════════════════
# R4 — 泛用失敗紅（`MATERIAL_RED` / `TRAFFIC_RED`）不得手繪在三態路徑上
#
# 2026-09-04 補。**這一節分成兩條，射程不同，理由也不同 —— 不要當成同一條讀。**
#
# 背景：R3 的兩條分別看「業務色」與「**寫死的 hex**」，於是用**具名 SSOT 常數**
# 手繪的那一種，兩條都不響。本檔模組 docstring 早就把它登記成「殘餘破口」。
#
#   R4-a（下方 `test_r4_...system_failure...`）：**系統失敗路徑**上出現具名泛用紅。
#       射程 = 全 `ui/**` + `app.py`。**既有站點實測 0 處 → 零豁免、零登記。**
#       它補的正是 R3 的第三條腿：R3 已經認定「這個函式在報系統失敗」，
#       那它畫的顏色就必須追得到角色 SSOT —— 業務色不行、inline hex 不行，
#       **具名的泛用紅同樣不行**（走 `system_error()`，顏色由 `st.error` 給）。
#
#   R4-b（下方 `test_r4_...business...`）：**業務警示**被手繪成泛用失敗紅。
#       射程 = **僅 `HEALTH_SCOPE`**，這是本節唯一需要解釋的取捨，寫在下面。
#
# ⚠️⚠️ **R4-b 的射程為什麼只到 HEALTH_SCOPE（實測數字 + 理由，不要只讀結論）**
#   2026-09-04 實測全 `ui/**` + `app.py`：「render 呼叫的引數提到泛用失敗紅」共
#   **8 處 / 6 檔**（其中 8 處全部帶 `unsafe_allow_html=True`）。逐處判讀後：
#     · **2 處是真的三態違規**（業務分析成果被畫成系統紅家族）——
#       `correlation.py`（影子基金偵測）與 `risk.py`（-2σ 深度超跌），
#       兩者都落在 `business_alert()` docstring 自己列的用途（「淘汰候選」）裡；
#     · **3 處根本不是警示**，把規則開到全域就會誤傷：
#       `app.py` 的**全域 CSS 區塊**（`.signal-buy` class 用 `TRAFFIC_GREEN`）、
#       `tab3_t7_ledger.py` 的**賣方區段標題**（紅是「賣方」的版面語彙，不是警示）、
#       `tab2_single_fund.py:1070` 的 **σ 位階色**（`_hc` 隨檔位變綠／黃／紅，是資料驅動的
#       色階，不是固定警示）；
#     · **3 處介於兩者之間**（`tab1_macro_ai.py` 的「總經完整率 < 50% 阻斷」、
#       `tab2_single_fund.py` 兩處「混期示警」）—— 它們比較像「資料不可信」，
#       該走灰或紅要先有業務判斷，**不是本 lane 能單方認定的**。
#   → 開到全域 = **8 列裡有 3 列的理由只能寫「這不是警示」**，
#     那是 `CLAUDE.md §8.2.A.0 規則 5` 明禁的「理由倒置」，
#     也正是「**一條被整片豁免掉的規則等於沒有規則**」的形狀 ——
#     它比不做還糟，因為後人會以為這裡有守衛。
#   → 另外，`shared/colors.py` 就地記載 2026-08-31 那一批**刻意未動**
#     `MATERIAL_RED` 的其餘用途（吃本金／z-score／sparkline，34 檔）。
#     把射程開到那些檔 = 重新打開一個已經被決定過的範圍問題（`§8.4 步驟 4`）。
#   → 故本批**只守 `HEALTH_SCOPE`**（客戶拍板的批次一範圍，三態規則真正落地的地方）。
#
# ⛔ **本組不裁決那 6 處（4 檔）該不該一起收**，已具名上報總管。
#    **不得**引用本節主張它們合規，也**不得**引用本節主張它們違規 —— 那是還沒判定。
# ══════════════════════════════════════════════════════════════════
GENERIC_RED_TOKENS = frozenset(GENERIC_FAILURE_REDS)


def _generic_red_values() -> frozenset[str]:
    import shared.colors as C
    return frozenset(getattr(C, n).lower() for n in GENERIC_RED_TOKENS if hasattr(C, n))


def _mentions_generic_red(node: ast.AST, docstrings: set[int]) -> bool:
    """這個節點有沒有引用泛用失敗紅？（具名常數 **或** 它的 hex 值）

    ⚠️ 兩種都要看：只看具名會被 inline hex 繞過，只看 hex 會被具名常數繞過 ——
    後者正是 R3 既有的破口（R3 只檢查 inline hex）。
    ⚠️ docstring 內的 hex 一律不算（同 `_docstring_nodes()`：在文件裡講一個顏色叫什麼，
    跟把它畫出來是兩件事）。
    """
    values = _generic_red_values()
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and n.id in GENERIC_RED_TOKENS:
            return True
        if isinstance(n, ast.Attribute) and n.attr in GENERIC_RED_TOKENS:
            return True
        if (isinstance(n, ast.Constant) and isinstance(n.value, str)
                and id(n) not in docstrings):
            if any(h.lower() in values for h in _HEX_RE.findall(n.value)):
                return True
    return False


def _is_hand_drawn_html(call: ast.Call) -> bool:
    """`unsafe_allow_html=True` ＝ 這段顏色是自己畫的，不是 widget 內建色。"""
    return any(k.arg == "unsafe_allow_html" and isinstance(k.value, ast.Constant)
               and k.value.value is True for k in call.keywords)


@pytest.mark.parametrize("path", UI_SOURCES, ids=_rel)
def test_r4_a_system_failure_renderer_never_paints_a_generic_red_constant(
        path: pathlib.Path):
    """R3 的第三條腿：系統失敗路徑不得用**具名**泛用紅手繪。

    R3 已有的兩條看的是「業務色」與「**寫死的 hex**」；
    `st.markdown(f"…border:2px solid {MATERIAL_RED}…")` 兩條都躲得過 ——
    它用的是具名 SSOT 常數，不是 inline hex。本檔模組 docstring 把這個形狀
    登記為「殘餘破口」，本條把它關掉。

    **定性**：這種寫法畫的是系統紅去報系統錯誤，**語意方向沒有錯**，
    錯的是它繞過了 `system_error()` —— 於是「系統紅長什麼樣」在 SSOT 之外
    多了一個沒人管的副本，改 SSOT 改不到它，而且少了紅框該有的可展開技術細節。

    ⚠️ **既有站點實測 0 處**（2026-09-04，全 `ui/**` + `app.py`，
    分母是 13 個落在失敗路徑上的 render 呼叫）→ **本條零豁免、零登記。**
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    aliases = _st_aliases(tree)
    containers = _container_names(tree, aliases)
    docstrings = _docstring_nodes(tree)
    bad = []
    for fn, call, args, why in _failure_path_renders(tree, aliases, containers):
        if any(_mentions_generic_red(a, docstrings) for a in args):
            bad.append(f"line {call.lineno}: {fn.name}() {why} —— 卻自己畫了泛用失敗紅")
    assert not bad, (
        f"{_rel(path)}：系統失敗路徑用**具名泛用紅**手繪，繞過了角色入口。\n"
        "系統紅請走 render_state.system_error()（顏色由 st.error 給，並附可展開技術細節）；"
        "若這其實是業務警訊，請走 business_alert()。\n  "
        + "\n  ".join(bad)
    )


# ⚠️ **這是「待修」登記，不是「這樣寫是對的」豁免**
# （`CLAUDE.md §8.2.A.0 規則 5`：理由要寫「為什麼這個位置是對的」；
#   **理由若其實是「還沒修」，就照實寫「待修」，不要包裝成豁免**）。
# 兩處都是**業務分析成果**被畫成系統紅家族 —— 正是客戶鐵則 03 要拆開的那一點。
# 正解都是改走 `render_state.business_alert()`（莓紅 + 6px 左軌），屬 **production 改動**，
# 不在本 lane（只改測試檔）的邊界內，故**只登記不修**。
R4B_PENDING = {
    "ui/helpers/fund_grp_health/correlation.py::_render_one_matrix()":
        "待修。影子基金偵測（相關係數 ≥ 門檻）是**分析成功了**的業務結論，"
        "落在 business_alert() docstring 自列的「淘汰候選」用途，卻用 MATERIAL_RED 手繪卡片。"
        "正解：改走 business_alert(title, lines)。",
    "ui/helpers/fund_grp_health/risk.py::_render_oversold_badges()":
        "待修。-2σ 深度超跌同樣是業務結論（數字可信，而且很難看），"
        "卻用 MATERIAL_RED 手繪 badge。正解：改走 business_alert(title, lines)。",
}


def _r4b_sites(path: pathlib.Path) -> list[tuple[str, int, str]]:
    """HEALTH_SCOPE 內「手繪泛用失敗紅、且不在系統失敗路徑上」的 render 呼叫。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    aliases = _st_aliases(tree)
    containers = _container_names(tree, aliases)
    docstrings = _docstring_nodes(tree)
    # 落在系統失敗路徑上的歸 R4-a 管，這裡排除，避免同一處被兩條規則各報一次。
    on_failure = {id(c) for _fn, c, _a, _w in
                  _failure_path_renders(tree, aliases, containers)}
    parent = {}
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n):
            parent[c] = n
    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and _is_render_call(node, aliases, containers)):
            continue
        if id(node) in on_failure or not _is_hand_drawn_html(node):
            continue
        args = [*node.args, *(k.value for k in node.keywords)]
        if not any(_mentions_generic_red(a, docstrings) for a in args):
            continue
        cur, fname = node, "<module>"
        while cur in parent:
            cur = parent[cur]
            if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fname = cur.name
                break
        out.append((f"{_rel(path)}::{fname}()", node.lineno, fname))
    return out


@pytest.mark.parametrize("path", HEALTH_SCOPE, ids=_rel)
def test_r4_b_business_alert_is_not_hand_drawn_in_the_system_red_family(
        path: pathlib.Path):
    """業務警示不得手繪成泛用失敗紅（射程：`HEALTH_SCOPE`，理由見本節開頭）。

    客戶鐵則 03：業務上的壞消息 ＝ 業務色；系統真出錯 ＝ 紅色警示。
    把「這幾檔該換」畫成系統紅家族，等於告訴使用者「這個數字不可信」——
    **要他做的事剛好相反**（業務色要他採信並行動，系統紅要他別採信、去修）。

    ⚠️ 既有 **2 處**登記在 `R4B_PENDING`（**待修**，不是豁免）。
    新增的一律當場轉紅 —— 2026-09-04 已用探針實測：在 `HEALTH_SCOPE` 放一個
    `st.markdown(f"<div style='border:2px solid {MATERIAL_RED};…'>…吃本金…</div>",
    unsafe_allow_html=True)`，本條轉紅（舊守衛全綠）。
    """
    bad = [f"line {ln}: {fn}() —— 業務警示卻手繪泛用失敗紅"
           for key, ln, fn in _r4b_sites(path) if key not in R4B_PENDING]
    assert not bad, (
        f"{_rel(path)}：**業務警示被畫成系統紅家族**（MATERIAL_RED / TRAFFIC_RED）。\n"
        "業務色的意思是「這個數字可信，而且它很難看」；系統紅的意思是「這個數字不可信」。"
        "請改走 render_state.business_alert()（莓紅 + 6px 左軌）。\n  "
        + "\n  ".join(bad)
    )


def test_r4_b_pending_list_only_shrinks_and_every_row_has_a_reason():
    """`R4B_PENDING` 的**反向斷言**：修好一列就轉紅，逼這張表變小。

    ⚠️ 沒有這條，`R4B_PENDING` 會退化成「加進去就沒事」的白名單 ——
    那正是本 repo 反覆記載的失效模式（清單自己違反自己的禁令）。
    **紅燈在這裡是提醒不是責備**：修好了就把那一列刪掉。
    """
    live = {key for p in HEALTH_SCOPE for key, _ln, _fn in _r4b_sites(p)}
    fixed = sorted(set(R4B_PENDING) - live)
    assert not fixed, (
        f"下列站點已經不再手繪泛用失敗紅（修好了？）：{fixed}\n"
        "請把它們從 `R4B_PENDING` 刪掉 —— 待修清單只准變短。")
    thin = sorted(k for k, v in R4B_PENDING.items() if len(v) < 20)
    assert not thin, f"下列待修理由太短，看不出「正解是什麼」：{thin}"


def test_r3_c_taint_reaches_a_fixed_point_not_just_one_hop():
    """X1 破口的突變哨兵（2026-09-04）—— **任意層數**的同檔 wrapper 都要抓得到。

    ⚠️ 本檔模組 docstring 原本把 X1 登記為「要補需要把同檔呼叫圖做到不動點，
    屬**範圍擴大**，本批不做」。**2026-09-04 已做，該段登記已就地更新。**

    ⚠️ 這條刻意用**三層**（比 X1 原本登記的兩層多一跳）：兩層只能證明
    「補到了第二跳」，證不了「這是一個固定點」。**三層過了才排除掉
    『把 one-hop 改成 two-hop』這種假修法。**

    ⛔ **突變驗證**：把 `_system_failure_renderers()` 裡那段
    `while changed:` 的固定點迴圈拿掉（退回只從 handler 種一次），
    本條**必須轉紅**。2026-09-04 已實測。**沒有這條，那個修正沒有東西守著。**
    """
    probe = (
        "import streamlit as st\n"
        "from shared.colors import BUSINESS_ALERT_ON_DARK\n"
        "def _inner(what, detail):\n"
        "    st.markdown(f\"<div style='color:{BUSINESS_ALERT_ON_DARK}'>{what}{detail}</div>\","
        " unsafe_allow_html=True)\n"
        "def _mid(what, detail):\n"
        "    _inner(what, detail)\n"
        "def _outer(what, detail):\n"
        "    _mid(what, detail)\n"
        "def render_block(payload):\n"
        "    try:\n"
        "        _ = payload['nav']\n"
        "    except Exception as e:\n"
        "        _outer('NAV 抓取失敗', e)\n"
    )
    tree = ast.parse(probe)
    suspects = _system_failure_renderers(tree)
    for hop, fn in ((1, "_outer"), (2, "_mid"), (3, "_inner")):
        assert fn in suspects, (
            f"第 {hop} 跳的 wrapper `{fn}` 沒有被判準 (c) 認出來 —— "
            "taint 沒有傳到不動點，『被標記的函式不畫圖、畫圖的函式沒被標記』，"
            "兩邊都不報（X1 破口）。")
    aliases = _st_aliases(tree)
    containers = _container_names(tree, aliases)
    business = _business_names(tree)
    painted = [c for fn, c, args, _w in
               _failure_path_renders(tree, aliases, containers)
               if fn.name == "_inner" and any(_mentions_business(a, business) for a in args)]
    assert painted, (
        "最內層被判為系統失敗渲染，卻沒認出它畫的是業務色 —— 規則只做了一半。")


def test_r4_a_named_generic_red_on_a_failure_path_is_actually_caught():
    """R4-a 的突變哨兵：把 R3 的第三條腿拿掉，本條必須轉紅。

    ⛔ 突變驗證：刪掉 `_mentions_generic_red()` 裡的具名分支
    （只留 hex 比對），本條**必須轉紅** —— 2026-09-04 已實測。
    這正是本檔模組 docstring 登記的「殘餘破口」：具名 SSOT 常數躲過了 R3 的兩條腿。
    """
    probe = (
        "import streamlit as st\n"
        "from shared.colors import MATERIAL_RED\n"
        "def _fail_card(what, exc):\n"
        "    st.markdown(f\"<div style='border:2px solid {MATERIAL_RED};"
        "color:{MATERIAL_RED}'>{what}: {exc}</div>\", unsafe_allow_html=True)\n"
        "def render_block(payload):\n"
        "    try:\n"
        "        _ = payload['nav']\n"
        "    except Exception as e:\n"
        "        _fail_card('NAV 抓取失敗', e)\n"
    )
    tree = ast.parse(probe)
    aliases = _st_aliases(tree)
    containers = _container_names(tree, aliases)
    docstrings = _docstring_nodes(tree)
    hit = [c for fn, c, args, _w in _failure_path_renders(tree, aliases, containers)
           if fn.name == "_fail_card"
           and any(_mentions_generic_red(a, docstrings) for a in args)]
    assert hit, (
        "用**具名** MATERIAL_RED 手繪的系統錯誤框沒有被 R4-a 抓到 —— "
        "R3 的兩條腿（業務色／inline hex）本來就看不見它，這是本條存在的唯一理由。")


def test_r4_b_a_hand_drawn_business_alert_is_actually_caught():
    """R4-b 的突變哨兵（探針 A 的形狀）：業務警示手繪成系統紅家族要轉紅。

    ⛔ 突變驗證：把 `_is_hand_drawn_html()` 改成恆 False（或刪掉 R4-b 的
    `_mentions_generic_red` 判斷），本條**必須轉紅** —— 2026-09-04 已實測。
    """
    probe = (
        "import streamlit as st\n"
        "from shared.colors import MATERIAL_RED\n"
        "def render_principal_erosion(fund_name, pct):\n"
        "    st.markdown(f\"<div style='border:2px solid {MATERIAL_RED};"
        "color:{MATERIAL_RED}'>{fund_name} 配息吃本金 {pct}%</div>\","
        " unsafe_allow_html=True)\n"
    )
    tree = ast.parse(probe)
    aliases = _st_aliases(tree)
    containers = _container_names(tree, aliases)
    docstrings = _docstring_nodes(tree)
    on_failure = {id(c) for _f, c, _a, _w in
                  _failure_path_renders(tree, aliases, containers)}
    hit = [n for n in ast.walk(tree)
           if isinstance(n, ast.Call) and _is_render_call(n, aliases, containers)
           and id(n) not in on_failure and _is_hand_drawn_html(n)
           and any(_mentions_generic_red(a, docstrings)
                   for a in [*n.args, *(k.value for k in n.keywords)])]
    assert hit, (
        "業務警示（吃本金）手繪成 MATERIAL_RED 沒有被 R4-b 抓到 —— "
        "這正是 2026-09-04 探針 A 溜過舊守衛的形狀。")


def test_the_two_guards_scan_exactly_the_same_files():
    """SSOT 反向斷言：本檔與 hub 掃的是**同一份**檔案清單。

    ⚠️ 2026-09-04 之前本檔自己重寫了一次 glob，是 `UI_SOURCES` 的第二份副本。
    現在改成 import；本條確保它**真的**是 import 來的，而不是有人哪天又貼回一份
    「看起來一樣」的 glob（兩份各自漂移時，「兩個守衛都綠」會像雙重保險，
    實際上其中一個沒掃到那些檔）。
    """
    import test_render_state_color_separation as _hub
    assert UI_SOURCES is _hub.UI_SOURCES, (
        "`UI_SOURCES` 不是 hub 的那一個物件 —— 有人又複製了一份 glob。"
        "同一個事實只准有一個真相源（CLAUDE.md §2.1 SSOT）。")
    assert ROOT is _hub.ROOT, "`ROOT` 不是 hub 的那一個物件。"
