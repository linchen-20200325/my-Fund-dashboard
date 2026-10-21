# -*- coding: utf-8 -*-
"""BL-0250 批次 3-C（客戶 2026-10-21 核准範圍與 Decision Gate Q1～Q5；`docs/DECISIONS.md` `DEC-2026-10-21-01`、`-02`；
`docs/v2/44_fund_ui_ssot.md` 第七節第三小節之十四；線框第六版 `docs/v2/61_bl0250_batch3_wireframe.md` 1.2 與第 7 節）。not-slow 線。

本檔守：
1. **U9 單一來源**：四頁頁首主要原因一行只經 `page_health.main_reason`（經 `header_view`），不存在第二套排序或句型；
   資料狀態行（`health.status_line`）與它專用的判讀已退場。
2. **頁首與設定與診斷頁總表逐字同源**：頁首主要原因 ＝ 總表「主要原因」欄；頁首「另有」＋主要原因那一項 ＝ 總表「狀態」欄。
3. **Q1**：只有使用者參數留空 → 頁首只寫「資料截至 ‹日期›」；參數留空＋同格真正資料缺口 → 那一類照算。
4. **四個符號**：各頁畫面上 ⛔／◇／⬜／◷ 的個數（頁首與被核准搬走的元素除外）與 3-C 動手前相同（凍結值取自 `ce6ffc32` 實測）。
5. **G2 搬遷**：被搬走的元素在功能頁不再出現、在目的地出現；判讀證據仍在；新設計 H；計價幣別出處長句進進階診斷。
6. **`_missing_string`**：產生處明確標記才認 ◇ 起頭的說明行（突變：拿掉標記，總表那一列就不見）。
7. **Q4**：設定與診斷頁 `SET-2`／`SET-6` 完全沒有取數紀錄時的收合標題；示範模式照舊。
"""

from __future__ import annotations

import ast
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

from ui_v2 import health, page_health as PH, plain, sections, symbols  # noqa: E402
from ui_v2.alo import fixtures as AF, logic as AL  # noqa: E402
from ui_v2.exp import live as EXL  # noqa: E402
from ui_v2.set import logic as SETL  # noqa: E402

_PAGES = ("mkt", "hld", "exp", "alo")
_CASES = [(page, name) for page in _PAGES for name in SCAN.SCRIPTS[page] if name != "整頁失敗"]
_TAG = re.compile(r"<[^>]+>")
_STYLE = re.compile(r"<style>.*?</style>", re.S)


def _app(script):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(script, default_timeout=180)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _header(at) -> list:
    """頁首那一枚（`class="v2-status-line"`）裡的每一行（內層 `<div>`），去標籤、還原字元參照。"""
    heads = [m.value for m in at.main.markdown if 'class="v2-status-line"' in m.value]
    assert len(heads) == 1, heads
    inner = heads[0].split('role="status">', 1)[1][: -len("</div>")]
    return [html.unescape(_TAG.sub("", line)) for line in re.findall(r"<div[^>]*>(.*?)</div>", inner)]


def _store(at):
    return at.session_state[PH.STATE_KEY]


def _visible(value: str) -> str:
    """畫面上看得到的字（不含 `title` 屬性）。"""
    return " ".join(html.unescape(_TAG.sub(" ", _STYLE.sub(" ", value or ""))).split())


# ═══════════════════════ 1. U9 單一來源（AST） ═══════════════════════


def _tree(rel):
    return ast.parse((_ROOT / rel).read_text(encoding="utf-8"))


def _calls(fn):
    out = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            out.add(ast.unparse(node.func))
    return out


def _function(rel, name):
    return next(n for n in ast.walk(_tree(rel)) if isinstance(n, ast.FunctionDef) and n.name == name)


def test_主要原因句型只住在_page_health_沒有第二套():
    """「主要原因：」那幾種句型（常值）全 `ui_v2` 只在 `page_health.py`；其他檔一個常值都沒有。"""
    offenders = []
    for path in sorted((_ROOT / "ui_v2").rglob("*.py")):
        if path.name == "page_health.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and "主要原因：" in node.value:
                offenders.append((path.name, node.value[:40]))
    assert offenders == []


