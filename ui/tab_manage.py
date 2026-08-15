"""ui/tab_manage.py — 📋 我的管理室(v19.433)。一站集中管理:選股池 + 投資組合 + 通報。

**不新增儲存**:選股池仍存 Google Sheets `_fund_pool` 分頁、投資組合仍存政策 Sheet
(和 Tab④ 保單管理**同一本、同源**),本頁只是它們的**集中管理介面**,全部重用既有
L1/L2/L0(§8.1 不重造):
- 📁 選股池:重用 `switch_advisor_section._render_pool_editor`(GS + 本地雙後端,永久保存)。
- 💼 投資組合:`load_all_policies_v2` 一覽 + `write_policy_v2` / `delete_policy_worksheet`
  刪改(寫回政策 Sheet;§8.2 EX-CRUD-1 允許 L3 直呼 L1 CRUD)。
- 🔔 通報:LINE 設定狀態 + 預覽本週訊息 + 測試發送 + 設定指引。**每週自動送仍是 NAS 排程**,
  本頁只負責看/測(Streamlit 不背景跑,§1 不假裝能排程)。

資料永久性:寫的是 Google Sheets 不是 App 本機(Streamlit Cloud FS ephemeral)→ 關掉重開都在,
每次開啟只是「從雲端讀回已存的資料」,不是重新輸入。
"""
from __future__ import annotations

import datetime as _dt

import streamlit as st


def _today_tw() -> str:
    return _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8))).date().isoformat()


def _friendly(title, e, level="warning"):
    try:
        from ui.helpers.session import friendly_error
        friendly_error(title, e, level=level)
    except Exception:  # noqa: BLE001
        st.caption(f"⬜ {title}:[{type(e).__name__}] {str(e)[:120]}")


# ───────────────────────── 政策 Sheet client / id ─────────────────────────

def _policy_client_and_sheet():
    """(gspread client, sheet_id) 供投資組合讀寫。用 user OAuth(本人擁有該 Sheet,和 Tab④ 編輯同法)。

    未登入 / 無 sheet_id → (None, reason) 讓呼叫端誠實顯示,不崩(§1)。
    """
    try:
        from ui.helpers.oauth_state import (
            _get_oauth_client,
            _sheet_id_secret,
            refresh_oauth_state,
        )
        try:
            refresh_oauth_state()
        except Exception as _re:  # noqa: BLE001 — token 刷新失敗不擋(下方 _client None 會誠實提示),但留痕(§1)
            import sys as _sys
            print(f"[tab_manage] refresh_oauth_state 失敗(續用現有 token):"
                  f"{type(_re).__name__}: {_re}", file=_sys.stderr)
        _client = _get_oauth_client()
    except Exception as _e:  # noqa: BLE001
        return None, f"OAuth client 取得失敗:{type(_e).__name__}"
    if _client is None:
        return None, "尚未用 Google 登入(請至左側 sidebar 🔐 登入)才能讀取/編輯投資組合。"
    _sid = (st.session_state.get("policy_sheet_id") or _sheet_id_secret or "").strip()
    if not _sid:
        return None, "找不到政策 Sheet ID(請先在 Tab④ 選帳本,或設 POLICY_SHEET_ID secret)。"
    return _client, _sid


# ───────────────────────── ① 選股池 ─────────────────────────

def _import_history_to_pool(df, existing_codes, add_fn) -> dict:
    """把說明書『曾經查過的基金清單』merge 進選股池。回 {added, skipped, total}。

    純函式(依賴注入 add_fn(code, name),不碰 st / L1),供單元測試。合併語意:**已在池的略過、
    不覆蓋**(保住 user 在池裡設過的型態/備註/類別);只加新代號。空代號跳過。
    """
    _seen = {str(c).strip().upper() for c in (existing_codes or set())}
    _added = 0
    _total = 0
    for _, _row in df.iterrows():
        _code = str(_row.get("代號") or _row.get("code") or "").strip().upper()
        if not _code:
            continue
        _total += 1
        if _code in _seen:
            continue
        add_fn(_code, str(_row.get("名稱") or _row.get("name") or "").strip())
        _seen.add(_code)
        _added += 1
    return {"added": _added, "skipped": _total - _added, "total": _total}


