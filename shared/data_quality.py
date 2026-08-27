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

**NAV 快取序列品質(2026-08-27 新增)**：`cache/nav/{code}.json` 是 Streamlit Cloud
美國 IP 被上游封鎖時的最終 fallback,但讀取端原本零品質閘。判定器
`assess_nav_cache_quality` 見本檔下半部;它同樣**只揭露不改值**,且門檻全部沿用
`shared/signal_thresholds.py` 的既有 SSOT。

⚠️ 本模組**不引入任何新門檻**：是否算「涵蓋不足」沿用呼叫端既有的
`len(s) >= n` 分支條件,不另立比例或天數常數(避免製造新的判定門檻)。
NAV 快取品質那一段同理 —— 密度 / 缺口 / 新鮮度三個門檻都是既有常數,
唯一的新常數 `NAV_CACHE_MIN_POINTS` 也只是把既有 inline `>= 10` 收成 SSOT。
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


# ════════════════════════════════════════════════════════════════════
# NAV 快取序列品質(cache/nav/{code}.json — Streamlit Cloud IP 被封時的最終保障)
# ════════════════════════════════════════════════════════════════════
# 背景(2026-08-27 稽核):`repositories/fund/sources._src_cache_files` 是 `fetch_nav`
# 的最後一道 fallback,但它原本**只檢查檔案存在 + history 非空** —— 不看筆數、不看
# 密度、不看年齡、也不跑 `validate_fund_nav`。而同一個 `fetch_nav` 的 live 分支要
# `len >= 10` **且** schema 驗證,長歷史路徑要 `len >= 50`。**唯獨這條照單全收。**
#
# 實測 `cache/nav/TLZF9.json`(該目錄唯一的檔):10 點橫跨 2011-11-18 → 2026-04-23
# (5,270 天 / 14.43 年),最大空窗 2,029 天,密度 0.69 點/年,updated_at 36 天前且
# `source="cache_only"`(該次一筆新資料都沒抓到)。這種序列拿去算 Sharpe / σ / 最大
# 回撤 —— 年化一律 ×√252、假設「每點 = 1 交易日」—— 出來的是**看起來像數字的雜訊**。
#
# 本模組只**判定並揭露**,不決定擋不擋(那是呼叫端的事,見 `usable` 與
# `supports_annualized` 兩個旗標的分工)。§1:不修數字、不刪資料,只讓它誠實。
#
# ⚠️ 門檻全部沿用**既有 SSOT**,本節不發明新的判定值:
#   - 密度 / 缺口 → `NAV_HIST_COVERAGE_MIN` / `NAV_HIST_MAX_GAP_DAYS`
#     (`shared/signal_thresholds.py`;全站年化指標同一把尺,`fund_service.
#      assess_series_coverage` 已在用)
#   - 新鮮度     → `MJ_FRESH_DAYS_YELLOW`(同上;全站 NAV 新鮮度黃線,
#     基金 NAV T+1~T+3 公布,7 天放寬以覆蓋連假)
#   唯一新增的是下面的 `NAV_CACHE_MIN_POINTS`,而它也**不是發明的值**,見其註解。

# 疑義原因代碼(機器可讀;顯示文字走 `reason`)
QUALITY_NAV_TOO_FEW: str = "nav_too_few_points"
QUALITY_NAV_SPARSE: str = "nav_sparse_series"
QUALITY_NAV_STALE: str = "nav_stale_series"

# 快取序列「可用」的最低筆數。
# **不是新門檻,是把既有的 inline 值收成 SSOT(§3.3)**:
#   - `repositories/fund/nav_metrics.fetch_nav` 的 live 分支:`if len(s) >= 10`
#   - `repositories/fund/fund_orchestration` 最終備援:`if len(_fallback_s) >= 10`
#   - 更下游 `fx_and_main.fetch_fund_by_key` 甚至要 `len(s) >= 20` 才收
# 也就是說 < 10 點的序列**下游本來就會丟掉**,快取路徑放它過去只是製造雜訊與
# 一段沒人驗過的 schema 破口。把快取路徑對齊到 live 路徑同一把尺 = **補回既有標準**,
# 不是新增限制,可用性零損失。
NAV_CACHE_MIN_POINTS: int = 10


