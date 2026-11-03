# -*- coding: utf-8 -*-
"""🌍 市場與趨勢頁（Preview；BL-0536 rendering 批；線框 `docs/v2/81`）。頁只吃 `MarketPageModel`，不取數、不計算領域值。

- `streamlit` 只在函式內 import（import `ui_v3` 時不得載入 Streamlit；守衛 `test_ui_v3_preview_not_formal_guard`）。
- 已核准字樣一律取規則表 `shared/ui_semantics/rules.py`；尚未核准的字樣一律取 `viewmodels/preview_wording.py` 並以
  `pending_span()` 輸出（`data-pending-wording` 屬性＋虛線底線，機器與人眼都可辨識）。這裡**不發明任何字樣**。
- 顏色不是唯一訊息：每個狀態 chip 都是「符號＋文字」；`tone` 只決定一個很淡的底色。⚠️ 色碼是 **Preview 暫用的樣式值**，
  不是 design token（`design/tokens.py` 值未定，視覺值待客戶驗收後重建）。
- 沒有任何方向詞、好壞詞、方向色、目標價線、threshold／band；首屏只放事實與規則表 chip：市場狀態、是否需注意各一枚 `⬜ 無法判定`＋資料新鮮度一枚 `⬜ 門檻待裁示`（首屏採 C；基準日改為圖表附近的純文字揭露行）。
"""
from __future__ import annotations

from contextvars import ContextVar
from html import escape
from typing import Optional

from shared.ui_semantics import rules
from ui_v3.pages import chart_svg
from ui_v3.shell.registry import IA_PAGES
from ui_v3.viewmodels import preview_wording as W
from ui_v3.viewmodels.common import STATUS_FAILED, STATUS_MISSING, STATUS_OK, STATUS_UNDETERMINED
from ui_v3.viewmodels.components import ChartCard
from ui_v3.viewmodels.market_page import (
    DEFAULT_PRIMARY_VIEW,
    DEFAULT_RATES_KEY,
    PRIMARY_VIEWS,
    RATES_KEYS,
    VIEW_COMPARE,
    DomainStatus,
    EvidenceFact,
    MarketPageModel,
    SecondaryCard,
    SeriesNote,
)

PAGE_TITLE = next(p.title for p in IA_PAGES if p.slug == "mkt")
DEFAULT_PERIOD = "1Y"
PERIODS = ("3M", "6M", "1Y", "3Y")
KEY_PERIOD, KEY_VIEW, KEY_RATES = "uv3_mkt_period", "uv3_mkt_view", "uv3_mkt_rates"
_VIEW_LABEL_KEY = {"compare": "view_compare", "vix": "view_vix", "us10y": "view_us10y", "us2y": "view_us2y"}

# Preview 暫用樣式（不是 design token）。
CSS = """
<style>
.block-container,.stMainBlockContainer{padding-top:3.4rem !important}
.block-container{max-width:1100px;padding-left:16px;padding-right:16px;padding-top:3.4rem}
h1{font-size:1.7rem !important;padding:.2rem 0 !important}
h3{font-size:1.2rem !important}
.uv3-pending{border-bottom:1px dashed rgba(128,128,128,.8)}
.uv3-chip{display:inline-block;border-radius:12px;padding:1px 10px;font-size:14px;border:1px solid rgba(128,128,128,.45);
  background:rgba(128,128,128,.12);margin:1px 6px 1px 0;white-space:normal}
.uv3-tone-red{border-color:#c0392b;background:rgba(192,57,43,.12)}
.uv3-tone-yellow{border-color:#b7791f;background:rgba(183,121,31,.14)}
.uv3-row{margin:.25rem 0;line-height:1.55}
.uv3-label{font-size:13px;opacity:.75;margin-right:6px}
.uv3-note{font-size:13px;opacity:.85;line-height:1.5;margin:.15rem 0}
.uv3-card{border:1px solid rgba(128,128,128,.35);border-radius:8px;padding:10px 12px;margin-bottom:8px}
.uv3-card h4{margin:0 0 4px 0;font-size:15px}
.uv3-metric{font-size:20px;margin:2px 0}
.uv3-chart{width:100%;max-width:720px;height:auto;display:block}
.uv3-spark{width:160px;height:40px;display:block;margin:4px 0}
</style>
"""


# ───────────────────────────── 小工具（純字串） ─────────────────────────────

