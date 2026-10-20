# -*- coding: utf-8 -*-
"""BL-0250 實機驗收回修 批次 3 第二段（3-B）（客戶 2026-10-19 批次 3 裁示，`docs/DECISIONS.md` `DEC-2026-10-19-05`；
44 第七節第三小節之十三）的守衛（fast lane：純函式＋AppTest 接線，不標 slow）。

本批只落兩件：標的探索「對照」「觀察清單」兩份多選清單（之七其二第 5 條的實作批）、結果清單每列的
「來源與取得時間」列展開（裁示第 5 點第三項的窄例外；新設計 H 的展開那一半）。各頁資料狀態總表（U8）本批停下沒做。

每一項至少一條正面（正式模式改了）＋一條反面（不該改的沒改：示範模式、格內來源名、寫入範圍、只加不減）。
不打網路：正式模式走 `tests/ui_v2/_exp_live_stub.py`（in-memory 設定＋C2 接線假資料）。
"""

from __future__ import annotations

import html
import json
import pathlib
import re
import sys

import pytest

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
for _p in (_HERE, _HERE.parent, _ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from ui_v2.exp import live, logic  # noqa: E402

_D44 = _ROOT / "docs" / "v2" / "44_fund_ui_ssot.md"


# ═══════════════════════ 純函式：多選清單 ═══════════════════════


def _cell(text, state=logic.STATE_OK, tag=None, tip=None):
    out = {"text": text, "_state": state, "_tone": "中性"}
    if tag:
        out["source_tag"] = tag
    if tip:
        out["source_tip"] = tip
    return out


def _row(code, name="基金", *, name_state=logic.STATE_OK, watched=False, cells=None):
    row_cells = {"fund_code": _cell(code)}
    if name is not None:
        row_cells["fund_name"] = _cell(name, name_state)
    row_cells.update(cells or {})
    return {
        "_fund_code": code,
        "_cells": row_cells,
        "_checkboxes": {
            logic.GROUP_COMPARE: {"note": ""},
            logic.GROUP_WATCH: {"note": logic.TEXT_ALREADY_WATCHED if watched else ""},
        },
    }


def _block(rows, keys=("fund_code", "fund_name"), labels=("基金代碼", "基金名")):
    return {"code": "EXP-2", "_rows": rows, "column_keys": tuple(keys), "column_labels": list(labels)}


def test_選項順序同結果清單_不另外排序():
    block = _block([_row("C03"), _row("A01"), _row("B02")])
    assert live.pick_options(block) == ["C03", "A01", "B02"]


def test_選項文字_代碼全形空白基金名_名稱不是值時只寫代碼():
    block = _block([
        _row("A01", "測試基金 A01"),
        _row("B02", "◇ 資料未備：基本資料尚未接入", name_state=logic.STATE_MISSING),
        _row("C03", name=None),                       # 基金名那一欄被取消顯示
    ])
    assert live.pick_label(block, "A01", logic.GROUP_COMPARE) == "A01　測試基金 A01"
    assert live.pick_label(block, "B02", logic.GROUP_COMPARE) == "B02"
    assert live.pick_label(block, "C03", logic.GROUP_WATCH) == "C03"


def test_已在觀察清單_只在觀察清單那一份加註_對照那一份不加():
    block = _block([_row("A01", "甲", watched=True), _row("B02", "乙")])
    assert live.pick_label(block, "A01", logic.GROUP_WATCH) == "A01　甲（已在觀察清單）"
    assert live.pick_label(block, "A01", logic.GROUP_COMPARE) == "A01　甲"
    assert live.pick_label(block, "B02", logic.GROUP_WATCH) == "B02　乙"
    assert live.already_watched(block, "A01") and not live.already_watched(block, "B02")


def test_多選改了_看得到的照清單_看不到的原樣留著():
    assert live.merge_picks(("Z09", "A01"), ("A01", "B02"), ["B02"]) == ("B02", "Z09")
    assert live.merge_picks((), ("A01", "B02"), []) == ()
    # 與每列勾選框一格一格切換的結果相同
    one_by_one = logic.toggle_checked(logic.toggle_checked(("Z09", "A01"), "A01", checked=False), "B02", checked=True)
    assert live.merge_picks(("Z09", "A01"), ("A01", "B02"), ["B02"]) == one_by_one


def test_畫之前放進輸入欄的已選項_只取本次選項_順序同選項():
    assert live.shown_picks(("Z09", "C03", "A01"), ("A01", "B02", "C03")) == ["A01", "C03"]
    assert live.shown_picks(None, ("A01",)) == []


def test_對照的說明行_已選幾檔_選滿另一行上限句_觀察清單沒有():
    assert live.pick_captions(logic.GROUP_COMPARE, 0) == ["已選 0／3"]
    assert live.pick_captions(logic.GROUP_COMPARE, 2) == ["已選 2／3"]
    assert live.pick_captions(logic.GROUP_COMPARE, 3) == ["已選 3／3", "同時最多對照 3 檔"]
    assert live.pick_captions(logic.GROUP_WATCH, 5) == []
    assert live.PICK_CAPS == {logic.GROUP_COMPARE: logic.COMPARE_LIMIT, logic.GROUP_WATCH: None}


def test_上限句與既有第4個勾選框的停用原因同一句():
    rows = [{"_fund_code": c, "_ccy": "USD", "_cells": {}, "_checkboxes": {}} for c in ("A01", "B02", "C03", "D04")]
    model = logic.build_page_model(
        {"fund_profile": [{"fund_code": r["_fund_code"], "fund_name": r["_fund_code"], "ccy": "USD"} for r in rows],
         "nav": [], "dividend": [], "errors": {}},
        draft_rules=[{"field": "fund_code", "op": "不等於", "value": "ZZZ"}],
        compare_checked=("A01", "B02", "C03"), watch_checked=())
    exp2 = logic.find_block(model, "EXP-2")
    reasons = {r["_checkboxes"][logic.GROUP_COMPARE]["disabled_reason"] for r in exp2["_rows"]} - {""}
    assert reasons == {live.TEXT_PICK_FULL}


# ═══════════════════════ 純函式：每列來源展開 ═══════════════════════


def test_滑鼠提示拆段_只拿取得時間與資料日期_其餘原順序原字():
    tip = "淨值來源：FundClear；取得時間：2026-10-14T01:00:00Z；資料日期：2026-10-10"
    assert live.split_tip(tip) == ("2026-10-14T01:00:00Z", "2026-10-10", "淨值來源：FundClear")
    reason = "配息來源：合庫配息頁；配息資料未確認完整，配息比不計算；供列的來源（TCB：截斷 3；過濾 0）；配息依據：TCB"
    assert live.split_tip(reason) == (None, None, reason)
    assert live.split_tip(None) == (None, None, "")
    assert live.split_tip("取得時間：A；取得時間：B") == ("A", None, "取得時間：B")


def test_取得時間換台北時間_讀不懂或沒有時區原樣():
    assert live.taipei_time_text("2026-10-14T01:00:00Z") == "2026-10-14 09:00"
    assert live.taipei_time_text("2026-10-13T20:30:00+00:00") == "2026-10-14 04:30"
    assert live.taipei_time_text("2026-10-14T01:00:00") == "2026-10-14T01:00:00"
    assert live.taipei_time_text("昨天") == "昨天"


def test_一列的來源展開_依欄序_只列有來源資訊的格_缺的寫一槓():
    row = _row("A01", cells={
        "nav_date": _cell("2026-10-10", tag="FundClear",
                          tip="淨值來源：FundClear；取得時間：2026-10-14T01:00:00Z；資料日期：2026-10-10"),
        "div_ratio_pct": _cell("◇ 資料未備：配息資料未確認完整，配息比不計算", logic.STATE_MISSING, tag="合庫配息頁",
                               tip="配息來源：合庫配息頁；配息資料未確認完整，配息比不計算"),
    })
    row["_cells"]["fund_name"]["source_tag"] = "MoneyDJ"
    block = _block([row], keys=("fund_code", "fund_name", "nav_date", "div_ratio_pct"),
                   labels=("基金代碼", "基金名", "最近淨值日", "近 12 個月配息佔淨值比"))
    assert live.source_rows(block, row) == [
        ("基金名", "MoneyDJ", "—", "—", "—"),
        ("最近淨值日", "FundClear", "2026-10-14 09:00", "2026-10-10", "淨值來源：FundClear"),
        ("近 12 個月配息佔淨值比", "合庫配息頁", "—", "—", "配息來源：合庫配息頁；配息資料未確認完整，配息比不計算"),
    ]


def test_一格來源資訊都沒有_那一列沒有展開():
    row = _row("A01", "甲")
    assert live.source_rows(_block([row]), row) == []


# ═══════════════════════ 44：窄例外的射程寫死、凍結不變量 ═══════════════════════


def test_44_之十三在檔尾_窄例外射程寫在本檔():
    text = _D44.read_text(encoding="utf-8")
    assert "#### 第七節第三小節之十三｜" in text
    tail = text.split("#### 第七節第三小節之十三｜")[1]
    assert "只限標的探索結果清單的每一列，只放來源資訊" in tail
    rule = [line for line in text.split("\n") if line.startswith("**規則**：層 1 與層 2 的 `default_open`")]
    assert len(rule) == 1 and "本句只有一個窄例外" in rule[0]


def test_44_凍結不變量_塊數與判準行數照舊():
    lines = _D44.read_text(encoding="utf-8").split("\n")
    count = lambda prefix: sum(1 for line in lines if line.startswith(prefix))
    assert (count("#### 塊 "), count("**判準**"), count("**節判準**"), count("**表判準**"), count("**元件判準**")) == (
        41, 41, 7, 8, 5)


# ═══════════════════════ AppTest 接線（不標 slow，跑在 not-slow 線） ═══════════════════════

_SCRIPT_LIVE = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
sys.path.insert(0, {str(_HERE)!r})
import _exp_live_stub as STUB
from ui_v2.exp import page
page.render(load_live=STUB.load_live, save_live=STUB.save_setting)
"""

_ALL_RULES = json.dumps([{"field": "fund_code", "op": "不等於", "value": "ZZZ"}], ensure_ascii=False)


@pytest.fixture
def stub():
    pytest.importorskip("streamlit")
    import _exp_live_stub as STUB

    STUB.reset()
    STUB.WIRED.append(True)
    STUB.STORE["exp_filter_rules"] = _ALL_RULES
    STUB.STORE["exp_visible_columns"] = json.dumps(list(logic.COLUMN_ORDER))
    yield STUB
    STUB.reset()


def _run(script=_SCRIPT_LIVE):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(script, default_timeout=90)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _ok(at):
    assert not at.exception, [e.value for e in at.exception]
    return at


def _table_html(at) -> str:
    tables = [e.value for e in at.markdown if 'class="exp-table"' in e.value and "exp-scroll" in e.value]
    assert tables, "找不到結果清單那一張表"
    return tables[0]


def _picks(at):
    return {m.key: m for m in at.multiselect}


def test_正式模式_每列不再畫兩組勾選框_改兩份多選清單(stub):
    at = _run()
    assert not [c for c in at.checkbox if c.key and c.key.startswith("exp2_")]
    picks = _picks(at)
    compare, watch = picks["exp2live_pick_compare"], picks["exp2live_pick_watch"]
    assert compare.label == "要對照的基金（最多 3 檔）" and watch.label == "要加入觀察清單的基金"
    assert compare.value == [] and watch.value == []                       # 不預先選任何一檔
    assert compare.proto.max_selections == logic.COMPARE_LIMIT and watch.proto.max_selections == 0
    order = re.findall(r"<tr><td[^>]*>([A-Z]\d\d)", _table_html(at))
    assert [o.split("　")[0] for o in compare.options] == order       # 選項順序同結果清單
    assert compare.options == watch.options


def test_示範模式照舊每列兩組勾選框_沒有多選清單_沒有列展開():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(_ROOT / "ui_v2" / "app_exp.py"), default_timeout=90)
    at.query_params["scenario"] = "full"
    _ok(at.run())
    assert [c for c in at.checkbox if c.key and c.key.startswith("exp2_")]
    assert not [m for m in at.multiselect if m.key and m.key.startswith("exp2live_")]
    assert not any("<details" in e.value for e in at.markdown)


def test_對照選滿3檔_說明行與上限句_並排對照依基金代碼(stub):
    at = _run()
    _ok(at.multiselect(key="exp2live_pick_compare").select("C03").select("A01").run())
    assert [c.value for c in at.caption if c.value.startswith("已選")] == ["已選 2／3"]
    _ok(at.multiselect(key="exp2live_pick_compare").select("B02").run())
    caps = [c.value for c in at.caption]
    assert "已選 3／3" in caps and "同時最多對照 3 檔" in caps
    grid = html.unescape([e.value for e in at.markdown if 'class="exp-cmp-grid"' in e.value][0])
    heads = re.findall(r'class="exp-cmp-head">([^<]*)<', grid)
    assert [re.search(r"[A-Z]\d\d", h).group(0) for h in heads] == ["A01", "B02", "C03"]   # 依基金代碼，不依選取先後


def test_觀察清單_選了按加入_寫已存與選取的聯集_只加不減(stub):
    stub.STORE["exp_watchlist"] = '["Z09"]'
    at = _run()
    assert at.button(key="exp5live_btn_0").disabled                       # 一檔都沒選 → 停用
    _ok(at.multiselect(key="exp2live_pick_watch").select("A01").run())
    assert not at.button(key="exp5live_btn_0").disabled
    _ok(at.button(key="exp5live_btn_0").click().run())
    assert stub.STORE["exp_watchlist"] == '["A01", "Z09"]'
    writes = {key for key, _v, _k in stub.SAVES}
    assert writes == {"exp_watchlist"}                                    # 只寫觀察清單那一鍵


def test_已在觀察清單_選項加註_結果清單該列下方一行(stub):
    stub.STORE["exp_watchlist"] = '["B02"]'
    at = _run()
    watch = _picks(at)["exp2live_pick_watch"]
    assert "B02　測試基金 B02（已在觀察清單）" in watch.options
    assert not [o for o in _picks(at)["exp2live_pick_compare"].options if "已在觀察清單" in o]
    table = _table_html(at)
    assert table.count(logic.TEXT_ALREADY_WATCHED) == 1


def _details_by_code(table: str) -> dict:
    """結果清單那一張表 → {基金代碼: 該列下方那一枚列展開的 HTML}（展開裡沒有第二層 `<details>`）。"""
    codes = re.findall(r"<tr><td[^>]*>([A-Z]\d\d)</td>", table)
    blocks = re.findall(r"<details.*?</details>", table, flags=re.DOTALL)
    assert len(codes) == len(blocks), (codes, len(blocks))
    return dict(zip(codes, blocks))


def test_每列來源展開_預設收合_台北時間_配息比原因進備註_格內來源名照舊(stub):
    at = _run()
    table = html.unescape(_table_html(at))
    by_code = _details_by_code(table)
    assert len(by_code) == 10
    assert "<details open" not in table and table.count("<summary") == 10
    a01 = by_code["A01"]
    assert f">{live.ROW_SOURCE_TITLE}</summary>" in a01
    for label in live.ROW_SOURCE_LABELS:
        assert f">{label}</th>" in a01
    # 取得時間換成台北時間；展開裡不再印原值
    assert "<td>2026-10-14 09:00</td><td>2026-10-10</td>" in a01 and "2026-10-14T01:00:00Z" not in a01
    # 新設計 H 的展開那一半：D04 配息比的原因句進了該列展開的備註
    assert "配息資料未確認完整，配息比不計算" in by_code["D04"]
    assert "配息資料未確認完整，配息比不計算" not in a01
    # 格內來源名先保留（線框第 11 節）：格內照舊有來源標示與滑鼠提示；格內原因句照舊（H 的另一半排在後段）
    assert 'class="exp-src">FundClear<' in table and 'title="淨值來源：FundClear；取得時間：2026-10-14T01:00:00Z' in table
    assert ">◇ 資料未備：配息資料未確認完整，配息比不計算<span" in table


def test_沒有來源資訊的列_不畫列展開(stub):
    stub.WIRED.clear()                                                    # 未接線：各格只有「…尚未接入」
    at = _run()
    assert "<details" not in _table_html(at)


def test_換頁回來_勾選狀態已在而輸入欄是新的_多選清單照勾選狀態畫(stub):
    """預覽入口換頁時輸入欄狀態被清掉、勾選狀態（`logic.checked_key`）留著（`ui_v2/app_preview.py` 檔頭）：
    回到本頁時多選清單要照勾選狀態畫，不得變回空的（否則看不到、卻照樣寫進觀察清單）。"""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(_SCRIPT_LIVE, default_timeout=90)
    at.session_state[logic.checked_key(logic.GROUP_WATCH, live.LIVE_SCENARIO)] = ("Z09", "C03", "A01")
    at.session_state[logic.checked_key(logic.GROUP_COMPARE, live.LIVE_SCENARIO)] = ("B02",)
    _ok(at.run())
    picks = _picks(at)
    assert picks["exp2live_pick_watch"].value == ["A01", "C03"]          # 只放本次選項裡的、順序同結果清單
    assert picks["exp2live_pick_compare"].value == ["B02"]
    # 不在本次清單上的 Z09 照舊留在勾選狀態裡（與每列勾選框的行為相同）
    _ok(at.multiselect(key="exp2live_pick_watch").unselect("C03").run())
    assert at.session_state[logic.checked_key(logic.GROUP_WATCH, live.LIVE_SCENARIO)] == ("A01", "Z09")


def test_三張核心卡不適用那一句_逐字等於線框第六版待裁示1推薦原文():
    """總管 2026-10-19 裁定（適用客戶 `DEC-2026-10-19-05` 第 1 點）：列展開已有，改用 61 第 8 節 (1) 的推薦原文。"""
    d61 = (_ROOT / "docs" / "v2" / "61_bl0250_batch3_wireframe.md").read_text(encoding="utf-8")
    line = [l for l in d61.split("\n") if l.startswith("- **推薦：`⬜ 不適用（")]
    assert len(line) == 1
    assert f"`{live.TEXT_CARD_PROVENANCE_NA}`" in line[0]
    assert live.TEXT_CARD_PROVENANCE_NA == "⬜ 不適用（這張卡由多檔基金組成，各檔來源見每列展開）"
