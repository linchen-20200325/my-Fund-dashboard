"""ui/helpers/portfolio/policy_admin_section.py — 保單管理（Google Sheets）區塊

**這個檔案是「原封搬家」的產物，不是新寫的功能。** 內容 790 行逐字取自
`ui/tab3_portfolio.py::render_portfolio_tab()`（搬遷前的 :637-1426），
搬移過程**只做「換檔案 + 補 import + 把 7 個 caller-local 名字改成參數」**，
渲染邏輯、判斷式、文案、例外處理**一個字都沒有改**
（`CLAUDE.md §-1.5.3 C` 禁止把行為變更夾帶在搬遷裡）。

為什麼要抽出來（客戶已拍板的線框 `docs/wireframes/fund-wireframe-final.html` §03 ④）
--------------------------------------------------------------------------
線框把「④ 我的配置」的職責定為 **「我實際持有什麼、值多少、下一筆錢怎麼配」**，
並列出這一段約 800 行的收合區（Sheet 快速存讀 · OAuth 引導 · v1→v2 升級 ·
進階工具 · 保單列新增更新）為**該搬走的最大一塊**：

> → 連線與授權設定：整段搬到 ⑤

⚠️ **本批（WP-D）刻意只抽出、不搬去 ⑤**，理由有二：
1. ⑤「設定與診斷」這個分頁在本批**還不存在**（屬 WP-E/WP-F），現在搬過去無處可接。
2. 線框對這一段的處置**不是整段搬走**：其中「新增／更新保單列」被判定為
   **資料輸入而非連線設定**，建議**留在 ④**（線框 Q9，客戶已答覆「留在 ④ 我的配置，
   只把連線與授權搬去 ⑤」）。也就是這一段**未來要沿著「連線授權」vs「保單資料輸入」
   切成兩半** —— 那一刀屬 WP-E 的範圍，本批不切，避免同一段程式碼被兩批各動一次。

→ **WP-E 接手時**：本模組已經是 self-contained 的獨立單元，
   把它的「連線／授權」部分接到 ⑤、把「新增／更新保單列」留在 ④ 即可，
   `ui/tab3_portfolio.py` 端只有一行呼叫要改。

分層（`CLAUDE.md §8.2` / §8.2.A）
--------------------------------
本檔是 **L3 UI**，直接 import `repositories.policy_repository` /
`repositories.snapshot_repository` / `repositories.ledger_repository`。
這是既有的 **EX-CRUD-1** 例外（本地／Google Sheets 持久化 CRUD：read+write 同檔、
無 `@_ttl_cache` / `@st.cache_data` 裝飾、無外部 HTTP fetcher 的 TTL 集中問題），
見 `CLAUDE.md §8.2.A.1` 該列。**搬遷沒有新增任何跨層呼叫** ——
這些 import 在搬遷前就存在於 `ui/tab3_portfolio.py`（同為 L3 UI），
本檔只是換了一個 L3 檔案來放它們。

⚠️ **為什麼 7 個名字要用參數傳，不在本檔 import**
------------------------------------------------
`_oauth_configured` / `_resolve_oauth_cfg` / `_get_oauth_client` / `_gsa_secret` /
`_sheet_id_secret` / `get_login_state` 這 6 個名字，在 `ui/helpers/oauth_state`
是 **module-level snapshot**；`render_portfolio_tab()` 開頭刻意先呼叫
`refresh_oauth_state()` **再重新 import** 一次，才拿得到 fresh 值
（該檔 v18.148 註解：不重取的話，wizard 寫完 session_state 並 rerun 之後，
仍會拿到 import 當下的 `False` snapshot）。

**若本檔在 module 頂部 import 它們，就會拿到 stale snapshot ——
那正是 v18.148 修掉的 bug。** 故一律由 caller 把它**當下已 refresh 過的值**傳進來，
本檔不自己取。第 7 個 `sheet_client` 是 caller 內部的 closure（SA-first + 403 回退
決策，`ui/tab3_portfolio.py::_t3_sheet_client`），本來就無法 import。

回傳值
------
`_sheet_id` —— 搬遷前這是 `render_portfolio_tab()` 的一個函式區域變數，
本區塊之後的「🗂️ 保單分組視圖」會讀它（「🔗 綁到保單」下拉的顯示條件）。
搬出來之後那個變數不再存在於 caller 的作用域，故**由本函式回傳原值**交還 caller。
⚠️ 刻意**回傳原值**而不是讓 caller 自己重算一次：重算會讀到「本函式執行之後」的
`st.session_state`，與搬遷前 caller 讀到的是**同一次 run 內不同時點**的值 ——
那是行為變更。回傳原值才是零變更。
"""
from __future__ import annotations

