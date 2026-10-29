"""scripts/analyze_moneydj_nav_series.py：以 synthetic 報告夾具驗證多日分類（不連網；夾具不是 MoneyDJ 真實回應）。"""
from __future__ import annotations

import gzip
import importlib.util
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))
_SPEC = importlib.util.spec_from_file_location("analyze_moneydj_nav_series", _ROOT / "scripts" / "analyze_moneydj_nav_series.py")
A = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(A)

_URL = {"TLZF9": "https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=TLZF9",
        "TLZF9-AL001": "https://x.moneydj.com/w/wb/wb01.djhtm?a=TLZF9-AL001",
        "TLZF9-24A7": "https://y.moneydj.com/w/wb/wb01.djhtm?a=TLZF9-24A7"}


def _o(inp, date, nav, name="某基金", kind=None, transport="direct", ccy=None):
    kind = kind or ("prod_nav30" if inp == "TLZF9" else "platform_wb")
    return {"input": inp, "base": "TLZF9", "kind": kind, "transport": transport, "parse_status": "ok", "http_status": 200,
            "nav": nav, "nav_date": date, "recent": [[date, nav]], "fund_name": name, "fund_name_source": "basic_info_url:u", "currency": ccy,
            "currency_source": "basic_info_url:u" if ccy else None, "url": _URL[inp], "raw": {"snippet_text": "x"}}


def _basic_acdd(ok=True):
    return [{"input": "ACDD01", "base": "ACDD01", "kind": "basic_info", "parse_status": "ok", "http_status": 200,
             "fund_name": "甲", "currency": "美元" if ok else None, "nav": None, "nav_date": None},
            {**_o("TLZF9", "2026-10-28", 1.0), "input": "ACDD01", "base": "ACDD01"}]


def _day(date, nav=8.4121, **over):
    obs = [_o("TLZF9", date, nav, ccy="美元"), _o("TLZF9-AL001", date, nav), _o("TLZF9-24A7", date, nav)]
    for o in obs:
        o.update(over.get(o["input"], {}))
    return obs + _basic_acdd()


def _write(tmp, runs):
    """runs: [(stamp, observations)]；寫成 results/<stamp>/report.json.gz。"""
    for i, (stamp, obs) in enumerate(runs):
        d = tmp / "results" / stamp
        d.mkdir(parents=True)
        rep = {"script_version": "moneydj_nav_equivalence/1.1", "generated_at_utc": f"2026-10-{20 + i:02d}T13:30:00+00:00",
               "executed_sha": "abc", "observations": obs, "transports": {"direct": "enabled", "nas_proxy": "proxy_not_configured"},
               "network_blocked": {"direct": {"blocked": False}, "nas_proxy": {"blocked": False}}}
        (d / "report.json.gz").write_bytes(gzip.compress(json.dumps(rep, ensure_ascii=False).encode()))
    return tmp


def _run(tmp, runs):
    reports, skipped = A.load_reports(_write(tmp, runs))
    return A.analyze(reports), skipped


def test_counts_distinct_nav_dates_not_runs(tmp_path):
    runs = [(f"r{i}", _day("2026-10-28")) for i in range(5)]      # 5 次 run、同一個 NAV 日
    res, _ = _run(tmp_path, runs)
    assert res["runs_count"] == 5 and res["distinct_nav_dates"] == 1 and res["distinct_consistent_nav_dates"] == 1
    assert res["classification"] == "insufficient_days"


def test_three_distinct_consistent_dates_is_strong(tmp_path):
    runs = [("r1", _day("2026-10-28")), ("r2", _day("2026-10-28")), ("r3", _day("2026-10-29", 8.5)), ("r4", _day("2026-10-30", 8.6))]
    res, _ = _run(tmp_path, runs)
    assert res["consistent_dates"] == ["2026-10-28", "2026-10-29", "2026-10-30"]
    assert res["classification"] == "strong_observational_evidence_same_series" and "strictly" not in res["classification"]
    assert res["acdd01_baseline_per_run"]["r1"] == "baseline_verified" and res["eqtal005_mapping_status"] == "UNVERIFIED"
    assert all(r["currency_evidence"]["platform_pages_currency_stated"] is False for r in res["runs"])


