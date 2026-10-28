# -*- coding: utf-8 -*-
"""BL-0520 Cross-View 特徵化測試 C1～C9（`DEC-2026-10-28-01`、`DEC-2026-10-28-03`；規格見 `docs/v2/69` 第 8 節）。

描述現況，不代表核准現況語意。

這份檔案的每一個斷言都是「現在程式實際做的事」，**不是**規格、**不是**客戶核准的語意：

- `test_char_agreement_*`：兩條路徑今天給出相同的值／日期／來源標籤。
- `test_char_divergence_*`：兩條路徑今天給出不同的值、日期或來源標籤；斷言的就是**目前的分歧**，
  讓它成為可重跑的證據。有人靜默修好或靜默改壞，測試會變紅，逼人回來更新 `docs/v2/69` 的實測結果表。
- 最後一節 `test_desired_*`：**期望不變量**（X1～X4），用 `xfail(strict=True)` 表達「canonical 層完成後應該成立」，
  同樣不是核准語意；strict 的用意是有人未計畫地修好時 CI 變紅。

硬約束：不打網路（Yahoo／FRED／MoneyDJ 等一律替身）、不讀試算表、不改任何 production 程式。
來源優先序、canonical identity、`get_latest_nav`、估值、FX 切日、報酬公式、新鮮度容差，本檔一律只量測、不改。
「會造成使用者看到不同數值」只在同一組替身輸入經兩條程式路徑得到不同值時才主張；其餘標「機制」。

本地執行備註：本機沒有 pandera，執行 C4 時以環境外的外掛把 `shared.schemas` 換成空操作（只影響 schema 驗證，不影響快取鍵與呼叫次數）；
CI 有真的 pandera。
"""

from __future__ import annotations

import ast
import datetime
import importlib
import math
import pathlib
import textwrap

import pandas as pd
import pytest

import _xview_fixtures as X
from _xview_fixtures import MARKER, yf_series

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_TAB3 = _ROOT / "ui" / "tab3_portfolio.py"


@pytest.fixture(autouse=True)
def _clean_caches():
    """每個測試前後清掉所有已註冊的 L1/L2 快取，讓呼叫次數可重現。"""
    from infra.cache import clear_all_caches
    clear_all_caches()
    yield
    clear_all_caches()


def _domains(view):
    """`build_market_view` 的 `domains`（list of dict）→ 以 `domain` 名稱為鍵的 dict。"""
    return {d["domain"]: d for d in view["domains"]}


def _close(a, b):
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)


# ═════════════════════════════════════════════════════════════════════════════
# C1／C2／C3／C4／C9：Yahoo 指數類（VIX、TAIEX、S&P 500）
# ═════════════════════════════════════════════════════════════════════════════

_VIX_CLOSED = (["2026-10-22", "2026-10-23", "2026-10-26"], [20.0, 21.5, 19.25])
_VIX_WITH_TODAY = (["2026-10-22", "2026-10-23", "2026-10-26", "2026-10-27"], [20.0, 21.5, 19.25, 25.0])


def _install_bline_and_view(monkeypatch, series_by_ticker):
    """把 `market_indicator.fetch_yf_close_with_error` 換成替身（B 線與 `market_view` 都經這個屬性取數），並記錄呼叫。"""
    from services.v2_tables import market_indicator as mi
    calls = []

    def fake(ticker, *args):
        calls.append((ticker, *args))
        s = series_by_ticker[ticker]
        out = s.copy()
        out.attrs = dict(s.attrs)
        return out, None

    monkeypatch.setattr(mi, "fetch_yf_close_with_error", fake)
    return calls


def test_char_agreement_c1_vix_value_and_obs_date_equal_between_bline_and_view(monkeypatch):
    """描述現況，不代表核准現況語意。C1：同一個替身餵 B 線 `vol_index` 與 🌍 `market_view` 的 VIX：obs_date、值、取得時間相等。
    這只證明「下游轉換邏輯在共用同一個替身時一致」，不是兩次獨立取數的來源一致；替身 `exchange_tz` 為 `Etc/UTC`，交易所時區換算規則在此未被施測。"""
    from services.v2_tables import market_indicator as mi, market_view as mv
    _install_bline_and_view(monkeypatch, {"^VIX": yf_series("^VIX", *_VIX_CLOSED),
                                          "^TWII": yf_series("^TWII", *_VIX_CLOSED),
                                          "^GSPC": yf_series("^GSPC", *_VIX_CLOSED)})
    rows = [r for r in mi.build_market_indicator_table()["rows"] if r["indicator_key"] == "vol_index"]
    dom = _domains(mv.build_market_view(fred_api_key=None))["vix"]
    assert dom["status"] == "ok"
    assert rows[-1]["obs_date"] == dom["obs_date"] == "2026-10-26"
    assert _close(rows[-1]["value_num"], 19.25) and _close(dom["points"][-1]["value_num"], 19.25)
    assert rows[-1]["fetched_at"] == dom["fetched_at"] == X.FETCHED


def test_char_divergence_c1_bline_and_view_call_yahoo_with_different_range_arguments(monkeypatch):
    """描述現況，不代表核准現況語意。C1：B 線以 `("^VIX",)` 取數（預設 2y），`market_view` 以 `("^VIX", "5y")` 取數；
    兩者在 L1 是不同呼叫形式（快取鍵見 C4），同一個 view 內出現兩份獨立取數。"""
    from services.v2_tables import market_indicator as mi, market_view as mv
    calls = _install_bline_and_view(monkeypatch, {t: yf_series(t, *_VIX_CLOSED) for t in ("^VIX", "^TWII", "^GSPC")})
    mi.build_market_indicator_table()
    mv.build_market_view(fred_api_key=None)
    assert calls == [("^VIX",), ("^VIX", "5y"), ("^TWII", "5y"), ("^GSPC", "5y")]


def test_char_divergence_c1_bline_row_carries_no_source_label_but_view_domain_does(monkeypatch):
    """描述現況，不代表核准現況語意。C1：B 線 `vol_index` 列只有 `source_tier`＝「市場指標」，沒有逐來源標籤；
    `market_view` 的 vix domain 帶 `source`＝`Yahoo:^VIX`。同一個數字在兩處的血緣可見度不同（機制；數值相同）。"""
    from services.v2_tables import market_indicator as mi, market_view as mv
    _install_bline_and_view(monkeypatch, {t: yf_series(t, *_VIX_CLOSED) for t in ("^VIX", "^TWII", "^GSPC")})
    row = [r for r in mi.build_market_indicator_table()["rows"] if r["indicator_key"] == "vol_index"][-1]
    dom = _domains(mv.build_market_view(fred_api_key=None))["vix"]
    assert "source" not in row and row["source_tier"] == "市場指標"
    assert dom["source"] == "Yahoo:^VIX"


def test_char_agreement_c2_no_second_path_exists_for_twii_gspc_us10y_us2y_in_bline():
    """描述現況，不代表核准現況語意。C2：B 線（`INDICATOR_SPECS`）今天沒有 `^TWII`／`^GSPC` 的 Yahoo 鍵，也沒有 `DGS10`／`DGS2` 的 FRED 鍵，
    所以這四個在 vNext 內部沒有第二條路徑可比較（「尚無法驗證」＝結構上沒有可比對的兩份；不是已證實一致）。"""
    from services.v2_tables import market_indicator as mi
    tickers = {spec["source"][1] for spec in mi.INDICATOR_SPECS.values() if spec["source"][0] == "Yahoo"}
    fred_ids = {spec["source"][1] for spec in mi.INDICATOR_SPECS.values() if spec["source"][0] == "FRED"}
    assert tickers == {"^VIX", "USDTWD=X"}
    assert not ({"^TWII", "^GSPC"} & tickers)
    assert not ({"DGS10", "DGS2"} & fred_ids)


