# -*- coding: utf-8 -*-
"""持倉體檢（hld）要讀的 `nav`、`dividend` 兩張表：L1 `*_with_error` 回傳 → `44` 4.2／4.3 表列。

ui_v2 只經由 `ui_v2/<頁>/source.py` 碰到本檔（`49` §3.3 方案 A）。**本輪不接任何 UI。**

依據（逐條出處）：
- 客戶裁示 Q12＝A：資料不另外存，每次開頁即時抓。快取只在 L1（`fetch_nav`／`fetch_div` 掛
  `infra/cache.py::_daily_cache`，以台灣日曆日為界），本檔**不另疊快取**（`49` §4.4）、**不寫任何試算表**、
  **不讀 `services/nav_history_gs.py` 的累積序列**（那是「保留歷史」，另一輪處理）。
- `49` §2.6 / §6.2 T3（幣別）：
  - `nav.ccy`：收**來源自報**的幣別（L1 序列 `attrs["currency"]`），或**持倉列的使用者手填幣別**
    （呼叫端傳入 `holding_ccy`；該欄語意就是計價幣別）。**預設值、名稱推測值一律不收**；
    兩者都沒有 → 該檔淨值整批不寫；兩者都有但不同 → 不猜哪個對，整批不寫。
    ⚠️ `fetch_nav` 目前**從不**自報幣別，所以實務上 `nav.ccy` 只會來自持倉列。
  - `dividend.ccy`：**只收來源自報**，不沿用持倉列的幣別（配息幣別可能與計價幣別不同）。
    `fetch_div` 回傳的每一筆只有 `date`、`amount`、`source`、`fetched_at`，**沒有幣別** ⇒
    走 MoneyDJ 的基金配息一列都寫不進去（`49` §2.6；客戶 Q5 已知悉）。
- `49` §2.6 / Q5：`div_kind` 一律 `unknown`（來源沒有收益／本金區分）；`pay_date` 來源不給 → 空值。
- `49` §2.2：`fetch_div` 的 `date` **是不是除息日，`49` 沒有查頁面欄位語意**。本檔把它寫進 `ex_date`
  之前需要先確認 ⇒ `DIV_DATE_IS_EX_DATE_VERIFIED`（預設 False）。未確認前**不取數、不寫列**
  （體例同 `market_indicator.FX_OBS_DATE_RULE_VERIFIED`：取回來也寫不進去，只會多打來源）。
- `49` §2.8 / §4.3（舊資料不得冒充新資料）：`fetch_nav` 即時網址全敗、退回預存舊序列那一支
  （`attrs["source"]` 以 `GitHubActions:cache/nav/` 開頭，或 `attrs` 帶 `nav_quality`）：
  `fetched_at` **改取 `attrs["cache_updated_at"]`**（該支的 `attrs["fetched_at"]` 是讀檔當下，不是取得時間）；
  沒有 `cache_updated_at` 就整批不寫。過期與否看 `nav_quality["stale"]`（不看 `supports_annualized`），
  記在 `provenance`，**不寫進 `is_estimated`**（預存序列的值是真的公布淨值，不是推估值）。
- `CLAUDE.md` §1：週末、假日、停止交易日沒有列是正常狀態 —— 本檔**只轉 L1 給的日期**，
  不補列、不 ffill、不以 0 補；非有限值、非正淨值、負配息、同一主鍵兩個不同值 → 不寫該列並計數。

**provenance**：`44` 的 `nav`／`dividend` 兩表**沒有 `source` 欄**（`nav` 只有 `source_tier`）。
本檔不自創欄名；每一列照 `44` 帶 `fetched_at`，來源字串（L1 的 `attrs["source"]`／每筆的 `source`）、
幣別出處與舊序列旗標放在回傳的 `provenance[fund_code]`（每檔一次 L1 呼叫，同一檔的列共用同一個來源）。

**錯誤**：L1 失敗原文逐字放進 `errors[fund_code]`；L1 拋例外時放 `型別名: 訊息`（不吞）。
本層**不遮蔽**；遮蔽在寫出點做一次（同 `market_indicator`；`ui_v2/<頁>/source.py` 呼叫 `masking`）。

**基金代碼 → MoneyDJ `full_key`**：`49` §2.2 記載「Sheets 的 `fund_code` 能不能直接當 `full_key` 用，
本組沒有查」。本檔不猜：呼叫端**必須**明確給 `full_key`，本檔原樣交給 L1。
"""

