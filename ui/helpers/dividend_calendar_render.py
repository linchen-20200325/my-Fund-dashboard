"""ui/helpers/dividend_calendar_render.py — 除息基準日/配息月曆 HTML 渲染(v19.537)。

純字串產生器(**零 streamlit、零 IO**),吃 `services.dividend_calendar.build_month_calendar`
的結構 → 產出自成一頁的 HTML(深/淺色皆適配)。共用於:App 內 `st.components.html` 嵌入(方式 A)、
之後 LINE 摘要附的連結 / 存檔(方式 C)。版型 = user 2026-08 核准的樣張。

v19.532:頁尾多一行**假日表降級警語**(僅在 `cal["holiday_calendar"] == "weekend_only"` 時出現)。
文案 SSOT 在 L2 `services.dividend_calendar.holiday_calendar_note`,與純文字摘要 / LINE Flex 同一句。

v19.533 §15 顯示層(user 2026-08-26 拍板):
  §15.2 明細表欄位正名 —— 「除息基準日」→ **「預估基準日」**、「信心」→ **「誤差」**。
        「預估」二字必須出現在**欄頭**(user 明確要求),不可只放頁尾免責。
        「高/中/低」三級徽章(舊 `.cf` 樣式與 `_CONF` 對照表)一併刪除 —— 留著等於留一條漂回去的路。
  §15.3 推不出日期的基金**保留可見**:圖例留色 + 月曆格**正下方**一排灰虛線 chip
        (`施羅德 · 上次 7/29`)+ 明細表仍列一行(預估基準日欄寫「—」)。
        ⚠️ **日期格子內不放任何東西** —— 我們確實不知道是哪天,放進格子等於發明位置。
  §15.4 **全部**推不出 → 換標題 / 副標 / 版面(**不畫空月曆格**),改逐檔一列的「待確認清單」。
  §15.5 待確認區塊末尾點名 —— 本次只做點名,不做手動輸入儲存(§-1 不主動擴散)。

v19.534 顯示層複驗回修(總管 2026-08-26 實測 + 實看 v533 三張圖後裁示):
  裁示 2  月曆格 chip 的低信心「?」**移除**:整張圖沒有一處解釋它,且會與誤差帶互相矛盾
          (同一檔可能同時「?」+「±0 天」)。一個訊號、一個地方 —— 誠實訊號是誤差帶。
  追加 7  副標 / 明細表標題 / 虛線 chip 標籤的「本月」→ **實際目標月**(走 `month_label`,
          與徽章同一個月份變數)。推播每月 28 號推下個月,「本月」在那個情境是錯的。
  追加 8  「上次 M/D」離目標月超過半年 → 帶年份(L2 `fmt_last_ex`)。
  追加 9  原因欄:版面有獨立「上次實際基準日」欄時不重複帶日期(L2 `reason_display`)。
  必改 1  誤差帶改 90 分位,頁尾配一句 `ERR_BAND_FOOTNOTE` 說明它憑什麼。

v19.535 顯示層收尾(總管 2026-08-26 實看 v534 三張圖後):
  待辦 1  誤差帶為「僅供參考」的列,**日期不加粗**(`.d-soft`)—— 粗體日期會被讀成
          確定日期,旁邊那個灰標籤壓不住它。日期本身照留(user 明確要求),降的是字重。
  待辦 2  待確認清單依「同一句說明」**分組**:同句提到組上方一行,列內只留
          「投信名 · 上次實際基準日」;單檔成組維持逐列寫法(不為 1 檔開組標題)。
  待辦 3  空月文案的「本月」→ 實際目標月(L2 `empty_month_note`,與追加 7 同病)。

v19.537 §16.1「入帳(估)」欄改用**逐檔**到帳窗(`_fmt_pay_window` 改吃 event 而非 ex):
  L2 早就逐檔算好了間隔,但本檔原本一律呼叫通用 `pay_window(ex)`(基準日 +5~7 營業日)——
  逐檔值 production 0 caller。實測通用窗對 user 5 檔真實配息表有 32% 的實際到帳日落在窗外
  (安聯 20/20 全落在窗外)。改後 walk-forward 命中 69.0% → 93.1%。
  **欄位、欄頭、版面一律未動** —— 同一格裡把對三分之一的人是錯的值換成對的值。
  該檔無發放紀錄 → 仍退回通用窗(§1 不借別檔的間隔補位)。

v19.536:§15.4「全部推不出」版型的 **H1** 也吃實際目標月(L2 `all_unpred_title`)——
追加 7 收了副標 / 明細表標題 / chip 標籤 / LINE 首行四處,獨漏這個標題常數。
"""
from __future__ import annotations

