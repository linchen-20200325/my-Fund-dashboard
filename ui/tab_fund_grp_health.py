"""v19.37 ui — 💊 基金組合健診 Tab。

對 100 萬 TWD 為基準，模擬持有 N 檔境外保單基金，計算每次配息折回 TWD 金額並判定吃本金。

UI 結構：
  1. text_area 多碼貼上（上限 10 檔，鏡像 stock_grp）
  2. 本金 / 警示閾值參數
  3. 按鈕觸發 → progress + 抓 NAV / 配息 / FX → 純函式運算
  4. KPI metric + 健診總表 + 逐期配息明細 expander

🧮 標示：所有自行計算欄位（份額 / TWD 配息 / 含息報酬率 / 吃本金判定）
原始欄位（MoneyDJ/Cnyes 直給）：除息日 / 原幣配息 / NAV
"""
from __future__ import annotations

import streamlit as st

from shared.colors import GH_BG_PRIMARY, GH_FG_SECONDARY, GRAY_55, INFO_BLUE, TRAFFIC_GREEN
from shared.converters import safe_num  # v19.387 V1 §1:缺值保留 None(不畫成 0% 假柱)

_MAX_CODES = 10
_DEFAULT_CCY = "USD"


def _pick_comparison_basis(rows: "list[dict]") -> str:
    """v19.304: 多基金績效比較圖的「基準」選擇 SSOT（純函式，可單元測試）。

    背景（user 2026-07-04「多檔比較資料都是 0」）：v19.180 把績效欄拆成
    「(年化)」+「(全期實際)」兩套。年化欄在持有 < 0.5 年時依
    `dividend_calc.MIN_YEARS_FOR_ANNUALIZE`（SSOT = shared/signal_thresholds.py）
    一律回 None（防「短期配息 × 倍數」年化幻象，§1 Fail Loud）。同保單同期買進的
    多檔常整排短歷史 → 年化全 None → 圖表 `float(None or 0)` 畫成全 0 空圖。

    規則：全檔都有年化值（皆 ≥ 0.5 年）→ 用「年化」(跨檔可比、原設計)；
    任一檔短歷史（年化為 None）→ 全圖退「全期實際」(100% 真實累計、永遠有值、
    不年化故無造假)。回傳基準字串，caller 用 f"X% ({basis})" 組欄位鍵，
    確保同一張圖各檔基準一致（不混基準）。
    """
    _all_annual = all(
        r.get("配息率% (年化)") is not None
        and r.get("含息% (年化)") is not None
        and r.get("淨值% (年化)") is not None
        for r in rows
    )
    return "年化" if _all_annual else "全期實際"


def _dedup_upper(seq) -> "list[str]":
    """代號清單 order-preserving 去重 + 大寫正規化 —— SSOT:本 Tab 代號唯一化只此一處。

    背景(user 2026-07-05「配息事件（多檔合併）有重複」):同一基金若被多張保單持有,
    `portfolio_funds` 會出現同 code 多筆;「🔗 從我的組合帶入」後代號清單即帶重複 →
    `_run_batch_health` 逐檔各算一次 → 持有 meta / 配息事件 / 比較圖三表全部重複列。
    本 Tab 輸入僅「代號 + 單一本金」,同 code = 完全相同計算 = 真重複,去重安全。
    """
    out: "list[str]" = []
    seen: set[str] = set()
    for x in seq:
        c = str(x).strip().upper()
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _dedup_rows_by_code(rows: "list[dict]") -> "list[dict]":
    """row list order-preserving 去重(以 code 為鍵)—— SSOT 顯示層 chokepoint。

    `_render_health_3tables` 同時被健診 Tab 與 Tab3 組合 embed 呼叫;任一路徑若傳入
    同 code 多筆(多保單持同檔),持有 meta / 配息事件 / 比較圖三表都會重複列。在渲染
    入口一次去重覆蓋所有 caller(補「代號輸入端 `_dedup_upper`」的另一半,兩者互補)。
    空 code 的 row 視為各自唯一(不丟、不去重),避免誤刪合法列。
    """
    out: "list[dict]" = []
    seen: set[str] = set()
    for r in rows:
        c = str(r.get("code", "")).strip().upper()
        if c and c in seen:
            continue
        if c:
            seen.add(c)
        out.append(r)
    return out


