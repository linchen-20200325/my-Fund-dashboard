"""IA 鐵則 04 —— 首屏無冗餘占位：空狀態三要素。

客戶 2026-09-01 拍板線框（`docs/wireframes/ia-wireframe.html` Rule 04）：

> 無資料不畫空表格外框，改用空狀態三要素：標題、缺什麼、去哪補。

線框 Tab 02 的實樣（本模組要產出的東西）::

    尚未設定持倉
    ⬜ 還沒有任何保單或扣款標的（請先到：④ 資產配置 › 保單與扣款標的）
    補完後這裡會自動出現逐檔體檢

**「去哪補」是三要素裡最容易被省掉、也最有價值的一項** ——
沒有它，空狀態只是把「消失」換成「灰色的消失」，使用者還是不知道下一步。

與 `ui/helpers/render_state.py` 的關係（**重要，不要重做**）
------------------------------------------------------------
灰態（⬜ 未載入／前提不足）的 SSOT 是 `render_state.not_ready()`，
它已經涵蓋三要素裡的**後兩項**（`message` ＝ 缺什麼、`where` ＝ 去哪補）。
本模組**不重寫那段**，只補它缺的第一項（**標題**）與區塊化排版，
其餘一律委派回去 —— 所以：

- 灰色文案的實際渲染仍然是 `not_ready()`；
- ⬜ 標記仍然是 `render_state.NOT_READY_MARK`（本檔不另定義一個）；
- 顏色仍然來自 `shared.colors`（本檔**沒有任何 hex 字面值**，§3.3）。

⚠️ **本模組不是「另一套灰態」。** 若日後要改灰態的視覺，改 `render_state`，
   本模組會跟著變；反過來在這裡加一套自己的灰，就是把 SSOT 劈成兩半。
"""
from __future__ import annotations

import streamlit as st

from shared.colors import GH_FG_MUTED
from ui.helpers.render_state import not_ready


def empty_state(title: str, missing: str, *, where: str = "",
                footer: str = "") -> None:
    """空狀態三要素：**標題**＋**缺什麼**＋**去哪補**。不畫空表格外框。

    Parameters
    ----------
    title   : 標題 —— 用**使用者的話**講他現在是什麼處境（「尚未設定持倉」），
              不要寫「無資料」「查無結果」這種對他沒有資訊量的字。
    missing : 缺什麼 —— 具體的東西（「還沒有任何保單或扣款標的」），
              不要只寫「無資料」。
    where   : 去哪補 —— 指到分頁 ＋ 區塊（「④ 資產配置 › 保單與扣款標的」）。
              ⚠️ 請走 `ui.helpers.story_nav` 的 `where_to_find()` 產生，
              **不要手抄分頁名** —— 手抄的指路文案在本 repo 已經指錯三次，
              且 `tests/test_wpf_five_tab_wiring.py` 會擋下寫死的分頁名。
    footer  : 補完之後會發生什麼（選填，「補完後這裡會自動出現逐檔體檢」）。

    Raises
    ------
    TypeError
        `missing` 收到 Exception。**手上有例外就不是「還沒設定」，是系統真出錯**
        —— 走 `render_state.system_error()`。這個防呆與 `not_ready()` 同源，
        在這裡先擋一次，是為了讓錯誤訊息指向呼叫端而不是委派之後的內層。
    """
    if isinstance(missing, BaseException):
        raise TypeError(
            "empty_state() 的 missing 不接受 Exception —— "
            "手上有例外代表這是系統真出錯，請用 render_state.system_error()；"
            f"收到的是 {type(missing).__name__}: {missing}")
    # 標題：灰色、粗體、**不帶 ⬜** —— 底下 not_ready() 會帶一個，
    # 兩個 ⬜ 疊在一起只是噪音。
    st.markdown(
        f"<div style='color:{GH_FG_MUTED};font-weight:600;font-size:14px;"
        f"margin:6px 0 2px'>{title}</div>",
        unsafe_allow_html=True,
    )
    not_ready(missing, where=where)
    if footer:
        st.markdown(
            f"<div style='color:{GH_FG_MUTED};opacity:.75;font-size:12px;"
            f"margin-top:2px'>{footer}</div>",
            unsafe_allow_html=True,
        )
