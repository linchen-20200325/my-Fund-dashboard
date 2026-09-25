# -*- coding: utf-8 -*-
"""設定與診斷的 Streamlit 渲染層。

本檔**只負責畫**：狀態、欄數、文案、結論燈、新鮮度、型別判定全部住在 logic.py，
這裡一個判定也不做。色票與對比住在 theme.py，假資料住在 fixtures.py。

本檔不 import 舊 repo 任何模組，不發任何網路請求，**不寫任何色碼字面值**
（每一個顏色都從 theme 取 —— 那一份每一組都算過對比）。

注意：本頁的「存檔」「重新取數」兩種按鈕畫得出來、按得下去，但**本頁沒有後端**：
   按下去不寫任何東西（SET-GAP-無後端）。這是一個用假資料畫的頁面，不是接上資料的成品。
"""

from __future__ import annotations

import html
import re

import streamlit as st

from . import fixtures, logic, theme

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


def _failbox(lines) -> None:
    # 拍板原型：失敗框掛在該鍵輸入欄下方、灰態容器、兩行；圖示已在字串裡（logic.SAVE_FAIL_GLYPH）。
    body = "<br/>".join(_esc(line) for line in lines)
    _html(f'<div class="set-failbox" role="alert">{body}</div>')


def _cell(text, *, badges=(), tone=None, raw="") -> str:
    body = _esc(text)
    if tone and tone != "中性":
        body = f'<span class="set-cell-tone" style="--set-tone:{_tone(tone)}">{body}</span>'
    body += "".join(_badge(b) for b in badges)
    if raw:
        body += f'<span class="set-raw">{_esc(raw)}</span>'
    return body


