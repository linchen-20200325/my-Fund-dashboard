# -*- coding: utf-8 -*-
"""設定與診斷（SET）純邏輯測試。**不需要 streamlit**，系統直譯器跑得起來。

要跑起來：`pytest tests/ui_v2/test_set_logic.py -q --noconftest`
（`--noconftest` 是因為 repo 根的 `tests/conftest.py` 會 import 舊 repo 的取數層。）

⚠️ 每一條都寫出它在驗 `44` 的哪一行判準或哪一條規則。
   每一道守衛本輪都在 scratchpad 的副本上**真的把實作改壞跑過一次**（突變測試），
   結果記在本輪回報裡；本檔不寫那些數字（會漂）。
⚠️ 本檔**刻意不釘 `44` 的 md5**：另一條線同時在改 `44`（ALO-4 那一格），釘了會讓本頁的測試替別人的改動紅燈。
   本頁與 `44` 的一致性改由逐字引文守衛與規格快照守衛（對 `44` 現行文字重抽比對）把關。
"""

import ast
import copy
import pathlib
import re
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ui_v2.set import fixtures, logic, theme  # noqa: E402

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_D44 = _ROOT / "docs" / "v2" / "44_fund_ui_ssot.md"
_SET_DIR = _ROOT / "ui_v2" / "set"
_APP = _ROOT / "ui_v2" / "app_set.py"

# 本頁全部原始碼檔（逐字守衛、禁詞守衛、隔離守衛的母體都從這一份出發）。
_ALL_SOURCE_FILES = (
    _SET_DIR / "__init__.py",
    _SET_DIR / "fixtures.py",
    _SET_DIR / "logic.py",
    _SET_DIR / "theme.py",
    _SET_DIR / "page.py",
    _APP,
    # 2026-09-26：規格快照由 fixtures.py 搬到 spec.py（正式模式也要讀、而正式路徑不得 import fixtures），
    # 納入同一批守衛的母體。放在最後，`[:4]`（不 import streamlit 的那四個）不受影響。
    _SET_DIR / "spec.py",
    # 2026-09-26 回修（總管裁示）：正式模式三個檔一併納入禁詞、逐字、缺口登記等守衛的母體。
    _SET_DIR / "live.py",
    _SET_DIR / "source.py",
    _ROOT / "ui_v2" / "app_set_live.py",
)
# 正式路徑檔：依 tests/ui_v2/test_ui_v2_live_import_guard.py，只有 source.py 可以碰 services.v2_tables。
_LIVE_SOURCE = _SET_DIR / "source.py"


def _model(name="ok", *, save_failed=False):
    return logic.build_page_model(fixtures.scenario_with(name, save_failed=save_failed))


def _every_case():
    for name in fixtures.ALL_SCENARIO_NAMES:
        for save_failed in fixtures.SAVE_FAIL_CHOICES:
            yield name, save_failed


def _setting(dataset, key, value):
    for row in dataset["user_setting"]:
        if row["setting_key"] == key:
            row["setting_value"] = value
            row["updated_at"] = fixtures.UPDATED_AT if value is not None else None
            return dataset
    raise KeyError(key)


def _block(model, code):
    return logic.find_block(model, code)


def _live44():
    return re.sub(r"~~.*?~~", "", _D44.read_text(encoding="utf-8"), flags=re.DOTALL)


# ═════════════════════ 一、分離與隔離 ═════════════════════

_OLD_ROOTS = {"ui", "services", "repositories", "shared", "infra", "fund_fetcher"}
_NET_ROOTS = {"requests", "httpx", "urllib", "urllib3", "yfinance", "gspread", "feedparser", "socket", "subprocess"}
_SISTER_PAGES = {"mkt", "hld", "exp", "alo"}


