"""離線測試：全部為合成輸入／mock，**不含真新聞、不發任何網路請求**；不得冒充真 RSS 測試。
MF1 代理 / MF2 HTTPS+3xx / MF3 bytes+時限 / MF4 時間窗 / MF5 去重與 HOLD，並含無落地／無洩漏負控。
"""
import builtins
import datetime as dt
import email.message
import os
import ssl
import sys
import urllib.request
import uuid

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import trial as t

NOW = dt.datetime(2026, 11, 23, 12, 0, tzinfo=dt.timezone.utc)
HOST = "feeds.bbci.co.uk"


def h(n):
    return (NOW - dt.timedelta(hours=n)).strftime("%a, %d %b %Y %H:%M:%S +0000")


# ---------- mock transport（在 HTTPSHandler.do_open 邊界攔截；零 socket） ----------
class FakeResp:
    def __init__(self, body=b"", code=200, headers=None, chunks=None):
        self.code, self.status, self.msg = code, code, "X"
        self.headers = email.message.Message()
        for k, v in (headers or {}).items():
            self.headers[k] = v
        self._body, self._chunks, self.served, self.closed = body, chunks, 0, False

    def info(self):
        return self.headers

    def getcode(self):
        return self.code

    def geturl(self):
        return "https://x/"

    def read(self, n=-1):
        if self._chunks is not None:           # 無限串流來源
            self.served += n
            return b"\0" * n
        out, self._body = self._body[:n], self._body[n:]
        self.served += len(out)
        return out

    def close(self):
        self.closed = True


@pytest.fixture
def transport(monkeypatch):
    calls = []
    plan = {"resp": FakeResp(b"<rss/>")}

    def fake_do_open(self, http_class, req, **kw):
        calls.append((req.host, req.selector, req.full_url))
        return plan["resp"]

    monkeypatch.setattr(urllib.request.HTTPSHandler, "do_open", fake_do_open)
    return calls, plan


RSS_OK = ("<rss><channel>" + "".join(
    f"<item><title>T{i}</title><link>https://a/{i}</link><pubDate>{h(1)}</pubDate></item>" for i in range(3)
) + "</channel></rss>").encode()


# ---------- MF1：顯式禁代理 ----------
def test_mf1_env_proxy_ignored_and_negative_control(monkeypatch, transport):
    calls, plan = transport
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("https_proxy", "http://127.0.0.1:9")
    plan["resp"] = FakeResp(RSS_OK)
    t.fetch_source("BBC World", t.build_trial_opener())
    assert calls[-1][0] == HOST and calls[-1][1].startswith("/news")      # 直連：host=目標站、selector=path
    # 負控：預設 opener 會被環境代理改道（證明此測試能偵測代理注入）
    urllib.request.build_opener(urllib.request.HTTPSHandler()).open("https://" + HOST + "/x")
    assert calls[-1][0] == "127.0.0.1:9"


def test_mf1_system_proxy_discovery_not_consulted(monkeypatch, transport):
    calls, plan = transport
    called = []
    monkeypatch.setattr(urllib.request, "getproxies", lambda: called.append(1) or {"https": "http://127.0.0.1:9"})
    monkeypatch.setattr(urllib.request, "proxy_bypass", lambda h: called.append(2) or False)
    plan["resp"] = FakeResp(RSS_OK)
    t.fetch_source("BBC World", t.build_trial_opener())
    assert calls[-1][0] == HOST and not called                            # Windows registry 路徑（getproxies）未被呼叫


# ---------- MF2：僅 pinned HTTPS；3xx 立停 ----------
@pytest.mark.parametrize("loc", ["https://evil.example/x", "http://evil.example/x", "/relative"])
def test_mf2_any_3xx_stops_without_second_request(transport, loc):
    calls, plan = transport
    plan["resp"] = FakeResp(b"", code=302, headers={"Location": loc})
    with pytest.raises(t.RedirectRefused):
        t.fetch_source("BBC World", t.build_trial_opener())
    assert len(calls) == 1


def test_mf2_https_only_and_pinned_and_tls_required():
    o = t.build_trial_opener()
    assert "http" not in o.handle_open and "https" in o.handle_open
    ctx = t._ssl_ctx()
    assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname is True
    https_h = [x for x in o.handlers if isinstance(x, urllib.request.HTTPSHandler)][0]
    assert https_h._context.verify_mode == ssl.CERT_REQUIRED
    assert all(u.startswith("https://") for u in t.FEEDS.values()) and len(t.FEEDS) == 5
    with pytest.raises(t.NotPinned):
        t.fetch_source("NotInList", o)