import calendar as _calendar
import html as _html

from services.dividend_calendar import (
    ALL_UNPRED_SUB_1,
    ALL_UNPRED_SUB_2,
    ERR_BAND_FOOTNOTE,
    PENDING_ASK_NOTE,
    PENDING_SECTION_TITLE,
    all_unpred_title,
    dedupe_events,
    display_label,
    empty_month_note,
    group_has_shared_note,
    group_unpredictable,
    holiday_calendar_note,
    is_all_unpredictable,
    month_label,
    pay_window,
    pending_line,
    reason_display,
)

_TITLE_DEFAULT = "基金除息配息行事曆"      # 預設標題(§15.4 全部推不出時整組換掉)

# ── §15.1 誤差帶顯示切點(顯示邏輯留 L3;分位數本身在 L2 `estimate_error_band`)──────
# user 2026-08-26 廢止畫面上的「高/中/低」三級標籤 —— 它回答不了「哪天該去看帳戶」,
# 而且三級的單調性只建立在 3 個樣本上,脆。改成該檔**自己的**歷史算出來的 ±N 天。
# ⚠️ 引擎的 `confidence` 沒動,仍是閘門與 §13.6 硬門檻的依據,只是不再直接顯示。
_ERR_BAND_EXACT = 0        # E = 0        → 「±0 天」
_ERR_BAND_DAYS_MAX = 2     # E <= 2       → 「±E 天」
_ERR_BAND_WEEK_MAX = 7     # E <= 7       → 「±1 週」
# E > 7 或 None(證據不足)→ 不給數字。§1:借用別檔的準確度填一個看似合理的 ±N = 捏造。
_ERR_BAND_NA_TEXT = "僅供參考"
_ERR_BAND_NA_CLASS = "na"           # 「僅供參考」那一階的 CSS class(下面的日期降階也認這個值)

# ── v19.535 待辦 1:「僅供參考」的列,日期**不加粗**(總管 2026-08-26 實看 v534_A 圖後裁示)──
# 粗體 + accent 色的日期會被當成**確定日期**讀,旁邊那個灰色小標籤壓不住它。
# 兩個 class 成對放在這裡,是為了讓「哪一階配哪種字重」一眼看得完,不必翻 CSS 才知道。
_DATE_STRONG_CLASS = "est"          # 誤差帶給得出數字 → 強調(accent + 700)
_DATE_SOFT_CLASS = "d-soft"         # 誤差帶「僅供參考」→ 降一階,與標籤同權重

