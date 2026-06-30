"""v18.213：基金體檢表（郭老師「挑三揀四」PK 同類型）。

把每檔基金的含息報酬與 MoneyDJ「同類型平均」PK，
打敗同類＝🏆 優等生（抱緊）；明顯落後＝⚠️ 汰弱候選。

資料邊界（誠實告知，呼應 CLAUDE.md §4）：
  - 同類平均取自 MoneyDJ 績效評比頁 risk_metrics.peer_compare，約 3 成基金抓不到 → 標 ⬜ 不評。
  - 郭老師另兩項標準（成分股 ROE>15%/EPS 成長、規模流動性）資料源無法取得 → 不納入。
  - 買賣點（標準差／布林）沿用 MK 戰情室既算欄位，僅在本表附「買點」燈號。
純函式 + 單一 render，無 @st.cache_data（STATE.md 鐵律）。
"""
from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from shared.colors import BG_DARK_AMBER_1, BG_DARK_GREEN_1, BG_DARK_RED_1, GH_BG_CARD, GH_BORDER, GH_FG_PRIMARY, MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED, TRAFFIC_NEUTRAL

# v19.245 R13:`dividend_safety` 已於 v19.150 由 SSOT `check_eating_principal_1y_mk`
# 取代(下方 _compute_fund_health_kpis line 166 動態 import),原 `div_safety_check`
# 為 dead import 0 caller。
from ui.components.mk_dashboard import tag_price_zone

# v19.54：TER 同類均值（沿用 tab2_single_fund L1004-1009 既有對照表，台灣基金市場常見估值）
_TER_AVG_MAP = {
    "股票": 1.50, "全球股票": 1.50, "科技": 1.60,
    "亞太": 1.60, "新興市場": 1.70, "高收益": 1.00,
    "債券": 0.80, "全球債券": 0.80, "投資等級": 0.80,
    "平衡": 1.20, "貨幣": 0.30,
}

_DISPLAY_COLS = [
    "代碼", "標的名稱",
    "近1M(%)", "近3M(%)", "近6M(%)", "近1Y含息(%)",
    "同類平均(1Y%)", "超額(pp)",
    "夏普值", "年化波動(1Y%)",
    # v19.59：從逐檔深度分析「投資試算」card 上抽 5 欄到上方比較表（同源公式）
    "計價幣別", "NAV(原幣)", "即時匯率(FX)",
    "可申購單位數", "月配股(單位)",
    "每月100萬配息(TWD)",
    # v19.60：投資試算完整 SSOT — 補實際本金 invest_twd 的 3 欄（原幣本金 / 月配 / 年配）
    "原幣本金🧮(本金)", "月配息🧮(本金TWD)", "年配息🧮(本金TWD)",
    "買點", "體檢判定",
]

_ZONE_LABEL = {
    "Buy_Zone_Deep": "🟢🟢 超跌(-2σ)",
    "Buy_Zone": "🟢 便宜(-1σ)",
    "Take_Profit": "🟠 停利(+2σ)",
    "Hold": "—",
    "N/A": "—",
}

# 超額報酬（pp）分級門檻：打敗同類 ≥ +2 為優等生、落後 ≤ −2 為汰弱候選。
_EXCESS_GOOD = 2.0
_EXCESS_LAG = -2.0


def _norm_ccy(raw: str, default: str = "", mode: str = "yf") -> str:
    """v19.59：lazy import services.currency.normalize_ccy 避 module load time 成本。"""
    from services.currency import normalize_ccy
    return normalize_ccy(raw, default=default, mode=mode)


def _safe_fx(ccy: str) -> float | None:
    """v19.59：取 ccy→TWD 即時匯率（5min cache，與 _render_investment_calc 同源）。TWD 計價回 1.0。"""
    if not ccy:
        return None
    if ccy == "TWD":
        return 1.0
    try:
        from services.fund_service import get_latest_fx
        v = get_latest_fx(f"{ccy}TWD=X")
        return float(v) if (v is not None and v > 0) else None
    except Exception:
        return None


# v19.222 P1-1:_safe_num 收口至 shared/converters.py SSOT
from shared.converters import safe_num as _safe_num  # noqa: E402



def _period_ret(fund: dict, perf_key: str, metric_key: str):
    """各期報酬：優先 MoneyDJ 官方 perf，缺則退本地 calc_metrics。"""
    mj = fund.get("moneydj_raw") or {}
    perf = mj.get("perf") or {}
    v = _safe_num(perf.get(perf_key))
    if v is not None:
        return v
    m = fund.get("metrics") or {}
    return _safe_num(m.get(metric_key))


