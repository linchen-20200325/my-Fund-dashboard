# -*- coding: utf-8 -*-
"""v19.351 — Put/Call staleness gate 回歸鎖(外部稽核 C2 後半:過時退出風險加權)。

背景:`_signal_put_call_ratio` 原本只取 `s.iloc[-1]` 算 level,**從不看最新資料點的
日期**。CBOE PCR 源常過時(多次改版,v19.141/v19.277 已換源),一個數週前的舊值仍會
被算成 🔴/🟡 塞進 `summarize_radar` 的系統性風險計數 → 污染分數。

修(§2.4 日頻 🔴>7d + §1 不用舊值污染):最新點 > `_PCR_STALE_DAYS`(7)天 → 回 `_empty`
⬜(summarize_radar 不計 gray = 退出加權),而非誤判散戶恐慌。

三個最容易出錯的輸入(§6):
1. 過時的**極端**值(1.5=紅)→ 不得計紅,須 gray(過時優先於 level)
2. 邊界:恰 7 天 = 不過時(>7 才過時);8 天 = 過時
3. summarize_radar 對 gray PCR → red/yellow 計數不含它
"""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from services import risk_radar as rr


def _pcr(latest_days_ago: int, value: float = 0.9, n: int = 8) -> pd.Series:
    """造一條最新點在 latest_days_ago 天前的 PCR 日頻序列。"""
    end = pd.Timestamp.now().normalize() - pd.Timedelta(days=latest_days_ago)
    idx = pd.date_range(end=end, periods=n, freq="D")
    return pd.Series([value] * (n - 1) + [value], index=idx, dtype=float)


class TestPcrStalenessGate:
    def test_stale_returns_gray_excluded(self):
        with patch.object(rr, "_resolve_put_call",
                          return_value=(_pcr(20, 0.9), "Yahoo ^CPC", [])):
            out = rr._signal_put_call_ratio()
        assert out["color"] == rr.GRAY, "過時應退出風險加權(gray)"
        assert "過時" in out["note"] and "退出風險加權" in out["note"]

    def test_stale_extreme_does_not_pollute(self):
        # 過時的極端值(1.5)本會 lvl=2 紅 → staleness 優先,仍須 gray
        with patch.object(rr, "_resolve_put_call",
                          return_value=(_pcr(30, 1.5), "stooq ^cpc", [])):
            out = rr._signal_put_call_ratio()
        assert out["color"] == rr.GRAY, "過時極端值不得污染成紅燈"

    def test_fresh_scored_normally(self):
        with patch.object(rr, "_resolve_put_call",
                          return_value=(_pcr(0, 1.25), "Yahoo ^CPC", [])):
            out = rr._signal_put_call_ratio()
        assert out["color"] != rr.GRAY, "新鮮資料應正常計分"
        assert "🔴" in out["signal"] and out["value"] == 1.25

    def test_boundary_7d_fresh_8d_stale(self):
        with patch.object(rr, "_resolve_put_call",
                          return_value=(_pcr(7, 0.9), "Yahoo ^CPC", [])):
            assert rr._signal_put_call_ratio()["color"] != rr.GRAY, "恰 7 天不算過時"
        with patch.object(rr, "_resolve_put_call",
                          return_value=(_pcr(8, 0.9), "Yahoo ^CPC", [])):
            assert rr._signal_put_call_ratio()["color"] == rr.GRAY, "8 天=過時"

    def test_summarize_excludes_gray_pcr_from_red(self):
        radar = {"put_call_ratio":
                 rr._empty("Put/Call 最新資料 20 天前(>7d 過時)→ 已退出風險加權", "x")}
        summ = rr.summarize_radar(radar)
        assert summ["red"] == 0 and summ["yellow"] == 0 and summ["gray"] == 1

    def test_constant_aligns_daily_freshness(self):
        assert rr._PCR_STALE_DAYS == 7   # §2.4 日頻 🔴 > 7 days
