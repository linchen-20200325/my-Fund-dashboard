# -*- coding: utf-8 -*-
"""路徑 B（單檔基本資料查詢）adapter／view model 的突變測試——證明檢查真的咬得住 **production 函式**（`DEC-2026-11-18-02`，待核）。

做法（同 `test_ui_v3_exp_pool_mutations.py`）：讀**目前**的 production 原始碼，套**一個**記憶體內字串替換（舊字串必須恰好出現一次，
否則本檔轉紅：目標消失或變得有歧義），把突變體 exec 進獨立命名空間（不寫檔、不進 `sys.modules`、不改 repo 檔案），然後
- 行為突變：跑下方的檢查集，至少一條必須失敗；
- 靜態突變：對突變後的原始碼跑 `static_problems`，至少一條必須回報。
對照組：未突變的原始碼經同一個載入器必須通過每一條檢查，所以「突變體紅燈」來自突變本身，不是載入方式。
活下來的突變只能列在 `SURVIVORS_DOCUMENTED`（附理由，且有測試證明它真的存活，理由失效時轉紅）。
覆蓋主題：入口攔截次序、loader 呼叫次數、fail-closed、禁止欄位、取數例外型別範圍、回顯長度上限、經理費率、失敗映射。
"""
from __future__ import annotations

import dataclasses
import logging
import pathlib
import sys
import types

import pytest

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import fund_lookup_support as S                          # noqa: E402
import test_ui_v3_fund_lookup_adapter as AT              # noqa: E402
import ui_v3_guard_lib as lib                            # noqa: E402
from fund_lookup_support import no_real_network          # noqa: E402,F401 - autouse fixture

VM_SRC = lib.ROOT / "ui_v3" / "viewmodels" / "fund_lookup.py"
AD_SRC = lib.ROOT / "ui_v3" / "adapters" / "fund_lookup.py"
VM_MODULE, AD_MODULE = "ui_v3.viewmodels.fund_lookup", "ui_v3.adapters.fund_lookup"
CODE = S.SAMPLE_CODE

#: M23：`fullmatch` 改 `match`。規則 2 已攔下所有換行，而 pattern 自帶 `^…$` 錨點，之後 `$` 吃尾端換行的差異不可觀察 → 行為上等價，必然存活；
#: 以「原始碼必須使用 fullmatch」的靜態檢查補強（見 STATIC 的 S11）。
SURVIVORS_DOCUMENTED = {"A99_fullmatch_to_match": "行為等價突變：pattern 自帶 ^…$ 錨點且規則 2 先攔下所有換行；改以靜態檢查 S11 擊殺"}


# ───────────────────────── 載入器 ─────────────────────────

def _load(source: str, module: str):
    package = module.rsplit(".", 1)[0]
    ns = {"__name__": module, "__package__": package}
    exec(compile(source, f"<mutant:{module}>", "exec", dont_inherit=True), ns)   # noqa: S102 - 本 repo 自己的原始碼，一處編輯
    return types.SimpleNamespace(**{k: v for k, v in ns.items() if not k.startswith("__")})


def _mutate(path: pathlib.Path, old: str, new: str, mid: str) -> str:
    source = path.read_text(encoding="utf-8")
    count = source.count(old)
    assert count == 1, f"{mid}: old string occurs {count} times in {path.name} (must be exactly 1)"
    return source.replace(old, new)


def _raises(error_type, fn) -> bool:
    try:
        fn()
    except error_type:
        return True
    return False


# ───────────────────────── 檢查集：view model（M＝被測的 view model 命名空間） ─────────────────────────

def _fields(M, **over):
    base = dict(fund_name=M.FieldView(M.FieldStatus.VALUE, "基金甲"), dividend_policy=M.FieldView(M.FieldStatus.VALUE, "dist"),
                inception_on=M.FieldView(M.FieldStatus.VALUE, "2010-05-03"), mgmt_fee_rate_pct=M.FieldView(M.FieldStatus.MISSING))
    base.update(over)
    return M.ProfileFields(**base)


def _bad(M, fn):
    return _raises(M.LookupContractError, fn)


def vm_unsafe_text_is_never_stored(M):
    states = ((M.LookupState.SOURCE_FAILED, "source_failed"), (M.LookupState.PAGE_UNMATCHED, "no_page"), (M.LookupState.BLOCKED, "code_format"))
    for text in ("US0378331005", "us 0378 3310 05", "US-0378331005", "https://x.example", "http", "www.x", "moneydj", "a=b", "a@b", "a%b", "a#b", "a?b",
                 "a&b", "a:b", "a/b", "a\\b", "é", "\x7f", "A" * 65, "AC\tX", "AC\nX", "​AB", "ＡＢ"):
        for state, reason in states:
            assert _bad(M, lambda state=state, reason=reason, text=text: M.FundLookupView(state, text, reason, None)), (text, state)
    assert M.FundLookupView(M.LookupState.SOURCE_FAILED, "A" * 64, "source_failed", None).input_code == "A" * 64
    assert M.FundLookupView(M.LookupState.BLOCKED, "AB CD", "code_format", None).input_code == "AB CD"


def vm_never_echo_reasons(M):
    for reason in ("isin_shape", "url_shape", "control_or_non_ascii"):
        assert M.FundLookupView(M.LookupState.BLOCKED, None, reason, None).input_code is None
        assert _bad(M, lambda reason=reason: M.FundLookupView(M.LookupState.BLOCKED, "ACTI71", reason, None))


def vm_predicates(M):
    assert M.looks_like_isin("ab0123456789") and M.looks_like_isin("AB 0123 45678 9") and M.looks_like_isin("A.B-0123_456789")
    assert not M.looks_like_isin("AB012345678A") and not M.looks_like_isin("AB01234567890") and not M.looks_like_isin("ACTI71")
    for text in ("a@b", "a%b", "a#b", "a?b", "a&b", "a=b", "a:b", "a/b", "a\\b", "HTTP", "WWW.X", "MoneyDJ"):
        assert M.looks_like_url(text), text
    assert not M.looks_like_url("ACTI71") and not M.looks_like_url("AB-CD 12")
    assert M.is_ascii_printable(" ~") and not M.is_ascii_printable("\x7f") and not M.is_ascii_printable("\x1f") and not M.is_ascii_printable("é")
    assert not M.is_ascii_printable("\x85") and not M.is_ascii_printable("\xa0") and not M.is_ascii_printable("​") and not M.is_ascii_printable("\t")
    assert M.INPUT_ECHO_MAX == 64
    assert M.is_safe_echo("A" * 64) and not M.is_safe_echo("A" * 65) and not M.is_safe_echo(None)


