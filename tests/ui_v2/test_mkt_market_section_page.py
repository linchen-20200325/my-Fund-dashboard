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

def _tw_series():
    idx = pd.bdate_range("2024-10-24", "2026-10-23") + pd.Timedelta(hours=1)
    s = pd.Series([22000.0 + i * 3 for i in range(len(idx))], index=idx, dtype=float, name="^TWII")
    s.attrs.update({{"fetched_at": "2026-10-27T06:00:00+00:00", "source": "Yahoo:^TWII", "exchange_tz": "Asia/Taipei"}})
    return s

def _gspc_series():
    idx = pd.bdate_range("2024-10-24", "2026-10-23") + pd.Timedelta(hours=13, minutes=30)
    s = pd.Series([5000.0 + i * 2 for i in range(len(idx))], index=idx, dtype=float, name="^GSPC")
    s.attrs.update({{"fetched_at": "2026-10-27T06:00:00+00:00", "source": "Yahoo:^GSPC", "exchange_tz": "America/New_York"}})
    return s

def _fred(base):
    def _fn(series_id, api_key, observation_start):
        days = pd.bdate_range("2024-10-24", "2026-10-23")
        df = pd.DataFrame({{"date": days, "value": [base + (i % 7) * 0.01 for i in range(len(days))],
                           "realtime_start": days + pd.Timedelta(days=1), "realtime_end": "9999-12-31"}})
        df.attrs.update({{"fetched_at": "2026-10-27T06:00:00+00:00", "realtime_floor": observation_start,
                         "source": "FRED:" + series_id + ":vintages"}})
        return df, None
    return _fn

_dataset = fixtures.dataset_all_ok()
_notes = {{"pending": {{"leading_index": "ndc_no_release_date", "coincident_index": "ndc_no_release_date",
                      "fx_twd_per_usd": "fx_obs_date_rule"}}, "masked_keys": [], "cooldowns": []}}
"""

_OK = _HEAD + """
_notes["market_view"] = mv.build_market_view(fetch_vix=lambda _t, _r=None: (_series(), None),
                                             fetch_taiex=lambda _t, _r=None: (_tw_series(), None),
                                             fetch_sp500=lambda _t, _r=None: (_gspc_series(), None),
                                             fetch_fred=lambda sid, k, o: _fred(4.0 if sid == "DGS10" else 3.5)(sid, k, o),
                                             fred_api_key="k")
page.render(load_live=lambda: {"dataset": _dataset, "notes": _notes})
"""

_ERR = _HEAD + """
_notes["market_view"] = mv.build_market_view(
    fetch_vix=lambda _t, _r=None: (pd.Series(dtype=float), "Yahoo:^VIX 失敗：HTTP 429 Too Many Requests"),
    fetch_taiex=lambda _t, _r=None: (_tw_series(), None),
    fetch_sp500=lambda _t, _r=None: (_gspc_series(), None),
    fetch_fred=lambda sid, k, o: _fred(4.0)(sid, k, o), fred_api_key="k")
page.render(load_live=lambda: {"dataset": _dataset, "notes": _notes})
"""

_TWERR = _HEAD + """
_notes["market_view"] = mv.build_market_view(
    fetch_vix=lambda _t, _r=None: (_series(), None),
    fetch_taiex=lambda _t, _r=None: (pd.Series(dtype=float), "Yahoo:^TWII 失敗：HTTP 429 Too Many Requests"),
    fetch_sp500=lambda _t, _r=None: (_gspc_series(), None),
    fetch_fred=lambda sid, k, o: _fred(4.0)(sid, k, o), fred_api_key="k")
page.render(load_live=lambda: {"dataset": _dataset, "notes": _notes})
"""

_NOKEY = _HEAD + """
_notes["market_view"] = mv.build_market_view(fetch_vix=lambda _t, _r=None: (_series(), None),
                                             fetch_taiex=lambda _t, _r=None: (_tw_series(), None),
                                             fetch_sp500=lambda _t, _r=None: (_gspc_series(), None),
                                             fred_api_key="")
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


_PERIOD_KEYS = ("mkt_vix_period", "mkt_taiex_period", "mkt_sp500_period", "mkt_us10y_period", "mkt_us2y_period")


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
                   "⬜ EPS 預估資料未取得，無法計算正式指數情境", "⬜ 無法判定",
                   market_section.TEXT_INTL_MISSING, market_section.TEXT_DATA_GAP,
                   "資料日期（最後觀測日）2026-10-23", "來源 Yahoo:^VIX", "來源 Yahoo Finance (^TWII)", "期間漲跌 +", "⬜ 門檻待裁示",
                   "來源 Yahoo Finance (^GSPC)", "來源 FRED (DGS10)", "來源 FRED (DGS2)", "期間變動 ",
                   "美國 10 年期公債殖利率", "美國 2 年期公債殖利率", "標普 500 指數（S&amp;P 500）",   # 卡標題經 HTML 轉義
                   market_section.TEXT_FRED_OBS_NOTE):
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
    assert len(_charts(at)) == 5          # VIX、TAIEX、S&P 500、US10Y、US2Y 各一張
    for key in _PERIOD_KEYS:
        radios = [r for r in at.radio if r.key == key]
        assert len(radios) == 1, key
        radio = radios[0]
        assert radio.value == "1Y"
        assert list(radio.options) == ["3M", "6M", "1Y", "3Y（資料不足）"]


@pytest.mark.parametrize("label", ["3M", "6M", "1Y"])
@pytest.mark.parametrize("key", list(_PERIOD_KEYS))
def test_期間切換_不報錯_仍是五張圖(label, key):
    at = _run(_OK)
    radio = next(r for r in at.radio if r.key == key)
    radio.set_value(label).run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(_charts(at)) == 5


