# -*- coding: utf-8 -*-
"""市場總覽（mkt）的 `market_indicator` 表：L1 `*_with_error` 回傳 → `44` 表列。

依據 docs/v2/49_data_integration_plan.md：
- §2.1 每個鍵的建議來源；§2.6 不可空缺口的第一階段處置；§2.8 必須保留的行為；
- §6.1 客戶 2026-09-26 裁示：Q1 政策利率看美國聯邦基金利率；Q2 景氣指標看台灣國發會；
  Q3 (a) 日頻收盤行情公布日＝觀測日、(b) 日頻收盤行情 `is_revised` 一律為否、
  (c) 來源不給公布日的月頻指標（國發會景氣指標）第一階段顯示資料未備；
- §6.2 T1：FRED 的公布日與版次要帶 vintage 參數才拿得到；~~**做好之前 FRED 三鍵不寫列**~~
  → **2026-10-13 狀態更新（不是漏刪；客戶 2026-10-13 裁示「切換前市場總覽真資料必須完成」）**：
  T1 已實作 —— 經 49 §6.3 N-3 的新 L1 檔 `repositories/macro/fred_vintage.py`
  （同一個 FRED 端點、同一把金鑰，多帶 `realtime_start`／`realtime_end`／`output_type=1`），
  每一筆取**首次公布日**當 `release_date`、修正版次另成一列且 `is_revised` 為真（44 主鍵含
  `release_date`、「修正不覆蓋原列」）。對不上公布日的觀測整筆不寫（見 `rows_from_fred_vintages`）。
  舊句在寫下當時為真（當時 L1 只有 `fetch_fred`，它的 `realtime_start` 是查詢當天）。

⇒ ~~第一階段只有 `vol_index` 寫列；其餘六個鍵不寫列、也不取數~~ → 現行：`vol_index` 與
   FRED 三鍵（`credit_spread_pct`／`term_spread_pct`／`policy_rate_pct`）取數並寫列；
   國發會兩鍵與 `fx_twd_per_usd` 不寫列、也不取數（取回來也寫不進去，
   只會多打來源；v3 §02「不連續轟炸來源」）。`fx_twd_per_usd` 是總管 2026-09-26 裁定暫停
   （見 `FX_OBS_DATE_RULE_VERIFIED`）。不寫列的原因以代碼記在回傳的 `pending`，
   說明文字記在 `skipped`；兩者都不是錯誤、不進 `errors`。
   2026-10-13：非美元幣別的匯率鍵（49 §6.1 Q9）另由 `build_fx_indicator_table` 交出，
   套同一條觀測日規則、同一個閘門；`INDICATOR_SPECS` 七鍵不變（市場總覽頁的鍵以它為準）。

**取數函式與區間（技術選擇，寫明理由）**：
- 匯率改用 `repositories/macro/yf.py::fetch_yf_close_with_error("USDTWD=X")`，**不用** 49 §2.1
  建議的 `repositories/hot_money_repository.py::fetch_usdtwd_series`，理由三條：
  (1) 後者在 Yahoo 回空那一支交出的是固定字串，不是來源原文；
  (2) 後者的 `attrs["fetched_at"]` 是它在未快取那一層轉換當下寫的時間，不是 L1 真正的取得時間；
  (3) 後者另疊一層 `st.cache_data`，與 49 §4.4「快取只在 L1 一層」相違。
- `range_` 用 L1 預設的 `"2y"`（兩年日線，約 500 筆／鍵）。49 沒有訂區間；MKT-4 觀察窗由使用者
  自填、上限不定，取兩年是為了讓常見觀察窗有資料可比。
  ⚠️ 快取不見得與其他呼叫端共用：`infra/cache.py::_ttl_cache` 的快取鍵是
  `(args, tuple(sorted(kwargs.items())))`，只看呼叫時實際傳入的引數、不補預設值，所以位置參數
  與關鍵字參數、有沒有明寫預設值，都會落在不同的快取鍵。本模組經 `fetch_yf_close_with_error`
  以位置參數 `(ticker, "2y", "1d")` 呼叫 `fetch_yf_close`，只會與同樣三個位置參數的呼叫共用快取。

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
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd

from repositories.macro.fred import FRED_BASE
from repositories.macro.fred_vintage import (
    REALTIME_END_LATEST,
    fetch_fred_vintages_with_error,
)
from repositories.macro.yf import EXCHANGE_TZ_ATTR, YF_CHART_BASE, fetch_yf_close_with_error
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
# ⇒ 驗證之前 `fx_twd_per_usd` 不取數、不寫列，顯示資料未備。
# ~~⚠️ 驗證確認 UTC 切日正確，才可以只改這一處；否則要先改判準（`_obs_date` 的切日規則）。~~
# → 2026-10-13 狀態更新（不是漏刪；客戶 2026-10-13 裁示）：探測報告
#   （`probe/fx-obs-date-results` 分支 `results/20261013T185433Z_run38450455092/report.json`）證實
#   UTC 切日**不正確**（匯率日線時間戳＝倫敦當地 00:00，夏令時 UTC 取日早一天），所以走的是上句的「否則」：
#   判準已改為「**以來源自報的交易所時區（`meta.exchangeTimezoneName`）的當地日期為準**」（見 `_obs_date`、
#   `rows_from_daily_close`）。**本格仍為 False**：新規則要在合併後**重跑探測**、以真實回應確認
#   （週末 0、同日重複 0、正式路徑列數合理）之後，才可以**只改這一格**。
#   舊句在寫下當時為真（當時還不知道哪一種切日才對），被推翻的是它「UTC 可能正確」的前提。
FX_OBS_DATE_RULE_VERIFIED = False

# 不寫列的原因代碼（L3 依代碼對照客戶核准的畫面文案；未知代碼在 L3 當場炸）。
PENDING_FRED_RELEASE_DATE = "fred_release_date"
PENDING_NDC_NO_RELEASE_DATE = "ndc_no_release_date"
PENDING_FX_OBS_DATE_RULE = "fx_obs_date_rule"

_PENDING_FX = "USDTWD=X 的觀測日切日規則待以真實資料驗證（總管 2026-09-26 裁定；FX_OBS_DATE_RULE_VERIFIED）"

# ⚠️ 2026-10-13 起 FRED 三鍵改為取數寫列（T1 已實作），本代碼與下一句說明**目前沒有任何鍵使用**；
#    刻意保留不刪：L3 `ui_v2/mkt/live.py::REASON_TEXT` 仍有對照文案（未知代碼在 L3 當場炸，
#    留著對照不會讓任何東西變寬），而 FRED 若日後因故暫停，回到 pending 只需改 `phase1` 一格。
_PENDING_FRED = (
    "FRED 的公布日要帶 vintage 參數才拿得到（49 §6.2 T1），尚未實作；"
    "做好之前不寫列（49 §2.6）"
)

# 49 §4.1：「轉換層先檢查 key，缺 key 直接寫成錯誤原文『未設定 FRED_API_KEY』」。
MISSING_FRED_API_KEY = "未設定 FRED_API_KEY"
# FRED 觀測往回取多少個日曆日（與 Yahoo 的 `range_="2y"` 對齊；49 沒有訂區間，理由同上方 `range_` 段）。
FRED_LOOKBACK_DAYS = 730
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
        # 2026-10-13：~~"phase1": "pending"~~ → "write"（T1 已實作，見檔頭；狀態更新，不是漏刪）。
        # FRED 單位為 Percent；利差是兩個百分比之差 ＝ 百分點，照 44 MKT-1 寫 `pp`，不換算。
        "source": ("FRED", FRED_HY_SPREAD), "value_unit": "pp",
        "phase1": "write", "pending_reason": None, "pending_code": None,
    },
    "term_spread_pct": {
        # 2026-10-13：~~"phase1": "pending"~~ → "write"（T1 已實作，見檔頭；狀態更新，不是漏刪）。
        # FRED 單位為 Percent；利差是兩個百分比之差 ＝ 百分點，照 44 MKT-1 寫 `pp`，不換算。
        "source": ("FRED", FRED_T10Y2Y), "value_unit": "pp",
        "phase1": "write", "pending_reason": None, "pending_code": None,
    },
    "policy_rate_pct": {
        # Q1：美國聯邦基金利率（月頻）。~~FRED 三鍵下一階段接
        # `repositories/macro/fred.py::fetch_fred_with_error` ＋ T1 的 vintage 公布日（本批不呼叫）。~~
        # → 2026-10-13 接 `repositories/macro/fred_vintage.py::fetch_fred_vintages_with_error`
        #   （49 §6.3 N-3；`fetch_fred` 本體未動）。單位 FRED 為 Percent，照 44 MKT-3 寫 `%`。
        "source": ("FRED", FRED_FED_FUNDS), "value_unit": "%",
        "phase1": "write", "pending_reason": None, "pending_code": None,
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

# ── 非美元幣別的匯率鍵（49 §6.1 Q9，客戶 2026-09-26 同意）──────────────────────────────
# Q9 原文：「新增對應幣別的匯率鍵，由 L2 轉換層直接呼叫既有的 L1 `repositories/macro/yf.py::fetch_yf_close`
# （例：`EURTWD=X`）」。不新增資料源：同一個 Yahoo 端點、同一個 L1 函式。
# - 鍵名：沿用 `fx_twd_per_usd` 的形狀，`fx_twd_per_` ＋ ISO 4217 代碼小寫（例：`fx_twd_per_eur`）。
#   ⚠️ 44 只定義了 `fx_twd_per_usd`；其餘鍵名是 Q9「新增對應幣別的匯率鍵」的落地寫法（2026-10-13 資料工程組），
#   不是 44 的原文。`ui_v2/alo/logic.py::fx_key_for` 是本規則的字面鏡像（ui_v2 不得 import services），
#   由 tests/test_v2_tables_market_indicator_fx_ccy.py 逐幣比對。
# - Yahoo 代碼：`<ISO>TWD=X`（同 `repositories/fund/fx_and_main.py::get_latest_fx` 的既有組法）；
#   方向「新臺幣／該幣」，與 `USDTWD=X` 同向，不取倒數。
# - **觀測日規則與美元同一條、同一個閘門**（`FX_OBS_DATE_RULE_VERIFIED`）：閘門關閉時不取數、不寫列，
#   原因代碼同 `PENDING_FX_OBS_DATE_RULE`（只會多打來源，v3 §02）。
# - 美元**不走這裡**：`fx_twd_per_usd` 住在 `INDICATOR_SPECS`（市場總覽頁的七鍵之一，經設定試算表落地）；
#   傳 `USD`／`TWD` 進來是呼叫端的 bug，當場炸。
FX_KEY_PREFIX = "fx_twd_per_"
# `value_unit` 字面值：美元沿用 MKT-3 的宣告「新臺幣／美元」；其餘幣別 44 沒有宣告，寫「新臺幣／<ISO 代碼>」
# （不自行翻譯幣名）。⚠️ 這一句不是 44 的原文，閘門打開前要一併覆核。
_FX_USD_UNIT = "新臺幣／美元"


def _require_iso_ccy(ccy) -> str:
    if not (isinstance(ccy, str) and len(ccy) == 3 and all("A" <= ch <= "Z" for ch in ccy)):
        raise ValueError(f"幣別須為 ISO 4217 三個大寫英文字母：{ccy!r}")
    return ccy


def fx_indicator_key(ccy) -> str:
    """幣別 → 匯率鍵（`USD` → `fx_twd_per_usd`；`EUR` → `fx_twd_per_eur`）。新臺幣沒有匯率鍵 → 炸。"""
    if _require_iso_ccy(ccy) == "TWD":
        raise ValueError("新臺幣不需要換算匯率鍵")
    return FX_KEY_PREFIX + ccy.lower()


def fx_yahoo_ticker(ccy) -> str:
    """幣別 → Yahoo 代碼（`USD` → `USDTWD=X`，與 `INDICATOR_SPECS` 那一格相同）。"""
    if _require_iso_ccy(ccy) == "TWD":
        raise ValueError("新臺幣不需要換算匯率")
    return f"{ccy}TWD=X"


def fx_value_unit(ccy) -> str:
    if _require_iso_ccy(ccy) == "USD":
        return _FX_USD_UNIT
    return f"新臺幣／{ccy}"


def build_fx_indicator_table(ccys) -> dict:
    """非美元幣別的匯率鍵（Q9）。回傳形狀同 `build_market_indicator_table`：
    `{"rows", "errors", "pending", "skipped", "fetched"}`，鍵為各幣別的匯率鍵。

    - 閘門（`FX_OBS_DATE_RULE_VERIFIED`）關閉：不取數、不寫列，`pending[鍵] = PENDING_FX_OBS_DATE_RULE`，
      說明記在 `skipped`；不進 `errors`（不是失敗，是資料未備）。
    - 閘門打開：經 `fetch_yf_close_with_error(<ISO>TWD=X)` 取數，套 `rows_from_daily_close`（與美元同一條規則）。
    - 同一幣別重複出現只處理一次；`USD`／`TWD`／不合 ISO 4217 → ValueError（呼叫端的 bug）。
    - 不另疊快取（49 §4.4）；不寫任何試算表；錯誤原文不遮蔽（遮蔽在寫出點做一次）。
    - ⚠️ 登記（2026-10-13 稽核 N4）：`phase1_hosts()`／`source_cooldowns()` 只列 `INDICATOR_SPECS` 那幾鍵的來源，
      **不涵蓋**這裡的 `<ISO>TWD=X`；「重新取數」停用原因看不到它們的冷卻狀態。閘門關閉時本函式不取數，目前無實害；
      閘門打開前一併處理。
    """
    rows, errors, pending, skipped, fetched = [], {}, {}, {}, {}
    for ccy in dict.fromkeys(ccys):
        if _require_iso_ccy(ccy) in ("USD", "TWD"):
            raise ValueError(f"{ccy} 不走這裡（美元在 INDICATOR_SPECS；新臺幣不需要匯率）")
        key = fx_indicator_key(ccy)
        ticker = fx_yahoo_ticker(ccy)
        if not FX_OBS_DATE_RULE_VERIFIED:
            pending[key] = PENDING_FX_OBS_DATE_RULE
            skipped[key] = [f"{ticker} 與 USDTWD=X 套同一條觀測日切日規則、同一個閘門，"
                            f"待以真實資料驗證（FX_OBS_DATE_RULE_VERIFIED）"]
            continue
        series, error = _call(fetch_yf_close_with_error, ticker)
        fetched[key] = 0 if (error or series is None) else len(series)
        key_rows, key_error, key_skipped = rows_from_daily_close(
            key, series, error, value_unit=fx_value_unit(ccy))
        rows.extend(key_rows)
        if key_error is not None:
            errors[key] = key_error
        if key_skipped:
            skipped[key] = key_skipped
    # 2026-10-13 稽核 N4：出口前核欄位與順序（同 `build_market_indicator_table`；不該發生，發生就是本檔的 bug，當場炸）。
    names = [name for name, _k, _n in MARKET_INDICATOR_FIELDS]
    for row in rows:
        if list(row) != names:
            raise AssertionError(f"market_indicator 列的欄位與契約不符：{list(row)}")
    return {"rows": rows, "errors": errors, "pending": pending, "skipped": skipped, "fetched": fetched}


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


# 不接受的 tzdata 子樹：`posix/`、`right/` 是同一份資料的別名樹（`right/` 還含閏秒），不是交易所會自報的名稱。
_REJECTED_TZ_PREFIXES = ("posix/", "right/")


def exchange_zone(name) -> Optional[ZoneInfo]:
    """來源自報的交易所時區字串 → `ZoneInfo`；認不得 → None（呼叫端走「該鍵整批不寫」）。

    **不推定**：不退回世界協調時間、不查任何寫死的「代碼 → 時區」對照表（客戶 2026-10-13 裁示：
    以來源自報的交易所時區為準；來源沒報就是不知道）。字串原樣交給 zoneinfo，不修剪、不改大小寫。

    回 None 的情形（2026-10-14 稽核 N／M 合併修正輪補齊）：
    - 缺、不是字串、空字串；
    - **不是 `Area/Location` 形式**（不含 `/`）：例如 `Factory`、`posixrules`、`UTC`、`GMT`、`EST5EDT` ——
      zoneinfo 認得它們，但它們不是交易所會自報的 IANA 地區名稱，一律拒絕（要表示世界協調時間請用 `Etc/UTC`）。
      ⚠️ **刻意的明確失敗，不是靜默錯值**：日後若新增回報這類名稱的標的（例如某些加密貨幣報價可能自報 `UTC`），
      該鍵會整批不寫，skipped 寫明「無法辨識」；要支援它須另案決定，不得在這裡放寬（登記於 docs/v2/49 第 8 節 (i)）；
    - `posix/`、`right/` 開頭（tzdata 的別名子樹）；
    - zoneinfo 拋 `ZoneInfoNotFoundError`、`ValueError`（例如含 `..`、結尾 `/`），或 **`OSError`**：
      目錄名（`America/Argentina` → `IsADirectoryError`）、名稱過長（`ENAMETOOLONG`）。
      ⚠️ 不接住 `OSError` 的話，一個怪字串就會讓整張市場指標表（含 FRED 鍵）炸掉。
    """
    if not isinstance(name, str) or not name or "/" not in name:
        return None
    if name.startswith(_REJECTED_TZ_PREFIXES):
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return None


def not_closed_cutoff_day(fetched_at_utc_iso: str, zone: ZoneInfo) -> str:
    """「未收盤」的界線日：觀測日 ≥ 本日期的根視為未收盤、不寫。

    界線 ＝ max(取得時刻的世界協調時間日期, 取得時刻的交易所當地日期)
    （AI 總管 2026-10-14 裁決，內部自決；稽核 M 實測後訂定）。
    - 匯率（`Europe/London`）：倫敦日期不早於世界協調時間日期 ⇒ 界線＝倫敦日期，與只看交易所當地日期相同。
    - ^VIX（`America/Chicago`）：芝加哥日期不晚於世界協調時間日期 ⇒ 界線＝世界協調時間日期，**與舊規則相同**。
      這一條成立的前提：**CBOE 收盤（15:15 CT）早於世界協調時間午夜**（CDT 19:00、CST 18:00），
      所以世界協調時間換日時，芝加哥當天那一根必已收盤；**另一半前提**：隔日的延長時段報價不會回頭改到前一天那根
      —— 依據是探測所見每根日 K 從芝加哥 02:00 起算（下一根從隔日 02:00 開始），**未以 CBOE 官方時刻表查證**。
      這是**保留既有 VIX 時效，不是新語意**：
      若只看芝加哥日期，世界協調時間 00:00～05:00／06:00 之間取數會把前一個美國交易日已定案的收盤
      多扣約 5 小時（稽核 M 實測：取得於 2026-10-14T02:00Z，舊規則最後一根 10-13，只看芝加哥日期會變 10-12）。
      ⚠️ 換成收盤晚於世界協調時間午夜的交易所（例如美洲以西），這個前提就不成立，要另外檢討。
    """
    fetched = datetime.fromisoformat(fetched_at_utc_iso.replace("Z", "+00:00"))
    utc_day = fetched.astimezone(timezone.utc).date().isoformat()
    local_day = fetched.astimezone(zone).date().isoformat()
    return max(utc_day, local_day)


def _local_stamp(stamp, zone: ZoneInfo) -> pd.Timestamp:
    """序列索引 → 交易所時區的當地時刻。

    L1 以 `pd.to_datetime(秒, unit="s")` 建索引：不帶時區＝世界協調時間，故先 `tz_localize("UTC")`；
    已帶時區者直接 `tz_convert`。
    """
    ts = pd.Timestamp(stamp)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert(zone)


def _obs_date(stamp, exchange_tz) -> str:
    """序列索引 → 觀測日（**交易所時區的當地日期**；客戶 2026-10-13 裁示）。

    ~~L1 以 Unix 秒建索引（無時區＝世界協調時間）；有時區則先換算。~~（舊規則取**世界協調時間**的日期；
    2026-10-13 有意識的變更，不是漏刪 —— 探測報告證實匯率日線時間戳＝倫敦當地 00:00，夏令時以 UTC 取日
    會早一天、出現週日觀測日、缺週五；舊規則在寫下時是唯一可推的做法，被推翻的是「UTC 日＝交易日」的前提。）

    `exchange_tz`：來源自報的時區字串（例：`"Europe/London"`）或 `ZoneInfo`。
    認不得 → `ValueError`（呼叫端應先以 `exchange_zone` 檢查並整鍵不寫；走到這裡代表呼叫端的 bug，§1 當場炸）。
    """
    zone = exchange_tz if isinstance(exchange_tz, ZoneInfo) else exchange_zone(exchange_tz)
    if zone is None:
        raise ValueError(f"交易所時區無法辨識：{exchange_tz!r}（不推定，不退回世界協調時間）")
    return _local_stamp(stamp, zone).date().isoformat()


def rows_from_daily_close(key: str, series, error, *, value_unit: str):
    """日頻收盤行情（Q3 a/b）→ (rows, error_text, skipped_reasons)。

    觀測日＝**來源自報的交易所時區**（L1 `attrs["exchange_tz"]`，即 Yahoo `meta.exchangeTimezoneName`）
    的當地日期（客戶 2026-10-13 裁示）。

    - error 非空：原文照回，不寫列。
    - 空序列又沒有原因：回 49 訂的弱訊息，不寫列。
    - `fetched_at` 取不到或沒有時區：整批不寫（不以當下時間補），記進 skipped。
    - 交易所時區缺、或認不得（見 `exchange_zone`）：整批不寫，記進 skipped（**不推定**：不退回世界協調時間、
      不查寫死的對照表）。L1 快取裡改版前的舊物件沒有這個鍵 → 同樣走這一支，TTL 過期或重啟後自然消失。
    - ~~觀測日不早於「取得時間換成同一交易所時區後的日期」~~ → 觀測日不早於 `not_closed_cutoff_day`
      ＝ max(取得時刻的世界協調時間日期, 取得時刻的交易所當地日期)（AI 總管 2026-10-14 裁決；舊表述會讓
      ^VIX 在世界協調時間剛換日時多扣一天，見該函式；有意識的更正，不是漏刪）：可能是未收盤的盤中值
      （或交易所當天那一根），Q3 的「收盤行情」前提不成立 → 不寫，記進 skipped。
    - 同一觀測日重複：主鍵（indicator_key, obs_date, release_date）會撞 → 該日全部不寫。
      ⚠️ **重複先於未收盤判定**：倫敦當天 00:00 那一根若帶值，又與最後一根盤中值落在同一個倫敦日，
      兩根都**歸「重複」**（不是「未收盤」）；只有一根時才歸「未收盤」。兩種歸類都不寫，差別只在計數落在哪一類。
    - 觀測日（當地）為星期六或星期日：與交易日錯位的跡象 → 不寫並計數。
    - **當地時刻須與同鍵其餘已收盤根一致**（以資料自證日界，不寫死 00:00）：已收盤根之中，
      當地時刻（時:分:秒.微秒）過半數相同者為基準，不同者不寫並計數；沒有任何一個時刻過半數
      → 無法自證日界，已收盤根全部不寫。
      ~~**基準的母體**（2026-10-14 稽核 N 要求寫明並以測試釘住）：同一個鍵之內、觀測日早於未收盤界線的根，
      **含**同日重複根與週末根（它們本身不寫，但計入分母 —— 它們出現就代表日界可疑，計入只會讓基準更難成立，
      不會讓錯位的根被寫進去），**不含**未收盤根（盤中值的時刻不是日界，計入反而會干擾）。~~
      → **分母與票分開**（AI 總管 2026-10-14 裁決；依據：稽核 M 反例；有意識的更正，不是漏刪）：
      - **分母**：同一個鍵之內、觀測日早於未收盤界線的全部根，含同日重複根與週末根；不含未收盤根
        （盤中值的時刻不是日界）。
      - **票**：只有「不重複、且交易所當地為平日」的已收盤根，才替自己的當地時刻投一票。
      - **基準**：某時刻票數 > 分母 / 2（嚴格過半）；沒有任何時刻達標 → 已收盤根全部不寫。
      舊表述的錯：重複根與週末根不只進分母，也替自己的時刻投票；日界錯位時，週一那根會標成週日 23:00，
      週末根天生與錯位根同一時刻，等於替錯位那一邊投票（反例：倫敦冬令 9 根正確 00:00 ＋ 10 根錯位 23:00〔8 平日、
      2 週日〕→ 舊做法基準變 23:00、8 根錯位根被寫入、觀測日早一天）。舊表述的用意（可疑根只能讓基準更難成立）
      仍然成立，改成「只進分母、不投票」之後，那句話才真的成立；代價是基準更難成立，可接受。理由：匯率日線在倫敦 00:00、^VIX 在芝加哥 02:00
      （探測報告實測，夏冬令皆同），所以不能一體要求 00:00；但同一個序列的日線開盤時刻應當一致，
      不一致的那幾根代表那一根的日界不是同一套，取日可能錯位。
      ⚠️ 「過半數」這個門檻是**實作組判準，不是客戶裁示**（決策者：AI 總管，2026-10-13；
      登記於 docs/v2/49 第 8 節 (i)）：「全部相同」在有一根異常時說不出哪一根才對，故取過半數。
      ^VIX 一併套用本規則同樣由 AI 總管決定（探測結果新舊相同，不分流）。
    - 非有限數值：不寫，記進 skipped。
    判定順序（每根只歸一類）：重複 → 未收盤 → 週末 → 當地時刻不一致 → 非有限值 → 契約。
    """
    if error:
        return [], str(error), []
    if series is None or len(series) == 0:
        return [], EMPTY_WITHOUT_REASON, []

    attrs = getattr(series, "attrs", {}) or {}
    skipped = []
    fetched_at = _utc_iso(attrs.get("fetched_at"))
    if fetched_at is None:
        skipped.append(f"L1 回傳的 fetched_at 取不到或沒有時區，{len(series)} 筆全部不寫")
        return [], None, skipped
    raw_tz = attrs.get(EXCHANGE_TZ_ATTR)
    if raw_tz is None or raw_tz == "":
        # ~~「來源未提供交易所時區」~~ → 2026-10-14 稽核合併修正輪改寫（有意識的更正，不是漏刪）：
        # L1 沒帶這個鍵有兩種原因，舊句只寫了一種。
        skipped.append(f"L1 回傳未帶交易所時區（來源未報，或改版前的快取物件；attrs[{EXCHANGE_TZ_ATTR!r}]），"
                       f"不推定，{len(series)} 筆全部不寫")
        return [], None, skipped
    zone = exchange_zone(raw_tz)
    if zone is None:
        skipped.append(f"來源自報的交易所時區 {raw_tz!r} 無法辨識（不是可用的 IANA 地區時區名稱），不推定，"
                       f"{len(series)} 筆全部不寫")
        return [], None, skipped
    fetched_day = not_closed_cutoff_day(fetched_at, zone)

    candidates = []
    for stamp, value in series.items():
        local = _local_stamp(stamp, zone)
        candidates.append((local, local.date().isoformat(), value))
    counts = {}
    for _local, obs, _value in candidates:
        counts[obs] = counts.get(obs, 0) + 1

    # 基準當地時刻（AI 總管 2026-10-14 裁決，依稽核 M 反例；見 docstring）：
    # - 分母：已收盤根（觀測日 < 未收盤界線）全部，含同日重複根與週末根；
    # - 票：只有「不重複、且交易所當地為平日」的已收盤根，替自己的當地時刻投一票；
    # - 某時刻票數 > 分母 / 2（嚴格過半）才成為基準；沒有 → 無基準，已收盤根全部不寫。
    # ~~已收盤根全部替自己的時刻投票~~（舊做法：日界錯位時週一那根落在週日 23:00，週末根天生與錯位根同一時刻，
    # 等於替錯位那一邊投票 —— 稽核 M 反例；有意識的更正，不是漏刪）。
    denominator = 0
    votes: dict = {}
    for local, obs, _value in candidates:
        if obs >= fetched_day:
            continue
        denominator += 1
        if counts[obs] == 1 and local.weekday() < 5:
            votes[local.time()] = votes.get(local.time(), 0) + 1
    reference = None
    if votes:
        top_time = max(votes, key=votes.get)
        if votes[top_time] * 2 > denominator:
            reference = top_time

    not_finite = not_closed = duplicated = contract_bad = weekend = time_mismatch = 0
    rows = []
    for local, obs, value in candidates:
        if counts[obs] > 1:
            duplicated += 1
            continue
        if obs >= fetched_day:
            not_closed += 1
            continue
        if local.weekday() >= 5:
            weekend += 1
            continue
        if reference is None or local.time() != reference:
            time_mismatch += 1
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
        skipped.append(f"觀測日不早於取得日（界線 {fetched_day}：取得時刻的世界協調時間日期與"
                       f"交易所時區 {raw_tz} 日期取較晚者）{not_closed} 筆不寫")
    if duplicated:
        skipped.append(f"同一觀測日重複 {duplicated} 筆不寫")
    if weekend:
        skipped.append(f"觀測日（交易所時區 {raw_tz}）為星期六或星期日 {weekend} 筆不寫")
    if time_mismatch:
        if reference is None:
            spread = "、".join(f"{t.isoformat()}×{n}" for t, n in sorted(votes.items())) or "無"
            skipped.append(f"已收盤根的當地時刻（交易所時區 {raw_tz}）沒有過半數一致的值"
                           f"（票數 {spread}；分母 {denominator}，含重複與週末根，只有不重複的平日根投票），"
                           f"無法自證日界，{time_mismatch} 筆不寫")
        else:
            skipped.append(f"當地時刻與同鍵已收盤根的基準 {reference.isoformat()}"
                           f"（交易所時區 {raw_tz}）不一致 {time_mismatch} 筆不寫")
    if contract_bad:
        skipped.append(f"不符欄位契約 {contract_bad} 筆不寫")
    return rows, None, skipped


def fred_api_key_from(sources) -> str:
    """從各來源 mapping（L3 傳入 `st.secrets`、`os.environ`）取 `FRED_API_KEY`；都沒有回空字串。

    本層**不自己讀** secrets（`masking.py` 檔頭：秘密值在 L3 讀）；這裡只看呼叫端交進來的 mapping，
    體例同 `masking.secret_values`。`st.secrets` 缺檔時 `.get` 會拋 → 當作沒有這個鍵。
    """
    for mapping in sources:
        if mapping is None:
            continue
        try:
            value = mapping.get("FRED_API_KEY")
        except Exception:  # noqa: BLE001 —— st.secrets 缺檔時 .get 會拋；當作沒有這個鍵（同 masking._get）
            value = None
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _utc_today():
    """今天（世界協調時間的日期）。獨立成函式是為了測試能固定它。"""
    return datetime.now(timezone.utc).date()


def _iso_day(value) -> Optional[str]:
    """Timestamp／日期字串 → `YYYY-MM-DD`；NaT、None、解析不了 → None。"""
    if value is None:
        return None
    try:
        ts = pd.Timestamp(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(ts):
        return None
    return ts.date().isoformat()


def rows_from_fred_vintages(key: str, frame, error, *, value_unit: str):
    """FRED 逐版次觀測（L1 `fetch_fred_vintages`）→ (rows, error_text, skipped_reasons)。

    44 `market_indicator`：`release_date` ＝「這一筆對外公布的日期」、主鍵含 `release_date`、
    「同一期間被修正多次時各成一列，修正不覆蓋原列」、`is_revised` ＝「是不是對同一 `obs_date` 的修正」。
    ⇒ 同一個 `date` 的每個版次各寫一列：`release_date` ＝ 該版次的 `realtime_start`；
       最早那一版（＝**首次公布日**）`is_revised` 為否，之後各版為真
       （與 `repositories/settings_sheet_repository.py::_mi_revised` 的重算規則同一條）。

    **對不上公布日的整個觀測期間不寫**（記進 skipped，不以 `obs_date`、查詢日或任何推算值補）：
    - 任一版次的 `realtime_start` 缺或解析不了；
    - 同一期間兩個版次的 `realtime_start` 相同（主鍵會撞）；
    - 最早一版的 `realtime_start` 等於 L1 的查詢下界 `realtime_floor`（分不出是當天公布還是被下界截斷）；
      L1 沒交出 `realtime_floor` → 整鍵不寫；
    - 最早一版的公布日早於觀測期間（不合理）、或任一版的公布日晚於取得日（世界協調時間）。
    值的規則：
    - 現行版次（`realtime_end` ＝ `9999-12-31`）不存在、或其值為缺值 → 該期間不寫（現在 FRED 上沒有這個值）；
    - 中間某版為缺值（FRED `"."`）→ 該版不寫，其餘照寫；第一個有值的版次 `is_revised` 為否。
    - error 非空：原文照回；空表又沒有原因：回 49 訂的弱訊息；`fetched_at` 取不到或沒有時區：整鍵不寫。

    ⚠️ **兩件須知（2026-10-13 稽核後補記；只是註記，不是規格條文）**：
    - **中間版次被撤成缺值時那一版不寫，屬於近似**：44 的表沒有「這一版把值撤掉」的寫法
      （`value_num` 不可空），所以那段期間 FRED 上其實沒有值，而表上看起來是前一版一直有效到下一版。
      不以前後版補值（§1），但讀表的人要知道這一段被省略了。
    - **首次部署要看 `skipped` 計數，特別是 `at_floor` 與 `before_obs`**：本環境沒有以真實 FRED 回應實測過
      （49 §1.3 出入 2 的推論依官方文件）。若這兩類大量出現，代表 ALFRED 版次起點或 `date` 慣例與本檔假設不符
      （例如存檔起點晚於觀測、或月頻 `date` 不是期初），該先查來源再看畫面，不要當成正常的「部分缺」。
    """
    if error:
        return [], str(error), []
    if frame is None or len(frame) == 0:
        return [], EMPTY_WITHOUT_REASON, []

    attrs = getattr(frame, "attrs", {}) or {}
    skipped = []
    fetched_at = _utc_iso(attrs.get("fetched_at"))
    if fetched_at is None:
        skipped.append(f"L1 回傳的 fetched_at 取不到或沒有時區，{len(frame)} 筆全部不寫")
        return [], None, skipped
    fetched_day = datetime.fromisoformat(fetched_at.replace("Z", "+00:00")).date().isoformat()
    raw_floor = attrs.get("realtime_floor")
    floor = _iso_day(raw_floor) if isinstance(raw_floor, str) else None
    if floor is None:
        skipped.append(f"L1 沒交出查詢下界 realtime_floor，分不出公布日是否被截斷，{len(frame)} 筆全部不寫")
        return [], None, skipped

    groups: dict = {}
    bad_obs_date = 0
    for record in frame.to_dict("records"):
        obs = _iso_day(record.get("date"))
        if obs is None:
            bad_obs_date += 1
            continue
        groups.setdefault(obs, []).append(record)

    counts = {"no_release": 0, "dup_release": 0, "at_floor": 0, "before_obs": 0,
              "after_fetch": 0, "not_current": 0, "current_missing": 0, "contract_bad": 0}
    rows = []
    for obs in sorted(groups):
        vintages = []
        broken = None
        for record in groups[obs]:
            release = _iso_day(record.get("realtime_start"))
            if release is None:
                broken = "no_release"
                break
            vintages.append((release, record.get("value"), str(record.get("realtime_end"))))
        if broken is None:
            vintages.sort(key=lambda v: v[0])
            releases = [v[0] for v in vintages]
            if len(set(releases)) != len(releases):
                broken = "dup_release"
            elif releases[0] == floor:
                broken = "at_floor"
            elif releases[0] < obs:
                broken = "before_obs"
            elif releases[-1] > fetched_day:
                broken = "after_fetch"
            elif vintages[-1][2] != REALTIME_END_LATEST:
                broken = "not_current"
        if broken is not None:
            counts[broken] += 1
            continue

        numeric = []
        for release, value, _end in vintages:
            try:
                number = float(value)
            except (TypeError, ValueError):
                number = math.nan
            numeric.append((release, number))
        if not math.isfinite(numeric[-1][1]):
            counts["current_missing"] += 1
            continue

        obs_rows = []
        for release, number in numeric:
            if not math.isfinite(number):
                continue   # 某一版是缺值：那一版不寫（沒有值可寫），不以前後版補
            obs_rows.append({
                "indicator_key": key,
                "obs_date": obs,
                "release_date": release,
                "value_num": number,
                "value_unit": value_unit,
                "source_tier": SOURCE_TIER,
                "is_revised": bool(obs_rows),   # 第一個有值的版次為否，之後各版為真
                "fetched_at": fetched_at,
            })
        # 任一版不符契約 → 整個期間不寫：只丟一版會讓下一版的 `is_revised` 失去它對照的那一列。
        if any(market_indicator_row_problems(row) for row in obs_rows):
            counts["contract_bad"] += 1
            continue
        rows.extend(obs_rows)

    labels = {
        "no_release": "公布日（realtime_start）缺或解析不了",
        "dup_release": "同一期間兩個版次公布日相同（主鍵會撞）",
        "at_floor": f"首次公布日等於查詢下界 {floor}（分不出是否被截斷）",
        "before_obs": "首次公布日早於觀測期間",
        "after_fetch": f"公布日晚於取得日（{fetched_day}，世界協調時間）",
        "not_current": "現行版次已不含此觀測",
        "current_missing": "現行版次的值為缺值",
    }
    if bad_obs_date:
        skipped.append(f"觀測日缺或解析不了 {bad_obs_date} 筆不寫")
    for code, label in labels.items():
        if counts[code]:
            skipped.append(f"{label}：{counts[code]} 個觀測期間整筆不寫")
    if counts["contract_bad"]:
        skipped.append(f"不符欄位契約：{counts['contract_bad']} 個觀測期間整筆不寫")
    return rows, None, skipped


def _call(fetch: Callable, *args):
    """呼叫 L1 `*_with_error`；L1 拋例外時轉成 (None, '型別名: 訊息')，不吞。"""
    try:
        return fetch(*args)
    except Exception as exc:  # noqa: BLE001 —— 轉成可見的失敗原文，不是吞掉
        return None, f"{type(exc).__name__}: {exc}"


def build_market_indicator_table(*, sink: Optional[Callable[[dict], None]] = None,
                                 fred_api_key: Optional[str] = None) -> dict:
    """組出 `market_indicator` 表的列。

    `fred_api_key`：FRED 三鍵用的金鑰，由 L3 以 `fred_api_key_from([st.secrets, os.environ])` 讀好傳入
    （本層不讀 secrets）。None 或空字串 → FRED 三鍵不打 L1，`errors[鍵]` 寫 `MISSING_FRED_API_KEY`
    （49 §4.1）；不是 pending —— 缺金鑰是設定問題，畫面要照實顯示取數失敗。

    回傳 `{"rows": [...], "errors": {鍵: 原文}, "pending": {鍵: 原因代碼},
           "skipped": {鍵: [不寫列的理由, ...]}}`。
    `pending` 只列「第一階段刻意不取數」的鍵；`skipped` 另含取數後逐筆被略過的理由。
    `fetched`：`{鍵: L1 取回的列數（過濾前）}`，只列真的取數的鍵；L1 回錯誤或回 None 時為 0。
    這是 `fetch_log.row_count`（`44`：「取回的列數」）的來源 —— 過濾後的 `rows` 數不是取回的列數
    （2026-09-26 set 頁回修第 2 輪新增；總管裁示必修 3）。
    `rows` 每一列逐欄照 `44` 的八欄、順序同契約。

    `sink`：Q12（`market_indicator` 與 `fetch_log` 落地到設定試算表）的**介面接縫**。
    本批不做落地；傳 None（預設）時什麼都不寫。傳入時以同一份回傳值呼叫一次，
    寫入端拋的例外照樣往上拋（不吞）。
    """
    rows, errors, pending, skipped, fetched = [], {}, {}, {}, {}
    for key, spec in INDICATOR_SPECS.items():
        if _phase1_of(spec) != "write":
            pending[key] = spec["pending_code"]
            skipped[key] = [spec["pending_reason"]]
            continue
        source, ticker = spec["source"]
        if source == "Yahoo":
            series, error = _call(fetch_yf_close_with_error, ticker)
            fetched[key] = 0 if (error or series is None) else len(series)
            key_rows, key_error, key_skipped = rows_from_daily_close(
                key, series, error, value_unit=spec["value_unit"])
        elif source == "FRED":
            if not (isinstance(fred_api_key, str) and fred_api_key.strip()):
                frame, error = None, MISSING_FRED_API_KEY
            else:
                observation_start = (_utc_today() - timedelta(days=FRED_LOOKBACK_DAYS)).isoformat()
                frame, error = _call(fetch_fred_vintages_with_error, ticker, fred_api_key,
                                     observation_start)
            fetched[key] = 0 if (error or frame is None) else len(frame)
            key_rows, key_error, key_skipped = rows_from_fred_vintages(
                key, frame, error, value_unit=spec["value_unit"])
        else:  # 新接一個來源卻沒寫轉換：當場炸（§1），不默默略過
            raise AssertionError(f"{key} 的來源 {source!r} 沒有對應的轉換函式")
        rows.extend(key_rows)
        if key_error is not None:
            errors[key] = key_error
        if key_skipped:
            skipped[key] = key_skipped

    names = [name for name, _k, _n in MARKET_INDICATOR_FIELDS]
    for row in rows:  # 出口前再核一次欄位與順序；不該發生，發生就是本檔的 bug（§1：當場炸）
        if list(row) != names:
            raise AssertionError(f"market_indicator 列的欄位與契約不符：{list(row)}")
    table = {"rows": rows, "errors": errors, "pending": pending, "skipped": skipped,
             "fetched": fetched}
    if sink is not None:
        sink(table)
    return table


def phase1_hosts() -> list:
    """第一階段真的會去取數的來源主機（退避鍵），供「重新取數」停用原因列出冷卻狀態。"""
    hosts = []
    for spec in INDICATOR_SPECS.values():
        if _phase1_of(spec) != "write":
            continue
        if spec["source"][0] == "Yahoo":
            hosts.append(host_of(f"{YF_CHART_BASE}/{spec['source'][1]}"))
        elif spec["source"][0] == "FRED":   # 2026-10-13 FRED 三鍵接上（同一個端點，見 fred_vintage）
            hosts.append(host_of(FRED_BASE))
    return list(dict.fromkeys(hosts))


def source_cooldowns() -> list:
    """第一階段來源之中仍在冷卻的，每筆 `{"source", "remaining_sec", ...}`，剩餘秒數由多到少。"""
    return cooling_sources(phase1_hosts())