def _render_fund_history():
    """📋 曾經查過的基金標的清單(Tab2/Tab3 自動記錄 + 預設)。v19.435 從說明書 Tab⑤ 整段搬來管理室。

    手動新增 / CSV 上傳還原 / 下載 / 清空 / 複製代號 / 升等預設,資料走 `services.fund_history`。
    標題由呼叫端的 expander 提供(避免重複),本函式只渲染內容。
    """
    with st.container():
        from services.fund_history import (
            clear_history as _clear_fh,
            export_preset_funds_json as _export_preset_json,
            get_history_df as _hist_df,
            import_from_csv as _import_fh,
            is_preset as _is_preset,
            promote_to_preset as _promote_preset,
            record_fund as _rec_fh_manual,
        )

        # 手動新增表單
        with st.form("_fh_add_form", clear_on_submit=True):
            _add_c1, _add_c2, _add_c3 = st.columns([1, 2, 1])
            _new_code = _add_c1.text_input(
                "基金代號", placeholder="例：ACCP138",
                key="_fh_new_code",
            )
            _new_name = _add_c2.text_input(
                "基金名稱（可選）", placeholder="例：聯博全球高收益基金",
                key="_fh_new_name",
            )
            _add_c3.markdown("&nbsp;", unsafe_allow_html=True)  # 對齊
            _submitted = _add_c3.form_submit_button(
                "➕ 加入清單", use_container_width=True,
            )
            if _submitted and _new_code.strip():
                _rec_fh_manual(_new_code.strip(), _new_name.strip(), source="manual")
                st.success(f"✅ 已加入 {_new_code.strip().upper()}")
                st.rerun()

        _df_fh = _hist_df()
        _fh_up = st.file_uploader(
            "📥 上傳之前下載的 fund_history.csv 還原紀錄（reboot 後第一件事）",
            type=["csv"],
            key="_fh_upload",
            help="紀錄會與當前清單 merge：同代號疊代次數 + 聯集來源 + 取較早 first / 較晚 last",
        )
        if _fh_up is not None:
            _ret = _import_fh(_fh_up.getvalue())
            if _ret["errors"]:
                st.error("、".join(_ret["errors"]))
            else:
                st.success(
                    f"✅ 還原成功：新增 {_ret['imported']} 檔、merge {_ret['merged']} 檔。"
                )
            _df_fh = _hist_df()
        if _df_fh.empty:
            st.info(
                "尚未查過任何基金。在「🔍 個基深掘」抓取後 / 「📦 組合基金」載入後，"
                "代號與名稱會自動寫入此清單。"
            )
        else:
            _fh_c1, _fh_c2, _fh_c3 = st.columns([2, 1, 1])
            _fh_c1.caption(f"📊 共 **{len(_df_fh)}** 檔唯一基金（依最近查詢時間排序）")
            _fh_csv = _df_fh.to_csv(index=False).encode("utf-8-sig")
            _fh_c2.download_button(
                "💾 下載 CSV",
                _fh_csv,
                file_name="fund_history.csv",
                mime="text/csv",
                use_container_width=True,
                key="_fh_dl_csv",
            )
            if _fh_c3.button("🗑️ 清空紀錄", use_container_width=True, key="_fh_clear"):
                _clear_fh()
                st.rerun()
            st.dataframe(_df_fh, use_container_width=True, hide_index=True)

            # ── v18.290: 點代碼自動複製（手機 tap 即複製）─
            # v18.293 hotfix: get_history_df() 欄名是中文「代號/名稱」非英文 code/name
            # 容錯：兩個欄名都接受（避免未來改 schema 再炸）
            _code_col = "代號" if "代號" in _df_fh.columns else (
                "code" if "code" in _df_fh.columns else None
            )
            _name_col = "名稱" if "名稱" in _df_fh.columns else (
                "name" if "name" in _df_fh.columns else None
            )
            if _code_col is None:
                st.caption(f"⚠️ 找不到代號欄（df columns: {list(_df_fh.columns)}）")
                _codes_list = []
            else:
                st.markdown("**📋 點下方任一代號的右側 📋 icon 即可複製**")
                _codes_list = _df_fh[_code_col].astype(str).str.upper().tolist()
                # 多欄並排省空間（每 4 個一排）
                _per_row = 4
                for _i in range(0, len(_codes_list), _per_row):
                    _cols = st.columns(_per_row)
                    for _j, _code in enumerate(_codes_list[_i:_i + _per_row]):
                        with _cols[_j]:
                            st.code(_code, language=None)

            # ── v18.290: ⭐ 升等為預設（寫回 config/preset_funds.json）─
            st.markdown("---")
            st.markdown("**⭐ 升等為預設清單**（reboot 後仍存在）")
            _promo_c1, _promo_c2, _promo_c3 = st.columns([2, 2, 1])
            _candidates = [c for c in _codes_list if not _is_preset(c)]
            if not _candidates:
                _promo_c1.caption("✅ 清單裡所有基金都已是預設了")
            else:
                _sel_code = _promo_c1.selectbox(
                    "選一檔基金",
                    options=_candidates,
                    key="_fh_promote_sel",
                    label_visibility="collapsed",
                )
                # 取對應 name（從 df 找最新一筆）
                _sel_name = ""
                if _code_col and _name_col:
                    _row_match = _df_fh[
                        _df_fh[_code_col].astype(str).str.upper() == _sel_code
                    ]
                    if not _row_match.empty:
                        _sel_name = str(_row_match.iloc[0].get(_name_col, "") or "")
                _promo_c2.text_input(
                    "基金名稱（會寫進 JSON）",
                    value=_sel_name,
                    key="_fh_promote_name",
                    label_visibility="collapsed",
                )
                if _promo_c3.button(
                    "⭐ 升等", use_container_width=True, key="_fh_promote_btn",
                ):
                    _r = _promote_preset(
                        _sel_code,
                        st.session_state.get("_fh_promote_name", _sel_name),
                    )
                    if _r["errors"]:
                        st.error("、".join(_r["errors"]))
                    elif _r["already"]:
                        st.info(f"ℹ️ {_sel_code} 已在預設清單，名稱已更新")
                    else:
                        st.success(
                            f"✅ 已升等 {_sel_code} → 預設清單共 {_r['total']} 檔。"
                            "**記得下方按「💾 下載 preset_funds.json」並 commit 回 repo，"
                            "否則 Cloud reboot 後會消失！**"
                        )
                    st.rerun()

            # 下載最新 preset_funds.json 給 user commit
            _preset_json_bytes = _export_preset_json()
            st.download_button(
                "💾 下載 preset_funds.json（reboot 持久化必做）",
                _preset_json_bytes,
                file_name="preset_funds.json",
                mime="application/json",
                use_container_width=True,
                key="_fh_dl_preset_json",
                help="升等後務必下載此檔 → 取代 repo 的 config/preset_funds.json → git commit + push",
            )
        st.caption(
            "💡 **內建預設常用基金永遠在**（即使 cache 被清空也會看到，來源標 `preset`）。"
            "user 抓過 / 手動加的紀錄存於容器內 `cache/fund_history.json`，"
            "**Streamlit Cloud 重啟容器時這部分會清空** → 用「下載 CSV → reboot 後上傳 CSV」雙保險。"
        )


def _sec_pool():
    st.markdown("### 📁 選股池(候選基金)")
    st.caption("**這不是你的持倉** —— 是你**還沒買、考慮想換進來**的候選名單,換股顧問拿它跟你的持倉比較。"
               "加/刪/改存到 **`_fund_pool` 分頁**(和你的保單持倉分頁**不同本清單**,不會動到持倉)。")

    with st.expander("📥 從說明書『曾經查過的基金清單』匯入 / 合併進選股池"):
        st.caption("把 Tab⑤ 說明書那份『曾經查過的基金(Tab2/Tab3 自動記錄)+ 預設清單』合併進來。"
                   "**已在池的略過、不覆蓋**你設過的型態/備註;只加新代號。")
        if st.button("📥 立即匯入 / 合併", use_container_width=True, key="pool_import_history"):
            try:
                from repositories.pool_repository import PoolEntry, add_or_update, list_pool
                from services.fund_history import get_history_df
                _existing = {e.code for e in list_pool()}
                _r = _import_history_to_pool(
                    get_history_df(), _existing,
                    lambda code, name: add_or_update(PoolEntry(code=code, name=name)))
                st.success(f"完成:新增 {_r['added']} 檔進選股池"
                           f"(略過已在池 {_r['skipped']} 檔,清單共 {_r['total']} 檔)。")
                st.rerun()
            except Exception as _e:  # noqa: BLE001
                _friendly("匯入基金清單失敗", _e, level="error")

    with st.expander("📋 曾經查過的基金標的清單（Tab2/Tab3 自動記錄 + 預設）—— 上方按鈕的來源清單"):
        try:
            _render_fund_history()                       # v19.435 從說明書 Tab⑤ 搬來
        except Exception as _e:  # noqa: BLE001
            _friendly("基金標的清單載入失敗", _e)

    try:
        from ui.helpers.fund_grp_health.switch_advisor_section import _render_pool_editor
        _render_pool_editor()
    except Exception as _e:  # noqa: BLE001
        _friendly("選股池管理載入失敗", _e)


# ───────────────────────── ② 投資組合 ─────────────────────────

def _sec_portfolio():
    st.markdown("### 💼 投資組合(持倉)")
    st.caption("**這是你目前實際持有的基金**(來自你的保單 Google Sheet)。**唯讀一覽** —— "
               "要改金額/級別或刪保單,請**直接到 Google Sheet 依範本改**(App 不再寫回、不會清空你的資料)。")

    if not st.button("📥 載入 / 重新整理投資組合(雲端)", use_container_width=True, key="manage_pf_load"):
        if not st.session_state.get("_manage_pf_loaded"):
            st.info("按上方按鈕從雲端載入你的投資組合(避免每次重整都打 Google API)。")
            return

    _client, _sid = _policy_client_and_sheet()
    if _client is None:
        st.info(_sid)                                   # 這裡 _sid 是原因字串
        return

    try:
        from repositories.policy.v2 import load_all_policies_v2
        _df = load_all_policies_v2(_client, _sid)
    except Exception as _e:  # noqa: BLE001
        _friendly("讀取投資組合失敗", _e, level="error")
        return
    st.session_state["_manage_pf_loaded"] = True

    from repositories.policy.v2 import ALL_COLS_V2
    # v19.436:10 欄 schema 全為基金列(item_type 退役) → 以非空 fund_code 認基金列。
    _fund_rows = _df[_df["fund_code"].astype(str).str.strip() != ""]
    if _fund_rows.empty and _df.empty:
        st.info("這本 Sheet 目前沒有任何持倉。可到 Tab④ 新增保單/基金。")
        return
    _codes = sorted({str(c).strip() for c in _fund_rows["fund_code"] if str(c).strip()})
    st.success(f"共 {len(_codes)} 檔基金 · {_df['policy_id'].nunique()} 張保單。")

    # v19.452 唯讀:移除「🔧 一鍵修正+精簡 / 💾 存 / 🗑 刪保單」等會覆寫/刪 Sheet 的動作
    # (user 決策改直接改 Sheet)。本區只做**一覽顯示**。
    _labels = {
        "policy_id": "保單", "fund_code": "基金代號", "fund_name": "名稱", "currency": "幣別",
        "tier": "級別", "invest_twd": "投入金額(TWD)", "div_cash_pct": "現金給付%",
        "units": "份額(選填)", "avg_nav": "平均成本(選填)", "avg_fx": "平均匯率(選填)",
    }
    for _pid in sorted({str(p) for p in _df["policy_id"] if str(p).strip()}):
        _pdf = _df[_df["policy_id"].astype(str) == _pid]
        with st.expander(f"📄 保單 {_pid}（{len(_pdf)} 列）", expanded=(_df['policy_id'].nunique() == 1)):
            _cols = [c for c in ALL_COLS_V2 if c in _pdf.columns]
            _view = (_pdf[_cols].reset_index(drop=True)
                     .rename(columns={c: _labels.get(c, c) for c in _cols}))
            st.dataframe(_view, use_container_width=True, hide_index=True)
    st.caption("唯讀顯示。要改金額/級別或刪保單,請**直接到 Google Sheet 依範本改**(App 不覆寫、不清空)。")


