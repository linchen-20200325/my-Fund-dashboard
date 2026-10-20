# -*- coding: utf-8 -*-
"""BL-0250 批次 3-B 第二輪兩組獨立稽核回修（50b1c513 之後；not-slow 線，不標 slow）。

條號照總管第二輪裁定：
A. 同一類淨值退回預存、各檔日期不同時，主要原因依日期分組；同一類另有沒預存可退的取數失敗，句尾點名；
B. 頁上畫 ⬜ 的格不計數，明細照抄頁上那一句（全情境守衛）；
C. 一般畫面不露出例外類別名（見 `test_bl0250_batch3b_audit_fix_logic.py` 第 3 條那幾條）；
D. 標的探索三張核心卡（同上檔第 4、5 條）；
E. 每列來源展開的備註只收來源段落與新設計 H 那一句（見 `test_bl0250_batch3b_logic.py`）；
可選 1. 明細表日期、時間、延遲、來源層級欄不放狀態字；
可選 2. 「◇ 另有 N 檔淨值超過…」那一句收集認得，明細出現在淨值與配息序列底下；
可選 3. 畫頁崩潰時總表不留上一筆正常記錄，照舊往上拋。
"""

from __future__ import annotations

import pathlib
import sys

import pytest

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
for _p in (_HERE, _HERE.parent, _ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from ui_v2 import health, page_health  # noqa: E402

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

import _plain_scan as SCAN  # noqa: E402

PH = page_health


def _app(script):
    at = AppTest.from_string(script, default_timeout=180)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _entry(script, page):
    at = _app(script)
    return at.session_state[PH.STATE_KEY][page]


# ═══════════════════════ A：退回預存依日期分組 ═══════════════════════


def _fetch(day=None, codes=(), no_retreat=()):
    return PH.make_item(PH.KIND_FETCH, "淨值", [PH.affected("績效與風險卡", core=True, unreadable=True)],
                        retreat={"day": day, "codes": list(codes)} if day else None, no_retreat=no_retreat)


def test_A_單一日期_照線框原句型():
    items = [_fetch("2026-09-18", ["AAAA"])]
    assert PH.main_reason(items) == "⛔ 主要原因：淨值取數失敗，改用 2026-09-18 的預存淨值（AAAA）"
    assert PH.main_reason(items) == PH.TEXT_MAIN_RETREAT.format(key="淨值", day="2026-09-18", codes="AAAA")
    same_day = [_fetch("2026-09-18", ["BBBB"]), _fetch("2026-09-18", ["AAAA"])]
    assert PH.main_reason(same_day) == "⛔ 主要原因：淨值取數失敗，改用 2026-09-18 的預存淨值（AAAA、BBBB）"


def test_A_多個日期_日期新的在前_同日期代碼排序():
    items = [_fetch("2026-09-10", ["BBBB"]), _fetch("2026-09-18", ["DDDD"]), _fetch("2026-09-18", ["AAAA"])]
    assert PH.main_reason(items) == (
        "⛔ 主要原因：淨值取數失敗，改用 2026-09-18 的預存淨值（AAAA、DDDD）、2026-09-10 的預存淨值（BBBB）")
    merged = PH.merge_items(items)
    assert len(merged) == 1 and PH.counts(merged) == {PH.KIND_FETCH: 1}           # 仍是一項


def test_A_混合_同一類另有沒預存可退的_句尾點名():
    items = [_fetch("2026-09-18", ["AAAA"]), _fetch(no_retreat=("DDDD",)), _fetch(no_retreat=("CCCC",)),
             _fetch("2026-09-10", ["BBBB"])]
    assert PH.main_reason(items) == ("⛔ 主要原因：淨值取數失敗，改用 2026-09-18 的預存淨值（AAAA）、"
                                     "2026-09-10 的預存淨值（BBBB）；CCCC、DDDD 沒有預存淨值")
    # 沒有任何一檔退回預存 → 照舊一般取數失敗那一句，不點名
    assert PH.main_reason([_fetch(no_retreat=("CCCC",))]) == "⛔ 主要原因：淨值取數失敗（1 張卡有值讀不到）"


def test_A_收集時逐檔沒有預存的取數失敗記下代碼():
    display = {"blocks": [{"code": "HLD-2", "title": "績效與風險卡", "_layer": 2, "_state": "系統錯誤"}]}
    events = [{"code": "HLD-2", "field": "text", "fields": ["text"], "data_classes": ("淨值",), "fund": "CCCC",
               "retreat_day": None, "container": None, "raw": "x"},
              {"code": "HLD-2", "field": "text", "fields": ["text"], "data_classes": ("淨值",), "fund": "AAAA",
               "retreat_day": "2026-09-18", "container": None, "raw": "y"}]
    items, _u = health.collect_page_items(display, {}, events, ["HLD-2"])
    assert PH.main_reason(items) == "⛔ 主要原因：淨值取數失敗，改用 2026-09-18 的預存淨值（AAAA）；CCCC 沒有預存淨值"


# ═══════════════════════ B：頁上畫 ⬜ 的格不計數（全情境守衛） ═══════════════════════

_BOX_EXTRA = {
    "exp|fetched_gt": SCAN._exp(rules=[{"field": "fetched_at", "op": "大於", "value": "1"}]),
    "exp|ccy_gt": SCAN._exp(rules=[{"field": "ccy", "op": "大於", "value": "1"}]),
    "exp|ccy_eq": SCAN._exp(rules=[{"field": "ccy", "op": "等於", "value": "USD"}]),
}


def _box_ids(display):
    """頁上畫成 ⬜ 的節點（值那一格的字以 ⬜ 起頭）；與收集那一支分開寫，不共用判斷。"""
    out = set()
    stack = [display]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            texts = [v for k, v in node.items() if k in ("text", "value_text") and isinstance(v, str)]
            # 複驗可選 4：混合欄位也算（一欄 ⬜、另一欄不是 ◇／⛔ 起頭）；判斷在這裡另寫，不共用產品碼
            if (texts and any(t[:1] == "⬜" for t in texts)
                    and not any(t[:2] in ("◇ ", "⛔ ") for t in texts)):
                out.add(id(node))
            stack.extend(v for v in node.values() if isinstance(v, (dict, list, tuple)))
        elif isinstance(node, (list, tuple)):
            stack.extend(node)
    return out


def _all_live_scripts():
    out = {}
    for page in ("mkt", "hld", "exp", "alo"):
        for name, script in SCAN.SCRIPTS[page].items():
            out[f"{page}|{name}"] = script
    out.update(_BOX_EXTRA)
    return out


@pytest.mark.parametrize("name", sorted(_all_live_scripts()))
def test_B_全情境_頁上畫方塊的格_總表不計成資料未備或取數失敗(name, monkeypatch):
    hits = []
    orig = health.collect_page_items

    def spy(display, summary, events, cards, **kwargs):
        trace = []
        out = orig(display, summary, events, cards, trace=trace)
        boxes = _box_ids(display)
        hits.extend((kind, key) for node_id, kind, key in trace if node_id in boxes)
        return out

    monkeypatch.setattr(health, "collect_page_items", spy)
    _app(_all_live_scripts()[name])
    assert hits == []


def test_B_篩選判定格畫方塊_不計數_明細照抄那一句():
    entry = _entry(_BOX_EXTRA["exp|ccy_gt"], "exp")
    assert PH.SETTING_FILTER_RULES not in {i["key"] for i in entry["items"]}
    rows = [r for r in PH.detail_rows(entry) if r[1].endswith(" 篩選判定")]
    assert rows and all(r[2].startswith("⬜ 無法判定（") for r in rows)


# ═══════════════════════ 可選 1：值欄不放狀態字 ═══════════════════════


@pytest.mark.parametrize("page, script", [("mkt", SCAN.MKT["未設定"]), ("hld", SCAN.HLD["退回預存過期"]),
                                          ("hld", SCAN.HLD["局部失敗"]), ("exp", SCAN.EXP["正常"])])
def test_可選1_日期時間延遲來源層級四欄_沒有值寫一槓_不放狀態字(page, script):
    rows = PH.detail_rows(_entry(script, page))
    assert rows
    for row in rows:
        for cell in row[3:]:
            assert not cell.startswith(("⛔", "◇", "⬜", "◷")), row


# ═══════════════════════ 可選 2：lines 欄位裡的 ◇ 句 ═══════════════════════


def test_可選2_另有N檔淨值超過10日那一句_收集認得_明細在淨值與配息序列底下():
    entry = _entry(SCAN.HLD["超過10日"], "hld")
    rows = PH.detail_rows(entry)
    assert any(r[1] == "淨值與配息序列" and r[2] == "◇ 資料未備" and r[0] == "淨值" for r in rows), rows


def test_可選2_lines欄位的禁止與資料未備句_沒有類別照樣報錯():
    display = {"blocks": [{"code": "HLD-6", "title": "淨值與配息序列", "_layer": 4, "_state": "ok",
                           "detail_lines": ["◇ 另有 2 檔淨值超過 10 日未更新（資料未備）"]}]}
    with pytest.raises(health.MissingClassError):
        health.collect_page_items(display, {}, (), [])


# ═══════════════════════ 可選 3：畫頁崩潰時總表不留上一筆正常記錄 ═══════════════════════

_CRASH = SCAN._HEAD + '''
import streamlit as st
from ui_v2 import health_view
_saved = health_view.render_status_line
if st.session_state.get("CRASH"):
    def _boom(*_a, **_k):
        raise RuntimeError("畫頁崩潰（測試注入）")
    health_view.render_status_line = _boom
try:
''' + "\n".join("    " + line for line in SCAN.MKT["未設定"].split("\n")) + '''
finally:
    health_view.render_status_line = _saved
'''


def test_可選3_記錄之後畫頁崩潰_總表改寫為無法彙整_照舊往上拋():
    at = AppTest.from_string(_CRASH, default_timeout=180)
    at.run()
    assert not at.exception and not at.session_state[PH.STATE_KEY]["mkt"].get("collect_error")
    at.session_state["CRASH"] = True
    at.run()
    assert at.exception and "畫頁崩潰" in at.exception[0].value               # 照舊往上拋，不吞
    entry = at.session_state[PH.STATE_KEY]["mkt"]
    assert entry["collect_error"] == "RuntimeError" and entry["items"] == []      # 不留上一筆正常記錄
    row = next(r for r in PH.summary_rows(at.session_state[PH.STATE_KEY]) if r["slug"] == "mkt")
    assert row["status"] == PH.TEXT_COLLECT_FAILED


def test_可選3_示範模式畫頁崩潰_照舊往上拋_不寫總表():
    script = SCAN._HEAD + '''
from ui_v2.mkt import page
_saved = page._pick_dataset
def _boom(*_a, **_k):
    raise RuntimeError("示範模式畫頁崩潰（測試注入）")
page._pick_dataset = _boom
try:
    page.render()
finally:
    page._pick_dataset = _saved
'''
    at = AppTest.from_string(script, default_timeout=180)
    at.run()
    assert at.exception and "示範模式畫頁崩潰" in at.exception[0].value
    assert PH.STATE_KEY not in at.session_state


# ═══════════════════════ 可選 5：總表排序 ═══════════════════════


def test_可選5_排序照舊_沒開過的頁排最後():
    store = {"mkt": {"at": "2026-10-20T01:00:00+00:00", "items": [], "as_of": "2026-09-21", "page_failure": None,
                     "normal": []}}
    rows = PH.summary_rows(store)
    assert [r["slug"] for r in rows] == ["mkt", "hld", "exp", "alo"] and rows[1]["main"] == PH.TEXT_NOT_OPENED


# ═══════════════════════ 複驗應修 1～3：每列來源展開 ═══════════════════════


def _source_rows_by_code(monkeypatch, script):
    from ui_v2.exp import live
    seen = {}
    orig = live.source_rows

    def spy(block, row):
        out = orig(block, row)
        seen[row.get("_fund_code")] = out
        return out

    monkeypatch.setattr(live, "source_rows", spy)
    _app(script)
    return seen


def test_複驗1_四項全空的欄不列_F06的計價幣別以外三欄不列(monkeypatch):
    rows = _source_rows_by_code(monkeypatch, SCAN.EXP["正常"])["F06"]
    fields = [r[0] for r in rows]
    assert "最近淨值日" not in fields and "最近淨值（原幣）" not in fields      # 只有判定句、沒有來源資訊 → 不列
    assert not any(r[1:] == ("—", "—", "—", "—") for r in rows)


def test_複驗2_來源一致性句_收回列展開(monkeypatch):
    rows = _source_rows_by_code(monkeypatch, SCAN.EXP["正常"])["F06"]
    ccy = next(r for r in rows if r[0] == "計價幣別")
    assert ccy[4].startswith("原因：各來源幣別不一致（") and "宣告" in ccy[4]


def test_複驗2_來源一致性句的字面與資料層真身相同():
    from ui_v2.exp import live
    src = (_ROOT / "services" / "v2_tables" / "exp_profile.py").read_text(encoding="utf-8")
    head = live.SOURCE_CONSISTENCY_HEAD
    assert head.startswith("原因：") and f'reason=f"{head[len("原因："):]}' in src


def test_複驗2與3_判定句在配息比以外不收_配息比格內原因句不論內容都收():
    from ui_v2.exp import live
    verdict = "淨值來源：MoneyDJ；計價幣別未確定（基本資料各來源幣別缺或不一致），淨值與配息比不取數"
    assert live.split_tip(verdict) == (None, None, "淨值來源：MoneyDJ")
    cell = "◇ 資料未備：計價幣別未確定（基本資料各來源幣別缺或不一致），淨值與配息比不取數"
    assert live.split_tip(verdict, reason_in=cell) == (None, None, verdict)
    partial = "出處：TDCC；原因：部分來源取數失敗，以其餘一致的來源為準（MoneyDJ：HTTP 503）"
    assert live.split_tip(partial) == (None, None, "出處：TDCC")                   # 不是來源一致性句


def test_複驗可選4_混合欄位_一欄方塊另一欄不是禁止或資料未備_不計數():
    node = {"label": "篩選判定", "_state": "資料未備", "value_text": "⬜ 無法判定（資料未備：ccy）", "text": "A01",
            PH.MISSING_KEYS_KEY: ("基金基本資料",)}
    display = {"blocks": [{"code": "EXP-2", "title": "候選清單卡", "_layer": 2, "_rows": [node]}]}
    items, _u = health.collect_page_items(display, {}, (), ["EXP-2"])
    assert items == []
    rows = health.boxed_entries(display)
    assert [(r["card"], r["status"]) for r in rows] == [("候選清單卡", "⬜ 無法判定（資料未備：ccy）")]
    mixed_missing = dict(node, text="◇ 資料未備")                                   # 另一欄是 ◇ → 照計
    display["blocks"][0]["_rows"] = [mixed_missing]
    items, _u = health.collect_page_items(display, {}, (), ["EXP-2"])
    assert [i["kind"] for i in items] == [PH.KIND_MISSING]
