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
    #    ⚠️ ~~現行 `parse_lines` 已改為委派 `entry_key`，本行釘住那個委派。~~
    #    → **2026-09-08 更正：這句話比它撐得起的強**（**有意識的更正，不是漏刪** ·
    #      決策者：**AI 總管**，依據獨立稽核指出後本組自行突變複驗）。
    #      **實測**：把 `parse_lines` 裡的 `entry_key(...)` 換成一份**行為完全相同的
    #      inline 複製**（`.strip().upper()` / `.strip()`），**本檔 22 條全綠**。
    #      也就是說本行釘住的是**行為**，**不是**「有沒有真的委派」——
    #      它擋得住「正規化被拿掉」，擋不住「正規化被複製成第二份」。
    #      **舊表述的用意仍然成立**（這一行確實補住了第一輪那顆存活的突變，
    #      而那顆突變正是「拿掉 `parse_lines` 的正規化」）；**被權衡掉的是它的強度宣稱**。
    #    ⛔ 要真的釘住委派，需要 AST 驗 `parse_lines` 內確實呼叫 `entry_key`。
    #      **本批沒有加那一條**（它會擴大本批射程），據實登記為缺口。
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


def test_a_non_list_existing_blows_up_instead_of_being_shredded():
    """⭐ **§1 Fail Loud：`existing` 型別不對就當場炸，不准安靜地拆掉它。**

    ## 這條擋的是一個「畫面正常、資料已壞」的事故（2026-09-08 獨立稽核指出）

    :func:`plan_new_holdings` 的 `merged` 會被
    `page_04_portfolio._render_add_fund` **直接寫回持倉清單** ——
    它是新五頁**唯一**會寫那個鍵的地方。而在補護欄之前那裡只有
    ``list(existing or [])``，於是傳進來一個 dict 會變成**它的 key 清單**、
    傳進來一個字串會變成**單一字元的清單**，然後被原樣寫回去。
    下游 `_holdings()` / :func:`pending_rows` 的 ``isinstance(_f, dict)``
    會把那些垃圾**全部濾掉** —— **畫面看起來一切正常，清單已經被換掉了。**

    ⛔ **正解是 raise，不是 `or []` / `if isinstance(...) else []`**：
       後者會把「呼叫端傳錯東西」這個 bug 靜靜吞掉，症狀變成**使用者的持倉憑空消失**，
       而那是 `CLAUDE.md §1` 逐字點名的「掩蓋問題，不是解決問題」。
    ⚠️ 兄弟函式 :func:`pending_rows` 用 ``return []`` 是**唯讀**路徑（最多少畫幾列），
       本函式是**寫入**路徑 —— 兩者代價不同級，所以處置刻意不同。

    ⚠️ **本條驗的是「有沒有炸」，不是訊息長什麼樣**：訊息措辭另受
    :func:`test_the_new_wording_carries_no_internal_progress_language` 約束
    （它禁止在本檔的活字串裡出現內部語言），比對字面值會讓兩條互相打架。
    """
    # `None` 與 list 一律照舊放行 —— session 鍵還沒建立時 `.get()` 就是回 `None`。
    assert plan_new_holdings("0050", None)["added"] == [("0050", "")]
    assert plan_new_holdings("0050", [])["added"] == [("0050", "")]

    # ⛔ 非 list 一律 raise。**四種形狀都測**，因為它們壞掉的方式不一樣：
    #    dict → 拆成 key；str → 拆成單一字元；int → `list()` 直接 TypeError
    #    （那一種本來就會炸，但訊息完全看不出是誰傳錯的）；tuple → 悄悄被接受。
    for _bad in ({"0050": 1}, "0050", 42, ("0050",)):
        with pytest.raises(TypeError):
            plan_new_holdings("0056", _bad)

    # ⭐ **最承重的一條：dict 不得被拆成 key 寫進 `merged`。**
    #    這是突變測試真正會抓到的那一顆 —— 把護欄拿掉之後，下面這行不會 raise，
    #    而 `merged` 會變成 `["0050", "0056"]`（兩個**字串**，不是 dict）。
    try:
        _m = plan_new_holdings("XXXX", {"0050": 1, "0056": 2})["merged"]
    except TypeError:
        pass                                    # 期望路徑
    else:                                       # pragma: no cover - 護欄失效才會到
        raise AssertionError(
            "dict 沒有被擋下來，而且已經被拆成："
            f"{[_x for _x in _m if not isinstance(_x, dict)]!r} —— "
            "這幾筆會被寫回持倉清單，然後被下游的 isinstance 過濾**整個吃掉**："
            "畫面上完全看不出來，資料已經壞了。")


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


