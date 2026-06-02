"""scripts/migrate_v149_schema.py — v1 → v2 schema 一次性升級工具

把舊 3-tab schema（保單分頁 v1 + _T7_State + _Ledgers）轉成 v2：
每張保單分頁 11 欄、內聯 units / avg_nav / avg_fx 持倉 + 多幣別現金部位。

設計原則（與 CLAUDE.md §4 鋼鐵自省一致）：
- **動原本前先備份**：呼叫 `copy_sheet_as_backup` 複製整本 Sheet → 才動原本
- **冪等**：對已是 v2 的 worksheet 自動跳過（用 `is_v2_worksheet` 判斷）
- **失敗安全**：單張保單轉換例外不中斷整批；錯誤訊息收集後一次回報
- **不刪 _T7_State / _Ledgers**：升級後保留舊 tab 一段時間以便人眼比對；
  user 確認新資料 OK 後手動刪除（或下個 release 移除）

呼叫端：
- 程式內呼叫：`from scripts.migrate_v149_schema import migrate_sheet`
- CLI 呼叫：`python -m scripts.migrate_v149_schema <SHEET_ID>`
  （CLI 模式從 st.secrets 讀 service account 或環境變數 OAuth tokens）
"""
from __future__ import annotations

from typing import Any
import json
import logging

import pandas as pd

from repositories.policy_repository import (
    PolicySheetError,
    ALL_COLS_V2,
    ITEM_TYPE_FUND,
    DEFAULT_WORKSHEET,
    is_v2_worksheet,
    write_policy_v2,
    copy_sheet_as_backup,
    load_policy_worksheet,
    _normalize_invest_twd,
    _normalize_fx,
)
from repositories.snapshot_repository import T7_STATE_TAB

log = logging.getLogger(__name__)


def _read_t7_state_rows(client: Any, sheet_id: str) -> list[dict]:
    """讀舊 _T7_State 整 tab 成 list[dict]；不存在回 []。"""
    try:
        sh = client.open_by_key(sheet_id)
        ws = sh.worksheet(T7_STATE_TAB)
    except Exception:
        return []
    try:
        rows = ws.get_all_records() or []
    except Exception:
        return []
    return rows


def _fold_ledger_json(ledger_json: str) -> dict:
    """解 _T7_State.ledger_json 一格的 JSON，fold 算出 units / avg_nav / avg_fx。

    _T7_State.ledger_json 是 LedgerT7.to_dict() 序列化結果。
    為了 portability 與 schema 弱依賴，直接解 dict 算 weighted avg：
      - total_units = Σ units(action='buy') - Σ units(action='sell')
      - total_cost_local = Σ (units × nav)(buy) - Σ (units × nav)(sell)
      - total_cost_twd  = Σ twd(buy) - Σ twd(sell)
    然後：
      - units = total_units
      - avg_nav = total_cost_local / total_units（避除以 0）
      - avg_fx  = total_cost_twd / total_cost_local（若 currency!=TWD）
    """
    out = {"units": 0.0, "avg_nav": 0.0, "avg_fx": 0.0}
    try:
        d = json.loads(ledger_json or "{}")
    except Exception:
        return out

    txns = d.get("transactions") or d.get("txns") or []
    if not isinstance(txns, list):
        return out

    total_units = 0.0
    total_cost_local = 0.0
    total_cost_twd = 0.0

    for t in txns:
        try:
            action = str(t.get("action", "buy")).lower()
            units = float(t.get("units", 0) or 0)
            nav = float(t.get("nav_at_action", t.get("nav", 0)) or 0)
            twd = float(t.get("twd", 0) or 0)
        except (TypeError, ValueError):
            continue
        sign = 1.0 if action in ("buy", "dividend") else (-1.0 if action == "sell" else 0.0)
        if sign == 0:
            continue
        total_units += sign * units
        total_cost_local += sign * (units * nav)
        total_cost_twd += sign * twd

    if total_units > 1e-9:
        out["units"] = total_units
        if total_cost_local > 0:
            out["avg_nav"] = total_cost_local / total_units
        if total_cost_local > 0 and total_cost_twd > 0:
            out["avg_fx"] = total_cost_twd / total_cost_local
    return out


