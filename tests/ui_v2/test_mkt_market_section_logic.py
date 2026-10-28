# -*- coding: utf-8 -*-
"""🌍 市場趨勢區段的文案與模型（`ui_v2/mkt/market_section.py`）純函式測試（fast lane；不需要 streamlit）。

Missing 文案**逐字**斷言（客戶 2026-10-27 派工指定）；市場結論只列狀態、無偏多偏空與總分；新鮮度只顯示日期與經過天數。
"""

from __future__ import annotations

import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from ui_v2.mkt import chart, logic, market_section as ms  # noqa: E402


def _dom(domain, status="資料未備", **kw):
    base = {"domain": domain, "status": status, "reason_code": None, "reason": None, "source": None,
            "fetched_at": None, "obs_date": None, "value_unit": None, "points": []}
    base.update(kw)
    return base


def _points(start="2024-10-24", end="2026-10-23"):
    from datetime import date, timedelta
    d, out = date.fromisoformat(start), []
    while d <= date.fromisoformat(end):
        if d.weekday() < 5:
            out.append({"obs_date": d.isoformat(), "value_num": 16.0 + (d.toordinal() % 7) * 0.1})
        d += timedelta(days=1)
    return out


def _taiex_ok(points=None):
    return _dom("taiex", "ok", source="Yahoo Finance (^TWII)", fetched_at="2026-10-27T06:00:00+00:00",
                obs_date="2026-10-23", value_unit="index", points=points if points is not None else _points())


def _sp500_ok(points=None):
    return _dom("sp500", "ok", source="Yahoo Finance (^GSPC)", fetched_at="2026-10-27T06:00:00+00:00",
                obs_date="2026-10-23", value_unit="index", points=points if points is not None else _points())


def _yield_points(start="2024-10-24", end="2026-10-23"):
    return [{"obs_date": p["obs_date"], "value_num": 4.0 + (i % 9) * 0.01}
            for i, p in enumerate(_points(start, end))]


def _yield_ok(key, label, points=None):
    return _dom(key, "ok", source=label, fetched_at="2026-10-27T06:00:00+00:00",
                obs_date="2026-10-23", value_unit="%", points=points if points is not None else _yield_points())


def _view(vix=None, taiex=None, sp500=None, us10y=None, us2y=None):
    vix = vix or _dom("vix", "ok", source="Yahoo:^VIX", fetched_at="2026-10-27T06:00:00+00:00",
                      obs_date="2026-10-23", value_unit="index", points=_points())
    return {"domains": [
        vix,
        taiex or _taiex_ok(),
        _dom("taiex_volume", reason_code="no_official_source", reason="x"),
        _dom("market_stats", reason_code="no_official_source", reason="x"),
        sp500 or _sp500_ok(),
        us10y or _yield_ok("us10y", "FRED (DGS10)"),
        us2y or _yield_ok("us2y", "FRED (DGS2)"),
        _dom("nasdaq", reason_code="no_official_source", reason="x"),
        _dom("msci_world", reason_code="no_official_source", reason="x"),
        _dom("msci_em", reason_code="no_official_source", reason="x"),
        _dom("eps_pe_scenario", reason_code="eps_forecast_unavailable", reason="x"),
        _dom("implied_trailing_index_earnings", reason_code="undeterminable", reason="x"),
    ], "provenance": {}}


# ───────────────────────── 逐字文案 ─────────────────────────


def test_固定文案逐字():
    assert ms.TEXT_EPS_PE_MISSING == "⬜ EPS 預估資料未取得，無法計算正式指數情境"
    assert ms.TEXT_IMPLIED_UNDETERMINABLE == "⬜ 無法判定"
    assert ms.TEXT_NO_CONCLUSION == "暫無完整市場綜合判定（缺正式 aggregation rule）"
    assert not hasattr(ms, "TEXT_TAIEX_PENDING")        # BL-0518 已裁示，「資料來源待確認」退役
    assert ms.TEXT_PERIOD_RETURN_UNDETERMINABLE == "⬜ 無法判定"
    assert "目前沒有正式資料來源" in ms.TEXT_INTL_MISSING and "Missing" in ms.TEXT_INTL_MISSING \
        and "Data Gap" in ms.TEXT_INTL_MISSING
    assert "Data Gap" in ms.TEXT_DATA_GAP
    assert "⬜ 門檻待裁示" in ms.TEXT_FRESHNESS_THRESHOLD
    assert ms.TEXT_GAP_NOTE == "圓點為實際觀測日；相鄰觀測之間的連線不代表中間日有資料；缺值日不補值"
    assert chart.TEXT_INSUFFICIENT == "資料不足以呈現此期間"


