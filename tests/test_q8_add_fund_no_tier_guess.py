"""Q8 止血第三批 — 「新增基金」不得再用基金名稱猜核心/衛星寫進客戶的 Google Sheet。

**這支測試守的是什麼**
`ui/tab3_portfolio.py`（保單分頁批次新增）與 `ui/tab3_t7_ledger.py`（帳本分頁新增）
在建立「新基金」紀錄時，曾經用 `_is_core_fund(基金名稱)` 這個**關鍵字啟發式**猜一個
核心/衛星，接著 `upsert_fund_in_policy(...)` 就把猜出來的值當成 `policy_tier`
**直接寫進使用者的 Google Sheet**。那是不可逆的資料汙染：使用者從沒設定過級別，
Sheet 上卻出現一個看起來像他設定過的值。

修復方式是**不寫**，不是改猜法 —— 紀錄裡不再有 `is_core` 鍵，下游既有的三元式
`("core" if …get("is_core") else "satellite" if …get("is_core") is False else "")`
就會落到 `else ""`，也就是「未設定」。

**為什麼用「抽出真源碼再執行」而不是字串比對**
字串比對只能證明某幾個字不見了，證明不了「寫進 Sheet 的到底是什麼」。
本檔用 AST 從**真的 production 檔案**裡把那段 `for` 迴圈／dict 建構式與
`policy_tier` 運算式整段挖出來執行，斷言的是**最後真的會送進 upsert 的那個值**。
把猜測加回 production，本檔會轉紅。

**錨點刻意不是被修的那幾行**（否則修好之後錨點就消失、測試會變成空轉）：
- portfolio 用 upsert payload 裡的 `"notes": "Tab3 batch add"`
- ledger   用 `_new_pf = {...}` 這個變數名與讀 `_fobj_w3` 的 upsert payload
錨點若找不到 → **AssertionError（紅燈）**，不是 skip。
"""
from __future__ import annotations

import ast
import sys
import types
from pathlib import Path
from unittest import mock

import pytest

_ROOT = Path(__file__).resolve().parents[1]

# 兩個名稱刻意選成會被 `is_core_fund` 判成相反結果的一組：
# 「科技」命中 _SAT_KEYWORDS → False；「配息」命中 _CORE_KEYWORDS → True。
# 修復前它們會寫出 'satellite' / 'core' 兩個不同的非空值，修復後必須都是 ''。
TECH_FUND = "富蘭克林華美AI科技基金"
DIVI_FUND = "安聯收益成長基金(基金之配息來源可能為本金)"


# ──────────────────────────────────────────────────────────────────────
# 取出真源碼的工具（全部走 AST，不用固定行數的上下文窗）
# ──────────────────────────────────────────────────────────────────────
def _src(rel: str) -> str:
    p = _ROOT / rel
    s = p.read_text(encoding="utf-8")
    # 防「重導向建出空檔 / 讀到半個檔」那一類假通過：這兩個檔都是十萬 bytes 等級
    assert len(s.encode("utf-8")) > 20_000, f"{rel} 只有 {len(s.encode())} bytes，讀取有問題"
    return s


def _dict_arg(call: ast.Call):
    for a in call.args:
        if isinstance(a, ast.Dict):
            return a
    return None


def _dict_get(d: ast.Dict, key: str):
    for k, v in zip(d.keys, d.values):
        if isinstance(k, ast.Constant) and k.value == key:
            return v
    return None


def _calls_named(tree: ast.AST, fname: str):
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f = n.func
            got = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
            if got == fname:
                yield n


def _record_assign(tree: ast.AST, varname: str):
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Dict):
            if any(isinstance(t, ast.Name) and t.id == varname for t in n.targets):
                return n
    return None


def _record_dicts(tree: ast.AST, varname: str):
    """`varname = {...}` 與 `varname.update({...})` 的所有 dict literal。"""
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Dict):
            if any(isinstance(t, ast.Name) and t.id == varname for t in n.targets):
                out.append((n.lineno, n.value))
        elif isinstance(n, ast.Expr) and isinstance(n.value, ast.Call):
            c = n.value
            if (isinstance(c.func, ast.Attribute) and c.func.attr == "update"
                    and isinstance(c.func.value, ast.Name) and c.func.value.id == varname):
                d = _dict_arg(c)
                if d is not None:
                    out.append((n.lineno, d))
    return sorted(out, key=lambda t: t[0])


