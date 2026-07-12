"""services/macro_tw_local_fetch.py 完整 coverage — 18 case mock HTTP。

Phase v19.24（A+B Step 2a）：4 個 fetcher 各覆蓋 happy / 空資料 /
HTTP 失敗 / 解析失敗 / 拐點偵測。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from repositories import macro_tw_local_repository as fetch_mod  # v19.197 P1-4


# ════════════════════════════════════════════════════════════════════════════
# Helpers — 假 FinMind response 工廠
# ════════════════════════════════════════════════════════════════════════════
def _fake_response(rows: list) -> MagicMock:
    """模擬 fetch_url 回傳 requests.Response。"""
    resp = MagicMock()
    resp.json.return_value = {'data': rows}
    return resp


def _fake_bad_json() -> MagicMock:
    """模擬 .json() raise。"""
    resp = MagicMock()
    resp.json.side_effect = ValueError('bad json')
    return resp


def _ndc_rows(vals: list) -> list:
    """模擬 TaiwanBusinessIndicator 寬表 rows(v19.342 起 NDC fetcher 的資料源;
    原 TaiwanMacroEconomics 長表 dataset 不存在,已正名)。"""
    return [
        {'date': f'2026-{i+1:02d}-01',
         'monitoring': v,
         'monitoring_color': 'green'}
        for i, v in enumerate(vals)
    ]


def _pmi_rows(vals: list) -> list:
    return [
        {'date': f'2026-{i+1:02d}-01',
         'indicator': '製造業採購經理人指數',
         'value': v}
        for i, v in enumerate(vals)
    ]


def _export_rows(vals: list) -> list:
    return [
        {'date': f'2026-{i+1:02d}-01',
         'indicator': '出口年增率(%)',
         'value': v}
        for i, v in enumerate(vals)
    ]


def _fi_rows(nets: list[int]) -> list:
    """模擬 TaiwanStockTotalInstitutionalInvestors Foreign_Investor rows。
    每筆 net = buy - sell；給 sell=0、buy=net (簡化)。"""
    rows = []
    for i, n in enumerate(nets):
        rows.append({'date': f'2026-06-{i+1:02d}',
                     'name': 'Foreign_Investor',
                     'buy': max(n, 0),
                     'sell': max(-n, 0)})
    return rows


def _clear_caches() -> None:
    """每次測試前清快取，避免 _ttl_cache 命中前次回傳。"""
    for fn in (fetch_mod.fetch_ndc_signal_history,
               fetch_mod.fetch_tw_pmi_local,
               fetch_mod.fetch_tw_export_yoy,
               fetch_mod.fetch_foreign_consecutive_days):
        if hasattr(fn, 'cache_clear'):
            fn.cache_clear()


# ════════════════════════════════════════════════════════════════════════════
# §1 fetch_ndc_signal_history — 5 case
# ════════════════════════════════════════════════════════════════════════════
class TestFetchNdcSignalHistory:
    def setup_method(self):
        _clear_caches()

    def test_happy_path_bullish_inflection(self):
        # 6 月分數：14, 15, 16, 18, 17, 20 → prev2=17, prev=17, cur=20
        # 實際序列：cur=20, prev=17, prev2=18 → prev2(18)>=prev(17) and cur(20)>prev(17) → '🚀 連2月翻多'
        with patch.object(fetch_mod, 'fetch_url',
                          return_value=_fake_response(_ndc_rows([14, 15, 16, 18, 17, 20]))):
            r = fetch_mod.fetch_ndc_signal_history()
        assert r['error'] is None
        assert r['score_latest'] == 20
        assert r['score_prev'] == 17
        assert r['score_prev2'] == 18
        # v19.151:source 升級為 'FinMind:<dataset>' 形式 + 加 fetched_at(F-PROV-1 phase 2)
        assert r['source'].startswith('FinMind:')
        assert 'fetched_at' in r and r['fetched_at']
        assert '🚀' in r['inflection']
        assert len(r['trend']) == 6

    def test_happy_path_bearish_inflection(self):
        # 序列：25, 23, 22, 20, 21, 18 → cur=18, prev=21, prev2=20
        # prev2(20)<=prev(21) and cur(18)<prev(21) → '⚠️ 連2月翻空'
        with patch.object(fetch_mod, 'fetch_url',
                          return_value=_fake_response(_ndc_rows([25, 23, 22, 20, 21, 18]))):
            r = fetch_mod.fetch_ndc_signal_history()
        assert r['score_latest'] == 18
        assert '⚠️' in r['inflection']

    def test_empty_data_returns_error(self):
        with patch.object(fetch_mod, 'fetch_url',
                          return_value=_fake_response([])):
            r = fetch_mod.fetch_ndc_signal_history()
        assert r['error'] is not None
        assert r['score_latest'] is None
        assert r['source'] is None

    def test_http_fail_returns_error(self):
        with patch.object(fetch_mod, 'fetch_url', return_value=None):
            r = fetch_mod.fetch_ndc_signal_history()
        assert r['error'] is not None
        assert 'TaiwanBusinessIndicator' in r['error']

    def test_partial_data_below_3_rows(self):
        with patch.object(fetch_mod, 'fetch_url',
                          return_value=_fake_response(_ndc_rows([20, 21]))):
            r = fetch_mod.fetch_ndc_signal_history()
        assert r['error'] is not None


# ════════════════════════════════════════════════════════════════════════════
# §2 fetch_tw_pmi_local — 4 case
# v19.348 重釘:PMI 改 9 源賽跑(repositories/tw_pmi_repository),不再走
# FinMind(_pmi_rows 工廠對本 fetcher 退役)。happy path patch 賽跑回傳;
# 失敗 path patch 賽跑 repo 的 fetch_url=None → 真跑 9 源全敗(端到端,
# 不依賴沙箱斷網僥倖 — 原寫法在有網 CI 會真打外部來源)。
# ════════════════════════════════════════════════════════════════════════════
def _race_hit(value, series=None, source='data.gov.tw'):
    d = {'value': value, 'date': '2026-06-01', 'source': source,
         'fetched_at': '2026-07-12T00:00:00+00:00'}
    if series is not None:
        d['series'] = series
    return d


class TestFetchTwPmiLocal:
    def setup_method(self):
        _clear_caches()

    def test_happy_expansion_to_contraction(self):
        import repositories.tw_pmi_repository as race_mod
        # prev=51, cur=48 → '⚠️ 由擴轉縮'
        _ser = [(f'2026-0{i+1}-01', v) for i, v in
                enumerate([52.0, 51.0, 51.0, 50.0, 51.0, 48.0])]
        with patch.object(race_mod, 'fetch_tw_pmi_race',
                          return_value=_race_hit(48.0, series=_ser)):
            r = fetch_mod.fetch_tw_pmi_local()
        assert r['error'] is None
        assert r['value'] == 48.0
        assert r['prev'] == 51.0
        assert '⚠️' in r['inflection']

    def test_happy_contraction_to_expansion(self):
        import repositories.tw_pmi_repository as race_mod
        # prev=49, cur=52 → '🚀 由縮轉擴'
        _ser = [(f'2026-0{i+1}-01', v) for i, v in
                enumerate([47.0, 48.0, 48.0, 49.0, 49.0, 52.0])]
        with patch.object(race_mod, 'fetch_tw_pmi_race',
                          return_value=_race_hit(52.0, series=_ser)):
            r = fetch_mod.fetch_tw_pmi_local()
        assert r['value'] == 52.0
        assert '🚀' in r['inflection']

    def test_single_point_source_no_inflection(self):
        import repositories.tw_pmi_repository as race_mod
        # 單點源(如 CIER-EN)命中:值可用但無上月 → 誠實「資料不足」(§1)
        with patch.object(race_mod, 'fetch_tw_pmi_race',
                          return_value=_race_hit(53.4, source='CIER-EN')):
            r = fetch_mod.fetch_tw_pmi_local()
        assert r['value'] == 53.4 and r['prev'] is None
        assert r['inflection'] == '⬜ 資料不足'

    def test_http_fail_all_sources(self):
        import repositories.tw_pmi_repository as race_mod
        # 端到端:賽跑 repo 的 fetch_url 全回 None → 9 源全敗 → error 合約
        with patch.object(race_mod, 'fetch_url', return_value=None):
            r = fetch_mod.fetch_tw_pmi_local()
        assert r['error'] is not None and '9 源全敗' in r['error']
        assert r['value'] is None


# ════════════════════════════════════════════════════════════════════════════
# §3 fetch_tw_export_yoy — 4 case
# ════════════════════════════════════════════════════════════════════════════
class TestFetchTwExportYoy:
    def setup_method(self):
        _clear_caches()

    def test_happy_negative_to_positive(self):
        # prev=-2.5, cur=3.5 → '🚀 由負轉正'
        with patch.object(fetch_mod, 'fetch_url',
                          return_value=_fake_response(_export_rows(
                              [-5.0, -4.0, -3.0, -2.5, -2.5, 3.5]))):
            r = fetch_mod.fetch_tw_export_yoy()
        assert r['error'] is None
        assert r['value'] == 3.5
        assert r['prev'] == -2.5
        assert '🚀' in r['inflection']

    def test_happy_positive_to_negative(self):
        # prev=2.0, cur=-1.5 → '⚠️ 由正轉負'
        with patch.object(fetch_mod, 'fetch_url',
                          return_value=_fake_response(_export_rows(
                              [10.0, 8.0, 5.0, 3.0, 2.0, -1.5]))):
            r = fetch_mod.fetch_tw_export_yoy()
        assert r['value'] == -1.5
        assert '⚠️' in r['inflection']

    def test_bad_json_returns_error(self):
        with patch.object(fetch_mod, 'fetch_url',
                          return_value=_fake_bad_json()):
            r = fetch_mod.fetch_tw_export_yoy()
        assert r['error'] is not None
        assert r['value'] is None

    def test_http_fail(self):
        with patch.object(fetch_mod, 'fetch_url', return_value=None):
            r = fetch_mod.fetch_tw_export_yoy()
        assert r['error'] is not None


# ════════════════════════════════════════════════════════════════════════════
# §4 fetch_foreign_consecutive_days — 5 case
# ════════════════════════════════════════════════════════════════════════════
class TestFetchForeignConsecutiveDays:
    def setup_method(self):
        _clear_caches()

    def test_happy_five_day_buy_streak(self):
        # 5 連買 → '🟢 連5日買超'
        with patch.object(fetch_mod, 'fetch_url',
                          return_value=_fake_response(_fi_rows(
                              [-100, -50, 200, 300, 250, 180, 320]))):
            r = fetch_mod.fetch_foreign_consecutive_days()
        assert r['error'] is None
        assert r['consec_days'] == 5  # +5
        # v19.151:source 升級為 'FinMind:<dataset>' 形式 + 加 fetched_at(F-PROV-1 phase 2)
        assert r['source'].startswith('FinMind:')
        assert 'fetched_at' in r and r['fetched_at']
        assert '🟢' in r['inflection']

    def test_inflection_sell_to_buy_after_long_sell(self):
        # 連 6 日賣後第 1 日轉買 → '🚀 連6賣→買（拐點）'
        with patch.object(fetch_mod, 'fetch_url',
                          return_value=_fake_response(_fi_rows(
                              [100, -50, -60, -70, -80, -90, -100, 500]))):
            r = fetch_mod.fetch_foreign_consecutive_days()
        assert r['consec_days'] == 1
        assert r['prev_streak'] == -6
        assert '🚀' in r['inflection']
        assert r['reversed'] is True

    def test_empty_foreign_rows_returns_error(self):
        # 有 data 但無 Foreign_Investor name
        rows = [{'date': '2026-06-01', 'name': 'Investment_Trust',
                 'buy': 100, 'sell': 50}]
        with patch.object(fetch_mod, 'fetch_url',
                          return_value=_fake_response(rows)):
            r = fetch_mod.fetch_foreign_consecutive_days()
        assert r['error'] is not None
        assert 'Foreign_Investor' in r['error']

    def test_http_fail_returns_error(self):
        with patch.object(fetch_mod, 'fetch_url', return_value=None):
            r = fetch_mod.fetch_foreign_consecutive_days()
        assert r['error'] is not None
        assert '抓取失敗' in r['error']

    def test_bad_json_returns_error(self):
        with patch.object(fetch_mod, 'fetch_url',
                          return_value=_fake_bad_json()):
            r = fetch_mod.fetch_foreign_consecutive_days()
        assert r['error'] is not None
        assert 'JSON' in r['error']


# ════════════════════════════════════════════════════════════════════════════
# §5 共用 helper smoke test
# ════════════════════════════════════════════════════════════════════════════
class TestSharedHelper:
    def setup_method(self):
        _clear_caches()

    def test_indicator_fuzzy_match_fallback(self):
        # 用變形 indicator key（含 '出口年增率' 但格式不同）→ 應走 contains fallback
        rows = [{'date': f'2026-{i+1:02d}-01',
                 'indicator': '臺灣出口年增率_月底',  # 模糊比對
                 'value': v}
                for i, v in enumerate([1.0, 2.0, 3.0])]
        with patch.object(fetch_mod, 'fetch_url',
                          return_value=_fake_response(rows)):
            r = fetch_mod.fetch_tw_export_yoy()
        assert r['error'] is None
        assert r['value'] == 3.0
