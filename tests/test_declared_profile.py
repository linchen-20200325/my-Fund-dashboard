"""`repositories/fund/declared_profile.py`（exp 正式模式批 C 的 C1：L1 自報基本資料取數）守衛。

⚠️ **本檔的 HTML 與 JSON 全部是手寫的最小樣本**，標籤結構（MoneyDJ 基本資料表）、
清單欄名（TDCC 3-2）、回應鍵名（FundClear `GetFundBasicInfo`）**都未以真實回應樣本驗證** ——
repo 裡沒有這三個來源的原始回應，本環境也連不到。樣本照 repo 既有解析碼
（`sources._src_tcb_meta`／`_src_tdcc_meta`／`_src_fundclear_meta`）會吃的形狀寫。

全程不打網路：`fetch_url_with_retry` 換成依網址回應的替身（失敗時照 `infra.proxy.fetch_url`
的做法把分類寫進 thread-local，讓 `pop_last_fail_kind()` 走真的那條路）；`_tdcc_get` 換成替身，
或保留真的 `_tdcc_get` 但預先放好它的行程內快取並把 `urlopen` 換成一碰就炸的替身。
"""
from __future__ import annotations

import json

import pytest

import infra.proxy as proxy_mod
import infra.source_backoff as sb
import repositories.fund.declared_profile as dp
from repositories.fund import sources as src

CODE = "TLZF9"
TCB = "tcbbankfund.moneydj.com"
WWW = "www.moneydj.com"


def _mdj(host, page, code=CODE):
    return f"https://{host}/funddj/yp/{page}.djhtm?a={code}"


# 境外（預設）順序：yp011001 tcb → yp011001 www → yp011000 tcb → yp011000 www
U1, U2, U3, U4 = (_mdj(TCB, "yp011001"), _mdj(WWW, "yp011001"),
                  _mdj(TCB, "yp011000"), _mdj(WWW, "yp011000"))

_PAD = "<p>" + ("基金 淨值 日期 績效 " * 40) + "</p>"   # 讓頁面長度 > 500 且過得了 is_valid_moneydj_page


def _page(rows_html: str, code: str = CODE, pad: bool = True) -> str:
    return (f"<html><body>{_PAD if pad else ''}<a href='/w/wb/wb01.djhtm?a={code}'>{code}</a>"
            f"<table>{rows_html}</table></body></html>")


def _row2(k, v):
    return f"<tr><td>{k}</td><td>{v}</td></tr>"


def _row4(k1, v1, k2, v2):
    return f"<tr><td>{k1}</td><td>{v1}</td><td>{k2}</td><td>{v2}</td></tr>"


FULL_TABLE = (_row2("基金名稱", "安聯收益成長基金-AM穩定月收類股(美元)")
              + _row4("計價幣別", "美元", "配息頻率", "月配")
              + _row4("成立日期", "2012/03/23", "最高經理費(%)", "1.80"))

SHELL = "<html><body>" + _PAD + ("x" * 2000) + "</body></html>"   # 長度夠、沒表、沒代碼


class _Resp:
    def __init__(self, text=None, payload=None):
        self.text = text if text is not None else json.dumps(payload or {})
        self._payload = payload

    def json(self):
        if self._payload is None:
            return json.loads(self.text)
        return self._payload


class _Net:
    """依網址回應的 `fetch_url_with_retry` 替身。spec：("html", str) / ("json", obj) / ("fail", kind) / ("empty",)。"""

    def __init__(self, routes: dict):
        self.routes = routes
        self.calls: list = []

    def __call__(self, url, headers=None, params=None, timeout=20, retries=3, sleep_sec=2):
        self.calls.append(url)
        proxy_mod._TLS_FAIL.kind = ""          # 同 fetch_url：進場先清
        spec = self.routes.get(url, ("fail", "not_found"))
        if spec[0] == "html":
            return _Resp(text=spec[1])
        if spec[0] == "json":
            return _Resp(payload=spec[1])
        if spec[0] == "fail":
            proxy_mod._TLS_FAIL.kind = spec[1]   # 同 fetch_url 的 _note_failure
            return None
        return None                            # empty：200 但內文空 → None 且無分類


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    for fn in (dp.fetch_moneydj_basic_fields, dp.fetch_tdcc_listing, dp.fetch_fundclear_declared_ccy):
        fn.cache_clear()
    dp._TDCC_OBSERVED.clear()
    monkeypatch.setattr(src, "_is_domestic_code", lambda code, page_type="": False)
    monkeypatch.setattr(src, "_tdcc_cache", {})

    def _no_network(*a, **k):
        raise AssertionError("測試不得打網路（urllib）")
    import urllib.request as ur
    monkeypatch.setattr(ur, "urlopen", _no_network)
    yield
    for fn in (dp.fetch_moneydj_basic_fields, dp.fetch_tdcc_listing, dp.fetch_fundclear_declared_ccy):
        fn.cache_clear()
    dp._TDCC_OBSERVED.clear()


