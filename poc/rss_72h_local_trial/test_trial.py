"""離線測試：全部為合成輸入／mock，**不含真新聞、不發任何網路請求**；不得冒充真 RSS 測試。
MF1 代理 / MF2 HTTPS+3xx / MF3 bytes+時限 / MF4 時間窗 / MF5 去重與 HOLD，並含無落地／無洩漏負控。
"""
import builtins
import multiprocessing
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


@pytest.fixture(autouse=True)
def _fork_children(monkeypatch):
    if "fork" not in multiprocessing.get_all_start_methods():
        pytest.skip("需要 fork 以讓子行程繼承 mock transport（僅測試用；正式於 Windows 用 spawn）")
    monkeypatch.setattr(t, "_MP_METHOD", "fork")


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
    t._fetch_core("BBC World", t.build_trial_opener(), t._now_mono())
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
    t._fetch_core("BBC World", t.build_trial_opener(), t._now_mono())
    assert calls[-1][0] == HOST and not called                            # Windows registry 路徑（getproxies）未被呼叫


# ---------- MF2：僅 pinned HTTPS；3xx 立停 ----------
@pytest.mark.parametrize("loc", ["https://evil.example/x", "http://evil.example/x", "/relative"])
def test_mf2_any_3xx_stops_without_second_request(transport, loc):
    calls, plan = transport
    plan["resp"] = FakeResp(b"", code=302, headers={"Location": loc})
    with pytest.raises(t.RedirectRefused):
        t._fetch_core("BBC World", t.build_trial_opener(), t._now_mono())
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
        t.fetch_source("NotInList")


# ---------- MF3：實際讀取上限／時限／編碼／DTD ----------
def test_mf3_infinite_body_stops_near_cap(transport):
    calls, plan = transport
    plan["resp"] = FakeResp(chunks=True)
    with pytest.raises(t.TooLarge):
        t._fetch_core("BBC World", t.build_trial_opener(), t._now_mono())
    assert plan["resp"].served <= t.MAX_BYTES + t.CHUNK and plan["resp"].closed


def test_mf3_lying_small_content_length_still_capped(transport):
    calls, plan = transport
    plan["resp"] = FakeResp(chunks=True, headers={"Content-Length": "10"})
    with pytest.raises(t.TooLarge):
        t._fetch_core("BBC World", t.build_trial_opener(), t._now_mono())
    assert plan["resp"].served <= t.MAX_BYTES + t.CHUNK


def test_mf3_declared_huge_length_rejected_before_read(transport):
    calls, plan = transport
    plan["resp"] = FakeResp(RSS_OK, headers={"Content-Length": str(t.MAX_BYTES + 1)})
    with pytest.raises(t.TooLarge):
        t._fetch_core("BBC World", t.build_trial_opener(), t._now_mono())
    assert plan["resp"].served == 0


def test_mf3_deadline_and_encoding_and_dtd(monkeypatch, transport):
    calls, plan = transport
    ticks = iter([0.0, 0.0, 999.0, 999.0, 999.0])
    monkeypatch.setattr(t, "_now_mono", lambda: next(ticks))
    plan["resp"] = FakeResp(chunks=True)
    with pytest.raises(t.DeadlineExceeded):
        t._fetch_core("BBC World", t.build_trial_opener(), t._now_mono())
    monkeypatch.setattr(t, "_now_mono", __import__("time").monotonic)
    plan["resp"] = FakeResp(RSS_OK, headers={"Content-Encoding": "gzip"})
    with pytest.raises(t.EncodingRefused):
        t._fetch_core("BBC World", t.build_trial_opener(), t._now_mono())
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
    """禁止任何磁碟開檔；唯一例外是 /dev/null（multiprocessing 子行程啟動自身會開它，非資料落地）。"""
    real_open, real_os_open = builtins.open, os.open

    def guard(real):
        def deny(path, *a, **k):
            if isinstance(path, int) or str(path) == os.devnull:   # fd 包裝（multiprocessing 內部）與 /dev/null 不算資料落地
                return real(path, *a, **k)
            raise AssertionError("disk I/O attempted")
        return deny
    monkeypatch.setattr(builtins, "open", guard(real_open))
    monkeypatch.setattr(os, "open", guard(real_os_open))


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
        t.fetch_source("BBC World")
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
        t._fetch_core("BBC World", t.build_trial_opener(), t._now_mono())
    # 解析之後超時也拒（假 parse 推進時鐘）
    clock["v"] = 0.0
    plan["resp"] = FakeResp(RSS_OK)
    real = t.parse_items
    monkeypatch.setattr(t, "parse_items", lambda b, *a, **k: (clock.__setitem__("v", 99.0), real(b))[1])
    with pytest.raises(t.DeadlineExceeded):
        t._fetch_core("BBC World", t.build_trial_opener(), t._now_mono())


