"""④ 新頁的**寫入入口** —— 加入標的、以及「加了但還沒抓到淨值」怎麼講。

客戶 2026-09-08 拍板（逐字）
---------------------------
> 「**加入基金入口：拍板整合至 ⑨「保單與扣款標的」，無持倉時直接就地展開輸入表單。**」
> 「…退場順序完全同意採「⑦ → ⑥ → ⑧ → ⑨」，並**以「⑨ 建立寫入入口」為第一前置**。」

也就是說：**這一塊做不出來，舊分頁就不能拔。** 本檔守的就是那個前置條件。

它守的三件事（與四組獨立調查驗出來的三個斷點一一對應）
------------------------------------------------------
======================================== ==========================================
調查驗出來的斷點                           本檔對應的守衛
======================================== ==========================================
新五頁寫進 `portfolio_funds` 的呼叫點      :func:`test_submitting_the_form_really_writes_into_portfolio_funds`
**是 0 個** ⇒ 新 UI 物理上加不了基金
`render_asset_allocation` 在沒有持倉時      :func:`test_the_form_is_on_screen_when_there_are_no_holdings_at_all`
early return，連表單都不畫
雲端讀回／JSON 還原之後基金是               :func:`test_a_book_full_of_unloaded_rows_is_not_called_empty`
`loaded=False`，被 `_holdings()` 濾掉      ＋ :func:`test_the_page_says_the_new_rows_have_no_nav_yet`
⇒ 畫面是空的，而且**沒有一句話**
告訴使用者還差一步
======================================== ==========================================

⭐ **本檔刻意不 import streamlit，一行都沒有**
----------------------------------------------
1. **純函式**（`ui/helpers/portfolio/add_entry.py`）—— 大小寫、複合鍵去重、
   同一批內重複、讀不懂的行。
2. **指路**（AST）—— 「去哪按載入」指到的地方**真的按得到**。

**渲染那一半住在 `tests/test_wf04_add_holdings_render.py`**，因為它需要 AppTest。
⛔ **兩者刻意分成兩個檔案，不是分成同一檔的兩段** —— `pytest.importorskip`
是**模組級**的：把它寫在同一個檔案的中間，沒有 streamlit 時**整個檔案**都會被 skip，
連上面這些根本不需要 streamlit 的斷言也一起不跑。
**那會讓「這些邊界在沒有 streamlit 的環境也跑得到」變成一句假話**，
而抽出純函式的全部理由就是那一句。

⚠️ **本檔由實作組單組產出，未經第二組獨立複驗**（`CLAUDE.md §-2` 規則 6）。
"""

from __future__ import annotations

import ast
import pathlib
import sys
from typing import Any

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from ui.helpers.portfolio.add_entry import (  # noqa: E402
    NEW_ENTRY_INVEST_TWD,
    NEW_ENTRY_LOADED,
    entry_key,
    new_holding,
    parse_lines,
    pending_rows,
    pending_split,
    plan_new_holdings,
)

# ══════════════════════════════════════════════════════════════════
# 1) 純函式 —— **不需要 streamlit**
# ══════════════════════════════════════════════════════════════════


def test_a_plain_line_becomes_one_skeleton_row():
    """一行一個代碼 → 一筆條目，欄位與 `sync_policies_to_portfolio_funds` 同構。"""
    _p = plan_new_holdings("0050", [], default_policy_id="")
    assert [_r["code"] for _r in _p["rows"]] == ["0050"]
    _row = _p["rows"][0]
    assert _row["invest_twd"] == NEW_ENTRY_INVEST_TWD
    assert _row["load_error"] is None
    assert _row["policy_id"] == "" and _row["policy_name"] == ""


