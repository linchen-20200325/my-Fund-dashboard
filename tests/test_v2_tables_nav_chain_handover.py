# -*- coding: utf-8 -*-
"""B 線淨值移交給 A 鏈（客戶 2026-10-13 裁示；總管同日技術裁定第 1～6 條）（fast lane；不打網路）。

A 鏈＝`services.moneydj_fetcher.auto_fetch_moneydj` → L2 enriched → L1 多來源瀑布 → L2 併入累積表。
B 線＝`services/v2_tables/nav_dividend.py::build_nav_table`（hld、set 共用）。
全部來源以 `tests/_a_chain_stub.py` 換成記錄呼叫的替身。
"""

from __future__ import annotations

import contextlib
import datetime as dt
import io

import pytest

import _a_chain_stub as H
from services.v2_tables import nav_dividend as ND

NOW = dt.datetime(2026, 3, 10, 0, 0, tzinfo=dt.timezone.utc)


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*args, **kwargs)


def _b(monkeypatch, name, *, ccy="USD", full_key=None, scenario=None, now=NOW):
    code, sc = H.scenarios()[name] if scenario is None else scenario
    calls = H.install(monkeypatch, sc)
    item = {"fund_code": code, "full_key": full_key or code, "chain_code": code, "portal": ""}
    if ccy is not None:
        item["holding_ccy"] = ccy
    out = _quiet(ND.build_nav_table, [item], now=now)
    return code, out, calls


# ═══════════════════════ 來源與優先序：原樣使用 A 鏈 ═══════════════════════

@pytest.mark.parametrize("name", sorted(H.scenarios()))
def test_來源呼叫順序與A鏈逐一相同(monkeypatch, name):
    from services.moneydj_fetcher import auto_fetch_moneydj
    code, sc = H.scenarios()[name]
    a_calls = H.install(monkeypatch, sc)
    _quiet(auto_fetch_moneydj, code)
    expected = list(a_calls)
    _code, _out, b_calls = _b(monkeypatch, name)
    assert b_calls == expected
    assert len(expected) >= 10       # 空掃防呆：確實跑過瀑布


def test_本層沒有自己的頁型迴圈或來源清單():
    import re
    src = (__import__("pathlib").Path(ND.__file__)).read_text(encoding="utf-8")
    body = re.sub(r"(?m)#.*$", "", re.sub(r'(?s)""".*?"""', "", src))   # 只看程式碼，不看說明
    # 2026-10-13：`fetch_fund_from_moneydj_url` 只准以「名字」出現在 `CHAIN_CACHED_FUNCTIONS`（清快取用），不准被呼叫
    for token in ("yp010000", "yp010001", "_src_", "fetch_fund_from_moneydj_url(", "fetch_fund_multi_source",
                  "fetch_nav_with_error"):
        assert token not in body, token


# ═══════════════════════ 累積表併入點：fetched_at 與來源標記誠實 ═══════════════════════

def test_累積表舊點_fetched_at取各自recorded_at_缺的不寫_重疊日用即時值(monkeypatch):
    code, out, _calls = _b(monkeypatch, "S1_complete_fundclear")
    rows = {r["nav_date"]: r for r in out["rows"]}
    assert rows["2025-11-03"]["fetched_at"] == "2025-11-03T09:00:00+00:00"
    assert rows["2025-11-05"]["fetched_at"] == "2025-11-05T09:00:00+00:00"
    assert "2025-11-04" not in rows                                      # recorded_at 空 → 不寫，不以當下補
    assert any("沒有 recorded_at" in s for s in out["skipped"][code])
    live_day = rows["2026-01-05"]                                        # 與累積表重疊：live 值、live 時間
    assert live_day["nav_orig_ccy"] == 10.0 and live_day["fetched_at"] == "2026-02-01T00:00:00+00:00"
    prov = out["provenance"][code]
    assert prov["nav_history"] == {"source": "GoogleSheet:nav_history:ZZF001", "points": 3, "written": 2,
                                   "recorded_at_missing": 1, "read_error": None}
    assert prov["latest_from"] == ND.LATEST_FROM_LIVE and prov["cache_fallback"] is False
    assert prov["live_error"] is None and prov["chain"]["page_type"] == "yp010000"
    assert out["fetched"][code] == len(out["rows"]) + out["skipped_rows"][code]