def test_四頁頁首只經_header_view_而_header_view_只經_main_reason():
    view = _function("ui_v2/page_health.py", "header_view")
    assert {"main_reason", "other_counts", "count_parts"} <= _calls(view)
    assert "count_parts" in _calls(_function("ui_v2/page_health.py", "count_text"))
    header = _function("ui_v2/health_view.py", "render_page_header")
    assert "page_health.header_view" in _calls(header) and "page_health.main_reason" not in _calls(header)
    for page in _PAGES:
        tree = _tree(f"ui_v2/{page}/page.py")
        calls = [ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)]
        assert calls.count("health_view.render_page_header") == 1, page
        assert calls.count("health_view.record_page_health") == 1, page
        names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert not names & {"status_line", "render_status_line", "has_missing_marker", "has_stale_marker",
                            "render_provenance", "main_reason", "pick_main"}, (page, names)


def test_資料狀態行與它專用的判讀已退場():
    for name in ("status_line", "has_missing", "has_missing_marker", "has_stale_marker", "STATUS_LABEL", "TEXT_STALE",
                 "PROVENANCE_TITLE"):
        assert not hasattr(health, name), name
    from ui_v2 import health_view

    for name in ("render_status_line", "render_provenance"):
        assert not hasattr(health_view, name), name


def test_頁首色調表與單元測試的鏡像一致():
    from ui_v2 import health_view

    import test_health_logic as THL

    assert {k: THL.health_view_tone(k) for k in PH.KINDS} == health_view.OTHER_TONES


# ═══════════════════════ 2. 頁首 ＝ 總表（逐字同源） ═══════════════════════


@pytest.mark.parametrize("page, name", _CASES)
def test_頁首主要原因與總表逐字相同_另有加主要原因等於總表狀態(page, name):
    at = _app(SCAN.SCRIPTS[page][name])
    lines = _header(at)
    entry = _store(at)[page]
    row = next(r for r in PH.summary_rows(_store(at)) if r["slug"] == page)
    view = PH.header_view(entry, as_of=entry["as_of"])
    assert lines == view["lines"], (lines, view["lines"])          # 畫出來的就是 `header_view` 交出的那幾行
    if row["main"] == PH.NO_VALUE:
        assert lines == [f"{PH.AS_OF_LABEL} {entry['as_of'] or PH.AS_OF_UNKNOWN}"]
        assert row["status"] == lines[0]                           # 都沒有 → 兩邊都只寫資料截至日
        return
    assert view["main"] == row["main"] and lines[0].startswith(row["main"])
    by_kind = dict(PH.other_counts(entry["items"]))
    if not view["inline"]:
        main_kind = PH.pick_main(entry["items"])["kind"]
        by_kind[main_kind] = by_kind.get(main_kind, 0) + 1
        assert PH.count_text(by_kind) == row["status"], (by_kind, row["status"])
    for word in ("資料齊", "正常", "資料狀態："):
        assert word not in "".join(lines)
    assert lines[-1].endswith(f"{PH.AS_OF_LABEL} {entry['as_of'] or PH.AS_OF_UNKNOWN}")


def test_順位6一行寫完_不加符號():
    item = PH.make_item(PH.KIND_UNCONFIGURED, "設定試算表", [PH.affected("風險情緒卡", core=True, unreadable=False)])
    store = {}
    PH.record(store, "mkt", [item], as_of="2026-09-21", now="2026-10-21T00:00:00+00:00")
    view = PH.header_view(PH.recorded(store, "mkt"), as_of="2026-09-21")
    assert view["lines"] == ["尚未設定：設定試算表（只影響比較值）　資料截至 2026-09-21"] and view["inline"]
    assert view["main"] == PH.summary_rows(store[PH.STATE_KEY])[0]["main"]


def test_沒有記錄就畫頁首_報錯不猜():
    with pytest.raises(ValueError):
        PH.header_view(None, as_of=None)


# ═══════════════════════ 3. Q1 回歸 ═══════════════════════


