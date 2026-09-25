# -*- coding: utf-8 -*-
"""標的探索（EXP）渲染層測試。

需要 streamlit；本環境的系統 python3 匯入不到 streamlit，故缺 streamlit 時整檔 skip。
要跑起來：`PYTHONPATH=<裝有 streamlit 的目錄> pytest tests/ui_v2/ -q --noconftest`

⚠️ **本檔的存在理由，寫在最前面**：streamlit 對每一個路由都回同一份靜態殼，
   **單看 HTTP 200 證明不了頁面有跑**。本檔用 `AppTest` 把每一個情境的腳本**真的執行一次**，
   看 `at.exception` 與**實際渲染出來的元素**。
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

from ui_v2.exp import fixtures, logic, page, theme  # noqa: E402

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_APP = _ROOT / "ui_v2" / "app_exp.py"


def _run_raw(raw_scenario):
    """直接把一個**可能不合法**的情境名塞進查詢參數（`_run` 只收合法名字）。"""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(_APP), default_timeout=120)
    at.query_params["scenario"] = raw_scenario
    at.run()
    return at


def _run(scenario="full", *, save_failed=False):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(_APP), default_timeout=120)
    at.query_params["scenario"] = scenario
    if save_failed:
        at.query_params["savefail"] = "1"
    at.run()
    return at


def _rendered(at):
    """渲染出來的畫面字串 —— 權威檢查掃的是這個，不是原始碼。

    ⚠️ **展開區的標題列也是畫面文字**；勾選框與下拉的標籤、選項也是。
    姊妹頁第一版這支只收 markdown／caption／button，於是層 3 與層 4 整片掃不到 ——
    紅線字表掃描會跟著瞎掉一半。**寧可多抓，不可漏抓。**
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
    for element in at.checkbox:
        out.append(element.label)
    for element in at.text_input:
        out.append(element.label)
        if element.placeholder:
            out.append(element.placeholder)
        if element.value:
            out.append(str(element.value))
    for element in at.selectbox:
        out.append(element.label)
        out.extend(str(option) for option in element.options)
    for group in (at.title, at.text, at.error, at.warning, at.info, at.success):
        for element in group:
            out.append(element.value)
    return out


def _every_case():
    for name in fixtures.ALL_SCENARIO_NAMES:
        for save_failed in fixtures.SAVE_FAIL_CHOICES:
            yield name, save_failed


def _lamp_text(at) -> str:
    """結論列那一行**文案本身**，不含它旁邊的塊代號。

    ⚠️ 用 `class="…"` 比對，不是用類名比對 —— `<style>` 那一塊裡也有 `.exp-lamp-text`。
    ⚠️ 而且只取那個 span 的內容：整塊 markdown 裡還有「EXP-0」，
       拿整塊去驗「文案裡沒有 0」會被那個 `0` 推翻（本輪實測踩過）。
    """
    hits = []
    for element in at.markdown:
        for match in re.finditer(r'class="exp-lamp-text">(.*?)</span>', element.value):
            hits.append(match.group(1))
    assert len(hits) == 1, hits
    return hits[0]


# ═════════════════════ 一、分離 ═════════════════════


def test_page只呼叫logic與fixtures與theme_自己不做判定():
    source = pathlib.Path(page.__file__).read_text(encoding="utf-8")
    for banned in (
        "STATE_OK =",
        "def columns_for_width",
        "def worst_state",
        "def conclusion_light",
        "def apply_rules",
        "def _compare",
        "def rule_is_effective",
        "COMPARE_LIMIT =",
        "def toggle_checked",
    ):
        assert banned not in source, banned


def _page_display_literals():
    """`page.py` 裡**會上畫面**的字串常數。

    ⚠️ 排除 docstring（那是給讀的人看的，不是畫面文字）——
    不排除的話，一句在講「不要寫那個字面」的註解會把自己抓進來。
    """
    import ast

    tree = ast.parse(pathlib.Path(page.__file__).read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docstrings.add(id(body[0].value))
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and id(node) not in docstrings
    }


def test_page沒有把任何一句44文案寫成字面值():
    """⛔ **畫面層不准自己拿著 `44` 的文案。**

    `44` 各塊的文案是規格；它只准從 `logic` 的常數經模型流到畫面。
    一句被複製到 `page.py` 的文案 ＝ **同一句話有兩份來源**，
    改了其中一份另一份不會有任何反應（本 repo 的憲法把這個形狀記成「同一個事實兩個真相源」）。

    ⚠️ **射程誠實**：本條管的是 `logic.TEXT_*` 那一族（`44` 各塊寫出字面的那些）。
    版面標籤（「層 1　結論」之類）**不在射程內** —— 那是頁面骨架，`44` 沒有給字面。
    """
    literals = _page_display_literals()
    assert literals, "一個字串常數也沒抽到 —— 這一條會變成空掃"
    texts = {name: getattr(logic, name) for name in dir(logic) if name.startswith("TEXT_")}
    assert len(texts) >= 15, len(texts)
    # ⛔ **2026-09-24 突變測試抓到的洞：這裡本來有一張兩筆的豁免表。**
    #    豁免的理由是「那兩個是頁面自己的標籤、由 `page` 具名引用」——
    #    **但「具名引用」正好表示它們不會以字面值出現**，所以那張豁免表根本不必要，
    #    而它一存在就開了一個洞：把那兩句之一複製成字面值，這條守衛不會叫。
    #    **實測**：把 `block["condition_caption"]` 換成字面值 → 157 條全綠存活。
    #    ⇒ **豁免表整張刪掉。** 一張沒有必要的豁免表，就是一個沒有人看著的缺口。
    leaked = {
        name: value
        for name, value in texts.items()
        if any(value in literal for literal in literals)
    }
    assert leaked == {}, leaked
    # 反空掃 ＋ 負控：這條守衛真的認得出洩漏。
    assert any(logic.TEXT_NO_CONDITION in l for l in {"x" + logic.TEXT_NO_CONDITION + "y"})


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
        "socket",
        "ui_v2.mkt",
        "ui_v2.hld",
    ):
        assert banned not in source, banned


