"""IA kit 守衛 —— 四大鐵則的共用元件 ＋ 五分頁骨架的職責對齊。

對應：2026-09-01 客戶拍板線框 `docs/wireframes/ia-wireframe.html`（五分頁動線重構）。

⚠️ **本檔刻意不重複既有的漂移鎖**（`CLAUDE.md §2.1` SSOT：同一件事只准守一次）。
分頁的**數量／順序／key／名稱**在本批之前就已經有三道鎖，本檔一條都不重寫：

===================================== ====================================
既有鎖                                  它鎖的東西
===================================== ====================================
`test_wpf_five_tab_wiring.py::`         `app.py` 的 `st.tabs` 只有一個、
`test_all_five_slots_go_through_tab_label`  剛好 5 個 slot、key 與**順序**正確、
                                        且五個都走 `tab_label()` 不寫死字面值
`test_story_nav.py::`                   `_TAB_LABELS` 的 key 與**順序**
`test_tab_labels_are_exactly_the_five_top_level_tabs`
`test_tab_label_wiring.py::`            五個**名稱字串**的逐字值
`test_strips_ordinal_prefix`            （改名必轉紅 —— 2026-09-01 實際轉紅過）
===================================== ====================================

**本檔只補它們沒有覆蓋的那一個缺口**：**每個分頁 slot 呼叫的 render 函式對不對**。
上面三道鎖合起來能保證「五個分頁、名字對、順序對」，但**不能**保證
`with tab_health:` 裡面跑的不是 `render_macro_tab()` ——
分頁名與內容互換是一種**測試全綠、畫面全錯**的漂移，見 `test_each_tab_slot_calls_its_own_render`。

⚠️ **本檔全部由前端／架構組單組產出，未經第二組獨立複驗**（`CLAUDE.md §-2` 規則 6）。
   突變結果逐條記在 PR 描述，**不在這裡自我宣稱**。
"""
from __future__ import annotations

import ast
import pathlib
import re
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
IA_DIR = ROOT / "ui" / "helpers" / "ia"

from ui.helpers.ia import (  # noqa: E402
    APPLY_LABEL,
    CARD_STATES,
    GRID_COLS,
    FormGate,
    card_row,
    render_cards,
    STATE_BUSINESS,
    STATE_ERROR,
    STATE_NOT_READY,
    STATE_OK,
    applied_form,
    card_grid,
    empty_state,
    state_card,
    wide_table,
)


def _fake_columns(n):
    """`st.columns` 替身：回**真的 list**（MagicMock 不可迭代，會讓 extend 炸）。"""
    return [MagicMock(name=f"col{i}") for i in range(n)]


# ══════════════════════════════════════════════════════════════════
# 鐵則 01 —— 三欄自適應網格
# ══════════════════════════════════════════════════════════════════
def test_grid_cols_is_three():
    """桌面欄數 = 3，且是**具名常數**（§3.3 反捏造：不准在各分頁 inline `3`）。

    改這個值等於改客戶拍板的版面 → 屬客戶 gate，不是實作細節。
    """
    assert GRID_COLS == 3


def test_card_grid_gives_one_column_per_item_and_keeps_column_width_stable():
    """`card_grid(n)` 回 n 個欄位；每一列都開滿 `GRID_COLS` 欄再取用。

    「開滿再取」不是實作細節，是版面要求：最後一列只剩 2 個項目時，
    若只開 2 欄，那兩張卡會各佔半頁、與上面幾列對不齊。
    """
    with patch("streamlit.columns", side_effect=_fake_columns) as _cols:
        _out = card_grid(5)
    assert len(_out) == 5, "回傳欄位數必須與項目數一致"
    # 5 個項目 → 兩列（3 + 2），兩次都必須開滿 3 欄
    assert [c.args[0] for c in _cols.call_args_list] == [GRID_COLS, GRID_COLS]


