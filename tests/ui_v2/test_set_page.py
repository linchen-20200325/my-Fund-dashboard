# -*- coding: utf-8 -*-
"""設定與診斷（SET）渲染層測試。

需要 streamlit；本環境的系統 python3 匯入不到 streamlit，故缺 streamlit 時整檔 skip。
⚠️ **在系統 lane 被 skip 是預期，但那代表本檔在那條 lane 上一條都沒有跑過** ——
   驗收一律用裝有 streamlit 的直譯器跑（交接檔 §2）。
"""

import html as _htmlmod
import pathlib
import re
import sys

import pytest

# 整檔標 slow（客戶 2026-09-25 裁示）：畫面測試（AppTest 與真瀏覽器）不進 fast lane
# （pre-commit 的 `pytest -m "not slow"`），改由 CI slow lane 跑。
# 守衛：`tests/ui_v2/test_ui_v2_lane_guards.py` —— 拿掉這一行會紅。
pytestmark = pytest.mark.slow

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

from ui_v2.set import fixtures, logic, page  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # 同目錄的共用模組
import _ui_v2_chromium  # noqa: E402  瀏覽器解析（CI 找不到要 fail）

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_APP = _ROOT / "ui_v2" / "app_set.py"


def _run(scenario="ok", *, save_failed=False):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(_APP), default_timeout=60)
    at.query_params["scenario"] = scenario
    if save_failed:
        at.query_params["savefail"] = "1"
    at.run()
    return at


def _rendered(at):
    """渲染出來的畫面字串 —— 權威檢查掃的是這個，不是原始碼。寧可多抓，不可漏抓。"""
    out = []
    for element in at.markdown:
        out.append(_htmlmod.unescape(element.value))
    for element in at.caption:
        out.append(element.value)
    for element in at.button:
        out.append(element.label)
        if element.help:
            out.append(element.help)
    for element in at.expander:
        out.append(element.label)
    for kind in ("text_input", "text_area"):
        for element in at.get(kind):
            out.append(element.label)
            if element.value:
                out.append(str(element.value))
    for element in at.radio:
        out.append(element.label)
        out.extend(str(o) for o in element.options)
    return out


def _button_labels(at):
    return [b.label for b in at.button]


# ───────────────────────── 分離 ─────────────────────────


def test_page只呼叫logic_自己不做判定():
    source = pathlib.Path(page.__file__).read_text(encoding="utf-8")
    for banned in (
        "def conclusion_light",
        "def columns_for_width",
        "def value_matches_kind",
        "def days_since",
        "json.",
        "datetime",
        "setting_value",
        "fetched_at",
        "取數失敗",
        "⚠",
    ):
        assert banned not in source, banned


def test_進入點docstring列的情境集合等於fixtures那一份():
    doc = _APP.read_text(encoding="utf-8")
    listed = re.search(r"\?scenario=([a-z0-9|]+)", doc).group(1).split("|")
    assert tuple(listed) == fixtures.ALL_SCENARIO_NAMES
    assert f"{len(fixtures.ALL_SCENARIO_NAMES)} 種情境" in doc


# ───────────────────────── 渲染 ─────────────────────────


def test_每一個情境與存檔失敗開關都渲染得出來而且不炸():
    for name in fixtures.ALL_SCENARIO_NAMES:
        for save_failed in fixtures.SAVE_FAIL_CHOICES:
            at = _run(name, save_failed=save_failed)
            assert not at.exception, (name, save_failed, at.exception)


def test_八塊的代號與標題都畫出來了():
    joined = "".join(_rendered(_run("ok")))
    for code, title in logic.BLOCK_TITLES.items():
        assert code in joined and title in joined, (code, title)


def test_層3層4四塊是展開區_而且預設收合():
    at = _run("ok")
    expanders = [e for e in at.expander if e.label.startswith("SET-")]
    assert [e.label.split("　")[0] for e in expanders] == ["SET-4", "SET-5", "SET-6", "SET-7"]
    for element in expanders:
        assert element.proto.expanded is False, element.label


def test_渲染出來的文字零方向詞零箭頭_每一個情境():
    for name in fixtures.ALL_SCENARIO_NAMES:
        for save_failed in fixtures.SAVE_FAIL_CHOICES:
            strings = _rendered(_run(name, save_failed=save_failed))
            assert strings
            assert logic.scan_forbidden(strings) == {}, (name, save_failed)