from __future__ import annotations

import math
from datetime import date, datetime, timezone
from typing import Optional

import pandas as pd

from repositories.fund.nav_metrics import fetch_div_with_error, fetch_nav_with_error
from services.v2_tables import contract
from services.v2_tables.market_indicator import EMPTY_WITHOUT_REASON

SOURCE_TIER_NAV = "淨值"           # `44` 值域四個之一
DIV_KIND_UNKNOWN = "unknown"       # Q5

# `49` §2.2：`fetch_div` 的 `date` 欄語意未查證（是不是除息日）。確認之前不取數、不寫列。
# ⚠️ 確認是除息日，才可以只改這一處；若其實是入帳日或公告日，要先改對照規則。
DIV_DATE_IS_EX_DATE_VERIFIED = False

# 退回預存舊序列的辨識（`49` §2.8）。
CACHE_FALLBACK_SOURCE_PREFIX = "GitHubActions:cache/nav/"

# 整檔不寫列的原因代碼（`withheld`）；L3 依代碼對照畫面文案（文案未定，屬草稿事項）。
WITHHELD_CCY_MISSING = "ccy_missing"                       # nav：來源沒自報、持倉也沒填
WITHHELD_CCY_CONFLICT = "ccy_conflict"                     # nav：來源自報與持倉手填不同
WITHHELD_CCY_NOT_SOURCE_REPORTED = "ccy_not_source_reported"  # dividend：來源沒自報幣別
WITHHELD_FETCHED_AT_MISSING = "fetched_at_missing"         # 取不到真的取得時間
WITHHELD_INPUT_CONFLICT = "input_conflict"                 # 同一檔基金給了互相矛盾的輸入
# 刻意不取數的原因代碼（`pending`，語意同 `market_indicator` 的 `pending`）。
PENDING_DIV_DATE_SEMANTICS = "div_date_semantics_unverified"

_PENDING_DIV_TEXT = (
    "fetch_div 的 date 欄是不是除息日尚未查證（49 §2.2）；確認之前不取數、不寫列"
    "（DIV_DATE_IS_EX_DATE_VERIFIED）"
)


# ───────────────────────── 小工具 ─────────────────────────

def _utc_iso(value) -> Optional[str]:
    """時間字串 → 世界協調時間 ISO 字串（同一瞬間）；取不到、格式不符、沒有時區回 None。"""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    if parsed.utcoffset().total_seconds() == 0:
        return value
    return parsed.astimezone(timezone.utc).isoformat()


def _iso_ccy(value) -> Optional[str]:
    """ISO 4217 三個大寫英文字母才收；其他（含小寫、空白、None）一律 None，不改寫、不猜。"""
    if isinstance(value, str) and len(value) == 3 and all("A" <= ch <= "Z" for ch in value):
        return value
    return None


def _call(fetch, *args):
    """呼叫 L1 `*_with_error`；L1 拋例外時轉成 (None, '型別名: 訊息')，不吞。"""
    try:
        return fetch(*args)
    except Exception as exc:  # noqa: BLE001 —— 轉成可見的失敗原文，不是吞掉
        return None, f"{type(exc).__name__}: {exc}"


