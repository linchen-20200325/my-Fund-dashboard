# -*- coding: utf-8 -*-
"""🌍 市場與趨勢頁「視覺層級」的模型（純函式；零 streamlit import、零網路、零舊樹 import）。

BL-0525 Batch C（客戶 2026-10-30 核准 D1～D7，`DEC-2026-10-30-01`；`docs/v2/72_mkt_wireframe_batch_c.md`）。
輸入是 L2 `market_view` 的 view（五個序列＋七個 Missing）與 B 線 `market_indicator` 的 dataset 列
（BL-0517 三序列：期限利差、信用利差、政策利率）；輸出是 `page.py` 要畫的純資料模型。

本檔**只改位置與版型，不改資料語意**：
- 數字、期間算法、新鮮度文字、來源標示、缺值語意全部沿用 `market_section`／`chart`／`logic`；本檔不自算任何新指標。
- 不新增資料來源：BL-0517 三序列用的是 B 線已寫進 `market_indicator` 的列（`dataset["rows"]`），不另外取數。
- 畫面上被收合的每一項內容都留在 detail（`presentation.detail_model`），不刪資訊（`docs/v2/67` 第 5.1 節：簡化呈現不得減少決策脈絡）。

視覺層級（D7 E2；第一眼＝有沒有異常，第二眼＝主要趨勢，第三眼＝為什麼這樣顯示、資料從哪來）：
status chip → 一句主判讀 → Primary Visual（五個序列切換） → Secondary（至多 3 個迷你圖卡） → 依據卡 → details／尚未取得／provenance。
"""

from __future__ import annotations

from collections import Counter

from .. import presentation as P
from . import chart, live, logic, market_section as MS

# ───────────────────────── D1：Primary 五個序列 ─────────────────────────

PRIMARY_KEYS = ("taiex", "sp500", "vix", "us10y", "us2y")
DEFAULT_PRIMARY = "taiex"
PRIMARY_OPTION_LABELS = {"taiex": "台股", "sp500": "S&P 500", "vix": "VIX", "us10y": "美10Y", "us2y": "美2Y"}
_MODEL_FN = {"taiex": MS.taiex_model, "sp500": MS.sp500_model, "vix": MS.vix_model,
             "us10y": MS.us10y_model, "us2y": MS.us2y_model}
_YIELD_KEYS = ("us10y", "us2y")

PRIMARY_CHART_HEIGHT = 300   # px；Primary 是完整趨勢閱讀入口——手機也不壓小（D6：太擠時降 Secondary 的細節，不是壓小 Primary）

# Secondary 的迷你圖固定看近 1Y（預設期間；Primary 才有期間切換——一組控制、不讓次圖各自一組）。
SECONDARY_PERIOD = chart.DEFAULT_PERIOD
SECONDARY_RISK_TITLE = "風險｜VIX"
SECONDARY_INTL_TITLE = "國際｜S&P 500"
SECONDARY_RATES_TITLE = "利率與信用"
MAX_SECONDARY = 3   # 客戶 2026-10-30：1 Primary＋「最多」3 Secondary；3 不是 KPI

# ───────────────────────── D2：利率與信用（BL-0517 三序列；B 線已寫列的資料，不新增來源）─────────────────────────

RATES_KEYS = ("term_spread_pct", "credit_spread_pct", "policy_rate_pct")
DEFAULT_RATES = "term_spread_pct"
RATES_OPTION_LABELS = {"term_spread_pct": "期限利差", "credit_spread_pct": "信用利差", "policy_rate_pct": "政策利率"}
# 來源標示＝ L2 `INDICATOR_SPECS` 的 `source`（FRED，series id）；page 層不得 import services，故此處是顯示用常數，
# 由 `tests/ui_v2/test_mkt_overview_logic.py` 對照 `INDICATOR_SPECS` 釘住（漂移會紅燈）。
RATES_SOURCE_LABELS = {"credit_spread_pct": "FRED (BAMLH0A0HYM2)", "term_spread_pct": "FRED (T10Y2Y)",
                       "policy_rate_pct": "FRED (FEDFUNDS)"}