def test_累積表救援_全部是舊點_標不是本次取得_記本次即時失敗(monkeypatch):
    code, out, _calls = _b(monkeypatch, "S7_hist_rescue")
    assert len(out["rows"]) == 30
    assert {r["fetched_at"] for r in out["rows"]} == {"2026-01-02T03:04:05+00:00"}
    prov = out["provenance"][code]
    assert prov["cache_fallback"] is True and prov["latest_from"] == ND.LATEST_FROM_NAV_HISTORY
    assert prov["live_error"]                                              # set 頁據此記 failed
    assert prov["fetched_at"] is None                                      # 沒有任何本次取得的點


def test_累積表的點比即時新_最新一筆標不是本次取得(monkeypatch):
    code = "ZZF010"
    sc = {"_src_fundclear_nav": H.series(25, start="2025-06-02",
                                         attrs={"source": "FundClear:x", "fetched_at": "2026-02-01T00:00:00+00:00"}),
          "_src_tcb_meta": {"fund_name": "測試十"},
          "nav_history_points": H._hist_points(code, ["2026-02-02"], recorded_at="2026-02-03T00:00:00+00:00")}
    _c, out, _calls = _b(monkeypatch, None, scenario=(code, sc))
    prov = out["provenance"][code]
    assert out["rows"][-1]["nav_date"] == "2026-02-02"
    assert prov["latest_from"] == ND.LATEST_FROM_NAV_HISTORY and prov["cache_fallback"] is True
    assert prov["stale"] is None and prov["live_error"] is None             # 即時那一段是成功的


def test_A鏈交出併入標記卻沒有日期清單_整檔不寫_不猜():
    s = H.series(12, attrs={"source": "FundClear:x", "fetched_at": "2026-02-01T00:00:00+00:00",
                            ND.HISTORY_MERGED_ATTR: "+3 pts from GoogleSheet:nav_history:X",
                            ND.HISTORY_DATES_ERROR_ATTR: "TypeError: boom"})
    out = ND.rows_from_nav_series("X", s, None, holding_ccys=["USD"], now=NOW)
    assert out["rows"] == [] and out["withheld"] == ND.WITHHELD_FETCHED_AT_MISSING
    assert "TypeError: boom" in out["skipped"][0]


# ═══════════════════════ 預存檔（cache/nav）沒有退化 ═══════════════════════

def test_預存檔那一支_fetched_at取cache_updated_at_標預存_失敗原文含瀑布與fetch_nav(monkeypatch):
    code, out, _calls = _b(monkeypatch, "S4_cache_fallback")
    assert len(out["rows"]) == 40
    assert {r["fetched_at"] for r in out["rows"]} == {"2026-03-01T00:00:00+00:00"}
    prov = out["provenance"][code]
    assert prov["cache_fallback"] is True and prov["stale"] is True
    assert "kind=blocked" in prov["live_error"] and "FundClear" in prov["live_error"]


# ═══════════════════════ 幣別（2026-10-13 稽核 5 B-1）═══════════════════════
# 標籤只用持倉手填；序列或累積表點宣告了與持倉不同的幣別 → 整檔不寫；非原生報價來源沒宣告 → 整檔不寫。

def test_宣告幣別與持倉相同_標籤用持倉_照寫(monkeypatch):
    code, out, _calls = _b(monkeypatch, "S5_hist_read_fail", ccy="USD")      # FundClear 宣告 USD
    assert out["rows"] and {r["ccy"] for r in out["rows"]} == {"USD"}
    assert out["provenance"][code]["ccy_source"] == "holding_user_input"
    code, out, _calls = _b(monkeypatch, "S5_hist_read_fail", ccy=None)       # 持倉沒填：不拿序列宣告當標籤
    assert out["rows"] == [] and out["withheld"] == {code: ND.WITHHELD_CCY_MISSING}


