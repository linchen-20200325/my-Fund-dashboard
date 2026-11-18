# -*- coding: utf-8 -*-
"""路徑 B（單檔基本資料查詢）adapter 測試（`DEC-2026-11-18-02`，待核；僅內部切片）：
T-A 入口攔截／次序／原值／不回顯、T-B 來源狀態與欄位缺值、T-C fail-closed、T-D 不洩漏、T-E 失敗不得映射為「基金不存在」、
T-F import／無 I/O 靜態守衛、T-G 與 L2 形狀的離線差分（AST 讀碼鎖死，**不 import 真實 L1／L2**）。

本機執行：
    pytest tests/ui_v3/test_ui_v3_fund_lookup_adapter.py -q --noconftest -p no:cacheprovider

⚠️ 全部輸入是**測試注入**的假 loader 與假 L2 回傳字典（形狀見 `fund_lookup_support.py`）；沒有取數、沒有 secrets、沒有真實網路
（autouse 守衛把 socket／urllib／http.client／requests 的入口換成會 raise 的版本，每個測試結尾斷言嘗試次數為 0）。
負控字串（毒字串）一律在測試中隨機現編，不寫死。
"""
from __future__ import annotations

import ast
import inspect
import json
import logging
import pathlib
import re
import subprocess
import sys

import pytest
from _pytest.outcomes import Failed, Skipped

import fund_lookup_support as S
import ui_v3_guard_lib as lib
from fund_lookup_support import no_real_network  # noqa: F401 - autouse fixture
from ui_v3.adapters import fund_lookup as adapter
from ui_v3.adapters.fund_lookup import adapt_profile_result, lookup_fund, not_queried, screen_input
from ui_v3.viewmodels.fund_lookup import (
    BLOCKED_REASONS,
    INPUT_ECHO_MAX,
    PAGE_UNMATCHED_REASONS,
    SOURCE_FAILED_REASONS,
    FieldStatus,
    FieldView,
    FundLookupView,
    LookupContractError,
    LookupSourceError,
    LookupState,
)

ADAPTER_REL = "ui_v3/adapters/fund_lookup.py"
VIEWMODEL_REL = "ui_v3/viewmodels/fund_lookup.py"
PROD_RELS = (ADAPTER_REL, VIEWMODEL_REL)
L2_DIR = lib.ROOT / "services" / "v2_tables"
L1_DECLARED = lib.ROOT / "repositories" / "fund" / "declared_profile.py"
MANIFEST = lib.ROOT / "tests" / "fixtures" / "moneydj_basic" / "manifest.json"
CODE = S.SAMPLE_CODE

ISIN_LIKE = ["US0378331005", "us0378331005", "lu0123456789", " US0378331005 ", "JP3633400001", "KY1234567890", "US0378331006",
             "US 0378331005", "US-0378331005", "US.0378331005", "US_0378331005", "US,0378331005", "us 0378 3310 05", "U-S-0-3-7-8-3-3-1-0-0-5", "AB000000000" + "1"]
URL_LIKE = ["https://www.moneydj.com/funddj/yp/yp011001.djhtm?a=ACTI71", "http://x", "HTTP", "Http://X", "hTTps", "www.moneydj.com/x", "WWW.X.COM", "moneydj",
            "MONEYDJ", "x?a=ACTI71", "ACTI71?", "a=ACTI71", "ACT&I71", "AC#TI71", "AC%TI71", "AC@TI71", "//host", "AC:TI71", "AC/TI71", "AC\\TI71",
            "ACHTTP1"]    # 最後一個是已知誤攔面：合法形狀但含 `http` 子字串，偏保守側攔下
NON_ASCII_OR_CONTROL = ["ＡＣＴＩ７１", "AC​TI71", "​ACTI71", "ACTI71​", "AC\x7fTI71", "\x7fACTI71", "ACTI71\x7f", "AC\x85TI71", "\x85ACTI71",
                        "ACTI71\x85", "AC\xa0TI71", "\xa0ACTI71", "ACTI71\xa0", "\x1cACTI71\n", "\x1fACTI71", "ACTI71\x1d", "\x0bACTI71", "ACTI71\x0c",
                        "\tACTI71", "ACTI71\t", "ACTI71\n", "\nACTI71", "AC\nTI71", "AC\tTI71", "\t", "\n", " \t ", "\r\n", "é", "基金", "\x00", "AC\x00TI71"]
BAD_FORMAT = ["AB", "A", "AC TI71", "ACTI 71", "A" * 31, "ACTI71-", "-ACTI71", "ACTI71--AB", "ACTI71-A", "ACTI71-" + "B" * 21, "AC.TI71", "AC_TI71", "AC,TI71",
              "AC(TI71)", "AC*TI71", "AC+TI71", "AC~TI71", "AC'TI71", 'AC"TI71', "AC!TI71", "AC$TI71", "AC^TI71", "AC;TI71", "AC<TI71", "AC|TI71"]


def real_codes() -> list:
    if not MANIFEST.exists():
        S.unavailable(f"離線樣本 manifest 不存在：{MANIFEST.relative_to(lib.ROOT)}")
    pages = json.loads(MANIFEST.read_text(encoding="utf-8"))["pages"]
    return sorted({p["code"] for p in pages if p.get("kind") == "real_code"})


def _capture_logs():
    class Handler(logging.Handler):
        def __init__(self):
            super().__init__(logging.DEBUG)
            self.lines = []

        def emit(self, record):
            self.lines.append(record.getMessage())

    handler = Handler()
    root = logging.getLogger()
    previous = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    return handler, lambda: (root.removeHandler(handler), root.setLevel(previous))


def everything_visible(view) -> str:
    """view 上所有看得到的東西：repr、str、每個欄位（遞迴）。"""
    parts = [repr(view), str(view)]
    stack = [view]
    while stack:
        obj = stack.pop()
        if hasattr(obj, "__dataclass_fields__"):
            for f in obj.__dataclass_fields__:
                child = getattr(obj, f)
                parts.append(str(child))
                stack.append(child)
    return " ".join(parts)


# ═════════════════════════ T-A 入口攔截 ═════════════════════════

@pytest.mark.parametrize("raw", ISIN_LIKE)
def test_isin_shaped_inputs_are_blocked_without_calling_the_loader_and_are_not_echoed(raw):
    loader = S.CountingLoader(S.profile())
    view = lookup_fund(loader, raw)
    assert (view.state, view.reason_code, view.input_code, view.fields) == (LookupState.BLOCKED, "isin_shape", None, None)
    assert loader.calls == [] and screen_input(raw) == "isin_shape"
    assert re.sub(r"\D", "", raw) not in everything_visible(view) or not re.sub(r"\D", "", raw)


@pytest.mark.parametrize("raw", URL_LIKE)
def test_url_shaped_inputs_are_blocked_without_calling_the_loader_and_are_not_echoed(raw):
    loader = S.CountingLoader(S.profile())
    view = lookup_fund(loader, raw)
    assert (view.state, view.reason_code, view.input_code) == (LookupState.BLOCKED, "url_shape", None)
    assert loader.calls == [] and raw not in everything_visible(view)


@pytest.mark.parametrize("raw", NON_ASCII_OR_CONTROL)
def test_whitelist_violations_anywhere_in_the_raw_string_are_blocked_before_any_strip(raw):
    """含頭尾位置（str.strip 會吃掉的字元）：先檢查白名單，不能先 strip。"""
    loader = S.CountingLoader(S.profile())
    view = lookup_fund(loader, raw)
    reason = "blank" if raw.strip(" ") == "" else "control_or_non_ascii"
    assert (view.state, view.reason_code) == (LookupState.BLOCKED, reason)
    assert loader.calls == []
    if reason == "control_or_non_ascii":
        assert view.input_code is None and raw not in everything_visible(view)
        text = everything_visible(view)
        assert all(c not in text for c in raw if not 0x20 <= ord(c) <= 0x7E)