RATES_UNIT_TEXT = {"credit_spread_pct": "pp", "term_spread_pct": "pp", "policy_rate_pct": "%"}
TEXT_RATES_OBS_NOTE = "資料日期為 FRED 觀測日（不是公布日）；利差單位為百分點（pp），政策利率單位為百分比（%）"
TEXT_RATES_NOTES = {
    "term_spread_pct": "期限利差（FRED T10Y2Y）與主圖可切換的美 10Y、美 2Y 資訊重疊；本圖只用現成序列，不自算差值",
    "credit_spread_pct": "信用利差為高收益債利差（FRED BAMLH0A0HYM2）；本圖只呈現數值與期間變動",
    "policy_rate_pct": "政策利率為月頻資料，期間內的點數比日頻序列少",
}

# ───────────────────────── D4：尚未取得群組 ─────────────────────────

# EPS×PE 排最前面（摘要列收合時就看得到缺了它）。
MISSING_GROUP_KEYS = ("eps_pe_scenario", "taiex_volume", "market_stats", "nasdaq", "msci_world", "msci_em",
                      "implied_trailing_index_earnings")

TEXT_ERROR_REASON = "這一項市場資料這次沒有取到。"
TEXT_UNAVAILABLE_REASON = "這一項目前沒有可用的資料。"
TEXT_WHERE_ERROR = "取數失敗的原文與診斷在「設定與診斷」頁的進階診斷"
TEXT_WHERE_UNAVAILABLE = "資料來源尚未就緒時，補件請見「設定與診斷」頁"

_NUMBER_FMT_VALUE = {"taiex": "{:,.2f}", "sp500": "{:,.2f}", "vix": "{:.2f}"}


# ───────────────────────── 一句主判讀（D3：C1＋日期 (i)）─────────────────────────


def hero_sentence(view: dict) -> str:
    """資料事實層級的一句話：只有計數＋「暫無完整市場綜合判定」；**不寫日期**（頁級日期不放，日期只在各圖卡 chip）。

    計數來自各 domain 的四狀態（不新增判定）：已取得＝ ok；其餘依狀態字面列出，0 項不寫。
    不得出現方向、好壞、分數字樣（aggregation rule 未訂，`DEC-2026-10-27-41`）。
    """
    counts = Counter(d["status"] for d in view["domains"])
    parts = [f"{counts.get(logic.STATE_OK, 0)} 項已取得"]
    for state, word in ((logic.STATE_MISSING, "資料未備"), (logic.STATE_BIZ, "業務例外"), (logic.STATE_ERROR, "取數失敗")):
        if counts.get(state, 0):
            parts.append(f"{counts[state]} 項{word}")
    return "、".join(parts) + "；暫無完整市場綜合判定。"


# ───────────────────────── 共用小工具 ─────────────────────────


def _valued(points) -> list:
    return [p for p in points if MS._is_observed_number(p.get("value_num"))]   # noqa: SLF001 —— 同一套「已觀測」定義


def latest_value(domain: dict):
    """最後一個有值的觀測值；沒有 → None（不補值）。"""
    valued = _valued(domain.get("points") or [])
    return valued[-1]["value_num"] if valued else None


def _value_text(key: str, value: float) -> str:
    if key in _YIELD_KEYS:
        return f"{value:.2f}%"
    return _NUMBER_FMT_VALUE[key].format(value)


def _pp_text(pp: float) -> str:
    return "0.00" if abs(pp) < 0.005 else f"{pp:+.2f}"


def _date_chip_text(domain: dict) -> str:
    """資料日 MM-DD（經過天數）；完整日期在 detail。不判新舊、不上顏色（門檻 ⬜ 待裁示）。"""
    freshness = MS.freshness_text(domain["obs_date"], domain["fetched_at"])
    return f"資料日 {domain['obs_date'][5:]}（{freshness}）"


