"""ui/helpers/dividend_calendar_render.py — 除息基準日/配息月曆 HTML 渲染(v19.530)。

純字串產生器(**零 streamlit、零 IO**),吃 `services.dividend_calendar.build_month_calendar`
的結構 → 產出自成一頁的 HTML(深/淺色皆適配)。共用於:App 內 `st.components.html` 嵌入(方式 A)、
之後 LINE 摘要附的連結 / 存檔(方式 C)。版型 = user 2026-08 核准的樣張。
"""
from __future__ import annotations

import calendar as _calendar
import html as _html

from services.dividend_calendar import dedupe_events, display_label, pay_window

# 投信分色(中間調,深/淺底都看得清;判不出 → 預設灰)
_HOUSE_COLOR = {
    "聯博": "#2e8079", "安聯": "#b5771f", "摩根": "#3f63ab", "施羅德": "#8a5680",
    "瀚亞": "#4f8248", "富蘭克林": "#c06a24", "貝萊德": "#43506b", "高盛": "#a8862f",
    "PIMCO": "#3d7ba8", "野村": "#a1444e", "景順": "#5a7a3a", "富達": "#4a8a6a",
    "法巴": "#5a6b8a", "M&G": "#8a5a3a", "復華": "#7a5a8a", "國泰": "#2f7d6a", "群益": "#a86a3a",
}
_DEFAULT_COLOR = "#6b7280"
_DOW = ["一", "二", "三", "四", "五", "六", "日"]
_CONF = {"high": ("高", "high"), "medium": ("中", "med"), "low": ("低", "low")}

