# -*- coding: utf-8 -*-
"""持倉體檢的 Streamlit 渲染層。

本檔**只負責畫**：四狀態、欄數、文案模板、結論燈、算式全部住在 logic.py，
這裡一個判定也不做。色票與對比住在 theme.py，假資料住在 fixtures.py。

本檔不 import 舊 repo 任何模組，不發任何網路請求，**不寫任何色碼字面值**
（每一個顏色都從 theme 取 —— 那一份每一組都算過對比）。
"""

from __future__ import annotations

import html

import streamlit as st

from . import fixtures, logic, theme

_MAX_PROBE_WIDTH = 2000


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
    for layer, marker in ((2, "hld-layer2"), (3, "hld-layer3")):
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
    return "".join(blocks)


def _base_css() -> str:
    return f"""
    .stApp {{ background: {theme.APP_BG}; }}
    .stApp, .stApp p, .stApp span, .stApp label {{ color: {theme.TEXT_PRIMARY}; }}
    .hld-title {{
      font-size: 1.45rem; font-weight: 700; letter-spacing: .04em;
      color: {theme.TEAL_BRIGHT}; border-bottom: 2px solid {theme.TEAL_DARK};
      padding-bottom: .4rem; margin-bottom: .2rem;
    }}
    .hld-sub {{ color: {theme.TEXT_MUTED}; font-size: .82rem; margin-bottom: 1rem; }}
    .hld-layer-label {{
      color: {theme.TEAL_BRIGHT}; font-size: .72rem; letter-spacing: .18em;
      text-transform: uppercase; margin: 1.1rem 0 .35rem;
    }}
    .hld-lamp {{
      display: flex; align-items: center; gap: .8rem;
      border: 1px solid var(--hld-tone); border-left: 5px solid var(--hld-tone);
      background: {theme.SURFACE}; border-radius: 8px; padding: .85rem 1rem;
    }}
    .hld-glyph {{ font-size: 1.25rem; line-height: 1; flex: 0 0 auto; }}
    .hld-stword {{
      display: inline-block; font-size: .68rem; font-weight: 700; border-radius: 999px;
      padding: .05rem .5rem; border: 1px solid var(--hld-tone); color: var(--hld-tone);
      margin-right: .5rem;
    }}
    .hld-lamp-text {{ font-size: 1.02rem; font-weight: 600; color: var(--hld-tone); }}
    .hld-code {{ color: {theme.TEXT_MUTED}; font-size: .78rem; margin-left: auto; }}
    .hld-card {{
      border: 1px solid var(--hld-tone); background: {theme.SURFACE};
      border-radius: 8px; padding: .9rem 1rem; height: 100%;
    }}
    .hld-card-head {{
      display: flex; align-items: baseline; gap: .5rem; flex-wrap: wrap;
      border-bottom: 1px solid {theme.BORDER}; padding-bottom: .45rem; margin-bottom: .6rem;
    }}
    .hld-card-code {{ color: {theme.TEXT_MUTED}; font-size: .72rem; }}
    .hld-card-title {{ font-weight: 700; color: {theme.TEAL_BRIGHT}; }}
    .hld-fgrp {{
      border: 1px solid {theme.BORDER}; border-radius: 6px;
      padding: .45rem .6rem; margin: .5rem 0;
    }}
    .hld-fh {{ font-size: .78rem; color: {theme.TEXT_SECOND}; margin-bottom: .3rem; }}
    .hld-mv {{ display: flex; justify-content: space-between; gap: .6rem; margin: .22rem 0; }}
    .hld-mv-label {{ color: {theme.TEXT_MUTED}; font-size: .76rem; }}
    .hld-mv-value {{ font-size: .98rem; font-weight: 600; color: var(--hld-tone); text-align: right; }}
    .hld-note {{ font-size: .75rem; color: {theme.TEXT_MUTED}; }}
    .hld-detail {{
      border-top: 1px dashed {theme.BORDER}; margin-top: .6rem; padding-top: .5rem;
      font-size: .78rem; color: {theme.TEXT_MUTED};
    }}
    .hld-errline {{ color: {theme.STATE_ERR}; font-weight: 700; font-size: .95rem; }}
    .hld-errdetail {{
      color: {theme.ERR_MSG_FG}; background: {theme.ERR_MSG_BG};
      border: 1px solid {theme.ERR_MSG_EDGE}; border-radius: 5px;
      padding: .3rem .5rem; font-size: .76rem; margin: .3rem 0;
    }}
    .hld-badge {{
      display: inline-block; border-radius: 999px; padding: .05rem .5rem;
      font-size: .68rem; border: 1px solid var(--hld-tone); color: var(--hld-tone);
      margin-right: .3rem;
    }}
    .hld-table {{ width: 100%; border-collapse: collapse; font-size: .76rem; }}
    .hld-table th {{
      text-align: left; color: {theme.TEAL_BRIGHT}; border-bottom: 1px solid {theme.TEAL_DARK};
      padding: .3rem .45rem; white-space: nowrap;
    }}
    .hld-table td {{
      border-bottom: 1px solid {theme.BORDER}; padding: .28rem .45rem;
      color: {theme.TEXT_PRIMARY}; white-space: nowrap;
    }}
    .hld-scroll {{ overflow-x: auto; max-height: 26rem; overflow-y: auto; }}
    .hld-kv {{
      display: grid; grid-template-columns: max-content 1fr; gap: .18rem .8rem;
      font-size: .78rem; margin: .3rem 0;
    }}
    .hld-kv span {{ color: {theme.TEXT_MUTED}; }}
    .hld-kv b {{ color: {theme.TEXT_PRIMARY}; font-weight: 600; }}
    .hld-plot {{
      border: 1px dashed {theme.EDGE}; border-radius: 6px; padding: .55rem .7rem;
      color: {theme.TEXT_MUTED}; font-size: .76rem; margin: .3rem 0;
    }}
    .hld-footer {{
      margin-top: 1.6rem; border-top: 1px solid {theme.BORDER}; padding-top: .7rem;
      color: {theme.TEXT_MUTED}; font-size: .78rem;
    }}
    .stTextInput input, .stTextInput input::placeholder {{ color: {theme.TEXT_PRIMARY}; }}
    .stTextInput input {{
      background: {theme.INPUT_BG} !important; border: 1px solid {theme.EDGE} !important;
    }}
    .stTextInput input::placeholder {{ color: {theme.PLACEHOLDER} !important; }}
    .stButton button {{
      background: {theme.BUTTON_BG}; border: 1px solid {theme.EDGE};
      color: {theme.TEXT_PRIMARY};
    }}
    """


