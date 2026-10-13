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
        "<th>每單位配息</th><th>年化配息率</th><th>幣別</th></tr>")
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
    assert first["dividend"]["settled"] == second["dividend"]["settled"] == {code: True}
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

def _tcb_items(*rows, header=("配息基準日", "除息日", "發放日", "類別", "每單位配息", "年化配息率", "幣別"),
               at=L1_AT):
    items = [{"date": base, "ex_date": ex, "pay_date": pay, "amount": amt, "yield_pct": 6.0, "currency": ccy,
              S.DIV_PROVENANCE_KEY: {"parser": S.DIV_PARSER_TCB,
                                     "date_header": header[0] if len(header) > 0 else None,
                                     "ex_date_header": header[1] if len(header) > 1 else None,
                                     "pay_date_header": header[2] if len(header) > 2 else None,
                                     "currency_header": header[6] if len(header) > 6 else None,
                                     "page": "tcbbankfund.moneydj.com/funddj/yp/wb05.djhtm", "fetched_at": at}}
             for base, ex, pay, amt, ccy in rows]
    return S._div_result(items, S.DIV_PARSER_TCB, S.DIV_STATUS_ROWS)


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


def _div(items, outcome=FO.DIV_OUTCOME_ROWS, sources=None):
    if sources is None:
        sources = [{"source": "tcb_moneydj", "parser": S.DIV_PARSER_TCB, "status": S.DIV_STATUS_ROWS,
                    "detail": "", "page_type": "yp010001"}]
    return {"items": items, "outcome": {"outcome": outcome, "sources": sources, "legacy_inline_parse": False},
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
    ("配息基準日", "配息基準日", "發放日", "類別", "每單位配息", "年化配息率", "幣別"),   # 第二欄其實是配息基準日
    ("除息日", "配息基準日", "發放日", "類別", "每單位配息", "年化配息率", "幣別"),       # 欄位對調
    (),                                                                                    # 抓不到表頭
])
def test_日期語意_表頭第二格不是除息日_照實列pending_不寫列(header):
    out = _rows(_div(_tcb_items(("2026/09/01", "2026/09/03", "2026/09/10", 0.05, "美元"), header=header)))
    assert out["rows"] == [] and out["pending"] == ND.PENDING_DIV_EX_DATE_UNVERIFIED
    assert out["settled"] is False
    assert any("證明不了是除息日" in line for line in out["skipped"])


def _fc_item(field, value="2026-09-01", ccy="USD", ccy_field="Currency"):
    return {"date": value, "ex_date": value, "pay_date": value, "amount": 0.05, "yield_pct": 0, "currency": ccy,
            S.DIV_PROVENANCE_KEY: {"parser": S.DIV_PARSER_FUNDCLEAR, "date_field": field,
                                   "currency_field": ccy_field, "fetched_at": L1_AT}}


def test_日期語意_FundClear_只收ExDividendDate_退回Date的不收():
    ok = _rows(_div([_fc_item("ExDividendDate")],
                    sources=[{"parser": S.DIV_PARSER_FUNDCLEAR, "status": S.DIV_STATUS_ROWS}]))
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
            S.DIV_PROVENANCE_KEY: {"parser": S.DIV_PARSER_CNYES, "date_field": "exDate", "fetched_at": L1_AT}}
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
    header = ("配息基準日", "除息日", "發放日", "類別", "每單位配息", "年化配息率", "備註")
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

def test_空清單_確實沒有配息_settled():
    out = _rows(_div([], outcome=FO.DIV_OUTCOME_NONE))
    assert out["rows"] == [] and out["error"] is None and out["withheld"] is None and out["settled"] is True


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
    sources = [{"source": "tcb_moneydj", "parser": S.DIV_PARSER_TCB, "status": S.DIV_STATUS_FAILED}]
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


def _hld_inputs(div_by_code):
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
                 "skipped_rows": {c: 0 for c in codes}, "provenance": {}}
    keys = [{"input": h["fund_code"], "ok": True, "full_key": h["fund_code"], "portal": "",
             "parsed_code": h["fund_code"], "mapping_hit": True, "error": None} for h in holding]
    acc = ND._empty_div_acc()
    ccy = {h["fund_code"]: h["ccy"] for h in holding}
    for code in codes:
        ND._merge_div(code, ND.rows_from_chain_dividends(code, div_by_code[code], holding_ccys=[ccy[code]], now=NOW),
                      acc)
    return dict(holding_tables=tables, holding_error=None,
                settings={"rows": {}, "broken_keys": [], "tab_missing": False, "bad_rows": []},
                settings_error=None, key_results=keys, nav_table=nav_table, direct_policy_id="DIRECT",
                policy_tab_source="x", direct_sources=frozenset({"x"}), empty_without_reason="空",
                nav_unavailable_withheld=(), dividend_gate_open=False, mask=lambda t: t.replace("SECRET", "***"),
                dividend_table=acc), holding