def _group_funds(funds):
    """輸入 → `{fund_code: {"full_key", "portal", "holding_ccys": set}}` 與 `{fund_code: 矛盾說明}`。

    同一檔基金掛在多張保單下是常態，取數只做一次；但 `full_key`／`portal` 不一致就不猜。
    `holding_ccys` 收集所有持倉列的手填幣別（含不合格式的原值，交給呼叫端判斷）。
    """
    grouped, conflicts = {}, {}
    for item in funds:
        code = item.get("fund_code")
        if not isinstance(code, str) or not code.strip() or code != code.strip():
            raise ValueError(f"fund_code 須為前後無空白的非空字串（{code!r}）")
        full_key = item.get("full_key")
        if not isinstance(full_key, str) or not full_key.strip():
            raise ValueError(f"{code}：full_key 須由呼叫端明確給出（{full_key!r}）；本檔不猜代碼對照")
        portal = item.get("portal", "") or ""
        entry = grouped.setdefault(code, {"full_key": full_key, "portal": portal,
                                          "holding_ccys": set()})
        if entry["full_key"] != full_key or entry["portal"] != portal:
            conflicts[code] = (f"同一檔基金給了不同的 full_key／portal："
                               f"({entry['full_key']!r}, {entry['portal']!r}) vs ({full_key!r}, {portal!r})")
        if "holding_ccy" in item and item["holding_ccy"] is not None:
            entry["holding_ccys"].add(item["holding_ccy"])
    return grouped, conflicts


def _check_rows_order(rows, fields, table):
    names = [name for name, _k, _n in fields]
    for row in rows:  # 出口前再核一次欄位與順序；不該發生，發生就是本檔的 bug（§1：當場炸）
        if list(row) != names:
            raise AssertionError(f"{table} 列的欄位與契約不符：{list(row)}")


# ───────────────────────── nav ─────────────────────────

def resolve_nav_ccy(source_ccy, holding_ccys):
    """`49` T3：`nav.ccy` 的取值。回 `(ccy, ccy_source, withheld_code, reason)`。

    - 來源自報（ISO 4217）與持倉手填（ISO 4217）都有且相同 → 該值，出處記「來源自報」。
    - 只有其中一個 → 該值與其出處。
    - 兩者不同、或持倉手填之間互相不同 → 不寫（`ccy_conflict`）。
    - 都沒有（含格式不合 ISO 4217 的值 —— 不改大小寫、不猜）→ 不寫（`ccy_missing`）。
    """
    holding_valid = {c for c in holding_ccys if _iso_ccy(c)}
    holding_bad = sorted(repr(c) for c in holding_ccys if not _iso_ccy(c))
    source = _iso_ccy(source_ccy)
    if len(holding_valid) > 1:
        return None, None, WITHHELD_CCY_CONFLICT, f"持倉列的幣別互相不同：{sorted(holding_valid)}"
    holding = next(iter(holding_valid), None)
    if source and holding and source != holding:
        return None, None, WITHHELD_CCY_CONFLICT, f"來源自報幣別 {source} 與持倉列幣別 {holding} 不同"
    if source:
        return source, "source_reported", None, None
    if holding:
        return holding, "holding_user_input", None, None
    detail = []
    if source_ccy is not None:
        detail.append(f"來源自報值不合 ISO 4217：{source_ccy!r}")
    if holding_bad:
        detail.append(f"持倉列幣別不合 ISO 4217：{', '.join(holding_bad)}")
    reason = "來源未自報幣別、持倉列也沒有可用的幣別" + (f"（{'；'.join(detail)}）" if detail else "")
    return None, None, WITHHELD_CCY_MISSING, reason


def _nav_date(stamp) -> Optional[str]:
    """序列索引 → `nav_date`。只收沒有時區的日期型索引（L1 以台灣日期字串建索引）；其餘 None。"""
    try:
        ts = pd.Timestamp(stamp)
    except (TypeError, ValueError):
        return None
    if ts is pd.NaT or ts.tzinfo is not None:
        return None
    return ts.date().isoformat()


