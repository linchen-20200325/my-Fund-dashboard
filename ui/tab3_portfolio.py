"""ui/tab3_portfolio.py — 組合基金 Tab（v18.128 B-C.6 最終）

從 app.py 抽出 Tab3（組合基金管理，含 T5/T6/T7 子區）的渲染邏輯 — B-C 系列最後一個。

Tab3 是 6 個 tab 中**最大**（3897 行 body），原 app.py 內有兩個 `with tab3:`
block 累積在同一 tab slot（block 1: MK 戰情室+組合管理，block 2: T5/T6/T7 持股
矩陣+講義+帳本）。本檔將兩 block 合併為**單一 render 函式**，行為等價。

設計：
- render_portfolio_tab() -> None **零閉包依賴**（與其他 5 個 tab 同設計）
- GEMINI_KEY 從 env / _calc_data_health, _friendly_error, _is_core_fund 從
  ui.helpers.session / 其餘 session_state 鍵透過 st.session_state 取
- T7 ledger 相關 Ledger/Switch class 維持原邏輯：函式內部 lazy import 自
  services.ledger_service（避免本檔頂部一次 import 太多）

對外 API:
- render_portfolio_tab() -> None
"""
from __future__ import annotations

import copy
import datetime
import json
import os
import time as _time_mod
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from infra.oauth import (
    OAuthError,
    build_credentials_from_tokens,
    ensure_fresh_tokens,
)
from infra.proxy import get_proxy_config
from models.policy import PK_SEP, fund_pk_str, make_pk, parse_pk, migrate_ledger_dict
from repositories.fund_repository import fetch_fund_from_moneydj_url
from repositories.ledger_repository import (
    append_ledger_row,
    load_all_ledgers,
    replace_ledgers_for_policy,
)
from repositories.news_repository import fetch_market_news
from repositories.policy_repository import (
    PolicySheetError,
    create_dashboard_sheet,
    delete_policy_row,
    detect_sheet_schema_version,
    get_gspread_client,
    get_gspread_client_from_oauth,
    get_sheet_title,
    list_policy_worksheets,
    list_user_folders,
    list_user_sheets,
    load_all_policies_v2,
    load_all_policy_worksheets,
    load_policies,
    rename_sheet,
    sync_policies_to_portfolio_funds,
    upsert_fund_in_policy,
    upsert_policy_row,
)
from repositories.snapshot_repository import (
    get_state_metadata,
    load_all_ledgers_snapshot,
    save_all_ledgers_snapshot,
)
from services.ai_service import (
    analyze_portfolio_mk_advisor,
    analyze_portfolio_correlation,
)
from services.fund_service import calc_metrics, calc_dividend_estimate
from services.macro_service import (
    backtest_sub_cycle_lights,
    calc_macro_phase,
    rank_macro_drivers,
)
from services.policy_advisor_service import (
    advise_fund,
    recommend_policy,
)
from services.portfolio_service import (
    calc_correlation_matrix,
    calc_holdings_overlap,
    dividend_safety as div_safety_check,
)
from services.precision_service import (
    PrecisionStrategyEngine,
    calc_hwm_sigma_levels,
)
from ui.components.mk_dashboard import render_mk_war_room
from ui.helpers.session import (
    calc_data_health as _calc_data_health_pure,
    friendly_error as _friendly_error,
    is_core_fund as _is_core_fund,
)
from ui.tab3_t7_ledger import render_t7_section

# 其他 fund_fetcher utility
from fund_fetcher import (
    classify_fetch_status,
    normalize_result_state,
    clean_risk_table,
    safe_float,
    is_valid_moneydj_page,
)


def _calc_data_health(indicators=None):
    ind = indicators if indicators is not None else st.session_state.get("indicators", {})
    return _calc_data_health_pure(ind)


