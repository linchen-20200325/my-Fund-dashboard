"""services/macro/china.py — v19.199 P1-7 中國 macro 子模組(信貸脈衝 / 五率 / regime / modifier)。

從 macro_service 主檔抽出。原 line 2940-3390:
- calc_china_credit_impulse_proxy
- _classify_zone / china_macro_snapshot
- _score_cli / _score_pmi / _score_cpi / _score_m2 / _score_usdcny
- compute_china_subscore / classify_china_regime
- apply_china_modifier / get_china_snapshot
"""
from __future__ import annotations

from typing import Optional

import pandas as pd


# China zone(對齊 §3.2 合理範圍)— v19.199 P1-7 從原 macro_service.py:2931 搬入
_CHINA_THRESHOLDS = {
    "CHN_CLI":   {"green_above": 100.0, "yellow_below": 99.0, "red_below": 98.0},
    "CHN_PMI":   {"green_above": 100.0, "yellow_below": 99.0, "red_below": 98.0},
    "CHN_CPI":   {"green_low": 1.0, "green_high": 3.0, "yellow_above": 4.0, "red_above": 5.0},
    "CHN_M2":    {"red_below": 5.0, "green_above": 9.0},  # M2 YoY < 5% 緊縮
    "USDCNY":    {"green_below": 7.0, "yellow_above": 7.2, "red_above": 7.4},
}


def calc_china_credit_impulse_proxy(m2_series: Optional[pd.Series],
                                    lag_months: int = 12) -> Optional[float]:
    """信貸脈衝 proxy:M2 YoY 與 12 月前 M2 YoY 的差(% pts)。

    為什麼是 proxy:真正信貸脈衝 = Δ(信貸/GDP),需社融存量 + GDP,
    無乾淨 FRED 來源;M2 YoY 變化是粗略貨幣寬鬆代理。

    Args
    ----
    m2_series: M2 YoY % 月頻時間序(date index ascending);**需已經是 YoY**,
               若上游給 level,caller 自己先 `.pct_change(12) * 100`。
    lag_months: 比較期,預設 12 月。

    Returns
    -------
    float | None
        正值 = 12 月內 M2 加速(寬鬆中)、負值 = 緊縮中;
        資料不足 N+1 筆 → None(§1 不偽造)。
    """
    if m2_series is None:
        return None
    try:
        s = pd.Series(m2_series).dropna()
    except (TypeError, ValueError):
        return None
    if len(s) < lag_months + 1:
        return None
    cur = float(s.iloc[-1])
    prev = float(s.iloc[-(lag_months + 1)])
    return round(cur - prev, 3)


def _classify_zone(value: Optional[float], rules: dict) -> str:
    """通用 traffic 分類:依 rules dict(green_above/yellow_below/red_below/...)→ 字串。"""
    if value is None or pd.isna(value):
        return "⬜ 無資料"
    v = float(value)
    if "red_above" in rules and v > rules["red_above"]:
        return "🔴 紅"
    if "red_below" in rules and v < rules["red_below"]:
        return "🔴 紅"
    if "yellow_above" in rules and v > rules["yellow_above"]:
        return "🟡 黃"
    if "yellow_below" in rules and v < rules["yellow_below"]:
        return "🟡 黃"
    if "green_above" in rules and v > rules["green_above"]:
        return "🟢 綠"
    if "green_below" in rules and v < rules["green_below"]:
        return "🟢 綠"
    if "green_low" in rules and "green_high" in rules:
        if rules["green_low"] <= v <= rules["green_high"]:
            return "🟢 綠"
    return "⚪ 中性"


