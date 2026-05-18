"""
repositories/snapshot_repository.py — T7 帳本 quick-restore snapshot
（v11.0 從 ledger_snapshot_store.py 搬入）

設計原則：
- 與 repositories/ledger_repository.py 互補：_Ledgers 是 audit trail（逐筆交易），
  _T7_State 是 quick-restore snapshot（每檔基金一列，完整 Ledger.to_dict()）
- 純資料層：不 import streamlit
- 共用 PolicySheetError，呼叫端只接這個例外
- 一檔基金一列：(pk_str, fund_code, currency, policy_id, ledger_json, updated_at)
  ledger_json 是 fund_ledger.Ledger.to_dict() 的 JSON 字串

T7 入口會自動 load 還原；A/B/C/初始持倉落帳完成後 dump 全表覆寫。

v11.0 分層歸位：本檔屬於 Repository Layer，Google Sheets snapshot 持久化 I/O。
向後相容：根目錄 ledger_snapshot_store.py 保留 `from repositories.snapshot_repository import *`
        shim，E 階段收尾後 shim 刪除。
"""
from __future__ import annotations

from typing import Any, Callable
import datetime as _dt
import json as _json
import time as _time

import pandas as pd

from repositories.policy_repository import PolicySheetError


T7_STATE_TAB = "_T7_State"

SNAPSHOT_COLS: tuple[str, ...] = (
    "pk_str",
    "fund_code",
    "currency",
    "policy_id",
    "ledger_json",
    "updated_at",
)

# v18.73: Sheets 429 指數退避 — Google Sheets API per-user 60 reads/min，
# delete_rows/append_row 迴圈很容易爆。逐次重試 1s/2s/4s/8s 共 4 次。
_QUOTA_BACKOFFS: tuple[float, ...] = (1.0, 2.0, 4.0, 8.0)


def _is_quota_error(exc: BaseException) -> bool:
    """偵測 gspread 429 / RESOURCE_EXHAUSTED。不依賴 gspread.exceptions 細節以容版差。"""
    msg = str(exc)
    return ("429" in msg or "Quota exceeded" in msg or "RATE_LIMIT" in msg
            or "RESOURCE_EXHAUSTED" in msg)


def _with_quota_retry(call: Callable, *args, **kwargs):
    """包裝 gspread 呼叫：遇 429 退避重試；非配額錯誤立即拋。"""
    last_err: BaseException | None = None
    for attempt, delay in enumerate(_QUOTA_BACKOFFS):
        try:
            return call(*args, **kwargs)
        except Exception as e:  # noqa: BLE001 — gspread 例外類型隨版本變
            last_err = e
            is_last = attempt == len(_QUOTA_BACKOFFS) - 1
            if not _is_quota_error(e) or is_last:
                raise
            _time.sleep(delay)
    # unreachable — 最後一次失敗已 raise
    if last_err is not None:
        raise last_err
    return None


# ──────────────────────────────────────────────────────────────────────
# Worksheet 管理
# ──────────────────────────────────────────────────────────────────────
def ensure_state_worksheet(client: Any, sheet_id: str, rows: int = 200) -> Any:
    """確保 _T7_State tab 存在；不存在則建立並寫表頭。"""
    if not sheet_id:
        raise PolicySheetError("開啟 Sheet 失敗：sheet_id 為空（請先在「📋 保單管理」設定或自動建立）")
    try:
        sh = _with_quota_retry(client.open_by_key, sheet_id)
    except Exception as e:
        # v18.41 強化錯誤訊息：gspread 例外 str(e) 常空白，補上型別與 ID 前綴
        _hint = f"[{type(e).__name__}] {e}" if str(e) else type(e).__name__
        _sid_hint = sheet_id[:12] + ("…" if len(sheet_id) > 12 else "")
        raise PolicySheetError(
            f"開啟 Sheet 失敗（ID `{_sid_hint}`）：{_hint}"
        ) from e

    try:
        ws = _with_quota_retry(sh.worksheet, T7_STATE_TAB)
        try:
            header = _with_quota_retry(ws.row_values, 1)
        except Exception:
            header = []
        if not header:
            _with_quota_retry(ws.append_row, list(SNAPSHOT_COLS))
        return ws
    except Exception:
        try:
            ws = _with_quota_retry(
                sh.add_worksheet,
                title=T7_STATE_TAB, rows=rows, cols=len(SNAPSHOT_COLS) + 2,
            )
            _with_quota_retry(ws.append_row, list(SNAPSHOT_COLS))
            return ws
        except Exception as e:
            raise PolicySheetError(f"建立 _T7_State worksheet 失敗：{e}") from e


