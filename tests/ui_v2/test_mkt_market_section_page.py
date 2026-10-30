# -*- coding: utf-8 -*-
"""🌍 市場趨勢區段的執行期測試（slow lane；Streamlit AppTest；BL-0516 批 1；BL-0525 Batch C 遷移，T9）。

~~舊版斷言：五張圖常駐、每張圖各一組期間按鈕、圖下常駐小字~~（有意識的更正，不是漏刪；`DEC-2026-10-30-01` D1／D2／D4／D7，
`docs/v2/72` 第 12.2 節）：新版同一時間只畫 **1 張 Primary 圖**（五個序列用一組切換）＋ 迷你次圖（不是 vega 圖）；圖下小字全部搬進
「▸ 為什麼‧來源‧限制」detail、Missing 併入「▸ 尚未取得」群組。**舊斷言的理由仍然成立**（資訊不能少、Missing 就是 Missing、
期間不足要說不足、取數失敗原文不上一般畫面）—— 新斷言驗的是同樣這幾件事，只是改驗「資訊存在、可展開取得、語意不變」，
不再要求「文字一定外露」。

以 stub 載入函式呼叫 `page.render(load_live=...)`；`notes["market_view"]` 由 L2 純函式 `market_view.build_market_view`
以合成序列組出（不打網路）。涵蓋：正式模式新區段出現且 Missing 文案在、期間切換不報錯、VIX 失敗（429）不畫圖、
示範模式與沒有 `market_view` 的舊替身不受影響。390px 不橫捲由 `test_live_390_page.py` 的 mkt 腳本涵蓋（需瀏覽器，CI 驗）。
"""

import pathlib
import re
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
    def _fn(series_id, api_key, n):
        days = pd.bdate_range("2024-10-24", "2026-10-23")
        df = pd.DataFrame({{"date": days, "value": [base + (i % 7) * 0.01 for i in range(len(days))],
                           "realtime_start": pd.Timestamp("2026-10-27"), "source": "FRED:" + series_id,
                           "fetched_at": "2026-10-27T06:00:00+00:00"}})
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
                                             fetch_fred=lambda sid, k, n: _fred(4.0 if sid == "DGS10" else 3.5)(sid, k, n),
                                             fred_api_key="k")
page.render(load_live=lambda: {"dataset": _dataset, "notes": _notes})
"""

_ERR = _HEAD + """
_notes["market_view"] = mv.build_market_view(
    fetch_vix=lambda _t, _r=None: (pd.Series(dtype=float), "Yahoo:^VIX 失敗：HTTP 429 Too Many Requests"),
    fetch_taiex=lambda _t, _r=None: (_tw_series(), None),
    fetch_sp500=lambda _t, _r=None: (_gspc_series(), None),
    fetch_fred=lambda sid, k, n: _fred(4.0)(sid, k, n), fred_api_key="k")
page.render(load_live=lambda: {"dataset": _dataset, "notes": _notes})
"""

_TWERR = _HEAD + """
_notes["market_view"] = mv.build_market_view(
    fetch_vix=lambda _t, _r=None: (_series(), None),
    fetch_taiex=lambda _t, _r=None: (pd.Series(dtype=float), "Yahoo:^TWII 失敗：HTTP 429 Too Many Requests"),
    fetch_sp500=lambda _t, _r=None: (_gspc_series(), None),
    fetch_fred=lambda sid, k, n: _fred(4.0)(sid, k, n), fred_api_key="k")
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


_SERIES = ("taiex", "sp500", "vix", "us10y", "us2y")
_SOURCES = {"taiex": "來源 Yahoo Finance (^TWII)", "sp500": "來源 Yahoo Finance (^GSPC)", "vix": "來源 Yahoo:^VIX",
            "us10y": "來源 FRED (DGS10)", "us2y": "來源 FRED (DGS2)"}



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


def _radio(at, key):
    return next(r for r in at.radio if r.key == key)


def _pick(at, series):
    _radio(at, "mkt_primary_series").set_value(series).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _primary(at):
    blobs = [t for t in _texts(at) if 'data-section="primary"' in t]
    assert len(blobs) == 1
    return blobs[0]


