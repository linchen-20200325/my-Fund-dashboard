"""v19.26 Fund Screener — 純函式層（零 Streamlit / 零 IO）。

對齊鉅亨買基金 anuefund 篩選介面的 10 條件 + 新增 1 條我們自家「含息報酬率 ≥ 配息率」三色燈。
本檔不抓資料、不渲染 UI；輸入既已 enrich 過的 fund dict list，輸出過濾結果 + 燈號統計。

對外 API
========
- ``div_health_light(ret_1y_total, annual_div_rate, warn_gap=2.0)``
    對應圖二燈號：🟢 健康 ｜ 🟡 警示（含息略低於配息）｜ 🔴 吃本金 ｜ ⚪ 資料不足

- ``apply_filters(funds, filters)``
    回 ``(filtered_funds, stats)``，stats 含三色燈計數 + 每條 filter 的命中數

設計守則
========
- 全部純函式可單測，沒有 ``st.*`` 依賴
- 缺欄位 / NaN / 型別錯一律 graceful：filter 視作「pass」（不剔除），燈號回 ⚪
- 11 條 filter 全為 OR-within-group + AND-across-group（同類別多選用 ∈，跨類別都要過）
"""
from __future__ import annotations

from typing import Any

# ════════════════════════════════════════════════════════════════
# §1 對外常量
# ════════════════════════════════════════════════════════════════
FILTER_KEYS: tuple[str, ...] = (
    "domestic_overseas",  # 境內 / 境外
    "fund_type",          # 股票型 / 債券型 / 平衡型 / 貨幣市場 / 其他
    "currency",           # TWD / USD / EUR / JPY / ...
    "brand",              # 安聯 / 貝萊德 / 富達 / ...
    "region",             # 亞洲 / 歐洲 / 全球 / 新興市場 / ...
    "fund_group",         # 環球股票 / 科技 / 新興市場債券 / ...
    "dividend_freq",      # 月配 / 季配 / 半年配 / 年配 / 不配息
    "lipper_min",         # int 1-5（≥ 此分數通過）
    "risk_level",         # RR1 / RR2 / RR3 / RR4 / RR5
    "esg_min",            # float 0-100（≥ 此分數通過）
    "div_health_healthy_only",  # bool，True = 只留 🟢 健康
)

DIV_HEALTH_LIGHTS: tuple[str, ...] = ("健康", "警示", "吃本金", "資料不足")
DIV_HEALTH_EMOJI: dict[str, str] = {
    "健康": "🟢",
    "警示": "🟡",
    "吃本金": "🔴",
    "資料不足": "⚪",
}

DEFAULT_WARN_GAP: float = 2.0


# ════════════════════════════════════════════════════════════════
# §2 三色燈純函式（圖二邏輯）
# ════════════════════════════════════════════════════════════════
def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN check
        return None
    return f


def div_health_light(
    ret_1y_total: Any,
    annual_div_rate: Any,
    warn_gap: float = DEFAULT_WARN_GAP,
) -> tuple[str, str]:
    """回 (label, emoji)，對應圖二「健康 / 警示 / 吃本金 / 資料不足」四級。

    規則
    ----
    - 任一輸入 None / NaN / 非數值 → ("資料不足", "⚪")
    - annual_div_rate ≤ 0（不配息基金）→ ("健康", "🟢") （無配息侵蝕本金疑慮）
    - ret_1y_total ≥ annual_div_rate → ("健康", "🟢") 圖二 ✅ 含息成長支撐配息
    - 差距 (div - ret) ∈ (0, warn_gap] → ("警示", "🟡") 圖二 ⚠️ 正在輕微侵蝕
    - 差距 > warn_gap → ("吃本金", "🔴") 圖二 ❌ 配息主要來自本金返還
    """
    ret = _safe_float(ret_1y_total)
    div = _safe_float(annual_div_rate)
    if ret is None or div is None:
        return ("資料不足", DIV_HEALTH_EMOJI["資料不足"])
    if div <= 0:
        return ("健康", DIV_HEALTH_EMOJI["健康"])
    gap = div - ret
    if gap <= 0:
        return ("健康", DIV_HEALTH_EMOJI["健康"])
    if gap <= warn_gap:
        return ("警示", DIV_HEALTH_EMOJI["警示"])
    return ("吃本金", DIV_HEALTH_EMOJI["吃本金"])


# ════════════════════════════════════════════════════════════════
# §3 11 條篩選 — 私有 predicate helper
# ════════════════════════════════════════════════════════════════
def _get_field(fund: dict, *keys: str) -> Any:
    """嘗試多個 key 取值（schema 在 fund_fetcher 中分散在 metrics / moneydj_raw 等）。"""
    for k in keys:
        if k in fund and fund[k] not in (None, "", []):
            return fund[k]
        for sub in ("metrics", "moneydj_raw", "details"):
            d = fund.get(sub) if isinstance(fund.get(sub), dict) else None
            if d and k in d and d[k] not in (None, "", []):
                return d[k]
    return None


def _str_in(field_val: Any, allowed: list[str] | None) -> bool:
    if not allowed:
        return True
    if field_val is None:
        return True  # graceful：缺資料不剔除
    s = str(field_val).strip()
    return any(a.strip() == s or a.strip() in s for a in allowed if a)