# 投信分色(中間調,深/淺底都看得清;判不出 → 預設灰)
_HOUSE_COLOR = {
    "聯博": "#2e8079", "安聯": "#b5771f", "摩根": "#3f63ab", "施羅德": "#8a5680",
    "瀚亞": "#4f8248", "富蘭克林": "#c06a24", "貝萊德": "#43506b", "高盛": "#a8862f",
    "PIMCO": "#3d7ba8", "野村": "#a1444e", "景順": "#5a7a3a", "富達": "#4a8a6a",
    "法巴": "#5a6b8a", "M&G": "#8a5a3a", "復華": "#7a5a8a", "國泰": "#2f7d6a", "群益": "#a86a3a",
}
_DEFAULT_COLOR = "#6b7280"
_DOW = ["一", "二", "三", "四", "五", "六", "日"]

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
.section-t{font-size:13px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-faint);font-weight:700;margin:28px 0 12px}
.tbl-scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;min-width:360px;font-size:14px}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line-soft)}
thead th{font-size:12px;letter-spacing:.04em;color:var(--ink-faint);font-weight:700;border-bottom:1px solid var(--line)}
tbody tr:last-child td{border-bottom:none}
td.name b{font-weight:700}
.house{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;color:var(--ink-soft);white-space:nowrap}
thead th{white-space:nowrap}
.est{color:var(--accent-ink);font-weight:700}
/* v19.535 待辦 1:誤差帶是「僅供參考」(帶寬 > 7 天 或 證據不足)的那一列,日期**降一階** ——
   不加粗、不上 accent 色,與同列其餘欄位同字重同色階。
   為什麼(總管 2026-08-26 實看 `v534_A_normal_2026-09.png`):粗體 + 強調色的日期會被當成
   **確定日期**讀,旁邊那個灰色「僅供參考」小標籤壓不住它。實例:施羅德 2026-09 印 9/30,
   但它的規律是「每月最後一個星期四」= 9/24,那一筆很可能就是錯的 —— 它之所以印得出來,
   是因為引擎閘門看的是 in-sample 復現率,而它真正的 walk-forward 誤差帶是 ±11 天。
   兩個訊號不一致時信 out-of-sample 那個(它才是被驗證過的表現)。§1:視覺權重必須與
   誠實度一致,不能讓「錯得看起來很確定」。⚠️ 日期本身**照常顯示**(user 明確要求「留」,
   且該檔 6 次裡 4 次是準的,仍有參考價值)—— 這裡降的是字重,不是資訊。 */
.d-soft{color:var(--ink-soft);font-weight:400}
.muted{color:var(--ink-faint)}
/* §15.1 誤差欄:取代原本的「高/中/低」信心徽章 */
.eb{font-size:11px;font-weight:700;padding:2px 8px;border-radius:999px;white-space:nowrap;display:inline-block}
.eb.exact{background:var(--ok-bg);color:var(--ok)}
.eb.days{background:var(--exclude-bg);color:var(--ink-soft)}
.eb.week{background:var(--accent-soft);color:var(--accent-ink)}
.eb.na{color:var(--ink-faint);border:1px dashed var(--line)}
/* §15.3 推不出日期的基金:月曆格**正下方**一排灰虛線 chip(日期格內不放任何東西)*/
.pending-lab{font-size:11.5px;letter-spacing:.04em;color:var(--ink-faint);font-weight:700;margin:14px 0 0}
.pending{display:flex;flex-wrap:wrap;gap:8px;margin:7px 0 0;padding:0;list-style:none}
.pending li{display:inline-flex;align-items:center;gap:7px;font-size:12.5px;font-weight:600;padding:4px 10px;border-radius:8px;border:1px dashed var(--line);color:var(--ink-faint);background:transparent}
tr.pend td{color:var(--ink-faint)}
tr.pend td.why{white-space:normal;line-height:1.55;font-size:12.5px}
/* v19.535 待辦 2:待確認清單的**組說明**列 —— 同一句原因只在該組上方講一次,
   組內各列只留「投信名 · 上次實際基準日」(原本 5 檔同原因 = 同一句印 5 遍)。 */
tr.grp td{color:var(--ink-soft);white-space:normal;line-height:1.55;font-size:12.5px;
  padding-top:14px;border-bottom:1px solid var(--line)}