def test_進入點沒有import舊repo模組():
    source = _APP.read_text(encoding="utf-8")
    for banned in ("from ui.", "from services.", "from repositories.",
                   "from shared.", "from infra.", "import fund_fetcher"):
        assert banned not in source, banned


def test_page一個色碼字面值都沒有寫():
    """⛔ **色碼只准從 `theme` 取** —— 那一份每一組都算過對比。

    一個寫死在 `page.py` 的色碼，結構上不會被 `CONTRAST_PAIRS` 檢查到。
    """
    source = pathlib.Path(page.__file__).read_text(encoding="utf-8")
    hits = re.findall(r"#[0-9a-fA-F]{3,8}\b", source)
    assert hits == [], hits
    # 反空掃：`theme` 那一份確實有色碼，所以上面那條 regex 真的認得出色碼。
    theme_hits = re.findall(r"#[0-9a-fA-F]{6}\b", pathlib.Path(theme.__file__).read_text(encoding="utf-8"))
    assert len(theme_hits) >= 15, len(theme_hits)


def test_page用到的每一個色都是theme公開的常數():
    source = pathlib.Path(page.__file__).read_text(encoding="utf-8")
    used = set(re.findall(r"theme\.([A-Z_][A-Z0-9_]*)", source))
    used |= {"TONE_HEX"} if "tone_hex" in source else set()
    assert used, "一個 theme 常數也沒用到 —— 這一條會變成空掃"
    for name in used:
        assert hasattr(theme, name), name


# ═════════════════════ 二、真的跑起來（不是 HTTP 200） ═════════════════════


def test_每一個情境乘存檔失敗開關都真的渲染過而且沒有例外():
    """⛔ **這是本檔最承重的一條。**

    每一種情境 × 兩種存檔結果，全部真的跑一次腳本。
    **這個數不寫死** —— 寫死之後新增一個情境要改兩個地方，而漏改的那一次不會紅。
    任何一次丟例外就是紅燈（§1 Fail Loud：不吞例外）。
    """
    ran = 0
    for name, save_failed in _every_case():
        at = _run(name, save_failed=save_failed)
        assert not at.exception, (name, save_failed, [e.value for e in at.exception])
        # **真的有東西畫出來**，不是一個空殼。
        assert len(at.markdown) >= 10, (name, save_failed, len(at.markdown))
        ran += 1
    assert ran == len(fixtures.ALL_SCENARIO_NAMES) * 2, ran


def test_情境閘門認得的名字就是fixtures那一份():
    """⛔ 一個進得了 `fixtures.scenario()`、卻進不了閘門的情境 ＝ 做出來沒有人看得見。"""
    source = pathlib.Path(page.__file__).read_text(encoding="utf-8")
    assert "fixtures.ALL_SCENARIO_NAMES" in source
    # 亂給一個名字會落回第一個情境，不會炸、也不會畫出一個半成品。
    at = _run("這個情境不存在")
    assert not at.exception
    joined = "".join(_rendered(at))
    assert fixtures.SCENARIO_LABELS[fixtures.ALL_SCENARIO_NAMES[0]] in joined


def test_進入點docstring列的情境集合等於fixtures那一份():
    """⛔ 一份會漂移的清單寫在 docstring 裡，下一個人會照它去試不存在的情境。"""
    doc = _APP.read_text(encoding="utf-8")
    body = doc.split("`?scenario=")[1].split("`")[0]
    listed = {n.strip() for n in body.replace("\n", "").split("|") if n.strip()}
    assert listed == set(fixtures.ALL_SCENARIO_NAMES), (
        listed ^ set(fixtures.ALL_SCENARIO_NAMES)
    )


def test_八塊的代號與塊名都畫在畫面上():
    for name, save_failed in _every_case():
        joined = "".join(_rendered(_run(name, save_failed=save_failed)))
        for code, title in logic.BLOCK_TITLES.items():
            assert code in joined, (name, save_failed, code)
            assert title in joined, (name, save_failed, title)


