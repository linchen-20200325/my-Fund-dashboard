# -*- coding: utf-8 -*-
"""資產配置（ALO）渲染層測試。

需要 streamlit；本環境的系統 python3 匯入不到 streamlit，故缺 streamlit 時整檔 skip。
⚠️ **在系統 lane 被 skip 是預期，但那代表本檔在那條 lane 上一條都沒有跑過** ——
   驗收一律用裝有 streamlit 的直譯器跑（交接檔 §2）。
"""

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

from ui_v2.alo import fixtures, logic, page  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # 同目錄的共用模組
import _ui_v2_chromium  # noqa: E402  瀏覽器解析（CI 找不到要 fail）

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_APP = _ROOT / "ui_v2" / "app_alo.py"


def _run(scenario="full", *, save_failed=False):
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
        out.append(element.value)
    for element in at.caption:
        out.append(element.value)
    for element in at.button:
        out.append(element.label)
        if element.help:
            out.append(element.help)
    for element in at.expander:
        out.append(element.label)
    for element in at.text_input:
        out.append(element.label)
        if element.value:
            out.append(str(element.value))
    for element in at.radio:
        out.append(element.label)
        out.extend(str(o) for o in element.options)
    for element in at.get("download_button"):
        out.append(element.proto.label)
    return out


def _button_labels(at):
    return [b.label for b in at.button] + [d.proto.label for d in at.get("download_button")]


# ───────────────────────── 分離 ─────────────────────────


def test_page只呼叫logic_自己不做判定():
    source = pathlib.Path(page.__file__).read_text(encoding="utf-8")
    for banned in (
        "def conclusion_light",
        "def columns_for_width",
        "def basis_value",
        "def fx_for_date",
        "math.",
        "isclose",
        "import math",
        "holding\"]",
        "setting_value(",
    ):
        assert banned not in source, banned


def test_進入點docstring列的情境集合等於fixtures那一份():
    doc = _APP.read_text(encoding="utf-8")
    listed = re.search(r"\?scenario=([a-z|]+)", doc).group(1).split("|")
    assert tuple(listed) == fixtures.ALL_SCENARIO_NAMES
    assert f"{len(fixtures.ALL_SCENARIO_NAMES)} 種情境" in doc


# ───────────────────────── 渲染 ─────────────────────────


def test_每一個情境與存檔失敗開關都渲染得出來而且不炸():
    for name in fixtures.ALL_SCENARIO_NAMES:
        for save_failed in fixtures.SAVE_FAIL_CHOICES:
            at = _run(name, save_failed=save_failed)
            assert not at.exception, (name, save_failed, at.exception)


def test_八塊的代號與標題都畫出來了():
    joined = "".join(_rendered(_run("full")))
    for code, title in logic.BLOCK_TITLES.items():
        assert code in joined and title in joined, (code, title)


def test_層3層4四塊是展開區_而且預設收合():
    at = _run("full")
    expanders = [e for e in at.expander if e.label.startswith("ALO-")]
    assert [e.label.split("　")[0] for e in expanders] == ["ALO-4", "ALO-5", "ALO-6", "ALO-7"]
    for element in expanders:
        assert element.proto.expanded is False, element.label


def test_渲染出來的文字零方向詞零箭頭_每一個情境():
    for name in fixtures.ALL_SCENARIO_NAMES:
        for save_failed in fixtures.SAVE_FAIL_CHOICES:
            strings = _rendered(_run(name, save_failed=save_failed))
            assert strings
            assert logic.scan_forbidden(strings) == {}, (name, save_failed)


def test_渲染出來的按鈕標籤零禁詞():
    for name in ("full", "first"):
        labels = _button_labels(_run(name))
        assert labels
        for label in labels:
            for word in logic.FORBIDDEN_BUTTON_WORDS:
                assert word not in label, (name, label)


def test_ALO4導覽鈕在畫面上持倉表空或不空都出現():
    """`44` ALO-4 判準新兩步（2026-09-24 第二十一輪）：第一步空持倉時出現、第二步有持倉時同樣出現。
    兩種都在畫面上驗（first＝空、full＝有資料），另逐情境掃：每一個情境畫面上都有那一枚（含 holding 取數失敗）。"""
    for name in fixtures.ALL_SCENARIO_NAMES:
        labels = _button_labels(_run(name))
        assert labels.count(logic.TEXT_GOTO_SHEETS) == 1, (name, labels)
    for name in ("first", "full"):
        at = _run(name)
        assert logic.TEXT_GOTO_SHEETS in _button_labels(at), name
        assert logic.TEXT_SHEETS_READONLY in "".join(_rendered(at)), name


