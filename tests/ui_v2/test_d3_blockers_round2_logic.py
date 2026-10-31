# -*- coding: utf-8 -*-
"""D-3 阻擋項修正第二輪（獨立稽核 B1／B2／S1～S4／S6；客戶 2026-10-30 裁示 `docs/DECISIONS.md` `DEC-2026-10-30-04`）的 logic 層守衛（fast lane）。

客戶原話（`docs/evidence/decisions/2026-10-30_d3_oauth_gate_rulings.md`）：
- F-18／BL-0411：「如果部分列目前被略過但 UI 沒揭露：頁燈、持有 N 檔、配置／持股整體判定都不能假裝覆蓋完整集合。
  必須先讓 omitted rows／未納入集合的事實可被辨識。」
- F-2：「持股只評估一部分時：不得只顯示「無偏離項」。必須同時讓使用者看得到既有的缺值／未評估原因。不要新增第二套 Missing vocabulary。」

- **B1**：保單分頁被略過（`skipped_tabs`）時，`ALO-0` 不寫「尚未建立任何持倉」，燈下寫出是哪一張分頁（字同持倉體檢同一件事）。
- **B2**：持倉列全數被略過時，`HLD-1`／`HLD-2`／`HLD-3`（與 `HLD-5`／`HLD-8`、紅燈補述）不寫「尚未建立任何持倉」。
- **S1**：有持倉、零偏離而有略過的列時，`HLD-1` 不寫「無偏離項」與「目前這一組門檻下，沒有任何一檔超出。」。
- **S2**：合併頁「基金占比」不以「N 檔」、佔比合計假裝覆蓋完整集合（`ui_v2/asset/overview.py`）。
- **S3**：74 H6（逐檔配息取數失敗、塊照舊 ok）屬持股只評估一部分 → `HLD-0` 帶原因（含 ⛔）、記 `_partial`，不寫「沒有任何一檔超出」。
- **S4**：F-2 那一行帶上卡上既有的原因（資料類／取數失敗原文），不只狀態字。
- **S6**：持股側資料承載層遮蔽略過列的原因字（拿掉 `mask()` 這幾條轉紅）。
本檔不含頁級合併燈（P3 尚未實作）。
"""

from __future__ import annotations

import copy
import pathlib
import re
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from ui_v2 import page_health, presentation  # noqa: E402
from ui_v2.alo import fixtures as AF  # noqa: E402
from ui_v2.alo import live as alo_live  # noqa: E402
from ui_v2.alo import logic as AL  # noqa: E402
from ui_v2.asset import overview as OV  # noqa: E402
from ui_v2.hld import fixtures as HF  # noqa: E402
from ui_v2.hld import live as hld_live  # noqa: E402
from ui_v2.hld import logic as HL  # noqa: E402

import test_d3_blockers_logic as R1  # noqa: E402  第一輪的 helper（正式模式那幾步、略過列 fixture）

_SKIPPED = R1._SKIPPED
_SKIPPED_LINE = R1._SKIPPED_LINE
_SKIPPED_FORMAL = "◇ 資料未備：PX-TEST-001 第 7 列（ZZ9999） 未列入：缺持倉補充"
_TAB = [{"tab": "PX-TEST-009", "error": "標頭格式有誤"}]
_TAB_LINE = "⛔ 取數失敗：PX-TEST-009：標頭格式有誤"
_TAB_FORMAL = "⛔ PX-TEST-009 取數失敗"


def _strings(model, collect):
    return "\n".join(collect(model))


# ───────────────────────── B1：ALO 側被略過的保單分頁 ─────────────────────────


def test_B1_持倉為空_只有略過的分頁_不寫尚未建立任何持倉_改配置差距無法判定():
    ds = R1._with(AF.scenario("noholding"), skipped_tabs=_TAB)
    alo0 = R1._alo0(ds)
    assert alo0["text"] == AL.TEXT_UNDECIDABLE_GAP and alo0["text"] != AL.TEXT_NO_HOLDING
    assert alo0["_incomplete"] is True and alo0["_tone"] == "灰" and alo0["_max_bucket"] is None
    assert alo0["detail_lines"][0] == _TAB_LINE
    formal = R1._alo_formal(ds)
    assert AL.TEXT_NO_HOLDING not in _strings(formal, AL.collect_ui_strings)
    assert AL.find_block(formal, "ALO-0")["detail_lines"][0] == _TAB_FORMAL
    # 真的空照舊（沒有略過任何分頁）
    assert R1._alo0(AF.scenario("noholding"))["text"] == AL.TEXT_NO_HOLDING


