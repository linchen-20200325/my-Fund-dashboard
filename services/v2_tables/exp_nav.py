# -*- coding: utf-8 -*-
"""標的探索（exp）正式模式的淨值與配息：`nav_dividend.build_nav_dividend_tables` 外面的逐檔短期記憶（L2；C2）。

⚠️ **這是 `docs/v2/49` §4.4「L2 不另疊快取」的有意偏離，不是漏看**（決策者：AI 總管；理由、TTL、撤銷條件
寫在 `49` 第 8 節 (t)）：

- **為什麼要有**：exp 頁每一次互動都會重跑；`build_nav_dividend_tables` 本身沒有任何快取，每一次都整條呼叫 A 鏈
  （`tests/test_v2_tables_exp_nav.py` 的計數測試實測：同一份輸入呼叫兩次 → A 鏈被呼叫兩次）。
  A 鏈 L1 `fund_orchestration.fetch_fund_from_moneydj_url` 雖有 15 分鐘快取，但**只收「每一個元件都成功」的結果**
  （`_moneydj_url_result_cacheable`：還要 wb07、wb01、持股、配息都成功、序列夠長、不是短窗）——
  淨值有了、持股沒抓到的那一檔，B 線拿得到可用的淨值，L1 卻不快取，下一次互動整條重打；
  **失敗的結果 L1 一律不快取**（計數測試同樣實測）。所以成功與失敗兩種記憶都做。
- **成功**：記 `SUCCESS_TTL_SEC`（＝`TTL_15MIN`，不長於 L1 自己的成功 TTL，不會讓 L2 比 L1 更舊）。
- **失敗**：記 `FAILURE_TTL_SEC`（＝`TTL_5MIN`，同 `declared_profile.FAILURE_MEMORY_SEC`），期間內不重打，
  回上一次的失敗原文，`memo[代碼]["cooling"]` 為真並附剩餘秒數。
  「失敗」＝ 該檔的 `nav.errors` 或 `dividend.errors` 有原文（A 鏈沒取到、例外、型別不符、full_key 不符）；
  淨值取到了但被幣別閘扣下（withheld）不算失敗（資料是確定的，重打也一樣）。
- **鍵**：`(fund_code, full_key, chain_code, declared_ccy, declared_ccy_source, portal, 台灣日期)` —— 任一不同就不命中；
  台灣日期以 `now` 換成 UTC+8 取日（跨日即失效，同 L1 `_daily_cache` 的日界）。`portal` 是本組多加的一格（從嚴）。
- **`fetched_at`**：沿用 L2 輸出（命中時交回的是當初那一份，不改成當下）。
- **清除**：`clear_memo()`；以 `register_cache` 登記名稱 `exp_nav_memo`；set 頁 `refetch_nav` 會呼叫。
- **只收 meta 模式**（`declared_ccy`＋`declared_ccy_source`）：持倉手填（`holding_ccy`）不在鍵裡，收了會錯配 → ValueError。
- **撤銷條件**：A 鏈 L1 改成「B 線可用的結果都快取、失敗另有記憶」時，本檔即可拿掉，改直接呼叫 `build_nav_dividend_tables`。

已知限制（照實寫）：沒有 single-flight（同一檔被並行查詢時各自出門）；`chain_fetch` 不在鍵裡（測試注入用，
正式路徑恆為 None —— 同一行程內換注入物而不 `clear_memo()` 會命中舊結果）。
"""

from __future__ import annotations

import copy
import threading
import time

from infra.cache import register_cache
from services.v2_tables import nav_dividend
from shared.ttls import TTL_5MIN, TTL_15MIN

SUCCESS_TTL_SEC = TTL_15MIN
FAILURE_TTL_SEC = TTL_5MIN

KIND_SUCCESS = "success"
KIND_FAILURE = "failure"

_NAV_KEYS = ("errors", "withheld", "skipped", "fetched", "skipped_rows", "provenance")
_DIV_KEYS = (*_NAV_KEYS, "pending", "settled")

_LOCK = threading.Lock()
_MEMO: dict = {}           # 鍵 → (存入時刻 monotonic, KIND_*, {"nav": 片段, "dividend": 片段})
#: 與 `infra.source_backoff._clock` 同一種時鐘（monotonic）；模組層變數讓測試能注入假時鐘。
_clock = time.monotonic


class _NavMemoCache:
    """給 `infra.cache` 的登記物件：`clear_all_caches()` 會呼叫 `cache_clear()`。"""

    __name__ = "exp_nav_memo"

    def cache_clear(self) -> None:
        with _LOCK:
            _MEMO.clear()

    def cache_info(self) -> dict:
        with _LOCK:
            return {"name": self.__name__, "size": len(_MEMO),
                    "ttl_sec": SUCCESS_TTL_SEC, "failure_ttl_sec": FAILURE_TTL_SEC}


_REGISTERED = register_cache(_NavMemoCache())


def clear_memo() -> None:
    _REGISTERED.cache_clear()


def _ttl(kind: str) -> int:
    return SUCCESS_TTL_SEC if kind == KIND_SUCCESS else FAILURE_TTL_SEC


def _expired(tick: float, at: float, kind: str) -> bool:
    """存入後經過的秒數 ≥ TTL 即過期（成功 900 秒時第 899 秒命中、第 900 秒不命中）。清理與查詢共用這一個判準。"""
    return tick - at >= _ttl(kind)


