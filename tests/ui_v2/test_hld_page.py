# -*- coding: utf-8 -*-
"""持倉體檢（HLD）渲染層測試。

需要 streamlit；本環境的系統 python3 匯入不到 streamlit，故缺 streamlit 時整檔 skip。
要跑起來：PYTHONPATH=<裝有 streamlit 的目錄> pytest tests/ui_v2/ -q --noconftest
"""

import pathlib
import re
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

from ui_v2.hld import fixtures, logic, page, theme  # noqa: E402

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_APP = _ROOT / "ui_v2" / "app_hld.py"


def _run(scenario="full"):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(_APP), default_timeout=60)
    at.query_params["scenario"] = scenario
    at.run()
    return at


def _rendered(at):
    """渲染出來的畫面字串 —— 權威檢查掃的是這個，不是原始碼。

    ⚠️ **展開區的標題列也是畫面文字**。第一版這支只收 markdown／caption／button，
    於是 `HLD-4`～`HLD-8` 五塊的標題列整列掃不到 —— 紅線字表掃描會跟著瞎掉一半。
    是 `test_九塊的標題都畫出來了` 把它抓出來的。**寧可多抓，不可漏抓。**
    """
    out = []
    for element in at.markdown:
        out.append(element.value)
    for element in at.caption:
        out.append(element.value)
    for element in at.button:
        out.append(element.label)
    for element in at.expander:
        out.append(element.label)
    for element in at.text_input:
        out.append(element.label)
        if element.placeholder:
            out.append(element.placeholder)
        if element.value:
            out.append(str(element.value))
    for group in (at.title, at.text, at.error, at.warning, at.info, at.success):
        for element in group:
            out.append(element.value)
    return out


# ───────────────────────── 分離 ─────────────────────────


def test_page只呼叫logic與fixtures與theme_自己不做判定():
    source = pathlib.Path(page.__file__).read_text(encoding="utf-8")
    for banned in (
        "STATE_OK =",
        "def columns_for_width",
        "def main_value_state",
        "def conclusion_light",
        "def return_pct",
        "def drawdown_pct",
    ):
        assert banned not in source


def test_page沒有import舊repo模組也沒有網路字表():
    source = pathlib.Path(page.__file__).read_text(encoding="utf-8")
    for banned in (
        "from ui.",
        "from services.",
        "from repositories.",
        "from shared.",
        "from infra.",
        "import fund_fetcher",
        "requests",
        "httpx",
        "urllib",
        "yfinance",
        "gspread",
        "feedparser",
        "subprocess",
    ):
        assert banned not in source


def test_進入點沒有import舊repo模組():
    source = _APP.read_text(encoding="utf-8")
    for banned in ("from ui.", "from services.", "from repositories.", "from shared.", "from infra."):
        assert banned not in source


# ───────────────────────── 渲染 ─────────────────────────


def test_六種狀態各渲染一次都不炸():
    """任何一個丟例外就是紅燈（§1 Fail Loud：不吞例外）。"""
    for scenario in ("full", "srcmiss", "bizexc", "fetchfail", "nothr", "empty"):
        at = _run(scenario)
        assert not at.exception, scenario


def test_層三層四用expander且預設收合():
    source = pathlib.Path(page.__file__).read_text(encoding="utf-8")
    assert "st.expander" in source
    model = logic.build_page_model(fixtures.dataset_full())
    for code in ("HLD-4", "HLD-5", "HLD-6", "HLD-7", "HLD-8"):
        assert logic.find_block(model, code)["_default_open"] is False


def test_九塊的標題都畫出來了():
    at = _run("full")
    joined = "".join(_rendered(at))
    for code, title in logic.BLOCK_TITLES.items():
        assert code in joined, code
        assert title in joined, title


# ───────────────────────── 紅線（掃實際畫面字串） ─────────────────────────


def test_渲染出來的文字零方向詞零箭頭():
    for scenario in ("full", "srcmiss", "bizexc", "fetchfail", "nothr", "empty"):
        at = _run(scenario)
        assert logic.scan_forbidden(_rendered(at)) == {}, scenario


def test_渲染出來的按鈕標籤零禁詞():
    for scenario in ("full", "empty"):
        at = _run(scenario)
        for button in at.button:
            for word in logic.FORBIDDEN_BUTTON_WORDS:
                assert word not in button.label, (scenario, button.label)


def test_渲染出來的輸入欄沒有一個帶非空的預設值():
    """`44` 1.1 節判準後半句，驗的是真的 widget。"""
    at = _run("empty")
    for widget in list(at.text_input) + list(at.date_input) + list(at.number_input):
        assert widget.value in (None, "", []), widget.label


