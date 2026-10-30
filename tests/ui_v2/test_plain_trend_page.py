# -*- coding: utf-8 -*-
"""去工程化守衛的射程補強：🌍 市場與趨勢的「市場趨勢」區段（BL-0525 Batch A；T8；slow lane）。

原本 `_plain_scan.SCRIPTS["mkt"]` 的五個情境都沒有餵 `market_view`，所以 `test_plain_page.py` 的「一般畫面沒有工程字樣」
**掃不到**市場趨勢區段（五張圖卡與 Missing 卡）的字；日後 Batch C 把圖卡下方的說明搬進 detail 展開區時，也沒有守衛會替新容器把關。
本檔用 `_plain_scan.MKT_TREND` 情境（合成序列、不打網路）補上：

1. 正控：畫面上真的有市場趨勢區段（圖卡標題在畫面上）—— 證明掃得到，不是空掃。
2. 同一組 PATTERNS（塊代號、層字樣、原始鍵名、秘密鍵名、例外型別名、實作字樣）對一般畫面（含預設收合展開區裡的字）0 命中。
"""

from __future__ import annotations

import pathlib
import sys

import pytest

pytestmark = pytest.mark.slow

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_HERE))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

import _plain_scan as SCAN  # noqa: E402
from test_plain_page import PATTERNS, _hits  # noqa: E402

from ui_v2.mkt import market_section  # noqa: E402


def _run():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(SCAN.MKT_TREND, default_timeout=90)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_正控_市場趨勢區段真的在畫面上_掃描不是空掃():
    texts = " ".join(SCAN.screen_texts(_run()))
    assert market_section.LABELS["vix"] in texts, "市場趨勢區段沒畫出來 —— 情境腳本失效"


def test_市場趨勢區段_一般畫面沒有工程字樣():
    texts = SCAN.screen_texts(_run())
    assert len(texts) >= 10
    assert _hits(texts, PATTERNS) == []


# ── BL-0525 Batch C（T8／T13 遷移）：新視覺層級的 detail 容器與切換後的畫面也納入同一組掃描 ──
# 新版同一時間只畫一個 Primary 序列，其餘四個序列的來源與限制文字只有切過去才會出現；
# 還有「利率與信用」三個子序列、合併的「▸ 次要圖：來源與限制」與「▸ 尚未取得」群組。逐一切過去掃。


@pytest.mark.parametrize("series", ["taiex", "sp500", "vix", "us10y", "us2y"])
def test_Primary每個序列切過去_一般畫面含detail展開區都沒有工程字樣(series):
    at = _run()
    next(r for r in at.radio if r.key == "mkt_primary_series").set_value(series).run()
    assert not at.exception, [e.value for e in at.exception]
    texts = SCAN.screen_texts(at)
    assert any(market_section.LABELS[series] in t for t in texts), "切換後該序列沒有畫出來 —— 掃描是空掃"
    assert _hits(texts, PATTERNS) == []


@pytest.mark.parametrize("key", ["term_spread_pct", "credit_spread_pct", "policy_rate_pct"])
def test_利率與信用每個子序列切過去_沒有工程字樣(key):
    at = _run()
    next(r for r in at.radio if r.key == "mkt_rates_series").set_value(key).run()
    assert not at.exception, [e.value for e in at.exception]
    texts = SCAN.screen_texts(at)
    assert any("利率與信用" in t for t in texts)
    assert _hits(texts, PATTERNS) == []


def test_新層級的展開區都被掃到_尚未取得_各項資料狀態_次要圖來源與限制():
    at = _run()
    labels = [e.label for e in at.expander]
    for prefix in ("▸ 尚未取得：", "▸ 各項資料狀態", "▸ 次要圖：來源與限制"):
        assert any(l.startswith(prefix) for l in labels), prefix
    texts = " ".join(SCAN.screen_texts(at))
    # screen_texts 沒有跳過這些展開區：群組標題、群組內 Missing 文案、次要圖 detail 的來源行都在掃描母體裡
    assert "尚未取得：" in texts and "目前沒有正式資料來源" in texts and "來源 FRED (T10Y2Y)" in texts