@pytest.mark.parametrize("page, script, as_of", [
    ("exp", SCAN._exp(rules=[]), "2026-10-13"),                          # 沒有任何篩選條件（篩選軌跡「尚未設定條件」◇）
    ("exp", SCAN._exp(rules=[{"field": "mgmt_fee_rate_pct", "op": "大於", "value": ""}]), "2026-10-13"),
    ("alo", SCAN._alo("partial"), "2026-09-23"),                          # 目標比重＋情境試算金額留空
])
def test_Q1_只有使用者參數留空_頁首只寫資料截至日_件數0(page, script, as_of):
    at = _app(script)
    entry = _store(at)[page]
    keys = {i["key"] for i in entry["items"]}
    assert not keys & set(PH.SETTING_KEYS), keys
    if page == "alo":
        assert entry["items"] == []
        assert _header(at) == [f"資料截至 {as_of}"]
        assert any("◇" in _visible(m.value) for m in at.main.markdown if 'class="v2-status-line"' not in m.value)
    else:   # 標的探索這兩個情境另有真的取數失敗／資料未備（假資料本來就有），只驗設定鍵不進頁首
        assert "篩選條件" not in "".join(_header(at))


def test_Q1_參數留空加同格真正缺口_那一類照算():
    ds = copy.deepcopy(AF.scenario("nofx"))
    row = next(r for r in ds["user_setting"] if r["setting_key"] == "alo_target_weights")
    row["setting_value"][0]["weight_ratio"] = None
    display, _raw, status = plain.plain_model(AL.build_page_model(ds), page="alo")
    symbols.apply(display)
    display, failures = health.dedupe_failures(display)
    health.relabel_unconfigured(display, failures)
    cards = sections.health_cards([b["code"] for b in display["blocks"] if b.get("_layer") == 2], "alo")
    trace = []
    items, _u = health.collect_page_items(display, failures, status["fetch_events"], cards, trace=trace)
    store = {}
    PH.record(store, "alo", items, as_of="2026-09-23", now="2026-10-21T00:00:00+00:00")
    lines = PH.header_view(PH.recorded(store, "alo"), as_of="2026-09-23")["lines"]
    assert lines[0].startswith("◇ 主要原因：市場指標資料未備"), lines
    assert "目標比重" not in "".join(lines)
    # 3-C 總管裁定第 2 點：那幾個「一格兩種成因」的節點本身仍被收下（資料類那一筆在），只略過設定那一個鍵 ——
    # 「整個節點含設定鍵就略過」的過度略過，上面兩條斷言抓不到（同類別別的節點照樣撐起主要原因），這一條會轉紅。
    nodes = []
    health._walk_nodes(display, None, "", nodes)
    dual = [node for node, _block, _path, _private in nodes
            if set(node.get(PH.MISSING_KEYS_KEY) or ()) & set(PH.SETTING_KEYS)
            and set(node.get(PH.MISSING_KEYS_KEY) or ()) - set(PH.SETTING_KEYS)]
    assert len(dual) == 2, [n.get(PH.MISSING_KEYS_KEY) for n in dual]      # ALO-2、ALO-3 核心那一列
    hits = [(kind, key) for node_id, kind, key in trace if node_id in {id(n) for n in dual}]
    assert hits == [(PH.KIND_MISSING, "市場指標")] * 2, hits


def test_Q1_標的探索參數留空加未接線真缺口_真缺口照算():
    at = _app(SCAN._exp(wired=False, rules=[{"field": "mgmt_fee_rate_pct", "op": "大於", "value": ""}]))
    entry = _store(at)["exp"]
    assert {i["kind"] for i in entry["items"]} >= {PH.KIND_MISSING} and "篩選條件" not in {i["key"] for i in entry["items"]}
    assert _header(at)[0].startswith("◇ 主要原因：")


