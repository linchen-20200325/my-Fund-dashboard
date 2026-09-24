# -*- coding: utf-8 -*-
"""標的探索的 Streamlit 渲染層。

本檔**只負責畫**：四狀態、欄數、文案模板、結論燈、篩選與排序全部住在 logic.py，
這裡一個判定也不做。色票與對比住在 theme.py，假資料住在 fixtures.py。

本檔不 import 舊 repo 任何模組，不發任何網路請求，**不寫任何色碼字面值**
（每一個顏色都從 theme 取 —— 那一份每一組都算過對比）。
"""

from __future__ import annotations

import html

import streamlit as st

from . import fixtures, logic, theme

_MAX_PROBE_WIDTH = 2000


def _esc(text) -> str:
    return html.escape(str(text))


def _tone(tone: str) -> str:
    return theme.tone_hex(tone)


def _breakpoint_edges(layer: int) -> list:
    """掃出該層欄數改變的寬度邊界，回 [(寬度, 該寬度起的欄數), ...]。

    數字只有一個真相源：logic 那支**已被測試釘住**的純函式。
    """
    edges = []
    previous = logic.layer_columns(layer, 1)
    for width in range(2, _MAX_PROBE_WIDTH + 1):
        current = logic.layer_columns(layer, width)
        if current != previous:
            edges.append((width, current))
            previous = current
    return edges


def _grid_css() -> str:
    """把 logic 的斷點翻成真的 CSS media query。

    `44` 2.1 量的是**視窗寬度的 CSS 像素**，所以用 media query 而不是伺服器端固定欄數。
    """
    blocks = [
        """
        [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; gap: 12px; }
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
        [data-testid="stHorizontalBlock"] > [data-testid="column"] {
          flex: 1 1 100% !important; min-width: 0 !important;
        }
        """
    ]
    for layer, marker in ((2, "exp-layer2"), (3, "exp-layer3")):
        for width, columns in _breakpoint_edges(layer):
            share = 100.0 / columns
            blocks.append(
                f"""
        @media (min-width: {width}px) {{
          .{marker} ~ div [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
          .{marker} ~ div [data-testid="stHorizontalBlock"] > [data-testid="column"] {{
            flex: 1 1 calc({share:.4f}% - 12px) !important;
          }}
        }}
        """
            )
    # `44` 2.1 硬規則：任何一段都不出現橫向捲動。`EXP-3` 的對照矩陣在窄寬度改成逐檔堆疊。
    # ⛔ **那個寬度不寫死在這裡** —— 它問的是 `logic.compare_stacks()`，
    #    與 `logic` 的斷點同一個真相源。寫死一個 `768` 的話，斷點一改這條 CSS 就悄悄脫隊。
    stack_below = max(
        (width for width in range(1, _MAX_PROBE_WIDTH + 1) if logic.compare_stacks(width)),
        default=0,
    )
    blocks.append(
        f"""
        @media (max-width: {stack_below}px) {{
          .exp-cmp-grid {{ display: block !important; }}
          .exp-cmp-col {{ width: 100% !important; }}
        }}
        """
    )
    return "".join(blocks)


