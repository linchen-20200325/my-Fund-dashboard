"""test_tab2_ccy_normalize.py — 中文幣別 normalize（v18.278 起源，v19.75 K2 遷移至 SSOT）。

v18.278：Tab2 widget 含 inline `_CCY_NORMALIZE` 解 user 截圖「台幣基金被當外幣」bug。
v19.75 K2：inline dict 遷移到 services/currency SSOT（含 yf mode 保留人民幣→CNH 行為）。
"""
from __future__ import annotations

from pathlib import Path


def test_tab2_uses_currency_ssot():
    """v19.75 K2：Tab2 不再有 inline _CCY_NORMALIZE，必須走 services/currency SSOT。"""
    src = (Path(__file__).parents[1] / "ui" / "tab2_single_fund.py").read_text(encoding="utf-8")
    assert "from services.currency import normalize_ccy" in src, \
        "Tab2 應 import services/currency.normalize_ccy"
    # 不應再有 inline dict（過時遷移後不該保留）
    assert "_CCY_NORMALIZE = {" not in src, "Tab2 inline _CCY_NORMALIZE 應被移除"


def test_tab2_uses_yf_mode_for_cnh():
    """v19.75 K2：Tab2 需用 mode='yf' 保留原行為人民幣→CNH（yfinance CNHTWD=X 較可靠）。"""
    src = (Path(__file__).parents[1] / "ui" / "tab2_single_fund.py").read_text(encoding="utf-8")
    assert 'mode="yf"' in src or "mode='yf'" in src, "Tab2 需 mode=yf 保留 CNH 行為"


def test_tab2_twd_fund_skips_fx_lookup():
    """TWD 基金（normalize 後 _ccy == 'TWD'）直接 _fx_to_twd=1.0 跳過 FX 抓取。"""
    src = (Path(__file__).parents[1] / "ui" / "tab2_single_fund.py").read_text(encoding="utf-8")
    assert 'if _ccy == "TWD":' in src, "TWD 基金應有早期短路 branch"
    assert "_fx_to_twd = 1.0" in src, "TWD 基金 fx 應直接設為 1.0 不打 API"


def test_tab2_no_more_upper_twd_comparison():
    """既有 `_ccy.upper() != \"TWD\"` 全部被換成 `_ccy != \"TWD\"`（因為 normalize 後 _ccy 已是 ISO）。"""
    src = (Path(__file__).parents[1] / "ui" / "tab2_single_fund.py").read_text(encoding="utf-8")
    assert "_ccy.upper() != \"TWD\"" not in src, "normalize 後不需 .upper()"
    assert "_ccy.upper() == \"TWD\"" not in src


def test_currency_ssot_handles_common_zh_currencies():
    """v19.75 K2：SSOT services/currency 必須涵蓋台灣 user 常見保單外幣（含雙模式）。"""
    from services.currency import normalize_ccy
    # ISO 模式
    iso_pairs = [
        ("台幣", "TWD"), ("美元", "USD"), ("歐元", "EUR"),
        ("日圓", "JPY"), ("港幣", "HKD"), ("澳幣", "AUD"),
        ("人民幣", "CNY"),  # ISO 預設 CNY
    ]
    for zh, iso in iso_pairs:
        assert normalize_ccy(zh) == iso, f"ISO 模式 {zh} → 預期 {iso}，實得 {normalize_ccy(zh)}"
    # YF 模式（Tab2 + health_extras 用）
    assert normalize_ccy("人民幣", mode="yf") == "CNH", "YF 模式人民幣應 CNH"


def test_tab2_twd_fund_shows_no_manual_input_caption():
    """TWD 基金應顯示「💰 此基金以新台幣計價」caption，不該跳手動 number_input。"""
    src = (Path(__file__).parents[1] / "ui" / "tab2_single_fund.py").read_text(encoding="utf-8")
    assert "💰 此基金以新台幣計價" in src