def test_渲染出來的按鈕只有存檔與重新取數_標籤零禁詞():
    for name in ("ok", "first", "settingfail"):
        labels = _button_labels(_run(name))
        assert sorted(labels) == ["存檔", "重新取數"], (name, labels)
        for label in labels:
            for word in logic.FORBIDDEN_BUTTON_WORDS:
                assert word not in label, (name, label)


def test_燈的狀態有圖示也有文字_三種顏色各一例():
    cases = {
        "ok": ("⬜", "資料齊、來源皆可達"),
        "stale": (logic.WARN_GLYPH, "有 1 筆資料超過你設定的新鮮度上限"),
        "failed": (logic.FETCH_FAIL_GLYPH, "失敗的來源層級：" + fixtures.FAILED_TIER),
    }
    for name, (glyph, text) in cases.items():
        lamp = [m.value for m in _run(name).markdown if 'class="set-lamp"' in m.value]
        assert len(lamp) == 1, name
        markup = _htmlmod.unescape(lamp[0])
        assert glyph in markup and text in markup and "狀態：" in markup, name


# ───────────────────────── SET-4／SET-5 輸入 ─────────────────────────


def test_首次開啟沒有一個輸入欄帶非空值_層級單選也沒有預選():
    at = _run("first")
    fields = list(at.text_input) + list(at.get("text_area"))
    assert len(fields) == 17
    for element in fields:
        assert element.value in ("", None), element.label
    assert len(at.radio) == 1 and at.radio[0].value is None


def test_SET4每一鍵一個輸入欄_多行型別畫成多行框():
    at = _run("ok")
    kinds = dict(fixtures.SPEC_SETTING_KEYS)
    labels = {e.label.split("（")[0]: "area" for e in at.get("text_area")}
    labels.update({e.label.split("（")[0]: "input" for e in at.text_input})
    assert set(labels) == set(kinds)
    for key, kind in kinds.items():
        assert labels[key] == ("area" if kind in ("list", "rules") else "input"), key


def test_SET5未選層級時重新取數停用且帶原因_選了之後可用():
    at = _run("ok")
    button = [b for b in at.button if b.label == "重新取數"][0]
    assert button.disabled is True and button.help == "尚未選定來源層級"
    assert list(at.radio[0].options) == list(fixtures.TIERS)
    at.radio[0].set_value("配息").run()
    button = [b for b in at.button if b.label == "重新取數"][0]
    assert button.disabled is False


def _set4_children(at):
    """SET-4 展開區內的元件，照畫面上的先後順序。"""
    exp = [e for e in at.expander if e.label.startswith("SET-4")][0]
    return [exp.children[i] for i in sorted(exp.children)]


_WIDGETS = ("text_input", "text_area", "button")


@pytest.mark.parametrize("fail_key", [fixtures.FAIL_KEY, "mkt_window_days", "exp_watchlist"])
def test_存檔寫入失敗_失敗框緊接在該鍵那組元件之後_下一個鍵的輸入欄之前(fail_key, monkeypatch):
    """`44` SET-4 空狀態欄；拍板原型：失敗框掛在該鍵輸入欄下方、⛔ 開頭、兩行。
    預設示範鍵 `set_max_age_days` 恰好是最後一鍵，所以另點名兩個不是最後的鍵（單行與多行各一）：
    失敗框必須落在「該鍵的輸入欄」與「下一個元件（下一鍵的輸入欄或存檔鈕）」之間。"""
    monkeypatch.setattr(fixtures, "FAIL_KEY", fail_key)
    keys = [k for k, _v in fixtures.SPEC_SETTING_KEYS]
    for name in ("ok", "first", "badkind"):
        at = _run(name, save_failed=True)
        children = _set4_children(at)
        kinds = [getattr(c, "type", "") for c in children]
        boxes = [i for i, c in enumerate(children) if kinds[i] == "markdown" and 'class="set-failbox"' in c.value]
        assert len(boxes) == 1, (name, fail_key, boxes)
        owner = [i for i, c in enumerate(children) if kinds[i] in ("text_input", "text_area")
                 and c.label.split("（")[0] == fail_key]
        assert len(owner) == 1, (name, fail_key)
        following = [i for i in range(owner[0] + 1, len(children)) if kinds[i] in _WIDGETS]
        assert following, "該鍵之後至少還有一枚存檔鈕"
        assert owner[0] < boxes[0] < following[0], (name, fail_key, owner, boxes, following)
        if keys.index(fail_key) < len(keys) - 1:
            assert kinds[following[0]] in ("text_input", "text_area"), (name, fail_key)
        assert children[owner[0]].value == fixtures.FAIL_INPUT
        text = _htmlmod.unescape(children[boxes[0]].value)
        assert logic.save_failed_text(fixtures.SAVE_FAIL_MESSAGE) in text
        assert text.split(">", 1)[1].startswith(logic.SAVE_FAIL_GLYPH + " 存檔寫入失敗：")
        assert logic.TEXT_KEEP_INPUT in text
    plain = _run("ok")
    assert fixtures.SAVE_FAIL_MESSAGE not in "".join(_rendered(plain))
    assert not [m for m in plain.markdown if 'class="set-failbox"' in m.value]