def _status_card(title: str, domain: dict) -> dict:
    """非 ok 的卡：狀態 chip（符號＋字）＋一句短原因；原文不上一般畫面（44 P0-①）。"""
    error = domain["status"] == logic.STATE_ERROR
    detail = P.detail_model(
        source=[f"狀態：{MS.status_text(domain)}"],
        where=[TEXT_WHERE_ERROR if error else TEXT_WHERE_UNAVAILABLE],
    )
    return {"kind": "status", "title": title, "chips": [P.chip(MS.status_text(domain), "紅" if error else "灰")],
            "reason": TEXT_ERROR_REASON if error else TEXT_UNAVAILABLE_REASON, "detail": detail,
            "slice": None, "spec": None, "message": None, "availability": {p: False for p in chart.PERIODS}}


def _change_chip(model: dict, period: str, *, pp: bool) -> dict:
    sliced = model["slice"]
    if sliced is None or sliced["status"] != chart.STATUS_OK:
        return P.chip(f"近{period} 資料不足", "灰")
    pr = model["period_return"]
    if pr is None or pr["status"] != "ok":
        return P.chip(f"近{period} {MS.TEXT_PERIOD_RETURN_UNDETERMINABLE}", "灰")
    return P.chip(f"近{period} {_pp_text(pr['pp'])} pp" if pp else f"近{period} {pr['pct']:+.1f}%")


TEXT_VIX_UNIT_CHIP = "指數點位（index）"


def _chart_card(title: str, key: str, domain: dict, model: dict, period: str, *, value_text: str, pp: bool) -> dict:
    # VIX 沒有期間漲跌（既有設計：波動度指數不算報酬率，`market_section.vix_model` 不帶 period_return）；
    # 中間那枚 chip 改放單位說明，不為了湊 3 枚而新增算法。
    middle = P.chip(TEXT_VIX_UNIT_CHIP, "灰") if key == "vix" else _change_chip(model, period, pp=pp)
    chips = [P.chip(f"最新 {value_text}"), middle, P.chip(_date_chip_text(domain))]
    if domain.get("reason"):
        chips.append(P.chip(domain["reason"], "灰"))     # 已略過 N 筆無法採用的觀測（沿用 L2 安靜說明）
    caption = model["caption_lines"]
    pr = model["period_return"]
    detail = P.detail_model(
        why=[pr["text"]] if pr is not None else [],
        source=caption[:2],
        limits=caption[2:],
    )
    card = P.chart_card_model(title, chips, None, detail=detail)
    card.update(slice=model["slice"], spec=model["spec"], message=model["message"], availability=model["availability"])
    return card


# ───────────────────────── Primary／Secondary（market_view 的五個序列）─────────────────────────


def primary_card(domain: dict, key: str, period: str) -> dict:
    """Primary Visual 目前選的序列。`kind`：`chart_card`（有資料）或 `status`（⛔／◇ 一枚 chip＋一句短原因，不畫空座標軸）。"""
    if key not in PRIMARY_KEYS:
        raise ValueError(f"Primary 序列須為 {PRIMARY_KEYS} 之一：{key!r}")
    title = MS.LABELS[key]
    if domain["status"] != logic.STATE_OK:
        return _status_card(title, domain)
    model = _MODEL_FN[key](domain, period)
    card = _chart_card(title, key, domain, model, period, value_text=_value_text(key, latest_value(domain)),
                       pp=key in _YIELD_KEYS)
    if card["spec"] is not None:
        card["spec"] = {**card["spec"], "height": PRIMARY_CHART_HEIGHT}
    return card