def _unexplained_display():
    """一塊尚未設定（有交代）＋一塊系統錯誤卻沒有任何一句摘要交代（3-C 總管裁定第 1 點）。"""
    display = {"blocks": [
        {"code": "HLD-1", "title": "偏離提示卡", "_layer": 2, "_state": "系統錯誤",
         "detail_lines": ["⛔ 保單與持倉 取數失敗：保單試算表尚未設定"]},
        {"code": "HLD-3", "title": "配息與本金卡", "_layer": 2, "_state": "系統錯誤", "detail_lines": ["⛔ 取數失敗"]},
    ]}
    return health.dedupe_failures(display)


def test_系統錯誤塊沒有原因項目點到_不整頁降級_其他原因照列_多一筆取數失敗():
    # 3-C 總管裁定第 1 點：~~收集報錯 → 頁首與總表都寫「⛔ 本頁狀態無法彙整」~~ → 記一筆取數失敗（鍵 `plain.DATA_CLASS_DEFAULT`，
    # base `ce6ffc32` 本函式認不出資料類那條退路已在用的字樣），其他原因照常收集。突變（改回拋錯）→ 本條轉紅。
    display, failures = _unexplained_display()
    items, unresolved = health.collect_page_items(display, failures, (), ["HLD-1", "HLD-3"])
    assert plain.DATA_CLASS_DEFAULT == "資料"
    assert sorted((i["kind"], i["key"]) for i in items) == sorted(
        [(PH.KIND_UNCONFIGURED, "保單試算表"), (PH.KIND_FETCH, plain.DATA_CLASS_DEFAULT)])
    assert [u["code"] for u in unresolved if u.get("unexplained")] == ["HLD-3"]
    store = {}
    PH.record(store, "hld", items, as_of="2026-09-23", now="2026-10-21T00:00:00+00:00")
    entry = PH.recorded(store, "hld")
    lines = PH.header_view(entry, as_of="2026-09-23")["lines"]
    assert lines == ["⛔ 主要原因：保單試算表尚未設定（1 張卡有值讀不到）", "另有：⛔ 取數失敗 1 項", "資料截至 2026-09-23"]
    assert PH.TEXT_COLLECT_FAILED not in "".join(lines)
    row = next(r for r in PH.summary_rows(store[PH.STATE_KEY]) if r["slug"] == "hld")
    assert row["main"] == lines[0] and row["status"] == "尚未設定 1 項　⛔ 取數失敗 1 項"
    assert [tuple(r) for r in PH.detail_rows(entry)] == [
        ("保單與持倉", "偏離提示卡", "⛔ 尚未設定：保單試算表", "—", "—", "—", "—"),
        ("資料", "配息與本金卡", "⛔ 取數失敗", "—", "—", "—", "—"),
    ]


def test_系統錯誤塊沒有原因項目點到_收集那一步寫warning_log_含塊代號(caplog):
    from ui_v2 import health_view

    display, failures = _unexplained_display()
    with caplog.at_level("WARNING", logger="ui_v2.health_view"):
        got = health_view.collect_page_health("hld", display, failures, (), ["HLD-1", "HLD-3"])
    assert "error" not in got and len(got["items"]) == 2
    messages = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert any("HLD-3" in m and "沒有任何原因項目點到" in m for m in messages), messages
    assert not any("認不出資料類" in m for m in messages), messages


# ═══════════════════════ 4. 四個符號的個數不變（頁首與被搬走的元素除外） ═══════════════════════