def test_SET4未設定的鍵在輸入欄下方畫出未設定():
    """建議 S2：`44` 4.5 畫面顯示 `⬜ 未設定`。逐鍵驗：每一個輸入欄與下一個元件之間有那一行。"""
    children = _set4_children(_run("first"))
    kinds = [getattr(c, "type", "") for c in children]
    fields = [i for i, k in enumerate(kinds) if k in ("text_input", "text_area")]
    assert len(fields) == 17
    for index in fields:
        nxt = next(i for i in range(index + 1, len(children)) if kinds[i] in _WIDGETS)
        between = [children[i].value for i in range(index + 1, nxt) if kinds[i] == "markdown"]
        assert any(">⬜ 未設定<" in v for v in between), children[index].label
    ok = _set4_children(_run("ok"))
    assert not [c for c in ok if getattr(c, "type", "") == "markdown" and ">⬜ 未設定<" in c.value]


def test_存檔寫入失敗時SET3那一列的目前值不變():
    def set3(at):
        column = [c for c in at.columns if any(">SET-3</span>" in m.value for m in c.markdown)][0]
        return [m.value for m in column.markdown]

    for name in ("ok", "first"):
        assert set3(_run(name)) == set3(_run(name, save_failed=True)), name


def test_存檔失敗疊在user_setting讀取失敗上_失敗框照樣畫出來_但不說上面這一欄():
    """必修：此時 SET-4 沒有任何輸入欄，失敗框只印第一行。"""
    at = _run("settingfail", save_failed=True)
    boxes = [_htmlmod.unescape(m.value) for m in at.markdown if 'class="set-failbox"' in m.value]
    assert len(boxes) == 1
    assert logic.save_failed_text(fixtures.SAVE_FAIL_MESSAGE) in boxes[0]
    assert logic.TEXT_KEEP_INPUT not in boxes[0]
    assert not at.text_input and not at.get("text_area")


# ───────────────────────── 取數失敗逐塊 ─────────────────────────


def _fail_count_by_block(at, text):
    out = {}
    out["SET-0"] = sum(_htmlmod.unescape(m.value).count(text) for m in at.markdown if 'class="set-lamp"' in m.value)
    for column in at.columns:
        markup = [m.value for m in column.markdown]
        for code in ("SET-1", "SET-2", "SET-3"):
            if any(f">{code}</span>" in m for m in markup):
                out[code] = _htmlmod.unescape("".join(markup)).count(text)
    for exp in at.expander:
        code = exp.label.split("　")[0]
        if code.startswith("SET-"):
            out[code] = _htmlmod.unescape("".join(m.value for m in exp.markdown)).count(text)
    return out


def test_讀取失敗在畫面上逐塊畫出_每一塊有且只有應有的失敗框():
    """逐塊對回模型（不是只數總數）：page 漏畫任何一塊都會紅。"""
    text = logic.fetch_failed_text(fixtures.READ_FAIL_MESSAGE)
    for name in ("navfail", "logfail", "settingfail", "ok"):
        model = logic.build_page_model(fixtures.scenario(name))
        expected = {b["code"]: int(any(text in s for s in logic.collect_ui_strings(b))) for b in model["blocks"]}
        got = _fail_count_by_block(_run(name), text)
        assert set(got) == set(expected), (name, sorted(got))
        assert got == expected, (name, got, expected)


