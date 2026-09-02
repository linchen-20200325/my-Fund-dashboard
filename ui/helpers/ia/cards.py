"""IA 鐵則 03 的**落點** —— 一張卡，三種狀態，三種不同的視覺。

客戶 2026-09-01 拍板線框（`docs/wireframes/ia-wireframe.html` Rule 03）：

> 灰＝未載入或前提不足；莓紅左軌＝業務警示；紅框＝系統真出錯。

⚠️ **顏色本身的 SSOT 不在這裡，在 `ui/helpers/render_state.py`。**
本模組**一行顏色都沒有實作**（也沒有任何 hex 字面值），它做的是另一件事：
把「狀態」從**呼叫端的自由心證**變成**一個必填參數**。

為什麼需要這一層（本模組存在的唯一理由）
----------------------------------------
`render_state` 提供了三個入口，但它們是**三個不同名字的函式**。
線框裡每一張卡（景氣位階／波動與信用／通膨與利率…）都是「同一張卡的三種狀態」，
呼叫端如果自己 `if / elif` 去挑函式，就會出現本 repo 已經發作過的那個形狀：
**同一個失敗在 A 分頁是 🔴、在 B 分頁是灰字**
（見 `tests/test_render_state_color_separation.py::test_twin_failures_wear_the_same_colour`
 —— 那是 2026-08-28 真的抓到的事故，不是假想）。

把三態收成一個 `state=` 參數之後：
- 「這張卡現在是什麼狀態」變成**呼叫端必須明講的事**，不能靠忘記寫而預設成好看的那個；
- 三個分支各自委派給 `render_state` 的對應入口，**視覺一定不同**，
  因為它們根本是不同函式（`tests/test_ia_kit.py::test_three_states_are_three_different_widgets` 守）。

⚠️ **`STATE_ERROR` 一定要帶 exc。** 沒有例外物件就不是「系統真出錯」——
   §1 Fail Loud 的紅燈必須帶得出技術細節，否則它只是一個紅色的猜測。
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from ui.helpers.render_state import business_alert, not_ready, system_error

#: 一切正常：可信、而且不難看。走 `st.metric`。
STATE_OK: str = "ok"
#: 灰：未載入／前提不足。**不是**故障。走 `render_state.not_ready()`。
STATE_NOT_READY: str = "not_ready"
#: 莓紅左軌：資料可信，但表現差（業務警示）。走 `render_state.business_alert()`。
STATE_BUSINESS: str = "business"
#: 紅框：系統真出錯，這個數字不可信。走 `render_state.system_error()`。
STATE_ERROR: str = "error"

#: 全部合法狀態。順序即「嚴重度」由低到高，僅供閱讀，程式不依賴順序。
CARD_STATES: tuple[str, ...] = (
    STATE_OK, STATE_NOT_READY, STATE_BUSINESS, STATE_ERROR)


def state_card(title: str, value: str = "", note: str = "", *,
               state: str = STATE_OK, exc: BaseException | None = None,
               where: str = "") -> None:
    """畫一張帶狀態的卡。**`state` 決定視覺，不是文案。**

    Parameters
    ----------
    title : 卡片標題（線框：「波動與信用」）。
    value : 主要數值（線框：「VIX 24.1」）。`STATE_NOT_READY` 時通常留空 ——
            **不要**在未載入時填一個假的 `—` 以外的東西（§1 禁止捏造）。
    note  : 一句話說明（線框：「已越過 22 黃線，尚未觸及 30 恐慌線。」）。
    state : :data:`CARD_STATES` 之一。
    exc   : `state=STATE_ERROR` 時**必填**的例外物件。
    where : `state=STATE_NOT_READY` 時的「去哪補」，走 `story_nav.where_to_find()`
            產生，不要手抄分頁名。

    Raises
    ------
    ValueError
        `state` 不在 :data:`CARD_STATES` 內 —— fail loud，不預設成 OK。
        **預設成 OK 是最糟的降級**：一張其實壞掉的卡會長得像正常的卡。
    TypeError
        `state=STATE_ERROR` 卻沒給 `exc`。
    """
    if state not in CARD_STATES:
        raise ValueError(
            f"state_card() 收到未知狀態 {state!r}；合法值：{CARD_STATES}。"
            "不預設成正常狀態 —— 那會讓壞掉的卡長得像好的卡。")

    if state == STATE_ERROR:
        if not isinstance(exc, BaseException):
            raise TypeError(
                "state_card(state='error') 必須帶 exc（例外物件）—— "
                "紅燈要帶得出技術細節，否則它只是一個紅色的猜測（§1）。")
        system_error(f"「{title}」無法計算", exc, hint=note)
        return

    if state == STATE_NOT_READY:
        st.markdown(f"**{title}**")
        not_ready(note or "尚未載入", where=where)
        return

    if state == STATE_BUSINESS:
        _lines = [ln for ln in (value, note) if ln]
        business_alert(title, _lines)
        return

    # STATE_OK
    st.metric(title, value or "—")
    if note:
        st.caption(note)


def render_cards(cards: list[dict[str, Any]], cols: int | None = None) -> None:
    """把一串卡片定義排進三欄網格（鐵則 01 ＋ 鐵則 03 的組合入口）。

    每個 dict 的 key 就是 :func:`state_card` 的參數名。

    Examples
    --------
    >>> render_cards([                                    # doctest: +SKIP
    ...     {"title": "景氣位階", "value": "擴張中段",
    ...      "note": "NDC 燈號 ＋ PMI ＋ 殖利率差合成。"},
    ...     {"title": "通膨與利率", "state": STATE_NOT_READY,
    ...      "note": "未載入", "where": "① 市場總覽 › 載入總經資料"},
    ... ])

    ⚠️ 空清單**不畫任何東西**（鐵則 04：不留冗餘占位）。要顯示「為什麼是空的」，
       請由呼叫端呼叫 `ui.helpers.ia.empty_state.empty_state()` —— 那需要三要素，
       本函式拿不到（它只知道「清單是空的」，不知道「缺什麼、去哪補」）。
    """
    if not cards:
        return
    # 延後 import：避免 `ia` 套件內部模組在載入期互相依賴。
    from ui.helpers.ia.layout import GRID_COLS, card_grid
    _cols = card_grid(len(cards), cols or GRID_COLS)
    for _c, _spec in zip(_cols, cards):
        with _c:
            state_card(**_spec)