def test_Missing_domain用到的文案():
    view = _view()
    by = ms.domain_by_key(view)
    assert ms.missing_copy(by["eps_pe_scenario"]) == "⬜ EPS 預估資料未取得，無法計算正式指數情境"
    assert ms.missing_copy(by["implied_trailing_index_earnings"]) == "⬜ 無法判定"
    assert "taiex" not in ms._MISSING_COPY
    for key in ("nasdaq", "msci_world", "msci_em"):
        assert ms.missing_copy(by[key]) == ms.TEXT_INTL_MISSING
    for key in ("taiex_volume", "market_stats"):
        assert ms.missing_copy(by[key]) == ms.TEXT_DATA_GAP


def test_Missing文案只在資料未備時套用_其他狀態照狀態字面_不冒用():
    d = _dom("nasdaq", "ok", obs_date="2026-10-23")
    assert ms.missing_copy(d) == "有資料（2026-10-23）"
    e = _dom("nasdaq", "系統錯誤")
    assert ms.missing_copy(e) == "⛔ 取數失敗"


def test_國際市場不拿ETF頂替_標籤只有三個指數名():
    assert ms.LABELS["nasdaq"] == "NASDAQ" and ms.LABELS["msci_world"] == "MSCI World" \
        and ms.LABELS["msci_em"] == "MSCI EM"
    blob = repr(ms.section_strings(_view(), "1Y"))
    for token in ("QQQ", "SPY", "URTH", "ACWI", "IXIC"):
        assert token not in blob


# ───────────────────────── 市場結論 ─────────────────────────


def test_市場結論_一句固定話_加各domain狀態列_只列狀態():
    model = ms.conclusion_model(_view())
    assert model["text"] == "暫無完整市場綜合判定（缺正式 aggregation rule）"
    assert [r["domain"] for r in model["rows"]] == [d["domain"] for d in _view()["domains"]]
    assert model["rows"][0]["status_text"] == "有資料（2026-10-23）"
    assert model["rows"][1]["domain"] == "taiex" and model["rows"][1]["status_text"] == "有資料（2026-10-23）"
    assert [r["domain"] for r in model["rows"][4:7]] == ["sp500", "us10y", "us2y"]
    assert all(r["status_text"] == "有資料（2026-10-23）" for r in model["rows"][4:7])    # 新 domain 列的是真實狀態
    missing_rows = [r for r in model["rows"] if r["domain"] not in ("vix", "taiex", "sp500", "us10y", "us2y")]
    assert len(missing_rows) == 7 and all(r["status_text"] == "⬜ 資料未備" for r in missing_rows)
    assert set(model["rows"][0]) == {"domain", "label", "status", "status_text", "tone"}   # 沒有分數欄


def test_市場結論無偏多偏空_無總分_無風險分級():
    strings = ms.section_strings(_view(), "1Y")
    for word in ("偏多", "偏空", "中性偏", "看多", "看空", "總分", "風險分級", "低風險", "高風險", "composite"):
        assert not [s for s in strings if word in s], word


def test_VIX系統錯誤_一般畫面只寫取數失敗_原文走原始訊息():
    bad = _dom("vix", "系統錯誤", reason="Yahoo:^VIX 失敗：HTTP 429")
    view = _view(bad)
    assert ms.conclusion_model(view)["rows"][0]["status_text"] == "⛔ 取數失敗"
    model = ms.vix_model(bad, "1Y")
    assert model["message"] == "⛔ 取數失敗"
    assert "429" not in "".join(ms.section_strings(view, "1Y"))
    raws = ms.raw_entries(view)
    assert [r["text"] for r in raws] == ["⛔ 取數失敗：Yahoo:^VIX 失敗：HTTP 429"]
    assert model["spec"] is None and not any(model["availability"].values())