def _base_css() -> str:
    return f"""
    .stApp {{ background: {theme.APP_BG}; }}
    .stApp, .stApp p, .stApp span, .stApp label {{ color: {theme.TEXT_PRIMARY}; }}
    .exp-title {{
      font-size: 1.45rem; font-weight: 700; letter-spacing: .04em;
      color: {theme.TEAL_BRIGHT}; border-bottom: 2px solid {theme.TEAL_DARK};
      padding-bottom: .4rem; margin-bottom: .2rem;
    }}
    .exp-sub {{ color: {theme.TEXT_MUTED}; font-size: .82rem; margin-bottom: 1rem; }}
    .exp-layer-label {{
      color: {theme.TEAL_BRIGHT}; font-size: .72rem; letter-spacing: .18em;
      text-transform: uppercase; margin: 1.1rem 0 .35rem;
    }}
    .exp-lamp {{
      display: flex; align-items: center; gap: .8rem;
      border: 1px solid var(--exp-tone); border-left: 5px solid var(--exp-tone);
      background: {theme.SURFACE}; border-radius: 8px; padding: .85rem 1rem;
    }}
    .exp-glyph {{ font-size: 1.25rem; line-height: 1; flex: 0 0 auto; }}
    /* ⛔ **2026-09-24 就地更正：這一枚原本與 `.exp-badge` 在視覺上逐項相同**
       （`inline-block` ／ `.68rem` ／ `border-radius:999px` ／同樣的 padding ／`1px solid`），
       而它的字面之一（「取數失敗」）**正是 `44` 5.2 那七個封閉字面值之一**、顏色也是 44 給它的紅
       —— 於是「本頁一枚狀態徽章也沒有掛」只在模型的 `_kind` 記帳上成立，**畫面上不成立**。
       本輪把它改成**方角、左側粗邊、無外框**的標記，與藥丸形的徽章一眼分得開；
       `test_結論燈的狀態標記在視覺上不是一枚徽章` 逐項釘住這個差別。
       ⚠️ **登記：`44` 沒有訂「結論燈的狀態標記算不算一枚徽章」。** 本頁的處置是
       「**讓它看起來不是**」，而不是「把它宣告成徽章」—— 後者做不到，因為它的四個字面裡
       有三個（條件未設／零檔符合／有檔符合）**不在**那七個之內，宣告成徽章當場違反 5.2 的封閉列舉。 */
    .exp-stword {{
      display: inline-block; font-size: .68rem; font-weight: 700; border-radius: 2px;
      padding: .05rem .4rem .05rem .35rem; border: 0;
      border-left: 3px solid var(--exp-tone); color: var(--exp-tone);
      background: {theme.STATE_GRAY_BG}; margin-right: .5rem; letter-spacing: .02em;
    }}
    .exp-lamp-text {{ font-size: 1.02rem; font-weight: 600; color: var(--exp-tone); }}
    .exp-code {{ color: {theme.TEXT_MUTED}; font-size: .78rem; margin-left: auto; }}
    .exp-card {{
      border: 1px solid var(--exp-tone); background: {theme.SURFACE};
      border-radius: 8px; padding: .9rem 1rem; height: 100%;
    }}
    .exp-card-head {{
      display: flex; align-items: baseline; gap: .5rem; flex-wrap: wrap;
      border-bottom: 1px solid {theme.BORDER}; padding-bottom: .45rem; margin-bottom: .6rem;
    }}
    .exp-card-code {{ color: {theme.TEXT_MUTED}; font-size: .72rem; }}
    .exp-card-title {{ font-weight: 700; color: {theme.TEAL_BRIGHT}; }}
    .exp-note {{ font-size: .78rem; color: {theme.TEXT_SECOND}; margin: .25rem 0; }}
    .exp-detail {{
      border-top: 1px dashed {theme.BORDER}; margin-top: .6rem; padding-top: .5rem;
      font-size: .76rem; color: {theme.TEXT_MUTED};
    }}
    .exp-errline {{
      color: {theme.STATE_GRAY}; background: {theme.STATE_GRAY_BG};
      border: 1px solid {theme.STATE_GRAY}; border-radius: 5px;
      padding: .4rem .6rem; margin: .4rem 0; font-size: .78rem;
    }}
    .exp-fetchfail {{
      color: {theme.ERR_MSG_FG}; background: {theme.ERR_MSG_BG};
      border: 1px solid {theme.ERR_MSG_EDGE}; border-radius: 5px;
      padding: .4rem .6rem; margin: .4rem 0; font-size: .78rem;
    }}
    .exp-empty {{
      color: {theme.STATE_GRAY}; border: 1px dashed {theme.EDGE};
      border-radius: 6px; padding: .55rem .7rem; margin: .4rem 0; font-size: .85rem;
    }}
    .exp-scroll {{ overflow-x: auto; }}
    .exp-table {{ width: 100%; border-collapse: collapse; font-size: .8rem; }}
    .exp-table th {{
      text-align: left; color: {theme.TEXT_SECOND}; font-weight: 600;
      border-bottom: 1px solid {theme.BORDER}; padding: .3rem .45rem; white-space: nowrap;
    }}
    .exp-table td {{
      border-bottom: 1px solid {theme.BORDER}; padding: .3rem .45rem;
      color: {theme.TEXT_PRIMARY};
    }}
    .exp-cmp-grid {{ display: flex; gap: 10px; }}
    .exp-cmp-col {{
      flex: 1 1 0; border: 1px solid {theme.BORDER}; border-radius: 6px;
      padding: .45rem .6rem; min-width: 0;
    }}
    .exp-cmp-head {{
      font-size: .8rem; font-weight: 700; color: {theme.TEXT_SECOND};
      border-bottom: 1px solid {theme.BORDER}; padding-bottom: .3rem; margin-bottom: .35rem;
    }}
    .exp-cmp-row {{ display: flex; justify-content: space-between; gap: .5rem; margin: .2rem 0; }}
    .exp-cmp-label {{ color: {theme.TEXT_MUTED}; font-size: .74rem; }}
    .exp-cmp-value {{ font-size: .88rem; font-weight: 600; color: var(--exp-cell); text-align: right; }}
    .exp-badge {{
      display: inline-block; font-size: .68rem; border-radius: 999px;
      padding: .05rem .5rem; margin-right: .35rem;
      border: 1px solid var(--exp-badge); color: var(--exp-badge);
    }}
    .exp-badge-ph {{ border-style: dashed; }}
    .exp-tail {{ color: {theme.STATE_GRAY}; font-size: .74rem; }}
    .exp-footer {{
      margin-top: 1.4rem; border-top: 1px solid {theme.BORDER}; padding-top: .6rem;
      color: {theme.TEXT_MUTED}; font-size: .74rem;
    }}
    .exp-sortcap {{ color: {theme.TEXT_MUTED}; font-size: .74rem; margin-bottom: .3rem; }}
    """