def vm_reason_sets(M):
    assert M.BLOCKED_REASONS == {"blank", "control_or_non_ascii", "url_shape", "isin_shape", "code_format", "key_rejected"}
    assert M.SOURCE_FAILED_REASONS == {"source_failed", "source_cooling", "loader_io_error"}
    assert M.PAGE_UNMATCHED_REASONS == {"unrecognized_page", "no_page", "source_not_listed", "name_unconfirmed"}
    for reasons in (M.BLOCKED_REASONS, M.SOURCE_FAILED_REASONS, M.PAGE_UNMATCHED_REASONS):
        assert not any(w in r for r in reasons for w in ("exist", "invalid", "not_found", "no_such", "wrong"))
    states = {M.LookupState.BLOCKED: M.BLOCKED_REASONS, M.LookupState.SOURCE_FAILED: M.SOURCE_FAILED_REASONS,
              M.LookupState.PAGE_UNMATCHED: M.PAGE_UNMATCHED_REASONS}
    every = M.BLOCKED_REASONS | M.SOURCE_FAILED_REASONS | M.PAGE_UNMATCHED_REASONS
    for state, ok in states.items():
        for reason in every - ok:
            assert _bad(M, lambda state=state, reason=reason: M.FundLookupView(state, "ACTI71", reason, None)), (state, reason)
        assert _bad(M, lambda state=state: M.FundLookupView(state, "ACTI71", None, None))


def vm_state_shapes(M):
    assert _bad(M, lambda: M.FundLookupView(M.LookupState.NOT_QUERIED, None, None, _fields(M)))
    assert _bad(M, lambda: M.FundLookupView(M.LookupState.NOT_QUERIED, "ACTI71"))
    assert _bad(M, lambda: M.FundLookupView(M.LookupState.NOT_QUERIED, None, "blank"))
    assert _bad(M, lambda: M.FundLookupView(M.LookupState.RESULT, "ACTI71", None, None))
    assert _bad(M, lambda: M.FundLookupView(M.LookupState.RESULT, "ACTI71", "source_failed", _fields(M)))
    assert _bad(M, lambda: M.FundLookupView(M.LookupState.SOURCE_FAILED, "ACTI71", "source_failed", _fields(M)))
    assert _bad(M, lambda: M.FundLookupView(M.LookupState.PAGE_UNMATCHED, "ACTI71", "no_page", _fields(M)))
    assert _bad(M, lambda: M.FundLookupView("result", "ACTI71", None, _fields(M)))
    assert M.FundLookupView(M.LookupState.RESULT, "ACTI71", None, _fields(M)).fields is not None


def vm_post_screening_states_keep_the_input(M):
    for state, reason in ((M.LookupState.SOURCE_FAILED, "source_failed"), (M.LookupState.PAGE_UNMATCHED, "no_page")):
        for bad in (None, "", "   "):
            assert _bad(M, lambda state=state, reason=reason, bad=bad: M.FundLookupView(state, bad, reason, None))
    assert _bad(M, lambda: M.FundLookupView(M.LookupState.RESULT, None, None, _fields(M)))
    assert _bad(M, lambda: M.FundLookupView(M.LookupState.BLOCKED, None, "key_rejected", None))
    assert _bad(M, lambda: M.FundLookupView(M.LookupState.BLOCKED, "ACTI71", "blank", None))
    assert M.FundLookupView(M.LookupState.BLOCKED, "   ", "blank", None).input_code == "   "


def vm_field_invariants(M):
    V, MI, C = M.FieldStatus.VALUE, M.FieldStatus.MISSING, M.FieldStatus.CONFLICT
    for bad in (None, "", "  ", 1, ["x"]):
        assert _bad(M, lambda bad=bad: M.FieldView(V, bad))
    for status in (MI, C):
        assert _bad(M, lambda status=status: M.FieldView(status, "x"))
        assert M.FieldView(status).value is None
    assert _bad(M, lambda: M.FieldView("value", "x"))
    assert _bad(M, lambda: _fields(M, fund_name=M.FieldView(MI)))
    assert _bad(M, lambda: _fields(M, fund_name=M.FieldView(C)))
    assert _bad(M, lambda: _fields(M, mgmt_fee_rate_pct=M.FieldView(V, "1.5")))
    assert _bad(M, lambda: _fields(M, mgmt_fee_rate_pct=M.FieldView(C)))
    assert _bad(M, lambda: _fields(M, dividend_policy="dist"))
    for bad in ("monthly", "Dist", "dist ", "0", "不配息", ""):
        assert _bad(M, lambda bad=bad: _fields(M, dividend_policy=M.FieldView(V, bad)))
    for ok in ("accum", "dist"):
        assert _fields(M, dividend_policy=M.FieldView(V, ok)).dividend_policy.value == ok
    for state in (MI, C):
        assert _fields(M, dividend_policy=M.FieldView(state), inception_on=M.FieldView(state)).inception_on.value is None


def vm_inception_dates(M):
    V = M.FieldStatus.VALUE
    for bad in ("2010-5-3", "20100503", "2010/05/03", "2025-02-29", "2010-13-01", "1899-12-31", "0099-01-01", "2010-05-03T00:00", "２０１０-05-03", "x"):
        assert _bad(M, lambda bad=bad: _fields(M, inception_on=M.FieldView(V, bad))), bad
    for ok in ("2010-05-03", "1900-01-01", "2024-02-29"):
        assert _fields(M, inception_on=M.FieldView(V, ok)).inception_on.value == ok


def vm_name_bounds(M):
    V = M.FieldStatus.VALUE
    for bad in ("N" * 201, "基金\x00甲", "基金\n甲", "基金\u200b甲", "https://x.example", "HTTP基金", "see www.x.com"):
        assert _bad(M, lambda bad=bad: _fields(M, fund_name=M.FieldView(V, bad))), bad
    assert _fields(M, fund_name=M.FieldView(V, "N" * 200)).fund_name.value == "N" * 200
    assert _fields(M, fund_name=M.FieldView(V, "A&B 基金（美元）")).fund_name.value == "A&B 基金（美元）"


def vm_no_forbidden_fields(M):
    assert [f.name for f in dataclasses.fields(M.FundLookupView)] == ["state", "input_code", "reason_code", "fields"]
    assert [f.name for f in dataclasses.fields(M.ProfileFields)] == ["fund_name", "dividend_policy", "inception_on", "mgmt_fee_rate_pct"]
    assert [f.name for f in dataclasses.fields(M.FieldView)] == ["status", "value"]


def vm_errors_do_not_echo_and_have_the_agreed_bases(M):
    secret = "secret-value-7f3a"
    for fn in (lambda: M.FieldView(M.FieldStatus.VALUE, [secret]), lambda: M.FundLookupView(secret), lambda: M.FundLookupView(M.LookupState.BLOCKED, secret + "?", "url_shape"),
               lambda: _fields(M, dividend_policy=M.FieldView(M.FieldStatus.VALUE, secret))):
        try:
            fn()
        except M.LookupContractError as exc:
            assert secret not in str(exc) and secret not in repr(exc.args)
        else:
            raise AssertionError("expected a contract error")
    assert issubclass(M.LookupContractError, ValueError) and not issubclass(M.LookupContractError, OSError)
    assert issubclass(M.LookupSourceError, Exception) and not issubclass(M.LookupSourceError, (ValueError, OSError))


