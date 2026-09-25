# -*- coding: utf-8 -*-
"""資產配置的 Streamlit 渲染層。

本檔**只負責畫**：狀態、欄數、文案、結論燈、差距與試算全部住在 logic.py，
這裡一個判定也不做。色票與對比住在 theme.py，假資料住在 fixtures.py。

本檔不 import 舊 repo 任何模組，不發任何網路請求，**不寫任何色碼字面值**
（每一個顏色都從 theme 取 —— 那一份每一組都算過對比）。

⚠️ 本頁的「存檔」「新增假設」「前往 Sheets 維護持倉」三種按鈕畫得出來、按得下去，
   但**本頁沒有後端**：按下去不寫任何東西、也不離開本頁（ALO-GAP-導覽目的地）。
   這是一個用假資料畫的頁面，不是接上資料的成品。
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
    # 層 2／層 3 各包在一個帶 key 的容器裡，Streamlit 會給它 `st-key-<key>` 這個 class，
    # media query 靠它只作用在該層那一排欄（其餘排法照上面那一段單欄）。
    for layer, marker in ((2, "st-key-alo_layer2"), (3, "st-key-alo_layer3")):
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
    """⛔ 2026-09-24 稽核修正：`.stApp span` 的權重（一個 class 加一個元素）高過單一個 `.alo-*` class，
    於是燈的黃字、狀態字、卡片標題的青色全被蓋成主文字色。現在每一條 `.alo-*` 規則都自動前綴 `.stApp `
    （兩個 class），權重一律高過那一條全域規則。畫面層守衛：`test_alo_page.py` 用瀏覽器量實際算出來的顏色。
    """
    return _scoped(_raw_css())


def _scoped(css: str) -> str:
    return re.sub(r"(?m)^(\s*)\.alo-", r"\1.stApp .alo-", css)


def _raw_css() -> str:
    # ALO-GAP-窄寬度表格：格內文字換行（white-space: normal），不出橫向捲動、不藏欄。
    return f"""
    .stApp {{ background: {theme.APP_BG}; }}
    .stApp, .stApp p, .stApp span, .stApp label {{ color: {theme.TEXT_PRIMARY}; }}
    .alo-title {{
      font-size: 1.45rem; font-weight: 700; letter-spacing: .04em;
      color: {theme.TEAL_BRIGHT}; border-bottom: 2px solid {theme.TEAL_DARK};
      padding-bottom: .4rem; margin-bottom: .2rem;
    }}
    .alo-sub {{ color: {theme.TEXT_MUTED}; font-size: .82rem; margin-bottom: .6rem; }}
    .alo-topline {{ color: {theme.STATE_GRAY}; font-size: .9rem; margin: .2rem 0 .6rem; }}
    .alo-layer-label {{
      color: {theme.TEAL_BRIGHT}; font-size: .72rem; letter-spacing: .18em;
      margin: 1.1rem 0 .35rem;
    }}
    .alo-lamp {{
      display: flex; align-items: center; gap: .8rem;
      border: 1px solid var(--alo-tone); border-left: 5px solid var(--alo-tone);
      background: {theme.SURFACE}; border-radius: 8px; padding: .85rem 1rem;
    }}
    .alo-glyph {{ font-size: 1.25rem; line-height: 1; color: var(--alo-tone); }}
    .alo-stword {{
      display: inline-block; font-size: .7rem; font-weight: 700;
      padding: .05rem .4rem; border-left: 3px solid var(--alo-tone); color: var(--alo-tone);
      background: {theme.STATE_GRAY_BG}; margin-right: .5rem;
    }}
    .alo-lamp-text {{ font-size: 1.02rem; font-weight: 600; color: var(--alo-tone); }}
    .alo-code {{ color: {theme.TEXT_MUTED}; font-size: .78rem; margin-left: auto; }}
    .alo-card-head {{
      display: flex; align-items: baseline; gap: .5rem; flex-wrap: wrap;
      border: 1px solid var(--alo-tone); border-bottom: 2px solid var(--alo-tone);
      background: {theme.SURFACE}; border-radius: 8px 8px 0 0; padding: .5rem .8rem;
    }}
    .alo-card-code {{ color: {theme.TEXT_MUTED}; font-size: .72rem; }}
    .alo-card-title {{ font-weight: 700; color: {theme.TEAL_BRIGHT}; }}
    .alo-intro {{ color: {theme.TEXT_SECOND}; font-size: .8rem; margin: .2rem 0 .3rem; }}
    .alo-note {{ font-size: .76rem; color: {theme.TEXT_MUTED}; margin: .2rem 0; }}
    .alo-line {{ font-size: .82rem; color: {theme.TEXT_SECOND}; margin: .2rem 0; }}
    .alo-empty {{
      color: var(--alo-tone); border: 1px dashed {theme.EDGE};
      border-radius: 6px; padding: .5rem .7rem; margin: .4rem 0; font-size: .85rem;
    }}
    .alo-errline {{
      color: {theme.STATE_GRAY}; background: {theme.STATE_GRAY_BG};
      border: 1px solid {theme.STATE_GRAY}; border-radius: 5px;
      padding: .4rem .6rem; margin: .4rem 0; font-size: .8rem;
    }}
    .alo-table {{ width: 100%; border-collapse: collapse; font-size: .78rem; table-layout: auto; }}
    .alo-table th {{
      text-align: left; color: {theme.TEAL_BRIGHT}; border-bottom: 1px solid {theme.TEAL_DARK};
      padding: .3rem .4rem; white-space: normal; word-break: break-word;
    }}
    .alo-table td {{
      border-bottom: 1px solid {theme.BORDER}; padding: .28rem .4rem;
      color: {theme.TEXT_PRIMARY}; white-space: normal; word-break: break-word;
    }}
    .alo-footer {{
      margin-top: 1.6rem; border-top: 1px solid {theme.BORDER}; padding-top: .7rem;
      color: {theme.TEXT_MUTED}; font-size: .78rem;
    }}
    .alo-badge {{
      display: inline-block; border-radius: 999px; padding: .05rem .5rem;
      font-size: .68rem; border: 1px solid var(--alo-tone); color: var(--alo-tone);
      margin-right: .3rem;
    }}
    .stTextInput input {{
      background: {theme.INPUT_BG} !important; border: 1px solid {theme.EDGE} !important;
      color: {theme.TEXT_PRIMARY} !important;
    }}
    .stTextInput input::placeholder {{ color: {theme.PLACEHOLDER} !important; }}
    .stButton button, .stDownloadButton button {{
      background: {theme.BUTTON_BG}; border: 1px solid {theme.EDGE}; color: {theme.TEXT_PRIMARY};
    }}
    """


def _html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def _lines(lines, css="alo-note") -> None:
    for line in lines or ():
        _html(f'<div class="{css}">{_esc(line)}</div>')


def _error_lines(block: dict) -> None:
    # `44` 第五節：狀態不靠顏色單獨辨識 —— 失敗框帶一個圖示。
    # 圖示只住在 logic.SAVE_FAIL_GLYPH（客戶 2026-09-25 裁示 ⛔；⚠ 只留給黃燈），本檔不寫字面。
    for line in block.get("error_lines", ()) or ():
        _html(f'<div class="alo-errline" role="alert">{logic.SAVE_FAIL_GLYPH} {_esc(line)}</div>')


def _placeholder(block: dict) -> None:
    node = block.get("placeholder")
    if not node:
        return
    glyph = node.get("glyph", "")
    text = f"{glyph} {node['text']}" if glyph else node["text"]
    _html(f'<div class="alo-empty" style="--alo-tone:{_tone(node["_tone"])}">{_esc(text)}</div>')


def _buttons(block: dict, prefix: str) -> None:
    for index, button in enumerate(block.get("buttons", ()) or ()):
        st.button(
            button["label"],
            key=f"{prefix}_btn_{index}",
            disabled=not button["_enabled"],
            help=button["disabled_reason"] or None,
        )


def _text_input(field: dict, key: str) -> None:
    """ALO-GAP-輸入元件：輸入欄不屬第五節五類元件的任何一類，照實畫成輸入欄。"""
    st.text_input(field["label"], value=field["value_text"], key=key)


def _table(labels, rows) -> str:
    head = "".join(f"<th>{_esc(label)}</th>" for label in labels)
    body = "".join("<tr>" + "".join(f"<td>{_esc(cell)}</td>" for cell in row) + "</tr>" for row in rows)
    return f'<table class="alo-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def _card_head(block: dict) -> None:
    _html(
        f'<div class="alo-card-head" style="--alo-tone:{_tone(block["_tone"])}">'
        f'<span class="alo-card-code">{_esc(block["code"])}</span>'
        f'<span class="alo-card-title">{_esc(block["title"])}</span></div>'
    )


# ───────────────────────── 層 1 ─────────────────────────


def _render_alo0(block: dict) -> None:
    _html(
        f'<div class="alo-lamp" style="--alo-tone:{_tone(block["_tone"])}">'
        f'<div class="alo-glyph" aria-hidden="true">{_esc(block["glyph"])}</div>'
        f'<div><div><span class="alo-stword">{_esc(block["state_word"])}</span>'
        f'<span class="alo-lamp-text">{_esc(block["text"])}</span></div>'
        f'<div class="alo-note">{_esc(block["answers"])}</div></div>'
        f'<div class="alo-code">{_esc(block["code"])}　{_esc(block["title"])}</div></div>'
    )
    _lines(block["detail_lines"])


# ───────────────────────── 層 2 ─────────────────────────


def _render_alo1(block: dict, scenario: str) -> None:
    _html(f'<div class="alo-intro">{_esc(block["intro_line"])}</div>')
    _card_head(block)
    _placeholder(block)
    fields = block["inputs"]
    target_fields = fields[: 2 * len(block["_rows"])]
    for index, row in enumerate(block["_rows"]):
        left, right = st.columns(2)
        with left:
            _text_input(target_fields[2 * index], f"{scenario}_{target_fields[2 * index]['name']}")
        with right:
            _text_input(target_fields[2 * index + 1], f"{scenario}_{target_fields[2 * index + 1]['name']}")
        if row["tail_text"]:
            _lines([row["tail_text"]], "alo-line")
    _lines(block["unset_lines"], "alo-line")
    for field in fields[2 * len(block["_rows"]) :]:
        _text_input(field, f"{scenario}_{field['name']}")
    _lines(block["tolerance_lines"], "alo-line")
    _lines(block["sum_lines"], "alo-line")
    _error_lines(block)
    _buttons(block, f"{scenario}_alo1")
    _lines([block["answers"]] + block["detail_lines"])


def _render_alo2(block: dict, scenario: str) -> None:
    _card_head(block)
    _placeholder(block)
    if block["_rows"]:
        _html(
            _table(
                block["column_labels"],
                [
                    [r["bucket_text"], r["current_text"], r["target_text"], r["diff_text"], r["band_text"]]
                    for r in block["_rows"]
                ],
            )
        )
    _lines(block["tail_lines"], "alo-line")
    _lines([block["answers"]] + block["detail_lines"])


def _render_alo3(block: dict, scenario: str) -> None:
    _card_head(block)
    fields = block["inputs"]
    for index, row in enumerate(block["input_rows"]):
        left, right = st.columns(2)
        with left:
            _text_input(fields[2 * index], f"{scenario}_{fields[2 * index]['name']}")
        with right:
            _text_input(fields[2 * index + 1], f"{scenario}_{fields[2 * index + 1]['name']}")
        if row["tail_text"]:
            _lines([row["tail_text"]], "alo-line")
    _lines(block["unset_lines"], "alo-line")
    _placeholder(block)
    if block["_rows"]:
        _html(
            _table(
                block["column_labels"],
                [[r["bucket_text"], r["share_text"], r["new_diff_text"]] for r in block["_rows"]],
            )
        )
    _error_lines(block)
    _buttons(block, f"{scenario}_alo3")
    _lines([block["answers"]] + block["detail_lines"])


# ───────────────────────── 層 3 ─────────────────────────


def _expander(block: dict):
    return st.expander(
        f"{block['code']}　{block['title']}　—　{block['summary_text']}",
        expanded=block["_default_open"],
    )


def _render_alo4(block: dict, scenario: str) -> None:
    with _expander(block):
        st.caption(block["answers"])
        for field in block["inputs"][:1]:
            options = list(field["_options"])
            st.radio(
                field["label"],
                options,
                index=None if field["_value"] is None else options.index(field["_value"]),
                format_func=block["basis_option_labels"].get,
                key=f"{scenario}_alo_basis",
                horizontal=True,
            )
        _lines([block["basis_line"]] if block["basis_line"] else [], "alo-line")
        for field in block["inputs"][1:]:
            _text_input(field, f"{scenario}_{field['name']}")
        _lines(block["bucket_unset_lines"], "alo-line")
        if block["_assign_rows"]:
            _html(
                _table(
                    block["assign_labels"],
                    [[r["fund_text"], r["bucket_text"], r["category_text"]] for r in block["_assign_rows"]],
                )
            )
        _lines(block["unassigned_lines"] + block["mismatch_lines"], "alo-line")
        for node in block["fail_nodes"]:
            _placeholder({"placeholder": node})
        _lines(block["detail_lines"])
        _error_lines(block)
        for index, button in enumerate(block["buttons"]):
            st.button(
                button["label"],
                key=f"{scenario}_alo4_btn_{index}",
                disabled=not button["_enabled"],
                help=button["disabled_reason"] or None,
            )
            if button["_action_kind"] == "導覽" and block["goto_note"]:
                # 44 逐字「並在按鈕下方寫一行「持倉資料在 Sheets 維護，本儀表板唯讀」」
                _lines([block["goto_note"]], "alo-line")


def _render_alo5(block: dict, scenario: str) -> None:
    with _expander(block):
        st.caption(block["answers"])
        button = block["buttons"][0]
        st.download_button(
            button["label"],
            data=block["_export_text"],
            file_name=block["file_name"],
            mime="text/csv",
            disabled=not button["_enabled"],
            help=button["disabled_reason"] or None,
            key=f"{scenario}_alo5_export",
        )
        _lines(block["detail_lines"])


# ───────────────────────── 層 4 ─────────────────────────


def _render_alo6(block: dict, scenario: str) -> None:
    with _expander(block):
        st.caption(block["answers"])
        _placeholder(block)
        if block["_rows"]:
            _html(
                _table(
                    block["column_labels"],
                    [
                        [
                            r["fund_text"],
                            r["policy_text"],
                            r["bucket_text"],
                            r["value_text"],
                            r["in_bucket_text"],
                            r["in_total_text"],
                        ]
                        for r in block["_rows"]
                    ],
                )
            )
        _lines(block["footer_lines"], "alo-line")
        _lines(block["detail_lines"])


def _render_alo7(block: dict, scenario: str) -> None:
    with _expander(block):
        st.caption(block["answers"])
        _placeholder(block)
        if block["_rows"]:
            _html(
                _table(
                    block["column_labels"],
                    [[r["key_text"], r["value_text"], r["time_text"]] for r in block["_rows"]],
                )
            )
        _lines(block["detail_lines"])


# ───────────────────────── 整頁 ─────────────────────────


def _pick_scenario() -> str:
    """情境用查詢參數挑，不做成輸入欄（`44` 1.1 節判準：輸入欄不帶非空預設值）。"""
    try:
        name = dict(st.query_params).get("scenario")
    except Exception:
        name = None
    return name if name in fixtures.ALL_SCENARIO_NAMES else "full"


def _pick_save_failed() -> bool:
    try:
        return dict(st.query_params).get("savefail") == "1"
    except Exception:
        return False


_RENDERERS = {
    "ALO-1": _render_alo1,
    "ALO-2": _render_alo2,
    "ALO-3": _render_alo3,
    "ALO-4": _render_alo4,
    "ALO-5": _render_alo5,
    "ALO-6": _render_alo6,
    "ALO-7": _render_alo7,
}


def render() -> None:
    _html(f"<style>{_base_css()}{_grid_css()}</style>")

    scenario = _pick_scenario()
    save_failed = _pick_save_failed()
    model = logic.build_page_model(fixtures.scenario_with(scenario, save_failed=save_failed))

    _html(f'<div class="alo-title">{_esc(model["title"])}</div>')
    label = fixtures.SCENARIO_LABELS[scenario] + ("　·　存檔寫入失敗" if save_failed else "")
    _html(
        f'<div class="alo-sub">{_esc(model["answers"])}　·　{_esc(model["hint_note"])}'
        f"　·　情境 {_esc(label)}</div>"
    )
    # ALO-GAP-灰字落點：照 ALO-1 規則欄現行字面「頁面頂端」。
    _lines(model["top_lines"], "alo-topline")

    _html('<div class="alo-layer-label">層 1　結論</div>')
    _render_alo0(logic.find_block(model, "ALO-0"))

    _html('<div class="alo-layer-label">層 2　核心卡</div>')
    with st.container(key="alo_layer2"):
        for column, code in zip(st.columns(3), logic.codes_in_layer(model, 2)):
            with column:
                _RENDERERS[code](logic.find_block(model, code), scenario)

    _html('<div class="alo-layer-label">層 3　操作（預設收合）</div>')
    with st.container(key="alo_layer3"):
        for column, code in zip(st.columns(3), logic.codes_in_layer(model, 3)):
            with column:
                _RENDERERS[code](logic.find_block(model, code), scenario)

    _html('<div class="alo-layer-label">層 4　佐證（預設收合）</div>')
    for code in logic.codes_in_layer(model, 4):
        _RENDERERS[code](logic.find_block(model, code), scenario)

    footer = "　".join(_esc(line) for line in model["footer_lines"])
    badges = "".join(
        f'<span class="alo-badge" style="--alo-tone:{_tone(b["_tone"])}">{_esc(b["text"])}</span>'
        for b in model["footer_badges"]
    )
    _html(f'<div class="alo-footer">本頁不負責什麼：{footer}<br/>{badges}</div>')