def _smallest_enclosing_loop(tree: ast.AST, lo: int, hi: int):
    best = None
    for n in ast.walk(tree):
        if isinstance(n, (ast.For, ast.While)) and n.lineno <= lo and n.end_lineno >= hi:
            if best is None or (n.end_lineno - n.lineno) < (best.end_lineno - best.lineno):
                best = n
    return best


class _SessionState:
    def __init__(self):
        self.portfolio_funds: list = []


class _StStub:
    def __init__(self):
        self.session_state = _SessionState()


class _PolicySheetError(Exception):
    pass


class _OAuthError(Exception):
    pass


# ──────────────────────────────────────────────────────────────────────
# portfolio：整段 for 迴圈（含 if/else 分支與真正的 upsert payload）拿去跑
# ──────────────────────────────────────────────────────────────────────
def _portfolio_upsert_payload(fund_name: str) -> dict:
    src = _src("ui/tab3_portfolio.py")
    tree = ast.parse(src)

    anchor = None
    for call in _calls_named(tree, "upsert_fund_in_policy"):
        d = _dict_arg(call)
        if d is None:
            continue
        note = _dict_get(d, "notes")
        if isinstance(note, ast.Constant) and note.value == "Tab3 batch add":
            anchor = call
            break
    assert anchor is not None, (
        "錨點不見了：ui/tab3_portfolio.py 找不到 notes='Tab3 batch add' 的 "
        "upsert_fund_in_policy —— 新增基金寫回 Sheet 的位置換了，本測試必須重寫"
    )
    rec = _record_assign(tree, "_new_item_b")
    assert rec is not None, "錨點不見了：找不到 `_new_item_b = {...}`"

    loop = _smallest_enclosing_loop(
        tree, min(rec.lineno, anchor.lineno), max(rec.end_lineno, anchor.end_lineno)
    )
    assert loop is not None, "錨點不見了：紀錄建構與 upsert 不在同一個迴圈內"

    seg = ast.get_source_segment(src, loop)
    assert seg and "upsert_fund_in_policy" in seg

    from ui.helpers.session import is_core_fund

    captured: dict = {}

    def _upsert(_client, _sid, _pid, payload):
        captured["payload"] = payload

    ns = {
        "_results": {("F0001", "P1"): ({"fund_name": fund_name, "currency": "USD"}, "")},
        "_fail": [], "_succ": [], "_sheet_synced": [],
        "_client_b": object(), "_sid_b": "<sheet-id-stub>",
        "_is_core_fund": is_core_fund,
        "upsert_fund_in_policy": _upsert,
        "PolicySheetError": _PolicySheetError, "OAuthError": _OAuthError,
        "st": _StStub(),
    }
    # 那段真源碼裡有一句 `from services.fund_history import record_fund`，
    # 而 `record_fund()` 會**真的寫 `cache/` 底下的 JSON**（相對於 CWD）。
    # 測試不可以有這種副作用，所以在 exec 期間把該模組換成 no-op。
    # ⚠️ 換的是**模組**不是被測邏輯 —— 上面那段 for 迴圈本身一個字都沒動。
    _fake_hist = types.ModuleType("services.fund_history")
    _fake_hist.record_fund = lambda *a, **k: None
    with mock.patch.dict(sys.modules, {"services.fund_history": _fake_hist}):
        exec(compile(seg, "<tab3_portfolio:add-fund-loop>", "exec"), ns, ns)
    assert "payload" in captured, "真的 for 迴圈跑完卻沒走到 Sheet upsert —— 測試前提失效"
    captured["record"] = ns["st"].session_state.portfolio_funds[0]
    return captured


