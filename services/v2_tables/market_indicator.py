# -*- coding: utf-8 -*-
"""市場總覽（mkt）的 `market_indicator` 表：L1 `*_with_error` 回傳 → `44` 表列。

依據 docs/v2/49_data_integration_plan.md：
- §2.1 每個鍵的建議來源；§2.6 不可空缺口的第一階段處置；§2.8 必須保留的行為；
- §6.1 客戶 2026-09-26 裁示：Q1 政策利率看美國聯邦基金利率；Q2 景氣指標看台灣國發會；
  Q3 (a) 日頻收盤行情公布日＝觀測日、(b) 日頻收盤行情 `is_revised` 一律為否、
  (c) 來源不給公布日的月頻指標（國發會景氣指標）第一階段顯示資料未備；
- §6.2 T1：FRED 的公布日與版次要帶 vintage 參數才拿得到；**做好之前 FRED 三鍵不寫列**。

⇒ 第一階段只有 `vol_index` 寫列；其餘六個鍵不寫列、也不取數（取回來也寫不進去，
   只會多打來源；v3 §02「不連續轟炸來源」）。`fx_twd_per_usd` 是總管 2026-09-26 裁定暫停
   （見 `FX_OBS_DATE_RULE_VERIFIED`）。不寫列的原因以代碼記在回傳的 `pending`，
   說明文字記在 `skipped`；兩者都不是錯誤、不進 `errors`。

**取數函式與區間（技術選擇，寫明理由）**：
- 匯率改用 `repositories/macro/yf.py::fetch_yf_close_with_error("USDTWD=X")`，**不用** 49 §2.1
  建議的 `repositories/hot_money_repository.py::fetch_usdtwd_series`，理由三條：
  (1) 後者在 Yahoo 回空那一支交出的是固定字串，不是來源原文；
  (2) 後者的 `attrs["fetched_at"]` 是它在未快取那一層轉換當下寫的時間，不是 L1 真正的取得時間；
  (3) 後者另疊一層 `st.cache_data`，與 49 §4.4「快取只在 L1 一層」相違。
- `range_` 用 L1 預設的 `"2y"`（兩年日線，約 500 筆／鍵）。49 沒有訂區間；MKT-4 觀察窗由使用者
  自填、上限不定，取兩年是為了讓常見觀察窗有資料可比，也與 L1 預設值共用同一個快取項。

**import 白名單**：本套件只 import 標準庫、L0（`shared`）、L1（`repositories`）與同套件，
**另外允許 `pandas`**（處理 L1 回傳的 Series／Timestamp）。docs/v2/49 §3.5 的白名單描述尚未列
`pandas`，留待下一輪改文件（本輪文件類只准動 ACCEPTANCE.md）。

規則（`CLAUDE.md` §1、`44` 第四節開頭、49 §2.8）：
- 失敗原文逐字放進 `errors[鍵]`；L1 拋例外時放 `型別名: 訊息`；不吞、不改寫。
- 不可空欄位取不到值 → 該列不寫入；不以 0、空字串、前一筆、當下時間補。
- `fetched_at` 取 L1 回傳的 `attrs["fetched_at"]`（快取命中時仍是當初的取得時間），
  只換算成世界協調時間的同一瞬間；取不到或沒有時區 → 該鍵整批不寫。
- 本模組不另疊快取（49 §4.4：外部取數的快取只在 L1）。
- 錯誤原文在本層**不遮蔽**；遮蔽在寫出點做一次（`services/v2_tables/masking.py`，
  由 `ui_v2/mkt/source.py` 呼叫；ACCEPTANCE 七）。
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Callable, Optional

import pandas as pd

from repositories.macro.yf import YF_CHART_BASE, fetch_yf_close_with_error
from repositories.v2_source_status import cooling_sources, host_of
from services.v2_tables.contract import (
    MARKET_INDICATOR_FIELDS,
    market_indicator_row_problems,
)
from shared.fred_series import FRED_FED_FUNDS, FRED_HY_SPREAD, FRED_T10Y2Y

SOURCE_TIER = "市場指標"  # `44` 值域四個之一；49 §2.1：舊的 T1／T2 不在值域內

# 49 §3.3 第 5 步：L1 回空、又沒交出原因時，只能寫這句如實但較弱的訊息，不得自行編造原因。
EMPTY_WITHOUT_REASON = "來源回傳空值，原因未提供"

# 總管 2026-09-26 裁定（稽核必修 1）：Yahoo `USDTWD=X` 日線的時間戳可能落在世界協調時間
# 前一天（例如 23:00 UTC），以世界協調時間取日期會差一天；本環境連不到 Yahoo，無法以真實資料驗證。
# ⇒ 驗證之前 `fx_twd_per_usd` 不取數、不寫列，顯示資料未備。**驗證完只改這一處（改成 True）即恢復。**
FX_OBS_DATE_RULE_VERIFIED = False

# 不寫列的原因代碼（L3 依代碼對照客戶核准的畫面文案；未知代碼在 L3 當場炸）。
PENDING_FRED_RELEASE_DATE = "fred_release_date"
PENDING_NDC_NO_RELEASE_DATE = "ndc_no_release_date"
PENDING_FX_OBS_DATE_RULE = "fx_obs_date_rule"

_PENDING_FX = "USDTWD=X 的觀測日切日規則待以真實資料驗證（總管 2026-09-26 裁定；FX_OBS_DATE_RULE_VERIFIED）"

_PENDING_FRED = (
    "FRED 的公布日要帶 vintage 參數才拿得到（49 §6.2 T1），尚未實作；"
    "做好之前不寫列（49 §2.6）"
)
_PENDING_NDC = (
    "國發會景氣指標來源不給公布日；客戶 2026-09-26 裁示 Q3(c)：第一階段顯示資料未備"
)

# 七個鍵的來源對照。`phase1`：`write`＝第一階段取數並寫列；`pending`＝不取數、不寫列。
# `source` 是（來源, 序列或欄位）；鍵名以 ui_v2/mkt/fixtures.py 的六鍵＋第七鍵為準（測試比對）。
INDICATOR_SPECS = {
    "vol_index": {
        "source": ("Yahoo", "^VIX"), "value_unit": "index",
        "phase1": "write", "pending_reason": None, "pending_code": None,
    },
    "fx_twd_per_usd": {
        # 49 §4.6：單位字面值以 MKT-3 的宣告為準。方向是「新臺幣／美元」，USDTWD=X 即此方向。
        # phase1 由 FX_OBS_DATE_RULE_VERIFIED 決定（見 `_phase1_of`）。
        "source": ("Yahoo", "USDTWD=X"), "value_unit": "新臺幣／美元",
        "phase1": "write_if_fx_verified", "pending_reason": _PENDING_FX,
        "pending_code": PENDING_FX_OBS_DATE_RULE,
    },
    "credit_spread_pct": {
        "source": ("FRED", FRED_HY_SPREAD), "value_unit": "pp",
        "phase1": "pending", "pending_reason": _PENDING_FRED,
        "pending_code": PENDING_FRED_RELEASE_DATE,
    },
    "term_spread_pct": {
        "source": ("FRED", FRED_T10Y2Y), "value_unit": "pp",
        "phase1": "pending", "pending_reason": _PENDING_FRED,
        "pending_code": PENDING_FRED_RELEASE_DATE,
    },
    "policy_rate_pct": {
        # Q1：美國聯邦基金利率（月頻）。FRED 三鍵下一階段接
        # `repositories/macro/fred.py::fetch_fred_with_error` ＋ T1 的 vintage 公布日（本批不呼叫）。
        "source": ("FRED", FRED_FED_FUNDS), "value_unit": "%",
        "phase1": "pending", "pending_reason": _PENDING_FRED,
        "pending_code": PENDING_FRED_RELEASE_DATE,
    },
    "leading_index": {
        # Q2：台灣國發會；下一階段接 L1 公開出口
        # `repositories/macro_tw_local_repository.py::fetch_tw_business_indicator_with_error`
        # 的 `leading` 欄（本批不 import、不呼叫）。
        "source": ("FinMind:TaiwanBusinessIndicator", "leading"), "value_unit": "index",
        "phase1": "pending", "pending_reason": _PENDING_NDC,
        "pending_code": PENDING_NDC_NO_RELEASE_DATE,
    },
    "coincident_index": {
        "source": ("FinMind:TaiwanBusinessIndicator", "coincident"), "value_unit": "index",
        "phase1": "pending", "pending_reason": _PENDING_NDC,
        "pending_code": PENDING_NDC_NO_RELEASE_DATE,
    },
}

def _phase1_of(spec) -> str:
    if spec["phase1"] == "write_if_fx_verified":
        return "write" if FX_OBS_DATE_RULE_VERIFIED else "pending"
    return spec["phase1"]


def _utc_iso(fetched_at) -> Optional[str]:
    """L1 的 fetched_at → 世界協調時間 ISO 字串（同一瞬間）；取不到、沒有時區回 None。"""
    if not isinstance(fetched_at, str) or not fetched_at:
        return None
    try:
        parsed = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    if parsed.utcoffset().total_seconds() == 0:
        return fetched_at
    return parsed.astimezone(timezone.utc).isoformat()


def _obs_date(stamp) -> str:
    """序列索引 → 觀測日。L1 以 Unix 秒建索引（無時區＝世界協調時間）；有時區則先換算。"""
    ts = pd.Timestamp(stamp)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC")
    return ts.date().isoformat()


def rows_from_daily_close(key: str, series, error, *, value_unit: str):
    """日頻收盤行情（Q3 a/b）→ (rows, error_text, skipped_reasons)。

    - error 非空：原文照回，不寫列。
    - 空序列又沒有原因：回 49 訂的弱訊息，不寫列。
    - `fetched_at` 取不到或沒有時區：整批不寫（不以當下時間補），記進 skipped。
    - 觀測日不早於取得日（世界協調時間）：可能是未收盤的盤中值，Q3 的「收盤行情」前提
      不成立 → 不寫，記進 skipped。
    - 同一觀測日重複：主鍵（indicator_key, obs_date, release_date）會撞 → 該日全部不寫。
    - 非有限數值：不寫，記進 skipped。
    """
    if error:
        return [], str(error), []
    if series is None or len(series) == 0:
        return [], EMPTY_WITHOUT_REASON, []

    skipped = []
    fetched_at = _utc_iso(getattr(series, "attrs", {}).get("fetched_at"))
    if fetched_at is None:
        skipped.append(f"L1 回傳的 fetched_at 取不到或沒有時區，{len(series)} 筆全部不寫")
        return [], None, skipped
    fetched_day = datetime.fromisoformat(fetched_at.replace("Z", "+00:00")).date().isoformat()

    candidates = []
    for stamp, value in series.items():
        candidates.append((_obs_date(stamp), value))
    counts = {}
    for obs, _value in candidates:
        counts[obs] = counts.get(obs, 0) + 1

    not_finite = not_closed = duplicated = contract_bad = 0
    rows = []
    for obs, value in candidates:
        if counts[obs] > 1:
            duplicated += 1
            continue
        if obs >= fetched_day:
            not_closed += 1
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            not_finite += 1
            continue
        if not math.isfinite(number):
            not_finite += 1
            continue
        row = {
            "indicator_key": key,
            "obs_date": obs,
            "release_date": obs,          # Q3(a)
            "value_num": number,
            "value_unit": value_unit,
            "source_tier": SOURCE_TIER,
            "is_revised": False,          # Q3(b)
            "fetched_at": fetched_at,
        }
        if market_indicator_row_problems(row):
            contract_bad += 1
            continue
        rows.append(row)

    if not_finite:
        skipped.append(f"數值非有限值 {not_finite} 筆不寫")
    if not_closed:
        skipped.append(f"觀測日不早於取得日（{fetched_day}，世界協調時間）{not_closed} 筆不寫")
    if duplicated:
        skipped.append(f"同一觀測日重複 {duplicated} 筆不寫")
    if contract_bad:
        skipped.append(f"不符欄位契約 {contract_bad} 筆不寫")
    return rows, None, skipped


def _call(fetch: Callable, *args):
    """呼叫 L1 `*_with_error`；L1 拋例外時轉成 (None, '型別名: 訊息')，不吞。"""
    try:
        return fetch(*args)
    except Exception as exc:  # noqa: BLE001 —— 轉成可見的失敗原文，不是吞掉
        return None, f"{type(exc).__name__}: {exc}"


def build_market_indicator_table(*, sink: Optional[Callable[[dict], None]] = None) -> dict:
    """組出 `market_indicator` 表的列。

    回傳 `{"rows": [...], "errors": {鍵: 原文}, "pending": {鍵: 原因代碼},
           "skipped": {鍵: [不寫列的理由, ...]}}`。
    `pending` 只列「第一階段刻意不取數」的鍵；`skipped` 另含取數後逐筆被略過的理由。
    `rows` 每一列逐欄照 `44` 的八欄、順序同契約。

    `sink`：Q12（`market_indicator` 與 `fetch_log` 落地到設定試算表）的**介面接縫**。
    本批不做落地；傳 None（預設）時什麼都不寫。傳入時以同一份回傳值呼叫一次，
    寫入端拋的例外照樣往上拋（不吞）。
    """
    rows, errors, pending, skipped = [], {}, {}, {}
    for key, spec in INDICATOR_SPECS.items():
        if _phase1_of(spec) != "write":
            pending[key] = spec["pending_code"]
            skipped[key] = [spec["pending_reason"]]
            continue
        _source, ticker = spec["source"]
        series, error = _call(fetch_yf_close_with_error, ticker)
        key_rows, key_error, key_skipped = rows_from_daily_close(
            key, series, error, value_unit=spec["value_unit"])
        rows.extend(key_rows)
        if key_error is not None:
            errors[key] = key_error
        if key_skipped:
            skipped[key] = key_skipped

    names = [name for name, _k, _n in MARKET_INDICATOR_FIELDS]
    for row in rows:  # 出口前再核一次欄位與順序；不該發生，發生就是本檔的 bug（§1：當場炸）
        if list(row) != names:
            raise AssertionError(f"market_indicator 列的欄位與契約不符：{list(row)}")
    table = {"rows": rows, "errors": errors, "pending": pending, "skipped": skipped}
    if sink is not None:
        sink(table)
    return table


def phase1_hosts() -> list:
    """第一階段真的會去取數的來源主機（退避鍵），供「重新取數」停用原因列出冷卻狀態。"""
    hosts = []
    for spec in INDICATOR_SPECS.values():
        if _phase1_of(spec) == "write" and spec["source"][0] == "Yahoo":
            hosts.append(host_of(f"{YF_CHART_BASE}/{spec['source'][1]}"))
    return list(dict.fromkeys(hosts))


def source_cooldowns() -> list:
    """第一階段來源之中仍在冷卻的，每筆 `{"source", "remaining_sec", ...}`，剩餘秒數由多到少。"""
    return cooling_sources(phase1_hosts())