def _ret_1y_total(fund: dict):
    """近 1Y 含息報酬：沿用全 app 一致的 compute_1y_total_return；缺則退 perf/metrics。"""
    try:
        from ui.helpers.macro_helpers import compute_1y_total_return
        _v, _ = compute_1y_total_return(fund)
        v = _safe_num(_v)
        if v is not None:
            return v
    except ImportError:
        pass
    mj = fund.get("moneydj_raw") or {}
    v = _safe_num((mj.get("perf") or {}).get("1Y"))
    if v is not None:
        return v
    m = fund.get("metrics") or {}
    for k in ("ret_1y_total", "ret_1y"):
        v = _safe_num(m.get(k))
        if v is not None:
            return v
    return None


def _extract_peer_1y(fund: dict):
    """從 peer_compare 取『同類型平均』報酬。回傳 (peer_ret 或 None, peer_label)。"""
    mj = fund.get("moneydj_raw") or {}
    peer = ((mj.get("risk_metrics") or {}).get("peer_compare")) or {}
    if not peer:
        return None, ""
    best_key = next(
        (k for k in peer
         if "平均" in k and ("同" in k or "類" in k or "型" in k or "區域" in k)),
        None,
    )
    if best_key is None:
        best_key = next((k for k in peer if "平均" in k), None)
    if best_key is None:
        return None, ""
    row = peer.get(best_key) or {}
    for v in row.values():
        f = _safe_num(v)
        if f is not None:
            return f, best_key
    return None, best_key


def _grade(ret_1y, peer_1y):
    """依超額報酬分級。回傳 (excess 或 None, 判定文字)。"""
    if peer_1y is None:
        return None, "⬜ 同類資料不足"
    if ret_1y is None:
        return None, "⬜ 報酬資料不足"
    excess = ret_1y - peer_1y
    if excess >= _EXCESS_GOOD:
        return excess, "🏆 優等生"
    if excess <= _EXCESS_LAG:
        return excess, "⚠️ 落後（汰弱）"
    return excess, "🟡 普通生"


def _compute_fund_health_kpis(fund: dict) -> dict:
    """v19.54：算單檔 4 大健診 KPI（吃本金 / 月配息 TWD / 年化配息率 / TER）。

    回傳 dict，缺資料欄位給 None；render 端負責 fallback 顯示。
    純函式，不碰 st，便於後續單測。
    """
    mj = fund.get("moneydj_raw") or {}
    m = fund.get("metrics") or {}

    # v19.150:吃本金檢查改走 check_eating_principal_1y_mk SSOT 入口
    # (與 tab_fund_grp_health 同源,未來 MK 公式變更只改一處)。
    # _adr / _tr1y 仍 expose 給其他 KPI(月配息/Coverage 顯示)使用。
    from services.health.dividend import check_eating_principal_1y_mk

    # 1) 年化配息率:MoneyDJ wb05 官方值優先,缺則退本地估算(展示用)
    _mj_dy = _safe_num(mj.get("moneydj_div_yield"))
    _adr = _mj_dy if (_mj_dy and _mj_dy > 0) else _safe_num(m.get("annual_div_rate"))
    if _adr is not None and _adr <= 0:
        _adr = None

    # 2) 吃本金檢查 + tr1y 經由 SSOT 入口
    # check_eating_principal_1y_mk 內部用 MK 嚴格單利優先(有 series + dividends 時)
    _ds = check_eating_principal_1y_mk(fund)

    # 3) tr1y 給其他 KPI 顯示用(月配息 / Coverage 計算)
    # SSOT 一致:若 _ds 走 mk_simple,_tr1y 應從 _ds["_tr1y_meta"] 取(避免顯示與
    # verdict 不同數字);若 fallback metrics,則用 _ret_1y_total。
    _tr1y = None
    if _ds and _ds.get("_tr1y_method") == "mk_simple":
        _meta = _ds.get("_tr1y_meta") or {}
        _nc = _meta.get("nav_change_pct")
        _dt = _meta.get("div_total_pct")
        if _nc is not None and _dt is not None:
            _tr1y = _nc + _dt
    if _tr1y is None:
        _tr1y = _ret_1y_total(fund)

    # 4) 月配息（TWD）= invest_twd × 年化配息率 ÷ 12（沿用 single-fund 試算邏輯）
    _inv_twd = _safe_num(fund.get("invest_twd")) or 0.0
    _monthly_div_twd = (_inv_twd * _adr / 100 / 12) if (_adr and _inv_twd > 0) else None

    # 5) TER 費用率分析 — 取 mgmt_fee + category → 對照表
    _ter_val = _safe_num(mj.get("mgmt_fee"))
    _ter_cat = str(mj.get("category", "") or "")
    _ter_avg = next(
        (_v for _k, _v in _TER_AVG_MAP.items() if _k and _k in _ter_cat),
        None,
    )
    _ter_diff = None
    if _ter_val is not None and _ter_avg is not None:
        _ter_diff = _ter_val - _ter_avg

    return {
        "adr": _adr,
        "ret_1y": _tr1y,
        "safety": _ds,
        "invest_twd": _inv_twd if _inv_twd > 0 else None,
        "monthly_div_twd": _monthly_div_twd,
        "ter_val": _ter_val,
        "ter_cat": _ter_cat,
        "ter_avg": _ter_avg,
        "ter_diff": _ter_diff,
    }


