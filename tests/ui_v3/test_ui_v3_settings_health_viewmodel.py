# -*- coding: utf-8 -*-
"""⚙️ 資料健康度第一切片 view model（`ui_v3/viewmodels/settings_health.py`）的離線契約與負控。

範圍（刻意窄）：只測純 view model。**沒有 renderer、沒有 registry／app_preview 變更、沒有取數、沒有真實資料**；
輸入全是測試端人造的 `DomainStatus`（FAKE 數值）。類別覆蓋（`coverage`）與列→類別對映由**測試注入**，
本檔不主張「哪個類別真的未接線／屬於哪一類」——那是需要證據的事實（線框讀法未經客戶核准）。

固定的事實：
1. 五態互斥且相加＝總數；未評估（undetermined）不進 ok、不進 failed；「尚未設定」不算取數失敗；
2. 沒有資料的類別 `tally is None`（不是 0）；模型沒有任何「整體／全站」欄位；
3. 缺時間保留缺值（不補現在、不以 as_of 代替）；ok 列缺證據欄位會如實列為 gaps；
4. 同輸入同輸出（確定性）；列順序＝輸入順序、類別順序固定；
5. fail-closed：未對映的列、覆蓋與資料矛盾、coverage 缺類／多類／值非法、重複 key、未知 status 一律拒絕；
6. 變異負控：把關鍵判斷改壞，`check_semantics()` 必須轉紅。

本機執行（本環境無 streamlit／conftest 依賴；本檔不需要它們）：
    pytest tests/ui_v3/test_ui_v3_settings_health_viewmodel.py -q --noconftest -p no:cacheprovider
"""
from __future__ import annotations

import ast
import dataclasses
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ui_v3.viewmodels import settings_health as sh
from ui_v3.viewmodels.common import STATUS_FAILED, STATUS_MISSING, STATUS_OK, STATUS_UNDETERMINED
from ui_v3.viewmodels.market_page import DomainStatus

STAMP = "2026-11-03T06:00:00+00:00"
OK_A = DomainStatus("taiex", "series_taiex", STATUS_OK, None, "Yahoo FAKE", "2026-11-02", STAMP)
OK_B = DomainStatus("us10y", "series_us10y", STATUS_OK, None, "FRED FAKE", "2026-11-02", STAMP)
FAILED = DomainStatus("sp500", "series_sp500", STATUS_FAILED, "fetch_failed", None, None, None)
NOT_CONF = DomainStatus("us2y", "series_us2y", STATUS_FAILED, "not_configured", None, None, None)
MISSING = DomainStatus("vix", "series_vix", STATUS_MISSING, "missing", None, None, None)
UNDET = DomainStatus("vix", "series_vix", STATUS_UNDETERMINED, "too_few_points", None, None, None)
UNDET_SP = DomainStatus("sp500", "series_sp500", STATUS_UNDETERMINED, "too_few_points", None, None, None)

# 注入用的覆蓋與對映（測試替身；不是事實宣稱）。
CATEGORY = {"taiex": "market", "sp500": "market", "vix": "market", "us10y": "rates", "us2y": "rates"}
COVERAGE = {
    "market": sh.COVERAGE_COVERED, "rates": sh.COVERAGE_COVERED, "fund": sh.COVERAGE_NOT_WIRED,
    "nav": sh.COVERAGE_NOT_WIRED, "holdings": sh.COVERAGE_NOT_EVALUATED, "dividend": sh.COVERAGE_NOT_WIRED,
    "fx": sh.COVERAGE_PENDING_RULING, "macro_cycle": sh.COVERAGE_NOT_WIRED,
}