# 3-C 動手前（`ce6ffc32`，2026-10-21 本組以同一份腳本實測）各情境畫面上的 (⛔, ◇, ⬜, ◷) 個數：Markdown 去標籤（不含 `title`）、
# Caption 與元件標籤；**不含**頁首資料狀態行與 ④「核心卡的來源與新鮮度」那一枚（被核准搬走的元素）。
_SYMBOLS_BEFORE = {
    'mkt/正常': (0, 0, 3, 0),
    'mkt/未設定': (27, 4, 3, 0),
    'mkt/取數失敗': (2, 3, 3, 0),
    'mkt/局部失敗': (0, 7, 3, 0),
    'mkt/stale': (0, 0, 3, 0),
    'hld/正常': (0, 0, 4, 0),
    'hld/未設定': (13, 0, 1, 0),
    'hld/取數失敗': (24, 0, 1, 0),
    'hld/局部失敗': (46, 0, 1, 0),
    'hld/stale': (0, 0, 4, 4),
    'hld/超過10日': (0, 32, 5, 0),
    'hld/退回預存過期': (15, 21, 3, 0),
    'hld/整頁失敗': (1, 0, 0, 0),
    'exp/正常': (4, 12, 2, 0),
    'exp/未設定': (17, 0, 0, 0),
    'exp/取數失敗': (11, 0, 0, 0),
    'exp/局部失敗': (0, 15, 0, 0),
    'exp/stale': (4, 12, 14, 0),
    'alo/正常': (0, 0, 0, 0),
    'alo/未設定': (9, 0, 0, 0),
    'alo/未設定保單': (6, 0, 0, 0),
    'alo/取數失敗': (6, 0, 0, 0),
    'alo/局部失敗': (6, 0, 0, 0),
    'alo/stale': (0, 0, 0, 0),
    'alo/整頁失敗': (1, 0, 0, 0),
}


def _symbols(at):
    out = [0, 0, 0, 0]

    def walk(node):
        kind = type(node).__name__
        if kind == "Markdown" or kind == "Caption":
            value = node.value
            if 'class="v2-status-line"' in value:
                return
            texts = [_visible(value)]
        elif kind == "Expander":
            texts = [str(node.label)]
        else:
            texts = [v for v in (getattr(node, "label", None), getattr(node, "help", None),
                                 getattr(node, "placeholder", None)) if isinstance(v, str)]
            opts = getattr(node, "options", None)
            if kind in ("Selectbox", "Radio", "Multiselect") and opts:
                texts.append(" | ".join(map(str, opts)))
        for text in texts:
            for i, symbol in enumerate("⛔◇⬜◷"):
                out[i] += text.count(symbol)
        for child in getattr(node, "children", {}).values():
            walk(child)

    walk(at._tree)
    return tuple(out)


# BL-0250 批次 3-D（新設計 B；44 第七節第三小節之十五；客戶 `DEC-2026-10-21-04` Q1 授權依 3-D 新規格更新本守衛）：
# ~~直接量現況畫面~~ → 量「把收起關掉」的畫面（＝3-C 的畫法），3-C 這一條守的「搬遷前後個數相同」照舊逐情境釘住同一張表；
# 收起前後的差另由 `tests/ui_v2/test_bl0250_batch3d_logic.py` 逐情境釘住並逐一歸類（有意識的政策變更，不是漏刪）。
_QUIET_OFF = """
from ui_v2 import sections as _S3D
_S3D.quiet_cards = lambda *_a, **_k: ({}, {})
_S3D.quiet_details = lambda *_a, **_k: {}   # 規則 5（Q5 (b)）也關掉
"""


@pytest.mark.parametrize("key", sorted(_SYMBOLS_BEFORE))
def test_四個符號在頁上的個數與動手前相同(key):
    page, name = key.split("/")
    body = "\n".join("    " + line for line in SCAN.SCRIPTS[page][name].split("\n"))
    script = (SCAN._HEAD + "from ui_v2 import sections as _S3D_SAVE\n_SAVED_3D = (_S3D_SAVE.quiet_cards, _S3D_SAVE.quiet_details)\n" + _QUIET_OFF
              + "try:\n" + body + "\nfinally:\n    _S3D_SAVE.quiet_cards, _S3D_SAVE.quiet_details = _SAVED_3D\n")   # 同一個行程：用完換回來
    assert _symbols(_app(script)) == _SYMBOLS_BEFORE[key]


# ═══════════════════════ 5. G2 搬遷：功能頁不再出現、目的地出現、判讀證據仍在 ═══════════════════════

_RETIRED_TITLE = "核心卡的來源與新鮮度"   # 3-C 退場的那一枚展開區標題（只在本測試當作「不得出現」的字）


@pytest.mark.parametrize("page, name", _CASES)
def test_核心卡的來源與新鮮度不再畫在功能頁(page, name):
    at = _app(SCAN.SCRIPTS[page][name])
    assert not any(str(e.label) == _RETIRED_TITLE for e in at.main.expander)
    assert not any("v2-provenance" in m.value for m in at.main.markdown)