# ───────────────────────── 小零件 ─────────────────────────


def _badge_html(badge: dict) -> str:
    extra = " exp-badge-ph" if badge.get("_placeholder") else ""
    return (
        f'<span class="exp-badge{extra}" style="--exp-badge:{_tone(badge["_tone"])}">'
        f'{_esc(badge["text"])}</span>'
    )


def _badges_html(badges) -> str:
    return "".join(_badge_html(b) for b in badges or ())


def _lines(lines, css="exp-note") -> None:
    for line in lines or ():
        st.markdown(f'<div class="{css}">{_esc(line)}</div>', unsafe_allow_html=True)


def _error_lines(block: dict) -> None:
    """畫存檔失敗那一族：**先失敗訊息本身，再登記註記** —— 兩者住在不同的鍵。

    ⛔ 一個鍵不裝兩種東西（同 `fetch_fail_lines` 拆出來的理由）。
    """
    for line in block.get("error_lines", ()) or ():
        st.markdown(f'<div class="exp-errline">{_esc(line)}</div>', unsafe_allow_html=True)
    for line in block.get("save_fail_notes", ()) or ():
        st.markdown(f'<div class="exp-errline">{_esc(line)}</div>', unsafe_allow_html=True)


def _fetch_fail_lines(block: dict) -> None:
    """畫取數失敗那一族。

    ⛔ **2026-09-24 就地更正：上一版是 `for line in detail_lines: if logic.ERR_TEXT in line:`。**
    那有兩個問題：(a) **畫面層在分類模型內容**，與本檔 docstring 的「一個判定也不做」不一致；
    (b) 挑出來畫完紅框之後，`_lines(detail_lines)` 又把同一行原封再畫一次 ——
    **本組實測（量測日 2026-09-24，修復前）：`profilefail` 印 11 次、`twofail` 17 次、`navfail` 10 次。**
    現在讀模型自己的 `fetch_fail_lines` 鍵，**不比對字串，也不重複**。
    """
    for line in block.get("fetch_fail_lines", ()) or ():
        st.markdown(f'<div class="exp-fetchfail">{_esc(line)}</div>', unsafe_allow_html=True)


