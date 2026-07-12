# -*- coding: utf-8 -*-
"""v19.348 — TW PMI 9 源賽跑移植(user 核准設計 B)回歸鎖。

三個最容易出錯的輸入(§6):
1. 多源同時命中但值不同 → 必須取優先序第一(禁止平均,§2.1)
2. dgtw CSV 含壞列(非數值/無日期)→ series 顯式跳過該列不腦補
3. 單點源命中(無 series)→ value 有值但 prev=None、inflection 誠實「資料不足」
"""
from __future__ import annotations


class _FakeResp:
    def __init__(self, *, text='', content=b'', status_code=200, jobj=None):
        self.text = text
        self.content = content or text.encode('utf-8')
        self.status_code = status_code
        self._jobj = jobj
        self.encoding = 'utf-8'

    def json(self):
        if self._jobj is None:
            raise ValueError('no json')
        return self._jobj


def _clear_pmi_cache():
    from repositories.macro_tw_local_repository import fetch_tw_pmi_local
    getattr(fetch_tw_pmi_local, 'cache_clear', lambda: None)()


# ═════════════════════════════════════════════════════════════════
# 賽跑器:優先序 / 全敗
# ═════════════════════════════════════════════════════════════════
class TestRacePriority:
    def test_priority_first_hit_wins_no_average(self, monkeypatch):
        import repositories.tw_pmi_repository as repo
        _hi = {'value': 52.0, 'date': '2026-06-01', 'label': 'x',
               'source': 'HI', 'is_proxy': False, 'series_id': 'hi'}
        _lo = {'value': 48.0, 'date': '2026-06-01', 'label': 'y',
               'source': 'LO', 'is_proxy': False, 'series_id': 'lo'}
        monkeypatch.setattr(repo, 'PMI_SOURCE_REGISTRY', [
            ('HI', lambda today, mad, errs: _hi),
            ('LO', lambda today, mad, errs: _lo),
        ])
        out = repo.fetch_tw_pmi_race()
        assert out['source'] == 'HI' and out['value'] == 52.0, (
            '兩源皆命中須取優先序第一,禁止平均(§2.1)')
        assert out.get('fetched_at'), 'provenance fetched_at 必帶(§2.2)'

    def test_lower_priority_hit_used_when_higher_fails(self, monkeypatch):
        import repositories.tw_pmi_repository as repo
        _lo = {'value': 48.0, 'date': '2026-06-01', 'label': 'y',
               'source': 'LO', 'is_proxy': False, 'series_id': 'lo'}
        monkeypatch.setattr(repo, 'PMI_SOURCE_REGISTRY', [
            ('HI', lambda today, mad, errs: None),
            ('LO', lambda today, mad, errs: _lo),
        ])
        assert repo.fetch_tw_pmi_race()['source'] == 'LO'

    def test_all_fail_returns_honest_error(self, monkeypatch):
        import repositories.tw_pmi_repository as repo

        def _boom(today, mad, errs):
            errs.append('SRC:模擬失敗')
            return None

        monkeypatch.setattr(repo, 'PMI_SOURCE_REGISTRY', [('SRC', _boom)])
        out = repo.fetch_tw_pmi_race()
        assert out['value'] is None
        assert 'SRC:模擬失敗' in out['_err_pmi']
        assert out['source'] == 'TW_PMI:all_tiers_failed'


# ═════════════════════════════════════════════════════════════════
# dgtw:CSV 全表 → series(fund 擴充)
# ═════════════════════════════════════════════════════════════════
class TestDgtwSeries:
    def _route(self, url, **kwargs):
        if 'data.gov.tw' in url:
            return _FakeResp(jobj={'result': {'resources': [
                {'format': 'CSV', 'url': 'https://x.example/pmi.csv'}]}})
        if url.endswith('pmi.csv'):
            csv = ('年月,製造業PMI\n'
                   '2026/01,48.5\n'
                   '2026/02,49.2\n'
                   '2026/03,壞值\n'          # 壞列:非數值 → 跳過
                   '2026/04,50.1\n'
                   '2026/05,51.3\n')
            return _FakeResp(text=csv)
        return None

    def test_series_extracted_and_bad_rows_skipped(self, monkeypatch):
        import datetime as dt

        import repositories.tw_pmi_repository as repo
        monkeypatch.setattr(repo, 'fetch_url', self._route)
        errs: list = []
        out = repo._pmi_src_dgtw(dt.date(2026, 6, 15), 90, errs)
        assert out is not None and out['source'] == 'data.gov.tw'
        assert out['value'] == 51.3 and out['date'] == '2026-05-01'
        assert [v for _, v in out['series']] == [48.5, 49.2, 50.1, 51.3], (
            '壞列(非數值)須顯式跳過,其餘升冪保留')
        assert out['series'][0][0] == '2026-01-01'   # 升冪


