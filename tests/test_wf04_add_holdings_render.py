"""④ 新頁寫入入口的**渲染**守衛 —— 需要 AppTest，故與純函式那半分開放。

⛔ **為什麼是獨立一個檔案**（不是 `tests/test_wf04_add_holdings.py` 的第三段）：
`pytest.importorskip` 是**模組級**的。把它寫在同一個檔案中間，沒有 streamlit 時
**整個檔案**都會被 skip —— 連那些根本不需要 streamlit 的純函式斷言也一起不跑，
而「那些邊界在沒有 streamlit 的環境也跑得到」正是把它們抽成純函式的全部理由。

⚠️ **skip 不是通過。** 本檔在沒有 streamlit 的環境會整段 skip；
PR 描述已逐條寫明哪些是實跑過的、哪些沒有（`CLAUDE.md §-2` 規則 6）。

本檔守的是客戶 2026-09-08 拍板那句話的**行為面**：
> 「加入基金入口：拍板整合至 ⑨「保單與扣款標的」，**無持倉時直接就地展開輸入表單**。」

純函式那一半（解析／去重／`loaded=False` 的語意）在
`tests/test_wf04_add_holdings.py`。**兩檔合起來才完整。**
"""

from __future__ import annotations

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
)

pytest.importorskip("streamlit.testing.v1", reason="streamlit < 1.28 不支援 AppTest")

from streamlit.testing.v1 import AppTest  # noqa: E402

# ⚠️ **共用同一支容器堆疊清理**，不在這裡抄第二份 ——
#    那支 helper 的長註記載了一次跨檔污染的完整機制（2026-09-05），
#    抄一份等於讓兩份各自過期。
from test_wf04_portfolio_skeleton import (  # noqa: E402
    _reset_streamlit_container_stack,
)

from ui.helpers.render_state import NOT_READY_MARK  # noqa: E402
from ui.helpers.story_nav import where_to_find  # noqa: E402
from ui.views.page_04_portfolio import (  # noqa: E402
    ADD_FUND_HEADING,
    ADD_SUBMIT_LABEL,
    BLOCK_POLICY,
    EMPTY_TITLE_NONE,
    EMPTY_TITLE_PENDING,
    invested_hint,
    STATUS_INVESTED_LABEL,
)

_SCRIPT = (
    f"import sys; sys.path.insert(0, {str(ROOT)!r})\n"
    "from ui.views.page_04_portfolio import render_asset_allocation\n"
    "render_asset_allocation()\n"
)


def _app(funds: list[dict[str, Any]] | None) -> Any:
    _reset_streamlit_container_stack()
    _at = AppTest.from_string(_SCRIPT, default_timeout=120)
    if funds is not None:
        _at.session_state["portfolio_funds"] = funds
    try:
        _at.run()
    finally:
        _reset_streamlit_container_stack()
    assert not _at.exception, (
        "整頁渲染時拋了未捕捉例外：\n"
        + "\n".join(str(_e.value) for _e in _at.exception))
    return _at


def _rerun(at: Any) -> Any:
    _reset_streamlit_container_stack()
    try:
        at.run()
    finally:
        _reset_streamlit_container_stack()
    return at


def _flat(node: Any) -> list[str]:
    """把元素樹壓成有序的一串字（形狀同 `test_wf04_portfolio_skeleton._flat`）。"""
    _out: list[str] = []
    _ch = getattr(node, "children", None)
    if not isinstance(_ch, dict):
        return _out
    for _, _c in sorted(_ch.items()):
        _t = type(_c).__name__
        _v = getattr(_c, "value", None)
        _lbl = getattr(_c, "label", None)
        if _t in ("Markdown", "Caption", "Text", "Header", "Subheader",
                  "Title", "Code", "Info", "Warning", "Error", "Success"):
            _out.append(f"[{_t}] {_v}")
        elif _lbl is not None:
            _out.append(f"[{_t}] {_lbl}")
        else:
            _out.append(f"[{_t}]")
        _out.extend(_flat(_c))
    return _out


def _text(at: Any) -> str:
    return "\n".join(_flat(at.main))


def _add(at: Any, codes: str, policy_id: str = "") -> Any:
    """在頁面上**真的**填一次、按一次。回傳同一個 `AppTest`。"""
    at.text_area[0].set_value(codes)
    if policy_id:
        at.text_input[0].set_value(policy_id)
    # ⚠️ 送出鈕用**標籤**找，不用索引 —— 索引會隨版面順序漂移，
    #    而版面順序本來就是別的守衛在管的東西。
    _btns = [_b for _b in at.button if _b.label == ADD_SUBMIT_LABEL]
    assert len(_btns) == 1, (
        f"畫面上叫「{ADD_SUBMIT_LABEL}」的按鈕有 {len(_btns)} 顆，預期恰好 1 顆。")
    _btns[0].click()
    return _rerun(at)


