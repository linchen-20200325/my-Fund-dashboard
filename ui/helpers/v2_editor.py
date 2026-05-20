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
    return pd.DataFrame(columns=[
        "fund_code", "fund_name", "units", "avg_nav", "avg_fx",
        "currency", "tier", "invest_twd",
    ])


def _empty_cash_df() -> pd.DataFrame:
    return pd.DataFrame(columns=["currency", "amount"])


def _split_policy_df(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """11 欄 df → (fund 8 欄, cash 2 欄) for st.data_editor 分區顯示。"""
    fund_cols = ["fund_code", "fund_name", "units", "avg_nav", "avg_fx",
                 "currency", "tier", "invest_twd"]
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
        rows.append({
            "policy_id":  policy_id,
            "item_type":  ITEM_TYPE_FUND,
            "fund_code":  code,
            "fund_name":  str(r.get("fund_name", "") or ""),
            "units":      r.get("units", 0) or 0,
            "avg_nav":    r.get("avg_nav", 0) or 0,
            "avg_fx":     r.get("avg_fx", 0) or 0,
            "currency":   str(r.get("currency", "") or "USD"),
            "tier":       str(r.get("tier", "") or ""),
            "amount":     "",
            "invest_twd": r.get("invest_twd", 0) or 0,
        })
    for _, r in cash_df.iterrows():
        ccy = str(r.get("currency", "") or "").strip()
        amt = r.get("amount", 0) or 0
        if not ccy or float(amt) == 0:
            continue
        rows.append({
            "policy_id":  policy_id,
            "item_type":  ITEM_TYPE_CASH,
            "fund_code":  "",
            "fund_name":  "",
            "units":      "",
            "avg_nav":    "",
            "avg_fx":     "",
            "currency":   ccy,
            "tier":       "",
            "amount":     amt,
            "invest_twd": "",
        })
    return pd.DataFrame(rows, columns=list(ALL_COLS_V2))


def _load_policy_into_buf(client: Any, sheet_id: str, policy_id: str) -> None:
    """從雲端讀單張保單 v2 資料進 buf。"""
    buf = _ensure_buf()
    try:
        df = load_policy_v2(client, sheet_id, policy_id)
    except PolicySheetError as e:
        st.error(f"❌ 讀「{policy_id}」失敗：{e}")
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

    # 列保單
    try:
        policy_ids = list_policy_worksheets(client, sheet_id)
    except PolicySheetError as e:
        st.error(f"❌ 列保單分頁失敗：{e}")
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
        # fund 編輯
        st.markdown("**💼 基金持有**")
        edited_fund = st.data_editor(
            fund_df,
            num_rows="dynamic",
            use_container_width=True,
            key=f"de_fund_{policy_id}",
            column_config={
                "fund_code":  st.column_config.TextColumn("代號", required=True),
                "fund_name":  st.column_config.TextColumn("名稱"),
                "units":      st.column_config.NumberColumn("單位數", format="%.4f"),
                "avg_nav":    st.column_config.NumberColumn("平均NAV", format="%.4f"),
                "avg_fx":     st.column_config.NumberColumn("平均FX", format="%.4f"),
                "currency":   st.column_config.SelectboxColumn(
                                  "幣別", options=["USD", "TWD", "EUR", "GBP", "JPY", "AUD"]),
                "tier":       st.column_config.SelectboxColumn(
                                  "級別", options=["", "core", "satellite"]),
                "invest_twd": st.column_config.NumberColumn("規劃 TWD", format="%d"),
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
                merged = _merge_policy_df(policy_id, edited_fund, edited_cash)
                n = write_policy_v2(client, sheet_id, policy_id, merged)
                buf = _ensure_buf()
                buf.setdefault(policy_id, {})["dirty"] = False
                st.success(f"✅ 已存 {n} 列到雲端")
                # 重讀以對齊雲端
                _load_policy_into_buf(client, sheet_id, policy_id)
                st.rerun()
            except PolicySheetError as e:
                st.error(f"❌ 存檔失敗：{e}")

        if _bc2.button(f"📥 重新讀回", key=f"btn_reload_{policy_id}",
                        use_container_width=True,
                        help="丟棄本地未存的改動，從雲端讀最新"):
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
                    st.session_state.pop(f"_confirm_del_{policy_id}", None)
                    st.success(f"✅ 已刪除「{policy_id}」")
                    st.rerun()
                except PolicySheetError as e:
                    st.error(f"❌ 刪除失敗：{e}")
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
            _load_policy_into_buf(client, sheet_id, sanitized)
            # 清掉 input
            st.session_state.pop("v2_new_policy_name", None)
            st.rerun()
        except PolicySheetError as e:
            st.error(f"❌ 建立失敗：{e}")


# ════════════════════════════════════════════════════════════
# 第一次使用 wizard（empty sheet 引導）
# ════════════════════════════════════════════════════════════
def render_first_use_wizard(client: Any, sheet_id: str) -> None:
    """4-step wizard：建保單名 → 加第一檔基金 → 加現金（可跳過）→ 存檔"""
    st.markdown("---")
    st.markdown("#### 🪜 第一次使用嚮導")
    st.caption("跟著 3 步走，建立你的第一張保單與第一檔基金（之後直接編輯即可）。")

    # Step 1：保單名
    st.markdown("**Step 1 / 3：保單名稱**")
    pid = st.text_input("保單名稱", key="wiz_pid",
                          placeholder="例：富邦人壽-001").strip()

    # Step 2：基金
    st.markdown("**Step 2 / 3：第一檔基金（保險公司對帳單抄上來）**")
    _f1, _f2 = st.columns(2)
    fcode = _f1.text_input("基金代號", key="wiz_fcode",
                              placeholder="例：FIDXEQI.LX").strip()
    fname = _f2.text_input("基金名稱", key="wiz_fname",
                              placeholder="例：富達世界基金").strip()
    _f3, _f4, _f5 = st.columns(3)
    units = _f3.number_input("持有單位數", key="wiz_units",
                              min_value=0.0, step=0.01, format="%.4f")
    avg_nav = _f4.number_input("平均 NAV", key="wiz_avg_nav",
                                min_value=0.0, step=0.001, format="%.4f")
    avg_fx = _f5.number_input("平均 FX (USD→TWD)", key="wiz_avg_fx",
                               min_value=0.0, step=0.01, format="%.4f")
    _f6, _f7 = st.columns(2)
    currency = _f6.selectbox("幣別", ["USD", "TWD", "EUR", "GBP", "JPY", "AUD"],
                              key="wiz_ccy")
    tier = _f7.selectbox("級別", ["core", "satellite", ""], key="wiz_tier")

    # Step 3：現金（可跳過）
    st.markdown("**Step 3 / 3：現金部位（沒有可跳過）**")
    _c1, _c2 = st.columns(2)
    cash_ccy = _c1.selectbox("現金幣別", ["（無）", "TWD", "USD", "EUR", "GBP"],
                              key="wiz_cash_ccy")
    cash_amt = _c2.number_input("現金金額", key="wiz_cash_amt",
                                  min_value=0.0, step=1000.0, format="%.2f")

    # 完成
    st.markdown("---")
    _ok1, _ok2 = st.columns([2, 3])
    if _ok1.button("✅ 建立並存檔", key="btn_wiz_finish",
                    type="primary", use_container_width=True,
                    disabled=not (pid and fcode and units > 0)):
        try:
            sanitized = _sanitize_tab_name(pid)
            rows = [{
                "policy_id":  sanitized,
                "item_type":  ITEM_TYPE_FUND,
                "fund_code":  fcode,
                "fund_name":  fname,
                "units":      units,
                "avg_nav":    avg_nav,
                "avg_fx":     avg_fx,
                "currency":   currency,
                "tier":       tier,
                "amount":     "",
                "invest_twd": "",
            }]
            if cash_ccy != "（無）" and cash_amt > 0:
                rows.append({
                    "policy_id":  sanitized,
                    "item_type":  ITEM_TYPE_CASH,
                    "fund_code":  "",
                    "fund_name":  "",
                    "units":      "",
                    "avg_nav":    "",
                    "avg_fx":     "",
                    "currency":   cash_ccy,
                    "tier":       "",
                    "amount":     cash_amt,
                    "invest_twd": "",
                })
            df = pd.DataFrame(rows, columns=list(ALL_COLS_V2))
            write_policy_v2(client, sheet_id, sanitized, df)
            st.success(f"✅ 已建立保單「{sanitized}」+ {len(rows)} 列資料")
            st.session_state.pop("_v2_show_wizard", None)
            # 清 wizard inputs
            for k in ("wiz_pid", "wiz_fcode", "wiz_fname", "wiz_units",
                      "wiz_avg_nav", "wiz_avg_fx", "wiz_cash_amt"):
                st.session_state.pop(k, None)
            # 清 buf cache 觸發下次 render 重讀
            st.session_state.pop(_KEY_V2_LOADED, None)
            st.rerun()
        except PolicySheetError as e:
            st.error(f"❌ 建立失敗：{e}")

    if _ok2.button("取消（回主畫面）", key="btn_wiz_cancel",
                    use_container_width=True):
        st.session_state.pop("_v2_show_wizard", None)
        st.rerun()
