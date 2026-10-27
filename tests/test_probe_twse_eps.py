"""離線測試：`scripts/probe_twse_eps.py`（BL-0509）。只依賴標準庫＋被測腳本；全部以假 fetcher，不發任何網路請求。

守：(a) 報告 schema (b) 絕不含 proxy 憑證／host (c) Missing 不補 0 (d) 端點白名單僅 GET 官方 TWSE／MOPS 網域。
射程外：不驗真實端點的欄位長相（沙箱連不到 TWSE）；不驗 workflow（見 yml 檔頭）。
"""
from __future__ import annotations

import gzip
import importlib.util
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("probe_twse_eps", _ROOT / "scripts" / "probe_twse_eps.py")
P = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(P)

NOW = datetime(2026, 10, 27, 4, 0, tzinfo=timezone.utc)   # 台北 2026-10-27
FAKE_PROXY = "http://probeuser:Sup3rSecretPw@nas-internal.example.invalid:31280"


def _resp(obj, status=200, ctype="application/json"):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    return {"status": status, "content_type": ctype, "latency_ms": 12.3, "bytes": len(body), "body": body, "error": None}


def _fake(routes, leak=None):
    calls = []

    def http_get(url, transport):
        calls.append((url, transport))
        if leak:
            return {"status": None, "content_type": None, "latency_ms": 1.0, "bytes": None, "body": None,
                    "error": P.mask_text(f"ProxyError: cannot connect {leak}", P.secret_literals())}
        for key, val in routes.items():
            if key in url:
                return val
        return _resp([], 200)
    http_get.calls = calls
    return http_get


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv("PROXY_URL", raising=False)
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    monkeypatch.setenv("PROBE_EXECUTED_SHA", "b" * 40)


ROUTES = {
    "MI_INDEX": _resp([{"日期": "1151026", "指數": P.TAIEX_NAME, "收盤指數": "20000.00"}]),
    "BWIBBU_ALL": _resp([{"Date": "1151026", "Code": "2330", "PEratio": "20.5"}]),
    "t187ap06_L": _resp([{"出表日期": "1150101", "公司代號": "2330", "基本每股盈餘（元）": "5.1"}]),
    "swagger.json": _resp({"info": {"title": "t", "version": "1"},
                           "paths": {"/exchangeReport/BWIBBU_ALL": {"get": {"summary": "本益比"}},
                                     "/other/x": {"get": {"summary": "zzz"}}}}),
}


def test_report_schema_and_both_transports(monkeypatch):
    f = _fake(ROUTES)
    rep = P.run_probe(http_get=f, sleep_sec=0, now=NOW)
    for k in ("schema_version", "probe", "generated_at_utc", "run_date_taipei", "trigger_sha",
              "executed_sha", "proxy", "endpoints", "swagger_summary", "research_metric", "complete"):
        assert k in rep
    assert rep["trigger_sha"] == "a" * 40 and rep["executed_sha"] == "b" * 40
    assert rep["proxy"] == {"enabled": False} and rep["complete"] is True
    assert len(rep["endpoints"]) == len(P.ENDPOINTS)
    for e in rep["endpoints"]:
        assert set(e["transports"]) == {"direct", "nas_proxy"}
    # 未設 PROXY_URL：nas_proxy 一個請求都不發，且如實標記
    assert all(t == "direct" for _u, t in f.calls)
    mi = next(e for e in rep["endpoints"] if e["id"] == "openapi_MI_INDEX")
    assert mi["transports"]["nas_proxy"]["outcome"] == "proxy_not_configured"
    d = mi["transports"]["direct"]
    assert d["outcome"] == "ok" and d["http_status"] == 200 and d["latency_ms"] == 12.3
    assert d["schema"]["n_rows"] == 1 and d["schema"]["fields"][0] == {"name": "日期", "type": "str"}
    assert d["freshness"]["latest_source_date"] == "2026-10-26" and d["freshness"]["state"] == "fresh"
    assert d["contains_taiex_row"] is True
    sw = rep["swagger_summary"]
    assert [h["path"] for h in sw["relevant_paths"]] == ["/exchangeReport/BWIBBU_ALL"] and sw["n_paths_total"] == 2


