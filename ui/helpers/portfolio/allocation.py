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
2. ~~**分類一律 `policy_tier` 優先**（使用者在 Google Sheet 明示的級別），
   缺才退 `is_core`（基金名稱關鍵字啟發式）。~~
   → **2026-10-10 更正（客戶裁示：級別三態）**：分類走 `shared/policy_tier.resolve_tier`
   （`policy_tier` → `is_core` 嚴格布林 → **未設定**）。`is_core` 不再由基金名稱猜出來；
   未設定是第三種獨立狀態，**不算核心、也不算衛星**。
   核心／衛星比例的分母 = **已設定級別**的投入本金（核心＋衛星），未設定另列、不進比例；
   一檔已設定且有本金的都沒有 → 比例回 None（不算）。全部已設定時與舊定義逐位元相同。
3. **目標一律 `portfolio_core_pct`**（session，預設見 `ui/helpers/session.py`），
   不得在各處寫死。

⚠️ **第 5 個顯示點的處置**（2026-08-06 稽核點名 → 2026-08-07 user 拍板）：
Tab⑤ 下半頁的 💊 持倉健診會 embed `ui/tab_fund_grp_health._render_health_3tables`，
其中「🧭 核心 / 衛星」走的是**另一把尺** ——
`services/health/asset_class.classify_core_satellite`（MoneyDJ 基金類別 +  3-3-3，
三態含「待定」）。

那不是漏收，是**不同問題**：本模組回答「這筆錢的配置定位」（使用者自己在 Sheet
標的），那一區回答「這檔基金的資產屬性」（系統依類別 + 3-3-3 判的）。user 的裁決是
**不合併、但降級**：那一區保留（看得出手上的東西實際偏股還是偏債），但

1. **不再輸出任何配置行動建議**（原本的「核心不足 / 衛星過重」4 級燈號連同其
   建議核心區間常數已從 `services/health/asset_class.py` 移除）；
2. **分母對齊**：那一區也只計使用者實際填過的投入本金 —— 未填者由 caller 補的
   100 萬「模擬本金」只服務逐檔配息試算，以 weight=0 擋在配置比例外。

→ 全站「配置比例 + 該不該再平衡」只有本模組這一個來源。

📌 **2026-08-31 WP-G 狀態更新（上面整段一字未刪未改 —— 這是狀態變更，不是漏刪；
決策者 user：「各頁不重複渲染相同功能 …… ④ 健診改單行連結」）**：
④ 我的配置頁的 💊 持倉健診 **已不再 embed** `_render_health_3tables`，只留一行指路
→ ② 組合健診。**故本段所稱的「第 5 個顯示點」在 ④ 這一頁已不存在**；
「🧭 核心 / 衛星（另一把尺）」現在只出現在 ② 那一頁。
**2026-08-07 user 裁決的兩點（不輸出配置行動建議、分母對齊）仍然有效、一項未減** ——
它們約束的是那一區本身，跟它畫在哪一頁無關；本次改的只有「在幾頁畫」。
⚠️「④ 已無第二把尺」是單組結論，未經第二組驗證（`CLAUDE.md` §-2 規則 6）。

