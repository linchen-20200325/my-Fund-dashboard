# -*- coding: utf-8 -*-
"""逐列資料狀態（`DomainStatus`）離線反例：兩列同樣沒有值，一列「取數失敗」、一列「未評估（undetermined）」。

只測**既有 API**：`ui_v3.viewmodels.market_page.DomainStatus`／`MarketPageModel.statuses`、
`ui_v3.adapters.shell_status.from_market_model`／`latest_fetched_at`、`ui_v3.pages.mkt.status_row_html`、
以及 `app_preview.py` 的 AppTest 渲染（取數函式在測試端換成 `market_stubs` 替身）。不建 renderer、不建新 view model。

固定的事實：
1. 失敗列計入 `failed_count`；未評估列**不**計入 `failed_count`、也**不**計入 `ok_count`（不進成功分母）；
   兩者互換位置時，`failed_count` 1↔0 隨之改變、`ok_count` 不變。
2. 缺日期不補：失敗／未評估列沒有 `fetched_at` 時，`last_fetched_at` 只取其他列的值，不用現在時間、不用 as_of 代替；
   全部都沒有 → None。
3. 逐列文字只由該列自身決定（`status_row_html(row)` 單一參數、不受其他列影響）；失敗與未評估的 `data-status-key` 不同，不互相冒充。
4. 收合／展開：Streamlit 的 `st.expander` 開合是瀏覽器端狀態，伺服器端沒有 API 可操作或觀察；AppTest 的 expander 內容
   不論開合都在，故本檔只能固定「expander 內的逐列 HTML 逐字等於 `status_row_html` 輸出，且不因 session 內任何值而變」，
   **開合動作本身不在本檔涵蓋範圍（缺口，見回報）**。

缺口（既有 API 無法承載，不自創）：`ShellStatus` 沒有「未評估」專用計數；未評估只能由 `total - ok - failed` 反推，
且與 `missing`、`not_configured` 混在同一個餘數裡。`adapters.market_page.domain_state` 也只產生 ok／missing／failed，
不會產生 undetermined（undetermined 列只能直接建構 `DomainStatus`）。

本機執行：pytest tests/ui_v3/test_ui_v3_status_rows_failed_vs_not_evaluated_offline.py -q --noconftest -p no:cacheprovider
"""
from __future__ import annotations

import dataclasses
import inspect
import re
from pathlib import Path

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")

import market_stubs as ms
from ui_v3.adapters import market_page as adapter
from ui_v3.adapters import shell_status
from ui_v3.pages import mkt
from ui_v3.viewmodels import preview_wording as W
from ui_v3.viewmodels.common import STATUS_FAILED, STATUS_MISSING, STATUS_OK, STATUS_UNDETERMINED
from ui_v3.viewmodels.market_page import DomainStatus

APP = str(Path(__file__).resolve().parents[2] / "ui_v3" / "app_preview.py")
STAMP_OK = "2026-11-03T06:00:00+00:00"
STAMP_FAILED = "2026-11-03T09:00:00+00:00"       # 比 ok 列晚；若被當成「最新取得時間」就是失敗列冒充取得

OK_ROW = DomainStatus("taiex", "series_taiex", STATUS_OK, None, "Yahoo FAKE", "2026-11-02", STAMP_OK)
FAILED_ROW = DomainStatus("sp500", "series_sp500", STATUS_FAILED, "fetch_failed", None, None, None)
NOT_EVALUATED_ROW = DomainStatus("vix", "series_vix", STATUS_UNDETERMINED, "too_few_points", None, None, None)
MISSING_ROW = DomainStatus("us10y", "series_us10y", STATUS_MISSING, "missing", None, None, None)


def _model(rows):
    base = adapter.build_market_page(ms.view(), ms.table(), period="1Y")
    return dataclasses.replace(base, statuses=tuple(rows))


def _count(model, fn=None):
    return (fn or shell_status.from_market_model)(model)


