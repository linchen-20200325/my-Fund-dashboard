"""v19.491:ISIN → secId 走 Morningstar **screener** 端點(精確 ISIN filter)。

user 2026-08-20 提案:現有 `_morningstar_search_secid`(lt.morningstar SecuritySearch)為**模糊
名稱搜尋**,保單平台基金常查不到 → 無 secId 可回填 → 落回 MoneyDJ 短窗。改用
`tools.morningstar.co.uk/.../security/screener?filters=ISIN:IN:<isin>`(**與 NAV timeseries 同
host + 同 token `klr5zyak8x`**、精確 ISIN 比對)先解析,查無 / 端點不可用才退回既有搜尋。

驗證:
- `_screener_extract_rows`:標準 {"rows":[…]} / list / {"results":[…]} 多形容忍;非預期 → []。
- `_morningstar_screener_secid`:命中回 F 型 secId + 回填名稱/幣別快取;空 ISIN / 無命中 / 暫時
  失敗 各自處理(§1 暫時失敗不入負快取、確定查無才負快取);多宇宙 fallthrough;cache 命中不重打。
- 與 `_src_morningstar_nav` 的接線:screener 先於 SecuritySearch(純附加 + 命中才回非空)。
"""
import json

import pandas as pd
import pytest

from repositories.fund import sources as S


def _patch_urlopen_seq(monkeypatch, payloads):
    """依呼叫序回傳 payloads 內每一筆(dict→JSON;Exception 實例→拋出)。用於多宇宙 fallthrough。"""
    _seq = list(payloads)

    class _Resp:
        def __init__(self, body):
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return self._body

    def _fake(*a, **k):
        if not _seq:
            raise AssertionError("urlopen 呼叫次數超過預期")
        nxt = _seq.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return _Resp(json.dumps(nxt).encode())

    monkeypatch.setattr("urllib.request.urlopen", _fake)


@pytest.fixture(autouse=True)
def _clear_caches():
    S._ms_screener_cache.clear()
    S._ms_secid_cache.clear()
    S._ms_name_cache.clear()
    S._ms_ccy_cache.clear()
    yield
    S._ms_screener_cache.clear()
    S._ms_secid_cache.clear()
    S._ms_name_cache.clear()
    S._ms_ccy_cache.clear()


# ── _screener_extract_rows:多形容忍 ─────────────────────────────────────
@pytest.mark.parametrize("data,expect_len", [
    ({"total": 1, "rows": [{"SecId": "F1"}]}, 1),
    ([{"SecId": "F1"}, {"SecId": "F2"}], 2),
    ({"results": [{"SecId": "F1"}]}, 1),
    ({"securities": [{"SecId": "F1"}]}, 1),
    ({"total": 0, "rows": []}, 0),
    ({"unexpected": "shape"}, 0),
    ("not-json-dict", 0),
    (None, 0),
])
def test_extract_rows_tolerant(data, expect_len):
    assert len(S._screener_extract_rows(data)) == expect_len


# ── _morningstar_screener_secid:命中 / 回填快取 ──────────────────────────
def test_hit_returns_secid_and_fills_caches(monkeypatch):
    _patch_urlopen_seq(monkeypatch, [{
        "rows": [{"SecId": "F00000P8WB", "Name": "Allianz Income and Growth AMg7 USD",
                  "ISIN": "LU2023250330", "Currency": "USD"}],
    }])
    assert S._morningstar_screener_secid("LU2023250330") == "F00000P8WB"
    assert S._ms_screener_cache["LU2023250330"] == "F00000P8WB"      # 正快取
    assert S._ms_secid_cache["LU2023250330"] == "F00000P8WB"         # 與 SecuritySearch 共用
    assert S._ms_name_cache["LU2023250330"] == "Allianz Income and Growth AMg7 USD"
    assert S._ms_ccy_cache["LU2023250330"] == "USD"                  # screener 直接回幣別


def test_currency_falls_back_to_name_suffix_when_screener_ccy_missing(monkeypatch):
    _patch_urlopen_seq(monkeypatch, [{
        "rows": [{"SecId": "F1", "Name": "Some Fund EUR Hedged", "ISIN": "LU9", "Currency": ""}],
    }])
    assert S._morningstar_screener_secid("LU9") == "F1"
    assert S._ms_ccy_cache["LU9"] == "EUR"                           # Currency 空 → 從名稱猜


def test_empty_isin_returns_empty(monkeypatch):
    # 不該打網路
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("空 ISIN 不該連外")))
    assert S._morningstar_screener_secid("") == ""
    assert S._morningstar_screener_secid("   ") == ""


def test_isin_normalized_upper(monkeypatch):
    _patch_urlopen_seq(monkeypatch, [{"rows": [{"SecId": "FX", "ISIN": "LU2023250330"}]}])
    assert S._morningstar_screener_secid(" lu2023250330 ") == "FX"
    assert "LU2023250330" in S._ms_screener_cache                    # key 正規化為大寫


