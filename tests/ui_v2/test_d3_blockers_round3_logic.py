# -*- coding: utf-8 -*-
"""D-3 阻擋項修正第三輪（獨立稽核 B-NEW-1、should-fix 1、should-fix 3、`_strip_dev_lines` 附註；客戶 2026-10-30 裁示
`docs/DECISIONS.md` `DEC-2026-10-30-04` F-18）的 logic 層守衛（fast lane；不需要 streamlit）。

客戶原話（`docs/evidence/decisions/2026-10-30_d3_oauth_gate_rulings.md`）：
- F-18／BL-0411：「如果部分列目前被略過但 UI 沒揭露：頁燈、持有 N 檔、配置／持股整體判定都不能假裝覆蓋完整集合。
  必須先讓 omitted rows／未納入集合的事實可被辨識。」

- **B-NEW-1**：有 DIRECT 列、保單分頁上的持倉列又全數被略過時，`ui_v2/hld/live.py::_apply_direct` 不再 raise（舊寫法要求
  「尚未建立任何持倉，沒有可以展開的檔。」那一行還在 —— 它已被換成略過的列 → 整頁被打成「⛔ 取數失敗」，略過的列也被蓋掉）。
  兩種揭露都留著：DIRECT 那一行黃字（N 筆）＋ 略過的列。HLD-5 摘要＝「⬜ 資料未備：持倉 · DIRECT N 筆未列入」（兩段都是既有字樣）。
  原本的不變式照舊守沒有略過的列那一種情形。
- **should-fix 1**：`ALO-6`「N 檔」與「總體佔比合計」、`ALO-4`「未指派 N 檔」在有略過的列時不讀成完整集合。
- **should-fix 3**：持倉列全數被略過時，展開區摘要保留資料類（「⬜ 資料未備：持倉」，正式模式「◇ 資料未備：持倉」）。
- **附註（`_strip_dev_lines`）**：F-2 那一行把上游原文接在「<卡名>：」後面；原文碰巧含殘留檢查那一小段時不得整頁 raise。
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

from ui_v2 import page_health  # noqa: E402
from ui_v2.alo import fixtures as AF  # noqa: E402
from ui_v2.alo import logic as AL  # noqa: E402
from ui_v2.asset import overview as OV  # noqa: E402
from ui_v2.hld import fixtures as HF  # noqa: E402
from ui_v2.hld import live as hld_live  # noqa: E402
from ui_v2.hld import logic as HL  # noqa: E402

import test_d3_blockers_logic as R1  # noqa: E402
import test_d3_blockers_round2_logic as R2  # noqa: E402
import test_hld_live_assemble as TH  # noqa: E402

_SKIPPED = R1._SKIPPED
_SKIPPED_LINE = R1._SKIPPED_LINE
_SKIPPED_FORMAL = R2._SKIPPED_FORMAL
_HOLDING = page_health.DATA_CLASSES["holding"]
_OMITTED_SUMMARY = f"{HL.ND_TEXT}：{_HOLDING}"


# ───────────────────────── B-NEW-1：DIRECT ＋ 持倉列全數被略過 ─────────────────────────


def _live_model(*, holdings: bool, skipped=True, direct=True):
    tables = TH._l2_holding_tables(direct=TH._l2_direct() if direct else ())
    if not holdings:
        tables["holding"] = []
    if skipped:
        tables["skipped_holdings"] = copy.deepcopy(_SKIPPED)
    kw = TH._kwargs(holding_tables=tables, key_results=TH._key_results(tables["holding"]))
    if not holdings:
        kw["nav_table"] = TH._empty_nav_table()
    loaded = hld_live.assemble_live_load(**kw)
    loaded["live_args"]["today"] = TH._TODAY
    return hld_live.build_live_model(loaded["dataset"], **loaded["live_args"])


def _direct_n():
    return sum(1 for r in TH._l2_direct() if r["source"] == TH._POLICY_TAB)


def test_BNEW1_DIRECT加持倉全數略過_不raise_兩種揭露都在():
    model = _live_model(holdings=False)
    n = _direct_n()
    hld5 = HL.find_block(model, "HLD-5")
    assert hld5["summary_text"] == _OMITTED_SUMMARY + hld_live.DIRECT_SUMMARY_SUFFIX.format(n=n) \
        == f"⬜ 資料未備：持倉 · DIRECT {n} 筆未列入"
    assert _SKIPPED_LINE in hld5["detail_lines"]                                      # 略過的列照留
    assert hld_live._HLD5_EMPTY_LINE not in hld5["detail_lines"]
    assert hld5["tail_notes"][0] == {"text": hld_live.DIRECT_EXCLUDED_TEXT.format(n=n), "_tone": "黃"}   # DIRECT 那一行照加
    assert [t["text"] for t in hld5["tail_notes"][1:]] == ["DIRECT 第 3 列", "DIRECT 第 5 列"]
    text = "\n".join(HL.collect_ui_strings(model))
    assert HL.TEXT_NO_HOLDING not in text
    # `_replace_exits` 不跑：各塊略過的列沒有被改寫成 DIRECT 那一句
    for code in ("HLD-0", "HLD-1", "HLD-2", "HLD-3", "HLD-8"):
        block = HL.find_block(model, code)
        lines = list(block.get("lines") or ()) + list(block.get("detail_lines") or ())
        assert _SKIPPED_LINE in lines, code
        assert hld_live.DIRECT_EXCLUDED_TEXT.format(n=n) not in lines, code


def test_BNEW1_DIRECT加持倉全數略過_各塊狀態不動():
    a, b = _live_model(holdings=False, direct=False), _live_model(holdings=False)
    for code in ("HLD-0", "HLD-1", "HLD-2", "HLD-3", "HLD-5", "HLD-8"):
        assert HL.find_block(a, code)["_state"] == HL.find_block(b, code)["_state"], code


def test_BNEW1_沒有略過的列時原本那一支照舊_DIRECT摘要與出口替換():
    model = _live_model(holdings=False, skipped=False)
    n = _direct_n()
    hld5 = HL.find_block(model, "HLD-5")
    assert hld5["summary_text"] == hld_live.DIRECT_SUMMARY_ONLY.format(n=n)
    assert hld_live._HLD5_EMPTY_LINE not in hld5["detail_lines"]
    assert hld_live.DIRECT_EXCLUDED_TEXT.format(n=n) in HL.find_block(model, "HLD-1")["detail_lines"]   # 出口照換


def test_BNEW1_原本的不變式照舊_沒有略過的列而那一行不在就raise():
    model = HL.build_page_model(HF.scenario("empty")["dataset"], demo_hint=False)
    hld5 = HL.find_block(model, "HLD-5")
    hld5["detail_lines"] = [line for line in hld5["detail_lines"] if line != hld_live._HLD5_EMPTY_LINE]
    with pytest.raises(ValueError, match="空持倉的說明行"):
        hld_live._apply_direct(model, [{"tab": "DIRECT", "row": 3}], has_holdings=False)


def test_BNEW1_有略過的列而logic沒換掉那一行_同樣raise():
    model = HL.build_page_model(HF.scenario("empty")["dataset"], demo_hint=False)   # 沒有略過的列 → 那一行還在
    with pytest.raises(ValueError, match="有略過的持倉列"):
        hld_live._apply_direct(model, [{"tab": "DIRECT", "row": 3}], has_holdings=False, omitted=True)


def test_BNEW1_DIRECT加略過的列加有持倉_摘要照接DIRECT_略過的列照在燈下():
    model = _live_model(holdings=True)
    n = _direct_n()
    hld5 = HL.find_block(model, "HLD-5")
    assert hld5["summary_text"].endswith(hld_live.DIRECT_SUMMARY_SUFFIX.format(n=n))
    assert hld5["tail_notes"][0]["text"] == hld_live.DIRECT_EXCLUDED_TEXT.format(n=n)
    assert _SKIPPED_LINE in HL.find_block(model, "HLD-0")["lines"]


# ───────────────────────── should-fix 3：展開區摘要保留資料類 ─────────────────────────


@pytest.mark.parametrize("formal", [False, True])
def test_SF3_持倉列全數被略過_HLD5與HLD8摘要寫資料未備持倉(formal):
    args, ds = R2._hld_empty()
    model = R2._hld_model(args, ds, formal)
    want = "◇ 資料未備：持倉" if formal else _OMITTED_SUMMARY
    for code in ("HLD-1", "HLD-2", "HLD-3", "HLD-5", "HLD-8"):
        assert HL.find_block(model, code)["summary_text"] == want, code
    assert HL.OMITTED_SUMMARY == _OMITTED_SUMMARY


# ───────────────────────── should-fix 1：ALO-6、ALO-4 ─────────────────────────


def _alo(ds, formal=False):
    return R1._alo_formal(ds) if formal else AL.build_page_model(ds)


@pytest.mark.parametrize("formal", [False, True])
def test_SF1_ALO6_有略過的列_件數改資料未備_合計之後接略過的列(formal):
    model = _alo(R1._with(AF.scenario("inband"), skipped_holdings=_SKIPPED), formal)
    alo6 = AL.find_block(model, "ALO-6")
    # ~~`("◇ 資料未備" if formal else AL.TEXT_NOT_READY)`~~ → 第三輪補（總管派工：帶資料類「持倉」，與持股側一致；有意識的更正，不是漏刪）
    assert alo6["summary_text"] == ("◇ 資料未備：持倉" if formal else AL.TEXT_OMITTED_COUNT)
    assert not re.fullmatch(r"\d+ 檔.*", alo6["summary_text"])
    total = next(i for i, line in enumerate(alo6["footer_lines"]) if line.startswith("總體佔比合計"))
    assert alo6["footer_lines"][total + 1] == (_SKIPPED_FORMAL if formal else _SKIPPED_LINE)
    assert _HOLDING in alo6[page_health.MISSING_KEYS_KEY]


def test_SF1_ALO6_列與合計數字不動():
    a = AL.find_block(AL.build_page_model(AF.scenario("inband")), "ALO-6")
    b = AL.find_block(AL.build_page_model(R1._with(AF.scenario("inband"), skipped_holdings=_SKIPPED)), "ALO-6")
    assert b["_rows"] == a["_rows"]
    assert b["footer_lines"][:len(a["footer_lines"])] == a["footer_lines"]
    assert b["footer_lines"][len(a["footer_lines"]):] == [_SKIPPED_LINE]


def test_SF1_ALO6_有被排除的檔時_被排除那一段照接():
    ds = R1._with(AF.scenario("nofx"), skipped_holdings=_SKIPPED)                     # nofx：4 檔、被排除 2 檔
    alo6 = AL.find_block(AL.build_page_model(ds), "ALO-6")
    base = AL.find_block(AL.build_page_model(AF.scenario("nofx")), "ALO-6")
    assert base["summary_text"] == "4 檔；被排除 2 檔"                                 # 前提
    assert alo6["summary_text"] == f"{AL.TEXT_OMITTED_COUNT}；被排除 2 檔"   # ~~`TEXT_NOT_READY`~~（第三輪補，同上）
    assert "被排除 2 檔" in alo6["footer_lines"] and alo6["footer_lines"][-1] == _SKIPPED_LINE


def test_SF1_ALO6_持倉全數被略過_表尾寫出略過的列():
    alo6 = AL.find_block(AL.build_page_model(R1._with(AF.scenario("noholding"), skipped_holdings=_SKIPPED)), "ALO-6")
    assert alo6["_rows"] == [] and alo6["footer_lines"] == [_SKIPPED_LINE]
    assert _HOLDING in alo6[page_health.MISSING_KEYS_KEY]


def test_SF1_ALO6_沒有略過的列_逐鍵與動手前相同的形狀():
    alo6 = AL.find_block(AL.build_page_model(AF.scenario("inband")), "ALO-6")
    assert re.fullmatch(r"\d+ 檔(；被排除 \d+ 檔)?", alo6["summary_text"])
    assert not any("未列入" in line for line in alo6["footer_lines"])
    assert page_health.MISSING_KEYS_KEY not in alo6 or _HOLDING not in alo6[page_health.MISSING_KEYS_KEY]


@pytest.mark.parametrize("formal", [False, True])
def test_SF1_ALO4_有略過的列_未指派件數改資料未備_不算成未指派(formal):
    ds = R1._with(AF.scenario("inband"), skipped_holdings=_SKIPPED)
    alo4 = AL.find_block(_alo(ds, formal), "ALO-4")
    # ~~`("未指派 ◇ 資料未備" if formal else f"未指派 {AL.TEXT_NOT_READY}") in …`~~ → 第三輪補：帶資料類「持倉」（有意識的更正，不是漏刪）
    assert ("未指派 ◇ 資料未備：持倉" if formal else f"未指派 {AL.TEXT_OMITTED_COUNT}") in alo4["summary_text"]
    assert not re.search(r"未指派 \d+ 檔", alo4["summary_text"])
    base = AL.find_block(AL.build_page_model(AF.scenario("inband")), "ALO-4")
    assert alo4["unassigned_lines"] == base["unassigned_lines"]                      # 略過的列不算成未指派
    assert _HOLDING in alo4[page_health.MISSING_KEYS_KEY]


def test_SF1_ALO4_沒有略過的列_照舊未指派N檔():
    alo4 = AL.find_block(AL.build_page_model(AF.scenario("inband")), "ALO-4")
    assert re.search(r"未指派 \d+ 檔", alo4["summary_text"])


def test_SF1_合併頁基金占比_讀ALO6表尾_略過的列只出現一次():
    alo = R1._alo_formal(R1._with(AF.scenario("inband"), skipped_holdings=_SKIPPED))
    alo6 = AL.find_block(alo, "ALO-6")
    limits = dict(OV.share_detail(alo6)["groups"])["限制"]
    assert limits.count(_SKIPPED_FORMAL) == 1
    total = next(i for i, line in enumerate(limits) if line.startswith("總體佔比合計"))
    assert limits[total + 1] == _SKIPPED_FORMAL


# ───────────────────────── 附註：`_strip_dev_lines` 的殘留檢查不把上游原文當開發字句 ─────────────────────────


def test_附註_F2那一行的上游原文含殘留字串_不raise_照原字留著():
    marker = next(m for code, _f, _o, _t, _a, m in hld_live._DEV_TRIMS if code == "HLD-0")
    ds = R2._h6()
    ds["fund_errors"]["dividend"]["CCCC"] = f"上游回應：{marker}"
    model = HL.build_page_model(ds, demo_hint=False)
    before = list(HL.find_block(model, "HLD-0")["lines"])
    assert before == [f"配息與本金卡：⛔ 取數失敗：CCCC：上游回應：{marker}"]
    hld_live._strip_dev_lines(model)
    assert HL.find_block(model, "HLD-0")["lines"] == before


def test_附註_範本行殘留照舊raise():
    model = HL.build_page_model(R2._h6(), demo_hint=False)
    hld0 = HL.find_block(model, "HLD-0")
    hld0["lines"] = list(hld0["lines"]) + ["配息與本金卡：兩句同時成立時哪一句出現，規格沒有寫"]   # 卡名開頭但不是上游原文
    with pytest.raises(ValueError, match="開發過程字句"):
        hld_live._strip_dev_lines(model)


# ───────────────────────── 第三輪補：HLD-5／HLD-8 的「N 檔」（總管派工，同 ALO-6）─────────────────────────


@pytest.mark.parametrize("formal", [False, True])
@pytest.mark.parametrize("code,rest", [("HLD-5", " · 同時最多展開一檔"), ("HLD-8", " · 有值取不到或不適用")])
def test_SF1_HLD5與HLD8_有持倉而有略過的列_件數改資料未備持倉_其餘照留(formal, code, rest):
    ds = R1._with(HF.scenario("full")["dataset"], skipped_holdings=_SKIPPED)
    model = R1._hld_formal(ds) if formal else HL.build_page_model(ds, demo_hint=False)
    block = HL.find_block(model, code)
    assert block["summary_text"] == ("◇ 資料未備：持倉" if formal else _OMITTED_SUMMARY) + rest
    assert not re.match(r"\d+ 檔", block["summary_text"])
    assert block["detail_lines"][-1] == (_SKIPPED_FORMAL if formal else _SKIPPED_LINE)
    assert _HOLDING in block[page_health.MISSING_KEYS_KEY]


@pytest.mark.parametrize("code", ["HLD-5", "HLD-8"])
def test_SF1_HLD5與HLD8_列與狀態不動_示範字尾隨件數拿掉(code):
    base = HF.scenario("full")["dataset"]
    a = HL.find_block(HL.build_page_model(base), code)                                # 示範模式（帶字尾）
    b = HL.find_block(HL.build_page_model(R1._with(base, skipped_holdings=_SKIPPED)), code)
    assert re.match(rf"\d+ 檔{re.escape(HL.HINT)} · ", a["summary_text"])            # 前提
    assert b["summary_text"] == _OMITTED_SUMMARY + a["summary_text"].split(HL.HINT, 1)[1]
    assert (b["_state"], b["_rows"], b.get("buttons")) == (a["_state"], a["_rows"], a.get("buttons"))


@pytest.mark.parametrize("code", ["HLD-5", "HLD-8"])
def test_SF1_HLD5與HLD8_沒有略過的列_照舊N檔(code):
    block = HL.find_block(HL.build_page_model(HF.scenario("full")["dataset"], demo_hint=False), code)
    assert re.match(r"\d+ 檔 · ", block["summary_text"])
    assert not any("未列入" in line for line in block["detail_lines"])


# ───────────────────────── 第三輪補 2（總管派工）：ALO-2「未分類 N 檔」、合併頁各檔區間報酬、豁免只限卡名開頭 ─────────────────────────


@pytest.mark.parametrize("formal", [False, True])
def test_補2_ALO2未分類件數_有略過的列_改資料未備持倉(formal):
    ds = R1._with(AF.scenario("unbkt"), skipped_holdings=_SKIPPED)
    alo2 = AL.find_block(_alo(ds, formal), "ALO-2")
    assert f"{AL.UNCLASSIFIED} {'◇ 資料未備：持倉' if formal else AL.TEXT_OMITTED_COUNT}" in alo2["tail_lines"]
    assert not any(re.fullmatch(rf"{AL.UNCLASSIFIED} \d+ 檔", line) for line in alo2["tail_lines"])
    assert _HOLDING in alo2[page_health.MISSING_KEYS_KEY]


def test_補2_ALO2未分類件數_沒有略過的列_照舊N檔():
    alo2 = AL.find_block(AL.build_page_model(AF.scenario("unbkt")), "ALO-2")
    assert any(re.fullmatch(rf"{AL.UNCLASSIFIED} \d+ 檔", line) for line in alo2["tail_lines"])
    assert page_health.MISSING_KEYS_KEY not in alo2 or _HOLDING not in alo2[page_health.MISSING_KEYS_KEY]


def test_補2_TEXT_OMITTED_COUNT與持股側同一個字型():
    assert AL.TEXT_OMITTED_COUNT == HL.OMITTED_SUMMARY == "⬜ 資料未備：持倉"


def _returns_limits(hld2):
    return dict(OV.returns_detail(hld2)["groups"])["限制"]


def test_補2_合併頁各檔區間報酬_有持倉而有略過的列_接一次():
    hld2 = HL.find_block(R1._hld_formal(R1._with(HF.scenario("full")["dataset"], skipped_holdings=_SKIPPED)), "HLD-2")
    limits = _returns_limits(hld2)
    assert limits.count(_SKIPPED_FORMAL) == 1 and limits[-1] == _SKIPPED_FORMAL


def test_補2_合併頁各檔區間報酬_持倉全數被略過_說明區已有那一行_不重複():
    args, ds = R2._hld_empty()
    hld2 = HL.find_block(R2._hld_model(args, ds, True), "HLD-2")
    assert _SKIPPED_FORMAL in hld2["detail_lines"]                                   # 前提：B2 已寫進說明區
    assert _returns_limits(hld2).count(_SKIPPED_FORMAL) == 1


def test_補2_合併頁各檔區間報酬_沒有略過的列_與動手前相同():
    hld2 = HL.find_block(R1._hld_formal(HF.scenario("full")["dataset"]), "HLD-2")
    assert _returns_limits(hld2) == list(hld2["detail_lines"]) + [OV.TEXT_RETURNS_NOT_SUMMED]


def test_補2_附註豁免只限卡名開頭_其他行含取數失敗與殘留字串照舊raise():
    """`_is_upstream_error_line` 的放寬只給 F-2 那一行（以 `HLD-2`／`HLD-3` 卡名開頭）；行內有「⛔ 取數失敗：」但開頭不是那兩個卡名
    的範本行，殘留檢查照舊 raise（稽核突變 S3：放寬成「行內有取數失敗前綴就算」時本條轉紅）。"""
    marker = next(m for code, _f, _o, _t, _a, m in hld_live._DEV_TRIMS if code == "HLD-0")
    model = HL.build_page_model(R2._h6(), demo_hint=False)
    hld0 = HL.find_block(model, "HLD-0")
    other_title = HL.BLOCK_TITLES["HLD-1"]
    hld0["lines"] = list(hld0["lines"]) + [f"{other_title}：{hld_live._ERROR_LINE_PREFIX}X：{marker}"]
    with pytest.raises(ValueError, match="開發過程字句"):
        hld_live._strip_dev_lines(model)
    for line in (f"（另：{hld_live._ERROR_LINE_PREFIX}{marker}）", f"{marker}　{hld_live._ERROR_LINE_PREFIX}X"):
        assert hld_live._is_upstream_error_line(line) is False, line
    for code in ("HLD-2", "HLD-3"):
        assert hld_live._is_upstream_error_line(f"{HL.BLOCK_TITLES[code]}：{hld_live._ERROR_LINE_PREFIX}X：{marker}") is True