VM_CHECKS = [vm_name_bounds, vm_unsafe_text_is_never_stored, vm_never_echo_reasons, vm_predicates, vm_reason_sets, vm_state_shapes, vm_post_screening_states_keep_the_input,
             vm_field_invariants, vm_inception_dates, vm_no_forbidden_fields, vm_errors_do_not_echo_and_have_the_agreed_bases]


# ───────────────────────── 檢查集：adapter（A＝被測的 adapter 命名空間；view model 用真的） ─────────────────────────

CE = AT.LookupContractError
LS = AT.LookupState


def ad_blocked_inputs_never_call_the_loader(A):
    cases = [("", "blank", ""), ("   ", "blank", "   "), ("\t", "control_or_non_ascii", None), (" \n ", "control_or_non_ascii", None),
             ("US0378331005", "isin_shape", None), ("us0378331005", "isin_shape", None), (" US0378331005 ", "isin_shape", None),
             ("US 0378331005", "isin_shape", None), ("US-0378331005", "isin_shape", None), ("US.0378331005", "isin_shape", None),
             ("US_0378331005", "isin_shape", None), ("US,0378331005", "isin_shape", None), ("AB-0123456789", "isin_shape", None),
             ("https://www.moneydj.com/x?a=ACTI71", "url_shape", None), ("http", "url_shape", None), ("HTTP", "url_shape", None), ("www.x", "url_shape", None),
             ("moneydj", "url_shape", None), ("a=ACTI71", "url_shape", None), ("ACT&I71", "url_shape", None), ("AC#TI71", "url_shape", None),
             ("AC%TI71", "url_shape", None), ("AC@TI71", "url_shape", None), ("AC:TI71", "url_shape", None), ("AC/TI71", "url_shape", None),
             ("AC\\TI71", "url_shape", None), ("ACTI71?", "url_shape", None),
             ("ＡＣＴＩ７１", "control_or_non_ascii", None), ("​ACTI71", "control_or_non_ascii", None), ("ACTI71​", "control_or_non_ascii", None),
             ("\x1cACTI71\n", "control_or_non_ascii", None), ("\x0bACTI71", "control_or_non_ascii", None), ("ACTI71\x0c", "control_or_non_ascii", None),
             ("\x7fACTI71", "control_or_non_ascii", None), ("ACTI71\x7f", "control_or_non_ascii", None), ("ACTI71\xa0", "control_or_non_ascii", None),
             ("\x85ACTI71", "control_or_non_ascii", None), ("ACTI71\n", "control_or_non_ascii", None), ("AC\tTI71", "control_or_non_ascii", None),
             ("AB", "code_format", "AB"), ("AC TI71", "code_format", "AC TI71"), ("A" * 31, "code_format", "A" * 31), ("ACTI71-", "code_format", "ACTI71-"),
             ("-ACTI71", "code_format", "-ACTI71"), ("AC.TI71", "code_format", "AC.TI71"), ("ACTI71-A", "code_format", "ACTI71-A"),
             ("A" * 64, "code_format", "A" * 64),
             ("A" * 65, "code_format", None), (CODE + " " * 60, "code_format", None), (" " * 65, "code_format", None), ("​" * 65, "code_format", None),
             ("https://" + "a" * 70, "code_format", None)]
    for raw, reason, echo in cases:
        loader = S.CountingLoader(S.profile())
        view = A.lookup_fund(loader, raw)
        assert (view.state, view.reason_code, view.input_code, view.fields) == (LS.BLOCKED, reason, echo, None), (raw, view)
        assert loader.calls == [], raw


def ad_rule_order(A):
    assert A.screen_input("​" * 65) == "code_format"
    assert A.screen_input("https://ＡＢ") == "control_or_non_ascii"
    assert A.screen_input("http://US0378331005") == "url_shape"
    assert A.screen_input("US 0378331005 ") == "isin_shape"
    assert A.screen_input("   ") == "blank" and A.screen_input("\t") == "control_or_non_ascii"


def ad_screen_releases_valid_shapes(A):
    for raw in (CODE, "acti71", "AB012345678A", "ABCDEFGHIJKL", "0A0378331005", "US037833100", "US0378331005X", "ACDD01-EQTAL005", "ABC", "A" * 30,
                "A" * 30 + "-" + "B" * 20, "  acti71  ", CODE + " " * (64 - len(CODE))):
        assert A.screen_input(raw) is None, raw
    for raw in ("AB-0123456789", "US0378331006"):
        assert A.screen_input(raw) == "isin_shape", raw


def ad_released_input_is_passed_stripped_and_kept_verbatim(A):
    loader = S.CountingLoader(lambda q: S.profile(q))
    view = A.lookup_fund(loader, "  acti71-ab  ")
    assert loader.calls == ["acti71-ab"]
    assert view.state is LS.RESULT and view.input_code == "  acti71-ab  "
    padded = CODE + " " * (64 - len(CODE))
    loader = S.CountingLoader(lambda q: S.profile(q))
    view = A.lookup_fund(loader, padded)
    assert view.state is LS.RESULT and view.input_code == padded and loader.calls == [CODE]


def ad_non_string_input_raises(A):
    for raw in (None, 0, b"ACTI71", ["ACTI71"], object()):
        loader = S.CountingLoader(S.profile())
        assert _raises(CE, lambda raw=raw: A.lookup_fund(loader, raw))
        assert loader.calls == []
        assert _raises(CE, lambda raw=raw: A.screen_input(raw))


def ad_loader_is_injected_and_checked(A):
    import inspect
    assert [p.default for p in inspect.signature(A.lookup_fund).parameters.values()] == [inspect.Parameter.empty] * 2
    for bad in (None, "x", 3):
        assert _raises(CE, lambda bad=bad: A.lookup_fund(bad, CODE))


class _Odd(Exception):
    pass


def ad_exception_scope(A):
    for exc in (A.LookupSourceError("x"), ConnectionError("x"), TimeoutError("x"), ConnectionResetError("x")):
        view = A.lookup_fund(S.CountingLoader(exc), CODE)
        assert (view.state, view.reason_code, view.fields, view.input_code) == (LS.SOURCE_FAILED, "loader_io_error", None, CODE)
    padded = A.lookup_fund(S.CountingLoader(ConnectionError("x")), "  ACTI71  ")
    assert padded.input_code == "  ACTI71  " and padded.reason_code == "loader_io_error"       # 輸入原值連空白都保留
    for exc in (TypeError("t"), ValueError("v"), KeyError("k"), AssertionError("a"), RuntimeError("r"), FileNotFoundError("f"), PermissionError("p"),
                OSError("o"), _Odd("o"), CE("bad")):
        try:
            A.lookup_fund(S.CountingLoader(exc), CODE)
        except type(exc):
            continue
        raise AssertionError(f"{type(exc).__name__} must propagate")
    for exc in (KeyboardInterrupt, SystemExit):
        try:
            A.lookup_fund(S.CountingLoader(exc()), CODE)
        except exc:
            continue
        raise AssertionError("base exceptions must propagate")


