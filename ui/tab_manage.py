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
    st.caption("你的候選基金清單,供換股顧問配對。加/刪/改**即時存到 Google Sheets**(`_fund_pool` 分頁),"
               "永久保存、跨裝置,關掉重開都在。")

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
    st.caption("你的保單持倉,和 Tab④ 保單管理**同一本 Google Sheet**。這裡可**一覽 + 編輯金額/級別 + 刪除**,"
               "存檔即寫回雲端、永久保存。")

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

    # v19.436:一鍵修正基金名稱(被灌成保單號)+ 精簡 Sheet 到 10 欄。用代號從 MoneyDJ 重抓真名,
    # 整張重寫時舊 13 欄的 item_type/含息成本/金額 自然消失(物理精簡)。
    with st.expander("🔧 一鍵修正基金名稱 + 精簡 Sheet（10 欄）", expanded=False):
        st.caption("若你的基金名稱欄顯示的是保單號(不是基金真名),按這裡:用基金代號到 MoneyDJ "
                   "重抓正確名稱,並把每張分頁精簡成 10 欄(移除沒在用的類型/含息成本/現金金額)。"
                   "會逐張重寫雲端、需數十秒;僅補空/修錯,不動你填的金額與級別。")
        if st.button("🔧 開始修正 + 精簡", key="manage_pf_fixnames", use_container_width=True):
            _run_fix_and_shrink(_client, _sid)

    # 只開放「安全欄」編輯;units/avg_nav/avg_fx(持倉模擬選填)**照原樣帶著、不清空**
    # (§1 防資料流失:write_policy_v2 是整張覆寫,若只寫核心欄會抹掉平均成本)。
    _editable = {"fund_code", "fund_name", "tier", "currency", "invest_twd", "div_cash_pct"}
    _labels = {
        "policy_id": "保單", "fund_code": "基金代號", "fund_name": "名稱", "currency": "幣別",
        "tier": "級別", "invest_twd": "投入金額(TWD)", "div_cash_pct": "現金給付%",
        "units": "份額(選填)", "avg_nav": "平均成本(選填)", "avg_fx": "平均匯率(選填)",
    }
    for _pid in sorted({str(p) for p in _df["policy_id"] if str(p).strip()}):
        _pdf = _df[_df["policy_id"].astype(str) == _pid]                 # 該保單全部基金列
        with st.expander(f"📄 保單 {_pid}（{len(_pdf)} 列）", expanded=(_df['policy_id'].nunique() == 1)):
            st.caption("可改:基金代號 / 名稱 / 幣別 / 級別 / 投入金額 / 現金給付%。刪列=移除該檔。"
                       "平均成本、份額等**灰色選填欄照原樣保留**(存檔不會清掉)。")
            _cols = [c for c in ALL_COLS_V2 if c in _pdf.columns]
            _view = _pdf[_cols].reset_index(drop=True)
            _edited = st.data_editor(
                _view, num_rows="dynamic", use_container_width=True, hide_index=True,
                key=f"manage_pf_editor_{_pid}",
                disabled=[c for c in _cols if c not in _editable],       # 非安全欄唯讀(帶著不清空)
                column_config={c: _labels.get(c, c) for c in _cols},
            )
            c1, c2 = st.columns([2, 1])
            if c1.button("💾 存這張保單到雲端", key=f"manage_pf_save_{_pid}", use_container_width=True):
                _save_policy(_client, _sid, _pid, _edited)
            if c2.button("🗑️ 刪整張保單", key=f"manage_pf_del_{_pid}", use_container_width=True):
                _delete_policy(_client, _sid, _pid)


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
    st.success(f"✅ 完成:{_res['policies']} 張保單 · {_res['funds']} 檔基金 · "
               f"修正名稱 {_res['names_fixed']} 筆。已精簡成 10 欄。")
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
    from infra.config import get_secret
    _ok = bool(get_secret("LINE_CHANNEL_TOKEN")) and bool(get_secret("LINE_USER_ID"))
    st.caption(("🟢 LINE 憑證已設定" if _ok else
                "🔴 LINE 尚未設定(App secrets 缺 LINE_CHANNEL_TOKEN / LINE_USER_ID → 只能預覽,不能測試發送)")
               + "　·　⚠️ **每週自動推播是你 NAS 的排程在跑**,本頁只負責預覽 + 測試發送。")

    _funds = st.session_state.get("portfolio_funds") or []
    _loaded = [f for f in _funds if f.get("loaded")]

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
        _pbc = {e.code: e for e in pool}
        with st.spinner("計算本週通報預覽(和 NAS 週報同一套邏輯)…"):
            _held = _rows_with_nav(funds, _pbc)
            _cands = _pool_rows(pool, funds)
            _res = advise_switches(_held, _cands, fx_label=_fx_label(),
                                   macro_composite=_macro_composite(),
                                   underperformance_by_code=_underperf_by_code(funds))
            _note = build_notification(_res, as_of=_today_tw(),
                                       skipped=max(0, len(funds) - len(_held)))
        st.text_area("本週會送的訊息(預覽,不會真的送)", _note["message"], height=260)
        st.caption(f"該通知={_note['should_notify']}｜換股/表現差建議 {_note['n_actionable']} 檔。"
                   "（沒建議時 NAS 週報不會吵你;此處僅預覽。）")
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

def render_manage_tab() -> None:
    st.markdown("## 📋 我的管理室")
    st.caption("選股池、投資組合、通報 一站管理。**資料存在 Google Sheets、永久保存**,關掉重開都在,"
               "不用每次重輸入(只有即時報價那種本來會變的才會重抓)。")
    _sec_pool()
    st.divider()
    _sec_portfolio()
    st.divider()
    _sec_notify()