def _buttons(block: dict, prefix: str) -> None:
    for index, button in enumerate(block.get("buttons", ()) or ()):
        st.button(
            button["label"],
            key=f"{prefix}_btn_{index}",
            disabled=not button["_enabled"],
            help=button["disabled_reason"] or None,
        )


def _card_open(block: dict) -> None:
    st.markdown(
        f'<div class="exp-card" style="--exp-tone:{_tone(block["_tone"])}">'
        f'<div class="exp-card-head"><span class="exp-card-code">{_esc(block["code"])}</span>'
        f'<span class="exp-card-title">{_esc(block["title"])}</span></div>',
        unsafe_allow_html=True,
    )


def _card_close(block: dict) -> None:
    st.markdown(
        f'<div class="exp-detail">{_badges_html(block["badges"])}'
        f'{_esc(block["redline_note"])}</div></div>',
        unsafe_allow_html=True,
    )


def _notes(block: dict) -> None:
    for line in block.get("notes", ()) or ():
        st.markdown(f'<div class="exp-empty">{_esc(line)}</div>', unsafe_allow_html=True)


# ───────────────────────── 層 1 ─────────────────────────


def _render_exp0(block: dict) -> None:
    tone = _tone(block["_tone_override"])
    st.markdown(
        f'<div class="exp-lamp" style="--exp-tone:{tone}">'
        f'<span class="exp-glyph">{_esc(block["glyph"])}</span>'
        f'<span><span class="exp-stword">狀態：{_esc(block["state_word"])}</span>'
        f'<span class="exp-lamp-text">{_esc(block["text"])}</span></span>'
        f'<span class="exp-code">{_esc(block["code"])}　{_esc(block["title"])}</span></div>',
        unsafe_allow_html=True,
    )
    st.caption(block["answers"])
    _fetch_fail_lines(block)
    if block["condition_lines"]:
        st.caption(block["condition_caption"])
        _lines(block["condition_lines"])
    _lines(block["detail_lines"], css="exp-detail")


# ───────────────────────── 層 2 ─────────────────────────


def _render_exp1(block: dict) -> None:
    _card_open(block)
    st.caption(block["answers"])
    _notes(block)
    for row in block["_rows"]:
        cells = st.columns([3, 2, 2, 2])
        for cell, field in zip(cells, row["_fields"]):
            with cell:
                st.text_input(
                    field["label"],
                    value=field["_value"],
                    placeholder=field["placeholder"],
                    key=f"exp1_{field['name']}",
                )
        with cells[3]:
            st.button(row["_button"]["label"], key=f"exp1_clear_{row['_index']}")
        if row["tail_text"]:
            st.markdown(
                f'<div class="exp-tail">{_esc(row["tail_text"])}</div>',
                unsafe_allow_html=True,
            )
    _buttons(block, "exp1")
    _error_lines(block)
    _lines(block["detail_lines"], css="exp-detail")
    _card_close(block)


