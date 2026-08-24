"""ui/helpers/dividend_calendar_render.py — 除息/配息月曆 HTML 渲染(v19.443)。

純字串產生器(**零 streamlit、零 IO**),吃 `services.dividend_calendar.build_month_calendar`
的結構 → 產出自成一頁的 HTML(深/淺色皆適配)。共用於:App 內 `st.components.html` 嵌入(方式 A)、
之後 LINE 摘要附的連結 / 存檔(方式 C)。版型 = user 2026-08 核准的樣張。
"""
from __future__ import annotations

import calendar as _calendar
import html as _html

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
  font-family:"PingFang TC","Noto Sans TC","Microsoft JhengHei",-apple-system,system-ui,sans-serif;
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
table{width:100%;border-collapse:collapse;min-width:640px;font-size:14px}
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


def _e(s) -> str:
    return _html.escape(str(s if s is not None else ""))


def _color(house: str) -> str:
    return _HOUSE_COLOR.get(house, _DEFAULT_COLOR)


def _chip_label(ev: dict) -> str:
    """月曆格子內的標籤:**只顯示投信名**(user 2026-08-24:「只保留投資商的名稱,移除代碼」)。

    代號仍保留在下方「本月除息明細」表(格子求乾淨、明細求可查)。
    §1:判不出投信(`detect_house` 回 "")→ 退顯示代號,**絕不留空白 chip** 把當日除息事件藏掉。
    """
    return (str(ev.get("house") or "").strip()
            or str(ev.get("code") or "").strip()
            or "—")


def _fmt_amt(v) -> str:
    return f"{v:.4f}" if isinstance(v, (int, float)) else "—"


def _fmt_pct(v) -> str:
    return f"{v:.1f}%" if isinstance(v, (int, float)) else "—"


def render_month_calendar_html(cal: dict, *, title: str = "基金除息配息行事曆",
                               is_sample: bool = False) -> str:
    """月曆結構 → 自成一頁 HTML 字串。"""
    y, m = int(cal["year"]), int(cal["month"])
    roc = y - 1911
    first_wd, days = _calendar.monthrange(y, m)      # first_wd: Mon=0..Sun=6
    by_day = cal.get("by_day") or {}
    events = cal.get("events") or []
    excluded = cal.get("excluded") or []

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
                f'<span class="chip"><span class="dot" style="background:{_e(_color(ev.get("house")))}"></span>'
                f'<b>{_e(_chip_label(ev))}</b>'
                + ('<span class="q">?</span>' if ev.get("confidence") == "low" else "")
                + '</span>'
                for ev in evs) + '</div>'
        has = " has" if evs else ""
        cells.append(f'<div class="cell{wknd}{has}"><div class="d tnum">{d}</div>{chips}</div>')
    grid_html = "".join(cells)

    # 明細表
    rows = ""
    for e in events:
        ex, pay = e["ex_date"], e.get("pay_date_est")
        cf_zh, cf_cls = _CONF.get(e.get("confidence"), ("—", "med"))
        rows += (
            f'<tr><td class="tnum est">{ex.month}/{ex.day}</td>'
            f'<td class="name"><b>{_e(e.get("name"))}</b> <span class="muted tnum">{_e(e.get("code"))}</span></td>'
            f'<td><span class="house"><span class="dot" style="background:{_e(_color(e.get("house")))}"></span>{_e(e.get("house") or "—")}</span></td>'
            f'<td class="tnum muted">{(str(pay.month)+"/"+str(pay.day)) if pay else "—"}</td>'
            f'<td class="tnum">{_fmt_amt(e.get("last_amount"))}</td>'
            f'<td class="tnum">{_fmt_pct(e.get("last_yield"))}</td>'
            f'<td><span class="cf {cf_cls}">{cf_zh}</span></td></tr>')
    if not rows:
        rows = '<tr><td colspan="7" class="muted">本月你的基金無推估除息日（或資料不足）。</td></tr>'

    exc_html = ""
    if excluded:
        names = "、".join(f'<b>{_e(x.get("code"))}</b> {_e(x.get("name"))}' for x in excluded)
        exc_html = (f'<div class="excluded"><span class="x">已排除</span>以下持有基金<b>無月配息</b>'
                    f'（累積型 / 查無配息），故不列入 —— 這是正常的，不是漏抓：{names}。</div>')

    # 稽核 M3:有配息史但本月無法推估(節奏不規則 / 疑停配過舊)→ 誠實揭露,不靜默消失
    unpredictable = cal.get("unpredictable") or []
    unp_html = ""
    if unpredictable:
        names = "、".join(f'<b>{_e(x.get("code"))}</b> {_e(x.get("name"))}' for x in unpredictable)
        unp_html = (f'<div class="excluded"><span class="x" style="color:var(--accent-ink)">無法推估</span>'
                    f'以下基金<b>有配息史但本月推不出除息日</b>（節奏不規則 / 最近無配息疑停配），'
                    f'請自行至基金公司網站確認：{names}。</div>')

    sample_badge = '<span class="badge sample">樣張 · 日期為推估</span>' if is_sample else \
                   '<span class="badge sample">日期為推估</span>'

    return f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{_e(title)}</title>