def test_the_new_row_is_not_marked_loaded():
    """⭐ **本批最承重的一個決定：新條目是 `loaded=False`，不是舊 ④ 的 `True`。**

    舊 ④ 敢寫 `True` 是因為它在同一顆按鈕裡把 MoneyDJ 抓完了；
    本頁**一次網路都不打**。寫 `True` 會讓 `page_04_portfolio._holdings()`
    把一筆什麼都沒有的條目當成有效持倉，核心／衛星比例、總投入、集中度
    全部會把它算進去 —— `CLAUDE.md §1`：**錯誤的數字比沒有數字更危險。**

    ⚠️ 斷言比對的是 :data:`NEW_ENTRY_LOADED` 這個**具名常數**，不是硬抄一個 `False`。
       硬抄的話，常數一改這條就永遠是 True —— 它守的 bug 照樣存在、而它不再看得見。
    """
    assert NEW_ENTRY_LOADED is False, (
        "新條目被改成 `loaded=True` 了 —— 這一頁沒有抓任何資料，"
        "那個 `True` 是一句謊話，而且下游會拿它去算比例。")
    assert new_holding("0050", "")["loaded"] is NEW_ENTRY_LOADED


def test_the_code_is_upper_cased_like_the_old_entry_did():
    """代碼一律大寫 —— 與舊 ④ 與 `sync_policies_to_portfolio_funds` 相同。

    ⚠️ 不統一大小寫的代價**不是美觀**：去重鍵含代碼，`abc` 與 `ABC`
       會變成兩筆，同一檔基金在保單一覽裡出現兩列。
    """
    assert plan_new_holdings("abc", [])["rows"][0]["code"] == "ABC"
    assert entry_key(" abc ", " P1 ") == ("ABC", "P1")
    # ⭐ **也驗 `parse_lines` 這一層** —— 少了這一行，「把 `parse_lines` 的正規化
    #    拿掉」這顆突變**活得下來**（實測：`passed=18 failed=0`），因為下游
    #    `new_holding()` 又走了一次 `entry_key`。那不是安全網，那是重複實作。
    #    現行 `parse_lines` 已改為委派 `entry_key`，本行釘住那個委派。
    assert parse_lines(" abc , p1 ")[0] == [("ABC", "p1")]


def test_the_default_policy_only_fills_the_lines_that_did_not_say():
    """行內寫了保單編號 → 用行內的；沒寫 → 才套用預設那一格。"""
    _p = plan_new_holdings("AAA\nBBB,自己的保單", [], default_policy_id="預設保單")
    assert [(_r["code"], _r["policy_id"]) for _r in _p["rows"]] == [
        ("AAA", "預設保單"), ("BBB", "自己的保單")]


def test_the_same_code_under_two_policies_is_two_rows():
    """⭐ 去重鍵是 `(代碼, 保單編號)` **複合鍵**，不是單獨的代碼。

    這一點是舊 ④ v18.56 修 bug 修出來的：使用者報告「19 筆跨 4 保單，
    讀回後變 7 檔 unique code」。用單鍵會讓同一檔基金在不同保單間互相覆蓋。
    """
    _p = plan_new_holdings("0050,保單甲\n0050,保單乙", [])
    assert [(_r["code"], _r["policy_id"]) for _r in _p["rows"]] == [
        ("0050", "保單甲"), ("0050", "保單乙")]


@pytest.mark.parametrize("existing,raw,want_added,want_skipped", [
    # 已經在清單裡 → 跳過
    ([{"code": "0050", "policy_id": ""}], "0050", [], [("0050", "")]),
    # 大小寫不同、其實是同一筆 → 也要跳過
    ([{"code": "0050", "policy_id": ""}], "0050 ", [], [("0050", "")]),
    # 同一批裡貼了兩次 → 第二次跳過（使用者貼上時很常見）
    ([], "0050\n0050", [("0050", "")], [("0050", "")]),
    # 保單不同 → 不是重複
    ([{"code": "0050", "policy_id": "甲"}], "0050,乙", [("0050", "乙")], []),
])
def test_a_duplicate_is_skipped_and_reported(existing, raw, want_added, want_skipped):
    """重複的不重複加，**而且要講出來**（§1：不靜默吞掉使用者的輸入）。"""
    _p = plan_new_holdings(raw, existing)
    assert _p["added"] == want_added
    assert _p["skipped"] == want_skipped


def test_a_line_without_a_code_is_reported_not_guessed():
    """讀不出代碼的行 → **原封回報**，不猜、不丟掉（§1）。"""
    _p = plan_new_holdings("0050\n,只有保單沒有代碼\n  \n0056", [])
    assert [_r["code"] for _r in _p["rows"]] == ["0050", "0056"]
    assert _p["invalid"] == [",只有保單沒有代碼"], (
        "讀不懂的那一行不是原封回報 —— 使用者無從知道他打的東西怎麼了。")


