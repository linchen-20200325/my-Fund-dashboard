# -*- coding: utf-8 -*-
"""S2-T0 選股池 adapter：L2 `load_pool_codes` 的回傳形狀 → `PoolSourceView`（`DEC-2026-11-17-04`；僅內部唯讀切片）。

這個檔**不 import 任何 services／repositories／infra／shared／streamlit**：
- 取數函式（形如 L2 `exp_universe.load_pool_codes(secret_values)`）**必須由呼叫端明確注入**；
  本檔**不提供會觸發真實取數的預設**，也不讀環境變數、不碰 secrets 值、不發網路請求、不寫任何持久層。
- L2 的三個 status 字面（`ok`／`pool_not_cloud`／`failed`）與回傳鍵集合在本檔另存一份，由測試對照 L2 原始碼鎖死
  （adapters 層不得 import `shared`，也不需要為了常數去載入 L2）。
- 選股池代碼是**不透明字串**：原樣沿用 L2 回傳（L2 已去前後空白、去重；大小寫原樣），本檔只驗證它是非空白 `str`，
  不解析、不正規化、不當基金身份、不冒用 R-ID-1。

契約不符（缺鍵、型別不符、未知 status、status 與其他欄位矛盾）一律 **fail-closed**：raise `PoolContractError`，
訊息只含欄位名與型別名，不回顯收到的值（範圍：本檔 adapter 輸入驗證與 `PoolSourceView`；`Exp2Row`／`Exp7Row`／`conditions_count`
的計數驗證沿用 S0 `require_count`，拋 `ValueError`、僅涉及內部算出的整數，見 view model 模組 docstring）。
只有「取數函式本身拋例外」才轉成 `FAILED`（例外字串一律丟棄，只留例外型別名到 log）。

`pool_not_cloud` 一律映成 `UNAVAILABLE`，且本層不解析 L2 的訊息、不擅自確定原因。依 L1／L2 原始碼
（`pool_repository._sa_present`／`get_pool_store`、`exp_universe.load_pool_codes`）核對，`pool_not_cloud` 只代表「L1 選到本機 store」：
Service Account secret 缺失、缺 `client_email`、或為字串但 JSON 無法解析；或 `POOL_SHEET_ID` 缺／空白（且未注入使用者 OAuth client）。
⚠️ 它**不是**「所有憑證問題」：憑證可解析且含 `client_email` 但實際無效（金鑰錯、權限不足）時，L1 仍選 Google Sheets 後端，
`list_pool` 在讀取時拋例外 → L2 回 `failed` → 本層映成 `FAILED`。DEC 的「未設定／憑證無法使用」因此分散在 `UNAVAILABLE` 與 `FAILED` 兩態；
消費端不得把 `UNAVAILABLE` 讀成「憑證壞了」，也不得假設 `FAILED` 排除憑證成因。

執行組讀法（非已裁示，可被客戶推翻）：來源為 `FAILED`／`UNAVAILABLE`／`EMPTY` 時，下游 `build_exp_counts` 即使零條件也不回「尚未設定條件」、
不產生 N／M；`DEC-2026-11-17-03` G-6 僅適用離線 FAKE Preview。
"""
from __future__ import annotations

import logging
from typing import Callable, List, Tuple, Union

from ui_v3.viewmodels.exp_pool import (
    REASON_LOADER_RAISED,
    REASON_POOL_UNAVAILABLE,
    REASON_SOURCE_COOLING,
    REASON_SOURCE_FAILED,
    PoolContractError,
    PoolSourceView,
    PoolState,
)

__all__ = ("L2_STATUS_OK", "L2_STATUS_NOT_CLOUD", "L2_STATUS_FAILED", "L2_REQUIRED_KEYS", "PoolContractError",
           "adapt_pool_result", "load_pool_view")

# ＝ `services.v2_tables.exp_universe.STATUS_*`（測試對照 L2 原始碼鎖死）。
L2_STATUS_OK = "ok"
L2_STATUS_NOT_CLOUD = "pool_not_cloud"
L2_STATUS_FAILED = "failed"
_KNOWN_STATUSES = frozenset({L2_STATUS_OK, L2_STATUS_NOT_CLOUD, L2_STATUS_FAILED})

# ＝ L2 每一條回傳路徑都會帶的鍵（`_empty()` 與成功結果；測試對照 L2 原始碼鎖死）。
L2_REQUIRED_KEYS = ("status", "backend", "codes", "dropped_blank", "duplicates", "message", "read_at", "ttl_sec", "cooling")

_LOG = logging.getLogger(__name__)


def _need(ok: bool, field: str, expected: str, value: object) -> None:
    if not ok:
        raise PoolContractError(f"{field}: expected {expected}, got {type(value).__name__}") from None