def render_portfolio_tab() -> None:
    """渲染組合基金 Tab — 含 MK 戰情室 + 加入基金 + T5/T6/T7 子區。

    Tab3 為 6 tab 最大塊（原 3897 行）；本函式合併 app.py 內兩個 with tab3: block。
    Caller 不需傳參數。
    """
    GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")

    # v18.140: 全部 helper 改正規 import — 徹底脫離 v18.129 sys.modules['__main__'] hack
    # v18.148: 先呼叫 refresh_oauth_state() 把 module-level snapshot 更新到 fresh，
    #          再 local 重 import _oauth_configured / _oauth_cfg；
    #          否則 wizard 寫 session_state 後 rerun，本檔仍拿 import 時的 False snapshot。
    from ui.helpers.oauth_state import refresh_oauth_state as _refresh_oauth_state
    _refresh_oauth_state()
    from ui.helpers.oauth_state import (
        _oauth_configured,
        _oauth_cfg,
        _resolve_oauth_cfg,
        _get_oauth_client,
        _gsa_secret,
        _sheet_id_secret,
    )
    from ui.helpers.holdings import _zh_holding
    from ui.helpers.data_registry import (
        _update_data_registry,
        _sync_invest_twd_from_ledgers,
    )

    st.markdown("## 📊 組合基金管理")
    st.caption("加入多檔基金，即時計算核心/衛星配比、六因子評分、現金流估算")

    if "portfolio_funds" not in st.session_state:
        st.session_state.portfolio_funds = []

    # ── v18.9 MK 智能戰情室（決策導向：核心衛星×體檢×買賣區間）────────────
    # 已載入基金時頂部優先顯示；空組合時讓給歡迎卡。
    _pf_for_warroom = [f for f in st.session_state.portfolio_funds
                       if f.get("loaded") and not f.get("load_error")]
    if _pf_for_warroom:
        # v18.163：頂部統一 hero KPI（合併 mk_war_room 4 卡 + 配息矩陣 4 卡，
        # 解決 user 反饋「上下兩段 KPI 重複占版面」）。
        from ui.helpers.portfolio_health import (
            compute_health_kpis,
            render_hero_kpi_cards,
        )
        try:
            from ui.components.mk_dashboard import build_mk_dataframe as _build_mk
            _loaded_hero = [f for f in _pf_for_warroom
                             if f.get("loaded") and not f.get("load_error")]
            _mk_df_hero = _build_mk(_loaded_hero, bench_series=None)
        except Exception:
            _mk_df_hero = None   # noqa: smoke-allow-pass — KPI 不影響後續功能
        _kpis_hero = compute_health_kpis(_pf_for_warroom, _mk_df_hero)
        st.session_state["_t3_kpis_hero"] = _kpis_hero   # 供下方 expander summary 用
        st.markdown(
            "<div style='background:linear-gradient(135deg,#1a2845,#0d1b2a);"
            "border-left:4px solid #64b5f6;border-radius:8px;padding:10px 14px;margin:8px 0'>"
            "<span style='color:#64b5f6;font-size:15px;font-weight:900'>📊 組合健康儀表</span>"
            "<span style='color:#888;font-size:11px;margin-left:8px'>v18.163 6 指標一覽</span>"
            "</div>",
            unsafe_allow_html=True)
        render_hero_kpi_cards(_kpis_hero)
        st.divider()

        # v18.14: 改用 markdown 章節（避免外層 expander 包住內部 expander 觸發 Streamlit 巢狀錯誤）
        st.markdown(
            "<div style='background:linear-gradient(135deg,#1a2845,#0d1b2a);"
            "border-left:4px solid #64b5f6;border-radius:8px;padding:10px 14px;margin:8px 0'>"
            "<span style='color:#64b5f6;font-size:15px;font-weight:900'>🎯 策略3 智能戰情室</span>"
            "<span style='color:#888;font-size:11px;margin-left:8px'>v18.9 新手戰情中心</span>"
            "</div>",
            unsafe_allow_html=True)
        render_mk_war_room(st.session_state.portfolio_funds)
        st.divider()

    # ════════════════════════════════════════════════════════════════
    # 🆕 v18.22 保單視圖 P1.3：保單管理 + 保單分組視圖（top-level expander）
    # v18.75：OAuth 設定解析 + 登入 UI 已 hoist 到 sidebar；此處僅保留 Sheet 設定
    # ════════════════════════════════════════════════════════════════

    # v18.28: 未登入 OAuth 或無 token 時預設展開（引導使用者連 Sheets）
    _gsheet_default_expand = not bool(st.session_state.get("gsheet_tokens"))
    with st.expander("📋 保單管理（Google Sheets）— Sheet 設定 / 保單清單",
                     expanded=_gsheet_default_expand):
        # v18.162：互動式快捷面板 ── 4 顆按鈕全部「真執行」一鍵到位。
        # 雲端讀寫抽 ui/helpers/cloud_io.py 純函式（dump_all_to_sheet /
        # load_all_from_sheet），與下方 L880+ 完整面板共用同一份 IO 邏輯；
        # JSON 下載/上傳沿用 v18.161 的 ui/helpers/json_backup.py。
        # 未登入 OAuth 或無 sheet_id 時，雲端 panel 顯示友善提示 + 動作按鈕 disabled。
        st.markdown("##### 🚀 快速存讀面板")
        _io_panel = st.session_state.get("t3_io_panel", "load")

        def _t3_set_io_panel(_name: str) -> None:
            st.session_state["t3_io_panel"] = _name

        _io_c1, _io_c2, _io_c3, _io_c4, _io_c5 = st.columns(5)
        _io_c1.button("📥 雲端讀取", use_container_width=True,
                      key="t3_io_btn_load",
                      type=("primary" if _io_panel == "load" else "secondary"),
                      on_click=_t3_set_io_panel, args=("load",),
                      help="從 Google Sheet 把保單分頁 + _T7_State 讀回本地")
        _io_c2.button("📦 雲端存檔", use_container_width=True,
                      key="t3_io_btn_save",
                      type=("primary" if _io_panel == "save" else "secondary"),
                      on_click=_t3_set_io_panel, args=("save",),
                      help="把目前持倉 + ledger 寫回 Google Sheet")
        _io_c3.button("✨ 新增帳本", use_container_width=True,
                      key="t3_io_btn_new",
                      type=("primary" if _io_panel == "new" else "secondary"),
                      on_click=_t3_set_io_panel, args=("new",),
                      help="建立全新的 Google Sheet 作為帳本")
        _io_c4.button("💾 下載 JSON", use_container_width=True,
                      key="t3_io_btn_dl",
                      type=("primary" if _io_panel == "dl" else "secondary"),
                      on_click=_t3_set_io_panel, args=("dl",),
                      help="把整本帳本下載為本機 JSON（不依賴網路）")
        _io_c5.button("📂 上傳 JSON", use_container_width=True,
                      key="t3_io_btn_ul",
                      type=("primary" if _io_panel == "ul" else "secondary"),
                      on_click=_t3_set_io_panel, args=("ul",),
                      help="從本機 JSON 還原整本帳本")

        # 共用：雲端 panel 需要的快取狀態（避免重複打 API）
        _sheet_id_q = (st.session_state.get("policy_sheet_id") or "").strip()
        _logged_in_q = bool(st.session_state.get("gsheet_tokens"))
        _can_cloud_q = bool(_sheet_id_q) and (
            _logged_in_q or (_gsa_secret and _sheet_id_secret)
        )
        _sheet_title_q = ""
        if _can_cloud_q and _oauth_configured and _logged_in_q:
            _sheet_title_q = st.session_state.get("_t3_cur_sheet_title", "")
            if not _sheet_title_q:
                try:
                    _sheet_title_q = (
                        get_sheet_title(_get_oauth_client(), _sheet_id_q) or ""
                    )
                    if _sheet_title_q:
                        st.session_state["_t3_cur_sheet_title"] = _sheet_title_q
                except Exception:
                    _sheet_title_q = ""

        def _t3_cloud_client_q():
            return (_get_oauth_client() if _oauth_configured
                    else get_gspread_client(dict(_gsa_secret)))

        with st.container(border=True):
            if _io_panel == "load":
                # v18.166：📥 雲端讀取 = 讀取現有帳本 + 從 Drive 挑帳本（兩者皆在此面板）
                st.markdown("**📥 雲端讀取（全部讀回 / 挑選帳本）**")
                if not _logged_in_q and not (_gsa_secret and _sheet_id_secret):
                    st.warning(
                        "⚠️ 尚未用 Google 登入。請至左側 sidebar 點「🔐 用 Google 登入」。"
                    )
                else:
                    # v18.168：對調 — 上半「📂 從 Drive 挑帳本」，下半「📥 立即全部讀回」
                    # 上半 ── 從 Drive 挑帳本（OAuth + 已登入時顯示）
                    if _oauth_configured and _logged_in_q:
                        st.markdown("**📂 從 Drive 挑帳本（切換 / 首次選用）**")
                        _fld_btn_c1, _fld_btn_c2 = st.columns([2, 3])
                        if _fld_btn_c1.button("🔄 載入資料夾清單",
                                               key="btn_load_drive_folders",
                                               use_container_width=True,
                                               help="點一次抓 Drive 內所有資料夾；之後下方下拉就能選"):
                            try:
                                _folders_ls = list_user_folders(_get_oauth_client())
                                st.session_state["_my_folders"] = _folders_ls
                                if not _folders_ls:
                                    st.info("ℹ️ Drive 內沒有資料夾，或 token 缺 `drive.metadata.readonly` 權限")
                            except (PolicySheetError, OAuthError) as _fle:
                                _err_text_f = str(_fle)
                                if "insufficient" in _err_text_f.lower() or "403" in _err_text_f:
                                    st.error("❌ 列資料夾失敗：OAuth token 缺中繼權限。左 sidebar「🚪 登出」→ 重新登入即可。")
                                else:
                                    st.error(f"❌ 列資料夾失敗：{_fle}")
                            except Exception as _fle2:
                                st.error(f"❌ 未預期錯誤：[{type(_fle2).__name__}] {_fle2}")

                        _my_folders = st.session_state.get("_my_folders") or []
                        _folder_options = [("", "🌐 整個帳號（不限資料夾）")] + [
                            (f["id"], f"📁 {f['name']}  (`{f['id'][:10]}…`)") for f in _my_folders]
                        _cur_folder_id = str(st.session_state.get("_drive_folder_id", "") or "")
                        try:
                            _cur_fld_idx = next(i for i, (fid, _) in enumerate(_folder_options) if fid == _cur_folder_id)
                        except StopIteration:
                            _cur_fld_idx = 0
                        _sel_fld_idx = st.selectbox(
                            "📁 限定資料夾（可選）",
                            range(len(_folder_options)),
                            index=_cur_fld_idx,
                            format_func=lambda i: _folder_options[i][1],
                            key="sel_drive_folder",
                            help="留空 = 列整個帳號；或先點「🔄 載入資料夾清單」抓 Drive 資料夾後挑一個")
                        _folder_id = _folder_options[_sel_fld_idx][0]
                        st.session_state["_drive_folder_id"] = _folder_id

                        if st.button("📂 從 Drive 列出 Sheets",
                                      key="btn_list_drive_sheets",
                                      use_container_width=True,
                                      help="需要 OAuth `drive.metadata.readonly` 權限；若尚未授權請先登出再登入"):
                            try:
                                _files_ls = list_user_sheets(_get_oauth_client(), folder_id=_folder_id)
                                st.session_state["_my_sheets"] = _files_ls
                                _scope_name = _folder_options[_sel_fld_idx][1].lstrip("📁🌐 ").split("  (")[0]
                                st.session_state["_my_sheets_scope"] = _scope_name
                                if not _files_ls:
                                    st.info("ℹ️ Drive 內沒有 Google Sheets，或目前 token 只能看 app 建立的檔。")
                            except (PolicySheetError, OAuthError) as _lse:
                                _err_text = str(_lse)
                                if "insufficient" in _err_text.lower() or "403" in _err_text:
                                    st.error(
                                        "❌ 列檔失敗：OAuth token 缺 `drive.metadata.readonly` 權限。"
                                        "請至 sidebar「🚪 登出」→ 重新「🔐 用 Google 登入」。"
                                    )
                                else:
                                    st.error(f"❌ 列檔失敗：{_lse}")
                            except Exception as _lse2:
                                st.error(f"❌ 未預期錯誤：[{type(_lse2).__name__}] {_lse2}")

                        _my_sheets = st.session_state.get("_my_sheets") or []
                        _scope_hint = st.session_state.get("_my_sheets_scope", "")
                        if _my_sheets:
                            _opt_labels = [f"📄 {f['name']}  (`{f['id'][:14]}…`)" for f in _my_sheets]
                            _scope_label = f"（來源：{_scope_hint}）" if _scope_hint else ""
                            _sel_idx = st.selectbox(
                                f"清單共 {len(_my_sheets)} 個 Sheets — 選一本 {_scope_label}",
                                range(len(_opt_labels)),
                                format_func=lambda i: _opt_labels[i],
                                key="sel_my_sheets",
                            )
                            if st.button("✅ 使用此 Sheet 作為投組資料庫",
                                          key="btn_pick_my_sheet",
                                          type="primary", use_container_width=True):
                                _picked = _my_sheets[_sel_idx]
                                st.session_state["policy_sheet_id"] = _picked["id"]
                                if "inp_sheet_id" in st.session_state:
                                    del st.session_state["inp_sheet_id"]
                                st.session_state.pop("_t3_cur_sheet_title", None)
                                st.success(f"✅ 已選用 `{_picked['name']}`（ID `{_picked['id']}`）")
                                st.rerun()
                        st.markdown("---")

                    # 下半 ── 全部讀回（需有 _sheet_id_q）
                    if _sheet_id_q:
                        st.markdown("**📥 全部讀回（雲端 → 本地）**")
                        _fund_n = len(st.session_state.get("portfolio_funds", []) or [])
                        _last_load = st.session_state.get("t3_last_load_at", "—")
                        _book_disp = (f"**{_sheet_title_q}**" if _sheet_title_q
                                      else f"`{_sheet_id_q[:14]}…`")
                        st.caption(
                            f"📂 帳本：{_book_disp} ｜ 本地持倉：{_fund_n} 檔 "
                            f"｜ 上次讀回：{_last_load}"
                        )
                        if st.button("📥 立即全部讀回", type="primary",
                                      use_container_width=True,
                                      key="t3_io_panel_load_run"):
                            from ui.helpers.cloud_io import load_all_from_sheet
                            _res = load_all_from_sheet(
                                _t3_cloud_client_q(), _sheet_id_q,
                                st.session_state,
                                oauth_mode=bool(_oauth_configured),
                            )
                            if not _res["ok"]:
                                st.error(f"❌ {_res['error']}")
                            else:
                                import datetime as _dt_q
                                st.session_state["t3_last_load_at"] = (
                                    _dt_q.datetime.now().strftime("%Y-%m-%d %H:%M")
                                )
                                _msg = [f"新增 {len(_res['added'])} 檔",
                                        f"保留 {len(_res['kept'])} 檔",
                                        f"移除 {len(_res['removed'])} 檔"]
                                if _res["restored_ct"]:
                                    _msg.append(f"T7 部位 {_res['restored_ct']} 筆")
                                st.success("📥 全部讀回完成：" + " / ".join(_msg))
                                for _w in _res["warnings"]:
                                    st.warning(f"⚠️ {_w}")
                                st.rerun()
                    else:
                        st.info(
                            "ℹ️ 尚未指定 Sheet ID。請從上方「📂 從 Drive 挑一本」，"
                            "或至「✨ 新增帳本」建立新帳本。"
                        )
            elif _io_panel == "save":
                st.markdown("**📦 全部寫入 Sheet（本地 → 雲端）**")
                if not _can_cloud_q:
                    st.warning(
                        "⚠️ 尚未登入 Google 或未指定 Sheet ID。請先在下方完成設定。"
                    )
                else:
                    _fund_n = len(st.session_state.get("portfolio_funds", []) or [])
                    _last_save = st.session_state.get("t3_last_save_at", "—")
                    _book_disp = (f"**{_sheet_title_q}**" if _sheet_title_q
                                  else f"`{_sheet_id_q[:14]}…`")
                    st.caption(
                        f"📂 帳本：{_book_disp} ｜ 待寫入持倉：{_fund_n} 檔 "
                        f"｜ 上次寫入：{_last_save}"
                    )
                    if st.button("📦 立即全部寫入", type="primary",
                                  use_container_width=True,
                                  key="t3_io_panel_save_run",
                                  disabled=(_fund_n == 0),
                                  help=("無持倉可寫入" if _fund_n == 0 else None)):
                        from ui.helpers.cloud_io import dump_all_to_sheet
                        _res = dump_all_to_sheet(
                            _t3_cloud_client_q(), _sheet_id_q, st.session_state,
                        )
                        if not _res["ok"]:
                            st.error(f"❌ {_res['error']}")
                        else:
                            import datetime as _dt_q
                            st.session_state["t3_last_save_at"] = (
                                _dt_q.datetime.now().strftime("%Y-%m-%d %H:%M")
                            )
                            _msg = [f"保單分頁 +{_res['written']} 筆"]
                            if _res["n_state"]:
                                _msg.append(f"_T7_State +{_res['n_state']} 筆")
                            if _res["skipped_no_pid"]:
                                _msg.append(f"略過未綁保單 {_res['skipped_no_pid']} 檔")
                            st.success("📦 已寫入 Sheet：" + "、".join(_msg))
                            for _w in _res["warnings"]:
                                st.warning(f"⚠️ {_w}")
                            st.rerun()
            elif _io_panel == "new":
                # v18.166：「✨ 新增帳本」只剩「自動建立新 Sheet」；
                # 「從 Drive 挑」已移到「📥 雲端讀取」面板（user 截圖反饋）
                st.markdown("**✨ 新增帳本（建立全新 Google Sheet）**")
                if not _oauth_configured:
                    st.warning(
                        "⚠️ 需先設定 OAuth Client 才能建立 Google Sheet。"
                        "請至下方 expander 設定。"
                    )
                elif not _logged_in_q:
                    st.warning(
                        "⚠️ 尚未用 Google 登入。請至左側 sidebar 點「🔐 用 Google 登入」。"
                    )
                else:
                    st.caption(
                        "💡 讓 app 建一張全新的 Google Sheet 作為帳本（不必先到 Drive 開檔）。"
                        "想挑 Drive 內既有的 Sheet 請改點「📥 雲端讀取」。"
                    )
                    _ac_c1, _ac_c2 = st.columns([3, 2])
                    _ac_title = _ac_c1.text_input(
                        "新 Sheet 名稱", value="Fund Dashboard - 投資組合",
                        key="inp_auto_sheet_title",
                    ).strip()
                    _ac_c2.write("")
                    if _ac_c2.button("🚀 自動建立 Sheet",
                                      key="btn_auto_create_sheet",
                                      use_container_width=True,
                                      disabled=not _ac_title):
                        try:
                            _new_sid, _new_url = create_dashboard_sheet(
                                _get_oauth_client(), _ac_title)
                            st.session_state["policy_sheet_id"] = _new_sid
                            if "inp_sheet_id" in st.session_state:
                                del st.session_state["inp_sheet_id"]
                            st.session_state.pop("_t3_cur_sheet_title", None)
                            st.success(
                                f"✅ 已建立新 Sheet `{_ac_title}` — ID `{_new_sid}` 已自動填入。"
                            )
                            st.markdown(f"📂 [在 Google Drive 開啟此 Sheet]({_new_url})")
                            st.rerun()
                        except (PolicySheetError, OAuthError) as _ace:
                            _err_text = str(_ace)
                            if "insufficient authentication scopes" in _err_text.lower() or "403" in _err_text:
                                st.error(
                                    "❌ 建立失敗：OAuth token 缺 `drive.file` 權限。"
                                    "請至 sidebar「🚪 登出」→ 重新「🔐 用 Google 登入」。"
                                )
                            else:
                                st.error(f"❌ 建立失敗：{_ace}")
                        except Exception as _ace2:
                            st.error(f"❌ 未預期錯誤：[{type(_ace2).__name__}] {_ace2}")
            elif _io_panel == "dl":
                import datetime as _dt_top
                import json as _json_top
                from ui.helpers.json_backup import build_export_payload
                _payload = build_export_payload(st.session_state)
                _bytes = _json_top.dumps(
                    _payload, ensure_ascii=False, indent=2,
                ).encode("utf-8")
                _ts = _dt_top.datetime.now().strftime("%Y%m%d_%H%M%S")
                st.markdown("**💾 下載完整 JSON 備份**")
                st.caption(
                    f"含 {len(_payload['portfolio_funds'])} 檔基金 + "
                    f"{len(_payload['t7_ledgers'])} 筆 ledger + "
                    f"{len(_payload['t7_scenarios'])} 個方案（離線可還原）"
                )
                st.download_button(
                    "💾 立即下載 JSON 備份",
                    data=_bytes,
                    file_name=f"fund_dashboard_backup_{_ts}.json",
                    mime="application/json",
                    use_container_width=True,
                    key="t3_io_dl_btn_top",
                )
            elif _io_panel == "ul":
                from ui.helpers.json_backup import restore_from_json_bytes
                st.markdown("**📂 上傳 JSON 還原**")
                st.caption("選擇先前下載的 `fund_dashboard_backup_*.json` 直接覆蓋本地帳本。")
                _up = st.file_uploader(
                    "選擇 JSON 備份檔", type=["json"],
                    key="t3_io_ul_top", label_visibility="collapsed",
                )
                if _up is not None:
                    _result = restore_from_json_bytes(_up.read(), st.session_state)
                    if _result["ok"]:
                        st.success(
                            f"✅ 已還原 {_result['n_funds']} 檔基金 + "
                            f"{_result['n_ledgers']} 筆 ledger。"
                            "請按下方「📡 載入所有未載入基金」重新抓取即時資料。"
                        )
                        st.session_state.pop("_t7_auto_estimate_done", None)
                        st.rerun()
                    else:
                        st.error(f"❌ {_result['error']}")
        st.divider()

        # ── 認證區塊（v18.75 已搬到 sidebar，這裡只顯示狀態與連結）─────
        _logged_in = bool(st.session_state.get("gsheet_tokens"))

        if _oauth_configured:
            if _logged_in:
                st.success("🟢 已用 Google 登入（OAuth）— 登出請至左側 sidebar")
            else:
                st.info("ℹ️ 尚未登入 Google — 請至左側 sidebar 點「🔐 用 Google 登入」")
        elif _gsa_secret and _sheet_id_secret:
            st.info("ℹ️ 偵測到 Service Account 設定，走舊版單表 schema（向後相容）")
            _logged_in = True   # SA 視同已登入
        else:
            # v18.32: In-app OAuth Client 設定 wizard
            #         不必碰 secrets.toml / 不必重新部署，session-only 即時生效
            st.warning(
                "尚未設定 OAuth Client。請依下方步驟在 GCP console 建一個，"
                "再回到這裡貼三個值即可登入。"
            )
            st.markdown("---")
            st.markdown("##### 🧙 OAuth Client 設定引導（5 分鐘完成）")
            st.markdown(
                """
                **一次性 GCP 設定**（之後你就只要按「🔐 用 Google 登入」即可）：

                1. **啟用 API**：[GCP Console → APIs Library](https://console.cloud.google.com/apis/library) →
                   啟用 `Google Sheets API` + `Google Drive API`
                2. **OAuth consent screen**：
                   [連結](https://console.cloud.google.com/apis/credentials/consent) → User Type: **External**
                   → 填 App name / email → Scopes 加 `spreadsheets` + `drive.file` + `openid` + `userinfo.email`
                   → Test users 加自己的 Gmail
                3. **建 OAuth Client ID**：
                   [連結](https://console.cloud.google.com/apis/credentials) → Create Credentials →
                   OAuth client ID → Web application
                   → **Authorized redirect URIs** 必須加上**這個 app 的 URL**（含尾巴 `/`），
                   e.g. `https://你的-app.streamlit.app/` 或 `http://localhost:8501/`
                   → 建完會跳出 Client ID + Client Secret，複製下來
                4. **填到下方表單**並按「💾 套用」，立即啟用登入按鈕
                """
            )

            st.markdown("##### 貼上你的 OAuth Client 三個值")
            # 預填 session_state 已存的（重整後重貼方便）
            _existing = st.session_state.get("custom_oauth_cfg", {}) or {}
            _wf1, _wf2 = st.columns(2)
            _w_cid = _wf1.text_input(
                "Client ID",
                value=_existing.get("client_id", ""),
                placeholder="1234567890-xxxxx.apps.googleusercontent.com",
                key="wf_oauth_cid",
            )
            _w_csec = _wf2.text_input(
                "Client Secret",
                value=_existing.get("client_secret", ""),
                placeholder="GOCSPX-xxxxxxxxxxxxxxxxxx",
                type="password",
                key="wf_oauth_csec",
            )
            # Redirect URI 預設：嘗試從當前 URL 推斷（給使用者複製到 GCP console）
            _default_redirect = _existing.get("redirect_uri", "")
            if not _default_redirect:
                try:
                    # Streamlit 1.30+ 提供 st.context.url；缺則留空讓使用者貼
                    _default_redirect = getattr(st.context, "url", "")
                except Exception:
                    _default_redirect = ""
            _w_uri = st.text_input(
                "Redirect URI（要跟 GCP console 完全一致，含尾巴 `/`）",
                value=_default_redirect,
                placeholder="https://你的-app.streamlit.app/",
                key="wf_oauth_uri",
                help="必須含 `https://` 開頭與結尾斜線，且要跟 GCP Console「Authorized redirect URIs」一字不差",
            )

            _wbc1, _wbc2 = st.columns([1, 3])
            if _wbc1.button("💾 套用設定", type="primary",
                            use_container_width=True,
                            disabled=not (_w_cid.strip() and _w_csec.strip()
                                          and _w_uri.strip()),
                            key="btn_save_custom_oauth"):
                _ru = _w_uri.strip()
                # 防呆 1：缺 scheme 自動補 https://
                if _ru and not (_ru.startswith("http://") or _ru.startswith("https://")):
                    _ru = "https://" + _ru
                # 防呆 2：Google OAuth 要求 redirect_uri 完整含 path，常見漏結尾 /
                if "/" not in _ru[8:]:  # 跳過 https:// 後檢查 path
                    _ru = _ru + "/"
                st.session_state["custom_oauth_cfg"] = {
                    "client_id":     _w_cid.strip(),
                    "client_secret": _w_csec.strip(),
                    "redirect_uri":  _ru,
                }
                if _ru != _w_uri.strip():
                    st.info(f"ℹ️ redirect_uri 自動補完為 `{_ru}` — 請確認 GCP Console「Authorized redirect URIs」也是這個字串")
                st.success("✅ OAuth Client 設定已套用（session 有效），"
                           "可按「🔐 用 Google 登入」")
                st.rerun()
            _wbc2.caption(
                "ℹ️ Session-only：重整頁面後要重貼。"
                "若要永久生效，請把這三個值寫到 Streamlit Secrets `[google_oauth]` section。"
            )

        # ── v18.164：Sheet ID 輸入已 hoist 到 sidebar；此處只從 session_state 取值 ──
        if _logged_in:
            _sheet_id = (st.session_state.get("policy_sheet_id")
                          or _sheet_id_secret or "").strip()

            # v18.165：「✨ 新增帳本」面板已 hoist 到頂部快捷面板第 5 顆按鈕
            # 此處不再重複渲染自動建立 / Drive 挑（避免 widget key 衝突）

            # ── v18.169：原「📋 保單清單」說明區塊已移至 Tab6 說明書（§9 Sheet 資料結構）──
            # 動態 metric（保單分頁 / _T7_State / _Ledgers 計數）已捨棄，避免 Tab3 雜訊

            # ── v18.48 多帳本管理（明顯區塊：建立 / 切換 / 改名）──
            # 用途：不同人 / 帳戶各自一本（例：本人 / 配偶 / 父母 / 退休帳戶）
            if _oauth_configured and _sheet_id:
                st.markdown("---")
                st.markdown("##### 📁 多帳本管理（不同人 / 帳戶各自一本）")

                # 顯示目前 Sheet 標題
                _cur_title = ""
                try:
                    _cur_title = get_sheet_title(_get_oauth_client(), _sheet_id)
                except Exception:
                    _cur_title = ""   # noqa: smoke-allow-pass — 取不到不影響後續功能
                if _cur_title:
                    st.info(f"📂 目前工作中的帳本：**{_cur_title}**　·　ID `{_sheet_id[:14]}…`")
                else:
                    st.info(f"📂 目前工作中的帳本 ID：`{_sheet_id[:14]}…`（標題取不到）")

                # 三個動作 tabs：建立另一本 / 改名 / 從 Drive 切換
                _mb_t1, _mb_t2, _mb_t3 = st.tabs([
                    "🆕 建立另一本", "📝 改名目前帳本", "🔁 切換到別本",
                ])

                with _mb_t1:
                    st.caption("為新的人 / 帳戶建立一本獨立 Google Sheet（不會動到目前這本）")
                    _another_name = st.text_input(
                        "新帳本名稱",
                        value="",
                        key="inp_another_sheet_name",
                        placeholder="例：Fund Dashboard - 配偶 / 退休帳戶 / 父母",
                    ).strip()
                    if st.button("🚀 建立並切換到新帳本",
                                  key="btn_create_another_sheet",
                                  type="primary", use_container_width=True,
                                  disabled=not _another_name):
                        try:
                            _ca_sid, _ca_url = create_dashboard_sheet(
                                _get_oauth_client(), _another_name)
                            st.session_state["policy_sheet_id"] = _ca_sid
                            if "inp_sheet_id" in st.session_state:
                                del st.session_state["inp_sheet_id"]
                            st.success(
                                f"✅ 已建立並切換到新帳本「{_another_name}」"
                                f"（原本的帳本仍在你的 Drive，可隨時切回去）"
                            )
                            st.markdown(f"📂 [在 Google Drive 開啟新帳本]({_ca_url})")
                            st.rerun()
                        except (PolicySheetError, OAuthError) as _cae:
                            _err_text = str(_cae)
                            if "insufficient" in _err_text.lower() or "403" in _err_text:
                                st.error(
                                    "❌ 建立失敗：OAuth token 缺少 `drive.file` 權限。"
                                    "請先登出再登入重新授權。"
                                )
                            else:
                                st.error(f"❌ 建立失敗：{_cae}")
                        except Exception as _cae2:
                            st.error(f"❌ 未預期錯誤：[{type(_cae2).__name__}] {_cae2}")

                with _mb_t2:
                    st.caption("把目前這本帳本改個更清楚的名字（不影響資料）")
                    _new_name = st.text_input(
                        "新名稱",
                        value=_cur_title or "",
                        key="inp_rename_sheet",
                        placeholder="例：Fund Dashboard - 本人",
                    ).strip()
                    if st.button("✅ 套用新名稱",
                                  key="btn_apply_rename",
                                  type="primary", use_container_width=True,
                                  disabled=not _new_name or _new_name == _cur_title):
                        try:
                            rename_sheet(_get_oauth_client(), _sheet_id, _new_name)
                            st.success(f"✅ 已將帳本改名為「{_new_name}」")
                            st.rerun()
                        except (PolicySheetError, OAuthError) as _rne:
                            st.error(f"❌ 改名失敗：{_rne}")
                        except Exception as _rne2:
                            st.error(f"❌ 未預期錯誤：[{type(_rne2).__name__}] {_rne2}")

                with _mb_t3:
                    st.caption("從你 Google Drive 內所有 Sheets 挑一本切換過去")
                    if st.button("📂 重新列出 Drive 中的所有 Sheets",
                                  key="btn_list_drive_sheets_t3",
                                  use_container_width=True):
                        try:
                            _client_ls2 = _get_oauth_client()
                            _files_ls2 = list_user_sheets(_client_ls2)
                            st.session_state["_my_sheets"] = _files_ls2
                            if not _files_ls2:
                                st.info("ℹ️ Drive 內沒有任何 Sheet")
                        except (PolicySheetError, OAuthError) as _lse2:
                            _err_text2 = str(_lse2)
                            if "insufficient" in _err_text2.lower() or "403" in _err_text2:
                                st.error(
                                    "❌ 列檔失敗：OAuth token 缺 `drive.metadata.readonly` 權限。"
                                    "請先登出再登入。"
                                )
                            else:
                                st.error(f"❌ 列檔失敗：{_lse2}")

                    _ms2 = st.session_state.get("_my_sheets") or []
                    if _ms2:
                        # 過濾掉目前正在用的這本
                        _ms2_others = [f for f in _ms2 if f.get("id") != _sheet_id]
                        if not _ms2_others:
                            st.caption("（目前 Drive 內只有這一本帳本）")
                        else:
                            _opts2 = [f"📄 {f['name']}  (ID `{f['id'][:12]}…`)" for f in _ms2_others]
                            _pick_idx = st.selectbox(
                                f"共 {len(_ms2_others)} 本可切換",
                                range(len(_opts2)),
                                format_func=lambda i: _opts2[i],
                                key="sel_switch_sheet",
                            )
                            if st.button("🔁 切換到此帳本",
                                          key="btn_switch_to_sheet",
                                          type="primary", use_container_width=True):
                                _target = _ms2_others[_pick_idx]
                                st.session_state["policy_sheet_id"] = _target["id"]
                                if "inp_sheet_id" in st.session_state:
                                    del st.session_state["inp_sheet_id"]
                                st.success(f"✅ 已切換到「{_target['name']}」")
                                st.rerun()

            # ── v18.149 schema v2 升級偵測（PR A — UI hook only）──
            # v2 schema：每張保單分頁內聯 units / avg_nav / avg_fx + 多幣別現金。
            # PR A 提供工具（detect / migrate / backup），PR B 才接 wizard / 編輯 UI。
            # 這裡只放偵測 + 一鍵升級按鈕讓 user 自己決定何時轉。
            if _oauth_configured and _sheet_id:
                st.markdown("---")
                st.markdown("##### 🆕 v18.149 新資料格式（snapshot-only）")
                st.caption(
                    "新格式：每張保單分頁直接存「持有單位、平均 NAV、平均 FX、多幣別現金」"
                    "（11 欄）— 砍掉 `_T7_State` + `_Ledgers` 結構。"
                    "T7 模組改成純讀模擬；真實加碼/贖回請自行在 Sheet 內修改。"
                    "升級前會先**複製整本 Sheet 為備份**，確認新資料無誤再手動刪舊備份。"
                )
                _mig_c1, _mig_c2 = st.columns([2, 3])
                if _mig_c1.button("🔍 偵測目前 Sheet 格式",
                                    key="btn_detect_schema_v149",
                                    use_container_width=True):
                    try:
                        _cli_d = _get_oauth_client()
                        _ver = detect_sheet_schema_version(_cli_d, _sheet_id)
                        st.session_state["_schema_ver"] = _ver
                    except PolicySheetError as _ed:
                        st.error(f"❌ 偵測失敗：{_ed}")
                    except Exception as _ed2:
                        st.error(f"❌ 未預期錯誤：[{type(_ed2).__name__}] {_ed2}")
                _ver_now = st.session_state.get("_schema_ver", "")
                if _ver_now == "v2":
                    _mig_c2.success("✅ 已是 v2 新格式")
                elif _ver_now == "v1":
                    _mig_c2.warning("⚠️ 目前是 v1 舊格式，建議升級")
                elif _ver_now == "empty":
                    _mig_c2.info("ℹ️ 空 Sheet（無保單分頁）— 等加保單後再升級")

                if _ver_now == "v1":
                    if st.button("🚀 升級到 v2（先備份原 Sheet）",
                                  key="btn_migrate_v149",
                                  type="primary", use_container_width=True):
                        try:
                            from scripts.migrate_v149_schema import migrate_sheet as _mig
                            _cli_m = _get_oauth_client()
                            with st.spinner("⏳ 備份 + 升級中（視保單數約 10-60 秒）..."):
                                _summary = _mig(_cli_m, _sheet_id, with_backup=True)
                            if _summary.get("backup_sheet_url"):
                                st.success(
                                    f"✅ 已備份原 Sheet → "
                                    f"[在 Drive 開啟備份]({_summary['backup_sheet_url']})"
                                )
                            _ok_n = sum(1 for m in _summary.get("migrated", [])
                                         if not m.get("errors"))
                            _err_n = sum(1 for m in _summary.get("migrated", [])
                                          if m.get("errors"))
                            st.success(
                                f"✅ 已升級 {_ok_n}/{_summary.get('policies', 0)} 張保單到 v2"
                                + (f"（{_err_n} 張有錯誤，見下方）" if _err_n else "")
                            )
                            if _err_n:
                                st.warning("\n".join(
                                    f"- {m['policy_id']}：{'; '.join(m['errors'])}"
                                    for m in _summary["migrated"] if m.get("errors")
                                ))
                            st.session_state["_schema_ver"] = "v2"
                            st.rerun()
                        except Exception as _eme:
                            st.error(f"❌ 升級失敗：[{type(_eme).__name__}] {_eme}")

                # v2 預覽：讀新 schema 顯示給 user 對照
                if _ver_now == "v2":
                    if st.checkbox("👁️ 預覽 v2 schema 資料（read-only）",
                                    key="cb_preview_v2", value=False):
                        try:
                            _cli_p = _get_oauth_client()
                            _df_v2 = load_all_policies_v2(_cli_p, _sheet_id)
                            if _df_v2.empty:
                                st.caption("（v2 schema 沒有任何資料）")
                            else:
                                st.dataframe(_df_v2, use_container_width=True,
                                              hide_index=True)
                                st.caption(
                                    f"共 {len(_df_v2)} 列；"
                                    f"fund={len(_df_v2[_df_v2['item_type']=='fund'])}、"
                                    f"cash={len(_df_v2[_df_v2['item_type']=='cash'])}。"
                                )
                        except Exception as _epe:
                            st.error(f"❌ 讀 v2 失敗：[{type(_epe).__name__}] {_epe}")

                # v18.150 PR B：v2 native 編輯 UI（保單區塊 + in-line data_editor +
                # 新增保單 + 第一次使用 wizard）
                if _ver_now == "v2":
                    try:
                        from ui.helpers.v2_editor import render_v2_section
                        _cli_v2 = _get_oauth_client()
                        render_v2_section(_cli_v2, _sheet_id)
                    except Exception as _ev2:
                        st.error(f"❌ v2 編輯 UI 載入失敗："
                                  f"[{type(_ev2).__name__}] {_ev2}")

            # ── v18.167：原「🧰 一鍵存讀」（與頂部 📥/📦 重複）已刪除
            #            此處只保留頂部沒有的小工具：refresh-only + 清空快取
            if _sheet_id:
                st.markdown("---")
                st.markdown("##### 🛠️ 進階工具")
                st.caption("📌 全部存讀請至頂部「🚀 快速存讀面板」；此處只放頂部沒有的小工具。")

                _tool_c1, _tool_c2 = st.columns(2)
                _refresh_clicked = _tool_c1.button(
                    "🔄 只重新整理分頁清單（不動投組）",
                    key="btn_policy_refresh", use_container_width=True,
                    help="只重整下方「保單分頁」下拉選單，不動投資組合資料"
                )
                # v18.58: 一鍵清空 fetch TTL 快取（強制下次抓 fresh NAV/FX/Macro）
                _clear_cache_clicked = _tool_c2.button(
                    "🗑️ 清空抓取快取",
                    key="btn_clear_fetch_cache_v18_58",
                    use_container_width=True,
                    help=("清空 fund_fetcher / macro_core 的 TTL 快取，"
                          "下次抓取會走 fresh HTTP（盤中需要即時新值時用）。\n"
                          "預設 TTL：NAV/FX 5min、MoneyDJ 15min、Macro 5min、FRED 30min")
                )
                if _clear_cache_clicked:
                    try:
                        from fund_fetcher import clear_all_caches as _cac
                        import repositories.macro_repository  # noqa: F401 — 觸發 macro 快取註冊
                        _n = _cac()
                        st.success(f"✅ 已清空 {_n} 個快取函式（下次抓取走 fresh HTTP）")
                    except Exception as _e_cc:
                        st.error(f"清空失敗：{str(_e_cc)[:120]}")
                try:
                    from fund_fetcher import get_all_cache_info as _gci
                    import repositories.macro_repository  # noqa: F401 — 觸發 macro 快取註冊
                    _info_rows = _gci()
                    if _info_rows:
                        _total_entries = sum(r["size"] for r in _info_rows)
                        _total_hits = sum(r.get("hits", 0) for r in _info_rows)
                        _total_misses = sum(r.get("misses", 0) for r in _info_rows)
                        _total_calls = _total_hits + _total_misses
                        _hit_rate = (
                            f"{(_total_hits / _total_calls * 100):.1f}%"
                            if _total_calls > 0 else "—"
                        )
                        st.caption(
                            f"🔋 快取狀態：{len(_info_rows)} 個函式 / "
                            f"{_total_entries} entries / hit-rate {_hit_rate}"
                            f"（hits={_total_hits} / misses={_total_misses}）"
                        )
                except Exception:
                    pass   # noqa: smoke-allow-pass — 顯示性 caption 失敗不影響功能

                # 共用：取統計與更新 _sheet_stats
                def _refresh_sheet_stats(_cli: object) -> None:
                    try:
                        _tabs_x = list_policy_worksheets(_cli, _sheet_id)
                        _meta_x = get_state_metadata(_cli, _sheet_id)
                        try:
                            _led_df = load_all_ledgers(_cli, _sheet_id)
                            _led_ct = len(_led_df)
                        except (PolicySheetError, OAuthError):
                            _led_ct = "—"
                        st.session_state["_sheet_stats"] = {
                            "tabs": len(_tabs_x),
                            "t7_state": _meta_x.get("row_count", 0),
                            "ledgers": _led_ct,
                            "last_sync": _meta_x.get("latest_updated_at", ""),
                        }
                    except Exception:
                        pass   # noqa: smoke-allow-pass — 統計失敗不影響主流程

                # v18.167：refresh_only 路徑（dump_all / load_all 已移到頂部快捷面板）
                if _refresh_clicked:
                    from ui.helpers.cloud_io import load_all_from_sheet
                    _client = _get_oauth_client() if _oauth_configured else \
                              get_gspread_client(dict(_gsa_secret))
                    _res_l = load_all_from_sheet(
                        _client, _sheet_id, st.session_state,
                        oauth_mode=bool(_oauth_configured),
                        refresh_only=True,
                    )
                    if not _res_l["ok"]:
                        st.error(f"❌ {_res_l['error']}")
                    else:
                        for _w in _res_l["warnings"]:
                            st.warning(f"⚠️ {_w}")
                        _refresh_sheet_stats(_client)
                        st.success("✅ 保單列表已刷新")
                        st.rerun()

                _pdf_cached = st.session_state.get("policies_df")
                if _pdf_cached is not None and not _pdf_cached.empty:
                    st.markdown("**📋 保單分頁清單**")
                    # v18.64: column header 改顯繁中（schema 仍英文，僅 UI 改名）
                    st.dataframe(
                        _pdf_cached, use_container_width=True, hide_index=True,
                        column_config={
                            "policy_id":    st.column_config.TextColumn("保單編號"),
                            "policy_name":  st.column_config.TextColumn("保單名稱"),
                            "fund_url":     st.column_config.TextColumn("基金代碼"),
                            "invest_twd":   st.column_config.NumberColumn("投資金額 (TWD)"),
                            "invest_date":  st.column_config.TextColumn("投資日期"),
                            "currency":     st.column_config.TextColumn("幣別"),
                            "fx_at_buy":    st.column_config.NumberColumn("買入匯率"),
                            "notes":        st.column_config.TextColumn("備註"),
                            "policy_tier":  st.column_config.TextColumn("配置定位"),
                        },
                    )

                # v18.167：「📁 本機 JSON 備份」整段刪除（與頂部 💾/📂 重複）

                # ── v18.63: 保單分頁管理區塊已移除（使用者反饋過度複雜）
                #           保單分頁的建立 / 刪除改由「批次加入」自動處理：
                #           - 加入基金時帶 pid → 自動建立對應保單分頁
                #           - 「📦 全部寫入 Sheet」自動上傳所有保單分頁
                #           - 如需刪除整個分頁，到 Google Sheets 直接刪 tab 即可

                # ── 舊 SA 路徑：保留原表單 ───────────────────────
                if _gsa_secret and not _oauth_configured:
                    _show_form = st.checkbox("➕ 編輯保單列（舊 SA schema）",
                        key="cb_policy_edit", value=False)
                    if _show_form:
                        st.markdown("##### 新增 / 更新保單列（主鍵：policy_id + fund_url）")
                        with st.form("form_policy_upsert", clear_on_submit=False):
                            _pf_c1, _pf_c2 = st.columns(2)
                            _row = {}
                            _row["policy_id"]   = _pf_c1.text_input("policy_id *", key="pol_id")
                            _row["policy_name"] = _pf_c2.text_input("policy_name", key="pol_name")
                            _row["fund_url"]    = _pf_c1.text_input("fund_url *", key="pol_url")
                            _row["invest_twd"]  = _pf_c2.number_input("invest_twd",
                                min_value=0, step=10000, key="pol_amt")
                            _row["invest_date"] = _pf_c1.text_input("invest_date", key="pol_date")
                            _row["currency"]    = _pf_c2.text_input("currency", key="pol_ccy")
                            _row["fx_at_buy"]   = _pf_c1.number_input("fx_at_buy",
                                min_value=0.0, step=0.01, key="pol_fx", value=0.0)
                            _row["notes"]       = _pf_c2.text_input("notes", key="pol_notes")
                            _fbcols = st.columns([1, 1, 4])
                            _save_clicked = _fbcols[0].form_submit_button("💾 儲存", type="primary")
                            _del_clicked  = _fbcols[1].form_submit_button("🗑️ 刪除此列")
                            if _save_clicked:
                                if not _row["policy_id"] or not _row["fund_url"]:
                                    st.warning("policy_id 與 fund_url 為必填")
                                else:
                                    try:
                                        _client = get_gspread_client(dict(_gsa_secret))
                                        _act = upsert_policy_row(_client, _sheet_id, _row)
                                        st.success(f"✅ {_act}")
                                    except PolicySheetError as _pe:
                                        st.error(f"❌ 寫入失敗：{_pe}")
                            elif _del_clicked:
                                if not _row["policy_id"] or not _row["fund_url"]:
                                    st.warning("policy_id + fund_url 必填")
                                else:
                                    try:
                                        _client = get_gspread_client(dict(_gsa_secret))
                                        _hit = delete_policy_row(_client, _sheet_id,
                                            _row["policy_id"], _row["fund_url"])
                                        st.success("✅ 已刪除" if _hit else "ℹ️ 主鍵未命中")
                                    except PolicySheetError as _pe:
                                        st.error(f"❌ 刪除失敗：{_pe}")

    with st.expander("🗂️ 保單分組視圖", expanded=True):
        _pol_funds = [f for f in st.session_state.portfolio_funds if f.get("policy_id")]
        _ungrouped = [f for f in st.session_state.portfolio_funds if not f.get("policy_id")]

        # v18.151: 頂部捷徑 — 有未載入基金時直接顯示載入按鈕，避免使用者滾不下去找
        from ui.helpers.portfolio_load import (
            batch_load_unloaded_funds as _batch_load_top,
            count_unloaded_funds as _count_unloaded_top,
        )
        _n_ent_top, _n_uniq_top = _count_unloaded_top()
        if _n_ent_top > 0:
            _top_label = (
                f"📡 載入未載入基金（{_n_ent_top} 條"
                + (f" / {_n_uniq_top} unique code" if _n_uniq_top != _n_ent_top else "")
                + "）— 抓即時 NAV / 績效"
            )
            if st.button(_top_label, type="primary",
                          key="btn_pf_load_all_top",
                          use_container_width=True):
                _batch_load_top()

        if not _pol_funds and not _ungrouped:
            st.info("尚未載入任何基金。設定 Google Sheets 後按「📡 從 Sheet 同步」即可帶入保單分組。")
        else:
            # 取 VIX 給 advisor（已在 session 內就用快取，否則 None）
            _vix_for_adv = None
            try:
                _vix_for_adv = float((st.session_state.get("compass_data") or {}).get("vix", {}).get("value")) \
                    if (st.session_state.get("compass_data") or {}).get("vix") else None
            except Exception:
                _vix_for_adv = None  # noqa: smoke-allow-pass

            # 分組
            _by_policy: dict[str, list[dict]] = {}
            for _f in _pol_funds:
                _by_policy.setdefault(_f.get("policy_id", "?"), []).append(_f)

            def _is_core_in_policy(_f: dict) -> bool:
                """P3：優先用 Sheet policy_tier，缺則 fallback 既有 _is_core_fund heuristic。"""
                _t = (_f.get("policy_tier") or "").lower()
                if _t == "core":
                    return True
                if _t == "satellite":
                    return False
                # fallback：既有 is_core flag（_is_core_fund 字串啟發）
                return bool(_f.get("is_core"))

            _policy_target = st.session_state.get("portfolio_core_pct", 75)

            for _pid, _funds in _by_policy.items():
                _pname = _funds[0].get("policy_name") or _pid
                _ptot  = sum(_f.get("invest_twd", 0) or 0 for _f in _funds)
                # P3：保單級 core/satellite 切分
                _p_core_amt = sum(_f.get("invest_twd", 0) or 0
                                  for _f in _funds if _is_core_in_policy(_f))
                _p_core_pct = round(_p_core_amt / _ptot * 100.0, 1) if _ptot else 0

                st.markdown(
                    f"<div style='background:linear-gradient(135deg,#0d1b2a,#1a2845);"
                    f"border-left:4px solid #64b5f6;border-radius:8px;padding:10px 14px;margin:10px 0 6px'>"
                    f"<span style='color:#64b5f6;font-weight:900;font-size:15px'>🏷️ {_pname}</span>"
                    f"<span style='color:#aaa;font-size:11px;margin-left:8px'>({_pid})</span>"
                    f"<span style='color:#fff;font-size:13px;margin-left:auto;float:right'>"
                    f"投入 NT$ {_ptot:,.0f} · {len(_funds)} 檔 · 核心 {_p_core_pct}%</span>"
                    f"</div>", unsafe_allow_html=True)

                # ── P3: 保單級核心/衛星 mini donut ────────────────────
                if _ptot > 0:
                    _dn_p_col, _dn_p_msg = st.columns([1, 2])
                    with _dn_p_col:
                        _dn_pv = [_p_core_amt, _ptot - _p_core_amt]
                        _dn_pl = [f"🛡️ 核心 {_p_core_pct}%",
                                  f"⚡ 衛星 {100 - _p_core_pct:.1f}%"]
                        fig_p_dn = go.Figure(go.Pie(
                            labels=_dn_pl, values=_dn_pv,
                            hole=0.65,
                            marker=dict(colors=["#64b5f6", "#ff9800"],
                                        line=dict(color="#0e1117", width=1)),
                            textinfo="percent", textfont=dict(size=9),
                            hovertemplate="%{label}: NT$%{value:,.0f}<extra></extra>",
                        ))
                        fig_p_dn.update_layout(
                            paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                            font_color="#e6edf3",
                            height=120,
                            margin=dict(t=4, b=4, l=4, r=4),
                            showlegend=False,
                            annotations=[dict(
                                text=f"<b>{_p_core_pct}%</b>",
                                x=0.5, y=0.5, font_size=12, showarrow=False,
                                font=dict(color="#64b5f6"))],
                        )
                        st.plotly_chart(fig_p_dn, use_container_width=True,
                                        key=f"policy_dn_{_pid}")
                    # 預先算每檔 sigma / dividend 供 recommend_policy 用（與下方 fund-level 同邏輯）
                    _funds_enriched = []
                    for _f in _funds:
                        _s = _f.get("series")
                        _m = _f.get("metrics", {}) or {}
                        _mj_e = _f.get("moneydj_raw", {}) or {}
                        _sig_e = None
                        if _s is not None and len(_s.dropna()) >= 30:
                            try:
                                from services.precision_service import calc_hwm_sigma_levels as _hwm_e
                                _sig_e = _hwm_e(_s, lookback=252)
                            except Exception:
                                _sig_e = None  # noqa: smoke-allow-pass
                        _div_e = None
                        try:
                            _tret = float(_mj_e.get("perf", {}).get("1Y")
                                          or _m.get("ret_1y") or 0)
                            _dyld = float(_mj_e.get("moneydj_div_yield")
                                          or _m.get("annual_div_rate") or 0)
                            if _dyld > 0:
                                _div_e = div_safety_check(_tret, _dyld)
                        except Exception:
                            _div_e = None  # noqa: smoke-allow-pass
                        _funds_enriched.append({
                            "invest_twd": _f.get("invest_twd", 0) or 0,
                            "is_core":    _is_core_in_policy(_f),
                            "sigma_info": _sig_e,
                            "dividend_info": _div_e,
                        })
                    _p_rec = recommend_policy(_funds_enriched, target_core_pct=_policy_target)
                    _rec_clr = {"red": "#f44336", "orange": "#ff9800", "yellow": "#ffeb3b",
                                "green": "#00c853", "grey": "#888"}.get(_p_rec["color"], "#888")
                    with _dn_p_msg:
                        st.markdown(
                            f"<div style='margin-top:18px;color:{_rec_clr};font-size:13px;"
                            f"line-height:1.55'>🎯 {_p_rec['text']}</div>",
                            unsafe_allow_html=True)

                for _f in _funds:
                    _code = _f.get("code", "?")
                    _name = (_f.get("name") or _code)[:30]
                    if not _f.get("loaded"):
                        st.caption(f"⏳ {_code} {_name} — 尚未抓資料（按下方批次載入）")
                        continue
                    if _f.get("load_error"):
                        st.caption(f"❌ {_code} — 載入失敗：{_f.get('load_error')}")
                        continue

                    _series  = _f.get("series")
                    _metrics = _f.get("metrics", {}) or {}
                    _mj      = _f.get("moneydj_raw", {}) or {}

                    # σ 位階
                    _sigma_info = None
                    if _series is not None and len(_series.dropna()) >= 30:
                        try:
                            from services.precision_service import calc_hwm_sigma_levels as _hwm_fn2
                            _sigma_info = _hwm_fn2(_series, lookback=252)
                        except Exception as _se:
                            _sigma_info = {"error": str(_se)[:60]}

                    # 配息覆蓋率 / 吃本金
                    _div_info = None
                    try:
                        _tret = float(_mj.get("perf", {}).get("1Y") or _metrics.get("ret_1y") or 0)
                        _dyld = float(_mj.get("moneydj_div_yield") or _metrics.get("annual_div_rate") or 0)
                        if _dyld > 0:
                            _div_info = div_safety_check(_tret, _dyld)
                    except Exception:
                        _div_info = None  # noqa: smoke-allow-pass

                    # 60MA 趨勢
                    _ma_trend = None
                    if _series is not None and len(_series.dropna()) >= 65:
                        try:
                            _ma60 = _series.dropna().rolling(60).mean()
                            if len(_ma60.dropna()) >= 5:
                                _ma_trend = "up" if _ma60.iloc[-1] > _ma60.iloc[-5] else "down"
                        except Exception:
                            _ma_trend = None  # noqa: smoke-allow-pass

                    _advice = advise_fund(_sigma_info, _div_info, _ma_trend, _vix_for_adv)

                    _sig_lbl = (_sigma_info or {}).get("label", "—") if _sigma_info else "—"
                    _sig_clr = (_sigma_info or {}).get("color", "#888") if _sigma_info else "#888"
                    _sig_rnk = (_sigma_info or {}).get("sigma_rank")
                    _sig_str = f"{_sig_rnk:+.2f}σ" if isinstance(_sig_rnk, (int, float)) else "—"
                    _div_alert = (_div_info or {}).get("alert_level", "grey")
                    _div_icon  = {"red": "🔴", "yellow": "🟡", "green": "🟢", "grey": "⚪"}.get(_div_alert, "⚪")
                    _adv_clr   = {"red": "#f44336", "orange": "#ff9800", "yellow": "#ffeb3b",
                                  "green": "#00c853", "grey": "#888"}.get(_advice["color"], "#888")
                    _inv_amt   = _f.get("invest_twd", 0) or 0

                    st.markdown(
                        f"<div style='background:#0d1117;border:1px solid #21262d;border-radius:8px;"
                        f"padding:10px 14px;margin:4px 0 8px 20px'>"
                        f"<div style='display:flex;align-items:center;gap:12px;flex-wrap:wrap'>"
                        f"<span style='color:#e6edf3;font-weight:700;font-size:13px'>{_name}</span>"
                        f"<span style='color:#888;font-size:11px'>{_code}</span>"
                        f"<span style='color:{_sig_clr};font-size:11px;background:#161b22;padding:2px 8px;border-radius:10px'>"
                        f"σ {_sig_str} · {_sig_lbl}</span>"
                        f"<span style='color:#ccc;font-size:11px'>{_div_icon} {_div_alert}</span>"
                        f"<span style='color:#aaa;font-size:11px;margin-left:auto'>NT$ {_inv_amt:,.0f}</span>"
                        f"</div>"
                        f"<div style='color:{_adv_clr};font-size:12px;margin-top:6px;line-height:1.5'>"
                        f"💡 {_advice['text']}</div>"
                        f"</div>", unsafe_allow_html=True)

            if _ungrouped:
                st.markdown(
                    "<div style='color:#888;font-size:12px;margin-top:14px'>📂 未分組基金（手動加入、未綁保單）</div>",
                    unsafe_allow_html=True)
                for _f in _ungrouped:
                    st.caption(f"• {_f.get('code','?')} — {_f.get('name','') or '尚未載入'}")
                # v18.151: 「未綁保單」inline 快捷 — 載入這些 + 綁到保單下拉
                st.caption(
                    f"⚠️ 你有 **{len(_ungrouped)} 檔未綁保單**（這些基金不在任何保單分頁內）。"
                )
                _ug_c1, _ug_c2 = st.columns([2, 3])
                # 載入這些（會等同上方主按鈕，只是顯眼快捷）
                _ug_not_loaded = [_g for _g in _ungrouped if not _g.get("loaded")]
                if _ug_not_loaded:
                    if _ug_c1.button(f"📡 載入這 {len(_ug_not_loaded)} 檔",
                                       key="btn_load_ungrouped",
                                       use_container_width=True,
                                       help="跟頂部「載入未載入基金」同效果，方便就近點"):
                        from ui.helpers.portfolio_load import batch_load_unloaded_funds as _bl_ug
                        _bl_ug()
                # 綁到既有保單（OAuth + 已升 v2 時才顯示，避免複雜化）
                if _oauth_configured and _sheet_id and \
                   st.session_state.get("_schema_ver") == "v2":
                    try:
                        from repositories.policy_repository import list_policy_worksheets as _lpw
                        _existing_pids = _lpw(_get_oauth_client(), _sheet_id)
                    except Exception:
                        _existing_pids = []
                    if _existing_pids:
                        with _ug_c2:
                            _bind_pid = st.selectbox(
                                "🔗 綁到保單", ["（先選保單）"] + list(_existing_pids),
                                key="sel_bind_policy_ungrouped",
                                label_visibility="collapsed")
                            if _bind_pid and _bind_pid != "（先選保單）":
                                if st.button(f"✅ 套用：把這 {len(_ungrouped)} 檔綁到「{_bind_pid}」",
                                              key="btn_apply_bind_pid",
                                              use_container_width=True):
                                    # 把所有未綁基金都設 policy_id
                                    _cnt = 0
                                    for _idx, _ff in enumerate(st.session_state.portfolio_funds):
                                        if not _ff.get("policy_id"):
                                            st.session_state.portfolio_funds[_idx]["policy_id"] = _bind_pid
                                            _cnt += 1
                                    st.success(
                                        f"✅ 已把 {_cnt} 檔綁到「{_bind_pid}」（仍須到「✨ v2 編輯介面」"
                                        f"填 units/avg_nav/avg_fx 後 [💾 存到雲端] 才會推 Google Sheet）"
                                    )
                                    st.rerun()
                else:
                    _ug_c2.caption(
                        "💡 升級到 v2 後可用「🔗 綁到保單」下拉，"
                        "或到「✨ v2 編輯介面」手動加列。"
                    )

    # ── v18.46 緊湊歡迎條（單列三步驟，不再佔大面積）────────────────────
    _pf_loaded = [f for f in st.session_state.portfolio_funds if f.get("loaded")]
    if not _pf_loaded:
        st.markdown(
            "<div style='background:#0d1b2a;border:1px dashed #64b5f6;border-radius:8px;"
            "padding:6px 14px;margin:4px 0 10px;font-size:12px;color:#aaa;"
            "display:flex;align-items:center;gap:12px;flex-wrap:wrap'>"
            "<span style='color:#64b5f6;font-weight:700'>👋 三步驟：</span>"
            "<span><b style='color:#fff'>1️⃣ 貼代碼</b></span>"
            "<span style='color:#555'>→</span>"
            "<span><b style='color:#fff'>2️⃣ 批次加入</b></span>"
            "<span style='color:#555'>→</span>"
            "<span><b style='color:#fff'>3️⃣ 看 KPI / T5 / T7</b></span>"
            "<span style='margin-left:auto;color:#666;font-size:10px'>"
            "💡 AI 分析按鈕觸發，不自動扣 API</span>"
            "</div>", unsafe_allow_html=True)

    # ── v15.1 ② KPI 字卡列：總資產 / 累計報酬 / 核心% / 月配息（新手語言）──
    if _pf_loaded:
        _tot_kpi  = sum(f.get("invest_twd",0) or 0 for f in _pf_loaded)
        _core_kpi = sum(f.get("invest_twd",0) or 0 for f in _pf_loaded if f.get("is_core"))
        _core_pct_kpi = round(_core_kpi/_tot_kpi*100,1) if _tot_kpi else 0
        # 累計報酬：以各基金 series 起點 → 當前點，按投資額加權
        _cum_ret_pct = None
        try:
            _w_returns = []
            _w_amounts = []
            for _f in _pf_loaded:
                _s = _f.get("series")
                _amt = _f.get("invest_twd", 0) or 0
                if _s is not None and len(_s.dropna()) >= 2 and _amt > 0:
                    _ss = _s.dropna()
                    _ret = (float(_ss.iloc[-1]) / float(_ss.iloc[0]) - 1.0) * 100.0
                    _w_returns.append(_ret * _amt)
                    _w_amounts.append(_amt)
            if _w_amounts:
                _cum_ret_pct = sum(_w_returns) / sum(_w_amounts)
        except Exception:
            _cum_ret_pct = None
        # 月配息估算：從 moneydj_raw.moneydj_div_yield / metrics.annual_div_rate
        # v18.39 修：原本用 dividend_yield_pct/yield_pct 都不是實際 schema 上的欄位，
        # 整個欄一直是 0；改用 v18.34 真實收益矩陣同款 fallback chain。
        _est_monthly_div = 0.0
        for _f in _pf_loaded:
            _mj_kpi = _f.get("moneydj_raw") or {}
            _m_kpi  = _f.get("metrics") or {}
            _yld = (_mj_kpi.get("moneydj_div_yield")
                    or _m_kpi.get("annual_div_rate")
                    or 0)
            _amt = _f.get("invest_twd", 0) or 0
            try:
                _est_monthly_div += (float(_yld) / 100.0) * float(_amt) / 12.0
            except Exception:
                pass  # noqa: smoke-allow-pass — 任一檔配息率非數值不影響其餘累加

        _ret_color = "#00c853" if (_cum_ret_pct or 0) > 0 else ("#f44336" if (_cum_ret_pct or 0) < 0 else "#888")
        _ret_str   = f"{_cum_ret_pct:+.2f}%" if _cum_ret_pct is not None else "—"
        st.markdown(
            "<div style='display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:8px 0 16px'>"
            f"<div style='background:linear-gradient(135deg,#0d1b2a,#1a2845);border:1px solid #30363d;"
            f"border-radius:12px;padding:16px 18px'>"
            f"<div style='color:#aaa;font-size:11px'>💰 總資產（NTD）</div>"
            f"<div style='color:#fff;font-size:26px;font-weight:900;margin-top:4px'>NT$ {_tot_kpi:,.0f}</div>"
            f"<div style='color:#888;font-size:10px;margin-top:2px'>{len(_pf_loaded)} 檔基金加總</div></div>"
            f"<div style='background:linear-gradient(135deg,#0d1b2a,#1a2845);border:1px solid #30363d;"
            f"border-radius:12px;padding:16px 18px'>"
            f"<div style='color:#aaa;font-size:11px'>📈 累計報酬</div>"
            f"<div style='color:{_ret_color};font-size:26px;font-weight:900;margin-top:4px'>{_ret_str}</div>"
            f"<div style='color:#888;font-size:10px;margin-top:2px'>從淨值首日加權至今</div></div>"
            f"<div style='background:linear-gradient(135deg,#0d1b2a,#1a2845);border:1px solid #30363d;"
            f"border-radius:12px;padding:16px 18px'>"
            f"<div style='color:#aaa;font-size:11px'>🛡️ 核心資產比例</div>"
            f"<div style='color:#64b5f6;font-size:26px;font-weight:900;margin-top:4px'>{_core_pct_kpi:.1f}%</div>"
            f"<div style='color:#888;font-size:10px;margin-top:2px'>衛星 {100-_core_pct_kpi:.1f}%</div></div>"
            f"<div style='background:linear-gradient(135deg,#0d1b2a,#1a2845);border:1px solid #30363d;"
            f"border-radius:12px;padding:16px 18px'>"
            f"<div style='color:#aaa;font-size:11px'>💵 預估月配息</div>"
            f"<div style='color:#ffb74d;font-size:26px;font-weight:900;margin-top:4px'>NT$ {_est_monthly_div:,.0f}</div>"
            f"<div style='color:#888;font-size:10px;margin-top:2px'>依各基金配息率粗估</div></div>"
            "</div>", unsafe_allow_html=True)

        # ── v15.1 ③ 資產成長曲線（vs 2% 無風險基準，§0 禁 ETF）─────────
        # v18.43：同 code 跨多保單會讓 _value_series.name 重複，join 時欄名衝突拋例外。
        # 分析視圖按 code 去重（與 v18.34 MK 戰情室 / v18.38 真實收益矩陣策略一致）。
        try:
            import pandas as _pd_curve
            _curve_df = None
            _seen_curve: set = set()
            for _f in _pf_loaded:
                _c_curve = str(_f.get("code", "") or "").strip().upper()
                if not _c_curve or _c_curve in _seen_curve:
                    continue
                _s = _f.get("series")
                _amt = _f.get("invest_twd", 0) or 0
                if _s is None or len(_s.dropna()) < 2 or _amt <= 0:
                    continue
                _seen_curve.add(_c_curve)
                _ss = _s.dropna()
                # 折算為「今日金額對齊到首日 NAV → 今日 NAV」的成長
                _value_series = (_ss / float(_ss.iloc[0])) * float(_amt)
                _value_series.name = _c_curve
                if _curve_df is None:
                    _curve_df = _value_series.to_frame()
                else:
                    _curve_df = _curve_df.join(_value_series, how="outer")
            if _curve_df is not None and len(_curve_df) >= 2:
                _curve_df = _curve_df.sort_index().ffill()
                _total_curve = _curve_df.sum(axis=1)
                # 2% 無風險基準（從首日總額複利）
                _days = (_total_curve.index - _total_curve.index[0]).days
                _rf_curve = float(_total_curve.iloc[0]) * (1.0 + 0.02) ** (_days / 365.0)

                with st.expander("📈 資產成長曲線（含 2% 無風險基準對比）", expanded=True):
                    fig_curve = go.Figure()
                    fig_curve.add_trace(go.Scatter(
                        x=_total_curve.index, y=_total_curve.values,
                        name="你的組合", mode="lines",
                        line=dict(color="#00c853", width=2.5, shape="spline"),
                        fill="tozeroy", fillcolor="rgba(0,200,83,0.08)",
                        hovertemplate="%{x|%Y-%m-%d}<br>NT$ %{y:,.0f}<extra></extra>"))
                    fig_curve.add_trace(go.Scatter(
                        x=_total_curve.index, y=_rf_curve,
                        name="2% 無風險基準", mode="lines",
                        line=dict(color="#888", width=1.2, dash="dot"),
                        hovertemplate="%{x|%Y-%m-%d}<br>NT$ %{y:,.0f}<extra>無風險</extra>"))
                    # 標註：起點 / 當前 / 最高 / 最低
                    _hi_idx = _total_curve.idxmax(); _lo_idx = _total_curve.idxmin()
                    fig_curve.add_trace(go.Scatter(
                        x=[_total_curve.index[0], _hi_idx, _lo_idx, _total_curve.index[-1]],
                        y=[_total_curve.iloc[0], _total_curve.loc[_hi_idx],
                           _total_curve.loc[_lo_idx], _total_curve.iloc[-1]],
                        mode="markers+text",
                        marker=dict(size=[8,10,10,12],
                                    color=["#888","#00c853","#f44336","#fff"],
                                    line=dict(color="#0e1117", width=2)),
                        text=["起點", f"高 NT${_total_curve.loc[_hi_idx]:,.0f}",
                              f"低 NT${_total_curve.loc[_lo_idx]:,.0f}",
                              f"今 NT${_total_curve.iloc[-1]:,.0f}"],
                        textposition=["top right","top center","bottom center","top left"],
                        textfont=dict(size=10, color="#e6edf3"),
                        showlegend=False,
                        hoverinfo="skip"))
                    fig_curve.update_layout(
                        paper_bgcolor="#0e1117", plot_bgcolor="#161b22",
                        font_color="#e6edf3", height=320,
                        margin=dict(t=20, b=30, l=55, r=20),
                        legend=dict(orientation="h", y=1.05, font_size=10),
                        hovermode="x unified")
                    fig_curve.update_yaxes(title_text="總資產 (NTD)", gridcolor="#1e2a3a")
                    fig_curve.update_xaxes(gridcolor="#1e2a3a")
                    st.plotly_chart(fig_curve, use_container_width=True)
                    st.caption(
                        "💡 **怎麼看**：綠線是你的組合走勢，灰虛線是「把錢放定存賺 2%」的基準。"
                        "綠線在灰線上方代表你的選擇贏過定存。")
        except Exception as _curve_e:
            # v18.43 補錯誤型別讓使用者能 debug
            _friendly_error(
                "資產曲線繪製失敗",
                f"[{type(_curve_e).__name__}] {_curve_e}",
                hint="可能是某些基金的 NAV 序列太短或缺漏，等資料補齊後重試即可。")

    # Hero：核心/衛星配置概況
    if _pf_loaded:
        _tot  = sum(f.get("invest_twd",0) or 0 for f in _pf_loaded)
        _core = sum(f.get("invest_twd",0) or 0 for f in _pf_loaded if f.get("is_core"))
        _core_pct = round(_core/_tot*100,1) if _tot else 0
        _target   = st.session_state.get("portfolio_core_pct",75)
        _diff     = round(_core_pct - _target, 1)
        _dc       = "#f44336" if abs(_diff)>10 else ("#ff9800" if abs(_diff)>5 else "#00c853")
        st.markdown(
            f"<div style='background:linear-gradient(135deg,#0d1b2a,#1a2332);border-radius:14px;padding:18px 22px;margin-bottom:16px;border:1px solid #30363d'>"
            f"<div style='font-size:13px;color:#888;margin-bottom:10px'>📊 目前投資組合 — {len(_pf_loaded)} 檔" + (f" · NT${_tot:,.0f}" if _tot else "") + "</div>"
            f"<div style='display:flex;gap:20px;flex-wrap:wrap'>"
            f"<div><div style='color:#64b5f6;font-size:11px'>🛡️ 核心資產</div><div style='color:#64b5f6;font-size:28px;font-weight:900'>{_core_pct}%</div></div>"
            f"<div><div style='color:#ff9800;font-size:11px'>⚡ 衛星資產</div><div style='color:#ff9800;font-size:28px;font-weight:900'>{100-_core_pct:.1f}%</div></div>"
            f"<div><div style='color:{_dc};font-size:11px'>目標偏差</div><div style='color:{_dc};font-size:28px;font-weight:900'>{_diff:+.1f}%</div></div>"
            f"</div></div>", unsafe_allow_html=True)

        # ── 核心/衛星甜甜圈（P1.3 縮成單列 mini chart）──────────────
        _dn_labels = [
            (f.get("code","?")[:8] + " 🛡️" if f.get("is_core") else f.get("code","?")[:8] + " ⚡")
            for f in _pf_loaded]
        _dn_values = [max(f.get("invest_twd", 0) or 0, 0) for f in _pf_loaded]
        _dn_colors = ["#64b5f6" if f.get("is_core") else "#ff9800" for f in _pf_loaded]
        _alert     = abs(_diff) > 10
        _bg_c      = "#1a0808" if _alert else "#0e1117"
        fig_dn = go.Figure()
        if sum(_dn_values) > 0:
            fig_dn.add_trace(go.Pie(
                labels    = _dn_labels,
                values    = _dn_values,
                hole      = 0.65,
                marker    = dict(colors=_dn_colors, line=dict(color="#0e1117", width=1)),
                textinfo  = "percent",
                textfont  = dict(size=9),
                hovertemplate="%{label}: NT$%{value:,.0f} (%{percent})<extra></extra>",
            ))
        fig_dn.update_layout(
            paper_bgcolor = _bg_c, plot_bgcolor = _bg_c,
            font_color    = "#e6edf3",
            height        = 140,
            margin        = dict(t=4, b=4, l=4, r=4),
            showlegend    = False,
            annotations   = [dict(
                text  = f"<b>{_core_pct}%</b><br><span style='font-size:9px'>核心</span>",
                x=0.5, y=0.5, font_size=14, showarrow=False,
                font=dict(color="#64b5f6"))],
        )
        st.plotly_chart(fig_dn, use_container_width=True)
        _target2 = st.session_state.get("portfolio_core_pct", 75)
        if _alert:
            st.caption(
                f"⚠️ 配置偏離 {_diff:+.1f}%（核心 {_core_pct}% vs 目標 {_target2}%）— "
                f"{'核心過重，可贖回轉衛星' if _diff > 0 else '衛星過重，可獲利轉核心'}"
            )
        else:
            st.caption(
                f"✅ 配置健康（核心 {_core_pct}% / 衛星 {100-_core_pct:.1f}%，"
                f"偏差 {_diff:+.1f}%，目標 {_target2}%±10%）"
            )

    with st.expander("➕ 手動加入基金（支援多檔批次）", expanded=False):
        st.caption(
            "**📋 2 步驟流程**　·　Step 1（這裡）：貼**代碼** → 按 **➕ 批次加入** → "
            "**📡 載入所有未載入基金**　→　Step 2（下方 T7「📝 編輯初始持倉」）：輸入"
            "**單位數 / 平均成本 / 匯率**　→　上方「📦 全部寫入 Sheet」一鍵同步雲端。"
        )
        _existing_pids = st.session_state.get("policy_tabs", [])
        c_codes, c_default_pid = st.columns([3, 2])
        with c_codes:
            pf_codes_input = st.text_area(
                "基金代碼（每行一檔，可加 ,pid 逐行覆寫）",
                label_visibility="collapsed",
                # v18.62: 高度 120 → 75 防手機被按鈕擠到 fold 下方
                height=75,
                placeholder=("ACCP138\nACDD01\nJFZN3,PL-2024-002"),
                key="pf_codes_input",
            )
        with c_default_pid:
            pf_pid_input = st.text_input(
                "預設保單號碼（可選）",
                label_visibility="collapsed",
                placeholder=("預設保單 " + (
                    f"（已有：{', '.join(_existing_pids[:3])}{'…' if len(_existing_pids)>3 else ''}）"
                    if _existing_pids else "（可選）")),
                key="pf_pid_input",
            )
        pf_add_btn = st.button(
            "➕ 批次加入（加完按上方「📡 載入所有未載入基金」抓資料）",
            type="primary",
            use_container_width=True,
            key="btn_pf_add",
        )

        if pf_add_btn and pf_codes_input.strip():
            default_pid = pf_pid_input.strip()
            # ── v18.33: 解析多行輸入 ──────────────────────────────
            _entries: list[tuple] = []   # [(code, pid), ...]
            _existing_set = {(f["code"], f.get("policy_id", "") or "")
                              for f in st.session_state.portfolio_funds}
            _skipped_dup: list[str] = []
            for _line in pf_codes_input.splitlines():
                _line = _line.strip()
                if not _line:
                    continue
                if "," in _line:
                    _parts = [p.strip() for p in _line.split(",", 1)]
                    _code, _pid = _parts[0].upper(), _parts[1]
                else:
                    _code = _line.upper()
                    _pid = default_pid
                if not _code:
                    continue
                if (_code, _pid) in _existing_set:
                    _skipped_dup.append(f"{_code}@{_pid or '(未綁)'}")
                    continue
                _existing_set.add((_code, _pid))
                _entries.append((_code, _pid))

            if not _entries:
                if _skipped_dup:
                    st.warning(
                        f"⚠️ 全部已存在於組合：{', '.join(_skipped_dup[:10])}"
                        f"{'…' if len(_skipped_dup) > 10 else ''}"
                    )
                else:
                    st.warning("⚠️ 沒有有效代碼可加入")
            else:
                # ── v18.33: 並行抓取 + v18.58: 按 unique code 先 dedupe 再 broadcast
                # 同 code 跨 N 保單只 fetch 一次，再 broadcast 給所有 (code, pid)
                from concurrent.futures import ThreadPoolExecutor, as_completed
                _uniq_codes = list({_c for _c, _ in _entries})
                _progress = st.progress(0.0,
                    text=f"開始並行載入 {len(_uniq_codes)} 檔 unique 基金"
                         f"（{len(_entries)} 條 entry, dedupe by code）…")
                _code_to_raw: dict = {}   # code → (raw_dict, error_msg)
                _done = 0
                with ThreadPoolExecutor(max_workers=4) as _ex:
                    _futures = {
                        _ex.submit(fetch_fund_from_moneydj_url, _c): _c
                        for _c in _uniq_codes
                    }
                    for _fut in as_completed(_futures):
                        _c_key = _futures[_fut]
                        try:
                            _code_to_raw[_c_key] = (_fut.result(), None)
                        except Exception as _e:
                            _code_to_raw[_c_key] = (None, str(_e)[:80])
                        _done += 1
                        _progress.progress(
                            _done / len(_uniq_codes),
                            text=f"完成 {_done}/{len(_uniq_codes)}：剛完成 {_c_key}",
                        )
                _progress.empty()
                # broadcast：每個 (code, pid) 都拿同一份 raw_dict
                _results: dict = {
                    (_c, _p): _code_to_raw[_c] for _c, _p in _entries
                }

                # ── v18.33: 批次寫入 + Sheets 同步（單一 OAuth client）──
                _succ, _fail, _sheet_synced = [], [], []
                _cfg_b = _resolve_oauth_cfg()
                _toks_b = st.session_state.get("gsheet_tokens")
                _sid_b = st.session_state.get("policy_sheet_id")
                _client_b = None
                if _cfg_b and _toks_b and _sid_b:
                    try:
                        _t_b = ensure_fresh_tokens(dict(_toks_b),
                            _cfg_b["client_id"], _cfg_b["client_secret"])
                        st.session_state["gsheet_tokens"] = _t_b
                        _creds_b = build_credentials_from_tokens(_t_b,
                            _cfg_b["client_id"], _cfg_b["client_secret"])
                        _client_b = get_gspread_client_from_oauth(_creds_b)
                    except Exception as _e_oc:
                        _client_b = None
                        st.caption(f"⚠️ OAuth client 建立失敗：{str(_e_oc)[:60]}")

                for (_code_b, _pid_b), (_raw_b, _err_b) in _results.items():
                    _new_item_b = {"code": _code_b, "invest_twd": 0,
                                    "loaded": True, "load_error": None,
                                    "policy_id": _pid_b,
                                    "policy_name": _pid_b}
                    _emsg = _err_b or (_raw_b.get("error") if _raw_b else "")
                    if _emsg:
                        _new_item_b.update({"load_error": _emsg})
                        _fail.append(f"{_code_b}: {str(_emsg)[:40]}")
                    else:
                        _new_item_b.update({
                            "name":        _raw_b.get("fund_name") or _code_b,
                            "series":      _raw_b.get("series"),
                            "dividends":   _raw_b.get("dividends", []),
                            "metrics":     _raw_b.get("metrics", {}),
                            "moneydj_raw": _raw_b,
                            "risk_metrics":_raw_b.get("risk_metrics", {}),
                            "is_core":     _is_core_fund(
                                _raw_b.get("fund_name") or _code_b),
                            "currency":    _raw_b.get("currency", "")
                                            or _raw_b.get("metrics", {}).get("currency", ""),
                        })
                        _succ.append(_code_b)
                        if _pid_b and _client_b:
                            try:
                                upsert_fund_in_policy(_client_b, _sid_b, _pid_b, {
                                    "fund_url":     _code_b,
                                    "policy_name":  _pid_b,
                                    "invest_twd":   0,
                                    "invest_date":  "",
                                    "currency":     _new_item_b.get("currency", ""),
                                    "fx_at_buy":    0.0,
                                    "notes":        "Tab3 batch add",
                                    "policy_tier":  ("core" if _new_item_b.get("is_core")
                                                     else "satellite"
                                                     if _new_item_b.get("is_core") is False
                                                     else ""),
                                })
                                _sheet_synced.append(_code_b)
                            except (PolicySheetError, OAuthError) as _e_ws:
                                _fail.append(
                                    f"{_code_b} Sheet 同步: {str(_e_ws)[:30]}")
                    st.session_state.portfolio_funds.append(_new_item_b)

                # 完成後刷新 policy_tabs cache
                if _client_b and _sheet_synced:
                    try:
                        st.session_state["policy_tabs"] = (
                            list_policy_worksheets(_client_b, _sid_b))
                    except Exception as _e_ref:
                        st.caption(f"⚠️ 保單列表刷新失敗：{str(_e_ref)[:60]}")

                _update_data_registry()

                # ── 摘要訊息 ────────────────────────────────────────
                _msg_parts = [f"成功 {len(_succ)} 檔"]
                if _sheet_synced:
                    _msg_parts.append(f"☁️ Sheet 同步 {len(_sheet_synced)} 檔")
                if _skipped_dup:
                    _msg_parts.append(f"⏭️ 跳過 {len(_skipped_dup)} 檔已存在")
                if _fail:
                    _msg_parts.append(f"❌ 失敗 {len(_fail)} 檔")
                _summary = " · ".join(_msg_parts)
                if _fail:
                    st.error(f"批次加入完成 — {_summary}")
                    st.caption("**失敗明細**：")
                    for _f_msg in _fail[:10]:
                        st.caption(f"• {_f_msg}")
                    if len(_fail) > 10:
                        st.caption(f"…還有 {len(_fail) - 10} 筆")
                else:
                    st.success(f"✅ 批次加入完成 — {_summary}")
                st.rerun()

    pf = st.session_state.portfolio_funds
    if not pf:
        st.info("💡 請在上方輸入基金代碼加入，支援多檔同時比較")
    else:
        # 批次載入按鈕（v18.151：邏輯抽到 ui/helpers/portfolio_load.py）
        not_loaded = [i for i, f in enumerate(pf) if not f.get("loaded")]
        if not_loaded:
            from ui.helpers.portfolio_load import (
                batch_load_unloaded_funds as _batch_load,
                count_unloaded_funds as _count_unloaded,
            )
            _n_ent, _n_uniq = _count_unloaded()
            _btn_label = (
                f"📡 載入所有未載入基金（{_n_ent} 條 entry"
                + (f" / {_n_uniq} unique" if _n_uniq != _n_ent else "")
                + "）"
            )
            if st.button(_btn_label, type="primary", key="btn_pf_load_all"):
                _batch_load()

        # v18.30: 為主清單預計算 VIX（給每檔 advise_fund 用）
        _vix_t3_main = None
        try:
            _vix_t3_main = float(
                (st.session_state.get("compass_data") or {}).get("vix", {}).get("value"))
        except Exception:
            _vix_t3_main = None   # noqa: smoke-allow-pass — VIX 缺也能算 advice

        def _compute_advice_for(_pf_item: dict) -> dict:
            """v18.30: 從 pf_item 算出 advise_fund 需要的三組訊號 + 呼叫 advisor。
            失敗時回傳 grey '⏳ 資料不足'。"""
            try:
                _s_local = _pf_item.get("series")
                _m_local = _pf_item.get("metrics", {}) or {}
                _mj_local = _pf_item.get("moneydj_raw", {}) or {}
                _sigma = None
                if _s_local is not None and len(_s_local.dropna()) >= 30:
                    try:
                        from services.precision_service import calc_hwm_sigma_levels as _hwm_fn3
                        _sigma = _hwm_fn3(_s_local, lookback=252)
                    except Exception as _e_s:
                        _sigma = {"error": str(_e_s)[:60]}
                _div = None
                try:
                    _tret_l = float(_mj_local.get("perf", {}).get("1Y")
                                     or _m_local.get("ret_1y") or 0)
                    _dyld_l = float(_mj_local.get("moneydj_div_yield")
                                     or _m_local.get("annual_div_rate") or 0)
                    if _dyld_l > 0:
                        _div = div_safety_check(_tret_l, _dyld_l)
                except Exception:
                    _div = None   # noqa: smoke-allow-pass
                _ma = None
                if _s_local is not None and len(_s_local.dropna()) >= 65:
                    try:
                        _ma60_l = _s_local.dropna().rolling(60).mean()
                        if len(_ma60_l.dropna()) >= 5:
                            _ma = "up" if _ma60_l.iloc[-1] > _ma60_l.iloc[-5] else "down"
                    except Exception:
                        _ma = None   # noqa: smoke-allow-pass
                return advise_fund(_sigma, _div, _ma, _vix_t3_main)
            except Exception:
                return {"text": "⏳ 建議計算失敗",
                        "code": "ERROR", "color": "grey"}

        # v18.37 基金清單按保單號碼分組成 expander（預設收合）
        # 不再使用 v18.35 per-fund 內層 expander（外層保單 expander 已提供摺疊功能；
        # Streamlit 禁止 expander 巢狀，這裡刻意把詳細內容攤平在保單 expander 內）。
        from collections import defaultdict as _dd_pf_main
        _pf_by_pid: dict = _dd_pf_main(list)
        for i, pf_item in enumerate(pf):
            _pid_main = str(pf_item.get("policy_id", "") or "").strip() or "(未綁保單)"
            _pf_by_pid[_pid_main].append((i, pf_item))

        for _pid_main, _items_main in _pf_by_pid.items():
          with st.expander(f"📋 保單 **{_pid_main}**　·　{len(_items_main)} 檔基金", expanded=False):
            for i, pf_item in _items_main:
                status_icon = "✅" if (pf_item.get("loaded") and not pf_item.get("load_error")) else ("❌" if pf_item.get("load_error") else "⏳")
                m_i    = pf_item.get("metrics",{})
                rm_i   = pf_item.get("risk_metrics",{})
                rt_i   = rm_i.get("risk_table",{})
                role_i = "🛡️核心" if pf_item.get("is_core") else ("⚡衛星" if pf_item.get("is_core") is False else "")
                _nav_i  = m_i.get("nav") or (pf_item.get("moneydj_raw") or {}).get("nav_latest","")
                _adr_i  = (pf_item.get("moneydj_raw") or {}).get("moneydj_div_yield") or m_i.get("annual_div_rate","")
                _sh_i   = (rt_i.get("一年") or {}).get("Sharpe","")
                _std_i  = (rt_i.get("一年") or {}).get("標準差","")
                with st.container():
                    ci1, ci2, ci3 = st.columns([4,4,1])
                    with ci1:
                        st.markdown(
                            f"<div style='padding:8px 12px;background:#161b22;border-radius:8px;margin:3px 0'>"
                            f"{status_icon} <b style='color:#e6edf3'>{(pf_item.get('name','') or pf_item['code'])[:28]}</b> "
                            f"<span style='color:#888;font-size:11px'>{pf_item['code']}</span> "
                            f"<span style='color:#ff9800;font-size:11px;margin-left:6px'>{role_i}</span></div>",
                            unsafe_allow_html=True)
                    with ci2:
                        st.markdown(
                            f"<div style='padding:8px 12px;background:#161b22;border-radius:8px;margin:3px 0;font-size:11px;color:#888'>"
                            f"NAV: <b style='color:#e6edf3'>{_nav_i}</b>"
                            f"　配息率: <b style='color:#ff9800'>{_adr_i}{'%' if _adr_i else ''}</b>"
                            f"　Sharpe: <b style='color:#69f0ae'>{_sh_i}</b>"
                            f"　σ: <b>{_std_i}{'%' if _std_i else ''}</b></div>",
                            unsafe_allow_html=True)
                    with ci3:
                        if st.button("🗑️", key=f"del_pf_{i}", help=f"移除 {pf_item['code']}"):
                            st.session_state.portfolio_funds.pop(i)
                            st.rerun()

                    if pf_item.get("load_error"):
                        st.caption(f"⚠️ {pf_item['load_error']}")

                    # 詳細建議 + MK 訊號（攤平在保單 expander 內，不再用內層 expander）
                    _can_detail = pf_item.get("loaded") and not pf_item.get("load_error")
                    if _can_detail:
                        _adv_card = _compute_advice_for(pf_item)
                        _adv_clr_card = {
                            "red": "#f44336", "orange": "#ff9800", "yellow": "#ffeb3b",
                            "green": "#00c853", "grey": "#888"
                        }.get(_adv_card.get("color", "grey"), "#888")
                        st.markdown(
                            f"<div style='padding:6px 12px;background:#0d1117;"
                            f"border-left:3px solid {_adv_clr_card};"
                            f"border-radius:6px;margin:3px 0 8px 0;"
                            f"font-size:12px;color:{_adv_clr_card};line-height:1.55'>"
                            f"💡 {_adv_card.get('text', '—')}</div>",
                            unsafe_allow_html=True)

                        # ── MK v3.0 買賣訊號迷你卡（共用 Tab2 的 metrics）──
                        if m_i:
                            _mi_b1 = m_i.get("buy1");  _mi_b2 = m_i.get("buy2");  _mi_b3 = m_i.get("buy3")
                            _mi_s1 = m_i.get("sell1"); _mi_s2 = m_i.get("sell2"); _mi_s3 = m_i.get("sell3")
                            _mi_nav = float(m_i.get("nav") or 0)
                            _mi_pl  = m_i.get("pos_label","正常")
                            _mi_pc  = m_i.get("pos_color","#888")
                            _mi_bbd = m_i.get("bb_lower"); _mi_bbu = m_i.get("bb_upper")
                            _mi_NEAR = float(m_i.get("near_threshold_pct") or 2.0)
                            if _mi_b1 and _mi_nav > 0:
                                def _mini_chip(target, is_buy):
                                    if not target: return ("—", "#666")
                                    d = (_mi_nav - target) / target * 100
                                    if is_buy:
                                        if d <= 0:           return ("🟢", "#00e676")
                                        elif d <= _mi_NEAR:  return ("⚠️", "#ffa726")
                                        else:                return ("▲",  "#555")
                                    else:
                                        if d >= 0:           return ("🔔", "#f44336")
                                        elif d >= -_mi_NEAR: return ("⚠️", "#ffa726")
                                        else:                return ("▼",  "#555")
                                # 雙確認：σ 觸發 + 布林同向
                                _double_buy  = (_mi_b1 and _mi_nav <= _mi_b1) and (_mi_bbd and _mi_nav <= _mi_bbd)
                                _double_sell = (_mi_s1 and _mi_nav >= _mi_s1) and (_mi_bbu and _mi_nav >= _mi_bbu)
                                _badge = ""
                                if _double_buy:
                                    _badge = "<span style='background:#0a3a1a;color:#00e676;border:1px solid #00e676;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700;margin-left:6px'>🟢🟢 σ+布林 雙確認買</span>"
                                elif _double_sell:
                                    _badge = "<span style='background:#3a0a0a;color:#f44336;border:1px solid #f44336;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700;margin-left:6px'>🔔🔔 σ+布林 雙確認賣</span>"
                                # 6 個訊號方塊（從深買到深賣）
                                _cells = ""
                                for _v, _lbl, _is_buy in [
                                    (_mi_b3, "買3", True), (_mi_b2, "買2", True), (_mi_b1, "買1", True),
                                    (_mi_s1, "賣1", False),(_mi_s2, "賣2", False),(_mi_s3, "賣3", False),
                                ]:
                                    _ch, _cc = _mini_chip(_v, _is_buy)
                                    _cells += (f"<div style='flex:1;text-align:center;padding:4px 2px;"
                                               f"background:#0d1117;border-radius:6px;margin:0 2px'>"
                                               f"<div style='font-size:9px;color:#888'>{_lbl}</div>"
                                               f"<div style='font-size:11px;font-weight:700;color:#ccc'>{_v:.3f}</div>"
                                               f"<div style='font-size:13px;color:{_cc}'>{_ch}</div></div>")
                                st.markdown(
                                    f"<div style='background:#0d1117;border:1px solid #21262d;border-radius:8px;padding:8px 12px;margin:2px 0 8px 0'>"
                                    f"<div style='display:flex;align-items:center;margin-bottom:5px'>"
                                    f"<span style='color:#888;font-size:10px'>📍 策略3 訊號</span>"
                                    f"<span style='background:#111;color:{_mi_pc};border:1px solid {_mi_pc};padding:1px 8px;"
                                    f"border-radius:10px;font-size:10px;font-weight:700;margin-left:6px'>{_mi_pl}</span>"
                                    f"{_badge}"
                                    f"<span style='color:#555;font-size:10px;margin-left:auto'>NAV {_mi_nav:.4f}</span>"
                                    f"</div>"
                                    f"<div style='display:flex;align-items:stretch'>{_cells}</div>"
                                    f"</div>", unsafe_allow_html=True)

        # 核心/衛星目標設定
        st.divider()
        st.session_state.portfolio_core_pct = st.slider(
            "目標核心資產比例（%）", 50, 90,
            st.session_state.get("portfolio_core_pct",75), 5, key="slider_core_pct")

        # ── 真實收益長條圖（Core Protocol v2.0 Ch.4）────────────────
        # v18.38：分析視圖按 code 去重（同基金跨多保單只算一次），
        # 與 v18.34 MK 戰情室 / v18.36 T5 重疊度矩陣的去重策略一致。
        _loaded_pf_raw = [f for f in pf if f.get("loaded") and not f.get("load_error")]
        _seen_rc: set = set()
        _loaded_pf: list = []
        for _f in _loaded_pf_raw:
            _c = str(_f.get("code", "") or "").strip().upper()
            if not _c or _c in _seen_rc:
                continue
            _seen_rc.add(_c)
            _loaded_pf.append(_f)
        if _loaded_pf:
            st.divider()
            st.markdown("### 📊 真實收益 vs 配息率健康矩陣")
            st.caption("長條高度 < 紅虛線 → 含息報酬不足以支撐配息 → 吃本金警示")

            # v18.48 三層 fallback + is_real 旗標，正確區分「真 0%」與「資料不足」
            # v18.72: 加 _rc_src 追蹤每檔 1Y 來源，hover 顯示讓使用者一眼看出走哪條 fallback
            _rc_names, _rc_ret, _rc_div, _rc_real, _rc_src = [], [], [], [], []
            for _f in _loaded_pf:
                _mj  = _f.get("moneydj_raw", {}) or {}
                _m   = _f.get("metrics", {}) or {}
                _pf2 = _mj.get("perf", {}) or {}
                _name = (_f.get("name") or _f["code"])[:18]

                # v18.65: 真 1Y 優先 — perf["1Y"] (wb01 官方 / local_calc 注入只有真 1Y)
                # v18.134: 改用 compute_1y_total_return 共用 helper（與 Tab2 對齊）
                # 修使用者反饋「同一基金兩 view 顯示不同 1Y 報酬」
                from ui.helpers.macro_helpers import compute_1y_total_return
                _ret_v, _src_label = compute_1y_total_return(_f)
                _is_real = _ret_v is not None
                _ret_window_days = None    # v18.65 短窗口提示（helper 內部已標明來源）

                try:
                    _div = float(_mj.get("moneydj_div_yield") or _m.get("annual_div_rate") or 0)
                except Exception:
                    _div = 0.0
                # v18.49 配息率 fallback：從 divs 歷史推算（12M 累積配息 / 現價）
                if _div <= 0:
                    _divs_f = _f.get("dividends") or []
                    if _divs_f:
                        try:
                            import datetime as _dt_t3d
                            _ctf = _dt_t3d.datetime.now() - _dt_t3d.timedelta(days=365)
                            _sa = 0.0
                            for _dd in _divs_f:
                                _ds = (_dd.get("date") or "").replace("/", "-")
                                try:
                                    _dp = _dt_t3d.datetime.strptime(_ds[:10], "%Y-%m-%d")
                                except (ValueError, TypeError):
                                    continue
                                if _dp >= _ctf:
                                    _sa += float(_dd.get("amount", 0) or 0)
                            _nv = _m.get("nav") or _mj.get("nav_latest")
                            try: _nv = float(_nv) if _nv is not None else None
                            except (TypeError, ValueError): _nv = None
                            if _sa > 0 and _nv and _nv > 0:
                                _div = round((_sa / _nv) * 100.0, 2)
                        except Exception:
                            pass  # noqa: smoke-allow-pass — divs 歷史推算失敗不影響其他維度
                _rc_names.append(_name)
                _rc_ret.append(round(_ret_v, 2) if _ret_v is not None else 0.0)
                _rc_div.append(round(_div, 2))
                _rc_real.append(_is_real)
                _rc_src.append(_src_label if _is_real else "資料不足")

            if _rc_names:
                # v18.48 顏色：未有 1Y 真實值 → 灰（資料不足），避免誤判為吃本金
                _rc_colors = []
                for _r, _d, _real in zip(_rc_ret, _rc_div, _rc_real):
                    if not _real:
                        _rc_colors.append("#888")       # 資料不足 → 灰
                    elif _d > 0 and _r < _d:
                        _rc_colors.append("#f44336")   # 吃本金 → 紅
                    elif _d > 0 and _r < _d * 1.2:
                        _rc_colors.append("#ff9800")   # 邊緣 → 橙
                    else:
                        _rc_colors.append("#00c853")   # 健康 → 綠

                fig_rc = go.Figure()
                # 含息報酬率長條（吃本金時顯示最小高度 0.5 以確保可見）
                _rc_ret_vis = [max(_r, 0.5) if (_d > 0 and _r < _d) else _r
                               for _r, _d in zip(_rc_ret, _rc_div)]
                fig_rc.add_trace(go.Bar(
                    x=_rc_names, y=_rc_ret_vis,
                    name="含息報酬率(1Y)%",
                    marker_color=_rc_colors,
                    text=[f"{v:.1f}%" for v in _rc_ret],
                    textposition="outside",
                    customdata=list(zip(_rc_ret, _rc_src)),
                    hovertemplate=("%{x}<br>含息報酬：%{customdata[0]:.2f}%"
                                   "<br>來源：%{customdata[1]}<extra></extra>")))
                # 配息年化率紅色點線
                if any(d > 0 for d in _rc_div):
                    fig_rc.add_trace(go.Scatter(
                        x=_rc_names, y=_rc_div,
                        name="配息年化率%",
                        mode="markers+lines",
                        line=dict(color="#f44336", width=1.5, dash="dot"),
                        marker=dict(symbol="diamond", size=8, color="#f44336"),
                        hovertemplate="%{x}<br>配息率：%{y:.2f}%<extra></extra>"))
                # 零基準線
                fig_rc.add_hline(y=0, line_color="#555", line_width=1)
                # ── 吃本金：背景色塊 + 標註（v18.48 只在 1Y 真實值有取到時才標）──
                _y_max = max(max(_rc_ret_vis, default=10), max(_rc_div, default=10)) * 1.35
                for _i, (_r, _d, _n, _real) in enumerate(zip(_rc_ret, _rc_div, _rc_names, _rc_real)):
                    if _real and _d > 0 and _r < _d:
                        fig_rc.add_vrect(
                            x0=_i - 0.45, x1=_i + 0.45,
                            fillcolor="rgba(244,67,54,0.08)",
                            line_color="rgba(244,67,54,0.4)", line_width=1,
                            layer="below")
                        fig_rc.add_annotation(
                            x=_n, y=_y_max,
                            text=f"⚠️ 吃本金<br>缺口 {_d-_r:.1f}%",
                            showarrow=False,
                            font=dict(color="#f44336", size=11),
                            bgcolor="rgba(42,10,10,0.85)",
                            bordercolor="#f44336", borderwidth=1,
                            borderpad=4)
                    elif not _real and _d > 0:
                        # 缺 1Y 資料 → 顯示「資料不足」灰色標註，不誤判吃本金
                        fig_rc.add_annotation(
                            x=_n, y=_y_max,
                            text="⬜ 1Y 資料不足<br>無法判定",
                            showarrow=False,
                            font=dict(color="#aaa", size=10),
                            bgcolor="rgba(60,60,60,0.7)",
                            bordercolor="#666", borderwidth=1,
                            borderpad=4)
                fig_rc.update_layout(
                    paper_bgcolor="#0e1117", plot_bgcolor="#161b22",
                    font_color="#e6edf3", height=360,
                    margin=dict(t=40, b=20, l=40, r=20),
                    legend=dict(orientation="h", font_size=10, y=1.08),
                    yaxis_title="報酬率 / 配息率 (%)",
                    yaxis=dict(range=[min(0, min(_rc_ret, default=0)) - 2, _y_max]),
                    bargap=0.35, hovermode="x unified")
                st.plotly_chart(fig_rc, use_container_width=True)

                # v18.163：下方 4 卡 KPI 已移除（與 Tab3 頂部 hero KPI 重複）；
                # 詳細數字在 hero「💵 現金流安全」/「🔴 留校查看」見。


    # ─── 以下為原 with tab3: 第二段 (T5/T6/T7) ───────────────
    # ── T5: 持股相關性矩陣（v18.36 按保單分組）──────────────────────────────
    _pf_for_corr_raw = [f for f in st.session_state.portfolio_funds
                        if f.get("loaded") and f.get("series") is not None]

    # 按 policy_id 分組（無保單者歸入「(未綁保單)」），每組內按 code 去重，
    # 避免同 code 跨保單時 calc_holdings_overlap 回傳 DataFrame 重複欄名
    # 觸發 pyarrow `Duplicate column names found` 例外。
    from collections import defaultdict as _dd_t5
    _t5_buckets: dict = _dd_t5(list)
    for _ft5 in _pf_for_corr_raw:
        _pid_raw = str(_ft5.get("policy_id", "") or "").strip()
        _t5_buckets[_pid_raw or "(未綁保單)"].append(_ft5)
    _t5_groups: dict = {}
    for _pid_k, _items_k in _t5_buckets.items():
        _seen_c: set = set()
        _uniq_k: list = []
        for _ft5 in _items_k:
            _code_k = str(_ft5.get("code", "") or "").strip().upper()
            if not _code_k or _code_k in _seen_c:
                continue
            _seen_c.add(_code_k)
            _uniq_k.append(_ft5)
        if len(_uniq_k) >= 2:
            _t5_groups[_pid_k] = _uniq_k

    if _t5_groups:
        st.divider()
        st.markdown("### 📊 T5 底層持股 + 產業重疊度矩陣（按保單分組）")
        st.caption("以「持股 Jaccard × 0.6 + 產業 cosine × 0.4」綜合分;資料不齊自動降級為 NAV 相關係數。"
                   "重疊度 大於等於 0.70 → 影子基金警告。已依保單號碼分群，組內基金互相比較。")
        for _pid_g, _group_funds in _t5_groups.items():
            with st.expander(f"📋 保單 **{_pid_g}**　·　{len(_group_funds)} 檔基金", expanded=False):
                _btn_key = f"btn_corr_{_pid_g}"
                _ss_key  = f"corr_result_{_pid_g}"
                if st.button("🔗 計算基金重疊度", key=_btn_key):
                    from services.portfolio_service import calc_holdings_overlap as _calc_holdings_overlap
                    _hov_input = []
                    for f in _group_funds:
                        _mj = (f.get("moneydj_raw") or {})
                        _h = _mj.get("holdings") or {}
                        _hov_input.append({
                            "code": f.get("code", "?"),
                            "name": f.get("name") or f.get("code"),
                            "top_holdings": _h.get("top_holdings") or [],
                            "sector_alloc": _h.get("sector_alloc") or [],
                        })
                    _hov_result = _calc_holdings_overlap(_hov_input)
                    if (not _hov_result) or _hov_result.get("method") == "n/a":
                        _corr_input = [{"code": f.get("code","?"), "series": f.get("series")}
                                       for f in _group_funds]
                        _hov_result = calc_correlation_matrix(_corr_input)
                        if _hov_result is not None:
                            _hov_result.setdefault("method", "nav_fallback")
                            _freq_used = _hov_result.get("freq", "?")
                            _hov_result.setdefault("notes",
                                f"持股 / 產業資料皆缺，降級為 NAV Pearson 相關"
                                f"（{_freq_used}頻；>= 0.85 為 shadow）")
                    st.session_state[_ss_key] = _hov_result
                _cr = st.session_state.get(_ss_key)
                if _cr and _cr.get("matrix") is not None:
                    _method = _cr.get("method", "?")
                    _notes  = _cr.get("notes", "")
                    _is_nav_fb = _method == "nav_fallback"
                    _shadow = _cr.get("shadow_pairs", [])
                    _thr = 0.85 if _is_nav_fb else 0.70
                    _label = "相關係數" if _is_nav_fb else "重疊度"
                    st.info(f"📌 計算方式：**{_method}**（{_notes}）")
                    if _shadow:
                        st.error(
                            f"⚠️ **影子基金警告**：偵測到 {len(_shadow)} 對 {_label} 大於等於 {_thr} 的基金，"
                            "持有意義可能重疊！"
                        )
                        _holdings_by_code: dict = {}
                        if not _is_nav_fb:
                            for _f in _group_funds:
                                _mj_h = ((_f.get("moneydj_raw") or {}).get("holdings") or {})
                                _holdings_by_code[_f.get("code", "?")] = [
                                    (h.get("name") or "").strip()
                                    for h in (_mj_h.get("top_holdings") or [])
                                    if h.get("name")
                                ]
                        for _sa, _sb, _sv in _shadow:
                            _common_html = ""
                            if not _is_nav_fb:
                                _ha = _holdings_by_code.get(_sa, [])
                                _hb_upper = {n.upper() for n in _holdings_by_code.get(_sb, []) if n}
                                _common = [n for n in _ha if n and n.upper() in _hb_upper]
                                if _common:
                                    _items_zh = []
                                    for _n in _common[:6]:
                                        _zh = _zh_holding(_n)
                                        _items_zh.append(f"{_n[:18]}{f'({_zh})' if _zh else ''}")
                                    _more = f"…+{len(_common)-6}" if len(_common) > 6 else ""
                                    _common_html = (
                                        f"<div style='color:#ffb74d;font-size:11px;margin:2px 0 0 12px'>"
                                        f"🔁 共同持股 {len(_common)} 檔："
                                        f"{'、'.join(_items_zh)}{_more}</div>")
                            st.markdown(
                                f"- `{_sa}` × `{_sb}` — {_label} **{_sv:.3f}**{_common_html}",
                                unsafe_allow_html=True)
                    else:
                        st.success(f"✅ 各基金 {_label} 均在 {_thr} 以下，組合分散效果良好")
                    def _color_overlap(v, _thr=_thr):
                        try: f = float(v)
                        except Exception: return ""
                        if f >= _thr:    return "background-color:#b71c1c;color:#fff"
                        if f >= 0.50:    return "background-color:#ef6c00;color:#fff"
                        if f >= 0.20:    return "background-color:#558b2f;color:#fff"
                        if f >= -0.20:   return "background-color:#2e7d32;color:#fff"
                        return "background-color:#1565c0;color:#fff"
                    try:
                        _styled = _cr["matrix"].style.applymap(_color_overlap).format("{:.2f}")
                        st.dataframe(_styled, use_container_width=True)
                    except Exception:
                        st.dataframe(_cr["matrix"].round(2), use_container_width=True)
                    if _is_nav_fb:
                        st.caption(
                            "💡 NAV 相關法：1.0 = 漲跌完全一樣｜0.5~0.85 = 連動偏高｜0 = 無關｜負 = 反向。"
                            "🔴 大於等於 0.85 = 影子基金。"
                        )
                    else:
                        st.caption(
                            f"💡 持股 + 產業重疊度（method={_method}）：1.0 = 完全相同組合｜"
                            "0.7~1.0 = 影子基金 / 集中度過高｜0.4~0.7 = 中度重疊｜"
                            "0~0.3 = 分散良好。建議擇一持有 大於等於 0.7 的對。"
                        )

    # ── T7 帳務 + AI 深度組合建議 ── (v18.144 抽至 ui/tab3_t7_ledger.py)
    render_t7_section()

    # v18.159：通用 AI 白話文總結 widget（4 視角 selectbox）
    _render_tab3_ai_summary(GEMINI_KEY)


