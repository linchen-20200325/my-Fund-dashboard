"""services/macro/causal_sankey.py — v19.199 P1-7 Sub-cycle + Sankey + Drivers + Cluster signals。

從 macro_service 主檔抽出(原 line 2262-2939)。
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from shared.colors import MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED

from services.macro._helpers import (  # noqa: F401
    _trend, _safe_last, recession_probability,
    _PMI_INFL_EXPANSION, _HY_YELLOW,
)
# v19.199 P1-7:_SUB_CYCLE_SPEC 在 turning_points.py 內(原檔 line 2243,落 turning_points
# range 1759-2261),但 calc_sub_cycle_lights 在本檔用 → 跨子模組 import(無循環)
from services.macro.turning_points import _SUB_CYCLE_SPEC  # noqa: F401


def _calc_zscore_safe(series, current_value=None):
    """Z-Score 容錯計算（複製自 shared.macro_card.calc_z_score，避開循環 import）。"""
    if series is None:
        return None
    try:
        import pandas as pd
        s = series if isinstance(series, pd.Series) else pd.Series(series)
        s = s.dropna()
        if len(s) < 10:
            return None
        mu, sigma = float(s.mean()), float(s.std())
        if sigma == 0:
            return None
        v = float(current_value) if current_value is not None else float(s.iloc[-1])
        return (v - mu) / sigma
    except Exception:
        return None


def calc_sub_cycle_lights(indicators: dict) -> list[dict]:
    """景氣循環細項燈號 — 7 個子領域燈號（Phase 2 v18.100）。

    Args:
        indicators: macro_engine 載入後的 dict，每 key 對應 {"value", "series", ...}

    Returns:
        list of {"name", "icon", "color", "signal", "z_avg", "verdict",
                 "indicators": [{"key", "z", "high_is_bad"}, ...],
                 "description"}

    判斷規則（依 high_is_bad 翻轉）：
        z_avg < -1.0  → 🟢 健康
        -1.0 ≤ z < 0  → 🟡 中性偏好
        0 ≤ z < 1.0   → 🟠 中性偏弱
        z ≥ 1.0       → 🔴 警示
    （high_is_bad=False 的指標，z 取負後再判斷，使「越高越好」與通膨「越低越好」可對齊。）
    """
    out = []
    for name, icon, ind_list, desc in _SUB_CYCLE_SPEC:
        z_components = []
        for key, high_is_bad in ind_list:
            iv = indicators.get(key) or {}
            series = iv.get("series")
            value = iv.get("value")
            z = _calc_zscore_safe(series, value)
            if z is None:
                continue
            # 統一語意：z_norm > 0 → 不健康；z_norm < 0 → 健康
            z_norm = z if high_is_bad else -z
            z_components.append({"key": key, "z": round(z, 2),
                                 "z_norm": round(z_norm, 2),
                                 "high_is_bad": high_is_bad})

        if not z_components:
            out.append({
                "name": name, "icon": icon, "color": "#666",
                "signal": "⬜", "z_avg": None, "verdict": "資料不足",
                "indicators": [], "description": desc,
            })
            continue

        z_avg = sum(c["z_norm"] for c in z_components) / len(z_components)
        if z_avg < -1.0:
            signal, color, verdict = "🟢", "#4caf50", "健康"
        elif z_avg < 0:
            signal, color, verdict = "🟡", "#ffeb3b", "中性偏好"
        elif z_avg < 1.0:
            signal, color, verdict = "🟠", MATERIAL_ORANGE, "中性偏弱"
        else:
            signal, color, verdict = "🔴", MATERIAL_RED, "警示"

        out.append({
            "name": name, "icon": icon, "color": color,
            "signal": signal, "z_avg": round(z_avg, 2),
            "verdict": verdict, "indicators": z_components,
            "description": desc,
        })
    return out


# ════════════════════════════════════════════════════════════
# v18.101 總經因果鏈 Sankey（Phase 2 — Macro Causal Sankey）
# 視覺化「政策 → 信貸 → 實體經濟 → 市場」三層因果，邊粗細由 z-score 決定
# ════════════════════════════════════════════════════════════
_SANKEY_NODES = [
    # (key, label, layer, high_is_bad)
    ("FED_RATE",        "🏛️ 聯準會利率",    0, True),
    ("SLOOS",           "🏦 銀行放貸意願",    1, True),
    ("HY_SPREAD",       "💳 信用利差",        1, True),
    ("PERMIT_HOUSING",  "🏠 房市建照",        2, False),
    ("JOBLESS",         "💼 失業金",          2, True),
    ("PMI",             "🏭 製造業 PMI",      2, False),
    ("VIX",             "😱 VIX 恐慌",        3, True),
    ("DXY",             "💵 美元指數",        3, True),
]

_SANKEY_LINKS = [
    # (source_key, target_key, edu_note)
    ("FED_RATE",        "SLOOS",          "升息 → 銀行緊縮放貸"),
    ("FED_RATE",        "HY_SPREAD",      "升息 → 信用利差擴大"),
    ("FED_RATE",        "DXY",            "升息 → 美元走強"),
    ("SLOOS",           "PERMIT_HOUSING", "放貸寬鬆 → 建照增加"),
    ("SLOOS",           "JOBLESS",        "放貸緊縮 → 失業上升"),
    ("HY_SPREAD",       "VIX",            "信用利差擴大 → 市場恐慌"),
    ("PERMIT_HOUSING",  "PMI",            "房市熱 → 製造業（建材）回升"),
    ("DXY",             "PMI",            "美元走強 → 出口承壓"),
    ("JOBLESS",         "VIX",            "失業惡化 → 市場避險"),
]


def build_macro_sankey_data(indicators: dict) -> dict:
    """總經因果鏈 Sankey 視覺化資料（Phase 2 v18.101）。

    Args:
        indicators: macro_engine 載入後的 dict

    Returns:
        {
          "labels":    [str, ...],          # 節點標籤（含 z 註記）
          "sources":   [int, ...],          # link 起點 index
          "targets":   [int, ...],          # link 終點 index
          "values":    [float, ...],        # 邊粗細 = 起點 |z| × 1.0（最小 0.3）
          "node_colors": [str, ...],        # 節點顏色（依 z_norm 健康度）
          "link_colors": [str, ...],        # 邊顏色（rgba 半透明）
          "link_labels": [str, ...],        # hover 教學文字
          "ok":        bool,                # 至少 50% 節點有 z 才算 ok
          "note":      str,
        }

    視覺解讀：
      - 節點顏色：🟢 健康 / 🟡 中性 / 🔴 警示（依 z_norm = z×(high_is_bad?1:-1)）
      - 邊粗細：起點 |z|（越偏離均值越粗）
      - 點開可看 hover 教學「升息 → ...」
    """
    node_z: dict = {}
    node_z_norm: dict = {}
    for key, _label, _layer, high_is_bad in _SANKEY_NODES:
        iv = indicators.get(key) or {}
        z = _calc_zscore_safe(iv.get("series"), iv.get("value"))
        node_z[key] = z
        if z is not None:
            node_z_norm[key] = z if high_is_bad else -z

    def _node_color(z_norm):
        if z_norm is None:
            return "#666"
        if z_norm < -1.0:
            return "#4caf50"   # 🟢
        if z_norm < 0:
            return "#ffeb3b"   # 🟡
        if z_norm < 1.0:
            return MATERIAL_ORANGE   # 🟠
        return MATERIAL_RED       # 🔴

    labels = []
    node_colors = []
    key_to_idx = {}
    for i, (key, label, _layer, _hib) in enumerate(_SANKEY_NODES):
        z = node_z.get(key)
        z_str = f" (z={z:+.1f})" if z is not None else ""
        labels.append(label + z_str)
        node_colors.append(_node_color(node_z_norm.get(key)))
        key_to_idx[key] = i

    sources, targets, values, link_colors, link_labels = [], [], [], [], []
    for src_key, tgt_key, edu in _SANKEY_LINKS:
        sources.append(key_to_idx[src_key])
        targets.append(key_to_idx[tgt_key])
        z_src = node_z.get(src_key)
        val = max(0.3, abs(z_src)) if z_src is not None else 0.3
        values.append(round(val, 2))
        # 邊顏色用起點顏色 + 0.35 alpha
        base = node_colors[key_to_idx[src_key]]
        if base.startswith("#") and len(base) == 7:
            r = int(base[1:3], 16); g = int(base[3:5], 16); b = int(base[5:7], 16)
            link_colors.append(f"rgba({r},{g},{b},0.35)")
        else:
            link_colors.append("rgba(120,120,120,0.35)")
        link_labels.append(edu)

    n_with_z = sum(1 for z in node_z.values() if z is not None)
    ok = n_with_z >= max(1, len(_SANKEY_NODES) // 2)
    return {
        "labels": labels,
        "sources": sources,
        "targets": targets,
        "values": values,
        "node_colors": node_colors,
        "link_colors": link_colors,
        "link_labels": link_labels,
        "ok": ok,
        "note": f"{n_with_z}/{len(_SANKEY_NODES)} 節點有 z-score",
    }


# ════════════════════════════════════════════════════════════
# v18.105 總經指南針 Phase 3
# (A) 因果鏈動態權重 — Sankey 邊粗細改用「兩端 series 相關係數」
# (B) 細項燈號歷史回測 — 燈號出現後 target 指標的 3M / 6M 變化
# ════════════════════════════════════════════════════════════

def _series_correlation(s1, s2) -> float | None:
    """兩 series 共同期間的 Pearson 相關係數。資料 <12 期回 None。"""
    if s1 is None or s2 is None:
        return None
    try:
        import pandas as pd
        a = s1 if isinstance(s1, pd.Series) else pd.Series(s1)
        b = s2 if isinstance(s2, pd.Series) else pd.Series(s2)
        joined = pd.concat([a.dropna(), b.dropna()], axis=1, join="inner")
        if len(joined) < 12:
            return None
        corr = float(joined.iloc[:, 0].corr(joined.iloc[:, 1]))
        return None if (corr != corr) else corr   # NaN guard
    except Exception:
        return None


def build_macro_sankey_dynamic(indicators: dict) -> dict:
    """Phase 3 (A) — 動態權重版 Sankey。

    取代固定 |z|，改用兩端 series 在共同期間的 |corr| 決定邊粗細：
    - |corr| < 0.1 → 0.3（floor，幾乎無關）
    - 0.1 ≤ |corr| < 0.5 → 1 + |corr|×2（弱相關）
    - |corr| ≥ 0.5 → 2 + |corr|×4（強相關，最粗 6）

    Returns 同 build_macro_sankey_data 結構 + extra:
      - "link_corrs": [float|None] 每條邊的實際 corr（可正可負，用於 hover）
    """
    base = build_macro_sankey_data(indicators)
    if not base["ok"]:
        return {**base, "link_corrs": [None] * len(base["sources"])}

    link_corrs = []
    new_values = []
    new_labels = list(base["link_labels"])
    for i, (src_key, tgt_key, edu) in enumerate(_SANKEY_LINKS):
        s_src = (indicators.get(src_key) or {}).get("series")
        s_tgt = (indicators.get(tgt_key) or {}).get("series")
        corr = _series_correlation(s_src, s_tgt)
        link_corrs.append(corr)
        if corr is None:
            new_values.append(0.3)
        else:
            ac = abs(corr)
            if ac < 0.1:
                w = 0.3
            elif ac < 0.5:
                w = 1.0 + ac * 2
            else:
                w = 2.0 + ac * 4
            new_values.append(round(w, 2))
        # hover label 加 corr 註記
        if corr is not None:
            new_labels[i] = f"{edu}（corr={corr:+.2f}）"

    return {
        **base,
        "values": new_values,
        "link_labels": new_labels,
        "link_corrs": link_corrs,
        "note": base["note"] + f"；邊粗細＝動態 |corr| × 加權",
    }


def _to_monthly(s):
    """[v18.111] 統一把任意頻率的 series resample 到月底 (ME) + 季頻 ffill。

    為 Phase 3-B 服務：原版 backtest_sub_cycle_lights 用 raw period count
    當 `window=60` 門檻，對 daily / weekly / monthly / quarterly series 語意完全不同
    （日 ≈ 3 個月、週 ≈ 14 個月、月 = 5 年）→ 必須先統一頻率才有意義。

    處理：
      - 無 DatetimeIndex → 原樣回傳（已是純數列無法 resample）
      - 有 DatetimeIndex → resample("ME").last() 取每月最後一筆值
      - ffill() 把季頻（如 SLOOS）的中間月補上前期值，避免 dropna 後變 sparse
      - 最後 dropna 刪只剩 leading NaN（首期之前）
    """
    import pandas as pd
    if s is None:
        return pd.Series(dtype=float)
    try:
        ss = s if isinstance(s, pd.Series) else pd.Series(s)
        ss = ss.dropna().sort_index()
        if isinstance(ss.index, pd.DatetimeIndex):
            ss = ss.resample("ME").last().ffill().dropna()
        return ss
    except Exception:
        return pd.Series(dtype=float)


def backtest_sub_cycle_lights(indicators: dict,
                              target_key: str = "LEI",
                              window: int = 60,
                              forward_months: int = 3) -> list[dict]:
    """Phase 3 (B) — 細項燈號歷史回測（v18.111 frequency-aware 治本版）。

    對每個子領域：
      1. 取 target_key 的 series（預設 LEI / CFNAI 領先指標）
      2. 統一 resample → 月底（"ME"）+ ffill — 跨頻率（日/週/月/季）一致語意
      3. 滑動視窗 expanding：每月計算 z_avg（用該月之前的全部歷史）
      4. 依 z_avg 分桶 🟢/🟡/🟠/🔴
      5. 對每桶計算「該月後 forward_months 後 target 變化」的平均

    Args:
        indicators: macro_engine 載入後 dict（含 _SUB_CYCLE_SPEC 列出的 key）
        target_key: 用哪個指標的「forward_months 期變化」當回測 outcome
        window: **明確語意：最少觀察月數**（<window 整組跳過）
                v18.111 之前是 raw period count → 對 weekly/daily series 語意錯位
        forward_months: 燈號出現後幾個月看 target 變化

    Returns:
        [{"name": str, "icon": str, "n_obs": int,
          "n_red": int, "n_orange": int, "n_yellow": int, "n_green": int,
          "fwd_chg_red": float|None, "fwd_chg_orange": float|None,
          "fwd_chg_yellow": float|None, "fwd_chg_green": float|None,
          "verdict": str},  # 例如「🔴 燈出現後 3M 平均跌 0.5pp」
         ...]
    """
    import pandas as pd
    import numpy as np

    target_iv = indicators.get(target_key) or {}
    target_series = target_iv.get("series")
    if target_series is None:
        return [{"name": n, "icon": ic, "verdict": f"target {target_key} 無 series",
                 "n_obs": 0, "n_red": 0, "n_orange": 0, "n_yellow": 0, "n_green": 0,
                 "fwd_chg_red": None, "fwd_chg_orange": None,
                 "fwd_chg_yellow": None, "fwd_chg_green": None}
                for n, ic, _, _ in _SUB_CYCLE_SPEC]
    t = _to_monthly(target_series)

    out = []
    for name, icon, ind_list, _desc in _SUB_CYCLE_SPEC:
        # 收集這組各指標的 series — 統一 resample 到月頻後再檢查 window 門檻
        series_list = []
        for key, high_is_bad in ind_list:
            iv = indicators.get(key) or {}
            ss = _to_monthly(iv.get("series"))
            if len(ss) >= window:
                series_list.append((ss, high_is_bad))

        if not series_list or t.empty:
            out.append({
                "name": name, "icon": icon, "n_obs": 0,
                "n_red": 0, "n_orange": 0, "n_yellow": 0, "n_green": 0,
                "fwd_chg_red": None, "fwd_chg_orange": None,
                "fwd_chg_yellow": None, "fwd_chg_green": None,
                "verdict": "資料不足",
            })
            continue

        # 對每組指標算 expanding z（避免未來資訊洩漏）
        buckets = {"red": [], "orange": [], "yellow": [], "green": []}
        # 用 series_list[0] 的 index 當基準（多數月底 series 同步）
        idx_base = series_list[0][0].index
        for ts in idx_base[window:]:
            z_norms = []
            for ss, hib in series_list:
                hist = ss.loc[:ts]
                if len(hist) < window:
                    continue
                mu, sigma = float(hist.mean()), float(hist.std())
                if sigma == 0:
                    continue
                v = float(hist.iloc[-1])
                z = (v - mu) / sigma
                z_norms.append(z if hib else -z)
            if not z_norms:
                continue
            z_avg = sum(z_norms) / len(z_norms)
            # 找 forward_months 後的 target
            try:
                t_now = t.asof(ts)
                future_ts = ts + pd.DateOffset(months=forward_months)
                t_future = t.asof(future_ts)
                if pd.isna(t_now) or pd.isna(t_future):
                    continue
                fwd_chg = float(t_future) - float(t_now)
            except Exception:
                continue

            if z_avg < -1.0:
                buckets["green"].append(fwd_chg)
            elif z_avg < 0:
                buckets["yellow"].append(fwd_chg)
            elif z_avg < 1.0:
                buckets["orange"].append(fwd_chg)
            else:
                buckets["red"].append(fwd_chg)

        def _avg(lst):
            return round(float(np.mean(lst)), 3) if lst else None

        n_obs = sum(len(v) for v in buckets.values())
        avg_red    = _avg(buckets["red"])
        avg_orange = _avg(buckets["orange"])
        avg_yellow = _avg(buckets["yellow"])
        avg_green  = _avg(buckets["green"])

        # 簡單 verdict：紅燈組平均 vs 綠燈組平均
        if avg_red is not None and avg_green is not None:
            diff = avg_red - avg_green
            verdict = (f"🔴 燈後 {forward_months}M：{target_key} 平均 {avg_red:+.2f}；"
                       f"🟢 燈後：{avg_green:+.2f}（差 {diff:+.2f}）")
        elif n_obs > 0:
            verdict = f"觀察 {n_obs} 月，部分桶樣本不足"
        else:
            verdict = "資料不足"

        out.append({
            "name": name, "icon": icon, "n_obs": n_obs,
            "n_red":    len(buckets["red"]),
            "n_orange": len(buckets["orange"]),
            "n_yellow": len(buckets["yellow"]),
            "n_green":  len(buckets["green"]),
            "fwd_chg_red":    avg_red,
            "fwd_chg_orange": avg_orange,
            "fwd_chg_yellow": avg_yellow,
            "fwd_chg_green":  avg_green,
            "verdict": verdict,
        })
    return out


# ════════════════════════════════════════════════════════════
# v18.108 總經指南針 Phase 4 — 變數重要性（lag-correlation 版）
# 不引入 shap / sklearn — 用簡單 |corr(node_t, target_{t+lag})| 排序
# ════════════════════════════════════════════════════════════
def rank_macro_drivers(indicators: dict,
                       target_key: str = "LEI",
                       lag_months: int = 3,
                       min_overlap: int = 24) -> dict:
    """Phase 4 — 對 Sankey 8 節點各 series，計算與 target lag_months 後變化的
    Pearson |corr|，排序回傳變數重要性 Top-N。

    重點設計：
      - 不依賴 sklearn / shap（避免新依賴）
      - lag-correlation 而非同期 corr：driver_t vs Δtarget_{t→t+lag} → 抓「領先性」
      - 並標註 corr 方向（正/負）— 正 = 同向（升升）/ 負 = 反向（升降）
      - 共同期間 <min_overlap 月 → 跳過該節點

    Args:
        indicators: macro_engine 載入後 dict（含 _SANKEY_NODES 列出的 key）
        target_key: 用哪個指標的「lag_months 期變化」當 outcome
        lag_months: 領先期數（月）
        min_overlap: 最小共同期數（<此值該節點跳過）

    Returns:
        {
          "target":      str,                  # target_key
          "lag_months":  int,
          "ranked":      [{"key": str, "name": str, "corr": float,
                           "abs_corr": float, "direction": "+/-",
                           "n_overlap": int, "weight": "高/中/低"}, ...],
          "ok":          bool,
          "note":        str,
        }
    """
    import pandas as pd

    out_empty = {
        "target": target_key, "lag_months": lag_months,
        "ranked": [], "ok": False,
        "note": f"target {target_key} 無 series 或樣本不足",
    }
    target_iv = indicators.get(target_key) or {}
    t_series = target_iv.get("series")
    if t_series is None:
        return out_empty
    try:
        t = t_series if isinstance(t_series, pd.Series) else pd.Series(t_series)
        t = t.dropna().sort_index()
    except Exception:
        return out_empty
    if len(t) < min_overlap + lag_months:
        return out_empty

    # 目標：target_{t+lag} — 標準 leading indicator lag-corr 定義
    # 用 resample 統一到月底 (ME)，避免 daily/weekly/monthly 混用
    try:
        t_m = t.resample("ME").last().dropna() \
            if hasattr(t, "resample") else t
    except Exception:
        t_m = t
    target_lagged = t_m.shift(-lag_months).dropna()
    if len(target_lagged) < min_overlap:
        return out_empty

    ranked = []
    for node in _SANKEY_NODES:
        key, label, _layer, _hib = node
        if key == target_key:
            continue   # 不對自己做變數重要性
        iv = indicators.get(key) or {}
        s = iv.get("series")
        if s is None:
            continue
        try:
            ss = s if isinstance(s, pd.Series) else pd.Series(s)
            ss = ss.dropna().sort_index()
            if hasattr(ss, "resample"):
                ss = ss.resample("ME").last().dropna()
        except Exception:
            continue
        joined = pd.concat([ss, target_lagged], axis=1, join="inner")
        joined.columns = ["driver", "target_lagged"]
        joined = joined.dropna()
        if len(joined) < min_overlap:
            continue
        try:
            corr = float(joined["driver"].corr(joined["target_lagged"]))
        except Exception:
            continue
        if corr != corr:   # NaN guard
            continue
        ac = abs(corr)
        if ac >= 0.5:
            wlabel = "高"
        elif ac >= 0.3:
            wlabel = "中"
        else:
            wlabel = "低"
        ranked.append({
            "key": key,
            "name": label,
            "corr": round(corr, 3),
            "abs_corr": round(ac, 3),
            "direction": "+" if corr >= 0 else "-",
            "n_overlap": int(len(joined)),
            "weight": wlabel,
        })

    # 依 abs_corr 降序
    ranked.sort(key=lambda x: x["abs_corr"], reverse=True)
    return {
        "target": target_key,
        "lag_months": lag_months,
        "ranked": ranked,
        "ok": len(ranked) > 0,
        "note": (f"共 {len(ranked)} 個 driver 達 ≥{min_overlap} 月共同期"
                 if ranked else "無 driver 達樣本門檻"),
    }


# ─── v18.291: 7 維獨立合議（把 23 個相關 factor 收斂成 7 個獨立 cluster）─
# 對應 user 反饋「多筆資料判斷會不准嗎」→ 14+ 個 factor 互相高度相關（共線性）
# 把它們依「真實獨立資訊源」歸類成 7 個 cluster，看 cluster-level 合議
# 避免「同一訊號穿 5 件衣服」的多數決幻覺
INDEPENDENT_CLUSTERS: list[dict] = [
    {"name": "利率曲線", "icon": "📐",
     "keys": ["YIELD_10Y2Y", "YIELD_10Y3M", "FED_RATE"]},
    {"name": "風險偏好", "icon": "🌡️",
     "keys": ["HY_SPREAD", "VIX"]},
    {"name": "製造業景氣", "icon": "🏭",
     "keys": ["PMI", "COPPER", "ADL"]},
    {"name": "通膨", "icon": "💸",
     "keys": ["CPI", "PPI", "INFL_EXP_5Y"]},
    {"name": "貨幣寬鬆", "icon": "💰",
     "keys": ["M2", "FED_BS", "M2_WEEKLY"]},
    {"name": "匯率", "icon": "💱",
     "keys": ["DXY"]},
    {"name": "就業", "icon": "💼",
     "keys": ["UNEMPLOYMENT", "JOBLESS", "SAHM", "CONT_CLAIMS", "LEI"]},
]


def compute_cluster_signals(indicators: dict) -> list[dict]:
    """v18.291: 把 23 factor 收斂成 7 個獨立 cluster signal。

    每 cluster 取內部 weighted-avg normalized score（-1~+1）→ 紅黃綠三檔：
      ≥ +0.3 → 🟢 安全
      -0.3 ~ +0.3 → 🟡 警戒
      ≤ -0.3 → 🔴 危險

    v19.1 (C-2)：入口呼叫 ``apply_weight_overrides`` — active.json 有 weight 就蓋；
    active 空時行為跟 v18.291 完全一致。

    Returns:
        list of {name, icon, score_norm, signal, color, top_contributor, members}
    """
    try:
        from services.macro.weights_store import apply_weight_overrides
        indicators = apply_weight_overrides(indicators or {})
    except ImportError:
        indicators = indicators or {}
    out = []
    for cluster in INDEPENDENT_CLUSTERS:
        sum_w = 0.0
        sum_ws = 0.0
        members = []
        for k in cluster["keys"]:
            ind = indicators.get(k)
            if not ind:
                continue
            try:
                w = float(ind.get("weight", 1) or 1)
                s = float(ind.get("score", 0) or 0)
            except (TypeError, ValueError):
                continue
            s = max(-w, min(w, s))  # clamp 到 [-w, w]
            sum_w += w
            sum_ws += s
            members.append({
                "key": k,
                "name": str(ind.get("name", k)),
                "value": ind.get("value"),
                "score": s,
                "weight": w,
            })
        norm = (sum_ws / sum_w) if sum_w > 0 else 0.0

        if norm >= 0.3:
            signal, color = "🟢 安全", MATERIAL_GREEN
        elif norm <= -0.3:
            signal, color = "🔴 危險", MATERIAL_RED
        else:
            signal, color = "🟡 警戒", MATERIAL_ORANGE

        top = ""
        if members:
            top_m = max(members, key=lambda m: abs(m["score"]))
            v = top_m.get("value")
            v_str = f"{v}" if v is not None else "n/a"
            top = f"{top_m['name']} = {v_str}"

        out.append({
            "name": cluster["name"],
            "icon": cluster["icon"],
            "score_norm": round(norm, 2),
            "signal": signal,
            "color": color,
            "top_contributor": top,
            "members": members,
        })
    return out


def summarize_cluster_consensus(clusters: list[dict]) -> dict:
    """整理 cluster 合議結果 → 紅黃綠統計 + 文字結論。"""
    n_g = sum(1 for c in clusters if "🟢" in c.get("signal", ""))
    n_y = sum(1 for c in clusters if "🟡" in c.get("signal", ""))
    n_r = sum(1 for c in clusters if "🔴" in c.get("signal", ""))
    total = max(1, n_g + n_y + n_r)

    if n_r >= 4:
        verdict = "🔴 多數紅燈 — 高度警戒，建議降低風險暴露"
    elif n_r >= 2:
        verdict = "🟡 多紅警示 — 注意風險，建議減碼至中性"
    elif n_g >= 5:
        verdict = "🟢 多數綠燈 — 環境偏好，可正常配置"
    elif n_y >= 4:
        verdict = "⚖️ 多數警戒 — 訊號分歧，保持彈性"
    else:
        verdict = "✅ 整體中性 — 維持現有配置"

    return {
        "n_green": n_g, "n_yellow": n_y, "n_red": n_r,
        "total": total, "verdict": verdict,
    }


# ════════════════════════════════════════════════════════════════════════════
# v19.113 — China macro snapshot + 衍生(方向 B)
# 對稱 Stock 端 tw_macro + macro_helpers China 補完
# Spec(§7 對齊):純函式無 I/O,搭配 macro_repository.fetch_china_macro 上游
# ════════════════════════════════════════════════════════════════════════════

# China zone(對齊 §3.2 合理範圍)
_CHINA_THRESHOLDS = {
    "CHN_CLI":   {"green_above": 100.0, "yellow_below": 99.0, "red_below": 98.0},
    "CHN_PMI":   {"green_above": 100.0, "yellow_below": 99.0, "red_below": 98.0},
    "CHN_CPI":   {"green_low": 1.0, "green_high": 3.0, "yellow_above": 4.0, "red_above": 5.0},
    "CHN_M2":    {"red_below": 5.0, "green_above": 9.0},  # M2 YoY < 5% 緊縮
    "USDCNY":    {"green_below": 7.0, "yellow_above": 7.2, "red_above": 7.4},
}