def rows_from_nav_series(fund_code: str, series, error, *, holding_ccys=()) -> dict:
    """單一檔基金的 L1 淨值序列 → `{rows, error, withheld, skipped, fetched, provenance}`（純函式）。

    `error` 非空：原文照回、不寫列。空序列又沒有原因：回 `EMPTY_WITHOUT_REASON`、不寫列。
    """
    out = {"rows": [], "error": None, "withheld": None, "skipped": [], "fetched": 0,
           "provenance": None}
    if error:
        out["error"] = str(error)
        return out
    if series is None or len(series) == 0:
        out["error"] = EMPTY_WITHOUT_REASON
        return out
    out["fetched"] = len(series)
    attrs = dict(getattr(series, "attrs", {}) or {})
    source = attrs.get("source")
    fallback = (isinstance(source, str) and source.startswith(CACHE_FALLBACK_SOURCE_PREFIX)) \
        or "nav_quality" in attrs
    quality = attrs.get("nav_quality") if isinstance(attrs.get("nav_quality"), dict) else {}
    stale = quality.get("stale") if fallback else None
    if fallback:
        fetched_at = _utc_iso(attrs.get("cache_updated_at"))
        at_reason = "退回預存舊序列，但 cache_updated_at 取不到或沒有時區"
    else:
        fetched_at = _utc_iso(attrs.get("fetched_at"))
        at_reason = "L1 回傳的 fetched_at 取不到或沒有時區"

    ccy, ccy_source, withheld, why = resolve_nav_ccy(attrs.get("currency"), holding_ccys)
    out["provenance"] = {"source": source, "fetched_at": fetched_at, "ccy_source": ccy_source,
                         "cache_fallback": bool(fallback), "stale": stale}
    if withheld:
        out["withheld"] = withheld
        out["skipped"].append(f"{why}，{len(series)} 筆全部不寫")
        return out
    if fetched_at is None:
        out["withheld"] = WITHHELD_FETCHED_AT_MISSING
        out["skipped"].append(f"{at_reason}，{len(series)} 筆全部不寫（不以當下時間補）")
        return out

    candidates = []
    bad_date = 0
    for stamp, value in series.items():
        day = _nav_date(stamp)
        if day is None:
            bad_date += 1
            continue
        candidates.append((day, value))
    by_day: dict = {}
    for day, value in candidates:
        by_day.setdefault(day, []).append(value)

    not_finite = not_positive = conflicting = contract_bad = 0
    for day in sorted(by_day):
        values = by_day[day]
        numbers = []
        bad = False
        for value in values:
            try:
                number = float(value)
            except (TypeError, ValueError):
                bad = True
                break
            if not math.isfinite(number):
                bad = True
                break
            numbers.append(number)
        if bad:
            not_finite += len(values)
            continue
        if len(set(numbers)) > 1:
            conflicting += len(values)    # 同一主鍵兩個不同值：不猜哪個對，該日全部不寫
            continue
        number = numbers[0]
        if number <= 0:
            not_positive += 1
            continue
        row = {
            "fund_code": fund_code,
            "nav_date": day,
            "nav_orig_ccy": number,
            "ccy": ccy,
            "source_tier": SOURCE_TIER_NAV,
            "is_estimated": False,        # 來源給的是公布淨值；預存舊序列另記在 provenance
            "fetched_at": fetched_at,
        }
        if contract.nav_row_problems(row):
            contract_bad += 1
            continue
        out["rows"].append(row)

    if bad_date:
        out["skipped"].append(f"索引不是無時區的日期 {bad_date} 筆不寫")
    if not_finite:
        out["skipped"].append(f"淨值非有限數值 {not_finite} 筆不寫")
    if not_positive:
        out["skipped"].append(f"淨值不大於 0 {not_positive} 筆不寫")
    if conflicting:
        out["skipped"].append(f"同一日期出現不同淨值 {conflicting} 筆不寫")
    if contract_bad:
        out["skipped"].append(f"不符欄位契約 {contract_bad} 筆不寫")
    return out


