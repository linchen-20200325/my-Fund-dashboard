# -*- coding: utf-8 -*-
"""路徑 B（單檔基本資料查詢）view model 測試（`DEC-2026-11-18-02`，待核；僅內部切片）：狀態、不變式、輸入回顯、禁止欄位、原因碼語意。

本機執行：
    pytest tests/ui_v3/test_ui_v3_fund_lookup_viewmodel.py -q --noconftest -p no:cacheprovider

全部是純資料測試；沒有取數、沒有 secrets、沒有網路（autouse 守衛會把所有網路入口換成會 raise 的版本）。
"""
from __future__ import annotations

import ast
import dataclasses
import datetime
import pathlib
import re

import pytest

import fund_lookup_support as S
import ui_v3_guard_lib as lib
from fund_lookup_support import no_real_network  # noqa: F401 - autouse fixture
from ui_v3.viewmodels import fund_lookup as vm
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
    ProfileFields,
)

VIEWMODEL_REL = "ui_v3/viewmodels/fund_lookup.py"
V = FieldView(FieldStatus.VALUE, "x")
M = FieldView(FieldStatus.MISSING)


def good_fields(**over) -> ProfileFields:
    base = dict(fund_name=FieldView(FieldStatus.VALUE, "基金甲"), dividend_policy=FieldView(FieldStatus.VALUE, "dist"),
                inception_on=FieldView(FieldStatus.VALUE, "2010-05-03"), mgmt_fee_rate_pct=M)
    base.update(over)
    return ProfileFields(**base)


def result_view(**over) -> FundLookupView:
    kw = dict(state=LookupState.RESULT, input_code="ACTI71", reason_code=None, fields=good_fields())
    kw.update(over)
    return FundLookupView(**kw)


# ───────────────────────── 狀態與不變式 ─────────────────────────

def test_five_states_are_distinct_and_the_set_is_closed():
    assert [s.name for s in LookupState] == ["NOT_QUERIED", "BLOCKED", "SOURCE_FAILED", "PAGE_UNMATCHED", "RESULT"]
    assert [s.name for s in FieldStatus] == ["VALUE", "MISSING", "CONFLICT"]


def test_not_queried_carries_nothing():
    view = FundLookupView(LookupState.NOT_QUERIED)
    assert (view.input_code, view.reason_code, view.fields) == (None, None, None)
    for over in (dict(input_code="ACTI71"), dict(reason_code="blank"), dict(fields=good_fields())):
        with pytest.raises(LookupContractError):
            FundLookupView(LookupState.NOT_QUERIED, **over)


@pytest.mark.parametrize("state,reasons", [(LookupState.BLOCKED, BLOCKED_REASONS), (LookupState.SOURCE_FAILED, SOURCE_FAILED_REASONS),
                                           (LookupState.PAGE_UNMATCHED, PAGE_UNMATCHED_REASONS)])
def test_every_non_result_state_needs_a_reason_from_its_own_fixed_set_and_never_carries_fields(state, reasons):
    def echo_for(reason):
        return None if reason in vm._NEVER_ECHO_REASONS else "  " if reason == "blank" else "ACTI71"

    for reason in sorted(reasons):
        view = FundLookupView(state, echo_for(reason), reason, None)
        assert view.fields is None and view.reason_code == reason
        with pytest.raises(LookupContractError):
            FundLookupView(state, echo_for(reason), reason, good_fields())
    for other in (None, "", "not_a_reason", "SOURCE_FAILED", *sorted({*BLOCKED_REASONS, *SOURCE_FAILED_REASONS, *PAGE_UNMATCHED_REASONS} - reasons)):
        with pytest.raises(LookupContractError):
            FundLookupView(state, "ACTI71", other, None)


def test_reason_codes_belong_to_exactly_one_state_and_the_sets_are_disjoint():
    sets = [BLOCKED_REASONS, SOURCE_FAILED_REASONS, PAGE_UNMATCHED_REASONS]
    assert sum(len(s) for s in sets) == len(BLOCKED_REASONS | SOURCE_FAILED_REASONS | PAGE_UNMATCHED_REASONS)
    assert BLOCKED_REASONS == {"blank", "control_or_non_ascii", "url_shape", "isin_shape", "code_format", "key_rejected"}
    assert SOURCE_FAILED_REASONS == {"source_failed", "source_cooling", "loader_io_error"}
    assert PAGE_UNMATCHED_REASONS == {"unrecognized_page", "no_page", "source_not_listed", "name_unconfirmed"}