def render_fund_grp_health_tab() -> None:
    """渲染 💊 基金組合健診 Tab（v19.37 新增）。"""
    st.markdown("### 💊 基金組合健診")
    from ui.helpers.story_nav import render_story_nav
    render_story_nav("health")  # v19.405 Phase 4:健診為決策動線第 2 站
    st.caption(
        "對 **100 萬 TWD** 為基準，模擬持有期間每次配息折算 TWD 金額並判定吃本金。"
        "🧮 = 本系統自行換算（非 MoneyDJ/Cnyes 直給）。"
    )

    # v19.303: 總經 Phase 對照橫幅 — 提供健診結果的市場環境上下文
    _phase_info = st.session_state.get("phase_info") or {}
    _phase_name = _phase_info.get("phase", "")
    if _phase_name:
        _phase_lower = _phase_name.lower()
        if any(k in _phase_lower for k in ("多頭", "擴張", "bull", "expansion")):
            _phase_icon, _phase_tip = "🟢", "多頭期：健診標準可適度放寬，重點看含息報酬能否跑贏通膨。"
        elif any(k in _phase_lower for k in ("衰退", "防禦", "bear", "recession")):
            _phase_icon, _phase_tip = "🔴", "防禦期：吃本金判定應從嚴看待；股票型基金承壓，配息穩定性更重要。"
        else:
            _phase_icon, _phase_tip = "🟡", "過渡期：健診結果請搭配個別基金趨勢判斷。"
        # v19.403 Phase 2 DUP-3:景氣位階字卡走 format_phase_score SSOT。
        # 原「評分 {_score:+.1f}」(如 +6.5)誤用正負號 —— phase score 恆 0-10,
        # 與 hero 的 23 指標淨分(genuinely signed)撞臉;改「{phase} {score}/10」統一。
        from ui.helpers.macro_helpers import format_phase_score
        st.info(
            f"📊 當前總經 Phase：{_phase_icon} **{format_phase_score(_phase_info)}**"
            f"　{_phase_tip}"
        )
    else:
        st.caption("💡 先至「🌐 市場定調」Tab 載入資料，健診結果將顯示對應市場環境說明。")

    # v19.302: 從組合配置帶入基金代號（讀 portfolio_funds session_state）
    _pf_raw = st.session_state.get("portfolio_funds") or []
    # v19.322 SSOT 去重:同基金跨多保單會出現同 code 多筆,帶入前先唯一化(否則三表重複列)
    _pf_codes = _dedup_upper(f.get("code", "") for f in _pf_raw)
    if _pf_codes:
        if st.button(f"🔗 從我的組合帶入（{len(_pf_codes)} 檔）", key="grp_health_import_from_pf"):
            st.session_state["fund_grp_health_codes"] = "\n".join(_pf_codes)
            st.rerun()

    codes_raw = st.text_area(
        f"基金代號（每行一檔，最多 {_MAX_CODES} 檔；例：ACCP138）",
        key="fund_grp_health_codes",
        height=130,
        placeholder="ACCP138\nACUSI23\n...",
    )
    # v19.59：移除「原幣別 fallback」selectbox — 幣別嚴格走 MoneyDJ wb05「計價幣別」欄抓網路。
    # MoneyDJ 抓不到 → 該檔回 error「幣別未知」（不再用人工選的 fallback 矇混）。
    c1, c2 = st.columns(2)
    with c1:
        principal_twd = st.number_input(
            "本金（TWD）",
            min_value=10_000.0, max_value=10_000_000.0,
            value=1_000_000.0, step=100_000.0,
            key="fund_grp_health_principal",
        )
    with c2:
        warn_gap = st.slider(
            "吃本金閾值 %",
            min_value=0.5, max_value=5.0, value=2.0, step=0.5,
            key="fund_grp_health_warn_gap",
            help="配息率 − 含息報酬率 > 此值 → 標 🔴 吃本金",
        )

    if not st.button("🩺 開始健診", key="fund_grp_health_btn"):
        return

    # v19.322:代號去重(SSOT _dedup_upper)—— 防同檔被多保單/手動貼多次 → 逐檔明細三表重複列
    codes = _dedup_upper(codes_raw.splitlines())[:_MAX_CODES]
    if not codes:
        st.warning("請至少輸入 1 個基金代號")
        return

    rows = _run_batch_health(codes, principal_twd, "", warn_gap)

    # v19.359 Track 2:健診批次抓成功 → 把各檔當日最新 NAV append 進 Google Sheet
    # nav_history 分頁(一鍵累積全部持倉,從現在累積歷史序列)。冪等 + 非致命。
    try:
        from ui.helpers.nav_history_hook import record_batch_nav_points
        record_batch_nav_points(
            [(r["code"], r["_fund_raw"]) for r in rows
             if r.get("ok") and r.get("_fund_raw")],
            source="健診",
        )
    except Exception:
        pass  # 記錄失敗不影響主流程(helper 內已顯示提示)

    # v19.189：逐檔財務健診（4 大功能 + 健診摘要表 PK + 健診卡）移到「健診總表」上方
    #（user 要求：易讀的摘要 PK + 健診卡應先看到，逐欄 🧮 總表移其下）。
    # _funds_extra 由 _build_fund_dict 包裝，下方「健診總表」與「進階分析」共用同一份。
    _funds_extra: list = []
    try:
        from ui.helpers.fund_grp_health_extras import _build_fund_dict
        _funds_extra = [
            _build_fund_dict(r["_fund_raw"], r["code"], principal_twd)
            for r in rows
            if r.get("ok") and r.get("_fund_raw")
        ]
    except Exception as _e_build:
        st.caption(
            f"⬜ 進階資料建構失敗：[{type(_e_build).__name__}] {str(_e_build)[:80]}"
        )
        _funds_extra = []

    # v19.181:模組化 3 表 wrapper(健康分析 / 配息相關 / 實際購買結果)。
    # funds_extra 透給 _render_health_table 內部用(基金體檢 PK + 健診卡)。
    # v19.347：健檢 Tab 開「🎯 選基金（低基期）」;Tab3 持倉健診不開(預設 False)。
    _render_health_3tables(rows, funds_extra=_funds_extra, show_screener=True)

    # v19.58 — 其餘進階貼圖區塊（真實收益矩陣 + 投資試算 + 持股 + 多檔比較 + AI…）。
    # 基金體檢 PK + 4 大健診卡已上移至健診總表之前，不再由此區塊渲染（避免上下重複）。
    if _funds_extra:
        try:
            from ui.helpers.fund_grp_health_extras import render_fund_grp_health_extras
            render_fund_grp_health_extras(_funds_extra, principal_twd)
        except Exception as _e_extra:
            st.caption(
                f"⬜ 進階分析區塊渲染失敗：[{type(_e_extra).__name__}] "
                f"{str(_e_extra)[:80]}"
            )


# v19.413:_auto_fetch_moneydj 隨 process_one_fund 下沉 services/fund_row.py 後,本檔已無 caller,
# 死 import 移除(fallback chain 仍集中於 services.moneydj_fetcher.auto_fetch_moneydj)。


# v19.413:process_one_fund 下沉 L2(services/fund_row.py),健診 + 批次共用同引擎。
from services.fund_row import process_one_fund  # noqa: E402

# backward-compat alias(舊呼叫者 / 測試直接 import 老名)
_process_one_fund = process_one_fund


