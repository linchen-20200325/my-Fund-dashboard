# -*- coding: utf-8 -*-
"""🌍 市場頁**本體**的瀏覽器級回歸守衛（slow lane；需要 streamlit 與 Chromium；客戶核准 G8／V4，`DEC-2026-11-10-06`）。

與同目錄 `test_ui_v3_top_nav_browser.py` 的分工：那一檔只量 Shell（頁首五格）；本檔量**頁本體**在真瀏覽器的版面事實。
AppTest 不載入 CSS，DOM 級守衛量不到「橫向溢出」「圖是否真的可見、有沒有尺寸、有沒有被蓋住」，這一檔補這一層。

資料：`market_stubs` 的**合成 fixture**（人造數值，不是市場資料；不連 FRED／Yahoo／任何外部來源）。情境用 query string 切換：
`normal`、`tw_missing`（台股缺）、`both_missing`（兩條都缺）、`us_failed`（S&P 取數失敗，原文帶假 token 用來驗不外漏）。

**斷言什麼（條件出處：`docs/evidence/fund_newui2_market_visual_acceptance_plan_2026_11_10.md` §1 MV 表）**
- 390／768／1280 整頁與頁本體元素無橫向溢出（MV-08、§6）。
- 主圖：存在、可見（非 display:none／visibility:hidden）、非零尺寸、水平在視窗內、長寬比維持 viewBox 360:240、
  在摘要之後與第一張 Secondary 卡之前、中心點沒被別的元素蓋住（MV-05、MV-09 只斷言「存在、可見、非零尺寸」）。
- **G5 客戶暫時接受現況**：首屏主圖露出量（390px 約 157／239px）**不設門檻，只記錄**（`record_property` 與 `-s` 的 print），絕不斷言。
- 頁首五格 S1（`DEC-2026-11-06-01`／`-07-02`）：≤768 五格全可見、等寬、不重疊、不橫滑、各格 ≥48px 高；≥769 側欄在、頁首隱藏。
- 已核准排版：區塊順序（MV-02）、首屏 chip＋核心數字 ≤5（MV-03）、缺資料恆 `⬜`／`◇ 資料未備`、Missing 不畫零不畫空座標軸、
  取數失敗原文不外漏（MV-04、MV-07）。

**穩定性**：不寫像素精確值。容差都有理由：長寬比 ±0.03（SVG `preserveAspectRatio` 縮放為浮點）、水平邊界 ±0.5px（次像素取整）、
五格等寬 ±1px（沿用頁首守衛）。順序用 DOM 順序（`compareDocumentPosition`），不用 y 座標（768／1280 兩欄並排時 y 會相等）。

**變異驗證（負控）**：本檔後半 `test_mutation_*` 在**測試內**對已載入的頁面注入 CSS／DOM（橫溢、隱藏圖、零尺寸圖、遮蓋圖、縮小頁首格、
改順序、加爆 chip、缺資料畫零），斷言上面同一組判定函式**真的會報**；不改任何 production 程式。負控全在記憶體內現編。
"""

import pathlib
import sys

import pytest

pytestmark = pytest.mark.slow

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT / "tests" / "ui_v2"))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

import _ui_v2_chromium  # noqa: E402  瀏覽器解析（CI 找不到要 fail）

_APP = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r}); sys.path.insert(0, {str(_HERE)!r})
import streamlit as st
import market_stubs as ms
from ui_v3.adapters import market_page as adapter
_SCENARIOS = {{"normal": {{}}, "tw_missing": dict(tw="missing"), "both_missing": dict(tw="missing", us="missing"),
              "us_failed": dict(us="error")}}