def test_the_form_is_on_screen_when_there_are_no_holdings_at_all():
    """⭐ **客戶逐字：「無持倉時直接就地展開輸入表單」。**

    在此之前 `render_asset_allocation()` 在沒有持倉時 early return，
    **連表單都不畫** —— 而它印的那句空狀態指向舊 ④，舊 ④ 一拔就是死路。
    """
    for _funds in ([], None):
        _at = _app(_funds)
        _all = _text(_at)
        assert BLOCK_POLICY in _all, (
            "沒有持倉時，客戶點名要就地展開的那一塊沒有畫出來。\n" + _all)
        assert ADD_FUND_HEADING in _all, "加入區的抬頭不在畫面上。\n" + _all
        assert [_b.label for _b in _at.button] == [ADD_SUBMIT_LABEL], (
            "沒有持倉時畫面上的按鈕不是「恰好一顆加入鈕」："
            f"{[_b.label for _b in _at.button]}")
        assert len(_at.text_area) == 1 and len(_at.text_input) == 1, (
            "加入表單的兩個欄位沒有都畫出來。")
        # ⛔ 沒有持倉時**不畫**四格狀態列與空表 —— 鐵則 04。
        assert STATUS_INVESTED_LABEL not in _all, (
            "一筆標的都沒有時還畫了狀態列 —— 四個「不知道」是冗餘占位（鐵則 04）。\n"
            + _all)


def test_submitting_the_form_really_writes_into_portfolio_funds():
    """⭐ **按下去，`portfolio_funds` 裡真的多了那幾筆。**

    這是本批的核心：在此之前新五頁寫進這個鍵的呼叫點是 **0 個**。
    """
    _at = _add(_app([]), "0050\n0056,我的保單")
    _funds = _at.session_state["portfolio_funds"]
    assert [(_f["code"], _f["policy_id"]) for _f in _funds] == [
        ("0050", ""), ("0056", "我的保單")], f"寫進去的東西不對：{_funds}"
    assert all(_f["loaded"] is NEW_ENTRY_LOADED for _f in _funds), (
        "寫進去的條目被標成已載入 —— 這一頁沒有抓任何資料。")
    assert all(_f["invest_twd"] == NEW_ENTRY_INVEST_TWD for _f in _funds)


def test_the_page_says_the_new_rows_have_no_nav_yet():
    """⭐ 加完之後，畫面要**講出來**還差一步，並且**給得出下一步**。

    ⛔ 這一條擋的是最容易犯的那個錯：加完了，畫面卻還在說「尚未設定持倉」——
       使用者剛剛才加過，那句話是錯的，而且會讓他再加一次。
    """
    _at = _add(_app([]), "0050\n0056")
    _all = _text(_at)
    assert EMPTY_TITLE_NONE not in _all, (
        "剛加完，畫面還在說「尚未設定持倉」。\n" + _all)
    assert EMPTY_TITLE_PENDING in _all, (
        "加完之後沒有講出「有標的了，但還沒有淨值」這個處境。\n" + _all)
    assert where_to_find("pf_load") in _all, (
        "講了缺什麼，卻沒有講去哪補 —— 空狀態三要素少一項（鐵則 04）。\n" + _all)
    assert where_to_find("pf_add") not in _all, (
        "還在把使用者指回舊 ④ 的「加入與管理基金」—— 他已經有基金了，"
        "那句話是錯的。\n" + _all)
    # 加進去的兩檔要出現在保單一覽裡（不是加了卻看不到）。
    assert BLOCK_POLICY in _all


def test_a_book_full_of_unloaded_rows_is_not_called_empty():
    """⭐ **雲端讀回／JSON 還原之後那個坑** —— 清單裡有十幾檔，畫面卻說「尚未設定」。

    `sync_policies_to_portfolio_funds` 與 `json_backup` 寫進來的都是
    `loaded=False` 骨架，而 `_holdings()` 會把它們濾掉。
    在此之前這一頁只會說「還沒有任何已載入的保單或扣款標的」＋指去舊 ④ ——
    **他已經有基金了**，照著做只會加出重複的一筆。
    """
    _at = _app([{"code": "AAA", "policy_id": "保單甲", "loaded": False,
                 "load_error": None},
                {"code": "BBB", "policy_id": "保單甲", "loaded": False,
                 "load_error": None}])
    _all = _text(_at)
    assert EMPTY_TITLE_NONE not in _all, (
        "清單裡明明有兩檔，畫面卻說「尚未設定持倉」。\n" + _all)
    assert EMPTY_TITLE_PENDING in _all, "沒有講出真正的處境。\n" + _all
    assert where_to_find("pf_load") in _all, "沒有給下一步。\n" + _all
    assert where_to_find("pf_add") not in _all, (
        "把已經有基金的人指去「加入基金」—— 那句話是錯的。\n" + _all)
    # 它們要出現在保單一覽裡，而且範圍說明要講明沒被算進總投入。
    assert "AAA" in _all and "BBB" in _all, (
        "已列入的標的沒有出現在保單一覽裡。\n" + _all)


