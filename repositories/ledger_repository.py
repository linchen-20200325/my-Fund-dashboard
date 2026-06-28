"""
repositories/ledger_repository.py — 交易帳同步到 Google Sheets（v11.0 從 ledger_store.py 搬入）

設計原則：
- 純資料層：不 import streamlit
- 與 policy_store 對稱（同樣 lazy import、PolicySheetError 共用例外體系）
- 一個系統 tab `_Ledgers` 存所有保單的交易紀錄，用 policy_id 欄區分
  → 避免每保單兩個 tab 把 sheet 撐爆（5 保單就 10 tab + 系統 tab）
- 主鍵 (policy_id, code, date, action, units)：同檔基金同日多筆交易要能區分

LEDGER_COLS（9 欄）：
    policy_id | date | code | action | units | nav_at_action | twd | fee | note

action 限 'buy' / 'sell' / 'dividend' / 'fee' / 'fx'，呼叫端自由：不在
列表內視為自訂類型（不會被攔截，但統計時可能漏算）。

v11.0 分層歸位：本檔屬於 Repository Layer，Google Sheets 持久化 I/O。
向後相容：根目錄 ledger_store.py 保留 `from repositories.ledger_repository import *` shim，
        E 階段收尾後 shim 刪除（届時 caller 改用 repositories.ledger_repository）。
"""
from __future__ import annotations

from typing import Any, Iterable
import datetime as _dt

import pandas as pd

# 共用 policy_store 的 PolicySheetError 體系，呼叫端只接一個例外
from repositories.policy_repository import PolicySheetError


LEDGER_TAB = "_Ledgers"

LEDGER_COLS: tuple[str, ...] = (
    "policy_id",
    "date",
    "code",
    "action",
    "units",
    "nav_at_action",
    "twd",
    "fee",
    "note",
)

KNOWN_ACTIONS = ("buy", "sell", "dividend", "fee", "fx")


# ──────────────────────────────────────────────────────────────────────
# Normalizers
# ──────────────────────────────────────────────────────────────────────
def _norm_float(v: Any) -> float:
    if v is None or v == "":
        return 0.0
    try:
        if isinstance(v, str):
            v = v.replace(",", "").strip()
            if not v:
                return 0.0
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def _norm_date(v: Any) -> str:
    """容錯：datetime/date/'YYYY-MM-DD'/'YYYY/MM/DD' → 'YYYY-MM-DD'；其餘原樣回傳 trimmed。"""
    if v is None or v == "":
        return ""
    if isinstance(v, (_dt.date, _dt.datetime)):
        return v.strftime("%Y-%m-%d")
    s = str(v).strip().replace("/", "-")
    return s


def _row_values(row: dict) -> list:
    """把 ledger dict 攤平成 LEDGER_COLS 順序的 list。"""
    return [row.get(c, "") for c in LEDGER_COLS]


# ──────────────────────────────────────────────────────────────────────
# Worksheet 管理
# ──────────────────────────────────────────────────────────────────────
def ensure_ledger_worksheet(client: Any, sheet_id: str, rows: int = 500) -> Any:
    """確保 _Ledgers tab 存在；不存在則建立並寫表頭。回傳 worksheet。"""
    try:
        sh = client.open_by_key(sheet_id)
    except Exception as e:
        raise PolicySheetError(f"開啟 Sheet 失敗：{e}") from e

    try:
        ws = sh.worksheet(LEDGER_TAB)
        try:
            header = ws.row_values(1)
        except Exception:
            header = []
        if not header:
            ws.append_row(list(LEDGER_COLS))
        return ws
    except Exception:
        try:
            ws = sh.add_worksheet(title=LEDGER_TAB, rows=rows, cols=len(LEDGER_COLS) + 2)
            ws.append_row(list(LEDGER_COLS))
            return ws
        except Exception as e:
            raise PolicySheetError(f"建立 ledger worksheet 失敗：{e}") from e


