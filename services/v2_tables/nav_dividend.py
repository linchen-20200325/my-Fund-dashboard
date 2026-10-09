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
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import pandas as pd

from repositories.fund.nav_metrics import LIVE_FETCH_ERROR_ATTR, fetch_div_with_error, fetch_nav_with_error
from services.v2_tables import contract
from services.v2_tables.market_indicator import EMPTY_WITHOUT_REASON


SOURCE_TIER_NAV = "淨值"           # `44` 值域四個之一
DIV_KIND_UNKNOWN = "unknown"       # Q5

# `49` §2.2：`fetch_div` 的 `date` 欄語意未查證（是不是除息日）。確認之前不取數、不寫列。
# ⚠️ 確認是除息日，才可以只改這一處；若其實是入帳日或公告日，要先改對照規則。
DIV_DATE_IS_EX_DATE_VERIFIED = False

# 退回預存舊序列的辨識（`49` §2.8）。
CACHE_FALLBACK_SOURCE_PREFIX = "GitHubActions:cache/nav/"

# ── 合理性門檻（第二輪回修 3；具名常數）──────────────────────────
# `nav_date`／`ex_date` 早於此日 → 不寫（L1 補年份或解析失準時常見的假日期，例：0001-09-18、1970-01-01）。
MIN_VALID_DATE = date(1900, 1, 1)
# 「未來日期」以台灣的日曆日判定：L1 以台灣日期建索引，台灣日期可能比世界協調時間的日期早一天進位。
# 晚於「當下的台灣日期」→ 不寫。
MARKET_DATE_TZ = timezone(timedelta(hours=8))
# `fetched_at`／`cache_updated_at` 晚於當下超過此秒數 → 不寫（取得時間不可能在未來）。
# 容差 300 秒（第三輪小修）：預存舊序列的 `cache_updated_at` 由另一台機器（GitHub Actions）寫入，
# 兩台機器的時鐘可能有偏差；L1 即時那一支的 `fetched_at` 也可能與本機時鐘有些微落差。
# 剛好晚 300 秒 → 收（邊界含在容差內）；晚 301 秒 → 拒收。nav 與 dividend 共用。
# ⚠️ 只放寬取得時間；`nav_date`／`ex_date` 的「晚於當下的台灣日期」判斷不受影響。
FETCHED_AT_MAX_FUTURE_SEC = 300

# 整檔不寫列的原因代碼（`withheld`）；L3 依代碼對照畫面文案（文案未定，屬草稿事項）。
WITHHELD_CCY_MISSING = "ccy_missing"                       # nav：來源沒自報、持倉也沒填
WITHHELD_CCY_CONFLICT = "ccy_conflict"                     # nav：來源自報與持倉手填（或手填之間）意思不同
WITHHELD_CCY_NOT_SOURCE_REPORTED = "ccy_not_source_reported"  # dividend：來源沒自報幣別
WITHHELD_FETCHED_AT_MISSING = "fetched_at_missing"         # 取不到真的取得時間（缺、格式不符、沒有時區）
WITHHELD_FETCHED_AT_FUTURE = "fetched_at_in_future"        # 取得時間晚於當下
WITHHELD_INPUT_CONFLICT = "input_conflict"                 # 同一檔基金給了互相矛盾的輸入
# 刻意不取數的原因代碼（`pending`，語意同 `market_indicator` 的 `pending`）。
PENDING_DIV_DATE_SEMANTICS = "div_date_semantics_unverified"

_PENDING_DIV_TEXT = (
    "fetch_div 的 date 欄是不是除息日尚未查證（49 §2.2）；確認之前不取數、不寫列"
    "（DIV_DATE_IS_EX_DATE_VERIFIED）"
)
# L1 回傳型別不對時寫進 `errors` 的前綴（第二輪回修 4）。
TYPE_ERROR_PREFIX = "L1 回傳型別不符"


# ───────────────────────── 小工具 ─────────────────────────

def _now_utc(now) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError(f"now 須為帶時區的 datetime（{now!r}）")
    return now.astimezone(timezone.utc)