# ──────────────────────────────────────────────────────────────────────
# Save: 一次性覆寫整張表（最簡單也最不易 race condition）
# ──────────────────────────────────────────────────────────────────────
def save_all_ledgers_snapshot(
    client: Any, sheet_id: str,
    ledgers_dict: dict, funds_lookup: dict | None = None,
) -> int:
    """
    把 t7_ledgers 全表寫進 _T7_State（清掉舊資料再 batch 寫入）。
    ledgers_dict: {pk_str: Ledger}
    funds_lookup: {pk_str: fund_dict} 用來取 policy_id（可省略，從 pk_str 解析）
    回傳實際寫入列數。

    v18.73: 由 (M delete_rows + N append_row) 改為 (1 clear + 1 batch update)，
    把 Sheets API 呼叫數從 O(M+N) 降到固定 2 次，根治 429 配額錯誤。
    """
    if ledgers_dict is None:
        return 0
    ws = ensure_state_worksheet(client, sheet_id)

    # 1. 先在記憶體組裝所有列（不打 API）
    now = _dt.datetime.now().isoformat(timespec="seconds")
    lookup = funds_lookup or {}
    rows: list[list[str]] = []
    for pk_str, led in ledgers_dict.items():
        if led is None:
            continue
        try:
            led_dict = led.to_dict()
        except Exception:
            continue
        # policy_id：優先 funds_lookup → 從 pk_str ("pid::code") 解析
        pid = ""
        if pk_str in lookup:
            pid = str(lookup[pk_str].get("policy_id", "") or "")
        if not pid and "::" in pk_str:
            pid = pk_str.split("::", 1)[0]
        rows.append([
            pk_str,
            led_dict.get("fund_code", ""),
            led_dict.get("currency", ""),
            pid,
            _json.dumps(led_dict, ensure_ascii=False),
            now,
        ])

    # 2. 一次清空整個 worksheet（保留結構，清掉所有 cell）
    try:
        _with_quota_retry(ws.clear)
    except Exception as e:
        raise PolicySheetError(f"清空 _T7_State 失敗：{e}") from e

    # 3. 一次 batch 寫入（表頭 + 全部 data rows），對 Sheets API 而言是「一個」呼叫
    if not rows:
        # 空 ledgers → 仍要把表頭寫回，後續讀取才能解析欄位
        try:
            _with_quota_retry(ws.update,
                              range_name="A1",
                              values=[list(SNAPSHOT_COLS)],
                              value_input_option="RAW")
        except Exception as e:
            raise PolicySheetError(f"寫 _T7_State 表頭失敗：{e}") from e
        return 0

    all_values = [list(SNAPSHOT_COLS)] + rows
    end_col_idx = len(SNAPSHOT_COLS)  # 6 → 'F'
    end_col = chr(ord("A") + end_col_idx - 1)
    end_row = len(all_values)
    rng = f"A1:{end_col}{end_row}"
    try:
        _with_quota_retry(ws.update,
                          range_name=rng,
                          values=all_values,
                          value_input_option="RAW")
    except Exception as e:
        raise PolicySheetError(f"寫 _T7_State 失敗：{e}") from e
    return len(rows)


# ──────────────────────────────────────────────────────────────────────
# Load: 讀回 + 反序列化（不重 replay，直接還原 position 快照）
# ──────────────────────────────────────────────────────────────────────
def load_all_ledgers_snapshot(
    client: Any, sheet_id: str, ledger_class: Any,
) -> dict:
    """
    從 _T7_State 讀回所有 ledger snapshot，反序列化成 {pk_str: Ledger} dict。
    ledger_class: fund_ledger.Ledger（傳入避免本模組依賴 fund_ledger 帶來 Streamlit 循環依賴）
    缺 tab / 空表 → 回 {}（不丟錯，方便 UI flow）
    """
    try:
        sh = _with_quota_retry(client.open_by_key, sheet_id)
        ws = _with_quota_retry(sh.worksheet, T7_STATE_TAB)
    except Exception:
        return {}

    try:
        records = _with_quota_retry(ws.get_all_records)
    except Exception as e:
        raise PolicySheetError(f"讀 _T7_State 失敗：{e}") from e

    if not records:
        return {}

    out: dict = {}
    for rec in records:
        pk = str(rec.get("pk_str", "")).strip()
        ledger_json = rec.get("ledger_json", "")
        if not pk or not ledger_json:
            continue
        try:
            led_dict = _json.loads(ledger_json)
            out[pk] = ledger_class.from_dict(led_dict)
        except Exception:
            continue
    return out


def get_state_metadata(client: Any, sheet_id: str) -> dict:
    """回傳 {row_count, latest_updated_at}，給 UI 顯示「最後同步時間」用。缺 tab 回空。"""
    try:
        sh = _with_quota_retry(client.open_by_key, sheet_id)
        ws = _with_quota_retry(sh.worksheet, T7_STATE_TAB)
    except Exception:
        return {}

    try:
        records = _with_quota_retry(ws.get_all_records)
    except Exception:
        return {}

    if not records:
        return {"row_count": 0, "latest_updated_at": ""}

    df = pd.DataFrame(records)
    latest = ""
    if "updated_at" in df.columns:
        try:
            latest = str(df["updated_at"].dropna().sort_values().iloc[-1])
        except Exception:
            latest = ""
    return {"row_count": len(df), "latest_updated_at": latest}