def test_B1例二_FundClear序列宣告USD_持倉填TWD_整檔不寫(monkeypatch):
    code, out, _calls = _b(monkeypatch, "S5_hist_read_fail", ccy="TWD")
    assert out["rows"] == [] and out["withheld"] == {code: ND.WITHHELD_CCY_CONFLICT}
    assert "即時序列:'USD'" in out["skipped"][code][0] and "持倉 TWD" in out["skipped"][code][0]


def test_B1例三_累積表點宣告USD_持倉填TWD_整檔不寫(monkeypatch):
    code = "ZZF011"
    sc = {"_src_tcb_meta": {"fund_name": "x"},
          "nav_history_points": [dict(p, currency="USD") for p in H._hist_points(
              code, [d.date().isoformat() for d in __import__("pandas").date_range("2025-10-01", periods=30, freq="B")])]}
    _c, out, _calls = _b(monkeypatch, None, scenario=(code, sc), ccy="TWD")
    assert out["rows"] == [] and out["withheld"] == {code: ND.WITHHELD_CCY_CONFLICT}
    assert "累積表 2025-10-01:'USD'" in out["skipped"][code][0]


def _ms_scenario(monkeypatch, *, secid_from: str, fund_name="某某收益成長基金"):
    """真的 `_src_morningstar_nav`（只換掉對外的部分）：池表／寫死表／名稱搜尋三種 secId 出處，
    timeseries 以 `currencyId` 要回換算後的淨值。回 `(code, scenario, search_calls)`。"""
    import io as _io
    import json as _json
    import repositories.fund.sources as SRC

    code = "TLZZ8"
    search_calls = []
    monkeypatch.setattr("repositories.pool_repository.resolve_secid",
                        lambda c: ("0PPOOL", "") if secid_from == "pool" else None, raising=False)
    monkeypatch.setattr("repositories.pool_repository.resolve_isin", lambda c: "", raising=False)
    monkeypatch.setattr(SRC, "_MORNINGSTAR_SECID_MAP",
                        {code: ("0PHARD" if secid_from == "hardcoded" else "", "USD")})

    def fake_search(q, *a, **k):
        search_calls.append(("search", q))
        return "0PNAME"
    monkeypatch.setattr(SRC, "_morningstar_search_secid", fake_search)
    payload = {"TimeSeries": {"Security": [{"HistoryDetail": [
        {"EndDate": d.date().isoformat(), "Value": str(30 + i / 10)}
        for i, d in enumerate(__import__("pandas").date_range("2024-01-01", periods=400, freq="B"))]}]}}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return _json.dumps(payload).encode()
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _Resp())
    real = SRC._src_morningstar_nav
    fund_name_meta = fund_name
    sc = {"_src_tdcc_meta": {"fund_name": fund_name, "nav_latest": 30.0},
          # 跨度延長（`_span_extend_insurance_nav`）那一趟會把 meta 名稱帶進來；瀑布 2g 那一趟還沒有名稱。
          # 這裡一律以 meta 名稱呼叫，重現「名稱搜尋」那條路（稽核 5 B-2 的實例）。
          "_src_morningstar_nav": lambda c, fund_name="", currency_hint="": real(
              c, fund_name=fund_name or fund_name_meta, currency_hint=currency_hint)}
    return code, sc, search_calls


def test_B1例一_晨星以currencyId_USD取回換算後淨值_持倉填TWD_整檔不寫(monkeypatch):
    code, sc, _search = _ms_scenario(monkeypatch, secid_from="hardcoded")
    _c, out, _calls = _b(monkeypatch, None, scenario=(code, sc), ccy="TWD", now=None)
    assert out["rows"] == [] and out["withheld"] == {code: ND.WITHHELD_CCY_CONFLICT}, out
    assert "USD" in out["skipped"][code][0]


