"""v19.35 進階篩選 UI — user 2026-06-09 spec §4 介面需求。

- 2 個下拉：💱 幣別 / 🌏 投資國家
- 1 個 checkbox：「💚 僅顯示含息報酬率 ≥ 配息率」預設 ON
- 表格：無符合資料顯示「查無符合條件的標的」
- 資料源開關：3 軌（TWSE / yfinance / SITCA）獨立 toggle
- 本地備援狀態：cache 幾天前一眼可見
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from services.screener_v2 import (
    PIPELINE_LABELS,
    cache_age_days,
    collect_countries,
    collect_currencies,
    fetch_all_pools,
    filter_rows,
)


def _load_pool(use_twse: bool, use_yf: bool, use_sitca: bool, force: bool) -> list:
    cache_key = "_screener_v2_pool"
    if not force and st.session_state.get(cache_key):
        return st.session_state[cache_key]
    with st.spinner("從 3 軌資料源抓取基金 + ETF 中…"):
        rows = fetch_all_pools(
            use_twse=use_twse, use_yfinance=use_yf, use_sitca=use_sitca,
        )
    st.session_state[cache_key] = rows
    return rows


def render_fund_screener_v2_tab() -> None:
    st.markdown("## 🔬 進階篩選：基金 + ETF (v19.35)")
    st.caption(
        "3 軌資料：🇹🇼 TWSE ETF + 🌐 yfinance (US/境外) + 🏛️ SITCA 共同基金 (stub) "
        "｜ 統一 schema → 篩選：幣別 × 國家 × 含息報酬率 ≥ 配息率"
    )
    st.info(
        "💡 **本 tab 為實驗性 ETF 擴充**，原「🔎 基金篩選」(v19.34) 共同基金核心保留不動。",
        icon="ℹ️",
    )

    with st.expander("⚙️ 資料源開關 + 本地備援狀態", expanded=False):
        c1, c2, c3 = st.columns(3)
        use_twse = c1.toggle("🇹🇼 TWSE ETF", value=True, key="_v2_use_twse")
        use_yf = c2.toggle("🌐 yfinance", value=True, key="_v2_use_yf")
        use_sitca = c3.toggle(
            "🏛️ SITCA", value=False, key="_v2_use_sitca",
            help="預設關閉：parser 仍為 stub（robots.txt 守門 + UA rotation 已備）",
        )
        for p in ("twse", "yfinance", "sitca"):
            age = cache_age_days(p)
            label = PIPELINE_LABELS.get(p, p)
            if age is None:
                st.caption(f"{label}：無本地備援")
            else:
                st.caption(f"{label}：本地備援 {age} 天前")

    refresh = st.button("🔄 重抓（清快取）", key="_v2_refresh")
    rows = _load_pool(use_twse, use_yf, use_sitca, force=refresh)

    if not rows:
        st.warning(
            "⚠️ 三軌全失敗 — 檢查網路 / Proxy 設定，或先載入本地備援。"
            "TWSE OpenAPI / yfinance 連通性可在 sidebar「🔍 測試 Proxy 連線」驗證。"
        )
        return

    st.success(f"✅ 載入 {len(rows)} 檔（ETF + 基金）")

    col_cur, col_cty, col_chk = st.columns([1, 1, 2])
    currencies = ["全部"] + collect_currencies(rows)
    countries = ["全部"] + collect_countries(rows)
    with col_cur:
        cur_sel = st.selectbox("💱 幣別", currencies, key="_v2_cur")
    with col_cty:
        cty_sel = st.selectbox("🌏 投資國家 / 區域", countries, key="_v2_cty")
    with col_chk:
        st.markdown("&nbsp;")
        require_cover = st.checkbox(
            "💚 僅顯示含息報酬率 ≥ 配息率（預設打開）",
            value=True, key="_v2_require_cover",
            help="勾選後只留 total_return ≥ dividend_rate，避免賺股息卻賠價差",
        )

    filtered = filter_rows(
        rows,
        currency=None if cur_sel == "全部" else cur_sel,
        country=None if cty_sel == "全部" else cty_sel,
        require_return_cover_div=require_cover,
    )

    st.markdown(f"### 📋 篩選結果（{len(filtered)} 檔）")
    if not filtered:
        st.info("📭 查無符合條件的標的 — 試著放寬幣別 / 國家 或關掉「含息 ≥ 配息」勾選。")
        return

    df = pd.DataFrame([{
        "資料源": PIPELINE_LABELS.get(r.source, r.source),
        "代碼": r.id,
        "名稱": r.name,
        "幣別": r.currency,
        "國家": r.country,
        "含息1Y%": round(r.total_return, 2),
        "配息率%": round(r.dividend_rate, 2),
        "差距%": round(r.total_return - r.dividend_rate, 2),
    } for r in filtered])
    df = df.sort_values(
        by=["差距%", "含息1Y%"], ascending=[False, False],
    ).reset_index(drop=True)
    st.dataframe(df, use_container_width=True, hide_index=True)