@pytest.fixture
def clock(monkeypatch):
    """讓 `_now_iso` 每次呼叫前進一秒，才驗得出「命中快取時時刻沒被改寫」。"""
    state = {"n": 0}

    def _tick():
        state["n"] += 1
        return f"2026-10-14T00:00:{state['n']:02d}+00:00"
    monkeypatch.setattr(dp, "_now_iso", _tick)
    return state


def _net(monkeypatch, routes):
    net = _Net(routes)
    monkeypatch.setattr(dp, "fetch_url_with_retry", net)
    return net


# ═════════════════════════════ MoneyDJ ═════════════════════════════

class TestMoneyDJLabels:
    def test_reads_exactly_the_four_labels_with_raw_literals(self, monkeypatch):
        _net(monkeypatch, {U1: ("html", _page(FULL_TABLE))})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["status"] == "ok"
        assert r["fields"] == {"基金名稱": "安聯收益成長基金-AM穩定月收類股(美元)",
                               "計價幣別": "美元", "配息頻率": "月配", "成立日期": "2012/03/23"}
        assert r["provenance"] == {"host": TCB, "page_type": "yp011001", "url": U1}
        assert r["error"] is None

    def test_max_mgmt_fee_is_never_read(self, monkeypatch):
        _net(monkeypatch, {U1: ("html", _page(FULL_TABLE))})
        r = dp.fetch_moneydj_basic_fields(CODE)
        dumped = json.dumps(r, ensure_ascii=False)
        assert "經理費" not in dumped and "1.80" not in dumped

    def test_near_miss_labels_are_not_accepted(self, monkeypatch):
        rows = (_row2("基金名稱", "某基金") + _row2("設立日期", "2001/01/01")
                + _row2("成立日", "2002/02/02") + _row2("計價幣別：", "美元")
                + _row2("配息頻率(年)", "12"))
        _net(monkeypatch, {U1: ("html", _page(rows))})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["status"] == "ok"
        assert r["fields"]["成立日期"] is None
        assert r["fields"]["計價幣別"] is None
        assert r["fields"]["配息頻率"] is None

    def test_surrounding_whitespace_is_stripped_for_label_match(self, monkeypatch):
        rows = _row2("基金名稱", "某基金") + _row2("  計價幣別\n", " 新臺幣 ")
        _net(monkeypatch, {U1: ("html", _page(rows))})
        assert dp.fetch_moneydj_basic_fields(CODE)["fields"]["計價幣別"] == "新臺幣"

    def test_missing_fields_are_none_not_zero(self, monkeypatch):
        _net(monkeypatch, {U1: ("html", _page(_row2("基金名稱", "某基金")))})
        f = dp.fetch_moneydj_basic_fields(CODE)["fields"]
        assert f == {"基金名稱": "某基金", "計價幣別": None, "配息頻率": None, "成立日期": None}

    def test_two_cell_and_four_cell_rows(self, monkeypatch):
        rows = (_row4("基金名稱", "甲", "計價幣別", "歐元") + _row2("配息頻率", "季配")
                + "<tr><td>成立日期</td><td>2010/01/01</td><td>孤兒格</td></tr>")   # 3 格不收
        _net(monkeypatch, {U1: ("html", _page(rows))})
        f = dp.fetch_moneydj_basic_fields(CODE)["fields"]
        assert f["基金名稱"] == "甲" and f["計價幣別"] == "歐元" and f["配息頻率"] == "季配"
        assert f["成立日期"] is None

    def test_conflicting_duplicate_label_keeps_first_and_is_reported(self, monkeypatch):
        rows = _row2("基金名稱", "甲") + _row2("計價幣別", "美元") + _row2("計價幣別", "台幣")
        _net(monkeypatch, {U1: ("html", _page(rows))})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["fields"]["計價幣別"] == "美元"
        assert r["label_conflicts"] and "台幣" in r["label_conflicts"][0]


