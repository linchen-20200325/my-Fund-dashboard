# -*- coding: utf-8 -*-
"""P3 頁級狀態 aggregation 的 logic 層守衛（fast lane；零 streamlit；固定 fixtures、不打網路）。

客戶 2026-10-30 裁示 P3／β（`docs/DECISIONS.md` `DEC-2026-10-30-04`；`docs/v2/74_assets_d3_formula_gate.md` 第 3 節 P3、第 5 節）：
取數失敗 ＞ 無持倉 ＞ ◆ ＞ ◇ ＞ ⬜ ＞ 持股只評估一部分（H7／H6） ＞ 無偏離／帶內；同級時「持股」先、「配置」後。
原則：任何一區異常、資料不足或尚未完整評估時，不得被另一區的正常結果遮蔽成「正常」。

本檔證明：
- 分類只讀 logic 明示的 `_page_class`（改字面或 `_tone` 不改分類）；每個 fixtures 情境的分類都在詞表內且與預期一致；
- 組合矩陣：HLD 7 類 × ALO 6 類的**真實模型**逐格、7 × 7 的**合成模型**窮舉（含每一對 severity 的全排列），頭條與第二行都對；
- Missing／Error／not evaluated 不被正常吃掉；
- aggregation 是純函式：深拷貝前後輸入相等、回傳是新物件，不回寫 domain block；
- 每個狀態都有文字（符號＋狀態字＋字樣，無「僅顏色」、無空字串）；
- 頭條不是 rule result：沒有 Digest／Risk Cap 的依賴。
"""

from __future__ import annotations

import ast
import copy
import itertools
import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from ui_v2 import health, plain, status_class as SC, symbols  # noqa: E402
from ui_v2.alo import fixtures as AF  # noqa: E402
from ui_v2.alo import live as alo_live  # noqa: E402
from ui_v2.alo import logic as AL  # noqa: E402
from ui_v2.asset import page_status as PS  # noqa: E402
from ui_v2.hld import fixtures as HF  # noqa: E402
from ui_v2.hld import logic as HL  # noqa: E402

_SKIPPED = [{"tab": "PX-TEST-001", "row": 7, "policy_id": "PX-TEST-001", "fund_code": "ZZ9999", "reasons": ["缺持倉補充"]}]


# ───────────────────────── 側的建法（同 `ui_v2/asset/page.py::_prepare` 的 ok 形狀；正式管線同 `prepare_live`）─────────────────────────


def _with(ds, **extra):
    out = copy.deepcopy(ds)
    out.update(copy.deepcopy(extra))
    return out


def _hld_model(ds, **kw):
    model = HL.build_page_model(ds, demo_hint=False, **kw)
    model, _raw, _status = plain.plain_model(model, page="hld")
    symbols.apply(model)
    model, failures = health.dedupe_failures(model)
    health.relabel_unconfigured(model, failures)
    return model


def _alo_model(ds):
    model = alo_live.apply_live_notes(AL.build_page_model(ds), wired_keys=(), runtime_source=False, sheet_failed=False)
    model, _raw, _status = plain.plain_model(model, page="alo")
    symbols.apply(model)
    model, failures = health.dedupe_failures(model)
    health.relabel_unconfigured(model, failures)
    return model


def _hld_side(args):
    kw = {k: v for k, v in args.items() if k != "dataset"}
    return {"state": "ok", "model": _hld_model(args["dataset"], **kw)}


def _alo_side(ds):
    return {"state": "ok", "model": _alo_model(ds)}


def _noexceed():
    return HF._dataset(window=(HF.WINDOW_START, HF.WINDOW_END), rules=(HF._RULES_NOEXCEED[0],))


def _h7():
    ds = _noexceed()
    ds["pending_tables"] = frozenset({"dividend"})
    return ds


def _h6():
    ds = _noexceed()
    ds["fund_errors"] = {"nav": {}, "dividend": {"CCCC": "上游逾時（探針）"}}
    return ds


def _a5c():
    targets = ({"bucket": AF.BOND, "weight_ratio": 0.10},) + tuple(AF.TARGETS)
    ds = AF._dataset(basis=AF.BASIS_MV, fx=False, targets=targets, bucket_names=AF.BUCKET_NAMES + (AF.BOND,))
    ds["nav"] = [r for r in ds["nav"] if r["fund_code"] not in ("BBBB", "DDDD")]
    return ds


def _blank_first_target(ds):
    ds = copy.deepcopy(ds)
    for row in ds["user_setting"]:
        if row["setting_key"] == "alo_target_weights":
            row["setting_value"][0]["weight_ratio"] = None
    return ds