def test_char_agreement_c2_view_twii_and_gspc_use_five_year_range_and_report_stub_last_bar(monkeypatch):
    """描述現況，不代表核准現況語意。C2：`market_view` 的 `^TWII`／`^GSPC` 以 `"5y"` 取數，最新觀測日與值＝替身最後一根已收盤的 K 棒
    （轉換邏輯對替身的反應；替身 `exchange_tz` 為 `Etc/UTC`，台北／紐約時區規則未被施測，也不是來源一致的證明）。"""
    from services.v2_tables import market_view as mv
    calls = _install_bline_and_view(monkeypatch, {
        "^VIX": yf_series("^VIX", *_VIX_CLOSED),
        "^TWII": yf_series("^TWII", ["2026-10-23", "2026-10-26"], [28000.5, 28100.25]),
        "^GSPC": yf_series("^GSPC", ["2026-10-23", "2026-10-26"], [7000.0, 7010.5])})
    d = _domains(mv.build_market_view(fred_api_key=None))
    assert [c for c in calls if c[0] in ("^TWII", "^GSPC")] == [("^TWII", "5y"), ("^GSPC", "5y")]
    assert (d["taiex"]["obs_date"], d["taiex"]["points"][-1]["value_num"]) == ("2026-10-26", 28100.25)
    assert (d["sp500"]["obs_date"], d["sp500"]["points"][-1]["value_num"]) == ("2026-10-26", 7010.5)
    assert d["taiex"]["source"] == "Yahoo Finance (^TWII)" and d["sp500"]["source"] == "Yahoo Finance (^GSPC)"


def test_char_divergence_c3_legacy_vix_takes_last_bar_but_view_excludes_unclosed_bar(monkeypatch):
    """描述現況，不代表核准現況語意。C3：替身最後一根是「取得時間當天（UTC）」的未收盤 K 棒（25.0）。
    舊版 `get_latest_vix` 取 `iloc[-1]`＝25.0；vNext `market_view` 排除未收盤那根，最新是 2026-10-26 的 19.25。
    同一個替身輸入、兩條程式路徑、兩個值（會造成使用者看到不同數值；前提：Yahoo 真的在收盤前回該根，屬替身假設）。"""
    import repositories.macro.yf as yf
    from services.fund_service import get_latest_vix
    from services.v2_tables import market_view as mv
    series = yf_series("^VIX", *_VIX_WITH_TODAY)
    monkeypatch.setattr(yf, "fetch_yf_close", lambda ticker, range_="2y", interval="1d": series)
    _install_bline_and_view(monkeypatch, {t: yf_series(t, *_VIX_WITH_TODAY) for t in ("^VIX", "^TWII", "^GSPC")})
    legacy = get_latest_vix()
    dom = _domains(mv.build_market_view(fred_api_key=None))["vix"]
    assert legacy == 25.0
    assert dom["obs_date"] == "2026-10-26" and _close(dom["points"][-1]["value_num"], 19.25)
    assert not _close(legacy, dom["points"][-1]["value_num"])


def test_char_agreement_c3_legacy_vix_equals_view_when_last_bar_is_closed(monkeypatch):
    """描述現況，不代表核准現況語意。C3：替身最後一根已收盤時，舊版 `get_latest_vix` 與 vNext VIX 相等（19.25）；
    注意舊版沒有日期可比，只能比值。"""
    import repositories.macro.yf as yf
    from services.fund_service import get_latest_vix
    from services.v2_tables import market_view as mv
    series = yf_series("^VIX", *_VIX_CLOSED)
    monkeypatch.setattr(yf, "fetch_yf_close", lambda ticker, range_="2y", interval="1d": series)
    _install_bline_and_view(monkeypatch, {t: yf_series(t, *_VIX_CLOSED) for t in ("^VIX", "^TWII", "^GSPC")})
    assert _close(get_latest_vix(), _domains(mv.build_market_view(fred_api_key=None))["vix"]["points"][-1]["value_num"])


def test_char_divergence_c4_fetch_yf_close_cache_key_depends_on_call_form(monkeypatch):
    """描述現況，不代表核准現況語意。C4：以計數的 `fetch_url` 替身（不打網路），對真的 `fetch_yf_close` 用六種呼叫形式取 `^VIX`：
    `("^VIX")`×2、`("^VIX","5y")`、`("^VIX", range_="5y")`、`("^VIX","5y","1d")`、`("^VIX","2y")` → 實際取數 5 次（只有完全相同的形式才共用快取）。
    再經 `fetch_yf_close_with_error("^VIX","5y")` → 命中 `("^VIX","5y","1d")` 的條目，不再取數。"""
    import repositories.macro.yf as yf
    seen = []

    def fake_fetch_url(url, params=None, **kwargs):
        seen.append((url.rsplit("/", 1)[-1], dict(params)["range"], dict(params)["interval"]))
        return X.FakeChartResponse(["2026-10-22", "2026-10-23", "2026-10-26"], [20.0, 21.5, 19.25])

    monkeypatch.setattr(yf, "fetch_url", fake_fetch_url)
    yf.fetch_yf_close("^VIX")
    yf.fetch_yf_close("^VIX")
    yf.fetch_yf_close("^VIX", "5y")
    yf.fetch_yf_close("^VIX", range_="5y")
    yf.fetch_yf_close("^VIX", "5y", "1d")
    yf.fetch_yf_close("^VIX", "2y")
    assert seen == [("^VIX", "2y", "1d"), ("^VIX", "5y", "1d"), ("^VIX", "5y", "1d"), ("^VIX", "5y", "1d"),
                    ("^VIX", "2y", "1d")]
    series, error = yf.fetch_yf_close_with_error("^VIX", "5y")
    assert error is None and len(series) == 3 and len(seen) == 5


def test_char_agreement_c4_same_call_form_shares_one_cache_entry_with_identical_fetched_at(monkeypatch):
    """描述現況，不代表核准現況語意。C4：完全相同的呼叫形式第二次命中快取，`fetched_at` 與第一次相同（快取內是原始取得時間）。"""
    import repositories.macro.yf as yf
    n = []
    monkeypatch.setattr(yf, "fetch_url", lambda url, params=None, **k: (n.append(1), X.FakeChartResponse(["2026-10-26"], [19.25]))[1])
    first = yf.fetch_yf_close("^VIX", "5y")
    second = yf.fetch_yf_close("^VIX", "5y")
    assert len(n) == 1 and first.attrs["fetched_at"] == second.attrs["fetched_at"]
    assert first.attrs["source"] == "Yahoo:^VIX"


def test_char_agreement_c9_direct_literal_vix_fetch_call_sites_match_the_current_list():
    """描述現況，不代表核准現況語意。C9：以 AST 數出 production 程式中「第一個參數是字面 `"^VIX"` 的 `fetch_yf_close*` 呼叫」，
    目前恰為五處（下列清單是現況棘輪，不是核准；新增直接呼叫點會紅，逼人登記）。其中 `services/macro/us_indicators.py` 是經包裝函式 `_yf_iso("^VIX","5y")` 的字面呼叫。
    限制：只抓名稱在集合內（含包裝 `_yf_iso`／`_yf_s`）且第一參數為字面的呼叫；以常數（如 `market_view.VIX_TICKER`）或變數傳入、或其他包裝名稱的呼叫抓不到，所以這不是「全站只有這幾處」的證明。"""
    import subprocess
    files = subprocess.check_output(["git", "ls-files", "*.py"], cwd=_ROOT, text=True).split()
    names = {"fetch_yf_close", "fetch_yf_close_with_error", "_yf_close", "_yf_iso", "_yf_s"}
    hits = []
    for rel in files:
        if rel.startswith("tests/"):
            continue
        try:
            tree = ast.parse((_ROOT / rel).read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                nm = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)
                if nm in names and node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "^VIX":
                    hits.append(rel)
    assert sorted(hits) == ["services/fund_service.py", "services/liquidity_engine.py",
                            "services/macro/us_indicators.py", "services/risk_radar.py", "services/risk_radar.py"]
    from services.v2_tables import market_view as mv
    assert mv.VIX_TICKER == "^VIX"  # 非字面（常數）的呼叫點：上面的掃描看不到它


# ═════════════════════════════════════════════════════════════════════════════
# C5：基金 NAV —— 呼叫形式、入口、Sheet nav_history、get_latest_nav
# ═════════════════════════════════════════════════════════════════════════════

