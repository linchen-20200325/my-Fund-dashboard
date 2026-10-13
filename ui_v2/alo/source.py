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
  - ~~`nav` **尚未接上**（L2 `settings_store.PENDING_TABLES` 列了 `nav`、`dividend`）→ 空列表、
    **不進 `errors`**（那是「還沒接」，不是「讀失敗」；體例同 `ui_v2/set/source.py`）。~~
    → 2026-10-09 狀態更新（不是漏刪）：客戶裁示 Q1 不存 NAV、各頁需要時即時抓取，L2 已把 `nav` 移出
    `PENDING_TABLES`；但**本頁取淨值未獲授權**（裁示只到 hld 與 set），所以 `nav` 照舊是空列表、
    **不進 `errors`**（本頁沒有去取，不是讀失敗）。
    ⇒ 使用者在 ALO-4 把比重基準切到「市值」時，每一檔都缺基準值，畫面照 `44` 5.5 顯示
    `⬜ 資料未備`、ALO-6 表尾照算「缺基準值被排除的檔數」。**這是 `CLAUDE.md` §1 Fail Loud，不是 bug**：
    不把市值選項灰掉、不填 0、不拿成本值頂替、不靜默退回成本。
    → **2026-10-13 狀態更新（有意識的變更，不是漏刪；依據：客戶 2026-10-13 裁示「B 線 `ui_v2/` 是唯一正式 UI，
    切換前資產配置必須是真資料」＋ 核准 B 線復用既有多來源淨值鏈）**：已存基準為「市值」時，本頁經 L2
    `nav_dividend.build_nav_table`（A 鏈，與 hld 同一個入口、同一套組輸入規則）取淨值；判讀在
    `live.assemble_nav`（扣下、對照失敗、來源回空 → 那一檔資料未備；其餘取數失敗 → `errors["nav"]`，原文經遮蔽）。
    成本基準不取（用不到）。上面三段舊句寫下時為真（當時未獲授權）；被推翻的是它的前提。
    非美元幣別的匯率依 49 §6.1 Q9 經 L2 `market_indicator.build_fx_indicator_table` 取，與美元同一個閘門
    （`FX_OBS_DATE_RULE_VERIFIED` 為假時不取數、不寫列 ⇒ 該類別「⬜ 資料未備：缺換算匯率 <鍵>」），
    閘門狀態放在 `notes["fx_pending"]`。
  - `market_indicator` 讀的是**已寫在試算表上的那一份**（`settings_store.load_market_indicator`），
    不觸發任何取數 —— 本頁是消費端，不是取數端。本頁只用得到 `fx_twd_per_usd` 那一個鍵，
    而它目前在 L2 是暫停取數的（`market_indicator.FX_OBS_DATE_RULE_VERIFIED` 為假），
    所以表上通常沒有那一列 ⇒ 市值基準會缺匯率，同樣照實顯示。
    （2026-10-13 補：非美元幣別的匯率鍵不在試算表上，由本頁經 L2 `build_fx_indicator_table` 取、併在後面；
    美元仍只讀試算表那一份 —— 「只用得到 `fx_twd_per_usd` 那一個鍵」自此不再為真，但美元那一半不變。）
  - `save_errors` 本函式一律回空 dict：~~本輪只接讀、不接寫~~ → 2026-10-09 起 ALO-1／ALO-4 接上寫入
    （`save_setting`），但存檔成敗是**按鈕那一次**的事、不是讀表的結果，由 `page.py` 記在 session、
    重繪時再併進 `save_errors`；本函式不碰它。
- `notes`：畫面**都用不到**，原樣轉交給下一輪（草稿 §D 的七件新東西）用 ——
  `mask_token`、`pending_tables`、`pages_reading_settings`、`read_estimate`（L1 的讀取量診斷）、
  `direct`／`warnings`（U9 的 DIRECT 列與逐筆警示）、`skipped`（沒寫進持倉的各種原因）、
  `setting_structure`（`user_setting` 的壞列與解析不了的鍵）。
  - 例外：`setting_raw`（`{鍵: 試算表上的原字串或 None}`）**存檔要用** —— 使用者沒動過的欄位寫回這個原字串，
    不寫畫面上格式化過的顯示字串（2026-10-09 稽核回修）。讀失敗時為空 dict。

`save_setting(鍵, 值或 None, value_kind)` → L2 `save_setting_for_page` 的回傳（純 dict，訊息已遮蔽）；
體例與 `ui_v2/set/source.py::save_setting` 相同（同一個 L2 函式、同一份秘密值）。
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

import streamlit as st

from services.v2_tables import (
    alo_holdings, contract, fund_keys, market_indicator, masking, nav_dividend, settings_store,
)

from . import live

_log = logging.getLogger(__name__)

