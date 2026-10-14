# -*- coding: utf-8 -*-
"""C3a：`nav_dividend` 多吃「meta 頁自報幣別」（`declared_ccy` ＋ `declared_ccy_source`）的那一支（fast lane；不打網路）。

hld（持倉手填）路徑零變化由 `tests/test_nav_dividend_golden_c3a.py` 逐位元組證明；本檔只測 meta 那一支：
- `ccy_source` 是呼叫端給的出處字串（配息是 `<出處>_matches_source`，不是幣別值）；
- 使用者可見文案不出現「持倉」，改用暫定字面「來源自報（<來源>）」；
- 判斷規則與 hld 相同：序列／配息宣告的幣別與 meta 不同 → 扣下；配息沒宣告 → 那幾筆不寫；
- `holding_ccy` 與 `declared_ccy` 混用 → ValueError；
- `chain_fetch` 可注入、預設值不變。
"""

from __future__ import annotations

import datetime as dt
import json

import pandas as pd
import pytest

import _a_chain_stub as H
import repositories.fund.sources as S
from repositories.fund import fund_orchestration as FO
from services.v2_tables import nav_dividend as ND

NOW = dt.datetime(2026, 10, 1, 0, 0, tzinfo=dt.timezone.utc)
L1_AT = "2026-09-30T08:00:00+00:00"
META = "meta:MoneyDJ+TDCC"
META_TEXT = "來源自報（MoneyDJ+TDCC）"
_NO_DROP = {"truncated": 0, "filtered": 0, "other_tables": 0}


def _fc_item(day, ccy, *, ccy_field="Currency"):
    return {"date": day, "ex_date": day, "pay_date": day, "amount": 0.04, "yield_pct": 0, "currency": ccy,
            S.DIV_PROVENANCE_KEY: {"parser": S.DIV_PARSER_FUNDCLEAR, "date_field": "ExDividendDate",
                                   "currency_field": ccy_field, "amount_field": "DividendAmount",
                                   "fetched_at": L1_AT}}


def _outcome():
    return {"outcome": FO.DIV_OUTCOME_ROWS, "legacy_inline_parse": False, "none_evidenced": False,
            "sources": [{"source": "FundClear", "parser": S.DIV_PARSER_FUNDCLEAR, "status": S.DIV_STATUS_ROWS,
                         "detail": "", "page_type": "yp010000", "dropped": dict(_NO_DROP)}]}


def _res(code, *, series_attrs=None, items=None, n=10):
    attrs = {"source": "FundClear:GetFundNAV", "fetched_at": L1_AT}
    attrs.update(series_attrs or {})
    return {"full_key": code, "series": H.series(n, start="2026-08-03", attrs=attrs),
            "dividends": items if items is not None else [_fc_item("2026-08-05", "USD"), _fc_item("2026-09-05", "USD")],
            FO.DIVIDENDS_OUTCOME_KEY: _outcome(), "data_source": "FundClear",
            "chain_started_at": "2026-09-30T07:00:00+00:00"}


def _fetch_from(by_code, calls=None):
    """注入用的 `chain_fetch`：A 鏈之後的判讀（`_nav_from_chain`／`_div_from_chain`）全部是真的。"""
    def fetch(chain_code, full_key):
        if calls is not None:
            calls.append((chain_code, full_key))
        res = by_code[chain_code]
        series, error = ND._nav_from_chain(res, "yp010000", chain_code, full_key)
        return series, error, ND._div_from_chain(res, full_key)
    return fetch


def _meta_funds(code, ccy="USD", source=META):
    return [{"fund_code": code, "full_key": code, "chain_code": code, "portal": "",
             "declared_ccy": ccy, "declared_ccy_source": source}]


def _build(funds, by_code, calls=None):
    return ND.build_nav_dividend_tables(funds, now=NOW, chain_fetch=_fetch_from(by_code, calls))


# ═══════════════════════ ccy_source 與標籤 ═══════════════════════

def test_meta_收_ccy_source是出處字串_配息是出處加matches_source():
    out = _build(_meta_funds("MZ01"), {"MZ01": _res("MZ01")})
    nav, div = out["nav"], out["dividend"]
    assert len(nav["rows"]) == 10 and {r["ccy"] for r in nav["rows"]} == {"USD"}
    assert nav["provenance"]["MZ01"]["ccy_source"] == META
    assert [r["ex_date"] for r in div["rows"]] == ["2026-08-05", "2026-09-05"]
    assert {r["ccy"] for r in div["rows"]} == {"USD"}
    assert div["provenance"]["MZ01"]["ccy_source"] == f"{META}_matches_source"
    assert div["provenance"]["MZ01"]["ccy_source"] != "USD_matches_source"   # :1464 的陷阱
    assert div["settled"] == {"MZ01": True}