def _prepare_write_df(edited_df, policy_id):
    """編輯後的 grid → 準備給 write_policy_v2 的 df:補 policy_id。

    v19.436:10 欄 schema 全為基金列(item_type 退役)。write_policy_v2 會跳過無 fund_code
    的空列,並保留 units/avg_nav/avg_fx 等選填欄照原樣帶著(§1 防資料流失:整張覆寫不抹掉)。
    純函式(不碰 st / 網路),供單元測試鎖住此回寫前處理(§6)。
    """
    _out = edited_df.copy()
    _out["policy_id"] = policy_id
    return _out


def _run_fix_and_shrink(client, sheet_id):
    """v19.436:一鍵修正基金名稱 + 精簡 Sheet。逐張進度條;完成後清快取重載。"""
    try:
        from ui.helpers.cloud_io import fix_and_shrink_v2_sheets
        from ui.helpers.v2_editor import _autofill_from_moneydj
    except Exception as _e:  # noqa: BLE001
        _friendly("載入修正工具失敗", _e, level="error")
        return
    _bar = st.progress(0.0, text="準備中…")

    def _cb(done, total, pid):
        _bar.progress(done / max(total, 1), text=f"處理 {pid}（{done}/{total}）…")

    try:
        with st.spinner("逐張重抓基金名稱 + 精簡欄位(需數十秒)…"):
            _res = fix_and_shrink_v2_sheets(
                client, sheet_id, info_fetcher=_autofill_from_moneydj, progress_cb=_cb)
    except Exception as _e:  # noqa: BLE001
        _friendly("修正 + 精簡失敗", _e, level="error")
        return
    _bar.empty()
    # 備份失敗 → fix_and_shrink 已中止(未動原本),只回 errors、無 policies
    if _res.get("errors") and _res.get("policies", 0) == 0 and not _res.get("names_fixed"):
        for _err in _res["errors"][:5]:
            st.error(f"❌ {_err}")
        return
    st.success(f"✅ 完成:{_res['policies']} 張保單 · {_res['funds']} 檔基金 · "
               f"修正名稱 {_res['names_fixed']} 筆。已精簡成 10 欄。")
    if _res.get("backup_url"):
        st.info(f"🛡️ 動手前已備份整本 Sheet:[開啟備份副本]({_res['backup_url']})")
    for _err in _res.get("errors", [])[:5]:
        st.warning(f"⚠️ {_err}")
    # 清 load_all 短快取,重載拿最新
    try:
        from repositories.policy.v2 import clear_load_all_ws_cache
        clear_load_all_ws_cache()
    except Exception:  # noqa: BLE001
        pass
    st.session_state["_manage_pf_loaded"] = True
    st.rerun()


def _save_policy(client, sheet_id, policy_id, edited_df):
    """編輯後的 grid → 回寫政策 Sheet(重用 write_policy_v2;§1 失敗顯示不崩)。"""
    try:
        from repositories.policy.v2 import write_policy_v2
        _out = _prepare_write_df(edited_df, policy_id)
        _n = write_policy_v2(client, sheet_id, policy_id, _out)
        st.success(f"已存 {policy_id}:{_n} 檔寫回雲端。")
        st.session_state["_manage_pf_loaded"] = True
        st.rerun()
    except Exception as _e:  # noqa: BLE001
        _friendly(f"保單 {policy_id} 存檔失敗", _e, level="error")


def _delete_policy(client, sheet_id, policy_id):
    try:
        from repositories.policy.v2 import delete_policy_worksheet
        _ok = delete_policy_worksheet(client, sheet_id, policy_id)
        if _ok:
            st.success(f"已刪除整張保單 {policy_id}。")
            st.rerun()
        else:
            st.warning(f"保單 {policy_id} 找不到或未刪除。")
    except Exception as _e:  # noqa: BLE001
        _friendly(f"保單 {policy_id} 刪除失敗", _e, level="error")


# ───────────────────────── ③ 通報 ─────────────────────────

def _sec_notify():
    st.markdown("### 🔔 換股通報(LINE)")
    # ── 稽核 E10：燈號假陰性 ────────────────────────────────────────────────
    # 原本只檢查 `LINE_CHANNEL_TOKEN`，但 `infra/line_push.py:58` 明確支援別名
    # `LINE_CHANNEL_ACCESS_TOKEN`（該檔 :10 註明「GitHub secret 常用後者」）。
    # 只設別名時：燈號顯示 🔴「尚未設定」，而且下方 `if _ok and st.button(...)`
    # 會**短路 → 測試按鈕整顆不渲染** —— 功能完好卻既說壞掉、又不給你測。
    # 改用與 push_text 完全相同的別名解析，避免兩邊各判各的。
    from infra.line_push import _resolve as _line_resolve
    _line_token = (_line_resolve("LINE_CHANNEL_TOKEN", None)
                   or _line_resolve("LINE_CHANNEL_ACCESS_TOKEN", None))
    _ok = bool(_line_token) and bool(_line_resolve("LINE_USER_ID", None))
    st.caption(("🟢 LINE 憑證已設定" if _ok else
                "🔴 LINE 尚未設定(App secrets 缺 LINE_CHANNEL_TOKEN / LINE_USER_ID → 只能預覽,不能測試發送)")
               + "　·　⚠️ **每週自動推播是你 NAS 的排程在跑**,本頁只負責預覽 + 測試發送。")

    _funds = st.session_state.get("portfolio_funds") or []
    # 稽核 E9：原本只看 `loaded` —— 但 `ui/helpers/portfolio/load.py:219-221` 會
    # 對抓取失敗的基金寫入 `{"loaded": True, "load_error": "..."}`，所以抓失敗的
    # 檔一樣會被算進通報觀察集合。全 repo 其他 8 個消費端都用
    # `loaded and not load_error`（含本檔 `_divcal_gather_items` 的「稽核 H2」），
    # **這裡是唯一漏網**。
    _loaded = [f for f in _funds if f.get("loaded") and not f.get("load_error")]

    if st.button("👁️ 預覽本週會送的通報訊息", use_container_width=True, key="manage_notify_preview"):
        _preview_notify(_loaded)

    if _ok and st.button("✉️ 測試發送一則到我的 LINE", use_container_width=True, key="manage_notify_test"):
        _test_send()

    with st.expander("📖 每週自動通報 — NAS 設定步驟"):
        st.markdown(
            "1. **LINE bot**:LINE Developers 建 Messaging API channel → 拿 channel access token + 你的 userId + 加 bot 好友。\n"
            "2. **NAS 環境變數**:`google_service_account` / `macro_weights_sheet_id` / `LINE_CHANNEL_TOKEN` / `LINE_USER_ID`。\n"
            "3. **先驗證(不會真送)**:`python scripts/weekly_switch_notify.py --dry-run`。\n"
            "4. **排程(每週一傍晚)**:`30 18 * * 1 cd /path/to/repo && python scripts/weekly_switch_notify.py`。\n\n"
            "完整版見 `docs/WEEKLY_SWITCH_NOTIFY_SETUP.md`。⚠️ LINE Notify 已於 2025/03 停用,本功能走 Messaging API。"
        )