# 淨值被扣下、畫面印「⬜ 資料未備」的四碼 —— 與 `ui_v2/hld/source.py::_NAV_UNAVAILABLE_WITHHELD` 同一份
# （兩頁不互相 import；tests/ui_v2/test_alo_source.py 比對兩者相等）。⛔ 刻意不含 `WITHHELD_INPUT_CONFLICT`。
_NAV_UNAVAILABLE_WITHHELD = frozenset({
    nav_dividend.WITHHELD_CCY_MISSING,
    nav_dividend.WITHHELD_CCY_CONFLICT,
    nav_dividend.WITHHELD_FETCHED_AT_MISSING,
    nav_dividend.WITHHELD_FETCHED_AT_FUTURE,
})

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


# 外層 `except` 只接這一組（2026-10-13 第二輪稽核 N-a；總管技術裁定）。逐一列舉三個呼叫會往外拋什麼（本組讀原始碼）：
# - `fund_keys.resolve_full_keys(list)`：自己 raise 的只有 TypeError（引數不是 list／tuple；本檔恆傳 list）與
#   注入對照表時的 TypeError／ValueError（本檔不注入）。讀對照表 `repositories/fund/sources.py::load_fund_code_mapping`
#   以 `os.path.exists` 判檔、`pd.read_csv` 包在 `except Exception` 內 print 後退回內建表 —— **讀檔失敗不往外拋**，
#   也沒有明文定義的讀檔失敗例外型別。⇒ 實務上沒有任何取數例外會漏出來。
# - `nav_dividend.build_nav_table`：L1（A 鏈）呼叫都經 `_call` 轉成錯誤字串；往外拋的只剩 `_group_funds` 的
#   ValueError（輸入不合契約）、`_check_rows_order` 的 AssertionError、`ReconcileError`（AssertionError 子類）——
#   全是程式或契約錯誤。累積表讀取（`nav_history_gs.NavHistoryError`）發生在 A 鏈內、同樣在 `_call` 裡；
#   且出處閘門關閉時根本不讀。
# - `market_indicator.build_fx_indicator_table`：L1 經 `_call`；往外拋的只有 ValueError（USD／TWD／不合 ISO）
#   與出口檢查的 AssertionError —— 全是程式錯誤。
# ⇒ 只接 `OSError`（含 ConnectionError、TimeoutError，以及 requests 的 RequestException〔IOError 子類〕），
#   以防日後 L1 改成不吞而讓網路／讀檔例外漏出來。AssertionError／TypeError／ValueError／KeyError 一律往上拋（§1）。
_FETCH_ERRORS = (OSError,)


def _today_tw():
    """台灣日曆日（L2 `nav_dividend.MARKET_DATE_TZ`，同 L2 判「未來淨值日」的那一個時區）。獨立成函式讓測試能固定它。"""
    return datetime.now(nav_dividend.MARKET_DATE_TZ).date()


