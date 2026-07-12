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

from shared.ttls import TTL_1MIN
from repositories.policy_repository import (
    ALL_COLS_V2,
    ITEM_TYPE_CASH,
    ITEM_TYPE_FUND,
    PolicySheetError,
    _sanitize_tab_name,
    compute_units,
    delete_policy_worksheet,
    ensure_policy_worksheet,
    estimate_dividend_split,
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
    # v18.160：fund 表 10 欄（v18.153 9 欄 + div_cash_pct 配息現金給付%）
    return pd.DataFrame(columns=[
        "fund_code", "fund_name", "units", "avg_nav", "avg_nav_with_div",
        "avg_fx", "currency", "tier", "invest_twd", "div_cash_pct",
    ])


def _empty_cash_df() -> pd.DataFrame:
    return pd.DataFrame(columns=["currency", "amount"])


def _split_policy_df(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """13 欄 df → (fund 10 欄, cash 2 欄) for st.data_editor 分區顯示。
    v18.160: fund 加 div_cash_pct（配息現金給付%）。"""
    fund_cols = ["fund_code", "fund_name", "units", "avg_nav", "avg_nav_with_div",
                 "avg_fx", "currency", "tier", "invest_twd", "div_cash_pct"]
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
        # v18.160：div_cash_pct clip 至 [0,100]，缺值預設 100
        _dcp = r.get("div_cash_pct", 100)
        try:
            _dcp = float(_dcp) if _dcp not in (None, "") else 100.0
        except (TypeError, ValueError):
            _dcp = 100.0
        _dcp = max(0.0, min(100.0, _dcp))
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
            "amount":           None,  # v18.274: 改 None 而非 "" — fund 列不該有 amount，pyarrow 才不會 mixed-type crash
            "invest_twd":       _inv,
            "div_cash_pct":     _dcp,
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
            # v18.274: cash 列無基金欄位 → 改 None 而非 ""；pyarrow Arrow 表才能正確
            # 推斷整欄為 nullable numeric（之前 mixed str/float 直接 ArrowInvalid crash）
            "units":            None,
            "avg_nav":          None,
            "avg_nav_with_div": None,
            "avg_fx":           None,
            "currency":         ccy,
            "tier":             "",
            "amount":           float(amt),
            "invest_twd":       None,
            "div_cash_pct":     None,   # cash 列無配息，留空
        })
    return pd.DataFrame(rows, columns=list(ALL_COLS_V2))


def _render_div_split_estimate(policy_id: str, fund_df: pd.DataFrame) -> None:
    """v18.160：在保單編輯區下方顯示「📊 配息估算」mini-section。

    依 user 手填的年配息率假設 + 每檔基金的 div_cash_pct，估算
    年現金流 / 年新增單位數。純前端計算（不依賴 portfolio_funds metrics），
    user 即看即得。
    """
    if fund_df is None or fund_df.empty:
        return
    # 只算有 invest_twd 的列
    rows = []
    for _, r in fund_df.iterrows():
        code = str(r.get("fund_code", "") or "").strip()
        inv = float(r.get("invest_twd", 0) or 0)
        if not code or inv <= 0:
            continue
        rows.append(r)
    if not rows:
        return

    # v19.346：expander → container(border)。本 mini-section 從 _render_policy_block
    # 內渲染,而該區塊又位於 tab3「保單管理」expander 內 → 不得用巢狀 expander
    # (StreamlitAPIException: Expanders may not be nested inside other expanders)。
    with st.container(border=True):
        st.markdown("**📊 配息現金/單位拆分估算（依 div_cash_pct）**")
        st.caption(
            "ℹ️ 估算用 user 手填的「年配息率假設 %」乘上每檔基金的 invest_twd，"
            "再依 `現金給付%` 拆分。實際配息以保險公司每月對帳單為準。"
        )
        # v18.170：年/月切換 — 月模式下年率÷12 顯示月配息/月現金/月新增單位
        _est_c1, _est_c2 = st.columns([1, 2])
        rate_pct = _est_c1.number_input(
            "年配息率假設 %", min_value=0.0, max_value=30.0, value=5.0, step=0.5,
            key=f"div_est_rate_{policy_id}",
            help="如不確定可填 5（市場平均月配息基金約 4-7%）。Tab2 載入該基金後可看到實際年化配息率。",
        )
        _period = _est_c2.segmented_control(
            "估算週期",
            ["📅 年估算", "📆 月估算"],
            default="📅 年估算",
            key=f"div_est_period_{policy_id}",
            help="年估算：rate × invest；月估算：rate/12 × invest（對保險公司月對帳單用）",
        ) or "📅 年估算"
        _is_monthly = _period.startswith("📆")
        _div = 12.0 if _is_monthly else 1.0
        _label = "月" if _is_monthly else "年"

        # v18.273：抓即時 FX 給「配息折算」用（成本基礎仍走 avg_fx）
        # User 反饋「組合買入的匯率固定，但轉配息由美元轉台必須要即時匯率」
        _current_fx_cache: dict[str, float] = {}
        def _get_current_fx(_ccy: str) -> float:
            _ccy = (_ccy or "").strip().upper()
            if not _ccy or _ccy == "TWD":
                return 0.0
            if _ccy in _current_fx_cache:
                return _current_fx_cache[_ccy]
            try:
                from services.fund_service import get_latest_fx as _gf
                import os as _os_dvs
                _fk = ""
                try:
                    _fk = st.secrets.get("FRED_API_KEY", "")
                except Exception:
                    _fk = ""
                _fk = _fk or _os_dvs.environ.get("FRED_API_KEY", "")
                _v = _gf(f"{_ccy}TWD=X", fred_api_key=_fk)
                _current_fx_cache[_ccy] = float(_v) if _v else 0.0
            except Exception:
                _current_fx_cache[_ccy] = 0.0
            return _current_fx_cache[_ccy]

        out_rows = []
        total_cash, total_reinv, total_div = 0.0, 0.0, 0.0
        for r in rows:
            _avg_fx_r = float(r.get("avg_fx", 0) or 0)
            _cur_fx_r = _get_current_fx(str(r.get("currency", "") or ""))
            est = estimate_dividend_split(
                invest_twd=float(r.get("invest_twd", 0) or 0),
                annual_div_rate_pct=rate_pct / _div,
                div_cash_pct=float(r.get("div_cash_pct", 100) or 100),
                avg_nav=float(r.get("avg_nav", 0) or 0),
                avg_fx=_avg_fx_r,
                current_fx=_cur_fx_r,  # v18.273
            )
            out_rows.append({
                "基金代號":                str(r.get("fund_code", "") or ""),
                "投資金額(TWD)":           int(r.get("invest_twd", 0) or 0),
                "現金%":                   int(est["cash_pct"]),
                "單位%":                   int(est["unit_pct"]),
                f"{_label}配息總額(TWD)":  int(est["annual_div_twd"]),
                f"{_label}現金流入(TWD)":  int(est["cash_twd"]),
                f"{_label}再投入(TWD)":    int(est["reinvest_twd"]),
                f"{_label}新增單位數":      round(est["new_units"], 4),
            })
            total_div += est["annual_div_twd"]
            total_cash += est["cash_twd"]
            total_reinv += est["reinvest_twd"]
        st.dataframe(pd.DataFrame(out_rows), use_container_width=True, hide_index=True)
        c1, c2, c3 = st.columns(3)
        c1.metric(f"📦 {_label}配息總額", f"NTD {int(total_div):,}")
        c2.metric(f"💵 {_label}現金流入", f"NTD {int(total_cash):,}",
                  delta=f"{(total_cash/total_div*100 if total_div else 0):.0f}% 現金")
        c3.metric(f"🪙 {_label}再投入累積單位",
                  f"NTD {int(total_reinv):,}",
                  delta=f"{(total_reinv/total_div*100 if total_div else 0):.0f}% 單位")


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
@st.cache_data(ttl=TTL_1MIN, show_spinner=False)
def _cached_load_policy_v2(_client: Any, sheet_id: str, policy_id: str):
    """`_client` 前綴底線 → Streamlit 不對 client object 計 hash。"""
    return load_policy_v2(_client, sheet_id, policy_id)


