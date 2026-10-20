# -*- coding: utf-8 -*-
"""設定與診斷的 Streamlit 渲染層。

本檔**只負責畫**：狀態、欄數、文案、結論燈、新鮮度、型別判定全部住在 logic.py，
這裡一個判定也不做。色票與對比住在 theme.py，假資料住在 fixtures.py。

本檔不 import 舊 repo 任何模組，不發任何網路請求，**不寫任何色碼字面值**
（每一個顏色都從 theme 取 —— 那一份每一組都算過對比）。

注意：示範模式（`ui_v2/app_set.py`，不傳入載入函式）的「存檔」「重新取數」兩種按鈕畫得出來、按得下去，
   但**沒有後端**：按下去不寫任何東西（SET-GAP-無後端）。
正式模式（`ui_v2/app_set_live.py`）由呼叫端注入三個函式（`render(load_live=, save_live=, refetch_live=)`），
   按鈕才真的存檔、取數；正式模式才有的文案與停用原因全部住在 `live.py`，本檔只畫。
   **不注入時，本檔走的路徑與加入注入參數之前逐字相同。**
"""

from __future__ import annotations

import html
import re

import streamlit as st

from .. import health_view, page_health, plain, sections, symbols
from . import fixtures, live, logic, theme

_MAX_PROBE_WIDTH = 2000


def _esc(value) -> str:
    return html.escape(str(value), quote=True)


def _tone(value) -> str:
    return theme.tone_hex(value)


def _breakpoint_edges(layer: int) -> list:
    """掃出該層欄數改變的寬度邊界。數字只有一個真相源：logic 那支已被測試釘住的純函式。"""
    edges = []
    previous = logic.layer_columns(layer, 1)
    for width in range(2, _MAX_PROBE_WIDTH + 1):
        current = logic.layer_columns(layer, width)
        if current != previous:
            edges.append((width, current))
            previous = current
    return edges


def _grid_css() -> str:
    """把 logic 的斷點翻成 CSS media query（`44` 2.1 量的是視窗寬度的 CSS 像素）。"""
    blocks = [
        """
        [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; gap: 12px; }
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
        [data-testid="stHorizontalBlock"] > [data-testid="column"] {
          flex: 1 1 100% !important; min-width: 0 !important;
        }
        """
    ]
    for layer, marker in ((2, "st-key-set_layer2"), (3, "st-key-set_layer3")):
        for width, columns in _breakpoint_edges(layer):
            share = 100.0 / columns
            blocks.append(
                f"""
        @media (min-width: {width}px) {{
          .{marker} > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
          .{marker} > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
            flex: 1 1 calc({share:.4f}% - 12px) !important;
          }}
        }}
        """
            )
    return "".join(blocks)


def _base_css() -> str:
    """每一條 `.set-*` 規則都自動前綴 `.stApp `（兩個 class），權重一律高過 `.stApp span` 那一條全域規則
    （姊妹頁 ui_v2/alo 稽核抓過的病；畫面層守衛在 test_set_page.py 用瀏覽器量實際算出來的顏色）。"""
    return _scoped(_raw_css())


def _scoped(css: str) -> str:
    return re.sub(r"(?m)^(\s*)\.set-", r"\1.stApp .set-", css)