# ---------- MF3：實際讀取上限／時限／編碼／DTD ----------
def test_mf3_infinite_body_stops_near_cap(transport):
    calls, plan = transport
    plan["resp"] = FakeResp(chunks=True)
    with pytest.raises(t.TooLarge):
        t.fetch_source("BBC World", t.build_trial_opener())
    assert plan["resp"].served <= t.MAX_BYTES + t.CHUNK and plan["resp"].closed


def test_mf3_lying_small_content_length_still_capped(transport):
    calls, plan = transport
    plan["resp"] = FakeResp(chunks=True, headers={"Content-Length": "10"})
    with pytest.raises(t.TooLarge):
        t.fetch_source("BBC World", t.build_trial_opener())
    assert plan["resp"].served <= t.MAX_BYTES + t.CHUNK


def test_mf3_declared_huge_length_rejected_before_read(transport):
    calls, plan = transport
    plan["resp"] = FakeResp(RSS_OK, headers={"Content-Length": str(t.MAX_BYTES + 1)})
    with pytest.raises(t.TooLarge):
        t.fetch_source("BBC World", t.build_trial_opener())
    assert plan["resp"].served == 0


def test_mf3_deadline_and_encoding_and_dtd(monkeypatch, transport):
    calls, plan = transport
    ticks = iter([0.0, 0.0, 999.0, 999.0, 999.0])
    monkeypatch.setattr(t, "_now_mono", lambda: next(ticks))
    plan["resp"] = FakeResp(chunks=True)
    with pytest.raises(t.DeadlineExceeded):
        t.fetch_source("BBC World", t.build_trial_opener())
    monkeypatch.setattr(t, "_now_mono", __import__("time").monotonic)
    plan["resp"] = FakeResp(RSS_OK, headers={"Content-Encoding": "gzip"})
    with pytest.raises(t.EncodingRefused):
        t.fetch_source("BBC World", t.build_trial_opener())
    with pytest.raises(t.DtdRefused):
        t.parse_items(b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><rss/>')
    with pytest.raises(t.ItemLimit):
        t.parse_items(b"<rss>" + b"<item><title>a</title><link>b</link></item>" * 5 + b"</rss>", max_items=3)


# ---------- MF4：時間窗與時間種類 ----------
def test_mf4_window_edges_no_future_grace():
    def v(sec):
        return t.aggregate({"A": [("x", "https://a/1", (NOW + dt.timedelta(seconds=sec)).strftime("%a, %d %b %Y %H:%M:%S +0000"), "published")]}, NOW)["valid"]
    assert v(-72 * 3600) == 1 and v(-72 * 3600 - 1) == 0
    assert v(0) == 1 and v(1) == 0 and v(300) == 0


def test_mf4_overflow_goes_unknown_and_other_rows_survive():
    per = {"A": [("t", "https://a/1", "Fri, 31 Dec 9999 23:00:00 -0100", "published"),
                 ("t2", "https://a/2", h(1), "published")]}
    s = t.aggregate(per, NOW)
    assert s["unknown_date"]["overflow"] == 1 and s["valid"] == 1


def test_mf4_unknown_buckets_and_atom_updated_only():
    assert t.parse_time("")[1] == "empty" and t.parse_time("garbage")[1] == "unparsable"
    assert t.parse_time("2026-11-23T10:00:00")[1] == "no_tz"
    assert t.parse_time("Mon, 23 Nov 2026 10:00:00 -0000")[1] == "no_tz"
    d, w = t.parse_time("Mon, 23 Nov 2026 20:00:00 +0800")
    assert w == "ok" and d.hour == 12
    atom = (b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>T</title><link href="https://u/1"/>'
            b"<updated>2026-11-23T10:00:00Z</updated></entry></feed>")
    items = t.parse_items(atom)
    assert items[0][3] == "updated_only"
    s = t.aggregate({"A": items}, NOW)
    assert s["valid"] == 0 and s["unknown_date"]["updated_only"] == 1


def test_parse_items_rss_drops_summary():
    rss = b"<rss><channel><item><title>T</title><link>http://u</link><description>SECRET</description><pubDate>Mon, 23 Nov 2026 10:00:00 GMT</pubDate></item></channel></rss>"
    assert t.parse_items(rss) == [("T", "http://u", "Mon, 23 Nov 2026 10:00:00 GMT", "published")]


# ---------- MF5：去重與空／失敗／HOLD ----------
def test_mf5_dedup_keeps_identifying_query_and_strips_tracking():
    def n(urls):
        return t.aggregate({"A": [(f"t{i}", u, h(1), "published") for i, u in enumerate(urls)]}, NOW)
    s = n(["https://a/p?id=1", "https://a/p?id=2"]); assert s["valid"] == 2 and s["dedup"] == 0
    s = n(["https://a/p?id=1&utm_source=x", "https://a/p?id=1&fbclid=z#frag"]); assert s["valid"] == 1 and s["dedup"] == 1
    s = n(["https://a/P", "https://a/p"]); assert s["valid"] == 2           # path 大小寫不合併
    s = n(["https://a/p?b=2&a=1", "https://a/p?a=1&b=2"]); assert s["valid"] == 1


def test_mf5_buckets_and_hold_verdicts():
    per = {"A": [], "B": "URLError", "C": [("x", "https://c/1", h(1), "published")]}
    s = t.aggregate(per, NOW)
    assert s["sources"] == {"A": "ok_empty_feed", "B": "fetch_failed:URLError", "C": "ok:1"}
    assert t.verdict(s, 0).startswith("HOLD:no_terms")
    assert t.verdict(t.aggregate({"B": "URLError"}, NOW), 1).startswith("HOLD:no_valid_source")
    assert t.verdict(s, 3).startswith("HOLD:insufficient_sample")
    big = {"A": [(f"x{i}", f"https://a/{i}", h(1), "published") for i in range(t.MIN_SAMPLE)]}
    assert t.verdict(t.aggregate(big, NOW), 1).startswith("SAMPLE_SIZE_OK")
    assert "沒有新聞" not in t.verdict(s, 3).replace("不代表沒有新聞", "")


# ---------- 無落地／無洩漏（成功與錯誤路徑，實跑 main） ----------
def _no_disk(monkeypatch):
    def deny(*a, **k):
        raise AssertionError("disk I/O attempted")
    monkeypatch.setattr(builtins, "open", deny)
    monkeypatch.setattr(os, "open", deny)


def test_no_persistence_no_leak_success_and_error(monkeypatch, capsys, transport):
    calls, plan = transport
    s_title, s_url = "T" + uuid.uuid4().hex, "https://leak.invalid/" + uuid.uuid4().hex
    body = (f"<rss><channel><item><title>{s_title}</title><link>{s_url}</link>"
            f"<pubDate>{h(1)}</pubDate></item></channel></rss>").encode()
    _no_disk(monkeypatch)
    plan["resp"] = FakeResp(body)
    t.main(["--terms-ok", "BBC World"])
    out = capsys.readouterr()
    assert s_title not in out.out + out.err and s_url not in out.out + out.err and "ok:1" in out.out
    # 錯誤路徑：例外訊息帶機敏字串，只許出現類型名
    secret = uuid.uuid4().hex

    def boom(*a, **k):
        raise urllib.error.URLError(f"https://{secret}.invalid/{s_title}")
    monkeypatch.setattr(urllib.request.HTTPSHandler, "do_open", boom)
    t.main(["--terms-ok", "BBC World,Unknown Name"])
    out = capsys.readouterr()
    assert secret not in out.out + out.err and s_title not in out.out + out.err
    assert "fetch_failed:URLError" in out.out and "terms_names_unknown = 1" in out.out
    assert "HOLD:no_valid_source_response" in out.out


def test_terms_gate_zero_requests(transport, capsys):
    calls, plan = transport
    t.main([])
    assert calls == [] and "HOLD:no_terms_confirmed_source" in capsys.readouterr().out
    t.main(["--terms-ok", "Nope"])
    assert calls == []


def test_no_forbidden_imports_or_flags():
    src = open(t.__file__, encoding="utf-8").read()
    for bad in ("import requests", "streamlit", "from services", "from ui_v3", "from repositories", "verify=False"):
        assert bad not in src.split('"""', 2)[2]