def build(rows, coverage=None, category=None):
    """預設：只有「實際出現資料列」的類別為 covered，其餘類別沿用 COVERAGE 的未覆蓋種類（避免單列測試被迫湊滿兩類）。"""
    cat = category or CATEGORY
    if coverage is None:
        used = {cat[r.key] for r in rows if hasattr(r, "key") and r.key in cat}
        coverage = {k: (sh.COVERAGE_COVERED if k in used else
                        (v if v != sh.COVERAGE_COVERED else sh.COVERAGE_NOT_WIRED)) for k, v in COVERAGE.items()}
    return sh.build_settings_health(rows, row_category=cat, coverage=coverage)


def tally_of(model, key):
    return next(c.tally for c in model.categories if c.category_key == key)


def check_semantics():
    """關鍵語意的集中斷言；變異負控也用它驗「壞實作會被抓到」。"""
    one_each = build([OK_A, FAILED, NOT_CONF, MISSING, OK_B])
    m, r = tally_of(one_each, "market"), tally_of(one_each, "rates")
    assert (m.ok, m.failed, m.missing, m.not_configured, m.undetermined) == (1, 1, 1, 0, 0)
    assert (r.ok, r.failed, r.not_configured) == (1, 0, 1)                      # 尚未設定 ≠ 取數失敗
    undet = tally_of(build([OK_A, FAILED, UNDET, OK_B]), "market")
    assert (undet.ok, undet.failed, undet.undetermined) == (1, 1, 1)             # 未評估不進成功、也不進失敗
    swapped = tally_of(build([OK_A, UNDET_SP, UNDET, OK_B]), "market")              # 失敗列換成未評估列
    assert (swapped.ok, swapped.failed, swapped.undetermined) == (1, 0, 2)
    for model in (one_each,):
        assert all(c.tally is None for c in model.categories if c.coverage != sh.COVERAGE_COVERED)   # 無資料≠0
        for cat in model.categories:
            if cat.tally is not None:
                assert cat.tally.total == sum(1 for x in model.rows if x.category_key == cat.category_key)


# ── 五態與計數 ───────────────────────────────────────────────────────────────

def test_check_semantics_holds_on_real_implementation():
    check_semantics()


def test_five_states_are_mutually_distinct_for_rows_without_value():
    model = build([FAILED, NOT_CONF, MISSING])
    assert [r.state for r in model.rows] == [sh.STATE_FAILED, sh.STATE_NOT_CONFIGURED, sh.STATE_MISSING]
    assert build([UNDET, OK_B]).rows[0].state == sh.STATE_UNDETERMINED
    assert len(set(sh.HEALTH_STATES)) == len(sh.HEALTH_STATES) == 5


def test_tally_total_equals_row_count_and_has_no_remainder_field():
    tally = tally_of(build([OK_A, FAILED, MISSING, OK_B]), "market")
    assert tally.total == 3
    assert {f.name for f in dataclasses.fields(tally)} == set(sh.HEALTH_STATES)       # 沒有「其他／餘數」欄


# ── 範圍揭露：沒有資料的類別不是 0；沒有整體欄位 ──────────────────────────────

def test_uncovered_categories_have_no_tally_not_zero():
    model = build([OK_A, OK_B])
    assert model.uncovered_keys == ("fund", "nav", "holdings", "dividend", "fx", "macro_cycle")
    assert model.covered_keys == ("market", "rates")
    for cat in model.categories:
        if cat.category_key in model.uncovered_keys:
            assert cat.tally is None


def test_model_has_no_overall_or_site_wide_field():
    names = {f.name for f in dataclasses.fields(sh.SettingsHealthModel)}
    assert names == {"categories", "rows", "freshness_state"}
    public = {n for n in dir(sh.SettingsHealthModel) if not n.startswith("_")}
    assert not {n for n in public | names if any(w in n for w in ("overall", "site", "level", "health_score", "all_ok"))}


def test_all_five_series_ok_does_not_make_uncovered_categories_ok():
    def ok(key, source):
        return DomainStatus(key, f"series_{key}", STATUS_OK, None, source, "2026-11-02", STAMP)

    model = build([ok("taiex", "a"), ok("sp500", "b"), ok("vix", "c"), ok("us10y", "d"), ok("us2y", "e")])
    assert tally_of(model, "market").ok == 3 and tally_of(model, "rates").ok == 2
    assert len(model.uncovered_keys) == 6                     # 範圍內全 ok，範圍外仍是 6 類無從計數


