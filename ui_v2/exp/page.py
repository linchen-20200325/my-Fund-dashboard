# -*- coding: utf-8 -*-
"""標的探索的 Streamlit 渲染層。

本檔**只負責畫**：四狀態、欄數、文案模板、結論燈、篩選與排序全部住在 logic.py，
這裡一個判定也不做。色票與對比住在 theme.py，假資料住在 fixtures.py。

本檔不 import 舊 repo 任何模組，不發任何網路請求，**不寫任何色碼字面值**
（每一個顏色都從 theme 取 —— 那一份每一組都算過對比）。
"""

from __future__ import annotations

import re

import streamlit as st

from . import fixtures, live, logic, theme

_MAX_PROBE_WIDTH = 2000


# 換行與連續空白（只認 ASCII 空白；全形空白「　」是版面用字，不折）。比照 `ui_v2/hld/page.py`（本頁不 import hld）。
_WS_RUN = re.compile(r"[ \t\r\n\f\v]+")
# 會被 Streamlit 的 Markdown 讀成語法的 ASCII 字元（同 hld）；一律改寫成數字字元參照（只當字面文字，不能組語法）。
_MD_ACTIVE = "\\`*_{}[]()#!|~$:"
# 一張表、一次走完（先 `html.escape` 再換字會把 `&#x27;` 的 `#` 再換一次；反過來會把 `&#36;` 的 `&` 換掉）。
_MD_ENTITY = {ord(ch): f"&#{ord(ch)};" for ch in _MD_ACTIVE + "&<>\"'"}


def _esc(text) -> str:
    """任何字串上畫面前一律走這裡（2026-10-14 修正輪 Q M1，比照 `ui_v2/hld/page.py::_esc`）。

    ~~`html.escape(str(text))`~~ → 上游錯誤原文可以是任何東西：只做 HTML escape 時，原文裡的空行會讓 Markdown
    跳出 HTML 區塊、`## ` 變成標題、`|` 變成表格（有意識的更正，不是漏刪；決策者：AI 總管）。三步：
      1. 換行與連續空白折成一個空格；
      2. HTML 特殊字元（`& < > " '`）改寫成字元參照（標籤以純文字呈現，`title` 屬性同樣安全）；
      3. Markdown 語法字元改寫成字元參照。
    不截斷。
    """
    return _WS_RUN.sub(" ", str(text)).translate(_MD_ENTITY)


def _title_attr(node: dict) -> str:
    """規則 10（2026-10-14 C2）：值旁的來源 tooltip。屬性值同樣經 `_esc`（含引號、換行、Markdown 字元）。"""
    tip = node.get("source_tip")
    return f' title="{_esc(tip)}"' if tip else ""


def _src_html(node: dict) -> str:
    """規則 10：值旁的簡短來源標示（不加欄）。樣式在 `theme.SOURCE_TAG_CSS`。"""
    tag = node.get("source_tag")
    return f'<span class="exp-src">{_esc(tag)}</span>' if tag else ""


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
                f'<td style="color:{_tone(row["_cells"][key]["_tone"])}"{_title_attr(row["_cells"][key])}>'
                f'{_esc(row["_cells"][key]["text"])}{_src_html(row["_cells"][key])}</td>'
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
                f'style="--exp-cell:{_tone(column["_cells"][key]["_tone"])}"{_title_attr(column["_cells"][key])}>'
                f'{_esc(column["_cells"][key]["text"])}{_src_html(column["_cells"][key])}</span></div>'
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


def _render_exp4(block: dict, *, scenario: str, save_click=None, editable: bool = True) -> None:
    """`save_click`：正式模式才有（`(on_click, args)`）。有傳時五個欄位勾選框可勾、排序下拉與存檔接上
    `user_setting`（客戶 2026-10-13 裁示）；**`EXP-2` 照舊只吃已存值**（判定在 `live.build_live_model`）。"""
    if save_click is not None:
        _render_exp4_live(block, save_click=save_click, editable=editable)
        return
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


