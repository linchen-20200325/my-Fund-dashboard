"""顏色五態分離 —— 守「形狀」而不是守字面。

客戶 2026-08-28 拍板（線框 `fund-empty-state-wireframe.html` §03）：
> 嚴格分離「業務紅燈」與「系統真紅燈」，未載入／未設定一律改灰色說明，
> 把用灰字印的真失敗改回系統紅燈。

本檔**刻意不做逐字斷言**。逐字斷言守不到語意 —— 姊妹 repo 實證過：一句假話被逐字
釘住之後，測試天天綠、話卻一直是假的。這裡守的是三種**結構**：

1. 手上有 exception → 一定不能用灰色 widget（`st.caption` / `st.info`）印出去。
   （AST：except handler 綁定的變數，不得出現在灰色 widget 的參數裡。）
2. 「金鑰／資料源沒設定」這種分支 → 一定不能用警示色 widget（`st.error` / `st.warning`）。
3. 三個入口自己畫出來的 widget 種類必須是對的（否則上面兩條可以靠改 helper 內容繞過）。

⚠️ 第 1、2 條是**單向**的：它們抓的是「畫錯顏色」，不是「有沒有畫」。
一個 except handler 什麼都不印（靜默吞掉）**不會**被本檔抓到 —— 那屬 §1 Fail Loud 的
守備範圍，不是本檔的。寫在這裡是為了讓下一個人知道本檔的邊界在哪。
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

# 本次（客戶拍板的第一批）涵蓋的範圍：組合健診套件 + 它的 Tab 主檔。
HEALTH_SCOPE = sorted((ROOT / "ui" / "helpers" / "fund_grp_health").glob("*.py")) + [
    ROOT / "ui" / "tab_fund_grp_health.py"
]

# 會把東西「印給使用者看」的呼叫：st.* 全部 + 專案自己的錯誤呈現入口。
# 「會把東西印到畫面上」的 st API。⚠️ 2026-08-28 第二輪稽核 A3：上一版漏了
# `metric` / `dataframe` / `table` / `json` / `latex` —— 用它們印例外一樣看得到，
# 卻不會被規則 1 抓到。集合漏一個，規則就在那個方向上是瞎的。
_ST_RENDER_ATTRS = {"caption", "info", "warning", "error", "success", "markdown",
                    "write", "text", "code", "toast", "exception",
                    "metric", "dataframe", "table", "json", "latex"}
_FUNC_RENDERERS = {"system_error", "friendly_error", "_friendly_error", "not_ready",
                   "business_alert"}
# 合格的「系統紅燈」入口（🔴 紅色錯誤框 + 可展開技術細節）。
RED_ENTRYPOINTS = {"system_error", "friendly_error", "_friendly_error", "st.error",
                   "st.exception"}


def _callee(call: ast.Call) -> str:
    if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name):
        return f"{call.func.value.id}.{call.func.attr}"
    if isinstance(call.func, ast.Name):
        return call.func.id
    return "<?>"


def _rendering_calls(node: ast.AST):
    """node 底下所有「會印東西給使用者看」的呼叫。"""
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        name = _callee(sub)
        if ((name.startswith("st.") and sub.func.attr in _ST_RENDER_ATTRS)
                or name in _FUNC_RENDERERS):
            yield sub


def _names_in(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


# 「這個值是從例外衍生來的」—— 不綁 `as e` 也能拿到例外內容的幾條路。
_EXC_DERIVED_CALLS = {"format_exc", "exc_info", "print_exc", "format_exception"}


def _contains(scope: ast.AST, target: ast.AST) -> bool:
    return any(n is target for n in ast.walk(scope))


def _visible_names(node: ast.AST) -> set[str]:
    """node 內用到的名字，**跳過被 comprehension 重新綁定的那些**。

    ⚠️ 2026-08-28 第二輪稽核 A2(a)：`except KeyError as e:` 之後寫
    `[x.name for e in entries]`／`[e.name for e in entries]` —— 那個 `e` 是
    comprehension **自己的**綁定，跟 handler 的 `e` 無關。而
    `for e in ...` **正是本 package 的現行慣例**（`switch_advisor_section` 就是），
    上一版會把這種完全合規的寫法叫去改成紅框。
    """
    shadow = []
    for sub in ast.walk(node):
        if isinstance(sub, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            bound = {n.id for gen in sub.generators for n in ast.walk(gen.target)
                     if isinstance(n, ast.Name)}
            if bound:
                shadow.append((sub, bound))
    out = set()
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Name):
            continue
        if any(sub.id in bound and _contains(scope, sub) for scope, bound in shadow):
            continue
        out.add(sub.id)
    return out


def _assign_pairs(node):
    """把賦值拆成 (目標, 來源值) 對；tuple 解包逐元素配對。

    ⚠️ 2026-08-28 第二輪稽核 A2(b)：`_reason, _n = str(e), len(rows)` ——
    上一版整條連坐，`_n`（只是筆數）也被當成帶著例外內容。
    """
    if isinstance(node, ast.Assign):
        value = node.value
        for tgt in node.targets:
            if (isinstance(tgt, (ast.Tuple, ast.List))
                    and isinstance(value, (ast.Tuple, ast.List))
                    and len(tgt.elts) == len(value.elts)):
                yield from zip(tgt.elts, value.elts)
            else:
                yield tgt, value
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and node.value is not None:
        yield node.target, node.value
    elif isinstance(node, ast.For):
        # `for line in traceback.format_exc().splitlines():` → line 帶著例外內容
        yield node.target, node.iter
    elif isinstance(node, ast.With):
        for item in node.items:
            if item.optional_vars is not None:
                yield item.optional_vars, item.context_expr


def _exception_tainted_names(handler: ast.ExceptHandler) -> set[str]:
    """這個 handler 裡，哪些名字「帶著例外的內容」？

    盲點 (a)（稽核組 2026-08-28 實測可繞過）：
        `except Exception as e:  _m = f"{type(e).__name__}: {e}";  st.caption(_m)`
    —— 印出去的是 `_m` 不是 `e`，只比對 `handler.name` 會放行。
    這裡做一次**傳遞閉包**：凡是賦值右邊碰到已污染的名字，左邊也污染，直到不動點。
    """
    tainted = {handler.name} if handler.name else set()
    changed = True
    while changed:
        changed = False
        for node in ast.walk(handler):
            for tgt, value in _assign_pairs(node):
                # 不綁 `as e` 但直接抓 traceback / exc_info 的，也算拿到例外內容
                derived = bool(_visible_names(value) & tainted) or any(
                    (isinstance(n, ast.Attribute) and n.attr in _EXC_DERIVED_CALLS)
                    or (isinstance(n, ast.Name) and n.id in _EXC_DERIVED_CALLS)
                    for n in ast.walk(value))
                if not derived:
                    continue
                for n in ast.walk(tgt):
                    if isinstance(n, ast.Name) and n.id not in tainted:
                        tainted.add(n.id)
                        changed = True
    return tainted


def _call_shows_exception(call: ast.Call, tainted: set[str]) -> bool:
    if _visible_names(call) & tainted:
        return True
    # 盲點 (b)：`except Exception:`（不綁）＋ 直接把 traceback 印出去
    return any(
        (isinstance(n, ast.Attribute) and n.attr in _EXC_DERIVED_CALLS)
        or (isinstance(n, ast.Name) and n.id in _EXC_DERIVED_CALLS)
        for arg in [*call.args, *(k.value for k in call.keywords)]
        for n in ast.walk(arg)
    )


@pytest.mark.parametrize("path", HEALTH_SCOPE, ids=lambda p: p.name)
def test_caught_exception_is_reported_as_a_system_failure(path: pathlib.Path):
    """真的壞掉了，畫面卻只是「還沒載入」—— 這是本批要修掉的那個 bug。

    判準（結構，不是字面）：這個 except handler **抓到了一個 exception，而且拿它去
    印給使用者看** → 那就是系統真出錯，印它的那個呼叫必須是「系統紅燈」入口。

    合格的系統紅燈入口只有兩個：
    - `ui.helpers.render_state.system_error()`（本批新增，走 friendly_error）
    - `st.error()` / `friendly_error()`（既有的正確寫法，未被本批動到的沿用）

    刻意**不**檢查訊息內容 —— 文案會被改寫，widget 種類不會。

    ⚠️ **本規則守得到什麼、守不到什麼（2026-08-28 稽核 T4 後更新，請照這個打折）**
    守得到：
      - 直接印 `as e` 綁定的名字；
      - 印一個**從 `e` 衍生**出來的中間變數（`_m = f"...{e}"` → `st.caption(_m)`），
        含 `for x in <衍生值>` 與 `with <衍生值> as x` 的綁定；
      - 不綁 `as e`、直接印 `traceback.format_exc()` / `sys.exc_info()`。
    不會誤抓（2026-08-28 稽核 A2 修正的兩個 false positive）：
      - comprehension 自己的綁定遮蔽 handler 名字（`[x for e in entries]`）；
      - tuple 解包時只有對應那一格被污染（`_reason, _n = str(e), len(rows)` → `_n` 乾淨）。
    **仍守不到**（已知盲點，不要以為守得住 —— 2026-08-28 稽核 A3 補第 4 種）：
      1. handler 什麼都不印（靜默吞掉）—— 屬 §1 Fail Loud 的守備範圍，不是本檔的；
      2. 例外內容先寫進 `dict` / `list` / `st.session_state` 再由**別的函式**印出去；
      3. ⭐ **同一個 handler 內**用容器累積後再印：`failures.append((code, e))` 之後
         印 `failures` —— 本檔只追蹤**名字之間**的傳遞，不追蹤「值進了容器」。
         ⚠️ 這正是本批新引進的 `_fetch_rich` / `_report_pool_fetch_failures` 的形狀
         （那一組是安全的：容器最後交給 `system_error`），但**規則沒有在守它**；
      4. 例外被轉成一個不含任何原名的字面字串（`st.caption("抓取失敗")`）——
         結構上與「這格沒資料」無法區分，只能靠 review。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bad = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        tainted = _exception_tainted_names(node)
        for call in _rendering_calls(node):
            if not _call_shows_exception(call, tainted):
                continue                      # 沒把例外拿給使用者看 → 不歸本檔管
            if _callee(call) in RED_ENTRYPOINTS:
                continue                      # 已經是系統紅燈
            bad.append(f"{path.relative_to(ROOT)}:{call.lineno} {_callee(call)}(…例外…)")
    assert not bad, (
        "以下位置把「抓到的例外」用非紅燈 widget 印出去，使用者會誤以為只是還沒載入、"
        "以為按一下就好；請改走 ui.helpers.render_state.system_error()：\n  "
        + "\n  ".join(bad)
    )