def _preview_notify(funds):
    if not funds:
        st.info("目前沒有『已載入』的持倉基金 → 先到 Tab④/組合健診 載入基金,再回來預覽。")
        return
    try:
        from repositories.pool_repository import list_pool
        from services.switch_advisor import advise_switches
        from services.switch_notify import build_notification
        from ui.helpers.fund_grp_health.switch_advisor_section import (
            _fx_label,
            _macro_composite,
            _pool_rows,
            _rows_with_nav,
            _underperf_by_code,
        )
        pool = list_pool()
        # 稽核 E8(d)：key 未正規化 → 選股池代碼若為小寫就對不到 type_override /
        # category。`scripts/weekly_switch_notify.py:296` 早就 `.upper()` 了
        # （且標了「稽核修」），本頁保留著同一個已修過的 bug。
        _pbc = {str(e.code or "").strip().upper(): e for e in pool}
        with st.spinner("計算本週通報預覽…"):
            _held = _rows_with_nav(funds, _pbc)
            _cands = _pool_rows(pool, funds)
            _res = advise_switches(_held, _cands, fx_label=_fx_label(),
                                   macro_composite=_macro_composite(),
                                   underperformance_by_code=_underperf_by_code(funds))
            _note = build_notification(_res, as_of=_today_tw(),
                                       skipped=max(0, len(funds) - len(_held)))
        st.text_area("本週會送的訊息(預覽,不會真的送)", _note["message"], height=260)
        # ── 稽核 E8：原文案宣稱「和 NAS 週報同一套邏輯」，實測 6 項差異 ──────────
        # (a) 觀察集合：本頁只看 session 已載入持倉；NAS 讀 Sheet 持倉 ∪
        #     WATCH_CSV_URL 追蹤清單（weekly_switch_notify.py:298-306）
        # (b) macro composite：本頁傳 `_macro_composite()`；NAS 預設 None
        #     （:328，除非 --with-macro）→ switch_advisor.py:225-226 讓
        #     **成長型賣出訊號在 NAS 端結構性永不觸發**。本頁說「該賣」，NAS 不送。
        # (c) source_by_code：本頁不傳 → 預覽看不到 [持倉]/[觀察] 標籤
        # (d) pool key 大小寫（已於上方修）
        # (e) skipped：本頁 `max(0, len(funds)-len(_held))`，而 `_assemble_rows`
        #     沒有任何 continue → **恆為 0**（不是低報，是該欄位完全失效）
        # (f) rows 組法：本頁走 rotation._assemble_rows；NAS :157-188 本地重製
        # 治本是把 NAS 那三個函式抽成 streamlit-free 的 services/switch_pipeline.py
        # 兩邊共用（已列 P0 待辦）；在那之前，先誠實揭露差異，不再宣稱同一套。
        st.caption(
            f"本週會通報 **{_note['n_actionable']}** 檔"
            f"（should_notify={_note['should_notify']}）。沒建議時 NAS 週報不會吵你。"
        )
        st.info(
            "ℹ️ **這是以「你目前已載入的持倉」試算的預覽，可能與 NAS 實際送出的不同**：\n\n"
            "- NAS 週報的標的是 **Google Sheet 持倉 ∪ 追蹤清單（`WATCH_CSV_URL`）**，"
            "本頁只涵蓋已載入的持倉\n"
            "- NAS 預設**不帶總經 composite**，所以「成長型看衰 → 賣出」這類建議"
            "只會出現在本頁預覽、**不會被送出**\n\n"
            "要看 NAS 真正會送什麼，請在 NAS 上跑 "
            "`python scripts/weekly_switch_notify.py --dry-run`。"
        )
    except Exception as _e:  # noqa: BLE001
        _friendly("預覽通報失敗", _e, level="error")


def _test_send():
    from infra.line_push import LinePushError, push_text   # import 移出 try:否則 import 失敗會
    try:                                                    # 讓 except LinePushError 變 NameError(稽核 FINDING 3)
        _r = push_text(f"✅ 基金戰情室測試（{_today_tw()}）：你的 LINE 通報設定正確,週報會送到這裡。",
                       dry_run=False)
        if _r.get("sent"):
            st.success("已發送測試訊息到你的 LINE 🎉 收到就代表設定成功。")
        else:
            st.warning(f"未發送:{_r.get('reason')}")
    except LinePushError as _e:  # noqa: BLE001
        st.error(f"發送失敗:{_e}")
    except Exception as _e:  # noqa: BLE001
        _friendly("測試發送失敗", _e, level="error")


# ───────────────────────── 入口 ─────────────────────────

def _divcal_gather_items():
    """蒐集月曆基金:選股池(現抓配息)∪ 已載入持倉(dividends 現成),依代號去重。

    選股池項目不帶配息 → 逐檔 auto_fetch_moneydj 現抓(帶進度);持倉直接用既有 dividends。
    回 (items, n_pool, n_held)。
    """
    from services.dividend_calendar import detect_house
    from services.moneydj_fetcher import auto_fetch_moneydj

    _funds = st.session_state.get("portfolio_funds") or []
    _held = [f for f in _funds if f.get("loaded") and not f.get("load_error")]   # 稽核 H2
    try:
        from repositories.pool_repository import list_pool
        _pool = list_pool()
    except Exception:  # noqa: BLE001
        _pool = []

    items, seen = [], set()
    for f in _held:                                  # 持倉:dividends 現成
        _c = str(f.get("code") or "").strip().upper()
        if not _c or _c in seen:
            continue
        seen.add(_c)
        items.append({"code": _c, "name": f.get("name") or _c,
                      "house": detect_house(f.get("name") or ""),
                      "dividends": f.get("dividends") or (f.get("moneydj_raw") or {}).get("dividends")})

    _pool_new = [e for e in _pool if str(e.code or "").strip().upper() not in seen]
    if _pool_new:
        _prog = st.progress(0.0, text="抓選股池各檔配息中…")
        for _i, e in enumerate(_pool_new):
            _c = str(e.code or "").strip().upper()
            try:
                fd = auto_fetch_moneydj(_c) or {}
                _name = fd.get("fund_name") or e.name or _c
                items.append({"code": _c, "name": _name, "house": detect_house(_name),
                              "dividends": fd.get("dividends")})
            except Exception:  # noqa: BLE001 — 單檔抓失敗略過,不擋整批
                items.append({"code": _c, "name": e.name or _c, "house": "", "dividends": None})
            _prog.progress((_i + 1) / len(_pool_new), text=f"抓配息 {_i + 1}/{len(_pool_new)}…")
        _prog.empty()
    return items, len(_pool), len(_held)


