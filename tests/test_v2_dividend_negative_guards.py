# -*- coding: utf-8 -*-
"""配息事件「不得誤推」負向守衛（C 線；fast lane；全程離線、不取數、不改資料契約）。

既有 `tests/test_v2_tables_dividend_chain.py` 已守衛多數正向行為；本檔只補它沒有的負向項目：
(a) 配息頻率標籤（月配等）不得被當成「已發放」；(b) settled 的空列不得被當成「累積型」證據；
(c) 配息表入口不收本金證據、輸出列不長出收益／本金欄；(d) `div_kind` 恆 unknown，來源夾帶的類別字樣不得被採用；
(e) `pay_date` 不得由 `ex_date` 補，也不得有「個人實收」欄位。
每項含正控（確認測試能看見東西）與變異負控（確認偵測器在被汙染時會紅）。
不解除 DIV_DATE_IS_EX_DATE_VERIFIED／NAV_HISTORY_PROVENANCE_VERIFIED；不碰 onebrain。
"""

from __future__ import annotations

import copy
import datetime as dt
import inspect

import pytest

import repositories.fund.sources as S
from repositories.fund import fund_orchestration as FO
from services.v2_tables import contract
from services.v2_tables import nav_dividend as ND

NOW = dt.datetime(2026, 10, 1, 0, 0, tzinfo=dt.timezone.utc)
L1_AT = "2026-09-30T08:00:00+00:00"
_NO_DROP = {"truncated": 0, "filtered": 0, "other_tables": 0}


def _tcb_item(ex="2026/09/03", pay="2026/09/10", amt=0.05, ccy="美元", **extra):
    item = {"date": "2026/09/01", "ex_date": ex, "pay_date": pay, "amount": amt, "yield_pct": 6.0, "currency": ccy,
            S.DIV_PROVENANCE_KEY: {"parser": S.DIV_PARSER_TCB, "date_header": "配息基準日", "ex_date_header": "除息日",
                                   "pay_date_header": "發放日", "currency_header": "幣別", "amount_header": "每單位配息額",
                                   "header_cells": 7, "row_td_cells": 7, "row_th_cells": 0, "table_has_span": False,
                                   "page": "x", "fetched_at": L1_AT}}
    item.update(extra)
    return item


def _div(items, outcome=FO.DIV_OUTCOME_ROWS, evidenced=False, **top):
    sources = [{"source": "tcb_moneydj", "parser": S.DIV_PARSER_TCB, "status": S.DIV_STATUS_ROWS, "detail": "",
                "page_type": "yp010001", "dropped": dict(_NO_DROP)}]
    out = {"items": items, "outcome": {"outcome": outcome, "sources": sources, "legacy_inline_parse": False,
                                       "none_evidenced": evidenced}, "error": None}
    out.update(top)
    return out


_ORIG_ROWS = ND.rows_from_chain_dividends      # 負控會替換 ND 上的函式；基準一律用原版


def _rows(div):
    return ND.rows_from_chain_dividends("ZZ01", div, holding_ccys=["USD"], now=NOW)


def _polluted(monkeypatch, mutate):
    """變異負控：把 production 的 `rows_from_chain_dividends` 換成「先照常算、再汙染輸出」的版本，
    讓負控走與正式測試相同的 `_rows` → helper 判斷路徑。"""
    orig = ND.rows_from_chain_dividends

    def wrapper(*a, **k):
        out = orig(*a, **k)
        mutate(out)
        return out

    monkeypatch.setattr(ND, "rows_from_chain_dividends", wrapper)


# ───────────── (a) 配息頻率標籤不得被當成「已發放」 ─────────────
# 既有測試沒有任何一個帶 dividend_policy／配息頻率的輸入。

_FREQ = {"dividend_policy": "月配", "配息頻率": "月配", "dividend_frequency": "monthly"}
_BARE = {"date": "2026/09/01", "ex_date": "2026/09/03", "amount": 0.05, "currency": "USD", **_FREQ}


def _assert_label_not_paid(out):
    assert out["rows"] == [] and out["settled"] is False


def test_a_正控_有解析依據的列_照寫():
    out = _rows(_div([_tcb_item()]))
    assert len(out["rows"]) == 1 and out["rows"][0]["ex_date"] == "2026-09-03"


def test_a_只有頻率標籤沒有解析依據的列_不寫列_不算已發放():
    out = _rows(_div([_BARE]))
    _assert_label_not_paid(out)
    assert out["pending"] == ND.PENDING_DIV_EX_DATE_UNVERIFIED