def _render_exp5(block: dict, *, save_click=None) -> None:
    with _expander(block):
        st.caption(block["answers"])
        _fetch_fail_lines(block)
        if save_click is None:
            _buttons(block, "exp5")
        else:
            _live_buttons(block, "exp5", {live.ACTION_SAVE: save_click})
        _error_lines(block)
        _lines(block["detail_lines"], css="exp-detail")


# ───────────────────────── 正式模式（客戶 2026-10-13 裁示） ─────────────────────────
#
# 分工（判定全在 `live.build_live_model`）：輸入欄／勾選框**當下**的值只決定欄位怎麼畫與存檔寫什麼；
# 正式結果（篩選、顯示欄、排序、觀察清單）只吃 `load_live` 交回的**已存**設定，存檔後下一次重跑才生效。

# 正式模式的 widget 鍵用另一組前綴與情境名，不與示範模式（`?scenario=`）的鍵相撞。
# 〔已搬〕原本在本檔定義的情境名 → 2026-10-14 移到 `live.LIVE_SCENARIO`（值不變；有意識的搬移，不是漏刪）。
# 正式模式 `EXP-1` 條件列的當下內容（每列帶自己的識別碼 `_id`，刪一列不讓其他列的輸入欄錯位）。
_RULES_STATE = "_exp_live_rules"
_RULE_SEQ_STATE = "_exp_live_rule_seq"
# 按「存檔」那一次的逐鍵結果（`{鍵: None 或失敗訊息原文}`）：按鈕那一次的事，不是讀表的結果。
_SAVE_RESULTS_STATE = "_exp_save_results"
_SORT_KEY = "exp4live_sort"
# 2026-10-13 稽核 L 回修：本 session 的輸入欄是用哪一版已存值填的（指紋 ＋ 那一版本身）。
_SEEDED_STATE = "_exp_live_seeded_fp"
_SEEDED_SETTINGS_STATE = "_exp_live_seeded_settings"


def _rule_key(uid: int, name: str) -> str:
    return f"exp1live_{uid}_{name}"


def _col_key(column: str) -> str:
    return f"exp4live_col_{column}"


def _next_rule_id() -> int:
    uid = st.session_state.get(_RULE_SEQ_STATE, 0) + 1
    st.session_state[_RULE_SEQ_STATE] = uid
    return uid


def _current_rules() -> list:
    """條件列的**當下**內容（輸入欄有值就取輸入欄的值）。session 裡還沒有條件列時回空。"""
    out = []
    for row in st.session_state.get(_RULES_STATE) or ():
        uid = row["_id"]
        out.append({"_id": uid, **{name: st.session_state.get(_rule_key(uid, name), row[name])
                                    for name in ("field", "op", "value")}})
    return out