class TestMoneyDJUrlChain:
    def test_shell_page_long_enough_does_not_stop_the_chain(self, monkeypatch):
        net = _net(monkeypatch, {U1: ("html", SHELL), U2: ("html", _page(FULL_TABLE))})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert len(SHELL) > 500
        assert r["status"] == "ok" and r["provenance"]["url"] == U2
        assert net.calls == [U1, U2]
        assert r["attempts"][0]["outcome"] == "valid_page_without_code_or_table"

    def test_page_not_mentioning_code_is_not_adopted(self, monkeypatch):
        other = _page(FULL_TABLE, code="OTHER1")
        net = _net(monkeypatch, {U1: ("html", other), U2: ("html", _page(FULL_TABLE))})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["provenance"]["url"] == U2
        assert r["attempts"][0]["outcome"] == "unrecognized_page"
        assert net.calls == [U1, U2]

    def test_domestic_code_tries_yp011000_first(self, monkeypatch):
        monkeypatch.setattr(src, "_is_domestic_code", lambda code, page_type="": True)
        net = _net(monkeypatch, {})
        dp.fetch_moneydj_basic_fields(CODE)
        assert net.calls == [U3, U4, U1, U2]

    def test_each_url_has_an_attempt_with_classified_fail_kind(self, monkeypatch):
        net = _net(monkeypatch, {U1: ("fail", "unreachable"), U2: ("fail", "blocked"),
                                 U3: ("fail", "rate_limited"), U4: ("fail", "server_error")})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["status"] == "failed"
        assert [a["url"] for a in r["attempts"]] == [U1, U2, U3, U4] == net.calls
        assert [a["fail_kind"] for a in r["attempts"]] == ["unreachable", "blocked", "rate_limited", "server_error"]
        assert all(a["outcome"] == "http_failed" for a in r["attempts"])
        for u in (U1, U2, U3, U4):
            assert u in r["error"]
        assert r["fetched_at"] is None
        assert proxy_mod.pop_last_fail_kind() == ""   # 分類被讀走了，沒有殘值留給下一個 caller

    def test_all_definite_absent_is_not_listed(self, monkeypatch):
        valid_no_code = "<html><body>" + _PAD + "</body></html>"
        _net(monkeypatch, {U1: ("fail", "not_found"), U2: ("fail", "not_found"),
                           U3: ("html", valid_no_code), U4: ("fail", "not_found")})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["status"] == "not_listed"
        assert r["error"] is None
        assert [a["outcome"] for a in r["attempts"]] == [
            "not_found_404", "not_found_404", "valid_page_without_code_or_table", "not_found_404"]

    @pytest.mark.parametrize("bad", [("fail", "unreachable"), ("fail", "blocked"), ("fail", "rate_limited"),
                                     ("fail", "server_error"), ("fail", "proxy_auth"), ("empty",)])
    def test_any_indeterminate_attempt_makes_it_failed_not_not_listed(self, monkeypatch, bad):
        _net(monkeypatch, {U1: ("fail", "not_found"), U2: ("fail", "not_found"),
                           U3: ("fail", "not_found"), U4: bad})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["status"] == "failed"
        assert U4 in r["error"]

    def test_empty_response_is_classified(self, monkeypatch):
        _net(monkeypatch, {U1: ("empty",)})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert r["attempts"][0]["outcome"] == "empty_response"

    def test_host_in_cooldown_is_not_fetched_and_counts_as_failed(self, monkeypatch):
        sb.record_failure(TCB, "blocked")
        net = _net(monkeypatch, {U2: ("fail", "not_found"), U4: ("fail", "not_found")})
        r = dp.fetch_moneydj_basic_fields(CODE)
        assert net.calls == [U2, U4]                       # tcbbankfund 兩個網址沒打
        cd = [a for a in r["attempts"] if a["host"] == TCB]
        assert len(cd) == 2 and all(a["fail_kind"] == "cooldown" for a in cd)
        assert all(a["cooldown_origin_kind"] == "blocked" for a in cd)
        assert r["status"] == "failed"

    def test_invalid_full_key_raises_without_network(self, monkeypatch):
        net = _net(monkeypatch, {})
        with pytest.raises(ValueError):
            dp.fetch_moneydj_basic_fields("a b")
        with pytest.raises(TypeError):
            dp.fetch_moneydj_basic_fields(None)
        assert net.calls == []