def _render_exp2(block: dict, *, scenario: str) -> None:
    _card_open(block)
    st.caption(block["answers"])
    _notes(block)
    st.markdown(
        f'<div class="exp-sortcap">{_esc(block["sort_caption"])}</div>',
        unsafe_allow_html=True,
    )
    if block["_rows"]:
        head = "".join(f"<th>{_esc(label)}</th>" for label in block["column_labels"])
        body = ""
        for row in block["_rows"]:
            cells = "".join(
                f'<td style="color:{_tone(row["_cells"][key]["_tone"])}">'
                f'{_esc(row["_cells"][key]["text"])}</td>'
                for key in block["column_keys"]
            )
            body += f"<tr>{cells}</tr>"
        st.markdown(
            f'<div class="exp-scroll"><table class="exp-table">'
            f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>",
            unsafe_allow_html=True,
        )
        # 兩組勾選框。`44` `EXP-2` 規則欄：兩組並存、互不連動。
        for row in block["_rows"]:
            code = row["_fund_code"]
            columns = st.columns([3, 2, 2])
            with columns[0]:
                st.markdown(
                    f'<div class="exp-note">{_esc(code)}</div>', unsafe_allow_html=True
                )
            for column, group in zip(columns[1:], (logic.GROUP_COMPARE, logic.GROUP_WATCH)):
                box = row["_checkboxes"][group]
                with column:
                    st.checkbox(
                        box["label"],
                        value=box["_checked"],
                        disabled=not box["_enabled"],
                        help=box["disabled_reason"] or None,
                        # ⚠️ widget 的鍵也要帶情境名，理由同 `logic.checked_key()`：
                        #    在瀏覽器裡換 `?scenario=` 是同一個 session，鍵不帶情境名
                        #    上一個情境勾好的框會原封留在新情境的畫面上。
                        key=_widget_key(group, code, scenario),
                        on_change=_toggle,
                        args=(group, code, scenario),
                    )
                    if box["note"]:
                        st.markdown(
                            f'<div class="exp-tail">{_esc(box["note"])}</div>',
                            unsafe_allow_html=True,
                        )
    _fetch_fail_lines(block)
    _lines(block["detail_lines"], css="exp-detail")
    _card_close(block)


def _render_exp3(block: dict) -> None:
    _card_open(block)
    st.caption(block["answers"])
    _notes(block)
    if block["_columns"]:
        cols = ""
        for column in block["_columns"]:
            rows_html = "".join(
                f'<div class="exp-cmp-row"><span class="exp-cmp-label">{_esc(label)}</span>'
                f'<span class="exp-cmp-value" '
                f'style="--exp-cell:{_tone(column["_cells"][key]["_tone"])}">'
                f'{_esc(column["_cells"][key]["text"])}</span></div>'
                for key, label in zip(block["row_keys"], block["row_labels"])
            )
            cols += (
                f'<div class="exp-cmp-col">'
                f'<div class="exp-cmp-head">{_esc(column["head_text"])}</div>'
                f"{rows_html}</div>"
            )
        st.markdown(f'<div class="exp-cmp-grid">{cols}</div>', unsafe_allow_html=True)
    _fetch_fail_lines(block)
    _lines(block["detail_lines"], css="exp-detail")
    _card_close(block)


# ───────────────────────── 層 3 與層 4 ─────────────────────────


def _expander(block: dict):
    return st.expander(
        f"{block['code']}　{block['title']}　—　{block['summary_text']}",
        expanded=block["_default_open"],
    )


def _render_exp4(block: dict, *, scenario: str) -> None:
    with _expander(block):
        st.caption(block["answers"])
        _notes(block)
        columns = st.columns(len(block["_options"]))
        for column, option in zip(columns, block["_options"]):
            with column:
                # ⛔ **這一組五個框是唯讀的，理由寫在畫面上（見本塊 detail_lines 最後一行）。**
                #    接線會讓「**基金名關掉、其他開著**」變成走得到的狀態，
                #    而 `44` 只保障「全不勾」那一種，**沒有寫這一種算不算可接受**。
                #    ⚠️ **試過鎖住「基金名」那一格，行不通**：把它固定成已勾，
                #    `nocond` 就違反 `44` 1.1 判準「首次開啟本頁卡片上沒有任何已勾選的選項」
                #    （實測當場紅燈）；只鎖它、不鎖別的，使用者從 `nocond` 勾一個 `ccy`
                #    照樣走到同一個未裁決狀態。**兩條限制同時成立時，這一組只能先不接。**
                #    值照舊反映真實狀態 ⇒ `44` 1.1 不受影響；狀態變化由情境示範。
                st.checkbox(
                    option["label"],
                    value=option["_checked"],
                    key=f"exp4_col_{option['_column']}__{scenario}",
                    disabled=True,
                )
        st.selectbox(
            "排序欄位",
            block["sort_options"],
            index=block["sort_options"].index(block["sort_shown"]),
            key=f"exp4_sort__{scenario}",
        )
        _buttons(block, "exp4")
        _error_lines(block)
        _lines(block["detail_lines"], css="exp-detail")