# ───────────────────────── 主題 ─────────────────────────


def test_theme色票就是客戶指定的三個色():
    assert theme.APP_BG == "#0e1117"
    assert theme.TEAL_DARK == "#0f6b6c"
    assert theme.TEAL_BRIGHT == "#5fd3d0"


def test_畫面用到的每一個色碼都登記在對比表裡():
    """防的是「在 page.py 裡隨手寫一個沒算過對比的色碼」。"""
    import re

    source = pathlib.Path(page.__file__).read_text(encoding="utf-8")
    hexes = {h.lower() for h in re.findall(r"#[0-9a-fA-F]{6}", source)}
    known = {c.lower() for c in theme.ALL_COLORS}
    assert hexes <= known, hexes - known


# ─────────── 第 5~8 輪裁示的回補 ＋ 本輪回修（渲染層正控） ───────────


def _source_tier_cells(at) -> list:
    """把 `HLD-6` 淨值表「來源層級」那一欄抽出來逐格回傳。

    掃整頁字串會被別處的同字命中（「淨值表」「單位淨值（原幣）」都含「淨值」），
    所以認的是**那一欄本身**：表頭找出欄位序，再取每一列同序的那一格。
    """
    for element in at.markdown:
        html_text = element.value
        if "淨值日期" not in html_text or "<table" not in html_text:
            continue
        heads = re.findall(r"<th>(.*?)</th>", html_text, re.S)
        if "來源層級" not in heads:
            return []
        index = heads.index("來源層級")
        cells = []
        for row in re.findall(r"<tr>(?!.*?<th>)(.*?)</tr>", html_text, re.S):
            tds = re.findall(r"<td>(.*?)</td>", row, re.S)
            if len(tds) > index:
                cells.append(re.sub(r"<[^>]+>", "", tds[index]).strip())
        return cells
    return []


def test_渲染出來的畫面沒有值域外的來源層級字面值():
    """`44` :1799 值域四個之一。⚠️ **本條第一版的防空掃守衛是假的**：`assert "淨值" in blob`
    —— 「淨值」也出現在「淨值表」「單位淨值（原幣）」，**把那一欄整個拿掉照樣通過**。
    現改為抽出該欄逐格看，並先斷言格數大於零。"""
    cells = _source_tier_cells(_run("full"))
    assert cells, "抽不到來源層級那一欄 —— 這一條會變成空掃"
    for cell in cells:
        assert cell in fixtures.SOURCE_TIERS, cell


def test_渲染出來的畫面不再出現被劃掉的那一句():
    """`44` :720（第五輪改寫）。"""
    for scenario in fixtures.SCENARIO_NAMES:
        blob = "\n".join(_rendered(_run(scenario)))
        assert "上面三張卡" not in blob, scenario
        if scenario == "full":
            assert "本頁那四塊用到的原始數字" in blob


def test_重新取數在畫面上的枚數與模型相等():
    """A3 撤回後的渲染層對照：釘模型與畫面不脫鉤，不釘「有幾枚」—— 客戶往哪邊裁都不擋。"""
    for scenario in ("srcmiss", "fetchfail"):
        model = logic.build_page_model(**fixtures.scenario(scenario))
        expected = sum(
            1 for block in logic.all_blocks(model)
            for b in block["buttons"] if b["label"] == "重新取數"
        )
        assert expected > 0, scenario
        rendered = sum(1 for b in _run(scenario).button if b.label == "重新取數")
        assert rendered == expected, (scenario, rendered, expected)


_KV_OPEN_TAG = '<div class="hld-kv">'


