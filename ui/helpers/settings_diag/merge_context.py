"""「⑤ 設定與診斷」合併頁的所有權旗標 —— 誰負責畫哪一塊，做成可查證的狀態。

為什麼有這個檔（而不是直接用 `ui/helpers/fund_research/merge_context.py`）
--------------------------------------------------------------------------
WP-C 已為「③ 基金研究」建立同型機制（thread-local 旗標 + `finally` 還原 +
未知名稱 raise）。本檔**照抄那個模式、但名稱空間刻意分開**：

1. ③ 與 ⑤ 是兩個不同的合併頁，各自持有各自的區塊。把 ⑤ 的名稱塞進
   ③ 的 `_KNOWN_PARTS`，等於讓兩頁共用一個旗標池 —— ③ 的任何持有
   都可能誤傷 ⑤ 的子頁（反之亦然），而且改 ③ 的檔案不在本工作包邊界內。
2. 兩頁的生命週期不同步（接線批次也可能分開切換），分開的封閉集合
   讓「⑤ 還沒接線」與「③ 已接線」可以同時成立而互不干擾。

機制本身的三個設計理由（與 WP-C 相同，收斂重述；完整論證見
`ui/helpers/fund_research/merge_context.py` 的模組 docstring）：

- **不用「加參數」**：既有測試斷言子頁 render 函式是零參數（B-C 設計準則）。
- **不用 `st.session_state`**：所有權只在「合併頁呼叫子渲染函式」那一小段成立，
  `session_state` 跨 rerun 活著，忘了清會讓**舊入口**無聲少掉整塊。
  context manager + `finally` 把「範圍」寫死在語言層。
- **旗標存 `threading.local()`**：Streamlit 一個 process 服務多個 session、
  每個 session 一條 ScriptRunner 執行緒 —— 模組層集合會跨 session 外洩
  （WP-C 2026-08-28 稽核實證過的真缺陷），thread-local 讓每條執行緒各持一份。

⚠️ 本模組不做任何渲染、不碰 streamlit —— 它只回答一個布林問題。
"""
from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator

#: 「📋 我的管理室」子頁自己的 `## ` 頁面大標。⑤ 已畫分區標題時跳過。
MANAGE_HEADER: str = "manage_header"

#: 「🔭 資料診斷」子頁自己的 `## ` 頁面大標。⑤ 已畫分區標題時跳過。
DATA_GUARD_HEADER: str = "data_guard_header"

#: 「📖 說明書」子頁自己的 `## ` 頁面大標。⑤ 已畫分區標題時跳過。
MANUAL_HEADER: str = "manual_header"

#: 「🔍 抓取診斷細節（哪個源失敗 + NAS Proxy 狀態）」整塊。
#: 線框 §03 ⑤ 把它從個基頁搬到 ⑤；⑤ 持有時，個基頁不再畫那一塊。
FETCH_DIAG: str = "fetch_diag"

#: 「📋 保單管理（Google Sheets）」區塊的 ⑤ 端開關。
#: ⚠️ 語意與其他旗標**方向相反但機制相同**：其他旗標是「⑤ 持有 → 子頁跳過」，
#: 本旗標是「接線批次宣告 ⑤ 持有 → ⑤ 才渲染」。⑤ 未接線前（旗標全空）
#: ⑤ 只顯示灰色說明，④ 的 `ui/tab3_portfolio.py` 照舊呼叫、一個字未改 ——
#: 同一塊不會被畫兩次。切換前的前置條件見 `policy_admin_bridge` docstring。
POLICY_ADMIN: str = "policy_admin"

#: 合法的所有權名稱。**刻意寫成封閉集合**：拼錯字時要當場炸掉，
#: 而不是安靜地回 False（那會讓區塊悄悄畫兩次 / 悄悄消失，而且沒有人會發現）
#: —— `CLAUDE.md §1` Fail Loud。
_KNOWN_PARTS: frozenset = frozenset({
    MANAGE_HEADER, DATA_GUARD_HEADER, MANUAL_HEADER, FETCH_DIAG, POLICY_ADMIN,
})

#: 目前被 ⑤ 持有的區塊，**每條執行緒各一份**（理由見模組 docstring）。
_STATE = threading.local()


def _owned() -> set:
    """本執行緒目前持有的區塊集合（第一次取用時才建立）。"""
    _s = getattr(_STATE, "owned", None)
    if _s is None:
        _s = set()
        _STATE.owned = _s
    return _s


def _validate(parts: tuple) -> None:
    unknown = sorted(p for p in parts if p not in _KNOWN_PARTS)
    if unknown:
        raise ValueError(
            f"未知的「設定與診斷」區塊名稱 {unknown}；合法值：{sorted(_KNOWN_PARTS)}。"
            "（打錯字時安靜回 False 會讓區塊畫兩次或無聲消失，故此處直接炸掉）")


def owned_by_settings_page(part: str) -> bool:
    """「⑤ 設定與診斷」是否已經持有 `part`？子渲染函式據此跳過重複的那一塊。

    未知名稱一律 `raise`（不是回 False）—— 理由見 `_validate`。
    """
    _validate((part,))
    return part in _owned()


@contextmanager
def settings_page_owns(*parts: str) -> Iterator[None]:
    """在區塊內宣告「這幾塊由 ⑤ 負責」；離開時**一定**還原（含例外路徑）。

    巢狀安全：離開時還原成進入前的集合，而不是清空。
    """
    _validate(parts)
    _cur = _owned()
    _before = set(_cur)
    _cur.update(parts)
    try:
        yield
    finally:
        _cur.clear()
        _cur.update(_before)