def ad_exception_text_never_leaks(A):
    poison = "poison-secret-9e1b"
    lines = []

    class Handler(logging.Handler):
        def emit(self, record):
            lines.append(record.getMessage())

    handler, root = Handler(logging.DEBUG), logging.getLogger()
    previous = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    try:
        view = A.lookup_fund(S.CountingLoader(ConnectionError(poison)), CODE)
    finally:
        root.removeHandler(handler)
        root.setLevel(previous)
    assert poison not in repr(view) and all(poison not in line for line in lines)
    assert any("ConnectionError" in line for line in lines)


def ad_source_state_mapping(A):
    def go(result):
        return A.lookup_fund(S.CountingLoader(result), CODE)

    v = go(S.failed_profile())
    assert (v.state, v.reason_code, v.fields) == (LS.SOURCE_FAILED, "source_failed", None)
    v = go(S.failed_profile(cooling=True))
    assert (v.state, v.reason_code) == (LS.SOURCE_FAILED, "source_cooling")
    for status, reason in (("unrecognized_page", "unrecognized_page"), ("not_found", "no_page"), ("not_listed", "source_not_listed")):
        v = go(S.unmatched_profile(status))
        assert (v.state, v.reason_code, v.fields) == (LS.PAGE_UNMATCHED, reason, None), status
        cooled = S.unmatched_profile(status)
        cooled["source_status"][CODE]["MoneyDJ"]["cooling"] = True                       # 冷卻旗標只對 failed 有意義
        assert go(cooled).reason_code == reason
    v = go(S.rejected_profile())
    assert (v.state, v.reason_code, v.input_code) == (LS.BLOCKED, "key_rejected", CODE)
    for name_status in ("not_ready", "inconsistent"):
        v = go(S.profile(fund_name=S.cell(name_status, None)))
        assert (v.state, v.reason_code, v.fields) == (LS.PAGE_UNMATCHED, "name_unconfirmed", None), name_status
    ok = go(S.profile())
    assert ok.state is LS.RESULT and ok.fields.fund_name.value == S.SAMPLE_NAME and ok.fields.mgmt_fee_rate_pct.status.name == "MISSING"


def ad_field_mapping(A):
    for field, okvalue in (("dividend_policy", "accum"), ("inception_on", "1999-12-31")):
        for status, expected in (("ok", "VALUE"), ("not_ready", "MISSING"), ("inconsistent", "CONFLICT")):
            view = A.lookup_fund(S.CountingLoader(S.profile(**{field: S.cell(status, okvalue if status == "ok" else None)})), CODE)
            got = getattr(view.fields, field)
            assert got.status.name == expected and got.value == (okvalue if status == "ok" else None), (field, status)


def ad_other_sources_and_currency_do_not_matter(A):
    baseline = A.lookup_fund(S.CountingLoader(S.profile()), CODE)
    for result in (S.profile(tdcc="failed", fundclear="failed"), S.profile(ccy=S.cell("inconsistent", None)), S.profile(ccy=S.cell("fetch_failed", None)),
                   S.profile(table_wide_failed=True), S.profile(tdcc="code_unmapped", fundclear="not_listed")):
        assert A.lookup_fund(S.CountingLoader(result), CODE) == baseline
    assert A.lookup_fund(S.CountingLoader(S.failed_profile()), CODE).state is LS.SOURCE_FAILED


def ad_fail_closed(A):
    def go(result):
        return lambda: A.lookup_fund(S.CountingLoader(result), CODE)

    for result in (None, {}, [], "ok", {"cells": {}}, {"source_status": {}}):
        assert _raises(CE, go(result)), result
    for field in A.L2_READ_CELL_FIELDS:
        for status in ("weird", "OK", None, "fetch_failed"):
            assert _raises(CE, go(S.profile(**{field: S.cell(status, None)}))), (field, status)
        assert _raises(CE, go(S.profile(**{field: S.cell("ok", None)}))), field
        assert _raises(CE, go(S.profile(**{field: S.cell("not_ready", "leftover")}))), field
        assert _raises(CE, go(S.profile(**{field: "not a dict"}))), field
    for cell in (S.cell("ok", 1.5), S.cell("ok", "1.5"), S.cell("ok", 0), S.cell("inconsistent", None), S.cell("fetch_failed", None), S.cell("not_ready", 0)):
        assert _raises(CE, go(S.profile(mgmt_fee_rate_pct=cell))), cell
        assert _raises(CE, go(S.profile(fund_name=S.cell("not_ready", None), mgmt_fee_rate_pct=cell))), cell
    for bad in ("monthly", "Dist", "", 1):
        assert _raises(CE, go(S.profile(dividend_policy=S.cell("ok", bad)))), bad
    for bad in ("2010-5-3", "2025-02-29", "1899-12-31", "", 20100503):
        assert _raises(CE, go(S.profile(inception_on=S.cell("ok", bad)))), bad
    for bad in ("", "  ", 5):
        assert _raises(CE, go(S.profile(fund_name=S.cell("ok", bad)))), bad
    assert _raises(CE, go(S.profile(fund_name=S.cell("fetch_failed", None))))             # 來源 ok 之下的 fetch_failed
    assert _raises(CE, go(S.profile(moneydj="mystery")))
    for status in ("OK", "", None, 1, "code_unmapped"):
        result = S.profile()
        result["source_status"][CODE]["MoneyDJ"]["status"] = status
        assert _raises(CE, go(result)), status
    for cooling in (None, 1, "False"):
        result = S.profile(moneydj="failed")
        result["source_status"][CODE]["MoneyDJ"]["cooling"] = cooling
        assert _raises(CE, go(result)), cooling
    for keys_of in ("cells", "source_status"):
        for keys in ((), ("OTHER1",), (CODE, "OTHER1"), (CODE.lower(),)):
            result = S.profile()
            original = result[keys_of][CODE]
            result[keys_of] = {k: original for k in keys}
            assert _raises(CE, go(result)), (keys_of, keys)
    result = S.profile()
    result["source_status"][CODE] = {"TDCC": S.source_entry("ok")}
    assert _raises(CE, go(result))


def ad_contract_errors_are_not_turned_into_failures(A):
    for bad in (None, {}, S.profile(fund_name=S.cell("weird", None)), S.profile(moneydj="mystery")):
        assert _raises(CE, lambda bad=bad: A.lookup_fund(S.CountingLoader(bad), CODE))


def ad_adapt_revalidates_its_inputs(A):
    good = S.profile()
    assert A.adapt_profile_result(CODE, CODE, good).state is LS.RESULT
    for input_code in ("AB", "US0378331005", "https://x", "A" * 65, "", None):
        assert _raises(CE, lambda input_code=input_code: A.adapt_profile_result(input_code, CODE, good))
    # 兩個檢查各自獨立：輸入與取數鍵彼此一致、回傳的 cells 也用同一個鍵，只有「輸入沒通過攔截」或「取數鍵不是輸入去空格」這一個錯
    assert _raises(CE, lambda: A.adapt_profile_result("AB", "AB", S.profile("AB")))
    assert _raises(CE, lambda: A.adapt_profile_result(CODE, "acti71", S.profile("acti71")))
    assert _raises(CE, lambda: A.adapt_profile_result("  " + CODE, CODE + " ", S.profile(CODE + " ")))
    for query_text in ("acti71", " ACTI71", "OTHER1", None):
        assert _raises(CE, lambda query_text=query_text: A.adapt_profile_result(CODE, query_text, good))


