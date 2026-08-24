"""v19.519:配息月曆 LINE Flex 彩色卡片(user 2026-08-24 選 Flex,非產圖託管)。

- infra.line_push.push_flex:複用 text 推播的憑證/POST,訊息型別改 {type:flex};dry-run/缺憑證誠實不送。
- services.dividend_calendar.build_summary_flex:月曆 → Flex bubble(每檔一列除息日 + 信心;到帳改清單
  上方單行,v19.523);純函式、JSON-safe。
"""
from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infra.line_push import push_flex  # noqa: E402
from services.dividend_calendar import (  # noqa: E402
    _PAY_BIZ_DAYS_MAX,
    _PAY_BIZ_DAYS_MIN,
    add_business_days,
    build_summary_flex,
)


class _Resp:
    def __init__(self, status=200):
        self.status_code = status
        self.text = ""


# ── push_flex ─────────────────────────────────────────────────────────────
def test_push_flex_dry_run_not_sent():
    r = push_flex({"type": "bubble"}, "alt", dry_run=True)
    assert r["sent"] is False and r["dry_run"] is True


def test_push_flex_empty_contents_not_sent():
    r = push_flex({}, "alt", token="t", user_id="u")
    assert r["sent"] is False and "空 Flex" in r["reason"]


def test_push_flex_posts_flex_message_shape():
    cap = {}

    def _poster(url, headers=None, json=None, timeout=None):
        cap["url"], cap["json"], cap["headers"] = url, json, headers
        return _Resp(200)
    bubble = {"type": "bubble", "body": {"type": "box", "layout": "vertical",
                                         "contents": [{"type": "text", "text": "x"}]}}
    r = push_flex(bubble, "我的替代文字", token="tok", user_id="U123", _poster=_poster)
    assert r["sent"] is True and r["status"] == 200
    _msg = cap["json"]["messages"][0]
    assert _msg["type"] == "flex" and _msg["altText"] == "我的替代文字"
    assert _msg["contents"]["type"] == "bubble"
    assert cap["json"]["to"] == "U123"
    assert cap["headers"]["Authorization"] == "Bearer tok"
    assert cap["url"].endswith("/v2/bot/message/push")


def test_push_flex_alt_text_truncated_400():
    cap = {}

    def _poster(url, headers=None, json=None, timeout=None):
        cap["json"] = json
        return _Resp(200)
    push_flex({"type": "bubble"}, "長" * 600, token="t", user_id="u", _poster=_poster)
    assert len(cap["json"]["messages"][0]["altText"]) <= 400


def test_push_flex_non2xx_raises():
    from infra.line_push import LinePushError

    def _poster(url, headers=None, json=None, timeout=None):
        return _Resp(400)
    try:
        push_flex({"type": "bubble"}, "alt", token="t", user_id="u", _poster=_poster)
        assert False, "應 raise LinePushError"
    except LinePushError:
        pass


# ── build_summary_flex ────────────────────────────────────────────────────
def _cal(events, y=2026, m=9, exc=0, unp=0):
    return {"year": y, "month": m, "events": events,
            "excluded": [{"code": f"E{i}"} for i in range(exc)],
            "unpredictable": [{"code": f"U{i}"} for i in range(unp)], "counts": {}}


def _ev(code, ex, house="", conf="high"):
    return {"code": code, "name": code, "house": house, "ex_date": ex,
            "pay_date_est": None, "confidence": conf, "last_amount": 0.05, "last_yield": 6.0, "n": 12}


def test_flex_structure_and_json_safe():
    out = build_summary_flex(_cal([_ev("TLZF9", _dt.date(2026, 9, 14), house="安聯")]))
    assert set(out.keys()) == {"contents", "alt_text"}
    b = out["contents"]
    assert b["type"] == "bubble" and "header" in b and "body" in b
    json.dumps(out)                                   # LINE 要求 JSON-safe → 不炸 = 通過


def test_flex_shows_ex_house_month_and_arrival_note():
    ex = _dt.date(2026, 9, 14)
    out = build_summary_flex(_cal([_ev("TLZF9", ex, house="安聯")]))
    txt = json.dumps(out, ensure_ascii=False)
    arr = add_business_days(ex, _PAY_BIZ_DAYS_MIN)
    assert "9/14 除息" in txt                          # 逐檔:除息日 + 名稱(不含到帳日期)
    assert f"{arr.month}/{arr.day} 到帳" not in txt     # user 2026-08-24:不再逐檔列到帳日期
    assert f"+{_PAY_BIZ_DAYS_MIN}~{_PAY_BIZ_DAYS_MAX} 個工作天" in txt   # 到帳改清單上方單行區間
    assert "安聯 TLZF9" in txt                         # house + code
    assert "民國115年9月" in txt                        # 標題目標(下)月
    assert "1 檔" in out["alt_text"]                   # altText 帶檔數