def test_two_dates_insufficient(tmp_path):
    res, _ = _run(tmp_path, [("r1", _day("2026-10-28")), ("r2", _day("2026-10-29"))])
    assert res["classification"] == "insufficient_days" and res["distinct_consistent_nav_dates"] == 2


def test_nav_conflict_on_same_date_wins_over_enough_days(tmp_path):
    runs = [("r1", _day("2026-10-28")), ("r2", _day("2026-10-29")), ("r3", _day("2026-10-30")),
            ("r4", _day("2026-10-29", **{"TLZF9-24A7": {"nav": 9.9, "recent": [["2026-10-29", 9.9]]}}))]
    res, _ = _run(tmp_path, runs)
    assert res["classification"] == "conflict_found" and res["date_conflicts"][0]["nav_date"] == "2026-10-29"


def test_fund_name_conflict_detected(tmp_path):
    res, _ = _run(tmp_path, [("r1", _day("2026-10-28", **{"TLZF9-AL001": {"fund_name": "別的基金"}}))])
    assert res["classification"] == "conflict_found" and res["date_conflicts"][0]["name_conflict"] is True


def test_publication_lag_is_date_anomaly_not_conflict_and_excluded_from_count(tmp_path):
    lag = _day("2026-10-28", **{"TLZF9-24A7": {"nav_date": "2026-10-27", "recent": [["2026-10-27", 8.4121]]}})
    runs = [("r1", lag), ("r2", _day("2026-10-29")), ("r3", _day("2026-10-30")), ("r4", _day("2026-10-31"))]
    res, _ = _run(tmp_path, runs)
    assert res["classification"] == "strong_observational_evidence_same_series" and res["run_level_conflicts"] == []
    assert res["date_anomalies"][0]["run"] == "r1" and res["reportable"] is True
    assert "2026-10-28" not in res["consistent_dates"] and res["consistent_dates"] == ["2026-10-29", "2026-10-30", "2026-10-31"]
    only, _ = _run(tmp_path / "b", [("r1", lag)])
    assert only["classification"] == "insufficient_days"


def test_name_evidence_surfaced_per_run(tmp_path):
    res, _ = _run(tmp_path, [("r1", _day("2026-10-28"))])
    assert res["runs"][0]["name_evidence"]["platform_names_stated"] is False
    assert res["runs"][0]["observational"] == "observational_consistent_day"


def test_blocked_when_no_nav_anywhere(tmp_path):
    res, _ = _run(tmp_path, [("r1", [])])
    assert res["classification"] == "blocked" and res["distinct_nav_dates"] == 0


def test_prod_page_of_dashed_input_does_not_count_as_platform_evidence(tmp_path):
    obs = _day("2026-10-28")
    obs[1]["kind"] = "prod_nav30"   # AL001 只有 prod 頁（可能回傳 base 頁）→ 不入矩陣
    res, _ = _run(tmp_path, [("r1", obs)])
    assert res["date_matrix"][0]["status"] == "partial" and "TLZF9-AL001" in res["date_matrix"][0]["missing_inputs"]


def test_baseline_failed_and_mapping_observed_surface(tmp_path):
    obs = _day("2026-10-28")[:-2] + _basic_acdd(ok=False)
    obs.append({**_o("TLZF9", "2026-10-28", 1.0), "input": "ACDD01-EQTAL005", "raw": {"snippet_text": "ACDD01 EQTAL005"}})
    res, _ = _run(tmp_path, [("r1", obs)])
    assert res["acdd01_baseline_per_run"]["r1"] == "baseline_failed" and res["eqtal005_mapping_status"] == "OBSERVED_ON_PAGE"


def test_skips_bad_and_foreign_files_and_renders(tmp_path):
    _write(tmp_path, [("r1", _day("2026-10-28"))])
    bad = tmp_path / "results" / "bad"
    bad.mkdir()
    (bad / "report.json.gz").write_bytes(b"not gzip")
    other = tmp_path / "results" / "other"
    other.mkdir()
    (other / "report.json.gz").write_bytes(gzip.compress(b'{"script_version": "twse_eps/2"}'))
    reports, skipped = A.load_reports(tmp_path)
    assert len(reports) == 1 and len(skipped) == 2
    md = A.render_markdown(A.analyze(reports), skipped)
    assert "classification" in md and "| 2026-10-28 | all_three_equal |" in md and "www.moneydj.com" in md
    assert A.main([str(tmp_path)]) == 0
