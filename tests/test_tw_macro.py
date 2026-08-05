"""
test_tw_macro.py — tw_macro 單元測試

驗證重點:
1. 三大 fetcher(TWSE / FinMind / CBC)都會透過 proxy_helper.fetch_url
   呼叫,即必走 NAS 中繼站,不會繞道直接 import requests。
2. 解析邏輯正確(用 fixture 模擬 API 回應)。
3. M1B/M2 三層備援的優先順序正確。
"""
from __future__ import annotations

from unittest.mock import MagicMock


# v19.196 P0-4-B:tw_macro 搬 repositories/,alias 保留讓 monkeypatch.setattr 不破
from repositories import tw_macro_repository as tw_macro


def _mock_resp(json_data, status: int = 200):
    """requests.Response mock（TWSE / FinMind / CBC 共用）。

    ⚠️ 原版只 stub 了 `.json()`，`m.status_code` 是個「truthy 的 MagicMock 物件」、
    body 也不帶 `status` 欄 → 一旦 production code 開始檢查 API 狀態碼，這個 mock
    就會讓測試量到假象（`MagicMock() == 200` 為 False、`.get('status')` 回 MagicMock）。
    這裡把兩者補齊，讓 mock 與真實 Response 契約一致：
      - `status_code` 為真 int
      - dict body 自動補 `status`（FinMind 的成功/失敗都靠這欄；list body 如 CBC
        ms1.json 不動）
      - `text` 供 infra.proxy 未預期狀態碼 log 取用
    """
    m = MagicMock()
    m.status_code = status
    if isinstance(json_data, dict) and 'status' not in json_data:
        json_data = {**json_data, 'status': status}
    m.json.return_value = json_data
    m.text = str(json_data)[:500]
    return m


# ══════════════════════════════════════════════════════════════
# TWSE 市場寬度
# ══════════════════════════════════════════════════════════════

def test_twse_breadth_via_proxy(monkeypatch):
    captured = {}

    def fake(url, headers=None, params=None, timeout=12):
        captured['url']    = url
        captured['params'] = params
        return _mock_resp({
            'date': '113/05/05',
            'tables': [{
                'data': [
                    ['上漲(漲停)', '500(20)'],
                    ['下跌(跌停)', '300(5)'],
                ]
            }]
        })

    monkeypatch.setattr(tw_macro, 'fetch_url', fake)
    r = tw_macro.fetch_twse_breadth()

    assert captured['url']               == tw_macro.TWSE_MI_INDEX_URL
    assert captured['params']['response'] == 'json'
    assert captured['params']['type']    == 'MS'
    assert r['adv']       == 500
    assert r['dec']       == 300
    assert r['breadth']   == 25.0     # (500-300)/(500+300) * 100
    assert r['z_breadth'] == 1.25     # 25 / 20
    assert r['date']      == '113/05/05'
    assert r['error']     is None


def test_twse_breadth_proxy_failure(monkeypatch):
    monkeypatch.setattr(tw_macro, 'fetch_url', lambda *a, **kw: None)
    r = tw_macro.fetch_twse_breadth()
    assert r['adv']     is None
    assert r['breadth'] is None
    assert r['error']   is not None


def test_twse_breadth_skips_non_breadth_tables(monkeypatch):
    """前面有不含「上漲」字樣的表也應該被跳過,直到找到正確的那張。"""
    def fake(url, headers=None, params=None, timeout=12):
        return _mock_resp({
            'date': '113/05/05',
            'tables': [
                {'data': [['成交筆數', '1234']]},   # 無「上漲」→ skip
                {'data': [
                    ['上漲', '600'],
                    ['下跌', '200'],
                ]},
            ]
        })
    monkeypatch.setattr(tw_macro, 'fetch_url', fake)
    r = tw_macro.fetch_twse_breadth()
    assert r['adv'] == 600
    assert r['dec'] == 200


# ══════════════════════════════════════════════════════════════
# FinMind 外資籌碼
# ══════════════════════════════════════════════════════════════