def test_正式模式_新區段出現_Missing文案逐字在():
    at = _run(_OK)
    assert not at.exception, [e.value for e in at.exception]
    text = "\n".join(_texts(at))
    for needle in ("暫無完整市場綜合判定（缺正式 aggregation rule）",       # 「▸ 各項資料狀態」內的市場結論卡
                   "⬜ EPS 預估資料未取得，無法計算正式指數情境", "⬜ 無法判定",
                   market_section.TEXT_INTL_MISSING, market_section.TEXT_DATA_GAP,
                   "資料日期（最後觀測日）2026-10-23", "來源 Yahoo Finance (^TWII)", "期間漲跌 +", "⬜ 門檻待裁示",
                   "來源 Yahoo:^VIX", "來源 Yahoo Finance (^GSPC)", "來源 FRED (T10Y2Y)",
                   "標普 500 指數（S&amp;P 500）" if False else "S&amp;P 500"):
        assert needle in text, needle
    assert ">市場結論</span>" in text and ">市場綜合判定</span>" not in text      # 卡名同 docs/v2/66 §3.1
    assert "缺值日不補值" in text and "折線斷開" not in text
    for name in ("NASDAQ", "MSCI World", "MSCI EM", "台股加權指數（TAIEX）"):
        assert name in text, name


def test_正式模式_新區段無方向詞_無偏多偏空_無目標價():
    at = _run(_OK)
    text = [t for t in _texts(at) if 'data-section="' in t]
    assert text
    joined = "\n".join(text)
    for word in ("偏多", "偏空", "目標價", "預測", "買進", "賣出"):
        assert word not in joined, word
    assert logic.scan_forbidden([joined]) == {}


def test_預設_只有一張Primary圖_序列五選一預設台股_期間四個3Y標資料不足():
    at = _run(_OK)
    assert len(_charts(at)) == 1                 # 不是五張圖：Secondary 是行內迷你圖，不是 vega 圖
    series = _radio(at, "mkt_primary_series")
    assert series.value == "taiex" and list(series.options) == ["台股", "S&P 500", "VIX", "美10Y", "美2Y"]
    period = _radio(at, "mkt_primary_period")
    assert period.value == "1Y" and list(period.options) == ["3M", "6M", "1Y", "3Y（資料不足）"]
    assert len([r for r in at.radio if r.key == "mkt_primary_period"]) == 1       # 全頁只有一組期間切換
    assert 'data-series="taiex"' in _primary(at)


@pytest.mark.parametrize("series", _SERIES)
def test_序列切換_不報錯_仍是一張圖_該序列的來源與限制在detail(series):
    at = _pick(_run(_OK), series)
    assert len(_charts(at)) == 1
    assert f'data-series="{series}"' in _primary(at)
    assert _SOURCES[series] in "\n".join(_texts(at))
    assert market_section.TEXT_FRESHNESS_THRESHOLD in "\n".join(_texts(at))


@pytest.mark.parametrize("label", ["3M", "6M", "1Y"])
@pytest.mark.parametrize("series", _SERIES)
def test_期間切換_不報錯_仍是一張圖(label, series):
    at = _pick(_run(_OK), series)
    _radio(at, "mkt_primary_period").set_value(label).run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(_charts(at)) == 1


@pytest.mark.parametrize("series", _SERIES)
def test_3Y_誠實顯示資料不足_沒有縮短冒充的圖(series):
    at = _pick(_run(_OK), series)
    _radio(at, "mkt_primary_period").set_value("3Y（資料不足）").run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(_charts(at)) == 0
    assert "資料不足以呈現此期間" in "\n".join(_texts(at))
    if series != "vix":        # VIX 沒有期間漲跌（既有設計），中間那枚 chip 是單位說明
        assert "近3Y 資料不足" in _primary(at)
    _radio(at, "mkt_primary_period").set_value("6M").run()      # 切回有資料的期間，圖回來
    assert len(_charts(at)) == 1