def _render_exp5(block: dict) -> None:
    with _expander(block):
        st.caption(block["answers"])
        _buttons(block, "exp5")
        _error_lines(block)
        _lines(block["detail_lines"], css="exp-detail")


def _render_exp6(block: dict) -> None:
    with _expander(block):
        st.caption(block["answers"])
        _notes(block)
        for node in block["_fields"]:
            st.markdown(
                f'<div class="exp-cmp-row"><span class="exp-cmp-label">'
                f'{_esc(node["label"])}</span>'
                f'<span class="exp-cmp-value" style="--exp-cell:{_tone(node["_tone"])}">'
                f'{_esc(node["text"])}</span></div>',
                unsafe_allow_html=True,
            )
        _fetch_fail_lines(block)
        _lines(block["detail_lines"], css="exp-detail")


def _render_exp7(block: dict) -> None:
    with _expander(block):
        st.caption(block["answers"])
        _notes(block)
        if block["_rows"]:
            head = "".join(f"<th>{_esc(label)}</th>" for label in block["column_labels"])
            body = ""
            for row in block["_rows"]:
                tail = f' <span class="exp-tail">{_esc(row["tail_text"])}</span>' if row["tail_text"] else ""
                body += (
                    f'<tr><td>{_esc(row["condition_text"])}{tail}</td>'
                    f'<td>{_esc(row["before_text"])}</td>'
                    f'<td>{_esc(row["after_text"])}</td></tr>'
                )
            st.markdown(
                f'<div class="exp-scroll"><table class="exp-table">'
                f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>",
                unsafe_allow_html=True,
            )
        _lines(block["detail_lines"], css="exp-detail")


# ───────────────────────── 整頁 ─────────────────────────


def _widget_key(group: str, fund_code: str, scenario: str) -> str:
    return f"exp2_{group}_{fund_code}__{scenario}"


def _toggle(group: str, fund_code: str, scenario: str) -> None:
    """按下某一列某一組的勾選框。**翻轉之後是什麼由 logic 決定**，這裡只寫回 session_state。"""
    key = logic.checked_key(group, scenario)
    st.session_state[key] = logic.toggle_checked(
        st.session_state.get(key) or (),
        fund_code,
        checked=st.session_state[_widget_key(group, fund_code, scenario)],
    )


def _checked(group: str, scenario: str, fallback):
    """讀這一組的勾選狀態，**第一次進來時先把情境給的那一份種進 session_state**。

    ⛔ **不種進去會壞掉，而且壞得很安靜**：`_toggle()` 是從 `st.session_state` 讀舊值再翻轉的，
    如果那個鍵還不存在，它會從**空集合**開始 —— 於是使用者第一次按任何一個框，
    情境原本勾好的那幾檔會**整批消失**，畫面上只剩剛按的那一個。
    （本輪實測：`full` 原本勾兩檔，按第五列的「觀察清單」之後變成一檔，不是三檔。）
    ⚠️ **這是「同一份狀態被兩個地方各讀一份」的老問題** —— 讀的那一邊有 fallback、
    寫的那一邊沒有。**修法是讓它只有一份**：種進去之後兩邊讀的都是 session_state。
    """
    key = logic.checked_key(group, scenario)
    try:
        if key not in st.session_state:
            st.session_state[key] = tuple(fallback)
        return tuple(st.session_state[key])
    except Exception:
        # ⚠️ **登記（2026-09-24 第二輪稽核：這個裸 `except` 原本零登記）**：
        #    這裡吞掉**所有**例外、讓勾選狀態**無聲退回情境給的預設值**。
        #    ⛔ 諷刺的是它正上方那段 docstring 整段在講「不種進去會壞掉，**而且壞得很安靜**」。
        #    **為什麼仍然留著吞**：`st.session_state` 在非 script 執行緒（例如測試收集階段、
        #    縮圖擷取）會拋 `StreamlitAPIException`；讓整頁炸掉**不會比退回預設值更誠實**，
        #    因為那不是資料問題，是宿主環境問題。
        #    ⛔ **界線**：這裡退的是**使用者的勾選狀態**，**不是任何一個數值** ——
        #    §1 管的是「不要編造資料」，這裡一個資料值都沒有被編出來。
        #    ⚠️ 真正的資料層照舊 Fail Loud（`fixtures.scenario()` 對不認得的名字 `raise KeyError`）。
        return tuple(fallback)


