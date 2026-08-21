"""services/allocation_backtest.py — 配置回測引擎(v19.427)。L2 純函式,零 IO,不 import streamlit。

給 N 檔基金(原幣 NAV)+ USDTWD 歷史,回測數套配置/切換策略在**台幣總報酬**下的表現,
排名效益最高者,並由勝出策略的**當前訊號**產出三種建議(動作清單 / 賣→買配對 / 目標權重%)。

反 lookahead(§2.3)是本引擎的生死線:每個再平衡日 t 只用「截至 t 為止」的 FX 窗與 NAV 算訊號,
**絕不**用全期均值;`fx_regime` / `calc_hwm_sigma_levels` 皆餵截止序列。成本內含(換手 × 申贖+換匯點差)
避免切換策略被高估(§1 誠實)。缺料 / 短史 / 非 USD/TWD / σ=0 → 誠實排除或 None,**絕不**捏造。

§4.1 單位:原幣 NAV × USDTWD(rate_twd_per_usd, TWD/USD)→ 台幣序列;台幣計價基金原樣。
§4.5 對齊:台幣序列共同交易日 intersection(不 ffill);FX 對 NAV 用 merge_asof backward(不吃未來)。
常數全走 shared.signal_thresholds SSOT(§3.3)。

5 套策略:
- S0 等權買進持有(baseline,永遠列)
- S1 NAV×匯率 2D 切換(現行方向:低NAV+台幣強→買 / 高NAV+台幣弱→賣)
- S2 NAV×匯率 2D 切換(**匯率軸反向**;與 S1 只差極性 → 兩者績效差 = 匯率方向的乾淨裁決)
- S3 只看 σ 基期輪動(低→買 / 高→賣,不看匯率)
- S4 效率前緣靜態最佳權重(訓練後固定持有)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from shared.signal_thresholds import (
    BACKTEST_COST_BPS,
    BACKTEST_FX_ASOF_TOLERANCE_DAYS,
    BACKTEST_FX_SPREAD_BPS,
    BACKTEST_MIN_COMMON_DAYS,
    BACKTEST_NEW_FUND_MIN_DAYS,
    BACKTEST_REBALANCE_FREQ,
    BACKTEST_TILT_BUY,
    BACKTEST_TILT_SELL,
    FRONTIER_MIN_OBS,
    FRONTIER_RF_ANNUAL,
    FX_REGIME_WINDOW_DAYS,
)

STRATEGY_IDS = ("S0", "S1", "S2", "S3", "S4")
STRATEGY_LABELS = {
    "S0": "等權買進持有(baseline)",
    "S1": "NAV×匯率(現行方向)",
    "S2": "NAV×匯率(匯率反向)",
    "S3": "σ 基期輪動(不看匯率)",
    "S4": "效率前緣靜態最佳",
}

CAVEAT = (
    "⚠️ 回測 ≠ 未來。少數基金 + 有限月數 → 統計檢定力低,結論為**方向性證據**而非顯著性。"
    "已內含換手成本(申贖 + 換匯點差),故切換策略不會被高估。過去績效不代表未來,勿照抄權重。"
)

_SUPPORTED_CCY = ("USD", "TWD")     # Phase 1;非此兩者無歷史匯率序列 → 誠實排除(§1)


# ───────────────────────── 幣別 / 對齊 ─────────────────────────

def _norm_ccy(ccy) -> str:
    """幣別正規化 → ISO 上碼。優先 services.currency.normalize_ccy;不可用時退化小映射。"""
    try:
        from services.currency import normalize_ccy
        # v19.449 稽核(H3 驗證 item6):default="" —— 缺/空幣別**不可矇成 USD**(會對無匯率
        # 曝險的檔捏造 FX 損益),回 "" 讓 to_twd_total_return_series 誠實排除(§1 + v19.59 原則)。
        _c = normalize_ccy(ccy, default="")
        if _c:
            return str(_c).upper()
    except ImportError:                          # 僅 normalize_ccy 不可用時退化本地映射;
        pass                                     # 非 ImportError(真 bug)不吞,往上拋(§3.3)
    _s = str(ccy or "").strip().upper()
    _map = {"美元": "USD", "美金": "USD", "台幣": "TWD", "新台幣": "TWD", "TWD": "TWD", "USD": "USD"}
    return _map.get(str(ccy or "").strip(), _map.get(_s, _s))


def _clean_fx(fx_series) -> "pd.Series | None":
    """USDTWD 序列 → 乾淨升冪 Series(tz-naive, 唯一日期, >0);<2 點 → None。"""
    if fx_series is None:
        return None
    s = pd.Series(fx_series).dropna()
    if len(s) < 2:
        return None
    idx = pd.to_datetime(s.index, errors="coerce")
    s = s[idx.notna()]
    idx = idx[idx.notna()]
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    s.index = idx
    s = s.sort_index()
    s = s[~s.index.duplicated(keep="last")]
    s = s[s > 0]
    return s if len(s) >= 2 else None


def to_twd_total_return_series(nav_series, ccy: str, fx_series=None) -> "pd.Series | None":
    """原幣 NAV → 台幣序列。USD: nav×usdtwd(merge_asof backward, 7日容差);TWD: 原樣;
    其餘 / 缺 FX → None(§1 不假造匯率路徑)。輸入 nav 須為已清乾淨的升冪 Series。"""
    from services.portfolio_performance import _clean_nav
    _nav = _clean_nav(nav_series)
    if _nav is None:
        return None
    _c = _norm_ccy(ccy)
    if _c == "TWD":
        return _nav
    if _c != "USD":
        return None                                    # 非 USD/TWD → 無歷史匯率(§1)
    _fx = _clean_fx(fx_series)
    if _fx is None:
        return None
    _left = pd.DataFrame({"date": _nav.index, "nav": _nav.to_numpy()}).sort_values("date")
    _right = pd.DataFrame({"date": _fx.index, "fx": _fx.to_numpy()}).sort_values("date")
    _m = pd.merge_asof(_left, _right, on="date", direction="backward",
                       tolerance=pd.Timedelta(days=BACKTEST_FX_ASOF_TOLERANCE_DAYS))
    _m = _m.dropna(subset=["fx"])                      # 無 on-or-before 匯率(容差外)→ 丟,不 ffill
    if len(_m) < 2:
        return None
    _out = pd.Series((_m["nav"] * _m["fx"]).to_numpy(), index=pd.DatetimeIndex(_m["date"]))
    return _out if len(_out) >= 2 else None


def build_aligned_matrices(nav_by_code: dict, ccy_by_code: dict, fx_series=None) -> tuple:
    """各檔 → (原幣序列 dict, 台幣共同交易日矩陣 df)。σ 用原幣(full),報酬用台幣(對齊)。

    → (orig_by_code, twd_df|None, included, excluded[dict], flags, foreign_codes:set)。
    §4.5 台幣序列共同日 intersection(不 ffill);排除誠實回報(§1)。
    """
    from services.portfolio_performance import _clean_nav
    excluded: list = []
    orig_by_code: dict = {}
    twd_by_code: dict = {}
    foreign: set = set()

    for _code, _nav in (nav_by_code or {}).items():
        _orig = _clean_nav(_nav)
        if _orig is None:
            excluded.append({"code": _code, "reason": "NAV 序列不足(<2 有效點)"})
            continue
        _ccy = _norm_ccy((ccy_by_code or {}).get(_code, ""))
        if _ccy not in _SUPPORTED_CCY:
            excluded.append({"code": _code,
                             "reason": f"幣別 {(ccy_by_code or {}).get(_code) or '未知'} 無歷史匯率序列(僅支援 USD/TWD)"})
            continue
        _twd = to_twd_total_return_series(_orig, _ccy, fx_series)
        if _twd is None:
            excluded.append({"code": _code, "reason": "台幣序列建構失敗(缺對齊匯率)"})
            continue
        orig_by_code[_code] = _orig
        twd_by_code[_code] = _twd
        if _ccy == "USD":
            foreign.add(_code)

    if len(twd_by_code) < 1:
        return orig_by_code, None, list(twd_by_code.keys()), excluded, {}, foreign

    _common = None
    for _s in twd_by_code.values():
        _common = _s.index if _common is None else _common.intersection(_s.index)
    if _common is None or len(_common) < 2:
        return orig_by_code, None, list(twd_by_code.keys()), excluded, {}, foreign

    _twd_df = pd.DataFrame({_c: _s.loc[_common] for _c, _s in twd_by_code.items()}).sort_index()
    _flags = {"low_confidence": bool(len(_common) < BACKTEST_NEW_FUND_MIN_DAYS)}
    return orig_by_code, _twd_df, list(_twd_df.columns), excluded, _flags, foreign


# ───────────────────────── 再平衡 / 權重 ─────────────────────────

def rebalance_dates(index, freq: str = BACKTEST_REBALANCE_FREQ) -> list:
    """交易日 index → 再平衡日清單。ME: 每月最後一個**實際**交易日(label 右閉,不引未來,§4.5);
    首個共同日納入為初始配置日。回傳升冪去重 list[Timestamp]。"""
    _idx = pd.DatetimeIndex(index).sort_values()
    if len(_idx) == 0:
        return []
    _s = pd.Series(_idx, index=_idx)
    _monthly = _s.groupby(_idx.to_period("M")).max()          # 每月最後交易日
    _dates = list(pd.DatetimeIndex(_monthly.to_numpy()))
    _dates.append(_idx[0])                                     # 初始配置日
    return sorted(set(_dates))


def _equal_weights(codes: list) -> dict:
    _n = len(codes)
    return {c: 1.0 / _n for c in codes} if _n else {}


def tiers_to_weights(tier_by_code: dict, base_weight: float) -> "dict | None":
    """tier(buy/sell/watch/na)→ 目標權重:tilt×base,floor 0,歸一 Σ=1;全 0 → None(§1)。"""
    _f = {"buy": BACKTEST_TILT_BUY, "sell": BACKTEST_TILT_SELL}
    _raw = {c: max(base_weight * _f.get(t, 1.0), 0.0) for c, t in (tier_by_code or {}).items()}
    _tot = sum(_raw.values())
    if _tot <= 0:
        return None
    return {c: v / _tot for c, v in _raw.items()}


def _flip_fx(label):
    """匯率位階反向:strong_twd↔weak_twd,neutral/None 不變(S2 專用)。"""
    return {"strong_twd": "weak_twd", "weak_twd": "strong_twd"}.get(label, label)


def _sigma_rank_at(orig_series, t) -> "float | None":
    """原幣序列截至 t → σ rank(現價在 HWM 下方第幾 σ)。PIT-safe(只用 ≤ t 的資料)。

    §1 誠實:短史 / 報酬不足(委派 calc_hwm_sigma_levels 內部下限,不重複 magic number)/
    **σ_abs=0(NAV 走平・停售清算)→ sigma_rank 為未定義的 0.0** → 一律 None,
    **絕不**把 0.0 當「高基期」餵給 classify_base 產出假 SELL(稽核 v19.427 HIGH)。
    """
    from services.precision_service import calc_hwm_sigma_levels
    _lv = calc_hwm_sigma_levels(orig_series.loc[:t])
    if not isinstance(_lv, dict) or "error" in _lv:
        return None
    _sr, _sa = _lv.get("sigma_rank"), _lv.get("sigma_abs")
    if _sr is None or _sa is None or _sa <= 0:      # σ_abs≤0 → 統計退化,誠實回 None(不捏造)
        return None
    return float(_sr)


def strategy_weights_at(strategy_id: str, t, orig_by_code: dict, twd_df, fx_series,
                        s4_ctx: "dict | None" = None) -> tuple:
    """在再平衡日 t 用 PIT 資料算某策略目標權重。→ (weights dict Σ=1, signals dict)。

    S0/S4 不需訊號(等權 / 前緣靜態);S1/S2/S3 逐檔算 nav_level(σ rank)+(S1/S2)匯率位階。
    """
    from services.nav_fx_switch import fx_regime, nav_fx_signal
    from services.rotation import classify_base

    codes = list(twd_df.columns)
    if strategy_id == "S0":
        return _equal_weights(codes), {c: {"tier": "hold", "note": "等權買進持有"} for c in codes}
    if strategy_id == "S4":
        _ctx = s4_ctx or {}
        _tw = _ctx.get("weights")
        if _tw and t >= _ctx.get("train_date", t):
            return dict(_tw), {c: {"tier": "hold", "note": "前緣靜態最佳"} for c in codes}
        return _equal_weights(codes), {c: {"tier": "hold", "note": "前緣訓練前→等權"} for c in codes}

    # S1/S2/S3 逐檔 tier
    fx_label = None
    if strategy_id in ("S1", "S2") and fx_series is not None:
        _fxwin = fx_series.loc[t - pd.Timedelta(days=FX_REGIME_WINDOW_DAYS): t]
        if len(_fxwin) >= 2:
            _r = fx_regime(_fxwin, spot=float(_fxwin.iloc[-1]))
            fx_label = _r.get("regime")
        if strategy_id == "S2":
            fx_label = _flip_fx(fx_label)

    tiers: dict = {}
    signals: dict = {}
    for c in codes:
        _sr = _sigma_rank_at(orig_by_code[c], t) if c in orig_by_code else None
        _nav_level = classify_base(_sr) if _sr is not None else "unknown"
        if strategy_id == "S3":
            _tier = {"low": "buy", "high": "sell"}.get(_nav_level, "watch")
        else:                                                 # S1 / S2
            _tier = nav_fx_signal(_nav_level, fx_label)["tier"]
        tiers[c] = _tier
        signals[c] = {"tier": _tier, "nav_level": _nav_level,
                      "fx_label": fx_label, "sigma_rank": _sr}

    _w = tiers_to_weights(tiers, 1.0 / len(codes)) if codes else None
    return (_w if _w else _equal_weights(codes)), signals


# ───────────────────────── 單一策略回測 ─────────────────────────

def _weight_vec(w: "dict | None", codes: list):
    if w is None:
        return None
    return np.array([float(w.get(c, 0.0)) for c in codes], dtype=float)


def run_strategy(strategy_id: str, orig_by_code: dict, twd_df, fx_series, *,
                 freq: str = BACKTEST_REBALANCE_FREQ,
                 cost_bps: float = BACKTEST_COST_BPS,
                 fx_spread_bps: float = BACKTEST_FX_SPREAD_BPS,
                 foreign_codes: "set | None" = None,
                 s4_ctx: "dict | None" = None,
                 rf_annual: float = FRONTIER_RF_ANNUAL) -> dict:
    """單一策略月頻再平衡回測 → {metrics, equity_curve, daily_returns, final_weights,
    final_signals, weight_path}。§2.3:day d 的報酬用「d 之前最後一次再平衡」的權重(不吃未來)。"""
    from services.portfolio_performance import metrics_from_return_series

    codes = list(twd_df.columns)
    common = twd_df.index
    _blank = {"strategy_id": strategy_id, "metrics": metrics_from_return_series(pd.Series(dtype=float)),
              "equity_curve": None, "daily_returns": None,
              "final_weights": None, "final_signals": None, "weight_path": {}}
    if len(common) < 2 or not codes:
        return _blank

    rdates = rebalance_dates(common, freq)
    wmap: dict = {}
    smap: dict = {}
    for t in rdates:
        _w, _sig = strategy_weights_at(strategy_id, t, orig_by_code, twd_df, fx_series, s4_ctx)
        wmap[t] = _w
        smap[t] = _sig

    _R = twd_df.pct_change(fill_method=None)              # 首列 NaN(無前值),不填 + 不補值
    days = common[1:]
    _rd_ns = np.array([pd.Timestamp(t).value for t in rdates])
    _day_ns = np.array([pd.Timestamp(d).value for d in days])
    _pos = np.searchsorted(_rd_ns, _day_ns, side="left") - 1   # day 之前最後一次再平衡 index

    port_ret = pd.Series(0.0, index=days)
    _foreign = foreign_codes or set()
    for i, d in enumerate(days):
        _k = int(_pos[i])
        if _k < 0:
            continue                                     # 首個再平衡日之前(理論上不發生,rdates[0]=common[0])
        _wv = _weight_vec(wmap[rdates[_k]], codes)
        if _wv is None:
            continue
        _rrow = _R.loc[d].to_numpy()
        port_ret.iloc[i] = float(np.nansum(_wv * _rrow))

    # 換手成本:第 2 次(含)起的再平衡日,依 |Δw| 收一次性成本(§1 避免切換被高估)
    for _k in range(1, len(rdates)):
        _t = rdates[_k]
        if _t not in port_ret.index:                     # 只有 rdates[0]=common[0] 不在 days
            continue
        _wp = _weight_vec(wmap[rdates[_k - 1]], codes)
        _wc = _weight_vec(wmap[rdates[_k]], codes)
        if _wp is None or _wc is None:
            continue
        _dwabs = np.abs(_wc - _wp)
        _tot = float(_dwabs.sum())
        if _tot <= 0:
            continue
        _turnover = 0.5 * _tot
        _fx_notional = float(sum(_dwabs[j] for j, c in enumerate(codes) if c in _foreign))
        _fx_frac = _fx_notional / _tot
        _cost = _turnover * (cost_bps / 1e4 + _fx_frac * fx_spread_bps / 1e4)
        _r0 = float(port_ret.loc[_t])
        port_ret.loc[_t] = (1.0 + _r0) * (1.0 - _cost) - 1.0

    _metrics = metrics_from_return_series(port_ret, rf_annual)
    _equity = (1.0 + port_ret).cumprod()
    _final_t = rdates[-1]
    return {
        "strategy_id": strategy_id,
        "metrics": _metrics,
        "equity_curve": _equity,
        "daily_returns": port_ret,
        "final_weights": wmap.get(_final_t),
        "final_signals": smap.get(_final_t),
        "weight_path": {str(pd.Timestamp(t).date()): wmap[t] for t in rdates},
    }


# ───────────────────────── 前緣訓練(S4)─────────────────────────

def _s4_train(twd_df, rf_annual: float) -> dict:
    """S4 靜態權重:找首個「截至該再平衡日 ≥ FRONTIER_MIN_OBS 共同日」的日期,以其前段
    台幣報酬算 max-Sharpe 權重,之後固定持有。訓練不足 / 最佳化失敗 → weights None(全程等權 fallback)。"""
    from services.portfolio_frontier import annualized_moments, max_sharpe_portfolio

    rdates = rebalance_dates(twd_df.index)
    for _t in rdates:
        _hist = twd_df.loc[:_t]
        if len(_hist) < FRONTIER_MIN_OBS:
            continue
        _rdf = _hist.pct_change(fill_method=None).dropna(how="any")  # §1 不補值
        if len(_rdf) < FRONTIER_MIN_OBS:
            continue
        _mu, _sig, _codes = annualized_moments(_rdf)
        _res = max_sharpe_portfolio(_mu, _sig, rf_annual)
        if _res is None:
            return {"train_date": _t, "weights": None}
        _w = {c: float(_res["weights"][i]) for i, c in enumerate(_codes)}
        return {"train_date": _t, "weights": _w}
    return {"train_date": None, "weights": None}


# ───────────────────────── 當前建議(三輸出)─────────────────────────

def current_actions_from_signals(final_signals: dict, final_weights: dict) -> dict:
    """勝出策略當前訊號 → {action_lists(buy/switch/watch), sell_buy_pairs, target_weights_pct}。

    賣→買配對:每個 sell-tier 配一檔最便宜(σ rank 最負)的 buy-tier(round-robin);無 buy → None(誠實)。
    """
    _sig = final_signals or {}
    buy = [c for c, s in _sig.items() if s.get("tier") == "buy"]
    sell = [c for c, s in _sig.items() if s.get("tier") == "sell"]
    watch = [c for c, s in _sig.items() if s.get("tier") in ("watch", "na", "hold", None)]

    _buy_sorted = sorted(buy, key=lambda c: (_sig[c].get("sigma_rank")
                                             if _sig[c].get("sigma_rank") is not None else 0.0))
    pairs = []
    for i, sc in enumerate(sell):
        bc = _buy_sorted[i % len(_buy_sorted)] if _buy_sorted else None
        pairs.append({
            "sell_code": sc,
            "sell_sigma": _sig[sc].get("sigma_rank"),
            "buy_code": bc,
            "buy_sigma": (_sig[bc].get("sigma_rank") if bc else None),
        })

    _w = final_weights or {}
    weights_pct = {c: round(float(v) * 100.0, 2) for c, v in _w.items()}
    return {
        "action_lists": {"buy": buy, "switch": sell, "watch": watch},
        "sell_buy_pairs": pairs,
        "target_weights_pct": weights_pct,
    }


# ───────────────────────── 一站式編排 ─────────────────────────

def _rank_key(res: dict):
    """排名鍵:Sharpe→Calmar→CAGR 降冪;None 沉底。"""
    _m = res.get("metrics") or {}
    def _v(x):
        return x if isinstance(x, (int, float)) else float("-inf")
    return (_v(_m.get("sharpe")), _v(_m.get("calmar")), _v(_m.get("cagr_pct")))


def backtest_allocations(nav_by_code: dict, ccy_by_code: dict, fx_series=None, *,
                         freq: str = BACKTEST_REBALANCE_FREQ,
                         cost_bps: float = BACKTEST_COST_BPS,
                         fx_spread_bps: float = BACKTEST_FX_SPREAD_BPS,
                         rf_annual: float = FRONTIER_RF_ANNUAL) -> dict:
    """一站式:對齊 → 跑 S0..S4 → 排名 → 挑 winner → S1/S2 匯率方向裁決 → 由 winner 現況產三輸出。

    → {ok, reason, results{sid:...}, ranking[sid], winner, verdict_s1_vs_s2, actions,
       included, excluded, window, flags, caveat}。§1 全程誠實;缺料/短史 → ok False。
    """
    _fx = _clean_fx(fx_series)
    orig_by_code, twd_df, included, excluded, flags, foreign = build_aligned_matrices(
        nav_by_code, ccy_by_code, _fx)

    if twd_df is None or len(twd_df.columns) < 1:
        return {"ok": False, "excluded": excluded, "included": included, "caveat": CAVEAT,
                "reason": "無足夠可回測基金(需 ≥1 檔 USD/TWD 且有台幣序列)。"}
    _n = len(twd_df.index)
    if _n < BACKTEST_MIN_COMMON_DAYS:
        return {"ok": False, "excluded": excluded, "included": included, "caveat": CAVEAT,
                "reason": f"共同交易日僅 {_n}(<{BACKTEST_MIN_COMMON_DAYS}),樣本太少不回測。"}

    _s4 = _s4_train(twd_df, rf_annual)
    results: dict = {}
    for _sid in STRATEGY_IDS:
        results[_sid] = run_strategy(
            _sid, orig_by_code, twd_df, _fx, freq=freq, cost_bps=cost_bps,
            fx_spread_bps=fx_spread_bps, foreign_codes=foreign,
            s4_ctx=(_s4 if _sid == "S4" else None), rf_annual=rf_annual)

    ranking = sorted(STRATEGY_IDS, key=lambda s: _rank_key(results[s]), reverse=True)
    winner = ranking[0]

    _s1 = (results["S1"]["metrics"] or {}).get("sharpe")
    _s2 = (results["S2"]["metrics"] or {}).get("sharpe")
    if _s1 is None or _s2 is None:
        _pair_winner, _wording = None, "S1/S2 至少一方 Sharpe 無法計算,匯率方向無法裁決(§1)。"
    elif abs(_s1 - _s2) < 1e-9:
        _pair_winner, _wording = "tie", "S1 與 S2 表現相同,匯率方向對此組合無明顯區別。"
    else:
        _pair_winner = "S1" if _s1 > _s2 else "S2"
        _dir = "現行方向(低NAV+台幣強進場)" if _pair_winner == "S1" else "反向(低NAV+台幣弱進場)"
        _wording = (f"{_pair_winner}={_dir} 勝出(Sharpe {max(_s1, _s2):.2f} vs {min(_s1, _s2):.2f},"
                    f"{_n} 交易日);為**方向性證據**,樣本有限非統計顯著。")
    verdict = {"s1_sharpe": _s1, "s2_sharpe": _s2, "winner": _pair_winner,
               "delta": (None if (_s1 is None or _s2 is None) else round(_s1 - _s2, 3)),
               "wording": _wording}

    # 三輸出綁「勝出策略」→ 動作/配對/權重內部一致,不自相矛盾(§1)。
    # 若 winner 為 S0/S4(不擇時)→ 買賣清單自然為空(誠實:回測顯示不需切換)。
    actions = current_actions_from_signals(results[winner]["final_signals"],
                                           results[winner]["final_weights"])

    # (2026-08-07 移除)原本另外回傳一份「各檔當前 2D 訊號」快照給回測區的 expander。
    # 該 expander 已下架,production 0 consumer;且它取自 S1 最後再平衡日,與健診大表的
    # live 值是**兩個不同時點**的同名數字,同頁並列本身就是矛盾來源。
    # 依 `PROCESS.md §4` 0-consumer 條款刪除,不留一個沒人讀的側車欄位。
    # 需要 live 訊號請直接看健診大表(單一真相);歷史訊號在 results[sid]["final_signals"]。

    return {
        "ok": True, "reason": None, "results": results, "ranking": ranking, "winner": winner,
        "verdict_s1_vs_s2": verdict, "actions": actions,
        "included": included, "excluded": excluded,
        "window": {"start": str(twd_df.index[0].date()), "end": str(twd_df.index[-1].date()),
                   "n_days": _n},
        "flags": {**flags, "s4_trained": bool(_s4.get("weights") is not None)},
        "caveat": CAVEAT,
        "assumption": "月頻再平衡・段內固定權重日再平衡・台幣總報酬・換手含申贖+換匯成本",
    }
