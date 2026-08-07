"""ui/helpers/portfolio/allocation.py — 核心 / 衛星配置的唯一真相（純函式）。

**為什麼要這一支**：同一頁原本有 4 處各算各的核心/衛星，3 種定義、2 種目標值 ——

| 位置 | 分母 | 分類依據 | 目標 |
|---|---|---|---|
| 組合健康儀表 | 檔數 | `mk_df["MK_Class"]` | 寫死 80 |
| ① 配置總覽 KPI 卡 | 金額 | `is_core` | 無 |
| Hero 卡 + 甜甜圈 | 金額 | `is_core` | `portfolio_core_pct`（預設 75）|
| 保單分組 | 金額 | `policy_tier` → `is_core` | `portfolio_core_pct` |

3 檔核心佔 5 檔 = 60%，但核心若持有 90% 的錢 → 同一頁同時出現「核心 60%」與
「核心 90%」，目標值又 80 vs 75 打架，使用者無從判斷該不該再平衡。

**本模組定的規則**：
1. **分母一律金額**（Σ 投入本金 TWD）。檔數比例只能當附註，不得當「配置比例」。
2. **分類一律 `policy_tier` 優先**（使用者在 Google Sheet 明示的級別），
   缺才退 `is_core`（基金名稱關鍵字啟發式）。
3. **目標一律 `portfolio_core_pct`**（session，預設見 `ui/helpers/session.py`），
   不得在各處寫死。

⚠️ **第 5 個顯示點的處置**（2026-08-06 稽核點名 → 2026-08-07 user 拍板）：
Tab⑤ 下半頁的 💊 持倉健診會 embed `ui/tab_fund_grp_health._render_health_3tables`，
其中「🧭 核心 / 衛星」走的是**另一把尺** ——
`services/health/asset_class.classify_core_satellite`（MoneyDJ 基金類別 + MK 3-3-3，
三態含「待定」）。

那不是漏收，是**不同問題**：本模組回答「這筆錢的配置定位」（使用者自己在 Sheet
標的），那一區回答「這檔基金的資產屬性」（系統依類別 + 3-3-3 判的）。user 的裁決是
**不合併、但降級**：那一區保留（看得出手上的東西實際偏股還是偏債），但

1. **不再輸出任何配置行動建議**（原本的「核心不足 / 衛星過重」4 級燈號連同其
   建議核心區間常數已從 `services/health/asset_class.py` 移除）；
2. **分母對齊**：那一區也只計使用者實際填過的投入本金 —— 未填者由 caller 補的
   100 萬「模擬本金」只服務逐檔配息試算，以 weight=0 擋在配置比例外。

→ 全站「配置比例 + 該不該再平衡」只有本模組這一個來源。

單位約定（CLAUDE.md §4.1）：`*_twd` 為 TWD 金額、`*_pct` 為 0~100 百分比
（**不是** 0~1 小數）、`n_*` 為檔數。
"""
from __future__ import annotations

from typing import Optional

CORE_TIER = "core"
SATELLITE_TIER = "satellite"

# 核心目標 % 的 session key 與其預設值 —— 預設值 SSOT 在
# `ui/helpers/session.INITIAL_SESSION_STATE`，這裡只做轉引用，禁止另寫常數。
CORE_TARGET_SESSION_KEY = "portfolio_core_pct"


def get_core_target_pct(session_state) -> float:
    """取核心目標 %（0~100）。session 沒設就退 `INITIAL_SESSION_STATE` 的預設。

    全站唯一取法；呼叫端不得再寫 `session_state.get(key, <數字>)`（數字會漂移）。
    """
    from ui.helpers.session import INITIAL_SESSION_STATE
    _default = INITIAL_SESSION_STATE[CORE_TARGET_SESSION_KEY]
    try:
        return float(session_state.get(CORE_TARGET_SESSION_KEY, _default))
    except (TypeError, ValueError):
        return float(_default)


def resolve_core_flag(fund: dict | None) -> bool:
    """核心 / 衛星判定：Sheet `policy_tier` 優先，缺則退既有 `is_core` 啟發式。

    與 Tab3 保單分組視圖原本的 `_is_core_in_policy` 同語意（該處已收斂為呼叫本函式），
    差別只在這裡是全頁共用、不再各處各寫一份。
    """
    _f = fund or {}
    _tier = str(_f.get("policy_tier") or "").strip().lower()
    if _tier == CORE_TIER:
        return True
    if _tier == SATELLITE_TIER:
        return False
    return bool(_f.get("is_core"))


