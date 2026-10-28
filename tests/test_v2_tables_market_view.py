# -*- coding: utf-8 -*-
"""L2 `services/v2_tables/market_view.py`（🌍 市場趨勢唯讀 Data View；BL-0516 批 1）的單元測試（fast lane；不打任何網路）。

L1 一律以替身注入（簽名同 `fetch_yf_close_with_error(ticker, range_)`；FRED 同 `fetch_fred_vintages_with_error`）。涵蓋：VIX 正常／空序列／429（L1 回 error）／
L1 拋例外／全部被收盤規則略過／缺值，以及「無正式來源的 domain 一律資料未備、不帶任何數值」與 provenance 欄位。
"""

from __future__ import annotations

import ast
import copy
import math
import pathlib

import pandas as pd
import pytest

from services.v2_tables import market_indicator as mi
from services.v2_tables import market_view as mv

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_FETCHED = "2026-10-27T06:00:00+00:00"


def _series(dates, values, *, fetched_at=_FETCHED, exchange_tz="Etc/UTC"):
    s = pd.Series(values, index=pd.to_datetime(dates), dtype=float, name="^VIX")
    if fetched_at is not None:
        s.attrs["fetched_at"] = fetched_at
    s.attrs["source"] = "Yahoo:^VIX"
    if exchange_tz is not None:
        s.attrs["exchange_tz"] = exchange_tz
    return s


def _tw_series(dates, values, *, fetched_at=_FETCHED):
    """^TWII 形狀：Yahoo 日 K 時間戳＝台北 09:00（＝UTC 01:00），交易所時區 Asia/Taipei。"""
    idx = pd.to_datetime(dates) + pd.Timedelta(hours=1) if len(dates) else pd.DatetimeIndex([])
    s = pd.Series(values, index=idx, dtype=float, name="^TWII")
    if fetched_at is not None:
        s.attrs["fetched_at"] = fetched_at
    s.attrs["source"] = "Yahoo:^TWII"
    s.attrs["exchange_tz"] = "Asia/Taipei"
    return s


def _gspc_series(dates, values, *, fetched_at=_FETCHED):
    """^GSPC 形狀：Yahoo 日 K 時間戳＝紐約 09:30（＝UTC 13:30 冬令／14:30 夏令），交易所時區 America/New_York。"""
    idx = pd.to_datetime(dates) + pd.Timedelta(hours=13, minutes=30) if len(dates) else pd.DatetimeIndex([])
    s = pd.Series(values, index=idx, dtype=float, name="^GSPC")
    if fetched_at is not None:
        s.attrs["fetched_at"] = fetched_at
    s.attrs["source"] = "Yahoo:^GSPC"
    s.attrs["exchange_tz"] = "America/New_York"
    return s


def _fred_frame(dates, values, *, fetched_at=_FETCHED, extra=None, series="DGS10"):
    """fetch_fred_vintages 形狀：每個觀測日一列現行版次（realtime_end＝9999-12-31）；`extra` 可加修正前的舊版次列。"""
    rows = [{"date": pd.Timestamp(d), "value": v, "realtime_start": pd.Timestamp(d) + pd.Timedelta(days=1),
             "realtime_end": "9999-12-31"} for d, v in zip(dates, values)]
    rows += list(extra or [])
    df = pd.DataFrame(rows, columns=["date", "value", "realtime_start", "realtime_end"])
    if fetched_at is not None:
        df.attrs["fetched_at"] = fetched_at
    df.attrs["source"] = f"FRED:{series}:vintages"
    df.attrs["realtime_floor"] = "2021-10-01"
    return df


class _FredFetch:
    """依 series_id 回不同結果的 FRED 替身；記錄呼叫（金鑰在 args 裡，測試用來斷言傳遞，不印出）。"""

    def __init__(self, by_series):
        self.by_series = by_series
        self.calls = []

    def __call__(self, series_id, api_key, observation_start):
        self.calls.append((series_id, api_key, observation_start))
        result = self.by_series[series_id]
        if isinstance(result, Exception):
            raise result
        return result


def _fred_ok(base10=4.0, base2=3.5, dates=None):
    dates = dates or _weekdays("2026-10-01", "2026-10-23")
    return _FredFetch({"DGS10": (_fred_frame(dates, [base10 + i * 0.01 for i in range(len(dates))]), None),
                       "DGS2": (_fred_frame(dates, [base2 + i * 0.01 for i in range(len(dates))], series="DGS2"), None)})


def _all(fred=None, key="test-key", sp500_result=None, **kw):
    """build_market_view 全部替身（VIX／TAIEX／S&P 500／FRED 各自獨立，不依賴預設走真 L1）。"""
    args = dict(_both(**kw))
    sp = sp500_result or (_gspc_series(_weekdays("2026-10-01", "2026-10-23"),
                                       [6000.0 + i for i in range(17)]), None)
    args.update(fetch_sp500=_Fetch(sp), fetch_fred=fred or _fred_ok(), fred_api_key=key)
    return args


