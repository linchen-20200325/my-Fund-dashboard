# -*- coding: utf-8 -*-
"""🌍 頁 adapter：既有正式資料層結果 → `MarketPageModel`（BL-0536 rendering 批）。

資料來源（**不新增資料源、不新增 L1、不新增公式**）：
- `services.v2_tables.market_view.build_market_view`（VIX／TAIEX／S&P 500／美 10Y／美 2Y 的日頻序列；Yahoo 5y、FRED 1500 筆）；
- `services.v2_tables.market_indicator.build_market_indicator_table`（B 線：信用利差、期限利差、政策利率等，與 ui_v2 同一條讀法）。
兩者都是 L2，且由它們自己去呼叫既有 L1（`repositories/macro/yf.py`、`fred.py`）；本檔不直接 import L1（分層守衛不開洞）。
`load()` 內才 import（lazy）：import `ui_v3` 時不得連帶載入 pandas／L1（`test_ui_v3_preview_not_formal_guard` 的執行期白名單）。

規則（BACKLOG BL-0536-H2／H3 的 rendering-batch adapter 要求，逐條有測試）：
1. **取數緩衝**：`market_view` 對 Yahoo 取 5y、FRED 取 1500 筆（約 5.8 年），而最長期間是 3Y（`periods.PERIOD_MONTHS`）→ 視窗起點前至少約 2 年歷史；
   週末／休市起點因此不會被誤判成歷史不足（A2：起點當日或之前有有效觀測即涵蓋；`normalize_pair` 一字未動）。
   `FETCH_MARGIN_OK` 由測試鎖（取數範圍月數 ≥ 最長期間月數 ＋ 12）。取數範圍是 `market_view` 的常數，本檔不改。
2. **收盤值先轉 float**（`numpy.int64`／`Decimal` 會被 `periods.is_number` 當缺口）；非有限值／bool → None（缺口，不補 0）。
3. **台北時區**：經過天數一律 `tz=Asia/Taipei`（預設 None 會取 UTC 日期，可能差一天）；負經過天數照實保留（呈現層寫成不適用，不是新）。
4. **取數失敗與缺資料分開**：`系統錯誤` → `failed`（序列鍵進 `failed_keys`）；`資料未備` → `missing`。缺 FRED 金鑰 → `failed`＋`not_configured`（呈現 `⛔ 尚未設定`，不寫成取數失敗；44 之十二其二第 1 條）。
5. **日頻保證**：只吃 `market_view` 的 `_daily_close_domain`／`fred_yield_domain`（逐日收盤／逐日觀測）；B 線 `policy_rate_pct` 等非日頻序列**只用於 Secondary／依據卡的「最新值」，不進歸一化、不當日頻畫**。
6. 失敗原文（`reason`）**不進 view model**（44 P0-①：原文不上一般畫面）；只帶原因代碼。
"""
from __future__ import annotations

import math
from typing import Optional
from zoneinfo import ZoneInfo

from services.v2_domain import periods
from services.v2_domain.freshness import delay_days
from services.v2_domain.market_summary import first_screen_summary, series_freshness
from services.v2_domain.normalization import normalize_pair
from ui_v3.adapters.market_chart import REASON_FETCH_FAILED, build_comparison_card
from ui_v3.viewmodels import preview_wording as W
from ui_v3.viewmodels.common import (
    FRESH_UNDETERMINED,
    STATUS_FAILED,
    STATUS_MISSING,
    STATUS_OK,
    STATUS_UNDETERMINED,
    FactMeta,
)
from ui_v3.viewmodels.components import ChartCard, ChartPoint, ChartSeries
from ui_v3.viewmodels.market_page import (
    DEFAULT_PRIMARY_VIEW,
    DEFAULT_RATES_KEY,
    PRIMARY_VIEWS,
    RATES_CREDIT,
    RATES_KEYS,
    RATES_POLICY,
    RATES_TERM,
    VIEW_COMPARE,
    VIEW_US2Y,
    VIEW_US10Y,
    VIEW_VIX,
    DomainStatus,
    EvidenceCard,
    EvidenceChange,
    EvidenceFact,
    MarketPageModel,
    SecondaryCard,
    SeriesNote,
)

__all__ = (
    "TAIPEI", "REASON_NOT_CONFIGURED", "MISSING_FRED_API_KEY_TEXT", "load", "build_market_page",
    "to_float", "domain_state",
)

