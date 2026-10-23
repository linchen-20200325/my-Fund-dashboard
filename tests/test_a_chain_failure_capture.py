# -*- coding: utf-8 -*-
"""A 鏈補收失敗原文（總管 2026-10-13 技術裁定第 3、4 條）：新增鍵以外，A 鏈行為零變化（fast lane；不打網路）。

證明方式：`tests/fixtures/a_chain_golden_before.json` 是**改動前**的程式碼對 `tests/_a_chain_stub.py::scenarios()`
七組 stub 輸入跑出來的結果（`auto_fetch_moneydj` 與 L1 `fetch_fund_from_moneydj_url` 兩條入口的回傳值，
加上各自依序呼叫了哪些來源）。改動後再跑一次，拿掉新增鍵後必須逐欄相同：
- 回傳 dict 的新增鍵：`nav_source_failures`（L1）、`nav_page_type_attempts`（`auto_fetch_moneydj`）；
- 淨值序列 attrs 的新增鍵：`nav_history_dates`／`nav_history_recorded_at`／`nav_history_source`／
  `nav_history_dates_error`（`_merge_nav_history_series`）。
每次跑都會變的兩個時間欄（`_moneydj_fetched_at`、`fetched_at`）兩邊都不比。

⚠️ 黃金檔的產生方式：改動前在乾淨的 `origin/main`（`1586a45`）＋本檔的 stub 工具上跑一次並存檔；
之後**不得**以改動後的程式重產（那會把要證明的東西變成循環論證）。
"""

from __future__ import annotations

import contextlib
import io
import json
import pathlib

import pytest

import _a_chain_stub as H

_GOLDEN = pathlib.Path(__file__).resolve().parent / "fixtures" / "a_chain_golden_before.json"
NEW_RESULT_KEYS = frozenset({"nav_source_failures", "nav_page_type_attempts", "chain_started_at",
                             # 2026-10-13 B 線配息移交：配息取數狀態（新增鍵）
                             "dividend_sources_status", "dividends_fetch_outcome"})
NEW_SERIES_ATTRS = frozenset({"nav_history_dates", "nav_history_recorded_at", "nav_history_source",
                              "nav_history_dates_error", "nav_history_currency", "nav_history_live_currency",
                              "secid_origin", "currency_id_origin"})
# 2026-10-23 客戶裁示 1B（docs/v2/64 §4 #1/#4/#5；BL-0420）：`calc_metrics` / `finalize_fund_metrics` 的
# 年化配息率改為「近 12 個月實際配息 ÷ 最新淨值」（無紀錄 → None，不再是 0）、新增配息筆數鍵、
# 不再把本地還原值注入 perf["1Y"]、對帳 self 只在窗口 ≥ 350 天時算。這些鍵在黃金檔裡是 1B 前的語意，
# **黃金檔不得以改動後程式重產**，故比對時兩邊同時拿掉這幾個鍵；其餘每一欄（含 perf / perf_source）照舊逐欄相同。
# 這幾個鍵的新語意由 `tests/test_ssot_1b_total_return_adr_eating.py` 正面釘住，不在這裡重產。
CHANGED_METRICS_KEYS_1B = frozenset({"annual_div", "monthly_div", "annual_div_rate",
                                     "annual_div_rate_div_count", "annual_div_rate_window_end",
                                     "ret_1y_div_count", "ret_1y_reconcile", "div_yield_reconcile"})


def _strip(value, keys: frozenset):
    """遞迴拿掉指定鍵（只用在 metrics 層的 1B 鍵；黃金檔已是 normalize 後的 JSON）。"""
    if isinstance(value, dict):
        return {k: _strip(v, keys) for k, v in value.items() if k not in keys}
    if isinstance(value, list):
        return [_strip(v, keys) for v in value]
    return value


def _run(monkeypatch, code, scenario):
    from repositories.fund.fund_orchestration import fetch_fund_from_moneydj_url
    from services.moneydj_fetcher import auto_fetch_moneydj

    calls = H.install(monkeypatch, scenario)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        res, page_type = auto_fetch_moneydj(code, return_page_type=True)
    auto_calls = list(calls)
    calls.clear()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        raw = fetch_fund_from_moneydj_url(code)
    return res, page_type, raw, auto_calls, list(calls)


