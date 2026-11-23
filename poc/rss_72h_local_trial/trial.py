# -*- coding: utf-8 -*-
"""C-RSS-3DAY-REAL-LOCAL-TRIAL-1（MF1-5 修補版）：一次性本機 RSS 72h 試點（隔離 poc；不被任何正式模組 import）。

只在記憶體處理 source/title/url/原始時間/取得時刻；只印聚合計數與錯誤「類型名」，
**不印、不寫標題／連結／摘要／XML／例外訊息**；不 import streamlit／services／ui_v3／repositories；
不呼叫 LLM／NAS Proxy／Sheet／Secrets。條款查核為人工前置：未列入 --terms-ok 的來源一律跳過。
連線：試點專用 opener——顯式 ProxyHandler({})（不讀環境變數、不讀 Windows 系統代理）、
僅 HTTPS 且 CERT_REQUIRED＋hostname 驗證、任何 3xx 立即停止（不跟轉）、零重試、有 bytes／時間上限。
用法：python3 poc/rss_72h_local_trial/trial.py --terms-ok "MarketWatch,BBC World"
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlsplit

FEEDS = {  # 與 repositories/news_repository.py 現列五源相同（不新增來源；只此五個 HTTPS URL 可被請求）
    "MarketWatch": "https://feeds.content.dowjones.io/public/rss/mw_bulletins",
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
    "CNBC Economy": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
    "CNBC Finance": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
    "BBC World": "https://feeds.bbci.co.uk/news/world/rss.xml",
}
WINDOW = dt.timedelta(hours=72)
MAX_BYTES = 2 * 1024 * 1024      # 每來源實際讀入上限（不信任 Content-Length）；PoC 暫定值，未經裁示
CHUNK = 64 * 1024
SOCK_TIMEOUT = 10                # 單次 socket 操作秒數
TOTAL_DEADLINE = 20.0            # 每來源整體秒數（含讀取迴圈）
MAX_ITEMS = 1000                 # 每來源條目上限（超出 fail-closed）
MIN_SAMPLE = 10                  # 有效樣本少於此數 → HOLD（暫定值，未經裁示）
TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ocid", "taid", "igshid", "ref_src"}  # 另加 utm_*
_now_mono = time.monotonic       # 測試可替換

TOPICS = {  # 規則式關鍵字；命中只代表文字層面相關，不是風險燈號
    "risk": ("crash", "selloff", "sell-off", "default", "bankruptcy", "volatility", "recession", "downgrade", "war", "sanction"),
    "cashflow": ("dividend", "payout", "yield", "interest rate", "rate cut", "rate hike", "coupon", "distribution"),
    "trend": ("rally", "surge", "slump", "record high", "outlook", "forecast", "trend", "inflation", "jobs"),
}
UP = ("rise", "rises", "gain", "gains", "surge", "rally", "jump", "climb")
DOWN = ("fall", "falls", "drop", "drops", "slump", "plunge", "tumble", "slide")


class FetchRefused(Exception):
    """試點自訂的安全拒絕（只用類別名回報，不帶任何來源內容）。"""


class RedirectRefused(FetchRefused): ...
class TooLarge(FetchRefused): ...
class DeadlineExceeded(FetchRefused): ...
class EncodingRefused(FetchRefused): ...
class DtdRefused(FetchRefused): ...
class ItemLimit(FetchRefused): ...
class NotPinned(FetchRefused): ...
class PartialRefused(FetchRefused): ...
class NotAFeed(FetchRefused): ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):  # 任何 3xx 立即停止，不產生第二次請求
        raise RedirectRefused()


def _ssl_ctx():
    """CERT_REQUIRED＋hostname 驗證；並**禁止 SSLKEYLOGFILE**（標準 context 會讀環境變數並由 native 層落盤 TLS 金鑰）。"""
    saved = os.environ.pop("SSLKEYLOGFILE", None)
    try:
        ctx = ssl.create_default_context()
    finally:
        if saved is not None:
            os.environ["SSLKEYLOGFILE"] = saved          # 不永久改動呼叫者環境
    ctx.keylog_filename = None
    return ctx


def build_trial_opener():
    """試點專用 opener：不繼承環境／系統代理；只有 https；3xx 拒絕。"""
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),                 # 顯式空：不讀 HTTPS_PROXY／Windows registry
        urllib.request.HTTPSHandler(context=_ssl_ctx()),
        _NoRedirect(),
    )
    opener.handle_open.pop("http", None)                 # 明確移除明文 http 處理器
    opener.addheaders = []
    return opener


def parse_time(raw):
    """回 (aware UTC datetime | None, reason)。無時區／溢位／無法解析 一律 unknown，不猜。"""
    if not raw or not str(raw).strip():
        return None, "empty"
    s = str(raw).strip()
    try:
        d = parsedate_to_datetime(s)
    except (TypeError, ValueError, IndexError):
        try:
            d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None, "unparsable"
    if d.tzinfo is None:
        return None, "no_tz"
    try:
        return d.astimezone(dt.timezone.utc), "ok"
    except (OverflowError, ValueError):
        return None, "overflow"


def _check_encoding_and_dtd(xml_bytes):
    """只接受 ASCII 相容編碼（UTF-8／含 BOM、ASCII、Latin-1 宣告）；UTF-16/32 等一律拒絕，
    使後續以 ASCII 位元組比對 DOCTYPE／ENTITY 不會被編碼繞過。"""
    b = xml_bytes
    if b[:3] == b"\xef\xbb\xbf":
        b = b[3:]
    if b[:2] in (b"\xff\xfe", b"\xfe\xff") or b[:4] in (b"\x00\x00\xfe\xff", b"\xff\xfe\x00\x00") \
            or b"\x00" in b[:8]:
        raise EncodingRefused()
    m = re.match(rb"<\?xml[^>]*?encoding\s*=\s*[\"']([A-Za-z0-9._-]+)[\"']", b[:200])
    if m and m.group(1).lower() not in (b"utf-8", b"utf8", b"us-ascii", b"ascii", b"iso-8859-1", b"latin1", b"latin-1"):
        raise EncodingRefused()
    low = b.lower()
    if b"<!doctype" in low or b"<!entity" in low:
        raise DtdRefused()
    return xml_bytes


def parse_items(xml_bytes, max_items=MAX_ITEMS):
    """RSS/Atom/RDF → [(title, url, raw_time, kind)]；只取四欄，其餘立即丟棄。
    kind='published'（pubDate／published／dc:date）或 'updated_only'（只有 updated，非首次發稿日）。
    根元素非 rss(含 channel)／feed／RDF → NotAFeed（不可當合法空 feed）。"""
    root = ET.fromstring(_check_encoding_and_dtd(xml_bytes))
    rname = root.tag.rsplit("}", 1)[-1]
    if rname == "rss":
        if not any(c.tag.rsplit("}", 1)[-1] == "channel" for c in root):
            raise NotAFeed()
    elif rname not in ("feed", "RDF"):
        raise NotAFeed()
    out = []
    for it in root.iter():
        if it.tag.rsplit("}", 1)[-1] not in ("item", "entry"):
            continue
        if len(out) >= max_items:
            raise ItemLimit()
        f = {c.tag.rsplit("}", 1)[-1]: c for c in it}
        link = ""
        if "link" in f:
            link = f["link"].text or f["link"].get("href") or ""
        t = (f["title"].text or "") if "title" in f else ""
        raw, kind = "", "published"
        for k in ("pubDate", "published", "date"):
            if k in f and f[k].text:
                raw = f[k].text
                break
        else:
            if "updated" in f and f["updated"].text:
                raw, kind = f["updated"].text, "updated_only"
        out.append((t.strip(), link.strip(), raw, kind))
    return out


def norm_key(url):
    """去重鍵：僅去 fragment 與明確追蹤參數；**保留 path（含尾斜線、大小寫）與 query 的原順序／重複 key**。"""
    p = urlsplit(url.strip())
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
         if not k.lower().startswith("utm_") and k.lower() not in TRACKING_PARAMS]
    return f"{p.scheme.lower()}://{p.netloc.lower()}{p.path}?{urlencode(q)}"


def aggregate(per_source, now):
    """per_source: {src: [(title,url,raw,kind)] | 錯誤類型名 str}。回傳只含計數。"""
    stats = {"sources": {}, "dedup": 0, "unknown_date": Counter(), "out_of_window": 0, "valid": 0}
    seen, kept = set(), []
    for src, res in per_source.items():
        if isinstance(res, str):
            stats["sources"][src] = f"fetch_failed:{res}"
            continue
        if not res:
            stats["sources"][src] = "ok_empty_feed"      # 合法空列表；≠ 沒有新聞，只是此刻此來源 0 條
            continue
        n = 0
        for title, url, raw, kind in res:
            if not title or not url:
                stats["unknown_date"]["missing_title_or_url"] += 1
                continue
            if kind == "updated_only":                   # updated 不是首次發稿日 → fail-closed
                stats["unknown_date"]["updated_only"] += 1
                continue
            ts, why = parse_time(raw)
            if ts is None:
                stats["unknown_date"][why] += 1
                continue
            if not (now - WINDOW <= ts <= now):          # 嚴格：now-72h ≤ t ≤ now（無未來寬限）
                stats["out_of_window"] += 1
                continue
            try:
                k = norm_key(url)
            except ValueError:                           # 畸形 URL：只分桶，不帶任何原文
                stats["unknown_date"]["malformed_url"] += 1
                continue
            if k in seen:
                stats["dedup"] += 1
                continue
            seen.add(k)
            kept.append((src, title.lower()))
            n += 1
        stats["sources"][src] = f"ok:{n}"
    stats["valid"] = len(kept)
    topics, pol = Counter(), {}
    for src, t in kept:
        for name, kws in TOPICS.items():
            if any(w in t for w in kws):
                topics[name] += 1
                p = ("up" if any(re.search(rf"\b{w}\b", t) for w in UP) else "") + (
                    "down" if any(re.search(rf"\b{w}\b", t) for w in DOWN) else "")
                pol.setdefault(name, []).append((src, p))
    stats["topic_hits"] = dict(topics)
    stats["opposing_signal_by_topic"] = {
        n: bool({s for s, p in l if p == "up"} and {s for s, p in l if p == "down"}
                and len({s for s, _ in l}) >= 2) for n, l in pol.items()}
    stats["event_grouping"] = "not_implemented(無事件群組鍵；同事件支持／反證不可可靠辨識)"
    return stats


def verdict(stats, n_terms_ok):
    """明確 HOLD／樣本不足表達；絕不輸出「沒有新聞」。"""
    ok_sources = [s for s, v in stats["sources"].items() if v.startswith("ok")]
    if n_terms_ok == 0:
        return "HOLD:no_terms_confirmed_source"
    if not ok_sources:
        return "HOLD:no_valid_source_response"
    if stats["valid"] < MIN_SAMPLE:
        return f"HOLD:insufficient_sample(valid={stats['valid']}<{MIN_SAMPLE}; 不代表沒有新聞)"
    return "SAMPLE_SIZE_OK(僅樣本量；不代表可用性／預測力)"


def _fetch_core(src, opener, t0, holder):
    url = FEEDS.get(src)
    if not url or not url.startswith("https://"):
        raise NotPinned()
    req = urllib.request.Request(url, headers={
        "User-Agent": "personal-research-trial/0.3 (single request)", "Accept-Encoding": "identity"})
    try:
        resp = opener.open(req, timeout=SOCK_TIMEOUT)
    except urllib.error.HTTPError as e:
        if 300 <= e.code < 400:
            raise RedirectRefused() from None
        raise
    holder["resp"] = resp
    try:
        status = getattr(resp, "status", None) or resp.getcode()
        if 300 <= status < 400:
            raise RedirectRefused()
        if status != 200:                                  # 206／204／201… 皆非完整成功
            raise PartialRefused()
        enc = (resp.headers.get("Content-Encoding") or "identity").lower()
        if enc not in ("", "identity"):
            raise EncodingRefused()
        cl = resp.headers.get("Content-Length")
        if cl and cl.isdigit() and int(cl) > MAX_BYTES:    # 只做早退；不信任，下面仍按實際讀入量計
            raise TooLarge()
        buf = bytearray()
        while True:
            if _now_mono() - t0 > TOTAL_DEADLINE:
                raise DeadlineExceeded()
            want = min(CHUNK, MAX_BYTES + 1 - len(buf))    # 實際讀入量嚴格 ≤ MAX_BYTES+1
            chunk = resp.read(want)
            if _now_mono() - t0 > TOTAL_DEADLINE:          # 最後一次 read（含 EOF）之後也檢查
                raise DeadlineExceeded()
            if not chunk:
                break
            buf += chunk
            if len(buf) > MAX_BYTES:
                raise TooLarge()
    finally:
        try:
            resp.close()
        except Exception:
            pass
    items = parse_items(bytes(buf))
    if _now_mono() - t0 > TOTAL_DEADLINE:                  # 解析之後
        raise DeadlineExceeded()
    return items


def fetch_source(src, opener):
    """單次、不重試；URL 只能取自 FEEDS（pinned HTTPS）。
    硬期限：核心在 daemon 工作緒執行，呼叫端 join(TOTAL_DEADLINE)；阻塞中的 read 也無法讓呼叫端超時。
    （被放棄的工作緒仍受 socket 逾時與 MAX_BYTES 限制，且只持有記憶體內暫存。）"""
    holder, box = {}, {}
    t0 = _now_mono()

    def work():
        try:
            box["ok"] = _fetch_core(src, opener, t0, holder)
        except BaseException as e:   # noqa: BLE001 — 轉交呼叫端，只用類型
            box["err"] = e
    th = threading.Thread(target=work, daemon=True)
    th.start()
    th.join(TOTAL_DEADLINE)
    if th.is_alive():
        r = holder.get("resp")
        if r is not None:
            try:
                r.close()
            except Exception:
                pass
        raise DeadlineExceeded()
    if "err" in box:
        raise box["err"]
    return box["ok"]


def run(terms_ok, opener, now):
    per, skipped = {}, []
    for src in FEEDS:
        if src not in terms_ok:
            skipped.append(src)
            continue
        try:
            per[src] = fetch_source(src, opener)
        except Exception as e:  # 只記錯誤類型名，不記訊息（可能含 URL／內容）
            per[src] = type(e).__name__
    st = aggregate(per, now)
    st["skipped_terms_unconfirmed"] = skipped
    st["terms_names_unknown"] = len([s for s in terms_ok if s not in FEEDS])
    st["verdict"] = verdict(st, len([s for s in terms_ok if s in FEEDS]))
    st["run_utc"] = now.isoformat(timespec="minutes")
    return st


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--terms-ok", default="", help="已人工查核條款可用的來源，逗號分隔")
    a = ap.parse_args(argv)
    ok = {s.strip() for s in a.terms_ok.split(",") if s.strip()}
    try:
        st = run(ok, build_trial_opener(), dt.datetime.now(dt.timezone.utc))
    except Exception as e:  # 任何未預期例外：只印類型名，不印訊息（可能含 URL／netloc）
        print("run_failed =", type(e).__name__)
        sys.exit(2)
    for k, v in st.items():
        print(k, "=", dict(v) if isinstance(v, Counter) else v)


if __name__ == "__main__":
    main()