def _sec_dividend_calendar():
    """🗓️ 除息行事曆:選股池(現抓配息)∪ 已載入持倉 → 本月除息/配息推估月曆(嵌入 HTML)。"""
    import datetime as _dt

    st.markdown("### 🗓️ 除息行事曆")
    st.caption("你的基金**本月除息 / 配息日推估**(選股池 + 已載入持倉)。用過往配息節奏推算,"
               "**非官方公告**;累積型不配息的自動不顯示,加減標的 → 下月自動更新。")

    if st.button("🗓️ 抓選股池標的 → 產生本月除息月曆", use_container_width=True, key="divcal_gen"):
        try:
            _items, _np, _nh = _divcal_gather_items()
            if not _items:
                st.info("選股池與已載入持倉都是空的 → 先到上面『選股池』加標的,或到組合健診載入基金。")
                st.session_state.pop("_divcal_items", None)
            else:
                st.session_state["_divcal_items"] = _items
                st.session_state["_divcal_src"] = f"選股池 {_np} 檔 + 持倉 {_nh} 檔"
        except Exception as _e:  # noqa: BLE001
            _friendly("抓取配息失敗", _e, level="error")

    _items = st.session_state.get("_divcal_items")
    if not _items:
        st.caption("按上面按鈕：會現抓選股池各檔配息史(約數秒~數十秒),再產生本月月曆。")
        return

    _now = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8)))
    try:
        import streamlit.components.v1 as _components

        from services.dividend_calendar import build_month_calendar
        from ui.helpers.dividend_calendar_render import render_month_calendar_html
        _cal = build_month_calendar(_items, _now.year, _now.month)
        _html = render_month_calendar_html(_cal)
        _components.html(_html, height=900, scrolling=True)
        _c = _cal["counts"]
        st.caption(f"來源:{st.session_state.get('_divcal_src', '')}　·　本月推估除息 {_c['events']} 檔"
                   + (f"｜{_c['excluded']} 檔累積型/無配息" if _c["excluded"] else "")
                   + (f"｜{_c['unpredictable']} 檔無法推估" if _c.get("unpredictable") else ""))
        st.download_button("⬇️ 下載本月月曆 HTML", _html,
                           file_name=f"除息行事曆_{_now.year}{_now.month:02d}.html",
                           mime="text/html", use_container_width=True, key="divcal_dl")
    except Exception as _e:  # noqa: BLE001
        _friendly("產生除息月曆失敗", _e, level="error")


def _yf_1y_return(ticker: str) -> "float | None":
    """yf 收盤 → 近1年報酬%(252 交易日;不足取全期)。無資料/失敗 → None(§1)。"""
    try:
        from repositories.macro.yf import fetch_yf_close
        _s = fetch_yf_close(ticker, range_="2y")
        if _s is None or len(_s) < 30:
            return None
        _last = float(_s.iloc[-1])
        _base = float(_s.iloc[-252]) if len(_s) >= 252 else float(_s.iloc[0])
        return (_last / _base - 1) * 100.0 if _base > 0 else None
    except Exception:  # noqa: BLE001
        return None


