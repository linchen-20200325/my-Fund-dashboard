# -*- coding: utf-8 -*-
"""🌍 市場趨勢區段的執行期測試（slow lane；Streamlit AppTest；BL-0516 批 1）。

以 stub 載入函式呼叫 `page.render(load_live=...)`；`notes["market_view"]` 由 L2 純函式 `market_view.build_market_view`
以合成序列組出（不打網路）。涵蓋：正式模式新區段出現且 Missing 文案在、期間切換不報錯、VIX 失敗（429）不畫圖、
示範模式與沒有 `market_view` 的舊替身不受影響。390px 不橫捲由 `test_live_390_page.py` 的 mkt 腳本涵蓋（需瀏覽器，CI 驗）。
"""

import pathlib
import sys

import pytest

pytestmark = pytest.mark.slow

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402

from ui_v2.mkt import chart, logic, market_section  # noqa: E402

_HEAD = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
import pandas as pd
from ui_v2.mkt import fixtures, page
from services.v2_tables import market_view as mv

def _series():
    idx = pd.bdate_range("2024-10-24", "2026-10-23")
    s = pd.Series([16.0 + (i % 9) * 0.3 for i in range(len(idx))], index=idx, dtype=float, name="^VIX")
    s.attrs.update({{"fetched_at": "2026-10-27T06:00:00+00:00", "source": "Yahoo:^VIX", "exchange_tz": "Etc/UTC"}})
    return s

_dataset = fixtures.dataset_all_ok()
_notes = {{"pending": {{"leading_index": "ndc_no_release_date", "coincident_index": "ndc_no_release_date",
                      "fx_twd_per_usd": "fx_obs_date_rule"}}, "masked_keys": [], "cooldowns": []}}
"""

_OK = _HEAD + """
_notes["market_view"] = mv.build_market_view(fetch_vix=lambda _t: (_series(), None))
page.render(load_live=lambda: {"dataset": _dataset, "notes": _notes})
"""

_ERR = _HEAD + """
_notes["market_view"] = mv.build_market_view(
    fetch_vix=lambda _t: (pd.Series(dtype=float), "Yahoo:^VIX 失敗：HTTP 429 Too Many Requests"))
page.render(load_live=lambda: {"dataset": _dataset, "notes": _notes})
"""

_LEGACY = _HEAD + """
page.render(load_live=lambda: {"dataset": _dataset, "notes": _notes})
"""

_DEMO = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
from ui_v2.mkt import page
page.render()
"""


def _run(script):
    at = AppTest.from_string(script, default_timeout=90)
    at.run()
    return at


def _texts(at):
    out = [e.value for e in at.markdown] + [e.value for e in at.caption]
    out += [e.label for e in at.button] + [e.label for e in at.expander]
    return out


def _charts(at):
    return at.get("vega_lite_chart")


def test_正式模式_新區段出現_Missing文案逐字在():
    at = _run(_OK)
    assert not at.exception, [e.value for e in at.exception]
    text = "\n".join(_texts(at))
    for needle in ("市場趨勢", "暫無完整市場綜合判定（缺正式 aggregation rule）",
                   "⬜ EPS 預估資料未取得，無法計算正式指數情境", "⬜ 無法判定", "⬜ 資料來源待確認",
                   market_section.TEXT_INTL_MISSING, market_section.TEXT_DATA_GAP,
                   "資料日期（最後觀測日）2026-10-23", "來源 Yahoo:^VIX", "⬜ 門檻待裁示"):
        assert needle in text, needle
    assert ">市場結論</span>" in text and ">市場綜合判定</span>" not in text      # 卡名同 docs/v2/66 §3.1
    assert "缺值日不補值" in text and "折線斷開" not in text
    for name in ("NASDAQ", "MSCI World", "MSCI EM", "台股加權指數（TAIEX）"):
        assert name in text, name


def test_正式模式_新區段無方向詞_無偏多偏空_無目標價():
    at = _run(_OK)
    text = [t for t in _texts(at) if 'data-section="trend' in t or "市場趨勢" in t]
    assert text
    joined = "\n".join(text)
    for word in ("偏多", "偏空", "目標價", "預測", "買進", "賣出"):
        assert word not in joined, word
    assert logic.scan_forbidden([joined]) == {}


def test_預設1Y_一張圖_期間按鈕四個_3Y標資料不足():
    at = _run(_OK)
    assert len(_charts(at)) == 1
    radios = [r for r in at.radio if r.key == "mkt_vix_period"]
    assert len(radios) == 1
    radio = radios[0]
    assert radio.value == "1Y"
    assert list(radio.options) == ["3M", "6M", "1Y", "3Y（資料不足）"]


@pytest.mark.parametrize("label", ["3M", "6M", "1Y"])
def test_期間切換_不報錯_仍是一張圖(label):
    at = _run(_OK)
    radio = next(r for r in at.radio if r.key == "mkt_vix_period")
    radio.set_value(label).run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(_charts(at)) == 1


def test_3Y_誠實顯示資料不足_沒有縮短冒充的圖():
    at = _run(_OK)
    radio = next(r for r in at.radio if r.key == "mkt_vix_period")
    radio.set_value("3Y（資料不足）").run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(_charts(at)) == 0
    assert "資料不足以呈現此期間" in "\n".join(_texts(at))
    # 切回有資料的期間，圖回來
    next(r for r in at.radio if r.key == "mkt_vix_period").set_value("6M").run()
    assert len(_charts(at)) == 1


def test_VIX取數失敗429_不畫圖_沒有期間按鈕_寫原文():
    at = _run(_ERR)
    assert not at.exception, [e.value for e in at.exception]
    assert len(_charts(at)) == 0
    assert not [r for r in at.radio if r.key == "mkt_vix_period"]
    assert "⛔ 取數失敗：Yahoo:^VIX 失敗：HTTP 429 Too Many Requests" in "\n".join(_texts(at))
    assert "⬜ EPS 預估資料未取得，無法計算正式指數情境" in "\n".join(_texts(at))   # 其他 Missing 區塊照樣在


def test_沒有market_view的舊替身_整段不畫_其餘照舊():
    at = _run(_LEGACY)
    assert not at.exception, [e.value for e in at.exception]
    text = "\n".join(_texts(at))
    assert "市場趨勢" not in text and 'data-section="trend' not in text
    assert len(_charts(at)) == 0


def test_示範模式不受影響():
    at = _run(_DEMO)
    assert not at.exception, [e.value for e in at.exception]
    text = "\n".join(_texts(at))
    assert 'data-section="trend' not in text and "市場趨勢" not in text
    assert len(_charts(at)) == 0
    assert not [r for r in at.radio if r.key == "mkt_vix_period"]


def test_section_strings_與畫面一致的禁詞守衛():
    # 純函式層的雙保險：期間四種各掃一次（見 test_mkt_market_section_logic）
    assert chart.PERIODS == ("3M", "6M", "1Y", "3Y")