def chip(key: str, label: Optional[str] = None, *, label_html: Optional[str] = None) -> str:
    """規則表一列 → chip HTML（符號＋字樣；`label`／`label_html` 只用在 fetch_failed／not_configured 的組合形式）。"""
    entry = rules.entry(key)
    inner = label_html if label_html is not None else escape(label if label is not None else entry.wording)
    return f'<span class="uv3-chip uv3-tone-{entry.tone}" data-status-key="{escape(key)}">{inner}</span>'


def failed_text(label: str) -> str:
    return rules.FETCH_FAILED_SCREEN_FORM.replace("<中文資料類>", label)


def not_configured_html() -> str:
    """第一次完整句：`⛔ 利率資料來源尚未設定`（客戶 2026-11-03 核准字樣，`DEC-2026-11-03-09`）。

    「哪一項」用使用者看得懂的資料類別字樣，**不得**是環境變數名或設定鍵名。本頁只有「利率資料來源」這一項會走到這裡；
    frozen 44 的句型 `NOT_CONFIGURED_FORM` 不改、不在這裡使用。
    """
    return escape(rules.NOT_CONFIGURED_RATES_SOURCE_TEXT)


_REASON_WORDING = {
    "missing": "reason_missing", "insufficient": "insufficient", "no_common_base": "reason_no_common",
    "too_few_common_days": "reason_few_common", "too_few_points": "reason_few_points",
    "no_source": "reason_no_source", "no_observation": "reason_no_observation",
}


def reason_span(code: Optional[str]) -> str:
    """原因代碼 → 暫時字樣。未知代碼一律走 `reason_unknown`；內部代碼不上畫面。"""
    return W.span(_REASON_WORDING.get(code or "", "reason_unknown"))


# 「尚未設定：<哪一項>」的「哪一項」一頁只交代一次（44 之七其二第 3 條）：render() 期間第一次出現寫完整句，其餘位置只寫狀態族
# `⛔ 尚未設定`。`active` 只在 render() 內為真；render() 以外直接呼叫輔助函式時一律寫完整句（不影響單元測試與其他呼叫端）。
# 狀態放 ContextVar（每個執行緒／context 各自一份；Streamlit 多 session 共用模組，不得用模組層可變全域）。
_NC_STATE: ContextVar[Optional[dict]] = ContextVar("uv3_mkt_not_configured_state", default=None)


def _not_configured_chip() -> str:
    state = _NC_STATE.get()
    if state is not None and state["seen"]:
        return chip("not_configured")
    if state is not None:
        state["seen"] = True
    return chip("not_configured", label_html=not_configured_html())


def status_html(status: str, reason: Optional[str], label_key: str) -> str:
    """非 ok 的狀態 → HTML。缺資料／取數失敗／尚未設定／無法判定各自獨立，不互相冒充。"""
    label = W.text(label_key)
    if status == STATUS_MISSING:
        return chip("missing")
    if status == STATUS_FAILED:
        if reason == "not_configured":
            return _not_configured_chip()
        return chip("fetch_failed", failed_text(label))
    if status == STATUS_UNDETERMINED:
        extra = W.span("insufficient") if reason == "insufficient" else reason_span(reason)
        return chip("undetermined") + extra
    raise ValueError(f"status_html 只處理非 ok 狀態：{status!r}")


def fmt_change(value: float) -> str:
    return f"{value:+.2f}%"


def fmt_value(value: float, unit: Optional[str], decimals: int = 2) -> str:
    suffix = "" if unit in (None, "", "index") else unit
    return f"{value:,.{decimals}f}{suffix}"


# 依據卡各指標的小數位數（44 第三節 3.1 規則欄：波動度指數 1 位、信用利差 2 位、政策利率 2 位、新臺幣對美元匯率 3 位）。
# 領先／同時指標的位數 44 沒有定（47 Q-13）：不替它挑＝不套用 2 位預設，有值時照原值轉字串、不四捨五入（`_raw_value`）；目前兩鍵皆 Missing。
_FACT_DECIMALS = {"fact_vix": 1, "fact_credit_spread": 2, "fact_policy_rate": 2, "fact_fx": 3}


def _raw_value(value: float, unit: Optional[str]) -> str:
    """位數未裁示的指標：照原值轉字串（不四捨五入、不補位數、不加千分位）。"""
    suffix = "" if unit in (None, "", "index") else unit
    return f"{value}{suffix}"