_SCENARIOS = H.scenarios()


@pytest.mark.parametrize("name", sorted(_SCENARIOS))
def test_除新增鍵外_改動前後逐欄相同_呼叫順序相同(monkeypatch, name):
    golden = json.loads(_GOLDEN.read_text(encoding="utf-8"))[name]
    code, scenario = H.scenarios()[name]
    res, page_type, raw, auto_calls, l1_calls = _run(monkeypatch, code, scenario)
    drop = H.VOLATILE_TOP_KEYS | NEW_RESULT_KEYS | NEW_SERIES_ATTRS
    assert page_type == golden["page_type"]
    assert [list(c) for c in auto_calls] == golden["auto_calls"]
    assert [list(c) for c in l1_calls] == golden["l1_calls"]
    assert _strip(H.normalize(res, drop=drop), CHANGED_METRICS_KEYS_1B) == _strip(golden["auto"], CHANGED_METRICS_KEYS_1B)
    assert _strip(H.normalize(raw, drop=drop), CHANGED_METRICS_KEYS_1B) == _strip(golden["l1"], CHANGED_METRICS_KEYS_1B)
    # 裁示 1B 的鍵只在 metrics 層；黃金檔裡 perf["1Y"] / perf_source 一欄未動（上面已逐欄比過）。
    _m = (res.get("metrics") or {}) if isinstance(res, dict) else {}
    if _m:
        assert "ret_1y_div_count" in _m and "annual_div_rate_div_count" in _m
        assert _m.get("annual_div_rate") != 0, "無配息紀錄的年化配息率必須是 None，不是 0（裁示 1B）"


def test_黃金檔七個情境都在_防空掃():
    golden = json.loads(_GOLDEN.read_text(encoding="utf-8"))
    assert set(golden) == set(_SCENARIOS) and len(golden) == 7


# ═══════════════════════ 新增鍵的內容 ═══════════════════════

def test_全來源失敗_逐來源原文依嘗試順序記下_含fetch_nav自己的逐網址原文(monkeypatch):
    code, scenario = H.scenarios()["S3_all_fail"]
    res, page_type, raw, _a, _l = _run(monkeypatch, code, scenario)
    attempts = res["nav_page_type_attempts"]
    assert [a["page_type"] for a in attempts] == ["yp010000", "yp010001"]   # 兩個頁型都留
    for attempt in attempts:
        sources = [f["source"] for f in attempt["nav_source_failures"]]
        assert sources[:3] == ["FundClear", "cnyes", "tcb_moneydj"]          # 瀑布 2a→2b→2c 的順序
        assert "fetch_nav（legacy 最終備援）" in sources
        legacy = [f for f in attempt["nav_source_failures"] if f["source"].startswith("fetch_nav")][0]
        assert "kind=blocked" in legacy["error"] and "回傳 0 筆" in legacy["error"]
    # 多來源主路線那幾筆帶頁型；legacy 段（不分頁型）的那幾筆不帶
    assert all("page_type" in f for f in raw["nav_source_failures"] if not f["source"].startswith("fetch_nav"))
    assert any(f["source"].startswith("fetch_nav") and "page_type" not in f for f in raw["nav_source_failures"])


def test_來源成功_仍記下被略過的來源_但不影響採用結果(monkeypatch):
    code, scenario = H.scenarios()["S2_shortwindow_rescue"]
    res, _pt, _raw, _a, _l = _run(monkeypatch, code, scenario)
    fails = res["nav_source_failures"]
    assert fails[0] == {"source": "FundClear", "page_type": "yp010000",
                        "error": "回傳 8 筆，未達本步採用門檻 20 筆"}
    assert any("近30日短窗" in f["error"] for f in fails)
    assert res["data_source"] == "tcb_moneydj"   # 採用結果與黃金檔相同（上一條已逐欄比過）