def test_層三層四用expander而且預設收合():
    at = _run("full")
    labels = [e.label for e in at.expander]
    assert len(labels) == 4, labels
    for code in ("EXP-4", "EXP-5", "EXP-6", "EXP-7"):
        assert any(code in label for label in labels), code
    model = logic.build_page_model(fixtures.dataset_full())
    for code in ("EXP-4", "EXP-5", "EXP-6", "EXP-7"):
        assert logic.find_block(model, code)["_default_open"] is False


def test_畫面的斷點與logic同一個真相源_不寫死數字():
    """⛔ CSS 裡那幾個寬度是從 `logic` 的純函式掃出來的，不是打上去的。

    一個寫死在 CSS 裡的斷點，`44` 改值時不會有任何東西轉紅。
    """
    import re

    css = page._grid_css()
    widths = {int(w) for w in re.findall(r"(?:min|max)-width:\s*(\d+)px", css)}
    assert widths, "一個斷點也沒抽到 —— 這一條會變成空掃"
    # 每一個出現在 CSS 裡的寬度，都要是 logic 那幾支函式自己的邊界。
    layer_edges = {
        width
        for layer in (2, 3)
        for width in range(2, 2000)
        if logic.layer_columns(layer, width) != logic.layer_columns(layer, width - 1)
    }
    stack_edge = max(w for w in range(1, 2000) if logic.compare_stacks(w))
    assert widths <= (layer_edges | {stack_edge}), widths - (layer_edges | {stack_edge})
    # `44` 廢棄的那兩個值一個也不准出現。
    assert 1024 not in widths and 640 not in widths, widths
    # 原始碼裡也不准把它們打成字面值。
    source = pathlib.Path(page.__file__).read_text(encoding="utf-8")
    for dead in ("1024px", "640px", "768px", "1280px"):
        assert dead not in source, dead


def test_層二的三張核心卡畫在同一列的三個欄位裡():
    source = pathlib.Path(page.__file__).read_text(encoding="utf-8")
    assert "st.columns(3)" in source
    assert 'logic.codes_in_layer(model, 2)' in source


# ═════════════════════ 三、紅線（掃實際渲染出來的字串） ═════════════════════


def test_渲染出來的文字零方向詞零箭頭():
    for name, save_failed in _every_case():
        strings = _rendered(_run(name, save_failed=save_failed))
        assert strings, (name, save_failed, "一句畫面文字也沒收到 —— 這一條會變成空掃")
        assert logic.scan_forbidden(strings) == {}, (name, save_failed)


def test_渲染出來的按鈕標籤零禁詞():
    for name, save_failed in _every_case():
        at = _run(name, save_failed=save_failed)
        labels = [b.label for b in at.button]
        assert labels, (name, save_failed, "一顆按鈕也沒有 —— 這一條會變成空掃")
        for label in labels:
            for word in logic.FORBIDDEN_BUTTON_WORDS:
                assert word not in label, (name, label, word)


def test_首次開啟那個情境沒有任何一個輸入欄帶非空的預設值():
    """`44` 1.1 節判準逐字第二分句。"""
    at = _run("nocond")
    assert not at.exception
    # ⛔ **2026-09-24 就地更正：這裡原本是 `for element in at.text_input:` 一個空迴圈。**
    #    **實測 `nocond` 的 `at.text_input` 是 0 個** —— 那一圈從來沒有跑過，
    #    而 docstring 說它在驗 44 判準第二分句。**同檔其他迴圈都有反空掃前置，唯獨這一條沒有。**
    #    首次開啟本來就一列條件也沒有 ⇒ **正確的斷言是「一個輸入欄也沒有」，不是「每個都空」**。
    assert len(at.text_input) == 0, [e.label for e in at.text_input]
    # 勾選框有 5 個（`EXP-4` 的欄位清單），每一個都必須是未勾的。
    assert len(at.checkbox) == len(logic.COLUMN_ORDER), [c.label for c in at.checkbox]
    for element in at.checkbox:
        assert element.value is False, element.label
    # 排序下拉不預先選定任何一欄。
    assert len(at.selectbox) == 1, len(at.selectbox)
    assert at.selectbox[0].value == logic.TEXT_NO_SORT
    # 對照組：有條件的情境**真的有**輸入欄（否則上面那條 `== 0` 會變成恆真的空話）。
    other = _run("full")
    assert len(other.text_input) > 0, "全齊那一組也沒有輸入欄 —— 上面那條分不出差別"


# ═════════════════════ 四、勾選框真的是兩組、而且真的可按 ═════════════════════


def test_每一列真的畫出兩組勾選框():
    """`44` `EXP-2` 判準第三分句 —— **驗的是畫出來的元件，不是模型。**"""
    at = _run("full")
    labels = [c.label for c in at.checkbox]
    rows = len(logic.find_block(logic.build_page_model(**_params("full")), "EXP-2")["_rows"])
    assert labels.count("對照") == rows, (labels, rows)
    assert labels.count("觀察清單") == rows, (labels, rows)
    # 加上 `EXP-4` 的五個欄位勾選框。
    assert len(at.checkbox) == rows * 2 + len(logic.COLUMN_ORDER)


def _params(name, *, save_failed=False):
    params = dict(fixtures.scenario_with(name, save_failed=save_failed))
    dataset = params.pop("dataset")
    return {"dataset": dataset, **params}


