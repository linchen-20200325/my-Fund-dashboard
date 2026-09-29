# -*- coding: utf-8 -*-
"""資產配置的正式資料來源：呼叫 L2 `services/v2_tables`，組出與 fixtures 同形的 dataset。

依據 docs/v2/49_data_integration_plan.md §3.3 方案 A（`source.py` 那一列）、
`ACCEPTANCE.md` 七（失敗訊息遮蔽），以及 2026-09-28 客戶核准的 `docs/wireframes/draft_alo_live.html`：
- **只由 `ui_v2/app_alo_live.py` import**；`page.py` 不 import 本檔（體例同 `ui_v2/set/source.py`）——
  本檔經 L2 會連到舊樹 L1 及其相依（`bs4`／`gspread` 等），`page.py` 一旦 import 本檔，
  缺那些套件的驗收環境會在 import 階段就失敗。
- 本檔不 import fixtures；不放任何快取（快取只在 L1，`49` §4.4）；不直接發任何網路請求，一律經 L2。
- **秘密值在本層讀**（`st.secrets`、環境變數、登入後的 OAuth 權杖），交給 L2；遮蔽由 L2 接到 L1、
  在寫出點做一次。本層交給畫面的每一個失敗字串都已遮蔽。
- 解析與判定一律住在 `live.py`（純函式，沒有 streamlit 也測得動）；本檔只負責「去拿」與「收錯誤」。

`load_live()` 回傳 `{"dataset": ..., "notes": ...}`：

- `dataset`：與 `fixtures.scenario()` 同形（`holding`、`nav`、`policy`、`market_indicator`、
  `user_setting`、`errors`、`save_errors`）。
  - `nav` **尚未接上**（L2 `settings_store.PENDING_TABLES` 列了 `nav`、`dividend`）→ 空列表、
    **不進 `errors`**（那是「還沒接」，不是「讀失敗」；體例同 `ui_v2/set/source.py`）。
    ⇒ 使用者在 ALO-4 把比重基準切到「市值」時，每一檔都缺基準值，畫面照 `44` 5.5 顯示
    `⬜ 資料未備`、ALO-6 表尾照算「缺基準值被排除的檔數」。**這是 `CLAUDE.md` §1 Fail Loud，不是 bug**：
    不把市值選項灰掉、不填 0、不拿成本值頂替、不靜默退回成本。
  - `market_indicator` 讀的是**已寫在試算表上的那一份**（`settings_store.load_market_indicator`），
    不觸發任何取數 —— 本頁是消費端，不是取數端。本頁只用得到 `fx_twd_per_usd` 那一個鍵，
    而它目前在 L2 是暫停取數的（`market_indicator.FX_OBS_DATE_RULE_VERIFIED` 為假），
    所以表上通常沒有那一列 ⇒ 市值基準會缺匯率，同樣照實顯示。
  - `save_errors` 恆為空 dict：**本輪只接讀、不接寫**（寫入端按鈕由 `live.apply_live_notes` 停用）。
- `notes`：本輪畫面**都用不到**，原樣轉交給下一輪（草稿 §D 的七件新東西）用 ——
  `mask_token`、`pending_tables`、`pages_reading_settings`、`read_estimate`（L1 的讀取量診斷）、
  `direct`／`warnings`（U9 的 DIRECT 列與逐筆警示）、`skipped`（沒寫進持倉的各種原因）、
  `setting_structure`（`user_setting` 的壞列與解析不了的鍵）。
"""

from __future__ import annotations

import os

import streamlit as st

from services.v2_tables import alo_holdings, masking, settings_store

from . import live

# `load_alo_tables` 回傳裡屬於「沒寫進持倉的列」那一組（草稿 D3）。本輪原樣轉交，不判讀、不歸納。
_SKIP_GROUPS = (
    "skipped_holdings",
    "missing_supplement",
    "duplicate_supplement",
    "orphan_supplement",
    "supplement_of_skipped",
    "supplement_unjudged",
    "missing_profile",
    "duplicate_profile",
    "orphan_profile",
    "profile_of_skipped",
    "profile_unjudged",
    "bad_rows",
    "blank_rows",
    "tab_missing",
    "skipped_tabs",
    "invest_twd_parse_errors",
)


def _secret_values() -> list:
    """從 `st.secrets`、環境變數與登入權杖讀出 ACCEPTANCE 7.2 列名鍵的值（同 mkt、set）。"""
    return masking.secret_values(
        [st.secrets, os.environ],
        oauth_tokens=st.session_state.get("gsheet_tokens"),
        custom_oauth_cfg=st.session_state.get("custom_oauth_cfg"),
    )


def load_live() -> dict:
    """給 `page.render(load_live=...)` 用的載入函式。三個來源逐一讀、逐一收錯誤，一個壞不拖垮其餘。"""
    values = _secret_values()
    errors, notes = {}, {}

    # ── holding ＋ policy：同一次呼叫的產物（見 live.tables_failed_together 的說明）──
    try:
        tables = alo_holdings.load_alo_tables(values)
    except alo_holdings.PolicySupplementError as exc:
        tables = None
        errors.update(live.tables_failed_together(str(exc)))   # 已由 L1 經 L2 的 mask 遮過

    # ── user_setting ──
    try:
        settings = settings_store.load_user_settings(values)
    except settings_store.SettingsSheetError as exc:
        settings = None
        errors["user_setting"] = str(exc)

    # ── market_indicator（只讀表，不取數）──
    try:
        indicators = settings_store.load_market_indicator(values)
    except settings_store.SettingsSheetError as exc:
        indicators = None
        errors["market_indicator"] = str(exc)

    setting_rows = []
    if settings is not None:
        setting_rows, problem = live.parse_user_settings(settings["rows"], settings["broken_keys"])
        if problem is not None:
            # 讀得到表、值卻不是本頁吃得下的形狀 → 當成 user_setting 這張表沒能交出可用的值。
            # 照 fixtures 的 `settingfail` 形狀：值一律不交出去，由各塊自己畫失敗框，
            # **不把它畫成「尚未設定」**（那是造假，§1）。
            errors["user_setting"] = problem
            setting_rows = []
        notes["setting_structure"] = {
            "bad_rows": len(settings["bad_rows"]),
            "broken_keys": list(settings["broken_keys"]),
        }

    dataset = {
        "holding": [dict(row) for row in tables["holding"]] if tables else [],
        "nav": [],                      # PENDING_TABLES：還沒接上，不是讀失敗
        "policy": [dict(row) for row in tables["policy"]] if tables else [],
        "market_indicator": [dict(row) for row in indicators["rows"]] if indicators else [],
        "user_setting": setting_rows,
        "errors": errors,
        "save_errors": {},              # 本輪不接寫
    }
    notes.update(
        mask_token=masking.MASK,
        pending_tables=list(settings_store.PENDING_TABLES),
        pages_reading_settings=list(settings_store.PAGES_READING_SETTINGS),
        read_estimate=(tables or {}).get("read_estimate"),
        direct=list((tables or {}).get("direct") or ()),
        warnings=list((tables or {}).get("warnings") or ()),
        skipped={name: (tables or {}).get(name) for name in _SKIP_GROUPS} if tables else {},
    )
    return {"dataset": dataset, "notes": notes}