def test_B1_有持倉_略過的分頁在燈下可辨識_燈句與燈色規則照舊():
    ds = R1._with(AF.scenario("inband"), skipped_tabs=_TAB)
    alo0 = R1._alo0(ds)
    assert alo0["text"] == AL.TEXT_UNDECIDABLE_GAP and alo0["detail_lines"][0] == _TAB_LINE
    # 有偏離時照舊點名（已評估類別的結果照留），分頁那一行照樣在
    full = R1._alo0(R1._with(AF.scenario("full"), skipped_tabs=_TAB))
    assert full["text"].endswith(" 個百分點") and full["_tone"] == "黃" and full["detail_lines"][0] == _TAB_LINE
    # 那一句「⛔ 取數失敗」的資料類記為持倉（頁首與總表才認得它，不落到「認不出資料類」）
    assert ("PX-TEST-009：標頭格式有誤", "持倉") in alo0[page_health.FETCH_CLASSES_KEY]


def test_B1_略過的分頁那一行逐字同持倉體檢同一件事的寫法():
    """持倉體檢：`hld/live.assemble_live_load` 把 `skipped_tabs` 組成 `errors["holding"]`，`HLD-1` 以 `fetch_failed_text` 印出。"""
    tabs = [{"tab": "PX-TEST-009", "error": "標頭格式有誤", "unread": False}, {"tab": "PX-TEST-010", "error": None, "unread": True}]
    base = dict(
        holding_error=None, settings=None, settings_error="settings unreadable", key_results=[],
        nav_table={"rows": [], "errors": {}, "withheld": {}, "skipped": {}, "fetched": {}, "skipped_rows": {}, "provenance": {}},
        direct_policy_id="DIRECT", policy_tab_source="保單分頁", direct_sources={"保單分頁"}, empty_without_reason="x",
        nav_unavailable_withheld=frozenset(), dividend_gate_open=False, mask=str, dividend_table=None,
    )
    hld_ds = hld_live.assemble_live_load(
        holding_tables={"holding": [], "policy": [], "direct": [], "skipped_tabs": tabs}, **base)["dataset"]
    alo_ds = R1._with(AF.scenario("inband"), **alo_live.skipped_for_dataset({"skipped_tabs": tabs}, str))
    assert R1._alo0(alo_ds)["detail_lines"][0] == HL.fetch_failed_text(hld_ds["errors"]["holding"]) \
        == "⛔ 取數失敗：PX-TEST-009：標頭格式有誤；PX-TEST-010"


def test_B1_分頁與略過的列都有時_分頁那一行在前():
    alo0 = R1._alo0(R1._with(AF.scenario("inband"), skipped_tabs=_TAB, skipped_holdings=_SKIPPED))
    assert alo0["detail_lines"][:2] == [_TAB_LINE, _SKIPPED_LINE]
    assert alo0["_omitted_rows"] == tuple(_SKIPPED)


def test_B1_分頁名不是文字_當場炸_不猜():
    with pytest.raises(ValueError):
        AL.skipped_tab_message([{"tab": None}])
    assert AL.skipped_tab_message(()) == ""


def test_B1_沒有略過任何分頁_燈逐鍵與動手前相同():
    alo0 = R1._alo0(AF.scenario("inband"))
    assert alo0["text"] == AL.TEXT_ALL_IN_BAND
    assert "_skipped_tab_text" not in alo0 and page_health.FETCH_CLASSES_KEY not in alo0
    assert not any(line.startswith("⛔") for line in alo0["detail_lines"])


# ───────────────────────── B2：持倉列全數被略過，卡上不寫「尚未建立任何持倉」─────────────────────────


def _hld_empty(name="empty"):
    args = HF.scenario(name)
    return args, R1._with(args["dataset"], skipped_holdings=_SKIPPED)


def _hld_model(args, ds, formal=False):
    kw = {k: v for k, v in args.items() if k not in ("dataset", "demo_hint")}
    return R1._hld_formal(ds, **kw) if formal else HL.build_page_model(**{**args, "dataset": ds})


