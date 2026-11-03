# -*- coding: utf-8 -*-
"""客戶 2026-11-03 裁示（`DEC-2026-11-03-09`）：首屏採 C、用字統一。

1. 首屏採 C：「市場狀態」「是否需注意」兩列、各自欄位標籤與各自一枚 chip；「基準日」不再是 chip，改成圖表附近的純文字揭露行
   （字樣不變）；首屏核心數字＋chip 合計仍 ≤5（frozen 44 之十九其一之一第 2 條；不修訂 44、不放寬其他頁）。
2. 用字統一：正式使用「⛔ 利率資料來源尚未設定」「美10Y」「美2Y」；不得再出現被禁的三個舊字樣。

⚠️ 被禁字樣在本檔以執行期拼接，不以字面寫進任何檔案（負控字串不落文件，`CLAUDE.md` §-2.A 第 8 款）。
"""
from __future__ import annotations

import html as htmllib
import re
from pathlib import Path

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")

import market_stubs as ms
from shared.ui_semantics import rules
from ui_v3.adapters import market_page as adapter
from ui_v3.pages import mkt
from ui_v3.viewmodels import preview_wording as W

ROOT = Path(__file__).resolve().parents[2]
APP = str(ROOT / "ui_v3" / "app_preview.py")

# 被禁的三個舊字樣（執行期拼接）
BANNED = (
    "⛔ 尚未設定" + "：利率資料來源",
    "美" + " 10Y",
    "美" + " 2Y",
)


def _banned_hits(text: str) -> list:
    return [b for b in BANNED if b in text]


def _run(monkeypatch, view=None, table=None, *, state=None):
    monkeypatch.setattr(adapter, "load", lambda sources: (view if view is not None else ms.view(), table if table is not None else ms.table()))
    at = streamlit_testing.AppTest.from_file(APP, default_timeout=60)
    for k, v in (state or {}).items():
        at.session_state[k] = v
    return at.run()


def _html(at) -> str:
    return "\n".join([m.value for m in at.markdown] + [t.value for t in at.title])