def test_multi_universe_fallthrough_first_empty_second_hits(monkeypatch):
    # 第一宇宙(FOEUR)回空 rows,第二宇宙(FOTWN)命中 → 應回第二個
    _patch_urlopen_seq(monkeypatch, [
        {"total": 0, "rows": []},
        {"rows": [{"SecId": "FTWN", "Name": "台灣某基金 台幣", "ISIN": "TW000T3619Y1"}]},
    ])
    assert S._morningstar_screener_secid("TW000T3619Y1") == "FTWN"
    assert S._ms_ccy_cache["TW000T3619Y1"] == "TWD"                  # 名稱含「台幣」→ TWD


def test_all_universes_empty_negative_cached(monkeypatch):
    # 全宇宙皆 HTTP 200 但查無 → 確定性負快取
    _patch_urlopen_seq(monkeypatch, [{"total": 0, "rows": []}] * len(S._MS_SCREENER_UNIVERSES))
    assert S._morningstar_screener_secid("LU9999999999") == ""
    assert S._ms_screener_cache["LU9999999999"] == ""               # 負快取


def test_transient_failure_not_negative_cached(monkeypatch):
    # 全宇宙都拋(timeout)→ 暫時性失敗 → **不入負快取**(可重試)
    _patch_urlopen_seq(monkeypatch,
                       [TimeoutError("boom")] * len(S._MS_SCREENER_UNIVERSES))
    assert S._morningstar_screener_secid("LU2023250330") == ""
    assert "LU2023250330" not in S._ms_screener_cache               # 未負快取


def test_mixed_transient_then_hit_returns_secid(monkeypatch):
    # 第一宇宙拋錯(暫時),第二宇宙命中 → 仍應回命中(暫時失敗不擋後續宇宙)
    _patch_urlopen_seq(monkeypatch, [
        TimeoutError("boom"),
        {"rows": [{"SecId": "FHIT", "ISIN": "LU5"}]},
    ])
    assert S._morningstar_screener_secid("LU5") == "FHIT"


def test_isin_mismatch_row_skipped(monkeypatch):
    # 回傳 row 的 ISIN 欄與查詢不符 → 跳過(雙保險防宇宙別名誤配),全宇宙無合格 → ""
    _payloads = [{"rows": [{"SecId": "FWRONG", "ISIN": "XX0000000000"}]}] \
        * len(S._MS_SCREENER_UNIVERSES)
    _patch_urlopen_seq(monkeypatch, _payloads)
    assert S._morningstar_screener_secid("LU2023250330") == ""


def test_cache_hit_skips_network(monkeypatch):
    S._ms_screener_cache["LU2023250330"] = "FCACHED"
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("cache 命中不該連外")))
    assert S._morningstar_screener_secid("LU2023250330") == "FCACHED"


# ── 接線:_src_morningstar_nav 先走 screener,再退 SecuritySearch ──────────
def test_src_morningstar_prefers_screener(monkeypatch):
    import repositories.pool_repository as PR
    monkeypatch.setattr(PR, "resolve_secid", lambda code: None)      # 池中無 secId → 走 ISIN 解析
    monkeypatch.setattr(PR, "resolve_isin", lambda code: "LU2023250330")
    monkeypatch.setattr(PR, "resolve_currency", lambda code: None)
    _wb = {}
    monkeypatch.setattr(PR, "set_secid",
                        lambda code, secid, **k: _wb.update({"code": code, "secid": secid, **k}))
    # screener 命中 → SecuritySearch 不該被呼叫
    monkeypatch.setattr(S, "_morningstar_screener_secid", lambda isin, ccy="USD": "F_SCREENER")
    monkeypatch.setattr(S, "_morningstar_search_secid",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("screener 命中不該退搜尋")))
    # timeseries 主端點(UK)回 2 筆
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _MSResp({
        "TimeSeries": {"Security": [{"HistoryDetail": [
            {"EndDate": "2024-01-02", "Value": 10.5},
            {"EndDate": "2024-01-03", "Value": 11.0},
        ]}]},
    }))
    out = S._src_morningstar_nav("ZZZZ9")
    assert len(out) == 2
    assert _wb["secid"] == "F_SCREENER"                             # 回填走 screener 結果


def test_src_morningstar_falls_back_to_search_when_screener_empty(monkeypatch):
    import repositories.pool_repository as PR
    monkeypatch.setattr(PR, "resolve_secid", lambda code: None)
    monkeypatch.setattr(PR, "resolve_isin", lambda code: "LU2023250330")
    monkeypatch.setattr(PR, "resolve_currency", lambda code: None)
    monkeypatch.setattr(PR, "set_secid", lambda code, secid, **k: None)
    monkeypatch.setattr(S, "_morningstar_screener_secid", lambda isin, ccy="USD": "")   # screener 空
    _called = {"search": False}

    def _search(*a, **k):
        _called["search"] = True
        return "F_SEARCH"
    monkeypatch.setattr(S, "_morningstar_search_secid", _search)
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _MSResp({
        "TimeSeries": {"Security": [{"HistoryDetail": [{"EndDate": "2024-01-02", "Value": 9.9}]}]},
    }))
    out = S._src_morningstar_nav("ZZZZ9")
    assert _called["search"] is True                               # screener 空 → 退回搜尋
    assert len(out) == 1


class _MSResp:
    """timeseries_price COMPACTJSON context-manager 假回應。"""
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return json.dumps(self._payload).encode()
