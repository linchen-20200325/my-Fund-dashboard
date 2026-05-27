"""test_ai_service.py — v18.217 多 Gemini key 自動輪替（pool + rotation）。"""
import services.ai_service as ai


# ── get_gemini_keys：來源解析 / 去重 / 保序 ──────────────────────
def test_get_gemini_keys_single(monkeypatch) -> None:
    for k in ("GEMINI_API_KEYS", *(f"GEMINI_API_KEY_{i}" for i in range(1, 11))):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "K_main")
    assert ai.get_gemini_keys() == ["K_main"]


def test_get_gemini_keys_csv_and_numbered_dedup(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "K1")
    monkeypatch.setenv("GEMINI_API_KEYS", "K2, K3 ;K1")   # K1 重複 → 去重
    monkeypatch.setenv("GEMINI_API_KEY_1", "K4")
    monkeypatch.setenv("GEMINI_API_KEY_2", "K2")          # 重複 → 去重
    for i in range(3, 11):
        monkeypatch.delenv(f"GEMINI_API_KEY_{i}", raising=False)
    assert ai.get_gemini_keys() == ["K1", "K2", "K3", "K4"]


def test_get_gemini_keys_empty(monkeypatch) -> None:
    for k in ("GEMINI_API_KEY", "GEMINI_API_KEYS",
              *(f"GEMINI_API_KEY_{i}" for i in range(1, 11))):
        monkeypatch.delenv(k, raising=False)
    assert ai.get_gemini_keys() == []


# ── gemini_generate：輪替行為 ──────────────────────────────────
def test_rotate_skips_quota_key(monkeypatch) -> None:
    """第一把撞 429 → 自動換下一把成功，且不會空等（retry=0）。"""
    seen = []

    def fake(key, prompt, max_tokens=2000, retry=2, force_json=False):
        seen.append((key, retry))
        if key == "BAD":
            return "❌ **Gemini 配額已達上限（HTTP 429）**"
        return f"OK::{key}"

    monkeypatch.setattr(ai, "_gemini", fake)
    out = ai.gemini_generate("p", keys=["BAD", "GOOD"], start=0)
    assert out == "OK::GOOD"
    assert seen == [("BAD", 0), ("GOOD", 0)]   # 兩把都用 retry=0


def test_rotate_all_quota_returns_429(monkeypatch) -> None:
    monkeypatch.setattr(
        ai, "_gemini",
        lambda *a, **k: "❌ **Gemini 配額已達上限（HTTP 429）**")
    out = ai.gemini_generate("p", keys=["A", "B"], start=0)
    assert "配額" in out or "429" in out


def test_rotate_start_offset_round_robin(monkeypatch) -> None:
    """start 指定從第二把開始試。"""
    monkeypatch.setattr(
        ai, "_gemini",
        lambda key, *a, **k: f"OK::{key}")
    assert ai.gemini_generate("p", keys=["A", "B", "C"], start=1) == "OK::B"


def test_transient_error_retries_same_key(monkeypatch) -> None:
    """5xx 忙線/逾時：不換 key，改在原 key 退避重試（retry=2）。"""
    calls = []

    def fake(key, prompt, max_tokens=2000, retry=2, force_json=False):
        calls.append((key, retry))
        return "❌ HTTP 503：high demand"

    monkeypatch.setattr(ai, "_gemini", fake)
    out = ai.gemini_generate("p", keys=["A", "B"], start=0)
    assert "503" in out
    assert calls == [("A", 0), ("A", 2)]   # 同把 key：先探測 retry=0，再退避 retry=2


def test_other_error_no_switch(monkeypatch) -> None:
    """非配額、非忙線的其他錯誤 → 直接回傳，不換 key、不重試。"""
    calls = []

    def fake(key, *a, **k):
        calls.append(key)
        return "❌ Gemini 回傳空結果，請重試"

    monkeypatch.setattr(ai, "_gemini", fake)
    out = ai.gemini_generate("p", keys=["A", "B"], start=0)
    assert "空結果" in out
    assert calls == ["A"]   # 只試第一把就回傳


def test_is_transient_error_detection() -> None:
    assert ai._is_transient_error("❌ HTTP 503：high demand")
    assert ai._is_transient_error("❌ 請求逾時，請重試")
    assert ai._is_transient_error("❌ **Gemini 模型暫時忙線（HTTP 503）**")
    assert not ai._is_transient_error("❌ **Gemini 配額已達上限（HTTP 429）**")
    assert not ai._is_transient_error("OK::A")
    assert not ai._is_transient_error(None)


def test_single_key_uses_default_retry(monkeypatch) -> None:
    """單把 key → 走 _gemini 預設 retry（保留原容錯行為）。"""
    seen = {}

    def fake(key, prompt, max_tokens=2000, retry=2, force_json=False):
        seen["retry"] = retry
        return "OK"

    monkeypatch.setattr(ai, "_gemini", fake)
    assert ai.gemini_generate("p", keys=["solo"]) == "OK"
    assert seen["retry"] == 2   # 未被改成 0


def test_no_keys_returns_warning(monkeypatch) -> None:
    assert "未設定" in ai.gemini_generate("p", keys=[])