def _parse_aware(value) -> Optional[datetime]:
    """時間字串 → 帶時區的 datetime；取不到、格式不符、沒有時區回 None。"""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def _utc_iso(value) -> Optional[str]:
    """時間字串 → 世界協調時間 ISO 字串（同一瞬間，一律 `+00:00` 形式）；取不到回 None。"""
    parsed = _parse_aware(value)
    if parsed is None:
        return None
    return parsed.astimezone(timezone.utc).isoformat()


def _fetched_at_check(value, now_utc: datetime):
    """回 `(utc_iso 或 None, withheld 代碼或 None, 理由或 None)`。"""
    parsed = _parse_aware(value)
    if parsed is None:
        return None, WITHHELD_FETCHED_AT_MISSING, "取不到、格式不符或沒有時區"
    if (parsed - now_utc).total_seconds() > FETCHED_AT_MAX_FUTURE_SEC:
        return None, WITHHELD_FETCHED_AT_FUTURE, f"晚於當下（{value!r}）"
    return parsed.astimezone(timezone.utc).isoformat(), None, None


def _iso_ccy(value) -> Optional[str]:
    """ISO 4217 三個大寫英文字母才收；其他（含小寫、空白、None）一律 None，不改寫、不猜。"""
    if isinstance(value, str) and len(value) == 3 and all("A" <= ch <= "Z" for ch in value):
        return value
    return None


def _ccy_meaning(value):
    """只用來**比對**意思是否相同（去空白、大寫化）；寫入一律用原值。非字串回 `("?", repr)`。"""
    if isinstance(value, str):
        text = value.strip().upper()
        return text or None
    return ("?", repr(value))


def _is_bool(value) -> bool:
    """bool 與 numpy bool 都不算數字（`float(True)` 會變成 1.0）。"""
    return pd.api.types.is_bool(value)


def _call(fetch, *args):
    """呼叫 L1 `*_with_error`；回 `(值, 錯誤)`。

    - L1 拋例外 → `(None, '型別名: 訊息')`，不吞。
    - L1 回的不是二元組 → `(None, TYPE_ERROR_PREFIX…)`：只讓這一檔進 errors，不讓整批中斷。
    """
    try:
        result = fetch(*args)
    except Exception as exc:  # noqa: BLE001 —— 轉成可見的失敗原文，不是吞掉
        return None, f"{type(exc).__name__}: {exc}"
    if not isinstance(result, tuple) or len(result) != 2:
        return None, f"{TYPE_ERROR_PREFIX}：預期 (值, 錯誤) 二元組，收到 {type(result).__name__}"
    return result


def _is_blank_ccy(value) -> bool:
    """持倉幣別「沒有填」：None、float nan、`pd.NA`、`pd.NaT` 這類缺值（第三輪小修 2）。
    不參與衝突判斷、不參與去重（NaN != NaN，放進清單會去重失敗）。字串一律不算缺值。"""
    if value is None:
        return True
    if isinstance(value, str):
        return False
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):   # 陣列等非純量：不是「沒填」，留給 resolve 判成衝突或缺
        return False


def _group_funds(funds):
    """輸入 → `{fund_code: {"full_key", "portal", "holding_ccys": list}}` 與 `{fund_code: 矛盾說明}`。

    同一檔基金掛在多張保單下是常態，取數只做一次；但 `full_key`／`portal` 不一致就不猜。
    `holding_ccys` 收集所有持倉列的手填幣別原值（含不合格式的值，交給 `resolve_nav_ccy` 判斷）。
    """
    grouped, conflicts = {}, {}
    for item in funds:
        code = item.get("fund_code")
        if not isinstance(code, str) or not code.strip() or code != code.strip():
            raise ValueError(f"fund_code 須為前後無空白的非空字串（{code!r}）")
        full_key = item.get("full_key")
        if not isinstance(full_key, str) or not full_key.strip():
            raise ValueError(f"{code}：full_key 須由呼叫端明確給出（{full_key!r}）；本檔不猜代碼對照")
        if full_key != full_key.strip():
            raise ValueError(f"{code}：full_key 前後帶空白（{full_key!r}）；本檔不偷偷去掉")
        portal = item.get("portal", "") or ""
        entry = grouped.setdefault(code, {"full_key": full_key, "portal": portal,
                                          "holding_ccys": []})
        if entry["full_key"] != full_key or entry["portal"] != portal:
            conflicts[code] = (f"同一檔基金給了不同的 full_key／portal："
                               f"({entry['full_key']!r}, {entry['portal']!r}) vs ({full_key!r}, {portal!r})")
        if "holding_ccy" in item and not _is_blank_ccy(item["holding_ccy"]):
            if item["holding_ccy"] not in entry["holding_ccys"]:
                entry["holding_ccys"].append(item["holding_ccy"])
    return grouped, conflicts


