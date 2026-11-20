"""OB-B 離線切片：`services/onebrain/provider_types.py` 的型別不變式與欄位集合釘死。

守什麼：
1. 每個資料型別的**欄位名集合 `==` 本批設計定稿（未經使用者逐項核准，見 DEC-2026-11-20-01 計法註）**（防悄悄加 confidence／cost／trace 等被禁欄位）。
2. 任何欄位名都不得含禁用詞（token／cost／trace／confidence／action／risk／policy…）。
3. `ProviderOutcome` 的「恰一者非空」不變式、各型別的建構時驗證、不可變性。

本檔不依賴 conftest 的任何 fixture，只用 stdlib + pytest + `services.onebrain`。
欄位守衛的「拿掉就轉紅」由本檔的變異負控證明（測試內動態組出違規型別餵同一個檢查函式）。
"""

from __future__ import annotations

import dataclasses
import inspect

import pytest

from services.onebrain import provider_types as pt
from services.onebrain.provider_types import (
    ProviderErrorKind,
    ProviderFailure,
    ProviderOutcome,
    ProviderRequest,
    ProviderResponse,
)

# ═══════════════════════════════════════════════════════════════════════════
# 欄位集合：本批設計定稿（未經使用者逐項核准，見 DEC-2026-11-20-01 計法註）。
# Gate 卡 §3-2／§3-3 為候選；ProviderFailure.is_fake 等為本批設計新增。
# ═══════════════════════════════════════════════════════════════════════════
EXPECTED_FIELDS: dict[type, frozenset[str]] = {
    ProviderRequest: frozenset(
        {"request_id", "model", "input_text", "timeout_seconds", "max_retries"}
    ),
    ProviderResponse: frozenset(
        {"request_id", "provider_name", "model", "text", "is_fake"}
    ),
    ProviderFailure: frozenset(
        {"request_id", "provider_name", "kind", "message", "is_fake"}
    ),
    ProviderOutcome: frozenset({"response", "failure"}),
}

EXPECTED_ERROR_KINDS = frozenset(
    {"TIMEOUT", "RATE_LIMIT", "PROVIDER_UNAVAILABLE", "DEGRADED"}
)

# 欄位名不得包含的片段（小寫比對）。對應 DEC-2026-11-20-01 不授權清單與 Gate 卡 §3-3「不含」。
FORBIDDEN_FIELD_SUBSTRINGS = (
    "token",
    "usage",
    "cost",
    "price",
    "trace",
    "span",
    "capabilit",
    "structured",
    "confidence",
    "probab",
    "score",
    "action",
    "risk",
    "cap_",
    "_cap",
    "policy",
    "config",
    "route",
    "routing",
    "digest",
    "prompt",
    "secret",
    "api_key",
    "apikey",
    "credential",
)


def _field_names(cls: type) -> frozenset[str]:
    return frozenset(f.name for f in dataclasses.fields(cls))


def _assert_field_set(cls: type, expected: frozenset[str]) -> None:
    actual = _field_names(cls)
    assert actual == expected, (
        f"{cls.__name__} 欄位集合與本批設計定稿（未經使用者逐項核准，見 DEC-2026-11-20-01 計法註）不符："
        f"多出 {sorted(actual - expected)}、缺少 {sorted(expected - actual)}"
    )


def _forbidden_field_hits(cls: type) -> list[str]:
    hits = []
    for name in _field_names(cls):
        lowered = name.lower()
        for frag in FORBIDDEN_FIELD_SUBSTRINGS:
            if frag in lowered:
                hits.append(f"{cls.__name__}.{name} ~ {frag}")
    return sorted(hits)


def _dataclasses_defined_in_module() -> list[type]:
    return [
        obj
        for _, obj in inspect.getmembers(pt, inspect.isclass)
        if obj.__module__ == pt.__name__ and dataclasses.is_dataclass(obj)
    ]


def _valid_request(**overrides) -> ProviderRequest:
    kwargs = dict(
        request_id="req-1",
        model="model-id",
        input_text="opaque",
        timeout_seconds=1.5,
        max_retries=0,
    )
    kwargs.update(overrides)
    return ProviderRequest(**kwargs)


