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
    assert "安聯" in html                             # 投信名(user 2026-08-24:改只顯示投信)
    assert "民國115年 8月（2026）" in html
    assert "8/14" in html or ">14<" in html          # 除息日出現(明細或格子)
    assert "已排除" in html and "ACDD01" in html      # 排除區(仍列代號,否則不知排除了誰)
    assert "配息入帳日為除息日後一個月內" in html      # 免責聲明


def test_removed_columns_gone():
    """user 2026-08-24:代號 / 上次配息(單位) / 年化配息 三者從明細表移除。

    年化配息移除同時解掉一個真 bug —— 該欄吃 `last_yield` 原始值,FundClear/Cnyes 來源常被
    上游 `or 0` 變成 0.0 而顯示「0.0%」(§1 捏造);正確年化率在 `_resolve_adr_with_fallback`。
    """
    html = render_month_calendar_html(_cal())
    assert "年化配息" not in html                     # 整欄移除(含表頭)
    assert "上次配息" not in html                     # 每單位配息金額(無幣別標示)整欄移除
    assert "所屬" not in html                         # 與基金欄同值 → 合併,不重複
    assert "TLZF9" not in html                        # 明細表不再出現代號
    assert "6.0%" not in html and "0.0500" not in html


def test_footer_note_wording(_=None):
    """user 2026-08-24 指定備註原文(基金公司公開說明書口徑)—— 逐句鎖住不被改寫。"""
    html = render_month_calendar_html(_cal())
    for _line in ("上述基金基準日皆以實際基金營業日為準。",
                  "依公開說明書規定，",
                  "入帳時間將依實際作業為準。",
                  "本行事曆所示之營業日僅供參考，實際之基金營業日請參閱"):
        assert _line in html, f"備註缺句:{_line}"
    assert "※ 日期為推估：" in html                   # §1:仍須聲明日期為推估、非官方公告
    assert "非官方公告" in html


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
def test_grid_chip_shows_house_only():
    from ui.helpers.dividend_calendar_render import _chip_label
    html = render_month_calendar_html(_cal())
    _grid = html.split('<h2 class="section-t">')[0]      # 月曆格子區(明細表之前)
    assert "安聯" in _grid                                # 格子標投信
    assert "TLZF9" not in _grid                           # 格子不出現代號
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


# ── 同日同投信合併(user 2026-08-24「移除重複」)──────────────────────────────
def test_same_house_same_day_merged_with_count():
    from ui.helpers.dividend_calendar_render import _dedupe_day_chips
    evs = [{"house": "安聯", "code": "TLZF9", "confidence": "high"},
           {"house": "安聯", "code": "TLZM7", "confidence": "high"}]
    out = _dedupe_day_chips(evs)
    assert len(out) == 1                              # 兩檔安聯 → 併成一個 chip
    assert out[0]["label"] == "安聯" and out[0]["n"] == 2      # ×2 標明有兩檔(不丟資訊)


def test_merge_keeps_low_confidence_flag():
    # 任一檔信心低 → 合併後仍標低信心(不因合併洗掉)
    from ui.helpers.dividend_calendar_render import _dedupe_day_chips
    out = _dedupe_day_chips([{"house": "安聯", "code": "A", "confidence": "high"},
                             {"house": "安聯", "code": "B", "confidence": "low"}])
    assert len(out) == 1 and out[0]["low"] is True


def test_different_houses_not_merged():
    from ui.helpers.dividend_calendar_render import _dedupe_day_chips
    out = _dedupe_day_chips([{"house": "安聯", "code": "A", "confidence": "high"},
                             {"house": "摩根", "code": "B", "confidence": "high"}])
    assert [c["label"] for c in out] == ["安聯", "摩根"]        # 不同投信不合併、保序
    assert all(c["n"] == 1 for c in out)


def test_unknown_house_funds_not_merged_together():
    # 兩檔都判不出投信 → label 退代碼(各自不同)→ 不可被誤併成一個
    from ui.helpers.dividend_calendar_render import _dedupe_day_chips
    out = _dedupe_day_chips([{"house": "", "code": "AAA", "confidence": "high"},
                             {"house": "", "code": "BBB", "confidence": "high"}])
    assert len(out) == 2 and {c["label"] for c in out} == {"AAA", "BBB"}


def test_grid_renders_merged_chip_once():
    funds = [{"code": "TLZF9", "name": "安聯收益成長", "dividends": _divs(14)},
             {"code": "TLZM7", "name": "安聯美國短年期債券", "dividends": _divs(14)}]
    for f in funds:
        f["house"] = detect_house(f["name"])
    html = render_month_calendar_html(build_month_calendar(funds, 2026, 8))
    _grid = html.split('<h2 class="section-t">')[0]
    assert _grid.count("安聯") == 2                    # 圖例 1 + 格子 1(不再重複兩個格子 chip)
    assert "×2" in _grid                               # 標明當日有兩檔(不丟資訊)
    assert html.count("<tr>") >= 2                     # 明細表仍逐檔各一列(只是不顯示代號)


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
