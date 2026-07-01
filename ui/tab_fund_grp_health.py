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

    codes = [c.strip().upper() for c in codes_raw.splitlines() if c.strip()]
    codes = codes[:_MAX_CODES]
    if not codes:
        st.warning("請至少輸入 1 個基金代號")
        return

    rows = _run_batch_health(codes, principal_twd, "", warn_gap)

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
    _render_health_3tables(rows, funds_extra=_funds_extra)

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


# v19.76 K3：原 32 行 _auto_fetch_moneydj 已遷移至 services.moneydj_fetcher，
# tab2/tab5 共用同一份 fallback chain（避免兩 Tab 對同檔基金路徑不一致）。
from services.moneydj_fetcher import auto_fetch_moneydj as _auto_fetch_moneydj  # noqa: F401


def process_one_fund(
    code: str,
    principal_twd: float,
    ccy_hint: str,
    warn_gap: float,
    fd: dict | None = None,
) -> dict:
    """v19.68 H：單檔健診 worker（純 IO + 計算，無 st 呼叫 → 可並行）。

    Args:
        code: 基金代號(MoneyDJ)
        principal_twd: 本金 TWD(per-fund;Tab3 用 user 實際 invest_twd,健診 Tab 統一 100 萬)
        ccy_hint: legacy hint(v19.59 後不再使用,留簽名相容)
        warn_gap: 配息率超出含息報酬率多少 → 警示燈
        fd: v19.180 新增 — 預先抓好的 fd(`auto_fetch_moneydj` 結果)。
            若 None → 本函式呼叫 `_auto_fetch_moneydj(code)`;
            若有 → 跳過 fetch 直接用(Tab3 從 portfolio_funds 已存的 moneydj_raw 傳入,免重抓 2-30s)。

    回傳 row dict（與舊序列版完全一致）；任一步失敗回 {ok: False, error}。
    """
    from services.fund_service import get_latest_fx
    from services.currency import normalize_ccy  # v19.71：single source of truth
    from services.health.dividend_calc import compute_dividend_twd_series
    try:
        if fd is None:
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
        # v19.59：移除人工 fallback。MoneyDJ 抓不到「計價幣別」→ 該檔直接 error，不矇 USD。
        ccy = ccy_auto
        if not ccy:
            return {"code": code, "ok": False,
                    "error": "幣別未知（MoneyDJ wb05 未提供「計價幣別」欄）"}
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
        # v19.176：配息頻率走 metrics.div_freq_n SSOT(fund_service.calc_metrics:450-464
        # auto-detect 結果),不再用 fd["dividend_freq"] MoneyDJ 原文。
        # 修「健診總表顯示『月配息』、Tab2 顯示『12』」跨 Tab 不一致。
        # 將數字轉回中文 label + 數字並陳:「月配息(12 次/年)」便於閱讀。
        _div_freq_n = (fd.get("metrics") or {}).get("div_freq_n")
        if _div_freq_n in (12, 4, 2, 1):
            _div_freq_label = {12: "月配息", 4: "季配息", 2: "半年配", 1: "年配"}[_div_freq_n]
            _div_freq = f"{_div_freq_label}({_div_freq_n} 次/年)"
        else:
            # fallback:auto-detect 失敗 → 顯示 MoneyDJ 原文(無數字)
            _div_freq = (fd.get("dividend_freq") or "").strip() or "—"
        _hold_yrs = max(float(s.get("holding_years_🧮") or 1), 0.01)
        _ann_twd_div = round(s["total_twd_div_🧮"] / _hold_yrs, 0)
        _p_ccy = result["principal_ccy_🧮"]
        _buy_fx = result["buy_fx"]
        _buy_fx_info = f"1M TWD→{_p_ccy:,.0f} {ccy} @ {_buy_fx:.2f}"

        # v19.148 — MK 老師 1Y SSOT 吃本金檢查(取代 v19.70 J2 calc_health_from_manual 自算路徑)
        # 同源 ui/helpers/fund_checkup.py 第 2 表「健診摘要表」,確保跨表 verdict 一致。
        # 方法論:近一年含息報酬率 vs MoneyDJ wb05 年化配息率(MK 老師體檢邏輯)。
        _metrics = fd.get("metrics") or {}
        _mk_pos = (_metrics.get("pos_label") or "—").strip() or "—"
        _mk_safety = None
        try:
            from services.health.dividend import check_eating_principal_1y_mk
            _mk_safety = check_eating_principal_1y_mk(fd)
        except Exception:
            _mk_safety = None
        if _mk_safety is None:
            _snap_health = "⚪ 資料不足"
        else:
            _snap_health = _mk_safety.get("status", "⚪ 資料不足")

        # v19.153:MK 老師 3-3-3 原則(長線挑核心資產輔助)
        # 成立 ≥ 3 年 + 3 年平均年化 > 7% → 通過
        _333_emoji = "⬜"
        _333_msg = "資料不足"
        try:
            from services.health.dividend import check_333_principle
            # 成立年數:從 NAV 序列首日到今天
            import datetime as _dt333
            _yrs_inc = None
            try:
                _first_iso = sorted(nav_dict.keys())[0]
                _first_d = _dt333.date.fromisoformat(str(_first_iso)[:10])
                _yrs_inc = (_dt333.date.today() - _first_d).days / 365.25
                # v19.292 FIX: 鏡像 _compute_holding_years guard —
                # series < 90 筆且年數 < 0.5 → 太短，無法可信估算成立日
                if len(nav_dict) < 90 and _yrs_inc < 0.5:
                    _yrs_inc = None
            except (ValueError, IndexError, TypeError):
                _yrs_inc = None
            # v19.177:metrics.ret_3y_ann 為 fund_service 統一計算的 3 年年化 SSOT
            # (cum→ann 開根公式集中於 fund_service.calc_metrics _annualize_cum_pct)。
            # 舊版 metrics 無 _ann 欄位時 fallback 自算,免破壞向後相容。
            _ann_3y = _metrics.get("ret_3y_ann")
            if _ann_3y is None:
                _ret_3y_cum = _metrics.get("ret_3y_cum") or _metrics.get("ret_3y")
                try:
                    if _ret_3y_cum is not None:
                        _cum = float(_ret_3y_cum) / 100.0
                        _ann_3y = ((1.0 + _cum) ** (1.0 / 3.0) - 1.0) * 100.0
                except (TypeError, ValueError):
                    _ann_3y = None
            _333_r = check_333_principle(_yrs_inc, _ann_3y)
            if _333_r.get("passed") is True:
                _333_emoji = "✅"
            elif _333_r.get("passed") is False:
                _333_emoji = "❌"
            _333_msg = _333_r.get("message", "")
        except Exception:
            pass
        _333_status = f"{_333_emoji} {_333_msg[:32]}" if _333_msg else _333_emoji

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
            # v19.180:三軸並陳 — 全期實際(永遠有值)+ 年化(< 0.5 年 None)。
            # 修截圖反饋「配息率% / 淨值% / 含息% (全期自算) 全 None」— 短歷史 user 仍想看
            # 「實際持有累計多少」(100% 真實數據,不年化故無 §1 Fail Loud 風險)。
            # 年化欄保留供 ≥ 0.5 年的長線觀察,verdict 仍走 1Y MK SSOT 不受影響。
            "配息率% (全期實際)": s["cum_div_rate_pct_🧮"],
            "淨值% (全期實際)": s["cum_nav_return_pct_🧮"],
            "含息% (全期實際)": s["cum_total_return_pct_🧮"],
            "配息率% (年化)": s["annual_div_rate_pct_🧮"],
            "淨值% (年化)": s["annual_nav_return_pct_🧮"],
            "含息% (年化)": s["ret_1y_total_pct_🧮"],
            # v19.148:單一 SSOT verdict(MK 老師 1Y 體檢標準,跨 tab 一致)
            "吃本金燈號 (1Y · MK)": _snap_health,
            # v19.153:MK 3-3-3 原則(長線核心資產篩選輔助 — 成立 ≥ 3 年 + 3 年平均年化 > 7%)
            "MK 3-3-3 篩": _333_status,
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


