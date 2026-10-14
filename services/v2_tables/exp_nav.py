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
- **成功**：記 `SUCCESS_TTL_SEC`（＝`TTL_15MIN`~~，不長於 L1 自己的成功 TTL，不會讓 L2 比 L1 更舊~~）。
  → 2026-10-14 稽核 V／W 必修 4（有意識的更正，不是漏刪；決策者：AI 總管）：刪掉的那半句**不成立** ——
  本層的時鐘從「存入本層」起算，存入時拿到的可能已是 L1 快取裡放了將近 `TTL_15MIN` 的結果，
  所以**最壞情形是實際取數後約 L1 TTL ＋ L2 TTL（約 30 分鐘）**才重打。畫面不會因此把舊資料說成新的：
  每一列的 `fetched_at` 是當初實際取得的時間，命中時原樣交回。
- **失敗**：記 `FAILURE_TTL_SEC`（＝`TTL_5MIN`，同 `declared_profile.FAILURE_MEMORY_SEC`），期間內不重打，
  回上一次的失敗原文，`memo[代碼]["cooling"]` 為真並附剩餘秒數。
  「失敗」＝ 該檔的 `nav.errors` 或 `dividend.errors` 有原文（A 鏈沒取到、例外、型別不符、full_key 不符）；
  淨值取到了但被幣別閘扣下（withheld）不算失敗（資料是確定的，重打也一樣）。
- **鍵**：`(fund_code, full_key, chain_code, declared_ccy, declared_ccy_source, portal, 台灣日期)` —— 任一不同就不命中；
  台灣日期以 `now` 換成 UTC+8 取日（跨日即失效，同 L1 `_daily_cache` 的日界）。`portal` 是本組多加的一格（從嚴）。
- **`fetched_at`**：沿用 L2 輸出（命中時交回的是當初那一份，不改成當下）。
- **清除**：`clear_memo()`；以 `register_cache` 登記名稱 `exp_nav_memo`；set 頁 `refetch_nav` 會呼叫。
- **只收 meta 模式**（`declared_ccy`＋`declared_ccy_source`）：持倉手填（`holding_ccy`）不在鍵裡，收了會錯配 → ValueError。
- **計價幣別未確定（`declared_ccy_source` 為 None）逐檔隔離**（2026-10-14 稽核必修 3）：該檔不取數、不記憶，
  `nav`／`dividend` 的 `withheld` 記 `WITHHELD_CCY_UNDETERMINED`、`skipped` 與回傳的 `not_fetched` 寫明原因；
  其他檔照常。其餘不合格的 `declared_ccy_source`（壞字串）照舊由 `nav_dividend` 整批 ValueError（那是程式錯誤）。
- **與當下時刻（不是日期）有關的扣下不記憶**（2026-10-14 稽核必修 2）：`nav_dividend` 裡唯一一種依時刻判定的扣下是
  `_fetched_at_check` 的「取得時間晚於當下超過 `FETCHED_AT_MAX_FUTURE_SEC`」（淨值整段、累積表各段、配息逐筆都走它）；
  過幾分鐘再判可能就過了，記住它會把當下的判斷重播成舊的。只要該檔的結果裡出現這一種扣下，本次就**不存**。
  依日期判定的（「晚於當下的台灣日期」）不受影響：鍵裡已有台灣日期，同一天內判斷不變。
- **清除與進行中讀取**（2026-10-14 稽核必修 5）：`clear_memo()` 會把世代計數加一；清除前就開始取數、清除後才完成的
  那一筆**不寫回**記憶（否則「重新取數」之後還會讀到清除前那一輪的結果）。
- **撤銷條件**：A 鏈 L1 改成「B 線可用的結果都快取、失敗另有記憶」時，本檔即可拿掉，改直接呼叫 `build_nav_dividend_tables`。

已知限制（照實寫）：沒有 single-flight（同一檔被並行查詢時各自出門）；記憶沒有容量上限，筆數受代碼總數與
存活時間限制（每次呼叫先清掉過期的）；`chain_fetch` 不在鍵裡（測試注入用，
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

#: 計價幣別未確定的檔（`declared_ccy_source` 為 None）：不取數、不寫列（2026-10-14 稽核必修 3）。
WITHHELD_CCY_UNDETERMINED = "ccy_undetermined"
TEXT_CCY_UNDETERMINED = "計價幣別未確定（declared_ccy_source 為 None），本檔不取數、不寫列"
#: `nav_dividend._fetched_at_check`「晚於當下」那一種扣下的理由開頭（逐筆、整段都用它）；有守衛測試釘住。
TIME_DEPENDENT_REASON_MARK = "晚於當下（"

_LOCK = threading.Lock()
_MEMO: dict = {}           # 鍵 → (存入時刻 monotonic, KIND_*, {"nav": 片段, "dividend": 片段})
_GEN = [0]                 # 世代計數：clear 一次加一；開始取數時的世代與寫回時不同 → 不寫回
#: 與 `infra.source_backoff._clock` 同一種時鐘（monotonic）；模組層變數讓測試能注入假時鐘。
_clock = time.monotonic