def test_card_row_opens_exactly_the_client_grid_width():
    """`card_row()` 預設必須開**恰好 `GRID_COLS`** 欄，並把那幾欄交出去。

    ⚠️ **本條是 2026-09-01 稽核抓到的缺口，補的**：在此之前 `card_row` 被
    `tests/test_ui_grid_contract.py` 的 `GRID_EXEMPT_SITES` **豁免**掉，
    自己卻**一條斷言都沒有** —— 稽核實測把預設值改成 2，全 suite `6350 passed`
    逐字不變、零反應。那正是該契約 docstring 警告的
    「一個 `_grid3()` helper 一秒繞過」，而且**下面沒有網**。
    （突變 A2-M1：預設值 3 → 2 必須轉紅。）
    """
    with patch("streamlit.columns", side_effect=_fake_columns) as _cols:
        with card_row() as _row:
            pass
    _cols.assert_called_once_with(GRID_COLS)
    assert len(_row) == GRID_COLS


def test_card_row_hands_back_the_real_columns():
    """yield 出去的必須是 `st.columns()` 回傳的那些物件本身（不是複本／不是空殼）。"""
    _made = []

    def _spy(n):
        _made.append(_fake_columns(n))
        return _made[-1]

    with patch("streamlit.columns", side_effect=_spy):
        with card_row() as _row:
            pass
    assert list(_row) == _made[0]


def test_card_grid_empty_draws_nothing():
    """0 個項目 → 不開任何欄（鐵則 04：不留冗餘占位）。"""
    with patch("streamlit.columns", side_effect=_fake_columns) as _cols:
        assert card_grid(0) == []
    _cols.assert_not_called()


# ══════════════════════════════════════════════════════════════════
# 鐵則 01（下半）＋ 鐵則 04 —— 大表全寬 ／ 空資料不畫空框
# ══════════════════════════════════════════════════════════════════
def test_wide_table_is_full_width():
    """大表必須全寬（`use_container_width=True`）才會有橫向捲動而不是被壓扁。"""
    _df = pd.DataFrame({"a": [1], "b": [2]})
    with patch("streamlit.dataframe") as _dfw:
        assert wide_table(_df) is True
    assert _dfw.call_args.kwargs.get("use_container_width") is True


def test_wide_table_empty_never_draws_an_empty_frame():
    """空資料 → 走空狀態，**絕不呼叫 `st.dataframe`**（鐵則 04 的機械化）。

    這是本檔最有價值的一條：`st.dataframe(空 df)` 的**預設行為就是畫一個空框**，
    所以這條規則若只寫在文件裡，等於沒有。
    """
    with patch("streamlit.dataframe") as _dfw, \
            patch("ui.helpers.ia.empty_state.empty_state") as _es:
        assert wide_table(pd.DataFrame(), empty_title="尚未設定持倉",
                          empty_missing="還沒有任何保單或扣款標的",
                          empty_where="④ 資產配置 › 保單與扣款標的") is False
    _dfw.assert_not_called()
    _es.assert_called_once()


def test_wide_table_refuses_empty_without_the_three_elements():
    """空資料卻沒給空狀態標題 → **fail loud**，不得靜默畫框（§1）。"""
    with pytest.raises(ValueError, match="empty_title"):
        wide_table(pd.DataFrame())


@pytest.mark.parametrize("empty_value", [None, [], {}, pd.DataFrame()])
def test_wide_table_recognises_every_empty_shape(empty_value):
    """`None` / 空 list / 空 dict / 空 DataFrame 都算空。

    刻意不用 `if not data:` —— DataFrame 的 `__bool__` 會拋
    `ValueError: truth value ... is ambiguous`，那會變成一個假的系統紅燈。
    """
    with pytest.raises(ValueError, match="empty_title"):
        wide_table(empty_value)