def migrate_one_policy(
    client: Any, sheet_id: str, policy_id: str,
    t7_state_index: dict,
) -> dict:
    """單張保單 v1 → v2：

    1. 讀 v1 保單分頁拿 fund_url / invest_twd / currency / policy_tier
    2. 對每檔 fund 用 t7_state_index 查 _T7_State.ledger_json → fold 出 units/avg_nav/avg_fx
    3. 組 v2 df → write_policy_v2 覆寫該 tab
    4. 回傳 stat dict
    """
    stat = {"policy_id": policy_id, "funds": 0, "cash": 0, "errors": []}

    try:
        df_v1 = load_policy_worksheet(client, sheet_id, policy_id)
    except PolicySheetError as e:
        stat["errors"].append(f"讀 v1 失敗：{e}")
        return stat

    if df_v1.empty:
        return stat

    v2_rows: list[dict] = []
    for _, r in df_v1.iterrows():
        fund_url = str(r.get("fund_url", "") or "").strip()
        currency = str(r.get("currency", "") or "").strip() or "USD"
        invest_twd = _normalize_invest_twd(r.get("invest_twd", 0))
        tier = str(r.get("policy_tier", "") or "").strip()
        fund_name = str(r.get("policy_name", "") or "").strip()
        if not fund_url:
            continue

        # 從 _T7_State.ledger_json fold 取持倉
        ledger_json = t7_state_index.get((policy_id, fund_url.upper()), "")
        folded = _fold_ledger_json(ledger_json)

        v2_rows.append({
            "policy_id":        policy_id,
            "item_type":        ITEM_TYPE_FUND,
            "fund_code":        fund_url,
            "fund_name":        fund_name,
            "units":            folded["units"],
            "avg_nav":          folded["avg_nav"],
            # v18.153：含息成本 user 後續到對帳單抄；migration 預設 0（v2 編輯介面醒目提示要補）
            "avg_nav_with_div": 0.0,
            "avg_fx":           folded["avg_fx"] if folded["avg_fx"] > 0 else _normalize_fx(
                                    r.get("fx_at_buy", 0)) or 0.0,
            "currency":         currency,
            "tier":             tier,
            "amount":           "",
            "invest_twd":       invest_twd,
        })
        stat["funds"] += 1

    df_v2 = pd.DataFrame(v2_rows, columns=list(ALL_COLS_V2))
    try:
        write_policy_v2(client, sheet_id, policy_id, df_v2)
    except PolicySheetError as e:
        stat["errors"].append(f"寫 v2 失敗：{e}")
    return stat


def migrate_sheet(
    client: Any, sheet_id: str, with_backup: bool = True,
) -> dict:
    """整本 Sheet 升級 v1 → v2。

    Args:
        client: gspread client
        sheet_id: 要升級的 Sheet ID
        with_backup: True 則先 copy 一份備份（推薦）

    Returns:
        summary dict:
        {
          "backup_sheet_id": str | "",
          "backup_sheet_url": str | "",
          "policies": int,
          "v2_already": int,
          "migrated": list[dict],   # 每張保單的 stat
          "errors": list[str],
        }
    """
    summary: dict = {
        "backup_sheet_id": "",
        "backup_sheet_url": "",
        "policies": 0,
        "v2_already": 0,
        "migrated": [],
        "errors": [],
    }

    # 1) Safety net：備份整本 Sheet
    if with_backup:
        try:
            bid, burl = copy_sheet_as_backup(client, sheet_id)
            summary["backup_sheet_id"] = bid
            summary["backup_sheet_url"] = burl
        except PolicySheetError as e:
            summary["errors"].append(f"備份失敗（中斷）：{e}")
            return summary

    # 2) 讀 _T7_State 建索引 (policy_id, fund_code) → ledger_json
    t7_rows = _read_t7_state_rows(client, sheet_id)
    t7_index: dict = {}
    for r in t7_rows:
        pid = str(r.get("policy_id", "") or "").strip()
        code = str(r.get("fund_code", "") or "").strip().upper()
        lj = r.get("ledger_json", "") or ""
        if pid and code:
            t7_index[(pid, code)] = lj

    # 3) 列保單分頁（過濾 _ 開頭與 Policies）
    try:
        sh = client.open_by_key(sheet_id)
        tabs = [ws for ws in sh.worksheets()
                if not ws.title.startswith("_") and ws.title != DEFAULT_WORKSHEET]
    except Exception as e:
        summary["errors"].append(f"列保單分頁失敗：{e}")
        return summary

    for ws in tabs:
        policy_id = ws.title
        summary["policies"] += 1

        # 已是 v2 跳過（冪等）
        if is_v2_worksheet(ws):
            summary["v2_already"] += 1
            summary["migrated"].append({
                "policy_id": policy_id, "funds": 0, "cash": 0,
                "errors": [], "skipped": "already v2",
            })
            continue

        stat = migrate_one_policy(client, sheet_id, policy_id, t7_index)
        summary["migrated"].append(stat)

    return summary


# ════════════════════════════════════════════════════════════
# CLI 用法（debug only，非生產）：
#   python -m scripts.migrate_v149_schema <SHEET_ID>
# 環境變數 GOOGLE_APPLICATION_CREDENTIALS 指向 service account JSON 檔
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    import os

    if len(sys.argv) < 2:
        print("Usage: python -m scripts.migrate_v149_schema <SHEET_ID>", file=sys.stderr)
        sys.exit(1)

    sheet_id_arg = sys.argv[1]
    gac = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not gac:
        print("ERROR: GOOGLE_APPLICATION_CREDENTIALS not set", file=sys.stderr)
        sys.exit(2)

    import json as _json
    with open(gac, "r", encoding="utf-8") as f:
        sa_creds = _json.load(f)

    from repositories.policy_repository import get_gspread_client
    cli = get_gspread_client(sa_creds)
    result = migrate_sheet(cli, sheet_id_arg, with_backup=True)
    print(_json.dumps(result, indent=2, ensure_ascii=False, default=str))