<style>{_CSS}</style></head><body><div class="wrap">
<header><p class="eyebrow">追蹤清單 ∪ 持倉 · 每月月初更新</p>
<h1>{_e(title)}</h1>
<p class="sub">依你的基金過往配息節奏，推估本月除息日與配息入帳日。加減基金 → 下月自動更新。</p>
<div class="badges"><span class="badge month tnum">民國{roc}年 {m}月（{y}）</span>{sample_badge}</div>
<ul class="legend">{legend_html}</ul></header>
<div class="cal-scroll"><div class="cal">
<div class="dow"><div>{_DOW[0]}</div><div>{_DOW[1]}</div><div>{_DOW[2]}</div><div>{_DOW[3]}</div><div>{_DOW[4]}</div><div class="sat">{_DOW[5]}</div><div class="sun">{_DOW[6]}</div></div>
<div class="grid">{grid_html}</div></div></div>
<h2 class="section-t">本月除息明細（推估）</h2>
<div class="tbl-scroll"><table><thead><tr>
<th>除息</th><th>基金</th><th>所屬</th><th>入帳(估)</th><th>上次配息</th><th>年化配息</th><th>信心</th>
</tr></thead><tbody>{rows}</tbody></table></div>
{exc_html}
{unp_html}
<footer class="note"><b>※ 日期為推估：</b>用你真實基金 + 各基金公司月配除息節奏推算，非官方公告。
依公開說明書，<b>配息入帳日為除息日後一個月內</b>，實際依基金公司作業為準；
除息日與基金營業日請以<b>基金公司網站公告</b>為準。</footer>
</div></body></html>"""


def render_month_calendar_png(cal: dict, *, title: str = "基金除息配息行事曆",
                              is_sample: bool = False, width: int = 820, scale: int = 2) -> bytes:
    """月曆結構 → PNG bytes(headless Chromium 截 `render_month_calendar_html` 的 `.wrap`)。

    user 2026-08-24 選「截 App 那張最像」:重用**同一份 HTML 樣板**(App 方式 A / LINE 方式 C 單一
    SSOT),故推播圖與 App 畫面一模一樣,不會走鐘。截圖 I/O **委派 L0** `infra.html_to_png`(本函式
    只組合 HTML + 呼叫,不直接開瀏覽器 → 合法下行依賴)。lazy import → App 只取 HTML 時不載入 playwright。

    Raises:
        infra.html_to_png.HtmlRenderError — playwright 缺 / Chromium 無法啟動 / 逾時(§1);
        呼叫端(每月 cron)接到後退回 Flex / 純文字,提醒仍送達。
    """
    from infra.html_to_png import html_to_png
    _html = render_month_calendar_html(cal, title=title, is_sample=is_sample)
    # require_cjk:本圖滿版中文 —— runner 缺中文字型會整張畫成 tofu 方塊,寧可 raise 讓呼叫端退
    # Flex/純文字,也不推一張沒人看得懂的圖(§1)。
    return html_to_png(_html, width=width, scale=scale, selector=".wrap",
                       color_scheme="light", require_cjk=True)


__all__ = ["render_month_calendar_html", "render_month_calendar_png", "_HOUSE_COLOR"]