def _module_of(path) -> str:
    parts = list(path.relative_to(_ROOT).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _import_targets(source: str, module: str, *, is_package=False):
    """AST 解析每一條 import，把相對寫法換算成絕對模組名，`from X import Y` 的 Y 也算成 `X.Y`。"""
    package = module if is_package else module.rpartition(".")[0]
    out = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append((alias.name, f"import {alias.name}"))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")
                base = base[: len(base) - (node.level - 1)]
                root = ".".join(base + ([node.module] if node.module else []))
            else:
                root = node.module or ""
            out.append((root, f"from {'.' * node.level}{node.module or ''} import ..."))
            for alias in node.names:
                out.append((f"{root}.{alias.name}", f"from {'.' * node.level}{node.module or ''} import {alias.name}"))
    return out


def _forbidden_import(target: str) -> bool:
    parts = target.split(".")
    if parts[0] in _OLD_ROOTS | _NET_ROOTS:
        return True
    return len(parts) >= 2 and parts[0] == "ui_v2" and parts[1] in _SISTER_PAGES


def test_六個檔都沒有import舊repo或網路或姊妹頁():
    """母體＝本頁全部原始碼檔（含 page.py 與 app_set.py；2026-09-26 起加 spec.py 與正式模式三檔，共十個）。
    AST 換算成絕對模組名再判。唯一例外：source.py 可以 import `services.v2_tables` 的模組（正式資料來源）。"""
    assert len(_ALL_SOURCE_FILES) == 10
    seen = 0
    for path in _ALL_SOURCE_FILES:
        source = path.read_text(encoding="utf-8")
        targets = _import_targets(source, _module_of(path), is_package=path.name == "__init__.py")
        seen += len(targets)
        bad = [raw for target, raw in targets if _forbidden_import(target)
               and not (path == _LIVE_SOURCE and (target == "services.v2_tables"
                                                  or target.startswith("services.v2_tables.")))]
        assert not bad, (path.name, bad)
    assert seen >= 10, seen


def test_logic與fixtures與theme與init都沒有import_streamlit():
    for path in _ALL_SOURCE_FILES[:4]:
        targets = _import_targets(path.read_text(encoding="utf-8"), _module_of(path), is_package=path.name == "__init__.py")
        assert not any(t.split(".")[0] == "streamlit" for t, _r in targets), path.name
        assert "import streamlit" not in path.read_text(encoding="utf-8"), path.name


def test_隔離掃描器本身會咬_負控():
    page_mod = "ui_v2.set.page"
    must_catch = (
        "from ui_v2 import alo",
        "from .. import exp",
        "from ..hld import logic",
        "from ..alo.logic import x",
        "import ui_v2.mkt",
        "from services.macro import x",
        "import requests",
        "import urllib.request",
        "from infra import proxy",
    )
    for line in must_catch:
        assert any(_forbidden_import(t) for t, _r in _import_targets(line + "\n", page_mod)), line
    for line in ("from . import fixtures, logic, theme", "import html", "from ui_v2.set import page", "import streamlit as st"):
        assert not any(_forbidden_import(t) for t, _r in _import_targets(line + "\n", page_mod)), line


def test_fixtures不import_logic_假資料不依賴判定層():
    source = (_SET_DIR / "fixtures.py").read_text(encoding="utf-8")
    targets = _import_targets(source, "ui_v2.set.fixtures")
    # 2026-09-26：唯一准的是規格快照 spec.py（純 tuple、零 import，不是判定層）；logic／page 照舊不准。
    assert not [t for t, _r in targets if t.startswith("ui_v2") and not t.startswith("ui_v2.set.spec")], targets
    spec_targets = _import_targets((_SET_DIR / "spec.py").read_text(encoding="utf-8"), "ui_v2.set.spec")
    assert spec_targets == [], spec_targets  # spec.py 本身零 import


# ═════════════════════ 二、逐字引文守衛 ═════════════════════

_QUOTE_CONNECTORS = set(" \t\r\n#：:是寫著引的為，,。－—-*~`＝=（(")
_MIN_VERIFIED_QUOTES = 5


def _strip_struck(text: str) -> str:
    return re.sub(r"~~.*?~~", "", text, flags=re.DOTALL)


def _flat(text: str) -> str:
    text = re.sub(r"\n\s*#\s*", "", text)
    text = text.replace("『", "「").replace("』", "」")
    return re.sub(r"\s+", "", re.sub(r"\*\*|~~|`|\*|_", "", text))


def _quotes_introduced_by_verbatim(text: str):
    out = []
    for match in re.finditer("逐字", text):
        j = match.end()
        while j < len(text) and j - match.end() <= 12 and text[j] in _QUOTE_CONNECTORS:
            j += 1
        if j >= len(text) or text[j] != "「":
            continue
        depth, k = 0, j
        while k < len(text):
            if text[k] == "「":
                depth += 1
            elif text[k] == "」":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        if k < len(text):
            out.append((match.start(), text[j + 1 : k]))
    return out


def _all_verbatim_quotes():
    out = []
    for path in _ALL_SOURCE_FILES:
        text = path.read_text(encoding="utf-8")
        for pos, quote in _quotes_introduced_by_verbatim(text):
            out.append((path.name, text[:pos].count("\n") + 1, quote))
    return out


def _check_quote(quote: str, d44: str) -> str:
    q = _flat(quote)
    if q in _flat(_strip_struck(d44)):
        return "live"
    if q in _flat(d44):
        return "struck_only"
    return "absent"


def test_標了逐字的引文_每一句都在44現行文字裡_而且不落在刪除線內():
    d44 = _D44.read_text(encoding="utf-8")
    found = _all_verbatim_quotes()
    assert found, "一句也沒抽到 —— 會變成空掃"
    bad, verified = [], 0
    for name, lineno, quote in found:
        verdict = _check_quote(quote, d44)
        if verdict == "live":
            verified += 1
        else:
            bad.append(f"{name}:{lineno} [{verdict}] {quote!r}")
    assert not bad, "\n".join(bad)
    assert verified >= _MIN_VERIFIED_QUOTES, verified


def test_逐字守衛本身會咬_刪除線內的舊條文與捏造的句子都判不合法():
    d44 = _D44.read_text(encoding="utf-8")
    retired = "不改資料內容 —— 本頁只改取數與呈現的參數"  # 3.5 頁首「不負責什麼」2026-09-21 劃掉的那一句
    assert "~~不改資料內容 —— 本頁只改取數與呈現的參數~~" in d44
    assert _check_quote(retired, d44) == "struck_only"
    assert _check_quote("本卡依系統推算的可信度排列", d44) == "absent"
    assert _check_quote("燈描述資料狀態，不描述市場或持倉", d44) == "live"
    sample = "# 44 逐字\n# 「燈描述資料狀態，不描述市場或持倉」\n"
    assert [q for _p, q in _quotes_introduced_by_verbatim(sample)] == ["燈描述資料狀態，不描述市場或持倉"]


def test_八塊的塊名逐字引44():
    text = _D44.read_text(encoding="utf-8")
    assert len(logic.BLOCK_TITLES) == 8
    for code, title in logic.BLOCK_TITLES.items():
        assert f"#### 塊 {code}｜{title}" in text, (code, title)


def test_八塊的回答什麼逐字引44現行那一句():
    d44 = _D44.read_text(encoding="utf-8")
    assert len(logic.ANSWERS) == 8
    for code, answer in logic.ANSWERS.items():
        assert _check_quote(answer, d44) == "live", (code, answer)
        # 而且真的住在該塊的「回答什麼」那一格。
        block = d44.split(f"#### 塊 {code}｜")[1].split("#### 塊 ")[0]
        assert f"| **回答什麼** | {answer} |" in block, code


def test_頁的回答什麼與不負責什麼逐字引44():
    d44 = _D44.read_text(encoding="utf-8")
    assert logic.PAGE_TITLE == "設定與診斷"
    assert _check_quote(logic.PAGE_ANSWERS, d44) == "live"
    for line in logic.NOT_RESPONSIBLE:
        assert _check_quote(line, d44) == "live", line


def test_44逐字的文案常數每一句都在現行文字裡():
    d44 = _D44.read_text(encoding="utf-8")
    assert len(logic.VERBATIM_TEXTS) >= 20
    for name, text in logic.VERBATIM_TEXTS.items():
        assert _check_quote(text, d44) == "live", (name, text)


def test_黃燈句型逐字_有N筆資料超過你設定的新鮮度上限():
    d44 = _D44.read_text(encoding="utf-8")
    assert _check_quote(logic.overdue_text(0).replace("0", "N"), d44) == "live"


# ═════════════════════ 三、取數失敗圖示：只有一個常數 ═════════════════════


def test_取數失敗模板與44第五節逐字相同_圖示取自單一常數():
    """`44` 5.5 系統錯誤模板。期望值由 FETCH_FAIL_GLYPH 組出，不在測試裡寫死圖示。"""
    template = logic.fetch_failed_text("<訊息原文>")
    assert template.startswith(logic.FETCH_FAIL_GLYPH + " ")
    row = [line for line in _live44().split("\n") if line.startswith("| `系統錯誤` | 取數或計算本身失敗 |")]
    assert len(row) == 1
    assert f"`{template}`" in row[0], (template, row[0])


def _strip_assigns(text, prefixes):
    """挖掉名字以 `prefixes` 開頭的模組層指派（登記表與禁詞表住在那裡）。"""
    lines = text.split("\n")
    drop = set()
    for node in ast.parse(text).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id.startswith(prefixes) for t in node.targets
        ):
            drop.update(range(node.lineno - 1, node.end_lineno))
    return "\n".join(line for i, line in enumerate(lines) if i not in drop)


_HARDCODED_FAIL = re.compile(r"[⚠⛔]\ufe0f?\s*取數失敗")


def test_原始碼沒有第二處寫死取數失敗的圖示():
    """登記 `SET-GAP-取數失敗圖示`：圖示只住在 `FETCH_FAIL_GLYPH` 一處。
    母體＝六個原始碼檔（含註解）；只挖掉 `GAPS` 登記表本身（它引用 44 的字面是登記，不是畫面文案）。"""
    hits = []
    for path in _ALL_SOURCE_FILES:
        body = _strip_assigns(path.read_text(encoding="utf-8"), ("GAPS",))
        hits += [(path.name, m.group(0)) for m in _HARDCODED_FAIL.finditer(body)]
    assert not hits, hits
    assert logic.FETCH_FAIL_GLYPH in ("⚠", "⛔")


def test_寫死圖示掃描本身會咬_負控():
    probe = 'GAPS = {"a": "⚠ 取數失敗"}\nX = "⛔ 取數失敗：" + m\n# ⚠取數失敗\n'
    body = _strip_assigns(probe, ("GAPS",))
    assert len(_HARDCODED_FAIL.findall(body)) == 2


def test_圖示常數改值之後_全頁每一處取數失敗與紅燈都跟著換_沒有殘留舊圖示(monkeypatch):
    """驗「改一個常數就全部換」：把常數換成另一個圖示（現值 ⛔ → ⚠；現值 ⚠ → ⛔），逐情境掃全頁模型，不得殘留「舊圖示 取數失敗」。"""
    old = logic.FETCH_FAIL_GLYPH
    new = "⛔" if old != "⛔" else "⚠"
    monkeypatch.setattr(logic, "FETCH_FAIL_GLYPH", new)
    seen = 0
    for name, save_failed in _every_case():
        model = _model(name, save_failed=save_failed)
        strings = logic.collect_ui_strings(model)
        assert not any(f"{old} {logic.TEXT_FETCH_FAILED}" in s for s in strings), name
        seen += sum(f"{new} {logic.TEXT_FETCH_FAILED}" in s for s in strings)
        lamp = _block(model, "SET-0")
        if lamp["_tone"] == "紅":
            assert lamp["glyph"] == new, name
        for badge in logic.collect_badges(model):
            if badge["text"] == "取數失敗":
                assert badge["glyph"] == new
    assert seen >= 10, seen


# ═════════════════════ 四、層次、四層通則、斷點 ═════════════════════


def test_層次分佈照44那張表():
    model = _model("ok")
    assert logic.codes_in_layer(model, 1) == ["SET-0"]
    assert logic.codes_in_layer(model, 2) == ["SET-1", "SET-2", "SET-3"]
    assert logic.codes_in_layer(model, 3) == ["SET-4", "SET-5"]
    assert logic.codes_in_layer(model, 4) == ["SET-6", "SET-7"]
    table = _D44.read_text(encoding="utf-8").split("### 3.5 頁｜設定與診斷")[1].split("#### 塊 SET-0")[0]
    for layer in (1, 2, 3, 4):
        row = [line for line in table.split("\n") if line.startswith(f"| 層 {layer} |")][0]
        assert re.findall(r"SET-\d", row) == logic.codes_in_layer(model, layer), layer