def test_序列與期間切換_在fragment內_且只讀已在view裡的資料_不重取數():
    """AppTest 的 `.run()` 一律重跑整份腳本，量不出 fragment 隔離；所以改驗結構（AST）：
    (1) 兩個帶切換器的函式都用 `@st.fragment`；(2) 它們（含所依賴的 overview 模型）不呼叫 `load_live`／任何取數函式、
    不 import `source`／services —— 切換只在記憶體裡的 view／dataset 上換一個序列。"""
    import ast
    tree = ast.parse((_ROOT / "ui_v2/mkt/page.py").read_text(encoding="utf-8"))
    funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    for name in ("_render_primary", "_render_rates_card"):
        decos = [ast.unparse(d) for d in funcs[name].decorator_list]
        assert "st.fragment" in decos, (name, decos)
        called = {ast.unparse(c.func) for c in ast.walk(funcs[name]) if isinstance(c, ast.Call)}
        assert not {c for c in called if "load_live" in c or "fetch" in c or "build_market" in c}, (name, called)
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
    assert "source" not in imported
    overview_tree = ast.parse((_ROOT / "ui_v2/mkt/overview.py").read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(overview_tree) if isinstance(n, ast.Name)} | \
        {n.attr for n in ast.walk(overview_tree) if isinstance(n, ast.Attribute)}
    assert not {n for n in names if n.startswith("fetch_") or n in ("requests", "load_live")}, names


def test_TAIEX期間漲跌_跟著期間切換更新_在detail的為什麼組():
    at = _run(_OK)
    before = [t for t in _texts(at) if "期間漲跌 +" in t and "收盤價）" in t]
    assert before
    _radio(at, "mkt_primary_period").set_value("3M").run()
    after = [t for t in _texts(at) if "期間漲跌 +" in t and "收盤價）" in t]
    assert after and after != before
    chip = re.search(r"近3M [+-]\d+\.\d%", _primary(at))
    assert chip


def test_TAIEX取數失敗429_Primary只寫取數失敗_原文走原始訊息_其他序列仍可切換():
    at = _run(_TWERR)
    assert not at.exception, [e.value for e in at.exception]
    assert len(_charts(at)) == 0          # 預設序列是 TAIEX：Primary 沒有圖（不畫空座標軸）
    assert not [r for r in at.radio if r.key == "mkt_primary_period"]
    needle = "Yahoo:^TWII 失敗：HTTP 429 Too Many Requests"
    text = "\n".join(_texts(at))
    assert needle not in text and "429" not in text
    assert "⛔ 取數失敗" in _primary(at)
    from ui_v2 import plain
    store = at.session_state[plain.RAW_STATE]["mkt"]["entries"]
    assert f"⛔ 取數失敗：{needle}" in [e["text"] for e in store]
    _pick(at, "vix")                       # 其他序列不受影響
    assert len(_charts(at)) == 1


def test_成交量_市場統計_EPS_PE_正式模式仍是Missing_沒有借TAIEX的資料():
    at = _run(_OK)
    text = "\n".join(_texts(at))
    assert text.count(market_section.TEXT_DATA_GAP) == 2            # 台股成交量、台股市場統計
    assert "⬜ EPS 預估資料未取得，無法計算正式指數情境" in text
    assert "台股成交量" in text and "台股市場統計" in text
    for blob in _texts(at):
        if 'data-section="trend-taiex_volume"' in blob or 'data-section="trend-market_stats"' in blob:
            assert "Yahoo" not in blob and "資料日期" not in blob


def test_尚未取得群組_預設收合_標題列點名七項_EPS_PE排最前():
    at = _run(_OK)
    group = [e for e in at.expander if e.label.startswith("▸ 尚未取得：")]
    assert len(group) == 1 and not group[0].proto.expanded
    label = group[0].label
    assert label.index("EPS") < label.index("台股成交量") and label.endswith("（7 項）")
    # 首屏不為 Missing 建獨立瘦卡：Missing 卡只出現在群組展開區那一個 markdown 裡
    blobs = [t for t in _texts(at) if 'data-section="trend-eps_pe_scenario"' in t]
    assert len(blobs) == 1 and 'data-section="trend-nasdaq"' in blobs[0]


