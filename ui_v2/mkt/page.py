# -*- coding: utf-8 -*-
"""市場總覽的 Streamlit 渲染層。

本檔**只負責畫**：四狀態、欄數、文案模板、結論燈全部住在 logic.py，
這裡一個判定也不做。色票住在 theme.py，假資料住在 fixtures.py。

本檔不 import 舊 repo 任何模組，不發任何網路請求。
"""

from __future__ import annotations

import html
from datetime import datetime, timezone

import streamlit as st

from . import fixtures, live, logic, theme

# 層 2／層 3 的斷點直接由 logic 那支**已被測試釘住**的純函式推出來，
# 不在本檔另寫一份數字（同一個事實只准有一個真相源）。
_MAX_PROBE_WIDTH = 2000


def _breakpoint_edges(layer: int) -> list[tuple[int, int]]:
    """掃出該層欄數改變的寬度邊界，回 [(寬度, 該寬度起的欄數), ...]。"""
    edges: list[tuple[int, int]] = []
    previous = logic.layer_columns(layer, 1)
    for width in range(2, _MAX_PROBE_WIDTH + 1):
        current = logic.layer_columns(layer, width)
        if current != previous:
            edges.append((width, current))
            previous = current
    return edges


def _grid_css() -> str:
    """把 logic 的斷點翻成真的 CSS media query。

    `44` 2.1 量的是**視窗寬度的 CSS 像素**，所以這裡用 media query 而不是
    伺服器端固定欄數 —— 那樣才真的會隨視窗改變。
    """
    column_selector = (
        '[data-testid="stHorizontalBlock"] > [data-testid="stColumn"], '
        '[data-testid="stHorizontalBlock"] > [data-testid="column"]'
    )
    blocks = [
        f"""
        [data-testid="stHorizontalBlock"] {{ flex-wrap: wrap !important; gap: 12px; }}
        {column_selector} {{ flex: 1 1 100% !important; min-width: 0 !important; }}
        """
    ]
    for layer, marker in ((2, "mkt-layer2"), (3, "mkt-layer3")):
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
    .mkt-page-title {{
      font-size: 1.45rem; font-weight: 700; letter-spacing: .04em;
      color: {theme.TEAL_BRIGHT}; border-bottom: 2px solid {theme.TEAL_DARK};
      padding-bottom: .4rem; margin-bottom: .2rem;
    }}
    .mkt-page-sub {{ color: {theme.TEXT_MUTED}; font-size: .82rem; margin-bottom: 1rem; }}
    .mkt-layer-label {{
      color: {theme.TEAL_BRIGHT}; font-size: .72rem; letter-spacing: .18em;
      text-transform: uppercase; margin: 1.1rem 0 .35rem;
    }}
    .mkt-light {{
      display: flex; align-items: center; gap: .8rem;
      border: 1px solid {theme.BORDER}; border-left: 5px solid var(--mkt-tone);
      background: {theme.SURFACE}; border-radius: 8px; padding: .85rem 1rem;
    }}
    .mkt-light-dot {{
      width: 14px; height: 14px; border-radius: 50%;
      background: var(--mkt-tone); flex: 0 0 14px;
    }}
    .mkt-light-text {{ font-size: 1.02rem; font-weight: 600; }}
    .mkt-light-code {{ color: {theme.TEXT_MUTED}; font-size: .78rem; margin-left: auto; }}
    .mkt-card {{
      border: 1px solid {theme.BORDER}; background: {theme.SURFACE};
      border-radius: 8px; padding: .9rem 1rem; height: 100%;
    }}
    .mkt-card-head {{
      display: flex; align-items: baseline; gap: .5rem; flex-wrap: wrap;
      border-bottom: 1px solid {theme.BORDER}; padding-bottom: .45rem; margin-bottom: .6rem;
    }}
    .mkt-card-code {{ color: {theme.TEXT_MUTED}; font-size: .72rem; }}
    .mkt-card-title {{ font-weight: 700; color: {theme.TEAL_BRIGHT}; }}
    .mkt-mv {{ margin: .55rem 0; }}
    .mkt-mv-label {{ color: {theme.TEXT_MUTED}; font-size: .78rem; }}
    .mkt-mv-value {{ font-size: 1.32rem; font-weight: 600; color: var(--mkt-tone); }}
    .mkt-mv-unit {{ font-size: .82rem; color: {theme.TEXT_MUTED}; margin-left: .3rem; }}
    .mkt-mv-note {{ font-size: .74rem; color: {theme.TEXT_MUTED}; }}
    .mkt-detail {{
      border-top: 1px dashed {theme.BORDER}; margin-top: .6rem; padding-top: .5rem;
      font-size: .82rem; color: {theme.TEXT_MUTED};
    }}
    .mkt-badge {{
      display: inline-block; border-radius: 999px; padding: .05rem .5rem;
      font-size: .68rem; border: 1px solid var(--mkt-tone); color: var(--mkt-tone);
      margin-right: .3rem;
    }}
    .mkt-table {{ width: 100%; border-collapse: collapse; font-size: .78rem; }}
    .mkt-table th {{
      text-align: left; color: {theme.TEAL_BRIGHT}; border-bottom: 1px solid {theme.TEAL_DARK};
      padding: .3rem .45rem; white-space: nowrap;
    }}
    .mkt-table td {{
      border-bottom: 1px solid {theme.BORDER}; padding: .28rem .45rem;
      color: {theme.TEXT_PRIMARY}; white-space: nowrap;
    }}
    .mkt-scroll {{ overflow-x: auto; }}
    .mkt-footer {{
      margin-top: 1.6rem; border-top: 1px solid {theme.BORDER}; padding-top: .7rem;
      color: {theme.TEXT_MUTED}; font-size: .8rem;
    }}
    """


def _esc(value) -> str:
    return html.escape(str(value), quote=True)


def _badge_html(badge: dict) -> str:
    tone = theme.tone_hex(badge.get("_tone", "中性"))
    return f'<span class="mkt-badge" style="--mkt-tone:{tone}">{_esc(badge["text"])}</span>'


def _badges_html(badges) -> str:
    return "".join(_badge_html(b) for b in badges)


# ───────────────────────── 層 1 ─────────────────────────


def _render_light(block: dict) -> None:
    tone = theme.tone_hex(block["_tone"])
    st.markdown(
        f"""<div class="mkt-light" style="--mkt-tone:{tone}">
          <div class="mkt-light-dot"></div>
          <div>
            <div class="mkt-light-text">{_esc(block["text"])}</div>
            <div class="mkt-mv-note">{_esc(block["answers"])}</div>
          </div>
          <div class="mkt-light-code">{_esc(block["code"])}　{_esc(block["title"])}</div>
        </div>""",
        unsafe_allow_html=True,
    )
    for index, button in enumerate(block["buttons"]):
        st.button(
            button["label"],
            key=f"{block['code']}_btn_{index}",
            disabled=not button["_enabled"],
            help=button["disabled_reason"] or None,
        )


# ───────────────────────── 層 2 ─────────────────────────


def _main_value_html(main_value: dict) -> str:
    tone = theme.tone_hex(main_value["_tone"])
    unit = main_value["unit_text"]
    unit_html = f'<span class="mkt-mv-unit">{_esc(unit)}</span>' if unit else ""
    lines = [
        f'<div class="mkt-mv">',
        f'  <div class="mkt-mv-label">{_esc(main_value["label"])}</div>',
        f'  <div class="mkt-mv-value" style="--mkt-tone:{tone}">'
        f'{_esc(main_value["value_text"])}{unit_html}</div>',
    ]
    if main_value.get("direction_text"):
        lines.append(f'  <div class="mkt-mv-note">{_esc(main_value["direction_text"])}</div>')
    # 正式模式才有（live.apply_live_notes 加的）：原因、已遮蔽憑證，各另起一行；示範模式沒有這個鍵
    for note in main_value.get("note_lines", ()):
        lines.append(f'  <div class="mkt-mv-note">{_esc(note)}</div>')
    if main_value["badges"]:
        lines.append(f'  <div>{_badges_html(main_value["badges"])}</div>')
    lines.append("</div>")
    return "".join(lines)


def _render_card(block: dict) -> None:
    detail = "".join(
        f'<div>{_esc(line)}</div>' for line in block["detail_lines"]
    )
    detail_html = f'<div class="mkt-detail">{detail}</div>' if detail else ""
    st.markdown(
        f"""<div class="mkt-card">
          <div class="mkt-card-head">
            <span class="mkt-card-code">{_esc(block["code"])}</span>
            <span class="mkt-card-title">{_esc(block["title"])}</span>
            {_badges_html(block["badges"])}
          </div>
          {"".join(_main_value_html(mv) for mv in block["main_values"])}
          {detail_html}
          <div class="mkt-mv-note">{_esc(block["answers"])}</div>
        </div>""",
        unsafe_allow_html=True,
    )
    for index, button in enumerate(block["buttons"]):
        st.button(
            button["label"],
            key=f"{block['code']}_btn_{index}",
            disabled=not button["_enabled"],
            help=button["disabled_reason"] or None,
        )


# ───────────────────────── 層 3 ─────────────────────────


def _as_setting_value(value):
    """`44` 4.5 表 user_setting：setting_value 是**設定值的字串形式**，空值表示未設定。"""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _field_window_days():
    value = st.session_state.get("mkt4_days")
    return int(value) if isinstance(value, (int, float)) else None


def _field_baseline_date():
    return _as_setting_value(st.session_state.get("mkt4_baseline"))


def _on_apply() -> None:
    """`44` MKT-4：套用只讀兩個欄位的當下值、重算三張核心卡，不寫任何資料表。"""
    st.session_state["_mkt_applied"] = {
        "window_days": _field_window_days(),
        "baseline_date": _field_baseline_date(),
    }


def _on_save() -> None:
    """`44` MKT-4：存檔把當下值寫回 user_setting 的同兩鍵並更新 updated_at，
    不重算三張核心卡。本輪的 user_setting 替身是一個 in-memory dict。

    刻意不碰 `_mkt_applied` —— 存檔不重算三張核心卡。
    """
    store = st.session_state.setdefault("_user_setting", {})
    store["mkt_window_days"] = _as_setting_value(st.session_state.get("mkt4_days"))
    store["mkt_baseline_date"] = _field_baseline_date()
    store["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")


def _render_mkt4(block: dict, *, live_mode: bool = False) -> None:
    with st.expander(f"{block['code']}　{block['title']}　—　{block['summary_text']}", expanded=block["_default_open"]):
        st.caption(block["answers"])
        days_field, date_field = block["inputs"]
        st.number_input(
            days_field["label"],
            value=None,  # `44` 逐字：欄位無預設值
            step=1,
            placeholder=days_field["placeholder"],
            key="mkt4_days",
        )
        st.date_input(date_field["label"], value=None, key="mkt4_baseline")
        st.caption(date_field["placeholder"])

        for line in block["detail_lines"]:
            st.caption(line)

        apply_button, save_button = block["buttons"]
        left, right = st.columns(2)
        with left:
            st.button(
                apply_button["label"],
                key="mkt4_apply",
                on_click=_on_apply,
                disabled=not apply_button["_enabled"],
                help=apply_button["disabled_reason"] or None,
            )
        with right:
            st.button(
                save_button["label"],
                key="mkt4_save",
                on_click=_on_save,
                disabled=not save_button["_enabled"],
                help=save_button["disabled_reason"] or None,
            )

        store = {} if live_mode else st.session_state.get("_user_setting", {})
        if store.get("updated_at"):
            st.caption(
                f"user_setting 已存檔，updated_at ＝ {store['updated_at']}"
                f"（本輪的 user_setting 替身是一個 in-memory dict）"
            )
        st.markdown(_badges_html(block["badges"]), unsafe_allow_html=True)
        st.caption("紅線說明區：所有試算參數均由使用者自行輸入。")


def _render_mkt5(block: dict) -> None:
    with st.expander(f"{block['code']}　{block['title']}　—　{block['summary_text']}", expanded=block["_default_open"]):
        st.caption(block["answers"])
        for item in block["_items"]:
            st.checkbox(
                item["label"],
                value=False,  # 一個也沒有預先勾
                key=f"mkt5_{item['name']}",
                disabled=True,  # 唯讀：本塊在 `44` 沒有宣告寫入對象
                help=item["disabled_reason"] or None,
            )
            if item["badges"]:
                st.markdown(_badges_html(item["badges"]), unsafe_allow_html=True)
        for line in block["detail_lines"]:
            st.caption(line)
        st.markdown(_badges_html(block["badges"]), unsafe_allow_html=True)
        st.caption("紅線說明區：勾選狀態由使用者自行輸入，系統不代填。")


# ───────────────────────── 層 4 ─────────────────────────


def _render_mkt6(block: dict) -> None:
    with st.expander(f"{block['code']}　{block['title']}　—　{block['summary_text']}", expanded=block["_default_open"]):
        st.caption(block["answers"])
        if block["_rows"]:
            head = "".join(f"<th>{_esc(label)}</th>" for label in block["column_labels"])
            head += "<th></th>"
            body = []
            for row in block["_rows"]:
                cells = "".join(f"<td>{_esc(row[column])}</td>" for column in block["_columns"])
                badge = (
                    _badge_html({"_tone": "黃", "text": row["_row_badge"]})
                    if row["_row_badge"]
                    else ""
                )
                body.append(f"<tr>{cells}<td>{badge}</td></tr>")
            st.markdown(
                '<div class="mkt-scroll"><table class="mkt-table">'
                f"<thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>",
                unsafe_allow_html=True,
            )
        for line in block["detail_lines"]:
            st.caption(line)


def _render_mkt7(block: dict) -> None:
    with st.expander(f"{block['code']}　{block['title']}　—　{block['summary_text']}", expanded=block["_default_open"]):
        st.caption(block["answers"])
        head = "".join(f"<th>{_esc(label)}</th>" for label in block["column_labels"])
        body = []
        for row in block["_rows"]:
            badge = _badges_html(row["badges"])
            body.append(
                "<tr>"
                f"<td>{_esc(row['indicator_key'])}{badge}</td>"
                f"<td>{_esc(row['obs_text'])}</td>"
                f"<td>{_esc(row['fetched_text'])}</td>"
                f"<td>{_esc(row['tier_text'])}</td>"
                f"<td>{_esc(row['delay_text'])}</td>"
                "</tr>"
            )
        st.markdown(
            '<div class="mkt-scroll"><table class="mkt-table">'
            f"<thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>",
            unsafe_allow_html=True,
        )
        for line in block["detail_lines"]:
            st.caption(line)


# ───────────────────────── 整頁 ─────────────────────────


def _pick_dataset() -> tuple[str, dict]:
    """情境用查詢參數挑，**不做成輸入欄** ——
    `44` 1.1 節判準要求「沒有一列輸入欄帶非空的預設值」，
    而一個情境下拉選單必然帶一個預設值。用 ?scenario=… 就不動到那張表。
    """
    datasets = fixtures.all_datasets()
    name = dict(st.query_params).get("scenario") or "all_ok"
    if name not in datasets:
        name = "all_ok"
    return name, datasets[name]


def render(*, load_live=None) -> None:
    """畫整頁。

    load_live：選填的載入函式（無參數，回傳 {"dataset": 與 fixtures 情境同形, "notes": {...}}）。
    不傳（None）時行為與加這個參數之前完全相同：照舊以 ?scenario= 挑 fixtures 情境。
    傳入時（正式入口 app_mkt_live.py）改由它取得資料，這一條路徑不讀 fixtures，
    並套用 live.apply_live_notes 的正式模式調整；頁首副標只印本頁的提問句 ——
    情境名與示意字樣只屬於示範模式（這一處畫面差異客戶 2026-09-26 已核准）。
    """
    st.markdown(f"<style>{_base_css()}{_grid_css()}</style>", unsafe_allow_html=True)

    live_input = None
    if load_live is None:
        scenario_name, dataset = _pick_dataset()
    else:
        live_input = load_live()
        scenario_name, dataset = None, live_input["dataset"]
    applied = st.session_state.get("_mkt_applied", {})
    model = logic.build_page_model(
        dataset,
        # 驅動三張核心卡的是**已套用**的那一組
        window_days=applied.get("window_days"),
        baseline_date=_as_setting_value(applied.get("baseline_date")),
        # 決定存檔能不能按的是**欄位當下**的值
        field_window_days=_field_window_days(),
        field_baseline_date=_field_baseline_date(),
        selected_keys=None,
    )

    st.markdown(f'<div class="mkt-page-title">{_esc(model["title"])}</div>', unsafe_allow_html=True)
    if live_input is not None:
        model = live.apply_live_notes(model, live_input["notes"])

    if load_live is None:
        st.markdown(
            f'<div class="mkt-page-sub">{_esc(model["answers"])}　·　'
            f'資料為假資料（示意值）·　情境 {_esc(scenario_name)}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="mkt-page-sub">{_esc(model["answers"])}</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="mkt-layer-label">層 1　結論</div>', unsafe_allow_html=True)
    _render_light(logic.find_block(model, "MKT-0"))

    st.markdown(
        '<div class="mkt-layer-label mkt-layer2">層 2　核心卡</div>', unsafe_allow_html=True
    )
    columns = st.columns(3)
    for column, code in zip(columns, logic.codes_in_layer(model, 2)):
        with column:
            _render_card(logic.find_block(model, code))

    st.markdown(
        '<div class="mkt-layer-label mkt-layer3">層 3　操作（預設收合）</div>',
        unsafe_allow_html=True,
    )
    left, right = st.columns(2)
    with left:
        _render_mkt4(logic.find_block(model, "MKT-4"), live_mode=live_input is not None)
    with right:
        _render_mkt5(logic.find_block(model, "MKT-5"))

    st.markdown(
        '<div class="mkt-layer-label">層 4　佐證（預設收合）</div>', unsafe_allow_html=True
    )
    _render_mkt6(logic.find_block(model, "MKT-6"))
    _render_mkt7(logic.find_block(model, "MKT-7"))

    footer = "　".join(_esc(line) for line in model["footer_lines"][:3])
    st.markdown(
        f'<div class="mkt-footer">{footer}<br/>{_esc(model["footer_lines"][3])}　'
        f'{_badges_html(model["footer_badges"])}</div>',
        unsafe_allow_html=True,
    )