def test_SET2失敗那一列的訊息原文逐字畫在畫面上():
    joined = "".join(_rendered(_run("failed")))
    assert fixtures.TIER_FAIL_MESSAGE in joined
    assert "回應為空" in "".join(_rendered(_run("emptyresp")))


def test_SET7未定義徽章與SET6保留筆數表尾畫在畫面上():
    assert "未定義" in "".join(_rendered(_run("undef")))
    total = len(fixtures.scenario("keep1")["fetch_log"])
    assert f"已移除 {total - 1} 筆" in "".join(_rendered(_run("keep1")))


# ───────────────────────── 畫面層：CSS 權重（靜態） ─────────────────────────


def _specificity(selector: str):
    ids = selector.count("#")
    classes = len(re.findall(r"\.[\w-]+|\[[^\]]+\]|:(?!:)[\w-]+", selector))
    elements = len(re.findall(r"(?:^|[\s>+~])([a-zA-Z][\w-]*)", selector))
    return (ids, classes, elements)


def test_帶色調的set規則權重高過全域的stApp_span():
    css = page._base_css()
    rules = re.findall(r"([^{}]+)\{([^{}]*)\}", css)
    colored = [(sel.strip(), body) for sel, body in rules if ".set-" in sel and re.search(r"(?<![-\w])color\s*:", body)]
    assert len(colored) >= 10, len(colored)
    floor = _specificity(".stApp span")
    for selectors, _body in colored:
        for selector in selectors.split(","):
            assert _specificity(selector.strip()) > floor, selector


# ───────────────────────── 畫面層：真的瀏覽器 ─────────────────────────

# 瀏覽器怎麼找、找不到時 skip 還是 fail：見 `_ui_v2_chromium.py`（CI=true 時 fail，本機 skip）。


@pytest.fixture(scope="module")
def browser_page():
    playwright_api = _ui_v2_chromium.import_sync_api()
    with playwright_api.sync_playwright() as p:
        browser = _ui_v2_chromium.launch(p)  # 先確認瀏覽器在，再起 streamlit
        try:
            # 起 streamlit、等健康檢查、起不來時把子行程輸出尾端放進 fail 訊息：見 `_ui_v2_chromium.streamlit_server`。
            with _ui_v2_chromium.streamlit_server(_APP) as base:
                yield browser, base
        finally:
            browser.close()


def _open(browser, base, scenario, width=1400, save_failed=False):
    tab = browser.new_page(viewport={"width": width, "height": 1200})
    tab.goto(f"{base}/?scenario={scenario}" + ("&savefail=1" if save_failed else ""), wait_until="networkidle")
    tab.wait_for_selector("text=可信度結論燈", timeout=60000)
    tab.wait_for_timeout(1500)
    for summary in tab.locator("summary").all():
        summary.click()
    tab.mouse.move(1, 1)
    tab.wait_for_timeout(800)
    return tab


def _rgb(hex_color):
    return "rgb({}, {}, {})".format(*(int(hex_color[i : i + 2], 16) for i in (1, 3, 5)))


def test_瀏覽器量到燈的三種顏色與卡片標題真的是那個顏色(browser_page):
    from ui_v2.set import theme

    browser, base = browser_page
    color = lambda tab, sel: tab.eval_on_selector(sel, "e => getComputedStyle(e).color")  # noqa: E731
    for name, hex_color in (("stale", theme.STATE_WARN), ("failed", theme.STATE_ERR), ("ok", theme.STATE_GRAY)):
        tab = _open(browser, base, name)
        assert color(tab, ".set-lamp-text") == _rgb(hex_color), name
        assert color(tab, ".set-stword") == _rgb(hex_color), name
        if name == "ok":
            assert color(tab, ".set-card-title") == _rgb(theme.TEAL_BRIGHT)
        tab.close()


