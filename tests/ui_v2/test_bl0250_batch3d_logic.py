# -*- coding: utf-8 -*-
"""BL-0250 批次 3-D：新設計 B「卡片安靜收起」（客戶 2026-10-19 核准 `DEC-2026-10-19-05`；2026-10-21 核准進入 3-D 並裁示
Decision Gate Q1～Q4，`docs/DECISIONS.md` `DEC-2026-10-21-03`、`-04`；唯一正式定義：線框 `docs/v2/61_bl0250_batch3_wireframe.md`
1.4；落字 `docs/v2/44_fund_ui_ssot.md` 第七節第三小節之十五）。not-slow 線。

本檔守：
1. **觸發條件**（純函式 `ui_v2/sections.py::quiet_view`）：全 ⛔、全 ◇、⛔＋◇ 混合 → 收；部分讀不到 → 不收；全 ⬜ → 不收；
   ◷ → 不收；⛔＋⬜ 非同源 → 收且 ⬜ 保留一行（客戶 Q2 (a)）；同源衍生的 ⬜ 不畫；原因行每種一行、不合併不同種。
2. **不收起的保守退路**：收集出錯、原因項目找不到、持倉體檢逐檔分組掛著判讀證據（3-D 停手項）。
3. **四頁實際情境**：哪幾張卡收起、原因行逐字；卡數不變（收起的卡仍是一張卡）；不只靠顏色（原因行帶符號＋文字，⛔ 紅）。
4. **頁首與 `SET-8` 輸出不變**：同一情境把收起關掉（＝3-C 現況）再畫一次，頁首每一行與總表記錄逐字相同。
5. **四個符號個數守衛重定**：逐情境比對收起前（3-C 現況）與收起後，每一個消失或新增的符號都歸到「被原因行取代的主值或重複行」
   「同源衍生 ⬜」「原因行」三類之一；其餘一個不差。
6. **示範模式不經過收起**：示範模式畫頁時收起判定一次都沒被呼叫。
7. **設定與診斷 `SET-1`**：只拿掉表格下面與表內逐字重複的那一行（線框 6.2），卡不收起；示範模式照舊。
"""

from __future__ import annotations

import copy
import html
import pathlib
import re
import sys

