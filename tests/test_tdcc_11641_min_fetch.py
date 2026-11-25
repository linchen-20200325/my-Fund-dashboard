"""scripts/tdcc_11641_min_fetch.py 離線測試（B-TDCC-REAL-NAV-S1；含 Work #7148209178 的 MF1～MF5）。

全檔 autouse 封鎖所有 socket 入口：任何真連線嘗試即失敗；transport／pool 一律為假。
負控／變異：test_mutation_* 以改寫來源字串的方式拿掉單一守衛，驗證對應測試會轉紅。
"""

from __future__ import annotations

import ast
import datetime as dt
import json
import os
import socket
import sys
import time
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))
SRC = _ROOT / "scripts" / "tdcc_11641_min_fetch.py"

import tdcc_11641_min_fetch as m  # noqa: E402

TODAY = dt.date(2026, 11, 24)
NOW = lambda: dt.datetime(2026, 11, 24, 3, 0, tzinfo=dt.timezone.utc)  # noqa: E731
GOOD_ISIN = "US0378331005"  # 公開範例 ISIN（Luhn 有效），非持倉、非任何使用者資料
RUN = "run-test-1"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """封鎖 socket 所有出口（SF-3：含 connect_ex、sendto、gethostbyname*、wrap_socket、urllib3.connect）。"""

    def _boom(*a, **k):
        raise AssertionError("network attempt in offline test")

    for name in ("connect", "connect_ex", "sendto", "send", "sendall"):
        monkeypatch.setattr(socket.socket, name, _boom)
    for name in ("create_connection", "getaddrinfo", "gethostbyname", "gethostbyname_ex", "gethostbyaddr"):
        monkeypatch.setattr(socket, name, _boom)
    import ssl
    import urllib3.connection

    monkeypatch.setattr(ssl.SSLContext, "wrap_socket", _boom)
    monkeypatch.setattr(urllib3.connection.HTTPConnection, "connect", _boom)


# ─────────────── 合成 OAS／資料 ───────────────
def _props(isin_desc="ISIN 碼：唯一識別單一份額級別", code_desc="基金代碼：識別該基金份額級別", isin_len=12):
    isin = {"type": "string", "description": isin_desc}
    if isin_len:
        isin.update({"minLength": isin_len, "maxLength": isin_len})
    return {m.KEY_CODE: {"type": "string", "description": code_desc},
            m.KEY_ISIN: isin,
            m.KEY_NAV: {"type": "string"}, m.KEY_DATE: {"type": "string"},
            m.KEY_CCY: {"type": "string"}, m.KEY_NAME: {"type": "string"}}


def _op(refs=("https://data.gov.tw/dataset/11641",), props=None, params=None, security=None, responses=None):
    op = {"summary": "境外基金淨值", "description": " ".join(refs),
          "responses": responses if responses is not None else {"200": {"content": {"application/json": {
              "schema": {"type": "array", "items": {"type": "object",
                                                    "properties": props if props is not None else _props()}}}}}}}
    if params is not None:
        op["parameters"] = params
    if security is not None:
        op["security"] = security
    return op


def _oas(path="/v1/opendata/X-1", servers=None, method="get", version="3.0.1", op=None, info=True, **extra):
    d = {"openapi": version, "servers": servers if servers is not None else [{"url": "https://openapi.tdcc.com.tw"}],
         "paths": {path: {method: op if op is not None else _op()}}}
    if info:
        d["info"] = {"title": "t", "version": "1.0.0"}
    d.update(extra)
    return d


def _row(**over):
    r = {m.KEY_CODE: "F001", m.KEY_ISIN: GOOD_ISIN, m.KEY_NAV: "12.3456", m.KEY_DATE: "20261123",
         m.KEY_CCY: "USD", m.KEY_NAME: "測試基金 A 類"}
    r.update(over)
    return r


def _rows(**over):
    return [_row(**over)]


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


def _rights(r2="ALLOWED", r3="UNKNOWN", r4="UNKNOWN", *, basis="TEST-BASIS", synthetic=True, ev="ok", run=RUN):
    evidence = (m.R2Evidence(run, m.R2_PURPOSE, m.R2_SCOPE_FILE, "consent#1") if ev == "ok" else ev)
    return m.Rights(r2, r3, r4, basis_ref=basis, synthetic=synthetic, r2_evidence=evidence)


ALLOWED = _rights()


def _run(tp, rights=ALLOWED, isin=GOOD_ISIN, confirmed=True, **kw):
    kw.setdefault("test_mode", True)
    return m.run(isin, user_confirmed_non_holding=confirmed, transport=tp, rights=rights, today=TODAY,
                 now=NOW, run_id=RUN, **kw)


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
    agg = res.aggregate()
    assert agg["formulas_called"] == 0 and agg["checks"] == {
        "isin_format_ok": True, "checksum_ok": True, "found": True, "pairing_unambiguous": True,
        "class_verified": True, "nav_conflict": False, "date_ok": True}
    assert agg["oas_version"] == "3.0.1" and agg["class_doc_evidence"] is True


def test_aggregate_has_no_isin_nav_name_or_url():
    res = _run(FakeTransport(_oas(), _rows()))
    blob = json.dumps(res.aggregate(), ensure_ascii=False)
    for secret in (GOOD_ISIN, "12.3456", "測試基金", "F001", "openapi.tdcc", "http"):
        assert secret not in blob


def test_multi_day_history_latest_day_wins():
    older = _row(**{m.KEY_DATE: "20261120", m.KEY_NAV: "10"})
    res = _run(FakeTransport(_oas(), [older, _row()]))
    assert res.local_display["nav_date"] == "2026-11-23" and res.aggregate()["distinct_dates"] == 2


# ─────────────── MF-5：確認／權利 ───────────────
@pytest.mark.parametrize("conf", [False, None, "no", "yes", "True", 1, 0, ""])
def test_confirmation_must_be_explicit_boolean_true(conf):
    tp = FakeTransport(_oas(), _rows())
    res = m.run(GOOD_ISIN, user_confirmed_non_holding=conf, transport=tp, today=TODAY)
    assert res.stop_reason == "user_confirmation_missing" and tp.calls == []


@pytest.mark.parametrize("bad", ["", "US0378331006", "us037833100", "123456789012", "US03783310O5X", None, 5])
def test_invalid_isin_zero_requests(bad):
    tp = FakeTransport(_oas(), _rows())
    res = m.run(bad, user_confirmed_non_holding=True, transport=tp, today=TODAY)
    assert res.stop_reason == "isin_invalid" and tp.calls == []


def test_isin_checks_split_format_vs_checksum():
    tp = FakeTransport(_oas(), _rows())
    r = m.run("US0378331006", user_confirmed_non_holding=True, transport=tp, today=TODAY)
    assert (r.checks.isin_format_ok, r.checks.checksum_ok) == (True, False)
    r = m.run("12345", user_confirmed_non_holding=True, transport=tp, today=TODAY)
    assert (r.checks.isin_format_ok, r.checks.checksum_ok) == (False, None)  # 未評估 ≠ False


@pytest.mark.parametrize("rights", [
    m.Rights(), m.Rights("DENY"), m.Rights("ALLOWED"),
    m.Rights("ALLOWED", basis_ref="   ", synthetic=True),  # 空白依據
    _rights(ev=None),  # 無 R2 證據
    _rights(ev=m.R2Evidence("   ", m.R2_PURPOSE, m.R2_SCOPE_FILE, "c")),  # 空白 run
    _rights(ev=m.R2Evidence("other-run", m.R2_PURPOSE, m.R2_SCOPE_FILE, "c")),  # 非本次
    _rights(ev=m.R2Evidence(RUN, "ai_use", m.R2_SCOPE_FILE, "c")),  # 非本機顯示用途
    _rights(ev=m.R2Evidence(RUN, m.R2_PURPOSE, "other.py", "c")),  # 非本檔
    _rights(ev=m.R2Evidence(RUN, m.R2_PURPOSE, m.R2_SCOPE_FILE, "  ")),  # 空白同意引用
    _rights(ev="evidence-as-string"),  # 型別不符
    _rights(r2=True),  # 非字串值
])
def test_rights_r2_not_proven_withholds_value_but_keeps_reason(rights):
    res = _run(FakeTransport(_oas(), _rows()), rights=rights)
    assert res.stop_reason == "rights_unverified" and res.withheld_reason == "rights_unverified"
    assert res.local_display is None and res.isin_matched and res.rights["R2"] != "ALLOWED"


def test_synthetic_rights_rejected_outside_test_mode():
    res = _run(FakeTransport(_oas(), _rows()), test_mode=False)
    assert res.stop_reason == "rights_unverified"


@pytest.mark.parametrize("r3,r4,derive,ai", [
    ("UNKNOWN", "UNKNOWN", False, False), ("ALLOWED", "UNKNOWN", True, False),
    ("ALLOWED", "DENY", True, False), ("DENY", "ALLOWED", False, False), ("ALLOWED", "ALLOWED", True, True),
])
def test_r3_r4_are_separate_axes_never_derived_from_r2(r3, r4, derive, ai):
    res = _run(FakeTransport(_oas(), _rows()), rights=_rights(r3=r3, r4=r4))
    ud = res.aggregate()["use_decisions"]
    assert res.rights["R2"] == "ALLOWED" and ud == {"display": True, "derive": derive, "ai": ai}
    assert res.aggregate()["formulas_called"] == 0


def test_r3_r4_allowed_alone_do_not_enable_display():
    res = _run(FakeTransport(_oas(), _rows()), rights=_rights(r2="UNKNOWN", r3="ALLOWED", r4="ALLOWED"))
    assert res.stop_reason == "rights_unverified" and res.aggregate()["use_decisions"] == {
        "display": False, "derive": False, "ai": False}


# ─────────────── MF-3：OAS 證據 ───────────────
def _gen():
    return [
        ("無 openapi 版本", _oas(version=None) | {"openapi": None}, "oas_version_unsupported"),
        ("swagger 2.0 不接受", {"swagger": "2.0", "paths": {}}, "oas_version_unsupported"),
        ("版本字串不完整", _oas(version="3"), "oas_version_unsupported"),
        ("缺 info.version", _oas(info=False), "oas_info_version_missing"),
        ("同名摘要、無 11641 引用", _oas(op=_op(refs=())), "binding_none"),
        ("引用 11639", _oas(op=_op(refs=("https://data.gov.tw/dataset/11639",))), "binding_none"),
        ("混引 11639+11641", _oas(op=_op(refs=("https://data.gov.tw/dataset/11639",
                                              "https://data.gov.tw/dataset/11641"))), "binding_none"),
        ("POST", _oas(method="post"), "binding_none"),
        ("舊碼 3-4 無引用", _oas(path="/v1/opendata/3-4", op=_op(refs=())), "binding_none"),
        ("必要查詢參數", _oas(op=_op(params=[{"name": "q", "in": "query", "required": True, "schema": {"type": "string"}}])),
         "op_requires_params"),
        ("path 參數", _oas(op=_op(params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}])),
         "op_requires_params"),
        ("需認證", _oas(op=_op(security=[{"apiKey": []}])), "op_requires_security"),
        ("全域認證", _oas(security=[{"apiKey": []}]), "op_requires_security"),
        ("缺 responses", _oas(op=_op(responses={})), "response_schema_missing"),
        ("無 200", _oas(op=_op(responses={"404": {}})), "response_schema_missing"),
        ("非 JSON 內容", _oas(op=_op(responses={"200": {"content": {"text/csv": {"schema": {}}}}})),
         "response_schema_missing"),
        ("回應非陣列", _oas(op=_op(responses={"200": {"content": {"application/json": {
            "schema": {"type": "object"}}}}})), "response_not_array"),
        ("items 無 properties", _oas(op=_op(responses={"200": {"content": {"application/json": {
            "schema": {"type": "array", "items": {"type": "object"}}}}}})), "response_items_not_object"),
        ("缺必要欄位", _oas(op=_op(props={m.KEY_ISIN: {}})), "response_keys_missing"),
        ("外部 $ref", _oas(op=_op(responses={"200": {"content": {"application/json": {
            "schema": {"$ref": "https://evil.example/s.json"}}}}})), "external_ref"),
        ("無法解析的內部 $ref", _oas(op=_op(responses={"200": {"content": {"application/json": {
            "schema": {"$ref": "#/components/schemas/Nope"}}}}})), "ref_unresolved"),
        ("OAS 非物件", [], "oas_shape"),
    ]