def test_finmind_via_proxy(monkeypatch):
    captured = {}

    def fake(url, headers=None, params=None, timeout=12):
        captured['url']    = url
        captured['params'] = params
        return _mock_resp({
            'data': [
                {'name': 'Foreign_Investor', 'date': '2026-05-04',
                 'buy': 8_000_000_000, 'sell': 5_000_000_000},
                {'name': 'Investment_Trust', 'date': '2026-05-05',
                 'buy': 100, 'sell': 100},
                {'name': 'Foreign_Investor', 'date': '2026-05-05',
                 'buy': 10_000_000_000, 'sell': 6_000_000_000},
            ]
        })

    monkeypatch.setattr(tw_macro, 'fetch_url', fake)
    r = tw_macro.fetch_finmind_foreign_investor()

    assert captured['url']                   == tw_macro.FINMIND_BASE
    assert captured['params']['dataset']     == 'TaiwanStockTotalInstitutionalInvestors'
    # 應取 2026-05-05(較新): buy 100億 - sell 60億 = 40億
    assert r['fii_net'] == 4_000_000_000
    assert r['z_fii']   == 0.8           # max(-3, min(3, 4e9/5e9))
    assert r['date']    == '2026-05-05'


def test_finmind_no_data(monkeypatch):
    monkeypatch.setattr(tw_macro, 'fetch_url',
                        lambda *a, **kw: _mock_resp({'data': []}))
    r = tw_macro.fetch_finmind_foreign_investor()
    assert r['fii_net'] is None
    assert 'Foreign_Investor' in (r['error'] or '')


def test_finmind_proxy_failure(monkeypatch):
    monkeypatch.setattr(tw_macro, 'fetch_url', lambda *a, **kw: None)
    r = tw_macro.fetch_finmind_foreign_investor()
    assert r['fii_net'] is None
    assert r['error']   is not None


# ── 402 額度用盡：本次修正的核心價值 ────────────────────────────────────
def test_finmind_402_quota_exhausted_reports_status_not_no_data(monkeypatch):
    """FinMind 免費額度用盡回 {"msg": ..., "status": 402} 且 **不帶 data 欄**。

    修正前 `.get('data', [])` 吐 [] → 被歸類成「無 Foreign_Investor 資料」，
    額度用盡完美偽裝成「今天沒外資資料」，資料硬停在某天而無人察覺（本次稽核母題）。
    修正後必須帶出真實 status 與 msg。
    """
    payload = {'msg': 'Requests reached the upper limit.', 'status': 402}
    monkeypatch.setattr(tw_macro, 'fetch_url',
                        lambda *a, **kw: _mock_resp(payload, status=402))
    r = tw_macro.fetch_finmind_foreign_investor()

    err = r['error'] or ''
    assert r['fii_net'] is None
    assert '402' in err, f"錯誤訊息必須帶狀態碼 402，實際：{err!r}"
    assert 'upper limit' in err, f"錯誤訊息必須帶 API msg，實際：{err!r}"
    # 反向鎖：不可再被歸類成「沒有資料」
    assert 'Foreign_Investor' not in err, f"402 被誤報成缺資料：{err!r}"


def test_finmind_401_bad_token_also_surfaces_status(monkeypatch):
    """401（token 失效）同樣走狀態碼分支，不可被當成缺資料。"""
    payload = {'msg': 'token not valid', 'status': 401}
    monkeypatch.setattr(tw_macro, 'fetch_url',
                        lambda *a, **kw: _mock_resp(payload, status=401))
    r = tw_macro.fetch_finmind_foreign_investor(token='bad-token')
    assert '401' in (r['error'] or '')


# ── token pass-through（匿名 300 次/hr vs 具名 600 次/hr）────────────────
def test_finmind_token_is_forwarded_when_provided(monkeypatch):
    """L2/L3 傳入 token → 必須進 params（否則永遠走匿名額度，最易撞 402）。

    §8.2 硬規則：L1 不得自己讀 st.secrets，token 只能由上層傳入。
    """
    captured = {}

    def fake(url, headers=None, params=None, timeout=12):
        captured['params'] = params
        return _mock_resp({'data': []})

    monkeypatch.setattr(tw_macro, 'fetch_url', fake)
    tw_macro.fetch_finmind_foreign_investor(token='tok-abc')
    assert captured['params'].get('token') == 'tok-abc'