def _esc(value) -> str:
    return html.escape(str(value), quote=True)


def _tone(value) -> str:
    return theme.tone_hex(value)


def _badge_html(badge: dict) -> str:
    return (
        f'<span class="hld-badge" style="--hld-tone:{_tone(badge.get("_tone", "中性"))}">'
        f'{_esc(badge["text"])}</span>'
    )


def _badges_html(badges) -> str:
    return "".join(_badge_html(b) for b in badges)


def _buttons(block, prefix) -> None:
    for index, button in enumerate(block.get("buttons", [])):
        st.button(
            button["label"],
            key=f"{prefix}_btn_{index}",
            disabled=not button["_enabled"],
            help=button["disabled_reason"] or None,
        )


def _lines(lines) -> None:
    for line in lines:
        st.caption(line)


# ───────────────────────── 層 1 ─────────────────────────


def _render_lamp(block: dict) -> None:
    tone = _tone(block["_tone"])
    st.markdown(
        f"""<div class="hld-lamp" style="--hld-tone:{tone}">
          <div class="hld-glyph" aria-hidden="true">{_esc(block["glyph"])}</div>
          <div>
            <div><span class="hld-stword">{_esc(block["state_word"])}</span>
              <span class="hld-lamp-text">{_esc(block["text"])}</span></div>
            <div class="hld-note">{_esc(block["answers"])}</div>
          </div>
          <div class="hld-code">{_esc(block["code"])}　{_esc(block["title"])}</div>
        </div>""",
        unsafe_allow_html=True,
    )
    _lines(block["lines"])
    _buttons(block, block["code"])
    _lines(block["detail_lines"])


# ───────────────────────── 層 2 ─────────────────────────