def test_累積表併入點_記下日期與各自的recorded_at_缺的留空不補(monkeypatch):
    code, scenario = H.scenarios()["S1_complete_fundclear"]
    res, _pt, _raw, _a, _l = _run(monkeypatch, code, scenario)
    attrs = res["series"].attrs
    assert attrs["nav_history_dates"] == ["2025-11-03", "2025-11-04", "2025-11-05"]   # 重疊日 live 贏，不算
    assert attrs["nav_history_recorded_at"] == {"2025-11-03": "2025-11-03T09:00:00+00:00",
                                                "2025-11-04": "",
                                                "2025-11-05": "2025-11-05T09:00:00+00:00"}
    assert attrs["nav_history_source"] == "GoogleSheet:nav_history:ZZF001"


def test_shared_reads範圍內_整張表只讀一次_失敗照實重拋不重打(monkeypatch):
    import services.nav_history_gs as nh

    reads = []

    def fake_get_sheet(oauth_client=None):
        reads.append(1)

        class _WS:
            def get_all_values(self):
                return [["code", "date", "nav"], ["AAA", "2026-01-02", "10"], ["BBB", "2026-01-02", "20"]]

        class _SH:
            def worksheet(self, _name):
                return _WS()
        return _SH()

    monkeypatch.setattr(nh, "is_enabled", lambda: True)
    monkeypatch.setattr(nh, "_nav_backoff_ident", lambda oauth_client=None: ("", ""))
    monkeypatch.setattr(nh, "_get_sheet", fake_get_sheet)
    with nh.shared_reads():
        a = nh.load_points("AAA")
        b = nh.load_points("bbb ")
        c = nh.load_series("AAA")
    assert len(reads) == 1
    assert [p["nav"] for p in a] == [10.0] and [p["nav"] for p in b] == [20.0] and list(c) == [10.0]
    nh.load_points("AAA")          # 範圍外：照原路徑再讀
    assert len(reads) == 2

    def boom(oauth_client=None):
        reads.append(1)
        raise RuntimeError("APIError 429 quota")

    monkeypatch.setattr(nh, "_get_sheet", boom)
    reads.clear()
    with nh.shared_reads():
        for _ in range(3):
            with pytest.raises(nh.NavHistoryError, match="429"):
                nh.load_points("AAA")
    assert len(reads) == 1


# ═══════════════════════ L1 十五分鐘快取（2026-10-13 總管技術裁定：補回、只快取成功、防污染）═══════════════════════

def _l1(code):
    from repositories.fund.fund_orchestration import fetch_fund_from_moneydj_url
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fetch_fund_from_moneydj_url(code)


def test_L1快取_成功結果十五分鐘內命中_不再打來源_開始時間是原本那一次(monkeypatch):
    from repositories.fund import fund_orchestration as FO
    from shared.ttls import TTL_15MIN
    code, sc = H.full_success_scenario()
    calls = H.install(monkeypatch, sc)
    first = _l1(code)
    n = len(calls)
    second = _l1(code)
    assert len(calls) == n and n > 0                                   # 第二次一個來源都沒打
    assert second["chain_started_at"] == first["chain_started_at"]    # 不是當下時間
    info = FO.fetch_fund_from_moneydj_url.cache_info()
    assert info["hits"] == 1 and info["ttl_sec"] == TTL_15MIN


def test_L1快取_下游改寫回傳物件_不會改到快取內容(monkeypatch):
    code, sc = H.full_success_scenario()
    H.install(monkeypatch, sc)
    first = _l1(code)
    original_nav = float(first["series"].iloc[0])
    original_name = first["fund_name"]
    # 模擬 L2 finalize／_merge_nav_history_series 的就地改寫
    first["fund_name"] = "被下游改掉"
    first["metrics"]["x"] = 1
    first["series"].iloc[0] = 999.0
    first["series"].attrs["source"] = "被下游改掉"
    first["source_trace"].append({"source": "下游", "success": True})
    second = _l1(code)
    assert second["fund_name"] == original_name and "x" not in second["metrics"]
    assert float(second["series"].iloc[0]) == original_nav
    assert second["series"].attrs["source"] != "被下游改掉"
    assert not any(e.get("source") == "下游" for e in second["source_trace"])
    assert second is not first and second["series"] is not first["series"]


@pytest.mark.parametrize("name", ["S1_complete_fundclear", "S3_all_fail", "S4_cache_fallback",
                                  "S6_insurance_morningstar"])