TAIPEI = ZoneInfo("Asia/Taipei")

# `ui_v3` adapters 不得 import `shared`（只開 `shared.ui_semantics`）→ 另存、測試鎖（對 `rules.REASON_NOT_CONFIGURED`／`market_indicator`）。
REASON_NOT_CONFIGURED = "not_configured"
MISSING_FRED_API_KEY_TEXT = "未設定 FRED_API_KEY"   # ＝ `market_indicator.MISSING_FRED_API_KEY`（測試鎖）

# `market_view` 四態字面（＝ `market_view.STATE_*`；測試鎖）。
_STATE_OK, _STATE_MISSING, _STATE_BIZ, _STATE_ERROR = "ok", "資料未備", "業務例外", "系統錯誤"

KEY_TAIEX, KEY_SP500, KEY_VIX, KEY_US10Y, KEY_US2Y = "taiex", "sp500", "vix", "us10y", "us2y"
_PRIMARY_DOMAIN = {VIEW_VIX: KEY_VIX, VIEW_US10Y: KEY_US10Y, VIEW_US2Y: KEY_US2Y}
_SERIES_LABEL_KEY = {KEY_TAIEX: "series_taiex", KEY_SP500: "series_sp500", KEY_VIX: "series_vix",
                     KEY_US10Y: "series_us10y", KEY_US2Y: "series_us2y"}
# B 線三條 Secondary 子序列：單位與來源標示（＝ `INDICATOR_SPECS`；測試鎖）。
_RATES_UNIT = {RATES_TERM: "pp", RATES_CREDIT: "pp", RATES_POLICY: "%"}
_RATES_SOURCE = {RATES_TERM: "FRED (T10Y2Y)", RATES_CREDIT: "FRED (BAMLH0A0HYM2)", RATES_POLICY: "FRED (FEDFUNDS)"}
_RATES_LABEL_KEY = {RATES_TERM: "rates_term_spread", RATES_CREDIT: "rates_credit_spread", RATES_POLICY: "rates_policy_rate"}
_NO_OBSERVATION = "no_observation"

# 尚未取得群組：`market_view` 的無正式來源 domain（順序＝畫面順序）→ 暫時字樣鍵。
_MISSING_DOMAINS = (
    ("taiex_volume", "missing_taiex_volume"), ("market_stats", "missing_market_stats"),
    ("nasdaq", "missing_nasdaq"), ("msci_world", "missing_msci_world"), ("msci_em", "missing_msci_em"),
    ("eps_pe_scenario", "missing_eps_pe"), ("implied_trailing_index_earnings", "missing_implied_earnings"),
)
# 各項資料狀態列：domain 鍵 → 暫時字樣鍵（先 Primary 序列，再其餘）。
_STATUS_ROWS = (
    (KEY_TAIEX, "series_taiex"), (KEY_SP500, "series_sp500"), (KEY_VIX, "series_vix"),
    (KEY_US10Y, "series_us10y"), (KEY_US2Y, "series_us2y"),
)


def load(sources) -> tuple:
    """取數（lazy import L2；L2 再呼叫既有 L1）。`sources`：L3 交進來的 mapping 清單（例 `[st.secrets, os.environ]`），只用來找 FRED 金鑰。

    順序：B 線先、`market_view` 後（同一個 Yahoo／FRED 主機共用冷卻，`market_view` 檔頭已說明）。
    回傳 `(view, table)`。L1 失敗不會在這裡拋出（兩個 L2 都把失敗轉成 `系統錯誤`／`errors`）。
    """
    from services.v2_tables import market_indicator, market_view  # lazy：import ui_v3 時不得載入 pandas／L1

    key = market_indicator.fred_api_key_from(sources)
    table = market_indicator.build_market_indicator_table(fred_api_key=key)
    view = market_view.build_market_view(fred_api_key=key)
    return view, table