def test_a_空列加頻率標籤_不當成已發放_也不當成確定不配息():
    plain = _rows(_div([], outcome=FO.DIV_OUTCOME_UNDETERMINED))
    labeled = _rows(_div([], outcome=FO.DIV_OUTCOME_UNDETERMINED, **_FREQ))
    _assert_label_not_paid(labeled)
    assert labeled["withheld"] == ND.WITHHELD_DIV_OUTCOME_UNDETERMINED
    assert labeled == plain


def test_a_頻率標籤不改變輸出_有解析依據的列帶標籤與不帶完全相同():
    assert _rows(_div([_tcb_item(**_FREQ)])) == _rows(_div([_tcb_item()]))


def test_a_變異負控_標籤被當成已發放時_helper會紅(monkeypatch):
    def leak(out):
        out["rows"].append({"fund_code": "ZZ01", "ex_date": "2026-09-03"})
        out["settled"] = True

    _polluted(monkeypatch, leak)
    with pytest.raises(AssertionError):
        _assert_label_not_paid(_rows(_div([_BARE])))


# ───────────── (b) settled 的空列不得被當成「累積型」證據 ─────────────
# 既有 :408 只驗 settled 為真；補：輸出結構（鍵集合、provenance 鍵、skipped 文案）沒有任何「類型」判定。

def _assert_no_type_claim(out):
    base = _ORIG_ROWS("ZZ01", _div([], outcome=FO.DIV_OUTCOME_UNDETERMINED), holding_ccys=["USD"], now=NOW)
    assert set(out) == set(base)
    assert set(out["provenance"]) == set(base["provenance"])
    assert out["rows"] == [] and out["skipped"] == [ND.TEXT_DIV_NONE]


def test_b_正控_確定沒有配息_settled_且無列():
    out = _rows(_div([], outcome=FO.DIV_OUTCOME_NONE, evidenced=True))
    assert out["rows"] == [] and out["settled"] is True


def test_b_settled空列_輸出結構沒有任何類型判定():
    _assert_no_type_claim(_rows(_div([], outcome=FO.DIV_OUTCOME_NONE, evidenced=True)))


def test_b_輸入帶累積型標籤_輸出結構不變():
    plain = _rows(_div([], outcome=FO.DIV_OUTCOME_NONE, evidenced=True))
    labeled = _rows(_div([], outcome=FO.DIV_OUTCOME_NONE, evidenced=True, dividend_policy="累積型"))
    assert labeled == plain
    _assert_no_type_claim(labeled)


def test_b_變異負控_輸出長出類型欄時_helper會紅(monkeypatch):
    _polluted(monkeypatch, lambda out: out["provenance"].update(dividend_policy="accumulating"))
    with pytest.raises(AssertionError):
        _assert_no_type_claim(_rows(_div([], outcome=FO.DIV_OUTCOME_NONE, evidenced=True)))


# ───────────── (c) 配息表入口不收本金證據、輸出列不長出收益／本金欄 ─────────────
# 範圍僅限本表的入口與輸出面。「全額收益」類輸出本身：無觀察點，無法機械守衛
# （本表資料流內沒有這種輸出；services/fund_total_return.py 等不在其內，本檔不碰）。

_PRINCIPAL_PARAMS = {"invest_twd", "principal_twd", "principal", "total_return"}
_CONTRACT_NAMES = {f[0] for f in contract.DIVIDEND_FIELDS}


def _assert_no_principal_input(fn):
    assert not (set(inspect.signature(fn).parameters) & _PRINCIPAL_PARAMS), fn.__name__


def _assert_contract_columns_only(rows):
    assert rows and all(set(r) == _CONTRACT_NAMES for r in rows)


def test_c_配息表函式簽名不收本金證據():
    for fn in (ND.rows_from_chain_dividends, ND.rows_from_dividends, ND.build_dividend_table):
        _assert_no_principal_input(fn)


def test_c_輸出列只有契約欄位():
    _assert_contract_columns_only(_rows(_div([_tcb_item(invest_twd="", principal_twd=0, total_return=123.0)]))["rows"])


def test_c_變異負控_簽名收本金或列長出欄位時_helper會紅(monkeypatch):
    def with_principal(items, *, invest_twd=None):
        return None

    with pytest.raises(AssertionError):
        _assert_no_principal_input(with_principal)
    _polluted(monkeypatch, lambda out: [r.update(total_return=1.0) for r in out["rows"]])
    with pytest.raises(AssertionError):
        _assert_contract_columns_only(_rows(_div([_tcb_item()]))["rows"])


# ───────────── (d) div_kind 恆 unknown，不得被下游當成已知類別 ─────────────
# 既有 :395 只驗一般列；補：來源夾帶類別字樣（A 鏈路徑與舊路徑 `rows_from_dividends` 直呼）仍 unknown。
# 下游端（HLD-8 對 unknown 印「配息類別未知」）已由 :534 守衛，不重複。