def build_nav_table(funds) -> dict:
    """組出 `nav` 表的列。`funds`：可迭代的 dict，每個帶 `fund_code`、`full_key`，選填 `portal`、
    `holding_ccy`（持倉列使用者手填的幣別；同一檔多列持倉可重複出現）。

    回傳 `{"rows", "errors", "withheld", "skipped", "fetched", "provenance"}`，皆以 `fund_code` 為鍵
    （`rows` 除外）：
    - `errors`：L1 失敗原文（未遮蔽）；
    - `withheld`：整檔不寫列的原因代碼；`skipped`：不寫列的文字理由（整檔或逐列）；
    - `fetched`：L1 取回的筆數（過濾前）；L1 回錯誤或回 None 時為 0；
    - `provenance`：`{source, fetched_at, ccy_source, cache_fallback, stale}`。
    """
    grouped, conflicts = _group_funds(funds)
    rows, errors, withheld, skipped, fetched, provenance = [], {}, {}, {}, {}, {}
    for code, entry in grouped.items():
        if code in conflicts:
            withheld[code] = WITHHELD_INPUT_CONFLICT
            skipped[code] = [conflicts[code] + "；不取數、不寫列"]
            continue
        series, error = _call(fetch_nav_with_error, entry["full_key"], entry["portal"])
        one = rows_from_nav_series(code, series, error, holding_ccys=entry["holding_ccys"])
        rows.extend(one["rows"])
        fetched[code] = one["fetched"]
        if one["error"] is not None:
            errors[code] = one["error"]
        if one["withheld"]:
            withheld[code] = one["withheld"]
        if one["skipped"]:
            skipped[code] = one["skipped"]
        if one["provenance"] is not None:
            provenance[code] = one["provenance"]
    _check_rows_order(rows, contract.NAV_FIELDS, "nav")
    return {"rows": rows, "errors": errors, "withheld": withheld, "skipped": skipped,
            "fetched": fetched, "provenance": provenance}


# ───────────────────────── dividend ─────────────────────────

def _ex_date(value) -> Optional[str]:
    """只收整格恰好 `YYYY-MM-DD` 的真實日期字串（`fetch_div` 以 `str(Timestamp)[:10]` 產生）。"""
    if not isinstance(value, str):
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return value if parsed.isoformat() == value else None


def rows_from_dividends(fund_code: str, items, error) -> dict:
    """單一檔基金的 L1 配息清單 → `{rows, error, withheld, skipped, fetched, provenance}`（純函式）。

    - `error` 非空：原文照回、不寫列。
    - 空清單又沒有原因：**不是錯誤**。L1 原註：頁面取回且解析跑完、但沒有配息列 ——
      同時涵蓋「這檔不配息」與「頁面改版、解析不到」，本層分辨不出來，只如實記在 `skipped`。
    - 幣別只收每一筆自帶的 `currency`（來源自報、ISO 4217）；任何一筆沒有 → 那一筆不寫，
      整檔一筆都沒有 → `withheld = ccy_not_source_reported`。
    - `div_per_unit_orig_ccy` 不小於 0（0 照寫）；負數、非有限值不寫。
    - 同一 `ex_date` 兩筆：金額相同只寫一列（主鍵），不同就該日全部不寫。
    - `fetched_at` 取每一筆自帶的值換成世界協調時間；取不到不寫（不以當下時間補）。
    """
    out = {"rows": [], "error": None, "withheld": None, "skipped": [], "fetched": 0,
           "provenance": None}
    if error:
        out["error"] = str(error)
        return out
    if not items:
        out["skipped"].append("來源頁面取回、但沒有任何配息列（無法分辨不配息或頁面改版，L1 原註）")
        return out
    out["fetched"] = len(items)
    sources = sorted({str(it.get("source")) for it in items if isinstance(it, dict) and it.get("source")})

    no_ccy = bad_date = not_finite = negative = no_time = conflicting = contract_bad = 0
    reached_time = 0   # 走到 fetched_at 那一關的筆數
    candidates: dict = {}
    times = set()
    for item in items:
        if not isinstance(item, dict):
            contract_bad += 1
            continue
        ccy = _iso_ccy(item.get("currency"))
        if ccy is None:
            no_ccy += 1
            continue
        day = _ex_date(item.get("date"))
        if day is None:
            bad_date += 1
            continue
        try:
            amount = float(item.get("amount"))
        except (TypeError, ValueError):
            not_finite += 1
            continue
        if not math.isfinite(amount):
            not_finite += 1
            continue
        if amount < 0:
            negative += 1
            continue
        reached_time += 1
        fetched_at = _utc_iso(item.get("fetched_at"))
        if fetched_at is None:
            no_time += 1
            continue
        times.add(fetched_at)
        candidates.setdefault(day, []).append((amount, ccy, fetched_at))

    for day in sorted(candidates):
        entries = candidates[day]
        if len({(a, c) for a, c, _t in entries}) > 1:
            conflicting += len(entries)
            continue
        amount, ccy, fetched_at = entries[0]
        row = {
            "fund_code": fund_code,
            "ex_date": day,
            "pay_date": None,                   # 來源不給（49 §2.2）
            "div_per_unit_orig_ccy": amount,
            "ccy": ccy,
            "div_kind": DIV_KIND_UNKNOWN,       # Q5
            "fetched_at": fetched_at,
        }
        if contract.dividend_row_problems(row):
            contract_bad += 1
            continue
        out["rows"].append(row)

    out["provenance"] = {"source": sources[0] if len(sources) == 1 else (sources or None),
                         "fetched_at": sorted(times)[-1] if times else None,
                         "ccy_source": "source_reported" if out["rows"] else None}
    if no_ccy == len(items):
        out["withheld"] = WITHHELD_CCY_NOT_SOURCE_REPORTED
        out["skipped"].append(f"來源未自報配息幣別（49 T3：不沿用持倉幣別），{no_ccy} 筆全部不寫")
        return out
    if no_ccy:
        out["skipped"].append(f"來源未自報配息幣別 {no_ccy} 筆不寫")
    if bad_date:
        out["skipped"].append(f"日期不是 YYYY-MM-DD {bad_date} 筆不寫")
    if not_finite:
        out["skipped"].append(f"配息金額非有限數值 {not_finite} 筆不寫")
    if negative:
        out["skipped"].append(f"配息金額為負 {negative} 筆不寫")
    if no_time:
        out["skipped"].append(f"fetched_at 取不到或沒有時區 {no_time} 筆不寫（不以當下時間補）")
        if not out["rows"] and no_time == reached_time:
            out["withheld"] = WITHHELD_FETCHED_AT_MISSING
    if conflicting:
        out["skipped"].append(f"同一日期出現不同配息 {conflicting} 筆不寫")
    if contract_bad:
        out["skipped"].append(f"不符欄位契約 {contract_bad} 筆不寫")
    return out


