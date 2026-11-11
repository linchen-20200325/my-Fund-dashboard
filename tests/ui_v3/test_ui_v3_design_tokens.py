# -*- coding: utf-8 -*-
"""Design token 命名守衛（批 2b；80 第 5 節；NG-4 A）。純讀檔，不依賴 conftest fixture。

1. 80 第 5 節表格點名的 token 名字全部存在（`state.empty.*` 以前綴對）；名字格式為點分隔小寫；不重複。
2. **只有客戶核准（G3：候選 B 色票＋候選 A 尺寸）的 token 才有值**（核准清單與逐值寫死在本檔，改值必須同步改這裡＝刻意的摩擦）；
   其餘一律 None；80 第 5 節的建議尺度只記在 `proposed`，且逐字對得上 80（核准值可以與 `proposed` 不同，如 caption 12→13）。
3. 唯一真相源：`theme.py`／`shell/nav.py`／`pages/mkt.py` 輸出的 CSS 內，每個色碼都來自 token 表，不得另寫色碼或 rgba；
   G3 批沒有改全 repo 共用的 `.streamlit/config.toml`（改它會連動正式入口與 `ui_v2`）。
4. chip token 與 `StatusChip.kind` 一致；`color.tone.*` 與規則表 tone 鍵一致；`color.status.*` 涵蓋規則表每一列已核准者、
   指向正確的 tone，且不是色碼。
"""
from __future__ import annotations

import re

import ui_v3_guard_lib as lib
from shared.ui_semantics import rules
from ui_v3.design import tokens
from ui_v3.viewmodels import components

DOC_80 = (lib.ROOT / rules.DOC_80).read_text(encoding="utf-8")
SECTION_5 = DOC_80[DOC_80.index("## 5. Design Contract"):DOC_80.index("## 6. View Model Contract")]


def test_token_names_are_dotted_lowercase_and_unique():
    assert len(tokens.TOKEN_NAMES) == len(set(tokens.TOKEN_NAMES))
    for name in tokens.TOKEN_NAMES:
        assert re.fullmatch(r"[a-z][a-z0-9_]*(\.[a-z0-9_]+)+", name), name


def test_every_token_named_in_80_section_5_exists():
    named = set(re.findall(r"`([a-z]+(?:\.[a-z0-9*]+)+)`", SECTION_5))
    assert {"space.1", "type.metric", "chip.attention", "nav.bottom", "state.empty.*"} <= named
    for name in named:
        if name.endswith(".*"):
            assert any(t.startswith(name[:-1]) for t in tokens.TOKEN_NAMES), name
        else:
            assert name in tokens.TOKENS, name


# G3 核准值（#1204 §A.5 候選 B 色票＋候選 A 尺寸；客戶經總管轉達）。逐值寫死：改值必須明確改這裡。
APPROVED_SCALARS = {
    "space.1": "4px", "space.2": "8px", "space.3": "12px", "space.4": "16px", "space.6": "24px", "space.8": "32px",
    "gutter.mobile": "16px",
    "type.page": "1.7rem", "type.section": "1.2rem", "type.metric": "20px", "type.body": "15px", "type.caption": "13px",
    "radius.card": "8px", "elevation.none": "none",
    "color.page.bg": "#f5f7fb", "color.surface": "#ffffff", "color.text.primary": "#172033", "color.text.secondary": "#4a5670",
    "color.primary": "#1a5fd0", "color.card.border": "#7f8ca6",
    "color.sidebar.bg": "#101a33", "color.sidebar.bg2": "#18254a", "color.sidebar.text": "#e6edf3",
    "color.sidebar.text2": "#aab6cf", "color.sidebar.accent": "#5fd3d0", "color.sidebar.border": "#34466e",
}
APPROVED_TONES = {
    "neutral": {"text": "#172033", "background": "#e6eaf3", "border": "#7f8ca6"},
    "grey": {"text": "#172033", "background": "#e6eaf3", "border": "#7f8ca6"},
    "yellow": {"text": "#6b4a0a", "background": "#fbf0d6", "border": "#b7791f"},
    "red": {"text": "#8a1f12", "background": "#fbe6e2", "border": "#c0392b"},
}
APPROVED_CARD = {"border_width": "1px", "padding": "10px 12px"}          # 內距 10×12 刻意不收斂到 4px 基數（G3：A 尺寸）
APPROVED_CHIP = {"radius": "12px", "padding": "1px 10px", "font_size": "14px"}


def test_only_approved_tokens_have_values_and_the_values_are_the_approved_ones():
    expected_valued = (set(APPROVED_SCALARS) | {f"color.tone.{t}" for t in APPROVED_TONES}
                       | {"card.summary", "card.chart", "card.detail"} | {f"chip.{k}" for k in components.CHIP_KINDS})
    assert set(tokens.VALUED_NAMES) == expected_valued
    assert set(tokens.UNVALUED_BY_DESIGN) == set(tokens.TOKENS) - expected_valued
    for name, value in APPROVED_SCALARS.items():
        assert tokens.TOKENS[name].value == value, name
    for tone, value in APPROVED_TONES.items():
        assert dict(tokens.TOKENS[f"color.tone.{tone}"].value) == value, tone
    for name in ("card.summary", "card.chart", "card.detail"):
        assert dict(tokens.TOKENS[name].value) == APPROVED_CARD, name
    for kind in components.CHIP_KINDS:
        assert dict(tokens.TOKENS[f"chip.{kind}"].value) == APPROVED_CHIP, kind


