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
    _patch_urlopen_seq(monkeypatch, [{"total": 0, "rows": []}] * (len(S._MS_SCREENER_HOSTS) * len(S._MS_SCREENER_UNIVERSES)))
    assert S._morningstar_screener_secid("LU9999999999") == ""
    assert S._ms_screener_cache["LU9999999999"] == ""               # 負快取


def test_transient_failure_not_negative_cached(monkeypatch):
    # 全宇宙都拋(timeout)→ 暫時性失敗 → **不入負快取**(可重試)
    _patch_urlopen_seq(monkeypatch,
                       [TimeoutError("boom")] * (len(S._MS_SCREENER_HOSTS) * len(S._MS_SCREENER_UNIVERSES)))
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
        * (len(S._MS_SCREENER_HOSTS) * len(S._MS_SCREENER_UNIVERSES))
    _patch_urlopen_seq(monkeypatch, _payloads)
    assert S._morningstar_screener_secid("LU2023250330") == ""


def test_host_fallback_second_host_hits(monkeypatch):
    # 主 host 連不上(NXDOMAIN 類連線層錯)→ break 到備 host 命中(v19.491 雙 host 備援)
    _patch_urlopen_seq(monkeypatch, [
        OSError("nxdomain"),                            # host1/uni1 → 連線失敗 → 跳 host2
        {"rows": [{"SecId": "FH2", "ISIN": "LU5"}]},    # host2/uni1 → 命中
    ])
    assert S._morningstar_screener_secid("LU5") == "FH2"


def test_connection_error_breaks_host_not_all_universes(monkeypatch):
    # 連線層錯 → 該 host 只試 1 次就跳(不硬打 7 個宇宙);兩 host 各 1 次 = 2 次 urlopen
    _calls = {"n": 0}

    def _boom(*a, **k):
        _calls["n"] += 1
        raise OSError("nxdomain")
    monkeypatch.setattr("urllib.request.urlopen", _boom)
    assert S._morningstar_screener_secid("LU5") == ""
    assert _calls["n"] == len(S._MS_SCREENER_HOSTS)     # 每 host 只打 1 次(連線死不硬試宇宙)
    assert "LU5" not in S._ms_screener_cache            # 連線層 = 暫時 → 不負快取


def test_cache_hit_skips_network(monkeypatch):
    S._ms_screener_cache["LU2023250330"] = "FCACHED"
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("cache 命中不該連外")))
    assert S._morningstar_screener_secid("LU2023250330") == "FCACHED"


# ── 接線:_src_morningstar_nav 先走 screener,再退 SecuritySearch ──────────
def test_src_morningstar_prefers_screener(monkeypatch):
    """screener 優先於 SecuritySearch(原意,**未變**);2026-09-06 起**不再回填**選股池。

    ⚠️ **有意識的政策變更,不是漏刪** · 日期 **2026-09-06** · 決策者:**客戶**
       (2026-09-06 永久授權,逐字:「凡是『查詢/搜尋』功能,一律強制走『純讀取(唯讀)』,
        絕對禁止反向寫入我的 Google Sheet。不用問我,直接切斷寫入!」)

    **舊斷言逐字保留於下,加刪除線**:
        ~~_wb = {}~~
        ~~monkeypatch.setattr(PR, "set_secid",~~
        ~~                    lambda code, secid, **k: _wb.update({"code": code, "secid": secid, **k}))~~
        ~~…~~
        ~~assert _wb["secid"] == "F_SCREENER"        # 回填走 screener 結果~~

    **舊斷言的理由仍然成立**:v19.491 的重點是「screener 比名稱搜尋準,保單平台基金
    才查得到 secId」,而「查到就存回去、下次不必再搜」是很自然的省成本設計,
    ⑤ 設定頁的表格也因此會自動長出晨星 ID。**那個目的一個字都沒有錯。**
    **被權衡掉的是它的形狀**:那個寫入綁在「查詢成功」上、不綁在使用者的意圖上,
    沒有任何按鈕或確認,而且外面包著 `except Exception: pass` —— 成功失敗都不上畫面。
    客戶禁的是**查詢的副作用寫入**這個形狀本身,不是寫入的大小。

    **可達性**:2026-09-06 第三組仲裁判定**走得到**(離線寫入哨兵從
    `fetch_fund_from_moneydj_url` 往下實跑,`ws.update` 當場觸發且函式正常回傳)。

    ⚠️ **代價據實寫明**:secId 不再自動回填 → 往後每次符合閘門條件的查詢都會
    **重新解析一次 ISIN→secId**,對外部來源的呼叫次數上升。**這是刻意的代價。**
    📌 **登記(只登記,不動手)**:若要保留自動回填,**正解是改成使用者明示動作**
    (按鈕／表單送出才寫)—— 那會新增視覺元件,須先送客戶線框草稿,不在本批授權內。

    ⛔ 本測試**不刪除**:`screener 優先`那一半原封不動,只把「回填」翻成「不准回填」。
    """
    import repositories.pool_repository as PR
    monkeypatch.setattr(PR, "resolve_secid", lambda code: None)      # 池中無 secId → 走 ISIN 解析
    monkeypatch.setattr(PR, "resolve_isin", lambda code: "LU2023250330")
    monkeypatch.setattr(PR, "resolve_currency", lambda code: None)
    _wb = {}
    def _must_not_be_called(code, secid, **k):        # noqa: ANN001 — 哨兵
        _wb.update({"code": code, "secid": secid, **k})
        raise AssertionError(
            f"查詢路徑回寫了選股池:set_secid({code!r}, {secid!r}, **{k!r}) —— "
            f"客戶 2026-09-06:查詢一律唯讀。")
    monkeypatch.setattr(PR, "set_secid", _must_not_be_called)
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
    # ⭐ 功能沒有消失:screener 解析出來的 secId **本次抓取照舊使用**
    assert len(out) == 2, "切掉回寫之後連 NAV 都抓不到了 → 那是砍功能,不是切副作用"
    # ⭐ 但一格都沒有寫回使用者的表
    assert _wb == {}, f"查詢路徑仍在回寫選股池:{_wb}"


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


