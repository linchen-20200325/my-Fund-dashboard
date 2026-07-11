# -*- coding: utf-8 -*-
"""v19.342 — 資料異常實診修復 + 第八份建議書屬實項的回歸測試。

修復(user 2026-07-11 實機截圖 + 第八份建議書,詳見 STATE.md v19.342):
1. SLOOS 季頻 freshness 靜態閾值 95/140 → 135/170(季首標記+發布延遲推導)。
2. 熱錢監測 data-only 補抓(hot_money_is_stale / refresh_hot_money_data),
   解「fetch 綁 ARCHIVED expander → 永久 stale」。
3. 雷達診斷 note 截斷 100 → 250(CBOE 層失敗原因不再被吃掉)。
4. NDC fetcher 改走 FinMind TaiwanBusinessIndicator(原 TaiwanMacroEconomics
   dataset 不存在)。
5. 第八份屬實項:app.py 死 wrapper 刪除、TER 行銷數字改有依據(1.01^20≈+22%)。
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

REPO = Path(__file__).resolve().parent.parent


# ═══ 1. SLOOS 季頻閾值(source-scan;_freshness 為閉包,行為由數值釘住)═══
class TestQuarterlyFreshnessThresholds:
    def test_thresholds_recalibrated(self):
        src = (REPO / "ui/helpers/io/data_registry.py").read_text(encoding="utf-8")
        assert "if age <= 135:" in src, "季頻綠燈上限應為 135 天"
        assert "if age <= 170:" in src, "季頻黃燈上限應為 170 天"
        assert "if age <= 95:" not in src, "舊 95 天綠燈上限應移除"

    def test_radar_note_cap_widened(self):
        src = (REPO / "ui/helpers/io/data_registry.py").read_text(encoding="utf-8")
        assert "_note[:250]" in src
        assert "_note[:100]" not in src


# ═══ 2. 熱錢 data-only 補抓 ══════════════════════════════════════
class TestHotMoneyStaleness:
    def test_missing_stash_is_stale(self):
        from ui.hot_money import hot_money_is_stale
        assert hot_money_is_stale(None) is True
        assert hot_money_is_stale({}) is True

    def test_fresh_date_not_stale(self):
        from ui.hot_money import hot_money_is_stale
        today = dt.date(2026, 7, 11)
        assert hot_money_is_stale({"date": "2026-07-10"}, today=today) is False
        assert hot_money_is_stale({"date": "2026-06-12"}, today=today) is False  # 29 天

    def test_over_30d_is_stale(self):
        from ui.hot_money import hot_money_is_stale
        today = dt.date(2026, 7, 11)
        assert hot_money_is_stale({"date": "2026-03-27"}, today=today) is True  # 106 天
        assert hot_money_is_stale({"date": "2026-06-10"}, today=today) is True  # 31 天

    def test_bad_date_treated_stale(self):
        from ui.hot_money import hot_money_is_stale
        assert hot_money_is_stale({"date": "not-a-date"}) is True


class TestRefreshHotMoneyData:
    def _mk_dfs(self):
        dates = pd.date_range("2026-06-22", periods=10, freq="B")
        flow = pd.DataFrame({"date": dates, "foreign_net_yi": [30.0] * 10})
        fx = pd.DataFrame({"date": dates, "usdtwd": [32.0 - i * 0.05 for i in range(10)]})
        return flow, fx

    def test_success_writes_stash(self, monkeypatch):
        import ui.hot_money as HM
        import repositories.hot_money_repository as R
        flow, fx = self._mk_dfs()
        monkeypatch.setattr(R, "fetch_foreign_flow_series", lambda d, t: (flow, ""))
        monkeypatch.setattr(R, "fetch_usdtwd_series", lambda d: (fx, ""))
        _ss: dict = {}
        monkeypatch.setattr(HM, "st", SimpleNamespace(session_state=_ss))
        ok, msg = HM.refresh_hot_money_data(token="")
        assert ok, msg
        hm = _ss.get("_macro_hot_money")
        assert hm and hm["date"] == "2026-07-03"
        assert hm["window"] == 5
        assert "已更新至 2026-07-03" in msg

    def test_empty_flow_fails_and_keeps_stash(self, monkeypatch):
        import ui.hot_money as HM
        import repositories.hot_money_repository as R
        _, fx = self._mk_dfs()
        monkeypatch.setattr(R, "fetch_foreign_flow_series",
                            lambda d, t: (pd.DataFrame(), "FinMind 402"))
        monkeypatch.setattr(R, "fetch_usdtwd_series", lambda d: (fx, ""))
        _ss = {"_macro_hot_money": {"date": "2026-03-27"}}
        monkeypatch.setattr(HM, "st", SimpleNamespace(session_state=_ss))
        ok, msg = HM.refresh_hot_money_data(token="")
        assert not ok
        assert "FinMind 402" in msg
        assert _ss["_macro_hot_money"]["date"] == "2026-03-27", "失敗須保留舊 stash"

    def test_tab1_auto_refresh_once_per_session_flag(self):
        src = (REPO / "ui/tab1_macro_longterm.py").read_text(encoding="utf-8")
        assert "_hm_auto_refresh_tried" in src
        assert "hot_money_is_stale" in src

    def test_tab5_button_reuses_helper(self):
        src = (REPO / "ui/tab5_data_guard.py").read_text(encoding="utf-8")
        assert "refresh_hot_money_data" in src


# ═══ 3. NDC 改走 TaiwanBusinessIndicator ═════════════════════════
_TBI_ROWS = [
    {"date": "2026-03-01", "leading": 102.1, "monitoring": 34, "monitoring_color": "green"},
    {"date": "2026-04-01", "leading": 102.6, "monitoring": 38, "monitoring_color": "yellow-red"},
    {"date": "2026-05-01", "leading": 103.0, "monitoring": 39, "monitoring_color": "red"},
]


class TestFundNdcTbi:
    def test_ndc_signal_from_tbi(self, monkeypatch):
        import repositories.macro_tw_local_repository as M
        monkeypatch.setattr(
            M, "fetch_url",
            lambda *a, **k: SimpleNamespace(
                status_code=200,
                json=lambda: {"msg": "success", "data": _TBI_ROWS}))
        r = M.fetch_ndc_signal_history(months_back=7)
        assert r["score_latest"] == 39
        assert r["score_prev"] == 38
        assert r["color_latest"] == "red"
        assert r["source"] == "FinMind:TaiwanBusinessIndicator"
        assert r["error"] is None

    def test_ndc_requests_tbi_dataset(self, monkeypatch):
        import repositories.macro_tw_local_repository as M
        seen = {}

        def _spy(url, params=None, **k):
            seen.update(params or {})
            return SimpleNamespace(status_code=200,
                                   json=lambda: {"data": _TBI_ROWS})

        monkeypatch.setattr(M, "fetch_url", _spy)
        M.fetch_ndc_signal_history(months_back=8)
        assert seen.get("dataset") == "TaiwanBusinessIndicator"

    def test_ndc_all_fail_graceful(self, monkeypatch):
        import repositories.macro_tw_local_repository as M
        monkeypatch.setattr(M, "fetch_url", lambda *a, **k: None)
        r = M.fetch_ndc_signal_history(months_back=9)
        assert r["score_latest"] is None
        assert "TaiwanBusinessIndicator" in (r["error"] or "")


# ═══ 4. 第八份建議書屬實項 ═══════════════════════════════════════
class TestEighthReviewFixes:
    def test_app_dead_wrapper_removed(self):
        src = (REPO / "app.py").read_text(encoding="utf-8")
        assert "def _calc_data_health(" not in src
        assert "calc_data_health as _calc_data_health_pure" not in src

    def test_ter_compounding_copy_has_basis(self):
        src = (REPO / "ui/tab2_single_fund.py").read_text(encoding="utf-8")
        assert "20 年後終值多 ~25%" not in src, "無依據的 ~25% 行銷數字應改有依據"
        assert "~22%＝1.01²⁰" in src