def test_flex_low_confidence_marked():
    out = build_summary_flex(_cal([_ev("X", _dt.date(2026, 9, 3), conf="low")]))
    assert "信心低" in json.dumps(out, ensure_ascii=False)


def test_flex_no_events_honest_and_no_arrival_note():
    out = build_summary_flex(_cal([]))
    txt = json.dumps(out, ensure_ascii=False)
    assert "無推估除息" in txt
    assert "0 檔" in out["alt_text"]
    assert "到帳 ≈" not in txt                          # 無事件 → 不列到帳說明


def test_flex_excluded_unpredictable_notes():
    out = build_summary_flex(_cal([_ev("A", _dt.date(2026, 9, 2))], exc=2, unp=1))
    txt = json.dumps(out, ensure_ascii=False)
    assert "2 檔累積型" in txt and "1 檔節奏不規則" in txt


# ── 稽核修:LINE 拒空字串 text(整則 Flex 400)→ 任何 text 節點皆須非空 ──────────────
def _all_text_nodes(node) -> list:
    out: list = []
    if isinstance(node, dict):
        if node.get("type") == "text":
            out.append(node.get("text"))
        for v in node.values():
            out.extend(_all_text_nodes(v))
    elif isinstance(node, list):
        for v in node:
            out.extend(_all_text_nodes(v))
    return out


def test_flex_no_empty_text_node_even_blank_code_house():
    # code 與 house 皆空 → 名稱退「—」,不得產生空字串 text(否則 LINE 400 → 全推播掛)
    ev = {"code": "", "name": "", "house": "", "ex_date": _dt.date(2026, 9, 4),
          "confidence": "high", "pay_date_est": None}
    out = build_summary_flex(_cal([ev]))
    texts = _all_text_nodes(out["contents"])
    assert texts and all(t and str(t).strip() for t in texts)     # 無空/純空白 text
    assert "—" in "".join(texts)                                  # 名稱退位符


def test_flex_all_text_nonempty_across_shapes():
    evs = [_ev("A", _dt.date(2026, 9, 2)),
           _ev("B", _dt.date(2026, 9, 9), house="安聯", conf="low")]
    for cal in (_cal(evs), _cal([], exc=2, unp=1), _cal(evs, exc=1, unp=2)):
        assert all(t and str(t).strip() for t in _all_text_nodes(build_summary_flex(cal)["contents"]))


def test_flex_caps_rows_and_under_50kb():
    evs = [_ev(f"F{i}", _dt.date(2026, 9, (i % 28) + 1)) for i in range(120)]
    out = build_summary_flex(_cal(evs))
    _wire = json.dumps(out["contents"], ensure_ascii=True)        # requests 送 ensure_ascii=True(CJK→\uXXXX)
    assert len(_wire.encode()) <= 50_000                          # LINE Flex JSON 上限
    assert "另 90 檔" in json.dumps(out["contents"], ensure_ascii=False)   # 120-30 收斂
    # 逐檔列數不超過上限
    _rows = [n for n in out["contents"]["body"]["contents"] if n.get("layout") == "horizontal"]
    assert len(_rows) == 30


def test_push_flex_whitespace_alt_becomes_nonempty():
    cap = {}

    def _poster(url, headers=None, json=None, timeout=None):
        cap["json"] = json
        return _Resp(200)
    push_flex({"type": "bubble"}, "   ", token="t", user_id="u", _poster=_poster)
    assert cap["json"]["messages"][0]["altText"].strip()         # 非空(退「LINE 通知」)


def test_main_falls_back_to_text_when_flex_fails(monkeypatch):
    # Flex 被 LINE 退(400)→ 退回純文字,提醒仍送達(§1 不讓失敗變成「這個月沒配息」的假象)
    import infra.line_push as LP
    import scripts.weekly_switch_notify as W
    from infra.line_push import LinePushError
    from scripts import dividend_calendar_notify as M
    monkeypatch.setattr(W, "_load_client_and_sheet", lambda: ("c", "s"))
    monkeypatch.setattr(W, "_read_holdings", lambda c, s: ["AAA"])
    monkeypatch.setattr(W, "_read_watchlist", lambda: [])
    monkeypatch.setattr(M, "_fetch_divs",
                        lambda codes: [{"code": "AAA", "name": "AAA", "house": "", "dividends": []}])

    def _flex_raise(*a, **k):
        raise LinePushError("bad flex 400")
    _text_calls = []

    def _text_ok(text, **k):
        _text_calls.append(text)
        return {"sent": True, "dry_run": False, "status": 200, "reason": "ok"}
    monkeypatch.setattr(LP, "push_flex", _flex_raise)
    monkeypatch.setattr(LP, "push_text", _text_ok)
    assert M.main([]) == 0 and len(_text_calls) == 1              # flex 失敗 → 純文字送達
