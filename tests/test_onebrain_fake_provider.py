"""OB-B 離線切片：`FakeProvider` 行為、注入式呼叫、結構化錯誤／降級、斷網證明。

本檔不依賴 conftest 的任何 fixture（只用 stdlib + pytest + `services.onebrain`）。
斷網測試的「陷阱有效」由同檔的對照測試證明：會碰網路的替身在同一個陷阱下必須炸。
"""

from __future__ import annotations

import re
import socket
import urllib.request

import pytest

from services.onebrain import fake_provider as fp_mod
from services.onebrain import provider_interface as pi_mod
from services.onebrain.fake_provider import (
    FAKE_OUTPUT_MARKER,
    FAKE_PROVIDER_NAME,
    FakeProvider,
    FakeScenario,
)
from services.onebrain.provider_interface import AnalysisProvider
from services.onebrain.provider_types import (
    ProviderErrorKind,
    ProviderFailure,
    ProviderOutcome,
    ProviderRequest,
    ProviderResponse,
)

# 67 第 2 節的行動／方向語意詞，以及其他不得出現在 FAKE 輸出的語意。
FORBIDDEN_OUTPUT_WORDS = (
    "續抱",
    "觀察",
    "降低曝險",
    "減碼",
    "加碼",
    "買進",
    "賣出",
    "替代比較",
    # 作者暫定，Gate 卡 §3-6 待總管確認：「無法判定」同屬 67 第 2 節六詞，但 75 第 4.2 節與
    # DEC-2026-10-31-03 第 13 點要求全失敗時可顯示「AI 分析暫不可用／無法判定」。
    # 降級字樣與行動詞的區分細節待定；暫時保守列入禁用（不移除）。
    "無法判定",
    "建議",
    "Risk Cap",
    "信心",
    "機率",
    "confidence",
)

SCENARIO_TO_KIND = {
    FakeScenario.TIMEOUT: ProviderErrorKind.TIMEOUT,
    FakeScenario.RATE_LIMIT: ProviderErrorKind.RATE_LIMIT,
    FakeScenario.UNAVAILABLE: ProviderErrorKind.PROVIDER_UNAVAILABLE,
    FakeScenario.DEGRADED: ProviderErrorKind.DEGRADED,
}


def _req(request_id: str = "req-42", model: str = "model-x") -> ProviderRequest:
    return ProviderRequest(
        request_id=request_id,
        model=model,
        input_text="opaque input",
        timeout_seconds=2.0,
        max_retries=0,
    )


def _assert_fake_text_is_clean(text: str) -> None:
    assert "FAKE" in text
    folded = text.casefold()
    for word in FORBIDDEN_OUTPUT_WORDS:
        assert word.casefold() not in folded, f"FAKE 文字含不得出現的語意：{word}"
    assert not re.search(r"\d", text), "FAKE 文字不得含數字（機率／信心／數值）"
    assert "%" not in text and "％" not in text


def test_output_word_check_is_case_insensitive_and_catches_mutants():
    """變異負控：大小寫變體與行動詞必須被同一個檢查函式抓到。"""
    for bad in ("FAKE RISK CAP", "FAKE Confidence", "FAKE 建議", "FAKE 減碼", "FAKE 90", "FAKE 50%"):
        with pytest.raises(AssertionError):
            _assert_fake_text_is_clean(bad)
    _assert_fake_text_is_clean("FAKE｜離線測試")


# ═══════════════════════════════════════════════════════════════════════════
# 1. 識別與標記
# ═══════════════════════════════════════════════════════════════════════════


def test_fake_provider_name_and_class_name_are_marked_fake():
    p = FakeProvider()
    assert "FAKE" in p.name
    assert p.name == FAKE_PROVIDER_NAME
    assert "Fake" in type(p).__name__
    assert isinstance(p, AnalysisProvider)