# v19.180:backward-compat alias(舊呼叫者 / 測試直接 import 老名)
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


def _render_health_3tables(rows: list[dict],
                           funds_extra: list | None = None) -> None:
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
    import pandas as pd
    from streamlit import column_config as _cc
    from services.health.report import (
        DIVIDEND_COLUMNS,
        HEALTH_COLUMNS,
        build_dividend_summary_row,
        build_health_analysis_row,
    )

    ok_rows = [r for r in rows if r.get("ok")]
    if not ok_rows:
        _render_health_table(rows, funds_extra=funds_extra)
        return

    # ── 表 ① 健康分析(4D Grade + 6 進階指標 + 3-3-3)──────────────
    st.markdown("#### 🩺 ① 健康分析表（4D Grade + 6 進階指標 + MK 3-3-3）")
    st.caption(
        "**4D Grade** 為基金健康度評等 SSOT(配息覆蓋 / Sharpe / 走勢 / 低波動 4 維)。"
        "Sortino / Calmar / Alpha / 費用率為進階指標(無評等,僅供對照)。"
        "Max DD / 3Y/5Y 年化 / 3-3-3 篩為長線挑核心資產輔助。"
    )
    _health_rows = []
    for _r in ok_rows:
        _fd = _r.get("_fund_raw") or {}
        _code = _r.get("code", "")
        _health_rows.append(build_health_analysis_row(_fd, _code))
    _health_df = pd.DataFrame(_health_rows)
    # v19.191:None → NaN for numeric cols(pandas object dtype 會顯示「None」字面值,
    # NaN 走 NumberColumn format 後顯示「—」/ 空白)。caller 拿 dict → DataFrame 默認 object
    # dtype,需顯式 to_numeric 轉。
    _health_num_cols = ["4D Score", "Sharpe 1Y", "Sortino", "Calmar",
                        "Alpha %", "費用率 %", "Max DD %",
                        "3Y 年化 %", "5Y 年化 %"]
    for _nc in _health_num_cols:
        if _nc in _health_df.columns:
            _health_df[_nc] = pd.to_numeric(_health_df[_nc], errors="coerce")
    _health_cfg = {
        "code": _cc.TextColumn("代號", width="small"),
        "基金名": _cc.TextColumn("基金名", width="medium"),
        "4D Grade": _cc.TextColumn("4D Grade", width="small",
            help="A≥80 / B≥65 / C≥50 / D≥35 / F<35(SSOT v19.177)"),
        "4D Score": _cc.NumberColumn("4D Score", format="%.1f", width="small"),
        "Sharpe 1Y": _cc.NumberColumn("Sharpe 1Y", format="%.2f"),
        "Sortino": _cc.NumberColumn("Sortino", format="%.2f"),
        "Calmar": _cc.NumberColumn("Calmar", format="%.2f"),
        "Alpha %": _cc.NumberColumn("Alpha %", format="%.2f %%",
            help="1Y 含息報酬 − 年化配息率(真實收益,非貨幣 Alpha)"),
        "費用率 %": _cc.NumberColumn("費用率 %", format="%.2f %%"),
        "Max DD %": _cc.NumberColumn("Max DD %", format="%.2f %%"),
        "3Y 年化 %": _cc.NumberColumn("3Y 年化 %", format="%.2f %%"),
        "5Y 年化 %": _cc.NumberColumn("5Y 年化 %", format="%.2f %%"),
        "MK 3-3-3": _cc.TextColumn("MK 3-3-3",
            help="成立 ≥ 3 年 + 過去 3 年平均年化 > 7% → 通過"),
    }
    st.dataframe(
        _health_df[HEALTH_COLUMNS], use_container_width=True, hide_index=True,
        column_config={k: v for k, v in _health_cfg.items() if k in _health_df.columns},
    )

    # ── 表 ② 配息相關(adr + 1Y 含息 + 吃本金 + 換標的建議)─────
    st.markdown("#### 💰 ② 配息相關表（含吃本金燈號 + MK 換標的建議）")
    st.caption(
        "**吃本金燈號 (1Y·MK)** 採郭俊宏老師 1Y 體檢:近一年含息報酬 < 年化配息率 → 🔴 吃本金。"
        "**換標的建議**走 MK 4 規則心型警結合:"
        "(a) 吃本金且持有 ≥ 1 年 / (b) 4D Grade F / "
        "(c) 3-3-3 未通過且持有 ≥ 3 年 / (d) Sharpe<0 且 max_dd<-30%。"
        "任一中 → 🔴 換 / 1-2 觀察 → 🟡 / 全未中 → 🟢。"
    )
    _div_rows = []
    for _r in ok_rows:
        _fd = _r.get("_fund_raw") or {}
        _code = _r.get("code", "")
        _div_rows.append(
            build_dividend_summary_row(_fd, _code, principal_twd=None)
        )
    _div_df = pd.DataFrame(_div_rows)
    # v19.191:None → NaN for numeric cols(同 ① 表 None → NaN 邏輯)
    _div_num_cols = ["1Y 含息 %", "年化配息率 %"]
    for _nc in _div_num_cols:
        if _nc in _div_df.columns:
            _div_df[_nc] = pd.to_numeric(_div_df[_nc], errors="coerce")
    _div_cfg = {
        "code": _cc.TextColumn("代號", width="small"),
        "基金名": _cc.TextColumn("基金名", width="medium"),
        "1Y 含息 %": _cc.NumberColumn("1Y 含息 %", format="%.2f %%"),
        "1Y 來源": _cc.TextColumn("1Y 來源",
            help="wb01 / local_calc / ret_1y_total / NAV 年化"),
        "年化配息率 %": _cc.NumberColumn("年化配息率 %", format="%.2f %%"),
        "吃本金燈號 (1Y·MK)": _cc.TextColumn("吃本金燈號 (1Y·MK)"),
        "換標的建議": _cc.TextColumn("換標的建議",
            help="MK 4 規則綜合判定(hover 看細節)"),
    }
    st.dataframe(
        _div_df[DIVIDEND_COLUMNS], use_container_width=True, hide_index=True,
        column_config={k: v for k, v in _div_cfg.items() if k in _div_df.columns},
    )

    # ── 表 ③ 實際購買配息結果(既有大表 — 不動,只改 section title)──
    st.markdown("#### 📦 ③ 實際購買配息結果（持有 meta + 累積 TWD 配息 + 全期實際/年化）")
    # v19.292 FIX: funds_extra=None → 不在此重複渲染 PK体检表 + 健診摘要表
    # (表 ① ② 已涵蓋健康分析資訊;PK 體檢由外層 render_fund_grp_health_extras 統一提供)
    _render_health_table(rows, funds_extra=None)