class TestMoneyDJCache:
    def test_ok_is_cached_and_fetched_at_unchanged_on_hit(self, monkeypatch, clock):
        net = _net(monkeypatch, {U1: ("html", _page(FULL_TABLE))})
        a = dp.fetch_moneydj_basic_fields(CODE)
        b = dp.fetch_moneydj_basic_fields(CODE)
        assert len(net.calls) == 1
        assert a["fetched_at"] and b["fetched_at"] == a["fetched_at"]
        assert dp.fetch_moneydj_basic_fields.cache_info()["hits"] == 1

    def test_not_listed_is_cached(self, monkeypatch):
        net = _net(monkeypatch, {})   # 全部 404
        assert dp.fetch_moneydj_basic_fields(CODE)["status"] == "not_listed"
        dp.fetch_moneydj_basic_fields(CODE)
        assert len(net.calls) == 4

    def test_failed_is_not_cached(self, monkeypatch):
        net = _net(monkeypatch, {U1: ("fail", "unreachable")})
        assert dp.fetch_moneydj_basic_fields(CODE)["status"] == "failed"
        dp.fetch_moneydj_basic_fields(CODE)
        assert len(net.calls) == 8
        assert dp.fetch_moneydj_basic_fields.cache_info()["uncached_fail"] == 2

    def test_returns_deep_copy(self, monkeypatch):
        _net(monkeypatch, {U1: ("html", _page(FULL_TABLE))})
        a = dp.fetch_moneydj_basic_fields(CODE)
        a["fields"]["計價幣別"] = "被改掉"
        a["attempts"].clear()
        b = dp.fetch_moneydj_basic_fields(CODE)
        assert b["fields"]["計價幣別"] == "美元" and b["attempts"]

    def test_registered_in_cache_registry(self):
        from infra.cache import _CACHE_REGISTRY
        names = {getattr(f, "__name__", "") for f in _CACHE_REGISTRY}
        assert {"fetch_moneydj_basic_fields", "fetch_tdcc_listing",
                "fetch_fundclear_declared_ccy"} <= names


# ═════════════════════════════ TDCC ═════════════════════════════

TDCC_ROWS = [
    {"基金代碼": "AAA01", "基金名稱": "甲基金", "計價幣別": "USD"},
    {"境外基金代碼": "tlzf9", "基金名稱": "安聯收益成長", "計價幣別": "美元"},
]


def _tdcc(monkeypatch, data, error=None):
    calls = []

    def fake(ep, *, error_out=None):
        calls.append(ep)
        if error and error_out is not None:
            error_out["error"] = error
        return data
    monkeypatch.setattr(src, "_tdcc_get", fake)
    return calls


