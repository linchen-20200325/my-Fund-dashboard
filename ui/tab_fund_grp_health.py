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
    c1, c2, c3 = st.columns(3)
    with c1:
        principal_twd = st.number_input(
            "本金（TWD）",
            min_value=10_000.0, max_value=10_000_000.0,
            value=1_000_000.0, step=100_000.0,
            key="fund_grp_health_principal",
        )
    with c2:
        ccy_hint = st.selectbox(
            "原幣別 fallback",
            options=["USD", "EUR", "ZAR", "AUD", "JPY", "GBP", "CNY", "HKD"],
            index=0,
            key="fund_grp_health_ccy",
            help="若無法自動偵測基金幣別則用此 fallback；FX 抓 {CCY}TWD=X 即時",
        )
    with c3:
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

    rows = _run_batch_health(codes, principal_twd, ccy_hint, warn_gap)
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


def _run_batch_health(
    codes: list[str],
    principal_twd: float,
    ccy_hint: str,
    warn_gap: float,
) -> list[dict]:
    from repositories.fund_repository import get_latest_fx
    from services.fund_dividend_calculator import compute_dividend_twd_series

    rows: list[dict] = []
    prog = st.progress(0.0, text="📥 抓取資料中…")
    n = len(codes)
    for i, code in enumerate(codes):
        prog.progress((i) / n, text=f"📥 {code} ({i + 1}/{n})")
        try:
            fd = _auto_fetch_moneydj(code)
            if fd.get("error") and not fd.get("series"):
                rows.append({"code": code, "ok": False, "error": fd.get("error", "?")})
                continue
            nav_s = fd.get("series")
            divs = fd.get("dividends") or []
            ccy_auto = (fd.get("currency") or "").strip().upper()
            fund_name = fd.get("fund_name", "") or fd.get("full_key", "")
            if nav_s is None or len(nav_s) == 0:
                rows.append({"code": code, "ok": False, "error": "NAV 抓不到"})
                continue
            nav_dict = {
                str(idx)[:10]: float(v)
                for idx, v in nav_s.items()
                if v == v  # NaN guard
            }
            ccy = ccy_auto if ccy_auto else ccy_hint
            fx = get_latest_fx(f"{ccy}TWD=X") or 0.0
            if fx <= 0:
                rows.append({"code": code, "ok": False, "error": f"FX {ccy}TWD 抓不到"})
                continue
            result = compute_dividend_twd_series(
                nav_series=nav_dict,
                dividend_events=divs,
                fx_rate_default=fx,
                principal_twd=principal_twd,
                warn_gap_pct=warn_gap,
            )
            if not result.get("ok"):
                rows.append({"code": code, "ok": False, "error": result.get("error", "?")})
            else:
                s = result["summary"]
                rows.append({
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
                    "年化配息率% 🧮": s["annual_div_rate_pct_🧮"],
                    "含息年化% 🧮": s["ret_1y_total_pct_🧮"],
                    "燈號 🧮": f"{s['div_health_emoji_🧮']} {s['div_health_light_🧮']}",
                    "_detail": result,
                    "_fund_raw": fd,  # v19.58：留給 render_fund_grp_health_extras
                    # v19.61 E1：MoneyDJ 資料新鮮度（_ 開頭自動排除表格）
                    "_nav_date": str(fd.get("nav_date") or "")[:10],
                    "_fetched_at": str(fd.get("_moneydj_fetched_at") or ""),
                })
        except Exception as e:
            rows.append({"code": code, "ok": False, "error": f"{type(e).__name__}: {e}"})
        prog.progress((i + 1) / n, text=f"✅ {code} 完成")
    prog.empty()
    return rows


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

        n_eat = sum(1 for r in ok_rows if "吃本金" in str(r.get("燈號 🧮", "")))
        n_warn = sum(1 for r in ok_rows if "警示" in str(r.get("燈號 🧮", "")))
        n_good = sum(1 for r in ok_rows if "健康" in str(r.get("燈號 🧮", "")))
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
