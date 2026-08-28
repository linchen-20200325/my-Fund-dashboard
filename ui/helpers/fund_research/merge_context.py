"""合併頁的「所有權旗標」—— 讓「這一塊由誰畫」變成可查證的狀態，而不是靠註解約定。

為什麼需要它（線框原文）
------------------------
客戶拍板的線框 `docs/wireframes/fund-wireframe-final.html` §03「③ 🔍 基金研究」寫：

> 不是把兩頁上下相接，而是**共用一個「先找到標的」的頂部**，再用一個模式切換
> 決定下面畫什麼。

「共用」帶來一個具體問題：合併頁在頂部畫了標題與「找代號」工具之後，
再去呼叫 `render_single_fund_tab()`，那支函式**又會畫一次自己的標題與搜尋框** ——
使用者會在同一個畫面上看到兩份。

為什麼不用「加一個參數」解
--------------------------
`tests/test_tab2_single_fund.py::test_import_and_signature` 與
`tests/test_app_smoke.py::test_tab_modules_import_without_error` 都斷言
`render_single_fund_tab` 是**零參數**函式（B-C 設計準則）。加參數會直接把它們弄紅。

為什麼不用 `st.session_state`
-----------------------------
所有權只在「合併頁呼叫子渲染函式」的那一小段期間成立，離開就該還原。
`session_state` 會跨 rerun 活著，一旦忘了清，**舊入口**（app.py 目前仍直接掛的
`render_single_fund_tab`）也會跟著少掉標題。用 context manager + `finally` 還原，
把「範圍」寫死在語言層，不靠紀律。

⚠️ 本模組不做任何渲染、不碰 streamlit —— 它只回答一個布林問題。
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

#: 合併頁自己畫的頁面大標（`## …`）。子渲染函式看到它被持有時，跳過自己那一行標題。
PAGE_HEADER: str = "page_header"

#: 合併頁自己畫的「🔍 關鍵字搜尋境外基金（TDCC / FundClear）」找代號工具。
SHARED_SEARCH: str = "shared_search"

#: 合法的所有權名稱。**刻意寫成封閉集合**：拼錯字時要當場炸掉，
#: 而不是安靜地回 False（那會讓標題悄悄畫兩次，而且沒有人會發現）——
#: `CLAUDE.md §1` Fail Loud。
_KNOWN_PARTS: frozenset = frozenset({PAGE_HEADER, SHARED_SEARCH})

#: 目前被合併頁持有的區塊。模組層單例：Streamlit 一次 rerun 是單執行緒由上而下跑完，
#: 而本旗標的生命週期只有「合併頁呼叫子渲染函式」那幾行。
_OWNED: set = set()


def _validate(parts: tuple) -> None:
    unknown = sorted(p for p in parts if p not in _KNOWN_PARTS)
    if unknown:
        raise ValueError(
            f"未知的合併頁區塊名稱 {unknown}；合法值：{sorted(_KNOWN_PARTS)}。"
            "（打錯字時安靜回 False 會讓標題畫兩次而沒人發現，故此處直接炸掉）")


def owned_by_merged_page(part: str) -> bool:
    """合併頁是否已經自己畫過 `part`？子渲染函式據此跳過重複的那一塊。

    未知名稱一律 `raise`（不是回 False）—— 理由見 `_validate`。
    """
    _validate((part,))
    return part in _OWNED


@contextmanager
def merged_page_owns(*parts: str) -> Iterator[None]:
    """在區塊內宣告「這幾塊由合併頁負責」；離開時**一定**還原（含例外路徑）。

    巢狀安全：離開時還原成進入前的集合，而不是清空。
    """
    _validate(parts)
    _before = set(_OWNED)
    _OWNED.update(parts)
    try:
        yield
    finally:
        _OWNED.clear()
        _OWNED.update(_before)