# ══════════════════════════════════════════════════════════════════
# 鐵則 02 —— Form 封裝防重繪
# ══════════════════════════════════════════════════════════════════
def test_gate_is_false_inside_the_block_and_reflects_submit_after_it():
    """`gate` 在 `with` 區塊內恆為 False，離開後才帶出送出結果。

    這是 `st.form` 的硬限制（送出鈕必須排在所有 widget 之後），
    釘住它是為了讓「在區塊內判斷」這個寫錯法有測試會擋，而不是靠讀 docstring。
    """
    _seen_inside = []
    with patch("streamlit.form", return_value=MagicMock()), \
            patch("streamlit.form_submit_button", return_value=True):
        with applied_form("k") as _gate:
            _seen_inside.append(bool(_gate))
    assert _seen_inside == [False], "區塊內不該已經是 True"
    assert bool(_gate) is True, "離開區塊後應反映送出結果"


def test_gate_is_false_when_not_submitted():
    """沒按送出 → gate 為 False，呼叫端就不會跑重運算（這條規則的全部意義）。"""
    with patch("streamlit.form", return_value=MagicMock()), \
            patch("streamlit.form_submit_button", return_value=False):
        with applied_form("k") as _gate:
            pass
    assert bool(_gate) is False


def test_submit_button_is_created_after_the_widgets():
    """送出鈕必須在使用者 widget **之後**建立，否則 Streamlit 會把它排到最上面。"""
    _order: list[str] = []
    with patch("streamlit.form", return_value=MagicMock()), \
            patch("streamlit.form_submit_button",
                  side_effect=lambda *a, **k: _order.append("submit") or True), \
            patch("streamlit.slider",
                  side_effect=lambda *a, **k: _order.append("slider")):
        import streamlit as st
        with applied_form("k"):
            st.slider("輪動門檻 σ")
    assert _order == ["slider", "submit"]


def test_default_submit_label_is_the_wireframe_wording():
    """線框 Tab 02 的送出鈕就是「套用」——具名常數，不在各分頁各抄一份。"""
    assert APPLY_LABEL == "套用"
    with patch("streamlit.form", return_value=MagicMock()), \
            patch("streamlit.form_submit_button", return_value=False) as _btn:
        with applied_form("k"):
            pass
    assert _btn.call_args.args[0] == APPLY_LABEL


def test_form_does_not_swallow_exceptions():
    """區塊內拋例外照常往上傳（§1 不吞例外），且不會留一個按了沒反應的鈕。"""
    with patch("streamlit.form", return_value=MagicMock()), \
            patch("streamlit.form_submit_button") as _btn:
        with pytest.raises(RuntimeError):
            with applied_form("k"):
                raise RuntimeError("boom")
    _btn.assert_not_called()


# ══════════════════════════════════════════════════════════════════
# 鐵則 03 —— 三態必須是三個不同的視覺（不是三種文案）
# ══════════════════════════════════════════════════════════════════
def _delegate_used(state: str, **kw) -> str:
    """跑一次 `state_card`，回報它實際委派給哪一個渲染入口。"""
    with patch("ui.helpers.ia.cards.not_ready") as _nr, \
            patch("ui.helpers.ia.cards.business_alert") as _ba, \
            patch("ui.helpers.ia.cards.system_error") as _se, \
            patch("streamlit.metric") as _mt, \
            patch("streamlit.markdown"), patch("streamlit.caption"):
        state_card("標題", "值", "說明", state=state, **kw)
        _hits = [_n for _n, _m in (("not_ready", _nr), ("business_alert", _ba),
                                   ("system_error", _se), ("metric", _mt))
                 if _m.called]
    assert len(_hits) == 1, f"state={state} 命中 {_hits}，應恰好一個渲染入口"
    return _hits[0]


def test_three_states_are_three_different_widgets():
    """**本檔的核心條**：四個狀態必須走**四個不同**的渲染入口。

    客戶鐵則 03 要的是「三態是三個不同的**視覺**」。若有人把業務警示改成
    `system_error`，顏色會從莓紅變成系統紅 —— 畫面上仍然「有東西」、
    文案也還在，**只有顏色的語意壞掉**，而顏色正是這條規則的全部內容。
    本條讓那種改動直接轉紅。
    """
    _used = {
        STATE_OK: _delegate_used(STATE_OK),
        STATE_NOT_READY: _delegate_used(STATE_NOT_READY),
        STATE_BUSINESS: _delegate_used(STATE_BUSINESS),
        STATE_ERROR: _delegate_used(STATE_ERROR, exc=ValueError("x")),
    }
    assert len(set(_used.values())) == len(CARD_STATES), (
        f"有狀態共用了同一個渲染入口：{_used}")