# 持股：class -> side（真實 fixtures 經正式管線）
HLD_CLASS_SIDES = {
    SC.ERROR: lambda: _hld_side(HF.scenario("fetchfail")),
    SC.NO_HOLDING: lambda: _hld_side(HF.scenario("empty")),
    SC.ATTENTION: lambda: _hld_side(HF.scenario("full")),
    SC.MISSING: lambda: _hld_side(HF.scenario("tiedstate")),
    SC.UNSET: lambda: _hld_side(HF.scenario("nothr")),
    SC.PARTIAL: lambda: _hld_side({"dataset": _h7()}),
    SC.NORMAL: lambda: _hld_side({"dataset": _noexceed()}),
}
# 配置：class -> side（ALO 沒有「只評估一部分」這一類）
ALO_CLASS_SIDES = {
    SC.ERROR: lambda: _alo_side(AF.scenario("holdfail")),
    SC.NO_HOLDING: lambda: _alo_side(AF.scenario("noholding")),
    SC.ATTENTION: lambda: _alo_side(AF.scenario("full")),
    SC.MISSING: lambda: _alo_side(AF.scenario("nofx")),
    SC.UNSET: lambda: _alo_side(AF.scenario("notarget")),
    SC.NORMAL: lambda: _alo_side(AF.scenario("inband")),
}


# ───────────────────────── 詞表與嚴重度 ─────────────────────────


def test_嚴重度階梯照客戶原話_取數失敗_無持倉_注意_資料未備_未設定_只評估一部分_無偏離():
    assert SC.SEVERITY_ORDER == (SC.ERROR, SC.NO_HOLDING, SC.ATTENTION, SC.MISSING, SC.UNSET, SC.PARTIAL, SC.NORMAL)
    assert [SC.RANK[c] for c in SC.SEVERITY_ORDER] == list(range(7))
    assert SC.NON_NORMAL == set(SC.SEVERITY_ORDER) - {SC.NORMAL}


# ───────────────────────── Q1：分類由 logic 明示，不比對字面或 _tone ─────────────────────────

_HLD_EXPECT = {
    "full": SC.ATTENTION, "srcmiss": SC.ATTENTION, "bizexc": SC.UNSET, "fetchfail": SC.ERROR, "nothr": SC.UNSET,
    "empty": SC.NO_HOLDING, "emptyfail": SC.ERROR, "noexceed": SC.NORMAL, "other_window": SC.NORMAL, "onenav": SC.UNSET,
    "tiedstate": SC.MISSING, "twofail": SC.ERROR, "holdfail": SC.ERROR, "profilefail": SC.ERROR, "holdfail_nothr": SC.ERROR,
    "badrange": SC.UNSET, "full_then_badrange": SC.ATTENTION,
}
_ALO_EXPECT = {
    "full": SC.ATTENTION, "first": SC.NO_HOLDING, "noholding": SC.NO_HOLDING, "notarget": SC.UNSET, "nobasis": SC.UNSET,
    "inband": SC.NORMAL, "notol": SC.UNSET, "mvbasis": SC.ATTENTION, "nofx": SC.MISSING, "unbkt": SC.ATTENTION,
    "nobucket": SC.ATTENTION, "partial": SC.ATTENTION, "holdfail": SC.ERROR, "fxfail": SC.ERROR, "settingfail": SC.ERROR,
    "policyfail": SC.ATTENTION,
}


def test_HLD0_每個fixtures情境都有分類且與預期一致():
    assert set(_HLD_EXPECT) == set(HF.ALL_SCENARIO_NAMES)
    for name, expect in _HLD_EXPECT.items():
        args = HF.scenario(name)
        kw = {k: v for k, v in args.items() if k != "dataset"}
        block = HL.find_block(HL.build_page_model(args["dataset"], demo_hint=False, **kw), "HLD-0")
        assert block["_page_class"] == expect, name


def test_ALO0_每個fixtures情境都有分類且與預期一致():
    assert set(_ALO_EXPECT) == set(AF.ALL_SCENARIO_NAMES)
    for name, expect in _ALO_EXPECT.items():
        assert AL.find_block(AL.build_page_model(AF.scenario(name)), "ALO-0")["_page_class"] == expect, name


def test_A6m_A5c_F18_F19_歸資料未備_不是無偏離():
    cases = {
        "A6m(1)目標比重留空": _blank_first_target(AF.scenario("inband")),
        "A6m(2)無目標類別缺值": _mv_unbucketed_without_nav(),
        "A6m(3)保單分頁被略過": _with(AF.scenario("inband"), skipped_tabs=[{"tab": "PX-TEST-009"}]),
        "A5c": _a5c(),
        "F18 skipped_holdings": _with(AF.scenario("inband"), skipped_holdings=_SKIPPED),
        "F18 全數被略過": _with(AF.scenario("noholding"), skipped_holdings=_SKIPPED),
        "F19 未分類 成本": AF._dataset(unbucket="CCCC", tolerance=40),
        "F19 未分類 市值": AF._dataset(unbucket="CCCC", tolerance=40, basis=AF.BASIS_MV),
    }
    for name, ds in cases.items():
        block = AL.find_block(AL.build_page_model(ds), "ALO-0")
        assert block["_page_class"] == SC.MISSING, name
        assert block["text"] == AL.TEXT_UNDECIDABLE_GAP, name


def _mv_unbucketed_without_nav():
    ds = AF._dataset(basis=AF.BASIS_MV, unbucket=AF.UNBUCKETED_FUND, tolerance=40)
    ds["nav"] = [r for r in ds["nav"] if r["fund_code"] != AF.UNBUCKETED_FUND]
    return ds


