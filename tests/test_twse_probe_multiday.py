"""離線測試：BL-0509 多日 probe 新增行為（條款 redirect 白名單跟隨、時序欄位、openapi vs rwd、跨 run 分析腳本）。

全部以假 fetcher／合成報告，不發任何網路請求。射程外：不驗真實 TWSE 條款頁的內容與跳轉；不驗 workflow（見
`test_twse_eps_probe_workflow.py`）。
"""
from __future__ import annotations

import gzip
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, _ROOT / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


P = _load("probe_twse_eps_md", "scripts/probe_twse_eps.py")
A = _load("analyze_twse_probe_series_md", "scripts/analyze_twse_probe_series.py")

NOW = datetime(2026, 10, 27, 4, 0, tzinfo=timezone.utc)
FAKE_PROXY = "http://probeuser:Sup3rSecretPw@nas-internal.example.invalid:31280"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("PROXY_URL", raising=False)
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    monkeypatch.setenv("PROBE_EXECUTED_SHA", "b" * 40)


def _html(text, status=200):
    body = text.encode("utf-8")
    return {"status": status, "content_type": "text/html; charset=utf-8", "latency_ms": 3.0, "bytes": len(body),
            "body": body, "error": None}


def _redir(loc, status=302):
    return {"status": status, "content_type": "text/html", "latency_ms": 1.0, "bytes": 0, "body": None,
            "error": None, "location": loc}


def _json(obj):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    return {"status": 200, "content_type": "application/json", "latency_ms": 5.0, "bytes": len(body),
            "body": body, "error": None}


def _fake(routes):
    calls = []

    def http_get(url, transport):
        calls.append((url, transport))
        v = routes.get(url)
        if v is None:
            return _json([])
        return v(url) if callable(v) else v
    http_get.calls = calls
    return http_get


EP = ("t", "terms_reach", "https://www.twse.com.tw/zh/page/terms.html", "reach")
OA = "https://openapi.twse.com.tw/"


# ───────────── (a) 條款 redirect：白名單跟隨 ─────────────

def test_terms_follows_whitelisted_hops_and_counts_keywords_without_storing_text():
    page = "<html>本網站使用條款。著作權屬證交所。授權使用。商業行為另議，商業用途請洽。 SECRET_PAGE_TEXT_MARKER</html>"
    f = _fake({EP[2]: _redir("/zh/page/terms/"),
               "https://www.twse.com.tw/zh/page/terms/": _redir("https://openapi.twse.com.tw/terms.html"),
               "https://openapi.twse.com.tw/terms.html": _html(page)})
    res, _a, _s = P.probe_one(f, EP, "direct", NOW.date(), (), False)
    assert res["outcome"] == "reachable" and res["n_hops"] == 2 and res["redirect_stop_reason"] == "final"
    assert [h["host"] for h in res["redirect_chain"]] == ["www.twse.com.tw", "www.twse.com.tw", "openapi.twse.com.tw"]
    assert res["redirect_chain"][-1]["path"] == "/terms.html" and res["final_path"] == "/terms.html"
    tp = res["terms_page"]
    assert tp["counts"] == {"使用條款": 1, "授權": 1, "著作權": 1, "商業": 2}
    assert tp["any_present"] is True and tp["status"] == "page_exists_with_keywords" and tp["page_text_stored"] is False
    raw = json.dumps(res, ensure_ascii=False)
    assert "SECRET_PAGE_TEXT_MARKER" not in raw and "證交所" not in raw          # 不存整頁文字
    assert res["redirect_chain"][-1]["body_sha256"] and res["redirect_chain"][-1]["body_bytes"] == len(page.encode())


def test_terms_stops_at_non_whitelisted_host_and_never_requests_it():
    f = _fake({EP[2]: _redir("https://evil.example.com/terms")})
    res, *_ = P.probe_one(f, EP, "direct", NOW.date(), (), False)
    assert res["outcome"] == "blocked_redirect"
    assert res["redirect_chain"][0]["next_host"] == "evil.example.com"
    assert res["redirect_chain"][0]["next_blocked"] == "host_not_in_allowlist"
    assert [u for u, _t in f.calls] == [EP[2]]                                   # 非白名單目標從未被請求