def test_初次載入展開的剛好是結論燈與三張核心卡():
    for name, save_failed in _every_case():
        model = _model(name, save_failed=save_failed)
        opened = [b["code"] for b in model["blocks"] if b["_default_open"]]
        assert opened == ["SET-0", "SET-1", "SET-2", "SET-3"], (name, opened)


def test_斷點欄數照客戶最終版三段():
    got = [logic.layer_columns(2, w) for w in (1280, 1279, 769, 768, 375, 374)]
    assert got == [3, 2, 2, 1, 1, 1], got
    edges = {w for w in range(2, 2000) if logic.columns_for_width(w) != logic.columns_for_width(w - 1)}
    assert edges == {769, 1280}
    for width in (374, 768, 1279, 1920):
        assert logic.layer_columns(1, width) == 1 and logic.layer_columns(4, width) == 1
        assert logic.layer_columns(3, width) <= 2


def test_層3與層4每一塊都有收合摘要_資料缺時寫出缺的來源鍵():
    """`44` 5.4 元件判準：把某個收合區內的資料抽掉，收合狀態下的摘要那一行寫出缺的來源鍵。"""
    for name, save_failed in _every_case():
        model = _model(name, save_failed=save_failed)
        for code in ("SET-4", "SET-5", "SET-6", "SET-7"):
            assert _block(model, code)["summary_text"], (name, code)
    assert "fetch_log" in _block(_model("first"), "SET-6")["summary_text"]
    assert "set_max_age_days" in _block(_model("nolimit"), "SET-4")["summary_text"]
    assert "user_setting" in _block(_model("settingfail"), "SET-4")["summary_text"]
    assert "fetch_log" in _block(_model("logfail"), "SET-6")["summary_text"]
    assert "未定義" in _block(_model("undef"), "SET-7")["summary_text"]


# ═════════════════════ 五、紅線 ═════════════════════


def test_全頁模型文字零方向詞零箭頭():
    for name, save_failed in _every_case():
        strings = logic.collect_ui_strings(_model(name, save_failed=save_failed))
        assert strings
        assert logic.scan_forbidden(strings) == {}, (name, save_failed)


def test_掃描器本身會咬_負控():
    for word in logic.FORBIDDEN_DIRECTION_WORDS + logic.FORBIDDEN_ARROWS + logic.FORBIDDEN_ADVICE_WORDS:
        assert logic.scan_forbidden([f"這一句含 {word} 這個詞"]) != {}, word


def _strip_forbidden_defs(text):
    """挖掉 `FORBIDDEN_*` 那幾個模組層定義本身（禁詞字表住在那裡，不該掃到自己）。"""
    lines = text.split("\n")
    drop = set()
    for node in ast.parse(text).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id.startswith("FORBIDDEN_") for t in node.targets
        ):
            drop.update(range(node.lineno - 1, node.end_lineno))
    return "\n".join(line for i, line in enumerate(lines) if i not in drop)


def _source_forbidden_words():
    """⚠️「一鍵」不收進原始碼層級的掃描：`44` SET-4 規則欄的「一鍵一個輸入欄」必然撞到它
    （量「鍵」的數量，不是那個按鈕詞）。按鈕標籤那一層的「一鍵」照樣由按鈕測試與畫面測試掃。"""
    button_words = tuple(w for w in logic.FORBIDDEN_BUTTON_WORDS if w != "一鍵")
    assert len(button_words) == 3
    return (
        logic.FORBIDDEN_DIRECTION_WORDS
        + logic.FORBIDDEN_ARROWS
        + logic.FORBIDDEN_ADVICE_WORDS
        + button_words
        + ("目標價", "建議")
    )


def test_原始碼六個檔零禁詞_母體含page與app_set():
    """⛔ 交接檔 §8.1：姊妹頁的禁詞原始碼掃描漏過 page.py。本條的母體數目寫死（2026-09-26 加 spec.py 與正式模式三檔後為十個）。"""
    assert len(_ALL_SOURCE_FILES) == 10
    assert _SET_DIR / "page.py" in _ALL_SOURCE_FILES and _APP in _ALL_SOURCE_FILES
    hits = []
    for path in _ALL_SOURCE_FILES:
        body = _strip_forbidden_defs(path.read_text(encoding="utf-8"))
        for word in _source_forbidden_words():
            if word in body:
                hits.append((path.name, word))
    assert not hits, hits


def test_原始碼禁詞掃描本身會咬_負控():
    for word in _source_forbidden_words():
        probe = "x = 1\nFORBIDDEN_DIRECTION_WORDS = (\n    " + repr(word) + ",\n)\nLABEL = " + repr("含" + word) + "\n"
        body = _strip_forbidden_defs(probe)
        assert "FORBIDDEN_DIRECTION_WORDS" not in body
        assert body.count(word) == 1, word


def test_按鈕標籤零禁詞_而且工廠會擋():
    for name, save_failed in _every_case():
        buttons = logic.collect_buttons(_model(name, save_failed=save_failed))
        assert buttons
        for button in buttons:
            for word in logic.FORBIDDEN_BUTTON_WORDS:
                assert word not in button["label"], (name, button["label"])
    for word in logic.FORBIDDEN_BUTTON_WORDS:
        with pytest.raises(ValueError):
            logic._button(f"測試{word}", "存檔")


def test_按鈕類別八類之內_而且沒有一類寫入那四張唯讀表():
    """`44` 5.3 元件判準。"""
    for name, save_failed in _every_case():
        for button in logic.collect_buttons(_model(name, save_failed=save_failed)):
            assert button["_action_kind"] in logic.BUTTON_KINDS
            assert not (button["_writes"] & set(logic.READONLY_TABLES)), button
    with pytest.raises(ValueError):
        logic._button("某個鈕", "再平衡")


def test_本頁按鈕只有存檔與重新取數兩枚_沒有套用也沒有清除():
    """`44` SET-4 規則欄逐字「本頁沒有「套用」類按鈕，本塊因此只掛這一枚」（登記 SET-GAP-清除鈕）。"""
    for name, save_failed in _every_case():
        model = _model(name, save_failed=save_failed)
        assert [(b["label"], b["_action_kind"]) for b in _block(model, "SET-4")["buttons"]] == [("存檔", "存檔")]
        assert [(b["label"], b["_action_kind"]) for b in _block(model, "SET-5")["buttons"]] == [("重新取數", "取數")]
        kinds = [b["_action_kind"] for b in logic.collect_buttons(model)]
        assert sorted(kinds) == ["取數", "存檔"], (name, kinds)


def test_存檔只寫user_setting_重新取數只寫fetch_log():
    model = _model("ok")
    assert _block(model, "SET-4")["buttons"][0]["_writes"] == {"user_setting"}
    assert _block(model, "SET-5")["buttons"][0]["_writes"] == {"fetch_log"}
    assert "user_setting" not in _block(model, "SET-5")["buttons"][0]["_writes"]


def test_首次開啟那個情境沒有一列輸入欄帶非空的預設值():
    """`44` 1.1 節判準。"""
    inputs = logic.collect_inputs(_model("first"))
    assert len(inputs) == 17, len(inputs)
    for field in inputs:
        assert field["_value"] is None and field["value_text"] == "", field


def test_紅線徽章只在說明區_而且是本頁那兩枚():
    """`44` 1.3 設定與診斷那一列：`G1†` `G3†`。"""
    model = _model("ok")
    marks = [b["text"] for b in logic.collect_badges(model) if b["_kind"] == "紅線"]
    assert marks == ["G1†", "G3†"]
    for block in model["blocks"]:
        for row in block.get("_rows", ()):
            assert "†" not in "".join(v for v in row.values() if isinstance(v, str))
    row = [line for line in _live44().split("\n") if line.startswith("| 設定與診斷 |")][0]
    assert "`G1†` `G3†`" in row


def test_狀態徽章字面值落在44那七個之內_顏色照5_2():
    tones = {"資料未備": "灰", "不適用": "黃", "取數失敗": "紅", "推估": "黃", "修正過": "黃", "部分缺": "黃", "未定義": "黃"}
    seen = set()
    for name, save_failed in _every_case():
        for badge in logic.collect_badges(_model(name, save_failed=save_failed)):
            if badge["_kind"] == "狀態":
                assert badge["text"] in logic.STATUS_BADGE_LITERALS
                assert badge["_tone"] == tones[badge["text"]]
                assert badge["glyph"], badge  # 狀態不靠顏色單獨辨識
                seen.add(badge["text"])
    assert seen == {"資料未備", "取數失敗", "未定義"}, seen
    with pytest.raises(ValueError):
        logic.status_badge("推薦")


