"""BL-0545 Phase 1 唯讀覆蓋率探針 -- T1~T10 驗收測試。

協定出處:`docs/evidence/bl0545_active_sheet_coverage_probe_status_2026_11_07.md` 第 4.4 節。
授權:DEC-2026-11-07-03。本檔全部離線(注入 fetcher / mapping / clock),不連網、不讀任何憑證。
T3 依本次限定改為 shadow 比較:DG2 只做平行差異報告,不影響主分組。
負控(假的敏感字串)一律在記憶體現編,不寫進檔案。
"""
from __future__ import annotations

import ast
import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts import bl0545_coverage_probe as probe

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "scripts" / "bl0545_coverage_probe.py"
FIXED = datetime(2026, 11, 7, 0, 0, 0, tzinfo=timezone.utc)


def _clock():
    return FIXED


def _ok(**inputs):
    return {"status": "ok", "inputs": inputs}


FULL_USD = _ok(tr1y_pct=10.0, adr_pct=6.0, sharpe=1.2, sigma_pct=12.0, fund_ccy="USD", fx_cv_pct=3.0)
FULL_TWD = _ok(tr1y_pct=10.0, adr_pct=6.0, sharpe=1.2, sigma_pct=12.0, fund_ccy="TWD")
JPY = _ok(tr1y_pct=10.0, adr_pct=6.0, sharpe=1.2, sigma_pct=12.0, fund_ccy="JPY")
TWO_DIM = _ok(sharpe=1.2, sigma_pct=12.0, fund_ccy="USD")


def _rows(*pairs):
    return [{"policy_id": p, "fund_code": c} for p, c in pairs]


def _run(rows, funds=None, **kw):
    table = funds or {}
    calls = []

    def fetcher(key):
        calls.append(key)
        return table.get(key, {"status": "not_attempted", "reason": "no_fixture_entry"})

    out = probe.run_probe(rows, fetcher=fetcher, clock=_clock, **kw)
    out["_calls"] = calls
    return out


def _text(out):
    o = {k: v for k, v in out.items() if k != "_calls"}
    return probe.render_json(o)


def _fund(out, key):
    return next(p for p in out["per_fund"] if p["canonical_key_or_raw_code"] == key)


# ───────────────────────── T1 ─────────────────────────

def test_t1_empty_list_nulls_no_division():
    out = _run([])
    assert out["population"]["unique_funds"] == 0
    assert out["population"]["holding_rows"] == 0
    assert out["valid"] is True
    for dim in probe.DIMENSIONS:
        assert all(v is None for v in out["dimensions"][dim].values())
    assert out["per_fund"] == []
    text = _text(out)
    assert "ratio" not in text and "%" not in text


def test_t1_codes_text_blank_and_comments_only():
    assert probe.parse_codes_text("\n  \n# 註解\n") == []


# ───────────────────────── T2 ─────────────────────────

def test_t2_same_code_two_policies_one_fetch():
    out = _run(_rows(("A", "acdd01"), ("B", "ACDD01")), {"ACDD01": FULL_USD})
    assert out["population"]["holding_rows"] == 2
    assert out["population"]["unique_funds"] == 1
    assert out["_calls"] == ["ACDD01"]
    f = _fund(out, "ACDD01")
    assert len(f["policy_rows"]) == 2 and len(set(f["policy_rows"])) == 2
    assert "A" not in f["policy_rows"] and "B" not in f["policy_rows"]  # 不輸出原始 policy_id


def test_t2_parse_two_column_csv_keeps_policy_rows():
    rows = probe.parse_codes_text("policy_id,fund_code\nP1,AAA111\nP2,AAA111\nBBB222\n")
    assert [r["policy_id"] for r in rows] == ["P1", "P2", None]
    out = _run(rows, {"AAA111": FULL_USD, "BBB222": FULL_USD})
    assert out["population"]["holding_rows"] == 3 and out["population"]["unique_funds"] == 2


# ───────────────────────── T3(shadow 化)─────────────────────────

class _Ident:
    def __init__(self, ck, status, original):
        self.canonical_key, self.verification_status, self.original_code = ck, status, original


def _merging_shadow(code, **_kw):
    """假的 DG2:把 AAA111 與 AAA111-XY 視為同一 canonical(只用於測試差異揭露)。"""
    if code.startswith("AAA111"):
        return _Ident("AAA111", "base_resolved_attributes_unverified", code)
    return _Ident(code, "base_resolved_attributes_unverified", code)