# ══════════════════════════════════════════════════════════════════
# 三個入口自己畫出來的 widget 種類 —— 上面的 AST 規則靠這幾條才不會被
# 「把 system_error 內容偷偷換成 st.caption」繞過。
# ══════════════════════════════════════════════════════════════════
class _FakeST:
    """記錄被呼叫的 widget 名稱（不驗文案）。"""

    def __init__(self, expander_raises: bool = False):
        self.calls: list[str] = []
        self._expander_raises = expander_raises

    def __getattr__(self, name):
        def _rec(*a, **k):
            self.calls.append(name)
        return _rec

    def expander(self, *a, **k):
        if self._expander_raises:
            # Streamlit 真的會這樣炸：Expanders may not be nested inside other expanders
            raise RuntimeError("Expanders may not be nested inside other expanders")
        import contextlib
        self.calls.append("expander")
        return contextlib.nullcontext()


def _run(fn, *, expander_raises=False, **kw):
    """在假的 streamlit 下跑 fn，回傳它畫了哪些 widget。"""
    import sys

    import ui.helpers.render_state as rs
    fake = _FakeST(expander_raises=expander_raises)
    orig_rs, orig_mod = rs.st, sys.modules["streamlit"]
    rs.st = fake
    sys.modules["streamlit"] = fake          # friendly_error 是函式內 lazy import
    try:
        fn(**kw)
    finally:
        rs.st = orig_rs
        sys.modules["streamlit"] = orig_mod
    return fake.calls