def test_no_reason_code_or_name_says_the_fund_does_not_exist():
    """T-E1：原因碼集合封閉，且沒有任何一個表達「不存在／查無／無效／代碼錯誤」。"""
    forbidden = ("exist", "not_found", "notfound", "no_such", "invalid", "unknown_fund", "wrong", "missing_fund", "nonexist", "absent", "delist", "closed")
    for reason in BLOCKED_REASONS | SOURCE_FAILED_REASONS | PAGE_UNMATCHED_REASONS:
        assert not any(f in reason for f in forbidden), reason
    constants = {n: getattr(vm, n) for n in dir(vm) if n.startswith("REASON_")}
    assert set(constants.values()) == BLOCKED_REASONS | SOURCE_FAILED_REASONS | PAGE_UNMATCHED_REASONS
    for name in constants:
        assert not any(f in name.lower() for f in forbidden), name


def test_source_failed_and_page_unmatched_are_never_confusable():
    assert SOURCE_FAILED_REASONS.isdisjoint(PAGE_UNMATCHED_REASONS) and SOURCE_FAILED_REASONS.isdisjoint(BLOCKED_REASONS)
    a = FundLookupView(LookupState.SOURCE_FAILED, "ACTI71", "source_failed", None)
    b = FundLookupView(LookupState.PAGE_UNMATCHED, "ACTI71", "no_page", None)
    assert a != b and a.state is not b.state


def test_result_requires_fields_and_no_reason():
    assert result_view().fields is not None
    with pytest.raises(LookupContractError):
        result_view(fields=None)
    with pytest.raises(LookupContractError):
        result_view(reason_code="source_failed")
    with pytest.raises(LookupContractError):
        result_view(fields=object())


def test_view_is_frozen_and_hashable_value_objects():
    view = result_view()
    with pytest.raises(dataclasses.FrozenInstanceError):
        view.state = LookupState.BLOCKED                              # type: ignore[misc]
    assert hash(view) == hash(result_view())


# ───────────────────────── 欄位級不變式 ─────────────────────────

def test_field_view_value_iff_status_value():
    assert FieldView(FieldStatus.VALUE, "x").value == "x"
    for status in (FieldStatus.MISSING, FieldStatus.CONFLICT):
        assert FieldView(status).value is None
        with pytest.raises(LookupContractError):
            FieldView(status, "x")
    for bad in (None, "", "   ", 1, b"x", ["x"]):
        with pytest.raises(LookupContractError):
            FieldView(FieldStatus.VALUE, bad)                         # type: ignore[arg-type]
    with pytest.raises(LookupContractError):
        FieldView("value")                                            # type: ignore[arg-type]


def test_profile_fields_pin_identity_evidence_and_the_fee_gap():
    assert good_fields().mgmt_fee_rate_pct.status is FieldStatus.MISSING
    for status in (FieldStatus.MISSING, FieldStatus.CONFLICT):
        with pytest.raises(LookupContractError):
            good_fields(fund_name=FieldView(status))                  # 名稱是身分綁定證據：RESULT 內必為 VALUE
    for fee in (V, FieldView(FieldStatus.VALUE, "1.5"), FieldView(FieldStatus.CONFLICT)):
        with pytest.raises(LookupContractError):
            good_fields(mgmt_fee_rate_pct=fee)                        # 費率意外出現數值／分歧 → fail-closed
    for name in ("fund_name", "dividend_policy", "inception_on", "mgmt_fee_rate_pct"):
        with pytest.raises(LookupContractError):
            good_fields(**{name: "not a FieldView"})


@pytest.mark.parametrize("policy", ["accum", "dist"])
def test_dividend_policy_values_are_exactly_accum_or_dist(policy):
    assert good_fields(dividend_policy=FieldView(FieldStatus.VALUE, policy)).dividend_policy.value == policy


@pytest.mark.parametrize("bad", ["Accum", "DIST", "none", "不配息", "0", "monthly", "dist ", " accum", "N/A"])
def test_any_other_dividend_policy_value_fails_closed(bad):
    with pytest.raises(LookupContractError):
        good_fields(dividend_policy=FieldView(FieldStatus.VALUE, bad))


