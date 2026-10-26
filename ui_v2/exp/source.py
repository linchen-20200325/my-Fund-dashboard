# -*- coding: utf-8 -*-
"""標的探索的正式資料來源：呼叫 L2 `services/v2_tables`，組出與 fixtures 同形的 dataset。

依據 docs/v2/49_data_integration_plan.md §3.3 方案 A（`source.py` 那一列）、`ACCEPTANCE.md` 七（失敗訊息遮蔽），
以及客戶 2026-10-13 裁示（B 線標的探索正式模式第一批 —— 骨架＋設定存讀＋母體代碼）：
- **只由 `ui_v2/app_exp_live.py`（與預覽入口 `ui_v2/app_preview.py`）import**；`page.py` 不 import 本檔 ——
  本檔經 L2 會連到舊樹 L1（及其 gspread 等相依），`page.py` 一旦 import 本檔，缺那些套件的驗收環境
  會在 import 階段就失敗（體例同 mkt／alo）。
- 本檔不 import fixtures；不放任何快取（~~快取只在 L1，`49` §4.4~~ → 2026-10-13 第二輪複驗更正（有意識的更正，
  不是漏刪；決策者：AI 總管）：**選股池代碼的快取在 L2 `exp_universe`**（L1 `list_pool` 沒有快取、本批不動 L1；
  偏離已登記在 `49` 第三節第 3 步）；本檔照舊不放任何快取）；不直接發任何網路請求，一律經 L2。
- **秘密值在本層讀**（`st.secrets`、環境變數、登入後的 OAuth 權杖），交給 L2；本層交給畫面的每一個失敗字串都已遮蔽。
- 解析與判定一律住在 `live.py`（純函式）；本檔只負責「去拿」與「收錯誤」。

`load_live()` 回傳 `{"dataset": ..., "notes": ...}`：
- `dataset`：與 `fixtures.scenario()["dataset"]` 同形（`live.build_dataset`）。
  母體＝選股池的基金代碼（L2 `exp_universe.load_pool_codes`；**只取代碼**）。
  ~~其餘欄一律空（⬜）~~ → 2026-10-14 C2 接線（狀態更新，不是漏刪）：基本資料來自 L2 `exp_profile`，
  淨值與配息來自 L2 `exp_nav`（只取 `EXP-2` 會列出的檔），見 `_load_funds`。
- `notes`：`pool`（L2 回傳原樣：狀態、後端、代碼、略過與重複的筆數、訊息）、
  `settings`（已存的 `exp_` 四鍵，`live.parse_user_settings` 解析後）、
  `settings_error`（讀不到或解析不了時的訊息原文，已遮蔽；讀得到時為 None —— **與「沒設定」分開**）。
  `cells`（2026-10-14 C2）：逐格的原因與來源標示（`live.assemble_wired`，已遮蔽）；母體讀不到時為 None。

`save_setting(鍵, 值或 None, value_kind)` → L2 `save_setting_for_page` 的回傳（純 dict，訊息已遮蔽）；
體例與 `ui_v2/mkt/source.py::save_setting` 相同。
客戶 2026-10-13 裁示：存檔成功只更新已存值；正式結果只讀已存值，下一次重新載入（rerun 重新讀 `user_setting`）生效。
"""

from __future__ import annotations

import logging
import os
import traceback
from datetime import datetime

import streamlit as st

from services.v2_tables import exp_nav, exp_profile, exp_universe, fund_keys, masking, nav_dividend, settings_store

from . import live

_LOG = logging.getLogger(__name__)

# 淨值被扣下、畫面印「⬜ 資料未備」的代碼 → 固定文字（None ＝ 用資料層的 `skipped` 原文）。封閉清單，體例同
# `ui_v2/hld/source.py::_NAV_UNAVAILABLE_WITHHELD`；⛔ 刻意不含 `WITHHELD_INPUT_CONFLICT`（契約被破壞 → raise）。
# `ccy_undetermined`（2026-10-14 C2）：計價幣別未確定的檔，資料層不取數。~~畫面寫 `exp_nav.TEXT_CCY_UNDETERMINED`~~
# → 2026-10-14 修正輪（有意識的更正，不是漏刪；決策者：AI 總管）：那一句含內部名稱 `declared_ccy_source`，
#   畫面改寫 `live.TEXT_CCY_UNDETERMINED`（白話）；L2 原文照舊留在 `skipped`。
# `ccy_conflict`：基本資料幣別與淨值資料幣別衝突（規則 14），原因用資料層的原文（含兩邊的幣別）。
_NAV_UNAVAILABLE_WITHHELD = {
    nav_dividend.WITHHELD_CCY_MISSING: None,
    nav_dividend.WITHHELD_CCY_CONFLICT: None,
    nav_dividend.WITHHELD_FETCHED_AT_MISSING: None,
    nav_dividend.WITHHELD_FETCHED_AT_FUTURE: None,
    exp_nav.WITHHELD_CCY_UNDETERMINED: live.TEXT_CCY_UNDETERMINED,
}


def _secret_values() -> list:
    """從 `st.secrets`、環境變數與登入權杖讀出 ACCEPTANCE 7.2 列名鍵的值。"""
    return masking.secret_values(
        [st.secrets, os.environ],
        oauth_tokens=st.session_state.get("gsheet_tokens"),
        custom_oauth_cfg=st.session_state.get("custom_oauth_cfg"),
        session_state=st.session_state,   # 個人 Google 登入權杖（`b_oauth.tokens`）也遮；經 L2 `masking`，本頁不碰 infra／shared
    )


