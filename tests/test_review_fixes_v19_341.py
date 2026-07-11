"""v19.341 — 第七份外部 review 查證後修復的回歸測試。

修復(查證屬實才修,詳見 STATE.md v19.341):
1. calc_metrics Sharpe 分母補 std>1e-12 guard — 同函式 Sortino/Calmar 皆有防,
   唯 Sharpe 漏;常數 NAV(停售/剛成立,§4.6)std=0 → inf/nan 直流 UI。
2. `_ret(n)` 分母補 >0 guard(第二道防線;入口 pandera 已擋 nav<=0)。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent


def _mk_series(values):
    idx = pd.date_range(end=pd.Timestamp("2026-07-10"), periods=len(values), freq="B")
    return pd.Series([float(v) for v in values], index=idx, name="nav")


class TestSharpeStdGuard:
    def test_constant_nav_sharpe_none_not_inf(self):
        """常數 NAV(300 筆同值):std=0 → Sharpe 必須回 None,不可 inf/nan。"""
        import fund_fetcher  # noqa: F401  解 circular
        from services.fund_service import calc_metrics
        m = calc_metrics(_mk_series([10.0] * 300), [])
        assert m.get("sharpe") is None, f"常數 NAV Sharpe 應為 None,得到 {m.get('sharpe')}"
        # Sortino 同樣無負報酬 → None(既有行為回歸保護)
        assert m.get("sortino") is None

    def test_normal_nav_sharpe_still_float(self):
        """正常波動 NAV:Sharpe 照常回浮點數(guard 不誤殺)。"""
        import fund_fetcher  # noqa: F401
        from services.fund_service import calc_metrics
        vals = [10.0 * (1 + 0.001 * ((-1) ** i) + i * 0.0002) for i in range(300)]
        m = calc_metrics(_mk_series(vals), [])
        assert isinstance(m.get("sharpe"), float)
        assert m.get("sharpe") == m.get("sharpe")  # not NaN


class TestRetDenominatorGuard:
    def test_guard_present_in_source(self):
        """_ret 分母 >0 guard 存在(第二道防線;入口 pandera 擋 nav<=0,
        功能路徑打不進 0,故以 source-scan 釘住)。"""
        src = (REPO / "services/fund_service.py").read_text(encoding="utf-8")
        assert "float(s.iloc[-n])>0" in src

    def test_sharpe_guard_present_in_source(self):
        src = (REPO / "services/fund_service.py").read_text(encoding="utf-8")
        assert "_std252>1e-12" in src