def test_t3_shadow_diff_disclosed_primary_unchanged():
    rows = _rows(("A", "AAA111"), ("B", "AAA111-XY"))
    plain = _run(rows, {"AAA111": FULL_USD, "AAA111-XY": FULL_USD})
    out = _run(rows, {"AAA111": FULL_USD, "AAA111-XY": FULL_USD}, shadow_resolver=_merging_shadow)
    # 主分組不受 shadow 影響
    assert out["population"]["unique_funds"] == plain["population"]["unique_funds"] == 2
    assert out["identity"]["primary_groups"] == plain["identity"]["primary_groups"]
    sd = out["identity"]["shadow_diff"]
    assert sd["evaluated"] is True and sd["differs"] is True
    assert sd["primary_unique_count"] == 2 and sd["shadow_unique_count"] == 1
    assert sd["entries"][0]["codes"] == ["AAA111", "AAA111-XY"]
    assert sd["entries"][0]["primary_group_count"] == 2 and sd["entries"][0]["shadow_group_count"] == 1
    assert "base_resolved_attributes_unverified" in set(sd["entries"][0]["shadow_verification_status"].values())


def test_t3_real_dg2_runs_parallel_and_never_touches_flag(monkeypatch):
    from shared import fund_identity as flags
    assert flags.DG2_SHADOW_ENABLED is False
    out = _run(_rows(("A", "ACDD01"), ("B", "acdd01")), {"ACDD01": FULL_USD})
    sd = out["identity"]["shadow_diff"]
    assert sd["evaluated"] is True and sd["differs"] is False
    assert flags.DG2_SHADOW_ENABLED is False  # 預設關閉,探針自身仍可平行比較且未修改旗標
    monkeypatch.setattr(flags, "DG2_SHADOW_ENABLED", True)
    out2 = _run(_rows(("A", "ACDD01")), {"ACDD01": FULL_USD})
    assert out2["population"]["unique_funds"] == 1
    assert flags.DG2_SHADOW_ENABLED is True  # 探針沒有改寫它


def test_t3_shadow_failure_only_recorded():
    def boom(code, **_kw):
        raise RuntimeError("boom " + secrets.token_hex(4))

    out = _run(_rows(("A", "ACDD01")), {"ACDD01": FULL_USD}, shadow_resolver=boom)
    sd = out["identity"]["shadow_diff"]
    assert sd["evaluated"] is False and sd["shadow_error"] == "RuntimeError"
    assert out["valid"] is True and out["population"]["fetch_success"] == 1
    assert "boom" not in _text(out)  # 例外訊息不輸出


# ───────────────────────── T4 / T5 ─────────────────────────

def test_t4_twd_not_applicable_not_in_applicable_n():
    out = _run(_rows(("A", "TWD001")), {"TWD001": FULL_TWD})
    fx = _fund(out, "TWD001")["dimensions"]["fx_risk"]
    assert fx["status"] == "not_applicable" and fx["production_status"] == "n/a"
    c = out["dimensions"]["fx_risk"]
    assert c["not_applicable"] == 1 and c["missing"] == 0 and c["applicable_n"] == 0
    assert _fund(out, "TWD001")["coverage_disclosure"]["text"] == "4/4"


def test_t5_non_usd_unsupported_with_production_missing():
    out = _run(_rows(("A", "JPY001")), {"JPY001": JPY})
    fx = _fund(out, "JPY001")["dimensions"]["fx_risk"]
    assert fx["status"] == "unsupported"
    assert fx["reason_code"] == "probe_label_fx_provider_usd_only"
    assert fx["production_status"] == "missing"
    assert out["dimensions"]["fx_risk"]["unsupported"] == 1
    assert out["dimensions"]["fx_risk"]["applicable_n"] == 1  # unsupported 計入 applicable_n(協定約定)


def test_t5_usd_without_cv_and_empty_ccy_stay_missing_not_unsupported():
    out = _run(_rows(("A", "USD001"), ("B", "NOC001")),
               {"USD001": _ok(sharpe=1.0, fund_ccy="USD"), "NOC001": _ok(sharpe=1.0)})
    assert _fund(out, "USD001")["dimensions"]["fx_risk"]["status"] == "missing"
    assert _fund(out, "USD001")["dimensions"]["fx_risk"]["reason_code"] == "fx_cv_pct_unavailable"
    assert _fund(out, "NOC001")["dimensions"]["fx_risk"]["reason_code"] == "fund_ccy_absent"
    assert out["dimensions"]["fx_risk"]["unsupported"] == 0