def _fetch_failed(call: str, exc: Exception, mask) -> str:
    """取數呼叫拋例外：遮蔽後記 log（CLAUDE.md §3.3：不吞、至少要 log），回傳給 errors 用的原文。"""
    text = mask(f"{type(exc).__name__}: {exc}")
    _log.warning("alo 取數失敗（%s）：%s", call, text)
    return text


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

    setting_rows, setting_raw = [], {}
    if settings is not None:
        setting_raw = {key: (settings["rows"].get(key) or {}).get("setting_value") for key in live.SETTING_KEYS}
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

    # ── nav ＋ 非美元匯率（2026-10-13 客戶裁示：B 線資產配置必須是真資料）──
    # 只在已存基準是「市值」時取（成本基準用不到）；組 L2 輸入照 `ui_v2/hld/source.py` 三條（帶 holding_ccy、
    # 不去重、只放代碼對照 ok 的檔）。
    # ~~這一段任何例外都轉成 `errors["nav"]` 的原文（經遮蔽）~~ → 2026-10-13 稽核 B2（總管技術裁定；有意識的更正，
    # 不是漏刪）：`except` **只包三個取數呼叫**（`resolve_full_keys`、`build_nav_table`、`build_fx_indicator_table`），
    # 被包住的例外記 log 後以「型別名: 訊息」（經遮蔽）進對應的 errors，市值基準下畫 ⛔。
    # 第二輪 N-a：而且只接取數類例外（`_FETCH_ERRORS`，列舉見該常數上方）。
    # 組輸入時的 KeyError／TypeError 與 `live.assemble_nav` 的契約錯誤（扣下碼不在清單、代碼對不上）是程式 bug，
    # 照 CLAUDE.md §1 往上拋 —— 頁面會印 Traceback，那是 bug 該有的 fail loud。舊寫法把 bug 標成「取數失敗」，
    # 會讓人去查來源而不是查程式；它的用意（本頁沒有錯誤畫面、不要整頁崩）只對取數失敗成立。
    nav_rows = []
    mi_rows = [dict(row) for row in indicators["rows"]] if indicators else []
    if tables is not None and live.wants_market_value(setting_rows):
        mask = alo_holdings.masker(values)
        holding = tables["holding"]
        key_results = nav_table = None
        try:
            key_results = fund_keys.resolve_full_keys([h["fund_code"] for h in holding])["results"]
        except _FETCH_ERRORS as exc:   # 不是吞：記 log，原文經遮蔽進 errors["nav"]（N-a：只接取數類例外）
            errors["nav"] = _fetch_failed("fund_keys.resolve_full_keys", exc, mask)
        if key_results is not None:
            resolved = {r["input"]: r for r in key_results if r["ok"] is True}
            funds = [
                {
                    "fund_code": h["fund_code"],
                    "full_key": resolved[h["fund_code"]]["full_key"],
                    "portal": resolved[h["fund_code"]]["portal"],
                    "chain_code": resolved[h["fund_code"]]["parsed_code"],
                    "holding_ccy": h["ccy"],
                }
                for h in holding if h["fund_code"] in resolved
            ]
            try:
                nav_table = nav_dividend.build_nav_table(funds)
            except _FETCH_ERRORS as exc:   # 不是吞：記 log，原文經遮蔽進 errors["nav"]（N-a）
                errors["nav"] = _fetch_failed("nav_dividend.build_nav_table", exc, mask)
        if nav_table is not None:
            nav_out = live.assemble_nav(   # 契約錯誤照拋（B2）
                holding_codes=[h["fund_code"] for h in holding],
                key_results=key_results,
                nav_table=nav_table,
                empty_without_reason=nav_dividend.EMPTY_WITHOUT_REASON,
                nav_unavailable_withheld=_NAV_UNAVAILABLE_WITHHELD,
                mask=mask,
                # N-b：淨值日距今（台灣日曆日，L2 的 MARKET_DATE_TZ）超過 SSOT 門檻 → 不納入市值
                today=_today_tw(),
                max_age_days=contract.NAV_MAX_AGE_DAYS,
            )
            nav_rows = nav_out["nav"]
            notes["nav"] = nav_out["notes"]
            if nav_out["error"] is not None:
                errors["nav"] = nav_out["error"]
            # 49 §6.1 Q9：非美元幣別的匯率鍵由 L2 取（同一條觀測日規則、同一個閘門；閘門關時不取數）。
            ccys = live.fx_ccys_needed(nav_rows)
            if ccys:
                try:
                    fx_table = market_indicator.build_fx_indicator_table(ccys)
                except _FETCH_ERRORS as exc:   # 不是吞：記 log，原文經遮蔽進 errors["market_indicator"]（N-a）
                    errors["market_indicator"] = "；".join(filter(None, [
                        errors.get("market_indicator"),
                        _fetch_failed("market_indicator.build_fx_indicator_table", exc, mask)]))
                else:
                    mi_rows, mi_error, notes["fx_pending"] = live.merge_fx_table(
                        mi_rows, errors.get("market_indicator"), fx_table, mask)
                    if mi_error is not None:
                        errors["market_indicator"] = mi_error

    dataset = {
        "holding": [dict(row) for row in tables["holding"]] if tables else [],
        # ~~本頁不取淨值（2026-10-09 裁示只到 hld、set），不是讀失敗~~ → 2026-10-13 客戶裁示：本頁取淨值（上面那段）
        "nav": nav_rows,
        "policy": [dict(row) for row in tables["policy"]] if tables else [],
        "market_indicator": mi_rows,
        "user_setting": setting_rows,
        "errors": errors,
        "save_errors": {},              # 存檔成敗由 page.py 併進來，不是讀表的結果
    }
    notes.update(
        mask_token=masking.MASK,
        pending_tables=list(settings_store.PENDING_TABLES),
        pages_reading_settings=list(settings_store.PAGES_READING_SETTINGS),
        read_estimate=(tables or {}).get("read_estimate"),
        setting_raw=setting_raw,
        direct=list((tables or {}).get("direct") or ()),
        warnings=list((tables or {}).get("warnings") or ()),
        skipped={name: (tables or {}).get(name) for name in _SKIP_GROUPS} if tables else {},
    )
    return {"dataset": dataset, "notes": notes}


def save_setting(setting_key, setting_value, value_kind) -> dict:
    """給 `page.render(save_live=...)` 用：存一個鍵（L2 先檢查值與型別，不符不存；寫表以外的例外照樣往上拋）。"""
    return settings_store.save_setting_for_page(setting_key, setting_value, value_kind, _secret_values())