_URL_JJ1 = "https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=ZZF100"
_URL_JJ0 = "https://www.moneydj.com/funddj/ya/yp010000.djhtm?a=ZZF100"
_NOW = datetime.datetime(2026, 3, 10, tzinfo=datetime.timezone.utc)


def _install_chain(monkeypatch, *, nav_history_points=None):
    """A 鏈離線替身（沿用 `tests/_a_chain_stub.py`）：全成功情境，序列 300 筆，最後一筆 2026-02-27／12.99，來源 `FundClear:GetFundNAV`；
    meta 純量 `nav_latest`＝10.24（與序列末值刻意不同，用來量「純量與序列互不核對」）。回傳記錄來源呼叫的 list。"""
    import _a_chain_stub as H
    code, scenario = H.full_success_scenario("ZZF100", currency="USD")
    if nav_history_points is not None:
        scenario = dict(scenario, nav_history_points=nav_history_points)
    return H.install(monkeypatch, scenario)


def _fundclear_calls(calls):
    return sum(1 for c in calls if c[0] == "_src_fundclear_nav")


def _last(series):
    return str(series.index[-1])[:10], float(series.iloc[-1]), series.attrs.get("source")


def test_char_divergence_c5_call_forms_bare_code_lowercase_and_urls_each_miss_the_l1_cache(monkeypatch):
    """描述現況，不代表核准現況語意。C5／G-NAV-1：同一檔基金以 `"ZZF100"`、`"ZZF100"`（重複）、yp010001 網址、`"zzf100"`、yp010000 網址
    依序經舊版 enriched 入口取數 → 來源瀑布（FundClear 替身）累計呼叫 1,1,2,3,4 次：不同字串各自一個快取條目。"""
    from services.fund_service import fetch_fund_from_moneydj_url_enriched as enr
    calls = _install_chain(monkeypatch)
    counts = []
    for arg in ("ZZF100", "ZZF100", _URL_JJ1, "zzf100", _URL_JJ0):
        enr(arg)
        counts.append(_fundclear_calls(calls))
    assert counts == [1, 1, 2, 3, 4]


def test_char_agreement_c5_code_built_url_shares_cache_with_the_pasted_yp010000_url(monkeypatch):
    """描述現況，不代表核准現況語意。C5：`auto_fetch_moneydj("ZZF100")` 先試的網址＝`build_moneydj_url` 組出的 yp010000 字串，
    與使用者貼的 yp010000 網址逐字相同 → 共用 L1 條目（來源瀑布只跑一次）；回傳頁型為 yp010000。"""
    from services.fund_service import fetch_fund_from_moneydj_url_enriched as enr
    from services.moneydj_fetcher import auto_fetch_moneydj
    calls = _install_chain(monkeypatch)
    enr(_URL_JJ0)
    assert _fundclear_calls(calls) == 1
    res, page_type = auto_fetch_moneydj("ZZF100", return_page_type=True)
    assert page_type == "yp010000" and _fundclear_calls(calls) == 1 and res["full_key"] == "ZZF100"


def test_char_divergence_c5_bare_code_tries_domestic_page_first_then_overseas_page(monkeypatch):
    """描述現況，不代表核准現況語意。C5：純代碼走 `auto_fetch_moneydj`：先 yp010000、結果不完整再 yp010001；網址形式則直接用貼上的那一個，
    不重試另一個頁型。（以替身記錄 enriched 入口收到的網址順序。）"""
    import services.fund_service as fs
    from services.moneydj_fetcher import auto_fetch_moneydj
    _install_chain(monkeypatch)
    original = fs.fetch_fund_from_moneydj_url_enriched
    urls = []

    def recorder(url, oauth_client=None):
        urls.append(url)
        if "yp010000" in url:
            return {"error": "stub: 第一個頁型沒有序列", "series": None}
        return original(url, oauth_client=oauth_client)

    monkeypatch.setattr(fs, "fetch_fund_from_moneydj_url_enriched", recorder)
    res, page_type = auto_fetch_moneydj("ZZF100", return_page_type=True)
    assert urls == [_URL_JJ0, _URL_JJ1] and page_type == "yp010001"
    urls.clear()
    _, page_type_url = auto_fetch_moneydj(_URL_JJ1, return_page_type=True)
    assert urls == [_URL_JJ1] and page_type_url == "yp010001"


def test_char_agreement_c5_every_call_form_returns_same_last_nav_date_and_source(monkeypatch):
    """描述現況，不代表核准現況語意。C5：裸代碼、小寫、兩種網址、`auto_fetch_moneydj` 對同一組替身，序列末筆的（日期、值、來源標籤）全部相同：
    （2026-02-27、12.99、`FundClear:GetFundNAV`）；`metrics["nav"]` 也是 12.99。"""
    from services.fund_service import fetch_fund_from_moneydj_url_enriched as enr
    from services.moneydj_fetcher import auto_fetch_moneydj
    _install_chain(monkeypatch)
    results = [enr(a) for a in ("ZZF100", "zzf100", _URL_JJ1, _URL_JJ0)] + [auto_fetch_moneydj("ZZF100")]
    lasts = {_last(r["series"]) for r in results}
    assert lasts == {("2026-02-27", 12.99, "FundClear:GetFundNAV")}
    assert {r["metrics"]["nav"] for r in results} == {12.99}


def test_char_divergence_c5_scalar_nav_latest_and_series_last_are_not_reconciled(monkeypatch):
    """描述現況，不代表核准現況語意。C5／G-NAV-6：結果 dict 同時帶 meta 純量 `nav_latest`（替身 10.24）與序列末值（12.99，也是 `metrics["nav"]`），
    程式沒有核對兩者（`nav_date` 純量在此替身下為空字串）。機制已證實；「使用者實際看到哪個」取決於頁面讀哪個欄位（tab2 banner 讀純量），未在此量測。"""
    from services.fund_service import fetch_fund_from_moneydj_url_enriched as enr
    _install_chain(monkeypatch)
    r = enr("ZZF100")
    assert r["nav_latest"] == 10.24 and r["nav_date"] == ""
    assert float(r["series"].iloc[-1]) == 12.99 and r["metrics"]["nav"] == 12.99


def _vnext_nav_dataset(monkeypatch, *, nav_history_points=None):
    from services.v2_tables import nav_dividend as nd
    _install_chain(monkeypatch, nav_history_points=nav_history_points)
    fund = {"fund_code": "ZZF100", "full_key": "ZZF100", "chain_code": "ZZF100", "holding_ccy": "USD"}
    return nd.build_nav_table([fund], now=_NOW)


def test_char_agreement_c5_vnext_hld_nav_row_and_alo_latest_nav_equal_legacy_series_last(monkeypatch):
    """描述現況，不代表核准現況語意。C5：沒有 Sheet 累積點時，vNext `build_nav_table`（hld 入口）最後一列與 ⚖️ alo 的 `latest_nav`
    都等於舊版序列末筆（2026-02-27、12.99），來源標籤 `FundClear:GetFundNAV`。"""
    from services.fund_service import fetch_fund_from_moneydj_url_enriched as enr
    from ui_v2.alo import logic as alo
    table = _vnext_nav_dataset(monkeypatch)
    legacy_date, legacy_value, legacy_source = _last(enr("ZZF100")["series"])
    row = table["rows"][-1]
    assert (row["nav_date"], row["nav_orig_ccy"], row["ccy"]) == (legacy_date, legacy_value, "USD") == ("2026-02-27", 12.99, "USD")
    assert table["provenance"]["ZZF100"]["source"] == legacy_source == "FundClear:GetFundNAV"
    assert alo.latest_nav({"nav": table["rows"]}, "ZZF100")["nav_orig_ccy"] == 12.99


_SHEET_NEWER = [{"code": "ZZF100", "date": "2026-03-05", "nav": 99.0, "fund_name": "", "source": "app",
                 "recorded_at": "2026-03-05T09:00:00+00:00", "currency": "USD"}]
