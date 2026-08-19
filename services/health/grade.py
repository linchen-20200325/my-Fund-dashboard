"""v19.177 #3A — 基金健康度 4D 評分 SSOT(zero-IO 純函式)。

從 `ui/tab2_single_fund.py:694-741` inline 邏輯抽出,供 Tab2 / Tab3 / 健診總表
共用同一份「個檔健康度評等」函式,杜絕同基金跨 Tab 不同 grade 散落。

設計
----
**5 維度**(老師體檢風格 — 配息核心;第 5 維 2026-08-14 加):
1. 💵 配息健康度(Coverage) — Coverage = ret_1y_total / annual_div_rate
2. 📈 風險調整報酬(Sharpe) — 年化 Sharpe Ratio
3. 📊 走勢健康(MA 方向 + 報酬) — 60d MA 方向 + ret_1y
4. 🛡️ 低波動性(σ) — 年化標準差(越低越好)
5. 💱 匯率風險 — 計價幣別對台幣的變異係數(台幣計價 = N/A,不是 0 分)

⚠️ 函式名保留 `compute_4d_health` 是為了不動 30+ 個 caller 與 UI 欄名;
   維度數以 `coverage.n_total` 為準,**不要從函式名推**。
   欄名「4D Grade / 4D Score」的白話化是另一批工作(需同步改 UI + 測試)。

**為什麼是 5D 而不是原訂的 6D**(2026-08-14 實測後改案,證據見 `scripts/audit_6d_coverage.py`):
- 費用率:官方揭露率實測 0 —— 有值的都是「拿經理費當費用率」,境外基金常差一倍以上,
  不足以拿來分 A/B。維持現況(大表有欄可看,不進總分)。
- 基金規模:2 檔就撞出 2 種字串格式(「266.04 億(美元)」vs「58,185.32 百萬歐元」),
  單位差 100 倍 + 幣別差一層,而解析錯**不會報錯**只會安靜地錯約 90 倍(§4.1)。不做。

**新增輸出 `coverage`**:幾維有證據 / 幾維適用 / 缺哪幾維。
加維度必須同時揭露分母 —— 否則 2/5 的 A 與 5/5 的 A 在表上同形。

**Grade(v19.177 #4B SSOT)**:
- A ≥ 80 / B ≥ 65 / C ≥ 50 / D ≥ 35 / F < 35
- cutoffs 走 `shared.signal_thresholds.GRADE_CUTOFFS_4D`

**6F vs 4D 分工**(v19.177 後):
- 4D = 個檔健康度評等(Tab2 KPI 卡 / Tab3 fund 評等共用此 SSOT)
- 6F = `portfolio_service.calc_fund_factor_score`,保留為「進階指標 dict」
  供「健診詳表」單獨顯示 Sortino / Calmar / Alpha / 費用率(4D 無法補的維度),
  **不再用於 grade 評等**(@deprecated for grading)
"""
from __future__ import annotations

from typing import Optional

from shared.colors import CAUTION_YELLOW, MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED, MD_GREEN_A200, TRAFFIC_NEUTRAL
from shared.signal_thresholds import GRADE_4D_MIN_FACTORS, GRADE_CUTOFFS_4D


# v19.222 P1-1:_safe_float 收口至 shared/converters.py SSOT
from shared.converters import safe_float as _safe_float  # noqa: E402



def _score_coverage(tr1y_pct: Optional[float], adr_pct: Optional[float]) -> Optional[int]:
    """配息健康度 0-100(Coverage = tr / adr 5 級分級)。

    coverage ≥ 1.5 → 95 / ≥ 1.2 → 80 / ≥ 1.0 → 65 / ≥ 0.5 → 40 / < 0.5 → 15
    """
    if tr1y_pct is None or adr_pct is None or adr_pct <= 0:
        return None
    cov = tr1y_pct / adr_pct
    if cov >= 1.5:
        return 95
    if cov >= 1.2:
        return 80
    if cov >= 1.0:
        return 65
    if cov >= 0.5:
        return 40
    return 15


def _score_sharpe(sharpe: Optional[float]) -> Optional[int]:
    """風險調整報酬 0-100。≥ 1.5 → 95 / ≥ 1.0 → 80 / ≥ 0.5 → 60 / ≥ 0 → 40 / < 0 → 15"""
    if sharpe is None:
        return None
    if sharpe >= 1.5:
        return 95
    if sharpe >= 1.0:
        return 80
    if sharpe >= 0.5:
        return 60
    if sharpe >= 0:
        return 40
    return 15