def test_對照那一組勾滿三檔之後第四個框是停用的_而同列觀察清單仍可按():
    """`44` `EXP-3` 判準第一分句 —— **驗的是畫出來的元件的 `disabled`。**"""
    at = _run("full")
    boxes = [c for c in at.checkbox if c.label in ("對照", "觀察清單")]
    compare = [c for c in boxes if c.label == "對照"]
    watch = [c for c in boxes if c.label == "觀察清單"]
    assert len(compare) == len(watch) >= 4
    assert [c.disabled for c in compare] == [False, False, False, True, True], [
        c.disabled for c in compare
    ]
    assert not any(c.disabled for c in watch), [c.disabled for c in watch]


def test_勾選框真的可按_按下去之後模型跟著變():
    """⛔ **一枚按了不動的勾選框比沒有勾選框更誤導。**

    這一條真的去按第四列的「觀察清單」，然後看 `EXP-5` 有沒有把它算進去。
    """
    at = _run("full")
    watch = [c for c in at.checkbox if c.label == "觀察清單"]
    assert len(watch) >= 5
    assert [c.value for c in watch] == [False, True, False, True, False], [c.value for c in watch]
    target = watch[4]  # 第五列，原本沒有勾
    target.check().run()
    assert not at.exception, [e.value for e in at.exception]
    joined = "".join(_rendered(at))
    # ⛔ **原本勾好的那兩檔不准在按下第三個的時候消失。**
    #    本輪實測踩過這個坑：`_toggle()` 從 `st.session_state` 讀舊值，
    #    而那個鍵在第一次互動之前還不存在 → 從空集合開始 → 兩檔變一檔。
    assert "勾起 3" in joined, [e.label for e in at.expander]


def _compare_column_count(at) -> int:
    """`EXP-3` 實際畫出來的欄數。

    ⚠️ **不看展開區的標題列** —— `EXP-3` 在層 2，是一張卡不是展開區，它的摘要不會上畫面。
    （本輪踩過：拿 `勾起 N` 那種摘要字串去驗層 2 的卡，永遠找不到。）
    """
    joined = "".join(m.value for m in at.markdown)
    return joined.count('class="exp-cmp-head"')


def test_取消勾選也真的生效():
    at = _run("full")
    compare = [c for c in at.checkbox if c.label == "對照"]
    assert [c.value for c in compare] == [True, True, True, False, False]
    assert _compare_column_count(at) == 3
    compare[0].uncheck().run()
    assert not at.exception, [e.value for e in at.exception]
    assert _compare_column_count(at) == 2
    # ⛔ 另外兩檔沒有跟著消失（那正是上一條記的那個 session 未種入的病）。
    assert [c.value for c in at.checkbox if c.label == "對照"] == [False, True, True, False, False]


def test_切到另一個情境時上一個情境的勾選不會跟過去():
    """⛔ 勾選狀態的 session 鍵帶情境名；不帶的話 `nocond` 會帶著三檔勾選進來。"""
    assert logic.checked_key(logic.GROUP_COMPARE, "full") != logic.checked_key(
        logic.GROUP_COMPARE, "nocond"
    )
    at = _run("nocond")
    assert all(c.value is False for c in at.checkbox), [c.label for c in at.checkbox if c.value]


# ═════════════════════ 五、各塊畫出來的東西 ═════════════════════


def test_EXP0的燈三色都畫得出來_而且都帶圖示與文字():
    seen = {}
    for name, save_failed in _every_case():
        at = _run(name, save_failed=save_failed)
        block = logic.find_block(logic.build_page_model(save_failed=save_failed, **_params(name, save_failed=save_failed)), "EXP-0")
        joined = "".join(_rendered(at))
        assert f'狀態：{block["state_word"]}' in joined, (name, block["state_word"])
        assert block["glyph"] in joined, (name, block["glyph"])
        seen[block["_tone_override"]] = name
    assert set(seen) == {"灰", "黃", "紅"}, seen


def test_零檔符合時畫面真的列出生效條件列():
    at = _run("zero")
    joined = "".join(_rendered(at))
    assert logic.TEXT_NO_MATCH in joined
    assert "目前生效的條件列" in joined
    for rule in fixtures.RULES_ZERO:
        assert logic.rule_text(rule) in joined, rule


def test_條件未設時畫面寫尚未設定條件而不是0檔():
    """`44` `EXP-0` 判準第二分句。**母體限定在結論列那一行**，不是全頁 ——

    全頁還有別的塊會誠實地寫「目前有 0 檔」（例如觀察清單），那不是本條在管的事。
    """
    at = _run("nocond")
    joined = "".join(_rendered(at))
    assert logic.TEXT_NO_CONDITION in joined
    assert logic.TEXT_NO_MATCH not in joined
    text = _lamp_text(at)
    assert text == logic.TEXT_NO_CONDITION, text
    assert "0" not in text, text


def test_數值未填那一列的列尾字面畫得出來():
    joined = "".join(_rendered(_run("blankvalue")))
    assert logic.TEXT_BLANK_VALUE in joined
    assert logic.TEXT_NOT_EFFECTIVE in joined