def _check_rows_order(rows, fields, table):
    names = [name for name, _k, _n in fields]
    for row in rows:  # 出口前再核一次欄位與順序；不該發生，發生就是本檔的 bug（§1：當場炸）
        if list(row) != names:
            raise AssertionError(f"{table} 列的欄位與契約不符：{list(row)}")


def _date_bounds_reason(day: date, today_market: date) -> Optional[str]:
    if day < MIN_VALID_DATE:
        return f"早於 {MIN_VALID_DATE.isoformat()}"
    if day > today_market:
        return f"晚於當下的台灣日期 {today_market.isoformat()}"
    return None


def _date_value(value):
    """日期值 → `(YYYY-MM-DD 或 None, 不收的理由或 None)`。

    只收三種（第二輪回修必修 1）：`pd.Timestamp`（無時區、非 NaT）、`datetime.date`（不含
    `datetime.datetime`，那一種日期語意要看時刻）、恰好 `YYYY-MM-DD` 的字串。
    整數、`RangeIndex`、"Sep 18"、"09/10/2026" 一律不收 —— 不交給 pandas 去猜。
    """
    if value is pd.NaT:
        return None, "日期是 NaT"
    if isinstance(value, pd.Timestamp):
        if value.tzinfo is not None:
            return None, "帶時區、日期語意不明"
        return value.date(), None
    if isinstance(value, datetime):
        return None, "是 datetime（不是 pd.Timestamp 或 date），日期語意不明"
    if isinstance(value, date):
        return value, None
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            return None, "字串不是 YYYY-MM-DD"
        if parsed.isoformat() != value:
            return None, "字串不是 YYYY-MM-DD"
        return parsed, None
    return None, f"型別不是日期（{type(value).__name__}）"


def _dated(value, today_market: date):
    """`_date_value` 再加上下限檢查 → `(YYYY-MM-DD 或 None, 理由或 None)`。"""
    day, why = _date_value(value)
    if day is None:
        return None, why
    why = _date_bounds_reason(day, today_market)
    if why:
        return None, why
    return day.isoformat(), None


def _tally(counter: dict, reason: str, n: int = 1) -> None:
    counter[reason] = counter.get(reason, 0) + n


def _tally_lines(counter: dict, what: str) -> list:
    return [f"{what}{reason} {n} 筆不寫" for reason, n in counter.items()]


# ───────────────────────── nav ─────────────────────────

def resolve_nav_ccy(source_ccy, holding_ccys):
    """`49` T3：`nav.ccy` 的取值。回 `(ccy, ccy_source, withheld_code, reason)`。

    - 合格（ISO 4217）的值寫入時一律用**原值**，不改寫。
    - 衝突判定（第二輪回修必修 2）：把來源自報與每一個持倉手填值**去空白、大寫化後**比意思；
      意思不只一種 → `ccy_conflict`（含「格式不對的值與合格的值意思不同」，例 `twd` vs `USD`、
      來源 `eur`／`EUR ` vs 持倉 `USD`）。非字串的值（例 840）意思無從比對，只要旁邊有別的值就當作衝突。
    - 意思相同時取合格的那一個（例 `usd` 與 `USD` 並存 → `USD`，出處記合格值那一方）。
    - 只有不合格式的值、沒有合格值 → `ccy_missing`（維持原判法：不改大小寫、不猜）。
    """
    # 缺值＝沒填（第三輪小修 2）。來源那一側的缺值必須在 append 之前先歸成 None（第四輪小修 1），
    # 否則 NaN 會帶著 ("?", 'nan') 的意思進衝突判斷。
    if _is_blank_ccy(source_ccy):
        source_ccy = None
    holding_ccys = [c for c in holding_ccys if not _is_blank_ccy(c)]
    provided = []
    if source_ccy is not None:
        provided.append(("source", source_ccy))
    provided.extend(("holding", c) for c in holding_ccys)
    meanings = {_ccy_meaning(v) for _side, v in provided} - {None}
    if len(meanings) > 1:
        shown = ", ".join(f"{side}:{v!r}" for side, v in provided)
        return None, None, WITHHELD_CCY_CONFLICT, f"幣別意思不一致（{shown}）"
    source = _iso_ccy(source_ccy)
    holding = next((c for c in holding_ccys if _iso_ccy(c)), None)
    if source:
        return source, "source_reported", None, None
    if holding:
        return holding, "holding_user_input", None, None
    detail = []
    if source_ccy is not None:
        detail.append(f"來源自報值不合 ISO 4217：{source_ccy!r}")
    bad = [repr(c) for c in holding_ccys if not _iso_ccy(c)]
    if bad:
        detail.append(f"持倉列幣別不合 ISO 4217：{', '.join(bad)}")
    reason = "來源未自報幣別、持倉列也沒有可用的幣別" + (f"（{'；'.join(detail)}）" if detail else "")
    return None, None, WITHHELD_CCY_MISSING, reason


