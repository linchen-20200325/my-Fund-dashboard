# -*- coding: utf-8 -*-
"""設定與診斷的正式資料來源：呼叫 L2 `services/v2_tables/settings_store`，組出與 fixtures 同形的 dataset。

依據 docs/v2/49_data_integration_plan.md §3.3 方案 A（`source.py` 那一列）、docs/v2/50_settings_sheet_design.md、
`ACCEPTANCE.md` 七（失敗訊息遮蔽），以及客戶 2026-09-26 核准的 set 頁正式模式線框草稿：
- **只由 `ui_v2/app_set_live.py` import**；`page.py` 不 import 本檔（體例同 `ui_v2/mkt/source.py`）。
- 本檔不 import fixtures；規格快照取自 `spec.py`（不是資料）。不放任何快取（快取只在 L1）；
  不直接發任何網路請求，一律經 L2。
- **秘密值在本層讀**（`st.secrets`、環境變數、登入後的 OAuth 權杖），交給 L2；遮蔽由 L2 接到 L1、
  在寫出點做一次。本層交給畫面的每一個失敗字串都已遮蔽。
- `fetch_log.message` 原樣交給畫面、**不再遮第二次**：它在寫進試算表之前已由 L2 遮過，畫面與
  `fetch_log` 必須是同一份字串（ACCEPTANCE 7.3 最後一條、7.4；`44` SET-5 判準）。

三個入口（`page.render(load_live=..., save_live=..., refetch_live=...)`）：

`load_live()` 回傳 `{"dataset": ..., "notes": ...}`：
- `dataset`：與 `fixtures.scenario()` 同形（`now_utc`、五張表、`errors`、`save_errors`、`save_inputs`、`spec`）。
  ~~`nav`、`dividend` 兩表尚未接上（`49` Q12）→ 空列表、不進 `errors`（那是「還沒接」，不是「讀失敗」）。~~
  → 2026-10-09 狀態更新（不是漏刪）：`dividend` 仍尚未接上 → 空列表、不進 `errors`（「還沒接」，不是「讀失敗」）。
  `nav` 不存表（客戶裁示 Q1）→ 也是空列表；SET-1 淨值列的最近取得時間改由 `kind_time_from_log`
  （L2 `LOG_TIMED_TABLES`，`{"nav": "淨值"}`）指給 `logic`：取 `fetch_log` 淨值層最近一次 `ok` 那一筆的 `started_at`（見 `logic._build_set1`）。
  `now_utc` 讀系統時鐘（`49` §2.5）。
- `notes`：
  `mask_token`（遮蔽記號，L2 那一份）、`pending_tables`、`wired_tiers`、`pages_reading_settings`（L2 的接線旗標，草稿 B7）、
  `gate`（寫入閘門，不打上游）、`title`（★10：`{"state": ok|not_configured|cooling|failed, "text", "remaining_sec"}`）、
  `table_errors`（`{表: {"code", "remaining_sec", "tab", "expected", "actual"}}`）、
  `structure`（★9 計數）、`source_cooldowns`（市場指標來源的冷卻狀態；只用在市場指標層，見 `live.refetch_button`）。

`save_setting(鍵, 值或 None, value_kind)` → L2 `save_setting_for_page` 的回傳（純 dict，訊息已遮蔽）。
`refetch(層級)` → `{"tier", "fetched", "log_message", "masked_errors", "empty", "stage", "message", "ok"}`
（L2 回傳裡**未遮蔽**的 `table["errors"]` 不交出去）。
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import streamlit as st

from services.v2_tables import market_indicator, masking, settings_store

from . import spec

_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _secret_values() -> list:
    """從 `st.secrets`、環境變數與登入權杖讀出 ACCEPTANCE 7.2 列名鍵的值（同 mkt）。"""
    return masking.secret_values(
        [st.secrets, os.environ],
        oauth_tokens=st.session_state.get("gsheet_tokens"),
        custom_oauth_cfg=st.session_state.get("custom_oauth_cfg"),
    )


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime(_TIME_FORMAT)


def _error_info(exc) -> dict:
    info = {"code": exc.code, "remaining_sec": exc.remaining_sec}
    if exc.code == "header_mismatch":
        info.update(tab=exc.details.get("tab"), expected=list(exc.details.get("expected", ())),
                    actual=list(exc.details.get("actual", ())))
    return info


def _read(loader, values, table, errors, table_errors):
    try:
        return loader(values)
    except settings_store.SettingsSheetError as exc:
        errors[table] = str(exc)            # 已由 L1 經 L2 的 mask 遮過
        table_errors[table] = _error_info(exc)
        return None


def _title_state(code, message, remaining_sec) -> dict:
    """★10 的狀態：沒設 ID／冷卻中（暫停，草稿 B4）／其餘讀不到。"""
    if code in ("not_configured", "cooling"):
        return {"state": code, "text": message, "remaining_sec": remaining_sec}
    return {"state": "failed", "text": message, "remaining_sec": None}


def load_live() -> dict:
    """給 `page.render(load_live=...)` 用的載入函式。"""
    values = _secret_values()
    errors, table_errors, structure = {}, {}, {}

    settings = _read(settings_store.load_user_settings, values, "user_setting", errors, table_errors)
    logs = _read(settings_store.load_fetch_log, values, "fetch_log", errors, table_errors)
    indicators = _read(settings_store.load_market_indicator, values, "market_indicator", errors, table_errors)

    user_setting = []
    if settings is not None:
        user_setting = [dict(row) for row in settings["rows"].values()]
        structure["user_setting"] = {"bad_rows": len(settings["bad_rows"]),
                                     "broken_keys": list(settings["broken_keys"])}
    fetch_log = []
    if logs is not None:
        fetch_log = [dict(row) for row in logs["rows"]]
        structure["fetch_log"] = {"bad_rows": len(logs["bad_rows"]) + len(logs["open_bad_rows"]),
                                  "duplicates": logs["duplicate_log_ids"]}
    mi_rows = []
    if indicators is not None:
        mi_rows = [dict(row) for row in indicators["rows"]]
        structure["market_indicator"] = {"bad_rows": len(indicators["bad_rows"]),
                                         "conflicts": len(indicators["conflicts"]),
                                         "is_revised_mismatch": indicators["is_revised_mismatch"]}

    # ★10：標題取自讀設定那一次打開（L1 記下），讀設定失敗時是同一個失敗的兩處呈現、不另計一次取數。
    if "user_setting" in errors:
        title = _title_state(table_errors["user_setting"]["code"], errors["user_setting"],
                             table_errors["user_setting"]["remaining_sec"])
    else:
        try:
            title = {"state": "ok", "text": settings_store.sheet_title(values)}
        except settings_store.SettingsSheetError as exc:
            title = _title_state(exc.code, str(exc), exc.remaining_sec)

    dataset = {
        "now_utc": _now_utc(),
        "nav": [],
        "kind_time_from_log": dict(settings_store.LOG_TIMED_TABLES),   # 淨值不存表：時間讀 fetch_log
        "dividend": [],
        "market_indicator": mi_rows,
        "fetch_log": fetch_log,
        "user_setting": user_setting,
        "errors": errors,
        "save_errors": {},
        "save_inputs": {},
        "spec": spec.dataset_spec(live=True),  # alo_basis 用實作層定的型別（客戶 2026-09-26 裁示）
    }
    notes = {
        "mask_token": masking.MASK,
        "pending_tables": list(settings_store.PENDING_TABLES),
        "wired_tiers": list(settings_store.WIRED_TIERS),
        "pages_reading_settings": list(settings_store.PAGES_READING_SETTINGS),
        "gate": dict(settings_store.sheet_gate(values)),
        "title": title,
        "table_errors": table_errors,
        "structure": structure,
        "source_cooldowns": market_indicator.source_cooldowns(),
    }
    return {"dataset": dataset, "notes": notes}


def save_setting(setting_key, setting_value, value_kind) -> dict:
    """給 `page.render(save_live=...)` 用：存一個鍵（L2 先檢查值與型別，不符不存）。"""
    return settings_store.save_setting_for_page(setting_key, setting_value, value_kind, _secret_values())


def refetch(tier) -> dict:
    """給 `page.render(refetch_live=...)` 用：重新取數。~~目前只接上市場指標那一層~~ → 2026-10-09 再接上淨值層
    （客戶裁示 Q2～Q4；狀態更新，不是漏刪）。入口由 L2 `REFETCH_BY_TIER` 分派（與 `WIRED_TIERS` 同一組鍵）。"""
    if tier not in settings_store.WIRED_TIERS:
        raise ValueError(f"層級 {tier!r} 的取數尚未接上")
    out = settings_store.REFETCH_BY_TIER[tier](_secret_values())
    persist = out["persist"]
    return {
        "tier": tier,
        # 淨值層持倉讀不到時 L2 沒有組表（`table` 為 None）→ 取回 0 列。
        "fetched": sum((out["table"] or {}).get("fetched", {}).values()),
        "log_message": persist["log_message"],
        "masked_errors": dict(persist["masked_errors"]),
        "empty": dict(persist["empty"]),
        "stage": persist["stage"],
        "message": persist["message"],
        "ok": persist["ok"],
    }