def test_not_ready_is_grey_and_cannot_carry_an_exception():
    from ui.helpers.render_state import not_ready
    calls = _run(not_ready, message="還沒載入", where="🌐 市場定調")
    assert calls == ["caption"], calls
    # 型別層防呆：「還沒載入」不可能有 exception 可報。
    with pytest.raises(TypeError):
        not_ready(RuntimeError("boom"))          # type: ignore[arg-type]


def test_system_error_is_a_red_box_with_technical_detail():
    from ui.helpers.render_state import system_error
    calls = _run(system_error, what="X 渲染失敗", exc=ValueError("boom"))
    assert "error" in calls, calls                  # 🔴 紅色錯誤框
    assert "code" in calls, calls                   # 技術細節（traceback）
    assert "caption" not in calls, calls            # 不得退化成灰字


def test_system_error_survives_a_nested_expander():
    """區塊隔離用的錯誤呈現，本身不可以炸掉整頁。

    這些 handler 有一部分住在 `st.expander` 裡（逐檔展開區）；Streamlit 禁止巢狀
    expander，硬開會把「一個區塊失敗」升級成整頁 StreamlitAPIException。
    """
    from ui.helpers.render_state import system_error
    calls = _run(system_error, expander_raises=True,
                 what="X 渲染失敗", exc=ValueError("boom"))
    assert "error" in calls and "code" in calls, calls


def test_business_alert_is_not_an_error_box():
    """業務紅燈：分析成功了，答案很難看 —— 那是成果，不是故障。"""
    from ui.helpers.render_state import business_alert
    calls = _run(business_alert, title="🔴 淘汰候選 2 檔", lines=["- A", "- B"])
    assert "error" not in calls, calls
    assert "markdown" in calls, calls


# ══════════════════════════════════════════════════════════════════
# 方向 B：「還沒設定 / 還沒載入」不得畫成警示色
#
# 兩條規則刻意用**兩種不同的抓法**，因為任一條單獨都有死角：
#   B1 結構：`if not <某個金鑰變數>:` 這個分支裡不准出現警示色 widget。
#            —— 抓得到「條件對、顏色錯」，抓不到把條件寫成別的形狀的。
#   B2 語彙：警示色 widget 的字面訊息不得帶「還沒設定」這組詞。
#            —— 抓得到條件寫成任何形狀的，抓不到把文案整組換掉的。
# 兩條一起，要繞過必須同時改掉條件寫法**和**文案。
#
# ⚠️ **2026-08-28 第二輪稽核 A1：上一版在這裡寫「那已經不是回歸，是改設計」——
#    那句風險評估不成立，實測改兩行就繞得過**：條件寫成
#    `if not st.secrets.get("FRED_API_KEY"):`（B1 只認 `if not <名字>`，
#    這是 Call 不是 Name）＋ 文案換成不帶語彙的中性句（B2 只認語彙家族）。
#    事實部分（兩條各自的抓法互補）成立；**「繞不過去」那半是我自己加上去的、
#    沒有驗證的話**。依 §-2 規則 6 就地改為誠實揭露：
#    **B1／B2 提高了繞過的成本，但擋不住刻意繞過的人。**
#    已知缺口（沒修，據實登記）：
#      - 條件不是裸名字（`st.secrets.get(...)` / `os.environ.get(...)` / `cfg.key`）；
#      - 文案完全避開語彙家族（「請先完成設定」之類）。
#    要補的話是第三條規則（追蹤憑證值的資料流），不在「只做顏色」這一批的範圍內。
# ══════════════════════════════════════════════════════════════════
ALARM_WIDGETS = {"error", "warning"}