def china_macro_snapshot(china_dict: dict) -> dict:
    """組裝 5 條 China macro raw fetch 結果為簡單 snapshot。

    Args
    ----
    china_dict: dict[series_id, DataFrame]
        repositories.macro_repository.fetch_china_macro() 的回傳結果;
        每個 DataFrame 含 [date, value, source, fetched_at] 至少欄位。

    Returns
    -------
    dict 包含 5 個 key:`cli` / `pmi` / `cpi_yoy` / `m2_yoy` / `usdcny`,
    每個對應:
        {
          "value": float | None,
          "date": str | None,        # 最新月份 YYYY-MM-DD
          "zone": str,                # 🟢/🟡/🔴/⚪/⬜
          "source": str | None,       # FRED:<id>
        }
    + `credit_impulse_proxy`(M2 YoY 12 月變化,§4.3 衍生)。

    §1 fail loud:單條 series 缺資料 → 該 key 的 value=None,**不偽造**。

    v19.115 校正(§4.1 量綱):
    - `FRED_CHN_M2`(`MABMM301CNM189S`)FRED 回的是 **M3 level (兆 CNY)**,
      非 YoY %。本函式內部先 `pct_change(12) * 100` 轉 YoY 才進 scorer。
    - `m2_yoy["value"]` 為轉換後 YoY %,可直接餵 `_score_m2`(門檻 5/9%)
    - `credit_impulse_proxy` 輸入也用 YoY 序列,而非 level
    """
    # SSOT 從 shared/fred_series 引入(對應 _CHINA_FRED_SPECS)
    from shared.fred_series import (
        FRED_CHN_CPI,
        FRED_CHN_M2,
        FRED_CHN_OECD_CLI,
        FRED_CHN_PMI,
        FRED_CNH_USD,
    )

    def _extract(sid: str, threshold_key: str) -> dict:
        df = china_dict.get(sid)
        out = {"value": None, "date": None, "zone": "⬜ 無資料", "source": None}
        if df is None or df.empty:
            return out
        try:
            last = df.iloc[-1]
            v = float(last["value"])
            d = pd.Timestamp(last["date"]).strftime("%Y-%m-%d")
            out["value"] = round(v, 4)
            out["date"] = d
            out["zone"] = _classify_zone(v, _CHINA_THRESHOLDS.get(threshold_key, {}))
            out["source"] = str(last.get("source", f"FRED:{sid}"))
        except (KeyError, ValueError, TypeError) as e:
            print(f"[china_macro_snapshot/{sid}] extract 失敗: {e}")
        return out

    # v19.115 校正:M2(實 M3 level)先轉 YoY series 再進 _extract 路徑
    # 避免直接吃 level 餵 _score_m2(門檻 5/9%)造成評分恆 100 的 bug
    m2_yoy_df = None
    m2_df_raw = china_dict.get(FRED_CHN_M2)
    if m2_df_raw is not None and not m2_df_raw.empty:
        try:
            tmp = m2_df_raw.copy()
            tmp["value"] = tmp["value"].astype(float).pct_change(12) * 100.0
            tmp = tmp.dropna(subset=["value"])
            if not tmp.empty:
                m2_yoy_df = tmp
        except (KeyError, ValueError, TypeError) as e:
            print(f"[china_macro_snapshot/m2_yoy_conv] {e}")

    def _extract_m2_yoy() -> dict:
        out = {"value": None, "date": None, "zone": "⬜ 無資料", "source": None}
        if m2_yoy_df is None:
            return out
        try:
            last = m2_yoy_df.iloc[-1]
            v = float(last["value"])
            d = pd.Timestamp(last["date"]).strftime("%Y-%m-%d")
            out["value"] = round(v, 4)
            out["date"] = d
            out["zone"] = _classify_zone(v, _CHINA_THRESHOLDS.get("CHN_M2", {}))
            out["source"] = str(last.get("source", f"FRED:{FRED_CHN_M2}"))
        except (KeyError, ValueError, TypeError) as e:
            print(f"[china_macro_snapshot/m2_yoy] {e}")
        return out

    snapshot = {
        "cli":     _extract(FRED_CHN_OECD_CLI, "CHN_CLI"),
        "pmi":     _extract(FRED_CHN_PMI, "CHN_PMI"),
        "cpi_yoy": _extract(FRED_CHN_CPI, "CHN_CPI"),
        "m2_yoy":  _extract_m2_yoy(),
        "usdcny":  _extract(FRED_CNH_USD, "USDCNY"),
    }

    # 衍生:信貸脈衝 proxy(M2 YoY 12 月變化)— 用已轉換的 YoY series
    if m2_yoy_df is not None:
        try:
            m2_yoy_series = m2_yoy_df["value"].astype(float)
            snapshot["credit_impulse_proxy"] = calc_china_credit_impulse_proxy(m2_yoy_series)
        except (KeyError, ValueError, TypeError) as e:
            print(f"[china_macro_snapshot/credit_impulse] {e}")
            snapshot["credit_impulse_proxy"] = None
    else:
        snapshot["credit_impulse_proxy"] = None

    return snapshot


