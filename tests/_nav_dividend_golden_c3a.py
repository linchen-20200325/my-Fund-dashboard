# -*- coding: utf-8 -*-
"""`tests/fixtures/nav_dividend_golden_before_c3a.json`（C3a 黃金檔）的情境矩陣與錄製腳本（測試共用；不是測試檔）。

用途：C3a（`services/v2_tables/nav_dividend.py` 新增 `label_source`／`declared_ccy`／`chain_fetch`，純重構）
**動手之前**，在乾淨的 `origin/main`（`4eda84d`）上以本檔的情境矩陣跑一次，把每個情境的回傳值整個序列化存檔；
改動後 `tests/test_nav_dividend_golden_c3a.py` 再跑一次，序列化結果必須與檔案**逐位元組相同**（hld 路徑零變化）。

用法（repo 根目錄，在**要當基準的那個版本**上執行；不打網路、不讀試算表）::

    python tests/_nav_dividend_golden_c3a.py <輸出 JSON 路徑>

⚠️ 不得用改動後的程式重錄來「讓測試變綠」—— 那會讓「改動前後逐位元組相同」變成循環論證
（同 `tests/_record_a_chain_golden.py` 的體例）。

三種情境（全部是 hld 會走到的程式碼；呼叫端只給 `holding_ccy`，不給任何新參數）：
- `chain:*`：真的 A 鏈（`services.moneydj_fetcher.auto_fetch_moneydj`），來源全部換成 `tests/_a_chain_stub.py` 的替身，
  經 `build_nav_dividend_tables` 整條跑完。
- `res:*`：把 `nav_dividend` 命名空間裡的 `auto_fetch_moneydj` 換成回傳手寫結果 dict 的替身 —— A 鏈之後的
  `_nav_from_chain`／`_div_from_chain`／`build_nav_dividend_tables` 全部是真的。用來造 A 鏈替身造不出來的形狀
  （非原生報價且未宣告幣別、晨星代碼來自名稱搜尋、累積表標記…）。
- `pure:*`：直接呼叫 `rows_from_nav_series`／`rows_from_chain_dividends`（不經 A 鏈的序列、累積表閘門開啟時的路徑）。
"""

from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]

NOW = dt.datetime(2026, 10, 1, 0, 0, tzinfo=dt.timezone.utc)
L1_AT = "2026-09-30T08:00:00+00:00"
STARTED = "2026-09-30T07:00:00+00:00"
_T0 = "2026-02-01T00:00:00+00:00"
_NO_DROP = {"truncated": 0, "filtered": 0, "other_tables": 0}
_TCB_HEADER = ("配息基準日", "除息日", "發放日", "類別", "每單位配息額", "年化配息率", "幣別")


def _setup_path():
    for p in (str(_ROOT), str(_ROOT / "tests")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import fund_fetcher  # noqa: F401  —— 先解開既有的循環 import（同 tests/conftest.py）


def dumps(value) -> str:
    """穩定序列化（鍵排序、保留中文、浮點用 repr）。不認得的型別 → 當場炸（不偷偷轉字串）。"""
    def _refuse(obj):
        raise TypeError(f"黃金檔遇到不能序列化的型別 {type(obj).__name__}: {obj!r}")
    return json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True, default=_refuse) + "\n"


# ───────────────────────── 素材 ─────────────────────────

def _tcb_items(*rows, header=_TCB_HEADER):
    import repositories.fund.sources as S
    items = [{"date": base, "ex_date": ex, "pay_date": pay, "amount": amt, "yield_pct": 6.0, "currency": ccy,
              S.DIV_PROVENANCE_KEY: {"parser": S.DIV_PARSER_TCB, "date_header": header[0],
                                     "ex_date_header": header[1], "pay_date_header": header[2],
                                     "currency_header": header[6], "amount_header": header[4],
                                     "header_cells": len(header), "row_td_cells": 7, "row_th_cells": 0,
                                     "table_has_span": False,
                                     "page": "tcbbankfund.moneydj.com/funddj/yp/wb05.djhtm", "fetched_at": L1_AT}}
             for base, ex, pay, amt, ccy in rows]
    return S._div_result(items, S.DIV_PARSER_TCB, S.DIV_STATUS_ROWS, dropped=dict(_NO_DROP))