def _seed_live_fields(settings, settings_error) -> None:
    """以**已存**設定填輸入欄／勾選框（`44` `EXP-1`／`EXP-4` 判準：重新載入後與存檔前逐字相同）。

    ~~狀態不在 session 裡時才填；已在 session 裡就不動。~~
    → **2026-10-13 稽核 L 回修（有意識的更正，不是漏刪；決策者：AI 總管）**：舊寫法在「讀設定失敗」那一輪
    建起來的空白勾選框，下一輪讀成功後**不會**改回已存值，按存檔就把空值蓋回雲端（稽核 L 實測試算表變成 `[]`）。
    現行：記下「本 session 用哪一版已存值填過」的指紋；讀得到設定、而且指紋與上次填入的不同
    （首次、讀失敗後恢復、他處改了設定）時，**強制以已存值覆寫**條件列、欄位勾選、排序下拉，並清掉上一次
    存檔的逐鍵結果。指紋相同時不動（使用者正在編的值留著）。存檔成功後由 `_after_saves` 更新指紋。
    讀不到設定時一格都不填、也不記指紋（沒有已存值可填；不拿猜的值去填）。
    ⚠️ 這不是「系統代填」（G3†）：填的是使用者自己存過的值；從未存過的欄位維持空白、不勾。
    ⚠️ 讀不到的那一輪**清掉指紋**：那一輪沒有建 `EXP-1`／`EXP-4` 的輸入欄，streamlit 會把沒畫出來的輸入欄狀態
    清掉；恢復後若指紋仍與讀失敗前相同而不重填，空白的勾選框就會被存回去。清掉指紋 ⇒ 恢復那一輪一定重填。
    """
    if settings_error:
        st.session_state.pop(_SEEDED_STATE, None)
        return
    fingerprint = live.settings_fingerprint(settings)
    if st.session_state.get(_SEEDED_STATE) == fingerprint:
        return
    for row in st.session_state.get(_RULES_STATE) or ():
        for name in ("field", "op", "value"):
            st.session_state.pop(_rule_key(row["_id"], name), None)
    st.session_state[_RULES_STATE] = [
        {"_id": _next_rule_id(), **rule} for rule in settings.get(live.KEY_RULES) or ()
    ]
    saved_columns = set(settings.get(live.KEY_COLUMNS) or ())
    for column in logic.COLUMN_ORDER:
        st.session_state[_col_key(column)] = column in saved_columns
    saved_sort = settings.get(live.KEY_SORT)
    st.session_state[_SORT_KEY] = logic.COLUMN_LABELS[saved_sort] if saved_sort else logic.TEXT_NO_SORT
    st.session_state.pop(_SAVE_RESULTS_STATE, None)
    st.session_state[_SEEDED_STATE] = fingerprint
    st.session_state[_SEEDED_SETTINGS_STATE] = dict(settings)


def _field_columns() -> list:
    return [c for c in logic.COLUMN_ORDER if st.session_state.get(_col_key(c)) is True]


def _field_sort():
    return logic.column_for_label(st.session_state.get(_SORT_KEY))


def _record_saves(results) -> None:
    merged = dict(st.session_state.get(_SAVE_RESULTS_STATE) or {})
    merged.update(results)
    st.session_state[_SAVE_RESULTS_STATE] = merged


def _on_add_rule() -> None:
    rows = _current_rules()
    rows.append({"_id": _next_rule_id(), "field": "", "op": "", "value": ""})
    st.session_state[_RULES_STATE] = rows


def _on_remove_rule(uid: int) -> None:
    st.session_state[_RULES_STATE] = [row for row in _current_rules() if row["_id"] != uid]
    for name in ("field", "op", "value"):
        st.session_state.pop(_rule_key(uid, name), None)


def _after_saves(entries, save_live) -> None:
    """寫入、記逐鍵結果；寫成功的鍵同步更新「已用哪一版已存值填過」的指紋（稽核 L 回修）——
    否則下一次重跑讀回剛存的值，會被當成「他處改了」而清掉這一次的存檔結果。"""
    results = live.run_saves(entries, save_live)
    _record_saves(results)
    seeded = st.session_state.get(_SEEDED_SETTINGS_STATE)
    if seeded is not None:
        updated = live.settings_after_saves(seeded, entries, results)
        st.session_state[_SEEDED_SETTINGS_STATE] = updated
        st.session_state[_SEEDED_STATE] = live.settings_fingerprint(updated)


def _on_save_rules(save_live) -> None:
    _after_saves(live.exp1_save_entries(_current_rules()), save_live)


def _on_save_columns(save_live) -> None:
    _after_saves(live.exp4_save_entries(_field_columns(), _field_sort()), save_live)


def _on_save_watch(save_live, saved_watchlist, settings_error) -> None:
    picked = _checked(logic.GROUP_WATCH, live.LIVE_SCENARIO, ())
    _after_saves(live.exp5_save_entries(saved_watchlist, picked, settings_error), save_live)