def _both(vix_result=None, taiex_result=None):
    """build_market_view 的兩個替身（VIX 與 TAIEX 各自獨立，不依賴預設走真 L1）。"""
    vix_result = vix_result or (_series(_weekdays("2026-10-01", "2026-10-23"), [16.0] * 17), None)
    taiex_result = taiex_result or (_tw_series(_weekdays("2026-10-01", "2026-10-23"), [23000.0 + i for i in range(17)]), None)
    return {"fetch_vix": _Fetch(vix_result), "fetch_taiex": _Fetch(taiex_result)}


def _weekdays(start, end):
    return [d.strftime("%Y-%m-%d") for d in pd.bdate_range(start, end)]


class _Fetch:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _domain(view, key):
    return next(d for d in view["domains"] if d["domain"] == key)


# ───────────────────────── VIX ─────────────────────────


def test_VIX正常_逐日觀測_最後觀測日_來源_取得時間_單位():
    dates = _weekdays("2026-10-01", "2026-10-23")
    series = _series(dates, [15 + i * 0.1 for i in range(len(dates))])
    fetch = _Fetch((series, None))
    view = mv.build_market_view(fetch_vix=fetch)
    vix = _domain(view, "vix")
    assert vix["status"] == mv.STATE_OK == "ok"
    assert vix["obs_date"] == "2026-10-23"
    assert vix["source"] == "Yahoo:^VIX"
    assert vix["fetched_at"] == _FETCHED
    assert vix["value_unit"] == "index"
    assert [p["obs_date"] for p in vix["points"]] == dates          # 升冪、逐日、沒有多的也沒有少的
    assert all(set(p) == {"obs_date", "value_num"} and math.isfinite(p["value_num"]) for p in vix["points"])
    assert vix["reason"] is None and vix["reason_code"] is None


def test_VIX要5y_與B線不同快取鍵_同一個Yahoo主機冷卻():
    """BL-0517 (3)：舊版「VIX 與 B 線同簽名同快取鍵」的性質已改——本頁 VIX 是 `("^VIX", "5y")`（獨立快取項、獨立請求），
    B 線 `vol_index` 仍是 `("^VIX",)`（見 test_B線vol_index取數不變）。3Y 按鈕因此是真的。"""
    assert mv.VIX_RANGE == "5y"
    fetch = _Fetch((_series(_weekdays("2026-10-01", "2026-10-23"), [16.0] * 17), None))
    mv.build_market_view(fetch_vix=fetch, fetch_taiex=_Fetch((_tw_series([], []), None)))
    assert fetch.calls[0] == (("^VIX", "5y"), {})
    assert fetch.calls[0][0] != ("^VIX",)       # 與 B 線簽名不同 → L1 快取鍵不同（誠實記錄：不再共用快取項）


def test_B線vol_index取數不變_仍是單一ticker位置參數_預設2y_WINDOW_DAYS_MAX_730(monkeypatch):
    """釘住：BL-0517 (3) 只改本頁 VIX 的 range，不動 B 線 `vol_index` 的取數簽名／來源／窗口上限。"""
    from ui_v2.mkt import logic

    calls = []

    def stub(ticker, *a, **k):
        calls.append((ticker, a, k))
        return _series(_weekdays("2026-10-01", "2026-10-23"), [16.0] * 17), None

    monkeypatch.setattr(mi, "fetch_yf_close_with_error", stub)
    monkeypatch.setattr(mi, "fetch_fred_vintages_with_error", lambda *a, **k: (None, "x"))
    mi.build_market_indicator_table(fred_api_key="k")
    assert ("^VIX", (), {}) in calls                           # 只傳 ticker 一個位置參數（預設 2y，快取鍵不變）
    assert not [c for c in calls if c[0] == "^VIX" and c != ("^VIX", (), {})]
    assert mi.INDICATOR_SPECS["vol_index"]["source"] == ("Yahoo", "^VIX")
    assert mi.FRED_LOOKBACK_DAYS == logic.WINDOW_DAYS_MAX == 730


def test_VIX空序列_沒有原因_系統錯誤_原文照回():
    view = mv.build_market_view(fetch_vix=_Fetch((_series([], []), None)))
    vix = _domain(view, "vix")
    assert vix["status"] == mv.STATE_ERROR == "系統錯誤"
    assert vix["reason"] == mi.EMPTY_WITHOUT_REASON
    assert vix["points"] == [] and vix["obs_date"] is None