def test_terms_blocks_http_downgrade_even_on_whitelisted_host():
    f = _fake({EP[2]: _redir("http://www.twse.com.tw/terms")})
    res, *_ = P.probe_one(f, EP, "direct", NOW.date(), (), False)
    assert res["outcome"] == "blocked_redirect" and res["redirect_chain"][0]["next_blocked"] == "not_https"
    assert len(f.calls) == 1


def test_terms_hop_limit_and_loop():
    n = {"i": 0}

    def chain(_url):
        n["i"] += 1
        return _redir(f"https://www.twse.com.tw/h{n['i']}")
    fake_routes = lambda url, t: chain(url)  # noqa: E731
    res, *_ = P.probe_one(fake_routes, EP, "direct", NOW.date(), (), False)
    assert res["outcome"] == "redirect_limit_exceeded"
    assert len(res["redirect_chain"]) == P.MAX_REDIRECT_HOPS + 1 and P.MAX_REDIRECT_HOPS == 3
    loop = _fake({EP[2]: _redir(EP[2])})
    res2, *_ = P.probe_one(loop, EP, "direct", NOW.date(), (), False)
    assert res2["outcome"] == "redirect_loop" and len(loop.calls) == 1


def test_terms_page_without_keywords_and_error_statuses():
    ok = _fake({EP[2]: _html("<html>nothing relevant</html>")})
    res, *_ = P.probe_one(ok, EP, "direct", NOW.date(), (), False)
    assert res["terms_page"]["status"] == "page_exists_no_keywords" and res["terms_page"]["any_present"] is False
    nf = _fake({EP[2]: _html("nf", status=404)})
    assert P.probe_one(nf, EP, "direct", NOW.date(), (), False)[0]["outcome"] == "http_error"
    down = _fake({EP[2]: {"status": None, "content_type": None, "latency_ms": 1.0, "bytes": None, "body": None, "error": "boom"}})
    assert P.probe_one(down, EP, "direct", NOW.date(), (), False)[0]["outcome"] == "unreachable"


def test_data_endpoints_still_do_not_follow_redirects():
    ep = ("d", "taiex", "https://openapi.twse.com.tw/v1/x", "json")
    f = _fake({ep[2]: _redir("https://www.twse.com.tw/elsewhere")})
    res, *_ = P.probe_one(f, ep, "direct", NOW.date(), (), False)
    assert res["outcome"] == "redirect_not_followed" and len(f.calls) == 1 and "redirect_chain" not in res
    assert P.FOLLOW_GROUPS == {"terms_reach"}


def test_proxy_host_masked_in_redirect_chain(monkeypatch):
    monkeypatch.setenv("PROXY_URL", FAKE_PROXY)
    sec = P.secret_literals()
    f = _fake({EP[2]: _redir("https://nas-internal.example.invalid/x")})
    res, *_ = P.probe_one(f, EP, "direct", NOW.date(), sec, True)
    raw = json.dumps(res, ensure_ascii=False)
    assert "nas-internal.example.invalid" not in raw and "Sup3rSecretPw" not in raw


def test_swagger_terms_links_extracted_full_and_followed_only_if_whitelisted(tmp_path):
    long_path = "zh/page/terms/" + "x" * 120 + "/use.html"                       # 超過 80 字：不得截斷
    full = f"https://www.twse.com.tw/{long_path}"
    desc = f"本平臺提供API。<br><br>[使用條款]({full})。外部：https://example.org/tos 與 http://www.twse.com.tw/old"
    sw = {"info": {"title": "t", "version": "1", "description": desc}, "paths": {}}
    info = P.extract_swagger_terms_links(sw)
    urls = [l["url"] for l in info["links"]]
    assert full in urls and "https://example.org/tos" in urls and "http://www.twse.com.tw/old" in urls
    allowed = {l["url"]: l["allowed"] for l in info["links"]}
    assert allowed[full] is True and allowed["https://example.org/tos"] is False
    assert allowed["http://www.twse.com.tw/old"] is False                         # http 不在白名單
    assert next(l for l in info["links"] if l["url"] == full)["host"] == "www.twse.com.tw"
    f = _fake({full: _html("使用條款 授權")})
    out = P.build_terms_research(f, sw, set(), (), False, NOW.date())
    assert out["license_verification"] == "⬜ 授權條款尚未完成驗證"
    assert [u for u, _t in f.calls] == [full]                                     # 只請求白名單內者，且只走 direct（未設 proxy）
    assert out["followed"][0]["transports"]["nas_proxy"]["outcome"] == "proxy_not_configured"
    assert out["followed"][0]["transports"]["direct"]["terms_page"]["counts"]["使用條款"] == 1
    # 與靜態端點重複者不再重打
    f2 = _fake({})
    out2 = P.build_terms_research(f2, sw, {full}, (), False, NOW.date())
    assert f2.calls == [] and out2["followed"] == []