def _sec_policy_portfolio():
    """📊 保單組合分析:上傳保單總表 CSV → 依保單分組 + 真實報酬(成本 vs 現價 + 已領配息)+ 標最差
    + vs 大盤(近1年近似)+ 一鍵載入健診/換股/除息。"""
    import pandas as pd

    from services.portfolio_csv import (
        parse_holdings,
        policy_returns,
        summarize_by_policy,
    )
    st.markdown("### 📊 保單組合分析(上傳總表)")
    st.caption("上傳你的『保單持倉總表』CSV → 依**保單**分組、算**真實報酬**(成本 vs 現價 + 已領配息)、"
               "標出**最差那組**。⚠️ 資料只在本次 session,**不寫進 repo/雲端**。")

    _up = st.file_uploader("上傳保單總表 CSV（保單號碼 / 基金代碼 / 幣別 / 投資金額(TWD) …）",
                           type=["csv"], key="polcsv_up")
    if _up is not None:
        _raw = _up.getvalue()
        _txt = None
        for _enc in ("utf-8-sig", "utf-8", "big5", "cp950"):
            try:
                _t = _raw.decode(_enc)
                if "�" not in _t:
                    _txt = _t
                    break
            except Exception:  # noqa: BLE001
                continue
        _txt = _txt if _txt is not None else _raw.decode("utf-8", errors="replace")
        _hs = parse_holdings(_txt)
        if not _hs:
            st.error("認不出表頭(需有『保單號碼』『基金代碼』欄)或無有效資料列。")
        else:
            st.session_state["_polcsv_holdings"] = _hs
            st.session_state.pop("_polcsv_enriched", None)      # 換檔 → 清舊現價
            st.success(f"讀到 {len(_hs)} 筆持倉 · {len({h['policy'] for h in _hs})} 張保單。")

    _hs = st.session_state.get("_polcsv_holdings")
    if not _hs:
        st.caption("上傳後顯示分組總表;再按『抓現價』算真實報酬 + 排名(哪組最差)。")
        return

    if st.button("💹 抓現價 → 算真實報酬 + 排名", use_container_width=True, key="polcsv_price"):
        try:
            from services.fund_service import get_latest_fx
            from services.moneydj_fetcher import auto_fetch_moneydj
            from services.portfolio_csv import enrich_returns
            _codes = sorted({h["code"] for h in _hs})
            _nav, _prog = {}, st.progress(0.0, text="抓現價中…")
            for _i, _c in enumerate(_codes):
                try:
                    _s = (auto_fetch_moneydj(_c) or {}).get("series")
                    if _s is not None and len(_s) > 0 and float(_s.iloc[-1]) > 0:
                        _nav[_c] = float(_s.iloc[-1])
                except Exception:  # noqa: BLE001
                    pass
                _prog.progress((_i + 1) / len(_codes), text=f"抓現價 {_i + 1}/{len(_codes)}…")
            _prog.empty()
            _usd = None
            try:
                _usd = get_latest_fx("USDTWD")
            except Exception:  # noqa: BLE001
                pass
            st.session_state["_polcsv_enriched"] = enrich_returns(_hs, nav_by_code=_nav, usdtwd=_usd)
            # vs 大盤(近1年近似):^GSPC(美股)/ ^TWII(台股)
            st.session_state["_polcsv_bench"] = {"spx": _yf_1y_return("^GSPC"),
                                                 "twii": _yf_1y_return("^TWII"),
                                                 "usdtwd": _yf_1y_return("TWD=X")}  # M5:USD/TWD 近1年%
        except Exception as _e:  # noqa: BLE001
            _friendly("抓現價/算報酬失敗", _e, level="error")

    _summ = summarize_by_policy(_hs)
    _c1, _c2, _c3 = st.columns(3)
    _c1.metric("總投資額", f"{sum(d['invest_twd'] for d in _summ):,.0f} TWD")
    _c2.metric("累積已領配息", f"{sum(d['cum_div_twd'] for d in _summ):,.0f} TWD")
    _c3.metric("保單數", f"{len(_summ)}")

    # v19.451 唯讀:移除「📤 匯入到 Google Sheet」(write_policy_v2 = clear→覆寫,會清空同名分頁;
    # user 2026-08-13 決策改直接在 Sheet 依範本填)。此區只保留上傳總表的**分析顯示**,不寫回。
    st.caption("ℹ️ 這裡只做**分析顯示**,不寫回 Google Sheet。要建/改保單資料,請直接在 "
               "Google Sheet 依範本欄位填(App 不再覆寫、不會清空你的資料)。")

    _en = st.session_state.get("_polcsv_enriched")
    if not _en:
        st.dataframe(pd.DataFrame([{
            "保單": d["policy"], "投資額(TWD)": f"{d['invest_twd']:,.0f}",
            "核心%": (f"{d['core_pct']:.0f}%" if d["core_pct"] is not None else "—"),
            "累領配息": f"{d['cum_div_twd']:,.0f}", "檔數": d["n_funds"],
        } for d in _summ]), hide_index=True, use_container_width=True)
        st.info("按上面『💹 抓現價』才會算真實報酬 + 排名(哪組最差)。")
        return

    from services.portfolio_csv import policy_benchmark_1y
    _pr = policy_returns(_en)
    _maxrank = max((p["rank"] for p in _pr if p.get("rank")), default=0)
    _n_suspect = sum(1 for h in _en if h.get("nav_suspect"))
    _bench = st.session_state.get("_polcsv_bench") or {}
    _pbench = policy_benchmark_1y(_hs, spx_1y_pct=_bench.get("spx"), twii_1y_pct=_bench.get("twii"),
                                  usdtwd_1y_pct=_bench.get("usdtwd"))  # M5:SPX 換 TWD basis
    _rows = []
    for p in _pr:
        _r = p.get("rank")
        _lamp = "🔴 最差" if _r == 1 else ("🟢 最佳" if _r and _r == _maxrank else ("🟡" if _r else "⬜"))
        if p["total_return_pct"] is not None:
            _ret = f"{p['total_return_pct']:+.1f}%"
        elif p["n_priced"] and (p.get("coverage") or 0) < 0.6:
            _ret = f"覆蓋不足 {p['coverage'] * 100:.0f}%"
        else:
            _ret = "資料不足"
        _bp = _pbench.get(p["policy"])
        _rows.append({
            "燈": _lamp, "排名": _r or "—", "保單": p["policy"], "真實報酬%": _ret,
            "大盤近1年": (f"{_bp:+.1f}%" if _bp is not None else "—"),
            "超額(近似)": (f"{p['total_return_pct'] - _bp:+.1f}pp"
                           if (p["total_return_pct"] is not None and _bp is not None) else "—"),
            "投資額": f"{p['invest_twd']:,.0f}",
            "現值": (f"{p['current_value_twd']:,.0f}" if p["current_value_twd"] is not None else "—"),
            "累領配息": f"{p['cum_div_twd']:,.0f}", "已估/檔數": f"{p['n_priced']}/{p['n_funds']}",
        })
    st.dataframe(pd.DataFrame(_rows), hide_index=True, use_container_width=True)
    _worst = next((p for p in _pr if p.get("rank") == 1), None)
    if _worst and _maxrank > 1:                     # 稽核 F4:只有 1 組可排名時不喊「最差」
        st.warning(f"🔴 **最差組合:保單 {_worst['policy']}**，真實報酬 "
                   f"{_worst['total_return_pct']:+.1f}%(含息、成本 vs 現價)。")
    if _n_suspect:
        st.caption(f"⚠️ {_n_suspect} 檔現價與成本淨值比異常(疑幣別/計價單位對不上)→ 已排除不硬算(§1)。")
    st.caption("真實報酬 =(現值 + 已領配息 − 成本)÷ 成本;現價現抓、含息;缺現價/覆蓋率<60% 不排名(§1);"
               "配息用各檔實際值加總(不分攤)。⚠️ **超額為近似**:真實報酬是持有至今、大盤是固定近1年,期間不對齊。")

    # 餵現有引擎:載入這些基金到 portfolio_funds(健診/換股/除息 都吃這個)
    # ── 稽核 E7（2026-08-14）：這是**整個換掉**，不是「加進去」──────────────────
    # 原本按下去就 `st.session_state["portfolio_funds"] = _funds` —— 靜默全覆蓋。
    # 兩個後果：
    #   (a) 你原本從保單分頁載入的持倉**整批消失**，而按鈕文案只說「載入」。
    #   (b) 這裡是**按 code 跨保單加總**的，產出的項目沒有 `policy_id` ——
    #       而全站的持倉主鍵是 `(policy_id, code)`（v18.56 修 bug 修出來的複合鍵）。
    #       覆蓋之後，T7 帳本、配置、換股那些依賴 policy_id 的地方會抓不到保單歸屬。
    # 這裡不改變「覆蓋」這個行為（CSV 分析本來就是另一種視角），只把代價講清楚並要求確認。
    _cur_pf = st.session_state.get("portfolio_funds") or []
    _cur_with_pid = sum(1 for _f in _cur_pf
                        if isinstance(_f, dict) and _f.get("policy_id"))
    if _cur_pf:
        st.warning(
            f"⚠️ 目前已載入 **{len(_cur_pf)} 檔**"
            + (f"（其中 {_cur_with_pid} 檔有保單歸屬）" if _cur_with_pid else "")
            + "。按下面的按鈕會**整個換成**這份 CSV 的內容，不是加進去。\n\n"
            + ("這份 CSV 是**按基金代碼跨保單加總**的，所以載入後的項目"
               "**沒有保單歸屬** —— 依賴保單的功能（T7 帳本、配置檢查、換股）"
               "會看不到是哪一張保單的。要換回來，回上面重新從保單分頁載入即可"
               "（Google Sheet 上的資料不會被動到）。" if _cur_with_pid else "")
        )
        _ok_overwrite = st.checkbox(
            "我知道這會取代目前已載入的組合", key="polcsv_load_confirm")
    else:
        _ok_overwrite = True
    if st.button("📥 把這些基金載入 健診 / 換股 / 除息(現有引擎)", use_container_width=True,
                 key="polcsv_load", disabled=not _ok_overwrite):
        try:
            from services.fund_row import process_one_fund
            from ui.helpers.fund_grp_health._utils import _build_fund_dict
            _inv_by_code: dict = {}
            for h in _hs:
                _inv_by_code[h["code"]] = _inv_by_code.get(h["code"], 0.0) + (h.get("invest_twd") or 0.0)
            _codes = sorted(_inv_by_code)
            _funds, _prog = [], st.progress(0.0, text="載入基金中…")
            for _i, _c in enumerate(_codes):
                try:
                    _r = process_one_fund(_c, _inv_by_code[_c] or 1_000_000.0)
                    if _r.get("ok") and _r.get("_fund_raw"):
                        _funds.append(_build_fund_dict(_r["_fund_raw"], _c, _inv_by_code[_c]))
                except Exception:  # noqa: BLE001
                    pass
                _prog.progress((_i + 1) / len(_codes), text=f"載入 {_i + 1}/{len(_codes)}…")
            _prog.empty()
            if _funds:
                # 稽核 E7:標記這批**沒有保單歸屬**,讓下游分得出來(§1 不假裝完整)。
                # 這裡是按 code 跨保單加總的,policy_id 在這個視角下本來就不存在,
                # 但下游不該把「沒有」誤讀成「還沒填」。
                for _f in _funds:
                    _f.setdefault("policy_id", "")
                    _f["_from_policy_csv"] = True
                st.session_state["portfolio_funds"] = _funds
                st.success(f"✅ 已載入 {len(_funds)}/{len(_codes)} 檔 → 到「🗓️ 除息行事曆 / 🔔 換股通報預覽 / "
                           "組合健診」都會用這些基金。")
                st.caption("ℹ️ 這批是**按基金代碼跨保單加總**的，沒有保單歸屬 —— "
                           "T7 帳本與配置檢查會看不到是哪一張保單。"
                           "要回到分保單的視角，請從上方保單分頁重新載入。")
            else:
                st.warning("全部載入失敗(抓取問題)。")
        except Exception as _e:  # noqa: BLE001
            _friendly("載入基金失敗", _e, level="error")


