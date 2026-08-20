"""v19.497:補選股池 currency 的名稱→幣別判定(§1 保守:只在有把握時填)。"""
import pytest

from scripts.fill_pool_currency import _derive_ccy


@pytest.mark.parametrize("name,expect_ccy", [
    ("聯博多元資產收益組合基金AI配息(美元)", "USD"),
    ("安聯台灣大壩基金-A累積型(台幣)", "TWD"),            # 名稱幣別字樣
    ("安聯台灣智慧基金", "TWD"),                          # 台股基金推定(含「台灣」、無外幣字樣)
    ("摩根投資基金-多重收益基金A股(美元對沖)", "USD"),
    ("PIMCO GIS Income Fund E EUR Hedged", "EUR"),
])
def test_derive_ccy_fills(name, expect_ccy):
    ccy, how = _derive_ccy(name)
    assert ccy == expect_ccy and how


def test_derive_ccy_leaves_empty_when_uncertain():
    # 無幣別字樣、且非台灣基金 → §1 不猜,留空
    for name in ("Some Global Bond Fund", "聯博-美國成長基金", ""):
        ccy, how = _derive_ccy(name)
        assert ccy == "" and how == ""


def test_taiwan_fallback_only_when_no_foreign_token():
    # 台灣基金但名稱標了美元 → 以美元為準(名稱幣別優先於台灣推定)
    ccy, how = _derive_ccy("某某台灣基金(美元)")
    assert ccy == "USD" and how == "名稱幣別字樣"
