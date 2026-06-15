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

_MAX_CODES = 10
_DEFAULT_CCY = "USD"


def render_fund_grp_health_tab() -> None:
    """渲染 💊 基金組合健診 Tab（v19.37 新增）。"""
    st.markdown("### 💊 基金組合健診")
    st.caption(
        "對 **100 萬 TWD** 為基準，模擬持有期間每次配息折算 TWD 金額並判定吃本金。"
        "🧮 = 本系統自行換算（非 MoneyDJ/Cnyes 直給）。"
    )

    codes_raw = st.text_area(
        f"基金代號（每行一檔，最多 {_MAX_CODES} 檔；例：ACCP138）",
        key="fund_grp_health_codes",
        height=130,
        placeholder="ACCP138\nACUSI23\n...",
    )
    # v19.71：移除「原幣別 fallback」selectbox（user 要求）+ FX 失敗根因（中文「美元」未 normalize）
    # 已在 _process_one_fund 透過 services.currency.normalize_ccy 處理；fallback 永遠 USD（保單最常見）。
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

    codes = [c.strip().upper() for c in codes_raw.splitlines() if c.strip()]
    codes = codes[:_MAX_CODES]
    if not codes:
        st.warning("請至少輸入 1 個基金代號")
        return

    rows = _run_batch_health(codes, principal_twd, _DEFAULT_CCY, warn_gap)
    _render_health_table(rows)

    # v19.58 — 5 大貼圖區塊（基金體檢 PK + 健診卡 + 真實收益矩陣 + 投資試算 + 持股分析）
    try:
        from ui.helpers.fund_grp_health_extras import (
            _build_fund_dict,
            render_fund_grp_health_extras,
        )
        _funds_extra = [
            _build_fund_dict(r["_fund_raw"], r["code"], principal_twd)
            for r in rows
            if r.get("ok") and r.get("_fund_raw")
        ]
        if _funds_extra:
            render_fund_grp_health_extras(_funds_extra, principal_twd)
    except Exception as _e_extra:
        st.caption(
            f"⬜ 進階分析區塊渲染失敗：[{type(_e_extra).__name__}] "
            f"{str(_e_extra)[:80]}"
        )


def _auto_fetch_moneydj(code: str) -> dict:
    """鏡像 ui/tab2_single_fund._auto_fetch_moneydj：試 yp010000（境內）→ yp010001（境外）挑最佳結果。

    回 fetch_fund_from_moneydj_url 的 dict（含 series / dividends / currency / status）。
    支援保單體系內部代碼（如 ACCP138 / ALBT8）。
    """
    from fund_fetcher import classify_fetch_status, normalize_result_state
    from repositories.fund_repository import fetch_fund_from_moneydj_url

    raw = (code or "").strip().upper()
    if not raw:
        return {}
    attempts: list = []
    for page_type in ("yp010000", "yp010001"):
        url = f"https://www.moneydj.com/funddj/ya/{page_type}.djhtm?a={raw}"
        try:
            res = normalize_result_state(fetch_fund_from_moneydj_url(url))
        except Exception as e:
            attempts.append(({"error": f"{type(e).__name__}: {e}"}, False, "failed"))
            continue
        status = res.get("status", classify_fetch_status(res))
        ser = res.get("series")
        has_series = (
            ser is not None and hasattr(ser, "__len__") and len(ser) >= 10
        )
        if not res.get("error") and status == "complete":
            return res
        attempts.append((res, has_series, status))
    with_series = [t for t in attempts if t[1]]
    if with_series:
        return with_series[0][0]
    return attempts[-1][0] if attempts else {}