def test_VIX_429_L1回error_系統錯誤_原文不改_不帶序列():
    text = "Yahoo:^VIX 失敗：HTTP 429 Too Many Requests"
    view = mv.build_market_view(fetch_vix=_Fetch((pd.Series(dtype=float, name="^VIX"), text)))
    vix = _domain(view, "vix")
    assert vix["status"] == mv.STATE_ERROR
    assert vix["reason"] == text
    assert vix["points"] == [] and vix["fetched_at"] is None


def test_VIX_L1拋例外_轉成可見的失敗原文_不吞():
    view = mv.build_market_view(fetch_vix=_Fetch(RuntimeError("boom")))
    vix = _domain(view, "vix")
    assert vix["status"] == mv.STATE_ERROR
    assert vix["reason"] == "RuntimeError: boom"


def test_VIX全部被收盤規則略過_資料未備_帶略過理由_不補值():
    # 唯一一根日 K 就是取得日當天（盤中值）→ 「未收盤」不寫
    series = _series(["2026-10-27"], [20.0])
    view = mv.build_market_view(fetch_vix=_Fetch((series, None)))
    vix = _domain(view, "vix")
    assert vix["status"] == mv.STATE_MISSING == "資料未備"
    assert vix["reason_code"] == mv.REASON_NO_OBSERVATION
    assert "未收盤" in vix["reason"] or "取得日" in vix["reason"]
    assert vix["points"] == [] and vix["obs_date"] is None


def test_VIX缺值_NaN不進序列_也不被補成0():
    dates = _weekdays("2026-10-01", "2026-10-23")
    values = [16.0] * len(dates)
    values[5] = float("nan")
    view = mv.build_market_view(fetch_vix=_Fetch((_series(dates, values), None)))
    vix = _domain(view, "vix")
    assert vix["status"] == mv.STATE_OK
    assert dates[5] not in [p["obs_date"] for p in vix["points"]]       # 缺的就是缺：不出現
    assert 0.0 not in [p["value_num"] for p in vix["points"]]
    assert all(math.isfinite(p["value_num"]) for p in vix["points"])


def test_VIX沒有fetched_at_整批不寫_資料未備_不以現在時間補():
    series = _series(_weekdays("2026-10-01", "2026-10-23"), [16.0] * 17, fetched_at=None)
    vix = _domain(mv.build_market_view(fetch_vix=_Fetch((series, None))), "vix")
    assert vix["status"] == mv.STATE_MISSING
    assert vix["fetched_at"] is None and vix["points"] == []


# ───────────────────────── Missing 結構 ─────────────────────────


def test_固定順序_與_domain_全集():
    view = mv.build_market_view(fetch_vix=_Fetch((_series(_weekdays("2026-10-01", "2026-10-23"), [16.0] * 17), None)))
    assert [d["domain"] for d in view["domains"]] == list(mv.DOMAIN_ORDER)
    assert mv.DOMAIN_ORDER == ("vix", "taiex", "taiex_volume", "market_stats", "sp500", "us10y", "us2y",
                               "nasdaq", "msci_world", "msci_em", "eps_pe_scenario",
                               "implied_trailing_index_earnings")


def test_無正式來源的domain_一律資料未備_不帶任何數值來源或時間():
    view = mv.build_market_view(fetch_vix=_Fetch((_series(_weekdays("2026-10-01", "2026-10-23"), [16.0] * 17), None)))
    missing = [d for d in view["domains"] if d["domain"] not in ("vix", "taiex", "sp500", "us10y", "us2y")]
    assert len(missing) == 7
    for d in missing:
        assert d["status"] == mv.STATE_MISSING, d["domain"]
        assert d["points"] == [], d["domain"]
        assert d["source"] is None and d["fetched_at"] is None and d["obs_date"] is None and d["value_unit"] is None
        assert d["reason_code"] and d["reason"], d["domain"]
    codes = {d["domain"]: d["reason_code"] for d in missing}
    assert not {"taiex", "sp500", "us10y", "us2y"} & set(codes)      # TAIEX 已是真 Data View（DEC-2026-10-27-43），不再是 Missing domain
    assert codes["nasdaq"] == codes["msci_world"] == codes["msci_em"] == mv.REASON_NO_OFFICIAL_SOURCE
    assert codes["eps_pe_scenario"] == mv.REASON_EPS_UNAVAILABLE
    assert codes["implied_trailing_index_earnings"] == mv.REASON_UNDETERMINABLE


def test_沒有拿ETF頂替_說明裡沒有QQQ_SPY_URTH字樣():
    view = mv.build_market_view(fetch_vix=_Fetch((_series(_weekdays("2026-10-01", "2026-10-23"), [16.0] * 17), None)))
    blob = repr(view)
    for token in ("QQQ", "SPY", "URTH", "ACWI", "^IXIC"):
        assert token not in blob, token