def test_HLD_F18_略過的持倉列_無偏離與無持倉都改歸資料未備_有偏離仍是注意():
    for ds, expect in ((_with(_noexceed(), skipped_holdings=_SKIPPED), SC.MISSING),
                       (_with(HF.scenario("empty")["dataset"], skipped_holdings=_SKIPPED), SC.MISSING),
                       (_with(HF.scenario("full")["dataset"], skipped_holdings=_SKIPPED), SC.ATTENTION)):
        assert HL.find_block(HL.build_page_model(ds, demo_hint=False), "HLD-0")["_page_class"] == expect


def test_HLD_H7與H6_部分評估歸只評估一部分_不是無偏離():
    for ds in (_h7(), _h6()):
        block = HL.find_block(HL.build_page_model(ds, demo_hint=False), "HLD-0")
        assert block["_partial"] is True and block["_page_class"] == SC.PARTIAL
    assert HL.find_block(HL.build_page_model(_noexceed(), demo_hint=False), "HLD-0")["_page_class"] == SC.NORMAL


def test_分類不讀字面也不讀tone_改字面與tone後分類不變():
    for cls, make in HLD_CLASS_SIDES.items():
        side = make()
        block = HL.find_block(side["model"], "HLD-0")
        block["text"], block["_tone"], block["glyph"], block["state_word"] = "亂寫", "紅", "?", "亂寫"
        assert PS.classify_side(PS.AREA_HLD, side)["class"] == cls
    for cls, make in ALO_CLASS_SIDES.items():
        side = make()
        block = AL.find_block(side["model"], "ALO-0")
        block["text"], block["_tone"], block["glyph"], block["state_word"] = "各類別皆在容許帶內", "灰", "?", "亂寫"
        assert PS.classify_side(PS.AREA_ALO, side)["class"] == cls


def test_沒有分類鍵或分類不在詞表_直接炸_不猜():
    side = HLD_CLASS_SIDES[SC.NORMAL]()
    del HL.find_block(side["model"], "HLD-0")["_page_class"]
    with pytest.raises(KeyError):
        PS.classify_side(PS.AREA_HLD, side)
    side = HLD_CLASS_SIDES[SC.NORMAL]()
    HL.find_block(side["model"], "HLD-0")["_page_class"] = "正常"
    with pytest.raises(ValueError):
        PS.classify_side(PS.AREA_HLD, side)


# ───────────────────────── 組合矩陣（真實模型）─────────────────────────


def _expected_headline(h_cls, a_cls):
    """β：嚴重度小者勝；同級持股先。"""
    return PS.AREA_HLD if SC.RANK[h_cls] <= SC.RANK[a_cls] else PS.AREA_ALO


def _all_real_pairs():
    for h_cls, a_cls in itertools.product(HLD_CLASS_SIDES, ALO_CLASS_SIDES):
        yield h_cls, a_cls


@pytest.mark.parametrize("h_cls,a_cls", list(_all_real_pairs()), ids=lambda v: str(v))
def test_矩陣_真實模型_頭條依beta_另一區固定照印為第二行(h_cls, a_cls):
    hld, alo = HLD_CLASS_SIDES[h_cls](), ALO_CLASS_SIDES[a_cls]()
    out = PS.aggregate(hld, alo)
    rows = out["rows"]
    if h_cls == a_cls == SC.NORMAL:                                     # Q5
        assert out["kind"] == PS.KIND_MERGED_NORMAL and len(rows) == 1
        return
    if h_cls == a_cls == SC.NO_HOLDING and rows[0]["area"] == PS.AREA_BOTH:   # Q6（跑完管線後同字才合成）
        assert out["kind"] == PS.KIND_MERGED_NO_HOLDING and len(rows) == 1
        return
    assert out["kind"] == PS.KIND_TWO_ROWS and len(rows) == 2
    assert rows[0]["area"] == _expected_headline(h_cls, a_cls)
    assert {r["area"] for r in rows} == {PS.AREA_HLD, PS.AREA_ALO}      # 沒有任何一區的狀態從畫面上消失
    by_area = {r["area"]: r for r in rows}
    assert by_area[PS.AREA_HLD]["class"] == h_cls and by_area[PS.AREA_ALO]["class"] == a_cls
    assert out["headline_class"] == rows[0]["class"] == min(h_cls, a_cls, key=lambda c: SC.RANK[c])
    # Q3：容器外觀＝頭條那一行自己的
    assert out["container"] == {"glyph": rows[0]["glyph"], "state_word": rows[0]["state_word"], "tone": rows[0]["tone"]}
    # 第二行含它自己的字樣與附行（逐字等於該區 block 的字，不改寫）
    h0, a0 = HL.find_block(hld["model"], "HLD-0"), AL.find_block(alo["model"], "ALO-0")
    assert by_area[PS.AREA_HLD]["text"] == h0["text"] and by_area[PS.AREA_HLD]["lines"] == tuple(h0["lines"])
    assert by_area[PS.AREA_ALO]["text"] == a0["text"]
    assert out["is_rule_result"] is False