def to_float(value) -> Optional[float]:
    """收盤值 → float；無效（None／bool／非數字／非有限）→ None（缺口；不補 0）。"""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def domain_state(domain: dict) -> tuple:
    """`market_view` domain → `(status, reason_code)`；取數失敗與缺資料分開。未知狀態大聲失敗（不猜）。"""
    status = domain["status"]
    if status == _STATE_OK:
        return STATUS_OK, None
    if status == _STATE_MISSING:
        return STATUS_MISSING, domain.get("reason_code") or STATUS_MISSING
    if status == _STATE_ERROR:
        if domain.get("reason") == MISSING_FRED_API_KEY_TEXT:
            return STATUS_FAILED, REASON_NOT_CONFIGURED
        return STATUS_FAILED, REASON_FETCH_FAILED
    raise ValueError(f"unsupported market_view domain status {status!r} (業務例外 is not produced for these domains)")


def _by_key(view: dict) -> dict:
    return {d["domain"]: d for d in view["domains"]}


def _points(domain: dict) -> Optional[list]:
    """ok 的 domain → `[{"obs_date", "value_num": float|None}]`；非 ok → None（缺）。"""
    if domain["status"] != _STATE_OK:
        return None
    return [{"obs_date": p["obs_date"], "value_num": to_float(p["value_num"])} for p in domain["points"]]


def _elapsed(as_of: Optional[str], fetched_at: Optional[str], tz) -> Optional[int]:
    if as_of is None or fetched_at is None:
        return None
    return delay_days(as_of, fetched_at, tz=tz)


def _meta_status(meta: FactMeta) -> str:
    return meta.status if meta.status in (STATUS_OK, STATUS_MISSING, STATUS_FAILED) else STATUS_UNDETERMINED


def _reason_for(series: ChartSeries, comparison_status: str) -> Optional[str]:
    """沒畫線序列的原因代碼；`withheld` 的真正原因只在比較層狀態（BACKLOG H3 rendering 要求 (b)）。"""
    code = series.meta.reason_code
    return comparison_status if code == "withheld" else code


def _comparison(by_key: dict, period: str):
    series = {k: _points(by_key[k]) for k in (KEY_TAIEX, KEY_SP500)}
    state = {k: domain_state(by_key[k]) for k in series}
    failed = frozenset(k for k, (s, _r) in state.items() if s == STATUS_FAILED)
    comparison = normalize_pair(series, period)
    labels = {k: W.text(_SERIES_LABEL_KEY[k]) for k in series}
    sources = {k: by_key[k].get("source") or "—" for k in series}
    card = build_comparison_card(comparison, title=W.text("title_compare"), labels=labels, sources=sources,
                                 failed_keys=failed)
    return comparison, card


def _compare_notes(comparison, card: ChartCard, by_key: dict, tz) -> tuple:
    fresh = {f.key: f for f in series_freshness(
        comparison, {k: by_key[k].get("fetched_at") for k in (KEY_TAIEX, KEY_SP500)}, tz=tz)}
    notes = []
    for result, series in zip(comparison.series, card.series):
        domain = by_key[result.key]
        info = fresh[result.key]
        notes.append(SeriesNote(
            result.key, _meta_status(series.meta), _reason_for(series, card.disclosure.status),
            info.last_obs_date, info.elapsed_days, domain.get("source"), domain.get("fetched_at")))
    return tuple(notes)


def _evidence_changes(comparison, card: ChartCard) -> tuple:
    out = []
    summary = first_screen_summary(comparison)
    for change, series in zip(summary.period_changes, card.series):
        status = _meta_status(series.meta)
        reason = None if status == STATUS_OK else _reason_for(series, card.disclosure.status)
        out.append(EvidenceChange(change.key, status, reason, change.period_change if status == STATUS_OK else None))
    return tuple(out)