def _process_one_fund(
    code: str,
    principal_twd: float,
    ccy_hint: str,
    warn_gap: float,
) -> dict:
    """v19.68 H：單檔健診 worker（純 IO + 計算，無 st 呼叫 → 可並行）。

    回傳 row dict（與舊序列版完全一致）；任一步失敗回 {ok: False, error}。
    """
    from repositories.fund_repository import get_latest_fx
    from services.currency import normalize_ccy  # v19.71：single source of truth
    from services.fund_dividend_calculator import compute_dividend_twd_series
    try:
        fd = _auto_fetch_moneydj(code)
        if fd.get("error") and not fd.get("series"):
            return {"code": code, "ok": False, "error": fd.get("error", "?")}
        nav_s = fd.get("series")
        divs = fd.get("dividends") or []
        # v19.71 截圖 bug 修復：MoneyDJ 對部分基金（如 ACCP138）回傳中文「美元」而非 ISO「USD」，
        # 導致 get_latest_fx("美元TWD=X") 全鏈失敗。normalize_ccy 中文→ISO 正規化。
        ccy_auto = normalize_ccy(fd.get("currency"), default="")
        fund_name = fd.get("fund_name", "") or fd.get("full_key", "")
        if nav_s is None or len(nav_s) == 0:
            return {"code": code, "ok": False, "error": "NAV 抓不到"}
        nav_dict = {
            str(idx)[:10]: float(v)
            for idx, v in nav_s.items()
            if v == v  # NaN guard
        }
        ccy = ccy_auto if ccy_auto else normalize_ccy(ccy_hint)
        # TWD 基金不打 FX API（鏡像 tab2 v18.278 短路）
        if ccy == "TWD":
            fx = 1.0
        else:
            fx = get_latest_fx(f"{ccy}TWD=X") or 0.0
            if fx <= 0:
                return {"code": code, "ok": False, "error": f"FX {ccy}TWD 抓不到"}
        result = compute_dividend_twd_series(
            nav_series=nav_dict,
            dividend_events=divs,
            fx_rate_default=fx,
            principal_twd=principal_twd,
            warn_gap_pct=warn_gap,
        )
        if not result.get("ok"):
            return {"code": code, "ok": False, "error": result.get("error", "?")}
        s = result["summary"]
        # v19.69 J1：額外欄位（費用率 / 配息頻率 / 年均配息 / 換匯資訊）
        _mgmt_fee = (fd.get("mgmt_fee") or "").strip() or "—"
        _div_freq = (fd.get("dividend_freq") or "").strip() or "—"
        _hold_yrs = max(float(s.get("holding_years_🧮") or 1), 0.01)
        _ann_twd_div = round(s["total_twd_div_🧮"] / _hold_yrs, 0)
        _p_ccy = result["principal_ccy_🧮"]
        _buy_fx = result["buy_fx"]
        _buy_fx_info = f"1M TWD→{_p_ccy:,.0f} {ccy} @ {_buy_fx:.2f}"

        # v19.70 J2：MK 倉位（已有 fd.metrics）+ 1Y 快算吃本金（calc_health_from_manual）
        _metrics = fd.get("metrics") or {}
        _mk_pos = (_metrics.get("pos_label") or "—").strip() or "—"
        _snap_health = "⚪ 資料不足"
        try:
            _items_sorted = sorted(nav_dict.items())  # iso 日期升冪
            if len(_items_sorted) >= 2:
                _last_d, _last_v = _items_sorted[-1]
                _yr_ago = (_last_d[:4] + "-01-01") if len(_last_d) >= 10 else ""
                _target_d = (
                    f"{int(_last_d[:4]) - 1}{_last_d[4:10]}"
                    if len(_last_d) >= 10 else ""
                )
                _below_1y = [
                    v for d, v in _items_sorted if d <= _target_d
                ] if _target_d else []
                _nav_1y_ago = _below_1y[-1] if _below_1y else _items_sorted[0][1]
                _freq_map = {"月配": 12, "季配": 4, "半年": 2, "年配": 1}
                _freq_n = next(
                    (n for k, n in _freq_map.items() if k in _div_freq), 12
                )
                _div_amt = float((divs[0] if divs else {}).get("amount") or 0)
                if _last_v > 0 and _nav_1y_ago > 0 and _div_amt > 0:
                    from services.fund_service import calc_health_from_manual
                    _hm = calc_health_from_manual(
                        nav_current=_last_v, nav_1y_ago=_nav_1y_ago,
                        div_per_unit=_div_amt, div_freq=_freq_n,
                    )
                    if not _hm.get("error"):
                        _snap_health = _hm.get("health", "⚪ 資料不足")
        except Exception:
            pass

        return {
            "code": code,
            "ok": True,
            "基金名": fund_name[:24],
            "幣別偵測": "自動" if ccy_auto else "fallback",
            "ccy": ccy,
            "fx_spot": fx,
            "principal_ccy 🧮": result["principal_ccy_🧮"],
            "units 🧮": result["units_held_🧮"],
            "配息次數": result["n_events"],
            "累積 TWD 配息 🧮": s["total_twd_div_🧮"],
            "年均配息 TWD 🧮": _ann_twd_div,
            "年化配息率% 🧮": s["annual_div_rate_pct_🧮"],
            "年化淨值% 🧮": s["annual_nav_return_pct_🧮"],
            "含息年化% 🧮": s["ret_1y_total_pct_🧮"],
            "燈號（全期 🧮）": f"{s['div_health_emoji_🧮']} {s['div_health_light_🧮']}",
            "快算燈號（1Y）": _snap_health,
            "MK 倉位": _mk_pos,
            "最高經理費%": _mgmt_fee,
            "配息頻率": _div_freq,
            "換匯資訊 🧮": _buy_fx_info,
            "_detail": result,
            "_fund_raw": fd,  # v19.58：留給 render_fund_grp_health_extras
            # v19.61 E1：MoneyDJ 資料新鮮度（_ 開頭自動排除表格）
            "_nav_date": str(fd.get("nav_date") or "")[:10],
            "_fetched_at": str(fd.get("_moneydj_fetched_at") or ""),
        }
    except Exception as e:
        return {"code": code, "ok": False, "error": f"{type(e).__name__}: {e}"}


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
                _ex.submit(_process_one_fund, _c, principal_twd, ccy_hint, warn_gap): _i
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


