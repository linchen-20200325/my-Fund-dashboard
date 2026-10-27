# -*- coding: utf-8 -*-
"""L2 `services/v2_tables/market_view.py`（🌍 市場趨勢唯讀 Data View；BL-0516 批 1）的單元測試（fast lane；不打任何網路）。

L1 一律以替身注入（簽名同 `fetch_yf_close_with_error(ticker)`）。涵蓋：VIX 正常／空序列／429（L1 回 error）／
L1 拋例外／全部被收盤規則略過／缺值，以及「無正式來源的 domain 一律資料未備、不帶任何數值」與 provenance 欄位。
"""

from __future__ import annotations

import ast
import copy
import math
import pathlib

import pandas as pd

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


def test_VIX只用ticker一個位置參數呼叫L1_與B線同一個快取鍵():
    fetch = _Fetch((_series(_weekdays("2026-10-01", "2026-10-23"), [16.0] * 17), None))
    mv.build_market_view(fetch_vix=fetch)
    assert fetch.calls == [(("^VIX",), {})]


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
    assert mv.DOMAIN_ORDER == ("vix", "taiex", "taiex_volume", "market_stats", "nasdaq", "msci_world", "msci_em",
                               "eps_pe_scenario", "implied_trailing_index_earnings")


def test_無正式來源的domain_一律資料未備_不帶任何數值來源或時間():
    view = mv.build_market_view(fetch_vix=_Fetch((_series(_weekdays("2026-10-01", "2026-10-23"), [16.0] * 17), None)))
    missing = [d for d in view["domains"] if d["domain"] != "vix"]
    assert len(missing) == 8
    for d in missing:
        assert d["status"] == mv.STATE_MISSING, d["domain"]
        assert d["points"] == [], d["domain"]
        assert d["source"] is None and d["fetched_at"] is None and d["obs_date"] is None and d["value_unit"] is None
        assert d["reason_code"] and d["reason"], d["domain"]
    codes = {d["domain"]: d["reason_code"] for d in missing}
    assert codes["taiex"] == mv.REASON_SOURCE_PENDING
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
    assert top <= {"__future__", "typing", "services"}, top      # 不直接 import L1，經 market_indicator 取同一支
    assert "sink" not in [n.arg for n in ast.walk(tree) if isinstance(n, ast.arg)]


def test_預設走market_indicator的L1屬性_替身換在market_indicator上兩邊一起換(monkeypatch):
    """不傳 fetch_vix 時，用的是 `market_indicator.fetch_yf_close_with_error`（B 線 `vol_index` 同一個屬性）。"""
    calls = []

    def stub(ticker, *a, **k):
        calls.append((ticker, a, k))
        return _series(_weekdays("2026-10-01", "2026-10-23"), [16.0] * 17), None

    monkeypatch.setattr(mi, "fetch_yf_close_with_error", stub)
    view = mv.build_market_view()
    assert calls == [("^VIX", (), {})]
    assert _domain(view, "vix")["status"] == mv.STATE_OK
