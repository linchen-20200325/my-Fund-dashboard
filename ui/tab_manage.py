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
    _fund_rows = _df[_df["item_type"].astype(str).str.strip().isin(["", "fund"])]
    if _fund_rows.empty and _df.empty:
        st.info("這本 Sheet 目前沒有任何持倉。可到 Tab④ 新增保單/基金。")
        return
    _codes = sorted({str(c).strip() for c in _fund_rows["fund_code"] if str(c).strip()})
    st.success(f"共 {len(_codes)} 檔基金 · {_df['policy_id'].nunique()} 張保單。")

    # 只開放「安全欄」編輯;其餘欄(平均成本 avg_nav / 份額 units / 含息成本…)**照原樣帶著、
    # 不清空**(§1 防資料流失:write_policy_v2 是整張覆寫,若只寫 5 欄會抹掉平均成本 + 現金列)。
    # 現金列(item_type=cash)也一併顯示 + 保留。
    # 只開放這 6 欄編輯(對齊下方 caption);item_type / amount / 平均成本 等唯讀,避免誤打
    # 把 fund 打成別的字 → write_policy_v2 兩邊都不認 → 整列數字被清空(稽核 FINDING 2)。
    _editable = {"fund_code", "fund_name", "tier", "currency", "invest_twd", "div_cash_pct"}
    _labels = {
        "item_type": "類型", "fund_code": "基金代號", "fund_name": "名稱", "currency": "幣別",
        "tier": "級別", "invest_twd": "投入金額(TWD)", "div_cash_pct": "現金給付%", "amount": "現金金額",
        "units": "份額(自動)", "avg_nav": "平均成本", "avg_nav_with_div": "含息成本", "avg_fx": "平均匯率",
        "policy_id": "保單",
    }
    for _pid in sorted({str(p) for p in _df["policy_id"] if str(p).strip()}):
        _pdf = _df[_df["policy_id"].astype(str) == _pid]                 # 全列(基金 + 現金),不只 5 欄
        with st.expander(f"📄 保單 {_pid}（{len(_pdf)} 列）", expanded=(_df['policy_id'].nunique() == 1)):
            st.caption("可改:基金代號 / 名稱 / 幣別 / 級別 / 投入金額 / 現金給付%。刪列=移除該檔。"
                       "平均成本、份額等**灰色欄照原樣保留**(存檔不會清掉)。")
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
    """編輯後的 grid → 準備給 write_policy_v2 的 df:補 policy_id;新增列(有代號但無類型)補 item_type=fund。

    §1 防資料流失:**保留每列原本的 item_type**(現金列不被改成 fund)、**保留所有唯讀欄**
    (平均成本 avg_nav / 份額 units / …,編輯器裡帶著)。只有使用者新增、item_type 留空又填了代號的列
    才預設為 fund。純函式(不碰 st / 網路),供單元測試鎖住此回寫前處理(§6)。
    """
    _out = edited_df.copy()
    _out["policy_id"] = policy_id
    if "item_type" in _out.columns and "fund_code" in _out.columns:
        _blank_type = _out["item_type"].astype(str).str.strip() == ""
        _has_code = _out["fund_code"].astype(str).str.strip() != ""
        _out.loc[_blank_type & _has_code, "item_type"] = "fund"        # 新增基金列補類型
    return _out


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