def test_每個domain都帶provenance欄位_四態在值域內():
    view = mv.build_market_view(fetch_vix=_Fetch((_series(_weekdays("2026-10-01", "2026-10-23"), [16.0] * 17), None)))
    for d in view["domains"]:
        assert set(d) == {"domain", "status", "reason_code", "reason", "source", "fetched_at", "obs_date",
                          "value_unit", "points"}
        assert d["status"] in mv.STATES
    assert view["provenance"]["readonly"] is True
    assert view["provenance"]["writes_market_indicator"] is False


def test_四態字面值與ui_v2_logic的STATE常數逐字相同():
    from ui_v2.mkt import logic
    assert (mv.STATE_OK, mv.STATE_MISSING, mv.STATE_BIZ, mv.STATE_ERROR) == (
        logic.STATE_OK, logic.STATE_MISSING, logic.STATE_BIZ, logic.STATE_ERROR)


# ───────────────────────── 邊界：唯讀、不動 B 線契約 ─────────────────────────


def test_不改INDICATOR_SPECS_也不寫表():
    before = copy.deepcopy(mi.INDICATOR_SPECS)
    mv.build_market_view(fetch_vix=_Fetch((_series(_weekdays("2026-10-01", "2026-10-23"), [16.0] * 17), None)))
    assert mi.INDICATOR_SPECS == before
    assert list(mi.INDICATOR_SPECS) == ["vol_index", "fx_twd_per_usd", "credit_spread_pct", "term_spread_pct",
                                        "policy_rate_pct", "leading_index", "coincident_index"]


def test_本檔不import_streamlit_ui_v2_網路套件_也沒有sink寫入():
    tree = ast.parse((_ROOT / "services" / "v2_tables" / "market_view.py").read_text(encoding="utf-8"))
    mods = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods.append(node.module or "")
    top = {m.split(".")[0] for m in mods}
    assert top <= {"__future__", "typing", "services", "math", "datetime", "shared"}, top      # 不直接 import L1，經 market_indicator 取同一支
    assert "sink" not in [n.arg for n in ast.walk(tree) if isinstance(n, ast.arg)]


def test_預設走market_indicator的L1屬性_替身換在market_indicator上兩邊一起換(monkeypatch):
    """不傳 fetch_vix 時，用的是 `market_indicator.fetch_yf_close_with_error`（B 線 `vol_index` 同一個屬性）。"""
    calls = []

    def stub(ticker, *a, **k):
        calls.append((ticker, a, k))
        return _series(_weekdays("2026-10-01", "2026-10-23"), [16.0] * 17), None

    monkeypatch.setattr(mi, "fetch_yf_close_with_error", stub)
    view = mv.build_market_view()
    assert calls == [("^VIX", ("5y",), {}), ("^TWII", ("5y",), {}), ("^GSPC", ("5y",), {})]   # 全部同一支 L1，沒有第二套取數；無金鑰不打 FRED
    assert _domain(view, "vix")["status"] == mv.STATE_OK


# ───────────────────────── TAIEX（BL-0518；DEC-2026-10-27-43）─────────────────────────


def test_TAIEX正常_Yahoo_TWII_逐日收盤_來源標示逐字_不是TWSE官方():
    dates = _weekdays("2026-10-01", "2026-10-23")
    values = [23000.0 + i * 10 for i in range(len(dates))]
    fetch = _Fetch((_tw_series(dates, values), None))
    view = mv.build_market_view(fetch_vix=_Fetch((_series(dates, [16.0] * len(dates)), None)), fetch_taiex=fetch)
    t = _domain(view, "taiex")
    assert fetch.calls == [(("^TWII", "5y"), {})]          # 只有 TAIEX 要 5y；VIX 仍是單一位置參數
    assert t["status"] == mv.STATE_OK
    assert t["source"] == "Yahoo Finance (^TWII)" == mv.TAIEX_SOURCE_LABEL
    assert "TWSE" not in t["source"] and "證交所" not in t["source"]
    assert t["obs_date"] == "2026-10-23" and t["fetched_at"] == _FETCHED and t["value_unit"] == "index"
    assert [p["obs_date"] for p in t["points"]] == dates
    assert [p["value_num"] for p in t["points"]] == values
    assert t["reason"] is None and t["reason_code"] is None


def test_TAIEX缺的日子就是沒有點_不補值不補0():
    dates = _weekdays("2026-10-01", "2026-10-23")
    values = [23000.0 + i for i in range(len(dates))]
    values[4] = float("nan")
    view = mv.build_market_view(**_both(taiex_result=(_tw_series(dates, values), None)))
    t = _domain(view, "taiex")
    assert t["status"] == mv.STATE_OK
    assert dates[4] not in [p["obs_date"] for p in t["points"]]
    assert 0.0 not in [p["value_num"] for p in t["points"]]