def _fc_item(day, amount, ccy, *, date_field="ExDividendDate", ccy_field="Currency"):
    import repositories.fund.sources as S
    return {"date": day, "ex_date": day, "pay_date": day, "amount": amount, "yield_pct": 0, "currency": ccy,
            S.DIV_PROVENANCE_KEY: {"parser": S.DIV_PARSER_FUNDCLEAR, "date_field": date_field,
                                   "currency_field": ccy_field, "amount_field": "DividendAmount",
                                   "fetched_at": L1_AT}}


def _outcome(name, *, parser=None, status=None, evidenced=False, dropped=None):
    import repositories.fund.sources as S
    parser = parser or S.DIV_PARSER_TCB
    status = status or S.DIV_STATUS_ROWS
    return {"outcome": name, "legacy_inline_parse": False, "none_evidenced": evidenced,
            "sources": [{"source": "tcb_moneydj", "parser": parser, "status": status, "detail": "",
                         "page_type": "yp010001", "dropped": dict(_NO_DROP) if dropped is None else dropped}]}


def _series(n, *, attrs, start="2026-08-03"):
    import _a_chain_stub as H
    return H.series(n, start=start, attrs=attrs)


def _res(code, series, *, dividends=None, outcome=None, data_source="FundClear", attempts=None):
    from services.moneydj_fetcher import NAV_ATTEMPTS_KEY
    from repositories.fund.fund_orchestration import DIVIDENDS_OUTCOME_KEY
    res = {"full_key": code, "series": series, "dividends": dividends if dividends is not None else [],
           DIVIDENDS_OUTCOME_KEY: outcome, "data_source": data_source, "chain_started_at": STARTED}
    if attempts is not None:
        res[NAV_ATTEMPTS_KEY] = attempts
    return res


def _funds(code, *ccys, full_key=None, chain_code=None, portal=""):
    if not ccys:
        return [{"fund_code": code, "full_key": full_key or code, "chain_code": chain_code or code, "portal": portal}]
    return [{"fund_code": code, "full_key": full_key or code, "chain_code": chain_code or code, "portal": portal,
             "holding_ccy": c} for c in ccys]


# ───────────────────────── 情境矩陣 ─────────────────────────

def chain_cases() -> dict:
    """`{名稱: (funds, A 鏈替身 scenario)}`：真的 A 鏈。"""
    import _a_chain_stub as H

    def full(ccy="", **over):
        code, sc = H.full_success_scenario(currency=ccy)
        # 黃金檔不需要 L1 快取判準的長序列：淨值改成 25 個工作日（過 FundClear 20 筆採用門檻），檔案小一個量級
        attrs = {"source": "FundClear:GetFundNAV", "fetched_at": _T0}
        if ccy:
            attrs["currency"] = ccy
        sc = dict(sc, _src_fundclear_nav=H.series(25, attrs=attrs))
        sc.update(over)
        return code, sc

    out = {}
    code, sc = full("", _src_tcb_div=_tcb_items(("2026/01/01", "2026/01/03", "2026/01/10", 0.05, "美元"),
                                                 ("2026/02/01", "2026/02/03", "2026/02/10", 0.05, "USD")))
    out["chain:holding_input_series_undeclared_div_accept"] = (_funds(code, "USD"), sc)
    code, sc = full("USD")
    out["chain:source_declared_matches_holding"] = (_funds(code, "USD"), sc)
    code, sc = full("EUR", _src_tcb_div=_tcb_items(("2026/01/01", "2026/01/03", "2026/01/10", 0.05, "歐元")))
    out["chain:series_declared_conflicts_holding_div_conflict"] = (_funds(code, "USD"), sc)
    code, sc = full("", _src_tcb_div=_tcb_items(("2026/01/01", "2026/01/03", "2026/01/10", 0.05, "")))
    out["chain:div_undeclared"] = (_funds(code, "USD"), sc)
    code, sc = full("", _src_tcb_div=_tcb_items(("2026/01/01", "2026/01/03", "2026/01/10", 0.05, "美元")))
    out["chain:holding_missing"] = (_funds(code), sc)
    out["chain:holding_bad_format"] = (_funds(code, "usd"), sc)
    out["chain:holding_two_rows_conflict"] = (_funds(code, "USD", "TWD"), sc)
    out["chain:holding_two_rows_same"] = (_funds(code, "USD", "USD", None), sc)
    bad_at = {"source": "FundClear:GetFundNAV", "fetched_at": "not-a-time"}
    code, sc = full("", _src_fundclear_nav=H.series(25, attrs=bad_at))
    out["chain:fetched_at_unparseable"] = (_funds(code, "USD"), sc)
    future = {"source": "FundClear:GetFundNAV", "fetched_at": "2027-01-01T00:00:00+00:00"}
    code, sc = full("", _src_fundclear_nav=H.series(25, attrs=future))
    out["chain:fetched_at_future"] = (_funds(code, "USD"), sc)
    for name in ("S1_complete_fundclear", "S3_all_fail", "S4_cache_fallback", "S5_hist_read_fail"):
        code, sc = H.scenarios()[name]
        out[f"chain:{name}"] = (_funds(code, "USD"), sc)
    code, sc = full("")
    out["chain:input_conflict"] = ([*_funds(code, "USD"), *_funds(code, "USD", full_key="OTHERKEY")], sc)
    out["chain:portal_given"] = (_funds(code, "USD", portal="tcb"), sc)
    out["chain:full_key_mismatch"] = (_funds(code, "USD", full_key="WANTKEY"), sc)
    return out