# ════════════════════════════════════════════════════════════════════════════
# v19.114 — China 副盤(sub-score + sub-regime)
# 設計決策(對齊 §-1 + §8.1 step 6):
#   - 不接入主 health / 主 phase(避免改變既有評分歷史可信度)
#   - 4 因子 OECD 月頻 + 1 因子 USDCNY 日頻,5 因子等權 0.20 each
#   - 4 級 regime + USDCNY > 7.4 獨立 flag
#   - 全缺 → return None(§1 fail loud,不偽 50 中性)
# ════════════════════════════════════════════════════════════════════════════

# 各因子打分函式(0/50/100,對應 紅/黃/綠 zone)
def _score_cli(v: Optional[float]) -> Optional[float]:
    """CLI 評分:>100 擴張 / 99-100 中性 / <99 收縮 / <98 衰退 → 100/50/25/0"""
    if v is None or pd.isna(v):
        return None
    v = float(v)
    if v > 100.0:  return 100.0
    if v >= 99.0:  return 50.0
    if v >= 98.0:  return 25.0
    return 0.0


def _score_pmi(v: Optional[float]) -> Optional[float]:
    """PMI proxy 評分:同 CLI 結構"""
    return _score_cli(v)


def _score_cpi(v: Optional[float]) -> Optional[float]:
    """CPI YoY 評分:1-3% 理想 100 / 0-1 或 3-4 中性 50 / >4 過熱 0 / <0 通縮 0"""
    if v is None or pd.isna(v):
        return None
    v = float(v)
    if 1.0 <= v <= 3.0:  return 100.0
    if 0.0 <= v < 1.0 or 3.0 < v <= 4.0:  return 50.0
    return 0.0


def _score_m2(v: Optional[float]) -> Optional[float]:
    """M2 YoY 評分:>=9% 寬鬆 100 / 5-9% 中性 50 / <5% 緊縮 0"""
    if v is None or pd.isna(v):
        return None
    v = float(v)
    if v >= 9.0:  return 100.0
    if v >= 5.0:  return 50.0
    return 0.0


def _score_usdcny(v: Optional[float]) -> Optional[float]:
    """USDCNY 評分:<7.0 強勢 100 / 7.0-7.2 中性 50 / 7.2-7.4 偏弱 25 / >7.4 大貶 0"""
    if v is None or pd.isna(v):
        return None
    v = float(v)
    if v < 7.0:  return 100.0
    if v <= 7.2: return 50.0
    if v <= 7.4: return 25.0
    return 0.0


def compute_china_subscore(snapshot: dict) -> Optional[dict]:
    """5 因子等權 0.20 each 計算 China 副盤分數。

    Args
    ----
    snapshot: china_macro_snapshot() 回傳結果(含 cli/pmi/cpi_yoy/m2_yoy/usdcny)

    Returns
    -------
    dict | None
        {
          "score": float in [0,100] | None,       # 5 因子加權後;全缺 → None
          "factors": {                             # 各因子細項
              "cli": {"value": float|None, "score": 0-100|None},
              "pmi": ...,
              "cpi": ...,
              "m2": ...,
              "usdcny": ...,
          },
          "n_available": int,                      # 有資料的因子數(0-5)
          "n_total": 5,
        }
        全缺(n_available=0)→ None,§1 fail loud,**不偽 50 中性**。
    """
    if not snapshot:
        return None

    # 對齊 snapshot 鍵 → 評分函式
    scorers = [
        ("cli",    "cli",     _score_cli),
        ("pmi",    "pmi",     _score_pmi),
        ("cpi",    "cpi_yoy", _score_cpi),
        ("m2",     "m2_yoy",  _score_m2),
        ("usdcny", "usdcny",  _score_usdcny),
    ]

    factors = {}
    scores = []
    for short, snap_key, scorer in scorers:
        entry = snapshot.get(snap_key, {})
        val = entry.get("value") if isinstance(entry, dict) else None
        s = scorer(val)
        factors[short] = {"value": val, "score": s}
        if s is not None:
            scores.append(s)

    n_avail = len(scores)
    if n_avail == 0:
        return None

    # 等權平均:缺項自動重分配(僅平均有效項)
    avg = round(sum(scores) / n_avail, 2)
    return {
        "score": avg,
        "factors": factors,
        "n_available": n_avail,
        "n_total": 5,
    }


