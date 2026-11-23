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
        t.parse_items(b"<rss><channel>" + b"<item><title>a</title><link>b</link></item>" * 5 + b"</channel></rss>", max_items=3)


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
    s = n(["https://a/p?b=2&a=1", "https://a/p?a=1&b=2"]); assert s["valid"] == 2   # 第二輪：不再排序，保守不合併


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


# =====================  第二輪 C1–C3（Work #7102770525 MF3）  =====================
import threading
import time as _time


# ---------- C1 ----------
def test_c1_hard_deadline_with_blocking_read(monkeypatch, transport):
    """阻塞中的 read（不回傳）也必須在期限內讓 fetch_source 返回 DeadlineExceeded。"""
    calls, plan = transport
    release = threading.Event()

    class Blocking(FakeResp):
        def read(self, n=-1):
            release.wait(5)          # 模擬卡住的 recv
            return b""
    plan["resp"] = Blocking()
    monkeypatch.setattr(t, "TOTAL_DEADLINE", 0.3)
    t0 = _time.monotonic()
    with pytest.raises(t.DeadlineExceeded):
        t.fetch_source("BBC World", t.build_trial_opener())
    assert _time.monotonic() - t0 < 2.0
    release.set()


def test_c1_deadline_checked_after_last_read_and_after_parse(monkeypatch, transport):
    calls, plan = transport
    clock = {"v": 0.0}
    monkeypatch.setattr(t, "_now_mono", lambda: clock["v"])

    class SlowEOF(FakeResp):
        def read(self, n=-1):
            clock["v"] += 21.0           # 最後一次 read 跨過 20s 才回 EOF
            return b"" if self._body is None else super().read(n)
    r = SlowEOF(RSS_OK)
    r._body = RSS_OK[:0]
    plan["resp"] = r
    with pytest.raises(t.DeadlineExceeded):
        t.fetch_source("BBC World", t.build_trial_opener())
    # 解析之後超時也拒（假 parse 推進時鐘）
    clock["v"] = 0.0
    plan["resp"] = FakeResp(RSS_OK)
    real = t.parse_items
    monkeypatch.setattr(t, "parse_items", lambda b, *a, **k: (clock.__setitem__("v", 99.0), real(b))[1])
    with pytest.raises(t.DeadlineExceeded):
        t.fetch_source("BBC World", t.build_trial_opener())


def test_c1_actual_bytes_strictly_capped(transport):
    calls, plan = transport
    plan["resp"] = FakeResp(chunks=True, headers={"Content-Length": "10"})
    with pytest.raises(t.TooLarge):
        t.fetch_source("BBC World", t.build_trial_opener())
    assert plan["resp"].served <= t.MAX_BYTES + 1          # 嚴格封頂，不再多讀一整個 chunk


@pytest.mark.parametrize("code", [206, 204, 201, 200])
def test_c1_only_plain_200_is_complete_success(transport, code):
    calls, plan = transport
    plan["resp"] = FakeResp(RSS_OK, code=code)
    if code == 200:
        assert len(t.fetch_source("BBC World", t.build_trial_opener())) == 3     # 正例
    else:
        with pytest.raises(t.PartialRefused):
            t.fetch_source("BBC World", t.build_trial_opener())


_DTD = '<?xml version="1.0" encoding="{enc}"?><!DOCTYPE r [<!ENTITY a "b">]><rss><channel/></rss>'


@pytest.mark.parametrize("enc,codec", [("UTF-16", "utf-16"), ("UTF-16LE", "utf-16-le"),
                                       ("UTF-16BE", "utf-16-be"), ("UTF-32", "utf-32")])
def test_c1_non_utf8_encodings_refused_even_with_dtd(enc, codec):
    with pytest.raises(t.FetchRefused):
        t.parse_items(_DTD.format(enc=enc).encode(codec))