import streamlit as st

from infra.oauth import OAuthError, build_authorize_url
from repositories.ledger_repository import load_all_ledgers
from repositories.policy_repository import (  # EX-CRUD-1（CLAUDE.md §8.2.A.1）
    PolicySheetError,
    create_dashboard_sheet,
    delete_policy_row,
    detect_sheet_schema_version,
    get_gspread_client,
    get_sheet_title,
    list_policy_worksheets,
    list_user_folders,
    list_user_sheets,
    load_all_policies_v2,
    upsert_policy_row,
)
from repositories.snapshot_repository import get_state_metadata  # EX-CRUD-1
from ui.helpers.render_state import not_ready
from ui.helpers.tw_time import tw_now_str


def render_policy_admin_section(
    *,
    oauth_configured: bool,
    resolve_oauth_cfg,
    get_oauth_client,
    gsa_secret,
    sheet_id_secret,
    get_login_state,
    sheet_client,
) -> str:
    """渲染「📋 保單管理（Google Sheets）」收合區，回傳本區算出的 `_sheet_id`。

    參數全部由 caller 注入（理由見模組 docstring：oauth_state 的 snapshot 必須
    是 caller `refresh_oauth_state()` 之後那一份，本檔不得自己 import）。

    Returns
    -------
    str
        本區塊執行完當下的 `_sheet_id`（未登入 / 未設定時為空字串 `""`）。
        後續「🗂️ 保單分組視圖」用它決定要不要顯示「🔗 綁到保單」。
    """
    # ── 搬遷前的 caller-local 名字，在此原名綁定 ──────────────────────────
    # 刻意保留底線開頭的原名，讓下方 790 行與搬遷前**逐字相同**、可直接 diff 比對。
    _oauth_configured = oauth_configured
    _resolve_oauth_cfg = resolve_oauth_cfg
    _get_oauth_client = get_oauth_client
    _gsa_secret = gsa_secret
    _sheet_id_secret = sheet_id_secret
    _get_login_state = get_login_state
    _t3_sheet_client = sheet_client
    # `_sheet_id` 在下方區塊內才會被賦值；此處先給函式級初值，語意與搬遷前
    # `render_portfolio_tab()` 的 `_sheet_id = ""`（原 :1030）一致 —— 那一行
    # 仍在下方原地，本行只是保證「expander 內任何提早 return 都不會 NameError」。
    _sheet_id = ""

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
        # v19.302: 補 _sheet_id_secret fallback(對齊 L828 既有 pattern)——純 Service
        # Account 使用者(設了 POLICY_SHEET_ID secret、從不走 OAuth 登入)原本
        # session 無 policy_sheet_id → _sheet_id_q 為空 → 自動讀回/讀取鈕都不出現。
        _sheet_id_q = (st.session_state.get("policy_sheet_id")
                       or _sheet_id_secret or "").strip()
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
            # v19.302: 委派 SSOT helper — 優先 Service Account(見 _t3_sheet_client)
            return _t3_sheet_client()

        # ── 切換帳本後自動讀回：持倉切換 + 同 code 基金資訊沿用（免重抓）──
        # 只在「帳本 ID 變了」且雲端可達時跑一次；真正不同的新標的留給既有
        # 「📡 載入未載入基金」按鈕抓（避免切換時卡 30s×N）。失敗也記下 id，
        # 不重試迴圈，user 可手動按「📥 雲端讀取」再試。
        # 防呆：本次 session「第一次進入」且已有本地持倉（如剛還原 JSON）→
        # 只記下帳本不自動讀回，避免 sync 把本地狀態洗掉；真正切換 id 時才讀。
        _prev_loaded_id = st.session_state.get("_last_loaded_sheet_id")
        if _sheet_id_q and _can_cloud_q and _prev_loaded_id != _sheet_id_q:
            _skip_first = (_prev_loaded_id is None
                           and bool(st.session_state.get("portfolio_funds")))
            st.session_state["_last_loaded_sheet_id"] = _sheet_id_q
            from ui.helpers.cloud_io import load_all_from_sheet as _auto_load
            from ui.helpers.portfolio_load import count_unloaded_funds
            _ares = ({"ok": False, "_skipped": True} if _skip_first else
                     _auto_load(_t3_cloud_client_q(), _sheet_id_q,
                                st.session_state,
                                oauth_mode=bool(_oauth_configured)))
            if _ares.get("_skipped"):
                pass   # 首次進入保留本地持倉，不自動讀回
            elif _ares.get("ok"):
                st.session_state["t3_last_load_at"] = tw_now_str()
                _reused_n = len(_ares.get("reused", []))
                _, _new_codes = count_unloaded_funds()
                _tot = len(st.session_state.get("portfolio_funds", []) or [])
                st.toast(
                    f"📥 已自動讀回此帳本：持倉 {_tot} 檔"
                    + (f"／沿用 {_reused_n} 檔免重抓" if _reused_n else "")
                    + (f"／{_new_codes} 檔新標的待載入" if _new_codes
                       else "／全部已載入"),
                    icon="📥",
                )
            else:
                st.warning(
                    "⚠️ 自動讀回失敗（可手動按上方「📥 雲端讀取」重試）："
                    f"{_ares.get('error')}"
                )

        with st.container(border=True):
            if _io_panel == "load":
                # v18.166：📥 雲端讀取 = 讀取現有帳本 + 從 Drive 挑帳本（兩者皆在此面板）
                st.markdown("**📥 雲端讀取（全部讀回 / 挑選帳本）**")
                if not _logged_in_q and not (_gsa_secret and _sheet_id_secret):
                    not_ready("還沒用 Google 登入,無法讀取雲端帳本",
                              where="左側 sidebar → 🔐 用 Google 登入")
                    # v19.296: 快捷登入按鈕（免回 Sidebar）
                    if _oauth_configured:
                        try:
                            _cfg_ld = _resolve_oauth_cfg()
                            _url_ld = build_authorize_url(
                                _cfg_ld["client_id"], _cfg_ld["redirect_uri"],
                                state=_get_login_state())
                            st.link_button("🔐 用 Google 登入", _url_ld)
                        except Exception:
                            pass
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
                                st.session_state["t3_last_load_at"] = tw_now_str()
                                _msg = [f"新增 {len(_res['added'])} 檔",
                                        f"保留 {len(_res['kept'])} 檔",
                                        f"移除 {len(_res['removed'])} 檔"]
                                if _res.get("reused"):
                                    _msg.append(f"沿用 {len(_res['reused'])} 檔免重抓")
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
                    not_ready("還沒登入 Google,或還沒指定 Sheet ID",
                              where="左側 sidebar → 🔐 用 Google 登入;Sheet ID 見下方設定區")
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
                            st.session_state["t3_last_save_at"] = tw_now_str()
                            _msg = [f"保單分頁 +{_res['written']} 筆"]
                            if _res["n_state"]:
                                _msg.append(f"_T7_State +{_res['n_state']} 筆")
                            if _res.get("n_overview"):
                                _msg.append(f"_持倉總覽 +{_res['n_overview']} 筆")
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
                    # ⚠️ 2026-09-04 就地更正（**有意識的更正，不是漏刪** ·
                    # 決策者：AI 總管 · 依據：實測）：舊文案寫
                    # ~~「本面板下方的『OAuth 設定』expander」~~ —— **兩個字都錯**：
                    # (a) 本檔**只有一個** `st.expander`（「📋 保單管理（Google Sheets）
                    #     — Sheet 設定 / 保單清單」），OAuth 那塊根本不是 expander，
                    #     使用者會去找一個收合區、找不到；
                    # (b) 它實際叫「🧙 OAuth Client 設定引導（5 分鐘完成）」
                    #     （`st.markdown("##### …")`），名字也對不上。
                    # 與 `shared/ui_control_labels.py` 記載的「🔄 強制重抓其實是
                    # checkbox」完全同型 —— **控制項的「型態」跟名字一樣會指錯**。
                    not_ready("還沒設定 OAuth Client,無法建立 Google Sheet",
                              where="本面板同一個收合區裡的"
                                    "「🧙 OAuth Client 設定引導（5 分鐘完成）」段落")
                elif not _logged_in_q:
                    not_ready("還沒用 Google 登入,無法建立帳本",
                              where="左側 sidebar → 🔐 用 Google 登入")
                    # v19.296: 快捷登入按鈕（免回 Sidebar）
                    if _oauth_configured:
                        try:
                            _cfg_nw = _resolve_oauth_cfg()
                            _url_nw = build_authorize_url(
                                _cfg_nw["client_id"], _cfg_nw["redirect_uri"],
                                state=_get_login_state())
                            st.link_button("🔐 用 Google 登入", _url_nw)
                        except Exception:
                            pass
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
                import json as _json_top
                from ui.helpers.json_backup import build_export_payload
                _payload = build_export_payload(st.session_state)
                _bytes = _json_top.dumps(
                    _payload, ensure_ascii=False, indent=2,
                ).encode("utf-8")
                _ts = tw_now_str("%Y%m%d_%H%M%S")
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
        # v19.52: 函式級初值，避免未登入時 L1133「綁到既有保單」分支讀未綁變數
        _sheet_id = ""
        _logged_in = bool(st.session_state.get("gsheet_tokens"))

        if _oauth_configured:
            if _logged_in:
                st.success("🟢 已用 Google 登入（OAuth）— 登出請至左側 sidebar")
            else:
                st.info("ℹ️ 尚未登入 Google — 請至左側 sidebar 點「🔐 用 Google 登入」")
                # v19.296: 快捷登入按鈕（免回 Sidebar）
                try:
                    _cfg_auth = _resolve_oauth_cfg()
                    _url_auth = build_authorize_url(
                        _cfg_auth["client_id"], _cfg_auth["redirect_uri"],
                        state=_get_login_state())
                    st.link_button("🔐 用 Google 登入", _url_auth)
                except Exception:
                    pass
        elif _gsa_secret and _sheet_id_secret:
            st.info("ℹ️ 偵測到 Service Account 設定，走舊版單表 schema（向後相容）")
            _logged_in = True   # SA 視同已登入
        else:
            # v18.32: In-app OAuth Client 設定 wizard
            #         不必碰 secrets.toml / 不必重新部署，session-only 即時生效
            not_ready("尚未設定 OAuth Client",
                      where="下方步驟：到 GCP console 建一個，再回這裡貼三個值即可登入")
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

            # ── 多帳本管理已移除（v18.188，user 要求）──
            # 改用「📥 雲端讀取（從 Drive 挑帳本）」+「📦 雲端存檔」以存取/讀取方式
            # 管理多帳本，不再需要獨立的「切換到此帳本」流程；建立新帳本見頂部
            # 「✨ 新增帳本」；改名請直接在 Google Drive 操作。

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
                                # v19.436:item_type 退役,全為基金列 → 以非空 fund_code 計數
                                _n_fund = int((_df_v2["fund_code"].astype(str).str.strip()
                                               != "").sum()) if "fund_code" in _df_v2 else 0
                                st.caption(f"共 {len(_df_v2)} 列；基金 {_n_fund} 檔。")
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
                        # `size` 是 cache_info() 欄位契約的必備欄位
                        # (infra.cache.CACHE_INFO_REQUIRED_KEYS)。**刻意直接用
                        # `r["size"]` 而非 `.get("size", 0)`** —— 生產者違約時要
                        # 炸出來(下方 except 會留 stderr),用 0 頂替會靜默少算
                        # entries,那就是 §1 禁止的假數字。
                        _total_entries = sum(r["size"] for r in _info_rows)
                        # ⚠️ 統計欄位是**全有或全無**:proxy 型快取
                        # (`_FX_CACHE` / `_SOURCE_BACKOFF`)只是 raw dict 包裝,
                        # 沒有攔截呼叫 → **命中率不適用**。
                        # 用 `"hits" in r` 明確把它們排除在分母之外,**不要**用
                        # `r.get("hits", 0)` —— 那會把「不適用」寫成「0 次命中」。
                        _stat_rows = [r for r in _info_rows
                                      if "hits" in r and "misses" in r]
                        _total_hits = sum(r["hits"] for r in _stat_rows)
                        _total_misses = sum(r["misses"] for r in _stat_rows)
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
                except Exception as _e_ci:
                    # §1 Fail Loud:**不影響主功能**這個判斷仍然成立(這只是一行
                    # 顯示性 caption),被權衡掉的是它**連 log 都沒有**。
                    # ⚠️ 這個 except 曾經整整吞掉一個真缺陷:2026-08-31 實測
                    # `get_all_cache_info()` 14 列有 4 種形狀,其中 7 列沒有
                    # `size` 欄位(`_ttl_cache` 用 `size`,`_daily_cache` 與兩個
                    # proxy 用 `currsize`)→ `sum(r["size"] …)` 拋
                    # `KeyError: 'size'` → 被這裡吞掉 → **這行 caption 從上線
                    # 以來一次都沒印出來過,而測試一路長綠**。
                    # 根因已在 infra/cache.py 的「cache_info() 欄位契約」收斂;
                    # 這裡補上留痕,讓**下一個**違約者不會再無聲消失。
                    import sys as _sys_ci
                    print(f"[policy_admin/cache_info] 快取狀態 caption 失敗"
                          f"(不影響主功能): {type(_e_ci).__name__}: {_e_ci}",
                          file=_sys_ci.stderr)

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
                    except Exception as _e_ss:
                        # §1 Fail Loud:同上一處的判讀 —— **不影響主流程**成立,
                        # 但**沒有 log** 不成立。這裡包的是三個真的會失敗的遠端
                        # 呼叫(list_policy_worksheets / get_state_metadata /
                        # load_all_ledgers),網路或授權失敗是**預期內**的;問題是
                        # 廣義 `except Exception` 連 KeyError / TypeError 這種
                        # **程式錯誤**也一起吞,和上一處的 KeyError 是同一個病。
                        # 📌 **與上一處的差別(據實記錄,不含糊)**:上一處吞掉的是
                        # 一個**看得見**的 caption;本處寫入的 `_sheet_stats`
                        # **全 repo 沒有任何讀取端**(AST + grep 窮舉:只有這一行
                        # 寫、無人讀)——它的 3 個 `st.metric` 消費者已於 v18.169
                        # 隨「📋 保單清單」區塊移除(見 ARCHITECTURE.md v18.169、
                        # SPEC.md「動態 metric 數字捨棄」)。也就是說本處**目前
                        # 藏不住可見症狀**,但仍是同一種靜默,故一併補留痕。
                        # ⚠️ 「這段是否該整個移除」屬**死碼判定**,取決於「有沒有
                        # 漏看」,且本批沒有任務碰它 → 依 §-1 **登記不動**,已寫進
                        # 本批 PR 描述。
                        import sys as _sys_ss
                        print(f"[policy_admin/sheet_stats] Sheet 統計更新失敗"
                              f"(不影響主流程): {type(_e_ss).__name__}: {_e_ss}",
                              file=_sys_ss.stderr)

                # v18.167：refresh_only 路徑（dump_all / load_all 已移到頂部快捷面板）
                if _refresh_clicked:
                    from ui.helpers.cloud_io import load_all_from_sheet
                    _client = _t3_sheet_client()  # v19.302: 優先 Service Account
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
                    # v19.436:同時涵蓋 v2(10 欄)與 v1 欄名 → 兩種 schema 載入時都有中文標籤,
                    # 不再露出 fund_code/units 等英文原名(Streamlit 自動忽略 df 沒有的鍵)。
                    # v2 欄:核心欄在前;units/avg_nav/avg_fx 為持倉模擬選填,標「(選填)」。
                    st.dataframe(
                        _pdf_cached, use_container_width=True, hide_index=True,
                        column_order=[
                            "policy_id", "fund_code", "fund_name", "currency",
                            "tier", "invest_twd", "div_cash_pct",
                            "units", "avg_nav", "avg_fx",
                            # v1 欄(非 oauth 模式 fallback)
                            "policy_name", "fund_url", "invest_date",
                            "fx_at_buy", "notes", "policy_tier",
                        ],
                        column_config={
                            # v2 schema（10 欄）
                            "policy_id":    st.column_config.TextColumn("保單編號"),
                            "fund_code":    st.column_config.TextColumn("基金代號"),
                            "fund_name":    st.column_config.TextColumn("基金名稱"),
                            "currency":     st.column_config.TextColumn("幣別"),
                            "tier":         st.column_config.TextColumn("級別"),
                            "invest_twd":   st.column_config.NumberColumn("投資金額 (TWD)"),
                            "div_cash_pct": st.column_config.NumberColumn("現金給付%"),
                            "units":        st.column_config.NumberColumn("持有單位數(選填)"),
                            "avg_nav":      st.column_config.NumberColumn("平均成本(選填)"),
                            "avg_fx":       st.column_config.NumberColumn("平均匯率(選填)"),
                            # v1 schema（向後相容）
                            "policy_name":  st.column_config.TextColumn("保單名稱"),
                            "fund_url":     st.column_config.TextColumn("基金代碼"),
                            "invest_date":  st.column_config.TextColumn("投資日期"),
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
                                        _client = get_gspread_client(_gsa_secret)
                                        _act = upsert_policy_row(_client, _sheet_id, _row)
                                        st.success(f"✅ {_act}")
                                    except PolicySheetError as _pe:
                                        st.error(f"❌ 寫入失敗：{_pe}")
                            elif _del_clicked:
                                if not _row["policy_id"] or not _row["fund_url"]:
                                    st.warning("policy_id + fund_url 必填")
                                else:
                                    try:
                                        _client = get_gspread_client(_gsa_secret)
                                        _hit = delete_policy_row(_client, _sheet_id,
                                            _row["policy_id"], _row["fund_url"])
                                        st.success("✅ 已刪除" if _hit else "ℹ️ 主鍵未命中")
                                    except PolicySheetError as _pe:
                                        st.error(f"❌ 刪除失敗：{_pe}")

    # 回傳給 caller：搬遷前這是同一個函式作用域內的區域變數（見模組 docstring）。
    return _sheet_id
