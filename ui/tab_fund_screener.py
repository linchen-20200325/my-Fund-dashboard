"""v19.27 Fund Screener UI — 基金篩選工具（+ 反向流健康基金榜）。

對齊鉅亨買基金 anuefund 篩選介面的 10 條件 + 自家第 11 條「💚 含息報酬率 ≥ 配息率」三色燈
+ v19.27 第 12 條「每單位月配金額」門檻 + 第三來源池「💎 健康基金榜」（反向流）。

來源池三選一
================
- 📊 我的組合：讀 ``st.session_state["portfolio_funds"]``（已 enrich 完整欄位）
- 🔍 關鍵字搜尋：呼 fund_repository.search_moneydj_by_name → 列原始命中 +
  可選「補抓詳情後套完整 12 篩選」按鈕（會對每檔跑 fetch_fund_multi_source，較慢）
- 💎 健康基金榜（v19.27 反向流）：對白名單 KNOWN_OVERSEAS_FUNDS 批次抓詳情 → 直接秀
  「🟢 健康 / 🟡 警示 / 🔴 吃本金 / ⚪ 資料不足」四桶排行榜
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from services.dividend_health_discoverer import (
    KNOWN_OVERSEAS_FUNDS,
    known_fund_codes,
    rank_by_health,
    summarize_ranking,
)
from services.fund_screener import (
    DIV_HEALTH_LIGHTS,
    apply_filters,
    collect_distinct_values,
)


# ════════════════════════════════════════════════════════════════
# §1 來源池 loader
# ════════════════════════════════════════════════════════════════
def _load_my_portfolio_funds() -> list[dict]:
    """從 session_state 抓既有組合基金；按 fund_code 去重。"""
    raw = st.session_state.get("portfolio_funds") or []
    seen: set[str] = set()
    out: list[dict] = []
    for f in raw:
        if not isinstance(f, dict):
            continue
        code = str(f.get("fund_code") or f.get("full_key") or "").strip()
        if not code or code in seen:
            continue
        seen.add(code)
        out.append(f)
    return out


def _search_pool_minimal(keyword: str) -> list[dict]:
    """呼搜尋 API → 回 minimal dict list（只有 full_key/name/portal/nav/source）。"""
    if not keyword.strip():
        return []
    try:
        from repositories.fund_repository import search_moneydj_by_name
    except ImportError:
        try:
            from fund_fetcher import search_moneydj_by_name  # type: ignore
        except ImportError:
            return []
    try:
        return search_moneydj_by_name(keyword) or []
    except Exception as e:
        st.warning(f"搜尋失敗：{e}")
        return []


def _load_discover_pool(force_refresh: bool = False) -> list[dict]:
    """v19.27 反向流：對 KNOWN_OVERSEAS_FUNDS 批次抓 enriched 詳情。

    結果存 session_state["_screener_discover_pool"] 跨 rerun 持久（避免重抓）。
    force_refresh=True 時清快取重抓。
    """
    cache_key = "_screener_discover_pool"
    if not force_refresh and st.session_state.get(cache_key):
        return st.session_state[cache_key]

    try:
        from fund_fetcher import fetch_fund_multi_source
    except ImportError:
        st.error("找不到 fetch_fund_multi_source，無法載入健康基金榜。")
        return []

    codes = known_fund_codes()
    out: list[dict] = []
    progress = st.progress(0.0, text=f"批次抓取健康基金榜 0/{len(codes)}…")
    for i, code in enumerate(codes, 1):
        try:
            d = fetch_fund_multi_source(code)
            if isinstance(d, dict):
                out.append(d)
        except Exception as e:
            st.caption(f"⚠️ {code} 抓取失敗：{e}")
        progress.progress(i / len(codes), text=f"批次抓取健康基金榜 {i}/{len(codes)}…")
    progress.empty()

    st.session_state[cache_key] = out
    return out


def _enrich_search_hits(hits: list[dict], max_n: int = 10) -> list[dict]:
    """對 search 結果批次抓詳情（fetch_fund_multi_source），讓 11 條件 filter 能跑。

    限制 max_n 避免暴量 HTTP；user 可手動加大但有 warning。
    """
    try:
        from fund_fetcher import fetch_fund_multi_source
    except ImportError:
        st.error("找不到 fetch_fund_multi_source，無法補抓詳情。")
        return []

    enriched: list[dict] = []
    progress = st.progress(0.0, text=f"補抓詳情 0/{min(len(hits), max_n)}…")
    capped = hits[:max_n]
    for i, h in enumerate(capped, 1):
        code = h.get("full_key") or h.get("code") or ""
        if not code:
            continue
        try:
            d = fetch_fund_multi_source(code)
            if isinstance(d, dict):
                enriched.append(d)
        except Exception as e:
            st.caption(f"⚠️ {code} 抓取失敗：{e}")
        progress.progress(i / len(capped), text=f"補抓詳情 {i}/{len(capped)}…")
    progress.empty()
    return enriched


# ════════════════════════════════════════════════════════════════
# §2 Filter widget 渲染
# ════════════════════════════════════════════════════════════════
_FIELD_LABEL_MAP: dict[str, str] = {
    "domestic_overseas": "境內/境外",
    "fund_type": "基金類型",
    "currency": "計價幣別",
    "brand": "基金品牌",
    "fund_region": "投資區域",
    "fund_group": "基金組別",
    "dividend_freq": "配息頻率",
    "risk_level": "風險等級",
}


def _render_filter_widgets(funds: list[dict]) -> dict[str, Any]:
    """左欄渲染 11 widget，回 filters dict 給 apply_filters 用。"""
    filters: dict[str, Any] = {}
    st.markdown("### 🎛️ 篩選條件")
    st.caption("對齊鉅亨買基金 10 條件 + 自家新增第 11 條含息健康度")

    # 8 個 multiselect（多選 OR）— 動態抽取 options
    for field, label in _FIELD_LABEL_MAP.items():
        opts = collect_distinct_values(funds, field)
        if not opts:
            continue
        # field 在 apply_filters 內部對應的 key 名（兩者一致）
        key_in_filters = "region" if field == "fund_region" else field
        selected = st.multiselect(label, opts, key=f"_screener_{field}")
        if selected:
            filters[key_in_filters] = selected

    # 2 個 slider（數值門檻）
    col1, col2 = st.columns(2)
    with col1:
        lipper = st.slider(
            "理柏總回報 ≥", 0, 5, 0,
            help="0 = 不限；1-5 為理柏星等門檻", key="_screener_lipper",
        )
        if lipper > 0:
            filters["lipper_min"] = lipper
    with col2:
        esg = st.slider(
            "ESG 評分 ≥", 0, 100, 0, step=10,
            help="0 = 不限；對齊鉅亨 >30 / >40 篩選", key="_screener_esg",
        )
        if esg > 0:
            filters["esg_min"] = esg

    # v19.27 第 12 條：每單位月配金額門檻
    mthly_div = st.slider(
        "💰 每單位月配金額 ≥", 0.0, 1.0, 0.0, step=0.01,
        help="0 = 不限；門檻單位依基金幣別（USD / TWD…）",
        key="_screener_mthly_div_min",
    )
    if mthly_div > 0:
        filters["monthly_div_min"] = mthly_div

    # 第 11 條：自家新增含息健康度 toggle
    st.markdown("---")
    healthy_only = st.toggle(
        "💚 只看「含息報酬率 ≥ 配息率」（健康）",
        value=False,
        help="圖二燈號邏輯：含息 ≥ 配息 = 🟢 有淨值成長支撐配息；差距 ≤ 2% = 🟡 警示；> 2% = 🔴 吃本金",
        key="_screener_healthy_only",
    )
    if healthy_only:
        filters["div_health_healthy_only"] = True

    return filters


# ════════════════════════════════════════════════════════════════
# §3 結果區塊渲染
# ════════════════════════════════════════════════════════════════
def _render_summary(stats: dict) -> None:
    """頂部 4 卡 + 三色燈分布。"""
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📥 來源池", f"{stats['n_input']} 檔")
    c2.metric("✅ 通過篩選", f"{stats['n_output']} 檔")
    c3.metric("🚫 被剔除", f"{stats['n_filtered_out']} 檔")
    lights = stats["lights"]
    c4.metric(
        "💚 健康燈",
        f"{lights['健康']} 檔",
        delta=f"⚠️ {lights['警示']}｜🔴 {lights['吃本金']}",
        delta_color="off",
    )

    # 三色燈詳細分布
    cols = st.columns(4)
    for i, label in enumerate(DIV_HEALTH_LIGHTS):
        cols[i].caption(f"{label}：{lights[label]} 檔")


def _build_table(filtered: list[dict]) -> pd.DataFrame:
    """把 filtered fund dict list 轉成顯示用 DataFrame。"""
    rows = []
    for f in filtered:
        m = f.get("metrics") or {}
        mj = f.get("moneydj_raw") or {}
        # 含息 / 配息抓 metrics 與 moneydj_raw fallback
        ret_1y = m.get("ret_1y_total") or m.get("ret_1y")
        div_rate = (
            mj.get("moneydj_div_yield") or m.get("annual_div_rate")
        )
        rows.append({
            "燈": f.get("_div_health_emoji", "⚪"),
            "健康度": f.get("_div_health_light", "資料不足"),
            "基金代碼": f.get("fund_code") or f.get("full_key") or "",
            "基金名稱": f.get("fund_name") or "",
            "幣別": f.get("currency") or "",
            "類型": f.get("fund_type") or f.get("category") or "",
            "風險": f.get("risk_level") or "",
            "配息頻率": f.get("dividend_freq") or "",
            "含息1Y%": (
                round(float(ret_1y), 2) if ret_1y is not None else None
            ),
            "配息率%": (
                round(float(div_rate), 2) if div_rate is not None else None
            ),
            "月配/單位": (
                round(float(f["_monthly_div_amount"]), 4)
                if f.get("_monthly_div_amount") is not None else None
            ),
        })
    return pd.DataFrame(rows)


def _render_table(filtered: list[dict]) -> None:
    if not filtered:
        st.info("📭 沒有基金通過篩選條件 — 試著放寬幾條 multiselect 或關掉「💚 只看健康」toggle。")
        return
    df = _build_table(filtered)
    # 排序：燈號優先（健康在最上）、再按含息排
    light_order = {"🟢": 0, "🟡": 1, "🔴": 2, "⚪": 3}
    df = df.sort_values(
        by=["燈", "含息1Y%"],
        key=lambda c: c.map(light_order) if c.name == "燈" else c,
        ascending=[True, False],
        na_position="last",
    ).reset_index(drop=True)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_light_spec() -> None:
    """🟢🟡🔴 三色燈規格說明 — 對應圖二燈號邏輯。"""
    with st.expander("📐 含息健康度燈號規格（對應圖二）", expanded=False):
        st.markdown("""
