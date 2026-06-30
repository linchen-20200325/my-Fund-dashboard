"""v19.249 R18 regression test — fetch_holdings 支援 multi-asset fund 的
asset-class sector_alloc(原寫死 keyword 漏抓 ACCP138 等多重資產 fund)。

User screenshot bug:ACCP138(瀚亞多重收益優化組合基金)持股頁 yp013001 確認:
- top_holdings 顯示「目前無資料」(常態)
- sector_alloc 含「全球股票/投資等級債券/現金與約當現金」等 9 類 asset class
- 但 fetcher 因 keyword 「資訊科技/工業/金融」0 命中 → 整檔 holdings 抓不到。

修法改結構性偵測:table header 含 (產業/資產類別/類別/地區) + 比例 + 不含投資名稱。
"""
from __future__ import annotations

from unittest.mock import patch


class _FakeResp:
    def __init__(self, text: str):
        self.text = text
        self.status_code = 200
        self.encoding = "big5"
        self.apparent_encoding = "big5"


# Multi-asset fund (ACCP138 同 type) 的 sector_alloc HTML(用 asset class 名,
# 無「資訊科技/工業/金融」keyword,原寫死偵測會 fail)
_MULTI_ASSET_HTML = """<html><body>
<table>
  <tr><td colspan='3'>基金投資分佈(依產業)</td></tr>
  <tr><td>產業</td><td>投資金額(台幣:以萬元為單位)</td><td>比例(%)</td></tr>
  <tr><td>全球股票</td><td>619,378.80</td><td>29.60</td></tr>
  <tr><td>非投資等級債券</td><td>372,464.30</td><td>17.80</td></tr>
  <tr><td>投資等級債券</td><td>341,076.80</td><td>16.30</td></tr>
  <tr><td>美國股票</td><td>286,671.90</td><td>13.70</td></tr>
  <tr><td>現金與約當現金</td><td>171,584.70</td><td>8.20</td></tr>
  <tr><td>新興市場債</td><td>85,792.30</td><td>4.10</td></tr>
  <tr><td>亞太不含日本</td><td>77,422.30</td><td>3.70</td></tr>
  <tr><td>可轉債</td><td>75,329.90</td><td>3.60</td></tr>
  <tr><td>新興市場股票</td><td>64,832.50</td><td>3.10</td></tr>
</table>
<table>
  <tr><td colspan='3'>基金前十大持股</td></tr>
  <tr><td>投資名稱</td><td>產業</td><td>比例(%)</td></tr>
  <tr><td>目前無資料</td><td></td><td></td></tr>
</table>
</body></html>"""

# 股票型 fund (ACDD01 同 type) — 應仍可偵測(回歸測試)
_EQUITY_FUND_HTML = """<html><body>
<table>
  <tr><td colspan='3'>基金投資分佈(依產業)</td></tr>
  <tr><td>產業</td><td>投資金額(以萬元為單位)</td><td>比例(%)</td></tr>
  <tr><td>半導體業</td><td>5,077,892</td><td>54.85</td></tr>
  <tr><td>電子零組件業</td><td>3,043,958</td><td>32.88</td></tr>
  <tr><td>化學工業</td><td>32,402</td><td>0.35</td></tr>
</table>
<table>
  <tr><td colspan='3'>基金前十大持股</td></tr>
  <tr><td>投資名稱</td><td>產業</td><td>比例(%)</td></tr>
  <tr><td>NVIDIA CORP</td><td>資訊科技</td><td>9.50</td></tr>
  <tr><td>APPLE INC</td><td>資訊科技</td><td>7.25</td></tr>
</table>
</body></html>"""


