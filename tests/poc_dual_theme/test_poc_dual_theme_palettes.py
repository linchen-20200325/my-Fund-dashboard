# -*- coding: utf-8 -*-
"""雙模式隔離 PoC：色票與 CSS 產生器的純單元測試（不起 Streamlit、不開瀏覽器）。

- light 值唯讀比對 `ui_v3.design.tokens`（只在**測試**裡 import，PoC 程式本身不 import ui_v3）：防 PoC 的 light fixture 與核准值漂移。
- 每個 CSS 色碼都必須來自該模式的 palette（單一真相源）；不含 JS／外部資源。
- 對比度由本 PoC 自寫的 WCAG 計算器（`poc_dual_theme_contrast_lib`）算；該計算器本身也有已知值測試。
"""
import pathlib
import re
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "poc" / "dual_theme_isolated"))

import poc_dual_theme_contrast_lib as cl  # noqa: E402
import poc_palettes as pal  # noqa: E402
import poc_theme_css as css  # noqa: E402

_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")


# ───────────────────────── 計算器自身 ─────────────────────────

def test_contrast_lib_known_values():
    assert cl.ratio((0, 0, 0), (255, 255, 255)) == pytest.approx(21.0)
    assert cl.ratio((255, 255, 255), (255, 255, 255)) == pytest.approx(1.0)
    assert cl.ratio((119, 119, 119), (255, 255, 255)) == pytest.approx(4.478, abs=0.002)  # #777 on white（WCAG 常見值）
    assert cl.ratio((255, 255, 255), (0, 0, 0)) == pytest.approx(21.0)  # 對稱


def test_contrast_lib_alpha_compositing():
    # 50% 黑在白上＝(127.5,127.5,127.5)；對白的比值應等於該灰對白
    comp = cl.composite((0, 0, 0, 0.5), (255, 255, 255))
    assert comp == pytest.approx((127.5, 127.5, 127.5))
    assert cl.text_ratio("rgba(0, 0, 0, 0.5)", (255, 255, 255)) == pytest.approx(cl.ratio((127.5,) * 3, (255,) * 3))
    # 疊底：透明層不改變底色；不透明層完全取代
    assert cl.effective_background([("rgba(0, 0, 0, 0)", 1.0), ("rgb(10, 20, 30)", 1.0)]) == pytest.approx((10, 20, 30))
    assert cl.effective_background([("rgb(200, 0, 0)", 1.0), ("rgb(10, 20, 30)", 1.0)]) == pytest.approx((200, 0, 0))
    # 最內層半透明疊在外層上（chain 由內到外）
    mixed = cl.effective_background([("rgba(255, 255, 255, 0.5)", 1.0), ("rgb(0, 0, 0)", 1.0)])
    assert mixed == pytest.approx((127.5, 127.5, 127.5))
    # 祖先 opacity 會縮小該層 alpha
    half = cl.effective_background([("rgb(255, 255, 255)", 0.5), ("rgb(0, 0, 0)", 1.0)])
    assert half == pytest.approx((127.5, 127.5, 127.5))


def test_contrast_lib_large_text_rules():
    assert cl.required_text_ratio(14, 400) == 4.5
    assert cl.required_text_ratio(24, 400) == 3.0
    assert cl.required_text_ratio(18.66, 700) == 3.0
    assert cl.required_text_ratio(18.66, 400) == 4.5


def test_contrast_lib_rejects_unparseable_color():
    with pytest.raises(ValueError):
        cl.parse_color("hsl(10, 20%, 30%)")


# ───────────────────────── 色票 ─────────────────────────

def test_light_palette_equals_approved_ui_v3_tokens_read_only():
    from ui_v3.design import tokens  # 唯讀；測試端 import，PoC 程式不 import
    L = pal.LIGHT
    approved = {"page_bg": "color.page.bg", "surface": "color.surface", "text": "color.text.primary", "text2": "color.text.secondary",
                "primary": "color.primary", "card_border": "color.card.border", "sidebar_bg": "color.sidebar.bg",
                "sidebar_text": "color.sidebar.text", "sidebar_border": "color.sidebar.border"}
    for key, token in approved.items():
        assert L[key] == tokens.value(token), (key, token)
    for tone in tokens.TONE_KEYS:
        assert dict(L["tones"][tone]) == dict(tokens.value(f"color.tone.{tone}")), tone


def test_dark_values_are_fixtures_not_in_ui_v3_tokens():
    """T4：暗色 HEX 只存在於 PoC；`ui_v3/design/tokens.py` 不得含任何「暗色獨有」的值。"""
    tokens_src = (_ROOT / "ui_v3" / "design" / "tokens.py").read_text(encoding="utf-8").lower()
    dark_only = pal.all_hex(pal.DARK) - pal.all_hex(pal.LIGHT)
    assert dark_only, "dark 與 light 完全相同（PoC 失效）"
    leaked = sorted(h for h in dark_only if h in tokens_src)
    assert not leaked, f"ui_v3 tokens.py 出現 PoC dark 值：{leaked}"