def _render_fund_health_card(fund: dict, k: dict) -> None:
    """v19.54：渲染單檔 4 大健診卡（吃本金 / 月配息 / 配息率 / TER），仿 tab2_single_fund 風格。"""
    _code = fund.get("code", "—")
    _name = (fund.get("name") or _code)[:30]

    # ── 吃本金燈號 ──
    _ds = k["safety"]
    _adr = k["adr"]
    _tr1y = k["ret_1y"]
    if _adr is None:
        _kpi_icon, _kpi_color, _kpi_bg = "⬜", TRAFFIC_NEUTRAL, GH_BG_CARD
        _kpi_title = "吃本金檢查 — ⬜ 不適用"
        _kpi_msg = "本基金無年化配息率資料（可能為累積型 / 不配息基金）"
        _kpi_cov_txt = "—"
    elif _tr1y is None or _ds is None:
        _kpi_icon, _kpi_color, _kpi_bg = "⬜", TRAFFIC_NEUTRAL, GH_BG_CARD
        _kpi_title = "吃本金檢查 — ⬜ 資料不足"
        _kpi_msg = "缺含息總報酬（1Y），無法計算 Coverage"
        _kpi_cov_txt = "—"
    else:
        _al = _ds.get("alert_level", "grey")
        _kpi_color = {"red": MATERIAL_RED, "yellow": MATERIAL_ORANGE,
                      "green": MATERIAL_GREEN}.get(_al, TRAFFIC_NEUTRAL)
        _kpi_bg = {"red": BG_DARK_RED_1, "yellow": BG_DARK_AMBER_1,
                   "green": BG_DARK_GREEN_1}.get(_al, GH_BG_CARD)
        _kpi_icon = {"red": "🔴", "yellow": "🟡", "green": "🟢"}.get(_al, "⬜")
        _kpi_title = f"吃本金檢查 — {_kpi_icon} {_ds.get('status', '')}"
        _kpi_msg = _ds.get("message", "")
        _cov = _ds.get("coverage")
        _kpi_cov_txt = f"{_cov:.2f}" if _cov is not None else "—"

    # ── 月配息（TWD）/ 年化配息率 / 1Y 含息 ──
    _monthly_txt = (f"{k['monthly_div_twd']:,.0f}"
                    if k["monthly_div_twd"] is not None else "—")
    _adr_txt = f"{_adr:.2f}%" if _adr else "—"
    _tr1y_txt = f"{_tr1y:.2f}%" if _tr1y is not None else "—"
    _inv_hint = (f"本金 {k['invest_twd']:,.0f} TWD ÷ 12 月"
                 if k["invest_twd"] else "尚未填投入金額 → 月配息 0")

    st.markdown(
        f"<div style='background:{_kpi_bg};border:2px solid {_kpi_color};"
        f"border-radius:12px;padding:10px 14px;margin:8px 0'>"
        f"<div style='color:{GH_FG_PRIMARY};font-weight:800;font-size:13px;margin-bottom:4px'>"
        f"💊 {_name} <span style='color:{TRAFFIC_NEUTRAL};font-size:11px'>{_code}</span></div>"
        f"<div style='color:{_kpi_color};font-size:12px;font-weight:700;margin-bottom:8px'>"
        f"{_kpi_title}</div>"
        f"<div style='display:flex;gap:18px;flex-wrap:wrap'>"
        f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>1Y 含息報酬</div>"
        f"<div style='color:#fff;font-weight:700;font-size:15px'>{_tr1y_txt}</div></div>"
        f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>年化配息率</div>"
        f"<div style='color:#fff;font-weight:700;font-size:15px'>{_adr_txt}</div></div>"
        f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>Coverage</div>"
        f"<div style='color:{_kpi_color};font-weight:700;font-size:15px'>{_kpi_cov_txt}</div></div>"
        f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>月配息（TWD）</div>"
        f"<div style='color:#fff;font-weight:700;font-size:15px'>{_monthly_txt}</div></div>"
        f"</div>"
        f"<div style='color:#aaa;font-size:11px;margin-top:6px'>{_kpi_msg}</div>"
        f"<div style='color:#666;font-size:10px;margin-top:2px'>{_inv_hint}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── TER 費用率分析 ──
    if k["ter_val"] is not None:
        _tv = k["ter_val"]
        _ta = k["ter_avg"]
        _tcat = k["ter_cat"]
        _td = k["ter_diff"]
        if _ta is not None and _td is not None:
            _ter_c = MATERIAL_GREEN if _td <= 0 else (MATERIAL_ORANGE if _td <= 0.5 else MATERIAL_RED)
            _vs_txt = (f"高於均值 +{_td:.2f}%" if _td > 0 else f"低於均值 {abs(_td):.2f}%")
            _avg_html = (
                f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>同類均值</div>"
                f"<div style='color:{TRAFFIC_NEUTRAL};font-weight:700;font-size:15px'>{_ta:.2f}%</div></div>"
                f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>費用比較</div>"
                f"<div style='color:{_ter_c};font-weight:700;font-size:15px'>{_vs_txt}</div></div>"
            )
        else:
            _ter_c, _avg_html = TRAFFIC_NEUTRAL, ""
        _ter_lbl = f" — {_tcat[:12]}" if _tcat else ""
        st.markdown(
            f"<div style='background:{GH_BG_CARD};border:1px solid {GH_BORDER};"
            f"border-radius:10px;padding:8px 14px;margin:4px 0 12px 0'>"
            f"<div style='color:{TRAFFIC_NEUTRAL};font-size:11px;margin-bottom:6px'>💰 TER 費用率分析{_ter_lbl}</div>"
            f"<div style='display:flex;gap:18px;flex-wrap:wrap'>"
            f"<div><div style='color:{TRAFFIC_NEUTRAL};font-size:10px'>最高經理費</div>"
            f"<div style='color:{_ter_c};font-weight:700;font-size:15px'>{_tv:.2f}%</div></div>"
            + _avg_html +
            "</div>"
            "<div style='color:#555;font-size:10px;margin-top:4px'>"
            "費用率愈低，長期複利效益愈佳（每降 1% TER，20 年後終值多 ~25%）</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.caption(f"💰 TER 費用率分析 — ⬜ {_code} 缺 mgmt_fee 資料")


def build_checkup_dataframe(portfolio_funds: list | None) -> pd.DataFrame:
    """把 portfolio_funds（已載入、依 code 去重）攤平成基金體檢 PK 表。"""
    if not portfolio_funds:
        return pd.DataFrame(columns=_DISPLAY_COLS)

    seen: set = set()
    rows: list = []
    for f in portfolio_funds:
        if not f.get("loaded") or f.get("load_error"):
            continue
        code = str(f.get("code", "") or "").strip().upper()
        if not code or code in seen:
            continue
        seen.add(code)

        m = f.get("metrics") or {}
        ret_1y = _ret_1y_total(f)
        peer_1y, _ = _extract_peer_1y(f)
        excess, verdict = _grade(ret_1y, peer_1y)
        mj = f.get("moneydj_raw") or {}
        # v19.58：每月每100萬配息（TWD）= 1,000,000 × adr% / 100 / 12 = 10000 × adr / 12
        # 沿用 _compute_fund_health_kpis 同源 adr 推導路徑（MoneyDJ wb05 優先 → metrics fallback）
        _mj_dy = _safe_num(mj.get("moneydj_div_yield"))
        _adr = _mj_dy if (_mj_dy and _mj_dy > 0) else _safe_num(m.get("annual_div_rate"))
        _mdiv_1m = (10000.0 * _adr / 12.0) if (_adr and _adr > 0) else None
        # v19.59：從 fund_grp_health_extras._render_investment_calc L194-283 上抽同源欄位到比較表
        _ccy_raw = (mj.get("currency") or f.get("currency") or "").strip()
        _ccy = _norm_ccy(_ccy_raw, default="", mode="yf") if _ccy_raw else ""
        _nav = _safe_num(m.get("nav") or mj.get("nav_latest"))
        _fx = _safe_fx(_ccy) if _ccy else None
        # 1,000,000 TWD → 原幣本金 → 可申購單位數 / 月配股
        # 公式：amt_local = TWD / FX（TWD 計價 FX=1）；units = amt_local / NAV；月配股 = (amt_local × adr/100/12) / NAV
        _units = None
        _mon_units = None
        if _nav and _nav > 0 and _fx and _fx > 0:
            _amt_local = 1_000_000.0 / _fx
            _units = _amt_local / _nav
            if _adr and _adr > 0:
                _mon_units = (_amt_local * _adr / 100.0 / 12.0) / _nav
        # v19.60：投資試算同源 SSOT — 吃 fund.invest_twd（sidebar 實際本金）
        # 公式：原幣本金 = invest_twd / FX；月配 TWD = invest_twd × adr/100/12；年配 TWD = invest_twd × adr/100
        _inv_twd = _safe_num(f.get("invest_twd")) or 0.0
        _amt_local_inv = None
        _mon_div_inv = None
        _ann_div_inv = None
        if _inv_twd > 0 and _fx and _fx > 0:
            _amt_local_inv = _inv_twd / _fx
            if _adr and _adr > 0:
                _mon_div_inv = _inv_twd * _adr / 100.0 / 12.0
                _ann_div_inv = _inv_twd * _adr / 100.0
        # v19.62：金額/單位欄 round to 2 防 Styler+dtype 漂移導致 NumberColumn format 失效
        def _r2(v):
            return round(v, 2) if v is not None else None
        rows.append({
            "代碼": f.get("code", "—"),
            "標的名稱": f.get("name") or f.get("code") or "—",
            "近1M(%)": _r2(_period_ret(f, "1M", "ret_1m")),
            "近3M(%)": _r2(_period_ret(f, "3M", "ret_3m")),
            "近6M(%)": _r2(_period_ret(f, "6M", "ret_6m")),
            "近1Y含息(%)": _r2(ret_1y),
            "同類平均(1Y%)": _r2(peer_1y),
            "超額(pp)": _r2(excess),
            "夏普值": _r2(_safe_num(m.get("sharpe"))),
            "年化波動(1Y%)": _r2(_safe_num(m.get("std_1y"))),
            "計價幣別": _ccy or "—",
            "NAV(原幣)": round(_nav, 4) if _nav is not None else None,
            "即時匯率(FX)": round(_fx, 4) if _fx is not None else None,
            "可申購單位數": _r2(_units),
            "月配股(單位)": _r2(_mon_units),
            "每月100萬配息(TWD)": _r2(_mdiv_1m),
            # v19.60：投資試算實際本金 3 欄（無 invest_twd 全 None → 顯示 —）
            "原幣本金🧮(本金)": _r2(_amt_local_inv),
            "月配息🧮(本金TWD)": _r2(_mon_div_inv),
            "年配息🧮(本金TWD)": _r2(_ann_div_inv),
            "買點": _ZONE_LABEL.get(tag_price_zone(f), "—"),
            "體檢判定": verdict,
        })
    return pd.DataFrame(rows, columns=_DISPLAY_COLS)


def _style_checkup(df: pd.DataFrame):
    """🏆 優等生綠底 / ⚠️ 汰弱紅底 / 超跌價深綠底。"""
    def _row_color(row):
        v = str(row.get("體檢判定", ""))
        z = str(row.get("買點", ""))
        if v.startswith("🏆"):
            return ["background-color: #0f3a1a"] * len(row)
        if v.startswith("⚠️"):
            return ["background-color: #4a1f1f"] * len(row)
        if "超跌" in z:
            return ["background-color: #14361f"] * len(row)
        return [""] * len(row)
    return df.style.apply(_row_color, axis=1)


_CHECKUP_COL_CONFIG = {
    "近1M(%)": st.column_config.NumberColumn(
        "近1M(%)", format="%.2f", help="近一個月報酬（挑三揀四短期趨勢）"),
    "近3M(%)": st.column_config.NumberColumn(
        "近3M(%)", format="%.2f", help="近三個月報酬"),
    "近6M(%)": st.column_config.NumberColumn(
        "近6M(%)", format="%.2f", help="近六個月報酬"),
    "近1Y含息(%)": st.column_config.NumberColumn(
        "近1Y含息(%)", format="%.2f",
        help="近一年含息總報酬（淨值漲跌＋配息），PK 同類平均的主指標"),
    "同類平均(1Y%)": st.column_config.NumberColumn(
        "同類平均(1Y%)", format="%.2f",
        help="MoneyDJ 績效評比頁『同類型平均』報酬；約 3 成基金無此資料"),
    "超額(pp)": st.column_config.NumberColumn(
        "超額(pp)", format="%+.2f",
        help="近1Y含息 − 同類平均。≥ +2 為🏆優等生、≤ −2 為⚠️汰弱候選"),
    "夏普值": st.column_config.NumberColumn(
        "夏普值", format="%.2f",
        help="(年化報酬-無風險利率)/年化波動。<0 代表承擔風險卻沒賺錢"),
    "年化波動(1Y%)": st.column_config.NumberColumn(
        "年化波動(1Y%)", format="%.2f", help="近一年日報酬年化標準差"),
    # v19.59：從逐檔深度分析「投資試算」上抽 5 欄到比較表
    "計價幣別": st.column_config.TextColumn(
        "計價幣別", help="MoneyDJ wb05「計價幣別」欄；本系統嚴格走網路抓不再人工 fallback"),
    "NAV(原幣)": st.column_config.NumberColumn(
        "NAV(原幣)", format="%.4f",
        help="MoneyDJ wb05 最新淨值（原幣計價）；缺則退 metrics.nav"),
    "即時匯率(FX)": st.column_config.NumberColumn(
        "即時匯率(FX)", format="%.4f",
        help="1 原幣 = X TWD（Yahoo 即時匯率，5min cache）；TWD 計價基金顯示 1"),
    "可申購單位數": st.column_config.NumberColumn(
        "可申購單位數", format="%,.2f",
        help="100 萬 TWD 換成原幣後，按最新 NAV 可買的單位數；公式：(1,000,000 ÷ FX) ÷ NAV"),
    "月配股(單位)": st.column_config.NumberColumn(
        "月配股(單位)", format="%,.2f",
        help="若月配息全部再投入可換的單位數；公式：(月配息原幣) ÷ NAV"),
    "每月100萬配息(TWD)": st.column_config.NumberColumn(
        "每月100萬配息(TWD)", format="%,.2f",
        help="假設投入 100 萬 TWD，按 MoneyDJ wb05 年化配息率推估的單月配息現金流；"
             "公式：1,000,000 × 年化配息率 / 12。無配息資料的基金顯示 —"),
    # v19.60：投資試算同源 SSOT — 對應 sidebar invest_twd 實際本金（沒填顯示 —）
    "原幣本金🧮(本金)": st.column_config.NumberColumn(
        "原幣本金🧮(本金)", format="%,.2f",
        help="按 sidebar 實際投入本金（invest_twd）換成原幣的金額；"
             "公式：invest_twd ÷ FX。未填投入金額顯示 —"),
    "月配息🧮(本金TWD)": st.column_config.NumberColumn(
        "月配息🧮(本金TWD)", format="%,.2f",
        help="按 sidebar 實際本金推估的單月配息（TWD）；"
             "公式：invest_twd × 年化配息率 / 100 / 12"),
    "年配息🧮(本金TWD)": st.column_config.NumberColumn(
        "年配息🧮(本金TWD)", format="%,.2f",
        help="按 sidebar 實際本金推估的年配息（TWD）；"
             "公式：invest_twd × 年化配息率 / 100"),
    "買點": st.column_config.TextColumn(
        "買點", help="標準差買點燈號：跌破 -1σ 便宜 / -2σ 超跌 / 破布林上軌停利"),
    "體檢判定": st.column_config.TextColumn(
        "體檢判定", help="與同類型 1Y 含息 PK：🏆優等生 / 🟡普通生 / ⚠️汰弱 / ⬜不評"),
}


def render_fund_checkup(portfolio_funds: list | None, expanded: bool = False) -> None:
    """Tab3 expander：基金體檢 PK 表（與同類型比較，揪優等生 / 汰弱候選）。

    expanded：expander 是否預設展開。組合健檢 tab 把此區塊上移到健診總表之上時傳
    True，讓「逐檔財務健診（4 大功能）」直接可見、不必再點開（v19.190）。
    """
    with st.expander("🩺 基金體檢表 — 與同類型 PK，揪出優等生 / 汰弱候選",
                     expanded=expanded):
        st.caption(
            "📖 郭老師「挑三揀四」法則：把每檔基金的含息報酬與『同類型平均』PK，"
            "打敗同類＝🏆 優等生（抱緊滾雪球），明顯落後＝⚠️ 汰弱候選。")

        df = build_checkup_dataframe(portfolio_funds)
        if df.empty:
            st.info("📊 載入基金後，這裡會列出每檔與同類型的 PK 體檢結果。")
            return

        st.markdown(
            "- **近 1M/3M/6M/1Y**：各區間報酬趨勢，連續落後同類是汰換警訊。\n"
            "- **同類平均(1Y)**：來自 MoneyDJ 績效評比頁，約 3 成基金抓不到 → 標 ⬜ 不評。\n"
            "- **超額(pp)** = 近1Y含息 − 同類平均：≥ +2 🏆優等生；±2 內 🟡普通生；≤ −2 ⚠️汰弱候選。\n"
            "- **每月100萬配息(TWD)** = 100萬 × MoneyDJ wb05 年化配息率 ÷ 12："
            "用同口徑估「現金流量化能力」，方便橫向 PK。\n"
            "- ⚠️ 老師另兩項標準（成分股 ROE>15%/EPS 成長、規模流動性）資料源無法取得，未納入；"
            "買賣點細節請見上方「MK 智能戰情室」。")

        _verdict = df["體檢判定"]
        n_good = int(_verdict.str.startswith("🏆").sum())
        n_lag = int(_verdict.str.startswith("⚠️").sum())
        n_na = int(_verdict.str.startswith("⬜").sum())
        st.markdown(
            f"**🏆 {n_good} 檔優等生** ・ ⚠️ {n_lag} 檔汰弱候選 ・ "
            f"⬜ {n_na} 檔同類資料不足（共 {len(df)} 檔）")

        df = df.sort_values(
            by="超額(pp)", ascending=False, na_position="last", kind="stable")
        st.dataframe(
            _style_checkup(df),
            column_config=_CHECKUP_COL_CONFIG,
            hide_index=True, use_container_width=True,
        )

        # v19.54 ── 逐檔財務健診卡（4 大功能：吃本金 / 月配息 / 配息率 / TER）──
        st.divider()
        st.markdown(
            "#### 💊 逐檔財務健診（4 大功能）"
            f"<span style='color:{TRAFFIC_NEUTRAL};font-size:11px;margin-left:8px'>"
            "吃本金 / 月配息 TWD / 年化配息率 / TER 費用率</span>",
            unsafe_allow_html=True,
        )
        st.caption(
            "對照「📊 投資試算」與「② 體檢儀表板」邏輯：年化配息率取 MoneyDJ wb05 官方值；"
            "Coverage = 1Y 含息報酬 ÷ 年化配息率；TER 對標台灣基金市場同類均值。")

        # v19.61：健診摘要表 — 多檔橫向 PK（同源 _compute_fund_health_kpis SSOT）
        # v19.183 Bug5：加「費用率排名 / 同類排名」欄
        #   - 費用率排名：組內升序(低=第1),格式 "n/N"
        #   - 同類排名：MoneyDJ peer_compare 萃取 percentile(越高越強),缺則 —
        try:
            from services.portfolio_service import rank_funds_within_portfolio
            _ranks = rank_funds_within_portfolio(
                [f for f in (portfolio_funds or [])
                 if f.get("loaded") and not f.get("load_error")]
            )
        except Exception as _e_rank:
            import sys as _sys_rank
            print(f"[fund_checkup] rank fail: {type(_e_rank).__name__}: {_e_rank}",
                  file=_sys_rank.stderr)
            _ranks = {}

        def _rank_txt(code):
            _r = _ranks.get(code) or {}
            _er = _r.get("expense_rank")
            _en = _r.get("expense_n") or 0
            _exp_s = f"{_er}/{_en}" if (_er and _en) else "—"
            _pp = _r.get("peer_percentile")
            _praw = _r.get("peer_rank_raw")
            _peer_s = f"{_pp:.0f}%（{_praw}）" if (_pp is not None and _praw) else "—"
            return _exp_s, _peer_s

        _seen_sum: set = set()
        _sum_rows: list = []
        _kpi_cache: dict = {}
        for f in (portfolio_funds or []):
            if not f.get("loaded") or f.get("load_error"):
                continue
            _c = str(f.get("code", "") or "").strip().upper()
            if not _c or _c in _seen_sum:
                continue
            _seen_sum.add(_c)
            _exp_rank_s, _peer_rank_s = _rank_txt(_c)
            try:
                _k = _compute_fund_health_kpis(f)
                _kpi_cache[_c] = (f, _k)
            except Exception as _e:
                _k = None
                _sum_rows.append({
                    "代號": _c, "基金名": f.get("name") or _c,
                    "吃本金狀態": f"⚠️ 計算失敗 [{type(_e).__name__}]",
                    "1Y 含息%": None, "年化配息率%": None,
                    "Coverage": None, "月配息(TWD)": None, "最高經理費%": None,
                    "費用率排名": _exp_rank_s, "同類排名": _peer_rank_s,
                })
                continue
            _ds = _k.get("safety") or {}
            _al = _ds.get("alert_level", "grey")
            _status = (
                f"{ {'red': '🔴', 'yellow': '🟡', 'green': '🟢'}.get(_al, '⬜') } "
                f"{_ds.get('status', '不適用' if _k['adr'] is None else '資料不足')}"
            )
            # v19.62：round 2 防 dtype 漂移；金額類欄與體檢表同源 2 位小數規範
            def _r2s(v):
                return round(v, 2) if v is not None else None
            _sum_rows.append({
                "代號": _c,
                "基金名": (f.get("name") or _c)[:30],
                "吃本金狀態": _status,
                "1Y 含息%": _r2s(_k.get("ret_1y")),
                "年化配息率%": _r2s(_k.get("adr")),
                "Coverage": _r2s(_ds.get("coverage")),
                "月配息(TWD)": _r2s(_k.get("monthly_div_twd")),
                "最高經理費%": _r2s(_k.get("ter_val")),
                "費用率排名": _exp_rank_s,
                "同類排名": _peer_rank_s,
            })

        if _sum_rows:
            st.markdown("##### 📋 健診摘要表（多檔橫向 PK）")
            _sum_df = pd.DataFrame(_sum_rows)
            st.dataframe(
                _sum_df, hide_index=True, use_container_width=True,
                column_config={
                    "吃本金狀態": st.column_config.TextColumn(
                        "吃本金狀態",
                        help="🟢 安全 / 🟡 警示 / 🔴 吃本金 / ⬜ 不適用或資料不足"),
                    "1Y 含息%": st.column_config.NumberColumn(
                        "1Y 含息%", format="%.2f",
                        help="近一年含息總報酬（淨值漲跌＋配息）"),
                    "年化配息率%": st.column_config.NumberColumn(
                        "年化配息率%", format="%.2f",
                        help="MoneyDJ wb05 官方年化配息率"),
                    "Coverage": st.column_config.NumberColumn(
                        "Coverage", format="%.2f",
                        help="1Y 含息報酬 ÷ 年化配息率；< 1 即吃本金"),
                    "月配息(TWD)": st.column_config.NumberColumn(
                        "月配息(TWD)", format="%,.2f",
                        help="按 sidebar 實際本金 × 年化配息率 ÷ 12；未填本金顯示 —"),
                    "最高經理費%": st.column_config.NumberColumn(
                        "最高經理費%", format="%.2f",
                        help="MoneyDJ wb05 最高經理費；缺資料顯示 —"),
                    "費用率排名": st.column_config.TextColumn(
                        "費用率排名",
                        help="在你載入的這幾檔之間，按最高經理費由低到高排名（第1名=最便宜）；"
                             "格式 n/N，N 為有費用率資料的檔數"),
                    "同類排名": st.column_config.TextColumn(
                        "同類排名",
                        help="MoneyDJ 同類型基金排名換算的 percentile（越高越強，100%=同類第1）；"
                             "約 3 成基金 MoneyDJ 無同類排名資料 → 顯示 —"),
                },
            )
            st.divider()

        # 逐檔卡（drill-down 細節保留）
        for _c, (_f, _k) in _kpi_cache.items():
            try:
                _render_fund_health_card(_f, _k)
            except Exception as _e:
                st.caption(f"⚠️ {_c} 健診卡渲染失敗：[{type(_e).__name__}] {str(_e)[:60]}")
