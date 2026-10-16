# -*- coding: utf-8 -*-
"""B 線配息移交給 A 鏈（客戶 2026-10-13 裁示；fast lane；不打網路）。

涵蓋：
- L1 三個配息解析器的新增鍵（取數狀態 `div_fetch`、逐筆 `div_provenance`）—— 取值與改動前相同；
- A 鏈的配息總結 `dividends_fetch_outcome` 與 L1 十五分鐘快取判準（不配息的基金命中快取、取數失敗不命中）；
- B 線逐來源的除息日判定、幣別規則、`div_kind` 恆為 `unknown`、`fetched_at` 取 L1 的值；
- `build_nav_dividend_tables` 同一次 A 鏈呼叫交出淨值與配息；
- hld 接線：HLD-3 期間配息合計、HLD-8 本金類配息佔比接上真資料後的結果。
"""

from __future__ import annotations

import contextlib
import copy
import datetime as dt
import io

import pytest

import _a_chain_stub as H
import repositories.fund.sources as S
from repositories.fund import fund_orchestration as FO
from services.v2_tables import nav_dividend as ND

NOW = dt.datetime(2026, 10, 1, 0, 0, tzinfo=dt.timezone.utc)
L1_AT = "2026-09-30T08:00:00+00:00"


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*args, **kwargs)


class _Resp:
    def __init__(self, text="", payload=None, status_code=200):
        self.text = text
        self._payload = payload
        self.status_code = status_code

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


_HDR = ("<tr><th>配息基準日</th><th>除息日</th><th>發放日</th><th>類別</th>"
        "<th>每單位配息額</th><th>年化配息率</th><th>幣別</th></tr>")
_ROW = ("<tr><td>2026/09/01</td><td>2026/09/03</td><td>2026/09/10</td><td>配息</td>"
        "<td>0.05</td><td>6.1</td><td>美元</td></tr>")
_TCB_PAGE = f"<table>{_HDR}{_ROW}</table>"
_TCB_EMPTY = f"<table>{_HDR}</table>"


def _by_url(mapping):
    def fake(url, *a, **k):
        for frag, value in mapping.items():
            if frag in url:
                return value
        return None
    return fake


def _strip_prov(items):
    return [{k: v for k, v in it.items() if k != S.DIV_PROVENANCE_KEY} for it in items]


# ═══════════════════════ L1：三個解析器的新增鍵（取值不變） ═══════════════════════

def test_TCB_記下表頭文字與取得時間_取值與改動前相同(monkeypatch):
    monkeypatch.setattr(S, "fetch_url_with_retry", lambda *a, **k: _Resp(_TCB_PAGE))
    divs = _quiet(S._src_tcb_div, "TLZF9")
    assert _strip_prov(divs) == [{"date": "2026/09/01", "ex_date": "2026/09/03", "pay_date": "2026/09/10",
                                  "amount": 0.05, "yield_pct": 6.1, "currency": "美元"}]
    prov = divs[0][S.DIV_PROVENANCE_KEY]
    assert prov["parser"] == S.DIV_PARSER_TCB
    assert (prov["date_header"], prov["ex_date_header"], prov["currency_header"]) == ("配息基準日", "除息日", "幣別")
    assert prov["fetched_at"] and prov["page"].startswith("tcbbankfund.moneydj.com")
    assert divs.div_fetch["status"] == S.DIV_STATUS_ROWS
    assert isinstance(divs, list)


def test_TCB_每一個網址都是空配息表_才算確實沒有配息(monkeypatch):
    monkeypatch.setattr(S, "fetch_url_with_retry", lambda *a, **k: _Resp(_TCB_EMPTY))
    divs = _quiet(S._src_tcb_div, "TLZF9")
    assert divs == [] and divs.div_fetch["status"] == S.DIV_STATUS_EMPTY


@pytest.mark.parametrize("other, why", [
    (None, "其中一個網址沒取到"),
    (_Resp("<html>blocked</html>"), "其中一個網址沒有配息表"),
    (_Resp(f"<table>{_HDR}<tr><td>查無資料</td></tr></table>"), "有解析不了的列"),
    (_Resp("<p>除息日</p><table><tr><td>x</td></tr></table>"), "字樣不在任何一張表裡"),
])
def test_TCB_任一網址分辨不出_算失敗不算沒有配息(monkeypatch, other, why):
    monkeypatch.setattr(S, "fetch_url_with_retry", _by_url({"www.moneydj.com/funddj/yp/funddividend": other,
                                                            "": _Resp(_TCB_EMPTY)}))
    divs = _quiet(S._src_tcb_div, "TLZF9")
    assert divs == [] and divs.div_fetch["status"] == S.DIV_STATUS_FAILED, why


@pytest.mark.parametrize("payload, status", [
    ({"Data": []}, S.DIV_STATUS_EMPTY),
    ({"data": []}, S.DIV_STATUS_EMPTY),
    ({"Data": None}, S.DIV_STATUS_FAILED),
    ({}, S.DIV_STATUS_FAILED),
    ({"Data": [{"DividendAmount": 0, "ExDividendDate": "2026-09-01"}]}, S.DIV_STATUS_FAILED),
])
def test_FundClear_取數狀態(monkeypatch, payload, status):
    monkeypatch.setattr(S, "fetch_url_with_retry", lambda *a, **k: _Resp(payload=payload))
    divs = _quiet(S._src_fundclear_div, "ZZ01")
    assert divs == [] and divs.div_fetch["status"] == status


def test_FundClear_請求失敗算失敗(monkeypatch):
    monkeypatch.setattr(S, "fetch_url_with_retry", lambda *a, **k: None)
    assert _quiet(S._src_fundclear_div, "ZZ01").div_fetch["status"] == S.DIV_STATUS_FAILED


def test_FundClear_記下日期與幣別取自哪個欄名_取值不變(monkeypatch):
    payload = {"Data": [
        {"DividendAmount": 0.05, "ExDividendDate": "2026-09-01", "Currency": "USD"},
        {"DividendAmount": 0.06, "Date": "2026-08-01"},
    ]}
    monkeypatch.setattr(S, "fetch_url_with_retry", lambda *a, **k: _Resp(payload=payload))
    divs = _quiet(S._src_fundclear_div, "ZZ01")
    assert _strip_prov(divs) == [
        {"date": "2026-09-01", "ex_date": "2026-09-01", "pay_date": "2026-09-01", "amount": 0.05,
         "yield_pct": 0, "currency": "USD"},
        {"date": "2026-08-01", "ex_date": "2026-08-01", "pay_date": "2026-08-01", "amount": 0.06,
         "yield_pct": 0, "currency": ""},
    ]
    assert [d[S.DIV_PROVENANCE_KEY]["date_field"] for d in divs] == ["ExDividendDate", "Date"]
    assert [d[S.DIV_PROVENANCE_KEY]["currency_field"] for d in divs] == ["Currency", ""]
    assert divs.div_fetch["status"] == S.DIV_STATUS_ROWS


@pytest.mark.parametrize("resp, status", [
    (_Resp(payload={"data": []}), S.DIV_STATUS_EMPTY),
    (_Resp(payload={"items": []}), S.DIV_STATUS_EMPTY),
    (_Resp(payload={}), S.DIV_STATUS_FAILED),
    (_Resp(payload={"data": []}, status_code=500), S.DIV_STATUS_FAILED),
])
def test_鉅亨_取數狀態_空結果也帶得出去(monkeypatch, resp, status):
    monkeypatch.setattr(S.requests, "get", lambda *a, **k: resp)
    divs = _quiet(S._src_cnyes_div, "ZZ01")
    assert divs == [] and divs.div_fetch["status"] == status


def test_鉅亨_記下日期取自哪個欄名(monkeypatch):
    monkeypatch.setattr(S.requests, "get", lambda *a, **k: _Resp(payload={"data": [
        {"exDate": "2026-09-01", "dividend": 0.05}, {"date": "2026-08-01", "dividend": 0.04}]}))
    divs = _quiet(S._src_cnyes_div, "ZZ01")
    assert [d[S.DIV_PROVENANCE_KEY]["date_field"] for d in divs] == ["exDate", "date"]
    assert [d["date"] for d in divs] == ["2026-09-01", "2026-08-01"]


# ═══════════════════════ A 鏈：配息總結與 L1 十五分鐘快取 ═══════════════════════

def _empty(parser):
    return S._div_result([], parser, S.DIV_STATUS_EMPTY, "空")


def _failed(parser):
    return S._div_result([], parser, S.DIV_STATUS_FAILED, "HTTP 503")


