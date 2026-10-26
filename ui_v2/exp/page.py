# -*- coding: utf-8 -*-
"""標的探索的 Streamlit 渲染層。

本檔**只負責畫**：四狀態、欄數、文案模板、結論燈、篩選與排序全部住在 logic.py，
這裡一個判定也不做。色票與對比住在 theme.py，假資料住在 fixtures.py。

本檔不 import 舊 repo 任何模組，不發任何網路請求，**不寫任何色碼字面值**
（每一個顏色都從 theme 取 —— 那一份每一組都算過對比）。
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import streamlit as st

from .. import health, health_view, plain, readonly, sections, symbols
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


def _block_attr(block: dict, plain_mode: bool) -> str:
    """正式模式：塊代號只放進 `data-block` 屬性（畫面不可見；給測試與瀏覽器量測定位）。示範模式回空字串、畫面照舊。"""
    return f' data-block="{_esc(block["code"])}"' if plain_mode else ""


def _card_open(block: dict, *, plain_mode: bool = False) -> None:
    code_span = "" if plain_mode else f'<span class="exp-card-code">{_esc(block["code"])}</span>'
    st.markdown(
        f'<div class="exp-card" style="--exp-tone:{_tone(block["_tone"])}"{_block_attr(block, plain_mode)}>'
        f'<div class="exp-card-head">{code_span}'
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


def _render_exp0(block: dict, *, plain_mode: bool = False) -> None:
    tone = _tone(block["_tone_override"])
    # 燈右側那一格：正式模式只留標題（44 第七節第三小節之七其二第 1 條）；示範模式「代號　標題」照舊。
    code_title = _esc(block["title"]) if plain_mode else f'{_esc(block["code"])}　{_esc(block["title"])}'
    st.markdown(
        f'<div class="exp-lamp" style="--exp-tone:{tone}"{_block_attr(block, plain_mode)}>'
        f'<span class="exp-glyph">{_esc(block["glyph"])}</span>'
        f'<span><span class="exp-stword">狀態：{_esc(block["state_word"])}</span>'
        f'<span class="exp-lamp-text">{_esc(block["text"])}</span></span>'
        f'<span class="exp-code">{code_title}</span></div>',
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


def _render_exp2(block: dict, *, scenario: str, plain_mode: bool = False) -> None:
    _card_open(block, plain_mode=plain_mode)
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


# ── BL-0250 批次 3-B（44 第七節第三小節之十三；客戶 `DEC-2026-10-19-05`）：正式模式的結果清單 ──
# 每列下方一行：已在觀察清單（若是）與一枚「來源與取得時間」列展開（HTML `<details>`，預設收合；只放來源資訊）；
# 表格下方「對照」「觀察清單」兩份多選清單取代每列兩組勾選框。示範模式照舊走 `_render_exp2`，一字未改。
# 樣式只寫在這幾枚元素的 style 屬性：共用 CSS 一字不改（示範模式畫面不變）。
_PICK_KEYS = {logic.GROUP_COMPARE: "exp2live_pick_compare", logic.GROUP_WATCH: "exp2live_pick_watch"}


def _on_pick(group: str, shown: tuple) -> None:
    """多選清單改了 → 寫回 `logic.checked_key` 那一份勾選狀態（存檔與 `EXP-3`／`EXP-5` 照舊只讀那一份）。
    `shown`：這一次畫進清單的已選項；沒畫進清單的已選檔（看不到的、或超過上限沒放進去的）原樣留著（3-B 稽核回修第 1 條）。"""
    key = logic.checked_key(group, live.LIVE_SCENARIO)
    st.session_state[key] = live.merge_picks(
        st.session_state.get(key) or (), shown, st.session_state.get(_PICK_KEYS[group]) or ())


def _row_source_html(block: dict, row: dict, colspan: int) -> str:
    """結果清單每列下方那一行（正式模式）；沒有要畫的就回空字串。"""
    parts = []
    if live.already_watched(block, row["_fund_code"]):
        parts.append(
            f'<div style="color:{theme.TEXT_SECOND};font-size:.74rem">{_esc(logic.TEXT_ALREADY_WATCHED)}</div>'
        )
    rows = live.source_rows(block, row)
    if rows:
        head = "".join(f'<th style="white-space:nowrap">{_esc(label)}</th>' for label in live.ROW_SOURCE_LABELS)
        body = "".join("<tr>" + "".join(f"<td>{_esc(cell)}</td>" for cell in line) + "</tr>" for line in rows)
        parts.append(
            f'<details class="exp-rowsrc"><summary style="color:{theme.TEAL_BRIGHT};font-size:.74rem;cursor:pointer">'
            f"{_esc(live.ROW_SOURCE_TITLE)}</summary>"
            f'<div style="overflow-x:auto"><table class="exp-table" style="font-size:.72rem">'
            f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div></details>"
        )
    if not parts:
        return ""
    return f'<tr><td colspan="{colspan}" style="padding:.1rem .45rem .35rem">{"".join(parts)}</td></tr>'


def _render_picks(block: dict, *, hide_watch: bool = False) -> None:
    """表格下方兩份多選清單（`EXP-3`「對照」、`EXP-5`「觀察清單」；44 第七節第三小節之七其二第 5 條）。
    `hide_watch`：「觀察清單」那一份不畫（`EXP-5` 的輸入，存檔鈕拿掉後已不影響本次畫面結果；J-14 精神，2026-10-26）。
    「對照」那一份會即時改 `EXP-3`／`EXP-6`，照畫。"""
    options = tuple(live.pick_options(block))
    for group in live.PICK_GROUPS:
        if hide_watch and group == logic.GROUP_WATCH:
            continue
        key = _PICK_KEYS[group]
        # 畫之前先把勾選狀態放進輸入欄（只放本次選項裡的檔）：換頁回來或條件改了之後，輸入欄與勾選狀態一致。
        shown = live.shown_picks(
            st.session_state.get(logic.checked_key(group, live.LIVE_SCENARIO)) or (), options, live.PICK_CAPS[group])
        st.session_state[key] = shown
        st.multiselect(
            live.PICK_LABELS[group],
            options=list(options),
            format_func=lambda code, group=group: live.pick_label(block, code, group),
            key=key,
            max_selections=live.PICK_CAPS[group],
            placeholder=live.PICK_PLACEHOLDER,
            on_change=_on_pick,
            args=(group, tuple(shown)),
        )
        for line in live.pick_captions(group, len(st.session_state.get(key) or ())):
            st.caption(line)


def _render_exp2_live(block: dict, *, hide_watch: bool = False) -> None:
    _card_open(block, plain_mode=True)
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
            # BL-0250 批次 3-C（G2 第 8～10 列、新設計 H；客戶 2026-10-21 Q3）：格內只留值 —— 來源標示與滑鼠提示裡的來源、
            # 取得時間、資料日期只在每列展開；判定句、計數句照留在格內滑鼠提示；配息比那一格畫成 ◇ 時格內只留 ◇。
            # ~~`{_title_attr(cell)}…{_esc(cell["text"])}{_src_html(cell)}`~~（有意識的政策變更，不是漏刪；`DEC-2026-10-21-01`）。
            cells = ""
            for key in block["column_keys"]:
                view = live.result_cell_view(key, row["_cells"][key])
                tip = f' title="{_esc(view["tip"])}"' if view["tip"] else ""
                cells += (f'<td style="color:{_tone(row["_cells"][key]["_tone"])}"{tip}>'
                          f'{_esc(view["text"])}</td>')
            body += f"<tr>{cells}</tr>" + _row_source_html(block, row, len(block["column_keys"]))
        st.markdown(
            f'<div class="exp-scroll"><table class="exp-table">'
            f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>",
            unsafe_allow_html=True,
        )
        _render_picks(block, hide_watch=hide_watch)
    _fetch_fail_lines(block)
    _lines(block["detail_lines"], css="exp-detail")
    _card_close(block)


def _render_exp3(block: dict, *, plain_mode: bool = False) -> None:
    _card_open(block, plain_mode=plain_mode)
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


def _expander(block: dict, *, plain_mode: bool = False):
    # 正式模式標題去掉塊代號（44 第七節第三小節之七其二第 1 條）；示範模式照舊。
    head = block["title"] if plain_mode else f"{block['code']}　{block['title']}"
    return st.expander(
        f"{head}　—　{block['summary_text']}",
        expanded=block["_default_open"],
    )


def _render_exp4(block: dict, *, scenario: str, save_click=None, editable: bool = True,
                 plain_mode: bool = False) -> None:
    """`save_click`：正式模式才有（`(on_click, args)`）。有傳時五個欄位勾選框可勾、排序下拉與存檔接上
    `user_setting`（客戶 2026-10-13 裁示）；**`EXP-2` 照舊只吃已存值**（判定在 `live.build_live_model`）。"""
    if save_click is not None:
        _render_exp4_live(block, save_click=save_click, editable=editable, plain_mode=plain_mode)
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


def _render_exp5(block: dict, *, save_click=None, plain_mode: bool = False) -> None:
    with _expander(block, plain_mode=plain_mode):
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
        values = {name: st.session_state.get(_rule_key(uid, name), row[name]) for name in ("field", "op", "value")}
        # 「欄位」是下拉選單（Phase 3 P0-①）：還沒選 ＝ None，讀作空字串 —— 與原本文字欄留空的值相同，存檔判定照舊。
        if values["field"] is None:
            values["field"] = ""
        out.append({"_id": uid, **values})
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


FIELD_PLACEHOLDER = "請選擇欄位"


def _field_select(field: dict, row: dict) -> None:
    """`EXP-1`「欄位」下拉（44 第七節第三小節之七其二第 6 條）：從既有欄位中選、以中文名顯示。

    底層值照舊是欄位鍵（存檔內容不變）；沒有預設值（`index=None`）；不在可選清單裡的舊值照樣列為選項、
    可以原樣回存（是否寫得進去照舊由 `live.exp1_save_entries` 判定，本處不加不減）。"""
    key = _rule_key(row["_id"], "field")
    current = row["field"]
    options = list(logic.FUND_PROFILE_FIELDS)
    if current and current not in options:
        options.append(current)
    index = None
    if key not in st.session_state and current in options:
        index = options.index(current)
    st.selectbox(
        field["label"],
        options,
        index=index,
        format_func=plain.key_name,
        placeholder=field["placeholder"] or FIELD_PLACEHOLDER,
        key=key,
    )


def _render_detail_quiet(view: dict) -> None:
    """④ 收合區比照規則 5（客戶 Q5 (b)；44 第七節第三小節之十五）：標題「標題　—　一句原因」，打開只有那一行（樣式同收起卡原因行）。"""
    line = view["line"]
    css = "exp-fetchfail" if line["_tone"] == "紅" else "exp-empty"
    with st.expander(f"{view['title']}　—　{line['text']}", expanded=False):
        st.markdown(f'<div class="{css} exp-quiet-line">{_esc(line["text"])}</div>', unsafe_allow_html=True)


def _render_exp1_quiet(block: dict, view: dict, *, clicks: dict) -> None:
    """正式模式、整張卡主值全部讀不到時的收起畫法（新設計 B；44 第七節第三小節之十五）：卡名＋「（暫時收起）」＋原因行，
    不畫「這張卡回答什麼」那句、被原因行取代的重複 ⛔ 行與卡尾徽章；說明句、按鈕（含停用原因「暫不提供存檔」）、存檔失敗行與
    紅線說明照留（總管判定）。讀不到時本來就沒有條件列可畫（`rows` 由呼叫端給空的）。"""
    st.markdown(
        f'<div class="exp-card" style="--exp-tone:{_tone(block["_tone"])}"{_block_attr(block, True)}>'
        f'<div class="exp-card-head"><span class="exp-card-title">{_esc(block["title"])}</span>'
        f'<span class="exp-quiet-mark" style="color:{_tone("灰")}">{_esc(view["mark"])}</span></div>',
        unsafe_allow_html=True,
    )
    # 原因行沿用本頁失敗行與空狀態那兩格的樣式（⛔ `exp-fetchfail`、其餘 `exp-empty`；收起前「⛔ 此區塊暫時無法判定」就是畫在
    # `exp-fetchfail` 裡），與卡頭之間的間距照舊。
    for line in view["lines"]:
        css = "exp-fetchfail" if line["_tone"] == "紅" else "exp-empty"
        st.markdown(f'<div class="{css} exp-quiet-line">{_esc(line["text"])}</div>', unsafe_allow_html=True)
    _lines([line for line in block.get("notes", ()) or () if sections.quiet_keep(view, line)], css="exp-empty")
    _lines([line for line in block.get("fetch_fail_lines", ()) or () if sections.quiet_keep(view, line)],
           css="exp-fetchfail")
    _live_buttons(block, "exp1", clicks)
    _error_lines(block)
    _lines([line for line in block["detail_lines"] if sections.quiet_keep(view, line)], css="exp-detail")
    st.markdown(f'<div class="exp-detail">{_esc(block["redline_note"])}</div></div>', unsafe_allow_html=True)


def _render_exp1_live(block: dict, rows: list, *, clicks: dict, plain_mode: bool = True, quiet=None) -> None:
    """正式模式的 `EXP-1`：輸入列接上 session（`rows` 與 `block["_rows"]` 同序，帶 `_id`）。"""
    if quiet is not None:
        _render_exp1_quiet(block, quiet, clicks=clicks)
        return
    _card_open(block, plain_mode=plain_mode)
    st.caption(block["answers"])
    _notes(block)
    _fetch_fail_lines(block)
    # 第一階段唯讀（J-14 精神，2026-10-26）：存檔鈕拿掉後這組輸入已不影響本次畫面結果 → 正式模式不畫（`ui_v2/readonly.py`）。
    # 條件列（含每列的「清除這一列」）不畫；已存的條件列照舊列在篩選軌跡（`EXP-7`）。
    for row, model_row in zip(() if readonly.inputs_hidden(block) else rows, block["_rows"]):
        cells = st.columns([3, 2, 2, 2])
        for cell, field, name in zip(cells, model_row["_fields"], ("field", "op", "value")):
            with cell:
                if name == "field":
                    _field_select(field, row)
                    continue
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


def _render_exp4_live(block: dict, *, save_click, editable: bool = True, plain_mode: bool = True) -> None:
    """`editable=False`（已存設定讀不到）：不建任何可編輯的勾選框與下拉（稽核 L 回修）——
    那一輪建起來的空白狀態會留在 session 裡，恢復後被存回去蓋掉雲端。只畫失敗行與說明。"""
    with _expander(block, plain_mode=plain_mode):
        st.caption(block["answers"])
        _notes(block)
        _fetch_fail_lines(block)
        if not editable:
            _live_buttons(block, "exp4", {live.ACTION_SAVE: save_click})
            _error_lines(block)
            _lines(block["detail_lines"], css="exp-detail")
            return
        # 第一階段唯讀（J-14 精神，2026-10-26）：存檔鈕拿掉後這組輸入已不影響本次畫面結果 → 正式模式不畫（`ui_v2/readonly.py`）。
        # 欄位勾選框與排序下拉不畫；生效中的欄位與排序照舊見結果清單（欄名與排序說明）。
        if not readonly.inputs_hidden(block):
            columns = st.columns(len(block["_options"]))
            for column, option in zip(columns, block["_options"]):
                with column:
                    # 值一律由 session 決定（`_seed_live_fields` 以已存值填）；這裡傳 False ＝ 不預先勾任何一欄。
                    st.checkbox(option["label"], value=False, key=_col_key(option["_column"]))
            # 選項清單照舊（值＝欄名字串，`_field_sort` 照舊以它反查欄位鍵）；正式模式只換顯示名（Phase 3 P0-①）。
            st.selectbox("排序欄位", block["sort_options"], index=0, key=_SORT_KEY,
                         format_func=plain.key_name if plain_mode else str)
        _live_buttons(block, "exp4", {live.ACTION_SAVE: save_click})
        _error_lines(block)
        _lines(block["detail_lines"], css="exp-detail")


def _render_exp6(block: dict, *, plain_mode: bool = False) -> None:
    with _expander(block, plain_mode=plain_mode):
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


def _render_exp7(block: dict, *, plain_mode: bool = False) -> None:
    with _expander(block, plain_mode=plain_mode):
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


@health_view.guard_page("exp")   # 3-B 第二輪稽核回修可選 3：畫頁崩潰時總表不留上一筆正常記錄
def render(*, load_live=None, save_live=None, settings_page=None, mask_error=None) -> None:
    """畫整頁。

    load_live：選填的載入函式（無參數，回傳 `{"dataset": 與 fixtures 情境同形, "notes": {...}}`）。
    不傳（None）時行為與加這個參數之前**完全相同**：照舊以 `?scenario=` 挑 fixtures 情境（示範模式）。
    傳入時（正式入口 `app_exp_live.py`）改由它取得資料，這一條路徑不讀 fixtures，
    組模型走 `live.build_live_model`（只吃已存設定、不帶示意字樣、缺的格寫原因）；頁首只印本頁的提問句。

    save_live：選填的寫入函式 `save_live(鍵, 值或 None, value_kind)`（`source.save_setting`；客戶 2026-10-13 裁示）。
    傳入時 `EXP-1`／`EXP-4`／`EXP-5` 的存檔寫進 `user_setting`，下一次重跑（重新讀 `user_setting`）才生效。
    只傳 `save_live` 不傳 `load_live` 是呼叫端的 bug，當場炸。

    settings_page：選填的 `st.Page`（Phase 3 P0-②；預覽入口傳設定與診斷那一頁）。正式模式頁首資料狀態行旁
    那一枚「前往設定與診斷」**只換頁**（`ui_v2/health_view.py::render_settings_link`）；不傳時只寫一行說明。
    示範模式不畫資料狀態行，傳了當場炸。

    mask_error：選填的遮蔽函式（字串 → 遮蔽後的字串；Phase 3 P1-⑤，正式入口傳 `source.mask_error`）。
    正式模式 `load_live()` 拋例外 → 不印 Traceback、也不吞（BL-0362）：整頁改畫錯誤畫面
    （`ui_v2/health_view.py::render_load_failure`），一般畫面只寫一句狀態加「前往設定與診斷」，
    型別與遮蔽後的訊息原文收進設定與診斷頁的進階診斷；不傳遮蔽函式時只收型別。示範模式傳了當場炸。
    """
    if load_live is None and save_live is not None:
        raise ValueError("save_live 要與 load_live 一起傳")
    if load_live is None and settings_page is not None:
        raise ValueError("settings_page 只給正式模式（要與 load_live 一起傳）")
    if load_live is None and mask_error is not None:
        raise ValueError("mask_error 要與 load_live 一起傳")
    st.markdown(f"<style>{_base_css()}{_grid_css()}{theme.SOURCE_TAG_CSS}</style>", unsafe_allow_html=True)
    if load_live is not None:
        _render_live(load_live, save_live, settings_page, mask_error)
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


def _as_of(model: dict):
    """資料截至日：候選清單上已畫出來的「最近淨值日」（`ok` 那幾格）最晚的一天；一格都沒有 → None（畫成「—」）。"""
    rows = logic.find_block(model, "EXP-2").get("_rows") or ()
    cells = [(row.get("_cells") or {}).get("nav_date") or {} for row in rows]
    return health.latest_date(
        [{"day": cell.get("text")} for cell in cells if cell.get("_state") == logic.STATE_OK], "day"
    )


def _render_live(load_live, save_live, settings_page=None, mask_error=None) -> None:
    """正式模式整頁。判定全在 `live.build_live_model`；這裡只負責讀 session、接按鈕、畫。"""
    try:
        live_input = load_live()
    except Exception as exc:  # noqa: BLE001 —— 不是吞：整頁改畫錯誤畫面，原文進進階診斷並記 log（BL-0362）
        health_view.render_load_failure(
            "exp", exc, mask_error, fetch_failed_text=logic.fetch_failed_text,
            title=logic.PAGE_TITLE, answers=logic.PAGE_ANSWERS,
            title_class="exp-title", sub_class="exp-sub", tone_hex=theme.tone_hex,
            settings_page=settings_page,
        )
        return
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
        # 「觀察清單」多選第一階段不畫（`readonly.hides_inputs("EXP-5")`）：session 裡殘留的勾選不交給模型。
        watch_checked=() if readonly.hides_inputs("EXP-5") else _checked(logic.GROUP_WATCH, live.LIVE_SCENARIO, ()),
        save_wired=save_live is not None,
        save_results=st.session_state.get(_SAVE_RESULTS_STATE),
    )
    # Phase 3 P0-①（44 第七節第三小節之七其二）：一般畫面換成使用者語言；原文交給設定與診斷頁的進階診斷。
    # 只換字：模型的判定、狀態、顏色、塊數、列數一個都不動（`ui_v2/plain.py`）。示範模式不經過這一步（BL-0367）。
    model, raw, _status = plain.plain_model(model, page="exp")
    # Phase 3 ◆／◇ 小批（44 第七節第三小節之七其三、其四，之八其三 (c-2)）：偏離的黃燈改不著色 ◆、「⬜ 資料未備」改 ◇。
    # 只換符號、顏色與那一句說明；判定、門檻、算法一個都不動（`ui_v2/symbols.py`）。示範模式不經過這一步。
    symbols.apply(model)
    # BL-0250 批次 3-C（線框第六版第 7 節第 10 列）：結果清單「計價幣別」那一格的出處長句格內拿掉，原句收進進階診斷。
    raw = list(raw) + live.ccy_tip_raw(logic.find_block(model, "EXP-2"))
    plain.record_raw(st.session_state, "exp", raw, datetime.now(timezone.utc))
    # Phase 3 P0-②（44 第七節第三小節之七其二第 3、4 條）：同源錯誤只在頁首資料狀態行摘要一次；
    # 核心卡的來源與新鮮度徽章移到 ④「證據／來源」。只改呈現：判定、狀態、顏色一個都不動（`ui_v2/health.py`）。
    model, failures = health.dedupe_failures(model)
    # 客戶 2026-10-19 裁示 G3（`DEC-2026-10-19-04`）：成因全部是「尚未設定」的塊，本頁自己擬的「取數失敗」字樣改寫成
    # 「尚未設定：<哪一項>」（燈、展開區摘要；`ui_v2/health.py::relabel_unconfigured`）。判定與符號照舊。
    health.relabel_unconfigured(model, failures)
    cards = logic.codes_in_layer(model, 2)
    # BL-0250 批次 3-B（44 第七節第三小節之十三其七）：本頁已畫出的 ⛔／◇／尚未設定逐項收下，給設定與診斷頁的各頁資料狀態總表。
    # 只讀、不改：判定、符號、畫面字一個都不動（`ui_v2/health.py::collect_page_items`）。
    # 3-B 稽核回修第 3 條：收集與記錄包在錯誤邊界裡（`health_view.collect_page_health`）；第 4 條：總表的核心卡取改層之後的層 2
    # （`EXP-2`、`EXP-3` 移到 ④，不算卡）。頁上的徽章搬移與資料狀態行照舊以改層前的三張卡為對象（一字不動）。
    health_cards = sections.health_cards(cards, "exp")
    collected = health_view.collect_page_health("exp", model, failures, _status["fetch_events"], health_cards)
    # 核心卡的來源與新鮮度徽章拿下來（本頁三張卡那一格是「⬜ 不適用（…）」）。BL-0250 批次 3-C（G2；線框第六版第 7 節第 11 列）：
    # 拿下來的那一份不再畫在 ④「核心卡的來源與新鮮度」—— 同一句已在總表明細的狀態欄（`normal_entries`，收集時讀）。
    # ~~`provenance = health.move_card_provenance(...)` → `health_view.render_provenance(provenance)`~~（有意識的政策變更，
    # 不是漏刪；`DEC-2026-10-21-01`）。
    health.move_card_provenance(model, cards)
    # BL-0250 批次 3-C（U9；44 第七節第三小節之十四）：頁首改畫主要原因＋另有，讀本頁剛記下的那一格（與總表同一份）。
    # ~~`status_line = health.status_line(...)`~~（有意識的政策變更，不是漏刪；`DEC-2026-10-21-01`）。
    as_of = _as_of(model)
    health_view.record_page_health("exp", model, collected, health_cards, as_of=as_of)
    # BL-0250 批次 3-D（新設計 B；44 第七節第三小節之十五）：整張卡主值全部讀不到 → 收起（卡名＋原因行）。在收集與記錄之後判定，
    # 頁首與總表讀的那一份記錄不受影響；只決定怎麼畫，模型一個字都不動（`ui_v2/sections.py::quiet_cards`，經 `health_view.quiet_cards`）。
    quiet = health_view.quiet_cards("exp", model, collected)
    # 客戶 2026-10-21 Q5 (b)（線框 1.4 規則 5；`DEC-2026-10-21-05`）：④ 主值全部讀不到、只有一種原因、沒有判讀證據的收合區比照。
    details = health_view.quiet_details("exp", model, collected)
    # Phase 3 P1-④（44 第七節第三小節之八其一 (a-1)）：`EXP-2` 移到層 3、`EXP-3` 移到層 4（預設收合），② 只剩 `EXP-1`；
    # 在上面的徽章搬移與資料狀態行之後才改層 —— 那兩步照舊以改層前的三張核心卡為對象，行為不變（`ui_v2/sections.py`）。
    sections.relayer(model, "exp")
    attention = sections.attention_items(model, "exp")
    # 新 B UI 第一階段唯讀（客戶 2026-10-26 裁示第 7 節；`DEC-2026-10-25-04` J-6）：寫 `user_setting` 的「存檔」不畫，
    # 叫人存檔的說明一併改寫（`ui_v2/readonly.py`）。在收集與記錄之後做，判定與總表不受影響。
    readonly.strip_write_controls(model)
    noop = (None, ())
    exp1_clicks = {live.ACTION_ADD_ROW: (_on_add_rule, ())}
    exp4_click = exp5_click = noop
    if save_live is not None:
        exp1_clicks[live.ACTION_SAVE] = (_on_save_rules, (save_live,))
        exp4_click = (_on_save_columns, (save_live,))
        exp5_click = (_on_save_watch, (save_live, tuple(settings.get(live.KEY_WATCH) or ()), settings_error))

    st.markdown(f'<div class="exp-title">{_esc(model["title"])}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="exp-sub">{_esc(model["answers"])}</div>', unsafe_allow_html=True)
    health_view.render_page_header("exp", as_of=as_of, tone_hex=theme.tone_hex, settings_page=settings_page)

    st.markdown(f'<div class="exp-layer-label">{plain.LABEL_LAYER1}</div>', unsafe_allow_html=True)
    _render_exp0(logic.find_block(model, "EXP-0"), plain_mode=True)

    st.markdown(
        f'<div class="exp-layer-label exp-layer2">{plain.LABEL_LAYER2}</div>',
        unsafe_allow_html=True,
    )
    for column, code in zip(st.columns(3), logic.codes_in_layer(model, 2)):
        with column:
            block = logic.find_block(model, code)
            if code == "EXP-1":
                _render_exp1_live(block, rows if readable else [], clicks=exp1_clicks, plain_mode=True,
                                  quiet=quiet.get(code))
            else:
                _RENDERERS[code](block, plain_mode=True)

    # ③需要注意：`EXP-0` 已算出的無法判定檔數；沒有就整段不畫。
    health_view.render_attention(attention, tone_hex=theme.tone_hex, label_class="exp-layer-label")

    # ④詳細資料（預設收合）。本頁例外：`EXP-2`（層 3）與 `EXP-3`（層 4）依 59 第 4.2 節合成一個「結果清單」框，
    # 放在兩個小標之前（之八其一 (a-1) 第 3 條，總管讀法）；其餘塊照舊「操作」「證據／來源」兩個小標分開（護欄 6）。
    st.markdown(f'<div class="exp-layer-label">{plain.LABEL_DETAILS}</div>', unsafe_allow_html=True)
    exp2 = logic.find_block(model, "EXP-2")
    with st.expander(f"{sections.EXP_RESULT_TITLE}　—　{exp2['summary_text']}", expanded=exp2["_default_open"]):
        # BL-0250 批次 3-B：每列來源展開與兩份多選清單（44 第七節第三小節之十三）；示範模式照舊 `_render_exp2`。
        _render_exp2_live(exp2, hide_watch=readonly.inputs_hidden(logic.find_block(model, "EXP-5")))
        _render_exp3(logic.find_block(model, "EXP-3"), plain_mode=True)
    st.markdown(
        f'<div class="exp-layer-label exp-layer3">{plain.LABEL_LAYER3}</div>',
        unsafe_allow_html=True,
    )
    operations = [code for code in logic.codes_in_layer(model, 3) if code not in sections.EXP_RESULT_CODES]
    for column, code in zip(st.columns(3), operations):
        with column:
            block = logic.find_block(model, code)
            if code in details:
                _render_detail_quiet(details[code])
            elif code == "EXP-4":
                _render_exp4(block, scenario=live.LIVE_SCENARIO, save_click=exp4_click, editable=readable,
                             plain_mode=True)
            else:
                _render_exp5(block, save_click=exp5_click, plain_mode=True)

    st.markdown(
        f'<div class="exp-layer-label">{plain.LABEL_LAYER4}</div>', unsafe_allow_html=True
    )
    for code in logic.codes_in_layer(model, 4):
        if code in details:
            _render_detail_quiet(details[code])
        elif code not in sections.EXP_RESULT_CODES:
            _RENDERERS[code](logic.find_block(model, code), plain_mode=True)

    # BL-0250 批次 2（44 第七節第三小節之十一 U1／U2）：正式模式頁尾只畫一句指路句，不加「本頁不負責什麼：」、不掛紅線標記徽章。
    st.markdown(f'<div class="exp-footer">{_esc(" ".join(model["footer_lines"]))}</div>', unsafe_allow_html=True)