def _detail(at, page):
    return [tuple(r) for r in PH.detail_rows(_store(at)[page])]


def test_市場總覽核心卡的來源與延遲在總表明細():
    at = _app(SCAN.MKT["正常"])
    rows = {r[1]: r for r in _detail(at, "mkt")}
    assert rows["風險情緒卡　波動度指數"][5:] == ("延遲 3 日", "T2")
    assert rows["資金與匯率卡　新臺幣對美元匯率"][5:] == ("延遲 1 日", "T1")


@pytest.mark.parametrize("name", ["正常", "未設定", "取數失敗", "局部失敗", "stale"])
def test_持倉體檢淨值表的來源層級欄與逐檔延遲_功能頁拿掉_總表明細有(name):
    at = _app(SCAN.HLD[name])
    table = next(m.value for m in at.main.markdown if "淨值日期</th>" in m.value)
    assert "<th>來源層級</th>" not in table and "<th>推估</th>" in table      # 推估欄照留
    for box in at.main.expander:
        if str(box.label).startswith(("淨值與配息序列", "最大回撤與本金類配息佔比")):
            body = " ".join(_visible(m.value) for m in box.markdown)
            assert "延遲 10 日" not in body and "當日" not in body, box.label
    rows = {r[1]: r for r in _detail(at, "hld")}
    for code in ("AAAA", "BBBB", "CCCC"):
        row = rows[f"淨值與配息序列　{code}"]
        assert row[0] == "淨值" and row[6] == "淨值", row
    if name != "局部失敗":
        assert rows["淨值與配息序列　AAAA"][5] == "延遲 10 日"
    if name not in ("局部失敗", "未設定"):
        assert rows["績效與風險卡　基金 A · 幣別 USD"][5] == "延遲 10 日"   # 核心卡那一列照舊


def test_持倉體檢判讀證據仍在():
    stale = " ".join(_visible(m.value) for m in _app(SCAN.HLD["stale"]).main.markdown)
    assert "◷淨值取自預存序列，不是本次取得；最近一筆2026-09-18" in stale.replace(" ", "")
    old = _app(SCAN.HLD["超過10日"])
    text = " ".join(_visible(m.value) for m in old.main.markdown)
    assert "◇ 另有 3 檔淨值超過 10 日未更新（資料未備），未列入" in text
    assert "最近一筆淨值2026-09-18，已超過10日" in text.replace(" ", "")   # 日期那一段不斷行（另包一層），比對時去空白
    hld8 = next(b for b in old.main.expander if str(b.label).startswith("最大回撤與本金類配息佔比"))
    assert " ".join(_visible(m.value) for m in hld8.markdown).count("◇ 資料未備") >= 3   # ◇ 那一種徽章照留
    retreat = " ".join(_visible(m.value) for m in _app(SCAN.HLD["退回預存過期"]).main.markdown)
    assert "改用 2026-09-18 的預存淨值" in retreat
    normal = " ".join(_visible(m.value) for m in _app(SCAN.HLD["正常"]).main.markdown)
    assert "⬜ 不適用：配息類別未知" in normal and "推估" in normal


def _spy_exp(monkeypatch, script):
    seen = []
    real = EXL.result_cell_view

    def spy(key, cell):
        out = real(key, cell)
        seen.append((key, copy.deepcopy(cell), out))
        return out

    monkeypatch.setattr(EXL, "result_cell_view", spy)
    at = _app(script)
    return at, seen