def test_proxy_enabled_runs_both_paths(monkeypatch):
    monkeypatch.setenv("PROXY_URL", FAKE_PROXY)
    f = _fake(ROUTES)
    rep = P.run_probe(http_get=f, sleep_sec=0, now=NOW)
    assert rep["proxy"] == {"enabled": True}
    assert {t for _u, t in f.calls} == {"direct", "nas_proxy"}
    mi = next(e for e in rep["endpoints"] if e["id"] == "openapi_MI_INDEX")
    assert mi["direct_vs_nas_same_body"] is True


def test_no_credentials_or_host_in_report(monkeypatch, tmp_path):
    monkeypatch.setenv("PROXY_URL", FAKE_PROXY)
    secrets = ("Sup3rSecretPw", "probeuser", "nas-internal.example.invalid", "31280")
    leak = f"{FAKE_PROXY} host=nas-internal.example.invalid port=31280"
    out = tmp_path / "r.json.gz"
    P.run_probe(http_get=_fake(ROUTES, leak=leak), out_path=str(out), sleep_sec=0, now=NOW)
    raw = gzip.decompress(out.read_bytes()).decode("utf-8")
    for s in secrets:
        assert s not in raw, f"報告含機敏字面值：{s!r}"
    assert "***" in raw   # 遮蔽確實發生（避免空掃）


def test_final_scrub_catches_leak_not_masked_by_fetcher(monkeypatch, tmp_path):
    monkeypatch.setenv("PROXY_URL", FAKE_PROXY)
    resp = _resp([{"a": 1}], 200, ctype="x/nas-internal.example.invalid")
    out = tmp_path / "r.json.gz"
    P.run_probe(http_get=_fake({"MI_INDEX": resp}), out_path=str(out), sleep_sec=0, now=NOW)
    raw = gzip.decompress(out.read_bytes()).decode("utf-8")
    assert "nas-internal.example.invalid" not in raw and "Sup3rSecretPw" not in raw


def test_missing_is_not_zero_filled():
    routes = {
        "MI_INDEX": _resp([]),                                   # 空資料集
        "FMTQIK": {"status": 404, "content_type": "text/html", "latency_ms": 5.0, "bytes": 3, "body": b"nf", "error": None},
        "BWIBBU_ALL": {"status": None, "content_type": None, "latency_ms": 1.0, "bytes": None, "body": None, "error": "boom"},
        "t187ap06_L": _resp([{"公司代號": "2330", "基本每股盈餘（元）": ""}]),   # 無日期欄
    }
    rep = P.run_probe(http_get=_fake(routes), sleep_sec=0, now=NOW)
    by = {e["id"]: e["transports"]["direct"] for e in rep["endpoints"]}
    assert by["openapi_MI_INDEX"]["outcome"] == "empty_dataset"
    assert by["openapi_FMTQIK"]["outcome"] == "http_error" and "schema" not in by["openapi_FMTQIK"]
    assert by["openapi_BWIBBU_ALL"]["outcome"] == "unreachable" and by["openapi_BWIBBU_ALL"]["http_status"] is None
    t6 = by["openapi_t187ap06_L"]
    assert t6["freshness"]["state"] == "no_source_date" and t6["freshness"]["age_days"] is None
    assert t6["schema"]["sample"][0]["基本每股盈餘（元）"] == ""    # 空值原樣，不變 0
    rm = rep["research_metric"]
    assert rm["implied_trailing_index_earnings"] is None
    assert "無法判定" in rm["inputs_ready_for_implied_trailing_index_earnings"]


def test_stale_judged_against_run_date():
    routes = {"MI_INDEX": _resp([{"日期": "1150901", "x": 1}])}
    rep = P.run_probe(http_get=_fake(routes), sleep_sec=0, now=NOW)
    fr = next(e for e in rep["endpoints"] if e["id"] == "openapi_MI_INDEX")["transports"]["direct"]["freshness"]
    assert fr["state"] == "stale" and fr["age_days"] == (date(2026, 10, 27) - date(2026, 9, 1)).days


@pytest.mark.parametrize("raw,expected", [
    ("1151026", date(2026, 10, 26)), ("20261026", date(2026, 10, 26)), ("115/10/26", date(2026, 10, 26)),
    ("2026-10-26", date(2026, 10, 26)), ("115年10月26日", date(2026, 10, 26)),
    ("", None), (None, None), ("abc", None), ("1151345", None),
])
def test_parse_source_date(raw, expected):
    assert P.parse_source_date(raw) == expected