def res_cases() -> dict:
    """`{名稱: (funds, {chain_code: res})}`：A 鏈之後全部是真的。"""
    import repositories.fund.sources as S
    from repositories.fund import fund_orchestration as FO
    from services.v2_tables import nav_dividend as ND

    fc = {"source": "FundClear:GetFundNAV", "fetched_at": L1_AT}
    ms = {"source": "Morningstar:0P000TEST", "fetched_at": L1_AT, S.MS_SECID_ORIGIN_ATTR: S.MS_SECID_FROM_POOL}
    out = {}
    code = "RZ01"
    out["res:non_native_undeclared"] = (_funds(code, "USD"), {code: _res(code, _series(20, attrs=ms))})
    out["res:non_native_declared_same"] = (_funds(code, "USD"),
                                           {code: _res(code, _series(20, attrs=dict(ms, currency="USD")))})
    out["res:non_native_declared_other"] = (_funds(code, "USD"),
                                            {code: _res(code, _series(20, attrs=dict(ms, currency="TWD")))})
    for origin in (S.MS_SECID_FROM_NAME_SEARCH, S.MS_SECID_FROM_CODE_SEARCH):
        attrs = dict(ms, **{S.MS_SECID_ORIGIN_ATTR: origin})
        out[f"res:morningstar_{origin}"] = (_funds(code, "USD"), {code: _res(code, _series(20, attrs=attrs))})
    # 累積表閘門關閉：live ＋ 累積點；只有累積點
    hist_dates = ["2026-07-01", "2026-07-02", "2026-07-03"]

    def with_hist(n_live, *, live_ccy="", hist_ccy=None):
        import pandas as pd
        live = _series(n_live, attrs={}) if n_live else None
        hist_idx = pd.to_datetime(hist_dates)
        hist = pd.Series([9.0, 9.01, 9.02], index=hist_idx, dtype=float)
        s = hist if live is None else pd.concat([hist, live])
        s.attrs = {"source": "FundClear:GetFundNAV", "fetched_at": L1_AT, ND.HISTORY_MERGED_ATTR: len(hist_dates),
                   ND.HISTORY_DATES_ATTR: list(hist_dates),
                   ND.HISTORY_RECORDED_AT_ATTR: {d: "2026-07-05T00:00:00+00:00" for d in hist_dates},
                   ND.HISTORY_SOURCE_ATTR: "nav_history", ND.HISTORY_LIVE_CURRENCY_ATTR: live_ccy,
                   ND.HISTORY_CURRENCY_ATTR: hist_ccy or {d: "" for d in hist_dates}}
        return s

    out["res:history_gate_closed_live_and_hist"] = (_funds(code, "USD"), {code: _res(code, with_hist(10))})
    out["res:history_gate_closed_hist_only"] = (_funds(code, "USD"), {code: _res(code, with_hist(0))})
    out["res:history_live_declared_conflict"] = (_funds(code, "USD"),
                                                 {code: _res(code, with_hist(10, live_ccy="EUR"))})
    # 配息：各種 outcome
    s = _series(10, attrs=fc)
    out["res:div_none_evidenced"] = (_funds(code, "USD"),
                                     {code: _res(code, s, outcome=_outcome(FO.DIV_OUTCOME_NONE, evidenced=True))})
    out["res:div_none_unevidenced"] = (_funds(code, "USD"), {code: _res(code, s, outcome=_outcome(FO.DIV_OUTCOME_NONE))})
    out["res:div_failed"] = (_funds(code, "USD"), {code: _res(
        code, s, outcome=_outcome(FO.DIV_OUTCOME_FAILED, status=S.DIV_STATUS_FAILED))})
    out["res:div_undetermined"] = (_funds(code, "USD"), {code: _res(code, s, outcome=None)})
    fc_items = [_fc_item("2026-08-05", 0.04, "USD"), _fc_item("2026-09-05", 0.04, "USD"),
                _fc_item("2026-07-05", 0.04, "USD", date_field="Date"),
                _fc_item("2026-06-05", 0.04, "", ccy_field="")]
    out["res:div_fundclear_mixed"] = (_funds(code, "USD"), {code: _res(
        code, s, dividends=fc_items, outcome=_outcome(FO.DIV_OUTCOME_ROWS, parser=S.DIV_PARSER_FUNDCLEAR))})
    out["res:div_fundclear_all_accept"] = (_funds(code, "USD"), {code: _res(
        code, s, dividends=fc_items[:2], outcome=_outcome(FO.DIV_OUTCOME_ROWS, parser=S.DIV_PARSER_FUNDCLEAR))})
    out["res:div_fundclear_conflict"] = (_funds(code, "TWD"), {code: _res(
        code, s, dividends=fc_items[:2], outcome=_outcome(FO.DIV_OUTCOME_ROWS, parser=S.DIV_PARSER_FUNDCLEAR))})
    out["res:div_holding_conflict"] = (_funds(code, "USD", "EUR"), {code: _res(
        code, s, dividends=fc_items[:2], outcome=_outcome(FO.DIV_OUTCOME_ROWS, parser=S.DIV_PARSER_FUNDCLEAR))})
    out["res:div_holding_missing_bad"] = (_funds(code, "us d"), {code: _res(
        code, s, dividends=fc_items[:2], outcome=_outcome(FO.DIV_OUTCOME_ROWS, parser=S.DIV_PARSER_FUNDCLEAR))})
    attempts = [{"page_type": "yp010000", "status": "failed", "error": "全部失敗",
                 "nav_source_failures": [{"source": "FundClear", "error": "HTTP 503", "page_type": "yp010000"}]}]
    out["res:no_series_with_attempts"] = (_funds(code, "USD"), {code: _res(code, None, attempts=attempts)})
    out["res:orchestrator_fetched_at"] = (_funds(code, "USD"), {code: _res(
        code, _series(10, attrs={"source": "FundClear:GetFundNAV"}))})
    two = [*_funds("RZ02", "USD"), *_funds("RZ03")]
    out["res:two_funds"] = (two, {"RZ02": _res("RZ02", _series(10, attrs=fc)),
                                  "RZ03": _res("RZ03", _series(10, attrs=dict(fc, currency="USD")))})
    return out


