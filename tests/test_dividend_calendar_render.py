"""除息月曆 HTML 渲染(ui/helpers/dividend_calendar_render,v19.443)。

守:產出含關鍵資料(代號/所屬/除息日/入帳/信心)、排除區、免責聲明、深淺色 token 齊備、
空月誠實、HTML 標籤成對(粗略)。純字串,無 streamlit。
"""
from __future__ import annotations

import datetime as _dt

from services.dividend_calendar import build_month_calendar, detect_house
from ui.helpers.dividend_calendar_render import render_month_calendar_html


def _divs(day, n=12, pay_gap=30, amount=0.05):
    y, m, out = 2025, 8, []
    for _ in range(n):
        ex = _dt.date(y, m, day)
        out.append({"ex_date": ex.isoformat(),
                    "pay_date": (ex + _dt.timedelta(days=pay_gap)).isoformat(),
                    "amount": amount, "yield_pct": 6.0})
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def _cal():
    funds = [
        {"code": "TLZF9", "name": "安聯收益成長", "dividends": _divs(14)},
        {"code": "ACDD01", "name": "安聯台灣大壩累積", "dividends": []},
    ]
    for f in funds:
        f["house"] = detect_house(f["name"])
    return build_month_calendar(funds, 2026, 8)


def test_render_contains_key_data():
    html = render_month_calendar_html(_cal())
    assert "TLZF9" in html and "安聯收益成長" in html
    assert "民國115年 8月（2026）" in html
    assert "8/14" in html or ">14<" in html          # 除息日出現(明細或格子)
    assert "6.0%" in html                            # 年化配息
    assert "已排除" in html and "ACDD01" in html      # 排除區
    assert "配息入帳日為除息日後一個月內" in html      # 免責聲明


def test_render_theme_tokens_present():
    html = render_month_calendar_html(_cal())
    assert 'data-theme="dark"' in html               # 深色 token 區塊
    assert "prefers-color-scheme:dark" in html
    assert "background:var(--bg)" in html             # body 用 token 上底色


def test_render_empty_month_is_honest():
    html = render_month_calendar_html(build_month_calendar([], 2026, 8))
    assert "無推估除息日" in html


def test_render_shows_unpredictable_bucket():
    """稽核 M3:節奏不規則的基金揭露在『無法推估』區,不靜默消失。"""
    funds = [{"code": "IRR", "name": "不規則配息",
              "dividends": [{"ex_date": d} for d in ("2025-01-10", "2025-02-20", "2025-06-05")]}]
    html = render_month_calendar_html(build_month_calendar(funds, 2026, 8))
    assert "無法推估" in html and "IRR" in html


def test_render_balanced_containers():
    html = render_month_calendar_html(_cal())
    for tag in ("div", "table", "tbody"):
        assert html.count(f"<{tag}") == html.count(f"</{tag}>"), f"{tag} 標籤未成對"


# ── 格子 chip 只顯示投信名(user 2026-08-24:「只保留投資商的名稱,移除代碼」)──────────
def test_grid_chip_shows_house_only_code_stays_in_table():
    from ui.helpers.dividend_calendar_render import _chip_label
    html = render_month_calendar_html(_cal())
    _grid = html.split('<h2 class="section-t">')[0]      # 月曆格子區(明細表之前)
    assert "安聯" in _grid                                # 格子仍標投信
    assert "TLZF9" not in _grid                           # 格子不再出現代號
    assert "TLZF9" in html                                # 代號仍在下方明細表(可查)
    assert _chip_label({"house": "安聯", "code": "TLZF9"}) == "安聯"


def test_chip_label_falls_back_to_code_when_house_unknown():
    # §1:判不出投信 → 退顯示代號,不可留空白 chip 把當日除息藏掉
    from ui.helpers.dividend_calendar_render import _chip_label
    assert _chip_label({"house": "", "code": "XYZ9"}) == "XYZ9"
    assert _chip_label({"house": None, "code": "XYZ9"}) == "XYZ9"
    assert _chip_label({"house": "", "code": ""}) == "—"   # 兩者皆空 → 退位符,仍看得到有事件


def test_unknown_house_fund_still_visible_in_grid():
    funds = [{"code": "NOHOUSE1", "name": "某某不知名基金", "dividends": _divs(14)}]
    for f in funds:
        f["house"] = detect_house(f["name"])              # → ""(判不出)
    html = render_month_calendar_html(build_month_calendar(funds, 2026, 8))
    _grid = html.split('<h2 class="section-t">')[0]
    assert "NOHOUSE1" in _grid                            # 判不出投信 → 格子退顯示代號(不消失)


# ── render_month_calendar_png(截 App 那張 HTML → PNG;user 2026-08-24)──────────
def test_png_render_module_does_not_eager_load_playwright():
    # App 只取 HTML 時不應載入 playwright(lazy import;否則 Streamlit Cloud 平白扛重依賴)。
    # 用乾淨子行程判定:import 渲染模組後 playwright 不應在 sys.modules。
    import subprocess
    import sys
    from pathlib import Path
    _root = Path(__file__).resolve().parents[1]
    _code = ("import sys; import ui.helpers.dividend_calendar_render as R; "
             "print('playwright' in sys.modules)")
    out = subprocess.run([sys.executable, "-c", _code], capture_output=True, text=True,
                         cwd=str(_root))
    assert out.stdout.strip() == "False", (out.stdout, out.stderr)


def test_png_render_produces_valid_png_or_skips():
    import pytest
    from ui.helpers.dividend_calendar_render import render_month_calendar_png
    try:
        from infra.html_to_png import HtmlRenderError
    except Exception:  # noqa: BLE001
        pytest.skip("infra.html_to_png 不可用")
    try:
        png = render_month_calendar_png(_cal())
    except HtmlRenderError as e:                       # Chromium/playwright 缺 → skip(CI 安全)
        pytest.skip(f"Chromium/playwright 不可用,跳過真截圖:{e}")
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 2000   # 合法 PNG、非空白