@pytest.mark.parametrize("name", ["正常", "stale"])
def test_標的探索格內只留值_拿掉的段落必在每列展開或進階診斷_留下的在滑鼠提示(monkeypatch, name):
    at, seen = _spy_exp(monkeypatch, SCAN.EXP[name])
    table = html.unescape(next(m.value for m in at.main.markdown if '<div class="exp-scroll">' in m.value))
    assert 'class="exp-src"' not in table                                  # 格內不畫來源標示
    raw = [e["text"] for e in (at.session_state[plain.RAW_STATE]["exp"]["entries"])]
    removed_total = kept_total = 0
    for key, cell, view in seen:
        parts = [p for p in str(cell.get("source_tip") or "").split("；") if p]
        kept = [p for p in str(view["tip"] or "").split("；") if p]
        fetched, day, note = EXL.split_tip(cell.get("source_tip"), reason_in=EXL._h_reason(key, cell))
        for part in parts:
            if part in kept:
                kept_total += 1
                assert not part.startswith(EXL.SOURCE_NOTE_PREFIXES + ("取得時間：", "資料日期：")), part
                continue
            removed_total += 1
            if part.startswith("取得時間："):
                assert EXL.taipei_time_text(fetched) in table
            elif part.startswith("資料日期："):
                assert day == part[len("資料日期："):]
            elif part in note.split("；"):
                assert f"<td>{part}" in table or f"；{part}" in table                       # 在該列展開的備註裡
            else:   # 計價幣別出處長句的「原因：…」：原句在進階診斷
                assert key == EXL.CCY_COLUMN and part.startswith(EXL.TIP_REASON_HEAD), (key, part)
                assert any(part in text for text in raw), part
        if cell.get("source_tag"):
            assert f"<td>{cell['source_tag']}</td>" in table                          # 在該列展開的「來源」欄
    assert removed_total >= 30 and kept_total >= 10, (removed_total, kept_total)


def test_標的探索_快照列出的判定句與計數句留在格內滑鼠提示():
    at = _app(SCAN.EXP["正常"])
    titles = [html.unescape(t) for m in at.main.markdown if "exp-scroll" in m.value
              for t in re.findall(r' title="([^"]*)"', m.value) if '<div class="exp-scroll">' in m.value]
    joined = "\n".join(titles)
    for sentence in ("配息依據：FundClear（頁面 yp010000）：有配息列", "合庫配息頁（頁面 yp010000）：沒有配息紀錄",
                     "各來源皆認得本檔且無配息紀錄", "之間沒有配息", "截斷 3", "配息宣告的幣別與淨值幣別不同的除息日：",
                     "計價幣別未確定（基本資料各來源幣別缺或不一致），淨值與配息比不取數"):
        assert sentence in joined, sentence
    for gone in ("淨值來源：", "取得時間：", "資料日期：", "計價幣別出處（來源自報）：", "取數失敗的來源："):
        assert gone not in joined, gone


def test_計價幣別出處長句原句進進階診斷_遮蔽照舊():
    at = _app(SCAN.EXP["正常"])
    entries = at.session_state[plain.RAW_STATE]["exp"]["entries"]
    ccy = [e for e in entries if EXL.TIP_CCY_HEAD in e["text"]]
    assert {e["text"].split("：", 1)[0] for e in ccy} >= {"D04", "G07"}
    assert all(e["where"] == "EXP-2 候選清單卡" for e in ccy)
    assert any("原因：部分來源取數失敗，以其餘一致的來源為準（MoneyDJ：timeout）" in e["text"] for e in ccy)


def test_新設計H_配息比格內只留菱形_原因句在列展開_淨值超過10日那一種格內照舊():
    at = _app(SCAN.EXP["正常"])
    table = html.unescape(next(m.value for m in at.main.markdown if '<div class="exp-scroll">' in m.value))
    assert ">◇</td>" in table and ">◇ 資料未備：配息資料未確認完整，配息比不計算<" not in table
    assert "<td>合庫配息頁</td><td>—</td><td>—</td><td>配息來源：合庫配息頁；配息資料未確認完整，配息比不計算</td>" in table
    assert ">◇ 資料未備：最近一筆淨值 2026-10-03，已超過 10 日<" in table      # 原因句不在展開 → 格內照舊
    assert ">⬜ 不適用：配息幣別與淨值幣別不同<" in table                     # J10 的 ⬜ 屬判讀證據，不動