def _no_div_scenario(*, tcb=None, fundclear=None, cnyes=None):
    code, sc = H.full_success_scenario()
    # ⚠️ 用 `is None` 判斷：失敗的 `DividendList` 是空清單，`or` 會把它換掉
    sc = dict(sc, _src_tcb_div=_empty(S.DIV_PARSER_TCB) if tcb is None else tcb,
              _src_fundclear_div=_empty(S.DIV_PARSER_FUNDCLEAR) if fundclear is None else fundclear,
              _src_cnyes_div=_empty(S.DIV_PARSER_CNYES) if cnyes is None else cnyes)
    return code, sc


def test_三個來源都自報確實沒有配息_總結為none_confirmed(monkeypatch):
    code, sc = _no_div_scenario()
    H.install(monkeypatch, sc)
    res = _quiet(FO.fetch_fund_from_moneydj_url, code)
    out = res[FO.DIVIDENDS_OUTCOME_KEY]
    assert out["outcome"] == FO.DIV_OUTCOME_NONE
    assert [s["source"] for s in out["sources"]] == ["tcb_moneydj", "FundClear", "cnyes"]   # 瀑布順序照舊


def test_不配息基金_L1第二次命中快取_不再打來源(monkeypatch):
    code, sc = _no_div_scenario()
    calls = H.install(monkeypatch, sc)
    _quiet(FO.fetch_fund_from_moneydj_url, code)
    n = len(calls)
    _quiet(FO.fetch_fund_from_moneydj_url, code)
    assert n > 0 and len(calls) == n


@pytest.mark.parametrize("which", ["tcb", "fundclear", "cnyes"])
def test_任一配息來源失敗_不入快取_下次真的再打(monkeypatch, which):
    parser = {"tcb": S.DIV_PARSER_TCB, "fundclear": S.DIV_PARSER_FUNDCLEAR, "cnyes": S.DIV_PARSER_CNYES}[which]
    code, sc = _no_div_scenario(**{which: _failed(parser)})
    calls = H.install(monkeypatch, sc)
    res = _quiet(FO.fetch_fund_from_moneydj_url, code)
    assert res[FO.DIVIDENDS_OUTCOME_KEY]["outcome"] == FO.DIV_OUTCOME_UNDETERMINED
    _quiet(FO.fetch_fund_from_moneydj_url, code)
    assert [c[0] for c in calls].count("_src_tcb_div") == 2


def test_三個來源都失敗_總結為failed_不入快取(monkeypatch):
    code, sc = _no_div_scenario(tcb=_failed(S.DIV_PARSER_TCB), fundclear=_failed(S.DIV_PARSER_FUNDCLEAR),
                                cnyes=_failed(S.DIV_PARSER_CNYES))
    calls = H.install(monkeypatch, sc)
    res = _quiet(FO.fetch_fund_from_moneydj_url, code)
    assert res[FO.DIVIDENDS_OUTCOME_KEY]["outcome"] == FO.DIV_OUTCOME_FAILED
    _quiet(FO.fetch_fund_from_moneydj_url, code)
    assert [c[0] for c in calls].count("_src_tcb_div") == 2


def test_解析器沒有取數狀態_判斷不了_維持不快取(monkeypatch):
    code, sc = _no_div_scenario(tcb=[], fundclear=[], cnyes=[])   # 一般 list：沒有 div_fetch
    calls = H.install(monkeypatch, sc)
    _quiet(FO.fetch_fund_from_moneydj_url, code)
    _quiet(FO.fetch_fund_from_moneydj_url, code)
    assert [c[0] for c in calls].count("_src_tcb_div") == 2


def _funds(code, ccy="USD"):
    return [{"fund_code": code, "full_key": code, "chain_code": code, "portal": "", "holding_ccy": ccy}]


def test_B線_不配息基金_第二次build命中快取(monkeypatch):
    code, sc = _no_div_scenario()
    calls = H.install(monkeypatch, sc)
    first = _quiet(ND.build_nav_dividend_tables, _funds(code), now=NOW)
    n = len(calls)
    second = _quiet(ND.build_nav_dividend_tables, _funds(code), now=NOW)
    assert not [c for c in calls[n:] if c[0].startswith("_src_") or c[0].startswith("fetch_")]
    # 稽核必修 3：本情境鉅亨淨值沒被呼叫（FundClear 已夠筆數）→ 鉅亨回空沒有「認得代碼」的證據 → 不算確定不配息
    assert first["dividend"]["settled"] == second["dividend"]["settled"] == {code: False}
    assert first["dividend"]["withheld"] == {code: ND.WITHHELD_DIV_OUTCOME_UNDETERMINED}
    assert first["dividend"]["rows"] == []


def test_B線_配息取數失敗_第二次build不命中快取(monkeypatch):
    code, sc = _no_div_scenario(tcb=_failed(S.DIV_PARSER_TCB))
    calls = H.install(monkeypatch, sc)
    out = _quiet(ND.build_nav_dividend_tables, _funds(code), now=NOW)
    n = len(calls)
    _quiet(ND.build_nav_dividend_tables, _funds(code), now=NOW)
    assert ("_src_tcb_div", code) in calls[n:]
    assert out["dividend"]["settled"] == {code: False}
    assert out["dividend"]["withheld"] == {code: ND.WITHHELD_DIV_OUTCOME_UNDETERMINED}


# ═══════════════════════ B 線：同一次 A 鏈呼叫交出淨值與配息 ═══════════════════════

def _tcb_items(*rows, header=("配息基準日", "除息日", "發放日", "類別", "每單位配息額", "年化配息率", "幣別"),
               at=L1_AT, dropped=None):
    items = [{"date": base, "ex_date": ex, "pay_date": pay, "amount": amt, "yield_pct": 6.0, "currency": ccy,
              S.DIV_PROVENANCE_KEY: {"parser": S.DIV_PARSER_TCB,
                                     "date_header": header[0] if len(header) > 0 else None,
                                     "ex_date_header": header[1] if len(header) > 1 else None,
                                     "pay_date_header": header[2] if len(header) > 2 else None,
                                     "currency_header": header[6] if len(header) > 6 else None,
                                     "amount_header": header[4] if len(header) > 4 else None,
                                     "header_cells": len(header), "row_td_cells": 7, "row_th_cells": 0,
                                     "table_has_span": False,
                                     "page": "tcbbankfund.moneydj.com/funddj/yp/wb05.djhtm", "fetched_at": at}}
             for base, ex, pay, amt, ccy in rows]
    return S._div_result(items, S.DIV_PARSER_TCB, S.DIV_STATUS_ROWS, dropped=dropped or {"truncated": 0, "filtered": 0,
                                                                                           "other_tables": 0})


def test_同一次A鏈呼叫_來源呼叫順序與只取淨值時相同_淨值逐鍵相同(monkeypatch):
    code, sc = H.full_success_scenario()
    sc = dict(sc, _src_tcb_div=_tcb_items(("2026/09/01", "2026/09/03", "2026/09/10", 0.05, "美元")))
    a = H.install(monkeypatch, sc)
    nav_only = _quiet(ND.build_nav_table, _funds(code), now=NOW)
    expected = list(a)
    b = H.install(monkeypatch, sc)
    both = _quiet(ND.build_nav_dividend_tables, _funds(code), now=NOW)
    assert list(b) == expected                              # 沒有多打任何一個來源
    assert both["nav"] == nav_only
    assert [r["ex_date"] for r in both["dividend"]["rows"]] == ["2026-09-03"]
    assert both["dividend"]["settled"] == {code: True}


_NO_DROP = {"truncated": 0, "filtered": 0, "other_tables": 0}


def _div(items, outcome=FO.DIV_OUTCOME_ROWS, sources=None, evidenced=False):
    if sources is None:
        sources = [{"source": "tcb_moneydj", "parser": S.DIV_PARSER_TCB, "status": S.DIV_STATUS_ROWS,
                    "detail": "", "page_type": "yp010001", "dropped": dict(_NO_DROP)}]
    return {"items": items, "outcome": {"outcome": outcome, "sources": sources, "legacy_inline_parse": False,
                                        "none_evidenced": evidenced},
            "error": None}


def _rows(div, ccy="USD"):
    return ND.rows_from_chain_dividends("ZZ01", div, holding_ccys=[ccy], now=NOW)


def test_日期語意_合庫表頭第二格是除息日_取除息日那一欄_不取配息基準日():
    out = _rows(_div(_tcb_items(("2026/09/01", "2026/09/03", "2026/09/10", 0.05, "美元"))))
    assert out["error"] is None and out["withheld"] is None and out["pending"] is None
    assert out["rows"] == [{"fund_code": "ZZ01", "ex_date": "2026-09-03", "pay_date": None,
                            "div_per_unit_orig_ccy": 0.05, "ccy": "USD", "div_kind": "unknown",
                            "fetched_at": "2026-09-30T08:00:00+00:00"}]
    assert out["settled"] is True