@pytest.mark.parametrize("state", [FieldStatus.MISSING, FieldStatus.CONFLICT])
def test_missing_and_conflict_are_allowed_for_policy_and_inception_without_values(state):
    fields = good_fields(dividend_policy=FieldView(state), inception_on=FieldView(state))
    assert fields.dividend_policy.value is None and fields.inception_on.value is None


@pytest.mark.parametrize("ok", ["2010-05-03", "1900-01-01", "2026-02-28", "2024-02-29"])
def test_inception_accepts_real_iso_dates(ok):
    assert good_fields(inception_on=FieldView(FieldStatus.VALUE, ok)).inception_on.value == ok


@pytest.mark.parametrize("bad", ["2010-5-3", "20100503", "2010/05/03", "2025-02-29", "2010-13-01", "2010-00-10", "1899-12-31", "0099-01-01",
                                 "2010-05-03T00:00", "2010-W20-1", "２０１０-05-03", "2010-05-03\n", "May 3 2010", "0", "None"])
def test_inception_rejects_non_iso_nonexistent_or_too_early_dates(bad):
    with pytest.raises(LookupContractError):
        good_fields(inception_on=FieldView(FieldStatus.VALUE, bad))


@pytest.mark.parametrize("bad", ["N" * (vm.NAME_MAX + 1), "基金\x00甲", "基金\n甲", "基金\u200b甲", "基金\x7f甲", "https://x.example", "HTTP基金", "see www.x.com"])
def test_fund_name_is_bounded_and_not_url_shaped_or_control(bad):
    with pytest.raises(LookupContractError):
        good_fields(fund_name=FieldView(FieldStatus.VALUE, bad))


def test_fund_name_at_the_limit_and_ordinary_punctuation_are_accepted():
    for ok in ("N" * vm.NAME_MAX, "富達-全球 A&B 基金（美元）", "Fund (USD) Acc"):
        assert good_fields(fund_name=FieldView(FieldStatus.VALUE, ok)).fund_name.value == ok


# ───────────────────────── 輸入回顯：結構上不保留被攔截的內容 ─────────────────────────

SAFE_BLOCKED = [("blank", ""), ("blank", "   "), ("code_format", "AB"), ("code_format", "AB CD"), ("key_rejected", "ACTI71")]


@pytest.mark.parametrize("reason,echo", SAFE_BLOCKED)
def test_safe_blocked_inputs_may_be_kept(reason, echo):
    assert FundLookupView(LookupState.BLOCKED, echo, reason, None).input_code == echo


@pytest.mark.parametrize("reason", sorted(vm._NEVER_ECHO_REASONS))
def test_isin_url_and_non_ascii_reasons_can_never_carry_the_input(reason):
    assert FundLookupView(LookupState.BLOCKED, None, reason, None).input_code is None
    for echo in ("ACTI71", "", "x"):
        with pytest.raises(LookupContractError):
            FundLookupView(LookupState.BLOCKED, echo, reason, None)


@pytest.mark.parametrize("bad", [
    "US" + "0378331" + "005",                      # ISIN 形（緊密）
    "us 0378331005", "US-0378331005", "US.0378331005", "US_0378331005", "US,0378331005", " US0378331005 ",
    "https://example.test/a", "http", "www.x", "moneydj", "a=ACTI71", "a?b", "a/b", "a\\b", "a#b", "a%b", "a@b", "a:b", "a&b",
    "ＡＣＴＩ７１", "AC​TI71", "AC\x7fTI71", "AC\x85TI71", "AC\xa0TI71", "AC\tTI71", "AC\nTI71", "\x1cACTI71", "ACTI71\n", "é",
    "A" * (INPUT_ECHO_MAX + 1),
])
@pytest.mark.parametrize("state_reason", [(LookupState.BLOCKED, "code_format"), (LookupState.SOURCE_FAILED, "source_failed"),
                                          (LookupState.PAGE_UNMATCHED, "no_page")])
def test_unsafe_text_cannot_be_stored_in_any_state(bad, state_reason):
    state, reason = state_reason
    with pytest.raises(LookupContractError):
        FundLookupView(state, bad, reason, None)
    with pytest.raises(LookupContractError):
        result_view(input_code=bad)


