"""AAII 情緒調查 parser 硬化 — golden / 防呆反向 / 接線驗證(2026-08-05 稽核)。

背景
----
線上顯示 AAII spread **+50.00%**(極度貪婪),但 aaii.com/sentimentsurvey 當日
最新一週(週結 2026-07-29)實際是 bull 31.0 / neutral 26.9 / bear 42.1
→ spread **−11.1**。誤差 61 個百分點且符號相反。

根因三件(repositories/macro/alternate.py):
  1. 對**原始 HTML** 跑 `[Bb]ullish[^0-9]{0,40}(\\d{1,2}\\.\\d)\\s*%`
     → 吃到 markup 裡的 CSS 進度條寬度(width:50.0% / width:0.0%);
  2. 完全沒有值域防呆(同檔 PMI 分支每段都有 30<=v<=70,AAII 零檢查);
  3. `date` 硬編碼 "weekly" → §2.3 PIT 連「這筆是不是上週的」都判斷不了。

每條測試都標注「修正前會不會紅」。
"""
from __future__ import annotations

import datetime as _dt
from unittest.mock import patch

import pytest


class _MockResp:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


# ── 真實頁面結構的 fixture ────────────────────────────────────────────
# 取自 aaii.com/sentimentsurvey 2026-08-05 實際內容:
#   Week Ending | Bullish | Neutral | Bearish 四欄表格 + 最近 4 週 + 歷史均值區塊。
# **刻意保留** production 頁面上會出現的干擾 markup(情緒 bar 的 inline CSS 寬度),
# 因為線上抓到的 bull=50.0 / bear=0.0 正是從這類 markup 來的 —— 舊 parser 跑這份
# fixture 會回 +50.0,新 parser 必須回 −11.1。
_REAL_PAGE_HTML = """
<div class="sentiment-widget">
  <div class="bar bullish" style="width:50.0%"></div>
  <div class="bar neutral" style="width:0.0%"></div>
  <div class="bar bearish" style="width:0.0%"></div>
</div>
<h2>What Direction Do AAII Members Feel The Stock Market Will Be In The Next 6 Months?</h2>
<table class="sentiment-table">
  <thead><tr><th>Week Ending</th><th>Bullish</th><th>Neutral</th><th>Bearish</th></tr></thead>
  <tbody>
    <tr><td>7/29/2026</td><td>31.0%</td><td>26.9%</td><td>42.1%</td></tr>
    <tr><td>7/22/2026</td><td>29.6%</td><td>28.1%</td><td>42.3%</td></tr>
    <tr><td>7/15/2026</td><td>44.9%</td><td>22.2%</td><td>32.9%</td></tr>
    <tr><td>7/8/2026</td><td>36.3%</td><td>26.5%</td><td>37.2%</td></tr>
  </tbody>
</table>
<div class="historical">
  <span>Historical Averages</span><span>37.5%</span><span>31.5%</span><span>31.0%</span>
  <span>1-Year Bullish High:</span><span>49.5%</span><span>Week Ending 1/14/2026</span>
  <span>1-Year Neutral High</span><span>31.4%</span><span>Week Ending 3/4/2026</span>
  <span>1-Year Bearish High</span><span>52.0%</span><span>Week Ending 3/18/2026</span>
</div>
"""

# 只有干擾 markup、沒有調查表格 —— 就是線上那個 +50.00 的來源形狀。
_GARBAGE_ONLY_HTML = """
<div class="sentiment-widget">
  <div class="bar bullish" style="width:50.0%"></div>
  <div class="bar bearish" style="width:0.0%"></div>
</div>
"""


def _table(rows_html: str, header: str = "<th>Bullish</th><th>Neutral</th><th>Bearish</th>") -> str:
    return (f"<table><thead><tr><th>Week Ending</th>{header}</tr></thead>"
            f"<tbody>{rows_html}</tbody></table>")


def _clear():
    from repositories.macro_repository import fetch_aaii_sentiment
    fetch_aaii_sentiment.cache_clear()


