"""v19.478:ISIN → Yahoo secId 自動解析(免手填 secId)。

user 2026-08-19:「流程本來就該用代號+星辰自動查,為何要我手填」。晨星 SecuritySearch
從雲端搜不到 → 改用 Yahoo search(v1/finance/search)以 ISIN 對到唯一 `{0P…}.F` symbol
(無級別歧義、雲端可達),讓「代號+ISIN → 自動補 5 年」全自動並回填選股池。

驗證:
- `_yahoo_search_secid_by_isin`:從 quotes 取第一個 `{0P…}.F` → 回 `0P…`;空 ISIN / 無 `.F` /
  urlopen 拋錯 各自處理(§1 暫時失敗不入負快取);cache 命中不重打。
- `_src_yahoo_finance_nav`:池中無 secId → 走 ISIN 解析 + 回填 set_secid,再打 chart。
"""
import io
import json

import pandas as pd
import pytest

from repositories.fund import sources as S


def _patch_urlopen(monkeypatch, payload):
    """把 urllib.request.urlopen 換成回傳固定 JSON 的 context manager。"""
    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(payload).encode()

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _Resp())


@pytest.fixture(autouse=True)
def _clear_cache():
    S._yf_isin_secid_cache.clear()
    yield
    S._yf_isin_secid_cache.clear()


# ── _yahoo_search_secid_by_isin ─────────────────────────────────────────
def test_extracts_0p_secid_from_dotF_symbol(monkeypatch):
    _patch_urlopen(monkeypatch, {"quotes": [
        {"symbol": "SOMEEQUITY", "quoteType": "EQUITY"},
        {"symbol": "0P0001J5YG.F", "quoteType": "MUTUALFUND"},
    ]})
    assert S._yahoo_search_secid_by_isin("LU2023250330") == "0P0001J5YG"
    assert S._yf_isin_secid_cache["LU2023250330"] == "0P0001J5YG"   # 正快取


def test_empty_isin_returns_empty(monkeypatch):
    assert S._yahoo_search_secid_by_isin("") == ""
    assert S._yahoo_search_secid_by_isin("   ") == ""


def test_no_dotF_symbol_negative_cached(monkeypatch):
    _patch_urlopen(monkeypatch, {"quotes": [{"symbol": "AAPL", "quoteType": "EQUITY"}]})
    assert S._yahoo_search_secid_by_isin("LU9999999999") == ""
    assert S._yf_isin_secid_cache["LU9999999999"] == ""              # 確定性查無 → 負快取


def test_transient_failure_not_negative_cached(monkeypatch):
    def _boom(*a, **k):
        raise TimeoutError("yahoo timeout")
    monkeypatch.setattr("urllib.request.urlopen", _boom)
    assert S._yahoo_search_secid_by_isin("LU2023250330") == ""
    assert "LU2023250330" not in S._yf_isin_secid_cache             # 暫時失敗不入負快取(可重試)


def test_cache_hit_skips_network(monkeypatch):
    S._yf_isin_secid_cache["LU2023250330"] = "0PCACHED"

    def _should_not_call(*a, **k):
        raise AssertionError("cache 命中不該再打 Yahoo")
    monkeypatch.setattr("urllib.request.urlopen", _should_not_call)
    assert S._yahoo_search_secid_by_isin("LU2023250330") == "0PCACHED"


def test_isin_normalized_upper(monkeypatch):
    _patch_urlopen(monkeypatch, {"quotes": [{"symbol": "0PABC1234X.F"}]})
    assert S._yahoo_search_secid_by_isin(" lu2023250330 ") == "0PABC1234X"
    assert "LU2023250330" in S._yf_isin_secid_cache                 # key 正規化為大寫


# ── _src_yahoo_finance_nav 走 ISIN 自動解析 + 回填 ───────────────────────
def test_yahoo_nav_resolves_secid_via_isin_and_writes_back(monkeypatch):
    import repositories.pool_repository as PR
    monkeypatch.setattr(PR, "resolve_secid", lambda code: ("", "USD"))   # 池中無 secId
    monkeypatch.setattr(PR, "resolve_isin", lambda code: "LU2023250330")
    _wb = {}
    monkeypatch.setattr(PR, "set_secid",
                        lambda code, secid, **k: _wb.update({"code": code, "secid": secid}))
    monkeypatch.setattr(S, "_yahoo_search_secid_by_isin", lambda isin: "0PFOUND")
    # chart 回 2 筆(secId 已解析 → 進 chart 抓取)
    _patch_urlopen(monkeypatch, {"chart": {"result": [{
        "timestamp": [1700000000, 1700086400],
        "indicators": {"quote": [{"close": [10.5, 11.0]}]},
    }]}})
    out = S._src_yahoo_finance_nav("TLZF9")
    assert len(out) == 2                                             # 有抓到(secId 由 ISIN 解析)
    assert _wb == {"code": "TLZF9", "secid": "0PFOUND"}              # 回填選股池


def test_yahoo_nav_no_isin_no_secid_returns_empty(monkeypatch):
    import repositories.pool_repository as PR
    monkeypatch.setattr(PR, "resolve_secid", lambda code: ("", "USD"))
    monkeypatch.setattr(PR, "resolve_isin", lambda code: "")          # 無 ISIN → 無從解析
    monkeypatch.setattr(S, "_yahoo_search_secid_by_isin",
                        lambda isin: (_ for _ in ()).throw(AssertionError("無 ISIN 不該呼叫")))
    out = S._src_yahoo_finance_nav("NOPE1")
    assert isinstance(out, pd.Series) and out.empty
