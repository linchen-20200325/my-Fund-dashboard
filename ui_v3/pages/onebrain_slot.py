# -*- coding: utf-8 -*-
"""🌍／💼 共用的 OneBrain 解釋槽（MK-1；客戶 2026-11-25 授權，`#1296` comment 7147974835）。

恆「未啟用」的靜態槽：不是 AI 結論、不呼叫任何模型或服務、不讀任何狀態、不依任何權利旗標改變；頁面在 AI 關閉時照常可操作。
字樣取 `preview_wording`（暫擬、待客戶定字）。一頁最多一個槽。純函式輸出 HTML；streamlit 只在 `render()` 內 import。
"""
from __future__ import annotations

from ui_v3.viewmodels import preview_wording as W

SLOT_BLOCK = "onebrain-slot"


def onebrain_slot_html() -> str:
    """靜態「未啟用」槽。`data-state="disabled"`、`role="note"`（不是按鈕、不可互動）。"""
    return (f'<div class="uv3-onebrain-slot" data-block="{SLOT_BLOCK}" data-state="disabled" role="note">'
            f'<b>{W.pending_span("onebrain_slot_title")}</b><br>{W.pending_span("onebrain_slot_body")}</div>')


def render() -> None:
    import streamlit as st

    st.markdown(onebrain_slot_html(), unsafe_allow_html=True)
