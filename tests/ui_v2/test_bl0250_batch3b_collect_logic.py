# -*- coding: utf-8 -*-
"""BL-0250 批次 3-B 總管第二輪裁定：四頁在產生處交出原因項目、收集、記錄、設定與診斷頁的各頁資料狀態總表（not-slow 線）。

依據：`docs/v2/44_fund_ui_ssot.md` 第七節第三小節之十三其五之四、之五、其七；總管 2026-10-19 第二輪裁定第 1～5 點。
原則：總表只彙整各頁已經畫出來的狀態，不重新判一次符號。本檔驗的是：
- 衍生的 ◇ 不計數、找不到類別的 ◇ 報錯（裁定第 1 點）；
- 資產配置使用者設定留空以設定的中文名計 ◇、一格兩種成因兩類各算一項（裁定第 2、3 點）；
- 取數失敗的資料類取自產生處、頁首一個字不改（裁定第 4 點）；
- 同順位依塊序（裁定第 5 點）；
- 四頁正式模式記錄、整頁載不出來、設定與診斷頁總表的畫面字。
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

from ui_v2 import health, page_health, plain, symbols  # noqa: E402
from ui_v2.alo import fixtures as AF, logic as AL  # noqa: E402
from ui_v2.exp import live as EXL  # noqa: E402
from ui_v2.hld import fixtures as HF, logic as HL  # noqa: E402
from ui_v2.mkt import fixtures as MF, logic as ML  # noqa: E402

_D44 = _ROOT / "docs" / "v2" / "44_fund_ui_ssot.md"


def _pipeline(model, page):
    """與四頁正式模式同一串（換字 → 換符號 → 同源錯誤去重 → 尚未設定改字 → 收集）。"""
    display, _raw, status = plain.plain_model(model, page=page)
    symbols.apply(display)
    display, failures = health.dedupe_failures(display)
    health.relabel_unconfigured(display, failures)
    cards = [b["code"] for b in display["blocks"] if b.get("_layer") == 2]
    items, unresolved = health.collect_page_items(display, failures, status["fetch_events"], cards)
    return display, failures, status, items, unresolved


def _keys(items, kind=None):
    return sorted((i["kind"], i["key"]) for i in items if kind is None or i["kind"] == kind)


def _cards(items, kind, key):
    item = next(i for i in items if i["kind"] == kind and i["key"] == key)
    return {e["card"] for e in item["affected"]}


# ═══════════════════════ 鍵名與鏡像 ═══════════════════════


def test_標記鍵與資料類對照_兩邊鏡像一致():
    assert plain.FETCH_CLASSES_KEY == page_health.FETCH_CLASSES_KEY
    assert page_health.DATA_CLASSES == plain.TABLE_NAMES
    # 「情境試算金額」照總管第二輪裁定第 2 點的字面（留空的是那一列的金額，不是整個情境試算輸入）；其餘三個與使用者設定鍵的中文名相同。
    assert set(page_health.SETTING_KEYS) - {page_health.SETTING_SCENARIO_INPUT} <= set(plain.SETTING_NAMES.values())
    assert page_health.DATA_CLASS_POOL in {cls for _m, cls, _s in plain._KNOWN_MESSAGES}
    assert page_health.FETCH_CLASSES_KEY in page_health.MARK_KEYS
    assert page_health.UNCONFIGURED_KEY == health.UNCONFIGURED_KEY


def test_總表的跨頁記錄不在換頁要清掉的清單裡():
    text = (_ROOT / "ui_v2" / "app_preview.py").read_text(encoding="utf-8")
    block = text.split("_PAGE_STATE_TO_DROP = (")[1].split(")\n")[0]
    assert "page_health" not in block and page_health.STATE_KEY not in block


def test_44_新塊的標題與程式常數相同():
    text = _D44.read_text(encoding="utf-8")
    assert f"#### 塊 {page_health.BLOCK_CODE}｜{page_health.BLOCK_TITLE}" in text
    tail = text.split("#### 塊 SET-8｜")[1]
    assert page_health.TEXT_LAMP_NOTE in text and page_health.TEXT_NOT_OPENED in tail


# ═══════════════════════ 裁定第 1 點：衍生的 ◇ 不計數；找不到類別報錯 ═══════════════════════


def _tiny(block_extra=None, value_extra=None):
    value = {"_state": "資料未備", "label": "某值", "text": "◇ 資料未備", **(value_extra or {})}
    block = {"code": "MKT-1", "title": "風險情緒卡", "_layer": 2, "_state": "資料未備", "main_values": [value],
             **(block_extra or {})}
    return {"blocks": [block]}


def test_衍生的塊層狀態不另算_值自己記的那一類算一項():
    display = _tiny(page_health.tag_derived({}, "塊的狀態取自本塊各值"),
                    {page_health.MISSING_KEYS_KEY: ("市場指標",)})
    items, unresolved = health.collect_page_items(display, {}, (), ["MKT-1"])
    assert _keys(items) == [("資料未備", "市場指標")] and unresolved == []
    assert len(items[0]["affected"]) == 1 and items[0]["affected"][0]["item"] == "某值"


def test_找不到類別又沒有標衍生的_報錯_不靠略過():
    display = _tiny(None, {page_health.MISSING_KEYS_KEY: ("市場指標",)})   # 塊層的 ◇ 沒有記類別、也沒有記衍生
    with pytest.raises(health.MissingClassError):
        health.collect_page_items(display, {}, (), ["MKT-1"])


def test_HLD7四塊沒有一塊出數_與結論燈_記為衍生不另算():
    model = HL.build_page_model(**HF.scenario("empty"))
    hld7 = HL.find_block(model, "HLD-7")
    assert hld7[page_health.DERIVED_KEY] is True and hld7[page_health.DERIVED_REASON_KEY]
    assert HL.find_block(model, "HLD-0")[page_health.DERIVED_KEY] is True
    _d, _f, _s, items, unresolved = _pipeline(model, "hld")
    for item in items:
        assert not {"計算軌跡", "體檢結論燈"} & {e["card"] for e in item["affected"]}, item
    assert unresolved == []


# ═══════════════════════ 裁定第 2、3 點：資產配置 ═══════════════════════


def _alo_both_missing():
    """缺匯率（市場指標）＋「核心」那一類目標比重留空：同一格兩種成因。"""
    ds = copy.deepcopy(AF.scenario("nofx"))
    row = next(r for r in ds["user_setting"] if r["setting_key"] == "alo_target_weights")
    row["setting_value"][0]["weight_ratio"] = None
    return ds


def test_一格兩種成因_兩類各算一項_而且記在判定分支():
    model = AL.build_page_model(_alo_both_missing())
    row = next(r for r in AL.find_block(model, "ALO-2")["_rows"] if r["_bucket"] == "核心（示意）")
    assert row[page_health.MISSING_KEYS_KEY] == ("市場指標", "目標比重")
    _d, _f, _s, items, _u = _pipeline(model, "alo")
    assert ("資料未備", "市場指標") in _keys(items) and ("資料未備", "目標比重") in _keys(items)
    assert "目標對照卡" in _cards(items, "資料未備", "目標比重") and "目標對照卡" in _cards(items, "資料未備", "市場指標")


def test_情境試算後差額_兩邊都缺時兩類都記():
    model = AL.build_page_model(_alo_both_missing())
    rows = {r["bucket_text"]: r for r in AL.find_block(model, "ALO-3")["_rows"]}
    assert rows["核心（示意）"][page_health.MISSING_KEYS_KEY] == ("市場指標", "目標比重")
    assert rows["衛星（示意）"][page_health.MISSING_KEYS_KEY] == ("市場指標",)
    _d, _f, _s, items, _u = _pipeline(model, "alo")
    assert "情境試算卡" in _cards(items, "資料未備", "目標比重")


def test_一邊缺只算那一邊():
    model = AL.build_page_model(AF.scenario("nofx"))
    _d, _f, _s, items, _u = _pipeline(model, "alo")
    assert _keys(items) == [("資料未備", "市場指標")]


def test_使用者設定留空_鍵是設定的中文名_資料類寫使用者設定():
    _d, _f, _s, items, _u = _pipeline(AL.build_page_model(AF.scenario("partial")), "alo")
    keys = {key for _kind, key in _keys(items, page_health.KIND_MISSING)}
    assert keys <= set(page_health.SETTING_KEYS) | {"市場指標", "淨值", "持倉"}
    assert keys & set(page_health.SETTING_KEYS)
    for item in items:
        assert item["key"] not in ("使用者設定", "alo_target_weights", "alo_scenario_input")
        if item["key"] in page_health.SETTING_KEYS:
            assert {e["data_class"] for e in item["affected"]} == {"使用者設定"}


def test_畫成方塊的不適用不計數():
    _d, _f, _s, items, _u = _pipeline(AL.build_page_model(AF.scenario("notarget")), "alo")
    assert items == []


def test_兩種成因的記號_正式畫面與示範模式一個字都不變():
    model = AL.build_page_model(_alo_both_missing())
    stripped = _without_marks(copy.deepcopy(model))
    assert AL.collect_ui_strings(model) == AL.collect_ui_strings(stripped)


def _without_marks(node):
    if isinstance(node, dict):
        return {k: _without_marks(v) for k, v in node.items() if k not in page_health.MARK_KEYS}
    if isinstance(node, list):
        return [_without_marks(v) for v in node]
    return node


# ═══════════════════════ 裁定第 4 點：取數失敗的資料類取自產生處 ═══════════════════════


def test_市場總覽的取數失敗是市場指標_頁首照舊寫資料():
    display, failures, status, items, unresolved = _pipeline(ML.build_page_model(MF.dataset_mkt1_fetch_failed()), "mkt")
    assert ("取數失敗", "市場指標") in _keys(items) and unresolved == []
    assert failures["fetch_failed"] == [plain.DATA_CLASS_DEFAULT]   # 頁首資料狀態行一個字不改
    assert {e["data_classes"] for e in status["fetch_events"]} == {("市場指標",)}


def test_同一句原文兩張表都回_各值依自己讀的那一張表():
    """持倉體檢 twofail：淨值與配息回同一句原文。績效與風險卡只屬淨值、配息與本金卡只屬配息 —— 不是依原文猜。"""
    model = HL.build_page_model(**HF.scenario("twofail"), strict_fetch_failure=True)
    _d, _f, _s, items, unresolved = _pipeline(model, "hld")
    assert unresolved == []
    assert "績效與風險卡" in _cards(items, "取數失敗", "淨值") and "績效與風險卡" not in _cards(items, "取數失敗", "配息")
    assert "配息與本金卡" in _cards(items, "取數失敗", "配息") and "配息與本金卡" not in _cards(items, "取數失敗", "淨值")


def test_產生處沒有寫類別的取數失敗_記為認不出_逐處列出():
    model = ML.build_page_model(MF.dataset_mkt1_fetch_failed())
    for block in model["blocks"]:
        for value in block.get("main_values") or ():
            value.pop(page_health.FETCH_CLASSES_KEY, None)
    _d, _f, _s, items, unresolved = _pipeline(model, "mkt")
    assert unresolved and ("取數失敗", plain.DATA_CLASS_DEFAULT) in _keys(items)


def test_一般畫面模型不留產生處記的原文():
    display, _f, _s, _i, _u = _pipeline(ML.build_page_model(MF.dataset_mkt1_fetch_failed()), "mkt")

    def walk(node):
        if isinstance(node, dict):
            assert page_health.FETCH_CLASSES_KEY not in node
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value)

    walk(display)


def test_標的探索各格的類別取自接線結果那一格的出處():
    cell = {"_state": "資料未備", "text": "⬜"}
    note = EXL._note("⬜ 資料未備：x", "資料未備", key="淨值")
    EXL._apply_cell_notes("A01", {"nav_date": cell}, {"A01": {"nav_date": note}})
    assert cell[page_health.MISSING_KEYS_KEY] == ("淨值",)
    failed = {"_state": "資料未備", "text": "⬜", page_health.MISSING_KEYS_KEY: ("配息",)}
    note = EXL._note("⛔ 取數失敗：MoneyDJ 取數失敗", "系統錯誤", key="淨值")
    EXL._apply_cell_notes("A01", {"div_ratio_pct": failed}, {"A01": {"div_ratio_pct": note}})
    assert page_health.MISSING_KEYS_KEY not in failed
    assert failed[page_health.FETCH_CLASSES_KEY] == (("MoneyDJ 取數失敗", "淨值"),)


# ═══════════════════════ 裁定第 5 點：同順位依塊序 ═══════════════════════


def test_同順位比到第三步_依塊序_由塊序產生():
    model = ML.build_page_model(MF.dataset_mkt1_fetch_failed())
    _d, _f, _s, items, _u = _pipeline(model, "mkt")
    orders = {(i["kind"], i["key"]): i["order"] for i in items}
    codes = [b["code"] for b in model["blocks"]]
    # 3-B 稽核回修第 5 條：順序＝塊序 × `_ORDER_BLOCK` ＋ 同塊之內的先後（被蓋住的成因再加 `_ORDER_SHADOWED`）；塊序仍在最前。
    assert orders[("取數失敗", "市場指標")] // health._ORDER_BLOCK == codes.index("MKT-1")
    a = page_health.make_item("資料未備", "甲", [page_health.affected("景氣位置卡", core=True, unreadable=True)],
                              order=codes.index("MKT-2"))
    b = page_health.make_item("資料未備", "乙", [page_health.affected("風險情緒卡", core=True, unreadable=True)],
                              order=codes.index("MKT-1"))
    assert page_health.pick_main([a, b])["key"] == "乙"


# ═══════════════════════ 四頁正式模式記錄與設定與診斷頁總表（AppTest） ═══════════════════════


def _run(*scripts):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    import _plain_scan as SCAN

    at = AppTest.from_string("\n".join(scripts), default_timeout=180)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at, SCAN


def _store(at):
    return at.session_state[page_health.STATE_KEY] if page_health.STATE_KEY in at.session_state else {}


def test_市場總覽正式模式記下的件數與線框1點2同一情境對得上():
    import _plain_scan as SCAN

    at, _ = _run(SCAN.MKT["未設定"])
    entry = _store(at)["mkt"]
    assert page_health.count_text(page_health.counts(entry["items"])) == "尚未設定 2 項　⛔ 取數失敗 1 項　◇ 資料未備 1 項"
    assert page_health.main_reason(entry["items"]).startswith("⛔ 主要原因：資料來源的金鑰尚未設定")


def test_整頁載不出來_記一筆頁層失敗():
    import _plain_scan as SCAN

    at, _ = _run(SCAN.HLD["整頁失敗"])
    entry = _store(at)["hld"]
    assert entry["page_failure"] == plain.DATA_CLASS_DEFAULT and entry["items"] == []
    assert page_health.main_reason(entry["items"], page_failure=entry["page_failure"]) == "⛔ 本頁暫時無法判定：資料取數失敗"


def _total_texts(at, SCAN):
    exp = [e for e in at.expander if e.label == page_health.BLOCK_TITLE]
    assert len(exp) == 1
    return [SCAN.markdown_text(m.value) for m in exp[0].markdown], exp[0]


def test_設定與診斷頁總表_只開過市場總覽():
    import _plain_scan as SCAN

    at, _ = _run(SCAN.MKT["未設定"], SCAN.SET["正常"])
    texts, box = _total_texts(at, SCAN)
    table = " ".join(texts[0].split())
    assert "市場總覽 尚未設定 2 項 ⛔ 取數失敗 1 項 ◇ 資料未備 1 項 ⛔ 主要原因：資料來源的金鑰尚未設定" in table
    for name in ("持倉體檢", "標的探索", "資產配置"):
        assert f"{name} — 本次尚未開過這一頁 —" in table
    assert page_health.TEXT_SCOPE in " ".join(texts)
    pick = box.selectbox[0]
    assert pick.label == page_health.TEXT_PICK_LABEL and pick.value == "市場總覽"
    assert pick.options[0] == "市場總覽"
    assert page_health.TEXT_LAMP_NOTE in " ".join(m.value for m in at.markdown)


def test_選單換一頁只換下面那張表_沒開過的頁寫沒有明細():
    import _plain_scan as SCAN

    at, _ = _run(SCAN.MKT["未設定"], SCAN.SET["正常"])
    box = _total_texts(at, SCAN)[1]
    box.selectbox[0].select("持倉體檢").run()
    texts, _box = _total_texts(at, SCAN)
    assert page_health.TEXT_DETAIL_EMPTY in " ".join(texts)
    assert not at.exception


def test_總表不影響可信度結論燈():
    import _plain_scan as SCAN

    def lamp(at):
        return [m.value for m in at.markdown if 'class="set-lamp"' in m.value]

    alone, _ = _run(SCAN.SET["正常"])
    with_mkt, _ = _run(SCAN.MKT["未設定"], SCAN.SET["正常"])
    assert lamp(alone) == lamp(with_mkt) and lamp(alone)


def test_排序_有異常的頁在前_沒開過的在最後_同級依固定頁序():
    import _plain_scan as SCAN

    at, _ = _run(SCAN.MKT["正常"], SCAN.HLD["stale"], SCAN.EXP["未設定"], SCAN.SET["正常"])
    pick = _total_texts(at, SCAN)[1].selectbox[0]
    assert pick.options == ["標的探索", "持倉體檢", "市場總覽", "資產配置"]


def test_不是最新整頁一項_取自卡上留著的時鐘記號():
    import _plain_scan as SCAN

    at, _ = _run(SCAN.HLD["stale"])
    entry = _store(at)["hld"]
    assert page_health.counts(entry["items"]) == {page_health.KIND_STALE: 1}


def test_明細表沒有異常的項目也列_狀態寫一槓():
    import _plain_scan as SCAN

    at, _ = _run(SCAN.MKT["正常"])
    entry = _store(at)["mkt"]
    rows = page_health.detail_rows(entry)
    assert rows and all(r[2] == page_health.NO_VALUE for r in rows)
    assert any(r[1].startswith("新鮮度與來源清單") and r[0] == "市場指標" for r in rows)
    assert any(r[1].startswith("風險情緒卡") for r in rows)