# 「這是一個憑證 / 資料源設定」的變數命名家族（本 repo 實際用法）。
_CREDENTIAL_HINTS = ("_KEY", "KEY", "_TOKEN", "TOKEN", "SECRET", "CREDENTIAL")

# 「還沒設定」的語彙家族。放在測試裡而不是散在各檔，是為了讓它有一個可以被讀、
# 被增修的地方；新增一種說法時把它加進來，而不是去改十幾個 assert。
NOT_CONFIGURED_PHRASES = ("未設定", "未設置", "需設置", "尚未設定", "缺少必要金鑰",
                          "請在 Streamlit Cloud Secrets 填入")

UI_SOURCES = sorted((ROOT / "ui").rglob("*.py")) + [ROOT / "app.py"]


def _is_credential_name(name: str) -> bool:
    up = name.upper()
    return any(h in up for h in _CREDENTIAL_HINTS)


def _literal_text(call: ast.Call) -> str:
    """把呼叫參數裡所有字串常數串起來（f-string 的常數段也算）。"""
    out = []
    for sub in ast.walk(call):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            out.append(sub.value)
    return "".join(out)


@pytest.mark.parametrize("path", UI_SOURCES, ids=lambda p: str(p.name))
def test_b1_missing_credential_branch_is_never_alarm_coloured(path: pathlib.Path):
    """`if not FRED_KEY:` / `if not GEMINI_KEY:` 這種分支 → 一律灰色說明。

    金鑰沒填是「你還沒設定」，不是「系統壞了」。畫成紅／橘會把真紅燈的份量稀釋掉
    （線框 §03：同一個條件，全站曾經有五種畫法）。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bad = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not (isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not)):
            continue
        names = [n for n in _names_in(test) if _is_credential_name(n)]
        if not names:
            continue
        for stmt in node.body:                      # 只看這個分支自己，不看巢狀 else
            for call in _st_calls_named(stmt, ALARM_WIDGETS):
                bad.append(f"{path.relative_to(ROOT)}:{call.lineno} "
                           f"if not {names[0]}: → st.{call.func.attr}")
    assert not bad, (
        "「金鑰／憑證沒設定」被畫成警示色；請改走 "
        "ui.helpers.render_state.not_ready()：\n  " + "\n  ".join(bad)
    )


@pytest.mark.parametrize("path", UI_SOURCES, ids=lambda p: str(p.name))
def test_b2_not_configured_wording_is_never_alarm_coloured(path: pathlib.Path):
    """換個條件寫法就繞過 B1 —— 這一條從訊息本身抓。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bad = []
    for call in _st_calls_named(tree, ALARM_WIDGETS):
        text = _literal_text(call)
        hit = [p for p in NOT_CONFIGURED_PHRASES if p in text]
        if hit:
            bad.append(f"{path.relative_to(ROOT)}:{call.lineno} "
                       f"st.{call.func.attr}(…{hit[0]}…)")
    assert not bad, (
        "「還沒設定」被畫成警示色；請改走 ui.helpers.render_state.not_ready()：\n  "
        + "\n  ".join(bad)
    )


def _st_calls_named(node: ast.AST, attrs: set[str]):
    for sub in ast.walk(node):
        if (isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Attribute)
                and sub.func.attr in attrs
                and isinstance(sub.func.value, ast.Name)
                and sub.func.value.id == "st"):
            yield sub


# ══════════════════════════════════════════════════════════════════
# 方向 C：業務紅燈 vs 系統紅燈
#
# 線框 §03 最重要的一條：
#   系統紅燈 = 「這個數字**不可信**」；業務紅燈 = 「這個數字**可信**，而且它很難看」。
#   兩者要使用者做的事完全相反 —— 前者要他別採信、去修；後者要他採信、去行動。
#   用同一個紅色，等於把「不要相信這個畫面」和「相信這個畫面並據以行動」畫成同一件事。
#
# 這裡守的形狀：`st.error`（＝系統紅框）**只給「這次執行出了問題」用**。
# 判準是**這個呼叫拿不拿得到失敗證據**，不是它的文案：
#   - 手上有 exception，或
#   - 訊息是從某個 error / 失敗欄位組出來的（`…["error"]`、`_err`、`load_error` …）
# 兩者皆無 → 它畫的是一個「分析成功之後的結論」或一則常駐警語，不該用系統紅框。
# ══════════════════════════════════════════════════════════════════
# ⚠️ 這是一個**完整詞**集合，不是子字串樣板 —— 比對方式見 `_has_failure_evidence`。
_FAILURE_EVIDENCE = frozenset({
    "error", "errors", "err", "errs",
    "fail", "failed", "failure", "failures",
    "exc", "exception", "exceptions",
    "traceback", "tb",
})