_view, _table = ms.view(**_SCENARIOS[st.query_params.get("scenario", "normal")]), ms.table()
adapter.load = lambda sources: (_view, _table)
from ui_v3 import app_preview
app_preview.main()
"""

_MEASURE = r"""
() => {
  const vis = e => { if (!e) return false; const s = getComputedStyle(e); return e.getClientRects().length > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const main = document.querySelector('[data-testid="stMain"]');
  const vw = document.documentElement.clientWidth, vh = window.innerHeight;
  const rect = e => { const b = e.getBoundingClientRect(); return {x: b.x, y: b.y, r: b.right, b: b.bottom, w: b.width, h: b.height}; };
  const out = {vw, vh, docScrollW: document.documentElement.scrollWidth, mainScrollW: main.scrollWidth, mainClientW: main.clientWidth};
  // 頁本體元素水平邊界
  out.bodyBoxes = [...main.querySelectorAll('.uv3-card, svg.uv3-chart, .uv3-row, .uv3-note, h1, h3, [data-testid="stRadio"], [data-testid="stExpander"]')]
    .filter(vis).map(e => ({t: e.tagName + (e.dataset.card ? '#' + e.dataset.card : ''), ...rect(e)}));
  // 主圖
  const svg = main.querySelector('svg.uv3-chart');
  if (svg) {
    const s = getComputedStyle(svg), b = svg.getBoundingClientRect();
    out.chart = {exists: true, display: s.display, visibility: s.visibility, opacity: s.opacity, visibleBox: vis(svg), ...rect(svg),
                 absTop: b.top + window.scrollY, series: svg.querySelectorAll('path').length,
                 foldPx: Math.max(0, Math.min(vh, b.bottom) - Math.max(0, b.top))};
  } else out.chart = {exists: false};
  // 區塊順序（DOM 順序）
  const q = (sel) => main.querySelector(sel);
  const exp = main.querySelectorAll('[data-testid="stExpander"]');
  const marks = {h1: q('h1'), market_state: q('[data-field="market_state"]'), attention: q('[data-field="attention"]'),
    evidence_row: (q('.uv3-evidence') || {closest: () => null}).closest('.uv3-row'),
    freshness: (q('[data-status-key="threshold_pending"]') || {closest: () => null}).closest('.uv3-row'),
    primary: q('h3'), chart: svg, source_limits: exp[0], vix: q('.uv3-card[data-card="vix"]'), rates: q('.uv3-card[data-card$="_pct"]'),
    'MKT-1': q('.uv3-card[data-card="MKT-1"]'), 'MKT-2': q('.uv3-card[data-card="MKT-2"]'), 'MKT-3': q('.uv3-card[data-card="MKT-3"]'),
    missing_group: exp[1], status_group: exp[2]};
  const present = Object.entries(marks).filter(([, e]) => e);
  present.sort((a, b) => (a[1].compareDocumentPosition(b[1]) & Node.DOCUMENT_POSITION_FOLLOWING) ? -1 : 1);
  out.order = present.map(([k]) => k);
  out.secondaryCount = main.querySelectorAll('.uv3-card[data-card="vix"], .uv3-card[data-card$="_pct"]').length;
  // 圖相對位置（圖在摘要之後、第一張 Secondary 卡之前）
  const fresh = marks.freshness, vix = marks.vix;
  out.summaryBottom = fresh ? fresh.getBoundingClientRect().bottom : null;
  out.vixTop = vix ? vix.getBoundingClientRect().top : null;
  // 首屏名額：第一張 data-card 之前、可見、不在摺疊區的 chip；格內有 chip 的 evidence 只算一格
  const firstCard = q('.uv3-card[data-card]');
  const scope = [...document.querySelectorAll('.uv3-chip, .uv3-evidence')].filter(e => vis(e) && !e.closest('[data-testid="stExpander"]')
      && !(e.classList.contains('uv3-chip') && e.closest('.uv3-evidence'))
      && (!firstCard || (e.compareDocumentPosition(firstCard) & Node.DOCUMENT_POSITION_FOLLOWING)));
  out.firstScreenBudget = scope.length;
  out.statusbarChips = document.querySelectorAll('.uv3-statusbar .uv3-chip').length;
  out.sidebarChips = document.querySelectorAll('[data-testid="stSidebar"] .uv3-chip').length;
  out.mainText = main.innerText;
  out.chipTexts = [...main.querySelectorAll('.uv3-chip')].filter(e => vis(e) && !e.closest('[data-testid="stExpander"]')).map(e => e.innerText.trim());
  // 頁首五格（S1）
  const nav = document.querySelector('.st-key-uv3-top-nav'), side = document.querySelector('[data-testid="stSidebar"]');
  out.navDisplay = nav ? getComputedStyle(nav).display : null;
  out.sidebarDisplay = side ? getComputedStyle(side).display : null;
  if (nav) {
    out.navScrollW = nav.scrollWidth; out.navClientW = nav.clientWidth;
    out.cells = [...nav.querySelectorAll('a[data-testid="stPageLink-NavLink"], .uv3-tn-disabled')].map(e => ({text: e.innerText.replace(/\s+/g, ' ').trim(), ...rect(e)}));
  }
  return out;
}
"""

_HIT = r"""
() => {   // 把主圖捲到視窗中央再取中心點命中的元素：圖不可被別的元素蓋住
  const svg = document.querySelector('[data-testid="stMain"] svg.uv3-chart');
  if (!svg) return null;
  svg.scrollIntoView({block: 'center'});
  const b = svg.getBoundingClientRect();
  const hit = document.elementFromPoint(b.x + b.width / 2, b.y + b.height / 2);
  return {covered: !!hit && !svg.contains(hit) && hit !== svg, hit: hit ? hit.tagName + '.' + String(hit.className.baseVal ?? hit.className).slice(0, 40) : null};
}
"""

_NAMES = ["市場", "資產", "找基金", "AI", "設定"]
_SCENARIOS = ("normal", "tw_missing", "both_missing", "us_failed")
_WIDTHS = (390, 768, 1280)
_BAD_TOKENS = ("NaN", "nan", "None", "null", "undefined", "Infinity")


# ───────────────────────── 判定函式（正向測試與變異驗證共用同一組） ─────────────────────────

def overflow_violations(m):
    bad = []
    if m["docScrollW"] > m["vw"]:
        bad.append(("整頁橫向溢出", m["docScrollW"], m["vw"]))
    if m["mainScrollW"] > m["mainClientW"]:
        bad.append(("主內容橫向溢出", m["mainScrollW"], m["mainClientW"]))
    bad += [("元素超出視窗水平邊界", b["t"], round(b["x"], 1), round(b["r"], 1)) for b in m["bodyBoxes"]
            if b["x"] < -0.5 or b["r"] > m["vw"] + 0.5]
    return bad


def chart_violations(m):
    c = m["chart"]
    if not c["exists"]:
        return [("主圖不存在",)]
    bad = []
    if c["display"] == "none" or c["visibility"] == "hidden" or float(c["opacity"]) == 0 or not c["visibleBox"]:
        bad.append(("主圖不可見", c["display"], c["visibility"], c["opacity"]))
    if c["w"] <= 0 or c["h"] <= 0:
        bad.append(("主圖零尺寸", c["w"], c["h"]))
        return bad
    # 寬 ≥280：viewBox 360 寬、刻度字 11px，窄於 280 字會縮到 <8.6px 難讀；390 視窗實測約 358
    if c["w"] < 280:
        bad.append(("主圖過窄", c["w"]))
    # 長寬比維持 viewBox 360:240（=0.667）；±0.03 容次像素取整
    if abs(c["h"] / c["w"] - 240 / 360) > 0.03:
        bad.append(("主圖長寬比跑掉", round(c["h"] / c["w"], 3)))
    if c["x"] < -0.5 or c["r"] > m["vw"] + 0.5:
        bad.append(("主圖超出視窗水平邊界", c["x"], c["r"]))
    if m["summaryBottom"] is not None and c["y"] < m["summaryBottom"] - 0.5:
        bad.append(("主圖在首屏摘要之上", c["y"], m["summaryBottom"]))
    if m["vixTop"] is not None and c["b"] > m["vixTop"] + 0.5:
        bad.append(("主圖壓到第一張 Secondary 卡", c["b"], m["vixTop"]))
    return bad


def nav_violations(m, width):
    if width >= 769:
        bad = []
        if m["navDisplay"] != "none" or m["sidebarDisplay"] != "block":
            bad.append(("≥769 應為側欄、頁首隱藏", m["navDisplay"], m["sidebarDisplay"]))
        return bad
    bad = []
    if m["navDisplay"] != "flex" or m["sidebarDisplay"] != "none":
        bad.append(("≤768 應為頁首、側欄隱藏", m["navDisplay"], m["sidebarDisplay"]))
    cells = m.get("cells") or []
    if len(cells) != 5:
        return bad + [("頁首格數不是 5", len(cells))]
    for cell, name in zip(cells, _NAMES):
        if name not in cell["text"]:
            bad.append(("格名不符", name, cell["text"]))
        if cell["x"] < -0.5 or cell["r"] > m["vw"] + 0.5:
            bad.append(("頁首格不在視窗內", name))
        if cell["w"] < 48 or cell["h"] < 48:
            bad.append(("觸控目標 <48px", name, round(cell["w"], 1), round(cell["h"], 1)))
    widths = [c["w"] for c in cells]
    if max(widths) - min(widths) > 1.0:
        bad.append(("五格不等寬", widths))
    if any(cells[i]["r"] > cells[i + 1]["x"] + 0.5 for i in range(4)):
        bad.append(("五格重疊",))
    if m["navScrollW"] > m["navClientW"]:
        bad.append(("頁首可橫向捲動", m["navScrollW"], m["navClientW"]))
    return bad


_FULL_ORDER = ["h1", "market_state", "attention", "evidence_row", "freshness", "primary", "chart", "source_limits", "vix", "rates",
               "MKT-1", "MKT-2", "MKT-3", "missing_group", "status_group"]


def order_violations(m):
    expected = [k for k in _FULL_ORDER if k in m["order"]]
    bad = [] if m["order"] == expected else [("區塊順序不符 MV-02", m["order"])]
    for must in ("h1", "market_state", "attention", "freshness", "primary", "vix", "rates", "MKT-1", "MKT-2", "MKT-3",
                 "missing_group", "status_group"):
        if must not in m["order"]:
            bad.append(("缺區塊", must))
    if m["secondaryCount"] > 3:
        bad.append(("Secondary 超過 3 張", m["secondaryCount"]))
    return bad


def budget_violations(m):
    bad = []
    if m["firstScreenBudget"] > 5:
        bad.append(("首屏 chip＋核心數字超過 5", m["firstScreenBudget"]))
    if m["statusbarChips"] or m["sidebarChips"]:
        bad.append(("Status Bar／側欄不得放 chip", m["statusbarChips"], m["sidebarChips"]))
    return bad


def missing_violations(m, scenario):
    """缺資料恆 `⬜`／`◇ 資料未備` 文字；Missing 不畫零、不畫空座標軸；失敗原文不外漏。"""
    text, bad = m["mainText"], []
    bad += [("畫面出現不可呈現的 token", t) for t in _BAD_TOKENS if t in text]
    bad += [("取數失敗原文外漏", t) for t in ("429", "secret-token", "HTTP") if t in text]
    if "⬜ 無法判定" not in text or "⬜ 門檻待裁示" not in text:
        bad.append(("首屏 ⬜ 字樣缺",))
    if "◇ 資料未備" not in text:      # MKT-2 領先／同時指標在 stub 恆缺 → 任何情境都應有
        bad.append(("缺值沒有 ◇ 資料未備 字樣",))
    series = m["chart"].get("series", 0) if m["chart"]["exists"] else 0
    expected_series = {"normal": 2, "tw_missing": 1, "us_failed": 1, "both_missing": 0}[scenario]
    if series != expected_series:
        bad.append(("主圖序列數不符（缺資料不補、不畫零）", series, expected_series))
    if scenario == "both_missing" and m["chart"]["exists"]:
        bad.append(("兩條皆缺不得畫空座標軸",))
    if scenario in ("tw_missing", "both_missing"):
        import re
        row = text.split("重要依據", 1)[-1].split("資料新鮮度", 1)[0]
        if "台股" in row and not re.search(r"台股\s*◇ 資料未備", row):
            bad.append(("台股缺值沒有以 ◇ 資料未備 呈現", row.strip()[:60]))
        if re.search(r"台股[^|｜S]*[+-]?0(\.0+)?\s*%", row):
            bad.append(("台股缺值被畫成 0%", row.strip()[:60]))
    return bad


# ───────────────────────── fixtures ─────────────────────────

@pytest.fixture(scope="module")
def base_and_browser(tmp_path_factory):
    api = _ui_v2_chromium.import_sync_api()
    app = tmp_path_factory.mktemp("uv3_market_page") / "app_market_page.py"
    app.write_text(_APP, encoding="utf-8")
    with _ui_v2_chromium.streamlit_server(app) as base, api.sync_playwright() as p:
        browser = _ui_v2_chromium.launch(p)
        try:
            yield base, browser, {}
        finally:
            browser.close()


def _open(browser, base, scenario, width):
    ctx = browser.new_context(viewport={"width": width, "height": 844 if width <= 768 else 800}, locale="zh-TW", has_touch=width <= 768)
    page = ctx.new_page()
    page.goto(f"{base}/?scenario={scenario}", wait_until="networkidle")
    page.wait_for_selector('[data-field="market_state"]', timeout=60000)
    page.wait_for_timeout(1500)
    return ctx, page


@pytest.fixture
def measure(base_and_browser):
    """(scenario, width) → 量測結果；同一組只開一次頁面（各測試共用）。"""
    base, browser, cache = base_and_browser

    def run(scenario, width):
        key = (scenario, width)
        if key not in cache:
            ctx, page = _open(browser, base, scenario, width)
            try:
                m = page.evaluate(_MEASURE)
                m["hit"] = page.evaluate(_HIT)
            finally:
                ctx.close()
            cache[key] = m
        return cache[key]
    return run


# ───────────────────────── 正向守衛 ─────────────────────────

@pytest.mark.parametrize("scenario", _SCENARIOS)
@pytest.mark.parametrize("width", _WIDTHS)
def test_no_horizontal_overflow(measure, scenario, width):
    assert not overflow_violations(measure(scenario, width))


@pytest.mark.parametrize("width", _WIDTHS)
def test_primary_chart_present_visible_nonzero_and_in_place(measure, width, record_property):
    m = measure("normal", width)
    assert not chart_violations(m), (chart_violations(m), m["chart"])
    assert m["hit"] is not None and not m["hit"]["covered"], ("主圖中心點被別的元素蓋住", m["hit"])
    # G5：首屏露出量只記錄、不斷言（客戶暫時接受現況；390px 實測約 157／239px）
    info = f"w{width}: chart top y={m['chart']['y']:.0f}, foldPx={m['chart']['foldPx']:.0f}/{m['chart']['h']:.0f} (viewport h={m['vh']}) — INFO ONLY, 無門檻"
    record_property(f"chart_fold_w{width}", info)
    print("\n[G5 info]", info)


@pytest.mark.parametrize("width", _WIDTHS)
def test_top_nav_s1_five_cells_mobile_and_sidebar_desktop(measure, width):
    m = measure("normal", width)
    assert not nav_violations(m, width), nav_violations(m, width)


@pytest.mark.parametrize("scenario", _SCENARIOS)
@pytest.mark.parametrize("width", _WIDTHS)
def test_block_order_and_first_screen_budget(measure, scenario, width):
    m = measure(scenario, width)
    assert not order_violations(m), order_violations(m)
    assert not budget_violations(m), budget_violations(m)


@pytest.mark.parametrize("scenario", _SCENARIOS)
@pytest.mark.parametrize("width", (390, 1280))
def test_missing_data_wording_no_zero_no_leak(measure, scenario, width):
    m = measure(scenario, width)
    assert not missing_violations(m, scenario), (missing_violations(m, scenario), m["chipTexts"])


# ───────────────────────── 變異驗證（負控；只在測試內對頁面注入，不改 production） ─────────────────────────

def _mutated(base_and_browser, scenario, width, *, css=None, js=None):
    base, browser, _ = base_and_browser
    ctx, page = _open(browser, base, scenario, width)
    try:
        if css:
            page.add_style_tag(content=css)
        if js:
            page.evaluate(js)
        page.wait_for_timeout(300)
        m = page.evaluate(_MEASURE)
        m["hit"] = page.evaluate(_HIT)
        return m
    finally:
        ctx.close()


def test_mutation_forced_wide_card_is_flagged_as_overflow(base_and_browser):
    m = _mutated(base_and_browser, "normal", 390, css=".uv3-card{min-width:900px !important}")
    assert overflow_violations(m)


def test_mutation_hidden_chart_is_flagged(base_and_browser):
    m = _mutated(base_and_browser, "normal", 390, css="svg.uv3-chart{display:none !important}")
    assert chart_violations(m)


def test_mutation_zero_size_chart_is_flagged(base_and_browser):
    m = _mutated(base_and_browser, "normal", 390, css="svg.uv3-chart{width:0 !important;height:0 !important}")
    assert any("零尺寸" in v[0] or "不可見" in v[0] for v in chart_violations(m))


def test_mutation_missing_chart_dom_is_flagged(base_and_browser):
    m = _mutated(base_and_browser, "normal", 390, js="document.querySelector('svg.uv3-chart').remove()")
    assert chart_violations(m) == [("主圖不存在",)]


def test_mutation_overlay_covering_chart_is_flagged(base_and_browser):
    js = """() => { const d = document.createElement('div'); d.style.cssText = 'position:fixed;inset:0;z-index:99999;background:#fff';
      document.body.appendChild(d); }"""
    m = _mutated(base_and_browser, "normal", 390, js=js)
    assert m["hit"]["covered"] is True


def test_mutation_shrunk_top_nav_cells_are_flagged(base_and_browser):
    m = _mutated(base_and_browser, "normal", 390,
                 css=".st-key-uv3-top-nav a[data-testid='stPageLink-NavLink'],.st-key-uv3-top-nav .uv3-tn-disabled{max-height:30px !important;min-height:0 !important}")
    assert any("<48px" in v[0] for v in nav_violations(m, 390))


def test_mutation_unequal_five_cells_nav_is_flagged(base_and_browser):
    m = _mutated(base_and_browser, "normal", 390, css=".st-key-uv3-top-nav > div:first-child{flex:3 1 0 !important}")
    assert any("不等寬" in v[0] for v in nav_violations(m, 390)), nav_violations(m, 390)


def test_mutation_reordered_blocks_are_flagged(base_and_browser):
    js = """() => { const box = e => e.closest('[data-testid="stElementContainer"]') || e;
      const vix = document.querySelector('.uv3-card[data-card="vix"]'), h3 = document.querySelector('[data-testid="stMain"] h3');
      box(h3).before(box(vix)); }"""
    m = _mutated(base_and_browser, "normal", 390, js=js)
    assert any("區塊順序" in v[0] for v in order_violations(m))


def test_mutation_extra_chips_blow_first_screen_budget(base_and_browser):
    js = """() => { const row = document.querySelector('[data-field="attention"]');
      for (let i = 0; i < 4; i++) { const s = document.createElement('span'); s.className = 'uv3-chip'; s.textContent = '⬜ 假chip'; row.appendChild(s); } }"""
    m = _mutated(base_and_browser, "normal", 390, js=js)
    assert any("超過 5" in v[0] for v in budget_violations(m))


def test_mutation_missing_series_drawn_as_zero_or_extra_path_is_flagged(base_and_browser):
    js = """() => { const svg = document.querySelector('svg.uv3-chart'); svg.appendChild(svg.querySelector('path').cloneNode(true));
      const row = document.querySelector('[data-testid="stMain"]').innerText; document.querySelectorAll('.uv3-evidence').forEach(e => {
        if (e.innerText.includes('資料未備')) e.textContent = '台股 近1Y 0.00%'; }); }"""
    m = _mutated(base_and_browser, "tw_missing", 390, js=js)
    msgs = [v[0] for v in missing_violations(m, "tw_missing")]
    assert any("序列數" in s for s in msgs)
    assert any("0%" in s or "沒有以" in s for s in msgs)


def test_mutation_leaked_failure_text_and_nan_are_flagged(base_and_browser):
    js = """() => { const n = document.createElement('div'); n.className = 'uv3-row'; n.textContent = 'HTTP 429 secret-token-abc123 NaN';
      document.querySelector('[data-testid="stMain"] h1').after(n); }"""
    m = _mutated(base_and_browser, "us_failed", 390, js=js)
    msgs = [v[0] for v in missing_violations(m, "us_failed")]
    assert "取數失敗原文外漏" in msgs and "畫面出現不可呈現的 token" in msgs
