"""services/decision_matrix.py — v19.15 決策矩陣（純函式）

將「總經 verdict」映射為「逐檔持股動作」（持有 / 加碼 / 減倉 / 全撤）+ 建議權重 +
白話原因。完全純函數、零外部依賴（無 streamlit / 無 HTTP / 無快取）、可獨立單測。

設計原則（對齊 §2/§4）：
- 不打 HTTP、不讀 streamlit 狀態
- 輸入皆為已算好的中間結果（verdict_level / verdict_score / 逐檔 sigma_info 與 dividend_info）
- 規則由「verdict 大方向」往下短路 → 個股 sigma/cov 覆寫，確保決定性與可追溯
- target_pct 表「**相對原配置**的建議比例」（100=維持／130=加碼三成／50=砍半／0=全撤）
  保留絕對權重決定權在 user，避免假精準

對應上游：
- verdict_level 由 ui/helpers/macro_helpers.composite_verdict 第 2 元素提供
- verdict_score 是 calculate_composite_score 後的 float
- fund.is_core 沿用 Tab3 _is_core_fund 既有 heuristic
- sigma_info / dividend_info 結構同 policy_advisor_service.advise_fund 第 1/2 參數
"""
from __future__ import annotations

from typing import Iterable, Optional

# Verdict level → 5 級對應動作標籤（與 composite_verdict 第 2 元素對齊）
VERDICT_LEVELS = ("極度樂觀", "樂觀", "中性", "悲觀", "極度悲觀")

# 動作代碼（測試斷言用，外部勿改字串）
ACTION_HOLD   = "持有"
ACTION_ADD    = "加碼"
ACTION_REDUCE = "減倉"
ACTION_EXIT   = "全撤"

ACTIONS = (ACTION_HOLD, ACTION_ADD, ACTION_REDUCE, ACTION_EXIT)

# Action → 顏色（與 policy_advisor 同色系）
_ACTION_COLOR = {
    ACTION_HOLD:   "grey",
    ACTION_ADD:    "red",      # 跌了買 = 紅燈買入
    ACTION_REDUCE: "orange",
    ACTION_EXIT:   "red",
}

# Action → target_pct (相對原配置 %)
_ACTION_TARGET_PCT = {
    ACTION_HOLD:   100,
    ACTION_ADD:    130,
    ACTION_REDUCE: 50,
    ACTION_EXIT:   0,
}


def _verdict_default_action(level: str, is_core: bool) -> str:
    """5 級 verdict × 核心/衛星 → 預設動作（不看個股訊號）"""
    if level == "極度樂觀":
        return ACTION_HOLD if is_core else ACTION_ADD
    if level == "樂觀":
        return ACTION_HOLD
    if level == "中性":
        return ACTION_HOLD
    if level == "悲觀":
        return ACTION_HOLD if is_core else ACTION_REDUCE
    if level == "極度悲觀":
        return ACTION_REDUCE if is_core else ACTION_EXIT
    return ACTION_HOLD


def _action_after_individual_signals(
    base_action: str,
    sigma_rank: Optional[float],
    div_alert: Optional[str],
    level: str,
    is_core: bool,
) -> tuple[str, list[str]]:
    """個股訊號覆寫：σ 極端 + 配息吃本金。回 (覆寫後 action, 原因 tag list)"""
    tags: list[str] = []
    action = base_action

    # σ ≤ -2 深度超跌
    if sigma_rank is not None and sigma_rank <= -2.0:
        if level in ("極度樂觀", "樂觀"):
            tags.append(f"σ {sigma_rank:+.1f}σ 深跌+多頭=分批承接")
            action = ACTION_ADD
        elif level == "中性":
            tags.append(f"σ {sigma_rank:+.1f}σ 深跌參考區")
            if action == ACTION_HOLD:
                action = ACTION_ADD
        elif level in ("悲觀", "極度悲觀"):
            tags.append(f"σ {sigma_rank:+.1f}σ 深跌但風險未消 → 觀望勿接刀")
            # 悲觀情境深跌不加碼，沿用 verdict 預設（衛星仍是 REDUCE/EXIT）

    # σ > +1 過熱
    elif sigma_rank is not None and sigma_rank > 1.0:
        if level in ("樂觀", "極度樂觀") and not is_core:
            tags.append(f"σ {sigma_rank:+.2f}σ 過熱 → 分批停利")
            action = ACTION_REDUCE
        elif level in ("悲觀", "極度悲觀"):
            tags.append(f"σ {sigma_rank:+.2f}σ 過熱+風險升 → 出場")
            action = ACTION_EXIT

    # 配息吃本金（alert == "red"）→ 動作往保守方向 bump 一級
    if div_alert == "red":
        tags.append("吃本金（配息>含息）")
        if action == ACTION_ADD:
            action = ACTION_HOLD
        elif action == ACTION_HOLD and not is_core:
            action = ACTION_REDUCE
        elif action == ACTION_REDUCE and not is_core:
            action = ACTION_EXIT

    return action, tags


