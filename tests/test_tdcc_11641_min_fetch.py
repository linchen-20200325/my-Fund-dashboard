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
    rid = m.prepare_run()   # 真實模式只接受 prepare_run() 發出的 nonce（逐次 R2；r97 S3）；證據綁同一個 nonce
    res = m.run(GOOD_ISIN, user_confirmed_non_holding=True, transport=FakeTransport(_oas(), _rows()), rights=_rights(run=rid), today=TODAY,
                now=NOW, run_id=rid, test_mode=False)
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
                        test_mode=True, today=TODAY, run_id=RUN)   # r97：真實模式另有 nonce 與顯示閘兩層擋，此處改用測試模式單獨檢驗「權利守衛」那一層
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
    def __init__(self, delay=0.0, payload=None, block=None, msg=("ok", {"a": 1}), recv_delay=0.0,
                 recv_block=None):
        payload = b"R" + m._tlv_encode({"a": 1}) if payload is None else payload
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
    ('    rx.join(max(0.0, wall - (time.monotonic() - t0)))\n', '    rx.join()\n', "rxjoin"),
    ('    if timed_out or p.is_alive():\n        _safe_kill(p)\n', '    if False:\n        _safe_kill(p)\n', "nokill"),
    ('    if (time.monotonic() - t0) > wall:\n        timed_out = True  # 逾期任何結果一律不用\n',
     '    pass\n', "latecheck"),
])
def test_round3_mutations_are_killed(monkeypatch, old, new, probe):
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
    elif probe == "latecheck":
        calls = {"n": 0}
        real = time.monotonic

        def fake():
            calls["n"] += 1
            return 0.0 if calls["n"] <= 2 else 100.0  # 接收剛好在邊界完成，但完成後時鐘已逾牆鐘

        monkeypatch.setattr(time, "monotonic", fake)
        try:
            out = ns["run_in_worker"](ent_ok, (1,), wall=5.0, reap=0.05, ctx=_ctx(_Conn(), _Proc()))
        except ns["FetchStop"] as e:
            assert e.reason == "wall_clock_timeout"
            out = None
        finally:
            monkeypatch.setattr(time, "monotonic", real)
        assert out == {"a": 1}  # 守衛被拿掉 ⇒ 逾期結果被接受＝與正常行為（拒絕）不同
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
    conn.send_bytes(b"R" + m._tlv_encode({"a": 1}))
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


