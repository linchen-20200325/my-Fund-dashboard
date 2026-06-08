"""v19.27 Dividend Health Discoverer — 反向流：先給名單，再算燈號排行榜。

設計動機
========
正向流（v19.26 anuefund 仿製器）：「給定我的池子，誰健康？」
反向流（本檔）：「先給一份知名海外基金白名單，跑健康度排行榜給使用者挑」

對外 API
========
- ``KNOWN_OVERSEAS_FUNDS``：~10 檔台灣可買的境外基金白名單（code/name/brand/region）
- ``rank_by_health(enriched_funds)``：依「健康 > 警示 > 吃本金 > 資料不足」排序，回 dict

設計守則
========
- 純函式，零 IO、零 Streamlit 依賴
- 名單只放專案已驗證可抓資料的 code（避免 hard-code 大量無效項）
- 排序穩定（同燈號內按含息報酬率降序）
"""
from __future__ import annotations

from typing import Any

from services.fund_screener import (
    DIV_HEALTH_EMOJI,
    _get_field,
    _safe_float,
    div_health_light,
)

# ════════════════════════════════════════════════════════════════
# §1 知名海外基金白名單（v19.27 種子清單，後續可擴）
# ════════════════════════════════════════════════════════════════
# 選擇原則：
# (a) 已在 _MORNINGSTAR_SECID_MAP 驗證過可抓資料的 code
# (b) 台灣保險平台/銀行常見配息型基金
# 欄位：code + 顯示名稱 + 品牌 + 主要投資區域 + 配息頻率（先驗）
KNOWN_OVERSEAS_FUNDS: tuple[dict[str, str], ...] = (
    {"code": "TLZF9",   "name": "安聯收益成長 AMg7 USD",          "brand": "安聯",   "region": "全球",   "dividend_freq": "月配"},
    {"code": "ANZ89",   "name": "安聯收益成長 AM USD",            "brand": "安聯",   "region": "全球",   "dividend_freq": "月配"},
    {"code": "JFZN3",   "name": "JPMorgan 環球收益 A icdiv USD",  "brand": "摩根",   "region": "全球",   "dividend_freq": "月配"},
    {"code": "FLFM1",   "name": "法巴永續全球公司債 MD USD",       "brand": "法巴",   "region": "全球",   "dividend_freq": "月配"},
    {"code": "CTZP0",   "name": "Invesco 全球投資級公司債 MD USD","brand": "景順",   "region": "全球",   "dividend_freq": "月配"},
    {"code": "ACTI94",  "name": "聯博全球非投資等級債券 AT USD",   "brand": "聯博",   "region": "全球",   "dividend_freq": "月配"},
    {"code": "ACCP138", "name": "聯博全球高收益債券 AA USD",       "brand": "聯博",   "region": "全球",   "dividend_freq": "月配"},
)


def known_fund_codes() -> list[str]:
    """回 KNOWN_OVERSEAS_FUNDS 的 code list（給 UI 批次抓詳情用）。"""
    return [str(f["code"]).strip() for f in KNOWN_OVERSEAS_FUNDS if f.get("code")]


def known_fund_meta(code: str) -> dict | None:
    """依 code 回白名單裡的 metadata（給 UI 在抓詳情前先顯示骨架）。"""
    if not code:
        return None
    c = code.upper().strip()
    for f in KNOWN_OVERSEAS_FUNDS:
        if str(f.get("code", "")).upper().strip() == c:
            return dict(f)
    return None


# ════════════════════════════════════════════════════════════════
# §2 排行榜計算
# ════════════════════════════════════════════════════════════════
_LIGHT_ORDER: dict[str, int] = {"健康": 0, "警示": 1, "吃本金": 2, "資料不足": 3}


def _ret_1y_total_of(fund: dict) -> float:
    """取含息報酬率 1Y 值（缺值用 -inf 推到尾端）。"""
    v = _safe_float(_get_field(fund, "ret_1y_total", "ret_1y"))
    return v if v is not None else float("-inf")


def rank_by_health(
    enriched_funds: list[dict],
    warn_gap: float = 2.0,
) -> dict[str, list[dict]]:
    """依三色燈分桶 + 桶內按含息 1Y% 降序。

    Parameters
    ----------
    enriched_funds : list[dict]
        已 enrich 的 fund dict list（schema 同 fetch_fund_multi_source 輸出）。
    warn_gap : float
        警示燈閾值（單位 %），對齊 fund_screener.DEFAULT_WARN_GAP。

    Returns
    -------
    dict
        ``{"健康": [...], "警示": [...], "吃本金": [...], "資料不足": [...]}``
        每個 fund 注入 ``_div_health_light`` / ``_div_health_emoji`` 欄位（淺拷貝）。
    """
    buckets: dict[str, list[dict]] = {
        "健康": [], "警示": [], "吃本金": [], "資料不足": [],
    }
    for fund in enriched_funds:
        if not isinstance(fund, dict):
            continue
        ret = _get_field(fund, "ret_1y_total", "ret_1y")
        div = _get_field(fund, "annual_div_rate", "moneydj_div_yield")
        label, emoji = div_health_light(ret, div, warn_gap=warn_gap)
        out = dict(fund)
        out["_div_health_light"] = label
        out["_div_health_emoji"] = emoji
        buckets[label].append(out)

    for label in buckets:
        buckets[label].sort(key=_ret_1y_total_of, reverse=True)
    return buckets


def flatten_ranking(buckets: dict[str, list[dict]]) -> list[dict]:
    """攤平 4 桶為單一 list（健康 → 警示 → 吃本金 → 資料不足）。"""
    out: list[dict] = []
    for label in sorted(buckets.keys(), key=lambda k: _LIGHT_ORDER.get(k, 99)):
        out.extend(buckets[label])
    return out


def summarize_ranking(buckets: dict[str, list[dict]]) -> dict[str, Any]:
    """4 桶計數 + 健康占比，給 UI 頂部摘要。"""
    counts = {label: len(items) for label, items in buckets.items()}
    total = sum(counts.values())
    healthy_pct = (counts.get("健康", 0) / total * 100.0) if total else 0.0
    return {
        "n_total": total,
        "counts": counts,
        "emoji": {label: DIV_HEALTH_EMOJI[label] for label in counts},
        "healthy_pct": round(healthy_pct, 1),
    }