def test_目標合計那一行灰字只在合計不為一時畫出來():
    assert any("目標合計 90%" in s for s in _rendered(_run("partial")))
    assert not any("目標合計" in s for s in _rendered(_run("full")))


def test_存檔寫入失敗的訊息原文畫在畫面上():
    joined = "".join(_rendered(_run("full", save_failed=True)))
    assert joined.count(fixtures.SAVE_FAIL_MESSAGE) == 3  # ALO-1、ALO-3、ALO-4 各一
    assert fixtures.SAVE_FAIL_MESSAGE not in "".join(_rendered(_run("full")))


def test_存檔寫入失敗框以禁止號開頭_畫面上不出現警告號配存檔失敗():
    """客戶 2026-09-25 裁示：存檔寫入失敗 ⛔，⚠ 只留給黃燈。量的是渲染出來的失敗框本身。"""
    rendered = _rendered(_run("full", save_failed=True))
    boxes = [s for s in rendered if 'class="alo-errline"' in s]
    assert len(boxes) == 3, boxes  # ALO-1、ALO-3、ALO-4 各一
    for box in boxes:
        assert f'role="alert">⛔ {logic.TEXT_SAVE_FAILED}：' in box, box
    joined = "".join(rendered)
    assert "⚠ " + logic.TEXT_SAVE_FAILED not in joined
    assert "⚠ " + fixtures.SAVE_FAIL_MESSAGE not in joined


def test_首次開啟沒有一個輸入欄帶非空值_基準二選一也沒有預選():
    at = _run("first")
    assert at.text_input, "一個輸入欄也沒有 —— 會變成空掃"
    for element in at.text_input:
        assert element.value in ("", None), element.label
    assert at.radio and at.radio[0].value is None


def test_匯出鈕在畫面上無列時停用且帶停用原因():
    disabled = _run("notarget").get("download_button")
    assert len(disabled) == 1
    assert disabled[0].proto.disabled is True
    assert disabled[0].proto.help == logic.TEXT_NO_EXPORT_ROWS
    enabled = _run("full").get("download_button")
    assert len(enabled) == 1 and enabled[0].proto.disabled is False


def test_燈的狀態有圖示也有文字():
    joined = "".join(_rendered(_run("full")))
    assert 'aria-hidden="true">⚠</div>' in joined and "狀態：要多看一眼" in joined
    # 取數失敗的燈用 ⛔（客戶 2026-09-24 裁示），不是 ⚠；黃燈仍是 ⚠。量的是燈的圖示格本身。
    failed = "".join(m.value for m in _run("holdfail").markdown if "alo-lamp" in m.value)
    assert 'aria-hidden="true">⛔</div>' in failed and "狀態：取數失敗" in failed
    assert f"{fixtures.CORE} 與目標差 6.0 個百分點" in joined


# ───────────────────────── 畫面層：示意行、取數失敗、ALO-4 的輸入元件 ─────────────────────────


def test_頁首示意行與每一塊的示意行真的畫在畫面上():
    at = _run("full")
    strings = _rendered(at)
    assert any(logic.PAGE_HINT_NOTE in s for s in strings)
    model = logic.build_page_model(fixtures.scenario("full"))
    expected = sum(logic.HINT_NOTE in b["detail_lines"] for b in model["blocks"])
    assert expected >= 6
    assert sum(logic.HINT_NOTE in s for s in strings) == expected


_FAIL_TEXT = "⛔ 取數失敗：" + fixtures.FETCH_FAIL_MESSAGE


def _fail_count_by_block(at):
    """逐塊數畫面上的失敗文案：燈（`alo-lamp` 那一段）、層 2 三欄（以卡頭的塊代號認欄）、層 3／4 四個展開區。"""
    import html as _html

    out = {}
    text = lambda values: _html.unescape("".join(values))  # noqa: E731
    out["ALO-0"] = sum(text([m.value]).count(_FAIL_TEXT) for m in at.markdown if "alo-lamp" in m.value)
    for column in at.columns:
        markup = [m.value for m in column.markdown]
        for code in ("ALO-1", "ALO-2", "ALO-3"):
            if any(f">{code}</span>" in m for m in markup):
                out[code] = text(markup).count(_FAIL_TEXT)
    for exp in at.expander:
        code = exp.label.split("　")[0]
        if code.startswith("ALO-"):
            out[code] = text([m.value for m in exp.markdown]).count(_FAIL_TEXT)
    return out


