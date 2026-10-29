"""MoneyDJ NAV 等價性 probe：比較引擎、解析、報告與安全邊界（不連網）。

HTML 夾具為 **synthetic**（照 `nav_metrics._parse_nav_html` 與 `declared_profile._parse_label_table` 預期的結構手寫：
`<table>` 內 `<tr><td>MM/DD</td><td>淨值</td></tr>`；基本資料表 `<td>基金名稱</td><td>…</td>`），不是 MoneyDJ 真實回應。
"""
from __future__ import annotations

import ast
import gzip
import importlib.util
import json
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("probe_moneydj_nav_equivalence", _ROOT / "scripts" / "probe_moneydj_nav_equivalence.py")
P = importlib.util.module_from_spec(_SPEC)
import sys
sys.path.insert(0, str(_ROOT / "scripts"))
_SPEC.loader.exec_module(P)


def _obs(inp="TLZF9", kind="prod_nav30", transport="direct", base="TLZF9", ccy="美元", points=(("2026-10-27", 10.1), ("2026-10-28", 10.2)), status="ok"):
    return {"input": inp, "base": base, "kind": kind, "transport": transport, "parse_status": status, "currency": ccy,
            "recent": [list(p) for p in points] if status == "ok" else [], "nav_date": points[-1][0] if status == "ok" else None,
            "parser": "v", "http_status": 200}


def _html(rows):
    return "<html><body><table>" + "".join(f"<tr><td>{d}</td><td>{v}</td></tr>" for d, v in rows) + "</table></body></html>"


def _basic(name="某基金", ccy="美元"):
    return f"<html><body><table><tr><td>基金名稱</td><td>{name}</td><td>計價幣別</td><td>{ccy}</td></tr></table></body></html>"


# ── 比較引擎 ──
def test_consistent():
    r = P.compare_observations(_obs(), _obs("TLZF9-AL001", "platform_wb"))
    assert r["status"] == "consistent" and r["compared_date"] == "2026-10-28" and r["scope"] == "cross_input"
    assert r["share_class"] == "unknown"


def test_date_differs_no_common_date_is_not_comparable():
    r = P.compare_observations(_obs(points=(("2026-10-20", 10.0),)), _obs("TLZF9-24A7", points=(("2026-10-28", 10.2),)))
    assert r["status"] == "not_comparable" and any(x.startswith("no_common_nav_date") for x in r["reasons"])
    assert r["nav_a"] is None and r["nav_b"] is None   # 缺值是 None，不是 0


def test_latest_dates_differ_but_common_date_equal_is_consistent_on_common_date():
    a = _obs(points=(("2026-10-27", 10.1),))
    b = _obs("TLZF9-AL001", points=(("2026-10-27", 10.1), ("2026-10-28", 10.2)))
    r = P.compare_observations(a, b)
    assert r["status"] == "consistent" and r["compared_date"] == "2026-10-27"


def test_currency_missing_or_differs_not_comparable():
    assert "currency_missing_not_explicit" in P.compare_observations(_obs(ccy=None), _obs("X", ccy="美元"))["reasons"]
    r = P.compare_observations(_obs(ccy="美元"), _obs("X", ccy="歐元"))
    assert r["status"] == "not_comparable" and any(x.startswith("currency_differs") for x in r["reasons"])


def test_parse_failure_not_comparable():
    r = P.compare_observations(_obs(status="no_nav_table", points=(("2026-10-28", 1.0),)), _obs("X"))
    assert r["status"] == "not_comparable" and r["reasons"][0].startswith("parse_failure")


def test_base_differs_not_comparable():
    r = P.compare_observations(_obs(), _obs("ACDD01", base="ACDD01"))
    assert r["status"] == "not_comparable" and any(x.startswith("base_differs") for x in r["reasons"])