# ════════════════════════════════════════════════════════════════
# 1. Golden test — 官網真實數字
# ════════════════════════════════════════════════════════════════
class TestGoldenRealPage:
    """修正前:**全紅**(舊 regex 吃 CSS 寬度 → bull=50.0 / bear=0.0 / spread=+50.0)。"""

    def test_parses_latest_week_values(self):
        from repositories.macro.alternate import _parse_aaii_table
        d = _parse_aaii_table(_REAL_PAGE_HTML)
        assert d["bull"] == pytest.approx(31.0)
        assert d["neutral"] == pytest.approx(26.9)
        assert d["bear"] == pytest.approx(42.1)

    def test_spread_is_minus_11_1(self):
        """稽核指定的 golden 斷言:spread = 31.0 − 42.1 = −11.1(§4.3 禁 ==)。"""
        from repositories.macro.alternate import _parse_aaii_table
        d = _parse_aaii_table(_REAL_PAGE_HTML)
        assert d["value"] == pytest.approx(-11.1, abs=1e-9)
        assert d["value"] < 0, "當週為淨看空,符號不可為正"

    def test_date_is_real_week_ending_not_weekly(self):
        """§2.3 PIT:date 必須是可辨識新舊的 ISO 週結日。"""
        from repositories.macro.alternate import _parse_aaii_table
        d = _parse_aaii_table(_REAL_PAGE_HTML)
        assert d["date"] == "2026-07-29"

    def test_picks_latest_week_not_an_older_row(self):
        """表格 4 週並列,必須取最新一週(7/15 那週 spread 是 +12.0,取錯就正負顛倒)。"""
        from repositories.macro.alternate import _parse_aaii_table
        d = _parse_aaii_table(_REAL_PAGE_HTML)
        assert d["date"] == "2026-07-29"
        assert d["value"] == pytest.approx(-11.1)

    def test_css_progress_bar_numbers_not_picked_up(self):
        """markup 裡的 50.0% / 0.0% 絕不可被當成調查值。"""
        from repositories.macro.alternate import _parse_aaii_table
        d = _parse_aaii_table(_REAL_PAGE_HTML)
        assert d["bull"] != pytest.approx(50.0)
        assert d["bear"] != pytest.approx(0.0)

    def test_historical_average_row_not_picked_up(self):
        """Historical Averages(37.5/31.5/31.0)無週結日,不得被當成當期值。"""
        from repositories.macro.alternate import _parse_aaii_table
        d = _parse_aaii_table(_REAL_PAGE_HTML)
        assert d["bull"] != pytest.approx(37.5)


# ════════════════════════════════════════════════════════════════
# 2. 防呆反向測試 — §1 Fail Loud,禁止回「能通過 schema 的垃圾數字」
# ════════════════════════════════════════════════════════════════
class TestGuardsFailLoud:
    """修正前:**全紅**(舊碼無任何防呆,一律回數字)。"""

    def test_garbage_only_page_returns_err_not_number(self):
        """線上那個 bull=50.0 / bear=0.0 的頁面形狀 → 必須 fail loud。"""
        _clear()
        from repositories import macro_repository as mr
        with patch("repositories.macro.alternate.fetch_url",
                   return_value=_MockResp(200, _GARBAGE_ONLY_HTML)):
            r = mr.fetch_aaii_sentiment()
        assert "_err" in r, f"垃圾頁面必須回 _err,實際回了 {r}"
        assert "value" not in r, "§1:不得回任何猜測值"
        assert r["source"].startswith("AAII:")
        assert "fetched_at" in r

    def test_sum_not_100_rejected(self):
        """三欄是同一份問卷的互斥選項,和不成 100 = 抓到非調查數字。"""
        from repositories.macro.alternate import _parse_aaii_table
        html = _table("<tr><td>7/29/2026</td><td>50.0%</td><td>0.0%</td><td>0.0%</td></tr>")
        with pytest.raises(ValueError, match="bull"):
            _parse_aaii_table(html)

    def test_spread_beyond_historical_extreme_rejected(self):
        """|bull−bear| > 60(近一年極值約 ±50)→ 不可能是真調查值。"""
        from repositories.macro.alternate import _parse_aaii_table
        html = _table("<tr><td>7/29/2026</td><td>80.0%</td><td>5.0%</td><td>15.0%</td></tr>")
        with pytest.raises(ValueError, match="bull−bear"):
            _parse_aaii_table(html)

    def test_out_of_range_column_rejected(self):
        from repositories.macro.alternate import _parse_aaii_table
        html = _table("<tr><td>7/29/2026</td><td>150.0%</td><td>0.0%</td><td>0.0%</td></tr>")
        with pytest.raises(ValueError):
            _parse_aaii_table(html)

    def test_future_week_ending_rejected(self):
        """週結日是過去的週三,解析出未來日期 = 欄位錯位(§2.3)。"""
        from repositories.macro.alternate import _parse_aaii_table
        future = _dt.date.today() + _dt.timedelta(days=400)
        html = _table(f"<tr><td>{future.month}/{future.day}/{future.year}</td>"
                      f"<td>31.0%</td><td>26.9%</td><td>42.1%</td></tr>")
        with pytest.raises(ValueError, match="週結日"):
            _parse_aaii_table(html)

    def test_no_table_reports_regex_no_match(self):
        from repositories.macro.alternate import _parse_aaii_table
        with pytest.raises(ValueError, match="regex"):
            _parse_aaii_table("<html><body>maintenance</body></html>")