def _table(labels, rows) -> str:
    """`rows` 的每一格已經是 `_cell()` 產出的安全 markup。"""
    head = "".join(f"<th>{_esc(label)}</th>" for label in labels)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f'<table class="set-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def _card_head(block: dict) -> None:
    _html(
        f'<div class="set-card-head" style="--set-tone:{_tone(block["_tone"])}">'
        f'<span class="set-card-code">{_esc(block["code"])}</span>'
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


def _render_set0(block: dict) -> None:
    _html(
        f'<div class="set-lamp" style="--set-tone:{_tone(block["_tone"])}">'
        f'<div class="set-glyph" aria-hidden="true">{_esc(block["glyph"])}</div>'
        f'<div><div><span class="set-stword">{_esc(block["state_word"])}</span>'
        f'<span class="set-lamp-text">{_esc(block["text"])}</span></div>'
        f'<div class="set-note">{_esc(block["answers"])}</div></div>'
        f'<div class="set-code">{_esc(block["code"])}　{_esc(block["title"])}</div></div>'
    )
    _lines(block["detail_lines"])


# ───────────────────────── 層 2 ─────────────────────────


def _render_set1(block: dict, key: str) -> None:
    _card_head(block)
    rows = []
    for row in block["_rows"]:
        fail_tone = "紅" if row["_failed"] else None
        rows.append(
            [
                _cell(row["kind_text"], badges=row["badges"]),
                _cell(row["at_text"], tone=fail_tone),
                _cell(row["days_text"]),
                _cell(row["compare_text"]),
            ]
        )
    _html(_table(block["column_labels"], rows))
    _placeholders(block["fail_nodes"])
    _lines(block["limit_lines"], "set-line")
    _lines([block["answers"]] + block["detail_lines"])


def _render_set2(block: dict, key: str) -> None:
    _card_head(block)
    _placeholders([block["placeholder"]])
    if block["_rows"]:
        rows = [
            [
                _cell(r["tier_text"], badges=r["badges"]),
                _cell(r["result_text"], tone=r["_tone"] if r["_tone"] == "紅" else None),
                _cell(r["time_text"]),
                _cell(r["message_text"], tone=r["_tone"] if r["_tone"] == "紅" else None),
            ]
            for r in block["_rows"]
        ]
        _html(_table(block["column_labels"], rows))
    _lines([block["answers"]] + block["detail_lines"])


def _render_set3(block: dict, key: str) -> None:
    _card_head(block)
    _placeholders([block["placeholder"]])
    if block["_rows"]:
        rows = [
            [_cell(r["key_text"]), _cell(r["value_text"], raw=r["raw_text"]), _cell(r["kind_text"]), _cell(r["time_text"])]
            for r in block["_rows"]
        ]
        _html(_table(block["column_labels"], rows))
    _lines([block["answers"]] + block["detail_lines"])


# ───────────────────────── 層 3 ─────────────────────────


def _expander(block: dict):
    return st.expander(
        f"{block['code']}　{block['title']}　—　{block['summary_text']}",
        expanded=block["_default_open"],
    )


def _render_set4(block: dict, key: str) -> None:
    with _expander(block):
        st.caption(block["answers"])
        _placeholders(block["fail_nodes"])
        for lines in block["orphan_fail_lines"]:
            _failbox(lines)
        for field in block["inputs"]:
            widget = st.text_area if field["_multiline"] else st.text_input  # SET-GAP-輸入欄型態
            widget(field["label"], value=field["value_text"], key=f"{key}_{field['name']}")
            _lines([field["used_by_text"]])
            _lines(field["unset_lines"], "set-line")
            _lines(field["hint_lines"], "set-hint")
            if field["fail_lines"]:
                _failbox(field["fail_lines"])
        _buttons(block["buttons"], f"{key}_set4")
        _lines(block["detail_lines"])


def _render_set5(block: dict, key: str) -> None:
    with _expander(block):
        st.caption(block["answers"])
        picked = st.radio(
            block["tier_label"],
            list(block["tier_options"]),
            index=None,
            key=f"{key}_set5_tier",
            horizontal=True,
        )
        # 停用與否由 logic 依單選的當下值判定；本檔不自己判。
        _buttons([logic.set5_button(picked)], f"{key}_set5")
        _lines(block["detail_lines"])


# ───────────────────────── 層 4 ─────────────────────────


def _render_set6(block: dict, key: str) -> None:
    with _expander(block):
        st.caption(block["answers"])
        _placeholders([block["placeholder"]])
        if block["_rows"]:
            _html(_table(block["column_labels"], [[_cell(c) for c in r["cells"]] for r in block["_rows"]]))
        _lines(block["tail_lines"], "set-line")
        _lines(block["detail_lines"])


def _render_set7(block: dict, key: str) -> None:
    with _expander(block):
        st.caption(block["answers"])
        rows = [[_cell(r["field_text"], badges=r["badges"]), _cell(r["blocks_text"])] for r in block["_rows"]]
        _html(_table(block["column_labels"], rows))
        _lines(block["detail_lines"])


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


def render() -> None:
    _html(f"<style>{_base_css()}{_grid_css()}</style>")

    scenario = _pick_scenario()
    save_failed = _pick_save_failed()
    model = logic.build_page_model(fixtures.scenario_with(scenario, save_failed=save_failed))
    # 輸入欄的 key 帶情境與開關：換情境時不沿用上一個情境留在 session 裡的值。
    key = f"{scenario}_{int(save_failed)}"

    _html(f'<div class="set-title">{_esc(model["title"])}</div>')
    label = fixtures.SCENARIO_LABELS[scenario] + ("　·　存檔寫入失敗" if save_failed else "")
    _html(
        f'<div class="set-sub">{_esc(model["answers"])}　·　{_esc(model["hint_note"])}'
        f"　·　情境 {_esc(label)}</div>"
    )

    _html('<div class="set-layer-label">層 1　結論</div>')
    _render_set0(logic.find_block(model, "SET-0"))

    _html('<div class="set-layer-label">層 2　核心卡</div>')
    with st.container(key="set_layer2"):
        for column, code in zip(st.columns(3), logic.codes_in_layer(model, 2)):
            with column:
                _RENDERERS[code](logic.find_block(model, code), key)

    _html('<div class="set-layer-label">層 3　操作（預設收合）</div>')
    with st.container(key="set_layer3"):
        for column, code in zip(st.columns(3), logic.codes_in_layer(model, 3)):
            with column:
                _RENDERERS[code](logic.find_block(model, code), key)

    _html('<div class="set-layer-label">層 4　佐證（預設收合）</div>')
    for code in logic.codes_in_layer(model, 4):
        _RENDERERS[code](logic.find_block(model, code), key)

    footer = "　".join(_esc(line) for line in model["footer_lines"])
    badges = "".join(_badge(b) for b in model["footer_badges"])
    _html(f'<div class="set-footer">本頁不負責什麼：{footer}<br/>{badges}</div>')