def _raw_css() -> str:
    # SET-GAP-窄寬度表格：格內文字在任何字元處換行，不出橫向捲動、不藏欄。
    return f"""
    .stApp {{ background: {theme.APP_BG}; }}
    .stApp, .stApp p, .stApp span, .stApp label {{ color: {theme.TEXT_PRIMARY}; }}
    .set-title {{
      font-size: 1.45rem; font-weight: 700; letter-spacing: .04em;
      color: {theme.TEAL_BRIGHT}; border-bottom: 2px solid {theme.TEAL_DARK};
      padding-bottom: .4rem; margin-bottom: .2rem;
    }}
    .set-sub {{ color: {theme.TEXT_MUTED}; font-size: .82rem; margin-bottom: .6rem; }}
    .set-layer-label {{
      color: {theme.TEAL_BRIGHT}; font-size: .72rem; letter-spacing: .18em;
      margin: 1.1rem 0 .35rem;
    }}
    .set-lamp {{
      display: flex; align-items: center; gap: .8rem; flex-wrap: wrap;
      border: 1px solid var(--set-tone); border-left: 5px solid var(--set-tone);
      background: {theme.SURFACE}; border-radius: 8px; padding: .85rem 1rem;
    }}
    .set-glyph {{ font-size: 1.25rem; line-height: 1; color: var(--set-tone); }}
    .set-stword {{
      display: inline-block; font-size: .7rem; font-weight: 700;
      padding: .05rem .4rem; border-left: 3px solid var(--set-tone); color: var(--set-tone);
      background: {theme.STATE_GRAY_BG}; margin-right: .5rem;
    }}
    .set-lamp-text {{
      font-size: 1.02rem; font-weight: 600; color: var(--set-tone); overflow-wrap: anywhere;
    }}
    .set-code {{ color: {theme.TEXT_MUTED}; font-size: .78rem; margin-left: auto; }}
    .set-card-head {{
      display: flex; align-items: baseline; gap: .5rem; flex-wrap: wrap;
      border: 1px solid var(--set-tone); border-bottom: 2px solid var(--set-tone);
      background: {theme.SURFACE}; border-radius: 8px 8px 0 0; padding: .5rem .8rem;
    }}
    .set-card-code {{ color: {theme.TEXT_MUTED}; font-size: .72rem; }}
    .set-card-title {{ font-weight: 700; color: {theme.TEAL_BRIGHT}; }}
    .set-note {{ font-size: .76rem; color: {theme.TEXT_MUTED}; margin: .2rem 0; overflow-wrap: anywhere; }}
    .set-line {{ font-size: .82rem; color: {theme.TEXT_SECOND}; margin: .2rem 0; overflow-wrap: anywhere; }}
    .set-empty {{
      color: var(--set-tone); border: 1px dashed {theme.EDGE}; overflow-wrap: anywhere;
      border-radius: 6px; padding: .5rem .7rem; margin: .4rem 0; font-size: .85rem;
    }}
    .set-failbox {{
      color: {theme.STATE_GRAY}; background: {theme.STATE_GRAY_BG};
      border: 1px solid {theme.STATE_GRAY}; border-radius: 5px; overflow-wrap: anywhere;
      padding: .4rem .6rem; margin: .1rem 0 .5rem; font-size: .8rem;
    }}
    .set-hint {{ font-size: .78rem; color: {theme.STATE_WARN}; margin: .1rem 0 .3rem; overflow-wrap: anywhere; }}
    .set-table {{ width: 100%; border-collapse: collapse; font-size: .78rem; table-layout: auto; }}
    .set-table th {{
      text-align: left; color: {theme.TEAL_BRIGHT}; border-bottom: 1px solid {theme.TEAL_DARK};
      padding: .3rem .4rem; white-space: normal; overflow-wrap: anywhere; word-break: break-word;
    }}
    .set-table td {{
      border-bottom: 1px solid {theme.BORDER}; padding: .28rem .4rem;
      color: {theme.TEXT_PRIMARY}; white-space: normal; overflow-wrap: anywhere; word-break: break-word;
    }}
    .set-cell-tone {{ color: var(--set-tone); }}
    .set-raw {{ display: block; color: {theme.TEXT_MUTED}; font-size: .72rem; }}
    .set-footer {{
      margin-top: 1.6rem; border-top: 1px solid {theme.BORDER}; padding-top: .7rem;
      color: {theme.TEXT_MUTED}; font-size: .78rem;
    }}
    .set-badge {{
      display: inline-block; border-radius: 999px; padding: .05rem .5rem;
      font-size: .68rem; border: 1px solid var(--set-tone); color: var(--set-tone);
      margin: 0 .3rem 0 .2rem;
    }}
    .stTextInput input, .stTextArea textarea {{
      background: {theme.INPUT_BG} !important; border: 1px solid {theme.EDGE} !important;
      color: {theme.TEXT_PRIMARY} !important;
    }}
    .stTextInput input::placeholder, .stTextArea textarea::placeholder {{ color: {theme.PLACEHOLDER} !important; }}
    .stButton button {{
      background: {theme.BUTTON_BG}; border: 1px solid {theme.EDGE}; color: {theme.TEXT_PRIMARY};
    }}
    """


def _html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def _lines(lines, css="set-note") -> None:
    for line in lines or ():
        _html(f'<div class="{css}">{_esc(line)}</div>')


def _badge(node: dict) -> str:
    glyph = node.get("glyph", "")
    text = f"{glyph} {node['text']}" if glyph else node["text"]
    return f'<span class="set-badge" style="--set-tone:{_tone(node["_tone"])}">{_esc(text)}</span>'


def _placeholder_markup(node: dict) -> str:
    glyph = node.get("glyph", "")
    text = f"{glyph} {node['text']}" if glyph else node["text"]
    return f'<div class="set-empty" style="--set-tone:{_tone(node["_tone"])}">{_esc(text)}</div>'


def _placeholders(nodes) -> None:
    for node in nodes or ():
        if node:
            _html(_placeholder_markup(node))
            _tone_lines(node.get("note_lines"))  # 正式模式才有


def _failbox(lines) -> None:
    # 拍板原型：失敗框掛在該鍵輸入欄下方、灰態容器、兩行；圖示已在字串裡（logic.SAVE_FAIL_GLYPH）。
    body = "<br/>".join(_esc(line) for line in lines)
    _html(f'<div class="set-failbox" role="alert">{body}</div>')


