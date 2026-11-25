# -*- coding: utf-8 -*-
"""💼 離線示範頁（A-AST-MOUNT-FAKE-1，客戶方案甲）與 🌍／💼 共用 OneBrain 未啟用槽（MK-1）的守衛。

純邏輯部分不需 streamlit；瀏覽器部分（slow lane）用真 Chromium 量 390／1280。🌍 資料是 `market_stubs` 的合成 fixture，💼 是固定常數封包。
這不是 Cloud／真機驗證（NOT VERIFIED）。
"""
import ast
import pathlib
import re
import sys

import pytest

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_HERE))

import assets_page_support as sup  # noqa: E402

from ui_v3.adapters.assets_demo_envelope import demo_envelope  # noqa: E402
from ui_v3.adapters.assets_page import build_assets_page  # noqa: E402
from ui_v3.pages import assets, chrome, onebrain_slot  # noqa: E402
from ui_v3.shell import registry  # noqa: E402
from ui_v3.viewmodels import preview_wording as W  # noqa: E402

_APPROVED = {  # 客戶核准字樣（#1296 comment 7079420078）逐字
    "ast_demo_nav_marker": "示範頁",
    "ast_demo_banner": "畫面示範｜尚未連接個人持倉資料",
    "ast_demo_limit_note": "此頁僅展示資產頁的版面與資料不足狀態，未讀取個人持股、成本或資產金額。",
    "ast_demo_footer": "PREVIEW · 未連接個人持倉資料",
}


def test_demo_envelope_is_exactly_scenario_three_and_is_a_fresh_dict_each_time():
    assert demo_envelope() == sup.market_blocked_result()
    a, b = demo_envelope(), demo_envelope()
    a["status"] = "changed"
    assert b["status"] == "blocked" and demo_envelope()["status"] == "blocked"   # 呼叫端改動不污染下一次
    assert demo_envelope()["evidence"] is None


def test_demo_envelope_module_has_no_imports_and_no_forbidden_names():
    src = (_ROOT / "ui_v3" / "adapters" / "assets_demo_envelope.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert [i.module if isinstance(i, ast.ImportFrom) else None for i in imports] == ["__future__"]
    assert "assets_source" not in src and "poc/" not in src


def test_rendered_demo_page_shows_no_fake_holdings_amounts_costs_or_personal_settings():
    html = assets.page_html(build_assets_page(demo_envelope()))
    for forbidden in ("成本", "FAKE", "FK0", "TWD", "USD", "%", "data-row", "units_shares", "fund_code"):
        assert forbidden not in html, forbidden
    assert not re.search(r"\d{3,}", re.sub(r"data-[a-z-]+=\"[^\"]*\"|class=\"[^\"]*\"", "", html)), "示範頁不得出現任何數字金額／件數"


def test_demo_wording_is_the_approved_text_verbatim_and_is_pending_not_formal():
    for key, text in _APPROVED.items():
        assert W.text(key) == text
        assert not W.is_approved(key) and "poc/" not in W.PREVIEW_PENDING_WORDING[key].source
    # 示範標示不等於『開發中』『尚未開放』
    assert W.text("ast_demo_nav_marker") not in (W.text("shell_nav_soon"), W.text("shell_nav_not_open"))


def test_registry_marks_only_assets_as_offline_demo_and_rejects_bad_combinations():
    assert [p.slug for p in registry.IA_PAGES if p.data_mode == registry.DATA_MODE_OFFLINE_DEMO] == ["ast"]
    with pytest.raises(ValueError):
        registry.PageSlot("ai", "🤖 AI 投資總結", True, data_mode=registry.DATA_MODE_OFFLINE_DEMO)
    with pytest.raises(ValueError):
        registry.PageSlot("xx", "🧪 未掛載", False, registry.REASON_WIREFRAME_PENDING, data_mode=registry.DATA_MODE_OFFLINE_DEMO)
    with pytest.raises(ValueError):
        registry.PageSlot("xx", "🧪 測試", True, data_mode="live")


def test_demo_marker_is_text_only_not_a_link_not_disabled_and_not_the_soon_label():
    from ui_v3.shell import nav
    item = next(i for i in nav.nav_items() if i.slug == "ast")
    assert item.demo and item.available
    for where in ("side", "top"):
        html = chrome.demo_marker_html(item, where=where)
        assert "示範頁" in html and "aria-disabled" not in html and "<a " not in html and "soon" not in html
    assert "uv3-chip" not in chrome.demo_banner_html() and "uv3-evidence" not in chrome.demo_banner_html()


def test_onebrain_slot_is_static_disabled_note_with_no_interactive_element():
    html = onebrain_slot.onebrain_slot_html()
    assert 'data-block="onebrain-slot"' in html and 'data-state="disabled"' in html and 'role="note"' in html
    assert not re.search(r"<(a|button|input|form)\b", html)
    assert "未啟用" in html


def test_app_preview_ast_renderer_is_isolated_from_data_loaders_and_fixtures():
    src = (_ROOT / "ui_v3" / "app_preview.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "_render_ast")
    body = "\n".join(ast.get_source_segment(src, stmt) for stmt in fn.body[1:])   # 去掉 docstring（說明文字會提到被禁的名稱）
    for forbidden in ("adapter.load", "fixtures", "st.secrets", "os.environ", "session_state", "render_status", "assets_source"):
        assert forbidden not in body, forbidden
    # 橫幅在標題之前
    assert body.index("render_demo_banner") < body.index("assets.render")


# ───────────────────────────── 瀏覽器（slow lane） ─────────────────────────────

pytestmark_slow = pytest.mark.slow


@pytest.fixture(scope="module")
def base_and_browser(tmp_path_factory):
    pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")
    sys.path.insert(0, str(_ROOT / "tests" / "ui_v2"))
    import _ui_v2_chromium
    app_src = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r}); sys.path.insert(0, {str(_HERE)!r})
