# -*- coding: utf-8 -*-
"""💼 我的資產｜離線示範頁的固定封包（純常數函式；不 import 任何東西、不取數、不讀憑證、不寫任何東西）。

授權：客戶 2026-11-25 核准 A-AST-MOUNT-FAKE-1（`#1296` comment 7147974835，要點轉述；正式 DEC 由治理 writer 落盤，本檔不冒充已入主線的 DEC）。
依 `DEC-2026-11-19-09` 條件 (1)／(8) 與 S-AST-M1 v2 Gate：既有 11 個 FAKE 情境中**只有情境③**（市值基準未開放、`evidence=None`）不顯示假持股、假金額、假成本或個人設定值，
所以本檔回傳與③相同的無證據封包；其餘 10 個情境只留在 PoC 測試，**不進任何畫面**。

⚠️ 這個封包是**離線示範的固定常數**，不是 production 載入端的現況快照：頁面據此顯示的「資料不足」是示範，不代表系統真的讀不到持倉。
形狀對照 `AssetsLoadResult.to_primitive()`（schema_version 1）；`ui_v3/adapters/assets_page.py::build_assets_page` 是它的唯一消費者。
"""
from __future__ import annotations

__all__ = ("demo_envelope",)


def demo_envelope() -> dict:
    """每次回傳新的 dict（呼叫端不得修改共用常數）：blocked、`evidence=None`、四項設定皆 `set`（只是狀態，不含任何設定值）。"""
    return {
        "schema_version": 1,
        "status": "blocked",
        "blocked_reason": "market_basis_assembly_not_available_in_preview",
        "problems": [],
        "settings_status": {"alo_basis": "set", "alo_target_weights": "set", "alo_tolerance_pp": "set", "alo_bucket_names": "set"},
        "holding_failure_code": None,
        "chart_claim": "withheld_pending_approval",
        "evidence": None,
    }
