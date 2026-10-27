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


def _view(vix=None):
    vix = vix or _dom("vix", "ok", source="Yahoo:^VIX", fetched_at="2026-10-27T06:00:00+00:00",
                      obs_date="2026-10-23", value_unit="index", points=_points())
    return {"domains": [
        vix,
        _dom("taiex", reason_code="source_pending_bl0518", reason="x"),
        _dom("taiex_volume", reason_code="no_official_source", reason="x"),
        _dom("market_stats", reason_code="no_official_source", reason="x"),
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
    assert ms.TEXT_TAIEX_PENDING == "⬜ 資料來源待確認"
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
    assert ms.missing_copy(by["taiex"]) == "⬜ 資料來源待確認"
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
    assert all(r["status_text"] == "⬜ 資料未備" for r in model["rows"][1:])
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
