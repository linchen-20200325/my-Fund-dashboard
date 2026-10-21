# -*- coding: utf-8 -*-
"""BL-0250 批次 3-B 兩組獨立稽核回修（7332b9f8 之後；not-slow 線，不標 slow）。

一條稽核發現一組測試，條號照總管回修單：
1. 「對照」多選清單已選而且看得到的超過 3 檔時不崩潰、不丟勾選；
2. 條件卡選得到的每一欄都在資料類對照表裡（`fetched_at`），查表遇未收錄鍵走錯誤邊界；
3. 收集與記錄的錯誤邊界：頁面照原樣、總表那一列寫「⛔ 本頁狀態無法彙整（‹例外類別›）」、寫 log；
4. 總表的核心卡取改層之後、在 ② 畫成卡的塊；
5. 主要原因與線框第六版例句逐一對照；被蓋住的成因；同塊同分的確定性規則；
6／7. 明細表：塊層成因涵蓋該卡底下畫成 ⛔／◇ 的值、狀態欄與延遲欄不矛盾、項目寫到基金；
8. 「篩選判定」比不出大小記成篩選條件；
11. 資產配置正式模式記錄、資產配置整頁失敗記錄、市場總覽／標的探索整頁載不出來時記錄。
（第 10 條在 `test_bl0250_batch3b_logic.py`；第 12 條是 `test_bl0250_batch3a_logic.py` 的測試替身。）
"""

from __future__ import annotations

import logging
import pathlib
import sys