def _single_primary(domain: dict, key: str, period: str, tz) -> tuple:
    """VIX／美 10Y／美 2Y 單序列檢視 → `(ChartCard, (SeriesNote,), unit)`。同一組期間切換；缺／失敗／期間不足都不畫假線。"""
    label = W.text(_SERIES_LABEL_KEY[key])
    status, reason = domain_state(domain)
    unit = domain.get("value_unit")
    source = domain.get("source")
    fetched_at = domain.get("fetched_at")
    if status != STATUS_OK:
        meta = FactMeta(status=status, source=None, as_of=None, freshness_state=FRESH_UNDETERMINED, reason_code=reason)
        card = ChartCard(label, (ChartSeries(label, meta, ()),), period=period)
        return card, (SeriesNote(key, status, reason, None, None, None, None),), unit
    sliced = periods.slice_period(_points(domain), period)
    last = sliced["last_obs"]
    if sliced["status"] == periods.STATUS_OK and source is not None:
        meta = FactMeta(status=STATUS_OK, source=source, as_of=last, freshness_state=FRESH_UNDETERMINED)
        series = ChartSeries(label, meta, tuple(ChartPoint(p["obs_date"], p["value_num"]) for p in sliced["points"]))
        note_status, note_reason = STATUS_OK, None
    else:
        reason_code = "insufficient" if sliced["status"] == periods.STATUS_INSUFFICIENT else "no_source"
        meta = FactMeta(status=STATUS_UNDETERMINED, source=source if last else None, as_of=last,
                        freshness_state=FRESH_UNDETERMINED, reason_code=reason_code)
        series = ChartSeries(label, meta, ())
        note_status, note_reason = STATUS_UNDETERMINED, reason_code
    note = SeriesNote(key, note_status, note_reason, last, _elapsed(last, fetched_at, tz), source, fetched_at)
    return ChartCard(label, (series,), period=period), (note,), unit


def _last_valid(points: list) -> Optional[dict]:
    valid = [p for p in points if p["value_num"] is not None]
    return valid[-1] if valid else None


def _spark(points: list) -> tuple:
    """近 1Y 迷你線（固定 1Y；Secondary 無期間切換）。回 `(ChartPoint…, spark_status)`；涵蓋不足不縮短冒充。"""
    sliced = periods.slice_period(points, periods.DEFAULT_PERIOD)
    if sliced["status"] == periods.STATUS_OK:
        return tuple(ChartPoint(p["obs_date"], p["value_num"]) for p in sliced["points"]), None
    return (), "insufficient"


def _secondary_from_points(key, status, reason, points, unit, source, fetched_at, tz) -> SecondaryCard:
    if status != STATUS_OK:
        return SecondaryCard(key, status, reason, None, unit, None, None, None)
    last = _last_valid(points)
    if last is None or source is None:   # 有 ok 卻沒有可用值或來源：不補（無法判定的資料問題→缺）
        return SecondaryCard(key, STATUS_MISSING, "no_observation" if last is None else "no_source", None, unit, None, None, None)
    spark, spark_status = _spark(points)
    return SecondaryCard(key, STATUS_OK, None, last["value_num"], unit, last["obs_date"],
                         _elapsed(last["obs_date"], fetched_at, tz), source, spark, spark_status)


def _indicator_series(table: dict, key: str) -> dict:
    """B 線 `market_indicator` 列 → `{status, reason, points, unit, fetched_at}`（同一觀測日取公布日最晚的一列；與 ui_v2 `rates_domain` 同讀法）。

    L2 在 `pending` 列出的鍵（第一階段刻意不取數）→ 缺資料＋該原因代碼；`errors` 有的 → 取數失敗（缺金鑰另標 `not_configured`）；
    都沒有 → 缺資料。**只讀、不寫表、不補值。**
    """
    rows = sorted((r for r in table.get("rows", []) if r["indicator_key"] == key),
                  key=lambda r: (r["obs_date"], r["release_date"]))
    by_date = {r["obs_date"]: to_float(r["value_num"]) for r in rows}
    points = [{"obs_date": d, "value_num": v} for d, v in sorted(by_date.items())]
    if _last_valid(points) is not None:
        last = _last_valid(points)["obs_date"]
        fetched = max(r["fetched_at"] for r in rows if r["obs_date"] == last)
        return {"status": STATUS_OK, "reason": None, "points": points, "unit": rows[-1].get("value_unit"),
                "fetched_at": fetched}
    errors = table.get("errors") or {}
    if key in errors:
        reason = REASON_NOT_CONFIGURED if errors[key] == MISSING_FRED_API_KEY_TEXT else REASON_FETCH_FAILED
        return {"status": STATUS_FAILED, "reason": reason, "points": [], "unit": None, "fetched_at": None}
    pending = (table.get("pending") or {}).get(key)
    return {"status": STATUS_MISSING, "reason": pending or _NO_OBSERVATION, "points": [], "unit": None,
            "fetched_at": None}


def _rates_card(table: dict, rates_key: str, tz) -> SecondaryCard:
    s = _indicator_series(table, rates_key)
    unit = s["unit"] or _RATES_UNIT[rates_key]
    return _secondary_from_points(rates_key, s["status"], s["reason"], s["points"], unit, _RATES_SOURCE[rates_key],
                                  s["fetched_at"], tz)