def test_TAIEX_429_系統錯誤_原文照回_來源標示仍是Yahoo_不帶序列():
    text = "Yahoo:^TWII 失敗：HTTP 429 Too Many Requests"
    view = mv.build_market_view(**_both(taiex_result=(pd.Series(dtype=float, name="^TWII"), text)))
    t = _domain(view, "taiex")
    assert t["status"] == mv.STATE_ERROR and t["reason"] == text
    assert t["points"] == [] and t["fetched_at"] is None and t["obs_date"] is None
    assert _domain(view, "vix")["status"] == mv.STATE_OK        # 兩條獨立：TAIEX 失敗不拖垮 VIX


def test_TAIEX_L1拋例外_轉成可見失敗原文():
    view = mv.build_market_view(**_both(taiex_result=RuntimeError("boom")))
    assert _domain(view, "taiex")["status"] == mv.STATE_ERROR
    assert _domain(view, "taiex")["reason"] == "RuntimeError: boom"


def test_TAIEX全被收盤規則略過_資料未備_不補值():
    # 唯一一根日 K 是取得日（台北 10-27）當天 → 未收盤不寫
    view = mv.build_market_view(**_both(taiex_result=(_tw_series(["2026-10-27"], [23500.0]), None)))
    t = _domain(view, "taiex")
    assert t["status"] == mv.STATE_MISSING and t["reason_code"] == mv.REASON_NO_OBSERVATION
    assert t["points"] == [] and t["obs_date"] is None


def test_變異_成交量_市場統計_PE_EPS_即使TAIEX有資料也維持Missing():
    """TAIEX 資料接入後，客戶明示不得延伸的 domain 必須仍是 Missing：不帶數值、來源、時間，也不借用 ^TWII。"""
    view = mv.build_market_view(**_both())
    assert _domain(view, "taiex")["status"] == mv.STATE_OK
    for key in ("taiex_volume", "market_stats", "eps_pe_scenario", "implied_trailing_index_earnings",
                "nasdaq", "msci_world", "msci_em"):
        d = _domain(view, key)
        assert d["status"] == mv.STATE_MISSING, key
        assert d["points"] == [] and d["source"] is None and d["fetched_at"] is None \
            and d["obs_date"] is None and d["value_unit"] is None, key
    assert _domain(view, "taiex_volume")["reason_code"] == mv.REASON_NO_OFFICIAL_SOURCE
    assert set(mv._MISSING_DOMAINS) == {"taiex_volume", "market_stats", "nasdaq", "msci_world", "msci_em",
                                        "eps_pe_scenario", "implied_trailing_index_earnings"}


def test_TAIEX沿用同一支L1_沒有第二套Yahoo取數_INDICATOR_SPECS沒有TAIEX鍵():
    assert not [k for k in mi.INDICATOR_SPECS if "twii" in k.lower() or "taiex" in k.lower()]
    assert not [spec for spec in mi.INDICATOR_SPECS.values() if "^TWII" in repr(spec)]


def test_TAIEX要5y_VIX也要5y_約4年序列3Y可用_2年序列3Y資料不足():
    """BL-0518／BL-0517：3Y 視窗要有夠長歷史。TAIEX 以 `(^TWII, '5y')`、VIX 以 `(^VIX, '5y')` 取數（B 線 `vol_index` 另測不變）。"""
    from ui_v2.mkt import chart

    assert mv.TAIEX_RANGE == "5y"
    vix_fetch = _Fetch((_series(_weekdays("2026-10-01", "2026-10-23"), [16.0] * 17), None))
    four = _weekdays("2022-10-03", "2026-10-23")          # 約 4 年
    two = _weekdays("2024-10-24", "2026-10-23")           # 約 2 年（舊的預設範圍）
    t_four = _Fetch((_tw_series(four, [20000.0 + i for i in range(len(four))]), None))
    view = mv.build_market_view(fetch_vix=vix_fetch, fetch_taiex=t_four, fetch_sp500=_Fetch((_gspc_series([], []), None)))
    assert vix_fetch.calls == [(("^VIX", "5y"), {})] and t_four.calls == [(("^TWII", "5y"), {})]
    assert chart.availability(_domain(view, "taiex")["points"]) == {"3M": True, "6M": True, "1Y": True, "3Y": True}
    t_two = _Fetch((_tw_series(two, [20000.0 + i for i in range(len(two))]), None))
    view2 = mv.build_market_view(fetch_vix=vix_fetch, fetch_taiex=t_two)
    assert chart.availability(_domain(view2, "taiex")["points"]) == {"3M": True, "6M": True, "1Y": True, "3Y": False}


# ───────────────────────── S&P 500（BL-0517 (1)）─────────────────────────