def _valid_response(**overrides) -> ProviderResponse:
    kwargs = dict(
        request_id="req-1",
        provider_name="p",
        model="m",
        text="t",
        is_fake=True,
    )
    kwargs.update(overrides)
    return ProviderResponse(**kwargs)


def _valid_failure(**overrides) -> ProviderFailure:
    kwargs = dict(
        request_id="req-1",
        provider_name="p",
        kind=ProviderErrorKind.TIMEOUT,
        message="m",
        is_fake=True,
    )
    kwargs.update(overrides)
    return ProviderFailure(**kwargs)


# ═══════════════════════════════════════════════════════════════════════════
# 1. 欄位集合釘死
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("cls", list(EXPECTED_FIELDS))
def test_field_sets_match_design_list(cls):
    _assert_field_set(cls, EXPECTED_FIELDS[cls])


def test_module_defines_exactly_the_designed_dataclasses():
    """防止悄悄多一個資料型別（例如 TokenUsage／TraceMetadata／Capability）。"""
    assert set(_dataclasses_defined_in_module()) == set(EXPECTED_FIELDS)


def test_error_kind_members_are_exactly_the_designed_four():
    assert frozenset(m.name for m in ProviderErrorKind) == EXPECTED_ERROR_KINDS


@pytest.mark.parametrize("cls", list(EXPECTED_FIELDS))
def test_no_forbidden_field_names(cls):
    assert _forbidden_field_hits(cls) == []


def test_expected_field_sets_themselves_are_clean():
    """設計定稿清單自己不能含禁用詞（防有人把禁用欄位連同清單一起改）。"""
    for cls, names in EXPECTED_FIELDS.items():
        for name in names:
            for frag in FORBIDDEN_FIELD_SUBSTRINGS:
                assert frag not in name.lower(), f"{cls.__name__}.{name} ~ {frag}"


def test_all_dataclasses_are_frozen():
    for cls in _dataclasses_defined_in_module():
        assert cls.__dataclass_params__.frozen is True, cls.__name__


# ── 變異負控：證明上面的檢查函式「拿掉就轉紅」（動態現編違規型別，不落任何固定字串到文件）──


def _mutant_with_extra_field(base: type, extra: str) -> type:
    fields = [(f.name, f.type, dataclasses.field(default=None)) for f in dataclasses.fields(base)]
    fields.append((extra, object, dataclasses.field(default=None)))
    return dataclasses.make_dataclass(base.__name__ + "Mutant", fields, frozen=True)


@pytest.mark.parametrize("cls", [ProviderRequest, ProviderResponse, ProviderFailure, ProviderOutcome])
@pytest.mark.parametrize(
    "extra",
    ["confidence", "token_usage", "cost_usd", "trace_id", "risk_cap", "action", "policy_name"],
)
def test_mutant_extra_field_is_caught_by_both_guards(cls, extra):
    mutant = _mutant_with_extra_field(cls, extra)
    with pytest.raises(AssertionError):
        _assert_field_set(mutant, EXPECTED_FIELDS[cls])
    assert _forbidden_field_hits(mutant), f"禁用詞檢查沒抓到 {extra}"


def test_mutant_missing_field_is_caught():
    fields = [
        (f.name, f.type, dataclasses.field(default=None))
        for f in dataclasses.fields(ProviderResponse)
        if f.name != "is_fake"
    ]
    mutant = dataclasses.make_dataclass("ResponseMissingFake", fields, frozen=True)
    with pytest.raises(AssertionError):
        _assert_field_set(mutant, EXPECTED_FIELDS[ProviderResponse])


def test_clean_unrelated_dataclass_is_not_flagged():
    """反向：合規欄位不誤報（只證會紅、不證不會誤紅，等於沒驗）。"""
    clean = dataclasses.make_dataclass("Clean", [("request_id", str), ("text", str)])
    assert _forbidden_field_hits(clean) == []


# ═══════════════════════════════════════════════════════════════════════════
# 2. ProviderRequest 驗證
# ═══════════════════════════════════════════════════════════════════════════


def test_request_valid_roundtrip():
    r = _valid_request()
    assert (r.request_id, r.model, r.input_text, r.timeout_seconds, r.max_retries) == (
        "req-1",
        "model-id",
        "opaque",
        1.5,
        0,
    )