def _button_keys(tree: ast.AST) -> set[str]:
    """檔內所有 `st.button(..., key=…)` 的 key。

    ⚠️ **f-string 的 key 取它的常數前綴**（`f"del_pf_{i}"` → `"del_pf_"`）——
    逐列產生的按鈕 key 一定帶變數，只收 `ast.Constant` 會**一顆都收不到**。
    """
    _out: set[str] = set()
    for _n in ast.walk(tree):
        if not (isinstance(_n, ast.Call)
                and getattr(_n.func, "attr", None) == "button"):
            continue
        for _kw in _n.keywords:
            if _kw.arg != "key":
                continue
            if isinstance(_kw.value, ast.Constant):
                _out.add(str(_kw.value.value))
            elif isinstance(_kw.value, ast.JoinedStr):
                _out.add("".join(_v.value for _v in _kw.value.values
                                 if isinstance(_v, ast.Constant)))
    return _out


def test_the_policy_admin_pointer_is_not_a_dead_end():
    """⭐ **狀態列三格指去的「保單管理」，真的按得到那兩件事** —— 去那個檔案裡確認。

    ## 這條與 `test_story_nav.py` 的漂移鎖**不重複**（同 `pf_load` 的雙鎖形狀）

    那一條驗的是「那個 expander 標題還在不在」——**字還在，不代表那裡還做得到事**。
    本條驗後者，而且**逐格對應到它真正要解決的那個鍵**：

    ===================== ====================================================
    ⑨ 狀態列的哪一格       它指過去要按的東西
    ===================== ====================================================
    📒 目前帳本            `key="btn_pick_my_sheet"`（✅ 使用此 Sheet 作為投組
                          資料庫）→ 寫 `policy_sheet_id`
    🕐 上次讀回            `key="t3_io_panel_load_run"`（📥 立即全部讀回）
                          → 寫 `t3_last_load_at`
    💰 總投入              同上那顆讀回鈕（金額在雲端 Sheet 上填，讀回才會進來）
    ===================== ====================================================

    ⚠️ **還要驗「舊 ④ 真的會渲染它」**：那 800 行被 WP-D 抽成獨立模組，
    舊 ④ 只剩一行委派。**模組存在 ≠ 使用者到得了** —— 若舊 ④ 不再呼叫它，
    這三格就全部變成死指路，而漂移鎖（比字串）**完全看不出來**。

    ⛔ **紅了要做什麼**：那個收合區若真的搬家了，正解是改
    `story_nav._SECTION_LABELS['pf_policy_admin']` 指到新家，**不是把本條拿掉**。
    """
    from ui.helpers.story_nav import where_to_find

    from ui.helpers.story_nav import section_label

    _where = where_to_find("pf_policy_admin")
    _mod = ROOT / "ui" / "helpers" / "portfolio" / "policy_admin_section.py"
    _tree = ast.parse(_mod.read_text(encoding="utf-8"))

    # ⭐ **SSOT 的字必須和那個 expander 的標題「逐字相等」，不是「包含」。**
    # ⚠️ 這一條是突變測試逼出來的，不是設計出來的：`test_story_nav.py` 的漂移鎖
    #    走的是 `_want in _src`（**子字串**），所以把 SSOT 從
    #    「📋 保單管理（Google Sheets）— Sheet 設定 / 保單清單」**截短**成
    #    「📋 保單管理」**照樣全綠** —— 實測那顆突變 10 passed。
    #    截短的指路會把使用者送去找一個畫面上不存在的標題，而漂移鎖看不見。
    #    → 本條用**相等**補上那個缺口（子字串鎖仍然保留，兩條方向不同：
    #      那條擋「目的地改字」，本條擋「SSOT 自己被改鬆」）。
    _labels = [_n.args[0].value for _n in ast.walk(_tree)
               if isinstance(_n, ast.Call)
               and getattr(_n.func, "attr", None) == "expander"
               and _n.args and isinstance(_n.args[0], ast.Constant)]
    assert len(_labels) == 1, (
        f"{_mod.name} 現在有 {len(_labels)} 個常數標題的 expander：{_labels!r} —— "
        "本條原本靠「只有一個」來認出那一區。多出來的話要改成具名定位，"
        "**不是**把這條斷言拿掉。")
    assert section_label("pf_policy_admin") == _labels[0], (
        "`_SECTION_LABELS['pf_policy_admin']` 與那個 expander 的標題不再逐字相同：\n"
        f"  SSOT     = {section_label('pf_policy_admin')!r}\n"
        f"  畫面實際 = {_labels[0]!r}\n"
        "⛔ 指路會指到一個使用者在畫面上找不到的標題。")

    # (a) 兩顆鈕都在。
    _keys = _button_keys(_tree)
    for _k, _what in (("btn_pick_my_sheet", "換一本帳本"),
                      ("t3_io_panel_load_run", "從雲端全部讀回")):
        assert _k in _keys, (
            f"{_mod.name} 裡找不到「{_what}」那顆鈕（`key=\"{_k}\"`）—— "
            f"⑨ 的狀態列把使用者指到 {_where}，他到了那裡按不到東西。")

    # (b) 兩顆鈕**真的寫到 ⑨ 讀的那兩個鍵**（不是只長得像）。
    #     ⚠️ 這兩個鍵正是 `page_04_portfolio._book_title()` 與 `_status_tiles()`
    #        讀的東西 —— 沒有這一半，指路只是「那裡有一顆鈕」而已。
    _written = {_t.slice.value
                for _n in ast.walk(_tree) if isinstance(_n, ast.Assign)
                for _t in _n.targets
                if isinstance(_t, ast.Subscript)
                and "session_state" in ast.dump(_t.value)
                and isinstance(_t.slice, ast.Constant)
                and isinstance(_t.slice.value, str)}
    for _key in ("policy_sheet_id", "t3_last_load_at"):
        assert _key in _written, (
            f"{_mod.name} 沒有寫 `{_key}` —— ⑨ 狀態列讀的就是這個鍵，"
            f"指使用者去 {_where} 等於叫他做一件不會改變畫面的事。")

    # (c) 舊 ④ 真的會渲染這一支（否則使用者根本到不了）。
    _old = ROOT / "ui" / "tab3_portfolio.py"
    _old_tree = ast.parse(_old.read_text(encoding="utf-8"))
    _names = {_a.asname or _a.name
              for _n in ast.walk(_old_tree) if isinstance(_n, ast.ImportFrom)
              for _a in _n.names if _a.name == "render_policy_admin_section"}
    assert _names, (
        f"{_old.name} 沒有 import `render_policy_admin_section` —— "
        f"⑨ 把使用者指到 {_where}，但舊 ④ 已經不渲染那一區了。")
    assert [_n.lineno for _n in ast.walk(_old_tree)
            if isinstance(_n, ast.Call)
            and getattr(_n.func, "id", None) in _names], (
        f"{_old.name} import 了卻沒有呼叫 `render_policy_admin_section` —— 死指路。")


