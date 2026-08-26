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
    """稽核 M3 + §15.4:節奏不規則的基金仍揭露在畫面上,不靜默消失。

    v19.533 改的是**呈現方式**(舊版是頁尾一段「無法推估」灰框,新版是「待確認清單」逐檔一列),
    要守的東西沒變:這檔基金必須看得見,且必須說得出為什麼。
    """
    funds = [{"code": "IRR", "name": "不規則配息",
              "dividends": [{"ex_date": d} for d in ("2025-01-10", "2025-02-20", "2025-06-05")]}]
    html = render_month_calendar_html(build_month_calendar(funds, 2026, 8))
    assert "待確認清單" in html and "IRR" in html
    assert "對不上固定規律" in html                    # §15.3 人話成因,不是靜默消失


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

    ⚠️ **v19.534 追加 7:副標與明細標題的「本月」改成實際目標月**(總管 2026-08-26 實看
    `v533_B_partial_2027-02.png` 後裁示)。cron 每月 1 號推的是**下個月**,而徽章寫的是真正的
    目標月 —— 同一張圖上「本月」與「民國116年 2月」自相矛盾。鎖的重點仍是「除息基準日」
    這五個字連在一起,月份前綴走 `month_label` 這一份 SSOT。

    ⚠️ **v19.533 §15.2 例外:明細表頭改成「預估基準日」**(user 2026-08-26 明確要求
    「預估」二字要出現在**欄頭**,不可只放頁尾免責)。「基準日」三個字仍在,§13.8 要防的
    「被拿去對另一個日期(除息日)」風險不變;另外三處仍寫滿「除息基準日」。
    """
    html = render_month_calendar_html(_cal())
    # 1) header 副標
    assert '<p class="sub">依你的基金過往配息節奏，推估民國115年8月的除息基準日與配息入帳日。' in html
    # 2) 明細區塊標題
    assert '<h2 class="section-t">民國115年8月除息基準日明細（推估）</h2>' in html
    # 追加 7 反向:畫面上不得再出現指涉目標月的「本月」(推播情境會是錯的)
    assert "推估本月" not in html and "本月除息基準日明細" not in html
    # 3) 明細表頭第一欄(§15.2 正名,「預估」必須在欄頭)
    assert '<th>預估基準日</th>' in html
    assert '<th>除息基準日</th>' not in html
    # 4) 空月文案(需要一份沒有事件的月曆才會渲染出來)
    #    ⚠️ v19.535 待辦 3:這句原本寫死「本月」—— 與追加 7 同病(cron 每月 1 號推的是**下個月**),
    #    改成吃徽章同一個月份變數。鎖的重點仍是「除息基準日」五個字,月份前綴走 `month_label`。
    from services.dividend_calendar import empty_month_note
    _empty = render_month_calendar_html(build_month_calendar([], 2026, 8))
    assert empty_month_note(2026, 8) in _empty
    assert '民國115年8月你的基金無推估除息基準日（或資料不足）。' in _empty
    assert '本月你的基金無推估' not in _empty


def test_ex_record_date_wording_has_no_bare_ex_date_label():
    """反向:四處露出點不得退回**裸的**「除息日」標籤(§13.8 的另一半)。

    只驗「標籤位置」,不禁止全篇出現「除息日」三個字 —— footer 的公開說明書原文
    「配息入帳日為除息日後一個月內」是 user 2026-08-24 指定的**引文**,那是基金公司的
    口徑不是我們的欄位名,不可連坐改掉(改了會變成竄改公開說明書用語)。
    """
    html = render_month_calendar_html(_cal())
    assert "<th>除息日</th>" not in html
    assert "除息日明細" not in html                       # v19.534:月份前綴改動後仍守住標籤
    assert "除息日與配息入帳日" not in html
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


def test_merge_drops_low_confidence_display_flag():
    """v19.534 裁示 2:合併後的 chip **不再帶低信心旗標**,格子裡也不再有「?」上標。

    ⚠️ 這是**有意識的政策變更,不是迴歸**。前身 `test_merge_keeps_low_confidence_flag`
    守的是「任一檔信心低 → 合併後仍標低信心(不因合併洗掉)」—— 那個理由當時成立,
    現在被權衡掉,兩邊理由並陳:
      舊(仍成立):合併會洗掉最保守的那一檔,訊號要跟著走最保守值。
      新(勝出,總管 2026-08-26):(a)「?」在整張圖(含圖例、頁尾)**沒有任何一處解釋**;
      (b) 它會與 §15.1 誤差帶**互相矛盾** —— 同一檔可能同時掛「?」(confidence=low)
      與「±0 天」(error_band=0),兩個訊號不同源卻並排。**一個訊號、一個地方**:
      誠實訊號現在是誤差帶,它在明細表(有數字、有頁尾說明、逐檔從自己的歷史算)。
    ⚠️ 引擎的 `confidence` 一個字都沒動 —— 見
    `test_build_month_calendar_carries_error_band_and_keeps_confidence`。
    """
    from ui.helpers.dividend_calendar_render import _dedupe_day_chips
    out = _dedupe_day_chips([{"house": "安聯", "code": "A", "confidence": "high"},
                             {"house": "安聯", "code": "B", "confidence": "low"}])
    assert len(out) == 1
    assert "low" not in out[0], "低信心旗標還在 → 留著就是留一條漂回去的路"


def test_low_confidence_question_mark_gone_from_grid():
    """裁示 2 的畫面側:整張 HTML 不得再出現無人解釋的「?」上標與它的樣式。"""
    funds = [{"code": "A", "name": "安聯甲", "dividends": _divs(14)},
             {"code": "B", "name": "摩根乙", "dividends": _divs(3)}]
    for f in funds:
        f["house"] = detect_house(f["name"])
    html = render_month_calendar_html(build_month_calendar(funds, 2026, 8))
    assert '<span class="q">?</span>' not in html
    assert ".chip .q{" not in html                       # CSS 也一起拿掉,不留半截


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


# ══════════════════════════════════════════════════════════════════════
# §15 顯示層(user 2026-08-26 拍板):誤差欄 / 推不出的基金保留可見 / 全部推不出換版面
#   §13.8:L3 用詞測試歸本檔。引擎的 `confidence` 一個字沒動 —— 改的是「顯示什麼」。
# ══════════════════════════════════════════════════════════════════════
def _divs_ending(day, n, end=(2026, 7), pay_gap=30):
    """n 筆月配紀錄,**最後一筆落在 `end` 月**(避免短歷史 fixture 被判疑停配而整檔消失)。"""
    y, m, out = end[0], end[1], []
    for _ in range(n):
        ex = roll_to_business_day(_dt.date(y, m, day))
        out.append({"ex_date": ex.isoformat(),
                    "pay_date": (ex + _dt.timedelta(days=pay_gap)).isoformat()})
        m -= 1
        if m < 1:
            m, y = 12, y - 1
    return list(reversed(out))


_IRREGULAR = [{"ex_date": d} for d in ("2025-01-10", "2025-02-20", "2025-06-05")]


def _cal_mixed():
    """一檔推得出(安聯)+ 一檔推不出(施羅德)→ §15.3 的主場景。"""
    funds = [{"code": "TLZF9", "name": "安聯收益成長", "dividends": _divs(14)},
             {"code": "SD080", "name": "施羅德環球收益", "dividends": _IRREGULAR}]
    for f in funds:
        f["house"] = detect_house(f["name"])
    return build_month_calendar(funds, 2026, 8)


def _cal_all_unpred():
    """全部推不出 → §15.4 的整組換版面。"""
    funds = [{"code": "SD080", "name": "施羅德環球收益", "dividends": _IRREGULAR},
             {"code": "IRR2", "name": "摩根不規則", "dividends": _IRREGULAR}]
    for f in funds:
        f["house"] = detect_house(f["name"])
    return build_month_calendar(funds, 2026, 8)


# ── §15.2 明細表欄位正名 ──────────────────────────────────────────────
def test_detail_table_headers_renamed():
    """§15.2:「除息」→「預估基準日」、「信心」→「誤差」。

    「預估」二字必須出現在**欄頭**(user 2026-08-26 明確要求)——
    頁尾免責沒人看,欄頭才是 user 讀數字時眼睛所在的位置。
    """
    html = render_month_calendar_html(_cal())
    _head = html.split("<thead>")[1].split("</thead>")[0]
    assert "<th>預估基準日</th>" in _head and "預估" in _head
    assert "<th>誤差</th>" in _head
    assert "<th>信心</th>" not in _head                 # 三級標籤從畫面廢止(引擎內部保留)


def test_confidence_three_level_labels_gone_from_detail_table():
    """§15.1:畫面上不再出現「高 / 中 / 低」三級信心徽章。

    ⚠️ 這條**不是**要引擎停算 confidence —— 它仍是 §3 閘門與 §13.6 硬門檻的依據
    (見 `test_build_month_calendar_carries_error_band_and_keeps_confidence`),
    只是不再直接顯示。user 要的是「哪天該去看帳戶」,「中信心」回答不了。
    """
    html = render_month_calendar_html(_cal())
    _tbl = html.split('<h2 class="section-t">')[1]
    for _cls in ('<span class="cf high">', '<span class="cf med">', '<span class="cf low">'):
        assert _cls not in _tbl


# ── §15.1 誤差欄 ────────────────────────────────────────────────────
def test_error_band_label_cutpoints():
    """§15.1 顯示切點:0 →「±0 天」/ <=2 →「±N 天」/ <=7 →「±1 週」/ >7 或 None →「僅供參考」。"""
    from ui.helpers.dividend_calendar_render import _err_band_label
    assert _err_band_label(0)[0] == "±0 天"
    assert _err_band_label(1)[0] == "±1 天"
    assert _err_band_label(2)[0] == "±2 天"
    assert _err_band_label(3)[0] == "±1 週"
    assert _err_band_label(7)[0] == "±1 週"
    assert _err_band_label(8)[0] == "僅供參考"
    assert _err_band_label(None)[0] == "僅供參考"       # 證據不足 → **不給數字**(§1)


def test_error_band_no_number_when_history_too_short():
    """歷史 < 8 筆但推得出日期 → 日期照給,誤差欄寫「僅供參考」,**不借別檔的準確度**。"""
    funds = [{"code": "NEW1", "name": "安聯新發行", "dividends": _divs_ending(14, 5)}]
    for f in funds:
        f["house"] = detect_house(f["name"])
    cal = build_month_calendar(funds, 2026, 8, ref_year=2026, ref_month=7, ref_day=20)
    assert cal["counts"]["events"] == 1                # 日期仍給(§1 誠實壓低 > 全部隱藏)
    assert cal["events"][0]["error_band"] is None
    html = render_month_calendar_html(cal)
    assert "僅供參考" in html and "±" not in html.split('<h2 class="section-t">')[1]


def test_error_band_shows_plus_minus_zero_for_clean_fund():
    html = render_month_calendar_html(_cal())
    assert "±0 天" in html


# ── §15.3 推不出的基金保留可見 ───────────────────────────────────────
def _grid_only(html: str) -> str:
    """只取月曆格子區(虛線 chip 排與明細表都在它之後)。"""
    return html.split('<div class="grid">')[1].split('<p class="pending-lab">')[0]


def test_unpredictable_fund_keeps_its_legend_colour():
    """§15.3:推不出的基金**圖例永遠保留顏色** —— 原本會整個拿掉,視覺系統斷裂。"""
    html = render_month_calendar_html(_cal_mixed())
    _legend = html.split('<ul class="legend">')[1].split("</ul>")[0]
    assert "施羅德" in _legend and "安聯" in _legend
    from ui.helpers.dividend_calendar_render import _HOUSE_COLOR
    assert _HOUSE_COLOR["施羅德"] in _legend


def test_unpredictable_fund_is_not_placed_in_any_day_cell():
    """§15.3 紅線:**日期格子內不放任何東西** —— 我們確實不知道是哪天,放進格子等於發明位置。

    「直接拿上個月的日期當本月預估」正是本次要修的病(月底型一猜就錯一整輪);
    畫面上顯示的必須是「上次」這個事實,而且不能長在格子裡。
    """
    html = render_month_calendar_html(_cal_mixed())
    assert "施羅德" not in _grid_only(html)
    assert "安聯" in _grid_only(html)                   # 推得出的照樣進格子


def test_unpredictable_fund_shows_dashed_chip_below_grid():
    """§15.3:月曆格**正下方**一排灰虛線 chip,寫「投信名 · 上次 M/D」。

    v19.534 追加 8:上次日期離目標月超過半年 → **帶年份**。本 fixture 的目標月是 2026-08、
    上次是 2025-06-05(差 14 個月),只寫「上次 6/5」會被讀成「兩個月前才配過」——
    `stale` 那類基金正是「上次很久以前」,不帶年份會讓 user 低估陳舊度(§1)。
    """
    html = render_month_calendar_html(_cal_mixed())
    assert '<ul class="pending">' in html
    _chips = html.split('<ul class="pending">')[1].split("</ul>")[0]
    assert "施羅德 · 上次 2025/6/5" in _chips           # 上一次的**實際**基準日(跨年 → 帶年份)
    assert "border:1px dashed" in html                  # 灰虛線:視覺上與「已確定」區隔
    # 位置:虛線 chip 必須在月曆之後、明細表之前
    assert html.index('<div class="grid">') < html.index('<ul class="pending">')
    assert html.index('<ul class="pending">') < html.index('<h2 class="section-t">')


def test_unpredictable_fund_still_has_a_detail_row():
    """§15.3:明細表仍列該檔一行 —— 預估基準日欄寫「—」,誤差欄寫原因人話 + 上次日期。

    追加 9:這個版面**沒有**獨立的「上次實際基準日」欄(日期欄是「—」)→ reason 要補尾巴。
    追加 8:目標月 2026-08 vs 上次 2025-06-05 差 14 個月 → 尾巴帶年份。
    """
    html = render_month_calendar_html(_cal_mixed())
    _body = html.split("<tbody>")[1].split("</tbody>")[0]
    _row = [r for r in _body.split("<tr") if "施羅德" in r]
    assert len(_row) == 1, "推不出的基金在明細表消失了"
    assert ">—<" in _row[0]                             # 預估基準日 / 入帳 皆為 —
    assert "對不上固定規律" in _row[0] and "（上次 2025/6/5）" in _row[0]


def test_reason_tail_is_decided_by_layout_not_by_string_matching():
    """v19.534 追加 9:reason 要不要帶「(上次 X)」由**版面**決定,判斷在 L2。

    前身 `test_detail_row_appends_last_date_when_reason_text_lacks_it` 守的是
    「文案沒帶日期 → L3 補」,方向對但不夠 —— 總管實看 `v533_C_all_unpred` 圖後點名:
    全空版型的三欄表**已有獨立的「上次實際基準日」欄**,reason 再帶一次等於同一列講兩次,
    5 檔同原因時是同一句話複製 5 遍,在 560px 推播圖上佔掉大半版面。
    ⚠️ 紅線:**不可**在 L3 用字串比對去砍尾巴 —— 文案一改比對就悄悄失效。
    """
    from ui.helpers.dividend_calendar_render import _pending_why
    _u = {"reason": "只有 2 筆配息紀錄，還看不出規律（至少要 3 筆）。",
          "reason_code": "too_few", "last_ex": _dt.date(2026, 7, 29)}
    # 沒有獨立日期欄(明細表)→ 補;目標月同年同月附近 → 只寫 M/D
    assert _pending_why(_u, has_date_column=False,
                        year=2026, month=8).endswith("（上次 7/29）")
    # 有獨立日期欄(全空版型三欄表)→ **不補**,不重複講第二次
    assert _pending_why(_u, has_date_column=True) == _u["reason"]
    # `stale` 的日期長在句子中間(是句子本體不是重複)→ 兩種版面都原樣輸出
    _s = {"reason": "上次配息是 2025/03，已經 11 個月沒動靜，可能停配或資料沒更新。",
          "reason_code": "stale", "last_ex": _dt.date(2025, 3, 14)}
    for _hdc in (True, False):
        assert _pending_why(_s, has_date_column=_hdc, year=2026, month=2) == _s["reason"]


def test_reason_tail_carries_year_when_last_ex_is_far_from_target_month():
    """追加 8:reason 尾巴的「上次 M/D」離目標月超過半年 → 帶年份(與虛線 chip 同一份規則)。"""
    from services.dividend_calendar import _LAST_EX_YEAR_MONTHS, fmt_last_ex
    from ui.helpers.dividend_calendar_render import _pending_why
    _u = {"reason": "只有 2 筆配息紀錄，還看不出規律（至少要 3 筆）。",
          "reason_code": "too_few", "last_ex": _dt.date(2026, 8, 11)}
    assert _pending_why(_u, has_date_column=False, year=2027, month=2).endswith("（上次 2026/8/11）")
    assert _pending_why(_u, has_date_column=False, year=2026, month=9).endswith("（上次 8/11）")
    # 門檻是 module 具名常數(§3.3);規則 = **跨年** or 相差 > 門檻
    assert _LAST_EX_YEAR_MONTHS == 6
    _d = _dt.date(2026, 8, 11)
    # 總管點名的實例:2026-08 → 2027-02 相差**剛好 6 個月**,單一個 `> 6` 會漏掉它 ——
    # 真正讓人誤讀的是年份不同,所以跨年一律帶年份。
    assert fmt_last_ex(_d, year=2027, month=2) == "2026/8/11"
    assert fmt_last_ex(_d, year=2027, month=1) == "2026/8/11"       # 跨年 → 仍帶年份
    assert fmt_last_ex(_d, year=2026, month=9) == "8/11"            # 同年近距 → 只寫 M/D
    assert fmt_last_ex(_dt.date(2026, 2, 11), year=2026, month=12) == "2026/2/11"  # 同年遠距
    assert fmt_last_ex(_d) == "2026/8/11"                           # 目標月不明 → 帶年份(保守)
    assert fmt_last_ex(None, year=2026, month=9) == ""              # §1 不捏造日期


# ── §15.4 全部推不出 → 整組換文案與版面 ────────────────────────────────
def test_all_unpredictable_swaps_title_and_subtitle():
    """§15.4:標題改「本月除息日推不出來」,副標講清楚「會配息,只是算不出哪天」。

    §1:原本的全空月曆 + 「本月無推估除息基準日」讀起來就是「這個月沒配息」——
    讓失敗看起來像成功,是本檔要防的頭號誤導。
    """
    html = render_month_calendar_html(_cal_all_unpred())
    assert "<h1>本月除息日推不出來</h1>" in html
    assert "基金除息配息行事曆" not in html              # 不沿用原標題
    assert "你的 2 檔基金這個月都會配息" in html
    assert "系統不敢給日期" in html
    assert "下方列出各檔上次的實際基準日供參考，實際日期請看基金公司公告。" in html


def test_all_unpredictable_draws_no_empty_calendar_grid():
    """§15.4:**不要畫空月曆格** —— 空格子是最大的誤導來源(空 = 那天沒事)。"""
    html = render_month_calendar_html(_cal_all_unpred())
    assert '<div class="grid">' not in html
    assert '<div class="cell' not in html
    assert "待確認清單" in html


def test_all_unpredictable_lists_each_fund_with_last_date_and_reason():
    """§15.4 待確認清單:每檔都要看得見(投信名 · 上次實際基準日)且說得出原因。

    ⚠️ **v19.535 待辦 2 版面變更**(總管實看 `v534_C_all_unpred_2026-09.png` 後核准):
    原本逐檔一列、每列各帶一次原因 —— 本 fixture 兩檔同句,C 情境 5 檔同句時等於同一句
    印 5 遍、每列還換行成 2 行,在 560px 推播圖上佔掉大半版面。改成同句**併一組**、
    說明提到組上方一行,列內只留「投信名 · 上次實際基準日」→ 表頭因此少一欄。
    要守的東西**沒有放寬**:兩檔都還在、上次日期還在、原因還在(移到組說明列),
    另見 `test_pending_list_groups_same_reason_into_one_sentence` 鎖分組結構本身。
    """
    html = render_month_calendar_html(_cal_all_unpred())
    assert "<th>基金</th><th>上次實際基準日</th>" in html
    assert "<th>原因</th>" not in html                   # 全組同句 → 沒有逐列原因欄可留
    assert "2025/6/5" in html                           # 上次的**實際**基準日(完整年月日)
    assert "對不上固定規律" in html                       # 原因仍說得出口(在組說明列)
    assert html.count('<tr class="pend">') == 2         # 兩檔都在,沒有人消失


def test_empty_month_with_no_funds_keeps_old_honest_wording():
    """反向護欄:`events` 與 `unpredictable` **都**空 = 真的沒有基金可列 → 沿用原空月文案。

    §15.4 換版面的觸發條件是「有配息史卻全數棄權」,不是「畫面上沒東西」——
    兩者混在一起會讓「你根本沒加基金」被講成「你的 0 檔基金都會配息」。
    """
    html = render_month_calendar_html(build_month_calendar([], 2026, 8))
    assert "本月除息日推不出來" not in html
    assert "無推估除息基準日" in html


# ── §15.5 點名需要人工補資料的基金 ─────────────────────────────────────
def test_pending_ask_note_present_in_both_layouts():
    """§15.5:「待確認」區塊末尾要點名 —— 部分推不出與全部推不出兩種版面都要有。"""
    _note = "※ 這幾檔若你手上有近期的實際基準日，可以補進來提高準確度。"
    assert _note in render_month_calendar_html(_cal_mixed())
    assert _note in render_month_calendar_html(_cal_all_unpred())
    # 全部推得出時不該出現(沒有人要被點名)
    assert _note not in render_month_calendar_html(_cal())


# ── 必改 1:誤差帶改 90 分位 + 頁尾說明它憑什麼 ──────────────────────────
def test_error_band_footnote_explains_the_number():
    """具體數字比模糊標籤更容易被過度相信 → 必須說明它是什麼、憑什麼(§1)。

    「±2 天」讀起來像個保證。頁尾這一句把它降回它真正的身分:**用該檔自己的配息史回測出來的
    九成區間**。文案 SSOT 在 L2 `ERR_BAND_FOOTNOTE`,「約九成」與 `_ERR_BAND_QUANTILE`
    (0.90)是同一件事的兩種寫法,不可只改一邊。
    """
    from services.dividend_calendar import ERR_BAND_FOOTNOTE, _ERR_BAND_QUANTILE
    assert ERR_BAND_FOOTNOTE == "※ 誤差 = 用該檔自己的配息史回測，約九成情況落在此範圍內。"
    assert _ERR_BAND_QUANTILE == 0.90
    html = render_month_calendar_html(_cal())
    assert ERR_BAND_FOOTNOTE in html
    assert html.index("<th>誤差</th>") < html.index(ERR_BAND_FOOTNOTE)   # 說明在數字之後(頁尾)


def test_error_band_footnote_absent_when_there_is_no_error_column():
    """全空版型沒有「誤差」欄 → 不加那句說明,否則是在解釋畫面上不存在的東西。"""
    from services.dividend_calendar import ERR_BAND_FOOTNOTE
    html = render_month_calendar_html(_cal_all_unpred())
    assert "<th>誤差</th>" not in html and ERR_BAND_FOOTNOTE not in html


def test_error_band_ninety_percentile_changes_real_fund_labels():
    """90 分位在**畫面上**的實際後果:摩根從「±0 天」變「±2 天」,施羅德變「僅供參考」。

    這條把「分位數」與「user 真正看到的那幾個字」綁在一起 —— 只鎖常數不鎖顯示,
    有人動了切點(`_ERR_BAND_DAYS_MAX` / `_ERR_BAND_WEEK_MAX`)一樣會悄悄漂掉。
    """
    from ui.helpers.dividend_calendar_render import _err_band_label
    assert _err_band_label(2)[0] == "±2 天"        # 摩根:12 次裡差過 2 天與 4 天,不是「保證那天」
    assert _err_band_label(0)[0] == "±0 天"        # 聯博 / 瀚亞 / 安聯
    assert _err_band_label(11)[0] == "僅供參考"     # 施羅德:帶寬 11 > 7,給數字反而誤導


def test_manual_override_ui_not_built_this_round():
    """§15.5 / §-1:本次**只做點名**,不做手動輸入儲存 —— 不主動擴散。"""
    html = render_month_calendar_html(_cal_all_unpred())
    for _widget in ("<input", "<form", "<button", "contenteditable"):
        assert _widget not in html


def test_all_unpredictable_table_does_not_repeat_the_date_in_the_reason():
    """v19.534 追加 9:三欄表已有獨立「上次實際基準日」欄 → 原因欄**不再重複**同一個日期。

    總管實看 `v533_C_all_unpred` 圖後點名:第 2 欄已經印了「2026/8/14」,第 3 欄又寫
    「上次是 8/14」;5 檔同原因時等於同一句話複製 5 遍,在 560px 推播圖上佔掉大半版面。
    """
    html = render_month_calendar_html(_cal_all_unpred())
    _body = html.split("<tbody>")[1].split("</tbody>")[0]
    assert "2025/6/5" in _body                          # 獨立欄:完整年月日(追加 8 已正確)
    assert "上次是" not in _body and "（上次" not in _body   # 原因欄:不重複講第二次
    assert "對不上固定規律" in _body                      # 但原因本身還在


def test_target_month_wording_replaces_this_month_everywhere_on_the_page():
    """v19.534 追加 7:圖上所有指涉目標月的「本月」→ **實際目標月**(走 `month_label`)。

    cron 每月 1 號推的是**下個月**:徽章寫「民國116年 2月」、副標卻寫「推估本月…」,
    同一張圖自相矛盾。此處連虛線 chip 上方那行標籤一起守(它也寫過「本月推不出日期」)。
    """
    from services.dividend_calendar import month_label
    _ml = month_label(2026, 8)
    html = render_month_calendar_html(_cal_mixed())
    assert f'<p class="pending-lab">{_ml}推不出日期' in html
    assert f'<h2 class="section-t">{_ml}除息基準日明細（推估）</h2>' in html
    assert f'推估{_ml}的除息基準日與配息入帳日' in html
    assert "本月推不出日期" not in html and "推估本月" not in html


def test_tab_manage_caption_does_not_say_zero_when_all_unpredictable():
    """v19.534 裁示 3:App 端 caption 與 §15.4 圖上的口徑對齊。

    原本全推不出時 caption 寫「本月推估除息 **0 檔**｜N 檔無法推估」—— 圖上剛講完
    「是推不出,不是沒配息」,底下這行又說「0 檔」,同一畫面兩個口徑(§1)。
    這條是 source-level drift-lock:caption 走 `is_all_unpredictable` 分流,
    且不得在該分支印「推估除息 0 檔」。
    """
    import pathlib as _pl
    _raw = _pl.Path("ui/tab_manage.py").read_text(encoding="utf-8")
    # 只看**會執行的程式碼**:註解裡引用舊文案是說明「改掉了什麼」,不是文案本身。
    src = "\n".join(ln for ln in _raw.splitlines() if not ln.lstrip().startswith("#"))
    assert "is_all_unpredictable(_cal)" in src, "caption 沒有走 §15.4 的分流判斷"
    assert "都推不出除息日" in src and "是推不出,不是沒配息" in src
    # 舊口徑不可回流:不得再出現「N 檔無法推估」這種讀起來像「這幾檔沒配息」的說法
    assert "檔無法推估" not in src
    assert "推不出日期(非沒配息)" in src        # 部分推不出時也要講清楚是哪一種


# ── §15.4 LINE caption / Flex altText ────────────────────────────────
def test_line_caption_first_line_says_not_no_dividend():
    """§15.4:LINE caption **首行**就要講「是推不出,不是沒配息」。

    LINE 推播預覽只看得到前一兩行 —— 原本首行是「🗓️ 基金除息行事曆 · 民國X年Y月（推估）」,
    第二行才是「本月無推估除息基準日」,user 掃過去的結論是「這個月沒事」(§1 違憲)。

    v19.534 裁示 4:首行的「本月」→ **實際目標月**。cron(每月 1 號)推的是**下個月**,
    §15.4 規格逐字寫的「本月」在推播情境是錯的(總管 2026-08-26 認錯改規格);
    App 端目標月 = 當月時語意仍正確,兩邊都對。
    """
    from services.dividend_calendar import build_summary_text
    _txt = build_summary_text(_cal_all_unpred())
    assert _txt.splitlines()[0] == "⚠️ 民國115年8月 有 2 檔推不出除息日 —— 是推不出，不是沒配息"
    assert "⚠️ 本月" not in _txt                        # 「本月」不可回流(推播情境會是錯的)
    assert "無推估除息基準日" not in _txt
    assert "施羅德 · 上次 2025/6/5" in _txt              # 逐檔列上次實際基準日(跨年 → 帶年份)
    assert "※ 這幾檔若你手上有近期的實際基準日" in _txt


def test_flex_alt_text_drops_zero_count_when_all_unpredictable():
    """§15.4:altText 改「N 檔待確認・系統推不出日期」,**移除「0 檔」**。

    「0 檔」在通知列上讀起來就是「這個月沒有基金配息」,與事實相反 —— 而 altText 往往是
    user 唯一看到的一行字。
    """
    from services.dividend_calendar import build_summary_flex
    _alt = build_summary_flex(_cal_all_unpred())["alt_text"]
    assert _alt == "🗓️ 民國115年8月 除息行事曆（2 檔待確認・系統推不出日期）"
    assert "0 檔" not in _alt


def test_flex_all_unpredictable_card_is_not_the_empty_card():
    from services.dividend_calendar import build_summary_flex
    import json
    _txt = json.dumps(build_summary_flex(_cal_all_unpred()), ensure_ascii=False)
    assert "本月除息日推不出來" in _txt and "待確認清單" in _txt
    assert "無推估除息基準日" not in _txt


# ══════════════════════════════════════════════════════════════════════
# v19.535 顯示層收尾(總管 2026-08-26 實看 v534 三張圖後)——
#   1. 「僅供參考」的日期不加粗   2. 待確認清單同句只講一次   3. 空月文案吃目標月
#   ⚠️ 三條都只碰「顯示什麼」;引擎推估邏輯一行沒動(三口徑驗收不變)。
# ══════════════════════════════════════════════════════════════════════
def _cal_soft_band():
    """推得出日期、但誤差帶是「僅供參考」的基金(歷史 5 筆 < 8 → `error_band` 為 None)。"""
    funds = [{"code": "NEW1", "name": "安聯新發行", "dividends": _divs_ending(14, 5)}]
    for f in funds:
        f["house"] = detect_house(f["name"])
    return build_month_calendar(funds, 2026, 8, ref_year=2026, ref_month=7, ref_day=20)


def _row_with(html: str, needle: str) -> str:
    """明細表 tbody 裡含 `needle` 的那一列(找不到 → 空字串,讓斷言指出真正的問題)。"""
    _body = html.split("<tbody>")[1].split("</tbody>")[0]
    _hit = [r for r in _body.split("<tr") if needle in r]
    return ("<tr" + _hit[0]) if len(_hit) == 1 else ""


def test_reference_only_date_is_not_bold():
    """待辦 1 drift-lock:誤差帶「僅供參考」的列,日期**不得**再用粗體 + accent 色。

    為什麼是 bug 而不是美感問題(總管 2026-08-26 實看 `v534_A_normal_2026-09.png`):
    粗體日期會被當成**確定日期**讀,旁邊那個灰色小標籤壓不住它。圖上施羅德印「**9/30**」,
    但它的規律是「每月最後一個星期四」= 2026-09 的 9/24 —— 那一筆很可能就是錯的。
    它印得出來是因為引擎閘門看 in-sample 復現率,而它真正的 walk-forward 誤差帶是 ±11 天;
    兩個訊號不一致時該信 out-of-sample 那個。**錯得看起來很確定**正是本輪要修的病。

    ⚠️ 反向同樣鎖住:日期本身**照常顯示**(user 明確要求「留」,該檔 6 次裡 4 次是準的),
    降的是字重不是資訊;誤差帶給得出數字的列也**不得**被連坐降階。
    """
    from ui.helpers.dividend_calendar_render import (_DATE_SOFT_CLASS, _DATE_STRONG_CLASS,
                                                     _ERR_BAND_NA_CLASS)
    html = render_month_calendar_html(_cal_soft_band())
    _row = _row_with(html, "僅供參考")
    assert _row, "找不到那一列 —— fixture 已經不是「推得出日期但誤差帶不足」的情境"
    assert f'class="tnum {_DATE_SOFT_CLASS}"' in _row          # 降一階
    assert f'class="tnum {_DATE_STRONG_CLASS}"' not in _row    # 粗體 accent 不得回流
    assert "8/14" in _row                                      # 日期照留(user:「留」)

    # 反向:誤差帶給得出數字的列維持強調(降階不可擴散成「全部都不強調」)
    _ok = _row_with(render_month_calendar_html(_cal()), "±0 天")
    assert f'class="tnum {_DATE_STRONG_CLASS}"' in _ok
    assert _DATE_SOFT_CLASS not in _ok

    # CSS 真的降了字重(只換 class 不改樣式 = 白做);且 class 名自我說明 + 註明理由
    assert ".d-soft{color:var(--ink-soft);font-weight:400}" in html
    assert _DATE_SOFT_CLASS == "d-soft" and _ERR_BAND_NA_CLASS == "na"


def test_reference_only_date_class_follows_the_error_band_label():
    """待辦 1 的另一半:字重由**誤差帶那一階**決定,不得在 L3 另做一次門檻比較。

    兩邊各判一次遲早會漂 —— 有人改了 `_ERR_BAND_WEEK_MAX` 卻只改到標籤那一側,
    畫面就會出現「僅供參考 + 粗體日期」這種自相矛盾的列,而且沒有任何測試會紅。
    """
    import inspect
    from ui.helpers.dividend_calendar_render import _detail_rows_html
    src = inspect.getsource(_detail_rows_html)
    assert "_ERR_BAND_NA_CLASS" in src and "_DATE_SOFT_CLASS" in src
    for _magic in ('"na"', "'na'", "_ERR_BAND_WEEK_MAX", "_ERR_BAND_DAYS_MAX"):
        assert _magic not in src, f"字重不可自行比門檻 / 寫死 class:{_magic}"


# ── 待辦 2:待確認清單同一句原因只講一次 ────────────────────────────────
def _cal_all_unpred_n(n: int):
    """n 檔**同一句**原因的全推不出月曆(v534_C 圖的縮小版:5 檔全 `anchor_weak`)。"""
    funds = [{"code": f"IRR{i}", "name": f"{h}不規則", "dividends": list(_IRREGULAR)}
             for i, h in enumerate(("施羅德", "摩根", "安聯", "聯博", "瀚亞")[:n])]
    for f in funds:
        f["house"] = detect_house(f["name"])
    return build_month_calendar(funds, 2026, 8)


def _cal_mixed_reasons():
    """兩檔同句(`anchor_weak`)+ 一檔自己一句(`too_few`)→ 分組與逐列寫法並存。"""
    funds = [{"code": "SD080", "name": "施羅德環球收益", "dividends": list(_IRREGULAR)},
             {"code": "IRR2", "name": "摩根不規則", "dividends": list(_IRREGULAR)},
             {"code": "NEW9", "name": "聯博新上市", "dividends": _divs_ending(14, 2)}]
    for f in funds:
        f["house"] = detect_house(f["name"])
    return build_month_calendar(funds, 2026, 8, ref_year=2026, ref_month=7, ref_day=20)


def test_pending_list_groups_same_reason_into_one_sentence():
    """待辦 2:5 檔同原因 → 說明句**只印一次**(提到組上方),列內只留投信名 · 上次基準日。

    症狀(總管實看 `v534_C_all_unpred_2026-09.png`):同一句話印 5 遍、每列還換行成 2 行,
    在 560px 推播圖上佔掉大半版面。前一組實測「拿掉日期尾巴」高度一個像素都沒少 ——
    因為重複的是**句子本身**,不是尾巴。
    """
    html = render_month_calendar_html(_cal_all_unpred_n(5))
    _body = html.split("<tbody>")[1].split("</tbody>")[0]
    assert _body.count("對不上固定規律") == 1              # 同一句只講一次(原本 5 遍)
    assert _body.count('<tr class="grp">') == 1           # 一組 → 一句說明
    assert _body.count('<tr class="pend">') == 5          # 5 檔一個都沒少
    for _h in ("施羅德", "摩根", "安聯", "聯博", "瀚亞"):
        assert _h in _body
    assert "<th>原因</th>" not in html                     # 沒有逐列原因 → 不留空欄配空欄頭


def test_pending_list_group_note_sits_above_its_rows():
    """待辦 2 版面結構:說明句在**該組上方**,不是塞回列內或跑到表尾。"""
    html = render_month_calendar_html(_cal_all_unpred_n(3))
    _body = html.split("<tbody>")[1].split("</tbody>")[0]
    assert _body.index("對不上固定規律") < _body.index('<tr class="pend">')
    assert _body.startswith('<tr class="grp">')
    # 組說明列橫跨整表(欄數走具名常數,不寫死數字)
    from ui.helpers.dividend_calendar_render import _PENDING_COLS_GROUPED
    assert f'<td colspan="{_PENDING_COLS_GROUPED}">' in _body


def test_pending_list_single_fund_group_keeps_the_per_row_wording():
    """待辦 2:**單檔成組不開組標題** —— 為 1 檔開一行標題,混合情境反而比原版更長。

    分組是為了消掉重複,不是為了分組本身。兩檔同句 → 併組;剩下那檔自己一句 → 留在列上。
    """
    html = render_month_calendar_html(_cal_mixed_reasons())
    _body = html.split("<tbody>")[1].split("</tbody>")[0]
    assert _body.count('<tr class="grp">') == 1           # 只有那個 2 檔組有標題
    assert _body.count('<tr class="pend">') == 3
    assert "<th>原因</th>" in html                         # 有逐列原因 → 欄頭要對得上
    _solo = _row_with(html, "只有 2 筆配息紀錄")
    assert _solo and "聯博" in _solo                       # 那句話留在它自己那一列


def test_pending_groups_never_merge_two_funds_with_different_numbers():
    """待辦 2 的 §1 紅線:同 `reason_code` **但句子不同**(帶各自的筆數)→ **不可**併組。

    只用 code 併組的話,組標題會拿其中一檔的數字代表全組 —— 把 A 檔的事實安到 B 檔頭上,
    那是捏造。這裡兩檔都是 `too_few`,一檔 2 筆一檔 1 筆,必須各自站一行。
    """
    from services.dividend_calendar import group_unpredictable
    funds = [{"code": "A2", "name": "安聯甲", "dividends": _divs_ending(14, 2)},
             {"code": "B1", "name": "摩根乙", "dividends": _divs_ending(14, 1)}]
    for f in funds:
        f["house"] = detect_house(f["name"])
    cal = build_month_calendar(funds, 2026, 8, ref_year=2026, ref_month=7, ref_day=20)
    _unp = cal["unpredictable"]
    assert {u["reason_code"] for u in _unp} == {"too_few"}          # 同一個 code
    _groups = group_unpredictable(_unp)
    assert len(_groups) == 2 and all(len(g["entries"]) == 1 for g in _groups)
    html = render_month_calendar_html(cal)
    _body = html.split("<tbody>")[1].split("</tbody>")[0]
    assert '<tr class="grp">' not in _body                          # 全是單檔 → 無組標題
    assert "只有 2 筆" in _body and "只有 1 筆" in _body              # 各自的數字都在


# ── 待辦 3:空月文案吃徽章同一個月份變數 ─────────────────────────────────
def test_empty_month_note_uses_target_month_not_this_month():
    """待辦 3:`events` 與 `unpredictable` **都**空的路徑,文案不再寫死「本月」。

    與 v19.534 追加 7 同病:cron 每月 1 號推的是**下個月**,徽章寫的是真正的目標月,
    同一張圖上「本月」與「民國116年2月」自相矛盾。
    (此路徑在推播情境不會觸發 —— 無代碼時 notify 直接 exit 2 —— 但用詞一致性仍要收:
     HTML / LINE 文字 / Flex 三處原本各寫各的,下次改文案必漏一處。)
    """
    import json
    from services.dividend_calendar import (EMPTY_MONTH_NOTE_TMPL, build_summary_flex,
                                            build_summary_text, empty_month_note, month_label)
    assert EMPTY_MONTH_NOTE_TMPL == "{month}你的基金無推估除息基準日（或資料不足）。"
    assert empty_month_note(2027, 2) == "民國116年2月你的基金無推估除息基準日（或資料不足）。"
    assert month_label(2027, 2) in empty_month_note(2027, 2)     # 與徽章同一個月份變數

    _cal_empty = build_month_calendar([], 2027, 2)
    _html = render_month_calendar_html(_cal_empty)
    _txt = build_summary_text(_cal_empty)
    _flex = json.dumps(build_summary_flex(_cal_empty), ensure_ascii=False)
    for _surface in (_html, _txt, _flex):
        assert empty_month_note(2027, 2) in _surface             # 三處同一句 SSOT
        assert "本月無推估" not in _surface and "本月你的基金" not in _surface
    assert "無推估除息基準日" in _html                            # §13.8 口徑仍是「基準日」