def secondary_card(domain: dict, key: str, title: str) -> dict:
    """Secondary（風險 VIX／國際 S&P 500）：同一份模型、固定近 1Y；迷你圖由 `spark` 交給畫面層（沒有座標軸、沒有期間切換）。"""
    if domain["status"] != logic.STATE_OK:
        card = _status_card(title, domain)
        card["spark"] = None
        return card
    model = _MODEL_FN[key](domain, SECONDARY_PERIOD)
    card = _chart_card(title, key, domain, model, SECONDARY_PERIOD, value_text=_value_text(key, latest_value(domain)),
                       pp=False)
    card["spark"] = _spark(card, title)
    return card


def _spark(card: dict, title: str):
    sliced = card["slice"]
    if sliced is None or sliced["status"] != chart.STATUS_OK:
        return None
    return chart.sparkline_svg(sliced["points"], aria_label=f"{title} 近 {SECONDARY_PERIOD} 迷你走勢（無座標軸）")


# ───────────────────────── 利率與信用（dataset 列）─────────────────────────


def rates_domain(dataset: dict, key: str) -> dict:
    """B 線 `market_indicator` 列 → 與 `market_view` domain 同形的 dict（唯讀；不取數）。

    同一觀測日有多個版次時取公布日最晚的一列（`logic.rows_for_key` 依 (obs_date, release_date) 排序，後者蓋前者）。
    沒有任何列：資料層記了失敗 → `取數失敗`；否則 → `資料未備`（不補值、不借別的序列）。
    """
    if key not in RATES_KEYS:
        raise ValueError(f"利率與信用序列須為 {RATES_KEYS} 之一：{key!r}")
    rows = logic.rows_for_key(dataset, key)
    by_date = {}
    for row in rows:
        by_date[row["obs_date"]] = row["value_num"]
    points = [{"obs_date": d, "value_num": v} for d, v in sorted(by_date.items())]
    base = {"domain": key, "status": None, "reason_code": None, "reason": None,
            "source": RATES_SOURCE_LABELS[key], "fetched_at": None, "obs_date": None,
            "value_unit": RATES_UNIT_TEXT[key], "points": points}
    if _valued(points):
        last = _valued(points)[-1]["obs_date"]
        fetched = max(r["fetched_at"] for r in rows if r["obs_date"] == last)
        return {**base, "status": logic.STATE_OK, "fetched_at": fetched, "obs_date": last}
    if key in (dataset.get("errors") or {}):
        return {**base, "status": logic.STATE_ERROR, "points": []}
    return {**base, "status": logic.STATE_MISSING, "points": []}


def rates_card(dataset: dict, key: str) -> dict:
    """「利率與信用」目前選的子序列（同一時間只顯示一個主要序列）；chips 只留值、近 1Y 變動（pp）、資料日。"""
    domain = rates_domain(dataset, key)
    title = f"{SECONDARY_RATES_TITLE}｜{RATES_OPTION_LABELS[key]}"
    if domain["status"] != logic.STATE_OK:
        card = _status_card(title, domain)
        card["spark"] = None
        return card
    sliced = chart.slice_period(domain["points"], SECONDARY_PERIOD)
    change = MS.period_change_pp(sliced["points"]) if sliced["status"] == chart.STATUS_OK else None
    unit = RATES_UNIT_TEXT[key]
    value = latest_value(domain)
    freshness = MS.freshness_text(domain["obs_date"], domain["fetched_at"])
    if sliced["status"] != chart.STATUS_OK:
        change_chip = P.chip(f"近{SECONDARY_PERIOD} 資料不足", "灰")
    elif change["status"] != "ok":
        change_chip = P.chip(f"近{SECONDARY_PERIOD} {MS.TEXT_PERIOD_RETURN_UNDETERMINABLE}", "灰")
    else:
        change_chip = P.chip(f"近{SECONDARY_PERIOD} {_pp_text(change['pp'])} pp")
    chips = [P.chip(f"最新 {value:.2f} {unit}" if unit == "pp" else f"最新 {value:.2f}%"), change_chip,
             P.chip(_date_chip_text(domain))]
    detail = P.detail_model(
        why=[change["text"]] if change and change["status"] == "ok" else [],
        source=[f"資料日期（最後觀測日）{domain['obs_date']}　{freshness}",
                f"來源 {domain['source']}　取得時間 {live.local_time_text(domain['fetched_at'])}（{live.DISPLAY_TZ_LABEL}）"],
        limits=[MS.TEXT_FRESHNESS_THRESHOLD, MS.TEXT_GAP_NOTE, TEXT_RATES_OBS_NOTE, TEXT_RATES_NOTES[key]],
    )
    card = P.chart_card_model(title, chips, None, detail=detail)
    card.update(slice=sliced, spec=None, message=chart.TEXT_INSUFFICIENT if sliced["status"] == chart.STATUS_INSUFFICIENT
                else (chart.TEXT_EMPTY if sliced["status"] == chart.STATUS_EMPTY else None), availability=None)
    card["spark"] = _spark(card, title)
    return card