def test_freshness_state_is_fixed_undetermined():
    assert build([OK_A]).freshness_state == "undetermined"
    with pytest.raises(ValueError):
        dataclasses.replace(build([OK_A]), freshness_state="fresh")


# ── 缺值保留與證據缺口 ───────────────────────────────────────────────────────

def test_missing_dates_are_kept_missing_not_filled():
    for row in build([FAILED, UNDET, NOT_CONF]).rows:
        assert row.as_of is None and row.fetched_at is None and row.source is None


def test_ok_row_missing_evidence_fields_is_reported_as_gaps_not_filled():
    partial = DomainStatus("taiex", "series_taiex", STATUS_OK, None, "Yahoo FAKE", None, None)
    row = build([partial]).rows[0]
    assert row.state == sh.STATE_OK and row.gaps == ("as_of", "fetched_at")
    assert row.as_of is None and row.fetched_at is None                              # 不以 now、不以他欄補
    assert build([OK_A]).rows[0].gaps == ()
    assert build([FAILED]).rows[0].gaps == ()                                        # 非 ok 列沒有「應有」的證據欄位
    with pytest.raises(ValueError):                                                  # gaps 不能被偽造成空
        dataclasses.replace(row, gaps=())


def test_module_never_reads_time_or_does_io():
    src = pathlib.Path(sh.__file__).read_text(encoding="utf-8")
    imported = {a.name.split(".")[0] for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module.split(".")[0] for n in ast.walk(ast.parse(src)) if isinstance(n, ast.ImportFrom) and n.module}
    assert not imported & {"datetime", "time", "os", "pathlib", "requests", "streamlit", "random"}


# ── 確定性與順序 ─────────────────────────────────────────────────────────────

def test_same_input_same_output_and_order_is_input_order():
    rows = [OK_B, FAILED, OK_A]
    first, second = build(rows), build(list(rows))
    assert first == second
    assert [r.key for r in first.rows] == ["us10y", "sp500", "taiex"]                # 列順序＝輸入順序
    assert [c.category_key for c in first.categories] == list(sh.HEALTH_CATEGORY_KEYS)   # 類別順序固定


def test_reordering_rows_does_not_change_any_tally():
    a, b = build([OK_A, FAILED, OK_B, NOT_CONF]), build([NOT_CONF, OK_B, FAILED, OK_A])
    assert a.categories == b.categories
    assert sorted(a.rows, key=lambda r: r.key) == sorted(b.rows, key=lambda r: r.key)


def test_each_row_depends_only_on_itself():
    alone = build([FAILED]).rows[0]
    assert build([OK_A, FAILED, MISSING, OK_B]).rows[1] == alone


# ── fail-closed ──────────────────────────────────────────────────────────────

def test_row_without_category_mapping_is_rejected_not_dropped_or_guessed():
    with pytest.raises(ValueError, match="沒有類別對映"):
        build([OK_A], category={"us10y": "rates"})


def test_row_in_unknown_category_is_rejected():
    with pytest.raises(ValueError):
        build([OK_A], category={"taiex": "crypto"})


def test_row_under_uncovered_category_contradicts_coverage_and_is_rejected():
    with pytest.raises(ValueError, match="互相矛盾"):
        build([OK_A], category={"taiex": "fund"}, coverage=COVERAGE)


def test_covered_category_without_rows_is_rejected():
    with pytest.raises(ValueError):
        build([OK_A], coverage=COVERAGE)       # coverage 宣告 rates 已覆蓋，卻沒有任何 rates 列