@pytest.mark.parametrize("header", [
    ("配息基準日", "配息基準日", "發放日", "類別", "每單位配息額", "年化配息率", "幣別"),   # 第二欄其實是配息基準日
    ("除息日", "配息基準日", "發放日", "類別", "每單位配息額", "年化配息率", "幣別"),       # 欄位對調
    (),                                                                                    # 抓不到表頭
])
def test_日期語意_表頭第二格不是除息日_照實列pending_不寫列(header):
    out = _rows(_div(_tcb_items(("2026/09/01", "2026/09/03", "2026/09/10", 0.05, "美元"), header=header)))
    assert out["rows"] == [] and out["pending"] == ND.PENDING_DIV_EX_DATE_UNVERIFIED
    assert out["settled"] is False
    assert any("證明不了是除息日" in line for line in out["skipped"])


def _fc_item(field, value="2026-09-01", ccy="USD", ccy_field="Currency", amount_field="DividendAmount"):
    return {"date": value, "ex_date": value, "pay_date": value, "amount": 0.05, "yield_pct": 0, "currency": ccy,
            S.DIV_PROVENANCE_KEY: {"parser": S.DIV_PARSER_FUNDCLEAR, "date_field": field,
                                   "currency_field": ccy_field, "amount_field": amount_field, "fetched_at": L1_AT}}


def test_日期語意_FundClear_只收ExDividendDate_退回Date的不收():
    ok = _rows(_div([_fc_item("ExDividendDate")],
                    sources=[{"parser": S.DIV_PARSER_FUNDCLEAR, "status": S.DIV_STATUS_ROWS, "dropped": {"filtered": 0}}]))
    assert [r["ex_date"] for r in ok["rows"]] == ["2026-09-01"] and ok["settled"] is True
    bad = _rows(_div([_fc_item("Date")]))
    assert bad["rows"] == [] and bad["pending"] == ND.PENDING_DIV_EX_DATE_UNVERIFIED


def test_日期語意_沒有解析依據的列_例如legacy段內嵌解析_一律不收():
    items = [{"date": "2026/09/01", "ex_date": "2026/09/03", "pay_date": "2026/09/10", "amount": 0.05,
              "yield_pct": 6.0, "currency": "USD"}]
    out = _rows(_div(items))
    assert out["rows"] == [] and out["pending"] == ND.PENDING_DIV_EX_DATE_UNVERIFIED


def test_日期語意_鉅亨取自exDate也因為沒有幣別而不寫():
    item = {"date": "2026-09-01", "amount": 0.05, "yield_pct": 0, "source": "Cnyes:dividend:ZZ01",
            "fetched_at": L1_AT,
            S.DIV_PROVENANCE_KEY: {"parser": S.DIV_PARSER_CNYES, "date_field": "exDate", "amount_field": "dividend",
                                   "fetched_at": L1_AT}}
    out = _rows(_div([item]))
    assert out["rows"] == [] and out["withheld"] == ND.WITHHELD_CCY_NOT_SOURCE_REPORTED


@pytest.mark.parametrize("value", ["2026/9/3", "115/09/03", "Sep 03", "2026-09-31"])
def test_日期格式_不是十字元的西元日期_不收不猜(value):
    out = _rows(_div(_tcb_items(("2026/09/01", value, "", 0.05, "美元"))))
    assert out["rows"] == [] and out["settled"] is False


# ── 幣別 ──

def test_幣別_來源宣告與持倉不同_整檔不寫():
    items = _tcb_items(("2026/09/01", "2026/09/03", "", 0.05, "美元"), ("2026/08/01", "2026/08/03", "", 0.05, "歐元"))
    out = _rows(_div(items), ccy="USD")
    assert out["rows"] == [] and out["withheld"] == ND.WITHHELD_CCY_CONFLICT and out["settled"] is False
    assert out["fetched"] == 2 and out["skipped_rows"] == 2


def test_幣別_來源宣告的值認不出_當成不同_整檔不寫():
    out = _rows(_div(_tcb_items(("2026/09/01", "2026/09/03", "", 0.05, "某某幣"))), ccy="USD")
    assert out["rows"] == [] and out["withheld"] == ND.WITHHELD_CCY_CONFLICT


def test_幣別_中文名與持倉相同_照寫_標籤用持倉手填():
    out = _rows(_div(_tcb_items(("2026/09/01", "2026/09/03", "", 0.05, "歐元"))), ccy="EUR")
    assert [r["ccy"] for r in out["rows"]] == ["EUR"]


def test_幣別_來源沒宣告_照實不寫():
    out = _rows(_div(_tcb_items(("2026/09/01", "2026/09/03", "", 0.05, ""))))
    assert out["rows"] == [] and out["withheld"] == ND.WITHHELD_CCY_NOT_SOURCE_REPORTED


def test_幣別_表頭第七格不是幣別_值不算來源宣告():
    header = ("配息基準日", "除息日", "發放日", "類別", "每單位配息額", "年化配息率", "備註")
    out = _rows(_div(_tcb_items(("2026/09/01", "2026/09/03", "", 0.05, "美元"), header=header)))
    assert out["rows"] == [] and out["withheld"] == ND.WITHHELD_CCY_NOT_SOURCE_REPORTED


@pytest.mark.parametrize("held, code", [([], ND.WITHHELD_CCY_MISSING), (["USD", "EUR"], ND.WITHHELD_CCY_CONFLICT)])
def test_幣別_持倉沒填或互相矛盾_不默認幣別(held, code):
    out = ND.rows_from_chain_dividends("ZZ01", _div(_tcb_items(("2026/09/01", "2026/09/03", "", 0.05, "美元"))),
                                       holding_ccys=held, now=NOW)
    assert out["rows"] == [] and out["withheld"] == code


def test_div_kind恆為unknown_pay_date恆為空():
    out = _rows(_div(_tcb_items(("2026/09/01", "2026/09/03", "2026/09/10", 0.05, "美元"),
                                ("2026/08/01", "2026/08/03", "2026/08/10", 0.04, "美元"))))
    assert {r["div_kind"] for r in out["rows"]} == {"unknown"} and {r["pay_date"] for r in out["rows"]} == {None}


def test_fetched_at取L1記下的值_缺了不以當下時間補():
    out = _rows(_div(_tcb_items(("2026/09/01", "2026/09/03", "", 0.05, "美元"), at=None)))
    assert out["rows"] == [] and out["withheld"] == ND.WITHHELD_FETCHED_AT_MISSING


# ── 空結果與失敗 ──

def test_空清單_確實沒有配息_而且每個來源都認得這個代碼_settled():
    out = _rows(_div([], outcome=FO.DIV_OUTCOME_NONE, evidenced=True))
    assert out["rows"] == [] and out["error"] is None and out["withheld"] is None and out["settled"] is True


def test_必修3_空清單但沒有認得代碼的證據_不當成確定不配息():
    out = _rows(_div([], outcome=FO.DIV_OUTCOME_NONE, evidenced=False))
    assert out["rows"] == [] and out["settled"] is False
    assert out["withheld"] == ND.WITHHELD_DIV_OUTCOME_UNDETERMINED
    assert any("認得這個代碼" in line for line in out["skipped"])


def test_空清單_全部來源失敗_進error_逐來源原文():
    sources = [{"source": "tcb_moneydj", "status": "failed", "detail": "HTTP 503", "page_type": "yp010001"}]
    out = _rows(_div([], outcome=FO.DIV_OUTCOME_FAILED, sources=sources))
    assert "HTTP 503" in out["error"] and out["settled"] is False


@pytest.mark.parametrize("outcome", [FO.DIV_OUTCOME_UNDETERMINED, None])
def test_空清單_分辨不出_不當成沒有配息(outcome):
    div = _div([], outcome=outcome) if outcome else {"items": [], "outcome": None, "error": None}
    out = _rows(div)
    assert out["withheld"] == ND.WITHHELD_DIV_OUTCOME_UNDETERMINED and out["settled"] is False


def test_供列的來源自報失敗_列照寫但不算settled():
    sources = [{"source": "tcb_moneydj", "parser": S.DIV_PARSER_TCB, "status": S.DIV_STATUS_FAILED,
                "dropped": dict(_NO_DROP)}]
    out = _rows(_div(_tcb_items(("2026/09/01", "2026/09/03", "", 0.05, "美元")), sources=sources))
    assert len(out["rows"]) == 1 and out["settled"] is False


