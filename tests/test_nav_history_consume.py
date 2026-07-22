"""tests/test_nav_history_consume.py — v19.360 Increment B+②:累積序列接回 metrics。

守:
- nav_history_gs.load_series:points → 昇冪去重 pd.Series + provenance attrs
- fund_service.assess_series_coverage:密集不稀疏 / 低覆蓋稀疏 / 大缺口稀疏(門檻 SSOT)
- fund_service._merge_nav_history_series:union keep-last(live 優先)/ 空 hist 不動 /
  讀失敗 fail-soft 退 live-only
- finalize_fund_metrics 端到端:短 live 被累積歷史救回過 len<10 gate;
  稀疏 → 自算年化值(sharpe self_calc / sortino / calmar / std nav)砍成 None + reason(§1);
  live-only(無累積)→ 行為與現在完全一致(無 nav_coverage key)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

# prime 匯入順序:services.fund_service ↔ fund_fetcher 為既有 latent 互相 import
#(fund_fetcher:285 `from services.fund_service import _RF_ANNUAL`),把 fund_service
# 當「第一個」import 會撞循環。先走自然入口 fund_fetcher(同 test_fund_load_enriched)。
import fund_fetcher  # noqa: F401,E402

from services import nav_history_gs as GS  # noqa: E402
from services.fund_service import (  # noqa: E402
    _merge_nav_history_series,
    assess_series_coverage,
    finalize_fund_metrics,
)


# ── load_series ───────────────────────────────────────────────
class _WS:
    def __init__(self, rows):
        self.rows = rows

    def get_all_values(self):
        return [[str(c) for c in r] for r in self.rows]


class _Sheet:
    def __init__(self, rows):
        self._ws = _WS(rows)

    def worksheet(self, name):
        return self._ws


def test_load_series_sorted_dedup_with_provenance():
    sh = _Sheet([list(GS._NAV_HEADERS),
                 ["TLZF9", "2026-07-22", "12.5", "安聯", "app", "t"],
                 ["TLZF9", "2026-07-20", "12.1", "安聯", "app", "t"],
                 ["TLZF9", "2026-07-22", "12.6", "安聯", "app", "t2"],  # 同日 → keep-last
                 ["ANZ89", "2026-07-21", "9.9", "安聯", "app", "t"]])   # 他檔 → 濾掉
    s = GS.load_series("TLZF9", _sheet=sh)
    assert list(s.index) == sorted(s.index)          # 昇冪
    assert len(s) == 2                                # 去重 + code 過濾
    assert s.iloc[-1] == 12.6                         # 同日 keep-last
    assert s.attrs["source"] == "GoogleSheet:nav_history:TLZF9"
    assert "fetched_at" in s.attrs                    # F-PROV-1


def test_load_series_empty_when_no_data():
    sh = _Sheet([list(GS._NAV_HEADERS)])
    s = GS.load_series("TLZF9", _sheet=sh)
    assert len(s) == 0


# ── assess_series_coverage ────────────────────────────────────
def _series(dates, values=None):
    idx = pd.to_datetime(dates)
    v = values if values is not None else np.linspace(10, 11, len(idx))
    return pd.Series(v, index=idx, dtype=float)


def test_coverage_dense_daily_not_sparse():
    idx = pd.bdate_range("2025-01-01", periods=252)
    cov = assess_series_coverage(pd.Series(np.linspace(10, 12, 252), index=idx))
    assert cov["sparse"] is False and cov["coverage"] > 0.9


def test_coverage_low_density_is_sparse():
    # 30 點散在 ~180 天 → coverage ≈ 30/(180×252/365) ≈ 0.24 < 0.6
    idx = pd.to_datetime([f"2025-01-{d:02d}" for d in range(1, 11)]
                         + [f"2025-03-{d:02d}" for d in range(1, 11)]
                         + [f"2025-06-{d:02d}" for d in range(1, 11)])
    cov = assess_series_coverage(pd.Series(np.linspace(10, 11, 30), index=idx))
    assert cov["sparse"] is True and cov["coverage"] < 0.6


def test_coverage_big_gap_is_sparse():
    # 密集但中間破一個 30 天洞 → max_gap > 14 → sparse
    idx = list(pd.bdate_range("2025-01-01", periods=100)) \
        + list(pd.bdate_range("2025-06-20", periods=100))
    cov = assess_series_coverage(pd.Series(np.linspace(10, 11, 200),
                                           index=pd.DatetimeIndex(idx)))
    assert cov["sparse"] is True and cov["max_gap_days"] > 14


def test_coverage_short_series_sparse():
    assert assess_series_coverage(_series(["2026-07-22"]))["sparse"] is True
    assert assess_series_coverage(None)["sparse"] is True


# ── _merge_nav_history_series ────────────────────────────────
def test_merge_extends_and_live_wins(monkeypatch):
    live = _series(["2026-07-21", "2026-07-22"], [11.0, 11.1])
    hist = _series(["2026-07-18", "2026-07-21"], [10.5, 99.9])  # 07-21 撞日
    hist.attrs["source"] = "GoogleSheet:nav_history:X"
    monkeypatch.setattr(GS, "load_series", lambda code: hist)
    merged, trace = _merge_nav_history_series(live, "X")
    assert trace["success"] is True and trace["added"] == 1
    assert len(merged) == 3
    assert merged.loc[pd.Timestamp("2026-07-21")] == 11.0   # live 優先,不被 hist 蓋
    assert merged.index.is_monotonic_increasing and merged.index.is_unique


def test_merge_empty_hist_unchanged(monkeypatch):
    live = _series(["2026-07-21", "2026-07-22"])
    monkeypatch.setattr(GS, "load_series", lambda code: pd.Series(dtype=float))
    merged, trace = _merge_nav_history_series(live, "X")
    assert trace is None and merged is live


def test_merge_read_failure_fail_soft(monkeypatch):
    live = _series(["2026-07-21", "2026-07-22"])

    def _boom(code):
        raise GS.NavHistoryError("quota")
    monkeypatch.setattr(GS, "load_series", _boom)
    merged, trace = _merge_nav_history_series(live, "X")
    assert merged is live and trace["success"] is False    # 不炸,退 live-only


# ── finalize_fund_metrics 端到端 ──────────────────────────────
def _noisy_series(idx):
    """有漲有跌(產生 ≥5 筆負報酬,讓 sharpe/sortino 可自算)。"""
    rng = np.random.default_rng(42)
    vals = 10 * np.cumprod(1 + rng.normal(0.0003, 0.01, len(idx)))
    return pd.Series(vals, index=idx, dtype=float)


def test_finalize_short_live_rescued_by_dense_history(monkeypatch):
    """短 live(5 筆)+ 密集歷史(300 筆)→ 過 len<10 gate、算出 metrics、不稀疏。"""
    hist_idx = pd.bdate_range("2025-01-01", periods=300)
    hist = _noisy_series(hist_idx)
    hist.attrs["source"] = "GoogleSheet:nav_history:X"
    live = hist.iloc[-5:] * 1.0  # 最後 5 天當 live
    monkeypatch.setattr(GS, "load_series", lambda code: hist)
    result = {"series": live, "dividends": [], "fund_code": "X"}
    finalize_fund_metrics(result)
    m = result.get("metrics") or {}
    assert m, "短 live 應被歷史救回並算出 metrics"
    assert m["nav_coverage"]["sparse"] is False
    assert m.get("is_sparse") is not True
    assert any(t.get("source") == "nav_history_merge" and t.get("success")
               for t in result["source_trace"])


def test_finalize_sparse_history_kills_self_calc_annualized(monkeypatch):
    """稀疏累積(80 點 / 每 4 日 1 點)→ sharpe(self_calc)/sortino 砍 None + reason(§1)。"""
    idx = pd.DatetimeIndex([pd.Timestamp("2025-01-01") + pd.Timedelta(days=4 * i)
                            for i in range(80)])   # span 316 天,coverage ≈ 0.37
    hist = _noisy_series(idx)
    live = hist.iloc[-3:] * 1.0
    monkeypatch.setattr(GS, "load_series", lambda code: hist)
    result = {"series": live, "dividends": [], "fund_code": "X"}
    finalize_fund_metrics(result)
    m = result.get("metrics") or {}
    assert m and m["nav_coverage"]["sparse"] is True
    assert m.get("is_sparse") is True and "sparse_reason" in m
    assert m.get("sharpe") is None and m.get("sortino") is None  # 自算年化 → 砍
    assert m.get("std_1y") is None                                # std_source=nav → 砍


def test_finalize_live_only_unchanged(monkeypatch):
    """無累積資料 → 行為與現在完全一致:無 nav_coverage、無 merge trace。"""
    idx = pd.bdate_range("2025-06-01", periods=120)
    live = _noisy_series(idx)
    monkeypatch.setattr(GS, "load_series", lambda code: pd.Series(dtype=float))
    result = {"series": live, "dividends": [], "fund_code": "X"}
    finalize_fund_metrics(result)
    m = result.get("metrics") or {}
    assert m and "nav_coverage" not in m
    assert not any(t.get("source") == "nav_history_merge"
                   for t in result["source_trace"])