單位約定（CLAUDE.md §4.1）：`*_twd` 為 TWD 金額、`*_pct` 為 0~100 百分比
（**不是** 0~1 小數）、`n_*` 為檔數。
"""
from __future__ import annotations

from typing import Optional

# 級別詞彙與判定的 SSOT 在 L0（`shared/policy_tier.py`），這裡只轉引用。
from shared.policy_tier import CORE_TIER, SATELLITE_TIER, resolve_tier  # noqa: F401
from services.format_helpers import fmt_twd

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
    """二態問句「這一檔是不是**明確**設定為核心」：`resolve_tier(fund) == "core"`。

    ⚠️ 回 `False` **不代表衛星** —— 未設定也回 `False`。要分辨衛星／未設定，
    一律改用 `shared.policy_tier.resolve_tier`（三態），不得寫
    `not resolve_core_flag(...)` 或 `'核心' if resolve_core_flag(...) else '衛星'`。
    """
    return resolve_tier(fund) == CORE_TIER


def summarize_core_satellite(
    funds: list | None,
    *,
    target_pct: Optional[float] = None,
) -> dict:
    """金額加權的核心 / 衛星配置摘要（級別三態，客戶 2026-10-10 裁示的方案 B）。

    參數
    ----
    funds       : list[dict]，每筆需有 `invest_twd`（TWD 投入本金）；
                  級別走 `resolve_tier`（`policy_tier` → `is_core` 嚴格布林 → 未設定）。
    target_pct  : 核心目標 %（0~100）。呼叫端請一律傳 `get_core_target_pct(...)`。
                  None = 不做偏差判定。

    回傳（缺資料時誠實回 None，不捏造 0；CLAUDE.md §1）
    ----
    total_twd                      : float，Σ **全部**投入本金（負值視為 0；含未設定）
    core_twd / sat_twd             : float，**明確**核心 / **明確**衛星的投入本金
    classified_twd                 : float，已設定級別的投入本金（核心＋衛星）＝比例分母
    unset_twd                      : float，級別未設定的投入本金（不進比例）
    core_pct / sat_pct             : float | None，核心 / 衛星佔 classified_twd 的 %；
                                     classified_twd = 0 → None（不算比例）
    n_funds / n_core / n_sat       : int，檔數（附註用，**不是**配置比例分母）
    n_tier_unset                   : int，級別未設定的檔數
    n_in_ratio                     : int，已設定級別且本金 > 0 的檔數（比例實際涵蓋的檔）
    n_tier_from_sheet              : int，級別由 v1 `policy_tier` 欄明示的檔數（沿用舊鍵）
    n_missing_amount               : int，未填 / 填 0 本金的檔數（金額版看不到它們）
    is_amount_weighted             : bool，False = 全數沒填本金
    target_pct / diff_pct          : float | None，目標與「核心% − 目標%」

    ⚠️ `classified_twd` 必須在迴圈內與 `total_twd` **同序累加**（不得寫成
    `core_twd + sat_twd`）：全部已設定時兩者才會逐位元相等，比例才與舊定義完全一致。
    """
    out: dict = {
        "total_twd": 0.0, "core_twd": 0.0, "sat_twd": 0.0,
        "core_pct": None, "sat_pct": None,
        "n_funds": 0, "n_core": 0, "n_sat": 0,
        "n_tier_from_sheet": 0, "n_missing_amount": 0,
        "is_amount_weighted": False,
        "target_pct": target_pct, "diff_pct": None,
        "classified_twd": 0.0, "unset_twd": 0.0,
        "n_tier_unset": 0, "n_in_ratio": 0,
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
        _tier = resolve_tier(_f)
        out["n_funds"] += 1
        if _amt <= 0:
            out["n_missing_amount"] += 1
        if str(_f.get("policy_tier") or "").strip().lower() in (
                CORE_TIER, SATELLITE_TIER):
            out["n_tier_from_sheet"] += 1
        if _tier == CORE_TIER:
            out["n_core"] += 1
            out["core_twd"] += _amt
        elif _tier == SATELLITE_TIER:
            out["n_sat"] += 1
            out["sat_twd"] += _amt
        else:
            out["n_tier_unset"] += 1
            out["unset_twd"] += _amt
        if _tier is not None:
            out["classified_twd"] += _amt
            if _amt > 0:
                out["n_in_ratio"] += 1
        out["total_twd"] += _amt

    if out["total_twd"] > 0:
        out["is_amount_weighted"] = True
    if out["classified_twd"] > 0:
        out["core_pct"] = out["core_twd"] / out["classified_twd"] * 100.0
        out["sat_pct"] = 100.0 - out["core_pct"]
        if target_pct is not None:
            out["diff_pct"] = out["core_pct"] - float(target_pct)
    return out


def format_core_satellite_caption(summary: dict) -> str:
    """一行說明：分母是什麼、級別設定了幾檔、有幾檔沒填本金（原則 4「多做說明」）。

    依狀態四選一（客戶 2026-10-10 核准的 S1／S2／S3／S3b／S4）；
    ⛔ 不再出現「以基金名稱關鍵字推定」—— 系統已不猜級別。
    """
    if not summary or not summary.get("n_funds"):
        return "尚無持倉可統計核心 / 衛星比例。"
    _n = summary["n_funds"]
    _n_unset = int(summary.get("n_tier_unset", 0) or 0)
    _n_set = _n - _n_unset
    _miss = summary.get("n_missing_amount", 0)
    if not summary.get("is_amount_weighted"):
        # S4
        return (f"⚠️ {_n} 檔皆未填投入本金 → 無法算金額比例"
                f"（級別已設定 {_n_set} 檔、⬜ 未設定 {_n_unset} 檔）。"
                "請在 Sheet 或「編輯初始持倉」填入本金後再看此比例。")
    if summary.get("core_pct") is None:
        if _n_set == 0:
            # S3
            return (f"⬜ {_n} 檔級別皆未設定 → 無法算核心／衛星比例。"
                    "請在 Google Sheet 的級別欄（`tier`／`policy_tier`）填 core 或 satellite。")
        # S3b
        return ("⬜ 目前沒有「已設定級別且已填本金」的基金 → 無法算核心／衛星比例"
                f"（級別已設定 {_n_set} 檔、⬜ 未設定 {_n_unset} 檔；⚠️ {_miss} 檔未填本金）。")
    _tail = (f"；⚠️ {_miss} 檔未填本金，未計入分母" if _miss else "")
    if _n_unset:
        # S1
        _unset_twd = float(summary.get("unset_twd", 0.0) or 0.0)
        _total = float(summary.get("total_twd", 0.0) or 0.0)
        _unset_pct = (_unset_twd / _total * 100.0) if _total > 0 else 0.0
        return ("分母 = 已設定級別的投入本金（**金額**加權，非檔數）；"
                f"級別已設定 {_n_set} 檔、⬜ 未設定 {_n_unset} 檔"
                f"（{fmt_twd(_unset_twd)}，佔全部投入 {_unset_pct:.1f}%）"
                f"不計入核心／衛星比例，設定後比例可能改變{_tail}。")
    # S2
    return (f"分母 = Σ 投入本金（**金額**加權，非檔數）；"
            f"級別已設定 {_n} 檔{_tail}。")
