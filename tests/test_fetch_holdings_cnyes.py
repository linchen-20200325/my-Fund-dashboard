"""v19.276 regression test — cnyes 持股 fallback。

User 反饋 ACTI71 / JFZN3 等基金 MoneyDJ yp013xxx 持股頁全空(子網域限制 /
multi-asset 透明度不足),要求「找其他替代方案爬持股」。新增 cnyes 持股 API
作為 MoneyDJ 全失敗 / 頁無持股時的 fallback(§2.1 fallback chain 末端)。

⚠️ cnyes 持股端點 JSON shape 無法於開發環境(local proxy 403)實測 →
   採防禦式「多 endpoint × 多欄位名」解析,本測試以 mock JSON 守多 shape 契約。
"""
from __future__ import annotations

from unittest.mock import patch

import repositories.fund.sources as S
from repositories.fund.nav_metrics import fetch_holdings


class _FakeJsonResp:
    def __init__(self, payload, status: int = 200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


# ── _cnyes_parse_holdings：純解析(無網路),守多 shape ──────────────────

def test_parse_holdings_nested_data_dict():
    """data.holdings + 每 item 不同欄位名(name/stockName、weight/ratio)都要吃到。"""
    payload = {"data": {"holdings": [
        {"name": "NVIDIA", "industry": "資訊科技", "weight": 6.5},
        {"stockName": "APPLE", "ratio": 5.2},
    ]}}
    out = S._cnyes_parse_holdings(payload)
    tops = {h["name"]: h["pct"] for h in out["top_holdings"]}
    assert tops == {"NVIDIA": 6.5, "APPLE": 5.2}
    assert out["top_holdings"][0]["sector"] == "資訊科技"
    assert out["top_holdings"][1]["sector"] == ""  # 缺 sector → 空字串不崩


def test_parse_holdings_with_sector_allocation():
    """topHoldings + industryAllocation 同時存在 → 兩段都解析。"""
    payload = {"data": {
        "topHoldings": [{"securityName": "TSMC", "percentage": 4.1}],
        "industryAllocation": [
            {"industryName": "科技", "weight": 40, "amount": 1000},
            {"industryName": "金融", "weight": 30},
        ],
    }}
    out = S._cnyes_parse_holdings(payload)
    assert out["top_holdings"][0]["name"] == "TSMC"
    secs = {s["name"]: (s["pct"], s["amount"]) for s in out["sector_alloc"]}
    assert secs["科技"] == (40.0, 1000.0)
    assert secs["金融"] == (30.0, 0.0)  # 缺 amount → 0.0


def test_parse_holdings_asset_allocation_only():
    """multi-asset fund:只有 assetAllocation(無個股 holdings)也要抓到 sector_alloc。"""
    payload = {"data": {"assetAllocation": [
        {"assetName": "投資等級債券", "weight": 50.0, "amount": 1000},
        {"assetName": "全球股票", "weight": 42.0},
    ]}}
    out = S._cnyes_parse_holdings(payload)
    assert "top_holdings" not in out
    secs = {s["name"]: s["pct"] for s in out["sector_alloc"]}
    assert secs == {"投資等級債券": 50.0, "全球股票": 42.0}


def test_parse_holdings_top_level_list():
    """data 直接是 holdings 陣列(無 data wrapper)也要吃到。"""
    payload = [{"name": "BOND A", "weight": 3.3}]
    out = S._cnyes_parse_holdings(payload)
    assert out["top_holdings"] == [{"name": "BOND A", "sector": "", "pct": 3.3}]


def test_parse_holdings_unrecognized_shape_returns_empty():
    """shape 不認得 → 回 {}(§1 Fail Loud:不偽造)。"""
    assert S._cnyes_parse_holdings({"foo": "bar"}) == {}
    assert S._cnyes_parse_holdings({"data": {"unknownKey": [1, 2, 3]}}) == {}


def test_parse_holdings_filters_out_of_range_pct():
    """pct 越界(0 / ≥100 / 負)應被濾掉,不污染輸出。"""
    payload = {"data": {"holdings": [
        {"name": "BAD0", "weight": 0},
        {"name": "BAD100", "weight": 150},
        {"name": "GOOD", "weight": 5.5},
    ]}}
    out = S._cnyes_parse_holdings(payload)
    assert [h["name"] for h in out["top_holdings"]] == ["GOOD"]


def test_parse_holdings_caps_top_10():
    """top_holdings 上限 10 筆(對齊 MoneyDJ fetch_holdings 契約)。"""
    payload = {"data": {"holdings": [
        {"name": f"H{i}", "weight": float(i + 1)} for i in range(15)]}}
    out = S._cnyes_parse_holdings(payload)
    assert len(out["top_holdings"]) == 10


# ── fetch_holdings_cnyes：含 mock 網路 ───────────────────────────────────

def test_fetch_holdings_cnyes_happy_path():
    """portfolio 端點回有效 JSON → 帶 provenance 的契約 dict。"""
    portfolio = {"data": {"holdings": [
        {"name": "NVIDIA", "weight": 6.5}, {"name": "APPLE", "weight": 5.2}]}}

    def _fake_get(url, **kw):
        if "/portfolio" in url:
            return _FakeJsonResp(portfolio)
        return _FakeJsonResp({}, status=404)

    with patch.object(S, "_cnyes_resolve_code", return_value=["ACTI71"]), \
         patch.object(S.requests, "get", side_effect=_fake_get):
        out = S.fetch_holdings_cnyes("ACTI71")

    assert [h["name"] for h in out["top_holdings"]] == ["NVIDIA", "APPLE"]
    assert out["source"] == "Cnyes:portfolio:ACTI71"
    assert "fetched_at" in out


def test_fetch_holdings_cnyes_all_endpoints_404_returns_empty():
    """所有候選端點皆 404 → {}(不崩潰、不偽造)。"""
    with patch.object(S, "_cnyes_resolve_code", return_value=["JFZN3"]), \
         patch.object(S.requests, "get",
                      return_value=_FakeJsonResp({}, status=404)):
        out = S.fetch_holdings_cnyes("JFZN3")
    assert out == {}


def test_fetch_holdings_cnyes_blank_code():
    """空代碼 → {}(不發網路)。"""
    assert S.fetch_holdings_cnyes("") == {}
    assert S.fetch_holdings_cnyes("   ") == {}


# ── 接線:nav_metrics.fetch_holdings → cnyes fallback ───────────────────

def test_fetch_holdings_falls_back_to_cnyes_when_moneydj_all_fail():
    """MoneyDJ 全 URL 失敗 → 應呼 cnyes fallback 並回其結果。"""
    fetch_holdings.cache_clear()
    _cy = {"top_holdings": [{"name": "X", "sector": "", "pct": 9.9}],
           "source": "Cnyes:portfolio:AAA", "fetched_at": "2026-06-30T00:00:00Z"}

    with patch("repositories.fund.nav_metrics.fetch_url_with_retry",
               return_value=None), \
         patch("repositories.fund.nav_metrics.fetch_holdings_cnyes",
               return_value=_cy) as _m:
        out = fetch_holdings("AAA")

    _m.assert_called_once_with("AAA")
    assert out["source"] == "Cnyes:portfolio:AAA"
    assert out["top_holdings"][0]["name"] == "X"


def test_fetch_holdings_falls_back_to_cnyes_when_page_has_no_holdings():
    """MoneyDJ 頁抓到但 parser 0 命中(multi-asset / FoF)→ cnyes fallback。"""
    fetch_holdings.cache_clear()

    class _Resp:
        # > 500 chars 但無任何可解析持股表
        text = "<html><body>" + ("<p>無持股表</p>" * 80) + "</body></html>"
        status_code = 200
        encoding = "big5"
        apparent_encoding = "big5"

    _cy = {"sector_alloc": [{"name": "債券", "pct": 50.0, "amount": 0.0}],
           "source": "Cnyes:asset:BBB", "fetched_at": "2026-06-30T00:00:00Z"}

    with patch("repositories.fund.nav_metrics.fetch_url_with_retry",
               return_value=_Resp()), \
         patch("repositories.fund.nav_metrics.fetch_holdings_cnyes",
               return_value=_cy) as _m:
        out = fetch_holdings("BBB")

    _m.assert_called_once_with("BBB")
    assert out["source"] == "Cnyes:asset:BBB"
    assert out["sector_alloc"][0]["name"] == "債券"


# ── v19.278 Morningstar 持股 fallback(cnyes 之後第二替代源)──────────────

def test_ms_parse_asset_allocation_nested_portfolios():
    """Morningstar Portfolios[].assetAllocation → sector_alloc(多重資產主路徑)。"""
    payload = {"Portfolios": [{"assetAllocation": [
        {"assetClass": "Equity", "netAssetPercent": 31.7},
        {"assetClass": "Convertible", "netAssetPercent": 31.6},
        {"assetClass": "High Yield Bond", "netAssetPercent": 30.8},
    ]}]}
    out = S._ms_parse_holdings(payload)
    secs = {s["name"]: s["pct"] for s in out["sector_alloc"]}
    assert secs == {"Equity": 31.7, "Convertible": 31.6, "High Yield Bond": 30.8}
    assert "top_holdings" not in out


def test_ms_parse_top_holdings_field_fallbacks():
    """holdingDetails + 多欄位名(securityName/weighting)。"""
    payload = {"holdingDetails": [
        {"securityName": "NVIDIA", "weighting": 6.5, "sector": "Technology"},
        {"name": "APPLE", "weight": 5.2},
    ]}
    out = S._ms_parse_holdings(payload)
    tops = {h["name"]: h["pct"] for h in out["top_holdings"]}
    assert tops == {"NVIDIA": 6.5, "APPLE": 5.2}
    assert out["top_holdings"][0]["sector"] == "Technology"


def test_ms_parse_unrecognized_returns_empty():
    assert S._ms_parse_holdings({"foo": "bar"}) == {}


def test_fetch_holdings_morningstar_happy_path():
    """secId 解析成功 + snapshot 回資產配置 → 帶 provenance 契約 dict。"""
    portfolio = {"Portfolios": [{"assetAllocation": [
        {"assetClass": "Equity", "netAssetPercent": 42.0},
        {"assetClass": "Bond", "netAssetPercent": 50.0}]}]}

    def _fake_get(url, **kw):
        return _FakeJsonResp(portfolio)

    with patch.object(S, "_resolve_ms_secid", return_value="0P0001J5YG"), \
         patch.object(S.requests, "get", side_effect=_fake_get):
        out = S.fetch_holdings_morningstar("TLZF9")

    secs = {s["name"]: s["pct"] for s in out["sector_alloc"]}
    assert secs == {"Equity": 42.0, "Bond": 50.0}
    assert out["source"].startswith("Morningstar:holdings:0P0001J5YG")
    assert "fetched_at" in out


def test_fetch_holdings_morningstar_no_secid_returns_empty():
    """secId 解析失敗 → {}(不發網路)。"""
    with patch.object(S, "_resolve_ms_secid", return_value=""):
        assert S.fetch_holdings_morningstar("UNKNOWN9") == {}


def test_fetch_holdings_morningstar_blank_code():
    assert S.fetch_holdings_morningstar("") == {}


def test_fetch_holdings_falls_back_to_morningstar_when_cnyes_empty():
    """MoneyDJ 全失敗 + cnyes 空 → 落到 Morningstar。"""
    fetch_holdings.cache_clear()
    _ms = {"sector_alloc": [{"name": "Equity", "pct": 42.0, "amount": 0.0}],
           "source": "Morningstar:holdings:0P0001J5YG:PortfolioSAL",
           "fetched_at": "2026-06-30T00:00:00Z"}

    with patch("repositories.fund.nav_metrics.fetch_url_with_retry",
               return_value=None), \
         patch("repositories.fund.nav_metrics.fetch_holdings_cnyes",
               return_value={}), \
         patch("repositories.fund.nav_metrics.fetch_holdings_morningstar",
               return_value=_ms) as _m:
        out = fetch_holdings("TLZF9")

    _m.assert_called_once_with("TLZF9")
    assert out["source"].startswith("Morningstar:")
    assert out["sector_alloc"][0]["name"] == "Equity"


def test_fetch_holdings_no_cnyes_when_moneydj_succeeds():
    """MoneyDJ 抓到持股 → 不該呼 cnyes(避免無謂網路)。"""
    fetch_holdings.cache_clear()

    class _Resp:
        text = ("<html><body><table>"
                "<tr><td colspan='3'>基金投資分佈(依產業)</td></tr>"
                "<tr><td>產業</td><td>投資金額</td><td>比例(%)</td></tr>"
                "<tr><td>半導體業</td><td>1000</td><td>55.00</td></tr>"
                "</table>" + ("<!-- pad -->" * 60) + "</body></html>")
        status_code = 200
        encoding = "big5"
        apparent_encoding = "big5"

    with patch("repositories.fund.nav_metrics.fetch_url_with_retry",
               return_value=_Resp()), \
         patch("repositories.fund.nav_metrics.fetch_holdings_cnyes",
               return_value={}) as _m:
        out = fetch_holdings("CCC")

    _m.assert_not_called()
    assert "sector_alloc" in out
    assert out["source"].startswith("MoneyDJ:")