# ── v19.491 收斂(稽核隊伍 4 lens):形狀辨識 / 大小寫容錯 / 異常不負快取 / 幣別 datapoint / 接線 ──
def test_shape_recognized():
    assert S._screener_shape_recognized({"rows": []}) is True
    assert S._screener_shape_recognized({"results": [{"SecId": "F1"}]}) is True
    assert S._screener_shape_recognized([]) is True
    assert S._screener_shape_recognized({"error": "rate limited"}) is False   # 軟錯誤 body
    assert S._screener_shape_recognized("boom") is False
    assert S._screener_shape_recognized(None) is False


def test_secid_key_casing_tolerated(monkeypatch):
    # 回傳用小寫 secId 鍵 → 仍抽得到(唯一載重欄位大小寫容錯,防永久靜默空)
    _patch_urlopen_seq(monkeypatch, [{"rows": [{"secId": "Flower", "ISIN": "LU5"}]}])
    assert S._morningstar_screener_secid("LU5") == "Flower"


def test_pricecurrency_read_when_currency_absent(monkeypatch):
    _patch_urlopen_seq(monkeypatch, [{"rows": [{"SecId": "F1", "ISIN": "LU5", "PriceCurrency": "EUR"}]}])
    assert S._morningstar_screener_secid("LU5") == "F1"
    assert S._ms_ccy_cache["LU5"] == "EUR"                 # 讀 PriceCurrency datapoint


def test_screener_ccy_wins_over_name_suffix(monkeypatch):
    # 名稱後綴說 USD,但 PriceCurrency 說 EUR → screener 直接回的贏(§4.1 準確優先)
    _patch_urlopen_seq(monkeypatch, [{"rows": [
        {"SecId": "F1", "ISIN": "LU5", "Name": "Fund USD", "PriceCurrency": "EUR"}]}])
    S._morningstar_screener_secid("LU5")
    assert S._ms_ccy_cache["LU5"] == "EUR"


def test_lowercase_currency_uppercased(monkeypatch):
    _patch_urlopen_seq(monkeypatch, [{"rows": [{"SecId": "F1", "ISIN": "LU5", "PriceCurrency": "eur"}]}])
    S._morningstar_screener_secid("LU5")
    assert S._ms_ccy_cache["LU5"] == "EUR"


def test_first_valid_row_taken_skipping_invalid(monkeypatch):
    # 非 dict / 無 SecId 的 row 跳過(不炸),取第一個合格 row(不是最後一個)
    _patch_urlopen_seq(monkeypatch, [{"rows": [
        "junk",                                   # 非 dict → 跳過(§1 不炸)
        {"Name": "no secid"},                     # 無 SecId → 跳過
        {"SecId": "FGOOD", "ISIN": "LU5"},        # 第一個合格 → 取這個
        {"SecId": "FLATER", "ISIN": "LU5"},       # 不該取到
    ]}])
    assert S._morningstar_screener_secid("LU5") == "FGOOD"


def test_negative_cache_hit_skips_network(monkeypatch):
    # 確定查無 → 負快取 "";第二次呼叫必須**不連外**(guard 用 `in`,不是 truthy)
    S._ms_screener_cache["LU9999999999"] = ""
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("負快取命中不該連外")))
    assert S._morningstar_screener_secid("LU9999999999") == ""