def _non_negative_int(raw: dict, field: str) -> int:
    value = raw[field]
    _need(isinstance(value, int) and not isinstance(value, bool) and value >= 0, field, "non-negative int", value)
    return value


def adapt_pool_result(raw: object) -> PoolSourceView:
    """L2 回傳 dict → `PoolSourceView`（純函式；不呼叫任何外部東西）。契約不符一律 raise `PoolContractError`。"""
    _need(isinstance(raw, dict), "result", "dict", raw)
    missing = [key for key in L2_REQUIRED_KEYS if key not in raw]
    if missing:
        raise PoolContractError(f"result: missing keys {missing}") from None
    status = raw["status"]
    _need(isinstance(status, str), "status", "str", status)
    if status not in _KNOWN_STATUSES:
        raise PoolContractError("status: not one of the known values") from None

    _need(isinstance(raw["backend"], str), "backend", "str", raw["backend"])    # 只驗型別；絕不帶出
    _need(isinstance(raw["codes"], list), "codes", "list", raw["codes"])
    dropped_blank = _non_negative_int(raw, "dropped_blank")
    duplicates = _non_negative_int(raw, "duplicates")
    ttl = raw["ttl_sec"]
    _need(isinstance(ttl, (int, float)) and not isinstance(ttl, bool) and ttl > 0, "ttl_sec", "positive number", ttl)
    _need(isinstance(raw["cooling"], bool), "cooling", "bool", raw["cooling"])
    message, read_at, cooling = raw["message"], raw["read_at"], raw["cooling"]

    if status == L2_STATUS_OK:
        _need(message is None, "message", "None when status is ok", message)
        _need(not cooling, "cooling", "False when status is ok", cooling)
        _need(read_at is None or isinstance(read_at, str), "read_at", "str or None", read_at)
        codes = tuple(raw["codes"])
        for index, code in enumerate(codes):
            _need(isinstance(code, str) and code.strip() != "", f"codes[{index}]", "non-blank str", code)
        # 空 → EMPTY；非空 → OK。PoolSourceView 自己再驗一次（非空白、無重複、read_at 為 ISO）。
        return PoolSourceView(PoolState.OK if codes else PoolState.EMPTY, codes, None, read_at)

    # failed／pool_not_cloud：不可帶代碼、不可帶讀取時間、不可帶統計（L2 的 `_empty()` 恆為空與 0）；訊息必須是 str 但絕不帶出。
    _need(len(raw["codes"]) == 0, "codes", "empty list when status is not ok", raw["codes"])
    _need(read_at is None, "read_at", "None when status is not ok", read_at)
    _need(dropped_blank == 0 and duplicates == 0, "dropped_blank/duplicates", "0 when status is not ok", dropped_blank)
    _need(isinstance(message, str), "message", "str when status is not ok", message)
    if status == L2_STATUS_NOT_CLOUD:
        _need(not cooling, "cooling", "False when status is pool_not_cloud", cooling)
        return PoolSourceView(PoolState.UNAVAILABLE, (), REASON_POOL_UNAVAILABLE, None)
    return PoolSourceView(PoolState.FAILED, (), REASON_SOURCE_COOLING if cooling else REASON_SOURCE_FAILED, None)


def load_pool_view(loader: Callable[..., object], secret_values: Union[List[str], Tuple[str, ...]]) -> PoolSourceView:
    """呼叫**呼叫端注入**的取數函式（簽章對齊 L2 `load_pool_codes(secret_values)`）並適配成 `PoolSourceView`。

    - `loader` 沒有預設值：本檔不知道、也不 import 真實的 L1／L2。
    - `secret_values` 只轉交給 `loader`（供它遮蔽用）；本檔不讀取、不複製、不輸出其內容。
    - `loader` 拋出的任何 `Exception` → `FAILED`（`loader_raised`）：例外字串**不進 view**、不進 log（log 只記例外型別名）。
    - `loader` 回傳的形狀不符 → `adapt_pool_result` 的 `PoolContractError` **照樣往外拋**（不吞、不轉成 FAILED）。
    """
    _need(callable(loader), "loader", "callable", loader)
    _need(isinstance(secret_values, (list, tuple)) and all(isinstance(v, str) for v in secret_values),
          "secret_values", "list or tuple of str", secret_values)
    try:
        raw = loader(secret_values)
    except Exception as exc:  # noqa: BLE001 — 只轉成固定類別碼；例外字串可能含秘密，結構上不帶出
        _LOG.warning("exp pool loader raised %s", type(exc).__name__)
        return PoolSourceView(PoolState.FAILED, (), REASON_LOADER_RAISED, None)
    return adapt_pool_result(raw)
