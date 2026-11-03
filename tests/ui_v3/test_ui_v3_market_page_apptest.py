# -*- coding: utf-8 -*-
"""🌍 Preview 頁的 Streamlit AppTest（BL-0536 rendering 批）：`ui_v3/app_preview.py` 實際跑一遍頁面。

取數：只在測試端換掉 `ui_v3.adapters.market_page.load`（回 `market_stubs` 的替身；`ui_v3/` 內沒有任何 fake 資料）。
涵蓋 missing／failed／stale（門檻未裁示→不得出現 ◷）／partial／未設定 FRED 金鑰／檢視切換／期間切換。
⚠️ AppTest 不載入瀏覽器 CSS；版面（390px／桌機）由 Playwright 截圖另證（`docs/evidence/`）。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")

import market_stubs as ms
from shared.ui_semantics import rules
from ui_v3.adapters import market_page as adapter
from ui_v3.pages import mkt
from ui_v3.viewmodels import preview_wording as W

APP = str(Path(__file__).resolve().parents[2] / "ui_v3" / "app_preview.py")


def run(monkeypatch, v=None, t=None, *, state=None, key=ms.KEY):
    view = v if v is not None else ms.view(key=key)
    table = t if t is not None else ms.table()
    monkeypatch.setattr(adapter, "load", lambda sources: (view, table))
    at = streamlit_testing.AppTest.from_file(APP, default_timeout=60)
    for k, val in (state or {}).items():
        at.session_state[k] = val
    return at.run()


def page_text(at) -> str:
    return "\n".join([m.value for m in at.markdown] + [t.value for t in at.title])


def plain(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).replace("&amp;", "&")


def chips(at, key: str) -> list:
    return re.findall(rf'data-status-key="{key}">([^<]*)<', page_text(at))


def pending_keys(at) -> set:
    return set(re.findall(r'data-pending-wording="([a-z0-9_]+)"', page_text(at)))


def test_normal_page_renders_four_first_screen_answers_and_no_exception(monkeypatch):
    at = run(monkeypatch)
    assert not at.exception
    assert [t.value for t in at.title] == ["🌍 市場與趨勢"]
    html = page_text(at)
    # 首屏採 C（DEC-2026-11-03-09）：市場狀態、是否需注意各一枚 `⬜ 無法判定`；資料新鮮度：一枚 `⬜ 門檻待裁示`（Q5 B）
    assert chips(at, "undetermined")[:2] == [rules.entry("undetermined").wording] * 2
    assert chips(at, "threshold_pending") == [rules.entry("threshold_pending").wording]
    summary = plain(html.split('data-card')[0])
    assert re.search(r"台股 近1Y [+-]\d+\.\d\d%", summary) and re.search(r"S&P 500 近1Y [+-]\d+\.\d\d%", summary)
    # 首屏摘要沒有日期、沒有「延遲 N 日」（Q4 A、Q5 B、D3 (i)）
    first = plain(html[: html.index("<h3>")])
    assert not re.search(r"\d{4}-\d{2}-\d{2}", first) and "延遲" not in first and "經過" not in first
    assert "◷" not in html and "◆" not in html           # 沒有正式規則／門檻 → 不判舊、不判注意


def test_primary_chart_has_two_lines_base_chip_frequency_and_per_series_data_dates(monkeypatch):
    at = run(monkeypatch)
    html = page_text(at)
    assert html.count('class="uv3-chart"') == 1 and html.count("stroke-dasharray") == 1   # 兩條線：實線＋虛線
    assert re.search(r"基準日 \d{4}-\d{2}-\d{2}＝100", plain(html))
    assert "頻率：日｜缺值不補、斷線" in plain(html) and "頻率 日" not in plain(html)
    dates = re.findall(r"(台股|S&P 500) 資料日 (\d{4}-\d{2}-\d{2})（經過 (\d+) 日）", plain(html))
    assert dates == [("台股", "2026-11-02", "1"), ("S&P 500", "2026-11-02", "1")]
    assert "100 基準線" not in html and html.count("<line ") == 1


def test_stale_series_is_shown_as_a_fact_only_and_never_judged(monkeypatch):
    """S4：一條較舊（S&P 最後觀測日 10-30、台股 11-02）→ 各畫到自己的最後一天；門檻未裁示 → 沒有 ◷／舊／過期字樣。"""
    v = ms.view(us_dates=ms.weekdays("2021-06-01", "2026-10-30"))
    at = run(monkeypatch, v)
    text = plain(page_text(at))
    assert "台股 資料日 2026-11-02（經過 1 日）" in text and "S&P 500 資料日 2026-10-30（經過 4 日）" in text
    assert "◷" not in text and "過期" not in text and "不是最新" not in text
    assert chips(at, "threshold_pending") == [rules.entry("threshold_pending").wording]


def test_negative_elapsed_days_render_as_not_applicable_not_negative_days(monkeypatch):
    v = ms.view()
    for d in v["domains"]:
        if d["domain"] == "taiex":
            d["fetched_at"] = "2026-10-30T02:00:00+00:00"
    text = plain(page_text(run(monkeypatch, v)))
    assert re.search(r"⬜ 不適用\s*：\s*取得時間早於觀測日", text)
    assert "-3 日" not in text and "經過 -" not in text


def test_missing_taiex_shows_data_not_ready_and_still_draws_the_other_series(monkeypatch):
    at = run(monkeypatch, ms.view(tw="missing"))
    assert not at.exception
    html = page_text(at)
    assert rules.entry("missing").wording in chips(at, "missing")
    assert re.search(r'data-key="taiex">台股[^<]*<span[^>]*data-status-key="missing"', html)
    assert html.count('class="uv3-chart"') == 1 and html.count("stroke-dasharray") == 1   # 只畫 S&P（單序列；樣式依序列順位＝虛線）
    assert "目前僅顯示可用序列；另一序列" in plain(html) and "暫不進行比較。" in plain(html)
    assert "single_fallback" not in pending_keys(at) and "evidence_single_note" in pending_keys(at)   # 正式字樣不標 pending
    assert "基準日" in plain(html) and "＝100" in plain(html)   # 單序列也標自己的基準日
    assert not re.search(r"取數失敗", plain(html).split("尚未取得")[0])


def test_failed_sp500_shows_fetch_failed_not_data_not_ready_and_no_raw_error(monkeypatch):
    at = run(monkeypatch, ms.view(us="error"))
    html = page_text(at)
    text = plain(html)
    assert "⛔ S&P 500 取數失敗" in text
    assert re.search(r'data-key="sp500">S&amp;P 500[^<]*<span[^>]*data-status-key="fetch_failed"', html)
    assert "secret-token-abc123" not in html and "HTTP 429" not in html      # 失敗原文不上一般畫面
    assert not re.search(r'data-key="sp500">[^<]*<span[^>]*data-status-key="missing"', html)   # 失敗不得冒充缺資料


def test_both_missing_shows_empty_state_without_drawing_an_empty_chart(monkeypatch):
    at = run(monkeypatch, ms.view(tw="missing", us="missing"))
    html = page_text(at)
    assert 'class="uv3-chart"' not in html
    assert "此圖目前沒有可畫的資料" in plain(html) and "chart_empty" not in pending_keys(at)   # 正式字樣（客戶 2026-11-03）
    assert chips(at, "missing").count(rules.entry("missing").wording) >= 2


def test_partial_history_falls_back_to_single_chart_with_insufficient_marked(monkeypatch):
    v = ms.view(us_dates=ms.weekdays("2024-11-01", ms.LAST_US))
    at = run(monkeypatch, v, state={mkt.KEY_PERIOD: "3Y"})
    html = page_text(at)
    assert html.count('class="uv3-chart"') == 1 and html.count("stroke-dasharray") == 0   # 只畫台股（第一條＝實線）
    assert "目前僅顯示可用序列；另一序列" in plain(html) and "資料不足" in plain(html)
    assert not {"fallback_note", "insufficient", "single_fallback"} & pending_keys(at)   # 已核准字樣不再標 pending
    assert "evidence_single_note" in pending_keys(at)        # 首屏漲跌不得被讀成比較
    assert re.search(r'data-key="sp500">S&amp;P 500[^<]*<span[^>]*data-status-key="undetermined"', html)


def test_missing_fred_key_renders_not_configured_not_fetch_failed(monkeypatch):
    t = ms.table(errors={"credit_spread_pct": "未設定 FRED_API_KEY"}, drop=("credit_spread_pct",))
    at = run(monkeypatch, ms.view(key=""), t, state={mkt.KEY_VIEW: "us10y", mkt.KEY_RATES: "credit_spread_pct"})
    html = page_text(at)
    assert "⛔ 利率資料來源尚未設定" in plain(html) and "FRED_API_KEY" not in html   # 不得外漏環境變數名
    assert "美10Y 取數失敗" not in plain(html)


def test_switching_view_to_vix_drops_the_secondary_vix_card_and_keeps_first_screen(monkeypatch):
    at = run(monkeypatch)
    assert html_count(at, 'data-card="vix"') == 1
    at.radio(key=mkt.KEY_VIEW).set_value("vix").run()
    assert not at.exception
    assert html_count(at, 'data-card="vix"') == 0                  # D1：Secondary 不複製 Primary
    assert html_count(at, 'data-card="term_spread_pct"') == 1
    assert re.search(r"台股 近1Y [+-]\d+\.\d\d%", plain(page_text(at)))   # 首屏仍是 TAIEX／S&P
    assert "VIX 資料日 2026-11-02（經過 1 日）" in plain(page_text(at))


def test_switching_period_changes_chart_and_first_screen_changes_together(monkeypatch):
    at = run(monkeypatch)
    one_year = re.search(r"台股 近1Y ([+-]\d+\.\d\d)%", plain(page_text(at))).group(1)
    at.radio(key=mkt.KEY_PERIOD).set_value("3M").run()
    three_month = re.search(r"台股 近3M ([+-]\d+\.\d\d)%", plain(page_text(at))).group(1)
    assert one_year != three_month
    assert "基準日 2026-08-03＝100" in plain(page_text(at))      # 3M 視窗起點為週日 08-02 → 基準日＝08-03（A2；餵足 margin）


def test_rates_radio_switches_sub_series_without_dropping_the_card(monkeypatch):
    at = run(monkeypatch)
    at.radio(key=mkt.KEY_RATES).set_value("policy_rate_pct").run()
    assert not at.exception and html_count(at, 'data-card="policy_rate_pct"') == 1 and html_count(at, 'data-card="term_spread_pct"') == 0


def test_evidence_cards_and_missing_groups_are_present_and_missing_stays_missing(monkeypatch):
    at = run(monkeypatch)
    text = plain(page_text(at))
    for code in ("MKT-1", "MKT-2", "MKT-3"):
        assert html_count(at, f'data-card="{code}"') == 1
    assert "▸ 尚未取得（7 項）" in [e.label for e in at.expander]
    assert "▸ 各項資料狀態" in [e.label for e in at.expander]
    assert "▸ 來源與限制" in [e.label for e in at.expander]
    assert "Yahoo Finance ^TWII（非 TWSE 官方）" in text


def test_every_visible_chip_is_symbol_plus_text_and_comes_from_the_registry(monkeypatch):
    """顏色不是唯一訊息：每個 data-status-key chip 都有符號＋文字，且字樣出自規則表（取數失敗／尚未設定的組合形式除外）。"""
    at = run(monkeypatch, ms.view(us="error"))
    html = page_text(at)
    for key, wording in re.findall(r'data-status-key="([a-z_]+)">([^<]*)<', html):
        entry = rules.entry(key) if key != "neutral" else None
        if entry is None or entry.symbol is None:
            continue
        assert wording.startswith(entry.symbol + " "), (key, wording)


def test_no_direction_words_target_lines_or_threshold_language_in_the_page(monkeypatch):
    text = plain(page_text(run(monkeypatch)))
    for banned in ("偏多", "偏空", "看多", "看空", "牛市", "熊市", "買進", "賣出", "目標價", "警戒", "危機", "正常", "安全", "過熱"):
        assert banned not in text, banned


def test_pending_wording_is_marked_on_screen_and_every_pending_key_exists(monkeypatch):
    at = run(monkeypatch)
    keys = pending_keys(at)
    assert {"title_compare", "preview_banner"} <= keys
    assert keys <= set(W.PREVIEW_PENDING_WORDING)
    # 客戶 2026-11-03 已核准的字樣：畫面上出現、但不再標 pending
    text = plain(page_text(at))
    for approved in ("暫無完整市場綜合判定（尚未建立正式綜合判定規則）", "重要依據", "資料新鮮度", "資料日", "頻率：日｜缺值不補、斷線"):
        assert approved in text
    assert not set(rules.APPROVED_WORDING) & keys


def test_page_imports_no_fixtures_and_no_old_ui(monkeypatch):
    run(monkeypatch)
    import ast
    for rel in ("ui_v3/app_preview.py", "ui_v3/pages/mkt.py", "ui_v3/adapters/market_page.py", "ui_v3/pages/chart_svg.py"):
        tree = ast.parse((Path(APP).parents[1] / rel).read_text(encoding="utf-8"))
        mods = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | \
               {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert not any(m.startswith("ui_v3.fixtures") or m.split(".")[0] in ("ui", "ui_v2", "app") for m in mods), (rel, mods)


def html_count(at, needle: str) -> int:
    return page_text(at).count(needle)