def test_缺淨值那一檔仍然在清單上而且格子是空方塊():
    joined = "".join(_rendered(_run("full")))
    assert fixtures.NO_NAV_FUND in joined
    assert "⬜" in joined


def test_兩檔不同幣別並排時欄頭各自印出幣別():
    joined = "".join(_rendered(_run("mixedccy")))
    assert "JPY" in joined and "TWD" in joined
    for word in ("合計", "平均", "差額"):
        # 說明區那一句是在複述 `44` 的禁令，不算；其餘不得出現。
        assert joined.count(word) <= 1, word


def test_取數失敗的訊息每塊每張失敗的表各印一次_外加EXP0轉述一次():
    """⛔ **2026-09-24 第二輪稽核抓到：這一條原本叫「一塊只印一次」，與它自己的斷言相反。**

    它的期望表寫 `"twofail": (3, 2)`、`want = 3*2 + 2 = 8` —— 也就是
    **一塊有兩張表失敗時就印兩行**。**斷言與數字都是對的，錯的是名字。**
    ⛔ **這是本輪第二隻同型的**：同一輪我在 `logic.py` 親手診斷並改好了它的孿生兄弟
    （`source_error_lines()` 那條，已改名為 `test_兩張表同時失敗時兩行各自帶自己的表名`），
    **同一個診斷、同一輪，改了一處、漏了另一處。**
    真正的不變量是：**每一塊 × 每一張失敗的表各一行，再加 `EXP-0` 轉述一次。**

    ⛔ **2026-09-24 本組自己重跑抓到的（量測日 2026-09-24，修復前）：同一句訊息被畫了 11／17／10 次。**

    兩個成因，一起修掉：
    (a) `page._fetch_fail_lines` 用 `if logic.ERR_TEXT in line` **從 `detail_lines` 裡挑** ——
        那是**畫面層在做分類**，而且挑出來畫完紅框之後 `_lines(detail_lines)` 又原封再畫一次；
    (b) `upstream_failure_note()` 與 `source_error_lines()` **各放了一份同樣的訊息**
        （一份進空狀態、一份進紅框）。
    現在：取數失敗那一族有自己的 `fetch_fail_lines` 鍵，**一塊只有一個地方印**；
    `EXP-0` 那一份是 `44` 規則欄逐字要的「文案列出失敗的那一段」，不算重複。
    """
    expected = {
        # 情境: (出錯的塊數, 每塊幾張表失敗)
        "profilefail": (4, 1),          # EXP-2／EXP-3／EXP-6／EXP-7 各一
        "profilefail_picked": (4, 1),
        "navfail": (3, 1),              # EXP-7 的上游只有 fund_profile，不受 nav 影響
        "twofail": (3, 2),              # nav ＋ dividend 兩張
    }
    for name, (blocks, tables) in expected.items():
        at = _run(name)
        joined = "".join(_rendered(at))
        # 各塊自己印一次 ＋ `EXP-0` 轉述一次。
        want = blocks * tables + tables
        got = joined.count(fixtures.FETCH_FAIL_MESSAGE)
        assert got == want, (name, got, want)
    # 沒有失敗的情境一次也不印。
    assert "".join(_rendered(_run("full"))).count(fixtures.FETCH_FAIL_MESSAGE) == 0


def test_page不再用字串比對去挑失敗行():
    """⛔ 承上 (a)：畫面層不准分類模型內容。

    ⚠️ 用 AST 掃**真的程式碼**，不掃 docstring —— `_fetch_fail_lines` 的 docstring 裡
    就引著那一行舊寫法當反例，掃原始碼會被自己的註解推翻（本輪實測踩過）。
    """
    import ast

    tree = ast.parse(pathlib.Path(page.__file__).read_text(encoding="utf-8"))
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and any(isinstance(o, ast.In) for o in node.ops):
            text = ast.unparse(node)
            if "ERR_TEXT" in text or "取數失敗" in text:
                bad.append(text)
    assert bad == [], bad
    assert 'block.get("fetch_fail_lines"' in pathlib.Path(page.__file__).read_text(encoding="utf-8")


def test_結論燈的狀態標記在視覺上不是一枚徽章():
    """⛔ **2026-09-24 就地更正：`.exp-stword` 原本與 `.exp-badge` 在視覺上逐項相同。**

    （`inline-block`／`.68rem`／`border-radius:999px`／同樣的 padding／`1px solid`），
    而它的字面之一「取數失敗」**正是 `44` 5.2 那七個封閉字面值之一**、顏色也是 44 給它的紅
    —— 於是「本頁一枚狀態徽章也沒有掛」**只在模型的 `_kind` 記帳上成立，畫面上不成立**。

    ⚠️ **不能把它宣告成徽章**：它另外三個字面（條件未設／零檔符合／有檔符合）
    **不在**那七個之內，宣告成徽章當場違反 5.2 的封閉列舉。
    ⇒ 處置是「**讓它看起來不是**」。本條逐項釘住那個差別。
    """
    css = page._base_css()
    def rule(selector):
        body = css.split(selector + " {", 1)[1].split("}", 1)[0]
        return " ".join(body.split())
    stword, badge = rule(".exp-stword"), rule(".exp-badge")
    assert "border-radius: 999px" in badge, badge          # 徽章是藥丸形
    assert "border-radius: 999px" not in stword, stword    # 狀態標記不是
    assert "border: 1px solid" in badge, badge             # 徽章有一圈外框
    assert "border: 0" in stword, stword                   # 狀態標記沒有
    assert "border-left: 3px solid" in stword, stword      # 改成左側粗邊
    assert "border-left" not in badge, badge
    # ⚠️ 而且它的字面**確實**有一個落在那七個之內 —— 這一條不假裝那個重疊不存在。
    words = set()
    for name, save_failed in _every_case():
        words.add(logic.find_block(
            logic.build_page_model(save_failed=save_failed, **_params(name, save_failed=save_failed)),
            "EXP-0")["state_word"])
    overlap = words & set(logic.STATUS_BADGE_LITERALS)
    assert overlap == {"取數失敗"}, overlap