def test_矩陣_七類乘六類共四十二格_恰有一格Q5合成_其餘為兩行或Q6():
    kinds = {}
    for h_cls, a_cls in _all_real_pairs():
        kinds[(h_cls, a_cls)] = PS.aggregate(HLD_CLASS_SIDES[h_cls](), ALO_CLASS_SIDES[a_cls]())["kind"]
    assert len(kinds) == 42
    assert [k for k, v in kinds.items() if v == PS.KIND_MERGED_NORMAL] == [(SC.NORMAL, SC.NORMAL)]
    assert [k for k, v in kinds.items() if v == PS.KIND_MERGED_NO_HOLDING] == [(SC.NO_HOLDING, SC.NO_HOLDING)]


# ───────────────────────── 組合矩陣（合成模型；7 × 7 窮舉，含每一對 severity 的全排列）─────────────────────────


def _synthetic_side(area, cls):
    code = "HLD-0" if area == PS.AREA_HLD else "ALO-0"
    line = f"{area}-{cls}-附行"
    block = {"code": code, "_page_class": cls, "glyph": "◆" if cls == SC.ATTENTION else "⬜", "state_word": f"狀態：{cls}",
             "text": f"{area}-{cls}", "_tone": "灰", "lines": [line], "detail_lines": [line, "固定說明句"], "buttons": []}
    if area == PS.AREA_ALO:
        block["_attached_n"] = 1      # ALO-0 的附行＝ detail_lines 最前面 `_attached_n` 行
    return {"state": "ok", "model": {"blocks": [block]}}


def test_矩陣_合成模型_七乘七共四十九格_頭條與第二行():
    count = 0
    for h_cls, a_cls in itertools.product(SC.SEVERITY_ORDER, repeat=2):
        count += 1
        out = PS.aggregate(_synthetic_side(PS.AREA_HLD, h_cls), _synthetic_side(PS.AREA_ALO, a_cls))
        if h_cls == a_cls == SC.NORMAL:
            assert out["kind"] == PS.KIND_MERGED_NORMAL
            assert [r["text"] for r in out["rows"]] == [f"{PS.AREA_HLD}-{SC.NORMAL}{PS.NORMAL_JOINER}{PS.AREA_ALO}-{SC.NORMAL}"]
            continue
        assert out["kind"] == PS.KIND_TWO_ROWS and len(out["rows"]) == 2
        head, second = out["rows"]
        # 嚴重度小者在前；同級持股先
        assert (SC.RANK[head["class"]], PS._AREA_ORDER[head["area"]]) <= (SC.RANK[second["class"]], PS._AREA_ORDER[second["area"]])
        assert head["area"] == _expected_headline(h_cls, a_cls)
        assert {head["area"], second["area"]} == {PS.AREA_HLD, PS.AREA_ALO}
        assert {head["class"], second["class"]} == {h_cls, a_cls}
        assert second["lines"] == (f"{second['area']}-{second['class']}-附行",)   # 第二行含它自己的附行
    assert count == 49


def test_全排列_任一方非正常時頭條一定非正常_正常絕不當頭條():
    for h_cls, a_cls in itertools.product(SC.SEVERITY_ORDER, repeat=2):
        out = PS.aggregate(_synthetic_side(PS.AREA_HLD, h_cls), _synthetic_side(PS.AREA_ALO, a_cls))
        if h_cls != SC.NORMAL or a_cls != SC.NORMAL:
            assert out["headline_class"] in SC.NON_NORMAL
            assert out["headline_class"] != SC.NORMAL
            # 該非正常那一區一定在畫面上（頭條或第二行）
            present = {(r["area"], r["class"]) for r in out["rows"]}
            for area, cls in ((PS.AREA_HLD, h_cls), (PS.AREA_ALO, a_cls)):
                if cls != SC.NORMAL:
                    assert (area, cls) in present


def test_同級時持股先_配置後():
    for cls in SC.SEVERITY_ORDER:
        if cls in (SC.NORMAL,):
            continue
        out = PS.aggregate(_synthetic_side(PS.AREA_HLD, cls), _synthetic_side(PS.AREA_ALO, cls))
        assert [r["area"] for r in out["rows"]] == [PS.AREA_HLD, PS.AREA_ALO], cls


# ───────────────────────── 各情境：Missing／Error／not evaluated 不被正常吃掉 ─────────────────────────


def test_1_HLD正常加ALO正常_合成一行_照印兩句原字_不寫正常():
    hld, alo = HLD_CLASS_SIDES[SC.NORMAL](), ALO_CLASS_SIDES[SC.NORMAL]()
    out = PS.aggregate(hld, alo)
    row = out["rows"][0]
    h0, a0 = HL.find_block(hld["model"], "HLD-0"), AL.find_block(alo["model"], "ALO-0")
    assert out["kind"] == PS.KIND_MERGED_NORMAL and len(out["rows"]) == 1
    assert row["text"] == f"{h0['text']}；{a0['text']}" == "無偏離項；各類別皆在容許帶內"
    assert row["lines"] == tuple(h0["lines"])                       # 附行只留 HLD-0 那一句
    assert "正常" not in PS.row_label(row)
    assert row["area"] is None


