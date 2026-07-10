"""tests/test_review_fixes_v19_336.py — 第三份外部 review 查證後修復守護。

TARGET:
- repositories/fund/sources.py            (M6 jpmorgan list 型回應)
- repositories/fund/fund_orchestration.py (M7 search_fundclear 單筆壞 nav)
- ui/helpers/io/data_registry.py          (M3 真新鮮度 / M2 盲點補登記)
- ui/tab2_single_fund.py                  (M9 風險卡去重)

查證裁決:M1 REFUTED(上游鍵恆全)/ M4 WONTFIX(標的函式 production 0 caller)
/ M5・M8 低 ROI 不動 — 詳 PR 描述。
"""
from __future__ import annotations

from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]


def _src(rel: str) -> str:
    return (_REPO / rel).read_text(encoding="utf-8")


# ══════════════════════════════════════════════════════════════
# M7 — search_fundclear 單筆壞 nav 不再中止整批
# ══════════════════════════════════════════════════════════════
class TestSearchFundclearBadNav:
    def test_bad_nav_row_does_not_kill_batch(self, monkeypatch):
        from repositories.fund import fund_orchestration as FO

        class _FakeResp:
            status_code = 200

            def json(self):
                return {"data": {"list": [
                    {"fundCode": "AAA01", "fundName": "好基金A", "nav": "12.34"},
                    {"fundCode": "BBB02", "fundName": "壞基金B", "nav": "N/A"},
                    {"fundCode": "CCC03", "fundName": "好基金C", "nav": 56.78},
                ]}}

        monkeypatch.setattr(FO.requests, "post", lambda *a, **k: _FakeResp())
        out = FO.search_fundclear("測試")
        # 舊行為:第二筆 float("N/A") ValueError 中斷 → 只剩 1 筆
        # 新行為:壞筆 nav=0.0 保留,三筆齊全
        assert [r["full_key"] for r in out] == ["AAA01", "BBB02", "CCC03"]
        assert out[1]["nav"] == 0.0
        assert out[2]["nav"] == pytest.approx(56.78)

    def test_source_uses_safe_float(self):
        src = _src("repositories/fund/fund_orchestration.py")
        assert 'nav = safe_float(item.get("nav") or item.get("latestNav")) or 0.0' in src
        assert 'nav  = float(item.get("nav") or item.get("latestNav") or 0)' not in src


# ══════════════════════════════════════════════════════════════
# M6 — jpmorgan list 型回應先判型
# ══════════════════════════════════════════════════════════════
class TestJpmorganListResponse:
    def test_type_dispatch_present(self):
        src = _src("repositories/fund/sources.py")
        assert "if isinstance(d_j, dict):" in src
        # 舊寫法(短路使 list 分支永遠到不了)不得回歸
        assert 'd_j.get("data") or (d_j if isinstance(d_j, list) else [])' not in src
        # ISIN 取得同樣需 dict 守衛
        assert "if not _isin and isinstance(d_j, dict):" in src


# ══════════════════════════════════════════════════════════════
# M3 — registry 子資料真新鮮度(不再硬編 🟢/本月)
# ══════════════════════════════════════════════════════════════
class TestRegistrySubdataFreshness:
    @property
    def _reg(self) -> str:
        return _src("ui/helpers/io/data_registry.py")

    def test_helpers_wired(self):
        src = self._reg
        assert "_sub_fresh" in src        # holdings data_date 路徑
        assert "_prov_fresh" in src       # perf/risk fetched_at 路徑
        assert 'str(_hold.get("data_date") or "")' in src

    def test_no_more_unconditional_green_blocks(self):
        # 5 個子條目原本的「寫死 本月+🟢」組合不得殘留:
        # 現在 fresh_icon 一律來自變數(_ic),不再是字面 "🟢"
        src = self._reg
        assert src.count('"fresh_icon":  "🟢"') == 0

    def test_m2b_advanced_risk_entry(self):
        src = self._reg
        assert "_進階風險" in src
        for k in ("max_drawdown", "sortino", "calmar"):
            assert k in src

    def test_m2a_fx_entry_both_paths(self):
        src = self._reg
        assert "總經_FX_USDTWD" in src
        assert "全源失敗" in src   # 失敗路徑 🔴 可見,非靜默缺席


# ══════════════════════════════════════════════════════════════
# M9 — tab2 風險卡去重
# ══════════════════════════════════════════════════════════════
class TestTab2RiskCardDedup:
    def test_shared_helper_defined_and_used_twice(self):
        src = _src("ui/tab2_single_fund.py")
        assert "def _risk_1y_rows_html(" in src
        assert src.count("_risk_1y_rows_html(") >= 3   # 1 def + 2 call sites
        # 同款 flex-div style 只應存在於 helper 內(1 次)
        assert src.count("display:flex;justify-content:space-between;padding:5px 10px;") == 1

    def test_helper_label_styles(self):
        from ui.tab2_single_fund import _risk_1y_rows_html
        tbl = {"一年": {"標準差": 12.3, "Sharpe": 0.8, "Alpha": 1.1, "Beta": 0.9}}
        short = _risk_1y_rows_html(tbl)
        long = _risk_1y_rows_html(tbl, label_style="long")
        assert "標準差(1Y)" in short and "12.3" in short
        assert "波動 σ(1Y)" in long and "12.3%" in long   # long 版數值型加 %
        # 空表不炸,回可渲染字串
        assert isinstance(_risk_1y_rows_html({}), str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