def test_modes_and_default():
    assert pal.MODES == ("light", "dark")
    assert pal.DEFAULT_MODE == "light"
    assert pal.get("light") is pal.LIGHT and pal.get("dark") is pal.DARK
    with pytest.raises(ValueError):
        pal.get("auto")
    with pytest.raises(ValueError):
        pal.get("")


def test_palettes_have_same_keys_and_are_read_only():
    assert set(pal.LIGHT) == set(pal.DARK)
    assert set(pal.LIGHT["tones"]) == set(pal.DARK["tones"]) == set(pal.TONE_KEYS)
    with pytest.raises(TypeError):
        pal.LIGHT["page_bg"] = "#000000"  # type: ignore[index]


# ───────────────────────── CSS 產生器 ─────────────────────────

@pytest.mark.parametrize("mode", ["light", "dark"])
def test_css_colors_all_come_from_palette(mode):
    p = pal.get(mode)
    out = css.build_css(p)
    used = {h.lower() for h in _HEX.findall(out)}
    assert used, "CSS 沒有任何色碼（產生器失效）"
    assert used <= pal.all_hex(p), f"CSS 出現不在 palette 的色碼：{sorted(used - pal.all_hex(p))}"
    assert f'data-poc-theme="{mode}"' in out and f"color-scheme:{p['color_scheme']}" in out


def test_css_differs_between_modes_and_has_no_cross_leak():
    light, dark = css.build_css(pal.LIGHT), css.build_css(pal.DARK)
    assert light != dark
    # 暗色獨有色碼不得出現在淺色 CSS，反之亦然
    only_dark = pal.all_hex(pal.DARK) - pal.all_hex(pal.LIGHT)
    only_light = pal.all_hex(pal.LIGHT) - pal.all_hex(pal.DARK)
    assert not any(h in light.lower() for h in only_dark)
    assert not any(h in dark.lower() for h in only_light)


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_css_has_no_js_or_external_resources(mode):
    out = css.build_css(pal.get(mode)).lower()
    for bad in ("<script", "javascript:", "@import", "url(", "http://", "https://", "expression(", "localstorage", "sessionstorage", "cookie"):
        assert bad not in out, bad


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_css_scoped_to_poc_and_streamlit_testids_only(mode):
    """沒有任何會影響到「PoC 以外」的全域選擇器：規則的選擇器要嘛是 :root／body／.stApp（本 PoC 頁自己的 document），要嘛 `poc-`／data-testid／已知 Streamlit class。"""
    out = css.build_css(pal.get(mode))
    body = out.split(">", 1)[1].rsplit("</style>", 1)[0]
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    selectors = [s.strip() for chunk in re.findall(r"([^{}]+)\{", body) for s in chunk.split(",") if s.strip()]
    assert selectors
    allowed = re.compile(r"^(:root|body|\.stApp|h1|h3|h4|\.block-container|\.poc-|\[class\*=\"st-key-poc-card-|\[data-testid=|@media)")
    odd = [s for s in selectors if not allowed.match(s)]
    assert not odd, f"非預期選擇器：{odd}"


# ───────────────────────── 色票對比度（靜態；瀏覽器實測見 contrast 測試） ─────────────────────────

_TEXT_PAIRS = (("text", "page_bg"), ("text", "surface"), ("text2", "page_bg"), ("text2", "surface"), ("disabled_text", "surface"),
               ("sidebar_text", "sidebar_bg"))
_UI_PAIRS = (("primary", "surface"), ("control_border", "surface"), ("focus_ring", "surface"), ("card_border", "page_bg"), ("card_border", "surface"))


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_palette_static_contrast(mode):
    p = pal.get(mode)
    for fg, bg in _TEXT_PAIRS:
        assert cl.ratio(cl.parse_color(p[fg]), cl.parse_color(p[bg])) >= 4.5, (mode, fg, bg)
    for fg, bg in _UI_PAIRS:
        assert cl.ratio(cl.parse_color(p[fg]), cl.parse_color(p[bg])) >= 3.0, (mode, fg, bg)
    for tone, v in p["tones"].items():
        assert cl.ratio(cl.parse_color(v["text"]), cl.parse_color(v["background"])) >= 4.5, (mode, tone, "text")
        assert cl.ratio(cl.parse_color(v["border"]), cl.parse_color(p["surface"])) >= 3.0, (mode, tone, "border")


def test_static_contrast_detects_a_bad_pair():
    """負控（記憶體內現編）：把 text2 換成與底色太近的值，檢查函式要能報。"""
    bad = dict(pal.DARK)
    bad["text2"] = "#2a3350"
    assert cl.ratio(cl.parse_color(bad["text2"]), cl.parse_color(bad["surface"])) < 4.5