def test_hld預設_配息ccy_source仍是holding_user_input_matches_source_不是幣別值():
    funds = [{"fund_code": "MZ01", "full_key": "MZ01", "chain_code": "MZ01", "portal": "", "holding_ccy": "USD"}]
    out = _build(funds, {"MZ01": _res("MZ01")})
    assert out["dividend"]["provenance"]["MZ01"]["ccy_source"] == "holding_user_input_matches_source"
    assert out["nav"]["provenance"]["MZ01"]["ccy_source"] == "holding_user_input"


def test_meta與hld_寫出的列與判斷結果相同_只差出處字串():
    hld = _build([{"fund_code": "MZ01", "full_key": "MZ01", "chain_code": "MZ01", "portal": "", "holding_ccy": "USD"}],
                 {"MZ01": _res("MZ01")})
    meta = _build(_meta_funds("MZ01"), {"MZ01": _res("MZ01")})
    for table in ("nav", "dividend"):
        assert meta[table]["rows"] == hld[table]["rows"]
        assert meta[table]["withheld"] == hld[table]["withheld"]
        assert meta[table]["skipped_rows"] == hld[table]["skipped_rows"]


# ═══════════════════════ 文案不出現「持倉」 ═══════════════════════

def _all_text(out) -> str:
    return json.dumps(out, ensure_ascii=False, default=str)


@pytest.mark.parametrize("ccy, attrs, items, nav_code, div_code", [
    ("usd", None, None, ND.WITHHELD_CCY_MISSING, ND.WITHHELD_CCY_MISSING),          # 格式不合
    (None, None, None, ND.WITHHELD_CCY_MISSING, ND.WITHHELD_CCY_MISSING),           # 缺值
    ("USD", {"currency": "EUR"}, None, ND.WITHHELD_CCY_CONFLICT, None),             # 序列宣告不同
    ("TWD", None, None, None, ND.WITHHELD_CCY_CONFLICT),                            # 配息宣告不同
])
def test_meta_各種扣下_文案沒有持倉_有來源自報字樣(ccy, attrs, items, nav_code, div_code):
    out = _build(_meta_funds("MZ01", ccy), {"MZ01": _res("MZ01", series_attrs=attrs, items=items)})
    assert out["nav"]["withheld"].get("MZ01") == nav_code
    assert out["dividend"]["withheld"].get("MZ01") == div_code
    text = _all_text(out)
    assert "持倉" not in text
    assert META_TEXT in text


def test_meta_非原生報價未宣告_文案沒有持倉():
    ms = {"source": "Morningstar:0P000TEST", S.MS_SECID_ORIGIN_ATTR: S.MS_SECID_FROM_POOL}
    out = _build(_meta_funds("MZ01"), {"MZ01": _res("MZ01", series_attrs=ms)})
    assert out["nav"]["withheld"] == {"MZ01": ND.WITHHELD_CCY_MISSING}
    line = out["nav"]["skipped"]["MZ01"][0]
    assert "持倉" not in line and META_TEXT in line and "Morningstar:0P000TEST" in line


def test_meta_兩筆meta幣別意思不同_淨值與配息都扣下_文案沒有持倉():
    funds = [*_meta_funds("MZ01", "USD"), *_meta_funds("MZ01", "EUR")]
    out = _build(funds, {"MZ01": _res("MZ01")})
    assert out["nav"]["withheld"] == {"MZ01": ND.WITHHELD_CCY_CONFLICT}
    assert out["dividend"]["withheld"] == {"MZ01": ND.WITHHELD_CCY_CONFLICT}
    assert "持倉" not in _all_text(out)
    assert "declared:'USD'" in out["nav"]["skipped"]["MZ01"][0]


def test_meta_resolve_nav_ccy_缺值文案_主詞換成淨值序列():
    ccy, src, code, why = ND.resolve_nav_ccy("eur", ["eur"], label_source=META)
    assert (ccy, src, code) == (None, None, ND.WITHHELD_CCY_MISSING)
    assert why == ("淨值序列未自報幣別、來源自報（MoneyDJ+TDCC）也沒有可用的幣別"
                   "（淨值序列自報值不合 ISO 4217：'eur'；來源自報（MoneyDJ+TDCC）幣別不合 ISO 4217：'eur'）")
    assert ND.resolve_nav_ccy(None, ["USD"], label_source=META)[:2] == ("USD", META)