# ──────────────────────────────────────────────────────────────────────
# Read
# ──────────────────────────────────────────────────────────────────────
def load_all_ledgers(client: Any, sheet_id: str) -> pd.DataFrame:
    """讀 _Ledgers 全表。tab 不存在或空表回空 DataFrame。"""
    try:
        sh = client.open_by_key(sheet_id)
        ws = sh.worksheet(LEDGER_TAB)
    except Exception:
        return pd.DataFrame(columns=list(LEDGER_COLS))

    try:
        records = ws.get_all_records()
    except Exception as e:
        raise PolicySheetError(f"讀取 _Ledgers 失敗：{e}") from e

    if not records:
        return pd.DataFrame(columns=list(LEDGER_COLS))

    df = pd.DataFrame(records)
    for c in LEDGER_COLS:
        if c not in df.columns:
            df[c] = ""
    df = df[list(LEDGER_COLS)].copy()
    df["units"]         = df["units"].map(_norm_float)
    df["nav_at_action"] = df["nav_at_action"].map(_norm_float)
    df["twd"]           = df["twd"].map(_norm_float)
    df["fee"]           = df["fee"].map(_norm_float)
    df["date"]          = df["date"].map(_norm_date)
    for c in ("policy_id", "code", "action", "note"):
        df[c] = df[c].fillna("").astype(str).str.strip()
    return df


def append_ledger_row(client: Any, sheet_id: str, row: dict) -> None:
    """
    純 append 一列交易（不去重，呼叫端負責主鍵）。
    自動 ensure tab + normalize 欄位。
    """
    pid = str(row.get("policy_id", "")).strip()
    code = str(row.get("code", "")).strip()
    if not pid or not code:
        raise PolicySheetError("append_ledger_row 必須提供 policy_id + code")

    clean = {
        "policy_id":     pid,
        "date":          _norm_date(row.get("date")),
        "code":          code,
        "action":        str(row.get("action", "")).strip().lower(),
        "units":         _norm_float(row.get("units")),
        "nav_at_action": _norm_float(row.get("nav_at_action")),
        "twd":           _norm_float(row.get("twd")),
        "fee":           _norm_float(row.get("fee")),
        "note":          str(row.get("note", "")).strip(),
    }
    ws = ensure_ledger_worksheet(client, sheet_id)
    try:
        ws.append_row(_row_values(clean))
    except Exception as e:
        raise PolicySheetError(f"append ledger 失敗：{e}") from e


def replace_ledgers_for_policy(
    client: Any, sheet_id: str, policy_id: str, rows: Iterable[dict],
) -> int:
    """
    把該保單的所有 ledger 列「全砍重寫」（用於 T7 編輯持倉的批次同步）。
    回傳新寫入的列數。
    """
    pid = str(policy_id).strip()
    if not pid:
        raise PolicySheetError("replace_ledgers_for_policy 必須提供 policy_id")

    ws = ensure_ledger_worksheet(client, sheet_id)
    try:
        all_values = ws.get_all_values()
    except Exception as e:
        raise PolicySheetError(f"讀 _Ledgers 失敗：{e}") from e

    header = all_values[0] if all_values else list(LEDGER_COLS)
    try:
        pid_idx = header.index("policy_id")
    except ValueError as e:
        raise PolicySheetError(f"_Ledgers 表頭缺 policy_id：{e}") from e

    # 從尾巴往前刪，避免行號偏移
    to_delete = [
        r for r, line in enumerate(all_values[1:], start=2)
        if len(line) > pid_idx and line[pid_idx] == pid
    ]
    for r in reversed(to_delete):
        try:
            ws.delete_rows(r)
        except Exception as e:
            raise PolicySheetError(f"清除舊 ledger 列失敗：{e}") from e

    new_rows = []
    for row in rows:
        clean = {
            "policy_id":     pid,
            "date":          _norm_date(row.get("date")),
            "code":          str(row.get("code", "")).strip(),
            "action":        str(row.get("action", "")).strip().lower(),
            "units":         _norm_float(row.get("units")),
            "nav_at_action": _norm_float(row.get("nav_at_action")),
            "twd":           _norm_float(row.get("twd")),
            "fee":           _norm_float(row.get("fee")),
            "note":          str(row.get("note", "")).strip(),
        }
        if not clean["code"]:
            continue
        new_rows.append(_row_values(clean))

    if new_rows:
        try:
            for vals in new_rows:
                ws.append_row(vals)
        except Exception as e:
            raise PolicySheetError(f"批次 append ledger 失敗：{e}") from e

    return len(new_rows)