def _render_tab3_ai_summary(gemini_key: str) -> None:
    """v18.159 Tab3 末端：4 視角 AI 白話文總結 widget。
    v18.160：snapshot 加入「配息現金/單位拆分」估算（從 v2 編輯 buf 撈 div_cash_pct）。"""
    from ui.helpers.ai_summary import render_ai_summary_widget  # noqa: PLC0415
    from repositories.policy_repository import estimate_dividend_split  # noqa: PLC0415
    pf = st.session_state.get("portfolio_funds", []) or []
    loaded = [f for f in pf if f.get("loaded") and not f.get("load_error")]
    if not loaded:
        return  # 組合空，不掛 widget

    n_total = len(loaded)
    n_core = sum(1 for f in loaded if f.get("is_core", True))
    n_sat = n_total - n_core
    core_pct = (n_core / n_total * 100) if n_total else 0

    lines = [
        f"## 組合快照（{n_total} 檔）",
        f"- 核心 {n_core} 檔（{core_pct:.0f}%）｜衛星 {n_sat} 檔（{100 - core_pct:.0f}%）",
        "- MK 建議：核心 80% / 衛星 20%",
    ]
    _shown = 0
    for f in loaded[:8]:
        m = f.get("metrics") or {}
        name = f.get("name", "") or f.get("code", "") or "—"
        ret_1y = m.get("ret_1y_total") or m.get("ret_1y", "—")
        sharpe = m.get("sharpe", "—")
        std_1y = m.get("std_1y", "—")
        lines.append(
            f"- {name}（{'核心' if f.get('is_core', True) else '衛星'}）："
            f"1Y 報酬 {ret_1y}%　|　Sharpe {sharpe}　|　波動 {std_1y}%"
        )
        _shown += 1
    if n_total > _shown:
        lines.append(f"- …（其餘 {n_total - _shown} 檔略）")

    # v18.160：配息現金/單位拆分估算（從 _v2_buf 撈 user 已設定的 div_cash_pct）
    _v2_buf = st.session_state.get("_v2_buf", {}) or {}
    _div_lines: list[str] = []
    _total_cash, _total_reinv, _total_div = 0.0, 0.0, 0.0
    for _pid, _buf in _v2_buf.items():
        _fdf = _buf.get("fund") if isinstance(_buf, dict) else None
        if _fdf is None or _fdf.empty:
            continue
        for _, _r in _fdf.iterrows():
            _code = str(_r.get("fund_code", "") or "").strip()
            _inv = float(_r.get("invest_twd", 0) or 0)
            if not _code or _inv <= 0:
                continue
            # annual_div_rate 來自 portfolio_funds metrics（fund_code → metric）
            _adr = 0.0
            for _pf in loaded:
                if str(_pf.get("code", "") or "").upper() == _code.upper():
                    _m = _pf.get("metrics") or {}
                    _adr = float(_m.get("annual_div_rate") or 0)
                    break
            if _adr <= 0:
                continue   # 無實際配息率 → 跳過估算
            _est = estimate_dividend_split(
                invest_twd=_inv, annual_div_rate_pct=_adr,
                div_cash_pct=float(_r.get("div_cash_pct", 100) or 100),
                avg_nav=float(_r.get("avg_nav", 0) or 0),
                avg_fx=float(_r.get("avg_fx", 0) or 0),
            )
            _total_div += _est["annual_div_twd"]
            _total_cash += _est["cash_twd"]
            _total_reinv += _est["reinvest_twd"]
            if len(_div_lines) < 6:
                _div_lines.append(
                    f"  - {_code}（{_pid}）：現金{int(_est['cash_pct'])}%/"
                    f"單位{int(_est['unit_pct'])}%　年配息估{int(_est['annual_div_twd']):,} TWD"
                    f"（現金{int(_est['cash_twd']):,} / 再投入{int(_est['reinvest_twd']):,}）"
                )
    if _total_div > 0:
        lines.append("- **📊 年配息現金/單位拆分估算（v18.160 新增）**：")
        lines.append(
            f"  - 總計：年配息估 {int(_total_div):,} TWD"
            f"｜現金 {int(_total_cash):,} ({_total_cash/_total_div*100:.0f}%)"
            f"｜再投入 {int(_total_reinv):,} ({_total_reinv/_total_div*100:.0f}%)"
        )
        lines.extend(_div_lines)

    snapshot = "\n".join(lines)
    headlines = [str(n.get("title", "") or n.get("headline", ""))
                 for n in st.session_state.get("news_items", []) or []
                 if isinstance(n, dict)][:8]
    render_ai_summary_widget(
        tab_key="tab3",
        tab_label="組合戰情室",
        snapshot=snapshot,
        headlines=headlines,
        gemini_api_key=gemini_key,
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — 回測