def _sec_nav_backfill() -> None:
    """📥 補歷史淨值(FundClear 境外基金)→ 存進 GS nav_history → 根治「抓不到→外推→假吃本金」。"""
    st.markdown("### 📥 補歷史淨值(FundClear 境外基金)")
    st.caption("抓 FundClear 境外基金的**完整歷史淨值**(單次可達 ~20 年)存進 Google Sheet,"
               "讓健診有足夠序列算**真實 1 年報酬** —— 根治「抓不到官方資料 → 外推 → 假吃本金」"
               "(如 ACTI71 −38%)。")
    st.warning("⚠️ **務必選『你實際持有的那個級別』**(同幣別、同累積 Acc/配息 Dist)——"
               "抓來的歷史會**併入**該基金既有序列,若級別/幣別對不上(例:你持配息級別卻抓累積級別、"
               "或幣別不同),接點會產生**跳空 → 報酬失真**。**最安全**是用在 App 目前完全抓不到"
               "淨值的基金(如 ACTI71),那時併入的是純 FundClear 單一序列,不會混。")
    with st.expander("展開:①挑基金 → ②選級別 → ③下載存進 Google Sheet"):
        # ① 用「現在有的資料」:載入你的持倉,從中挑(自動帶基金名稱 + 內部碼,免手打、免打錯)
        if st.button("📇 載入我的持倉清單(從中挑基金)", key="navbf_load_holdings"):
            try:
                _cli_h, _sid_h = _policy_client_and_sheet()
                if _cli_h is None:
                    st.info(_sid_h)
                else:
                    from repositories.policy.v2 import load_all_policies_v2
                    _pdf_h = load_all_policies_v2(_cli_h, _sid_h)
                    _seen, _hold = set(), []
                    for _r in _pdf_h.itertuples(index=False):
                        _c = str(getattr(_r, "fund_code", "") or "").strip().upper()
                        _nm = str(getattr(_r, "fund_name", "") or "").strip()
                        if _c and _c not in _seen:
                            _seen.add(_c)
                            _hold.append({"code": _c, "name": _nm})
                    st.session_state["navbf_holdings"] = _hold
                    if not _hold:
                        st.info("持倉裡沒有基金代號可挑。")
            except Exception as _e:  # noqa: BLE001
                _friendly("載入持倉失敗", _e, level="error")

        _hold = st.session_state.get("navbf_holdings") or []
        _fixed_code = ""
        if _hold:
            _hopts = {f"{h['name'] or h['code']}（{h['code']}）": h for h in _hold}
            _hpick = _hopts.get(st.selectbox("① 從你的持倉挑一檔(自動帶名稱 + 內部碼)",
                                             list(_hopts), key="navbf_hold_pick"))
            _name = (_hpick["name"] or _hpick["code"]) if _hpick else ""
            _fixed_code = _hpick["code"] if _hpick else ""
            st.caption(f"→ 用名稱「**{_name}**」去 FundClear 找,抓到後存進內部碼「**{_fixed_code}**」。")
        else:
            _name = st.text_input("① 基金名稱(或先按上面『載入持倉』從清單挑)", key="navbf_name",
                                  placeholder="例:聯博多元資產收益組合基金")
        _org = st.text_input("機構代碼(選填;知道就填可加速。例 019=安聯)", key="navbf_org",
                             placeholder="留空 = 全機構搜尋(較慢;機構清單 endpoint 部署後才驗證)")
        with st.expander("🔧 出現「機構清單 endpoint 全部候選失敗」?怎麼辦"):
            st.markdown(
                "FundClear 的**機構清單**那支 API 路徑還沒驗證到(規格書 §2.5 也標未驗證)。兩個解法:\n\n"
                "**A. 直接填機構代碼(最快)**:在上面『機構代碼』欄填代碼再按找。已知 **019 = 安聯**。\n\n"
                "**B. 幫我抓真實路徑(一勞永逸,之後就能用下拉)**:\n"
                "1. 電腦瀏覽器開 `https://www.fundclear.com.tw/offshore/nav-profit/fund-nav?type=history`\n"
                "2. 按 **F12** → 選 **Network(網路)** → 篩選 **Fetch/XHR**\n"
                "3. **重新整理**頁面\n"
                "4. 找開頭像 `common-select` 的請求,把它的 **Request URL** 貼給我\n"
                "5. (順便)機構下拉選你的基金公司(如聯博),看新請求 payload 裡的 `organizeCode`,"
                "那就是你的機構代碼\n\n"
                "把 4/5 貼給我,我把實際 endpoint 寫死,你之後就不用填代碼。")
        # v19.456:user 想「打代碼」→ 用選股池 + 持倉的代碼↔名稱對照,把代碼自動換成名稱去 FundClear
        # 找、代碼留著存回 nav_history。打名稱則原樣。
        _code_name_map = {}
        try:
            from repositories.pool_repository import list_pool
            for _pe in list_pool():
                if getattr(_pe, "code", ""):
                    _code_name_map[str(_pe.code).strip().upper()] = getattr(_pe, "name", "") or ""
        except Exception:  # noqa: BLE001 — 選股池讀不到不阻斷,仍可用名稱直接找
            pass
        for _h in (st.session_state.get("navbf_holdings") or []):
            _code_name_map.setdefault(str(_h.get("code", "")).strip().upper(), _h.get("name", "") or "")
        from services.fundclear_backfill import resolve_search_name
        _search_name, _resolved_code = resolve_search_name(_name, _code_name_map)
        if _resolved_code and _search_name != str(_name).strip():
            _fixed_code = _resolved_code            # 打代碼 → 存回用該代碼(健診讀得回)
            st.caption(f"🔁 代碼 **{_resolved_code}** → 名稱「**{_search_name}**」"
                       "(拿名稱去 FundClear 找、拿代碼存回)")

        if st.button("🔎 找 FundClear 對應基金", key="navbf_find", disabled=not _search_name.strip()):
            try:
                from services.fundclear_backfill import find_fund_candidates
                with st.spinner("搜尋 FundClear 基金清單…"):
                    st.session_state["navbf_cands"] = find_fund_candidates(
                        _search_name.strip(), (_org.strip() or None))
                if not st.session_state["navbf_cands"]:
                    st.warning("查無相似基金 —— 可能非 FundClear 境外基金,或需指定機構代碼。")
            except Exception as _e:  # noqa: BLE001
                _friendly("搜尋 FundClear 失敗(部署環境才連得到;機構清單報錯請填機構代碼或按下方掃描)",
                          _e, level="error")

        if st.button("🔍 掃描全部機構找我的基金(機構清單抓不到時用;較慢 ~1-2 分)",
                     key="navbf_scan", disabled=not _search_name.strip()):
            try:
                from services.fundclear_backfill import find_fund_candidates
                with st.spinner("逐一掃描機構 001-060(~1-2 分,跑完前別關頁面)…"):
                    st.session_state["navbf_cands"] = find_fund_candidates(
                        _search_name.strip(), organize_code=None, scan_range=60)
                if not st.session_state["navbf_cands"]:
                    st.warning("掃描完仍查無 —— 可能非 FundClear 境外基金,或機構代碼超出 001-060 範圍。")
            except Exception as _e:  # noqa: BLE001
                _friendly("掃描失敗", _e, level="error")

        _cands = st.session_state.get("navbf_cands") or []
        if _cands:
            _opts = {f"{c['name']}（{c.get('organize_name') or c['organize_code']}/{c['value']}）"
                     f" · {c['score']:.0%}": c for c in _cands}
            _pick = _opts.get(st.selectbox("選對應基金(**核對名稱**)", list(_opts), key="navbf_pick"))
            if _pick and st.button("取級別清單", key="navbf_classes_btn"):
                try:
                    from services.fundclear_backfill import list_classes_for
                    st.session_state["navbf_classes"] = list_classes_for(
                        _pick["organize_code"], _pick["value"])
                    st.session_state["navbf_pick_fund"] = _pick
                except Exception as _e:  # noqa: BLE001
                    _friendly("取級別清單失敗", _e, level="error")

        _classes = st.session_state.get("navbf_classes") or []
        _pick_fund = st.session_state.get("navbf_pick_fund")
        if _classes and _pick_fund:
            _copts = {f"{c['name']}（{c['value']}）": c for c in _classes}
            _cpick = _copts.get(st.selectbox(
                "選級別 —— **選你實際持有的那個**(幣別 + 累積/配息 都要一致,否則併入會跳空失真)",
                list(_copts), key="navbf_class_pick"))
            if _fixed_code:
                _app_code = _fixed_code                            # 自動帶自持倉 → 健診一定讀得回
                st.caption(f"存進內部碼:**{_app_code}**(自動帶自你的持倉,免打錯)")
            else:
                _app_code = st.text_input(
                    "存進 nav_history 的**持倉內部碼**(健診以此讀回;例 ACTI71)", key="navbf_appcode")
            # ── 稽核 E6（2026-08-14）：寫入前必須先預覽 ────────────────────────
            # 原本這裡是**一顆按鈕直接寫**:抓數千筆 → 直接進 Google Sheet 的
            # nav_history 分頁,零預覽、零確認、無 dry-run、無 rollback。
            # 而那個分頁在說明書上標「🚨 絕對不要刪…無法從任何來源重建」。
            #
            # 真正致命的是去重鍵只有 `(code, date)`:同一檔基金常有多個級別
            # (美元累積 / 美元配息 / 歐元避險…),淨值完全不同。選錯級別寫進去後,
            # **正確級別的淨值會被當成重複而永遠寫不進來**,而錯的那份會被健診
            # 拿去算 1Y 報酬、Sharpe、σ —— 使用者不會收到任何警告。
            #
            # 改成兩段:① 預覽(只抓不寫 + 比對既有資料)→ ② 看過再確認寫入。
            _bf_key = f"{_pick_fund['value']}|{_cpick['value']}|{_app_code.strip()}"
            if _cpick and st.button("① 🔍 預覽（只抓不寫）", key="navbf_preview",
                                    disabled=not _app_code.strip(),
                                    use_container_width=True):
                try:
                    from services.fundclear_backfill import download_and_store
                    with st.spinner("抓完整歷史(可能數十秒)…尚未寫入任何資料"):
                        _prev = download_and_store(
                            _pick_fund["organize_code"], _pick_fund["value"],
                            _cpick["value"], _app_code.strip(),
                            fund_name=_pick_fund["name"], dry_run=True)
                    st.session_state["navbf_preview"] = {"key": _bf_key, "res": _prev}
                except Exception as _e:  # noqa: BLE001
                    _friendly("預覽失敗", _e, level="error")

            _pv = st.session_state.get("navbf_preview") or {}
            # 選項改過 → 舊預覽作廢(否則會拿 A 級別的預覽去確認 B 級別的寫入)
            if _pv and _pv.get("key") == _bf_key:
                _res = _pv["res"]
                if not _res.get("ok"):
                    st.error(f"抓取失敗:{_res.get('reason')}")
                else:
                    _s0, _s1 = _res["span"]
                    _cf = _res.get("conflict") or {}
                    _v = _cf.get("verdict")
                    st.info(
                        f"**預覽結果（尚未寫入）**：{_app_code.strip()} 抓到 "
                        f"**{_res['count']} 筆**，{_s0} ~ {_s1}，計價幣別 "
                        f"**{_res['currency']}**。\n\n"
                        f"這一檔目前已累積 {_cf.get('n_existing', 0)} 筆；"
                        f"其中 {_cf.get('n_overlap', 0)} 天與這次抓到的重疊。"
                    )
                    if _v == "conflict":
                        _rows = "\n".join(
                            f"- {s['date']}：已存 **{s['existing']:.4f}** vs "
                            f"這次 **{s['incoming']:.4f}**（差 {s['diff_pct']:+.1f}%）"
                            for s in (_cf.get("samples") or []))
                        st.error(
                            f"⛔ **偵測到 {_cf['n_conflict']} 天的淨值對不上 —— "
                            "極可能選錯級別，已擋下不寫入。**\n\n"
                            f"{_rows}\n\n"
                            "同一檔基金常有好幾個級別（美元累積 / 美元配息 / 歐元避險…），"
                            "淨值完全不同。**請回上一步核對幣別與配息/累積型是否與你實際持有的一致。**\n\n"
                            "⚠️ 為什麼一定要擋：這個分頁的去重只看「代碼 + 日期」，"
                            "**錯的資料寫進去之後，正確的就永遠寫不進來了**，"
                            "而健診會拿錯的去算報酬率。"
                        )
                    elif _v == "duplicate":
                        st.warning(
                            "ℹ️ 這段歷史**已經在裡面了**（重疊日的淨值完全一致）。"
                            "按下面的確認鈕不會有任何改變，也不會弄壞什麼。")
                    elif _v == "unknown":
                        st.warning(
                            "⚠️ **讀不到既有資料，無法確認會不會撞到既有紀錄。**"
                            "多半是 Google Sheet 還沒設定好。"
                            "在確認之前建議先到「📖 參考 / 診斷」看一下累積狀態燈。")
                    else:
                        st.success("✅ 沒有與既有資料重疊，這是純新增，安全。")

                    if _v != "conflict":
                        st.caption("確認前請再看一眼上面的**計價幣別**與**起訖日期**是否合理。")
                        if st.button("② ✍️ 確認寫入 Google Sheet", key="navbf_commit",
                                     type="primary", use_container_width=True):
                            try:
                                from services.fundclear_backfill import download_and_store
                                with st.spinner("寫入 Google Sheet…"):
                                    _w = download_and_store(
                                        _pick_fund["organize_code"], _pick_fund["value"],
                                        _cpick["value"], _app_code.strip(),
                                        fund_name=_pick_fund["name"])
                                if not _w.get("ok"):
                                    st.error(f"已擋下未寫入:{_w.get('reason')}")
                                else:
                                    st.success(
                                        f"✅ {_app_code.strip()}:寫入 {_w['written']} 筆"
                                        f"(重複略過 {_w['skipped']})。"
                                        "重整健診 / 個基體檢就會用這段歷史算真實 1Y,不再外推誤判。")
                                    st.session_state.pop("navbf_preview", None)
                            except Exception as _e:  # noqa: BLE001
                                _friendly("寫入失敗", _e, level="error")