def _card_shell(block: dict, body_html: str) -> None:
    st.markdown(
        f"""<div class="hld-card" style="--hld-tone:{_tone(block["_tone"])}">
          <div class="hld-card-head">
            <span class="hld-card-code">{_esc(block["code"])}</span>
            <span class="hld-card-title">{_esc(block["title"])}</span>
            {_badges_html(block["badges"])}
          </div>
          {body_html}
          <div class="hld-note">{_esc(block["answers"])}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def _render_hld1(block: dict) -> None:
    parts = []
    if block["_rows"]:
        head = "".join(f"<th>{_esc(label)}</th>" for label in block["column_labels"])
        body = "".join(
            "<tr>"
            f"<td>{_esc(row['fund_name'])}</td>"
            f"<td>{_esc(row['actual_text'])}</td>"
            f"<td>{_esc(row['threshold_text'])}</td>"
            f"<td>{_esc(row['delta_text'])}</td>"
            "</tr>"
            for row in block["_rows"]
        )
        parts.append(
            '<div class="hld-scroll"><table class="hld-table">'
            f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"
        )
    placeholder = block.get("_placeholder")
    if placeholder is not None:
        parts.append(
            f'<div class="hld-mv-value" style="--hld-tone:{_tone(placeholder["_tone"])}">'
            f'{_esc(placeholder["text"])}</div>'
        )
    elif not block["_rows"]:
        parts.append(
            f'<div class="hld-mv-value" style="--hld-tone:{_tone("灰")}">'
            f'{_esc(logic.TEXT_NO_DEVIATION)}</div>'
        )
    for line in block["tail_lines"]:
        parts.append(f'<div class="hld-note">{_esc(line)}</div>')
    detail = "".join(f"<div>{_esc(line)}</div>" for line in block["detail_lines"])
    if detail:
        parts.append(f'<div class="hld-detail">{detail}</div>')
    parts.append(
        f'<div class="hld-detail">{_badges_html(block["badges"])}'
        f'{_esc(block["redline_note"])}</div>'
    )
    _card_shell(block, "".join(parts))
    _buttons(block, block["code"])


def _render_core_card(block: dict) -> None:
    parts = []
    for group in block["fund_groups"]:
        rows = "".join(
            f'<div class="hld-mv">'
            f'<span class="hld-mv-label">{_esc(mv["label"])}</span>'
            f'<span class="hld-mv-value" style="--hld-tone:{_tone(mv["_tone"])}">'
            f'{_esc(mv["text"])}</span></div>'
            for mv in group["main_values"]
        )
        parts.append(
            f'<div class="hld-fgrp"><div class="hld-fh">{_esc(group["head_text"])}</div>'
            f"{rows}</div>"
        )
    detail = "".join(f"<div>{_esc(line)}</div>" for line in block["detail_lines"])
    if detail:
        parts.append(f'<div class="hld-detail">{detail}</div>')
    _card_shell(block, "".join(parts))
    _buttons(block, block["code"])


# ───────────────────────── 層 3 ─────────────────────────


def _expander(block: dict):
    return st.expander(
        f"{block['code']}　{block['title']}　—　{block['summary_text']}",
        expanded=block["_default_open"],
    )


def _render_hld4(block: dict) -> None:
    with _expander(block):
        st.caption(block["answers"])
        columns = st.columns(2)
        for column, field in zip(columns, block["inputs"]):
            with column:
                st.text_input(
                    field["label"],
                    value=field["_value"] or "",
                    placeholder=field["placeholder"],
                    key=f"hld4_{field['name']}",
                )
        st.caption("門檻（指標名＋比較方向＋數值，可增減列）")
        for index, row in enumerate(block["threshold_rows"]):
            cells = st.columns([3, 2, 2, 2])
            for cell, field in zip(cells, row):
                with cell:
                    st.text_input(
                        field["label"],
                        value="" if field["_value"] == "" else str(field["_value"]),
                        placeholder=field["placeholder"],
                        key=f"hld4_{field['name']}",
                    )
            with cells[3]:
                button = block["row_buttons"][index]
                st.button(button["label"], key=f"hld4_row_{index}")
        _lines(block["detail_lines"])
        _buttons(block, "hld4")
        _lines(block["notes"])
        st.markdown(
            f'<div class="hld-detail">{_badges_html(block["badges"])}'
            f'{_esc(block["redline_note"])}</div>',
            unsafe_allow_html=True,
        )


def _render_hld5(block: dict) -> None:
    with _expander(block):
        st.caption(block["answers"])
        _lines(block["detail_lines"])
        for item in block["_items"]:
            with st.expander(item["head_text"], expanded=item["_open"]):
                kv = "".join(
                    f"<span>{_esc(label)}</span><b>{_esc(value)}</b>"
                    for label, value in item["_fields"]
                )
                st.markdown(
                    f'<div class="hld-kv">{kv}</div>'
                    f'<div class="hld-plot">{_esc(item["nav_plot_text"])}</div>'
                    f'<div class="hld-plot">{_esc(item["div_plot_text"])}</div>',
                    unsafe_allow_html=True,
                )


# ───────────────────────── 層 4 ─────────────────────────


def _table_html(labels, rows, cells) -> str:
    head = "".join(f"<th>{_esc(label)}</th>" for label in labels)
    body = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in cells(row)) + "</tr>"
        for row in rows
    )
    return (
        '<div class="hld-scroll"><table class="hld-table">'
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"
    )


def _render_hld6(block: dict) -> None:
    with _expander(block):
        st.caption(block["answers"])
        if block["nav_rows"]:
            st.caption("淨值表")
            st.markdown(
                _table_html(
                    block["nav_labels"],
                    block["nav_rows"],
                    lambda row: [
                        _esc(row["fund_code"]),
                        _esc(row["nav_date"]),
                        _esc(row["nav_text"]),
                        _esc(row["ccy"]),
                        _badge_html({"_tone": "中性", "text": row["source_tier"]}),
                        _badge_html({"_tone": "黃", "text": row["_estimated_badge"]})
                        if row["_estimated_badge"]
                        else "—",
                    ],
                ),
                unsafe_allow_html=True,
            )
        if block["div_rows"]:
            st.caption("配息表")
            st.markdown(
                _table_html(
                    block["div_labels"],
                    block["div_rows"],
                    lambda row: [
                        _esc(row["fund_code"]),
                        _esc(row["ex_date"]),
                        _esc(row["pay_date"]),
                        _esc(row["div_text"]),
                        _esc(row["ccy"]),
                        _esc(row["div_kind"]),
                    ],
                ),
                unsafe_allow_html=True,
            )
        _lines(block["detail_lines"])


def _render_hld7(block: dict) -> None:
    with _expander(block):
        st.caption(block["answers"])
        if block["_rows"]:
            st.markdown(
                _table_html(
                    block["column_labels"],
                    block["_rows"],
                    lambda row: [
                        _esc(row["indicator_text"]),
                        _esc(row["inputs_text"]),
                        _esc(row["formula_text"]),
                        _esc(row["output_text"]),
                    ],
                ),
                unsafe_allow_html=True,
            )
        _lines(block["detail_lines"])


def _render_hld8(block: dict) -> None:
    with _expander(block):
        st.caption(block["answers"])
        if block["_rows"]:
            st.markdown(
                _table_html(
                    block["column_labels"],
                    block["_rows"],
                    lambda row: [
                        _esc(row["fund_name"]),
                        _esc(row["ccy_text"]),
                        f'<span style="color:{_tone(row["drawdown"]["_tone"])}">'
                        f'{_esc(row["drawdown"]["text"])}</span>',
                        f'<span style="color:{_tone(row["principal"]["_tone"])}">'
                        f'{_esc(row["principal"]["text"])}</span>',
                    ],
                ),
                unsafe_allow_html=True,
            )
        _lines(block["detail_lines"])
        _buttons(block, "hld8")


# ───────────────────────── 整頁 ─────────────────────────


def _pick_scenario() -> str:
    """情境用查詢參數挑，**不做成輸入欄** ——
    `44` 1.1 節判準要求「沒有一列輸入欄帶非空的預設值」，
    而一個情境下拉選單必然帶一個預設值。用 ?scenario=… 就不動到那張表。
    """
    try:
        name = dict(st.query_params).get("scenario")
    except Exception:
        name = None
    if name not in fixtures.SCENARIO_NAMES:
        name = "full"
    return name


_RENDERERS = {
    "HLD-1": _render_hld1,
    "HLD-2": _render_core_card,
    "HLD-3": _render_core_card,
    "HLD-4": _render_hld4,
    "HLD-5": _render_hld5,
    "HLD-6": _render_hld6,
    "HLD-7": _render_hld7,
    "HLD-8": _render_hld8,
}


def render() -> None:
    st.markdown(f"<style>{_base_css()}{_grid_css()}</style>", unsafe_allow_html=True)

    scenario = _pick_scenario()
    model = logic.build_page_model(**fixtures.scenario(scenario))

    st.markdown(
        f'<div class="hld-title">{_esc(model["title"])}</div>', unsafe_allow_html=True
    )
    st.markdown(
        f'<div class="hld-sub">{_esc(model["answers"])}　·　'
        f'資料為假資料，每一個數字都帶「示意」二字　·　'
        f'情境 {_esc(fixtures.SCENARIO_LABELS[scenario])}</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="hld-layer-label">層 1　結論</div>', unsafe_allow_html=True)
    _render_lamp(logic.find_block(model, "HLD-0"))

    st.markdown(
        '<div class="hld-layer-label hld-layer2">層 2　核心卡</div>',
        unsafe_allow_html=True,
    )
    for column, code in zip(st.columns(3), logic.codes_in_layer(model, 2)):
        with column:
            _RENDERERS[code](logic.find_block(model, code))

    st.markdown(
        '<div class="hld-layer-label hld-layer3">層 3　操作（預設收合）</div>',
        unsafe_allow_html=True,
    )
    # `44` 2.1：層 3 只有兩塊，兩塊並排同一列，第三欄空著。
    for column, code in zip(st.columns(3), logic.codes_in_layer(model, 3)):
        with column:
            _RENDERERS[code](logic.find_block(model, code))

    st.markdown(
        '<div class="hld-layer-label">層 4　佐證（預設收合）</div>', unsafe_allow_html=True
    )
    for code in logic.codes_in_layer(model, 4):
        _RENDERERS[code](logic.find_block(model, code))

    footer = "　".join(_esc(line) for line in model["footer_lines"][:3])
    st.markdown(
        f'<div class="hld-footer">本頁不負責什麼：{footer}<br/>'
        f'{_esc(model["footer_lines"][3])}　'
        f'{_badges_html(model["footer_badges"])}</div>',
        unsafe_allow_html=True,
    )