def _empty_tables() -> dict:
    return {"nav": {"rows": [], **{k: {} for k in _NAV_KEYS}},
            "dividend": {"rows": [], **{k: {} for k in _DIV_KEYS}}}


def _piece(tables: dict, code: str) -> dict:
    """單檔呼叫的結果 → 只含這一檔的片段（同表形狀）。"""
    out = {}
    for name, keys in (("nav", _NAV_KEYS), ("dividend", _DIV_KEYS)):
        src = tables[name]
        out[name] = {"rows": list(src["rows"]), **{k: ({code: src[k][code]} if code in src[k] else {}) for k in keys}}
    return out


def _merge(acc: dict, piece: dict) -> None:
    for name, keys in (("nav", _NAV_KEYS), ("dividend", _DIV_KEYS)):
        acc[name]["rows"].extend(piece[name]["rows"])
        for k in keys:
            acc[name][k].update(piece[name][k])


def _check_items(funds) -> list:
    items = list(funds)
    for item in items:
        if not isinstance(item, dict):
            raise TypeError(f"funds 的每一筆須為 dict（收到 {type(item).__name__}）")
        if "holding_ccy" in item:
            raise ValueError(f"{item.get('fund_code')!r}：exp 淨值只收 meta 模式（declared_ccy＋declared_ccy_source）；"
                             "持倉手填（holding_ccy）不在記憶的鍵裡，收了會錯配")
        if "declared_ccy" not in item and "declared_ccy_source" not in item:
            raise ValueError(f"{item.get('fund_code')!r}：每一筆都要明確帶 declared_ccy 與 declared_ccy_source"
                             "（沒有幣別請給 declared_ccy=None）")
    return items


def load_nav_dividend(funds, *, now=None, clock=None, chain_fetch=None) -> dict:
    """exp 用：逐檔記憶的 `build_nav_dividend_tables`。

    `funds`：同 `build_nav_dividend_tables`（每筆帶 `fund_code`、`full_key`、`chain_code`、`portal`、
    `declared_ccy`、`declared_ccy_source`）。輸入檢查完全交給 `nav_dividend`（同一套 `ValueError`），
    另加：不收 `holding_ccy`、每筆都要帶 declared 鍵（見檔頭）。
    `now`：帶時區的 datetime（決定台灣日期，並原樣交給 `build_nav_dividend_tables`）；None ＝ 當下。
    `clock`：monotonic 時鐘（可呼叫物，測試注入）；None ＝ 模組層 `_clock`。
    `chain_fetch`：原樣交給 `build_nav_dividend_tables`（測試注入）。

    回傳 `{"nav": ..., "dividend": ..., "memo": {代碼: {"hit", "cooling", "cooling_remaining_sec"}}}`；
    `nav`／`dividend` 形狀與 `build_nav_dividend_tables` 相同（列依代碼第一次出現的順序串接）。
    `memo[代碼]["hit"]`：本次是否取自記憶；`cooling`：命中的是失敗記憶（本次未重打）。
    """
    items = _check_items(funds)
    now_utc = nav_dividend._now_utc(now)
    tw_date = now_utc.astimezone(nav_dividend.MARKET_DATE_TZ).date().isoformat()
    tick = (clock or _clock)()
    grouped, conflicts = nav_dividend._group_funds(items, chain=True)   # 同一套輸入檢查（不合格當場 ValueError）
    acc = _empty_tables()
    memo_info = {}
    with _LOCK:
        for k in [k for k, (at, kind, _p) in _MEMO.items() if _expired(tick, at, kind)]:
            del _MEMO[k]
    for code, entry in grouped.items():
        own = [item for item in items if item.get("fund_code") == code]
        key = None
        if code not in conflicts:
            key = (code, entry["full_key"], entry["chain_code"], tuple(entry["holding_ccys"]),
                   entry["label_source"], entry["portal"], tw_date)
            try:
                hash(key)
            except TypeError:          # declared_ccy 是不可雜湊的怪值：不記憶，照常交給 nav_dividend 判
                key = None
        hit = None
        if key is not None:
            with _LOCK:
                hit = _MEMO.get(key)
            if hit is not None and _expired(tick, hit[0], hit[1]):
                hit = None
        if hit is not None:
            at, kind, piece = hit
            cooling = kind == KIND_FAILURE
            memo_info[code] = {"hit": True, "cooling": cooling,
                               "cooling_remaining_sec": round(_ttl(kind) - (tick - at), 1) if cooling else None}
            _merge(acc, copy.deepcopy(piece))
            continue
        tables = nav_dividend.build_nav_dividend_tables(own, now=now_utc, chain_fetch=chain_fetch)
        piece = _piece(tables, code)
        if key is not None:
            failed = code in piece["nav"]["errors"] or code in piece["dividend"]["errors"]
            with _LOCK:
                _MEMO[key] = (tick, KIND_FAILURE if failed else KIND_SUCCESS, copy.deepcopy(piece))
        memo_info[code] = {"hit": False, "cooling": False, "cooling_remaining_sec": None}
        _merge(acc, piece)
    return {"nav": acc["nav"], "dividend": acc["dividend"], "memo": memo_info}
