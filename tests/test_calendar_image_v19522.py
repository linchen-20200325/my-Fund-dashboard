"""v19.522:格子月曆 PNG 繪圖(infra.calendar_image,PNG 推播 PR2/4)。

user 2026-08-24 選真圖檔:Pillow 畫 7 欄月格 + 彩色圓點(綠=除息日、藍=到帳日)。純繪圖、零網路。
圖面純 ASCII(Pillow 內建字型無 CJK,中文由 caption 承載);本測守:輸出為合法 PNG、尺寸穩定、
壞資料不炸(§1 不畫假點)。
"""
from __future__ import annotations

import datetime as _dt
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infra.calendar_image import render_month_calendar_png  # noqa: E402

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _ev(code, day, house="", conf="high"):
    return {"code": code, "name": code, "house": house,
            "ex_date": _dt.date(2026, 9, day), "confidence": conf}


def _cal(events, y=2026, m=9, exc=0):
    return {"year": y, "month": m, "events": events,
            "excluded": [{"code": f"E{i}"} for i in range(exc)],
            "unpredictable": [], "counts": {}}


def _png_ok(b) -> bool:
    return isinstance(b, bytes) and b[:8] == _PNG_MAGIC and len(b) > 1000


def test_renders_valid_png():
    b = render_month_calendar_png(_cal([_ev("ACCP138", 2), _ev("TLZF9", 15)]))
    assert _png_ok(b)


def test_opens_with_pillow_expected_size():
    from PIL import Image
    b = render_month_calendar_png(_cal([_ev("A", 2)]))
    im = Image.open(io.BytesIO(b))
    assert im.format == "PNG" and im.width == 1080 and im.height > 900


def test_empty_events_still_valid_png():
    b = render_month_calendar_png(_cal([]))
    assert _png_ok(b)                                  # 空月仍畫格 + "No estimated ex-dates"


def test_malformed_ex_date_no_crash():
    # ex_date=None / 非日期 → 不畫點、不炸(§1 不硬給假日期)
    cal = _cal([{"code": "X", "name": "X", "ex_date": None, "confidence": "high"},
                {"code": "Y", "name": "Y", "ex_date": "notadate", "confidence": "high"}])
    assert _png_ok(render_month_calendar_png(cal))


def test_dimensions_stable_across_event_counts():
    # 尺寸只依月份格數(6 列),與事件多寡無關 → 可重現
    from PIL import Image
    _s1 = Image.open(io.BytesIO(render_month_calendar_png(_cal([_ev("A", 2)])))).size
    _s2 = Image.open(io.BytesIO(render_month_calendar_png(
        _cal([_ev(f"F{i}", (i % 28) + 1) for i in range(20)])))).size
    assert _s1 == _s2


def test_arrival_spilling_next_month_no_crash():
    # 9/30 除息 → 到帳落 10 月(本格不畫)——不炸,仍出圖
    b = render_month_calendar_png(_cal([_ev("LATE", 30)]))
    assert _png_ok(b)


def test_deterministic_same_input():
    cal = _cal([_ev("A", 2), _ev("B", 9)])
    assert render_month_calendar_png(cal) == render_month_calendar_png(cal)   # 同輸入同輸出(可重現 §5)