def ad_error_messages_do_not_echo(A):
    poison = "poison-value-4c2d"
    for raw in (poison, [poison], {"cells": poison, "source_status": poison}, S.profile(fund_name=S.cell("weird", poison)),
                S.profile(dividend_policy=S.cell("ok", poison)), S.profile(moneydj=poison)):
        try:
            A.lookup_fund(S.CountingLoader(raw), CODE)
        except CE as exc:
            assert poison not in str(exc) and poison not in repr(exc.args)
        else:
            raise AssertionError("expected a contract error")


def ad_free_text_never_reaches_the_view(A):
    poison = "poison-free-text-5b8e"
    cells = {f: S.cell("ok", v, reason=poison, raw={"MoneyDJ": poison}) for f, v in (("fund_name", "基金甲"), ("ccy", "USD"), ("inception_on", "2010-05-03"),
                                                                                       ("dividend_policy", "dist"))}
    cells["mgmt_fee_rate_pct"] = S.cell("not_ready", None, reason=poison)
    result = S.profile(cells=cells)
    result["source_status"][CODE]["MoneyDJ"]["error"] = poison
    result["backend"] = poison
    view = A.lookup_fund(S.CountingLoader(result), CODE)
    assert poison not in repr(view)
    failed = S.failed_profile()
    failed["source_status"][CODE]["MoneyDJ"]["error"] = poison
    assert poison not in repr(A.lookup_fund(S.CountingLoader(failed), CODE))


def ad_not_queried(A):
    view = A.not_queried()
    assert (view.state, view.input_code, view.reason_code, view.fields) == (LS.NOT_QUERIED, None, None, None)


AD_CHECKS = [ad_blocked_inputs_never_call_the_loader, ad_rule_order, ad_screen_releases_valid_shapes, ad_released_input_is_passed_stripped_and_kept_verbatim,
             ad_non_string_input_raises, ad_loader_is_injected_and_checked, ad_exception_scope, ad_exception_text_never_leaks, ad_source_state_mapping,
             ad_field_mapping, ad_other_sources_and_currency_do_not_matter, ad_fail_closed, ad_contract_errors_are_not_turned_into_failures,
             ad_adapt_revalidates_its_inputs, ad_error_messages_do_not_echo, ad_free_text_never_reaches_the_view, ad_not_queried]


#: 崩潰型例外（名稱／屬性／語法／匯入錯誤）不算「被殺」：突變體只是壞掉，不代表有檢查咬到契約。
#: 刻意**不**納入 TypeError：部分突變（例如拿掉非字串輸入檢查，之後 `len(None)` 拋 TypeError）正是以 TypeError 作為預期殺手；
#: 納入會讓這類突變失效。代價是 TypeError 型的崩潰仍會被算成「被殺」，由逐筆人工審視突變清單補位。
CRASH_ERRORS = (NameError, AttributeError, SyntaxError, ImportError, UnboundLocalError)


def _failures(checks, module) -> list:
    failed = []
    for fn in checks:
        try:
            fn(module)
        except CRASH_ERRORS:
            continue
        except BaseException as exc:  # noqa: BLE001 - 契約／斷言失敗代表「突變被發現」；KeyboardInterrupt 不吞
            if isinstance(exc, KeyboardInterrupt):
                raise
            failed.append(fn.__name__)
    return failed


def test_crash_type_errors_do_not_count_as_kills():
    def crashes(_module):
        raise NameError("boom")

    def attribute(_module):
        raise AttributeError("boom")

    def asserts(_module):
        raise AssertionError("real kill")

    assert _failures([crashes, attribute], None) == []
    assert _failures([crashes, asserts, attribute], None) == ["asserts"]
    mutant = _load("def f():\n    return missing_name\n", AD_MODULE)
    assert _failures([lambda m: m.f()], mutant) == []


# ───────────────────────── 突變清單：(id, old〔恰好一次〕, new, 它破壞什麼) ─────────────────────────