@pytest.mark.parametrize("bad", [
    {k: v for k, v in COVERAGE.items() if k != "fx"},                       # 缺一類
    {**COVERAGE, "crypto": sh.COVERAGE_NOT_WIRED},                           # 多一類
    {**COVERAGE, "fx": "ok"},                                                # 值非法（不得用 ok 冒充覆蓋）
])
def test_coverage_must_be_exactly_eight_valid_categories(bad):
    with pytest.raises(ValueError):
        build([OK_A, OK_B], coverage=bad)


def test_duplicate_row_key_and_non_domainstatus_rejected():
    with pytest.raises(ValueError):
        build([OK_A, OK_A])
    with pytest.raises(TypeError):
        build([{"key": "taiex"}])


def test_unknown_status_is_rejected_not_defaulted():
    fake = DomainStatus.__new__(DomainStatus)                                # 繞過建構檢查，模擬未來新增的 status
    for name, value in dict(key="taiex", label_key="series_taiex", status="stale", reason_code=None,
                            source=None, as_of=None, fetched_at=None).items():
        object.__setattr__(fake, name, value)
    with pytest.raises(ValueError, match="status 必須在|無法對映"):   # 未知 status 在 DomainStatus 重建或 _state_of 任一處被拒，皆為 fail-closed
        build([fake])


def test_row_invariants_at_construction():
    good = build([FAILED]).rows[0]
    with pytest.raises(ValueError):
        dataclasses.replace(good, reason_code=None)                          # 非 ok 必帶原因碼
    with pytest.raises(ValueError):
        dataclasses.replace(good, state=sh.STATE_NOT_CONFIGURED)             # 尚未設定與原因碼必須同時成立
    with pytest.raises(ValueError):
        dataclasses.replace(good, state="stale")


def test_category_health_invariants():
    tally = sh.StateTally(1, 0, 0, 0, 0)
    with pytest.raises(ValueError):
        sh.CategoryHealth("fund", sh.COVERAGE_NOT_WIRED, tally)              # 無資料類別不得帶 tally
    with pytest.raises(ValueError):
        sh.CategoryHealth("market", sh.COVERAGE_COVERED, None)
    with pytest.raises(ValueError):
        sh.CategoryHealth("market", sh.COVERAGE_COVERED, sh.StateTally(0, 0, 0, 0, 0))   # 已覆蓋卻 0 列
    with pytest.raises(ValueError):
        sh.StateTally(-1, 0, 0, 0, 0)
    with pytest.raises(ValueError):
        sh.StateTally(True, 0, 0, 0, 0)


def test_model_rejects_tally_that_disagrees_with_rows():
    model = build([OK_A, FAILED, OK_B])
    forged = tuple(dataclasses.replace(c, tally=sh.StateTally(3, 0, 0, 0, 0)) if c.category_key == "market" else c
                   for c in model.categories)
    with pytest.raises(ValueError, match="tally 與資料列不符"):
        dataclasses.replace(model, categories=forged)


def test_no_screen_wording_in_module_constants():
    """view model 只放鍵值，不放畫面字樣（字樣全部待客戶定字，不得從這裡漏出去）。"""
    for name in ("HEALTH_CATEGORY_KEYS", "COVERAGE_KINDS", "HEALTH_STATES", "GAP_FIELDS"):
        for value in getattr(sh, name):
            assert value.isascii() and value == value.lower() and " " not in value


# ── 與既有 ShellStatus 計數交叉核對（同一批列，兩條路徑的 ok／failed 必須一致）──────────────