@pytest.mark.parametrize("formal", [False, True])
def test_B2_持倉列全數被略過_整頁沒有一處尚未建立任何持倉(formal):
    args, ds = _hld_empty()
    model = _hld_model(args, ds, formal)
    assert HL.TEXT_NO_HOLDING not in _strings(model, HL.collect_ui_strings)
    line = _SKIPPED_FORMAL if formal else _SKIPPED_LINE
    for code in ("HLD-1", "HLD-2", "HLD-3"):
        block = HL.find_block(model, code)
        assert line in block["detail_lines"], code
        # ~~`in (HL.ND_TEXT, "◇ 資料未備")`~~ → D-3 第三輪（獨立稽核 should-fix 3；有意識的更正，不是漏刪）：摘要保留資料類，
        # 既有字型「⬜／◇ 資料未備：持倉」（`HL.OMITTED_SUMMARY`；見 `test_d3_blockers_round3_logic.py::test_SF3_*`）。
        assert block["summary_text"] == ("◇ 資料未備：持倉" if formal else HL.OMITTED_SUMMARY), code


def test_B2_各塊的狀態與主值不動_只換字():
    args, ds = _hld_empty()
    plain_model = HL.build_page_model(**args)
    model = HL.build_page_model(**{**args, "dataset": ds})
    for code in ("HLD-1", "HLD-2", "HLD-3", "HLD-5", "HLD-8"):
        a, b = HL.find_block(plain_model, code), HL.find_block(model, code)
        assert b["_state"] == a["_state"] == HL.STATE_MISSING, code
        assert b.get("_placeholder") == a.get("_placeholder"), code
    # 真的空照舊
    assert HL.TEXT_NO_HOLDING in _strings(plain_model, HL.collect_ui_strings)


def test_B2_空持倉而有一塊取數失敗_紅燈補述不寫尚未建立任何持倉():
    args, ds = _hld_empty("emptyfail")
    hld0 = HL.find_block(HL.build_page_model(**{**args, "dataset": ds}), "HLD-0")
    assert hld0["_tone"] == "紅"                                                     # 紅燈照舊
    assert HL.HLD0_NO_HOLDING_ASIDE not in hld0["lines"] and _SKIPPED_LINE in hld0["lines"]
    plain_hld0 = HL.find_block(HL.build_page_model(**args), "HLD-0")
    assert HL.HLD0_NO_HOLDING_ASIDE in plain_hld0["lines"]                           # 真的空照舊


def test_B2_ALO側_持倉全數被略過或分頁被略過_整頁沒有一處尚未建立任何持倉():
    for extra in ({"skipped_holdings": _SKIPPED}, {"skipped_tabs": _TAB}):
        model = R1._alo_formal(R1._with(AF.scenario("noholding"), **extra))
        assert AL.TEXT_NO_HOLDING not in _strings(model, AL.collect_ui_strings), extra


# ───────────────────────── S1：零偏離而有略過的列，HLD-1 不寫覆蓋完整集合的句子 ─────────────────────────


def _noexceed():
    return HF._dataset(window=(HF.WINDOW_START, HF.WINDOW_END), rules=(HF._RULES_NOEXCEED[0],))


@pytest.mark.parametrize("formal", [False, True])
def test_S1_HLD1零偏離_有略過的列_不寫無偏離項與沒有任何一檔超出(formal):
    ds = R1._with(_noexceed(), skipped_holdings=_SKIPPED)
    model = R1._hld_formal(ds) if formal else HL.build_page_model(ds, demo_hint=False)
    hld1 = HL.find_block(model, "HLD-1")
    assert hld1["_rows"] == [] and hld1["_state"] == HL.STATE_OK                    # 已評估的檔照舊零偏離、塊態不動
    assert HL.TEXT_NO_DEVIATION_LINE not in hld1["detail_lines"]
    assert hld1["summary_text"] != HL.TEXT_NO_DEVIATION
    assert hld1["_placeholder"] is not None and hld1["_placeholder"]["text"] in (HL.ND_TEXT, "◇ 資料未備")
    assert (_SKIPPED_FORMAL if formal else _SKIPPED_LINE) in hld1["detail_lines"]
    assert page_health.DATA_CLASSES["holding"] in hld1[page_health.MISSING_KEYS_KEY]
    assert page_health.DATA_CLASSES["holding"] in hld1["_placeholder"][page_health.MISSING_KEYS_KEY]
    assert HL.TEXT_NO_DEVIATION_LINE not in _strings(model, HL.collect_ui_strings)