def _expanded_fields(at) -> list:
    """畫面上真的展開了的是哪幾檔 —— 看展開內容那一塊有沒有被畫出來。

    ⚠️ 不看 `_open` 旗標：那是模型，這一支要驗的是**畫面**。

    ⚠️ **2026-09-24 就地更正：原本那個看起來像守衛的條件不守任何東西**
    （有意識的更正，不是漏刪；決策者：AI 總管；稽核抓到）。
    ~~原寫 `if "hld-kv" in blob and marker in blob`。~~
    **`hld-kv` 這個字串同時出現在 `page.py` 注進去的 `<style>` 裡**（CSS 的類別定義），
    而 `<style>` 也是一個 `at.markdown` 元素 ⇒ **零檔展開時那個條件就已經是 `True`**，
    那個 `and` 的左半**恆真**。結論今天碰巧對（三檔的單位數字串互異），
    **但左半從來沒有守過任何東西。**
    **現行**：(1) 把 `<style>` 整個排除掉；(2) 認的是**開標籤**而不是類別名 ——
    CSS 裡寫的是選擇器，不含開標籤，所以這一次真的分得開；
    (3) 順便斷言畫出來的展開區塊數與抓到的檔數相等，讓它自己驗自己。
    """
    key = logic.HLD5_OPEN_KEY
    opened = at.session_state[key] if key in at.session_state else None
    model = logic.build_page_model(**fixtures.scenario("full"), open_fund=opened)
    blob = "\n".join(
        element.value for element in at.markdown if "<style>" not in element.value
    )
    out = []
    for item in logic.find_block(model, "HLD-5")["_items"]:
        marker = item["_fields"][3][1]  # 單位數那一格：逐檔不同，只在展開內容裡出現
        if _KV_OPEN_TAG in blob and marker in blob:
            out.append(item["_fund_code"])
    # 自驗：畫面上展開區塊的枚數，要與上面抓到的檔數一致。
    assert blob.count(_KV_OPEN_TAG) == len(out), (blob.count(_KV_OPEN_TAG), out)
    return out


def test_A9_hld_kv類別名在樣式表裡_所以舊那個條件恆真():
    """**2026-09-24 稽核必修 A9 的釘樁** —— 把「為什麼舊條件是死的」變成可執行的證據。

    ⚠️ **這一條沒有會讓它轉紅的突變，理由據實寫明（不寫「未複驗」）**：
    舊條件 `"hld-kv" in blob` 是**冗餘**，不是**錯的** —— 真正在分辨的一直是
    `marker in blob`（逐檔互異的單位數字串）。把修復整個還原之後，
    `_expanded_fields()` 在本頁現有的 fixtures 上**回傳一模一樣的結果**，
    所以任何突變都紅不起來。**本組實跑確認過**（影子樹，A9 突變 exit=0、零紅燈）。
    **這正是它當初能一直躺著沒被發現的原因。**

    ⇒ 這一條守的是**那兩個讓舊條件變冗餘的事實**，而不是行為：
    類別名出現在樣式表裡（左半恆真）、開標籤不出現在樣式表裡（新的那個真的分得開）。
    **若哪天 `page.py` 的樣式或標記改到讓這兩個事實不成立，這一條會紅**，
    那時 `_expanded_fields()` 的前提就要重新檢查。
    """
    at = _run("full")
    styles = [e.value for e in at.markdown if "<style>" in e.value]
    assert len(styles) == 1, len(styles)
    # (1) 類別名在樣式表裡（＝舊條件的左半恆真）。
    assert "hld-kv" in styles[0]
    # (2) 但開標籤不在樣式表裡（＝新條件分得開）。
    assert _KV_OPEN_TAG not in styles[0]
    # (3) 零檔展開時，畫面上一個展開區塊也沒有。
    body = "\n".join(e.value for e in at.markdown if "<style>" not in e.value)
    assert _KV_OPEN_TAG not in body
    assert _expanded_fields(at) == []

    # (4) 兩個 token 的分辨力真的不同 —— 展開一檔之後逐一數給它看。
    model = logic.build_page_model(**fixtures.scenario("full"))
    code = logic.find_block(model, "HLD-5")["_items"][0]["_fund_code"]
    at.button(key=f"hld5_open_{code}").click().run()
    whole = "\n".join(e.value for e in at.markdown)
    assert whole.count(_KV_OPEN_TAG) == 1, whole.count(_KV_OPEN_TAG)
    assert whole.count("hld-kv") > 1, whole.count("hld-kv")   # 樣式表那幾筆把它灌爆
    assert _expanded_fields(at) == [code]


