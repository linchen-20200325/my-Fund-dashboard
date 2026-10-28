# -*- coding: utf-8 -*-
"""🌍 市場與趨勢頁的唯讀 Data View（L2；BL-0516 批 1，客戶裁示 C：`DEC-2026-10-27-41`、`-42` (c)）。

這一層做什麼：把「市場與趨勢」頁這一批要畫的序列與缺口，整理成一份**畫面可直接讀**的結構。
目前有四種內容：

1. **VIX 序列**：讀 B 線 `vol_index` 列所用的同一支 L1 `fetch_yf_close_with_error`，改要 `range_="5y"`
   （`VIX_RANGE`；讓 3Y 按鈕是真的，同 TAIEX），再用 `market_indicator.rows_from_daily_close`
   （同一條「已收盤、不重複、非週末、日界自證」規則）轉成逐日觀測。**不另寫一套收盤判定。**
   ⚠️ 性質變更（BL-0517 (3)，誠實記錄）：舊版 VIX 與 B 線 `vol_index` 呼叫簽名相同（`("^VIX",)`）→ 同一個 L1 快取鍵、
   不多打來源；現版 VIX 是 `("^VIX", "5y")`，**有自己獨立的 L1 快取項與一次獨立請求**（與 B 線 2y 的鍵不同），
   **同一個 Yahoo 主機的冷卻（host cooldown）仍是共用的**——B 線先打、本頁後打，若 B 線已被 429，本頁也會被擋。
   B 線 `vol_index` 的取數（`("^VIX",)`、預設 2y）、快取鍵、`WINDOW_DAYS_MAX` **一字不動**（測試釘住）。
2. **TAIEX 指數收盤序列（BL-0518；客戶 2026-10-27 裁示，`DEC-2026-10-27-43`）**：**唯一來源是 Yahoo `^TWII`**，
   只作「台股加權指數價格／歷史」的 Data View；沿用同一支 L1 `fetch_yf_close_with_error`（不開第二套 Yahoo 取數架構）
   與同一條 `rows_from_daily_close` 規則（缺的日子就是沒有點，不補）。來源標示固定為 `Yahoo Finance (^TWII)`，
   **絕不標成 TWSE 官方**。成交量、市場統計、市場 PE、EPS、forward EPS、g、市場廣度、TWSE 官方統計**不得**由本序列延伸，
   維持下一項的 Missing。
3. **S&P 500 指數收盤序列（BL-0517 (1)；客戶 2026-10-27 C 裁示，總管讀法 `DEC-2026-10-27-44`）**：
   Yahoo `^GSPC`，同一支 L1、同一條 `rows_from_daily_close`，`range_="5y"`；來源標示固定 `Yahoo Finance (^GSPC)`。
4. **美國公債殖利率（BL-0517 (2)）**：FRED `DGS10`（10Y）／`DGS2`（2Y），經已被 `market_indicator` import 的
   `fetch_fred_with_error(series_id, api_key, n)`（`repositories/macro/fred.py`；**production 已在用的同一條讀法**：
   `risk_radar`／`us_indicators` 走 `fetch_fred`，本頁走它的 `_with_error` 薄包裝，同一層 `_ttl_cache`）。
   值是**百分比**（`value_unit="%"`，不是價格）；`obs_date` ＝ FRED 觀測日（`date` 欄），**不是公布日**：
   `fetch_fred` 的 `realtime_start` 是**查詢當天**，不是首次公布日，本層不使用它、不宣稱任何公布延遲；
   缺值（FRED `.`、NaN）在 L1 內即被丟掉，不進序列、不補 0。來源標示 `FRED (DGS10)`／`FRED (DGS2)`。
   2026-10-28 總管裁示（稽核 S1）：~~`fetch_fred_vintages_with_error` 只取現行版次~~ → 改走上述 production 已驗證的讀法
   （**有意識的更正，不是漏刪**；日期 2026-10-28；決策者 AI 總管）。舊讀法的理由是「vintage 才拿得到公布日」，但本頁**不顯示**公布日，
   那份能力用不到，卻要承擔「本 repo 從未真實連線實測」的風險；被權衡掉的是版次資訊，本頁不需要。
   ⚠️ 本 session 沒有對 FRED 真實連線驗證回應；只用替身測過形狀。首次部署要看畫面是否為「⛔ 取數失敗」或空序列。
5. **Missing 結構**：尚無正式來源的 domain 一律交回 `資料未備`＋原因代碼，不補值、不用 0、不拿別的代號頂替。

硬邊界（寫死，違反即 bug）：
- **唯讀、不寫 `market_indicator` 表、不改 `INDICATOR_SPECS`**（`DEC-2026-10-27-42` (c)；改表屬 44 資料契約變更，須另開 44 一輪）。
- **不新增 L1 函式、不新增 host / API、不新增 FRED series、不新增 `INDICATOR_SPECS` 鍵**；只用 B 線已經在打的同一個 Yahoo 端點
  （`^VIX`、`^TWII`、`^GSPC`）與同一個 FRED 端點（`DGS10`、`DGS2` 是 `shared/fred_series.py` 既有常數）；本檔不直接 import L1，經 `market_indicator` 取同一支。
  NASDAQ／MSCI World／MSCI EM 維持 Missing／Data Gap，不以任何代理（QQQ、ETF）頂替；proxy 不是真資料。
- **不讀 `st.secrets`、不 import streamlit、不 import `ui_v2`**（L2 不得上行）；失敗原文的遮蔽由 L3 `source.py` 做一次。
  FRED 金鑰由 L3 以 `fred_api_key=` 傳入（`source._fred_api_key`），本層**不印、不記、不放進回傳結構**；缺金鑰 → 兩個殖利率
  domain 為 `系統錯誤`＋`MISSING_FRED_API_KEY` 原文（走既有 raw_entries 路徑），不打 L1。
- **不下判定**：不算分數、不分偏多偏空、不自創任何 threshold 或新鮮度門檻。這一層只交資料與狀態。
- 不快取（快取只在 L1，49 §4.4）。

回傳結構（`build_market_view` ）：

    {"domains": [domain, ...],        # 固定順序，見 DOMAIN_ORDER；每個 domain 都有四態之一
     "provenance": {...}}             # 本份 view 的出處說明（唯讀、無數值）

    domain = {"domain": 鍵, "status": 四態之一, "reason_code": 代碼或 None, "reason": 原文或 None,
              "source": "Yahoo:^VIX"／"Yahoo Finance (^TWII)"／"Yahoo Finance (^GSPC)"／"FRED (DGS10)" 或 None, "fetched_at": ISO 或 None, "obs_date": 最後觀測日或 None,
              "value_unit": "index"／"%"（殖利率）或 None, "points": [{"obs_date", "value_num"}, ...]}  # 無序列者為 []

四態字面值與 `ui_v2/mkt/logic.py` 的 `STATE_*` 逐字相同（測試比對；本層不 import `ui_v2`）。
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Callable, Optional

from services.v2_tables import market_indicator
from services.v2_tables.market_indicator import (
    EMPTY_WITHOUT_REASON,
    INDICATOR_SPECS,
    MISSING_FRED_API_KEY,
    OBS_DATE_SAME_DAY,
    rows_from_daily_close,
)
from shared.fred_series import FRED_DGS2, FRED_DGS10

# 四態（逐字同 `ui_v2/mkt/logic.py::STATE_*`；由 tests/test_v2_tables_market_view.py 與該檔比對）。
STATE_OK = "ok"
STATE_MISSING = "資料未備"
STATE_BIZ = "業務例外"
STATE_ERROR = "系統錯誤"
STATES = (STATE_OK, STATE_MISSING, STATE_BIZ, STATE_ERROR)

VIX_TICKER = "^VIX"
TAIEX_TICKER = "^TWII"
# TAIEX 來源標示（客戶 2026-10-27 裁示，逐字）：Yahoo 的 ^TWII，不是 TWSE 官方；成交量／市場統計不由它延伸。
TAIEX_SOURCE_LABEL = "Yahoo Finance (^TWII)"
TAIEX_VALUE_UNIT = "index"
# TAIEX 要 3M／6M／1Y／3Y（客戶 2026-10-27 裁示）：L1 預設 2y 不夠 3Y，故只有 ^TWII 這一支改要 5y（既有 `range_` 參數）。
TAIEX_RANGE = "5y"
# VIX 同理（BL-0517 (3)）：3Y 按鈕要是真的 → 本頁 VIX 要 5y。B 線 `vol_index` 仍是 `("^VIX",)` 預設 2y，不動。
VIX_RANGE = "5y"
# S&P 500（BL-0517 (1)）：Yahoo ^GSPC，同 TAIEX 規格。
SP500_TICKER = "^GSPC"
SP500_SOURCE_LABEL = "Yahoo Finance (^GSPC)"
SP500_VALUE_UNIT = "index"
SP500_RANGE = "5y"
# 美國公債殖利率（BL-0517 (2)）：FRED 既有 series（shared/fred_series.py），值單位是百分比（%）。
US10Y_SERIES = FRED_DGS10
US2Y_SERIES = FRED_DGS2
US10Y_SOURCE_LABEL = "FRED (DGS10)"
US2Y_SOURCE_LABEL = "FRED (DGS2)"
YIELD_VALUE_UNIT = "%"
# FRED 取最近幾筆觀測（`fetch_fred` 以 `sort_order=desc&limit=n` 取最新 n 筆）：日頻約每年 260 個平日，
# 5 年約 1300 筆（含 FRED 以 `.` 標記的假日，約每年 9~10 筆，L1 會丟掉）；取 1500（約 5.8 年）涵蓋 3Y 視窗並留餘裕。
# 這是取數範圍，不是新鮮度或判定門檻。與 B 線（vintage 讀法、不同函式）及 `fetch_fred` 其他 caller（n=250 等）快取鍵不同。
FRED_VIEW_OBSERVATION_LIMIT = 1500

# domain 鍵（固定順序＝畫面上狀態列的順序）。
DOMAIN_VIX = "vix"
DOMAIN_TAIEX = "taiex"
DOMAIN_TAIEX_VOLUME = "taiex_volume"
DOMAIN_MARKET_STATS = "market_stats"
DOMAIN_SP500 = "sp500"
DOMAIN_US10Y = "us10y"
DOMAIN_US2Y = "us2y"
DOMAIN_NASDAQ = "nasdaq"
DOMAIN_MSCI_WORLD = "msci_world"
DOMAIN_MSCI_EM = "msci_em"
DOMAIN_EPS_PE = "eps_pe_scenario"
DOMAIN_IMPLIED_EARNINGS = "implied_trailing_index_earnings"
DOMAIN_ORDER = (
    DOMAIN_VIX, DOMAIN_TAIEX, DOMAIN_TAIEX_VOLUME, DOMAIN_MARKET_STATS,
    DOMAIN_SP500, DOMAIN_US10Y, DOMAIN_US2Y,
    DOMAIN_NASDAQ, DOMAIN_MSCI_WORLD, DOMAIN_MSCI_EM, DOMAIN_EPS_PE, DOMAIN_IMPLIED_EARNINGS,
)

# 原因代碼（畫面文案由 L3 依代碼對照；本層不寫面向使用者的字，只寫給人讀的 `reason` 說明原文）。
REASON_SOURCE_PENDING = "source_pending_bl0518"        # ~~TAIEX 取數來源待客戶確認（BL-0518）~~：2026-10-27 已裁示（DEC-2026-10-27-43），不再被任何 domain 使用；常數保留供舊引用
REASON_NO_OFFICIAL_SOURCE = "no_official_source"       # 目前沒有正式資料來源（NASDAQ／MSCI／成交量／市場統計）
REASON_EPS_UNAVAILABLE = "eps_forecast_unavailable"    # EPS 預估資料未取得
REASON_UNDETERMINABLE = "undeterminable"               # 無法判定（缺 EPS 預估與正式 trailing PE）
REASON_NO_OBSERVATION = "no_closed_observation"        # 來源有回，但沒有任何一筆通過收盤規則

# 沒有正式來源的 domain：鍵 → (原因代碼, 給人讀的說明原文)。
# 出處：`docs/v2/66` 區段 B／C 第四次更新（`DEC-2026-10-27-41`、`-42`）；`docs/v2/68`（TWSE 端點可取不等於 production 授權）。
_MISSING_DOMAINS = {
    # 成交量／市場統計：客戶 2026-10-27 明示不得由 Yahoo ^TWII 延伸（DEC-2026-10-27-43）；維持 Data Gap。
    DOMAIN_TAIEX_VOLUME: (REASON_NO_OFFICIAL_SOURCE, "成交量沒有已核准的來源（Data Gap）；Yahoo ^TWII 只核准指數價格，不延伸到成交量"),
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


def _daily_close_domain(domain: str, rows_key: str, series, error, *, value_unit: str,
                        source_label: Optional[str] = None) -> dict:
    """純函式：L1 `(Series, error)` → 日頻收盤 domain（VIX、TAIEX 共用，一套規則）。無 I/O；替身可直接餵。

    - `error` 非空 → `系統錯誤`，原文照回（本層不改寫、不截斷；遮蔽在 L3）；不帶舊序列。
    - 轉換規則全交給 `market_indicator.rows_from_daily_close`（與 B 線 `vol_index` 同一條）。
    - 轉換後完全沒有列、也沒有錯誤（全被收盤規則略過）→ `資料未備`＋略過理由，不補值。
    - `source_label`：給了就用它當來源標示（TAIEX 固定 `Yahoo Finance (^TWII)`）；沒給沿用 L1 自報的 `attrs["source"]`。
    """
    rows, row_error, skipped = rows_from_daily_close(
        rows_key, series, error, value_unit=value_unit, obs_date_rule=OBS_DATE_SAME_DAY)
    source = source_label
    if source is None:
        attrs = getattr(series, "attrs", None) or {}
        if isinstance(attrs.get("source"), str):
            source = attrs["source"]
    if row_error is not None:
        return _domain(domain, STATE_ERROR, reason=str(row_error), source=source)
    if not rows:
        return _domain(domain, STATE_MISSING, reason_code=REASON_NO_OBSERVATION,
                       reason="；".join(skipped) if skipped else "沒有任何通過收盤規則的觀測", source=source)
    points = [{"obs_date": r["obs_date"], "value_num": r["value_num"]}
              for r in sorted(rows, key=lambda r: r["obs_date"])]
    last = points[-1]["obs_date"]
    fetched_at = next(r["fetched_at"] for r in rows if r["obs_date"] == last)
    return _domain(domain, STATE_OK, source=source, fetched_at=fetched_at, obs_date=last,
                   value_unit=value_unit, points=points)


def vix_domain_from_l1(series, error) -> dict:
    """VIX domain（行為與 BL-0516 批 1 相同）。"""
    return _daily_close_domain(DOMAIN_VIX, "vol_index", series, error,
                               value_unit=INDICATOR_SPECS["vol_index"]["value_unit"])


def taiex_domain_from_l1(series, error) -> dict:
    """TAIEX domain：Yahoo `^TWII` 收盤（BL-0518；`DEC-2026-10-27-43`）。來源標示固定，不標成 TWSE 官方。"""
    return _daily_close_domain(DOMAIN_TAIEX, DOMAIN_TAIEX, series, error,
                               value_unit=TAIEX_VALUE_UNIT, source_label=TAIEX_SOURCE_LABEL)


def sp500_domain_from_l1(series, error) -> dict:
    """S&P 500 domain：Yahoo `^GSPC` 收盤（BL-0517 (1)）。來源標示固定；規則與 VIX／TAIEX 同一條。"""
    return _daily_close_domain(DOMAIN_SP500, DOMAIN_SP500, series, error,
                               value_unit=SP500_VALUE_UNIT, source_label=SP500_SOURCE_LABEL)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def skipped_observations_text(count: int) -> str:
    """S2：有點留下、但有觀測被略過時，寫進 domain `reason` 的安靜說明（總管擬，待覆核）。"""
    return f"已略過 {count} 筆無法採用的觀測"


def fred_yield_domain_from_l1(domain: str, frame, error, *, source_label: str) -> dict:
    """純函式：L1 `fetch_fred_with_error` 的 `(DataFrame, error)` → 殖利率 domain（%）。無 I/O；替身可直接餵。

    L1 契約（2026-10-28 讀 `repositories/macro/fred.py::fetch_fred` 實測）：欄位 `date`（Timestamp）、`value`（float64）、
    `realtime_start`、`source`、`fetched_at`（**欄位**，不是 attrs；UTC ISO、有時區，整欄同一值）；列已依 `date` **由舊到新**排序
    （請求端是最新 n 筆）；FRED 的 `.` 與 NaN 在 L1 內即被丟掉（不計入略過數：那是來源的缺值，不是被本層略過的觀測）。

    - `error` 非空 → `系統錯誤`，原文照回（遮蔽在 L3）；空表又沒有原因 → `EMPTY_WITHOUT_REASON`，不補。
    - `obs_date` ＝ FRED 觀測日（`date` 欄），**不是公布日**；不用 `realtime_start`（它是查詢當天），也不推算任何公布延遲。
    - 值必須是有限數字（bool、NaN、inf、None、字串都不是觀測）→ 不進序列、**不補 0**、不前值填補；負值與 0.0 是有效觀測。
    - 同一觀測日出現不只一列（L1 不該產生）→ 該日全部不進序列（不隨便挑一列），計入略過數。
    - 觀測日晚於取得日（UTC）→ 不進序列（來源資料不合理，不顯示），計入略過數。
    - 取得時間用 L1 的 `fetched_at` 欄（第一個非空值；要有時區）；取不到或沒有時區 → 整批不寫、`資料未備`，不以現在時間補。
    - 有點留下、但有觀測被略過（日期無法解析、值無法採用、重複、晚於取得日）→ `ok`，`reason` ＝ `skipped_observations_text(N)`；
      沒有被略過 → `reason` 為 None。完全沒有可用觀測、也沒有錯誤 → `資料未備`＋略過理由。
    """
    if error:
        return _domain(domain, STATE_ERROR, reason=str(error), source=source_label)
    if frame is None or len(frame) == 0:
        return _domain(domain, STATE_ERROR, reason=EMPTY_WITHOUT_REASON, source=source_label)
    stamps = frame["fetched_at"].dropna() if "fetched_at" in getattr(frame, "columns", ()) else ()
    fetched_at = market_indicator._utc_iso(stamps.iloc[0] if len(stamps) else None)
    if fetched_at is None:
        return _domain(domain, STATE_MISSING, reason_code=REASON_NO_OBSERVATION,
                       reason=f"L1 回傳的 fetched_at 取不到或沒有時區，{len(frame)} 筆全部不寫", source=source_label)
    fetched_day = datetime.fromisoformat(fetched_at.replace("Z", "+00:00")).astimezone(timezone.utc).date().isoformat()

    by_date: dict = {}
    bad_date = bad_value = future = 0
    for record in frame.to_dict("records"):
        obs = market_indicator._iso_day(record.get("date"))
        if obs is None:
            bad_date += 1
            continue
        by_date.setdefault(obs, []).append(record.get("value"))
    duplicated = sum(len(v) for v in by_date.values() if len(v) > 1)
    points = []
    for obs in sorted(by_date):
        values = by_date[obs]
        if len(values) > 1:
            continue
        value = values[0]
        if not _is_number(value):
            bad_value += 1
            continue
        if obs > fetched_day:
            future += 1
            continue
        points.append({"obs_date": obs, "value_num": float(value)})
    skipped_n = bad_date + bad_value + duplicated + future
    if not points:
        parts = []
        if bad_date:
            parts.append(f"觀測日缺或解析不了 {bad_date} 筆不寫")
        if bad_value:
            parts.append(f"值為缺值或非有限數字 {bad_value} 筆不寫")
        if duplicated:
            parts.append(f"同一觀測日有多列 {duplicated} 筆不寫")
        if future:
            parts.append(f"觀測日晚於取得日（{fetched_day}，世界協調時間）{future} 筆不寫")
        return _domain(domain, STATE_MISSING, reason_code=REASON_NO_OBSERVATION,
                       reason="；".join(parts) if parts else "沒有任何可用的觀測", source=source_label)
    return _domain(domain, STATE_OK, source=source_label, fetched_at=fetched_at, obs_date=points[-1]["obs_date"],
                   value_unit=YIELD_VALUE_UNIT, points=points,
                   reason=skipped_observations_text(skipped_n) if skipped_n else None)


def _call(fetch: Callable, *args):
    """呼叫 L1 `*_with_error`；L1 拋例外時轉成 (None, '型別名: 訊息')，不吞（同 `market_indicator._call`）。"""
    try:
        return fetch(*args)
    except Exception as exc:  # noqa: BLE001 —— 轉成可見的失敗原文，不是吞掉
        return None, f"{type(exc).__name__}: {exc}"


def build_market_view(*, fetch_vix: Optional[Callable] = None, fetch_taiex: Optional[Callable] = None,
                      fetch_sp500: Optional[Callable] = None, fetch_fred: Optional[Callable] = None,
                      fred_api_key: Optional[str] = None) -> dict:
    """組出本頁的 Data View。

    `fetch_vix`：測試替身（簽名同 `fetch_yf_close_with_error(ticker, range_)`）；不傳＝L1 真函式。
    `fetch_taiex`／`fetch_sp500`：同上，給 `^TWII`／`^GSPC`；不傳＝與 VIX 用**同一支**
    （`fetch_vix` 若有給就是它，否則 L1 真函式）——沒有自己的取數架構。
    `fetch_fred`：簽名同 `fetch_fred_with_error(series_id, api_key, n)`；不傳＝L1 真函式
    （經 `market_indicator` 屬性取，測試替身換在那裡時兩邊一起換）。
    `fred_api_key`：由 L3 傳入（`source._fred_api_key`）；本層不讀 secrets、不印、不記、不放進回傳。
    None／空白 → 兩個殖利率 domain 為 `系統錯誤`＋`MISSING_FRED_API_KEY`，**不打 L1**。

    呼叫順序（B 線先、本頁後；同一個 Yahoo／FRED 主機共用冷卻）：
    B 線 `build_market_indicator_table`（由 L3 先呼叫，不在本函式內）→ VIX → TAIEX → S&P 500 → FRED 10Y → FRED 2Y。
    ⚠️ **host 級冷卻風險**：本頁在 Yahoo 多打三次不同快取鍵的請求（^VIX 5y、^TWII 5y、^GSPC 5y），FRED 多打兩次
    （DGS10、DGS2；與 B 線三個 series 的快取鍵不同）。若來源對該主機回 429，L1 的主機冷卻會讓**排在後面的**請求一起被擋；
    排序把 B 線與 VIX 放前面，新增的 domain 放後面，是為了讓既有畫面最後受影響。
    VIX：呼叫 `("^VIX", "5y")`（`VIX_RANGE`）。**與舊版不同**：舊版與 B 線同簽名同快取鍵；現版有自己的快取項與請求，
    但 B 線 `vol_index` 的 `("^VIX",)` 預設 2y、快取鍵、`WINDOW_DAYS_MAX` 完全不變（測試釘住）。
    TAIEX／S&P 500：`(ticker, "5y")`。視窗切片在客戶端（`ui_v2/mkt/chart.py`）。
    FRED：`n` ＝ `FRED_VIEW_OBSERVATION_LIMIT`（1500，最新 n 筆）；與 B 線（vintage 讀法）不同函式、不同快取鍵。
    ⚠️ 本 session 沒有對 FRED 真實連線驗證回應（見檔頭）。
    """
    # 經 `market_indicator` 模組取 L1 函式（呼叫時才解析）：與 B 線 `vol_index` 用的是同一個屬性，
    # 測試替身換 `market_indicator.fetch_yf_close_with_error` 時兩邊一起換，不會一邊真打網路。
    fetch = fetch_vix if fetch_vix is not None else market_indicator.fetch_yf_close_with_error
    series, error = _call(fetch, VIX_TICKER, VIX_RANGE)
    t_series, t_error = _call(fetch_taiex if fetch_taiex is not None else fetch, TAIEX_TICKER, TAIEX_RANGE)
    g_series, g_error = _call(fetch_sp500 if fetch_sp500 is not None else fetch, SP500_TICKER, SP500_RANGE)
    domains = {DOMAIN_VIX: vix_domain_from_l1(series, error),
               DOMAIN_TAIEX: taiex_domain_from_l1(t_series, t_error),
               DOMAIN_SP500: sp500_domain_from_l1(g_series, g_error)}
    has_key = isinstance(fred_api_key, str) and bool(fred_api_key.strip())
    for key, series_id, label in ((DOMAIN_US10Y, US10Y_SERIES, US10Y_SOURCE_LABEL),
                                  (DOMAIN_US2Y, US2Y_SERIES, US2Y_SOURCE_LABEL)):
        if not has_key:
            frame, f_error = None, MISSING_FRED_API_KEY
        else:
            frame, f_error = _call(fetch_fred if fetch_fred is not None
                                   else market_indicator.fetch_fred_with_error,
                                   series_id, fred_api_key, FRED_VIEW_OBSERVATION_LIMIT)
        domains[key] = fred_yield_domain_from_l1(key, frame, f_error, source_label=label)
    for key in _MISSING_DOMAINS:
        domains[key] = missing_domain(key)
    return {
        "domains": [domains[k] for k in DOMAIN_ORDER],
        "provenance": {
            "readonly": True,
            "writes_market_indicator": False,
            "note": "唯讀 Data View；VIX、TAIEX（Yahoo ^TWII，非 TWSE 官方）、S&P 500（Yahoo ^GSPC）沿用同一支 L1 取數與收盤規則；"
                    "美債殖利率取 FRED 觀測日資料（`fetch_fred`）；其餘 domain 無正式來源，一律資料未備。",
        },
    }
