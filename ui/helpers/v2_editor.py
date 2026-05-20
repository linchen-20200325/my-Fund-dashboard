"""ui/helpers/v2_editor.py — v18.149 Schema v2 native UI（PR B）

提供 user 跟 v2 schema（每張保單一個 worksheet、11 欄）互動的編輯介面：
- `render_v2_section(client, sheet_id)`：主入口（從 tab3 expander 呼叫）
- `render_first_use_wizard(...)`：empty sheet 時的 4-step 引導
- 每張保單一個區塊，內含 fund / cash 兩個 `st.data_editor` + [💾 存到雲端] 按鈕

設計原則（與 CLAUDE.md §2 一致）：
- 純 UI 層；CRUD I/O 委由 `repositories.policy_repository` 的 v2 API
- 本機編輯狀態存在 `st.session_state["_v2_buf"][policy_id]` 內，按存檔才推雲端
- 失敗訊息 in-place（`st.error`），不在這一層丟例外
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from repositories.policy_repository import (
    ALL_COLS_V2,
    ITEM_TYPE_CASH,
    ITEM_TYPE_FUND,
    PolicySheetError,
    _sanitize_tab_name,
    compute_units,
    delete_policy_worksheet,
    ensure_policy_worksheet,
    list_policy_worksheets,
    load_all_policies_v2,
    load_policy_v2,
    write_policy_v2,
)


# ════════════════════════════════════════════════════════════
# session_state key 助記
# ════════════════════════════════════════════════════════════
_KEY_V2_BUF = "_v2_buf"           # dict[policy_id, {"fund": df, "cash": df, "dirty": bool}]
_KEY_V2_LOADED = "_v2_loaded_sid"  # 已從這個 sheet_id 讀過資料


def _ensure_buf() -> dict:
    if _KEY_V2_BUF not in st.session_state:
        st.session_state[_KEY_V2_BUF] = {}
    return st.session_state[_KEY_V2_BUF]


def _empty_fund_df() -> pd.DataFrame:
    # v18.153：fund 表 9 欄（含 avg_nav_with_div 含息成本）
    return pd.DataFrame(columns=[
        "fund_code", "fund_name", "units", "avg_nav", "avg_nav_with_div",
        "avg_fx", "currency", "tier", "invest_twd",
    ])


def _empty_cash_df() -> pd.DataFrame:
    return pd.DataFrame(columns=["currency", "amount"])


def _split_policy_df(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """12 欄 df → (fund 9 欄, cash 2 欄) for st.data_editor 分區顯示。"""
    fund_cols = ["fund_code", "fund_name", "units", "avg_nav", "avg_nav_with_div",
                 "avg_fx", "currency", "tier", "invest_twd"]
    cash_cols = ["currency", "amount"]
    fund_df = df[df["item_type"] == ITEM_TYPE_FUND][fund_cols].reset_index(drop=True) \
              if not df.empty else _empty_fund_df()
    cash_df = df[df["item_type"] == ITEM_TYPE_CASH][cash_cols].reset_index(drop=True) \
              if not df.empty else _empty_cash_df()
    return fund_df, cash_df


def _merge_policy_df(policy_id: str, fund_df: pd.DataFrame, cash_df: pd.DataFrame) -> pd.DataFrame:
    """(fund_df, cash_df) → 11 欄合併 df（給 write_policy_v2 用）。"""
    rows: list[dict] = []
    for _, r in fund_df.iterrows():
        code = str(r.get("fund_code", "") or "").strip()
        if not code:
            continue
        # v18.153：units 公式自動算（user 直接看到結果，存進去給 T7 用）
        _inv = float(r.get("invest_twd", 0) or 0)
        _nav = float(r.get("avg_nav", 0) or 0)
        _fx  = float(r.get("avg_fx", 0) or 0)
        rows.append({
            "policy_id":        policy_id,
            "item_type":        ITEM_TYPE_FUND,
            "fund_code":        code,
            "fund_name":        str(r.get("fund_name", "") or ""),
            "units":            compute_units(_inv, _nav, _fx),
            "avg_nav":          _nav,
            "avg_nav_with_div": float(r.get("avg_nav_with_div", 0) or 0),
            "avg_fx":           _fx,
            "currency":         str(r.get("currency", "") or "USD"),
            "tier":             str(r.get("tier", "") or ""),
            "amount":           "",
            "invest_twd":       _inv,
        })
    for _, r in cash_df.iterrows():
        ccy = str(r.get("currency", "") or "").strip()
        amt = r.get("amount", 0) or 0
        if not ccy or float(amt) == 0:
            continue
        rows.append({
            "policy_id":        policy_id,
            "item_type":        ITEM_TYPE_CASH,
            "fund_code":        "",
            "fund_name":        "",
            "units":            "",
            "avg_nav":          "",
            "avg_nav_with_div": "",
            "avg_fx":           "",
            "currency":         ccy,
            "tier":             "",
            "amount":           amt,
            "invest_twd":       "",
        })
    return pd.DataFrame(rows, columns=list(ALL_COLS_V2))


def _is_quota_msg(e: Exception) -> bool:
    """v18.152: 偵測 Google Sheets 429 quota，給 friendly UI 訊息用。"""
    m = str(e)
    return ("429" in m or "Quota exceeded" in m
            or "RATE_LIMIT" in m or "RESOURCE_EXHAUSTED" in m)


def _show_quota_friendly(prefix: str, e: Exception) -> None:
    """v18.152: 把 raw API 例外換成中文友善訊息。"""
    if _is_quota_msg(e):
        st.warning(
            f"⏳ {prefix}：Google Sheets API 配額暫時超載"
            "（每 user 每分鐘 60 reads 上限）。"
            "請等 30-60 秒再點頁面任何按鈕重整（已內建退避重試，仍可能需要稍候）。"
        )
    else:
        st.error(f"❌ {prefix}：{e}")


# v18.152：Streamlit cache wrapper — 同一 (sheet_id, policy_id) 60 秒內只打一次 API
# 避免 Tab3 反覆 rerun（任何 button 點擊）都重新 list+load 整個帳本爆 quota。
@st.cache_data(ttl=60, show_spinner=False)
def _cached_load_policy_v2(_client: Any, sheet_id: str, policy_id: str):
    """`_client` 前綴底線 → Streamlit 不對 client object 計 hash。"""
    return load_policy_v2(_client, sheet_id, policy_id)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_list_policies(_client: Any, sheet_id: str):
    from repositories.policy_repository import list_policy_worksheets as _lpw
    return _lpw(_client, sheet_id)


def _invalidate_cache(sheet_id: str, policy_id: str | None = None) -> None:
    """寫入後 / user 主動 reload 時清快取。policy_id None → 清整本。"""
    _cached_list_policies.clear()
    _cached_load_policy_v2.clear()


def _load_policy_into_buf(client: Any, sheet_id: str, policy_id: str) -> None:
    """從雲端讀單張保單 v2 資料進 buf；走 60s cache 避免 429。"""
    buf = _ensure_buf()
    try:
        df = _cached_load_policy_v2(client, sheet_id, policy_id)
    except PolicySheetError as e:
        _show_quota_friendly(f"讀「{policy_id}」失敗", e)
        return
    fund_df, cash_df = _split_policy_df(df)
    buf[policy_id] = {"fund": fund_df, "cash": cash_df, "dirty": False}


# ════════════════════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════════════════════
def render_v2_section(client: Any, sheet_id: str) -> None:
    """v2 native UI 主入口 — 從 tab3 expander 內呼叫。

    呼叫條件：caller 已確認 `detect_sheet_schema_version(...)` == "v2"。
    """
    st.markdown("---")
    st.markdown("##### ✨ v2 編輯介面（保單與基金）")
    st.caption(
        "每張保單一個分頁；可加 fund 列與多幣別現金列。"
        "編輯後按各保單區塊的 **[💾 存到雲端]** 推上 Google Sheets。"
        "T7 模擬器**不會寫回**，真實加碼/贖回請在此編輯或直接改 Sheet。"
    )

    # 列保單（v18.152：走 60s cache）
    try:
        policy_ids = _cached_list_policies(client, sheet_id)
    except PolicySheetError as e:
        _show_quota_friendly("列保單分頁失敗", e)
        if st.button("🔄 重試（清快取）", key="btn_retry_list_v2"):
            _invalidate_cache(sheet_id)
            st.rerun()
        return

    # session_state buf：新 sheet 或還沒讀過 → 全部 lazy load
    if st.session_state.get(_KEY_V2_LOADED) != sheet_id:
        for pid in policy_ids:
            _load_policy_into_buf(client, sheet_id, pid)
        st.session_state[_KEY_V2_LOADED] = sheet_id

    # Empty Sheet / 沒有保單 → 顯示 wizard 入口
    if not policy_ids:
        st.info("ℹ️ 這本帳本還沒有任何保單。")
        if st.button("🚀 第一次使用 — 引導建立第一張保單",
                      key="btn_v2_first_use", type="primary",
                      use_container_width=True):
            st.session_state["_v2_show_wizard"] = True
            st.rerun()
        if st.session_state.get("_v2_show_wizard"):
            render_first_use_wizard(client, sheet_id)
        return

    # 既有保單列表
    buf = _ensure_buf()
    for pid in policy_ids:
        _render_policy_block(client, sheet_id, pid, buf.get(pid, {}))

    # 新增保單區
    st.markdown("---")
    _render_new_policy_section(client, sheet_id)


# ════════════════════════════════════════════════════════════
# 單張保單區塊
# ════════════════════════════════════════════════════════════
def _render_policy_block(client: Any, sheet_id: str, policy_id: str, buf_one: dict) -> None:
    fund_df = buf_one.get("fund", _empty_fund_df())
    cash_df = buf_one.get("cash", _empty_cash_df())
    dirty = buf_one.get("dirty", False)

    _title = f"📋 保單「{policy_id}」"
    if dirty:
        _title += "  🔸 未存檔"
    with st.expander(_title, expanded=False):
        # v18.153：色彩說明 + auto 欄位視覺區隔
        st.caption(
            "🟨 黃底：自己填（保單對帳單抄）　·　"
            "⬜ 灰底：自動帶（MoneyDJ / 公式算）"
        )
        # fund 編輯 — 12 欄裡的 9 欄；auto cols 標 disabled、user cols 可編
        st.markdown("**💼 基金持有**")
        # 在送 data_editor 前 inject units 計算結果（read-only 顯示）
        if not fund_df.empty:
            fund_df = fund_df.copy()
            fund_df["units"] = fund_df.apply(
                lambda r: compute_units(r.get("invest_twd", 0) or 0,
                                          r.get("avg_nav", 0) or 0,
                                          r.get("avg_fx", 0) or 0), axis=1)
        edited_fund = st.data_editor(
            fund_df,
            num_rows="dynamic",
            use_container_width=True,
            key=f"de_fund_{policy_id}",
            column_config={
                # USER-input (yellow)
                "fund_code":        st.column_config.TextColumn(
                                        "🟨 基金代號", required=True,
                                        help="到 MoneyDJ 抓 NAV 的代號"),
                "avg_nav":          st.column_config.NumberColumn(
                                        "🟨 平均買入單位成本", format="%.4f",
                                        help="對帳單欄(1)"),
                "avg_nav_with_div": st.column_config.NumberColumn(
                                        "🟨 平均買入含息單位成本", format="%.4f",
                                        help="對帳單欄(10) — 含息報酬率計算用，沒有填 0"),
                "avg_fx":           st.column_config.NumberColumn(
                                        "🟨 平均買入匯率", format="%.4f",
                                        help="對帳單欄(3)"),
                "invest_twd":       st.column_config.NumberColumn(
                                        "🟨 淨投資金額 (TWD)", format="%d",
                                        help="對帳單欄(4) = 平均單位成本 × 單位數 × 平均匯率"),
                # AUTO (grey, disabled)
                "fund_name":        st.column_config.TextColumn(
                                        "⬜ 基金名稱（自動）", disabled=True,
                                        help="存檔時用 fund_code 從 MoneyDJ 帶入"),
                "units":            st.column_config.NumberColumn(
                                        "⬜ 持有單位數（自動算）", format="%.4f",
                                        disabled=True,
                                        help="= 淨投資金額 / (平均單位成本 × 平均匯率)"),
                "currency":         st.column_config.TextColumn(
                                        "⬜ 幣別（自動）", disabled=True,
                                        help="存檔時從 MoneyDJ 帶入"),
                "tier":             st.column_config.SelectboxColumn(
                                        "級別", options=["", "core", "satellite"],
                                        help="存檔時自動判斷，可手動修正"),
            },
        )

        # cash 編輯
        st.markdown("**💵 現金部位（多幣別）**")
        edited_cash = st.data_editor(
            cash_df,
            num_rows="dynamic",
            use_container_width=True,
            key=f"de_cash_{policy_id}",
            column_config={
                "currency": st.column_config.SelectboxColumn(
                                "幣別", options=["TWD", "USD", "EUR", "GBP", "JPY", "AUD"],
                                required=True),
                "amount":   st.column_config.NumberColumn("金額", format="%.2f"),
            },
        )

        # diff 偵測 → 標記 dirty
        if not edited_fund.equals(fund_df) or not edited_cash.equals(cash_df):
            buf = _ensure_buf()
            buf.setdefault(policy_id, {})
            buf[policy_id]["fund"] = edited_fund.copy()
            buf[policy_id]["cash"] = edited_cash.copy()
            buf[policy_id]["dirty"] = True

        # 動作按鈕列
        _bc1, _bc2, _bc3, _bc4 = st.columns([2, 2, 1, 1])
        if _bc1.button(f"💾 存到雲端", key=f"btn_save_{policy_id}",
                        type="primary", use_container_width=True):
            try:
                # v18.153：存檔前對 fund_name/currency/tier 空的列 → MoneyDJ 自動帶
                fund_df_v2 = edited_fund.copy() if not edited_fund.empty else edited_fund
                if not fund_df_v2.empty:
                    for _i, _r in fund_df_v2.iterrows():
                        _fc = str(_r.get("fund_code", "") or "").strip()
                        if not _fc:
                            continue
                        _need_fname = not str(_r.get("fund_name", "") or "").strip()
                        _need_ccy = not str(_r.get("currency", "") or "").strip()
                        _need_tier = not str(_r.get("tier", "") or "").strip()
                        if _need_fname or _need_ccy or _need_tier:
                            _afn, _accy, _atier = _autofill_from_moneydj(_fc)
                            if _need_fname and _afn:
                                fund_df_v2.at[_i, "fund_name"] = _afn
                            if _need_ccy and _accy:
                                fund_df_v2.at[_i, "currency"] = _accy
                            if _need_tier and _atier:
                                fund_df_v2.at[_i, "tier"] = _atier
                merged = _merge_policy_df(policy_id, fund_df_v2, edited_cash)
                n = write_policy_v2(client, sheet_id, policy_id, merged)
                buf = _ensure_buf()
                buf.setdefault(policy_id, {})["dirty"] = False
                st.success(f"✅ 已存 {n} 列到雲端（自動帶 MoneyDJ 缺漏）")
                # v18.152：寫入後清 cache，重讀拿雲端最新
                _invalidate_cache(sheet_id, policy_id)
                _load_policy_into_buf(client, sheet_id, policy_id)
                st.rerun()
            except PolicySheetError as e:
                _show_quota_friendly("存檔失敗", e)

        if _bc2.button(f"📥 重新讀回", key=f"btn_reload_{policy_id}",
                        use_container_width=True,
                        help="丟棄本地未存的改動，從雲端讀最新"):
            _invalidate_cache(sheet_id, policy_id)
            _load_policy_into_buf(client, sheet_id, policy_id)
            st.rerun()

        if _bc3.button(f"🗑️", key=f"btn_del_{policy_id}",
                        use_container_width=True,
                        help="刪除整張保單分頁（不可復原）"):
            st.session_state[f"_confirm_del_{policy_id}"] = True

        if st.session_state.get(f"_confirm_del_{policy_id}"):
            st.warning(f"⚠️ 確定要刪除保單「{policy_id}」整個分頁？")
            _dc1, _dc2 = st.columns(2)
            if _dc1.button("✅ 確定刪除", key=f"btn_del_yes_{policy_id}",
                            use_container_width=True):
                try:
                    delete_policy_worksheet(client, sheet_id, policy_id)
                    buf = _ensure_buf()
                    buf.pop(policy_id, None)
                    _invalidate_cache(sheet_id)
                    st.session_state.pop(f"_confirm_del_{policy_id}", None)
                    st.success(f"✅ 已刪除「{policy_id}」")
                    st.rerun()
                except PolicySheetError as e:
                    _show_quota_friendly("刪除失敗", e)
            if _dc2.button("取消", key=f"btn_del_no_{policy_id}",
                            use_container_width=True):
                st.session_state.pop(f"_confirm_del_{policy_id}", None)
                st.rerun()


# ════════════════════════════════════════════════════════════
# 新增保單
# ════════════════════════════════════════════════════════════
def _render_new_policy_section(client: Any, sheet_id: str) -> None:
    st.markdown("##### ➕ 新增保單")
    _nc1, _nc2 = st.columns([3, 2])
    new_pid = _nc1.text_input(
        "新保單名稱（會變成 Sheet 的 worksheet tab 名）",
        key="v2_new_policy_name",
        placeholder="例：富邦人壽-001 / 國泰-USD / 退休帳戶",
    ).strip()
    _nc2.write("")
    _nc2.write("")
    if _nc2.button("🆕 建立保單分頁", key="btn_v2_new_policy",
                    type="primary", use_container_width=True,
                    disabled=not new_pid):
        try:
            sanitized = _sanitize_tab_name(new_pid)
            ensure_policy_worksheet(client, sheet_id, sanitized)
            # 寫一個 v2 header（讓 detect_sheet_schema_version 一致回 v2）
            empty_df = pd.DataFrame(columns=list(ALL_COLS_V2))
            write_policy_v2(client, sheet_id, sanitized, empty_df)
            st.success(f"✅ 已建立保單「{sanitized}」")
            _invalidate_cache(sheet_id)
            _load_policy_into_buf(client, sheet_id, sanitized)
            # 清掉 input
            st.session_state.pop("v2_new_policy_name", None)
            st.rerun()
        except PolicySheetError as e:
            _show_quota_friendly("建立失敗", e)


# ════════════════════════════════════════════════════════════
# 第一次使用 wizard（empty sheet 引導）
# ════════════════════════════════════════════════════════════
def render_first_use_wizard(client: Any, sheet_id: str) -> None:
    """4-step wizard：建保單名 → 加第一檔基金 → 加現金（可跳過）→ 存檔"""
    st.markdown("---")
    st.markdown("#### 🪜 第一次使用嚮導")
    st.caption("跟著 3 步走，建立你的第一張保單與第一檔基金（之後直接編輯即可）。")

    # Step 1：保單名
    # v18.153：wizard 只露 user-input 欄位
    # 自動帶：fund_name、currency（MoneyDJ）｜ units（公式算）｜ tier（_is_core_fund）
    st.markdown("**Step 1 / 3：保單名稱**")
    pid = st.text_input("🟨 保單名稱", key="wiz_pid",
                          placeholder="例：富邦人壽-001").strip()

    st.markdown("**Step 2 / 3：第一檔基金（保險公司對帳單抄上來）**")
    _f1 = st.columns(1)[0]
    fcode = _f1.text_input("🟨 基金代號", key="wiz_fcode",
                              placeholder="例：FIDXEQI.LX",
                              help="到 MoneyDJ 抓 NAV 的代號；存檔時自動帶基金名稱/幣別").strip()
    _f3, _f4 = st.columns(2)
    avg_nav = _f3.number_input("🟨 平均買入單位成本（對帳單欄(1)）", key="wiz_avg_nav",
                                min_value=0.0, step=0.001, format="%.4f")
    # v18.157：對帳單兩種格式 — type A 有「平均買入含息單位成本」；
    # type B 沒這欄，但有「累積現金配息金額 (NT)」可反推。
    _div_mode = _f4.radio(
        "📋 對帳單欄位（含息成本來源）",
        ["A. 有「平均買入含息單位成本」", "B. 只有「累積現金配息金額 (NT)」"],
        key="wiz_div_mode", horizontal=False,
        help="A：直接抄欄(10)；B：用配息金額反推（公式：avg_nav − 累積配息NT / (avg_fx × units)）"
    )
    if _div_mode.startswith("A"):
        avg_nav_w_input = _f4.number_input(
            "🟨 平均買入含息單位成本（欄(10)，沒有填 0）",
            key="wiz_avg_nav_div",
            min_value=0.0, step=0.001, format="%.4f")
        cumul_div_input = 0.0
    else:
        avg_nav_w_input = 0.0
        cumul_div_input = _f4.number_input(
            "🟨 累積現金配息金額 (NT) — 對帳單抄",
            key="wiz_cumul_div_twd",
            min_value=0.0, step=100.0, format="%.0f",
            help="存檔時自動換算成含息成本存進去")
    _f5, _f6 = st.columns(2)
    avg_fx = _f5.number_input("🟨 平均買入匯率（欄(3)）", key="wiz_avg_fx",
                                min_value=0.0, step=0.01, format="%.4f")
    inv_twd = _f6.number_input("🟨 淨投資金額 TWD（欄(4)）", key="wiz_inv_twd",
                                 min_value=0, step=1000, format="%d")

    # 即時算 units 預覽
    if avg_nav > 0 and avg_fx > 0 and inv_twd > 0:
        _u_preview = compute_units(inv_twd, avg_nav, avg_fx)
        st.info(f"🧮 自動算：持有單位數 ≈ **{_u_preview:.4f}**（= {inv_twd:,} / ({avg_nav:.4f} × {avg_fx:.4f}）")

    st.markdown("**Step 3 / 3：現金部位（沒有可跳過）**")
    _c1, _c2 = st.columns(2)
    cash_ccy = _c1.selectbox("🟨 現金幣別", ["（無）", "TWD", "USD", "EUR", "GBP"],
                              key="wiz_cash_ccy")
    cash_amt = _c2.number_input("🟨 現金金額", key="wiz_cash_amt",
                                  min_value=0.0, step=1000.0, format="%.2f")

    st.markdown("---")
    _ok1, _ok2 = st.columns([2, 3])
    if _ok1.button("✅ 建立並存檔", key="btn_wiz_finish",
                    type="primary", use_container_width=True,
                    disabled=not (pid and fcode and avg_nav > 0 and avg_fx > 0
                                   and inv_twd > 0)):
        try:
            sanitized = _sanitize_tab_name(pid)
            # 自動：MoneyDJ 抓 fund_name + currency；_is_core_fund 判 tier
            _fname, _ccy, _tier = _autofill_from_moneydj(fcode)
            _u_calc = compute_units(inv_twd, avg_nav, avg_fx)
            # v18.157：type B 對帳單 → 從累積配息反推 avg_nav_with_div
            if avg_nav_w_input > 0:
                _anwd_final = avg_nav_w_input
            elif cumul_div_input > 0 and _u_calc > 0:
                from repositories.policy_repository import avg_nav_with_div_from_cumul_div_twd
                _anwd_final = avg_nav_with_div_from_cumul_div_twd(
                    avg_nav, avg_fx, _u_calc, cumul_div_input)
            else:
                _anwd_final = 0.0
            rows = [{
                "policy_id":        sanitized,
                "item_type":        ITEM_TYPE_FUND,
                "fund_code":        fcode,
                "fund_name":        _fname,
                "units":            _u_calc,
                "avg_nav":          avg_nav,
                "avg_nav_with_div": _anwd_final,
                "avg_fx":           avg_fx,
                "currency":         _ccy or "USD",
                "tier":             _tier,
                "amount":           "",
                "invest_twd":       inv_twd,
            }]
            if cash_ccy != "（無）" and cash_amt > 0:
                rows.append({
                    "policy_id":        sanitized,
                    "item_type":        ITEM_TYPE_CASH,
                    "fund_code":        "",
                    "fund_name":        "",
                    "units":            "",
                    "avg_nav":          "",
                    "avg_nav_with_div": "",
                    "avg_fx":           "",
                    "currency":         cash_ccy,
                    "tier":             "",
                    "amount":           cash_amt,
                    "invest_twd":       "",
                })
            df = pd.DataFrame(rows, columns=list(ALL_COLS_V2))
            write_policy_v2(client, sheet_id, sanitized, df)
            st.success(
                f"✅ 已建立保單「{sanitized}」+ {len(rows)} 列資料"
                + (f"，自動帶入：{_fname} ({_ccy})" if _fname else "")
            )
            _invalidate_cache(sheet_id)
            st.session_state.pop("_v2_show_wizard", None)
            for k in ("wiz_pid", "wiz_fcode", "wiz_avg_nav", "wiz_avg_nav_div",
                      "wiz_avg_fx", "wiz_inv_twd", "wiz_cash_amt",
                      "wiz_cumul_div_twd", "wiz_div_mode"):
                st.session_state.pop(k, None)
            st.session_state.pop(_KEY_V2_LOADED, None)
            st.rerun()
        except PolicySheetError as e:
            _show_quota_friendly("建立失敗", e)

    if _ok2.button("取消（回主畫面）", key="btn_wiz_cancel",
                    use_container_width=True):
        st.session_state.pop("_v2_show_wizard", None)
        st.rerun()


def _autofill_from_moneydj(fund_code: str) -> tuple[str, str, str]:
    """v18.153：從 MoneyDJ 抓 fund_name / currency；用 _is_core_fund 判 tier。

    抓失敗 → 回 ("", "", "")，caller 再 fallback default。
    """
    fname, ccy, tier = "", "", ""
    if not fund_code:
        return fname, ccy, tier
    try:
        from fund_fetcher import fetch_fund_from_moneydj_url
        raw = fetch_fund_from_moneydj_url(fund_code)
        fname = raw.get("fund_name", "") or ""
        ccy = raw.get("currency", "") or raw.get("metrics", {}).get("currency", "")
    except Exception:
        pass   # noqa: smoke-allow-pass — MoneyDJ 抓失敗，user 之後可手動補
    if fname:
        try:
            from ui.helpers.session import is_core_fund
            tier = "core" if is_core_fund(fname) else "satellite"
        except Exception:
            pass   # noqa: smoke-allow-pass
    return fname, ccy, tier
