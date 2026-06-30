"""services/macro/turning_points.py — v19.199 P1-7 景氣拐點偵測 + 歷史回測。

從 macro_service 主檔抽出(原 line 1759-2261)。
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from repositories.macro_repository import fetch_fred, fetch_yf_close
from shared.colors import MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED, TRAFFIC_NEUTRAL

from services.macro._helpers import (  # noqa: F401
    FRED_AMTMNO, FRED_DGS10, FRED_DGS2, FRED_MNFCTRIRSA, FRED_T10Y2Y,
    _trend, _safe_last,
)


def _yoy_pct(df: pd.DataFrame, periods: int = 12) -> pd.Series:
    """月頻 DataFrame → YoY %（與 12 個月前比較）。回傳 pd.Series（index=date, 值=%）。"""
    if df is None or df.empty or len(df) < periods + 2:
        return pd.Series(dtype=float)
    s = df.sort_values("date").set_index("date")["value"].astype(float)
    return (s / s.shift(periods) - 1.0) * 100.0


def detect_turning_points(fred_api_key: str = "") -> dict:
    """景氣拐點偵測 (v18.20)

    指標一：新訂單 YoY − 庫存 YoY（製造業 M3 調查代理 ISM 新訂單－庫存擴散）
        - FRED AMTMNO   : Manufacturers' New Orders: Total Manufacturing（月頻）
        - FRED MNFCTRIRSA: Manufacturers' Total Inventories（月頻）
        - 訊號邏輯：近 3 月 (orders_yoy − inv_yoy) 序列若前一期 ≤ 0 而本期 > 0
          → 🚀 擴張拐點已現；否則回報目前狀態（擴張中 / 收縮中 / 持平）
        - 說明：ISM 自 2016-08 起對 FRED 收回授權，FRED 已無 ISM 子分項細項；
          M3 調查（Census）為次優替代，與 ISM 新訂單－庫存相關性 ~0.7

    指標二：10Y − 2Y 殖利率利差（T10Y2Y）
        - FRED T10Y2Y（日頻）
        - 訊號邏輯：最近 60 日內曾倒掛（min < 0）且最新值 ≥ 0 → ⚠️ 衰退末期反彈
          否則回報「正斜率」/「倒掛」/「資料不足」

    Returns
    -------
    {
      "pmi_diff":    {signal, color, icon, value, prev, trend(list), label, note, source_ok},
      "yield_curve": {signal, color, icon, value, prev, trend(list), label, note, source_ok},
    }
    """
    out: dict = {
        "pmi_diff": {
            "signal": "⬜ 資料不足", "color": TRAFFIC_NEUTRAL, "icon": "⬜",
            "value": None, "prev": None, "trend": [],
            "label": "新訂單 YoY − 庫存 YoY (M3 製造業)",
            "note": "FRED API 失敗或資料不足", "source_ok": False,
        },
        "yield_curve": {
            "signal": "⬜ 資料不足", "color": TRAFFIC_NEUTRAL, "icon": "⬜",
            "value": None, "prev": None, "trend": [],
            "label": "10Y − 2Y 利差 (T10Y2Y)",
            "note": "FRED API 失敗或資料不足", "source_ok": False,
        },
        # v18.250 新增三組景氣反轉拐點
        "hy_spread": {
            "signal": "⬜ 資料不足", "color": TRAFFIC_NEUTRAL, "icon": "⬜",
            "value": None, "prev": None, "trend": [],
            "label": "HY 信用利差 (BAMLH0A0HYM2)",
            "note": "FRED API 失敗或資料不足", "source_ok": False,
        },
        "sahm_rule": {
            "signal": "⬜ 資料不足", "color": TRAFFIC_NEUTRAL, "icon": "⬜",
            "value": None, "prev": None, "trend": [],
            "label": "薩姆規則 (SAHMREALTIME)",
            "note": "FRED API 失敗或資料不足", "source_ok": False,
        },
        "lei_cfnai": {
            "signal": "⬜ 資料不足", "color": TRAFFIC_NEUTRAL, "icon": "⬜",
            "value": None, "prev": None, "trend": [],
            "label": "CFNAI 領先指標 3M MA",
            "note": "FRED API 失敗或資料不足", "source_ok": False,
        },
    }

    if not fred_api_key:
        return out

    # v19.48 並行化：5 個拐點抽成 inner func + ThreadPoolExecutor，wallclock 2-4s → ~max 單拐點
    def _calc_pmi_diff() -> tuple[str, dict]:
        try:
            df_new = fetch_fred(FRED_AMTMNO,     fred_api_key, n=60)
            df_inv = fetch_fred(FRED_MNFCTRIRSA, fred_api_key, n=60)
            ny = _yoy_pct(df_new)
            iy = _yoy_pct(df_inv)
            if ny.empty or iy.empty:
                return "pmi_diff", {}
            joined = pd.concat([ny.rename("o"), iy.rename("i")], axis=1).dropna().tail(12)
            if len(joined) < 2:
                return "pmi_diff", {}
            diff = (joined["o"] - joined["i"]).tolist()
            cur, prev = diff[-1], diff[-2]
            trend = [round(v, 2) for v in diff[-6:]]
            if prev <= 0 and cur > 0:
                sig, col, ic = "🚀 擴張拐點已現", MATERIAL_GREEN, "🚀"
                note = (f"前期 {prev:+.1f}pp → 本期 {cur:+.1f}pp（由負轉正）"
                        f"｜製造業新訂單成長動能首度超越庫存補貨")
            elif cur > 0 and prev > 0:
                sig, col, ic = "🟢 擴張延續", MATERIAL_GREEN, "🟢"
                note = f"連續正值 {cur:+.1f}pp，新訂單動能 > 庫存補貨"
            elif cur < 0 and prev > 0:
                sig, col, ic = "🟡 動能轉弱", MATERIAL_ORANGE, "🟡"
                note = f"前期 {prev:+.1f}pp → 本期 {cur:+.1f}pp（由正轉負）需觀察"
            elif cur < 0:
                sig, col, ic = "🔻 收縮中", MATERIAL_RED, "🔻"
                note = f"{cur:+.1f}pp，新訂單動能弱於庫存補貨"
            else:
                sig, col, ic = "📊 持平", TRAFFIC_NEUTRAL, "📊"
                note = f"{cur:+.1f}pp，無明確方向"
            return "pmi_diff", {
                "signal": sig, "color": col, "icon": ic,
                "value": round(cur, 2), "prev": round(prev, 2),
                "trend": trend, "note": note, "source_ok": True,
            }
        except Exception as e:
            return "pmi_diff", {"note": f"AMTMNO/MNFCTRIRSA 抓取異常：{str(e)[:80]}"}

    def _calc_yield_curve() -> tuple[str, dict]:
        try:
            df_t = fetch_fred(FRED_T10Y2Y, fred_api_key, n=120)
            if df_t.empty or len(df_t) < 30:
                return "yield_curve", {}
            s = df_t.sort_values("date").set_index("date")["value"].astype(float).dropna()
            window60 = s.tail(60)
            cur = float(s.iloc[-1])
            prev = float(s.iloc[-2]) if len(s) >= 2 else None
            min60 = float(window60.min())
            trend = [round(v, 2) for v in s.tail(60).resample("W").last().dropna().tail(8).tolist()]
            if min60 < 0 and cur >= 0:
                sig, col, ic = "⚠️ 衰退末期，布局反彈", MATERIAL_ORANGE, "⚠️"
                note = (f"近 60 日最低 {min60:+.2f}%（倒掛）→ 最新 {cur:+.2f}%（翻正）"
                        f"｜歷史經驗：倒掛翻正後 6~18 月為股市底部累積期")
            elif cur < 0:
                sig, col, ic = "🔴 倒掛中", MATERIAL_RED, "🔴"
                note = f"{cur:+.2f}%（仍倒掛），衰退預警維持"
            elif cur >= 0 and min60 >= 0:
                sig, col, ic = "🟢 正斜率（健康）", MATERIAL_GREEN, "🟢"
                note = f"{cur:+.2f}%（近 60 日皆 ≥0），無拐點訊號"
            else:
                sig, col, ic = "📊 持平", TRAFFIC_NEUTRAL, "📊"
                note = f"{cur:+.2f}%"
            return "yield_curve", {
                "signal": sig, "color": col, "icon": ic,
                "value": round(cur, 2),
                "prev": round(prev, 2) if prev is not None else None,
                "trend": trend, "note": note, "source_ok": True,
            }
        except Exception as e:
            return "yield_curve", {"note": f"T10Y2Y 抓取異常：{str(e)[:80]}"}

    def _calc_hy_spread() -> tuple[str, dict]:
        try:
            df_hy = fetch_fred(FRED_HY_SPREAD, fred_api_key, n=400)
            if df_hy.empty or len(df_hy) < 30:
                return "hy_spread", {}
            s = df_hy.sort_values("date").set_index("date")["value"].astype(float).dropna()
            cur = float(s.iloc[-1]); prev = float(s.iloc[-2])
            max90 = float(s.tail(90).max())
            trend = [round(v, 2) for v in s.tail(60).resample("W").last().dropna().tail(8).tolist()]
            if max90 >= 6.0 and cur < max90 * 0.85 and cur < prev:
                sig, col, ic = "🚀 信用拐點：高位回落", MATERIAL_GREEN, "🚀"
                note = (f"90 日高點 {max90:.2f}% → 最新 {cur:.2f}%（-{max90-cur:.2f}pp）"
                        f"｜信用風險溢價收斂，risk-on 醞釀")
            elif cur >= 6:
                sig, col, ic = "🔴 高風險區", MATERIAL_RED, "🔴"
                note = f"{cur:.2f}% ≥ 6%，信用市場警戒中"
            elif cur < 4:
                sig, col, ic = "🟢 信用寬鬆", MATERIAL_GREEN, "🟢"
                note = f"{cur:.2f}% < 4%，市場樂觀（尚無拐點）"
            else:
                sig, col, ic = "🟡 中性帶", MATERIAL_ORANGE, "🟡"
                note = f"{cur:.2f}%，介於 4~6%（待觀察方向）"
            return "hy_spread", {
                "signal": sig, "color": col, "icon": ic,
                "value": round(cur, 2), "prev": round(prev, 2),
                "trend": trend, "note": note, "source_ok": True,
            }
        except Exception as e:
            return "hy_spread", {"note": f"BAMLH0A0HYM2 抓取異常：{str(e)[:80]}"}

    def _calc_sahm() -> tuple[str, dict]:
        try:
            df_sa = fetch_fred(FRED_SAHM, fred_api_key, n=36)
            if df_sa.empty or len(df_sa) < 6:
                return "sahm_rule", {}
            s = df_sa.sort_values("date").set_index("date")["value"].astype(float).dropna()
            cur = float(s.iloc[-1]); prev = float(s.iloc[-2])
            max12 = float(s.tail(12).max())
            trend = [round(v, 2) for v in s.tail(8).tolist()]
            if max12 >= 0.5 and cur < 0.5:
                sig, col, ic = "🚀 衰退警報解除", MATERIAL_GREEN, "🚀"
                note = (f"近 12 月高點 {max12:.2f}（觸發過 0.5）→ 最新 {cur:.2f}"
                        f"｜歷史經驗：解除後 12 月內為股市底部布局期")
            elif cur >= 0.5:
                sig, col, ic = "🔴 衰退警報中", MATERIAL_RED, "🔴"
                note = f"{cur:.2f} ≥ 0.5，失業率上升訊號"
            elif cur < 0.3:
                sig, col, ic = "🟢 安全區", MATERIAL_GREEN, "🟢"
                note = f"{cur:.2f} < 0.3，無衰退訊號"
            else:
                sig, col, ic = "🟡 警戒中", MATERIAL_ORANGE, "🟡"
                note = f"{cur:.2f}，介於 0.3~0.5（接近觸發）"
            return "sahm_rule", {
                "signal": sig, "color": col, "icon": ic,
                "value": round(cur, 2), "prev": round(prev, 2),
                "trend": trend, "note": note, "source_ok": True,
            }
        except Exception as e:
            return "sahm_rule", {"note": f"SAHMREALTIME 抓取異常：{str(e)[:80]}"}

    def _calc_lei() -> tuple[str, dict]:
        try:
            df_lei = fetch_fred(FRED_CFNAI, fred_api_key, n=36)
            if df_lei.empty or len(df_lei) < 6:
                return "lei_cfnai", {}
            s = df_lei.sort_values("date").set_index("date")["value"].astype(float).dropna()
            ma3 = s.rolling(3).mean().dropna()
            if len(ma3) < 2:
                return "lei_cfnai", {}
            cur = float(ma3.iloc[-1]); prev = float(ma3.iloc[-2])
            trend = [round(v, 2) for v in ma3.tail(8).tolist()]
            if cur > 0 and prev <= 0:
                sig, col, ic = "🚀 領先指標翻揚", MATERIAL_GREEN, "🚀"
                note = (f"3M MA：前期 {prev:+.2f} → 本期 {cur:+.2f}（由負轉正）"
                        f"｜85 指標 z-score 平均轉正，景氣進入擴張")
            elif cur > 0:
                sig, col, ic = "🟢 擴張中", MATERIAL_GREEN, "🟢"
                note = f"3M MA {cur:+.2f}（正值），景氣正常擴張"
            elif cur < -0.7:
                sig, col, ic = "🔴 衰退預警", MATERIAL_RED, "🔴"
                note = f"3M MA {cur:+.2f} < -0.7，強烈衰退訊號"
            elif cur < 0:
                sig, col, ic = "🟡 動能轉弱", MATERIAL_ORANGE, "🟡"
                note = f"3M MA {cur:+.2f}（負值但 > -0.7），待觀察"
            else:
                sig, col, ic = "📊 持平", TRAFFIC_NEUTRAL, "📊"
                note = f"3M MA {cur:+.2f}"
            return "lei_cfnai", {
                "signal": sig, "color": col, "icon": ic,
                "value": round(cur, 2), "prev": round(prev, 2),
                "trend": trend, "note": note, "source_ok": True,
            }
        except Exception as e:
            return "lei_cfnai", {"note": f"CFNAI 抓取異常：{str(e)[:80]}"}

    from concurrent.futures import ThreadPoolExecutor as _TPE_tp
    _jobs_tp = [_calc_pmi_diff, _calc_yield_curve, _calc_hy_spread, _calc_sahm, _calc_lei]
    with _TPE_tp(max_workers=5) as _ex_tp:
        _futs_tp = [_ex_tp.submit(_fn) for _fn in _jobs_tp]
        for _fut_tp in _futs_tp:
            try:
                _key, _payload = _fut_tp.result(timeout=25)
                if _payload:
                    out[_key].update(_payload)
            except Exception as e:
                # 並行框架異常 — 不阻斷其他拐點
                print(f"[detect_turning_points] parallel worker exception: {type(e).__name__}: {e}")
    return out


# ══════════════════════════════════════════════════════════════════
# v18.21 倒掛翻正歷史回測（Leading Indicator Backtest）
# ══════════════════════════════════════════════════════════════════
def _find_uninversion_events(s: pd.Series,
                             min_inversion_depth: float,
                             stable_days: int,
                             cooldown_days: int) -> list:
    """掃描 T10Y2Y 序列，識別所有「真倒掛 → 穩定翻正」事件。

    事件定義（同時滿足）：
      1. 區段內 min(T10Y2Y) ≤ min_inversion_depth（去除貼地噪音）
      2. 翻正日 T10Y2Y ≥ 0 且後續 stable_days 日皆 ≥ 0（穩定翻正去抖）
      3. 距上一事件 ≥ cooldown_days（避免同週期重複觸發）

    Returns: [{"date": Timestamp, "t10y2y_min_pre": float}, ...]
    """
    if s is None or s.empty or len(s) < stable_days + 2:
        return []
    s = s.sort_index().dropna()
    vals  = s.values
    dates = s.index

    events: list = []
    in_inversion = False
    seg_min      = 0.0
    last_event_t = None

    for i in range(len(vals)):
        v = vals[i]
        if v < 0:
            if not in_inversion:
                in_inversion = True
                seg_min = v
            else:
                seg_min = min(seg_min, v)
        else:
            # 候選翻正日
            if in_inversion and seg_min <= min_inversion_depth:
                # 驗 stable_days 天皆 ≥ 0
                end = i + stable_days
                if end <= len(vals) and (vals[i:end] >= 0).all():
                    t = dates[i]
                    if last_event_t is None or (t - last_event_t).days >= cooldown_days:
                        events.append({
                            "date": t,
                            "t10y2y_min_pre": float(round(seg_min, 3)),
                        })
                        last_event_t = t
            in_inversion = False
            seg_min      = 0.0
    return events


def _forward_return(spx: pd.Series, t0: pd.Timestamp, days: int):
    """SPX 從 t0 起 days 天後的累計報酬（%）。窗口未到期回 None。"""
    if spx is None or spx.empty:
        return None
    try:
        # t0 最近後續交易日（含當日）
        idx0 = spx.index.searchsorted(t0)
        if idx0 >= len(spx):
            return None
        p0 = float(spx.iloc[idx0])
        t1 = t0 + pd.Timedelta(days=days)
        idx1 = spx.index.searchsorted(t1)
        if idx1 >= len(spx):
            return None
        p1 = float(spx.iloc[idx1])
        if p0 <= 0:
            return None
        return round((p1 / p0 - 1.0) * 100.0, 2)
    except Exception as e:
        # v19.184 F-MED:加 stderr log(§3.3 反捏造)
        import sys as _sys
        print(f'[macro_service] _daily_spx_return fail: '
              f'{type(e).__name__}: {e}', file=_sys.stderr)
        return None


def backtest_turning_points(
    fred_api_key: str = "",
    min_inversion_depth: float = -0.10,
    stable_days: int = 5,
    cooldown_days: int = 365,
) -> dict:
    """倒掛翻正歷史回測（v18.21）

    抓 30Y+ T10Y2Y 日頻 + ^GSPC 全歷史，識別所有「倒掛→翻正」事件，
    對每事件計算 SPX 後續 6M / 12M / 18M 累計報酬，及樣本中位數與勝率。

    Parameters
    ----------
    min_inversion_depth: float, default -0.10
        倒掛深度門檻（%），需 ≤ 此值才算真倒掛
    stable_days: int, default 5
        翻正後須連續 ≥0 天數
    cooldown_days: int, default 365
        兩事件最小間隔（避免同週期重複觸發）

    Returns
    -------
    {
      "events": [
        {"date": Timestamp, "t10y2y_min_pre": float,
         "ret_6m": float|None, "ret_12m": float|None, "ret_18m": float|None,
         "complete": bool},  # complete=False 表示 18M 窗口未到期
        ...
      ],
      "summary": {"n_events": int, "n_complete_18m": int,
                  "median_6m/12m/18m": float, "mean_6m/12m/18m": float,
                  "win_rate_6m/12m/18m": float},
      "spx_series":   pd.Series,
      "t10y2y_series": pd.Series,
      "source_ok": bool,
      "note": str,
    }
    """
    out: dict = {
        "events": [],
        "summary": {"n_events": 0, "n_complete_18m": 0,
                    "median_6m": None,  "median_12m": None, "median_18m": None,
                    "mean_6m":   None,  "mean_12m":   None, "mean_18m":   None,
                    "win_rate_6m": None, "win_rate_12m": None, "win_rate_18m": None},
        "spx_series":    pd.Series(dtype=float),
        "t10y2y_series": pd.Series(dtype=float),
        "source_ok": False,
        "note": "",
    }

    if not fred_api_key:
        out["note"] = "FRED API key 未設置"
        return out

    # ── 抓 T10Y2Y 30Y+ ───────────────────────────────────────────
    try:
        df_t = fetch_fred(FRED_T10Y2Y, fred_api_key, n=11000)
    except Exception as e:
        out["note"] = f"T10Y2Y 抓取異常：{str(e)[:80]}"
        return out
    if df_t is None or df_t.empty or len(df_t) < 1000:
        out["note"] = "T10Y2Y 資料不足（< 1000 obs）"
        return out

    s_t = (df_t.sort_values("date").set_index("date")["value"]
                 .astype(float).dropna())
    try:
        s_t.index = s_t.index.tz_localize(None)
    except (AttributeError, TypeError):
        pass
    out["t10y2y_series"] = s_t

    # ── 抓 SPX 全歷史（v18.251 多 range 備援，避免 max 失敗）──────
    spx = None
    _spx_tried: list[str] = []
    for _rng in ("max", "30y", "20y", "10y", "5y"):
        try:
            _candidate = fetch_yf_close("^GSPC", range_=_rng, interval="1d")
            _spx_tried.append(f"{_rng}={len(_candidate) if _candidate is not None else 0}")
            if _candidate is not None and not _candidate.empty:
                spx = _candidate if spx is None or len(_candidate) > len(spx) else spx
                if spx is not None and len(spx) >= 1000:
                    break
        except Exception as e:
            _spx_tried.append(f"{_rng}=ERR:{type(e).__name__}")
            continue
    if spx is None or spx.empty or len(spx) < 1000:
        out["note"] = (
            f"SPX history insufficient (< 1000 trading days)"
            f" — Yahoo Chart 多 range 嘗試結果：{', '.join(_spx_tried)}"
        )
        return out
    try:
        spx.index = spx.index.tz_localize(None)
    except (AttributeError, TypeError):
        pass
    out["spx_series"] = spx.sort_index()

    # ── 事件識別 ────────────────────────────────────────────────
    events = _find_uninversion_events(
        s_t, min_inversion_depth=min_inversion_depth,
        stable_days=stable_days, cooldown_days=cooldown_days,
    )

    # ── 對每事件計算 SPX +6M/+12M/+18M 報酬 ──────────────────────
    today = pd.Timestamp.today().normalize()
    enriched: list = []
    for ev in events:
        t0 = ev["date"]
        r6  = _forward_return(out["spx_series"], t0, 182)
        r12 = _forward_return(out["spx_series"], t0, 365)
        r18 = _forward_return(out["spx_series"], t0, 547)
        complete = (today - t0).days >= 547 and r18 is not None
        enriched.append({
            "date": t0,
            "t10y2y_min_pre": ev["t10y2y_min_pre"],
            "ret_6m":  r6,
            "ret_12m": r12,
            "ret_18m": r18,
            "complete": complete,
        })
    out["events"] = enriched

    # ── Summary 統計（只納完整窗口）─────────────────────────────
    def _stat(key: str, require_complete: bool = False):
        vals = [e[key] for e in enriched
                if e[key] is not None
                and (e["complete"] if require_complete else True)]
        if not vals:
            return None, None, None
        med = float(np.median(vals))
        avg = float(np.mean(vals))
        wr  = float(sum(1 for v in vals if v > 0) / len(vals) * 100.0)
        return round(med, 2), round(avg, 2), round(wr, 1)

    m6,  a6,  w6  = _stat("ret_6m")
    m12, a12, w12 = _stat("ret_12m")
    m18, a18, w18 = _stat("ret_18m", require_complete=True)

    out["summary"].update({
        "n_events":        len(enriched),
        "n_complete_18m":  sum(1 for e in enriched if e["complete"]),
        "median_6m":   m6,  "median_12m": m12, "median_18m": m18,
        "mean_6m":     a6,  "mean_12m":   a12, "mean_18m":   a18,
        "win_rate_6m": w6,  "win_rate_12m": w12, "win_rate_18m": w18,
    })
    out["source_ok"] = True
    out["note"] = f"識別 {len(enriched)} 個事件（去抖 stable={stable_days}d, depth≤{min_inversion_depth}）"
    return out


# ════════════════════════════════════════════════════════════
# v18.100 景氣循環細項燈號（Phase 2 — Sub-Cycle Lights）
# 7 個子領域，各取 1-2 個既有指標 z-score 平均 → 🟢🟡🔴
# ════════════════════════════════════════════════════════════
_SUB_CYCLE_SPEC = [
    # (name, icon, [(indicator_key, high_is_bad)], description)
    ("製造業",   "🏭", [("PMI", False), ("LEI", False)],
     "ISM PMI 50 線 + CFNAI 領先指標"),
    ("房市",     "🏠", [("PERMIT_HOUSING", False)],
     "建照核發年化（領先 6-12 個月）"),
    ("就業",     "💼", [("JOBLESS", True), ("CONT_CLAIMS", True)],
     "初領 + 持續失業金（裁員領先指標）"),
    ("信貸",     "💳", [("SLOOS", True), ("HY_SPREAD", True)],
     "銀行放貸意願 + 高收益債利差"),
    ("流動性",   "💧", [("M2", False), ("FED_BS", False)],
     "M2 貨幣供給 + Fed 資產負債表年增"),
    ("消費",     "🛒", [("CONSUMER_CONF", False), ("COPPER", False)],
     "Michigan 消費信心 + 銅博士月漲跌"),
    ("通膨壓力", "🔥", [("CPI", True), ("PPI", True)],
     "CPI + PPI 年增（越低越好）"),
]
