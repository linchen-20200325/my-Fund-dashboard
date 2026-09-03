"""IA 鐵則 02 —— Form 封裝防重繪：按「套用」才運算。

客戶 2026-09-01 拍板線框（`docs/wireframes/ia-wireframe.html` Rule 02）：

> 篩選、輸入框、滑桿一律 `st.form` 包住，按「套用」才運算。

線框 Tab 02 就地點名了現況：「**目前每拉一格全頁重繪，本次一併修掉**」。

為什麼要一個 helper（而不是各分頁自己寫 `st.form`）
--------------------------------------------------
`st.form` 的正確用法有兩個**很容易漏掉、而且漏掉不會報錯**的地方：

1. **一定要有 `st.form_submit_button`。** 少了它 Streamlit 會在 render 時丟
   `StreamlitAPIException`，但那是在**跑到那一頁**才炸 —— 不是寫的時候。
2. **submit 的回傳值要被接住並用來 gate 運算。** 很多寫法是
   `with st.form(...): ... ; st.form_submit_button("套用")` 而**不接回傳值**，
   於是 form 只擋住了「widget 互動觸發 rerun」，**沒有擋住「重運算」** ——
   每次 rerun 照樣把重運算跑一遍。**畫面看起來沒問題，成本一分沒省。**

本模組把這兩件事變成單一入口：submit 的結果由 :class:`FormGate` 帶出來，
呼叫端**必須**拿它去 gate 後續運算，否則就會很明顯地看出沒 gate。

用法
----
::

    from ui.helpers.ia import applied_form

    with applied_form("health_filters") as gate:
        thr = st.slider("輪動門檻 σ", 0.5, 2.0, 1.0)
        window = st.number_input("回看窗（月）", 1, 36, 12)
        satellite_only = st.checkbox("只看衛星")

    if gate:                      # ← 按下「套用」才進來
        run_expensive_diagnosis(thr, window, satellite_only)

⚠️ **`gate` 要在 `with` 區塊「之外」判斷。** 在區塊裡判斷永遠是 `False` ——
   submit 按鈕是在 `yield` 之後才建立的（它必須排在所有 widget 底下）。
   這一點由 `tests/test_ia_kit.py::test_gate_is_false_inside_the_block` 釘住。
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

import streamlit as st

#: 送出鈕的預設字。線框 Tab 02 用的就是「套用」。
#: 其他分頁有自己的動詞（「載入總經資料」／「搜尋」／「試算」），
#: 那些**是有意義的差異**，用 `submit_label=` 傳，不要改這個預設值。
APPLY_LABEL: str = "套用"


@dataclass
class FormGate:
    """`applied_form()` 的把手：帶出「這一輪有沒有按下送出」。

    `__bool__` 直接回 :attr:`submitted`，所以 `if gate:` 就夠了，
    不必寫 `if gate.submitted:`（兩種都可以，前者是給常見情況用的糖）。
    """

    key: str
    submitted: bool = False
    #: 送出鈕的字，除錯／測試用（不參與渲染判斷）。
    submit_label: str = APPLY_LABEL
    #: 保留給呼叫端塞任意脈絡，本模組不讀它。
    extra: dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return bool(self.submitted)


@contextmanager
def applied_form(key: str, *, submit_label: str = APPLY_LABEL,
                 clear_on_submit: bool = False,
                 border: bool = True) -> Iterator[FormGate]:
    """把一組輸入 widget 包進 `st.form`，yield 一個 :class:`FormGate`。

    Parameters
    ----------
    key             : `st.form` 的 key。全站唯一（Streamlit 會在重複時炸掉，
                      那是**對的行為**，不要為了消音而加隨機後綴）。
    submit_label    : 送出鈕文字，預設 :data:`APPLY_LABEL`。
    clear_on_submit : 送出後清空欄位。查詢型表單一律 `False`
                      （使用者通常想在上次條件上微調）；新增型表單才用 `True`。
    border          : 畫不畫外框。

    ⚠️ **本函式不吞例外**（§1）：`with` 區塊裡拋出的例外會照常往上傳，
       此時送出鈕不會被建立 —— 那是**刻意**的，讓失敗的表單明顯壞掉，
       而不是留一個按了沒反應的鈕。
    """
    _gate = FormGate(key=key, submit_label=submit_label)
    # `border` 是 Streamlit 1.29+ 的參數；本 repo 的 floor 遠高於它
    # （現行宣告見 requirements.txt，憲法不釘版本號）。
    with st.form(key, clear_on_submit=clear_on_submit, border=border):
        yield _gate
        # 送出鈕必須排在所有 widget **之後**，所以只能在 yield 回來之後建立。
        # 這也是 `gate` 在區塊內恆為 False 的原因（見模組 docstring 的 ⚠️）。
        _gate.submitted = bool(st.form_submit_button(submit_label))