def _cell(text, *, badges=(), tone=None, raw="", notes=()) -> str:
    body = _esc(text)
    if tone and tone != "中性":
        body = f'<span class="set-cell-tone" style="--set-tone:{_tone(tone)}">{body}</span>'
    body += "".join(_badge(b) for b in badges)
    if raw:
        body += f'<span class="set-raw">{_esc(raw)}</span>'
    # 正式模式才有（live.apply_live_notes 加的）：原因行、已遮蔽憑證，各另起一行；示範模式沒有這些鍵
    for note in notes or ():
        body += f'<span class="set-raw">{_esc(note)}</span>'
    return body


def _tone_lines(nodes) -> None:
    """正式模式的附加行（`live.py` 產生；每一行 `{"text", "_tone"}` 或純字串）。灰色小字用 set-note。"""
    for node in nodes or ():
        if isinstance(node, str):
            node = {"text": node, "_tone": "中性"}
        if node["_tone"] == "灰":
            _html(f'<div class="set-note">{_esc(node["text"])}</div>')
        elif node["_tone"] == "中性":
            _html(f'<div class="set-line">{_esc(node["text"])}</div>')
        else:
            _html(
                f'<div class="set-line"><span class="set-cell-tone" style="--set-tone:{_tone(node["_tone"])}">'
                f'{_esc(node["text"])}</span></div>'
            )


def _table(labels, rows) -> str:
    """`rows` 的每一格已經是 `_cell()` 產出的安全 markup。"""
    head = "".join(f"<th>{_esc(label)}</th>" for label in labels)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f'<table class="set-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def _block_attr(block: dict, plain_mode: bool) -> str:
    """正式模式：塊代號只放進 `data-block` 屬性（畫面不可見；給測試與瀏覽器量測定位）。示範模式回空字串、畫面照舊。"""
    return f' data-block="{_esc(block["code"])}"' if plain_mode else ""


def _card_head(block: dict, plain_mode: bool = False) -> None:
    code_span = "" if plain_mode else f'<span class="set-card-code">{_esc(block["code"])}</span>'
    _html(
        f'<div class="set-card-head" style="--set-tone:{_tone(block["_tone"])}"{_block_attr(block, plain_mode)}>'
        f'{code_span}'
        f'<span class="set-card-title">{_esc(block["title"])}</span></div>'
    )


def _buttons(buttons, prefix: str) -> None:
    for index, button in enumerate(buttons or ()):
        st.button(
            button["label"],
            key=f"{prefix}_btn_{index}",
            disabled=not button["_enabled"],
            help=button["disabled_reason"] or None,
        )


# ───────────────────────── 層 1 ─────────────────────────


def _render_set0(block: dict, *, plain_mode: bool = False) -> None:
    # 燈右側那一格：正式模式只留標題（44 第七節第三小節之七其二第 1 條）；示範模式「代號　標題」照舊。
    code_title = _esc(block["title"]) if plain_mode else f'{_esc(block["code"])}　{_esc(block["title"])}'
    _html(
        f'<div class="set-lamp" style="--set-tone:{_tone(block["_tone"])}"{_block_attr(block, plain_mode)}>'
        f'<div class="set-glyph" aria-hidden="true">{_esc(block["glyph"])}</div>'
        f'<div><div><span class="set-stword">{_esc(block["state_word"])}</span>'
        f'<span class="set-lamp-text">{_esc(block["text"])}</span></div>'
        f'<div class="set-note">{_esc(block["answers"])}</div></div>'
        f'<div class="set-code">{code_title}</div></div>'
    )
    _lines(block.get("note_lines"))  # 正式模式才有：燈文含遮蔽記號時的下一行（★5）
    _lines(block["detail_lines"])


# ───────────────────────── 層 2 ─────────────────────────


def _render_set1(block: dict, key: str, ctx=None) -> None:
    _card_head(block, ctx is not None)
    rows = []
    for row in block["_rows"]:
        fail_tone = "紅" if row["_failed"] else None
        rows.append(
            [
                _cell(row["kind_text"], badges=row["badges"], notes=row.get("note_lines")),
                _cell(row["at_text"], tone=fail_tone, notes=row.get("at_note_lines")),
                _cell(row["days_text"]),
                _cell(row["compare_text"]),
            ]
        )
    _html(_table(block["column_labels"], rows))
    _placeholders(block["fail_nodes"])
    _tone_lines(block.get("live_lines"))  # 正式模式才有（★9）
    _lines(block["limit_lines"], "set-line")
    _lines([block["answers"]] + block["detail_lines"])


def _render_set2(block: dict, key: str, ctx=None) -> None:
    _card_head(block, ctx is not None)
    _placeholders([block["placeholder"]])
    if block["_rows"]:
        rows = [
            [
                _cell(r["tier_text"], badges=r["badges"], notes=r.get("note_lines")),
                _cell(r["result_text"], tone=r["_tone"] if r["_tone"] == "紅" else None),
                _cell(r["time_text"]),
                _cell(r["message_text"], tone=r["_tone"] if r["_tone"] == "紅" else None,
                      notes=r.get("message_note_lines")),
            ]
            for r in block["_rows"]
        ]
        _html(_table(block["column_labels"], rows))
    _lines([block["answers"]] + block["detail_lines"])