def render_manage_tab() -> None:
    from ui.helpers.story_nav import render_flow_nav, tab_label as _tab_label_tm
    st.markdown(f"## {_tab_label_tm('manage')}")
    render_flow_nav("manage")   # 巨觀:第 ③ 層（選股池 = 流程圖的「觀察池 Watchlist」）
    st.caption("你的基金資料**一站集中在這一頁**。資料存在 Google Sheets、永久保存,關掉重開都在。")
    st.info(
        "**這一頁由上到下有 6 塊**,先看前兩塊就好:\n\n"
        "1. 💼 **投資組合(持倉)** — 你**已經買、目前真正持有**的基金 ← 這才是「你的組合」。\n"
        "2. 📁 **選股池(候選基金)** — 你**還沒買、考慮想換進來**的備選名單(不是持倉)。\n"
        "3. 📊 **保單組合分析** — 上傳保單總表做分析(只顯示,不寫回 Sheet)。\n"
        "4. 🗓️ **除息行事曆** — 你持有基金的配息日曆。\n"
        "5. 📥 **補歷史淨值** — 幫抓不到淨值的基金補歷史(根治吃本金誤判)。\n"
        "6. 🔔 **換股通報** — 設定 LINE 每週提醒。"
    )
    _sec_portfolio()          # ★ v19.452:持倉最重要 → 放最前
    st.divider()
    _sec_pool()
    st.divider()
    _sec_policy_portfolio()
    st.divider()
    _sec_dividend_calendar()
    st.divider()
    _sec_nav_backfill()
    st.divider()
    _sec_notify()