def _render_health_table(rows: list[dict]) -> None:
    if not rows:
        return
    import pandas as pd

    ok_rows = [r for r in rows if r.get("ok")]
    err_rows = [r for r in rows if not r.get("ok")]

    if ok_rows:
        # v19.61 E1：MoneyDJ 資料新鮮度 banner（NAV 日期 / 抓取於 / 延遲天數 / 燈號）
        # 鏡像 Stock v18.201 D2 「FinMind last_update」設計，但 Fund 端用 banner 而非 hover
        _render_mj_freshness_banner(ok_rows)

        n_eat = sum(1 for r in ok_rows if "吃本金" in str(r.get("燈號（全期 🧮）", "")))
        n_warn = sum(1 for r in ok_rows if "警示" in str(r.get("燈號（全期 🧮）", "")))
        n_good = sum(1 for r in ok_rows if "健康" in str(r.get("燈號（全期 🧮）", "")))
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
        st.markdown("#### 健診總表（🧮 = 自行換算欄位）")
        st.dataframe(df, use_container_width=True, hide_index=True)

        # v19.69 J1：多基金績效比較圖
        if len(ok_rows) >= 2:
            try:
                import plotly.graph_objects as _go
                _codes = [r["code"] for r in ok_rows]
                _div_r  = [float(r.get("年化配息率% 🧮") or 0) for r in ok_rows]
                _ret_r  = [float(r.get("含息年化% 🧮") or 0) for r in ok_rows]
                _nav_r  = [float(r.get("年化淨值% 🧮") or 0) for r in ok_rows]
                _fig = _go.Figure()
                _fig.add_trace(_go.Bar(x=_codes, y=_div_r, name="年化配息率%🧮", marker_color="#f0883e"))
                _fig.add_trace(_go.Bar(x=_codes, y=_ret_r, name="含息年化%🧮",  marker_color="#3fb950"))
                _fig.add_trace(_go.Bar(x=_codes, y=_nav_r, name="年化淨值%🧮",  marker_color="#58a6ff"))
                _fig.add_hline(y=0, line_dash="dot", line_color="#555")
                _fig.update_layout(
                    barmode="group",
                    title="📊 多基金績效比較 🧮（配息率 / 含息報酬 / 淨值漲跌）",
                    height=360,
                    paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                    font=dict(color="#c9d1d9"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                    margin=dict(l=20, r=20, t=70, b=20),
                )
                st.plotly_chart(_fig, use_container_width=True)
            except Exception as _e_chart:
                st.caption(f"⬜ 比較圖渲染失敗：{type(_e_chart).__name__}")

        for r in ok_rows:
            with st.expander(f"📋 {r['code']} — 逐期配息明細 🧮"):
                detail = r.get("_detail", {})
                meta = {
                    "買進日": detail.get("buy_date"),
                    "買進 NAV": detail.get("buy_nav"),
                    "買進 FX": f"{detail.get('buy_fx')} ({detail.get('buy_fx_source')})",
                    "原幣本金 🧮": detail.get("principal_ccy_🧮"),
                    "持有單位 🧮": detail.get("units_held_🧮"),
                    "末日": detail.get("summary", {}).get("last_date"),
                    "末日 NAV": detail.get("summary", {}).get("last_nav"),
                    "持有年數 🧮": detail.get("summary", {}).get("holding_years_🧮"),
                }
                st.json(meta, expanded=False)
                ev = detail.get("events", [])
                if ev:
                    st.dataframe(pd.DataFrame(ev), use_container_width=True, hide_index=True)
                else:
                    st.info("此檔於買進日後無配息事件")

    if err_rows:
        st.markdown("#### ❌ 抓取失敗")
        for r in err_rows:
            st.error(f"{r['code']}: {r.get('error', '?')}")