def _fact_from_indicator(table: dict, key: str, label_key: str) -> EvidenceFact:
    s = _indicator_series(table, key)
    if s["status"] != STATUS_OK:
        return EvidenceFact(label_key, s["status"], s["reason"], None, None, None)
    last = _last_valid(s["points"])
    return EvidenceFact(label_key, STATUS_OK, None, last["value_num"], s["unit"] or "", last["obs_date"])


def _evidence_cards(table: dict) -> tuple:
    ndc = _indicator_series(table, "leading_index")
    ndc_fact = (EvidenceFact("fact_ndc", ndc["status"], ndc["reason"], None, None, None) if ndc["status"] != STATUS_OK
                else _fact_from_indicator(table, "leading_index", "fact_ndc"))
    return (
        EvidenceCard("MKT-1", "evidence_card_1", (_fact_from_indicator(table, "vol_index", "fact_vix"),
                                                   _fact_from_indicator(table, RATES_CREDIT, "fact_credit_spread"))),
        EvidenceCard("MKT-2", "evidence_card_2", (ndc_fact,)),
        EvidenceCard("MKT-3", "evidence_card_3", (_fact_from_indicator(table, RATES_POLICY, "fact_policy_rate"),
                                                   _fact_from_indicator(table, "fx_twd_per_usd", "fact_fx"))),
    )


def _domain_row(domain: dict, label_key: str) -> DomainStatus:
    status, reason = domain_state(domain)
    return DomainStatus(domain["domain"], label_key, status, reason, domain.get("source"), domain.get("obs_date"),
                        domain.get("fetched_at"))


def build_market_page(view: dict, table: dict, *, period: str, primary_view: str = DEFAULT_PRIMARY_VIEW,
                      rates_key: str = DEFAULT_RATES_KEY, tz=TAIPEI) -> MarketPageModel:
    """`market_view` 結果＋B 線表 → 頁 view model。純函式、無 I/O。

    - 首屏「重要依據」與圖同一個 `NormalizedComparison`（基準、視窗、期間相同；不另算）。
    - `primary_view == compare` → 歸一化比較圖卡；其餘 → 單序列圖卡（同一組期間）。
    - Primary 為 VIX 時 Secondary 的 VIX 卡讓位（D1；客戶裁示 DEC-2026-11-03-06）；切回其他檢視恢復，不補入其他卡。
    """
    if period not in periods.PERIODS:
        raise ValueError(f"period must be one of {periods.PERIODS}: {period!r}")
    if primary_view not in PRIMARY_VIEWS:
        raise ValueError(f"primary_view must be one of {PRIMARY_VIEWS}: {primary_view!r}")
    if rates_key not in RATES_KEYS:
        raise ValueError(f"rates_key must be one of {RATES_KEYS}: {rates_key!r}")
    by_key = _by_key(view)
    comparison, cmp_card = _comparison(by_key, period)
    if primary_view == VIEW_COMPARE:
        primary_card, primary_notes, unit = cmp_card, _compare_notes(comparison, cmp_card, by_key, tz), None
    else:
        key = _PRIMARY_DOMAIN[primary_view]
        primary_card, primary_notes, unit = _single_primary(by_key[key], key, period, tz)

    secondary = []
    if primary_view != VIEW_VIX:
        vix = by_key[KEY_VIX]
        status, reason = domain_state(vix)
        secondary.append(_secondary_from_points(KEY_VIX, status, reason, _points(vix) or [], vix.get("value_unit") or "index",
                                                vix.get("source"), vix.get("fetched_at"), tz))
    secondary.append(_rates_card(table, rates_key, tz))

    return MarketPageModel(
        period=period, view=primary_view,
        evidence_comparable=cmp_card.disclosure.comparable, comparison_mode=comparison.mode,
        evidence_changes=_evidence_changes(comparison, cmp_card),
        primary_card=primary_card, primary_notes=primary_notes, primary_unit=unit,
        secondary=tuple(secondary), rates_key=rates_key,
        evidence_cards=_evidence_cards(table),
        missing=tuple(_domain_row(by_key[k], lk) for k, lk in _MISSING_DOMAINS),
        statuses=tuple(_domain_row(by_key[k], lk) for k, lk in _STATUS_ROWS),
    )