def test_market_pe_field_absent_is_reported_false_not_invented():
    routes = {"MI_INDEX": _resp([{"日期": "1151026", "收盤指數": "1"}]),
              "FMTQIK": _resp([{"日期": "1151026", "成交金額": "1"}])}
    rm = P.run_probe(http_get=_fake(routes), sleep_sec=0, now=NOW)["research_metric"]
    assert rm["market_level_trailing_pe_field_provided"] is False


def test_allowlist_only_official_https_hosts():
    assert all(P.is_allowed_url(u) for _i, _g, u, _k in P.ENDPOINTS)
    for bad in ("http://openapi.twse.com.tw/v1/x", "https://evil.example.com/", "https://twse.com.tw.evil.com/",
                "https://user:pw@openapi.twse.com.tw/", "ftp://www.twse.com.tw/"):
        assert not P.is_allowed_url(bad), bad
    assert P.ALLOWED_HOSTS == {"openapi.twse.com.tw", "www.twse.com.tw", "mopsov.twse.com.tw", "mops.twse.com.tw"}


def test_non_allowlisted_endpoint_is_never_requested():
    f = _fake({})
    ep = ("bad", "x", "https://evil.example.com/a", "json")
    rep = P.run_probe(http_get=f, sleep_sec=0, now=NOW, endpoints=(ep,))
    assert f.calls == []
    assert rep["endpoints"][0]["transports"]["direct"]["outcome"] == "blocked_by_allowlist"


def test_script_is_get_only_and_has_no_secret_printing():
    src = (_ROOT / "scripts" / "probe_twse_eps.py").read_text(encoding="utf-8")
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    assert re.search(r"\.(post|put|delete|patch)\(", code) is None
    assert "rsplit('@'" not in code and 'rsplit("@"' not in code
    # infra.proxy 不得在模組層 import（測試環境缺依賴時也要能 import 本腳本）
    assert re.search(r"^\s*(from|import)\s+infra", code, re.M) is None


def test_write_report_is_gzip_json(tmp_path):
    out = tmp_path / "x" / "r.json.gz"
    P.run_probe(http_get=_fake(ROUTES), out_path=str(out), sleep_sec=0, now=NOW)
    data = json.loads(gzip.decompress(out.read_bytes()))
    assert data["probe"] == "twse_eps" and data["complete"] is True


# ───────────── 稽核修正（M1/M2/S1/S3/S5/S7）─────────────

def test_m1_pe_pb_yield_field_classification():
    fn = P.classify_field
    assert fn("PEratio") == "pe" and fn("P/E") == "pe" and fn("本益比") == "pe" and fn("PE") == "pe"
    assert fn("PBratio") == "pb" and fn("股價淨值比") == "pb"
    assert fn("DividendYield") == "yield" and fn("殖利率(%)") == "yield"
    assert fn("Type") is None and fn("Code") is None


def test_m1_bwibbu_peratio_detected_in_report():
    row = {"Date": "1151026", "Code": "2330", "PEratio": "20.5", "PBratio": "5.1", "DividendYield": "2.0"}
    rep = P.run_probe(http_get=_fake({"BWIBBU_ALL": _resp([row])}), sleep_sec=0, now=NOW)
    r = next(e for e in rep["endpoints"] if e["id"] == "openapi_BWIBBU_ALL")["transports"]["direct"]
    assert r["pe_like_field_names"] == ["PEratio"]
    assert r["pb_like_field_names"] == ["PBratio"] and r["yield_like_field_names"] == ["DividendYield"]
    assert rep["research_metric"]["per_security_pe_sources"]["openapi_BWIBBU_ALL/direct"]["pe_like_field_names"] == ["PEratio"]