@pytest.mark.parametrize("raw", BAD_FORMAT)
def test_bad_formats_are_blocked_as_code_format_and_may_be_echoed_within_the_limit(raw):
    loader = S.CountingLoader(S.profile())
    view = lookup_fund(loader, raw)
    assert (view.state, view.reason_code, view.input_code) == (LookupState.BLOCKED, "code_format", raw)
    assert loader.calls == []


@pytest.mark.parametrize("raw", ["", " ", "   ", " " * INPUT_ECHO_MAX])
def test_blank_inputs_are_blocked_and_kept_because_they_hold_only_ascii_spaces(raw):
    loader = S.CountingLoader(S.profile())
    view = lookup_fund(loader, raw)
    assert (view.state, view.reason_code, view.input_code) == (LookupState.BLOCKED, "blank", raw)
    assert loader.calls == []


def test_tab_and_newline_are_not_blank_they_are_control():
    for raw in ("\t", "\n", " \n ", "\r"):
        assert screen_input(raw) == "control_or_non_ascii"


@pytest.mark.parametrize("raw", [None, 0, 1, 1.5, True, b"ACTI71", ["ACTI71"], ("ACTI71",), {"a": 1}, object()])
def test_non_string_inputs_are_a_programming_error_not_a_state(raw):
    loader = S.CountingLoader(S.profile())
    with pytest.raises(LookupContractError):
        lookup_fund(loader, raw)
    with pytest.raises(LookupContractError):
        screen_input(raw)
    assert loader.calls == []


def test_isin_boundaries_are_structural_and_check_digit_is_not_verified():
    assert screen_input("US037833100") is None              # 11 字元：不是 ISIN 形，是合法形狀的代碼
    assert screen_input("AB012345678A") is None             # 12 字元但末碼為字母：不是 ISIN 形，放行
    assert screen_input("ABCDEFGHIJKL") is None             # 12 個字母：末碼非數字，放行
    assert screen_input("0A0378331005") is None             # 前 2 碼不是字母，放行
    assert screen_input("AB-0123456789") == "isin_shape"    # 12 字元含連字號：移除非英數後是 ISIN 形，攔下（已知偏保守的誤攔面）
    assert screen_input("US0378331005X") is None            # 13 碼：不是 ISIN 形，合法純代碼形狀 → 放行（契約包稱走 code_format，與 PURE_CODE_PATTERN 不一致，見檔頭記錄）
    assert screen_input("US03783310051") is None            # 13 碼：同上
    assert screen_input("US0378331006") == "isin_shape" and screen_input("US0378331005") == "isin_shape"   # 檢查碼對錯都一樣


def test_thirteen_char_variant_is_released_and_echoed_within_the_limit():
    loader = S.CountingLoader(S.profile("US0378331005X"))
    view = lookup_fund(loader, "US0378331005X")
    assert view.state is LookupState.RESULT and view.input_code == "US0378331005X" and loader.calls == ["US0378331005X"]


def test_inputs_length_gate_acts_on_the_raw_unstripped_string():
    exact = CODE + " " * (INPUT_ECHO_MAX - len(CODE))
    over = exact + " "
    loader = S.CountingLoader(S.profile())
    ok = lookup_fund(loader, exact)
    assert ok.state is LookupState.RESULT and ok.input_code == exact and loader.calls == [CODE]
    blocked = S.CountingLoader(S.profile())
    view = lookup_fund(blocked, over)
    assert (view.state, view.reason_code, view.input_code) == (LookupState.BLOCKED, "code_format", None) and blocked.calls == []
    for raw in (" " * (INPUT_ECHO_MAX + 1), "A" * 10_000, " " * 5_000 + CODE + " " * 5_000, "​" * 1_000, "https://" + "a" * 1_000):
        loader = S.CountingLoader(S.profile())
        view = lookup_fund(loader, raw)
        assert (view.state, view.reason_code, view.input_code) == (LookupState.BLOCKED, "code_format", None), raw[:20]
        assert loader.calls == []


def test_exactly_at_the_limit_a_non_code_is_blocked_but_kept():
    raw = "A" * INPUT_ECHO_MAX
    view = lookup_fund(S.CountingLoader(), raw)
    assert (view.reason_code, view.input_code) == ("code_format", raw)


def test_rule_order_first_match_decides_the_reason():
    assert screen_input("​" * (INPUT_ECHO_MAX + 1)) == "code_format"          # 1a 先於 2
    assert screen_input("https://ＡＢ") == "control_or_non_ascii"                   # 2 先於 3
    assert screen_input("http://US0378331005") == "url_shape"                      # 3 先於 4
    assert screen_input("US0378331005?") == "url_shape"
    assert screen_input("US 0378331005 ") == "isin_shape"                           # 4 先於 5
    assert screen_input("   ") == "blank"                                          # 1 先於 2
    assert screen_input("\t") == "control_or_non_ascii"
    assert screen_input("") == "blank"


def test_allowed_input_is_passed_to_the_loader_stripped_of_ascii_spaces_only_with_case_kept():
    loader = S.CountingLoader(lambda q: S.profile(q))
    view = lookup_fund(loader, "  acti71-ab  ")
    assert loader.calls == ["acti71-ab"]                                          # 去頭尾 ASCII 空格；大小寫原樣（L2 自行大寫化）
    assert view.state is LookupState.RESULT and view.input_code == "  acti71-ab  "     # 輸入原值連空白都保留，不 strip 也不轉大小寫


def test_suffixed_codes_are_opaque_strings_and_are_released():
    for raw in ("ACDD01-EQTAL005", "TLZF9", "acti71", "ABC", "A" * 30, "A" * 30 + "-" + "B" * 20):
        assert screen_input(raw) is None, raw


def test_real_moneydj_sample_codes_are_never_blocked():
    codes = real_codes()
    assert len(codes) >= 5
    for code in codes:
        assert screen_input(code) is None and screen_input(code.lower()) is None, code


def test_screen_input_is_pure_and_returns_none_or_a_known_blocked_reason():
    for raw in [*ISIN_LIKE, *URL_LIKE, *NON_ASCII_OR_CONTROL, *BAD_FORMAT, CODE, ""]:
        assert screen_input(raw) in (None, *BLOCKED_REASONS)
    assert not any(r in {"key_rejected"} for r in {screen_input(r) for r in [*ISIN_LIKE, *URL_LIKE, *NON_ASCII_OR_CONTROL, *BAD_FORMAT]})


def test_blocked_inputs_never_leave_their_content_in_log_output():
    handler, restore = _capture_logs()
    try:
        for raw in (*URL_LIKE, *ISIN_LIKE):
            lookup_fund(S.sentinel_loader(), raw)
    finally:
        restore()
    assert not [line for line in handler.lines if any(tag in line for tag in ("moneydj", "0378331005", "http"))]


# ═════════════════════════ T-B 來源狀態與欄位缺值 ═════════════════════════

def run(result, raw=CODE):
    loader = S.CountingLoader(result)
    return lookup_fund(loader, raw), loader


def test_all_fields_present_gives_a_result_with_each_value():
    view, loader = run(S.profile())
    assert view.state is LookupState.RESULT and view.reason_code is None and loader.calls == [CODE]
    f = view.fields
    assert (f.fund_name, f.dividend_policy, f.inception_on) == (FieldView(FieldStatus.VALUE, S.SAMPLE_NAME), FieldView(FieldStatus.VALUE, "dist"),
                                                                 FieldView(FieldStatus.VALUE, S.SAMPLE_INCEPTION))
    assert f.mgmt_fee_rate_pct == FieldView(FieldStatus.MISSING)