def _empty_out():
    return {"rows": [], "error": None, "withheld": None, "skipped": [], "fetched": 0,
            "skipped_rows": 0, "provenance": None}


class ReconcileError(AssertionError):
    """核帳不平：本檔計數的 bug（不是資料問題）。"""


def _reconcile(out, skipped_rows: int, table: str):
    """核帳（第三輪小修 3）：寫出的列數＋略過與合併的筆數＝L1 取回的筆數。
    對不上就是本檔的計數 bug（§1：當場炸，不交出一份帳對不上的結果）。"""
    out["skipped_rows"] = skipped_rows
    if len(out["rows"]) + skipped_rows != out["fetched"]:
        raise ReconcileError(f"{table} 核帳不平：rows {len(out['rows'])} ＋ skipped {skipped_rows}"
                             f" ≠ fetched {out['fetched']}")
    return out


def rows_from_nav_series(fund_code: str, series, error, *, holding_ccys=(), now=None) -> dict:
    """單一檔基金的 L1 淨值序列 → `{rows, error, withheld, skipped, fetched, provenance}`（純函式）。

    `error` 非空：原文照回、不寫列。`series` 不是 `pd.Series`（含 None）：型別錯誤進 `error`。
    空序列又沒有原因：回 `EMPTY_WITHOUT_REASON`、不寫列。`now`：判「未來」用的當下（測試注入）。
    """
    out = _empty_out()
    if error:
        out["error"] = str(error)
        return out
    if not isinstance(series, pd.Series):
        out["error"] = f"{TYPE_ERROR_PREFIX}：預期 pd.Series，收到 {type(series).__name__}"
        return out
    if len(series) == 0:
        out["error"] = EMPTY_WITHOUT_REASON
        return out
    now_utc = _now_utc(now)
    today_market = now_utc.astimezone(MARKET_DATE_TZ).date()
    out["fetched"] = len(series)
    attrs = dict(series.attrs or {})
    source = attrs.get("source")
    fallback = (isinstance(source, str) and source.startswith(CACHE_FALLBACK_SOURCE_PREFIX)) \
        or "nav_quality" in attrs
    quality = attrs.get("nav_quality") if isinstance(attrs.get("nav_quality"), dict) else {}
    stale = quality.get("stale") if fallback else None
    at_field = "cache_updated_at" if fallback else "fetched_at"
    fetched_at, at_code, at_why = _fetched_at_check(attrs.get(at_field), now_utc)

    ccy, ccy_source, withheld, why = resolve_nav_ccy(attrs.get("currency"), holding_ccys)
    # `live_error`（2026-10-09 客戶裁示 M-1 採 A）：退回預存舊序列時，L1 交出的本次即時網址失敗原文
    # （未遮蔽）；不是預存那一支 → None。只供 set 頁淨值層重新取數判失敗用；hld 不讀它，列照常寫。
    live_error = attrs.get(LIVE_FETCH_ERROR_ATTR) if fallback else None
    out["provenance"] = {"source": source, "fetched_at": fetched_at, "ccy_source": ccy_source,
                         "cache_fallback": bool(fallback), "stale": stale,
                         "live_error": None if live_error is None else str(live_error)}
    if withheld:
        out["withheld"] = withheld
        out["skipped"].append(f"{why}，{len(series)} 筆全部不寫")
        return _reconcile(out, len(series), "nav")
    if fetched_at is None:
        out["withheld"] = at_code
        lead = "退回預存舊序列，但 cache_updated_at " if fallback else "L1 回傳的 fetched_at "
        out["skipped"].append(f"{lead}{at_why}，{len(series)} 筆全部不寫（不以當下時間補）")
        return _reconcile(out, len(series), "nav")

    date_bad: dict = {}
    by_day: dict = {}
    for stamp, value in series.items():
        day, why = _dated(stamp, today_market)
        if day is None:
            _tally(date_bad, why)
            continue
        by_day.setdefault(day, []).append(value)

    value_bad: dict = {}
    collateral = conflicting = not_positive = contract_bad = merged = 0
    for day in sorted(by_day):
        valid = []
        invalid = 0
        for value in by_day[day]:
            if _is_bool(value):
                _tally(value_bad, "是布林值（不算數字）")
                invalid += 1
                continue
            try:
                number = float(value)
            except OverflowError:
                _tally(value_bad, "數值溢位（超出浮點範圍）")
                invalid += 1
                continue
            except (TypeError, ValueError):
                _tally(value_bad, "無法轉成數字")
                invalid += 1
                continue
            if not math.isfinite(number):
                _tally(value_bad, "非有限數值")
                invalid += 1
                continue
            valid.append(number)
        if invalid:
            collateral += len(valid)      # 原規則：同一日有無效值，該日整天不寫
            continue
        if len(set(valid)) > 1:
            conflicting += len(valid)     # 同一主鍵兩個不同值：不猜哪個對，該日全部不寫
            continue
        number = valid[0]
        if number <= 0:
            not_positive += len(valid)
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
            contract_bad += len(valid)
            continue
        merged += len(valid) - 1          # 同日同值：主鍵只留一列
        out["rows"].append(row)

    out["skipped"].extend(_tally_lines(date_bad, "日期："))
    out["skipped"].extend(_tally_lines(value_bad, "淨值"))
    if collateral:
        out["skipped"].append(f"同一日期另有無效淨值，連帶 {collateral} 筆有效值不寫")
    if not_positive:
        out["skipped"].append(f"淨值不大於 0 {not_positive} 筆不寫")
    if conflicting:
        out["skipped"].append(f"同一日期出現不同淨值 {conflicting} 筆不寫")
    if contract_bad:
        out["skipped"].append(f"不符欄位契約 {contract_bad} 筆不寫")
    if merged:
        out["skipped"].append(f"同日同值合併 {merged} 筆")
    total = (sum(date_bad.values()) + sum(value_bad.values()) + collateral + not_positive
             + conflicting + contract_bad + merged)
    return _reconcile(out, total, "nav")