def test_request_accepts_empty_input_text_and_int_timeout():
    r = _valid_request(input_text="", timeout_seconds=3)
    assert r.input_text == ""
    assert r.timeout_seconds == 3


@pytest.mark.parametrize("field", ["request_id", "model"])
@pytest.mark.parametrize("bad", ["", "   "])
def test_request_rejects_blank_identifiers(field, bad):
    with pytest.raises(ValueError):
        _valid_request(**{field: bad})


@pytest.mark.parametrize(
    "overrides",
    [
        {"request_id": 1},
        {"model": None},
        {"input_text": b"bytes"},
        {"timeout_seconds": "1"},
        {"timeout_seconds": True},
        {"max_retries": 1.0},
        {"max_retries": True},
        {"max_retries": None},
    ],
)
def test_request_rejects_wrong_types(overrides):
    with pytest.raises(TypeError):
        _valid_request(**overrides)


@pytest.mark.parametrize("bad", [0, -1, -0.5, float("nan"), float("inf"), float("-inf")])
def test_request_rejects_non_positive_nan_or_infinite_timeout(bad):
    with pytest.raises(ValueError):
        _valid_request(timeout_seconds=bad)


def test_request_rejects_negative_retries():
    with pytest.raises(ValueError):
        _valid_request(max_retries=-1)


# ═══════════════════════════════════════════════════════════════════════════
# 3. ProviderResponse／ProviderFailure 驗證
# ═══════════════════════════════════════════════════════════════════════════


def test_response_valid_and_is_fake_must_be_bool():
    assert _valid_response().is_fake is True
    assert _valid_response(is_fake=False).is_fake is False
    for bad in (1, 0, "True", None):
        with pytest.raises(TypeError):
            _valid_response(is_fake=bad)


@pytest.mark.parametrize("field", ["request_id", "provider_name", "model"])
def test_response_rejects_blank_identifiers(field):
    with pytest.raises(ValueError):
        _valid_response(**{field: ""})


def test_response_text_must_be_str():
    with pytest.raises(TypeError):
        _valid_response(text=None)


def test_failure_valid_and_kind_must_be_enum():
    f = _valid_failure()
    assert f.kind is ProviderErrorKind.TIMEOUT
    for bad in ("timeout", 1, None):
        with pytest.raises(TypeError):
            _valid_failure(kind=bad)


def test_failure_requires_nonblank_message_and_bool_flag():
    with pytest.raises(ValueError):
        _valid_failure(message="")
    with pytest.raises(TypeError):
        _valid_failure(is_fake="yes")


# ═══════════════════════════════════════════════════════════════════════════
# 4. ProviderOutcome 不變式（恰一者非空）
# ═══════════════════════════════════════════════════════════════════════════


def test_outcome_success_shape():
    o = ProviderOutcome(response=_valid_response())
    assert o.is_success is True
    assert o.failure is None


def test_outcome_failure_shape():
    o = ProviderOutcome(failure=_valid_failure())
    assert o.is_success is False
    assert o.response is None


def test_outcome_rejects_both_empty():
    with pytest.raises(ValueError):
        ProviderOutcome()


def test_outcome_rejects_both_set():
    with pytest.raises(ValueError):
        ProviderOutcome(response=_valid_response(), failure=_valid_failure())


def test_outcome_rejects_wrong_member_types():
    with pytest.raises(TypeError):
        ProviderOutcome(response="not a response")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ProviderOutcome(failure="not a failure")  # type: ignore[arg-type]
    # 把 failure 塞進 response 欄位也要被擋
    with pytest.raises(TypeError):
        ProviderOutcome(response=_valid_failure())  # type: ignore[arg-type]


# ═══════════════════════════════════════════════════════════════════════════
# 5. 不可變性與相等性
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "obj,attr",
    [
        (_valid_request(), "model"),
        (_valid_response(), "text"),
        (_valid_failure(), "message"),
        (ProviderOutcome(response=_valid_response()), "failure"),
    ],
)
def test_instances_are_immutable(obj, attr):
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(obj, attr, "changed")


def test_value_equality_and_hashability():
    assert _valid_request() == _valid_request()
    assert hash(_valid_response()) == hash(_valid_response())
    assert _valid_failure() != _valid_failure(kind=ProviderErrorKind.DEGRADED)