def _render_set3(block: dict, key: str, ctx=None) -> None:
    _card_head(block, ctx is not None)
    _tone_lines(block.get("head_lines"))  # 正式模式才有（★10）
    _placeholders([block["placeholder"]])
    if block["_rows"]:
        rows = [
            [_cell(r["key_text"]), _cell(r["value_text"], raw=r["raw_text"]), _cell(r["kind_text"]), _cell(r["time_text"])]
            for r in block["_rows"]
        ]
        _html(_table(block["column_labels"], rows))
    _tone_lines(block.get("live_lines"))  # 正式模式才有（★9）
    _lines([block["answers"]] + block["detail_lines"])


# ───────────────────────── 層 3 ─────────────────────────


def _expander(block: dict, plain_mode: bool = False):
    # 正式模式標題去掉塊代號（44 第七節第三小節之七其二第 1 條）；示範模式照舊。
    head = block["title"] if plain_mode else f"{block['code']}　{block['title']}"
    return st.expander(
        f"{head}　—　{block['summary_text']}",
        expanded=block["_default_open"],
    )


def _render_set4(block: dict, key: str, ctx=None) -> None:
    with _expander(block, ctx is not None):
        st.caption(block["answers"])
        _tone_lines(block.get("top_lines"))  # 正式模式才有（★6 缺設定那一行）
        _placeholders(block["fail_nodes"])
        for lines in block["orphan_fail_lines"]:
            _failbox(lines)
        for field in block["inputs"]:
            widget = st.text_area if field["_multiline"] else st.text_input  # SET-GAP-輸入欄型態
            widget(field["label"], value=field["value_text"], key=f"{key}_{field['name']}")
            _lines(field.get("saved_lines"), "set-line")  # 正式模式才有（★6「已存檔」）
            if field["used_by_text"] is not None:  # 正式模式下未設定的非 set_ 鍵不出這一行（草稿 B9）
                _lines([field["used_by_text"]])
            _lines(field["unset_lines"], "set-line")
            _lines(field["hint_lines"], "set-hint")
            if field["fail_lines"]:
                _failbox(field["fail_lines"])
        _tone_lines(block.get("live_lines"))  # 正式模式才有（★9）
        if ctx is None:
            _buttons(block["buttons"], f"{key}_set4")
        else:
            _live_save(block, key, ctx)
        _lines(block["detail_lines"])


def _live_save(block: dict, key: str, ctx) -> None:
    """正式模式的「存檔」：寫入被編輯的鍵，結果放進 session 後重跑一次，下一輪畫出「已存檔」或失敗框。
    停用原因、要存哪幾鍵、結果怎麼寫，全部由 live.py 判定；本函式只收集輸入欄的當下值、呼叫注入的函式。"""
    button = block["buttons"][0]
    clicked = st.button(button["label"], key=f"{key}_set4_btn_0", disabled=not button["_enabled"],
                        help=button["disabled_reason"] or None)
    if not clicked:
        return
    values = {f["name"]: st.session_state.get(f"{key}_{f['name']}") for f in block["inputs"]}
    results = {}
    for name, value, kind in live.changed_settings(block["inputs"], values):
        results[name] = {**ctx["save_live"](name, value, kind), "attempted": value}
    st.session_state["_set_live_save_results"] = results
    st.rerun()


def _render_set5(block: dict, key: str, ctx=None) -> None:
    with _expander(block, ctx is not None):
        st.caption(block["answers"])
        picked = st.radio(
            block["tier_label"],
            list(block["tier_options"]),
            index=None,
            key=f"{key}_set5_tier",
            horizontal=True,
        )
        if ctx is None:
            # 停用與否由 logic 依單選的當下值判定；本檔不自己判。
            _buttons([logic.set5_button(picked)], f"{key}_set5")
        else:
            _live_refetch(picked, key, ctx)
        _lines(block["detail_lines"])


def _live_refetch(picked, key: str, ctx) -> None:
    """正式模式的「重新取數」：停用原因由 live.refetch_button 判定；按下後先畫「取數中」並停用，
    取完把結果放進 session 後重跑一次，下一輪在按鈕下方畫結果行（下一次互動後消失；要回頭看，看 SET-6）。"""
    slot = st.empty()
    button = live.refetch_button(picked, ctx["notes"])
    clicked = slot.button(button["label"], key=f"{key}_set5_btn_0", disabled=not button["_enabled"],
                          help=button["disabled_reason"] or None)
    result = ctx.get("refetch_result")
    if result is not None:
        _tone_lines(live.refetch_result_lines(result, ctx["notes"]["mask_token"]))
    if not clicked:
        return
    running = live.refetch_button(picked, ctx["notes"], running=True)
    with slot.container():
        st.button(running["label"], key=f"{key}_set5_btn_running", disabled=True,
                  help=running["disabled_reason"])
        _html(f'<div class="set-line">{_esc(running["disabled_reason"])}</div>')
    st.session_state["_set_live_refetch_result"] = ctx["refetch_live"](picked)
    st.rerun()