def _run_batch_health(
    codes: list[str],
    principal_twd: float,
    ccy_hint: str,
    warn_gap: float,
) -> list[dict]:
    """v19.68 H：N 檔基金並行健診（原逐檔序列 → ThreadPoolExecutor）。

    瓶頸：每檔序列 _auto_fetch_moneydj（MoneyDJ 2-30s）+ get_latest_fx 累加，
    10 檔可達數十秒。改並行（max 4 worker，鏡像 Tab3 portfolio_load + macro
    4-way）。worker 無 st 呼叫；進度條在主執行緒以 as_completed 更新；by-index
    收集保留輸入順序與重複代碼。
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    n = len(codes)
    if n == 0:
        return []
    prog = st.progress(0.0, text="📥 並行抓取資料中…")
    _results: list = [None] * n
    _workers = min(n, 4)
    try:
        with ThreadPoolExecutor(max_workers=_workers) as _ex:
            _futs = {
                _ex.submit(process_one_fund, _c, principal_twd, ccy_hint, warn_gap): _i
                for _i, _c in enumerate(codes)
            }
            _done = 0
            for _fut in as_completed(_futs):
                _i = _futs[_fut]
                try:
                    _results[_i] = _fut.result()
                except Exception as e:
                    _results[_i] = {"code": codes[_i], "ok": False,
                                    "error": f"{type(e).__name__}: {e}"}
                _done += 1
                prog.progress(_done / n, text=f"📥 已完成 {_done}/{n} 檔…")
    finally:
        prog.empty()
    # 防呆：任一 slot 未填（理論上不會）→ 補錯誤列
    return [(_r if _r is not None
             else {"code": codes[_idx], "ok": False, "error": "未取得結果"})
            for _idx, _r in enumerate(_results)]


def _render_mj_freshness_banner(ok_rows: list[dict]) -> None:
    """v19.62 E3：改 call 共用 helper（向後相容包裝；原 60 行邏輯抽至 ui/helpers/freshness）。"""
    from ui.helpers.freshness import render_mj_freshness_banner
    _items = [
        {"code": _r.get("code", "?"), "name": _r.get("基金名", ""),
         "nav_date": _r.get("_nav_date", ""), "fetched_at": _r.get("_fetched_at", "")}
        for _r in ok_rows
    ]
    render_mj_freshness_banner(_items)


def _eats_principal_flag(fd: dict) -> "bool | None":
    """v19.347：從 MK 吃本金 verdict 取乾淨布林（True=吃本金 / False=不吃 / None=未知）。

    走 `dividend_safety` 的 `alert_level`（red/yellow/green/grey）語意欄位,
    不解析 emoji：red→吃本金；green/yellow→不吃（黃=margin 薄但未吃）；其餘→未知。
    """
    try:
        from services.health.dividend import check_eating_principal_1y_mk
        _v = check_eating_principal_1y_mk(fd)
        if isinstance(_v, dict):
            _lvl = _v.get("alert_level")
            if _lvl == "red":
                return True
            if _lvl in ("green", "yellow"):
                return False
    except Exception:
        pass
    return None


def _render_low_base_screener(ok_rows: list[dict]) -> None:
    """🎯 選基金（低基期進場點）— v19.347。

    在「已載入的基金」裡找進場候選：現價落在「期間高點 − N×標準差」之下（低基期）
    且不吃本金，可依幣別/類別篩。**重用組合健診已抓的 NAV**，不新增外部抓取。
    L3 render；篩選邏輯全在 `services.fund_screening`（L2 純函式）。
    """
    from services.fund_screening import screen_funds  # L2 純函式

    # 1) 由已載入 row 的 _fund_raw 組 items（series/幣別/類別 + 吃本金布林）
    items = []
    for _r in ok_rows:
        fd = _r.get("_fund_raw") or {}
        _mj = fd.get("moneydj_raw") or {}
        items.append({
            "code": _r.get("code", ""),
            "name": (fd.get("fund_name") or _r.get("基金名") or "")[:24],
            "series": fd.get("series"),
            "currency": (fd.get("currency") or _r.get("ccy") or "").strip().upper(),
            "category": (_mj.get("category") or fd.get("category") or "").strip(),
            "eats_principal": _eats_principal_flag(fd),
        })

    st.markdown("#### 🎯 選基金（低基期進場點 · 高點−σ）")
    st.caption(
        "在已載入的基金裡，找「現價 ≤ 期間高點 − N×標準差」且不吃本金的**進場候選**。"
        "低幾σ 越大 = 離高點越深。"
    )

    _c1, _c2, _c3 = st.columns([1, 1, 2])
    _n = _c1.radio("低基期 σ 倍數", [1, 2], horizontal=True, key="lb_nsigma",
                   help="門檻 = 期間高點 − N×標準差；N 越大越嚴（要跌更深才算低基期）。")
    _lb_years = _c2.radio("回看期間", ["1年", "2年", "3年"], key="lb_years",
                          help="以交易日計：1年≈252、2年≈504、3年≈756。")
    _lookback = {"1年": 252, "2年": 504, "3年": 756}[_lb_years]
    _all_ccy = sorted({it["currency"] for it in items if it["currency"]})
    _all_cat = sorted({it["category"] for it in items if it["category"]})
    _sel_ccy = _c3.multiselect("幣別（外幣/台幣）", _all_ccy, default=_all_ccy, key="lb_ccy")
    _sel_cat = _c3.multiselect("基金類別", _all_cat, default=_all_cat, key="lb_cat")
    _cc1, _cc2 = st.columns(2)
    _only_eat = _cc1.checkbox("只留不吃本金（MK 綠/黃燈）", value=True, key="lb_noeat")
    _only_low = _cc2.checkbox("只留低基期", value=True, key="lb_onlylow")

    # 2) L2 純函式篩選（多選清空 → None = 不篩該維度，避免空表困惑）
    rows = screen_funds(
        items, n_sigma=float(_n), lookback=_lookback,
        only_low_base=_only_low, only_no_eat=_only_eat,
        currencies=(set(_sel_ccy) or None),
        categories=(set(_sel_cat) or None),
    )
    if not rows:
        st.info("目前沒有符合條件的基金——可放寬 σ / 回看期間，或取消『只留』勾選。")
        return

    import pandas as pd
    from streamlit import column_config as _cc
    _eat_map = {True: "🔴 吃本金", False: "🟢 不吃", None: "❓ 未知"}
    _lb_map = {True: "✅ 低基期", False: "— 非低基期", None: "⚪ 無法判定"}
    _df = pd.DataFrame([{
        "代號": r["code"], "基金名": r["name"],
        "類別": r["category"] or "—", "幣別": r["currency"] or "—",
        "現價": r["current"], "期間高點": r["high"],
        "門檻(高點−σ)": r["threshold"],
        "低幾σ": r["sigma_below_high"],
        "低基期": _lb_map.get(r["is_low_base"], "⚪"),
        "吃本金": _eat_map.get(r["eats_principal"], "❓ 未知"),
        "樣本數": r["n_points"],
        "可信度": "✅" if r["reliable"] else "⚠️ 低",
    } for r in rows])
    st.dataframe(
        _df, use_container_width=True, hide_index=True,
        column_config={
            "現價": _cc.NumberColumn(format="%.2f"),
            "期間高點": _cc.NumberColumn(format="%.2f"),
            "門檻(高點−σ)": _cc.NumberColumn(format="%.2f"),
            "低幾σ": _cc.NumberColumn(format="%.2f σ"),
        },
    )
    st.caption(
        f"共 {len(rows)} 檔符合（依「低幾σ」深→淺排序）。門檻/σ 以「{_lb_years}」窗 × {_n}σ 計算；"
        "停售/NAV 幾乎不動者（std≈0）標『無法判定』不硬湊（§1）；樣本 < 60 筆標『可信度低』。"
    )
    st.download_button(
        "⬇️ 下載選基金清單 CSV", _df.to_csv(index=False).encode("utf-8-sig"),
        "low_base_funds.csv", "text/csv", key="lb_dl",
    )


def _render_health_3tables(rows: list[dict],
                           funds_extra: list | None = None,
                           show_screener: bool = False) -> None:
    """v19.181 3 表模組化渲染:① 健康分析 ② 配息相關 ③ 實際購買結果(既有 _render_health_table)。

    共用 SSOT row builder(`services.health.report`)讓 Tab3 也能同源渲染。
    每張表獨立 dataframe,user 可選關注的維度。

    Args:
        rows: process_one_fund 回傳的 row list
        funds_extra: v19.189 基金體檢 PK + 健診卡資料(透給 _render_health_table 用,
                     Tab3 caller 不傳則 None)
    """
    if not rows:
        return
    # v19.322 SSOT 去重(顯示層 chokepoint):健診 Tab + Tab3 embed 皆經此;同 code 多筆
    # (多保單持同檔)只留第一筆 → 持有 meta / 配息事件 / 比較圖三表不再重複列。
    rows = _dedup_rows_by_code(rows)
    import pandas as pd
    from streamlit import column_config as _cc
    from services.health.report import (
        build_dividend_summary_row,
        build_health_analysis_row,
    )

    ok_rows = [r for r in rows if r.get("ok")]
    if not ok_rows:
        _render_health_table(rows, funds_extra=funds_extra)
        return

    # v19.330:① 健康分析 rows 提前建(核心/衛星 label 來源)—— 供「配置檢查」+ ① 表共用,不重算。
    _health_rows = [
        build_health_analysis_row(_r.get("_fund_raw") or {}, _r.get("code", ""))
        for _r in ok_rows
    ]

    # ── 🧭 核心/衛星配置檢查(依投入本金加權 vs 核心 50~80%)── v19.330:兩 tab 共用最上方 ──
    # 健檢 Tab 全檔本金 100 萬 = 等權(≈ 檔數佔比);組合 Tab3 為各檔實際 invest_twd 加權。
    try:
        from services.health.asset_class import summarize_core_satellite_allocation
        _cs_items = []
        for _hr, _r in zip(_health_rows, ok_rows):
            _lbl = (_hr.get("核心/衛星") or "").split()
            _cs_items.append({
                "label": _lbl[-1] if _lbl else "待定",
                "weight": _r.get("_principal_twd") or 0,
            })
        _csa = summarize_core_satellite_allocation(_cs_items)
        st.markdown("#### 🧭 核心 / 衛星配置檢查（建議：核心 50~80%）")
        _ca1, _ca2, _ca3, _ca4 = st.columns(4)
        _ca1.metric("🟦 核心", f"{_csa['core_pct']:.0f}%", f"{_csa['n_core']} 檔")
        _ca2.metric("🟠 衛星", f"{_csa['satellite_pct']:.0f}%", f"{_csa['n_satellite']} 檔")
        _ca3.metric("⬜ 待定", f"{_csa['undetermined_pct']:.0f}%", f"{_csa['n_undetermined']} 檔")
        _ca4.metric("配置評估", _csa["status"])
        st.caption(
            f"{_csa['status']} {_csa['message']}"
            f"（依各檔投入本金加權，總計 {_csa['total_weight']:,.0f} TWD；"
            f"核心=穩健長線 / 衛星=主題追報酬 / 待定=分類不足）"
        )
    except Exception as _e_csa:
        st.caption(f"⬜ 核心/衛星配置檢查失敗："
                   f"{type(_e_csa).__name__}: {str(_e_csa)[:80]}")

    # ── 🎯 選基金（低基期進場點）── v19.347：僅健檢 Tab 顯示(show_screener),
    #    Tab3 持倉健診不放(避免互動 widget key 與健檢 Tab 撞 + §8.1 不過度設計)。
    if show_screener:
        try:
            _render_low_base_screener(ok_rows)
        except Exception as _e_lb:
            st.caption(f"⬜ 選基金（低基期）渲染失敗："
                       f"{type(_e_lb).__name__}: {str(_e_lb)[:80]}")

    # ── 🔴 淘汰候選紅區(MK 4 規則 verdict=replace)── v19.315:提到最上面,一眼看見要換的 ──
    # 先建 ② 配息 rows(內含 _verdict),紅區與下方表 ② 共用同一份、不重算(SSOT,避免雙倍計算)。
    _div_rows = [
        build_dividend_summary_row(_r.get("_fund_raw") or {}, _r.get("code", ""),
                                   principal_twd=_r.get("_principal_twd"),
                                   fx=_r.get("fx_spot"))
        for _r in ok_rows
    ]
    _replace = [r for r in _div_rows if r.get("_verdict") == "replace"]
    if _replace:
        _lines = "\n".join(
            f"- **{r.get('code', '')}** "
            f"{str(r.get('基金名', '') or '')[:20]}："
            f"{r.get('_換標的 detail', '') or r.get('換標的建議', '')}"
            for r in _replace
        )
        st.error(
            f"### 🔴 淘汰候選 {len(_replace)} 檔（MK 4 規則觸發，建議換標的）\n\n"
            f"{_lines}\n\n"
            "↓ 完整指標見下方 ① 健康分析 / ② 配息相關表。"
        )

    # v19.411:① 健康分析表不再單獨渲染,欄位已併入「健診大表」。僅保留 _health_cfg(數值格式)
    # 供合併表 column_config 重用;數值 coerce 交由 build_unified_health_df 統一處理。
    from shared.signal_thresholds import (  # v19.419 捕捉率 help 文字用(SSOT,非 magic)
        CAPTURE_MIN_MONTHS as _CAP_MIN,
        CAPTURE_ROBUST_MONTHS as _CAP_ROB,
    )
    _health_cfg = {
        "code": _cc.TextColumn("代號", width="small"),
        "基金名": _cc.TextColumn("基金名", width="medium"),
        # v19.327:核心/衛星資產分類(類別 + MK 3-3-3 兩層,見「分類依據」欄)
        "基金類別": _cc.TextColumn("基金類別", width="small",
            help="MoneyDJ 投資標的 / 基金類型原始值(核心/衛星判定依據)"),
        "核心/衛星": _cc.TextColumn("核心/衛星", width="small",
            help="🟦 核心=廣泛分散/穩健長線(可重壓);🟠 衛星=集中/主題/高波動(小部位);"
                 "⬜ 待定=類別+3-3-3 皆無法判定"),
        "分類依據": _cc.TextColumn("分類依據", width="small",
            help="類別=依基金類型;3-3-3=通過 MK 3-3-3 達核心標準;—=資料不足"),
        "4D Grade": _cc.TextColumn("4D Grade", width="small",
            help="A≥80 / B≥65 / C≥50 / D≥35 / F<35(SSOT v19.177)"),
        "4D Score": _cc.NumberColumn("4D Score", format="%.1f", width="small"),
        "Sharpe 1Y": _cc.NumberColumn("Sharpe 1Y", format="%.2f",
            help="自計算（NAV序列，用於4D評分）；非MoneyDJ公布值"),
        "Sortino": _cc.NumberColumn("Sortino", format="%.2f"),
        "Calmar": _cc.NumberColumn("Calmar", format="%.2f"),
        "Alpha %": _cc.NumberColumn("真實收益 %", format="%.2f %%",
            help="含息報酬率 − 年化配息率（≠ CAPM Alpha）"),
        "費用率 %": _cc.NumberColumn("費用率 %", format="%.2f %%"),
        "Max DD %": _cc.NumberColumn("Max DD %", format="%.2f %%"),
        "3Y 年化 %": _cc.NumberColumn("3Y 年化 %", format="%.2f %%"),
        "5Y 年化 %": _cc.NumberColumn("5Y 年化 %", format="%.2f %%"),
        "MK 3-3-3": _cc.TextColumn("MK 3-3-3",
            help="成立 ≥ 3 年 + 過去 3 年平均年化 > 7% → 通過"),
        # v19.414 經理人操作能力;v19.419 放寬門檻 6→3(help 註明參考值,§1 誠實)
        "上檔捕捉%": _cc.NumberColumn("上檔捕捉%", format="%.1f %%",
            help=("大盤上漲月:基金複利 / 大盤複利 × 100(越高 = 越追得上漲)。"
                  f"需漲、跌月各 ≥ {_CAP_MIN} 才算;{_CAP_MIN}–{_CAP_ROB - 1} 月為參考值。")),
        "下檔捕捉%": _cc.NumberColumn("下檔捕捉%", format="%.1f %%",
            help="大盤下跌月:基金複利 / 大盤複利 × 100(越低 = 越抗跌)。"),
        "操盤評分": _cc.NumberColumn("操盤評分", format="%d",
            help=("經理人操作評分 clamp(50 +(上檔 − 下檔)/2, 0, 100)。"
                  f"需漲、跌月各 ≥ {_CAP_MIN};{_CAP_MIN}–{_CAP_ROB - 1} 月為參考值(低信心)。")),
        # v19.420 vs 大盤%(近1Y純價格報酬差;純淨值對純指數,公平不含息)
        "vs 大盤%": _cc.NumberColumn("vs 大盤%", format="%+.1f %%",
            help=("近 1 年**純價格**報酬 − 大盤(TWD→台股 / 其餘→S&P500)。"
                  "正 = 跑贏。純淨值對純指數(公平,兩邊都不含息);歷史不足 1 年 → 用全期。")),
        # v19.421 基期標籤(由 σ rank 分類,一眼挑高/低基期標的;門檻同輪動配對)
        "基期": _cc.TextColumn("基期", width="small",
            help=("現價 vs 期間高點的 σ 位階:🔴 高基期(σ ≥ −0.5,貼近高點、偏貴)/ "
                  "⚪ 中性 / 🟢 低基期(σ ≤ −1.5,跌深、可能均值回歸)/ ⬜ 資料不足。"
                  "可點欄排序,一次挑出所有高基期或低基期標的。")),
    }
    # v19.411:② 配息相關表不再單獨渲染,欄位併入健診大表;保留 _div_cfg 供格式重用。
    _div_cfg = {
        "code": _cc.TextColumn("代號", width="small"),
        "基金名": _cc.TextColumn("基金名", width="medium"),
        "1Y 含息 %": _cc.NumberColumn("1Y 含息 %", format="%.2f %%"),
        "1Y 來源": _cc.TextColumn("1Y 來源",
            help="wb01 / local_calc / ret_1y_total / NAV 年化"),
        "年化配息率 %": _cc.NumberColumn("年化配息率 %", format="%.2f %%"),
        # v19.326:每月配息金額(TWD 現金)= 最近一筆實配 × 持有單位 × 匯率(來源同「配息來源」欄)
        "每月配息 (TWD)": _cc.NumberColumn("每月配息 (TWD)", format="%.0f",
            help="每月實領台幣現金 = 最近一筆實際配息 × 持有單位 × 匯率。"
                 "健診 Tab 全檔以 100 萬 TWD 為基準;Tab3 為各檔實際投入本金。"),
        # v19.324:每月配息單位數 = 最近一筆實際配息 × 持有單位 / NAV(真實記錄優先)
        # v19.325:真實記錄缺 → 年化配息率估算 fallback,「配息來源」欄註記真實/估算
        "每月配息單位數": _cc.NumberColumn("每月配息單位數", format="%.2f",
            help="= 最近一筆實際配息(原幣/單位) × 持有單位 / NAV。"
                 "優先用 MoneyDJ 真實配息記錄;缺則以年化配息率估算(見「配息來源」欄)。"
                 "健診 Tab 全檔以 100 萬 TWD 為基準比較;Tab3 為各檔實際投入本金。"),
        "配息來源": _cc.TextColumn("配息來源", width="small",
            help="真實=最近一筆實際配息記錄;估算=年化配息率÷12 攤平(季配/年配某些月實際為 0)"),
        "吃本金燈號 (1Y·MK)": _cc.TextColumn("吃本金燈號 (1Y·MK)"),
        "換標的建議": _cc.TextColumn("換標的建議",
            help="MK 4 規則綜合判定(hover 看細節)"),
    }
    # v19.411:② 表 dataframe 移除(併入健診大表)。

    # ── 📊 健診大表(①②③ + σ/風險/MK 去重複合併成一張)── v19.411 ──
    st.markdown("#### 📊 健診大表（①②③ 已去重複合併成一張;橫向可滾動）")
    st.caption("原「① 健康分析 / ② 配息相關 / ③ 實際購買結果」三表已合併去重複。"
               "評分(4D Grade)/ 每月配息 / σ 位階 / MK 買賣點皆在此一張表內。")
    # ①② by-code 資料 + σ/風險/MK,全部傳給 _render_health_table 併成一張大表。
    _health_by_code = {str(r.get("code")): r for r in _health_rows if r.get("code")}
    _div_by_code = {str(r.get("code")): {k: v for k, v in r.items() if not str(k).startswith("_")}
                    for r in _div_rows if r.get("code")}
    _extra_by_code: dict = {}
    if funds_extra:
        try:
            from ui.helpers.fund_grp_health.unified import build_merged_extra_columns
            _pi3 = st.session_state.get("phase_info") if hasattr(st, "session_state") else None
            _, _extra_by_code = build_merged_extra_columns(
                funds_extra, (_pi3 or {}).get("phase") or "", (_pi3 or {}).get("score"))
        except Exception:  # noqa: BLE001 — σ/風險/MK 併入失敗不擋大表
            _extra_by_code = {}
    _render_health_table(rows, funds_extra=None,
                         health_by_code=_health_by_code,
                         div_by_code=_div_by_code,
                         extra_by_code=_extra_by_code,
                         extra_cfg={**_health_cfg, **_div_cfg})


def _render_health_table(rows: list[dict], funds_extra: list | None = None, *,
                         health_by_code: dict | None = None,
                         div_by_code: dict | None = None,
                         extra_by_code: dict | None = None,
                         extra_cfg: dict | None = None) -> None:
    if not rows:
        return
    import pandas as pd

    ok_rows = [r for r in rows if r.get("ok")]
    err_rows = [r for r in rows if not r.get("ok")]

    if ok_rows:
        # v19.61 E1：MoneyDJ 資料新鮮度 banner（NAV 日期 / 抓取於 / 延遲天數 / 燈號）
        # 鏡像 Stock v18.201 D2 「FinMind last_update」設計，但 Fund 端用 banner 而非 hover
        _render_mj_freshness_banner(ok_rows)

        # v19.148:SSOT 統一改用 MK 老師 1Y 標準(「吃本金燈號 (1Y · MK)」),
        # 與下方「健診摘要表」同源,不再與全期自算 verdict 不一致。
        _mk_col = "吃本金燈號 (1Y · MK)"
        n_eat = sum(1 for r in ok_rows if "吃本金" in str(r.get(_mk_col, "")))
        n_warn = sum(1 for r in ok_rows if ("警示" in str(r.get(_mk_col, ""))
                                            or "邊緣" in str(r.get(_mk_col, ""))))
        n_good = sum(1 for r in ok_rows if "健康" in str(r.get(_mk_col, "")))
        total_twd = sum(float(r.get("累積 TWD 配息 🧮", 0) or 0) for r in ok_rows)

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("檢查檔數", len(ok_rows))
        k2.metric("🟢 健康", n_good)
        k3.metric("🟡 警示", n_warn)
        k4.metric("🔴 吃本金", n_eat)
        k5.metric("累積 TWD 配息 🧮", f"{total_twd:,.0f}")

        df = pd.DataFrame([
            {k: v for k, v in r.items() if not k.startswith("_")}
            for r in ok_rows
        ])
        # v19.411:① 健康分析 + ② 配息相關 + ③ 本表 + σ/風險/MK「去重複合併」成一張大表
        # (user 2026-07-27 要求)。原 ①② 分散表移除,一律併入本表。相關性矩陣 / 真實收益圖 /
        # Bollinger / 持股維持獨立。缺欄留 None(§1 不偽造)。
        if health_by_code or div_by_code or extra_by_code:
            try:
                from ui.helpers.fund_grp_health.unified import build_unified_health_df
                df = build_unified_health_df(
                    df, health_by_code or {}, div_by_code or {}, extra_by_code or {})
            except Exception as _e_merge:  # noqa: BLE001 — 合併失敗不擋健診總表
                st.caption(f"⬜ ①②③ 合併大表失敗:"
                           f"[{type(_e_merge).__name__}] {str(_e_merge)[:80]}")
        # v19.189：逐檔財務健診（4 大功能 + 健診摘要表 PK + 健診卡）插在健診總表上方。
        # user 要求易讀的摘要 PK + 健診卡先看到（原在下方「進階分析」區塊）。
        if funds_extra:
            try:
                from ui.helpers.fund_checkup import render_fund_checkup
                # expanded=True：上移到健診總表之上後直接展開，避免 user 以為「沒有」。
                render_fund_checkup(funds_extra, expanded=True)
            except Exception as _e_chk:
                st.caption(
                    f"⬜ 基金體檢 PK 表渲染失敗：[{type(_e_chk).__name__}] "
                    f"{str(_e_chk)[:80]}"
                )

        st.markdown("#### 健診總表（🧮 = 自行換算欄位）")
        # v19.180:全期實際 / 年化兩軸並陳。短歷史也顯示真實累計值,不再 None。
        st.caption(
            "🩺 **吃本金燈號 (1Y · MK)** 採郭俊宏 MK 老師體檢邏輯:"
            "**近一年含息報酬 < 年化配息率 → 🔴 吃本金**(MoneyDJ wb05 官方數值)。"
            "「**(全期實際)**」欄為持有期累計真實值(不年化),短歷史也照顯示;"
            "「**(年化)**」欄需持有 ≥ 0.5 年才有數值(避免短歷史年化幻象)。"
            "兩欄皆**僅供歷史參考**,不參與燈號判定。"
            "📊 **長線挑核心資產**請另參 3-3-3 原則:成立 ≥ 3 年 + 3 年平均年化 > 7%。"
        )
        # v19.77 L1：column_config 數值格式化（百分號 / 千分位）+ 欄寬調整
        from streamlit import column_config as _cc
        _col_cfg = {
            "code": _cc.TextColumn("代號", width="small"),
            "基金名": _cc.TextColumn("基金名", width="medium"),
            "ccy": _cc.TextColumn("幣別", width="small"),
            "fx_spot": _cc.NumberColumn("FX", format="%.4f", width="small"),
            "principal_ccy 🧮": _cc.NumberColumn("原幣本金 🧮", format="%,.0f"),
            "units 🧮": _cc.NumberColumn("單位 🧮", format="%,.2f"),
            "配息次數": _cc.NumberColumn("配息次數", format="%d", width="small"),
            "累積 TWD 配息 🧮": _cc.NumberColumn("累積 TWD 配息 🧮", format="%,.0f"),
            "年均配息 TWD 🧮": _cc.NumberColumn("年均配息 TWD 🧮", format="%,.0f"),
            # v19.180:全期實際(不年化,短歷史也顯示真實累計值)
            "配息率% (全期實際)": _cc.NumberColumn(
                "配息率% (全期實際)", format="%.2f %%",
                help="自買進日起累積配息 / 本金 × 100(不年化)。短歷史也顯示真實累計。verdict 不採。"),
            "淨值% (全期實際)": _cc.NumberColumn(
                "淨值% (全期實際)", format="%.2f %%",
                help="自買進日起累積淨值漲跌幅(不年化)。短歷史也顯示真實累計。verdict 不採。"),
            "含息% (全期實際)": _cc.NumberColumn(
                "含息% (全期實際)", format="%.2f %%",
                help="全期實際淨值% + 全期實際配息%(不年化)。短歷史也顯示真實累計。verdict 不採。"),
            # v19.148/v19.180:年化 3 軸(< 0.5 年顯示 None,避免幻象);verdict 仍走 1Y MK SSOT
            "配息率% (年化)": _cc.NumberColumn(
                "配息率% (年化)", format="%.2f %%",
                help="(累積配息 / 本金 / 持有年數)× 100。需持有 ≥ 0.5 年。verdict 不採。"),
            "淨值% (年化)": _cc.NumberColumn(
                "淨值% (年化)", format="%.2f %%",
                help="累積淨值變化 / 持有年數。需持有 ≥ 0.5 年。verdict 不採。"),
            "含息% (年化)": _cc.NumberColumn(
                "含息% (年化)", format="%.2f %%",
                help="年化淨值% + 年化配息%。需持有 ≥ 0.5 年。verdict 不採。"),
            "吃本金燈號 (1Y · MK)": _cc.TextColumn(
                "吃本金燈號 (1Y · MK)",
                help="MK 老師 1Y 體檢:近一年含息報酬 vs MoneyDJ wb05 年化配息率。"
                     "與下方「健診摘要表」同源 SSOT。"),
            # v19.153:MK 3-3-3 原則(長線核心資產輔助)
            "MK 3-3-3 篩": _cc.TextColumn(
                "MK 3-3-3 篩",
                help="MK 老師 3-3-3 長線挑核心資產篩選:成立 ≥ 3 年 + 過去 3 年平均年化報酬 > 7%。"
                     "✅ 通過 / ❌ 未通過 / ⬜ 資料不足。3 年平均年化由 metrics.ret_3y(累計)"
                     "用 (1+R)^(1/3)-1 換算。本欄為長線輔助,非吃本金主判定。"),
        }
        # v19.411:合併表 column_config = ③ 本表 + ①② 傳入格式(extra_cfg)。
        _full_cfg = {**_col_cfg, **(extra_cfg or {})}
        st.dataframe(
            df, use_container_width=True, hide_index=True,
            column_config={k: v for k, v in _full_cfg.items() if k in df.columns},
        )

        # v19.69 J1：多基金績效比較圖
        if len(ok_rows) >= 2:
            try:
                import plotly.graph_objects as _go
                _codes = [r["code"] for r in ok_rows]
                # v19.190 fix + v19.194 merge reconcile：key 對齊 process_one_fund 實際輸出。
                # 並行線 v19.180 把欄位拆成「(全期實際)」+「(年化)」兩套。
                # v19.304 FIX（user 2026-07-04「多檔比較資料都是 0」根治）:
                #   年化欄在持有 < 0.5 年時依 dividend_calc.MIN_YEARS_FOR_ANNUALIZE guard
                #   一律為 None（防「短期配息 × 倍數」年化幻象，§1 Fail Loud）。同保單同期
                #   買進的多檔常整排短歷史 → 年化全 None → 圖表 float(None or 0) 畫成全 0 空圖。
                #   修法:全檔都有年化值才用「年化」(跨檔可比、原設計);任一檔短歷史 →
                #   全圖改用「全期實際」(100% 真實累計、永遠有值、不年化故無造假風險),
                #   基準統一避免同圖混基準,並在標題 / 圖例 / caption 明示當前基準。
                _basis = _pick_comparison_basis(ok_rows)
                _all_annual = _basis == "年化"
                _div_key = f"配息率% ({_basis})"
                _ret_key = f"含息% ({_basis})"
                _nav_key = f"淨值% ({_basis})"
                # v19.387 V1 §1:缺值保留 None → Plotly 該柱留缺口(誠實),不再 `or 0` 畫成
                # 與「真實 0%」無法區分的假柱。基準切換(v19.304)已解全 0,此處補單檔 None。
                _div_r  = [safe_num(r.get(_div_key)) for r in ok_rows]
                _ret_r  = [safe_num(r.get(_ret_key)) for r in ok_rows]
                _nav_r  = [safe_num(r.get(_nav_key)) for r in ok_rows]
                _fig = _go.Figure()
                _fig.add_trace(_go.Bar(x=_codes, y=_div_r, name=f"配息率%({_basis})🧮", marker_color="#f0883e"))
                _fig.add_trace(_go.Bar(x=_codes, y=_ret_r, name=f"含息%({_basis})🧮",  marker_color=TRAFFIC_GREEN))
                _fig.add_trace(_go.Bar(x=_codes, y=_nav_r, name=f"淨值%({_basis})🧮",  marker_color=INFO_BLUE))
                _fig.add_hline(y=0, line_dash="dot", line_color=GRAY_55)
                _fig.update_layout(
                    barmode="group",
                    title=f"📊 多基金績效比較 🧮（{_basis}:配息率 / 含息報酬 / 淨值漲跌）",
                    height=360,
                    paper_bgcolor=GH_BG_PRIMARY, plot_bgcolor=GH_BG_PRIMARY,
                    font=dict(color=GH_FG_SECONDARY),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                    margin=dict(l=20, r=20, t=70, b=20),
                    # v19.395 V3:3 序列分組長條 → unified hover,同基金三值一次讀
                    # (audit DEFECT-NOHOVER);原無 hovermode。
                    hovermode="x unified",
                )
                st.plotly_chart(_fig, use_container_width=True)
                if not _all_annual:
                    st.caption(
                        "ℹ️ 部分基金持有 < 0.5 年，年化值會失真（短期配息 × 倍數的幻象），"
                        "故本圖改以「全期實際」(持有期累計、未年化) 呈現真實數據，各檔基準一致。"
                    )
                # v19.77 L1：精簡比較表（對照圖看精確值，基準同上圖 v19.304）
                _cmp_df = pd.DataFrame([
                    {
                        "代號": r["code"],
                        "基金名": r.get("基金名", ""),
                        _ret_key: safe_num(r.get(_ret_key)),  # v19.387 §1:缺值 → 空格(NumberColumn),非 0
                        _div_key: safe_num(r.get(_div_key)),
                        _nav_key: safe_num(r.get(_nav_key)),
                    }
                    for r in ok_rows
                ])
                st.dataframe(
                    _cmp_df, use_container_width=True, hide_index=True,
                    column_config={
                        "代號": _cc.TextColumn("代號", width="small"),
                        "基金名": _cc.TextColumn("基金名", width="medium"),
                        _ret_key: _cc.NumberColumn(_ret_key, format="%.2f %%"),
                        _div_key: _cc.NumberColumn(_div_key, format="%.2f %%"),
                        _nav_key: _cc.NumberColumn(_nav_key, format="%.2f %%"),
                    },
                )
            except Exception as _e_chart:
                st.caption(f"⬜ 比較圖渲染失敗：{type(_e_chart).__name__}")

        # v19.77 L1：逐檔 expander → 兩張多檔合併表（持有 meta + 配息事件）
        st.markdown("#### 📋 逐檔配息明細 🧮")
        _meta_rows = []
        _ev_rows: list[dict] = []
        for r in ok_rows:
            detail = r.get("_detail", {}) or {}
            summary = detail.get("summary", {}) or {}
            _meta_rows.append({
                "代號": r["code"],
                "基金名": r.get("基金名", ""),
                "買進日": detail.get("buy_date"),
                "買進 NAV": detail.get("buy_nav"),
                "買進 FX": detail.get("buy_fx"),
                "FX 源": detail.get("buy_fx_source"),
                "原幣本金 🧮": detail.get("principal_ccy_🧮"),
                "持有單位 🧮": detail.get("units_held_🧮"),
                "末日": summary.get("last_date"),
                "末日 NAV": summary.get("last_nav"),
                "持有年數 🧮": summary.get("holding_years_🧮"),
            })
            for _ev in (detail.get("events") or []):
                if isinstance(_ev, dict):
                    _ev_rows.append({"代號": r["code"], **_ev})

        _meta_df = pd.DataFrame(_meta_rows)
        st.markdown("##### 持有 meta")
        st.dataframe(
            _meta_df, use_container_width=True, hide_index=True,
            column_config={
                "代號": _cc.TextColumn("代號", width="small"),
                "基金名": _cc.TextColumn("基金名", width="medium"),
                "買進 NAV": _cc.NumberColumn("買進 NAV", format="%.4f"),
                "買進 FX": _cc.NumberColumn("買進 FX", format="%.4f"),
                "原幣本金 🧮": _cc.NumberColumn("原幣本金 🧮", format="%,.0f"),
                "持有單位 🧮": _cc.NumberColumn("持有單位 🧮", format="%,.2f"),
                "末日 NAV": _cc.NumberColumn("末日 NAV", format="%.4f"),
                "持有年數 🧮": _cc.NumberColumn("持有年數 🧮", format="%.2f"),
            },
        )
        st.markdown("##### 配息事件（多檔合併）")
        if _ev_rows:
            st.dataframe(
                pd.DataFrame(_ev_rows),
                use_container_width=True, hide_index=True,
            )
        else:
            st.info("所有檔於買進日後皆無配息事件")

    if err_rows:
        st.markdown("#### ❌ 抓取失敗")
        for r in err_rows:
            st.error(f"{r['code']}: {r.get('error', '?')}")