def test_run_probe_report_has_terms_research_even_without_swagger():
    nf = {"status": 404, "content_type": "text/html", "latency_ms": 1.0, "bytes": 2, "body": b"nf", "error": None}
    rep = P.run_probe(http_get=_fake({"https://openapi.twse.com.tw/v1/swagger.json": nf}), sleep_sec=0, now=NOW)
    assert rep["terms_research"]["license_verification"] == "⬜ 授權條款尚未完成驗證"
    assert rep["terms_research"]["swagger_description"] == {"outcome": "swagger_missing"}
    assert rep["schema_version"] == 2


# ───────────── (b)(c) 時序欄位與 openapi vs rwd ─────────────

RWD = {"stat": "OK", "date": "20261027", "title": "t", "fields": ["日期", "成交股數", "發行量加權股價指數"],
       "data": [["115/10/21", "1", "100.0"], ["115/10/22", "2", ""], ["115/10/23", "3", "-"], ["115/10/26", "4", "101.0"]]}
OAPI = [{"Date": "1151021", "TAIEX": "99"}, {"Date": "1151022", "TAIEX": ""}]


def test_timeseries_fields_for_dict_and_list_payloads():
    ts = P.analyze_json(RWD)["timeseries"]
    assert ts["row_count"] == 4 and ts["top_level_date_raw"] == "20261027" and ts["top_level_date"] == "2026-10-27"
    assert ts["row_date_min"] == "2026-10-21" and ts["row_date_max"] == "2026-10-26" and ts["latest_row_date"] == "2026-10-26"
    assert ts["latest_source_date"] == "2026-10-27"                               # 與 freshness 同口徑（含頂層 date）
    assert ts["head_date_min"] == "2026-10-21" and ts["tail_date_max"] == "2026-10-26" and ts["row_order"] == "ascending"
    assert ts["empty_string_cells"] == 1 and ts["dash_cells"] == 1 and ts["null_cells"] == 0 and ts["n_cells"] == 12
    assert ts["missing_by_field"] == {"發行量加權股價指數": {"empty": 1, "dash": 1, "null": 0}}   # 只計數，不補值
    tl = P.analyze_json(OAPI)["timeseries"]
    assert tl["row_count"] == 2 and tl["top_level_date_raw"] is None and tl["latest_source_date"] == "2026-10-22"


def test_head_tail_use_n_rows_each_side():
    rows = [{"Date": f"11510{d:02d}", "v": "1"} for d in range(1, 21)]
    ts = P.analyze_json(rows)["timeseries"]
    assert ts["head_date_max"] == "2026-10-05" and ts["tail_date_min"] == "2026-10-16" and ts["head_tail_n"] == 5


def test_schema_hash_tracks_field_names_not_values():
    a = P.analyze_json([{"Date": "1151021", "x": "1"}])["timeseries"]["schema_hash"]
    b = P.analyze_json([{"Date": "1151022", "x": "9"}, {"Date": "1151023", "x": "8"}])["timeseries"]["schema_hash"]
    c = P.analyze_json([{"Date": "1151021", "y": "1"}])["timeseries"]["schema_hash"]
    d = P.analyze_json([{"x": "1", "Date": "1151021"}])["timeseries"]["schema_hash"]
    assert a == b and a != c and a != d


def test_no_date_columns_gives_none_not_filled():
    ts = P.analyze_json([{"a": "1"}])["timeseries"]
    assert ts["latest_source_date"] is None and ts["row_date_min"] is None and ts["head_date_min"] is None


