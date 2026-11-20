# -*- coding: utf-8 -*-
"""💼 隔離式 FAKE Preview 的瀏覽器級「反控制」守衛（slow lane；需要 streamlit 與 Chromium）。

真 Chromium 390×844，逐一切到缺值／失敗／未選定／無法判定／部分略過／完整情境（情境 ③ 市值基準未開放為重點），斷言**使用者實際看到的 DOM**：
- 頁頂 harness 的 FAKE 橫幅恆在（FAKE 不得被當成真資料）；
- 沒有任何成本／持倉金額／占比／市值數字（輸入帶哨兵值，頁面整份 textContent 與 outerHTML 都不得出現）；
- 缺值字樣出現在 A20 四格，格內沒有以 0 代替；
- ③ 沒有持倉列、沒有基準值（不顯示假成本）；失敗代碼與工程詞不上畫面；
- 來源狀態字樣與 `data-source-state` 隨情境改變（同一頁、不同上游 → 不同畫面）。

反控制：判定函式必須能對「注入了哨兵值的頁面」報紅（在記憶體內現編的隨機哨兵，不寫檔）。真實 Streamlit Cloud 與真機未驗。
"""
import pathlib
import re
import secrets
import sys

import pytest

pytestmark = pytest.mark.slow

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
_APP = _ROOT / "poc" / "assets_fixture_preview" / "app_assets_preview.py"
for _p in (str(_ROOT / "tests" / "ui_v2"), str(_ROOT / "tests" / "ui_v3"), str(_HERE), str(_ROOT / "poc" / "assets_fixture_preview"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pytest.importorskip("streamlit", reason="本環境匯入不到 streamlit")

import _ui_v2_chromium  # noqa: E402
import assets_fake_inputs as fake  # noqa: E402
from shared.ui_semantics import rules  # noqa: E402

BANNER = "FAKE／測試資料（非真實持倉，不代表任何實際資料）"
MISSING = rules.entry("missing").wording
SENTINELS = (fake.SENTINEL_COST_TWD, fake.SENTINEL_COST_ORIG, fake.SENTINEL_HOLDING_VALUE, fake.SENTINEL_CATEGORY_VALUE, fake.SENTINEL_SHARE_PCT)
FORBIDDEN_WORDS = ("NaN", "None", "undefined", "null", "Traceback", "NETWORK_ERROR", "holding_read_failed", "no_active_source")
# 情境 → (預期 data-source-state, 預期持倉列數)
CASES = {
    "market_blocked": ("not_read", 0),
    "no_active": ("not_selected", 0),
    "read_failed": ("read_failed", 0),
    "unprovided_skip_evidence": ("undetermined", 0),
    "complete_counts_unprovided": ("undetermined", 2),
    "partial": ("partial", 2),
    "multi_currency": ("complete", 2),
}

DOM_JS = r"""
() => {
  const main = document.querySelector('[data-testid="stMain"]');
  const cells = [...document.querySelectorAll('[data-block="a20"] [data-status-key]')];
  const a20 = document.querySelector('[data-block="a20"]');
  return {text: main.textContent, html: main.outerHTML,
          banner: [...document.querySelectorAll('[data-harness="true"]')].map(e => e.textContent.trim()),
          state: (document.querySelector('[data-source-state]') || {dataset: {}}).dataset.sourceState || null,
          rows: document.querySelectorAll('.uv3-a50-row').length,
          a20Missing: cells.filter(e => e.dataset.statusKey === 'missing').length,
          a20Text: a20 ? a20.textContent : null,
          a50StatusOnly: !!document.querySelector('[data-a50="status-only"]'),
          basisCard: (document.querySelector('[data-block="a10"]') || {textContent: ''}).textContent,
          outbound: 0};
}
"""


def numeric_leaks(text: str, html: str, sentinels=SENTINELS) -> list:
    """畫面（textContent 與 outerHTML）裡出現任一哨兵值的任何常見字串形態 → 回傳命中者。"""
    hits = []
    for s in sentinels:
        i = int(s)
        for form in {repr(s), str(s), f"{s:,}", f"{s:,.2f}", f"{s:,.0f}", str(i), f"{i:,}"}:
            if len(form) < 5 and "." not in form:
                continue   # 太短的整數形態（例如 33）會誤中樣式的色碼，不當作證據
            if form in text or form in html:
                hits.append(form)
    return sorted(set(hits))


@pytest.fixture(scope="module")
def server_and_browser():
    api = _ui_v2_chromium.import_sync_api()
    with _ui_v2_chromium.streamlit_server(_APP) as base, api.sync_playwright() as p:
        browser = _ui_v2_chromium.launch(p)
        try:
            yield base, browser
        finally:
            browser.close()


@pytest.fixture(scope="module")
def doms(server_and_browser):
    base, browser = server_and_browser
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, locale="zh-TW", has_touch=True)
    page = ctx.new_page()
    foreign = []
    page.on("request", lambda r: foreign.append(r.url) if not re.match(r"^(http://(localhost|127\.0\.0\.1)|data:|blob:|about:)", r.url) else None)
    out = {}
    try:
        page.goto(base, wait_until="networkidle")
        page.wait_for_selector("[data-source-state]", timeout=60000)
        for sid, (state, rows) in CASES.items():
            page.locator('[data-testid="stSelectbox"] input').first.click()
            page.get_by_role("option", name=fake.SCENARIOS[sid][0], exact=True).click()
            page.wait_for_function("s => document.querySelector('[data-source-state]')?.dataset.sourceState === s", arg=state, timeout=30000)
            page.wait_for_function("n => document.querySelectorAll('.uv3-a50-row').length === n", arg=rows, timeout=30000)
            page.wait_for_timeout(400)
            out[sid] = page.evaluate(DOM_JS)
        out["_foreign_requests"] = list(foreign)
    finally:
        ctx.close()
    return out


@pytest.mark.parametrize("sid", sorted(CASES))
def test_fake_banner_is_always_present_exactly_once(doms, sid):
    assert doms[sid]["banner"] == [BANNER], doms[sid]["banner"]


@pytest.mark.parametrize("sid", sorted(CASES))
def test_no_cost_value_or_share_number_in_the_rendered_dom(doms, sid):
    d = doms[sid]
    assert numeric_leaks(d["text"], d["html"]) == [], sid
    for w in FORBIDDEN_WORDS:
        assert w not in d["text"], (sid, w)
    assert "%" not in d["text"] and "NT$" not in d["text"], sid


@pytest.mark.parametrize("sid", sorted(CASES))
def test_summary_cells_are_missing_wording_never_zero(doms, sid):
    d = doms[sid]
    assert d["a20Missing"] == 4, (sid, d["a20Missing"])
    assert d["a20Text"].count(MISSING) == 4, (sid, d["a20Text"])
    assert not re.search(r"(?<![\d.])0(?![\d.])", re.sub(r"\s+", "", d["a20Text"])), (sid, d["a20Text"])


@pytest.mark.parametrize("sid", sorted(CASES))
def test_source_state_and_row_count_follow_the_scenario(doms, sid):
    state, rows = CASES[sid]
    assert doms[sid]["state"] == state and doms[sid]["rows"] == rows, sid


def test_market_blocked_shows_no_rows_no_basis_value_no_fake_holding_name(doms):
    d = doms["market_blocked"]
    assert d["rows"] == 0 and d["a50StatusOnly"] is True
    assert "FAKE 基金" not in d["text"] and "FK0001" not in d["text"] and "成本" not in d["basisCard"]
    assert MISSING in d["basisCard"]   # 基準一格也走缺值字樣


def test_the_card_itself_carries_no_fake_marker_only_the_harness_banner_does(doms):
    """已知落差（D5，如實鎖住）：卡片本體沒有 FAKE 標記，FAKE 辨識只靠頁頂 harness 橫幅。掛載後（無 harness）此保證消失，屬 Gate G1。"""
    d = doms["multi_currency"]
    card = re.sub(r"\s+", "", d["text"]).replace(re.sub(r"\s+", "", BANNER), "")
    assert "測試資料" not in card and "示範" not in card, "缺口若已補好，請更新 docs/evidence/open_items_ledger_2026_11_20.md C-13 列與 Gate G1，並同步調整本鎖，不得單純改綠"


def test_different_upstream_different_screen(doms):
    states = {sid: doms[sid]["state"] for sid in CASES}
    assert len(set(states.values())) == 6   # not_read／not_selected／read_failed／undetermined／partial／complete（undetermined 有兩個情境共用）
    texts = {sid: re.sub(r"\s+", "", doms[sid]["text"]) for sid in CASES}
    assert texts["no_active"] != texts["read_failed"] != texts["market_blocked"]
    assert texts["unprovided_skip_evidence"] != texts["multi_currency"]


def test_page_made_no_non_local_request(doms):
    assert doms["_foreign_requests"] == []


def test_negative_control_the_leak_detector_fires_on_an_injected_sentinel():
    token = secrets.randbelow(10**9) + 10**9 + 0.5   # 本次現編的獨立哨兵，不入庫
    assert numeric_leaks(f"x {token} y", "", sentinels=(token,)) != []
    assert numeric_leaks("x 1 y", "<b>2</b>", sentinels=(token,)) == []
    assert numeric_leaks(f"x {int(token):,} y", "", sentinels=(token,)) != []   # 千分位形態也要抓得到