# ──────────────────────────────────────────────────────────────────────
# ledger：建 `_new_pf`，再用讀 `_fobj_w3` 的那個 upsert 的真 policy_tier 運算式去算
#   真實資料流：_new_pf → st.session_state.portfolio_funds → _pf_t7
#               → _f_obj → _funds_to_sheet → upsert(_fobj_w3)
# ──────────────────────────────────────────────────────────────────────
def _ledger_tier(fund_name: str) -> tuple[str, dict]:
    src = _src("ui/tab3_t7_ledger.py")
    tree = ast.parse(src)

    rec = _record_assign(tree, "_new_pf")
    assert rec is not None, "錨點不見了：ui/tab3_t7_ledger.py 找不到 `_new_pf = {...}`"

    from ui.helpers.session import is_core_fund

    ns = {
        "_new_code_clean": "F0001",
        "_new_raw": {"fund_name": fund_name, "currency": "USD"},
        "_is_core_fund": is_core_fund,
    }
    exec(compile(ast.get_source_segment(src, rec), "<tab3_t7_ledger:_new_pf>", "exec"), ns, ns)
    record = ns["_new_pf"]

    tier_src = None
    for call in _calls_named(tree, "upsert_fund_in_policy"):
        d = _dict_arg(call)
        if d is None:
            continue
        if "_fobj_w3" not in (ast.get_source_segment(src, d) or ""):
            continue
        v = _dict_get(d, "policy_tier")
        if v is not None:
            tier_src = ast.get_source_segment(src, v)
            break
    assert tier_src is not None, (
        "錨點不見了：ui/tab3_t7_ledger.py 找不到讀 `_fobj_w3` 的 upsert policy_tier 運算式"
    )
    # get_source_segment 只給 value node，它的外層括號在 dict entry 上 →
    # 多行三元式必須自己補括號才 compile 得起來。
    tier = eval(compile("(" + tier_src + "\n)", "<tab3_t7_ledger:policy_tier>", "eval"),
                {"_fobj_w3": record}, {})
    return tier, record


# ══════════════════════════════════════════════════════════════════════
# 0) 前提：啟發式本身仍然會把這兩個名字判成相反 —— 否則下面的「兩者相同」會空轉
# ══════════════════════════════════════════════════════════════════════
def test_the_two_sample_names_are_still_discriminated_by_the_heuristic():
    """若 is_core_fund 哪天對這兩個名字回同一個值，本檔的「不受名稱影響」就會變成
    **空轉的假綠燈**（兩邊相同只是因為輸入沒差別）。這條把那個前提釘死。"""
    from ui.helpers.session import is_core_fund

    assert is_core_fund(TECH_FUND) is False, "科技型樣本不再被判為衛星 —— 請換樣本"
    assert is_core_fund(DIVI_FUND) is True, "配息型樣本不再被判為核心 —— 請換樣本"


# ══════════════════════════════════════════════════════════════════════
# 1) 保單分頁（ui/tab3_portfolio.py）
# ══════════════════════════════════════════════════════════════════════
def test_portfolio_tech_fund_writes_unset_tier():
    assert _portfolio_upsert_payload(TECH_FUND)["payload"]["policy_tier"] == "", (
        "新增科技型基金時，保單分頁又把猜出來的級別寫進客戶 Google Sheet"
    )


def test_portfolio_dividend_fund_writes_unset_tier():
    assert _portfolio_upsert_payload(DIVI_FUND)["payload"]["policy_tier"] == "", (
        "新增配息型基金時，保單分頁又把猜出來的級別寫進客戶 Google Sheet"
    )


def test_portfolio_tier_does_not_depend_on_fund_name():
    """這條才是真正的止血斷言：兩個**會被啟發式判成相反**的名稱，寫回值必須一樣。"""
    a = _portfolio_upsert_payload(TECH_FUND)["payload"]["policy_tier"]
    b = _portfolio_upsert_payload(DIVI_FUND)["payload"]["policy_tier"]
    assert a == b == "", f"寫回 Sheet 的級別仍隨基金名稱改變：科技型={a!r} 配息型={b!r}"


def test_portfolio_new_fund_record_carries_no_is_core_key():
    assert "is_core" not in _portfolio_upsert_payload(TECH_FUND)["record"], (
        "新增基金的紀錄又帶了 is_core —— 下游三元式會據此寫出非空的 policy_tier"
    )


def test_portfolio_add_fund_path_never_calls_the_name_heuristic():
    """連呼叫都不該有 —— 擋掉「換個 key 名繼續猜」這種變體。"""
    src = _src("ui/tab3_portfolio.py")
    tree = ast.parse(src)
    anchor = next(
        (c for c in _calls_named(tree, "upsert_fund_in_policy")
         if (d := _dict_arg(c)) is not None
         and isinstance(n := _dict_get(d, "notes"), ast.Constant)
         and n.value == "Tab3 batch add"),
        None,
    )
    assert anchor is not None, "錨點不見了：notes='Tab3 batch add' 的 upsert"
    rec = _record_assign(tree, "_new_item_b")
    assert rec is not None
    loop = _smallest_enclosing_loop(
        tree, min(rec.lineno, anchor.lineno), max(rec.end_lineno, anchor.end_lineno)
    )
    bad = [n.lineno for n in ast.walk(loop)
           if isinstance(n, ast.Name) and n.id in {"_is_core_fund", "is_core_fund"}]
    assert not bad, f"新增基金路徑又呼叫了名稱啟發式，行號：{bad}"


