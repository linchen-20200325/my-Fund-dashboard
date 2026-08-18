"""services/ladder235.py — L2 深度強化:235 精準加碼引擎(基金版,v19.465)。

補「老師 235 精準加碼」那一格(user 2026-08-18 核准數學規格)。用**週 NAV**(週五定案)算
20 週布林 + 4/13/52 週均線,配 VIX,依「三取一 Max(最嚴重燈優先)」判定加碼水位燈:

  ⚪ 巡航(定期定額) / 🟢 燈一(小跌 20%) / 🟡 燈二(急跌 30%) / 🔴 燈三(深水 50%)
  💰 停利(布林上軌 +2σ 分批 / +3σ 強制)—— 獨立於四燈,且優先(超漲不加碼)。

純函式・零 IO(NAV 序列 + VIX + 選填加碼金由呼叫端傳入)。常數走 `shared.signal_thresholds`(§3.3)。
§1 Fail-Loud:週資料 < 20 週 / σ=0 → 燈=None「資料不足」(不硬給);VIX=None → 只用均線+布林
兩維判燈並標「(無 VIX)」;NAV 週末缺值正常 → resample 取最後營業日,**不 ffill 偽造**。
§3.2 sign:z_bb 負=下檔、正=上檔。§4.1:週交易週對齊;VIX 為指數點、reserve 為 TWD。

加碼金(選填)：當前燈 → 建議動用閒置加碼金 % = LADDER235_DEPLOY_PCT[燈]。**不追蹤累計耗盡**
(真要精算「用掉前面剩 50%」需交易記錄狀態,§1 不假造帳本 → user 核准簡化版)。
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from shared.colors import (
    MATERIAL_ORANGE,
    TRAFFIC_GREEN,
    TRAFFIC_NEUTRAL,
    TRAFFIC_RED,
    TRAFFIC_YELLOW,
)
from shared.signal_thresholds import (
    LADDER235_BB_WINDOW_W,
    LADDER235_DEPLOY_PCT,
    LADDER235_MA_MONTH_W,
    LADDER235_MA_QUARTER_W,
    LADDER235_MA_YEAR_W,
    LADDER235_MIN_CV,
    LADDER235_MIN_WEEKS,
    LADDER235_VIX_L1,
    LADDER235_VIX_L2,
    LADDER235_VIX_L3,
)

_LAMP_META = {
    "巡航": ("⚪", TRAFFIC_NEUTRAL),
    "燈一": ("🟢", TRAFFIC_GREEN),
    "燈二": ("🟡", TRAFFIC_YELLOW),
    "燈三": ("🔴", TRAFFIC_RED),
    "分批停利": ("💰", MATERIAL_ORANGE),
    "強制停利": ("🔴", TRAFFIC_RED),
}


def _weekly_close(nav) -> "pd.Series | None":
    """日 NAV → 週五定案週收盤(當週最後營業日 NAV)。dropna、>0、升冪;無法轉日期 → None。"""
    if nav is None:
        return None
    s = pd.Series(nav).dropna()
    if len(s) < 2:
        return None
    idx = pd.to_datetime(s.index, errors="coerce")
    s = s[idx.notna()]
    s.index = idx[idx.notna()]
    if getattr(s.index, "tz", None) is not None:
        s.index = s.index.tz_localize(None)
    s = s.sort_index()
    s = s[~s.index.duplicated(keep="last")]
    wk = s.resample("W-FRI").last().dropna()   # 週末缺值不 ffill,取當週最後有值營業日
    wk = wk[wk > 0]
    return wk if len(wk) >= 2 else None


def _ma(wk: pd.Series, weeks: int) -> Optional[float]:
    """last `weeks` 週均線;不足 weeks 週 → None(不從不足資料偽造年線,§1)。"""
    return float(wk.iloc[-weeks:].mean()) if len(wk) >= weeks else None


def _blank(status: str, wk_n: int, vix) -> dict:
    return {"lamp": None, "emoji": "⬜", "color": TRAFFIC_NEUTRAL, "status": status,
            "z_bb": None, "c": None, "ma4": None, "ma13": None, "ma52": None,
            "mu": None, "sigma": None, "vix": vix, "weeks": wk_n,
            "deploy_pct": 0.0, "deploy_twd": None, "reasons": [], "note": ""}


def _classify(c, ma4, ma13, ma52, z_bb, vix) -> tuple:
    """三取一 Max:回 (lamp, reasons)。停利優先(超漲不加碼),再由最嚴重加碼燈往下檢查。"""
    # 停利(布林上軌;獨立且優先)
    if z_bb > 3:
        return "強制停利", [f"布林 z={z_bb:+.2f} > +3σ(超漲,獲利轉回核心)"]
    if z_bb > 2:
        return "分批停利", [f"布林 z={z_bb:+.2f} > +2σ(超漲,分批停利)"]

    _has_vix = isinstance(vix, (int, float))
    # 燈三 深水
    r3 = []
    if _has_vix and vix >= LADDER235_VIX_L3:
        r3.append(f"VIX {vix:.1f} ≥ {LADDER235_VIX_L3:.0f}")
    if ma52 is not None and c < ma52 and z_bb < -2:
        r3.append(f"週收<52週年線 且 布林 z={z_bb:+.2f}<-2σ")
    if z_bb < -3:
        r3.append(f"布林 z={z_bb:+.2f} < -3σ")
    if r3:
        return "燈三", r3
    # 燈二 急跌
    r2 = []
    if _has_vix and LADDER235_VIX_L2 <= vix < LADDER235_VIX_L3:
        r2.append(f"VIX {vix:.1f} ∈ [{LADDER235_VIX_L2:.0f},{LADDER235_VIX_L3:.0f})")
    if ma13 is not None and c < ma13:
        r2.append("週收 < 13週季線")
    if z_bb < -2:
        r2.append(f"布林 z={z_bb:+.2f} < -2σ")
    if r2:
        return "燈二", r2
    # 燈一 小跌
    r1 = []
    if _has_vix and LADDER235_VIX_L1 <= vix < LADDER235_VIX_L2:
        r1.append(f"VIX {vix:.1f} ∈ [{LADDER235_VIX_L1:.0f},{LADDER235_VIX_L2:.0f})")
    if ma4 is not None and c < ma4:
        r1.append("週收 < 4週月線")
    if z_bb < -1:
        r1.append(f"布林 z={z_bb:+.2f} < -1σ")
    if r1:
        return "燈一", r1
    # 巡航
    _vixtxt = "VIX<20、" if _has_vix else ""   # VIX=None 時不寫死「VIX<20」(稽核 #3)
    return "巡航", [f"{_vixtxt}週收≥4週月線、布林 z≥-1σ(維持定期定額)"]


def _defense_note(wk: pd.Series, c, ma13, ma52, z_bb) -> str:
    """深水區防守註記(不改燈):等待共伴確認 / 落底回升信號。"""
    if ma52 is not None and c < ma52 and z_bb >= -2:
        return "⏳ 僅跌破年線、布林未達 -2σ → 等待共伴確認(不逕觸發深水)"
    # 落底回升:近 8 週曾探到年線之下、現又站回季線
    if ma52 is not None and ma13 is not None and c >= ma13:
        if float(wk.iloc[-8:].min()) < ma52:
            return "🔄 跌破年線後站回 13週季線 → 落底回升信號"
    return ""


def ladder_signal(nav, vix: Optional[float] = None,
                  reserve_twd: Optional[float] = None,
                  category=None) -> dict:
    """235 加碼水位燈。純函式,離線可驗。

    Args:
        nav: 單檔基金**日 NAV 原幣**序列(pandas Series/dict,日期索引)。
        vix: VIX 最新值(整組共用);None → 只用均線+布林兩維判燈。
        reserve_twd: 閒置加碼金 TWD(選填);有值 → 附建議本次投入 = reserve × 燈比例。
        category: 基金類別(選填);Core 桶(平衡多重/貨幣市場)→ 不做加碼擇時(比照 Z-Score,
            §1 避免低波近平盤標的被布林雜訊誤報極端燈;稽核 #8)。

    Returns: dict(lamp/emoji/color/z_bb/c/ma4/ma13/ma52/mu/sigma/vix/weeks/
             deploy_pct/deploy_twd/reasons/note/status)。
    """
    _vix = float(vix) if isinstance(vix, (int, float)) else None
    # Core(平衡/貨幣)→ 不適用加碼擇時(內建配置;同 zscore_engine.is_core_bucket)
    if category is not None:
        try:
            from services.zscore_engine import is_core_bucket  # noqa: PLC0415 — L2 同層
            if is_core_bucket(category):
                _b = _blank("core", 0, _vix)
                _b["note"] = "Core(平衡多重/貨幣市場)內建股債配置,不做加碼水位擇時"
                return _b
        except Exception:  # noqa: BLE001 — 分類失敗 → 當非 Core 續判(較保守不漏)
            pass

    wk = _weekly_close(nav)
    if wk is None or len(wk) < LADDER235_MIN_WEEKS:
        return _blank("insufficient", (0 if wk is None else len(wk)), _vix)

    c = float(wk.iloc[-1])
    mu = float(wk.iloc[-LADDER235_BB_WINDOW_W:].mean())
    sigma = float(wk.iloc[-LADDER235_BB_WINDOW_W:].std(ddof=1))
    if not (sigma > 0):                       # σ=0(20 週全同值)→ 布林無意義(§1)
        return _blank("degenerate", len(wk), _vix)
    if mu > 0 and (sigma / mu) < LADDER235_MIN_CV:   # 低波近平盤 → 布林位階雜訊大(稽核 #8)
        _b = _blank("lowvol", len(wk), _vix)
        _b["note"] = f"低波標的(週 σ/均值 {sigma / mu:.4f} < {LADDER235_MIN_CV})→ 布林位階雜訊大,不判加碼燈"
        return _b

    z_bb = (c - mu) / sigma
    ma4 = _ma(wk, LADDER235_MA_MONTH_W)
    ma13 = _ma(wk, LADDER235_MA_QUARTER_W)
    ma52 = _ma(wk, LADDER235_MA_YEAR_W)

    lamp, reasons = _classify(c, ma4, ma13, ma52, z_bb, _vix)
    if _vix is None:
        reasons.append("(無 VIX,僅均線+布林判定)")
    note = _defense_note(wk, c, ma13, ma52, z_bb)
    if ma52 is None:
        note = (note + " ｜ " if note else "") + "⬜ 週資料 <52 週,年線條件暫略"

    deploy_pct = float(LADDER235_DEPLOY_PCT.get(lamp, 0.0))
    deploy_twd = (round(reserve_twd * deploy_pct)
                  if isinstance(reserve_twd, (int, float)) and reserve_twd > 0 else None)
    emoji, color = _LAMP_META.get(lamp, ("⬜", TRAFFIC_NEUTRAL))
    return {
        "lamp": lamp, "emoji": emoji, "color": color, "status": "ok",
        "z_bb": round(z_bb, 3), "c": round(c, 4),
        "ma4": (round(ma4, 4) if ma4 is not None else None),
        "ma13": (round(ma13, 4) if ma13 is not None else None),
        "ma52": (round(ma52, 4) if ma52 is not None else None),
        "mu": round(mu, 4), "sigma": round(sigma, 4), "vix": _vix, "weeks": len(wk),
        "deploy_pct": deploy_pct, "deploy_twd": deploy_twd,
        "reasons": reasons, "note": note,
    }


__all__ = ["ladder_signal"]