VIEWMODEL = [
    ("V01_never_echo_unchecked", '_need(self.input_code is None, "input_code", "None for a safety-blocked input", self.input_code)',
     '_need(True, "input_code", "None for a safety-blocked input", self.input_code)', "被安全攔截的輸入仍可存入 view model"),
    ("V02_safe_echo_allows_isin", "and not looks_like_url(text) and not looks_like_isin(text))", "and not looks_like_url(text))", "ISIN 形可被回顯"),
    ("V03_safe_echo_allows_url", "and not looks_like_url(text) and not looks_like_isin(text))", "and not looks_like_isin(text))", "網址形可被回顯"),
    ("V04_safe_echo_no_length_limit", "isinstance(text, str) and len(text) <= INPUT_ECHO_MAX and is_ascii_printable(text)",
     "isinstance(text, str) and is_ascii_printable(text)", "回顯長度上限被移除"),
    ("V05_safe_echo_allows_non_ascii", "and is_ascii_printable(text)\n", "\n", "非可印刷 ASCII 可被回顯"),
    ("V06_echo_limit_raised", "INPUT_ECHO_MAX = 64\n", "INPUT_ECHO_MAX = 100000\n", "回顯長度上限放寬"),
    ("V07_fee_may_have_value", '_need(self.mgmt_fee_rate_pct.status is FieldStatus.MISSING, "mgmt_fee_rate_pct", "MISSING (no source by contract)", self.mgmt_fee_rate_pct)',
     '_need(True, "mgmt_fee_rate_pct", "MISSING (no source by contract)", self.mgmt_fee_rate_pct)', "經理費率可以有值"),
    ("V08_name_may_be_missing_in_result",
     '        _need(self.fund_name.status is FieldStatus.VALUE, "fund_name", "VALUE (identity-binding evidence)", self.fund_name)\n'
     '        _need(isinstance(self.fund_name.value, str) and _is_safe_name(self.fund_name.value), "fund_name", "short text without control characters or url shape", self.fund_name.value)\n',
     "", "RESULT 內名稱可缺值（兩層檢查都移除；單移除狀態檢查時，名稱安全檢查會擋下 None，屬縱深防禦）"),
    ("V09_dividend_policy_unchecked", '_need(self.dividend_policy.value in _DIVIDEND_POLICIES, "dividend_policy", "accum or dist", self.dividend_policy.value)',
     '_need(True, "dividend_policy", "accum or dist", self.dividend_policy.value)', "配息方式可為 accum／dist 以外的值"),
    ("V10_inception_unchecked", '_need(_is_iso_date(self.inception_on.value), "inception_on", "ISO date YYYY-MM-DD", self.inception_on.value)',
     '_need(True, "inception_on", "ISO date YYYY-MM-DD", self.inception_on.value)', "成立日期不驗 ISO"),
    ("V11_blank_value_allowed", 'isinstance(self.value, str) and self.value.strip() != "", "value"', 'isinstance(self.value, str), "value"', "VALUE 可以是空白字串"),
    ("V12_missing_may_carry_value", '_need(self.value is None, "value", "None when status is not VALUE", self.value)',
     '_need(True, "value", "None when status is not VALUE", self.value)', "缺值／分歧狀態可夾帶值"),
    ("V13_reason_code_unchecked", '_need(isinstance(self.reason_code, str) and self.reason_code in allowed, "reason_code", "a known category code for this state", self.reason_code)',
     '_need(True, "reason_code", "a known category code for this state", self.reason_code)', "原因碼不驗（可塞自由文字）"),
    ("V14_non_result_may_carry_fields", '_need(self.fields is None, "fields", "None when state is not RESULT", self.fields)',
     '_need(True, "fields", "None when state is not RESULT", self.fields)', "非 RESULT 狀態可夾帶欄位值"),
    ("V15_result_may_carry_reason", '_need(self.reason_code is None, "reason_code", "None when state is RESULT", self.reason_code)',
     '_need(True, "reason_code", "None when state is RESULT", self.reason_code)', "RESULT 可夾帶失敗原因碼"),
    ("V16_forbidden_field_added_to_view", "    fields: Optional[ProfileFields] = None\n", "    fields: Optional[ProfileFields] = None\n    fetched_at: Optional[str] = None\n",
     "view model 新增取得時間欄位"),
    ("V17_forbidden_field_added_to_fields", "    mgmt_fee_rate_pct: FieldView\n", "    mgmt_fee_rate_pct: FieldView\n    ccy: Optional[str] = None\n", "欄位集合新增幣別"),
    ("V18_error_echoes_value", 'f"{field}: expected {expected}, got {_kind(value)}"', 'f"{field}: expected {expected}, got {value!r}"', "驗證錯誤回顯收到的值"),
    ("V19_failure_classes_merged", "PAGE_UNMATCHED_REASONS = frozenset({REASON_UNRECOGNIZED_PAGE,", "PAGE_UNMATCHED_REASONS = frozenset({REASON_SOURCE_FAILED, REASON_UNRECOGNIZED_PAGE,",
     "來源失敗與頁面無法確認的原因碼集合相交"),
    ("V20_not_exist_reason", 'REASON_NO_PAGE = "no_page"', 'REASON_NO_PAGE = "does_not_exist"', "原因碼表達「不存在」"),
    ("V21_not_queried_may_carry_fields", '_need(self.fields is None, "fields", "None when state is not-queried", self.fields)',
     '_need(True, "fields", "None when state is not-queried", self.fields)', "尚未查詢可夾帶欄位"),
    ("V22_post_screening_input_optional", '_need(isinstance(self.input_code, str) and self.input_code.strip(" ") != "", "input_code", "non-blank str once the input passed screening",',
     '_need(True, "input_code", "non-blank str once the input passed screening",', "通過攔截後的狀態可以沒有輸入原值"),
    ("V23_blank_may_hold_text", 'isinstance(self.input_code, str) and self.input_code.strip(" ") == ""', "True", "blank 原因可帶非空白文字"),
    ("V24_url_at_sign_missing", ':/\\\\?&=#%@")', ':/\\\\?&=#%")', "網址形漏判 @"),
    ("V25_isin_last_char_alnum", "[A-Z]{2}[A-Z0-9]{9}[0-9]", "[A-Z]{2}[A-Z0-9]{10}", "ISIN 形末碼放寬為英數"),
    ("V26_isin_keeps_separators", 'squeezed = "".join(c for c in text if c in _ALNUM).upper()', "squeezed = text.upper()", "ISIN 形判斷前不移除分隔符"),
    ("V27_url_substring_moneydj_missing", '("http", "www.", "moneydj")', '("http", "www.")', "網址形漏判 moneydj 子字串"),
    ("V28_inception_floor_removed", "MIN_INCEPTION_YEAR = 1900\n", "MIN_INCEPTION_YEAR = 1\n", "成立日期年份下限被移除"),
    ("V29_inception_existence_unchecked", "parsed = _dt.date.fromisoformat(text)", "parsed = _dt.date(2000, 1, 1)", "不存在的日期被放行"),
    ("V30_contract_error_base", "class LookupContractError(ValueError):", "class LookupContractError(Exception):", "契約錯誤型別改了基底"),
    ("V31_printable_range_widened", "0x20 <= ord(c) <= 0x7E", "0x20 <= ord(c) <= 0xFF", "可印刷 ASCII 白名單放寬到 Latin-1"),
    ("V33_name_unbounded", "len(text) <= NAME_MAX and ", "", "基金名稱長度上限被移除"),
    ("V34_name_allows_control", 'not any(unicodedata.category(c).startswith("C") for c in text)', "True", "基金名稱可含控制字元"),
    ("V35_name_allows_url", '"http" not in lowered and "www." not in lowered', "True", "基金名稱可為網址形"),
    ("V32_source_error_base", "class LookupSourceError(Exception):", "class LookupSourceError(ValueError):", "取數例外型別改了基底"),
]

