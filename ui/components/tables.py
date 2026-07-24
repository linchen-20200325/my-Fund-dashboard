"""ui/components/tables.py — 統一表格渲染 (v19.388 V2)。

收斂目標(可視化稽核 ④):原「裸 st.dataframe / column_config 陣營 / Tab5 的 CSS
偽表」三種混用。本檔提供 `styled_dataframe()` 薄封裝(預設 hide_index + 容器寬)+
`num_col()` 數值欄快捷。**只管呈現,不改動 df 內容/列數/欄數**(§1:不掉行、不竄值)。
"""
from __future__ import annotations


def num_col(label: str, *, fmt: str = "%.2f", help: str | None = None):
    """數值欄設定(統一格式 + tabular)。回傳 st.column_config.NumberColumn。"""
    import streamlit as st
    return st.column_config.NumberColumn(label, format=fmt, help=help)


def styled_dataframe(df, *, column_config=None, **kwargs):
    """`st.dataframe` 薄封裝:預設 hide_index=True + use_container_width=True。

    caller 傳 column_config(可用 num_col 建數值欄)。**df 原樣傳入,本函式不複製/不變更
    內容**;缺值由 NumberColumn 呈現為空格(§1 誠實,不填 0)。
    """
    import streamlit as st
    kwargs.setdefault("hide_index", True)
    kwargs.setdefault("use_container_width", True)
    if column_config is not None:
        kwargs["column_config"] = column_config
    return st.dataframe(df, **kwargs)
