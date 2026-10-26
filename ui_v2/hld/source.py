# -*- coding: utf-8 -*-
"""持倉體檢的正式資料來源：呼叫 L2 `services/v2_tables`，交給 `live.assemble_live_load` 組成 `load_live` 回傳值。

體例同 `ui_v2/alo/source.py`：
- **只由 `ui_v2/app_hld_live.py` import**；`page.py` 不 import 本檔（本檔經 L2 會連到舊樹 L1 及其相依）。
- 本檔不 import fixtures；不放任何快取；不直接發任何網路請求，一律經 L2。
- 秘密值在本層讀，交給 L2；本層交給畫面的每一個失敗字串都經遮蔽。
- 判定與組裝一律住在 `live.py`（純函式）；本檔只負責「去拿」、「收錯誤」與「組 L2 輸入」。
  L2 常數一律在這裡以參數注入（`live.py` 不得 import services）。

組 L2 輸入（`build_nav_table` 的 funds）三條（hld S6b-2 留給 S6b-3 的陷阱）：
1. 每一筆持倉列對應一筆，帶 `holding_ccy`（漏傳 ⇒ 每一檔被扣成 `ccy_missing`）；
2. **不去重**（去重會吃掉 `ccy_conflict`）；
3. 只放代碼對照 `ok is True` 的檔（`ok is False` 的檔以 `full_key=None` 交出會整頁報錯）。

`resolve_full_keys` 的 L1 例外不在這裡攔：交給 `page.render` 的 try 畫錯誤畫面（不印 Traceback）。
"""

from __future__ import annotations

import os

import streamlit as st

from services.v2_tables import alo_holdings, contract, fund_keys, masking, nav_dividend, settings_store

from .. import active_gate
from . import live

# 淨值被扣下、畫面印「⬜ 資料未備」的四碼。⛔ 刻意不含 `WITHHELD_INPUT_CONFLICT`（契約被破壞 → raise）。
_NAV_UNAVAILABLE_WITHHELD = frozenset({
    nav_dividend.WITHHELD_CCY_MISSING,
    nav_dividend.WITHHELD_CCY_CONFLICT,
    nav_dividend.WITHHELD_FETCHED_AT_MISSING,
    nav_dividend.WITHHELD_FETCHED_AT_FUTURE,
})


def _secret_values() -> list:
    """從 `st.secrets`、環境變數與登入權杖讀出 ACCEPTANCE 7.2 列名鍵的值（同 alo）。"""
    return masking.secret_values(
        [st.secrets, os.environ],
        oauth_tokens=st.session_state.get("gsheet_tokens"),
        custom_oauth_cfg=st.session_state.get("custom_oauth_cfg"),
        session_state=st.session_state,   # 個人 Google 登入權杖（`b_oauth.tokens`）也遮；經 L2 `masking`，本頁不碰 infra／shared
    )


def mask_error(message: str) -> str:
    """給 `page.render(mask_error=...)`：錯誤畫面上的訊息原文經遮蔽才上畫面。"""
    return masking.mask_message(message, _secret_values())


def load_live() -> dict:
    """給 `page.render(load_live=...)` 用的載入函式。回傳 `{"dataset", "live_args"}`（`live.assemble_live_load`）。"""
    values = _secret_values()
    mask = alo_holdings.masker(values)

    tables = holding_error = key_results = nav_table = dividend_table = None
    try:
        # 批 3b-4（客戶 2026-10-26 J-7／J-13）：持倉原始表只讀使用者的 Active Sheet（個人 Google 帳號、唯讀），
        # 不再讀 `POLICY_SHEET_ID`／服務帳戶，沒有任何 fallback。判定與計算（`build_alo_tables` 以下）一個字未動。
        tables = alo_holdings.load_alo_tables_active(st.session_state, values)
    except alo_holdings.ActiveSourceError as exc:
        if active_gate.is_no_active(exc.code, exc.reason):
            raise active_gate.NoActiveSource(exc.code) from None   # 沒有 Active：整頁「⬜ 尚未選定持倉資料來源」，不是錯誤
        holding_error = mask(active_gate.failure_text(exc.code, exc.reason))   # 其餘九 code 之一：走既有持倉讀取失敗路徑

    settings = settings_error = None
    try:
        settings = settings_store.load_user_settings(values)
    except settings_store.SettingsSheetError as exc:
        settings_error = mask(str(exc))

    if tables is not None:
        holding = tables["holding"]
        key_results = fund_keys.resolve_full_keys([h["fund_code"] for h in holding])["results"]
        resolved = {r["input"]: r for r in key_results if r["ok"] is True}
        # 2026-10-13（客戶同日裁示：B 線配息沿用 A 鏈；只改接線）：~~`build_nav_table`~~ → `build_nav_dividend_tables`，
        # 同一次 A 鏈呼叫交出淨值與配息（不另外發請求）；淨值那一半與 `build_nav_table` 逐鍵相同。
        both = nav_dividend.build_nav_dividend_tables([
            {
                "fund_code": h["fund_code"],
                "full_key": resolved[h["fund_code"]]["full_key"],
                "portal": resolved[h["fund_code"]]["portal"],
                # 2026-10-13：淨值走 A 鏈，交查表前的代碼（A 鏈自己查對照表）；只改接線。
                "chain_code": resolved[h["fund_code"]]["parsed_code"],
                "holding_ccy": h["ccy"],
            }
            for h in holding if h["fund_code"] in resolved
        ])
        nav_table, dividend_table = both["nav"], both["dividend"]

    return live.assemble_live_load(
        holding_tables=tables,
        holding_error=holding_error,
        settings=settings,
        settings_error=settings_error,
        key_results=key_results,
        nav_table=nav_table,
        direct_policy_id=contract.DIRECT_POLICY_ID,
        policy_tab_source=alo_holdings.POLICY_TAB,
        direct_sources=frozenset({alo_holdings.POLICY_TAB, alo_holdings.TAB_PROFILE, alo_holdings.TAB_SUPPLEMENT}),
        empty_without_reason=nav_dividend.EMPTY_WITHOUT_REASON,
        nav_unavailable_withheld=_NAV_UNAVAILABLE_WITHHELD,
        dividend_gate_open=nav_dividend.DIV_DATE_IS_EX_DATE_VERIFIED,
        mask=mask,
        dividend_table=dividend_table,
    )


def save_setting(setting_key, setting_value, value_kind) -> dict:
    """給 `page.render(save_live=...)` 用：存一個鍵（L2 先檢查值與型別，不符不存）。客戶 2026-10-16 裁示第 2 點。
    體例與 `ui_v2/mkt/source.py::save_setting`、`ui_v2/alo/source.py::save_setting` 相同（同一個 L2 函式、同一份秘密值）；
    不新增資料來源。回 L2 `save_setting_for_page` 的純 dict（訊息已遮蔽）。"""
    return settings_store.save_setting_for_page(setting_key, setting_value, value_kind, _secret_values())
