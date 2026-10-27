# -*- coding: utf-8 -*-
"""🌍 市場與趨勢頁「市場趨勢」區段的文案與模型（純函式；零 streamlit import、零網路、零舊樹 import）。

BL-0516 批 1（客戶裁示 C，`DEC-2026-10-27-41`；`docs/v2/66` 第 3.1 節、區段 B／C 第四次更新）。
輸入是 L2 `services/v2_tables/market_view.py` 交來的 view（由 `source.py` 放進 `notes["market_view"]`，
本檔不 import services）；輸出是畫面要的純資料模型，`page.py` 只負責畫。

規則（每條有測試）：
- **面向使用者的固定文案逐字寫在本檔常數**（客戶 2026-10-27 派工指定；其餘最小化，標「總管擬，待覆核」）。
- **市場結論只列各 domain 的資料狀態**：不給偏多偏空、不給總分、不給風險分級（缺正式 aggregation rule，
  `DEC-2026-10-27-41`；`docs/v2/66` 3.1「不可顯示」）。
- **Missing 就是 Missing**：沒有正式來源的 domain 不補值、不用 0、不拿別的代號頂替（例：不以 QQQ 代 NASDAQ）。
- **已知限制（期間邊界）**：視窗起點若落在週末／假日，最早一筆有值觀測日必晚於起點，會被判「資料不足」；
  不另發明容忍規則。目前 L1 抓 2y：1Y 以下不受影響，3Y 本來就不足。
- **新鮮度只顯示資料日期與經過天數，不判新舊、不上顏色**（門檻 ⬜ 門檻待裁示，不自創）；
  經過天數沿用 `logic.delay_days`／`logic.freshness_badge_text`，台北日期（同 `live.DISPLAY_TZ`）。
"""

from __future__ import annotations

from . import chart, live, logic, theme

# ───────────────────────── 固定文案（逐字；總管擬，待覆核）─────────────────────────

SECTION_LABEL = "市場趨勢"
TEXT_NO_CONCLUSION = "暫無完整市場綜合判定（缺正式 aggregation rule）"
TEXT_EPS_PE_MISSING = "⬜ EPS 預估資料未取得，無法計算正式指數情境"
TEXT_IMPLIED_UNDETERMINABLE = "⬜ 無法判定"
TEXT_INTL_MISSING = "⬜ Missing／Data Gap：目前沒有正式資料來源"
TEXT_TAIEX_PENDING = "⬜ 資料來源待確認"
TEXT_DATA_GAP = "⬜ Data Gap：目前沒有已核准的資料來源"
TEXT_FRESHNESS_THRESHOLD = "新鮮度門檻 ⬜ 門檻待裁示：本圖只顯示資料日期與經過天數，不判新舊"
TEXT_GAP_NOTE = "圓點為實際觀測日；相鄰觀測之間的連線不代表中間日有資料；缺值日不補值"

# domain → 畫面名稱
LABELS = {
    "vix": "波動度指數（VIX）",
    "taiex": "台股加權指數（TAIEX）",
    "taiex_volume": "台股成交量",
    "market_stats": "台股市場統計",
    "nasdaq": "NASDAQ",
    "msci_world": "MSCI World",
    "msci_em": "MSCI EM",
    "eps_pe_scenario": "EPS × 本益比 指數情境",
    "implied_trailing_index_earnings": "隱含指數盈餘（implied trailing）",
}

# 沒有正式來源的 domain → 固定文案（只在 view 的 status 為 `資料未備` 時使用；其他狀態一律照狀態字面，不套用）
_MISSING_COPY = {
    "taiex": TEXT_TAIEX_PENDING,
    "taiex_volume": TEXT_DATA_GAP,
    "market_stats": TEXT_DATA_GAP,
    "nasdaq": TEXT_INTL_MISSING,
    "msci_world": TEXT_INTL_MISSING,
    "msci_em": TEXT_INTL_MISSING,
    "eps_pe_scenario": TEXT_EPS_PE_MISSING,
    "implied_trailing_index_earnings": TEXT_IMPLIED_UNDETERMINABLE,
}

# 狀態列的字（只描述資料狀態；沒有任何方向、好壞、分數字樣）
_STATUS_TEXT = {
    logic.STATE_MISSING: "⬜ 資料未備",
    logic.STATE_BIZ: "⬜ 業務例外",
    logic.STATE_ERROR: "⛔ 取數失敗",
}
_STATUS_TONE = {logic.STATE_OK: "中性", logic.STATE_MISSING: "灰", logic.STATE_BIZ: "灰", logic.STATE_ERROR: "紅"}


def domain_by_key(view: dict) -> dict:
    return {d["domain"]: d for d in view["domains"]}