_CSS = """
:root{
  --bg:#f6f4ef;--surface:#fff;--cell:#fbfaf6;--weekend:#efebe1;
  --ink:#1b1e28;--ink-soft:#5c6376;--ink-faint:#8b91a1;
  --line:#e4dfd4;--line-soft:#efe9dd;
  --band:#28324c;--band-ink:#f3f1ea;
  --accent:#a9631a;--accent-ink:#7a4712;--accent-soft:#f4e6d2;
  --ok:#2e7d55;--ok-bg:#e2f0e8;--exclude:#8b91a1;--exclude-bg:#f0eee9;
  --shadow:0 1px 2px rgba(30,30,40,.05),0 6px 20px rgba(30,30,40,.05);--radius:14px;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#13151d;--surface:#1b1e28;--cell:#1f232f;--weekend:#191c26;
  --ink:#ecebe6;--ink-soft:#a3a9b8;--ink-faint:#6d7284;
  --line:#2b3040;--line-soft:#242938;--band:#2c3853;--band-ink:#eef1f8;
  --accent:#e0a44e;--accent-ink:#eab566;--accent-soft:#39301f;
  --ok:#6bbd93;--ok-bg:#1e3329;--exclude:#767c8c;--exclude-bg:#20242f;
  --shadow:0 1px 2px rgba(0,0,0,.3),0 8px 24px rgba(0,0,0,.35);
}}
:root[data-theme="dark"]{
  --bg:#13151d;--surface:#1b1e28;--cell:#1f232f;--weekend:#191c26;
  --ink:#ecebe6;--ink-soft:#a3a9b8;--ink-faint:#6d7284;
  --line:#2b3040;--line-soft:#242938;--band:#2c3853;--band-ink:#eef1f8;
  --accent:#e0a44e;--accent-ink:#eab566;--accent-soft:#39301f;
  --ok:#6bbd93;--ok-bg:#1e3329;--exclude:#767c8c;--exclude-bg:#20242f;
  --shadow:0 1px 2px rgba(0,0,0,.3),0 8px 24px rgba(0,0,0,.35);
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  /* "Noto Sans CJK TC" 為 Debian/Ubuntu `fonts-noto-cjk` 實際註冊的家族名(cron runner 用);
     "Noto Sans TC" 是 Google Fonts 子集家族名(Debian 沒有)。少了 CJK TC 這條,runner 上所有
     指名字型都 miss → 落到 generic sans-serif → Noto Sans CJK 預設臉是 **JP**,繁中會被畫成
     日文漢字變體(直/骨/令 等字形不同)。明確指名 TC 才不必賭 lang 轉發。 */
  font-family:"PingFang TC","Noto Sans CJK TC","Noto Sans TC","Microsoft JhengHei",
              -apple-system,system-ui,sans-serif;
  line-height:1.5;-webkit-font-smoothing:antialiased}
.wrap{max-width:1040px;margin:0 auto;padding:clamp(16px,3.5vw,32px)}
.tnum{font-variant-numeric:tabular-nums}
.eyebrow{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent-ink);font-weight:700;margin:0 0 6px}
h1{font-size:clamp(22px,3.6vw,32px);margin:0;font-weight:800;letter-spacing:-.01em;text-wrap:balance}
.sub{color:var(--ink-soft);margin:8px 0 0;font-size:14px}
.badges{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;align-items:center}
.badge{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;font-weight:700;padding:5px 11px;border-radius:999px;border:1px solid var(--line)}
.badge.sample{background:var(--accent-soft);color:var(--accent-ink);border-color:transparent}
.badge.month{background:var(--band);color:var(--band-ink);border-color:transparent}
.legend{display:flex;flex-wrap:wrap;gap:12px 16px;margin:14px 0 20px;padding:0;list-style:none}
.legend li{display:flex;align-items:center;gap:7px;font-size:13px;color:var(--ink-soft)}
.dot{width:10px;height:10px;border-radius:50%;flex:none}
.cal-scroll{overflow-x:auto}
.cal{min-width:680px;background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);overflow:hidden}
.dow{display:grid;grid-template-columns:repeat(7,1fr);background:var(--band)}
.dow div{padding:10px;color:var(--band-ink);font-weight:700;font-size:13px}
.dow div.sat{color:#b9c4de}.dow div.sun{color:#e6b6a0}
.grid{display:grid;grid-template-columns:repeat(7,1fr)}
.cell{min-height:92px;padding:8px;border-right:1px solid var(--line-soft);border-top:1px solid var(--line-soft);display:flex;flex-direction:column;gap:5px}
.cell:nth-child(7n){border-right:none}
.cell.wknd{background:var(--weekend)}.cell.blank{background:transparent}
.d{font-size:14px;font-weight:700;color:var(--ink-soft)}
.cell.has .d{color:var(--ink)}
.chips{display:flex;flex-direction:column;gap:4px;margin-top:2px}
.chip{display:flex;align-items:center;gap:6px;font-size:12px;font-weight:600;padding:3px 7px;border-radius:7px;background:var(--cell);border:1px solid var(--line-soft);color:var(--ink)}
.chip .dot{width:8px;height:8px}.chip .code{color:var(--ink-faint);font-weight:600;font-size:11px}
.chip .q{color:var(--accent-ink);font-weight:700;font-size:11px}
.section-t{font-size:13px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-faint);font-weight:700;margin:28px 0 12px}
.tbl-scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;min-width:360px;font-size:14px}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line-soft)}
thead th{font-size:12px;letter-spacing:.04em;color:var(--ink-faint);font-weight:700;border-bottom:1px solid var(--line)}
tbody tr:last-child td{border-bottom:none}
td.name b{font-weight:700}
.house{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;color:var(--ink-soft)}
.est{color:var(--accent-ink);font-weight:700}
.muted{color:var(--ink-faint)}
.cf{font-size:11px;font-weight:700;padding:2px 8px;border-radius:999px;white-space:nowrap}
.cf.high{background:var(--ok-bg);color:var(--ok)}
.cf.med{background:var(--exclude-bg);color:var(--ink-soft)}
.cf.low{background:var(--accent-soft);color:var(--accent-ink)}
.excluded{margin-top:16px;padding:13px 16px;background:var(--exclude-bg);border-radius:12px;border:1px solid var(--line-soft);font-size:13.5px;color:var(--ink-soft)}
.excluded b{color:var(--ink)}
.excluded .x{display:inline-block;padding:1px 7px;border-radius:6px;background:var(--surface);border:1px solid var(--line);color:var(--exclude);font-size:12px;font-weight:700;margin-right:8px}
footer.note{margin-top:24px;padding-top:16px;border-top:1px solid var(--line);color:var(--ink-faint);font-size:12.5px;line-height:1.7}
footer.note b{color:var(--ink-soft)}
"""