# ═════════════════════════════════════════════════════════════════
# fetch_tw_pmi_local 合約映射(UI 零改動的關鍵)
# ═════════════════════════════════════════════════════════════════
class TestLocalContractMapping:
    def test_series_source_full_contract_and_inflection(self, monkeypatch):
        import repositories.tw_pmi_repository as repo
        from repositories.macro_tw_local_repository import fetch_tw_pmi_local
        from shared.schemas import validate_tw_pmi_dict
        _clear_pmi_cache()
        monkeypatch.setattr(repo, 'fetch_tw_pmi_race', lambda **k: {
            'value': 50.2, 'date': '2026-06-01', 'source': 'data.gov.tw',
            'fetched_at': '2026-07-12T00:00:00+00:00',
            'series': [('2026-01-01', 47.0), ('2026-02-01', 47.5),
                       ('2026-03-01', 48.1), ('2026-04-01', 48.8),
                       ('2026-05-01', 49.8), ('2026-06-01', 50.2)]})
        d = fetch_tw_pmi_local()
        assert d['value'] == 50.2 and d['prev'] == 49.8
        assert len(d['trend']) == 6 and d['trend'][-1] == 50.2
        assert d['inflection'] == '🚀 由縮轉擴'   # 49.8<50<=50.2
        assert d['source'] == 'data.gov.tw' and d['error'] is None
        assert validate_tw_pmi_dict(d) is d, 'UI 端 validator 必須原樣通過'

    def test_single_point_source_honest_no_inflection(self, monkeypatch):
        import repositories.tw_pmi_repository as repo
        from repositories.macro_tw_local_repository import fetch_tw_pmi_local
        from shared.schemas import validate_tw_pmi_dict
        _clear_pmi_cache()
        monkeypatch.setattr(repo, 'fetch_tw_pmi_race', lambda **k: {
            'value': 53.4, 'date': '2026-06-01', 'source': 'CIER-EN',
            'fetched_at': '2026-07-12T00:00:00+00:00'})   # 無 series
        d = fetch_tw_pmi_local()
        assert d['value'] == 53.4 and d['prev'] is None
        assert d['trend'] == [53.4]
        assert d['inflection'] == '⬜ 資料不足', '單點無上月,不腦補轉折(§1)'
        assert validate_tw_pmi_dict(d) is d

    def test_all_fail_maps_to_error_contract(self, monkeypatch):
        import repositories.tw_pmi_repository as repo
        from repositories.macro_tw_local_repository import fetch_tw_pmi_local
        from shared.schemas import validate_tw_pmi_dict
        _clear_pmi_cache()
        monkeypatch.setattr(repo, 'fetch_tw_pmi_race', lambda **k: {
            '_err_pmi': 'x | y', 'value': None,
            'source': 'TW_PMI:all_tiers_failed',
            'fetched_at': '2026-07-12T00:00:00+00:00'})
        d = fetch_tw_pmi_local()
        assert d['value'] is None and d['error'] and '9 源全敗' in d['error']
        assert validate_tw_pmi_dict(d) is d   # error path 原樣放行


# ═════════════════════════════════════════════════════════════════
# SSOT 漂移鎖:registry 來源名 ⊆ shared 白名單
# ═════════════════════════════════════════════════════════════════
def test_registry_sources_subset_of_schema_whitelist():
    from repositories.tw_pmi_repository import PMI_SOURCE_REGISTRY
    from shared.schemas import TW_PMI_RACE_SOURCES
    _reg = {nm for nm, _ in PMI_SOURCE_REGISTRY}
    _missing = _reg - set(TW_PMI_RACE_SOURCES)
    assert not _missing, (
        f'registry 有來源不在 shared.schemas.TW_PMI_RACE_SOURCES 白名單:{_missing}'
        f' — validator 會把它的命中判成違規,兩邊須同步(SSOT 漂移鎖)')