def test_L1快取_失敗或預存檔或序列不足_不入快取_下次真的再打(monkeypatch, name):
    code, sc = H.scenarios()[name]
    calls = H.install(monkeypatch, sc)
    _l1(code)
    n = len(calls)
    _l1(code)
    # 第二次真的再跑一次瀑布：FundClear 被打的次數與第一次相同（持股另有自己的一小時快取，不在本條射程）
    first = [c[0] for c in calls[:n]].count("_src_fundclear_nav")
    assert first > 0 and [c[0] for c in calls[n:]].count("_src_fundclear_nav") == first


def test_L1快取_cache_clear清得掉_有登記在全域清除名單(monkeypatch):
    from infra.cache import _CACHE_REGISTRY
    from repositories.fund import fund_orchestration as FO
    assert FO.fetch_fund_from_moneydj_url.__wrapped__ in _CACHE_REGISTRY   # 登記的是內層快取那一層
    code, sc = H.full_success_scenario()
    calls = H.install(monkeypatch, sc)
    _l1(code)
    FO.fetch_fund_from_moneydj_url.cache_clear()
    _l1(code)
    # 清掉之後真的再跑一次瀑布（持股另有自己的一小時快取，不在本條射程）
    assert [c[0] for c in calls].count("_src_fundclear_nav") == 2


def test_B線連續兩次build_第二次不再打任何來源(monkeypatch):
    """hld 每次重跑都呼叫 build_nav_table：第二次應全部命中 L1 快取（累積表讀取不在此列，見第 3 條）。"""
    import datetime as dt
    from services.v2_tables import nav_dividend as ND
    code, sc = H.full_success_scenario()
    calls = H.install(monkeypatch, sc)
    funds = [{"fund_code": code, "full_key": code, "chain_code": code, "holding_ccy": "USD"}]
    now = dt.datetime(2026, 3, 10, tzinfo=dt.timezone.utc)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        first = ND.build_nav_table(funds, now=now)
        n = len(calls)
        second = ND.build_nav_table(funds, now=now)
    extra = calls[n:]
    assert [c[0] for c in extra] == ["nav_history.load_points"]       # 只剩累積表那一次
    assert first["rows"] == second["rows"]


# ═══════════════════════ B-3：只有每個組成部分都成功才快取（稽核 6 兩個實驗，head 與 base 行為相同）═══════════════════════
# base ＝ 沒有 L1 快取（`fdbfb550`～本批之前）：每次呼叫都重試每一個組成部分。

def _flaky(first, then):
    state = {"n": 0}

    def fn(*_a, **_k):
        state["n"] += 1
        return first if state["n"] == 1 else then
    return fn


def test_B3實驗一_wb07第一次失敗第二次成功_第二次補得到_與base相同(monkeypatch):
    code, sc = H.full_success_scenario()
    ok = sc["fetch_risk_metrics"]
    sc = dict(sc, fetch_risk_metrics=_flaky({}, ok))
    H.install(monkeypatch, sc)
    first = _l1(code)
    second = _l1(code)
    assert first["risk_metrics"] == {} and second["risk_metrics"] == ok       # base 第二次會補到


def test_B3實驗二_名稱第一次失敗_第二次結果與base相同(monkeypatch):
    code, sc = H.full_success_scenario()
    sc = dict(sc, _src_tcb_meta=_flaky({}, sc["_src_tcb_meta"]))
    H.install(monkeypatch, sc)
    first = _l1(code)
    second = _l1(code)
    assert not first["fund_name"] and first["status"] == "partial"
    assert second["fund_name"] == "全成功基金"                               # base：failed→complete 的那個補回


@pytest.mark.parametrize("broken", ["fetch_performance_wb01", "fetch_holdings", "_src_tcb_div"])
def test_B3_任一組成部分失敗_不入快取(monkeypatch, broken):
    code, sc = H.full_success_scenario()
    sc = dict(sc, **{broken: [] if broken == "_src_tcb_div" else {}})
    calls = H.install(monkeypatch, sc)
    _l1(code)
    _l1(code)
    assert [c[0] for c in calls].count("_src_fundclear_nav") == 2


