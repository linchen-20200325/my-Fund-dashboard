# -*- coding: utf-8 -*-
"""五頁正式模式 390 寬瀏覽器煙霧測試（Phase 2 批 3 G4；slow lane；需要 streamlit 與 Chromium）。

每一頁以**正式模式**（`page.render(load_live=...)`）起一個 streamlit 子行程，CSS viewport 寬 390、高 844，驗：

1. 頁面渲染無例外（`[data-testid=stException]` 為 0）。
2. **整頁不得水平捲動** —— 同時量三個地方：
   - `document.documentElement`（派工指定的那一個）；
   - `[data-testid=stMain]`：Streamlit 的頁面捲動容器其實是它，不是 `html`。內容把頁面推寬時，
     `documentElement.scrollWidth` 仍等於 `clientWidth`（實測：市場總覽三張核心卡變成程式碼區塊、
     `stMain` 捲到 5878 寬時，`documentElement` 量到的是 390／390），只量 `html` 會漏掉；
   - 逐一列出右緣超出視窗的元素（排除範圍見下）。
   先量預設（收合）狀態，再把每一個 `<details>` 展開後量一次。
3. Data Health 燈（各頁 `*-0`）存在，且在首屏可見：預設狀態下 bounding box 頂端 ≥ 0、＜ 視窗高度、高度 ＞ 0。
4. 沒有 HTML 被 Markdown 印成程式碼區塊（`[data-testid=stCode]` 為 0），1400 寬下 `stMain` 不橫捲 —— 正式模式五頁之外，
   示範模式五頁也各跑一個情境（2026-10-16 市場總覽核心卡原始碼外露那個病的專屬守衛）。

**排除範圍與理由（只排這些，不是排除「所有會捲的東西」）**：
- 各頁自己設計的容器內橫捲外框 `.mkt-scroll`／`.hld-scroll`／`.exp-scroll`（`overflow-x: auto`）裡的元素。
  理由：`44` 2.1 的硬規則是「不把整頁推寬」；這三個外框把寬表關在容器內捲動，`stMain` 不會因此變寬。
- 但**預設就看得到**（不在 `<details>` 裡）的容器內橫捲，只准出現在 `_DEFAULT_VISIBLE_INNER_SCROLL` 登記的那幾塊。
  理由：交接驗收要看「核心區不靠水平捲動」，預設可見的寬表是否屬核心區要客戶看線框判斷，本檔不替客戶決定；
  新出現一塊就轉紅，逼下一個人登記並回報。

替身：mkt／alo／hld 以各頁 `fixtures` 的資料當 `load_live` 的回傳（示範資料、正式路徑）；exp 用
`_exp_live_stub`（C2 接線結果）；set 走真 L2 ＋ 真 L1 ＋ 假 gspread（同 `test_set_live_page.py` 的 `real`）。
不打任何網路。不改任何程式；發現真的問題時標 `xfail(strict=True)` 並寫原因 —— 修版面要客戶線框。
"""

import pathlib
import sys

import pytest

# 整檔標 slow：畫面測試不進 fast lane（守衛：tests/ui_v2/test_ui_v2_lane_guards.py）。
pytestmark = pytest.mark.slow

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
_TESTS = _ROOT / "tests"
sys.path.insert(0, str(_HERE))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

import _ui_v2_chromium  # noqa: E402  瀏覽器解析（CI 找不到要 fail）

_VIEWPORT = {"width": 390, "height": 844}

_HEAD = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
sys.path.insert(0, {str(_HERE)!r})
sys.path.insert(0, {str(_TESTS)!r})
"""

_SCRIPTS = {
    "mkt": _HEAD + """
from ui_v2.mkt import fixtures, page
_dataset = fixtures.dataset_all_ok()
_notes = {"pending": {"leading_index": "ndc_no_release_date", "coincident_index": "ndc_no_release_date",
                      "fx_twd_per_usd": "fx_obs_date_rule"},
          "masked_keys": [], "cooldowns": []}
page.render(load_live=lambda: {"dataset": _dataset, "notes": _notes})
""",
    "hld": _HEAD + """
import datetime
from ui_v2.hld import fixtures, logic, page