def _exp4_overrides(dataset: dict, scenario: str) -> dict:
    """把 `EXP-4` 那五個勾選框與排序下拉的**當下值**讀出來餵回模型。

    ⛔ **2026-09-24 第二輪稽核抓到：這兩組控制項原本完全沒接線。**
    選了排序欄位之後，排序說明列仍印「依 `fund_code` 字面值排列（**未選排序欄位**）」
    —— **使用者操作之後畫面說了一句假話**。取消勾欄位則是 `EXP-2` 完全不動。
    ⚠️ 同一頁 `EXP-2` 的對照勾選框**是有接線的**，一組接一組不接、而且一句登記都沒有。

    **第一次進來（鍵還不存在）時回空 dict ＝ 不覆寫**，模型走已存值，
    行為與接線前完全相同 —— 接線只改「使用者動過之後」會發生什麼。
    """
    out = {}
    try:
        # ⛔ **欄位勾選刻意不覆寫** —— 那一組是唯讀的，理由見 `_render_exp4` 與畫面上那一行。
        sort_key = f"exp4_sort__{scenario}"
        if sort_key in st.session_state:
            label = st.session_state[sort_key]
            out["sort_column"] = logic.column_for_label(label)
    except Exception:
        # ⚠️ 讀不到 session_state 就**不覆寫**（回空 dict），模型走已存值。
        #    這裡刻意不吞成「空選擇」——那會把讀取失敗演成「使用者把欄位全取消了」。
        return {}
    return out


# 網址上原本要的那個情境名（可能是打錯的），給退回提示用。
_ASKED: dict = {}


def _pick_scenario() -> str:
    """情境用查詢參數挑，**不做成輸入欄** ——
    `44` 1.1 節判準要求「沒有一列輸入欄帶有非空的預設值」，
    而一個情境下拉選單必然帶一個預設值。用 ?scenario=… 就不動到那張表。
    """
    try:
        name = dict(st.query_params).get("scenario")
    except Exception:
        name = None
    _ASKED["scenario"] = name
    # ⛔ 閘門讀的就是 `fixtures` 那一份**唯一的**清單。
    #    姊妹頁 `hld` 2026-09-24 就因為閘門讀了另一份較短的清單，
    #    讓三個新做的畫面**頁面永遠選不到、任何測試也沒渲染過**。
    #
    # ⚠️ **就地登記：這是一次「安靜的退回」，而本檔別處一律 Fail Loud —— 為什麼這裡可以。**
    #    網址列打錯情境名時，本函式**不報錯**，直接退回清單第一個情境。
    #    它**不牴觸 §1**，理由是它退的東西不是資料：這一格挑的是「**要展示哪一份假資料**」，
    #    **沒有任何一個數值被編出來或被替換**。真正的資料層照舊大聲炸 ——
    #    `fixtures.scenario()` 對不認得的名字 `raise KeyError("沒有這個情境：…")`
    #    （本組實測 2026-09-24），本閘門只是讓它**走不到**那一步。
    #    ⛔ **決策者：AI 總管（本組），不是 `44`** —— `44` 沒有規範這一頁的示範情境怎麼挑。
    #    由 `test_網址打錯情境名時退回預設而不是炸掉` 釘住；拿掉下面兩行，該條轉紅。
    if name not in fixtures.ALL_SCENARIO_NAMES:
        name = fixtures.ALL_SCENARIO_NAMES[0]
    return name


def _pick_save_failed() -> bool:
    """存檔失敗是一枚與情境**正交**的開關，不是多出來的一種情境（理由見 `fixtures`）。

    ⚠️ 刻意不在這裡寫「第幾種」—— 那是一個會隨情境增減而漂走的數字。
    """
    try:
        raw = dict(st.query_params).get("savefail")
    except Exception:
        raw = None
    return str(raw).lower() in ("1", "true", "yes")