| 燈號 | 條件 | 解讀 |
|---|---|---|
| 🟢 健康 | 含息報酬率 ≥ 配息率 | 有淨值成長作支撐 |
| 🟡 警示 | 配息率 − 含息報酬率 ≤ 2% | 正在輕微侵蝕本金 |
| 🔴 吃本金 | 配息率 − 含息報酬率 > 2% | 配息主要來自本金返還 |
| ⚪ 資料不足 | 含息或配息任一缺值 | 待「補抓詳情」 |

**含息報酬率優先序**：`metrics.ret_1y_total` → `perf["1Y"]`（MoneyDJ wb01）→ 自算（淨值漲跌% + 配息率）
**配息率優先序**：`moneydj_div_yield`（MoneyDJ wb05 官方值）→ `annual_div_rate`（自算近 12 月配息 / 平均淨值）

**實例**：安聯收益成長 含息 1Y = +5.2%，配息率 = 9.6%
→ 差距 -4.4% > 2% → 🔴 吃本金（每年淨值被侵蝕 4.4%，10 年後本金大幅減損）
""")


# ════════════════════════════════════════════════════════════════
# §4 主入口
# ════════════════════════════════════════════════════════════════
def render_fund_screener_tab() -> None:
    st.markdown("## 🔎 基金篩選工具")
    st.caption(
        "對齊鉅亨買基金 anuefund 篩選 + 新增「💚 含息報酬率 ≥ 配息率」三色燈"
        "（圖二健康度判讀）"
    )

    source = st.radio(
        "資料來源池",
        ["📊 我的組合", "🔍 關鍵字搜尋", "💎 健康基金榜"],
        horizontal=True,
        key="_screener_source",
        help=(
            "我的組合：用已載入的基金（快、完整 12 條件）；"
            "關鍵字搜尋：探索新基金（慢、需補抓詳情）；"
            "💎 健康基金榜（v19.27 反向流）：對知名海外基金白名單批次跑健康度排行"
        ),
    )

    funds: list[dict] = []

    if source == "📊 我的組合":
        funds = _load_my_portfolio_funds()
        if not funds:
            st.info(
                "📭 還沒載入任何組合基金。請先到「📊 組合基金」Tab 載入保單/組合，"
                "回來這裡就能套 11 條件篩選 + 三色燈評估。"
            )
            return
        st.success(f"✅ 已從我的組合載入 {len(funds)} 檔基金")

    elif source == "💎 健康基金榜":
        st.caption(
            f"🌐 反向流：對 KNOWN_OVERSEAS_FUNDS 白名單（{len(KNOWN_OVERSEAS_FUNDS)} 檔台灣可買境外基金）"
            "批次跑 fetch_fund_multi_source → 健康度排行榜。首次載入約需 30-60 秒。"
        )
        col_btn1, col_btn2 = st.columns([1, 1])
        with col_btn1:
            load_clicked = st.button(
                "🌟 載入健康基金榜", type="primary", use_container_width=True,
                key="_screener_load_discover",
            )
        with col_btn2:
            refresh_clicked = st.button(
                "🔄 重抓（清快取）", use_container_width=True,
                key="_screener_refresh_discover",
            )

        if load_clicked or refresh_clicked:
            with st.spinner("批次抓取健康基金榜中…"):
                funds = _load_discover_pool(force_refresh=refresh_clicked)
        else:
            funds = st.session_state.get("_screener_discover_pool") or []

        if not funds:
            st.info("👆 按「🌟 載入健康基金榜」開始批次抓取詳情並排健康度。")
            _render_light_spec()
            return

        # 渲染排行榜摘要（4 桶計數 + 健康占比）
        buckets = rank_by_health(funds)
        summary = summarize_ranking(buckets)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🟢 健康", f"{summary['counts']['健康']} 檔")
        c2.metric("🟡 警示", f"{summary['counts']['警示']} 檔")
        c3.metric("🔴 吃本金", f"{summary['counts']['吃本金']} 檔")
        c4.metric("💎 健康占比", f"{summary['healthy_pct']}%")
        st.success(f"✅ 已載入 {len(funds)} 檔健康基金榜，可繼續套 12 條件再篩")

    else:  # 🔍 關鍵字搜尋
        kw = st.text_input(
            "輸入基金名稱關鍵字",
            placeholder="例如：安聯、貝萊德、收益成長、5G、AI",
            key="_screener_kw",
        )
        col_btn1, col_btn2 = st.columns([1, 1])
        with col_btn1:
            search_clicked = st.button("🔍 搜尋", type="primary", use_container_width=True)
        with col_btn2:
            max_n = st.number_input(
                "補抓詳情上限",
                min_value=1, max_value=30, value=10, step=1,
                help="補抓詳情會對每檔跑 MoneyDJ/FundClear 抓取，每檔約 3-5 秒",
                key="_screener_max_n",
            )

        # 維持搜尋結果在 session_state，避免按一下就消失
        if search_clicked and kw.strip():
            with st.spinner(f"搜尋「{kw}」中…"):
                st.session_state["_screener_search_hits"] = _search_pool_minimal(kw)
                st.session_state.pop("_screener_enriched", None)

        hits = st.session_state.get("_screener_search_hits") or []
        if not hits:
            st.info("👆 輸入關鍵字後按「搜尋」")
            _render_light_spec()
            return

        st.caption(f"📦 搜尋命中 {len(hits)} 筆（取前 {max_n} 檔補抓詳情）")
        st.dataframe(
            pd.DataFrame(hits)[["full_key", "name", "portal", "source"]].head(max_n),
            use_container_width=True, hide_index=True,
        )

        if st.button(f"📥 補抓前 {max_n} 檔詳情並套完整 11 篩選", type="secondary"):
            st.session_state["_screener_enriched"] = _enrich_search_hits(hits, max_n=int(max_n))

        funds = st.session_state.get("_screener_enriched") or []
        if not funds:
            st.info("👆 補抓詳情後才能套完整 11 條件篩選與三色燈評估")
            _render_light_spec()
            return
        st.success(f"✅ 已補抓 {len(funds)} 檔詳情")

    # 兩路徑共用 — 渲染 filter + table
    st.markdown("---")
    col_filter, col_result = st.columns([1, 2], gap="large")
    with col_filter:
        filters = _render_filter_widgets(funds)
    with col_result:
        filtered, stats = apply_filters(funds, filters)
        _render_summary(stats)
        st.markdown("### 📋 篩選結果")
        _render_table(filtered)

    _render_light_spec()
