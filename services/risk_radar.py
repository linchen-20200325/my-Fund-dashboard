"""v19.20 短線風險雷達 (Risk-Off Velocity Radar) — 10 燈快速訊號

設計動機（v19.20 epic）：
拐點偵測中心 5 大訊號全是「月～季級慢速 macro inflection」(PMI/Sahm/CFNAI/yield curve/HY 90D max)，
對 6/5/2026 那種「1-day 急殺」事件結構性盲眼。本模組補 10 個 1～5 day 動量／情緒／位階訊號，
與拐點偵測中心互補（慢 vs 快）。

10 燈清單：
  1. vix_level         — VIX 絕對值 ＋ 日變化%
  2. vix_term_struct   — VIX/VIX3M 期限結構（>1 = 後端逆轉 = 急殺前兆）
  3. hy_oas_delta      — HY OAS 1-day bp 變化（信用快裂）
  4. yield_10y_shock   — 10Y Treasury 殖利率 1-day bp 變化
  5. move_level        — MOVE Index 級距（債券恐慌）
  6. spx_trend_break   — SPX vs 50DMA / 200DMA 均線破口
  7. sox_drop          — 半導體龍頭 SOX 1-day 跌幅
  8. sector_rotation   — 防禦 (XLP+XLU+XLV) vs 攻擊 (XLK+XLY+XLF) 30D 動能差
  9. put_call_ratio    — CBOE Put/Call 比率（散戶恐慌）
 10. asia_overnight    — Nikkei + HSI 亞洲夜盤平均跌幅

每燈回傳 dict：
    {
        signal: "🟢 平靜 / 🟡 警戒 / 🔴 警報 / ⬜ 無資料",
        color : "#22c55e / #eab308 / #ef4444 / #888",
        value : float | None,
        prev  : float | None,
        note  : str,           # 觸發解釋（user-facing）
        label : str,           # 資料源說明
        trend : list[float],   # sparkline 用近 6～8 期
    }

防禦：每燈獨立 try/except，單一資料源掛點不拖垮整體（其他 9 燈仍出）。
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from repositories.macro_repository import fetch_fred, fetch_yf_close

GREEN = "#22c55e"
YELLOW = "#eab308"
RED = "#ef4444"
GRAY = "#888888"

_RADAR_KEYS = (
    "vix_level",
    "vix_term_struct",
    "hy_oas_delta",
    "yield_10y_shock",
    "move_level",
    "spx_trend_break",
    "sox_drop",
    "sector_rotation",
    "put_call_ratio",
    "asia_overnight",
)


def _color_from(level: int) -> str:
    return {0: GREEN, 1: YELLOW, 2: RED}.get(level, GRAY)


def _signal_from(level: int) -> str:
    return {0: "🟢 平靜", 1: "🟡 警戒", 2: "🔴 警報"}.get(level, "⬜ 無資料")


def _empty(note: str = "資料來源暫時無法取得", label: str = "—") -> dict:
    return {
        "signal": "⬜ 無資料",
        "color": GRAY,
        "value": None,
        "prev": None,
        "note": note,
        "label": label,
        "trend": [],
    }


def _build(level: int, value, prev, note: str, label: str, trend: list) -> dict:
    return {
        "signal": _signal_from(level),
        "color": _color_from(level),
        "value": value,
        "prev": prev,
        "note": note,
        "label": label,
        "trend": trend,
    }


# ── 1. VIX 絕對值 + 日變化 ─────────────────────────────────────────
def _signal_vix_level() -> dict:
    try:
        s = fetch_yf_close("^VIX", range_="6mo")
        if s.empty or len(s) < 2:
            return _empty("VIX 抓取不足 2 筆", "Yahoo ^VIX 日線")
        cur = float(s.iloc[-1])
        prev = float(s.iloc[-2])
        delta_pct = (cur - prev) / prev * 100 if prev else 0.0
        if cur >= 30 or delta_pct >= 20:
            lvl = 2
        elif cur >= 25 or delta_pct >= 10:
            lvl = 1
        else:
            lvl = 0
        note = f"VIX={cur:.1f}（單日 {delta_pct:+.1f}%）｜>30 或 +20% 為紅燈"
        trend = [round(x, 2) for x in s.tail(8).tolist()]
        return _build(lvl, round(cur, 2), round(prev, 2), note,
                      "Yahoo ^VIX 日線", trend)
    except Exception as e:  # noqa: BLE001
        return _empty(f"VIX 抓取失敗：{str(e)[:60]}", "Yahoo ^VIX 日線")


# ── 多源 fallback helper (v19.30 鏡像 stock v18.181) ─────────────
def _fetch_cboe_csv(short_name: str) -> pd.Series:
    """CBOE 官方每日 CSV → 收盤 Series（key: short_name 如 'VIX3M' / 'CPC' / 'CPCE'）。

    URL pattern: https://cdn.cboe.com/api/global/us_indices/daily_prices/{short}_History.csv
    對 ^VIX3M、^CPC、^CPCE 等 Yahoo 已停供 ticker 的官方替代源。

    失敗回空 Series。
    """
    import io

    from infra.proxy import fetch_url
    try:
        url = ("https://cdn.cboe.com/api/global/us_indices/"
               f"daily_prices/{short_name}_History.csv")
        r = fetch_url(url, timeout=15)
        if r is None or getattr(r, "status_code", 0) != 200:
            print(f"[risk_radar/cboe] {short_name} HTTP {getattr(r, 'status_code', None)}")
            return pd.Series(dtype=float)
        df = pd.read_csv(io.StringIO(r.text))
        date_col = next((c for c in df.columns if "DATE" in c.upper()), None)
        close_col = next((c for c in df.columns if "CLOSE" in c.upper()), None)
        if not date_col or not close_col or df.empty:
            print(f"[risk_radar/cboe] {short_name} 欄位不符: {list(df.columns)}")
            return pd.Series(dtype=float)
        idx = pd.to_datetime(df[date_col], errors="coerce")
        vals = pd.to_numeric(df[close_col], errors="coerce")
        s = pd.Series(vals.values, index=idx).dropna().sort_index()
        return s.tail(180)  # 對齊 6mo
    except Exception as e:  # noqa: BLE001
        print(f"[risk_radar/cboe] {short_name} 失敗: {e}")
        return pd.Series(dtype=float)


def _resolve_vix3m() -> tuple[pd.Series, str]:
    """VIX3M 多源 chain：Yahoo ^VIX3M → Yahoo ^VXV (legacy) → CBOE CSV。"""
    for t in ("^VIX3M", "^VXV"):
        s = fetch_yf_close(t, range_="6mo")
        if not s.empty and len(s) >= 2:
            return s, f"Yahoo {t}"
    s = _fetch_cboe_csv("VIX3M")
    if not s.empty and len(s) >= 2:
        return s, "CBOE VIX3M_History.csv"
    return pd.Series(dtype=float), ""


def _resolve_put_call() -> tuple[pd.Series, str]:
    """CBOE Put/Call 多源 chain：Yahoo ^CPC → ^CPCE → CBOE CSV CPC/CPCE。"""
    for t in ("^CPC", "^CPCE"):
        s = fetch_yf_close(t, range_="6mo")
        if not s.empty and len(s) >= 2:
            return s, f"Yahoo {t}"
    for short in ("CPC", "CPCE"):
        s = _fetch_cboe_csv(short)
        if not s.empty and len(s) >= 2:
            return s, f"CBOE {short}_History.csv"
    return pd.Series(dtype=float), ""


# ── 2. VIX 期限結構 (VIX / VIX3M) ────────────────────────────────
def _signal_vix_term_struct() -> dict:
    try:
        sv = fetch_yf_close("^VIX", range_="6mo")
        s3, src3 = _resolve_vix3m()
        _label = f"Yahoo ^VIX / {src3}" if src3 else "Yahoo ^VIX / VIX3M（全源失敗）"
        if sv.empty or s3.empty:
            return _empty("VIX/VIX3M 抓取失敗（Yahoo + CBOE 全源失敗）", _label)
        df = pd.concat([sv.rename("vix"), s3.rename("v3m")], axis=1).dropna()
        if df.empty or len(df) < 2:
            return _empty("VIX/VIX3M 對齊後不足 2 筆", _label)
        ratio = df["vix"] / df["v3m"]
        cur = float(ratio.iloc[-1])
        prev = float(ratio.iloc[-2])
        if cur >= 1.10:
            lvl = 2
        elif cur >= 1.00:
            lvl = 1
        else:
            lvl = 0
        note = f"VIX/VIX3M={cur:.3f}｜>1 = 後端逆轉（急殺前兆）｜>1.1 = 紅燈"
        trend = [round(x, 3) for x in ratio.tail(8).tolist()]
        return _build(lvl, round(cur, 3), round(prev, 3), note, _label, trend)
    except Exception as e:  # noqa: BLE001
        return _empty(f"VIX 期限結構抓取失敗：{str(e)[:60]}",
                      "Yahoo ^VIX / VIX3M chain")


# ── 3. HY OAS 1-day 變化 ──────────────────────────────────────────
def _signal_hy_oas_delta(fred_api_key: str) -> dict:
    try:
        df = fetch_fred("BAMLH0A0HYM2", fred_api_key, n=120)
        if df.empty or len(df) < 2:
            return _empty("HY OAS 抓取不足 2 筆", "FRED BAMLH0A0HYM2 日線")
        s = df.set_index("date")["value"].sort_index()
        cur = float(s.iloc[-1])
        prev = float(s.iloc[-2])
        delta_bp = (cur - prev) * 100  # % → bp
        if delta_bp >= 30:
            lvl = 2
        elif delta_bp >= 20:
            lvl = 1
        else:
            lvl = 0
        note = f"HY OAS={cur:.2f}%（單日 {delta_bp:+.0f}bp）｜≥+30bp = 紅燈（信用快裂）"
        trend = [round(x, 2) for x in s.tail(8).tolist()]
        return _build(lvl, round(cur, 2), round(prev, 2), note,
                      "FRED BAMLH0A0HYM2 日線", trend)
    except Exception as e:  # noqa: BLE001
        return _empty(f"HY OAS 抓取失敗：{str(e)[:60]}",
                      "FRED BAMLH0A0HYM2 日線")


# ── 4. 10Y Treasury 殖利率衝擊 ────────────────────────────────────
def _signal_yield_10y_shock(fred_api_key: str) -> dict:
    try:
        df = fetch_fred("DGS10", fred_api_key, n=120)
        if df.empty or len(df) < 2:
            return _empty("10Y 殖利率抓取不足 2 筆", "FRED DGS10 日線")
        s = df.set_index("date")["value"].sort_index()
        cur = float(s.iloc[-1])
        prev = float(s.iloc[-2])
        delta_bp = (cur - prev) * 100
        if delta_bp >= 10:
            lvl = 2
        elif delta_bp >= 7:
            lvl = 1
        else:
            lvl = 0
        note = f"10Y={cur:.2f}%（單日 {delta_bp:+.0f}bp）｜≥+10bp = 紅燈（殖利率衝擊）"
        trend = [round(x, 2) for x in s.tail(8).tolist()]
        return _build(lvl, round(cur, 2), round(prev, 2), note,
                      "FRED DGS10 日線", trend)
    except Exception as e:  # noqa: BLE001
        return _empty(f"10Y 殖利率抓取失敗：{str(e)[:60]}",
                      "FRED DGS10 日線")


# ── 5. MOVE Index 級距 ───────────────────────────────────────────
def _signal_move_level() -> dict:
    try:
        s = fetch_yf_close("^MOVE", range_="6mo")
        if s.empty or len(s) < 2:
            return _empty("MOVE 抓取不足 2 筆", "Yahoo ^MOVE 日線")
        cur = float(s.iloc[-1])
        prev = float(s.iloc[-2])
        if cur >= 130:
            lvl = 2
        elif cur >= 110:
            lvl = 1
        else:
            lvl = 0
        note = f"MOVE={cur:.1f}｜>130 = 紅燈（債券恐慌）｜>110 = 黃燈"
        trend = [round(x, 1) for x in s.tail(8).tolist()]
        return _build(lvl, round(cur, 1), round(prev, 1), note,
                      "Yahoo ^MOVE 日線", trend)
    except Exception as e:  # noqa: BLE001
        return _empty(f"MOVE 抓取失敗：{str(e)[:60]}", "Yahoo ^MOVE 日線")


# ── 6. SPX 均線破口（50DMA / 200DMA）─────────────────────────────
def _signal_spx_trend_break() -> dict:
    try:
        s = fetch_yf_close("^GSPC", range_="1y")
        if s.empty or len(s) < 200:
            return _empty("SPX 不足 200 日無法算 200DMA", "Yahoo ^GSPC 日線")
        cur = float(s.iloc[-1])
        sma50 = float(s.tail(50).mean())
        sma200 = float(s.tail(200).mean())
        if cur < sma200:
            lvl = 2
        elif cur < sma50:
            lvl = 1
        else:
            lvl = 0
        note = (f"SPX={cur:.0f}｜50DMA={sma50:.0f}｜200DMA={sma200:.0f}"
                f"｜跌破 200DMA = 紅燈；跌破 50DMA = 黃燈")
        trend = [round(x, 0) for x in s.tail(8).tolist()]
        return _build(lvl, round(cur, 2), round(sma50, 2), note,
                      "Yahoo ^GSPC 日線", trend)
    except Exception as e:  # noqa: BLE001
        return _empty(f"SPX 抓取失敗：{str(e)[:60]}", "Yahoo ^GSPC 日線")


# ── 7. SOX 半導體龍頭單日跌幅 ────────────────────────────────────
def _signal_sox_drop() -> dict:
    try:
        s = fetch_yf_close("^SOX", range_="6mo")
        if s.empty or len(s) < 2:
            return _empty("SOX 抓取不足 2 筆", "Yahoo ^SOX 日線")
        cur = float(s.iloc[-1])
        prev = float(s.iloc[-2])
        delta_pct = (cur - prev) / prev * 100 if prev else 0.0
        if delta_pct <= -3:
            lvl = 2
        elif delta_pct <= -2:
            lvl = 1
        else:
            lvl = 0
        note = f"SOX={cur:.0f}（單日 {delta_pct:+.2f}%）｜≤-3% = 紅燈（半導體龍頭破口）"
        trend = [round(x, 0) for x in s.tail(8).tolist()]
        return _build(lvl, round(cur, 2), round(prev, 2), note,
                      "Yahoo ^SOX 日線", trend)
    except Exception as e:  # noqa: BLE001
        return _empty(f"SOX 抓取失敗：{str(e)[:60]}", "Yahoo ^SOX 日線")


# ── 8. Sector Rotation 防禦 vs 攻擊（30D 動能差）─────────────────
def _signal_sector_rotation() -> dict:
    try:
        defensive = ("XLP", "XLU", "XLV")
        offensive = ("XLK", "XLY", "XLF")

        def _ret_30d(ticker: str) -> Optional[float]:
            sx = fetch_yf_close(ticker, range_="3mo")
            if sx.empty or len(sx) < 22:
                return None
            return (float(sx.iloc[-1]) - float(sx.iloc[-22])) / float(sx.iloc[-22]) * 100

        d_rets = [r for r in (_ret_30d(t) for t in defensive) if r is not None]
        o_rets = [r for r in (_ret_30d(t) for t in offensive) if r is not None]
        if not d_rets or not o_rets:
            return _empty("Sector ETF 抓取不足", "Yahoo XLP/XLU/XLV vs XLK/XLY/XLF")
        d_avg = sum(d_rets) / len(d_rets)
        o_avg = sum(o_rets) / len(o_rets)
        gap = d_avg - o_avg
        if gap >= 4:
            lvl = 2
        elif gap >= 2:
            lvl = 1
        else:
            lvl = 0
        note = (f"30D 防禦 {d_avg:+.1f}% / 攻擊 {o_avg:+.1f}%｜差 {gap:+.1f}pp"
                f"｜≥+4pp = 紅燈（資金撤離成長股）")
        return _build(lvl, round(gap, 2), round(o_avg, 2), note,
                      "Yahoo XLP/XLU/XLV vs XLK/XLY/XLF 30D", [])
    except Exception as e:  # noqa: BLE001
        return _empty(f"Sector rotation 抓取失敗：{str(e)[:60]}",
                      "Yahoo Sector ETF 30D")


# ── 9. CBOE Put/Call Ratio ───────────────────────────────────────
def _signal_put_call_ratio() -> dict:
    try:
        s, src = _resolve_put_call()
        _label = src if src else "CBOE Put/Call chain（全源失敗）"
        if s.empty or len(s) < 2:
            return _empty(
                "Put/Call 抓取失敗（Yahoo ^CPC/^CPCE + CBOE CSV 全源失敗）",
                _label,
            )
        cur = float(s.iloc[-1])
        prev = float(s.iloc[-2])
        if cur >= 1.20:
            lvl = 2
        elif cur >= 1.00:
            lvl = 1
        else:
            lvl = 0
        note = f"Put/Call={cur:.2f}｜>1.2 = 紅燈（散戶恐慌極端）｜>1.0 = 黃燈"
        trend = [round(x, 2) for x in s.tail(8).tolist()]
        return _build(lvl, round(cur, 2), round(prev, 2), note, _label, trend)
    except Exception as e:  # noqa: BLE001
        return _empty(f"Put/Call 抓取失敗：{str(e)[:60]}",
                      "CBOE Put/Call chain")


# ── 10. 亞洲夜盤（Nikkei + HSI 平均單日跌幅）──────────────────────
def _signal_asia_overnight() -> dict:
    try:
        def _last_pct(ticker: str) -> Optional[float]:
            sx = fetch_yf_close(ticker, range_="1mo")
            if sx.empty or len(sx) < 2:
                return None
            return (float(sx.iloc[-1]) - float(sx.iloc[-2])) / float(sx.iloc[-2]) * 100

        n_pct = _last_pct("^N225")
        h_pct = _last_pct("^HSI")
        rets = [r for r in (n_pct, h_pct) if r is not None]
        if not rets:
            return _empty("Nikkei + HSI 都抓取失敗", "Yahoo ^N225 + ^HSI")
        avg = sum(rets) / len(rets)
        if avg <= -2.5:
            lvl = 2
        elif avg <= -1.5:
            lvl = 1
        else:
            lvl = 0
        n_txt = f"Nikkei {n_pct:+.2f}%" if n_pct is not None else "Nikkei N/A"
        h_txt = f"HSI {h_pct:+.2f}%" if h_pct is not None else "HSI N/A"
        note = f"{n_txt}｜{h_txt}｜平均 {avg:+.2f}%（≤-2.5% = 紅燈，台灣盤前領先）"
        return _build(lvl, round(avg, 2), None, note,
                      "Yahoo ^N225 + ^HSI 日線", [])
    except Exception as e:  # noqa: BLE001
        return _empty(f"亞洲夜盤抓取失敗：{str(e)[:60]}",
                      "Yahoo ^N225 + ^HSI")


# ══════════════════════════════════════════════════════════════
# 對外入口
# ══════════════════════════════════════════════════════════════
def detect_risk_radar(fred_api_key: str) -> dict[str, dict]:
    """10-light 短線風險雷達。

    回傳 dict keyed by signal id (10 keys)：
      vix_level / vix_term_struct / hy_oas_delta / yield_10y_shock /
      move_level / spx_trend_break / sox_drop / sector_rotation /
      put_call_ratio / asia_overnight

    每 value 為 dict (signal, color, value, prev, note, label, trend)。
    單一訊號抓取失敗 → 該 key 回傳 _empty() ⬜，其餘 9 燈不受影響。
    """
    return {
        "vix_level":       _signal_vix_level(),
        "vix_term_struct": _signal_vix_term_struct(),
        "hy_oas_delta":    _signal_hy_oas_delta(fred_api_key),
        "yield_10y_shock": _signal_yield_10y_shock(fred_api_key),
        "move_level":      _signal_move_level(),
        "spx_trend_break": _signal_spx_trend_break(),
        "sox_drop":        _signal_sox_drop(),
        "sector_rotation": _signal_sector_rotation(),
        "put_call_ratio":  _signal_put_call_ratio(),
        "asia_overnight":  _signal_asia_overnight(),
    }


def summarize_radar(radar: dict[str, dict]) -> dict:
    """彙總 10 燈狀態 → 摘要 dict。

    Returns
    -------
    {
        red    : int,       # 🔴 數
        yellow : int,       # 🟡 數
        green  : int,       # 🟢 數
        gray   : int,       # ⬜ 數
        level  : str,       # 整體："平靜" / "警戒" / "警報" / "極端警報"
        color  : str,
    }

    閾值規則：
      red ≥ 4               → 極端警報
      red ≥ 2               → 警報
      red + yellow ≥ 4      → 警戒
      其餘                  → 平靜
    """
    counts = {"red": 0, "yellow": 0, "green": 0, "gray": 0}
    for v in radar.values():
        sig = v.get("signal", "") if isinstance(v, dict) else ""
        if "🔴" in sig:
            counts["red"] += 1
        elif "🟡" in sig:
            counts["yellow"] += 1
        elif "🟢" in sig:
            counts["green"] += 1
        else:
            counts["gray"] += 1

    if counts["red"] >= 4:
        level, color = "極端警報", RED
    elif counts["red"] >= 2:
        level, color = "警報", RED
    elif counts["red"] + counts["yellow"] >= 4:
        level, color = "警戒", YELLOW
    else:
        level, color = "平靜", GREEN
    return {**counts, "level": level, "color": color}


def synthesize_dual_verdict(
    slow_level: str,
    slow_score: float,
    slow_color: str,
    slow_icon: str,
    slow_action: str,
    radar_level: str | None,
) -> dict:
    """v19.21 雙速合議 — 將慢總經 verdict 與短線雷達 level 整合為單一行動建議。

    Returns
    -------
    {
        "icon"   : str,    # 🟢🟡🟠🔴 之一
        "level"  : str,    # 合議結論短語
        "color"  : str,    # hex
        "action" : str,    # 行動建議全文（內含分歧/降槓桿等明確指引）
        "mode"   : str,    # "adopt_slow" / "downgrade_1" / "downgrade_2" / "override_defense"
    }

    決策表：
      radar=None/平靜    → adopt_slow（採用慢總經）
      radar=警戒          → downgrade_1（慢樂觀則維持觀察；慢中性/悲觀則降至中性）
      radar=警報          → downgrade_2（慢樂觀→降槓桿；慢中性→偏空；慢悲觀→全面防守）
      radar=極端警報      → override_defense（強制減倉，慢總經暫不採信）
    """
    if radar_level in (None, "平靜"):
        suffix = "（短線雷達平靜確認）" if radar_level == "平靜" else ""
        return {
            "icon": slow_icon,
            "level": f"{slow_level}{suffix}",
            "color": slow_color,
            "action": slow_action,
            "mode": "adopt_slow",
        }

    if radar_level == "極端警報":
        return {
            "icon": "🔴",
            "level": "立即減倉防守",
            "color": "#d32f2f",
            "action": (
                f"短線急殺進行中（雷達 4+ 紅燈）→ 現金 30%+、核心轉投資等級債／防守型；"
                f"慢總經 {slow_level}({slow_score:+.1f}) 暫不採信，待雷達回到警戒以下再恢復攻擊"
            ),
            "mode": "override_defense",
        }

    if radar_level == "警報":
        if slow_score >= 5:
            return {
                "icon": "🟠",
                "level": "雙速分歧：降槓桿",
                "color": "#ef6c00",
                "action": (
                    f"慢總經 {slow_level}({slow_score:+.1f}) 仍多頭，但短線雷達警報 → "
                    f"倉位降至 50-60%、暫緩定額、停利收緊；觀察 24-48h 雷達是否轉警戒"
                ),
                "mode": "downgrade_2",
            }
        if slow_score >= -5:
            return {
                "icon": "🔴",
                "level": "雙線疲弱：偏空操作",
                "color": "#d84315",
                "action": (
                    f"慢總經 {slow_level}({slow_score:+.1f}) 本已疲弱，疊加短線警報 → "
                    f"現金 25-30%、停止加碼、衛星部位獲利了結"
                ),
                "mode": "downgrade_2",
            }
        return {
            "icon": "🔴",
            "level": "全面防守",
            "color": "#b71c1c",
            "action": (
                f"慢總經 {slow_level}({slow_score:+.1f}) 已悲觀，疊加短線警報 → "
                f"現金 35%+、核心轉投資等級債／全球均衡"
            ),
            "mode": "downgrade_2",
        }

    if radar_level == "警戒":
        if slow_score >= 5:
            return {
                "icon": slow_icon,
                "level": f"{slow_level}但警戒觀察",
                "color": "#fbc02d",
                "action": (
                    f"慢總經 {slow_level}({slow_score:+.1f}) 仍主導，但雷達警戒（紅+黃 ≥4 燈）→ "
                    f"維持持倉、暫緩單筆加碼，留意雷達是否升級至警報"
                ),
                "mode": "downgrade_1",
            }
        return {
            "icon": "🟡",
            "level": "中性觀察",
            "color": "#f9a825",
            "action": (
                f"慢總經 {slow_level}({slow_score:+.1f}) 疊加雷達警戒 → "
                f"分批進場、倉位 60-70%、定期定額減半"
            ),
            "mode": "downgrade_1",
        }

    # 未知雷達狀態 fallback
    return {
        "icon": slow_icon,
        "level": slow_level,
        "color": slow_color,
        "action": slow_action,
        "mode": "adopt_slow",
    }