def secondary_detail_blocks(view: dict, dataset: dict) -> list:
    """Secondary 區下方那一個合併的「▸ 次要圖：來源與限制」的內容：[(卡名, detail), ...]。

    三張次圖的 detail 合併成一處（D6：降低 Secondary 的細節密度，不是壓小 Primary）；資訊不減——
    「利率與信用」三個子序列各自的來源與限制**全部**在內（不隨目前選的子序列增減）。
    """
    domains = MS.domain_by_key(view)
    blocks = [(SECONDARY_RISK_TITLE, secondary_card(domains["vix"], "vix", SECONDARY_RISK_TITLE)["detail"]),
              (SECONDARY_INTL_TITLE, secondary_card(domains["sp500"], "sp500", SECONDARY_INTL_TITLE)["detail"])]
    for key in RATES_KEYS:
        card = rates_card(dataset, key)
        blocks.append((card["title"], card["detail"]))
    return blocks


SECONDARY_DETAIL_TITLE = "▸ 次要圖：來源與限制"


# ───────────────────────── 尚未取得群組（D4 β）─────────────────────────


def missing_group(view: dict):
    """尚未取得群組：把非 ok 的 Missing domain 併成一個預設收合的展開區；摘要列（標題）就點名缺哪幾項。
    沒有任何缺項 → None（不畫）。每一項仍逐項可見於展開區（卡片文案沿用 `market_section.missing_copy`，一字未改）。"""
    domains = MS.domain_by_key(view)
    keys = [k for k in MISSING_GROUP_KEYS if domains[k]["status"] != logic.STATE_OK]
    if not keys:
        return None
    names = "、".join(MS.LABELS[k] for k in keys)
    return {"keys": keys, "title": f"▸ 尚未取得：{names}（{len(keys)} 項）"}


STATUS_DETAIL_TITLE = "▸ 各項資料狀態"


# ───────────────────────── 字串清單（供禁詞／箭頭／目標價掃描）─────────────────────────


def page_strings(view: dict, dataset: dict) -> list:
    """本頁新層級會印出的字（五個 Primary 序列＋三張 Secondary＋hero＋尚未取得群組）。"""
    domains = MS.domain_by_key(view)
    out = [hero_sentence(view), SECONDARY_DETAIL_TITLE, STATUS_DETAIL_TITLE]
    for key in PRIMARY_KEYS:
        out += P.detail_texts(primary_card(domains[key], key, chart.DEFAULT_PERIOD)["detail"])
        out += [c["text"] for c in primary_card(domains[key], key, chart.DEFAULT_PERIOD)["chips"]]
    for title, detail in secondary_detail_blocks(view, dataset):
        out += [title, *P.detail_texts(detail)]
    for key in RATES_KEYS:
        out += [c["text"] for c in rates_card(dataset, key)["chips"]]
    group = missing_group(view)
    if group:
        out.append(group["title"])
    return out