def test_empty_then_transient_not_negative_cached(monkeypatch):
    # 前宇宙乾淨查無、後宇宙暫時失敗、全程無命中 → 不負快取(可重試;§1 混合序不誤鎖)
    _seq = [{"total": 0, "rows": []}] + [TimeoutError("boom")] * ((len(S._MS_SCREENER_HOSTS) * len(S._MS_SCREENER_UNIVERSES)) - 1)
    _patch_urlopen_seq(monkeypatch, _seq)
    assert S._morningstar_screener_secid("LU5") == ""
    assert "LU5" not in S._ms_screener_cache


def test_rows_present_no_secid_is_anomaly_not_cached(monkeypatch):
    # 全宇宙都「有 rows 卻抽不到 SecId」(疑欄位名不符)→ 異常 → **不負快取**(讓錯誤現形)
    _payloads = [{"rows": [{"WrongKey": "F1", "ISIN": "LU5"}]}] * (len(S._MS_SCREENER_HOSTS) * len(S._MS_SCREENER_UNIVERSES))
    _patch_urlopen_seq(monkeypatch, _payloads)
    assert S._morningstar_screener_secid("LU5") == ""
    assert "LU5" not in S._ms_screener_cache               # 異常 → 未負快取


def test_unrecognized_shape_is_anomaly_not_cached(monkeypatch):
    # 全宇宙都回非 screener 形狀(軟錯誤 body)→ 異常 → 不負快取(§1 不當「確定查無」)
    _payloads = [{"error": "rate limited"}] * (len(S._MS_SCREENER_HOSTS) * len(S._MS_SCREENER_UNIVERSES))
    _patch_urlopen_seq(monkeypatch, _payloads)
    assert S._morningstar_screener_secid("LU5") == ""
    assert "LU5" not in S._ms_screener_cache


def test_url_has_encoded_currency_and_filter(monkeypatch):
    _urls = []

    class _R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"total": 0, "rows": []}).encode()

    def _cap(req, *a, **k):
        _urls.append(req.full_url if hasattr(req, "full_url") else req.get_full_url())
        return _R()

    monkeypatch.setattr("urllib.request.urlopen", _cap)
    S._morningstar_screener_secid("LU5", currency="EUR")
    _first = _urls[0]
    assert "currencyId=EUR" in _first                       # 幣別已帶入(且 EUR 為 ASCII 不變)
    assert "filters=ISIN%3AIN%3ALU5" in _first              # ISIN filter 精確 + 已編碼
    assert "universeIds=FOLUX%24%24ALL" in _first           # 第一宇宙 = 盧森堡,$ 已編碼


def test_user_currency_threaded_into_screener(monkeypatch):
    # 接線:使用者填的幣別要傳進 screener 當 currencyId(不被吞成 USD)
    import repositories.pool_repository as PR
    monkeypatch.setattr(PR, "resolve_secid", lambda code: None)
    monkeypatch.setattr(PR, "resolve_isin", lambda code: "LU2023250330")
    monkeypatch.setattr(PR, "resolve_currency", lambda code: "EUR")
    monkeypatch.setattr(PR, "set_secid", lambda code, secid, **k: None)
    _seen = {}

    def _screener(isin, ccy="USD"):
        _seen["isin"], _seen["ccy"] = isin, ccy
        return "FZ"
    monkeypatch.setattr(S, "_morningstar_screener_secid", _screener)
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _MSResp({
        "TimeSeries": {"Security": [{"HistoryDetail": [{"EndDate": "2024-01-02", "Value": 9.9}]}]},
    }))
    S._src_morningstar_nav("ZZZZ9")
    assert _seen == {"isin": "LU2023250330", "ccy": "EUR"}   # 使用者幣別 → screener


def test_no_isin_screener_not_called(monkeypatch):
    # 池中無 ISIN → screener 不該被呼叫(且不炸),落回名稱搜尋
    import repositories.pool_repository as PR
    monkeypatch.setattr(PR, "resolve_secid", lambda code: None)
    monkeypatch.setattr(PR, "resolve_isin", lambda code: "")     # 無 ISIN
    monkeypatch.setattr(PR, "resolve_currency", lambda code: None)
    monkeypatch.setattr(S, "_morningstar_screener_secid",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("無 ISIN 不該呼叫 screener")))
    monkeypatch.setattr(S, "_morningstar_search_secid", lambda *a, **k: "")   # 名稱搜尋也空
    out = S._src_morningstar_nav("ZZZZ9")
    assert isinstance(out, pd.Series) and out.empty


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