def build_dividend_table(funds) -> dict:
    """組出 `dividend` 表的列。`funds` 同 `build_nav_table`（`holding_ccy` 在本表**不使用**，T3）。

    回傳 `{"rows", "errors", "pending", "withheld", "skipped", "fetched", "provenance"}`。
    `DIV_DATE_IS_EX_DATE_VERIFIED` 為假時：每一檔都列在 `pending`（代碼 `PENDING_DIV_DATE_SEMANTICS`）、
    **不呼叫 L1**、不寫列。
    """
    grouped, conflicts = _group_funds(funds)
    rows, errors, pending, withheld, skipped, fetched, provenance = [], {}, {}, {}, {}, {}, {}
    for code, entry in grouped.items():
        if code in conflicts:
            withheld[code] = WITHHELD_INPUT_CONFLICT
            skipped[code] = [conflicts[code] + "；不取數、不寫列"]
            continue
        if not DIV_DATE_IS_EX_DATE_VERIFIED:
            pending[code] = PENDING_DIV_DATE_SEMANTICS
            skipped[code] = [_PENDING_DIV_TEXT]
            continue
        items, error = _call(fetch_div_with_error, entry["full_key"], entry["portal"])
        one = rows_from_dividends(code, items, error)
        rows.extend(one["rows"])
        fetched[code] = one["fetched"]
        if one["error"] is not None:
            errors[code] = one["error"]
        if one["withheld"]:
            withheld[code] = one["withheld"]
        if one["skipped"]:
            skipped[code] = one["skipped"]
        if one["provenance"] is not None:
            provenance[code] = one["provenance"]
    _check_rows_order(rows, contract.DIVIDEND_FIELDS, "dividend")
    return {"rows": rows, "errors": errors, "pending": pending, "withheld": withheld,
            "skipped": skipped, "fetched": fetched, "provenance": provenance}