_SHEET_OLDER = [{"code": "ZZF100", "date": "2024-12-02", "nav": 8.0, "fund_name": "", "source": "app",
                 "recorded_at": "2024-12-02T09:00:00+00:00", "currency": "USD"}]


def test_char_divergence_c5_sheet_nav_history_newer_point_changes_legacy_latest_nav_but_not_vnext(monkeypatch):
    """描述現況，不代表核准現況語意。C5／G-NAV-2／G-SHEET-1：Sheet `nav_history` 有一筆比 live 序列更新的點（2026-03-05／99.0，替身）。
    舊版 enriched 入口併入它：序列末筆 99.0（2026-03-05），`metrics["nav"]`＝99.0，序列 301 筆；vNext `build_nav_table` 因
    `NAV_HISTORY_PROVENANCE_VERIFIED=False` 不採用累積表：最新列 12.99（2026-02-27），並在 provenance 標 `gate_closed`。
    同一組替身、兩條路徑、兩個最新 NAV（會造成使用者看到不同數值；前提：Sheet 真有比 live 新的點，屬替身假設）。"""
    from services.fund_service import fetch_fund_from_moneydj_url_enriched as enr
    from services.v2_tables import nav_dividend as nd
    assert nd.NAV_HISTORY_PROVENANCE_VERIFIED is False
    calls = _install_chain(monkeypatch, nav_history_points=_SHEET_NEWER)
    legacy = enr("ZZF100")
    assert _last(legacy["series"])[:2] == ("2026-03-05", 99.0) and legacy["metrics"]["nav"] == 99.0
    from infra.cache import clear_all_caches
    clear_all_caches()
    table = _vnext_nav_dataset(monkeypatch, nav_history_points=_SHEET_NEWER)
    assert (table["rows"][-1]["nav_date"], table["rows"][-1]["nav_orig_ccy"]) == ("2026-02-27", 12.99)
    prov = table["provenance"]["ZZF100"]["nav_history"]
    assert prov["gate_closed"] is True and prov["written"] == 0
    assert calls  # 替身確實被呼叫（沒有走網路）


def test_char_divergence_c5_sheet_nav_history_older_point_leaves_latest_equal_but_history_length_differs(monkeypatch):
    """描述現況，不代表核准現況語意。C5：Sheet 累積點比 live 起點更早（2024-12-02／8.0）。最新 NAV 兩條路徑相同（12.99／2026-02-27），
    但舊版序列多一筆（301 vs vNext 300 列），影響以列數／序列起點計算的報酬窗口（見 C6）。"""
    from services.fund_service import fetch_fund_from_moneydj_url_enriched as enr
    _install_chain(monkeypatch, nav_history_points=_SHEET_OLDER)
    legacy = enr("ZZF100")
    from infra.cache import clear_all_caches
    clear_all_caches()
    table = _vnext_nav_dataset(monkeypatch, nav_history_points=_SHEET_OLDER)
    assert _last(legacy["series"])[:2] == (table["rows"][-1]["nav_date"], table["rows"][-1]["nav_orig_ccy"]) == ("2026-02-27", 12.99)
    assert len(legacy["series"]) == 301 and len(table["rows"]) == 300


def _guard_other_nav_sources(monkeypatch):
    """`get_latest_nav` 的第 2～4 順位來源一律換成「被呼叫就失敗」，確保測試不會悄悄打網路。"""
    import repositories.fund.fx_and_main as fm

    def boom(*a, **k):
        raise AssertionError("get_latest_nav 不應走到第 2～4 順位來源")

    for name in ("_src_yahoo_finance_nav", "_src_cnyes_nav", "_src_morningstar_nav"):
        monkeypatch.setattr(fm, name, boom)


def test_char_divergence_c5_get_latest_nav_prefers_yahoo_and_returns_bare_float_unlike_the_a_chain(monkeypatch):
    """描述現況，不代表核准現況語意。C5／G-NAV-3：Yahoo 以基金代碼為 ticker 有值（替身 11.11）時，`get_latest_nav` 直接回 11.11（裸 float，無日期、無來源）；
    同一檔基金的 A 鏈（FundClear 替身）回 12.99／2026-02-27／`FundClear:GetFundNAV`。T7 市值走前者、單一基金頁走後者。
    機制已證實（來源優先序不同）；11.11 vs 12.99 的數值差異來自兩個 stub 輸入刻意設成不同，**不是**「同一輸入、兩條路徑」的證據。"""
    import repositories.macro_repository as mr
    from services.fund_service import fetch_fund_from_moneydj_url_enriched as enr, get_latest_nav
    _install_chain(monkeypatch)
    _guard_other_nav_sources(monkeypatch)
    ysr = yf_series("ZZF100", ["2026-02-26", "2026-02-27"], [11.0, 11.11], currency="USD")
    monkeypatch.setattr(mr, "fetch_yf_close", lambda t, range_="2y", interval="1d": ysr)
    latest = get_latest_nav("ZZF100", "USD")
    chain_date, chain_value, chain_source = _last(enr("ZZF100")["series"])
    assert isinstance(latest, float) and latest == 11.11
    assert (chain_date, chain_value, chain_source) == ("2026-02-27", 12.99, "FundClear:GetFundNAV")
    assert not _close(latest, chain_value)


def test_char_agreement_c5_get_latest_nav_fails_closed_when_expected_currency_is_empty(monkeypatch):
    """描述現況，不代表核准現況語意。C5：呼叫端明示幣別未知（`expected_ccy=""`）時，Yahoo 非原生報價一律不採用；
    本測試把後續來源換成會失敗的替身，所以只驗證「Yahoo 值沒被採用」這一步（結果會往後掉，不在此量測後續來源）。"""
    import repositories.fund.fx_and_main as fm
    import repositories.macro_repository as mr
    ysr = yf_series("ZZF100", ["2026-02-27"], [11.11], currency="USD")
    monkeypatch.setattr(mr, "fetch_yf_close", lambda t, range_="2y", interval="1d": ysr)
    monkeypatch.setattr(fm, "_src_yahoo_finance_nav", lambda c: pd.Series(dtype=float))
    monkeypatch.setattr(fm, "_src_cnyes_nav", lambda c: pd.Series(dtype=float))
    monkeypatch.setattr(fm, "_src_morningstar_nav", lambda c: pd.Series(dtype=float))
    assert fm.get_latest_nav("ZZF100", expected_ccy="") is None


# ═════════════════════════════════════════════════════════════════════════════
# C5b：識別鍵推導（同一組輸入經各函式）
# ═════════════════════════════════════════════════════════════════════════════

_IDENTITY_INPUTS = {
    "bare": "ACDD01",
    "lower": "acdd01",
    "suffix": "ACDD01-EQTAL005",
    "suffix_lower": "acdd01-eqtal005",
    "url_overseas": "https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=ACDD01",
    "url_platform_suffix": "https://chubb.moneydj.com/w/wr/wr01.djhtm?a=ACDD01-EQTAL005",
    "url_mobile_lower": "https://m.moneydj.com/a1.aspx?a=acdd01",
    "url_fragment": "https://www.moneydj.com/funddj/ya/yp010001.djhtm?A=ACDD01#frag",
    "url_decoy_param": "https://www.moneydj.com/funddj/ya/yp010001.djhtm?area=TW&a=ACDD01",
}


def _identity_table():
    from repositories.fund.sources import canonicalize_moneydj_url, parse_moneydj_input
    from repositories.policy.v1 import _extract_code_from_url
    from services.moneydj_fetcher import build_moneydj_url
    from services.v2_tables.fund_keys import resolve_full_keys
    out = {}
    for name, raw in _IDENTITY_INPUTS.items():
        res = resolve_full_keys([raw], mapping={})["results"][0]
        out[name] = {
            "parse": parse_moneydj_input(raw)["code"],
            "canon_then_parse": parse_moneydj_input(canonicalize_moneydj_url(raw))["code"],
            "policy_extract": _extract_code_from_url(raw),
            "fund_keys": res["full_key"],
            "built_url_tail": build_moneydj_url(raw, "yp010001").rsplit("?", 1)[-1],
        }
    return out