# ═════════════════════ 六、對比 ═════════════════════


def test_對比逐組算過而且未達標為零():
    failures = [
        (name, round(theme.contrast_ratio(fg, bg), 3), floor)
        for name, fg, bg, floor in theme.CONTRAST_PAIRS
        if theme.contrast_ratio(fg, bg) < floor
    ]
    assert not failures, failures
    assert len(theme.CONTRAST_PAIRS) >= 20


def test_每一個狀態色都以文字門檻對頁底與卡底各驗過一次():
    pairs = {(fg, bg, floor) for _n, fg, bg, floor in theme.CONTRAST_PAIRS}
    for tone, color in theme.TONE_HEX.items():
        for bg in (theme.APP_BG, theme.SURFACE):
            assert (color, bg, theme.TEXT_FLOOR) in pairs, (tone, color, bg)
    assert (theme.STATE_GRAY, theme.STATE_GRAY_BG, theme.TEXT_FLOOR) in pairs  # 存檔失敗框


def test_對比函式本身算得對_負控():
    assert abs(theme.contrast_ratio("#000000", "#ffffff") - 21.0) < 1e-9
    assert theme.contrast_ratio("#8b949e", "#6e7681") < theme.TEXT_FLOOR


def test_每一個用到的色都登記過對比_page不寫色碼():
    registered = {fg for _n, fg, _b, _f in theme.CONTRAST_PAIRS} | {bg for _n, _f, bg, _l in theme.CONTRAST_PAIRS}
    for color in theme.ALL_COLORS:
        if color == theme.BORDER:
            continue
        assert color in registered, color
    page_source = (_SET_DIR / "page.py").read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{6}\b", page_source)


def test_每一個顏色語意都在theme登記過_查不到就炸():
    for name, save_failed in _every_case():
        tones = {n["_tone"] for n in logic._walk(_model(name, save_failed=save_failed)) if "_tone" in n}
        assert tones <= set(theme.TONE_HEX), (name, tones)
    with pytest.raises(KeyError):
        theme.tone_hex("綠")


# ═════════════════════ 七、SET-0 可信度結論燈 ═════════════════════


def test_SET0只讀SET1與SET2():
    assert _block(_model("ok"), "SET-0")["_reads"] == ("SET-1", "SET-2")
    sig = list(__import__("inspect").signature(logic.conclusion_light).parameters)
    assert sig == ["set1", "set2"], sig


def test_SET0判準_放寬上限到沒有任何一筆逾期_燈轉灰且文案為資料齊來源皆可達():
    lamp = _block(_model("ok"), "SET-0")
    assert lamp["_tone"] == "灰" and lamp["text"] == "資料齊、來源皆可達"
    dataset = fixtures.scenario("stale")
    assert _block(logic.build_page_model(dataset), "SET-0")["_tone"] == "黃"
    _setting(dataset, "set_max_age_days", "999")
    lamp = _block(logic.build_page_model(dataset), "SET-0")
    assert lamp["_tone"] == "灰" and lamp["text"] == "資料齊、來源皆可達"


def test_SET0判準_讓某一個來源取數失敗_燈轉紅且文案含該來源的層級字面值():
    lamp = _block(_model("failed"), "SET-0")
    assert lamp["_tone"] == "紅"
    assert fixtures.FAILED_TIER in lamp["text"]
    assert lamp["glyph"] == logic.FETCH_FAIL_GLYPH and "狀態：" in lamp["state_word"]


def test_SET0判準_全新環境_文案為兩句其中一句_不是資料齊():
    lamp = _block(_model("first"), "SET-0")
    assert lamp["text"] in ("尚未設定新鮮度上限", "尚無取數紀錄")
    assert lamp["text"] == "尚未設定新鮮度上限"  # SET-GAP-燈兩句同時成立
    assert lamp["_tone"] == "灰"


def test_SET0空狀態兩句各自成立():
    assert _block(_model("nolimit"), "SET-0")["text"] == "尚未設定新鮮度上限"
    dataset = fixtures.scenario("ok")
    dataset["fetch_log"] = []
    lamp = _block(logic.build_page_model(dataset), "SET-0")
    assert lamp["text"] == "尚無取數紀錄" and lamp["_tone"] == "灰"


def test_SET0黃_逾期大於零而失敗來源為零():
    lamp = _block(_model("stale"), "SET-0")
    assert lamp["_tone"] == "黃" and lamp["text"] == "有 1 筆資料超過你設定的新鮮度上限"
    assert lamp["glyph"] == logic.WARN_GLYPH


def test_SET0紅蓋過黃_也蓋過上限未設():
    """`failed` 情境同時有逾期；另把上限清空（SET-GAP-燈紅與空狀態相撞）。"""
    assert _block(_model("failed"), "SET-0")["_tone"] == "紅"
    dataset = fixtures.scenario("failed")
    _setting(dataset, "set_max_age_days", None)
    assert _block(logic.build_page_model(dataset), "SET-0")["_tone"] == "紅"


def test_SET0某類無列或某層級無紀錄仍照字面為灰():
    """登記 `SET-GAP-某類無列不入燈`。"""
    for name in ("norows", "notier"):
        assert _block(_model(name), "SET-0")["text"] == "資料齊、來源皆可達", name


def test_SET0讀取失敗時燈為紅且照抄失敗字串():
    """登記 `SET-GAP-燈讀取失敗`。"""
    for name in ("navfail", "logfail", "settingfail"):
        lamp = _block(_model(name), "SET-0")
        assert lamp["_tone"] == "紅", name
        assert lamp["text"] == logic.fetch_failed_text(fixtures.READ_FAIL_MESSAGE), name
        assert lamp["text"] not in ("資料齊、來源皆可達", "尚未設定新鮮度上限")


def test_SET0每一種燈都同時有圖示與狀態字():
    for name, save_failed in _every_case():
        lamp = _block(_model(name, save_failed=save_failed), "SET-0")
        assert lamp["glyph"] and lamp["state_word"].startswith("狀態："), name


# ═════════════════════ 八、SET-1 資料新鮮度卡 ═════════════════════


def _rows(model, code):
    return _block(model, code)["_rows"]


def test_SET1一列一類三欄_淨值配息市場指標():
    model = _model("ok")
    assert [r["kind_text"] for r in _rows(model, "SET-1")] == ["淨值", "配息", "市場指標"]
    assert len(_block(model, "SET-1")["column_labels"]) == 4  # 類名 ＋ 三欄
    assert [r["days_text"] for r in _rows(model, "SET-1")] == ["1", "4", "2"]
    assert all(r["compare_text"] == "內" for r in _rows(model, "SET-1"))


def test_SET1表頭註明時區字面值():
    """`44` SET-1 規則欄逐字：顯示時轉當地時區並在表頭註明時區字面值。"""
    labels = _block(_model("ok"), "SET-1")["column_labels"]
    assert any(logic.DISPLAY_TZ_LABEL in label for label in labels)
    assert _rows(_model("ok"), "SET-1")[0]["at_text"] == "2026-09-21 11:10"


def test_SET1判準_上限設成0日_三列皆外_SET0的N等於3():
    model = _model("zero")
    assert [r["compare_text"] for r in _rows(model, "SET-1")] == ["外", "外", "外"]
    assert _block(model, "SET-0")["text"] == "有 3 筆資料超過你設定的新鮮度上限"