def _render_health_table(rows: list[dict], funds_extra: list | None = None) -> None:
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
        st.dataframe(
            df, use_container_width=True, hide_index=True,
            column_config={k: v for k, v in _col_cfg.items() if k in df.columns},
        )

        # v19.69 J1：多基金績效比較圖
        if len(ok_rows) >= 2:
            try:
                import plotly.graph_objects as _go
                _codes = [r["code"] for r in ok_rows]
                # v19.190 fix + v19.194 merge reconcile：key 對齊 process_one_fund 實際輸出。
                # 並行線 v19.180 把欄位拆成「(全期實際)」+「(年化)」兩套；圖表取**年化**
                # （= 原 annual_*_pct_🧮，跨檔可比）。舊鍵「年化…% 🧮」已不存在，不可再讀。
                _div_r  = [float(r.get("配息率% (年化)") or 0) for r in ok_rows]
                _ret_r  = [float(r.get("含息% (年化)") or 0) for r in ok_rows]
                _nav_r  = [float(r.get("淨值% (年化)") or 0) for r in ok_rows]
                _fig = _go.Figure()
                _fig.add_trace(_go.Bar(x=_codes, y=_div_r, name="配息率%(年化)🧮", marker_color="#f0883e"))
                _fig.add_trace(_go.Bar(x=_codes, y=_ret_r, name="含息%(年化)🧮",  marker_color=TRAFFIC_GREEN))
                _fig.add_trace(_go.Bar(x=_codes, y=_nav_r, name="淨值%(年化)🧮",  marker_color=INFO_BLUE))
                _fig.add_hline(y=0, line_dash="dot", line_color=GRAY_55)
                _fig.update_layout(
                    barmode="group",
                    title="📊 多基金績效比較 🧮（配息率 / 含息報酬 / 淨值漲跌）",
                    height=360,
                    paper_bgcolor=GH_BG_PRIMARY, plot_bgcolor=GH_BG_PRIMARY,
                    font=dict(color=GH_FG_SECONDARY),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                    margin=dict(l=20, r=20, t=70, b=20),
                )
                st.plotly_chart(_fig, use_container_width=True)
                # v19.77 L1：精簡比較表（對照圖看精確值）
                _cmp_df = pd.DataFrame([
                    {
                        "代號": r["code"],
                        "基金名": r.get("基金名", ""),
                        "含息% (年化)": float(r.get("含息% (年化)") or 0),
                        "配息率% (年化)": float(r.get("配息率% (年化)") or 0),
                        "淨值% (年化)": float(r.get("淨值% (年化)") or 0),
                    }
                    for r in ok_rows
                ])
                st.dataframe(
                    _cmp_df, use_container_width=True, hide_index=True,
                    column_config={
                        "代號": _cc.TextColumn("代號", width="small"),
                        "基金名": _cc.TextColumn("基金名", width="medium"),
                        "含息% (年化)": _cc.NumberColumn("含息% (年化)", format="%.2f %%"),
                        "配息率% (年化)": _cc.NumberColumn("配息率% (年化)", format="%.2f %%"),
                        "淨值% (年化)": _cc.NumberColumn("淨值% (年化)", format="%.2f %%"),
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