def test_部分列不收_其餘照寫但不算settled():
    items = _tcb_items(("2026/09/01", "2026/09/03", "", 0.05, "美元"), ("2026/08/01", "2026/8/3", "", 0.05, "美元"))
    out = _rows(_div(items))
    assert len(out["rows"]) == 1 and out["settled"] is False and out["skipped_rows"] == 1


def test_A鏈回的full_key與代碼對照不同_配息不寫():
    res = {"full_key": "OTHER", "dividends": [], "series": None}
    div = ND._div_from_chain(res, "ZZ01")
    assert div["error"] and "OTHER" in div["error"]


# ═══════════════════════ hld 接線：HLD-3、HLD-8 接上真資料 ═══════════════════════

from ui_v2.hld import fixtures as HF, live as HL, logic as HG  # noqa: E402

_WINDOW = (HF.WINDOW_START, HF.WINDOW_END)
_DECL = {"USD": "美元", "EUR": "歐元"}


def _settings_rows(window=None):
    """L2 `load_user_settings` 的形狀；`window` 給了就存成 `hld_window_start`／`hld_window_end`（存檔區間）。"""
    rows = {}
    if window:
        for key, value in zip(("hld_window_start", "hld_window_end"), window):
            rows[key] = {"setting_key": key, "setting_value": value, "value_kind": "date",
                         "updated_at": "2026-09-30T00:00:00+00:00"}
    return {"rows": rows, "broken_keys": [], "tab_missing": False, "bad_rows": []}


# ~~`saved_window=None`~~ → 客戶 2026-10-16 裁示第 2 點（有意識的更正，不是漏刪）：正式模式不再收「套用」的區間，
# 原本靠 `_model(applied_window=_WINDOW)` 帶區間的測試改成把同一段區間存進設定（計算結果不變）。
def _hld_inputs(div_by_code, *, saved_window=_WINDOW):
    holding = HF.holdings()
    for h in holding:
        if h["policy_id"] == "DIRECT":
            h["policy_id"] = "P-001"
    tables = {"holding": holding, "policy": [p for p in HF.policies() if p["policy_id"] != "DIRECT"],
              "direct": [], "skipped_tabs": []}
    codes = sorted({h["fund_code"] for h in holding})
    navs = HF.navs()
    nav_table = {"rows": navs, "errors": {}, "withheld": {}, "skipped": {},
                 "fetched": {c: sum(1 for r in navs if r["fund_code"] == c) for c in codes},
                 "skipped_rows": {c: 0 for c in codes},
                 "provenance": {c: {"source": "MoneyDJ:x", "fetched_at": "2026-09-19T02:00:00+00:00",
                                    "ccy_source": "holding_user_input", "cache_fallback": False, "stale": None}
                                for c in codes}}
    keys = [{"input": h["fund_code"], "ok": True, "full_key": h["fund_code"], "portal": "",
             "parsed_code": h["fund_code"], "mapping_hit": True, "error": None} for h in holding]
    acc = ND._empty_div_acc()
    ccy = {h["fund_code"]: h["ccy"] for h in holding}
    for code in codes:
        ND._merge_div(code, ND.rows_from_chain_dividends(code, div_by_code[code], holding_ccys=[ccy[code]], now=NOW),
                      acc)
    return dict(holding_tables=tables, holding_error=None,
                settings=_settings_rows(saved_window),
                settings_error=None, key_results=keys, nav_table=nav_table, direct_policy_id="DIRECT",
                policy_tab_source="x", direct_sources=frozenset({"x"}), empty_without_reason="空",
                nav_unavailable_withheld=(), dividend_gate_open=False, mask=lambda t: t.replace("SECRET", "***"),
                dividend_table=acc), holding


def _tcb_for(code, ccy, rows):
    return _div(_tcb_items(*[("2026/01/01", ex.replace("-", "/"), "", amt, _DECL[ccy]) for ex, amt in rows]))


# ~~`_TODAY = dt.date(2026, 10, 1)`~~ → 2026-10-13 客戶裁示（狀態更新，不是漏刪）：淨值日距今**大於** 10 天 → 資料未備、不再照算。
# 假資料最後一筆淨值是 2026-09-18，10-01 已是 13 天 ⇒ 配息佔淨值比（分母是區間末淨值）會變成資料未備，
# 本檔要驗的配息語意被蓋掉。改用恰 10 天（照用）的 9/28；斷言一字未放寬。
_TODAY = dt.date(2026, 9, 28)


def _model(loaded):
    """真的走 `live.build_live_model`（含覆蓋期間閘門），與正式頁面同一條路。
    客戶 2026-10-16 裁示第 2 點起不帶 `applied_window`（正式結果只讀已存設定；區間由 `_hld_inputs(saved_window=)` 存進去）。"""
    return HL.build_live_model(loaded["dataset"], today=_TODAY, **loaded["live_args"])


def _hld3(model, code):
    block = next(b for b in model["blocks"] if b["code"] == "HLD-3")
    group = next(g for g in block["fund_groups"] if g["_fund_code"] == code)
    return {v["label"]: v for v in group["main_values"]}


def _hld8_principal(model, code):
    block = next(b for b in model["blocks"] if b["code"] == "HLD-8")
    return next(r for r in block["_rows"] if r["_fund_code"] == code)["principal"]


def _metrics(loaded, holding, code):
    fund = next(h for h in holding if h["fund_code"] == code)
    return HG.fund_metrics(loaded["dataset"], fund, _WINDOW)


def test_hld_每一檔都確定_接上真資料_HLD3合計與HLD8本金佔比():
    # 區間 2026-01-01 起；每一檔有配息列的最舊一筆都早於它（覆蓋期間涵蓋整個區間），閘門不擋
    divs = {"AAAA": _tcb_for("AAAA", "USD", [("2025-08-15", 0.1010), ("2026-01-15", 0.1059), ("2026-09-16", 0.1059)]),
            "BBBB": _div([], outcome=FO.DIV_OUTCOME_NONE, evidenced=True),
            "CCCC": _tcb_for("CCCC", "EUR", [("2025-10-10", 0.1400), ("2026-02-10", 0.1492)])}
    kw, holding = _hld_inputs(divs)
    loaded = HL.assemble_live_load(**kw)
    ds = loaded["dataset"]
    assert ds["pending_tables"] == ["fund_profile"]
    assert {r["fund_code"] for r in ds["dividend"]} == {"AAAA", "CCCC"}
    model = _model(loaded)
    a = _hld3(model, "AAAA")
    units_a = next(h["units_shares"] for h in holding if h["fund_code"] == "AAAA")
    assert a["期間配息合計"]["_state"] == HG.STATE_OK
    assert a["期間配息合計"]["_raw"] == pytest.approx((0.1059 + 0.1059) * units_a)   # 2025-08-15 在區間外
    assert _hld8_principal(model, "AAAA")["text"] == HG.not_applicable_text("配息類別未知")
    assert _hld3(model, "BBBB")["期間配息合計"]["text"] == HG.not_applicable_text("區間內無配息")


# ~~test_hld_有一檔分辨不出_整張配息表照舊列為尚未接上_不說成區間內無配息~~ → 客戶 2026-10-16 裁示第 5 點
# （有意識的更正，不是漏刪）：改為只有分辨不出的那一檔資料未備，其他檔照常。舊斷言（`pending_tables` 含 dividend、
# `dividend` 為空）在寫下當時是「全有或全無」規則下的正確期望。
def test_hld_有一檔分辨不出_只有那一檔資料未備_其他檔照常_不說成區間內無配息():
    divs = {"AAAA": _tcb_for("AAAA", "USD", [("2025-12-15", 0.1000), ("2026-01-15", 0.1059)]),
            "BBBB": _div([], outcome=FO.DIV_OUTCOME_UNDETERMINED),
            "CCCC": _tcb_for("CCCC", "EUR", [("2025-12-10", 0.1400), ("2026-02-10", 0.1492)])}
    kw, holding = _hld_inputs(divs)
    loaded = HL.assemble_live_load(**kw)
    assert loaded["dataset"]["pending_tables"] == ["fund_profile"]
    assert loaded["dataset"]["dividend_not_ready"] == ["BBBB"]
    assert {r["fund_code"] for r in loaded["dataset"]["dividend"]} == {"AAAA", "CCCC"}
    b = _metrics(loaded, holding, "BBBB")
    assert b["期間配息合計"]["_state"] == HG.STATE_MISSING
    model = _model(loaded)
    assert _hld3(model, "BBBB")["期間配息合計"]["text"] == HG.ND_TEXT
    assert _hld3(model, "BBBB")["期間配息合計"]["text"] != HG.not_applicable_text("區間內無配息")
    for code in ("AAAA", "CCCC"):
        assert _hld3(model, code)["期間配息合計"]["_state"] == HG.STATE_OK, code