def test_finmind_no_token_stays_anonymous(monkeypatch):
    """未傳 token → params 不得出現 token 欄（維持既有匿名行為，向後相容）。"""
    captured = {}

    def fake(url, headers=None, params=None, timeout=12):
        captured['params'] = params
        return _mock_resp({'data': []})

    monkeypatch.setattr(tw_macro, 'fetch_url', fake)
    tw_macro.fetch_finmind_foreign_investor()
    assert 'token' not in captured['params']


def test_finmind_repository_does_not_read_st_secrets():
    """§8.2:L1 repository 不得自己讀 st.secrets（token 必須由上層傳入）。"""
    import inspect
    src = inspect.getsource(tw_macro)
    assert 'st.secrets' not in src, "L1 不得讀 st.secrets — token 應由 L2/L3 傳入"


# ══════════════════════════════════════════════════════════════
# CBC M1B / M2 三層備援
# ══════════════════════════════════════════════════════════════

def test_cbc_m1b_m2_tier1_hit(monkeypatch):
    """Tier 1 ms1.json 命中,Tier 2/3 不應呼叫。"""
    rows = [{'M1B': str(100 + i), 'M2': str(200 + i * 0.5)} for i in range(13)]
    call_count = {'fetch_url': 0}

    def fake(url, headers=None, params=None, timeout=12):
        call_count['fetch_url'] += 1
        if 'ms1.json' in url:
            return _mock_resp(rows)
        return None

    monkeypatch.setattr(tw_macro, 'fetch_url', fake)
    r = tw_macro.fetch_cbc_m1b_m2()

    assert r['tier_used']      == 1
    assert r['is_proxy_tier']  is False
    assert r['m1b_yoy']        is not None
    assert r['m2_yoy']         is not None
    assert r['gap']            is not None
    # 確認 Tier 2 沒被呼叫(只 hit Tier 1 的第一個 url)
    assert call_count['fetch_url'] == 1


def test_cbc_m1b_m2_falls_through_to_tier3(monkeypatch):
    """Tier 1/2 都失敗,Tier 3 ^TWII proxy 命中。"""
    monkeypatch.setattr(tw_macro, 'fetch_url', lambda *a, **kw: None)

    # Mock _try_twii_proxy 以避開實際走 macro_core/網路
    monkeypatch.setattr(tw_macro, '_try_twii_proxy', lambda: (5.0, 1.5))
    r = tw_macro.fetch_cbc_m1b_m2()

    assert r['tier_used']     == 3
    assert r['is_proxy_tier'] is True
    assert r['m1b_yoy']       == 5.0
    assert r['m2_yoy']        == 1.5
    assert r['gap']           == 3.5


def test_cbc_m1b_m2_all_fail(monkeypatch):
    """全部 tier 都失敗 → tier_used=None,error 有值。"""
    monkeypatch.setattr(tw_macro, 'fetch_url', lambda *a, **kw: None)
    monkeypatch.setattr(tw_macro, '_try_twii_proxy', lambda: None)
    r = tw_macro.fetch_cbc_m1b_m2()
    assert r['tier_used'] is None
    assert r['m1b_yoy']   is None
    assert r['error']     is not None


# v19.209 P0-3-#1:整合 API `fetch_tw_market_snapshot` 已拔毒(production 0 caller),
# 此區 test 連動刪除。3 個 sub-fetcher 的個別 test 已在前面 covered。


# ══════════════════════════════════════════════════════════════
# 結構性檢查 — 確認沒有偷偷直接 import requests
# ══════════════════════════════════════════════════════════════

def test_no_direct_requests_import():
    """tw_macro 不應該直接 import requests(全部抓取要走 proxy_helper)。"""
    import inspect
    src = inspect.getsource(tw_macro)
    # tw_macro 應只透過 proxy_helper.fetch_url 抓網路;不應自己 import requests
    assert 'import requests' not in src, \
        "tw_macro 偷偷 import requests — 違反「全部走 NAS proxy」原則"