def test_result_cell_view_單元():
    cell = {"text": "◇ 資料未備：配息資料未確認完整，配息比不計算", "_state": "資料未備", "source_tag": "合庫配息頁",
            "source_tip": "配息來源：合庫配息頁；配息資料未確認完整，配息比不計算；配息依據：TCB：有配息列"}
    assert EXL.result_cell_view("div_ratio_pct", cell) == {
        "text": "◇", "tip": "配息資料未確認完整，配息比不計算；配息依據：TCB：有配息列"}
    same = dict(cell, text="◇ 資料未備：別的原因")
    assert EXL.result_cell_view("div_ratio_pct", same)["text"] == same["text"]     # 展開沒有這一句 → 格內照舊
    assert EXL.result_cell_view("nav_date", cell)["text"] == cell["text"]          # H 只管配息比
    ccy = {"text": "USD", "_state": "ok", "source_tip": "計價幣別出處（來源自報）：TDCC；取數失敗的來源：MoneyDJ；原因：X"}
    assert EXL.result_cell_view("ccy", ccy) == {"text": "USD", "tip": None}


# ═══════════════════════ 6. `_missing_string`：產生處明確標記（突變） ═══════════════════════

_NO_MARK = """
from ui_v2 import health as _H, page_health as _PH
_real_collect = _H.collect_page_items


def _strip_marks(node):
    if isinstance(node, dict):
        node.pop(_PH.MISSING_LINES_KEY, None)
        for value in node.values():
            _strip_marks(value)
    elif isinstance(node, (list, tuple)):
        for value in node:
            _strip_marks(value)


def _without_marks(display, *a, **k):
    _strip_marks(display)
    return _real_collect(display, *a, **k)


_H.collect_page_items = _without_marks
try:
"""


def test_拿掉產生處的說明行標記_總表那一列就不見_突變():
    """模擬「產生處沒有寫明欄位」：收集之前把標記拿掉 —— 淨值與配息序列表尾那一句（◇ 起頭）就不再被認成 ◇，總表那一列消失。
    證明收集那一步靠的是產生處的標記，不是字首。"""
    row = ("淨值", "淨值與配息序列", "◇ 資料未備", "—", "—", "—", "—")
    assert row in _detail(_app(SCAN.HLD["超過10日"]), "hld")
    body = "\n".join("    " + line for line in SCAN.HLD["超過10日"].split("\n"))
    script = SCAN._HEAD + _NO_MARK + body + "\nfinally:\n    _H.collect_page_items = _real_collect\n"
    without = _detail(_app(script), "hld")
    assert row not in without
    assert health.collect_page_items.__name__ == "collect_page_items"        # 已還原


def test_hld產生處兩處說明行都寫明欄位():
    from ui_v2.hld import fixtures as HF, logic as HL

    model = HL.build_page_model(**HF.scenario("full"))
    for code, field in (("HLD-1", "tail_lines"), ("HLD-6", "detail_lines")):
        block = HL.find_block(model, code)
        has_line = any(HL._NOT_READY_SUFFIX in line for line in block.get(field) or () if isinstance(line, str))
        assert (field in (block.get(PH.MISSING_LINES_KEY) or ())) == has_line
    assert "_missing_lines" in PH.MARK_KEYS


# ═══════════════════════ 7. Q4：SET-2／SET-6 完全沒有取數紀錄 ═══════════════════════


def test_Q4_SET2與SET6完全沒有取數紀錄_標題不露出表名_只此兩處():
    at = _app(SCAN.SET["正常"])
    labels = [str(e.label) for e in at.main.expander]
    assert "來源健康卡　—　◇ 尚無取數紀錄" in labels and "取數紀錄　—　尚無取數紀錄" in labels
    assert not any("fetch_log" in label for label in labels)


def test_Q4_示範模式照舊():
    from ui_v2.set import fixtures as SF

    # ~~`if hasattr(SF, "scenario") else None` → `pytest.skip(...)`~~：走不到的略過分支（`SF.scenario` 一直在），
    # 3-C 總管裁定第 4 點拿掉（有意識的更正，不是漏刪）。
    model = SETL.build_page_model(SF.scenario("first"))
    set6 = SETL.find_block(model, "SET-6")
    assert set6["summary_text"] == "缺 fetch_log：" + SETL.TEXT_NO_RECORDS