def test_hld_配息取數失敗_走既有的取數失敗_原文經遮蔽():
    divs = {"AAAA": {"items": None, "outcome": None, "error": "上游逾時 SECRET"},
            "BBBB": _div([], outcome=FO.DIV_OUTCOME_NONE, evidenced=True),
            "CCCC": _tcb_for("CCCC", "EUR", [("2026-02-10", 0.1492)])}
    kw, holding = _hld_inputs(divs)
    loaded = HL.assemble_live_load(**kw)
    assert loaded["dataset"]["fund_errors"]["dividend"] == {"AAAA": "上游逾時 ***"}
    assert loaded["dataset"]["pending_tables"] == ["fund_profile"]
    assert _metrics(loaded, holding, "AAAA")["期間配息合計"]["_state"] == HG.STATE_ERROR


def test_hld_配息表出現持倉沒有的代碼_raise():
    divs = {c: _div([], outcome=FO.DIV_OUTCOME_NONE, evidenced=True) for c in ("AAAA", "BBBB", "CCCC")}
    kw, _holding = _hld_inputs(divs)
    kw = copy.deepcopy(kw)
    kw["dividend_table"]["settled"]["ZZZZ"] = True
    with pytest.raises(ValueError):
        HL.assemble_live_load(**kw)


# ═══════════════════════ 稽核 11／12 回修 ═══════════════════════

def _rows_page(n, *, amount="0.05", extra=""):
    """合庫配息頁：表頭 ＋ n 列月配（2020-01 起往後），每列 7 格。"""
    trs = []
    for i in range(n):
        y, m = 2020 + i // 12, i % 12 + 1
        trs.append(f"<tr><td>{y}/{m:02d}/01</td><td>{y}/{m:02d}/03</td><td>{y}/{m:02d}/10</td><td>配息</td>"
                   f"<td>{amount}</td><td>6.1</td><td>美元</td></tr>")
    return f"<table>{_HDR}{''.join(trs)}{extra}</table>"


def _real_tcb_through_chain(monkeypatch, page, *, ccy="USD"):
    """端到端：A 鏈（其餘來源走替身）＋**真的**合庫配息解析器 → B 線。"""
    code, sc = H.full_success_scenario()
    sc = {k: v for k, v in sc.items() if k != "_src_tcb_div"}
    H.install(monkeypatch, sc)
    monkeypatch.setattr(FO, "_src_tcb_div", S._src_tcb_div)
    monkeypatch.setattr(S, "fetch_url_with_retry", lambda *a, **k: _Resp(page))
    # 真解析器記的取得時間是**真的當下**；判「未來」用的 now 也要是真的當下，否則會被當成未來時間
    out = _quiet(ND.build_nav_dividend_tables, _funds(code, ccy), now=dt.datetime.now(dt.timezone.utc))
    return code, out["dividend"]


def test_必修1a_真解析器_70列只讀59列_回報truncated_B線不算settled(monkeypatch):
    monkeypatch.setattr(S, "fetch_url_with_retry", lambda *a, **k: _Resp(_rows_page(70)))
    divs = _quiet(S._src_tcb_div, "TLZF9")
    assert len(divs) == 59                                        # 回傳值與改動前相同（只讀前 59 列）
    assert divs.div_fetch["dropped"] == {"truncated": 11, "filtered": 0, "other_tables": 0}
    code, tbl = _real_tcb_through_chain(monkeypatch, _rows_page(70))
    assert len(tbl["rows"]) == 59 and tbl["settled"] == {code: False}


@pytest.mark.parametrize("bad_row, why", [
    ("<tr><td>2026/09/01</td><td>2026/09/03</td><td>2026/09/10</td><td>配息</td><td>1500</td><td>6.1</td>"
     "<td>美元</td></tr>", "金額大於 1000"),
    ("<tr><td>20260901</td><td>2026/09/03</td><td>2026/09/10</td><td>配息</td><td>0.05</td><td>6.1</td>"
     "<td>美元</td></tr>", "第一欄沒有「/」"),
    ("<tr><td>2026/09/01</td><td>0.05</td></tr>", "欄數不足 6"),
])
def test_必修1a_被過濾掉的列_回報filtered_B線不算settled(monkeypatch, bad_row, why):
    page = _rows_page(3, extra=bad_row)
    monkeypatch.setattr(S, "fetch_url_with_retry", lambda *a, **k: _Resp(page))
    divs = _quiet(S._src_tcb_div, "TLZF9")
    assert len(divs) == 3 and divs.div_fetch["dropped"]["filtered"] == 1, why
    code, tbl = _real_tcb_through_chain(monkeypatch, page)
    assert tbl["settled"] == {code: False}, why


def test_必修1a_第一張表之後的其他配息表_回報other_tables(monkeypatch):
    page = _rows_page(2) + _rows_page(4)
    monkeypatch.setattr(S, "fetch_url_with_retry", lambda *a, **k: _Resp(page))
    divs = _quiet(S._src_tcb_div, "TLZF9")
    assert len(divs) == 2 and divs.div_fetch["dropped"]["other_tables"] == 4


def test_必修1a_沒有丟列_對照組_settled(monkeypatch):
    monkeypatch.setattr(S, "fetch_url_with_retry", lambda *a, **k: _Resp(_rows_page(3)))
    divs = _quiet(S._src_tcb_div, "TLZF9")
    assert divs.div_fetch["dropped"] == {"truncated": 0, "filtered": 0, "other_tables": 0}
    code, tbl = _real_tcb_through_chain(monkeypatch, _rows_page(3))
    assert tbl["settled"] == {code: True}


def test_必修1a_丟列算不出來_也不算settled():
    out = _rows(_div(_tcb_items(("2026/09/01", "2026/09/03", "", 0.05, "美元")),
                     sources=[{"source": "tcb_moneydj", "parser": S.DIV_PARSER_TCB, "status": S.DIV_STATUS_ROWS,
                               "dropped": {"truncated": None, "filtered": None, "other_tables": None}}]))
    assert len(out["rows"]) == 1 and out["settled"] is False


def test_必修1a_FundClear_被金額條件丟掉的項_回報filtered(monkeypatch):
    payload = {"Data": [{"DividendAmount": 0.05, "ExDividendDate": "2026-09-01"},
                        {"DividendAmount": 0, "ExDividendDate": "2026-08-01"}]}
    monkeypatch.setattr(S, "fetch_url_with_retry", lambda *a, **k: _Resp(payload=payload))
    divs = _quiet(S._src_fundclear_div, "ZZ01")
    assert len(divs) == 1 and divs.div_fetch["dropped"] == {"filtered": 1}


def test_必修2_真解析器_表頭第五格是年化配息率_pending_0列(monkeypatch):
    hdr = ("<tr><th>配息基準日</th><th>除息日</th><th>發放日</th><th>類別</th>"
           "<th>年化配息率</th><th>每單位配息額</th><th>幣別</th></tr>")
    row = ("<tr><td>2026/09/01</td><td>2026/09/03</td><td>2026/09/10</td><td>配息</td>"
           "<td>5.1</td><td>0.05</td><td>美元</td></tr>")
    code, tbl = _real_tcb_through_chain(monkeypatch, f"<table>{hdr}{row}</table>")
    assert tbl["rows"] == [] and tbl["pending"] == {code: ND.PENDING_DIV_EX_DATE_UNVERIFIED}


def test_必修2_真解析器_表頭格數與資料列格數不一致_pending_0列(monkeypatch):
    row = ("<tr><td>2026/09/01</td><td>2026/09/03</td><td>2026/09/10</td><td>配息</td>"
           "<td>0.05</td><td>6.1</td><td>美元</td><td>多一格</td></tr>")
    code, tbl = _real_tcb_through_chain(monkeypatch, f"<table>{_HDR}{row}</table>")
    assert tbl["rows"] == [] and tbl["pending"] == {code: ND.PENDING_DIV_EX_DATE_UNVERIFIED}


@pytest.mark.parametrize("field", ["Amount", "amount", ""])
def test_必修2_FundClear金額取自語意不明的欄名_pending(field):
    out = _rows(_div([_fc_item("ExDividendDate", amount_field=field)]))
    assert out["rows"] == [] and out["pending"] == ND.PENDING_DIV_EX_DATE_UNVERIFIED