@pytest.mark.parametrize("key", list(_PERIOD_KEYS))
def test_3Y_誠實顯示資料不足_沒有縮短冒充的圖(key):
    at = _run(_OK)
    radio = next(r for r in at.radio if r.key == key)
    radio.set_value("3Y（資料不足）").run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(_charts(at)) == 4          # 只有被切到 3Y 的那張消失；其餘不受影響（fragment 隔離）
    assert "資料不足以呈現此期間" in "\n".join(_texts(at))
    # 切回有資料的期間，圖回來
    next(r for r in at.radio if r.key == key).set_value("6M").run()
    assert len(_charts(at)) == 5


def test_TAIEX期間漲跌_跟著期間切換更新_不重跑另一張卡():
    at = _run(_OK)
    before = "\n".join(_texts(at))
    assert "期間漲跌 +" in before and "收盤價）" in before
    next(r for r in at.radio if r.key == "mkt_taiex_period").set_value("3M").run()
    after = [t for t in _texts(at) if "trend-taiex-return" in t]
    assert len(after) == 1 and "期間漲跌 +" in after[0]
    assert after[0] != [t for t in _texts(_run(_OK)) if "trend-taiex-return" in t][0]
    # VIX 卡沒有期間漲跌
    assert not [t for t in _texts(at) if "trend-vix-return" in t]


def test_TAIEX取數失敗429_不畫TAIEX圖_主頁只寫取數失敗_原文走原始訊息():
    at = _run(_TWERR)
    assert not at.exception, [e.value for e in at.exception]
    assert len(_charts(at)) == 4          # TAIEX 沒有圖，其餘四張仍在
    assert not [r for r in at.radio if r.key == "mkt_taiex_period"]
    assert [r for r in at.radio if r.key == "mkt_vix_period"]
    needle = "Yahoo:^TWII 失敗：HTTP 429 Too Many Requests"
    text = "\n".join(_texts(at))
    assert needle not in text and "429" not in text
    assert "⛔ 取數失敗" in text
    from ui_v2 import plain
    store = at.session_state[plain.RAW_STATE]["mkt"]["entries"]
    assert f"⛔ 取數失敗：{needle}" in [e["text"] for e in store]


def test_成交量_市場統計_EPS_PE_正式模式仍是Missing_沒有借TAIEX的資料():
    at = _run(_OK)
    text = "\n".join(_texts(at))
    assert text.count(market_section.TEXT_DATA_GAP) == 2            # 台股成交量、台股市場統計
    assert "⬜ EPS 預估資料未取得，無法計算正式指數情境" in text
    assert "台股成交量" in text and "台股市場統計" in text
    for blob in _texts(at):
        if 'data-section="trend-taiex_volume"' in blob or 'data-section="trend-market_stats"' in blob:
            assert "Yahoo" not in blob and "資料日期" not in blob


def test_VIX取數失敗429_不畫圖_沒有期間按鈕_寫原文():
    at = _run(_ERR)
    assert not at.exception, [e.value for e in at.exception]
    assert len(_charts(at)) == 4          # VIX 沒有圖，其餘四張仍在
    assert not [r for r in at.radio if r.key == "mkt_vix_period"]
    needle = "⛔ 取數失敗：Yahoo:^VIX 失敗：HTTP 429 Too Many Requests"
    assert needle not in "\n".join(_texts(at))        # 44 P0-①：一般畫面不印原文
    assert "⛔ 取數失敗" in "\n".join(_texts(at))
    from ui_v2 import plain
    store = at.session_state[plain.RAW_STATE]["mkt"]["entries"]
    assert needle in [e["text"] for e in store]       # 原文在跨頁原始訊息
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


def test_殖利率期間變動_pp_跟著期間切換_是百分點不是百分比():
    at = _run(_OK)
    first = [t for t in _texts(at) if "trend-us10y-return" in t]
    assert len(first) == 1 and "期間變動 " in first[0] and "個百分點（pp）" in first[0] and "期間漲跌" not in first[0]
    next(r for r in at.radio if r.key == "mkt_us10y_period").set_value("3M").run()
    after = [t for t in _texts(at) if "trend-us10y-return" in t]
    assert len(after) == 1 and after[0] != first[0]
    # 價格卡仍是百分比報酬
    assert [t for t in _texts(at) if "trend-sp500-return" in t][0].count("期間漲跌 ") == 1


def test_缺FRED金鑰_兩張殖利率卡只寫取數失敗_原文走原始訊息_價格圖不受影響():
    at = _run(_NOKEY)
    assert not at.exception, [e.value for e in at.exception]
    assert len(_charts(at)) == 3          # VIX、TAIEX、S&P 500
    assert not [r for r in at.radio if r.key in ("mkt_us10y_period", "mkt_us2y_period")]
    text = "\n".join(_texts(at))
    assert "未設定 FRED_API_KEY" not in text and "⛔ 取數失敗" in text
    from ui_v2 import plain
    entries = [e["text"] for e in at.session_state[plain.RAW_STATE]["mkt"]["entries"]]
    assert entries.count("⛔ 取數失敗：未設定 FRED_API_KEY") == 2


def test_NASDAQ_MSCI正式模式仍是Missing_不借SP500():
    at = _run(_OK)
    text = "\n".join(_texts(at))
    assert text.count(market_section.TEXT_INTL_MISSING) == 3
    for blob in _texts(at):
        if any(f'data-section="trend-{k}"' in blob for k in ("nasdaq", "msci_world", "msci_em")):
            assert "Yahoo" not in blob and "^GSPC" not in blob and "資料日期" not in blob