def test_VIX資料未備_卡上寫原因_沒有圖():
    miss = _dom("vix", "資料未備", reason_code="no_closed_observation", reason="同一觀測日重複 2 筆不寫")
    model = ms.vix_model(miss, "1Y")
    assert model["spec"] is None
    assert model["message"] == "⬜ 資料未備：同一觀測日重複 2 筆不寫"


# ───────────────────────── VIX 圖卡模型 ─────────────────────────


def test_VIX圖卡_預設1Y可畫_3Y顯示資料不足_按鈕標示不足():
    vix = ms.domain_by_key(_view())["vix"]
    one = ms.vix_model(vix, "1Y")
    assert one["spec"] is not None and one["message"] is None
    assert one["slice"]["window_start"] == "2025-10-23"
    three = ms.vix_model(vix, "3Y")
    assert three["spec"] is None and three["message"] == "資料不足以呈現此期間"
    assert one["availability"] == {"3M": True, "6M": True, "1Y": True, "3Y": False}
    assert ms.period_option_label("3Y", False) == "3Y（資料不足）"
    assert ms.period_option_label("1Y", True) == "1Y"


def test_VIX圖卡_標資料日期_來源_取得時間_新鮮度_門檻待裁示():
    lines = ms.vix_model(ms.domain_by_key(_view())["vix"], "1Y")["caption_lines"]
    assert lines[0] == "資料日期（最後觀測日）2026-10-23　延遲 4 日"
    assert lines[1] == "來源 Yahoo:^VIX　取得時間 2026-10-27 14:00（UTC+8）"
    assert ms.TEXT_FRESHNESS_THRESHOLD in lines


def test_新鮮度_沿用logic_延遲日數_台北日期_不判新舊():
    # 取得時間 2026-10-27T20:00Z ＝ 台北 10-28 04:00 → 台北日期 10-28，延遲 5 日（用台北日期算，同 live.DISPLAY_TZ）
    assert ms.freshness_text("2026-10-23", "2026-10-27T20:00:00+00:00") == "延遲 5 日"
    assert ms.freshness_text("2026-10-27", "2026-10-27T06:00:00+00:00") == "經過 0 日"
    assert ms.freshness_text("2026-10-28", "2026-10-27T06:00:00+00:00") == "未定義"
    for text in ("延遲 5 日", "經過 0 日", "未定義"):
        assert not any(w in text for w in ("新鮮", "過期", "陳舊", "正常", "良好"))


def test_新鮮度沒有顏色欄_也沒有自創門檻():
    model = ms.vix_model(ms.domain_by_key(_view())["vix"], "1Y")
    assert "tone" not in model and "color" not in model
    import ast
    import inspect
    import textwrap
    tree = ast.parse(textwrap.dedent(inspect.getsource(ms.freshness_text)))
    ops = {type(op) for node in ast.walk(tree) if isinstance(node, ast.Compare) for op in node.ops}
    assert ops <= {ast.Eq, ast.Is, ast.IsNot}, ops      # 沒有自己的 < > 比大小門檻；級距判定全在 logic


def test_全部面向使用者的字串_過禁詞掃描_且無目標價_預測():
    for period in chart.PERIODS:
        strings = ms.section_strings(_view(), period)
        assert strings
        assert logic.scan_forbidden(strings) == {}, period
        for word in ("目標價", "預測", "情境點位", "買進", "賣出"):
            assert not [s for s in strings if word in s], (period, word)


# ───────────────────────── TAIEX（BL-0518）─────────────────────────


def test_TAIEX圖卡_預設1Y可畫_3Y不足_來源標示逐字_標資料日期與經過天數():
    t = ms.domain_by_key(_view())["taiex"]
    one = ms.taiex_model(t, "1Y")
    assert one["spec"] is not None and one["message"] is None and one["label"] == "台股加權指數（TAIEX）"
    assert one["availability"] == {"3M": True, "6M": True, "1Y": True, "3Y": False}
    assert one["caption_lines"][0] == "資料日期（最後觀測日）2026-10-23　延遲 4 日"
    assert one["caption_lines"][1] == "來源 Yahoo Finance (^TWII)　取得時間 2026-10-27 14:00（UTC+8）"
    assert ms.taiex_model(t, "3Y")["spec"] is None and ms.taiex_model(t, "3Y")["message"] == "資料不足以呈現此期間"
    assert "TWSE" not in "".join(one["caption_lines"])