def test_必修2_FundClear_真解析器記下金額欄名(monkeypatch):
    payload = {"Data": [{"DividendAmount": 0.05, "ExDividendDate": "2026-09-01"},
                        {"Amount": 0.06, "ExDividendDate": "2026-08-01"}]}
    monkeypatch.setattr(S, "fetch_url_with_retry", lambda *a, **k: _Resp(payload=payload))
    divs = _quiet(S._src_fundclear_div, "ZZ01")
    assert [d[S.DIV_PROVENANCE_KEY]["amount_field"] for d in divs] == ["DividendAmount", "Amount"]


def test_必修2_鉅亨金額取自amount_pending():
    item = {"date": "2026-09-01", "amount": 0.05, "yield_pct": 0,
            S.DIV_PROVENANCE_KEY: {"parser": S.DIV_PARSER_CNYES, "date_field": "exDate", "amount_field": "amount",
                                   "fetched_at": L1_AT}}
    out = _rows(_div([item]))
    assert out["rows"] == [] and out["pending"] == ND.PENDING_DIV_EX_DATE_UNVERIFIED


def _evidenced_no_div(code, sc, cnyes_code):
    # FundClear 淨值只回 5 筆（低於 20 的門檻）→ 瀑布接著打鉅亨；合庫基本資料認得本代碼
    return dict(sc, _src_fundclear_nav=H.series(5, attrs={"source": "FundClear:GetFundNAV", "fetched_at": "x"}),
                _src_cnyes_nav=H.series(300, start="2025-01-06",
                                        attrs={"source": f"Cnyes:fund.api:v2/funds/{cnyes_code}/nav",
                                               "fetched_at": "2026-02-01T00:00:00+00:00"}))


def test_必修3_三個來源同一輪都認得這個代碼_才當成確定不配息(monkeypatch):
    code, sc = _no_div_scenario()
    H.install(monkeypatch, _evidenced_no_div(code, sc, code))
    out = _quiet(FO.fetch_fund_from_moneydj_url, code)[FO.DIVIDENDS_OUTCOME_KEY]
    assert out["outcome"] == FO.DIV_OUTCOME_NONE and out["none_evidenced"] is True
    assert all(s["code_recognized"] for s in out["sources"])
    tbl = _quiet(ND.build_nav_dividend_tables, _funds(code), now=NOW)["dividend"]
    assert tbl["settled"] == {code: True} and tbl["rows"] == []


def test_必修3_鉅亨淨值換了候選代碼_不算認得本代碼(monkeypatch):
    code, sc = _no_div_scenario()
    H.install(monkeypatch, _evidenced_no_div(code, sc, "OTHER123"))
    out = _quiet(FO.fetch_fund_from_moneydj_url, code)[FO.DIVIDENDS_OUTCOME_KEY]
    assert out["outcome"] == FO.DIV_OUTCOME_NONE and out["none_evidenced"] is False
    tbl = _quiet(ND.build_nav_dividend_tables, _funds(code), now=NOW)["dividend"]
    assert tbl["settled"] == {code: False}


def test_必修4_M11_真解析器端到端_表頭第二格是配息基準日_pending_0列(monkeypatch):
    hdr = ("<tr><th>除息日</th><th>配息基準日</th><th>發放日</th><th>類別</th>"
           "<th>每單位配息額</th><th>年化配息率</th><th>幣別</th></tr>")
    row = ("<tr><td>2026/09/03</td><td>2026/09/01</td><td>2026/09/10</td><td>配息</td>"
           "<td>0.05</td><td>6.1</td><td>美元</td></tr>")
    code, tbl = _real_tcb_through_chain(monkeypatch, f"<table>{hdr}{row}</table>")
    assert tbl["rows"] == [] and tbl["pending"] == {code: ND.PENDING_DIV_EX_DATE_UNVERIFIED}
    assert tbl["settled"] == {code: False}


def test_必修4_真解析器端到端_正常頁面_照寫_對照組(monkeypatch):
    code, tbl = _real_tcb_through_chain(monkeypatch, _rows_page(3))
    assert [r["ex_date"] for r in tbl["rows"]] == ["2020-01-03", "2020-02-03", "2020-03-03"]


def test_必修4_M13_legacy段_沒有配息一律undetermined(monkeypatch):
    code, sc = H.scenarios()["S3_all_fail"]
    sc = dict(sc, _src_tcb_div=_empty(S.DIV_PARSER_TCB), _src_fundclear_div=_empty(S.DIV_PARSER_FUNDCLEAR),
              _src_cnyes_div=_empty(S.DIV_PARSER_CNYES))
    H.install(monkeypatch, sc)
    out = _quiet(FO.fetch_fund_from_moneydj_url, code)[FO.DIVIDENDS_OUTCOME_KEY]
    assert out["legacy_inline_parse"] is True
    assert [s["status"] for s in out["sources"]] == [S.DIV_STATUS_EMPTY] * 3
    assert out["outcome"] == FO.DIV_OUTCOME_UNDETERMINED     # 三個來源都回空，但 legacy 段另跑了沒有狀態的解析


# ~~test_必修1b_區間起點早於最舊一筆除息日_整張退回尚未接上_不說區間內無配息~~ → 客戶 2026-10-16 裁示第 5 點
# （有意識的更正，不是漏刪）：閘門改為逐檔；區間改取已存設定（第 2 點，`_gate_dividend_coverage` 不再收區間參數）。
def test_必修1b_區間起點早於最舊一筆除息日_只有那幾檔退回資料未備_不說區間內無配息():
    divs = {"AAAA": _tcb_for("AAAA", "USD", [("2026-03-15", 0.1059)]),
            "BBBB": _div([], outcome=FO.DIV_OUTCOME_NONE, evidenced=True),
            "CCCC": _tcb_for("CCCC", "EUR", [("2026-02-10", 0.1492)])}
    kw, holding = _hld_inputs(divs)
    loaded = HL.assemble_live_load(**kw)
    assert loaded["live_args"]["dividend_coverage"] == {"AAAA": "2026-03-15", "CCCC": "2026-02-10"}
    # 存檔區間 2026-01-01 起 → 早於 AAAA／CCCC 的最舊一筆：只有那兩檔進資料未備、列被拿掉
    gated = HL._gate_dividend_coverage(loaded["dataset"], loaded["live_args"]["dividend_coverage"])
    assert gated["dividend"] == [] and gated["dividend_not_ready"] == ["AAAA", "CCCC"]
    assert gated["pending_tables"] == ["fund_profile"]
    for code in ("AAAA", "CCCC"):
        m = HG.fund_metrics(gated, next(h for h in holding if h["fund_code"] == code), _WINDOW)
        assert m["期間配息合計"]["_state"] == HG.STATE_MISSING
        assert m["期間配息合計"]["text"] != HG.not_applicable_text("區間內無配息")
    # BBBB 沒有任何配息列（L2 確定不配息），不在覆蓋期間的射程內：照舊「區間內無配息」
    m = HG.fund_metrics(gated, next(h for h in holding if h["fund_code"] == "BBBB"), _WINDOW)
    assert m["期間配息合計"]["text"] == HG.not_applicable_text("區間內無配息")
    # 只有一檔早於覆蓋期間（區間 2026-03-01 起：早於 AAAA 的 03-15、晚於 CCCC 的 02-10）→ 只標 AAAA
    kw_mid, _h = _hld_inputs(divs, saved_window=("2026-03-01", HF.WINDOW_END))
    mid = HL.assemble_live_load(**kw_mid)
    gated_mid = HL._gate_dividend_coverage(mid["dataset"], mid["live_args"]["dividend_coverage"])
    assert gated_mid["dividend_not_ready"] == ["AAAA"]
    assert {r["fund_code"] for r in gated_mid["dividend"]} == {"CCCC"}
    # 區間起點不早於任何一檔的最舊一筆 → 照接（原樣交回）
    kw_late, _h = _hld_inputs(divs, saved_window=("2026-03-15", HF.WINDOW_END))
    late = HL.assemble_live_load(**kw_late)
    assert HL._gate_dividend_coverage(late["dataset"], late["live_args"]["dividend_coverage"]) is late["dataset"]
    assert loaded["dataset"]["dividend"] and loaded["dataset"]["pending_tables"] == ["fund_profile"]   # 輸入沒被改
    assert loaded["dataset"]["dividend_not_ready"] == []


def _late_coverage_divs():
    return {"AAAA": _tcb_for("AAAA", "USD", [("2026-03-15", 0.1059)]),
            "BBBB": _div([], outcome=FO.DIV_OUTCOME_NONE, evidenced=True),
            "CCCC": _tcb_for("CCCC", "EUR", [("2026-02-10", 0.1492)])}


