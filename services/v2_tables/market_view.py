# -*- coding: utf-8 -*-
"""🌍 市場與趨勢頁的唯讀 Data View（L2；BL-0516 批 1，客戶裁示 C：`DEC-2026-10-27-41`、`-42` (c)）。

這一層做什麼：把「市場與趨勢」頁這一批要畫的序列與缺口，整理成一份**畫面可直接讀**的結構。
本批只有兩種內容：

1. **VIX 序列**：讀 B 線 `vol_index` 列所用的同一支 L1 `fetch_yf_close_with_error("^VIX")`
   （同一個呼叫簽名 → 同一個 L1 快取鍵，不會多打一次來源），再用 `market_indicator.rows_from_daily_close`
   （同一條「已收盤、不重複、非週末、日界自證」規則）轉成逐日觀測。**不另寫一套收盤判定。**
2. **Missing 結構**：尚無正式來源的 domain 一律交回 `資料未備`＋原因代碼，不補值、不用 0、不拿別的代號頂替。

硬邊界（寫死，違反即 bug）：
- **唯讀、不寫 `market_indicator` 表、不改 `INDICATOR_SPECS`**（`DEC-2026-10-27-42` (c)；改表屬 44 資料契約變更，須另開 44 一輪）。
- **不新增 L1 函式、不新增 host / API**；只用 B 線已經在打的 Yahoo `^VIX`（本檔不直接 import L1，經 `market_indicator` 取同一支）。
- **不讀 `st.secrets`、不 import streamlit、不 import `ui_v2`**（L2 不得上行）；失敗原文的遮蔽由 L3 `source.py` 做一次。
- **不下判定**：不算分數、不分偏多偏空、不自創任何 threshold 或新鮮度門檻。這一層只交資料與狀態。
- 不快取（快取只在 L1，49 §4.4）。

回傳結構（`build_market_view` ）：

    {"domains": [domain, ...],        # 固定順序，見 DOMAIN_ORDER；每個 domain 都有四態之一
     "provenance": {...}}             # 本份 view 的出處說明（唯讀、無數值）

    domain = {"domain": 鍵, "status": 四態之一, "reason_code": 代碼或 None, "reason": 原文或 None,
              "source": "Yahoo:^VIX" 或 None, "fetched_at": ISO 或 None, "obs_date": 最後觀測日或 None,
              "value_unit": "index" 或 None, "points": [{"obs_date", "value_num"}, ...]}  # 無序列者為 []

四態字面值與 `ui_v2/mkt/logic.py` 的 `STATE_*` 逐字相同（測試比對；本層不 import `ui_v2`）。
"""

from __future__ import annotations

from typing import Callable, Optional

from services.v2_tables import market_indicator
from services.v2_tables.market_indicator import (
    INDICATOR_SPECS,
    OBS_DATE_SAME_DAY,
    rows_from_daily_close,
)

# 四態（逐字同 `ui_v2/mkt/logic.py::STATE_*`；由 tests/test_v2_tables_market_view.py 與該檔比對）。
STATE_OK = "ok"
STATE_MISSING = "資料未備"
STATE_BIZ = "業務例外"
STATE_ERROR = "系統錯誤"
STATES = (STATE_OK, STATE_MISSING, STATE_BIZ, STATE_ERROR)

VIX_TICKER = "^VIX"

# domain 鍵（固定順序＝畫面上狀態列的順序）。
DOMAIN_VIX = "vix"
DOMAIN_TAIEX = "taiex"
DOMAIN_TAIEX_VOLUME = "taiex_volume"
DOMAIN_MARKET_STATS = "market_stats"
DOMAIN_NASDAQ = "nasdaq"
DOMAIN_MSCI_WORLD = "msci_world"
DOMAIN_MSCI_EM = "msci_em"
DOMAIN_EPS_PE = "eps_pe_scenario"
DOMAIN_IMPLIED_EARNINGS = "implied_trailing_index_earnings"
DOMAIN_ORDER = (
    DOMAIN_VIX, DOMAIN_TAIEX, DOMAIN_TAIEX_VOLUME, DOMAIN_MARKET_STATS,
    DOMAIN_NASDAQ, DOMAIN_MSCI_WORLD, DOMAIN_MSCI_EM, DOMAIN_EPS_PE, DOMAIN_IMPLIED_EARNINGS,
)

# 原因代碼（畫面文案由 L3 依代碼對照；本層不寫面向使用者的字，只寫給人讀的 `reason` 說明原文）。
REASON_SOURCE_PENDING = "source_pending_bl0518"        # TAIEX 取數來源待客戶確認（BL-0518）
REASON_NO_OFFICIAL_SOURCE = "no_official_source"       # 目前沒有正式資料來源（NASDAQ／MSCI／成交量／市場統計）
REASON_EPS_UNAVAILABLE = "eps_forecast_unavailable"    # EPS 預估資料未取得
REASON_UNDETERMINABLE = "undeterminable"               # 無法判定（缺 EPS 預估與正式 trailing PE）
REASON_NO_OBSERVATION = "no_closed_observation"        # 來源有回，但沒有任何一筆通過收盤規則

