"""models/policy.py — 保單視圖 T7 帳本複合鍵工具（v11.0 從 policy_keys.py 搬入）

問題：t7_ledgers 原以 fund_code 為鍵，若一檔基金在不同保單各買一份會互相覆蓋，
損益／配息現金流被攪混。本模組把 (policy_id, fund_code) 轉為字串 pk，
讓既有 `dict[str → Ledger]` 結構不變、只升鍵語意。

純函式，無 streamlit / 第三方依賴，便於單元測試。

v11.0 分層歸位：本檔屬於 Models / DTO Layer，純資料型別 + 複合鍵 helper。
向後相容：根目錄 policy_keys.py 保留 `from models.policy import *` shim，
        E 階段收尾後 shim 刪除。
"""
from __future__ import annotations

from typing import Iterable

# 分隔符選擇：基金代碼是 [A-Z0-9_-]，policy_id 用戶自填；用兩個冒號避免衝突
PK_SEP = "::"


def make_pk(fund: dict | None) -> tuple[str, str]:
    """
    從 portfolio_funds 條目產生 (policy_id, code) 複合鍵元組。

    - fund 為 None 或缺 code → ("", "")
    - 缺 policy_id → ("", code) — 視為「未綁保單」/手動加入
    """
    if not isinstance(fund, dict):
        return ("", "")
    code = str(fund.get("code", "") or "").strip().upper()
    pid  = str(fund.get("policy_id", "") or "").strip()
    return (pid, code)


def pk_str(pk: tuple[str, str]) -> str:
    """元組 → 字串（給 session_state dict / widget key 用）。"""
    if not isinstance(pk, tuple) or len(pk) != 2:
        return ""
    return f"{pk[0]}{PK_SEP}{pk[1]}"


def parse_pk(s: str) -> tuple[str, str]:
    """字串 → 元組；不含分隔符視為舊鍵（只有 code）。"""
    if not isinstance(s, str):
        return ("", "")
    if PK_SEP not in s:
        return ("", s.strip().upper())
    pid, code = s.split(PK_SEP, 1)
    return (pid.strip(), code.strip().upper())


def fund_pk_str(fund: dict | None) -> str:
    """便利捷徑：fund dict → 直接字串 pk。"""
    return pk_str(make_pk(fund))


def migrate_ledger_dict(
    old: dict,
    portfolio_funds: Iterable[dict] | None = None,
) -> dict:
    """
    一次性遷移 session_state.t7_ledgers：
    - 已是 composite pk（含 `::`）→ 原樣保留
    - 舊鍵（純 code）→ 用 portfolio_funds 反查 policy_id，重 key 成 composite
        - 同 code 在 portfolio_funds 出現多次：v1 取「第一個有 policy_id 的」優先；
          其餘退回 ("", code)（未綁）— 因 v1 舊 session 不可能同 code 兩條帳本
    - 未在 portfolio_funds 找到的舊鍵：保留為 ("", code)

    回傳一個新 dict，不修改輸入。
    """
    if not isinstance(old, dict):
        return {}
    pf_list = list(portfolio_funds or [])
    # 反查表：code → 第一個有 policy_id 的 fund
    lookup: dict[str, dict] = {}
    for _f in pf_list:
        _c = str(_f.get("code", "") or "").strip().upper()
        if not _c:
            continue
        if _c not in lookup:
            lookup[_c] = _f
        else:
            # 若已存在但前一個沒 policy_id、這個有，則覆蓋
            if not lookup[_c].get("policy_id") and _f.get("policy_id"):
                lookup[_c] = _f

    out: dict = {}
    for k, v in old.items():
        if not isinstance(k, str):
            continue
        if PK_SEP in k:
            out[k] = v
            continue
        code_norm = k.strip().upper()
        _f = lookup.get(code_norm)
        pid = str((_f or {}).get("policy_id", "") or "").strip()
        out[f"{pid}{PK_SEP}{code_norm}"] = v
    return out