def test_conflict_lists_candidate_causes_never_different_fund():
    a = _obs(points=(("2026-10-27", 10.1), ("2026-10-28", 10.2)))
    b = _obs("TLZF9-AL001", "platform_wb", points=(("2026-10-27", 10.1), ("2026-10-28", 10.3)))
    r = P.compare_observations(a, b)
    assert r["status"] == "conflict"
    causes = {c["cause"]: c for c in r["candidate_causes"]}
    assert set(causes) == {"as_of_differs", "publication_lag", "page_type", "currency", "share_class",
                           "platform_stale_cache", "parser_difference", "source_inconsistency"}
    assert causes["page_type"]["status"] == "supported" and causes["currency"]["status"] == "ruled_out"
    assert causes["share_class"]["status"] == "unverified"
    assert "UNVERIFIED" in r["conclusion"] and "different_fund" not in json.dumps(r)


def test_conflict_stale_platform_supported():
    a = _obs(points=(("2026-10-27", 10.1), ("2026-10-28", 10.2)))
    b = _obs("TLZF9-AL001", "platform_wb", points=(("2026-10-26", 9.9), ("2026-10-27", 10.0)))
    r = P.compare_observations(a, b)
    causes = {c["cause"]: c for c in r["candidate_causes"]}
    assert r["status"] == "conflict" and causes["platform_stale_cache"]["status"] == "supported"
    assert causes["as_of_differs"]["status"] == "supported" and causes["publication_lag"]["status"] == "supported"


# ── 群組裁定 ──
def _grp(obs, inputs=("TLZF9", "TLZF9-AL001")):
    comps = [P.compare_observations(x, y) for i, x in enumerate(obs) for y in obs[i + 1:]]
    return P.summarize_group(inputs, obs, comps), comps


def test_group_consistent_requires_all_inputs_covered():
    g, _ = _grp([_obs(), _obs("TLZF9-AL001", "platform_wb")])
    assert g["verdict"] == "consistent" and g["supports_suffix_does_not_change_nav"] is True


def test_group_partial_is_not_comparable():
    g, _ = _grp([_obs(), _obs("TLZF9-AL001", "platform_wb", status="no_nav_table")])
    assert g["verdict"] == "not_comparable" and g["uncovered_inputs"] == ["TLZF9", "TLZF9-AL001"]
    assert g["supports_suffix_does_not_change_nav"] is None


def test_group_conflict_and_blocked():
    g, _ = _grp([_obs(), _obs("TLZF9-AL001", points=(("2026-10-27", 10.1), ("2026-10-28", 99.0)))])
    assert g["verdict"] == "conflict" and g["supports_suffix_does_not_change_nav"] is False
    blocked = P.summarize_group(("TLZF9",), [{"input": "TLZF9", "http_status": 403}], [])
    assert blocked["verdict"] == "blocked"


# ── 解析（synthetic 夾具） ──
def test_build_observation_ok_and_failures():
    resp = lambda b, st=200: dict(status=st, content_type="text/html; charset=utf-8", latency_ms=1.0, bytes=len(b), body=b, error=None)
    o = P.build_observation(input_code="TLZF9", base="TLZF9", kind="prod_nav30", transport="direct", url="u",
                            resp=resp(_html([("10/27", "10.1"), ("10/28", "10.2")]).encode()), parser_version="v",
                            basic={"fund_name": "某基金", "currency": "美元"})
    assert o["parse_status"] == "ok" and o["nav"] == 10.2 and o["currency"] == "美元" and o["raw"]["sha256"]
    nt = P.build_observation(input_code="X", base="X", kind="prod_nav30", transport="direct", url="u",
                             resp=resp(b"<html><body>no table</body></html>"), parser_version="v")
    assert nt["parse_status"] == "no_nav_table" and nt["nav"] is None and nt["currency"] is None
    hf = P.build_observation(input_code="X", base="X", kind="prod_nav30", transport="direct", url="u",
                             resp=dict(status=403, body=b"x", error=None), parser_version="v")
    assert hf["parse_status"] == "http_failed"
    b = P.build_observation(input_code="X", base="X", kind="basic_info", transport="direct", url="u",
                            resp=resp(_basic().encode()), parser_version="v")
    assert b["fund_name"] == "某基金" and b["currency"] == "美元"
    b2 = P.build_observation(input_code="X", base="X", kind="basic_info", transport="direct", url="u",
                             resp=resp(_basic(ccy="").encode()), parser_version="v")
    assert b2["currency"] is None   # 頁面沒明示 → None，不猜