def _routes_pair(openapi_date="1151022"):
    return {
        "https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK": _json([{"Date": openapi_date, "TAIEX": "1"}]),
        "https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK?response=json": _json(RWD),
    }


def test_openapi_vs_rwd_diff_days_and_missing_side_is_none():
    rep = P.run_probe(http_get=_fake(_routes_pair()), sleep_sec=0, now=NOW)
    rows = {(r["pair"], r["transport"]): r for r in rep["openapi_vs_rwd"]}
    fm = rows[("FMTQIK", "direct")]
    assert fm["openapi_latest_source_date"] == "2026-10-22" and fm["rwd_latest_source_date"] == "2026-10-27"
    assert fm["diff_days"] == 5
    assert fm["row_date_diff_days"] == 4                                          # 列內日期 10-26 − 10-22
    mi = rows[("MI_INDEX", "direct")]                                             # 預設假回應為空 list → 沒有日期
    assert mi["diff_days"] is None and mi["reason"]
    assert rows[("FMTQIK", "nas_proxy")]["diff_days"] is None                     # 未設 proxy：不補值
    assert "proxy_not_configured" in rows[("FMTQIK", "nas_proxy")]["reason"]


def test_no_leak_and_still_no_credentials_with_new_fields(monkeypatch, tmp_path):
    monkeypatch.setenv("PROXY_URL", FAKE_PROXY)
    routes = dict(_routes_pair())
    routes["https://openapi.twse.com.tw/v1/swagger.json"] = _json(
        {"info": {"description": "[條款](https://www.twse.com.tw/zh/page/terms/use)"}, "paths": {}})
    routes["https://www.twse.com.tw/zh/page/terms/use"] = _html("使用條款 nas-internal.example.invalid Sup3rSecretPw")
    out = tmp_path / "r.json.gz"
    P.run_probe(http_get=_fake(routes), out_path=str(out), sleep_sec=0, now=NOW)
    raw = gzip.decompress(out.read_bytes()).decode("utf-8")
    for s in ("Sup3rSecretPw", "probeuser", "nas-internal.example.invalid", "31280"):
        assert s not in raw, s
    assert "swagger_terms_link_1" in raw


# ───────────── 2. 跨 run 分析腳本 ─────────────

def _rep(taipei_dt, latest, sha, rows=10, schema="s1", empty=0, openapi_diff=None, terms=None):
    utc = taipei_dt.astimezone(timezone.utc)
    ts = {"row_count": rows, "schema_hash": schema, "latest_source_date": latest, "n_cells": 100,
          "empty_string_cells": empty, "dash_cells": 0, "null_cells": 0,
          "missing_by_field": ({"PEratio": {"empty": empty, "dash": 0, "null": 0}} if empty else {})}
    rep = {"schema_version": 2, "probe": "twse_eps", "generated_at_utc": utc.isoformat(),
           "run_date_taipei": taipei_dt.date().isoformat(),
           "endpoints": [{"id": "openapi_BWIBBU_ALL", "group": "pe", "transports": {
               "direct": {"outcome": "ok", "body_sha256": sha, "timeseries": ts,
                          "freshness": {"latest_source_date": latest}}}}],
           "openapi_vs_rwd": [], "terms_research": terms or {}}
    if openapi_diff is not None:
        rep["openapi_vs_rwd"] = [{"pair": "BWIBBU", "transport": "direct", "openapi_latest_source_date": latest,
                                  "rwd_latest_source_date": "2026-10-28", "diff_days": openapi_diff,
                                  "row_date_diff_days": None, "reason": None}]
    return rep


def _write(tmp, name, rep):
    d = tmp / name
    d.mkdir()
    (d / "report.json.gz").write_bytes(gzip.compress(json.dumps(rep, ensure_ascii=False).encode("utf-8")))


TP = timezone(timedelta(hours=8))