# 識別字/文案切詞：只取 ASCII 英數字段。`_gs_error` → {gs, error}；
# `_excluded` → {excluded}；「（Excel 匯出同理）」→ {excel}；中文整段是分隔符。
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _has_failure_evidence(call: ast.Call) -> bool:
    """這個呼叫手上有沒有「失敗的證據」？

    ⚠️ **兩個踩過的坑，都寫在這裡，因為它們都會讓這條規則安靜地失效。**

    坑 1（第一版）：掃了整個 call node —— 而 `st.error` 的 attr 本身就是 `"error"`，
    每一個 `st.error` 都自證有證據，規則當場失效、突變測試不會紅。
    → 改為只掃**參數**（`call.args` / `call.keywords`），不碰 `call.func`。

    坑 2（第二版，稽核組 2026-08-28 抓到）：比對方式是**裸子字串** `k in blob`，
    而 `_FAILURE_EVIDENCE` 裡有 `exc` / `err` / `fail` 這種短字根。實測後果：
      - 業務結論回退成 `st.error`，變數叫 `_excluded` → `"exc"` 命中 → **被豁免**
      - 常駐警語回退成 `st.error`，文案加「（Excel 匯出同理）」→ `"exc"` 命中 → **被豁免**
    也就是「ratchet 只准往下走」這句承重宣稱，對任何含 `exc`/`err`/`fail` 子字串的
    訊息或變數名**都不成立**，新的業務紅框可以無聲加進來。
    → 改為**完整詞**比對：把識別字與文案切成 ASCII 英數 token，再跟集合取交集。
    """
    tokens: set[str] = set()
    for arg in [*call.args, *(k.value for k in call.keywords)]:
        for sub in ast.walk(arg):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                tokens |= set(_TOKEN_RE.findall(sub.value.lower()))
            elif isinstance(sub, ast.Name):
                tokens |= set(_TOKEN_RE.findall(sub.id.lower()))
            elif isinstance(sub, ast.Attribute):
                tokens |= set(_TOKEN_RE.findall(sub.attr.lower()))
    return bool(tokens & _FAILURE_EVIDENCE)


# 錯誤呈現的實作本身（它們就是那個紅框），不在受檢範圍內。
# ⚠️ 一律寫**相對路徑**不寫 basename：basename 相同的檔案在別的目錄下會被誤放行，
#    而改名會讓 parametrize case 無聲消失（下方 `test_c_declared_paths_still_exist` 擋這一半）。
_RED_BOX_IMPLEMENTATIONS = {"ui/helpers/session.py", "ui/helpers/render_state.py"}

# 本批（客戶拍板的第一批）實際轉換的兩處業務／常駐紅框所在檔案。
BATCH_SCOPE_C = {"ui/tab_fund_grp_health.py", "ui/tab6_manual.py"}


def _rel(path: pathlib.Path) -> str:
    return path.relative_to(ROOT).as_posix()

# 範圍外、**已登記待後批處理**的既有 bare `st.error`。
# ⚠️ 2026-08-28 稽核 A7：**三把不同的尺，不要互相加減**。實測 origin/main：
#   `ui/**` 不含 `app.py` ＝ 25／含 `app.py` ＝ 26／
#   **本規則自己的尺**（`UI_SOURCES` 再扣掉 `BATCH_SCOPE_C` 與 `_RED_BOX_IMPLEMENTATIONS`）＝ 23。
# 本批轉掉 4 處 → **本規則的尺由 23 降為 21**。（「25 − 4 = 21」是巧合，別再那樣寫。）
# ⚠️ 這不是豁免清單，是**待辦的可見化**：它是一個 ratchet，數字只准往下走。
# 多數是表單驗證與中文失敗訊息（「投入總額必須大於 0」「讀回失敗」），
# 判定要逐條看業務語意，不在「只做顏色」這一批的範圍內（§8.4 step 4：不自作主張擴大範圍）。
BARE_ERROR_RATCHET = 21