def test_two_rows_without_value_are_distinct_facts_at_construction():
    for row in (FAILED_ROW, NOT_EVALUATED_ROW):
        assert row.as_of is None and row.source is None and row.fetched_at is None
    assert FAILED_ROW.status != NOT_EVALUATED_ROW.status and FAILED_ROW.reason_code != NOT_EVALUATED_ROW.reason_code
    with pytest.raises(ValueError):
        DomainStatus("x", "series_taiex", STATUS_FAILED, None, None, None, None)           # 非 ok 必帶原因碼
    with pytest.raises(ValueError):
        DomainStatus("x", "series_taiex", STATUS_UNDETERMINED, None, None, None, None)


def check_counts(count_fn):
    """分母不混同的斷言；mutation 測試也用它驗「壞的計數函式會被抓到」。"""
    both = count_fn(_model([OK_ROW, FAILED_ROW, NOT_EVALUATED_ROW]))
    assert (both.ok_count, both.failed_count, both.total) == (1, 1, 3)
    swapped_out = count_fn(_model([OK_ROW, NOT_EVALUATED_ROW, NOT_EVALUATED_ROW]))      # 失敗列換成未評估列
    assert (swapped_out.ok_count, swapped_out.failed_count, swapped_out.total) == (1, 0, 3)
    only_failed = count_fn(_model([OK_ROW, FAILED_ROW, FAILED_ROW]))
    assert (only_failed.ok_count, only_failed.failed_count) == (1, 2)
    none_ok = count_fn(_model([FAILED_ROW, NOT_EVALUATED_ROW]))                          # 沒有任何成功：未評估不能撐出成功數
    assert (none_ok.ok_count, none_ok.failed_count, none_ok.total, none_ok.level) == (0, 1, 2, "none")


def test_failed_counts_as_failed_and_not_evaluated_stays_out_of_both_numerators():
    check_counts(shell_status.from_market_model)


def test_not_evaluated_and_missing_are_not_counted_as_failed_and_remainder_is_not_split():
    status = _count(_model([OK_ROW, FAILED_ROW, NOT_EVALUATED_ROW, MISSING_ROW]))
    assert (status.ok_count, status.failed_count, status.total) == (1, 1, 4)
    remainder = status.total - status.ok_count - status.failed_count
    assert remainder == 2        # 缺口：未評估與缺資料混在同一個餘數裡，ShellStatus 沒有各自的計數欄位
    assert {f.name for f in dataclasses.fields(status)} == {
        "level", "ok_count", "total", "failed_count", "last_fetched_at", "refresh_available", "refresh_reason_code"}


def test_not_configured_failure_is_not_counted_as_failed():
    row = DomainStatus("us2y", "series_us2y", STATUS_FAILED, adapter.REASON_NOT_CONFIGURED, None, None, None)
    status = _count(_model([OK_ROW, row]))
    assert (status.ok_count, status.failed_count, status.total) == (1, 0, 2)


def test_missing_dates_are_not_filled_in():
    only_undated = _count(_model([FAILED_ROW, NOT_EVALUATED_ROW]))
    assert only_undated.last_fetched_at is None
    mixed = _count(_model([FAILED_ROW, NOT_EVALUATED_ROW, OK_ROW]))
    assert mixed.last_fetched_at == STAMP_OK                       # 只取有值的列；不用現在時間、不用 as_of 代替
    unparseable = DomainStatus("us2y", "series_us2y", STATUS_OK, None, "Yahoo FAKE", "2026-11-02", "2026-11-03 06:00:00")   # 無時區
    assert shell_status.latest_fetched_at([r.fetched_at for r in (unparseable, FAILED_ROW)]) is None