def _build_reason(level: str, is_core: bool, tags: list[str]) -> str:
    """組白話原因（verdict 主軸 + 個股 tag）"""
    role = "核心" if is_core else "衛星"
    head = f"{role}・{level}"
    if tags:
        return head + " | " + " / ".join(tags)
    return head


def verdict_to_actions(
    verdict_level: str,
    verdict_score: float,
    funds: Iterable[dict],
) -> list[dict]:
    """逐檔產生決策建議。

    Args:
        verdict_level: 5 級 ("極度樂觀"/"樂觀"/"中性"/"悲觀"/"極度悲觀")
        verdict_score: 總經 composite score（float，僅供 reason 顯示用，不影響邏輯）
        funds: 逐檔 fund dict iterable，預期欄位：
            code (str), name (str, optional), is_core (bool, default False),
            invest_twd (float, optional), sigma_info (dict|None), dividend_info (dict|None)

    Returns:
        list[{code, name, action, action_code, color, reason, target_pct, is_core}]
        順序對齊輸入；空 funds → 空 list；未知 verdict_level → 全部 HOLD 並標 reason。

    邊界：
        - sigma_info.error 存在 / sigma_rank 非數值 → 略過 σ 覆寫
        - dividend_info 無 alert_level → 略過 cov 覆寫
        - is_core 缺失 → 視為衛星 (False)，較保守
    """
    out: list[dict] = []
    if not funds:
        return out

    is_known_level = verdict_level in VERDICT_LEVELS

    for f in funds:
        if not isinstance(f, dict):
            continue
        code = str(f.get("code", "") or "")
        name = str(f.get("name", "") or "")
        is_core = bool(f.get("is_core", False))

        sig = f.get("sigma_info") or {}
        sigma_rank: Optional[float] = None
        if isinstance(sig, dict) and "error" not in sig:
            _r = sig.get("sigma_rank")
            if isinstance(_r, (int, float)):
                sigma_rank = float(_r)

        div = f.get("dividend_info") or {}
        div_alert: Optional[str] = None
        if isinstance(div, dict):
            _al = div.get("alert_level")
            if isinstance(_al, str):
                div_alert = _al

        if is_known_level:
            base = _verdict_default_action(verdict_level, is_core)
            action, tags = _action_after_individual_signals(
                base, sigma_rank, div_alert, verdict_level, is_core
            )
        else:
            action = ACTION_HOLD
            tags = [f"未知 verdict level: {verdict_level!r} → 預設持有"]

        out.append({
            "code": code,
            "name": name,
            "action": action,
            "action_code": action,  # 保留別名供未來 i18n
            "color": _ACTION_COLOR[action],
            "reason": _build_reason(verdict_level, is_core, tags),
            "target_pct": _ACTION_TARGET_PCT[action],
            "is_core": is_core,
            "verdict_score": float(verdict_score) if isinstance(verdict_score, (int, float)) else 0.0,
        })

    return out


def summarize_actions(actions: list[dict]) -> dict:
    """聚合 verdict_to_actions 輸出 → 概覽 dict。

    Returns:
        {
            n_total, n_hold, n_add, n_reduce, n_exit,
            core_hold_pct, satellite_avg_target_pct,
            top_risk_funds: list[code]  # action == 全撤/減倉，照原 list 順序
        }
    """
    if not actions:
        return {
            "n_total": 0,
            "n_hold": 0, "n_add": 0, "n_reduce": 0, "n_exit": 0,
            "core_hold_pct": 0.0,
            "satellite_avg_target_pct": 0.0,
            "top_risk_funds": [],
        }

    n_total = len(actions)
    n_hold = sum(1 for a in actions if a["action"] == ACTION_HOLD)
    n_add = sum(1 for a in actions if a["action"] == ACTION_ADD)
    n_reduce = sum(1 for a in actions if a["action"] == ACTION_REDUCE)
    n_exit = sum(1 for a in actions if a["action"] == ACTION_EXIT)

    cores = [a for a in actions if a.get("is_core")]
    sats = [a for a in actions if not a.get("is_core")]
    core_hold = sum(1 for a in cores if a["action"] == ACTION_HOLD)
    core_hold_pct = (core_hold / len(cores) * 100.0) if cores else 0.0
    sat_avg = (sum(a["target_pct"] for a in sats) / len(sats)) if sats else 0.0

    top_risk = [a["code"] for a in actions if a["action"] in (ACTION_EXIT, ACTION_REDUCE)]

    return {
        "n_total": n_total,
        "n_hold": n_hold,
        "n_add": n_add,
        "n_reduce": n_reduce,
        "n_exit": n_exit,
        "core_hold_pct": round(core_hold_pct, 1),
        "satellite_avg_target_pct": round(sat_avg, 1),
        "top_risk_funds": top_risk,
    }


__all__ = [
    "VERDICT_LEVELS",
    "ACTION_HOLD", "ACTION_ADD", "ACTION_REDUCE", "ACTION_EXIT",
    "ACTIONS",
    "verdict_to_actions",
    "summarize_actions",
]