ADAPTER = [
    ("A01_isin_screen_removed", "if looks_like_isin(raw):", "if False:", "移除 ISIN 形攔截"),
    ("A02_url_screen_removed", "if looks_like_url(raw):", "if False:", "移除網址形攔截"),
    ("A03_screening_ignored", "    if reason is not None:\n        return FundLookupView(LookupState.BLOCKED, _echo(raw_input), reason, None)",
     "    if False:\n        return FundLookupView(LookupState.BLOCKED, _echo(raw_input), reason, None)", "攔截命中後仍呼叫 loader"),
    ("A04_screening_after_loader", "    reason = screen_input(raw_input)\n    if reason is not None:", "    _early = loader(str(raw_input))\n    reason = screen_input(raw_input)\n    if reason is not None:",
     "攔截挪到 loader 呼叫之後"),
    ("A05_echo_always", "    return raw if is_safe_echo(raw) else None", "    return raw", "被安全攔截的輸入原值也回顯"),
    ("A06_strip_before_whitelist", "if not is_ascii_printable(raw):", "if not is_ascii_printable(raw.strip()):", "規則 2 先 strip 再檢查白名單"),
    ("A07_length_gate_removed", "if len(raw) > INPUT_ECHO_MAX:", "if False:", "移除原始字串總長度閘門"),
    ("A08_exceptions_widened_to_exception", "except (LookupSourceError, ConnectionError, TimeoutError) as exc:", "except Exception as exc:", "任何例外都轉成來源失敗"),
    ("A09_exceptions_widened_to_oserror", "except (LookupSourceError, ConnectionError, TimeoutError) as exc:", "except (LookupSourceError, OSError) as exc:", "改用廣義 OSError"),
    ("A10_timeout_not_caught", "except (LookupSourceError, ConnectionError, TimeoutError) as exc:", "except (LookupSourceError, ConnectionError) as exc:", "TimeoutError 沒轉成來源失敗"),
    ("A11_source_error_not_caught", "except (LookupSourceError, ConnectionError, TimeoutError) as exc:", "except (ConnectionError, TimeoutError) as exc:", "LookupSourceError 沒轉成來源失敗"),
    ("A12_exception_text_in_log", "type(exc).__name__)", "exc)", "例外字串進 log"),
    ("A13_contract_error_swallowed", "return adapt_profile_result(raw_input, query_text, result)",
     "try:\n        return adapt_profile_result(raw_input, query_text, result)\n    except LookupContractError:\n        return FundLookupView(LookupState.SOURCE_FAILED, raw_input, REASON_SOURCE_FAILED, None)",
     "契約錯誤被吞成來源失敗"),
    ("A14_cooling_ignored", "REASON_SOURCE_COOLING if cooling else REASON_SOURCE_FAILED", "REASON_SOURCE_FAILED", "冷卻中與一般失敗不分"),
    ("A15_cooling_reversed", "REASON_SOURCE_COOLING if cooling else REASON_SOURCE_FAILED", "REASON_SOURCE_FAILED if cooling else REASON_SOURCE_COOLING", "冷卻判斷反向"),
    ("A16_unrecognized_not_unmatched", "if status in _UNMATCHED_BY_SOURCE_STATUS:", "if status in _UNMATCHED_BY_SOURCE_STATUS and status != L2_SOURCE_UNRECOGNIZED:",
     "頁面無法確認落入名稱判斷"),
    ("A17_no_page_reported_as_source_failure", "L2_SOURCE_NOT_FOUND: REASON_NO_PAGE,", "L2_SOURCE_NOT_FOUND: REASON_SOURCE_FAILED,", "無對應頁面被當成來源失敗"),
    ("A18_key_rejected_removed", "    if not entry:", "    if False:", "刪除 key_rejected 分支"),
    ("A19_fee_check_removed", '_need(cell_pairs["mgmt_fee_rate_pct"][0] == L2_CELL_NOT_READY,', "_need(True,", "接受費率格的非缺值"),
    ("A20_fetch_failed_allowed", "_need(cell_status != L2_CELL_FETCH_FAILED,", "_need(True,", "來源 ok 之下的 fetch_failed 被放行"),
    ("A21_unknown_cell_status_allowed", '_need(isinstance(status, str) and status in _CELL_STATUSES,', "_need(True,", "未知 cell status 被降級放行"),
    ("A22_unknown_source_status_allowed", '_need(isinstance(status, str) and status in _SOURCE_STATUSES,', "_need(True,", "未知來源 status 被放行"),
    ("A23_cooling_type_unchecked", "_need(isinstance(cooling, bool),", "_need(True,", "cooling 型別不驗"),
    ("A24_not_ok_value_unchecked", '_need(value is None, f"cells.{field}.value", "None when status is not ok", value)',
     '_need(True, f"cells.{field}.value", "None when status is not ok", value)', "非 ok 的格帶值被悄悄丟掉"),
    ("A25_query_text_unchecked", '_need(isinstance(query_text, str) and query_text == input_code.strip(" "),', "_need(True,", "取數鍵與輸入不一致不驗"),
    ("A26_input_not_rescreened", "_need(screen_input(input_code) is None,", "_need(True,", "adapt_profile_result 不重驗輸入"),
    ("A27_cells_keys_unchecked", "isinstance(cells, dict) and set(cells) == {query_text}", "isinstance(cells, dict)", "cells 多出別的代碼也放行"),
    ("A28_source_status_keys_unchecked", "isinstance(statuses, dict) and set(statuses) == {query_text}", "isinstance(statuses, dict)", "source_status 多出別的代碼也放行"),
    ("A29_loader_callable_unchecked", '_need(callable(loader),', "_need(True,", "loader 不是 callable 不報契約錯誤"),
    ("A30_loader_has_default", "def lookup_fund(loader: Callable[[str], object], raw_input: object)", "def lookup_fund(loader: Callable[[str], object] = None, raw_input: object = '')",
     "loader 有預設值（不再必須由呼叫端注入）"),
    ("A31_non_string_input_unchecked", '_need(isinstance(raw, str), "raw_input", "str", raw)', '_need(True, "raw_input", "str", raw)', "非字串輸入不報契約錯誤"),
    ("A32_name_unconfirmed_ignored", 'if cell_pairs["fund_name"][0] != L2_CELL_OK:', "if False:", "名稱未確認仍回 RESULT"),
    ("A33_table_wide_failed_read", "    if status == L2_SOURCE_FAILED:", "    _need(not raw_result.get('table_wide_failed'), 'x', 'y', 0)\n    if status == L2_SOURCE_FAILED:",
     "讀取 table_wide_failed 影響狀態"),
    ("A34_query_text_uppercased", 'query_text = raw_input.strip(" ")', 'query_text = raw_input.strip(" ").upper()', "傳給 loader 的字串被轉大寫"),
    ("A35_echo_normalised", "FundLookupView(LookupState.SOURCE_FAILED, raw_input, REASON_LOADER_IO_ERROR, None)",
     "FundLookupView(LookupState.SOURCE_FAILED, raw_input.strip(), REASON_LOADER_IO_ERROR, None)", "輸入原值被 strip 後存入"),
    ("A36_inconsistent_as_value", "        return FieldView(FieldStatus.CONFLICT, None)", '        return FieldView(FieldStatus.VALUE, "x")', "inconsistent 映為 VALUE"),
    ("A37_not_found_literal_changed", 'L2_SOURCE_NOT_FOUND = "not_found"', 'L2_SOURCE_NOT_FOUND = "not_found_x"', "L2 字面與 adapter 不一致"),
    ("A38_blank_treats_any_whitespace", 'if raw.strip(" ") == "":', 'if raw.strip() == "":', "tab／換行被當成 blank"),
    ("A39_pattern_without_strip", '_PURE_CODE.fullmatch(raw.strip(" ").upper())', "_PURE_CODE.fullmatch(raw.upper())", "規則 5 不去前後空格"),
    ("A40_pattern_case_sensitive", '_PURE_CODE.fullmatch(raw.strip(" ").upper())', '_PURE_CODE.fullmatch(raw.strip(" "))', "規則 5 不轉大寫"),
    ("A41_mdj_cell_required_only", 'L2_READ_CELL_FIELDS = ("fund_name", "dividend_policy", "inception_on", "mgmt_fee_rate_pct")',
     'L2_READ_CELL_FIELDS = ("fund_name", "dividend_policy", "inception_on")', "經理費率格不再被讀取與驗證"),
    ("A42_fail_open_on_missing_primary_source", '_need(_SOURCE_KEY in entry, "source_status[code]", "an entry for the primary source", entry)',
     '_need(True, "source_status[code]", "an entry for the primary source", entry)', "缺主要來源條目不報契約錯誤"),
]