def test_2_HLD正常加ALO異常_異常是頭條_正常那一區在第二行不被吃掉():
    for bad in (SC.ATTENTION, SC.MISSING, SC.UNSET, SC.NO_HOLDING, SC.ERROR):
        out = PS.aggregate(HLD_CLASS_SIDES[SC.NORMAL](), ALO_CLASS_SIDES[bad]())
        assert out["rows"][0]["area"] == PS.AREA_ALO and out["rows"][0]["class"] == bad
        assert out["rows"][1]["area"] == PS.AREA_HLD and out["rows"][1]["class"] == SC.NORMAL


def test_3_HLD異常加ALO正常_異常是頭條():
    for bad in (SC.ATTENTION, SC.MISSING, SC.UNSET, SC.NO_HOLDING, SC.ERROR, SC.PARTIAL):
        out = PS.aggregate(HLD_CLASS_SIDES[bad](), ALO_CLASS_SIDES[SC.NORMAL]())
        assert out["rows"][0]["area"] == PS.AREA_HLD and out["rows"][0]["class"] == bad
        assert out["rows"][1]["area"] == PS.AREA_ALO and out["rows"][1]["class"] == SC.NORMAL


def test_4_一側Missing_不被另一側正常蓋掉_也不蓋過更嚴重的Error與無持倉與注意():
    out = PS.aggregate(HLD_CLASS_SIDES[SC.MISSING](), ALO_CLASS_SIDES[SC.NORMAL]())      # 持股缺值、配置正常
    assert out["headline_class"] == SC.MISSING and out["kind"] == PS.KIND_TWO_ROWS and out["rows"][1]["class"] == SC.NORMAL
    out = PS.aggregate(HLD_CLASS_SIDES[SC.NORMAL](), ALO_CLASS_SIDES[SC.MISSING]())      # 持股正常、配置缺值
    assert out["headline_class"] == SC.MISSING and out["kind"] == PS.KIND_TWO_ROWS and out["rows"][1]["class"] == SC.NORMAL
    for stronger in (SC.ERROR, SC.NO_HOLDING, SC.ATTENTION):
        out = PS.aggregate(HLD_CLASS_SIDES[SC.MISSING](), ALO_CLASS_SIDES[stronger]())
        assert out["headline_class"] == stronger and out["rows"][1]["class"] == SC.MISSING   # Missing 仍在第二行


def test_5_一側取數失敗_最嚴重_另一側照畫():
    for other_cls, make in ALO_CLASS_SIDES.items():
        out = PS.aggregate(HLD_CLASS_SIDES[SC.ERROR](), make())
        assert out["rows"][0]["area"] == PS.AREA_HLD and out["headline_class"] == SC.ERROR
    for other_cls, make in HLD_CLASS_SIDES.items():
        out = PS.aggregate(make(), ALO_CLASS_SIDES[SC.ERROR]())
        assert out["headline_class"] == SC.ERROR
        assert any(r["area"] == PS.AREA_HLD and r["class"] == other_cls for r in out["rows"]) or other_cls == SC.ERROR


def test_5b_PE_一區拋例外_另一區照畫_拋例外的區歸取數失敗():
    pe = {"state": "error", "line": "⛔ 持倉 取數失敗：暫時無法判定"}
    out = PS.aggregate(pe, ALO_CLASS_SIDES[SC.NORMAL]())
    assert out["headline_class"] == SC.ERROR and out["rows"][0]["area"] == PS.AREA_HLD
    assert out["rows"][1]["class"] == SC.NORMAL and out["rows"][1]["text"] == "各類別皆在容許帶內"
    assert out["rows"][0]["glyph"] == "⛔" and out["rows"][0]["state_word"] == "狀態：取數失敗"
    out = PS.aggregate(HLD_CLASS_SIDES[SC.NORMAL](), pe)
    assert out["rows"][0]["area"] == PS.AREA_ALO and out["rows"][0]["class"] == SC.ERROR
    assert out["rows"][1]["area"] == PS.AREA_HLD and out["rows"][1]["class"] == SC.NORMAL
    both = PS.aggregate(pe, copy.deepcopy(pe))
    assert both["kind"] == PS.KIND_TWO_ROWS and [r["area"] for r in both["rows"]] == [PS.AREA_HLD, PS.AREA_ALO]


def test_5c_沒有ActiveSheet的一側_與另一側取數失敗混合時_取數失敗是頭條():
    no_active = {"state": "no_active", "line": "⬜ 尚未選定持倉資料來源"}
    pe = {"state": "error", "line": "⛔ 持倉 取數失敗：暫時無法判定"}
    out = PS.aggregate(no_active, pe)
    assert out["headline_class"] == SC.ERROR and out["rows"][1]["class"] == SC.UNSET
    assert out["rows"][1]["text"] == "尚未選定持倉資料來源" and PS.row_label(out["rows"][1])


