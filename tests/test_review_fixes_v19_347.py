# -*- coding: utf-8 -*-
"""v19.347 — 大工程清單 🟢 ⑯:追蹤誤差(Tracking Error)接 UI 回歸鎖。

wb07 風險表本就解析 Tracking Error 入 risk_table(clean_risk_table NUMERIC
集含此鍵),但 _risk_1y_rows_html 從未顯示 → 補列(short/long 兩視圖),
缺值誠實顯「—」(§1)。
"""
from __future__ import annotations


def test_tracking_error_row_short_style():
    from ui.tab2_single_fund import _risk_1y_rows_html
    html = _risk_1y_rows_html({"一年": {
        "標準差": 12.5, "Sharpe": 1.1, "Alpha": 0.3, "Beta": 0.9,
        "Tracking Error": 3.2,
    }})
    assert "追蹤誤差(1Y)" in html and "3.2" in html
    assert "標準差(1Y)" in html  # 既有列不受影響


def test_tracking_error_row_long_style_pct():
    from ui.tab2_single_fund import _risk_1y_rows_html
    html = _risk_1y_rows_html(
        {"一年": {"標準差": 12.5, "Tracking Error": 3.2}},
        label_style="long")
    assert "追蹤誤差 TE(1Y)" in html and "3.2%" in html


def test_tracking_error_missing_shows_dash():
    from ui.tab2_single_fund import _risk_1y_rows_html
    html = _risk_1y_rows_html({"一年": {"標準差": 12.5, "Sharpe": 1.1}})
    assert "追蹤誤差(1Y)" in html   # 列仍在
    # 該列值為 —(缺值誠實顯示,不腦補)
    _te_row = [seg for seg in html.split("追蹤誤差(1Y)")[1:]][0][:200]
    assert "—" in _te_row


def test_na_string_passthrough():
    from ui.tab2_single_fund import _risk_1y_rows_html
    html = _risk_1y_rows_html(
        {"一年": {"Tracking Error": "N/A"}}, label_style="long")
    assert "N/A" in html and "N/A%" not in html  # 字串不硬加 %