def test_SET1判準_清空上限_比較欄不適用而最近取得時間仍出數():
    rows = _rows(_model("nolimit"), "SET-1")
    assert all(r["compare_text"] == "⬜ 不適用：尚未設定上限" for r in rows)
    assert all(re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", r["at_text"]) for r in rows)


def test_SET1某類無任何列_三欄空方塊掛資料未備():
    row = _rows(_model("norows"), "SET-1")[1]
    assert (row["at_text"], row["days_text"], row["compare_text"]) == ("⬜", "⬜", "⬜")
    assert [b["text"] for b in row["badges"]] == ["資料未備"]
    others = [_rows(_model("norows"), "SET-1")[i] for i in (0, 2)]
    assert all(r["compare_text"] == "內" for r in others)


def test_SET1判準原文_上限0日且某類今天才取得_三列皆外_SET0的N等於3():
    """`44` SET-1 判準逐字「把上限設成 0 日，三列的比較欄皆為「外」且 `SET-0` 的 N 等於 3」。
    `zerotoday` 裡淨值距今 0 日 —— 這一條正是端點（大於等於算外）的出處（SET-GAP-端點）。"""
    model = _model("zerotoday")
    rows = _rows(model, "SET-1")
    assert rows[0]["days_text"] == "0"
    assert [r["compare_text"] for r in rows] == ["外", "外", "外"]
    assert _block(model, "SET-0")["text"] == "有 3 筆資料超過你設定的新鮮度上限"


def test_SET1端點_距今日數等於上限算外():
    """登記 `SET-GAP-端點`：由 44 SET-1 判準推得。"""
    dataset = fixtures.scenario("ok")
    _setting(dataset, "set_max_age_days", "4")
    rows = _rows(logic.build_page_model(dataset), "SET-1")
    assert rows[1]["days_text"] == "4" and rows[1]["compare_text"] == "外"
    _setting(dataset, "set_max_age_days", "5")
    assert _rows(logic.build_page_model(dataset), "SET-1")[1]["compare_text"] == "內"
    assert "推得" in logic.GAPS["SET-GAP-端點"] and "44 沒寫" not in logic.GAPS["SET-GAP-端點"].split("（原型")[0]


def test_SET1讀取失敗只讓那一列進系統錯誤():
    """登記 `SET-GAP-讀取失敗逐列`。"""
    rows = _rows(_model("navfail"), "SET-1")
    assert rows[0]["at_text"] == logic.fetch_failed_text(fixtures.READ_FAIL_MESSAGE)
    assert rows[1]["compare_text"] == "內" and rows[2]["compare_text"] == "內"
    assert _block(_model("navfail"), "SET-1")["_tone"] == "紅"


# ═════════════════════ 九、SET-2 來源健康卡 ═════════════════════


def test_SET2四個層級逐一列出_不依紀錄增減():
    for name in ("ok", "notier", "failed", "emptyresp", "broken"):
        assert [r["tier_text"] for r in _rows(_model(name), "SET-2")] == ["淨值", "配息", "市場指標", "其他"], name
    live = _live44()
    assert "`淨值`／`配息`／`市場指標`／`其他`" in live
    assert tuple(logic.TIERS) == tuple(fixtures.TIERS) == ("淨值", "配息", "市場指標", "其他")


def test_SET2判準_失敗那一列結果為failed_訊息逐字等於紀錄裡的message():
    rows = {r["tier_text"]: r for r in _rows(_model("failed"), "SET-2")}
    failed = rows[fixtures.FAILED_TIER]
    assert failed["result_text"] == "failed"
    record = [r for r in fixtures.scenario("failed")["fetch_log"] if r["outcome"] == "failed"][0]
    assert failed["message_text"] == record["message"] == fixtures.TIER_FAIL_MESSAGE
    assert [b["text"] for b in failed["badges"]] == ["取數失敗"]


def test_SET2判準_全部紀錄清空_卡片顯示尚無取數紀錄而不是全ok():
    block = _block(_model("first"), "SET-2")
    assert block["_rows"] == []
    assert block["placeholder"]["text"] == "尚無取數紀錄" and block["placeholder"]["_empty_kind"] == "來源缺"


def test_SET2與SET6來源缺_不掛重新取數():
    """登記 `SET-GAP-來源缺按鈕`（44 5.5 空狀態欄整格為準）。"""
    model = _model("first")
    assert _block(model, "SET-2")["buttons"] == [] and _block(model, "SET-6")["buttons"] == []


def test_SET2某層級從無紀錄_三欄空方塊掛資料未備():
    row = {r["tier_text"]: r for r in _rows(_model("notier"), "SET-2")}[fixtures.NO_RECORD_TIER]
    assert (row["result_text"], row["time_text"], row["message_text"]) == ("⬜", "⬜", "⬜")
    assert [b["text"] for b in row["badges"]] == ["資料未備"]


def test_SET2取數回空_訊息欄寫回應為空而結果為ok():
    """`44` SET-5 空狀態欄；登記 `SET-GAP-回應為空`。"""
    row = {r["tier_text"]: r for r in _rows(_model("emptyresp"), "SET-2")}[fixtures.EMPTY_TIER]
    assert row["result_text"] == "ok" and row["message_text"] == "回應為空"
    record = max((r for r in fixtures.scenario("emptyresp")["fetch_log"] if r["source_tier"] == fixtures.EMPTY_TIER),
                 key=lambda r: r["started_at"])
    assert record["outcome"] == "ok" and record["row_count"] == 0 and record["message"] is None


def test_SET2不改寫訊息_不給處置方向():
    block = _block(_model("failed"), "SET-2")
    assert "訊息原文照印，不改寫成安撫語句" in "".join(block["detail_lines"])
    assert "本卡不對失敗給出處置方向" in "".join(block["detail_lines"])


# ═════════════════════ 十、SET-3 規則參數卡 ═════════════════════


def test_SET3判準_全新環境每一列目前值皆未設定_而且沒有第五欄():
    block = _block(_model("first"), "SET-3")
    assert len(block["column_labels"]) == 4
    assert len(block["_rows"]) == 17
    assert all(r["value_text"] == "⬜ 未設定" for r in block["_rows"])


def test_SET3依setting_key排列():
    keys = [r["key_text"] for r in _rows(_model("ok"), "SET-3")]
    assert keys == sorted(keys) and len(keys) == 17


def test_SET3依setting_key排列_與表裡的列序無關():
    """負控：把 user_setting 的列序倒過來、或整張表清空，SET-3 仍依鍵名排。"""
    dataset = fixtures.scenario("ok")
    dataset["user_setting"] = list(reversed(dataset["user_setting"]))
    keys = [r["key_text"] for r in _rows(logic.build_page_model(dataset), "SET-3")]
    assert keys == sorted(keys) and keys != [r["setting_key"] for r in dataset["user_setting"]]
    dataset["user_setting"] = []
    keys = [r["key_text"] for r in _rows(logic.build_page_model(dataset), "SET-3")]
    assert keys == sorted(keys) and len(keys) == 17


def test_SET3全表為空也逐鍵列出():
    """`44` SET-3 空狀態逐字「全表為空 → 逐鍵列出且目前值欄皆 ⬜ 未設定」（登記 SET-GAP-鍵清單）。"""
    dataset = fixtures.scenario("ok")
    dataset["user_setting"] = []
    rows = _rows(logic.build_page_model(dataset), "SET-3")
    assert len(rows) == 17 and all(r["value_text"] == "⬜ 未設定" for r in rows)


def test_SET3判準_值與型別不符_出現不適用並印出原始字面值():
    row = {r["key_text"]: r for r in _rows(_model("badkind"), "SET-3")}[fixtures.BAD_KIND_KEY]
    assert row["value_text"] == "⬜ 不適用：值與型別不符"
    assert fixtures.BAD_KIND_LITERAL in row["raw_text"]


def test_SET3沒有內建預設值欄():
    labels = "".join(_block(_model("ok"), "SET-3")["column_labels"])
    assert "預設" not in labels and "系統值" not in labels


def test_value_kind判定規則_六種各有正反例():
    """登記 `SET-GAP-型別判定規則`。"""
    cases = {
        "int": ("7", "ninety"),
        "float": ("4.5", "四點五"),
        "ratio": ("0.3", "1.5"),
        "date": ("2026-09-21", "2026-13-40"),
        "list": ('["a"]', "a, b"),
        "rules": ('["r"]', "{}"),
    }
    for kind, (good, bad) in cases.items():
        assert logic.value_matches_kind(good, kind), kind
        assert not logic.value_matches_kind(bad, kind), kind
    assert logic.value_matches_kind("cost", None)  # SET-GAP-型別缺
    with pytest.raises(ValueError):
        logic.value_matches_kind("1", "percent")


def test_value_kind六種照44第四節():
    row = [line for line in _live44().split("\n") if line.startswith("| `value_kind` |")][0]
    assert re.findall(r"`(\w+)`", row.split("|")[5]) == list(logic.VALUE_KINDS)


# ═════════════════════ 十一、SET-4 參數編輯 ═════════════════════


def test_SET4一鍵一個輸入欄_型態依value_kind():
    inputs = _block(_model("ok"), "SET-4")["inputs"]
    assert [f["name"] for f in inputs] == [r["key_text"] for r in _rows(_model("ok"), "SET-3")]
    for field in inputs:
        assert field["_multiline"] is (field["_kind"] in ("list", "rules"))


def test_SET4判準_清除上限_SET1比較欄不適用而不是以0計():
    dataset = fixtures.scenario("ok")
    _setting(dataset, "set_max_age_days", None)
    rows = _rows(logic.build_page_model(dataset), "SET-1")
    assert all(r["compare_text"] == "⬜ 不適用：尚未設定上限" for r in rows)
    assert all(r["compare_text"] != "外" for r in rows)


def test_SET4輸入值與型別不符_欄位下方型別說明_SET3的值不變():
    """`44` SET-4 判準：輸入一個與 value_kind 不符的值按存檔，SET-3 該列目前值與存檔前逐字相同。"""
    before = {r["key_text"]: r["value_text"] for r in _rows(_model("ok"), "SET-3")}
    dataset = fixtures.scenario("ok")
    dataset["save_inputs"] = {"mkt_window_days": "ninety"}
    model = logic.build_page_model(dataset)
    field = [f for f in _block(model, "SET-4")["inputs"] if f["name"] == "mkt_window_days"][0]
    assert field["value_text"] == "ninety"
    assert field["hint_lines"] and "int" in field["hint_lines"][0]
    after = {r["key_text"]: r["value_text"] for r in _rows(model, "SET-3")}
    assert after == before


def test_SET4每一鍵寫出會影響哪幾塊():
    inputs = {f["name"]: f for f in _block(_model("ok"), "SET-4")["inputs"]}
    assert inputs["set_max_age_days"]["used_by_text"].endswith("SET-1")
    assert "HLD-8" in inputs["hld_window_end"]["used_by_text"]
    assert "沒有宣告" in inputs["set_log_keep_rows"]["used_by_text"]  # SET-GAP-影響哪幾塊


def test_SET4存檔寫入失敗_失敗框掛在該鍵下方_當下輸入不清掉_SET3那一列不變():
    """`44` SET-4 空狀態欄；拍板原型：⛔ 開頭、灰態。"""
    for name in fixtures.ALL_SCENARIO_NAMES:
        if name == "settingfail":
            continue
        plain, failed = _model(name), _model(name, save_failed=True)
        fields = {f["name"]: f for f in _block(failed, "SET-4")["inputs"]}
        target = fields[fixtures.FAIL_KEY]
        assert target["fail_lines"] == [logic.save_failed_text(fixtures.SAVE_FAIL_MESSAGE), logic.TEXT_KEEP_INPUT], name
        assert target["fail_lines"][0].startswith(logic.SAVE_FAIL_GLYPH + " 存檔寫入失敗：")
        assert target["value_text"] == fixtures.FAIL_INPUT, name
        assert sum(bool(f["fail_lines"]) for f in fields.values()) == 1, name
        assert _rows(failed, "SET-3") == _rows(plain, "SET-3"), name
        assert _rows(failed, "SET-1") == _rows(plain, "SET-1"), name


def test_存檔失敗框的圖示與拍板原型相同_而且與黃燈的圖示分開():
    """客戶 2026-09-24 裁示「失敗框補圖示」；拍板原型 `ui_prototype_set.html` 的失敗框以 ⛔ 開頭。
    ⚠️ 2026-09-24 第二十一輪更正（有意識的更正，不是漏刪）：本條原名寫「而且與取數失敗和黃燈的圖示分開」，
    但斷言從來只驗黃燈那一半；客戶同日另裁取數失敗也用 ⛔，兩種失敗自此同一個圖示（文字不同），
    故名字只留黃燈那一半，並把「兩種失敗同圖示」釘成事實（見 SET-GAP-取數失敗圖示）。"""
    proto = (_ROOT / "docs" / "v2" / "prototype" / "ui_prototype_set.html").read_text(encoding="utf-8")
    glyphs = set(re.findall(r"'<div class=\"failbox\">(\S+) 存檔寫入失敗：", proto))
    assert glyphs == {logic.SAVE_FAIL_GLYPH}, glyphs
    assert logic.save_failed_text("x") == logic.SAVE_FAIL_GLYPH + " 存檔寫入失敗：x"
    assert logic.SAVE_FAIL_GLYPH != logic.WARN_GLYPH
    assert logic.SAVE_FAIL_GLYPH == logic.FETCH_FAIL_GLYPH == "⛔"


def test_SET4存檔失敗疊在user_setting讀取失敗上_失敗框改掛在塊上():
    """登記 `SET-GAP-失敗無輸入欄`。"""
    block = _block(_model("settingfail", save_failed=True), "SET-4")
    assert block["inputs"] == []
    # 必修：沒有任何輸入欄時，第二行「上面這一欄的當下輸入…」是假話，不印。
    assert block["orphan_fail_lines"] == [[logic.save_failed_text(fixtures.SAVE_FAIL_MESSAGE)]]
    assert logic.TEXT_KEEP_INPUT not in logic.collect_ui_strings(block)
    assert block["fail_nodes"][0]["text"] == logic.fetch_failed_text(fixtures.READ_FAIL_MESSAGE)


def test_失敗框第二行與型別說明句尾照拍板草稿():
    """建議 S1：拍板草稿失敗框兩行；型別說明句尾「本次不存檔，SET-3 的值不變。」（含 44 SET-4 空狀態欄那半句）。"""
    draft = (_ROOT / "docs" / "wireframes" / "draft_set_savefail.html").read_text(encoding="utf-8")
    assert f"第二行「{logic.TEXT_KEEP_INPUT}」" in draft
    assert "本次不存檔，SET-3 的值不變。" in re.sub(r"</?b>", "", draft)
    assert _check_quote("不存檔，`SET-3` 的值不變", _D44.read_text(encoding="utf-8")) == "live"
    field = {f["name"]: f for f in _block(_model("badkind"), "SET-4")["inputs"]}[fixtures.BAD_KIND_KEY]
    assert field["hint_lines"][0].endswith(logic.TEXT_NOT_SAVED)


def test_SET4未設定的鍵畫面顯示未設定_輸入欄仍留空():
    """建議 S2：`44` 4.5「未設定的鍵 `setting_value` 為空，畫面顯示 `⬜ 未設定`，不顯示任何候選值」。"""
    inputs = _block(_model("first"), "SET-4")["inputs"]
    assert len(inputs) == 17
    for field in inputs:
        assert field["unset_lines"] == ["⬜ 未設定"] and field["value_text"] == "", field["name"]
    nolimit = {f["name"]: f for f in _block(_model("nolimit"), "SET-4")["inputs"]}
    assert nolimit["set_max_age_days"]["unset_lines"] == ["⬜ 未設定"]
    assert all(f["unset_lines"] == [] for k, f in nolimit.items() if k != "set_max_age_days")
    # 存檔失敗時那一鍵畫的是當下輸入，不再說它未設定。
    failed = {f["name"]: f for f in _block(_model("first", save_failed=True), "SET-4")["inputs"]}
    assert failed[fixtures.FAIL_KEY]["unset_lines"] == []


def test_型別說明不給示例值_只寫格式():
    """建議 2：示例值等於代填候選值（G3†）。說明裡不得出現任何數字（date 的 YYYY-MM-DD 是格式字母），也不得出現「例如」。"""
    assert set(logic.KIND_HINTS) == set(logic.VALUE_KINDS)
    for kind, hint in logic.KIND_HINTS.items():
        assert "例如" not in hint and not re.search(r"\d", hint.replace("0 到 1", "")), (kind, hint)
    field = {f["name"]: f for f in _block(_model("badkind"), "SET-4")["inputs"]}[fixtures.BAD_KIND_KEY]
    assert field["hint_lines"] == ["型別說明：這個鍵的 value_kind 是 int，要輸入一個整數。本次不存檔，SET-3 的值不變。"]


def test_SET1說明行引的判準是44逐字():
    """建議 1：畫面那句判準引文逐字取自 44 SET-1 判準行。"""
    line = [l for l in _block(_model("ok"), "SET-1")["detail_lines"] if "推得" in l][0]
    assert f"「{logic.TEXT_SET1_JUDGE}」" in line
    judge = [l for l in _live44().split("\n") if l.startswith("**判準**：把上限設成 0 日")]
    assert len(judge) == 1 and logic.TEXT_SET1_JUDGE in judge[0]


def test_SET4不提供還原系統值():
    block = _block(_model("ok"), "SET-4")
    assert all("還原" not in b["label"] for b in block["buttons"])
    assert "沒有系統值可還原" in "".join(block["detail_lines"])


def test_存檔失敗的鍵不認得就炸():
    dataset = fixtures.scenario("ok")
    dataset["save_errors"] = {"no_such_key": "x"}
    with pytest.raises(ValueError):
        logic.build_page_model(dataset)


# ═════════════════════ 十二、SET-5 重新取數 ═════════════════════


def test_SET5未選層級_按鈕停用_原因逐字():
    button = _block(_model("ok"), "SET-5")["buttons"][0]
    assert button["_enabled"] is False and button["disabled_reason"] == "尚未選定來源層級"
    assert button["label"] == "重新取數" and "一鍵" not in button["label"]


def test_SET5選了層級才可用_選項是44那四個():
    assert _block(_model("ok"), "SET-5")["tier_options"] == ("淨值", "配息", "市場指標", "其他")
    for tier in logic.TIERS:
        button = logic.set5_button(tier)
        assert button["_enabled"] is True and button["disabled_reason"] == ""
    with pytest.raises(ValueError):
        logic.set5_button("股票")


def test_SET5寫出取數只寫資料表與fetch_log():
    assert "取數只寫入資料表與 fetch_log，不改寫任何 user_setting" in "".join(_block(_model("ok"), "SET-5")["detail_lines"])


# ═════════════════════ 十三、SET-6 取數紀錄 ═════════════════════


def test_SET6依started_at由新到舊_耗時單位秒():
    rows = _rows(_model("ok"), "SET-6")
    started = [r["cells"][2] for r in rows]
    assert started == sorted(started, reverse=True)
    assert rows[0]["cells"][3] == "4.0"
    assert "秒" in _block(_model("ok"), "SET-6")["column_labels"][3]


def test_SET6判準_finished_at清空_耗時欄不適用而其餘欄照印():
    row = {r["_log_id"]: r for r in _rows(_model("broken"), "SET-6")}[fixtures.BROKEN_LOG_ID]
    assert row["cells"][3] == "⬜ 不適用：未記錄結束時間"
    assert all(c not in ("", "⬜") for i, c in enumerate(row["cells"]) if i != 3)


def test_SET6判準_保留筆數設成1_表上一列_表尾註明已移除筆數():
    block = _block(_model("keep1"), "SET-6")
    assert len(block["_rows"]) == 1
    total = len(fixtures.scenario("keep1")["fetch_log"])
    assert block["tail_lines"] == [f"保留筆數上限 1（set_log_keep_rows），已移除 {total - 1} 筆"]


def test_SET6保留筆數為負_不說成型別不符_全部列出():
    """建議 S3：登記 `SET-GAP-保留筆數為負`。"""
    dataset = fixtures.scenario("ok")
    _setting(dataset, "set_log_keep_rows", "-1")
    block = _block(logic.build_page_model(dataset), "SET-6")
    assert len(block["_rows"]) == len(dataset["fetch_log"])
    assert "⬜ 不適用：保留筆數小於 0" in block["tail_lines"][0]
    assert logic.TEXT_NA_BAD_KIND not in block["tail_lines"][0]


def test_SET6保留筆數為零_零列_表尾寫已移除_不說成尚無取數紀錄():
    """建議 S3：登記 `SET-GAP-保留筆數為零`。"""
    dataset = fixtures.scenario("ok")
    _setting(dataset, "set_log_keep_rows", "0")
    block = _block(logic.build_page_model(dataset), "SET-6")
    assert block["_rows"] == [] and block["placeholder"] is None
    assert block["tail_lines"] == [f"保留筆數上限 0（set_log_keep_rows），已移除 {len(dataset['fetch_log'])} 筆"]


def test_fetch_log值域越界與其他表讀取失敗_炸掉():
    """建議 S4／S5：登記 `SET-GAP-fetch_log值域越界`、`SET-GAP-其他表讀取失敗炸`。"""
    for column, value in (("source_tier", "股票"), ("outcome", "partial")):
        dataset = fixtures.scenario("ok")
        dataset["fetch_log"][0][column] = value
        with pytest.raises(ValueError, match="值域越界"):
            logic.build_page_model(dataset)
    for table in ("holding", "policy", "fund_profile"):
        dataset = fixtures.scenario("ok")
        dataset["errors"] = {table: "x"}
        with pytest.raises(ValueError):
            logic.build_page_model(dataset)


def test_SET6無任何列是來源缺_文案尚無取數紀錄():
    block = _block(_model("first"), "SET-6")
    assert block["_rows"] == [] and block["placeholder"]["text"] == "尚無取數紀錄"
    assert block["placeholder"]["_empty_kind"] == "來源缺"


# ═════════════════════ 十四、SET-7 欄位對照表 ═════════════════════


def test_SET7一列一個表欄位_未被使用的寫未被任何塊使用():
    block = _block(_model("ok"), "SET-7")
    fields = [r["field_text"] for r in block["_rows"]]
    assert len(fields) == 59 and len(set(fields)) == 59
    rows = {r["field_text"]: r for r in block["_rows"]}
    assert rows["policy.fee_rate_pct"]["blocks_text"] == "⬜ 未被任何塊使用"
    assert "SET-2" in rows["fetch_log.message"]["_blocks"] and "SET-6" in rows["fetch_log.message"]["_blocks"]


def test_SET7判準_任取一列的塊代號_該塊來源欄寫出那個欄位():
    """對 `44` 現行文字逐列驗（不是對快照驗）。"""
    d44 = _live44()
    checked = 0
    for row in _rows(_model("ok"), "SET-7"):
        table, column = row["field_text"].split(".")
        for code in row["_blocks"]:
            block = d44.split(f"#### 塊 {code}｜")[1].split("#### 塊 ")[0]
            source = re.search(r"(?m)^\| \*\*來源\*\* \|(.*)\|\s*$", block).group(1)
            assert f"`{table}.{column}`" in source or re.search(rf"`{table}` 全(表|欄)", source), (code, row)
            checked += 1
    assert checked >= 60, checked


def test_SET7判準_把第四節某欄位改名_出現一列掛未定義徽章的舊欄位名():
    dataset = fixtures.scenario("ok")
    tables = dict(dataset["spec"]["tables"])
    tables["fetch_log"] = tuple("msg" if c == "message" else c for c in tables["fetch_log"])
    dataset["spec"] = {**dataset["spec"], "tables": tuple(tables.items())}
    rows = {r["field_text"]: r for r in _rows(logic.build_page_model(dataset), "SET-7")}
    assert [b["text"] for b in rows["fetch_log.message"]["badges"]] == ["未定義"]
    # 新名只被「`fetch_log` 全欄」那兩塊帶到；明寫 `fetch_log.message` 的 SET-2 落在舊名那一列。
    assert rows["fetch_log.msg"]["_blocks"] == ("SET-5", "SET-6")
    assert rows["fetch_log.message"]["_blocks"] == ("SET-2",)


def test_SET7未定義情境():
    rows = {r["field_text"]: r for r in _rows(_model("undef"), "SET-7")}
    assert [b["text"] for b in rows[fixtures.UNDEF_FIELD]["badges"]] == ["未定義"]
    assert rows[fixtures.UNDEF_FIELD]["_blocks"] == (fixtures.UNDEF_BLOCK,)


def test_SET7判準_規則欄用到來源欄沒宣告的欄位_本表看不見():
    """射程限制真的存在（44 SET-7 判準第三句）：44 的 SET-6 規則欄用到 `user_setting`（保留筆數），
    來源欄卻沒宣告 —— 本表 user_setting 那幾列的塊代號清單裡沒有 SET-6。對 44 現行文字驗前提。"""
    d44 = _live44()
    set6 = d44.split("#### 塊 SET-6｜")[1].split("#### 塊 ")[0]
    rule = re.search(r"(?m)^\| \*\*規則\*\* \|(.*)\|\s*$", set6).group(1)
    source = re.search(r"(?m)^\| \*\*來源\*\* \|(.*)\|\s*$", set6).group(1)
    assert "`user_setting`" in rule and "user_setting" not in source
    rows = {r["field_text"]: r for r in _rows(_model("ok"), "SET-7")}
    for column in ("setting_key", "setting_value", "value_kind", "updated_at"):
        assert "SET-6" not in rows[f"user_setting.{column}"]["_blocks"], column


# ═════════════════════ 十五、取數失敗逐塊 ═════════════════════


def _fail_blocks(model, message=fixtures.READ_FAIL_MESSAGE):
    text = logic.fetch_failed_text(message)
    return {b["code"] for b in model["blocks"] if any(text in s for s in logic.collect_ui_strings(b))}


def test_每一種讀取失敗_受影響的塊逐塊點名_不整頁炸():
    """登記 `SET-GAP-取數失敗`：照 44 5.5 系統錯誤模板畫在受影響的塊。"""
    expected = {
        "navfail": {"SET-0", "SET-1"},
        "logfail": {"SET-0", "SET-2", "SET-6"},
        "settingfail": {"SET-0", "SET-1", "SET-3", "SET-4", "SET-6"},
    }
    for name, codes in expected.items():
        assert _fail_blocks(_model(name)) == codes, (name, _fail_blocks(_model(name)))
    for name in fixtures.ALL_SCENARIO_NAMES:
        if name not in expected:
            assert _fail_blocks(_model(name)) == set(), name


def test_讀取失敗的空狀態是系統錯誤_紅_不掛重新取數():
    for name, code in (("logfail", "SET-2"), ("logfail", "SET-6"), ("settingfail", "SET-3")):
        node = _block(_model(name), code)["placeholder"]
        assert node["_empty_kind"] == "系統錯誤" and node["_tone"] == "紅", (name, code)
        assert _block(_model(name), code)["buttons"] == []


def test_user_setting讀取失敗_不說成未設定_不畫輸入欄():
    """登記 `SET-GAP-設定取數失敗`。"""
    model = _model("settingfail")
    for code in ("SET-1", "SET-3", "SET-4"):
        assert logic.TEXT_UNSET not in logic.collect_ui_strings(_block(model, code)), code
    assert _block(model, "SET-4")["inputs"] == []
    assert all(r["compare_text"] == "⬜" for r in _rows(model, "SET-1"))


def test_本頁沒有畫法的取數失敗才炸():
    dataset = fixtures.scenario("ok")
    dataset["errors"] = {"holding": "HTTP 503（示意）"}
    with pytest.raises(ValueError, match="取數失敗"):
        logic.build_page_model(dataset)


# ═════════════════════ 十六、規格快照對 44 現行文字 ═════════════════════


def _spec_tables_from_44():
    text = _D44.read_text(encoding="utf-8")
    sec4 = text[text.index("## 4. 資料庫結構") : text.index("## 5. 元件清單")]
    out = []
    for match in re.finditer(r"(?m)^#{3,4} (?:4\.\d )?表 `([a-z_]+)`", sec4):
        rest = sec4[match.end():]
        nxt = re.search(r"(?m)^#{3,4} ", rest)
        body = rest[: nxt.start()] if nxt else rest
        out.append((match.group(1), tuple(re.findall(r"(?m)^\| `([a-z_]+)` \|", body))))
    return tuple(out)


def _block_sources_from_44():
    text = _D44.read_text(encoding="utf-8")
    sec3 = text[text.index("## 3. 五頁") : text.index("## 4. 資料庫結構")]
    out = []
    for chunk in re.split(r"(?m)^#### 塊 ", sec3)[1:]:
        code = chunk.split("｜")[0]
        live = _strip_struck(re.search(r"(?m)^\| \*\*來源\*\* \|(.*)\|\s*$", chunk).group(1))
        declared = sorted(set(re.findall(r"`([a-z_]+\.[a-z_]+)`", live)))
        declared += [f"{t}.*" for t, _k in re.findall(r"`([a-z_]+)` 全(表|欄)", live)]
        out.append((code, tuple(declared), live))
    return out


def test_規格快照_第四節八張表的欄位與44逐欄相同():
    assert fixtures.SPEC_TABLES == _spec_tables_from_44()
    assert sum(len(c) for _t, c in fixtures.SPEC_TABLES) == 59


def test_規格快照_四十一塊來源欄與44重抽相同():
    """登記 `SET-GAP-SET7寫死`／`SET-GAP-SET7母體`。"""
    derived = _block_sources_from_44()
    assert len(derived) == 41
    assert fixtures.SPEC_BLOCK_SOURCES == tuple((c, d) for c, d, _l in derived)


def test_規格快照_十七個鍵與44全文相同_各鍵被哪幾塊來源欄寫出也相同():
    live = _live44()
    keys = sorted(set(re.findall(r"`((?:set|mkt|hld|exp|alo)_[a-z_]+)`", live)))
    assert [k for k, _v in fixtures.SPEC_SETTING_KEYS] == keys
    derived = tuple((k, tuple(c for c, _d, src in _block_sources_from_44() if f"`{k}`" in src)) for k in keys)
    assert fixtures.SPEC_KEY_USED_BY == derived
    for _key, kind in fixtures.SPEC_SETTING_KEYS:
        assert kind is None or kind in logic.VALUE_KINDS


def test_規格快照守衛本身會咬_負控():
    derived = _block_sources_from_44()
    mutated = list(fixtures.SPEC_BLOCK_SOURCES)
    mutated[0] = (mutated[0][0], ("nav.fetched_at",))
    assert tuple(mutated) != tuple((c, d) for c, d, _l in derived)


# ═════════════════════ 十七、情境表與登記 ═════════════════════


def test_情境表與ALL_SCENARIO_NAMES不得漂移_每一個都有標籤():
    assert set(fixtures.SCENARIO_LABELS) == set(fixtures.ALL_SCENARIO_NAMES)
    assert len(fixtures.ALL_SCENARIO_NAMES) == 17
    with pytest.raises(KeyError):
        fixtures.scenario("nope")


def test_每一個情境都建得出模型而且八塊齊全():
    for name, save_failed in _every_case():
        assert [b["code"] for b in _model(name, save_failed=save_failed)["blocks"]] == list(logic.BLOCK_TITLES)


def test_build_page_model不改動dataset():
    for name, save_failed in _every_case():
        dataset = fixtures.scenario_with(name, save_failed=save_failed)
        before = copy.deepcopy(dataset)
        logic.build_page_model(dataset)
        assert dataset == before, name


def _block_has_numbers(block) -> bool:
    strings = logic.collect_ui_strings({k: v for k, v in block.items() if k != "code"})
    strings = [re.sub(r"SET-\d|UTC\+8|[A-Z]{3}-\d", "", s) for s in strings if s != logic.HINT_NOTE]
    return any(re.search(r"\d", s) for s in strings)


def test_示意標記_頁首一行_有數字的核心卡與紀錄塊各一行():
    """登記 `SET-GAP-示意標記`。"""
    checked = 0
    for name, save_failed in _every_case():
        model = _model(name, save_failed=save_failed)
        assert model["hint_note"] == logic.PAGE_HINT_NOTE
        for code in ("SET-1", "SET-2", "SET-3", "SET-6"):
            block = _block(model, code)
            if _block_has_numbers(block):
                assert logic.HINT_NOTE in block["detail_lines"], (name, code)
                checked += 1
    assert checked >= 60, checked


def test_缺口登記表每一筆都在原始碼裡被引用():
    assert len(logic.GAPS) >= 20
    sources = "".join(p.read_text(encoding="utf-8") for p in _ALL_SOURCE_FILES)
    for gap_id, text in logic.GAPS.items():
        assert sources.count(gap_id) >= 2, gap_id
        assert len(text) >= 20, gap_id


def test_缺口登記守衛本身會咬_負控():
    sources = "".join(p.read_text(encoding="utf-8") for p in _ALL_SOURCE_FILES)
    assert sources.count("SET-GAP-不存在的一筆") == 0


def test_fixtures的欄位照44第四節():
    tables = dict(_spec_tables_from_44())
    dataset = fixtures.scenario("ok")
    for table in ("nav", "dividend", "market_indicator", "user_setting", "fetch_log"):
        assert dataset[table], table
        for row in dataset[table]:
            assert set(row) == set(tables[table]), table
    for row in fixtures.scenario("first")["user_setting"]:
        assert row["setting_value"] is None and row["updated_at"] is None
    for row in dataset["user_setting"]:
        assert row["setting_value"] is None or isinstance(row["setting_value"], str)  # 44 4.5：字串形式
    for row in dataset["fetch_log"]:
        assert row["source_tier"] in fixtures.TIERS and row["outcome"] in ("ok", "failed")
