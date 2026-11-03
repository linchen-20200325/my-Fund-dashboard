# -*- coding: utf-8 -*-
"""渲染輸出的核准字樣逐字比對規則表（`APPROVED_WORDING`），並補「一頁只交代一次」「未知原因代碼」「位數未裁示」守衛。

規則表 `text` 模板只靠 apptest 擋不夠：這裡把模板轉成 regex（欄位換成樣式），逐字（含全形標點）比對畫面。
"""
from __future__ import annotations

import dataclasses
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
from ui_v3.viewmodels.common import STATUS_OK, STATUS_UNDETERMINED
from ui_v3.viewmodels.market_page import EvidenceChange, EvidenceFact

APP = str(Path(__file__).resolve().parents[2] / "ui_v3" / "app_preview.py")
DATE = r"\d{4}-\d{2}-\d{2}"


def run(monkeypatch, view, table=None, *, state=None, wrap=None):
    table = table if table is not None else ms.table()
    monkeypatch.setattr(adapter, "load", lambda sources: (view, table))
    if wrap is not None:
        real = adapter.build_market_page
        monkeypatch.setattr(adapter, "build_market_page", lambda *a, **k: wrap(real(*a, **k)))
    at = streamlit_testing.AppTest.from_file(APP, default_timeout=60)
    for k, v in (state or {}).items():
        at.session_state[k] = v
    return at.run()


def visible(at) -> str:
    """去標籤（不補空白，讓巢狀 span 的句子保持連續）＋還原跳脫；回畫面上連續的可見文字。"""
    raw = "\n".join(m.value for m in at.markdown)
    return htmllib.unescape(re.sub(r"<[^>]+>", "", raw))


def template_regex(key: str, **patterns: str) -> "re.Pattern":
    """規則表 `text` 模板 → regex：模板固定字元逐字（含全形標點）、`{欄位}` 換成指定樣式。"""
    body = re.escape(rules.APPROVED_WORDING[key].text)
    for name, pattern in patterns.items():
        body = body.replace(re.escape("{" + name + "}"), f"(?:{pattern})")
    assert "\\{" not in body, f"{key} 還有未指定樣式的欄位"
    return re.compile(body)


NO_KEY = lambda: (ms.view(key=""), ms.table(errors={k: "未設定" for k in ("credit_spread_pct", "term_spread_pct", "policy_rate_pct")},
                                           drop=("credit_spread_pct", "term_spread_pct", "policy_rate_pct")))


# ───────────── 1. 「哪一項」一頁只交代一次 ─────────────
FULL = re.compile(r"⛔ 尚未設定：利率資料來源")
SHORT = re.compile(r"⛔ 尚未設定(?!：)")


@pytest.mark.parametrize("view_key", ["compare", "vix", "us10y", "us2y"])
def test_no_fred_key_full_sentence_once_per_page_rest_is_status_family(monkeypatch, view_key):
    view, table = NO_KEY()
    at = run(monkeypatch, view, table, state={mkt.KEY_VIEW: view_key})
    assert not at.exception
    text = visible(at)
    assert len(FULL.findall(text)) == 1, (view_key, FULL.findall(text))
    assert rules.entry("not_configured").wording in text


def test_no_fred_key_repeat_positions_use_status_family_wording(monkeypatch):
    view, table = NO_KEY()
    text = visible(run(monkeypatch, view, table, state={mkt.KEY_VIEW: "us10y"}))
    assert len(SHORT.findall(text)) >= 1          # 同頁其餘位置寫狀態族句
    assert text.index("⛔ 尚未設定：利率資料來源") <= text.index(SHORT.search(text).group(0))   # 完整句在最先出現的位置


@pytest.mark.parametrize("view_key", ["compare", "vix", "us10y"])
def test_other_scenarios_without_not_configured_are_unchanged(monkeypatch, view_key):
    text = visible(run(monkeypatch, ms.view(), state={mkt.KEY_VIEW: view_key}))
    assert "尚未設定" not in text