def test_the_principal_pointer_is_not_a_dead_end():
    """⭐ **「去哪填本金」指到的地方，真的打得進一個金額** —— 而且兩處是同一個答案。

    ## 這條是第二輪獨立稽核擋下來的那件事

    在此之前**同一個缺失欄位 `invest_twd`、同一個畫面、兩句相反的話**：
    :func:`_render_mix` 指 `pf_add`、`_status_tiles` 的 💰 那一格指 `pf_policy_admin`。
    **兩句不可能同時是對的**，而實測顯示**兩句都不是最好的那一句**：

    - `pf_add`（舊 ④「➕ 加入與管理基金」）**填不了本金** —— 實測
      `ui/tab3_portfolio.py` 對 `invest_twd` **只有** `invest_twd: 0` 的字面值
      （新條目）與原樣搬運既有值，**沒有任何一處寫使用者輸入的金額**。
    - `pf_policy_admin` 走得通，但要**離開 App** 去改 Sheet 再回來讀。

    → 兩處統一指 `pf_ledger`（舊 ④「💼 持倉戰情（T7 帳本）」），因為那裡的
    `🟨 淨投資金額 (NT)` 是**全站唯一「使用者打一個金額進去、它就落在持倉清單上」**
    的地方，而且**無 OAuth／schema 條件**。

    ⚠️ **本條同時是 `pf_ledger` 的逐字相等鎖。** `P-SECLABEL-1`（見
    `EXCEPTIONS.md §8.3.P`）記著：既有漂移鎖走 `_want in _src`（**子字串**），
    **截短照樣全綠**。本批把 `pf_ledger` 變成「去哪填本金」的唯一答案，
    它因此成為本批的**承重** key —— 所以在這裡把它鎖成相等。
    ⛔ **其餘幾個仍然只有子字串鎖，本批刻意不動**（`CLAUDE.md §8.4 步驟 4`：
    不擅自擴大範圍），已登記在 `P-SECLABEL-1`。
    """
    import ast as _ast

    from ui.helpers.story_nav import section_label, where_to_find

    _page = ROOT / "ui" / "views" / "page_04_portfolio.py"
    _ptree = _ast.parse(_page.read_text(encoding="utf-8"))

    # (a) 兩處都指 `pf_ledger`，而且**都不**指 `pf_add`。
    def _where_keys(fnname: str) -> set[str]:
        _fn = next((_n for _n in _ast.walk(_ptree)
                    if isinstance(_n, _ast.FunctionDef) and _n.name == fnname), None)
        assert _fn is not None, f"找不到 {fnname} —— 它被改名或刪掉了。"
        return {_n.args[0].value for _n in _ast.walk(_fn)
                if isinstance(_n, _ast.Call)
                and getattr(_n.func, "id", None) == "where_to_find"
                and _n.args and isinstance(_n.args[0], _ast.Constant)}

    _mix = _where_keys("_render_mix")
    _tiles = _where_keys("_status_tiles")
    assert "pf_ledger" in _mix, (
        f"`_render_mix` 的指路不是 `pf_ledger`，而是 {sorted(_mix)} —— "
        "算不出比例時要指到「去哪填本金」，而那裡是帳本。")
    assert "pf_ledger" in _tiles, (
        f"`_status_tiles` 沒有任何一格指 `pf_ledger`（實際：{sorted(_tiles)}）—— "
        "💰 總投入那一格要指到「去哪填本金」。")
    assert "pf_add" not in _mix, (
        "`_render_mix` 又指回 `pf_add` 了 —— 那一區填不了本金，使用者會撲空。")

    # (b) SSOT 的字與舊 ④ 那個抬頭**逐字相等**（不是「包含」）。
    _old = ROOT / "ui" / "tab3_portfolio.py"
    _osrc = _old.read_text(encoding="utf-8")
    _otree = _ast.parse(_osrc)
    _heads = {_n.args[0].value.removeprefix("### ")
              for _n in _ast.walk(_otree)
              if isinstance(_n, _ast.Call)
              and getattr(_n.func, "attr", None) == "markdown"
              and _n.args and isinstance(_n.args[0], _ast.Constant)
              and isinstance(_n.args[0].value, str)
              and _n.args[0].value.startswith("### ")}
    assert section_label("pf_ledger") in _heads, (
        f"`_SECTION_LABELS['pf_ledger']` ＝ {section_label('pf_ledger')!r} 不在舊 ④ 的"
        f"一級抬頭清單裡：{sorted(_heads)}\n"
        "⛔ 指路會指到一個使用者在畫面上找不到的標題（截短也會在這裡紅）。")

    # (c) 那一區真的會渲染 T7（否則使用者到得了標題、到不了輸入格）。
    _names = {_a.asname or _a.name for _n in _ast.walk(_otree)
              if isinstance(_n, _ast.ImportFrom)
              for _a in _n.names if _a.name == "render_t7_section"}
    assert _names and [_n for _n in _ast.walk(_otree)
                       if isinstance(_n, _ast.Call)
                       and getattr(_n.func, "id", None) in _names], (
        f"{_old.name} 沒有真的呼叫 `render_t7_section` —— "
        f"本頁把使用者指到 {where_to_find('pf_ledger')}，那是一條死指路。")

    # (d) ⭐ 那裡真的有一個「打得進金額」的輸入格，而且它真的寫 `invest_twd`。
    _led = ROOT / "ui" / "tab3_t7_ledger.py"
    _ltree = _ast.parse(_led.read_text(encoding="utf-8"))
    _keys = _button_keys(_ltree) | {
        "".join(_v.value for _v in _kw.value.values if isinstance(_v, _ast.Constant))
        for _n in _ast.walk(_ltree)
        if isinstance(_n, _ast.Call) and getattr(_n.func, "attr", None) == "number_input"
        for _kw in _n.keywords
        if _kw.arg == "key" and isinstance(_kw.value, _ast.JoinedStr)}
    assert "t7_init_inv_" in _keys, (
        f"{_led.name} 裡找不到那個金額輸入格（`key=f\"t7_init_inv_{{pk}}\"`）—— "
        "本頁把使用者指過去，他到了那裡沒有東西可以填。")
    _writes = [_ast.unparse(_n) for _n in _ast.walk(_ltree)
               if isinstance(_n, _ast.Assign)
               for _t in _n.targets
               if isinstance(_t, _ast.Subscript)
               and isinstance(_t.slice, _ast.Constant)
               and _t.slice.value == "invest_twd"]
    assert _writes, (
        f"{_led.name} 有輸入格、卻**沒有任何一處**把它寫進 `invest_twd` —— "
        "那就跟 `pf_add` 一樣是撲空。")

    # ══════════════════════════════════════════════════════════════════
    # ⭐ (e)~(h)：**指路要在「畫面印出它的那個狀態」下有效**，不是在別的狀態下有效
    #
    # 第三輪獨立稽核用**真渲染**擋下一件事：`pf_ledger` 在「加了但還沒抓到」
    # （rows 有、一檔都沒 `loaded`）那個狀態下**是死的** —— T7 的「✏️ 編輯持倉」
    # 住在 `if not _pf_t7:` 的 else 分支，那個狀態下整個 expander 不渲染。
    # ⚠️ 而 (a)~(d) 四項**結構上看不到它**：稽核的兩顆突變都全綠 ——
    #   M-GATE-1：舊 ④ 只在恆假條件下呼叫 `render_t7_section`  → 23 passed
    #   M-GATE-2：`expanded=True` → `False`                      → 23 passed
    #   （正對照：目的地不再寫 `invest_twd` → RED，證明本條不是恆綠。）
    # 下面四項就是補那個洞。**判準：如果我的新答案在那個狀態下是錯的，這裡會不會紅？**
    # ══════════════════════════════════════════════════════════════════

    # (e) ⭐ **謂詞等價** —— 這是整個修法賴以成立的那一條，先釘死它。
    #     本頁 `_holdings()` 濾 `loaded and not load_error`；
    #     T7 的閘門 `ui/helpers/session.py::fund_is_usable` 也是 `loaded and not load_error`。
    #     **兩者相同 ⇒ `_holdings()` 非空 ⟺ 那個輸入格一定渲染得出來。**
    #     任一邊改了謂詞，這個等價就斷了，指路會在某個狀態下再度變死。
    from ui.helpers.session import fund_is_usable

    for _row, _want in (({"loaded": True}, True),
                        ({"loaded": True, "load_error": None}, True),
                        ({"loaded": True, "load_error": "404"}, False),
                        ({"loaded": False}, False),
                        ({}, False),
                        ("not-a-dict", False)):
        assert fund_is_usable(_row) is _want, (
            f"`fund_is_usable({_row!r})` 不再等於 `loaded and not load_error` —— "
            "本頁 `_holdings()` 與 T7 的閘門就此不同源，"
            "「有已載入的標的 ⇒ 編輯持倉一定在」這個前提斷掉，`pf_ledger` 會變回死指路。")

    _hold_fn = next(_n for _n in _ast.walk(_ptree)
                    if isinstance(_n, _ast.FunctionDef) and _n.name == "_holdings")
    # ⚠️ `ast.unparse` 會把字串常數正規化成單引號，所以這裡比對的是**正規化後**的形狀
    #    （本組第一版寫 `get("loaded")` 雙引號，當場自己紅了一次）。
    _hold_src = _ast.unparse(_hold_fn)
    assert "get('loaded')" in _hold_src and "get('load_error')" in _hold_src, (
        "`_holdings()` 的過濾條件變了 —— 它必須與 `fund_is_usable` 同一個謂詞，"
        f"否則本格的狀態分界就不再對應 T7 的閘門：\n{_hold_src[:400]}")

    # (f) ⭐ **本格必須是條件式**，不能無條件給 `pf_ledger`。
    #     這一條直接對應被擋下的那個 bug：無條件給 = 在 pending 狀態下指到不存在的東西。
    _tiles_fn = next(_n for _n in _ast.walk(_ptree)
                     if isinstance(_n, _ast.FunctionDef) and _n.name == "_status_tiles")
    _led_calls = [_n for _n in _ast.walk(_tiles_fn)
                  if isinstance(_n, _ast.Call)
                  and getattr(_n.func, "id", None) == "where_to_find"
                  and _n.args and isinstance(_n.args[0], _ast.Constant)
                  and _n.args[0].value == "pf_ledger"]
    assert _led_calls, "`_status_tiles` 不再指 `pf_ledger` —— 若是刻意改的，本條要一起改。"
    _guarded = [_c for _c in _led_calls
                if any(isinstance(_n, _ast.IfExp)
                       and _n.lineno <= _c.lineno <= (_n.end_lineno or 0)
                       and "_loaded" in _ast.unparse(_n.test)
                       for _n in _ast.walk(_tiles_fn))]
    assert len(_guarded) == len(_led_calls), (
        "`_status_tiles` 裡有 `where_to_find(\"pf_ledger\")` **不在**「有沒有已載入標的」"
        "的條件式底下 —— 那會在「加了但還沒抓到」的狀態下指到一個**不存在**的輸入格"
        "（T7 的「✏️ 編輯持倉」在該狀態不渲染）。**這正是第三輪稽核擋下的那個 bug。**")

    # (g) ⭐ **舊 ④ 必須無條件渲染 T7**（擋 M-GATE-1）。
    #     只驗「有沒有被呼叫」不夠：包一層恆假的 `if` 一樣叫「被呼叫」。
    _t7_names = {_a.asname or _a.name for _n in _ast.walk(_otree)
                 if isinstance(_n, _ast.ImportFrom)
                 for _a in _n.names if _a.name == "render_t7_section"}
    _t7_calls = [_n for _n in _ast.walk(_otree)
                 if isinstance(_n, _ast.Call)
                 and getattr(_n.func, "id", None) in _t7_names]
    assert _t7_calls, f"{_old.name} 沒有呼叫 `render_t7_section` —— 整個目的地不存在。"
    for _c in _t7_calls:
        _ifs = [_n.lineno for _n in _ast.walk(_otree)
                if isinstance(_n, (_ast.If, _ast.While))
                and _n.lineno <= _c.lineno <= (_n.end_lineno or 0)]
        assert not _ifs, (
            f"{_old.name}:{_c.lineno} 的 `render_t7_section()` 被包進條件式了"
            f"（第 {_ifs} 行）—— 那代表 T7 可能整段不渲染，而本頁把使用者指過去。\n"
            "⛔ 若那個條件是刻意的，指路必須跟著它走（就像本格對 `_loaded` 做的那樣），"
            "不是把本條拿掉。")

    # (h) 那個 expander 必須 `expanded=True`（擋 M-GATE-2）。
    #     ⚠️ 收合起來**不算死指路**（使用者點得開），但本頁**在註解裡拿它當挑選理由之一**——
    #        既然引用了它，就要釘住它；理由消失時要當場知道，而不是讓一句過期的理由留著。
    _exp = [_n for _n in _ast.walk(_ltree)
            if isinstance(_n, _ast.Call)
            and getattr(_n.func, "attr", None) == "expander"
            and _n.args and isinstance(_n.args[0], _ast.Constant)
            and "編輯持倉" in str(_n.args[0].value)]
    assert _exp, (
        f"{_led.name} 找不到「✏️ 編輯持倉」那個收合區 —— 金額輸入格就住在它裡面。")
    for _e in _exp:
        _kw = {_k.arg: _ast.unparse(_k.value) for _k in _e.keywords}
        assert _kw.get("expanded") == "True", (
            f"「編輯持倉」改成 `expanded={_kw.get('expanded')}` 了 —— "
            "本頁的就地註解把「預設展開」列為挑這條指路的理由之一，"
            "理由變了就要一起改（或把那句理由撤掉），不是讓它留著過期。")