def test_c1_utf8_dtd_still_refused_and_clean_utf8_bom_ok():
    with pytest.raises(t.DtdRefused):
        t.parse_items(_DTD.format(enc="UTF-8").encode("utf-8"))
    with pytest.raises(t.DtdRefused):
        t.parse_items(("﻿" + _DTD.format(enc="UTF-8")).encode("utf-8"))
    ok = b"\xef\xbb\xbf" + RSS_OK
    assert len(t.parse_items(ok)) == 3


# ---------- C2 ----------
def test_c2_dedup_keeps_trailing_slash_and_duplicate_query_order():
    def n(urls):
        return t.aggregate({"A": [(f"t{i}", u, h(1), "published") for i, u in enumerate(urls)]}, NOW)
    assert n(["https://a/p", "https://a/p/"])["valid"] == 2                      # 尾斜線有識別力
    assert n(["https://a/p?id=1&id=2", "https://a/p?id=2&id=1"])["valid"] == 2    # 重複 key 值序保留
    assert n(["https://a/p?id=1&id=2", "https://a/p?id=1&id=2&utm_x=1#f"])["valid"] == 1   # 正例：僅追蹤參數／fragment 合併


@pytest.mark.parametrize("body", [b"<html><body/></html>", b"<foo/>", b"<rss/>", b"<feed-x/>"])
def test_c2_non_feed_structure_is_error_not_empty(body):
    with pytest.raises(t.NotAFeed):
        t.parse_items(body)


@pytest.mark.parametrize("body", [
    b"<rss><channel><title>x</title></channel></rss>",
    b'<feed xmlns="http://www.w3.org/2005/Atom"><title>x</title></feed>',
    b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"/>',
])
def test_c2_legit_empty_feeds_are_ok_empty(body):
    assert t.parse_items(body) == []
    assert t.aggregate({"A": t.parse_items(body)}, NOW)["sources"]["A"] == "ok_empty_feed"


# ---------- C3 ----------
def test_c3_malformed_url_no_leak_no_escape(capsys):
    sentinel = uuid.uuid4().hex
    per = {"A": [("t", f"http://[{sentinel}", h(1), "published"), ("ok", "https://a/ok", h(1), "published")]}
    s = t.aggregate(per, NOW)                      # 不得拋出
    assert s["valid"] == 1 and s["unknown_date"]["malformed_url"] == 1
    assert sentinel not in repr(s)


def test_c3_malformed_url_through_main_prints_only_class(monkeypatch, capsys, transport):
    calls, plan = transport
    sentinel = uuid.uuid4().hex
    body = (f"<rss><channel><item><title>x</title><link>http://[{sentinel}</link><pubDate>{h(1)}</pubDate></item>"
            "</channel></rss>").encode()
    plan["resp"] = FakeResp(body)
    t.main(["--terms-ok", "BBC World"])
    out = capsys.readouterr()
    assert sentinel not in out.out + out.err


def test_c3_unexpected_exception_in_run_does_not_escape_or_leak(monkeypatch, capsys):
    sentinel = uuid.uuid4().hex
    monkeypatch.setattr(t, "run", lambda *a, **k: (_ for _ in ()).throw(ValueError(sentinel)))
    with pytest.raises(SystemExit):
        t.main(["--terms-ok", "BBC World"])
    out = capsys.readouterr()
    assert sentinel not in out.out + out.err and "ValueError" in out.out + out.err


def test_c3_sslkeylogfile_never_writes(monkeypatch, tmp_path):
    p = tmp_path / "keys.log"
    monkeypatch.setenv("SSLKEYLOGFILE", str(p))
    # 負控：未防護的標準 context 會建檔（證明偵測力）
    ssl.create_default_context()
    assert p.exists()
    p.unlink()
    ctx = t._ssl_ctx()
    t.build_trial_opener()
    assert not p.exists() and ctx.keylog_filename is None
    assert os.environ.get("SSLKEYLOGFILE") == str(p)          # 不永久改動呼叫者環境
