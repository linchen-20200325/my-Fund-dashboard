"""infra/calendar_image.py — 除息行事曆 PNG(格子月曆)。L0 infra(繪圖 I/O)。

user 2026-08-24:LINE 推「格子月曆圖檔」(像 ETF股息助手)。本模組用 **Pillow** 把
`services.dividend_calendar.build_month_calendar` 的月曆結構畫成一張 PNG:7 欄月格 + 每日彩色圓點
(綠=除息日、藍=到帳日推估),回 `bytes`。純繪圖、無網路、無 streamlit。

**字型**:用 Pillow 內建可縮放預設字型(`ImageFont.load_default(size)`)—— 隨 Pillow 一起帶、
不依賴 runner 系統字型、不需內嵌檔案 → 排程可重現。**僅 Latin/數字**(預設字型無中文字符),
故圖面用數字/英文標籤;中文細節(基金公司名/代號/到帳)由呼叫端放「圖下方 caption 文字」,
交給 LINE 用內建中文字型渲染(§設計:圖不內嵌 CJK,最穩)。

§1:資料異常(缺 events / 壞日期)不硬畫假點 —— 缺就不畫,標題仍出、空月顯示 "No estimated ex-dates"。
"""
from __future__ import annotations

import calendar as _cal
import datetime as _dt
import io as _io

from services.dividend_calendar import _PAY_BUSINESS_DAYS, add_business_days

# ── 尺寸 / 色票(淺底圖;LINE 任一主題皆可看)──────────────────────────────
_W = 1080
_PAD = 44
_TITLE_H = 118
_WEEK_H = 58
_LEGEND_H = 78
_ROWS = 6
_CELL_W = (_W - 2 * _PAD) // 7
_CELL_H = 128

_C_BG = (255, 255, 255)
_C_INK = (31, 45, 61)          # 主字
_C_SUB = (136, 150, 166)       # 次要/表頭
_C_GRID = (232, 236, 239)      # 格線
_C_OTHER = (199, 206, 214)     # 非本月日
_C_EX = (46, 125, 91)          # 除息日圓點(綠)
_C_PAY = (43, 108, 176)        # 到帳日圓點(藍)
_C_ACCENT = (46, 125, 91)

_WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def _font(size: int):
    from PIL import ImageFont
    return ImageFont.load_default(size=size)


def _in_month(d, year: int, month: int) -> bool:
    return isinstance(d, _dt.date) and d.year == year and d.month == month


def render_month_calendar_png(cal: dict) -> bytes:
    """月曆結構 → 格子月曆 PNG bytes。純函式,零網路/streamlit。

    綠點 = 該日有基金除息;藍點 = 該日有基金到帳(除息 +N 工作天推估)。跨到本月外的到帳日
    不畫在本格(誠實 —— caption 文字仍列)。空 events → 仍畫空月格 + "No estimated ex-dates"。
    """
    from PIL import Image, ImageDraw

    y = int(cal.get("year") or 0)
    m = int(cal.get("month") or 0)
    events = cal.get("events") or []

    # 收集本月的除息日 / 到帳日(集合,避免重複點)
    _ex_days, _pay_days = set(), set()
    for e in events:
        _ex = e.get("ex_date")
        if _in_month(_ex, y, m):
            _ex_days.add(_ex.day)
        _arr = add_business_days(_ex, _PAY_BUSINESS_DAYS) if isinstance(_ex, _dt.date) else None
        if _in_month(_arr, y, m):
            _pay_days.add(_arr.day)

    _grid_top = _PAD + _TITLE_H + _WEEK_H
    _H = _grid_top + _ROWS * _CELL_H + _LEGEND_H + _PAD
    img = Image.new("RGB", (_W, _H), _C_BG)
    dr = ImageDraw.Draw(img)

    # ── 標題(ROC 年月 + 西元;Latin/數字)──────────────────────────────
    _roc = (y - 1911) if y else "?"
    dr.text((_PAD, _PAD), f"Ex-Dividend Calendar", font=_font(30), fill=_C_SUB)
    dr.text((_PAD, _PAD + 40), f"{y} / {m:02d}", font=_font(52), fill=_C_INK)
    dr.text((_W - _PAD - 210, _PAD + 52), f"ROC {_roc}", font=_font(26), fill=_C_SUB)
    dr.line([(_PAD, _PAD + _TITLE_H - 8), (_W - _PAD, _PAD + _TITLE_H - 8)], fill=_C_GRID, width=2)

    # ── 星期表頭 ──────────────────────────────────────────────────────
    _wf = _font(24)
    for i, wd in enumerate(_WEEKDAYS):
        _cx = _PAD + i * _CELL_W + _CELL_W // 2
        _col = _C_SUB if 0 < i < 6 else _C_ACCENT       # 六日淡綠強調
        _w = dr.textlength(wd, font=_wf)
        dr.text((_cx - _w / 2, _PAD + _TITLE_H + 14), wd, font=_wf, fill=_col)

    # ── 月格 + 圓點 ───────────────────────────────────────────────────
    _weeks = _cal.monthcalendar(y, m) if y and m else []
    _daynum_f = _font(30)
    for r in range(_ROWS):
        for c in range(7):
            _x0 = _PAD + c * _CELL_W
            _y0 = _grid_top + r * _CELL_H
            dr.rectangle([_x0, _y0, _x0 + _CELL_W, _y0 + _CELL_H], outline=_C_GRID, width=1)
            _day = _weeks[r][c] if r < len(_weeks) else 0
            if _day == 0:
                continue
            dr.text((_x0 + 12, _y0 + 8), str(_day), font=_daynum_f, fill=_C_INK)
            # 圓點:除息(綠)在左、到帳(藍)在右;可同時
            _dots = []
            if _day in _ex_days:
                _dots.append(_C_EX)
            if _day in _pay_days:
                _dots.append(_C_PAY)
            _rad, _gap = 11, 30
            _cx0 = _x0 + _CELL_W // 2 - (len(_dots) - 1) * _gap // 2 if _dots else 0
            _cy = _y0 + _CELL_H - 30
            for i, _col in enumerate(_dots):
                _cx = _cx0 + i * _gap
                dr.ellipse([_cx - _rad, _cy - _rad, _cx + _rad, _cy + _rad], fill=_col)

    # ── 圖例 / 空月訊息 ────────────────────────────────────────────────
    _ly = _grid_top + _ROWS * _CELL_H + 20
    _lf = _font(24)
    if events:
        # §圖面純 ASCII(預設字型無中文字符,中文說明由 caption 承載)——避免 tofu 方塊。
        dr.ellipse([_PAD, _ly + 2, _PAD + 20, _ly + 22], fill=_C_EX)
        dr.text((_PAD + 30, _ly), "Ex-date", font=_lf, fill=_C_INK)
        _x2 = _PAD + 210
        dr.ellipse([_x2, _ly + 2, _x2 + 20, _ly + 22], fill=_C_PAY)
        dr.text((_x2 + 30, _ly),
                f"Payout (est. +{_PAY_BUSINESS_DAYS} biz days)", font=_lf, fill=_C_INK)
    else:
        dr.text((_PAD, _ly), "No estimated ex-dates this month.", font=_lf, fill=_C_SUB)

    _buf = _io.BytesIO()
    img.save(_buf, format="PNG", optimize=True)
    return _buf.getvalue()
