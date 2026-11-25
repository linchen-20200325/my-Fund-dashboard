"""scripts/tdcc_11641_min_fetch.py 離線測試（B-TDCC-REAL-NAV-S1）。

全檔 autouse 封鎖 socket：任何真連線嘗試即失敗。transport 一律為假。
負控／變異：test_mutation_* 以改寫來源字串的方式拿掉單一守衛，驗證對應測試會轉紅。
"""

from __future__ import annotations

import ast
import datetime as dt
import json
import socket
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))
SRC = _ROOT / "scripts" / "tdcc_11641_min_fetch.py"

import tdcc_11641_min_fetch as m  # noqa: E402

TODAY = dt.date(2026, 11, 24)
GOOD_ISIN = "US0378331005"  # 公開範例 ISIN（Luhn 有效），非持倉、非任何使用者資料


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("network attempt in offline test")

    monkeypatch.setattr(socket.socket, "connect", _boom)
    monkeypatch.setattr(socket, "create_connection", _boom)
    monkeypatch.setattr(socket, "getaddrinfo", _boom)


def _oas(path="/v1/opendata/X-1", refs=("https://data.gov.tw/dataset/11641",), servers=None, method="get"):
    op = {"summary": "境外基金淨值", "description": " ".join(refs)}
    return {"servers": servers if servers is not None else [{"url": "https://openapi.tdcc.com.tw"}],
            "paths": {path: {method: op}}}


def _rows(**over):
    r = {m.KEY_ISIN: GOOD_ISIN, m.KEY_NAV: "12.3456", m.KEY_DATE: "20261123", m.KEY_CCY: "USD",
         m.KEY_NAME: "測試基金 A 類"}
    r.update(over)
    return [r]


class FakeTransport:
    def __init__(self, oas, rows, *, status0=200, status1=200, ctype="application/json", enc="identity"):
        self.calls: list[str] = []
        self._oas, self._rows = oas, rows
        self._s0, self._s1, self._ct, self._enc = status0, status1, ctype, enc

    def __call__(self, url, max_bytes):
        self.calls.append(url)
        first = len(self.calls) == 1
        payload = self._oas if first else self._rows
        body = payload if isinstance(payload, (bytes, bytearray)) else json.dumps(payload, ensure_ascii=False).encode()
        return m.Response(self._s0 if first else self._s1, self._ct, bytes(body), self._enc)


ALLOWED = m.Rights("ALLOWED", "UNKNOWN", "UNKNOWN", basis_ref="TEST-BASIS", synthetic=True)


def _run(tp, rights=ALLOWED, **kw):
    kw.setdefault("test_mode", True)
    return m.run(GOOD_ISIN, user_confirmed_non_holding=True, transport=tp, rights=rights, today=TODAY,
                 now=lambda: dt.datetime(2026, 11, 24, 3, 0, tzinfo=dt.timezone.utc), **kw)


# ─────────────── 正控 ───────────────
def test_happy_path_releases_value_with_exactly_two_requests():
    tp = FakeTransport(_oas(), _rows())
    res = _run(tp)
    assert res.stop_reason is None and res.value_released
    assert len(tp.calls) == 2 and res.requests_used == 2
    assert tp.calls[0] == m.R0_URL and tp.calls[1] == "https://openapi.tdcc.com.tw/v1/opendata/X-1"
    d = res.local_display
    assert (d["nav"], d["currency"], d["nav_date"]) == ("12.3456", "USD", "2026-11-23")
    assert d["fetched_at_utc"] == "2026-11-24T03:00Z"
    assert "遵循該條款方可利用" in d["attribution"]["license_statement"]
    assert d["attribution"]["metadata_updated_on"].startswith("未載明")
    assert res.aggregate()["formulas_called"] == 0


def test_aggregate_has_no_isin_nav_name_or_url():
    res = _run(FakeTransport(_oas(), _rows()))
    blob = json.dumps(res.aggregate(), ensure_ascii=False)
    for secret in (GOOD_ISIN, "12.3456", "測試基金", "openapi.tdcc", "http"):
        assert secret not in blob


# ─────────────── 輸入／確認 ───────────────
def test_requires_user_confirmation_zero_requests():
    tp = FakeTransport(_oas(), _rows())
    res = m.run(GOOD_ISIN, user_confirmed_non_holding=False, transport=tp, today=TODAY)
    assert res.stop_reason == "user_confirmation_missing" and tp.calls == []