def test_6_一側部分評估_不是無偏離_不與正常合成():
    hld = HLD_CLASS_SIDES[SC.PARTIAL]()
    h0 = HL.find_block(hld["model"], "HLD-0")
    out = PS.aggregate(hld, ALO_CLASS_SIDES[SC.NORMAL]())
    assert out["kind"] == PS.KIND_TWO_ROWS and out["headline_class"] == SC.PARTIAL
    head = out["rows"][0]
    assert head["lines"] == tuple(h0["lines"]) and head["lines"], "必須同時看得到既有的缺值／未評估原因"
    assert "◇" in " ".join(head["lines"])
    assert out["rows"][1]["class"] == SC.NORMAL                      # 正常那一區仍照印在第二行，但不是頭條、也不合成
    # H6（逐檔配息取數失敗、塊照舊 ok）同樣歸只評估一部分
    out6 = PS.aggregate(_hld_side({"dataset": _h6()}), ALO_CLASS_SIDES[SC.NORMAL]())
    assert out6["headline_class"] == SC.PARTIAL and "⛔" in " ".join(out6["rows"][0]["lines"])
    # 只評估一部分 ＞ 只輸給更嚴重的
    assert PS.aggregate(hld, ALO_CLASS_SIDES[SC.UNSET]())["headline_class"] == SC.UNSET
    assert PS.aggregate(hld, ALO_CLASS_SIDES[SC.MISSING]())["headline_class"] == SC.MISSING


def test_7_ALO有市值但無目標_F19_歸資料未備_不與正常合成():
    for ds in (AF._dataset(unbucket="CCCC", tolerance=40), AF._dataset(unbucket="CCCC", tolerance=40, basis=AF.BASIS_MV)):
        alo = _alo_side(ds)
        a0 = AL.find_block(alo["model"], "ALO-0")
        assert a0["text"] == AL.TEXT_UNDECIDABLE_GAP and a0["_page_class"] == SC.MISSING
        out = PS.aggregate(HLD_CLASS_SIDES[SC.NORMAL](), alo)
        assert out["kind"] == PS.KIND_TWO_ROWS and out["headline_class"] == SC.MISSING
        assert out["rows"][0]["text"] == AL.TEXT_UNDECIDABLE_GAP
        assert "各類別皆在容許帶內" not in "\n".join(PS.row_label(r) for r in out["rows"])   # 不得與 C2 的「無法判定」互相矛盾


def test_8_略過的持倉列與分頁_兩側皆不假裝覆蓋完整集合_附行照印():
    # 配置側：ALO-0 的附行（略過的列）隨第二行／頭條照印
    alo = _alo_side(_with(AF.scenario("inband"), skipped_holdings=_SKIPPED))
    a0 = AL.find_block(alo["model"], "ALO-0")
    assert a0["_page_class"] == SC.MISSING and a0["_omitted_rows"]
    out = PS.aggregate(HLD_CLASS_SIDES[SC.NORMAL](), alo)
    assert out["headline_class"] == SC.MISSING and out["rows"][0]["area"] == PS.AREA_ALO
    assert out["rows"][0]["lines"] == tuple(a0["detail_lines"][:a0["_attached_n"]]) and len(out["rows"][0]["lines"]) == 1
    assert "未列入" in out["rows"][0]["lines"][0]
    # 配置側：略過的保單分頁
    tabs = _alo_side(_with(AF.scenario("inband"), skipped_tabs=[{"tab": "PX-TEST-009"}]))
    out_t = PS.aggregate(HLD_CLASS_SIDES[SC.NORMAL](), tabs)
    assert out_t["headline_class"] == SC.MISSING and out_t["rows"][0]["lines"], "略過的分頁那一行要照印"
    # 持股側：HLD-0 無偏離但有略過的列 → 資料未備，附行是略過的列
    hld = _hld_side({"dataset": _with(_noexceed(), skipped_holdings=_SKIPPED)})
    h0 = HL.find_block(hld["model"], "HLD-0")
    assert h0["_page_class"] == SC.MISSING and h0["_omitted_rows"]
    out_h = PS.aggregate(hld, ALO_CLASS_SIDES[SC.NORMAL]())
    assert out_h["headline_class"] == SC.MISSING and out_h["rows"][0]["area"] == PS.AREA_HLD
    assert out_h["rows"][0]["lines"] == tuple(h0["lines"]) and "未列入" in out_h["rows"][0]["lines"][0]
    # 兩側都被略過 → 兩行都是資料未備，持股先
    out_both = PS.aggregate(hld, alo)
    assert [r["class"] for r in out_both["rows"]] == [SC.MISSING, SC.MISSING]
    assert [r["area"] for r in out_both["rows"]] == [PS.AREA_HLD, PS.AREA_ALO]


