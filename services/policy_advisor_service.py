"""services/policy_advisor_service.py — 保單視圖純規則建議引擎
（v11.0 C-18 從 policy_advisor.py 搬入）

依據三個訊號（σ 位階、配息覆蓋率、60MA 趨勢）配合可選 VIX，短路匹配 10 條規則，
組合出一句中文操作建議。完全純函數、零外部依賴、可獨立單測。

設計原則（與專案 §2 精準讀寫 §4 鋼鐵自省一致）：
- 不打 HTTP、不讀 streamlit 狀態、不抓即時資料
- 輸入皆為已算好的中間結果（避免重複計算）
- 規則由上往下短路匹配，確保決定性與可追溯

v11.0 分層歸位：本檔屬於 Service Layer，純規則決策（零 I/O 零依賴）。
向後相容：根目錄 policy_advisor.py 保留 shim re-export，既有 caller 零修改。
"""
from __future__ import annotations

from typing import Iterable, Optional


# 規則代碼（測試斷言用，外部勿改字串）
INSUFFICIENT_DATA      = "INSUFFICIENT_DATA"
DEEP_DROP_VIX_BUY      = "DEEP_DROP_VIX_BUY"
DEEP_DROP_RED_SWITCH   = "DEEP_DROP_RED_SWITCH"
DEEP_DROP_NEUTRAL      = "DEEP_DROP_NEUTRAL"
MID_DROP_MA_UP         = "MID_DROP_MA_UP"
MID_DROP_MA_DOWN       = "MID_DROP_MA_DOWN"
NEAR_HWM_RED_TP_CHECK  = "NEAR_HWM_RED_TP_CHECK"
NEAR_HWM_GREEN_HOLD    = "NEAR_HWM_GREEN_HOLD"
ABOVE_HWM_TAKE_PROFIT  = "ABOVE_HWM_TAKE_PROFIT"
DEFAULT_HOLD           = "DEFAULT_HOLD"

# P3：保單級配置建議規則代碼
POLICY_EMPTY                 = "POLICY_EMPTY"
POLICY_CORE_OVER             = "POLICY_CORE_OVER"          # 核心過重
POLICY_CORE_UNDER            = "POLICY_CORE_UNDER"         # 核心過輕
POLICY_RISK_HEAVY_DROP       = "POLICY_RISK_HEAVY_DROP"    # 多檔深度超跌
POLICY_RISK_HEAVY_RED        = "POLICY_RISK_HEAVY_RED"     # 多檔吃本金
POLICY_HEALTHY               = "POLICY_HEALTHY"            # 配置健康


def _coverage_str(div: dict | None) -> str:
    cov = (div or {}).get("coverage")
    return f"{cov:.2f}" if isinstance(cov, (int, float)) else "N/A"


def advise_fund(
    sigma_info: Optional[dict],
    dividend_info: Optional[dict],
    ma60_trend: Optional[str] = None,
    vix: Optional[float] = None,
) -> dict:
    """
    回傳 {text, code, color}

    sigma_info 預期欄位：sigma_rank (float)，或 error (str)
    dividend_info 預期欄位：alert_level ("red"|"yellow"|"green"|"grey")、coverage (float|None)
    ma60_trend："up" | "down" | None
    vix：當前 VIX 值，None 視為未提供
    """
    if not sigma_info or "error" in sigma_info or sigma_info.get("sigma_rank") is None:
        return {
            "text": "⏳ 資料不足，暫無法判斷（NAV 序列 < 30 點或無 σ 位階）",
            "code": INSUFFICIENT_DATA,
            "color": "grey",
        }

    rank = float(sigma_info["sigma_rank"])
    alert = (dividend_info or {}).get("alert_level", "grey")
    cov_str = _coverage_str(dividend_info)

    # ── 規則 1：深度超跌 + 恐慌 → 跌了就買 ─────────────────────────
    if rank <= -2.0 and vix is not None and vix >= 30:
        return {
            "text": f"σ {rank:+.1f}σ 大買區 + VIX {vix:.0f} 恐慌 → 符合「跌了就買」，建議分批加碼",
            "code": DEEP_DROP_VIX_BUY,
            "color": "red",
        }

    # ── 規則 2：深度超跌 + 配息吃本金 → 汰弱換強 ────────────────────
    if rank <= -2.0 and alert == "red":
        return {
            "text": f"σ {rank:+.1f}σ 超跌 + 配息覆蓋率 {cov_str} 吃本金 → 評估汰弱換強，勿盲目攤平",
            "code": DEEP_DROP_RED_SWITCH,
            "color": "red",
        }

    # ── 規則 3：深度超跌 + 其他 → 達加碼區 ──────────────────────────
    if rank <= -2.0:
        return {
            "text": f"σ {rank:+.1f}σ 進入加碼參考區 → 配息穩健，可分批承接",
            "code": DEEP_DROP_NEUTRAL,
            "color": "orange",
        }

    # ── 規則 4：中度跌 + 60MA 上升 → 趨勢未壞 ───────────────────────
    if -2.0 < rank <= -1.0 and ma60_trend == "up":
        return {
            "text": f"σ {rank:+.1f}σ 觀察區 + 60MA 上升 → 趨勢未壞，留意 -2σ 加碼點",
            "code": MID_DROP_MA_UP,
            "color": "yellow",
        }

    # ── 規則 5：中度跌 + 60MA 下行 → 等趨勢轉折 ─────────────────────
    if -2.0 < rank <= -1.0 and ma60_trend == "down":
        return {
            "text": f"σ {rank:+.1f}σ 觀察區 + 60MA 下行 → 等趨勢轉折再決策,勿接刀",
            "code": MID_DROP_MA_DOWN,
            "color": "orange",
        }

    # ── 規則 6：接近 HWM + 紅燈 → 短期反彈停利檢視 ──────────────────
    if -0.5 < rank <= 0.5 and alert == "red":
        return {
            "text": f"σ 接近 HWM ({rank:+.2f}σ) + 配息吃本金（覆蓋率 {cov_str}）→ 短期反彈停利檢視",
            "code": NEAR_HWM_RED_TP_CHECK,
            "color": "orange",
        }

    # ── 規則 7：接近 HWM + 綠燈 → 健康持有 ──────────────────────────
    if -0.5 < rank <= 0.5 and alert == "green":
        return {
            "text": f"σ 接近 HWM ({rank:+.2f}σ) + 含息報酬充分覆蓋配息（覆蓋率 {cov_str}）→ 健康持有",
            "code": NEAR_HWM_GREEN_HOLD,
            "color": "green",
        }

    # ── 規則 8：超越 HWM → 過熱停利 ──────────────────────────────────
    if rank > 0.5:
        return {
            "text": f"σ {rank:+.2f}σ 創新高區 → 留意過熱,可分批停利或設追蹤停損",
            "code": ABOVE_HWM_TAKE_PROFIT,
            "color": "yellow",
        }

    # ── 規則 9：其他情況 → 標準持有 ─────────────────────────────────
    return {
        "text": f"σ {rank:+.2f}σ — 標準持有區,持續觀察 60MA 與配息覆蓋率",
        "code": DEFAULT_HOLD,
        "color": "grey",
    }


