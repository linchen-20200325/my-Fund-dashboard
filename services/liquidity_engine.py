"""services/liquidity_engine.py — Global Macro Liquidity Warning Engine（數據獲取層 v1）

四個「深水區」流動性因子的原始抓取 + 滾動 252 日 Z-Score，產出與
macro_service 一致的 indicator dict（name/value/prev/unit/type/date/desc/
signal/color/score/weight/series），可直接流進既有 UI / 研判層。

因子（對應四大維度）
  XCCY_PROXY  離岸美元荒（代理：FRED 廣義美元指數 DTWEXBGS 20D 動能）
  CARRY_UNWIND  套利平倉（JPY/CHF 對美元短線升值幅度，急升=避險去槓桿）
  SSR  影子/數位流動性（DefiLlama 穩定幣總市值 → BTC 市值 / 穩定幣市值）
  MOVE_VIX  跨資產波動率背離（^MOVE / ^VIX 比值，債市劇震 vs 股市樂觀）

工程規範（CLAUDE.md §1）：
- 滾動視窗 252 交易日 Z-Score（去歷史絕對值極值干擾）
- 邊界防禦：樣本不足 / 分母為零（平線）/ inf → 回 None，不崩潰
- 因子融合（合成風險分數 + .clip(-3,3)）為下一階段，本檔只負責「取數 + 標準化」

注意：本檔屬 Service Layer，HTTP 抓取一律委派 repositories.macro_repository
（走 NAS proxy + TTL 快取），不自行直連。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from infra.cache import _ttl_cache, register_cache
from shared.ttls import TTL_30MIN
from shared.fred_series import FRED_CHF_USD, FRED_DXY, FRED_JPY_USD
from repositories.macro_repository import (
    fetch_defillama_stablecoin_mcap,
    fetch_fred,
    fetch_yf_close,
)

WINDOW = 252                     # 滾動標準化視窗（交易日）
_MIN_SAMPLES = 60                # 樣本少於此不計算 Z-Score（邊界防禦）
_BTC_SUPPLY_APPROX = 19_800_000  # BTC 流通量近似（~固定）→ 市值 ≈ 價格 × 供給

# 流動性「壓力分數」只由三個 risk-off 因子組成（同向：Z 越高=壓力越大）。
# SSR 依設計為獨立「鏈上子彈水位」對沖指標，不計入壓力分數（見 compute_liquidity_score）。
STRESS_FACTORS: tuple = ("XCCY_PROXY", "CARRY_UNWIND", "MOVE_VIX")
DEFAULT_WEIGHTS: dict = {"XCCY_PROXY": 0.4, "CARRY_UNWIND": 0.3, "MOVE_VIX": 0.3}
_CLIP = 3.0                       # 單因子 Z 截斷區間 ±3（去極端值干擾）


def rolling_zscore(series: pd.Series, window: int = WINDOW) -> "float | None":
    """最後一點相對滾動視窗的 Z-Score；樣本不足 / 標準差為零 → None。"""
    if series is None:
        return None
    s = series.replace([np.inf, -np.inf], np.nan).dropna()
    if len(s) < _MIN_SAMPLES:
        return None                      # 邊界：歷史不足滾動視窗
    w = s.tail(window)
    sd = float(w.std())
    if sd == 0 or np.isnan(sd):
        return None                      # 邊界：分母為零（價格平線）
    return float((float(w.iloc[-1]) - float(w.mean())) / sd)


def rolling_zscore_series(series: pd.Series, window: int = WINDOW) -> pd.Series:
    """整條滾動 Z-Score 序列（每點對其前 window 視窗標準化），供合成歷史趨勢。

    最後一點與 rolling_zscore() 一致（同樣 window 視窗）。樣本不足 / 全平 → 空 Series。
    """
    if series is None:
        return pd.Series(dtype=float)
    s = series.replace([np.inf, -np.inf], np.nan).dropna()
    if len(s) < _MIN_SAMPLES:
        return pd.Series(dtype=float)
    mu = s.rolling(window, min_periods=_MIN_SAMPLES).mean()
    sd = s.rolling(window, min_periods=_MIN_SAMPLES).std()
    z = (s - mu) / sd.replace(0.0, np.nan)
    return z.replace([np.inf, -np.inf], np.nan).dropna()


def _sig_color_score(z: "float | None", *, hi: float = 2.0, mid: float = 1.0,
                     invert: bool = False) -> tuple:
    """由 Z-Score 給 (signal, color, score)。

    invert=False：z 越高越危險（🔴）。invert=True：z 越低越危險。
    score：+1 健康 / 0 中性 / -1 警示，供研判層加權。
    """
    if z is None:
        return "⬜", "#666", 0            # 無資料 → 不評
    zz = -z if invert else z
    if zz >= hi:
        return "🔴", "#f44336", -1
    if zz >= mid:
        return "🟡", "#ff9800", 0
    return "🟢", "#00c853", 1


def _weekly_tail(series: pd.Series, n: int = 260) -> pd.Series:
    """週頻重採樣 + 取尾，與 macro_service 既有 series 欄一致（供趨勢圖）。"""
    s = series.replace([np.inf, -np.inf], np.nan).dropna()
    if s.empty:
        return s
    try:
        return s.resample("W").last().dropna().tail(n)
    except (TypeError, ValueError):
        return s.tail(n)


# ──────────────────────────────────────────────────────────────
# 因子 1：離岸美元荒（代理：廣義美元指數動能）
# ──────────────────────────────────────────────────────────────
def build_xccy_proxy(fred_api_key: str) -> "dict | None":
    """FRED 廣義美元指數 DTWEXBGS 的 20 日動能 → Z-Score。

    代理邏輯：真 3M XCCY basis 無免費源；以「美元急速走強」近似離岸美元荒
    （非美機構搶美元 → 美元指數噴升）。⚠️ 非真實 basis，UI 須標註代理。
    """
    df = fetch_fred(FRED_DXY, fred_api_key, 800)
    if df.empty or len(df) < _MIN_SAMPLES:
        return None
    s = df.set_index("date")["value"].astype(float)
    mom = (s / s.shift(20) - 1.0) * 100.0          # 20 交易日動能（%）
    mom = mom.dropna()
    if mom.empty:
        return None
    z = rolling_zscore(mom)
    sig, color, score = _sig_color_score(z, invert=False)   # 動能越高=越荒
    v = round(float(mom.iloc[-1]), 2)
    p = round(float(mom.iloc[-6]), 2) if len(mom) >= 6 else v
    return dict(
        name="離岸美元荒（代理：廣義美元指數動能）",
        value=v, prev=p, unit="%(20D)", type="領先",
        date=str(s.index[-1])[:10],
        desc="⚠️代理指標（非真 XCCY basis）｜美元急升=非美機構搶美元=系統性美元荒前瞻",
        zscore=None if z is None else round(z, 2),
        signal=sig, color=color, score=score, weight=1,
        series=_weekly_tail(mom),
        z_series=_weekly_tail(rolling_zscore_series(mom)),
    )


# ──────────────────────────────────────────────────────────────
# 因子 2：套利平倉（JPY / CHF 短線升值幅度）
# ──────────────────────────────────────────────────────────────
def build_carry_unwind(fred_api_key: str) -> "dict | None":
    """JPY/CHF 對美元 5 日升值幅度（取較極端者）→ Z-Score。

    carry unwind 邏輯：避險貨幣（日圓/瑞郎）無預警急升 = 對沖基金被迫平倉
    償還低息借貸 → 拋售風險資產。FRED DEXJPUS/DEXSZUS 為「每 1 美元兌多少
    日圓/瑞郎」，**下跌 = 該貨幣升值**，故升值幅度 = -ROC。
    """
    appr_series = []     # 各貨幣「升值%」序列（正=升值）
    latest = {}
    for sid, label in ((FRED_JPY_USD, "JPY"), (FRED_CHF_USD, "CHF")):
        df = fetch_fred(sid, fred_api_key, 400)
        if df.empty or len(df) < _MIN_SAMPLES:
            continue
        s = df.set_index("date")["value"].astype(float)
        appr = -((s / s.shift(5) - 1.0) * 100.0)    # 5 日升值%（正=避險貨幣走強）
        appr = appr.dropna()
        if not appr.empty:
            appr_series.append(appr.rename(label))
            latest[label] = round(float(appr.iloc[-1]), 2)
    if not appr_series:
        return None
    # 對齊後逐日取「較極端的升值」（避險壓力以最強的一方為準）
    combined = pd.concat(appr_series, axis=1).max(axis=1).dropna()
    if combined.empty:
        return None
    z = rolling_zscore(combined)
    sig, color, score = _sig_color_score(z, invert=False)   # 升值越急=越警示
    v = round(float(combined.iloc[-1]), 2)
    p = round(float(combined.iloc[-6]), 2) if len(combined) >= 6 else v
    _detail = "｜".join(f"{k}+{v_:.1f}%" if v_ >= 0 else f"{k}{v_:.1f}%"
                        for k, v_ in latest.items())
    return dict(
        name="套利平倉壓力（JPY/CHF 急升）",
        value=v, prev=p, unit="%(5D)", type="領先",
        date=None, detail=_detail,
        desc=f"避險貨幣急升=carry unwind 去槓桿（{_detail}）",
        zscore=None if z is None else round(z, 2),
        signal=sig, color=color, score=score, weight=1,
        series=_weekly_tail(combined),
        z_series=_weekly_tail(rolling_zscore_series(combined)),
    )


# ──────────────────────────────────────────────────────────────
# 因子 3：影子/數位流動性（SSR = BTC 市值 / 穩定幣市值）
# ──────────────────────────────────────────────────────────────
def build_ssr() -> "dict | None":
    """SSR (Stablecoin Supply Ratio) = BTC 市值 / 穩定幣總市值。

    BTC 市值 ≈ BTC 價格 × 近似流通量；穩定幣市值取自 DefiLlama。
    SSR 高（Z > 0）= BTC 市值 >> 穩定幣市值 = 鏈上子彈耗盡 = 危險（高 z = 🔴），
    與其他三個 risk-off 因子同向 → invert=False。
    SSR 低（Z < 0）= 鏈上法幣子彈多 = 潛在買盤強（偏多訊號），附掛為獨立對沖參考。
    """
    stable = fetch_defillama_stablecoin_mcap()
    btc = fetch_yf_close("BTC-USD", "5y")
    if stable.empty or btc.empty:
        return None
    btc_mcap = (btc * _BTC_SUPPLY_APPROX)
    # 日對齊（兩者皆日頻；normalize 去時分秒）
    df = pd.concat(
        [btc_mcap.rename("btc"), stable.rename("stable")], axis=1
    )
    df.index = pd.to_datetime(df.index).normalize()
    df = df[~df.index.duplicated(keep="last")].sort_index().ffill().dropna()
    if len(df) < _MIN_SAMPLES:
        return None
    ssr = (df["btc"] / df["stable"]).replace([np.inf, -np.inf], np.nan).dropna()
    if ssr.empty:
        return None
    z = rolling_zscore(ssr)
    # SSR 高（Z > 0）= BTC 市值 >> 穩定幣市值 = 子彈耗盡 = 危險 → invert=False（高 z = 🔴）
    sig, color, score = _sig_color_score(z, invert=False)
    v = round(float(ssr.iloc[-1]), 2)
    p = round(float(ssr.iloc[-6]), 2) if len(ssr) >= 6 else v
    _stable_b = float(df["stable"].iloc[-1]) / 1e9
    return dict(
        name="SSR 穩定幣購買力（BTC市值/穩定幣市值）",
        value=v, prev=p, unit="", type="領先",
        date=str(df.index[-1])[:10],
        detail=f"穩定幣總市值≈${_stable_b:,.0f}B",
        desc="SSR 低(Z<0)=鏈上法幣子彈多=潛在買盤強；SSR 高=子彈耗盡",
        zscore=None if z is None else round(z, 2),
        signal=sig, color=color, score=score, weight=1,
        series=_weekly_tail(ssr),
        z_series=_weekly_tail(rolling_zscore_series(ssr)),
    )


# ──────────────────────────────────────────────────────────────
# 因子 4：跨資產波動率背離（MOVE / VIX）
# ──────────────────────────────────────────────────────────────
def build_move_vix() -> "dict | None":
    """MOVE（美債波動率）/ VIX（美股波動率）比值 → Z-Score。

    比值異常飆高（Z>2）= 資金源頭（債市）已劇震、股市盲目樂觀，
    預示股市隨後資金踩踏補跌。
    """
    s_move = fetch_yf_close("^MOVE", "5y")
    s_vix = fetch_yf_close("^VIX", "5y")
    if s_move.empty or s_vix.empty:
        return None
    df = pd.concat([s_move.rename("move"), s_vix.rename("vix")], axis=1)
    df.index = pd.to_datetime(df.index).normalize()
    df = df[~df.index.duplicated(keep="last")].sort_index().dropna()
    if len(df) < _MIN_SAMPLES:
        return None
    ratio = (df["move"] / df["vix"]).replace([np.inf, -np.inf], np.nan).dropna()
    if ratio.empty:
        return None
    z = rolling_zscore(ratio)
    sig, color, score = _sig_color_score(z, invert=False)   # 比值越高=越危險
    v = round(float(ratio.iloc[-1]), 2)
    p = round(float(ratio.iloc[-6]), 2) if len(ratio) >= 6 else v
    return dict(
        name="MOVE/VIX 波動率背離",
        value=v, prev=p, unit="", type="領先",
        date=str(df.index[-1])[:10],
        detail=f"MOVE={df['move'].iloc[-1]:.1f}｜VIX={df['vix'].iloc[-1]:.1f}",
        desc="比值飆高(Z>2)=債市劇震+股市樂觀→股市補跌風險",
        zscore=None if z is None else round(z, 2),
        signal=sig, color=color, score=score, weight=1,
        series=_weekly_tail(ratio),
        z_series=_weekly_tail(rolling_zscore_series(ratio)),
    )


# ──────────────────────────────────────────────────────────────
# 對外入口：一次取齊四因子（個別失敗不影響其他）
# ──────────────────────────────────────────────────────────────
@register_cache
@_ttl_cache(ttl_sec=TTL_30MIN, maxsize=2)   # P1：深水區流動性 4 因子，rerun 免重打 FRED
def fetch_liquidity_factors(fred_api_key: str = "") -> dict:
    """取齊四個深水區流動性因子，回傳 {KEY: indicator_dict}（抓不到的略過）。

    KEY: XCCY_PROXY / CARRY_UNWIND / SSR / MOVE_VIX
    個別因子以 try/except 隔離 — 單一來源失敗不拖垮整體（邊界防禦）。
    """
    out: dict = {}
    _builders = {
        "XCCY_PROXY":   lambda: build_xccy_proxy(fred_api_key),
        "CARRY_UNWIND": lambda: build_carry_unwind(fred_api_key),
        "SSR":          build_ssr,
        "MOVE_VIX":     build_move_vix,
    }
    for key, fn in _builders.items():
        try:
            entry = fn()
            if entry:
                out[key] = entry
        except Exception as e:
            print(f"[liquidity_engine] {key} 建構失敗: {e}")
    return out


# ──────────────────────────────────────────────────────────────
# 因子融合：流動性壓力綜合分數（SSR 為獨立子彈水位，不計入）
# ──────────────────────────────────────────────────────────────
def _tier(score: float) -> tuple:
    """壓力分數 → (分級, signal, color, 研判文字)。"""
    if score >= 2.0:
        return "流動性危機", "🔴", "#f44336", "美元荒/避險平倉/波動率背離同時引爆，risk-off 去槓桿"
    if score >= 1.0:
        return "警戒", "🟠", "#ff6d00", "壓力升溫，留意資金面轉向與槓桿回收"
    if score >= 0.5:
        return "正常偏緊", "🟡", "#ffc107", "壓力溫和，中性偏謹慎"
    return "寬鬆充裕", "🟢", "#00c853", "流動性壓力低，risk-on 友善"


def compute_liquidity_score(factors: dict, weights: "dict | None" = None) -> "dict | None":
    """三個 risk-off 壓力因子加權合成「流動性壓力分數」。

    設計（user 拍板 B 案）：SSR **不計入**壓力分數，改作獨立「鏈上子彈水位」
    對沖指標附掛於輸出，供研判層對照（SSR 低=子彈多=偏多，方向與壓力相反）。

    流程：各因子 Z 先 `clip(±3)` → 依權重加權平均（缺因子自動重正規化權重，
    邊界防禦）→ 切四檔分級。三因子全缺 → None。

    Parameters
    ----------
    factors : dict   fetch_liquidity_factors 的輸出 {KEY: indicator_dict}
    weights : dict   可調權重（預設 DEFAULT_WEIGHTS）；只對在線因子正規化

    Returns
    -------
    dict  含 value(總分)/tier/signal/color/desc/breakdown(逐因子貢獻)/
          weights(正規化後)/ssr(獨立對照)；無壓力因子在線 → None。
    """
    w = dict(weights or DEFAULT_WEIGHTS)
    present = {k: factors[k] for k in STRESS_FACTORS
               if factors.get(k) and factors[k].get("zscore") is not None}
    if not present:
        return None
    wsum = sum(w.get(k, 0.0) for k in present) or 1.0   # 邊界：缺因子重正規化
    score = 0.0
    breakdown = []
    norm_w = {}
    for k, e in present.items():
        z = max(-_CLIP, min(_CLIP, float(e["zscore"])))   # clip(±3)
        wn = w.get(k, 0.0) / wsum
        contrib = z * wn
        score += contrib
        norm_w[k] = round(wn, 3)
        breakdown.append(dict(key=k, name=e.get("name", k), z=round(z, 2),
                              weight=round(wn, 3), contrib=round(contrib, 3)))
    score = round(score, 3)
    tier, sig, color, note = _tier(score)

    # 合成分數「歷史序列」：對齊各因子 z_series → clip → 同權重加權加總
    # （只取所有在線因子皆有值的日期，末點與上方純量 score 一致）
    score_series = pd.Series(dtype=float)
    _zs_cols = []
    for k in present:
        zs = present[k].get("z_series")
        if zs is not None and len(zs):
            _zs_cols.append((zs.clip(-_CLIP, _CLIP) * norm_w[k]).rename(k))
    if _zs_cols:
        sdf = pd.concat(_zs_cols, axis=1).sort_index().dropna()
        if not sdf.empty:
            score_series = sdf.sum(axis=1)

    ssr_e = factors.get("SSR")
    ssr_info = None
    if ssr_e:
        ssr_info = dict(name=ssr_e.get("name"), value=ssr_e.get("value"),
                        zscore=ssr_e.get("zscore"), signal=ssr_e.get("signal"))

    return dict(
        name="流動性壓力綜合分數",
        value=score, unit="加權Z", type="綜合",
        tier=tier, signal=sig, color=color,
        desc=f"{tier}：{note}（{len(present)}/{len(STRESS_FACTORS)} 壓力因子在線）",
        breakdown=breakdown, weights=norm_w, ssr=ssr_info,
        score_series=score_series,
    )


def liquidity_verdict(score_entry: "dict | None", factors: "dict | None" = None) -> str:
    """由壓力分數 + 因子拆解產生一段白話研判（純函式，供 UI 直接顯示）。

    內容：分級總評 → 主導因子（breakdown 最大絕對貢獻）→ SSR 子彈水位 →
    A→B 傳導/操作註記。資料不足回提示字串。
    """
    if not score_entry:
        return "（流動性因子資料不足，暫無法研判。）"
    val = score_entry.get("value", 0.0)
    parts = [f"目前流動性壓力分數 **{val:+.2f}**，分級「**{score_entry.get('tier', '—')}**」"
             f"{score_entry.get('signal', '')}。"]

    bd = score_entry.get("breakdown") or []
    if bd:
        top = max(bd, key=lambda b: abs(b.get("contrib", 0.0)))
        direction = "推升壓力" if top.get("contrib", 0.0) > 0 else "壓低壓力"
        parts.append(f"主導因子為「{top.get('name', '')}」"
                     f"（{direction}，貢獻 {top.get('contrib', 0.0):+.2f}）。")

    ssr = score_entry.get("ssr") or {}
    sz = ssr.get("zscore")
    if sz is not None:
        if sz < -1:
            parts.append(f"鏈上子彈水位充裕（SSR Z {sz:+.2f}，穩定幣相對 BTC 偏多），潛在買盤可期。")
        elif sz > 1:
            parts.append(f"鏈上子彈接近耗盡（SSR Z {sz:+.2f}），追價力道受限。")
        else:
            parts.append(f"鏈上子彈水位中性（SSR Z {sz:+.2f}）。")

    if val >= 2.0:
        parts.append("⚠️ 美元/避險/波動率多軌同時緊繃，留意 risk-off 去槓桿向風險資產傳導"
                     "（時滯約數日至數週），宜降槓桿、備現金。")
    elif val >= 1.0:
        parts.append("壓力升溫但未失控，建議降低槓桿、提高現金緩衝並緊盯主導因子。")
    else:
        parts.append("流動性環境相對寬鬆，對風險資產偏友善；仍留意單一因子突發跳升。")
    return " ".join(parts)
