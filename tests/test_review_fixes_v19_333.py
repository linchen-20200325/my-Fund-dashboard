"""tests/test_review_fixes_v19_333.py — 第二份外部 review 查證後修復的守護測試。

TARGET:
- repositories/fund/sources.py  (F2 yahoo quote[] / F4 alphavantage TypeError / F5 MM/DD 年份)
- infra/proxy.py                (F6 thread-local session 複用)
- ui/tab5_data_guard.py         (F1 safe_float / F8 完整率🟡 / F9 Row5)
- app.py                        (F10 docstring 對齊實作)

查證裁決見 PR 描述:F2a/F4/F6/F8/F10 CONFIRMED;F5 review 主張誤判但挖出
真正的 UTC-vs-TW 時區邊界(修的是後者);F1 為防禦性缺口(現行餵入為強型別,
但 pipeline 無 per-fund try 包覆,炸一檔 = 炸整個 Tab5)。
"""
from __future__ import annotations

import datetime as dt
import json
import threading
from pathlib import Path

import pandas as pd
import pytest

_REPO = Path(__file__).resolve().parents[1]


# ══════════════════════════════════════════════════════════════
# F5 — MM/DD 年份推斷(純函式)
# ══════════════════════════════════════════════════════════════
class TestInferYearForMmdd:
    def _fn(self):
        from repositories.fund.sources import _infer_year_for_mmdd
        return _infer_year_for_mmdd

    def test_cross_year_december_entry_read_in_january(self):
        # 1 月讀到 12/28 → 歸「去年」12/28(近30日窗語意,review 誤判為 bug 的情境)
        assert self._fn()(12, 28, dt.date(2026, 1, 4)) == 2025

    def test_same_day_is_current_year(self):
        assert self._fn()(1, 4, dt.date(2026, 1, 4)) == 2026

    def test_tw_today_prevents_365d_misplacement(self):
        # UTC 慢 TW 8 小時的窗:TW 已 01/05、UTC 仍 01/04。
        # 用 TW today(1/5)時 01/05 條目 → 今年(正確);
        # 若仍用 UTC today(1/4)會推成去年 01/05(≈365 天錯置)— 本次修復點。
        assert self._fn()(1, 5, dt.date(2026, 1, 5)) == 2026
        assert self._fn()(1, 5, dt.date(2026, 1, 4)) == 2025  # 舊行為(文件化對照)

    def test_mid_year_normal(self):
        assert self._fn()(7, 10, dt.date(2026, 7, 10)) == 2026
        assert self._fn()(7, 11, dt.date(2026, 7, 10)) == 2025

    def test_call_site_uses_tw_timezone(self):
        # 源碼守衛:MM/DD 補年份區塊必須用 UTC+8 today,不可退回裸 date.today()
        src = (_REPO / "repositories" / "fund" / "sources.py").read_text(encoding="utf-8")
        assert "_dtt2.timezone(_dtt2.timedelta(hours=8))" in src
        assert "_td2 = _dtt2.date.today()" not in src


# ══════════════════════════════════════════════════════════════
# 共用 fake urlopen
# ══════════════════════════════════════════════════════════════
class _FakeResp:
    def __init__(self, payload: bytes):
        self._p = payload

    def read(self):
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _patch_urlopen(monkeypatch, payload_dict: dict):
    raw = json.dumps(payload_dict).encode("utf-8")

    def _fake_urlopen(req, timeout=None):
        return _FakeResp(raw)

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)


# ══════════════════════════════════════════════════════════════
# F2 — _src_yahoo_finance_nav:quote 空 list 不再靠 IndexError 被吞
# ══════════════════════════════════════════════════════════════
class TestYahooFinanceNavQuoteGuard:
    def test_empty_quote_list_returns_empty_series_without_exception(self, monkeypatch):
        from repositories.fund import sources as S
        monkeypatch.setitem(S._MORNINGSTAR_SECID_MAP, "ZZTST", ("0PTEST", "USD"))
        _patch_urlopen(monkeypatch, {"chart": {"result": [{
            "timestamp": [1700000000, 1700086400],
            "indicators": {"quote": []},   # key 在但空 list — 舊碼 [0] IndexError
        }]}})
        out = S._src_yahoo_finance_nav("ZZTST")
        assert isinstance(out, pd.Series)
        assert out.empty

    def test_happy_path_parses_and_skips_none_and_zero(self, monkeypatch):
        from repositories.fund import sources as S
        monkeypatch.setitem(S._MORNINGSTAR_SECID_MAP, "ZZTST", ("0PTEST", "USD"))
        _patch_urlopen(monkeypatch, {"chart": {"result": [{
            "timestamp": [1700000000, 1700086400, 1700172800, 1700259200],
            "indicators": {"quote": [{"close": [10.5, None, 0, 11.2]}]},
        }]}})
        out = S._src_yahoo_finance_nav("ZZTST")
        # None(缺值)與 0(NAV 不變量:必為正)皆跳過,合法值保留
        assert len(out) == 2
        assert set(round(v, 4) for v in out.values) == {10.5, 11.2}
        assert out.attrs.get("source", "").startswith("Yahoo:chart:")