def summarize_core_satellite(
    funds: list | None,
    *,
    target_pct: Optional[float] = None,
) -> dict:
    """金額加權的核心 / 衛星配置摘要。

    參數
    ----
    funds       : list[dict]，每筆需有 `invest_twd`（TWD 投入本金）；
                  級別走 `resolve_core_flag`（`policy_tier` → `is_core`）。
    target_pct  : 核心目標 %（0~100）。呼叫端請一律傳
                  `st.session_state.get("portfolio_core_pct", <session 預設>)`，
                  不要在呼叫點另寫常數。None = 不做偏差判定。

    回傳（缺資料時誠實回 None，不捏造 0；CLAUDE.md §1）
    ----
    total_twd / core_twd / sat_twd : float，Σ 投入本金（負值視為 0）
    core_pct / sat_pct             : float | None，金額佔比 %；total_twd = 0 → None
    n_funds / n_core / n_sat       : int，檔數（附註用，**不是**配置比例分母）
    n_tier_from_sheet              : int，級別由 Sheet `policy_tier` 明示的檔數
    n_missing_amount               : int，未填 / 填 0 本金的檔數（金額版看不到它們）
    is_amount_weighted             : bool，False = 全數沒填本金 → `core_pct` 不可信
    target_pct / diff_pct          : float | None，目標與「核心% − 目標%」
    """
    out: dict = {
        "total_twd": 0.0, "core_twd": 0.0, "sat_twd": 0.0,
        "core_pct": None, "sat_pct": None,
        "n_funds": 0, "n_core": 0, "n_sat": 0,
        "n_tier_from_sheet": 0, "n_missing_amount": 0,
        "is_amount_weighted": False,
        "target_pct": target_pct, "diff_pct": None,
    }
    if not funds:
        return out

    for _f in funds:
        _f = _f or {}
        try:
            _amt = float(_f.get("invest_twd", 0) or 0)
        except (TypeError, ValueError):
            _amt = 0.0
        _amt = max(_amt, 0.0)
        _is_core = resolve_core_flag(_f)
        out["n_funds"] += 1
        if _amt <= 0:
            out["n_missing_amount"] += 1
        if str(_f.get("policy_tier") or "").strip().lower() in (
                CORE_TIER, SATELLITE_TIER):
            out["n_tier_from_sheet"] += 1
        if _is_core:
            out["n_core"] += 1
            out["core_twd"] += _amt
        else:
            out["n_sat"] += 1
            out["sat_twd"] += _amt
        out["total_twd"] += _amt

    if out["total_twd"] > 0:
        out["is_amount_weighted"] = True
        out["core_pct"] = out["core_twd"] / out["total_twd"] * 100.0
        out["sat_pct"] = 100.0 - out["core_pct"]
        if target_pct is not None:
            out["diff_pct"] = out["core_pct"] - float(target_pct)
    return out


def format_core_satellite_caption(summary: dict) -> str:
    """一行說明：分母是什麼、級別哪來的、有幾檔沒填本金（原則 4「多做說明」）。"""
    if not summary or not summary.get("n_funds"):
        return "尚無持倉可統計核心 / 衛星比例。"
    _n = summary["n_funds"]
    _from_sheet = summary.get("n_tier_from_sheet", 0)
    _src = (f"{_from_sheet}/{_n} 檔級別來自 Google Sheet `policy_tier`，"
            f"其餘 {_n - _from_sheet} 檔以基金名稱關鍵字推定")
    if not summary.get("is_amount_weighted"):
        return (f"⚠️ {_n} 檔皆未填投入本金 → 無法算金額比例（{_src}）。"
                "請在 Sheet 或「編輯初始持倉」填入本金後再看此比例。")
    _miss = summary.get("n_missing_amount", 0)
    _tail = (f"；⚠️ {_miss} 檔未填本金，未計入分母" if _miss else "")
    return (f"分母 = Σ 投入本金（**金額**加權，非檔數）；"
            f"{_src}{_tail}。")