def test_char_agreement_c5b_parse_canonicalize_and_fund_keys_agree_on_the_code_for_plain_inputs():
    """描述現況，不代表核准現況語意。C5b／G-ID-1：對裸碼、大小寫、平台後綴、三種網址形式，`parse_moneydj_input`、
    `canonicalize_moneydj_url`→`parse`、`fund_keys.resolve_full_keys` 三個推導給相同的代碼（大寫、平台後綴保留）。"""
    t = _identity_table()
    for name in ("bare", "lower", "url_overseas", "url_mobile_lower", "url_decoy_param"):
        assert {t[name]["parse"], t[name]["canon_then_parse"], t[name]["fund_keys"]} == {"ACDD01"}, name
    for name in ("suffix", "suffix_lower", "url_platform_suffix"):
        assert {t[name]["parse"], t[name]["canon_then_parse"], t[name]["fund_keys"]} == {"ACDD01-EQTAL005"}, name


def test_char_agreement_c5b_platform_suffix_is_kept_so_suffixed_and_plain_codes_are_different_keys():
    """描述現況，不代表核准現況語意。C5b：`ACDD01` 與 `ACDD01-EQTAL005` 在每個推導下都是不同的鍵（平台後綴被保留），
    即各推導一致地把兩者當成兩檔；它們是否其實是同一檔基金的不同 NAV 序列，程式裡沒有欄位可表達（G-ID-2／G-ID-3）。"""
    t = _identity_table()
    for fn in ("parse", "canon_then_parse", "policy_extract", "fund_keys"):
        assert t["bare"][fn] != t["suffix"][fn], fn


def test_char_divergence_c5b_policy_extract_keeps_url_fragment_that_the_other_derivations_drop():
    """描述現況，不代表核准現況語意。C5b／G-ID-1：同一個含 `#frag` 的網址，policy `_extract_code_from_url` 得 `ACDD01#FRAG`，
    parse／fund_keys 得 `ACDD01`。Sheet 政策列以前者推導代碼、NAV 取數以後者推導，鍵可能對不上（機制；真實政策列是否含 fragment 未驗）。"""
    t = _identity_table()["url_fragment"]
    assert t["policy_extract"] == "ACDD01#FRAG"
    assert {t["parse"], t["canon_then_parse"], t["fund_keys"]} == {"ACDD01"}


def test_char_divergence_c5b_policy_extract_takes_first_key_ending_with_a_or_code_not_the_a_parameter():
    """描述現況，不代表核准現況語意。C5b／G-ID-1：網址 `…?area=TW&a=ACDD01`（人工構造輸入），policy `_extract_code_from_url` 取第一個「key 以 a／code 結尾」的值＝`TW`，
    parse／fund_keys 取 `a=` 參數＝`ACDD01`。真實 MoneyDJ 網址是否出現此形態未驗（機制）。"""
    t = _identity_table()["url_decoy_param"]
    assert t["policy_extract"] == "TW"
    assert {t["parse"], t["fund_keys"]} == {"ACDD01"}


def test_char_divergence_c5b_build_moneydj_url_keeps_url_input_case_so_cache_strings_differ():
    """描述現況，不代表核准現況語意。C5b／G-NAV-1：`build_moneydj_url` 對裸碼轉大寫拼網址，對 http 開頭輸入原樣回傳；
    同一檔 `a=acdd01`（行動版小寫網址）與裸碼 `acdd01` 組出的字串不同，L1 快取以字串為鍵 → 條目不同。"""
    from services.moneydj_fetcher import build_moneydj_url
    from_code = build_moneydj_url("acdd01", "yp010001")
    from_url = build_moneydj_url("https://m.moneydj.com/a1.aspx?a=acdd01", "yp010001")
    assert from_code == "https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=ACDD01"
    assert from_url == "https://m.moneydj.com/a1.aspx?a=acdd01" and from_code != from_url


