"""顏色五態 SSOT —— 「系統真紅燈」與「業務紅燈」嚴格分離。

客戶 2026-08-28 拍板（線框 `fund-empty-state-wireframe.html` §03「顏色：三態統一規則」）：

> 嚴格分離「業務紅燈」與「系統真紅燈」，未載入／未設定一律改灰色說明，
> 把用灰字印的真失敗改回系統紅燈。

為什麼一定要分（線框原文，本模組存在的唯一理由）
------------------------------------------------
**系統紅燈的意思是「這個數字不可信」；業務紅燈的意思是「這個數字可信，而且它很難看」。**
兩者要使用者做的事完全相反 —— 前者要他別採信、去修；後者要他採信、去換基金。
用同一個紅色，等於把「不要相信這個畫面」和「相信這個畫面並據以行動」畫成同一件事。

反方向同樣是 bug：真正的失敗（抓取／渲染／模組載入）如果用灰字印，
畫面看起來只是「還沒載入」—— 使用者會以為按一下就好，實際按幾次都一樣。
這與 `CLAUDE.md §1`「錯誤的數字比沒有數字更危險」同源。

五態對照
--------
| 狀態         | 視覺                       | 本模組入口              |
|--------------|----------------------------|-------------------------|
| 未載入／未設定 | ⬜ 灰色說明（`st.caption`） | `not_ready()`           |
| 不適用       | ➖ 或不顯示                 | `NOT_APPLICABLE_MARK`（現況已分對，**不要**併進 ⬜） |
| 業務警訊     | 🔴 紅字，但用卡片／表格列    | `business_alert()`      |
| 系統真出錯   | 🔴 紅色錯誤框 + 可展開技術細節 | `system_error()`      |
| 破壞性操作提醒 | 🟠 常駐橘框                | `st.warning()`（無例外處理，不需 helper） |

⚠️ `not_ready()` 不吃 Exception —— 這是刻意的型別層防呆：
「還沒載入」永遠不會有 exception 可報；一旦手上有 exception，就是 `system_error()`。
`tests/test_render_state_color_separation.py` 以 AST 守住這條分界（守形狀，不守字面）。
"""
from __future__ import annotations

import streamlit as st

from shared.colors import BG_DARK_RED_1, GH_FG_PRIMARY, MATERIAL_RED

# ⬜ 在 ui/ 全層已是家規（量測日 2026-08-28：299 處）——沿用，不引進新符號。
NOT_READY_MARK: str = "⬜"
# ➖「結構上不適用」（台幣基金沒有匯率位階、不配息基金沒有配息欄）。
# 與 ⬜ 語意不同：⬜ 是「現在沒有、之後會有」，➖ 是「這件事對它本來就不存在」。
NOT_APPLICABLE_MARK: str = "➖"


def not_ready(message: str, *, where: str = "") -> None:
    """⬜ 灰色說明：還沒載入／還沒執行／還沒設定。**不是**故障。

    Parameters
    ----------
    message : 缺什麼（寫具體的東西，不要只寫「無資料」）。
    where   : 去哪裡補（例：「🌐 市場定調 → 📡 載入總經資料」）。
              線框 §02：這是最容易省掉、也最有價值的一項 ——
              沒有它，占位只是把「消失」換成「灰色的消失」。
    """
    if isinstance(message, BaseException):
        # 型別層防呆:「還沒載入」永遠不會有 exception 可報。手上有 exception
        # 卻走到這裡,代表把「系統真出錯」畫成了「還沒載入」—— 那正是本模組要擋的 bug。
        raise TypeError(
            "not_ready() 不接受 Exception —— 手上有例外就是 system_error()，"
            f"收到的是 {type(message).__name__}: {message}")
    _msg = f"{NOT_READY_MARK} {message}"
    if where:
        _msg += f"（請先到：{where}）"
    st.caption(_msg)


def system_error(what: str, exc: BaseException, *, hint: str = "") -> None:
    """🔴 系統真出錯：紅色錯誤框 + 可展開技術細節 + stderr 鏡射。

    用在：抓取失敗、渲染失敗、模組載入失敗 —— 也就是**畫面上少了或錯了一個數字**。

    走 `ui.helpers.session.friendly_error(level="error")`（全站錯誤呈現 SSOT，
    §2.1），本函式只負責把「這是系統紅燈」這個語意具名化，讓稽核與測試找得到。
    """
    from ui.helpers.session import friendly_error  # lazy：避免 import 迴圈

    friendly_error(
        what, exc,
        hint=hint or "此區塊已隔離，其他區塊與分頁不受影響；"
                     "請展開下方「🔧 技術細節」把 traceback 截圖回報。",
        level="error",
    )


def business_alert(title: str, lines: list[str], *, footer: str = "") -> None:
    """🔴 業務警訊：紅字卡片，**不是**紅色錯誤框。

    用在：淘汰候選、嚴重吃本金、系統性風險暫緩換標 —— 分析**成功了**，
    答案是「這幾檔該換」。那是成果，不是故障，所以不能用 `st.error`
    （會和系統崩潰共用同一個視覺語彙）。
    """
    _body = "".join(f"<div style='margin:2px 0'>{ln}</div>" for ln in lines)
    _foot = (f"<div style='color:{GH_FG_PRIMARY};opacity:.7;font-size:11px;"
             f"margin-top:6px'>{footer}</div>") if footer else ""
    st.markdown(
        f"<div style='background:{BG_DARK_RED_1};border-left:4px solid {MATERIAL_RED};"
        f"border-radius:6px;padding:10px 12px;margin:6px 0'>"
        f"<div style='color:{MATERIAL_RED};font-weight:700;font-size:15px;"
        f"margin-bottom:4px'>{title}</div>"
        f"<div style='color:{GH_FG_PRIMARY};font-size:13px'>{_body}</div>"
        f"{_foot}</div>",
        unsafe_allow_html=True,
    )
