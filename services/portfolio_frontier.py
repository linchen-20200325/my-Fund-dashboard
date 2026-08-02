"""services/portfolio_frontier.py — 效率前緣診斷(v19.424)。純函式,零 IO。**教學,非投資建議**。

§1 誠實:歷史平均當預期報酬(對未來預測力極弱)+ 樣本共變異數(噪音大 → 最佳化把噪音放大成
極端、不穩定的權重 = error maximization)。全程重 caveat,絕不把「最佳」權重當處方。
重用 `services.portfolio_performance` 的 `_clean_nav` + 共同交易日 intersection 對齊(§4.5 不 ffill)。
long-only(w≥0)、Σw=1。所有 vol/ret 內部用 **decimal**(0.12=12%);L3 顯示時 ×100。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from services.portfolio_performance import _clean_nav, _normalize_weights
from shared.signal_thresholds import (
    FRONTIER_COND_MAX,
    FRONTIER_GRID_SIZE,
    FRONTIER_MIN_OBS,
    FRONTIER_MU_SPREAD_MIN,
    FRONTIER_N_RANDOM,
    FRONTIER_RANDOM_SEED,
    FRONTIER_RF_ANNUAL,
    FRONTIER_RIDGE_EPS,
    FRONTIER_ROBUST_OBS,
    TRADING_DAYS_PER_YEAR,
)

CAVEAT = (
    "⚠️ 教學診斷,非投資建議:效率前緣用「歷史平均報酬」當預期報酬(對未來預測力極弱)、"
    "用「樣本共變異數」估風險 —— 樣本雜訊會被最佳化放大成極端且不穩定的權重"
    "(error maximization)。圖中「最佳」權重僅供理解風險/報酬取捨,切勿照抄;過去績效不代表未來。"
)


def aligned_returns_matrix(nav_by_code: dict):
    """各基金 NAV → 對齊共同交易日的每日報酬矩陣。→ (returns_df|None, codes, excluded, reason|None)。"""
    excluded: list = []
    cleaned: dict = {}
    for _code, _nav in (nav_by_code or {}).items():
        _s = _clean_nav(_nav)
        if _s is None:
            excluded.append({"code": _code, "reason": "NAV 序列不足(<2 有效點)"})
        else:
            cleaned[_code] = _s
    if len(cleaned) < 2:
        return None, list(cleaned.keys()), excluded, "效率前緣需至少 2 檔有共同歷史的基金(目前 <2)。"
    _common = None
    for _s in cleaned.values():
        _common = _s.index if _common is None else _common.intersection(_s.index)
    if _common is None or len(_common) < 2:
        return None, list(cleaned.keys()), excluded, "納入基金無共同交易日,無法對齊。"
    _nav_df = pd.DataFrame({_c: _s.loc[_common] for _c, _s in cleaned.items()}).sort_index()
    _rdf = _nav_df.pct_change().dropna(how="any")            # 丟首列(無前值),不偽造
    if len(_rdf) < 2:
        return None, list(cleaned.keys()), excluded, "共同交易日不足,無法算報酬。"
    return _rdf, list(_rdf.columns), excluded, None


def annualized_moments(returns_df: "pd.DataFrame") -> tuple:
    """→ (mu, Sigma, codes)。mu=年化平均(×252),Sigma=年化樣本共變異數(ddof=1 ×252),decimal。"""
    _mu = returns_df.mean().to_numpy() * TRADING_DAYS_PER_YEAR
    _sig = returns_df.cov().to_numpy() * TRADING_DAYS_PER_YEAR
    return _mu, _sig, list(returns_df.columns)


def _sharpe(w, mu, Sigma, rf: float):
    _ret = float(w @ mu)
    _var = float(w @ Sigma @ w)
    _vol = float(np.sqrt(max(_var, 0.0)))
    return (_ret, _vol, ((_ret - rf) / _vol if _vol > 0 else None))


def _bounds_x0(K: int):
    return tuple((0.0, 1.0) for _ in range(K)), np.full(K, 1.0 / K)


def min_variance_portfolio(mu, Sigma, rf_annual: float = 0.0):
    """min wᵀΣw s.t. Σw=1, 0≤w≤1。非收斂 → None。"""
    K = len(mu)
    _bounds, _x0 = _bounds_x0(K)
    _cons = ({"type": "eq", "fun": lambda w: float(w.sum() - 1.0), "jac": lambda w: np.ones(K)},)
    _res = minimize(lambda w: float(w @ Sigma @ w), _x0, method="SLSQP",
                    jac=lambda w: 2.0 * Sigma @ w, bounds=_bounds, constraints=_cons,
                    options={"maxiter": 500, "ftol": 1e-9})
    if not _res.success:
        return None
    _ret, _vol, _sh = _sharpe(_res.x, mu, Sigma, rf_annual)
    return {"vol": _vol, "ret": _ret, "sharpe": _sh, "weights": _res.x}


def max_sharpe_portfolio(mu, Sigma, rf_annual: float = 0.0):
    """max (wᵀμ−rf)/√(wᵀΣw) s.t. Σw=1, 0≤w≤1(對 −Sharpe 極小化)。非收斂/σ≈0 → None。"""
    K = len(mu)
    _bounds, _x0 = _bounds_x0(K)
    _cons = ({"type": "eq", "fun": lambda w: float(w.sum() - 1.0), "jac": lambda w: np.ones(K)},)

    def _neg_sharpe(w):
        _r, _v, _s = _sharpe(w, mu, Sigma, rf_annual)
        return 1e6 if _s is None else -_s          # σ≈0 → 重罰,避免最佳化衝向奇異點

    _res = minimize(_neg_sharpe, _x0, method="SLSQP", bounds=_bounds, constraints=_cons,
                    options={"maxiter": 500, "ftol": 1e-9})
    if not _res.success:
        return None
    _ret, _vol, _sh = _sharpe(_res.x, mu, Sigma, rf_annual)
    if _sh is None:
        return None
    return {"vol": _vol, "ret": _ret, "sharpe": _sh, "weights": _res.x}


def efficient_frontier(mu, Sigma, *, grid_size: int = FRONTIER_GRID_SIZE) -> list:
    """target ∈ linspace(min μ, max μ, grid_size) 上逐點 min wᵀΣw s.t. wᵀμ=target, Σw=1, w≥0。

    只收 res.success 的點(§1 跳過非收斂,不外插)。warm-start:前一格解當下格 x0。
    → list[{"vol","ret","weights"}](可能 < grid_size)。
    """
    K = len(mu)
    _bounds, _x0 = _bounds_x0(K)
    _targets = np.linspace(float(mu.min()), float(mu.max()), grid_size)
    _out: list = []
    _warm = _x0
    for _t in _targets:
        _cons = (
            {"type": "eq", "fun": (lambda w, t=_t: float(w @ mu - t)), "jac": lambda w: mu},
            {"type": "eq", "fun": lambda w: float(w.sum() - 1.0), "jac": lambda w: np.ones(K)},
        )
        _res = minimize(lambda w: float(w @ Sigma @ w), _warm, method="SLSQP",
                        jac=lambda w: 2.0 * Sigma @ w, bounds=_bounds, constraints=_cons,
                        options={"maxiter": 500, "ftol": 1e-9})
        if _res.success:
            _w = _res.x
            _vol = float(np.sqrt(max(_w @ Sigma @ _w, 0.0)))
            _out.append({"vol": _vol, "ret": float(_w @ mu), "weights": _w})
            _warm = _w
    return _out


def random_portfolio_cloud(mu, Sigma, *, n: int = FRONTIER_N_RANDOM,
                           rf_annual: float = 0.0, seed: int = FRONTIER_RANDOM_SEED) -> dict:
    """N 個 long-only 隨機權重(Dirichlet → 單體均勻),向量化。→ {vol[N], ret[N], sharpe[N]}。"""
    K = len(mu)
    _rng = np.random.default_rng(seed)
    _W = _rng.dirichlet(np.ones(K), size=n)             # (N,K),每列 sum=1、≥0
    _ret = _W @ mu
    _vol = np.sqrt(np.maximum(np.einsum("ij,jk,ik->i", _W, Sigma, _W), 0.0))
    # np.divide(where=) 避免對 vol=0 列先除再遮罩的 RuntimeWarning(結果同 nan;稽核 Finding 4)
    _sh = np.divide(_ret - rf_annual, _vol, out=np.full_like(_vol, np.nan), where=_vol > 0)
    return {"vol": _vol, "ret": _ret, "sharpe": _sh}


def portfolio_point(mu, Sigma, weights_vec, rf_annual: float = 0.0) -> dict:
    """任意權重向量在同一 μ/Σ 空間的座標(current portfolio 點)。"""
    _w = np.asarray(weights_vec, dtype=float)
    _ret, _vol, _sh = _sharpe(_w, mu, Sigma, rf_annual)
    return {"vol": _vol, "ret": _ret, "sharpe": _sh, "weights": _w}


def _maybe_ridge(Sigma):
    """近奇異(cond>MAX 或 min 特徵值≤0)→ 加微脊。→ (Sigma_used, near_singular, ridge_applied)。"""
    try:
        _cond = float(np.linalg.cond(Sigma))
        _min_eig = float(np.linalg.eigvalsh(Sigma).min())
    except np.linalg.LinAlgError:
        _cond, _min_eig = np.inf, -1.0
    _near = (not np.isfinite(_cond)) or _cond > FRONTIER_COND_MAX or _min_eig <= 0
    if not _near:
        return Sigma, False, False
    _eps = FRONTIER_RIDGE_EPS * float(np.mean(np.diag(Sigma))) or FRONTIER_RIDGE_EPS
    return Sigma + _eps * np.eye(len(Sigma)), True, True


def efficient_frontier_diagnostic(nav_by_code: dict, weights: dict, *,
                                  rf_annual: float = FRONTIER_RF_ANNUAL,
                                  n_random: int = FRONTIER_N_RANDOM,
                                  grid_size: int = FRONTIER_GRID_SIZE,
                                  seed: int = FRONTIER_RANDOM_SEED) -> dict:
    """一站式:對齊 → moments → 前緣 + max-Sharpe + min-var + 隨機雲 + current 點。§1 全程誠實。"""
    _rdf, _codes, _excluded, _reason = aligned_returns_matrix(nav_by_code)
    if _rdf is None:
        return {"ok": False, "reason": _reason, "excluded": _excluded, "caveat": CAVEAT}
    _n = len(_rdf)
    if _n < FRONTIER_MIN_OBS:
        return {"ok": False, "excluded": _excluded, "caveat": CAVEAT,
                "reason": f"共同歷史僅 {_n} 交易日(<{FRONTIER_MIN_OBS}),樣本太少,前緣不可靠故不計算。"}

    _mu, _sigma, _codes = annualized_moments(_rdf)
    _sigma_used, _near, _ridge = _maybe_ridge(_sigma)
    _zero_var = [_codes[i] for i in range(len(_codes)) if _sigma[i, i] <= 1e-12]
    _mu_degen = bool(float(_mu.max() - _mu.min()) < FRONTIER_MU_SPREAD_MIN)

    _w = _normalize_weights(weights or {}, _codes)
    _cur = None
    if _w is not None:
        _wvec = np.array([_w.get(c, 0.0) for c in _codes], dtype=float)
        _cur = portfolio_point(_mu, _sigma_used, _wvec, rf_annual)
        _cur["weights"] = {c: float(_wvec[i]) for i, c in enumerate(_codes)}

    _front = [] if _mu_degen else efficient_frontier(_mu, _sigma_used, grid_size=grid_size)
    _ms = max_sharpe_portfolio(_mu, _sigma_used, rf_annual)
    _mv = min_variance_portfolio(_mu, _sigma_used, rf_annual)
    _cloud = random_portfolio_cloud(_mu, _sigma_used, n=n_random, rf_annual=rf_annual, seed=seed)

    def _wdict(p):
        if p is None:
            return None
        return {**p, "weights": {c: float(p["weights"][i]) for i, c in enumerate(_codes)}}

    return {
        "ok": True, "reason": None, "codes": _codes, "excluded": _excluded,
        "n_days": _n, "start": str(_rdf.index[0].date()), "end": str(_rdf.index[-1].date()),
        "mu_annual": {c: float(_mu[i]) for i, c in enumerate(_codes)},
        "vol_diag_annual": {c: float(np.sqrt(max(_sigma[i, i], 0.0))) for i, c in enumerate(_codes)},
        "frontier": [{"vol": p["vol"], "ret": p["ret"],
                      "weights": {c: float(p["weights"][i]) for i, c in enumerate(_codes)}}
                     for p in _front],
        "max_sharpe": _wdict(_ms), "min_var": _wdict(_mv), "current": _cur,
        "random_cloud": {"vol": _cloud["vol"].tolist(), "ret": _cloud["ret"].tolist(),
                         "sharpe": _cloud["sharpe"].tolist()},
        "rf_annual": rf_annual,
        "flags": {
            "near_singular": _near, "ridge_applied": _ridge, "zero_variance_codes": _zero_var,
            "mu_degenerate": _mu_degen, "low_confidence": bool(_n < FRONTIER_ROBUST_OBS),
            "n_frontier_converged": len(_front), "n_frontier_requested": (0 if _mu_degen else grid_size),
        },
        "caveat": CAVEAT,
        "assumption": "arithmetic-mean mu (x252) + sample-cov Sigma (x252); long-only; sum(w)=1",
    }