def pure_cases() -> dict:
    """`{名稱: callable() -> 回傳值}`：直接呼叫純函式。"""
    import pandas as pd
    import repositories.fund.sources as S
    from services.v2_tables import nav_dividend as ND

    def plain(attrs, holding):
        s = _series(8, attrs=attrs)
        return lambda: ND.rows_from_nav_series("PZ01", s, None, holding_ccys=holding, now=NOW)

    fc = {"source": "FundClear:GetFundNAV", "fetched_at": L1_AT}
    out = {
        "pure:nav_source_reported": plain(dict(fc, currency="USD"), ()),
        "pure:nav_source_and_holding_same": plain(dict(fc, currency="USD"), ["usd", "USD"]),
        "pure:nav_source_conflicts_holding": plain(dict(fc, currency="EUR"), ["USD"]),
        "pure:nav_holding_only": plain(fc, ["TWD"]),
        "pure:nav_both_bad_format": plain(dict(fc, currency="eur"), ["eur "]),
        "pure:nav_holding_non_string": plain(fc, [840]),
        "pure:nav_missing": plain(fc, []),
        "pure:nav_holding_nan": plain(fc, [float("nan")]),
    }

    def gate_open(live_ccy, hist_ccy):
        def run():
            from _pytest.monkeypatch import MonkeyPatch
            mp = MonkeyPatch()
            try:
                mp.setattr(ND, "NAV_HISTORY_PROVENANCE_VERIFIED", True)
                dates = ["2026-07-01", "2026-07-02"]
                hist = pd.Series([9.0, 9.01], index=pd.to_datetime(dates), dtype=float)
                live = _series(5, attrs={})
                s = pd.concat([hist, live])
                s.attrs = {"source": "FundClear:GetFundNAV", "fetched_at": L1_AT,
                           ND.HISTORY_MERGED_ATTR: 2, ND.HISTORY_DATES_ATTR: dates,
                           ND.HISTORY_RECORDED_AT_ATTR: {dates[0]: "2026-07-05T00:00:00+00:00"},
                           ND.HISTORY_SOURCE_ATTR: "nav_history", ND.HISTORY_CURRENCY_ATTR: hist_ccy,
                           ND.CHAIN_ATTR: {"page_type": "yp010000", "data_source": "x", "fetched_at_from": "series_attrs"},
                           ND.CHAIN_FAILURES_ATTR: None, ND.CHAIN_HIST_READ_ERROR_ATTR: None,
                           ND.CHAIN_DECLARED_CCY_ATTR: live_ccy}
                return ND.rows_from_nav_series("PZ02", s, None, holding_ccys=["USD"], now=NOW)
            finally:
                mp.undo()
        return run

    out["pure:history_gate_open_ok"] = gate_open("", {"2026-07-01": "", "2026-07-02": ""})
    out["pure:history_gate_open_hist_ccy_conflict"] = gate_open("USD", {"2026-07-01": "TWD", "2026-07-02": ""})

    items = [*_tcb_items(("2026/01/01", "2026/01/03", "2026/01/10", 0.05, "美元"),
                         ("2026/02/01", "2026/02/03", "2026/02/10", 0.05, "")),
             {"date": "2026-03-01", "amount": 0.05, "currency": "USD"},
             "not-a-dict"]
    div = {"items": items, "error": None, "outcome": {
        "outcome": "rows", "legacy_inline_parse": False, "none_evidenced": False,
        "sources": [{"source": "tcb_moneydj", "parser": S.DIV_PARSER_TCB, "status": S.DIV_STATUS_ROWS,
                     "detail": "", "page_type": "yp010001", "dropped": dict(_NO_DROP)}]}}
    out["pure:div_mixed_tcb"] = lambda: ND.rows_from_chain_dividends("PZ03", div, holding_ccys=["USD"], now=NOW)
    out["pure:div_holding_missing"] = lambda: ND.rows_from_chain_dividends("PZ03", div, holding_ccys=[], now=NOW)
    out["pure:div_not_dict"] = lambda: ND.rows_from_chain_dividends("PZ03", "x", holding_ccys=["USD"], now=NOW)
    out["pure:resolve_nav_ccy"] = lambda: [list(ND.resolve_nav_ccy(src, hold)) for src, hold in (
        ("USD", []), (None, ["USD"]), ("EUR", ["USD"]), ("eur", ["eur"]), (None, []), (None, ["x", "y"]),
        (float("nan"), ["JPY"]))]
    return out


