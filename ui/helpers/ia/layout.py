"""IA 鐵則 01 —— 三欄自適應網格 ／ 大表全寬橫向捲動。

客戶 2026-09-01 拍板線框（`docs/wireframes/ia-wireframe.html` Rule 01）：

> 卡片與指標排 3 欄，手機自動塌為 1 欄；多欄位大表維持全寬橫向捲動。

**這條規則有兩半，而且第二半才是它真正在防的東西。**
「卡片排 3 欄」誰都會寫；會出事的是**把 9 欄的大表塞進 1/3 寬的欄位** ——
表格不會消失，它會把每一欄壓到剩兩個字，然後使用者以為資料壞了。
所以本模組把「網格」與「大表」做成**兩個名字不同、簽名不同的入口**，
讓「該用哪一個」在呼叫端就必須先想清楚，而不是兩個都寫 `st.columns`。

對外 API
--------
- :data:`GRID_COLS` —— 3。桌面欄數的唯一出處（§3.3 反捏造：不准 inline `3`）。
- :func:`card_row` —— 產生一列 `GRID_COLS` 欄的 context（卡片／指標用）。
- :func:`card_grid` —— 依項目數自動分列，回傳與項目一一對應的欄位序列。
- :func:`wide_table` —— 大表全寬 + 橫向捲動；**空資料時不畫空表格外框**（鐵則 04）。

⚠️ **「手機自動塌為 1 欄」由 Streamlit 內建的 responsive 行為提供，本模組不另加 CSS。**
   本組**沒有實測**這件事 —— 沙箱沒有瀏覽器、也沒有任何裝置寬度可模擬（§-2 規則 6）。
   下面這個決定的理由是「不要自己造一套會跟框架打架的 CSS」，
   **不是**「我驗過它會塌」。要驗請在真機上開窄視窗看。
   ⛔ 若日後實測發現它**不會**塌，正確的修法是在本模組補 CSS，
   **不是**在各分頁各自補一份 —— 那正是本模組存在的理由。

⚠️ **本模組不碰顏色。** 三態顏色的 SSOT 是 `ui/helpers/render_state.py`
   （灰 `not_ready` ／ 莓紅 `business_alert` ／ 紅框 `system_error`），
   本模組**不重做、不包一層、不 re-export**（同一個東西只准有一處實作）。
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Sequence

import streamlit as st

#: 桌面版網格欄數。客戶鐵則 01 寫死 3；具名而不 inline（§3.3 反捏造）。
#: ⚠️ 改這個值等於改客戶拍板的版面 —— 屬 §-1.5 v3 §03-2 ① 的客戶 gate，
#: 不是實作細節。`tests/test_ia_kit.py::test_grid_cols_is_three` 守住它。
GRID_COLS: int = 3


@contextmanager
def card_row(cols: int = GRID_COLS) -> Iterator[Sequence[Any]]:
    """開一列 `cols` 欄的網格，yield 欄位序列。

    Examples
    --------
    >>> with card_row() as (c1, c2, c3):   # doctest: +SKIP
    ...     with c1:
    ...         st.metric("景氣位階", "擴張中段")

    Parameters
    ----------
    cols : 欄數，預設 :data:`GRID_COLS`。**除了大表以外不要改它** ——
           要改的通常是「這個東西不該放在網格裡」，不是「這一列想要 2 欄」。
    """
    yield st.columns(cols)


def card_grid(n_items: int, cols: int = GRID_COLS) -> list[Any]:
    """`n_items` 個項目 → 回傳長度 `n_items` 的欄位序列，已自動分列。

    比 :func:`card_row` 好用的地方：呼叫端不必自己算「幾個要分幾列」。
    最後一列不足 `cols` 個時**留白，不補空卡** —— 補空卡就是鐵則 04
    「無資料不畫空表格外框」的同一種病（畫一個沒有內容的框給使用者看）。

    Examples
    --------
    >>> for _c, _item in zip(card_grid(len(items)), items):   # doctest: +SKIP
    ...     with _c:
    ...         st.metric(_item["label"], _item["value"])
    """
    if n_items <= 0:
        return []
    _out: list[Any] = []
    _left = n_items
    while _left > 0:
        _take = min(cols, _left)
        # 一律開滿 `cols` 欄再取前 `_take` 個 —— 這樣最後一列的欄寬與前幾列一致，
        # 不會出現「剩兩個項目就各佔半頁」的塌陷版面。
        _out.extend(st.columns(cols)[:_take])
        _left -= _take
    return _out


def wide_table(data: Any, *, empty_title: str = "", empty_missing: str = "",
               empty_where: str = "", **kwargs: Any) -> bool:
    """大表：**全寬 + 橫向捲動**；空資料時走空狀態，不畫空表格外框。

    Returns
    -------
    bool : 有沒有真的畫出表格。`False` 代表走了空狀態分支。

    為什麼把「空」綁在這裡（本函式存在的第二個理由）
    ------------------------------------------------
    鐵則 04「無資料不畫空表格外框」如果只寫在文件裡，就得靠每個呼叫端自律；
    而 `st.dataframe(空 df)` 的預設行為**正好就是畫一個空框**。
    把判斷收在唯一的大表入口，這條規則才有機械上的著力點。

    ⚠️ **一定要傳空狀態三要素**：沒有 `empty_title` 就代表呼叫端沒想過「空的時候
    要跟使用者說什麼」—— 直接 fail loud，不要靜默畫一個空框（§1）。

    ⚠️ **不要把本函式放進 `card_row()` 的欄位裡。** 大表在 1/3 寬會被壓成無法閱讀
    的窄欄；`use_container_width=True` 在那裡只會撐滿那 1/3。
    這一點無法在函式內偵測（Streamlit 不對外提供「我現在在不在欄位裡」），
    所以它是**呼叫端的責任**，寫在這裡讓人看得到。
    """
    if _is_empty(data):
        if not empty_title:
            raise ValueError(
                "wide_table() 收到空資料，但沒有提供 empty_title —— "
                "鐵則 04 要求空狀態三要素（標題／缺什麼／去哪補），"
                "不得靜默畫一個空表格外框。")
        # 延後 import：避免 `ui.helpers.ia` 內部模組互相 import 造成載入順序耦合。
        from ui.helpers.ia.empty_state import empty_state
        empty_state(empty_title, empty_missing, where=empty_where)
        return False
    kwargs.setdefault("use_container_width", True)
    st.dataframe(data, **kwargs)
    return True


def _is_empty(data: Any) -> bool:
    """判斷「沒有資料」。**不吞例外、不猜值**（§1）。

    刻意不用 `if not data:` —— DataFrame 的 `__bool__` 會直接拋
    `ValueError: The truth value of a DataFrame is ambiguous`，
    而 numpy array 的 `__bool__` 對多元素同樣會炸。
    """
    if data is None:
        return True
    _empty_attr = getattr(data, "empty", None)   # pandas DataFrame / Series
    if isinstance(_empty_attr, bool):
        return _empty_attr
    try:
        return len(data) == 0                     # list / tuple / dict
    except TypeError:
        # 沒有長度、也不是 pandas 物件 —— 不猜，當成「有資料」交給 Streamlit 去畫。
        return False