def _bare_error_calls(path: pathlib.Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    inside_except = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            inside_except.update(id(c) for c in _st_calls_named(node, {"error"}))
    return [c for c in _st_calls_named(tree, {"error"})
            if id(c) not in inside_except and not _has_failure_evidence(c)]


@pytest.mark.parametrize("path", sorted(p for p in UI_SOURCES if _rel(p) in BATCH_SCOPE_C),
                         ids=lambda p: str(p.name))
def test_c_system_red_box_is_reserved_for_actual_failures(path: pathlib.Path):
    """`st.error` 不得拿來畫「業務結論」或「常駐警語」。

    抓法刻意不看文案：只看這個呼叫**手上有沒有失敗證據**。
    「🔴 淘汰候選 N 檔」拿不到任何 exception / error 欄位 —— 因為分析成功了，
    它報的是成果；那就不該長得跟系統崩潰一樣。
    """
    bare = _bare_error_calls(path)
    assert not bare, (
        f"{path.relative_to(ROOT)}：st.error 拿不到任何失敗證據 —— "
        "業務結論／常駐警語不可與系統崩潰共用紅框。"
        "業務警訊走 render_state.business_alert()，常駐提醒走 st.warning()。\n  "
        + "\n  ".join(f"line {c.lineno}" for c in bare)
    )


def test_c_bare_error_backlog_only_shrinks():
    """範圍外的既有 bare `st.error` 是 ratchet：可以慢慢還，不可以再借。

    本批只做顏色，逐條判定那 21 處的業務語意不在範圍內（§8.4 step 4）；
    但新寫的 code 不准再往這個數字上加。

    ⚠️ **21 是「本規則自己這把尺」量出來的**（`UI_SOURCES` 再扣掉 `BATCH_SCOPE_C`
    與 `_RED_BOX_IMPLEMENTATIONS`），origin/main 上這把尺是 **23**，本批轉掉 4 處 → 21。
    換一把尺就是別的數字：`ui/**` 不含 `app.py` ＝ 25、含 `app.py` ＝ 26。
    **不要拿不同 scope 的數字互相加減。**
    """
    total = sum(len(_bare_error_calls(p)) for p in UI_SOURCES
                if _rel(p) not in BATCH_SCOPE_C | _RED_BOX_IMPLEMENTATIONS)
    assert total <= BARE_ERROR_RATCHET, (
        f"拿不到失敗證據的 st.error 從 {BARE_ERROR_RATCHET} 增為 {total} —— "
        "新的業務結論／常駐警語請走 business_alert() / st.warning()，不要再加進紅框。"
    )


def test_c_declared_paths_still_exist():
    """`BATCH_SCOPE_C` / `_RED_BOX_IMPLEMENTATIONS` 寫死了路徑 —— 檔案改名要出聲。

    不加這條的話，改個檔名就會讓上面的 parametrize case **無聲消失**（0 個 case
    也算通過），而 ratchet 只擋得住「數字變大」，擋不住「規則整條蒸發」。
    """
    missing = sorted(r for r in BATCH_SCOPE_C | _RED_BOX_IMPLEMENTATIONS
                     if not (ROOT / r).is_file())
    assert not missing, (
        f"下列路徑已不存在，本檔的 C 規則正在對空氣生效：{missing}"
    )


def test_c_business_verdict_uses_the_business_entrypoint():
    """反向護欄：上一條可以靠「整塊刪掉」通過，這一條擋掉那條逃生路。

    ⚠️ 用 **AST 找真正的呼叫**，不是 `"business_alert(" in src`。
    稽核組 2026-08-28 實測過那個字串版的破法：把方向 C 完整回退成 `st.error`、
    只留一行註解 `# TODO: 改回 business_alert(` —— 三條 C 規則同時失效、全綠。
    """
    tree = ast.parse((ROOT / "ui" / "tab_fund_grp_health.py").read_text(encoding="utf-8"))
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call)
             and ((isinstance(n.func, ast.Name) and n.func.id == "business_alert")
                  or (isinstance(n.func, ast.Attribute) and n.func.attr == "business_alert"))]
    assert calls, (
        "健診頁的「淘汰候選」業務警訊不見了 —— 它是分析的主要成果，"
        "改顏色不等於可以拿掉（§1）。（註解裡寫 business_alert 不算數：本條看 AST。）"
    )