def test_取數失敗在畫面上逐塊畫出_每一塊有且只有應有的失敗框():
    """稽核 N12：舊版只斷言總數 >= 4，page 漏畫 ALO-4 那一框照樣過。現在逐塊對回模型。"""
    for name in ("holdfail", "fxfail", "settingfail", "policyfail", "full"):
        model = logic.build_page_model(fixtures.scenario(name))
        expected = {
            b["code"]: int(any(_FAIL_TEXT in s for s in logic.collect_ui_strings(b))) for b in model["blocks"]
        }
        got = _fail_count_by_block(_run(name))
        assert set(got) == set(expected), (name, sorted(got))
        assert got == expected, (name, got, expected)


_WIDGET_TYPES = (
    "text_input", "number_input", "text_area", "selectbox", "multiselect", "checkbox",
    "radio", "slider", "select_slider", "date_input", "time_input", "toggle", "color_picker",
)


def test_ALO4畫面上沒有任何可以改指派的輸入元件():
    """`44` ALO-4 判準：在指派欄上按任何一處，值不變，畫面上也沒有任何可以改它的輸入元件。
    在 AppTest 裡數 ALO-4 展開區內的每一種輸入元件與它的 key／label。"""
    for name in ("full", "unbkt", "nobucket"):
        at = _run(name)
        block = [e for e in at.expander if e.label.startswith("ALO-4")]
        assert len(block) == 1
        exp = block[0]
        counts = {kind: len(exp.get(kind)) for kind in _WIDGET_TYPES}
        names = logic.setting_value(fixtures.scenario(name), "alo_bucket_names") or ()
        assert counts.pop("radio") == 1 and counts.pop("text_input") == len(names), (name, counts)
        assert not any(counts.values()), (name, counts)
        assert exp.radio[0].label == "比重基準"
        codes = {h["fund_code"] for h in fixtures.scenario(name)["holding"]}
        for widget in exp.text_input:
            assert widget.label.startswith("類別名稱 "), widget.label
            assert not any(code in (widget.key or "") or code in widget.label for code in codes)


# ───────────────────────── 畫面層：CSS 權重（靜態） ─────────────────────────


def _specificity(selector: str):
    ids = selector.count("#")
    classes = len(re.findall(r"\.[\w-]+|\[[^\]]+\]|:(?!:)[\w-]+", selector))
    elements = len(re.findall(r"(?:^|[\s>+~])([a-zA-Z][\w-]*)", selector))
    return (ids, classes, elements)


def test_帶色調的alo規則權重高過全域的stApp_span():
    """稽核 G：`.stApp span` 曾把燈的黃字與卡片標題的青色蓋掉。每一條會設 color 的 `.alo-*` 規則，
    權重都要嚴格高過 `.stApp span`。"""
    css = page._base_css()
    rules = re.findall(r"([^{}]+)\{([^{}]*)\}", css)
    colored = [(sel.strip(), body) for sel, body in rules if ".alo-" in sel and re.search(r"(?<![-\w])color\s*:", body)]
    assert len(colored) >= 8, len(colored)
    floor = _specificity(".stApp span")
    for selectors, _body in colored:
        for selector in selectors.split(","):
            assert _specificity(selector.strip()) > floor, selector


# ───────────────────────── 畫面層：真的瀏覽器 ─────────────────────────

# 瀏覽器怎麼找、找不到時 skip 還是 fail：見 `_ui_v2_chromium.py`（CI=true 時 fail，本機 skip）。