# ───────────────────────── 執行 ─────────────────────────

def _quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*a, **k)


def run_case(name):
    """跑單一情境，回傳值（未序列化）。"""
    _setup_path()
    from _pytest.monkeypatch import MonkeyPatch
    import _a_chain_stub as H
    from services.v2_tables import nav_dividend as ND

    kind = name.split(":", 1)[0]
    if kind == "pure":
        return _quiet(pure_cases()[name])
    mp = MonkeyPatch()
    try:
        if kind == "chain":
            funds, scenario = chain_cases()[name]
            H.install(mp, scenario)
        else:
            funds, by_code = res_cases()[name]
            mp.setattr(ND, "auto_fetch_moneydj", lambda code, return_page_type=False: (by_code[code], "yp010000"))
        return _quiet(ND.build_nav_dividend_tables, funds, now=NOW)
    finally:
        mp.undo()


def case_names() -> list:
    _setup_path()
    return sorted([*chain_cases(), *res_cases(), *pure_cases()])


def record(out_path: str) -> dict:
    golden = {name: json.loads(dumps(run_case(name))) for name in case_names()}
    pathlib.Path(out_path).write_text(dumps(golden), encoding="utf-8")
    return golden


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("用法：python tests/_nav_dividend_golden_c3a.py <輸出 JSON 路徑>")
    g = record(sys.argv[1])
    print("ok", len(g), "cases")