def classify_china_regime(snapshot: dict) -> dict:
    """從 China snapshot 推導 4 級 regime + USDCNY 警示 flag。

    Levels:
      🟢 擴張:CLI > 100 AND PMI > 100
      🟡 減速:CLI < 99 OR PMI < 99(但非衰退)
      🔴 衰退/緊縮:(CLI < 98 AND PMI < 98) OR M2 < 5%
      ⚪ 中性:其餘
      🚨 fx_alert flag(獨立):USDCNY > 7.4

    任一關鍵指標缺 → regime = "⬜ 資料不足"

    Returns
    -------
    dict:
        {"regime": str, "fx_alert": bool, "reason": str}
    """
    if not snapshot:
        return {"regime": "⬜ 資料不足", "fx_alert": False, "reason": "snapshot 空"}

    def _val(k: str):
        entry = snapshot.get(k, {})
        return entry.get("value") if isinstance(entry, dict) else None

    cli = _val("cli")
    pmi = _val("pmi")
    m2 = _val("m2_yoy")
    usdcny = _val("usdcny")

    # FX flag 獨立判讀(可在任何 regime 同時亮起)
    fx_alert = (usdcny is not None and not pd.isna(usdcny) and float(usdcny) > 7.4)

    # 主 regime 至少需 CLI + PMI 之一可判
    if cli is None and pmi is None:
        return {"regime": "⬜ 資料不足", "fx_alert": fx_alert,
                "reason": "CLI/PMI 雙缺"}

    # 衰退/緊縮優先判定
    cli_red = (cli is not None and float(cli) < 98.0)
    pmi_red = (pmi is not None and float(pmi) < 98.0)
    m2_tight = (m2 is not None and float(m2) < 5.0)
    if (cli_red and pmi_red) or m2_tight:
        reasons = []
        if cli_red and pmi_red:
            reasons.append(f"CLI={cli:.1f} & PMI={pmi:.1f} 雙紅")
        if m2_tight:
            reasons.append(f"M2={m2:.1f}% 緊縮")
        return {"regime": "🔴 衰退/緊縮", "fx_alert": fx_alert,
                "reason": "; ".join(reasons)}

    # 擴張:CLI 與 PMI 兩者都 > 100
    cli_green = (cli is not None and float(cli) > 100.0)
    pmi_green = (pmi is not None and float(pmi) > 100.0)
    if cli_green and pmi_green:
        return {"regime": "🟢 擴張", "fx_alert": fx_alert,
                "reason": f"CLI={cli:.1f} & PMI={pmi:.1f} 雙綠"}

    # 減速:CLI 或 PMI 任一 < 99(非衰退)
    cli_slow = (cli is not None and float(cli) < 99.0)
    pmi_slow = (pmi is not None and float(pmi) < 99.0)
    if cli_slow or pmi_slow:
        which = []
        if cli_slow:  which.append(f"CLI={cli:.1f}")
        if pmi_slow:  which.append(f"PMI={pmi:.1f}")
        return {"regime": "🟡 減速", "fx_alert": fx_alert,
                "reason": " / ".join(which) + " <99"}

    return {"regime": "⚪ 中性", "fx_alert": fx_alert,
            "reason": f"CLI={cli}, PMI={pmi} 皆 99-100 區間"}