# ───────────────────────── T6 ─────────────────────────

def test_t6_two_dimensions_show_2_over_n():
    out = _run(_rows(("A", "TWO001")), {"TWO001": TWO_DIM})
    d = _fund(out, "TWO001")["coverage_disclosure"]
    assert d["scored_n"] == 2 and d["applicable_n"] == 5 and d["text"] == "2/5"
    assert d["missing_dimensions"] == ["coverage", "fx_risk", "trend"]
    assert "5/5" not in _text(out)


# ───────────────────────── T7 ─────────────────────────

def test_t7_fetch_failure_excluded_and_conserved():
    funds = {"AAA111": FULL_USD, "BBB222": {"status": "failed", "reason": "http_timeout"}}
    out = _run(_rows(("A", "AAA111"), ("B", "BBB222"), ("C", "not a code!")), funds)
    p = out["population"]
    assert (p["fetch_success"], p["fetch_failed"], p["not_attempted"], p["identity_unresolved"]) == (1, 1, 1, 1)
    assert p["fetch_success"] + p["fetch_failed"] + p["not_attempted"] == p["unique_funds"] == 3
    assert out["dimensions"]["sharpe"]["scored_n"] == 1  # 失敗/未嘗試者不進任何維度計數
    bad = _fund(out, "BBB222")
    assert bad["fetch_status"] == "failed" and bad["fetch_failure_reason"] == "http_timeout"
    assert bad["dimensions"] is None
    assert out["valid"] is True


def test_t7_fetcher_exception_recorded_without_retry_or_message():
    calls = []

    def fetcher(key):
        calls.append(key)
        raise TimeoutError("連線到內網 10.0.0.5 逾時")

    out = probe.run_probe(_rows(("A", "AAA111")), fetcher=fetcher, clock=_clock)
    assert calls == ["AAA111"]  # 不重試
    f = _fund(out, "AAA111")
    assert f["fetch_status"] == "failed" and f["fetch_failure_reason"] == "fetcher_exception_timeouterror"
    assert "10.0.0.5" not in probe.render_json(out)


def test_t7_no_fetcher_is_not_attempted_live_not_implemented():
    out = probe.run_probe(_rows(("A", "AAA111")), clock=_clock)
    assert out["population"]["not_attempted"] == 1 and out["population"]["fetch_success"] == 0
    assert _fund(out, "AAA111")["fetch_failure_reason"] == "live_mode_not_implemented_no_fetcher"
    assert out["live_mode"] == "NOT IMPLEMENTED"
    assert all(v is None for v in out["dimensions"]["sharpe"].values())  # 全未量測 → null,不是 0


# ───────────────────────── T8 ─────────────────────────

def test_t8_proxy_flag_distinguishable_without_changing_counts():
    fx = {"PRX001": {**FULL_USD, "dimension_meta": {"trend": {"proxy": True, "source_tag": "ret1y_fallback",
                                                              "obs_date": "2026-11-06"}}}}
    out = _run(_rows(("A", "PRX001")), fx)
    t = _fund(out, "PRX001")["dimensions"]["trend"]
    assert t["proxy"] is True and t["status"] == "scored" and t["obs_date"] == "2026-11-06"
    assert out["dimensions"]["trend"]["scored_n"] == 1 and out["dimensions"]["trend"]["proxy_scored_n"] == 1
    assert out["dimensions"]["sharpe"]["proxy_scored_n"] == 0
    # 探針不自行推斷 proxy
    assert _fund(_run(_rows(("A", "PRX001")), {"PRX001": FULL_USD}), "PRX001")["dimensions"]["trend"]["proxy"] is False


# ───────────────────────── T9 ─────────────────────────

def _valid_out():
    return _run(_rows(("A", "AAA111"), ("B", "TWD001"), ("C", "JPY001")),
                {"AAA111": FULL_USD, "TWD001": FULL_TWD, "JPY001": JPY})


def test_t9_conservation_holds_for_every_dimension():
    out = _valid_out()
    n = out["population"]["fetch_success"]
    for dim in probe.DIMENSIONS:
        c = out["dimensions"][dim]
        assert c["scored_n"] + c["not_applicable"] + c["unsupported"] + c["missing"] == n
    assert probe.check_invariants(out) == []


def test_t9_violation_marks_invalid_and_does_not_patch_numbers():
    out = _valid_out()
    out["dimensions"]["sharpe"]["missing"] += 1
    reasons = probe.check_invariants(out)
    assert any(r.startswith("T9_sharpe") for r in reasons)
    out2 = _valid_out()
    out2["population"]["fetch_failed"] += 1
    assert any(r.startswith("T7") for r in probe.check_invariants(out2))