# 靜態突變：(id, 檔, old〔恰好一次〕, new, 說明)
STATIC = [
    ("S01_adapter_imports_os", AD_SRC, "import logging\n", "import logging\nimport os\n", "adapter 讀環境變數"),
    ("S02_adapter_imports_real_l2", AD_SRC, "import logging\n", "import logging\nfrom services.v2_tables import exp_profile\n", "adapter import 真實 L2"),
    ("S03_adapter_imports_key_resolver", AD_SRC, "import logging\n", "import logging\nfrom services.v2_tables.fund_keys import resolve_full_keys\n",
     "adapter 解析身份（冒用 R-ID-1）"),
    ("S04_adapter_imports_requests", AD_SRC, "import logging\n", "import logging\nimport requests\n", "adapter 發網路請求"),
    ("S05_viewmodel_imports_streamlit", VM_SRC, "import datetime as _dt\n", "import datetime as _dt\nimport streamlit as st\n", "view model 碰 session_state"),
    ("S06_viewmodel_writes_file", VM_SRC, "def _kind(value: object) -> str:\n    return type(value).__name__\n",
     "def _kind(value: object) -> str:\n    open('x.txt', 'w').write('1')\n    return type(value).__name__\n", "view model 寫檔"),
    ("S07_adapter_reads_environment", AD_SRC, "def not_queried() -> FundLookupView:\n", "def not_queried() -> FundLookupView:\n    import os\n    os.environ.get('K')\n",
     "adapter 在函式內讀環境變數"),
    ("S08_adapter_imports_sqlite", AD_SRC, "import logging\n", "import logging\nimport sqlite3\n", "adapter 寫持久層"),
    ("S09_adapter_mentions_currency_cell", AD_SRC, '_SOURCE_KEY = "MoneyDJ"\n', '_SOURCE_KEY = "MoneyDJ"\n_CCY_FIELD = "ccy"\n', "adapter 讀取幣別格"),
    ("S10_viewmodel_gains_time_identifier", VM_SRC, "INPUT_ECHO_MAX = 64\n", "INPUT_ECHO_MAX = 64\nfetched_at = None\n", "view model 出現取得時間識別字"),
    ("S11_fullmatch_replaced_by_match", AD_SRC, "_PURE_CODE.fullmatch(raw.strip", "_PURE_CODE.match(raw.strip", "規則 5 不再整段比對（行為等價，靠靜態檢查擊殺）"),
    ("S12_adapter_imports_alias_table", AD_SRC, "import logging\n", "import logging\nfrom services.v2_tables.fund_keys import load_alias_mapping\n", "adapter 使用別名表"),
    ("S13_adapter_uses_proxy_fetch", AD_SRC, "import logging\n", "import logging\nfrom infra.proxy import fetch_url\n", "adapter 直接取數"),
    ("S14_adapter_imports_json", AD_SRC, "import logging\n", "import logging\nimport json\n", "adapter 引入白名單以外的標準函式庫"),
]


def static_problems(rel: str, source: str) -> list:
    problems = AT.static_problems(rel, source)
    if rel == AT.ADAPTER_REL and "_PURE_CODE.fullmatch(" not in source:
        problems.append("規則 5 必須使用 fullmatch（整段比對）")
    return problems


def test_control_unmutated_sources_pass_every_check_and_static_rule():
    vm = _load(VM_SRC.read_text(encoding="utf-8"), VM_MODULE)
    ad = _load(AD_SRC.read_text(encoding="utf-8"), AD_MODULE)
    assert _failures(VM_CHECKS, vm) == [] and _failures(AD_CHECKS, ad) == []
    assert static_problems(AT.VIEWMODEL_REL, VM_SRC.read_text(encoding="utf-8")) == []
    assert static_problems(AT.ADAPTER_REL, AD_SRC.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("mutation", VIEWMODEL, ids=lambda m: m[0])
def test_viewmodel_mutation_is_killed(mutation):
    mid, old, new, doc = mutation
    killers = _failures(VM_CHECKS, _load(_mutate(VM_SRC, old, new, mid), VM_MODULE))
    assert killers, f"{mid} ({doc}): no check noticed the mutation"


@pytest.mark.parametrize("mutation", ADAPTER, ids=lambda m: m[0])
def test_adapter_mutation_is_killed(mutation):
    mid, old, new, doc = mutation
    killers = _failures(AD_CHECKS, _load(_mutate(AD_SRC, old, new, mid), AD_MODULE))
    assert killers, f"{mid} ({doc}): no check noticed the mutation"


@pytest.mark.parametrize("mutation", STATIC, ids=lambda m: m[0])
def test_static_mutation_is_killed(mutation):
    mid, path, old, new, doc = mutation
    rel = AT.VIEWMODEL_REL if path == VM_SRC else AT.ADAPTER_REL
    assert static_problems(rel, _mutate(path, old, new, mid)), f"{mid} ({doc}): no static rule noticed the mutation"


def test_the_documented_survivor_really_survives_behaviourally_and_is_killed_statically():
    """M23 的紀錄不得過期：它必須仍是行為等價（所有檢查都通過），且被靜態檢查擊殺。"""
    source = _mutate(AD_SRC, "_PURE_CODE.fullmatch(raw.strip", "_PURE_CODE.match(raw.strip", "A99_fullmatch_to_match")
    assert _failures(AD_CHECKS, _load(source, AD_MODULE)) == []
    assert static_problems(AT.ADAPTER_REL, source)
    assert set(SURVIVORS_DOCUMENTED) == {"A99_fullmatch_to_match"}


def test_mutation_lists_are_not_trivial_and_ids_are_unique():
    ids = [m[0] for m in VIEWMODEL + ADAPTER] + [m[0] for m in STATIC]
    assert len(ids) == len(set(ids))
    assert len(VIEWMODEL) >= 30 and len(ADAPTER) >= 40 and len(STATIC) >= 12


def test_mutation_themes_are_covered():
    """（限制：只是對 `doc` 文字做關鍵字檢查的形式性測試，證明清單有涵蓋各主題，**不**證明每個主題的突變真的被對應檢查擊殺；擊殺由逐筆測試負責。）
    主要風險主題各至少一個突變：攔截次序、loader 呼叫次數、fail-closed、禁止欄位、例外型別範圍、回顯長度上限、經理費率、失敗映射。"""
    text = " ".join(m[3] for m in VIEWMODEL + ADAPTER + [(a, b, c, d) for a, _p, b, c, d in STATIC])
    for theme in ("攔截挪到", "仍呼叫 loader", "不報契約錯誤", "新增取得時間欄位", "新增幣別", "改用廣義 OSError", "回顯長度上限", "經理費率", "來源失敗"):
        assert theme in text, theme


def test_mutants_do_not_replace_or_pollute_sys_modules():
    real_vm, real_ad = sys.modules[VM_MODULE], sys.modules[AD_MODULE]
    before = set(sys.modules)
    _load(_mutate(VM_SRC, *VIEWMODEL[0][1:3], VIEWMODEL[0][0]), VM_MODULE)
    _load(_mutate(AD_SRC, *ADAPTER[0][1:3], ADAPTER[0][0]), AD_MODULE)
    assert sys.modules[VM_MODULE] is real_vm and sys.modules[AD_MODULE] is real_ad and set(sys.modules) == before


def test_mutation_targets_are_production_files_not_tests():
    assert VM_SRC.parts[-3:] == ("ui_v3", "viewmodels", "fund_lookup.py") and AD_SRC.parts[-3:] == ("ui_v3", "adapters", "fund_lookup.py")
