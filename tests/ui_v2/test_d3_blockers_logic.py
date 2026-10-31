# -*- coding: utf-8 -*-
"""D-3 阻擋項（客戶 2026-10-30 裁示 `docs/DECISIONS.md` `DEC-2026-10-30-04`；`docs/v2/74_assets_d3_formula_gate.md` 第 5 節）的 logic 層守衛（fast lane）。

- **F-13**：任何配置類別沒有成功評估時，`ALO-0` 不得寫「各類別皆在容許帶內」（74 A6m 條件 (1)～(4)）；改既有「配置差距無法判定」。
- **F-14**：任何正式狀態不得有狀態而沒有字（74 A5c）。
- **F-19**：有值而沒有目標的類別算「沒評估到」（未分類、類別名不在名單內、名單內卻沒有目標列）。
- **F-2**：持股只評估一部分（74 H7）時，`HLD-0` 不得只寫「無偏離項」，要帶上 `HLD-2`／`HLD-3` 卡上既有的未評估字樣。
- **F-18／BL-0411**：保單分頁上有列沒寫進持倉（L2 `skipped_holdings`）時，燈、「持有 N 檔」、配置／持股整體判定都不得假裝覆蓋完整集合。

另守「domain block 的原始狀態與 reason 完整保留、可追溯」：各修法只改燈那一塊（與 `sections` 的檔數），不動 `ALO-2`／`HLD-1～3` 的任何一格。
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

from ui_v2 import health, page_health, plain, sections, symbols  # noqa: E402
from ui_v2.alo import fixtures as AF  # noqa: E402
from ui_v2.alo import live as alo_live  # noqa: E402
from ui_v2.alo import logic as AL  # noqa: E402
from ui_v2.asset import overview as OV  # noqa: E402
from ui_v2.hld import fixtures as HF  # noqa: E402
from ui_v2.hld import live as hld_live  # noqa: E402
from ui_v2.hld import logic as HL  # noqa: E402

# 一列 L2 `skipped_holdings`（形狀照 `services/v2_tables/alo_holdings.py::build_alo_tables`；原因字逐字是 L2 的字）。
_SKIPPED = [{"tab": "PX-TEST-001", "row": 7, "policy_id": "PX-TEST-001", "fund_code": "ZZ9999", "reasons": ["缺持倉補充"]}]
_SKIPPED_LINE = "⬜ 資料未備：PX-TEST-001 第 7 列（ZZ9999） 未列入：缺持倉補充"


def _with(ds, **extra):
    out = copy.deepcopy(ds)
    out.update(copy.deepcopy(extra))
    return out


def _alo0(ds):
    return AL.find_block(AL.build_page_model(ds), "ALO-0")


def _alo_formal(ds):
    """正式模式那幾步（同 `ui_v2/alo/page.py::prepare_live`）：只換字與符號，判定不動。"""
    model = alo_live.apply_live_notes(AL.build_page_model(ds), wired_keys=(), runtime_source=False, sheet_failed=False)
    model, _raw, _status = plain.plain_model(model, page="alo")
    symbols.apply(model)
    model, failures = health.dedupe_failures(model)
    health.relabel_unconfigured(model, failures)
    return model


def _hld_formal(ds, **kw):
    model = HL.build_page_model(ds, demo_hint=False, **kw)
    model, _raw, _status = plain.plain_model(model, page="hld")
    symbols.apply(model)
    model, failures = health.dedupe_failures(model)
    health.relabel_unconfigured(model, failures)
    return model


def _blank_first_target(ds):
    ds = copy.deepcopy(ds)
    for row in ds["user_setting"]:
        if row["setting_key"] == "alo_target_weights":
            row["setting_value"][0]["weight_ratio"] = None
    return ds


def _mv_unbucketed_without_nav():
    """A6m 條件 (2)：無目標的類別（未分類）缺基準值 —— 不擋燈。"""
    ds = AF._dataset(basis=AF.BASIS_MV, unbucket=AF.UNBUCKETED_FUND, tolerance=40)
    ds["nav"] = [r for r in ds["nav"] if r["fund_code"] != AF.UNBUCKETED_FUND]
    return ds


def _named_bucket_without_target():
    """F-19 第三種：類別名在名單內、目標表沒有這一列。"""
    ds = AF._dataset(bucket_names=AF.BUCKET_NAMES + (AF.BOND,), tolerance=40)
    ds["holding"][-1]["bucket"] = AF.BOND
    return ds


def _a5c():
    """74 A5c（F-14）：市值基準、無匯率、拿掉兩檔台幣基金淨值、目標表第一列有比重而沒有持倉。"""
    targets = ({"bucket": AF.BOND, "weight_ratio": 0.10},) + tuple(AF.TARGETS)
    ds = AF._dataset(basis=AF.BASIS_MV, fx=False, targets=targets, bucket_names=AF.BUCKET_NAMES + (AF.BOND,))
    ds["nav"] = [r for r in ds["nav"] if r["fund_code"] not in ("BBBB", "DDDD")]
    return ds


# ───────────────────────── F-13／F-19：ALO-0 不從已評估子集合推論帶內 ─────────────────────────

_INCOMPLETE_CASES = {
    "A6m(1)目標比重留空": lambda: _blank_first_target(AF.scenario("inband")),
    "A6m(2)無目標類別缺值": _mv_unbucketed_without_nav,
    "A6m(3)保單分頁被略過": lambda: _with(AF.scenario("inband"), skipped_tabs=[{"tab": "PX-TEST-009"}]),
    "A6m(4)F19未分類_成本基準": lambda: AF._dataset(unbucket="CCCC", tolerance=40),
    "A6m(4)F19未分類_市值基準": lambda: AF._dataset(unbucket="CCCC", tolerance=40, basis=AF.BASIS_MV),
    "A6m(4)F19名單內卻沒有目標列": _named_bucket_without_target,
    "F18略過的持倉列": lambda: _with(AF.scenario("inband"), skipped_holdings=_SKIPPED),
}


@pytest.mark.parametrize("name", list(_INCOMPLETE_CASES))
def test_F13_有類別沒評估到_ALO0不寫皆在容許帶內_改寫配置差距無法判定(name):
    ds = _INCOMPLETE_CASES[name]()
    alo0 = _alo0(ds)
    assert alo0["text"] != AL.TEXT_ALL_IN_BAND, name
    assert alo0["text"] == AL.TEXT_UNDECIDABLE_GAP == "配置差距無法判定", name
    assert alo0["_incomplete"] is True, name
    assert alo0["_tone"] == "灰" and alo0["_max_bucket"] is None, name          # 燈色規則照舊
    # 正式模式畫面上同樣不出現帶內那一句
    formal = AL.find_block(_alo_formal(ds), "ALO-0")
    assert formal["text"] == AL.TEXT_UNDECIDABLE_GAP, name
    assert AL.TEXT_ALL_IN_BAND not in "\n".join(AL.collect_ui_strings({"blocks": [formal]})), name


def test_F19_重現_unbucket_CCCC_tolerance40_兩基準皆不再寫帶內():
    for basis in (AF.BASIS_COST, AF.BASIS_MV):
        model = AL.build_page_model(AF._dataset(unbucket="CCCC", tolerance=40, basis=basis))
        alo2 = AL.find_block(model, "ALO-2")
        unclassified = next(r for r in alo2["_rows"] if r["_bucket"] == AL.UNCLASSIFIED)
        assert unclassified["_value"] and unclassified["_diff"] is None and unclassified["_has_target"] is False
        assert AL.find_block(model, "ALO-0")["text"] == AL.TEXT_UNDECIDABLE_GAP, basis


def test_F13_評估完整時照舊寫皆在容許帶內_不加任何新鍵():
    alo0 = _alo0(AF.scenario("inband"))
    assert alo0["text"] == AL.TEXT_ALL_IN_BAND
    assert "_incomplete" not in alo0 and "_omitted_rows" not in alo0


def test_F13_已評估類別的結果照留_超出容許帶照點名_只記不完整():
    """「已成功評估的類別結果可以保留」：有偏離的類別照點名；只多記 `_incomplete`。"""
    ds = AF._dataset(unbucket="CCCC")                       # 預設容許帶 4：衛星超出
    alo0 = _alo0(ds)
    assert alo0["text"].endswith(" 個百分點") and alo0["_leaders"], alo0
    assert alo0["_incomplete"] is True
    full = _alo0(AF.scenario("full"))
    assert full["text"].endswith(" 個百分點") and "_incomplete" not in full


# ───────────────────────── F-14：沒有字的燈 ─────────────────────────


def test_F14_A5c_燈有字_用既有配置差距無法判定_不補成帶內():
    alo0 = _alo0(_a5c())
    assert alo0["text"] == AL.TEXT_UNDECIDABLE_GAP
    assert alo0["text"] not in (AL.TEXT_ALL_IN_BAND, HL.TEXT_NO_DEVIATION)
    formal = AL.find_block(_alo_formal(_a5c()), "ALO-0")
    assert isinstance(formal["text"], str) and formal["text"].strip(), formal


def test_F14_被擋下的第一列有字時照舊印那一列的理由():
    ds = AF.scenario("nofx")
    alo0 = _alo0(ds)
    alo2 = AL.find_block(AL.build_page_model(ds), "ALO-2")
    blocked = [r for r in alo2["_rows"] if r["_blocks_lamp"]]
    assert blocked and blocked[0]["_gap_text"] and alo0["text"] == blocked[0]["_gap_text"]


def test_F14_全部情境與阻擋項變體_ALO0與HLD0都有字():
    alo_sets = [AF.scenario(n) for n in AF.ALL_SCENARIO_NAMES] + [f() for f in _INCOMPLETE_CASES.values()] + [_a5c()]
    alo_sets.append(_with(AF.scenario("noholding"), skipped_holdings=_SKIPPED))
    for ds in alo_sets:
        text = AL.find_block(AL.build_page_model(ds), "ALO-0")["text"]
        assert isinstance(text, str) and text.strip(), ds
        formal = AL.find_block(_alo_formal(ds), "ALO-0")
        # 正式模式唯一允許燈句為空的情形：取數失敗（74 A1）—— `health.trim_light_echo` 拿掉與頁首同一句的燈句，
        # 燈上照舊有「⛔ 狀態：取數失敗」那幾個字（狀態字本身就是文字），不是「有狀態但沒有文字」的中性燈。
        if not (isinstance(formal["text"], str) and formal["text"].strip()):
            assert (formal["glyph"], formal["state_word"]) == ("⛔", "狀態：取數失敗"), formal
    for name in HF.ALL_SCENARIO_NAMES:
        args = HF.scenario(name)
        for ds in (args["dataset"], _with(args["dataset"], skipped_holdings=_SKIPPED)):
            text = HL.find_block(HL.build_page_model(**{**args, "dataset": ds}), "HLD-0")["text"]
            assert isinstance(text, str) and text.strip(), name


# ───────────────────────── F-2：持股只評估一部分（H7）─────────────────────────


def _h7():
    """74 H7（v5 實跑條件）：`dataset_noexceed` ＋ 配息表未接上 ＋ 門檻只用最大回撤。"""
    ds = HF._dataset(window=(HF.WINDOW_START, HF.WINDOW_END), rules=(HF._RULES_NOEXCEED[0],))
    ds["pending_tables"] = frozenset({"dividend"})
    return ds


def test_F2_H7_燈照舊無偏離項但同時帶上HLD3卡上既有的未評估字樣():
    model = HL.build_page_model(_h7(), demo_hint=False)
    hld0, hld1, hld3 = (HL.find_block(model, c) for c in ("HLD-0", "HLD-1", "HLD-3"))
    # 前提：HLD-1 完整評估、零偏離；HLD-3 資料未備
    assert hld1["_state"] == HL.STATE_OK and hld1["_rows"] == [] and hld3["_state"] == HL.STATE_MISSING
    assert hld0["text"] == HL.TEXT_NO_DEVIATION                      # 字樣照舊（不是只剩它）
    # ~~`[f"{HL.BLOCK_TITLES['HLD-3']}：{HL.ND_TEXT}"]`~~ → D-3 第二輪（獨立稽核 S4，`DEC-2026-10-30-04` F-2「必須同時讓使用者看得到
    # 既有的缺值／未評估原因」；有意識的更正，不是漏刪）：帶上產生處記的資料類（「⬜ 資料未備：配息」，同卡片收起時那一行的既有字型）。
    assert hld0["lines"] == [f"{HL.BLOCK_TITLES['HLD-3']}：{HL.ND_TEXT}：配息"]
    assert hld0["_partial"] is True
    assert hld0["_state"] == HL.STATE_MISSING and hld0["_tone"] == "灰"   # 原判定、色照舊
    formal = HL.find_block(_hld_formal(_h7()), "HLD-0")
    assert formal["lines"] == ["配息與本金卡：◇ 資料未備：配息"]          # 正式模式：既有 ◇ 字樣（~~「配息與本金卡：◇ 資料未備」~~，同上）


def test_F2_附行只帶既有字樣_不計數_不出第二套缺值字樣():
    for line in HL.find_block(_hld_formal(_h7()), "HLD-0")["lines"]:
        assert not re.search(r"\d+\s*(檔|項|筆)", line), line
        assert "◇ 資料未備" in line or "⬜ 不適用" in line, line


def test_F2_H7計數行j維持HLD1未評估檔數_44之八其一a2定義不變():
    """j ＝ `HLD-1` 沒有進入偏離評估的檔數（44 之八其一 (a-2) 第 1 條）。H7 時每一檔都進了偏離評估，j＝0 不是誤報 —— 本批不改 j 的定義；
    缺值原因由燈那一行承擔（上一條）。"""
    model = _hld_formal(_h7())
    assert sections.hld_counts(model) == "持有 3 檔　◆ 需要注意 0 檔　⬜ 無法判定 0 檔"
    assert HL.find_block(model, "HLD-0")["lines"]


def test_F2_三塊皆ok時照舊_不加附行_不加新鍵():
    ds = HF._dataset(window=(HF.WINDOW_START, HF.WINDOW_END), rules=(HF._RULES_NOEXCEED[0],))
    hld0 = HL.find_block(HL.build_page_model(ds, demo_hint=False), "HLD-0")
    assert hld0["text"] == HL.TEXT_NO_DEVIATION and hld0["lines"] == [HL.TEXT_NO_DEVIATION_LINE]
    assert "_partial" not in hld0 and "_omitted_rows" not in hld0


# ───────────────────────── F-18／BL-0411：略過的持倉列 ─────────────────────────


def test_BL0411_HLD_無偏離時不寫無偏離項_改既有資料未備_每一列略過的持倉一行():
    ds = _with(HF._dataset(window=(HF.WINDOW_START, HF.WINDOW_END), rules=(HF._RULES_NOEXCEED[0],)), skipped_holdings=_SKIPPED)
    model = HL.build_page_model(ds, demo_hint=False)
    hld0 = HL.find_block(model, "HLD-0")
    assert hld0["text"] == HL.ND_TEXT and hld0["_state"] == HL.STATE_MISSING
    assert hld0["lines"] == [_SKIPPED_LINE]
    assert HL.TEXT_NO_DEVIATION_LINE not in hld0["lines"]
    assert hld0["_omitted_rows"] == tuple(_SKIPPED)
    formal = _hld_formal(ds)
    assert HL.find_block(formal, "HLD-0")["lines"] == ["◇ 資料未備：PX-TEST-001 第 7 列（ZZ9999） 未列入：缺持倉補充"]
    # 「持有 N 檔」不假裝覆蓋完整集合：計數行不畫、檔數 None
    assert sections.hld_holding_count(formal) is None and sections.hld_counts(formal) is None


def test_BL0411_HLD_有偏離時照舊點名_原因另列_N只是下限():
    ds = _with(HF.scenario("full")["dataset"], skipped_holdings=_SKIPPED)
    hld0 = HL.find_block(HL.build_page_model(ds, demo_hint=False), "HLD-0")
    assert hld0["text"].startswith("有 ") and "超出你設定的門檻" in hld0["text"]
    assert hld0["lines"][-1] == _SKIPPED_LINE


def test_BL0411_HLD_持倉全數被略過_不寫尚未建立任何持倉():
    args = HF.scenario("empty")
    ds = _with(args["dataset"], skipped_holdings=_SKIPPED)
    hld0 = HL.find_block(HL.build_page_model(**{**args, "dataset": ds}), "HLD-0")
    assert hld0["text"] == HL.ND_TEXT and HL.TEXT_NO_HOLDING not in hld0["text"]
    assert _SKIPPED_LINE in hld0["lines"]
    plain_empty = HL.find_block(HL.build_page_model(**args), "HLD-0")
    assert plain_empty["text"] == HL.TEXT_NO_HOLDING                  # 真的空照舊


def test_BL0411_ALO_帶內改無法判定_略過的列各一行在燈下():
    ds = _with(AF.scenario("inband"), skipped_holdings=_SKIPPED)
    alo0 = _alo0(ds)
    assert alo0["text"] == AL.TEXT_UNDECIDABLE_GAP and alo0["_incomplete"] is True
    assert alo0["detail_lines"][0] == _SKIPPED_LINE and alo0["_omitted_rows"] == tuple(_SKIPPED)
    formal = AL.find_block(_alo_formal(ds), "ALO-0")
    assert formal["detail_lines"][0] == "◇ 資料未備：PX-TEST-001 第 7 列（ZZ9999） 未列入：缺持倉補充"


def test_BL0411_ALO_持倉全數被略過_不寫尚未建立任何持倉():
    alo0 = _alo0(_with(AF.scenario("noholding"), skipped_holdings=_SKIPPED))
    assert alo0["text"] == AL.TEXT_UNDECIDABLE_GAP and alo0["text"] != AL.TEXT_NO_HOLDING
    assert _alo0(AF.scenario("noholding"))["text"] == AL.TEXT_NO_HOLDING   # 真的空照舊


def test_BL0411_合併頁主判讀_持有檔數無法判定_配置差距無法判定():
    hld = _hld_formal(_with(HF.scenario("full")["dataset"], skipped_holdings=_SKIPPED))
    alo = _alo_formal(_with(AF.scenario("inband"), skipped_holdings=_SKIPPED))
    n = OV.hero_holding_count(sections.hld_holding_count(hld), holding_error=False)
    alo0, alo2 = AL.find_block(alo, "ALO-0"), AL.find_block(alo, "ALO-2")
    assert n is None
    assert OV.hero_sentence(n, alo0, incomplete=OV.allocation_incomplete(alo0, alo2)) == "持有檔數無法判定；配置差距無法判定。"


def test_BL0411_配置有偏離仍點名時_略過的列讓主判讀不宣稱最大差距():
    """ALO-0 照舊點名（已評估類別的結果照留），但持倉集合不完整 → 一句主判讀不寫「目前最大配置差距在 X」（`ALO-0` 的 `_incomplete`）。"""
    alo = _alo_formal(_with(AF.scenario("full"), skipped_holdings=_SKIPPED))
    alo0, alo2 = AL.find_block(alo, "ALO-0"), AL.find_block(alo, "ALO-2")
    assert alo0["_leaders"] and alo0["text"].endswith(" 個百分點") and not OV.has_unevaluated_category(alo2)
    assert OV.allocation_incomplete(alo0, alo2) is True
    assert OV.hero_sentence(3, alo0, incomplete=OV.allocation_incomplete(alo0, alo2)) == "持有 3 檔基金；配置差距無法判定。"
    clean = _alo_formal(AF.scenario("full"))
    assert OV.allocation_incomplete(AL.find_block(clean, "ALO-0"), AL.find_block(clean, "ALO-2")) is False


def test_BL0411_L2真輸出一路轉交到兩頁的燈_原因字逐字是L2的字():
    """L2 `build_alo_tables`（缺 `_持倉補充` 的列）→ 兩頁資料承載層（只轉交、經遮蔽）→ 燈。"""
    pytest.importorskip("repositories.policy_supplement_repository")
    from repositories import policy_supplement_repository as R
    from services.v2_tables import alo_holdings as A

    prow = {"policy_id": "PX-TEST-001", "fund_code": "ZZ9999", "fund_name": "測試基金甲", "currency": "USD", "tier": "core",
            "invest_twd": 300000, "div_cash_pct": 100.0, "units": 1000.0, "avg_nav": 10.0, "avg_fx": 30.0,
            "_tab": "PX-TEST-001", "_row": 2}
    tabs = {R.TAB_HOLDING_SUPPLEMENT: {"records": [], "bad_rows": [], "blank_rows": 0, "tab_missing": False},
            R.TAB_POLICY_PROFILE: {"records": [], "bad_rows": [], "blank_rows": 0, "tab_missing": False}}
    out = A.build_alo_tables([prow], tabs)
    assert out["holding"] == [] and out["skipped_holdings"][0]["reasons"] == ["缺持倉補充"]
    alo_extra = alo_live.skipped_for_dataset(out, lambda s: s.replace("ZZ9999", "＊＊＊"))
    assert alo_extra["skipped_holdings"][0]["fund_code"] == "＊＊＊"           # 經遮蔽
    assert "skipped_tabs" not in alo_extra
    line = page_health.omitted_row_lines(alo_extra["skipped_holdings"])[0]
    assert line == "⬜ 資料未備：PX-TEST-001 第 2 列（＊＊＊） 未列入：缺持倉補充"
    hld_rows = hld_live._omitted_rows_for_dataset(out["skipped_holdings"], str)
    assert page_health.omitted_row_lines(hld_rows) == ["⬜ 資料未備：PX-TEST-001 第 2 列（ZZ9999） 未列入：缺持倉補充"]


def test_BL0411_HLD資料承載層_有略過的列才帶鍵_沒有時dataset逐鍵不變():
    base = dict(
        holding_error=None, settings=None, settings_error="settings unreadable", key_results=[],
        nav_table={"rows": [], "errors": {}, "withheld": {}, "skipped": {}, "fetched": {}, "skipped_rows": {}, "provenance": {}},
        direct_policy_id="DIRECT", policy_tab_source="保單分頁", direct_sources={"保單分頁"}, empty_without_reason="x",
        nav_unavailable_withheld=frozenset(), dividend_gate_open=False, mask=lambda s: s.replace("ZZ9999", "＊＊＊"),
        dividend_table=None,
    )
    tables = {"holding": [], "policy": [], "direct": [], "skipped_tabs": []}
    without = hld_live.assemble_live_load(holding_tables=tables, **base)["dataset"]
    assert "skipped_holdings" not in without
    withk = hld_live.assemble_live_load(holding_tables={**tables, "skipped_holdings": _SKIPPED}, **base)["dataset"]
    assert withk["skipped_holdings"] == [{"tab": "PX-TEST-001", "row": 7, "fund_code": "＊＊＊", "reasons": ["缺持倉補充"]}]
    assert {k: v for k, v in withk.items() if k != "skipped_holdings"} == without


def test_BL0411_ALO資料承載層_略過的分頁與列才帶鍵():
    assert alo_live.skipped_for_dataset({"skipped_holdings": [], "skipped_tabs": []}, str) == {}
    got = alo_live.skipped_for_dataset({"skipped_holdings": _SKIPPED, "skipped_tabs": [{"tab": "T9", "error": "標頭格式有誤"}]}, str)
    # ~~`"skipped_tabs": [{"tab": "T9"}]`~~ → D-3 第二輪（獨立稽核 B1；有意識的更正，不是漏刪）：原因一併轉交（`ALO-0` 燈下要寫出
    # 是哪一張分頁、為什麼）。
    assert got == {"skipped_holdings": [{"tab": "PX-TEST-001", "row": 7, "fund_code": "ZZ9999", "reasons": ["缺持倉補充"]}],
                   "skipped_tabs": [{"tab": "T9", "error": "標頭格式有誤"}]}
    unread = alo_live.skipped_for_dataset({"skipped_tabs": [{"tab": "T9", "error": None, "unread": True}]}, str)
    assert unread == {"skipped_tabs": [{"tab": "T9"}]}                            # 沒有原因 → 不放 error 鍵（不猜）
    with pytest.raises(ValueError):
        alo_live.skipped_for_dataset({"skipped_holdings": [{**_SKIPPED[0], "reasons": []}]}, str)


def test_BL0411_形狀不對當場炸_不靜默略過():
    with pytest.raises(TypeError):
        page_health.omitted_rows({"skipped_holdings": "缺持倉補充"})
    with pytest.raises(TypeError):
        page_health.omitted_rows({"skipped_holdings": [{"tab": "x"}]})
    assert page_health.omitted_rows({}) == ()


# ───────────────────────── domain block 的原始狀態與 reason 保留、可追溯 ─────────────────────────


def _strip(node, keys=("_omitted_rows", "_skipped_tabs")):
    if isinstance(node, dict):
        return {k: _strip(v, keys) for k, v in node.items() if k not in keys}
    if isinstance(node, list):
        return [_strip(v, keys) for v in node]
    return node


def test_追溯_略過紀錄只加在燈與記號上_ALO2與HLD1至3的每一格不變():
    alo_a = AL.build_page_model(AF.scenario("inband"))
    alo_b = AL.build_page_model(_with(AF.scenario("inband"), skipped_holdings=_SKIPPED, skipped_tabs=[{"tab": "T9"}]))
    # ~~`!= "ALO-0"`（只有燈改）~~ → D-3 第三輪（獨立稽核 should-fix 1，`DEC-2026-10-30-04` F-18；有意識的更正，不是漏刪）：
    # `ALO-4`「未指派 N 檔」與 `ALO-6`「N 檔」、表尾佔比合計同屬覆蓋完整集合的宣稱 —— 件數改既有 `⬜ 資料未備`、表尾接略過的列
    # （只動字與資料類記號）。這兩塊的列、指派、合計數字照舊，見下面逐項；其餘各塊照舊每一格不變。
    for code in [b["code"] for b in alo_a["blocks"] if b["code"] not in ("ALO-0", "ALO-4", "ALO-6")]:
        assert _strip(AL.find_block(alo_b, code)) == AL.find_block(alo_a, code), code
    a4, b4 = AL.find_block(alo_a, "ALO-4"), AL.find_block(alo_b, "ALO-4")
    assert (b4["_assign_rows"], b4["unassigned_lines"], b4["_tone"]) == (a4["_assign_rows"], a4["unassigned_lines"], a4["_tone"])
    a6, b6 = AL.find_block(alo_a, "ALO-6"), AL.find_block(alo_b, "ALO-6")
    assert (b6["_rows"], b6["_tone"]) == (a6["_rows"], a6["_tone"])
    assert b6["footer_lines"][:len(a6["footer_lines"])] == a6["footer_lines"]
    assert AL.find_block(alo_b, "ALO-2")["_omitted_rows"] == tuple(_SKIPPED)       # 原始紀錄可追溯
    hds = HF._dataset(window=(HF.WINDOW_START, HF.WINDOW_END), rules=(HF._RULES_NOEXCEED[0],))
    hld_a = HL.build_page_model(hds, demo_hint=False)
    hld_b = HL.build_page_model(_with(hds, skipped_holdings=_SKIPPED), demo_hint=False)
    # ~~`!= "HLD-0"`（只有燈改）~~ → D-3 第二輪（獨立稽核 S1，`DEC-2026-10-30-04` F-18；有意識的更正，不是漏刪）：零偏離時 `HLD-1` 的
    # 「無偏離項」＋「目前這一組門檻下，沒有任何一檔超出。」同屬覆蓋完整集合的宣稱，改既有 `⬜ 資料未備` 與略過的列（只動字與佔位；
    # `_state`、`_rows` 照舊，見下一條）。其餘各塊照舊每一格不變。
    for code in [b["code"] for b in hld_a["blocks"] if b["code"] not in ("HLD-0", "HLD-1")]:
        assert _strip(HL.find_block(hld_b, code)) == HL.find_block(hld_a, code), code
    assert HL.find_block(hld_b, "HLD-2")["_omitted_rows"] == tuple(_SKIPPED)
    a1, b1 = HL.find_block(hld_a, "HLD-1"), HL.find_block(hld_b, "HLD-1")
    assert (b1["_state"], b1["_rows"]) == (a1["_state"], a1["_rows"]) == (HL.STATE_OK, [])
    assert b1["_omitted_rows"] == tuple(_SKIPPED)


def test_追溯_F13與F2只改燈_其餘各塊與沒改前同一份輸入算出的一樣():
    """F-13／F-2 改的是燈的字或附行；`ALO-2` 的列（含 `_diff`、理由字）與 `HLD-1～3` 的 `_state`、主值照舊算、照舊在。"""
    model = AL.build_page_model(AF._dataset(unbucket="CCCC", tolerance=40))
    tail = AL.find_block(model, "ALO-2")["tail_lines"]
    assert any(line.startswith(AL.UNCLASSIFIED) for line in tail)                  # 沒評估到的理由仍在 ALO-2
    model = HL.build_page_model(_h7(), demo_hint=False)
    assert [HL.find_block(model, c)["_state"] for c in ("HLD-1", "HLD-2", "HLD-3")] == [
        HL.STATE_OK, HL.STATE_OK, HL.STATE_MISSING]


# ───────────────────────── 塊層級的組合（客戶列的情境中，塊層級適用的那幾種）─────────────────────────


@pytest.mark.parametrize("label,ds_fn,expect_text", [
    ("雙方完整正常_配置", lambda: AF.scenario("inband"), AL.TEXT_ALL_IN_BAND),
    ("一側部分評估_配置", lambda: AF._dataset(unbucket="CCCC", tolerance=40), AL.TEXT_UNDECIDABLE_GAP),
    ("一側Missing_配置", _a5c, AL.TEXT_UNDECIDABLE_GAP),
    ("ALO有未設定目標類別", _named_bucket_without_target, AL.TEXT_UNDECIDABLE_GAP),
    ("BL0411_omitted_rows_配置", lambda: _with(AF.scenario("inband"), skipped_holdings=_SKIPPED), AL.TEXT_UNDECIDABLE_GAP),
])
def test_塊層級_配置側各情境的燈字(label, ds_fn, expect_text):
    assert _alo0(ds_fn())["text"] == expect_text, label


def test_塊層級_一側取數失敗_燈照舊取數失敗_不被不完整蓋掉():
    alo0 = _alo0(_with(AF.scenario("holdfail"), skipped_tabs=[{"tab": "T9"}]))
    assert alo0["text"] == AF.FETCH_FAIL_MESSAGE or AF.FETCH_FAIL_MESSAGE in alo0["text"]
    hld0 = HL.find_block(HL.build_page_model(**HF.scenario("holdfail")), "HLD-0")
    assert hld0["_tone"] == "紅" and hld0["_state"] == HL.STATE_ERROR
