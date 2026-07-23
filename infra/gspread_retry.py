"""infra/gspread_retry.py — Google Sheets (gspread) 429 / 配額退避共用工具 (v19.385 T2a)。

原本 `repositories/policy/_helpers.py` 與 `repositories/snapshot_repository.py` 各持一份
near-identical 的 `_is_quota_error` + `_with_quota_retry`(逐字重複),本檔抽 L0 infra 收斂。

⚠️ 退避排程(backoffs)保留為**參數**而非寫死常數 —— 兩處刻意不同節奏(§8.4 值不同不可強收):
  - policy 層  `(2, 4, 8, 16)` = 總 30s(v18.253:給 Google quota 視窗多一拍 reset)
  - snapshot 層 `(1, 2, 4, 8)`  = 總 15s
各 caller 傳自己的 backoffs;本檔只提供共用的偵測 + 重試迴圈。

L0 infra:無上行依賴,僅用 std `time`。
"""
from __future__ import annotations

import time
from typing import Any, Callable

# caller 未指定時的預設(對齊 snapshot 原節奏);policy 明確傳 (2,4,8,16)。
DEFAULT_QUOTA_BACKOFFS: tuple[float, ...] = (1.0, 2.0, 4.0, 8.0)


def is_quota_error(exc: BaseException) -> bool:
    """偵測 gspread 429 / RESOURCE_EXHAUSTED;不依賴 gspread.exceptions 細節以容版差。"""
    msg = str(exc)
    return ("429" in msg or "Quota exceeded" in msg or "RATE_LIMIT" in msg
            or "RESOURCE_EXHAUSTED" in msg)


def with_quota_retry(call: Callable, *args,
                     backoffs: tuple[float, ...] = DEFAULT_QUOTA_BACKOFFS,
                     **kwargs) -> Any:
    """包裝 gspread 呼叫:遇 429 依 `backoffs` 逐次退避重試;非配額錯誤立即拋。

    嘗試次數 = len(backoffs);最後一次仍 429 → 拋出原例外(§1 fail loud,不吞)。
    最後一個 backoff 值不會被 sleep(該次即 raise),與原兩份實作行為一致。
    """
    last_err: BaseException | None = None
    for attempt, delay in enumerate(backoffs):
        try:
            return call(*args, **kwargs)
        except Exception as e:  # noqa: BLE001 — gspread 例外類型隨版本變
            last_err = e
            is_last = attempt == len(backoffs) - 1
            if not is_quota_error(e) or is_last:
                raise
            time.sleep(delay)
    if last_err is not None:
        raise last_err
    return None