def test_meta_出處沒有meta前綴_字樣照原文顯示():
    assert ND._label_words("TDCC:基本資料")["row"] == "來源自報（TDCC:基本資料）"
    assert ND._label_words(ND.LABEL_SOURCE_HOLDING)["row"] == "持倉列"


# ═══════════════════════ 序列／配息宣告的幣別與 meta 不同 → 扣下 ═══════════════════════

def test_meta_序列宣告幣別與meta不同_淨值整檔扣下():
    out = _build(_meta_funds("MZ01", "USD"), {"MZ01": _res("MZ01", series_attrs={"currency": "JPY"})})
    assert out["nav"]["rows"] == []
    assert out["nav"]["withheld"] == {"MZ01": ND.WITHHELD_CCY_CONFLICT}
    assert "即時序列:'JPY'" in out["nav"]["skipped"]["MZ01"][0]
    assert out["nav"]["fetched"]["MZ01"] == 10 and out["nav"]["skipped_rows"]["MZ01"] == 10


def test_meta_配息宣告幣別與meta不同_配息整檔扣下():
    items = [_fc_item("2026-08-05", "USD"), _fc_item("2026-09-05", "EUR")]
    out = _build(_meta_funds("MZ01", "USD"), {"MZ01": _res("MZ01", items=items)})
    assert out["dividend"]["rows"] == []
    assert out["dividend"]["withheld"] == {"MZ01": ND.WITHHELD_CCY_CONFLICT}
    assert out["dividend"]["skipped"]["MZ01"] == [
        f"配息宣告的幣別與{META_TEXT}的幣別不同或認不出（'EUR'；{META_TEXT} USD）；"
        "不改標籤、不換算，這一檔的配息 2 筆全部不寫"]
    assert len(out["nav"]["rows"]) == 10   # 淨值不受影響


def test_meta_配息沒宣告的那幾筆不寫_其餘照寫():
    items = [_fc_item("2026-08-05", "USD"), _fc_item("2026-09-05", "", ccy_field="")]
    out = _build(_meta_funds("MZ01", "USD"), {"MZ01": _res("MZ01", items=items)})
    assert [r["ex_date"] for r in out["dividend"]["rows"]] == ["2026-08-05"]
    assert out["dividend"]["settled"] == {"MZ01": False}


def test_meta_配息全部沒宣告_ccy_not_source_reported():
    items = [_fc_item("2026-08-05", "", ccy_field=""), _fc_item("2026-09-05", "", ccy_field="")]
    out = _build(_meta_funds("MZ01", "USD"), {"MZ01": _res("MZ01", items=items)})
    assert out["dividend"]["rows"] == []
    assert out["dividend"]["withheld"] == {"MZ01": ND.WITHHELD_CCY_NOT_SOURCE_REPORTED}


def test_meta_累積表閘門開啟時_各段的ccy_source都是meta出處(monkeypatch):
    monkeypatch.setattr(ND, "NAV_HISTORY_PROVENANCE_VERIFIED", True)
    dates = ["2026-07-01", "2026-07-02"]
    hist = pd.Series([9.0, 9.01], index=pd.to_datetime(dates), dtype=float)
    s = pd.concat([hist, H.series(5, start="2026-08-03")])
    s.attrs = {"source": "FundClear:GetFundNAV", "fetched_at": L1_AT, ND.HISTORY_MERGED_ATTR: 2,
               ND.HISTORY_DATES_ATTR: dates,
               ND.HISTORY_RECORDED_AT_ATTR: {d: "2026-07-05T00:00:00+00:00" for d in dates},
               ND.HISTORY_SOURCE_ATTR: "nav_history"}
    out = ND.rows_from_nav_series("MZ01", s, None, holding_ccys=["USD"], now=NOW, label_source=META)
    assert len(out["rows"]) == 7
    assert out["provenance"]["ccy_source"] == META