def test_瀏覽器量到失敗框是灰態容器_而且在該鍵輸入欄正下方(browser_page):
    from ui_v2.set import theme

    browser, base = browser_page
    tab = _open(browser, base, "ok", save_failed=True)
    box = tab.locator(".set-failbox")
    assert box.count() == 1
    style = box.evaluate("e => { const s = getComputedStyle(e); return [s.color, s.backgroundColor, s.borderTopColor]; }")
    assert style == [_rgb(theme.STATE_GRAY), _rgb(theme.STATE_GRAY_BG), _rgb(theme.STATE_GRAY)], style
    assert box.inner_text().startswith(logic.SAVE_FAIL_GLYPH)
    field = tab.get_by_label(re.compile("^" + fixtures.FAIL_KEY))
    assert field.input_value() == fixtures.FAIL_INPUT
    field_box, fail_box = field.bounding_box(), box.bounding_box()
    assert fail_box["y"] > field_box["y"] + field_box["height"] - 1
    assert fail_box["y"] - (field_box["y"] + field_box["height"]) < 120, (field_box, fail_box)
    tab.close()


_AUDIT_JS = """
() => {
  const lum = c => { const v = c / 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  const parse = s => { const m = s.match(/rgba?\\(([^)]+)\\)/); if (!m) return null;
    const p = m[1].split(',').map(x => parseFloat(x)); return {r:p[0], g:p[1], b:p[2], a: p.length > 3 ? p[3] : 1}; };
  const L = c => 0.2126 * lum(c.r) + 0.7152 * lum(c.g) + 0.0722 * lum(c.b);
  const bgOf = el => { const chain = []; for (let e = el; e; e = e.parentElement) chain.push(e);
      let c = {r: 14, g: 17, b: 23, a: 1};
      for (const e of chain.reverse()) { const x = parse(getComputedStyle(e).backgroundColor);
        if (x && x.a > 0) c = {r: x.r * x.a + c.r * (1 - x.a), g: x.g * x.a + c.g * (1 - x.a),
                               b: x.b * x.a + c.b * (1 - x.a), a: 1}; }
      return c; };
  const out = []; let n = 0;
  const main = document.querySelector('[data-testid=stMain]') || document.body;
  for (const el of main.querySelectorAll('*')) {
    const own = [...el.childNodes].some(x => x.nodeType === 3 && x.textContent.trim());
    if (!own) continue;
    const st = getComputedStyle(el);
    if (st.visibility === 'hidden' || st.display === 'none' || el.getClientRects().length === 0) continue;
    if (el.closest('button:disabled, [disabled], [aria-disabled=true]')) continue;
    const raw = parse(st.color), bg = bgOf(el); n++;
    const fg = {r: raw.r * raw.a + bg.r * (1 - raw.a), g: raw.g * raw.a + bg.g * (1 - raw.a),
                b: raw.b * raw.a + bg.b * (1 - raw.a), a: 1};
    const a = L(fg), b = L(bg), r = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    if (r < 4.5) out.push([el.textContent.trim().slice(0, 30), st.color, r.toFixed(2)]);
  }
  return {checked: n, failures: out};
}
"""


def test_瀏覽器逐一量畫面上每一段文字的實際前景與背景對比(browser_page):
    """驗的是 page 實際畫出來的前景／背景組合，不只色票常數。停用中的控制項不在門檻內（WCAG 1.4.3 例外）。"""
    browser, base = browser_page
    for name, save_failed in (("ok", False), ("first", True), ("failed", False), ("stale", False),
                              ("settingfail", True), ("undef", False), ("badkind", True)):
        tab = _open(browser, base, name, save_failed=save_failed)
        result = tab.evaluate(_AUDIT_JS)
        tab.close()
        assert result["checked"] >= 60, (name, result["checked"])
        assert not result["failures"], (name, result["failures"][:8])


def test_瀏覽器每一個情境與存檔失敗開關都沒有例外_375寬沒有橫向捲動(browser_page):
    browser, base = browser_page
    for name in fixtures.ALL_SCENARIO_NAMES:
        for save_failed in fixtures.SAVE_FAIL_CHOICES:
            tab = _open(browser, base, name, width=375, save_failed=save_failed)
            assert tab.locator("[data-testid=stException]").count() == 0, (name, save_failed)
            widths = tab.evaluate(
                "() => { const m = document.querySelector('[data-testid=stMain]') || document.documentElement;"
                " return [m.scrollWidth, m.clientWidth, document.documentElement.scrollWidth, window.innerWidth]; }"
            )
            tab.close()
            assert widths[0] <= widths[1] and widths[2] <= widths[3], (name, save_failed, widths)