# ════════════════════════════════════════════════════════════════
# 3. 欄序不寫死 — 表頭順序改變不可造成 bull/bear 對調
# ════════════════════════════════════════════════════════════════
class TestColumnOrderFollowsHeader:
    """欄序解析 + **非官方欄序一律 fail loud**(v19.429 稽核後改設計)。

    ── 設計變更說明(原測試斷言「表頭顛倒仍正確對應」,現改為必須 raise)──
    初版設計是「由表頭位置動態決定欄序」,好處是 AAII 真的改版重排欄位時能自動適應。
    但 2026-08-05 獨立稽核指出:本檔三條不變量**全部對 bull↔bear 互換不敏感** ——
      · 各欄 ∈ [0,100]      → 值域對稱,不敏感
      · 三欄和 ≈ 100        → 加法可交換,完全不敏感
      · |bull − bear| ≤ 60  → 取絕對值,完全不敏感
    也就是說,欄序啟發式(`rfind` 找最靠近資料列的表頭字)是**唯一**防線。一旦它誤判
    (例如頁面某處註腳出現 "Bullish" 且比真表頭更靠近資料列),parser 會靜默回傳
    bull/bear 顛倒的結果,spread 由 −11.1 翻成 +11.1(散戶偏空 → 極度貪婪),
    而四道防呆全綠 —— 正是 `CLAUDE.md §1`「錯誤的數字比沒有數字更危險」。

    **取捨**:AAII 官網欄序二十年未變。真改版時 fail loud 只是讓人來看一次;
    啟發式誤判時靜默翻號則無人察覺。故選 raise。
    """

    def test_non_canonical_header_order_raises(self):
        """**修正前必紅**(舊設計會回傳對調後「看似正確」的值,不 raise)。"""
        from repositories.macro.alternate import _parse_aaii_table
        html = _table(
            "<tr><td>7/29/2026</td><td>42.1%</td><td>26.9%</td><td>31.0%</td></tr>",
            header="<th>Bearish</th><th>Neutral</th><th>Bullish</th>")
        with pytest.raises(ValueError, match="欄序"):
            _parse_aaii_table(html)

    def test_canonical_header_order_still_parses(self):
        """護欄:官方欄序(Bullish / Neutral / Bearish)必須照常解析,不被誤擋。"""
        from repositories.macro.alternate import _parse_aaii_table
        html = _table(
            "<tr><td>7/29/2026</td><td>31.0%</td><td>26.9%</td><td>42.1%</td></tr>",
            header="<th>Bullish</th><th>Neutral</th><th>Bearish</th>")
        d = _parse_aaii_table(html)
        assert d["bull"] == pytest.approx(31.0)
        assert d["bear"] == pytest.approx(42.1)
        assert d["value"] == pytest.approx(-11.1)