import pytest

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
for _p in (_HERE, _HERE.parent, _ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from ui_v2 import health, health_view, page_health, sections  # noqa: E402
from ui_v2.exp import live as EXL, logic as EXG  # noqa: E402

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

import _plain_scan as SCAN  # noqa: E402


def _app(script, *, ok=True):
    at = AppTest.from_string(script, default_timeout=180)
    at.run()
    if ok:
        assert not at.exception, [e.value for e in at.exception]
    return at


def _store(at):
    return at.session_state[page_health.STATE_KEY] if page_health.STATE_KEY in at.session_state else {}


def _entry(script, page):
    return _store(_app(script))[page]


def _screen(at):
    """頁面元素樹裡會上畫面的字（比對「頁面照原樣」用）。"""
    return ([m.value for m in at.markdown], [c.value for c in at.caption], [e.label for e in at.expander],
            [b.label for b in at.button])


# ═══════════════════════ 第 1 條：「對照」超過上限不崩潰 ═══════════════════════

_EXP_CAP = SCAN._HEAD + '''
import json
import streamlit as st
import _exp_live_stub as STUB
from ui_v2.exp import logic, page
STUB.reset(); STUB.WIRED.append(True)
ex = st.session_state.get("EXCL", "ZZZ")
STUB.STORE["exp_filter_rules"] = json.dumps([{"field": "fund_code", "op": "不等於", "value": ex}], ensure_ascii=False)
STUB.STORE["exp_visible_columns"] = json.dumps(list(logic.COLUMN_ORDER))
STUB.STORE["exp_sort_column"] = json.dumps([])
STUB.STORE["exp_watchlist"] = json.dumps([])
try:
    page.render(load_live=STUB.load_live, save_live=STUB.save_setting)
finally:
    STUB.reset()
'''


def _compare(at):
    return next(m for m in at.multiselect if m.key == "exp2live_pick_compare")


def _checked(at):
    key = EXG.checked_key(EXG.GROUP_COMPARE, EXL.LIVE_SCENARIO)
    return tuple(at.session_state[key]) if key in at.session_state else ()


def test_第1條_選滿3檔_條件藏一檔再加選一檔_條件改回來_不崩潰也不丟勾選():
    at = _app(_EXP_CAP)
    _compare(at).set_value(["A01", "B02", "C03"]).run()
    at.session_state["EXCL"] = "A01"
    at.run()
    assert not at.exception and _compare(at).value == ["B02", "C03"]
    _compare(at).set_value(["B02", "C03", "D04"]).run()
    assert _checked(at) == ("A01", "B02", "C03", "D04")
    at.session_state["EXCL"] = "ZZZ"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    # 依勾選狀態的順序只放前 3 檔進清單與並排對照；第 4 檔照舊留在勾選狀態裡（沒有靜默丟掉）；上限句照舊
    assert _compare(at).value == ["A01", "B02", "C03"]
    assert _checked(at) == ("A01", "B02", "C03", "D04")
    assert EXL.TEXT_PICK_FULL in [c.value for c in at.caption]
    # 只改了清單、沒有在清單上動過 → 再跑一次勾選狀態不變
    at.run()
    assert _checked(at) == ("A01", "B02", "C03", "D04") and not at.exception
    # 在清單上拿掉一檔：只動畫進清單的那幾檔，沒畫進清單的 D04 照舊留著
    _compare(at).set_value(["A01", "B02"]).run()
    assert _checked(at) == ("A01", "B02", "D04") and not at.exception


def test_第1條_純函式_放進清單的已選項不超過上限_順序同選項():
    assert EXL.shown_picks(("A01", "B02", "C03", "D04"), ["D04", "C03", "B02", "A01"], 3) == ["C03", "B02", "A01"]
    assert EXL.shown_picks(("A01", "B02"), ["A01", "B02"], 3) == ["A01", "B02"]
    assert EXL.shown_picks(("A01", "B02", "C03", "D04"), ["A01", "B02", "C03", "D04"]) == ["A01", "B02", "C03", "D04"]
    # 沒畫進清單的已選檔，在清單上改別的檔時照舊留著
    assert EXL.merge_picks(("A01", "B02", "C03", "D04"), ("A01", "B02", "C03"), ("A01", "B02")) == ("A01", "B02", "D04")


# ═══════════════════════ 第 2 條：資料類對照表收齊；未收錄鍵走錯誤邊界 ═══════════════════════


def test_第2條_條件卡選得到的每一欄與結果清單每一欄都在對照表裡():
    for column in (*EXG.FUND_PROFILE_FIELDS, *EXG.COLUMN_ORDER, EXG.CODE_COLUMN):
        assert column in EXG.COLUMN_DATA_CLASS, column
    assert EXG.COLUMN_DATA_CLASS["fetched_at"] == page_health.DATA_CLASSES["fund_profile"]


@pytest.mark.parametrize("op, value", [("大於", "1"), ("小於", "1"), ("等於", "x")])
def test_第2條_以取得時間篩選_大於小於等於_不崩潰_總表照常記(op, value):
    at = _app(SCAN._exp(rules=[{"field": "fetched_at", "op": op, "value": value}]))
    entry = _store(at)["exp"]
    assert not entry.get("collect_error")
    keys = {i["key"] for i in entry["items"] if i["kind"] == page_health.KIND_MISSING}
    # 取得時間是字串：大於／小於比不出大小 ⇒ 篩選判定格畫「⬜ 無法判定（…）」—— 頁上是 ⬜，不計數（第二輪 B），明細照抄那一句
    assert page_health.SETTING_FILTER_RULES not in keys
    boxed = [r for r in page_health.detail_rows(entry) if r[1].endswith(" 篩選判定")]
    assert bool(boxed) == (op != "等於") and all(r[2].startswith("⬜ 無法判定") and r[0] == "使用者設定" for r in boxed)


@pytest.mark.parametrize("op", ["大於", "小於", "等於"])
def test_第2條_取得時間值缺_記成基本資料(op):
    rows = [{"fund_code": "A01", "fetched_at": None}, {"fund_code": "B02", "fetched_at": "2026-10-14T01:00:00Z"}]
    _steps, listed, undet = EXG.apply_rules_tristate(rows, [{"field": "fetched_at", "op": op, "value": "1"}])
    assert undet["A01"] == ["資料未備：fetched_at"] and "A01" in [r["fund_code"] for r in listed]
    assert EXG.judge_keys(undet["A01"]) == (page_health.DATA_CLASSES["fund_profile"],)


def test_第2條_查表沒收錄的鍵_產生處不拋例外_收集報錯():
    assert page_health.class_of({"a": "甲"}, "a") == "甲"
    marker = page_health.class_of({"a": "甲"}, "b")
    assert page_health.is_unmapped(marker)
    display = {"blocks": [{"code": "MKT-1", "title": "風險情緒卡", "_layer": 2,
                           "main_values": [{"label": "x", "_state": "資料未備", page_health.MISSING_KEYS_KEY: (marker,)}]}]}
    with pytest.raises(health.MissingClassError):
        health.collect_page_items(display, {}, (), ["MKT-1"])


# ═══════════════════════ 第 3 條：錯誤邊界 ═══════════════════════

_PATCH = '''
import streamlit as st
from ui_v2 import health, page_health, sections as _S3D
from ui_v2.exp import logic as _EXG
_saved = (health.collect_page_items, health.normal_entries, page_health.record, dict(_EXG.COLUMN_DATA_CLASS),
          _S3D.quiet_cards, _S3D.quiet_details)
_mode = st.session_state.get("BREAK")
# BL-0250 批次 3-D（新設計 B；44 第七節第三小節之十五）：收集出錯時卡片不收起、照 3-C 的畫法（原因行寫不出來的保守退路）。
# 沒有注入錯誤的那一輪把收起關掉（＝3-C 畫法），下面「頁面照原樣」的比對因此驗的是「收集出錯 → 真程式退回 3-C 畫法、逐字相同」。
# ~~兩輪都走真程式~~（有意識的更正，不是漏刪：3-D 之後沒出錯那一輪會收起，與出錯那一輪本來就不同；斷言強度不變）。
if not _mode:
    _S3D.quiet_cards = lambda *_a, **_k: ({}, {})
    _S3D.quiet_details = lambda *_a, **_k: {}
def _boom(cls):
    def f(*_a, **_k):
        raise cls("測試注入")
    return f
if _mode == "MissingClassError":
    health.collect_page_items = _boom(health.MissingClassError)
elif _mode == "KeyError":
    health.normal_entries = _boom(KeyError)
elif _mode == "ValueError":
    page_health.record = _boom(ValueError)
elif _mode == "unmapped":
    _EXG.COLUMN_DATA_CLASS.pop("ccy")
try:
'''
_UNPATCH = '''
finally:
    health.collect_page_items, health.normal_entries, page_health.record = _saved[:3]
    _EXG.COLUMN_DATA_CLASS.clear(); _EXG.COLUMN_DATA_CLASS.update(_saved[3])
    _S3D.quiet_cards, _S3D.quiet_details = _saved[4], _saved[5]
'''


def _broken(script):
    body = "\n".join("    " + line for line in script.split("\n"))
    return SCAN._HEAD + _PATCH + body + _UNPATCH


@pytest.mark.parametrize("page, script, mode", [
    ("mkt", SCAN.MKT["未設定"], "MissingClassError"),
    ("hld", SCAN.HLD["未設定"], "KeyError"),
    ("alo", SCAN.ALO["取數失敗"], "ValueError"),
    ("exp", SCAN.EXP["正常"], "MissingClassError"),
    # 篩選判定那一格「資料未備：ccy」查表時查不到 ccy（模擬漏收錄的鍵）
    ("exp", SCAN._exp(rules=[{"field": "ccy", "op": "等於", "value": "USD"}]), "unmapped"),
])
def test_第3條_收集或記錄出錯_頁面照原樣_總表寫無法彙整_不留舊記錄(page, script, mode, caplog):
    at = _app(_broken(script))
    before = _screen(at)
    good = _store(at)[page]
    assert not good.get("collect_error") and good["items"]
    at.session_state["BREAK"] = mode
    with caplog.at_level(logging.WARNING, logger="ui_v2.health_view"):
        at.run()
    assert not at.exception, [e.value for e in at.exception]
    # ~~`_screen(at) == before`（頁面照原樣逐字不變，含頁首資料狀態行）~~ → BL-0250 批次 3-C（U9；44 第七節第三小節之十四；
    # 客戶 `DEC-2026-10-21-01`）：頁首自 3-C 起讀總表同一份記錄，收集出錯時頁首主要原因那一行寫總表同一句「⛔ 本頁狀態無法彙整」
    # （有意識的政策變更，不是漏刪）；頁首以外照原樣逐字不變。
    after = _screen(at)
    head = [i for i, v in enumerate(after[0]) if 'class="v2-status-line"' in v]
    assert len(head) == 1 and page_health.TEXT_COLLECT_FAILED in after[0][head[0]]
    assert [v for i, v in enumerate(after[0]) if i not in head] == [
        v for v in before[0] if 'class="v2-status-line"' not in v] and after[1:] == before[1:]
    entry = _store(at)[page]
    cls = "MissingClassError" if mode == "unmapped" else mode
    assert entry["collect_error"] == cls and entry["items"] == [] and entry["normal"] == []   # 整格改寫，不留舊記錄
    assert entry["at"]                                                      # 記錄時間照寫
    row = next(r for r in page_health.summary_rows(_store(at)) if r["slug"] == page)
    # 第二輪 C：一般畫面不露出例外類別名；類別只進 log（記錄裡留著，畫面不讀）
    assert row["status"] == "⛔ 本頁狀態無法彙整" and cls not in row["status"] and row["at"] != page_health.NO_VALUE
    assert page_health.summary_rows(_store(at))[0]["slug"] == page        # 與 ⛔ 同一級，排最前
    assert any(page in r.getMessage() and cls in r.getMessage() for r in caplog.records)


def test_第3條_總表與明細都寫同一句():
    at = _app(_broken(SCAN.MKT["未設定"]) + "\n" + SCAN.SET["正常"])
    at.session_state["BREAK"] = "MissingClassError"
    at.run()
    box = next(e for e in at.expander if e.label == page_health.BLOCK_TITLE)
    texts = " ".join(" ".join(SCAN.markdown_text(m.value).split()) for m in box.markdown)
    assert texts.count("⛔ 本頁狀態無法彙整") == 2 and "MissingClassError" not in texts   # 總表那一列＋明細；不露出類別名
    assert box.selectbox[0].value == "市場總覽"


def test_第3條_認不出資料類的取數失敗_逐處寫log(monkeypatch, caplog):
    monkeypatch.setattr(health, "collect_page_items",
                        lambda *a, **k: ([], [{"code": "MKT-1", "field": "value_text", "raw": "x"}]))
    monkeypatch.setattr(health, "normal_entries", lambda *a, **k: [])
    with caplog.at_level(logging.WARNING, logger="ui_v2.health_view"):
        got = health_view.collect_page_health("mkt", {"blocks": []}, {}, (), [])
    assert got == {"items": [], "normal": []}
    assert any("mkt" in r.getMessage() and "MKT-1" in r.getMessage() for r in caplog.records)


def test_第3條_其他例外照舊往上拋_不吞(monkeypatch):
    monkeypatch.setattr(health, "collect_page_items", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    with pytest.raises(RuntimeError):
        health_view.collect_page_health("mkt", {"blocks": []}, {}, (), [])


# ═══════════════════════ 第 4、5 條：核心卡、主要原因對照線框例句 ═══════════════════════


def test_第4條_總表的核心卡取改層之後在二畫成卡的塊():
    # 第二輪 D：標的探索照客戶裁示原文「EXP 三張核心卡」，三張都算
    assert sections.health_cards(["EXP-1", "EXP-2", "EXP-3"], "exp") == ["EXP-1", "EXP-2", "EXP-3"]
    assert sections.health_cards(["ALO-1", "ALO-2", "ALO-3"], "alo") == ["ALO-2"]
    assert sections.health_cards(["HLD-1", "HLD-2", "HLD-3"], "hld") == ["HLD-1", "HLD-2", "HLD-3"]
    assert sections.health_cards(["MKT-1", "MKT-2", "MKT-3"], "mkt") == ["MKT-1", "MKT-2", "MKT-3"]


def _main(entry):
    return page_health.main_reason(entry["items"], page_failure=entry.get("page_failure"))


def _others(entry):
    return page_health.count_text(page_health.other_counts(entry["items"], page_failure=entry.get("page_failure")))


@pytest.mark.parametrize("page, script, main, others", [
    # 線框第六版 2.x（市場總覽三處，已一致）
    ("mkt", SCAN.MKT["未設定"], "⛔ 主要原因：資料來源的金鑰尚未設定（2 張卡有值讀不到）", "尚未設定 1 項　⛔ 取數失敗 1 項　◇ 資料未備 1 項"),
    ("mkt", SCAN.MKT["取數失敗"], "⛔ 主要原因：市場指標取數失敗（1 張卡有值讀不到）", "◇ 資料未備 1 項"),
    # 線框第六版 3.2
    ("hld", SCAN.HLD["未設定"], "⛔ 主要原因：保單試算表尚未設定（3 張卡有值讀不到）", "尚未設定 1 項"),
    # 線框第六版 5.2
    ("alo", SCAN.ALO["取數失敗"], "⛔ 主要原因：持倉取數失敗（1 張卡有值讀不到）", None),
])
def test_第5條_主要原因與線框例句逐字相同(page, script, main, others):
    entry = _entry(script, page)
    assert _main(entry) == main
    assert _others(entry) == others


def test_第5條_標的探索未設定_同順位比到頁序_設定試算表在前_待客戶裁示():
    # 線框第六版 4.2 寫「⛔ 主要原因：選股池的雲端來源尚未設定」（不帶件數）。條件輸入卡畫著「⛔ 尚未設定：設定試算表」，
    # 依新設計 A 同順位比 (a) 設定試算表讓 1 張核心卡讀不到、選股池讓 0 張 ⇒ 設定試算表在前。要對上線框，得改「有值讀不到」
    # 的語意（條件輸入卡不算）—— 不改，停下回報；同日總管裁定維持現況（`44` 之十三其八第 13 條：規則表優先於示意例句，
    # 3-B 驗收時向客戶揭露，可被客戶推翻）。本條釘的是現況，不是例句。
    entry = _entry(SCAN.EXP["未設定"], "exp")
    # 第二輪 D：三張核心卡都算 ⇒ 設定試算表（條件輸入卡、候選清單卡）與選股池（候選清單卡、並排對照卡）都 2 張、都影響燈；
    # 比到 (c) 用總管訂的頁序（44 塊序；同塊畫出的先）⇒ 設定試算表在前。
    assert _main(entry) == "⛔ 主要原因：設定試算表尚未設定（2 張卡有值讀不到）"
    by_key = {i["key"]: i for i in entry["items"]}
    assert len(page_health.main_unreadable_cards(by_key["設定試算表"])) == len(
        page_health.main_unreadable_cards(by_key["選股池的雲端來源"])) == 2
    assert _others(entry) == "尚未設定 1 項"


def test_第4條_只讓移到四的塊讀不到的尚未設定_不誤歸只影響比較值():
    script = SCAN._exp(pool={"status": "pool_not_cloud", "codes": [],
                             "message": "選股池未設定雲端來源（沒有服務帳戶憑證），不讀本機暫存檔當母體"})
    assert _main(_entry(script, "exp")) == "⛔ 主要原因：選股池的雲端來源尚未設定（2 張卡有值讀不到）"
    settings_only = SCAN._mkt("fixtures.dataset_all_ok()", settings_error='"未設定試算表 ID，暫停寫入"')
    assert _main(_entry(settings_only, "mkt")) == "尚未設定：設定試算表（只影響比較值）"   # 線框 1.2 第 6 順位照舊


def test_第5條_被蓋住的成因_記在產生處_畫面不變():
    from ui_v2.hld import fixtures as HF, logic as HL
    dataset = HF.scenario("holdfail")
    dataset["holding"] = []
    dataset.setdefault("errors", {})
    dataset["errors"]["holding"] = "未設定保單試算表 ID（POLICY_SHEET_ID），不讀取"
    dataset["errors"]["user_setting"] = "未設定試算表 ID，暫停寫入"
    dataset["user_setting"] = []
    model = HL.build_page_model(dataset, strict_fetch_failure=True)
    blocks = {b["code"]: b for b in model["blocks"]}
    assert [m for m, _c in blocks["HLD-2"][page_health.SHADOWED_KEY]] == [dataset["errors"]["holding"]]
    assert [m for m, _c in blocks["HLD-1"][page_health.SHADOWED_KEY]] == [dataset["errors"]["user_setting"]]
    assert page_health.SHADOWED_KEY in page_health.MARK_KEYS


def test_第5條_同塊同分_畫出的成因先於被蓋住的成因():
    entry = _entry(SCAN.HLD["未設定"], "hld")
    by_key = {i["key"]: i for i in entry["items"]}
    shelf, settings = by_key["保單試算表"], by_key["設定試算表"]
    assert len(page_health.main_unreadable_cards(shelf)) == len(page_health.main_unreadable_cards(settings)) == 3
    assert shelf["lamp"] == settings["lamp"]
    assert shelf["order"] < settings["order"]
    assert shelf["order"] // health._ORDER_BLOCK == settings["order"] // health._ORDER_BLOCK   # 同一塊（偏離提示卡）
    # 被蓋住的成因另加一段偏移（防日後收集的次序改動時，被蓋住的成因跑到畫出的前面）
    assert 0 < health._ORDER_SHADOWED < health._ORDER_BLOCK
    assert settings["order"] % health._ORDER_BLOCK >= health._ORDER_SHADOWED > shelf["order"] % health._ORDER_BLOCK


# ═══════════════════════ 第 6、7 條：明細表 ═══════════════════════


def _detail(script, page):
    return page_health.detail_rows(_entry(script, page))


def test_第6條_畫面上是禁止符號的值_不列成一槓():
    rows = _detail(SCAN.MKT["未設定"], "mkt")
    by_item = {r[1]: r for r in rows}
    for item in ("風險情緒卡　高收益信用利差", "資金與匯率卡　政策利率"):
        assert by_item[item][2] == "⛔ 尚未設定：資料來源的金鑰" and by_item[item][0] == "市場指標"
    assert "風險情緒卡" not in by_item and "資金與匯率卡" not in by_item         # 不另列空項目名的那一列
    hld = _detail(SCAN.HLD["局部失敗"], "hld")
    for card, cls in (("績效與風險卡", "淨值"), ("配息與本金卡", "配息")):
        for fund in ("基金 A · 幣別 USD", "基金 B · 幣別 USD", "基金 C · 幣別 EUR"):
            row = next(r for r in hld if r[1] == f"{card}　{fund}")
            assert row[2] == "⛔ 取數失敗" and row[0] == cls
    # ~~`not any(r[2] == NO_VALUE for r in hld)`~~ → BL-0250 批次 3-C：明細多了淨值表逐檔那幾列（來源層級與延遲，`normal_entries`）；
    # 那一塊在本情境畫的是正常的淨值列（頁上沒有 ⛔），狀態欄寫「—」是照實。其餘各列照舊不得寫「—」（有意識的更正，不是漏刪）。
    assert not any(r[2] == page_health.NO_VALUE for r in hld if not r[1].startswith("淨值與配息序列　"))
    assert [r[2] for r in hld if r[1].startswith("淨值與配息序列　")] == [page_health.NO_VALUE] * 3


def test_第7條_狀態欄與延遲欄不矛盾_不另列空項目名的資料未備():
    rows = _detail(SCAN.HLD["退回預存過期"], "hld")
    assert not any(r[2] == page_health.NO_VALUE and r[5].startswith(page_health.SYMBOL_MISSING) for r in rows)
    assert not any(r[1] in ("績效與風險卡", "配息與本金卡") and r[2].startswith(page_health.SYMBOL_MISSING) for r in rows)
    for fund in ("基金 B · 幣別 USD", "基金 C · 幣別 EUR"):
        mine = [r for r in rows if r[1].startswith(f"績效與風險卡　{fund}")]
        assert mine and all(r[2] == "◇ 資料未備" for r in mine)


def test_第7條_市場總覽沒有異常的列_資料類寫市場指標():
    rows = _detail(SCAN.MKT["正常"], "mkt")
    assert rows and all(r[0] == "市場指標" for r in rows)


def test_第7條_標的探索_不適用那一句放狀態欄_項目寫到基金_同欄多檔不去重():
    rows = _detail(SCAN.EXP["正常"], "exp")
    na = [r for r in rows if r[1] == "條件輸入卡"]
    assert na and na[0][2].startswith("⬜ 不適用") and na[0][5] == na[0][6] == page_health.NO_VALUE
    assert any(r[1] == "候選清單卡　G07 最近淨值日" and r[2] == "⛔ 取數失敗" for r in rows)
    nav_missing = [r for r in rows if r[1].endswith(" 最近淨值日") and r[2] == "◇ 資料未備"]
    assert len({r[1] for r in nav_missing}) == len(nav_missing) >= 2


def test_第6條_純函式_塊層成因展開到該卡讀不到的值_被點名的值不重列():
    entry = {"items": [page_health.make_item("取數失敗", "淨值", [
        page_health.affected("甲卡", core=True, unreadable=True, data_class="淨值"),
        page_health.affected("甲卡", "基金 B 區間報酬率", core=True, unreadable=True, data_class="淨值")])],
        "normal": [page_health.affected("甲卡", "基金 A", unreadable=True, delay="延遲 1 日"),
                   page_health.affected("甲卡", "基金 B", unreadable=True, delay="◇ 資料未備"),
                   page_health.affected("甲卡", "基金 C", unreadable=False, delay="延遲 0 日")],
        "page_failure": None}
    rows = page_health.detail_rows(entry)
    assert rows == [
        ("淨值", "甲卡　基金 A", "⛔ 取數失敗", "—", "—", "延遲 1 日", "—"),
        # 第二輪可選 1：延遲欄那一格是狀態字（「◇ 資料未備」）時寫「—」，狀態只在狀態欄
        ("淨值", "甲卡　基金 B 區間報酬率", "⛔ 取數失敗", "—", "—", "—", "—"),
        ("—", "甲卡　基金 C", "—", "—", "—", "延遲 0 日", "—"),
    ]


# ═══════════════════════ 第 8 條：比不出大小記成篩選條件 ═══════════════════════


def test_第8條_欄位值或條件數值不是數值_鍵是篩選條件_資料類使用者設定():
    keys = EXG.judge_keys(["資料未備：ccy", "欄位值不是數值：mgmt_fee_rate_pct", "條件數值「abc」不是數值：inception_on"])
    assert keys == (page_health.DATA_CLASSES["fund_profile"], page_health.SETTING_FILTER_RULES)
    assert EXG.judge_keys(["條件數值「a：b」不是數值：ccy"]) == (page_health.SETTING_FILTER_RULES,)
    entry = _entry(SCAN._exp(rules=[{"field": "fund_name", "op": "大於", "value": "1"}]), "exp")
    # 第二輪 B：篩選判定格頁上畫 ⬜ ⇒ 不計數；明細照抄頁上那一句，資料類取自產生處記的鍵
    assert page_health.SETTING_FILTER_RULES not in {i["key"] for i in entry["items"]}
    boxed = [r for r in page_health.detail_rows(entry) if r[1].endswith(" 篩選判定")]
    assert boxed and all(r[2].startswith("⬜ 無法判定（") for r in boxed)
    assert all(r[0] == "使用者設定" for r in boxed if "不是數值" in r[2] and "資料未備" not in r[2])


# ═══════════════════════ 第 11 條：記錄的三個入口 ═══════════════════════

_RAISE_MKT = SCAN._HEAD + '''
from ui_v2.mkt import page
def _load():
    raise RuntimeError("fetch_url returned None (kind=unreachable)")
page.render(load_live=_load, mask_error=str, save_live=lambda *_a: {"status": "saved"})
'''
_RAISE_EXP = SCAN._HEAD + '''
from ui_v2.exp import page
def _load():
    raise RuntimeError("fetch_url returned None (kind=unreachable)")
page.render(load_live=_load, mask_error=str, save_live=lambda *_a: {"status": "saved"})
'''


def test_第11條_資產配置正式模式_記下這一頁():
    entry = _entry(SCAN.ALO["取數失敗"], "alo")
    assert entry["page_failure"] is None and not entry.get("collect_error")
    assert page_health.counts(entry["items"]) == {page_health.KIND_FETCH: 1}


def test_第11條_資產配置整頁載不出來_記頁層失敗():
    entry = _entry(SCAN.ALO["整頁失敗"], "alo")
    assert entry["page_failure"] == "資料" and entry["items"] == []


@pytest.mark.parametrize("page, script", [("mkt", _RAISE_MKT), ("exp", _RAISE_EXP)])
def test_第11條_市場總覽與標的探索整頁載不出來_記頁層失敗(page, script):
    entry = _entry(script, page)
    assert entry["page_failure"] == "資料" and entry["items"] == []
    assert _main(entry) == "⛔ 本頁暫時無法判定：資料取數失敗"