def _tcb_for(code, ccy, rows):
    return _div(_tcb_items(*[("2026/01/01", ex.replace("-", "/"), "", amt, _DECL[ccy]) for ex, amt in rows]))


def _metrics(loaded, holding, code):
    fund = next(h for h in holding if h["fund_code"] == code)
    return HG.fund_metrics(loaded["dataset"], fund, _WINDOW)


def test_hld_每一檔都確定_接上真資料_HLD3合計與HLD8本金佔比():
    divs = {"AAAA": _tcb_for("AAAA", "USD", [("2025-08-15", 0.1010), ("2026-01-15", 0.1059), ("2026-09-16", 0.1059)]),
            "BBBB": _div([], outcome=FO.DIV_OUTCOME_NONE),
            "CCCC": _tcb_for("CCCC", "EUR", [("2026-02-10", 0.1492)])}
    kw, holding = _hld_inputs(divs)
    loaded = HL.assemble_live_load(**kw)
    ds = loaded["dataset"]
    assert ds["pending_tables"] == ["fund_profile"]
    assert {r["fund_code"] for r in ds["dividend"]} == {"AAAA", "CCCC"}
    a = _metrics(loaded, holding, "AAAA")
    units_a = next(h["units_shares"] for h in holding if h["fund_code"] == "AAAA")
    assert a["期間配息合計"]["_state"] == HG.STATE_OK
    assert a["期間配息合計"]["_raw"] == pytest.approx((0.1059 + 0.1059) * units_a)   # 2025-08-15 在區間外
    assert a["本金類配息佔比"]["text"] == HG.not_applicable_text("配息類別未知")
    b = _metrics(loaded, holding, "BBBB")
    assert b["期間配息合計"]["text"] == HG.not_applicable_text("區間內無配息")


def test_hld_有一檔分辨不出_整張配息表照舊列為尚未接上_不說成區間內無配息():
    divs = {"AAAA": _tcb_for("AAAA", "USD", [("2026-01-15", 0.1059)]),
            "BBBB": _div([], outcome=FO.DIV_OUTCOME_UNDETERMINED),
            "CCCC": _tcb_for("CCCC", "EUR", [("2026-02-10", 0.1492)])}
    kw, holding = _hld_inputs(divs)
    loaded = HL.assemble_live_load(**kw)
    assert loaded["dataset"]["pending_tables"] == ["fund_profile", "dividend"]
    assert loaded["dataset"]["dividend"] == []
    b = _metrics(loaded, holding, "BBBB")
    assert b["期間配息合計"]["_state"] == HG.STATE_MISSING


def test_hld_配息取數失敗_走既有的取數失敗_原文經遮蔽():
    divs = {"AAAA": {"items": None, "outcome": None, "error": "上游逾時 SECRET"},
            "BBBB": _div([], outcome=FO.DIV_OUTCOME_NONE),
            "CCCC": _tcb_for("CCCC", "EUR", [("2026-02-10", 0.1492)])}
    kw, holding = _hld_inputs(divs)
    loaded = HL.assemble_live_load(**kw)
    assert loaded["dataset"]["fund_errors"]["dividend"] == {"AAAA": "上游逾時 ***"}
    assert loaded["dataset"]["pending_tables"] == ["fund_profile"]
    assert _metrics(loaded, holding, "AAAA")["期間配息合計"]["_state"] == HG.STATE_ERROR


def test_hld_配息表出現持倉沒有的代碼_raise():
    divs = {c: _div([], outcome=FO.DIV_OUTCOME_NONE) for c in ("AAAA", "BBBB", "CCCC")}
    kw, _holding = _hld_inputs(divs)
    kw = copy.deepcopy(kw)
    kw["dividend_table"]["settled"]["ZZZZ"] = True
    with pytest.raises(ValueError):
        HL.assemble_live_load(**kw)