def _score_trend(ma_dir: Optional[str], tr1y_pct: Optional[float]) -> Optional[int]:
    """走勢健康 0-100(MA 方向 + ret_1y 組合判斷)。

    up + 正報酬 → 85 / up only → 70 /
    down + 負報酬 → 25 / down only → 45 /
    無 MA 方向但 ret_1y > 5% → 70 / < -5% → 25 / 否則 None
    """
    if ma_dir == "up" and tr1y_pct is not None and tr1y_pct > 0:
        return 85
    if ma_dir == "up":
        return 70
    if ma_dir == "down" and tr1y_pct is not None and tr1y_pct < 0:
        return 25
    if ma_dir == "down":
        return 45
    if tr1y_pct is not None and tr1y_pct > 5:
        return 70
    if tr1y_pct is not None and tr1y_pct < -5:
        return 25
    return None


def _score_volatility(sigma_pct: Optional[float]) -> Optional[int]:
    """低波動性 0-100。σ < 10 → 90 / < 15 → 75 / < 20 → 55 / < 30 → 35 / ≥ 30 → 15

    v19.422:σ ≤ 0 視為**無效/偽造**(真實年化 σ 恆 > 0;稽核 Bug1 發現無歷史基金 σ fallback=0
    → 被評「最低風險 90 分」)→ 回 None 不計分。
    """
    if sigma_pct is None or sigma_pct <= 0:
        return None
    if sigma_pct < 10:
        return 90
    if sigma_pct < 15:
        return 75
    if sigma_pct < 20:
        return 55
    if sigma_pct < 30:
        return 35
    return 15


def score_fx_risk(fund_ccy, fx_cv_pct: Optional[float]) -> tuple:
    """匯率風險 0-100（第 5 維，2026-08-14 Layer 3-C）。

    回 `(score | None, status)`；status 有**三種**且必須分得開（§1）：
      - `"n/a"`      台幣計價 → 沒有匯率風險是**事實**，不是缺資料。
                     評分時要從分母移除；給 0 分等於懲罰一個優點。
      - `"scored"`   算得出來
      - `"missing"`  外幣但拿不到匯率序列 → 真的缺資料

    fx_cv_pct = 變異係數 = std/mean × 100，由 caller 從
    `services.nav_fx_switch.fx_regime()` 已算好的 std / mean 導出（§2.1 不另算）。
    用 CV 而非絕對 std：USDTWD ≈ 32、JPYTWD ≈ 0.21，絕對 std 差兩個數量級，
    直接比大小是 §4.1 量綱錯誤。
    """
    from shared.signal_thresholds import (
        FX_RISK_CV_HIGH_PCT,
        FX_RISK_CV_LOW_PCT,
        FX_RISK_CV_MID_PCT,
        FX_RISK_CV_MILD_PCT,
    )
    _c = str(fund_ccy or "").strip().upper()
    if _c in ("TWD", "台幣", "新台幣"):
        return None, "n/a"
    _cv = _safe_float(fx_cv_pct)
    if _cv is None or _cv <= 0:
        # CV ≤ 0 在數學上不可能（std ≥ 0、mean > 0）→ 視為無效輸入，不是「零風險」。
        # 對照 v19.422 `_score_volatility` 的同型修正（σ=0 被評成最低風險 90 分）。
        return None, "missing"
    if _cv < FX_RISK_CV_LOW_PCT:
        return 90, "scored"
    if _cv < FX_RISK_CV_MILD_PCT:
        return 70, "scored"
    if _cv < FX_RISK_CV_MID_PCT:
        return 50, "scored"
    if _cv < FX_RISK_CV_HIGH_PCT:
        return 30, "scored"
    return 15, "scored"


def _grade_from_score(score: Optional[float]) -> tuple[str, str, str]:
    """v19.177 #4B SSOT — Grade A/B/C/D/F + 顏色 + 文字評語。

    走 GRADE_CUTOFFS_4D = (80, 65, 50, 35)。
    Returns (grade_letter, color_hex, verdict_text)
    """
    if score is None:
        return "—", TRAFFIC_NEUTRAL, "資料不足以評等"
    a, b, c, d = GRADE_CUTOFFS_4D
    if score >= a:
        return "A", MATERIAL_GREEN, "✅ 健康優質基金"
    if score >= b:
        return "B", MD_GREEN_A200, "🟢 表現穩健"
    if score >= c:
        return "C", CAUTION_YELLOW, "🟡 中性,持續觀察"
    if score >= d:
        return "D", MATERIAL_ORANGE, "🟠 警示偏弱"
    return "F", MATERIAL_RED, "🔴 多項警示"