def test_非原生來源沒宣告幣別_整檔不寫():
    s = H.series(12, attrs={"source": "AlphaVantage:TIME_SERIES_DAILY_ADJUSTED:X", "fetched_at": "2026-02-01T00:00:00+00:00",
                            ND.CHAIN_ATTR: {"page_type": "yp010001"}, ND.CHAIN_DECLARED_CCY_ATTR: ""})
    out = ND.rows_from_nav_series("X", s, None, holding_ccys=["USD"], now=NOW)
    assert out["rows"] == [] and out["withheld"] == ND.WITHHELD_CCY_MISSING
    assert "非原生報價來源" in out["skipped"][0]


# ═══════════════════════ secId 出處（2026-10-13 稽核 5 B-2）═══════════════════════

def test_B2_晨星secId由名稱搜尋得來_B線整檔不寫_A鏈照舊採用(monkeypatch):
    code, sc, search_calls = _ms_scenario(monkeypatch, secid_from="name")
    _c, out, _calls = _b(monkeypatch, None, scenario=(code, sc), ccy="USD", now=None)
    assert ("search", "某某收益成長基金") in search_calls
    assert out["rows"] == [] and "以基金名稱搜尋的晨星代碼，依規則不採用" in out["errors"][code]
    from services.moneydj_fetcher import auto_fetch_moneydj
    res = _quiet(auto_fetch_moneydj, code)                      # A 鏈本身：照舊採用（不改選擇與順序）
    assert res["series"] is not None and res["series"].attrs["secid_origin"] == "name_search"


@pytest.mark.parametrize("secid_from,origin", [("pool", "pool"), ("hardcoded", "hardcoded_map")])
def test_B2_晨星secId來自池表或寫死表_照收_並標出currencyId出處(monkeypatch, secid_from, origin):
    code, sc, search_calls = _ms_scenario(monkeypatch, secid_from=secid_from)
    _c, out, _calls = _b(monkeypatch, None, scenario=(code, sc), ccy="USD", now=None)
    assert search_calls == [] and out["rows"] and code not in out["errors"]
    from services.moneydj_fetcher import auto_fetch_moneydj
    attrs = _quiet(auto_fetch_moneydj, code)["series"].attrs
    assert attrs["secid_origin"] == origin and attrs["currency_id_origin"] == "hardcoded_map"


# ═══════════════════════ 稽核 5 N1／N2／N3 ═══════════════════════

def test_N1_序列沒帶fetched_at_用快取內原本那次的chain_started_at_不是當下(monkeypatch):
    code, sc = H.full_success_scenario()
    sc["_src_fundclear_nav"].attrs.pop("fetched_at")
    H.install(monkeypatch, sc)
    item = {"fund_code": code, "full_key": code, "chain_code": code, "holding_ccy": "USD"}
    first = _quiet(ND.build_nav_table, [item])
    second = _quiet(ND.build_nav_table, [item])                           # 命中 L1 快取
    times = {r["fetched_at"] for r in first["rows"]}
    assert len(times) == 1 and {r["fetched_at"] for r in second["rows"]} == times
    assert first["provenance"][code]["chain"]["fetched_at_from"] == "orchestrator"


def test_N2_失敗行用每筆自己的頁型_成功不印狀態行():
    res = {ND.NAV_ATTEMPTS_KEY: [
        {"page_type": "yp010000", "status": "partial", "error": None, "nav_source_failures": [
            {"source": "FundClear", "page_type": "yp010001", "error": "回傳 0 筆"},
            {"source": "fetch_nav（legacy 最終備援）", "error": "回傳 0 筆"}]},
        {"page_type": "yp010001", "status": "complete", "error": None, "nav_source_failures": []}]}
    lines = ND._chain_failure_lines(res)
    assert "[yp010001] FundClear：回傳 0 筆" in lines
    assert "[yp010000·legacy] fetch_nav（legacy 最終備援）：回傳 0 筆" in lines
    assert not any("complete" in line for line in lines)


def test_N3_預存檔那一支_fetched_at_from標cache_updated_at(monkeypatch):
    code, out, _calls = _b(monkeypatch, "S4_cache_fallback")
    assert out["provenance"][code]["chain"]["fetched_at_from"] == "cache_updated_at"


