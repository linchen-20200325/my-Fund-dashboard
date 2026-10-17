# -*- coding: utf-8 -*-
"""市場總覽的正式資料來源：呼叫 L2 `services/v2_tables`，組出與 fixtures 同形的 dataset。

依據 docs/v2/49_data_integration_plan.md §3.3 方案 A（`source.py` 那一列）與
`ACCEPTANCE.md` 七（失敗訊息遮蔽，客戶 2026-09-26 裁示 Q13）：
- **只由 `ui_v2/app_mkt_live.py` import**；`page.py` 不 import 本檔 —— 本檔經 L2 會連到
  舊樹 L1（及其 streamlit、bs4 等相依），`page.py` 一旦 import 本檔，缺那些套件的驗收環境
  會在 import 階段就失敗。
- 本檔不 import fixtures；不放任何快取（快取只在 L1，49 §4.4）；不發任何網路請求。
- **秘密值在本層讀**（`st.secrets`、環境變數、登入後的 OAuth 權杖），交給 L2 的遮蔽函式；
  遮蔽在這裡做一次（畫面的寫出點），L2 本身不讀任何秘密值、不 import streamlit。

`load_live()` 回傳：
- `dataset`：與 `fixtures.dataset_*()` 同形的 `{"rows": [...], "errors": {...}}`，errors 已遮蔽；
- `notes`：正式模式畫面要用的附註 ——
  `pending`（不寫列的鍵 → 原因代碼）、`masked_keys`（錯誤原文含遮蔽記號的鍵）、
  `cooldowns`（本頁來源的冷卻狀態）、
  `available_keys`（MKT-5 可勾清單：L2 `INDICATOR_SPECS` 裡**第一階段會取數**的鍵，見 `available_keys()`；
  客戶 2026-10-13 裁示「資料層實際可取得、可追溯」，此為總管依裁示的實作解讀）、
  `settings`（**已存**的 `mkt_` 三鍵，經 `live.parse_user_settings` 解析）、
  `settings_error`（讀不到或解析不了時的訊息原文，已遮蔽；讀得到時為 None）。

`save_setting(鍵, 值或 None, value_kind)` → L2 `save_setting_for_page` 的回傳（純 dict，訊息已遮蔽）；
體例與 `ui_v2/alo/source.py::save_setting` 相同（同一個 L2 函式、同一份秘密值）。
客戶 2026-10-13 裁示：存檔成功只更新已存值；正式結果只讀已存值，下一次重新載入（rerun 重新讀 `user_setting`）生效。
"""

from __future__ import annotations

import os

import streamlit as st

from services.v2_tables import market_indicator, masking, settings_store

from . import live


def _secret_values() -> list:
    """從 `st.secrets`、環境變數與登入權杖讀出 ACCEPTANCE 7.2 列名鍵的值。"""
    return masking.secret_values(
        [st.secrets, os.environ],
        oauth_tokens=st.session_state.get("gsheet_tokens"),
        custom_oauth_cfg=st.session_state.get("custom_oauth_cfg"),
    )


def mask_error(message: str) -> str:
    """給 `page.render(mask_error=...)`：整頁載入失敗時的訊息原文經遮蔽，才收進設定與診斷頁的進階診斷
    （Phase 3 P1-⑤，BL-0362；同 `ui_v2/hld/source.py::mask_error`）。"""
    return masking.mask_message(message, _secret_values())


def _fred_api_key() -> str:
    """FRED 三鍵的金鑰（2026-10-13 起）：`st.secrets` 優先、環境變數其次（同 `app.py::_load_keys` 的鏡像方向）。
    讀不到回空字串，由 L2 寫成「未設定 FRED_API_KEY」的取數失敗（49 §4.1），本層不補任何值。"""
    return market_indicator.fred_api_key_from([st.secrets, os.environ])


def load_live() -> dict:
    """給 `page.render(load_live=...)` 用的載入函式。"""
    table = market_indicator.build_market_indicator_table(fred_api_key=_fred_api_key())
    values = _secret_values()
    errors = {key: masking.mask_message(message, values)
              for key, message in table["errors"].items()}
    settings, settings_error = _load_settings(values)
    return {
        "dataset": {
            "rows": [dict(row) for row in table["rows"]],
            "errors": errors,
        },
        "notes": {
            "pending": dict(table["pending"]),
            "masked_keys": sorted(k for k, m in errors.items() if masking.is_masked(m)),
            "cooldowns": market_indicator.source_cooldowns(),
            "available_keys": available_keys(table),
            "settings": settings,
            "settings_error": settings_error,
        },
    }


def available_keys(table) -> list:
    """MKT-5 可勾清單（N3，2026-10-13 稽核 G，總管裁定）：資料層註冊的鍵，排除 L2 本次交回的 `pending`
    （第一階段刻意不取數、不寫列的鍵 —— `phase1` 為 `pending`，或 FX 觀測日規則未驗證時的
    `write_if_fx_verified`）。判定一律取 L2 自己交出的旗標，本層不寫死任何鍵名。
    ~~舊寫法：`list(market_indicator.INDICATOR_SPECS)`（七鍵全列）~~ —— 那會讓第一階段不可能有資料的鍵
    成為可勾選項，不合「實際可取得」。"""
    pending = set(table.get("pending") or {})
    return [key for key in market_indicator.INDICATOR_SPECS if key not in pending]


def _load_settings(values) -> tuple:
    """讀已存的 `mkt_` 三鍵。讀不到（`SettingsSheetError`，訊息已由 L1 經 L2 遮過）→ (全 None, 訊息)。
    分頁不存在（`tab_missing`）＝尚無資料，不是錯誤（L1 docstring）→ 三鍵皆未設定。"""
    try:
        loaded = settings_store.load_user_settings(values)
    except settings_store.SettingsSheetError as exc:
        return {"window_days": None, "baseline_date": None, "indicator_keys": None, "pair_consistent": None}, str(exc)
    return live.parse_user_settings(loaded["rows"], loaded["broken_keys"])


def save_setting(setting_key, setting_value, value_kind) -> dict:
    """給 `page.render(save_live=...)` 用：存一個鍵（L2 先檢查值與型別，不符不存）。"""
    return settings_store.save_setting_for_page(setting_key, setting_value, value_kind, _secret_values())
