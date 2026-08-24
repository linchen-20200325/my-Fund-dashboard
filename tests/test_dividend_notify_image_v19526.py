"""v19.526:配息月曆推播接線 —— 圖檔優先 + 三段降級(圖 → Flex → 純文字)。

user 2026-08-24 要 LINE 收到「截 App 那張」月曆圖。推播鏈有三個會壞的地方:
產圖(Chromium/中文字型)、發佈(GITHUB_TOKEN / workflow 權限)、LINE 推圖(公開網址)。
§1 核心:**任一段壞掉都必須退回 Flex/純文字,提醒照樣送達** —— 靜默失敗會讓人以為
「這個月沒配息」。本測把整條降級鏈鎖住(零網路,全部注入假物件)。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from scripts import dividend_calendar_notify as M  # noqa: E402

_URL = "https://raw.githubusercontent.com/o/r/deadbeef/dividend-calendar/2026-09.png"
_PNG = b"\x89PNG\r\n\x1a\n" + b"z" * 500


@pytest.fixture
def wired(monkeypatch):
    """把取數段(Sheets/MoneyDJ)換成假資料,只留推播鏈受測。回傳呼叫紀錄。"""
    import scripts.weekly_switch_notify as W
    monkeypatch.setattr(W, "_load_client_and_sheet", lambda: ("c", "s"))
    monkeypatch.setattr(W, "_read_holdings", lambda c, s: ["AAA"])
    monkeypatch.setattr(W, "_read_watchlist", lambda: [])
    # 配息史須「接到現在為止」,否則推下個月時會被判為已越過目標月/疑停配 → 0 事件。
    # 故以實際 TW 當月為錨,往回產 12 個月的月配紀錄。
    import datetime as _dt
    _now = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8)))
    _hist = []
    _y, _m = _now.year, _now.month
    for _ in range(12):
        _hist.append({"ex_date": f"{_y}-{_m:02d}-14"})
        _m -= 1
        if _m == 0:
            _m, _y = 12, _y - 1
    monkeypatch.setattr(M, "_fetch_divs", lambda codes: [
        {"code": "AAA", "name": "安聯測試", "house": "安聯",
         "dividends": list(reversed(_hist))}])
    calls: dict = {"image": [], "flex": [], "text": []}
    import infra.line_push as LP

    def _img(url, preview=None, *, caption=None, **k):
        calls["image"].append({"url": url, "caption": caption})
        return {"sent": True, "dry_run": False, "status": 200, "reason": "ok"}

    def _flex(contents, alt, **k):
        calls["flex"].append(alt)
        return {"sent": True, "dry_run": False, "status": 200, "reason": "ok"}

    def _text(text, **k):
        calls["text"].append(text)
        return {"sent": True, "dry_run": False, "status": 200, "reason": "ok"}
    monkeypatch.setattr(LP, "push_image", _img)
    monkeypatch.setattr(LP, "push_flex", _flex)
    monkeypatch.setattr(LP, "push_text", _text)
    return calls


def _ok_render(monkeypatch):
    import ui.helpers.dividend_calendar_render as R
    monkeypatch.setattr(R, "render_month_calendar_png", lambda cal, **k: _PNG)


def _ok_publish(monkeypatch, url=_URL):
    import infra.asset_publish as AP
    monkeypatch.setattr(AP, "publish_asset", lambda data, path, **k: url)


# ── 快樂路徑:圖檔 + caption 文字,不動 Flex/文字 ────────────────────────────
def test_happy_path_pushes_image_with_caption(monkeypatch, wired):
    _ok_render(monkeypatch)
    _ok_publish(monkeypatch)
    assert M.main([]) == 0
    assert len(wired["image"]) == 1 and not wired["flex"] and not wired["text"]
    _sent = wired["image"][0]
    assert _sent["url"] == _URL
    assert "除息行事曆" in _sent["caption"]            # 圖下方文字清單一起送
    assert "營業日左右" in _sent["caption"]


def test_published_path_is_year_month_scoped(monkeypatch, wired):
    _ok_render(monkeypatch)
    seen = {}
    import infra.asset_publish as AP

    def _pub(data, path, **k):
        seen["path"], seen["bytes"] = path, data
        return _URL
    monkeypatch.setattr(AP, "publish_asset", _pub)
    assert M.main([]) == 0
    # 檔名帶「目標月」(=下個月)→ 每月一張、不互相覆蓋,舊訊息的圖不會被蓋掉
    import datetime as _dt
    _now = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8)))
    _ny, _nm = (_now.year + 1, 1) if _now.month == 12 else (_now.year, _now.month + 1)
    assert seen["path"] == f"dividend-calendar/{_ny}-{_nm:02d}.png"
    assert seen["bytes"] == _PNG


# ── §1 降級鏈:每一段壞掉都要退到 Flex,不可靜默不送 ────────────────────────
def test_render_failure_falls_back_to_flex(monkeypatch, wired):
    import ui.helpers.dividend_calendar_render as R

    def _boom(cal, **k):
        raise RuntimeError("no chromium")
    monkeypatch.setattr(R, "render_month_calendar_png", _boom)
    _ok_publish(monkeypatch)
    assert M.main([]) == 0
    assert not wired["image"] and len(wired["flex"]) == 1      # 產圖失敗 → Flex 仍送達


def test_publish_failure_falls_back_to_flex(monkeypatch, wired):
    _ok_render(monkeypatch)
    import infra.asset_publish as AP
    from infra.asset_publish import AssetPublishError

    def _boom(data, path, **k):
        raise AssetPublishError("403 forbidden")
    monkeypatch.setattr(AP, "publish_asset", _boom)
    assert M.main([]) == 0
    assert not wired["image"] and len(wired["flex"]) == 1      # 發佈失敗 → Flex 仍送達


def test_line_image_rejection_falls_back_to_flex(monkeypatch, wired):
    _ok_render(monkeypatch)
    _ok_publish(monkeypatch)
    import infra.line_push as LP
    from infra.line_push import LinePushError

    def _boom(url, preview=None, *, caption=None, **k):
        raise LinePushError("400 invalid image url")
    monkeypatch.setattr(LP, "push_image", _boom)
    assert M.main([]) == 0
    assert len(wired["flex"]) == 1                             # LINE 退圖 → Flex 仍送達


def test_image_not_sent_reason_falls_back_to_flex(monkeypatch, wired):
    # push_image 回 sent=False(如缺憑證)而非 raise → 也要退 Flex,不可當成功
    _ok_render(monkeypatch)
    _ok_publish(monkeypatch)
    import infra.line_push as LP
    monkeypatch.setattr(LP, "push_image", lambda *a, **k: {
        "sent": False, "dry_run": False, "status": None, "reason": "缺 LINE_USER_ID"})
    assert M.main([]) == 0
    assert len(wired["flex"]) == 1


def test_full_ladder_image_then_flex_then_text(monkeypatch, wired):
    # 圖 + Flex 都壞 → 最後純文字仍送達(§1 提醒不可消失)
    import infra.line_push as LP
    import ui.helpers.dividend_calendar_render as R
    from infra.line_push import LinePushError

    def _no_img(cal, **k):
        raise RuntimeError("no chromium")
    monkeypatch.setattr(R, "render_month_calendar_png", _no_img)

    def _bad_flex(contents, alt, **k):
        raise LinePushError("bad flex")
    monkeypatch.setattr(LP, "push_flex", _bad_flex)
    assert M.main([]) == 0
    assert len(wired["text"]) == 1 and "除息行事曆" in wired["text"][0]


def test_flex_sent_false_falls_through_to_text(monkeypatch, wired):
    """稽核 MEDIUM-LOW-5:Flex 回 sent=False(不 raise)也必須退純文字。

    只接 exception 會讓 sent=False 直接落到 return 1 —— 明明手上有現成 text 卻不送,提醒消失(§1)。
    """
    import infra.line_push as LP
    import ui.helpers.dividend_calendar_render as R

    def _no_img(cal, **k):
        raise RuntimeError("no chromium")
    monkeypatch.setattr(R, "render_month_calendar_png", _no_img)
    monkeypatch.setattr(LP, "push_flex", lambda *a, **k: {
        "sent": False, "dry_run": False, "status": None, "reason": "空 Flex 內容,未送"})
    assert M.main([]) == 0
    assert len(wired["text"]) == 1                     # 沒 raise,但仍退到純文字送達


def test_render_png_signature_accepts_scale():
    """簽名鎖:1MB 保護會呼叫 `render_month_calendar_png(cal, scale=1)`。

    若日後改名/改順序,`_render_and_publish` 的 `except Exception` 會把 TypeError 吞掉 →
    每個月都靜默退 Flex,而 user 只看得到「沒有圖」,看不到 stderr。故直接鎖真實簽名。
    """
    import inspect

    from ui.helpers.dividend_calendar_render import render_month_calendar_png
    _sig = inspect.signature(render_month_calendar_png)
    assert "scale" in _sig.parameters
    _p = _sig.parameters["scale"]
    assert _p.kind is inspect.Parameter.KEYWORD_ONLY and _p.default == 2
    _sig.bind(object(), scale=1)                       # 真的綁得起來才算數


# ── LINE preview ≤1MB:超標自動降 scale,再超標就退 Flex(不推會被 LINE 退的圖)──────
def test_oversize_png_retried_at_scale1(monkeypatch, wired):
    _ok_publish(monkeypatch)
    import ui.helpers.dividend_calendar_render as R
    seen = []

    def _render(cal, **k):
        seen.append(k.get("scale"))
        return b"\x89PNG\r\n\x1a\n" + b"z" * (2_000_000 if k.get("scale") is None else 100)
    monkeypatch.setattr(R, "render_month_calendar_png", _render)
    assert M.main([]) == 0
    assert seen == [None, 1]                       # 先預設(retina),超標 → 重畫 scale=1
    assert len(wired["image"]) == 1                # 縮圖後可推


def test_still_oversize_falls_back_to_flex(monkeypatch, wired):
    _ok_publish(monkeypatch)
    import ui.helpers.dividend_calendar_render as R
    monkeypatch.setattr(R, "render_month_calendar_png",
                        lambda cal, **k: b"\x89PNG\r\n\x1a\n" + b"z" * 2_000_000)
    assert M.main([]) == 0
    assert not wired["image"] and len(wired["flex"]) == 1   # 縮不下來 → 退 Flex


# ── dry-run:完全不產圖、不發佈、不推播 ─────────────────────────────────────
def test_dry_run_publishes_nothing(monkeypatch, wired, capsys):
    import infra.asset_publish as AP
    import ui.helpers.dividend_calendar_render as R

    def _should_not_run(*a, **k):
        raise AssertionError("dry-run 不應產圖/發佈")
    monkeypatch.setattr(R, "render_month_calendar_png", _should_not_run)
    monkeypatch.setattr(AP, "publish_asset", _should_not_run)
    assert M.main(["--dry-run"]) == 0
    assert not wired["image"] and not wired["flex"] and not wired["text"]
