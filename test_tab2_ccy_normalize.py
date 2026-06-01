"""test_tab2_ccy_normalize.py — v18.278 中文幣別 normalize（源於 user 截圖 TWD 基金被當外幣）"""
from __future__ import annotations

from pathlib import Path


def test_tab2_widget_has_ccy_normalize_dict():
    """Tab2 widget 必須有中文 → ISO 幣別 normalize 字典。"""
    src = (Path(__file__).parent / "ui" / "tab2_single_fund.py").read_text(encoding="utf-8")
    assert "_CCY_NORMALIZE = {" in src, "需要 _CCY_NORMALIZE 字典"
    # 核心中文幣別必須在內
    for zh in ["台幣", "新台幣", "美元", "歐元", "日圓", "人民幣"]:
        assert f'"{zh}"' in src, f"_CCY_NORMALIZE 應含「{zh}」"


def test_tab2_twd_fund_skips_fx_lookup():
    """TWD 基金（normalize 後 _ccy == 'TWD'）直接 _fx_to_twd=1.0 跳過 FX 抓取。"""
    src = (Path(__file__).parent / "ui" / "tab2_single_fund.py").read_text(encoding="utf-8")
    assert 'if _ccy == "TWD":' in src, "TWD 基金應有早期短路 branch"
    assert "_fx_to_twd = 1.0" in src, "TWD 基金 fx 應直接設為 1.0 不打 API"


def test_tab2_no_more_upper_twd_comparison():
    """既有 `_ccy.upper() != \"TWD\"` 全部被換成 `_ccy != \"TWD\"`（因為 normalize 後 _ccy 已是 ISO）。"""
    src = (Path(__file__).parent / "ui" / "tab2_single_fund.py").read_text(encoding="utf-8")
    assert "_ccy.upper() != \"TWD\"" not in src, "normalize 後不需 .upper()"
    assert "_ccy.upper() == \"TWD\"" not in src


def test_tab2_normalize_handles_common_zh_currencies():
    """字典應涵蓋台灣 user 常見保單外幣（美元/歐元/日圓/人民幣/澳幣/紐幣 等）。"""
    src = (Path(__file__).parent / "ui" / "tab2_single_fund.py").read_text(encoding="utf-8")
    expected_pairs = [
        ('"台幣"', '"TWD"'),
        ('"美元"', '"USD"'),
        ('"歐元"', '"EUR"'),
        ('"日圓"', '"JPY"'),
        ('"人民幣"', '"CNH"'),
        ('"港幣"', '"HKD"'),
        ('"澳幣"', '"AUD"'),
    ]
    for zh, iso in expected_pairs:
        # 寬鬆驗：字串都要在；緊密順序不檢
        assert zh in src and iso in src, f"normalize 缺 {zh} → {iso}"


def test_tab2_twd_fund_shows_no_manual_input_caption():
    """TWD 基金應顯示「💰 此基金以新台幣計價」caption，不該跳手動 number_input。"""
    src = (Path(__file__).parent / "ui" / "tab2_single_fund.py").read_text(encoding="utf-8")
    assert "💰 此基金以新台幣計價" in src