def test_row_html_is_a_pure_function_of_the_row_and_the_two_statuses_are_not_interchangeable():
    assert list(inspect.signature(mkt.status_row_html).parameters) == ["row"]
    failed_html, undetermined_html = mkt.status_row_html(FAILED_ROW), mkt.status_row_html(NOT_EVALUATED_ROW)
    assert 'data-status-key="fetch_failed"' in failed_html and 'data-status-key="undetermined"' not in failed_html
    assert 'data-status-key="undetermined"' in undetermined_html and 'data-status-key="fetch_failed"' not in undetermined_html
    assert mkt.status_row_html(FAILED_ROW) == failed_html          # 同一列兩次輸出逐字相同（與其他列、與呼叫次序無關）
    for html in (failed_html, undetermined_html, mkt.status_row_html(MISSING_ROW)):
        assert not re.search(r"\d{4}-\d{2}-\d{2}", html)           # 沒有日期的列不補日期
    ok_html = mkt.status_row_html(OK_ROW)
    assert "2026-11-02" in ok_html and "Yahoo FAKE" in ok_html


def test_non_ok_rows_do_not_render_source_as_of_or_fetched_at_even_when_the_row_carries_them():
    """既有行為（記錄用）：非 ok 列的 `source`／`as_of`／`fetched_at` 不上畫面（逐列證據只在 ok 列顯示）。"""
    carrying = DomainStatus("sp500", "series_sp500", STATUS_FAILED, "fetch_failed", "Yahoo FAKE", "2026-11-02", STAMP_FAILED)
    html = mkt.status_row_html(carrying)
    assert "Yahoo FAKE" not in html and "2026-11-02" not in html and STAMP_FAILED not in html


def _page(monkeypatch, rows):
    real = adapter.build_market_page

    def build(view, table, **kw):
        return dataclasses.replace(real(view, table, **kw), statuses=tuple(rows))

    monkeypatch.setattr(adapter, "load", lambda sources: (ms.view(), ms.table()))
    monkeypatch.setattr(adapter, "build_market_page", build)
    return streamlit_testing.AppTest.from_file(APP, default_timeout=60).run()


def _status_expander_markdown(at):
    expanders = [e for e in at.expander if e.label == W.text("status_group_title")]
    assert len(expanders) == 1
    return "".join(m.value for m in expanders[0].markdown)


def test_status_expander_content_equals_per_row_html_regardless_of_other_rows_and_reruns(monkeypatch):
    rows = [OK_ROW, FAILED_ROW, NOT_EVALUATED_ROW, MISSING_ROW]
    at = _page(monkeypatch, rows)
    assert not at.exception
    expected = "".join(mkt.status_row_html(r) for r in rows)
    first = _status_expander_markdown(at)
    assert first == expected
    assert _status_expander_markdown(at.run()) == expected         # 再跑一次（模擬 rerun）逐字不變
    reordered = _status_expander_markdown(_page(monkeypatch, list(reversed(rows))))
    assert set(re.findall(r'<div class="uv3-row uv3-status-row">.*?</div>', reordered, re.S)) == \
        set(re.findall(r'<div class="uv3-row uv3-status-row">.*?</div>', expected, re.S))      # 換順序，每列內容不變


# 變異負控：把「未評估」算進成功、或不把失敗算進失敗數的壞計數函式，必須被 check_counts 抓到。
@pytest.mark.parametrize("mutation", ["undetermined_as_ok", "failed_not_counted", "undetermined_as_failed"])
def test_mutated_counters_are_caught(mutation):
    def bad(model):
        rows = model.statuses
        ok = sum(1 for r in rows if r.status == STATUS_OK or (mutation == "undetermined_as_ok" and r.status == STATUS_UNDETERMINED))
        failed = sum(1 for r in rows if (r.status == STATUS_FAILED and mutation != "failed_not_counted")
                     or (mutation == "undetermined_as_failed" and r.status == STATUS_UNDETERMINED))
        level = "ok" if ok == len(rows) else "none" if ok == 0 else "partial"
        return shell_status.ShellStatus(level, ok, len(rows), min(failed, len(rows) - ok), None, False, shell_status.REFRESH_NOT_WIRED)

    with pytest.raises(AssertionError):
        check_counts(bad)
