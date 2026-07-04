"""v19.307 回歸網 — Tab3 載入走 L2 enriched wrapper（metrics 有值）。

user 2026-07-04 截圖回報：核心戰情室 / ① 健康分析表所有 metric 欄位 None
（連「目前市價」都 None）。根因：`ui/helpers/portfolio/load.py::batch_load_unloaded_funds`
與 `ui/helpers/d_mode.py` 呼叫 **raw** `fetch_fund_from_moneydj_url`（result["metrics"]
永遠 {}），而非 R8（fdbfb55 / PR #457）新增、內含 `finalize_fund_metrics` 的
`_enriched` 版 —— R8 漏遷移這兩個 caller。

本檔鎖住：
1. 兩個載入 caller 確實 import enriched wrapper（守門，防再次漏遷移）。
2. `finalize_fund_metrics` 給正常 series → metrics 有值（含「目前市價」nav）；
   給過短 series → **不假造** metrics（§1 Fail Loud）。
"""
from __future__ import annotations

import pandas as pd

# prime 匯入順序：services.fund_service ↔ fund_fetcher 為既有 latent 互相 import
#（fund_fetcher:285 `from services.fund_service import _RF_ANNUAL`），直接把
# fund_service 當「第一個」import 會撞循環（ImportError _RF_ANNUAL）。先走自然入口
# fund_fetcher（app.py 生產路徑同序）即可解 —— 非本次改動引入的問題。
import fund_fetcher  # noqa: F401,E402
from services.fund_service import finalize_fund_metrics  # noqa: E402


def _src(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _mk_series(n: int) -> pd.Series:
    # 線性上升的合成 NAV，index 為升序 DatetimeIndex（calc_metrics 可算）。
    idx = pd.date_range("2022-01-03", periods=n, freq="B")
    vals = [10.0 + 0.01 * i for i in range(n)]
    return pd.Series(vals, index=idx)


class TestLoadCallersUseEnriched:
    def test_portfolio_load_uses_enriched(self):
        src = _src("ui/helpers/portfolio/load.py")
        assert "fetch_fund_from_moneydj_url_enriched" in src, (
            "Tab3 批次載入應改走 L2 enriched wrapper"
        )
        # 舊 raw import 語句不得殘留為實際 import 來源
        assert "from fund_fetcher import fetch_fund_from_moneydj_url\n" not in src

    def test_d_mode_uses_enriched(self):
        src = _src("ui/helpers/d_mode.py")
        assert "fetch_fund_from_moneydj_url_enriched" in src
        assert "from fund_fetcher import fetch_fund_from_moneydj_url as _fetch" not in src


class TestFinalizePopulatesMetrics:
    def test_valid_series_populates_metrics_incl_nav(self):
        """正常長度 series → metrics 非空，且「目前市價」(nav) 算得出（就是截圖那個 None）。"""
        s = _mk_series(400)
        raw = {"series": s, "dividends": [], "fund_code": "TEST",
               "data_source": "test"}
        out = finalize_fund_metrics(raw)
        assert isinstance(out.get("metrics"), dict) and out["metrics"], (
            "有 series 時 metrics 不該是空 dict"
        )
        assert out["metrics"].get("nav") is not None, "目前市價(nav) 應算得出"

    def test_short_series_does_not_fabricate_metrics(self):
        """< 10 筆 → 不算 metrics、留 source_trace 失敗註記（§1 Fail Loud，不假造）。"""
        s = _mk_series(5)
        raw = {"series": s, "dividends": [], "fund_code": "T", "data_source": "t"}
        out = finalize_fund_metrics(raw)
        assert not out.get("metrics"), "過短 series 不該產生 metrics"
        assert any(
            t.get("source") == "nav_series" and not t.get("success")
            for t in out.get("source_trace", [])
        ), "應留下 nav_series 失敗的 source_trace"

    def test_none_series_safe(self):
        """series=None → 安全回傳、不炸、不假造。"""
        out = finalize_fund_metrics({"series": None, "fund_code": "T"})
        assert not out.get("metrics")