def test_t9_probe_vs_production_coverage_mismatch_is_invalid(monkeypatch, tmp_path):
    def lying_health(**_kw):
        return {"factors": {"coverage": 1, "sharpe": 1, "trend": 1, "volatility": 1, "fx_risk": 1},
                "fx_risk_status": "scored",
                "coverage": {"n_scored": 4, "n_applicable": 5, "n_total": 5, "missing": ["fx_risk"]}}

    out = _run(_rows(("A", "AAA111")), {"AAA111": FULL_USD}, health_fn=lying_health)
    assert out["valid"] is False
    assert any("coverage_mismatch" in r for r in out["invalid_reasons"])
    # CLI:invalid → 非 0,且輸出標 valid=false
    fx = {"schema": probe.FIXTURE_SCHEMA, "holdings": [{"policy_id": "A", "fund_code": "AAA111"}],
          "funds": {"AAA111": FULL_USD}}
    fp, op = tmp_path / "fx.json", tmp_path / "out.json"
    fp.write_text(json.dumps(fx), encoding="utf-8")
    real = probe.derive_dimensions

    def bad(inp, meta, health_fn=None):
        r = real(inp, meta, health_fn)
        r["consistent_with_production"] = False
        return r

    monkeypatch.setattr(probe, "derive_dimensions", bad)
    assert probe.main(["--fixture", str(fp), "--out", str(op)]) == 3
    assert json.loads(op.read_text(encoding="utf-8"))["valid"] is False


# ───────────────────────── T10 / 洩漏 ─────────────────────────

def test_t10_no_secrets_in_output_with_in_memory_negative_controls():
    email = f"{secrets.token_hex(4)}@{secrets.token_hex(3)}.example"
    sheet_id = secrets.token_urlsafe(33)  # 44 字元
    bearer = "ya29." + secrets.token_hex(20)
    internal = "10.%d.%d.%d" % (secrets.randbelow(200), secrets.randbelow(200), secrets.randbelow(200))
    url = f"http://{internal}/{secrets.token_hex(4)}"
    rows = _rows((email, email), (sheet_id, sheet_id), ("P", bearer), ("P", url), ("P", "AAA111"))
    funds = {"AAA111": {**FULL_USD, "dimension_meta": {"coverage": {"source_tag": email, "obs_date": url}}}}
    out = _run(rows, funds, as_of=email, main_sha=bearer)
    text = _text(out)
    for needle in (email, sheet_id, bearer, internal, url, "ya29"):
        assert needle not in text
    assert out["source"]["active_sheet_id_hash"] is None and out["source"]["account_sub_hash"] is None
    for k in ("client_secret", "refresh_token", "access_token", "password"):
        assert k not in text.lower()


def test_t10_fetch_reason_free_text_redacted():
    funds = {"AAA111": {"status": "failed", "reason": "timeout while contacting " + secrets.token_hex(4) + " host"}}
    out = _run(_rows(("A", "AAA111")), funds)
    assert _fund(out, "AAA111")["fetch_failure_reason"] == "unspecified_reason_redacted"


def test_t10_last_line_guard_rejects_leaky_dict():
    leaky = {"x": f"{secrets.token_hex(3)}@{secrets.token_hex(3)}.example"}
    with pytest.raises(ValueError):
        probe.render_json(leaky)


# ───────────────────────── 語意護欄 ─────────────────────────

def test_missing_is_never_zero_or_filled():
    out = _run(_rows(("A", "EMP001")), {"EMP001": _ok(fund_ccy="USD")})
    f = _fund(out, "EMP001")
    assert all(d["status"] == "missing" for d in f["dimensions"].values())
    assert out["dimensions"]["sharpe"]["missing"] == 1 and out["dimensions"]["sharpe"]["scored_n"] == 0
    assert f["coverage_disclosure"]["scored_n"] == 0
    assert "score" not in _text(out).replace("scored", "")  # 沒有任何分數欄位


def test_no_summary_verdict_wording_and_fixed_declarations():
    for origin in ("fixture", "user_supplied_code_list"):
        out = _run(_rows(("A", "AAA111")), {"AAA111": FULL_USD}, holdings_origin=origin)
        text = _text(out)
        assert not re.search(r"\b(PASS|SAFE|OK)\b", text)
        assert "正式准入" not in text and "grade" not in text.lower()
        assert out["admission"] == "NOT DEFINED"
        assert out["real_active_sheet_coverage"] == "NOT VERIFIED"
        assert out["source"]["holdings_origin"] == origin