@st.cache_data(ttl=TTL_1MIN, show_spinner=False)
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
    # v19.346：expander → container(border)。render_v2_section 從 tab3「保單管理」
    # expander 內呼叫(見 module docstring),巢狀 expander 會 crash 整個 v2 編輯 UI
    # (StreamlitAPIException: Expanders may not be nested inside other expanders)。
    # 代價:每張保單改為常開外框卡片,不再各自收合。
    with st.container(border=True):
        st.markdown(f"#### {_title}")
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
                # v18.160：配息「現金給付 %」（單位數% = 100 - 該值）
                "div_cash_pct":     st.column_config.NumberColumn(
                                        "🟨 現金給付 %",
                                        min_value=0, max_value=100, step=10,
                                        format="%d",
                                        help="保險公司 APP 設定的「配息現金給付%」。"
                                             "100 = 全部現金、0 = 全部新增單位、"
                                             "80 = 80% 現金 + 20% 新增單位（如 USDEQ5110）。"
                                             "預設 100（多數保單預設行為）。"),
            },
        )
        # v18.160：顯示「單位數%」derived caption + 配息估算 mini-section
        try:
            _dcps = [float(v) for v in edited_fund.get("div_cash_pct", []) if v not in (None, "")]
            if _dcps:
                _avg_cash = sum(_dcps) / len(_dcps)
                st.caption(
                    f"💡 配息拆分均值：**現金 {_avg_cash:.0f}%** / "
                    f"**新增單位 {100 - _avg_cash:.0f}%**（保單內所有基金平均）。"
                    "每檔基金可獨立設定，例如保險公司 APP 設「80% 現金、20% 單位」就填 80。"
                )
        except Exception:
            pass
        _render_div_split_estimate(policy_id, edited_fund)

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
        # v19.240 R8 EX-L1ORCH-1 退役:走 L2 enriched wrapper(含 metrics + reconcile)
        from services.fund_service import fetch_fund_from_moneydj_url_enriched
        raw = fetch_fund_from_moneydj_url_enriched(fund_code)
        fname = raw.get("fund_name", "") or ""
        ccy = raw.get("currency", "") or raw.get("metrics", {}).get("currency", "")
    except Exception:
        pass   # smoke-allow-pass — MoneyDJ 抓失敗，user 之後可手動補
    if fname:
        try:
            from ui.helpers.session import is_core_fund
            tier = "core" if is_core_fund(fname) else "satellite"
        except Exception:
            pass   # smoke-allow-pass
    return fname, ccy, tier