# ~~test_必修1b_build_live_model_按套用的區間早於覆蓋期間_HLD3顯示資料未備~~ → 客戶 2026-10-16 裁示第 2 點
# （有意識的更正，不是漏刪）：正式模式不再收套用的區間，「按套用」這一條路已不存在；同一個閘門由下一條
# `test_N12_…`（存檔區間）照樣覆蓋。原條在寫下當時為真。


def test_N12_沒按套用_走存檔區間_閘門照樣觸發():
    kw, _holding = _hld_inputs(_late_coverage_divs(), saved_window=_WINDOW)
    loaded = HL.assemble_live_load(**kw)
    model = _model(loaded)             # 預設載入路徑：區間取自存檔設定
    assert model["_window"] == _WINDOW
    # ~~三檔都資料未備~~ → 客戶 2026-10-16 裁示第 5 點（有意識的更正，不是漏刪）：只有早於覆蓋期間的兩檔；
    # BBBB 沒有配息列（確定不配息），照舊「區間內無配息」。
    for code in ("AAAA", "CCCC"):
        total = _hld3(model, code)["期間配息合計"]
        assert total["_state"] == HG.STATE_MISSING and total["text"] == HG.ND_TEXT, code
    assert _hld3(model, "BBBB")["期間配息合計"]["text"] == HG.not_applicable_text("區間內無配息")
    # 對照組：存檔區間落在覆蓋期間內 → 照接
    kw2, _h2 = _hld_inputs(_late_coverage_divs(), saved_window=("2026-03-15", HF.WINDOW_END))
    ok = _model(HL.assemble_live_load(**kw2))
    assert _hld3(ok, "AAAA")["期間配息合計"]["_state"] == HG.STATE_OK


def test_HLD3_配息佔淨值比_值等於區間內每單位配息加總除以區間末淨值():
    # 每一檔有配息列的最舊一筆都早於區間起點 2026-01-01（覆蓋期間涵蓋整個區間）
    divs = {"AAAA": _tcb_for("AAAA", "USD", [("2025-12-15", 0.1000), ("2026-01-15", 0.1059), ("2026-09-16", 0.1059)]),
            "BBBB": _div([], outcome=FO.DIV_OUTCOME_NONE, evidenced=True),
            "CCCC": _tcb_for("CCCC", "EUR", [("2025-12-10", 0.1400), ("2026-01-02", 0.1492)])}
    kw, holding = _hld_inputs(divs)
    loaded = HL.assemble_live_load(**kw)
    a = _hld3(_model(loaded), "AAAA")
    navs = [r for r in HF.navs() if r["fund_code"] == "AAAA" and _WINDOW[0] <= r["nav_date"] <= _WINDOW[1]]
    last = sorted(navs, key=lambda r: r["nav_date"])[-1]["nav_orig_ccy"]
    assert a["配息佔淨值比"]["_state"] == HG.STATE_OK
    assert a["配息佔淨值比"]["_raw"] == pytest.approx((0.1059 + 0.1059) / last * 100.0)


def test_N2_coverage_start取最舊一筆_不是最新一筆():
    out = _rows(_div(_tcb_items(("2026/09/01", "2026/09/03", "", 0.05, "美元"),
                                ("2025/03/01", "2025/03/03", "", 0.05, "美元"),
                                ("2026/01/01", "2026/01/03", "", 0.05, "美元"))))
    assert out["provenance"]["coverage_start"] == "2025-03-03"
    divs = {"AAAA": _tcb_for("AAAA", "USD", [("2026-09-16", 0.1059), ("2025-08-15", 0.1010), ("2026-01-15", 0.1059)]),
            "BBBB": _div([], outcome=FO.DIV_OUTCOME_NONE, evidenced=True),
            "CCCC": _tcb_for("CCCC", "EUR", [("2026-02-10", 0.1492), ("2025-10-10", 0.1400)])}
    kw, _holding = _hld_inputs(divs)
    loaded = HL.assemble_live_load(**kw)
    assert loaded["live_args"]["dividend_coverage"] == {"AAAA": "2025-08-15", "CCCC": "2025-10-10"}
    assert _hld3(_model(loaded), "AAAA")["期間配息合計"]["_state"] == HG.STATE_OK   # 取最新一筆的話會被擋


def test_N8_空序列不算認得代碼的證據():
    import pandas as pd
    seen = {}
    FO._div_code_evidence(seen, "FundClear", pd.Series(dtype=float), "GetFundNAV 淨值")
    FO._div_code_evidence(seen, "cnyes", pd.Series(dtype=float, name="x"), "v2/funds 淨值", cnyes_code="ZZ01")
    FO._div_code_evidence(seen, "tcb_moneydj", {"fund_name": ""}, "MoneyDJ 基本資料頁")
    assert seen == {}
    FO._div_code_evidence(seen, "FundClear", H.series(3, attrs={"source": "FundClear:GetFundNAV"}), "GetFundNAV 淨值")
    assert list(seen) == ["FundClear"]                     # 對照組：非空才算


def test_N8_A鏈_FundClear淨值回空_就沒有FundClear的證據(monkeypatch):
    code, sc = _no_div_scenario()
    sc = _evidenced_no_div(code, sc, code)
    sc = dict(sc, _src_fundclear_nav=H.series(0), _src_fundclear_meta={})
    H.install(monkeypatch, sc)
    out = _quiet(FO.fetch_fund_from_moneydj_url, code)[FO.DIVIDENDS_OUTCOME_KEY]
    fc = next(s for s in out["sources"] if s["source"] == "FundClear")
    assert fc["code_recognized"] == [] and out["none_evidenced"] is False


def test_記證據失敗_記一行log_不吞_不算證據(capsys):
    class Boom(dict):
        def get(self, *_a, **_k):
            raise RuntimeError("token=SECRET123")
    seen = {}
    FO._div_code_evidence(seen, "tcb_moneydj", Boom(), "MoneyDJ 基本資料頁")
    out = capsys.readouterr().out
    assert seen == {} and "div_code_evidence" in out and "RuntimeError" in out
    assert "SECRET123" not in out                           # 只印例外類別名，不印原文


def test_稽核小修_資料列開頭多一格th當列號_欄位錯一格_pending_0列(monkeypatch):
    row = ("<tr><th>1</th><td>2026/09/01</td><td>2026/09/03</td><td>2026/09/10</td><td>配息</td>"
           "<td>0.05</td><td>6.1</td><td>美元</td></tr>")
    page = f"<table>{_HDR}{row}</table>"
    monkeypatch.setattr(S, "fetch_url_with_retry", lambda *a, **k: _Resp(page))
    divs = _quiet(S._src_tcb_div, "TLZF9")
    # A 鏈回傳值不變：解析器照舊只讀 td（7 格）。但畫面上列號那一格佔了第 1 欄，
    # 「除息日」表頭底下其實是 2026/09/01（配息基準日），解析器卻把第 2 個 td（2026/09/03）當除息日。
    assert _strip_prov(divs) == [{"date": "2026/09/01", "ex_date": "2026/09/03", "pay_date": "2026/09/10",
                                  "amount": 0.05, "yield_pct": 6.1, "currency": "美元"}]
    prov = divs[0][S.DIV_PROVENANCE_KEY]
    # 取值讀 7 個 td ＝ 表頭 7 格，但這一列含 th → 對不上（稽核組 B 回修後改看兩個鍵）
    assert (prov["row_td_cells"], prov["row_th_cells"], prov["header_cells"]) == (7, 1, 7)
    assert "row_cells" not in prov                                  # th＋td 合計那一個鍵已拆掉，不留兩種數法
    code, tbl = _real_tcb_through_chain(monkeypatch, page)
    assert tbl["rows"] == [] and tbl["settled"] == {code: False}
    assert tbl["pending"] == {code: ND.PENDING_DIV_EX_DATE_UNVERIFIED}


# ═══════════════════════ 稽核組 B 回修：資料列含 th → 取值讀的 td 與表頭對不上 ═══════════════════════