def test_m2_low_entropy_fragments_do_not_rewrite_sample_values(monkeypatch, tmp_path):
    monkeypatch.setenv("PROXY_URL", "http://ab:Sup3rSecretPw@nas-internal.example.invalid:3128")
    row = {"收盤指數": "23128.45", "Code": "3128", "note": "ab"}
    out = tmp_path / "r.json.gz"
    P.run_probe(http_get=_fake({"MI_INDEX": _resp([row])}), out_path=str(out), sleep_sec=0, now=NOW)
    raw = gzip.decompress(out.read_bytes()).decode("utf-8")
    assert "23128.45" in raw and '"3128"' in raw and '"ab"' in raw
    for s in ("Sup3rSecretPw", "nas-internal.example.invalid"):
        assert s not in raw


def test_m2_error_text_still_masks_port_and_host(monkeypatch, tmp_path):
    monkeypatch.setenv("PROXY_URL", FAKE_PROXY)
    out = tmp_path / "r.json.gz"
    P.run_probe(http_get=_fake({}, leak="host=nas-internal.example.invalid port=31280"), out_path=str(out),
                sleep_sec=0, now=NOW)
    raw = gzip.decompress(out.read_bytes()).decode("utf-8")
    assert "31280" not in raw and "nas-internal.example.invalid" not in raw and "Sup3rSecretPw" not in raw


def test_s1_redirect_not_followed_and_offsite_blocked():
    def redirect(loc):
        return {"status": 302, "content_type": "text/html", "latency_ms": 1.0, "bytes": 0, "body": None, "error": None,
                "location": loc}
    ep = ("r", "x", "https://openapi.twse.com.tw/v1/x", "json")
    off = P.run_probe(http_get=_fake({"/v1/x": redirect("https://evil.example.com/a")}), sleep_sec=0, now=NOW, endpoints=(ep,))
    t = off["endpoints"][0]["transports"]["direct"]
    assert t["outcome"] == "blocked_redirect" and t["redirect_location_host"] == "evil.example.com" and "schema" not in t
    on = P.run_probe(http_get=_fake({"/v1/x": redirect("/v1/y")}), sleep_sec=0, now=NOW, endpoints=(ep,))
    assert on["endpoints"][0]["transports"]["direct"]["outcome"] == "redirect_not_followed"


def test_s1_http_get_disables_redirects():
    src = (_ROOT / "scripts" / "probe_twse_eps.py").read_text(encoding="utf-8")
    assert "allow_redirects=False" in src


def test_s3_freshness_heuristic_and_financials_not_judged():
    rep = P.run_probe(http_get=_fake(ROUTES), sleep_sec=0, now=NOW)
    by = {e["id"]: e for e in rep["endpoints"]}
    assert by["openapi_MI_INDEX"]["transports"]["direct"]["freshness"]["heuristic"] is True
    fr = by["openapi_t187ap06_L"]["transports"]["direct"]["freshness"]
    assert fr["state"] == "publication_date_not_period" and fr["heuristic"] is True


def test_s5_candidates_flagged():
    rep = P.run_probe(http_get=_fake(ROUTES), sleep_sec=0, now=NOW)
    by = {e["id"]: e for e in rep["endpoints"]}
    assert by["openapi_t187ap06_L_ci"]["candidate"] is True and by["openapi_t187ap14_L"]["candidate"] is True
    assert by["openapi_BWIBBU_ALL"]["candidate"] is False


def test_s7_retry_exception_clears_stale_5xx_status(monkeypatch):
    requests = pytest.importorskip("requests")
    monkeypatch.setattr(P.time, "sleep", lambda *_a: None)
    calls = {"n": 0}

    class R5:
        status_code = 503
        headers = {"Content-Type": "text/html"}
        def iter_content(self, _n):
            yield b"x"
        def close(self):
            pass

    class S:
        def get(self, *a, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                return R5()
            raise requests.exceptions.ConnectionError("down")
        trust_env = False

    class Hd(dict):
        pass
    class S2(S):
        headers = Hd()
        proxies = {}
    monkeypatch.setattr(requests, "Session", lambda: S2())
    r = P.make_http_get(())("https://openapi.twse.com.tw/v1/x", "direct")
    assert r["status"] is None and r["body"] is None and r["error"]
    rep = P.run_probe(http_get=lambda u, t: r, sleep_sec=0, now=NOW,
                      endpoints=(("r", "x", "https://openapi.twse.com.tw/v1/x", "json"),))
    assert rep["endpoints"][0]["transports"]["direct"]["outcome"] == "unreachable"