# ══════════════════════════════════════════════════════════════════════
# 2) 帳本分頁（ui/tab3_t7_ledger.py）
# ══════════════════════════════════════════════════════════════════════
def test_ledger_tech_fund_writes_unset_tier():
    assert _ledger_tier(TECH_FUND)[0] == "", (
        "新增科技型基金時，帳本分頁又把猜出來的級別寫進客戶 Google Sheet"
    )


def test_ledger_dividend_fund_writes_unset_tier():
    assert _ledger_tier(DIVI_FUND)[0] == "", (
        "新增配息型基金時，帳本分頁又把猜出來的級別寫進客戶 Google Sheet"
    )


def test_ledger_tier_does_not_depend_on_fund_name():
    a, _ = _ledger_tier(TECH_FUND)
    b, _ = _ledger_tier(DIVI_FUND)
    assert a == b == "", f"寫回 Sheet 的級別仍隨基金名稱改變：科技型={a!r} 配息型={b!r}"


def test_ledger_new_fund_record_carries_no_is_core_key():
    assert "is_core" not in _ledger_tier(TECH_FUND)[1], (
        "新增基金的紀錄又帶了 is_core —— 下游三元式會據此寫出非空的 policy_tier"
    )


def test_ledger_no_longer_imports_the_name_heuristic():
    """帳本分頁的 `is_core_fund` import 在拿掉猜測後成為孤兒，已同批刪除。

    ⚠️ **刻意只對帳本分頁斷言。** `ui/tab3_portfolio.py` 的同名 import
    **不是**孤兒 —— `tests/test_tab3_portfolio.py::test_is_core_fund_alias`
    仍然 `from ui.tab3_portfolio import _is_core_fund` 並斷言 identity，
    刪掉它會讓那支既有測試轉紅。詳見 EXCEPTIONS.md 該筆登記。
    """
    src = _src("ui/tab3_t7_ledger.py")
    tree = ast.parse(src)
    bad = [(n.lineno, a.name) for n in ast.walk(tree)
           if isinstance(n, ast.ImportFrom)
           for a in n.names if a.name in {"is_core_fund", "_is_core_fund"}]
    assert not bad, f"ui/tab3_t7_ledger.py 又 import 了名稱啟發式：{bad}"
    used = [n.lineno for n in ast.walk(tree)
            if isinstance(n, ast.Name) and n.id in {"_is_core_fund", "is_core_fund"}]
    assert not used, f"ui/tab3_t7_ledger.py 又用了名稱啟發式，行號：{used}"


# ══════════════════════════════════════════════════════════════════════
# 3) 反向對照：三元式本身沒被改壞 —— 有 is_core 時它仍該寫出非空值
#    （否則上面那堆 '' 可能只是因為三元式被人改成恆回空字串）
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("flag,expected", [(True, "core"), (False, "satellite")])
def test_downstream_ternary_still_maps_an_explicit_flag(flag, expected):
    """本批**沒有**改那個三元式（它仍然無視 policy_tier，屬另一批的事）。
    這條確認它原封不動：拿掉 is_core 之後寫出 '' 是因為**鍵不在了**，
    不是因為三元式被改成恆空 —— 兩者在畫面上一樣，在語意上完全不同。"""
    src = _src("ui/tab3_t7_ledger.py")
    tree = ast.parse(src)
    tier_src = None
    for call in _calls_named(tree, "upsert_fund_in_policy"):
        d = _dict_arg(call)
        if d is None or "_fobj_w3" not in (ast.get_source_segment(src, d) or ""):
            continue
        v = _dict_get(d, "policy_tier")
        if v is not None:
            tier_src = ast.get_source_segment(src, v)
            break
    assert tier_src is not None, "錨點不見了：讀 _fobj_w3 的 upsert policy_tier"
    got = eval(compile("(" + tier_src + "\n)", "<ternary>", "eval"),
               {"_fobj_w3": {"is_core": flag}}, {})
    assert got == expected, f"下游三元式語意變了：is_core={flag!r} → {got!r}（預期 {expected!r}）"