def test_states_delegate_to_the_render_state_ssot_not_a_local_copy():
    """三態的實作必須**就是** `ui/helpers/render_state.py` 那三個函式本人。

    不是「長得像」、不是「包一層」—— 用 `is` 比對物件同一性。
    有人在 `ia` 裡自己抄一份灰／莓紅／紅框，這條會轉紅。
    """
    from ui.helpers import render_state
    from ui.helpers.ia import cards
    assert cards.not_ready is render_state.not_ready
    assert cards.business_alert is render_state.business_alert
    assert cards.system_error is render_state.system_error


def test_error_state_requires_a_real_exception():
    """🔴 一定要帶例外物件 —— 沒有技術細節的紅燈只是一個紅色的猜測（§1）。"""
    with pytest.raises(TypeError, match="exc"):
        state_card("波動與信用", state=STATE_ERROR)


def test_unknown_state_fails_loud_and_does_not_default_to_ok():
    """未知狀態 → 炸掉。**預設成 OK 是最糟的降級**（壞卡長得像好卡）。"""
    with pytest.raises(ValueError, match="未知狀態"):
        state_card("x", state="looks_fine")


# ══════════════════════════════════════════════════════════════════
# 鐵則 01 × 03 的組合入口 —— render_cards
# ══════════════════════════════════════════════════════════════════
def test_render_cards_lays_cards_out_at_the_client_grid_width():
    """`render_cards()` 必須把卡片排進**三欄**網格。

    ⚠️ **本條同為 2026-09-01 稽核抓到的缺口**：稽核把 `cols or GRID_COLS`
    改成 `cols or 1`（整頁卡片塌成一欄、鐵則 01 當場失效），
    全 suite **6350 passed 零反應** —— 這個匯出符號當時一條斷言都沒有。
    （突變 A3-M1：`cols or 1` 必須轉紅。）
    """
    with patch("streamlit.columns", side_effect=_fake_columns) as _cols, \
            patch("streamlit.metric"), patch("streamlit.caption"):
        render_cards([{"title": f"卡{_i}", "value": "1"} for _i in range(3)])
    assert [c.args[0] for c in _cols.call_args_list] == [GRID_COLS]


def test_render_cards_routes_every_card_to_its_own_state():
    """每張卡都要照自己的 `state` 走對應入口 —— 不是整批用同一個視覺。"""
    with patch("streamlit.columns", side_effect=_fake_columns), \
            patch("streamlit.markdown"), patch("streamlit.caption"), \
            patch("streamlit.metric") as _mt, \
            patch("ui.helpers.ia.cards.not_ready") as _nr, \
            patch("ui.helpers.ia.cards.business_alert") as _ba:
        render_cards([
            {"title": "景氣位階", "value": "擴張中段"},
            {"title": "通膨與利率", "state": STATE_NOT_READY, "note": "未載入"},
            {"title": "波動與信用", "value": "VIX 24.1", "state": STATE_BUSINESS},
        ])
    assert _mt.call_count == 1, "OK 卡沒走 st.metric"
    assert _nr.call_count == 1, "灰卡沒走 not_ready"
    assert _ba.call_count == 1, "業務警示卡沒走 business_alert"


def test_render_cards_empty_draws_nothing():
    """空清單不畫任何東西（鐵則 04：不留冗餘占位）—— 連欄位都不該開。"""
    with patch("streamlit.columns", side_effect=_fake_columns) as _cols:
        render_cards([])
    _cols.assert_not_called()


# ══════════════════════════════════════════════════════════════════
# FormGate —— 匯出的型別，行為要有斷言（同為稽核抓到的零覆蓋符號）
# ══════════════════════════════════════════════════════════════════
def test_form_gate_is_falsy_until_submitted():
    """`if gate:` 是本套件對外承諾的用法，`__bool__` 必須跟著 `submitted` 走。"""
    _g = FormGate(key="k")
    assert bool(_g) is False and _g.submitted is False
    _g.submitted = True
    assert bool(_g) is True


