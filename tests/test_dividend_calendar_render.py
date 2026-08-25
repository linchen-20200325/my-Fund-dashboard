"""除息月曆 HTML 渲染(ui/helpers/dividend_calendar_render,v19.443;v19.530 修訂)。

守:產出含關鍵資料(投信/除息基準日/入帳/信心)、排除區、免責聲明、深淺色 token 齊備、
空月誠實、HTML 標籤成對(粗略)、**§13.8 UI 用詞 drift-lock**。純字串,無 streamlit。

⚠️ **v19.530 fixture 通則**:合成配息日一律先套營業日校正(`roll_to_business_day`)——
真實基金不會把除息基準日訂在週六或國定假日,而錨定引擎(規格 §2)是拿「投影後套 R 的值」
去比對歷史的。字面日號寫死的舊 fixture(14 號 12 筆裡有 5 筆是週末)在現實中不存在,
復現率必然 < 0.80 → 引擎依 §3 誠實棄權 → 月曆整個空掉,測到的不是渲染而是壞 fixture。
"""
from __future__ import annotations

import datetime as _dt

from services.dividend_calendar import build_month_calendar, detect_house, roll_to_business_day
from ui.helpers.dividend_calendar_render import render_month_calendar_html


def _divs(day, n=12, pay_gap=30, amount=0.05):
    """n 筆月配紀錄(基準日錨在 day 號,落非營業日則校正 → 見檔頭通則)。"""
    y, m, out = 2025, 8, []
    for _ in range(n):
        ex = roll_to_business_day(_dt.date(y, m, day))
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
    assert "配息入帳日為除息日後一個月內" in html      # 免責聲明


def test_no_dividend_section_removed():
    """user 2026-08-24「沒有配息的整段移除」:累積型/查無配息基金不再佔版面。

    ⚠️ `unpredictable`(有配息史但本月推不出)必須**保留** —— 語意是「可能有配息但算不出來」,
    靜默吃掉會讓人誤判當月無事(§1);見 test_render_shows_unpredictable_bucket。
    """
    html = render_month_calendar_html(_cal())
    assert "已排除" not in html
    assert "無月配息" not in html
    assert "ACDD01" not in html                       # 該累積型基金整段不再出現


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
    """空月要誠實說「推不出」(§1),且用詞跟著 §0 改口徑為「除息**基準日**」。"""
    html = render_month_calendar_html(build_month_calendar([], 2026, 8))
    assert "無推估除息基準日" in html


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


# ── §13.8 UI 用詞 drift-lock:全站一律「除息基準日」(user 2026-08-25 指定)────────────
def test_ex_record_date_wording_locked_in_four_places():
    """§0 + §13.8:推估目標量改成**除息基準日**,四個 UI 露出點的用詞一起鎖住。

    **為什麼要鎖**:MoneyDJ 配息表三欄是三個**不同**的日期 ——
      col[0] 配息基準日(基金公司照名冊那天,本引擎的目標量)
      col[1] 除息日    (基準日 +1~2 個營業日)
      col[2] 發放日
    v19.529 以前錨在 col[1],5 檔真實資料 walk-forward 命中率僅 52%;v19.530 §0 改錨 col[0]。
    若畫面繼續寫「除息日」,user 會拿推估值去對基金公司公告的**另一個**日期,
    差 1~2 個營業日卻找不出原因 —— 那是 §1 意義下的誤導(數字沒錯,但講的不是同一件事)。
    用詞漂回去不會讓任何測試變紅,所以必須有這條 drift-lock 明著守。

    四處 = 副標 / 明細區塊標題 / 明細表頭 / 空月文案(見 `render_month_calendar_html`)。
    """
    html = render_month_calendar_html(_cal())
    # 1) header 副標
    assert '<p class="sub">依你的基金過往配息節奏，推估本月除息基準日與配息入帳日。' in html
    # 2) 明細區塊標題
    assert '<h2 class="section-t">本月除息基準日明細（推估）</h2>' in html
    # 3) 明細表頭第一欄
    assert '<th>除息基準日</th>' in html
    # 4) 空月文案(需要一份沒有事件的月曆才會渲染出來)
    _empty = render_month_calendar_html(build_month_calendar([], 2026, 8))
    assert '本月你的基金無推估除息基準日（或資料不足）。' in _empty


def test_ex_record_date_wording_has_no_bare_ex_date_label():
    """反向:四處露出點不得退回**裸的**「除息日」標籤(§13.8 的另一半)。

    只驗「標籤位置」,不禁止全篇出現「除息日」三個字 —— footer 的公開說明書原文
    「配息入帳日為除息日後一個月內」是 user 2026-08-24 指定的**引文**,那是基金公司的
    口徑不是我們的欄位名,不可連坐改掉(改了會變成竄改公開說明書用語)。
    """
    html = render_month_calendar_html(_cal())
    assert "<th>除息日</th>" not in html
    assert "本月除息日明細" not in html
    assert "推估本月除息日與配息入帳日" not in html
    for _h in (html, render_month_calendar_html(build_month_calendar([], 2026, 8))):
        assert "無推估除息日（或資料不足）" not in _h
    # footer 的公開說明書引文必須原封不動留著(證明上面鎖的是欄位名,不是全域禁詞)
    assert "配息入帳日為除息日後一個月內" in html


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
def test_same_house_same_day_merged():
    from ui.helpers.dividend_calendar_render import _dedupe_day_chips
    evs = [{"house": "安聯", "code": "TLZF9", "confidence": "high"},
           {"house": "安聯", "code": "TLZM7", "confidence": "high"}]
    out = _dedupe_day_chips(evs)
    assert len(out) == 1 and out[0]["label"] == "安聯"        # 兩檔安聯 → 併成一個 chip(無 ×N)


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
    assert "×2" not in _grid                           # user 2026-08-24:×N 也移除
    assert html.count("<tr>") >= 2                     # 明細表仍逐檔各一列 → 兩檔都沒被藏掉


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


# ── 推播圖 compact 版型(user 2026-08-24「字體太小,版面集中一點」)────────────────
def test_compact_css_only_when_requested():
    plain = render_month_calendar_html(_cal())
    comp = render_month_calendar_html(_cal(), compact=True)
    assert "min-width:0" not in plain and "min-width:680px" in plain   # App 版不變
    assert "min-width:0" in comp                                      # 推播版解除最小寬


def test_compact_enlarges_text_and_tightens_layout():
    comp = render_month_calendar_html(_cal(), compact=True)
    for rule in ("table{min-width:0;font-size:16px}",   # 表格字 14 → 16
                 ".d{font-size:15px}",                  # 日期數字 14 → 15
                 ".chip{font-size:13px",                # 格子內投信名 12 → 13
                 ".cell{min-height:72px",               # 格高 92 → 72(收緊)
                 ".wrap{max-width:100%;padding:18px 16px}"):
        assert rule in comp, f"compact 缺規則:{rule}"


def test_push_width_narrower_than_app():
    # 手機上字的視覺大小 = 字級 ÷ 圖寬 → 圖畫窄才是放大字的主要手段
    from ui.helpers.dividend_calendar_render import _PUSH_WIDTH
    assert _PUSH_WIDTH < 820 and _PUSH_WIDTH >= 480   # 太窄會擠壞 7 欄格子


def test_png_uses_compact_and_requires_cjk():
    # drift-lock:推播圖必須套 compact 版型 + 開中文字型探針(缺字型寧可退 Flex)
    import inspect
    from ui.helpers import dividend_calendar_render as R
    src = inspect.getsource(R.render_month_calendar_png)
    assert "compact=True" in src
    assert "require_cjk=True" in src