def _merge_one(code, one, acc):
    acc["rows"].extend(one["rows"])
    acc["fetched"][code] = one["fetched"]
    acc["skipped_rows"][code] = one["skipped_rows"]
    if one["error"] is not None:
        acc["errors"][code] = one["error"]
    if one["withheld"]:
        acc["withheld"][code] = one["withheld"]
    if one["skipped"]:
        acc["skipped"][code] = one["skipped"]
    if one["provenance"] is not None:
        acc["provenance"][code] = one["provenance"]


def build_nav_table(funds, *, now=None) -> dict:
    """組出 `nav` 表的列。`funds`：可迭代的 dict，每個帶 `fund_code`、`full_key`，選填 `portal`、
    `holding_ccy`（持倉列使用者手填的幣別；同一檔多列持倉可重複出現）。

    回傳 `{"rows", "errors", "withheld", "skipped", "fetched", "skipped_rows", "provenance"}`，皆以 `fund_code` 為鍵
    （`rows` 除外）：
    - `errors`：L1 失敗原文（未遮蔽）或型別錯誤；
    - `withheld`：整檔不寫列的原因代碼；`skipped`：不寫列的文字理由（整檔或逐列）；
    - `fetched`：L1 取回的筆數（過濾前）；L1 回錯誤或型別不對時為 0；
    - `skipped_rows`：略過與合併的筆數；有這兩個鍵的檔恆有 `len(該檔 rows) + skipped_rows == fetched`（核帳）；
    - ⚠️ **射程**：`fetched`／`skipped_rows` 只列**真的呼叫過 L1 的檔**（含取數失敗、型別錯誤，此時兩者為 0）。
      `withheld` 為 `input_conflict` 的檔**沒有呼叫 L1，也就沒有這兩個鍵** —— 不補 0（補 0 會讓它看起來像「取回 0 筆」）；
    - `provenance`：`{source, fetched_at, ccy_source, cache_fallback, stale, live_error}`（`live_error` 2026-10-09 加）。
    """
    grouped, conflicts = _group_funds(funds)
    acc = {"rows": [], "errors": {}, "withheld": {}, "skipped": {}, "fetched": {}, "skipped_rows": {},
           "provenance": {}}
    for code, entry in grouped.items():
        if code in conflicts:
            acc["withheld"][code] = WITHHELD_INPUT_CONFLICT
            acc["skipped"][code] = [conflicts[code] + "；不取數、不寫列"]
            continue
        series, error = _call(fetch_nav_with_error, entry["full_key"], entry["portal"])
        _merge_one(code, rows_from_nav_series(code, series, error,
                                              holding_ccys=entry["holding_ccys"], now=now), acc)
    _check_rows_order(acc["rows"], contract.NAV_FIELDS, "nav")
    return acc


