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
    get_gspread_client,
    get_gspread_client_from_oauth,
    get_sheet_title,
    list_policy_worksheets,
    list_user_sheets,
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
    from ui.helpers.oauth_state import (
        _oauth_configured,
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
            )

            _wbc1, _wbc2 = st.columns([1, 3])
            if _wbc1.button("💾 套用設定", type="primary",
                            use_container_width=True,
                            disabled=not (_w_cid.strip() and _w_csec.strip()
                                          and _w_uri.strip()),
                            key="btn_save_custom_oauth"):
                st.session_state["custom_oauth_cfg"] = {
                    "client_id":     _w_cid.strip(),
                    "client_secret": _w_csec.strip(),
                    "redirect_uri":  _w_uri.strip(),
                }
                st.success("✅ OAuth Client 設定已套用（session 有效），"
                           "可按「🔐 用 Google 登入」")
                st.rerun()
            _wbc2.caption(
                "ℹ️ Session-only：重整頁面後要重貼。"
                "若要永久生效，請把這三個值寫到 Streamlit Secrets `[google_oauth]` section。"
            )

        # ── Sheet ID 輸入 ───────────────────────────────────────────
        if _logged_in:
            _sheet_id_default = st.session_state.get("policy_sheet_id", _sheet_id_secret)
            _sheet_id_raw = st.text_input(
                "Google Sheet ID 或完整 URL（系統會自動解析 ID）",
                value=_sheet_id_default, key="inp_sheet_id",
            ).strip()
            # v18.39：使用者貼整段 URL → 自動萃取 ID；否則視為已是 ID。
            import re as _re_sid
            _m_sid = _re_sid.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", _sheet_id_raw)
            _sheet_id = _m_sid.group(1) if _m_sid else _sheet_id_raw
            if _sheet_id and _sheet_id != _sheet_id_default:
                st.session_state["policy_sheet_id"] = _sheet_id
            if _sheet_id_raw and _m_sid:
                st.caption(f"✅ 已從 URL 解析出 Sheet ID：`{_sheet_id}`")

            # v18.40 自動建立新 Sheet（OAuth 模式且尚未填 ID 時顯示）
            if _oauth_configured and not _sheet_id:
                st.caption("💡 還沒有 Google Sheet？讓 app 幫你建一個——不必先到 Drive 開檔。")
                _auto_c1, _auto_c2 = st.columns([3, 2])
                _auto_title = _auto_c1.text_input(
                    "新 Sheet 名稱", value="Fund Dashboard - 投資組合",
                    key="inp_auto_sheet_title",
                ).strip()
                _auto_c2.write("")
                if _auto_c2.button("🚀 自動建立 Sheet",
                                    key="btn_auto_create_sheet",
                                    use_container_width=True,
                                    disabled=not _auto_title):
                    try:
                        _client_ac = _get_oauth_client()
                        _new_sid, _new_url = create_dashboard_sheet(_client_ac, _auto_title)
                        st.session_state["policy_sheet_id"] = _new_sid
                        # v18.44 fix：widget key 已實體化不能直接寫入；刪掉讓 rerun 重 init
                        # 並從 policy_sheet_id（已更新）取 value
                        if "inp_sheet_id" in st.session_state:
                            del st.session_state["inp_sheet_id"]
                        st.success(
                            f"✅ 已建立新 Sheet `{_auto_title}` — ID `{_new_sid}` 已自動填入。"
                            f"下次登入 app 會記得此 ID，免重新貼。"
                        )
                        st.markdown(f"📂 [在 Google Drive 開啟此 Sheet]({_new_url})")
                        st.rerun()
                    except (PolicySheetError, OAuthError) as _ace:
                        # v18.43 偵測 insufficient scopes（drive.file 未授權）→ 提示重登入
                        _err_text = str(_ace)
                        if "insufficient authentication scopes" in _err_text.lower() or "403" in _err_text:
                            st.error(
                                "❌ 建立失敗：OAuth token 缺少 `drive.file` 權限。\n\n"
                                "**解法**：按上方「🚪 登出」→ 重新點「🔐 用 Google 登入」"
                                "（會重新跳出 Google 同意畫面，這次會勾選 Sheets + Drive 兩項）→ "
                                "回來再點「🚀 自動建立 Sheet」即可。"
                            )
                        else:
                            st.error(f"❌ 建立失敗：{_ace}")
                    except Exception as _ace2:
                        st.error(f"❌ 未預期錯誤：[{type(_ace2).__name__}] {_ace2}")

            # v18.45 從 Drive 既有 Sheets 挑（OAuth + Sheet ID 為空 OR 想換）
            if _oauth_configured:
                st.markdown("---")
                st.caption("📂 **或者** — 從你 Google Drive 內既有的 Sheets 挑一個：")
                _list_c1, _list_c2 = st.columns([2, 3])
                if _list_c1.button("📂 從 Drive 列出 Sheets",
                                    key="btn_list_drive_sheets",
                                    use_container_width=True,
                                    help="需要 OAuth `drive.metadata.readonly` 權限；若尚未授權請先登出再登入"):
                    try:
                        _client_ls = _get_oauth_client()
                        _files_ls = list_user_sheets(_client_ls)
                        st.session_state["_my_sheets"] = _files_ls
                        if not _files_ls:
                            st.info("ℹ️ Drive 內沒有 Google Sheets，或目前 token 只能看 app 建立的檔。")
                    except (PolicySheetError, OAuthError) as _lse:
                        _err_text = str(_lse)
                        if "insufficient" in _err_text.lower() or "403" in _err_text:
                            st.error(
                                "❌ 列檔失敗：OAuth token 缺少 `drive.metadata.readonly` 權限。\n\n"
                                "**解法**：按上方「🚪 登出」→ 重新「🔐 用 Google 登入」"
                                "（這次同意畫面會新增 Drive 中繼資料權限）→ 回來再試。"
                            )
                        else:
                            st.error(f"❌ 列檔失敗：{_lse}")
                    except Exception as _lse2:
                        st.error(f"❌ 未預期錯誤：[{type(_lse2).__name__}] {_lse2}")

                _my_sheets = st.session_state.get("_my_sheets") or []
                if _my_sheets:
                    _opt_labels = [f"📄 {f['name']}  (`{f['id'][:14]}…`)" for f in _my_sheets]
                    _sel_idx = st.selectbox(
                        f"清單共 {len(_my_sheets)} 個 Sheets — 選一個",
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
                        st.success(f"✅ 已選用 `{_picked['name']}` (ID `{_picked['id']}`)")
                        st.rerun()

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

            # ── v18.50 帳本內容速覽 + 一鍵存讀（解決「同一筆資料散在三個 tab，
            #          看不出全貌」的散亂感）──────────────────────────────
            if _sheet_id:
                st.markdown("---")
                st.markdown("##### 📊 帳本內容速覽（這本 Sheet 裡有什麼）")
                st.caption(
                    "同一張 Sheet 內 **3 種 tab**：保單分頁（基金清單與設定）／"
                    "`_T7_State`（部位快照）／`_Ledgers`（交易流水）。"
                    "平時下方各動作（批次加入、T7 套用）會自動同步到對應 tab；"
                    "若不確定哪個按鈕同步什麼，用這裡的「一鍵存／讀」。"
                )

                _ss_stats = st.session_state.get("_sheet_stats") or {}
                _sm1, _sm2, _sm3 = st.columns(3)
                _sm1.metric(
                    "📋 保單分頁",
                    _ss_stats.get("tabs", "—"),
                    help="一張保單 = 一個 tab，放該保單下的基金清單 / 級別 / 幣別"
                )
                _sm2.metric(
                    "📸 _T7_State 部位快照",
                    _ss_stats.get("t7_state", "—"),
                    help="T7 持倉的單位數 / 平均成本 / 匯率快照，重啟 app 用此還原"
                )
                _sm3.metric(
                    "📜 _Ledgers 交易流水",
                    _ss_stats.get("ledgers", "—"),
                    help="所有 buy / sell / dividend 事件 audit trail（append-only）"
                )
                if _ss_stats.get("last_sync"):
                    st.caption(f"⏱ _T7_State 最後同步：{_ss_stats['last_sync']}")

                st.markdown("##### 🧰 一鍵存讀（同步整本帳本）")
                _aa_c1, _aa_c2 = st.columns(2)
                _dump_all_clicked = _aa_c1.button(
                    "📦 全部寫入 Sheet（本地 → 雲端）",
                    key="btn_dump_all_v18_50", type="primary",
                    use_container_width=True,
                    help=("本地 → 雲端：把 portfolio_funds 寫進各保單分頁、"
                          "t7_ledgers 寫進 _T7_State。_Ledgers 為流水，"
                          "於落帳時自動 append，此處不重寫。")
                )
                _load_all_clicked = _aa_c2.button(
                    "📥 全部讀回（雲端 → 本地）",
                    key="btn_load_all_v18_50",
                    use_container_width=True,
                    help=("雲端 → 本地：保單分頁載入投資組合 + _T7_State 載回 T7 持倉。"
                          "_Ledgers 為流水備查，不覆蓋 t7_ledgers。")
                )
                _refresh_clicked = st.button(
                    "🔄 只重新整理分頁清單（不動投組）",
                    key="btn_policy_refresh", use_container_width=False,
                    help="只重整下方「保單分頁」下拉選單，不動投資組合資料"
                )
                # v18.58: 一鍵清空 fetch TTL 快取（強制下次抓 fresh NAV/FX/Macro）
                _cache_c1, _cache_c2 = st.columns([1, 3])
                if _cache_c1.button(
                    "🗑️ 清空抓取快取",
                    key="btn_clear_fetch_cache_v18_58",
                    use_container_width=True,
                    help=("清空 fund_fetcher / macro_core 的 TTL 快取，"
                          "下次抓取會走 fresh HTTP（盤中需要即時新值時用）。\n"
                          "預設 TTL：NAV/FX 5min、MoneyDJ 15min、Macro 5min、FRED 30min")
                ):
                    try:
                        from fund_fetcher import clear_all_caches as _cac
                        import repositories.macro_repository  # noqa: F401 — 觸發 macro 快取註冊
                        _n = _cac()
                        st.success(f"✅ 已清空 {_n} 個快取函式（下次抓取走 fresh HTTP）")
                    except Exception as _e_cc:
                        st.error(f"清空失敗：{str(_e_cc)[:120]}")
                with _cache_c2:
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

                if _dump_all_clicked:
                    try:
                        _client = _get_oauth_client() if _oauth_configured else \
                                  get_gspread_client(dict(_gsa_secret))
                        # 1) 把 portfolio_funds 寫回對應保單分頁
                        _written = 0
                        _skipped_no_pid = 0
                        for _f_dump in st.session_state.get("portfolio_funds", []):
                            _pid_d = str(_f_dump.get("policy_id", "") or "").strip()
                            _code_d = str(_f_dump.get("code", "") or "").strip().upper()
                            if not _pid_d:
                                _skipped_no_pid += 1
                                continue
                            if not _code_d:
                                continue
                            try:
                                upsert_fund_in_policy(_client, _sheet_id, _pid_d, {
                                    "fund_url":     _code_d,
                                    "policy_name":  _pid_d,
                                    "invest_twd":   int(_f_dump.get("invest_twd", 0) or 0),
                                    "invest_date":  "",
                                    "currency":     str(_f_dump.get("currency", "")),
                                    "fx_at_buy":    0.0,
                                    "notes":        "v18.50 全部寫入",
                                    "policy_tier":  ("core" if _f_dump.get("is_core")
                                                     else "satellite"
                                                     if _f_dump.get("is_core") is False
                                                     else ""),
                                })
                                _written += 1
                            except (PolicySheetError, OAuthError):
                                continue
                        # 2) _T7_State 快照
                        _t7_dict = st.session_state.get("t7_ledgers", {}) or {}
                        _funds_lookup = {fund_pk_str(_f): _f
                                         for _f in st.session_state.get("portfolio_funds", [])}
                        _n_state = 0
                        if _t7_dict:
                            try:
                                _n_state = save_all_ledgers_snapshot(
                                    _client, _sheet_id, _t7_dict, _funds_lookup)
                            except (PolicySheetError, OAuthError) as _e_sn:
                                st.warning(f"⚠️ _T7_State 寫入失敗：{str(_e_sn)[:120]}")
                        _refresh_sheet_stats(_client)
                        _msg_dump = [f"保單分頁 +{_written} 筆"]
                        if _n_state:
                            _msg_dump.append(f"_T7_State +{_n_state} 筆")
                        if _skipped_no_pid:
                            _msg_dump.append(f"略過未綁保單 {_skipped_no_pid} 檔")
                        st.success("📦 已寫入 Sheet：" + "、".join(_msg_dump))
                        st.rerun()
                    except (PolicySheetError, OAuthError) as _pe:
                        st.error(f"❌ Sheet 寫入失敗：{_pe}")
                    except Exception as _e:
                        st.error(f"❌ 未預期錯誤：[{type(_e).__name__}] {_e}")

                if _load_all_clicked or _refresh_clicked:
                    try:
                        _client = _get_oauth_client() if _oauth_configured else \
                                  get_gspread_client(dict(_gsa_secret))
                        # OAuth 模式走新 per-policy schema；SA 模式走舊 Policies 表
                        if _oauth_configured:
                            _pdf = load_all_policy_worksheets(_client, _sheet_id)
                            _tabs = list_policy_worksheets(_client, _sheet_id)
                            st.session_state["policy_tabs"] = _tabs
                        else:
                            _pdf = load_policies(_client, _sheet_id)
                        st.session_state["policies_df"] = _pdf

                        if _load_all_clicked:
                            _merged, _report = sync_policies_to_portfolio_funds(
                                _pdf, st.session_state.portfolio_funds)
                            st.session_state.portfolio_funds = _merged
                            _restored_ct = 0
                            try:
                                from services.ledger_service import Ledger as _LedT7_load
                                _restored = load_all_ledgers_snapshot(
                                    _client, _sheet_id, _LedT7_load)
                                if _restored:
                                    st.session_state["t7_ledgers"] = _restored
                                    _restored_ct = len(_restored)
                                    # v18.52: 同步 invest_twd 灌回 portfolio_funds，
                                    #         否則上方 KPI / 圓餅圖看不到單位數對應金額
                                    _sync_invest_twd_from_ledgers()
                                    # v18.52: 清除 auto-restore done flag，讓 T7 進入時
                                    #         不會被既有 flag 擋掉重新還原（rerun 後再判斷）
                                    st.session_state.pop("_t7_auto_restore_done", None)
                                    # v18.68: 同步重設自動估算 flag，讓 T7 重新對齊 invest_twd
                                    st.session_state.pop("_t7_auto_estimate_done", None)
                            except (PolicySheetError, OAuthError) as _e_ld:
                                st.warning(f"⚠️ _T7_State 讀回失敗：{str(_e_ld)[:120]}")
                            _refresh_sheet_stats(_client)
                            _msg_load = [
                                f"新增 {len(_report['added'])} 檔",
                                f"保留 {len(_report['kept'])} 檔",
                                f"移除 {len(_report['removed'])} 檔",
                            ]
                            if _restored_ct:
                                _msg_load.append(f"還原 T7 部位 {_restored_ct} 筆")
                            st.success("📥 全部讀回完成：" + " / ".join(_msg_load))
                            if _report["added"]:
                                st.caption(f"新增待載入：{', '.join(_report['added'])}（按下方批次載入）")
                        else:
                            _refresh_sheet_stats(_client)
                            st.success("✅ 保單列表已刷新")
                        st.rerun()
                    except (PolicySheetError, OAuthError) as _pe:
                        st.error(f"❌ Sheet 操作失敗：{_pe}")
                    except Exception as _e:
                        st.error(f"❌ 未預期錯誤：[{type(_e).__name__}] {_e}")

                _pdf_cached = st.session_state.get("policies_df")
                if _pdf_cached is not None and not _pdf_cached.empty:
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

                # ── v18.70: 本機 JSON 備份（從 T7 區移上來，與雲端存讀同類整合）─────
                st.markdown("---")
                st.markdown("##### 📁 本機 JSON 備份（不依賴網路，可離線還原）")
                import json as _json_pm
                import datetime as _dt_pm

                def _pm_export_payload() -> dict:
                    """v18.70: 統一存檔邏輯。剝掉 series / moneydj_raw 等大物件。"""
                    _slim_funds = []
                    for _f_e in st.session_state.get("portfolio_funds", []):
                        _slim_funds.append({
                            "code":         _f_e.get("code", ""),
                            "name":         _f_e.get("name", ""),
                            "invest_twd":   _f_e.get("invest_twd", 0),
                            "policy_id":    _f_e.get("policy_id", ""),
                            "policy_name":  _f_e.get("policy_name", ""),
                            "policy_tier":  _f_e.get("policy_tier", ""),
                            "currency":     _f_e.get("currency", ""),
                            "is_core":      _f_e.get("is_core"),
                            "invest_date":  _f_e.get("invest_date", ""),
                            "fx_at_buy":    _f_e.get("fx_at_buy"),
                        })
                    _ledgers_dict = {pk: l.to_dict()
                                     for pk, l in st.session_state.get("t7_ledgers", {}).items()}
                    return {
                        "schema_version":    "1.0",
                        "exported_at":       _dt_pm.datetime.now().isoformat(timespec="seconds"),
                        "portfolio_funds":   _slim_funds,
                        "t7_ledgers":        _ledgers_dict,
                        "t7_scenarios":      list(st.session_state.get("t7_scenarios", [])),
                        "active_policy_id":  st.session_state.get("active_policy_id", ""),
                        "policy_sheet_id":   st.session_state.get("policy_sheet_id", ""),
                    }

                _pm_payload = _pm_export_payload()
                _pm_payload_bytes = _json_pm.dumps(
                    _pm_payload, ensure_ascii=False, indent=2
                ).encode("utf-8")
                _pm_ts = _dt_pm.datetime.now().strftime("%Y%m%d_%H%M%S")
                _pm_filename = f"fund_dashboard_backup_{_pm_ts}.json"

                _pm_c1, _pm_c2 = st.columns(2)
                _pm_c1.download_button(
                    "💾 下載 JSON 備份",
                    data=_pm_payload_bytes,
                    file_name=_pm_filename,
                    mime="application/json",
                    use_container_width=True,
                    help=f"含 {len(_pm_payload['portfolio_funds'])} 檔基金 + "
                         f"{len(_pm_payload['t7_ledgers'])} 筆 ledger + "
                         f"{len(_pm_payload['t7_scenarios'])} 個方案",
                )
                _pm_uploaded = _pm_c2.file_uploader(
                    "📂 上傳 JSON 還原",
                    type=["json"], key="pm_upload_json_v18_70",
                    label_visibility="visible",
                )
                if _pm_uploaded is not None:
                    try:
                        _pm_data_in = _json_pm.loads(_pm_uploaded.read().decode("utf-8"))
                        if not isinstance(_pm_data_in, dict) or "portfolio_funds" not in _pm_data_in:
                            st.error("❌ 檔案格式不正確（必須含 portfolio_funds 欄位）")
                        else:
                            from services.ledger_service import Ledger as _LedT7_pm
                            _pm_restored_funds = []
                            for _f_i in _pm_data_in.get("portfolio_funds", []):
                                _f_i.update({"loaded": False, "load_error": None})
                                _pm_restored_funds.append(_f_i)
                            st.session_state.portfolio_funds = _pm_restored_funds
                            _pm_restored_led = {}
                            for _pk_i, _d_i in (_pm_data_in.get("t7_ledgers", {}) or {}).items():
                                try:
                                    _pm_restored_led[_pk_i] = _LedT7_pm.from_dict(_d_i)
                                except Exception:
                                    continue
                            st.session_state.t7_ledgers = _pm_restored_led
                            st.session_state.t7_scenarios = list(
                                _pm_data_in.get("t7_scenarios", []) or [])
                            if _pm_data_in.get("policy_sheet_id"):
                                st.session_state["policy_sheet_id"] = _pm_data_in["policy_sheet_id"]
                            if _pm_data_in.get("active_policy_id"):
                                st.session_state["active_policy_id"] = _pm_data_in["active_policy_id"]
                            # 清掉 auto-restore flag 讓 T7 重新對齊
                            st.session_state.pop("_t7_auto_restore_done", None)
                            st.success(
                                f"✅ 已還原 {len(_pm_restored_funds)} 檔基金 + "
                                f"{len(_pm_restored_led)} 筆 ledger。"
                                "請按「📡 載入所有未載入基金」重新抓取即時資料。"
                            )
                            st.rerun()
                    except Exception as _e_pm:
                        st.error(f"❌ JSON 解析失敗：{str(_e_pm)[:120]}")

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
        # 批次載入按鈕
        not_loaded = [i for i, f in enumerate(pf) if not f.get("loaded")]
        if not_loaded:
            # v18.58: 同 code 跨多保單只 fetch 一次 — 先 dedupe，再 broadcast 給 N 個 pf_item
            _uniq_codes_load = sorted({
                str(st.session_state.portfolio_funds[i].get("code","")).strip()
                for i in not_loaded
            } - {""})
            _btn_label = (
                f"📡 載入所有未載入基金（{len(not_loaded)} 條 entry"
                + (f" / {len(_uniq_codes_load)} unique" if len(_uniq_codes_load) != len(not_loaded) else "")
                + "）"
            )
            if st.button(_btn_label, type="primary", key="btn_pf_load_all"):
                # v18.60: 載入前先清 fetch 快取，確保用最新 calc_metrics 邏輯
                # （避免 v18.58 cache hold 住 pre-fix 的結果，使用者抓到舊算法）
                try:
                    from fund_fetcher import clear_all_caches as _cac_btn
                    import repositories.macro_repository  # noqa: F401 — 觸發 macro 快取註冊
                    _cac_btn()
                except Exception:
                    pass   # noqa: smoke-allow-pass — clear 失敗不擋 loading
                _errors = []
                _code_cache_b: dict = {}
                # v18.79: 用 st.status + progress bar 取代 per-iter st.spinner
                #         每檔 30s+ × 7 unique = 3.5min，原本完全沒進度更新使用者
                #         會誤判「沒有動作」；現在每抓完一檔即時 log + 進度條動。
                _n_uniq = len(_uniq_codes_load)
                with st.status(f"📡 開始載入 {_n_uniq} 個 unique codes（每檔約 30s）...",
                                expanded=True) as _ld_status:
                    _ld_prog = st.progress(0.0)
                    for cnt_c, _code_b2 in enumerate(_uniq_codes_load):
                        _ld_status.update(
                            label=f"📡 載入 {_code_b2} ({cnt_c+1}/{_n_uniq})")
                        try:
                            _code_cache_b[_code_b2] = fetch_fund_from_moneydj_url(_code_b2)
                            _nm_ok = (_code_cache_b[_code_b2].get("fund_name") or "")[:18]
                            st.write(f"✅ `{_code_b2}` {_nm_ok}")
                        except Exception as _le_c:
                            _code_cache_b[_code_b2] = {"error": str(_le_c)[:80]}
                            st.write(f"❌ `{_code_b2}` 失敗：{str(_le_c)[:80]}")
                        _ld_prog.progress((cnt_c + 1) / _n_uniq)
                    _ld_status.update(label=f"✅ 完成 — 抓到 {_n_uniq} 個 unique codes",
                                       state="complete", expanded=False)
                # Step 2: broadcast 到每個 pf_item（同 code 共用同一份 raw）
                for i in not_loaded:
                    pf_item = st.session_state.portfolio_funds[i]
                    _c_pf = str(pf_item.get("code","")).strip()
                    pf_raw = _code_cache_b.get(_c_pf, {"error": "no code"})
                    if pf_raw.get("error"):
                        _errors.append(f"{pf_item['code']}: {pf_raw['error']}")
                        st.session_state.portfolio_funds[i].update({"loaded":True,"load_error":pf_raw["error"]})
                    else:
                        st.session_state.portfolio_funds[i].update({
                            "name":       pf_raw.get("fund_name") or pf_item["code"],
                            "series":     pf_raw.get("series"),
                            "dividends":  pf_raw.get("dividends",[]),
                            "metrics":    pf_raw.get("metrics",{}),
                            "moneydj_raw":pf_raw,
                            "risk_metrics":pf_raw.get("risk_metrics",{}),
                            "is_core":    _is_core_fund(pf_raw.get("fund_name") or pf_item["code"]),
                            # v18.18: 補 currency 讓 Tab5 footer 顯示
                            "currency":   pf_raw.get("currency","") or pf_raw.get("metrics",{}).get("currency",""),
                            "loaded":     True, "load_error": None,
                        })
                if _errors:
                    st.warning("部分基金載入失敗：\n" + "\n".join(_errors))
                _update_data_registry()
                st.rerun()

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

                # v18.48 吃本金統計摘要：排除「1Y 資料不足」的基金
                _eat_n = sum(1 for r, d, real in zip(_rc_ret, _rc_div, _rc_real)
                             if real and d > 0 and r < d)
                _na_n  = sum(1 for real in _rc_real if not real)
                _ok_n  = len(_rc_names) - _eat_n - _na_n
                _sc1, _sc2, _sc3, _sc4 = st.columns(4)
                _sc1.metric("組合基金數", len(_rc_names))
                _sc2.metric("✅ 現金流健康", _ok_n)
                _sc3.metric("🔴 吃本金警示", _eat_n,
                            delta=f"-{_eat_n} 檔需檢視" if _eat_n else None,
                            delta_color="inverse")
                _sc4.metric("⬜ 1Y 資料不足", _na_n,
                            help="這些基金的 1Y 含息報酬無法從 metrics / perf / NAV 任一來源取得，"
                                 "暫不納入吃本金判定（避免誤判）")


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
                            _hov_result.setdefault("notes",
                                "持股 / 產業資料皆缺，降級為 NAV Pearson 相關（>= 0.85 為 shadow）")
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

    # ── T7: 帳務與再平衡試算 (Universal Fund Ledger v1.0) ─────────────────────
    st.divider()
    st.markdown("### 💰 T7 帳務與再平衡試算（A / B / C）")
    st.caption(
        "v1.0 加權平均會計引擎。NAV / FX 一律由 yfinance 即時抓取，"
        "使用者只填「投入金額」與「目標權重」。帳本以記憶體保留至重新整理頁面為止——"
        "本工具定位為「先試算、後落帳」。"
    )

    _pf_t7 = [f for f in st.session_state.portfolio_funds if f.get("loaded")]
    if not _pf_t7:
        st.info("ℹ️ 請先在上方「組合管理」載入至少一檔基金後，再使用 A/B/C 試算。")
    else:
        try:
            from services.ledger_service import Ledger as _LedT7, Switch as _SwT7
            from fund_fetcher import get_latest_fx as _fx_now, get_latest_nav as _nav_now
            _T7_OK = True
        except ImportError as _e:
            _T7_OK = False
            st.error(f"⚠️ T7 引擎尚未就緒：{_e}")

        if _T7_OK:
            from datetime import date as _d_t7

            if "t7_ledgers" not in st.session_state:
                st.session_state.t7_ledgers = {}

            # ── P2 一次性遷移：舊 session 中 code-only 鍵 → (policy_id, code) ──
            _t7_migrated = migrate_ledger_dict(
                st.session_state.t7_ledgers, st.session_state.portfolio_funds
            )
            if _t7_migrated != st.session_state.t7_ledgers:
                st.session_state.t7_ledgers = _t7_migrated

            # ── v18.29 helper：T7 帳本 ↔ Google Sheets `_T7_State` 雙向直連 ──
            def _t7_get_gsheet_client_sid():
                """回傳 (client, sheet_id)；OAuth 未配/未登入/sheet_id 未設 → (None, None)。"""
                _cfg_s = _resolve_oauth_cfg()
                _toks_s = st.session_state.get("gsheet_tokens")
                _sid_s = st.session_state.get("policy_sheet_id")
                if not (_cfg_s and _toks_s and _sid_s):
                    return None, None
                try:
                    _t_s = ensure_fresh_tokens(dict(_toks_s),
                        _cfg_s["client_id"], _cfg_s["client_secret"])
                    st.session_state["gsheet_tokens"] = _t_s
                    _creds_s = build_credentials_from_tokens(_t_s,
                        _cfg_s["client_id"], _cfg_s["client_secret"])
                    return get_gspread_client_from_oauth(_creds_s), _sid_s
                except (PolicySheetError, OAuthError):
                    return None, None
                except Exception:
                    return None, None

            def _t7_save_snapshot_to_sheets() -> str:
                """落帳完成後呼叫：把目前 t7_ledgers 全表寫進 _T7_State。
                回傳 status 字串給 success message 附在後面（成功 ' + State N 筆' / 失敗 ' ⚠️ ...'）。"""
                _c_s, _sid_s = _t7_get_gsheet_client_sid()
                if not _c_s:
                    return ""
                try:
                    _funds_lookup = {fund_pk_str(f): f
                                     for f in st.session_state.get("portfolio_funds", [])}
                    _n = save_all_ledgers_snapshot(
                        _c_s, _sid_s,
                        st.session_state.t7_ledgers, _funds_lookup)
                    return f" + _T7_State 寫 {_n} 筆"
                except (PolicySheetError, OAuthError) as _e_ss:
                    return f" ⚠️ _T7_State 同步失敗：{str(_e_ss)[:200]}"
                except Exception as _e_ss:
                    return f" ⚠️ _T7_State 例外：[{type(_e_ss).__name__}] {str(_e_ss)[:200]}"

            def _t7_load_snapshot_from_sheets() -> tuple:
                """從 _T7_State 還原 t7_ledgers。回傳 (count, error_msg)。"""
                _c_s, _sid_s = _t7_get_gsheet_client_sid()
                if not _c_s:
                    return 0, "OAuth 未登入或 sheet_id 未設"
                try:
                    _restored = load_all_ledgers_snapshot(_c_s, _sid_s, _LedT7)
                    if _restored:
                        st.session_state.t7_ledgers = _restored
                        _sync_invest_twd_from_ledgers()
                    return len(_restored), ""
                except (PolicySheetError, OAuthError) as _e_ld:
                    return 0, str(_e_ld)[:120]
                except Exception as _e_ld:
                    return 0, str(_e_ld)[:120]

            # ── v18.29: T7 entry 自動還原 — 只當 t7_ledgers 為空且 OAuth 已登入時 ──
            if (not st.session_state.t7_ledgers
                    and st.session_state.get("gsheet_tokens")
                    and st.session_state.get("policy_sheet_id")
                    and not st.session_state.get("_t7_auto_restore_done")):
                _n_r, _err_r = _t7_load_snapshot_from_sheets()
                st.session_state["_t7_auto_restore_done"] = True
                if _n_r > 0:
                    st.info(f"☁️ 已從 `_T7_State` 自動還原 {_n_r} 筆 ledger（重整頁面後雲端帳本仍在）")

            # v18.70: T7「💾 帳本存檔...」整段已移到上方「📋 保單管理」expander，
            #         避免「上下兩個存讀位置」的混亂。Sheets 直連登入也合併到上方。

            # ── 反查表：pk_str → fund dict（同 code 跨保單不衝突） ───────────
            _fund_by_pk = {fund_pk_str(f): f for f in _pf_t7}

            # v18.76: 幣別保底匯率（yfinance / Yahoo 在某些網路被擋時最終 fallback）
            #         手動微調可在「📝 編輯持倉」expander 改 fx_at_buy；此處只求數字「不歸 0」。
            _FX_FALLBACK = {
                "USD": 32.0, "EUR": 34.5, "HKD": 4.1, "JPY": 0.21,
                "AUD": 21.0, "GBP": 40.0, "CNY": 4.45, "CHF": 36.0,
                "SGD": 24.0, "CAD": 23.5, "NZD": 19.5, "ZAR": 1.75,
            }

            # v18.80: 幣別中英對照 — 使用者帳本常存中文（美元/台幣...），
            #         _FX_FALLBACK key 是 ISO，若不先正規化 .get("美元") 永遠回 None
            #         → 整批 fx=0 全部 skip auto-estimate。修正以後 USD/EUR/HKD/JPY 等
            #         中文名也能命中保底匯率。
            _CCY_NORMALIZE = {
                "美元": "USD", "美金": "USD",
                "歐元": "EUR",
                "港幣": "HKD", "港元": "HKD",
                "日圓": "JPY", "日元": "JPY",
                "澳幣": "AUD", "澳元": "AUD",
                "英鎊": "GBP",
                "人民幣": "CNY", "CNH": "CNY",
                "台幣": "TWD", "新台幣": "TWD", "新臺幣": "TWD",
                "瑞郎": "CHF", "瑞士法郎": "CHF",
                "新幣": "SGD", "新加坡幣": "SGD", "星幣": "SGD",
                "加幣": "CAD", "加元": "CAD",
                "紐幣": "NZD", "紐元": "NZD",
                "蘭特": "ZAR", "南非幣": "ZAR",
            }

            def _norm_ccy(_raw: str) -> str:
                """幣別正規化：中文 / ISO 都統一回 ISO 3 碼。未知則回原值大寫。"""
                _u = str(_raw or "USD").upper().strip()
                return _CCY_NORMALIZE.get(_u, _u)

            def _latest_nav_fx_t7(_fund: dict) -> tuple:
                _code = str(_fund.get("code", "")).strip()
                _ccy  = _norm_ccy(_fund.get("currency", "USD"))
                _nav  = _nav_now(_code)
                if _nav is None:
                    _s = _fund.get("series")
                    if _s is not None and len(_s.dropna()):
                        _nav = float(_s.dropna().iloc[-1])
                _fx = _fx_now(f"{_ccy}TWD") if _ccy != "TWD" else 1.0
                if _fx is None or _fx <= 0:
                    _fx = float(_fund.get("fx_rate", 0) or 0) or 0.0
                # v18.26: 最後一道 FX fallback — 用 ledger 的平均買入匯率
                #         （否則最新 FX 抓不到時市值整個歸 0 → -100% 報酬假象）
                if _fx <= 0:
                    try:
                        _pk_f = fund_pk_str(_fund)
                        _l_fb = st.session_state.t7_ledgers.get(_pk_f)
                        if _l_fb is not None:
                            _fx = float(getattr(_l_fb.position, "fx_avg", 0) or 0)
                    except Exception:
                        pass   # noqa: smoke-allow-pass — fallback 靜默：留 _fx=0 給上層 if 守
                # v18.76: 幣別保底匯率（YF 被擋 + 無 ledger 歷史時的最終救援）
                #         讓自動估算「不再因 FX 抓不到全部 skip」；
                #         準確匯率使用者可手動改 fx_at_buy。
                if _fx <= 0 and _ccy in _FX_FALLBACK:
                    _fx = _FX_FALLBACK[_ccy]
                return float(_nav or 0.0), float(_fx or 0.0)


            def _ledger_for(_pk: str) -> "_LedT7":
                """_pk 為 pk_str(make_pk(fund))。"""
                _led = st.session_state.t7_ledgers.get(_pk)
                if _led is None:
                    _f = _fund_by_pk.get(_pk)
                    _, _code = parse_pk(_pk)
                    _ccy = _norm_ccy((_f or {}).get("currency", "USD"))
                    _led = _LedT7(fund_code=_code, currency=_ccy)
                    st.session_state.t7_ledgers[_pk] = _led
                return _led

            # ── v18.68/v18.69: T7 entry 自動估算 — 進帳本就同步上方 invest_twd → 下方 ledger
            #            根因：上方 KPI 用 invest_twd（Sheet 直接讀），下方 T7 KPI 用
            #            ledger.units × NAV × FX。ledger 缺則下方歸 0，造成上下不一致。
            #            自動估算 units = invest_twd / (NAV × FX)，使用者進入 T7 即可看到
            #            完整數據；保留「📝 編輯初始持倉」expander 給手動微調。
            # v18.69 改進：移除 session-level flag（卡住問題），改 fund-level 自然冪等
            #              ledger.units > 0 → skip（守護手動值 + 防重複）；
            #              每次 rerun 重檢，NAV/FX 後續抓到也能估算
            # v18.81: 估算用「投資日期當天 NAV」做 cost，否則 cost = current → P&L 永遠 0
            def _nav_at_date_t7(_fund: dict, _date_str: str) -> float:
                """從 fund.series 取 _date_str <= 的最後一筆 NAV（asof），缺則回 0。"""
                if not _date_str:
                    return 0.0
                _s = _fund.get("series")
                if _s is None:
                    return 0.0
                try:
                    _s2 = _s.dropna().sort_index()
                    if len(_s2) == 0:
                        return 0.0
                    _dt = pd.Timestamp(_date_str)
                    _v = _s2.asof(_dt)
                    if pd.notna(_v) and float(_v) > 0:
                        return float(_v)
                except Exception:
                    pass   # noqa: smoke-allow-pass — asof 失敗回 0 讓上層走 fallback
                return 0.0

            _auto_est_count = 0
            _auto_est_skip_no_nav = 0
            _auto_est_skip_no_twd = 0
            for _f_ae in _pf_t7:
                _pk_ae = fund_pk_str(_f_ae)
                _twd_ae = float(_f_ae.get("invest_twd", 0) or 0)
                _ex_ae = st.session_state.t7_ledgers.get(_pk_ae)
                # 已有單位（手動值或上次自動估算）→ skip 守護
                if _ex_ae is not None and float(_ex_ae.position.units) > 0:
                    continue
                if _twd_ae <= 0:
                    _auto_est_skip_no_twd += 1
                    continue
                _nav_today, _fx_ae = _latest_nav_fx_t7(_f_ae)
                # v18.81: 優先用投資日期當天 NAV 做 cost；缺則 fallback 今天
                _invest_date_ae = str(_f_ae.get("invest_date", "") or "").strip()
                _nav_hist_ae = _nav_at_date_t7(_f_ae, _invest_date_ae) if _invest_date_ae else 0.0
                if _nav_hist_ae > 0:
                    _nav_for_cost = _nav_hist_ae
                    try:
                        _date_for_buy = pd.Timestamp(_invest_date_ae).date()
                    except Exception:
                        _date_for_buy = _d_t7.today()
                else:
                    _nav_for_cost = _nav_today   # fallback：series 缺或日期無解
                    _date_for_buy = _d_t7.today()
                if _nav_for_cost <= 0 or _fx_ae <= 0:
                    _auto_est_skip_no_nav += 1
                    continue
                _u_ae = round(_twd_ae / (_nav_for_cost * _fx_ae), 4)
                if _u_ae <= 0:
                    continue
                _c_ae = _f_ae.get("code", "?")
                _ccy_ae = _norm_ccy(_f_ae.get("currency", "USD"))
                _new_led_ae = _LedT7(fund_code=_c_ae, currency=_ccy_ae)
                _amt_ae = _u_ae * _nav_for_cost * _fx_ae
                _new_led_ae.subscribe(_amt_ae, _fx_ae, _nav_for_cost, _date_for_buy)
                st.session_state.t7_ledgers[_pk_ae] = _new_led_ae
                _auto_est_count += 1
            if _auto_est_count > 0:
                _sync_invest_twd_from_ledgers()
                try:
                    _t7_save_snapshot_to_sheets()
                except Exception:
                    pass   # noqa: smoke-allow-pass — dump 失敗不擋顯示
                _msg_skip = ""
                if _auto_est_skip_no_nav > 0:
                    _msg_skip = (f"（{_auto_est_skip_no_nav} 檔因 NAV 仍抓不到跳過 — "
                                 f"按「🗑️ 清空抓取快取」後重新載入再試）")
                st.success(
                    f"⚡ **自動估算 {_auto_est_count} 檔持倉** — "
                    f"`units = invest_twd ÷ (NAV_at_buy × FX)`；"
                    f"**cost NAV 用「投資日期當天 NAV」**（v18.81，可顯真實 P&L）"
                    f"若 yfinance 抓不到 FX 會用幣別保底匯率（USD≈32 / EUR≈34.5 / HKD≈4.1 ...）。"
                    f"已有 ledger 不會被覆寫；若要重估請按下方「🗑️ 重置帳本」清空後重進 T7。{_msg_skip}"
                )
            elif _auto_est_skip_no_nav > 0 and _auto_est_skip_no_twd == 0:
                # v18.76: 加了幣別保底匯率後，這條路徑通常只剩「NAV 真的抓不到」
                st.warning(
                    f"⚠️ **{_auto_est_skip_no_nav} 檔基金需自動估算但 NAV 抓不到** — "
                    f"請至「📋 保單管理」按「🗑️ 清空抓取快取」後重新載入基金。"
                    f"FX 已加幣別保底匯率，不該是擋點。"
                )

            def _sync_actions_to_sheet(rows_by_pid: dict) -> str:
                """v18.27: 把 T7 落帳交易（A/B/C/初始）同步寫進 _Ledgers tab。
                rows_by_pid: {policy_id: [{date, code, action, units, nav_at_action,
                                            twd, fee, note}, ...]}
                OAuth 未登入 / sheet_id 未設 → 靜默略過（本地 ledger 仍生效）。
                失敗不擋本地落帳，回傳警告字串給呼叫端附在 success message 上。"""
                if not rows_by_pid:
                    return ""
                _cfg_w = _resolve_oauth_cfg()
                _toks_w = st.session_state.get("gsheet_tokens")
                _sid_w = st.session_state.get("policy_sheet_id")
                if not (_cfg_w and _toks_w and _sid_w):
                    return ""
                try:
                    _t_w = ensure_fresh_tokens(dict(_toks_w),
                        _cfg_w["client_id"], _cfg_w["client_secret"])
                    st.session_state["gsheet_tokens"] = _t_w
                    _creds_w = build_credentials_from_tokens(_t_w,
                        _cfg_w["client_id"], _cfg_w["client_secret"])
                    _client_w = get_gspread_client_from_oauth(_creds_w)
                    _total_w = 0
                    for _pid_w, _rows_w in rows_by_pid.items():
                        if not _pid_w:
                            continue
                        for _r_w in _rows_w:
                            append_ledger_row(_client_w, _sid_w,
                                dict(_r_w, policy_id=_pid_w))
                            _total_w += 1
                    return (f" + Sheets `_Ledgers` +{_total_w} 筆"
                            if _total_w > 0 else "")
                except (PolicySheetError, OAuthError) as _e_w:
                    return f" ⚠️ Sheets 同步失敗：{str(_e_w)[:60]}"
                except Exception as _e_w:
                    return f" ⚠️ Sheets 例外：{str(_e_w)[:60]}"

            def _get_dy_t7(_fund: dict) -> float:
                """取得基金年化配息率 (%)，fallback：moneydj_div_yield → metrics.annual_div_rate → 0。"""
                _mj = _fund.get("moneydj_raw", {}) or {}
                try:
                    _v = (_mj.get("moneydj_div_yield")
                          or _fund.get("metrics", {}).get("annual_div_rate", 0)
                          or 0)
                    return float(_v)
                except Exception:
                    return 0.0

            # P2: 字典以 pk_str 為鍵，避免跨保單同代碼覆蓋
            _dy_lookup_t7 = {fund_pk_str(f): _get_dy_t7(f) for f in _pf_t7}
            _name_lookup_t7 = {fund_pk_str(f): (f.get("name") or f.get("code", "?"))
                               for f in _pf_t7}

            def _label_for_pk(_pk: str) -> str:
                """選單顯示用：「保單/代碼 – 基金名」；無保單顯示「(未綁)/代碼」。"""
                _pid, _code = parse_pk(_pk)
                _name = _name_lookup_t7.get(_pk, _code)[:24]
                _pid_disp = _pid if _pid else "(未綁)"
                return f"{_pid_disp}/{_code} – {_name}"

            # v18.52: _sync_invest_twd_from_ledgers 已 hoist 到模組層（line 358），
            # 此處 T7 區呼叫者透過 Python global scope 解析（NameError 修復）

            # ── v18.70: 「編輯持倉」改成預設展開的主視圖（不再藏 expander）
            with st.expander("✏️ 編輯持倉（手動微調 — 從 CHUBB 對帳單抄入精確值）",
                             expanded=True):
                st.caption(
                    "📝 把帳單上「持有單位 / 平均買入淨值 NAV / 平均買入匯率」一次貼進來，"
                    "並可在同一列指定保單號碼把該基金歸組（OAuth 已登入會同步寫進對應保單分頁）。"
                    "**自動估算結果**也可在這裡微調精確值。"
                )
                # v18.59: ledger ↔ fund 匹配診斷 — 救「重新 loading 後欄位變 0」困惑
                # (v18.56 改用複合鍵 pk_str = "pid::code"；若 _T7_State 是 v18.56 前
                #  存的 7 條 ledger，新 19 條 fund 中只有 7 條能匹配，剩 12 條顯 0)
                _t7_dbg_ledgers = st.session_state.get("t7_ledgers", {}) or {}
                _t7_dbg_fund_pks = {fund_pk_str(_f) for _f in _pf_t7}
                _t7_dbg_match    = _t7_dbg_fund_pks & set(_t7_dbg_ledgers.keys())
                _t7_dbg_orphan_l = set(_t7_dbg_ledgers.keys()) - _t7_dbg_fund_pks
                _t7_dbg_empty_f  = _t7_dbg_fund_pks - set(_t7_dbg_ledgers.keys())
                _t7_dbg_color = (
                    "#00c853" if len(_t7_dbg_match) == len(_pf_t7)
                    else "#ff9800" if _t7_dbg_match
                    else "#f44336"
                )
                st.markdown(
                    f"<div style='font-size:11px;color:{_t7_dbg_color};margin:4px 0'>"
                    f"🔍 持倉診斷：{len(_pf_t7)} 個 fund 條目 / "
                    f"{len(_t7_dbg_ledgers)} 個 ledger / "
                    f"<b>{len(_t7_dbg_match)} 條匹配</b>"
                    + (f" / ⚠️ {len(_t7_dbg_empty_f)} 個 fund 顯 0（無對應 ledger）"
                       if _t7_dbg_empty_f else "")
                    + (f" / 🗑 {len(_t7_dbg_orphan_l)} 個 ledger 找不到 fund（v18.56 前舊鍵）"
                       if _t7_dbg_orphan_l else "")
                    + "</div>",
                    unsafe_allow_html=True
                )
                if _t7_dbg_orphan_l:
                    st.caption(
                        "💡 **v18.56 鍵升級提示**：v18.56 前 ledger 用 fund_code 單鍵儲存，"
                        "若您之前是這樣存的，現在跨多保單同 code 只有第一筆能對到。"
                        "請手動補填其他保單條目的單位數，並按下方「💾 套用為起始部位」存檔；"
                        "或可去掉「🗑 ledger 找不到 fund」那些舊鍵（執行下方 🧹 清理孤立 ledger）。"
                    )
                    if st.button("🧹 清理孤立 ledger（無對應 fund 條目）",
                                 key="btn_clean_orphan_ledger_v18_59",
                                 help="把那些 ledger 鍵不在當前 portfolio_funds 的條目刪掉（v18.56 前舊鍵）"):
                        _n_clean = 0
                        for _k_orph in list(_t7_dbg_orphan_l):
                            st.session_state.t7_ledgers.pop(_k_orph, None)
                            _n_clean += 1
                        st.success(f"✅ 已清掉 {_n_clean} 個孤立 ledger，下次「📦 全部寫入」會覆寫 _T7_State")
                        st.rerun()

                # v18.66: ⚡ 從 invest_twd + 最新 NAV/FX 反推單位 — 救「上方有資料下方空」
                # 使用者在保單分頁輸入「投資金額」後，這裡可一鍵填出 ledger position
                # 估算公式: units = invest_twd / (latest_nav × latest_fx)
                _t7_can_estimate = []
                for _f_est in _pf_t7:
                    _pk_est = fund_pk_str(_f_est)
                    _twd_est = float(_f_est.get("invest_twd", 0) or 0)
                    if _twd_est <= 0:
                        continue
                    _nav_est, _fx_est = _latest_nav_fx_t7(_f_est)
                    if _nav_est <= 0 or _fx_est <= 0:
                        continue
                    _ex_est = st.session_state.t7_ledgers.get(_pk_est)
                    if _ex_est is not None and float(_ex_est.position.units) > 0:
                        continue   # 已有手動輸入值，不覆蓋
                    _u_est = round(_twd_est / (_nav_est * _fx_est), 4)
                    _t7_can_estimate.append((_pk_est, _f_est, _u_est, _nav_est, _fx_est))

                if _t7_can_estimate:
                    _est_c1, _est_c2 = st.columns([3, 1])
                    with _est_c1:
                        st.info(
                            f"⚡ **{len(_t7_can_estimate)} 檔基金有 invest_twd 但 ledger 為空**，"
                            f"可從「投資金額 ÷ 最新 NAV × FX」反推估算單位。\n"
                            f"按右側按鈕一鍵填入；估算值與實際對帳單可能有 0.1~1% 偏差，"
                            f"再依需要手動修正後按「💾 套用為起始部位」存檔。"
                        )
                    with _est_c2:
                        if st.button("⚡ 自動估算填入",
                                     key="btn_t7_auto_est_v18_66",
                                     type="primary",
                                     use_container_width=True):
                            for _pk_e, _f_e, _u_e, _nav_e, _fx_e in _t7_can_estimate:
                                _c_e = _f_e.get("code", "?")
                                _ccy_e = str(_f_e.get("currency", "USD")).upper()
                                _new_led_e = _LedT7(fund_code=_c_e, currency=_ccy_e)
                                _amt_e = _u_e * _nav_e * _fx_e
                                _new_led_e.subscribe(_amt_e, _fx_e, _nav_e, _d_t7.today())
                                st.session_state.t7_ledgers[_pk_e] = _new_led_e
                            _sync_invest_twd_from_ledgers()
                            # 自動 dump _T7_State
                            try:
                                _msg_dump_e = _t7_save_snapshot_to_sheets()
                            except Exception:
                                _msg_dump_e = ""
                            st.success(
                                f"✅ 已自動估算 {len(_t7_can_estimate)} 檔的單位數 "
                                f"（用最新 NAV × FX 反推）。{_msg_dump_e}"
                            )
                            st.rerun()

                with st.form("t7_init_pos_form", clear_on_submit=False):
                    _init_inputs = {}
                    for _f in _pf_t7:
                        _pk_f = fund_pk_str(_f)
                        _c = _f.get("code", "?")
                        _name = _name_lookup_t7.get(_pk_f, _c)
                        _ccy = str(_f.get("currency", "USD")).upper()
                        _pid_cur = _f.get("policy_id") or ""
                        _pid_disp = _pid_cur or "(未綁)"
                        _exist = st.session_state.t7_ledgers.get(_pk_f)
                        _u_default = float(_exist.position.units) if _exist else 0.0
                        _cu_default = float(_exist.position.cost_unit) if _exist else 0.0
                        _fx_default = float(_exist.position.fx_avg) if _exist else 0.0
                        st.markdown(f"**[{_pid_disp}] {_c} — {_name[:35]}**")
                        ic1, ic2, ic3, ic4 = st.columns([1, 1, 1, 1])
                        _u = ic1.number_input(
                            "持有單位數", min_value=0.0, max_value=10_000_000.0,
                            value=_u_default,
                            step=100.0, format="%.4f", key=f"t7_init_u_{_pk_f}",
                            help="從帳單『單位數』欄抄"
                        )
                        _cu = ic2.number_input(
                            f"平均買入淨值 NAV ({_ccy})", min_value=0.0, max_value=10000.0,
                            value=_cu_default,
                            step=0.01, format="%.4f", key=f"t7_init_cu_{_pk_f}",
                            help="= 你買進當下基金的單位淨值；NAV 通常 < 1000"
                        )
                        _fx = ic3.number_input(
                            f"平均買入匯率 ({_ccy}→TWD)", min_value=0.0, max_value=200.0,
                            value=_fx_default,
                            step=0.01, format="%.4f", key=f"t7_init_fx_{_pk_f}",
                            help="= 買進當下原幣對 TWD 即期匯率，如 1 USD = 31.50 TWD"
                        )
                        _pid_new = ic4.text_input(
                            "保單號碼", value=_pid_cur,
                            key=f"t7_init_pid_{_pk_f}",
                            placeholder="可選，e.g. PL-2024-001",
                            help="留空 = 不綁保單；若改變，會遷移 ledger 鍵與同步寫入新保單分頁"
                        )
                        _init_inputs[_pk_f] = (_c, _u, _cu, _fx, _ccy,
                                               _pid_cur, _pid_new.strip())
                    _init_submit = st.form_submit_button(
                        "💾 套用為起始部位（覆蓋 T7 帳本）", type="primary"
                    )
                if _init_submit:
                    _applied = 0
                    _per_policy_rows: dict[str, list[dict]] = {}
                    _pid_changes: list[tuple] = []   # v18.28: (old_pid, new_pid, code, fund)
                    for _pk_f, (_c, _u, _cu, _fx, _ccy,
                                _pid_old, _pid_new) in _init_inputs.items():
                        if _u <= 0 or _cu <= 0 or _fx <= 0:
                            continue
                        # v18.28: pid 變更 → 更新 fund.policy_id + 紀錄遷移
                        _f_obj = _fund_by_pk.get(_pk_f) or {}
                        if _pid_new != _pid_old:
                            _f_obj["policy_id"]   = _pid_new
                            _f_obj["policy_name"] = _pid_new or _f_obj.get("policy_name", "")
                            _pid_changes.append((_pid_old, _pid_new, _c, _f_obj))
                            # ledger key 從 "old_pid::code" → "new_pid::code"
                            _new_pk = fund_pk_str(_f_obj)
                            if _new_pk != _pk_f:
                                st.session_state.t7_ledgers.pop(_pk_f, None)
                                _pk_f = _new_pk
                        _new_led = _LedT7(fund_code=_c, currency=_ccy)
                        _amount_twd = _u * _cu * _fx
                        _new_led.subscribe(_amount_twd, _fx, _cu, _d_t7.today())
                        st.session_state.t7_ledgers[_pk_f] = _new_led
                        _applied += 1
                        # 雙寫到 _Ledgers（用 new pid）
                        _pid_w = _pid_new
                        if _pid_w:
                            _per_policy_rows.setdefault(_pid_w, []).append({
                                "date":          _d_t7.today().isoformat(),
                                "code":          _c,
                                "action":        "buy",
                                "units":         _u,
                                "nav_at_action": _cu,
                                "twd":           _amount_twd,
                                "fee":           0.0,
                                "note":          "T7 init position",
                            })
                    _sync_invest_twd_from_ledgers()

                    # P4 D2: dual-write to Google Sheets `_Ledgers` tab（OAuth 模式）
                    _gsheet_sync_msg = ""
                    _pid_migrate_msg = ""
                    if _per_policy_rows or _pid_changes:
                        _cfg = _resolve_oauth_cfg()
                        _tokens = st.session_state.get("gsheet_tokens")
                        _sid = st.session_state.get("policy_sheet_id")
                        if _cfg and _tokens and _sid:
                            try:
                                _t = ensure_fresh_tokens(dict(_tokens),
                                    _cfg["client_id"], _cfg["client_secret"])
                                st.session_state["gsheet_tokens"] = _t
                                _creds = build_credentials_from_tokens(_t,
                                    _cfg["client_id"], _cfg["client_secret"])
                                _client = get_gspread_client_from_oauth(_creds)
                                _total = 0
                                for _pid_w2, _rows_w2 in _per_policy_rows.items():
                                    _total += replace_ledgers_for_policy(
                                        _client, _sid, _pid_w2, _rows_w2)
                                _gsheet_sync_msg = (
                                    f" + Sheets `_Ledgers` 寫入 {_total} 筆")
                                # v18.28: pid 變更 → 寫 fund row 進新保單 worksheet
                                for _po, _pn, _code, _fobj in _pid_changes:
                                    if not _pn:
                                        continue
                                    try:
                                        upsert_fund_in_policy(_client, _sid, _pn, {
                                            "fund_url":     _code,
                                            "policy_name":  _pn,
                                            "invest_twd":   int(_fobj.get("invest_twd", 0) or 0),
                                            "invest_date":  "",
                                            "currency":     str(_fobj.get("currency", "")),
                                            "fx_at_buy":    0.0,
                                            "notes":        f"T7 pid migrate from '{_po or '(none)'}'",
                                            "policy_tier":  ("core" if _fobj.get("is_core")
                                                             else "satellite"
                                                             if _fobj.get("is_core") is False
                                                             else ""),
                                        })
                                    except (PolicySheetError, OAuthError) as _e_mi:
                                        _pid_migrate_msg = f" ⚠️ 保單分頁同步失敗：{str(_e_mi)[:60]}"
                                if _pid_changes:
                                    # 刷新 policy_tabs cache
                                    try:
                                        st.session_state["policy_tabs"] = (
                                            list_policy_worksheets(_client, _sid))
                                    except Exception:
                                        pass   # noqa: smoke-allow-pass — cache 刷失敗不擋
                            except (PolicySheetError, OAuthError) as _e_sy:
                                _gsheet_sync_msg = (
                                    f" ⚠️ Sheets 同步失敗：{str(_e_sy)[:60]}")
                            except Exception as _e_sy:
                                _gsheet_sync_msg = (
                                    f" ⚠️ Sheets 例外：{str(_e_sy)[:60]}")

                    if _applied > 0:
                        _pid_chg_summary = (
                            f"  • 保單號碼變更 {len(_pid_changes)} 檔"
                            if _pid_changes else ""
                        )
                        _msg_init_state = _t7_save_snapshot_to_sheets()
                        st.success(
                            f"✅ 已套用 {_applied} 檔起始部位{_pid_chg_summary}，T7 帳本已更新。"
                            f"{_gsheet_sync_msg}{_pid_migrate_msg}{_msg_init_state}"
                        )
                        st.rerun()
                    else:
                        st.warning("⚠️ 持有/NAV/匯率三欄都填 > 0 才會套用該檔基金。")

            # ── v18.4 方案 (scenario) 基礎建設 ───────────────────────────────
            if "t7_scenarios" not in st.session_state:
                st.session_state.t7_scenarios = []
            _T7_SCENARIO_LIMIT = 5

            def _t7_snapshot_ledgers() -> dict:
                """序列化成 dict[pk_str -> Ledger.to_dict()]（P2 後 key 為 "policy_id::code"）。"""
                return {pk: l.to_dict()
                        for pk, l in st.session_state.t7_ledgers.items()}

            def _t7_restore_ledgers(snap: dict) -> None:
                """把 snapshot 還原成主帳本（覆蓋 t7_ledgers）；接受 pk_str 鍵。"""
                st.session_state.t7_ledgers = {
                    pk: _LedT7.from_dict(d) for pk, d in snap.items()
                }

            def _t7_summary_from_ledgers(ledgers: dict,
                                          nav_fx_cache: dict | None = None) -> dict:
                """以給定 ledgers 計算總體 summary（市值/成本/未實現損益/月配息）。

                P2：ledgers 鍵改為 pk_str = "policy_id::code"。
                nav_fx_cache 仍以 pk_str 為鍵；落帳當下抓得到 NAV/FX，
                避免 panel 渲染時抓不到 → summary 抓到 0 的 bug（v18.5 行為延續）。
                """
                _v_total = _cost_total = _ann_total = 0.0
                _cache = nav_fx_cache or {}
                for _pk, _l in ledgers.items():
                    if _l.position.units <= 0:
                        continue
                    if _pk in _cache:
                        _nav, _fx = _cache[_pk]
                    else:
                        _f = _fund_by_pk.get(_pk)
                        if _f is None:
                            # fallback：用 ledger 自己的 cost basis 當保守估值
                            _nav = _l.position.cost_unit
                            _fx  = _l.position.fx_avg
                        else:
                            _nav, _fx = _latest_nav_fx_t7(_f)
                            if not (_nav and _fx):
                                _nav = _l.position.cost_unit
                                _fx  = _l.position.fx_avg
                    _dy = _dy_lookup_t7.get(_pk, 0.0)
                    _v = _l.position.value_twd(_nav, _fx) if (_nav and _fx) else 0
                    _cost = _l.position.net_investment_twd
                    _v_total += _v
                    _cost_total += _cost
                    _ann_total += _v * _dy / 100.0
                _pl = _v_total - _cost_total
                _pl_pct = (_pl / _cost_total * 100.0) if _cost_total > 0 else 0.0
                return {
                    "total_value_twd": round(_v_total, 0),
                    "total_cost_twd": round(_cost_total, 0),
                    "unrealized_pl_twd": round(_pl, 0),
                    "unrealized_pl_pct": round(_pl_pct, 2),
                    "monthly_cashflow_twd": round(_ann_total / 12, 0),
                    "annual_cashflow_twd": round(_ann_total, 0),
                }

            def _t7_save_scenario(name: str, action_type: str, details: str,
                                   nav_fx_cache: dict | None = None) -> None:
                """落帳完後把目前 t7_ledgers 快照存進 scenarios。超過上限覆蓋最舊。

                v18.5 修正：nav_fx_cache 用於 summary 計算 + 存進 scenario 供之後重算。
                """
                from datetime import datetime as _dt_now
                _snap = _t7_snapshot_ledgers()
                _ledgers_now = {c: _LedT7.from_dict(d) for c, d in _snap.items()}
                _summary = _t7_summary_from_ledgers(_ledgers_now, nav_fx_cache)
                _scenario = {
                    "id": f"sc_{int(_dt_now.now().timestamp() * 1000)}",
                    "name": name or f"{action_type} 方案",
                    "action_type": action_type,
                    "details": details[:200],
                    "snapshot": _snap,
                    "summary": _summary,
                    "nav_fx_cache": dict(nav_fx_cache or {}),
                    "created_at": _dt_now.now().strftime("%H:%M:%S"),
                }
                st.session_state.t7_scenarios.append(_scenario)
                if len(st.session_state.t7_scenarios) > _T7_SCENARIO_LIMIT:
                    st.session_state.t7_scenarios = (
                        st.session_state.t7_scenarios[-_T7_SCENARIO_LIMIT:]
                    )

            def _t7_build_navfx_cache() -> dict:
                """為所有 _pf_t7 預抓一次 NAV/FX，鍵為 pk_str（同 code 跨保單不衝突）。"""
                _cache = {}
                for _f in _pf_t7:
                    _pk_f = fund_pk_str(_f)
                    if not _pk_f or _pk_f == PK_SEP:
                        continue
                    _n, _x = _latest_nav_fx_t7(_f)
                    if _n and _x:
                        _cache[_pk_f] = (_n, _x)
                return _cache

            def _t7_run_in_scenario(action_callable) -> dict:
                """在 deepcopy 的 ledgers 上跑 action（避免污染主帳本），回傳 (snapshot, ledgers)。"""
                _backup_snap = _t7_snapshot_ledgers()
                try:
                    action_callable()
                    _new_snap = _t7_snapshot_ledgers()
                    _new_ledgers = {c: _LedT7.from_dict(d)
                                    for c, d in _new_snap.items()}
                    # 還原主帳本
                    _t7_restore_ledgers(_backup_snap)
                    return {"snapshot": _new_snap, "ledgers": _new_ledgers}
                except Exception as _e:
                    _t7_restore_ledgers(_backup_snap)
                    raise

            # 占位：tabs 處理完才渲染最新帳本，避免 1 cycle 過期
            _panel_ph = st.empty()

            _tA, _tB, _tC = st.tabs(
                ["A 新投入", "B 投入再平衡", "C 轉換再平衡 (Switch)"]
            )

            # ── A. 新投入 ───────────────────────────────────────────────────
            with _tA:
                st.caption("拿一筆新台幣加碼某檔（或多檔）基金。NAV / FX 即時自動抓取，使用者只填金額。")
                _a_mode = st.radio(
                    "加碼模式",
                    options=["既有基金", "新增基金"],
                    horizontal=True, key="t7a_mode",
                    help="既有基金 = 從目前組合中選；新增基金 = 直接輸入新代碼，submit 時自動載入 + 落帳"
                )
                # v18.81: A 新投入改為「保單先選 → 多選標的 → 各檔金額」
                #         policy + multiselect 必須在 form 外，否則 form 內無法即時 reactive
                _aopts = {fund_pk_str(f): f for f in _pf_t7}
                _a_selected_pks: list = []
                _a_sel_pid = ""
                if _a_mode == "既有基金":
                    def _pid_of_pk_a(_pk: str) -> str:
                        _ff = _aopts.get(_pk) or {}
                        return str(_ff.get("policy_id") or "").strip() or "(未綁)"
                    _a_policies = sorted({_pid_of_pk_a(p) for p in _aopts.keys()})
                    if _a_policies:
                        _a_sel_pid = st.selectbox(
                            "1️⃣ 先選保單號碼",
                            _a_policies, key="t7a_policy_pid",
                            help="同保單內可一次加碼多檔；跨保單請分次操作。",
                        )
                        _a_cands_pk = [p for p in _aopts.keys()
                                       if _pid_of_pk_a(p) == _a_sel_pid]
                        _a_selected_pks = st.multiselect(
                            "2️⃣ 選一檔或多檔標的（同一保單內）",
                            _a_cands_pk,
                            key=f"t7a_codes__{_a_sel_pid}",
                            format_func=lambda p: f"{_label_for_pk(p)}（{_aopts[p].get('currency','?')}）",
                            help="每檔下面會出現一個金額輸入框，可獨立填",
                        )
                    else:
                        st.caption("⚠️ 目前無基金可選 — 請先到 Tab3 上方加入基金 / 載入保單")

                with st.form("t7_form_a", clear_on_submit=False):
                    _apk = ""
                    _acode = ""
                    _a_new_code = ""
                    _aamt = 0
                    _a_amounts: dict = {}
                    if _a_mode == "既有基金":
                        if not _a_selected_pks:
                            st.caption("👆 先在上方選一檔以上的標的")
                        for _pk_a in _a_selected_pks:
                            _code_a_lbl = parse_pk(_pk_a)[1]
                            _name_a_full = str((_aopts.get(_pk_a) or {}).get("name", "")).strip()
                            _name_a_short = (_name_a_full[:14] + "…") if len(_name_a_full) > 14 else _name_a_full
                            _label_amt = (f"💵 {_code_a_lbl}｜{_name_a_short} 投入 (NTD)"
                                          if _name_a_short else f"💵 {_code_a_lbl} 投入 (NTD)")
                            _amt = st.number_input(
                                _label_amt, min_value=0, step=10000, value=300000,
                                key=f"t7a_amt__{_pk_a}",
                            )
                            _a_amounts[_pk_a] = float(_amt)
                        if _a_selected_pks:
                            _a_total = sum(_a_amounts.values())
                            st.caption(f"📊 合計投入：**NT${_a_total:,.0f}** "
                                       f"（{len(_a_selected_pks)} 檔）")
                    else:
                        _a_new_code = st.text_input(
                            "新基金代碼或 MoneyDJ URL",
                            placeholder="例：TLZF9 / ACTI71 / ...",
                            key="t7a_new_code",
                        )
                        _aamt = st.number_input(
                            "預計投入台幣 (NTD)", min_value=0, step=10000, value=300000,
                            key="t7a_amt_new"
                        )
                    if _a_mode == "新增基金":
                        st.info(
                            "ℹ️ 新增基金模式必須直接套用主帳本（會永久把該檔加入組合管理清單）。"
                            "若要試算多方案，請先在 Tab3 上方「組合管理」加入基金後，回此用「既有基金」模式。"
                        )
                        _a_commit_mode = "✅ 直接套用主帳本"
                        _a_scenario_name = ""
                    else:
                        _a_commit_mode = st.radio(
                            "落帳目標",
                            options=["💡 暫存為方案（不動主帳本）", "✅ 直接套用主帳本"],
                            horizontal=True, key="t7a_commit_mode",
                            help="暫存方案可同時保留多個（最多 5 個）並排比較；確認最佳方案後再「鎖定為主帳本」"
                        )
                        _a_scenario_name = st.text_input(
                            "方案名稱（暫存模式才用）",
                            placeholder="如：A 方案-加碼 TLZF9+ACCP138 各 30 萬",
                            key="t7a_scenario_name",
                        )
                    _asubmit = st.form_submit_button("💰 試算", type="primary")

                if _asubmit:
                    # ── 新增基金模式：fetch + append + 單檔 subscribe（原 flow）──
                    if _a_mode == "新增基金":
                        _new_code_clean = _a_new_code.strip().upper()
                        if not _new_code_clean:
                            st.error("❌ 請輸入新基金代碼或 URL。")
                            st.stop()
                        if any(f["code"] == _new_code_clean for f in
                               st.session_state.portfolio_funds):
                            st.warning(
                                f"⚠️ {_new_code_clean} 已在組合中，"
                                "請改用「既有基金」模式或先重新整理頁面。"
                            )
                            st.stop()
                        try:
                            with st.spinner(f"📡 抓取 {_new_code_clean}..."):
                                _new_raw = fetch_fund_from_moneydj_url(_new_code_clean)
                            if _new_raw.get("error"):
                                st.error(f"❌ 抓取失敗：{_new_raw['error']}")
                                st.stop()
                            _new_pf = {
                                "code":       _new_code_clean,
                                "invest_twd": 0,
                                "name":       _new_raw.get("fund_name") or _new_code_clean,
                                "series":     _new_raw.get("series"),
                                "dividends":  _new_raw.get("dividends", []),
                                "metrics":    _new_raw.get("metrics", {}),
                                "moneydj_raw":_new_raw,
                                "risk_metrics":_new_raw.get("risk_metrics", {}),
                                "is_core":    _is_core_fund(
                                    _new_raw.get("fund_name") or _new_code_clean),
                                "currency":   _new_raw.get("currency","")
                                              or _new_raw.get("metrics",{}).get("currency",""),
                                "loaded":     True, "load_error": None,
                            }
                            st.session_state.portfolio_funds.append(_new_pf)
                            _pf_t7.append(_new_pf)
                            _new_pk = fund_pk_str(_new_pf)
                            _aopts[_new_pk] = _new_pf
                            _fund_by_pk[_new_pk] = _new_pf
                            _name_lookup_t7[_new_pk] = (
                                _new_pf["name"] or _new_code_clean
                            )
                            _dy_lookup_t7[_new_pk] = _get_dy_t7(_new_pf)
                            _apk = _new_pk
                            _acode = _new_code_clean
                        except Exception as _e_new:
                            st.error(f"❌ 抓取例外：{_e_new}")
                            st.stop()

                        _afund = _aopts[_apk]
                        _anav, _afx = _latest_nav_fx_t7(_afund)
                        if _anav <= 0 or _afx <= 0:
                            st.error("❌ 無法取得最新 NAV 或 FX，請確認網路。")
                        elif _aamt <= 0:
                            st.error("❌ 投入金額必須大於 0。")
                        else:
                            _led = _ledger_for(_apk)
                            _new_u = _led.subscribe(
                                float(_aamt), _afx, _anav, _d_t7.today()
                            )
                            _sync_invest_twd_from_ledgers()
                            _pid_a_sync = parse_pk(_apk)[0]
                            _msg_a = _sync_actions_to_sheet({_pid_a_sync: [{
                                "date":          _d_t7.today().isoformat(),
                                "code":          _acode,
                                "action":        "buy",
                                "units":         _new_u,
                                "nav_at_action": _anav,
                                "twd":           float(_aamt),
                                "fee":           0.0,
                                "note":          "T7 A 加碼（新增基金）",
                            }]} if _pid_a_sync else {})
                            _msg_a_state = _t7_save_snapshot_to_sheets()
                            st.success(
                                f"✅ {_acode} 已加碼 NT${_aamt:,.0f} → "
                                f"+{_new_u:,.4f} 單位（已套用主帳本）{_msg_a}{_msg_a_state}"
                            )
                            c1, c2, c3 = st.columns(3)
                            c1.metric("即時 NAV", f"{_anav:.4f}")
                            c2.metric("即時 FX", f"{_afx:.4f}")
                            c3.metric("買入後總單位", f"{_led.position.units:,.4f}",
                                      delta=f"+{_new_u:,.4f}")

                    # ── 既有基金模式：多檔 batch（v18.81 新流程）──
                    else:
                        _a_n_valid = sum(1 for _v in _a_amounts.values() if _v > 0)
                        if _a_n_valid == 0:
                            st.error("❌ 請至少選一檔基金 + 填投入金額 > 0")
                            st.stop()
                        _is_scenario = _a_commit_mode.startswith("💡")
                        _baseline_snap_a = (_t7_snapshot_ledgers()
                                             if _is_scenario else None)
                        _bundled_lines: list = []
                        _sheet_rows_by_pid: dict = {}
                        _navfx_cache_a = _t7_build_navfx_cache()
                        _total_amt = 0.0
                        _total_div_twd = 0.0
                        _n_ok = 0
                        _skipped: list = []
                        for _pk_a in _a_selected_pks:
                            _amt_a = float(_a_amounts.get(_pk_a, 0.0) or 0.0)
                            if _amt_a <= 0:
                                continue
                            _f_a = _aopts.get(_pk_a)
                            _nav_a, _fx_a = _latest_nav_fx_t7(_f_a)
                            _code_a = parse_pk(_pk_a)[1]
                            if _nav_a <= 0 or _fx_a <= 0:
                                _skipped.append(f"`{_code_a}`（NAV/FX 抓不到）")
                                continue
                            _led_a = _ledger_for(_pk_a)
                            _new_u_a = _led_a.subscribe(
                                _amt_a, _fx_a, _nav_a, _d_t7.today()
                            )
                            _navfx_cache_a[_pk_a] = (_nav_a, _fx_a)
                            _total_amt += _amt_a
                            _dy_pk_a = _dy_lookup_t7.get(_pk_a, 0.0)
                            _total_div_twd += _amt_a * _dy_pk_a / 100.0
                            _n_ok += 1
                            _bundled_lines.append(
                                f"• `{_code_a}` NT${_amt_a:,.0f} → "
                                f"+{_new_u_a:.4f} 單位 @ NAV {_nav_a:.4f} / FX {_fx_a:.4f}"
                            )
                            _pid_a = parse_pk(_pk_a)[0]
                            if _pid_a:
                                _sheet_rows_by_pid.setdefault(_pid_a, []).append({
                                    "date":          _d_t7.today().isoformat(),
                                    "code":          _code_a,
                                    "action":        "buy",
                                    "units":         _new_u_a,
                                    "nav_at_action": _nav_a,
                                    "twd":           _amt_a,
                                    "fee":           0.0,
                                    "note":          "T7 A 加碼（多檔）",
                                })
                        if _skipped:
                            st.warning("⚠️ 跳過：" + "、".join(_skipped))
                        if _n_ok == 0:
                            st.error("❌ 沒有成功加碼任何標的")
                        else:
                            if _is_scenario:
                                _t7_save_scenario(
                                    name=_a_scenario_name or
                                          f"A 加碼 {_n_ok} 檔 NT${_total_amt:,.0f}",
                                    action_type="A",
                                    details="\n".join(_bundled_lines),
                                    nav_fx_cache=_navfx_cache_a,
                                )
                                _t7_restore_ledgers(_baseline_snap_a)
                                st.info(
                                    f"💡 已暫存方案「"
                                    f"{_a_scenario_name or f'A 加碼 {_n_ok} 檔'}"
                                    f"」，主帳本未變動。"
                                )
                            else:
                                _sync_invest_twd_from_ledgers()
                                _msg_a = _sync_actions_to_sheet(_sheet_rows_by_pid)
                                _msg_a_state = _t7_save_snapshot_to_sheets()
                                st.success(
                                    f"✅ 已加碼 **{_n_ok} 檔**（合計 "
                                    f"**NT${_total_amt:,.0f}**）— 已套用主帳本"
                                    + _msg_a + _msg_a_state
                                )
                            st.markdown("\n".join(_bundled_lines))
                            _c1, _c2, _c3 = st.columns(3)
                            _c1.metric("加碼檔數", f"{_n_ok}")
                            _c2.metric("合計投入", f"NT${_total_amt:,.0f}")
                            _c3.metric(
                                "本次新增預估年配息",
                                f"NT${_total_div_twd:,.0f}",
                                help=f"≈ 月均 NT${_total_div_twd/12:,.0f}"
                            )

            # ── B. 投入再平衡 ────────────────────────────────────────────────
            with _tB:
                st.caption(
                    "拿一筆新台幣按目標權重攤分到多檔基金。"
                    "依「投入後總市值 × 目標權重 − 目前市值」缺口比例分配。"
                )
                with st.form("t7_form_b", clear_on_submit=False):
                    _btot = st.number_input(
                        "預計投入總台幣 (NTD)", min_value=0, step=10000,
                        value=300000, key="t7b_amt"
                    )
                    st.markdown("**目標權重 (%)**（誤差 ≤ 0.5% 自動於最後一檔對齊）")
                    _bweights: dict = {}
                    _w_default = round(100.0 / max(len(_pf_t7), 1), 2)
                    _wcols = st.columns(min(len(_pf_t7), 4))
                    for _idx, _f in enumerate(_pf_t7):
                        _pk_f = fund_pk_str(_f)
                        _code = _f.get("code", "?")
                        _pid_disp = _f.get("policy_id") or "(未綁)"
                        # v18.73: 標籤加基金名稱，避免一片代碼看不出是哪檔
                        _name_full = str(_f.get("name") or "").strip()
                        _name_short = (_name_full[:10] + "…") if len(_name_full) > 10 else _name_full
                        _label = (f"{_pid_disp}/{_code}｜{_name_short} 權重 %"
                                  if _name_short else f"{_pid_disp}/{_code} 權重 %")
                        _help = (f"保單 {_pid_disp}｜{_name_full or _code}"
                                 f"｜代碼 {_code}")
                        _w = _wcols[_idx % len(_wcols)].number_input(
                            _label, min_value=0.0, max_value=100.0,
                            value=_w_default, step=1.0, key=f"t7b_w_{_pk_f}",
                            help=_help,
                        )
                        _bweights[_pk_f] = float(_w)
                    _b_commit_mode = st.radio(
                        "落帳目標",
                        options=["💡 暫存為方案（不動主帳本）", "✅ 直接套用主帳本"],
                        horizontal=True, key="t7b_commit_mode",
                    )
                    _b_scenario_name = st.text_input(
                        "方案名稱（暫存模式才用）",
                        placeholder="如：B 方案-30 萬攤至 5 檔",
                        key="t7b_scenario_name",
                    )
                    _bsubmit = st.form_submit_button(
                        "🧮 試算分配", type="primary"
                    )

                if _bsubmit:
                    _wsum = sum(_bweights.values())
                    if abs(_wsum - 100.0) > 0.5:
                        st.error(f"❌ 權重總和 = {_wsum:.2f}%，超出 ± 0.5% 容忍度。")
                    elif _btot <= 0:
                        st.error("❌ 投入總額必須大於 0。")
                    else:
                        _is_scenario_b = _b_commit_mode.startswith("💡")
                        _baseline_snap_b = (_t7_snapshot_ledgers()
                                             if _is_scenario_b else None)
                        _wn = dict(_bweights)
                        _last = list(_wn.keys())[-1]
                        _wn[_last] += (100.0 - _wsum)
                        _navfx = {}
                        _v_curr = {}
                        for _f in _pf_t7:
                            _pk_f = fund_pk_str(_f)
                            _n, _x = _latest_nav_fx_t7(_f)
                            _navfx[_pk_f] = (_n, _x, str(_f.get("currency", "USD")).upper())
                            _l = _ledger_for(_pk_f)
                            _v_curr[_pk_f] = (
                                _l.position.value_twd(_n, _x) if (_n and _x) else 0.0
                            )
                        _v_post = sum(_v_curr.values()) + float(_btot)
                        _gaps = {
                            p: max(_v_post * _wn[p] / 100.0 - _v_curr[p], 0.0)
                            for p in _wn
                        }
                        _g_sum = sum(_gaps.values())
                        _rows = []
                        _b_ann_total = 0.0
                        _b_rows_by_pid: dict[str, list[dict]] = {}   # v18.27 dual-write 收集
                        for _pk_g, _gap in _gaps.items():
                            _share_twd = (
                                float(_btot) * _gap / _g_sum if _g_sum > 0 else 0.0
                            )
                            _n, _x, _ccy = _navfx[_pk_g]
                            _orig = _share_twd / _x if _x > 0 else 0
                            _units = _orig / _n if _n > 0 else 0
                            if _share_twd > 0 and _n > 0 and _x > 0:
                                _ledger_for(_pk_g).subscribe(
                                    _share_twd, _x, _n, _d_t7.today()
                                )
                                _pid_g_b = parse_pk(_pk_g)[0]
                                if _pid_g_b:
                                    _b_rows_by_pid.setdefault(_pid_g_b, []).append({
                                        "date":          _d_t7.today().isoformat(),
                                        "code":          parse_pk(_pk_g)[1],
                                        "action":        "buy",
                                        "units":         _units,
                                        "nav_at_action": _n,
                                        "twd":           _share_twd,
                                        "fee":           0.0,
                                        "note":          "T7 B 再平衡",
                                    })
                            _dy_b = _dy_lookup_t7.get(_pk_g, 0.0)
                            _ann_b = _share_twd * _dy_b / 100.0
                            _b_ann_total += _ann_b
                            _pid_b, _code_b = parse_pk(_pk_g)
                            _pid_b_disp = _pid_b or "(未綁)"
                            _rows.append({
                                "保單": _pid_b_disp,
                                "基金": _code_b,
                                "目標權重": f"{_wn[_pk_g]:.2f}%",
                                "目前市值 TWD": f"{_v_curr[_pk_g]:,.0f}",
                                "缺口 TWD": f"{_gap:,.0f}",
                                "應買 TWD": f"{_share_twd:,.0f}",
                                f"應買 {_ccy}": f"{_orig:,.2f}",
                                "預估單位": f"{_units:,.4f}",
                                "配息率": f"{_dy_b:.2f}%",
                                "本次加碼年配息(TWD)": f"NT${_ann_b:,.0f}",
                            })
                        st.dataframe(
                            pd.DataFrame(_rows),
                            use_container_width=True, hide_index=True
                        )
                        bh1, bh2, bh3 = st.columns(3)
                        bh1.metric("本次投入 TWD", f"NT${float(_btot):,.0f}")
                        bh2.metric(
                            "💵 預估年配息（本次加碼）",
                            f"NT${_b_ann_total:,.0f}",
                            help="= Σ 各檔 應買 TWD × 配息率"
                        )
                        bh3.metric(
                            "📅 月均（÷12）",
                            f"NT${_b_ann_total/12:,.0f}"
                        )
                        if _is_scenario_b:
                            # 從 _navfx 已收集的資料 build cache（_navfx[pk] = (n, x, ccy)）
                            _navfx_cache_b = {p: (v[0], v[1])
                                              for p, v in _navfx.items()
                                              if v[0] and v[1]}
                            _t7_save_scenario(
                                name=_b_scenario_name or
                                     f"B 投入再平衡 NT${float(_btot):,.0f}",
                                action_type="B",
                                details=(
                                    f"投入 NT${float(_btot):,.0f} 攤至 "
                                    f"{len(_wn)} 檔（總和 {sum(_wn.values()):.2f}%）"
                                ),
                                nav_fx_cache=_navfx_cache_b,
                            )
                            _t7_restore_ledgers(_baseline_snap_b)
                            st.info(
                                f"💡 已暫存方案「"
                                f"{_b_scenario_name or 'B 投入再平衡'}"
                                "」，主帳本未變動。可下方面板比較或鎖定。"
                            )
                        else:
                            _sync_invest_twd_from_ledgers()
                            _msg_b = _sync_actions_to_sheet(_b_rows_by_pid)
                            _msg_b_state = _t7_save_snapshot_to_sheets()
                            st.success(
                                f"✅ 已落帳（已套用主帳本），組合權重已朝目標靠攏（總和 "
                                f"{sum(_wn.values()):.2f}%）{_msg_b}{_msg_b_state}"
                            )

            # ── C. 轉換再平衡 [核心，M→N action-driven，v18.5] ──────────────
            with _tC:
                st.caption(
                    "**多賣方組 + 各自買方組** 複合轉換。例：A 賣 10% 配 C / "
                    "B 賣 20% 配 D, E。同幣別 → fx_avg 嚴格繼承；跨幣別 → 即期立帳。"
                )
                # 候選清單（pk_str 為主鍵，跨保單同代碼可區分）：必須有正單位數
                _c_candidates = [
                    fund_pk_str(f) for f in _pf_t7
                    if (st.session_state.t7_ledgers.get(fund_pk_str(f)) is not None
                        and st.session_state.t7_ledgers[fund_pk_str(f)].position.units > 0)
                ]
                _c_all_pks = [fund_pk_str(f) for f in _pf_t7]

                # v18.74: 保單卡控 — 同一保單號碼才能互相轉換（同合約內基金互換才合法）
                def _pid_of_pk(_pk: str) -> str:
                    _ff = _fund_by_pk.get(_pk) or {}
                    return str(_ff.get("policy_id") or "").strip() or "(未綁)"

                if not _c_candidates:
                    st.info(
                        "ℹ️ 目前帳本無任何持倉部位，"
                        "請先用「📝 編輯初始持倉」或 A / B 落帳建立部位後再轉換。"
                    )
                else:
                    # 1️⃣ 先選保單號碼（同保單內互轉才合法；跨保單轉換要走贖回+申購）
                    _c_policies = sorted({_pid_of_pk(p) for p in _c_candidates})
                    _sel_pid = st.selectbox(
                        "1️⃣ 先選保單號碼（同保單內才能互轉，避免跨保單錯帳）",
                        _c_policies,
                        key="t7c_policy_pid",
                        help="跨保單的資金搬移需先贖回再申購、不能用 switch；此處只列同保單內互轉。",
                    )
                    # 同保單下：賣方候選 = 該保單下有部位的基金；
                    # 買方候選 = 該保單下所有基金（不限有部位，可加碼新標的）
                    _c_cands_pid = [p for p in _c_candidates if _pid_of_pk(p) == _sel_pid]
                    _c_all_pks_pid = [p for p in _c_all_pks if _pid_of_pk(p) == _sel_pid]
                    if len(_c_cands_pid) < 1:
                        st.warning(f"⚠️ 保單 `{_sel_pid}` 下無任何持倉部位，無法執行轉換。")
                        _sell_pks = []
                    elif len(_c_all_pks_pid) < 2:
                        st.warning(
                            f"⚠️ 保單 `{_sel_pid}` 下只有 {len(_c_all_pks_pid)} 檔基金，"
                            "無法執行轉換（至少需 2 檔，買賣不能同檔）。"
                        )
                        _sell_pks = []
                    else:
                        # 用保單號碼當 widget key 後綴，切換保單時自動重置選擇，
                        # 避免殘留跨保單的 pk 觸發 StreamlitAPIException。
                        _sell_pks = st.multiselect(
                            "2️⃣ 賣方組（**可多選**，最多 5 檔；每個賣方下面會有自己的買方組與權重）",
                            _c_cands_pid,
                            default=_c_cands_pid[:1] if _c_cands_pid else [],
                            max_selections=5,
                            key=f"t7c_sell_codes__{_sel_pid}",
                            format_func=lambda p: _label_for_pk(p),
                            help=(
                                "M→N 複合轉換：一次選 1~5 個賣方，每個賣方各自設定賣 % "
                                "+ 對應的 1~5 個買方 + 各買方權重 — 比例獨立計算。\n"
                                "例：A 賣 10% → C 100% / B 賣 20% → D 60% E 40%"
                            ),
                        )
                    if not _sell_pks:
                        if _c_candidates and _c_cands_pid:
                            st.warning("⚠️ 請至少選一檔賣方。")
                    else:
                        # v18.84: 已選賣方數量即時提示，提醒使用者可繼續加
                        _n_sel = len(_sell_pks)
                        st.caption(
                            f"📋 已選 **{_n_sel} 個賣方** — 下方每個賣方獨立設定買方組 "
                            f"+ 比例個別計算（最多可再加 {5 - _n_sel} 個）"
                            if _n_sel < 5 else
                            f"📋 已選滿 5 個賣方（上限）"
                        )
                        # v18.82: 賣方 / 買方 視覺分區 — 紅區（賣）+ 綠區（買）
                        # 使用者反饋「賣方與買方分開區塊 放在一起會看錯」
                        # 用色塊 header + divider 強化視覺分離
                        _sell_configs = {}  # sell_pk -> {sell_pct, buy_weights}
                        for _idx_s, _spk in enumerate(_sell_pks):
                            _slabel = _label_for_pk(_spk)
                            with st.expander(
                                f"🔁 #{_idx_s+1}　賣方 {_slabel}",
                                expanded=(_idx_s == 0),
                            ):
                                # ─── 紅區：賣方設定 ───
                                st.markdown(
                                    "<div style='background:linear-gradient(90deg,#3a1a1a,#2a1010);"
                                    "border-left:4px solid #f44336;border-radius:0 6px 6px 0;"
                                    "padding:8px 14px;margin-bottom:8px'>"
                                    "<span style='color:#ff7043;font-weight:700;font-size:13px'>"
                                    "📉 賣方設定</span>"
                                    f"<span style='color:#888;font-size:11px;margin-left:8px'>"
                                    f"{_slabel}</span></div>",
                                    unsafe_allow_html=True,
                                )
                                _sp = st.number_input(
                                    "賣出 % 部位（從此檔當前持有單位賣出多少）",
                                    min_value=1.0, max_value=100.0,
                                    value=10.0, step=5.0,
                                    key=f"t7c2_sp_{_spk}",
                                    help="此部位目前持有單位中賣出多少 %",
                                )

                                st.markdown(
                                    "<div style='height:1px;background:linear-gradient(90deg,"
                                    "transparent,#30363d 30%,#30363d 70%,transparent);"
                                    "margin:14px 0'></div>",
                                    unsafe_allow_html=True,
                                )

                                # ─── 綠區：買方設定 ───
                                st.markdown(
                                    "<div style='background:linear-gradient(90deg,#0d2a1a,#0a1f12);"
                                    "border-left:4px solid #00c853;border-radius:0 6px 6px 0;"
                                    "padding:8px 14px;margin-bottom:8px'>"
                                    "<span style='color:#69f0ae;font-weight:700;font-size:13px'>"
                                    "📈 買方組（此賣款導向以下標的）</span>"
                                    f"<span style='color:#888;font-size:11px;margin-left:8px'>"
                                    f"同保單 {_sel_pid} 下，最多 5 檔</span></div>",
                                    unsafe_allow_html=True,
                                )
                                # v18.74: 買方候選限制在同保單（_c_all_pks_pid）
                                _b_opts = [p for p in _c_all_pks_pid if p != _spk]
                                _bcs = st.multiselect(
                                    "買方標的（複選）",
                                    _b_opts,
                                    default=_b_opts[:1] if _b_opts else [],
                                    max_selections=5,
                                    key=f"t7c2_bcs_{_spk}",
                                    format_func=lambda p: _label_for_pk(p),
                                )
                                _bweights: dict = {}
                                if _bcs:
                                    st.caption("買方權重分配（總和應 ≈ 100%）")
                                    _wcols = st.columns(min(len(_bcs), 5))
                                    _wd = round(100.0 / max(len(_bcs), 1), 2)
                                    for _j, _bpk in enumerate(_bcs):
                                        _w = _wcols[_j % len(_wcols)].number_input(
                                            f"{_label_for_pk(_bpk)} %",
                                            min_value=0.0, max_value=100.0,
                                            value=_wd, step=1.0,
                                            key=f"t7c2_w_{_spk}_{_bpk}",
                                        )
                                        _bweights[_bpk] = float(_w)
                                    _wsum_disp = sum(_bweights.values())
                                    _wsum_color = ("#00c853" if abs(_wsum_disp - 100.0) <= 0.5
                                                    else "#f44336")
                                    st.markdown(
                                        f"<div style='text-align:right;font-size:12px;"
                                        f"color:{_wsum_color};margin-top:4px'>"
                                        f"買方權重合計：<b>{_wsum_disp:.2f}%</b></div>",
                                        unsafe_allow_html=True,
                                    )
                                _sell_configs[_spk] = {
                                    "sell_pct": float(_sp),
                                    "buy_weights": _bweights,
                                }

                        _c_commit_mode = st.radio(
                            "落帳目標",
                            options=["💡 暫存為方案（不動主帳本）",
                                     "✅ 直接套用主帳本"],
                            horizontal=True, key="t7c_commit_mode",
                        )
                        _c_scenario_name = st.text_input(
                            "方案名稱（暫存模式才用）",
                            placeholder=f"如：C 方案-複合轉換 {len(_sell_pks)} 賣方",
                            key="t7c_scenario_name",
                        )
                        _csubmit = st.button("🔁 試算 M→N 複合轉換", type="primary",
                                             key="t7c_submit_btn")

                        if _csubmit:
                            # 驗證每個賣方的買方權重總和 ≈ 100
                            _bad_sells = []
                            for _spk, _cfg in _sell_configs.items():
                                _bws = _cfg["buy_weights"]
                                if not _bws:
                                    _bad_sells.append(f"{_label_for_pk(_spk)}（無買方）")
                                    continue
                                _wsum = sum(_bws.values())
                                if abs(_wsum - 100.0) > 0.5:
                                    _bad_sells.append(
                                        f"{_label_for_pk(_spk)}（買方權重 {_wsum:.2f}% ≠ 100%）"
                                    )
                            if _bad_sells:
                                st.error(
                                    "❌ 配置錯誤：" + "／".join(_bad_sells)
                                    + "（每賣方的買方權重需 = 100% ± 0.5%）"
                                )
                            else:
                                _is_scenario_c = _c_commit_mode.startswith("💡")
                                _baseline_snap_c = (_t7_snapshot_ledgers()
                                                     if _is_scenario_c else None)
                                # 預先抓所有涉及基金的 NAV/FX，存進 cache（鍵：pk_str）
                                _navfx_cache_c = {}
                                _all_pks_c = set(_sell_pks) | {
                                    bp for cfg in _sell_configs.values()
                                    for bp in cfg["buy_weights"].keys()
                                }
                                for _pk_x in _all_pks_c:
                                    _f = _fund_by_pk.get(_pk_x)
                                    if _f:
                                        _n, _x = _latest_nav_fx_t7(_f)
                                        if _n and _x:
                                            _navfx_cache_c[_pk_x] = (_n, _x)
                                # baseline cost basis 守恆計算
                                _baseline_costs = {}
                                for _spk in _sell_pks:
                                    _l = st.session_state.t7_ledgers[_spk]
                                    _baseline_costs[_spk] = {
                                        "cost_unit": _l.position.cost_unit,
                                        "fx_avg": _l.position.fx_avg,
                                        "units_total": _l.position.units,
                                    }
                                _result_rows = []  # 全域 (sell_pk, buy_pk) 明細
                                _c_rows_by_pid: dict[str, list[dict]] = {}   # v18.27 dual-write
                                _twd_total_moved = 0.0
                                _ann_gain_total = 0.0
                                _ann_lost_total = 0.0
                                _expected_total = 0.0
                                try:
                                    for _spk, _cfg in _sell_configs.items():
                                        _Sf = _fund_by_pk.get(_spk)
                                        _na, _xa = _navfx_cache_c.get(
                                            _spk, _latest_nav_fx_t7(_Sf)
                                        )
                                        _S = {
                                            "nav": _na, "fx": _xa,
                                            "ccy": str(_Sf.get("currency", "USD")
                                                       ).upper(),
                                            "ledger": _ledger_for(_spk),
                                        }
                                        _u_redeem_s = (
                                            _baseline_costs[_spk]["units_total"]
                                            * _cfg["sell_pct"] / 100.0
                                        )
                                        _u_redeem_s = min(
                                            _u_redeem_s,
                                            _baseline_costs[_spk]["units_total"]
                                        )
                                        if _u_redeem_s <= 0 or _S["nav"] <= 0:
                                            raise ValueError(
                                                f"賣方 {_label_for_pk(_spk)}：賣出 units = 0 或 NAV 抓不到"
                                            )
                                        _expected_total += (
                                            _u_redeem_s
                                            * _baseline_costs[_spk]["cost_unit"]
                                            * _baseline_costs[_spk]["fx_avg"]
                                        )
                                        # 失去 A 配息
                                        _dy_S = _dy_lookup_t7.get(_spk, 0.0)
                                        _ann_lost_total += (
                                            _u_redeem_s * _S["nav"] * _S["fx"]
                                            * _dy_S / 100.0
                                        )
                                        # 對齊 100% 買方權重到最後一檔
                                        _wn = dict(_cfg["buy_weights"])
                                        _last_bpk = list(_wn.keys())[-1]
                                        _wn[_last_bpk] += (100.0 - sum(_wn.values()))
                                        _used_units = 0.0
                                        for _bpk, _w in _wn.items():
                                            if _bpk == _last_bpk:
                                                _u_chunk = _u_redeem_s - _used_units
                                            else:
                                                _u_chunk = _u_redeem_s * _w / 100.0
                                                _used_units += _u_chunk
                                            _Bf = _fund_by_pk.get(_bpk)
                                            _nb, _xb = _navfx_cache_c.get(
                                                _bpk, _latest_nav_fx_t7(_Bf)
                                            )
                                            if _nb <= 0:
                                                raise ValueError(
                                                    f"買方 {_label_for_pk(_bpk)} NAV 抓不到"
                                                )
                                            _Bd = {
                                                "nav": _nb, "fx": _xb,
                                                "ccy": str(_Bf.get("currency", "USD")
                                                           ).upper(),
                                                "ledger": _ledger_for(_bpk),
                                            }
                                            if _S["ccy"] == _Bd["ccy"]:
                                                _sr = _SwT7.switch_same_currency(
                                                    ledger_from=_S["ledger"],
                                                    ledger_to=_Bd["ledger"],
                                                    units_to_redeem=_u_chunk,
                                                    nav_from_redeem=_S["nav"],
                                                    nav_to_buy=_Bd["nav"],
                                                    fee_orig=0.0,
                                                    txn_date=_d_t7.today(),
                                                )
                                                _mode_b = "同幣別"
                                            else:
                                                _fxA_t = (
                                                    _fx_now(f"{_S['ccy']}TWD")
                                                    or _S["fx"]
                                                )
                                                _fxB_t = (
                                                    _fx_now(f"{_Bd['ccy']}TWD")
                                                    or _Bd["fx"]
                                                )
                                                if _fxB_t <= 0:
                                                    raise ValueError(
                                                        f"{_bc} 對 TWD 匯率為 0"
                                                    )
                                                _cross_t = _fxA_t / _fxB_t
                                                _sr = _SwT7.switch_cross_currency(
                                                    ledger_from=_S["ledger"],
                                                    ledger_to=_Bd["ledger"],
                                                    units_to_redeem=_u_chunk,
                                                    nav_from_redeem=_S["nav"],
                                                    nav_to_buy=_Bd["nav"],
                                                    cross_rate=_cross_t,
                                                    fx_to_at_switch_twd=_fxB_t,
                                                    fee_orig=0.0,
                                                    txn_date=_d_t7.today(),
                                                )
                                                _mode_b = (
                                                    f"跨幣別 (cross={_cross_t:.4f})"
                                                )
                                            _twd_total_moved += (
                                                _sr.twd_cost_basis_transferred
                                            )
                                            _dy_b_loop = _dy_lookup_t7.get(_bpk, 0.0)
                                            _ann_b = (
                                                _sr.units_added_to * _Bd["nav"]
                                                * _Bd["fx"] * _dy_b_loop / 100.0
                                            )
                                            _ann_gain_total += _ann_b
                                            _spid, _scode_disp = parse_pk(_spk)
                                            _bpid, _bcode_disp = parse_pk(_bpk)
                                            # v18.27: dual-write 收集 (sell + buy 各一筆)
                                            _today_iso = _d_t7.today().isoformat()
                                            if _spid:
                                                _c_rows_by_pid.setdefault(_spid, []).append({
                                                    "date":          _today_iso,
                                                    "code":          _scode_disp,
                                                    "action":        "sell",
                                                    "units":         float(_sr.units_redeemed_from),
                                                    "nav_at_action": float(_S["nav"]),
                                                    "twd":           float(_sr.twd_cost_basis_transferred),
                                                    "fee":           0.0,
                                                    "note":          f"T7 C 轉換 → {_bcode_disp}",
                                                })
                                            if _bpid:
                                                _c_rows_by_pid.setdefault(_bpid, []).append({
                                                    "date":          _today_iso,
                                                    "code":          _bcode_disp,
                                                    "action":        "buy",
                                                    "units":         float(_sr.units_added_to),
                                                    "nav_at_action": float(_Bd["nav"]),
                                                    "twd":           float(_sr.twd_cost_basis_transferred),
                                                    "fee":           0.0,
                                                    "note":          f"T7 C 轉換 ← {_scode_disp}",
                                                })
                                            _result_rows.append({
                                                "賣方保單": _spid or "(未綁)",
                                                "賣方": _scode_disp,
                                                "賣 %": f"{_cfg['sell_pct']:.1f}%",
                                                "買方保單": _bpid or "(未綁)",
                                                "買方": _bcode_disp,
                                                "買方名稱": (
                                                    _name_lookup_t7.get(_bpk, _bcode_disp)[:18]
                                                ),
                                                "權重": f"{_w:.2f}%",
                                                "賣出單位": (
                                                    f"{_sr.units_redeemed_from:,.4f}"
                                                ),
                                                "買進單位": (
                                                    f"{_sr.units_added_to:,.4f}"
                                                ),
                                                "TWD 成本搬移": (
                                                    f"NT${_sr.twd_cost_basis_transferred:,.0f}"
                                                ),
                                                "B 新 NAV 成本": (
                                                    f"{_sr.cost_unit_to_basis:.4f}"
                                                ),
                                                "B 新 FX": (
                                                    f"{_sr.fx_avg_inherited:.4f}"
                                                ),
                                                "模式": _mode_b,
                                                "預估年配息": f"NT${_ann_b:,.0f}",
                                            })
                                    # 顯示結果
                                    st.success(
                                        f"✅ 複合轉換：{len(_sell_pks)} 賣方 → "
                                        f"{len(_result_rows)} 筆 switch 完成"
                                    )
                                    _df_c = pd.DataFrame(_result_rows)
                                    st.dataframe(
                                        _df_c, use_container_width=True,
                                        hide_index=True,
                                    )
                                    # 全域 hero
                                    _ann_diff = _ann_gain_total - _ann_lost_total
                                    hh1, hh2, hh3 = st.columns(3)
                                    hh1.metric(
                                        "📉 失去年配息（賣方組合計）",
                                        f"NT${_ann_lost_total:,.0f}/年",
                                    )
                                    hh2.metric(
                                        "📈 取得年配息（買方組合計）",
                                        f"NT${_ann_gain_total:,.0f}/年",
                                    )
                                    hh3.metric(
                                        "🔁 換倉後月配息變化",
                                        f"NT${_ann_diff/12:+,.0f}/月",
                                        delta=f"NT${_ann_diff:+,.0f}/年",
                                        help="正值 = 換倉後現金流增加；負值 = 為了成長換取配息",
                                    )
                                    tt1, tt2 = st.columns(2)
                                    tt1.metric(
                                        "TWD 成本基礎總搬移",
                                        f"NT${_twd_total_moved:,.0f}",
                                        help="Σ 各對 (sell_i, buy_j) 的 TWD 成本搬移",
                                    )
                                    _delta = _twd_total_moved - _expected_total
                                    tt2.metric(
                                        "守恆檢查（賣方組 baseline）",
                                        f"NT${_expected_total:,.0f}",
                                        delta=f"差 NT${_delta:+,.0f}",
                                        help=(
                                            "Σ 各賣方 (units_redeemed × cost_unit × fx_avg)；"
                                            "與『TWD 總搬移』差距應 < N NTD（浮點累積）"
                                        ),
                                    )
                                    if _is_scenario_c:
                                        _t7_save_scenario(
                                            name=_c_scenario_name or
                                                 f"C 複合轉換 {len(_sell_pks)}→{len(_result_rows)}",
                                            action_type="C",
                                            details=(
                                                f"{len(_sell_pks)} 賣方 → "
                                                f"{len(_result_rows)} 筆 switch；"
                                                f"TWD 搬移 NT${_twd_total_moved:,.0f}"
                                            ),
                                            nav_fx_cache=_navfx_cache_c,
                                        )
                                        _t7_restore_ledgers(_baseline_snap_c)
                                        st.info(
                                            f"💡 已暫存方案「"
                                            f"{_c_scenario_name or 'C 複合轉換'}"
                                            "」，主帳本未變動。"
                                        )
                                    else:
                                        _sync_invest_twd_from_ledgers()
                                        _msg_c = _sync_actions_to_sheet(_c_rows_by_pid)
                                        _msg_c_state = _t7_save_snapshot_to_sheets()
                                        st.caption(
                                            "💡 已套用主帳本：完成 "
                                            f"{len(_result_rows)} 筆複合 switch。{_msg_c}{_msg_c_state}"
                                        )
                                except Exception as _e_sw:
                                    if _is_scenario_c and _baseline_snap_c is not None:
                                        _t7_restore_ledgers(_baseline_snap_c)
                                    st.error(f"❌ 複合轉換失敗：{_e_sw}")

            # ── 帳本即時面板（最後渲染，永遠拿到最新 session_state） ────────
            with _panel_ph.container():
                # ── 方案比較區（v18.4 新增，僅在有 scenarios 時顯示）─────────
                if st.session_state.t7_scenarios:
                    with st.expander(
                        f"📊 方案比較（{len(st.session_state.t7_scenarios)} / "
                        f"{_T7_SCENARIO_LIMIT}）",
                        expanded=True,
                    ):
                        _live_navfx_cache = _t7_build_navfx_cache()
                        _live_summary = _t7_summary_from_ledgers(
                            st.session_state.t7_ledgers,
                            nav_fx_cache=_live_navfx_cache,
                        )
                        _cmp_rows = [{
                            "方案": "🟢 主帳本 (Live)",
                            "類型": "—",
                            "建立時間": "—",
                            "總市值 TWD": f"NT${_live_summary['total_value_twd']:,.0f}",
                            "成本 TWD": f"NT${_live_summary['total_cost_twd']:,.0f}",
                            "未實現損益 TWD": f"NT${_live_summary['unrealized_pl_twd']:+,.0f}",
                            "報酬 %": f"{_live_summary['unrealized_pl_pct']:+.2f}%",
                            "月配息 TWD": f"NT${_live_summary['monthly_cashflow_twd']:,.0f}",
                            "說明": "目前實際帳本",
                        }]
                        for _sc in st.session_state.t7_scenarios:
                            _s = _sc["summary"]
                            _diff_pl = (_s["unrealized_pl_twd"]
                                        - _live_summary["unrealized_pl_twd"])
                            _diff_cf = (_s["monthly_cashflow_twd"]
                                        - _live_summary["monthly_cashflow_twd"])
                            _cmp_rows.append({
                                "方案": f"💡 {_sc['name'][:24]}",
                                "類型": _sc["action_type"],
                                "建立時間": _sc["created_at"],
                                "總市值 TWD": f"NT${_s['total_value_twd']:,.0f}",
                                "成本 TWD": f"NT${_s['total_cost_twd']:,.0f}",
                                "未實現損益 TWD": (
                                    f"NT${_s['unrealized_pl_twd']:+,.0f}"
                                ),
                                "報酬 %": f"{_s['unrealized_pl_pct']:+.2f}%",
                                "月配息 TWD": (
                                    f"NT${_s['monthly_cashflow_twd']:,.0f} "
                                    f"({_diff_cf:+,.0f})"
                                ),
                                "說明": _sc["details"][:60],
                            })
                        st.dataframe(
                            pd.DataFrame(_cmp_rows),
                            use_container_width=True, hide_index=True,
                        )
                        st.caption(
                            "💡 月配息欄括號 = 與主帳本差距；未實現損益反映各方案買進後預估價位（NAV 不變假設）。"
                        )
                        # 每個 scenario 對應 commit/delete 按鈕
                        for _idx, _sc in enumerate(st.session_state.t7_scenarios):
                            _bcol1, _bcol2, _bcol3 = st.columns([4, 1, 1])
                            _bcol1.markdown(
                                f"**{_sc['name']}** "
                                f"<span style='color:#888;font-size:11px'>"
                                f"({_sc['action_type']} @ {_sc['created_at']})"
                                f"</span>",
                                unsafe_allow_html=True,
                            )
                            if _bcol2.button(
                                "📌 鎖定為主帳本",
                                key=f"t7_commit_sc_{_sc['id']}",
                                help="把此方案套用為主帳本（其他方案保留）"
                            ):
                                _t7_restore_ledgers(_sc["snapshot"])
                                _sync_invest_twd_from_ledgers()
                                st.success(
                                    f"✅ 已鎖定「{_sc['name']}」為主帳本。"
                                )
                                st.rerun()
                            if _bcol3.button(
                                "🗑️", key=f"t7_del_sc_{_sc['id']}",
                                help="刪除此方案"
                            ):
                                st.session_state.t7_scenarios = [
                                    s for s in st.session_state.t7_scenarios
                                    if s["id"] != _sc["id"]
                                ]
                                st.rerun()
                        if st.button("🗑️ 清空全部方案", key="t7_clear_all_scenarios"):
                            st.session_state.t7_scenarios = []
                            st.rerun()

                with st.expander("📒 目前帳本 + 以息養股現金流（in-memory，隨頁面重整清空）",
                                 expanded=True):
                    _snap_rows = []
                    _v_total_twd = 0.0
                    _ann_total_twd = 0.0
                    _cost_total_twd = 0.0
                    # v18.31: 追蹤未計入的基金，給 KPI 卡顯示差額來源
                    _uncounted_funds: list[str] = []
                    for _f in _pf_t7:
                        _pk_f = fund_pk_str(_f)
                        _c = _f.get("code", "?")
                        _pid_disp = _f.get("policy_id") or "(未綁)"
                        _name_short = (_name_lookup_t7.get(_pk_f, _c))[:28]
                        _l = st.session_state.t7_ledgers.get(_pk_f)
                        _nav, _fx = _latest_nav_fx_t7(_f)
                        _dy = _dy_lookup_t7.get(_pk_f, 0.0)
                        if _l is None or _l.position.units <= 0:
                            _uncounted_funds.append(f"{_c}({_pid_disp})")
                            _snap_rows.append({
                                "保單": _pid_disp,
                                "代碼": _c, "基金名稱": _name_short,
                                "幣別": _f.get("currency", "USD"),
                                "持有單位": "—",
                                "平均買入淨值 NAV": "—", "平均買入匯率": "—",
                                "最新 NAV": f"{_nav:.4f}" if _nav else "—",
                                "最新 FX": f"{_fx:.4f}" if _fx else "—",
                                "成本基礎 (TWD)": "—",
                                "市值 (TWD)": "—",
                                "未實現損益 (TWD)": "—",
                                "未實現損益 %": "—",
                                "配息率": f"{_dy:.2f}%" if _dy else "—",
                                "預估月配息 (TWD)": "—",
                            })
                            continue
                        _v = _l.position.value_twd(_nav, _fx) if (_nav and _fx) else 0
                        _cost = _l.position.net_investment_twd
                        _pl_twd = _v - _cost
                        _pl_pct = (_pl_twd / _cost * 100.0) if _cost > 0 else 0.0
                        _v_total_twd += _v
                        _cost_total_twd += _cost
                        _ann = _v * _dy / 100.0
                        _ann_total_twd += _ann
                        _pl_str = f"NT${_pl_twd:+,.0f}"
                        _pl_pct_str = f"{_pl_pct:+.2f}%"
                        _snap_rows.append({
                            "保單": _pid_disp,
                            "代碼": _c, "基金名稱": _name_short,
                            "幣別": _l.currency,
                            "持有單位": f"{_l.position.units:,.4f}",
                            "平均買入淨值 NAV": f"{_l.position.cost_unit:.4f}",
                            "平均買入匯率": f"{_l.position.fx_avg:.4f}",
                            "最新 NAV": f"{_nav:.4f}" if _nav else "—",
                            "最新 FX": f"{_fx:.4f}" if _fx else "—",
                            "成本基礎 (TWD)": f"NT${_cost:,.0f}",
                            "市值 (TWD)": f"NT${_v:,.0f}",
                            "未實現損益 (TWD)": _pl_str,
                            "未實現損益 %": _pl_pct_str,
                            "配息率": f"{_dy:.2f}%",
                            "預估月配息 (TWD)": f"NT${_ann/12:,.0f}",
                        })
                    if _snap_rows:
                        # 紅虧綠賺：用 pandas Styler 著色（純 CSS 不依賴 matplotlib）
                        _df_snap = pd.DataFrame(_snap_rows)
                        def _color_pl(val):
                            if not isinstance(val, str) or val == "—":
                                return ""
                            try:
                                # 抽出第一個正/負號旁的數字
                                v = val.replace("NT$", "").replace(",", "").replace("%", "")
                                f = float(v)
                                if f > 0:  return "color:#00c853;font-weight:600"
                                if f < 0:  return "color:#f44336;font-weight:600"
                            except Exception:
                                return ""
                            return ""
                        try:
                            _styled = _df_snap.style.applymap(
                                _color_pl, subset=["未實現損益 (TWD)", "未實現損益 %"]
                            )
                            st.dataframe(_styled, use_container_width=True,
                                         hide_index=True)
                        except Exception:
                            st.dataframe(_df_snap, use_container_width=True,
                                         hide_index=True)
                    # v18.70: 市值 = 0 時用 invest_twd 顯示估算值，避免「上下不同步」視覺斷層
                    _pl_total = _v_total_twd - _cost_total_twd
                    _pl_total_pct = (_pl_total / _cost_total_twd * 100.0
                                      if _cost_total_twd > 0 else 0.0)
                    # 計算 invest_twd 總和（fallback 用）
                    _invest_total_twd = sum(
                        float(_f.get("invest_twd", 0) or 0)
                        for _f in _pf_t7
                    )
                    _pc1, _pc2, _pc3, _pc4, _pc5 = st.columns([2, 2, 2, 2, 1])
                    if _v_total_twd > 0:
                        _pc1.metric("組合當前市值 (TWD)", f"NT${_v_total_twd:,.0f}")
                    elif _invest_total_twd > 0:
                        # 沒 ledger 但有 invest_twd → 顯示投資金額作為近似
                        _pc1.metric(
                            "組合當前市值 (TWD) ⚠️ 近似",
                            f"NT${_invest_total_twd:,.0f}",
                            help="目前帳本無持倉細節，以保單投資金額（invest_twd）作為近似。"
                                 "進「✏️ 編輯持倉」用「⚡ 自動估算」填入持倉，或手動輸入精確值。"
                        )
                    else:
                        _pc1.metric("組合當前市值 (TWD)", "NT$0",
                                    help="尚無持倉資料 — 請加入基金 + 設定單位/NAV/匯率")
                    _pc2.metric(
                        "💸 整體未實現損益 (TWD)",
                        f"NT${_pl_total:+,.0f}",
                        delta=f"{_pl_total_pct:+.2f}% 報酬率",
                        delta_color="normal",   # v18.26: 損益恆用 normal（虧損紅、賺綠）
                    )
                    _pc3.metric(
                        "💵 預估年配息（TWD）",
                        f"NT${_ann_total_twd:,.0f}",
                        help="= Σ 各檔 市值 × 配息率"
                    )
                    _pc4.metric(
                        "📅 每月被動現金流",
                        f"NT${_ann_total_twd/12:,.0f}"
                    )
                    if _pc5.button("🗑️ 重置帳本", key="t7_reset"):
                        st.session_state.t7_ledgers = {}
                        st.rerun()
                    # v18.31: KPI vs 表格差額來源說明
                    _counted = len(_pf_t7) - len(_uncounted_funds)
                    if _uncounted_funds:
                        st.caption(
                            f"ℹ️ KPI 已計入 **{_counted} / {len(_pf_t7)} 檔**；"
                            f"未計入 {len(_uncounted_funds)} 檔（"
                            f"{', '.join(_uncounted_funds[:5])}"
                            f"{'…' if len(_uncounted_funds) > 5 else ''}）"
                            f"— 請在「📝 編輯初始持倉」填入持有單位/NAV/匯率"
                        )
                    else:
                        st.caption(
                            f"✅ KPI 已計入全部 **{len(_pf_t7)} 檔**基金；"
                            "若上方表格列數與 KPI 不符，請檢查 ledger 狀態（「📝 編輯初始持倉」）"
                        )


            # ── v18.82 MK 老師深度組合建議（AI）—— 放 _panel_ph 之外才會在 A/B/C 下方 ──
            # 使用者反饋「組合基金下方缺乏 AI 組合分析」：v18.81 expander 寫在
            # _panel_ph.container() 裡，那個 placeholder 在 A/B/C tabs 上方創建，
            # 渲染進去 = 顯示在 tabs 上方，使用者在 C tab 往下看當然看不到。
            # 搬出 placeholder 後 expander 渲染在 if _T7_OK 區段最末，即 A/B/C 下方。
            st.divider()
            st.markdown(
                "<div style='background:linear-gradient(135deg,#2a1845,#1a0d2a);"
                "border-left:4px solid #b388ff;border-radius:8px;"
                "padding:10px 14px;margin:8px 0'>"
                "<span style='color:#b388ff;font-size:15px;font-weight:900'>"
                "📜 策略3 深度組合建議</span>"
                "<span style='color:#888;font-size:11px;margin-left:8px'>"
                "AI 4 節結構：3 大缺點 / 換股建議 / 配置比例 / 高賣低買 vs 跌就買</span>"
                "</div>",
                unsafe_allow_html=True,
            )
            if not GEMINI_KEY:
                st.info("ℹ️ 需設置 Gemini API key 才能使用此功能")
            elif not _pf_t7:
                st.info("ℹ️ 請先載入基金（上方「📡 載入所有未載入基金」）")
            else:
                _mk_ai_phase = (st.session_state.get("phase_info_global")
                                or st.session_state.get("phase_info") or {})
                _mk_ai_ind = st.session_state.get("indicators") or {}
                _mk_data_ok, _ = _calc_data_health(_mk_ai_ind)
                if _mk_data_ok < 50:
                    st.warning(
                        f"🔴 總經完整率 **{_mk_data_ok}%**（&lt;50%）— "
                        "建議先到「🌐 總經」按「📡 全量抓取」載入指標後再生成，"
                        "AI 才能給景氣位階對應的換股建議。仍可勾選下方略過按鈕直接生成基礎組合分析。"
                    )
                # v18.87: 資料來源透明化 — 明確說 AI 只看主帳本（不含 A/B/C 暫存方案）
                # 使用者反饋「MK 老師的判斷不能抓取重新配置的資料，因為這資料只是給我
                # 想要重新配置的參考值」— 程式碼確實已隔離，但 UI 沒講清楚使用者會擔心
                _mk_n_funds = sum(1 for f in _pf_t7 if f.get("loaded"))
                _mk_total_inv = sum(int(f.get("invest_twd", 0) or 0)
                                     for f in _pf_t7 if f.get("loaded"))
                _mk_n_scenarios = len(st.session_state.get("t7_scenarios", []) or [])
                st.markdown(
                    "<div style='background:#0d1117;border:1px solid #30363d;"
                    "border-radius:6px;padding:8px 12px;margin:6px 0;font-size:12px'>"
                    "<span style='color:#69f0ae;font-weight:700'>🔍 分析範圍：</span>"
                    f"<span style='color:#c9d1d9'>主帳本 <b>{_mk_n_funds} 檔</b>"
                    f"，合計投入 <b>NT${_mk_total_inv:,}</b></span>"
                    + (f"<span style='color:#ff9800;margin-left:12px'>"
                       f"（A/B/C 暫存方案 {_mk_n_scenarios} 個 — <b>不</b>納入分析）"
                       "</span>" if _mk_n_scenarios > 0 else "")
                    + "</div>",
                    unsafe_allow_html=True,
                )
                _mk_cols = st.columns([2, 1, 1])
                _mk_btn = _mk_cols[0].button(
                    "🤖 生成 策略3 深度建議",
                    key="btn_mk_advisor",
                    type="primary",
                    use_container_width=True,
                    help="只分析主帳本（已落帳的實際持倉），A/B/C 暫存方案不會被納入",
                )
                if _mk_cols[1].button("🗑️ 清除上次結果",
                                       key="btn_mk_advisor_clear",
                                       use_container_width=True):
                    st.session_state.pop("mk_advisor_txt", None)
                    st.rerun()
                if _mk_btn:
                    # v18.87: 防禦性 — 呼叫 AI 前 deep-copy 主帳本 + portfolio_funds，
                    # 確保 spinner 期間其他 callback 或 rerun side-effect 都不影響 AI 看到的資料
                    import copy as _cp_mk
                    _mk_pf_snapshot = _cp_mk.deepcopy(_pf_t7)
                    _mk_ledger_snapshot = _t7_snapshot_ledgers()
                    # v18.85/86: 抓 RSS 新聞給 AI 判斷系統性風險
                    _mk_news: list = []
                    with st.spinner("📰 抓取近期國際財經新聞 + 系統性風險事件 (RSS)..."):
                        try:
                            _mk_news = fetch_market_news(max_per_feed=4) or []
                        except Exception as _e_news:
                            st.caption(f"⚠️ 新聞抓取失敗（{str(_e_news)[:60]}），"
                                       f"AI 將在無新聞背景下分析")
                    if _mk_news:
                        _n_sys = sum(1 for h in _mk_news if h.get("is_systemic"))
                        if _n_sys > 0:
                            st.warning(
                                f"🚨 偵測到 **{_n_sys} 條系統性風險新聞**"
                                f"（戰爭 / 銀行倒閉 / 黑天鵝事件）— 已餵給 AI 優先判讀"
                            )
                        st.caption(
                            f"✅ 已抓 {len(_mk_news)} 條近期新聞"
                            + (f"（含 {_n_sys} 條 🚨 系統性風險）" if _n_sys > 0 else "")
                            + " — 將餵給 AI 判斷系統性風險"
                        )
                    # 重建 ledgers dict 給 AI（避免 AI 內部任何 mutate 污染主帳本）
                    _mk_ledger_for_ai = {
                        pk: _LedT7.from_dict(d) for pk, d in _mk_ledger_snapshot.items()
                    }
                    # v18.110: 預先計算 Phase 4 driver 排名 + Phase 3-B 燈號回測
                    # → 讓 AI prompt 有量化證據可以引用，建議不再空談
                    _mk_drv: dict | None = None
                    _mk_sub: list | None = None
                    if _mk_ai_ind:
                        try:
                            _mk_drv = rank_macro_drivers(
                                _mk_ai_ind, target_key="LEI", lag_months=3, min_overlap=24,
                            )
                        except Exception as _e_drv:
                            print(f"[MK AI] rank_macro_drivers 失敗：{_e_drv}")
                        try:
                            _mk_sub = backtest_sub_cycle_lights(
                                _mk_ai_ind, target_key="LEI", window=60, forward_months=3,
                            )
                        except Exception as _e_sub:
                            print(f"[MK AI] backtest_sub_cycle_lights 失敗：{_e_sub}")
                    with st.spinner("🤖 Gemini 分析組合中...（約 15-30 秒）"):
                        try:
                            _mk_txt = analyze_portfolio_mk_advisor(
                                GEMINI_KEY,
                                _mk_pf_snapshot,    # v18.87 deep-copy snapshot
                                _mk_ai_phase,
                                ledgers=_mk_ledger_for_ai,   # v18.87 重建副本
                                indicators=_mk_ai_ind,
                                news_headlines=_mk_news,   # v18.85
                                driver_ranking=_mk_drv,    # v18.110 Phase 4
                                subcycle_lights=_mk_sub,   # v18.110 Phase 3-B
                            )
                            # v18.88: _gemini 失敗時回傳 "❌ ..." 或 "⚠️ ..." 字串而非 raise
                            #         之前直接存進 session 結果區會顯示成功訊息但內容是錯誤
                            if isinstance(_mk_txt, str) and _mk_txt.startswith(("❌", "⚠️")):
                                st.error(
                                    f"❌ 策略3 AI 回傳錯誤訊息：\n\n{_mk_txt[:400]}\n\n"
                                    "**可能原因**：\n"
                                    "- Gemini API 配額用完（HTTP 429）→ 等 1-2 分鐘\n"
                                    "- Prompt 太大被拒（HTTP 400/413）→ v18.88 已大幅瘦身\n"
                                    "- 網路超時 → 重按按鈕"
                                )
                            else:
                                st.session_state["mk_advisor_txt"] = _mk_txt
                                st.session_state["mk_advisor_news_n"] = len(_mk_news)
                                st.session_state["mk_advisor_news_sys_n"] = sum(
                                    1 for h in _mk_news if h.get("is_systemic"))
                        except Exception as _e_mk:
                            # v18.88: 直接顯示真實錯誤 + 異常類型，不藏在 friendly_error 裡
                            st.error(
                                f"❌ 策略3 AI 生成失敗：**[{type(_e_mk).__name__}]** "
                                f"{str(_e_mk)[:300]}\n\n"
                                "**常見原因**：\n"
                                "- HTTP 429 配額 → 等 1-2 分鐘\n"
                                "- HTTP 400 prompt 超限 → v18.88 已瘦身（19→7 unique codes + news 30→8 條）\n"
                                "- 網路逾時 → 重試"
                            )
                if st.session_state.get("mk_advisor_txt"):
                    st.markdown("---")
                    _n_news_used = st.session_state.get("mk_advisor_news_n", 0)
                    _n_sys_used = st.session_state.get("mk_advisor_news_sys_n", 0)
                    if _n_news_used > 0:
                        st.caption(
                            f"📰 本次分析已納入 **{_n_news_used} 條近期新聞** "
                            + (f"（含 **{_n_sys_used} 條 🚨 系統性風險**：戰爭/銀行倒閉/黑天鵝） "
                                if _n_sys_used > 0 else "")
                            + "判斷系統性風險"
                        )
                    st.markdown(st.session_state["mk_advisor_txt"])
                    st.caption("⚠️ AI 建議僅供參考，最終決策需自行判斷市場與風險承受度")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — 回測