def _pid_alive(pid):
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@pytest.mark.parametrize("old,new,probe", [
    ('    if set(sch) - _ISIN_SCHEMA_KEYS or any(v is None for v in sch.values()):\n        return False\n', '', "keys"),
    ('    if not isinstance(mt, str) or not _MEDIA_TYPE.fullmatch(mt) or not isinstance(mo, dict):',
     '    if not isinstance(mt, str) or not isinstance(mo, dict):', "mediatype"),
    ('        _validate_schema_object(p["schema"], oas)\n', '', "paramref"),
    ('        _validate_schema_object(mo["schema"], oas)', '        pass', "mediaref"),
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


# ─────────────── 第五輪（Work #7161452041）MF2／MF3 ───────────────
# MF2：監督者行程不對子行程產出做 json／pickle／可替換函式反序列化
def _hold_gil(seconds):
    import ctypes

    sleep = ctypes.PyDLL(None).sleep  # PyDLL：呼叫期間持有 GIL

    def _f(*a, **k):
        sleep(seconds)
        raise AssertionError("supervisor must not reach this hook")

    return _f


def _real_spawn_run(worker, wall, hooks):
    import multiprocessing as mp

    ctx = mp.get_context("spawn")
    beat = ctx.Value("d", 0.0)
    t_epoch, t0 = time.time(), time.monotonic()
    out, err = None, None
    try:
        out = m.run_in_worker(ent_ok, (beat,), wall=wall, reap=2.0, ctx=ctx, worker=worker)
    except m.FetchStop as e:
        err = e.reason
    ret = time.monotonic() - t0
    return out, err, ret, beat.value - t_epoch, mp


@pytest.fixture
def _gil_holding_hooks(monkeypatch):
    """把監督者行程裡所有『可替換的反序列化／解碼入口』換成持有 GIL 3 秒的呼叫（Work 的 pickle 探針＋json 探針）。"""
    import multiprocessing.connection as mc

    hold = _hold_gil(3)
    monkeypatch.setattr(mc._ForkingPickler, "loads", staticmethod(hold))
    monkeypatch.setattr(m.json, "loads", hold)
    monkeypatch.setattr(m.json, "load", hold)


def test_mf2_success_path_is_not_delayed_by_gil_holding_deserializers(_gil_holding_hooks):
    out, err, ret, last_beat, mp = _real_spawn_run(w_frame_then_beat, 20.0, None)
    assert err is None and out == {"a": 1}
    assert ret < 2.5, f"監督者回傳 {ret:.2f}s（若走了被替換的 pickle／json 會 ≥3s）"
    assert 0 < last_beat <= ret + 0.2, "worker 停止時間不得晚於監督者回傳"
    assert not mp.active_children()


def test_mf2_timeout_path_returns_at_wall_clock_and_worker_stops_with_it(_gil_holding_hooks):
    def w_silent(conn, entry, args):  # 啟動後完全不送資料（模擬卡住的 worker）
        (beat,) = args
        while True:
            beat.value = time.time()
            time.sleep(0.005)

    out, err, ret, last_beat, mp = _real_spawn_run(w_silent_beat, 3.0, None)
    assert err == "wall_clock_timeout" and out is None
    assert 2.9 <= ret <= 3.0 + 1.0, f"監督者回傳 {ret:.2f}s（牆鐘 3s）"
    assert 0 < last_beat <= ret + 0.1, f"worker 最後心跳 {last_beat:.2f}s／回傳 {ret:.2f}s"
    assert not mp.active_children()


def w_silent_beat(conn, entry, args):
    (beat,) = args
    while True:
        beat.value = time.time()
        time.sleep(0.005)


def test_mf2_run_in_worker_source_has_no_json_pickle_or_recv_calls():
    import inspect

    src = inspect.getsource(m.run_in_worker)
    body = src.split('"""', 2)[2]  # 去掉 docstring
    for needle in ("json", "pickle", ".recv(", "loads", "_decode", "literal_eval"):
        assert needle not in body, needle
    assert "recv_bytes" in body
    import ast as _ast

    tree = _ast.parse(SRC.read_text(encoding="utf-8"))
    imported = {a.name.split(".")[0] for n in _ast.walk(tree) if isinstance(n, _ast.Import) for a in n.names}
    assert "pickle" not in imported and "marshal" not in imported and "shelve" not in imported


def test_mf2_tlv_roundtrip_and_encoder_limits():
    for obj in (None, True, False, 0, -5, 2**40, "", "中文 ABC", [], [1, [2, [3]]], {}, {"a": {"b": [1, "x", None]}},
                {"rows": [{"k": "v"}] * 3, "n": 7, "ok": True}):
        got = m.run_in_worker(ent_ok, (1,), wall=5.0, reap=0.05, ctx=_ctx(_Conn(payload=b"R" + m._tlv_encode(obj)), _Proc()))
        assert got == obj and type(got) is type(obj)
    for bad in (1.5, (1, 2), {1: "x"}, {"a": object()}, b"bytes", {"a": 2**70}):
        with pytest.raises((ValueError, OverflowError)):
            m._tlv_encode(bad)
    deep = 1
    for _ in range(12):
        deep = [deep]
    with pytest.raises(ValueError):
        m._tlv_encode(deep)


@pytest.mark.parametrize("payload,why", [
    (b"R", "空"), (b"RI\\x00", "整數被截斷"), (b"RS\\x00\\x00\\x00\\x05ab", "字串長度超出"),
    (b"RN" + b"N", "尾端多餘位元組"), (b"RX", "未知標籤"), (b"RL\\xff\\xff\\xff\\xffN", "元素數不可能"),
    (b"RS\\x00\\x00\\x00\\x02\\xff\\xfe", "非法 UTF-8"), (b"RD\\x00\\x00\\x00\\x01I" + b"\\x00" * 8 + b"N", "字典 key 非字串"),
    (b"R" + b"L\\x00\\x00\\x00\\x01" * 12 + b"N", "巢狀過深"), (b"RL\\x00\\x00\\x00\\x02N", "清單元素不足"),
])
def test_mf2_malformed_tlv_is_ipc_bad_payload_without_exception_leak(payload, why):
    payload = payload.replace(b"\\\\x", b"\\x") if b"\\\\x" in payload else payload
    with pytest.raises(m.FetchStop) as e:
        m.run_in_worker(ent_ok, (1,), wall=5.0, reap=0.05, ctx=_ctx(_Conn(payload=payload), _Proc()))
    assert e.value.reason == "ipc_bad_payload", why


def test_mf2_fixed_codes_for_worker_tags_remain():
    for payload, reason in ((b"Soversize", "oversize"), (b"Sbad reason!", "step_error"), (b"Zxx", "step_error"),
                            (b"E", "step_error")):
        with pytest.raises(m.FetchStop) as e:
            m.run_in_worker(ent_ok, (1,), wall=5.0, reap=0.05, ctx=_ctx(_Conn(payload=payload), _Proc()))
        assert e.value.reason == reason


def test_mf2_late_result_is_refused_with_real_clock_boundary(monkeypatch):
    calls = {"n": 0}
    real = time.monotonic

    def fake():
        calls["n"] += 1
        return 0.0 if calls["n"] <= 2 else 100.0

    monkeypatch.setattr(time, "monotonic", fake)
    try:
        with pytest.raises(m.FetchStop) as e:
            m.run_in_worker(ent_ok, (1,), wall=5.0, reap=0.05, ctx=_ctx(_Conn(), _Proc()))
    finally:
        monkeypatch.setattr(time, "monotonic", real)
    assert e.value.reason == "wall_clock_timeout"


def test_mf2_real_spawn_fast_path_and_error_codes_without_residual():
    import multiprocessing as mp

    assert m.run_in_worker(ent_ok, (7,), wall=20) == {"a": 7}
    with pytest.raises(m.FetchStop) as e:
        m.run_in_worker(ent_ok, (1,), wall=20, worker=w_garbage)
    assert e.value.reason == "ipc_bad_payload"
    assert not mp.active_children()


# MF3：解析終點必須是合法 Schema Object
_SCHEMA_ENDPOINTS = {
    "str": "nonschema", "list": ["nonschema"], "int": 5, "none": None, "bool": True,
    "badtype": {"type": "nope"}, "badtype_list": {"type": ["string"]}, "arr_no_items": {"type": "array"},
    "unknown": {"type": "string", "bogusKeyword": 1}, "minlen_str": {"type": "string", "minLength": "3"},
    "minlen_neg": {"type": "string", "minLength": -1}, "minlen_bool": {"type": "string", "minLength": True},
    "enum_empty": {"type": "string", "enum": []}, "enum_str": {"type": "string", "enum": "a"},
    "required_empty": {"type": "object", "required": []}, "required_nonstr": {"type": "object", "required": [1]},
    "props_list": {"type": "object", "properties": ["a"]}, "props_bad_child": {"type": "object", "properties": {"a": "x"}},
    "items_str": {"type": "array", "items": "x"}, "items_list": {"type": "array", "items": []},
    "oneof_empty": {"oneOf": []}, "oneof_nonlist": {"oneOf": {"type": "string"}}, "oneof_bad": {"oneOf": ["x"]},
    "not_bad": {"not": "x"}, "addl_str": {"type": "object", "additionalProperties": "yes"},
    "nullable_str": {"type": "string", "nullable": "true"}, "format_int": {"type": "string", "format": 5},
    "pattern_int": {"type": "string", "pattern": 5}, "desc_list": {"type": "string", "description": []},
    "numeric_str": {"type": "number", "maximum": "9"}, "numeric_bool": {"type": "number", "minimum": True},
    "ref_to_str": {"$ref": "#/components/schemas/str"}, "ref_ext": {"$ref": "https://evil.example/s.json"},
    "ref_nonstr": {"$ref": 5},
}


def _params_with_schema_endpoint(kind, where, level):
    comps = {n: v for n, v in _SCHEMA_ENDPOINTS.items()}
    comps["str"] = "nonschema"
    ref = {"$ref": "#/components/schemas/" + kind}
    if where == "param":
        plist = [_p(schema=ref)]
    else:
        plist = [_p(content={"application/json": {"schema": ref}})]
    oas = _with_params(plist, level)
    oas["components"] = {"schemas": comps}
    return oas


@pytest.mark.parametrize("level", ["op", "item"])
@pytest.mark.parametrize("where", ["param", "media"])
@pytest.mark.parametrize("kind", ["str", "list", "int", "none", "bool", "badtype", "badtype_list", "arr_no_items",
                                  "unknown", "minlen_str", "minlen_neg", "minlen_bool", "enum_empty", "enum_str",
                                  "required_empty", "required_nonstr", "props_list", "props_bad_child", "items_str",
                                  "items_list", "oneof_empty", "oneof_nonlist", "oneof_bad", "not_bad", "addl_str",
                                  "nullable_str", "format_int", "pattern_int", "desc_list", "numeric_str",
                                  "numeric_bool", "ref_to_str"])
def test_mf3_ref_endpoint_must_be_a_valid_schema_object(kind, where, level):
    tp = FakeTransport(_params_with_schema_endpoint(kind, where, level), _rows())
    res = _run(tp)
    assert res.stop_reason in ("schema_not_object", "schema_invalid", "schema_unknown_keyword", "external_ref",
                               "ref_unresolved"), (kind, res.stop_reason)
    assert len(tp.calls) == 1 and res.requests_used == 1


@pytest.mark.parametrize("level", ["op", "item"])
@pytest.mark.parametrize("where", ["param", "media"])
@pytest.mark.parametrize("schema", [
    "nonschema", ["nonschema"], 5, None, True, {"type": "nope"}, {"type": "array"}, {"type": "string", "minLength": "3"},
    {"oneOf": []}, {"properties": {"a": "x"}, "type": "object"}, {"$ref": "https://evil.example/s.json"},
    {"$ref": "#/components/schemas/Absent"}, {"bogus": 1},
])
def test_mf3_inline_schema_must_be_a_valid_schema_object_too(schema, where, level):
    plist = [_p(schema=schema)] if where == "param" else [_p(content={"application/json": {"schema": schema}})]
    tp = FakeTransport(_with_params(plist, level), _rows())
    res = _run(tp)
    assert res.stop_reason in ("op_params_invalid", "schema_not_object", "schema_invalid", "schema_unknown_keyword",
                               "external_ref", "ref_unresolved"), (schema, res.stop_reason)
    assert len(tp.calls) == 1 and res.requests_used == 1


@pytest.mark.parametrize("schema", [
    {"type": "string"}, {"type": "integer", "minimum": 0, "maximum": 10, "nullable": True},
    {"type": "array", "items": {"type": "string", "enum": ["a", "b"]}, "minItems": 1, "uniqueItems": True},
    {"type": "object", "required": ["a"], "properties": {"a": {"type": "string", "pattern": "^x$"}},
     "additionalProperties": False},
    {"oneOf": [{"type": "string"}, {"type": "integer"}], "x-vendor": {"anything": 1}},
    {"allOf": [{"$ref": "#/components/schemas/Ok"}], "description": "d"}, {"not": {"type": "boolean"}},
    {"type": "object", "additionalProperties": {"type": "string"}}, {"$ref": "#/components/schemas/Cyc"},
])
def test_mf3_valid_schema_objects_are_still_accepted(schema):
    for level in ("op", "item"):
        for where in ("param", "media"):
            plist = [_p(schema=schema)] if where == "param" else [_p(content={"application/json": {"schema": schema}})]
            oas = _with_params(plist, level)
            oas["components"] = {"schemas": {"Ok": {"type": "string"}, "Cyc": {
                "type": "object", "properties": {"a": {"$ref": "#/components/schemas/Cyc"}}}}}
            tp = FakeTransport(oas, _rows())
            assert _run(tp).stop_reason is None and len(tp.calls) == 2, (schema, where, level)


def test_mf3_schema_validator_budget_and_cycle_safety():
    comps = {f"S{i}": {"type": "object", "properties": {"n": {"$ref": f"#/components/schemas/S{i + 1}"}}}
             for i in range(40)}
    comps["S40"] = {"type": "string"}
    oas = _with_params([_p(schema={"$ref": "#/components/schemas/S0"})])
    oas["components"] = {"schemas": comps}
    assert _run(FakeTransport(oas, _rows())).stop_reason == "schema_too_complex"  # 深度上限
    big = {"type": "object", "properties": {f"p{i}": {"type": "string"} for i in range(700)}}
    oas2 = _with_params([_p(schema=big)])
    assert _run(FakeTransport(oas2, _rows())).stop_reason == "schema_too_complex"  # 節點數上限


@pytest.mark.parametrize("old,new,probe", [
    ('    if not isinstance(node, dict):\n        raise FetchStop("schema_not_object")\n', '    if not isinstance(node, dict):\n        return\n', "notobject"),
    ('    if any(not isinstance(k, str) or (k not in _SCHEMA_KEYS and not k.startswith("x-")) for k in node):\n        raise FetchStop("schema_unknown_keyword")\n', '', "unknownkey"),
    ('    if "type" in node and (not isinstance(t, str) or t not in _SCHEMA_TYPES):\n        raise FetchStop("schema_invalid")\n', '', "typeset"),
    ('    if t == "array" and "items" not in node:\n        raise FetchStop("schema_invalid")\n', '', "items"),
])
def test_round5_schema_mutations_are_killed(old, new, probe):
    ns = _mutant(old, new)
    bad = {"notobject": "nonschema", "unknownkey": {"type": "string", "bogus": 1}, "typeset": {"type": "nope"},
           "items": {"type": "array"}}[probe]
    oas = (_params_with_schema_endpoint("str", "param", "op") if probe == "notobject"
           else _with_params([_p(schema=bad)]))
    res = _mrun(ns, FakeTransport(oas, _rows()))
    assert res.stop_reason is None  # 守衛被拿掉 ⇒ 非法 Schema Object 也放行（R-1 被送出）


# ─────────────── 第六輪（Work #7161727036）MF3：Schema Object 關鍵字「值」的合法性 ───────────────
_BAD_KEYWORD_VALUES = {
    # Work 具名反例
    "exclusiveMaximum_str_false": {"type": "number", "maximum": 5, "exclusiveMaximum": "false"},
    "multipleOf_zero": {"type": "number", "multipleOf": 0},
    "xml_int": {"type": "string", "xml": 9},
    # 同類延伸
    "exclusiveMinimum_str": {"type": "number", "minimum": 1, "exclusiveMinimum": "true"},
    "exclusiveMaximum_number_3_1_style": {"type": "number", "exclusiveMaximum": 5},
    "exclusiveMinimum_none": {"type": "number", "exclusiveMinimum": None},
    "exclusiveMaximum_list": {"type": "number", "exclusiveMaximum": [True]},
    "multipleOf_neg": {"type": "number", "multipleOf": -1}, "multipleOf_str": {"type": "number", "multipleOf": "2"},
    "multipleOf_bool": {"type": "number", "multipleOf": True}, "multipleOf_float_zero": {"type": "number", "multipleOf": 0.0},
    "multipleOf_none": {"type": "number", "multipleOf": None},
    "maximum_str": {"type": "number", "maximum": "9"}, "maximum_nan": {"type": "number", "maximum": float("nan")},
    "maximum_inf": {"type": "number", "maximum": float("inf")},
    "xml_str": {"type": "string", "xml": "x"}, "xml_list": {"type": "string", "xml": ["a"]},
    "xml_none": {"type": "string", "xml": None}, "xml_name_int": {"type": "string", "xml": {"name": 5}},
    "xml_attr_str": {"type": "string", "xml": {"attribute": "yes"}}, "xml_wrapped_int": {"type": "string", "xml": {"wrapped": 1}},
    "xml_unknown": {"type": "string", "xml": {"bogus": "x"}},
    "extdocs_str": {"type": "string", "externalDocs": "x"}, "extdocs_no_url": {"type": "string", "externalDocs": {"description": "d"}},
    "extdocs_url_int": {"type": "string", "externalDocs": {"url": 5}}, "extdocs_unknown": {"type": "string", "externalDocs": {"url": "u", "bogus": 1}},
    "extdocs_desc_int": {"type": "string", "externalDocs": {"url": "u", "description": 5}},
    "disc_str": {"oneOf": [{"type": "string"}], "discriminator": "x"},
    "disc_no_prop": {"oneOf": [{"type": "string"}], "discriminator": {}},
    "disc_prop_int": {"oneOf": [{"type": "string"}], "discriminator": {"propertyName": 5}},
    "disc_mapping_list": {"oneOf": [{"type": "string"}], "discriminator": {"propertyName": "t", "mapping": ["a"]}},
    "disc_mapping_val_int": {"oneOf": [{"type": "string"}], "discriminator": {"propertyName": "t", "mapping": {"a": 1}}},
    "disc_unknown": {"oneOf": [{"type": "string"}], "discriminator": {"propertyName": "t", "bogus": 1}},
}


@pytest.mark.parametrize("level", ["op", "item"])
@pytest.mark.parametrize("where", ["param", "media"])
@pytest.mark.parametrize("kind", sorted(_BAD_KEYWORD_VALUES))
def test_mf3_round6_invalid_schema_keyword_values_mean_zero_r1(kind, where, level):
    schema = _BAD_KEYWORD_VALUES[kind]
    plist = [_p(schema=schema)] if where == "param" else [_p(content={"application/json": {"schema": schema}})]
    tp = FakeTransport(_with_params(plist, level), _rows())
    res = _run(tp)
    assert res.stop_reason == "schema_invalid" and len(tp.calls) == 1 and res.requests_used == 1, (kind, res.stop_reason)


def test_mf3_round6_work_named_twelve_cases_exactly():
    named = ("exclusiveMaximum_str_false", "multipleOf_zero", "xml_int")
    n = 0
    for kind in named:
        for where in ("param", "media"):
            for level in ("op", "item"):
                schema = _BAD_KEYWORD_VALUES[kind]
                plist = [_p(schema=schema)] if where == "param" else [_p(content={"application/json": {"schema": schema}})]
                tp = FakeTransport(_with_params(plist, level), _rows())
                assert _run(tp).stop_reason == "schema_invalid" and len(tp.calls) == 1  # R-1 = 0
                n += 1
    assert n == 12


@pytest.mark.parametrize("schema", [
    {"type": "number", "maximum": 5, "exclusiveMaximum": True}, {"type": "number", "minimum": 1, "exclusiveMinimum": False},
    {"type": "number", "multipleOf": 0.5}, {"type": "integer", "multipleOf": 3, "minimum": -2.5, "maximum": 10},
    {"type": "string", "xml": {"name": "a", "namespace": "http://x", "prefix": "p", "attribute": True, "wrapped": False}},
    {"type": "string", "xml": {}, "x-flag": 1}, {"type": "string", "xml": {"x-vendor": 1}},
    {"type": "string", "externalDocs": {"url": "https://docs.example"}},
    {"type": "string", "externalDocs": {"url": "u", "description": "d", "x-v": 1}},
    {"oneOf": [{"type": "string"}, {"type": "integer"}], "discriminator": {"propertyName": "kind"}},
    {"oneOf": [{"type": "string"}], "discriminator": {"propertyName": "kind", "mapping": {"a": "#/x", "b": "y"}}},
])
def test_mf3_round6_valid_keyword_values_are_still_accepted(schema):
    for level in ("op", "item"):
        for where in ("param", "media"):
            plist = [_p(schema=schema)] if where == "param" else [_p(content={"application/json": {"schema": schema}})]
            tp = FakeTransport(_with_params(plist, level), _rows())
            assert _run(tp).stop_reason is None and len(tp.calls) == 2, (schema, where, level)


@pytest.mark.parametrize("old,new,probe", [
    ('    if "multipleOf" in node and not (_is_real(node["multipleOf"]) and node["multipleOf"] > 0):\n        raise FetchStop("schema_invalid")', '    pass', "multipleof"),
    ('        if not isinstance(x, dict) or any(', '        if False or any(', "xmlshape"),
    ('    for k in _SCHEMA_NUM:\n        if k in node and not _is_real(node[k]):\n            raise FetchStop("schema_invalid")\n', '', "numeric"),
    ('_SCHEMA_BOOL = ("nullable", "deprecated", "readOnly", "writeOnly", "uniqueItems", "exclusiveMaximum",\n                "exclusiveMinimum")', '_SCHEMA_BOOL = ("nullable", "deprecated", "readOnly", "writeOnly", "uniqueItems")', "exclusive"),
    ('    if "externalDocs" in node:', '    if False and "externalDocs" in node:', "extdocs"),
    ('    if "discriminator" in node:', '    if False and "discriminator" in node:', "disc"),
])
def test_round6_mutations_are_killed(old, new, probe):
    ns = _mutant(old, new)
    bad = {"multipleof": "multipleOf_zero", "xmlshape": "xml_int", "numeric": "maximum_str",
           "exclusive": "exclusiveMaximum_str_false", "extdocs": "extdocs_str", "disc": "disc_str"}[probe]
    try:
        res = _mrun(ns, FakeTransport(_with_params([_p(schema=_BAD_KEYWORD_VALUES[bad])]), _rows()))
    except AttributeError:
        return  # 守衛被拿掉 ⇒ 行為改變（崩潰）＝被殺
    assert res.stop_reason is None, probe  # 守衛被拿掉 ⇒ 非法關鍵字值被放行（R-1 被送出）＝被殺


def test_round6_does_not_touch_tlv_ipc_or_supervisor():
    import inspect

    src = inspect.getsource(m.run_in_worker)
    assert "recv_bytes" in src and "_unpack" in src and "json" not in src.split('"""', 2)[2]


# ═════════════ M2 來源側離線候選（CURRENT_PLAN r94；r97 核准 S1～S4）：test_mode 可信產生、fund_code、結構化顯名、display_handoff、逐次 nonce ═════════════
# 全部為記憶體內合成資料；不含真 ISIN／NAV／基金名稱／授權敏感值；實際真 payload 仍不可能（無 runner、LIVE_ENABLED=False）。
@pytest.fixture(autouse=True)
def _fresh_nonce_and_seal_registries():
    """模組級登記表（nonce／sealed）每個測試前清空：測試之間不互相消耗、不累積。"""
    m._NONCES.clear()
    m._SEALED.clear()
    yield
    m._NONCES.clear()
    m._SEALED.clear()


def _real(**kw):
    """非合成、有依據、有 R2 證據的權利（記憶體測試資料；證據的 run_id 預設 RUN，真實模式須以 `run=` 綁 nonce）。"""
    kw.setdefault("synthetic", False)
    return _rights(**kw)


_ORIG_ATTRIBUTION_BLOCK = m.attribution_block   # monkeypatch 換掉 m.attribution_block 之前先留住原函式（避免遞迴）


def _stated_attr():
    """測試用結構化顯名：年份／版本標為已載明（合成值，不是供應方原值）。"""
    a = _ORIG_ATTRIBUTION_BLOCK()
    a["release_year"] = {"value": "2099", "stated": True, "reason": "synthetic_test_value"}
    a["dataset_version"] = {"value": "v-synthetic", "stated": True, "reason": "synthetic_test_value"}
    return a


def _real_run(monkeypatch=None, *, stated=True, rows=None, rights=None, tp=None, rid=None, confirmed=True, **kw):
    """真實模式（test_mode=False）：先 `prepare_run()` 取 nonce，R2 證據綁該 nonce，再 `run()`（run_id＝nonce）。"""
    if stated:
        monkeypatch.setattr(m, "attribution_block", _stated_attr)
    rid = rid or m.prepare_run()
    rg = rights(rid) if callable(rights) else (rights if rights is not None else _real(run=rid))
    tp = tp if tp is not None else FakeTransport(_oas(), rows if rows is not None else _rows())
    return m.run(GOOD_ISIN, user_confirmed_non_holding=confirmed, transport=tp, rights=rg, test_mode=False, today=TODAY, now=NOW,
                 run_id=rid, **kw)


# ─── test_mode 可信產生 ───
def test_run_without_test_mode_is_unmarked_and_never_releases_a_payload():
    res = m.run(GOOD_ISIN, user_confirmed_non_holding=True, transport=FakeTransport(_oas(), _rows()), rights=_real(),
                today=TODAY, now=NOW, run_id=RUN)
    assert res.test_mode is None and res.stop_reason == "test_mode_unmarked" and res.withheld_reason == "test_mode_unmarked"
    assert res.local_display is None and res.value_released is False and res.isin_matched is True


@pytest.mark.parametrize("mode", ["false", "False", "true", 0, 1, "real", (), object()])
def test_non_boolean_test_mode_values_are_unmarked_not_real_and_never_accept_synthetic_rights(mode):
    res = _run(FakeTransport(_oas(), _rows()), rights=_real(), test_mode=mode)
    assert res.test_mode is None and res.stop_reason == "test_mode_unmarked" and res.local_display is None
    syn = _run(FakeTransport(_oas(), _rows()), rights=ALLOWED, test_mode=mode)    # 合成權利在非布林模式下不得被當成測試模式接受
    assert syn.test_mode is None and syn.stop_reason == "rights_unverified" and syn.local_display is None


def test_the_recorded_mode_is_exactly_what_the_caller_marked(monkeypatch):
    assert _run(FakeTransport(_oas(), _rows()), rights=ALLOWED, test_mode=True).test_mode is True
    assert _real_run(monkeypatch).test_mode is False
    assert m.Result().test_mode is None                                           # 預設是未標明，不是 False


# ─── S1：唯一顯示出口＝handoff；真實模式拒收時 Result 不暴露 NAV／基金名稱、不誤報 value_released ───
def test_s1_real_mode_refusal_exposes_no_nav_or_name_and_never_reports_value_released(monkeypatch):
    res = _real_run(stated=False)                                                 # 供應方未載年份／版本
    assert res.test_mode is False and res.stop_reason == "attribution_not_stated" and res.withheld_reason == "attribution_not_stated"
    assert res.value_released is False and res.local_display is None
    agg = res.aggregate()
    assert agg["value_released"] is False and agg["stop_reason"] == "attribution_not_stated"
    blob = json.dumps(agg, ensure_ascii=False)
    for secret in ("12.3456", "測試基金", "F001", GOOD_ISIN):
        assert secret not in blob, secret
    h = m.display_handoff(res)
    assert h["released"] is False and h["reason"] == "attribution_not_stated" and h["payload"] is None
    assert h["decisions"] == {"display": True, "derive": False, "ai": False}      # 權利仍是來源層算出的，原因另列


def test_s1_the_cli_prints_only_the_handoff_payload_never_the_raw_local_display(monkeypatch, capsys):
    class _R:  # 假 runner；run 被換掉，不會真的呼叫
        pass

    released = _real_run(monkeypatch)                                              # 先取得一個真的登記過的放行結果（之後才換掉 m.run）
    monkeypatch.setattr(m, "make_live_runner", lambda: _R())
    leaked = m.Result(value_released=True, local_display={"nav": "12.3456", "fund_name": "測試基金 A 類", "fund_code": "F001"})   # 手造、未登記
    monkeypatch.setattr(m, "run", lambda *a, **k: leaked)
    m.main(["--isin", GOOD_ISIN, "--confirm-non-holding"])
    out = capsys.readouterr().out
    assert "12.3456" not in out and "測試基金" not in out and "僅本機顯示" not in out
    monkeypatch.setattr(m, "run", lambda *a, **k: released)
    m.main(["--isin", GOOD_ISIN, "--confirm-non-holding"])
    out2 = capsys.readouterr().out
    assert "僅本機顯示" in out2 and "12.3456" in out2 and GOOD_ISIN not in out2.split("僅本機顯示")[1]


def test_handoff_releases_a_fixed_key_payload_with_structured_attribution_and_no_identity_or_consent_values(monkeypatch):
    res = _real_run(monkeypatch)
    assert res.value_released is True and res.local_display is not None and res.stop_reason is None
    h = m.display_handoff(res)
    assert h["released"] is True and h["reason"] is None and h["schema"] == m.HANDOFF_SCHEMA
    p = h["payload"]
    assert set(p) == {"fund_code", "nav", "currency", "nav_date", "fund_name", "source", "retrieved_at_utc", "attribution"}
    assert (p["fund_code"], p["nav"], p["currency"], p["nav_date"], p["retrieved_at_utc"]) == ("F001", "12.3456", "USD", "2026-11-23", "2026-11-24T03:00Z")
    blob = json.dumps(h, ensure_ascii=False)
    for secret in (GOOD_ISIN, "consent#1", "TEST-BASIS", RUN):                    # 不含 ISIN、consent_ref、basis_ref、run_id
        assert secret not in blob, secret
    assert p["attribution"]["release_year"] == {"value": "2099", "stated": True, "reason": "synthetic_test_value"}


def test_handoff_never_releases_a_test_mode_or_unmarked_result_even_with_stated_attribution(monkeypatch):
    monkeypatch.setattr(m, "attribution_block", _stated_attr)
    syn = _run(FakeTransport(_oas(), _rows()), rights=ALLOWED, test_mode=True)
    assert syn.value_released is True
    h = m.display_handoff(syn)
    assert h["released"] is False and h["reason"] == "test_mode_synthetic" and h["payload"] is None
    unmarked = _run(FakeTransport(_oas(), _rows()), rights=_real(), test_mode=None)
    assert m.display_handoff(unmarked)["reason"] == "test_mode_unmarked"
    for junk in (None, {}, "x", 1):
        assert m.display_handoff(junk)["reason"] == "not_a_result" and m.display_handoff(junk)["released"] is False


# ─── S2：handoff 只信本次 run() 內部登記的不可變內容；手造或事後改寫的 Result 一律無效 ───
def test_s2_a_hand_built_or_guessed_result_is_never_released():
    forged = m.Result(test_mode=False, value_released=True, rights={"R2": "ALLOWED", "R3": "ALLOWED", "R4": "ALLOWED"}, local_display={
        "fund_code": "F001", "nav": "12.3456", "currency": "USD", "nav_date": "2026-11-23", "fund_name": "測試基金 A 類",
        "source": "x", "fetched_at_utc": "2026-11-24T03:00Z", "attribution": _ORIG_ATTRIBUTION_BLOCK()})
    assert m.display_handoff(forged)["reason"] == "not_issued_by_run" and m.display_handoff(forged)["released"] is False
    forged.handle = "0" * 32                                                      # 猜一個 token
    assert m.display_handoff(forged)["reason"] == "not_issued_by_run"
    forged.handle = 12345                                                          # 非字串 token
    assert m.display_handoff(forged)["reason"] == "not_issued_by_run"


def test_s2_overwriting_a_withheld_result_afterwards_cannot_turn_it_into_a_release(monkeypatch):
    unproven = lambda rid: m.Rights("UNKNOWN", basis_ref="B", synthetic=False, r2_evidence=m.R2Evidence(rid, m.R2_PURPOSE, m.R2_SCOPE_FILE, "c"))  # noqa: E731
    res = _real_run(monkeypatch, rights=unproven)
    assert res.stop_reason == "rights_unverified" and m.display_handoff(res)["released"] is False
    res.rights["R2"] = "ALLOWED"                                                   # 事後自稱權利
    res.test_mode, res.value_released, res.stop_reason = False, True, None
    res.local_display = {"fund_code": "F001", "nav": "12.3456", "currency": "USD", "nav_date": "2026-11-23", "fund_name": "x",
                         "source": "x", "fetched_at_utc": "2026-11-24T03:00Z", "attribution": _stated_attr()}
    h = m.display_handoff(res)
    assert h["released"] is False and h["reason"] == "no_value_released" and h["payload"] is None


def test_s2_overwriting_a_released_result_afterwards_changes_nothing(monkeypatch):
    res = _real_run(monkeypatch)
    before = m.display_handoff(res)
    assert before["released"] is True
    res.local_display["nav"] = "999.9999"
    res.local_display["attribution"]["release_year"]["value"] = "1999"
    res.rights["R3"] = res.rights["R4"] = "ALLOWED"
    res.test_mode = True
    assert m.display_handoff(res) == before                                       # 內容來自登記時的不可變快照
    before["payload"]["nav"] = "1.0"                                              # 回傳值是副本：改它不影響下一次
    assert m.display_handoff(res)["payload"]["nav"] == "12.3456"


def test_s2_flipping_a_synthetic_result_to_real_afterwards_stays_refused(monkeypatch):
    monkeypatch.setattr(m, "attribution_block", _stated_attr)
    syn = _run(FakeTransport(_oas(), _rows()), rights=ALLOWED, test_mode=True)
    syn.test_mode = False
    assert m.display_handoff(syn)["reason"] == "test_mode_synthetic"


# ─── S3：真實模式只接受 prepare_run() 發出、尚未消耗的 nonce ───
def test_s3_a_caller_chosen_run_id_is_refused_before_any_request_even_with_matching_evidence():
    tp = FakeTransport(_oas(), _rows())
    res = m.run(GOOD_ISIN, user_confirmed_non_holding=True, transport=tp, rights=_real(), test_mode=False, today=TODAY, now=NOW, run_id=RUN)
    assert res.stop_reason == "run_id_not_issued" and res.requests_used == 0 and tp.calls == [] and res.local_display is None
    for junk in (None, 123, ["x"], "", "0" * 32):
        r = m.run(GOOD_ISIN, user_confirmed_non_holding=True, transport=FakeTransport(_oas(), _rows()), rights=_real(), test_mode=False,
                  today=TODAY, now=NOW, run_id=junk)
        assert r.stop_reason == "run_id_not_issued" and r.requests_used == 0, junk


def test_s3_a_nonce_is_single_use_replay_is_refused_without_any_request(monkeypatch):
    rid = m.prepare_run()
    first = _real_run(monkeypatch, rid=rid)
    assert first.value_released is True
    tp = FakeTransport(_oas(), _rows())
    again = _real_run(monkeypatch, rid=rid, tp=tp)
    assert again.stop_reason == "run_id_consumed" and again.requests_used == 0 and tp.calls == [] and again.local_display is None


def test_s3_a_nonce_is_consumed_even_when_the_first_run_failed(monkeypatch):
    rid = m.prepare_run()
    failed = _real_run(monkeypatch, rid=rid, confirmed=False)                    # 第一次失敗：使用者確認缺失
    assert failed.stop_reason == "user_confirmation_missing"
    tp = FakeTransport(_oas(), _rows())
    retry = _real_run(monkeypatch, rid=rid, tp=tp)
    assert retry.stop_reason == "run_id_consumed" and tp.calls == []
    rid2 = m.prepare_run()
    net = _real_run(monkeypatch, rid=rid2, tp=FakeTransport(_oas(), _rows(), status0=500))   # 傳輸失敗也消耗
    assert net.stop_reason is not None and net.requests_used >= 1
    assert _real_run(monkeypatch, rid=rid2).stop_reason == "run_id_consumed"


def test_s3_evidence_bound_to_another_nonce_is_a_mismatch_and_does_not_burn_the_other_nonce(monkeypatch):
    a, b = m.prepare_run(), m.prepare_run()
    res = _real_run(monkeypatch, rid=a, rights=_real(run=b))                      # 同意綁的是 b，執行的是 a
    assert res.stop_reason == "rights_unverified" and res.local_display is None
    assert m._NONCES[a] == "consumed" and m._NONCES[b] == "issued"
    assert _real_run(monkeypatch, rid=b).value_released is True                   # b 仍可用一次


def test_s3_concurrent_use_of_one_nonce_lets_exactly_one_run_proceed(monkeypatch):
    import threading

    monkeypatch.setattr(m, "attribution_block", _stated_attr)
    rid = m.prepare_run()
    out: list = []
    barrier = threading.Barrier(8)

    def go():
        barrier.wait()
        out.append(m.run(GOOD_ISIN, user_confirmed_non_holding=True, transport=FakeTransport(_oas(), _rows()), rights=_real(run=rid),
                         test_mode=False, today=TODAY, now=NOW, run_id=rid))

    ts = [threading.Thread(target=go) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(out) == 8 and sum(1 for r in out if r.stop_reason != "run_id_consumed") == 1


def test_s3_test_mode_keeps_caller_chosen_run_ids_reusable_but_never_releases():
    for _ in range(2):
        r = _run(FakeTransport(_oas(), _rows()), rights=ALLOWED, test_mode=True)
        assert r.value_released is True and m.display_handoff(r)["released"] is False


def test_s3_prepare_run_issues_unique_unguessable_nonces_and_caps_outstanding_ones():
    ns = {m.prepare_run() for _ in range(m._NONCE_MAX_OUTSTANDING)}
    assert len(ns) == m._NONCE_MAX_OUTSTANDING and all(len(n) == 32 and int(n, 16) >= 0 for n in ns)
    with pytest.raises(m.FetchStop) as e:
        m.prepare_run()
    assert e.value.reason == "too_many_prepared_runs"


# ─── 權利不成立 ───
@pytest.mark.parametrize("variant", [
    lambda rid: m.Rights("UNKNOWN", basis_ref="B", synthetic=False, r2_evidence=m.R2Evidence(rid, m.R2_PURPOSE, m.R2_SCOPE_FILE, "c")),
    lambda rid: m.Rights("DENY", basis_ref="B", synthetic=False, r2_evidence=m.R2Evidence(rid, m.R2_PURPOSE, m.R2_SCOPE_FILE, "c")),
    lambda rid: m.Rights("ALLOWED", basis_ref="  ", synthetic=False, r2_evidence=m.R2Evidence(rid, m.R2_PURPOSE, m.R2_SCOPE_FILE, "c")),
    lambda rid: m.Rights("ALLOWED", basis_ref="B", synthetic=False, r2_evidence=None),
    lambda rid: m.Rights("ALLOWED", basis_ref="B", synthetic=False, r2_evidence=m.R2Evidence("other-run", m.R2_PURPOSE, m.R2_SCOPE_FILE, "c")),
    lambda rid: m.Rights("ALLOWED", basis_ref="B", synthetic=False, r2_evidence=m.R2Evidence(rid, "not_display", m.R2_SCOPE_FILE, "c")),
    lambda rid: m.Rights("ALLOWED", basis_ref="B", synthetic=False, r2_evidence=m.R2Evidence(rid, m.R2_PURPOSE, "scripts/other.py", "c")),
    lambda rid: m.Rights("ALLOWED", basis_ref="B", synthetic=False, r2_evidence=m.R2Evidence(rid, m.R2_PURPOSE, m.R2_SCOPE_FILE, " ")),
])
def test_unproven_r2_never_yields_a_real_payload_or_a_handoff(variant, monkeypatch):
    res = _real_run(monkeypatch, rights=variant)
    assert res.stop_reason == "rights_unverified" and res.local_display is None and res.value_released is False
    h = m.display_handoff(res)
    assert h["released"] is False and h["reason"] == "no_value_released" and h["payload"] is None
    assert h["decisions"]["display"] is False and h["decisions"]["derive"] is False and h["decisions"]["ai"] is False


@pytest.mark.parametrize("r3,r4,derive,ai", [("UNKNOWN", "UNKNOWN", False, False), ("ALLOWED", "UNKNOWN", True, False),
                                             ("UNKNOWN", "ALLOWED", False, False), ("ALLOWED", "ALLOWED", True, True)])
def test_handoff_decisions_come_from_the_source_layer_and_r3_r4_are_never_derived_from_r2(r3, r4, derive, ai, monkeypatch):
    res = _real_run(monkeypatch, rights=lambda rid: _real(run=rid, r3=r3, r4=r4))
    h = m.display_handoff(res)
    assert h["released"] is True and h["decisions"] == {"display": True, "derive": derive, "ai": ai}


# ─── 顯示閘（純函式）：顯名／時間／代碼 ───
def _gate_inputs():
    rights = {"R2": "ALLOWED", "R3": "UNKNOWN", "R4": "UNKNOWN"}
    ld = {"fund_code": "F001", "nav": "12.3456", "currency": "USD", "nav_date": "2026-11-23", "fund_name": "測試基金 A 類",
          "source": "TDCC OpenAPI／data.gov.tw 11641", "fetched_at_utc": "2026-11-24T03:00Z", "attribution": _stated_attr()}
    return rights, ld


def test_the_release_gate_positive_control_and_rights_failures():
    rights, ld = _gate_inputs()
    reason, payload = m._release_gate(rights, ld)
    assert reason is None and payload["fund_code"] == "F001" and set(payload) == {
        "fund_code", "nav", "currency", "nav_date", "fund_name", "source", "retrieved_at_utc", "attribution"}
    assert m._release_gate({**rights, "R2": "UNKNOWN"}, ld) == ("rights_unverified", None)
    assert m._release_gate({"R3": "ALLOWED", "R4": "ALLOWED"}, ld) == ("rights_unverified", None)    # R3／R4 不能代替 R2
    assert m._release_gate(None, ld) == ("no_value_released", None) and m._release_gate(rights, None) == ("no_value_released", None)
    assert m._release_gate(rights, dict(ld, fetched_at_utc="2026-11-24")) == ("retrieved_at_invalid", None)
    assert m._release_gate(rights, dict(ld, nav=" ")) == ("payload_incomplete", None)


@pytest.mark.parametrize("edit,reason", [
    (lambda a: a.__setitem__("release_year", {"value": None, "stated": True, "reason": "x"}), "attribution_malformed"),          # 虛假 stated：宣稱已載明卻沒有值
    (lambda a: a.__setitem__("release_year", {"value": "2099", "stated": "yes", "reason": "x"}), "attribution_malformed"),       # stated 不是布林
    (lambda a: a.__setitem__("release_year", {"value": "2099", "stated": False, "reason": "x"}), "attribution_malformed"),       # stated=False 卻帶值
    (lambda a: a.__setitem__("release_year", {"value": "未載明（本次未取得）", "stated": True, "reason": "x"}), "attribution_malformed"),
    (lambda a: a.__setitem__("release_year", {"value": "N/A", "stated": True, "reason": "x"}), "attribution_malformed"),
    (lambda a: a.__setitem__("release_year", {"value": "26", "stated": True, "reason": "x"}), "attribution_malformed"),           # 不是年份
    (lambda a: a.__setitem__("release_year", "2099"), "attribution_malformed"),                                                  # 舊式字串形狀
    (lambda a: a.pop("release_year"), "attribution_malformed"),
    (lambda a: a.__setitem__("dataset_version", {"value": None, "stated": False, "reason": "not_stated_by_supplier"}), "attribution_not_stated"),
    (lambda a: a.__setitem__("release_year", {"value": None, "stated": False, "reason": "not_stated_by_supplier"}), "attribution_not_stated"),
    (lambda a: a.__setitem__("metadata_updated_on", {"value": "2099", "stated": True, "reason": "x"}), "attribution_substituted"),   # 詮釋資料更新日冒充年份
    (lambda a: a.__setitem__("metadata_updated_on", {"value": "v-synthetic", "stated": True, "reason": "x"}), "attribution_substituted"),  # 冒充版本
    (lambda a: a.__setitem__("license_url", "https://evil.example/license"), "attribution_malformed"),
    (lambda a: a.__setitem__("agency", "  "), "attribution_malformed"),
    (lambda a: a.__setitem__("dataset", "未載明"), "attribution_malformed"),
])
def test_the_release_gate_refuses_false_missing_or_substituted_attribution(edit, reason):
    rights, ld = _gate_inputs()
    edit(ld["attribution"])
    assert m._release_gate(rights, ld) == (reason, None)
    rights2, ld2 = _gate_inputs()
    ld2["attribution"] = ["not", "a", "dict"]
    assert m._release_gate(rights2, ld2) == ("attribution_malformed", None)


def test_attribution_block_is_structured_never_fabricates_and_does_not_add_unapproved_fields():
    a = m.attribution_block()
    for k in m.STRUCTURED_ATTRIBUTION_FIELDS:
        assert set(a[k]) == {"value", "stated", "reason"} and a[k]["value"] is None and a[k]["stated"] is False, k   # 現缺者 stated=False、不捏造值
    assert a["metadata_updated_on"]["reason"] == "conflict_pending_review"
    assert "disclaimer" not in a and "modification_notice" not in a                                                    # N3：最終必備集合未生效前不補造
    assert a["license_url"] == m.OGDL_LICENSE_URL and "未載明" not in json.dumps(a, ensure_ascii=False)


# ─── S4：代碼文法與 UI 同一個樣式；fund_code 只取一對一核證者，不以 ISIN 代替 ───
_UI_SRC = _ROOT / "ui_v3" / "adapters" / "fund_lookup.py"


def test_s4_the_code_pattern_is_byte_identical_to_the_ui_pattern_and_the_ui_still_normalizes_the_same_way():
    import re as _re

    src = _UI_SRC.read_text(encoding="utf-8")
    found = _re.search(r'^L2_PURE_CODE_PATTERN = r"(.+)"$', src, _re.M)
    assert found and found.group(1) == m.UI_PURE_CODE_PATTERN
    assert 'fullmatch(raw.strip(" ").upper())' in src                             # UI 先去 ASCII 空格再轉大寫；本層同樣正規化


_COMPAT = ["F001", "T4521", "0001", "ABC", "ABC-12", "A" * 30, "f001", " f001 "]
_INCOMPAT = ["A1.B", "ab_c", "AB", "a1", "A" * 31, "AB CD", "a/b", "-x", "ABC-1", "ABC--12", "ABC-", "測試01", ""]


@pytest.mark.parametrize("code", _COMPAT + _INCOMPAT)
def test_s4_handoff_accepts_exactly_the_codes_the_ui_accepts_and_emits_the_normalized_code(code, monkeypatch):
    import re as _re

    ui = _re.compile(_re.search(r'^L2_PURE_CODE_PATTERN = r"(.+)"$', _UI_SRC.read_text(encoding="utf-8"), _re.M).group(1))
    ui_ok = ui.fullmatch(code.strip(" ").upper()) is not None
    res = _real_run(monkeypatch, rows=_rows(**{m.KEY_CODE: code}))
    h = m.display_handoff(res)
    if code.strip():                                                               # 空白代碼在更上游就停（class_unverified）
        assert h["released"] is ui_ok, (code, h["reason"])
    if ui_ok:
        assert h["payload"]["fund_code"] == code.strip(" ").upper()
        assert res.value_released is True
    else:
        assert h["payload"] is None and res.local_display is None and res.value_released is False   # S1：拒收不暴露


def test_fund_code_is_only_the_verified_one_to_one_code_never_an_isin_substitute(monkeypatch):
    res = _real_run(monkeypatch)
    assert res.local_display["fund_code"] == "F001" and res.checks.pairing_unambiguous is True
    amb = _real_run(monkeypatch, rows=[_row(), _row(**{m.KEY_ISIN: "ZZ0000000008"})])                  # 同一代碼對到兩個 ISIN ⇒ 配對不唯一
    assert amb.stop_reason == "pairing_ambiguous" and amb.local_display is None and m.display_handoff(amb)["reason"] == "no_value_released"
    as_isin = _real_run(monkeypatch, rows=_rows(**{m.KEY_CODE: GOOD_ISIN}))                            # 代碼欄位內容就是 ISIN ⇒ 不當成代碼
    assert as_isin.stop_reason == "no_paired_code" and as_isin.local_display is None and m.display_handoff(as_isin)["reason"] == "no_paired_code"
    other = _real_run(monkeypatch, rows=_rows(**{m.KEY_CODE: "ZZ0000000008"}))                         # 另一個合法 ISIN 形的代碼 ⇒ 也拒
    assert other.stop_reason == "no_paired_code" and m.display_handoff(other)["reason"] == "no_paired_code"
    syn = _run(FakeTransport(_oas(), _rows(**{m.KEY_CODE: GOOD_ISIN})), rights=ALLOWED, test_mode=True)   # 合成模式：代碼＝ISIN 時 fund_code 仍為 None
    assert syn.local_display["fund_code"] is None


def test_aggregate_stays_clean_and_unchanged_by_the_new_fields(monkeypatch):
    res = _real_run(monkeypatch)
    agg = res.aggregate()
    assert set(agg) == {"schema", "requests_used", "requests_max", "r0", "binding", "oas_version", "class_doc_evidence", "r1", "stop_reason",
                        "rows_seen", "n_selected_rows", "distinct_dates", "checks", "isin_matched", "value_released", "withheld_reason",
                        "rights", "use_decisions", "formulas_called", "long_term_metrics", "persistence"}
    blob = json.dumps(agg, ensure_ascii=False)
    for secret in (GOOD_ISIN, "12.3456", "測試基金", "F001", "consent#1", "TEST-BASIS", "https://", res.handle):
        assert secret not in blob, secret
    assert agg["persistence"] == "none" and agg["formulas_called"] == 0 and agg["requests_used"] == 2


def test_new_guards_do_not_rely_on_assert_and_the_handoff_is_pure():
    import ast as _ast

    tree = _ast.parse(SRC.read_text(encoding="utf-8"))
    fns = {n.name: n for n in _ast.walk(tree) if isinstance(n, _ast.FunctionDef)}
    for name in ("run", "display_handoff", "_attribution_problem", "_handoff_refuse", "_release_gate", "attribution_block", "prepare_run",
                 "_consume_nonce", "_seal"):
        assert not any(isinstance(x, _ast.Assert) for x in _ast.walk(fns[name])), name       # -O 會移除 assert：新守衛一律用明確條件
    banned = {"open", "print", "socket", "urlopen", "getenv", "environ", "write_text", "write_bytes", "eval", "exec", "system", "popen"}
    for name in ("display_handoff", "_attribution_problem", "_handoff_refuse", "_release_gate", "_consume_nonce", "prepare_run", "_seal"):
        used = {x.id for x in _ast.walk(fns[name]) if isinstance(x, _ast.Name)} | {x.attr for x in _ast.walk(fns[name]) if isinstance(x, _ast.Attribute)}
        assert not (used & banned), (name, used & banned)


def test_the_new_refusals_still_hold_under_python_dash_O():
    import subprocess

    code = (
        "import sys; sys.path.insert(0, %r); import tdcc_11641_min_fetch as m\n"
        "def boom(url, n): raise RuntimeError('transport must not be called')\n"
        "r = m.run('US0378331005', user_confirmed_non_holding=True, transport=boom, test_mode=False, run_id='forged')\n"
        "print(r.stop_reason, r.requests_used)\n"
        "print(m.display_handoff(m.Result(test_mode=False, value_released=True))['reason'])\n"
        "n = m.prepare_run()\n"
        "print(m._consume_nonce(n), m._consume_nonce(n))\n" % str(_ROOT / "scripts")
    )
    out = subprocess.run([sys.executable, "-O", "-c", code], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.split("\n")[:3] == ["run_id_not_issued 0", "not_issued_by_run", "None run_id_consumed"]


# ─── 變異（拿掉任一道新守衛，對應測試必須轉紅；以改寫來源字串現編，不落盤）───
def _nrun(ns, *, synthetic=False, test_mode=False, rows=None, rid=None, stated=False, rights_unknown=False, **kw):
    """用突變版模組自己的類別與登記表跑一次；真實模式先在突變版取 nonce。stated=True 時換成合成已載明顯名。"""
    if stated:
        ns["attribution_block"] = _stated_attr
    if test_mode is False:
        rid = rid or ns["prepare_run"]()
    run_id = rid if rid is not None else RUN
    r = ns["Rights"]("UNKNOWN" if rights_unknown else "ALLOWED", basis_ref="B", synthetic=synthetic,
                     r2_evidence=ns["R2Evidence"](run_id, ns["R2_PURPOSE"], ns["R2_SCOPE_FILE"], "c"))
    return ns["run"](GOOD_ISIN, user_confirmed_non_holding=True, transport=FakeTransport(_oas(), rows if rows is not None else _rows()),
                     rights=r, test_mode=test_mode, today=TODAY, now=NOW, run_id=run_id, **kw)


_UNMARKED_GUARD = '        if res.test_mode is None:\n            raise FetchStop("test_mode_unmarked")  # 明確條件（非 assert，-O 不會移除）：未標明模式不得出任何真 payload\n'
_MODE_COERCE = "    mode = test_mode if type(test_mode) is bool else None"
_GATE_ON = "        if res.test_mode is False:  # S1：真實模式的唯一出口＝顯示閘；拒收時 Result 不暴露 NAV／基金名稱，也不誤報 value_released\n"
_SEAL_SYN = '    elif mode is True:\n        refusal = "test_mode_synthetic"\n'
_STATED_LOOP = ('    for k in HANDOFF_STATED_REQUIRED:\n        if stated_values.get(k) is None:\n            return "attribution_not_stated"\n')
_ISIN_SUBST_RUN = ' or str(fund_code).strip().upper() == isin'
_ISIN_SHAPE_GATE = ' or isin_valid(code)'
_SUBST_CHECK = ('    if meta is not None and meta in (stated_values.get("release_year"), stated_values.get("dataset_version")):\n'
                '        return "attribution_substituted"  # 詮釋資料更新日不得冒充年份／版本\n')
_NONCE_NOT_ISSUED = '        if state is None:\n            return "run_id_not_issued"\n        if state != "issued":\n            return "run_id_consumed"\n'
_NONCE_MARK = '        _NONCES[run_id] = "consumed"\n'
_NONCE_GATE = ('        if mode is False:  # S3：真實模式只接受 `prepare_run()` 發出且尚未消耗的 nonce；一律在任何請求之前消耗（失敗後也不得重用）\n'
               '            why = _consume_nonce(run_id)\n            if why is not None:\n                raise FetchStop(why)\n')
_UNISSUED_REFUSE = '    if rec is None:\n        return _handoff_refuse("not_issued_by_run")\n'
_UI_PATTERN = 'UI_PURE_CODE_PATTERN = r"^([A-Z0-9]{3,30}(?:-[A-Z0-9]{2,20})?)$"'


def test_mutation_removing_the_unmarked_mode_guard_fails_open():
    ns = _mutant_multi([(_UNMARKED_GUARD, "")])
    assert _nrun(ns, test_mode=None).local_display is not None            # 守衛被拿掉 ⇒ 未標明模式也出 payload
    assert m.run(GOOD_ISIN, user_confirmed_non_holding=True, transport=FakeTransport(_oas(), _rows()), rights=_real(), today=TODAY,
                 now=NOW, run_id=RUN).local_display is None                # 原版：拒絕


def test_mutation_coercing_the_mode_to_bool_lets_string_modes_accept_synthetic_rights():
    ns = _mutant_multi([(_MODE_COERCE, "    mode = bool(test_mode) if test_mode is not None else None")])
    assert _nrun(ns, synthetic=True, test_mode="false").local_display is not None      # "false" 變成 True ⇒ 合成權利被當測試模式接受
    assert _run(FakeTransport(_oas(), _rows()), rights=ALLOWED, test_mode="false").local_display is None


def test_mutation_removing_the_seal_refusal_for_synthetic_results_releases_them_only_when_the_gate_is_also_widened():
    only_widened = _mutant_multi([(_GATE_ON, "        if res.test_mode is not None:\n")])
    syn = _nrun(only_widened, synthetic=True, test_mode=True, stated=True)
    assert only_widened["display_handoff"](syn)["reason"] == "test_mode_synthetic"      # 第二層（登記時的模式拒絕）仍擋住
    both = _mutant_multi([(_GATE_ON, "        if res.test_mode is not None:\n"), (_SEAL_SYN, "")])
    syn2 = _nrun(both, synthetic=True, test_mode=True, stated=True)
    assert both["display_handoff"](syn2)["released"] is True                             # 兩層都拿掉 ⇒ 合成結果放行
    assert m.display_handoff(_run(FakeTransport(_oas(), _rows()), rights=ALLOWED, test_mode=True))["released"] is False


def test_mutation_removing_the_stated_requirement_releases_unstated_attribution():
    ns = _mutant_multi([(_STATED_LOOP, "")])
    nres = _nrun(ns)                                                     # 真實模式、權利完整、顯名預設＝年份／版本 stated=False
    assert ns["display_handoff"](nres)["released"] is True               # 年份／版本未載明也放行 ⇒ 守衛被拿掉
    assert m.display_handoff(_real_run(stated=False))["released"] is False


def test_mutation_removing_the_metadata_substitution_check_lets_the_update_date_pose_as_year():
    ns = _mutant_multi([(_SUBST_CHECK, "")])

    def substituted():
        a = _stated_attr()
        a["metadata_updated_on"] = {"value": "2099", "stated": True, "reason": "x"}
        return a

    ns["attribution_block"] = substituted
    assert ns["display_handoff"](_nrun(ns))["released"] is True
    rights, ld = _gate_inputs()
    ld["attribution"] = substituted()
    assert m._release_gate(rights, ld) == ("attribution_substituted", None)


def test_mutation_removing_the_isin_substitution_checks_lets_an_isin_pose_as_the_code():
    ns = _mutant_multi([(_ISIN_SUBST_RUN, "")])
    assert _nrun(ns, test_mode=True, rows=_rows(**{m.KEY_CODE: GOOD_ISIN})).local_display["fund_code"] == GOOD_ISIN   # 代碼＝ISIN 被帶出
    ns2 = _mutant_multi([(_ISIN_SHAPE_GATE, "")])
    nres = _nrun(ns2, rows=_rows(**{m.KEY_CODE: "ZZ0000000008"}), stated=True)
    assert ns2["display_handoff"](nres)["released"] is True
    assert m.display_handoff(_real_run(stated=False, rows=_rows(**{m.KEY_CODE: "ZZ0000000008"})))["released"] is False


def test_mutation_removing_the_real_mode_display_gate_exposes_nav_in_the_result():
    ns = _mutant_multi([(_GATE_ON, "        if False:\n")])
    nres = _nrun(ns)                                                     # 顯名未載明＋真實模式
    assert nres.local_display is not None and nres.value_released is True   # 閘被拿掉 ⇒ Result 暴露 NAV／名稱（S1 的缺口）
    res = _real_run(stated=False)
    assert res.local_display is None and res.value_released is False


def test_mutation_removing_nonce_consumption_lets_a_replay_through():
    ns = _mutant_multi([(_NONCE_MARK, "")])
    rid = ns["prepare_run"]()
    assert _nrun(ns, rid=rid, stated=True).value_released is True
    assert _nrun(ns, rid=rid, stated=True).value_released is True        # 重放放行 ⇒ 守衛被拿掉
    rid2 = m.prepare_run()
    assert _real_run(stated=False, rid=rid2).stop_reason == "attribution_not_stated"
    assert _real_run(stated=False, rid=rid2).stop_reason == "run_id_consumed"


def test_mutation_removing_the_issued_check_lets_a_caller_chosen_run_id_through():
    ns = _mutant_multi([(_NONCE_NOT_ISSUED, '        if state is None:\n            return None\n')])
    assert _nrun(ns, test_mode=False, rid="chosen-by-caller", stated=True).stop_reason is None
    res = m.run(GOOD_ISIN, user_confirmed_non_holding=True, transport=FakeTransport(_oas(), _rows()), rights=_real(), test_mode=False,
                today=TODAY, now=NOW, run_id=RUN)
    assert res.stop_reason == "run_id_not_issued"


def test_mutation_removing_the_nonce_gate_in_run_lets_unissued_ids_run_real_mode():
    ns = _mutant_multi([(_NONCE_GATE, "")])
    assert _nrun(ns, test_mode=False, rid="chosen-by-caller", stated=True).stop_reason is None


def test_mutation_widening_the_code_pattern_lets_ui_incompatible_codes_through():
    ns = _mutant_multi([(_UI_PATTERN, 'UI_PURE_CODE_PATTERN = r"^[A-Za-z0-9._-]{1,40}$"')])
    assert ns["display_handoff"](_nrun(ns, rows=_rows(**{m.KEY_CODE: "A1.B"}), stated=True))["released"] is True
    import re as _re

    assert ns["UI_PURE_CODE_PATTERN"] != _re.search(r'^L2_PURE_CODE_PATTERN = r"(.+)"$', _UI_SRC.read_text(encoding="utf-8"), _re.M).group(1)


def test_mutation_accepting_unissued_results_in_the_handoff_breaks_the_forgery_defence():
    ns = _mutant_multi([(_UNISSUED_REFUSE, "")])
    forged = ns["Result"](test_mode=False, value_released=True)
    with pytest.raises(AttributeError):                                  # 沒有登記內容可讀：守衛被拿掉就崩（不再是乾淨拒收）
        ns["display_handoff"](forged)
    assert m.display_handoff(m.Result())["reason"] == "not_issued_by_run"


# ═════════════ r101 L1：seal 綁定「本次 run() 真正產出的 Result 實例」（弱引用＋`is`）；他人的 handle 貼到別的 Result／淺拷貝／已釋放者不得冒領 ═════════════
def _refused_real_result(monkeypatch):
    """真實模式但顯名未載明 ⇒ 被拒收的 Result（有自己的 handle）。先把可能被前一次 `_real_run(stated=True)` 換掉的顯名還原成原函式。"""
    monkeypatch.setattr(m, "attribution_block", _ORIG_ATTRIBUTION_BLOCK)
    return _real_run(monkeypatch, stated=False)


def test_l1_pasting_a_released_handle_onto_a_refused_result_does_not_release_anything(monkeypatch):
    released = _real_run(monkeypatch)
    refused = _refused_real_result(monkeypatch)
    assert released.value_released is True and refused.value_released is False
    own_before = m.display_handoff(refused)
    stolen = refused.handle
    refused.handle = released.handle                       # 把「另一個已放行 Result」的 handle 貼上來
    h = m.display_handoff(refused)
    assert h["released"] is False and h["reason"] == "not_issued_by_run" and h["payload"] is None
    assert h["decisions"] == {"display": False, "derive": False, "ai": False}
    refused.handle = stolen                                # 原持有者：照原核證結果、原拒收不變
    assert m.display_handoff(refused) == own_before and own_before["reason"] == "attribution_not_stated"
    assert m.display_handoff(released)["released"] is True and m.display_handoff(released)["payload"]["nav"] == "12.3456"


def test_l1_pasting_a_released_handle_onto_a_hand_built_or_synthetic_result_is_refused(monkeypatch):
    released = _real_run(monkeypatch)
    forged = m.Result(test_mode=False, value_released=True, handle=released.handle)
    assert m.display_handoff(forged)["reason"] == "not_issued_by_run"
    monkeypatch.setattr(m, "attribution_block", _stated_attr)
    syn = _run(FakeTransport(_oas(), _rows()), rights=ALLOWED, test_mode=True)
    syn.handle = released.handle
    assert m.display_handoff(syn)["released"] is False and m.display_handoff(syn)["reason"] == "not_issued_by_run"


def test_l1_copies_of_a_released_result_cannot_claim_the_release_but_the_original_keeps_it(monkeypatch):
    import copy
    import dataclasses

    released = _real_run(monkeypatch)
    before = m.display_handoff(released)
    for dup in (copy.copy(released), copy.deepcopy(released), dataclasses.replace(released)):
        assert dup is not released and dup.handle == released.handle   # 拷貝帶著同一個 handle，但不是登記當時的那個實例
        h = m.display_handoff(dup)
        assert h["released"] is False and h["reason"] == "not_issued_by_run" and h["payload"] is None
    assert m.display_handoff(released) == before and before["released"] is True


def test_l1_a_handle_of_a_freed_result_cannot_be_claimed_by_a_new_result(monkeypatch):
    import gc

    res = _real_run(monkeypatch)
    handle = res.handle
    assert m._SEALED[handle].owner() is res
    del res
    gc.collect()
    assert handle not in m._SEALED                         # r108（SF-P1）：實例釋放即清除其登記（原 v3 此處是「留下空殼」；前提已被取代）
    heir = m.Result(test_mode=False, value_released=True, handle=handle)
    h = m.display_handoff(heir)
    assert h["released"] is False and h["reason"] == "not_issued_by_run"


def test_l1_the_sealed_record_stays_immutable_and_bounded_and_the_handle_never_appears_in_repr_or_aggregate(monkeypatch):
    import dataclasses

    res = _real_run(monkeypatch)
    rec = m._SEALED[res.handle]
    with pytest.raises(dataclasses.FrozenInstanceError):
        rec.owner = lambda: None
    assert res.handle not in repr(res) and res.handle not in json.dumps(res.aggregate())   # （本機顯示用的 local_display 不在本斷言範圍）
    holders = [m.Result(test_mode=False) for _ in range(m._SEAL_MAX + 5)]      # r108：實例釋放即清登記，要填滿上限就得讓它們活著
    for h in holders:
        h.handle = m._seal(h, None)
    assert len(m._SEALED) <= m._SEAL_MAX                   # 有限記憶體
    assert m.display_handoff(res)["reason"] == "not_issued_by_run"   # 被淘汰＝fail closed


def test_l1_old_s2_guarantees_still_hold_after_the_binding(monkeypatch):
    res = _real_run(monkeypatch)
    before = m.display_handoff(res)
    res.local_display["nav"] = "999.9999"
    res.rights["R3"] = res.rights["R4"] = "ALLOWED"
    assert m.display_handoff(res) == before
    refused = _refused_real_result(monkeypatch)
    refused.value_released, refused.test_mode, refused.stop_reason = True, False, None
    assert m.display_handoff(refused)["released"] is False


_OWNER_CHECK = ('    if rec.owner() is not res:  # r101 L1：handle 只對「登記當時的那個 Result 實例」有效；他人 handle 貼到別的 Result／淺拷貝／實例已釋放者一律拒收\n'
                '        return _handoff_refuse("not_issued_by_run")\n')


def test_l1_mutation_removing_the_owner_check_lets_a_pasted_handle_through():
    ns = _mutant_multi([(_OWNER_CHECK, "")])
    released = _nrun(ns, stated=True)
    refused = _nrun(ns)                                     # 顯名未載明 ⇒ 拒收
    refused.handle = released.handle
    assert ns["display_handoff"](refused)["released"] is True       # 守衛被拿掉 ⇒ 冒領成功
    cp = ns["Result"](test_mode=False, value_released=True, handle=released.handle)
    assert ns["display_handoff"](cp)["released"] is True


def test_l1_mutation_holding_the_result_strongly_keeps_a_freed_result_alive():
    import gc

    ns = _mutant_multi([("                  weakref.ref(res, lambda wr, _h=handle: _owner_gone(_h, wr)))\n",
                         "                  (lambda _r=res: (lambda: _r))())\n")])
    r = _nrun(ns, stated=True)
    h = r.handle
    del r
    gc.collect()
    assert h in ns["_SEALED"] and ns["_SEALED"][h].owner() is not None   # 強引用變異：實例不會釋放（記憶體不受控）


def test_l1_the_new_guard_does_not_rely_on_assert_and_works_under_python_dash_O():
    import ast as _ast
    import subprocess

    tree = _ast.parse(SRC.read_text(encoding="utf-8"))
    fns = {n.name: n for n in _ast.walk(tree) if isinstance(n, _ast.FunctionDef)}
    assert not any(isinstance(x, _ast.Assert) for x in _ast.walk(fns["display_handoff"]))
    code = (
        "import sys; sys.path.insert(0, %r); import tdcc_11641_min_fetch as m\n"
        "a = m.Result(test_mode=False); a.handle = m._seal(a, None)\n"
        "b = m.Result(test_mode=False, handle=a.handle)\n"
        "print(m.display_handoff(a)['reason'], m.display_handoff(b)['reason'])\n" % str(_ROOT / "scripts")
    )
    out = subprocess.run([sys.executable, "-O", "-c", code], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "no_value_released not_issued_by_run"


# ═════════════ r108 SF-P1：owner 釋放後即清除其登記（含 payload_json）；清除不得競態／死鎖／誤刪其他登記 ═════════════
def _payload_strings_in_registry():
    return [rec.payload_json for rec in list(m._SEALED.values()) if rec.payload_json is not None]


def test_sfp1_a_released_result_leaves_no_registration_and_no_retained_payload(monkeypatch):
    import gc

    res = _real_run(monkeypatch)
    handle = res.handle
    assert handle in m._SEALED and any("12.3456" in p for p in _payload_strings_in_registry())
    del res
    gc.collect()
    assert handle not in m._SEALED
    assert not any("12.3456" in p for p in _payload_strings_in_registry())      # 釋放後登記表不再持有 NAV 內容


def test_sfp1_refused_and_cyclic_results_are_purged_too(monkeypatch):
    import gc

    refused = _refused_real_result(monkeypatch)
    hr = refused.handle
    released = _real_run(monkeypatch)
    released.__dict__["self_ref"] = released                 # 循環參照：要靠循環 GC 才會釋放
    hc = released.handle
    assert hr in m._SEALED and hc in m._SEALED
    del refused, released
    gc.collect()
    assert hr not in m._SEALED and hc not in m._SEALED


def test_sfp1_purging_one_owner_never_touches_other_registrations(monkeypatch):
    import gc

    a = _real_run(monkeypatch)
    b = _real_run(monkeypatch)
    keep = m.display_handoff(b)
    ha, hb = a.handle, b.handle
    del a
    gc.collect()
    assert ha not in m._SEALED and hb in m._SEALED
    assert m.display_handoff(b) == keep and keep["released"] is True      # 原持有者照原核證結果
    c = _refused_real_result(monkeypatch)
    assert m.display_handoff(c)["reason"] == "attribution_not_stated"      # 原拒收不變


def test_sfp1_purge_needs_the_same_owner_reference_so_a_stale_or_foreign_callback_deletes_nothing(monkeypatch):
    import weakref

    res = _real_run(monkeypatch)
    other = _real_run(monkeypatch)
    foreign = weakref.ref(other)                            # 不是此登記的 owner 參照
    m._purge(res.handle, foreign)
    assert res.handle in m._SEALED and m.display_handoff(res)["released"] is True
    m._purge("0" * 32, m._SEALED[res.handle].owner)         # 不存在的 handle：安靜無事
    assert m.display_handoff(res)["released"] is True


def test_sfp1_a_release_during_the_registry_lock_is_deferred_not_deadlocked_and_not_mutating_mid_operation(monkeypatch):
    import gc
    import threading

    res = _real_run(monkeypatch)
    handle = res.handle
    done = threading.Event()

    def worker():
        with m._SEAL_LOCK:                                  # 持鎖期間 owner 被釋放（等同 GC 在註冊表操作中途觸發）
            local = res_box.pop()
            del local
            gc.collect()
            assert_in_lock.append(handle in m._SEALED)      # 持鎖期間不得被動手腳
        done.set()

    res_box = [res]
    assert_in_lock: list = []
    del res
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(5)
    assert done.is_set() and not t.is_alive(), "持鎖期間釋放 owner 造成死鎖"
    assert assert_in_lock == [True]
    m.display_handoff(m.Result())                           # 下一次登記表操作會清掉延後的項目
    assert handle not in m._SEALED and not m._DEAD


def test_sfp1_concurrent_create_read_evict_and_release_stay_consistent(monkeypatch):
    import gc
    import threading

    monkeypatch.setattr(m, "attribution_block", _stated_attr)
    errors: list = []
    alive: list = []
    lock = threading.Lock()

    def churn(seed):
        try:
            for i in range(120):
                r = m.Result(test_mode=False, stop_reason=None)
                r.handle = m._seal(r, None)
                if (i + seed) % 17 == 0:
                    with lock:
                        alive.append(r)
                m.display_handoff(r)
                if i % 5 == 0:
                    m.display_handoff(m.Result())           # 觸發 drain
        except Exception as e:                              # noqa: BLE001
            errors.append(repr(e))

    ts = [threading.Thread(target=churn, args=(k,)) for k in range(8)]
    [t.start() for t in ts]
    [t.join(60) for t in ts]
    assert not any(t.is_alive() for t in ts) and errors == []
    gc.collect()
    m.display_handoff(m.Result())
    assert len(m._SEALED) <= m._SEAL_MAX
    live = {r.handle for r in alive}
    assert live <= set(m._SEALED) or len(m._SEALED) == m._SEAL_MAX   # 活著的 owner 的登記還在（除非被上限淘汰）
    assert all(rec.owner() is not None for rec in list(m._SEALED.values()))     # 已釋放者一律被清掉，沒有空殼


def test_sfp1_eviction_still_fails_closed_and_the_cap_still_holds(monkeypatch):
    keep = _real_run(monkeypatch)
    holders = [m.Result(test_mode=False) for _ in range(m._SEAL_MAX + 3)]       # 讓它們活著才會逼出上限淘汰
    for h in holders:
        h.handle = m._seal(h, None)
    assert len(m._SEALED) <= m._SEAL_MAX
    assert m.display_handoff(keep)["reason"] == "not_issued_by_run"          # 被上限淘汰＝拒收


def test_sfp1_the_new_functions_do_not_use_assert_and_the_callback_closure_holds_no_strong_reference(monkeypatch):
    import ast as _ast
    import gc
    import weakref

    tree = _ast.parse(SRC.read_text(encoding="utf-8"))
    fns = {n.name: n for n in _ast.walk(tree) if isinstance(n, _ast.FunctionDef)}
    for name in ("_owner_gone", "_purge", "_drain_dead", "_seal", "display_handoff"):
        assert not any(isinstance(x, _ast.Assert) for x in _ast.walk(fns[name])), name
    res = _real_run(monkeypatch)
    probe = weakref.ref(res)
    del res
    gc.collect()
    assert probe() is None                                  # 登記（含 callback）沒有把 Result 抓成強引用


def test_sfp1_mutation_removing_the_release_callback_keeps_the_payload_alive():
    import gc

    ns = _mutant_multi([("                  weakref.ref(res, lambda wr, _h=handle: _owner_gone(_h, wr)))\n", "                  weakref.ref(res))\n")])
    r = _nrun(ns, stated=True)
    h = r.handle
    del r
    gc.collect()
    assert h in ns["_SEALED"]                               # 守衛被拿掉 ⇒ 釋放後登記（含 payload）仍留著


def test_sfp1_mutation_blocking_acquire_in_the_callback_self_deadlocks_when_released_under_the_lock():
    import gc
    import threading

    ns = _mutant_multi([("    if _SEAL_LOCK.acquire(blocking=False):\n", "    if _SEAL_LOCK.acquire():\n")])
    r = _nrun(ns, stated=True)
    box = [r]
    del r
    done = threading.Event()

    def worker():
        with ns["_SEAL_LOCK"]:
            box.pop()
            gc.collect()
        done.set()

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(2)
    assert not done.is_set() and t.is_alive()               # 變異版：持鎖時釋放即死鎖（守衛有效的反證）


def test_sfp1_mutation_removing_the_owner_identity_check_lets_a_foreign_reference_delete_a_registration():
    import weakref

    ns = _mutant_multi([("    if rec is not None and rec.owner is owner_ref:\n", "    if rec is not None:\n")])
    r1 = _nrun(ns, stated=True)
    r2 = _nrun(ns, stated=True)
    ns["_purge"](r1.handle, weakref.ref(r2))
    assert r1.handle not in ns["_SEALED"]                   # 守衛被拿掉 ⇒ 外來參照可刪別人的登記


def test_sfp1_mutation_removing_the_drain_leaves_a_deferred_purge_stuck():
    import gc
    import threading

    ns = _mutant_multi([("    with _SEAL_LOCK:\n        _drain_dead()\n        rec = _SEALED.get(handle)", "    with _SEAL_LOCK:\n        rec = _SEALED.get(handle)")])
    r = _nrun(ns, stated=True)
    h = r.handle
    box = [r]
    del r

    def worker():
        with ns["_SEAL_LOCK"]:
            box.pop()
            gc.collect()

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(5)
    ns["display_handoff"](ns["Result"]())
    assert h in ns["_SEALED"]                               # 守衛被拿掉 ⇒ 延後的清除永遠不會發生