def elapsed_html(label: str, as_of: Optional[str], elapsed: Optional[int]) -> str:
    """圖下資料日一行：日期與經過天數只在圖卡出現；負值＝不適用（取得時間早於觀測日），不得顯示「-N 日」、不得當成新。"""
    if as_of is None:
        return ""
    if elapsed is None:
        return W.span("data_date_no_elapsed", label=label, date=as_of)
    if elapsed < 0:
        return (W.span("data_date_no_elapsed", label=label, date=as_of) + " "
                + f'<span class="uv3-chip uv3-tone-grey" data-status-key="not_applicable">'
                  f'{escape(rules.entry("not_applicable").wording)}{W.span("colon")}</span>' + W.span("negative_elapsed_suffix"))
    return W.span("data_date_line", label=label, date=as_of, days=elapsed)


def _label_of(key: str) -> str:
    return W.text(_label_key_of(key))


def primary_chart_html(model: MarketPageModel) -> Optional[str]:
    """Primary 圖。沒有任何畫線序列 → None（呼叫端改顯示空狀態，不畫空座標軸）。"""
    card: ChartCard = model.primary_card
    lines = []
    for index, series in enumerate(card.series):
        points = tuple((p.date, p.value) for p in series.points)
        if not any(v is not None for _d, v in points):
            continue
        last = [v for _d, v in points if v is not None][-1]
        text = f"{series.label} {last:.1f}" if card.normalized else f"{series.label} {fmt_value(last, model.primary_unit)}"
        lines.append(chart_svg.Line(points, dashed=index % 2 == 1, end_label=text))
    if not lines:
        return None
    return chart_svg.line_chart_svg(lines, aria_label=W.text("chart_aria", title=card.title, period=model.period))


def disclosure_notes(model: MarketPageModel) -> list:
    """歸一化揭露與非比較說明（HTML 片段清單）。只在比較檢視。"""
    card = model.primary_card
    d = card.disclosure
    if d is None:
        return []
    notes = []
    # 基準日不再是 chip（首屏採 C，`DEC-2026-11-03-09`）：圖表附近一行純文字揭露，字樣不變（基準日…＝100；頻率：日｜缺值不補、斷線）。
    line = W.span("disclosure_line", date=d.base_date) if d.base_date is not None else W.span("frequency_line")
    notes.append(f'<div class="uv3-note" data-disclosure="base-frequency">{line}</div>')
    issues = {i.series_key: i.reason_code for i in d.series_issues}
    if d.mode == "pair" and d.base_date is None:   # 兩條都有資料但整張不可畫：真正原因只在比較層狀態
        notes.append(f'<div class="uv3-note">{W.span_html("window_withheld_note", reason=W.span(_reason_phrase(d.status)))}</div>')
    elif d.mode in ("single", "fallback"):
        reason = _reason_phrase(next(iter(issues.values()), None) if d.mode == "single" else d.fallback_reason)
        notes.append(f'<div class="uv3-note">{W.span_html("single_fallback", reason=W.span(reason))}</div>')
    return notes


def _reason_phrase(code: Optional[str]) -> str:
    return {"missing": "reason_missing", "fetch_failed": "reason_fetch_failed", "not_configured": "reason_not_configured",
            "insufficient": "insufficient", "no_common_base": "reason_no_common",
            "too_few_common_days": "reason_few_common", "too_few_points": "reason_few_points"}.get(code or "", "reason_unknown")


def note_html(note: SeriesNote) -> str:
    """圖下一條序列：資料日一行，或（沒有資料日時）該序列的狀態。"""
    label = _label_of(note.key)
    if note.status == STATUS_OK or note.as_of is not None:
        line = elapsed_html(label, note.as_of, note.elapsed_days)
        if note.status != STATUS_OK:   # 有資料日但沒畫線：資料日照實顯示，另標原因
            line += " " + status_html(note.status, note.reason_code, _label_key_of(note.key))
        return f'<div class="uv3-row">{line}</div>'
    return f'<div class="uv3-row"><span class="uv3-label">{escape(label)}</span>{status_html(note.status, note.reason_code, _label_key_of(note.key))}</div>'


def _label_key_of(key: str) -> str:
    return {"taiex": "series_taiex", "sp500": "series_sp500", "vix": "series_vix", "us10y": "series_us10y",
            "us2y": "series_us2y"}[key]


# ───────────────────────────── 頁面區塊 ─────────────────────────────