tr.grp:first-child td{padding-top:9px}
.ask{margin-top:12px;font-size:12.5px;color:var(--ink-faint)}
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
.eb{font-size:13px;padding:2px 9px}
tr.pend td.why{font-size:13px}
tr.grp td{font-size:13px}
.pending-lab{font-size:13px;margin-top:12px}
.pending li{font-size:13px;padding:4px 9px}
.ask{font-size:13px}
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
    本函式只負責補上顯示用的顏色。

    v19.534 裁示 2:原本還回一個 `low` 旗標,格子裡會渲染成一個「?」上標 —— **整個移除**。
    理由(總管 2026-08-26):(a)「?」在整張圖(含圖例、頁尾)**沒有任何一處解釋**;
    (b) 它會與 §15.1 誤差帶**互相矛盾** —— 同一檔可能同時掛「?」(confidence=low)與
    「±0 天」(error_band=0),兩個訊號不同源卻擺在一起。**一個訊號、一個地方**:
    誠實訊號現在是誤差帶,它在明細表。
    ⚠️ 引擎的 `confidence` 一個字都沒動(仍是 §3 閘門與 §13.6 硬門檻的依據),
    移除的只是**畫面痕跡** —— 旗標不再算、不再傳,才不會留一條漂回去的路。
    """
    return [{"label": _chip_label(_ev), "color": _color(_ev.get("house"))}
            for _ev in dedupe_events(evs)]


def _fmt_pay_window(ev: dict) -> str:
    """事件 → 入帳推估「區間」字串(如 `8/22~8/26`)。口徑 SSOT 全在 L2,本函式只負責排版。

    **優先用該檔自己的到帳窗**(`pay_window_est`,L2 §16.1 由該檔自己的「基準→發放」間隔
    p10~p90 算出);該檔沒有發放紀錄才退回通用窗 `pay_window`(基準日 +5~7 個營業日)。

    ⚠️ **v19.537 修的就是這裡**(實測,非推測):`pay_window_est` 這個值 L2 早就逐檔算好了,
    但本函式原本簽名吃 `ex`、直接呼叫通用窗,逐檔值**從頭到尾沒有任何 caller** ——
    畫面上所有基金一律顯示同一套 +5~7 營業日。對 user 的 5 檔真實配息表 walk-forward:
    通用窗命中 40/58 = 69.0%,逐檔窗 54/58 = **93.1%**(寬度 4.1 → 4.5 天,幾乎沒變寬);
    安聯 TLZF9 **0/12 → 11/12**(它自己的間隔是 5 個日曆日,通用窗整段偏晚)。
    「哪天該去看帳戶」正是這一欄唯一要回答的問題。

    §1:兩種窗都算不出(ex 非日期)→ 「—」,不捏造日期。
    """
    _w = ev.get("pay_window_est") or pay_window(ev.get("ex_date"))
    if not _w:
        return "—"
    _lo, _hi = _w
    return f"{_lo.month}/{_lo.day}~{_hi.month}/{_hi.day}"


def _err_band_label(band) -> tuple:
    """§15.1 誤差帶(天)→ (顯示字串, CSS class)。

    E = 0 → 「±0 天」;E <= 2 → 「±E 天」;E <= 7 → 「±1 週」;
    E > 7 **或 None(證據不足)** → 「僅供參考」—— **不給數字**。
    §1:證據不足時填一個看似合理的 ±N(例如全站平均)= 讓沒把握的看起來有把握,是捏造。
    """
    if band is None:
        return _ERR_BAND_NA_TEXT, _ERR_BAND_NA_CLASS
    try:
        _b = int(band)
    except (TypeError, ValueError):
        return _ERR_BAND_NA_TEXT, _ERR_BAND_NA_CLASS   # 壞值 → 誠實退「僅供參考」,不猜
    if _b <= _ERR_BAND_EXACT:
        return "±0 天", "exact"
    if _b <= _ERR_BAND_DAYS_MAX:
        return f"±{_b} 天", "days"
    if _b <= _ERR_BAND_WEEK_MAX:
        return "±1 週", "week"
    return _ERR_BAND_NA_TEXT, _ERR_BAND_NA_CLASS


def _pending_why(u: dict, *, has_date_column: bool = False,
                 year=None, month=None) -> str:
    """待確認基金的「原因」欄文字。是否補「(上次 X)」由**版面**決定,判斷在 L2。

    v19.534 追加 9:版面有獨立的「上次實際基準日」欄時(全空版型三欄表)→ 不補,
    否則同一個日期在同一列講兩次,5 檔同原因時等於同一句話複製 5 遍,在 560px
    推播圖上佔掉大半版面。明細表的日期欄是「—」→ 補。
    ⚠️ 這裡**不做字串比對砍尾巴** —— 文案一改比對就悄悄失效;知識在 L2 `reason_display`。
    ⚠️ 跨年帶年份(追加 8)也在 L2,與虛線 chip 同一份規則。
    """
    return reason_display(u, has_date_column=has_date_column, year=year, month=month)


def _legend_html(events: list, unpredictable: list) -> str:
    """圖例:本月出現的投信(去重保序)。

    §15.3:**推不出日期的基金也要留在圖例裡** —— 原本只掃 events,一旦某檔推不出,
    它的顏色會整個從圖例消失,視覺系統斷裂(user 會以為這檔基金被移除了)。
    """
    seen, legend = set(), []
    for e in [*events, *unpredictable]:
        h = e.get("house") or ""
        key = h or e.get("code")
        if key not in seen:
            seen.add(key)
            legend.append((h or e.get("code"), _color(h)))
    return "".join(
        f'<li><span class="dot" style="background:{_e(c)}"></span>{_e(h)}</li>' for h, c in legend)


def _pending_chips_html(unpredictable: list, *, year=None, month=None) -> str:
    """§15.3 月曆格**正下方**一排灰虛線 chip:`施羅德 · 上次 7/29`。

    ⚠️ **日期格子內不放任何東西** —— 我們確實不知道是哪一天,把上個月的日期放進格子
    等於發明位置(月底型一猜就錯一整輪,正是本次要修的病)。
    ⚠️ chip 上寫的是**上一次的實際基準日**(事實),不是本月預估;「上次」二字不可省。
    虛線 + 灰字 + 不在格子裡,三個訊號一起說「這是參考,不是本月的答案」。
    """
    if not unpredictable:
        return ""
    _items = "".join(
        f'<li><span class="dot" style="background:{_e(_color(u.get("house")))}"></span>'
        f'{_e(pending_line(u, year=year, month=month))}</li>' for u in unpredictable)
    # v19.534 追加 7:標籤原寫「本月」,但推播每月 28 號推的是**下個月** → 用實際目標月。
    return (f'<p class="pending-lab">{_e(month_label(year, month))}'
            f'推不出日期（顯示上次實際基準日，僅供參考）</p>'
            f'<ul class="pending">{_items}</ul>')


def _detail_rows_html(events: list, unpredictable: list, *, year=None, month=None) -> str:
    """明細表列:先列推得出的(帶預估基準日 + 誤差),再列推不出的(§15.3 仍列一行)。"""
    rows = ""
    for e in dedupe_events(events):                  # 同日同投信只列一次(user 2026-08-24)
        ex = e["ex_date"]
        _eb_txt, _eb_cls = _err_band_label(e.get("error_band"))
        # v19.535 待辦 1:誤差帶「僅供參考」→ 日期降一階(不加粗、不上 accent 色),
        # 讓視覺權重與那個標籤一致。判斷吃 `_err_band_label` 回的 class,不另做一次門檻比較
        # —— 兩邊各判一次遲早會漂(例如只改了切點常數卻忘了字重那一側)。
        _date_cls = (_DATE_SOFT_CLASS if _eb_cls == _ERR_BAND_NA_CLASS else _DATE_STRONG_CLASS)
        rows += (
            f'<tr><td class="tnum {_date_cls}">{ex.month}/{ex.day}</td>'
            f'<td class="name"><span class="house">'
            f'<span class="dot" style="background:{_e(_color(e.get("house")))}"></span>'
            f'<b>{_e(_chip_label(e))}</b></span></td>'
            f'<td class="tnum muted">{_e(_fmt_pay_window(e))}</td>'
            f'<td><span class="eb {_eb_cls}">{_e(_eb_txt)}</span></td></tr>')
    # §15.3:推不出的基金**仍列一行**(不是整檔消失)——「預估基準日」寫 —,「誤差」欄寫原因人話。
    for u in unpredictable:
        rows += (
            f'<tr class="pend"><td class="muted">—</td>'
            f'<td class="name"><span class="house">'
            f'<span class="dot" style="background:{_e(_color(u.get("house")))}"></span>'
            f'<b>{_e(display_label(u))}</b></span></td>'
            f'<td class="muted">—</td>'
            f'<td class="why">'
            f'{_e(_pending_why(u, has_date_column=False, year=year, month=month))}</td></tr>')
    if not rows:
        # v19.535 待辦 3:原本寫死「本月」—— 與追加 7 同病(cron 每月 28 號推的是**下個月**)。
        # 文案 SSOT 在 L2 `empty_month_note`(HTML / LINE 文字 / Flex 三處同一句),
        # 月份走 `month_label` 這一份變數,與徽章 / 副標 / 明細標題同源。
        rows = (f'<tr><td colspan="4" class="muted">'
                f'{_e(empty_month_note(year, month))}</td></tr>')
    return rows


# §15.4 待確認清單的欄數:分組版型只有兩欄(原因提到組上方);混到**單檔組**時才需要
# 第三欄放那一檔的原因。colspan 與欄頭吃同一組常數,不會一邊改一邊忘(§3.3 不寫 inline 數字)。
_PENDING_COLS_GROUPED = 2        # 基金 ｜ 上次實際基準日
_PENDING_COLS_WITH_REASON = 3    # 基金 ｜ 上次實際基準日 ｜ 原因(單檔組的逐列寫法)


def _all_unpredictable_body(unpredictable: list, *, year=None, month=None) -> str:
    """§15.4 全部推不出:**不畫空月曆格**,改「待確認清單」;同一句原因**只講一次**。

    空格子是最大的誤導來源 —— 一整片空白讀起來就是「這個月沒配息」,但事實是
    「這幾檔都會配,只是我算不出是哪一天」(§1 讓失敗看起來像成功)。

    v19.535 待辦 2(總管實看 `v534_C_all_unpred_2026-09.png` 後核准的版面變更):
    原本逐檔一列、每列各帶一次原因 —— 5 檔全 `anchor_weak` 時同一句話印 5 遍,
    每列還換行成 2 行,在 560px 推播圖上佔掉大半版面。改成:
      · **多檔同句** → 說明句提到該組**上方一行**,組內各列只留「投信名 · 上次實際基準日」
      · **只有一組** → 那句話就是清單上方的唯一說明(自然落在同一條規則裡)
      · **單檔成組** → 維持逐列寫法,**不為 1 檔開一個組標題**(組標題會多佔一行;
        在「每檔成因都不同」的情境反而比原版更長 —— 分組是為了消重複,不是為了分組)
    ⚠️ 併組規則(含「為什麼分組鍵不是只有 reason_code」)在 L2 `group_unpredictable`。
    """
    _groups = group_unpredictable(unpredictable, year=year, month=month)
    # 有單檔組才需要「原因」欄;全部都是多檔組時那一欄會整欄空著 —— 留一個空欄配一個欄頭,
    # 等於為畫面上不存在的內容保留版面(也會讓 user 以為那裡漏印了東西)。
    _has_inline = any(not group_has_shared_note(_g) for _g in _groups)
    _cols = _PENDING_COLS_WITH_REASON if _has_inline else _PENDING_COLS_GROUPED
    _head = ('<th>基金</th><th>上次實際基準日</th><th>原因</th>' if _has_inline
             else '<th>基金</th><th>上次實際基準日</th>')
    rows = ""
    for _g in _groups:
        _shared = group_has_shared_note(_g)
        if _shared:                      # 組說明:同一句只在這裡講一次
            rows += (f'<tr class="grp"><td colspan="{_cols}">{_e(_g["reason"])}</td></tr>')
        for u in _g["entries"]:
            # 組內列不重複講原因;單檔組把原因留在自己那一列(混合版型才有第三欄)。
            _why_cell = ('<td class="why"></td>' if _has_inline else '') if _shared else \
                        f'<td class="why">{_e(_g["reason"])}</td>'
            rows += (
                f'<tr class="pend"><td class="name"><span class="house">'
                f'<span class="dot" style="background:{_e(_color(u.get("house")))}"></span>'
                f'<b>{_e(display_label(u))}</b></span></td>'
                f'<td class="tnum">{_e(_fmt_last_ex(u))}</td>{_why_cell}</tr>')
    return (f'<h2 class="section-t">{_e(PENDING_SECTION_TITLE)}</h2>'
            f'<div class="tbl-scroll"><table><thead><tr>'
            f'{_head}'
            f'</tr></thead><tbody>{rows}</tbody></table></div>'
            f'<p class="ask">{_e(PENDING_ASK_NOTE)}</p>')


def _fmt_last_ex(u: dict) -> str:
    """上次實際基準日 → `YYYY/M/D`;查不到 → 「不詳」(§1 不回填任何日期)。"""
    _last = u.get("last_ex")
    return f"{_last.year}/{_last.month}/{_last.day}" if _last is not None else "不詳"


def render_month_calendar_html(cal: dict, *, title: str = _TITLE_DEFAULT,
                               is_sample: bool = False, compact: bool = False) -> str:
    """月曆結構 → 自成一頁 HTML 字串(日期欄位一律為**除息基準日**推估值)。

    `compact=True`:推播圖專用版型(窄幅 + 大字 + 收緊留白),見 `_CSS_COMPACT`。
    App 網頁版用預設 False,版面完全不變。

    v19.533(§15 顯示層,user 2026-08-26 拍板)三件事:
      §15.2 明細表欄位正名:「除息基準日」→ **「預估基準日」**、「信心」→ **「誤差」**。
            「預估」二字必須出現在**欄頭**(user 明確要求),不可只放頁尾免責 ——
            頁尾沒人看,欄頭才是 user 讀數字時眼睛所在的位置。
      §15.3 推不出日期的基金**保留可見**:圖例留色 + 月曆格正下方一排灰虛線 chip
            (寫「上次 M/D」)+ 明細表仍列一行(預估基準日欄寫 —)。日期格內不放東西。
      §15.4 **全部**推不出 → 整組換標題 / 副標 / 版面(不畫空月曆),改「待確認清單」。
    """
    y, m = int(cal["year"]), int(cal["month"])
    roc = y - 1911
    events = cal.get("events") or []
    unpredictable = cal.get("unpredictable") or []
    _all_unp = is_all_unpredictable(cal)

    # §15.4:整組換標題。只在 caller 沿用預設標題時覆寫 —— 明確指定標題的 caller(存檔 / 樣張)
    # 有自己的意圖,不代它決定。
    if _all_unp and title == _TITLE_DEFAULT:
        # v19.536:H1 原寫死「本月」—— v19.534 追加 7 把副標 / 明細表標題 / chip 標籤 /
        # LINE 首行都換成實際目標月時獨漏這一處,推播(每月 28 號推下個月)時 H1 與正下方
        # 的徽章互相矛盾。月份走 L2 `all_unpred_title` → `month_label`,與 `_ml` 同源。
        title = all_unpred_title(y, m)
    # v19.534 追加 7:副標原寫「推估**本月**…」,但徽章寫的是真正的目標月,推播(每月 28 號推
    # 下個月)時同一張圖自相矛盾 —— 改用與徽章同一個月份變數(`month_label`)。
    _ml = month_label(y, m)
    _sub = (f'{_e(ALL_UNPRED_SUB_1.format(n=len(unpredictable)))}<br>'
            f'{_e(ALL_UNPRED_SUB_2)}') if _all_unp else \
        (f'依你的基金過往配息節奏，推估{_e(_ml)}的除息基準日與配息入帳日。'
         f'加減基金 → 下月自動更新。')

    legend_html = _legend_html(events, unpredictable)

    if _all_unp:
        _main = _all_unpredictable_body(unpredictable, year=y, month=m)
    else:
        first_wd, days = _calendar.monthrange(y, m)      # first_wd: Mon=0..Sun=6
        by_day = cal.get("by_day") or {}
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
                    f'<b>{_e(c["label"])}</b></span>'
                    for c in _dedupe_day_chips(evs)) + '</div>'
            has = " has" if evs else ""
            cells.append(f'<div class="cell{wknd}{has}"><div class="d tnum">{d}</div>{chips}</div>')
        grid_html = "".join(cells)
        # 明細表(user 2026-08-24:基金欄只留投信名、拿掉代號;「上次配息」「年化配息」整欄移除;
        # 原「所屬」欄與基金欄同值 → 合併成一欄,不重複)
        rows = _detail_rows_html(events, unpredictable, year=y, month=m)
        _ask = (f'<p class="ask">{_e(PENDING_ASK_NOTE)}</p>' if unpredictable else '')
        _main = (
            f'<div class="cal-scroll"><div class="cal">\n'
            f'<div class="dow"><div>{_DOW[0]}</div><div>{_DOW[1]}</div><div>{_DOW[2]}</div>'
            f'<div>{_DOW[3]}</div><div>{_DOW[4]}</div><div class="sat">{_DOW[5]}</div>'
            f'<div class="sun">{_DOW[6]}</div></div>\n'
            f'<div class="grid">{grid_html}</div></div></div>\n'
            # §15.3:虛線 chip 排在**月曆格正下方**(不是頁尾),user 看完格子就會看到它
            f'{_pending_chips_html(unpredictable, year=y, month=m)}\n'
            # v19.534 追加 7:標題同上,「本月」→ 實際目標月。
            f'<h2 class="section-t">{_e(_ml)}除息基準日明細（推估）</h2>\n'
            f'<div class="tbl-scroll"><table><thead><tr>\n'
            # §15.2:「預估」在欄頭。「誤差」取代「信心」—— user 要的是「哪天該去看帳戶」,
            # 「中信心」回答不了;±N 天回答得了。
            f'<th>預估基準日</th><th>基金</th><th>入帳(估)</th><th>誤差</th>\n'
            f'</tr></thead><tbody>{rows}</tbody></table></div>{_ask}')

    sample_badge = '<span class="badge sample">樣張 · 日期為推估</span>' if is_sample else \
                   '<span class="badge sample">日期為推估</span>'

    # v19.532 阻斷 2:假日表降級**必須看得見**。實測(user 5 檔真實配息表)有 TW 假日表時
    # 覆蓋 93.7% / 命中 89.8%,缺假日表時掉到覆蓋 61.9% / 命中 84.6%(跌破 §13.6 的 85%),
    # 而在此之前畫面一字不改 —— 準確度悄悄少一截,user 看到的仍是同樣自信的月曆(§1 違憲)。
    # 文案 SSOT 在 L2 `holiday_calendar_note`(text / Flex / 本頁尾三處同一句)。
    _cal_warn = holiday_calendar_note(cal)
    warn_html = (f'<br><b>{_e(_cal_warn)}</b>' if _cal_warn else '')

    # v19.534 必改 1 配套:「誤差」欄給的是**具體數字**,而具體數字比模糊標籤更容易被過度相信
    # —— 必須說明它是什麼、憑什麼(§1)。只在有「誤差」欄的版面出現;全空版型沒有那一欄,
    # 加了等於解釋一個畫面上不存在的東西。文案 SSOT 在 L2 `ERR_BAND_FOOTNOTE`。
    err_note_html = ('' if _all_unp else f'{_e(ERR_BAND_FOOTNOTE)}<br>')

    return f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{_e(title)}</title>
<style>{_CSS}{_CSS_COMPACT if compact else ''}</style></head><body><div class="wrap">
<header><p class="eyebrow">追蹤清單 ∪ 持倉 · 每月月底更新</p>
<h1>{_e(title)}</h1>
<p class="sub">{_sub}</p>
<div class="badges"><span class="badge month tnum">民國{roc}年 {m}月（{y}）</span>{sample_badge}</div>
<ul class="legend">{legend_html}</ul></header>
{_main}
<footer class="note"><b>※ 日期為推估：</b>用你真實基金 + 各基金公司月配除息節奏推算「<b>除息基準日</b>」，非官方公告。{warn_html}<br>
{err_note_html}
上述基金基準日皆以實際基金營業日為準。<br>
依公開說明書規定，<b>配息入帳日為除息日後一個月內</b>，入帳時間將依實際作業為準。<br>
本行事曆所示之營業日僅供參考，實際之基金營業日請參閱<b>基金公司網站公告</b>為準。</footer>
</div></body></html>"""


def render_month_calendar_png(cal: dict, *, title: str = _TITLE_DEFAULT,
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