@pytest.mark.parametrize("name,oas,reason", _gen(), ids=[g[0] for g in _gen()])
def test_oas_evidence_failures_mean_zero_r1(name, oas, reason):
    body = oas if isinstance(oas, (bytes, bytearray)) else oas
    tp = FakeTransport(body, _rows())
    res = _run(tp)
    assert res.stop_reason == reason, name
    assert len(tp.calls) == 1 and res.requests_used == 1 and res.r1_status == "not_run"


def test_oas_internal_ref_is_resolved_and_synthetic_description_only_link_is_not_enough():
    resp = {"200": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/L"}}}}}
    oas = _oas(op=_op(responses=resp), components={"schemas": {
        "L": {"type": "array", "items": {"$ref": "#/components/schemas/I"}},
        "I": {"type": "object", "properties": _props()}}})
    tp = FakeTransport(oas, _rows())
    assert _run(tp).stop_reason is None and len(tp.calls) == 2  # 自足的內部 $ref 可解析
    # 僅描述含 11641 連結、但無版本／schema 的合成物件 ⇒ 0 R-1（Work 反例）
    fake = {"servers": [{"url": "https://openapi.tdcc.com.tw"}],
            "paths": {"/a": {"get": {"description": "https://data.gov.tw/dataset/11641"}}}}
    tp2 = FakeTransport(fake, _rows())
    assert _run(tp2).stop_reason == "oas_version_unsupported" and len(tp2.calls) == 1


def test_r0_not_json_and_content_rules():
    assert _run(FakeTransport(b"<html>", _rows())).stop_reason == "r0_not_json"
    for kw, reason in (({"status0": 302}, "redirect_refused"), ({"status0": 500}, "http_status_500"),
                       ({"enc": "gzip"}, "content_encoding_refused"), ({"ctype": "text/html"}, "content_type_not_json")):
        tp = FakeTransport(_oas(), _rows(), **kw)
        res = _run(tp)
        assert res.stop_reason == reason and len(tp.calls) == 1 and res.r0_status == "failed"


# ─────────────── MF-S1-1：URL 精確核證（沿用）───────────────
@pytest.mark.parametrize("servers,path,reason", [
    ([{"url": "https://openapi.tdcc.com.tw.evil.com"}], "/v1/a", "host_mismatch"),
    ([{"url": "https://openapi.tdcc.com.tw@evil.com"}], "/v1/a", "origin_has_userinfo_port_query"),
    ([{"url": "http://openapi.tdcc.com.tw"}], "/v1/a", "scheme_not_https"),
    ([{"url": "https://openapi.tdcc.com.tw:8443"}], "/v1/a", "origin_has_userinfo_port_query"),
    ([{"url": "https://openapi.tdcc.com.tw"}, {"url": "https://openapi.tdcc.com.tw/"}], "/v1/a", "server_not_unique"),
    ([{"url": "https://openapi.tdcc.com.tw"}], "/v1/./opendata/3-4", "dot_segment"),
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
    assert res.stop_reason == reason and len(tp.calls) == 1 and res.binding == f"rejected:{reason}"


def test_url_positive_controls_and_prepared_mismatch():
    assert m.assemble_url([{"url": "https://openapi.tdcc.com.tw/v1"}], "/opendata/A") == \
        "https://openapi.tdcc.com.tw/v1/opendata/A"
    assert m.assemble_url([{"url": "https://openapi.tdcc.com.tw"}], "/v1/open.data/a.b").endswith("/a.b")
    with pytest.raises(m.FetchStop) as e:
        m.assemble_url([{"url": "https://openapi.tdcc.com.tw"}], "/v1/a", prepare=lambda u: u + "x")
    assert e.value.reason == "prepared_url_mismatch"


# ─────────────── MF-1：級別核證／最近七日／逐日衝突／幣別 ───────────────
def _sel(rows, class_doc=True, isin=GOOD_ISIN):
    info = m.process_r1(json.dumps(rows, ensure_ascii=False).encode(), isin)
    return m.evaluate_selection(info, class_doc, TODAY, m.Checks()), info


@pytest.mark.parametrize("rows,reason", [
    ([_row(**{m.KEY_DATE: "20200101"})], "nav_date_stale"),  # 2020 舊日（O／Work 探針）
    ([_row(**{m.KEY_DATE: "20261125"})], "nav_date_in_future"),  # 明日
    ([_row(**{m.KEY_CCY: "ZZZ"})], "ccy_unrecognized"),  # 三碼但非 ISO
    ([_row(**{m.KEY_CCY: "CNH"})], "ccy_unrecognized"),
    ([_row(**{m.KEY_CCY: "usd"})], "ccy_unrecognized"),
    ([_row(**{m.KEY_CCY: "美元"})], "ccy_unrecognized"),
    ([_row(**{m.KEY_NAV: ""})], "nav_unreadable"), ([_row(**{m.KEY_NAV: "0"})], "nav_not_positive"),
    ([_row(**{m.KEY_NAV: "-1"})], "nav_not_positive"), ([_row(**{m.KEY_NAV: "NaN"})], "nav_not_positive"),
    ([_row(**{m.KEY_DATE: "112年1月1日"})], "nav_date_unreadable"),
    ([_row(**{m.KEY_NAME: "  "})], "class_unverified"), ([_row(**{m.KEY_CODE: " "})], "class_unverified"),
])
def test_value_level_rejections(rows, reason):
    ev, _ = _sel(rows)
    assert ev["reason"] == reason


def test_window_boundary_is_exactly_seven_days():
    ok = _row(**{m.KEY_DATE: (TODAY - dt.timedelta(days=7)).strftime("%Y%m%d")})
    old = _row(**{m.KEY_DATE: (TODAY - dt.timedelta(days=8)).strftime("%Y%m%d")})
    assert _sel([ok])[0]["reason"] is None
    assert _sel([old])[0]["reason"] == "nav_date_stale"
    assert _sel([_row(**{m.KEY_DATE: TODAY.strftime("%Y%m%d")})])[0]["reason"] is None


def test_older_day_conflict_is_caught_not_only_latest_day():
    base = _row(**{m.KEY_DATE: "20261120", m.KEY_NAV: "10"})
    conflict = _row(**{m.KEY_DATE: "20261120", m.KEY_NAV: "11"})
    ev, _ = _sel([base, conflict, _row()])
    assert ev["reason"] == "same_day_conflict"
    res = _run(FakeTransport(_oas(), [base, conflict, _row()]))
    assert res.checks.nav_conflict is True and res.checks.class_verified is False and not res.value_released


def test_identical_duplicate_rows_are_not_a_conflict():
    ev, _ = _sel([_row(), _row()])
    assert ev["reason"] is None


def test_more_than_seven_rows_fails_date_ok():
    rows = [_row(**{m.KEY_DATE: (TODAY - dt.timedelta(days=i)).strftime("%Y%m%d")}) for i in range(8)]
    ev, _ = _sel(rows)
    assert ev["reason"] == "too_many_dates"


def test_class_conflict_and_pairing_ambiguity_withhold():
    a = _row()
    assert _sel([a, _row(**{m.KEY_NAME: "別的級別", m.KEY_DATE: "20261120"})])[0]["reason"] == "class_conflict"
    # 同 ISIN 對應兩個代碼
    assert _sel([a, _row(**{m.KEY_CODE: "F002", m.KEY_DATE: "20261120"})])[0]["reason"] == "class_conflict"
    # 同代碼出現在另一個 ISIN（O 的探針：R-1 另含別的 ISIN 列）
    other = _row(**{m.KEY_ISIN: "US0000000002", m.KEY_NAV: "5"})
    ev, info = _sel([a, other])
    assert info["code_isin_max"] == 2 and ev["reason"] == "pairing_ambiguous"
    res = _run(FakeTransport(_oas(), [a, other]))
    assert res.checks.pairing_unambiguous is False and res.checks.class_verified is False and not res.value_released


def test_class_document_evidence_required_else_nav_withheld():
    for isin_desc in ("ISIN 碼", "", None):
        props = _props(isin_desc=isin_desc)
        res = _run(FakeTransport(_oas(op=_op(props=props)), _rows()))
        assert res.stop_reason == "class_evidence_insufficient" and res.local_display is None
        assert res.class_doc_evidence is False and res.checks.class_verified is False
        assert res.isin_matched and res.checks.found is True  # 已取得、身分未核、值扣下


def test_code_description_also_required():
    res = _run(FakeTransport(_oas(op=_op(props=_props(code_desc=""))), _rows()))
    assert res.stop_reason == "class_evidence_insufficient"


def test_zero_fallback_by_name_or_code_and_not_found_flags():
    rows = _rows(**{m.KEY_ISIN: "US0000000002"})
    rows[0]["基金代碼"] = GOOD_ISIN
    res = _run(FakeTransport(_oas(), rows))
    assert res.stop_reason == "isin_not_found" and res.checks.found is False and not res.value_released
    assert res.checks.class_verified is None and res.withheld_reason == "isin_not_found"


@pytest.mark.parametrize("rows,reason", [
    ([{m.KEY_ISIN: GOOD_ISIN}], "row_schema_mismatch"),
    ([_row(), {"x": 1}], "row_schema_mismatch"),  # 只首列合格、後列缺鍵（SF-2）
    ([_row(), "str"], "row_schema_mismatch"),
    ({"a": 1}, "r1_not_list"),
])
def test_r1_every_row_validated(rows, reason):
    res = _run(FakeTransport(_oas(), rows))
    assert res.stop_reason == reason and res.r1_status == "failed"


def test_r1_not_json_status_and_row_cap():
    assert _run(FakeTransport(_oas(), b"<html>")).stop_reason == "r1_not_json"
    assert _run(FakeTransport(_oas(), _rows(), status1=301)).stop_reason == "redirect_refused"
    tp = FakeTransport(_oas(), [{}] * (m.R1_MAX_ROWS + 1))
    assert _run(tp).stop_reason == "too_many_rows" and len(tp.calls) == 2


def test_oversize_bodies():
    big = b"[" + b"1," * (m.R0_MAX_BYTES // 2) + b"1]"
    assert _run(FakeTransport(big, _rows())).stop_reason == "oversize"


def test_too_many_selected_rows():
    rows = [_row(**{m.KEY_DATE: "20261123"}) for _ in range(m.MAX_SELECTED_ROWS + 1)]
    assert _run(FakeTransport(_oas(), rows)).stop_reason == "too_many_selected"


# ─────────────── MF-4：最後 HTTP 送出點 ───────────────
class _FakeHeaders(dict):
    def get(self, k, d=None):
        for kk, v in self.items():
            if kk.lower() == k.lower():
                return v
        return d


class _FakeResp:
    def __init__(self, status=200, headers=None, body=b"[]", log=None):
        self.status = status
        self.headers = _FakeHeaders(headers if headers is not None else {"Content-Type": "application/json"})
        self._body = body
        self.reads: list[int] = []
        self.released = False

    def read(self, amt=None, decode_content=False):
        self.reads.append(amt)
        out, self._body = self._body[:amt], self._body[amt:]
        return out

    def release_conn(self):
        self.released = True

    def close(self):
        pass


class _FakePool:
    instances: list = []

    def __init__(self, *a, **k):
        self.kwargs = k
        self.requests: list = []
        self.resp = _FakePool.next_resp
        _FakePool.instances.append(self)

    def request(self, method, path, **k):
        self.requests.append((method, path, k))
        return self.resp


def _patch_pool(monkeypatch, resp):
    import urllib3

    _FakePool.instances = []
    _FakePool.next_resp = resp
    monkeypatch.setattr(urllib3, "HTTPSConnectionPool", _FakePool)


PINNED = "https://openapi.tdcc.com.tw/v1/opendata/X-1"


def test_send_point_refuses_when_live_disabled_with_zero_send(monkeypatch):
    _patch_pool(monkeypatch, _FakeResp())
    with pytest.raises(m.FetchStop) as e:
        m._single_get(PINNED, 100, 1.0)
    assert e.value.reason == "live_disabled" and _FakePool.instances == []  # 0 send、0 pool


@pytest.mark.parametrize("env,reason", [({"SSLKEYLOGFILE": "/x"}, "sslkeylogfile_set"),
                                         ({"HTTPS_PROXY": "http://p"}, "proxy_env_set")])
def test_send_point_refuses_keylog_and_proxy_env_even_if_live(monkeypatch, env, reason):
    monkeypatch.setattr(m, "LIVE_ENABLED", True)
    for k in ("SSLKEYLOGFILE", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    _patch_pool(monkeypatch, _FakeResp())
    with pytest.raises(m.FetchStop) as e:
        m._single_get(PINNED, 100, 1.0)
    assert e.value.reason == reason and _FakePool.instances == []


def _live(monkeypatch):
    monkeypatch.setattr(m, "LIVE_ENABLED", True)
    for k in ("SSLKEYLOGFILE", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(k, raising=False)


@pytest.mark.parametrize("bad", ["http://openapi.tdcc.com.tw/x", "https://evil.com/x",
                                 "https://openapi.tdcc.com.tw:8443/x", "https://openapi.tdcc.com.tw/v1/./x",
                                 "https://openapi.tdcc.com.tw/v1/x?a=1", "https://openapi.tdcc.com.tw"])
def test_send_point_refuses_unpinned_url_before_any_io(monkeypatch, bad):
    _live(monkeypatch)
    _patch_pool(monkeypatch, _FakeResp())
    with pytest.raises(m.FetchStop):
        m._single_get(bad, 100, 1.0)
    assert _FakePool.instances == []


@pytest.mark.parametrize("resp,reason", [
    (_FakeResp(302, {"Content-Type": "application/json"}), "redirect_refused"),
    (_FakeResp(500), "http_status_500"),
    (_FakeResp(200, {"Content-Type": "application/json", "Content-Encoding": "gzip"}), "content_encoding_refused"),
    (_FakeResp(200, {"Content-Type": "text/html"}), "content_type_not_json"),
    (_FakeResp(200, {"Content-Type": "application/json", "Content-Length": "999999"}), "oversize"),
    (_FakeResp(200, {"Content-Type": "application/json", "Content-Length": "abc"}), "content_length_invalid"),
])
def test_send_point_rejects_before_reading_any_body(monkeypatch, resp, reason):
    _live(monkeypatch)
    _patch_pool(monkeypatch, resp)
    with pytest.raises(m.FetchStop) as e:
        m._single_get(PINNED, 100, 1.0)
    assert e.value.reason == reason and resp.reads == [] and resp.released  # 0 body read


def test_send_point_reads_at_most_cap_plus_one_exactly(monkeypatch):
    _live(monkeypatch)
    resp = _FakeResp(body=b"x" * 10_000)
    _patch_pool(monkeypatch, resp)
    with pytest.raises(m.FetchStop) as e:
        m._single_get(PINNED, 70_000 - 69_990, 1.0)  # cap=10 bytes
    assert e.value.reason == "oversize" and sum(resp.reads) == 11  # 精確 cap+1，非 64 KiB chunk
    resp2 = _FakeResp(body=b"y" * 200_000)
    _patch_pool(monkeypatch, resp2)
    with pytest.raises(m.FetchStop):
        m._single_get(PINNED, 100_000, 1.0)
    assert sum(resp2.reads) == 100_001 and max(resp2.reads) <= 64 * 1024


def test_send_point_happy_request_shape(monkeypatch):
    _live(monkeypatch)
    resp = _FakeResp(body=b"[]")
    _patch_pool(monkeypatch, resp)
    out = m._single_get(PINNED, 100, 1.0)
    pool = _FakePool.instances[0]
    (method, path, k), = pool.requests
    assert out.body == b"[]" and method == "GET" and path == "/v1/opendata/X-1"
    assert k["redirect"] is False and k["retries"] is False and k["preload_content"] is False
    assert k["headers"]["Accept-Encoding"] == "identity" and pool.kwargs["retries"] is False
    assert pool.kwargs["cert_reqs"] == "CERT_REQUIRED" and pool.kwargs["ssl_context"].check_hostname is True
    assert "proxy" not in " ".join(pool.kwargs).lower()


def test_factory_and_cli_make_zero_requests_by_default(capsys, monkeypatch):
    assert m.LIVE_ENABLED is False
    with pytest.raises(m.FetchStop) as e:
        m.make_live_runner()
    assert e.value.reason == "live_disabled"
    assert m.main(["--isin", GOOD_ISIN, "--confirm-non-holding"]) == 2
    assert "live_disabled" in capsys.readouterr().out


def test_guard_env_and_tls_context():
    import ssl

    assert m.live_guard_errors({"SSLKEYLOGFILE": "/x"}) == ["sslkeylogfile_set"]
    assert m.live_guard_errors({"HTTPS_PROXY": "http://p"}) == ["proxy_env_set"]
    assert m.live_guard_errors({}) == []
    ctx = m.build_tls_context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname is True


# ─────────────── MF-2：worker／IPC（真 spawn 子行程；零網路）───────────────
def ent_ok(x):
    return {"a": x}


def ent_sleep():
    time.sleep(30)


def ent_stop():
    raise m.FetchStop("oversize")


def ent_stop_bad_reason():
    raise m.FetchStop("含空白與中文 reason!")


def ent_raise():
    raise RuntimeError("secret detail must not leak")


def ent_big():
    return {"x": "y" * (m.IPC_MAX_BYTES + 10)}


def ent_response():
    return [1, 2, 3]


def w_partial_exit(conn, entry, args):  # 寫 4 byte 表頭＋10 bytes 後死亡
    os.write(conn.fileno(), (5000).to_bytes(4, "big") + b"0123456789")
    os._exit(1)


def w_partial_stall(conn, entry, args):  # 寫一半後卡住（子行程仍存活）
    os.write(conn.fileno(), (5000).to_bytes(4, "big") + b"0123456789")
    time.sleep(30)


def w_oversize_header(conn, entry, args):
    os.write(conn.fileno(), (10_000_000).to_bytes(4, "big") + b"x")
    time.sleep(30)


def w_silent_exit(conn, entry, args):
    os._exit(0)


def w_garbage(conn, entry, args):
    conn.send_bytes(b"Rnot-json")
    conn.close()


def w_unknown_tag(conn, entry, args):
    conn.send_bytes(b"Zxx")
    conn.close()


def test_worker_returns_value_via_spawn():
    assert m.run_in_worker(ent_ok, (7,), wall=20) == {"a": 7}


def test_wall_clock_kills_sleeping_child_and_reaps():
    t0 = time.monotonic()
    with pytest.raises(m.FetchStop) as e:
        m.run_in_worker(ent_sleep, wall=1.5, reap=2.0)
    assert e.value.reason == "wall_clock_timeout" and time.monotonic() - t0 < 12


@pytest.mark.parametrize("worker,reason,limit", [
    (w_partial_exit, "ipc_truncated", 15),  # 子行程死亡 ⇒ EOF ⇒ 立即結束（Work／O 的 PoC）
    (w_partial_stall, "wall_clock_timeout", 15),  # 寫一半卡住 ⇒ watchdog 截斷
    (w_oversize_header, "ipc_oversize", 15),
    (w_silent_exit, "ipc_truncated", 15),
    (w_garbage, "ipc_bad_payload", 15),
    (w_unknown_tag, "step_error", 15),
])
def test_ipc_faults_are_bounded_and_fixed_codes(worker, reason, limit):
    t0 = time.monotonic()
    with pytest.raises(m.FetchStop) as e:
        m.run_in_worker(ent_ok, (1,), wall=2.0, reap=2.0, worker=worker)
    assert e.value.reason == reason and time.monotonic() - t0 < limit


def test_partial_frame_does_not_hang_beyond_wall_clock():
    t0 = time.monotonic()
    with pytest.raises(m.FetchStop):
        m.run_in_worker(ent_ok, (1,), wall=1.0, reap=2.0, worker=w_partial_stall)
    assert time.monotonic() - t0 < 10  # 對照：缺修補時永久阻塞（外部 timeout 才殺）


def test_child_errors_map_to_fixed_codes_without_leaking():
    with pytest.raises(m.FetchStop) as e:
        m.run_in_worker(ent_stop, wall=20)
    assert e.value.reason == "oversize"
    with pytest.raises(m.FetchStop) as e:
        m.run_in_worker(ent_stop_bad_reason, wall=20)
    assert e.value.reason == "step_error"
    with pytest.raises(m.FetchStop) as e:
        m.run_in_worker(ent_raise, wall=20)
    assert e.value.reason == "step_error" and "secret" not in str(e.value)
    with pytest.raises(m.FetchStop) as e:
        m.run_in_worker(ent_big, wall=20)
    assert e.value.reason == "result_oversize"
    assert m.run_in_worker(ent_response, wall=20) == [1, 2, 3]


def test_unreaped_is_a_hard_stop_with_fake_context():
    import multiprocessing as mp

    real = mp.get_context("spawn")

    class _P:
        def __init__(self, target, args, daemon):
            self._p = real.Process(target=target, args=args, daemon=daemon)
            self.exitcode = None

        def start(self):
            self._p.start()

        def kill(self):
            pass  # 殺不掉

        def join(self, t=None):
            self._p.join(0.01)

        def is_alive(self):
            return True

    class _Ctx:
        Pipe = staticmethod(real.Pipe)
        Process = _P

    with pytest.raises(m.FetchStop) as e:
        m.run_in_worker(ent_ok, (1,), wall=3.0, reap=0.05, ctx=_Ctx())
    assert e.value.reason == "UNREAPED"


def test_spawn_entries_are_module_level_and_picklable():
    import pickle

    for fn in (m._entry_r0, m._entry_r1, m._worker_main):
        assert pickle.loads(pickle.dumps(fn)) is fn
    src = SRC.read_text(encoding="utf-8")
    assert 'get_context("spawn")' in src and "get_context(\"fork\")" not in src


def test_live_runner_end_to_end_with_fake_send_point_in_process(monkeypatch):
    """worker 內的 entry 與 InProcessRunner 共用同一組 process_*：以假 pool 驗 GET＋解析整鏈。"""
    _live(monkeypatch)
    oas = json.dumps(_oas()).encode()
    _patch_pool(monkeypatch, _FakeResp(body=oas))
    info = m._entry_r0("https://openapi.tdcc.com.tw/tdcc-opendata-api-docs")
    assert info["path"] == "/v1/opendata/X-1" and info["class_doc_ok"] is True
    _patch_pool(monkeypatch, _FakeResp(body=json.dumps(_rows()).encode()))
    info1 = m._entry_r1(PINNED, GOOD_ISIN)
    assert info1["rows_seen"] == 1 and info1["selected"][0][m.KEY_ISIN] == GOOD_ISIN


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
                                              and isinstance(n.value.value, str))]
    code = ast.unparse(tree)
    for needle in ("check_333_principle", "classify_eating_principal", "st.secrets", "service_account", "GOOGLE_",
                   "os.environ[", "getenv"):
        assert needle not in code, needle
    assert "'Accept-Encoding': 'identity'" in code


def test_pinned_limits_match_authorization():
    assert (m.MAX_REQUESTS, m.R0_MAX_BYTES, m.R1_MAX_BYTES, m.R1_MAX_ROWS, m.STEP_WALL_SECONDS) == \
        (2, 2 * 1024 * 1024, 16 * 1024 * 1024, 100_000, 20.0)
    assert m.ORIGIN_HOST == "openapi.tdcc.com.tw" and m.R0_URL.startswith("https://" + m.ORIGIN_HOST + "/")
    assert m.LIVE_ENABLED is False


# ─────────────── SF-3：外連負控自身有效（守衛不是空的）───────────────
@pytest.mark.parametrize("probe", [
    lambda: socket.socket().connect(("127.0.0.1", 9)),
    lambda: socket.socket().connect_ex(("127.0.0.1", 9)),
    lambda: socket.socket().sendto(b"x", ("127.0.0.1", 9)),
    lambda: socket.create_connection(("127.0.0.1", 9)),
    lambda: socket.getaddrinfo("example.invalid", 80),
    lambda: socket.gethostbyname("example.invalid"),
    lambda: socket.gethostbyname_ex("example.invalid"),
])
def test_socket_guard_blocks_every_entry(probe):
    with pytest.raises(AssertionError, match="network attempt"):
        probe()


def test_urllib3_connect_and_wrap_socket_are_blocked():
    import ssl
    import urllib3.connection

    with pytest.raises(AssertionError):
        urllib3.connection.HTTPConnection("127.0.0.1", 9).connect()
    with pytest.raises(AssertionError):
        ssl.create_default_context().wrap_socket(socket.socket.__new__(socket.socket))


# ─────────────── 變異負控：拿掉單一守衛，對應行為必須改變（⇒ 原測試會轉紅）───────────────
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


def _mutant_multi(pairs):
    src = SRC.read_text(encoding="utf-8")
    for old, new in pairs:
        assert src.count(old) == 1, old
        src = src.replace(old, new)
    return _load_src(src, "mutant_multi_" + str(abs(hash(tuple(o for o, _ in pairs))) % 10**8))


def _mrun(ns, tp, rights=None, **kw):
    r = rights or ns["Rights"]("ALLOWED", basis_ref="B", synthetic=True,
                               r2_evidence=ns["R2Evidence"](RUN, ns["R2_PURPOSE"], ns["R2_SCOPE_FILE"], "c"))
    return ns["run"](GOOD_ISIN, user_confirmed_non_holding=kw.pop("confirmed", True), transport=tp, rights=r,
                     test_mode=True, today=TODAY, run_id=RUN, **kw)


def test_mutation_url_layers_each_catch_dot_segment_and_both_removed_fails_open():
    src = SRC.read_text(encoding="utf-8")
    dot = '    if any(s in (".", "..") for s in segs):\n        raise FetchStop("dot_segment")\n'
    eq = '    if prepare(url) != url:\n        raise FetchStop("prepared_url_mismatch")\n    return url\n'
    assert src.count(dot) == 1 and src.count(eq) == 1
    a = _load_src(src.replace(dot, ""), "mut_a")
    with pytest.raises(a["FetchStop"]) as e:
        a["assemble_url"]([{"url": "https://openapi.tdcc.com.tw"}], "/v1/./opendata/3-4")
    assert e.value.reason == "prepared_url_mismatch"
    b = _load_src(src.replace(eq, "    return url\n"), "mut_b")
    with pytest.raises(b["FetchStop"]) as e2:
        b["assemble_url"]([{"url": "https://openapi.tdcc.com.tw"}], "/v1/./opendata/3-4")
    assert e2.value.reason == "dot_segment"
    both = _load_src(src.replace(dot, "").replace(eq, "    return url\n"), "mut_both")
    assert both["assemble_url"]([{"url": "https://openapi.tdcc.com.tw"}], "/v1/./opendata/3-4").endswith("/./opendata/3-4")


@pytest.mark.parametrize("old,new,probe", [
    ('        if refs == {DATASET_ID}:', '        if DATASET_ID in refs:', "mixed"),
    ('    if len(hits) > 1:\n        raise FetchStop("binding_ambiguous")\n', "", "ambiguous"),
    ('    if not isinstance(ver, str) or not _OAS3.match(ver):\n        raise FetchStop("oas_version_unsupported")\n',
     "", "noversion"),
    ('    if not all(k in props for k in REQUIRED_KEYS):\n        raise FetchStop("response_keys_missing")\n', "",
     "nokeys"),
    ('            if p.get("required") is True or p.get("in") == "path":\n'
     '                raise FetchStop("op_requires_params")', "            pass", "params"),
    ('        if any(x for x in sec):\n            raise FetchStop("op_requires_security")', "        pass", "security"),
    ('            raise FetchStop("row_type_mismatch")', '            pass', "rowtype"),
    ('        raise FetchStop("server_conflict")', '        pass', "serverconflict"),
    ('            raise FetchStop("response_key_schema_invalid")', '            pass', "keyschema"),
    ('            raise FetchStop("op_security_invalid")', '            pass', "secinvalid"),
    ('    if timed_out:\n        raise FetchStop("wall_clock_timeout")\n',
     '    if False:\n        raise FetchStop("wall_clock_timeout")\n', "latefull"),
    ('        if user_confirmed_non_holding is not True:', '        if not user_confirmed_non_holding:', "truthy"),
    ('        if not use_decisions(res.rights)["display"]:\n            raise FetchStop("rights_unverified")',
     "        if False:\n            raise FetchStop('rights_unverified')", "rights"),
    ('        base_ok = _nonblank(self.basis_ref) and', '        base_ok = bool(self.basis_ref) and', "blankbasis"),
    ('    if not class_doc_ok:\n        note("class_evidence_insufficient")', "    pass", "classdoc"),
    ('    if ccy not in ISO4217:', '    if len(ccy) != 3:', "ccy"),
    ('        if d < today - _dt.timedelta(days=WINDOW_DAYS):\n            raise FetchStop("nav_date_stale")\n', "",
     "stale"),
    ('    checks.nav_conflict = any(len(v) > 1 for v in by_date.values())  # 逐日（含較舊日）',
     '    checks.nav_conflict = len(by_date.get(max(by_date), ())) > 1 if by_date else False', "latestonly"),
    ('    checks.pairing_unambiguous = len(codes) == 1 and "" not in codes and info.get("code_isin_max") == 1',
     '    checks.pairing_unambiguous = True', "pairing"),
    ('        if not isinstance(r, dict) or not all(k in r for k in REQUIRED_KEYS):',
     '        if not isinstance(r, dict) or (not selected and not all(k in r for k in REQUIRED_KEYS)):', "firstrow"),
    ('    assert_live_allowed()\n    verify_pinned_url(url)\n', '    verify_pinned_url(url)\n', "sendguard"),
])
def test_mutations_are_killed(monkeypatch, old, new, probe):
    ns = _mutant(old, new)
    ok_tp = lambda **kw: FakeTransport(_oas(**kw), _rows())  # noqa: E731
    if probe == "mixed":
        op = _op(refs=("https://data.gov.tw/dataset/11639", "https://data.gov.tw/dataset/11641"))
        assert _mrun(ns, FakeTransport(_oas(op=op), _rows())).stop_reason != "binding_none"
    elif probe == "ambiguous":
        oas = _oas()
        oas["paths"]["/b"] = {"get": _op()}
        assert _mrun(ns, FakeTransport(oas, _rows())).stop_reason != "binding_ambiguous"
    elif probe == "noversion":
        assert _mrun(ns, FakeTransport(_oas(version="9"), _rows())).stop_reason != "oas_version_unsupported"
    elif probe == "nokeys":
        try:
            res = _mrun(ns, FakeTransport(_oas(op=_op(props={m.KEY_ISIN: {}})), _rows()))
            assert res.stop_reason != "response_keys_missing"
        except KeyError:
            pass  # 守衛被拿掉 ⇒ 行為改變（崩潰）＝被殺
    elif probe == "params":
        op = _op(params=[{"name": "q", "in": "query", "required": True}])
        assert _mrun(ns, FakeTransport(_oas(op=op), _rows())).stop_reason != "op_requires_params"
    elif probe == "security":
        assert _mrun(ns, FakeTransport(_oas(op=_op(security=[{"k": []}])), _rows())).stop_reason != "op_requires_security"
    elif probe == "truthy":
        tp = ok_tp()
        _mrun(ns, tp, confirmed="no")
        assert len(tp.calls) >= 1  # 字串 "no" 也放行 ⇒ 守衛被拿掉
    elif probe == "rights":
        res = ns["run"](GOOD_ISIN, user_confirmed_non_holding=True, transport=ok_tp(), rights=ns["Rights"](),
                        test_mode=False, today=TODAY, run_id=RUN)
        assert res.local_display is not None
    elif probe == "blankbasis":
        r = ns["Rights"]("ALLOWED", basis_ref="  ", synthetic=True,
                         r2_evidence=ns["R2Evidence"](RUN, ns["R2_PURPOSE"], ns["R2_SCOPE_FILE"], "c"))
        assert _mrun(ns, ok_tp(), rights=r).local_display is not None
    elif probe == "classdoc":
        assert _mrun(ns, FakeTransport(_oas(op=_op(props=_props(isin_desc="ISIN"))), _rows())).local_display is not None
    elif probe == "ccy":
        assert _mrun(ns, FakeTransport(_oas(), _rows(**{m.KEY_CCY: "ZZZ"}))).local_display is not None
    elif probe == "stale":
        assert _mrun(ns, FakeTransport(_oas(), _rows(**{m.KEY_DATE: "20200101"}))).local_display is not None
    elif probe == "latestonly":
        rows = [_row(**{m.KEY_DATE: "20261120", m.KEY_NAV: "10"}), _row(**{m.KEY_DATE: "20261120", m.KEY_NAV: "11"}),
                _row()]
        assert _mrun(ns, FakeTransport(_oas(), rows)).local_display is not None
    elif probe == "pairing":
        rows = [_row(), _row(**{m.KEY_ISIN: "US0000000002"})]
        assert _mrun(ns, FakeTransport(_oas(), rows)).local_display is not None
    elif probe == "firstrow":
        rows = [_row(), {"x": 1}]
        try:
            assert _mrun(ns, FakeTransport(_oas(), rows)).stop_reason != "row_schema_mismatch"
        except KeyError:
            pass  # 守衛被拿掉 ⇒ 行為改變（崩潰）＝被殺
    elif probe == "rowtype":
        try:
            res = _mrun(ns, FakeTransport(_oas(), _rows(**{m.KEY_NAME: 123})))
            assert res.stop_reason != "row_type_mismatch"
        except AttributeError:
            pass
    elif probe == "serverconflict":
        op = _op()
        op["servers"] = [{"url": "https://openapi.tdcc.com.tw/other"}]
        assert _mrun(ns, FakeTransport(_oas(op=op), _rows())).stop_reason != "server_conflict"
    elif probe == "keyschema":
        props = _props()
        props[m.KEY_NAME] = {"description": "x"}
        assert _mrun(ns, FakeTransport(_oas(op=_op(props=props)), _rows())).stop_reason != "response_key_schema_invalid"
    elif probe == "secinvalid":
        assert _mrun(ns, FakeTransport(_oas(op=_op(security="oops")), _rows())).stop_reason != "op_security_invalid"
    elif probe == "latefull":
        conn = _Conn(delay=0.2)
        proc = _Proc()
        try:
            out = ns["run_in_worker"](ent_ok, (1,), wall=0.05, reap=0.05, ctx=_ctx(conn, proc))
            assert out != {"a": 1}
        except ns["FetchStop"] as e:
            assert e.reason != "wall_clock_timeout"  # 守衛被拿掉 ⇒ 逾期結果不再以 wall_clock_timeout 拒絕＝被殺
    elif probe == "sendguard":
        ns["LIVE_ENABLED"] = False
        _patch_pool(monkeypatch, _FakeResp())
        monkeypatch.setattr(ns["__builtins__"] if False else m, "LIVE_ENABLED", False)
        out = ns["_single_get"](PINNED, 100, 1.0)  # 守衛被拿掉 ⇒ LIVE=False 仍送出
        assert out.body == b"[]" and len(_FakePool.instances) == 1


# ─────────────── 修後複驗（Work #7151535412）MF1／MF2／MF3 具名反例 ───────────────
@pytest.mark.parametrize("isin_desc,code_desc", [
    ("ISIN 碼：不代表任何份額級別", "基金代碼"),  # Work 反例：否定
    ("ISIN 碼（單一份額級別識別）", "基金代碼，不是級別識別"),  # Work 反例：代碼說明否定
    ("this ISIN is not a share class identifier", "fund code"),
    ("ISIN 碼並非單一份額級別識別", "基金代碼"),
    ("ISIN 碼（單一份額級別識別，但目前無法保證）", "基金代碼"),
    ("份額級別", "基金代碼"),  # 只有名詞、無「識別」語意
    ("ISIN 碼", "基金代碼"),
])
def test_mf1_class_doc_requires_positive_evidence_and_rejects_negation(isin_desc, code_desc):
    res = _run(FakeTransport(_oas(op=_op(props=_props(isin_desc=isin_desc, code_desc=code_desc))), _rows()))
    assert res.stop_reason == "class_evidence_insufficient" and res.local_display is None
    assert res.class_doc_evidence is False and res.checks.class_verified is False


def test_mf1_positive_class_evidence_forms_are_accepted():
    for isin_d, code_d in (("ISIN 碼：唯一識別單一份額級別", "基金代碼：識別該基金份額級別"),
                           ("ISIN：唯一對應一個份額級別", "基金代號用以識別基金"),
                           ("唯一識別單一份額級別。", "份額級別代碼：代表該份額級別"),
                           ("The ISIN uniquely identifies a single share class", "fund code identifies the fund")):
        res = _run(FakeTransport(_oas(op=_op(props=_props(isin_desc=isin_d, code_desc=code_d))), _rows()))
        assert res.stop_reason is None and res.class_doc_evidence is True, (isin_d, code_d)


@pytest.mark.parametrize("isin_desc,code_desc,why", [
    ("各份額級別共用同一 ISIN，單一份額級別識別", "基金代碼：識別該基金份額級別", "Work 反例：共享 ISIN 仍命中舊關鍵字"),
    ("ISIN 碼：唯一識別單一份額級別", "行銷活動代碼", "Work 反例：代碼說明無關"),
    ("ISIN 碼：唯一識別單一份額級別", "基金代碼：行銷活動用", "含無關詞"),
    ("ISIN 碼：唯一識別單一份額級別，多個份額共享", "基金代碼：識別該基金份額級別", "共享／多個"),
    ("ISIN 碼：識別單一份額級別", "基金代碼：識別該基金份額級別", "缺『唯一』"),
    ("ISIN 碼：單一份額級別識別碼", "基金代碼：識別該基金份額級別", "只提級別、無唯一性"),
    ("ISIN 碼：唯一識別單一份額級別", "基金代碼", "代碼說明無身分語意"),
    ("ISIN 碼：唯一識別單一份額級別", "基金代碼：for reference only", "代碼說明無身分語意（英文）"),
    ("ISIN is shared by multiple classes; uniquely identifies a single share class", "fund code identifies the fund", "英文共享"),
])
def test_mf1_shared_unrelated_or_non_unique_evidence_is_withheld(isin_desc, code_desc, why):
    res = _run(FakeTransport(_oas(op=_op(props=_props(isin_desc=isin_desc, code_desc=code_desc))), _rows()))
    assert res.stop_reason == "class_evidence_insufficient" and res.local_display is None, why
    assert res.class_doc_evidence is False and res.checks.class_verified is False


def test_mf1_text_alone_is_not_enough_isin_schema_must_restrict_valid_12_chars():
    res = _run(FakeTransport(_oas(op=_op(props=_props(isin_len=None))), _rows()))
    assert res.stop_reason == "class_evidence_insufficient" and res.local_display is None  # 無任何長度限制


def _isin_schema_case(**sch):
    props = _props(isin_len=None)
    props[m.KEY_ISIN].update(sch)
    return _run(FakeTransport(_oas(op=_op(props=props)), _rows()))


@pytest.mark.parametrize("sch,why", [
    ({"minLength": 13, "maxLength": 12}, "Work 反例：min13／max12 自相矛盾"),
    ({"minLength": 12}, "只宣告 min"), ({"maxLength": 12}, "只宣告 max"),
    ({"minLength": 12, "maxLength": 13}, "max 不是 12"), ({"minLength": 11, "maxLength": 12}, "min 不是 12"),
    ({"minLength": True, "maxLength": True}, "布林冒充 1"), ({"minLength": "12", "maxLength": "12"}, "字串數字"),
    ({"minLength": 12.0, "maxLength": 12.0}, "浮點"),
    ({"pattern": "^(12)?[A-Z0-9]+$"}, "Work 反例：不限長度的樣式"),
    ({"pattern": "^[A-Z0-9]+$"}, "不限長度"), ({"pattern": ".*"}, "任意"),
    ({"pattern": "^[A-Z]{2}[A-Z0-9]{9}$"}, "只允許 11 碼"), ({"pattern": "^[A-Z]{2}[A-Z0-9]{11}[0-9]$"}, "13 碼"),
    ({"pattern": "[A-Z0-9]{12}"}, "未錨定：11／13 碼也含 12 碼子串"),
    ({"pattern": "^[a-z]{12}$"}, "不接受合法 ISIN"), ({"pattern": "("}, "無法編譯"), ({"pattern": 12}, "非字串"),
    ({"pattern": "^" + "(a*)*" * 40 + "$"}, "過長／可疑樣式"),
    ({"minLength": 12, "maxLength": 12, "pattern": "^[A-Z0-9]+$"}, "長度對但樣式宣告了且不成立"),
])
def test_mf1_isin_schema_must_really_restrict_12_chars(sch, why):
    res = _isin_schema_case(**sch)
    assert res.stop_reason == "class_evidence_insufficient" and res.local_display is None, why


def test_mf1_isin_schema_type_must_be_string():
    res = _isin_schema_case(type="integer", minLength=12, maxLength=12)
    assert res.stop_reason == "response_key_schema_invalid" and res.local_display is None


@pytest.mark.parametrize("sch", [
    {"minLength": 12, "maxLength": 12},
    {"pattern": "^[A-Z]{2}[A-Z0-9]{9}[0-9]$"}, {"pattern": "^[A-Z]{2}[A-Z0-9]{10}$"},
    {"pattern": "^[A-Z0-9]{12}$"},
    {"minLength": 12, "maxLength": 12, "pattern": "^[A-Z]{2}[A-Z0-9]{9}[0-9]$"},
])
def test_mf1_isin_schema_that_really_restricts_12_chars_is_accepted(sch):
    assert _isin_schema_case(**sch).stop_reason is None


@pytest.mark.parametrize("isin_desc,code_desc,why", [
    ("ISIN 碼：唯一識別單一份額級別", "基金代碼欄無關；代碼附註：基金代碼不識別基金", "Work 反例：代碼說明自相矛盾"),
    ("本資料集沿用母基金 ISIN；唯一識別單一份額級別僅為欄位設計目標", "基金代碼：識別該基金份額級別", "Work 反例：沿用母基金／設計目標"),
    ("ISIN 碼：唯一識別單一份額級別。母基金 ISIN 沿用", "基金代碼：識別該基金份額級別", "附加子句"),
    ("ISIN 碼：唯一識別單一份額級別（設計目標）", "基金代碼：識別該基金份額級別", "括號內設計目標"),
    ("ISIN 碼：唯一識別單一份額級別 預留欄位", "基金代碼：識別該基金份額級別", "預留"),
    ("ISIN 碼：唯一識別單一份額級別", "基金代碼：識別該基金份額級別，但與本欄位無關", "代碼說明含無關"),
    ("ISIN 碼：唯一識別單一份額級別", "備註代碼", "無關代碼（無基金身分語意）"),
    ("ISIN 碼：唯一識別單一份額級別", "客戶代碼：識別該客戶", "他種代碼"),
    ("ISIN 碼：唯一識別單一份額級別" + "x" * 200, "基金代碼：識別該基金份額級別", "過長（可夾帶矛盾）"),
    ("ISIN 碼：唯一識別單一份額級別\n母基金", "基金代碼：識別該基金份額級別", "換行附註"),
    ("the ISIN uniquely identifies a single share class (inherited from the parent fund)", "fund code identifies the fund", "英文繼承"),
    ("ISIN 碼：唯一識別單一份額級別", "fund code identifies the fund; planned", "英文計畫"),
])
def test_mf1_contradictory_inherited_design_goal_or_unrelated_text_is_never_evidence(isin_desc, code_desc, why):
    res = _run(FakeTransport(_oas(op=_op(props=_props(isin_desc=isin_desc, code_desc=code_desc))), _rows()))
    assert res.stop_reason == "class_evidence_insufficient" and res.local_display is None, why
    assert res.class_doc_evidence is False


@pytest.mark.parametrize("field", [m.KEY_CODE, m.KEY_NAME, m.KEY_ISIN, m.KEY_CCY, m.KEY_DATE])
@pytest.mark.parametrize("bad", [123, None, ["x"], {"a": 1}, True])
def test_mf1_non_string_identity_fields_are_refused_not_stringified(field, bad):
    res = _run(FakeTransport(_oas(), _rows(**{field: bad})))
    assert res.stop_reason == "row_type_mismatch" and res.local_display is None and not res.value_released


def test_mf1_non_string_identity_in_unselected_row_also_stops():
    res = _run(FakeTransport(_oas(), [_row(), _row(**{m.KEY_ISIN: "US0000000002", m.KEY_CODE: 999})]))
    assert res.stop_reason == "row_type_mismatch"


@pytest.mark.parametrize("nav,ok", [("12.5", True), (12.5, True), (7, True), (True, False), (None, False),
                                      ([1], False), ({"a": 1}, False)])
def test_mf1_nav_type_rules(nav, ok):
    res = _run(FakeTransport(_oas(), _rows(**{m.KEY_NAV: nav})))
    assert (res.stop_reason is None) == ok, res.stop_reason


# ── MF3
def _op_with(**kw):
    op = _op()
    op.update(kw)
    return op


@pytest.mark.parametrize("name,oas,reason", [
    ("operation server 與全域不同", _oas(op=_op_with(servers=[{"url": "https://openapi.tdcc.com.tw/other"}])),
     "server_conflict"),
    ("pathItem server 與全域不同", None, "server_conflict"),
    ("全域無 server、僅 operation 宣告兩個", _oas(servers=[], op=_op_with(servers=[{"url": "a"}, {"url": "b"}])),
     "server_conflict"),
    ("三層皆無 server", {"openapi": "3.0.1", "info": {"version": "1"}, "paths": {"/v1/x": {"get": _op()}}},
     "server_not_unique"),
    ("必要欄位 schema 為 null", _oas(op=_op(props=dict(_props(), **{m.KEY_NAME: None}))), "response_key_schema_invalid"),
    ("必要欄位 schema 缺 type", _oas(op=_op(props=dict(_props(), **{m.KEY_NAV: {"description": "x"}}))),
     "response_key_schema_invalid"),
    ("必要欄位 type 為 array", _oas(op=_op(props=dict(_props(), **{m.KEY_CODE: {"type": "array"}}))),
     "response_key_schema_invalid"),
    ("security 非陣列", _oas(op=_op(security="oops")), "op_security_invalid"),
    ("security 元素非物件", _oas(op=_op(security=["x"])), "op_security_invalid"),
    ("全域 security 非陣列", _oas(security={"a": []}), "op_security_invalid"),
    ("parameters 非陣列", _oas(op=_op_with(parameters="oops")), "op_params_invalid"),
    ("parameter 非物件", _oas(op=_op(params=["x"])), "op_params_invalid"),
    ("parameter required 非布林", _oas(op=_op(params=[{"name": "q", "in": "query", "required": "yes"}])),
     "op_params_invalid"),
    ("parameter 缺 in", _oas(op=_op(params=[{"name": "q"}])), "op_params_invalid"),
    ("pathItem 為 $ref", {"openapi": "3.0.1", "info": {"version": "1"}, "servers": [{"url": "https://openapi.tdcc.com.tw"}],
                         "paths": {"/v1/x": {"$ref": "#/x", "get": _op()}}}, "path_item_ref"),
], ids=lambda x: x if isinstance(x, str) else None)
def test_mf3_effective_server_and_structure_evidence(name, oas, reason):
    if oas is None:
        oas = _oas()
        oas["paths"]["/v1/opendata/X-1"]["servers"] = [{"url": "https://openapi.tdcc.com.tw/other"}]
    tp = FakeTransport(oas, _rows())
    res = _run(tp)
    assert res.stop_reason == reason and len(tp.calls) == 1 and res.requests_used == 1, name


def test_mf3_consistent_multi_level_servers_and_empty_security_ok():
    op = _op_with(servers=[{"url": "https://openapi.tdcc.com.tw"}], security=[])
    oas = _oas(op=op, security=[{"apiKey": []}])  # operation 以 [] 明示覆蓋全域認證
    oas["paths"]["/v1/opendata/X-1"]["servers"] = [{"url": "https://openapi.tdcc.com.tw"}]
    tp = FakeTransport(oas, _rows())
    assert _run(tp).stop_reason is None and len(tp.calls) == 2


def test_mf3_effective_server_must_still_be_the_pinned_origin():
    op = _op_with(servers=[{"url": "https://evil.example"}])
    oas = _oas(op=op, servers=[{"url": "https://evil.example"}])
    tp = FakeTransport(oas, _rows())
    res = _run(tp)
    assert res.stop_reason == "host_mismatch" and len(tp.calls) == 1


# ── MF2：監督者獨立計時；逾期完整 frame 亦拒；回收不被接收阻塞（假 context，零網路）
class _Conn:
    def __init__(self, delay=0.0, payload=b'R{"a": 1}', block=None, msg=("ok", {"a": 1}), recv_delay=0.0,
                 recv_block=None):
        self.delay, self.payload, self.block, self.closed = delay, payload, block, False
        self.msg, self.recv_delay, self.recv_block = msg, recv_delay, recv_block

    def recv_bytes(self, maxlength=None):
        if self.block is not None:
            self.block.wait(30)
        time.sleep(self.delay)
        return self.payload

    def recv(self):  # decoder 行程回傳（純資料）
        if self.recv_block is not None:
            self.recv_block.wait(30)
        time.sleep(self.recv_delay)
        return self.msg

    def close(self):
        self.closed = True


class _Child:
    def close(self):
        pass


class _Proc:
    def __init__(self):
        self.killed, self.joins, self._alive = 0, [], True

    def start(self):
        pass

    def kill(self):
        self.killed += 1
        self._alive = False

    def join(self, t=None):
        self.joins.append(t)

    def is_alive(self):
        return self._alive


def _ctx(conn, proc):
    class _C:
        @staticmethod
        def Pipe(duplex=False):
            return conn, _Child()

        @staticmethod
        def Process(target, args, daemon):
            return proc

    return _C()


def test_mf2_full_frame_after_deadline_is_refused():
    conn, proc = _Conn(delay=0.2), _Proc()
    t0 = time.monotonic()
    with pytest.raises(m.FetchStop) as e:
        m.run_in_worker(ent_ok, (1,), wall=0.05, reap=0.05, ctx=_ctx(conn, proc))
    assert e.value.reason == "wall_clock_timeout" and proc.killed >= 1 and time.monotonic() - t0 < 2


def test_mf2_reap_runs_even_while_receive_is_blocked_and_exit_is_bounded():
    from threading import Event

    gate = Event()
    conn, proc = _Conn(block=gate), _Proc()
    t0 = time.monotonic()
    try:
        with pytest.raises(m.FetchStop) as e:
            m.run_in_worker(ent_ok, (1,), wall=0.2, reap=0.1, ctx=_ctx(conn, proc))
        assert e.value.reason == "wall_clock_timeout"
        assert time.monotonic() - t0 < 2 and proc.killed >= 1 and proc.joins  # 回收在接收仍阻塞時已執行
    finally:
        gate.set()


# ─────────────── 第三輪（Work #7153884392）MF1／MF2／MF3 ───────────────
# MF3：parameters 未宣告 vs null；合法位置；完整結構
def _with_params(value, level="op"):
    op = _op()
    oas = _oas(op=op)
    if level == "op":
        op["parameters"] = value
    else:
        oas["paths"]["/v1/opendata/X-1"]["parameters"] = value
    return oas


@pytest.mark.parametrize("level", ["op", "item"])
@pytest.mark.parametrize("value,name", [
    (None, "parameters: null"),
    ("oops", "字串"), ({"name": "q"}, "物件非陣列"), (0, "數字"),
    ([{"name": "q", "in": "invalid", "schema": {"type": "string"}}], "in: invalid（Work 反例）"),
    ([{"name": "q", "in": "", "schema": {"type": "string"}}], "in 為空"),
    ([{"name": "q", "in": None, "schema": {"type": "string"}}], "in 為 null"),
    ([{"name": "", "in": "query", "schema": {"type": "string"}}], "name 為空"),
    ([{"in": "query", "schema": {"type": "string"}}], "缺 name"),
    ([{"name": "q", "in": "query"}], "缺 schema／content"),
    ([{"name": "q", "in": "query", "schema": None}], "schema 為 null"),
    ([{"name": "q", "in": "query", "schema": {"type": "string"}, "required": "yes"}], "required 非布林"),
    ([{"name": "id", "in": "path", "schema": {"type": "string"}}], "path 參數未標 required"),
    ([None], "元素為 null"), (["x"], "元素非物件"),
])
def test_mf3_declared_but_invalid_parameters_mean_zero_r1(level, value, name):
    tp = FakeTransport(_with_params(value, level), _rows())
    res = _run(tp)
    assert res.stop_reason == "op_params_invalid" and len(tp.calls) == 1 and res.requests_used == 1, name


@pytest.mark.parametrize("params", [
    [{"name": "q", "in": "query", "schema": {"type": "string"}},
     {"name": "X-Trace", "in": "header", "required": False, "schema": {"type": "string"}},
     {"name": "c", "in": "cookie", "content": {"application/json": {"schema": {}}}}],
    [],
])
def test_mf3_absent_or_fully_valid_optional_parameters_are_accepted(params):
    tp = FakeTransport(_with_params(params), _rows())
    assert _run(tp).stop_reason is None and len(tp.calls) == 2
    assert _run(FakeTransport(_oas(), _rows())).stop_reason is None  # 未宣告鍵＝合法


def test_mf3_parameter_via_valid_ref_is_resolved_and_bad_ref_stops():
    oas = _with_params([{"$ref": "#/components/parameters/Q"}])
    oas["components"] = {"parameters": {"Q": {"name": "q", "in": "query", "required": True, "schema": {"type": "string"}}}}
    assert _run(FakeTransport(oas, _rows())).stop_reason == "op_requires_params"
    oas2 = _with_params([{"$ref": "#/components/parameters/Missing"}])
    assert _run(FakeTransport(oas2, _rows())).stop_reason == "ref_unresolved"


# 第三輪突變：拿掉新守衛，行為必須改變
@pytest.mark.parametrize("old,new,probe", [
    ('        if not isinstance(plist, list):  # 含 null\n            raise FetchStop("op_params_invalid")\n',
     '        if plist is None:\n            continue\n        if not isinstance(plist, list):\n            raise FetchStop("op_params_invalid")\n',
     "paramsnull"),
    ('p.get("in") not in _PARAM_IN', 'False', "paramin"),
    ('    if has_schema == has_content:  # 同存或皆無\n        raise FetchStop("op_params_invalid")\n',
     '    if not (has_schema or has_content):\n        raise FetchStop("op_params_invalid")\n', "bothrep"),
    ('    if not isinstance(c, dict) or len(c) != 1:  # 空、或多個 media entries\n        raise FetchStop("op_params_invalid")\n',
     '    if not isinstance(c, dict):\n        raise FetchStop("op_params_invalid")\n', "multimedia"),
    ('            if ident in seen:\n                raise FetchStop("op_params_invalid")  # 同層 name＋in 不得重複\n',
     '            if False:\n                raise FetchStop("op_params_invalid")\n', "dupparam"),
    ('                and _isin_schema_restricts_12(props[KEY_ISIN]))', ')', "structure"),
    ('code_txt and _CODE_FULL.fullmatch(code_txt)', 'code_txt', "codeidentity"),
    ('            t_dec.join(_left())\n', '            t_dec.join()\n', "decodejoin"),
    ('    t_rx.join(_left())\n', '    t_rx.join()\n', "rxjoin"),
    ('                    box["msg"] = dparent.recv()', '                    box["msg"] = ("ok", _decode_ipc(body))', "paredecode"),
    ('        if timed_out or pr.is_alive():\n            _safe_kill(pr)', '        if False:\n            _safe_kill(pr)', "nokill"),
])
def test_round3_mutations_are_killed(old, new, probe):
    ns = _mutant(old, new)
    if probe == "paramsnull":
        assert _mrun(ns, FakeTransport(_with_params(None), _rows())).stop_reason != "op_params_invalid"
    elif probe == "paramin":
        bad = [{"name": "q", "in": "invalid", "schema": {"type": "string"}}]
        assert _mrun(ns, FakeTransport(_with_params(bad), _rows())).stop_reason != "op_params_invalid"
    elif probe == "bothrep":
        both = [{"name": "q", "in": "query", "schema": {"type": "string"}, "content": {"application/json": {}}}]
        assert _mrun(ns, FakeTransport(_with_params(both), _rows())).stop_reason != "op_params_invalid"
    elif probe == "multimedia":
        two = [{"name": "q", "in": "query", "content": {"application/json": {}, "text/plain": {}}}]
        try:
            assert _mrun(ns, FakeTransport(_with_params(two), _rows())).stop_reason != "op_params_invalid"
        except ValueError:
            pass  # 守衛被拿掉 ⇒ 行為改變（解包失敗）＝被殺
    elif probe == "dupparam":
        dup = [{"name": "q", "in": "query", "schema": {"type": "string"}}] * 2
        assert _mrun(ns, FakeTransport(_with_params(dup), _rows())).stop_reason != "op_params_invalid"
    elif probe == "structure":
        sch = _props(isin_len=None)
        sch[m.KEY_ISIN].update({"minLength": 13, "maxLength": 12})
        assert _mrun(ns, FakeTransport(_oas(op=_op(props=sch)), _rows())).local_display is not None
    elif probe == "codeidentity":
        res = _mrun(ns, FakeTransport(_oas(op=_op(props=_props(code_desc="備註代碼"))), _rows()))
        assert res.local_display is not None  # 無關代碼說明仍放行 ⇒ 守衛被拿掉
    elif probe == "decodejoin":
        from threading import Event, Timer

        gate = Event()
        Timer(0.6, gate.set).start()
        t0 = time.monotonic()
        try:
            try:
                ns["run_in_worker"](ent_ok, (1,), wall=0.1, reap=0.05, ctx=_ctx(_Conn(recv_block=gate), _Proc()))
            except ns["FetchStop"]:
                pass  # 逾期結果仍被事後拒絕，但監督者已被拖過牆鐘
            assert time.monotonic() - t0 >= 0.5  # 無期限等解碼 ⇒ 回傳時刻不再受牆鐘約束＝被殺
        finally:
            gate.set()
    elif probe == "rxjoin":
        from threading import Event, Timer

        gate = Event()
        Timer(0.6, gate.set).start()
        t0 = time.monotonic()
        try:
            try:
                ns["run_in_worker"](ent_ok, (1,), wall=0.1, reap=0.05, ctx=_ctx(_Conn(block=gate), _Proc()))
            except ns["FetchStop"]:
                pass
            assert time.monotonic() - t0 >= 0.5  # 無期限等接收 ⇒ 回傳時刻不受牆鐘約束＝被殺
        finally:
            gate.set()
    elif probe == "paredecode":
        calls = []
        ns["_decode_ipc"] = lambda body: (calls.append(1), {"a": 1})[1]
        ns["run_in_worker"](ent_ok, (1,), wall=2.0, reap=0.05, ctx=_ctx(_Conn(), _Proc()))
        assert calls  # 監督者行程自己解碼了 ⇒ 與正常行為（0 次）不同＝被殺
    elif probe == "nokill":
        proc = _Proc()
        proc._alive = False  # 已死：正常路徑不會殺；逾期路徑才必須殺
        with pytest.raises(ns["FetchStop"]):
            ns["run_in_worker"](ent_ok, (1,), wall=0.05, reap=0.05, ctx=_ctx(_Conn(delay=0.3), proc))
        assert proc.killed == 0  # 逾期未殺 ⇒ 與正常行為（killed≥1）不同＝被殺


_MARKERS = '    if any(n in low for n in _NEGATION) or any(x in low for x in _SHARED):\n        return None\n'
_CLAUSES = '    if re.search(r"[，；;,\\n]", desc.strip().rstrip("。.")):\n        return None  # 多子句／附加說明（可夾帶矛盾）一律不採證\n'


@pytest.mark.parametrize("texts", [
    ("ISIN 碼：唯一識別單一份額級別，惟並非對所有基金成立", "基金代碼：識別該基金份額級別"),  # 否定
    ("各份額級別皆可識別；唯一識別單一份額級別", "基金代碼：識別該基金份額級別"),  # 泛稱
    ("本資料集沿用母基金 ISIN；唯一識別單一份額級別僅為欄位設計目標", "基金代碼：識別該基金份額級別"),  # 沿用／設計目標
    ("ISIN 碼：唯一識別單一份額級別", "基金代碼欄無關；代碼附註：基金代碼不識別基金"),  # 矛盾
])
def test_round3_text_layers_overlap_but_removing_all_of_them_releases(texts):
    """文字防線是多層（標記／子句／整句 fullmatch）；全部拿掉才放行，證明每個反例都由這幾層擋住。"""
    pairs = [(_MARKERS, "    pass\n"), (_CLAUSES, "    pass\n"),
             ("_ISIN_FULL.fullmatch(isin_txt)", "isin_txt"), ("_CODE_FULL.fullmatch(code_txt)", "code_txt")]
    ns = _mutant_multi(pairs)
    res = _mrun(ns, FakeTransport(_oas(op=_op(props=_props(isin_desc=texts[0], code_desc=texts[1]))), _rows()))
    assert res.local_display is not None
    real = _run(FakeTransport(_oas(op=_op(props=_props(isin_desc=texts[0], code_desc=texts[1]))), _rows()))
    assert real.local_display is None and real.stop_reason == "class_evidence_insufficient"


def test_mf1_generic_all_classes_wording_is_withheld_even_with_unique_phrase():
    res = _run(FakeTransport(_oas(op=_op(props=_props(isin_desc="各份額級別皆可識別；唯一識別單一份額級別"))), _rows()))
    assert res.stop_reason == "class_evidence_insufficient" and res.local_display is None


# ─────────────── MF3：Parameter Object（schema／content 互斥且恰一；同層不重複）───────────────
def _p(**kw):
    d = {"name": "q", "in": "query"}
    d.update(kw)
    return d


@pytest.mark.parametrize("level", ["op", "item"])
@pytest.mark.parametrize("plist,why", [
    ([_p(schema={"type": "string"}, content={"application/json": {}})], "Work 反例：schema＋content 同存"),
    ([_p()], "兩者皆無"),
    ([_p(content={})], "Work 反例：空 content"),
    ([_p(content={"application/json": {}, "text/plain": {}})], "Work 反例：兩個 media entries"),
    ([_p(content={"not a media type": {}})], "非法 media type 字串"),
    ([_p(content={"": {}})], "空 media type"),
    ([_p(content={"application/json": None})], "media object 為 null"),
    ([_p(content={"application/json": "x"})], "media object 非物件"),
    ([_p(content={"application/json": {"schema": "x"}})], "media schema 非物件"),
    ([_p(content=[("application/json", {})])], "content 非物件"),
    ([_p(content=None)], "content 為 null（無 schema）"),
    ([_p(schema="x")], "schema 非物件"),
    ([_p(schema=None, content={"application/json": {}})], "schema 為 null＋content"),
    ([_p(schema={"type": "string"}), _p(schema={"type": "integer"})], "Work 反例：同層重複 name＋in"),
    ([_p(name="X-Id", **{"in": "header"}, schema={"type": "string"}),
      _p(name="x-id", **{"in": "header"}, schema={"type": "string"})], "header 名稱大小寫不分的重複"),
    ([_p(schema={"type": "string"}), {"$ref": "#/components/parameters/Q"}], "經 $ref 重複"),
])
def test_mf3_parameter_object_representation_and_uniqueness(level, plist, why):
    oas = _with_params(plist, level)
    oas["components"] = {"parameters": {"Q": _p(schema={"type": "string"})}}
    tp = FakeTransport(oas, _rows())
    res = _run(tp)
    assert res.stop_reason == "op_params_invalid" and len(tp.calls) == 1 and res.requests_used == 1, why


@pytest.mark.parametrize("plist", [
    [_p(schema={"type": "string"})],
    [_p(content={"application/json": {}})],
    [_p(content={"application/json; charset=utf-8": {"schema": {"type": "string"}}})],
    [_p(schema={"type": "string"}), _p(name="q", **{"in": "header"}, schema={"type": "string"})],  # 同名不同位置
    [_p(name="X-Id", **{"in": "header"}, schema={"type": "string"}),
     _p(name="X-Other", **{"in": "header"}, schema={"type": "string"})],
])
def test_mf3_exactly_one_valid_representation_is_accepted(plist):
    tp = FakeTransport(_with_params(plist), _rows())
    assert _run(tp).stop_reason is None and len(tp.calls) == 2


def test_mf3_same_name_in_across_levels_is_allowed_override():
    oas = _with_params([_p(schema={"type": "string"})], "item")
    oas["paths"]["/v1/opendata/X-1"]["get"]["parameters"] = [_p(schema={"type": "integer"})]
    assert _run(FakeTransport(oas, _rows())).stop_reason is None


# ─────────────── MF2：監督者獨立於解碼所持 GIL（釋放／持有兩種堵塞負控）───────────────
class _RecProc(_Proc):
    pid = 4242


def _rec_ctx(conn, procs):
    class _C:
        @staticmethod
        def Pipe(duplex=False):
            return conn, _Child()

        @staticmethod
        def Process(target, args, daemon):
            pr = _RecProc()
            pr.target, pr.args = target, args
            procs.append(pr)
            return pr

    return _C()


def w_frame_then_beat(conn, entry, args):
    """送出完整 frame 後持續寫心跳（共享記憶體）直到被殺；用來量測『何時被殺』。"""
    (beat,) = args
    conn.send_bytes(b'R{"a": 1}')
    while True:
        beat.value = time.time()
        time.sleep(0.005)




# ─────────────── 第四輪（Work #7159400965）MF1／MF2／MF3 ───────────────
# MF1：ISIN schema 只採「可證固定寬度」的保守子集
@pytest.mark.parametrize("sch,why", [
    ({"pattern": "^[A-Z]{2}[A-Z0-9]{10}([A-Z0-9]{2})?$"}, "Work 反例：可選尾，14 碼也匹配"),
    ({"minLength": 12, "maxLength": 12, "pattern": None}, "Work 反例：pattern:null"),
    ({"minLength": 12, "maxLength": 12, "enum": [""]}, "Work 反例：矛盾 enum"),
    ({"minLength": 12, "maxLength": 12, "enum": ["US0378331005"]}, "enum 無法證明（保守扣值）"),
    ({"minLength": 12, "maxLength": 12, "const": "US0378331005"}, "const"),
    ({"minLength": 12, "maxLength": 12, "oneOf": [{"type": "string"}]}, "oneOf"),
    ({"minLength": 12, "maxLength": 12, "anyOf": [{"type": "string"}]}, "anyOf"),
    ({"minLength": 12, "maxLength": 12, "allOf": [{"maxLength": 3}]}, "allOf 可能自相矛盾"),
    ({"minLength": 12, "maxLength": 12, "not": {}}, "not"),
    ({"minLength": 12, "maxLength": 12, "nullable": True}, "nullable"),
    ({"minLength": 12, "maxLength": None}, "maxLength:null"),
    ({"minLength": None, "maxLength": 12}, "minLength:null"),
    ({"minLength": 12, "maxLength": 12, "format": None}, "format:null"),
    ({"pattern": "^[A-Z]{12}|x$"}, "alternation"),
    ({"pattern": "^[A-Z]{10,12}$"}, "{n,m} 可變寬度"), ({"pattern": "^[A-Z]{12,}$"}, "{n,}"),
    ({"pattern": "^[A-Z0-9]*$"}, "*"), ({"pattern": "^[A-Z0-9]+$"}, "+"), ({"pattern": "^[A-Z0-9]?{12}$"}, "?"),
    ({"pattern": "^.{12}$"}, "any char"), ({"pattern": "^\\w{12}$"}, "escape class"),
    ({"pattern": "^(?:[A-Z]{12})$"}, "group"), ({"pattern": "^[A-Z]{012}$"}, "前導零"), ({"pattern": "^[A-Z]{0}$"}, "{0}"),
    ({"pattern": "^[Z-A]{12}$"}, "反向範圍"), ({"pattern": "^[A-9]{12}$"}, "跨類範圍"),
    ({"pattern": "^[a-z]{12}$"}, "寬度可證但不接受合法 ISIN 範例"),
    ({"pattern": "[A-Z0-9]{12}"}, "未錨定"), ({"pattern": "^[A-Z0-9]{12}"}, "缺 $"), ({"pattern": "^$"}, "空"),
    ({"pattern": "^[A-Z]{2}[A-Z0-9]{11}$"}, "13 碼"), ({"pattern": "^[A-Z]{2}[A-Z0-9]{9}$"}, "11 碼"),
    ({"pattern": 12}, "非字串"), ({"pattern": ""}, "空字串"), ({"pattern": "^" + "[A-Z]" * 70 + "$"}, "過長"),
])
def test_mf4_isin_schema_must_be_provably_fixed_width_12(sch, why):
    res = _isin_schema_case(**sch)
    assert res.stop_reason == "class_evidence_insufficient" and res.local_display is None, why


@pytest.mark.parametrize("sch", [
    {"pattern": "^[A-Z]{2}[A-Z0-9]{9}[0-9]$"}, {"pattern": "^[A-Z]{2}[A-Z0-9]{10}$"}, {"pattern": "^[A-Z0-9]{12}$"},
    {"pattern": "^[A-Z][A-Z][A-Z0-9]{9}[0-9]$"}, {"pattern": "^[A-Z0-9]{2}[A-Z0-9]{10}$"},
    {"pattern": "^[A-Z]{2}[A-Z0-9]{9}[0-9]$", "minLength": 12, "maxLength": 12},
    {"minLength": 12, "maxLength": 12, "description": "x", "example": "US0378331005", "format": "isin"},
])
def test_mf4_provable_fixed_width_12_schemas_are_accepted(sch):
    sch = dict(sch)
    desc = sch.pop("description", None)
    res = _isin_schema_case(**sch)
    assert res.stop_reason is None, sch
    del desc


def test_mf4_pattern_width_helper_is_exact():
    assert m._provable_pattern_width("^[A-Z]{2}[A-Z0-9]{9}[0-9]$") == 12
    assert m._provable_pattern_width("^[A-Z0-9]{12}$") == 12
    assert m._provable_pattern_width("^[A-Z]$") == 1
    for bad in ("^[A-Z]{2}([A-Z0-9]{2})?$", "^[A-Z]+$", "^(a)$", "[A-Z]{12}", "^$", None, 5):
        assert m._provable_pattern_width(bad) is None, bad


# MF3：media type 參數語法與未解析 schema 參照
@pytest.mark.parametrize("level", ["op", "item"])
@pytest.mark.parametrize("plist,why", [
    ([_p(content={"application/json; charset": {}})], "Work 反例：無值的 media type 參數"),
    ([_p(content={"application/json;charset=": {}})], "空參數值"),
    ([_p(content={"application/json;": {}})], "結尾分號"), ([_p(content={"application/": {}})], "缺子型"),
    ([_p(content={"/json": {}})], "缺主型"), ([_p(content={"application/json charset=utf-8": {}})], "空白代替分號"),
    ([_p(content={'application/json; charset="utf-8': {}})], "引號未閉合"),
    ([_p(schema={"$ref": "#/components/schemas/Absent"})], "Work 反例：參數 schema 的未解析 $ref"),
    ([_p(content={"application/json": {"schema": {"$ref": "#/components/schemas/Absent"}}})], "Work 反例：media schema 未解析 $ref"),
    ([_p(schema={"type": "array", "items": {"$ref": "#/components/schemas/Absent"}})], "巢狀未解析 $ref"),
    ([_p(schema={"allOf": [{"$ref": "#/components/schemas/Absent"}]})], "allOf 內未解析 $ref"),
    ([_p(schema={"$ref": "https://evil.example/s.json"})], "外部 $ref"),
    ([_p(schema={"$ref": "#/components/schemas/Dangling"})], "$ref 指向的 schema 內含未解析 $ref"),
])
def test_mf5_media_type_syntax_and_unresolved_schema_refs_mean_zero_r1(level, plist, why):
    oas = _with_params(plist, level)
    oas["components"] = {"schemas": {"Dangling": {"$ref": "#/components/schemas/Absent"},
                                     "Ok": {"type": "string"}}}
    tp = FakeTransport(oas, _rows())
    res = _run(tp)
    assert res.stop_reason in ("op_params_invalid", "ref_unresolved", "external_ref") and len(tp.calls) == 1, why
    assert res.requests_used == 1


@pytest.mark.parametrize("plist", [
    [_p(content={"application/json; charset=utf-8": {}})], [_p(content={'application/json; charset="utf-8"': {}})],
    [_p(content={"application/json;charset=utf-8;q=1": {"schema": {"type": "string"}}})],
    [_p(content={"text/plain": {"schema": {"$ref": "#/components/schemas/Ok"}}})],
    [_p(schema={"$ref": "#/components/schemas/Ok"})],
    [_p(schema={"$ref": "#/components/schemas/Cyc"})],  # 環狀但皆可解析
    [_p(schema={"type": "array", "items": {"$ref": "#/components/schemas/Ok"}})],
])
def test_mf5_valid_media_types_and_resolvable_refs_are_accepted(plist):
    for level in ("op", "item"):
        oas = _with_params(plist, level)
        oas["components"] = {"schemas": {"Ok": {"type": "string"}, "Cyc": {"type": "object",
                                                                            "properties": {"a": {"$ref": "#/components/schemas/Cyc"}}}}}
        tp = FakeTransport(oas, _rows())
        assert _run(tp).stop_reason is None and len(tp.calls) == 2, plist


# MF2：可能持 GIL 的解碼移到獨立 decoder 行程；分別斷言「監督者回傳時間」與「worker／decoder 停止時間」
import functools  # noqa: E402


def d_hold_gil(rec, conn, body):
    """decoder 替身：進入後記錄 pid，並以持有 GIL 的原生呼叫堵 8 秒（永不完成，除非被殺）。"""
    import ctypes

    rec[0] = float(os.getpid())
    ctypes.PyDLL(None).sleep(8)
    rec[2] = 1.0
    conn.send(("ok", {"a": 1}))


def d_release_gil(rec, conn, body):
    rec[0] = float(os.getpid())
    time.sleep(8)  # 釋放 GIL 的堵塞
    rec[2] = 1.0
    conn.send(("ok", {"a": 1}))


def d_crash(conn, body):
    os._exit(1)


def _pid_alive(pid):
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _blocked_decoder_scenario(decoder_fn, wall=4.0):
    import multiprocessing as mp

    ctx = mp.get_context("spawn")
    beat, rec = ctx.Value("d", 0.0), ctx.Array("d", 3)
    t_epoch, t0 = time.time(), time.monotonic()
    with pytest.raises(m.FetchStop) as e:
        m.run_in_worker(ent_ok, (beat,), wall=wall, reap=2.0, ctx=ctx, worker=w_frame_then_beat,
                        decoder=functools.partial(decoder_fn, rec))
    ret = time.monotonic() - t0
    assert e.value.reason == "wall_clock_timeout"
    # ① 監督者回傳硬牆鐘：回傳時刻≈牆鐘（不被 8 秒的解碼拖住）
    assert wall - 0.1 <= ret <= wall + 1.0, f"監督者回傳 {ret:.2f}s（牆鐘 {wall}s）"
    # ② worker 停止時間：最後心跳不得晚於監督者回傳，且 worker 已被回收
    last = beat.value
    assert t_epoch + 0.1 < last <= t_epoch + ret + 0.1, f"worker 最後心跳 {last - t_epoch:.2f}s／回傳 {ret:.2f}s"
    # ③ decoder 確實進入過、未完成、且已被殺
    assert rec[0] > 0 and rec[2] == 0.0 and not _pid_alive(rec[0])
    assert not mp.active_children()


def test_mf2_hold_gil_decoder_cannot_delay_supervisor_return_and_is_killed():
    _blocked_decoder_scenario(d_hold_gil)


def test_mf2_release_gil_decoder_cannot_delay_supervisor_return_and_is_killed():
    _blocked_decoder_scenario(d_release_gil)


def test_mf2_real_spawn_fast_path_and_decoder_error_codes():
    import multiprocessing as mp

    assert m.run_in_worker(ent_ok, (7,), wall=20) == {"a": 7}
    assert not mp.active_children()
    with pytest.raises(m.FetchStop) as e:
        m.run_in_worker(ent_ok, (1,), wall=20, worker=w_garbage)
    assert e.value.reason == "ipc_bad_payload"
    with pytest.raises(m.FetchStop) as e:
        m.run_in_worker(ent_ok, (1,), wall=20, decoder=d_crash)
    assert e.value.reason == "ipc_truncated"
    assert not mp.active_children()


def test_mf2_supervisor_process_never_calls_json_decode(monkeypatch):
    def _boom(body):
        raise AssertionError("supervisor must not decode")

    monkeypatch.setattr(m, "_decode_ipc", _boom)
    procs: list = []
    assert m.run_in_worker(ent_ok, (1,), wall=5.0, reap=0.05, ctx=_rec_ctx(_Conn(), procs)) == {"a": 1}
    assert [pr.target for pr in procs] == [m._worker_main, m._decoder_main]  # decoder 為獨立行程


def test_mf2_decoder_reports_plain_data_only():
    assert m._plain({"a": [1, 2.5, None, True, "x", {"b": "c"}]})
    for bad in ({1: "x"}, {"a": object()}, {"a": (1, 2)}, {"a": {"b": {"c": {"d": {"e": {"f": {"g": {"h": {"i": 1}}}}}}}}}):
        assert not m._plain(bad)
    box: list = []

    class _C:
        def send(self, msg):
            box.append(msg)

        def close(self):
            pass

    m._decoder_main(_C(), b'{"a": 1}')
    m._decoder_main(_C(), b"not-json")
    assert box == [("ok", {"a": 1}), ("err", "ipc_bad_payload")]


@pytest.mark.parametrize("old,new,probe", [
    ('    if set(sch) - _ISIN_SCHEMA_KEYS or any(v is None for v in sch.values()):\n        return False\n', '', "keys"),
    ('    if not isinstance(mt, str) or not _MEDIA_TYPE.fullmatch(mt) or not isinstance(mo, dict):',
     '    if not isinstance(mt, str) or not isinstance(mo, dict):', "mediatype"),
    ('        _check_refs_resolvable(p["schema"], oas)\n', '', "paramref"),
    ('        _check_refs_resolvable(mo["schema"], oas)', '        pass', "mediaref"),
])
def test_round4_mutations_are_killed(old, new, probe):
    ns = _mutant(old, new)
    ok = lambda **kw: _mrun(ns, FakeTransport(_oas(**kw), _rows()))  # noqa: E731
    if probe == "keys":
        for extra in ({"enum": [""]}, {"format": None}):
            props = _props(isin_len=12)
            props[m.KEY_ISIN].update(extra)
            assert ok(op=_op(props=props)).local_display is not None  # 守衛被拿掉 ⇒ 矛盾 enum／null 也放行
    elif probe == "width":
        props = _props(isin_len=None)
        props[m.KEY_ISIN]["pattern"] = "^[A-Z]{2}[A-Z0-9]{12}$"
        assert ok(op=_op(props=props)).local_display is not None  # 14 碼樣式也放行
    elif probe == "mediatype":
        bad = [{"name": "q", "in": "query", "content": {"application/json; charset": {}}}]
        assert _mrun(ns, FakeTransport(_with_params(bad), _rows())).stop_reason != "op_params_invalid"
    elif probe == "paramref":
        bad = [{"name": "q", "in": "query", "schema": {"$ref": "#/components/schemas/Absent"}}]
        assert _mrun(ns, FakeTransport(_with_params(bad), _rows())).stop_reason is None
    elif probe == "mediaref":
        bad = [{"name": "q", "in": "query", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Absent"}}}}]
        assert _mrun(ns, FakeTransport(_with_params(bad), _rows())).stop_reason is None


def test_round4_width_proof_and_sample_sanity_are_both_needed_remove_both_releases_14_chars():
    pairs = [('_provable_pattern_width(sch["pattern"]) == 12', '_provable_pattern_width(sch["pattern"]) is not None'),
             ('            ok_pat = all(rx.fullmatch(x) for x in ("US0378331005", "JP3633400001"))', '            ok_pat = True')]
    ns = _mutant_multi(pairs)
    props = _props(isin_len=None)
    props[m.KEY_ISIN]["pattern"] = "^[A-Z]{2}[A-Z0-9]{12}$"  # 可證寬度 14
    assert _mrun(ns, FakeTransport(_oas(op=_op(props=props)), _rows())).local_display is not None
    real = _run(FakeTransport(_oas(op=_op(props=props)), _rows()))
    assert real.stop_reason == "class_evidence_insufficient" and real.local_display is None
