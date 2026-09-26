"""tests/test_v2_l1_error_sidecars.py — docs/v2/49 §6.3 第二類 E-1~E-8 守衛。

## 這組測試守的是什麼

49 §1.4 把現有取數函式依「怎麼交出錯誤」分成甲／乙／丙三類。乙類只回空值、
丙類把例外吞掉 —— ui_v2 接真資料時，頁面會把「抓失敗」誤判成「資料未備」。
§6.3 第二類的 8 處改動**只新增錯誤旁路輸出（與 E-1 的快取），不改既有回傳型別與值**。

## 旁路的統一形狀

每一處新增一個 `<原函式名>_with_error(...)`，參數與原函式相同，回傳
`(原回傳值, error)`：

- `error is None` ⇔ 本層沒有偵測到失敗（值仍可能為空 —— 那是來源明確回答的「沒有」，
  各函式的說明寫明哪些空值屬於這一種）；
- 否則 `error` 是失敗原文（例外型別 ＋ 訊息，不改寫、不截斷）。
- **例外**：E-1 的兩個保單讀取函式，第二個值是「被略過的分頁」清單
  `list[{"tab": 分頁名, "error": 原文}]`（§6.3 E-1 (a) 要的是分頁名）。

每一項有兩組測試：
1. **新行為**：旁路交出正確的原因（改動前 import 不到 `*_with_error` → 紅）；
2. **舊行為不變**：同一份輸入，原函式的回傳值與改動前逐欄相同（改動前後都綠）。

測試一律不打真網路：以 monkeypatch 換掉 `fetch_url` / `fetch_url_with_retry` /
`urllib.request.urlopen` / gspread client。
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pandas as pd
import pytest


# ══════════════════════════════════════════════════════════════
# 共用 stub
# ══════════════════════════════════════════════════════════════

class _Resp:
    """最小的 HTTP 回應替身：`status_code` / `text` / `json()`。"""

    def __init__(self, payload=None, text="", status_code=200):
        self._payload = payload
        self.text = text
        self.status_code = status_code

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def _set_fail_kind(kind: str) -> None:
    """模擬 `infra.proxy.fetch_url` 失敗時在本執行緒留下的失敗分類。"""
    from infra import proxy as _px
    _px._TLS_FAIL.kind = kind


# ══════════════════════════════════════════════════════════════
# E-1 repositories/policy/v2.py::load_all_policies_v2 / load_all_policy_worksheets
# ══════════════════════════════════════════════════════════════

def _v2_ws(title, rows=None, exc=None):
    ws = MagicMock()
    ws.title = title
    if exc is not None:
        ws.get_all_records.side_effect = exc
    else:
        ws.get_all_records.return_value = rows or []
    return ws


def _v2_client(worksheets):
    sh = MagicMock()
    sh.worksheets.return_value = list(worksheets)
    client = MagicMock()
    client.open_by_key.return_value = sh
    return client


_V2_ROW_OK = {
    "policy_id": "P1", "fund_code": "F001", "fund_name": "Alpha",
    "currency": "USD", "tier": "core", "invest_twd": "1,000",
    "div_cash_pct": "", "units": "10", "avg_nav": "12.5", "avg_fx": "31",
}
_V2_ROW_BAD_TWD = {**_V2_ROW_OK, "fund_code": "F002", "invest_twd": "NT$9"}


@pytest.fixture
def _clean_policy_caches():
    from repositories.policy import v2 as v2mod
    v2mod.clear_load_all_ws_cache()
    if hasattr(v2mod, "clear_load_all_policies_v2_cache"):
        v2mod.clear_load_all_policies_v2_cache()
    yield
    v2mod.clear_load_all_ws_cache()
    if hasattr(v2mod, "clear_load_all_policies_v2_cache"):
        v2mod.clear_load_all_policies_v2_cache()


def test_e1_legacy_load_all_policies_v2_return_unchanged(_clean_policy_caches):
    """舊行為不變：同一份輸入，回傳 DataFrame 的欄與值與改動前相同；壞分頁照舊被略過。"""
    from repositories.policy.v2 import ALL_COLS_V2, load_all_policies_v2
    client = _v2_client([
        _v2_ws("P1", rows=[_V2_ROW_OK]),
        _v2_ws("P-BAD", exc=RuntimeError("boom")),
        _v2_ws("_Ledgers", rows=[_V2_ROW_OK]),
    ])
    df = load_all_policies_v2(client, "SID")
    assert list(df.columns) == list(ALL_COLS_V2)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["fund_code"] == "F001"
    assert row["invest_twd"] == 1000
    assert row["units"] == 10.0 and row["avg_nav"] == 12.5 and row["avg_fx"] == 31.0
    # 舊呼叫端（不帶 cache_user）不快取：兩次呼叫兩次開檔
    load_all_policies_v2(client, "SID")
    assert client.open_by_key.call_count == 2


def test_e1_legacy_load_all_policy_worksheets_return_unchanged(_clean_policy_caches):
    """舊行為不變：v1 讀取函式照舊略過壞分頁、照舊快取 60 秒（含缺分頁的結果）。"""
    from repositories.policy.v2 import load_all_policy_worksheets
    good = _v2_ws("PL-1", rows=[{
        "policy_id": "x", "policy_name": "A", "fund_url": "U1", "invest_twd": 100,
        "invest_date": "", "currency": "", "fx_at_buy": "", "notes": "",
        "policy_tier": "",
    }])
    client = _v2_client([good, _v2_ws("PL-BAD", exc=RuntimeError("boom"))])
    df1 = load_all_policy_worksheets(client, "SID-WS")
    df2 = load_all_policy_worksheets(client, "SID-WS")
    assert len(df1) == 1 and df1.iloc[0]["policy_id"] == "PL-1"
    pd.testing.assert_frame_equal(df1, df2)
    assert client.open_by_key.call_count == 1


def test_e1_with_error_reports_skipped_tab(_clean_policy_caches):
    from repositories.policy.v2 import (
        load_all_policies_v2, load_all_policies_v2_with_error,
    )
    client = _v2_client([
        _v2_ws("P1", rows=[_V2_ROW_OK]),
        _v2_ws("P-BAD", exc=RuntimeError("boom kaput")),
    ])
    df, skipped = load_all_policies_v2_with_error(client, "SID")
    assert skipped == [{"tab": "P-BAD", "error": "RuntimeError: boom kaput"}]
    pd.testing.assert_frame_equal(df, load_all_policies_v2(client, "SID"))


def test_e1_with_error_no_skip_returns_empty_list(_clean_policy_caches):
    from repositories.policy.v2 import load_all_policies_v2_with_error
    client = _v2_client([_v2_ws("P1", rows=[_V2_ROW_OK]), _v2_ws("P2", rows=[])])
    _df, skipped = load_all_policies_v2_with_error(client, "SID")
    assert skipped == []


def test_e1_worksheets_with_error_reports_skipped_even_on_cache_hit(_clean_policy_caches):
    from repositories.policy.v2 import load_all_policy_worksheets_with_error
    client = _v2_client([_v2_ws("PL-1", rows=[]), _v2_ws("PL-BAD", exc=KeyError("k"))])
    _d1, s1 = load_all_policy_worksheets_with_error(client, "SID-WS2")
    _d2, s2 = load_all_policy_worksheets_with_error(client, "SID-WS2")
    assert client.open_by_key.call_count == 1          # 第二次是快取命中
    assert s1 == s2 == [{"tab": "PL-BAD", "error": "KeyError: 'k'"}]


def test_e1_cache_keyed_by_user_and_sheet(_clean_policy_caches):
    from repositories.policy.v2 import load_all_policies_v2
    client = _v2_client([_v2_ws("P1", rows=[_V2_ROW_OK])])
    a = load_all_policies_v2(client, "SID", cache_user="u1@x")
    b = load_all_policies_v2(client, "SID", cache_user="u1@x")
    assert client.open_by_key.call_count == 1
    pd.testing.assert_frame_equal(a, b)
    load_all_policies_v2(client, "SID", cache_user="u2@x")     # 換登入者 → 不共用
    assert client.open_by_key.call_count == 2
    load_all_policies_v2(client, "SID-OTHER", cache_user="u1@x")  # 換試算表 → 不共用
    assert client.open_by_key.call_count == 3


def test_e1_cache_returns_copy(_clean_policy_caches):
    from repositories.policy.v2 import load_all_policies_v2
    client = _v2_client([_v2_ws("P1", rows=[_V2_ROW_OK])])
    a = load_all_policies_v2(client, "SID", cache_user="u1@x")
    a.loc[0, "fund_name"] = "MUTATED"
    b = load_all_policies_v2(client, "SID", cache_user="u1@x")
    assert b.loc[0, "fund_name"] == "Alpha"


def test_e1_skipped_result_is_not_cached(_clean_policy_caches):
    from repositories.policy.v2 import load_all_policies_v2_with_error
    client = _v2_client([_v2_ws("P1", rows=[_V2_ROW_OK]),
                         _v2_ws("P-BAD", exc=RuntimeError("boom"))])
    load_all_policies_v2_with_error(client, "SID", cache_user="u1@x")
    _df, skipped = load_all_policies_v2_with_error(client, "SID", cache_user="u1@x")
    assert client.open_by_key.call_count == 2, "缺分頁的結果被快取了"
    assert skipped and skipped[0]["tab"] == "P-BAD"


def test_e1_cache_ttl_expires(_clean_policy_caches, monkeypatch):
    from repositories.policy import v2 as v2mod
    client = _v2_client([_v2_ws("P1", rows=[_V2_ROW_OK])])
    t = {"now": 1000.0}
    monkeypatch.setattr("time.time", lambda: t["now"])
    v2mod.load_all_policies_v2(client, "SID", cache_user="u1@x")
    t["now"] += 59
    v2mod.load_all_policies_v2(client, "SID", cache_user="u1@x")
    assert client.open_by_key.call_count == 1
    t["now"] += 2
    v2mod.load_all_policies_v2(client, "SID", cache_user="u1@x")
    assert client.open_by_key.call_count == 2


def test_e1_clear_cache(_clean_policy_caches):
    from repositories.policy import v2 as v2mod
    client = _v2_client([_v2_ws("P1", rows=[_V2_ROW_OK])])
    v2mod.load_all_policies_v2(client, "SID", cache_user="u1@x")
    v2mod.clear_load_all_policies_v2_cache()
    v2mod.load_all_policies_v2(client, "SID", cache_user="u1@x")
    assert client.open_by_key.call_count == 2


def test_e1_cache_hit_restores_invest_twd_parse_errors(_clean_policy_caches):
    """快取命中時，本金解析失敗清單要與「重讀一次」時相同（不能被別的 loader 的清單蓋掉）。"""
    from repositories.policy import v2 as v2mod
    from repositories.policy._helpers import (
        get_invest_twd_parse_errors, reset_invest_twd_parse_errors,
    )
    client = _v2_client([_v2_ws("P1", rows=[_V2_ROW_OK, _V2_ROW_BAD_TWD])])
    v2mod.load_all_policies_v2(client, "SID", cache_user="u1@x")
    first = get_invest_twd_parse_errors()
    assert len(first) == 1
    reset_invest_twd_parse_errors()                 # 模擬中間有別的 loader 進場
    v2mod.load_all_policies_v2(client, "SID", cache_user="u1@x")
    assert client.open_by_key.call_count == 1
    assert get_invest_twd_parse_errors() == first


@pytest.mark.parametrize("bad", ["", "   "])
def test_e1_empty_cache_user_is_rejected(_clean_policy_caches, bad):
    from repositories.policy.v2 import load_all_policies_v2
    client = _v2_client([_v2_ws("P1", rows=[_V2_ROW_OK])])
    with pytest.raises(ValueError):
        load_all_policies_v2(client, "SID", cache_user=bad)


def test_e1_open_failure_still_raises_and_is_not_cached(_clean_policy_caches):
    from repositories.policy._helpers import PolicySheetError
    from repositories.policy.v2 import load_all_policies_v2_with_error
    client = MagicMock()
    client.open_by_key.side_effect = RuntimeError("down")
    for _ in range(2):
        with pytest.raises(PolicySheetError):
            load_all_policies_v2_with_error(client, "SID", cache_user="u1@x")
    assert client.open_by_key.call_count == 2


# ══════════════════════════════════════════════════════════════
# E-2 repositories/macro_tw_local_repository.py::_finmind_business_indicator
# ══════════════════════════════════════════════════════════════

_TBI_ROWS = [
    {"date": "2026-01-01", "leading": 101.0, "coincident": 99.5, "lagging": 98.0,
     "monitoring": 27, "monitoring_color": "G"},
    {"date": "2026-02-01", "leading": 101.5, "coincident": 99.9, "lagging": 98.1,
     "monitoring": 29, "monitoring_color": "G"},
    {"date": "2026-03-01", "leading": 102.0, "coincident": 100.2, "lagging": 98.3,
     "monitoring": 31, "monitoring_color": "Y"},
]


def test_e2_legacy_private_fn_columns_unchanged(monkeypatch):
    from repositories import macro_tw_local_repository as m
    monkeypatch.setattr(m, "fetch_url", lambda *a, **k: _Resp({"status": 200, "data": _TBI_ROWS}))
    df = m._finmind_business_indicator(months_back=6)
    assert list(df.columns) == ["date", "monitoring", "monitoring_color", "leading"]
    assert df["monitoring"].tolist() == [27, 29, 31]


def test_e2_legacy_ndc_signal_history_unchanged(monkeypatch):
    from repositories import macro_tw_local_repository as m
    m.fetch_ndc_signal_history.cache_clear()
    monkeypatch.setattr(m, "fetch_url", lambda *a, **k: _Resp({"status": 200, "data": _TBI_ROWS}))
    try:
        out = m.fetch_ndc_signal_history(months_back=6)
    finally:
        m.fetch_ndc_signal_history.cache_clear()
    out.pop("fetched_at")
    assert out == {
        "score_latest": 31, "score_prev": 29, "score_prev2": 27,
        "trend": [27, 29, 31], "inflection": "🟢 連3月上升",
        "date_latest": "2026-03-01", "source": "FinMind:TaiwanBusinessIndicator",
        "error": None, "color_latest": "Y",
    }


def test_e2_public_exit_keeps_coincident(monkeypatch):
    from repositories import macro_tw_local_repository as m
    monkeypatch.setattr(m, "fetch_url", lambda *a, **k: _Resp({"status": 200, "data": _TBI_ROWS}))
    df, err = m.fetch_tw_business_indicator_with_error(months_back=6)
    assert err is None
    assert "coincident" in df.columns
    assert df["coincident"].tolist() == [99.5, 99.9, 100.2]


def test_e2_public_exit_reports_failure(monkeypatch):
    from repositories import macro_tw_local_repository as m
    monkeypatch.setattr(m, "fetch_url", lambda *a, **k: _Resp({"status": 402, "msg": "quota"}))
    df, err = m.fetch_tw_business_indicator_with_error(months_back=6)
    assert df is None
    assert "402" in err and "quota" in err


# ══════════════════════════════════════════════════════════════
# E-3 repositories/macro/fred.py::fetch_fred
# ══════════════════════════════════════════════════════════════

_FRED_OK = {"observations": [
    {"date": "2026-01-01", "value": "4.1", "realtime_start": "2026-01-15"},
    {"date": "2026-02-01", "value": ".", "realtime_start": "2026-02-15"},
    {"date": "2026-03-01", "value": "4.3", "realtime_start": "2026-03-15"},
]}


@pytest.fixture
def _fred():
    from repositories.macro import fred as fred_mod
    fred_mod.fetch_fred.cache_clear()
    _set_fail_kind("")
    yield fred_mod
    fred_mod.fetch_fred.cache_clear()
    _set_fail_kind("")


def test_e3_legacy_success_unchanged(_fred, monkeypatch):
    monkeypatch.setattr(_fred, "fetch_url", lambda *a, **k: _Resp(_FRED_OK))
    df = _fred.fetch_fred("SER", "k")
    assert list(df.columns) == ["date", "value", "realtime_start", "source", "fetched_at"]
    assert df["value"].tolist() == [4.1, 4.3]
    assert df["source"].unique().tolist() == ["FRED:SER"]


@pytest.mark.parametrize("case", ["nokey", "none", "json", "empty"])
def test_e3_legacy_failures_still_empty_frames(_fred, monkeypatch, case):
    payload = {"none": None, "json": _Resp(ValueError("bad json")),
               "empty": _Resp({"observations": []})}.get(case)
    monkeypatch.setattr(_fred, "fetch_url", lambda *a, **k: payload)
    df = _fred.fetch_fred("SER", "" if case == "nokey" else "k")
    assert isinstance(df, pd.DataFrame) and df.empty and len(df.columns) == 0


def test_e3_missing_key(_fred):
    df, err = _fred.fetch_fred_with_error("SER", "")
    assert df.empty and "api_key" in err


def test_e3_unreachable(_fred, monkeypatch):
    def _f(*a, **k):
        _set_fail_kind("unreachable")
        return None
    monkeypatch.setattr(_fred, "fetch_url", _f)
    df, err = _fred.fetch_fred_with_error("SER", "k")
    assert df.empty and "unreachable" in err and "FRED:SER" in err


def test_e3_not_found_is_cached_and_error_survives_cache_hit(_fred, monkeypatch):
    calls = {"n": 0}

    def _f(*a, **k):
        calls["n"] += 1
        _set_fail_kind("not_found")
        return None
    monkeypatch.setattr(_fred, "fetch_url", _f)
    _d1, e1 = _fred.fetch_fred_with_error("SER", "k")
    _d2, e2 = _fred.fetch_fred_with_error("SER", "k")
    assert calls["n"] == 1, "404 照舊快取的行為被改掉了"
    assert e1 and e1 == e2 and "not_found" in e1


def test_e3_json_parse_failure(_fred, monkeypatch):
    monkeypatch.setattr(_fred, "fetch_url", lambda *a, **k: _Resp(ValueError("bad json")))
    _df, err = _fred.fetch_fred_with_error("SER", "k")
    assert "JSON" in err and "ValueError: bad json" in err


def test_e3_empty_observations(_fred, monkeypatch):
    monkeypatch.setattr(_fred, "fetch_url", lambda *a, **k: _Resp({"observations": []}))
    _df, err = _fred.fetch_fred_with_error("SER", "k")
    assert "observations" in err


def test_e3_success_has_no_error(_fred, monkeypatch):
    monkeypatch.setattr(_fred, "fetch_url", lambda *a, **k: _Resp(_FRED_OK))
    df, err = _fred.fetch_fred_with_error("SER", "k")
    assert err is None
    # 走同一層 `_ttl_cache`（不另疊快取）：同一組位置參數拿到的是同一個快取物件
    assert df is _fred.fetch_fred("SER", "k", 250)


# ══════════════════════════════════════════════════════════════
# E-4 repositories/macro/yf.py::fetch_yf_close
# ══════════════════════════════════════════════════════════════

_YF_OK = {"chart": {"result": [{
    "timestamp": [1704067200, 1704153600],
    "indicators": {"quote": [{"close": [100.0, 101.0]}]},
}]}}


@pytest.fixture
def _yf():
    from repositories.macro import yf as yf_mod
    yf_mod.fetch_yf_close.cache_clear()
    _set_fail_kind("")
    yield yf_mod
    yf_mod.fetch_yf_close.cache_clear()
    _set_fail_kind("")


def test_e4_legacy_unchanged(_yf, monkeypatch):
    monkeypatch.setattr(_yf, "fetch_url", lambda *a, **k: _Resp(_YF_OK))
    s = _yf.fetch_yf_close("^VIX")
    assert s.tolist() == [100.0, 101.0] and s.name == "^VIX"
    _yf.fetch_yf_close.cache_clear()
    monkeypatch.setattr(_yf, "fetch_url", lambda *a, **k: None)
    s2 = _yf.fetch_yf_close("^VIX")
    assert s2.empty and s2.dtype == float and s2.name == "^VIX"


def test_e4_unreachable(_yf, monkeypatch):
    def _f(*a, **k):
        _set_fail_kind("rate_limited")
        return None
    monkeypatch.setattr(_yf, "fetch_url", _f)
    s, err = _yf.fetch_yf_close_with_error("^VIX")
    assert s.empty and "rate_limited" in err and "^VIX" in err


def test_e4_parse_failure_cached_error_survives(_yf, monkeypatch):
    calls = {"n": 0}

    def _f(*a, **k):
        calls["n"] += 1
        return _Resp({"chart": {"result": None}})
    monkeypatch.setattr(_yf, "fetch_url", _f)
    _s1, e1 = _yf.fetch_yf_close_with_error("BAD")
    _s2, e2 = _yf.fetch_yf_close_with_error("BAD")
    assert calls["n"] == 1
    assert e1 == e2 and "TypeError" in e1


def test_e4_success_no_error(_yf, monkeypatch):
    monkeypatch.setattr(_yf, "fetch_url", lambda *a, **k: _Resp(_YF_OK))
    s, err = _yf.fetch_yf_close_with_error("^VIX")
    assert err is None and len(s) == 2


# ══════════════════════════════════════════════════════════════
# E-5 repositories/fund/nav_metrics.py::fetch_div
# E-8 repositories/fund/nav_metrics.py::fetch_nav
# ══════════════════════════════════════════════════════════════

_DIV_HTML = (
    "<html><body><table><tr><td>除息日</td><td>配息</td></tr>"
    "<tr><td>2025/12/15</td><td>0.05</td></tr>"
    "<tr><td>2025/11/15</td><td>0.04</td></tr></table></body></html>"
)
_NO_DIV_HTML = "<html><body><table><tr><td>基金名稱</td></tr></table></body></html>"


def _nav_html(n):
    rows = "".join(
        f"<tr><td>2025/{(i // 28) + 1:02d}/{(i % 28) + 1:02d}</td><td>{10 + i * 0.1:.2f}</td></tr>"
        for i in range(n))
    return f"<html><body><table>{rows}</table></body></html>"


@pytest.fixture
def _nm():
    from repositories.fund import nav_metrics as nm
    nm.fetch_div.cache_clear()
    nm.fetch_nav.cache_clear()
    yield nm
    nm.fetch_div.cache_clear()
    nm.fetch_nav.cache_clear()


def _strip_fetched_at(divs):
    return [{k: v for k, v in d.items() if k != "fetched_at"} for d in divs]


def test_e5_legacy_unchanged(_nm, monkeypatch):
    monkeypatch.setattr(_nm, "fetch_url_with_retry", lambda *a, **k: _Resp(text=_DIV_HTML))
    out = _nm.fetch_div("FUND01")
    assert _strip_fetched_at(out) == [
        {"date": "2025-12-15", "amount": 0.05, "source": "MoneyDJ:fetch_div:FUND01"},
        {"date": "2025-11-15", "amount": 0.04, "source": "MoneyDJ:fetch_div:FUND01"},
    ]
    _nm.fetch_div.cache_clear()
    monkeypatch.setattr(_nm, "fetch_url_with_retry", lambda *a, **k: None)
    assert _nm.fetch_div("FUND01") == []


def test_e5_all_urls_failed(_nm, monkeypatch):
    monkeypatch.setattr(_nm, "fetch_url_with_retry", lambda *a, **k: None)
    out, err = _nm.fetch_div_with_error("FUND01")
    assert out == [] and err and "取數失敗" in err and "FUND01" in err


def test_e5_page_ok_but_no_dividend_rows_is_not_an_error(_nm, monkeypatch):
    monkeypatch.setattr(_nm, "fetch_url_with_retry", lambda *a, **k: _Resp(text=_NO_DIV_HTML))
    out, err = _nm.fetch_div_with_error("FUND01")
    assert out == [] and err is None


def test_e5_exception_is_reported(_nm, monkeypatch):
    def _boom(*a, **k):
        raise ConnectionError("reset by peer")
    monkeypatch.setattr(_nm, "fetch_url_with_retry", _boom)
    out, err = _nm.fetch_div_with_error("FUND01")
    assert out == [] and "ConnectionError: reset by peer" in err


def test_e5_cache_hit_success_has_no_stale_error(_nm, monkeypatch):
    calls = {"n": 0}

    def _f(*a, **k):
        calls["n"] += 1
        return _Resp(text=_DIV_HTML)
    monkeypatch.setattr(_nm, "fetch_url_with_retry", _f)
    _nm.fetch_div("FUND01", "")          # 與 fetch_div_with_error 同一組位置參數 → 同一筆快取
    _nm._FETCH_DIV_TLS.error = "stale from another call"
    out, err = _nm.fetch_div_with_error("FUND01")
    assert calls["n"] == 1 and len(out) == 2 and err is None


def test_e5_empty_list_is_never_cached(_nm, monkeypatch):
    """`fetch_div_with_error` 依賴「空 list 不入快取」；這條釘住那個前提。"""
    calls = {"n": 0}

    def _f(*a, **k):
        calls["n"] += 1
        return None
    monkeypatch.setattr(_nm, "fetch_url_with_retry", _f)
    _nm.fetch_div("FUND01")
    n1 = calls["n"]
    _nm.fetch_div("FUND01")
    assert calls["n"] == 2 * n1


def test_e8_legacy_unchanged(_nm, monkeypatch):
    monkeypatch.setattr(_nm, "fetch_url_with_retry", lambda *a, **k: _Resp(text=_nav_html(12)))
    s = _nm.fetch_nav("FUND01")
    assert len(s) == 12 and s.iloc[0] == 10.0
    assert s.attrs["source"].startswith("MoneyDJ:")
    _nm.fetch_nav.cache_clear()
    monkeypatch.setattr(_nm, "fetch_url_with_retry", lambda *a, **k: None)
    monkeypatch.setattr(_nm, "_src_cache_files", lambda code: None)
    s2 = _nm.fetch_nav("FUND01")
    assert s2.empty and s2.dtype == float


def test_e8_all_failed_reports_each_attempt(_nm, monkeypatch):
    monkeypatch.setattr(_nm, "fetch_url_with_retry", lambda *a, **k: None)
    monkeypatch.setattr(_nm, "_src_cache_files", lambda code: pd.Series(dtype=float))
    s, err = _nm.fetch_nav_with_error("FUND01")
    assert s.empty and err
    assert err.count("取數失敗") >= 2           # 每個網址各一行
    assert "cache/nav/FUND01.json" in err


def test_e8_parse_too_few_does_not_claim_not_found(_nm, monkeypatch):
    """§8 (c)：解析不到 ≠ 查無此基金；旁路不得替來源下「查無此基金」的結論。"""
    monkeypatch.setattr(_nm, "fetch_url_with_retry", lambda *a, **k: _Resp(text=_nav_html(3)))
    monkeypatch.setattr(_nm, "_src_cache_files", lambda code: None)
    _s, err = _nm.fetch_nav_with_error("FUND01")
    assert "解析出 3 筆" in err
    assert "無法分辨" in err
    assert "查無此基金" not in err.replace("無法分辨查無此基金或頁面改版", "")


def test_e8_cache_fallback_error_reported(_nm, monkeypatch):
    def _boom(code):
        raise OSError("disk")
    monkeypatch.setattr(_nm, "fetch_url_with_retry", lambda *a, **k: None)
    monkeypatch.setattr(_nm, "_src_cache_files", _boom)
    _s, err = _nm.fetch_nav_with_error("FUND01")
    assert "OSError: disk" in err


def test_e8_success_and_stale_fallback_have_no_error(_nm, monkeypatch):
    monkeypatch.setattr(_nm, "fetch_url_with_retry", lambda *a, **k: _Resp(text=_nav_html(12)))
    s, err = _nm.fetch_nav_with_error("FUND01")
    assert err is None and len(s) == 12
    _nm.fetch_nav.cache_clear()
    cached = pd.Series([1.0, 2.0], index=pd.to_datetime(["2025-01-01", "2025-01-02"]))
    cached.attrs["source"] = "GitHubActions:cache/nav/FUND01.json"
    monkeypatch.setattr(_nm, "fetch_url_with_retry", lambda *a, **k: None)
    monkeypatch.setattr(_nm, "_src_cache_files", lambda code: cached)
    s2, err2 = _nm.fetch_nav_with_error("FUND01")
    assert err2 is None and s2 is cached


# ══════════════════════════════════════════════════════════════
# E-6 repositories/fund/sources.py::tdcc_search_fund
# ══════════════════════════════════════════════════════════════

class _UrlResp:
    def __init__(self, data):
        self._b = json.dumps(data).encode("utf-8")

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def _src():
    from repositories.fund import sources as src
    src._tdcc_cache.clear()
    yield src
    src._tdcc_cache.clear()


def _patch_urlopen(monkeypatch, handler):
    import urllib.request as ur
    monkeypatch.setattr(ur, "urlopen", lambda req, timeout=None: handler(req.full_url))


def _all_down(url):
    raise OSError(f"down: {url.split('?')[0]}")


_TDCC_DATA = {
    "3-2": [{"基金名稱": "安聯收益成長基金", "基金代碼": "ALZ01", "總代理名稱": "安聯投信"}],
    "3-4": [{"基金代碼": "ALZ01", "基金名稱": "安聯收益成長基金", "基金淨值": "10.1",
             "日期": "2026-09-25"}],
    "3-1": [{"境外基金機構名稱": "ALLIANZ", "總代理名稱": "安聯投信"}],
}


def _tdcc_ok(url):
    for ep, data in _TDCC_DATA.items():
        if url.endswith("/" + ep):
            return _UrlResp(data)
    raise AssertionError(f"unexpected url {url}")


def test_e6_legacy_unchanged(_src, monkeypatch):
    _patch_urlopen(monkeypatch, _all_down)
    assert _src.tdcc_search_fund("安聯") == []
    _src._tdcc_cache.clear()
    _patch_urlopen(monkeypatch, _tdcc_ok)
    assert _src.tdcc_search_fund("安聯") == [{
        "基金名稱": "安聯收益成長基金", "基金代碼": "ALZ01", "總代理": "安聯投信",
        "淨值": "10.1", "日期": "2026-09-25", "來源": "TDCC-3-2",
    }]
    assert _src._tdcc_get("3-2") == _TDCC_DATA["3-2"]


def test_e6_all_failed_is_not_zero_match(_src, monkeypatch):
    _patch_urlopen(monkeypatch, _all_down)
    res, err = _src.tdcc_search_fund_with_error("安聯")
    assert res == []
    assert err and "3-2" in err and "3-4" in err and "FundClear" in err
    assert "OSError: down" in err


def test_e6_success_no_error(_src, monkeypatch):
    _patch_urlopen(monkeypatch, _tdcc_ok)
    res, err = _src.tdcc_search_fund_with_error("安聯")
    assert err is None and len(res) == 1


def test_e6_tdcc_get_error_out_is_opt_in(_src, monkeypatch):
    _patch_urlopen(monkeypatch, _all_down)
    box: dict = {}
    assert _src._tdcc_get("3-2", error_out=box) == []
    assert box["error"].startswith("OSError: down")


# ══════════════════════════════════════════════════════════════
# E-7 repositories/ledger_repository.py::load_all_ledgers
# ══════════════════════════════════════════════════════════════

class WorksheetNotFound(Exception):
    """與 gspread 同名的替身（`_is_worksheet_not_found` 以型別名判斷）。"""


def _ledger_client(open_exc=None, ws_exc=None, records=None):
    client = MagicMock()
    if open_exc is not None:
        client.open_by_key.side_effect = open_exc
        return client
    sh = MagicMock()
    if ws_exc is not None:
        sh.worksheet.side_effect = ws_exc
    else:
        ws = MagicMock()
        ws.get_all_records.return_value = records or []
        sh.worksheet.return_value = ws
    client.open_by_key.return_value = sh
    return client


@pytest.mark.parametrize("kw", [
    {"open_exc": PermissionError("403")},
    {"ws_exc": WorksheetNotFound("_Ledgers")},
    {"ws_exc": RuntimeError("quota")},
    {"records": []},
])
def test_e7_legacy_unchanged(kw):
    from repositories.ledger_repository import LEDGER_COLS, load_all_ledgers
    df = load_all_ledgers(_ledger_client(**kw), "SID")
    assert df.empty and list(df.columns) == list(LEDGER_COLS)


def test_e7_legacy_rows_unchanged():
    from repositories.ledger_repository import load_all_ledgers
    df = load_all_ledgers(_ledger_client(records=[{
        "policy_id": " P1 ", "date": "2026-01-02", "code": "F1", "action": "buy",
        "units": "1,000", "nav_at_action": "10", "twd": "300000", "fee": "", "note": "x",
    }]), "SID")
    assert df.iloc[0]["policy_id"] == "P1" and df.iloc[0]["units"] == 1000.0


def test_e7_open_failure_is_reported():
    from repositories.ledger_repository import load_all_ledgers_with_error
    df, err = load_all_ledgers_with_error(_ledger_client(open_exc=PermissionError("403 forbidden")), "SID")
    assert df.empty and "PermissionError: 403 forbidden" in err


def test_e7_other_worksheet_error_is_reported():
    from repositories.ledger_repository import load_all_ledgers_with_error
    _df, err = load_all_ledgers_with_error(_ledger_client(ws_exc=RuntimeError("quota")), "SID")
    assert "RuntimeError: quota" in err


def test_e7_missing_tab_is_not_an_error():
    from repositories.ledger_repository import load_all_ledgers_with_error
    df, err = load_all_ledgers_with_error(_ledger_client(ws_exc=WorksheetNotFound("_Ledgers")), "SID")
    assert df.empty and err is None


# ══════════════════════════════════════════════════════════════
# 跨項：旁路鍵名一致、E-3 值全為 "."
# ══════════════════════════════════════════════════════════════

def test_fetch_error_attr_name_is_the_same_in_three_modules():
    """E-3 / E-4 / E-8 三處各自定義 `_FETCH_ERROR_ATTR`（不得新增共用模組），釘住三者同名。"""
    from repositories.fund import nav_metrics
    from repositories.macro import fred, yf
    assert fred._FETCH_ERROR_ATTR == yf._FETCH_ERROR_ATTR == nav_metrics._FETCH_ERROR_ATTR


def test_e3_all_missing_values(_fred, monkeypatch):
    payload = {"observations": [{"date": "2026-01-01", "value": ".", "realtime_start": "2026-01-15"}]}
    monkeypatch.setattr(_fred, "fetch_url", lambda *a, **k: _Resp(payload))
    df, err = _fred.fetch_fred_with_error("SER", "k")
    assert df.empty and "缺值" in err


# ══════════════════════════════════════════════════════════════
# 稽核必修（2026-09-26）：E-5 解析例外不得被當成「不配息」；E-5／E-8 原文帶失敗分類
# ══════════════════════════════════════════════════════════════

def _none_with_kind(kind):
    def _f(*a, **k):
        _set_fail_kind(kind)
        return None
    return _f


def test_e5_page_ok_but_parse_raises_reports_error(_nm, monkeypatch):
    """頁面有取回（200），但 BeautifulSoup 解析拋例外 → 必須交出原因，不能回 ([], None)。"""
    monkeypatch.setattr(_nm, "fetch_url_with_retry", lambda *a, **k: _Resp(text=_DIV_HTML))

    def _bad_soup(*a, **k):
        raise RuntimeError("lxml exploded")
    monkeypatch.setattr(_nm, "BeautifulSoup", _bad_soup)
    out, err = _nm.fetch_div_with_error("FUND01")
    assert out == [] and err and "RuntimeError: lxml exploded" in err


def test_e5_fetch_failure_carries_fail_kind(_nm, monkeypatch):
    monkeypatch.setattr(_nm, "fetch_url_with_retry", _none_with_kind("blocked"))
    _out, err = _nm.fetch_div_with_error("FUND01")
    assert "kind=blocked" in err


def test_e8_fetch_failure_carries_fail_kind(_nm, monkeypatch):
    monkeypatch.setattr(_nm, "fetch_url_with_retry", _none_with_kind("proxy_auth"))
    monkeypatch.setattr(_nm, "_src_cache_files", lambda code: None)
    _s, err = _nm.fetch_nav_with_error("FUND01")
    assert "kind=proxy_auth" in err
    assert "狀態碼見 [proxy] log" not in err


def test_e8_kind_is_consumed_so_no_residue_leaks(_nm, monkeypatch):
    """讀分類用的是「取出即清掉」：讀完之後本執行緒不留殘值。"""
    from infra.proxy import pop_last_fail_kind
    monkeypatch.setattr(_nm, "fetch_url_with_retry", _none_with_kind("not_found"))
    monkeypatch.setattr(_nm, "_src_cache_files", lambda code: None)
    _nm.fetch_nav_with_error("FUND01")
    assert pop_last_fail_kind() == ""


def test_e8_empty_body_without_kind_is_labelled(_nm, monkeypatch):
    """`fetch_url` 成功但內容空白 → 分類為空；原文據實寫出，不編一個分類。"""
    monkeypatch.setattr(_nm, "fetch_url_with_retry", _none_with_kind(""))
    monkeypatch.setattr(_nm, "_src_cache_files", lambda code: None)
    _s, err = _nm.fetch_nav_with_error("FUND01")
    assert "內容為空白" in err