def test_input_echo_length_limit_is_exact():
    assert INPUT_ECHO_MAX == 64
    assert result_view(input_code="A" * INPUT_ECHO_MAX).input_code == "A" * INPUT_ECHO_MAX
    with pytest.raises(LookupContractError):
        result_view(input_code="A" * (INPUT_ECHO_MAX + 1))


def test_states_after_screening_must_keep_a_non_blank_input_and_not_queried_must_not():
    for state, reason in ((LookupState.SOURCE_FAILED, "source_failed"), (LookupState.PAGE_UNMATCHED, "no_page")):
        for bad in (None, "", "  "):
            with pytest.raises(LookupContractError):
                FundLookupView(state, bad, reason, None)
    with pytest.raises(LookupContractError):
        result_view(input_code=None)
    with pytest.raises(LookupContractError):
        FundLookupView(LookupState.BLOCKED, None, "key_rejected", None)
    with pytest.raises(LookupContractError):
        FundLookupView(LookupState.BLOCKED, "ACTI71", "blank", None)  # blank 只能是全空格


def test_input_code_is_kept_verbatim_not_normalised():
    assert result_view(input_code="acti71").input_code == "acti71"
    assert result_view(input_code=" ACTI71 ").input_code == " ACTI71 "


def test_shape_predicates_agree_with_the_stated_rules():
    assert vm.is_ascii_printable(" ~") and not vm.is_ascii_printable("\x7f") and not vm.is_ascii_printable("\x1f") and not vm.is_ascii_printable("ａ")
    assert vm.looks_like_url("HTTP") and vm.looks_like_url("WWW.x") and vm.looks_like_url("Moneydj") and not vm.looks_like_url("ACTI71")
    assert vm.looks_like_isin("ab0123456789") and vm.looks_like_isin("AB 0123 45678 9") and not vm.looks_like_isin("AB012345678A")   # 末碼必為數字
    assert not vm.looks_like_isin("ACTI71") and not vm.looks_like_isin("AB01234567890") and not vm.looks_like_isin("")
    assert vm.is_safe_echo("ACTI71") and vm.is_safe_echo("") and not vm.is_safe_echo(None) and not vm.is_safe_echo(7)


# ───────────────────────── 不洩漏：欄位集合、錯誤訊息 ─────────────────────────

FORBIDDEN_FIELD_WORDS = ("ccy", "currency", "nav", "return", "perf", "fetched", "observed", "provider", "source", "tier", "raw", "response",
                         "url", "error", "exception", "message", "full_key", "secret", "token", "key", "reason_text", "traceback")


def test_dataclass_fields_are_exactly_the_five_internal_test_fields_and_nothing_else():
    """T-D1：欄位集合鎖死（無幣別、淨值、報酬、績效、時間、來源、原始回應、網址、例外訊息、完整查詢鍵、密鑰）。"""
    assert [f.name for f in dataclasses.fields(FundLookupView)] == ["state", "input_code", "reason_code", "fields"]
    assert [f.name for f in dataclasses.fields(ProfileFields)] == ["fund_name", "dividend_policy", "inception_on", "mgmt_fee_rate_pct"]
    assert [f.name for f in dataclasses.fields(FieldView)] == ["status", "value"]
    names = [f.name for c in (FundLookupView, ProfileFields, FieldView) for f in dataclasses.fields(c)]
    for word in FORBIDDEN_FIELD_WORDS:
        assert not [n for n in names if word in n.lower()], (word, names)


def test_viewmodel_source_has_no_forbidden_identifier_or_string_constant():
    """AST：識別子（名稱、屬性、引數、類別／函式名、關鍵字引數）與非 docstring 字串常數都不含禁止詞。"""
    tree = ast.parse((lib.ROOT / VIEWMODEL_REL).read_text(encoding="utf-8"))
    docstrings = {id(n.body[0].value) for n in ast.walk(tree) if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef)) and n.body
                  and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    idents = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            idents.add(node.id)
        elif isinstance(node, ast.Attribute):
            idents.add(node.attr)
        elif isinstance(node, ast.arg):
            idents.add(node.arg)
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            idents.add(node.name)
        elif isinstance(node, ast.keyword) and node.arg:
            idents.add(node.arg)
    strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings]
    banned = ("ccy", "fetched_at", "observed_at", "source_tier", "full_key", "provider", "moneydj", "tdcc", "fundclear", "nav", "secret", "traceback")
    assert not [i for i in idents if any(b in i.lower() for b in banned)], idents
    # 字串常數：輸入形狀判斷需要 `moneydj` 這個子字串（攔截用，不是來源名輸出），其餘來源名仍不得出現。
    assert not [s for s in strings if any(b in s.lower() for b in banned if b != "moneydj")], strings


