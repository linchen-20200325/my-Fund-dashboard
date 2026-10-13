# -*- coding: utf-8 -*-
"""標的探索的正式資料來源：呼叫 L2 `services/v2_tables`，組出與 fixtures 同形的 dataset。

依據 docs/v2/49_data_integration_plan.md §3.3 方案 A（`source.py` 那一列）、`ACCEPTANCE.md` 七（失敗訊息遮蔽），
以及客戶 2026-10-13 裁示（B 線標的探索正式模式第一批 —— 骨架＋設定存讀＋母體代碼）：
- **只由 `ui_v2/app_exp_live.py`（與預覽入口 `ui_v2/app_preview.py`）import**；`page.py` 不 import 本檔 ——
  本檔經 L2 會連到舊樹 L1（及其 gspread 等相依），`page.py` 一旦 import 本檔，缺那些套件的驗收環境
  會在 import 階段就失敗（體例同 mkt／alo）。
- 本檔不 import fixtures；不放任何快取（快取只在 L1，`49` §4.4）；不直接發任何網路請求，一律經 L2。
- **秘密值在本層讀**（`st.secrets`、環境變數、登入後的 OAuth 權杖），交給 L2；本層交給畫面的每一個失敗字串都已遮蔽。
- 解析與判定一律住在 `live.py`（純函式）；本檔只負責「去拿」與「收錯誤」。

`load_live()` 回傳 `{"dataset": ..., "notes": ...}`：
- `dataset`：與 `fixtures.scenario()["dataset"]` 同形（`live.build_dataset`）。
  母體＝選股池的基金代碼（L2 `exp_universe.load_pool_codes`；**只取代碼**），其餘欄一律空（⬜）。
- `notes`：`pool`（L2 回傳原樣：狀態、後端、代碼、略過與重複的筆數、訊息）、
  `settings`（已存的 `exp_` 四鍵，`live.parse_user_settings` 解析後）、
  `settings_error`（讀不到或解析不了時的訊息原文，已遮蔽；讀得到時為 None —— **與「沒設定」分開**）。

`save_setting(鍵, 值或 None, value_kind)` → L2 `save_setting_for_page` 的回傳（純 dict，訊息已遮蔽）；
體例與 `ui_v2/mkt/source.py::save_setting` 相同。
客戶 2026-10-13 裁示：存檔成功只更新已存值；正式結果只讀已存值，下一次重新載入（rerun 重新讀 `user_setting`）生效。
"""

from __future__ import annotations

import os

import streamlit as st

from services.v2_tables import exp_universe, masking, settings_store

from . import live


def _secret_values() -> list:
    """從 `st.secrets`、環境變數與登入權杖讀出 ACCEPTANCE 7.2 列名鍵的值。"""
    return masking.secret_values(
        [st.secrets, os.environ],
        oauth_tokens=st.session_state.get("gsheet_tokens"),
        custom_oauth_cfg=st.session_state.get("custom_oauth_cfg"),
    )


def load_live() -> dict:
    """給 `page.render(load_live=...)` 用的載入函式。"""
    values = _secret_values()
    # ⚠️ `oauth_client` 恆為 None：取登入者 gspread client 的現有函式住在舊樹 `ui/`，ui_v2 不得 import。
    #    ⇒ 只有服務帳戶一條路；沒有服務帳戶時 L2 回「選股池未設定雲端來源」（不讀本機暫存檔當母體）。
    pool = exp_universe.load_pool_codes(values, oauth_client=None)
    settings, settings_error = _load_settings(values)
    return {
        "dataset": live.build_dataset(pool, settings),
        "notes": {"pool": pool, "settings": settings, "settings_error": settings_error},
    }


def _load_settings(values) -> tuple:
    """讀已存的 `exp_` 四鍵。讀不到（`SettingsSheetError`，訊息已由 L1 經 L2 遮過）→ (全 None, 訊息)。
    分頁不存在（`tab_missing`）＝尚無資料（L1 docstring），不是錯誤 → 四鍵皆未設定。"""
    try:
        loaded = settings_store.load_user_settings(values)
    except settings_store.SettingsSheetError as exc:
        return dict(live.EMPTY_SETTINGS), str(exc)
    return live.parse_user_settings(loaded["rows"], loaded["broken_keys"])


def save_setting(setting_key, setting_value, value_kind) -> dict:
    """給 `page.render(save_live=...)` 用：存一個鍵（L2 先檢查值與型別，不符不存）。"""
    return settings_store.save_setting_for_page(setting_key, setting_value, value_kind, _secret_values())