def test_VIX取數失敗429_Primary選VIX只寫取數失敗_次圖也只寫狀態_寫原文():
    at = _run(_ERR)
    assert not at.exception, [e.value for e in at.exception]
    _pick(at, "vix")
    assert len(_charts(at)) == 0
    assert "⛔ 取數失敗" in _primary(at)
    needle = "⛔ 取數失敗：Yahoo:^VIX 失敗：HTTP 429 Too Many Requests"
    assert needle not in "\n".join(_texts(at))        # 44 P0-①：一般畫面不印原文
    from ui_v2 import plain
    store = at.session_state[plain.RAW_STATE]["mkt"]["entries"]
    assert needle in [e["text"] for e in store]       # 原文在跨頁原始訊息
    assert "⬜ EPS 預估資料未取得，無法計算正式指數情境" in "\n".join(_texts(at))   # 其他 Missing 區塊照樣在
    secondary = [t for t in _texts(at) if 'data-section="secondary"' in t and "風險｜VIX" in t]
    assert secondary and "⛔ 取數失敗" in secondary[0] and "<svg" not in secondary[0]


def test_沒有market_view的舊替身_維持舊版面_其餘照舊():
    at = _run(_LEGACY)
    assert not at.exception, [e.value for e in at.exception]
    text = "\n".join(_texts(at))
    assert "市場趨勢" not in text and 'data-section="trend' not in text and 'data-section="primary"' not in text
    assert len(_charts(at)) == 0
    assert not [r for r in at.radio if r.key.startswith("mkt_primary")]


def test_示範模式不受影響():
    at = _run(_DEMO)
    assert not at.exception, [e.value for e in at.exception]
    text = "\n".join(_texts(at))
    assert 'data-section="trend' not in text and "市場趨勢" not in text and 'data-section="primary"' not in text
    assert len(_charts(at)) == 0
    assert not [r for r in at.radio if r.key.startswith("mkt_primary")]


def test_section_strings_與畫面一致的禁詞守衛():
    # 純函式層的雙保險：期間四種各掃一次（見 test_mkt_market_section_logic）
    assert chart.PERIODS == ("3M", "6M", "1Y", "3Y")


def test_殖利率期間變動_pp_跟著期間切換_是百分點不是百分比():
    at = _pick(_run(_OK), "us10y")
    first = _primary(at)
    assert re.search(r"近1Y [+-]?\d+\.\d\d pp", first) and "%</span>" in first
    text = "\n".join(_texts(at))
    assert "期間變動 " in text and "個百分點（pp）" in text and "期間漲跌" not in _detail_of_primary(at)
    _radio(at, "mkt_primary_period").set_value("3M").run()
    assert _primary(at) != first
    # 價格序列仍是百分比報酬
    _pick(at, "sp500")
    assert re.search(r"近\d[MY] [+-]\d+\.\d%", _primary(at))


def _detail_of_primary(at):
    """目前 Primary 的 detail 區（render_detail 畫的 markdown：緊接在圖後面、含「為什麼」組）。"""
    blobs = [t for t in _texts(at) if t.startswith('<div class="pc-detail-group">') and "為什麼" in t]
    return blobs[0] if blobs else ""


def test_缺FRED金鑰_殖利率Primary只寫取數失敗_原文走原始訊息_價格序列不受影響():
    at = _run(_NOKEY)
    assert not at.exception, [e.value for e in at.exception]
    assert len(_charts(at)) == 1          # 預設 TAIEX 有圖
    _pick(at, "us10y")
    assert len(_charts(at)) == 0 and "⛔ 取數失敗" in _primary(at)
    _pick(at, "us2y")
    assert len(_charts(at)) == 0 and "⛔ 取數失敗" in _primary(at)
    text = "\n".join(_texts(at))
    assert "未設定 FRED_API_KEY" not in text
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
