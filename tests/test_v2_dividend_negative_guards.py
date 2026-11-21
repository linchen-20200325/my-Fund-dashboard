# -*- coding: utf-8 -*-
"""配息事件「不得誤推」負向守衛（C 線；fast lane；全程離線、不取數、不改資料契約）。

既有 `tests/test_v2_tables_dividend_chain.py` 已守衛多數正向行為；本檔只補它沒有的負向項目：
(a) 配息頻率標籤（月配等）不得被當成「已發放」；(b) settled 的空列不得被當成「累積型」證據；
(c) 本金證據不是配息表的輸入（無「全額收益」觀察點）；(d) `div_kind` 恆 unknown，來源夾帶的類別字樣不得被採用；
(e) `pay_date` 不得由 `ex_date` 補，也不得有「個人實收」欄位。
每項含正控（確認測試能看見東西）與變異負控（確認偵測器在被汙染時會紅）。
不解除 DIV_DATE_IS_EX_DATE_VERIFIED／NAV_HISTORY_PROVENANCE_VERIFIED；不碰 onebrain。
"""

from __future__ import annotations

import copy
import datetime as dt
import inspect
import json

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


def _rows(div):
    return ND.rows_from_chain_dividends("ZZ01", div, holding_ccys=["USD"], now=NOW)


# ───────────── (a) 配息頻率標籤不得被當成「已發放」 ─────────────
# 既有測試：`test_日期語意_沒有解析依據的列…_一律不收` 只用不帶頻率標籤的列；沒有任何測試帶 dividend_policy／配息頻率。

_FREQ = {"dividend_policy": "月配", "配息頻率": "月配", "dividend_frequency": "monthly"}


def test_a_正控_有解析依據的列_照寫():
    out = _rows(_div([_tcb_item()]))
    assert len(out["rows"]) == 1 and out["rows"][0]["ex_date"] == "2026-09-03"


def test_a_只有頻率標籤沒有解析依據的列_不寫列_不算已發放():
    bare = {"date": "2026/09/01", "ex_date": "2026/09/03", "amount": 0.05, "currency": "USD", **_FREQ}
    out = _rows(_div([bare]))
    assert out["rows"] == [] and out["settled"] is False
    assert out["pending"] == ND.PENDING_DIV_EX_DATE_UNVERIFIED


def test_a_空列加頻率標籤_不當成已發放_也不當成確定不配息():
    # 頂層帶「月配」標籤、items 空、取數狀態分辨不出 → 照舊 undetermined；標籤不得改變結果
    plain = _rows(_div([], outcome=FO.DIV_OUTCOME_UNDETERMINED))
    labeled = _rows(_div([], outcome=FO.DIV_OUTCOME_UNDETERMINED, **_FREQ))
    assert labeled["rows"] == [] and labeled["settled"] is False
    assert labeled["withheld"] == ND.WITHHELD_DIV_OUTCOME_UNDETERMINED
    assert labeled == plain


def test_a_頻率標籤不改變輸出_有解析依據的列帶標籤與不帶完全相同():
    assert _rows(_div([_tcb_item(**_FREQ)])) == _rows(_div([_tcb_item()]))


def test_a_變異負控_偵測器對汙染敏感():
    # 若實作把「月配」當成已發放，會多出一列；此處手造汙染結果，確認 a 類斷言形狀會紅
    clean = _rows(_div([{"ex_date": "2026/09/03", "amount": 0.05, "currency": "USD", **_FREQ}]))
    polluted = copy.deepcopy(clean)
    polluted["rows"].append({"fund_code": "ZZ01", "ex_date": "2026-09-03"})
    with pytest.raises(AssertionError):
        assert polluted["rows"] == []


# ───────────── (b) settled 的空列不得被當成「累積型」證據 ─────────────
# 既有測試只驗 settled 為真、rows 為空；沒有驗輸出不含任何「累積型」判定。

def _accum_claim(out) -> bool:
    text = json.dumps(out, ensure_ascii=False, default=str).lower()
    return any(w in text for w in ("累積", "accum", "不配息型"))


def test_b_正控_確定沒有配息_settled_且無列():
    out = _rows(_div([], outcome=FO.DIV_OUTCOME_NONE, evidenced=True))
    assert out["rows"] == [] and out["settled"] is True


def test_b_settled空列_輸出不含任何累積型判定():
    out = _rows(_div([], outcome=FO.DIV_OUTCOME_NONE, evidenced=True))
    assert not _accum_claim(out)
    assert "div_kind" not in out and "dividend_policy" not in out["provenance"]


def test_b_有標籤的空列_標籤不得被改寫成累積型():
    out = _rows(_div([], outcome=FO.DIV_OUTCOME_NONE, evidenced=True, dividend_policy="累積型"))
    assert not _accum_claim(out)          # 輸入帶「累積型」字樣也不得被回傳


def test_b_變異負控_偵測器對汙染敏感():
    out = _rows(_div([], outcome=FO.DIV_OUTCOME_NONE, evidenced=True))
    out["provenance"]["note"] = "累積型"
    assert _accum_claim(out) is True