def test_marker_constant_has_required_wording_and_is_clean():
    assert "FAKE" in FAKE_OUTPUT_MARKER
    assert "非 AI 分析" in FAKE_OUTPUT_MARKER
    _assert_fake_text_is_clean(FAKE_OUTPUT_MARKER)


def test_default_scenario_is_marker():
    assert FakeProvider().scenario is FakeScenario.MARKER


def test_scenario_members_pinned():
    assert {m.name for m in FakeScenario} == {
        "MARKER",
        "TIMEOUT",
        "RATE_LIMIT",
        "UNAVAILABLE",
        "DEGRADED",
    }


def test_scenario_must_be_enum():
    for bad in ("marker", None, 1):
        with pytest.raises(TypeError):
            FakeProvider(bad)  # type: ignore[arg-type]


# ═══════════════════════════════════════════════════════════════════════════
# 2. 成功路徑
# ═══════════════════════════════════════════════════════════════════════════


def test_marker_scenario_returns_structured_fake_response():
    out = FakeProvider(FakeScenario.MARKER).invoke(_req())
    assert isinstance(out, ProviderOutcome)
    assert out.is_success is True and out.failure is None
    resp = out.response
    assert isinstance(resp, ProviderResponse)
    assert resp.is_fake is True
    assert resp.provider_name == FAKE_PROVIDER_NAME
    assert resp.request_id == "req-42"
    assert resp.model == "model-x"
    assert resp.text == FAKE_OUTPUT_MARKER
    _assert_fake_text_is_clean(resp.text)


def test_output_is_deterministic_and_input_text_is_not_echoed():
    p = FakeProvider()
    first = p.invoke(_req())
    second = p.invoke(_req())
    assert first == second
    assert "opaque input" not in first.response.text
    # 不同輸入文字也得到同一個固定標記（FAKE 不解讀輸入）
    other = p.invoke(
        ProviderRequest("req-42", "model-x", "different", 2.0, 0)
    )
    assert other.response.text == first.response.text


# ═══════════════════════════════════════════════════════════════════════════
# 3. 結構化錯誤／降級
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("scenario", [s for s in FakeScenario if s is not FakeScenario.MARKER])
def test_failure_scenarios_return_structured_failure_not_exception(scenario):
    out = FakeProvider(scenario).invoke(_req())
    assert out.is_success is False and out.response is None
    failure = out.failure
    assert isinstance(failure, ProviderFailure)
    assert failure.kind is SCENARIO_TO_KIND[scenario]
    assert failure.is_fake is True
    assert failure.provider_name == FAKE_PROVIDER_NAME
    assert failure.request_id == "req-42"
    _assert_fake_text_is_clean(failure.message)


def test_every_scenario_is_covered_by_this_file():
    """新增 FakeScenario 成員時，本檔必須同步決定它對應的結果（防悄悄新增情境）。"""
    covered = set(SCENARIO_TO_KIND) | {FakeScenario.MARKER}
    assert covered == set(FakeScenario)


def test_each_failure_kind_is_reachable_and_distinct():
    kinds = {
        FakeProvider(s).invoke(_req()).failure.kind
        for s in FakeScenario
        if s is not FakeScenario.MARKER
    }
    assert kinds == set(ProviderErrorKind)


def test_invalid_request_is_a_programming_error_and_raises():
    for bad in (None, "text", {"request_id": "x"}):
        with pytest.raises(TypeError):
            FakeProvider().invoke(bad)  # type: ignore[arg-type]


# ═══════════════════════════════════════════════════════════════════════════
# 4. 抽象介面與注入式使用
# ═══════════════════════════════════════════════════════════════════════════


def test_interface_is_abstract():
    with pytest.raises(TypeError):
        AnalysisProvider()  # type: ignore[abstract]

    class _MissingInvoke(AnalysisProvider):
        @property
        def name(self) -> str:
            return "x"

    with pytest.raises(TypeError):
        _MissingInvoke()  # type: ignore[abstract]