def test_S1_沒有略過的列_HLD1照舊無偏離項():
    hld1 = HL.find_block(HL.build_page_model(_noexceed(), demo_hint=False), "HLD-1")
    assert hld1["summary_text"] == HL.TEXT_NO_DEVIATION and hld1["_placeholder"] is None
    assert HL.TEXT_NO_DEVIATION_LINE in hld1["detail_lines"] and "_omitted_rows" not in hld1


def test_S1_有偏離列時HLD1照舊列出_不加略過的列():
    ds = R1._with(HF.scenario("full")["dataset"], skipped_holdings=_SKIPPED)
    a = HL.find_block(HL.build_page_model(HF.scenario("full")["dataset"], demo_hint=False), "HLD-1")
    b = HL.find_block(HL.build_page_model(ds, demo_hint=False), "HLD-1")
    assert b == a


# ───────────────────────── S2：合併頁「基金占比」─────────────────────────


def test_S2_有略過的列_件數那一枚改資料未備_合計之後接略過的列():
    alo = R1._alo_formal(R1._with(AF.scenario("inband"), skipped_holdings=_SKIPPED))
    alo2, alo4, alo6 = (AL.find_block(alo, c) for c in ("ALO-2", "ALO-4", "ALO-6"))
    omitted = OV.share_omitted_lines(alo2)
    assert omitted == [_SKIPPED_FORMAL]
    rows = OV.share_rows(alo6)
    chips = OV.share_chips(alo4, rows, omitted_lines=omitted)
    assert chips[0]["text"] == presentation.MISSING_CHIP_TEXT == "◇ 資料未備"
    assert not any(re.fullmatch(r"\d+ 檔", c["text"]) for c in chips)
    # ~~`OV.share_detail(alo6, omitted_lines=omitted)`~~ → D-3 第三輪（獨立稽核 should-fix 1；有意識的更正，不是漏刪）：
    # 略過的列改由 `ALO-6` 自己接在表尾（單頁與合併頁同一份），`share_detail` 照舊只讀表尾、不另接（參數拿掉）。
    limits = dict(OV.share_detail(alo6)["groups"])["限制"]
    total = next(i for i, line in enumerate(limits) if line.startswith("總體佔比合計"))
    assert limits[total + 1] == _SKIPPED_FORMAL
    assert limits.count(_SKIPPED_FORMAL) == 1


def test_S2_沒有略過的列_照舊N檔():
    alo = R1._alo_formal(AF.scenario("inband"))
    alo2, alo4, alo6 = (AL.find_block(alo, c) for c in ("ALO-2", "ALO-4", "ALO-6"))
    omitted = OV.share_omitted_lines(alo2)
    assert omitted == []
    rows = OV.share_rows(alo6)
    assert OV.share_chips(alo4, rows, omitted_lines=omitted) == OV.share_chips(alo4, rows)
    assert OV.share_chips(alo4, rows)[0]["text"] == f"{len(rows)} 檔"
    # ~~`assert OV.share_detail(alo6, omitted_lines=omitted) == OV.share_detail(alo6)`~~（D-3 第三輪：參數已拿掉，有意識的更正，不是漏刪）
    assert not any("未列入" in line for line in dict(OV.share_detail(alo6)["groups"])["限制"])


# ───────────────────────── S3：74 H6（逐檔配息取數失敗，塊照舊 ok）─────────────────────────


def _h6():
    ds = _noexceed()
    ds["fund_errors"] = {"nav": {}, "dividend": {"CCCC": "上游逾時（探針）"}}
    return ds


def test_S3_H6_塊照舊ok_燈不寫沒有任何一檔超出_帶上取數失敗原因_記partial():
    model = HL.build_page_model(_h6(), demo_hint=False)
    hld0, hld1, hld3 = (HL.find_block(model, c) for c in ("HLD-0", "HLD-1", "HLD-3"))
    assert hld3["_state"] == HL.STATE_OK and hld1["_state"] == HL.STATE_OK and hld1["_rows"] == []   # 前提（塊態不動）
    assert hld0["text"] == HL.TEXT_NO_DEVIATION
    assert HL.TEXT_NO_DEVIATION_LINE not in hld0["lines"]
    assert hld0["lines"] == ["配息與本金卡：⛔ 取數失敗：CCCC：上游逾時（探針）"]
    assert hld0["_partial"] is True
    assert hld0["_state"] == HL.STATE_OK and hld0["_tone"] == "灰"                   # 燈的狀態與色照舊（頁級規則讀 `_partial`）
    assert ("CCCC：上游逾時（探針）", "配息") in hld0[page_health.FETCH_CLASSES_KEY]