@pytest.mark.parametrize("bad", ["", "US0378331006", "us037833100", "123456789012", "US03783310O5X"])
def test_invalid_isin_zero_requests(bad):
    tp = FakeTransport(_oas(), _rows())
    res = m.run(bad, user_confirmed_non_holding=True, transport=tp, today=TODAY)
    assert res.stop_reason == "isin_invalid" and tp.calls == []


# ─────────────── MF-S1-1：唯一官方對應 ───────────────
@pytest.mark.parametrize("oas,reason", [
    (_oas(refs=()), "binding_none"),  # 同名摘要、無引用
    (_oas(refs=("https://data.gov.tw/dataset/11639",)), "binding_none"),
    (_oas(refs=("https://data.gov.tw/dataset/11639", "https://data.gov.tw/dataset/11641")), "binding_none"),
    (_oas(method="post"), "binding_none"),
    ({"servers": [{"url": "https://openapi.tdcc.com.tw"}], "paths": {
        "/a": {"get": {"description": "https://data.gov.tw/dataset/11641"}},
        "/b": {"get": {"description": "https://data.gov.tw/dataset/11641"}}}}, "binding_ambiguous"),
    ([], "oas_shape"),
])
def test_binding_failures_mean_zero_r1(oas, reason):
    tp = FakeTransport(oas, _rows())
    res = _run(tp)
    assert res.stop_reason == reason and len(tp.calls) == 1 and res.requests_used == 1


def test_old_code_location_without_reference_is_not_evidence():
    tp = FakeTransport(_oas(path="/v1/opendata/3-4", refs=()), _rows())
    assert _run(tp).stop_reason == "binding_none" and len(tp.calls) == 1


# ─────────────── MF-S1-1：URL 精確核證 ───────────────
@pytest.mark.parametrize("servers,path,reason", [
    ([{"url": "https://openapi.tdcc.com.tw.evil.com"}], "/v1/a", "host_mismatch"),
    ([{"url": "https://openapi.tdcc.com.tw@evil.com"}], "/v1/a", "origin_has_userinfo_port_query"),
    ([{"url": "http://openapi.tdcc.com.tw"}], "/v1/a", "scheme_not_https"),
    ([{"url": "https://openapi.tdcc.com.tw:8443"}], "/v1/a", "origin_has_userinfo_port_query"),
    ([{"url": "https://openapi.tdcc.com.tw"}, {"url": "https://openapi.tdcc.com.tw/"}], "/v1/a", "server_not_unique"),
    ([{"url": "https://openapi.tdcc.com.tw"}], "/v1/./opendata/3-4", "dot_segment"),  # Work 反例
    ([{"url": "https://openapi.tdcc.com.tw"}], "/v1/opendata/.", "dot_segment"),
    ([{"url": "https://openapi.tdcc.com.tw"}], "/v1/opendata/..", "path_illegal_chars"),
    ([{"url": "https://openapi.tdcc.com.tw/v1/."}], "/opendata/a", "dot_segment_base"),
    ([{"url": "https://openapi.tdcc.com.tw"}], "/v1/open.data/a..b", "path_illegal_chars"),
    ([{"url": "https://openapi.tdcc.com.tw"}], "/v1//a", "path_illegal_chars"),
    ([{"url": "https://openapi.tdcc.com.tw"}], "/v1%2Fa", "path_illegal_chars"),
    ([{"url": "https://openapi.tdcc.com.tw"}], "/v1/{id}", "path_template_or_relative"),
    ([{"url": "https://openapi.tdcc.com.tw"}], "https://evil.com/x", "path_template_or_relative"),
    ([{"url": "https://openapi.tdcc.com.tw"}], "/v1/a?x=1", "path_illegal_chars"),
    ([{"url": "https://openapi.tdcc.com.tw"}], "/v1/а", "path_not_ascii_or_long"),
])
def test_url_negative_controls_zero_r1(servers, path, reason):
    tp = FakeTransport(_oas(path=path, servers=servers), _rows())
    res = _run(tp)
    assert res.stop_reason == reason and len(tp.calls) == 1


def test_url_positive_controls():
    assert m.assemble_url([{"url": "https://openapi.tdcc.com.tw/v1"}], "/opendata/A") == \
        "https://openapi.tdcc.com.tw/v1/opendata/A"
    assert m.assemble_url([{"url": "https://openapi.tdcc.com.tw"}], "/v1/open.data/a.b").endswith("/a.b")


def test_prepared_url_mismatch_blocks_even_if_other_rules_pass():
    with pytest.raises(m.FetchStop) as e:
        m.assemble_url([{"url": "https://openapi.tdcc.com.tw"}], "/v1/a", prepare=lambda u: u + "x")
    assert e.value.reason == "prepared_url_mismatch"