@pytest.mark.parametrize("policy", ["accum", "dist"])
def test_both_dividend_policy_values_pass_through_as_codes_not_wording(policy):
    view, _ = run(S.profile(dividend_policy=S.cell("ok", policy)))
    assert view.fields.dividend_policy.value == policy


STATUS_TO_FIELD = [("ok", FieldStatus.VALUE), ("not_ready", FieldStatus.MISSING), ("inconsistent", FieldStatus.CONFLICT)]


@pytest.mark.parametrize("field,okvalue", [("dividend_policy", "accum"), ("inception_on", "1999-12-31")])
@pytest.mark.parametrize("status,expected", STATUS_TO_FIELD)
def test_each_optional_field_maps_cell_status_independently(field, okvalue, status, expected):
    cell = S.cell(status, okvalue if status == "ok" else None)
    view, _ = run(S.profile(**{field: cell}))
    assert view.state is LookupState.RESULT
    got = getattr(view.fields, field)
    assert got.status is expected and got.value == (okvalue if status == "ok" else None)
    others = {n: getattr(view.fields, n) for n in ("fund_name", "dividend_policy", "inception_on") if n != field}
    assert others["fund_name"].status is FieldStatus.VALUE


def test_every_combination_of_missing_policy_and_inception_is_a_result_with_visible_gaps():
    for pol in ("ok", "not_ready"):
        for inc in ("ok", "not_ready"):
            view, _ = run(S.profile(dividend_policy=S.cell(pol, "dist" if pol == "ok" else None),
                                    inception_on=S.cell(inc, S.SAMPLE_INCEPTION if inc == "ok" else None)))
            assert view.state is LookupState.RESULT
            assert (view.fields.dividend_policy.status is FieldStatus.VALUE) == (pol == "ok")
            assert (view.fields.inception_on.status is FieldStatus.VALUE) == (inc == "ok")


def test_fee_is_always_missing_in_a_result():
    for reason in (None, "no source", "x"):
        view, _ = run(S.profile(mgmt_fee_rate_pct=S.cell("not_ready", None, reason=reason)))
        assert view.fields.mgmt_fee_rate_pct == FieldView(FieldStatus.MISSING)


@pytest.mark.parametrize("cooling,reason", [(False, "source_failed"), (True, "source_cooling")])
def test_source_failure_is_its_own_state_and_cooling_is_its_own_reason(cooling, reason):
    view, loader = run(S.failed_profile(cooling=cooling))
    assert (view.state, view.reason_code, view.fields, view.input_code) == (LookupState.SOURCE_FAILED, reason, None, CODE)
    assert len(loader.calls) == 1


@pytest.mark.parametrize("source_status,reason", [("unrecognized_page", "unrecognized_page"), ("not_found", "no_page"), ("not_listed", "source_not_listed")])
def test_page_unmatched_states_have_their_own_reason_codes_and_never_become_source_failures(source_status, reason):
    view, _ = run(S.unmatched_profile(source_status))
    assert (view.state, view.reason_code, view.fields) == (LookupState.PAGE_UNMATCHED, reason, None)
    assert view.state is not LookupState.SOURCE_FAILED


@pytest.mark.parametrize("name_status", ["not_ready", "inconsistent"])
def test_ok_source_without_a_confirmed_name_shows_nothing_else(name_status):
    view, _ = run(S.profile(fund_name=S.cell(name_status, None)))
    assert (view.state, view.reason_code, view.fields) == (LookupState.PAGE_UNMATCHED, "name_unconfirmed", None)
    assert "2010" not in everything_visible(view) and "dist" not in everything_visible(view)


def test_other_sources_failing_and_currency_trouble_do_not_change_the_result():
    """B6：TDCC／FundClear 失敗、幣別格 inconsistent／fetch_failed、table_wide_failed 為真，而 MoneyDJ 為 ok ⇒ 仍是同一個 RESULT。"""
    baseline, _ = run(S.profile())
    variants = [
        S.profile(tdcc="failed", fundclear="failed"), S.profile(tdcc="code_unmapped"), S.profile(fundclear="not_listed"),
        S.profile(ccy=S.cell("inconsistent", None, reason="各來源幣別不一致")), S.profile(ccy=S.cell("fetch_failed", None)),
        S.profile(ccy=S.cell("not_ready", None)), S.profile(table_wide_failed=True), S.profile(tdcc="failed", ccy=S.cell("fetch_failed"), table_wide_failed=True),
    ]
    for result in variants:
        view, _ = run(result)
        assert view == baseline


def test_other_sources_ok_do_not_rescue_a_failed_moneydj():
    view, _ = run(S.failed_profile())
    assert view.state is LookupState.SOURCE_FAILED
    result = S.failed_profile()
    result["source_status"][CODE]["TDCC"] = S.source_entry("ok")
    result["source_status"][CODE]["FundClear"] = S.source_entry("ok")
    assert run(result)[0].state is LookupState.SOURCE_FAILED


def test_l2_rejecting_the_key_is_key_rejected_and_keeps_the_input():
    view, loader = run(S.rejected_profile())
    assert (view.state, view.reason_code, view.input_code, view.fields) == (LookupState.BLOCKED, "key_rejected", CODE, None)
    assert len(loader.calls) == 1


def test_loader_receives_exactly_one_call_with_the_stripped_query_text():
    loader = S.CountingLoader(lambda q: S.profile(q))
    lookup_fund(loader, " Abc123 ")
    assert loader.calls == ["Abc123"]


def test_cells_key_must_be_the_exact_query_text_case_and_all():
    """B8：`cells` 鍵必須是 adapter 傳給 loader 的那一個字串；大小寫不同＝契約不符，不得悄悄挑一個。"""
    with pytest.raises(LookupContractError):
        lookup_fund(S.CountingLoader(lambda q: S.profile(q.upper())), "acti71")
    with pytest.raises(LookupContractError):
        lookup_fund(S.CountingLoader(lambda q: S.profile(" " + q)), "acti71")
    assert lookup_fund(S.CountingLoader(lambda q: S.profile(q)), "acti71").state is LookupState.RESULT


# ── loader 例外 ──

class _AssemblerNetworkError(Exception):
    """組裝端自己的例外型別（不是 LookupSourceError）——不在可轉換範圍。"""


@pytest.mark.parametrize("exc_type", [LookupSourceError, ConnectionError, TimeoutError, ConnectionResetError, ConnectionRefusedError, BrokenPipeError,
                                      ConnectionAbortedError])
@pytest.mark.parametrize("poison_index", range(4))
def test_explicit_fetch_exceptions_become_source_failed_without_any_text(exc_type, poison_index):
    poison = S.poisons()[poison_index]
    handler, restore = _capture_logs()
    try:
        view, loader = run(exc_type(poison))
    finally:
        restore()
    assert (view.state, view.reason_code, view.fields, view.input_code) == (LookupState.SOURCE_FAILED, "loader_io_error", None, CODE)
    assert poison not in everything_visible(view) and all(poison not in line for line in handler.lines)
    assert any(exc_type.__name__ in line for line in handler.lines)        # 留下型別名，不是靜默吞掉
    assert len(loader.calls) == 1


def test_socket_timeout_is_the_builtin_timeout_error():
    import socket
    assert socket.timeout is TimeoutError
    assert run(socket.timeout("x"))[0].reason_code == "loader_io_error"