def _scrub(node):
    if isinstance(node, str):
        return node.replace(logic.HINT, "")
    if isinstance(node, dict):
        return {k: _scrub(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_scrub(v) for v in node]
    return node

_dataset = _scrub(fixtures.scenario("full")["dataset"])
for _h in _dataset["holding"]:
    if _h["policy_id"] == "DIRECT":       # 正式路徑要求 L2 已排除 DIRECT 列（同 test_hld_live_page._render_app）
        _h["policy_id"] = "P-001"
_live_args = {"direct_policy_id": "DIRECT", "today": datetime.date(2026, 9, 28),
              "nav_provenance": {r["fund_code"]: {"cache_fallback": False, "stale": None} for r in _dataset["nav"]}}
page.render(load_live=lambda: {"dataset": _dataset, "live_args": _live_args}, mask_error=str,
            save_live=lambda *_a: {"status": "saved"})
""",
    "exp": _HEAD + """
import json
import _exp_live_stub as STUB
from ui_v2.exp import logic, page
STUB.reset()
STUB.WIRED.append(True)
STUB.STORE["exp_filter_rules"] = json.dumps([{"field": "fund_code", "op": "不等於", "value": "ZZZ"}], ensure_ascii=False)
STUB.STORE["exp_visible_columns"] = json.dumps(list(logic.COLUMN_ORDER))
page.render(load_live=STUB.load_live, save_live=STUB.save_setting)
""",
    "alo": _HEAD + """
from ui_v2.alo import fixtures, page
_dataset = fixtures.scenario("full")
page.render(load_live=lambda: {"dataset": _dataset, "notes": {}})
""",
    "set": _HEAD + """
import types
from _fake_settings_sheet import FakeClient, FakeSpreadsheet
from infra import gspread_retry as GR
from repositories import settings_sheet_repository as R
from ui_v2.set import page, source

class _Book(FakeSpreadsheet):
    title = "測試用設定本"

_book = _Book()
_cfg = {"SETTINGS_SHEET_ID": "sheet-for-390-smoke",
        "google_service_account": {"client_email": "sa@example.iam.gserviceaccount.com"}}
R.get_secret = lambda key, default=None: _cfg.get(key, default)
R._make_client = lambda creds: FakeClient(_book)
R._TITLES = {}
GR.time = types.SimpleNamespace(sleep=lambda _s: None)
source.st = types.SimpleNamespace(secrets=_cfg, session_state={})
source.market_indicator.source_cooldowns = lambda: []
page.render(load_live=source.load_live, save_live=source.save_setting, refetch_live=source.refetch)
""",
}

# BL-0250 批次 3-D（新設計 B；客戶 2026-10-21 Q4：390px 實測、截圖、量測，只修畫面缺陷）：上面那五個情境資料都齊，
# 從來沒有跑過「尚未設定」「取數失敗」—— 卡片安靜收起只在那兩種情境出現。補上五頁各兩種（腳本同一般畫面掃描那一份，
# `tests/ui_v2/_plain_scan.py`；替身、不打網路），鍵寫成「頁/情境」，量法與上面五個一字不差。
import _plain_scan as _SCAN  # noqa: E402

for _page in ("mkt", "hld", "exp", "alo", "set"):
    for _scenario in ("未設定", "取數失敗"):
        _SCRIPTS[f"{_page}/{_scenario}"] = _SCAN.SCRIPTS[_page][_scenario]

# 各頁 Data Health 燈（`*-0`）的外框 class：`ui_v2/<頁>/page.py` 的 `_render_light`／`_render_lamp`／`_render_*0`。
_LAMP = {"mkt": ".mkt-light", "hld": ".hld-lamp", "exp": ".exp-lamp", "alo": ".alo-lamp", "set": ".set-lamp"}

# 設計上的容器內橫捲外框（`overflow-x: auto`）；裡面的元素不算「把整頁推寬」。
_INNER_SCROLL = ".mkt-scroll, .hld-scroll, .exp-scroll"

# 預設可見（不在 `<details>` 裡）、390 寬會在容器內橫捲的塊 —— 2026-10-16 實測登記。
# exp：EXP-2 候選表（7 欄，容器 358 寬、內容 674 寬）。客戶 2026-10-16 先接受，Phase 3 實機再定（裁示第 10 點）。
_DEFAULT_VISIBLE_INNER_SCROLL = {"mkt": set(), "hld": set(), "exp": {"EXP-2"}, "alo": set(), "set": set()}


def _slug(name: str) -> str:
    """「頁/情境」→ 頁（3-D 補的情境沿用該頁的燈與登記）。"""
    return name.split("/", 1)[0]

_PAGES = tuple(_SCRIPTS)

_MEASURE_JS = """([lampSel, innerSel]) => {
  const vw = window.innerWidth, vh = window.innerHeight;
  const de = document.documentElement;
  const main = document.querySelector('[data-testid=stMain]');
  const offenders = [];
  for (const el of (main || document.body).querySelectorAll('*')) {
    const box = el.getBoundingClientRect();
    if (box.width === 0 || box.height === 0 || box.right <= vw + 1) continue;
    if (el.closest(innerSel)) continue;
    offenders.push([el.tagName, (el.getAttribute('data-testid') || String(el.className)).slice(0, 40),
                    Math.round(box.right), el.textContent.trim().slice(0, 60)]);
  }
  // 預設可見的容器內橫捲：記下它前面最近的一個塊代號。
  // ~~讀 `*-card-code`／`*-code` 的文字~~ → Phase 3 P0-①（有意識的更正，不是漏刪）：正式模式畫面上不再印塊代號，
  // 改讀卡片／燈外框的 `data-block` 屬性（畫面不可見）；示範模式沒有這個屬性，照舊讀代號文字。
  const codes = [...document.querySelectorAll('[data-block], [class$="-card-code"], [class$="-code"]')];
  const innerScroll = [];
  for (const box of document.querySelectorAll(innerSel)) {
    if (box.scrollWidth <= box.clientWidth + 1 || box.closest('details')) continue;
    let code = null;
    for (const c of codes) {
      if (c.compareDocumentPosition(box) & Node.DOCUMENT_POSITION_FOLLOWING) {
        code = c.getAttribute('data-block') || c.textContent.trim().split(/\\s/)[0];
      }
    }
    innerScroll.push(code);
  }
  const lamp = document.querySelector(lampSel);
  const lampBox = lamp ? lamp.getBoundingClientRect() : null;
  return {
    vw, vh,
    doc: [de.scrollWidth, de.clientWidth],
    main: main ? [main.scrollWidth, main.clientWidth] : null,
    offenders: offenders.slice(0, 12), offenderCount: offenders.length,
    innerScroll,
    lamp: lampBox ? [lampBox.top, lampBox.bottom, lampBox.height] : null,
    exceptions: [...document.querySelectorAll('[data-testid=stException]')].map(e => e.innerText.slice(0, 300)),
    codeBlocks: [...document.querySelectorAll('[data-testid=stCode]')].map(e => e.innerText.slice(0, 120)),
  };
}"""


@pytest.fixture(scope="module")
def browser():
    api = _ui_v2_chromium.import_sync_api()
    with api.sync_playwright() as p:
        instance = _ui_v2_chromium.launch(p)  # 先確認瀏覽器在，再起 streamlit
        try:
            yield instance
        finally:
            instance.close()


@pytest.fixture(scope="module", params=_PAGES)
def live_page(request, browser, tmp_path_factory):
    """每一頁起一次 streamlit（同一頁的各條測試共用），回傳 (頁名, browser, base URL)。"""
    name = request.param
    safe = name.replace("/", "_")   # 「頁/情境」不能直接當檔名
    app = tmp_path_factory.mktemp(f"live390_{safe}") / f"app_{safe}_live390.py"
    app.write_text(_SCRIPTS[name], encoding="utf-8")
    with _ui_v2_chromium.streamlit_server(app) as base:
        yield name, browser, base


def _open(browser, base, name):
    tab = browser.new_page(viewport=_VIEWPORT)
    tab.goto(base + "/", wait_until="networkidle")
    tab.wait_for_selector(_LAMP[_slug(name)], timeout=60000)
    tab.wait_for_timeout(1500)
    return tab


def _measure(tab, name):
    return tab.evaluate(_MEASURE_JS, [_LAMP[_slug(name)], _INNER_SCROLL])


def _expand_all(tab):
    for summary in tab.locator("summary").all():
        summary.click()
    tab.mouse.move(1, 1)
    tab.wait_for_timeout(1200)


def _assert_no_page_hscroll(name, state, m):
    assert m["doc"][0] <= m["doc"][1], (name, state, "documentElement 被推寬", m["doc"])
    assert m["main"] is not None, (name, state, "找不到 stMain")
    assert m["main"][0] <= m["main"][1] + 1, (name, state, "stMain 被推寬（整頁要橫捲）", m["main"], m["offenders"])
    assert m["offenderCount"] == 0, (name, state, "右緣超出視窗、又不在設計的容器內橫捲外框裡", m["offenders"])


def test_390寬_正式模式_渲染無例外_DataHealth燈在首屏(live_page):
    name, browser, base = live_page
    tab = _open(browser, base, name)
    m = _measure(tab, name)
    tab.close()
    assert m["vw"] == _VIEWPORT["width"] and m["vh"] == _VIEWPORT["height"], m
    assert m["exceptions"] == [], (name, m["exceptions"])
    assert m["lamp"] is not None, (name, "找不到 Data Health 燈", _LAMP[_slug(name)])
    top, _bottom, height = m["lamp"]
    assert height > 0 and 0 <= top < m["vh"], (name, "Data Health 燈不在首屏", m["lamp"])


# ~~本測試發現、尚未修的整頁橫捲：頁名 → 原因（strict：修好後 XPASS 轉紅，逼人拿掉這一條）。~~
# ~~_KNOWN_PAGE_HSCROLL = {"mkt": _MKT_HSCROLL_REASON}~~
# → 2026-10-16 同 PR 修正（狀態更新，不是漏刪；決策者：AI 總管判定屬「修回原本規格」）：市場總覽三張核心卡的 HTML
#   曾被 Markdown 當成程式碼區塊印出（3 個 `stCode`，`stMain` 被推到 5878 寬；示範模式與 1400 寬同樣重現）。
#   成因：`ui_v2/mkt/page.py::_render_card` 在沒有徽章時 `{_badges_html(...)}` 那一行只剩空白 ＝ 空行，結束 HTML 區塊；
#   已由同檔 `_drop_blank_lines` 修正，xfail 拿掉。下方 `test_沒有程式碼區塊外露_1400寬stMain不橫捲` 是這個病的專屬守衛。


def test_390寬_正式模式_整頁不得水平捲動_收合與全部展開都量(live_page):
    name, browser, base = live_page
    tab = _open(browser, base, name)
    try:
        collapsed = _measure(tab, name)
        assert collapsed["exceptions"] == [], (name, collapsed["exceptions"])
        assert collapsed["codeBlocks"] == [], (name, "HTML 被當成程式碼區塊印出", collapsed["codeBlocks"])
        _assert_no_page_hscroll(name, "收合", collapsed)
        assert set(collapsed["innerScroll"]) <= _DEFAULT_VISIBLE_INNER_SCROLL[_slug(name)], (
            name, "預設可見的容器內橫捲多了一塊（未登記）", collapsed["innerScroll"])
        _expand_all(tab)
        expanded = _measure(tab, name)
        assert expanded["exceptions"] == [], (name, expanded["exceptions"])
        _assert_no_page_hscroll(name, "全部展開", expanded)
    finally:
        tab.close()


# ───────────────────────── 程式碼區塊外露守衛（2026-10-16 市場總覽核心卡那一個病） ─────────────────────────
#
# 五頁的 page 都用 `st.markdown(unsafe_allow_html=True)` 交 HTML 樣板；樣板裡出現空行，Markdown 就把後面縮排的行當成
# 程式碼區塊，原始碼直接印上畫面、還把整頁推寬。示範與正式模式各一個情境；示範模式不帶 `?scenario=`，
# 市場總覽的預設情境 `all_ok` 正是核心卡沒有徽章的那一種（2026-10-16 實測重現過）。

_DEMO_PAGES = ("mkt", "hld", "exp", "alo", "set")   # 示範模式只跑五頁各一個（3-D 補的情境只有正式模式）
_DEMO_APPS = {name: _ROOT / "ui_v2" / f"app_{name}.py" for name in _DEMO_PAGES}
_WIDE = {"width": 1400, "height": 1200}


def _assert_no_code_block_and_no_hscroll(tab, name, mode):
    m = _measure(tab, name)
    assert m["exceptions"] == [], (name, mode, m["exceptions"])
    assert m["codeBlocks"] == [], (name, mode, "HTML 被當成程式碼區塊印出", m["codeBlocks"])
    assert m["main"] is not None and m["main"][0] <= m["main"][1] + 1, (name, mode, "1400 寬 stMain 被推寬", m["main"])


def test_沒有程式碼區塊外露_1400寬stMain不橫捲_正式模式(live_page):
    name, browser, base = live_page
    tab = browser.new_page(viewport=_WIDE)
    try:
        tab.goto(base + "/", wait_until="networkidle")
        tab.wait_for_selector(_LAMP[_slug(name)], timeout=60000)
        tab.wait_for_timeout(1500)
        _assert_no_code_block_and_no_hscroll(tab, name, "正式模式")
    finally:
        tab.close()


@pytest.mark.parametrize("name", _DEMO_PAGES)
def test_沒有程式碼區塊外露_1400寬stMain不橫捲_示範模式(browser, name):
    with _ui_v2_chromium.streamlit_server(_DEMO_APPS[name]) as base:
        tab = browser.new_page(viewport=_WIDE)
        try:
            tab.goto(base + "/", wait_until="networkidle")
            tab.wait_for_selector(_LAMP[name], timeout=60000)
            tab.wait_for_timeout(1500)
            _assert_no_code_block_and_no_hscroll(tab, name, "示範模式")
        finally:
            tab.close()