def test_稽核B_8格表頭_資料列首格th加7個td_合計8對8_仍pending_0列(monkeypatch):
    hdr = _HDR.replace("</tr>", "<th>X</th></tr>")                 # 表頭 8 格
    row = ("<tr><th>2026/09/01</th><td>2026/09/03</td><td>2026/09/10</td><td>配息</td>"
           "<td>0.05</td><td>6.1</td><td>美元</td><td>美元</td></tr>")
    page = f"<table>{hdr}{row}</table>"
    monkeypatch.setattr(S, "fetch_url_with_retry", lambda *a, **k: _Resp(page))
    divs = _quiet(S._src_tcb_div, "TLZF9")
    # A 鏈回傳值不變：取值只讀 td → 整排左移一格（金額拿到年化配息率、除息日拿到發放日）
    assert _strip_prov(divs) == [{"date": "2026/09/03", "ex_date": "2026/09/10", "pay_date": "配息",
                                  "amount": 6.1, "yield_pct": 0, "currency": "美元"}]
    prov = divs[0][S.DIV_PROVENANCE_KEY]
    assert (prov["row_td_cells"], prov["row_th_cells"], prov["header_cells"]) == (7, 1, 8)
    code, tbl = _real_tcb_through_chain(monkeypatch, page)
    assert tbl["rows"] == [] and tbl["settled"] == {code: False}
    assert tbl["pending"] == {code: ND.PENDING_DIV_EX_DATE_UNVERIFIED}
    assert tbl["withheld"].get(code) is None


def test_稽核B_7格表頭_資料列首格th加6個td_原因是格式不符_不是幣別(monkeypatch):
    row = ("<tr><th>2026/09/01</th><td>2026/09/03</td><td>2026/09/10</td><td>配息</td>"
           "<td>0.05</td><td>6.1</td><td>美元</td></tr>")
    page = f"<table>{_HDR}{row}</table>"
    code, tbl = _real_tcb_through_chain(monkeypatch, page)
    assert tbl["rows"] == [] and tbl["settled"] == {code: False}
    assert tbl["pending"] == {code: ND.PENDING_DIV_EX_DATE_UNVERIFIED}
    assert tbl["withheld"].get(code) != ND.WITHHELD_CCY_NOT_SOURCE_REPORTED


def test_稽核B_正常頁_無th_td數等於表頭_照常寫出(monkeypatch):
    monkeypatch.setattr(S, "fetch_url_with_retry", lambda *a, **k: _Resp(_TCB_PAGE))
    prov = _quiet(S._src_tcb_div, "TLZF9")[0][S.DIV_PROVENANCE_KEY]
    assert (prov["row_td_cells"], prov["row_th_cells"], prov["header_cells"]) == (7, 0, 7)
    code, tbl = _real_tcb_through_chain(monkeypatch, _TCB_PAGE)
    assert [(r["ex_date"], r["div_per_unit_orig_ccy"], r["ccy"]) for r in tbl["rows"]] == [("2026-09-03", 0.05, "USD")]
    assert tbl["settled"] == {code: True} and tbl["pending"].get(code) is None


_OK_CELLS = {"row_td_cells": 7, "row_th_cells": 0, "header_cells": 7, "table_has_span": False}


@pytest.mark.parametrize("cells", [
    dict(_OK_CELLS, header_cells=8),                                    # td 數 ≠ 表頭
    dict(_OK_CELLS, row_th_cells=1),                                    # 含 th
    dict(_OK_CELLS, row_th_cells=1, header_cells=8),                    # 合計相符但含 th
    {"row_td_cells": 7, "header_cells": 7, "table_has_span": False},    # 缺 th 鍵 → fail closed
    {"row_cells": 7, "header_cells": 7, "table_has_span": False},       # 只有舊鍵 → fail closed
    dict(_OK_CELLS, row_td_cells=True, header_cells=1),                 # bool 不算 int
    dict(_OK_CELLS, table_has_span=True),                               # 稽核組 C：表內有合併儲存格
    {"row_td_cells": 7, "row_th_cells": 0, "header_cells": 7},          # 缺 table_has_span 鍵 → fail closed
    dict(_OK_CELLS, table_has_span=None),                               # 型別不對 → fail closed
    dict(_OK_CELLS, table_has_span=0),                                  # int 0 不是 bool → fail closed
    dict(_OK_CELLS, table_has_span="False"),                            # 字串不是 bool → fail closed
])
def test_稽核B_格數判定_fail_closed(cells):
    assert ND._tcb_cells_mismatch(cells) is True
    assert ND._tcb_cells_mismatch(dict(_OK_CELLS)) is False


# ═══════════════════════ 稽核組 C 回修：合併儲存格（colspan／rowspan）→ 格數相同也錯位 ═══════════════════════

_HDR_ANNUAL_COLSPAN2 = ("<tr><th>配息基準日</th><th>除息日</th><th>發放日</th><th>類別</th>"
                        "<th>每單位配息額</th><th colspan=\"2\">年化配息率</th><th>幣別</th></tr>")


def test_稽核C_重現1_年化配息率colspan2_資料列首格colspan2_pending_0列(monkeypatch):
    row = ("<tr><td colspan=\"2\">2026/09/01</td><td>2026/09/10</td><td>配息</td>"
           "<td>0.05</td><td>6.1</td><td>美元</td><td>美元</td></tr>")
    page = f"<table>{_HDR_ANNUAL_COLSPAN2}{row}</table>"
    monkeypatch.setattr(S, "fetch_url_with_retry", lambda *a, **k: _Resp(page))
    divs = _quiet(S._src_tcb_div, "TLZF9")
    assert (divs[0]["ex_date"], divs[0]["amount"]) == ("2026/09/10", 6.1)     # A 鏈取值不變（錯位照舊）
    prov = divs[0][S.DIV_PROVENANCE_KEY]
    assert (prov["header_cells"], prov["row_td_cells"], prov["row_th_cells"]) == (7, 7, 0)  # 格數條件擋不住
    assert prov["table_has_span"] is True
    code, tbl = _real_tcb_through_chain(monkeypatch, page)
    assert tbl["rows"] == [] and tbl["settled"] == {code: False}
    assert tbl["pending"] == {code: ND.PENDING_DIV_EX_DATE_UNVERIFIED}


def test_稽核C_重現2_上一列基準日rowspan2_下一列7格_pending_0列(monkeypatch):
    rows = ("<tr><td rowspan=\"2\">2026/09/01</td><td>2026/09/03</td><td>2026/09/10</td><td>配息</td>"
            "<td>0.05</td><td>6.1</td><td>美元</td></tr>"
            "<tr><td>2026/09/04</td><td>2026/09/11</td><td>配息</td>"
            "<td>0.06</td><td>6.2</td><td>美元</td><td>美元</td></tr>")
    page = f"<table>{_HDR}{rows}</table>"
    monkeypatch.setattr(S, "fetch_url_with_retry", lambda *a, **k: _Resp(page))
    divs = _quiet(S._src_tcb_div, "TLZF9")
    assert (divs[1]["ex_date"], divs[1]["amount"]) == ("2026/09/11", 6.2)     # 第二列錯位（取值不變）
    assert [d[S.DIV_PROVENANCE_KEY]["table_has_span"] for d in divs] == [True, True]
    code, tbl = _real_tcb_through_chain(monkeypatch, page)
    assert tbl["rows"] == [] and tbl["settled"] == {code: False}
    assert tbl["pending"] == {code: ND.PENDING_DIV_EX_DATE_UNVERIFIED}


@pytest.mark.parametrize("span_attr", ['colspan="1"', 'rowspan="1"', 'colspan="1" rowspan=" 1 "'])
def test_稽核C_span值為1_正常頁照常寫出(monkeypatch, span_attr):
    row = (f"<tr><td {span_attr}>2026/09/01</td><td>2026/09/03</td><td>2026/09/10</td><td>配息</td>"
           "<td>0.05</td><td>6.1</td><td>美元</td></tr>")
    hdr = _HDR.replace("<th>除息日</th>", f"<th {span_attr}>除息日</th>")
    page = f"<table>{hdr}{row}</table>"
    monkeypatch.setattr(S, "fetch_url_with_retry", lambda *a, **k: _Resp(page))
    assert _quiet(S._src_tcb_div, "TLZF9")[0][S.DIV_PROVENANCE_KEY]["table_has_span"] is False
    code, tbl = _real_tcb_through_chain(monkeypatch, page)
    assert [(r["ex_date"], r["div_per_unit_orig_ccy"], r["ccy"]) for r in tbl["rows"]] == [("2026-09-03", 0.05, "USD")]
    assert tbl["settled"] == {code: True}


@pytest.mark.parametrize("attr, expected", [
    ('colspan="2"', True), ('rowspan="3"', True), ('colspan="abc"', True), ('colspan=""', True),
    ('colspan="0"', True), ('colspan="1"', False), ("", False),
])
def test_稽核C_table_has_span_判定(attr, expected):
    from bs4 import BeautifulSoup
    tbl = BeautifulSoup(f"<table>{_HDR}<tr><td {attr}>x</td></tr></table>", "lxml").find("table")
    assert S._tcb_div_table_has_span(tbl) is expected