import pytest

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
for _p in (_HERE, _HERE.parent, _ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

import _plain_scan as SCAN  # noqa: E402

from ui_v2 import health, page_health as PH, sections as S  # noqa: E402

_TAG = re.compile(r"<[^>]+>")
_STYLE = re.compile(r"<style>.*?</style>", re.S)


def _visible(value: str) -> str:
    return " ".join(html.unescape(_TAG.sub(" ", _STYLE.sub(" ", value or ""))).split())


# ═══════════════════════ 0. 鏡像常數 ═══════════════════════


def test_鏡像常數與health真身逐字相同():
    assert S.LINE_BLOCK_UNDECIDABLE == health.LINE_BLOCK_UNDECIDABLE
    assert S.LINE_FETCH_FAILED == health.LINE_FETCH_FAILED
    assert S.LINE_NOT_CONFIGURED == health.LINE_NOT_CONFIGURED
    assert S.LINE_SETTINGS_UNREADABLE == health.LINE_SETTINGS_UNREADABLE
    assert S.LINE_MISSING == f"{health.SYMBOL_MISSING} {health.TEXT_MISSING}"
    assert (S.TEXT_FETCH_FAILED, S.TEXT_MISSING, S.TEXT_NOT_CONFIGURED) == (
        health.TEXT_FETCH_FAILED, health.TEXT_MISSING, health.TEXT_NOT_CONFIGURED)
    # 尚未設定那一行的字與 3-A／3-C 既有的 `not_configured_reason` 同一套（多項以「、」連接）
    assert f"{S.LINE_NOT_CONFIGURED}：A、B" == f"{health.SYMBOL_ERROR} {health.not_configured_reason('A', 'B')}"
    assert S.QUIET_MARK == "（暫時收起）"
    assert S.QUIET_CODES == {"mkt": ("MKT-1", "MKT-2", "MKT-3"), "hld": ("HLD-1", "HLD-2", "HLD-3"),
                             "exp": ("EXP-1",), "alo": ("ALO-2", "ALO-3")}     # 線框附錄 2 P3 影響塊（SET-1 另走 6.2）


# ═══════════════════════ 1. 觸發條件（純函式） ═══════════════════════


def _mv(label, text, state, notes=()):
    node = {"label": label, "value_text": text, "_state": state}
    if notes:
        node["note_lines"] = list(notes)
    return node


def _mkt_card(*values, detail=()):
    return {"code": "MKT-1", "title": "風險情緒卡", "main_values": list(values), "detail_lines": list(detail)}


def _items(*specs):
    """`(種類, 鍵, 卡名, 項目名)` → 收集那一步的原因項目（只放本檔用得到的欄位）。"""
    out = []
    for kind, key, card, label in specs:
        out.append(PH.make_item(kind, key, [PH.affected(card, label, core=True, unreadable=True)]))
    return out


_FETCH = PH.KIND_FETCH
_UNCONF = PH.KIND_UNCONFIGURED
_MISS = PH.KIND_MISSING
_ERR = ("⛔ 此區塊暫時無法判定", "系統錯誤")
_GONE = ("◇ 資料未備", "資料未備")


def test_全部取數失敗_收起_原因行寫值名():
    card = _mkt_card(_mv("波動度指數", *_ERR), _mv("高收益信用利差", *_ERR))
    view, hold = S.quiet_view(card, _items((_FETCH, "市場指標", "風險情緒卡", "波動度指數"),
                                           (_FETCH, "市場指標", "風險情緒卡", "高收益信用利差")), "mkt")
    assert hold is None and [l["text"] for l in view["lines"]] == ["⛔ 取數失敗：波動度指數、高收益信用利差"]
    assert view["lines"][0]["_tone"] == "紅" and view["mark"] == "（暫時收起）"


def test_全部資料未備_收起_原因句接在原因行下():
    card = _mkt_card(_mv("領先指標", *_GONE, notes=["原因：來源不提供公布日"]),
                     _mv("同時指標", *_GONE, notes=["原因：來源不提供公布日"]))
    view, _ = S.quiet_view(card, _items((_MISS, "市場指標", "風險情緒卡", "領先指標")), "mkt")
    assert [(l["text"], l["_tone"]) for l in view["lines"]] == [
        ("◇ 資料未備：領先指標、同時指標", "灰"), ("原因：來源不提供公布日", "灰")]


def test_資料未備兩種原因句不合併_各一行():
    card = _mkt_card(_mv("A", *_GONE, notes=["原因：甲"]), _mv("B", *_GONE, notes=["原因：乙"]))
    view, _ = S.quiet_view(card, _items((_MISS, "市場指標", "風險情緒卡", "A")), "mkt")
    assert [l["text"] for l in view["lines"]] == ["◇ 資料未備：A", "原因：甲", "◇ 資料未備：B", "原因：乙"]


def test_取數失敗加尚未設定加資料未備混合_收起_每種一行_依值在卡上的順序():
    card = _mkt_card(_mv("政策利率", *_ERR), _mv("匯率", *_GONE, notes=["原因：規則未定"]), _mv("波動度指數", *_ERR))
    items = _items((_UNCONF, "資料來源的金鑰", "風險情緒卡", ""), (_MISS, "市場指標", "風險情緒卡", "匯率"),
                   (_FETCH, "市場指標", "風險情緒卡", "波動度指數"))
    view, _ = S.quiet_view(card, items, "mkt")
    assert [l["text"] for l in view["lines"]] == [
        "⛔ 尚未設定：資料來源的金鑰", "◇ 資料未備：匯率", "原因：規則未定", "⛔ 取數失敗：波動度指數"]


def test_只有部分讀不到_不收起():
    card = _mkt_card(_mv("波動度指數", *_ERR), _mv("高收益信用利差", "3.45", "ok"))
    assert S.quiet_view(card, _items((_FETCH, "市場指標", "風險情緒卡", "波動度指數")), "mkt") == (None, None)


def test_主值全部是方框_不收起():
    card = _mkt_card(_mv("A", "⬜ 不適用：單位不符", "業務例外"), _mv("B", "⬜ 不適用：單位不符", "業務例外"))
    assert S.quiet_view(card, [], "mkt") == (None, None)


def test_頁上畫成方框的值_即使狀態記資料未備_也不算讀不到():
    """與總表同一條讀法（`health.drawn_box`：頁上畫 ⬜ 的不計數，3-B 第二輪稽核回修 B）：收起看的是畫出來的符號，不另判。"""
    card = _mkt_card(_mv("A", "⬜ 無法判定（資料未備：x）", "資料未備"), _mv("B", "⬜ 無法判定（資料未備：y）", "資料未備"))
    assert S.quiet_view(card, _items((_MISS, "市場指標", "風險情緒卡", "A")), "mkt") == (None, None)


def test_讀得到但不是最新_不收起():
    card = _mkt_card(_mv("A", *_ERR), _mv("B", "18.8", "ok"))
    card["main_values"][1]["badges"] = [{"_kind": "新鮮度", "text": "◷ 延遲 3 日"}]
    assert S.quiet_view(card, _items((_FETCH, "市場指標", "風險情緒卡", "A")), "mkt") == (None, None)


def test_取數失敗加非同源方框_收起_方框照留一行():
    card = _mkt_card(_mv("波動度指數", *_ERR), _mv("高收益信用利差", "⛔ 尚未設定：資料來源的金鑰", "系統錯誤"),
                     detail=["⬜ 不適用（尚未設定：設定試算表）"])
    items = _items((_FETCH, "市場指標", "風險情緒卡", "波動度指數"), (_UNCONF, "資料來源的金鑰", "風險情緒卡", ""))
    view, _ = S.quiet_view(card, items, "mkt")
    assert [l["text"] for l in view["lines"]] == ["⛔ 取數失敗：波動度指數", "⛔ 尚未設定：資料來源的金鑰"]
    assert S.quiet_keep(view, "⬜ 不適用（尚未設定：設定試算表）")          # 設定試算表不是這張卡的原因 → 照留


def test_同源衍生的方框與重複行不畫_其餘照畫():
    view = {"unconfigured": ["資料來源的金鑰"], "fetch": True, "missing": False}
    assert not S.quiet_keep(view, "⬜ 不適用（尚未設定：資料來源的金鑰）")
    assert not S.quiet_keep(view, "⬜ 不適用：取數失敗，比較值不計算")
    assert S.quiet_keep(view, "⬜ 不適用：資料未備")                           # 這張卡沒有資料未備那一種原因
    for dup in (S.LINE_BLOCK_UNDECIDABLE, S.LINE_FETCH_FAILED, S.LINE_NOT_CONFIGURED, S.LINE_SETTINGS_UNREADABLE,
                S.LINE_MISSING, "⛔ 尚未設定：資料來源的金鑰"):
        assert not S.quiet_keep(view, dup), dup
    for evidence in ("⛔ 另有 3 檔的門檻指標取數失敗，未列入", "⛔ AAAA 取數失敗", "⛔ 尚未設定：別的設定",
                     "⛔ 淨值 取數失敗：AAAA：改用 2026-09-18 的預存淨值", "最大回撤在下方「詳細資料」"):
        assert S.quiet_keep(view, evidence), evidence
    assert S.quiet_keep(None, S.LINE_BLOCK_UNDECIDABLE)                        # 沒收起 → 一律照畫


def test_沒有值名的頁_原因行寫收集記下的資料類():
    block = {"code": "ALO-2", "title": "目標對照卡", "_rows": [],
             "placeholder": {"text": "⛔ 此區塊暫時無法判定", "_empty_kind": "系統錯誤"}}
    view, _ = S.quiet_view(block, _items((_FETCH, "持倉", "目標對照卡", "")), "alo")
    assert [l["text"] for l in view["lines"]] == ["⛔ 取數失敗：持倉"]          # 線框 5.2 例
    rows = dict(block, _rows=[{"bucket_text": "核心"}])
    assert S.quiet_view(rows, _items((_FETCH, "持倉", "目標對照卡", "")), "alo") == (None, None)


def test_原因項目找不到_不收起_退回現況():
    card = _mkt_card(_mv("A", *_ERR), _mv("B", *_GONE))
    assert S.quiet_view(card, _items((_FETCH, "市場指標", "風險情緒卡", "A")), "mkt") == (None, S.QUIET_HOLD_NO_ITEM)
    assert S.quiet_view(card, _items((_FETCH, "市場指標", "別的卡", "A")), "mkt")[0] is None


def test_持倉體檢逐檔分組掛著判讀證據_不收起_停手項():
    group = {"head_text": "基金 A", "freshness_note": {"text": "最近一筆淨值 2026-09-18，已超過 10 日"},
             "main_values": [{"label": "區間報酬率", "text": "◇ 資料未備", "_state": "資料未備"}]}
    block = {"code": "HLD-2", "title": "績效與風險卡", "fund_groups": [group]}
    assert S.quiet_view(block, _items((_MISS, "淨值", "績效與風險卡", "")), "hld") == (None, S.QUIET_HOLD_EVIDENCE)
    bare = copy.deepcopy(block)
    bare["fund_groups"][0]["freshness_note"] = None
    assert S.quiet_view(bare, _items((_MISS, "淨值", "績效與風險卡", "")), "hld")[0]["lines"][0]["text"] == "◇ 資料未備：淨值"


def test_收集出錯_一張都不收起():
    display = {"blocks": [_mkt_card(_mv("A", *_ERR))]}
    assert S.quiet_cards(display, {"error": "ValueError"}, "mkt") == ({}, {"MKT-1": "收集那一步出錯",
                                                                          "MKT-2": "收集那一步出錯",
                                                                          "MKT-3": "收集那一步出錯"})
    assert S.quiet_cards(display, {"items": []}, "set") == ({}, {})            # 設定與診斷頁不收卡（6.2 另走）


def test_設定與診斷資料新鮮度卡_只挑出逐字重複的那一行():
    block = {"_rows": [{"at_text": "⛔ 尚未設定：試算表 ID"}, {"at_text": "◇"}],
             "fail_nodes": [{"text": "⛔ 尚未設定：試算表 ID"}, {"text": "⛔ 取數失敗：別的原因"}, None]}
    assert S.set1_duplicate_fail_nodes(block) == [{"text": "⛔ 尚未設定：試算表 ID"}]


# ═══════════════════════ 3～5. 四頁實際情境 ═══════════════════════

# 收起後畫面上的原因行（逐字，依序）；不在表上的卡不收起。
_EXPECTED = {
    ("mkt", "未設定"): {
        "MKT-1": ["⛔ 取數失敗：波動度指數", "⛔ 尚未設定：資料來源的金鑰"],
        "MKT-2": ["◇ 資料未備：領先指標、同時指標", "原因：來源不提供公布日"],
        "MKT-3": ["⛔ 尚未設定：資料來源的金鑰", "◇ 資料未備：新臺幣對美元匯率", "原因：本指標規則未定，暫不顯示"],
    },
    ("mkt", "取數失敗"): {"MKT-2": ["◇ 資料未備：領先指標、同時指標", "原因：來源不提供公布日"]},
    ("hld", "未設定"): {
        "HLD-1": ["⛔ 尚未設定：保單試算表、設定試算表"],
        "HLD-2": ["⛔ 尚未設定：保單試算表、設定試算表"],
        "HLD-3": ["⛔ 尚未設定：保單試算表、設定試算表"],
    },
    ("hld", "取數失敗"): {"HLD-3": ["⛔ 取數失敗：配息"]},
    ("hld", "局部失敗"): {"HLD-1": ["⛔ 取數失敗：淨值、配息"], "HLD-2": ["⛔ 取數失敗：淨值"], "HLD-3": ["⛔ 取數失敗：配息"]},
    ("hld", "超過10日"): {"HLD-1": ["◇ 資料未備：淨值"]},
    ("hld", "退回預存過期"): {"HLD-1": ["⛔ 取數失敗：淨值"]},
    ("exp", "未設定"): {"EXP-1": ["⛔ 尚未設定：設定試算表"]},
    ("exp", "取數失敗"): {"EXP-1": ["⛔ 取數失敗：使用者設定"]},
    ("alo", "未設定"): {"ALO-2": ["⛔ 尚未設定：設定試算表"], "ALO-3": ["⛔ 尚未設定：設定試算表"]},
    ("alo", "未設定保單"): {"ALO-2": ["⛔ 尚未設定：保單試算表"], "ALO-3": ["⛔ 尚未設定：保單試算表"]},
    ("alo", "取數失敗"): {"ALO-2": ["⛔ 取數失敗：持倉"], "ALO-3": ["⛔ 取數失敗：持倉"]},
    ("alo", "局部失敗"): {"ALO-2": ["⛔ 取數失敗：市場指標"], "ALO-3": ["⛔ 取數失敗：市場指標"]},
}
# 主值全部讀不到、但依保守退路不收起的（3-D 停手項：逐檔判讀證據收起後放哪裡，1.4 沒有定）。
_HELD = {("hld", "超過10日"): {"HLD-2": S.QUIET_HOLD_EVIDENCE},
         ("hld", "退回預存過期"): {"HLD-2": S.QUIET_HOLD_EVIDENCE}}

_PAGES = ("mkt", "hld", "exp", "alo")
_CASES = [(page, name) for page in _PAGES for name in SCAN.SCRIPTS[page] if name != "整頁失敗"]

# 把收起關掉（＝3-C 現況）：收起判定回空，畫法走原本那一支。
_OFF = """
from ui_v2 import sections as _S3D
_S3D.quiet_cards = lambda *_a, **_k: ({}, {})
"""
# 記下每一次收起判定的結果（不改行為）。
_SPY = """
from ui_v2 import sections as _S3D
_real_quiet = _S3D.quiet_cards
_QUIET_LOG = []
def _spy_quiet(display, collected, page, *rest):
    out = _real_quiet(display, collected, page, *rest)
    _QUIET_LOG.append((page, out))
    import streamlit as _st
    _st.session_state["_test_quiet_log"] = list(_QUIET_LOG)
    return out
_S3D.quiet_cards = _spy_quiet
"""


def _wrap(prefix: str, script: str) -> str:
    """AppTest 與 pytest 同一個行程：換掉的 `sections` 函式一律在 finally 換回來，不汙染之後的測試。"""
    if not prefix:
        return SCAN._HEAD + script
    body = "\n".join("    " + line for line in script.split("\n"))
    return (SCAN._HEAD + "from ui_v2 import sections as _S3D_SAVE\n"
            "_SAVED_3D = (_S3D_SAVE.quiet_cards, _S3D_SAVE.set1_duplicate_fail_nodes)\n" + prefix
            + "try:\n" + body + "\nfinally:\n"
            "    _S3D_SAVE.quiet_cards, _S3D_SAVE.set1_duplicate_fail_nodes = _SAVED_3D\n")


def _run(script, prefix=""):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(_wrap(prefix, script), default_timeout=180)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


@pytest.fixture(scope="module")
def runs():
    """每個情境畫兩次：收起（現況）與關掉收起（3-C 現況），之後各條斷言共用。"""
    cache = {}

    def get(page, name):
        key = (page, name)
        if key not in cache:
            script = SCAN.SCRIPTS[page][name]
            cache[key] = (_run(script, _SPY), _run(script, _OFF))
        return cache[key]

    return get


def _card_markdowns(at):
    """`data-block` → 該塊畫出的 markdown（依序；一塊可能跨好幾枚，取到下一個 data-block 或下一個段標籤為止）。"""
    out, current = {}, None
    for node in _walk(at._tree):
        if type(node).__name__ != "Markdown":
            continue
        match = re.search(r'data-block="([^"]+)"', node.value)
        if match:
            current = match.group(1)
        elif "layer-label" in node.value or "v2-attention" in node.value:
            current = None
        if current:
            out.setdefault(current, []).append(node.value)
    return out


def _walk(node):
    yield node
    for child in getattr(node, "children", {}).values():
        yield from _walk(child)


@pytest.mark.parametrize("page, name", _CASES)
def test_收起的卡與原因行逐字_不在表上的卡不收起(runs, page, name):
    at, _off = runs(page, name)
    log = at.session_state["_test_quiet_log"]
    assert len(log) == 1 and log[0][0] == page
    views, holds = log[0][1]
    assert {code: [l["text"] for l in v["lines"]] for code, v in views.items()} == _EXPECTED.get((page, name), {})
    assert holds == _HELD.get((page, name), {})
    marks = [code for code, parts in _card_markdowns(at).items() if S.QUIET_MARK in _visible(parts[0])]
    assert sorted(marks) == sorted(_EXPECTED.get((page, name), {}))


@pytest.mark.parametrize("page, name", [k for k in _EXPECTED])
def test_收起的卡仍是一張卡_卡數不變_原因行帶符號與文字_紅色只是輔助(runs, page, name):
    at, off = runs(page, name)
    before, after = _card_markdowns(off), _card_markdowns(at)
    assert list(before) == list(after)                                    # 每一塊都還在，順序不變（不刪、不隱藏）
    for code, lines in _EXPECTED[(page, name)].items():
        joined = "".join(after[code])
        assert f'data-block="{code}"' in after[code][0]
        found = re.findall(r'<div class="([^"]*\b[a-z]+-quiet-line)"(?: style="([^"]*)")?>([^<]*)</div>', joined)
        assert [html.unescape(t) for _c, _s, t in found] == lines
        for css, style, text in found:
            text = html.unescape(text)
            if text.startswith("⛔ "):
                # ⛔ 照舊紅：市場總覽、持倉體檢、資產配置寫在樣式裡（該頁 theme 的紅）；標的探索沿用本頁失敗行那一格（`exp-fetchfail`，
                # 收起前「⛔ 此區塊暫時無法判定」就畫在那裡，色票由該頁 theme 的錯誤訊息前景色撐起）
                color = re.search(r"#[0-9A-Fa-f]{3,8}", style or "")
                assert ("exp-fetchfail" in css) if page == "exp" else (color and color.group(0).lower() in _reds(page)), (
                    code, text, css, style)
            assert text.split(" ", 1)[0] in ("⛔", "◇") or text.startswith("原因：")   # 符號＋文字，不只靠顏色
        assert S.QUIET_MARK in _visible(after[code][0])


def _reds(page):
    import importlib

    theme = importlib.import_module(f"ui_v2.{page}.theme")
    return {theme.tone_hex("紅").lower()}


def _header_lines(at):
    heads = [m.value for m in at.main.markdown if 'class="v2-status-line"' in m.value]
    return heads


@pytest.mark.parametrize("page, name", _CASES)
def test_頁首與總表記錄與3C現況逐字相同(runs, page, name):
    at, off = runs(page, name)
    assert _header_lines(at) == _header_lines(off)
    entry, base = at.session_state[PH.STATE_KEY][page], off.session_state[PH.STATE_KEY][page]
    strip = lambda e: {k: v for k, v in e.items() if k != "at"}  # noqa: E731  記錄時間（每次開頁都不同）以外逐欄相同
    assert strip(entry) == strip(base)
    rows = lambda at_: [strip(r) for r in PH.summary_rows(at_.session_state[PH.STATE_KEY])]  # noqa: E731
    assert rows(at) == rows(off)
    assert [tuple(r) for r in PH.detail_rows(entry)] == [tuple(r) for r in PH.detail_rows(base)]


# ── 5. 四個符號 ──

def _count(texts):
    out = [0, 0, 0, 0]
    for text in texts:
        for i, symbol in enumerate("⛔◇⬜◷"):
            out[i] += text.count(symbol)
    return tuple(out)


def _symbols(at):
    """同 3-C 守衛的量法（`test_bl0250_batch3c_logic.py::_symbols`）：Markdown 去標籤、Caption、元件標籤；不含頁首。"""
    import test_bl0250_batch3c_logic as T3C

    return T3C._symbols(at)


# 3-D 前後各情境 (⛔, ◇, ⬜, ◷) 的差（後 − 前）與歸類。前 ＝ 3-C 守衛釘住的值（`test_bl0250_batch3c_logic._SYMBOLS_BEFORE`）。
# 歸類：「主值」＝被原因行取代的主值本身（主值位置的 ⛔／◇）；「重複行」＝「⛔ 此區塊暫時無法判定」那一種被原因行取代的狀態族句；
# 「原因行」＝收起後新畫的原因行；「同源 ⬜」＝由同一原因衍生的 ⬜（本機情境沒有這一種，件數 0）。
_DIFF = {
    "mkt/未設定": (0, -1, 0, 0),       # MKT-1：⛔×2 主值 → ⛔×2 原因行；MKT-2：◇×2 主值 → ◇×1 原因行；MKT-3：⛔＋◇ → ⛔＋◇
    "mkt/取數失敗": (0, -1, 0, 0),     # MKT-2：◇×2 主值 → ◇×1 原因行
    "hld/未設定": (-1, 0, 0, 0),       # HLD-1：佔位 ⛔＋重複行 ⛔ → ⛔×1；HLD-2、HLD-3：重複行 ⛔ → ⛔×1
    "hld/取數失敗": (-6, 0, 0, 0),     # HLD-3：主值 ⛔×6＋重複行 ⛔ → ⛔×1
    "hld/局部失敗": (-12, 0, 0, 0),    # HLD-2、HLD-3：各主值 ⛔×6＋重複行 → ⛔×1；HLD-1：佔位 ⛔ → ⛔×1（卡尾判讀證據 ⛔×4 照留）
    "hld/超過10日": (0, 0, 0, 0),      # HLD-1：佔位 ◇ → ◇×1（卡尾判讀證據 ◇ 照留）；HLD-2 依退路不收
    "hld/退回預存過期": (0, 0, 0, 0),  # HLD-1：佔位 ⛔ → ⛔×1（卡尾 ⛔×2、◇×1 判讀證據照留）；HLD-2 依退路不收
    "exp/未設定": (0, 0, 0, 0),        # EXP-1：重複行 ⛔ → ⛔×1
    "exp/取數失敗": (0, 0, 0, 0),
    "alo/未設定": (0, 0, 0, 0),        # ALO-2、ALO-3：佔位 ⛔ → ⛔×1（各一）
    "alo/未設定保單": (0, 0, 0, 0),
    "alo/取數失敗": (0, 0, 0, 0),
    "alo/局部失敗": (0, 0, 0, 0),
}


@pytest.mark.parametrize("page, name", _CASES + [("hld", "整頁失敗"), ("alo", "整頁失敗")])
def test_四個符號_收起前後的差逐情境釘住_而且只出在收起的卡上(runs, page, name):
    import test_bl0250_batch3c_logic as T3C

    at, off = runs(page, name)
    key = f"{page}/{name}"
    before, after = _symbols(off), _symbols(at)
    assert before == T3C._SYMBOLS_BEFORE[key]                              # 關掉收起 ＝ 3-C 現況（3-C 守衛同一張表）
    assert tuple(a - b for a, b in zip(after, before)) == _DIFF.get(key, (0, 0, 0, 0))
    # 差只出在收起的卡上：未收起的卡逐塊符號個數相同。
    cards_before, cards_after = _card_markdowns(off), _card_markdowns(at)
    quiet = set(_EXPECTED.get((page, name), {}))
    for code in cards_before:
        if code not in quiet:
            assert _count(map(_visible, cards_after[code])) == _count(map(_visible, cards_before[code])), code


@pytest.mark.parametrize("page, name", [k for k in _EXPECTED])
def test_四個符號_收起的卡上每一個消失的符號都歸得了類(runs, page, name):
    """收起的卡：後 ＝ 前 − 主值與它身上的字 − 被原因行取代的重複行 − 同源 ⬜ ＋ 原因行；照留的每一句前後都在。"""
    at, off = runs(page, name)
    log = at.session_state["_test_quiet_log"][0][1][0]
    before, after = _card_markdowns(off), _card_markdowns(at)
    for code, view in log.items():
        text_before = " ".join(map(_visible, before[code]))
        text_after = " ".join(map(_visible, after[code]))
        reasons = _count(l["text"] for l in view["lines"])
        dropped = [d for d in (S.LINE_BLOCK_UNDECIDABLE, S.LINE_FETCH_FAILED, S.LINE_NOT_CONFIGURED, S.LINE_MISSING)
                   if d in text_before]
        # 卡上沒有任何 ⬜ 在收起時消失（本機情境沒有同源 ⬜；非同源 ⬜ 照留 —— 客戶 Q2 (a)）
        assert text_after.count("⬜") == text_before.count("⬜"), code
        # 不在主值、重複行之列的 ⛔／◇ 句（判讀證據）原樣都在
        for sentence in re.findall(r"[⛔◇] 另有 \d+ 檔[^。]*?未列入|⛔ [A-Z]{4} 取數失敗|⛔ 淨值 取數失敗：[^ ]+ 的預存淨值",
                                   text_before):
            assert sentence in text_after, (code, sentence)
        # 收起之後卡上的 ⛔／◇ ＝ 原因行 ＋ 照留的判讀證據句；一個都不多
        kept = _count(re.findall(r"[⛔◇] 另有 \d+ 檔|⛔ [A-Z]{4} 取數失敗|⛔ 淨值 取數失敗", text_after))
        assert _count([text_after])[:2] == tuple(r + k for r, k in zip(reasons[:2], kept[:2])), (code, dropped)


# ═══════════════════════ 6. 示範模式 ═══════════════════════

_DEMO_RAISE = """
from ui_v2 import sections as _S3D
def _boom(*_a, **_k):
    raise AssertionError("示範模式不得經過收起判定")
_S3D.quiet_cards = _boom
"""


@pytest.mark.parametrize("page", ["mkt", "hld", "exp", "alo"])
def test_示範模式不經過收起判定(page):
    _run(f"from ui_v2.{page} import page\npage.render()\n", _DEMO_RAISE)


# ═══════════════════════ 7. 設定與診斷 SET-1（線框 6.2） ═══════════════════════



@pytest.mark.parametrize("name, sentence", [("未設定", "⛔ 尚未設定：試算表 ID"), ("取數失敗", "⛔ 尚未設定：Google 服務帳戶")])
def test_SET1只拿掉表下重複那一行_表格三列照留(name, sentence):
    on = _run(SCAN.SET[name])
    off = _run(SCAN.SET[name], """
from ui_v2 import sections as _S3D
_S3D.set1_duplicate_fail_nodes = lambda block: []
""")
    table_on = next(m.value for m in on.main.markdown if 'class="set-table"' in m.value and "最近取得時間" in m.value)
    table_off = next(m.value for m in off.main.markdown if 'class="set-table"' in m.value and "最近取得時間" in m.value)
    assert table_on == table_off and html.unescape(table_on).count(sentence) == 2   # 淨值、市場指標兩列照留
    under_on = [v for v in _card_markdowns(on)["SET-1"] if 'class="set-empty"' in v and sentence in html.unescape(v)]
    under_off = [v for v in _card_markdowns(off)["SET-1"] if 'class="set-empty"' in v and sentence in html.unescape(v)]
    assert len(under_off) == 1 and under_on == []                                    # 表下那一行（重複）拿掉


def test_SET1示範模式照舊畫表下那一行():
    from ui_v2.set import fixtures as SF, logic as SL

    model = SL.build_page_model(SF.scenario("first"))
    block = SL.find_block(model, "SET-1")
    # 示範模式走 `ctx is None` 那一支，表下失敗行一行都不拿（畫面逐位元組守衛見 test_set_reshape_page）
    import inspect

    from ui_v2.set import page as SP

    src = inspect.getsource(SP._render_set1)
    assert "if ctx is None:\n        _placeholders(block[\"fail_nodes\"])" in src
    assert isinstance(block["fail_nodes"], list)