def test_c1_actual_bytes_strictly_capped(transport):
    calls, plan = transport
    plan["resp"] = FakeResp(chunks=True, headers={"Content-Length": "10"})
    with pytest.raises(t.TooLarge):
        t._fetch_core("BBC World", t.build_trial_opener(), t._now_mono())
    assert plan["resp"].served <= t.MAX_BYTES + 1          # 嚴格封頂，不再多讀一整個 chunk


@pytest.mark.parametrize("code", [206, 204, 201, 200])
def test_c1_only_plain_200_is_complete_success(transport, code):
    calls, plan = transport
    plan["resp"] = FakeResp(RSS_OK, code=code)
    if code == 200:
        assert len(t._fetch_core("BBC World", t.build_trial_opener(), t._now_mono())) == 3     # 正例
    else:
        with pytest.raises(t.PartialRefused):
            t._fetch_core("BBC World", t.build_trial_opener(), t._now_mono())


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
    b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/"><channel/></rdf:RDF>',
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


# =====================  第三輪 C1–C3（Work #7103693395 MF3）  =====================
import io
import multiprocessing


class _BlockingRaw(io.RawIOBase):
    """read 持有 BufferedReader 內部鎖並阻塞——重現 Work 的反例（同步 close 需同一把鎖）。"""
    def __init__(self, gate):
        self.gate = gate

    def readable(self):
        return True

    def readinto(self, b):
        self.gate.wait(30)
        return 0


class BufferedBlockingResp(FakeResp):
    def __init__(self, gate):
        super().__init__(b"")
        self.br = io.BufferedReader(_BlockingRaw(gate))

    def read(self, n=-1):
        return self.br.read(n)

    def close(self):
        self.br.close()          # 與阻塞中的 read 搶同一把鎖 → 同步 close 也會被卡住


def test_c3_1_blocking_bufferedreader_timeout_path_is_bounded(monkeypatch, transport):
    calls, plan = transport
    gate = threading.Event()
    plan["resp"] = BufferedBlockingResp(gate)
    monkeypatch.setattr(t, "TOTAL_DEADLINE", 0.3)
    t0 = _time.monotonic()
    try:
        with pytest.raises(t.DeadlineExceeded):
            t.fetch_source("BBC World")
        assert _time.monotonic() - t0 < 1.5, "timeout 返回路徑必須有界（Work 反例：被 close 鎖住）"
    finally:
        gate.set()


# ---------- 第三輪 C1：進程隔離——timeout 返回路徑與資源生命週期皆有界 ----------
def test_c3r_1_child_process_killed_and_reaped_after_timeout(monkeypatch, transport):
    calls, plan = transport
    gate = threading.Event()
    plan["resp"] = BufferedBlockingResp(gate)
    monkeypatch.setattr(t, "TOTAL_DEADLINE", 0.3)
    t0 = _time.monotonic()
    with pytest.raises(t.DeadlineExceeded):
        t.fetch_source("BBC World")
    assert _time.monotonic() - t0 < t.TOTAL_DEADLINE + t.KILL_JOIN_SECONDS + 0.5      # 返回路徑有界
    p = t._LAST_PROC
    assert p is not None and not p.is_alive() and p.exitcode is not None            # 子行程已被殺且回收（無殘留）
    gate.set()


def test_c3r_1_spawn_context_is_default_off_linux_and_success_roundtrip(transport):
    calls, plan = transport
    plan["resp"] = FakeResp(RSS_OK)
    items = t.fetch_source("BBC World")                                            # 正例：子行程成功往返
    assert len(items) == 3 and t._LAST_PROC.exitcode == 0