# ── 端到端（假 fetcher） ──
def _run(get, transports=None):
    return P.run_probe(get, sleep=lambda s: None, transports_enabled=transports or {"direct": True, "nas_proxy": False})


def _ok(url, t):
    body = _basic() if "/yp/" in url else _html([("10/27", "10.1"), ("10/28", "10.2")])
    return dict(status=200, content_type="text/html", latency_ms=1.0, bytes=len(body), body=body.encode(), error=None)


def test_end_to_end_consistent_and_resolver_evidence():
    r = _run(_ok)
    assert [i["original_input"] for i in r["inputs"]] == list(P.INPUTS)
    assert {i["original_input"]: i["base_fund_code"] for i in r["inputs"]}["TLZF9-24A7"] == "TLZF9"
    assert r["summary"]["TLZF9"]["verdict"] == "consistent" and r["summary"]["ACDD01"]["verdict"] == "not_comparable"
    assert "only prod pages compared" in r["summary"]["ACDD01"]["detail"]   # 帶後綴者無 platform 頁 → 不算覆蓋
    o = next(o for o in r["observations"] if o["input"] == "TLZF9-AL001" and o["kind"] == "platform_wb")
    assert o["currency_source"].startswith("basic_info_url:") and o["fund_name_source"].startswith("basic_info_url:")
    kinds = {o["kind"] for o in r["observations"] if o["input"] == "TLZF9-AL001"}
    assert {"prod_nav30", "platform_hist", "platform_wb", "basic_info"} <= kinds
    assert all(o["transport"] == "direct" for o in r["observations"]) and r["transports"]["nas_proxy"] == "proxy_not_configured"
    assert r["complete"] is True and r["parser_version"].startswith(P.SCRIPT_VERSION)


def test_end_to_end_network_blocked_stops_and_records_error():
    calls = []

    def blocked(url, t):
        calls.append(url)
        return dict(status=None, content_type=None, latency_ms=1.0, bytes=None, body=None, error="ProxyError: Tunnel connection failed: 403 Forbidden")
    r = _run(blocked)
    assert len(calls) == P.BLOCK_PROBE_N                      # 前 N 個失敗即停，不再發請求、不繞路
    assert r["network_blocked"]["direct"]["blocked"] is True and "403 Forbidden" in r["network_blocked"]["direct"]["errors"][0]
    assert all(v["verdict"] == "blocked" for v in r["summary"].values())
    assert all(o["nav"] is None for o in r["observations"])   # 缺值 None，不是 0


def test_end_to_end_conflict_when_one_input_differs():
    def get(url, t):
        if "/yp/" in url:
            return _ok(url, t)
        v = "10.9" if "a=TLZF9-24A7" in url or "A=TLZF9-24A7" in url else "10.2"
        body = _html([("10/27", "10.1"), ("10/28", v)])
        return dict(status=200, content_type="text/html", latency_ms=1.0, bytes=len(body), body=body.encode(), error=None)
    r = _run(get)
    assert r["summary"]["TLZF9"]["verdict"] == "conflict"
    assert any(c["status"] == "conflict" and c["candidate_causes"] for c in r["comparisons"])


def test_spacing_enforced_between_requests():
    slept = []
    P.run_probe(_ok, sleep=slept.append, inputs=("TLZF9",), transports_enabled={"direct": True, "nas_proxy": False})
    assert slept and all(s > 0 for s in slept) and max(slept) <= P.SPACING_SEC