def test_HLD5是純文字列表_不巢狀_不自動展開_也沒有死鈕():
    """A4：`44` :707／§5.4「**展開區不巢狀第二層**」＋ :119／:128「**不自動展開**」
    ＋ :2420「**一枚按了不動的按鈕，比沒有按鈕更誤導**」。

    上一輪先是在塊層 expander 裡面又開一層（一檔一枚）、且第一檔初次載入就展開；
    改成 `展開` 類按鈕之後又留下一枚**按了不動的鈕**（`open_fund` 沒有任何呼叫端會傳值）。
    本輪退成純文字列表。既有的 `test_層三層四用expander且預設收合` 只驗塊層旗標與
    原始碼字串，**上述三件全部零覆蓋**。

    ⚠️ **2026-09-23 客戶裁示第 4 件之後，「沒有死鈕」那一段改寫（有意識的政策變更，
    不是漏刪；日期 2026-09-23；決策者：客戶）**：逐檔那一枚 `展開` 鈕**回來了**，
    但它**不再是死鈕** —— `page.py` 已把 `st.session_state` 接上去，按下去真的展開。
    ~~舊表述：`assert not [k for k in item if "button" in k]`（逐檔不得帶任何按鈕）~~
    **舊表述在寫下當時為真**：那一輪那枚鈕確實按了不動，而 `44` :2420 逐字
    「一枚按了不動的按鈕，比沒有按鈕更誤導」——拿掉它是對的。
    **被權衡掉的是它的前提**：它把「鈕是死的」釘成「不准有鈕」，
    而 `44` HLD-5 規則欄逐字要的正是「**點一檔展開一檔**」—— 沒有鈕就點不動。
    **現在釘的是「鈕必須是活的」**：真的按下去、畫面真的變（見下面那一條）。
    """
    at = _run("full")
    labels = [element.label for element in at.expander]
    model = logic.build_page_model(**fixtures.scenario("full"))
    expected = {
        f"{b['code']}　{b['title']}　—　{b['summary_text']}"
        for b in logic.all_blocks(model)
        if b["code"] in ("HLD-4", "HLD-5", "HLD-6", "HLD-7", "HLD-8")
    }
    # 不巢狀：畫面上的 expander 剛好是那五塊，沒有一枚是某一檔的標題。
    assert set(labels) == expected and len(labels) == 5, labels
    block = logic.find_block(model, "HLD-5")
    items = block["_items"]
    for item in items:
        assert item["head_text"] not in labels, item["head_text"]
    # 不自動展開。
    assert [b["code"] for b in logic.all_blocks(model) if b["_default_open"]] == [
        "HLD-0", "HLD-1", "HLD-2", "HLD-3"
    ]
    assert sum(1 for i in items if i["_open"]) == 0, "初次載入不得有任何一檔自己打開"
    # 塊層仍然零按鈕（`44` :707 空狀態欄一個按鈕也沒寫）。
    assert block["buttons"] == [], block["buttons"]
    # 逐檔那一枚是 `44` 5.3 八類裡的 `展開`，初次載入全部可用（沒有一檔是開的）。
    assert items, "一檔也沒有 —— 這一條會變成空掃"
    for item in items:
        assert item["_button"]["_action_kind"] == "展開", item["_button"]
        assert item["_button"]["_enabled"] is True, item["_button"]
    # 逐檔標題仍然畫得出來（否則這一條會退化成只驗「什麼都沒有」）。
    blob = "\n".join(_rendered(at))
    for item in items:
        assert item["head_text"] in blob, item["head_text"]


def test_HLD5那枚展開鈕是活的_按下去真的展開一檔():
    """A4 續：客戶 2026-09-23 裁示第 4 件 ——「接 session_state，讓單檔展開真的可點」。

    **這一條是第 4 件的正控**：把 `page.py` 的 `on_click=_click_open` 拿掉，
    按下去 session_state 不會變，展開中的檔數恆為 0，本條轉紅。
    """
    at = _run("full")
    model = logic.build_page_model(**fixtures.scenario("full"))
    codes = [i["_fund_code"] for i in logic.find_block(model, "HLD-5")["_items"]]
    assert len(codes) >= 2, "少於兩檔就驗不到「展開第二檔時第一檔自動收合」"

    # 初次載入：零檔展開（`44` :119／:128／:2315）。
    assert not any(_expanded_fields(at)), "初次載入就有一檔展開了"

    # 點第一檔 → 只有它展開。
    at.button(key=f"hld5_open_{codes[0]}").click().run()
    assert at.session_state[logic.HLD5_OPEN_KEY] == codes[0]
    assert _expanded_fields(at) == [codes[0]], _expanded_fields(at)
    # `44` 5.3：展開中的那一檔，它的鈕停用而且**不隱藏**。
    assert at.button(key=f"hld5_open_{codes[0]}").disabled is True

    # 點第二檔 → 第一檔自動收合，同時處於展開狀態的檔數為 1（`44` :711 判準逐字）。
    at.button(key=f"hld5_open_{codes[1]}").click().run()
    assert _expanded_fields(at) == [codes[1]], _expanded_fields(at)
    assert at.button(key=f"hld5_open_{codes[0]}").disabled is False


def test_HLD5展開之後仍然不巢狀第二層():
    """`44` :707／§5.4 逐字「**展開區不巢狀第二層**」—— 展開之後也不准多一枚 expander。"""
    at = _run("full")
    before = len(at.expander)
    model = logic.build_page_model(**fixtures.scenario("full"))
    code = logic.find_block(model, "HLD-5")["_items"][0]["_fund_code"]
    at.button(key=f"hld5_open_{code}").click().run()
    assert before == 5, before
    assert len(at.expander) == before, [e.label for e in at.expander]