def test_form_gate_defaults_carry_the_wireframe_label():
    """gate 自帶的送出字預設是「套用」，且 `extra` 是每個實例各自的 dict。"""
    _a, _b = FormGate(key="a"), FormGate(key="b")
    assert _a.submit_label == APPLY_LABEL
    _a.extra["x"] = 1
    assert _b.extra == {}, "extra 被共用了（dataclass 可變預設值的經典 bug）"


# ══════════════════════════════════════════════════════════════════
# 鐵則 04 —— 空狀態三要素
# ══════════════════════════════════════════════════════════════════
def test_empty_state_carries_all_three_elements():
    """標題自己畫、缺什麼＋去哪補**委派回 `not_ready()`**（灰態 SSOT）。"""
    with patch("streamlit.markdown") as _md, \
            patch("ui.helpers.ia.empty_state.not_ready") as _nr:
        empty_state("尚未設定持倉", "還沒有任何保單或扣款標的",
                    where="④ 資產配置 › 保單與扣款標的")
    assert "尚未設定持倉" in _md.call_args_list[0].args[0], "標題沒畫出來"
    _nr.assert_called_once_with("還沒有任何保單或扣款標的",
                                where="④ 資產配置 › 保單與扣款標的")


def test_empty_state_rejects_an_exception():
    """手上有例外 → 那是系統真出錯，不是「還沒設定」（與 `not_ready` 同源防呆）。"""
    with pytest.raises(TypeError, match="system_error"):
        empty_state("標題", ValueError("boom"))


# ══════════════════════════════════════════════════════════════════
# 套件層規範：顏色只准來自 SSOT、三態不准在這裡重做
# ══════════════════════════════════════════════════════════════════
_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")


@pytest.mark.parametrize("path", sorted(IA_DIR.glob("*.py")), ids=lambda p: p.name)
def test_ia_modules_contain_no_hex_colour_literals(path: pathlib.Path):
    """`ui/helpers/ia/` 內不得出現 hex 色碼 —— 顏色一律走 `shared.colors`（§3.3）。

    只看**會被求值的字串常數**，不看註解／docstring（註解可以講顏色的來歷）。
    """
    _tree = ast.parse(path.read_text(encoding="utf-8"))
    _docs = set()
    for _n in ast.walk(_tree):
        if isinstance(_n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                           ast.ClassDef)):
            _b = getattr(_n, "body", None)
            if (_b and isinstance(_b[0], ast.Expr)
                    and isinstance(_b[0].value, ast.Constant)
                    and isinstance(_b[0].value.value, str)):
                _docs.add(id(_b[0].value))
    _bad = [_n.value for _n in ast.walk(_tree)
            if isinstance(_n, ast.Constant) and isinstance(_n.value, str)
            and id(_n) not in _docs and _HEX.search(_n.value)]
    assert not _bad, (
        f"{path.name} 出現 hex 色碼字面值 {_bad} —— "
        "顏色請具名 import 自 shared/colors.py（同一個顏色只准定義一次）")