def test_ok_and_failed_counts_agree_with_existing_shell_status_counter():
    shell_status = pytest.importorskip("ui_v3.adapters.shell_status")
    market_page = pytest.importorskip("ui_v3.viewmodels.market_page")
    import market_stubs as ms
    from ui_v3.adapters import market_page as adapter

    base = adapter.build_market_page(ms.view(), ms.table(), period="1Y")
    rows = (OK_A, FAILED, UNDET, NOT_CONF, OK_B)
    model = dataclasses.replace(base, statuses=rows)
    status = shell_status.from_market_model(model)
    health = build(list(rows))
    ok = sum(c.tally.ok for c in health.categories if c.tally)
    failed = sum(c.tally.failed for c in health.categories if c.tally)
    assert (status.ok_count, status.failed_count, status.total) == (ok, failed, len(rows))
    # ShellStatus 把「未評估」與「尚未設定」混在 total-ok-failed 的餘數裡；本模型把它們拆開（補上 #1311 自陳的缺口）。
    remainder = status.total - status.ok_count - status.failed_count
    split = sum(c.tally.undetermined + c.tally.not_configured + c.tally.missing for c in health.categories if c.tally)
    assert remainder == split == 2
    assert market_page.DomainStatus is DomainStatus


# ── 變異負控：把關鍵判斷改壞，check_semantics 必須轉紅 ──────────────────────────────

def _bad_state_of(mutation):
    real = sh._state_of

    def bad(row):
        if mutation == "undetermined_as_ok" and row.status == STATUS_UNDETERMINED:
            return sh.STATE_OK
        if mutation == "undetermined_as_failed" and row.status == STATUS_UNDETERMINED:
            return sh.STATE_FAILED
        if mutation == "not_configured_as_failed" and row.status == STATUS_FAILED:
            return sh.STATE_FAILED
        if mutation == "failed_as_missing" and row.status == STATUS_FAILED and row.reason_code != "not_configured":
            return sh.STATE_MISSING
        return real(row)

    return bad


@pytest.mark.parametrize("mutation", ["undetermined_as_ok", "undetermined_as_failed", "failed_as_missing"])
def test_mutated_state_mapping_is_caught_by_semantic_check(monkeypatch, mutation):
    monkeypatch.setattr(sh, "_state_of", _bad_state_of(mutation))
    with pytest.raises(AssertionError):            # 必須是語意斷言抓到，不是建構錯誤
        check_semantics()


def test_mutated_not_configured_as_failed_is_caught_by_the_row_invariant(monkeypatch):
    """尚未設定被算成取數失敗：由 `HealthRow` 的「not_configured 狀態與原因碼必須同時成立」不變量在建構時擋下（另一道獨立防線）。"""
    monkeypatch.setattr(sh, "_state_of", _bad_state_of("not_configured_as_failed"))
    with pytest.raises(ValueError, match="尚未設定 ≠ 取數失敗"):
        check_semantics()


def test_mutated_uncovered_tally_zero_instead_of_none_is_caught(monkeypatch):
    real_init = sh.CategoryHealth.__post_init__

    def lenient(self):                                   # 拿掉「非 covered 不得帶 tally」並改用 0 計數
        if self.coverage != sh.COVERAGE_COVERED:
            object.__setattr__(self, "tally", sh.StateTally(0, 0, 0, 0, 0))
            return
        real_init(self)

    monkeypatch.setattr(sh.CategoryHealth, "__post_init__", lenient)
    # 這個變異同時繞過 SettingsHealthModel 的 recount？不——model 對非 covered 只查「沒有資料列」，故模型可建出來，
    # 此時 check_semantics 的 `tally is None` 斷言必須抓到「無資料被表達成 0」。
    with pytest.raises(AssertionError):
        check_semantics()


def test_mutated_gap_detection_is_caught(monkeypatch):
    monkeypatch.setattr(sh, "_gaps_of", lambda row, state: ())
    partial = DomainStatus("taiex", "series_taiex", STATUS_OK, None, "Yahoo FAKE", None, None)
    with pytest.raises(ValueError, match="gaps 必須如實"):
        build([partial])


def test_blank_string_fields_are_treated_as_missing_not_crashing_the_page():
    blank = DomainStatus("taiex", "series_taiex", STATUS_OK, None, "", "  ", STAMP)
    row = build([blank]).rows[0]
    assert (row.source, row.as_of, row.fetched_at) == (None, None, STAMP)
    assert row.gaps == ("source", "as_of")                       # 缺口如實列出，不補值