# ─────────────── 傳輸／容量規則 ───────────────
@pytest.mark.parametrize("kw,reason", [
    ({"status0": 302}, "redirect_refused"),
    ({"status0": 500}, "http_status_500"),
    ({"enc": "gzip"}, "content_encoding_refused"),
    ({"ctype": "text/html"}, "content_type_not_json"),
])
def test_r0_transport_rules(kw, reason):
    tp = FakeTransport(_oas(), _rows(), **kw)
    res = _run(tp)
    assert res.stop_reason == reason and len(tp.calls) == 1 and res.r0_status == "failed"


def test_r1_redirect_no_followup_request():
    tp = FakeTransport(_oas(), _rows(), status1=301)
    res = _run(tp)
    assert res.stop_reason == "redirect_refused" and len(tp.calls) == 2  # 0 重試、0 轉址、0 額外 GET


def test_r0_and_r1_oversize_and_row_cap():
    big = b"[" + b"1," * (m.R0_MAX_BYTES // 2) + b"1]"
    res = _run(FakeTransport(big, _rows()))
    assert res.stop_reason == "oversize"
    rows = [{m.KEY_ISIN: "X"}] * (m.R1_MAX_ROWS + 1)
    res = _run(FakeTransport(_oas(), rows))
    assert res.stop_reason == "too_many_rows"


def test_r0_not_json_and_r1_not_list_and_schema_mismatch():
    assert _run(FakeTransport(b"<html>", _rows())).stop_reason == "r0_not_json"
    assert _run(FakeTransport(_oas(), {"a": 1})).stop_reason == "r1_not_list"
    assert _run(FakeTransport(_oas(), [{"x": 1}])).stop_reason == "schema_mismatch"


# ─────────────── 級別／缺值／零 fallback／權利 ───────────────
def test_zero_fallback_by_name_or_code():
    rows = _rows(**{m.KEY_ISIN: "US0000000002"})
    rows[0]["基金代碼"] = GOOD_ISIN  # 欄位雖含該字串，也不得以其他欄位補比
    res = _run(FakeTransport(_oas(), rows))
    assert res.stop_reason == "isin_not_found" and not res.value_released and res.withheld_reason


@pytest.mark.parametrize("over,reason", [
    ({m.KEY_NAV: ""}, "nav_unreadable"), ({m.KEY_NAV: "0"}, "nav_not_positive"),
    ({m.KEY_NAV: "-1"}, "nav_not_positive"), ({m.KEY_NAV: "NaN"}, "nav_not_positive"),
    ({m.KEY_DATE: "112年1月1日"}, "nav_date_unreadable"), ({m.KEY_DATE: "20271231"}, "nav_date_in_future"),
    ({m.KEY_CCY: "美元"}, "ccy_unrecognized"), ({m.KEY_NAME: "  "}, "class_unverified"),
])
def test_missing_is_withheld_never_zero(over, reason):
    res = _run(FakeTransport(_oas(), _rows(**over)))
    assert res.stop_reason == reason and res.local_display is None and not res.value_released


def test_same_day_conflict_and_class_conflict_withhold():
    a = _rows()[0]
    b = dict(a, **{m.KEY_NAV: "99"})
    assert _run(FakeTransport(_oas(), [a, b])).stop_reason == "same_day_conflict"
    c = dict(a, **{m.KEY_NAME: "別的級別"})
    assert _run(FakeTransport(_oas(), [a, c])).stop_reason == "class_conflict"


def test_latest_date_wins_and_older_conflict_does_not_block():
    old = dict(_rows()[0], **{m.KEY_DATE: "20261120", m.KEY_NAV: "10"})
    res = _run(FakeTransport(_oas(), [old] + _rows()))
    assert res.local_display["nav_date"] == "2026-11-23"


@pytest.mark.parametrize("rights", [
    m.Rights(), m.Rights("DENY"), m.Rights("ALLOWED"),  # 無依據
    m.Rights("ALLOWED", basis_ref="B", synthetic=True),  # 非測試模式的合成
])
def test_rights_not_allowed_withholds_value_but_keeps_reason(rights):
    res = _run(FakeTransport(_oas(), _rows()), rights=rights, test_mode=False)
    assert res.stop_reason == "rights_unverified" and res.withheld_reason == "rights_unverified"
    assert res.local_display is None and res.isin_matched and res.rights["R2"] != "ALLOWED"


def test_r3_r4_never_derived_from_r2():
    res = _run(FakeTransport(_oas(), _rows()))
    assert res.rights == {"R2": "ALLOWED", "R3": "UNKNOWN", "R4": "UNKNOWN"}


# ─────────────── 真網路守衛 ───────────────
def test_live_disabled_by_default_and_cli_makes_zero_requests(capsys):
    assert m.LIVE_ENABLED is False
    with pytest.raises(m.FetchStop) as e:
        m.make_live_transport()
    assert e.value.reason == "live_disabled"
    assert m.main(["--isin", GOOD_ISIN, "--confirm-non-holding"]) == 2
    assert "live_disabled" in capsys.readouterr().out


def test_live_guard_blocks_keylog_and_proxy_env():
    assert m.live_guard_errors({"SSLKEYLOGFILE": "/x"}) == ["sslkeylogfile_set"]
    assert m.live_guard_errors({"HTTPS_PROXY": "http://p"}) == ["proxy_env_set"]
    assert m.live_guard_errors({}) == []


def test_tls_context_verifies():
    import ssl

    ctx = m.build_tls_context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname is True


def test_single_get_refuses_unpinned_origin_before_any_io():
    for bad in ("http://openapi.tdcc.com.tw/x", "https://evil.com/x", "https://openapi.tdcc.com.tw:8443/x"):
        with pytest.raises(m.FetchStop) as e:
            m._single_get(bad, 10, 1.0)
        assert e.value.reason == "origin_not_pinned"


def test_wall_clock_timeout_kills_and_reaps_without_network():
    import time

    t0 = time.monotonic()
    with pytest.raises(m.FetchStop) as e:
        m.run_step_with_wall_clock(lambda: time.sleep(30), wall=0.5, reap=1.0)
    assert e.value.reason == "wall_clock_timeout" and time.monotonic() - t0 < 5


def test_wall_clock_returns_value_and_maps_errors():
    assert m.run_step_with_wall_clock(lambda: {"a": 1}, wall=5) == {"a": 1}
    r = m.run_step_with_wall_clock(lambda: m.Response(200, "application/json", b"{}"), wall=5)
    assert isinstance(r, m.Response) and r.body == b"{}"

    def _stop():
        raise m.FetchStop("oversize")

    with pytest.raises(m.FetchStop) as e:
        m.run_step_with_wall_clock(_stop, wall=5)
    assert e.value.reason == "oversize"


# ─────────────── 零落盤／零敏感／零公式（AST 靜態守衛）───────────────
def test_script_has_no_persistence_secrets_or_formula_imports():
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    imported = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imported |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            imported.add((n.module or "").split(".")[0])
    assert imported.isdisjoint({"pickle", "shelve", "sqlite3", "shutil", "tempfile", "subprocess", "requests",
                                "services", "repositories", "infra", "streamlit", "gspread", "pandas"})
    calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    attrs = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "open" not in calls
    assert attrs.isdisjoint({"write_text", "write_bytes", "dump", "mkdir", "touch", "to_csv", "to_parquet"})
    tree.body = [n for n in tree.body if not (isinstance(n, ast.Expr) and isinstance(getattr(n, "value", None), ast.Constant)
                                              and isinstance(n.value.value, str))]  # 去掉模組 docstring
    code = ast.unparse(tree)
    for needle in ("check_333_principle", "classify_eating_principal", "st.secrets", "service_account", "GOOGLE_",
                   "os.environ[", "getenv"):
        assert needle not in code, needle
    assert "'Accept-Encoding': 'identity'" in code  # 不請求壓縮


def test_pinned_limits_match_authorization():
    assert (m.MAX_REQUESTS, m.R0_MAX_BYTES, m.R1_MAX_BYTES, m.R1_MAX_ROWS, m.STEP_WALL_SECONDS) == \
        (2, 2 * 1024 * 1024, 16 * 1024 * 1024, 100_000, 20.0)
    assert m.ORIGIN_HOST == "openapi.tdcc.com.tw" and m.R0_URL.startswith("https://" + m.ORIGIN_HOST + "/")


# ─────────────── 變異負控：拿掉單一守衛，對應測試必須轉紅 ───────────────
def _load_src(src: str, name: str) -> dict:
    import types

    mod = types.ModuleType(name)
    sys.modules[name] = mod
    try:
        exec(compile(src, name, "exec"), mod.__dict__)  # noqa: S102
    finally:
        sys.modules.pop(name, None)
    return mod.__dict__


def _mutant(old: str, new: str):
    src = SRC.read_text(encoding="utf-8")
    assert src.count(old) == 1, old
    return _load_src(src.replace(old, new), "mutant_" + str(abs(hash(old)) % 10**8))


def _mut_run(ns, tp, **kw):
    return ns["run"](GOOD_ISIN, user_confirmed_non_holding=True, transport=tp, rights=ns["Rights"](
        "ALLOWED", basis_ref="B", synthetic=True), test_mode=True, today=TODAY, **kw)


def test_mutation_dot_segment_rule_removed_dot_still_caught_by_prepared_equality_then_both_removed_fails_open():
    dot = ('    if any(s in (".", "..") for s in segs):\n        raise FetchStop("dot_segment")\n', "")
    seg_dot_base = ('        if any(s in (".", "..") for s in bsegs):\n            raise FetchStop("dot_segment_base")\n', "")
    eq = ('    if prepare(url) != url:\n        raise FetchStop("prepared_url_mismatch")\n', "")
    a = _mutant(*dot)
    with pytest.raises(a["FetchStop"]) as e:
        a["assemble_url"]([{"url": "https://openapi.tdcc.com.tw"}], "/v1/./opendata/3-4")
    assert e.value.reason == "prepared_url_mismatch"  # 僅留等值核對仍擋
    src = SRC.read_text(encoding="utf-8")
    both = src.replace(dot[0], "").replace(eq[0], "")
    ns = _load_src(both, "mutant_both")
    # 兩層都拿掉：反例通過 ⇒ 證明原測試會轉紅
    assert ns["assemble_url"]([{"url": "https://openapi.tdcc.com.tw"}], "/v1/./opendata/3-4").endswith("/./opendata/3-4")
    b = _mutant(*eq)
    with pytest.raises(b["FetchStop"]) as e2:
        b["assemble_url"]([{"url": "https://openapi.tdcc.com.tw"}], "/v1/./opendata/3-4")
    assert e2.value.reason == "dot_segment"
    assert seg_dot_base[0] in src


@pytest.mark.parametrize("old,new,probe", [
    ('        if refs == {DATASET_ID}:', '        if DATASET_ID in refs:', "mixed"),
    ('    if len(hits) > 1:\n        raise FetchStop("binding_ambiguous")\n', "", "ambiguous"),
    ('        if res.rights["R2"] != "ALLOWED":\n            raise FetchStop("rights_unverified")', "        if False:\n            raise FetchStop('rights_unverified')", "rights"),
    ('        if not user_confirmed_non_holding:\n            raise FetchStop("user_confirmation_missing")', "        pass", "confirm"),
    ('    if len(at_latest) != 1:\n        raise FetchStop("same_day_conflict")', "    pass", "sameday"),
    ('        raise FetchStop("isin_not_found")', "        matched = rows", "fallback"),
])
def test_mutations_are_killed(old, new, probe):
    ns = _mutant(old, new)
    if probe == "mixed":
        oas = _oas(refs=("https://data.gov.tw/dataset/11639", "https://data.gov.tw/dataset/11641"))
        assert ns["run"](GOOD_ISIN, user_confirmed_non_holding=True, transport=FakeTransport(oas, _rows()),
                         rights=ns["Rights"]("ALLOWED", basis_ref="B", synthetic=True), test_mode=True,
                         today=TODAY).stop_reason != "binding_none"
    elif probe == "ambiguous":
        oas = {"servers": [{"url": "https://openapi.tdcc.com.tw"}], "paths": {
            "/a": {"get": {"description": "https://data.gov.tw/dataset/11641"}},
            "/b": {"get": {"description": "https://data.gov.tw/dataset/11641"}}}}
        assert _mut_run(ns, FakeTransport(oas, _rows())).stop_reason != "binding_ambiguous"
    elif probe == "rights":
        res = ns["run"](GOOD_ISIN, user_confirmed_non_holding=True, transport=FakeTransport(_oas(), _rows()),
                        rights=ns["Rights"](), test_mode=False, today=TODAY)
        assert res.local_display is not None  # 守衛被拿掉 ⇒ 無權利也放行 ⇒ 原測試會轉紅
    elif probe == "confirm":
        tp = FakeTransport(_oas(), _rows())
        ns["run"](GOOD_ISIN, user_confirmed_non_holding=False, transport=tp, today=TODAY)
        assert len(tp.calls) >= 1
    elif probe == "sameday":
        a = _rows()[0]
        res = _mut_run(ns, FakeTransport(_oas(), [a, dict(a, **{m.KEY_NAV: "99"})]))
        assert res.stop_reason != "same_day_conflict"
    elif probe == "fallback":
        rows = _rows(**{m.KEY_ISIN: "US0000000002"})
        res = _mut_run(ns, FakeTransport(_oas(), rows))
        assert res.stop_reason != "isin_not_found"