def test_S3_H6_正式模式燈下有那一檔的取數失敗():
    hld0 = HL.find_block(R1._hld_formal(_h6()), "HLD-0")
    assert hld0["lines"] == ["配息與本金卡：⛔ CCCC 取數失敗"]
    assert hld0["_partial"] is True


def test_S3_三塊每一個值都ok時照舊無偏離項與那一句():
    hld0 = HL.find_block(HL.build_page_model(_noexceed(), demo_hint=False), "HLD-0")
    assert hld0["lines"] == [HL.TEXT_NO_DEVIATION_LINE] and "_partial" not in hld0


# ───────────────────────── S4：F-2 那一行帶原因 ─────────────────────────


@pytest.mark.parametrize("mv,expect", [
    ({"_state": HL.STATE_MISSING, "text": HL.ND_TEXT, "_missing_keys": ("配息",)}, "⬜ 資料未備：配息"),
    ({"_state": HL.STATE_MISSING, "text": HL.ND_TEXT, "_missing_keys": ("淨值", "配息")}, "⬜ 資料未備：淨值、配息"),
    ({"_state": HL.STATE_MISSING, "text": HL.ND_TEXT}, HL.ND_TEXT),                                    # 沒記原因 → 只寫狀態字（不猜）
    ({"_state": HL.STATE_ERROR, "text": HL.ERR_TEXT, "reason_text": "逾時", "_fund_scoped_error": True}, "⛔ 取數失敗：G01：逾時"),
    ({"_state": HL.STATE_ERROR, "text": HL.ERR_TEXT, "reason_text": "逾時"}, "⛔ 取數失敗：逾時"),
    ({"_state": HL.STATE_ERROR, "text": HL.ERR_TEXT, "reason_text": ""}, HL.ERR_TEXT),
    ({"_state": HL.STATE_BIZ, "text": "⬜ 不適用：區間內無配息"}, "⬜ 不適用：區間內無配息"),
    ({"_state": HL.STATE_OK, "text": "1.00%"}, None),
])
def test_S4_每一種非ok主值帶卡上既有的原因字(mv, expect):
    assert HL._partial_reason_text({"_fund_code": "G01"}, mv) == expect


def test_S4_不計數_不出第二套缺值字樣():
    for ds in (R1._h7(), _h6()):
        for line in HL.find_block(R1._hld_formal(ds), "HLD-0")["lines"]:
            assert not re.search(r"\d+\s*(檔|項|筆)", line), line
            assert any(t in line for t in ("◇ 資料未備", "⬜ 不適用", "取數失敗")), line


# ───────────────────────── S6：持股側資料承載層遮蔽略過列的原因字 ─────────────────────────

_SECRET = "TOKEN-sk-0042-only-in-tests"


def _secret_row():
    return {"tab": "PX-TEST-001", "row": 7, "policy_id": "PX-TEST-001", "fund_code": "ZZ9999",
            "reasons": [f"缺持倉補充（{_SECRET}）"]}


def _mask(text):
    return text.replace(_SECRET, "＊＊＊")


def test_S6_HLD承載層_略過列的原因字經遮蔽():
    rows = hld_live._omitted_rows_for_dataset([_secret_row()], _mask)
    assert _SECRET not in repr(rows)
    assert rows[0]["reasons"] == ["缺持倉補充（＊＊＊）"]
    assert _SECRET not in "\n".join(page_health.omitted_row_lines(rows))