def _live_buttons(block: dict, prefix: str, clicks: dict) -> None:
    """依按鈕類別接 on_click（`clicks`：`{action_kind: (on_click, args)}`）；沒接的類別照舊只畫。"""
    for index, button in enumerate(block.get("buttons", ()) or ()):
        on_click, args = clicks.get(button["_action_kind"], (None, ()))
        st.button(
            button["label"],
            key=f"{prefix}live_btn_{index}",
            on_click=on_click,
            args=args,
            disabled=not button["_enabled"],
            help=button["disabled_reason"] or None,
        )


def _render_exp1_live(block: dict, rows: list, *, clicks: dict) -> None:
    """正式模式的 `EXP-1`：輸入列接上 session（`rows` 與 `block["_rows"]` 同序，帶 `_id`）。"""
    _card_open(block)
    st.caption(block["answers"])
    _notes(block)
    _fetch_fail_lines(block)
    for row, model_row in zip(rows, block["_rows"]):
        cells = st.columns([3, 2, 2, 2])
        for cell, field, name in zip(cells, model_row["_fields"], ("field", "op", "value")):
            with cell:
                st.text_input(
                    field["label"],
                    value=row[name] if _rule_key(row["_id"], name) not in st.session_state else "",
                    placeholder=field["placeholder"],
                    key=_rule_key(row["_id"], name),
                )
        with cells[3]:
            st.button(model_row["_button"]["label"], key=f"exp1live_clear_{row['_id']}",
                      on_click=_on_remove_rule, args=(row["_id"],))
        if model_row["tail_text"]:
            st.markdown(
                f'<div class="exp-tail">{_esc(model_row["tail_text"])}</div>',
                unsafe_allow_html=True,
            )
    _live_buttons(block, "exp1", clicks)
    _error_lines(block)
    _lines(block["detail_lines"], css="exp-detail")
    _card_close(block)


def _render_exp4_live(block: dict, *, save_click, editable: bool = True) -> None:
    """`editable=False`（已存設定讀不到）：不建任何可編輯的勾選框與下拉（稽核 L 回修）——
    那一輪建起來的空白狀態會留在 session 裡，恢復後被存回去蓋掉雲端。只畫失敗行與說明。"""
    with _expander(block):
        st.caption(block["answers"])
        _notes(block)
        _fetch_fail_lines(block)
        if not editable:
            _live_buttons(block, "exp4", {live.ACTION_SAVE: save_click})
            _error_lines(block)
            _lines(block["detail_lines"], css="exp-detail")
            return
        columns = st.columns(len(block["_options"]))
        for column, option in zip(columns, block["_options"]):
            with column:
                # 值一律由 session 決定（`_seed_live_fields` 以已存值填）；這裡傳 False ＝ 不預先勾任何一欄。
                st.checkbox(option["label"], value=False, key=_col_key(option["_column"]))
        st.selectbox("排序欄位", block["sort_options"], index=0, key=_SORT_KEY)
        _live_buttons(block, "exp4", {live.ACTION_SAVE: save_click})
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
                f'<span class="exp-cmp-value" style="--exp-cell:{_tone(node["_tone"])}"{_title_attr(node)}>'
                f'{_esc(node["text"])}{_src_html(node)}</span></div>',
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
                    f'<td>{_esc(row["after_text"])}</td>'
                    # 正式模式才有第四欄「無法判定」（AI 總管落地選擇；〔已撤〕舊註寫「客戶 2026-10-13 裁示」，
                    # 稽核 L 第七輪指出，有意識的更正，不是漏刪）；示範模式的列沒有這個鍵。
                    + (f'<td>{_esc(row["undet_text"])}</td>' if "undet_text" in row else "")
                    + '</tr>'
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


