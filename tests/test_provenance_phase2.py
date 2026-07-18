"""tests/test_provenance_phase2.py — F-PROV-1 phase 2 守衛(v19.151)

CLAUDE.md §2.2 Provenance:已有 macro_repository.fetch_fred 帶 source + fetched_at
(v19.83 phase 1)。phase 2 擴至:
- services/macro_tw_local_fetch.py 4 個 fetcher 的 result dict
- hot_money.py DataFrame.attrs(對齊 fetch_yf_close v19.83 pattern)

本檔守:
1. 各 fetcher 結果含 source(具名 dataset)+ fetched_at(UTC ISO)
2. fetched_at 是合法 ISO 8601 + UTC
3. source 字串包含 dataset(非僅 'FinMind')
"""
from __future__ import annotations

import datetime as _dt

import pytest

# 純靜態檢查:不實際 call fetcher(會打網路),從 source 抓出修改點驗證
import inspect


class TestMacroTwLocalFetchProvenance:
    """services/macro_tw_local_fetch.py 4 fetcher 結果 schema 守衛。"""

    def test_ndc_signal_returns_source_and_fetched_at(self):
        from repositories import macro_tw_local_repository as m  # v19.197 P1-4
        src = inspect.getsource(m.fetch_ndc_signal_history)
        assert "'source'" in src and "'fetched_at'" in src, (
            "fetch_ndc_signal_history 應寫入 source + fetched_at"
        )
        # v19.342:dataset 正名 TaiwanBusinessIndicator(TaiwanMacroEconomics 不存在)
        assert "FinMind:TaiwanBusinessIndicator" in src, (
            "source 應為具名 dataset(非僅 'FinMind')"
        )
        # 抓所有寫入 source 的行,確認都升級
        assert "result['source']       = 'FinMind'\n" not in src, (
            "舊版 'FinMind' (短) 殘留 → 升級不完整"
        )

    def test_tw_pmi_local_returns_source_and_fetched_at(self):
        # v19.348 重釘:PMI 改 9 源賽跑,source 由賽跑命中源帶回(血緣沿用),
        # 不再是寫死的 'FinMind:TaiwanMacroEconomics'(該 dataset 不存在,v19.342)
        from repositories import macro_tw_local_repository as m  # v19.197 P1-4
        src = inspect.getsource(m.fetch_tw_pmi_local)
        assert "fetch_tw_pmi_race" in src, "PMI 須走 9 源賽跑(v19.348)"
        assert "FinMind:TaiwanMacroEconomics" not in src, "假 dataset 不得回歸"
        assert "fetched_at" in src
        assert "result['source']" in src, "provenance source 沿用命中源(F-PROV-1)"

    def test_tw_export_yoy_returns_source_and_fetched_at(self):
        from repositories import macro_tw_local_repository as m  # v19.197 P1-4
        src = inspect.getsource(m.fetch_tw_export_yoy)
        # v19.355:出口改走海關 opendata 6053(原 FinMind:TaiwanMacroEconomics 不存在)
        assert "Customs:Export6053" in src
        assert "fetched_at" in src

    def test_foreign_consecutive_days_returns_source_and_fetched_at(self):
        from repositories import macro_tw_local_repository as m  # v19.197 P1-4
        src = inspect.getsource(m.fetch_foreign_consecutive_days)
        # 不同 dataset(外資資料)
        assert "FinMind:TaiwanStockTotalInstitutionalInvestors" in src
        assert "fetched_at" in src


class TestHotMoneyDataFrameAttrs:
    """fetch_foreign_flow_series → DataFrame.attrs 承載 provenance。

    v19.196 P0-4-A:fetcher 從根目錄 hot_money.py 下沉 repositories.hot_money_repository。
    """

    def test_foreign_flow_series_sets_attrs(self):
        from repositories import hot_money_repository
        src = inspect.getsource(hot_money_repository.fetch_foreign_flow_series)
        assert 'attrs["source"]' in src or "attrs['source']" in src, (
            "fetch_foreign_flow_series 應設 DataFrame.attrs['source']"
        )
        assert ('attrs["fetched_at"]' in src
                or "attrs['fetched_at']" in src), (
            "fetch_foreign_flow_series 應設 DataFrame.attrs['fetched_at']"
        )
        assert "FinMind:TaiwanStockTotalInstitutionalInvestors" in src, (
            "source 應為具名 dataset"
        )


class TestSchemaAdditiveNoBreaking:
    """v19.151 為 schema-additive — 既有 caller 不存取新欄位時不應 break。
    對 existing dict-returning fetcher,新增 key 不影響舊 caller。"""

    def test_existing_callers_dont_compare_to_short_finmind(self):
        """sanity:升級 source 字串前已掃過,無 caller 對 == 'FinMind' 做嚴格比對。
        防本 PR 升級後悄悄破壞 downstream(若未來有人加新比對 → 即時警示)。"""
        import subprocess
        result = subprocess.run(
            ["grep", "-rnE", r"source.*==.*['\"]FinMind['\"]\b", "services/", "ui/"],
            cwd=".",
            capture_output=True, text=True,
        )
        # 應該找不到任何嚴格比對(returncode != 0 = no match)
        assert result.returncode != 0, (
            "發現對 source == 'FinMind' 嚴格比對,v19.151 升級為 "
            "'FinMind:<dataset>' 後會 break:\n" + result.stdout
        )


class TestProvenanceFormatConventions:
    """v19.151 provenance 格式慣例(對齊 fetch_fred v19.83 / fetch_yf_close v19.83)。"""

    def test_fetched_at_uses_utc_isoformat(self):
        """fetched_at 必須是 UTC ISO 字串(便於跨時區追蹤,§2.2 慣例)。"""
        from repositories import macro_tw_local_repository as m  # v19.197 P1-4
        src = inspect.getsource(m.fetch_ndc_signal_history)
        # 應出現 datetime.now(timezone.utc).isoformat() 或等價
        assert ("timezone.utc" in src or "tz=UTC" in src
                or 'now(_dt.timezone.utc)' in src), (
            "fetched_at 應使用 UTC 時區(非 naive),確保跨時區追蹤一致"
        )

    def test_source_format_convention(self):
        """source 格式應為 'Provider:Dataset'(對齊 fetch_fred 'FRED:<sid>' v19.83)。

        v19.348 重釘:fetch_tw_pmi_local 改 9 源賽跑後 source 為**動態**命中源
        (白名單守在 shared.schemas.TW_PMI_RACE_SOURCES + validator),無字面
        'Provider:Dataset' 常數可掃 → 從本掃描移除,改驗「沿用命中源」寫法。
        """
        from repositories import macro_tw_local_repository as m  # v19.197 P1-4
        for fn in (m.fetch_ndc_signal_history,
                   m.fetch_tw_export_yoy, m.fetch_foreign_consecutive_days):
            src = inspect.getsource(fn)
            # 應有 'X:Y' 形式
            import re
            assert re.search(r"'[A-Z][a-zA-Z]+:[A-Z][a-zA-Z]+", src), (
                f"{fn.__name__} source 應為 'Provider:Dataset' 形式"
            )
        # PMI:動態血緣 — 驗沿用 hit['source'] 而非字面常數
        _pmi_src = inspect.getsource(m.fetch_tw_pmi_local)
        assert "hit.get('source'" in _pmi_src, (
            'fetch_tw_pmi_local source 應沿用賽跑命中源(動態血緣,v19.348)')
