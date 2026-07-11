"""tests/test_review_fixes_v19_339.py — 第五份外部 review 查證後修復守護。

TARGET:
- repositories/fund/sources.py       (Bug 4:_parse_nav_html NameError 潛伏 ×3 + Bug 5:負快取)
- services/macro/us_indicators.py    (Bug 3:DXY 月變化除零守衛)
- ui/tab5_data_guard.py              (死碼 _FRED_KEYS / _calc_data_health wrapper)
- repositories/fund/fund_orchestration.py (Bug 1 防再犯 smoke:v19.287 class)

查證裁決:其餘主張為已修過/誤判 — 詳 PR 描述。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

_REPO = Path(__file__).resolve().parents[1]


def _src(rel: str) -> str:
    return (_REPO / rel).read_text(encoding="utf-8")


def _nav_html(n_rows: int = 12) -> str:
    """最小可解析的 MoneyDJ 淨值表(date + value 兩欄)。"""
    rows = "".join(
        f"<tr><td>2026/06/{d:02d}</td><td>10.{d:02d}</td></tr>"
        for d in range(1, n_rows + 1)
    )
    return f"<html><body><table>{rows}</table></body></html>"


class _FakeResp:
    def __init__(self, text: str):
        self.text = text
        self.status_code = 200


# ══════════════════════════════════════════════════════════════
# Bug 4 — sources.py 三處 _parse_nav_html NameError 潛伏
# ══════════════════════════════════════════════════════════════
class TestParseNavHtmlResolvable:
    def test_three_lazy_imports_present(self):
        src = _src("repositories/fund/sources.py")
        assert src.count(
            "from repositories.fund.nav_metrics import _parse_nav_html") == 3, \
            "_src_bank_platform_nav / _src_tcb_nav / _src_insurance_subdomain_nav 各需 lazy import"

    def test_parse_nav_html_unit(self):
        from repositories.fund.nav_metrics import _parse_nav_html

        s = _parse_nav_html(_nav_html(12))
        assert len(s) == 12
        assert float(s.iloc[0]) == 10.01

    def test_src_tcb_nav_no_nameerror_end_to_end(self, monkeypatch):
        """v19.248 拆檔後 sources 模組無 _parse_nav_html 綁定 → 此路徑一走到就
        NameError 被外層吞掉,fallback 從未生效。餵罐頭 HTML 驗證全程可跑通。"""
        from repositories.fund import sources as S

        monkeypatch.setattr(S, "fetch_url_with_retry",
                            lambda *a, **k: _FakeResp(_nav_html(12)))
        s = S._src_tcb_nav("ZZTEST")
        assert len(s) == 12, "應成功解析 12 筆(舊版 NameError → 空 Series)"
        assert str(s.attrs.get("source", "")).startswith("MoneyDJ:")

    def test_src_insurance_subdomain_nav_no_nameerror_end_to_end(self, monkeypatch):
        from repositories.fund import sources as S

        monkeypatch.setattr(S, "fetch_url_with_retry",
                            lambda *a, **k: _FakeResp(_nav_html(11)))
        s = S._src_insurance_subdomain_nav("TLTEST9")   # TL 前綴 → 台灣人壽 portals
        assert len(s) == 11
        assert "InsuranceSubdomain" in str(s.attrs.get("source", ""))


# ══════════════════════════════════════════════════════════════
# Bug 5 — Morningstar secId:暫時性失敗不得永久負快取
# ══════════════════════════════════════════════════════════════
class TestMorningstarNegativeCache:
    def test_transient_failure_not_cached(self, monkeypatch):
        import urllib.request as _ur

        from repositories.fund import sources as S

        def _boom(*a, **k):
            raise OSError("simulated timeout")

        monkeypatch.setattr(_ur, "urlopen", _boom)
        S._ms_secid_cache.pop("ZZ_TRANSIENT_TEST", None)
        assert S._morningstar_search_secid("ZZ_TRANSIENT_TEST") == ""
        assert "ZZ_TRANSIENT_TEST" not in S._ms_secid_cache, \
            "timeout/403 等暫時性失敗不得永久負快取(span-extend 救援會整段失效)"

    def test_legit_empty_still_negative_cached(self, monkeypatch):
        import urllib.request as _ur

        from repositories.fund import sources as S

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b"[]"

        monkeypatch.setattr(_ur, "urlopen", lambda *a, **k: _Resp())
        S._ms_secid_cache.pop("ZZ_EMPTY_TEST", None)
        assert S._morningstar_search_secid("ZZ_EMPTY_TEST") == ""
        assert S._ms_secid_cache.get("ZZ_EMPTY_TEST") == "", \
            "HTTP 200 查無結果 = 確定性負結果,應保留合法負快取"
        S._ms_secid_cache.pop("ZZ_EMPTY_TEST", None)   # 清理,不污染其他測試


# ══════════════════════════════════════════════════════════════
# Bug 3 — DXY 月變化除零守衛
# ══════════════════════════════════════════════════════════════
class TestDxyDivisionGuard:
    def test_dxy_block_has_guard(self):
        src = _src("services/macro/us_indicators.py")
        dxy_block = src.split("# ── DXY ")[1].split("# ── v18.107")[0]
        assert "if m1 else 0.0" in dxy_block, "DXY chg_m 除法應有 m1=0 守衛"


# ══════════════════════════════════════════════════════════════
# 死碼刪除 — tab5 _FRED_KEYS / _calc_data_health wrapper
# ══════════════════════════════════════════════════════════════
class TestTab5DeadCodeRemoved:
    def test_dead_fred_keys_list_gone(self):
        src = _src("ui/tab5_data_guard.py")
        assert "_FRED_KEYS = [" not in src, "v19.195 遷移殘留死清單應刪除"
        # SSOT import 仍在
        assert src.count("from ui.helpers.session import D5_FRED_KEYS") >= 2

    def test_dead_calc_data_health_wrapper_gone(self):
        src = _src("ui/tab5_data_guard.py")
        assert "def _calc_data_health(" not in src
        assert "calc_data_health as _calc_data_health_pure" not in src

    def test_tab5_still_imports(self):
        from ui.tab5_data_guard import render_data_guard_tab  # noqa: F401


# ══════════════════════════════════════════════════════════════
# Bug 1 防再犯 — v19.287 class(star-import 漏綁 → NameError 被吞)smoke
# ══════════════════════════════════════════════════════════════
class TestOrchestrationNamesResolvable:
    _CRITICAL = ["fetch_holdings", "fetch_nav", "fetch_performance_wb01",
                 "fetch_risk_metrics", "_span_extend_insurance_nav",
                 "_src_morningstar_nav", "_src_cnyes_nav"]

    def test_critical_callables_bound(self):
        """v19.287/288 根因:orchestration 呼叫的名字沒真的被 import,NameError
        被 except Exception 吞掉多版本。本 smoke 釘住關鍵名字必須可解析+可呼叫,
        未來拆檔/改 import 若再漏綁,此測試立即紅燈(而非 production 靜默 None)。"""
        from repositories.fund import fund_orchestration as FO

        for name in self._CRITICAL:
            fn = getattr(FO, name, None)
            assert callable(fn), f"fund_orchestration.{name} 不可解析 — v19.287 class 回歸"