@pytest.mark.parametrize("path", sorted(IA_DIR.glob("*.py")), ids=lambda p: p.name)
def test_ia_modules_do_not_redefine_the_tricolor_entrypoints(path: pathlib.Path):
    """`ia` 不得自己定義 `not_ready` / `business_alert` / `system_error`。

    它們的 SSOT 是 `ui/helpers/render_state.py`。在這裡重新定義一份，
    就會出現「同一個灰色有兩個地方可以改」——本 repo 已經因為這種形狀
    出過「同一個失敗在 A 分頁是 🔴、在 B 分頁是灰字」的事故。
    """
    _tree = ast.parse(path.read_text(encoding="utf-8"))
    _owned = {"not_ready", "business_alert", "system_error"}
    _defined = {_n.name for _n in ast.walk(_tree)
                if isinstance(_n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert not (_defined & _owned), (
        f"{path.name} 重新定義了三態入口 {_defined & _owned} —— "
        "請改為 import ui.helpers.render_state 的同名函式")


# ══════════════════════════════════════════════════════════════════
# 五分頁骨架：職責對齊（既有三道鎖沒有覆蓋的那一個缺口）
# ══════════════════════════════════════════════════════════════════
#: 每個分頁 slot 應該呼叫的 render 函式。**這張表就是「職責對齊」的定義**：
#: 分頁名（由 `story_nav._TAB_LABELS` 管）與分頁內容（本表）是兩件事，
#: 既有的三道鎖只守前者。
_SLOT_RENDER: dict[str, str] = {
    # 2026-09-04 五分頁動線重構（WF-IA-1）：① 改掛全新撰寫的 View
    # `ui/views/page_01_macro.py::render_market_overview`。
    # ⚠️ **這是「意圖」變更，不是把規則放寬** —— 本條的作用（分頁內容不准跟著
    #    改名一起漂走）一字未減：它仍然斷言 `with tab_macro:` 只呼叫這一個
    #    render 函式，把別頁的 render 搬進來照樣紅。改的只是**該叫哪一個**。
    # ⚠️ 舊 `ui/tab1_macro.py::render_macro_tab` **一個字都沒有動**（客戶方針第 3 條
    #    「舊版 tab 檔案暫留作為參考」），只是不再被 `app.py` 掛上 ①。
    "tab_macro":     "render_market_overview",       # ① 只做總體環境判讀
    "tab_health":    "render_fund_grp_health_tab",   # ② 只診斷，不給建議動作
    "tab_research":  "render_fund_research_tab",     # ③ 找標的、研究單檔
    "tab_portfolio": "render_portfolio_tab",         # ④ 要執行的動作都在這裡
    "tab_settings":  "render_settings_diag_tab",     # ⑤ 系統面
}


def _slot_to_render_calls() -> dict[str, list[str]]:
    """從 `app.py` 靜態解析 `with tab_*:` 區塊各自呼叫的 `render_*` 函式。"""
    _tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    _out: dict[str, list[str]] = {}
    for _n in ast.walk(_tree):
        if not isinstance(_n, ast.With):
            continue
        for _item in _n.items:
            _ctx = _item.context_expr
            if isinstance(_ctx, ast.Name) and _ctx.id in _SLOT_RENDER:
                _out[_ctx.id] = [
                    _c.func.id for _c in ast.walk(_n)
                    if isinstance(_c, ast.Call) and isinstance(_c.func, ast.Name)
                    and _c.func.id.startswith("render_")
                ]
    return _out


def test_each_tab_slot_calls_its_own_render():
    """分頁**內容**沒有跟著改名一起漂走。

    既有三道鎖保證「五個分頁、名字對、順序對」，但**它們全都看不到這件事**：
    把 `render_macro_tab()` 搬進 `with tab_health:` —— 名字全對、順序全對、
    `st.tabs` 也只有一個，**三道鎖全綠，畫面全錯**。

    2026-09-01 改名批之所以需要這條：改名讓「哪個 slot 裝什麼」這件事
    第一次變得不能靠讀分頁名推斷（`tab_macro` 這個變數名現在對應的顯示名是
    「🌐 市場總覽」）。**變數名與顯示名脫鉤之後，就需要一張明寫的對照表。**
    """
    _actual = _slot_to_render_calls()
    assert set(_actual) == set(_SLOT_RENDER), (
        f"app.py 的分頁 slot 與對照表對不上：{sorted(_actual)} != {sorted(_SLOT_RENDER)}")
    for _slot, _want in _SLOT_RENDER.items():
        assert _actual[_slot] == [_want], (
            f"`with {_slot}:` 呼叫的是 {_actual[_slot]}，應為 ['{_want}'] —— "
            "分頁內容與職責對不上（分頁名對、內容錯，是測試全綠但畫面全錯的漂移）")