def test_c3r_1_child_error_only_class_name_crosses_pipe(monkeypatch, transport):
    calls, plan = transport
    secret = uuid.uuid4().hex

    def boom(self, *a, **k):
        raise urllib.error.URLError(f"https://{secret}.invalid/x")
    monkeypatch.setattr(urllib.request.HTTPSHandler, "do_open", boom)
    with pytest.raises(Exception) as ei:
        t.fetch_source("BBC World")
    assert type(ei.value).__name__ == "URLError" and secret not in repr(ei.value) and secret not in str(ei.value)


def test_c3r_1_child_crash_is_classified_not_hung(monkeypatch, transport):
    calls, plan = transport

    def die(self, *a, **k):
        os._exit(3)                                  # 子行程直接死亡（無回應）
    monkeypatch.setattr(urllib.request.HTTPSHandler, "do_open", die)
    t0 = _time.monotonic()
    with pytest.raises(t.FetchRefused):
        t.fetch_source("BBC World")
    assert _time.monotonic() - t0 < 3


def test_c3r_1_unknown_source_zero_process():
    before = t._LAST_PROC
    with pytest.raises(t.NotPinned):
        t.fetch_source("NotInList")
    assert t._LAST_PROC is before


# ---------- 第三輪 C2：namespace 與必要結構 ----------
ATOM = 'xmlns="http://www.w3.org/2005/Atom"'
RDFNS = 'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/"'
DCNS = 'xmlns:dc="http://purl.org/dc/elements/1.1/"'


def test_c3r_2_valid_formats_positive_with_items():
    rss = f"<rss><channel><item><title>a</title><link>https://x/1</link><pubDate>{h(1)}</pubDate></item></channel></rss>".encode()
    atom = f'<feed {ATOM}><entry><title>a</title><link href="https://x/2"/><published>2026-11-23T10:00:00Z</published></entry></feed>'.encode()
    rdf = (f"<rdf:RDF {RDFNS} {DCNS}><channel><title>c</title></channel>"
           f"<item><title>a</title><link>https://x/3</link><dc:date>2026-11-23T10:00:00Z</dc:date></item></rdf:RDF>").encode()
    assert t.parse_items(rss)[0][:2] == ("a", "https://x/1")
    assert t.parse_items(atom)[0][:3] == ("a", "https://x/2", "2026-11-23T10:00:00Z")
    r = t.parse_items(rdf)
    assert r[0][:3] == ("a", "https://x/3", "2026-11-23T10:00:00Z") and r[0][3] == "published"


@pytest.mark.parametrize("body", [
    b'<feed xmlns="http://example.invalid/not-atom"><entry/></feed>',                    # 非 Atom namespace 的 feed
    b"<feed><entry/></feed>",                                                           # 無 namespace 的 feed
    b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><description/></rdf:RDF>',   # 無 RSS 結構的 RDF
    b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://example.invalid/x"><channel/></rdf:RDF>',  # 錯 namespace 的 channel
    b'<rss xmlns="http://example.invalid/x"><channel/></rss>',                           # 帶 namespace 的 rss
    b"<rss><item/></rss>",                                                              # 無 channel
    b'<x:rss xmlns:x="urn:x"><x:channel/></x:rss>',
])
def test_c3r_2_wrong_namespace_or_structure_is_notafeed_never_ok_empty(body):
    with pytest.raises(t.NotAFeed):
        t.parse_items(body)


def test_c3r_2_items_outside_proper_namespace_not_counted():
    body = f'<feed {ATOM}><x:entry xmlns:x="urn:x"><title>a</title></x:entry></feed>'.encode()
    assert t.parse_items(body) == []                      # 合法 Atom feed，但該元素非 Atom entry → 不計
    body2 = b"<rss><channel><item xmlns='urn:z'><title>a</title><link>https://x/1</link></item></channel></rss>"
    assert t.parse_items(body2) == []