def assess_nav_cache_quality(
    s,
    cache_updated_at: "str | None" = None,
    now=None,
) -> dict:
    """評估 NAV 快取序列夠不夠格被下游當「真的歷史」用。

    Args:
        s: NAV `pd.Series`(DatetimeIndex → float)。本函式**不修改**它。
        cache_updated_at: 快取檔自帶的 `updated_at`(ISO 字串);None = 未知。
            ⚠️ 這是 **GH Actions 寫檔時間**,與「最新資料點多舊」是兩個維度,
            兩個都回報:前者看 cron 有沒有死,後者看數字有沒有過期。
        now: 注入用的「現在」(`datetime`,tz-aware);None = 取當下 UTC。
            測試要能固定時間,故開放注入(§5 可重現性)。

    Returns:
        dict:
        - `code`             — 最嚴重的一項疑義代碼(見上方常數);無疑義 = `QUALITY_OK`
        - `usable`           — **擋不擋的唯一依據**。False 只在筆數不足時發生
                               (下游本來就會丟掉,見 `NAV_CACHE_MIN_POINTS` 註解)。
        - `supports_annualized` — **標註疑義的核心旗標**。False = 這條序列
                               **不足以算 Sharpe / σ / 最大回撤**(年化 ×√252 會失真)。
                               ⚠️ 它可以在 `usable=True` 時為 False —— 那正是本設計的重點:
                               **序列照放行,但下游必須知道年化指標算不得**。
        - `n_points` / `span_days` / `coverage` / `max_gap_days` / `sparse`
        - `newest_age_days`  — 最新資料點距今幾天(None = 無法判定)
        - `file_age_days`    — 快取檔 updated_at 距今幾天(None = 未提供 / 解析失敗)
        - `stale`            — 最新資料點是否超過 `MJ_FRESH_DAYS_YELLOW`
        - `reason`           — 給人看的誠實說明(無疑義時為 None)
        - `honest_label`     — UI 可直接掛的短標籤(無疑義時為空字串)

    §1:任何一項不合格都**不回 None、不改值** —— 只揭露。
    """
    import datetime as _dt

    from shared.signal_thresholds import (
        MJ_FRESH_DAYS_YELLOW,
        NAV_HIST_COVERAGE_MIN,
        NAV_HIST_MAX_GAP_DAYS,
        TRADING_DAYS_PER_YEAR,
    )

    n = 0 if s is None else int(len(s))
    out = {
        "code": QUALITY_OK,
        "usable": n >= NAV_CACHE_MIN_POINTS,
        "supports_annualized": True,
        "n_points": n,
        "span_days": None,
        "coverage": 0.0,
        "max_gap_days": None,
        "sparse": True,
        "newest_age_days": None,
        "file_age_days": None,
        "stale": False,
        "reason": None,
        "honest_label": "",
    }

    if now is None:
        now = _dt.datetime.now(_dt.timezone.utc)

    # ── 快取檔本身的年齡(cron 健康度;與資料新舊是兩回事)────────────────
    if cache_updated_at:
        try:
            _u = _dt.datetime.fromisoformat(str(cache_updated_at).replace("Z", "+00:00"))
            if _u.tzinfo is None:
                _u = _u.replace(tzinfo=_dt.timezone.utc)
            out["file_age_days"] = int((now - _u).days)
        except (ValueError, TypeError):
            pass  # 解析不出來就留 None(§1:不猜)

    # ── 覆蓋率 / 最大缺口 ────────────────────────────────────────────────
    # ⚠️ 算式必須與 L2 `services/fund_service.assess_series_coverage` **逐欄一致**
    # (那是全站年化指標的同一把尺)。L1 不得 import L2(§8.2,EX-L1ORCH-1 退役前例),
    # 故實作放在本 L0 模組;兩份的一致性由
    # `tests/test_nav_cache_quality_gate.py::test_coverage_matches_l2_assess_series_coverage`
    # 漂移鎖住 —— 任一邊改了另一邊沒跟上就 CI 紅燈。
    if n >= 2:
        _span = int((s.index[-1] - s.index[0]).days)
        out["span_days"] = _span
        if _span > 0:
            _expected = _span * TRADING_DAYS_PER_YEAR / 365.0
            out["coverage"] = (
                round(float(min(1.0, n / _expected)), 3) if _expected > 0 else 0.0
            )
            _gaps = s.index.to_series().diff().dt.days.dropna()
            out["max_gap_days"] = int(_gaps.max()) if len(_gaps) else None
            out["sparse"] = bool(
                out["coverage"] < NAV_HIST_COVERAGE_MIN
                or (out["max_gap_days"] or 0) > NAV_HIST_MAX_GAP_DAYS
            )
        # ── 最新資料點年齡 ──
        try:
            _newest = s.index[-1].to_pydatetime()
            if _newest.tzinfo is None:
                _newest = _newest.replace(tzinfo=_dt.timezone.utc)
            out["newest_age_days"] = int((now - _newest).days)
            out["stale"] = out["newest_age_days"] > MJ_FRESH_DAYS_YELLOW
        except (AttributeError, ValueError, TypeError):
            pass

    # ── 判定 ──────────────────────────────────────────────────────────────
    # 年化指標(Sharpe / σ / 最大回撤)要求「每點 ≈ 1 交易日」;筆數不足或序列稀疏
    # 兩者任一成立就不成立 → 這是本函式最重要的一個輸出。
    out["supports_annualized"] = bool(out["usable"] and not out["sparse"])

    if not out["usable"]:
        out["code"] = QUALITY_NAV_TOO_FEW
        out["reason"] = (
            f"快取序列只有 {n} 筆(< {NAV_CACHE_MIN_POINTS} 筆下限)"
            f"→ 與 live 路徑同一把尺,下游本來就不會採用"
        )
        out["honest_label"] = "⚠️快取筆數不足"
        return out

    _bits = []
    if out["sparse"]:
        out["code"] = QUALITY_NAV_SPARSE
        _span_txt = "" if out["span_days"] is None else f"橫跨 {_fmt_years(out['span_days'])}"
        _bits.append(
            f"序列稀疏({n} 點{('、' + _span_txt) if _span_txt else ''}"
            f",覆蓋率 {out['coverage']} < {NAV_HIST_COVERAGE_MIN}"
            f",最大空窗 {out['max_gap_days']} 天 > {NAV_HIST_MAX_GAP_DAYS} 天)"
            f"→ **不足以算 Sharpe / σ / 最大回撤**(年化 ×√{TRADING_DAYS_PER_YEAR} "
            f"假設每點 = 1 交易日)"
        )
    if out["stale"]:
        if out["code"] == QUALITY_OK:
            out["code"] = QUALITY_NAV_STALE
        _bits.append(
            f"最新資料點已 {out['newest_age_days']} 天前"
            f"(> {MJ_FRESH_DAYS_YELLOW} 天新鮮度黃線)"
            + (
                f";快取檔本身 {out['file_age_days']} 天未更新"
                if out["file_age_days"] is not None
                else ""
            )
        )
    if _bits:
        out["reason"] = "離線快取:" + ";".join(_bits)
        out["honest_label"] = (
            "⚠️稀疏快取" if out["sparse"] else "⚠️過期快取"
        )
    return out