def test_analyzer_single_sample_says_insufficient(tmp_path):
    _write(tmp_path, "a", _rep(datetime(2026, 10, 27, 19, 37, tzinfo=TP), "2026-10-22", "a" * 64))
    reports, skipped = A.load_reports([tmp_path])
    md = A.analyze(reports, skipped)
    assert md.count("樣本不足") >= 3 and "更新頻率：**樣本不足**" in md
    assert "⬜ 授權條款尚未完成驗證" in md and "不補 0" in md


def test_analyzer_multi_run_changes_lag_revision_and_missing(tmp_path):
    _write(tmp_path, "r1", _rep(datetime(2026, 10, 28, 6, 43, tzinfo=TP), "2026-10-27", "a" * 64, rows=10, empty=2, openapi_diff=1))
    _write(tmp_path, "r2", _rep(datetime(2026, 10, 28, 19, 37, tzinfo=TP), "2026-10-27", "b" * 64, rows=10, empty=2, openapi_diff=1))
    _write(tmp_path, "r3", _rep(datetime(2026, 10, 29, 6, 43, tzinfo=TP), "2026-10-28", "c" * 64, rows=11, schema="s2", empty=5, openapi_diff=0))
    reports, skipped = A.load_reports([tmp_path])
    assert [A.run_label(r) for r in reports] == ["10-28 06:43", "10-28 19:37", "10-29 06:43"]
    md = A.analyze(reports, skipped)
    assert "相鄰 run sha 變 2/2 次" in md and "變（2 種）" in md and "10～11（變）" in md
    # lag：run_date_taipei − latest
    assert "| 10-28 06:43 | 2026-10-27 | 1 |" in md and "| 10-29 06:43 | 2026-10-28 | 1 |" in md
    # 發布延遲：2026-10-28 首次出現於 10-29 06:43 → 距該日 00:00 約 30.7 小時（上界）
    assert "| 2026-10-28 | 10-29 06:43 | 30.7 |" in md and "上界" in md
    # 同一來源日期 2026-10-27 在 r1、r2 sha 不同 → 疑似 revision，但註明不等於確認
    assert "sha 不一致：1" in md and "sha 不同 ≠ 已確認 revision" in md
    assert "2.0000%" in md and "5.0000%" in md and '"PEratio": 2' in md
    assert "diff_days 範圍 0～1" in md and "不穩定" in md
    assert "更新頻率：**樣本不足**" in md                                         # 只有 2 個台北日 < 3


def test_analyzer_no_revision_when_no_shared_source_date(tmp_path):
    _write(tmp_path, "r1", _rep(datetime(2026, 10, 28, 6, 43, tzinfo=TP), "2026-10-27", "a" * 64))
    _write(tmp_path, "r2", _rep(datetime(2026, 10, 29, 6, 43, tzinfo=TP), "2026-10-28", "b" * 64))
    md = A.analyze(*A.load_reports([tmp_path]))
    assert "沒有任何端點在 ≥ 2 份報告中出現同一個" in md and "sha 不一致" not in md


def test_analyzer_accepts_files_skips_garbage_and_cli_out(tmp_path, capsys):
    good = tmp_path / "x_report.json.gz"
    good.write_bytes(gzip.compress(json.dumps(_rep(datetime(2026, 10, 27, 19, 37, tzinfo=TP), "2026-10-22", "a" * 64)).encode()))
    (tmp_path / "junk.json.gz").write_bytes(b"not gzip")
    (tmp_path / "other.json.gz").write_bytes(gzip.compress(b'{"probe": "other"}'))
    out = tmp_path / "o" / "s.md"
    assert A.main([str(tmp_path), "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert printed == out.read_text(encoding="utf-8") and "略過" in printed


def test_analyzer_runs_on_real_v1_evidence_without_crashing():
    p = _ROOT / "docs" / "evidence" / "probe_twse_eps" / "20261027T143156Z_run40521810949_report.json.gz"
    if not p.exists():
        pytest.skip("evidence file absent")
    md = A.analyze(*A.load_reports([p]))
    assert "樣本不足" in md and "schema_version 1" in md


def test_analyzer_is_stdlib_only_and_has_no_network():
    src = (_ROOT / "scripts" / "analyze_twse_probe_series.py").read_text(encoding="utf-8")
    for bad in ("import requests", "import urllib", "import socket", "import subprocess", "PROXY_URL"):
        assert bad not in src