def test_helpers_outside_render_always_write_the_full_sentence():
    html = mkt.status_html("failed", "not_configured", "series_us10y")
    assert "利率資料來源" in html and "利率資料來源" in mkt.status_html("failed", "not_configured", "series_us10y")


# ───────────── 2. 渲染輸出 vs APPROVED_WORDING ─────────────
def test_rendered_approved_wording_matches_rule_table_verbatim_on_normal_page(monkeypatch):
    text = visible(run(monkeypatch, ms.view()))
    assert template_regex("base_chip", date=DATE).search(text)
    assert rules.APPROVED_WORDING["frequency_line"].text in text
    assert rules.APPROVED_WORDING["hero_sentence"].text in text
    assert template_regex("data_date_line", label=r"[^\n]+?", date=DATE, days=r"\d+").search(text)


def test_rendered_single_fallback_and_insufficient_match_rule_table(monkeypatch):
    text = visible(run(monkeypatch, ms.view(us_dates=ms.weekdays("2024-11-01", ms.LAST_US)), state={mkt.KEY_PERIOD: "3Y"}))
    assert template_regex("single_fallback", reason=r"[^，。]+").search(text)
    assert rules.APPROVED_WORDING["insufficient"].text in text


def test_rendered_chart_empty_matches_rule_table(monkeypatch):
    view = ms.view(tw="missing", us="missing", vx="missing")
    text = visible(run(monkeypatch, view, ms.table(drop=("vol_index", "credit_spread_pct", "term_spread_pct", "policy_rate_pct"))))
    assert rules.APPROVED_WORDING["chart_empty"].text in text


def test_approved_templates_used_by_page_are_in_rule_table_not_a_local_copy():
    for key in ("base_chip", "frequency_line", "single_fallback", "data_date_line", "hero_sentence", "insufficient",
                "chart_empty", "reason_unknown"):
        assert W.text(key, **{f: "X" for f in re.findall(r"\{(\w+)\}", rules.APPROVED_WORDING[key].text)}) == \
               rules.APPROVED_WORDING[key].text.format(**{f: "X" for f in re.findall(r"\{(\w+)\}", rules.APPROVED_WORDING[key].text)})
        assert key not in W.PREVIEW_PENDING_WORDING


# ───────────── 3. 未知原因代碼走渲染層 ─────────────
UNKNOWN = "zz_unmapped_reason"


def _inject_unknown(model):
    changes = (EvidenceChange(model.evidence_changes[0].key, STATUS_UNDETERMINED, UNKNOWN, None),) + tuple(model.evidence_changes[1:])
    card = model.primary_card
    disclosure = card.disclosure
    if disclosure is not None and disclosure.mode in ("single", "fallback"):
        disclosure = dataclasses.replace(disclosure, fallback_reason=UNKNOWN,
                                         series_issues=tuple(dataclasses.replace(i, reason_code=UNKNOWN) for i in disclosure.series_issues))
        card = dataclasses.replace(card, disclosure=disclosure)
    return dataclasses.replace(model, evidence_changes=changes, primary_card=card)


@pytest.mark.parametrize("scenario", ["complete", "partial"])
def test_unknown_reason_code_never_reaches_screen_and_says_reason_unknown(monkeypatch, scenario):
    if scenario == "complete":
        at = run(monkeypatch, ms.view(), wrap=_inject_unknown)
    else:
        at = run(monkeypatch, ms.view(us_dates=ms.weekdays("2024-11-01", ms.LAST_US)), state={mkt.KEY_PERIOD: "3Y"}, wrap=_inject_unknown)
    assert not at.exception
    raw = "\n".join(m.value for m in at.markdown)
    assert UNKNOWN not in raw
    assert rules.APPROVED_WORDING["reason_unknown"].text == "原因未明" and "原因未明" in visible(at)
    assert "已停更" not in visible(at)


