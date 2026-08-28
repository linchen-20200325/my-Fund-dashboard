"""ui/components/column_group_tabs.py — 健診大表「分組欄位」切換器（UI3b）。

一句話：**把一張橫向爆炸的健診大表，切成幾組看得完的欄位**，
而且**每一組都必須帶著同一批釘選欄**。

⚠️ 釘選欄（`pinned`）為什麼是硬要求，不是體貼
---------------------------------------------
一檔只抓到 30 筆淨值的基金，`Sharpe / σ / MaxDD` 會**整批留白**，
但 `4D Score` 照樣給得出分數。也就是說：**在表裡，它和一檔資料完整的正常基金
長得一模一樣**，只差幾個空格 —— 而空格很容易被讀成「這項剛好不適用」。

`淨值樣本` / `評分覆蓋` / `對帳` 這三欄是唯一能把它認出來的東西。
**把它們藏進某一個分組 = 重新製造這個 bug。** 故本元件在每一組前面都強制插入
`pinned`，並且**不提供關掉的參數**（`tests/test_ui3b_components.py` 守著）。

⚠️ 巢狀 `st.tabs` 的查證結果（2026-08-28 實測）
----------------------------------------------
`app.py` 的全域 CSS 有兩條 tab bar 規則：第一條讓**頂層** tab-list `position:sticky`；
第二條 `div[data-testid="stTabs"] div[data-testid="stTabs"] div[data-baseweb="tab-list"]`
把**巢狀** tab-list 還原成 `position:static`。

→ **巢狀 `st.tabs` 沒有被禁止，只是不黏頂**（否則子分頁列會和頂層那條互相打架）。
   repo 內已有既存用法（`app.py` 的「📖 說明書 / 🔭 資料診斷」子分頁本身就在頂層 tab 內）。
   該選擇器用 descendant 而非 `>`，第 3 層以上的巢狀同樣被涵蓋。

→ 故 `mode="tabs"` **可用，並設為預設**。

⚠️ 但保留 `mode="radio"`，理由要寫清楚：`st.tabs` **單次 run 會渲染全部分頁**
（`app.py` 內對此有既有註記）。分 6 組 = 同一張大表被渲染 6 次。
`st.radio(horizontal=True)` 只渲染選中的那一組。若接線時量到重繪成本有感，
呼叫端改傳 `mode="radio"` 即可，**不必改本元件**。

§1 Fail Loud
------------
- **元件不改列數、不改內容、不排序。** `df` 原樣切欄後交給
  `ui.components.tables.styled_dataframe`（它同樣自陳「不改動 df 內容/列數/欄數」）。
- `groups` 列出、但 `df` 沒有的欄 → **靜默略過該欄，但該分頁下方 caption 必須列出**
  「本組有 N 欄未產生：X / Y（**不是這些基金沒有**）」。
  差別很重要：欄位沒被算出來（上游沒跑）≠ 這些基金沒有這個值。
- **某組欄位全缺，標籤仍然顯示。** 讓分頁憑空消失，看的人會以為只有 5 組、
  永遠不會發現第 6 組整組沒算出來。

⛔ **禁止 `degraded=True`**：表格就是數值本身，不是「掉了一張圖」。

⚠️ `groups` / `pinned` **刻意不定義在本檔**
------------------------------------------
分組定義是健診大表的業務知識，寫在這裡就會變成第二份 SSOT
（一份在呼叫端、一份在元件裡，然後開始漂移）。**本元件只接受傳入。**
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from ui.components.tables import styled_dataframe


def resolve_group_columns(
    df_columns: Sequence[Any],
    group_cols: Sequence[str],
    pinned: Sequence[str],
) -> tuple[list[str], list[str], list[str]]:
    """算出某一組實際要顯示的欄位。**純函式，可單獨測試。**

    Returns
    -------
    (ordered, missing_group, missing_pinned)
        ordered        : 釘選欄（依 `pinned` 順序）＋ 本組欄（依 `group_cols` 順序），去重。
        missing_group  : `group_cols` 裡 df 沒有的欄。
        missing_pinned : `pinned` 裡 df 沒有的欄（比 missing_group 更嚴重 —— 那是防線本身沒了）。
    """
    have = list(df_columns)
    have_set = set(have)
    ordered: list[str] = []
    seen: set[str] = set()
    for c in list(pinned) + list(group_cols):
        if c in have_set and c not in seen:
            ordered.append(c)
            seen.add(c)
    missing_pinned = [c for c in pinned if c not in have_set]
    missing_group = [c for c in group_cols if c not in have_set and c not in pinned]
    return ordered, missing_group, missing_pinned


def build_missing_caption(missing_group: Sequence[str],
                          missing_pinned: Sequence[str]) -> str:
    """缺欄說明（純字串）。兩者都空 → 回 `""`（不製造噪音）。"""
    parts: list[str] = []
    if missing_pinned:
        parts.append(
            f"🔴 釘選欄有 {len(missing_pinned)} 欄未產生："
            + " / ".join(str(c) for c in missing_pinned)
            + " —— 少了它，資料不足的基金在表裡與正常基金無法分辨。")
    if missing_group:
        parts.append(
            f"⬜ 本組有 {len(missing_group)} 欄未產生："
            + " / ".join(str(c) for c in missing_group)
            + "（**不是這些基金沒有**，是這幾欄這次沒被算出來）。")
    return "　".join(parts)


def _subset_config(col_config: Mapping[str, Any] | None,
                   cols: Sequence[str]) -> dict | None:
    if not col_config:
        return None
    sub = {k: v for k, v in col_config.items() if k in set(cols)}
    return sub or None


def render_column_group_tabs(
    df: Any,
    col_config: Mapping[str, Any] | None,
    groups: Sequence[tuple[str, Sequence[str]]],
    pinned: Sequence[str],
    *,
    mode: str = "tabs",
    key_prefix: str = "colgrp",
) -> None:
    """渲染分組欄位切換器。

    Parameters
    ----------
    df         : 已組好的健診大表。**本元件不改它**（不排序、不篩列、不補值）。
    col_config : `st.column_config.*` 的 dict；本元件只做 key 子集切片。
    groups     : `[(分組標籤, [欄名, ...]), ...]` —— 由呼叫端提供（見模組 docstring）。
    pinned     : 每一組都會被插到最前面的釘選欄。
    mode       : `"tabs"`（預設，巢狀 tabs 已查證可用）或 `"radio"`（只渲染選中組，省重繪）。
    key_prefix : widget key 前綴（`mode="radio"` 時需要；同頁多個實例不得共用）。
    """
    import streamlit as st  # lazy

    if not groups:
        from ui.helpers.render_state import not_ready
        not_ready("尚未定義欄位分組", where="呼叫端的 groups 參數")
        return

    labels = [str(lbl) for lbl, _ in groups]

    def _render_one(idx: int) -> None:
        _lbl, group_cols = groups[idx]
        ordered, missing_group, missing_pinned = resolve_group_columns(
            list(getattr(df, "columns", [])), group_cols, pinned)
        if ordered:
            styled_dataframe(df[ordered],
                             column_config=_subset_config(col_config, ordered))
        else:
            from ui.helpers.render_state import not_ready
            # 整組一欄都沒有 —— 標籤仍在（見 docstring），但表格畫不出來。
            not_ready("本組欄位這次一欄都沒有產生", where="健診大表的欄位計算")
        cap = build_missing_caption(missing_group, missing_pinned)
        if cap:
            st.caption(cap)

    if mode == "radio":
        choice = st.radio("欄位分組", labels, horizontal=True,
                          key=f"{key_prefix}_group", label_visibility="collapsed")
        _render_one(labels.index(choice))
        return

    # 預設：巢狀 st.tabs（已查證可用，僅不黏頂）。
    for i, tab in enumerate(st.tabs(labels)):
        with tab:
            _render_one(i)
