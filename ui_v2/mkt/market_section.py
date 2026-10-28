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
  不另發明容忍規則。VIX、TAIEX、S&P 500 本頁都抓 5y（`market_view.VIX_RANGE`／`TAIEX_RANGE`／`SP500_RANGE`），
  3Y 在歷史夠長時可用；美債殖利率 FRED 抓約 5 年（`market_view.FRED_VIEW_LOOKBACK_DAYS`）。
- **殖利率不是價格**（BL-0517 (2)）：單位是百分比（`%`），期間指標是**百分點變動（pp，末值減首值）**，不是報酬率；
  不算 `%` 漲跌、不除以起點（起點為 0 或負也有定義）。資料日期是 FRED **觀測日**，不是公布日，本檔不宣稱任何公布延遲。
- **新鮮度只顯示資料日期與經過天數，不判新舊、不上顏色**（門檻 ⬜ 門檻待裁示，不自創）；
  經過天數沿用 `logic.delay_days`／`logic.freshness_badge_text`，台北日期（同 `live.DISPLAY_TZ`）。
"""

from __future__ import annotations

import math

from . import chart, live, logic, theme

# ───────────────────────── 固定文案（逐字；總管擬，待覆核）─────────────────────────

SECTION_LABEL = "市場趨勢"
TEXT_NO_CONCLUSION = "暫無完整市場綜合判定（缺正式 aggregation rule）"
TEXT_EPS_PE_MISSING = "⬜ EPS 預估資料未取得，無法計算正式指數情境"
TEXT_IMPLIED_UNDETERMINABLE = "⬜ 無法判定"
TEXT_INTL_MISSING = "⬜ Missing／Data Gap：目前沒有正式資料來源"
TEXT_DATA_GAP = "⬜ Data Gap：目前沒有已核准的資料來源"
TEXT_FRESHNESS_THRESHOLD = "新鮮度門檻 ⬜ 門檻待裁示：本圖只顯示資料日期與經過天數，不判新舊"
TEXT_PERIOD_RETURN_UNDETERMINABLE = "⬜ 無法判定"
TEXT_GAP_NOTE = "圓點為實際觀測日；相鄰觀測之間的連線不代表中間日有資料；缺值日不補值"
TEXT_FRED_OBS_NOTE = "資料日期為 FRED 觀測日（不是公布日）；單位為百分比（%），不是價格"
# ~~「…；只取現行版次；…」~~：2026-10-28 改走 `fetch_fred_with_error`（不讀 vintage），該句不再為真（總管擬，待覆核；有意識的更正，不是漏刪）。

# domain → 畫面名稱
LABELS = {
    "vix": "波動度指數（VIX）",
    "taiex": "台股加權指數（TAIEX）",
    "sp500": "標普 500 指數（S&P 500）",
    "us10y": "美國 10 年期公債殖利率",
    "us2y": "美國 2 年期公債殖利率",
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


def raw_entries(view: dict) -> list:
    """系統錯誤的 domain → 跨頁原始訊息清單（`plain.record_raw` 的 entries 格式）；原文逐字 `logic.fetch_failed_text`。"""
    return [{"where": f"{SECTION_LABEL} {LABELS[d['domain']]}", "text": logic.fetch_failed_text(d["reason"])}
            for d in view["domains"] if d["status"] == logic.STATE_ERROR]


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


def _is_observed_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def period_return(points: list) -> dict:
    """期間漲跌（確定性、只用已觀測的點）：視窗內最後一個有值收盤 vs 第一個有值收盤。

    `points` 是 `chart.slice_period` 在 `status == "ok"` 時交回的視窗內點（可含 None 的點；None 不算觀測）。
    有值的點少於 2 個、或起點收盤不為正 → `{"status": "undeterminable", "text": "⬜ 無法判定"}`；不補值、不內插。
    成功 → `{"status": "ok", "pct": float, "first_obs", "last_obs", "text": "期間漲跌 +x.x%（起日 至 迄日，收盤）"}`。
    這是價格算術，不是判定：不分偏多偏空、不上方向顏色。
    """
    # NaN / inf / bool 都不是「已觀測的收盤」：視為未觀測（不補值），不足兩點即落回「無法判定」。
    valued = [p for p in points if _is_observed_number(p.get("value_num"))]
    if len(valued) < 2 or valued[0]["value_num"] <= 0:
        return {"status": "undeterminable", "pct": None, "first_obs": None, "last_obs": None,
                "text": TEXT_PERIOD_RETURN_UNDETERMINABLE}
    first, last = valued[0], valued[-1]
    pct = (last["value_num"] / first["value_num"] - 1.0) * 100.0
    return {"status": "ok", "pct": pct, "first_obs": first["obs_date"], "last_obs": last["obs_date"],
            "text": f"期間漲跌 {pct:+.1f}%（{first['obs_date']} 至 {last['obs_date']}，收盤價）"}


def period_change_pp(points: list) -> dict:
    """殖利率（單位 %）的期間變動：視窗內最後一個有值觀測 **減** 第一個有值觀測，單位**百分點（pp）**。

    這不是報酬率：不除以起點、不乘 100，所以起點為 0 或負值也有定義（殖利率可為負）。
    有值的點少於 2 個 → `{"status": "undeterminable", ...}`，不補值、不內插。NaN／inf／bool／None 不是觀測。
    成功 → `{"status": "ok", "kind": "pp", "pp": float, "pct": None, "first_obs", "last_obs", "text": "期間變動 +0.15 pp（…）"}`。
    確定性算術，不是判定：不分偏多偏空、不上方向顏色。
    """
    valued = [p for p in points if _is_observed_number(p.get("value_num"))]
    if len(valued) < 2:
        return {"status": "undeterminable", "kind": "pp", "pp": None, "pct": None, "first_obs": None,
                "last_obs": None, "text": TEXT_PERIOD_RETURN_UNDETERMINABLE}
    first, last = valued[0], valued[-1]
    pp = last["value_num"] - first["value_num"]
    pp_text = "0.00" if abs(pp) < 0.005 else f"{pp:+.2f}"      # 四捨五入後為零不印正負號（避免「-0.00」）
    return {"status": "ok", "kind": "pp", "pp": pp, "pct": None, "first_obs": first["obs_date"],
            "last_obs": last["obs_date"],
            "text": f"期間變動 {pp_text} 個百分點（pp）（{first['obs_date']} 至 {last['obs_date']}，FRED 觀測值）"}


def _price_model(domain: dict, period: str, *, key: str, short_label: str, value_title: str,
                 with_return: bool = False, change: str = "pct", observation_word: str = "收盤") -> dict:
    """日頻折線圖卡模型（VIX、TAIEX、S&P 500、美債殖利率共用，同一份 `chart`）。`period` 是目前選的期間。

    `change`：`"pct"`＝價格報酬（`period_return`）；`"pp"`＝百分點變動（`period_change_pp`，殖利率用）。
    `observation_word`：圖說明用字（價格「收盤」、殖利率「觀測值」）。

    - `domain.status != ok`：沒有圖，`message` 是原因（系統錯誤只寫「⛔ 取數失敗」，原文走 `raw_entries`；資料未備寫原因）。
    - ok：`slice` 是 `chart.slice_period` 的結果；`slice.status == insufficient` → 沒有圖，message 為固定文案。
    """
    avail = chart.availability(domain["points"]) if domain["status"] == logic.STATE_OK else {p: False for p in chart.PERIODS}
    model = {"label": LABELS[key], "status": domain["status"], "availability": avail, "period": period,
             "slice": None, "spec": None, "message": None, "caption_lines": [], "freshness": None,
             "period_return": None}
    if domain["status"] == logic.STATE_ERROR:
        # 44 第七節 P0-①：原文不上一般畫面，只寫狀態字；原文走 `raw_entries` 進跨頁原始訊息。
        model["message"] = _STATUS_TEXT[logic.STATE_ERROR]
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
    if change == "pp":
        model["caption_lines"].append(TEXT_FRED_OBS_NOTE)
    if domain.get("reason"):
        # S2：有點留下、但有觀測被略過 → 安靜的一行說明（文案由 L2 `skipped_observations_text` 產生，總管擬，待覆核）。
        model["caption_lines"].append(domain["reason"])
    if sliced["status"] == chart.STATUS_INSUFFICIENT:
        model["message"] = chart.TEXT_INSUFFICIENT
    elif sliced["status"] == chart.STATUS_EMPTY:
        model["message"] = chart.TEXT_EMPTY
    else:
        model["spec"] = chart.build_spec(
            sliced["points"], label=short_label, value_title=value_title, color=theme.TEAL_DARK,
            description=f"{LABELS[key]}近 {period} {observation_word}折線圖，資料日期至 {domain['obs_date']}")
        if with_return:
            model["period_return"] = (period_change_pp if change == "pp" else period_return)(sliced["points"])
    return model


def vix_model(domain: dict, period: str) -> dict:
    """VIX 圖卡模型。"""
    return _price_model(domain, period, key="vix", short_label="VIX", value_title="指數點位（index）")


def taiex_model(domain: dict, period: str) -> dict:
    """TAIEX 圖卡模型（來源 Yahoo `^TWII`，標示由 L2 的 `source` 帶入；另有期間漲跌，確定性算術）。"""
    return _price_model(domain, period, key="taiex", short_label="TAIEX", value_title="指數點位（index）",
                        with_return=True)


def sp500_model(domain: dict, period: str) -> dict:
    """S&P 500 圖卡模型（來源 Yahoo `^GSPC`，標示由 L2 帶入；有期間漲跌，同 TAIEX）。"""
    return _price_model(domain, period, key="sp500", short_label="S&P 500", value_title="指數點位（index）",
                        with_return=True)


def us10y_model(domain: dict, period: str) -> dict:
    """美國 10 年期公債殖利率圖卡模型（FRED DGS10；單位 %；期間指標為百分點變動 pp）。"""
    return _price_model(domain, period, key="us10y", short_label="US10Y", value_title="殖利率（%）",
                        with_return=True, change="pp", observation_word="觀測值")


def us2y_model(domain: dict, period: str) -> dict:
    """美國 2 年期公債殖利率圖卡模型（FRED DGS2；單位 %；期間指標為百分點變動 pp）。"""
    return _price_model(domain, period, key="us2y", short_label="US2Y", value_title="殖利率（%）",
                        with_return=True, change="pp", observation_word="觀測值")


def period_option_label(period: str, available: bool) -> str:
    """期間按鈕字面：資料不足的期間在按鈕上就說明，不等按下去才發現。"""
    return period if available else f"{period}（資料不足）"


def section_strings(view: dict, period: str) -> list:
    """本區段所有面向使用者的字串（供禁詞／箭頭／目標價掃描）。"""
    domains = domain_by_key(view)
    out = [SECTION_LABEL, TEXT_NO_CONCLUSION, TEXT_FRESHNESS_THRESHOLD, TEXT_GAP_NOTE, TEXT_FRED_OBS_NOTE]
    for row in conclusion_model(view)["rows"]:
        out += [row["label"], row["status_text"]]
    vix = vix_model(domains["vix"], period)
    out += [vix["label"], *vix["caption_lines"]]
    if vix["message"]:
        out.append(vix["message"])
    if vix["spec"] is not None:
        out += chart.spec_strings(vix["spec"])
    taiex = taiex_model(domains["taiex"], period)
    out += [taiex["label"], *taiex["caption_lines"]]
    if taiex["message"]:
        out.append(taiex["message"])
    if taiex["period_return"] is not None:
        out.append(taiex["period_return"]["text"])
    if taiex["spec"] is not None:
        out += chart.spec_strings(taiex["spec"])
    for fn, key in ((sp500_model, "sp500"), (us10y_model, "us10y"), (us2y_model, "us2y")):
        card = fn(domains[key], period)
        out += [card["label"], *card["caption_lines"]]
        if card["message"]:
            out.append(card["message"])
        if card["period_return"] is not None:
            out.append(card["period_return"]["text"])
        if card["spec"] is not None:
            out += chart.spec_strings(card["spec"])
    for key in _MISSING_COPY:
        out += [LABELS[key], missing_copy(domains[key])]
    return out
