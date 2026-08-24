"""v19.521:infra.line_push.push_image —— LINE 圖片訊息(+ 選填 caption 文字)。

格子月曆 PNG 推播 PR1(user 2026-08-24 選真圖檔)。LINE 圖片訊息要求 originalContentUrl/
previewImageUrl 皆為公開 HTTPS 網址(不能夾 bytes);push_image 複用 _post_messages 的憑證/POST/
§1 錯誤處理,與 text/flex 共用同一組 token/userId/端點。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infra.line_push import LinePushError, push_image  # noqa: E402

_URL = "https://raw.githubusercontent.com/o/r/abc123/cal.png"


class _Resp:
    def __init__(self, status=200):
        self.status_code = status
        self.text = ""


def _cap_poster(cap):
    def _p(url, headers=None, json=None, timeout=None):
        cap["url"], cap["json"], cap["headers"] = url, json, headers
        return _Resp(200)
    return _p


def test_dry_run_not_sent():
    r = push_image(_URL, dry_run=True)
    assert r["sent"] is False and r["dry_run"] is True


def test_non_https_rejected():
    r = push_image("http://x/p.png", token="t", user_id="u")
    assert r["sent"] is False and "https" in r["reason"]
    r2 = push_image(_URL, "http://x/prev.png", token="t", user_id="u")   # preview 非 https
    assert r2["sent"] is False


def test_image_payload_shape():
    cap = {}
    r = push_image(_URL, token="tok", user_id="U1", _poster=_cap_poster(cap))
    assert r["sent"] is True and r["status"] == 200
    _msgs = cap["json"]["messages"]
    assert len(_msgs) == 1                                  # 無 caption → 只有圖
    assert _msgs[0]["type"] == "image"
    assert _msgs[0]["originalContentUrl"] == _URL
    assert _msgs[0]["previewImageUrl"] == _URL              # preview 省略 → 用 original
    assert cap["json"]["to"] == "U1"
    assert cap["headers"]["Authorization"] == "Bearer tok"


def test_preview_url_distinct():
    cap = {}
    _p = "https://raw.githubusercontent.com/o/r/abc/prev.png"
    push_image(_URL, _p, token="t", user_id="u", _poster=_cap_poster(cap))
    assert cap["json"]["messages"][0]["previewImageUrl"] == _p


def test_caption_appended_as_text():
    cap = {}
    push_image(_URL, caption="🗓️ 9月除息", token="t", user_id="u", _poster=_cap_poster(cap))
    _msgs = cap["json"]["messages"]
    assert len(_msgs) == 2                                  # 圖 + 文字 caption
    assert _msgs[0]["type"] == "image" and _msgs[1]["type"] == "text"
    assert _msgs[1]["text"] == "🗓️ 9月除息"


def test_caption_truncated():
    cap = {}
    push_image(_URL, caption="長" * 6000, token="t", user_id="u", _poster=_cap_poster(cap))
    assert len(cap["json"]["messages"][1]["text"]) <= 5000


def test_non_2xx_raises():
    def _p(url, headers=None, json=None, timeout=None):
        return _Resp(400)
    try:
        push_image(_URL, token="t", user_id="u", _poster=_p)
        assert False, "應 raise LinePushError"
    except LinePushError:
        pass


def test_missing_creds_short_circuit():
    r = push_image(_URL)                                    # 無 token/uid、非 dry-run
    assert r["sent"] is False and r["dry_run"] is False     # 缺憑證 → 誠實不送(不 raise)