class _NavMemoCache:
    """給 `infra.cache` 的登記物件：`clear_all_caches()` 會呼叫 `cache_clear()`。"""

    __name__ = "exp_nav_memo"

    def cache_clear(self) -> None:
        with _LOCK:
            _MEMO.clear()
            _GEN[0] += 1

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


def _time_dependent(piece: dict, code: str) -> bool:
    """該檔的結果裡有沒有「取得時間晚於當下」這一種依時刻判定的扣下（整段 withheld 或逐筆 skipped）。"""
    for name in ("nav", "dividend"):
        part = piece[name]
        if part["withheld"].get(code) == nav_dividend.WITHHELD_FETCHED_AT_FUTURE:
            return True
        if any(TIME_DEPENDENT_REASON_MARK in str(line) for line in part["skipped"].get(code) or ()):
            return True
    return False


def _undetermined_piece(code: str) -> dict:
    piece = _empty_tables()
    for name in ("nav", "dividend"):
        piece[name]["withheld"][code] = WITHHELD_CCY_UNDETERMINED
        piece[name]["skipped"][code] = [TEXT_CCY_UNDETERMINED]
    piece["dividend"]["settled"][code] = False
    return piece


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
        code = item.get("fund_code")
        if not isinstance(code, str) or not code.strip() or code != code.strip():
            raise ValueError(f"fund_code 須為前後無空白的非空字串（{code!r}）")
    return items


def load_nav_dividend(funds, *, now=None, clock=None, chain_fetch=None) -> dict:
    """exp 用：逐檔記憶的 `build_nav_dividend_tables`。

    `funds`：同 `build_nav_dividend_tables`（每筆帶 `fund_code`、`full_key`、`chain_code`、`portal`、
    `declared_ccy`、`declared_ccy_source`）。輸入檢查完全交給 `nav_dividend`（同一套 `ValueError`），
    另加：不收 `holding_ccy`、每筆都要帶 declared 鍵（見檔頭）。
    `now`：帶時區的 datetime（決定台灣日期，並原樣交給 `build_nav_dividend_tables`）；None ＝ 當下。
    `clock`：monotonic 時鐘（可呼叫物，測試注入）；None ＝ 模組層 `_clock`。
    `chain_fetch`：原樣交給 `build_nav_dividend_tables`（測試注入）。

    回傳 `{"nav": ..., "dividend": ..., "memo": {代碼: {"hit", "cooling", "cooling_remaining_sec"}},
    "not_fetched": {代碼: 原因}}`（`not_fetched`：計價幣別未確定、本次沒有取數的檔）；
    `nav`／`dividend` 形狀與 `build_nav_dividend_tables` 相同（列依代碼第一次出現的順序串接）。
    `memo[代碼]["hit"]`：本次是否取自記憶；`cooling`：命中的是失敗記憶（本次未重打）。
    """
    items = _check_items(funds)
    now_utc = nav_dividend._now_utc(now)
    tw_date = now_utc.astimezone(nav_dividend.MARKET_DATE_TZ).date().isoformat()
    tick = (clock or _clock)()
    undetermined = {item["fund_code"] for item in items if item.get("declared_ccy_source") is None}
    fetchable = [item for item in items if item["fund_code"] not in undetermined]
    grouped, conflicts = nav_dividend._group_funds(fetchable, chain=True)   # 同一套輸入檢查（不合格當場 ValueError）
    acc = _empty_tables()
    memo_info, not_fetched = {}, {}
    with _LOCK:
        for k in [k for k, (at, kind, _p) in _MEMO.items() if _expired(tick, at, kind)]:
            del _MEMO[k]
    for code in dict.fromkeys(item["fund_code"] for item in items):   # 代碼第一次出現的順序
        if code in undetermined:
            not_fetched[code] = TEXT_CCY_UNDETERMINED
            memo_info[code] = {"hit": False, "cooling": False, "cooling_remaining_sec": None}
            _merge(acc, _undetermined_piece(code))
            continue
        entry = grouped[code]
        own = [item for item in fetchable if item["fund_code"] == code]
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
        with _LOCK:
            gen = _GEN[0]
        tables = nav_dividend.build_nav_dividend_tables(own, now=now_utc, chain_fetch=chain_fetch)
        piece = _piece(tables, code)
        if key is not None and not _time_dependent(piece, code):
            failed = code in piece["nav"]["errors"] or code in piece["dividend"]["errors"]
            with _LOCK:
                if _GEN[0] == gen:     # 取數期間被清過 → 不寫回（清除前那一輪的結果不得留到清除後）
                    _MEMO[key] = (tick, KIND_FAILURE if failed else KIND_SUCCESS, copy.deepcopy(piece))
        memo_info[code] = {"hit": False, "cooling": False, "cooling_remaining_sec": None}
        _merge(acc, piece)
    return {"nav": acc["nav"], "dividend": acc["dividend"], "memo": memo_info, "not_fetched": not_fetched}