def test_取數失敗時訊息原文照印_不改寫成安撫語句():
    """`44` 4.4：`message` 存來源回傳的原始字串，不換成安撫語句，也不截斷。"""
    joined = "".join(_rendered(_run("profilefail")))
    assert fixtures.FETCH_FAIL_MESSAGE in joined
    assert logic.ERR_TEXT in joined
    for word in ("請稍後再試", "系統忙碌", "發生一些問題"):
        assert word not in joined, word


def test_存檔寫入失敗時三塊各出一個失敗框_而按鈕停用的那一塊不出():
    on = "".join(_rendered(_run("full", save_failed=True)))
    off = "".join(_rendered(_run("full", save_failed=False)))
    # `EXP-1`／`EXP-4`／`EXP-5` 各一個。**頁首那一行刻意不寫這個字面**，所以這個數是乾淨的。
    assert on.count(logic.TEXT_SAVE_FAILED) == 3, on.count(logic.TEXT_SAVE_FAILED)
    assert logic.TEXT_SAVE_FAILED not in off
    # `nowatch`：`EXP-5` 那一枚是停用的，所以只出兩個。
    disabled = "".join(_rendered(_run("nowatch", save_failed=True)))
    assert disabled.count(logic.TEXT_SAVE_FAILED) == 2, disabled.count(logic.TEXT_SAVE_FAILED)


def test_上游掛掉時畫面上不會出現查無此代碼那句假話():
    """⛔ **同一個代碼、兩種情形，畫面必須說不同的話。**"""
    failed = "".join(_rendered(_run("profilefail_picked")))
    assert fixtures.FETCH_FAIL_MESSAGE in failed
    assert logic.TEXT_NO_SUCH_FUND not in failed, "上游掛掉卻印了「查無此代碼」"
    assert logic.TEXT_NO_MATCH not in failed
    assert logic.TEXT_PICK_THREE not in failed
    # 對照組：真的查無那一檔時，那句話照舊印得出來。
    joined = "".join(_rendered(_run("unknownfund")))
    assert logic.TEXT_NO_SUCH_FUND in joined
    assert fixtures.FETCH_FAIL_MESSAGE not in joined


def test_查無此代碼那個畫面畫得出來():
    joined = "".join(_rendered(_run("unknownfund")))
    # `44` `EXP-6` 空狀態欄的文案逐字是「查無此 `fund_code`」——
    # 那是**欄位名**，不是值。值另外寫在說明區（不然使用者看不出它在查哪一檔）。
    assert logic.TEXT_NO_SUCH_FUND in joined
    assert fixtures.MISSING_FUND_CODE in joined, "說明區沒有寫出它在查哪一個代碼"


def test_EXP5按鈕停用時仍在畫面上而且帶得出停用原因():
    at = _run("nowatch")
    target = [b for b in at.button if b.label == logic.TEXT_ADD_WATCH]
    assert len(target) == 1, [b.label for b in at.button]
    assert target[0].disabled is True
    assert logic.TEXT_NO_PICK in "".join(_rendered(at))


def test_全頁一枚重新取數的按鈕都沒有():
    """⛔ `E-22` 登記：那枚鈕按了不能寫它缺的那兩張表。"""
    for name, save_failed in _every_case():
        labels = [b.label for b in _run(name, save_failed=save_failed).button]
        assert "重新取數" not in labels, (name, save_failed, labels)


def test_三張核心卡各掛一組來源與新鮮度的佔位徽章():
    """⛔ `E-21` 登記：`44` 的卡片參數是逐主值的，而這三張卡沒有「主值」。"""
    joined = "".join(_rendered(_run("full")))
    assert joined.count("〔來源層級〕") == 3, joined.count("〔來源層級〕")
    assert joined.count("〔新鮮度〕") == 3, joined.count("〔新鮮度〕")
    assert "G2†" in joined


# ═════════════════════ 六、名字集合 ═════════════════════