@pytest.fixture(scope="module")
def browser_page():
    playwright_api = _ui_v2_chromium.import_sync_api()
    import socket
    import subprocess
    import time
    import urllib.request

    with playwright_api.sync_playwright() as p:
        browser = _ui_v2_chromium.launch(p)  # 先確認瀏覽器在，再起 streamlit
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        proc = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", str(_APP), "--server.headless", "true",
             "--server.port", str(port), "--browser.gatherUsageStats", "false"],
            # 不讀輸出就不要開 PIPE：管線緩衝塞滿會讓 streamlit 卡住。
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        base = f"http://127.0.0.1:{port}"
        try:
            for _ in range(120):
                try:
                    if urllib.request.urlopen(base + "/_stcore/health", timeout=1).read() == b"ok":
                        break
                except Exception:
                    time.sleep(0.5)
            else:
                pytest.fail("streamlit 沒有起來")
            yield browser, base
        finally:
            browser.close()
            proc.terminate()
            proc.wait(timeout=20)


def _open(browser, base, scenario, width=1400):
    tab = browser.new_page(viewport={"width": width, "height": 1200})
    tab.goto(f"{base}/?scenario={scenario}", wait_until="networkidle")
    tab.wait_for_selector("text=差距結論燈", timeout=60000)
    tab.wait_for_timeout(1500)
    for summary in tab.locator("summary").all():
        summary.click()
    tab.mouse.move(1, 1)  # 滑鼠移開，量的是不被游標停住時的畫面
    tab.wait_for_timeout(800)
    return tab


def _rgb(hex_color):
    return "rgb({}, {}, {})".format(*(int(hex_color[i : i + 2], 16) for i in (1, 3, 5)))


def test_瀏覽器量到燈的黃字與狀態字與卡片標題真的是那個顏色(browser_page):
    from ui_v2.alo import theme

    browser, base = browser_page
    tab = _open(browser, base, "full")
    color = lambda sel: tab.eval_on_selector(sel, "e => getComputedStyle(e).color")  # noqa: E731
    assert color(".alo-lamp-text") == _rgb(theme.STATE_WARN)
    assert color(".alo-stword") == _rgb(theme.STATE_WARN)
    assert color(".alo-card-title") == _rgb(theme.TEAL_BRIGHT)
    tab.close()


_AUDIT_JS = """
() => {
  const lum = c => { const v = c / 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  const parse = s => { const m = s.match(/rgba?\\(([^)]+)\\)/); if (!m) return null;
    const p = m[1].split(',').map(x => parseFloat(x)); return {r:p[0], g:p[1], b:p[2], a: p.length > 3 ? p[3] : 1}; };
  const L = c => 0.2126 * lum(c.r) + 0.7152 * lum(c.g) + 0.0722 * lum(c.b);
  // 背景：由根往下把每一層（含半透明層）依 alpha 疊在頁底上，得到這個元素底下實際的顏色。
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
    // 稽核建議 5：前景 alpha < 1 時先疊在背景上再算（否則半透明字會被當成實色，對比被高估）。
    const fg = {r: raw.r * raw.a + bg.r * (1 - raw.a), g: raw.g * raw.a + bg.g * (1 - raw.a),
                b: raw.b * raw.a + bg.b * (1 - raw.a), a: 1};
    const a = L(fg), b = L(bg), r = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    if (r < 4.5) out.push([el.textContent.trim().slice(0, 30), st.color, r.toFixed(2)]);
  }
  return {checked: n, failures: out};
}
"""


def test_瀏覽器逐一量畫面上每一段文字的實際前景與背景對比(browser_page):
    """稽核守衛 2：驗的是 page 實際畫出來的前景／背景組合，不只色票常數。停用中的控制項不在門檻內（WCAG 1.4.3 例外）。"""
    browser, base = browser_page
    for name in ("full", "first", "nofx", "holdfail", "settingfail", "partial"):
        tab = _open(browser, base, name)
        result = tab.evaluate(_AUDIT_JS)
        tab.close()
        assert result["checked"] >= 40, (name, result["checked"])
        assert not result["failures"], (name, result["failures"][:8])


def test_瀏覽器每一個情境都沒有例外_375寬沒有橫向捲動(browser_page):
    browser, base = browser_page
    for name in fixtures.ALL_SCENARIO_NAMES:
        tab = _open(browser, base, name, width=375)
        assert tab.locator("[data-testid=stException]").count() == 0, name
        widths = tab.evaluate(
            "() => { const m = document.querySelector('[data-testid=stMain]') || document.documentElement;"
            " return [m.scrollWidth, m.clientWidth, document.documentElement.scrollWidth, window.innerWidth]; }"
        )
        tab.close()
        assert widths[0] <= widths[1] and widths[2] <= widths[3], (name, widths)