def test_multi_asset_fund_sector_alloc_extracted():
    """v19.249 R18 root cause 守 — ACCP138 type fund 的 multi-asset sector
    必須能被 fetcher 抓到(不能因為 keyword 「資訊科技/工業/金融」缺漏就整段失敗)。"""
    import fund_fetcher  # noqa: F401 — circular
    from repositories.fund.nav_metrics import fetch_holdings

    with patch("repositories.fund.nav_metrics.fetch_url_with_retry",
               return_value=_FakeResp(_MULTI_ASSET_HTML)):
        out = fetch_holdings("ACCP138")

    assert "sector_alloc" in out, \
        f"multi-asset fund 必須抓到 sector_alloc(原 bug:keyword 命中失敗)。actual={out}"
    sectors = {s["name"]: s["pct"] for s in out["sector_alloc"]}
    # 抽樣關鍵 asset class
    assert sectors.get("全球股票") == 29.60, f"全球股票 pct 不對:{sectors}"
    assert sectors.get("投資等級債券") == 16.30, f"投資等級債券 pct 不對:{sectors}"
    assert sectors.get("現金與約當現金") == 8.20, f"現金與約當現金 pct 不對:{sectors}"
    assert len(sectors) >= 9, f"應抓到 ≥9 個 asset class,實際 {len(sectors)}"


def test_multi_asset_top_holdings_empty_logged_not_crashed():
    """multi-asset fund top_holdings 表常顯示「目前無資料」— fetcher 應跳過該表但
    不影響 sector_alloc;結果應有 sector_alloc 但無 top_holdings(graceful partial)。"""
    import fund_fetcher  # noqa: F401
    from repositories.fund.nav_metrics import fetch_holdings

    with patch("repositories.fund.nav_metrics.fetch_url_with_retry",
               return_value=_FakeResp(_MULTI_ASSET_HTML)):
        out = fetch_holdings("ACCP138")

    assert "sector_alloc" in out, "graceful partial — sector_alloc 仍有"
    assert "top_holdings" not in out or out.get("top_holdings") == [], \
        f"「目前無資料」表應跳過,實際 {out.get('top_holdings')}"


def test_equity_fund_still_works_no_regression():
    """v19.249 R18 回歸守 — 股票型 fund (ACDD01 type) 仍能正常抓 sector_alloc + top_holdings。"""
    import fund_fetcher  # noqa: F401
    from repositories.fund.nav_metrics import fetch_holdings

    with patch("repositories.fund.nav_metrics.fetch_url_with_retry",
               return_value=_FakeResp(_EQUITY_FUND_HTML)):
        out = fetch_holdings("ACDD01")

    assert "sector_alloc" in out, "股票型 sector_alloc 也要抓到"
    assert "top_holdings" in out, "股票型 top_holdings 也要抓到"

    sectors = {s["name"]: s["pct"] for s in out["sector_alloc"]}
    assert sectors.get("半導體業") == 54.85
    assert sectors.get("化學工業") == 0.35

    tops = {h["name"]: h["pct"] for h in out["top_holdings"]}
    assert tops.get("NVIDIA CORP") == 9.50
    assert tops.get("APPLE INC") == 7.25


def test_structural_detection_skips_non_sector_tables():
    """邊界 — table 含「比例」但無 sector header 不應誤吃(避免吃到 perf table 等)。"""
    import fund_fetcher  # noqa: F401
    from repositories.fund.nav_metrics import fetch_holdings

    # 一張 perf table:有「比例」(假設 perf 顯示 % 報酬)但無 sector header
    _NOISE_HTML = """<html><body>
    <table>
      <tr><td colspan='2'>近期報酬</td></tr>
      <tr><td>期間</td><td>比例(%)</td></tr>
      <tr><td>1年</td><td>12.5</td></tr>
    </table>
    </body></html>"""

    # v19.276/278:此 fund 抓不到任何 holdings → 會試 cnyes + Morningstar fallback;
    # 本測試只驗 MoneyDJ parser 不誤吃 perf table,patch 兩 fallback 回 {} 維持確定性。
    with patch("repositories.fund.nav_metrics.fetch_url_with_retry",
               return_value=_FakeResp(_NOISE_HTML)), \
         patch("repositories.fund.nav_metrics.fetch_holdings_cnyes", return_value={}), \
         patch("repositories.fund.nav_metrics.fetch_holdings_morningstar", return_value={}):
        out = fetch_holdings("XXX")

    assert "sector_alloc" not in out, f"perf table 不該被誤吃為 sector_alloc:{out}"