# ── 安全邊界 ──
def test_mask_and_report_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("PROXY_URL", "http://user:S3cretPass@10.9.8.7:3128")
    sec = P.secret_literals()
    def leak(url, t):
        return dict(status=None, content_type=None, latency_ms=1.0, bytes=None, body=None,
                    error=P.mask_text("ProxyError via http://user:S3cretPass@10.9.8.7:3128", sec))
    r = _run(leak)
    out = tmp_path / "r.json.gz"
    P.write_report(r, out)
    text = gzip.decompress(out.read_bytes()).decode()
    assert "S3cretPass" not in text and "10.9.8.7" not in text and "PROXY_URL" not in text.replace("PROXY_URL 環境變數", "")
    assert json.loads(text)["script_version"] == P.SCRIPT_VERSION


def test_import_guard_no_writer_modules():
    tree = ast.parse((_ROOT / "scripts" / "probe_moneydj_nav_equivalence.py").read_text(encoding="utf-8"))
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module)
    banned = ("gspread", "nav_history", "policy", "snapshot", "pool_repository", "portfolio_perf", "cache_store",
              "oauth", "settings_store", "weights_store")
    assert not [m for m in mods if any(b in m for b in banned)], mods
    text = (_ROOT / "scripts" / "probe_moneydj_nav_equivalence.py").read_text(encoding="utf-8")
    assert "requests.post" not in text and ".post(" not in text and ".put(" not in text and ".delete(" not in text


# ── 審查回修：覆蓋判定、共同日、旗標 ──
def test_dashed_input_needs_platform_page_to_count_as_covered():
    g, _ = _grp([_obs(), _obs("TLZF9-AL001", "prod_nav30")])
    assert g["verdict"] == "not_comparable" and "only prod pages compared" in g["detail"]
    assert "prod_nav30~prod_nav30" in g["detail"]
    g2, _ = _grp([_obs(), _obs("TLZF9-AL001", "platform_wb")])
    assert g2["verdict"] == "consistent" and "prod_nav30~platform_wb" in g2["detail"]


def test_three_input_group_partial_not_comparable():
    ins = ("TLZF9", "TLZF9-AL001", "TLZF9-24A7")
    g, _ = _grp([_obs(), _obs("TLZF9-AL001", "platform_wb"), _obs("TLZF9-24A7", "platform_wb", status="no_nav_table")], ins)
    assert g["verdict"] == "not_comparable" and g["uncovered_inputs"] == ["TLZF9-24A7"]   # 退回 `if cons` 會變 consistent
    g2, _ = _grp([_obs(), _obs("TLZF9-AL001", "platform_wb"), _obs("TLZF9-24A7", "platform_wb")], ins)
    assert g2["verdict"] == "consistent"


def test_common_date_pick_is_latest_common():
    a = _obs(points=(("2026-10-26", 9.0), ("2026-10-27", 10.1), ("2026-10-28", 10.2)))
    b = _obs("X", "platform_wb", points=(("2026-10-26", 9.5), ("2026-10-27", 10.1)))
    r = P.compare_observations(a, b)
    assert r["compared_date"] == "2026-10-27" and r["status"] == "consistent"   # 取最舊共同日(10-26)會變 conflict


def test_fund_name_mismatch_flag_and_same_input_conflicts_surface():
    a, b = _obs(), _obs("TLZF9-AL001", "platform_wb")
    a["fund_name"], b["fund_name"] = "甲基金", "乙基金"
    g, comps = _grp([a, b])
    assert comps[0]["fund_name_mismatch"] is True and g["fund_name_mismatch_pairs"] and g["verdict"] == "consistent"
    c = _obs("TLZF9", "prod_nav30", "nas_proxy", points=(("2026-10-27", 10.1), ("2026-10-28", 99.0)))
    g2, _ = _grp([_obs(), c, _obs("TLZF9-AL001", "platform_wb")])
    assert g2["same_input_conflicts"] and "same_input_conflicts" in g2["detail"]


def test_non200_keeps_masked_snippet():
    o = P.build_observation(input_code="X", base="X", kind="prod_nav30", transport="direct", url="u",
                            resp=dict(status=403, content_type="text/html", body="<html>Forbidden 拒絕</html>".encode(), error=None),
                            parser_version="v")
    assert o["parse_status"] == "http_failed" and "Forbidden" in o["error_snippet"]