def summary_html(model: MarketPageModel) -> str:
    # 首屏採 C（客戶 2026-11-03，`DEC-2026-11-03-09`）：「市場狀態」「是否需注意」兩列、各自欄位標籤與各自一枚 chip
    # （無正式規則時各自 `⬜ 無法判定`，語意不變、不新增規則）；符號＋文字，不只靠顏色。
    rows = [
        f'<div class="uv3-row" data-field="market_state"><span class="uv3-label">{W.span("field_market_state")}</span>'
        f'{chip("undetermined")}<span>{W.span("hero_sentence")}</span></div>',
        f'<div class="uv3-row" data-field="attention"><span class="uv3-label">{W.span("field_attention")}</span>'
        f'{chip("undetermined")}</div>',
    ]
    items = []
    for change in model.evidence_changes:
        label_key = _label_key_of(change.key)
        label = escape(W.text(label_key))
        if change.status == STATUS_OK:
            items.append(f'<span class="uv3-evidence" data-key="{escape(change.key)}">{W.span(label_key)} '
                         f'{W.span("evidence_period_change", period=model.period, change=fmt_change(change.period_change))}</span>')
        else:
            items.append(f'<span class="uv3-evidence" data-key="{escape(change.key)}">{label} '
                         f'{status_html(change.status, change.reason_code, label_key)}</span>')
    note = ""
    if not model.evidence_comparable and any(c.status == STATUS_OK for c in model.evidence_changes):
        note = f'<div class="uv3-note">{W.span("evidence_single_note")}</div>'
    rows.append(f'<div class="uv3-row"><span class="uv3-label">{W.span("evidence_label")}</span>'
                f'{W.span("separator").join(items)}</div>{note}')
    rows.append(f'<div class="uv3-row"><span class="uv3-label">{W.span("freshness_label")}</span>{chip("threshold_pending")}</div>')
    return "".join(rows)


def secondary_html(card: SecondaryCard, title_key: str, sub_label_key: Optional[str] = None) -> str:
    title = W.span(title_key)
    sub = f"{W.span('separator')}{W.span(sub_label_key)}" if sub_label_key else ""
    head = f'<div class="uv3-card" data-card="{escape(card.key)}"><h4>{title}{sub}</h4>'
    label_key = sub_label_key or "series_vix"
    if card.status != STATUS_OK:
        return head + status_html(card.status, card.reason_code, label_key) + "</div>"
    body = f'<div class="uv3-metric">{escape(fmt_value(card.value, card.unit))}</div>'
    body += f'<div class="uv3-note">{elapsed_html(W.text(label_key), card.as_of, card.elapsed_days)}</div>'
    if card.spark:
        body += chart_svg.spark_svg(tuple((p.date, p.value) for p in card.spark), aria_label=f"{W.text(title_key)} {W.text('secondary_spark_caption')}")
        body += f'<div class="uv3-note">{W.span("secondary_spark_caption")}</div>'
    elif card.spark_status == "insufficient":
        body += f'<div class="uv3-note">{W.span("secondary_spark_caption")}{W.span("colon")}{W.span("insufficient")}</div>'
    return head + body + "</div>"


def _fact_value_text(fact: EvidenceFact) -> str:
    if fact.label_key in _FACT_DECIMALS:
        return fmt_value(fact.value, fact.unit, _FACT_DECIMALS[fact.label_key])
    return _raw_value(fact.value, fact.unit)


def fact_html(fact: EvidenceFact) -> str:
    label = W.span(fact.label_key)
    if fact.status == STATUS_OK:
        return (f'<div class="uv3-row">{label} {escape(_fact_value_text(fact))}'
                f' <span class="uv3-note">{escape(fact.as_of)}</span></div>')
    return f'<div class="uv3-row">{label} {status_html(fact.status, fact.reason_code, fact.label_key)}</div>'


def status_row_html(row: DomainStatus) -> str:
    label = W.text(row.label_key)
    if row.status == STATUS_OK:
        return f'<div class="uv3-row">{W.span("status_ok_row", label=label, source=row.source or "—", date=row.as_of or "—")}</div>'
    return f'<div class="uv3-row">{W.span("label_colon", label=label)}{status_html(row.status, row.reason_code, row.label_key)}</div>'


# ───────────────────────────── 進入點 ─────────────────────────────

