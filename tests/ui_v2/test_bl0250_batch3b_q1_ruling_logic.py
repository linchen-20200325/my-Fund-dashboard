# -*- coding: utf-8 -*-
"""BL-0250 批次 3-B 客戶驗收裁示第 1 題（2026-10-20；`docs/DECISIONS.md` `DEC-2026-10-20-01`；
`docs/v2/44_fund_ui_ssot.md` 第七節第三小節之十三其八第 23 條）。not-slow 線。

客戶裁示：使用者自己的參數留空（資產配置目標比重、情境試算金額、目標修改紀錄 `ALO-7`；標的探索篩選條件比照）
**不計入資料狀態件數**（理由：資料健康 ≠ 使用者輸入）；**格內符號維持現況**（頁上照舊畫 ◇）。

本檔驗四件事：
1. 使用者參數留空不計件數、不進主要原因、不列明細；
2. 頁上那幾格照舊畫 ◇（產生處的記號照舊）；
3. 資料真缺（基準值缺、持倉缺、取數失敗）照舊計數，一格兩種成因只略過設定那一邊；
4. 找不到類別的 ◇ 照舊報錯（不因本裁示變成「略過」）。
"""

from __future__ import annotations

import copy
import pathlib
import sys

import pytest

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
for _p in (_HERE, _HERE.parent, _ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from ui_v2 import health, page_health as PH, plain, sections, symbols  # noqa: E402
from ui_v2.alo import fixtures as AF, logic as AL  # noqa: E402

_D44 = _ROOT / "docs" / "v2" / "44_fund_ui_ssot.md"
_SETTING = set(PH.SETTING_KEYS)


def _pipeline(model, page):
    """與四頁正式模式同一串（換字 → 換符號 → 同源錯誤去重 → 尚未設定改字 → 收集）。"""
    display, _raw, status = plain.plain_model(model, page=page)
    symbols.apply(display)
    display, failures = health.dedupe_failures(display)
    health.relabel_unconfigured(display, failures)
    # 總表的核心卡取改層之後在 ② 畫成卡的塊（同四頁正式模式，`sections.health_cards`）
    cards = sections.health_cards([b["code"] for b in display["blocks"] if b.get("_layer") == 2], page)
    items, unresolved = health.collect_page_items(display, failures, status["fetch_events"], cards)
    return display, items, unresolved


def _keys(items):
    return sorted((i["kind"], i["key"]) for i in items)


def _drawn_diamond_setting_nodes(display):
    """頁上畫成 ◇、產生處記了使用者設定鍵的節點（本檔自己判斷，不共用產品的收集碼）。"""
    out = []
    stack = [display]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            keys = set(node.get(PH.MISSING_KEYS_KEY) or ())
            texts = [v for k, v in node.items() if isinstance(v, str) and not str(k).startswith("_")]
            # 塊層的 ◇ 由狀態「資料未備」畫出（例：篩選軌跡「尚未設定條件」），值那一格的 ◇ 寫在字面上。
            if keys & _SETTING and (node.get("_state") == "資料未備" or any(t == "◇" or t.startswith("◇ ") for t in texts)):
                out.append(node)
            stack.extend(v for v in node.values() if isinstance(v, (dict, list, tuple)))
        elif isinstance(node, (list, tuple)):
            stack.extend(node)
    return out


def _entry(items, *, as_of="2026-09-23"):
    store = {}
    PH.record(store, "alo", items, as_of=as_of, now="2026-10-20T01:00:00+00:00")
    return store[PH.STATE_KEY]["alo"]


# ═══════════════════════ 1＋2：資產配置使用者參數留空 ═══════════════════════


def test_目標比重與情境試算金額留空_頁上照舊畫菱形_但不計件數不進主要原因不列明細():
    display, items, unresolved = _pipeline(AL.build_page_model(AF.scenario("partial")), "alo")
    drawn = _drawn_diamond_setting_nodes(display)
    assert {k for n in drawn for k in n[PH.MISSING_KEYS_KEY]} == {PH.SETTING_TARGET_WEIGHTS, PH.SETTING_SCENARIO_INPUT}
    assert len(drawn) >= 4                                 # 目標輸入卡、目標對照卡、情境試算卡兩處 —— 頁面一個字沒改
    assert items == [] and unresolved == []
    assert PH.counts(items) == {} and PH.main_reason(items) is None
    entry = _entry(items)
    assert PH.detail_rows(entry) == []
    assert PH.summary_rows({"alo": entry})[0]["status"] == "資料截至 2026-09-23"


def test_ALO7尚未設定目標_頁上照舊畫菱形_不計件數():
    display, items, _u = _pipeline(AL.build_page_model(AF.scenario("first")), "alo")
    alo7 = AL.find_block(display, "ALO-7")
    assert alo7["placeholder"]["glyph"] == "◇" and alo7["placeholder"][PH.MISSING_KEYS_KEY] == (PH.SETTING_TARGET_WEIGHTS,)
    # 同一頁的持倉缺是資料真缺：照舊一項、照舊是主要原因
    assert _keys(items) == [(PH.KIND_MISSING, "持倉")]
    assert PH.main_reason(items) == "◇ 主要原因：持倉資料未備（1 張卡有值讀不到）"
    assert "目標修改紀錄" not in {e["card"] for i in items for e in i["affected"]}


def test_ALO7尚未設定過_產生處照舊記容許帶_不計件數():
    ds = copy.deepcopy(AF.scenario("full"))
    next(r for r in ds["user_setting"] if r["setting_key"] == "alo_tolerance_pp")["updated_at"] = None
    model = AL.build_page_model(ds)
    row = next(r for r in AL.find_block(model, "ALO-7")["_rows"] if r["_key"] == "alo_tolerance_pp")
    assert row["time_text"] == AL.TEXT_NEVER_SET and row[PH.MISSING_KEYS_KEY] == (PH.SETTING_TOLERANCE,)
    _d, items, _u = _pipeline(model, "alo")
    assert items == []


# ═══════════════════════ 3：資料真缺照舊計數 ═══════════════════════


def test_一格兩種成因_只略過目標比重_基準值缺的市場指標照算():
    ds = copy.deepcopy(AF.scenario("nofx"))
    next(r for r in ds["user_setting"] if r["setting_key"] == "alo_target_weights")["setting_value"][0]["weight_ratio"] = None
    model = AL.build_page_model(ds)
    row = next(r for r in AL.find_block(model, "ALO-2")["_rows"] if r["_bucket"] == "核心（示意）")
    assert row[PH.MISSING_KEYS_KEY] == ("市場指標", PH.SETTING_TARGET_WEIGHTS)   # 產生處的記號照舊兩邊都記
    _d, items, _u = _pipeline(model, "alo")
    assert _keys(items) == [(PH.KIND_MISSING, "市場指標")]
    assert {"目標對照卡", "情境試算卡"} <= {e["card"] for e in items[0]["affected"]}
    assert PH.main_reason(items) == "◇ 主要原因：市場指標資料未備（1 張卡有值讀不到）"


@pytest.mark.parametrize("scenario, expected", [
    ("nofx", [(PH.KIND_MISSING, "市場指標")]),
    ("noholding", [(PH.KIND_MISSING, "持倉")]),
    ("holdfail", [(PH.KIND_FETCH, "持倉")]),
    ("fxfail", [(PH.KIND_FETCH, "市場指標")]),
])
def test_資料真缺與取數失敗_照舊計數(scenario, expected):
    _d, items, _u = _pipeline(AL.build_page_model(AF.scenario(scenario)), "alo")
    assert _keys(items) == expected


def test_收集那一步_設定鍵不成項_資料類照算():
    display = {"blocks": [{"code": "ALO-2", "title": "目標對照卡", "_layer": 2, "_state": "ok", "_rows": [
        {"bucket_text": "甲", "target_text": "◇ 資料未備", PH.MISSING_KEYS_KEY: (PH.SETTING_TARGET_WEIGHTS,)},
        {"bucket_text": "乙", "target_text": "◇ 資料未備", PH.MISSING_KEYS_KEY: ("市場指標", PH.SETTING_TARGET_WEIGHTS)},
        {"bucket_text": "丙", "target_text": "◇ 資料未備", PH.MISSING_KEYS_KEY: (PH.SETTING_FILTER_RULES, PH.SETTING_SCENARIO_INPUT,
                                                                           PH.SETTING_TOLERANCE)},
    ]}]}
    trace = []
    items, unresolved = health.collect_page_items(display, {}, (), ["ALO-2"], trace=trace)
    assert _keys(items) == [(PH.KIND_MISSING, "市場指標")] and unresolved == []
    assert [e["item"] for e in items[0]["affected"]] == ["乙"]
    assert all(key not in _SETTING for _id, _kind, key in trace)


# ═══════════════════════ 4：找不到類別照舊報錯 ═══════════════════════


def test_畫成菱形卻沒有任何鍵_照舊報錯_不因本裁示略過():
    display = {"blocks": [{"code": "ALO-2", "title": "目標對照卡", "_layer": 2, "_state": "ok", "_rows": [
        {"bucket_text": "甲", "target_text": "◇ 資料未備"}]}]}
    with pytest.raises(health.MissingClassError):
        health.collect_page_items(display, {}, (), ["ALO-2"])


# ═══════════════════════ 44 落字 ═══════════════════════


def test_44_其八第23條記下客戶裁示_舊的待裁示那一項已劃線():
    text = _D44.read_text(encoding="utf-8")
    tail = text.split("#### 第七節第三小節之十三｜")[1]
    item = next(line for line in tail.split("\n") if line.startswith("23. **使用者自己的參數留空不計入資料狀態件數"))
    assert "DEC-2026-10-20-01" in item and "決策者：客戶" in item and "BL-0382" in item
    assert "- ~~使用者自己的參數留空，畫面上是 ◇，總表照頁面現況計一項" in tail


# ═══════════════════════ 標的探索篩選條件比照（正式模式整頁，AppTest；不標 slow） ═══════════════════════


def _exp_run(script, monkeypatch):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    seen = []
    orig = health.collect_page_items

    def spy(display, summary, events, cards, **kwargs):
        seen.append(display)
        return orig(display, summary, events, cards, **kwargs)

    monkeypatch.setattr(health, "collect_page_items", spy)
    at = AppTest.from_string(script, default_timeout=180)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(seen) == 1
    return seen[0], at.session_state[PH.STATE_KEY]["exp"]


def test_標的探索沒有任何條件_篩選軌跡照舊畫菱形_不計件數不進主要原因(monkeypatch):
    import _plain_scan as SCAN

    display, entry = _exp_run(SCAN._exp(rules=[]), monkeypatch)
    drawn = _drawn_diamond_setting_nodes(display)
    assert drawn and all(n[PH.MISSING_KEYS_KEY] == (PH.SETTING_FILTER_RULES,) for n in drawn)
    assert entry["items"] == [] and PH.main_reason(entry["items"]) is None
    assert all(r[0] != plain.TABLE_NAMES["user_setting"] for r in PH.detail_rows(entry))


def test_標的探索條件數值留空_不計篩選條件_資料真缺照舊計數(monkeypatch):
    import _plain_scan as SCAN

    rules = [{"field": "mgmt_fee_rate_pct", "op": "大於", "value": ""}]
    display, entry = _exp_run(SCAN._exp(wired=False, rules=rules), monkeypatch)
    assert any(n[PH.MISSING_KEYS_KEY] == (PH.SETTING_FILTER_RULES,) for n in _drawn_diamond_setting_nodes(display))
    assert _keys(entry["items"]) == [(PH.KIND_MISSING, "基金基本資料"), (PH.KIND_MISSING, "淨值"),
                                     (PH.KIND_MISSING, "配息")]
    assert PH.main_reason(entry["items"]) == "◇ 主要原因：基金基本資料資料未備（1 張卡有值讀不到）"