def test_期間漲跌_只用已觀測點_末筆比首筆():
    pts = [{"obs_date": "2026-10-01", "value_num": 100.0}, {"obs_date": "2026-10-02", "value_num": None},
           {"obs_date": "2026-10-05", "value_num": 110.0}, {"obs_date": "2026-10-06", "value_num": 105.0}]
    r = ms.period_return(pts)
    assert r["status"] == "ok" and r["pct"] == pytest.approx(5.0)
    assert r["text"] == "期間漲跌 +5.0%（2026-10-01 至 2026-10-06，收盤價）"
    down = ms.period_return([{"obs_date": "2026-10-01", "value_num": 200.0},
                             {"obs_date": "2026-10-02", "value_num": 190.0}])
    assert down["text"].startswith("期間漲跌 -5.0%")
    for text in (r["text"], down["text"]):
        assert logic.scan_forbidden([text]) == {}


@pytest.mark.parametrize("pts", [
    [],
    [{"obs_date": "2026-10-01", "value_num": 100.0}],
    [{"obs_date": "2026-10-01", "value_num": 100.0}, {"obs_date": "2026-10-02", "value_num": None}],
    [{"obs_date": "2026-10-01", "value_num": 0.0}, {"obs_date": "2026-10-02", "value_num": 5.0}],
])
def test_期間漲跌_不足兩點或起點非正_無法判定_不補值(pts):
    r = ms.period_return(pts)
    assert r == {"status": "undeterminable", "pct": None, "first_obs": None, "last_obs": None,
                 "text": "⬜ 無法判定"}


_NAN, _INF = float("nan"), float("inf")


@pytest.mark.parametrize("pts", [
    [{"obs_date": "2026-10-01", "value_num": _NAN}, {"obs_date": "2026-10-02", "value_num": 10.0}],
    [{"obs_date": "2026-10-01", "value_num": 10.0}, {"obs_date": "2026-10-02", "value_num": _NAN}],
    [{"obs_date": "2026-10-01", "value_num": 10.0}, {"obs_date": "2026-10-02", "value_num": _INF}],
    [{"obs_date": "2026-10-01", "value_num": -_INF}, {"obs_date": "2026-10-02", "value_num": 10.0}],
    [{"obs_date": "2026-10-01", "value_num": True}, {"obs_date": "2026-10-02", "value_num": 10.0}],
    [{"obs_date": "2026-10-01", "value_num": 10.0}, {"obs_date": "2026-10-02", "value_num": False}],
])
def test_期間漲跌_非有限數與布林視為未觀測_無法判定(pts):
    r = ms.period_return(pts)
    assert r == {"status": "undeterminable", "pct": None, "first_obs": None, "last_obs": None,
                 "text": "⬜ 無法判定"}


def test_期間漲跌_中間夾NaN或bool_略過該點_其餘照算():
    pts = [{"obs_date": "2026-10-01", "value_num": 100.0}, {"obs_date": "2026-10-02", "value_num": _NAN},
           {"obs_date": "2026-10-05", "value_num": True}, {"obs_date": "2026-10-06", "value_num": 110.0}]
    r = ms.period_return(pts)
    assert r["status"] == "ok" and r["pct"] == pytest.approx(10.0)
    assert r["text"] == "期間漲跌 +10.0%（2026-10-01 至 2026-10-06，收盤價）"


def test_TAIEX圖卡_期間漲跌跟著所選窗口走():
    t = _taiex_ok(points=[{"obs_date": d, "value_num": 100.0 + i} for i, d in
                          enumerate(p["obs_date"] for p in _points())])
    three_m = ms.taiex_model(t, "3M")["period_return"]
    six_m = ms.taiex_model(t, "6M")["period_return"]
    assert three_m["status"] == six_m["status"] == "ok"
    assert three_m["first_obs"] > six_m["first_obs"]          # 窗口短 → 起點較晚


def test_VIX圖卡沒有期間漲跌_只有TAIEX有():
    assert ms.vix_model(ms.domain_by_key(_view())["vix"], "1Y")["period_return"] is None
    assert ms.taiex_model(ms.domain_by_key(_view())["taiex"], "1Y")["period_return"]["status"] == "ok"