# ══════════════════════════════════════════════════════════════
# F4 — _src_alphavantage_nav:JSON null 只跳該筆,不再丟整段
# ══════════════════════════════════════════════════════════════
class TestAlphavantageNullValue:
    def test_null_adjusted_close_skips_row_not_whole_series(self, monkeypatch):
        from repositories.fund import sources as S
        monkeypatch.setenv("ALPHAVANTAGE_API_KEY", "test-key")
        monkeypatch.setitem(S._MORNINGSTAR_SECID_MAP, "ZZTST", ("0PTEST", "USD"))
        # 外層有 len(s) >= 10 採納門檻 → 給 11 筆有效 + 1 筆 JSON null
        _ts = {f"2026-01-{d:02d}": {"5. adjusted close": f"{10 + d * 0.1:.1f}"}
               for d in range(2, 13)}                        # 11 筆有效
        _ts["2026-01-15"] = {"5. adjusted close": None}      # 舊碼 float(None) TypeError
        _patch_urlopen(monkeypatch, {"Time Series (Daily)": _ts})
        out = S._src_alphavantage_nav("ZZTST")
        # 舊行為:TypeError 冒泡 → 整段序列丟失(len 0 → 外層報無資料);
        # 新行為:只跳 null 該筆,11 筆有效值完整保留
        assert len(out) == 11
        assert pd.Timestamp("2026-01-15") not in out.index


# ══════════════════════════════════════════════════════════════
# F6 — infra/proxy thread-local session 複用
# ══════════════════════════════════════════════════════════════
class TestThreadLocalSession:
    def test_same_thread_reuses_session(self):
        from infra.proxy import _get_thread_session
        assert _get_thread_session() is _get_thread_session()

    def test_different_threads_get_isolated_sessions(self):
        from infra.proxy import _get_thread_session
        main_s = _get_thread_session()
        got = {}

        def _worker():
            got["s"] = _get_thread_session()

        t = threading.Thread(target=_worker)
        t.start()
        t.join()
        assert got["s"] is not main_s

    def test_make_retry_session_api_unchanged_fresh_each_call(self):
        from infra.proxy import make_retry_session
        assert make_retry_session() is not make_retry_session()

    def test_fetch_url_uses_thread_session(self):
        src = (_REPO / "infra" / "proxy.py").read_text(encoding="utf-8")
        assert "sess     = _get_thread_session()" in src
        assert "sess     = make_retry_session()" not in src


# ══════════════════════════════════════════════════════════════
# F1 / F8 / F9 — tab5 源碼守衛
# ══════════════════════════════════════════════════════════════
class TestTab5Guards:
    @property
    def _src(self) -> str:
        return (_REPO / "ui" / "tab5_data_guard.py").read_text(encoding="utf-8")

    def test_f1_no_bare_float_on_nav_adr(self):
        src = self._src
        assert "float(_d5_nav or 0)" not in src
        assert "float(_d5_adr or 0)" not in src
        assert "_safe_float(_d5_nav)" in src
        assert "_safe_float(_d5_adr)" in src

    def test_f1_safe_float_imported_from_ssot(self):
        assert "from shared.converters import safe_float as _safe_float" in self._src

    def test_f8_partial_counts_half(self):
        src = self._src
        assert "0.5 * _n_yellow" in src
        assert "'/'.join([str(_n_green), str(4)])" not in src

    def test_f9_row5_cells_present(self):
        src = self._src
        for token in ("3Y年化報酬", "5Y年化報酬", "6M報酬", "TER費用率",
                      "ret_3y_ann", "ret_5y_ann", "ret_6m"):
            assert token in src, f"Row5 缺 {token}"

    def test_tab5_still_importable(self):
        import ui.tab5_data_guard as t5
        assert callable(getattr(t5, "render_data_guard_tab", None))


# ══════════════════════════════════════════════════════════════
# F10 — app.py docstring 與快取實作對齊
# ══════════════════════════════════════════════════════════════
class TestAppDocstringCacheClaim:
    def test_no_more_zero_cache_claim(self):
        src = (_REPO / "app.py").read_text(encoding="utf-8")
        assert "零快取:每次操作皆即時抓取" not in src
        assert "_ttl_cache" in src.split('"""')[1]  # docstring 內指向真實快取設計


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