def test_the_delete_pointer_is_not_a_dead_end():
    """⭐ **失敗卡說「要刪只能到舊 ④」，那裡就真的要刪得掉。**

    本頁的失敗卡（:func:`_render_pending_notice`）逐字告訴使用者：這一頁改不了、
    也刪不掉，要移掉錯的那一筆只能到 `where_to_find('pf_add')` 用該列的 🗑️。
    **那句話是本批寫的，所以本批要為它負責。**

    ⚠️ 驗的是**那顆鈕真的會刪**（`portfolio_funds.pop(...)`），不是「有一顆 🗑️」——
    一顆不會刪東西的垃圾桶圖示，比不提還糟。

    ⚠️ **key 是 f-string**（`f"del_pf_{i}"`，逐列產生），所以走
    :func:`_button_keys` 取常數前綴；只收 `ast.Constant` 會**一顆都收不到**。

    ⛔ **紅了要做什麼**：舊 ④ 若把刪除搬走了，正解是改失敗卡那句指路指到新家；
       若是**整個不見了**（舊 ④ 被拔），那代表全站再也沒有地方能刪掉一筆加錯的標的
       —— 那是**必須先解決的斷點**，不是一條可以刪掉的測試。
    """
    _old = ROOT / "ui" / "tab3_portfolio.py"
    _tree = ast.parse(_old.read_text(encoding="utf-8"))

    assert "del_pf_" in _button_keys(_tree), (
        f"{_old.name} 裡找不到逐列的刪除鈕（`key=f\"del_pf_{{i}}\"`）—— "
        "而本頁的失敗卡告訴使用者「要刪只能去那裡」。")

    _pops = [ast.unparse(_n) for _n in ast.walk(_tree)
             if isinstance(_n, ast.Call)
             and getattr(_n.func, "attr", None) == "pop"
             and "portfolio_funds" in ast.unparse(_n)]
    assert _pops, (
        f"{_old.name} 有刪除鈕、卻沒有任何 `portfolio_funds.pop(...)` —— "
        "那顆 🗑️ 不會真的刪掉東西，而本頁正把使用者指過去。")


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
                # ⭐ **2026-09-08 第二輪：射程多收 `_status_tiles`（獨立稽核指出的缺口）。**
                #    稽核往 `_status_tiles` 塞了 5 個違禁詞，**92 條測試無一抓到** ——
                #    那四格的 `missing` 文案**是會印在畫面上的字**，卻不在任何一條
                #    內部語言守衛的射程內。這是**既有守衛的射程缺口**（不是本批造成的），
                #    但本批正好在改那四格的文案，依 `CLAUDE.md §-1.5.1c 判定 3`
                #    屬「本次弄到的東西」的收尾義務 —— 故就地補上。
                #    ⚠️ **這是把射程放大，不是放寬**：收進來的字只會**多**紅、不會少紅。
                #    ⚠️ **仍然看不到的**：`_status_tiles` 的 `label` 走的是模組層常數
                #    （`STATUS_*_LABEL`），那些常數的**定義處不在本清單裡** ——
                #    也就是把違禁詞寫進那幾個常數，本條照樣抓不到。**據實登記，不假裝全守住。**
                and _fn.name in ("_render_add_fund", "_render_add_result",
                                 "_render_pending_notice", "_render_no_holdings",
                                 "_status_tiles")):
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