def test_reason_phrase_default_is_reason_unknown_and_known_codes_are_mapped():
    assert mkt._reason_phrase(UNKNOWN) == "reason_unknown" and mkt._reason_phrase(None) == "reason_unknown"
    for code, key in (("missing", "reason_missing"), ("fetch_failed", "reason_fetch_failed"), ("not_configured", "reason_not_configured"),
                      ("insufficient", "insufficient"), ("no_common_base", "reason_no_common"),
                      ("too_few_common_days", "reason_few_common"), ("too_few_points", "reason_few_points")):
        assert mkt._reason_phrase(code) == key
    assert mkt.reason_span(UNKNOWN) == W.span("reason_unknown")


# ───────────── 4. 位數未裁示的指標：不套用預設 2 位 ─────────────
def test_undecided_decimals_fact_is_not_rounded_to_two_places():
    fact = EvidenceFact("fact_leading", STATUS_OK, None, 101.23456, "index", "2026-10-31")
    out = mkt.fact_html(fact)
    assert "101.23456" in out and "101.23<" not in out and "101.23 " not in out
    fact2 = EvidenceFact("fact_coincident", STATUS_OK, None, 7.0, "%", "2026-10-31")
    assert "7.0%" in mkt.fact_html(fact2)


def test_decided_decimals_facts_keep_their_fixed_places():
    assert "18.3" in mkt.fact_html(EvidenceFact("fact_vix", STATUS_OK, None, 18.2567, "index", "2026-10-31"))
    assert "31.457" in mkt.fact_html(EvidenceFact("fact_fx", STATUS_OK, None, 31.45678, "", "2026-10-31"))


# ───────────── 狀態不共用：連續 render／多執行緒 render ─────────────
def _render_capture(model, out):
    """以假 streamlit 收集 render() 輸出的 markdown（只測「已交代」狀態的隔離，不起 Streamlit）。"""
    import sys
    import types

    calls = []
    fake = types.SimpleNamespace(
        markdown=lambda html, **k: calls.append(html), title=lambda *a, **k: None, divider=lambda: None,
        radio=lambda *a, **k: None, expander=lambda *a, **k: __import__("contextlib").nullcontext(),
        columns=lambda n: [__import__("contextlib").nullcontext() for _ in range(n if isinstance(n, int) else 1)],
        session_state={},
    )
    return fake, calls


def _model_no_key():
    view, table = NO_KEY()
    return adapter.build_market_page(view, table, period="1Y", primary_view="us10y", rates_key="credit_spread_pct")


def _full_count(monkeypatch_streamlit, model):
    import sys
    fake, calls = monkeypatch_streamlit
    sys.modules["streamlit"], saved = fake, sys.modules.get("streamlit")
    try:
        mkt.render(model)
    finally:
        sys.modules["streamlit"] = saved
    return len(FULL.findall(htmllib.unescape(re.sub(r"<[^>]+>", "", "\n".join(calls)))))


def test_consecutive_and_threaded_renders_each_write_the_full_sentence_exactly_once():
    import threading
    model = _model_no_key()
    assert mkt._NC_STATE.get() is None
    assert [_full_count(_render_capture(model, None), model) for _ in range(2)] == [1, 1]   # 第二次不受第一次殘留影響
    assert mkt._NC_STATE.get() is None                                                      # render 結束即還原
    results = []
    barrier = threading.Barrier(2)

    def worker():
        barrier.wait()
        results.append(mkt.status_html("failed", "not_configured", "series_us10y").count("利率資料來源"))
        token = mkt._NC_STATE.set({"seen": False})
        try:
            first = mkt.status_html("failed", "not_configured", "series_us10y")
            second = mkt.status_html("failed", "not_configured", "series_us10y")
        finally:
            mkt._NC_STATE.reset(token)
        results.append((first.count("利率資料來源"), second.count("利率資料來源")))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(r for r in results if isinstance(r, tuple)) == [(1, 0), (1, 0)]
