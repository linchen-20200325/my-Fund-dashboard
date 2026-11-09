"""`scripts/probe_yahoo_indices_sp.py` 與 `.github/workflows/yahoo_indices_sp_probe.yml` 的離線守衛。

全部僅用 mock opener／sleep，無網路。守的是：實發請求恰好四個且有程式層硬上限、
任何失敗立即停止且不重試、遮罩有效、輸出路徑已存在即拒絕、workflow 權限與觸發最小。

## 守不到什麼

* 不驗 GitHub Actions 能否直連 Yahoo、Yahoo 實際回應形狀、dispatch API 是否回 403。
* workflow 檢查是對 repo 內這一份檔的靜態檢查；按鈕分支上被改過的 yml 本檔看不到。
"""
from __future__ import annotations

import ast
import base64
import calendar
import datetime as dt
import gzip
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "scripts" / "probe_yahoo_indices_sp.py"
_WF = _ROOT / ".github" / "workflows" / "yahoo_indices_sp_probe.yml"


def _load():
    spec = importlib.util.spec_from_file_location("probe_yahoo_indices_sp", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["probe_yahoo_indices_sp"] = mod
    spec.loader.exec_module(mod)
    return mod


P = _load()


def _chart_body(ts, close, tz="America/New_York", gmt=-18000, extra_meta=None) -> bytes:
    meta = {
        "exchangeTimezoneName": tz,
        "gmtoffset": gmt,
        "timezone": "EST",
        "instrumentType": "INDEX",
        "regularMarketTime": ts[-1] if ts else 0,
        "dataGranularity": "1d",
        "validRanges": ["1d", "5d", "1mo", "2y"],
        "symbol": "X",
    }
    meta.update(extra_meta or {})
    obj = {"chart": {"result": [{"meta": meta, "timestamp": ts,
                                 "indicators": {"quote": [{"close": close}]}}], "error": None}}
    return json.dumps(obj).encode()


def _ts(y, m, d, h=0, mi=0):
    return calendar.timegm((y, m, d, h, mi, 0))


GOOD_TS = [_ts(2026, 6, 2, 13, 30), _ts(2026, 6, 3, 13, 30), _ts(2026, 6, 4, 13, 30)]
GOOD_BODY = _chart_body(GOOD_TS, [100.0, None, 102.5])


class FakeOpener:
    """依序回應；plan 的每項為 (status, headers, body) 或 Exception。"""

    def __init__(self, plan):
        self.plan = list(plan)
        self.calls = []

    def __call__(self, url, headers, timeout):
        self.calls.append((url, dict(headers), timeout))
        item = self.plan[len(self.calls) - 1]
        if isinstance(item, Exception):
            raise item
        return item


def _ok(body=GOOD_BODY):
    return (200, {"content-type": "application/json", "set-cookie": "A=secret", "date": "x"}, body)


class Sleeps(list):
    def __call__(self, s):
        self.append(s)


_ENV = {"GITHUB_SHA": "trig123", "PROBE_EXECUTED_SHA": "exec456", "GITHUB_RUN_ID": "99",
        "GITHUB_RUN_ATTEMPT": "1", "GITHUB_WORKFLOW": "wf"}


def _run(plan):
    op, sl = FakeOpener(plan), Sleeps()
    rep = P.run_probe(opener=op, sleep=sl, env=dict(_ENV))
    return rep, op, sl


# (1) 全成功 -----------------------------------------------------------------
def test_all_success_exactly_four_calls_and_sleeps():
    rep, op, sl = _run([_ok()] * 4)
    assert len(op.calls) == 4
    assert rep["http_requests_attempted"] == 4
    assert sl == [5.0, 5.0, 5.0] and all(s >= 5 for s in sl)
    assert rep["stop_reason"] == "completed_all_authorized_requests"
    assert rep["failed_request_index"] is None and rep["skipped_not_attempted"] == []
    for key in ("trigger_sha", "executed_sha", "run_id", "run_attempt", "workflow",
                "authorization_ref", "data_source", "interpretation_limits", "hard_limit"):
        assert rep[key] not in (None, "")
    assert rep["authorization_ref"] == "DEC-2026-11-09-08"
    assert "非 TWSE／CBOE 官方" in rep["data_source"]
    for r in rep["requests"]:
        assert r["raw_sha256"] == hashlib.sha256(GOOD_BODY).hexdigest()
        assert gzip.decompress(base64.b64decode(r["raw_gzip_b64"])) == GOOD_BODY
        assert r["http_status"] == 200 and r["body_bytes"] == len(GOOD_BODY)
        assert "set-cookie" not in r["response_headers"]
        assert r["parsed"]["close_null_indexes"] == [1]
        assert r["raw_consistency"]["consistent"] is True
        assert r["url"].startswith("https://query1.finance.yahoo.com/v8/finance/chart/%5E")
    urls = [c[0] for c in op.calls]
    assert "%5EGSPC?interval=1d&range=2y" in urls[0]
    assert "%5EVIX?interval=1d&range=2y" in urls[1]
    assert "%5ETWII?interval=1d&range=2y" in urls[2]
    assert "%5EVIX?period1=" in urls[3] and "range=" not in urls[3]
    assert [r["http_requests_attempted_after_this"] for r in rep["requests"]] == [1, 2, 3, 4]


# (2) 第 N 次失敗 ---------------------------------------------------------------
_FAILS = {
    "429": (429, {"date": "d"}, b"Too Many Requests"),
    "500": (500, {}, b"boom"),
    "exc": OSError("connection reset"),
    "empty": (200, {}, b""),
    "nonjson": (200, {}, b"<html>not json</html>"),
    "3xx": (302, {"location": "https://elsewhere/"}, b""),
    "schema": (200, {}, b'{"chart": {"result": null}}'),
    "nonmono": (200, {}, _chart_body([10, 5], [1.0, 2.0])),
    "lenmismatch": (200, {}, _chart_body([10, 20], [1.0])),
}


@pytest.mark.parametrize("n", [1, 2, 3, 4])
@pytest.mark.parametrize("kind", list(_FAILS))
def test_failure_stops_and_never_retries(n, kind):
    plan = [_ok()] * (n - 1) + [_FAILS[kind]]
    rep, op, sl = _run(plan)
    assert len(op.calls) == n, "失敗後不得再發任何請求（含重試）"
    assert rep["http_requests_attempted"] == n
    assert rep["failed_request_index"] == n
    assert rep["stop_reason"] and rep["stop_reason"] != "completed_all_authorized_requests"
    assert [s["request_index"] for s in rep["skipped_not_attempted"]] == list(range(n + 1, 5))
    assert all(s["status"] == "skipped_not_attempted" for s in rep["skipped_not_attempted"])
    assert len(rep["requests"]) == n and rep["requests"][-1]["ok"] is False
    assert len(sl) == n - 1


def test_stop_reason_kinds_and_cooldown():
    rep, _, _ = _run([_FAILS["429"]])
    assert rep["stop_reason"].startswith("http_status") and "cooldown_notice" in rep
    assert "30 分鐘" in rep["cooldown_notice"] and "重新" in rep["cooldown_notice"]
    assert _run([_FAILS["3xx"]])[0]["stop_reason"].startswith("redirect_not_followed")
    assert _run([_FAILS["exc"]])[0]["stop_reason"].startswith("exception")
    assert _run([_FAILS["empty"]])[0]["stop_reason"].startswith("empty_body")
    assert _run([_FAILS["nonjson"]])[0]["stop_reason"].startswith("json_parse")
    assert _run([_FAILS["schema"]])[0]["stop_reason"].startswith("schema")
    assert "cooldown_notice" not in _run([_FAILS["500"]])[0]


# (3) 硬上限 ---------------------------------------------------------------------
def test_hard_cap_refuses_fifth_request():
    b = P.RequestBudget()
    for _ in range(4):
        b.before_send()
    with pytest.raises(P.HardCapExceeded):
        b.before_send()
    assert b.http_requests_attempted == 4


def test_hard_cap_cannot_be_raised_and_send_one_refuses_fifth():
    assert P.RequestBudget(limit=99).limit == 4
    b = P.RequestBudget()
    op = FakeOpener([_ok()] * 5)
    for req in P.AUTHORIZED_REQUESTS:
        P._send_one(req, b, op, lambda: dt.datetime.now(dt.timezone.utc), {})
    with pytest.raises(P.HardCapExceeded):
        P._send_one(P.AUTHORIZED_REQUESTS[0], b, op, lambda: dt.datetime.now(dt.timezone.utc), {})
    assert len(op.calls) == 4 and b.http_requests_attempted == 4


def test_script_has_no_cli_way_to_widen_requests():
    src = _SCRIPT.read_text(encoding="utf-8")
    flags = set(re.findall(r'add_argument\(\s*"(--[a-z\-]+)"', src))
    assert flags == {"--out", "--dry-run"}
    assert len(P.AUTHORIZED_REQUESTS) == 4
    assert [r["symbol"] for r in P.AUTHORIZED_REQUESTS] == ["^GSPC", "^VIX", "^TWII", "^VIX"]


# (4) 不用 infra.proxy／重試 ---------------------------------------------------------
def test_script_does_not_use_infra_proxy_or_retries():
    src = _SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    for banned in ("infra", "requests", "repositories", "services", "shared", "streamlit", "pandas"):
        assert banned not in imported
    code_names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | \
                 {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert "fetch_url" not in code_names and "fetch_url_with_retry" not in code_names
    assert "PROXY_URL" not in {n.value for n in ast.walk(tree)
                               if isinstance(n, ast.Constant) and isinstance(n.value, str)
                               and n.value == "PROXY_URL"}
    assert "ProxyHandler({})" in src  # 不讀環境代理


def test_default_opener_does_not_follow_redirect(monkeypatch):
    seen = {}

    class _H:
        def __init__(self, *a, **k):
            seen["redirect_handler"] = a

    # 直接驗 _NoRedirect 行為：redirect_request 回 None → urllib 會拋 HTTPError 而非再發一次請求
    h = P._NoRedirect()
    assert h.redirect_request(None, None, 302, "Found", {}, "https://x/") is None


# (5) 遮罩 ------------------------------------------------------------------------
def test_mask_patterns():
    s = ("Authorization: Bearer abc.def-123 token=SECRETVAL api_key=K1 PROXY_URL=http://u:p@h:8080 "
         "Set-Cookie: A=1; B=2 https://user:pw@host/x")
    m = P.mask(s, env={})
    for leak in ("abc.def-123", "SECRETVAL", "K1", "u:p@", "A=1", "user:pw"):
        assert leak not in m
    assert "***" in m


def test_mask_env_values_and_report_has_no_leak(tmp_path):
    env = {"PROXY_URL": "http://nas.example:3128", "MY_TOKEN": "tok_abcdef123"}
    assert "tok_abcdef123" not in P.mask("err tok_abcdef123 x", env)
    rep, _, _ = _run([OSError("failed via http://nas.example:3128 Bearer zzz999")])
    out = tmp_path / "r.json"
    P.write_report(rep, out)
    text = out.read_text(encoding="utf-8")
    assert "zzz999" not in text


def test_error_text_is_masked_in_report():
    rep, _, _ = _run([OSError("boom Bearer topsecret123 token=abc")])
    err = rep["requests"][0]["error"]
    assert "topsecret123" not in err and "token=abc" not in err


# (6) 輸出路徑已存在 ------------------------------------------------------------------
def test_existing_output_refuses_with_zero_requests(tmp_path, monkeypatch, capsys):
    out = tmp_path / "exists.json"
    out.write_text("{}\n", encoding="utf-8")
    called = []
    monkeypatch.setattr(P, "run_probe", lambda *a, **k: called.append(1))
    assert P.main(["--out", str(out)]) == 2
    assert called == []
    assert out.read_text(encoding="utf-8") == "{}\n"
    with pytest.raises(FileExistsError):
        P.write_report({"a": 1}, out)


def test_main_writes_report_and_exit_codes(tmp_path, monkeypatch):
    rep, _, _ = _run([_ok()] * 4)
    rep2, _, _ = _run([_FAILS["500"]])
    monkeypatch.setattr(P, "run_probe", lambda *a, **k: rep)
    out = tmp_path / "sub" / "r.json"
    assert P.main(["--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["http_requests_attempted"] == 4
    assert out.read_text(encoding="utf-8").endswith("}\n")
    monkeypatch.setattr(P, "run_probe", lambda *a, **k: rep2)
    assert P.main(["--out", str(tmp_path / "r2.json")]) == 1


def test_dry_run_sends_nothing(monkeypatch, capsys):
    monkeypatch.setattr(P, "default_opener", lambda *a, **k: pytest.fail("dry-run 不得發請求"))
    assert P.main(["--dry-run"]) == 0
    assert len(capsys.readouterr().out.strip().splitlines()) == 4


# (7) workflow 靜態檢查 ----------------------------------------------------------------
def _wf():
    try:
        import yaml
    except ImportError:  # 安全守衛：缺 pyyaml 一律紅燈、不 skip
        pytest.fail("缺 pyyaml：安全守衛不得 skip")
    return yaml.safe_load(_WF.read_text(encoding="utf-8"))


def test_workflow_static():
    wf = _wf()
    raw = _WF.read_text(encoding="utf-8")
    on = wf.get("on", wf.get(True))
    assert set(on) == {"push", "workflow_dispatch"}
    assert on["push"]["branches"] == ["probe/yahoo-indices-sp-trigger"]
    assert not on["workflow_dispatch"]  # 無 inputs
    assert "schedule" not in on and "pull_request" not in on
    assert wf["permissions"] == {"contents": "write"}
    assert wf["concurrency"]["group"] == "yahoo-indices-sp-probe"
    assert wf["concurrency"]["cancel-in-progress"] is False
    job = wf["jobs"]["probe"]
    assert job["timeout-minutes"] == 10
    steps = job["steps"]
    checkouts = [s for s in steps if str(s.get("uses", "")).startswith("actions/checkout")]
    assert len(checkouts) == 1
    assert checkouts[0]["with"]["ref"] == "main"
    assert checkouts[0]["with"]["persist-credentials"] is False
    code = "\n".join(ln for ln in raw.splitlines() if not ln.lstrip().startswith("#"))
    assert "PROXY_URL" not in code and "secrets.PROXY" not in code
    assert "pip install" not in code
    assert "--force" not in code and "push -f" not in code and "--force-with-lease" not in code
    assert "github.sha" not in code and "github.ref" not in code
    pushes = [ln.strip() for ln in code.splitlines() if re.search(r"\bpush origin\b", ln)]
    assert pushes == ['agit push origin "HEAD:refs/heads/$RESULT_BRANCH"']
    assert job["env"]["RESULT_BRANCH"] == "probe/yahoo-indices-sp-results"
    assert "probe/fx-obs-date" not in code
    assert "main" not in " ".join(pushes)
    names = [s.get("id") for s in steps]
    assert "guard" in names
    probe_idx = next(i for i, s in enumerate(steps) if "probe_yahoo_indices_sp.py" in s.get("run", ""))
    assert names.index("guard") < probe_idx
    commit = steps[-1]
    assert "always()" in commit["if"] and "steps.guard.outcome" in commit["if"]
    assert wf["name"].count("探測") >= 1 and "只讀" in wf["name"]


def test_workflow_names_not_shared_with_fx_probe():
    fx = (_ROOT / ".github" / "workflows" / "fx_obs_date_probe.yml").read_text(encoding="utf-8")
    assert "yahoo-indices-sp" not in fx
    assert "yahoo-indices-sp" in _WF.read_text(encoding="utf-8")


# (8) 時間戳換算 --------------------------------------------------------------------------
def test_exchange_local_dates_per_index():
    # 美東：2026-06-02 13:30Z = 09:30 EDT 同日；2026-06-03T00:00Z 的 UTC 日期是 06-03，美東本地是 06-02
    b = _chart_body([_ts(2026, 6, 3, 0, 0), _ts(2026, 6, 3, 13, 30)], [1.0, 2.0], "America/New_York")
    p = P.parse_chart(json.loads(b))
    assert (p["bars"][0]["utc_date"], p["bars"][0]["exchange_local_date"],
            p["bars"][0]["exchange_local_weekday"]) == ("2026-06-03", "2026-06-02", "Tue")
    assert p["bars"][1]["exchange_local_date"] == "2026-06-03" and p["bars"][1]["exchange_local_weekday"] == "Wed"
    # 台北：2026-06-02 16:00Z = 06-03 00:00 +08
    b = _chart_body([_ts(2026, 6, 2, 16, 0), _ts(2026, 6, 3, 1, 0)], [1.0, 2.0], "Asia/Taipei", 28800)
    p = P.parse_chart(json.loads(b))
    assert p["bars"][0]["utc_date"] == "2026-06-02" and p["bars"][0]["exchange_local_date"] == "2026-06-03"
    assert p["bars"][1]["exchange_local_date"] == "2026-06-03"
    # 芝加哥（夏令 -5）：2026-06-03T03:00Z = 06-02 22:00 CDT；週二
    b = _chart_body([_ts(2026, 6, 3, 3, 0)], [1.0], "America/Chicago", -18000)
    p = P.parse_chart(json.loads(b))
    assert (p["bars"][0]["exchange_local_date"], p["bars"][0]["exchange_local_weekday"]) == ("2026-06-02", "Tue")
    assert p["meta"]["exchangeTimezoneName"] == "America/Chicago" and p["meta"]["gmtoffset"] == -18000
    assert p["bars"][0]["utc_iso"] == "2026-06-03T03:00:00.000Z"


def test_missing_timezone_is_recorded_not_guessed():
    b = _chart_body([_ts(2026, 6, 3, 3, 0)], [1.0], tz=None)
    p = P.parse_chart(json.loads(b))
    assert p["bars"][0]["exchange_local_date"] is None


# (9) period1/period2 窗 --------------------------------------------------------------------
def test_period_window_contains_target_date():
    t = _ts(2026, 6, 3, 0, 0)
    assert P.PERIOD1_EPOCH < t < P.PERIOD2_EPOCH
    assert P.PERIOD1_EPOCH == _ts(2026, 5, 29) and P.PERIOD2_EPOCH == _ts(2026, 6, 9)
    url = P.build_url(P.AUTHORIZED_REQUESTS[3])
    assert f"period1={P.PERIOD1_EPOCH}" in url and f"period2={P.PERIOD2_EPOCH}" in url and "interval=1d" in url
    rep, _, _ = _run([_ok(_chart_body([t - 86400 * 0, t + 3600], [1.0, 2.0]))] * 4)
    chk = rep["requests"][3]["window_target_check"]
    assert chk["target_date"] == "2026-06-03" and chk["bars_with_utc_date"] == [0, 1]
    assert "window_target_check" not in rep["requests"][0]