# ── 推播圖專用覆寫(user 2026-08-24「字體太小,版面集中一點」)────────────────────────
# 手機看 LINE 圖片時,圖會被縮到聊天氣泡寬度 → **字的視覺大小 = 字級 ÷ 圖的 CSS 寬度**。
# 原本 820px 寬 + 14px 字,縮到手機上就變很小。故推播版:(a) 畫窄到 560px、(b) 字級加大、
# (c) 收緊留白與格高。App 網頁版不受影響(只有 compact=True 才套用)。
_CSS_COMPACT = """
.wrap{max-width:100%;padding:18px 16px}
.eyebrow{font-size:12px;margin-bottom:4px}
h1{font-size:30px}
.sub{font-size:15px;margin-top:6px}
.badges{gap:7px;margin-top:10px}
.badge{font-size:14px;padding:6px 12px}
.legend{gap:8px 14px;margin:12px 0 14px}
.legend li{font-size:14px;gap:6px}
.legend .dot{width:11px;height:11px}
/* 關鍵:解除 680px 最小寬,讓 7 欄格子縮到容器寬,不再需要橫向捲動/縮圖 */
.cal-scroll{overflow:visible}
.cal{min-width:0}
.dow div{padding:9px 2px;font-size:15px;text-align:center}
.cell{min-height:72px;padding:6px 4px;gap:3px}
.d{font-size:15px}
.chips{gap:3px;margin-top:1px}
.chip{font-size:13px;padding:3px 5px;gap:4px;white-space:nowrap;justify-content:center}
.chip .dot{width:7px;height:7px}
.section-t{font-size:14px;margin:20px 0 10px}
.tbl-scroll{overflow:visible}
table{min-width:0;font-size:16px}
th,td{padding:9px 5px}
thead th{font-size:14px}
.house{font-size:15px;gap:5px}
.cf{font-size:13px;padding:2px 9px}
footer.note{font-size:13px;margin-top:18px;padding-top:14px;line-height:1.65}
"""


# 推播圖 CSS 寬度:字的視覺大小 = 字級 ÷ 此寬度。窄 → 手機上字更大。
# 560 是「7 欄格子還塞得下投信名」與「字夠大」的平衡點(再窄會擠壞格子)。
_PUSH_WIDTH = 560


def _e(s) -> str:
    return _html.escape(str(s if s is not None else ""))


def _color(house: str) -> str:
    return _HOUSE_COLOR.get(house, _DEFAULT_COLOR)


def _chip_label(ev: dict) -> str:
    """月曆格子/明細表的標籤:**只顯示投信名**(user 2026-08-24)。

    規則 SSOT 在 L2 `services.dividend_calendar.display_label` —— 圖檔、明細表、LINE 文字、
    Flex 四個介面共用同一份,避免各寫各的而漂移。§1 保證非空(退代號 → 基金名 → 「—」)。
    """
    return display_label(ev)


def _dedupe_day_chips(evs: list) -> list:
    """同一天(同一除息基準日)同投信多檔 → 合併成**一個** chip(user 2026-08-24「移除重複」)。

    去重規則走 L2 `dedupe_events`(格子 / 明細表 / LINE 文字 / Flex 同一份 SSOT,不會漂移);
    本函式只負責補上顯示用的顏色與低信心旗標。信心已由 L2 取最保守值(任一 low → low)。
    """
    return [{"label": _chip_label(_ev), "color": _color(_ev.get("house")),
             "low": _ev.get("confidence") == "low"}
            for _ev in dedupe_events(evs)]