_LOAD_BEARING = (
    "test_每一個情境乘存檔失敗開關都真的渲染過而且沒有例外",
    "test_情境閘門認得的名字就是fixtures那一份",
    "test_進入點docstring列的情境集合等於fixtures那一份",
    "test_渲染出來的文字零方向詞零箭頭",
    "test_page一個色碼字面值都沒有寫",
    "test_勾選框真的可按_按下去之後模型跟著變",
    "test_對照那一組勾滿三檔之後第四個框是停用的_而同列觀察清單仍可按",
    "test_全頁一枚重新取數的按鈕都沒有",
    "test_上游掛掉時畫面上不會出現查無此代碼那句假話",
    "test_page沒有把任何一句44文案寫成字面值",
    "test_取數失敗的訊息每塊每張失敗的表各印一次_外加EXP0轉述一次",
    "test_page不再用字串比對去挑失敗行",
    "test_結論燈的狀態標記在視覺上不是一枚徽章",
)


def test_承重測試一條都不准無聲消失():
    """⛔ **「總數沒變」不是沒刪東西的證據。要比的是名字的集合。**"""
    here = {name for name in globals() if name.startswith("test_")}
    missing = [name for name in _LOAD_BEARING if name not in here]
    assert not missing, f"這幾條承重測試不見了：{missing}"
    assert len(here) >= 28, len(here)


def test_網址打錯情境名時退回預設而不是炸掉():
    """⛔ **2026-09-24 本組自查補上：這個退路當時沒有任何測試釘著。**

    `_pick_scenario()` 對不認得的情境名**安靜退回**清單第一個 —— 那是一次沉默的處理，
    而本頁別處一律 Fail Loud，所以它必須被釘住、也必須說得出為什麼可以沉默。
    **理由（也在 `page._pick_scenario` 就地登記）**：這一格挑的是「展示哪一份假資料」，
    **不編造任何數值**；資料層照舊大聲炸。
    本條把兩邊都驗：畫面不炸、退回預設，**而且** `fixtures.scenario()` 對同一個名字仍然 raise。
    """
    at = _run("不存在的情境")
    assert not at.exception, [str(e.value) for e in at.exception]
    joined = "\n".join(m.value for m in at.markdown)
    default_label = fixtures.SCENARIO_LABELS[fixtures.ALL_SCENARIO_NAMES[0]]
    assert default_label in joined, "打錯情境名應該看到預設情境的標籤"
    # 反面：換一個**真的存在**的情境，看到的就不是預設那一張 —— 否則上面那句等於恆真。
    other = fixtures.ALL_SCENARIO_NAMES[2]
    other_joined = "\n".join(m.value for m in _run(other).markdown)
    assert fixtures.SCENARIO_LABELS[other] in other_joined
    assert default_label not in other_joined
    # 資料層仍然大聲炸 —— 沉默只發生在挑情境這一格。
    with pytest.raises(KeyError):
        fixtures.scenario("不存在的情境")


def test_五項與草稿四項的差異真的畫在畫面上_不是只寫在註解():
    """⛔ **2026-09-24 第二輪稽核抓到：這一筆承諾「讓客戶看得到」，畫面上卻 0 字。**

    `logic.COLUMN_ORDER` 上方的登記自己寫著「**這個事實必須讓客戶看得到**」，
    而當時唯一釘它的斷言是 `assert "不是客戶裁的" in source` —— **斷言的是 Python 原始碼**。
    稽核掃 46 份模型、162 條畫面字串並真渲染覆驗：「四項」「AI 總管」「總管」「客戶」**全部 0 命中**。
    ⛔ 同一塊的 `E-07`／`E-17` 都寫上了畫面 —— **唯獨「客戶沒拍板過的視覺元件」這一筆停在註解層。**

    本條釘的是**畫面**：這句話要真的被渲染出來，而且要帶得出三個承重事實 ——
    **五項 vs 四項**、**這是一次視覺元件增加**、**授權來自總管的派工指定而非客戶裁示**。
    ⚠️ 本條不掃原始碼，只看渲染結果；把 `detail_lines` 那一句刪掉，本條轉紅。
    """
    shown = "".join(_rendered(_run("full")))
    assert "可選欄位四項" in shown, "草稿的四項這個事實沒有出現在畫面上"
    assert "五項" in shown
    assert "視覺元件增加" in shown
    assert "AI 總管，本輪派工指定" in shown
    assert "不是客戶裁示" in shown
    # 反面：這是本頁常態資訊，不是只有某一個情境才出現。
    for name in ("zero", "nocond", "profilefail"):
        other = "".join(_rendered(_run(name)))
        assert "可選欄位四項" in other, name


def test_排序下拉真的接上了_選了就重排而且說明列不再說假話():
    """⛔ **2026-09-24 第二輪稽核抓到：選了排序欄位之後，說明列仍印「未選排序欄位」。**

    那是**使用者操作之後畫面說的一句假話** —— 與本頁到處在防的那一類
    （「取數失敗卻說查無此代碼」）**同形**：畫面聲稱了一件與事實相反的事。
    現在排序下拉真的接上：選什麼就依什麼排，說明列跟著換，選回「不排序」再換回來。
    """
    at = _run("full")
    def caption(app):
        for m in app.markdown:
            if 'class="exp-sortcap"' in m.value and "<style>" not in m.value:
                return re.sub(r"<[^>]+>", "", m.value)
        return ""
    before = caption(at)
    assert "未選排序欄位" in before, before

    at.selectbox[0].select("ccy").run()
    after = caption(at)
    assert "依「ccy」排序" in after, after
    assert "未選排序欄位" not in after, "選了欄位之後還在說沒選 —— 就是那句假話"

    # 換一欄也要跟著換（否則可能只是被寫死成某一句）。
    at.selectbox[0].select("近 12 個月配息佔淨值比").run()
    assert "近 12 個月配息佔淨值比" in caption(at)

    # 選回「不排序」要真的回到原本那句。
    at.selectbox[0].select(logic.TEXT_NO_SORT).run()
    assert "未選排序欄位" in caption(at)