# ───────────────────────── 層 4 ─────────────────────────


def _render_set6(block: dict, key: str, ctx=None) -> None:
    with _expander(block, ctx is not None):
        st.caption(block["answers"])
        _placeholders([block["placeholder"]])
        if block["_rows"]:
            _html(_table(block["column_labels"], [
                [_cell(c, notes=r.get("cell_notes", {}).get(i)) for i, c in enumerate(r["cells"])]
                for r in block["_rows"]
            ]))
        _lines(block["tail_lines"], "set-line")
        _tone_lines(block.get("live_lines"))  # 正式模式才有（★9）
        _lines(block["detail_lines"])


def _render_set7(block: dict, key: str, ctx=None) -> None:
    with _expander(block, ctx is not None):
        st.caption(block["answers"])
        rows = [[_cell(r["field_text"], badges=r["badges"]), _cell(r["blocks_text"])] for r in block["_rows"]]
        _html(_table(block["column_labels"], rows))
        _lines(block["detail_lines"])


# ── 進階診斷（原始訊息）：Phase 3 P0-①（44 第七節第三小節之七其二第 8 條；只在正式模式畫） ──
# 呈現層：不取數、不寫入，只轉放其他頁本次瀏覽已經畫過、移出一般畫面的原文（`ui_v2/plain.py::record_raw`），
# 以及原始鍵名、塊代號的對照。它是一枚預設收合的展開區，不是新的塊（不計入塊數與判準行數）。
ADVANCED_DIAG_NOTE = "只收錄本次瀏覽開過的頁；每一頁每次重新畫面時整格更新。原文已遮蔽憑證，照印、不改寫。"
# 原文可以是任何東西（例：上游錯誤頁裡的空行、`## `、`|`）。本頁 `_esc` 只做 HTML 跳脫，空行會讓 Markdown 跳出
# HTML 區塊、把後面的字當語法解析 —— 這一枚改走與 `ui_v2/hld/page.py::_esc` 同樣的三步（折空白、HTML、Markdown
# 語法字元一律改成數字字元參照），不截斷。
_DIAG_WS = re.compile(r"[ \t\r\n\f\v]+")
_DIAG_ENTITY = {ord(ch): f"&#{ord(ch)};" for ch in "\\`*_{}[]()#!|~$:" + "&<>\"'"}


def _diag_cell(value) -> str:
    return _DIAG_WS.sub(" ", str(value)).translate(_DIAG_ENTITY)
ADVANCED_DIAG_EMPTY = "本次瀏覽開過的頁沒有被移出的原始訊息。"
ADVANCED_DIAG_NO_PAGE = "本次瀏覽還沒有開過其他頁。"
_ADVANCED_DIAG_LABELS = ("頁", "記錄時間", "位置", "原文")


# BL-0250 批次 3-A（U7（b）（c）；44 第七節第三小節之十二）：取數紀錄的紀錄編號與結果原值不上一般畫面，改在這裡照列。
ADVANCED_DIAG_LOG_TITLE = "取數紀錄的紀錄編號與結果原值"
_ADVANCED_DIAG_LOG_LABELS = ("紀錄編號", f"開始（{logic.DISPLAY_TZ_LABEL}）", "結果原值")


def _render_advanced_diag(raw_log=None) -> None:
    with st.expander(plain.ADVANCED_DIAG_TITLE, expanded=False):
        st.caption(ADVANCED_DIAG_NOTE)
        pages = plain.recorded_pages(st.session_state)
        if pages:
            _lines(["已記錄的頁：" + "、".join(f"{name}（{at}）" for name, at in pages)], "set-line")
        else:
            _lines([ADVANCED_DIAG_NO_PAGE], "set-line")
        entries = plain.raw_entries(st.session_state)
        if entries:
            _html(_table(_ADVANCED_DIAG_LABELS, [[_diag_cell(cell) for cell in entry] for entry in entries]))
        elif pages:
            _lines([ADVANCED_DIAG_EMPTY], "set-line")
        _lines(["塊代號對照"], "set-line")
        _html(_table(("塊代號", "塊名"), [[_cell(code), _cell(name)] for code, name in plain.BLOCK_NAMES.items()]))
        _lines(["原始鍵名對照"], "set-line")
        _html(_table(("鍵名", "畫面上的名稱"), [[_cell(k), _cell(v)] for k, v in plain.KEY_NAMES.items()]))
        if raw_log:
            _lines([ADVANCED_DIAG_LOG_TITLE], "set-line")
            _html(_table(_ADVANCED_DIAG_LOG_LABELS, [[_cell(c) for c in row] for row in raw_log]))


