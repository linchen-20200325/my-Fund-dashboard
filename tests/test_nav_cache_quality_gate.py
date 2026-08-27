"""cache/nav 讀取端品質閘 — 2026-08-27。

## 修的是什麼

`repositories/fund/sources._src_cache_files` 是 `fetch_nav` 的最後一道 fallback
(Streamlit Cloud 美國 IP 被上游封鎖時,唯一還吐得出 NAV 的來源),但它原本
**只檢查檔案存在 + `history` 非空**就回傳 —— 不看筆數、不看密度、不看年齡、
也不跑 `validate_fund_nav`。

而同一條 chain 的其他路徑都有閘:
  - live(`fetch_nav` 迴圈內)      → `len >= 10` **且** `validate_fund_nav()`
  - 長歷史(`nav_metrics` 多處)    → `len >= 50` / `>= 100`
  - 下游(`fx_and_main.fetch_fund_by_key`)→ `len >= 20` 才收

實測 `cache/nav/TLZF9.json`(該目錄唯一的檔):**10 點橫跨 14.43 年**、最大空窗
**2,029 天**、密度 0.69 點/年、`source="cache_only"`。這種序列被下游拿去算
Sharpe / σ / 最大回撤(年化一律 ×√252、假設「每點 = 1 交易日」)= 假精確。

## 閘的形狀(刻意不對稱)

- **Tier A 擋**:筆數 < `NAV_CACHE_MIN_POINTS` 或 schema 違反 → 回空。
  這**不是新標準**,是補回 live 分支同一把尺;且下游本來就會丟掉 <10 點的序列,
  可用性零損失。
- **Tier B 不擋,標註疑義**:密度 / 空窗 / 新鮮度 → 序列照回,掛
  `attrs["supports_annualized"]=False`。⚠️ 刻意不擋 —— 擋掉會把「數字可疑」
  變成「完全沒資料」,對這條最後的 fallback 是更糟的失效模式(§1 是讓它誠實,
  不是讓它消失)。
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd
import pytest

from repositories.fund.sources import _src_cache_files
from shared.data_quality import (
    NAV_CACHE_MIN_POINTS,
    QUALITY_NAV_SPARSE,
    QUALITY_NAV_TOO_FEW,
    QUALITY_OK,
    assess_nav_cache_quality,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CACHE_DIR = _REPO_ROOT / "cache" / "nav"
_NOW = dt.datetime(2026, 8, 27, tzinfo=dt.timezone.utc)


def _mk(dates: list[str], navs: list[float] | None = None) -> pd.Series:
    navs = navs or [10.0 + i * 0.01 for i in range(len(dates))]
    s = pd.Series(navs, index=pd.to_datetime(dates), dtype=float).sort_index()
    s.attrs["source"] = "GitHubActions:cache/nav/TEST.json"
    s.attrs["fetched_at"] = _NOW.isoformat()
    return s


def _dense(n: int, end: str = "2026-08-26") -> pd.Series:
    """n 個連續日曆日(密度足夠、不過期)。"""
    end_d = dt.date.fromisoformat(end)
    return _mk([str(end_d - dt.timedelta(days=n - 1 - i)) for i in range(n)])


@pytest.fixture
def _seed():
    """在 repo 根 cache/nav/ 寫測試檔,測完刪(不污染 production 的 TLZF9.json)。"""
    written: list[Path] = []

    def _w(code: str, history: list[dict], updated_at: str) -> str:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        p = _CACHE_DIR / f"{code}.json"
        p.write_text(
            json.dumps({"code": code, "updated_at": updated_at,
                        "count": len(history), "history": history}) + "\n",
            encoding="utf-8",
        )
        written.append(p)
        return code

    yield _w
    for p in written:
        p.unlink(missing_ok=True)


# ════════════════════════════════════════════════════════════════
# L0 判定器本身
# ════════════════════════════════════════════════════════════════

def test_dense_recent_series_is_clean():
    """密集 + 新鮮 → 無疑義,年化指標可用。"""
    q = assess_nav_cache_quality(_dense(60), cache_updated_at=_NOW.isoformat(), now=_NOW)
    assert q["code"] == QUALITY_OK
    assert q["usable"] is True
    assert q["supports_annualized"] is True
    assert q["sparse"] is False and q["stale"] is False
    assert q["reason"] is None


def test_too_few_points_is_blocked():
    """筆數 < 下限 → usable=False(Tier A,唯一會擋的情形)。"""
    q = assess_nav_cache_quality(_dense(NAV_CACHE_MIN_POINTS - 1), now=_NOW)
    assert q["usable"] is False
    assert q["code"] == QUALITY_NAV_TOO_FEW
    assert q["supports_annualized"] is False


def test_min_points_boundary_is_inclusive():
    """邊界:剛好等於下限 → 放行(>=,不是 >)。"""
    assert assess_nav_cache_quality(_dense(NAV_CACHE_MIN_POINTS), now=_NOW)["usable"] is True


def test_tlzf9_shaped_series_passes_but_is_flagged():
    """本次事故的真實形狀:10 點 / 14 年 / 空窗 2029 天。

    **放行**(usable=True — 這是最後的 fallback,不能關掉),
    但 **supports_annualized=False**(下游不得拿去算 Sharpe/σ/回撤)。
    """
    q = assess_nav_cache_quality(
        _mk(["2011-11-18", "2012-10-15", "2012-10-16", "2013-03-01", "2013-05-02",
             "2015-03-18", "2020-02-03", "2020-10-01", "2026-04-22", "2026-04-23"]),
        cache_updated_at="2026-07-22T04:31:29.432936+00:00", now=_NOW,
    )
    assert q["usable"] is True, "最後的 fallback 不可被關掉"
    assert q["supports_annualized"] is False, "稀疏序列不得支撐年化指標"
    assert q["code"] == QUALITY_NAV_SPARSE
    assert q["sparse"] is True and q["stale"] is True
    assert q["n_points"] == 10 and q["span_days"] == 5270
    assert q["max_gap_days"] == 2029
    # 以注入的 _NOW(2026-08-27T00:00Z)為基準 → 35;用真實當下跑會是 36。
    # 差 1 天純粹是參考時點不同,故本測試注入固定 now(§5 可重現性)。
    assert q["newest_age_days"] == 126 and q["file_age_days"] == 35
    assert "Sharpe" in q["reason"]


def test_empty_and_none_are_not_usable():
    for s in (None, pd.Series(dtype=float)):
        q = assess_nav_cache_quality(s, now=_NOW)
        assert q["usable"] is False and q["supports_annualized"] is False


def test_stale_but_dense_is_flagged_not_blocked():
    """夠密但過期 → 仍放行;stale=True。"""
    q = assess_nav_cache_quality(_dense(60, end="2026-01-31"), now=_NOW)
    assert q["usable"] is True
    assert q["stale"] is True
    assert q["reason"] is not None


def test_thresholds_come_from_ssot_not_inline():
    """§3.3:三個判定門檻必須是既有 SSOT 常數,不是本模組發明的數字。"""
    from shared import signal_thresholds as st
    assert st.NAV_HIST_COVERAGE_MIN == 0.6
    assert st.NAV_HIST_MAX_GAP_DAYS == 14
    assert st.MJ_FRESH_DAYS_YELLOW == 7
    # 下限本身也不是憑空來的:它等於 live 分支的 inline `>= 10`
    assert NAV_CACHE_MIN_POINTS == 10


def test_coverage_matches_l2_assess_series_coverage():
    """漂移鎖:L0 的覆蓋率算式必須與 L2 `fund_service.assess_series_coverage` 逐欄相同。

    L1 不得 import L2(§8.2,EX-L1ORCH-1 退役前例),所以算式在 L0 又有一份。
    兩份一旦漂移,全站「年化指標可不可信」就會有兩個答案 → 本測試把它們釘死。
    """
    from services.fund_service import assess_series_coverage
    cases = [
        _dense(60),
        _dense(300),
        _mk(["2011-11-18", "2012-10-15", "2012-10-16", "2013-03-01", "2013-05-02",
             "2015-03-18", "2020-02-03", "2020-10-01", "2026-04-22", "2026-04-23"]),
        _mk(["2026-01-01", "2026-06-01"]),
    ]
    for s in cases:
        l2 = assess_series_coverage(s)
        l0 = assess_nav_cache_quality(s, now=_NOW)
        assert l0["coverage"] == l2["coverage"], f"coverage 漂移 @ {len(s)} 點"
        assert l0["max_gap_days"] == l2["max_gap_days"], f"max_gap 漂移 @ {len(s)} 點"
        assert l0["sparse"] == l2["sparse"], f"sparse 漂移 @ {len(s)} 點"


# ════════════════════════════════════════════════════════════════
# 接線:_src_cache_files 真的有用到判定器(防死接線)
# ════════════════════════════════════════════════════════════════

def test_wired_sparse_cache_returns_series_with_flags(_seed):
    """稀疏快取 → 序列照回(fallback 沒被關掉)+ attrs 帶疑義旗標。"""
    code = _seed("ZZSPARSE1", [
        {"date": d, "nav": 10.0 + i}
        for i, d in enumerate(
            ["2011-11-18", "2012-10-15", "2013-03-01", "2013-05-02", "2015-03-18",
             "2020-02-03", "2020-10-01", "2022-01-05", "2026-04-22", "2026-04-23"])
    ], "2026-07-22T04:31:29+00:00")

    s = _src_cache_files(code)
    assert not s.empty and len(s) == 10, "最後的 fallback 不可被閘關掉"
    assert s.attrs["supports_annualized"] is False
    assert s.attrs["nav_quality_code"] == QUALITY_NAV_SPARSE
    assert s.attrs["nav_quality"]["max_gap_days"] > 14


def test_wired_too_few_points_returns_empty(_seed):
    """筆數不足 → 回空(Tier A)。"""
    code = _seed("ZZFEW1", [
        {"date": f"2026-08-{d:02d}", "nav": 10.0} for d in range(1, 5)
    ], "2026-08-26T00:00:00+00:00")
    assert _src_cache_files(code).empty


def test_wired_schema_violation_returns_empty(_seed):
    """NAV <= 0(停售/清算應為 NaN 而非 0)→ schema 擋掉,不再靜默流進 chain。"""
    code = _seed("ZZBAD1", [
        {"date": f"2026-08-{d:02d}", "nav": (0.0 if d == 3 else 10.0)}
        for d in range(1, 15)
    ], "2026-08-26T00:00:00+00:00")
    assert _src_cache_files(code).empty, "NAV=0 的快取必須被 validate_fund_nav 擋下"


def test_wired_healthy_cache_is_untouched(_seed):
    """健康快取 → 完全不受影響(閘不是拿來擋好資料的)。"""
    end = dt.date(2026, 8, 26)
    code = _seed("ZZGOOD1", [
        {"date": str(end - dt.timedelta(days=59 - i)), "nav": 10.0 + i * 0.01}
        for i in range(60)
    ], "2026-08-26T00:00:00+00:00")
    s = _src_cache_files(code)
    assert len(s) == 60
    assert s.attrs["supports_annualized"] is True
    assert s.attrs["nav_quality_code"] == QUALITY_OK