def test_SP500正常_Yahoo_GSPC_5y_來源標示逐字_單位index_逐日收盤():
    dates = _weekdays("2026-10-01", "2026-10-23")
    values = [6000.0 + i * 5 for i in range(len(dates))]
    fetch = _Fetch((_gspc_series(dates, values), None))
    view = mv.build_market_view(**{**_all(), "fetch_sp500": fetch})
    g = _domain(view, "sp500")
    assert fetch.calls == [(("^GSPC", "5y"), {})] and mv.SP500_RANGE == "5y"
    assert g["status"] == mv.STATE_OK
    assert g["source"] == "Yahoo Finance (^GSPC)" == mv.SP500_SOURCE_LABEL
    assert g["value_unit"] == "index" and g["obs_date"] == "2026-10-23" and g["fetched_at"] == _FETCHED
    assert [p["obs_date"] for p in g["points"]] == dates and [p["value_num"] for p in g["points"]] == values


def test_SP500_429_系統錯誤_原文照回_不拖垮其他domain():
    text = "Yahoo:^GSPC 失敗：HTTP 429 Too Many Requests"
    view = mv.build_market_view(**_all(sp500_result=(pd.Series(dtype=float, name="^GSPC"), text)))
    g = _domain(view, "sp500")
    assert g["status"] == mv.STATE_ERROR and g["reason"] == text and g["points"] == [] and g["obs_date"] is None
    assert _domain(view, "vix")["status"] == _domain(view, "taiex")["status"] == mv.STATE_OK
    assert _domain(view, "us10y")["status"] == mv.STATE_OK


def test_SP500_L1拋例外_空序列_全被略過_缺值():
    assert _domain(mv.build_market_view(**_all(sp500_result=RuntimeError("boom"))), "sp500")["reason"] == "RuntimeError: boom"
    empty = _domain(mv.build_market_view(**_all(sp500_result=(_gspc_series([], []), None))), "sp500")
    assert empty["status"] == mv.STATE_ERROR and empty["reason"] == mi.EMPTY_WITHOUT_REASON
    today_only = _domain(mv.build_market_view(**_all(sp500_result=(_gspc_series(["2026-10-27"], [6100.0]), None))), "sp500")
    assert today_only["status"] == mv.STATE_MISSING and today_only["reason_code"] == mv.REASON_NO_OBSERVATION
    dates = _weekdays("2026-10-01", "2026-10-23")
    vals = [6000.0 + i for i in range(len(dates))]
    vals[3] = float("nan")
    g = _domain(mv.build_market_view(**_all(sp500_result=(_gspc_series(dates, vals), None))), "sp500")
    assert dates[3] not in [p["obs_date"] for p in g["points"]] and 0.0 not in [p["value_num"] for p in g["points"]]


# ───────────────────────── 美債殖利率（BL-0517 (2)）─────────────────────────


def test_殖利率正常_FRED現行版次_單位百分比_來源標示逐字_觀測日不是公布日():
    dates = _weekdays("2026-10-01", "2026-10-23")
    fred = _fred_ok(4.0, 3.5, dates)
    view = mv.build_market_view(**_all(fred=fred))
    for key, label, base in (("us10y", "FRED (DGS10)", 4.0), ("us2y", "FRED (DGS2)", 3.5)):
        d = _domain(view, key)
        assert d["status"] == mv.STATE_OK and d["source"] == label
        assert d["value_unit"] == "%" and d["value_unit"] != "index"        # 單位是百分比，不是價格
        assert [p["obs_date"] for p in d["points"]] == dates                  # 觀測日，不是 realtime_start（觀測日 +1）
        assert d["obs_date"] == "2026-10-23" and d["fetched_at"] == _FETCHED
        assert [p["value_num"] for p in d["points"]] == pytest.approx([base + i * 0.01 for i in range(len(dates))])
    assert [c[0] for c in fred.calls] == ["DGS10", "DGS2"]
    assert mv.US10Y_SERIES == "DGS10" and mv.US2Y_SERIES == "DGS2"


def test_殖利率L1呼叫參數_金鑰與觀測起點_不新增series():
    fred = _fred_ok()
    mv.build_market_view(**_all(fred=fred, key="the-key"))
    assert all(c[1] == "the-key" for c in fred.calls)
    expect = (mv._utc_today() - pd.Timedelta(days=mv.FRED_VIEW_LOOKBACK_DAYS)).isoformat()
    assert {c[2] for c in fred.calls} == {expect}
    assert {c[0] for c in fred.calls} <= {"DGS10", "DGS2"}


