# -*- coding: utf-8 -*-
"""C-RSS-3DAY-REAL-LOCAL-TRIAL-1：一次性本機 RSS 72h 試點（隔離 poc；不被任何正式模組 import）。

只在記憶體處理 source/title/url/原始時間/取得時刻；只印聚合計數與錯誤類型，
**不印、不寫標題／連結／摘要／XML**；不 import streamlit／services／ui_v3／repositories；
不呼叫 LLM／NAS Proxy／Sheet／Secrets。條款查核為人工前置：未列入 TERMS_OK 的來源一律跳過。
用法：python3 poc/rss_72h_local_trial/trial.py --terms-ok "MarketWatch,BBC World"
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from email.utils import parsedate_to_datetime

FEEDS = {  # 與 repositories/news_repository.py 現列五源相同（不新增來源）
    "MarketWatch": "https://feeds.content.dowjones.io/public/rss/mw_bulletins",
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
    "CNBC Economy": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
    "CNBC Finance": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
    "BBC World": "https://feeds.bbci.co.uk/news/world/rss.xml",
}
WINDOW = dt.timedelta(hours=72)
# 主題關鍵字（規則式、可審；命中只代表「文字層面相關」，不是風險燈號）
TOPICS = {
    "risk": ("crash", "selloff", "sell-off", "default", "bankruptcy", "volatility", "recession", "downgrade", "war", "sanction"),
    "cashflow": ("dividend", "payout", "yield", "interest rate", "rate cut", "rate hike", "coupon", "distribution"),
    "trend": ("rally", "surge", "slump", "record high", "outlook", "forecast", "trend", "inflation", "jobs"),
}
UP = ("rise", "rises", "gain", "gains", "surge", "rally", "jump", "climb")
DOWN = ("fall", "falls", "drop", "drops", "slump", "plunge", "tumble", "slide")


def parse_time(raw):
    """回 (aware UTC datetime | None, reason)。無時區資訊者不猜，記 unknown。"""
    if not raw or not str(raw).strip():
        return None, "empty"
    try:
        d = parsedate_to_datetime(str(raw).strip())
    except (TypeError, ValueError):
        try:
            d = dt.datetime.fromisoformat(str(raw).strip().replace("Z", "+00:00"))
        except ValueError:
            return None, "unparsable"
    if d.tzinfo is None:
        return None, "no_tz"
    return d.astimezone(dt.timezone.utc), "ok"


def parse_items(xml_bytes):
    """RSS/Atom → [(title, url, raw_time)]；只取三個欄位，其餘立即丟棄。"""
    root = ET.fromstring(xml_bytes)
    out = []
    for it in root.iter():
        tag = it.tag.rsplit("}", 1)[-1]
        if tag not in ("item", "entry"):
            continue
        f = {c.tag.rsplit("}", 1)[-1]: c for c in it}
        link = f["link"].text if "link" in f and f["link"].text else (f["link"].get("href") if "link" in f else "")
        t = (f["title"].text or "") if "title" in f else ""
        raw = ""
        for k in ("pubDate", "published", "updated", "date"):
            if k in f and f[k].text:
                raw = f[k].text
                break
        out.append((t.strip(), (link or "").strip(), raw))
    return out


def norm_key(title, url):
    u = re.sub(r"[?#].*$", "", url.lower()).rstrip("/")
    return u or re.sub(r"\W+", " ", title.lower()).strip()


def aggregate(per_source, now):
    """per_source: {src: [(title,url,raw)] | Exception类名str}。回傳只含計數。"""
    stats = {"sources": {}, "dedup": 0, "unknown_date": Counter(), "out_of_window": 0, "valid": 0}
    seen, kept = set(), []
    for src, res in per_source.items():
        if isinstance(res, str):
            stats["sources"][src] = f"fetch_failed:{res}"
            continue
        n = 0
        for title, url, raw in res:
            if not title or not url:
                stats["unknown_date"]["missing_title_or_url"] += 1
                continue
            ts, why = parse_time(raw)
            if ts is None:
                stats["unknown_date"][why] += 1
                continue
            if not (now - WINDOW <= ts <= now + dt.timedelta(minutes=5)):
                stats["out_of_window"] += 1
                continue
            k = norm_key(title, url)
            if k in seen:
                stats["dedup"] += 1
                continue
            seen.add(k)
            kept.append((src, title.lower()))
            n += 1
        stats["sources"][src] = f"ok:{n}"
    stats["valid"] = len(kept)
    topics = Counter()
    pol = {}
    for src, t in kept:
        for name, kws in TOPICS.items():
            if any(w in t for w in kws):
                topics[name] += 1
                p = ("up" if any(re.search(rf"\b{w}\b", t) for w in UP) else "") + (
                    "down" if any(re.search(rf"\b{w}\b", t) for w in DOWN) else "")
                pol.setdefault(name, []).append((src, p))
    stats["topic_hits"] = dict(topics)
    # 反面證據可辨識性：同主題下是否同時有 up 與 down 且來自 ≥2 來源（粗略；不是事件對齊）
    cand = {}
    for name, lst in pol.items():
        ups = {s for s, p in lst if p == "up"}
        downs = {s for s, p in lst if p == "down"}
        cand[name] = bool(ups and downs and len(ups | downs) >= 2)
    stats["opposing_signal_by_topic"] = cand
    stats["event_grouping"] = "not_implemented(無事件群組鍵；同事件支持／反證不可可靠辨識)"
    return stats


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "personal-research-trial/0.1 (single request)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # 單次、不重試、不繞 403
        return r.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--terms-ok", default="", help="已人工查核條款可用的來源，逗號分隔")
    a = ap.parse_args()
    ok = {s.strip() for s in a.terms_ok.split(",") if s.strip()}
    per, skipped = {}, []
    for src, url in FEEDS.items():
        if src not in ok:
            skipped.append(src)
            continue
        try:
            per[src] = parse_items(fetch(url))
        except Exception as e:  # 只記錯誤類型，不記訊息（可能含 URL）
            per[src] = type(e).__name__
    now = dt.datetime.now(dt.timezone.utc)
    st = aggregate(per, now)
    st["skipped_by_terms"] = skipped
    st["run_utc"] = now.isoformat(timespec="minutes")
    for k, v in st.items():
        print(k, "=", dict(v) if isinstance(v, Counter) else v)


if __name__ == "__main__":
    main()