def test_排序下拉的每一個選項都對得回一個欄位():
    """⛔ 下拉的選項集合就是 `logic.column_for_label()` 的定義域；少一個對映就會靜默變成不排序。"""
    at = _run("full")
    options = at.selectbox[0].options
    assert options, "一個選項都沒有 —— 這一條會變成空掃"
    assert options[0] == logic.TEXT_NO_SORT
    assert logic.column_for_label(logic.TEXT_NO_SORT) is None
    for label in options[1:]:
        column = logic.column_for_label(label)
        assert column in logic.COLUMN_ORDER, (label, column)
    # 反面：不在選項裡的字**不會**被誤認成某一欄。
    assert logic.column_for_label("不存在的欄位名") is None


def test_欄位勾選框是唯讀的_而且畫面上說了為什麼():
    """⛔ **2026-09-24 第二輪稽核：`EXP-4` 五個勾選框沒接線，而畫面上一句說明都沒有。**

    本頁的處置是**唯讀 ＋ 畫面上寫明原因**，不是偷偷讓它按不動。
    ⚠️ **為什麼不接線（理由也寫在畫面上）**：接了就讓「取消勾基金名、其他仍勾著」
    變成走得到的狀態，而 `44` 只保障「全不勾」那一種，**沒有寫這一種算不算可接受**。
    ⚠️ **試過只鎖「基金名」那一格，行不通**：把它固定成已勾會讓 `nocond` 違反
    `44` 1.1 判準「首次開啟本頁卡片上沒有任何已勾選的選項」（實測當場紅燈）。
    """
    at = _run("full")
    boxes = [c for c in at.checkbox if c.key.startswith("exp4_col_")]
    assert len(boxes) == len(logic.COLUMN_ORDER), [c.key for c in boxes]
    assert all(c.disabled for c in boxes), [c.key for c in boxes if not c.disabled]
    # 對照：`EXP-2` 那一組**不是**全部唯讀（否則代表整頁被鎖死了）。
    exp2 = [c for c in at.checkbox if c.key.startswith("exp2_")]
    assert exp2 and not all(c.disabled for c in exp2)
    # 畫面上要說得出它是唯讀的、以及為什麼。
    shown = "".join(_rendered(at))
    assert "唯讀" in shown
    assert "全部不勾" in shown
    assert "待裁決" in shown


def test_44沒裁決的那個欄位狀態_在畫面上走不到():
    """⛔ **底線 (b)：「取消勾基金名、其他仍勾著」這個狀態不准變成走得到的。**

    本組登記過 `cols(("ccy",)) → ['ccy']`（基金名不顯示），而 `44` **沒有寫**那算不算可接受。
    本條從**畫面**驗它走不到：五個框都不可按 ⇒ 使用者改不出那個組合。
    ⚠️ 這一條不是驗 `logic`（`logic` 照舊能表達那個狀態，情境也還用得到它），
       驗的是**使用者到不到得了**。
    """
    for name in ("full", "nocond", "nocolumn"):
        at = _run(name)
        boxes = [c for c in at.checkbox if c.key.startswith("exp4_col_")]
        assert boxes, name
        assert all(c.disabled for c in boxes), (name, [c.key for c in boxes if not c.disabled])
    # `44` 保障的「全不勾」那一種照舊示範得出來。
    nocolumn = _run("nocolumn")
    assert all(
        not c.value for c in nocolumn.checkbox if c.key.startswith("exp4_col_")
    ), "nocolumn 情境應該五格都沒勾"


def test_情境名打錯時畫面上說了它退回哪一個():
    """⛔ **2026-09-24 第二輪稽核：閘門安靜退回，畫面上一個字都沒說。**

    實測 `?scenario=sortnvav`（打錯）與 `?scenario=full` **渲染逐字相同**，
    頁首還肯定地寫「情境 狀態 1｜全齊」——
    **使用者看到的是一個他沒要求的畫面，而畫面不承認這件事。**
    ⚠️ 這不違反 §1（沒有編造任何數值，資料層照舊 `raise KeyError`），
    但它與本輪第 6、7 條**同形**：**真相寫在註解裡，畫面上沒有。**
    """
    bad = _run_raw("sortnvav")
    shown = "".join(_rendered(bad))
    assert "查無此情境" in shown
    assert "sortnvav" in shown, "要說出使用者原本打的是什麼"
    assert fixtures.SCENARIO_LABELS[fixtures.ALL_SCENARIO_NAMES[0]] in shown, "要說出退回到哪一個"
    # 反面：名字正確時**不准**出現這一句（否則變成每頁都在喊退回）。
    good = "".join(_rendered(_run("full")))
    assert "查無此情境" not in good
