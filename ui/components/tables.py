"""ui/components/tables.py — 統一表格渲染 (v19.388 V2)。

收斂目標(可視化稽核 ④):原「裸 st.dataframe / column_config 陣營 / Tab5 的 CSS
偽表」三種混用。本檔提供 `styled_dataframe()` 薄封裝(預設 hide_index + 容器寬)。
**只管呈現,不改動 df 內容/列數/欄數**(§1:不掉行、不竄值)。

2026-08-05 稽核 🟡 必修 5 裁決(`PROCESS.md §4` 0-consumer 條款):
- `styled_dataframe()` → **保留 + 接線**,首個 production caller 為
  `ui/tab1_macro.py::_render_realtime_decision_dashboard` 的逐檔決策矩陣表。
- `num_col()` → **刪除**。它是 `column_config` 的便捷建構子,自 v19.388 建立起
  production 0 caller,且已接線的 caller 也不需要 column_config(該表全為字串欄)。
  留著 = `CLAUDE.md §8.1 step 6`「用不到的抽象」,依 §4 稽核落地條款應刪不應留。
  真需要時 caller 直接寫 `st.column_config.NumberColumn(...)` 即可,零損失。
"""
from __future__ import annotations


def styled_dataframe(df, *, column_config=None, **kwargs):
    """`st.dataframe` 薄封裝:預設 hide_index=True + use_container_width=True。

    caller 可傳 column_config(直接用 `st.column_config.*` 建)。**df 原樣傳入,本函式
    不複製/不變更內容**;缺值由 NumberColumn 呈現為空格(§1 誠實,不填 0)。
    """
    import streamlit as st
    kwargs.setdefault("hide_index", True)
    kwargs.setdefault("use_container_width", True)
    if column_config is not None:
        kwargs["column_config"] = column_config
    return st.dataframe(df, **kwargs)