def test_no_default_provider_factory_or_config_selector_exposed():
    banned_fragments = ("default", "factory", "create_", "make_", "get_provider", "select", "config")
    for mod in (fp_mod, pi_mod):
        public = [n for n in dir(mod) if not n.startswith("_")]
        for name in public:
            low = name.lower()
            assert not any(f in low for f in banned_fragments), f"{mod.__name__}.{name}"


def consume(provider: AnalysisProvider, request: ProviderRequest) -> str:
    """最小消費端：provider 一律由呼叫端注入，不存在預設值。"""
    outcome = provider.invoke(request)
    if outcome.response is not None:
        return f"ok:{outcome.response.text}"
    return f"error:{outcome.failure.kind.value}"


def test_consumer_requires_explicit_injection():
    with pytest.raises(TypeError):
        consume(request=_req())  # type: ignore[call-arg]


def test_consumer_handles_success_and_every_failure_kind():
    assert consume(FakeProvider(FakeScenario.MARKER), _req()) == f"ok:{FAKE_OUTPUT_MARKER}"
    for scenario, kind in SCENARIO_TO_KIND.items():
        assert consume(FakeProvider(scenario), _req()) == f"error:{kind.value}"


def test_consumer_is_provider_neutral_with_a_custom_stub():
    class _StubProvider(AnalysisProvider):
        @property
        def name(self) -> str:
            return "stub"

        def invoke(self, request: ProviderRequest) -> ProviderOutcome:
            return ProviderOutcome(
                failure=ProviderFailure(
                    request_id=request.request_id,
                    provider_name="stub",
                    kind=ProviderErrorKind.DEGRADED,
                    message="stub degraded",
                    is_fake=True,
                )
            )

    assert consume(_StubProvider(), _req()) == "error:degraded"


# ═══════════════════════════════════════════════════════════════════════════
# 5. 無網路：陷阱本身有效 + Fake 全流程在陷阱下仍成功
# ═══════════════════════════════════════════════════════════════════════════


class _NetworkTouched(AssertionError):
    pass


def _install_network_trap(monkeypatch) -> None:
    def _boom(*_a, **_k):
        raise _NetworkTouched("偵測到網路呼叫")

    class _TrapSocket:
        def __init__(self, *_a, **_k):
            raise _NetworkTouched("偵測到 socket 建立")

    monkeypatch.setattr(socket, "socket", _TrapSocket)
    for attr in ("getaddrinfo", "gethostbyname", "gethostbyname_ex", "create_connection"):
        monkeypatch.setattr(socket, attr, _boom)
    monkeypatch.setattr(urllib.request, "urlopen", _boom)


def test_network_trap_is_live_a_networked_provider_fails_under_it(monkeypatch):
    """對照組：會碰網路的替身在同一個陷阱下必須炸，證明陷阱不是空的。"""

    class _NetworkedProvider(AnalysisProvider):
        @property
        def name(self) -> str:
            return "networked"

        def invoke(self, request: ProviderRequest) -> ProviderOutcome:
            socket.create_connection(("example.invalid", 443))
            raise AssertionError("不應走到這裡")

    _install_network_trap(monkeypatch)
    with pytest.raises(_NetworkTouched):
        _NetworkedProvider().invoke(_req())
    with pytest.raises(_NetworkTouched):
        socket.socket()
    with pytest.raises(_NetworkTouched):
        socket.getaddrinfo("example.invalid", 80)


def test_fake_full_flow_works_with_network_trapped(monkeypatch):
    _install_network_trap(monkeypatch)
    results = [consume(FakeProvider(s), _req()) for s in FakeScenario]
    assert results[0] == f"ok:{FAKE_OUTPUT_MARKER}"
    assert len(results) == len(list(FakeScenario))
    # 型別層與介面層同樣不碰網路
    assert ProviderOutcome(response=ProviderResponse("r", "p", "m", "t", True)).is_success