def test_meta_累積表閘門關閉_即時那一段的ccy_source是meta出處():
    dates = ["2026-07-01"]
    s = pd.concat([pd.Series([9.0], index=pd.to_datetime(dates), dtype=float), H.series(5, start="2026-08-03")])
    s.attrs = {"source": "FundClear:GetFundNAV", "fetched_at": L1_AT, ND.HISTORY_MERGED_ATTR: 1,
               ND.HISTORY_DATES_ATTR: dates, ND.HISTORY_RECORDED_AT_ATTR: {}, ND.HISTORY_SOURCE_ATTR: "nav_history"}
    out = ND.rows_from_nav_series("MZ01", s, None, holding_ccys=["USD"], now=NOW, label_source=META)
    assert len(out["rows"]) == 5 and out["provenance"]["ccy_source"] == META


# ═══════════════════════ 輸入檢查 ═══════════════════════

def test_混用holding_ccy與declared_ccy_ValueError_不同列():
    funds = [*_meta_funds("MZ01"),
             {"fund_code": "MZ02", "full_key": "MZ02", "chain_code": "MZ02", "portal": "", "holding_ccy": "USD"}]
    with pytest.raises(ValueError, match="不混用"):
        _build(funds, {})


def test_混用holding_ccy與declared_ccy_ValueError_同一列():
    funds = [dict(_meta_funds("MZ01")[0], holding_ccy=None)]
    with pytest.raises(ValueError, match="不混用"):
        _build(funds, {})


def test_混用_只給declared_ccy_source也算meta():
    funds = [{"fund_code": "MZ01", "full_key": "MZ01", "chain_code": "MZ01", "portal": "",
              "declared_ccy_source": META, "holding_ccy": "USD"}]
    with pytest.raises(ValueError, match="不混用"):
        _build(funds, {})


@pytest.mark.parametrize("source", [None, "", " meta:X", "meta:X ", 5, ND.LABEL_SOURCE_HOLDING])
def test_declared_ccy_source不合格_ValueError(source):
    with pytest.raises(ValueError, match="declared_ccy_source"):
        _build(_meta_funds("MZ01", source=source), {})


def test_同一檔meta出處不同_列為輸入矛盾_不取數():
    calls = []
    funds = [*_meta_funds("MZ01", source="meta:MoneyDJ"), *_meta_funds("MZ01", source="meta:TDCC")]
    out = _build(funds, {"MZ01": _res("MZ01")}, calls)
    assert calls == []
    assert out["nav"]["withheld"] == {"MZ01": ND.WITHHELD_INPUT_CONFLICT}
    assert out["dividend"]["withheld"] == {"MZ01": ND.WITHHELD_INPUT_CONFLICT}
    assert "declared_ccy_source" in out["nav"]["skipped"]["MZ01"][0]


# ═══════════════════════ chain_fetch 注入 ═══════════════════════

def test_注入的chain_fetch被呼叫_參數是chain_code與full_key(monkeypatch):
    monkeypatch.setattr(ND, "fetch_chain_with_error", lambda *a, **k: pytest.fail("注入時不得呼叫預設值"))
    calls = []
    funds = [{"fund_code": "MZ01", "full_key": "MZ01", "chain_code": "MZ01", "portal": "", "holding_ccy": "USD"}]
    out = _build(funds, {"MZ01": _res("MZ01")}, calls)
    assert calls == [("MZ01", "MZ01")]
    assert len(out["nav"]["rows"]) == 10


def test_chain_fetch預設值不變_沒給就呼叫模組層fetch_chain_with_error(monkeypatch):
    import inspect
    assert inspect.signature(ND.build_nav_dividend_tables).parameters["chain_fetch"].default is None
    calls = []
    monkeypatch.setattr(ND, "fetch_chain_with_error", _fetch_from({"MZ01": _res("MZ01")}, calls))
    funds = [{"fund_code": "MZ01", "full_key": "MZ01", "chain_code": "MZ01", "portal": "", "holding_ccy": "USD"}]
    out = ND.build_nav_dividend_tables(funds, now=NOW)
    assert calls == [("MZ01", "MZ01")] and len(out["nav"]["rows"]) == 10


def test_chain_fetch拋例外_照舊轉成兩邊的失敗原文():
    def boom(chain_code, full_key):
        raise RuntimeError("壞了")
    out = ND.build_nav_dividend_tables(_meta_funds("MZ01"), now=NOW, chain_fetch=boom)
    assert out["nav"]["errors"] == {"MZ01": "RuntimeError: 壞了"}
    assert out["dividend"]["errors"] == {"MZ01": "RuntimeError: 壞了"}


def test_chain_fetch不是可呼叫物_ValueError():
    with pytest.raises(ValueError, match="chain_fetch"):
        ND.build_nav_dividend_tables(_meta_funds("MZ01"), now=NOW, chain_fetch="x")