def test_tokens_outside_g3_scope_stay_unvalued():
    for name in tokens.TOKEN_NAMES:
        if name.startswith(("chart.", "state.", "cta.", "nav.", "meta.", "color.status.")):
            assert tokens.TOKENS[name].value is None, name
    for name in ("meta.asof", "meta.source", "meta.freshness"):   # #1204 §A.5：type.caption 含 meta.*，只指向、不另給值
        assert tokens.TOKENS[name].refers_to == "type.caption"


def test_value_accessor_fails_loud_without_a_default():
    import pytest as _pytest
    with _pytest.raises(ValueError):
        tokens.value("chart.height.primary")
    with _pytest.raises(KeyError):
        tokens.value("space.99")


def test_approved_palette_is_light_main_with_dark_blue_sidebar_and_no_dark_main():
    """G2／`DEC-2026-10-27-09`：淺色主內容＋深色側欄；深色主內容不在範圍。"""
    def lum(h):
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    for name in ("color.page.bg", "color.surface"):
        assert lum(tokens.value(name)) > 0.8, name
    for name in ("color.sidebar.bg", "color.sidebar.bg2"):
        assert lum(tokens.value(name)) < 0.05, name


def test_proposed_scales_are_verbatim_from_80_and_not_applied():
    for name in ("space.1", "space.2", "space.3", "space.4", "space.6", "space.8", "gutter.mobile"):
        assert f"`{name}`＝{tokens.TOKENS[name].proposed}" in SECTION_5, name
    sizes = "／".join(tokens.TOKENS[f"type.{n}"].proposed for n in ("page", "section", "metric", "body", "caption"))
    assert f"（建議 {sizes}）" in SECTION_5
    assert "建議尺度，屬提案" in SECTION_5


def _token_color_literals():
    out = {v.lower() for v in APPROVED_SCALARS.values() if v.startswith("#")}
    for tone in APPROVED_TONES.values():
        out |= {v.lower() for v in tone.values()}
    return out


def test_css_has_no_color_literal_outside_the_token_table():
    from ui_v3.design import theme
    from ui_v3.pages import mkt
    from ui_v3.shell import nav

    allowed = _token_color_literals()
    for label, css in (("theme.app_css", theme.app_css()), ("theme.tone_css", theme.tone_css()),
                       ("theme.card_css", theme.card_css(".x")), ("nav.shell_css", nav.shell_css()), ("mkt.CSS", mkt.CSS)):
        assert "rgba(" not in css and "rgb(" not in css, f"{label} 內有 rgb()/rgba() 字面值：不得另寫色，請取 token"
        stray = {h.lower() for h in re.findall(r"#[0-9a-fA-F]{3,8}\b", css)} - allowed
        assert not stray, f"{label} 內有不在 token 表的色碼：{sorted(stray)}"
    assert mkt.CSS.count("#") and nav.shell_css().count("#")


def test_shared_streamlit_config_is_untouched_by_the_g3_batch():
    """`.streamlit/config.toml` 全 repo 共用（正式入口與 `ui_v2` 也讀它）；G3 批只改 ui_v3 自己的 CSS，不得連動別條線的外觀。
    要改它必須由客戶另批（影響正式入口與 ui_v2），改的人同時改這裡。"""
    text = (lib.ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    for legacy in ('primaryColor = "#1f6feb"', 'backgroundColor = "#f6f8fa"', 'secondaryBackgroundColor = "#eef1f4"',
                   'textColor = "#1f2328"', 'backgroundColor = "#0e1117"'):
        assert legacy in text, legacy


def test_every_token_carries_a_source():
    assert all(t.source.strip() for t in tokens.TOKENS.values())


def test_chip_tokens_match_status_chip_kinds():
    assert tokens.CHIP_TOKEN_KINDS == components.CHIP_KINDS
    assert {f"chip.{k}" for k in components.CHIP_KINDS} <= set(tokens.TOKENS)


def test_color_tokens_follow_rules_table_tones():
    assert tokens.TONE_KEYS == tuple(rules.TONES)
    approved = {e.key: e.tone for e in rules.ENTRIES.values() if not e.is_pending}
    assert tokens.STATUS_TONES == approved
    for key, tone in approved.items():
        token = tokens.TOKENS[f"color.status.{key}"]
        assert token.refers_to == f"color.tone.{tone}" and token.refers_to in tokens.TOKENS
    for e in rules.pending_entries():
        assert f"color.status.{e.key}" not in tokens.TOKENS  # 字樣未核准的列不配色