def test_blank_lines_are_not_errors():
    """空白行直接跳過，**不算「讀不懂」** —— 貼一段帶空行的文字是常態。"""
    assert plan_new_holdings("\n\n0050\n\n", [])["invalid"] == []


def test_the_plan_does_not_mutate_what_it_was_given():
    """純函式：`existing` 一個位元都不能被改到。

    ⚠️ 這不是潔癖：呼叫端拿到的是 `st.session_state["portfolio_funds"]` 本尊。
       就地修改它 ＝ **在算出結果之前就已經寫進去了**，
       那會讓「這一批到底加了什麼」變成不可知（也會讓上面那些去重斷言變成假的）。
    """
    _existing: list[dict[str, Any]] = [{"code": "0050", "policy_id": ""}]
    _snapshot = [dict(_f) for _f in _existing]
    _p = plan_new_holdings("0056", _existing)
    assert _existing == _snapshot, "`existing` 被就地改掉了。"
    assert len(_p["merged"]) == 2 and _p["merged"][0] is _existing[0]


def test_junk_in_the_list_is_kept_not_silently_dropped():
    """`existing` 裡形狀不對的元素**原樣保留**，不參與去重、也不被丟掉。

    它不是我們寫的，我們不猜它的意思，也不悄悄把它刪了（§1）。
    """
    _existing = ["這不是 dict", {"code": "0050", "policy_id": ""}]
    _p = plan_new_holdings("0056", _existing)
    assert _p["merged"][0] == "這不是 dict"
    assert len(_p["merged"]) == 3


def test_pending_split_separates_waiting_from_failed():
    """⭐ 「還沒抓」與「抓過失敗」要分得開 —— **兩者的下一步完全不同**。

    還沒抓的：去按一次載入就好。
    抓過失敗的：再按一百次也一樣，要看的是原因。
    合成一句「N 檔未載入」，等於叫使用者去做一件對其中一半沒有用的事。
    """
    _funds = [
        {"code": "A", "loaded": True},                       # 好的
        {"code": "B", "loaded": False},                      # 還沒抓
        {"code": "C", "loaded": True, "load_error": "404"},  # 抓過、失敗
    ]
    _waiting, _failed = pending_split(_funds)
    assert [_f["code"] for _f in _waiting] == ["B"]
    assert [_f["code"] for _f in _failed] == ["C"]
    assert [_f["code"] for _f in pending_rows(_funds)] == ["B", "C"]


def test_pending_rows_survives_a_missing_or_broken_session_value():
    """session 裡那個鍵可能是 `None`、可能不是 list —— 不准炸、也不准猜。"""
    assert pending_rows(None) == []
    assert pending_rows("不是 list") == []
    assert pending_rows([None, 3, {"code": "A", "loaded": False}]) == [
        {"code": "A", "loaded": False}]


def test_parse_lines_reads_only_the_first_comma():
    """保單編號裡有逗號時不得被切斷 —— 只切**第一個**逗號。"""
    _entries, _ = parse_lines("0050,保單甲,附約")
    assert _entries == [("0050", "保單甲,附約")]


# ══════════════════════════════════════════════════════════════════
# 2) 指路 —— AST，**不需要 streamlit**
# ══════════════════════════════════════════════════════════════════