def _fmt_pay_window(ex) -> str:
    """除息基準日 → 入帳推估「區間」字串(如 `8/22~8/26`)。口徑 SSOT 走 L2 `pay_window`。

    §1:算不出(ex 非日期)→ 「—」,不捏造日期。
    """
    _w = pay_window(ex)
    if not _w:
        return "—"
    _lo, _hi = _w
    return f"{_lo.month}/{_lo.day}~{_hi.month}/{_hi.day}"


def render_month_calendar_html(cal: dict, *, title: str = "基金除息配息行事曆",
                               is_sample: bool = False, compact: bool = False) -> str:
    """月曆結構 → 自成一頁 HTML 字串(日期欄位一律為**除息基準日**推估值)。

    `compact=True`:推播圖專用版型(窄幅 + 大字 + 收緊留白),見 `_CSS_COMPACT`。
    App 網頁版用預設 False,版面完全不變。
    """
    y, m = int(cal["year"]), int(cal["month"])
    roc = y - 1911
    first_wd, days = _calendar.monthrange(y, m)      # first_wd: Mon=0..Sun=6
    by_day = cal.get("by_day") or {}
    events = cal.get("events") or []

    # 圖例:本月出現的投信(去重保序)
    seen, legend = set(), []
    for e in events:
        h = e.get("house") or ""
        key = h or e.get("code")
        if key not in seen:
            seen.add(key)
            legend.append((h or e.get("code"), _color(h)))
    legend_html = "".join(
        f'<li><span class="dot" style="background:{_e(c)}"></span>{_e(h)}</li>' for h, c in legend)

    # 月曆格子
    cells = []
    for _ in range(first_wd):
        cells.append('<div class="cell blank"></div>')
    for d in range(1, days + 1):
        dow = (first_wd + d - 1) % 7
        wknd = " wknd" if dow >= 5 else ""
        evs = by_day.get(d) or []
        chips = ""
        if evs:
            chips = '<div class="chips">' + "".join(
                f'<span class="chip"><span class="dot" style="background:{_e(c["color"])}"></span>'
                f'<b>{_e(c["label"])}</b>'
                + ('<span class="q">?</span>' if c["low"] else "")
                + '</span>'
                for c in _dedupe_day_chips(evs)) + '</div>'
        has = " has" if evs else ""
        cells.append(f'<div class="cell{wknd}{has}"><div class="d tnum">{d}</div>{chips}</div>')
    grid_html = "".join(cells)

    # 明細表(user 2026-08-24:基金欄只留投信名、拿掉代號;「上次配息」「年化配息」整欄移除;
    # 原「所屬」欄與基金欄同值 → 合併成一欄,不重複)
    rows = ""
    for e in dedupe_events(events):                  # 同日同投信只列一次(user 2026-08-24)
        ex = e["ex_date"]
        cf_zh, cf_cls = _CONF.get(e.get("confidence"), ("—", "med"))
        rows += (
            f'<tr><td class="tnum est">{ex.month}/{ex.day}</td>'
            f'<td class="name"><span class="house">'
            f'<span class="dot" style="background:{_e(_color(e.get("house")))}"></span>'
            f'<b>{_e(_chip_label(e))}</b></span></td>'
            f'<td class="tnum muted">{_e(_fmt_pay_window(ex))}</td>'
            f'<td><span class="cf {cf_cls}">{cf_zh}</span></td></tr>')
    if not rows:
        rows = '<tr><td colspan="4" class="muted">本月你的基金無推估除息基準日（或資料不足）。</td></tr>'

    # user 2026-08-24「沒有配息的整段移除」:累積型/查無配息的基金本來就不會配息,不需佔版面提醒。
    # ⚠️ 下方 `unpredictable`(有配息史但本月推不出)**保留** —— 那是「可能有配息但算不出來」,
    # 靜默吃掉會讓你誤以為當月沒事(§1 誠實揭露)。兩者語意不同,不可一起砍。
    exc_html = ""

    # 稽核 M3:有配息史但本月無法推估(節奏不規則 / 疑停配過舊)→ 誠實揭露,不靜默消失
    unpredictable = cal.get("unpredictable") or []
    unp_html = ""
    if unpredictable:
        names = "、".join(f'<b>{_e(x.get("code"))}</b> {_e(x.get("name"))}' for x in unpredictable)
        unp_html = (f'<div class="excluded"><span class="x" style="color:var(--accent-ink)">無法推估</span>'
                    f'以下基金<b>有配息史但本月推不出除息基準日</b>'
                    f'（節奏不規則 / 最近無配息疑停配 / 本月錨定日遇連假無法校正），'
                    f'請自行至基金公司網站確認：{names}。</div>')

    sample_badge = '<span class="badge sample">樣張 · 日期為推估</span>' if is_sample else \
                   '<span class="badge sample">日期為推估</span>'

    return f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{_e(title)}</title>