def test_stale_conflict_not_evaluated_null_not_zero():
    out = _valid_out()
    assert out["not_evaluated_states"] == ["stale", "conflict"]
    for dim in probe.DIMENSIONS:
        assert out["dimensions"][dim]["stale"] is None and out["dimensions"][dim]["conflict"] is None
    for f in out["per_fund"]:
        for d in f["dimensions"].values():
            assert d["stale_status"] == "not_evaluated" and d["conflict_status"] == "not_evaluated"


def test_probe_does_not_change_compute_4d_health_results():
    from services.health.grade import compute_4d_health
    kw = dict(tr1y_pct=10.0, adr_pct=6.0, sharpe=1.2, sigma_pct=12.0, ma_dir=None,
              fund_ccy="USD", fx_cv_pct=3.0)
    before = json.dumps(compute_4d_health(**kw), sort_keys=True)
    _valid_out()
    after = json.dumps(compute_4d_health(**kw), sort_keys=True)
    assert before == after
    # 探針導出的 scored 與 production 直接呼叫一致(不自行重算)
    prod = compute_4d_health(**kw)
    out = _run(_rows(("A", "AAA111")), {"AAA111": _ok(**{k: v for k, v in kw.items() if k != "ma_dir"})})
    assert _fund(out, "AAA111")["coverage_disclosure"]["scored_n"] == prod["coverage"]["n_scored"]


def test_formula_version_and_fetched_at_evidence():
    out = _run(_rows(("A", "AAA111")), {"AAA111": FULL_USD}, main_sha="b227ae5c")
    assert out["fetched_at"] == FIXED.isoformat()
    fv = out["formula_version"]
    assert re.fullmatch(r"[0-9a-f]{40}", fv["health_module"]) and fv["main_sha"] == "b227ae5c"
    assert out["schema"] == "bl0545_probe_output_v1"


# ───────────────────────── 靜態檢查 / CLI ─────────────────────────

def test_source_has_no_streamlit_no_env_credentials_no_network_imports():
    src = SRC.read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported.isdisjoint({"streamlit", "os", "requests", "httpx", "urllib", "subprocess", "gspread",
                                "yfinance", "socket"}), imported
    assert "environ" not in src and "getenv" not in src


def test_no_production_module_imports_the_probe():
    pat = re.compile(r"bl0545_coverage_probe")
    hits = []
    for base in ("services", "repositories", "infra", "shared", "ui", "ui_v2", "ui_v3", "app.py"):
        p = REPO / base
        files = [p] if p.is_file() else list(p.rglob("*.py")) if p.exists() else []
        hits += [str(f) for f in files if pat.search(f.read_text(encoding="utf-8", errors="ignore"))]
    assert hits == []


def test_cli_fixture_end_to_end_and_codes_only(tmp_path, capsys):
    fx = {"schema": probe.FIXTURE_SCHEMA, "as_of": "2026-11-06",
          "holdings": [{"policy_id": "P1", "fund_code": "AAA111"}, {"policy_id": "P2", "fund_code": "aaa111"}],
          "funds": {"AAA111": FULL_USD}}
    fp, op = tmp_path / "fx.json", tmp_path / "out.json"
    fp.write_text(json.dumps(fx), encoding="utf-8")
    assert probe.main(["--fixture", str(fp), "--out", str(op), "--main-sha", "b227ae5c"]) == 0
    res = json.loads(op.read_text(encoding="utf-8"))
    assert res["valid"] is True and res["population"]["unique_funds"] == 1
    assert res["source"]["holdings_origin"] == "fixture" and res["as_of"] == "2026-11-06"
    cf = tmp_path / "codes.txt"
    cf.write_text("AAA111\nBBB222\n", encoding="utf-8")
    assert probe.main(["--codes-file", str(cf)]) == 0
    res2 = json.loads(capsys.readouterr().out)
    assert res2["population"]["not_attempted"] == 2 and res2["source"]["holdings_origin"] == "user_supplied_code_list"
    assert probe.main([]) == 2


def test_cli_rejects_wrong_fixture_schema(tmp_path):
    fp = tmp_path / "bad.json"
    fp.write_text(json.dumps({"schema": "other"}), encoding="utf-8")
    assert probe.main(["--fixture", str(fp)]) == 2