def test_第5件_emptyfail情境的紅燈畫面真的畫得出來():
    """**客戶 2026-09-23 的要求，由總管轉述：「第 5 項改紅後要補 fixture，
    讓使用者看得到紅燈畫面。」**（⚠️ **本組手上沒有原始對話**，這一句是總管給的；
    依 `44` :2347 的教訓，**不在句尾標「逐字」** —— 轉述一次、標成逐字一次，
    兩步各自都小，合起來就是替客戶造話。原本這裡寫的是「客戶…逐字」，2026-09-24 改掉。）

    這一條跑的是真的 `AppTest`，驗的是**畫面**（燈色的色碼與文案），不是模型旗標。
    ⚠️ 拿掉修復（把 `conclusion_light` 的 `not has_holdings` 移回 `STATE_ERROR` 前面）
    本條轉紅：燈會回到灰，而畫面上會寫「尚未建立任何持倉」當主文案。
    """
    at = _run("emptyfail")
    lamp = logic.find_block(
        logic.build_page_model(**fixtures.scenario("emptyfail")), "HLD-0"
    )
    blob = "\n".join(_rendered(at))
    # 畫面上真的畫出紅色（色碼從 theme 取，本檔不寫色碼字面值）。
    red = theme.tone_hex("紅")
    lamp_html = [m.value for m in at.markdown if 'class="hld-lamp"' in m.value]
    assert len(lamp_html) == 1, len(lamp_html)
    assert f"--hld-tone:{red}" in lamp_html[0], lamp_html[0][:400]
    # 文案逐字。
    assert lamp["text"] in lamp_html[0]
    assert "有一塊取數失敗，這一頁的數字先不要照著讀" in lamp_html[0]
    # 失敗的那一塊被點名，而且空持倉那一句沒有被吞掉。
    assert "配息與本金卡：取數失敗。" in blob
    assert logic.TEXT_NO_HOLDING in blob
    # ⛔ 反向：這一態的畫面不得把主文案寫成「尚未建立任何持倉」（那就是被改掉的那個謊）。
    assert logic.TEXT_NO_HOLDING not in lamp_html[0], lamp_html[0][:400]
    # 情境標籤也畫出來了（證明 `?scenario=emptyfail` 真的被吃進去，不是退回預設）。
    assert fixtures.SCENARIO_LABELS["emptyfail"] in blob


def test_第5件_同一支渲染在empty情境下仍然是灰():
    """⛔ 反向控制：只有「空持倉 ＋ 有一塊失敗」改紅，單純空持倉照舊是灰。"""
    at = _run("empty")
    lamp_html = [m.value for m in at.markdown if 'class="hld-lamp"' in m.value]
    assert len(lamp_html) == 1
    assert f"--hld-tone:{theme.tone_hex('灰')}" in lamp_html[0]
    assert logic.TEXT_NO_HOLDING in lamp_html[0]


def test_A11_展開之後在同一個session內回不到零檔():
    """**2026-09-24 稽核必修 A11 的釘樁** —— 本組曾把一條不存在的出口寫成既有的出口。

    `logic.open_fund_after_click` 的註解原本說「回到零檔的路是 `44` :120
    『展開狀態不跨頁保留；離開再回來，回到預設』」。
    **那一句引得沒錯，錯在把它當成本原型已經有的路**：`st.session_state`
    是同一個 session 內持久的，而本原型只有一頁，`44` :120 講的「跨頁」在這裡不發生。

    這一條把**現況**釘住（不是把它說成對的）：展開之後切情境再切回來，那一檔仍然是開的。
    ⚠️ 要不要給一條收合的路，待客戶裁決；真的給了，這一條要跟著改。
    """
    at = _run("full")
    model = logic.build_page_model(**fixtures.scenario("full"))
    code = logic.find_block(model, "HLD-5")["_items"][0]["_fund_code"]
    at.button(key=f"hld5_open_{code}").click().run()
    assert at.session_state[logic.HLD5_OPEN_KEY] == code

    at.query_params["scenario"] = "empty"
    at.run()
    assert at.session_state[logic.HLD5_OPEN_KEY] == code, "切到別的情境就被清掉了？"

    at.query_params["scenario"] = "full"
    at.run()
    assert at.session_state[logic.HLD5_OPEN_KEY] == code
    assert at.button(key=f"hld5_open_{code}").disabled is True
    assert _expanded_fields(at) == [code]
