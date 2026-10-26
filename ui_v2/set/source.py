# -*- coding: utf-8 -*-
"""設定與診斷的正式資料來源：呼叫 L2 `services/v2_tables/settings_store`，組出與 fixtures 同形的 dataset。

依據 docs/v2/49_data_integration_plan.md §3.3 方案 A（`source.py` 那一列）、docs/v2/50_settings_sheet_design.md、
`ACCEPTANCE.md` 七（失敗訊息遮蔽），以及客戶 2026-09-26 核准的 set 頁正式模式線框草稿：
- **只由 `ui_v2/app_set_live.py` import**；`page.py` 不 import 本檔（體例同 `ui_v2/mkt/source.py`）。
- 本檔不 import fixtures；規格快照取自 `spec.py`（不是資料）。不放任何快取（快取只在 L1）；
  不直接發任何網路請求，一律經 L2。
- **秘密值在本層讀**（`st.secrets`、環境變數、登入後的 OAuth 權杖），交給 L2；遮蔽由 L2 接到 L1、
  在寫出點做一次。本層交給畫面的每一個失敗字串都已遮蔽。
- `fetch_log.message` 原樣交給畫面、**不再遮第二次**：它在記錄之前已由 L2 遮過，畫面與
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
  `structure`（★9 計數）、`source_cooldowns`（市場指標來源的冷卻狀態；只用在市場指標層，見 `live.refetch_button`）、
  `runtime`（`{"fetch_log": bool, "market_indicator": bool}`：哪一張表含本次工作階段的重新取數結果；2026-10-26 裁示第 6 節，
  重新取數不寫試算表，結果放在 `st.session_state`，讀取時優先併入，畫面標來源）。

`save_setting(鍵, 值或 None, value_kind)` → L2 `save_setting_for_page` 的回傳（純 dict，訊息已遮蔽）。
`refetch(層級)` → `{"tier", "fetched", "log_message", "masked_errors", "empty", "stage", "message", "ok"}`
（L2 回傳裡**未遮蔽**的 `table["errors"]` 不交出去）。
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import streamlit as st

from services.v2_tables import market_indicator, masking, personal_session, settings_store

from . import spec

_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _secret_values() -> list:
    """從 `st.secrets`、環境變數與登入權杖讀出 ACCEPTANCE 7.2 列名鍵的值（同 mkt）。"""
    return masking.secret_values(
        [st.secrets, os.environ],
        oauth_tokens=st.session_state.get("gsheet_tokens"),
        custom_oauth_cfg=st.session_state.get("custom_oauth_cfg"),
    )


def mask_error(message: str) -> str:
    """給 `page.render(mask_error=...)`：整頁載入失敗時的訊息原文經遮蔽，才收進設定與診斷頁的進階診斷
    （Phase 3 P1-⑤，BL-0362；同 `ui_v2/hld/source.py::mask_error`）。"""
    return masking.mask_message(message, _secret_values())


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
    # 2026-10-26 裁示第 6 節：併入本次工作階段的重新取數結果（記憶體，未存入試算表；規則見 `_merge_runtime`：
    # 市場指標同主鍵不同值不覆蓋、計入主鍵矛盾），試算表讀取錯誤照留，畫面另標來源。
    runtime = _merge_runtime(settings_store.session_runtime(st.session_state), fetch_log, mi_rows, errors,
                             structure)

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
        "service_account": dict(settings_store.service_account_status(values)),   # 客戶 2026-10-18 裁示 C1／S1
        "title": title,
        "table_errors": table_errors,
        "structure": structure,
        "source_cooldowns": market_indicator.source_cooldowns(),
        "runtime": runtime,
    }
    return {"dataset": dataset, "notes": notes}


def _merge_runtime(runtime, fetch_log: list, mi_rows: list, errors: dict, structure: dict) -> dict:
    """把本次工作階段的取數紀錄與市場指標列併進（就地改 `fetch_log`、`mi_rows`、`structure`）。

    ~~有本次資料時 `errors.pop(表)`~~ → 2026-10-26 獨立稽核必修 1（有意識的更正，不是漏刪）：試算表讀取錯誤**照留**、
    照既有方式顯示；畫面另標「本次工作階段取數，未存入試算表；試算表讀取失敗」（`live.TEXT_RUNTIME_SOURCE_SHEET_FAILED`）。
    市場指標列以 L2 `merge_sheet_and_runtime_indicators` 合併（同主鍵不同值不覆蓋、計入主鍵矛盾；必修 2）。

    回 `notes["runtime"]`：`{"fetch_log": bool, "market_indicator": bool, "conflicts": int}` —— 哪一張表含本次工作階段的資料、
    本次與試算表主鍵矛盾幾組（畫面據此標來源）。都沒有 → 原樣（照既有 Missing／失敗呈現）。
    """
    logs = runtime.load_fetch_log()["rows"]
    if logs:
        ids = {r["log_id"] for r in logs}
        fetch_log[:] = sorted([r for r in fetch_log if r["log_id"] not in ids] + [dict(r) for r in logs],
                              key=lambda r: r["started_at"])
    merged = settings_store.merge_sheet_and_runtime_indicators(mi_rows, runtime)
    mi_rows[:] = merged["rows"]
    conflicts = len(merged["conflicts"])
    if conflicts:
        mi = structure.setdefault("market_indicator", {"bad_rows": 0, "conflicts": 0, "is_revised_mismatch": 0})
        mi["conflicts"] = mi.get("conflicts", 0) + conflicts   # ★9「⚠ 主鍵矛盾 N 組，未採用」照既有方式顯示
    return {"fetch_log": bool(logs), "market_indicator": bool(merged["runtime_rows"]), "conflicts": conflicts}


def save_setting(setting_key, setting_value, value_kind) -> dict:
    """給 `page.render(save_live=...)` 用：存一個鍵（L2 先檢查值與型別，不符不存）。"""
    return settings_store.save_setting_for_page(setting_key, setting_value, value_kind, _secret_values())


def refetch(tier) -> dict:
    """給 `page.render(refetch_live=...)` 用：重新取數。~~目前只接上市場指標那一層~~ → 2026-10-09 再接上淨值層
    （客戶裁示 Q2～Q4；狀態更新，不是漏刪）。入口由 L2 `REFETCH_BY_TIER` 分派（與 `WIRED_TIERS` 同一組鍵）。"""
    if tier not in settings_store.WIRED_TIERS:
        raise ValueError(f"層級 {tier!r} 的取數尚未接上")
    # 2026-10-26 裁示第 6 節：結果與取數紀錄記在本次工作階段（`st.session_state`），不寫任何 Google Sheet。
    runtime = settings_store.session_runtime(st.session_state)
    if tier == market_indicator.SOURCE_TIER:
        # 2026-10-13：市場指標層含 FRED 三鍵，金鑰在本層讀好交下去（L2 不讀 secrets；讀法同 `ui_v2/mkt/source.py`）。
        out = settings_store.REFETCH_BY_TIER[tier](
            _secret_values(), runtime=runtime,
            fred_api_key=market_indicator.fred_api_key_from([st.secrets, os.environ]))
    else:
        out = settings_store.REFETCH_BY_TIER[tier](_secret_values(), runtime=runtime)
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


# ───────────────────────── Google 個人登入（批 3b-2） ─────────────────────────
# 只用 `st.session_state` 與 `st.query_params`（工作階段身分；本頁不讀平台登入身分、不 fallback）。
# 登入、確認、登出、切換是身分動作，不是試算表寫入：本段不呼叫任何 Sheet 寫入函式。
# 失敗一律只往畫面交錯誤代號（九個之一），不交例外字串、不交權杖、不交授權碼。

_KEY_NOTICE = "_set_login_notice"          # 上一個登入動作留下的錯誤代號（畫面讀一次就清）
_KEY_SWITCH_ASK = "_set_login_switch_ask"  # 已按［切換帳號］、等使用者確認
_KEY_CB_SEEN = "_set_login_cb_seen"        # 這個工作階段已處理過的 callback state（防重跑重放）
# Google 導回時帶的參數：處理完一律從網址拿掉（授權碼一次性，不留在網址列、不隨重跑重送）。
_CALLBACK_PARAMS = ("code", "state", "scope", "authuser", "prompt", "hd", "error", "error_description", "iss")
_LOG = logging.getLogger(__name__)


def _handle_oauth_callback() -> None:
    """網址帶 `code` 與 `state` → 先把這些參數從網址拿掉，再呼叫 `complete_login` 一次；失敗只記錯誤代號。

    成功只進「待確認登入」（要使用者按［確認］才啟用，見 `login_act`）。重跑時同一個 state 不再送第二次
    （橋接與 OAuth 層本來就是一次性，第二次必得 AUTH_STATE_INVALID，會把成功蓋成假失敗）。"""
    params = st.query_params
    present = [name for name in _CALLBACK_PARAMS if name in params]
    if not present:
        return
    code, state_param, has_error = params.get("code"), params.get("state"), "error" in params
    for name in present:   # 先拿掉（含單獨出現的 code／state）、再處理：授權碼一次性，不留在網址列
        del params[name]
    if code is None or state_param is None:
        if has_error and code is None:   # 授權頁導回帶 error：取消或沒有完成（分不出細項，不猜）
            st.session_state[_KEY_NOTICE] = "AUTH_REQUIRED"
        return
    if st.session_state.get(_KEY_CB_SEEN) == state_param:
        return
    st.session_state[_KEY_CB_SEEN] = state_param
    result = personal_session.complete_login(st.session_state, code, state_param)
    if result.get("ok") is not True:
        st.session_state[_KEY_NOTICE] = result.get("error_code")


def login_load() -> dict:
    """給 `page.render(login_live=...)`：先處理 callback，再交出畫面要的輸入（`ui_v2/set/live.py::login_view` 的輸入）。
    任何一步出乎意料的例外 → 該項給 None，畫面落「⬜ 無法判定」，不往上拋、不猜成已登入。"""
    state = st.session_state
    try:
        _handle_oauth_callback()
    except Exception as exc:  # noqa: BLE001 —— 不是吞：記類型（不記訊息）、畫面如實落「無法判定」，不當成已登入
        _LOG.warning("設定頁登入 callback 處理失敗：%s", type(exc).__name__)
        state[_KEY_NOTICE] = "UNAVAILABLE"
    try:
        status = personal_session.status(state)
    except Exception as exc:  # noqa: BLE001 —— 同上
        _LOG.warning("設定頁讀登入狀態失敗：%s", type(exc).__name__)
        status = None
    begin = None
    if isinstance(status, dict) and status.get("login_state") == "logged_out":
        try:
            begin = personal_session.begin_login(state)   # 同一工作階段重複呼叫會重用尚未過期的授權請求
        except Exception as exc:  # noqa: BLE001 —— 同上
            _LOG.warning("設定頁取授權網址失敗：%s", type(exc).__name__)
            begin = None
    switch_confirm = bool(state.get(_KEY_SWITCH_ASK)) and isinstance(status, dict) \
        and status.get("login_state") == "logged_in"
    if not switch_confirm:
        state.pop(_KEY_SWITCH_ASK, None)
    return {"status": status, "begin": begin, "notice": state.pop(_KEY_NOTICE, None),
            "switch_confirm": switch_confirm}


def login_act(action, displayed_email=None) -> None:
    """畫面按鈕的動作（只接白名單內的代號）。確認只由使用者按［確認］進來，沒有任何自動確認的路徑。

    `confirm` 要帶「畫面上顯示的待確認帳號」：動作當下重讀狀態，目前待確認的帳號不等於畫面上顯示的就不確認（無動作；
    重畫後畫面會顯示新的待確認登入）。`switch_go` 要有 `switch_ask` 留下的標記。"""
    state = st.session_state
    if action == "switch_ask":
        state[_KEY_SWITCH_ASK] = True
        return
    if action == "switch_cancel":
        state.pop(_KEY_SWITCH_ASK, None)
        return
    if action == "confirm":
        try:
            current = personal_session.status(state)
        except Exception as exc:  # noqa: BLE001 —— 讀不到目前待確認的帳號 ＝ 無法證明畫面上那個還是它，不確認
            _LOG.warning("設定頁確認前讀登入狀態失敗：%s", type(exc).__name__)
            return
        shown = displayed_email.strip() if isinstance(displayed_email, str) else ""
        if not (isinstance(current, dict) and current.get("login_state") == "pending_login" and shown
                and current.get("pending_login_email") == shown):
            return
        result = personal_session.confirm_login(state)
    elif action == "reject":
        result = personal_session.reject_login(state)
    elif action == "logout":
        state.pop(_KEY_SWITCH_ASK, None)
        result = personal_session.logout(state)
    elif action == "switch_go":
        if not state.pop(_KEY_SWITCH_ASK, None):
            return
        result = personal_session.switch_account(state)   # 先登出（清 Active／Pending），再開始新授權；回到未登入畫面
    else:
        return
    if result.get("ok") is not True:
        state[_KEY_NOTICE] = result.get("error_code")


login_live = {"load": login_load, "act": login_act}