def test_9_無持倉_兩區同為尚未建立任何持倉_合成一行_鈕只出一次():
    hld, alo = HLD_CLASS_SIDES[SC.NO_HOLDING](), ALO_CLASS_SIDES[SC.NO_HOLDING]()
    h0, a0 = HL.find_block(hld["model"], "HLD-0"), AL.find_block(alo["model"], "ALO-0")
    assert h0["text"] == a0["text"] == "尚未建立任何持倉"                 # 「同字」以跑完管線後的字串判定
    out = PS.aggregate(hld, alo)
    assert out["kind"] == PS.KIND_MERGED_NO_HOLDING and len(out["rows"]) == 1
    row = out["rows"][0]
    assert row["area"] == PS.AREA_BOTH and row["text"] == "尚未建立任何持倉" and row["class"] == SC.NO_HOLDING
    assert row["lines"] == tuple(h0["lines"])                          # HLD0_NO_RULES_ASIDE 之類的附行照留
    assert sum(1 for r in out["rows"] if r["has_buttons"]) == 1        # 前往 Sheets 鈕只出一次
    assert row["has_buttons"] is bool(h0["buttons"])
    # 一區無持倉、另一區不是 → 不合成
    other = PS.aggregate(hld, ALO_CLASS_SIDES[SC.NORMAL]())
    assert other["kind"] == PS.KIND_TWO_ROWS and other["headline_class"] == SC.NO_HOLDING
    # 字不同 → 不合成（不以類別硬湊）
    alo2 = copy.deepcopy(alo)
    AL.find_block(alo2["model"], "ALO-0")["text"] = "別的字"
    assert PS.aggregate(hld, alo2)["kind"] == PS.KIND_TWO_ROWS


def test_10_特定兩枚異常_precedence實例():
    # ◆ ＞ ◇：HLD 缺值、ALO 有偏離 → ALO 的 ◆ 是頭條
    out = PS.aggregate(HLD_CLASS_SIDES[SC.MISSING](), ALO_CLASS_SIDES[SC.ATTENTION]())
    assert (out["rows"][0]["area"], out["rows"][0]["class"]) == (PS.AREA_ALO, SC.ATTENTION)
    assert (out["rows"][1]["area"], out["rows"][1]["class"]) == (PS.AREA_HLD, SC.MISSING)
    # 無持倉 ＞ ◆
    out = PS.aggregate(HLD_CLASS_SIDES[SC.ATTENTION](), ALO_CLASS_SIDES[SC.NO_HOLDING]())
    assert out["headline_class"] == SC.NO_HOLDING
    # ◆ ＞ ⬜
    out = PS.aggregate(HLD_CLASS_SIDES[SC.UNSET](), ALO_CLASS_SIDES[SC.ATTENTION]())
    assert out["headline_class"] == SC.ATTENTION and out["rows"][0]["area"] == PS.AREA_ALO
    # S3：寫死的頭條斷言（不用 SC.RANK 當預期）。◇ ＞ ⬜
    out = PS.aggregate(HLD_CLASS_SIDES[SC.UNSET](), ALO_CLASS_SIDES[SC.MISSING]())
    assert (out["rows"][0]["area"], out["rows"][0]["class"]) == ("配置", "資料未備")
    assert (out["rows"][1]["area"], out["rows"][1]["class"]) == ("持股", "未設定或不適用")
    out = PS.aggregate(HLD_CLASS_SIDES[SC.MISSING](), ALO_CLASS_SIDES[SC.UNSET]())
    assert (out["rows"][0]["area"], out["rows"][0]["class"]) == ("持股", "資料未備")
    # S3：寫死的頭條斷言。⬜ ＞ 只評估一部分
    out = PS.aggregate(HLD_CLASS_SIDES[SC.PARTIAL](), ALO_CLASS_SIDES[SC.UNSET]())
    assert (out["rows"][0]["area"], out["rows"][0]["class"]) == ("配置", "未設定或不適用")
    assert (out["rows"][1]["area"], out["rows"][1]["class"]) == ("持股", "只評估一部分")


def test_S1_未設定與不適用分支_有略過的列或分頁時歸資料未備_字樣狀態色一字不動():
    # 持股：nothr／bizexc／onenav ＋ 略過的持倉列
    for name in ("nothr", "bizexc", "onenav"):
        base = HF.scenario(name)["dataset"]
        plain_block = HL.find_block(HL.build_page_model(base, demo_hint=False), "HLD-0")
        assert plain_block["_page_class"] == SC.UNSET, name
        block = HL.find_block(HL.build_page_model(_with(base, skipped_holdings=_SKIPPED), demo_hint=False), "HLD-0")
        assert block["_page_class"] == SC.MISSING, name
        for key in ("text", "_state", "_tone", "glyph", "state_word"):
            assert block[key] == plain_block[key], (name, key)
    # 配置：notarget／nobasis／notol ＋ 略過的持倉列、略過的分頁、兩者
    for name in ("notarget", "nobasis", "notol"):
        base = AF.scenario(name)
        plain_block = AL.find_block(AL.build_page_model(base), "ALO-0")
        assert plain_block["_page_class"] == SC.UNSET, name
        for extra in ({"skipped_holdings": _SKIPPED}, {"skipped_tabs": [{"tab": "PX-TEST-009"}]},
                      {"skipped_holdings": _SKIPPED, "skipped_tabs": [{"tab": "PX-TEST-009"}]}):
            block = AL.find_block(AL.build_page_model(_with(base, **extra)), "ALO-0")
            assert block["_page_class"] == SC.MISSING, (name, sorted(extra))
            for key in ("text", "_tone", "glyph", "state_word"):
                assert block[key] == plain_block[key], (name, key)
            assert "_incomplete" not in block or block.get("_incomplete") == plain_block.get("_incomplete")
    # 沒有略過時維持未設定
    assert PS.classify_side(PS.AREA_ALO, ALO_CLASS_SIDES[SC.UNSET]())["class"] == SC.UNSET