# ════════════════════════════════════════════════════════════════════════════
# v19.116 — China 副盤 → 主分 乘法 modifier(user 指定 blend 設計)
# 設計:composite = main × (0.7 + 0.3 × china/100)
#   - china=100(全綠)→ multiplier=1.0 → composite=main(不加分)
#   - china=50(中性)→ multiplier=0.85 → composite=0.85×main(15% 懲罰)
#   - china=0  (全紅)→ multiplier=0.7 → composite=0.7×main(30% 懲罰)
# 哲學:不對「中國好」主觀加成(避免主分高估),只對「中國壞」做風險溢價懲罰。
#
# 用法(caller 自行選用,本檔不強制套用):
#   from services.macro_service import (
#       china_macro_snapshot, compute_china_subscore, apply_china_modifier,
#       calc_macro_phase,
#   )
#   main = calc_macro_phase(indicators)["score"]
#   china = compute_china_subscore(china_macro_snapshot(china_dict))
#   composite = apply_china_modifier(main, china["score"] if china else None)
# ════════════════════════════════════════════════════════════════════════════

CHINA_MODIFIER_FLOOR: float = 0.7  # China 全紅時的最低折扣(70% × main)
CHINA_MODIFIER_RANGE: float = 0.3  # 0.7 ~ 1.0 之間擺動


def apply_china_modifier(main_score: Optional[float],
                         china_subscore: Optional[float]) -> Optional[dict]:
    """套用 China 副盤對主分的乘法 modifier。

    公式:composite = main × (CHINA_MODIFIER_FLOOR + CHINA_MODIFIER_RANGE × china/100)
    範圍:multiplier ∈ [0.7, 1.0],只懲罰不加成。

    Args
    ----
    main_score: 主 macro 分數,[0, 100] 或 None
    china_subscore: China 副盤分數,[0, 100] 或 None(無資料)

    Returns
    -------
    dict | None:
      - main_score=None 或 非數值 → None(無主分可乘)
      - 否則 dict 含:
          composite:  float [0,100],套用 modifier 後的分數(若 china=None 則=main)
          main:       float [0,100],主分(已 clip)
          china:      float [0,100] | None,使用的 china 副盤分數(None 表無資料)
          multiplier: float [0.7, 1.0],實際使用的乘子(china=None 時為 1.0,fail-safe)

    §1 fail loud:中國資料缺失時 multiplier=1.0(不懲罰)但欄位明示 china=None,
    caller 從 china==None 即知「modifier 未實際啟用」,UI 可條件渲染。
    """
    if main_score is None:
        return None
    try:
        m = float(main_score)
    except (TypeError, ValueError):
        return None
    # main clip 到 [0,100] 防越界帶來的結果越界
    m_clipped = max(0.0, min(100.0, m))

    if china_subscore is None:
        # Fail-safe:無中國資料 → multiplier=1.0,composite=main
        return {
            "composite": round(m_clipped, 2),
            "main": round(m_clipped, 2),
            "china": None,
            "multiplier": 1.0,
        }
    try:
        c = float(china_subscore)
    except (TypeError, ValueError):
        return None
    # clip china 到 [0, 100] 防越界
    c_clipped = max(0.0, min(100.0, c))
    multiplier = CHINA_MODIFIER_FLOOR + CHINA_MODIFIER_RANGE * (c_clipped / 100.0)
    composite = max(0.0, min(100.0, m_clipped * multiplier))
    return {
        "composite": round(composite, 2),
        "main": round(m_clipped, 2),
        "china": round(c_clipped, 2),
        "multiplier": round(multiplier, 4),
    }


def get_china_snapshot(fred_api_key: str) -> dict:
    """v19.118 L2 一站式 wrapper:抓取 + 組裝 China macro snapshot。

    存在意義(§8.2 分層守衛):避免 L3 UI 直呼 L1 fetch_china_macro,
    讓 ui/tab1_macro.py 的 China drag 面板用單一 L2 介面取數(無需登記
    EX-PASSTHRU-1 例外)。本函式僅串接已存在的 L1 fetch_china_macro
    + L2 china_macro_snapshot,5 行 thin wrapper。

    Args
    ----
    fred_api_key: FRED API key,空字串 → 回空 dict(fail-safe)

    Returns
    -------
    dict: snapshot 結構同 china_macro_snapshot(),5 key + credit_impulse_proxy;
          fred_api_key 空時回 {} ,caller 應檢查 truthy 後再 compute_china_subscore。
    """
    from repositories.macro_repository import fetch_china_macro
    if not fred_api_key:
        return {}
    return china_macro_snapshot(fetch_china_macro(fred_api_key))