def test_the_load_pointer_is_not_a_dead_end():
    """⭐ **「去哪按載入」指到的地方，真的按得到載入** —— 去那個檔案裡確認。

    ## 這條與 `test_story_nav.py` 的漂移鎖**不重複**

    那一條驗的是「`🗂️ 保單分組視圖` 這幾個字還在不在 `ui/tab3_portfolio.py` 裡」——
    **字還在，不代表那裡還按得到載入**。本條驗的是後者：
    那個檔案裡真的有 `batch_load_unloaded_funds(...)` 的呼叫。

    ⚠️ **alias 要解析**：舊 ④ 的三處呼叫都是
    ``from ui.helpers.portfolio_load import batch_load_unloaded_funds as _batch_load_top``
    這種帶別名的寫法，純字串 grep `batch_load_unloaded_funds(` **一處都掃不到**
    （同 `tests/test_wpf_five_tab_wiring.py` 記載過的那個形狀）。

    ⛔ **紅了要做什麼**：那顆載入鈕若真的搬走了，正解是**改指路**（改
    `story_nav._SECTION_LABELS['pf_load']` 指到新家），**不是把本條拿掉**。
    ⛔ 若它是**整個不見了**（舊 ④ 被拔），那代表新五頁裡沒有任何地方能載入 ——
       那是一個**必須先解決**的斷點，不是一條可以刪掉的測試。
    """
    from ui.helpers.story_nav import where_to_find

    _where = where_to_find("pf_load")
    assert "🗂️ 保單分組視圖" in _where, (
        f"`where_to_find('pf_load')` 沒有帶上分區名：{_where!r}")

    _old = ROOT / "ui" / "tab3_portfolio.py"
    _tree = ast.parse(_old.read_text(encoding="utf-8"))
    # 別名解析：`from ... import batch_load_unloaded_funds as X` → 收集所有 X。
    _names: set[str] = set()
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.ImportFrom):
            for _a in _n.names:
                if _a.name == "batch_load_unloaded_funds":
                    _names.add(_a.asname or _a.name)
    assert _names, (
        f"{_old.name} 裡找不到 `batch_load_unloaded_funds` 的 import —— "
        f"本頁把使用者指到 {_where}，那是一條死指路。")
    _calls = [_n.lineno for _n in ast.walk(_tree)
              if isinstance(_n, ast.Call)
              and getattr(_n.func, "id", None) in _names]
    assert _calls, (
        f"{_old.name} import 了 `batch_load_unloaded_funds` 卻**沒有呼叫它** —— "
        f"本頁把使用者指到 {_where}，他到了那裡按不到任何東西。")

    # ⭐ **再釘那一顆按鈕本身。**
    # ⚠️ 只驗「這個檔案裡有 `batch_load_unloaded_funds(...)`」**不夠** ——
    #    突變實測：把「保單分組視圖」頂部那一處的 import 改掉，
    #    **本條仍然全綠**（舊 ④ 底下另有兩處同名呼叫替它過關）。
    #    而指路指的是**那一個區塊**，不是那個檔案。
    #    `key="btn_pf_load_all_top"` 是那顆頂部主按鈕的穩定錨點
    #    （它旁邊那一行就是 `_batch_load_top()`）。
    _keys = {_k.value for _n in ast.walk(_tree)
             if isinstance(_n, ast.Call)
             and getattr(_n.func, "attr", None) == "button"
             for _kw in _n.keywords
             if _kw.arg == "key" and isinstance(_kw.value, ast.Constant)
             for _k in (_kw.value,)}
    assert "btn_pf_load_all_top" in _keys, (
        f"{_old.name} 裡找不到「{_where}」頂部那顆載入鈕"
        "（`key=\"btn_pf_load_all_top\"`）—— 使用者到了那一區會找不到東西可按。\n"
        "⛔ 若它真的搬走了，正解是改 `story_nav._SECTION_LABELS['pf_load']` 指到新家，"
        "不是把本條拿掉。")