# ⚠️ `EXP-2` 與 `EXP-4` 需要情境名（widget 鍵要帶它），所以不進這張表，在 `render()` 裡另外接。
_RENDERERS = {
    "EXP-1": _render_exp1,
    "EXP-3": _render_exp3,
    "EXP-5": _render_exp5,
    "EXP-6": _render_exp6,
    "EXP-7": _render_exp7,
}


def render() -> None:
    st.markdown(f"<style>{_base_css()}{_grid_css()}</style>", unsafe_allow_html=True)

    scenario = _pick_scenario()
    save_failed = _pick_save_failed()
    params = fixtures.scenario_with(scenario, save_failed=save_failed)

    model = logic.build_page_model(
        params["dataset"],
        draft_rules=params.get("draft_rules"),
        compare_checked=_checked(
            logic.GROUP_COMPARE, scenario, params.get("compare_checked", ())
        ),
        watch_checked=_checked(
            logic.GROUP_WATCH, scenario, params.get("watch_checked", ())
        ),
        save_failed=save_failed,
        **_exp4_overrides(params["dataset"], scenario),
    )

    st.markdown(
        f'<div class="exp-title">{_esc(model["title"])}</div>', unsafe_allow_html=True
    )
    st.markdown(
        f'<div class="exp-sub">{_esc(model["answers"])}　·　'
        f'資料為假資料，每一個會隨資料變的數都帶「示意」二字　·　'
        f'情境 {_esc(fixtures.SCENARIO_LABELS.get(scenario, scenario))}'
        # ⚠️ 這一行的字面住在 `logic`，理由見那邊的註解（它刻意與空狀態欄那句話不同字）。
        f'{"　·　" + logic.TEXT_SAVEFAIL_BANNER if save_failed else ""}</div>',
        unsafe_allow_html=True,
    )

    # ⛔ **2026-09-24 第二輪稽核：閘門安靜退回，畫面上一個字都沒說。**
    #    判定（要不要說、說什麼）住在 `logic`；這裡只負責畫。
    _fallback = logic.scenario_fallback_note(
        _ASKED.get("scenario"), scenario, fixtures.SCENARIO_LABELS.get(scenario, scenario)
    )
    if _fallback:
        st.markdown(
            f'<div class="exp-errline">{_esc(_fallback)}</div>', unsafe_allow_html=True
        )

    st.markdown('<div class="exp-layer-label">層 1　結論</div>', unsafe_allow_html=True)
    _render_exp0(logic.find_block(model, "EXP-0"))

    st.markdown(
        '<div class="exp-layer-label exp-layer2">層 2　核心卡</div>',
        unsafe_allow_html=True,
    )
    for column, code in zip(st.columns(3), logic.codes_in_layer(model, 2)):
        with column:
            block = logic.find_block(model, code)
            if code == "EXP-2":
                _render_exp2(block, scenario=scenario)
            else:
                _RENDERERS[code](block)

    st.markdown(
        '<div class="exp-layer-label exp-layer3">層 3　操作（預設收合）</div>',
        unsafe_allow_html=True,
    )
    # `44` 2.1：層 3 只有兩塊，兩塊並排同一列，第三欄空著。
    for column, code in zip(st.columns(3), logic.codes_in_layer(model, 3)):
        with column:
            block = logic.find_block(model, code)
            if code == "EXP-4":
                _render_exp4(block, scenario=scenario)
            else:
                _RENDERERS[code](block)

    st.markdown(
        '<div class="exp-layer-label">層 4　佐證（預設收合）</div>', unsafe_allow_html=True
    )
    for code in logic.codes_in_layer(model, 4):
        _RENDERERS[code](logic.find_block(model, code))

    footer = "　".join(_esc(line) for line in model["footer_lines"])
    st.markdown(
        f'<div class="exp-footer">本頁不負責什麼：{footer}<br/>'
        f'{_badges_html(model["footer_badges"])}</div>',
        unsafe_allow_html=True,
    )