# ══════════════════════════════════════════════════════════════════
# 逐檔迴圈裡的紅燈 —— 修「示警不足」不可以修出「示警過度」
#
# 2026-08-28 稽核 M1：選股池補抓失敗原本是**就地**畫紅燈，而它住在
# `_pool_rows` 的逐檔迴圈裡。選股池 20 檔，遇 proxy 掛掉或 MoneyDJ 子網域 403
# （依 `CLAUDE.md §1` Fund 脈絡屬**例行**狀況）→ 一次 20 個滿版紅框，
# 每個底下各掛一塊技術細節。那正是線框 §03 要防的
# 「滿版警示讓真錯誤沒人看見」，只是換成紅色、更嚴重。
# ══════════════════════════════════════════════════════════════════
def test_m1_per_item_fetch_helper_renders_nothing_itself():
    """`_fetch_rich` 在迴圈裡被逐檔呼叫 → 它自己不准畫任何東西。

    守的是**位置**不是文案：只要這個函式體內出現任何渲染呼叫，
    N 檔失敗就會變成 N 個框。
    """
    src = (ROOT / "ui" / "helpers" / "fund_grp_health" / "switch_advisor_section.py")
    tree = ast.parse(src.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_fetch_rich")
    rendered = [f"line {c.lineno}: {_callee(c)}" for c in _rendering_calls(fn)]
    assert not rendered, (
        "`_fetch_rich` 住在 `_pool_rows` 的逐檔迴圈裡，就地渲染會讓 N 檔失敗噴 N 個框；"
        "請把失敗收進 `failures` 由呼叫端彙總成一則：\n  " + "\n  ".join(rendered)
    )


def test_m1_the_per_item_loop_itself_renders_nothing():
    """守的是**渲染位置**，不只是「哪個函式不准畫」。

    ⚠️ 2026-08-28 第二輪稽核 N5：上一版只守 `_fetch_rich` 的函式體。稽核組實測，
    把逐檔渲染**搬進 `_pool_rows` 的迴圈裡**、改用 `system_error()` ——
    「20 檔 = 20 個滿版紅框」的原病完整復發，三條 M1 測試**全綠**。
    （改用 `st.error` 會被 ratchet 攔到，但那是後手，不是 M1 在守。）

    現在的判準：**任何呼叫 `_fetch_rich` 的迴圈，其迴圈體內不得出現渲染呼叫。**
    收集在迴圈內、上報在迴圈外，是這個機制唯一正確的形狀。
    """
    src = ROOT / "ui" / "helpers" / "fund_grp_health" / "switch_advisor_section.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    bad = []
    for loop in ast.walk(tree):
        if not isinstance(loop, (ast.For, ast.While)):
            continue
        calls_fetch = any(isinstance(c, ast.Call) and _callee(c) == "_fetch_rich"
                          for c in ast.walk(loop))
        if not calls_fetch:
            continue
        for c in _rendering_calls(loop):
            bad.append(f"{src.relative_to(ROOT)}:{c.lineno} {_callee(c)}()"
                       f"（在 line {loop.lineno} 的逐檔迴圈內）")
    assert not bad, (
        "逐檔迴圈內出現渲染呼叫 —— N 檔失敗就是 N 個框，正是線框 §03 要防的"
        "「滿版警示讓真錯誤沒人看見」；請收集到迴圈外再彙總成一則：\n  "
        + "\n  ".join(bad)
    )


def test_m1_pool_fetch_failures_are_reported_as_exactly_one_red_box(monkeypatch):
    """N 檔失敗 → **一則**系統紅燈，而且要把 N 個代號都講出來。"""
    from ui.helpers.fund_grp_health import switch_advisor_section as sas

    calls: list[tuple] = []
    monkeypatch.setattr(sas, "system_error",
                        lambda what, exc, **kw: calls.append((what, exc, kw)))
    sas._report_pool_fetch_failures(
        [("AAA", RuntimeError("boom")), ("BBB", RuntimeError("boom")),
         ("CCC", RuntimeError("boom"))])

    assert len(calls) == 1, f"應彙總成一則，實際 {len(calls)} 則"
    what = calls[0][0]
    for code in ("AAA", "BBB", "CCC"):
        assert code in what, f"彙總訊息漏掉 {code}：{what!r}"


def test_n1_ok_false_is_collected_not_silently_dropped(monkeypatch):
    """`process_one_fund` 回 `ok=False` 時，那一檔**不可以靜靜消失**。

    ⚠️ 2026-08-28 第二輪稽核 N1：上一輪的彙總機制只接 `except`，
    而 `services/fund_row.process_one_fund` **整段包在一個 try 裡、結尾一律
    `return {"ok": False, "error": ...}`（幾乎不 raise）** —— proxy 掛掉／403
    走的是 `fd["error"]` → `ok=False`。也就是說：我為一條**罕見**路徑蓋了彙總機制，
    而**主要**路徑（`ok=False` → `return None`）仍然整條靜默，`r["error"]` 被丟掉。
    這正是 `_report_pool_fetch_failures` 自己 docstring 寫的那個「示警不足」。
    """
    from ui.helpers.fund_grp_health import switch_advisor_section as sas

    monkeypatch.setattr(sas, "_pool_oauth_client", lambda: None)
    monkeypatch.setitem(
        __import__("sys").modules, "services.fund_row",
        type("M", (), {"process_one_fund":
                       staticmethod(lambda *a, **k: {"ok": False, "error": "NAV 抓不到"})})())

    failures: list = []
    assert sas._fetch_rich("AAA", "某基金", failures=failures) is None
    assert len(failures) == 1, "ok=False 沒有被收進 failures —— 該檔會靜靜消失"
    code, exc = failures[0]
    assert code == "AAA"
    assert "NAV 抓不到" in str(exc), f"上游的 error 訊息被丟掉了：{exc!r}"


def test_n1_failure_reasons_are_all_reported_not_just_the_first(monkeypatch):
    """N 檔失敗原因**各不相同**時，不可以只講第一個（§1：其餘等於被吞掉）。"""
    from ui.helpers.fund_grp_health import switch_advisor_section as sas
    calls: list[tuple] = []
    monkeypatch.setattr(sas, "system_error",
                        lambda what, exc, **kw: calls.append((what, exc, kw)))
    sas._report_pool_fetch_failures([("AAA", RuntimeError("NAV 抓不到")),
                                     ("BBB", RuntimeError("FX USDTWD 抓不到"))])
    assert len(calls) == 1
    blob = calls[0][0] + " " + str(calls[0][2].get("hint", ""))
    for reason in ("NAV 抓不到", "FX USDTWD 抓不到"):
        assert reason in blob, f"漏掉失敗原因 {reason!r}：{blob!r}"


def test_m1_no_failures_stays_silent(monkeypatch):
    """沒失敗就不要出聲（否則每次開頁都多一個框）。"""
    from ui.helpers.fund_grp_health import switch_advisor_section as sas
    calls: list = []
    monkeypatch.setattr(sas, "system_error", lambda *a, **k: calls.append(a))
    sas._report_pool_fetch_failures([])
    assert calls == []


def test_m3_degraded_is_orange_and_default_is_red():
    """M3：純圖失敗（數字全在且全對）→ 🟠；結論會變錯的失敗 → 🔴。

    兩者穿同一件衣服，等於把客戶 Q2 要建立的分辨力又抹平。
    """
    from ui.helpers.render_state import system_error
    assert "error" in _run(system_error, what="X", exc=ValueError("b"))
    assert "warning" in _run(system_error, what="X", exc=ValueError("b"), degraded=True)


# ══════════════════════════════════════════════════════════════════
# 同一句灰字不要印兩遍
#
# 2026-08-28 稽核 M2：`tab1_macro` 的「尚未設定 FRED 金鑰…」被兩個**平行**的
# `if`（同縮排，都會執行）各印一次。線框 §04① 要的是「把指錯對象的那句換掉」，
# 不是「再講一次」—— 同一句灰字印兩遍會把它變成雜訊。
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("path", UI_SOURCES, ids=lambda p: str(p.name))
def test_m2_same_grey_line_is_not_printed_twice_in_one_function(path: pathlib.Path):
    """同一個函式裡，不得有兩個 `not_ready()` 帶完全相同的訊息字面。

    守的是**重複**，不是文案內容：訊息想怎麼改都行，但不要同一句講兩遍。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    dupes = []
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        seen: dict[str, int] = {}
        for call in ast.walk(fn):
            if not (isinstance(call, ast.Call) and _callee(call) == "not_ready"
                    and call.args):
                continue
            first = call.args[0]
            if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
                continue                       # f-string / 變數 → 不比（可能真的不同）
            if first.value in seen:
                dupes.append(f"{path.relative_to(ROOT)}:{seen[first.value]} 與 "
                             f":{call.lineno} 在 {fn.name}() 內印了同一句：{first.value!r}")
            else:
                seen[first.value] = call.lineno
    assert not dupes, "同一句灰色說明重複印出：\n  " + "\n  ".join(dupes)


_CHART_CALLS = {"plotly_chart", "pyplot", "line_chart", "bar_chart", "area_chart",
                "altair_chart", "map", "image"}

# 在「只畫圖」的 try 裡出現也無妨的裸函式呼叫：Python builtins ＋ 一個具名的純數值轉換。
_CHART_SAFE_BARE_CALLS = frozenset({
    "len", "list", "dict", "set", "tuple", "float", "int", "str", "bool",
    "min", "max", "sum", "abs", "round", "sorted", "enumerate", "zip", "range",
    "isinstance", "hasattr", "getattr", "any", "all", "reversed", "map", "filter",
    # 專案自己的純數值轉換（把值安全轉 float / None），不渲染、不產生新結論。
    # ⚠️ 要往這個集合加東西，先問：它會不會在畫面上產生一個「數字」？會就不准加。
    "_safe_num",
})


def _is_chart_only_try(node: ast.Try) -> bool:
    """這個 `try:` 是不是「從頭到尾只在畫一張圖」？

    ⚠️ **2026-08-28 第二輪稽核 N4：上一版的判定是錯的，而且錯得會逼出錯誤的顏色。**
    上一版只看 `st.*` 呼叫 —— 於是這種 try 會被判成 chart-only：

        try:
            _rows = _build_ranking_table(nav, funds)   # 專案 helper，渲染數十個數字
            st.plotly_chart(_rows["fig"], ...)
        except Exception as e:
            system_error("排名表 + 疊圖失敗", e)        # 數字真的沒了 → 應該 🔴

    失敗時數字**真的消失**，卻被守衛要求改成 🟠。**「只認 st.*」等於把專案自己的
    render helper 當成隱形的。** 現在改成白名單：try 內每一個**裸函式呼叫**都必須是
    builtin 或具名的純數值轉換；只要出現一個不認識的裸呼叫（＝可能是專案 helper），
    就**不是** chart-only。方法呼叫（`fig.add_trace` / `_s.rolling` / `go.Figure`）
    不在此限 —— 它們作用在本地物件或繪圖／資料函式庫上。
    """
    st_calls = [c for b in node.body
                for c in _st_calls_named(b, _ST_RENDER_ATTRS | _CHART_CALLS)]
    charts = [c for c in st_calls if c.func.attr in _CHART_CALLS]
    if not charts or len(charts) != len(st_calls):
        return False                       # 沒畫圖、或還畫了別的 st 輸出
    for b in node.body:
        for c in ast.walk(b):
            if (isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                    and c.func.id not in _CHART_SAFE_BARE_CALLS):
                return False               # 不認識的裸呼叫 → 可能是會產生數字的 helper
    return True


@pytest.mark.parametrize("path", HEALTH_SCOPE, ids=lambda p: p.name)
def test_n3_degraded_is_not_a_one_way_escape_hatch(path: pathlib.Path):
    """`degraded=True`（🔴 → 🟠）**只准用在「只畫圖」的 try 上**。

    ⚠️ 2026-08-28 第二輪稽核 N3：`degraded=` 是整批 PR 裡**唯一能把紅變橘的槓桿**，
    而它上一輪**零守衛** —— 通過條件只寫在 docstring，機器不管。兩組稽核各自實測：
    把風險指標表（HWM σ）的真失敗、以及 `render_state` docstring 自己點名必須 🔴 的
    正例（USDTWD 不可用 → 美元計價基金被排除）加上 `degraded=True`，**全套件照樣全綠**。
    整批 PR 的論旨是「真失敗必須是紅的」，那條槓桿不能沒有鎖。

    ⚠️ 這是**單向**規則，刻意的：它擋「不該降的降了」，**不強迫**「該降的一定要降」。
    反方向的強迫規則（chart-only ⇒ 必須 degraded）上一輪存在過，被稽核 N4 打掉 ——
    它會把「數字真的消失」的區塊逼成橘色，正好是客戶 Q2 要建立的分辨力的反方向。
    代價據實揭露：**把某處的 `degraded=True` 拿掉不會有測試轉紅**（那個方向由 review 守）。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bad = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try) or _is_chart_only_try(node):
            continue
        for handler in node.handlers:
            for call in ast.walk(handler):
                if (isinstance(call, ast.Call) and _callee(call) == "system_error"
                        and any(k.arg == "degraded"
                                and getattr(k.value, "value", False) is True
                                for k in call.keywords)):
                    bad.append(f"{path.relative_to(ROOT)}:{call.lineno}")
    assert not bad, (
        "以下 `system_error(degraded=True)` 所在的 try **不是「只畫圖」**——"
        "失敗時畫面上會少掉或改掉數字，使用者可能因此做出錯誤決定，不得降為 🟠：\n  "
        + "\n  ".join(bad)
    )