# ── BL-0250 批次 3-B：各頁資料狀態總表（44 第七節第三小節之十三其七；線框 6.3；只在正式模式畫） ──
# 呈現層：不取數、不寫入，只讀其他頁本次瀏覽已經記下的狀態（`ui_v2/page_health.py::record`）。放在 ② 資料新鮮度卡下面，
# 本身是一枚預設展開的收合區；逐頁明細用「看哪一頁的明細」選單切換、下面只出一張表（不巢狀）。選單的值不存進使用者設定。
_HEALTH_PICK_KEY = "set_page_health_pick"


def _render_page_health(pages=None) -> None:
    store = st.session_state.get(page_health.STATE_KEY) or {}
    rows = page_health.summary_rows(store)
    with st.container(key="set_layer2_health"):
        with st.expander(page_health.BLOCK_TITLE, expanded=True):
            _html(_table(page_health.SUMMARY_LABELS,
                         [[_cell(r["page"]), _cell(r["status"]), _cell(r["main"]), _cell(r["at"])] for r in rows]))
            if pages:
                # 每列的「前往該頁」：只換頁（`st.page_link`），不取數、不寫入。依上表的列序。
                for row in rows:
                    page = pages.get(row["slug"])
                    if page is not None:
                        st.page_link(page, label=page_health.TEXT_GOTO.format(page=row["page"]))
            else:
                _lines([page_health.TEXT_NO_NAV], "set-line")
            _lines([page_health.TEXT_SCOPE], "set-line")
            names = [r["page"] for r in rows]
            slugs = {r["page"]: r["slug"] for r in rows}
            picked = st.selectbox(page_health.TEXT_PICK_LABEL, names, index=0, key=_HEALTH_PICK_KEY)
            entry = store.get(slugs[picked])
            if entry is None:
                _lines([page_health.TEXT_DETAIL_EMPTY], "set-line")
                return
            _lines([page_health.TEXT_RECORDED_AT.format(at=page_health.recorded_time_text(entry["at"]))], "set-line")
            detail = page_health.detail_rows(entry)
            if detail:
                _html(_table(page_health.DETAIL_LABELS, [[_cell(c) for c in row] for row in detail]))
            else:
                _lines([page_health.TEXT_DETAIL_NONE], "set-line")


# ── Phase 3 P1-⑥：正式模式 ④ 的搬入塊與 `SET-0` 燈旁的導覽（44 第七節第三小節之八其二；示範模式不經過這裡） ──

_MOVED_SUMMARY = {"SET-2": sections.set2_summary, "SET-3": sections.set3_summary}


def _render_set0_nav() -> None:
    """`SET-0` 燈旁那一枚 `導覽`（之八其二 (b-1) 第 2 條）：同頁錨點連結，只把畫面捲到 ④「操作」的 `SET-5`。
    純 HTML 錨點 —— 不是 `st.button`（按下會重跑整頁、重讀設定試算表），不讀也不寫任何資料表，
    不觸發取數、重新整理、存檔或任何寫入（護欄 3）。樣式寫在這一枚的 style 屬性：共用 CSS 一字不改（示範模式畫面不變）。"""
    _html(
        f'<div class="set-nav" style="margin:.35rem 0 .2rem;font-size:.82rem">'
        f'<a href="#{_esc(sections.SET_NAV_ANCHOR)}" style="color:{theme.TEAL_BRIGHT};text-decoration:underline">'
        f"{_esc(sections.SET_NAV_LABEL)}</a></div>"
    )


def _render_moved(code: str, block: dict, key: str, ctx) -> None:
    """正式模式 ④ 內的一塊：`SET-2`／`SET-3` 原本是層 2 的卡，移進 ④ 之後包成一枚預設收合的展開區，
    標題帶摘要（只拼卡上已有的格，`sections.set2_summary`／`set3_summary`；44 第五節第四小節）。
    `SET-5` 前放錨點（`SET-0` 燈旁那一枚導覽的落點）。其餘塊照原本的畫法。"""
    if code == sections.SET_REFETCH_CODE:
        _html(f'<div id="{_esc(sections.SET_NAV_ANCHOR)}"></div>')
    if code in _MOVED_SUMMARY:
        with st.expander(f"{block['title']}　—　{_MOVED_SUMMARY[code](block)}", expanded=block["_default_open"]):
            _RENDERERS[code](block, key, ctx)
        return
    _RENDERERS[code](block, key, ctx)


# ───────────────────────── 整頁 ─────────────────────────


def _query(name):
    try:
        return dict(st.query_params).get(name)
    except Exception:
        return None


def _pick_scenario() -> str:
    """情境用查詢參數挑，不做成輸入欄（`44` 1.1 節判準：輸入欄不帶非空預設值）。"""
    name = _query("scenario")
    return name if name in fixtures.ALL_SCENARIO_NAMES else "ok"