# 沒有正式來源的 domain：鍵 → (原因代碼, 給人讀的說明原文)。
# 出處：`docs/v2/66` 區段 B／C 第四次更新（`DEC-2026-10-27-41`、`-42`）；`docs/v2/68`（TWSE 端點可取不等於 production 授權）。
_MISSING_DOMAINS = {
    DOMAIN_TAIEX: (REASON_SOURCE_PENDING,
                   "TAIEX 正式取數來源待客戶確認（BL-0518）；repo 目前沒有 TAIEX 的 production 來源"),
    DOMAIN_TAIEX_VOLUME: (REASON_NO_OFFICIAL_SOURCE, "成交量沒有已核准的來源（Data Gap）"),
    DOMAIN_MARKET_STATS: (REASON_NO_OFFICIAL_SOURCE, "市場成交／市場統計沒有已核准的來源（Data Gap）"),
    DOMAIN_NASDAQ: (REASON_NO_OFFICIAL_SOURCE, "NASDAQ 目前沒有正式資料來源"),
    DOMAIN_MSCI_WORLD: (REASON_NO_OFFICIAL_SOURCE, "MSCI World 目前沒有正式資料來源"),
    DOMAIN_MSCI_EM: (REASON_NO_OFFICIAL_SOURCE, "MSCI EM 目前沒有正式資料來源"),
    DOMAIN_EPS_PE: (REASON_EPS_UNAVAILABLE,
                    "EPS 預估資料未取得（DEC-2026-10-27-37：Phase 1 只研究 actual／trailing）"),
    DOMAIN_IMPLIED_EARNINGS: (REASON_UNDETERMINABLE,
                              "universe alignment、PE methodology、denominator consistency、historical validation 未完成"),
}


def _domain(domain: str, status: str, *, reason_code=None, reason=None, source=None, fetched_at=None,
            obs_date=None, value_unit=None, points=None) -> dict:
    if status not in STATES:   # 呼叫端的 bug：當場炸（§1）
        raise ValueError(f"status 須為 {STATES} 之一：{status!r}")
    return {
        "domain": domain, "status": status, "reason_code": reason_code, "reason": reason,
        "source": source, "fetched_at": fetched_at, "obs_date": obs_date, "value_unit": value_unit,
        "points": list(points or []),
    }


def missing_domain(domain: str) -> dict:
    """尚無正式來源的 domain：`資料未備`，帶原因代碼；不帶任何數值、來源、時間（沒有就是沒有）。"""
    code, reason = _MISSING_DOMAINS[domain]
    return _domain(domain, STATE_MISSING, reason_code=code, reason=reason)


def vix_domain_from_l1(series, error) -> dict:
    """純函式：L1 `(Series, error)` → VIX domain。無 I/O；替身可直接餵。

    - `error` 非空 → `系統錯誤`，原文照回（本層不改寫、不截斷；遮蔽在 L3）；不帶舊序列。
    - 轉換規則全交給 `market_indicator.rows_from_daily_close`（與 B 線 `vol_index` 同一條）。
    - 轉換後完全沒有列、也沒有錯誤（全被收盤規則略過）→ `資料未備`＋略過理由，不補值。
    """
    spec = INDICATOR_SPECS["vol_index"]
    rows, row_error, skipped = rows_from_daily_close(
        "vol_index", series, error, value_unit=spec["value_unit"], obs_date_rule=OBS_DATE_SAME_DAY)
    source = None
    attrs = getattr(series, "attrs", None) or {}
    if isinstance(attrs.get("source"), str):
        source = attrs["source"]
    if row_error is not None:
        return _domain(DOMAIN_VIX, STATE_ERROR, reason=str(row_error), source=source)
    if not rows:
        return _domain(DOMAIN_VIX, STATE_MISSING, reason_code=REASON_NO_OBSERVATION,
                       reason="；".join(skipped) if skipped else "沒有任何通過收盤規則的觀測", source=source)
    points = [{"obs_date": r["obs_date"], "value_num": r["value_num"]}
              for r in sorted(rows, key=lambda r: r["obs_date"])]
    last = points[-1]["obs_date"]
    fetched_at = next(r["fetched_at"] for r in rows if r["obs_date"] == last)
    return _domain(DOMAIN_VIX, STATE_OK, source=source, fetched_at=fetched_at, obs_date=last,
                   value_unit=spec["value_unit"], points=points)


def _call(fetch: Callable, *args):
    """呼叫 L1 `*_with_error`；L1 拋例外時轉成 (None, '型別名: 訊息')，不吞（同 `market_indicator._call`）。"""
    try:
        return fetch(*args)
    except Exception as exc:  # noqa: BLE001 —— 轉成可見的失敗原文，不是吞掉
        return None, f"{type(exc).__name__}: {exc}"


def build_market_view(*, fetch_vix: Optional[Callable] = None) -> dict:
    """組出本頁的 Data View。

    `fetch_vix`：測試替身（簽名同 `fetch_yf_close_with_error(ticker)`）；不傳＝L1 真函式。
    呼叫時**只傳 ticker 一個位置參數**（與 `market_indicator.build_market_indicator_table` 同一個簽名，
    L1 快取鍵相同；多傳一個預設值也會落在不同的快取鍵，見 market_indicator 檔頭）。
    """
    # 經 `market_indicator` 模組取 L1 函式（呼叫時才解析）：與 B 線 `vol_index` 用的是同一個屬性，
    # 測試替身換 `market_indicator.fetch_yf_close_with_error` 時兩邊一起換，不會一邊真打網路。
    fetch = fetch_vix if fetch_vix is not None else market_indicator.fetch_yf_close_with_error
    series, error = _call(fetch, VIX_TICKER)
    domains = {DOMAIN_VIX: vix_domain_from_l1(series, error)}
    for key in _MISSING_DOMAINS:
        domains[key] = missing_domain(key)
    return {
        "domains": [domains[k] for k in DOMAIN_ORDER],
        "provenance": {
            "readonly": True,
            "writes_market_indicator": False,
            "note": "唯讀 Data View；VIX 沿用 B 線 vol_index 的 L1 取數與收盤規則；其餘 domain 無正式來源，一律資料未備。",
        },
    }
