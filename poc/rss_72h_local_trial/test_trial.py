"""合成輸入測試（不含真新聞；不得冒充真新聞實測）。"""
import datetime as dt, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import trial as t

NOW = dt.datetime(2026, 11, 23, 12, 0, tzinfo=dt.timezone.utc)
def h(n): return (NOW - dt.timedelta(hours=n)).strftime("%a, %d %b %Y %H:%M:%S +0000")

def test_parse_time():
    assert t.parse_time("")[1] == "empty"
    assert t.parse_time("garbage")[1] == "unparsable"
    assert t.parse_time("2026-11-23T10:00:00")[1] == "no_tz"          # 無時區不猜
    d, w = t.parse_time("Mon, 23 Nov 2026 20:00:00 +0800"); assert w == "ok" and d.hour == 12

def test_aggregate_buckets():
    per = {"A": [("x1", "http://a/1", h(1)), ("x1", "http://a/1?utm=2", h(1)),   # 去重
                 ("old", "http://a/2", h(80)), ("nodate", "http://a/3", ""),
                 ("", "", h(1))],
           "B": "URLError", "C": []}
    s = t.aggregate(per, NOW)
    assert s["valid"] == 1 and s["dedup"] == 1 and s["out_of_window"] == 1
    assert s["unknown_date"]["empty"] == 1 and s["unknown_date"]["missing_title_or_url"] == 1
    assert s["sources"]["B"].startswith("fetch_failed") and s["sources"]["C"] == "ok:0"

def test_future_date_rejected():
    s = t.aggregate({"A": [("t", "http://a/9", h(-5))]}, NOW)
    assert s["valid"] == 0 and s["out_of_window"] == 1

def test_parse_items_rss_and_atom_drop_summary():
    rss = b"<rss><channel><item><title>T</title><link>http://u</link><description>SECRET</description><pubDate>Mon, 23 Nov 2026 10:00:00 GMT</pubDate></item></channel></rss>"
    assert t.parse_items(rss) == [("T", "http://u", "Mon, 23 Nov 2026 10:00:00 GMT")]
    atom = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>T</title><link href="http://u"/><updated>2026-11-23T10:00:00Z</updated></entry></feed>'
    assert t.parse_items(atom)[0][1] == "http://u"

def test_no_persistence_and_no_systemic_flag():
    import re
    src = open(t.__file__, encoding="utf-8").read()
    code = src.split("def main")[0]
    assert not re.search(r"(?<![.\w])open\(", code) and ".write(" not in src
    assert "is_systemic" not in src.split('"""', 2)[2]   # docstring 之外不使用排序旗標