def test_S1_頁級_略過列加未設定_頭條是資料未備_排在未設定前():
    hld = _hld_side({"dataset": _with(HF.scenario("nothr")["dataset"], skipped_holdings=_SKIPPED)})
    out = PS.aggregate(hld, ALO_CLASS_SIDES[SC.UNSET]())
    assert out["rows"][0]["area"] == PS.AREA_HLD and out["headline_class"] == SC.MISSING
    assert out["rows"][1]["class"] == SC.UNSET


# ───────────────────────── 純函式：不回寫 domain block ─────────────────────────


def test_aggregation不回寫domain_block_深拷貝前後相等_回傳是新物件():
    for h_cls, a_cls in _all_real_pairs():
        hld, alo = HLD_CLASS_SIDES[h_cls](), ALO_CLASS_SIDES[a_cls]()
        before_h, before_a = copy.deepcopy(hld), copy.deepcopy(alo)
        out = PS.aggregate(hld, alo)
        assert hld == before_h and alo == before_a, (h_cls, a_cls)
        # 改回傳值不影響輸入（沒有共用可變物件）
        out["rows"][0]["lines"] = ("被改了",)
        out["rows"][0]["text"] = "被改了"
        out["container"]["glyph"] = "X"
        out["rows"].clear()
        assert hld == before_h and alo == before_a
        assert HL.find_block(hld["model"], "HLD-0")["text"] == HL.find_block(before_h["model"], "HLD-0")["text"]
    pe = {"state": "error", "line": "x"}
    before = copy.deepcopy(pe)
    PS.aggregate(pe, ALO_CLASS_SIDES[SC.NORMAL]())
    assert pe == before


def test_原rule_result完整保留_HLD0與ALO0的狀態字樣與reason不因aggregation改變():
    for h_cls, a_cls in _all_real_pairs():
        hld, alo = HLD_CLASS_SIDES[h_cls](), ALO_CLASS_SIDES[a_cls]()
        keys = ("text", "glyph", "state_word", "_tone", "_state", "lines", "detail_lines", "buttons")
        h0, a0 = HL.find_block(hld["model"], "HLD-0"), AL.find_block(alo["model"], "ALO-0")
        snap = ({k: copy.deepcopy(h0.get(k)) for k in keys}, {k: copy.deepcopy(a0.get(k)) for k in keys})
        PS.aggregate(hld, alo)
        assert ({k: h0.get(k) for k in keys}, {k: a0.get(k) for k in keys}) == snap


# ───────────────────────── 每個狀態都有文字（無「僅顏色」、無空字串）─────────────────────────


def test_每個狀態的每一行都有符號_狀態字_與可讀的畫面字():
    for h_cls, a_cls in _all_real_pairs():
        out = PS.aggregate(HLD_CLASS_SIDES[h_cls](), ALO_CLASS_SIDES[a_cls]())
        for row in out["rows"]:
            assert row["glyph"].strip() and row["state_word"].strip(), (h_cls, a_cls, row)
            label = PS.row_label(row)
            assert label.strip() and row["state_word"] in label and row["glyph"] in label
        assert out["container"]["glyph"].strip() and out["container"]["state_word"].strip()
    for side in ({"state": "error", "line": "x"}, {"state": "no_active", "line": "⬜ 尚未選定持倉資料來源"}):
        row = PS.classify_side(PS.AREA_HLD, side)
        assert row["glyph"].strip() and row["state_word"].strip() and PS.row_label(row).strip()


def test_合成模型七類各自有文字():
    for cls in SC.SEVERITY_ORDER:
        for area in (PS.AREA_HLD, PS.AREA_ALO):
            label = PS.row_label(PS.classify_side(area, _synthetic_side(area, cls)))
            assert label.strip() and cls in label


# ───────────────────────── 邊界：不是 rule result、不進 Digest、不是 Risk Cap ─────────────────────────


def test_頭條不是rule_result_不依賴Digest或RiskCap():
    out = PS.aggregate(HLD_CLASS_SIDES[SC.NORMAL](), ALO_CLASS_SIDES[SC.NORMAL]())
    assert out["is_rule_result"] is False
    src = pathlib.Path(PS.__file__).read_text(encoding="utf-8")
    imported = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ImportFrom):
            imported |= {(node.module or "", alias.name) for alias in node.names}
        elif isinstance(node, ast.Import):
            imported |= {(alias.name, "") for alias in node.names}
    flat = {name for _mod, name in imported} | {mod for mod, _name in imported}
    assert not any("digest" in str(x).lower() or "risk" in str(x).lower() for x in flat), flat
    assert not any("streamlit" in str(x).lower() for x in flat), flat      # 純函式，零 streamlit import