def test_S6_HLD承載層_一路到燈下都沒有原字():
    base = dict(
        holding_error=None, settings=None, settings_error="settings unreadable", key_results=[],
        nav_table={"rows": [], "errors": {}, "withheld": {}, "skipped": {}, "fetched": {}, "skipped_rows": {}, "provenance": {}},
        direct_policy_id="DIRECT", policy_tab_source="保單分頁", direct_sources={"保單分頁"}, empty_without_reason="x",
        nav_unavailable_withheld=frozenset(), dividend_gate_open=False, mask=_mask, dividend_table=None,
    )
    tables = {"holding": [], "policy": [], "direct": [], "skipped_tabs": [], "skipped_holdings": [_secret_row()]}
    ds = hld_live.assemble_live_load(holding_tables=tables, **base)["dataset"]
    assert _SECRET not in repr(ds["skipped_holdings"])
    args = HF.scenario("empty")
    model = HL.build_page_model(**{**args, "dataset": R1._with(args["dataset"], skipped_holdings=ds["skipped_holdings"])})
    assert _SECRET not in _strings(model, HL.collect_ui_strings)
    assert "缺持倉補充（＊＊＊）" in _strings(model, HL.collect_ui_strings)


def test_S6_ALO承載層_略過列的原因字與分頁原因經遮蔽():
    got = alo_live.skipped_for_dataset(
        {"skipped_holdings": [_secret_row()], "skipped_tabs": [{"tab": "T9", "error": f"標頭格式有誤 {_SECRET}"}]}, _mask)
    assert _SECRET not in repr(got)
    assert got["skipped_holdings"][0]["reasons"] == ["缺持倉補充（＊＊＊）"]
    assert got["skipped_tabs"] == [{"tab": "T9", "error": "標頭格式有誤 ＊＊＊"}]


# ───────────────────────── 追溯：各修法不動 domain block 的判定 ─────────────────────────


def test_追溯_第二輪各修法不動ALO2至ALO7與HLD2至HLD8的每一格_除B2換字的那幾塊():
    """B1／S2 只動燈與合併頁呈現；S3／S4 只動燈。`ALO-2`～`ALO-7` 每一格不變；有持倉時 `HLD-2`～`HLD-8` 每一格不變。"""
    alo_a = AL.build_page_model(AF.scenario("inband"))
    alo_b = AL.build_page_model(R1._with(AF.scenario("inband"), skipped_tabs=_TAB))
    for code in [b["code"] for b in alo_a["blocks"] if b["code"] != "ALO-0"]:
        assert R1._strip(AL.find_block(alo_b, code)) == AL.find_block(alo_a, code), code
    h_a = HL.build_page_model(_noexceed(), demo_hint=False)
    h_b = HL.build_page_model(_h6(), demo_hint=False)
    a3, b3 = HL.find_block(h_a, "HLD-3"), HL.find_block(h_b, "HLD-3")
    assert b3["_state"] == a3["_state"] == HL.STATE_OK                                # S3 不改塊態
    h_c = HL.build_page_model(R1._with(_noexceed(), skipped_holdings=_SKIPPED), demo_hint=False)
    for code in [b["code"] for b in h_a["blocks"] if b["code"] not in ("HLD-0", "HLD-1")]:
        assert R1._strip(HL.find_block(h_c, code)) == HL.find_block(h_a, code), code


def test_全部情境與兩組略過變體_ALO0與HLD0都有字_且不出現覆蓋完整集合的句子():
    """F-14「任何正式狀態不得出現『有狀態但沒有文字』」＋ F-18 的反向掃描（含第二輪新增的分頁變體）。"""
    for name in AF.ALL_SCENARIO_NAMES:
        for extra in ({"skipped_tabs": _TAB}, {"skipped_holdings": _SKIPPED}, {"skipped_tabs": _TAB, "skipped_holdings": _SKIPPED}):
            ds = R1._with(AF.scenario(name), **copy.deepcopy(extra))
            alo0 = R1._alo0(ds)
            assert isinstance(alo0["text"], str) and alo0["text"].strip(), (name, extra)
            assert alo0["text"] not in (AL.TEXT_ALL_IN_BAND, AL.TEXT_NO_HOLDING), (name, extra)
    for name in HF.ALL_SCENARIO_NAMES:
        args = HF.scenario(name)
        ds = R1._with(args["dataset"], skipped_holdings=_SKIPPED)
        model = HL.build_page_model(**{**args, "dataset": ds})
        text = "\n".join(HL.collect_ui_strings(model))
        assert HL.find_block(model, "HLD-0")["text"].strip(), name
        assert HL.TEXT_NO_HOLDING not in text and HL.TEXT_NO_DEVIATION_LINE not in text, name