# ═══════════════════════ 代碼對照 ═══════════════════════

def test_A鏈回的full_key與fund_keys不同_照實標缺_原因讀得懂(monkeypatch):
    code, sc = H.scenarios()["S1_complete_fundclear"]
    sc = dict(sc, mapping={code: {"public_code": "ZZF999", "page_type": "yp010001"}})
    _c, out, _calls = _b(monkeypatch, None, scenario=(code, sc), full_key=code)
    assert out["rows"] == []
    assert out["errors"][code] == ND.TEXT_KEY_MISMATCH.format(got="ZZF999", want=code)
    assert "不猜" in out["errors"][code]


def test_沒給chain_code_當場炸_不拿full_key或fund_code去猜():
    with pytest.raises(ValueError, match="chain_code"):
        ND.build_nav_table([{"fund_code": "X1", "full_key": "X1"}])


def test_portal非空_A鏈不吃_照實報錯不取數(monkeypatch):
    calls = H.install(monkeypatch, {})
    out = ND.build_nav_table([{"fund_code": "X1", "full_key": "X1", "chain_code": "X1", "portal": "TCB",
                               "holding_ccy": "USD"}], now=NOW)
    assert calls == [] and "portal" in out["errors"]["X1"]


# ═══════════════════════ 全來源失敗：原文呈現 ═══════════════════════

def test_全來源失敗_兩個頁型逐來源原文都在errors(monkeypatch):
    code, out, _calls = _b(monkeypatch, "S3_all_fail")
    err = out["errors"][code]
    assert err.startswith(ND.TEXT_NO_SERIES.format(code=code))
    assert "[yp010000] FundClear：回傳 0 筆" in err and "[yp010001] FundClear：回傳 0 筆" in err
    assert "fetch_nav('ZZF003') 即時網址與預存檔皆失敗" in err and "kind=blocked" in err
    assert out["fetched"] == {code: 0} and out["rows"] == []


def test_累積表讀取失敗_即時部分照交_原文記在provenance與skipped(monkeypatch):
    code, out, _calls = _b(monkeypatch, "S5_hist_read_fail")
    assert len(out["rows"]) == 25 and code not in out["errors"]
    assert "429" in out["provenance"][code]["nav_history"]["read_error"]
    assert any("累積表本次讀取失敗" in s for s in out["skipped"][code])


# ═══════════════════════ Sheets 讀取量：同一次 build 整張表只讀一次 ═══════════════════════

def test_同一次build_多檔基金_累積表只讀一次(monkeypatch):
    import services.nav_history_gs as nh
    real_load_points = nh.load_points
    sc = {"_src_fundclear_nav": H.series(25, attrs={"source": "FundClear:x",
                                                     "fetched_at": "2026-02-01T00:00:00+00:00"}),
          "_src_tcb_meta": {"fund_name": "x"}}
    H.install(monkeypatch, sc)
    monkeypatch.setattr(nh, "load_points", real_load_points)
    reads = []

    def fake_get_sheet(oauth_client=None):
        reads.append(1)

        class _WS:
            def get_all_values(self):
                return [["code", "date", "nav", "fund_name", "source", "recorded_at"],
                        ["ZZA1", "2025-11-03", "9", "", "app", "2025-11-03T09:00:00+00:00"]]

        class _SH:
            def worksheet(self, _n):
                return _WS()
        return _SH()

    monkeypatch.setattr(nh, "is_enabled", lambda: True)
    monkeypatch.setattr(nh, "_nav_backoff_ident", lambda oauth_client=None: ("", ""))
    monkeypatch.setattr(nh, "_get_sheet", fake_get_sheet)
    funds = [{"fund_code": c, "full_key": c, "chain_code": c, "holding_ccy": "USD"} for c in ("ZZA1", "ZZA2", "ZZA3")]
    out = _quiet(ND.build_nav_table, funds, now=NOW)
    assert len(reads) == 1
    assert "2025-11-03" in {r["nav_date"] for r in out["rows"] if r["fund_code"] == "ZZA1"}