def test_char_agreement_c5b_no_canonical_id_or_share_class_symbol_exists_in_production_python():
    """描述現況，不代表核准現況語意。C5b／G-ID-2／G-ID-3：AST 掃 production `.py`，沒有名為 `canonical_id`／`share_class` 的函式、參數、變數或屬性
    （字面名稱掃描；不證明沒有以其他名稱表達同一概念）。"""
    import subprocess
    files = subprocess.check_output(["git", "ls-files", "*.py"], cwd=_ROOT, text=True).split()
    wanted = {"canonical_id", "share_class"}
    found = []
    for rel in files:
        if rel.startswith("tests/"):
            continue
        try:
            tree = ast.parse((_ROOT / rel).read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            ident = (node.id if isinstance(node, ast.Name) else node.arg if isinstance(node, ast.arg)
                     else node.attr if isinstance(node, ast.Attribute)
                     else node.name if isinstance(node, (ast.FunctionDef, ast.ClassDef)) else None)
            if ident in wanted:
                found.append((rel, ident))
    assert found == []


# ═════════════════════════════════════════════════════════════════════════════
# C6：報酬公式
# ═════════════════════════════════════════════════════════════════════════════

def _weekly_series():
    idx = pd.date_range("2023-01-06", periods=150, freq="7D")
    return pd.Series([10 + 0.05 * i for i in range(150)], index=idx)


def _daily_series():
    idx = pd.bdate_range("2025-01-06", periods=300)
    return pd.Series([10 + 0.01 * i for i in range(300)], index=idx)


def test_char_divergence_c6_weekly_series_row_window_one_year_versus_calendar_window(monkeypatch):
    """描述現況，不代表核准現況語意。C6／G-RET-3：150 個每週點（約 2.9 年）。`calc_metrics` 的 `ret_1y`（252 列窗）＝None；
    `ret_1y_total` 也用列數窗，實際窗口 1043 天、值 74.5%；vNext hld 的 `fund_metrics`（區間＝使用者選的日曆窗，此處取最後 365 日曆日）區間首末兩筆報酬＝17.5%；
    `ret_1m` 用 22 列＝約 22 週。同一個 NAV 序列、三種「近一年」口徑、三個數字（會造成使用者看到不同數值；週頻序列是替身假設，真實基金是否出現此稀疏度未驗）。"""
    from services.fund_service import calc_metrics
    from ui_v2.hld.logic import fund_metrics
    s = _weekly_series()
    m = calc_metrics(s, [])
    dataset = {"nav": [{"fund_code": "ZZF100", "nav_date": d.strftime("%Y-%m-%d"), "nav_orig_ccy": float(v), "ccy": "USD"}
                       for d, v in s.items()],
               "dividend": [], "holding": [{"fund_code": "ZZF100"}], "errors": {}}
    fund = {"fund_code": "ZZF100", "ccy": "USD", "units_shares": 100.0, "cost_twd": 1.0, "holding_id": "h1",
            "fund_name": "替身", "policy_id": "p", "category": "c"}
    # 視窗＝使用者選的區間；此處選「最後一筆往前 365 日曆日」（production 視窗來自 saved_window，不是固定 365 天）
    window = ((s.index[-1] - pd.Timedelta(days=365)).strftime("%Y-%m-%d"), s.index[-1].strftime("%Y-%m-%d"))
    hld = fund_metrics(dataset, fund, window)["區間報酬率"]["_raw"]
    assert m["ret_1y"] is None
    assert m["ret_1y_window_days"] == 1043 and _close(m["ret_1y_total"], 74.5)
    assert _close(hld, 17.508417508417494)
    assert m["ret_1m"] == 6.4  # 22 列（22 週），不是一個月


def test_char_divergence_c6_raw_ret_1y_total_versus_ssot_gate_resolve_1y_total_return():
    """描述現況，不代表核准現況語意。C6／G-RET-2（R4 閘門）：同一個週頻序列的 `metrics["ret_1y_total"]`（原始 74.5%，窗口 1043 天）
    經 `resolve_1y_total_return`：本函式只擋「窗口 < 350 天」與「缺窗口」，窗口過長（1043 天）不擋 → 仍回 ok／74.5。
    AI 與 tab3 表欄讀原始值、tab2 KPI 讀 SSOT：這個替身下兩者數字相同（不分歧），分歧僅在窗口 < 350 天時（下一個測試）。"""
    from services.fund_service import calc_metrics
    from services.fund_total_return import resolve_1y_total_return
    m = calc_metrics(_weekly_series(), [])
    res = resolve_1y_total_return({"metrics": m, "series": _weekly_series()})
    assert (res["status"], res["window_days"]) == ("ok", 1043) and _close(res["value_pct"], m["ret_1y_total"])


def test_char_divergence_c6_short_window_raw_ret_1y_total_has_value_but_ssot_gate_withholds_it():
    """描述現況，不代表核准現況語意。C6／G-RET-2：120 個營業日（窗口 < 350 天）。`calc_metrics` 的 `ret_1y_total` 有值，
    `resolve_1y_total_return` 回 `window_short`／value=None。tab3 表欄與 tab2 AI 快照讀原始值、tab2 KPI 讀 SSOT → 同一檔基金一邊有數字、一邊「⬜」
    （此為函式層量測；各 UI 欄位實際讀哪個，依 `docs/v2/69` 5.2 的讀碼結論，未在此渲染驗證）。"""
    from services.fund_service import calc_metrics
    from services.fund_total_return import resolve_1y_total_return
    s = _daily_series().iloc[:120]
    m = calc_metrics(s, [])
    res = resolve_1y_total_return({"metrics": m, "series": s})
    assert m["ret_1y_total"] is not None and m["ret_1y_window_days"] < 350
    assert res["status"] == "unavailable" and res["reason"] == "window_short" and res["value_pct"] is None


def test_char_agreement_c6_dense_daily_series_ret_1y_equals_ret_1y_total_without_dividends():
    """描述現況，不代表核准現況語意。C6：300 個營業日、無配息：`ret_1y`＝`ret_1y_total`＝23.95，窗口 351 天；
    `resolve_1y_total_return` 回 ok／23.95（SSOT 閘門在此情境與原始值一致）。"""
    from services.fund_service import calc_metrics
    from services.fund_total_return import resolve_1y_total_return
    s = _daily_series()
    m = calc_metrics(s, [])
    res = resolve_1y_total_return({"metrics": m, "series": s})
    assert m["ret_1y"] == m["ret_1y_total"] == 23.95 and m["ret_1y_window_days"] == 351
    assert (res["status"], res["value_pct"]) == ("ok", 23.95)


def test_char_divergence_c6_one_month_checkup_prefers_wb01_but_mk_dashboard_uses_self_calc(monkeypatch):
    """描述現況，不代表核准現況語意。C6／G-RET-1：同一個 fund dict：wb01 官方 `perf["1M"]`＝9.99、自算 `metrics["ret_1m"]`＝1.64。
    健診表的 `_period_ret` 回 9.99；衛星戰情室 `build_mk_dataframe` 的「近1M(%)」欄回 1.64。
    機制已證實（欄位選擇不同：wb01 優先 vs 只用自算）；9.99 vs 1.64 的數值差異來自 stub 輸入刻意設成不同，**不是**同一輸入的證據。"""
    log = []
    _fake, restore = X.swap_in_fake_streamlit(log)
    try:
        checkup = importlib.import_module("ui.helpers.fund.checkup")
        mk = importlib.import_module("ui.components.mk_dashboard")
        s = _daily_series()
        fund = {"code": "ZZF100", "name": "替身基金", "series": s, "loaded": True,
                "metrics": {"nav": 12.99, "ret_1m": 1.64, "ret_3m": 5.18},
                "moneydj_raw": {"perf": {"1M": 9.99}}}
        health_value = checkup._period_ret(fund, "1M", "ret_1m")
        mk_row = mk.build_mk_dataframe([fund]).iloc[0]
        assert health_value == 9.99
        assert mk_row["近1M(%)"] == 1.64
    finally:
        restore()


# ═════════════════════════════════════════════════════════════════════════════
# C7：FX 與估值
# ═════════════════════════════════════════════════════════════════════════════

def _usdtwd_bars(n=25):
    """n 個營業日、最後一根 2026-10-26（週一，值 31.4），之前每天遞減 0.05；供 `rows_from_daily_close` 的外匯最少根數門檻。"""
    idx = pd.bdate_range(end="2026-10-26", periods=n)
    values = [round(31.4 - 0.05 * (n - 1 - i), 4) for i in range(n)]
    return yf_series("USDTWD=X", [d.strftime("%Y-%m-%d") for d in idx], values)


def test_char_agreement_c7_fx_gate_is_closed_so_vnext_writes_no_usd_row_while_legacy_returns_latest(monkeypatch):
    """描述現況，不代表核准現況語意。C7／G-FX-1：`FX_OBS_DATE_RULE_VERIFIED` 目前是 False → B 線不取數、不寫 `fx_twd_per_usd` 列
    （pending＝`fx_obs_date_rule`）；舊版 `get_latest_fx("USDTWD")` 對同一組替身回最新價 31.4。
    vNext 對美元持股顯示「缺換算匯率」、舊版顯示 TWD 市值（本測試量到函式層差異；畫面字樣未在此渲染驗證）。"""
    import repositories.macro_repository as mr
    from services.fund_service import get_latest_fx
    from services.v2_tables import market_indicator as mi
    assert mi.FX_OBS_DATE_RULE_VERIFIED is False
    bars = _usdtwd_bars()
    calls = _install_bline_and_view(monkeypatch, {"^VIX": yf_series("^VIX", *_VIX_CLOSED), "USDTWD=X": bars})
    table = mi.build_market_indicator_table()
    assert table["pending"]["fx_twd_per_usd"] == "fx_obs_date_rule"
    assert [r for r in table["rows"] if r["indicator_key"] == "fx_twd_per_usd"] == []
    assert ("USDTWD=X",) not in calls
    monkeypatch.setattr(mr, "fetch_yf_close", lambda t, range_="2y", interval="1d": bars)
    assert get_latest_fx("USDTWD") == 31.4


def _fx_rows_with_gate_open(monkeypatch):
    from services.v2_tables import market_indicator as mi
    _install_bline_and_view(monkeypatch, {"^VIX": yf_series("^VIX", *_VIX_CLOSED), "USDTWD=X": _usdtwd_bars()})
    monkeypatch.setattr(mi, "FX_OBS_DATE_RULE_VERIFIED", True)
    return [r for r in mi.build_market_indicator_table()["rows"] if r["indicator_key"] == "fx_twd_per_usd"]


def test_char_divergence_c7_gate_open_vnext_fx_obs_date_is_previous_weekday_of_the_bar_date(monkeypatch):
    """描述現況，不代表核准現況語意。C7／G-FX-1（此測試**人工打開**閘門以量測規則本身；production 閘門仍關）：最後一根 K 棒日期 2026-10-26（週一），
    vNext 把它標成 obs_date＝2026-10-23（前一平日）、值 31.4；舊版 `get_latest_fx` 對同一根只回 31.4，沒有日期。"""
    rows = _fx_rows_with_gate_open(monkeypatch)
    assert (rows[-1]["obs_date"], rows[-1]["value_num"]) == ("2026-10-23", 31.4)
    assert (rows[-2]["obs_date"], rows[-2]["value_num"]) == ("2026-10-22", 31.35)


def test_char_divergence_c7_valuation_alo_fx_by_nav_date_versus_legacy_latest_fx(monkeypatch):
    """描述現況，不代表核准現況語意。C7／G-VAL-1／G-FX-1：持有 100 單位、NAV 10.0 USD、NAV 日 2026-10-22。
    ⚠️ 31350 只在**測試人為把 `FX_OBS_DATE_RULE_VERIFIED` 打開**時才存在；production 閘門關閉，vNext 目前對美元持股顯示「缺換算匯率」（函式層，見上一個 C7 測試），
    所以本測試證明的是「閘門開啟後的機制差異」，不是現況畫面上的數字差異。
    ⚖️ alo `basis_value` 取「obs_date ≤ NAV 日」的匯率列（2026-10-22／31.35）＝31350；舊版 `FundPosition.value_twd`／`enrich_returns` 用最新價 31.4＝31400。
    閘門人為開啟下兩套實作對同一組替身給不同市值（差 50 元，約 0.16%；NAV 日落後於最新匯率日時才出現，屬替身情境）。"""
    from models.ledger import FundPosition
    from services.portfolio_csv import enrich_returns
    from ui_v2.alo import logic as alo
    rows = _fx_rows_with_gate_open(monkeypatch)
    dataset = {"nav": [{"fund_code": "ZZF100", "nav_date": "2026-10-22", "nav_orig_ccy": 10.0, "ccy": "USD"}],
               "market_indicator": rows}
    holding = {"fund_code": "ZZF100", "units_shares": 100.0, "cost_twd": 30000.0}
    alo_value, reason = alo.basis_value(dataset, holding, alo.BASIS_MV)
    latest_fx = 31.4
    legacy_position = FundPosition(fund_code="ZZF100", units=100.0).value_twd(10.0, latest_fx)
    legacy_csv = enrich_returns([{"code": "ZZF100", "units": 100.0, "currency": "USD", "invest_twd": 30000.0, "policy": "P"}],
                                nav_by_code={"ZZF100": 10.0}, usdtwd=latest_fx)[0]["current_value_twd"]
    assert reason is None and _close(alo_value, 31350.0)
    assert _close(legacy_position, 31400.0) and _close(legacy_csv, 31400.0)
    assert not _close(alo_value, legacy_position)


def test_char_agreement_c7_valuation_legacy_position_and_enrich_returns_agree_for_same_nav_and_fx():
    """描述現況，不代表核准現況語意。C7／G-VAL-1：`FundPosition.value_twd` 與 `enrich_returns` 對同一個（單位、NAV、匯率）給相同市值（31400）。"""
    from models.ledger import FundPosition
    from services.portfolio_csv import enrich_returns
    a = FundPosition(fund_code="ZZF100", units=100.0).value_twd(10.0, 31.4)
    b = enrich_returns([{"code": "ZZF100", "units": 100.0, "currency": "USD", "invest_twd": 30000.0, "policy": "P"}],
                       nav_by_code={"ZZF100": 10.0}, usdtwd=31.4)[0]["current_value_twd"]
    assert _close(a, b) and _close(a, 31400.0)


def test_char_divergence_c7_enrich_returns_clears_value_on_nav_to_cost_ratio_guard_others_do_not():
    """描述現況，不代表核准現況語意。C7／G-VAL-1：`cost_nav`＝1.0、現價 10.0（比值 10 倍，超出 0.2～5 倍護欄）。
    `enrich_returns` 清空市值並標 `nav_suspect`；`FundPosition.value_twd` 與 alo `basis_value` 對同樣的單位／NAV／匯率仍給 31400。
    同一組輸入、三套實作、兩種結果（護欄只存在於其中一套）。"""
    from models.ledger import FundPosition
    from services.portfolio_csv import enrich_returns
    from ui_v2.alo import logic as alo
    enriched = enrich_returns([{"code": "ZZF100", "units": 100.0, "currency": "USD", "invest_twd": 30000.0,
                                "cost_nav": 1.0, "policy": "P"}], nav_by_code={"ZZF100": 10.0}, usdtwd=31.4)[0]
    dataset = {"nav": [{"fund_code": "ZZF100", "nav_date": "2026-10-26", "nav_orig_ccy": 10.0, "ccy": "USD"}],
               "market_indicator": [{"indicator_key": "fx_twd_per_usd", "obs_date": "2026-10-26", "value_num": 31.4}]}
    alo_value, _ = alo.basis_value(dataset, {"fund_code": "ZZF100", "units_shares": 100.0, "cost_twd": 30000.0}, alo.BASIS_MV)
    assert enriched["current_value_twd"] is None and enriched["nav_suspect"] is True
    assert _close(FundPosition(fund_code="ZZF100", units=100.0).value_twd(10.0, 31.4), 31400.0)
    assert _close(alo_value, 31400.0)


# ═════════════════════════════════════════════════════════════════════════════
# C8：AI 輸入與快取
# ═════════════════════════════════════════════════════════════════════════════

def test_char_divergence_c8_ai_summary_session_cache_shown_even_after_snapshot_changes(monkeypatch):
    """描述現況，不代表核准現況語意。C8／G-AI-2：`render_ai_summary_widget` 第一次（按鈕按下）以快照 A 生成「AI-TEXT-A」並存入 session；
    第二次以不同的快照 B（VIX 值變了）渲染、沒按按鈕：畫面仍顯示「AI-TEXT-A」，磁碟快取查詢（以 snapshot 雜湊為鍵）完全沒被呼叫。
    session 內有舊 AI 文字就不比對快照變更（函式層量測；真實頁面的 session 生命週期未在此驗證）。"""
    import repositories.ai_cache as ac
    import services.ai_service as svc
    loads, saves = [], []
    monkeypatch.setattr(ac, "load", lambda key: (loads.append(key), None)[1])
    monkeypatch.setattr(ac, "save", lambda key, value: saves.append((key, value)))
    monkeypatch.setattr(svc, "gemini_generate", lambda prompt, **k: "AI-TEXT-A")
    monkeypatch.setattr(svc, "get_gemini_keys", lambda: ["stub-key"])
    log = []
    _fake, restore = X.swap_in_fake_streamlit(log, button_results=[True, False])
    try:
        widget = importlib.import_module("ui.helpers.ai_summary")
        widget.render_ai_summary_widget(tab_key="tabX", tab_label="替身", snapshot="VIX: 19.25", sections=["a"])
        widget.render_ai_summary_widget(tab_key="tabX", tab_label="替身", snapshot="VIX: 25.0", sections=["a"])
    finally:
        restore()
    shown = [text for kind, text in log if kind == "markdown" and text == "AI-TEXT-A"]
    assert len(shown) == 2
    assert len(loads) == 1 and len(saves) == 1  # 第一次渲染查過磁碟（未命中）；第二次完全沒查，也沒有因快照變更而重存
    assert saves[0][0] == loads[0]


def _tab3_function_source(name):
    tree = ast.parse(_TAB3.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            segment = ast.get_source_segment(_TAB3.read_text(encoding="utf-8"), node)
            return textwrap.dedent(" " * node.col_offset + segment)
    raise AssertionError(f"找不到 {name}")


def _tab3_ai_fingerprint_part(fund, n):
    """執行 `ui/tab3_portfolio.py` 內 `_ai_fp_parts.append(<f-string>)` 那個真實的 f-string 運算式（AST 取出、不複製邏輯）。"""
    tree = ast.parse(_TAB3.read_text(encoding="utf-8"))
    exprs = [node.args[0] for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "append"
             and isinstance(node.func.value, ast.Name) and node.func.value.id == "_ai_fp_parts"]
    assert len(exprs) == 1
    code = compile(ast.fix_missing_locations(ast.Expression(exprs[0])), "<tab3-ai-fp>", "eval")
    return eval(code, {"_f_fp": fund, "_n_fp": n, "_tier_fp": lambda f: "core"})  # noqa: S307 —— 取自 repo 自己的原始碼


def test_char_divergence_c8_tab3_ai_snapshot_fingerprint_ignores_nav_and_fx_values():
    """描述現況，不代表核准現況語意。C8／G-AI-2：tab3 AI 快照 memo 指紋（取自真實程式的 f-string）由代碼｜投入金額｜序列長度｜幣別｜級別組成。
    兩檔只有 NAV 值、metrics、匯率不同的持倉 → 指紋完全相同 → 命中同一份快照 memo（NAV／匯率變動不使它失效）；序列長度變了才會不同。"""
    a = {"code": "zzf100", "invest_twd": 100000, "currency": "USD", "metrics": {"nav": 12.99}, "fx": 31.4}
    b = {"code": "zzf100", "invest_twd": 100000, "currency": "USD", "metrics": {"nav": 99.0}, "fx": 33.9}
    fa, fb = _tab3_ai_fingerprint_part(a, 300), _tab3_ai_fingerprint_part(b, 300)
    assert fa == fb == "ZZF100|100000|300|USD|core"
    assert _tab3_ai_fingerprint_part(a, 301) != fa


def test_char_divergence_c8_tab3_health_cache_fingerprint_ignores_nav_values():
    """描述現況，不代表核准現況語意。C8：tab3 健檢快取指紋 `_pf_health_fingerprint`（AST 取出真實函式執行）只含代碼｜投入金額｜序列長度；
    同長度、不同 NAV 值的序列 → 指紋相同。程式註解自陳「指紋刻意不含時間／值」，要最新值請按重算（設計意圖；此處只量測其效果）。"""
    namespace: dict = {}
    exec(compile(_tab3_function_source("_pf_health_fingerprint"), "<tab3-health-fp>", "exec"), namespace)  # noqa: S102
    fingerprint = namespace["_pf_health_fingerprint"]
    s1 = pd.Series([10.0, 11.0, 12.0])
    s2 = pd.Series([20.0, 30.0, 40.0])
    f1 = [{"code": "zzf100", "invest_twd": 100000, "series": s1}]
    f2 = [{"code": "zzf100", "invest_twd": 100000, "series": s2}]
    assert fingerprint(f1) == fingerprint(f2) == "ZZF100|100000|3"


def test_char_divergence_c8_ai_prompt_indicator_line_has_value_but_no_as_of_or_source(monkeypatch):
    """描述現況，不代表核准現況語意。C8／G-AI-1：`analyze_portfolio_mk_advisor` 的指標摘要行只輸出 `- VIX: <value>`，由呼叫端傳入的 `indicators` 原樣帶入，
    沒有 as-of 日期、沒有來源標籤，也不與 🌍 頁（19.25／2026-10-26）核對：餵 25.0 就印 25.0。"""
    import services.ai_service as svc
    captured = {}

    def fake_llm(prompt, **kwargs):
        captured["prompt"] = prompt
        return "stub"

    monkeypatch.setattr(svc, "call_llm", fake_llm)
    svc.analyze_portfolio_mk_advisor("k", [], {"phase": "x", "score": 1, "allocation": {}},
                                     indicators={"VIX": {"value": 25.0, "date": "2026-10-27", "source": "Yahoo:^VIX"}})
    lines = [ln for ln in captured["prompt"].splitlines() if "VIX" in ln]
    assert "  - VIX: 25.0" in lines
    assert not any("2026-10-27" in ln or "Yahoo" in ln for ln in lines)


# ═════════════════════════════════════════════════════════════════════════════
# 期望不變量（X1～X4）—— 不是核准語意；canonical 層／Decision Gate 之前預期失敗
# ═════════════════════════════════════════════════════════════════════════════

_X_REASON = ("描述現況，不代表核准現況語意：這是『期望不變量』，不是客戶核准的語意；"
             "需 canonical instrument 層／Decision Gate（DG-2、BL-0521／BL-0522）後才可能成立。strict：未計畫地修好會轉紅。")


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="X1 " + _X_REASON)
def test_desired_x1_legacy_vix_equals_view_vix_when_last_bar_is_unclosed(monkeypatch):
    """描述現況，不代表核准現況語意。X1（期望）：舊版風險雷達的 VIX 應等於 🌍 的 VIX（值）。現況見 C3：25.0 vs 19.25。"""
    import repositories.macro.yf as yf
    from services.fund_service import get_latest_vix
    from services.v2_tables import market_view as mv
    series = yf_series("^VIX", *_VIX_WITH_TODAY)
    monkeypatch.setattr(yf, "fetch_yf_close", lambda ticker, range_="2y", interval="1d": series)
    _install_bline_and_view(monkeypatch, {t: yf_series(t, *_VIX_WITH_TODAY) for t in ("^VIX", "^TWII", "^GSPC")})
    assert _close(get_latest_vix(), _domains(mv.build_market_view(fred_api_key=None))["vix"]["points"][-1]["value_num"])


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="X2 " + _X_REASON)
def test_desired_x2_ai_summary_must_not_show_text_generated_for_a_different_snapshot(monkeypatch):
    """描述現況，不代表核准現況語意。X2（期望）：快照變了，畫面不應再顯示依舊快照生成的 AI 文字。現況見 C8：仍顯示舊文字。"""
    import repositories.ai_cache as ac
    import services.ai_service as svc
    monkeypatch.setattr(ac, "load", lambda key: None)
    monkeypatch.setattr(ac, "save", lambda key, value: None)
    monkeypatch.setattr(svc, "gemini_generate", lambda prompt, **k: "AI-TEXT-A")
    monkeypatch.setattr(svc, "get_gemini_keys", lambda: ["stub-key"])
    log = []
    _fake, restore = X.swap_in_fake_streamlit(log, button_results=[True, False])
    try:
        widget = importlib.import_module("ui.helpers.ai_summary")
        widget.render_ai_summary_widget(tab_key="tabX", tab_label="替身", snapshot="VIX: 19.25", sections=["a"])
        log.clear()
        widget.render_ai_summary_widget(tab_key="tabX", tab_label="替身", snapshot="VIX: 25.0", sections=["a"])
    finally:
        restore()
    assert "AI-TEXT-A" not in [text for kind, text in log if kind == "markdown"]


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="X3 " + _X_REASON)
def test_desired_x3_valuation_nav_equals_single_fund_nav_for_same_instrument(monkeypatch):
    """描述現況，不代表核准現況語意。X3（期望）：T7 估值用的 `get_latest_nav` 應等於單一基金頁（A 鏈）的 NAV。現況見 C5：11.11 vs 12.99（stub 輸入本就不同，機制為來源優先序）。"""
    import repositories.macro_repository as mr
    from services.fund_service import fetch_fund_from_moneydj_url_enriched as enr, get_latest_nav
    _install_chain(monkeypatch)
    _guard_other_nav_sources(monkeypatch)
    ysr = yf_series("ZZF100", ["2026-02-26", "2026-02-27"], [11.0, 11.11], currency="USD")
    monkeypatch.setattr(mr, "fetch_yf_close", lambda t, range_="2y", interval="1d": ysr)
    assert _close(get_latest_nav("ZZF100", "USD"), float(enr("ZZF100")["series"].iloc[-1]))


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="X4 " + _X_REASON)
def test_desired_x4_alo_valuation_equals_legacy_valuation_at_same_as_of(monkeypatch):
    """描述現況，不代表核准現況語意。X4（期望）：同一組持倉與 NAV，⚖️ alo 的市值應等於舊版市值（同 as-of、同 FX 切日）。現況見 C7：閘門人為開啟下 31350 vs 31400（production 閘門關閉時 vNext 無 USD 匯率列，不是 31350）。"""
    from models.ledger import FundPosition
    from ui_v2.alo import logic as alo
    rows = _fx_rows_with_gate_open(monkeypatch)
    dataset = {"nav": [{"fund_code": "ZZF100", "nav_date": "2026-10-22", "nav_orig_ccy": 10.0, "ccy": "USD"}],
               "market_indicator": rows}
    value, _ = alo.basis_value(dataset, {"fund_code": "ZZF100", "units_shares": 100.0, "cost_twd": 30000.0}, alo.BASIS_MV)
    assert _close(value, FundPosition(fund_code="ZZF100", units=100.0).value_twd(10.0, 31.4))


# ═════════════════════════════════════════════════════════════════════════════
# 自我守衛：標示文字不得被拿掉
# ═════════════════════════════════════════════════════════════════════════════

def test_char_marker_every_test_and_module_docstring_carries_the_non_approval_marker():
    """描述現況，不代表核准現況語意。自我守衛：本檔與 `_xview_fixtures.py` 的模組 docstring、本檔每個 `test_*` 的 docstring 都含標示文字。"""
    for path in (pathlib.Path(__file__), pathlib.Path(X.__file__)):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert MARKER in (ast.get_docstring(tree) or ""), path.name
    tree = ast.parse(pathlib.Path(__file__).read_text(encoding="utf-8"))
    missing = [n.name for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
               and MARKER not in (ast.get_docstring(n) or "")]
    assert missing == []