def _assert_kinds_unknown(out):
    assert out["rows"] and {r["div_kind"] for r in out["rows"]} == {"unknown"}


@pytest.mark.parametrize("kw", [{"div_kind": "principal"}, {"dividend_type": "本金"}, {"類別": "收益"},
                                {"div_kind": "income", "type": "income"}])
def test_d_來源夾帶類別字樣_div_kind仍為unknown(kw):
    _assert_kinds_unknown(_rows(_div([_tcb_item(**kw)])))


@pytest.mark.parametrize("kw", [{"div_kind": "principal"}, {"dividend_type": "本金"}, {"類別": "收益"}])
def test_d_舊路徑直呼rows_from_dividends_夾帶類別字樣_div_kind仍為unknown(kw):
    item = {"date": "2026-09-03", "amount": 0.05, "currency": "USD", "fetched_at": L1_AT, **kw}
    _assert_kinds_unknown(ND.rows_from_dividends("ZZ01", [item], None, now=NOW))


def test_d_契約擋掉未登記的類別值():
    row = dict(_rows(_div([_tcb_item()]))["rows"][0])
    assert contract.dividend_row_problems(row) == []
    assert contract.dividend_row_problems(dict(row, div_kind="zz_mut"))      # 未登記值必有問題


def test_d_變異負控_列被汙染成已知類別時_helper會紅(monkeypatch):
    _polluted(monkeypatch, lambda out: [r.update(div_kind="principal") for r in out["rows"]])
    with pytest.raises(AssertionError):
        _assert_kinds_unknown(_rows(_div([_tcb_item()])))


# ───────────── (e) ex_date／pay_date／個人實收三者不得互相推導 ─────────────
# 既有 :395 只驗發放日有值時 pay_date 為 None；補：FundClear 把同值寫進 pay_date 也不採、
# 輸入缺 pay_date 不由 ex_date 補、輸出沒有實收欄位。

def _fc_item():
    return {"date": "2026-09-01", "ex_date": "2026-09-01", "pay_date": "2026-09-01", "amount": 0.05, "yield_pct": 0,
            "currency": "USD", S.DIV_PROVENANCE_KEY: {"parser": S.DIV_PARSER_FUNDCLEAR, "date_field": "ExDividendDate",
                                                      "currency_field": "Currency", "amount_field": "DividendAmount",
                                                      "fetched_at": L1_AT}}


def _fc_div(items):
    out = _div(items)
    out["outcome"]["sources"] = [{"parser": S.DIV_PARSER_FUNDCLEAR, "status": S.DIV_STATUS_ROWS,
                                  "dropped": {"filtered": 0}}]
    return out


def _assert_pay_date_empty(out):
    assert out["rows"] and all(r["pay_date"] is None for r in out["rows"])


def _assert_no_receipt_field(out):
    assert out["rows"]
    for r in out["rows"]:
        assert not any(w in k.lower() for k in r for w in ("receiv", "實收", "入帳", "personal"))


def test_e_正控_FundClear列被採用_ex_date有值():
    assert [r["ex_date"] for r in _rows(_fc_div([_fc_item()]))["rows"]] == ["2026-09-01"]


def test_e_pay_date恆為空_即使來源把同值寫進pay_date():
    _assert_pay_date_empty(_rows(_fc_div([_fc_item()])))


def test_e_輸入缺pay_date_不由ex_date補():
    item = _fc_item()
    del item["pay_date"]
    _assert_pay_date_empty(_rows(_fc_div([item])))


def test_e_發放日與除息日不同的列_pay_date仍為空_不採發放日():
    out = _rows(_div([_tcb_item(ex="2026/09/03", pay="2026/09/10")]))
    assert [(r["ex_date"], r["pay_date"]) for r in out["rows"]] == [("2026-09-03", None)]


def test_e_輸出沒有個人實收欄位():
    _assert_no_receipt_field(_rows(_div([_tcb_item(received_amount=9.9, actual_received="2026-09-12")])))


def test_e_變異負控_pay_date被ex_date補或長出實收欄時_helper會紅(monkeypatch):
    _polluted(monkeypatch, lambda out: [r.update(pay_date=r["ex_date"]) for r in out["rows"]])
    with pytest.raises(AssertionError):
        _assert_pay_date_empty(_rows(_div([_tcb_item()])))
    _polluted(monkeypatch, lambda out: [r.update(received_amount=1.0) for r in out["rows"]])
    with pytest.raises(AssertionError):
        _assert_no_receipt_field(_rows(_div([_tcb_item()])))