def _plain(html: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", html))).strip()


_NO_RATES = ("credit_spread_pct", "term_spread_pct", "policy_rate_pct")
SCENARIOS = {
    "complete": lambda: (ms.view(), ms.table(), {}),
    "tw_missing": lambda: (ms.view(tw="missing"), ms.table(), {}),
    "both_failed": lambda: (ms.view(tw="error", us="error", vx="error"), ms.table(), {}),
    "all_missing": lambda: (ms.view(tw="missing", us="missing", vx="missing"),
                            ms.table(drop=("vol_index",) + _NO_RATES), {}),
    "no_rates_key": lambda: (ms.view(key=""), ms.table(errors={k: "x" for k in _NO_RATES}, drop=_NO_RATES), {}),
}


# ───────────── 1. 首屏採 C ─────────────
def _first_screen(html: str) -> str:
    """首屏摘要區＝第一個 `<h3>`（Primary 標題）之前。"""
    return html[: html.index("<h3>")]


def test_first_screen_has_two_separate_labelled_rows_each_with_its_own_chip(monkeypatch):
    html = _html(_run(monkeypatch))
    first = _first_screen(html)
    rows = dict(re.findall(r'<div class="uv3-row" data-field="([a-z_]+)">(.*?)</div>', first, flags=re.S))
    assert set(rows) == {"market_state", "attention"}
    for field, key in (("market_state", "field_market_state"), ("attention", "field_attention")):
        row = rows[field]
        assert rules.APPROVED_WORDING[key].text in _plain(row)
        assert row.count('class="uv3-chip') == 1                       # 各自一枚、不共用
        assert rules.entry("undetermined").wording in _plain(row)      # 符號＋文字（⬜ 無法判定），不只靠顏色
    assert first.index('data-field="market_state"') < first.index('data-field="attention"')
    assert rules.APPROVED_WORDING["hero_sentence"].text in _plain(rows["market_state"])


def test_base_date_is_plain_text_near_the_chart_not_a_chip_and_wording_is_unchanged(monkeypatch):
    html = _html(_run(monkeypatch))
    first = _first_screen(html)
    assert "基準日" not in _plain(first)                                # 首屏不再有基準日 chip
    line = re.search(r'<div class="uv3-note" data-disclosure="base-frequency">(.*?)</div>', html, flags=re.S)
    assert line is not None and "uv3-chip" not in line.group(1)
    assert re.fullmatch(r"基準日 \d{4}-\d{2}-\d{2}＝100；頻率：日｜缺值不補、斷線", _plain(line.group(1)))
    assert html.index("<h3>") < html.index('data-disclosure="base-frequency"') < html.index('class="uv3-chart"')   # 在圖表附近（圖前）
    assert "neutral" not in re.findall(r'data-status-key="([a-z_]+)"', html)                                      # 沒有基準日 chip


@pytest.mark.parametrize("name", list(SCENARIOS))
@pytest.mark.parametrize("view_key", ["compare", "vix", "us10y", "us2y"])
def test_first_screen_chips_plus_core_numbers_stay_within_five(monkeypatch, name, view_key):
    """計法（81 第 10.2 節計數表；44 之十九其一之一第 7 條讀法）：頁級狀態 chip ＋ 頁級核心數字；期間／檢視切換是 display control 不計。
    重要依據的每一格是一個核心數字，缺／失敗時該格改以一枚狀態 chip 取代（仍只佔一個名額）。"""
    view, table, state = SCENARIOS[name]()
    at = _run(monkeypatch, view, table, state={**state, mkt.KEY_VIEW: view_key})
    assert not at.exception
    first = _first_screen(_html(at))
    chips = len(re.findall(r'class="uv3-chip', first))
    numbers = len(re.findall(r"近\d+[A-Z]? [+-]\d+\.\d\d%", _plain(first)))
    evidence_cells = len(re.findall(r'class="uv3-evidence"', first))
    status_chips_fixed = 3                                              # 市場狀態、是否需注意、資料新鮮度
    assert evidence_cells == 2
    # 依據格若有值＝1 個核心數字（不是 chip）；若無值＝1 枚狀態 chip（被 `chips` 計到）
    assert chips - status_chips_fixed + numbers == evidence_cells
    assert chips + numbers == 3 + evidence_cells == 5 and chips + numbers <= 5


def test_first_screen_wording_has_both_field_labels_and_no_merged_label(monkeypatch):
    first = _plain(_first_screen(_html(_run(monkeypatch))))
    assert "市場狀態" in first and "是否需注意" in first
    assert "市場狀態／是否需注意" not in first
    assert "status_row_label" not in W.PREVIEW_PENDING_WORDING


# ───────────── 2. 用字統一 ─────────────
def test_approved_new_wording_is_verbatim_in_decisions_and_evidence():
    decisions = (ROOT / rules.DOC_DECISIONS).read_text(encoding="utf-8")
    evidence = (ROOT / rules.EVIDENCE_FIRST_SCREEN_RULING).read_text(encoding="utf-8")
    for text in (rules.NOT_CONFIGURED_RATES_SOURCE_TEXT, rules.approved("series_us10y").text, rules.approved("series_us2y").text):
        assert text in decisions and text in evidence, text
    assert rules.NOT_CONFIGURED_RATES_SOURCE_TEXT == "⛔ 利率資料來源尚未設定"
    assert (rules.approved("series_us10y").text, rules.approved("series_us2y").text) == ("美10Y", "美2Y")


def test_frozen_44_not_configured_form_is_untouched():
    assert rules.NOT_CONFIGURED_FORM == "⛔ 尚未設定：<哪一項>"
    assert rules.entry("not_configured").wording == "⛔ 尚未設定"       # 同頁其餘位置仍寫狀態族短句


@pytest.mark.parametrize("name", list(SCENARIOS))
@pytest.mark.parametrize("view_key", ["compare", "vix", "us10y", "us2y"])
def test_rendered_page_never_shows_the_banned_old_wording(monkeypatch, name, view_key):
    view, table, state = SCENARIOS[name]()
    at = _run(monkeypatch, view, table, state={**state, mkt.KEY_VIEW: view_key})
    text = _plain(_html(at)) + " " + " ".join(str(o) for r in at.radio for o in r.options) + " ".join(r.label for r in at.radio)
    assert _banned_hits(text.replace("\xa0", " ")) == [], (name, view_key)


def test_no_banned_wording_in_ui_v3_sources_or_rules_or_wording_tables():
    files = [p for p in (ROOT / "ui_v3").rglob("*.py")] + [p for p in (ROOT / "shared" / "ui_semantics").rglob("*.py")]
    assert files
    for path in files:
        assert _banned_hits(path.read_text(encoding="utf-8")) == [], path.name
    for entry in list(rules.APPROVED_WORDING.values()) + list(W.PREVIEW_PENDING_WORDING.values()):
        for banned in BANNED:
            assert banned not in entry.text, entry.key


def test_banned_negative_control_detects_an_injected_old_wording():
    """負控：把舊字樣注入規則表以外的任一段文字，偵測必須轉紅（證明上面的掃描不是空掃）。"""
    for banned in BANNED:
        assert _banned_hits("x " + banned + " y") == [banned]
    assert _banned_hits("⛔ 利率資料來源尚未設定 美10Y 美2Y") == []


def test_series_labels_come_from_the_rule_table_not_pending(monkeypatch):
    assert W.text("series_us10y") == "美10Y" and W.text("series_us2y") == "美2Y"
    assert W.is_approved("series_us10y") and W.is_approved("series_us2y")
    assert "series_us10y" not in W.PREVIEW_PENDING_WORDING and "series_us2y" not in W.PREVIEW_PENDING_WORDING
    html = mkt.status_html("failed", "not_configured", "series_us10y")
    assert _plain(html) == "⛔ 利率資料來源尚未設定" and "data-pending-wording" not in html


def test_ok_fixture_has_two_ok_evidence_numbers(monkeypatch):
    at = _run(monkeypatch)
    assert len(re.findall(r"近\d+[A-Z]? [+-]\d+\.\d\d%", _plain(_first_screen(_html(at))))) == 2