def mask_error(message: str) -> str:
    """給 `page.render(mask_error=...)`：整頁載入失敗時的訊息原文經遮蔽，才收進設定與診斷頁的進階診斷
    （Phase 3 P1-⑤，BL-0362；同 `ui_v2/hld/source.py::mask_error`）。"""
    return masking.mask_message(message, _secret_values())


def load_live() -> dict:
    """給 `page.render(load_live=...)` 用的載入函式。"""
    values = _secret_values()
    # ⚠️ `oauth_client` 恆為 None：取登入者 gspread client 的現有函式住在舊樹 `ui/`，ui_v2 不得 import。
    #    ⇒ 只有服務帳戶一條路；沒有服務帳戶時 L2 回「選股池未設定雲端來源」（不讀本機暫存檔當母體）。
    pool = exp_universe.load_pool_codes(values, oauth_client=None)
    settings, settings_error = _load_settings(values)
    wired = None
    if pool["status"] == "ok":
        wired = _load_funds(pool["codes"], settings, settings_error, values)
    return {
        "dataset": live.build_dataset(pool, settings, wired),
        "notes": {"pool": pool, "settings": settings, "settings_error": settings_error,
                  "cells": None if wired is None else wired["cells"],
                  "wiring_error": None if wired is None else wired["errors"].get("fund_profile")},
    }


def _load_funds(codes, settings, settings_error, values) -> dict:
    """C2 接線（2026-10-14）：兩段取數 —— 先基本資料（全部母體），再只對 `EXP-2` 會列出的檔取淨值與配息。

    - 基本資料：`fund_keys.resolve_full_keys` → `exp_profile.build_profiles`（三來源；L1 例外已在 L2 收成 failed）。
    - 淨值：`live.nav_codes_needed`（已存條件篩完的名單）→ `exp_nav.load_nav_dividend`，傳 `declared_ccy` 與
      `declared_ccy_source`（幣別未確定者傳 None，資料層隔離成 `ccy_undetermined`）。
    - 代碼對照表讀不到（L1 例外，`fund_keys` 不攔）→ 整批 ⛔ 取數失敗（訊息遮蔽後上畫面，不吞）。
    - 每一格的原因與來源標示在 `live.assemble_wired` 統一遮蔽（本層交 `mask`）。
    """
    mask = lambda text: masking.mask_message(text, values)  # noqa: E731
    # 同一個當下時刻餵給基本資料、淨值與畫面的「台灣今天」（三處判同一天，測試可重現）。
    now = datetime.now(live.TAIPEI)
    # ~~try「只包住讀取本身（L1 例外 fund_keys 不攔）」~~ → 2026-10-15 #966 修正輪 3 據實更正（稽核 B 複驗；有意識的更正，
    # 不是漏刪；決策者：AI 總管；只改註解、行為不變）：try 包住的是**整支** `fund_keys.resolve_full_keys` —— 讀對照表
    # （L1 例外 fund_keys 不攔）之外，還有逐檔的 `_resolve_one`。所以逐檔解析的程式錯誤也會落到下面這個 except，
    # 被歸為「代碼對照表讀取失敗」：畫面整批 ⛔（遮蔽後原文）、log 附遮蔽後的 traceback（可據以定位到出錯那一行），
    # 不是吞錯。**歸類不精確屬已知限制，已登記**；本輪刻意不縮 try 範圍（避免行為變更）。
    try:
        resolved = fund_keys.resolve_full_keys(list(codes))
    except Exception as exc:  # noqa: BLE001 —— 轉成畫面上的 ⛔ 取數失敗（遮蔽後原文）並記 log，不是吞掉
        message = mask(f"代碼對照表讀取失敗：{type(exc).__name__}: {exc}")
        # ~~`_LOG.error(..., message)`（沒有 traceback）~~ → 2026-10-15 #966 修正輪 3（獨立稽核小修；有意識的更正，
        # 不是漏刪；決策者：AI 總管）：補上 traceback，查錯才找得到出錯的那一行。
        # ⚠️ 刻意不用 `_LOG.exception`／`exc_info=True`：那會把**未遮蔽**的例外原文（可能含秘密值）原樣寫進 log
        # （ACCEPTANCE 七）；改成自己格式化 traceback、先遮蔽再寫。~~try 只包住讀取本身（範圍不變）。~~
        # → 同日據實更正（有意識的更正，不是漏刪）：try 範圍本輪未變，但它涵蓋整支 `resolve_full_keys`（含逐檔解析），
        # 不只讀取本身；見上方 try 前的註解。
        trace = mask("".join(traceback.format_exception(exc)))
        _LOG.error("exp 代碼對照表讀取失敗，整批不取數：%s\n%s", message, trace)
        return live.wiring_failed(message)
    key_results = resolved["results"]                           # 契約取值不在 try 裡：形狀錯誤照常 raise
    # #965 已合併（main 0805bcb）：`build_profiles` 有 `now` 參數，直接傳同一個 `now`
    # （~~以簽章判斷、相容兩版~~ 已收掉；有意識的更正，不是漏刪）。
    profiles = exp_profile.build_profiles(key_results, now=now)
    needed = live.nav_codes_needed(profiles["rows"], settings, settings_error)
    funds, unresolved = live.nav_requests(needed, key_results, profiles["declared"])
    nav_out = exp_nav.load_nav_dividend(funds, now=now) if funds else None
    return live.assemble_wired(
        profiles, needed, nav_out,
        unresolved=unresolved,
        today=now.date(),
        mask=mask,
        withheld_texts=_NAV_UNAVAILABLE_WITHHELD,
        input_conflict=nav_dividend.WITHHELD_INPUT_CONFLICT,
        div_ccy_differs=nav_dividend.WITHHELD_DIV_CCY_DIFFERS,
    )


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