def test_殖利率只取現行版次_修正過的觀測日用現行值_不用舊版():
    d1, d2, d3 = "2026-10-01", "2026-10-02", "2026-10-05"
    # 舊版列刻意排在現行版次列「之後」：若實作取「每個觀測日最後一列」就會誤取 3.90 → 本測試會紅
    stale = {"date": pd.Timestamp(d2), "value": 3.90, "realtime_start": pd.Timestamp("2026-10-03"),
             "realtime_end": "2026-10-09"}
    frame = _fred_frame([d1, d2, d3], [4.00, 4.15, 4.20], extra=[stale])
    d = mv.fred_yield_domain_from_l1("us10y", frame, None, source_label=mv.US10Y_SOURCE_LABEL)
    assert {p["obs_date"]: p["value_num"] for p in d["points"]} == {d1: 4.00, d2: 4.15, d3: 4.20}
    assert 3.90 not in [p["value_num"] for p in d["points"]]


def test_殖利率重複現行版次_該日不進序列_理由寫明_不隨便挑一列():
    frame = _fred_frame(["2026-10-01", "2026-10-02"], [4.0, 4.1])
    dup = pd.DataFrame([{"date": pd.Timestamp("2026-10-02"), "value": 9.99, "realtime_start": pd.Timestamp("2026-10-04"),
                         "realtime_end": "9999-12-31"}])
    frame = pd.concat([frame, dup], ignore_index=True)
    frame.attrs.update(fetched_at=_FETCHED, realtime_floor="2021-10-01")
    d = mv.fred_yield_domain_from_l1("us10y", frame, None, source_label="FRED (DGS10)")
    assert [p["obs_date"] for p in d["points"]] == ["2026-10-01"]
    assert 9.99 not in [p["value_num"] for p in d["points"]] and 4.1 not in [p["value_num"] for p in d["points"]]


def test_殖利率沒有現行版次的觀測日_不進序列():
    only_old = [{"date": pd.Timestamp("2026-10-02"), "value": 4.1, "realtime_start": pd.Timestamp("2026-10-03"),
                 "realtime_end": "2026-10-09"}]
    frame = _fred_frame(["2026-10-01"], [4.0], extra=only_old)
    d = mv.fred_yield_domain_from_l1("us10y", frame, None, source_label="FRED (DGS10)")
    assert [p["obs_date"] for p in d["points"]] == ["2026-10-01"]


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf"), None, True, "4.1", "."])
def test_殖利率非有限數值_不是觀測_不補0_不前值填補(bad):
    frame = _fred_frame(["2026-10-01", "2026-10-02", "2026-10-05"], [4.0, bad, 4.2])
    d = mv.fred_yield_domain_from_l1("us10y", frame, None, source_label="FRED (DGS10)")
    assert [p["obs_date"] for p in d["points"]] == ["2026-10-01", "2026-10-05"]
    assert [p["value_num"] for p in d["points"]] == [4.0, 4.2]       # 缺的日子沒有點；不是 0，也不是 4.0 延伸


def test_殖利率全部缺值_資料未備_帶略過理由():
    frame = _fred_frame(["2026-10-01", "2026-10-02"], [float("nan"), float("nan")])
    d = mv.fred_yield_domain_from_l1("us2y", frame, None, source_label="FRED (DGS2)")
    assert d["status"] == mv.STATE_MISSING and d["reason_code"] == mv.REASON_NO_OBSERVATION
    assert "缺值" in d["reason"] and d["points"] == [] and d["obs_date"] is None and d["fetched_at"] is None


def test_殖利率負值是有效觀測_不被當成缺值():
    frame = _fred_frame(["2026-10-01", "2026-10-02"], [-0.10, 0.0])
    d = mv.fred_yield_domain_from_l1("us2y", frame, None, source_label="FRED (DGS2)")
    assert [p["value_num"] for p in d["points"]] == [-0.10, 0.0]       # 0.0 是真實觀測（不是缺值）


def test_殖利率觀測日晚於取得日_不進序列():
    frame = _fred_frame(["2026-10-26", "2026-10-28"], [4.0, 4.1])      # 取得日（UTC）2026-10-27
    d = mv.fred_yield_domain_from_l1("us10y", frame, None, source_label="FRED (DGS10)")
    assert [p["obs_date"] for p in d["points"]] == ["2026-10-26"] and "晚於取得日" not in (d["reason"] or "")


def test_殖利率fetched_at取不到_整批不寫_不以現在時間補():
    for bad in (None, "2026-10-27T06:00:00"):       # 缺、或沒有時區
        frame = _fred_frame(["2026-10-01"], [4.0], fetched_at=bad)
        d = mv.fred_yield_domain_from_l1("us10y", frame, None, source_label="FRED (DGS10)")
        assert d["status"] == mv.STATE_MISSING and d["points"] == [] and d["fetched_at"] is None