class TestTdcc:
    def test_listed_by_offshore_code_key(self, monkeypatch):
        _tdcc(monkeypatch, TDCC_ROWS)
        r = dp.fetch_tdcc_listing(CODE)
        assert r["status"] == "ok"
        assert r["fields"] == {"基金名稱": "安聯收益成長", "計價幣別": "美元"}
        assert r["provenance"]["code_key"] == "境外基金代碼"
        assert r["fetched_at"] is None and r["observed_at"]

    def test_non_empty_list_without_code_is_not_listed(self, monkeypatch):
        _tdcc(monkeypatch, TDCC_ROWS)
        r = dp.fetch_tdcc_listing("ZZZ99")
        assert r["status"] == "not_listed" and r["error"] is None

    def test_missing_currency_key_is_none(self, monkeypatch):
        _tdcc(monkeypatch, [{"基金代碼": CODE, "基金名稱": "甲"}])
        assert dp.fetch_tdcc_listing(CODE)["fields"]["計價幣別"] is None

    def test_empty_list_with_error_is_failed_and_records_backoff(self, monkeypatch):
        _tdcc(monkeypatch, [], error="HTTPError: HTTP Error 403: Forbidden")
        r = dp.fetch_tdcc_listing(CODE)
        assert r["status"] == "failed" and "403" in r["error"]
        assert r["attempts"][0]["fail_kind"] == "blocked"
        skip, _left, kind = sb.should_skip("openapi.tdcc.com.tw")
        assert skip and kind == "blocked"

    def test_fresh_empty_list_without_error_is_failed(self, monkeypatch):
        _tdcc(monkeypatch, [])
        r = dp.fetch_tdcc_listing(CODE)
        assert r["status"] == "failed"
        assert r["attempts"][0]["outcome"] == "empty_or_non_list"

    def test_cached_empty_list_from_real_tdcc_get_is_failed(self, monkeypatch):
        # 真的 `_tdcc_get`；行程內快取放 `[]`（它把非清單回應永久快取成這個）；urlopen 一碰就炸。
        monkeypatch.setattr(src, "_tdcc_cache", {"3-2": []})
        r = dp.fetch_tdcc_listing(CODE)
        assert r["status"] == "failed"
        assert r["attempts"][0]["outcome"] == "cached_empty_list"
        assert not sb.should_skip("openapi.tdcc.com.tw")[0]   # 沒發請求，不記失敗

    def test_cooldown_does_not_call_tdcc_get(self, monkeypatch):
        calls = _tdcc(monkeypatch, TDCC_ROWS)
        sb.record_failure("openapi.tdcc.com.tw", "unreachable")
        r = dp.fetch_tdcc_listing(CODE)
        assert calls == []
        assert r["status"] == "failed" and r["attempts"][0]["fail_kind"] == "cooldown"

    def test_ok_cached_failed_not_cached(self, monkeypatch):
        calls = _tdcc(monkeypatch, TDCC_ROWS)
        dp.fetch_tdcc_listing(CODE)
        dp.fetch_tdcc_listing(CODE)
        assert calls == ["3-2"]
        calls2 = _tdcc(monkeypatch, [])
        dp.fetch_tdcc_listing("BBB02")
        dp.fetch_tdcc_listing("BBB02")
        assert calls2 == ["3-2", "3-2"]

    def test_observed_at_is_first_observation_of_same_list(self, monkeypatch, clock):
        _tdcc(monkeypatch, TDCC_ROWS)
        a = dp.fetch_tdcc_listing(CODE)
        b = dp.fetch_tdcc_listing("AAA01")        # 不同 key、同一份清單物件
        assert a["observed_at"] == b["observed_at"]
        _tdcc(monkeypatch, list(TDCC_ROWS))       # 換成另一份清單物件（快取被換掉）
        c = dp.fetch_tdcc_listing("ZZZ99")
        assert c["observed_at"] != a["observed_at"]

    def test_cache_hit_keeps_observed_at(self, monkeypatch, clock):
        _tdcc(monkeypatch, TDCC_ROWS)
        a = dp.fetch_tdcc_listing(CODE)
        b = dp.fetch_tdcc_listing(CODE)
        assert a["observed_at"] == b["observed_at"]

    def test_ambiguous_duplicate_code_is_failed(self, monkeypatch):
        _tdcc(monkeypatch, [{"基金代碼": CODE, "基金名稱": "甲", "計價幣別": "USD"},
                            {"基金代碼": CODE, "基金名稱": "甲", "計價幣別": "TWD"}])
        r = dp.fetch_tdcc_listing(CODE)
        assert r["status"] == "failed" and r["match_count"] == 2


# ═════════════════════════════ FundClear ═════════════════════════════

FC_URL = ("https://www.fundclear.com.tw/SmartFundAPI/api/FundAjax"
          f"/GetFundBasicInfo?FundCode={CODE}")