def selected_controls() -> tuple:
    """讀（並在第一次設定預設）目前選的 `(period, view, rates_key)`。controls 的 widget 稍後以同一組 key 畫出。"""
    import streamlit as st

    st.session_state.setdefault(KEY_PERIOD, DEFAULT_PERIOD)
    st.session_state.setdefault(KEY_VIEW, DEFAULT_PRIMARY_VIEW)
    st.session_state.setdefault(KEY_RATES, DEFAULT_RATES_KEY)
    period, view, rates = st.session_state[KEY_PERIOD], st.session_state[KEY_VIEW], st.session_state[KEY_RATES]
    return (period if period in PERIODS else DEFAULT_PERIOD, view if view in PRIMARY_VIEWS else DEFAULT_PRIMARY_VIEW,
            rates if rates in RATES_KEYS else DEFAULT_RATES_KEY)


def render(model: MarketPageModel) -> None:
    token = _NC_STATE.set({"seen": False})
    try:
        _render(model)
    finally:
        _NC_STATE.reset(token)


def _render(model: MarketPageModel) -> None:
    import streamlit as st

    md = lambda html: st.markdown(html, unsafe_allow_html=True)  # noqa: E731
    md(CSS)
    st.title(PAGE_TITLE)
    md(summary_html(model))

    st.divider()
    card = model.primary_card
    md(f'<h3>{W.span("title_compare") if model.view == VIEW_COMPARE else escape(card.title)}</h3>')
    st.radio(W.text("view_label"), PRIMARY_VIEWS, key=KEY_VIEW, horizontal=True,
             format_func=lambda v: W.text(_VIEW_LABEL_KEY[v]))
    st.radio(W.text("period_label"), PERIODS, key=KEY_PERIOD, horizontal=True)
    for note in disclosure_notes(model):
        md(note)
    chart = primary_chart_html(model)
    if chart is not None:
        md(chart)
    else:
        md(f'<div class="uv3-row">{W.span("chart_empty")}</div>')
    for note in model.primary_notes:
        md(note_html(note))
    with st.expander(W.text("source_limits_title")):
        md(source_limits_html(model))

    st.divider()
    columns = st.columns(len(model.secondary))
    for column, secondary in zip(columns, model.secondary):
        with column:
            if secondary.key == "vix":
                md(secondary_html(secondary, "secondary_vix_title"))
            else:
                st.radio(W.text("secondary_rates_title"), RATES_KEYS, key=KEY_RATES, horizontal=True,
                         format_func=lambda k: W.text(_RATES_LABEL[k]))
                md(secondary_html(secondary, "secondary_rates_title", _RATES_LABEL[secondary.key]))
    st.divider()
    md(f'<div class="uv3-note">{W.span("evidence_no_rule_note")}</div>')
    for column, evidence in zip(st.columns(len(model.evidence_cards)), model.evidence_cards):
        with column:
            md(f'<div class="uv3-card" data-card="{escape(evidence.code)}"><h4>{W.span(evidence.title_key)}</h4>'
               + "".join(fact_html(f) for f in evidence.facts) + "</div>")
    with st.expander(W.text("missing_group_title", n=len(model.missing))):
        md("".join(f'<div class="uv3-row">{escape(W.text(m.label_key))} {status_html(m.status, m.reason_code, m.label_key)}</div>'
                   for m in model.missing))
    with st.expander(W.text("status_group_title")):
        md("".join(status_row_html(s) for s in model.statuses))


_RATES_LABEL = {"term_spread_pct": "rates_term_spread", "credit_spread_pct": "rates_credit_spread",
                "policy_rate_pct": "rates_policy_rate"}


def source_limits_html(model: MarketPageModel) -> str:
    """▸ 來源與限制（層 3）：取得時間、來源、限制。失敗原文不在任何一般畫面（44 P0-①）。"""
    parts = []
    for note in model.primary_notes:
        label = _label_of(note.key)
        if note.source:
            parts.append(f'<div class="uv3-note">{W.span("source_line", label=label, source=note.source)}</div>')
        if note.fetched_at:
            parts.append(f'<div class="uv3-note">{W.span("fetched_at_line", label=label, stamp=_taipei(note.fetched_at))}</div>')
    parts.append(f'<div class="uv3-note">{W.span("limits_taiex")}</div>')
    parts.append(f'<div class="uv3-note">{W.span("limits_obs_date")}</div>')
    parts.append(f'<div class="uv3-note">{W.span("rates_obs_note")}</div>')
    return "".join(parts)


def _taipei(stamp: str) -> str:
    """ISO 取得時間 → 台北時間字串（只換時區與格式；無時區就原樣輸出，不猜）。"""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        return stamp
    return moment.astimezone(ZoneInfo("Asia/Taipei")).strftime("%Y-%m-%d %H:%M")