def test_a_failed_row_is_not_painted_grey():
    """⛔ **抓過、失敗了的那幾檔不得用灰字印。**

    `ui/helpers/render_state.py` 的五態表逐字：「真正的失敗（抓取／渲染／模組載入）
    如果用灰字印，畫面看起來只是『還沒載入』—— 使用者會以為按一下就好，
    **實際按幾次都一樣**。」

    本條驗兩件事：(a) 失敗的原因**有講出來**；(b) 那句話**不是**灰態。
    """
    _at = _app([{"code": "GOODONE", "name": "好的", "loaded": True},
                {"code": "BADONE", "loaded": True, "load_error": "404 找不到"}])
    _parts = _flat(_at.main)
    _all = "\n".join(_parts)
    assert "404 找不到" in _all, (
        "抓取失敗的原因沒有出現在畫面上 —— 使用者只會看到那一列是空的。\n" + _all)
    _grey_with_code = [_p for _p in _parts
                       if NOT_READY_MARK in _p and "BADONE" in _p]
    assert not _grey_with_code, (
        "抓取失敗被畫成灰態了 —— 使用者會以為按一下載入就好，實際按幾次都一樣：\n  "
        + "\n  ".join(_grey_with_code))


def test_a_duplicate_submit_adds_nothing_and_says_so():
    """同一個代碼再送一次 → 不重複加，**而且畫面要講**（§1：不靜默吞）。"""
    _at = _add(_app([]), "0050")
    _at = _add(_at, "0050")
    assert [_f["code"] for _f in _at.session_state["portfolio_funds"]] == ["0050"], (
        "重複的代碼被加了第二筆。")
    assert "0050" in _text(_at)


def test_an_unreadable_line_is_reported_on_screen():
    """讀不懂的行要在畫面上講，而且要講**怎麼改**。"""
    _at = _add(_app([]), "0050\n,只有保單")
    _all = _text(_at)
    assert [_f["code"] for _f in _at.session_state["portfolio_funds"]] == ["0050"]
    assert "只有保單" in _all, (
        "讀不懂的那一行被靜靜吃掉了 —— 使用者不知道他打的東西怎麼了。\n" + _all)


def test_the_confirmation_does_not_stay_on_screen_forever():
    """確認訊息**只顯示一次** —— 留著不走會被讀成「我剛剛又加了一次」。"""
    _at = _add(_app([]), "0050")
    assert "已加入 1 檔" in _text(_at)
    _rerun(_at)
    assert "已加入 1 檔" not in _text(_at), (
        "上一次的確認訊息還留在畫面上。")


def test_a_list_of_only_failed_rows_does_not_tell_him_to_press_load():
    """⭐ **「全部都抓失敗」時，不得叫使用者去按載入** —— 按下去什麼都不會發生。

    ## 這是實跑抓到的一個錯，不是假想

    本頁第一版的空狀態**無條件**指去 `where_to_find('pf_load')`。
    但 `ui/helpers/portfolio/load.py::batch_load_unloaded_funds()` 只挑
    **`loaded` 為假**的那幾筆；抓過而失敗的是 `loaded=True` ＋ `load_error`，
    **它根本不會碰**。也就是那句指路描述的動作，對這個情況完全無效 ——
    正是 `ui/helpers/render_state.py` 五態表警告的
    「使用者會以為按一下就好，**實際按幾次都一樣**」。
    """
    _at = _app([{"code": "BADONE", "loaded": True, "load_error": "連線逾時"}])
    _all = _text(_at)
    assert EMPTY_TITLE_PENDING in _all, "沒有講出真正的處境。\n" + _all
    assert where_to_find("pf_load") not in _all, (
        "全部都抓失敗，畫面卻叫使用者去按載入 —— 那顆按鈕不會碰這幾筆。\n" + _all)
    assert "連線逾時" in _all, "抓不到的原因沒有出現在畫面上。\n" + _all