def compute_4d_health(
    tr1y_pct: Optional[float] = None,
    adr_pct: Optional[float] = None,
    sharpe: Optional[float] = None,
    sigma_pct: Optional[float] = None,
    ma_dir: Optional[str] = None,
    *,
    fund_ccy: Optional[str] = None,
    fx_cv_pct: Optional[float] = None,
) -> dict:
    """基金健康度 4D 評分 SSOT 入口(v19.177)。

    Args
    ----
    tr1y_pct : 1Y 含息報酬率 %(走 compute_1y_total_return SSOT)
    adr_pct : 年化配息率 %(走 _resolve_adr_with_fallback SSOT)
    sharpe : 年化 Sharpe Ratio(metrics.sharpe SSOT)
    sigma_pct : 年化標準差 %(metrics.std_1y SSOT)
    ma_dir : 'up' | 'down' | None(60d MA 方向,UI 端算)

    Returns
    -------
    {
        "score": float | None,                # 綜合 0-100
        "grade": str,                          # 'A' | 'B' | 'C' | 'D' | 'F' | '—'
        "grade_color": str,                    # hex
        "verdict": str,                        # 評語
        "factors": {
            "coverage": int | None,            # 💵 配息健康度
            "sharpe": int | None,              # 📈 風險調整報酬
            "trend": int | None,               # 📊 走勢健康
            "volatility": int | None,          # 🛡️ 低波動性
        },
        "eat_warn": bool,                      # 🔴 吃本金警示(coverage < 50)
    }
    """
    f_cov = _score_coverage(_safe_float(tr1y_pct), _safe_float(adr_pct))
    f_sh = _score_sharpe(_safe_float(sharpe))
    f_tr = _score_trend(ma_dir, _safe_float(tr1y_pct))
    f_vol = _score_volatility(_safe_float(sigma_pct))
    # 第 5 維(2026-08-14):匯率風險。caller 不傳 → (None, "missing") → 行為與加維前完全相同。
    f_fx, fx_status = score_fx_risk(fund_ccy, fx_cv_pct)

    scores = [x for x in (f_cov, f_sh, f_tr, f_vol, f_fx) if x is not None]
    # v19.422 §1 修(稽核 Bug1):資料不足不硬給評等。原本只平均「算得出來的維度」、無最低數把關
    # → 單一維度(如僅 σ→90)就評 A「健康優質」,把資料稀疏基金排在完整分析基金之上。
    # 需 **≥ GRADE_4D_MIN_FACTORS 維度 且 至少一個核心維度(配息 or Sharpe)**,否則 score=None
    # → grade「—」「資料不足以評等」(user 2026-07-28 拍板)。
    _core_present = (f_cov is not None) or (f_sh is not None)
    if len(scores) >= GRADE_4D_MIN_FACTORS and _core_present:
        overall = sum(scores) / len(scores)
    else:
        overall = None
    grade, color, verdict = _grade_from_score(overall)

    # ── 評分覆蓋（2026-08-14 Layer 3-C）──────────────────────────────────
    # user 2026-08-14 拍板：加維度時**必須**同時揭露分母，比照既有的「策略分覆蓋」。
    # 理由：`GRADE_4D_MIN_FACTORS = 2` 表示湊得出 2 維就給等第。分母變 5 之後，
    # 一個 2/5 撐起來的 A 和一個 5/5 的 A 在表上長得一模一樣 ——
    # 那是 F12（樣本量不揭露）的評分版，而且後果更嚴重：
    # F12 只是欄位留白，這裡是**一個看起來很有信心的字母**。
    #
    # `n_applicable` 刻意扣掉「不適用」的維度：台幣基金沒有匯率風險是事實，
    # 把它算進分母會讓台幣基金的覆蓋率永遠低一截，等於懲罰一個優點（§1）。
    _dims = {
        "coverage": f_cov, "sharpe": f_sh, "trend": f_tr,
        "volatility": f_vol, "fx_risk": f_fx,
    }
    _n_total = len(_dims)
    _n_na = 1 if fx_status == "n/a" else 0
    _n_applicable = _n_total - _n_na
    _n_scored = len(scores)
    _missing = sorted(k for k, v in _dims.items()
                      if v is None and not (k == "fx_risk" and fx_status == "n/a"))

    return {
        "score": overall,
        "grade": grade,
        "grade_color": color,
        "verdict": verdict,
        "factors": {
            "coverage": f_cov,
            "sharpe": f_sh,
            "trend": f_tr,
            "volatility": f_vol,
            "fx_risk": f_fx,
        },
        "eat_warn": (f_cov is not None and f_cov < 50),
        # 匯率維的三態(scored / n/a / missing)—— 消費端要分得開才不會把
        # 「台幣基金沒有匯率風險」講成「匯率資料抓不到」
        "fx_risk_status": fx_status,
        "coverage": {
            "n_scored": _n_scored,          # 真的算出分數的維度數
            "n_applicable": _n_applicable,  # 適用維度數(已扣掉 N/A)
            "n_total": _n_total,            # 維度總數
            "missing": _missing,            # 哪幾維缺(不含 N/A)
            "ratio": (_n_scored / _n_applicable) if _n_applicable else None,
        },
    }