def _num_min(field_val: Any, threshold: float | None) -> bool:
    if threshold is None:
        return True
    v = _safe_float(field_val)
    if v is None:
        return True  # graceful
    return v >= threshold


def _passes_div_health(fund: dict, healthy_only: bool, warn_gap: float) -> tuple[bool, str]:
    """回 (pass, light_label)。健康度 always 計算（給 stats），是否剔除看 healthy_only。"""
    ret = _get_field(fund, "ret_1y_total", "ret_1y")
    div = _get_field(fund, "annual_div_rate", "moneydj_div_yield")
    label, _ = div_health_light(ret, div, warn_gap=warn_gap)
    if not healthy_only:
        return (True, label)
    return (label == "健康", label)


# ════════════════════════════════════════════════════════════════
# §4 主入口：apply_filters
# ════════════════════════════════════════════════════════════════
def apply_filters(
    funds: list[dict],
    filters: dict | None = None,
    warn_gap: float = DEFAULT_WARN_GAP,
) -> tuple[list[dict], dict]:
    """套 11 條件 → 回 (filtered_funds, stats)。

    Parameters
    ----------
    funds : list[dict]
        已 enrich 的基金 dict list（schema 沿用 fetch_fund_multi_source 回傳結構）。
    filters : dict | None
        11 keys（見 FILTER_KEYS）；缺 key 視作該條件未啟用全部通過。
        str 類別欄收 ``list[str]``（多選 OR），數值欄收 ``float/int`` threshold。
        ``div_health_healthy_only`` 為 ``bool``。
    warn_gap : float
        警示燈閾值（單位 %），預設 2.0 對齊 user 圖二「差距 -4.4% 紅燈」直覺。

    Returns
    -------
    (filtered, stats)
        filtered : list[dict]
            每個元素是「原 fund dict + 注入 ``_div_health_light``」（不改 caller 原物件）。
        stats : dict
            ``{n_input, n_output, n_filtered_out, lights: {健康/警示/吃本金/資料不足: int}}``
            ``lights`` 統計的是「filtered_funds 內」的燈號分布。
    """
    filters = filters or {}
    healthy_only = bool(filters.get("div_health_healthy_only", False))

    stats: dict[str, Any] = {
        "n_input": len(funds),
        "n_output": 0,
        "n_filtered_out": 0,
        "lights": {label: 0 for label in DIV_HEALTH_LIGHTS},
    }

    filtered: list[dict] = []
    for fund in funds:
        if not isinstance(fund, dict):
            continue

        # 10 鉅亨條件 — 全為 string 多選或數值門檻
        if not _str_in(
            _get_field(fund, "domestic_overseas", "is_offshore_label"),
            filters.get("domestic_overseas"),
        ):
            continue
        if not _str_in(
            _get_field(fund, "fund_type", "category"),
            filters.get("fund_type"),
        ):
            continue
        if not _str_in(
            _get_field(fund, "currency"),
            filters.get("currency"),
        ):
            continue
        if not _str_in(
            _get_field(fund, "brand", "fund_name"),
            filters.get("brand"),
        ):
            continue
        if not _str_in(
            _get_field(fund, "fund_region", "region"),
            filters.get("region"),
        ):
            continue
        if not _str_in(
            _get_field(fund, "fund_group", "lipper_group"),
            filters.get("fund_group"),
        ):
            continue
        if not _str_in(
            _get_field(fund, "dividend_freq"),
            filters.get("dividend_freq"),
        ):
            continue
        if not _num_min(
            _get_field(fund, "lipper_score", "lipper_total_return"),
            filters.get("lipper_min"),
        ):
            continue
        if not _str_in(
            _get_field(fund, "risk_level", "rr"),
            filters.get("risk_level"),
        ):
            continue
        if not _num_min(
            _get_field(fund, "esg_score"),
            filters.get("esg_min"),
        ):
            continue

        # 第 11 條：自家含息健康度燈
        passes, light = _passes_div_health(fund, healthy_only, warn_gap)
        if not passes:
            continue

        # 注入燈號欄位（淺拷貝避免 mutate caller 物件）
        out_fund = dict(fund)
        out_fund["_div_health_light"] = light
        out_fund["_div_health_emoji"] = DIV_HEALTH_EMOJI[light]
        filtered.append(out_fund)
        stats["lights"][light] += 1

    stats["n_output"] = len(filtered)
    stats["n_filtered_out"] = stats["n_input"] - stats["n_output"]
    return filtered, stats


# ════════════════════════════════════════════════════════════════
# §5 便利 helper：給 UI 抽 distinct 值用（multiselect options）
# ════════════════════════════════════════════════════════════════
def collect_distinct_values(funds: list[dict], field: str) -> list[str]:
    """掃 funds 抽 distinct 的字串值，給 UI multiselect 動態列選項。

    None / "" / NaN 自動過濾。回傳依出現次數降序，便於 UI 把最常見的放前面。
    """
    counter: dict[str, int] = {}
    for fund in funds:
        if not isinstance(fund, dict):
            continue
        v = _get_field(fund, field)
        if v is None:
            continue
        s = str(v).strip()
        if not s or s.lower() in ("nan", "none"):
            continue
        counter[s] = counter.get(s, 0) + 1
    return sorted(counter.keys(), key=lambda k: (-counter[k], k))