import market_stubs as ms
from ui_v3.adapters import market_page as adapter
adapter.load = lambda sources: (ms.view(), ms.table())
from ui_v3 import app_preview
app_preview.main()
"""
    app = tmp_path_factory.mktemp("uv3_ast_demo") / "app_ast_demo.py"
    app.write_text(app_src, encoding="utf-8")
    api = _ui_v2_chromium.import_sync_api()
    with _ui_v2_chromium.streamlit_server(app) as base, api.sync_playwright() as p:
        browser = _ui_v2_chromium.launch(p)
        try:
            yield base, browser
        finally:
            browser.close()


_MEASURE = """() => {
  const main = document.querySelector('[data-testid="stMain"]');
  const top = document.querySelector('.st-key-uv3-top-nav');
  const cells = top && getComputedStyle(top).display !== 'none' ? [...top.querySelectorAll('a[data-testid="stPageLink-NavLink"], .uv3-tn-disabled')].map(e => {
      const r = e.getBoundingClientRect(); return {w: r.width, h: r.height, text: (e.innerText || '').replace(/\\s+/g, ' ').trim()}; }) : [];
  const h1 = document.querySelector('h1'); const banner = document.querySelector('[data-shell="demo-banner"]');
  const slots = [...document.querySelectorAll('[data-block="onebrain-slot"]')];
  const touch = [...document.querySelectorAll('main a, main button, [data-testid="stMain"] summary')].filter(e => e.offsetParent && !e.closest('[data-testid="stSidebar"]'))
      .map(e => { const r = e.getBoundingClientRect(); return {t: (e.innerText||'').trim().slice(0, 20), h: r.height}; });
  return {vw: document.documentElement.clientWidth, docScrollW: document.documentElement.scrollWidth, mainScrollW: main.scrollWidth, mainClientW: main.clientWidth,
          title: h1 && h1.innerText, bannerText: banner && banner.innerText, bannerBeforeTitle: !!(banner && h1 && (banner.compareDocumentPosition(h1) & Node.DOCUMENT_POSITION_FOLLOWING)),
          note: (document.querySelector('[data-shell="demo-note"]') || {}).innerText || null, footer: (document.querySelector('[data-shell="footer"]') || {}).innerText || null,
          slots: slots.map(s => ({state: s.dataset.state, text: s.innerText})), statusbar: document.querySelectorAll('.uv3-statusbar').length,
          cells, demoMarkers: [...document.querySelectorAll('[data-nav-demo]')].filter(e => e.offsetParent).map(e => e.innerText.trim()),
          soonOnAst: !!document.querySelector('[data-nav="ast"]'), touch, bodyText: document.body.innerText};
}"""


def _open(browser, base, width, path):
    ctx = browser.new_context(viewport={"width": width, "height": 844}, locale="zh-TW", has_touch=width <= 768)
    page = ctx.new_page()
    reqs = []
    page.on("request", lambda r: reqs.append(r.url))
    page.goto(base + path, wait_until="networkidle")
    return ctx, page, reqs


@pytest.mark.slow
@pytest.mark.parametrize("width", [390, 1280])
def test_demo_page_in_real_browser(base_and_browser, width):
    base, browser = base_and_browser
    ctx, page, reqs = _open(browser, base, width, "/ast")
    try:
        page.wait_for_selector('[data-shell="demo-banner"]', timeout=60000)
        page.wait_for_selector('[data-block="onebrain-slot"]', timeout=60000)
        m = page.evaluate(_MEASURE)
    finally:
        ctx.close()
    assert m["title"] == "💼 我的資產", m["title"]
    assert m["bannerText"] == _APPROVED["ast_demo_banner"] and m["bannerBeforeTitle"], m
    assert m["note"] == _APPROVED["ast_demo_limit_note"] and m["footer"] == _APPROVED["ast_demo_footer"], m
    assert m["slots"] == [{"state": "disabled", "text": m["slots"][0]["text"]}] and "未啟用" in m["slots"][0]["text"], m["slots"]
    assert m["statusbar"] == 0, "💼 示範頁不畫 🌍 的 Status Bar"
    assert m["docScrollW"] <= m["vw"] and m["mainScrollW"] <= m["mainClientW"], ("不得橫向溢出", m)
    assert "成本" not in m["bodyText"].replace(_APPROVED["ast_demo_limit_note"], ""), "除客戶核准的限制說明本身外，頁面不得出現『成本』（情境③沒有成本欄）"
    assert all(t["h"] >= 48 for t in m["touch"]), ("觸控目標 ≥48px", [t for t in m["touch"] if t["h"] < 48])
    assert all(re.match(r"^https?://(127\.0\.0\.1|localhost)", u) or u.startswith(("data:", "blob:")) for u in reqs), ("零外部請求", [u for u in reqs if not u.startswith(("data:", "blob:")) and "127.0.0.1" not in u and "localhost" not in u])
    if width <= 768:
        assert len(m["cells"]) == 5, m["cells"]
        assert all(c["w"] >= 48 and c["h"] >= 48 for c in m["cells"]), m["cells"]
        assert max(c["w"] for c in m["cells"]) - min(c["w"] for c in m["cells"]) <= 1.0, ("五格等寬", m["cells"])
        assert m["demoMarkers"] == ["示範頁"], m["demoMarkers"]
    else:
        assert m["demoMarkers"] == ["示範頁"], m["demoMarkers"]


@pytest.mark.slow
@pytest.mark.parametrize("width", [390, 1280])
def test_market_page_has_exactly_one_disabled_onebrain_slot_and_stays_operable(base_and_browser, width):
    base, browser = base_and_browser
    ctx, page, _ = _open(browser, base, width, "/")
    try:
        page.wait_for_selector('[data-block="onebrain-slot"]', timeout=60000)
        m = page.evaluate(_MEASURE)
        page.locator('[data-testid="stRadio"] label').nth(1).click()   # 頁面控制項在 AI 未啟用下照常可操作
        page.wait_for_timeout(500)
        after = page.evaluate(_MEASURE)
    finally:
        ctx.close()
    assert len(m["slots"]) == 1 and m["slots"][0]["state"] == "disabled" and "未啟用" in m["slots"][0]["text"], m["slots"]
    assert len(after["slots"]) == 1 and after["docScrollW"] <= after["vw"]
    assert m["demoMarkers"] == ["示範頁"] or m["demoMarkers"] == [], m["demoMarkers"]