@pytest.mark.parametrize("exc", [TypeError("t"), ValueError("v"), KeyError("k"), AssertionError("a"), RuntimeError("r"), FileNotFoundError("f"),
                                 PermissionError("p"), OSError(5, "io"), IsADirectoryError("d"), ZeroDivisionError(), AttributeError("x"),
                                 LookupContractError("bad"), _AssemblerNetworkError("net"), UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad")])
def test_programming_or_contract_errors_from_the_loader_propagate_and_are_never_a_state(exc):
    with pytest.raises(type(exc)):
        run(exc)


def test_broad_oserror_is_not_treated_as_a_fetch_failure():
    """不用廣義 OSError：它含 FileNotFoundError／PermissionError 等多半是設定或程式問題的子類。"""
    for exc in (OSError("x"), FileNotFoundError("x"), PermissionError("x")):
        with pytest.raises(type(exc)):
            run(exc)
    assert not issubclass(OSError, (LookupSourceError, ConnectionError, TimeoutError))


@pytest.mark.parametrize("exc", [KeyboardInterrupt, SystemExit, GeneratorExit])
def test_base_exceptions_are_never_swallowed(exc):
    with pytest.raises(exc):
        run(exc())


def test_not_queried_is_empty():
    assert not_queried() == FundLookupView(LookupState.NOT_QUERIED)
    assert (not_queried().input_code, not_queried().fields, not_queried().reason_code) == (None, None, None)


def test_loader_must_be_injected_there_is_no_default():
    for fn, expected in ((lookup_fund, ["loader", "raw_input"]), (adapt_profile_result, ["input_code", "query_text", "raw_result"])):
        params = inspect.signature(fn).parameters
        assert list(params) == expected
        assert [p.default for p in params.values()] == [inspect.Parameter.empty] * len(params)
    for bad in (None, "load", 7, ()):
        with pytest.raises(LookupContractError):
            lookup_fund(bad, CODE)                                       # type: ignore[arg-type]
    with pytest.raises(TypeError):
        lookup_fund()                                                    # type: ignore[call-arg]


# ═════════════════════════ T-C fail-closed ═════════════════════════

@pytest.mark.parametrize("raw", [None, [], (), "ok", 0, 1.5, b"x", [("cells", {})], object(), {}, {"cells": {}}, {"source_status": {}},
                                 {"cells": None, "source_status": None}])
def test_wrong_shapes_fail_closed(raw):
    with pytest.raises(LookupContractError):
        lookup_fund(S.CountingLoader(raw), CODE)


@pytest.mark.parametrize("key", ["cells", "source_status"])
def test_missing_required_top_level_keys_fail_closed(key):
    result = S.profile()
    del result[key]
    with pytest.raises(LookupContractError):
        run(result)


@pytest.mark.parametrize("keys_of", ["cells", "source_status"])
@pytest.mark.parametrize("keys", [(), ("OTHER1",), (CODE, "OTHER1"), ("acti71",), (CODE.lower(),)])
def test_cells_and_source_status_must_have_exactly_the_queried_code_as_their_only_key(keys_of, keys):
    result = S.profile()
    original = result[keys_of][CODE]
    result[keys_of] = {k: original for k in keys}
    with pytest.raises(LookupContractError):
        run(result)


@pytest.mark.parametrize("container", ["cells", "source_status"])
@pytest.mark.parametrize("bad", [None, [], "x", 0, ()])
def test_per_code_entries_must_be_dicts(container, bad):
    result = S.profile()
    result[container][CODE] = bad
    with pytest.raises(LookupContractError):
        run(result)


@pytest.mark.parametrize("field", adapter.L2_READ_CELL_FIELDS)
def test_a_missing_read_cell_fails_closed_when_the_source_is_ok(field):
    result = S.profile()
    del result["cells"][CODE][field]
    with pytest.raises(LookupContractError):
        run(result)


@pytest.mark.parametrize("field", adapter.L2_READ_CELL_FIELDS)
@pytest.mark.parametrize("bad", [None, "ok", 1, [], ()])
def test_a_non_dict_cell_fails_closed(field, bad):
    with pytest.raises(LookupContractError):
        run(S.profile(**{field: bad}))


@pytest.mark.parametrize("field", adapter.L2_READ_CELL_FIELDS)
@pytest.mark.parametrize("drop", ["status", "value"])
def test_a_cell_without_status_or_value_fails_closed(field, drop):
    cell = S.cell("ok", "x")
    del cell[drop]
    with pytest.raises(LookupContractError):
        run(S.profile(**{field: cell}))


@pytest.mark.parametrize("field", adapter.L2_READ_CELL_FIELDS)
@pytest.mark.parametrize("status", ["OK", "Ok", "ok ", "", "done", "unknown", "error", "missing", "failed", "ready", None, 1, True, ["ok"], b"ok"])
def test_unknown_or_mistyped_cell_status_fails_closed_never_downgraded_to_missing(field, status):
    with pytest.raises(LookupContractError):
        run(S.profile(**{field: S.cell(status, None)}))


@pytest.mark.parametrize("field", adapter.L2_READ_CELL_FIELDS)
def test_ok_without_a_value_and_not_ok_with_a_value_both_fail_closed(field):
    with pytest.raises(LookupContractError):
        run(S.profile(**{field: S.cell("ok", None)}))
    for status in ("not_ready", "inconsistent"):
        with pytest.raises(LookupContractError):
            run(S.profile(**{field: S.cell(status, "leftover")}))


@pytest.mark.parametrize("field", adapter.L2_READ_CELL_FIELDS)
def test_fetch_failed_under_an_ok_source_is_a_contract_violation(field):
    with pytest.raises(LookupContractError):
        run(S.profile(**{field: S.cell("fetch_failed", None)}))


@pytest.mark.parametrize("cell", [S.cell("ok", 1.5), S.cell("ok", "1.5"), S.cell("ok", 0), S.cell("ok", 0.0), S.cell("ok", ""), S.cell("inconsistent", None),
                                  S.cell("fetch_failed", None), S.cell("not_ready", 0), S.cell("not_ready", "")])
def test_an_unexpected_fee_value_or_status_fails_closed(cell):
    """C5：經理費率目前恆缺值；任何數值（含 0）、空字串或非 not_ready 狀態都是契約違反。"""
    with pytest.raises(LookupContractError):
        run(S.profile(mgmt_fee_rate_pct=cell))
    with pytest.raises(LookupContractError):
        run(S.profile(fund_name=S.cell("not_ready", None), mgmt_fee_rate_pct=cell))      # 名稱未確認也一樣：先驗再判斷


@pytest.mark.parametrize("bad", ["monthly", "Dist", "ACCUM", "dist ", "", "none", "0", "不配息", 1, True, ["dist"], b"dist"])
def test_dividend_policy_value_outside_accum_or_dist_fails_closed(bad):
    with pytest.raises(LookupContractError):
        run(S.profile(dividend_policy=S.cell("ok", bad)))


@pytest.mark.parametrize("bad", ["2010-5-3", "20100503", "2010/05/03", "2025-02-29", "2010-13-01", "1899-12-31", "0099-01-01", "2010-05-03T00:00", "", "N/A",
                                 20100503, True, ["2010-05-03"]])
def test_inception_value_that_is_not_an_iso_date_fails_closed(bad):
    with pytest.raises(LookupContractError):
        run(S.profile(inception_on=S.cell("ok", bad)))


@pytest.mark.parametrize("bad", ["", "   ", 5, True, ["x"], b"x", {"a": 1}])
def test_a_confirmed_name_must_be_a_non_blank_string(bad):
    with pytest.raises(LookupContractError):
        run(S.profile(fund_name=S.cell("ok", bad)))


@pytest.mark.parametrize("source", [None, [], "ok", 0, (), {"status": "ok"}])
def test_a_malformed_primary_source_entry_fails_closed(source):
    result = S.profile()
    result["source_status"][CODE]["MoneyDJ"] = source
    with pytest.raises(LookupContractError):
        run(result)


def test_source_status_without_the_primary_source_key_fails_closed_unless_it_is_empty():
    result = S.profile()
    result["source_status"][CODE] = {"TDCC": S.source_entry("ok"), "FundClear": S.source_entry("ok")}
    with pytest.raises(LookupContractError):
        run(result)


@pytest.mark.parametrize("status", ["OK", "Ok", "ok ", "", "success", "error", "code_unmapped", "fetch_failed", "not_ready", "empty", None, 1, True, ["ok"]])
def test_unknown_source_status_fails_closed(status):
    result = S.profile()
    result["source_status"][CODE]["MoneyDJ"] = {"status": status, "error": None, "cooling": False, "cooling_remaining_sec": None}
    with pytest.raises(LookupContractError):
        run(result)


@pytest.mark.parametrize("cooling", [None, 1, 0, "False", "", [], 0.0])
def test_cooling_must_be_a_real_bool(cooling):
    for status in ("ok", "failed", "not_found"):
        result = S.profile(moneydj=status)
        result["source_status"][CODE]["MoneyDJ"]["cooling"] = cooling
        with pytest.raises(LookupContractError):
            run(result)


@pytest.mark.parametrize("drop", ["status", "cooling"])
def test_source_entry_without_status_or_cooling_fails_closed(drop):
    result = S.profile()
    del result["source_status"][CODE]["MoneyDJ"][drop]
    with pytest.raises(LookupContractError):
        run(result)


def test_adapt_profile_result_revalidates_its_own_inputs():
    good = S.profile()
    assert adapt_profile_result(CODE, CODE, good).state is LookupState.RESULT
    for input_code in (None, 1, "", "US0378331005", "https://x", "​AB", "A" * 65, " "):
        with pytest.raises(LookupContractError):
            adapt_profile_result(input_code, CODE, good)                                  # type: ignore[arg-type]
    for query_text in (None, "acti71", " ACTI71", "ACTI71 ", "OTHER1", ""):
        with pytest.raises(LookupContractError):
            adapt_profile_result(CODE, query_text, good)                                  # type: ignore[arg-type]
    assert adapt_profile_result("  " + CODE + " ", CODE, good).input_code == "  " + CODE + " "


def test_contract_errors_from_a_misbehaving_loader_still_raise_and_are_not_turned_into_a_source_failure():
    for bad in (None, {}, "ok", [], S.profile(fund_name=S.cell("weird", None)), {"cells": {}, "source_status": {}}):
        with pytest.raises(LookupContractError):
            run(bad)


@pytest.mark.parametrize("poison_index", range(4))
def test_contract_error_messages_name_fields_and_types_only(poison_index):
    poison = S.poisons()[poison_index]
    p = S.cell
    attempts = [
        poison, [poison], {poison: poison}, {"cells": poison, "source_status": poison},
        {"cells": {CODE: poison}, "source_status": {CODE: poison}},
        S.profile(fund_name=p("weird", poison)), S.profile(fund_name=p(poison, poison)), S.profile(fund_name=p("ok", [poison])),
        S.profile(dividend_policy=p("ok", poison)), S.profile(inception_on=p("ok", poison)), S.profile(mgmt_fee_rate_pct=p("ok", poison)),
        S.profile(moneydj=poison), S.profile(**{"fund_name": poison}),
        {"cells": {poison: {}}, "source_status": {poison: {}}},
    ]
    for raw in attempts:
        with pytest.raises(LookupContractError) as info:
            run(raw)
        assert poison not in str(info.value) and poison not in repr(info.value.args)
        assert info.value.__cause__ is None and info.value.__suppress_context__


# ═════════════════════════ T-D 不洩漏 ═════════════════════════

class Probe(dict):
    """記錄被讀取的鍵（getitem／get／contains／pop），用來證明 adapter 只讀被允許的鍵。"""

    def __init__(self, data, seen, label):
        super().__init__(data)
        self._seen, self._label = seen, label

    def __getitem__(self, key):
        self._seen.add((self._label, key))
        return super().__getitem__(key)

    def get(self, key, default=None):
        self._seen.add((self._label, key))
        return super().get(key, default)

    def __contains__(self, key):
        self._seen.add((self._label, key))
        return super().__contains__(key)


def probed(result, seen):
    code = next(iter(result["cells"]))
    cells = {f: Probe(c, seen, "cell") for f, c in result["cells"][code].items()}
    entry = {src: Probe(v, seen, "source") for src, v in result["source_status"][code].items()}
    return Probe({**result, "cells": Probe({code: Probe(cells, seen, "cellmap")}, seen, "cells"),
                  "source_status": Probe({code: Probe(entry, seen, "entry")}, seen, "statuses")}, seen, "result")


def test_adapter_reads_only_the_allowed_keys_and_never_touches_other_sources_currency_or_free_text():
    seen: set = set()
    view = adapt_profile_result(CODE, CODE, probed(S.profile(), seen))
    assert view.state is LookupState.RESULT
    allowed = {("result", "cells"), ("result", "source_status"), ("cells", CODE), ("statuses", CODE), ("entry", "MoneyDJ"),
               ("source", "status"), ("source", "cooling"), ("cell", "status"), ("cell", "value")}
    allowed |= {("cellmap", f) for f in adapter.L2_READ_CELL_FIELDS}
    extra = {s for s in seen if s not in allowed}
    assert extra == set(), extra
    assert ("cell", "reason") not in seen and ("result", "rows") not in seen and ("result", "declared") not in seen
    assert ("result", "table_wide_failed") not in seen and ("cellmap", "ccy") not in seen and ("entry", "TDCC") not in seen


@pytest.mark.parametrize("poison_index", range(4))
def test_free_text_raw_and_error_fields_never_reach_the_view_or_the_log(poison_index):
    poison = S.poisons()[poison_index]
    cells = {f: S.cell("ok", v, reason=poison, raw={"MoneyDJ": poison, "TDCC": poison}) for f, v in
             (("fund_name", "基金甲"), ("ccy", "USD"), ("inception_on", "2010-05-03"), ("dividend_policy", "dist"))}
    cells["mgmt_fee_rate_pct"] = S.cell("not_ready", None, reason=poison)
    results = [
        S.profile(cells=cells), S.failed_profile(), S.failed_profile(cooling=True), S.unmatched_profile("unrecognized_page"),
        S.unmatched_profile("not_found"), S.unmatched_profile("not_listed"), S.rejected_profile(),
    ]
    for result in results:
        result["source_status"][CODE] = {k: dict(v, error=poison) for k, v in result["source_status"][CODE].items()}
        result["rows"][0]["note"] = poison
        result["declared"][CODE] = (poison, poison)
        result["backend"] = poison
        handler, restore = _capture_logs()
        try:
            view, _ = run(result)
        finally:
            restore()
        assert poison not in everything_visible(view)
        assert all(poison not in line for line in handler.lines)


def test_unknown_extra_top_level_keys_are_ignored_not_carried():
    poison = S.poisons()[0]
    assert poison not in everything_visible(run(dict(S.profile(), future_field=poison))[0])


def test_view_never_names_a_source_currency_or_time():
    view, _ = run(S.profile())
    text = everything_visible(view).lower()
    for word in ("moneydj", "tdcc", "fundclear", "ccy", "usd", "fetched", "observed", "2026-11-18", "t01:02"):
        assert word not in text, word


# ═════════════════════════ T-E 失敗不得映射為「基金不存在」 ═════════════════════════

def all_outputs():
    """一組涵蓋全部狀態與原因碼的輸出（BLOCKED 全部原因、SOURCE_FAILED 全部原因、PAGE_UNMATCHED 全部原因、RESULT、NOT_QUERIED）。"""
    outs = [not_queried(), run(S.profile())[0], run(S.rejected_profile())[0], run(S.failed_profile())[0], run(S.failed_profile(cooling=True))[0],
            run(S.profile(fund_name=S.cell("not_ready", None)))[0], run(ConnectionError("x"))[0]]
    outs += [run(S.unmatched_profile(s))[0] for s in ("unrecognized_page", "not_found", "not_listed")]
    outs += [lookup_fund(S.sentinel_loader(), raw) for raw in ("", "US0378331005", "https://x", "​", "AB", "A" * 100)]
    return outs


def test_the_grid_covers_every_reason_code():
    codes = {o.reason_code for o in all_outputs()}
    assert codes >= (BLOCKED_REASONS | SOURCE_FAILED_REASONS | PAGE_UNMATCHED_REASONS)


def test_no_output_ever_says_the_fund_does_not_exist():
    """T-E：掃所有輸出的文字與原因碼，沒有任何「不存在／查無／無效」意味（含中文）。"""
    forbidden = ("exist", "not_found", "no_such", "invalid", "wrong", "nonexist", "absent", "delist", "查無", "不存在", "無此", "錯誤", "無效", "已停售")
    for view in all_outputs():
        text = (everything_visible(view) + " " + str(view.reason_code)).lower()
        assert not [w for w in forbidden if w in text], (view.state, view.reason_code)


def test_every_failure_class_is_a_distinct_state_and_none_of_them_is_a_result():
    states = {name: run(res)[0].state for name, res in {
        "failed": S.failed_profile(), "unrecognized": S.unmatched_profile("unrecognized_page"), "not_found": S.unmatched_profile("not_found"),
        "not_listed": S.unmatched_profile("not_listed"), "name": S.profile(fund_name=S.cell("not_ready", None)), "rejected": S.rejected_profile()}.items()}
    assert states == {"failed": LookupState.SOURCE_FAILED, "unrecognized": LookupState.PAGE_UNMATCHED, "not_found": LookupState.PAGE_UNMATCHED,
                      "not_listed": LookupState.PAGE_UNMATCHED, "name": LookupState.PAGE_UNMATCHED, "rejected": LookupState.BLOCKED}
    assert all(v is not LookupState.RESULT for v in states.values())


def test_each_moneydj_source_status_literal_has_exactly_one_destination():
    """窮舉表：新增來源 status 字面卻沒給去處時紅燈。"""
    destinations = {}
    for status in sorted(adapter._SOURCE_STATUSES):
        if status == "ok":
            view = run(S.profile())[0]
        elif status == "failed":
            view = run(S.failed_profile())[0]
        else:
            view = run(S.unmatched_profile(status))[0]
        destinations[status] = (view.state, view.reason_code)
    assert destinations == {"ok": (LookupState.RESULT, None), "failed": (LookupState.SOURCE_FAILED, "source_failed"),
                            "unrecognized_page": (LookupState.PAGE_UNMATCHED, "unrecognized_page"), "not_found": (LookupState.PAGE_UNMATCHED, "no_page"),
                            "not_listed": (LookupState.PAGE_UNMATCHED, "source_not_listed")}
    assert len(set(destinations.values())) == len(destinations)


def test_page_unmatched_and_source_failed_reason_sets_are_disjoint():
    assert SOURCE_FAILED_REASONS.isdisjoint(PAGE_UNMATCHED_REASONS)


# ═════════════════════════ T-F 靜態守衛 ═════════════════════════

_FORBIDDEN_NAMES = frozenset({
    "open", "environ", "getenv", "putenv", "session_state", "secrets", "st", "os", "sys", "subprocess", "socket", "requests", "httpx", "urlopen",
    "gspread", "write", "writelines", "write_text", "write_bytes", "dump", "dumps", "save", "commit", "exec", "eval", "print", "input",
    "resolve_full_keys", "fund_keys", "build_profiles", "exp_profile", "declared_profile", "fetch_url", "fetch_url_with_retry", "get_proxy_config",
})
_ALLOWED_IMPORTS = {
    ADAPTER_REL: {"__future__", "logging", "re", "typing", "ui_v3.viewmodels.fund_lookup"},
    VIEWMODEL_REL: {"__future__", "datetime", "re", "dataclasses", "enum", "typing"},
}
_FORBIDDEN_WORDS = ("ccy", "fetched_at", "observed_at", "source_tier", "full_key", "table_wide_failed", "declared", "traceback", "raw_response")


def _docstring_ids(tree) -> set:
    return {id(n.body[0].value) for n in ast.walk(tree) if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef)) and n.body
            and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}


