"""shared/data_quality.py — 「有疑義的歷史資料」標註 SSOT(L0,無 I/O、純函式)。

§1 Fail Loud, Never Fake：歷史序列涵蓋不足時,**不修數字、不刪資料**,
改以「誠實標註」揭露 ——「這段歷史不可信、原因是什麼」一律由本模組產生,
**UI 禁止自行編字串**(§2.1 SSOT;避免同一件事在多處各寫一版而漂移)。

本模組目前處理的疑義型態
------------------------
**視窗涵蓋不足(window coverage shortfall)**：呼叫端要一個「近 N 交易日」的
統計量(如「年高 / 年低」),但序列根本沒有 N 筆 —— 既有實作一律**靜默退回
全序列**再冠上「年」的標籤。序列若橫跨十餘年(停售基金 / 新發行基金 /
`cache/nav/{code}.json` 這類稀疏快取),畫面上那條「年高」線可能是十幾年前
的高點,屬 §1 明文禁止的「讓流程看起來成功」——**值沒有錯,錯的是標籤**。

處置：值**原樣保留**(不動任何判定門檻與買賣點),另外回報
`covers_window` / `actual_span_days` / `reason`,由 UI 改用誠實標籤。

⚠️ 本模組**不引入任何新門檻**：是否算「涵蓋不足」沿用呼叫端既有的
`len(s) >= n` 分支條件,不另立比例或天數常數(避免製造新的判定門檻)。
"""
from __future__ import annotations

# 疑義原因代碼(機器可讀;UI 顯示文字走 `reason` / `honest_label`)
QUALITY_OK: str = "ok"
QUALITY_WINDOW_SHORTFALL: str = "window_shortfall"


def _fmt_years(days: float) -> str:
    """把日曆天數轉成人看的年數標籤(1 位小數;不足 1 年改用天)。"""
    if days < 365:
        return f"{round(days)}天"
    return f"{days / 365.0:.1f}年"


def assess_window_coverage(
    n_points: int,
    requested_days: int,
    span_days: float | None = None,
    window_label: str = "",
) -> dict:
    """評估「近 requested_days 交易日」這個視窗的涵蓋情形。

    Args:
        n_points: 序列實際筆數。
        requested_days: 呼叫端**宣稱**的視窗長度(交易日)。
        span_days: 實際被納入計算那段資料的**日曆**跨度(天);None = 未知。
        window_label: 呼叫端原本要掛的標籤(例 "年高")。

    Returns:
        dict — `code` / `covers_window` / `requested_days` / `n_points` /
        `actual_span_days` / `reason`(涵蓋足夠時為 None)/ `honest_label`
        (涵蓋足夠時等於 `window_label`,不足時改寫為據實的跨度標籤)。

    §1：涵蓋不足**不回 None、不改值** —— 只揭露,讓呼叫端決定怎麼標。
    """
    covers = int(n_points) >= int(requested_days)
    out = {
        "code": QUALITY_OK if covers else QUALITY_WINDOW_SHORTFALL,
        "covers_window": covers,
        "requested_days": int(requested_days),
        "n_points": int(n_points),
        "actual_span_days": (None if span_days is None else float(span_days)),
        "reason": None,
        "honest_label": window_label,
    }
    if covers:
        return out
    _span_txt = "" if span_days is None else f",實際涵蓋 {_fmt_years(span_days)}"
    out["reason"] = (
        f"視窗涵蓋不足（{int(n_points)}/{int(requested_days)} 交易日{_span_txt}）"
        f"→ 已退回全序列計算,此值**不是**「近 {int(requested_days)} 交易日」的值"
    )
    # `honest_label` 是**視窗描述詞**,呼叫端會在後面接「高 / 低」等量詞,
    # 故涵蓋不足時整個換掉(而非在原標籤後綴),避免組出「年⚠️…年高」這種病句。
    out["honest_label"] = (
        "⚠️全期" if span_days is None
        else f"⚠️全期{_fmt_years(span_days)}"
    )
    return out