# ───────────────────────── dividend ─────────────────────────

def rows_from_dividends(fund_code: str, items, error, *, now=None) -> dict:
    """單一檔基金的 L1 配息清單 → `{rows, error, withheld, skipped, fetched, provenance}`（純函式）。

    - `error` 非空：原文照回、不寫列。`items` 不是 list（含 None、字串）：型別錯誤進 `error`
      （不對字串逐字元計數）。
    - 空清單又沒有原因：**不是錯誤**。L1 原註：頁面取回且解析跑完、但沒有配息列 ——
      同時涵蓋「這檔不配息」與「頁面改版、解析不到」，本層分辨不出來，只如實記在 `skipped`。
    - 幣別只收每一筆自帶的 `currency`（來源自報、ISO 4217）；任何一筆沒有 → 那一筆不寫，
      整檔一筆都沒有 → `withheld = ccy_not_source_reported`。
    - `ex_date` 只收 `_date_value` 那三種，且不早於 `MIN_VALID_DATE`、不晚於當下的台灣日期。
    - `div_per_unit_orig_ccy` 不小於 0（0 照寫）；負數、布林、非有限值不寫。
    - 同一 `ex_date` 兩筆：金額相同只寫一列（主鍵），不同就該日全部不寫。
    - `fetched_at` 取每一筆自帶的值換成世界協調時間；取不到或晚於當下不寫（不以當下時間補）。
    """
    out = _empty_out()
    if error:
        out["error"] = str(error)
        return out
    if not isinstance(items, list):
        out["error"] = f"{TYPE_ERROR_PREFIX}：預期 list，收到 {type(items).__name__}"
        return out
    if not items:
        out["skipped"].append("來源頁面取回、但沒有任何配息列（無法分辨不配息或頁面改版，L1 原註）")
        return out
    now_utc = _now_utc(now)
    today_market = now_utc.astimezone(MARKET_DATE_TZ).date()
    out["fetched"] = len(items)
    sources = sorted({str(it.get("source")) for it in items if isinstance(it, dict) and it.get("source")})

    no_ccy = negative = conflicting = contract_bad = not_dict = merged = 0
    date_bad: dict = {}
    amount_bad: dict = {}
    time_bad: dict = {}
    time_codes = set()
    reached_time = 0
    candidates: dict = {}
    times = set()
    for item in items:
        if not isinstance(item, dict):
            not_dict += 1
            continue
        ccy = _iso_ccy(item.get("currency"))
        if ccy is None:
            no_ccy += 1
            continue
        day, why = _dated(item.get("date"), today_market)
        if day is None:
            _tally(date_bad, why)
            continue
        raw = item.get("amount")
        if _is_bool(raw):
            _tally(amount_bad, "是布林值（不算數字）")
            continue
        try:
            amount = float(raw)
        except OverflowError:
            _tally(amount_bad, "數值溢位（超出浮點範圍）")
            continue
        except (TypeError, ValueError):
            _tally(amount_bad, "無法轉成數字")
            continue
        if not math.isfinite(amount):
            _tally(amount_bad, "非有限數值")
            continue
        if amount < 0:
            negative += 1
            continue
        reached_time += 1
        fetched_at, code, why = _fetched_at_check(item.get("fetched_at"), now_utc)
        if fetched_at is None:
            _tally(time_bad, why)
            time_codes.add(code)
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
            contract_bad += len(entries)
            continue
        merged += len(entries) - 1        # 同日同額：主鍵只留一列
        out["rows"].append(row)

    out["provenance"] = {"source": sources[0] if len(sources) == 1 else (sources or None),
                         "fetched_at": sorted(times)[-1] if times else None,
                         "ccy_source": "source_reported" if out["rows"] else None}
    if not_dict:
        out["skipped"].append(f"不是 dict {not_dict} 筆不寫")
    if no_ccy and no_ccy == len(items) - not_dict:
        out["withheld"] = WITHHELD_CCY_NOT_SOURCE_REPORTED
        out["skipped"].append(f"來源未自報配息幣別（49 T3：不沿用持倉幣別），{no_ccy} 筆全部不寫")
        return _reconcile(out, not_dict + no_ccy, "dividend")
    if no_ccy:
        out["skipped"].append(f"來源未自報配息幣別 {no_ccy} 筆不寫")
    out["skipped"].extend(_tally_lines(date_bad, "日期："))
    out["skipped"].extend(_tally_lines(amount_bad, "配息金額"))
    if negative:
        out["skipped"].append(f"配息金額為負 {negative} 筆不寫")
    if time_bad:
        out["skipped"].extend(f"fetched_at {line}（不以當下時間補）" for line in _tally_lines(time_bad, ""))
        if not out["rows"] and sum(time_bad.values()) == reached_time and len(time_codes) == 1:
            out["withheld"] = next(iter(time_codes))
    if conflicting:
        out["skipped"].append(f"同一日期出現不同配息 {conflicting} 筆不寫")
    if contract_bad:
        out["skipped"].append(f"不符欄位契約 {contract_bad} 筆不寫")
    if merged:
        out["skipped"].append(f"同日同值合併 {merged} 筆")
    total = (not_dict + no_ccy + sum(date_bad.values()) + sum(amount_bad.values()) + negative
             + sum(time_bad.values()) + conflicting + contract_bad + merged)
    return _reconcile(out, total, "dividend")