# ════════════════════════════════════════════════════════════════
# 4. 接線驗證(PROCESS.md §4 Wiring Test)
#    判準:「產生端完全正確、但沒接出去」時必須變紅。
# ════════════════════════════════════════════════════════════════
class TestWiringToProductionCaller:
    def test_l2_caller_receives_real_week_and_spread(self):
        """production caller(services.us_liquidity_engine._aaii_with_judgment)
        真的拿到修好的數字 + 真實週結日。

        修正前:**紅** —— 舊碼給 value=+50.0 / date="weekly",
        判讀會變「🔴 散戶過度樂觀」。
        接線判準:若 L1 修好但 L2 沒把 date/value 傳出去,本條同樣紅。
        """
        _clear()
        from services import us_liquidity_engine as ule
        ule.fetch_aaii_sentiment.cache_clear()
        with patch("repositories.macro.alternate.fetch_url",
                   return_value=_MockResp(200, _REAL_PAGE_HTML)):
            out = ule._aaii_with_judgment()
        assert "_err" not in out, f"合法頁面不該 fail:{out.get('_err')}"
        assert out["date"] == "2026-07-29", "UI 卡片顯示的就是這個 date 欄"
        assert out["value"] == pytest.approx(-11.1)
        assert out["neutral"] == pytest.approx(26.9)
        # −11.1 落在 [AAII_PANIC_PCT, AAII_EUPHORIA_PCT] → 中性,不得是「過度樂觀」
        assert "過度樂觀" not in out["label"], (
            f"spread −11.1 被判成過度樂觀 = 判讀鏈吃到錯數字:{out['label']}")

    def test_l2_caller_rejects_garbage_dict_via_schema(self):
        """垃圾值(線上那組 bull=50.0 / bear=0.0)在 **L2 caller** 端也必須被擋。

        修正前:**紅** —— 舊 schema 只驗 [0,100],這組完全合規通過。
        接線判準:把 `services/us_liquidity_engine.py` 裡
        `validate_aaii_sentiment(raw)` 那一行拿掉,本條立刻紅
        (會拿到 value=50.0 而不是 _err)。
        """
        from services import us_liquidity_engine as ule
        garbage = {
            "value": 50.0, "unit": "%", "bull": 50.0, "bear": 0.0, "neutral": 0.0,
            "date": "2026-07-29", "url_used": "https://www.aaii.com/sentimentsurvey",
            "source": "AAII:sentimentsurvey",
            "fetched_at": "2026-08-05T00:00:00+00:00",
        }
        with patch.object(ule, "fetch_aaii_sentiment", return_value=garbage):
            out = ule._aaii_with_judgment()
        assert "_err" in out, f"垃圾值必須被 schema 攔下,實際回了 {out}"
        assert "schema" in out["_err"]

    def test_l2_caller_rejects_weekly_placeholder_date(self):
        """`date="weekly"` 回歸鎖:任何人把硬編碼寫回去,這條就紅(§2.3 PIT)。"""
        from services import us_liquidity_engine as ule
        legacy = {
            "value": -11.1, "unit": "%", "bull": 31.0, "bear": 42.1, "neutral": 26.9,
            "date": "weekly", "url_used": "https://www.aaii.com/sentimentsurvey",
            "source": "AAII:sentimentsurvey",
            "fetched_at": "2026-08-05T00:00:00+00:00",
        }
        with patch.object(ule, "fetch_aaii_sentiment", return_value=legacy):
            out = ule._aaii_with_judgment()
        assert "_err" in out, "無時點的 date 必須被擋(否則無法判斷資料新舊)"


# ════════════════════════════════════════════════════════════════
# 5. 防呆常數 SSOT — 常數必須來自 shared/schemas.py,不得 inline 重寫
# ════════════════════════════════════════════════════════════════
class TestGuardConstantsAreSSOT:
    def test_parser_reads_spread_cap_from_shared_schemas(self):
        """把 SSOT 上限調到 5,原本合法的 −11.1 就必須被擋。

        修正前:**紅**(常數根本不存在)。
        本條也是 SSOT 接線鎖:若 parser 改寫成 inline 60.0,調 SSOT 不再有效果 → 紅。
        """
        import shared.schemas as sch
        from repositories.macro.alternate import _parse_aaii_table
        with patch.object(sch, "AAII_SPREAD_ABS_MAX_PCT", 5.0):
            with pytest.raises(ValueError, match="bull−bear"):
                _parse_aaii_table(_REAL_PAGE_HTML)

    def test_parser_reads_sum_tolerance_from_shared_schemas(self):
        """把總和容差放寬到 100,和不成 100 的殘缺配對就會被放行 → 證明吃的是 SSOT。"""
        import shared.schemas as sch
        from repositories.macro.alternate import _parse_aaii_table
        html = _table("<tr><td>7/29/2026</td><td>31.0%</td><td>10.0%</td><td>42.1%</td></tr>")
        with pytest.raises(ValueError, match="bull"):
            _parse_aaii_table(html)
        with patch.object(sch, "AAII_SUM_ABS_TOL_PCT", 100.0):
            d = _parse_aaii_table(html)
        assert d["value"] == pytest.approx(-11.1)