<style>{_CSS}{_CSS_COMPACT if compact else ''}</style></head><body><div class="wrap">
<header><p class="eyebrow">追蹤清單 ∪ 持倉 · 每月月初更新</p>
<h1>{_e(title)}</h1>
<p class="sub">依你的基金過往配息節奏，推估本月除息基準日與配息入帳日。加減基金 → 下月自動更新。</p>
<div class="badges"><span class="badge month tnum">民國{roc}年 {m}月（{y}）</span>{sample_badge}</div>
<ul class="legend">{legend_html}</ul></header>
<div class="cal-scroll"><div class="cal">
<div class="dow"><div>{_DOW[0]}</div><div>{_DOW[1]}</div><div>{_DOW[2]}</div><div>{_DOW[3]}</div><div>{_DOW[4]}</div><div class="sat">{_DOW[5]}</div><div class="sun">{_DOW[6]}</div></div>
<div class="grid">{grid_html}</div></div></div>
<h2 class="section-t">本月除息基準日明細（推估）</h2>
<div class="tbl-scroll"><table><thead><tr>
<th>除息基準日</th><th>基金</th><th>入帳(估)</th><th>信心</th>
</tr></thead><tbody>{rows}</tbody></table></div>
{exc_html}
{unp_html}
<footer class="note"><b>※ 日期為推估：</b>用你真實基金 + 各基金公司月配除息節奏推算「<b>除息基準日</b>」，非官方公告。<br>
上述基金基準日皆以實際基金營業日為準。<br>
依公開說明書規定，<b>配息入帳日為除息日後一個月內</b>，入帳時間將依實際作業為準。<br>
本行事曆所示之營業日僅供參考，實際之基金營業日請參閱<b>基金公司網站公告</b>為準。</footer>
</div></body></html>"""


def render_month_calendar_png(cal: dict, *, title: str = "基金除息配息行事曆",
                              is_sample: bool = False, width: int = _PUSH_WIDTH,
                              scale: int = 2) -> bytes:
    """月曆結構 → PNG bytes(headless Chromium 截 `render_month_calendar_html` 的 `.wrap`)。

    user 2026-08-24 選「截 App 那張最像」:重用**同一份 HTML 樣板**(App 方式 A / LINE 方式 C 單一
    SSOT),故推播圖與 App 畫面一模一樣,不會走鐘。截圖 I/O **委派 L0** `infra.html_to_png`(本函式
    只組合 HTML + 呼叫,不直接開瀏覽器 → 合法下行依賴)。lazy import → App 只取 HTML 時不載入 playwright。

    Raises:
        infra.html_to_png.HtmlRenderError — playwright 缺 / Chromium 無法啟動 / 逾時(§1);
        呼叫端(每月 cron)接到後退回 Flex / 純文字,提醒仍送達。
    """
    from infra.html_to_png import html_to_png
    _html = render_month_calendar_html(cal, title=title, is_sample=is_sample, compact=True)
    # require_cjk:本圖滿版中文 —— runner 缺中文字型會整張畫成 tofu 方塊,寧可 raise 讓呼叫端退
    # Flex/純文字,也不推一張沒人看得懂的圖(§1)。
    return html_to_png(_html, width=width, scale=scale, selector=".wrap",
                       color_scheme="light", require_cjk=True)


__all__ = ["render_month_calendar_html", "render_month_calendar_png", "_HOUSE_COLOR"]