@pytest.mark.parametrize("poison_index", range(4))
def test_contract_error_messages_name_fields_and_types_only(poison_index):
    poison = S.poisons()[poison_index]
    attempts = [
        lambda: FieldView(FieldStatus.VALUE, [poison]),
        lambda: FieldView(poison),                                                   # type: ignore[arg-type]
        lambda: good_fields(dividend_policy=FieldView(FieldStatus.VALUE, poison)),
        lambda: good_fields(inception_on=FieldView(FieldStatus.VALUE, poison)),
        lambda: good_fields(fund_name=poison),                                       # type: ignore[arg-type]
        lambda: FundLookupView(LookupState.BLOCKED, poison, "url_shape", None),
        lambda: FundLookupView(LookupState.SOURCE_FAILED, "ACTI71", poison, None),
        lambda: FundLookupView(poison),                                              # type: ignore[arg-type]
        lambda: result_view(input_code=poison + "?"),
        lambda: result_view(fields=poison),                                          # type: ignore[arg-type]
    ]
    for make in attempts:
        with pytest.raises(LookupContractError) as info:
            make()
        assert poison not in str(info.value) and poison not in repr(info.value.args)
        assert info.value.__cause__ is None and info.value.__suppress_context__


def test_exception_types_have_the_agreed_bases():
    assert issubclass(LookupContractError, ValueError) and not issubclass(LookupContractError, OSError)
    assert issubclass(LookupSourceError, Exception) and not issubclass(LookupSourceError, (ValueError, OSError))


# ───────────────────────── 靜態 ─────────────────────────

ALLOWED_IMPORTS = {"__future__", "datetime", "re", "unicodedata", "dataclasses", "enum", "typing"}


def test_viewmodel_passes_existing_ui_v3_guards_and_imports_only_the_standard_library():
    path = lib.ROOT / VIEWMODEL_REL
    assert pathlib.Path(path) in lib.population()
    source = lib.read(path)
    assert lib.import_violations(VIEWMODEL_REL, source) == [] and lib.write_surface_violations(VIEWMODEL_REL, source) == []
    assert lib.module_level_side_effects(source) == []
    modules = set(lib.imports_of(ast.parse(source), lib.package_of(VIEWMODEL_REL)))
    assert {m.split(".")[0] for m in modules} <= ALLOWED_IMPORTS, modules


def test_viewmodel_defines_no_wording_and_no_clock():
    source = (lib.ROOT / VIEWMODEL_REL).read_text(encoding="utf-8")
    code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
    tree = ast.parse(code)
    calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not calls & {"now", "today", "utcnow", "time", "getenv"}                  # 沒有時鐘（成立日期「不晚於今天」留給 L2）
    docstrings = {id(n.body[0].value) for n in ast.walk(tree) if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef)) and n.body
                  and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    cjk = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings
           and re.search(r"[㐀-鿿]", n.value)]
    assert cjk == []                                                                 # 不含任何中文顯示字樣


def test_network_guard_is_live_and_all_other_tests_ran_under_it(no_real_network):
    import socket
    with pytest.raises(S.NetworkAttempt):
        socket.create_connection(("127.0.0.1", 9))
    with pytest.raises(S.NetworkAttempt):
        socket.socket().connect(("127.0.0.1", 9))
    assert no_real_network == ["socket.create_connection", "socket.connect"]
    no_real_network.clear()                                                          # 這是刻意的負控；清掉才不會讓結尾的斷言誤報


def test_today_is_irrelevant_to_the_view_model_dates():
    """成立日期只驗格式與下限；未來日期的判定留在 L2（本層沒有時鐘）。"""
    future = (datetime.date.today() + datetime.timedelta(days=400)).isoformat()
    assert good_fields(inception_on=FieldView(FieldStatus.VALUE, future)).inception_on.value == future