def test_TAIEX系統錯誤_一般畫面只寫取數失敗_原文走原始訊息():
    bad = _dom("taiex", "系統錯誤", source="Yahoo Finance (^TWII)", reason="Yahoo:^TWII 失敗：HTTP 429")
    view = _view(taiex=bad)
    model = ms.taiex_model(bad, "1Y")
    assert model["message"] == "⛔ 取數失敗" and model["spec"] is None and model["period_return"] is None
    assert ms.conclusion_model(view)["rows"][1]["status_text"] == "⛔ 取數失敗"
    assert "429" not in "".join(ms.section_strings(view, "1Y"))
    assert [r["text"] for r in ms.raw_entries(view)] == ["⛔ 取數失敗：Yahoo:^TWII 失敗：HTTP 429"]


def test_成交量_市場統計_PE_EPS_Missing文案不因TAIEX接入而改():
    by = ms.domain_by_key(_view())
    assert ms.missing_copy(by["taiex_volume"]) == ms.TEXT_DATA_GAP
    assert ms.missing_copy(by["market_stats"]) == ms.TEXT_DATA_GAP
    assert ms.missing_copy(by["eps_pe_scenario"]) == "⬜ EPS 預估資料未取得，無法計算正式指數情境"
    assert ms.missing_copy(by["implied_trailing_index_earnings"]) == "⬜ 無法判定"
    assert set(ms._MISSING_COPY) == {"taiex_volume", "market_stats", "nasdaq", "msci_world", "msci_em",
                                     "eps_pe_scenario", "implied_trailing_index_earnings"}


# ───────────────────────── S&P 500／美債殖利率（BL-0517）─────────────────────────


def test_BL0517新文案_標籤與註記_總管擬待覆核():
    assert ms.LABELS["sp500"] == "標普 500 指數（S&P 500）"
    assert ms.LABELS["us10y"] == "美國 10 年期公債殖利率"
    assert ms.LABELS["us2y"] == "美國 2 年期公債殖利率"
    assert ms.TEXT_FRED_OBS_NOTE == "資料日期為 FRED 觀測日（不是公布日）；單位為百分比（%），不是價格"
    assert "現行版次" not in ms.TEXT_FRED_OBS_NOTE and "版次" not in ms.TEXT_FRED_OBS_NOTE   # 不再讀 vintage，該句不再為真


def test_SP500圖卡_同TAIEX規格_期間漲跌是百分比報酬_來源標示逐字():
    d = ms.domain_by_key(_view())["sp500"]
    one = ms.sp500_model(d, "1Y")
    assert one["spec"] is not None and one["label"] == "標普 500 指數（S&P 500）"
    assert one["availability"] == {"3M": True, "6M": True, "1Y": True, "3Y": False}
    assert one["caption_lines"][1] == "來源 Yahoo Finance (^GSPC)　取得時間 2026-10-27 14:00（UTC+8）"
    assert one["period_return"]["text"].startswith("期間漲跌 ") and "%（" in one["period_return"]["text"]
    assert ms.TEXT_FRED_OBS_NOTE not in one["caption_lines"]      # 價格卡不帶殖利率註記
    assert ms.sp500_model(d, "3Y")["message"] == "資料不足以呈現此期間"


def test_SP500系統錯誤_一般畫面只寫取數失敗_原文走原始訊息():
    bad = _dom("sp500", "系統錯誤", source="Yahoo Finance (^GSPC)", reason="Yahoo:^GSPC 失敗：HTTP 429")
    view = _view(sp500=bad)
    model = ms.sp500_model(bad, "1Y")
    assert model["message"] == "⛔ 取數失敗" and model["spec"] is None and model["period_return"] is None
    assert "429" not in "".join(ms.section_strings(view, "1Y"))
    assert [r["text"] for r in ms.raw_entries(view)] == ["⛔ 取數失敗：Yahoo:^GSPC 失敗：HTTP 429"]