def static_problems(rel: str, source: str) -> list:
    """本批新檔的靜態規則：既有 ui_v3 守衛函式庫＋精確 import 白名單＋禁用名稱＋禁用識別字／字串（幣別、時間、來源等級、完整查詢鍵、解析器）。"""
    tree = ast.parse(source)
    out = list(lib.import_violations(rel, source)) + list(lib.write_surface_violations(rel, source)) + lib.module_level_side_effects(source)
    allowed = _ALLOWED_IMPORTS[rel]
    for module in set(lib.imports_of(tree, lib.package_of(rel))):
        if module not in allowed and not any(module.startswith(a + ".") for a in allowed):
            out.append(f"import 不在白名單：{module}")
    docs = _docstring_ids(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            out.append(f"禁用名稱 {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr in _FORBIDDEN_NAMES:
            out.append(f"禁用屬性 .{node.attr}")
        elif isinstance(node, ast.alias) and (node.name in _FORBIDDEN_NAMES or node.name.split(".")[-1] in _FORBIDDEN_NAMES):
            out.append(f"禁用 import 名稱 {node.name}")
        ident = (node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else node.arg if isinstance(node, ast.arg)
                 else node.name if isinstance(node, (ast.FunctionDef, ast.ClassDef)) else None)
        if ident and (any(w in ident.lower() for w in _FORBIDDEN_WORDS) or re.search(r"resolv|alias|mapping", ident.lower())):
            out.append(f"禁用識別字 {ident}")
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            if any(w in node.value.lower() for w in _FORBIDDEN_WORDS):
                out.append(f"禁用字串常數 {node.value!r}")
    return out


@pytest.mark.parametrize("rel", PROD_RELS)
def test_new_production_files_pass_every_static_rule(rel):
    assert static_problems(rel, (lib.ROOT / rel).read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("rel", PROD_RELS)
def test_new_files_are_inside_the_ui_v3_population_and_pass_the_existing_guards(rel):
    assert pathlib.Path(lib.ROOT / rel) in lib.population()
    source = lib.read(lib.ROOT / rel)
    assert lib.import_violations(rel, source) == [] and lib.write_surface_violations(rel, source) == []
    assert lib.module_level_side_effects(source) == []


@pytest.mark.parametrize("snippet", [
    "import os\n", "from os import environ\n", "x = os.environ['K']\n", "x = os.getenv('K')\n", "import sys\nsys.stdout.write('x')\n",
    "import streamlit as st\n", "st.session_state['k'] = 1\n", "def f():\n    open('x', 'w').write('1')\n", "def f(p):\n    p.write_text('1')\n",
    "def f():\n    open('x')\n", "import requests\n", "import urllib.request\n", "import http.client\n", "import socket\n", "import subprocess\n",
    "import gspread\n", "import sqlite3\n", "import json\n", "import importlib\n", "import builtins\n", "def f():\n    return __import__('os')\n",
    "def f():\n    return eval('1')\n", "def f():\n    return getattr(f, 'modules')\n",
    "from services.v2_tables.fund_keys import resolve_full_keys\n", "from services.v2_tables import exp_profile\n",
    "from services.v2_tables.exp_profile import build_profiles\n", "from repositories.fund import declared_profile\n", "from infra.proxy import fetch_url\n",
    "from shared import ttls\n", "from ui_v3.pages import x\n", "from ui_v3.adapters import exp_pool\n",
    "def f(x):\n    return resolve_full_keys(x)\n", "def f(x):\n    return x['ccy']\n", "FETCHED = 'fetched_at'\n", "def f(x):\n    return x.declared\n",
    "def resolve_isin(x):\n    return x\n", "ALIAS_TABLE = {}\n", "def f(x, mapping=None):\n    return x\n",
])
@pytest.mark.parametrize("rel", PROD_RELS)
def test_static_rules_have_teeth_negative_controls_in_memory(rel, snippet):
    source = (lib.ROOT / rel).read_text(encoding="utf-8") + "\n" + snippet
    assert static_problems(rel, source), (rel, snippet)


def test_adapter_has_no_io_calls_in_any_function_body():
    tree = ast.parse((lib.ROOT / ADAPTER_REL).read_text(encoding="utf-8"))
    calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert not calls & {"open", "print", "input", "exec", "eval", "compile", "__import__", "globals", "locals", "vars"}, calls
    attrs = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert attrs <= {"warning", "getLogger", "compile", "fullmatch", "strip", "upper", "join", "items", "get"} | {"startswith"}, attrs


def test_pure_code_pattern_is_matched_with_fullmatch_and_never_match_or_search():
    """M23 的靜態補強：規則 5 必須整段完全符合（`$` 會吃掉尾端換行，`match`／`search` 都不是整段比對）。"""
    source = (lib.ROOT / ADAPTER_REL).read_text(encoding="utf-8")
    assert "_PURE_CODE.fullmatch(" in source and "_PURE_CODE.match(" not in source and "_PURE_CODE.search(" not in source


def test_importing_and_running_the_adapter_in_a_fresh_interpreter_loads_no_heavy_modules_and_makes_no_network_attempt():
    code = (
        "import socket, sys\n"
        "def blocked(*a, **k):\n"
        "    raise SystemExit('NETWORK ATTEMPT')\n"
        "socket.socket.connect = blocked; socket.create_connection = blocked; socket.getaddrinfo = blocked\n"
        "import ui_v3.adapters.fund_lookup as A\n"
        "calls = []\n"
        "def loader(q):\n"
        "    calls.append(q)\n"
        "    raise ConnectionError('x')\n"
        "views = [A.lookup_fund(loader, 'ACTI71'), A.lookup_fund(loader, 'https://x'), A.lookup_fund(loader, 'US0378331005'), A.not_queried()]\n"
        "print(','.join(sorted(n for n in sys.modules if n.split('.')[0] in "
        "{'streamlit','services','repositories','infra','shared','ui','ui_v2','gspread','requests','pandas','numpy','yfinance','urllib3'})))\n"
        "print([v.state.value for v in views], calls)\n")
    proc = subprocess.run([sys.executable, "-s", "-c", code], capture_output=True, text=True, cwd=str(lib.ROOT), env=_subprocess_env(), timeout=120)
    assert proc.returncode == 0, proc.stderr
    lines = proc.stdout.strip().splitlines()
    loaded = [m for m in lines[0].split(",") if m]
    # `ui_v3.viewmodels` 套件本身（既有 `__init__`）會載入 `shared.ui_semantics`；除此之外不得有任何舊樹／重依賴。
    assert all(m == "shared" or m.startswith("shared.ui_semantics") for m in loaded), loaded
    assert lines[1] == "['source_failed', 'blocked', 'blocked', 'not_queried'] ['ACTI71']", lines


_SAFE_ENV_KEYS = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT", "PYTHONIOENCODING", "VIRTUAL_ENV")


def _subprocess_env() -> dict:
    import os
    env = {k: os.environ[k] for k in _SAFE_ENV_KEYS if k in os.environ}
    env.setdefault("PATH", "/usr/bin:/bin")
    env["PYTHONPATH"] = str(lib.ROOT)
    return env


def test_no_skip_paths_exist_in_these_test_files_except_the_ci_aware_helper():
    """後設守衛：本批測試檔內不得有靜默跳過路徑；唯一的 skip 在 `fund_lookup_support.unavailable`（CI 內改為 fail）。"""
    for name in ("test_ui_v3_fund_lookup_viewmodel.py", "test_ui_v3_fund_lookup_adapter.py", "test_ui_v3_fund_lookup_mutations.py"):
        text = (pathlib.Path(__file__).parent / name).read_text(encoding="utf-8")
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in ("skip", "importorskip", "skipif", "xfail"):
                pytest.fail(f"{name}: forbidden skip path .{node.attr}")
            if isinstance(node, ast.Name) and node.id in ("skip", "importorskip", "skipif", "xfail"):
                pytest.fail(f"{name}: forbidden skip path {node.id}")
    support = ast.parse((pathlib.Path(__file__).parent / "fund_lookup_support.py").read_text(encoding="utf-8"))
    skips = [n for n in ast.walk(support) if isinstance(n, ast.Attribute) and n.attr == "skip"]
    assert len(skips) == 1
    fn = next(n for n in support.body if isinstance(n, ast.FunctionDef) and n.name == "unavailable")
    assert skips[0] in list(ast.walk(fn))
    assert "pytest.fail" in ast.unparse(fn) and "ci_is_true" in ast.unparse(fn)


def test_ci_aware_helper_fails_in_ci_and_skips_locally(monkeypatch):
    monkeypatch.setenv("CI", "true")
    with pytest.raises(Failed):
        S.unavailable("dependency missing")
    monkeypatch.setenv("CI", "0")
    with pytest.raises(Skipped):
        S.unavailable("dependency missing")
    for value, expected in (("1", True), ("true", True), ("TRUE", True), ("yes", True), ("", False), ("0", False), ("false", False), ("False", False)):
        monkeypatch.setenv("CI", value)
        assert S.ci_is_true() is expected


def test_network_guard_blocks_every_known_entry_point_and_is_live(no_real_network):
    import http.client
    import socket
    import urllib.request
    with pytest.raises(S.NetworkAttempt):
        socket.create_connection(("127.0.0.1", 9))
    with pytest.raises(S.NetworkAttempt):
        socket.getaddrinfo("example.invalid", 80)
    with pytest.raises(S.NetworkAttempt):
        urllib.request.urlopen("http://example.invalid/")
    with pytest.raises(S.NetworkAttempt):
        http.client.HTTPConnection("example.invalid").connect()
    with pytest.raises(S.NetworkAttempt):
        socket.socket().connect(("127.0.0.1", 9))
    assert len(no_real_network) == 5
    no_real_network.clear()                                                  # 刻意負控；清掉才不會讓結尾斷言誤報


# ═════════════════════════ T-G 與 L2 形狀的離線差分（讀碼，不 import、不呼叫） ═════════════════════════

def _tree(path: pathlib.Path) -> ast.Module:
    if not path.exists():
        S.unavailable(f"L2／L1 原始碼檔不存在，無法做形狀差分：{path.relative_to(lib.ROOT)}")
    return ast.parse(path.read_text(encoding="utf-8"))


def _module_assigns(tree: ast.Module) -> dict:
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            out[node.targets[0].id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            out[node.target.id] = node.value
    return out


def _func(tree: ast.Module, name: str) -> ast.FunctionDef:
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)


def _const(node) -> object:
    return ast.literal_eval(node)


def test_l2_cell_status_literals_equal_the_adapter_literals():
    assigns = _module_assigns(_tree(L2_DIR / "exp_profile.py"))
    l2 = {k: _const(assigns[k]) for k in ("STATUS_OK", "STATUS_NOT_READY", "STATUS_FAILED", "STATUS_INCONSISTENT")}
    assert l2 == {"STATUS_OK": "ok", "STATUS_NOT_READY": "not_ready", "STATUS_FAILED": "fetch_failed", "STATUS_INCONSISTENT": "inconsistent"}
    assert (adapter.L2_CELL_OK, adapter.L2_CELL_NOT_READY, adapter.L2_CELL_FETCH_FAILED, adapter.L2_CELL_INCONSISTENT) == tuple(l2.values())


def test_l1_declared_profile_status_literals_equal_the_adapter_source_literals():
    assigns = _module_assigns(_tree(L1_DECLARED))
    l1 = {k: _const(assigns[k]) for k in ("STATUS_OK", "STATUS_NOT_LISTED", "STATUS_FAILED", "STATUS_UNRECOGNIZED", "STATUS_NOT_FOUND")}
    assert l1 == {"STATUS_OK": "ok", "STATUS_NOT_LISTED": "not_listed", "STATUS_FAILED": "failed", "STATUS_UNRECOGNIZED": "unrecognized_page",
                  "STATUS_NOT_FOUND": "not_found"}
    assert adapter._SOURCE_STATUSES == frozenset(l1.values())
    assert (adapter.L2_SOURCE_OK, adapter.L2_SOURCE_NOT_LISTED, adapter.L2_SOURCE_FAILED, adapter.L2_SOURCE_UNRECOGNIZED,
            adapter.L2_SOURCE_NOT_FOUND) == tuple(l1.values())


def test_l2_moneydj_allowed_statuses_are_exactly_the_adapter_source_statuses():
    tree = _tree(L2_DIR / "exp_profile.py")
    table = _module_assigns(tree)["_L1_STATUSES"]
    entry = next(v for k, v in zip(table.keys, table.values) if isinstance(k, ast.Constant) and k.value == "MoneyDJ")
    names = {e.attr for e in entry.elts}
    assert names == {"STATUS_OK", "STATUS_NOT_LISTED", "STATUS_UNRECOGNIZED", "STATUS_NOT_FOUND", "STATUS_FAILED"}
    declared = {k: _const(v) for k, v in _module_assigns(_tree(L1_DECLARED)).items() if k in names}
    assert frozenset(declared.values()) == adapter._SOURCE_STATUSES


def test_l2_cell_fields_include_the_four_read_fields_and_the_adapter_ignores_the_fifth():
    cell_fields = _const(_module_assigns(_tree(L2_DIR / "exp_profile.py"))["CELL_FIELDS"])
    assert cell_fields == ("fund_name", "ccy", "inception_on", "dividend_policy", "mgmt_fee_rate_pct")
    assert set(adapter.L2_READ_CELL_FIELDS) == set(cell_fields) - {"ccy"} and len(adapter.L2_READ_CELL_FIELDS) == 4


def test_l2_dividend_policy_values_and_inception_floor_equal_the_view_model_constants():
    from ui_v3.viewmodels import fund_lookup as vm
    assigns = _module_assigns(_tree(L2_DIR / "exp_profile.py"))
    assert (_const(assigns["DIVIDEND_POLICY_ACCUM"]), _const(assigns["DIVIDEND_POLICY_DIST"])) == (vm.DIVIDEND_POLICY_ACCUM, vm.DIVIDEND_POLICY_DIST)
    assert _const(assigns["MIN_INCEPTION_YEAR"]) == vm.MIN_INCEPTION_YEAR
    table = assigns["DIVIDEND_FREQ_TO_POLICY"]
    names = {v.id for v in table.values if isinstance(v, ast.Name)}
    assert names == {"DIVIDEND_POLICY_ACCUM", "DIVIDEND_POLICY_DIST"}                 # 對照表的值只有這兩個常數（其餘是 None＝不判定）
    assert all(isinstance(v, ast.Name) or (isinstance(v, ast.Constant) and v.value is None) for v in table.values)


def test_l2_pure_code_pattern_equals_the_adapter_pattern():
    assert _const(_module_assigns(_tree(L2_DIR / "fund_keys.py"))["PURE_CODE_PATTERN"]) == adapter.L2_PURE_CODE_PATTERN


def test_l2_build_profiles_result_keys_cell_keys_and_source_entry_keys_equal_the_fixture_shape():
    tree = _tree(L2_DIR / "exp_profile.py")
    cell_ret = next(n.value for n in ast.walk(_func(tree, "_cell")) if isinstance(n, ast.Return))
    entry_ret = next(n.value for n in ast.walk(_func(tree, "_status_entry")) if isinstance(n, ast.Return))
    out = next(n.value for n in ast.walk(_func(tree, "build_profiles")) if isinstance(n, ast.Assign)
               and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "out" and isinstance(n.value, ast.Dict))
    keys = lambda d: {k.value for k in d.keys if isinstance(k, ast.Constant)}          # noqa: E731
    assert keys(out) == set(S.profile()) == {"rows", "cells", "declared", "source_status", "table_wide_failed"}
    assert keys(cell_ret) == set(S.cell())
    assert keys(entry_ret) == set(S.source_entry())


def test_l2_fee_cell_is_built_with_no_value_and_default_not_ready_status():
    """經理費率恆缺值：L2 `build_profiles` 寫死 `_cell(reason=...)`（無 value、預設 status ＝ not_ready）。"""
    tree = _tree(L2_DIR / "exp_profile.py")
    cells = next(n.value for n in ast.walk(_func(tree, "build_profiles")) if isinstance(n, ast.Assign)
                 and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "cells" and isinstance(n.value, ast.Dict) and len(n.value.keys) == 5)
    fee = next(v for k, v in zip(cells.keys, cells.values) if isinstance(k, ast.Constant) and k.value == "mgmt_fee_rate_pct")
    assert isinstance(fee, ast.Call) and fee.func.id == "_cell" and not fee.args and [k.arg for k in fee.keywords] == ["reason"]
    default = _func(tree, "_cell").args.defaults[1]
    assert isinstance(default, ast.Name) and default.id == "STATUS_NOT_READY"


def test_l2_rejected_keys_get_an_empty_source_status_and_all_cells_not_ready():
    tree = _tree(L2_DIR / "exp_profile.py")
    src = ast.unparse(_func(tree, "build_profiles"))
    assert "out['source_status'][code] = {}" in src
    assert "_cell(reason=reason) for f in CELL_FIELDS" in src


def test_l2_key_results_input_is_the_cells_key():
    """`cells` 的鍵＝傳入 `resolve_full_keys` 結果的 `input`（呼叫端原字串，不是大寫化後的 `full_key`）。"""
    tree = _tree(L2_DIR / "exp_profile.py")
    src = ast.unparse(_func(tree, "build_profiles"))
    assert "code = entry.get('input')" in src and "out['cells'][code]" in src


def test_real_sample_codes_flow_through_the_whole_adapter_with_fake_l2_shapes():
    for code in real_codes():
        loader = S.CountingLoader(lambda q: S.profile(q))
        view = lookup_fund(loader, code.lower())
        assert view.state is LookupState.RESULT and loader.calls == [code.lower()]