def test_the_empty_state_no_longer_sends_people_to_the_old_add_block():
    """⛔ **空狀態不得再把使用者指去舊 ④ 的「加入與管理基金」。**

    客戶 2026-09-08 把那個入口整合到本頁，而且已拍板退場順序（⑦→⑥→⑧→⑨）——
    舊 ④ 一拔，`where_to_find('pf_add')` 就指向一個不存在的地方。

    ## 為什麼用 AST 而不是渲染

    渲染版的同型斷言在 `tests/test_wf04_portfolio_skeleton.py::`
    `test_nothing_renders_before_holdings_land`，**但它需要 streamlit**。
    本條只讀原始碼，所以**在沒有 streamlit 的環境也擋得住**這顆突變
    （實測：把 `where=` 改回 `where_to_find("pf_add")`，本條轉紅）。

    ⚠️ **射程只到 `_render_no_holdings` 這一支。** 本頁別處（例如
    `_render_mix` 的「一檔本金都沒填」灰態）**目前仍在用 `pf_add`**，
    那是**另一件事**（它指的是「去哪填投入金額」，不是「去哪加基金」），
    **不在本批的射程內，也不由本條管** —— 據實寫明，不假裝掃乾淨了。
    """
    _page = ROOT / "ui" / "views" / "page_04_portfolio.py"
    _fn = next((_n for _n in ast.walk(ast.parse(_page.read_text(encoding="utf-8")))
                if isinstance(_n, ast.FunctionDef)
                and _n.name == "_render_no_holdings"), None)
    assert _fn is not None, "找不到 `_render_no_holdings` —— 它被改名或刪掉了。"
    _bad = [f"第 {_n.lineno} 行 {ast.unparse(_n)}"
            for _n in ast.walk(_fn)
            if isinstance(_n, ast.Call)
            and getattr(_n.func, "id", None) == "where_to_find"
            and _n.args and isinstance(_n.args[0], ast.Constant)
            and _n.args[0].value == "pf_add"]
    assert not _bad, (
        "空狀態又把使用者指回舊 ④ 的「加入與管理基金」了：\n  " + "\n  ".join(_bad)
        + "\n⛔ 那個入口已經整合到本頁（`ADD_FUND_HEADING`），而舊 ④ 排定要拔掉。")


def test_the_new_wording_carries_no_internal_progress_language():
    """⛔ **畫面上只准有「使用者的處境」，不准有「我們的進度」。**

    客戶抱怨過三次。本條掃的是**本批新寫的那些活字串**
    （`add_entry.py` 全檔 ＋ `page_04_portfolio` 的三支新函式），
    不是整頁 —— 整頁掃會被既有的 `_PENDING_NOTE`（「本頁分批上線」）打紅，
    而那一句是**別批**刻意留著的灰態理由，不在本批的檔案邊界內。

    ⚠️ **本條看的是 AST 活字串，不是渲染結果** —— 註解與 docstring 裡可以講
    「取數」「分批上線」，那是寫給下一個維護者看的，不會出現在畫面上。
    """
    _banned = ("已送客戶確認", "上游", "取數", "分批上線", "policy_tier",
               "Jaccard", "session_state", "portfolio_funds")
    _targets: list[tuple[str, ast.AST]] = []
    _add_entry = ROOT / "ui" / "helpers" / "portfolio" / "add_entry.py"
    _targets.append((_add_entry.name, ast.parse(_add_entry.read_text(encoding="utf-8"))))
    _page = ROOT / "ui" / "views" / "page_04_portfolio.py"
    _page_tree = ast.parse(_page.read_text(encoding="utf-8"))
    for _fn in ast.walk(_page_tree):
        if (isinstance(_fn, ast.FunctionDef)
                and _fn.name in ("_render_add_fund", "_render_add_result",
                                 "_render_pending_notice", "_render_no_holdings")):
            _targets.append((f"{_page.name}::{_fn.name}", _fn))

    _docs: set[int] = set()
    for _name, _node in _targets:
        for _n in ast.walk(_node):
            if isinstance(_n, (ast.Module, ast.ClassDef, ast.FunctionDef,
                               ast.AsyncFunctionDef)):
                _b = getattr(_n, "body", None)
                if (_b and isinstance(_b[0], ast.Expr)
                        and isinstance(_b[0].value, ast.Constant)
                        and isinstance(_b[0].value.value, str)):
                    _docs.add(id(_b[0].value))

    _bad: list[str] = []
    for _name, _node in _targets:
        for _n in ast.walk(_node):
            if not (isinstance(_n, ast.Constant) and isinstance(_n.value, str)):
                continue
            if id(_n) in _docs:
                continue
            for _w in _banned:
                if _w in _n.value:
                    _bad.append(f"{_name}:{_n.lineno} 出現「{_w}」：{_n.value[:60]!r}")
    assert not _bad, (
        "本批新寫的畫面文字裡出現了內部語言：\n  " + "\n  ".join(_bad)
        + "\n⛔ 理由寫程式碼註解，不要寫畫面。")