def test_a_list_that_is_added_but_not_fetched_says_neither_of_the_two_wrong_things():
    """⭐ **「加了但還沒抓到」那個狀態，畫面上兩句話都不准出現。**

    ## 這條守的是**呼叫端餵錯資料**，不是那個純函式

    第四輪獨立稽核在 `_status_tiles` 的**呼叫處**做了兩顆單 token 突變，
    **24 條 streamlit-free 守衛與本檔既有的兩條渲染斷言全部綠燈**，而畫面上：

    - ``n_loaded=len(_loaded)`` → ``len(_all)``：畫面說「**已載入的**標的都沒有填投入
      金額」＋ 指 `pf_ledger`，**而同一畫面下一行寫著「只加已載入的 0 檔」** ——
      這正是第三輪獨立稽核擋下的那個 bug，逐字重現。
    - ``pending_split(session[…])`` → ``pending_split(_loaded)``：畫面說
      「**一檔標的都還沒有**」，**而下一行寫著「另有 2 檔尚未載入或載入失敗」**。

    **兩顆都是餵錯資料，不是那個函式算錯。** 所以擋它們的斷言必須看**畫面**。

    ## 為什麼是這兩句話

    這個狀態下 `_holdings()` 是空的、清單卻非空，所以：

    - `pf_ledger`（T7「✏️ 編輯持倉」）**在這個狀態下不渲染**（閘門 `fund_is_usable`），
      指過去是死路 —— **第三輪擋下的就是它**；
    - :data:`EMPTY_TITLE_NONE`（「還沒有任何保單或扣款標的」）**是假的** ——
      使用者剛加過，清單裡有兩檔，照著做只會加出重複的一筆。

    ⚠️ **本條不重複驗那個純函式**（那是 `tests/test_wf04_add_holdings.py` 的真值表
    與 `test_the_call_site_feeds_invested_hint_the_right_three_numbers` 的工作）。
    **它只驗這個狀態下畫面說的是不是對的那一句。**

    ## ⛔ 本條有**兩組**斷言，**缺一不可，兩組都不得刪除**

    ⚠️ **2026-09-08 第五輪就地更正（有意識的更正，不是漏刪 · 依第四輪稽核 R-A）**：
    ~~稽核建議的那條斷言（`EMPTY_TITLE_NONE` 不得出現）只殺得掉一半，本組實測後**換掉了**。~~

    **上面那句話有兩個錯，而且第二個有害**：
    1. **「只殺得掉一半」對，但只講了一半的一半。** 本組實測 M11 之下稽核那條確實 GREEN；
       **但沒有去看反方向** —— **M20**（同型餵錯，打在 :func:`_render_no_holdings` 上：
       ``pending_split(_holdings())``）之下，**只有稽核那條會紅，本組新加的 SSOT 斷言全部 PASS**。
       **兩組互不涵蓋。**
    2. ⛔ **「換掉了」根本不是事實** —— 稽核那兩個半句**在出貨的程式碼裡原封都在**（見下）。
       本組做的是**純新增**，**嚴格變強**。
       **那句「換掉」如果留著，會誘導下一個人去刪掉唯一擋得住 M20 的那條斷言。**

    ### 兩組各自守什麼（實測，逐樹比對）

    ==================== ================== ================== ==================
    突變                  稽核那兩個半句       本組的 SSOT 斷言      擋得住嗎
    ==================== ================== ================== ==================
    **M10**（`n_loaded`）  RED（`pf_ledger`）  **RED**             ✅ 兩組都抓到
    **M11**（`_status_tiles` 餵錯） GREEN（盲）  **RED**            ✅ **只有本組這條**
    **M20**（`_render_no_holdings` 餵錯） **RED**  GREEN（盲）      ✅ **只有稽核那兩句**
    ==================== ================== ================== ==================

    ⛔⛔ **`EMPTY_TITLE_PENDING in _all` 與 `EMPTY_TITLE_NONE not in _all` 兩條不得刪除。**
    它們守的是 :func:`_render_no_holdings`（空狀態那一支）——
    **本檔其餘任何斷言都看不到那裡。** 刪掉它們，M20 那一整類（畫面說「還沒有任何保單」，
    而清單裡明明有兩檔）就沒有人擋。
    ⛔⛔ **本組的 `_want_missing` / `_want_where` 兩條同樣不得刪除。**
    它們守的是 :func:`_status_tiles`（💰 那一格）—— 稽核那兩句看不到那裡。

    ## 本組新增的那組：**問 SSOT 這個狀態該說哪一句，然後要求畫面上真的是那一句**

    不硬抄任何文案 —— 直接呼叫 :func:`invested_hint`（產品自己那支）算出
    「0 已載入 / 2 還沒抓 / 0 失敗」該說什麼，再確認畫面上就是它。
    **餵錯任何一個數字，渲染出來的就會是別支的句子 ⇒ 當場紅。**
    """
    _at = _app([{"code": "0050", "loaded": False, "load_error": None},
                {"code": "0056", "loaded": False, "load_error": None}])
    _all = _text(_at)

    # ══════════════════════════════════════════════════════════════════════
    # ⛔⛔ 【第 1 組｜守 `_render_no_holdings`】**這兩條不得刪除。**
    #     它們是**唯一**擋得住 M20 的東西（`_render_no_holdings` 被餵過濾後的清單
    #     → `_pending_n` 變 0 → 畫面說「還沒有任何保單或扣款標的」，
    #     而清單裡明明有兩檔）。**下面第 2 組對 M20 全部 PASS，看不到它。**
    #     ⚠️ 本檔上一版的 docstring 曾說這兩條「被換掉了」—— **那是假的，它們一直都在**，
    #        而那句話會誘導人來刪它們。已就地更正，理由見 docstring 的對照表。
    # ══════════════════════════════════════════════════════════════════════
    assert EMPTY_TITLE_PENDING in _all, (
        "沒有講出「東西有了、資料還沒抓回來」這個處境。\n" + _all)
    assert EMPTY_TITLE_NONE not in _all, (
        "清單裡明明有兩檔，畫面卻說「還沒有任何保單或扣款標的」。\n"
        "⛔ M20（`_render_no_holdings` 餵錯資料）就是這個症狀，**只有本條抓得到**。\n"
        + _all)

    # ══════════════════════════════════════════════════════════════════════
    # ⛔⛔ 【第 2 組｜守 `_status_tiles` 的 💰 那一格】**這兩條同樣不得刪除。**
    #     它們是**唯一**擋得住 M11 的東西（`_status_tiles` 被餵過濾後的清單）。
    #     **上面第 1 組對 M11 全部 PASS，看不到它。**
    # ══════════════════════════════════════════════════════════════════════
    # ⭐ 這一組測資是 2 檔、都沒抓過 ⇒ 正解必然是「還沒抓過淨值」那一支。
    _want_missing, _want_where = invested_hint(n_loaded=0, n_waiting=2, n_failed=0)
    assert _want_missing in _all, (
        f"💰 那格說的不是這個狀態該說的話。應該要有：\n  {_want_missing}\n"
        "⛔ 稽核的兩顆呼叫端突變都會在這裡紅：\n"
        "   · M10 `n_loaded=len(_all)` → 畫面改說「**已載入的**標的都沒有填投入金額」，"
        "而同一畫面下一行寫著「只加已載入的 **0** 檔」；\n"
        "   · M11 `pending_split(_loaded)` → 畫面改說「**一檔標的都還沒有**」，"
        "而下一行寫著「另有 **2** 檔尚未載入或載入失敗」。\n" + _all)
    assert _want_where in _all, (
        f"💰 那格的「去哪補」不是 {_want_where!r}。\n" + _all)
    assert where_to_find("pf_ledger") not in _all, (
        "一檔都還沒抓到，畫面卻指去帳本的「編輯持倉」—— 那個 expander 在這個狀態"
        "**不渲染**（閘門是 `fund_is_usable`），使用者走過去只會看到「請先載入至少一檔」。\n"
        "⛔ 這是第三輪已經擋下過一次的 bug，稽核的 M10 讓它逐字重現。\n" + _all)


def test_the_failure_card_escapes_what_the_fetcher_sent_back():
    """⛔ `load_error` 是**抓取端丟回來的**字串，含 `<` `>` 時不得被當成標籤。

    `business_alert()` 走 `unsafe_allow_html` —— 不 escape 的話，
    一段含 HTML 的錯誤訊息會插進畫面結構裡（輕則原因看不見）。
    ⚠️ 同時驗**我們自己的** `<b>` 仍然是標籤：兩者都 escape 就變成畫面上一堆角括號。
    """
    _at = _app([{"code": "BAD<1>", "loaded": True, "load_error": "404 <b>x</b>"}])
    _card = [_p for _p in _flat(_at.main) if "border-left" in _p and "抓不到淨值" in _p]
    assert _card, "失敗卡沒有畫出來。"
    assert "&lt;b&gt;" in _card[0], "抓取端丟回來的 HTML 沒有被跳脫。"
    assert "<b>BAD&lt;1&gt;</b>" in _card[0], (
        "代碼沒有被跳脫，或我們自己的 `<b>` 被一起跳脫掉了。")