def test_殖利率圖卡_單位是百分比_期間指標是百分點pp_不是百分比報酬():
    pts = [{"obs_date": "2026-10-01", "value_num": 4.00}, {"obs_date": "2026-10-02", "value_num": None},
           {"obs_date": "2026-10-05", "value_num": 4.10}, {"obs_date": "2026-10-06", "value_num": 4.15}]
    r = ms.period_change_pp(pts)
    assert r["status"] == "ok" and r["kind"] == "pp" and r["pct"] is None
    assert r["pp"] == pytest.approx(0.15)                          # 4.15 - 4.00，不是 +3.75%
    assert r["text"] == "期間變動 +0.15 個百分點（pp）（2026-10-01 至 2026-10-06，FRED 觀測值）"
    assert "%" not in r["text"]                                      # 沒有任何「百分比報酬」字樣
    down = ms.period_change_pp([{"obs_date": "2026-10-01", "value_num": 4.20},
                                {"obs_date": "2026-10-02", "value_num": 3.95}])
    assert down["text"].startswith("期間變動 -0.25 個百分點")
    assert logic.scan_forbidden([r["text"], down["text"]]) == {}


def test_殖利率pp_起點為0或負值也有定義_不像百分比報酬會拒絕():
    r = ms.period_change_pp([{"obs_date": "2026-10-01", "value_num": 0.0},
                             {"obs_date": "2026-10-02", "value_num": 0.30}])
    assert r["status"] == "ok" and r["pp"] == pytest.approx(0.30)
    n = ms.period_change_pp([{"obs_date": "2026-10-01", "value_num": -0.10},
                             {"obs_date": "2026-10-02", "value_num": 0.20}])
    assert n["pp"] == pytest.approx(0.30)
    assert ms.period_return([{"obs_date": "2026-10-01", "value_num": 0.0},
                             {"obs_date": "2026-10-02", "value_num": 0.30}])["status"] == "undeterminable"


@pytest.mark.parametrize("pts", [
    [],
    [{"obs_date": "2026-10-01", "value_num": 4.0}],
    [{"obs_date": "2026-10-01", "value_num": 4.0}, {"obs_date": "2026-10-02", "value_num": None}],
    [{"obs_date": "2026-10-01", "value_num": _NAN}, {"obs_date": "2026-10-02", "value_num": 4.0}],
    [{"obs_date": "2026-10-01", "value_num": 4.0}, {"obs_date": "2026-10-02", "value_num": _INF}],
    [{"obs_date": "2026-10-01", "value_num": True}, {"obs_date": "2026-10-02", "value_num": 4.0}],
])
def test_殖利率pp_不足兩點或非有限數或布林_無法判定_不補值(pts):
    assert ms.period_change_pp(pts) == {"status": "undeterminable", "kind": "pp", "pp": None, "pct": None,
                                        "first_obs": None, "last_obs": None, "text": "⬜ 無法判定"}


def test_殖利率圖卡_單位標示_觀測日註記_來源逐字_不宣稱公布延遲():
    by = ms.domain_by_key(_view())
    for fn, key, label, short in ((ms.us10y_model, "us10y", "FRED (DGS10)", "US10Y"),
                                  (ms.us2y_model, "us2y", "FRED (DGS2)", "US2Y")):
        m = fn(by[key], "1Y")
        assert m["spec"] is not None
        assert m["caption_lines"][1] == f"來源 {label}　取得時間 2026-10-27 14:00（UTC+8）"
        assert ms.TEXT_FRED_OBS_NOTE in m["caption_lines"]
        assert m["period_return"]["kind"] == "pp"
        enc = m["spec"]["layer"][0]["encoding"]["y"]
        assert enc["title"] == "殖利率（%）"                          # 軸標題寫百分比，不是價格「指數點位」
        assert "指數點位" not in "".join(chart.spec_strings(m["spec"]))
        assert m["spec"]["layer"][2]["data"]["values"][0]["text"].startswith(f"{short} ")
        blob = "".join(m["caption_lines"]) + m["period_return"]["text"]
        for word in ("公布延遲", "發布延遲", "T+", "落後"):
            assert word not in blob
        assert m["availability"] == {"3M": True, "6M": True, "1Y": True, "3Y": False}


def test_殖利率系統錯誤_缺金鑰_一般畫面只寫取數失敗_原文走原始訊息():
    bad = _dom("us10y", "系統錯誤", source="FRED (DGS10)", reason="未設定 FRED_API_KEY")
    view = _view(us10y=bad)
    m = ms.us10y_model(bad, "1Y")
    assert m["message"] == "⛔ 取數失敗" and m["spec"] is None and m["period_return"] is None
    assert not any("FRED_API_KEY" in s for s in ms.section_strings(view, "1Y"))
    assert [r["text"] for r in ms.raw_entries(view)] == ["⛔ 取數失敗：未設定 FRED_API_KEY"]
    assert ms.conclusion_model(view)["rows"][5]["status_text"] == "⛔ 取數失敗"
    assert ms.conclusion_model(view)["text"] == "暫無完整市場綜合判定（缺正式 aggregation rule）"