def render(*, load_live=None, save_live=None) -> None:
    """畫整頁。

    load_live：選填的載入函式（無參數，回傳 `{"dataset": 與 fixtures 情境同形, "notes": {...}}`）。
    不傳（None）時行為與加這個參數之前**完全相同**：照舊以 `?scenario=` 挑 fixtures 情境（示範模式）。
    傳入時（正式入口 `app_exp_live.py`）改由它取得資料，這一條路徑不讀 fixtures，
    組模型走 `live.build_live_model`（只吃已存設定、不帶示意字樣、缺的格寫原因）；頁首只印本頁的提問句。

    save_live：選填的寫入函式 `save_live(鍵, 值或 None, value_kind)`（`source.save_setting`；客戶 2026-10-13 裁示）。
    傳入時 `EXP-1`／`EXP-4`／`EXP-5` 的存檔寫進 `user_setting`，下一次重跑（重新讀 `user_setting`）才生效。
    只傳 `save_live` 不傳 `load_live` 是呼叫端的 bug，當場炸。
    """
    if load_live is None and save_live is not None:
        raise ValueError("save_live 要與 load_live 一起傳")
    st.markdown(f"<style>{_base_css()}{_grid_css()}{theme.SOURCE_TAG_CSS}</style>", unsafe_allow_html=True)
    if load_live is not None:
        _render_live(load_live, save_live)
        return

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


def _render_live(load_live, save_live) -> None:
    """正式模式整頁。判定全在 `live.build_live_model`；這裡只負責讀 session、接按鈕、畫。"""
    live_input = load_live()
    notes = live_input["notes"]
    settings = notes.get("settings") or {}
    settings_error = notes.get("settings_error")
    _seed_live_fields(settings, settings_error)
    rows = _current_rules()
    readable = not settings_error
    model = live.build_live_model(
        live_input,
        field_rules=rows if readable else None,
        field_columns=_field_columns() if readable else None,
        field_sort=_field_sort() if readable else None,
        compare_checked=_checked(logic.GROUP_COMPARE, live.LIVE_SCENARIO, ()),
        watch_checked=_checked(logic.GROUP_WATCH, live.LIVE_SCENARIO, ()),
        save_wired=save_live is not None,
        save_results=st.session_state.get(_SAVE_RESULTS_STATE),
    )
    noop = (None, ())
    exp1_clicks = {live.ACTION_ADD_ROW: (_on_add_rule, ())}
    exp4_click = exp5_click = noop
    if save_live is not None:
        exp1_clicks[live.ACTION_SAVE] = (_on_save_rules, (save_live,))
        exp4_click = (_on_save_columns, (save_live,))
        exp5_click = (_on_save_watch, (save_live, tuple(settings.get(live.KEY_WATCH) or ()), settings_error))

    st.markdown(f'<div class="exp-title">{_esc(model["title"])}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="exp-sub">{_esc(model["answers"])}</div>', unsafe_allow_html=True)

    st.markdown('<div class="exp-layer-label">層 1　結論</div>', unsafe_allow_html=True)
    _render_exp0(logic.find_block(model, "EXP-0"))

    st.markdown(
        '<div class="exp-layer-label exp-layer2">層 2　核心卡</div>',
        unsafe_allow_html=True,
    )
    for column, code in zip(st.columns(3), logic.codes_in_layer(model, 2)):
        with column:
            block = logic.find_block(model, code)
            if code == "EXP-1":
                _render_exp1_live(block, rows if readable else [], clicks=exp1_clicks)
            elif code == "EXP-2":
                _render_exp2(block, scenario=live.LIVE_SCENARIO)
            else:
                _RENDERERS[code](block)

    st.markdown(
        '<div class="exp-layer-label exp-layer3">層 3　操作（預設收合）</div>',
        unsafe_allow_html=True,
    )
    for column, code in zip(st.columns(3), logic.codes_in_layer(model, 3)):
        with column:
            block = logic.find_block(model, code)
            if code == "EXP-4":
                _render_exp4(block, scenario=live.LIVE_SCENARIO, save_click=exp4_click, editable=readable)
            else:
                _render_exp5(block, save_click=exp5_click)

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