# ══════════════════════════════════════════════════════════════════════
# P3：保單級配置建議（純函式，無 streamlit / 無 I/O）
# ══════════════════════════════════════════════════════════════════════
def recommend_policy(
    funds_in_policy: Iterable[dict],
    target_core_pct: float = 75.0,
    risk_count_threshold: int = 2,
) -> dict:
    """
    輸入單一保單下的 fund 條目集合，依下列訊號短路匹配 5 條規則：
    - core_pct 偏離 target 超過 ±10%（核心過重 / 過輕）
    - 多檔深度超跌（sigma_info.sigma_rank ≤ -2.0）
    - 多檔吃本金（dividend_info.alert_level == "red"）

    每個 fund 預期欄位：
      invest_twd (int|float)
      is_core (bool)         ← Tab3 已用既有 _is_core_fund heuristic 填好
      sigma_info (dict?)     ← optional；若 None / 缺 sigma_rank 視為不計
      dividend_info (dict?)  ← optional；若 None / 無 alert_level 視為不計

    回傳: {text, code, color}
    """
    funds = [f for f in (funds_in_policy or []) if isinstance(f, dict)]
    total_amt = sum(float(f.get("invest_twd", 0) or 0) for f in funds)

    if total_amt <= 0:
        return {
            "text": "保單內無有效投入金額；先在 T7「📝 編輯初始持倉」填入單位數。",
            "code": POLICY_EMPTY,
            "color": "grey",
        }

    core_amt = sum(float(f.get("invest_twd", 0) or 0) for f in funds if f.get("is_core"))
    core_pct = round(core_amt / total_amt * 100.0, 1)
    diff = round(core_pct - float(target_core_pct), 1)

    # ── 規則 P1：核心過重（>target + 10%） ────────────────────────────
    if diff > 10.0:
        return {
            "text": (
                f"核心配置 {core_pct}% 高於目標 {target_core_pct:.0f}%（+{diff:.1f}%）"
                f" → 可釋出至衛星追求成長，或留意核心過度集中"
            ),
            "code": POLICY_CORE_OVER,
            "color": "yellow",
        }

    # ── 規則 P2：核心過輕（<target - 10%） ────────────────────────────
    if diff < -10.0:
        return {
            "text": (
                f"核心配置 {core_pct}% 低於目標 {target_core_pct:.0f}%（{diff:+.1f}%）"
                f" → 評估從衛星轉核心鞏固防禦"
            ),
            "code": POLICY_CORE_UNDER,
            "color": "orange",
        }

    # ── 規則 P3：多檔深度超跌（sigma_rank ≤ -2.0） ─────────────────────
    risky_n = 0
    for _f in funds:
        _sig = (_f.get("sigma_info") or {})
        _r = _sig.get("sigma_rank")
        if isinstance(_r, (int, float)) and _r <= -2.0:
            risky_n += 1
    if risky_n >= risk_count_threshold:
        return {
            "text": (
                f"{risky_n} 檔基金已達深度超跌（σ ≤ -2.0），保單系統性風險高 "
                f"→ 可分批加碼但避免單押；先檢視配息覆蓋率"
            ),
            "code": POLICY_RISK_HEAVY_DROP,
            "color": "red",
        }

    # ── 規則 P4：多檔吃本金（dividend alert == red） ──────────────────
    red_n = 0
    for _f in funds:
        _div = (_f.get("dividend_info") or {})
        if _div.get("alert_level") == "red":
            red_n += 1
    if red_n >= risk_count_threshold:
        return {
            "text": (
                f"{red_n} 檔基金吃本金（配息 > 含息報酬）→ 檢視配息來源、評估汰弱換強，"
                f"避免本金侵蝕"
            ),
            "code": POLICY_RISK_HEAVY_RED,
            "color": "red",
        }

    # ── 規則 P5：其餘 → 健康 ─────────────────────────────────────────
    return {
        "text": (
            f"核心 {core_pct}% / 衛星 {100.0 - core_pct:.1f}%（偏差 {diff:+.1f}%）"
            f" → 配置健康，持續觀察 60MA 與配息覆蓋率"
        ),
        "code": POLICY_HEALTHY,
        "color": "green",
    }