def test_殖利率FRED空表_L1回error_L1拋例外_都是系統錯誤_原文照回():
    empty = _fred_frame([], [])
    view = mv.build_market_view(**_all(fred=_FredFetch({"DGS10": (empty, None), "DGS2": (None, "FRED:DGS2 回 200,observations 為空")})))
    assert _domain(view, "us10y")["status"] == mv.STATE_ERROR and _domain(view, "us10y")["reason"] == mi.EMPTY_WITHOUT_REASON
    assert _domain(view, "us2y")["reason"] == "FRED:DGS2 回 200,observations 為空"
    view = mv.build_market_view(**_all(fred=_FredFetch({"DGS10": RuntimeError("boom"), "DGS2": (None, "HTTP 429 Too Many Requests")})))
    assert _domain(view, "us10y")["reason"] == "RuntimeError: boom"
    assert _domain(view, "us2y")["status"] == mv.STATE_ERROR and _domain(view, "us2y")["reason"] == "HTTP 429 Too Many Requests"
    assert _domain(view, "us10y")["points"] == [] and _domain(view, "us10y")["source"] == "FRED (DGS10)"
    assert _domain(view, "vix")["status"] == _domain(view, "sp500")["status"] == mv.STATE_OK


@pytest.mark.parametrize("key", [None, "", "   "])
def test_缺金鑰_兩個殖利率系統錯誤_原文是MISSING_FRED_API_KEY_不打L1(key):
    fred = _fred_ok()
    view = mv.build_market_view(**_all(fred=fred, key=key))
    for k in ("us10y", "us2y"):
        d = _domain(view, k)
        assert d["status"] == mv.STATE_ERROR and d["reason"] == mi.MISSING_FRED_API_KEY == "未設定 FRED_API_KEY"
        assert d["points"] == []
    assert fred.calls == []
    assert _domain(view, "sp500")["status"] == mv.STATE_OK              # 缺 FRED 金鑰不影響 Yahoo 的 domain


def test_金鑰不進回傳結構_也不進任何domain欄位():
    secret = "SECRET-KEY-abc123"
    view = mv.build_market_view(**_all(key=secret))
    assert secret not in repr(view)
    view = mv.build_market_view(**_all(fred=_FredFetch({"DGS10": (None, "HTTP 500"), "DGS2": (None, "HTTP 500")}), key=secret))
    assert secret not in repr(view)


def test_預設走market_indicator的FRED屬性_替身換在market_indicator上(monkeypatch):
    calls = []

    def stub(series_id, api_key, observation_start):
        calls.append((series_id, api_key))
        return _fred_frame(_weekdays("2026-10-01", "2026-10-23"), [4.0] * 17, series=series_id), None

    monkeypatch.setattr(mi, "fetch_fred_vintages_with_error", stub)
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", lambda t, *a, **k: (_series(_weekdays("2026-10-01", "2026-10-23"), [16.0] * 17), None))
    view = mv.build_market_view(fred_api_key="k")
    assert calls == [("DGS10", "k"), ("DGS2", "k")]
    assert _domain(view, "us10y")["status"] == mv.STATE_OK


def test_呼叫順序_VIX先_TAIEX_SP500_FRED10Y_FRED2Y_B線由L3先呼叫():
    order = []

    def yf(t, r):
        order.append(t)
        return _series(_weekdays("2026-10-01", "2026-10-23"), [16.0] * 17), None

    def fr(sid, k, o):
        order.append(sid)
        return _fred_frame(_weekdays("2026-10-01", "2026-10-23"), [4.0] * 17), None

    mv.build_market_view(fetch_vix=yf, fetch_fred=fr, fred_api_key="k")
    assert order == ["^VIX", "^TWII", "^GSPC", "DGS10", "DGS2"]


def test_變異_新domain換成錯誤或空_既有Missing七個domain完全不變():
    base = mv.build_market_view(**_all())
    bad = mv.build_market_view(**_all(sp500_result=RuntimeError("x"), fred=_FredFetch({"DGS10": RuntimeError("y"), "DGS2": (None, "z")})))
    for key in ("taiex_volume", "market_stats", "nasdaq", "msci_world", "msci_em", "eps_pe_scenario",
                "implied_trailing_index_earnings"):
        assert _domain(bad, key) == _domain(base, key), key
        assert _domain(bad, key)["status"] == mv.STATE_MISSING and _domain(bad, key)["points"] == []


def test_INDICATOR_SPECS沒有新鍵_B線七鍵凍結_沒有SP500或DGS10_DGS2新鍵():
    assert list(mi.INDICATOR_SPECS) == ["vol_index", "fx_twd_per_usd", "credit_spread_pct", "term_spread_pct",
                                        "policy_rate_pct", "leading_index", "coincident_index"]
    assert not [spec for spec in mi.INDICATOR_SPECS.values() if "^GSPC" in repr(spec) or "DGS" in repr(spec)]
