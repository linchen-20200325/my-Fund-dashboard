# -*- coding: utf-8 -*-
"""預覽殼層的畫面（BL-0484／BL-0479；D1 方案 A）：深色側欄（桌機）＋底部導覽（手機）。

**只畫導覽**：不 import 任何頁、任何 `source`／`fixtures`，不讀不寫任何資料，不呼叫 AI，不碰 query params。
`st.page_link` 只換頁（client 端換頁、同一個 session），與設定頁的「前往設定與診斷」同一種用法。

用法（`ui_v2/app_preview.py::main`）：

    navigation = st.navigation(pages, position="hidden")   # 原生側欄導覽關掉，改由本模組自繪
    shell.render(entries, current_title=navigation.title)
    st.sidebar.info(PREVIEW_NOTE)                           # 側欄說明維持原字（守衛：test_preview_entry）
    navigation.run()

`entries`：`[(slug, title, st.Page), ...]`，順序與頁名取自 `app_preview.PAGES`，本模組一個字都不改。
"""

from __future__ import annotations

import streamlit as st

from ui_v2 import shell_nav


def _link(entry, *, prefix: str, current: bool) -> None:
    slug, title, page = entry
    icon, name = shell_nav.split_title(title)
    # `key` 讓 Streamlit 在容器上掛 `st-key-<key>` class；「目前」那一項的 key 多一個結尾，樣式據此畫粗體、底線、色條
    # （顏色以外的辨識，`PROJECT_RULES.md` 13.2 第 3 條）。同一個 slug 在兩個導覽（側欄、底部）各有一個容器，key 不重複。
    with st.container(key=shell_nav.container_key(prefix, slug, current)):
        st.page_link(page, label=name, icon=icon or None)


def render(entries, *, current_title: str) -> None:
    """畫側欄五項與底部導覽五項。`entries` 空或 `current_title` 不在其中時，所有項目都不標「目前」（不猜）。"""
    if not entries:
        return   # 沒有頁就沒有導覽（`st.columns(0)` 會拋例外）；不補任何預設項
    st.markdown(f"<style>{shell_nav.SHELL_CSS}</style>", unsafe_allow_html=True)
    items = shell_nav.build_items([(slug, title) for slug, title, _ in entries], current_title)
    with st.sidebar:
        for entry, item in zip(entries, items):
            _link(entry, prefix=shell_nav.SIDEBAR_KEY_PREFIX, current=item["current"])
    with st.container(key=shell_nav.BOTTOM_KEY):
        for column, entry, item in zip(st.columns(len(entries)), entries, items):
            with column:
                _link(entry, prefix=shell_nav.BOTTOM_ITEM_PREFIX, current=item["current"])