def status_text(domain: dict) -> str:
    if domain["status"] == logic.STATE_OK:
        return f"有資料（{domain['obs_date']}）"
    return _STATUS_TEXT[domain["status"]]


def conclusion_model(view: dict) -> dict:
    """市場結論：固定一句＋各 domain 狀態列（只列狀態）。"""
    rows = [{"domain": d["domain"], "label": LABELS[d["domain"]], "status": d["status"],
             "status_text": status_text(d), "tone": _STATUS_TONE[d["status"]]}
            for d in view["domains"]]
    return {"text": TEXT_NO_CONCLUSION, "rows": rows}


def missing_copy(domain: dict) -> str:
    """Missing 卡的固定文案；status 不是 `資料未備`（理論上本批不會發生）→ 照狀態字面，不冒用 Missing 文案。"""
    if domain["status"] == logic.STATE_MISSING and domain["domain"] in _MISSING_COPY:
        return _MISSING_COPY[domain["domain"]]
    return status_text(domain)


def freshness_text(obs_date: str, fetched_at: str) -> str:
    """經過天數（台北日期）。`delay >= 1` 沿用 `logic.freshness_badge_text`（「延遲 N 日」）；
    0 日寫「經過 0 日」；其他（obs_date 晚於取得日，不該發生）寫 `未定義`，不猜。不判新舊、不上顏色。"""
    delay = logic.delay_days(obs_date, fetched_at, tz=live.DISPLAY_TZ)
    badge = logic.freshness_badge_text(delay)
    if badge is not None:
        return badge
    return "經過 0 日" if delay == 0 else "未定義"


def vix_model(domain: dict, period: str) -> dict:
    """VIX 圖卡模型。`period` 是目前選的期間。

    - `domain.status != ok`：沒有圖，`message` 是原因（系統錯誤照 `logic.fetch_failed_text` 原文；資料未備寫原因）。
    - ok：`slice` 是 `chart.slice_period` 的結果；`slice.status == insufficient` → 沒有圖，message 為固定文案。
    """
    avail = chart.availability(domain["points"]) if domain["status"] == logic.STATE_OK else {p: False for p in chart.PERIODS}
    model = {"label": LABELS["vix"], "status": domain["status"], "availability": avail, "period": period,
             "slice": None, "spec": None, "message": None, "caption_lines": [], "freshness": None}
    if domain["status"] == logic.STATE_ERROR:
        model["message"] = logic.fetch_failed_text(domain["reason"])
        return model
    if domain["status"] != logic.STATE_OK:
        model["message"] = f"{_STATUS_TEXT[domain['status']]}：{domain['reason']}" if domain.get("reason") \
            else _STATUS_TEXT[domain["status"]]
        return model
    sliced = chart.slice_period(domain["points"], period)
    model["slice"] = sliced
    freshness = freshness_text(domain["obs_date"], domain["fetched_at"])
    model["freshness"] = freshness
    model["caption_lines"] = [
        f"資料日期（最後觀測日）{domain['obs_date']}　{freshness}",
        f"來源 {domain['source']}　取得時間 {live.local_time_text(domain['fetched_at'])}（{live.DISPLAY_TZ_LABEL}）",
        TEXT_FRESHNESS_THRESHOLD,
        TEXT_GAP_NOTE,
    ]
    if sliced["status"] == chart.STATUS_INSUFFICIENT:
        model["message"] = chart.TEXT_INSUFFICIENT
    elif sliced["status"] == chart.STATUS_EMPTY:
        model["message"] = chart.TEXT_EMPTY
    else:
        model["spec"] = chart.build_spec(
            sliced["points"], label="VIX", value_title="指數點位（index）", color=theme.TEAL_DARK,
            description=f"{LABELS['vix']}近 {period} 日收盤折線圖，資料日期至 {domain['obs_date']}")
    return model


def period_option_label(period: str, available: bool) -> str:
    """期間按鈕字面：資料不足的期間在按鈕上就說明，不等按下去才發現。"""
    return period if available else f"{period}（資料不足）"


def section_strings(view: dict, period: str) -> list:
    """本區段所有面向使用者的字串（供禁詞／箭頭／目標價掃描）。"""
    domains = domain_by_key(view)
    out = [SECTION_LABEL, TEXT_NO_CONCLUSION, TEXT_FRESHNESS_THRESHOLD, TEXT_GAP_NOTE]
    for row in conclusion_model(view)["rows"]:
        out += [row["label"], row["status_text"]]
    vix = vix_model(domains["vix"], period)
    out += [vix["label"], *vix["caption_lines"]]
    if vix["message"]:
        out.append(vix["message"])
    if vix["spec"] is not None:
        out += chart.spec_strings(vix["spec"])
    for key in _MISSING_COPY:
        out += [LABELS[key], missing_copy(domains[key])]
    return out