def build_dividend_table(funds, *, now=None) -> dict:
    """組出 `dividend` 表的列。`funds` 同 `build_nav_table`（`holding_ccy` 在本表**不使用**，T3）。

    回傳 `{"rows", "errors", "pending", "withheld", "skipped", "fetched", "skipped_rows", "provenance"}`
    （`skipped_rows` 與核帳同 `build_nav_table`）。
    ⚠️ 射程：`fetched`／`skipped_rows` 只列真的呼叫過 L1 的檔；`input_conflict` 的檔與語意閘未開而列在
    `pending` 的檔**沒有呼叫 L1，也沒有這兩個鍵**，不補 0。
    `DIV_DATE_IS_EX_DATE_VERIFIED` 為假時：每一檔都列在 `pending`（代碼 `PENDING_DIV_DATE_SEMANTICS`）、
    **不呼叫 L1**、不寫列。
    """
    grouped, conflicts = _group_funds(funds)
    acc = {"rows": [], "errors": {}, "pending": {}, "withheld": {}, "skipped": {}, "fetched": {},
           "skipped_rows": {}, "provenance": {}}
    for code, entry in grouped.items():
        if code in conflicts:
            acc["withheld"][code] = WITHHELD_INPUT_CONFLICT
            acc["skipped"][code] = [conflicts[code] + "；不取數、不寫列"]
            continue
        if not DIV_DATE_IS_EX_DATE_VERIFIED:
            acc["pending"][code] = PENDING_DIV_DATE_SEMANTICS
            acc["skipped"][code] = [_PENDING_DIV_TEXT]
            continue
        items, error = _call(fetch_div_with_error, entry["full_key"], entry["portal"])
        _merge_one(code, rows_from_dividends(code, items, error, now=now), acc)
    _check_rows_order(acc["rows"], contract.DIVIDEND_FIELDS, "dividend")
    return acc