class TestFundClear:
    def test_reads_currency_from_data(self, monkeypatch):
        _net(monkeypatch, {FC_URL: ("json", {"Data": {"FundName": "甲", "Currency": "USD"}})})
        r = dp.fetch_fundclear_declared_ccy(CODE)
        assert r["status"] == "ok"
        assert r["fields"] == {"currency": "USD"} and r["currency_key"] == "Currency"
        assert r["provenance"]["url"] == FC_URL

    def test_lowercase_currency_key_recorded(self, monkeypatch):
        _net(monkeypatch, {FC_URL: ("json", {"Data": [{"currency": "歐元"}]})})
        r = dp.fetch_fundclear_declared_ccy(CODE)
        assert r["fields"]["currency"] == "歐元" and r["currency_key"] == "currency"

    def test_without_data_key_outer_payload_is_not_read(self, monkeypatch):
        _net(monkeypatch, {FC_URL: ("json", {"Currency": "USD", "FundName": "冒充", "data": {"Currency": "JPY"}})})
        r = dp.fetch_fundclear_declared_ccy(CODE)
        assert r["status"] == "failed"
        assert r["fields"]["currency"] is None
        assert "USD" not in json.dumps(r["fields"]) and r["attempts"][0]["outcome"] == "no_data_key"

    def test_missing_currency_is_none_not_zero(self, monkeypatch):
        _net(monkeypatch, {FC_URL: ("json", {"Data": {"FundName": "甲", "Currency": ""}})})
        r = dp.fetch_fundclear_declared_ccy(CODE)
        assert r["status"] == "ok" and r["fields"]["currency"] is None and r["currency_key"] is None

    def test_inception_date_is_not_read(self, monkeypatch):
        _net(monkeypatch, {FC_URL: ("json", {"Data": {"Currency": "USD", "InceptionDate": "2001-01-01"}})})
        assert "2001" not in json.dumps(dp.fetch_fundclear_declared_ccy(CODE))

    def test_null_data_is_not_listed_and_cached(self, monkeypatch):
        net = _net(monkeypatch, {FC_URL: ("json", {"Data": None})})
        assert dp.fetch_fundclear_declared_ccy(CODE)["status"] == "not_listed"
        dp.fetch_fundclear_declared_ccy(CODE)
        assert net.calls == [FC_URL]

    @pytest.mark.parametrize("payload,outcome", [
        ({"Data": [{"Currency": "USD"}, {"Currency": "TWD"}]}, "data_ambiguous"),
        ({"Data": {"FundCode": "OTHER", "Currency": "USD"}}, "code_mismatch"),
        ({"Data": "x"}, "data_not_dict"),
        ([1, 2], "no_data_key"),
    ])
    def test_shape_failures(self, monkeypatch, payload, outcome):
        _net(monkeypatch, {FC_URL: ("json", payload)})
        r = dp.fetch_fundclear_declared_ccy(CODE)
        assert r["status"] == "failed" and r["attempts"][0]["outcome"] == outcome
        assert r["fields"]["currency"] is None

    def test_404_is_failed_not_cached(self, monkeypatch):
        net = _net(monkeypatch, {FC_URL: ("fail", "not_found")})
        r = dp.fetch_fundclear_declared_ccy(CODE)
        assert r["status"] == "failed" and r["attempts"][0]["fail_kind"] == "not_found"
        dp.fetch_fundclear_declared_ccy(CODE)
        assert net.calls == [FC_URL, FC_URL]

    def test_cooldown_not_fetched(self, monkeypatch):
        sb.record_failure("www.fundclear.com.tw", "server_error")
        net = _net(monkeypatch, {FC_URL: ("json", {"Data": {"Currency": "USD"}})})
        r = dp.fetch_fundclear_declared_ccy(CODE)
        assert net.calls == [] and r["status"] == "failed"
        assert r["attempts"][0]["fail_kind"] == "cooldown"

    def test_fetched_at_unchanged_on_cache_hit(self, monkeypatch, clock):
        _net(monkeypatch, {FC_URL: ("json", {"Data": {"Currency": "USD"}})})
        a = dp.fetch_fundclear_declared_ccy(CODE)
        b = dp.fetch_fundclear_declared_ccy(CODE)
        assert a["fetched_at"] and a["fetched_at"] == b["fetched_at"]
