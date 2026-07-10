"""tests/test_review_fixes_v19_337.py — 第四份外部 review 查證後修復守護。

TARGET:
- repositories/fund/nav_metrics.py   (F 4 個 live fetcher 補 @_daily_cache + @register_cache)
- repositories/fund/sources.py       (D cnyes "data": null → 先判型再取,fallback 鍵可達)
- ui/helpers/io/data_registry.py     (E 淨值 source 讀 series.attrs 真實來源)

查證裁決:其餘主張為已修過/過時或誤判 — 詳 PR 描述。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

_REPO = Path(__file__).resolve().parents[1]


def _src(rel: str) -> str:
    return (_REPO / rel).read_text(encoding="utf-8")


# ══════════════════════════════════════════════════════════════
# F — nav_metrics 4 個 live fetcher 接上 daily cache + 全域刷新註冊
# ══════════════════════════════════════════════════════════════
class TestNavMetricsCached:
    _FETCHERS = ["fetch_nav", "fetch_div", "fetch_performance_wb01", "fetch_risk_metrics"]

    def test_four_fetchers_wrapped_by_daily_cache(self):
        from repositories.fund import nav_metrics as NM

        for name in self._FETCHERS:
            fn = getattr(NM, name)
            # _daily_cache wrapper 才有 cache_info/cache_clear(對齊 _ttl_cache 介面)
            assert hasattr(fn, "cache_info"), f"{name} 未包 _daily_cache"
            assert hasattr(fn, "cache_clear"), f"{name} 未包 _daily_cache"
            assert fn.cache_info()["ttl"] == "daily-reset", f"{name} 非 daily cache"

    def test_four_fetchers_registered_for_global_refresh(self):
        """@register_cache 進 _CACHE_REGISTRY → UI「全域刷新」可清。"""
        from infra.cache import _CACHE_REGISTRY
        from repositories.fund import nav_metrics as NM

        for name in self._FETCHERS:
            fn = getattr(NM, name)
            assert any(fn is reg for reg in _CACHE_REGISTRY), \
                f"{name} 未 @register_cache,全域刷新清不到"

    def test_daily_cache_hit_and_failure_not_cached(self):
        """機制守護:同日第二次呼叫 cache hit;空結果(失敗)不入 cache 會重試。

        這是 F 修復的核心依據 — 若 _daily_cache 開始快取空 Series,
        「失敗黑洞」會回來(整天拿 cached 空值),此測試立即紅燈。
        """
        from infra.cache import _daily_cache

        calls = {"n": 0}

        @_daily_cache(today_fn=lambda: "2026-07-10")
        def _fake_fetch(key: str) -> pd.Series:
            calls["n"] += 1
            if calls["n"] == 1:
                return pd.Series(dtype=float)          # 第一次:上游失敗 → 空
            return pd.Series([1.0, 2.0])               # 之後:成功

        assert _fake_fetch("A").empty                  # 失敗結果
        assert len(_fake_fetch("A")) == 2              # 未被快取 → 重抓成功
        assert len(_fake_fetch("A")) == 2              # 成功結果 → cache hit
        assert calls["n"] == 2, "成功結果應 cache hit,失敗結果應重試"
        info = _fake_fetch.cache_info()
        assert info["uncached_fail"] == 1
        assert info["hits"] == 1


# ══════════════════════════════════════════════════════════════
# D — cnyes "data": null 防護:fallback 鍵(items)可達,不再整段被吞
# ══════════════════════════════════════════════════════════════
class TestCnyesDataNull:
    def test_resolve_code_reaches_items_when_data_null(self, monkeypatch):
        """舊行為:data=null → None.get("list") AttributeError 被 except 吞,
        items 鍵永遠讀不到 → 回空。新行為:先判型,fallback 鍵可達。"""
        from repositories.fund import sources as S

        class _FakeResp:
            status_code = 200

            def json(self):
                return {"data": None,
                        "items": [{"fundCode": "TESTFC1"},
                                  {"fundCode": "TESTFC2"}]}

        monkeypatch.setattr(S.requests, "get", lambda *a, **k: _FakeResp())
        out = S._cnyes_resolve_code("ZZTEST")
        assert "TESTFC1" in out and "TESTFC2" in out

    def test_fetch_nav_cnyes_reaches_items_when_data_null(self, monkeypatch):
        from repositories.fund import sources as S

        class _FakeResp:
            status_code = 200

            def json(self):
                return {"data": None,
                        "items": [{"date": "2026-07-01", "nav": 10.5},
                                  {"date": "2026-07-02", "nav": 10.6}]}

        monkeypatch.setattr(S.requests, "get", lambda *a, **k: _FakeResp())
        monkeypatch.setattr(S, "_cnyes_resolve_code", lambda code: ["TESTFC1"])
        s = S.fetch_nav_cnyes("ZZTEST")
        assert len(s) == 2, "data=null 時應 fallback 到 items 鍵取得 NAV"
        assert s.attrs.get("source", "").startswith("Cnyes:")

    def test_no_remaining_null_unsafe_data_chain(self):
        """守住兩處修點:不再有 data.get("data", {}).get(...) 鏈式寫法。"""
        src = _src("repositories/fund/sources.py")
        assert 'get("data", {}).get(' not in src
        assert src.count("isinstance(_d_raw, dict)") >= 2


# ══════════════════════════════════════════════════════════════
# E — data_registry 淨值 source 讀 series.attrs(F-PROV-1 血緣)
# ══════════════════════════════════════════════════════════════
class TestRegistryNavSource:
    def test_source_reads_attrs_not_hardcoded(self):
        src = _src("ui/helpers/io/data_registry.py")
        # 兩處(基金_/組合_)都改讀 attrs,fallback 保留 MoneyDJ 字樣
        assert src.count('_nav_src = (getattr(s, "attrs", None) or {}).get("source") or "MoneyDJ"') == 2
        # 淨值登記 entry 不再硬寫 "source": "MoneyDJ"
        assert '"source":      "MoneyDJ"' not in src

    def test_attrs_pattern_prefers_real_source(self):
        """語意等價驗證:有 attrs 用真實來源;無 attrs / 空 attrs 回退 MoneyDJ。"""
        s1 = pd.Series([1.0]); s1.attrs["source"] = "Cnyes:fund.api"
        s2 = pd.Series([1.0])
        pick = lambda s: (getattr(s, "attrs", None) or {}).get("source") or "MoneyDJ"  # noqa: E731
        assert pick(s1) == "Cnyes:fund.api"
        assert pick(s2) == "MoneyDJ"