# ───────────── (c) 缺本金證據不得讓任何「全額收益」類輸出出現數字 ─────────────
# 觀察點：配息表層沒有「全額收益」輸出，也不接收 invest_twd／本金；`ui_v2/hld` 亦無此字樣 → 只能守「入口與輸出面」。
# 「全額收益」類輸出本身：無觀察點，無法機械守衛（services/fund_total_return.py 等不在本表的資料流內，本檔不碰）。

_PRINCIPAL_WORDS = ("invest", "principal", "本金", "twd", "total_return", "全額")


def test_c_配息表函式簽名不收本金證據():
    for fn in (ND.rows_from_chain_dividends, ND.rows_from_dividends, ND.build_dividend_table):
        params = " ".join(inspect.signature(fn).parameters).lower()
        assert not any(w in params for w in _PRINCIPAL_WORDS), fn.__name__


def test_c_輸出列只有契約欄位_沒有收益或本金衍生欄():
    out = _rows(_div([_tcb_item(invest_twd="", principal_twd=0, total_return=123.0)]))
    names = {f[0] for f in contract.DIVIDEND_FIELDS}
    assert out["rows"] and all(set(r) == names for r in out["rows"])


def test_c_變異負控_偵測器對汙染敏感():
    row = dict(_rows(_div([_tcb_item()]))["rows"][0], total_return=1.0)
    assert set(row) != {f[0] for f in contract.DIVIDEND_FIELDS}


# ───────────── (d) div_kind 恆 unknown，不得被下游當成已知類別 ─────────────
# 既有 `test_div_kind恆為unknown…` 只驗一般列；補：來源夾帶「本金／收益」字樣時仍 unknown。
# 下游端（HLD-8 對 unknown 印「配息類別未知」）已由 `test_hld_每一檔都確定_接上真資料…` 守衛，不重複。

def _kinds(out):
    return {r["div_kind"] for r in out["rows"]}


@pytest.mark.parametrize("kw", [{"div_kind": "principal"}, {"dividend_type": "本金"}, {"類別": "收益"},
                                {"div_kind": "income", "type": "income"}])
def test_d_來源夾帶類別字樣_div_kind仍為unknown(kw):
    out = _rows(_div([_tcb_item(**kw)]))
    assert out["rows"] and _kinds(out) == {"unknown"}


def test_d_unknown在契約值域內_且常數未被改寫():
    assert ND.DIV_KIND_UNKNOWN == "unknown" and "unknown" in contract.DIV_KIND_VALUES


def test_d_變異負控_常數被改成未登記值_列不再通過(monkeypatch):
    monkeypatch.setattr(ND, "DIV_KIND_UNKNOWN", "zz_mut")
    out = _rows(_div([_tcb_item()]))
    assert _kinds(out) != {"unknown"}      # 偵測器對被汙染的常數敏感（列被契約擋掉或類別改變）


# ───────────── (e) ex_date／pay_date／個人實收三者不得互相推導 ─────────────
# 既有測試只驗 pay_date 為 None（輸入的發放日有值）；補：FundClear 把同值寫進 pay_date 也不採、
# 輸入缺 pay_date 不由 ex_date 補、輸出沒有任何「實收」欄位。

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


def test_e_正控_FundClear列被採用_ex_date有值():
    out = _rows(_fc_div([_fc_item()]))
    assert [r["ex_date"] for r in out["rows"]] == ["2026-09-01"]


def test_e_pay_date恆為空_即使來源把同值寫進pay_date():
    out = _rows(_fc_div([_fc_item()]))
    assert [r["pay_date"] for r in out["rows"]] == [None]


def test_e_輸入缺pay_date_不由ex_date補():
    item = _fc_item()
    del item["pay_date"]
    out = _rows(_fc_div([item]))
    assert out["rows"] and all(r["pay_date"] is None and r["pay_date"] != r["ex_date"] for r in out["rows"])


def test_e_發放日與除息日不同的列_pay_date仍為空_不採發放日():
    out = _rows(_div([_tcb_item(ex="2026/09/03", pay="2026/09/10")]))
    assert [(r["ex_date"], r["pay_date"]) for r in out["rows"]] == [("2026-09-03", None)]


def test_e_輸出沒有個人實收欄位():
    out = _rows(_div([_tcb_item(received_amount=9.9, actual_received="2026-09-12")]))
    assert out["rows"]
    for r in out["rows"]:
        assert not any(w in k.lower() for k in r for w in ("receiv", "實收", "入帳", "personal"))


def test_e_變異負控_偵測器對汙染敏感():
    row = dict(_rows(_div([_tcb_item()]))["rows"][0])
    row["pay_date"] = row["ex_date"]                    # 模擬「由 ex_date 補 pay_date」
    assert row["pay_date"] is not None
    with pytest.raises(AssertionError):
        assert [row["pay_date"]] == [None]