def _pick_save_failed() -> bool:
    return _query("savefail") == "1"


_RENDERERS = {
    "SET-1": _render_set1,
    "SET-2": _render_set2,
    "SET-3": _render_set3,
    "SET-4": _render_set4,
    "SET-5": _render_set5,
    "SET-6": _render_set6,
    "SET-7": _render_set7,
}


def render(*, load_live=None, save_live=None, refetch_live=None, mask_error=None, pages=None) -> None:
    """畫整頁。

    三個參數都不傳（None）時行為與加這些參數之前完全相同：照舊以 ?scenario= 挑 fixtures 情境。
    傳入時（正式入口 app_set_live.py）改由 `load_live()` 取得資料，這一條路徑不讀 fixtures，
    並套用 `live.apply_live_notes` 的正式模式調整；「存檔」呼叫 `save_live(鍵, 值, value_kind)`，
    「重新取數」呼叫 `refetch_live(層級)`。頁首副標只印本頁的提問句（草稿 ✂1）。
    三個函式要一起傳：只傳其中一部分就是呼叫端的 bug，當場炸。

    mask_error：選填的遮蔽函式（字串 → 遮蔽後的字串；Phase 3 P1-⑤，正式入口傳 `source.mask_error`）。
    正式模式 `load_live()` 拋例外 → 不印 Traceback、也不吞（BL-0362）：整頁改畫錯誤畫面
    （`ui_v2/health_view.py::render_load_failure`；本頁就是設定與診斷，不掛「前往設定與診斷」），
    型別與遮蔽後的訊息原文收進進階診斷、並在同一頁畫出那一枚進階診斷；不傳遮蔽函式時只收型別。
    示範模式傳了當場炸。

    pages：選填 `{頁 slug: st.Page}`（BL-0250 批次 3-B；預覽入口 `ui_v2/app_preview.py` 傳四頁），給各頁資料狀態總表每列的
    「前往該頁」（只換頁）。單頁入口不傳 → 總表照畫，只寫一句沒有換頁連結。示範模式傳了當場炸。
    """
    _html(f"<style>{_base_css()}{_grid_css()}</style>")

    ctx = None
    if load_live is None:
        if save_live is not None or refetch_live is not None:
            raise ValueError("save_live／refetch_live 要與 load_live 一起傳")
        if mask_error is not None:
            raise ValueError("mask_error 要與 load_live 一起傳")
        if pages is not None:
            raise ValueError("pages 要與 load_live 一起傳")
        scenario = _pick_scenario()
        save_failed = _pick_save_failed()
        model = logic.build_page_model(fixtures.scenario_with(scenario, save_failed=save_failed))
        # 輸入欄的 key 帶情境與開關：換情境時不沿用上一個情境留在 session 裡的值。
        key = f"{scenario}_{int(save_failed)}"
    else:
        if save_live is None or refetch_live is None:
            raise ValueError("正式模式要同時傳 load_live、save_live、refetch_live")
        try:
            live_input = load_live()
        except Exception as exc:  # noqa: BLE001 —— 不是吞：整頁改畫錯誤畫面，原文進進階診斷並記 log（BL-0362）
            health_view.render_load_failure(
                "set", exc, mask_error, fetch_failed_text=logic.fetch_failed_text,
                title=logic.PAGE_TITLE, answers=logic.PAGE_ANSWERS,
                title_class="set-title", sub_class="set-sub", tone_hex=theme.tone_hex, link=False,
            )
            # 原文只在進階診斷照印（44 第七節第三小節之七其二第 8 條）；本頁就是那一頁，錯誤畫面下面直接畫那一枚。
            _render_advanced_diag()
            return
        # 本頁上一次載入失敗時記下的那一筆，載入成功就拿掉（免得舊的錯誤留在進階診斷裡說謊）。
        plain.clear_raw(st.session_state, "set")
        save_results = st.session_state.pop("_set_live_save_results", None)
        dataset = live.dataset_with_save_results(live_input["dataset"], save_results)
        model = live.apply_live_notes(logic.build_page_model(dataset), dataset, live_input["notes"],
                                      save_results=save_results)
        # Phase 3 P0-①：本頁只換塊代號、層字樣與 `SET-1` 的鍵名；`SET-2`／`SET-6`／`SET-7` 照舊照印原文與鍵名
        # （44 第七節第三小節之七其二第 1、2 條），`SET-3`／`SET-4` 的鍵名不在本批。判定一個都不動。
        model, _raw, _status = plain.plain_model(model, page="set")
        # Phase 3 ◆／◇ 小批（44 第七節第三小節之七其三、其四，之八其三 (c-2)）：偏離的黃燈改不著色 ◆、「⬜ 資料未備」改 ◇。
        # 只換符號、顏色與那一句說明；判定、門檻、算法一個都不動（`ui_v2/symbols.py`）。示範模式不經過這一步。
        symbols.apply(model)
        # Phase 3 P1-⑥（44 第七節第三小節之八其二 (b-1)～(b-4)、其三 (c-1)）：`SET-2` → 層 4（④「證據／來源」）、
        # `SET-3` → 層 3（④「操作」）；`SET-0` 黃燈那一句與設定試算表未設定時的第三句；`SET-1`「外」前加 ◷；
        # ③ 由 `SET-1` 已算出的「外」那幾列撐起。判定、門檻、取數與寫入一個都不動（`ui_v2/sections.py`）。
        # 客戶 2026-10-18 裁示（`DEC-2026-10-18-01`）：S1 第三句優先於由此衍生的讀取失敗；C1 服務帳戶也未設定時維持 ⛔。
        sections.set_reshape(model, sheet_configured=live.sheet_configured(live_input["notes"]),
                             service_account_configured=live.service_account_configured(live_input["notes"]))
        attention = sections.attention_items(model, "set")
        ctx = {
            "notes": live_input["notes"],
            "save_live": save_live,
            "refetch_live": refetch_live,
            "refetch_result": st.session_state.pop("_set_live_refetch_result", None),
        }
        key = "live"

    _html(f'<div class="set-title">{_esc(model["title"])}</div>')
    if ctx is None:
        label = fixtures.SCENARIO_LABELS[scenario] + ("　·　存檔寫入失敗" if save_failed else "")
        _html(
            f'<div class="set-sub">{_esc(model["answers"])}　·　{_esc(model["hint_note"])}'
            f"　·　情境 {_esc(label)}</div>"
        )
    else:
        _html(f'<div class="set-sub">{_esc(model["answers"])}</div>')  # 草稿 ✂1：只留提問句

    plain_mode = ctx is not None
    label1, label2, label3, label4 = (
        (plain.LABEL_LAYER1, plain.LABEL_LAYER2, plain.LABEL_LAYER3, plain.LABEL_LAYER4) if plain_mode
        else ("層 1　結論", "層 2　核心卡", "層 3　操作（預設收合）", "層 4　佐證（預設收合）")
    )
    _html(f'<div class="set-layer-label">{label1}</div>')
    _render_set0(logic.find_block(model, "SET-0"), plain_mode=plain_mode)
    if plain_mode:
        # BL-0250 批次 3-B（線框 6.3「與結論燈的關係」）：總表不影響燈，燈的說明補一句。燈的判定一個都不動。
        _lines([page_health.TEXT_LAMP_NOTE])
        _render_set0_nav()

    _html(f'<div class="set-layer-label">{label2}</div>')
    with st.container(key="set_layer2"):
        for column, code in zip(st.columns(3), logic.codes_in_layer(model, 2)):
            with column:
                _RENDERERS[code](logic.find_block(model, code), key, ctx)
    if plain_mode:
        _render_page_health(pages)   # ② 資料新鮮度卡下面（BL-0250 批次 3-B）

    if plain_mode:
        # ③需要注意：`SET-1` 已算出的「外」那幾列；沒有就整段不畫（Phase 3 P1-⑥，之八其二 (b-2) 第 4 條）。
        health_view.render_attention(attention, tone_hex=theme.tone_hex, label_class="set-layer-label")
        # ④詳細資料；④ 內「操作」與「證據／來源」兩個小標分開（護欄 6）。
        _html(f'<div class="set-layer-label">{plain.LABEL_DETAILS}</div>')
    _html(f'<div class="set-layer-label">{label3}</div>')
    with st.container(key="set_layer3"):
        for column, code in zip(st.columns(3), logic.codes_in_layer(model, 3)):
            with column:
                if plain_mode:
                    _render_moved(code, logic.find_block(model, code), key, ctx)
                else:
                    _RENDERERS[code](logic.find_block(model, code), key, ctx)

    _html(f'<div class="set-layer-label">{label4}</div>')
    for code in logic.codes_in_layer(model, 4):
        if plain_mode:
            _render_moved(code, logic.find_block(model, code), key, ctx)
        else:
            _RENDERERS[code](logic.find_block(model, code), key, ctx)
    if plain_mode:
        _render_advanced_diag(logic.find_block(model, "SET-6").get("_raw_log"))

    # BL-0250 批次 2（44 第七節第三小節之十一 U1／U2）：正式模式頁尾只畫一句指路句，不加「本頁不負責什麼：」、不掛紅線標記徽章。
    if plain_mode:
        _html(f'<div class="set-footer">{_esc(" ".join(model["footer_lines"]))}</div>')
        return
    footer = "　".join(_esc(line) for line in model["footer_lines"])
    badges = "".join(_badge(b) for b in model["footer_badges"])
    _html(f'<div class="set-footer">本頁不負責什麼：{footer}<br/>{badges}</div>')