# ═══════════════════════ 稽核 5 N3：救援採用的標明、多候選代碼的原文保留 ═══════════════════════

def test_先記失敗後經救援採用_標明(monkeypatch):
    code, sc = H.scenarios()["S2_shortwindow_rescue"]
    H.install(monkeypatch, sc)
    res = _l1(code)
    tcb = [f for f in res["nav_source_failures"] if f["source"] == "tcb_moneydj"]
    assert tcb and all("後經側車救援採用" in f["error"] for f in tcb)


def test_多候選代碼_前面候選的失敗原文保留(monkeypatch):
    code = "ACTI171"                                    # 境內，normalize_domestic_code 會展開成兩個候選
    calls = H.install(monkeypatch, {"_src_tcb_meta": {"fund_name": "x"}})
    res = _l1(code)
    cands = {f.get("candidate") for f in res["nav_source_failures"] if f.get("candidate")}
    assert {"ACTI171", "ACTI71"} <= cands
    assert ("_src_fundclear_nav", "ACTI171") in calls and ("_src_fundclear_nav", "ACTI71") in calls


# ═══════════════════════ 稽核 6 N2：_ttl_cache 多執行緒 ═══════════════════════

def test_ttl_cache_多執行緒寫入淘汰_不拋錯_預設行為不變():
    import threading
    from infra.cache import _ttl_cache

    @_ttl_cache(ttl_sec=60, maxsize=64)
    def f(x):
        return x * 2

    errors = []

    def worker(base):
        try:
            for i in range(3000):
                assert f(base * 100000 + i) == (base * 100000 + i) * 2
        except Exception as exc:  # noqa: BLE001
            errors.append(repr(exc))

    threads = [threading.Thread(target=worker, args=(b,)) for b in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert f.cache_info()["size"] <= 64
    assert f(7) == 14 and f(7) == 14 and f.cache_info()["hits"] >= 1



# ═══════════════════════ 2026-10-13 第三輪：快取判準的補洞測試 ═══════════════════════

def test_M6_除了淨值是預存檔以外全部成功_不入快取(monkeypatch):
    code, sc = H.full_success_scenario()
    # 長跨度（不是短窗），確保擋下它的只有「預存檔」這一條
    cache_s = H.series(300, start="2025-01-06", attrs={"source": f"GitHubActions:cache/nav/{code}.json",
                                  "fetched_at": "2026-03-05T00:00:00+00:00",
                                  "cache_updated_at": "2026-03-01T00:00:00+00:00", "nav_quality": {"stale": False}})
    sc = dict(sc, _src_fundclear_nav=H.series(0), fetch_nav=cache_s)
    calls = H.install(monkeypatch, sc)
    first = _l1(code)
    assert first["fund_name"] and first["dividends"] and first["risk_metrics"]       # 其餘都成功
    assert first["series"].attrs["source"].startswith("GitHubActions:cache/nav/")
    _l1(code)
    assert [c[0] for c in calls].count("fetch_nav") == 2


def test_短窗tcb30救回後不入快取(monkeypatch):
    code, sc = H.full_success_scenario()
    sc = dict(sc, _src_fundclear_nav=H.series(0),
              _src_tcb_nav=H.series(30, attrs={"source": "MoneyDJ:tcb:nav30", "fetched_at": "2026-02-01T00:00:00+00:00"}))
    calls = H.install(monkeypatch, sc)
    first = _l1(code)
    assert first["data_source"] == "tcb_moneydj" and len(first["series"]) == 30   # 側車救援採用的短窗
    _l1(code)
    assert [c[0] for c in calls].count("_src_tcb_nav") == 2


@pytest.mark.parametrize("value,ok", [
    ({"risk_table": {}, "source": "MoneyDJ:x:wb07"}, True),
    ({"source": "MoneyDJ:all_failed", "diag": []}, False),
    ({"source": "MoneyDJ:exception", "error": "x"}, False),
    ({}, False), (None, False), ([1], False),
])
def test_component_ok_判讀失敗標記(value, ok):
    from repositories.fund.fund_orchestration import _component_ok
    assert _component_ok(value) is ok