def test_c3r_2_dedup_regression_kept():
    def n(urls):
        return t.aggregate({"A": [(f"t{i}", u, h(1), "published") for i, u in enumerate(urls)]}, NOW)
    assert n(["https://a/p", "https://a/p/"])["valid"] == 2
    assert n(["https://a/p?id=1&id=2", "https://a/p?id=2&id=1"])["valid"] == 2
    assert n(["https://a/p?id=1&utm_x=1#f", "https://a/p?id=1"])["valid"] == 1


# ---------- 第三輪 C3：context 建構不讀 key-log、不改環境、無競態 ----------
def test_c3r_3_factory_never_uses_create_default_context_nor_touches_env(monkeypatch, tmp_path):
    p = tmp_path / "k.log"
    monkeypatch.setenv("SSLKEYLOGFILE", str(p))
    monkeypatch.setattr(ssl, "create_default_context",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("create_default_context 被呼叫")))
    seen = []
    real_pop = os.environ.pop
    monkeypatch.setattr(os.environ, "pop", lambda *a, **k: seen.append(a) or real_pop(*a, **k))
    ctx = t._ssl_ctx()
    assert not seen and os.environ["SSLKEYLOGFILE"] == str(p) and not p.exists() and ctx.keylog_filename is None
    assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname is True
    assert ctx.minimum_version >= ssl.TLSVersion.TLSv1_2


def test_c3r_3_two_contexts_interleaved_no_native_file_side_effect(monkeypatch, tmp_path):
    """Work 反例（確定性重現）：A 暫移環境變數建構中、B 同時進入；A 還原後 B 才呼叫標準工廠 →
    B 讀到還原後的環境，native 層嘗試開檔（父目錄不存在 → FileNotFoundError）。新實作不經標準工廠、不碰環境。"""
    missing = tmp_path / "no_such_dir" / "k.log"
    monkeypatch.setenv("SSLKEYLOGFILE", str(missing))
    real = ssl.create_default_context
    a_inside, b_inside, n = threading.Event(), threading.Event(), [0]
    lock = threading.Lock()
    errs = []

    def instrumented(*a, **k):                        # 舊實作會經過這裡；新實作不會
        with lock:
            n[0] += 1
            me = n[0]
        if me == 1:                                   # A：等 B 進入後才建完（此時環境仍被 A 移除）
            a_inside.set()
            b_inside.wait(2)
            return real(*a, **k)
        b_inside.set()                                # B：等 A 還原環境後才呼叫標準工廠
        for _ in range(200):
            if os.environ.get("SSLKEYLOGFILE"):
                break
            _time.sleep(0.01)
        return real(*a, **k)
    monkeypatch.setattr(ssl, "create_default_context", instrumented)

    def worker(first):
        try:
            if not first:
                a_inside.wait(2)
            t._ssl_ctx()
        except Exception as e:   # noqa: BLE001
            errs.append(type(e).__name__)
    th = [threading.Thread(target=worker, args=(True,)), threading.Thread(target=worker, args=(False,))]
    [x.start() for x in th]; [x.join(8) for x in th]
    assert errs == [] and not missing.parent.exists()
    assert os.environ["SSLKEYLOGFILE"] == str(missing)


def test_c3r_3_negative_control_standard_factory_does_write(monkeypatch, tmp_path):
    p = tmp_path / "ctl.log"
    monkeypatch.setenv("SSLKEYLOGFILE", str(p))
    ssl.create_default_context()
    assert p.exists()                              # 偵測力：標準工廠確實 native 開檔
    p.unlink()
    t._ssl_ctx()
    t.build_trial_opener()
    assert not p.exists()


def test_c3r_3_threads_hammer_no_file_no_error(monkeypatch, tmp_path):
    p = tmp_path / "h.log"
    monkeypatch.setenv("SSLKEYLOGFILE", str(p))
    errs = []

    def run():
        try:
            for _ in range(20):
                t._ssl_ctx()
        except Exception as e:   # noqa: BLE001
            errs.append(type(e).__name__)
    th = [threading.Thread(target=run) for _ in range(4)]
    [x.start() for x in th]; [x.join(20) for x in th]
    assert errs == [] and not p.exists() and os.environ["SSLKEYLOGFILE"] == str(p)