def test_殖利率資料未備_卡上寫原因_沒有圖():
    miss = _dom("us2y", "資料未備", reason_code="no_closed_observation", reason="現行版次的值為缺值 3 個觀測日不寫")
    m = ms.us2y_model(miss, "1Y")
    assert m["spec"] is None and m["message"] == "⬜ 資料未備：現行版次的值為缺值 3 個觀測日不寫"


def test_NASDAQ_MSCI仍是Missing_不被SP500或殖利率頂替():
    by = ms.domain_by_key(_view())
    for key in ("nasdaq", "msci_world", "msci_em"):
        assert ms.missing_copy(by[key]) == ms.TEXT_INTL_MISSING
        assert by[key]["points"] == []
    blob = repr(ms.section_strings(_view(), "1Y"))
    for token in ("QQQ", "SPY", "URTH", "ACWI", "IXIC", "^GSPC 代"):
        assert token not in blob


def test_Mutation_把所有新domain換成系統錯誤_既有Missing文案與結論句不變():
    bad = {k: _dom(k, "系統錯誤", reason=f"{k} boom") for k in ("sp500", "us10y", "us2y")}
    view = _view(**bad)
    by = ms.domain_by_key(view)
    assert ms.missing_copy(by["eps_pe_scenario"]) == ms.TEXT_EPS_PE_MISSING
    assert ms.missing_copy(by["nasdaq"]) == ms.TEXT_INTL_MISSING
    assert ms.conclusion_model(view)["text"] == ms.TEXT_NO_CONCLUSION
    assert len(ms.raw_entries(view)) == 3


def test_S2略過觀測的安靜說明_ok的殖利率卡帶reason時多一行_沒有reason時不多():
    quiet = ms.us10y_model(_yield_ok("us10y", "FRED (DGS10)"), "1Y")
    assert not [c for c in quiet["caption_lines"] if "略過" in c]
    d = _yield_ok("us10y", "FRED (DGS10)")
    d["reason"] = "已略過 3 筆無法採用的觀測"
    m = ms.us10y_model(d, "1Y")
    assert m["status"] == "ok" and m["spec"] is not None             # 狀態仍是 ok，圖照畫
    assert m["caption_lines"][-1] == "已略過 3 筆無法採用的觀測" and m["message"] is None
    assert logic.scan_forbidden(m["caption_lines"]) == {}
    assert "已略過 3 筆無法採用的觀測" in ms.section_strings(_view(us10y=d), "1Y")


def test_S2非ok的domain不加說明行_原因照舊走message():
    bad = _dom("us10y", "資料未備", reason="值為缺值或非有限數字 2 筆不寫", reason_code="no_closed_observation")
    m = ms.us10y_model(bad, "1Y")
    assert m["caption_lines"] == [] and m["message"].endswith("值為缺值或非有限數字 2 筆不寫")


def test_pp四捨五入為零不印負號_N2():
    mk = lambda a, b: ms.period_change_pp([{"obs_date": "2026-10-01", "value_num": a}, {"obs_date": "2026-10-02", "value_num": b}])
    for delta in (-0.004, 0.004, 0.0, -1e-12):
        t = mk(4.0, 4.0 + delta)["text"]
        assert t.startswith("期間變動 0.00 個百分點") and "-0.00" not in t and "+0.00" not in t, t
    assert mk(4.0, 4.006)["text"].startswith("期間變動 +0.01 個百分點")
    assert mk(4.0, 3.994)["text"].startswith("期間變動 -0.01 個百分點")


def test_圖上最後一點標籤_接近零的殖利率不印負零():
    from ui_v2.mkt import chart as ch
    pts = [{"obs_date": "2026-10-01", "value_num": 0.1}, {"obs_date": "2026-10-02", "value_num": -0.003}]
    spec = ch.build_spec(pts, label="US2Y", value_title="殖利率（%）", color="#000000", description="x")
    texts = [t for t in ch.spec_strings(spec) if t.startswith("US2Y ")]
    assert texts == ["US2Y 0.00"], texts
