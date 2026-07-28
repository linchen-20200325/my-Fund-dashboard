"""MoneyDJ 基金類別選取 `_pick_fund_category` — v19.419。

修 bug:原本「投資標的」優先,把公開說明書長描述當類別(污染 UI + 輪動跨類配對)。
新規則:投資標的僅在夠短(≤15字,像分類標籤)時採用,否則退回基金類型;都不合則空。
"""
from repositories.fund.sources import _pick_fund_category


def test_short_investment_target_used_as_label():
    assert _pick_fund_category({"投資標的": "平衡型", "基金類型": "平衡型"}) == "平衡型"


def test_short_target_without_type():
    assert _pick_fund_category({"投資標的": "全球股票"}) == "全球股票"


def test_long_description_falls_back_to_type():
    _desc = "本基金投資於中華民國境內之有價證券及外國有價證券。原則上,本基金自成立日起…"
    assert _pick_fund_category({"投資標的": _desc, "基金類型": "債券型"}) == "債券型"


def test_long_description_no_type_returns_empty():
    _desc = "本基金投資於中華民國境內之有價證券為中華民國境內由國家或機構所保證、發行"
    assert _pick_fund_category({"投資標的": _desc}) == ""    # 寧可空,不吐長描述


def test_type_only():
    assert _pick_fund_category({"基金類型": "股票型"}) == "股票型"


def test_empty_map():
    assert _pick_fund_category({}) == ""
