# -*- coding: utf-8 -*-
"""🔍 找一檔基金／依條件篩選 隔離式 FAKE Preview：AppTest（不開瀏覽器）。

驗：查詢互動（輸入依 fixture 走成功／資料不足／失敗／無法辨識／ISIN）、情境切換、條件勾選、結果隨操作改變、
整頁無寫入面、斷網仍綠（含正控）、不讀憑證／環境變數（含正控）、子行程沒有載入取數／憑證相關模組（含正控）。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

import pytest

pytest.importorskip("streamlit", reason="本環境匯入不到 streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

import fund_search_support as S  # noqa: E402
import fund_search_fake_inputs as fake  # noqa: E402

IDS = list(fake.SCENARIOS)
COUNT = fake.CONDITION_COUNT


def _run() -> AppTest:
    at = AppTest.from_file(str(S.APP), default_timeout=60).run()
    assert not at.exception, at.exception
    return at


def _md(at: AppTest) -> str:
    return "\n".join(m.value for m in at.markdown)


def _query(at: AppTest, raw: str) -> AppTest:
    at.text_input(key=S.KEY_INPUT).set_value(raw)
    at.button[0].click().run()   # st.form_submit_button
    assert not at.exception, at.exception
    return at


def _scenario(at: AppTest, sid: str) -> AppTest:
    at.selectbox(key=S.KEY_SCENARIO).set_value(sid).run()
    assert not at.exception, at.exception
    return at


def _cond(at: AppTest, *ns: int) -> AppTest:
    for n in range(1, COUNT + 1):
        box = at.checkbox(key=S.KEY_COND.format(n=n))
        (box.check() if n in ns else box.uncheck())
    at.run()
    assert not at.exception, at.exception
    return at


def _block(at: AppTest, name: str) -> str:
    found = [m.value for m in at.markdown if f'data-block="{name}"' in m.value]
    assert len(found) == 1, (name, len(found))
    return found[0]


def _outcome(at: AppTest):
    found = re.findall(r'data-block="lookup-result" data-outcome="([a-z_]+)"', _md(at))
    return found[0] if found else None


# ───────────────────────── 初始畫面 ─────────────────────────

def test_initial_page_has_no_result_card_the_harness_banner_first_and_zero_conditions():
    at = _run()
    banners = [m.value for m in at.markdown if 'data-harness="true"' in m.value]
    assert len(banners) == 1 and "FAKE／測試資料（離線注入，未執行任何真實請求）" in banners[0] and at.markdown[0].value == banners[0]
    assert [t.value for t in at.title] == ["找一檔基金"]
    assert at.text_input(key=S.KEY_INPUT).label == "MoneyDJ 基金代碼或 ISIN" and at.text_input(key=S.KEY_INPUT).value == ""
    assert _outcome(at) is None and 'data-block="isin-note"' in _md(at)
    assert S.idle_violations(_block(at, "lookup-idle")) == []          # 查詢前只顯示『尚未查詢』，沒有任何欄位列
    assert at.selectbox(key=S.KEY_SCENARIO).value == fake.DEFAULT_SCENARIO
    assert 'data-counts-shown="no"' in _block(at, "exp0") and "尚未設定條件" in _block(at, "exp0")
    assert not any(at.checkbox(key=S.KEY_COND.format(n=n)).value for n in range(1, COUNT + 1))   # 首次進入沒有任何已套用條件
    assert [b.label for b in at.button] == ["查詢"]


def test_renderer_blocks_come_in_the_specified_order():
    at = _run()
    md = _md(at)
    order = [md.index(f'data-block="{b}"') for b in ("isin-note", "lookup-idle", "basic-info", "exp-divider", "exp0", "exp1", "exp2", "exp7")]
    assert order == sorted(order)


# ───────────────────────── 單檔查詢互動 ─────────────────────────

@pytest.mark.parametrize("raw,outcome", [
    ("FAKE-OK01", "found"), ("FAKE-LOW1", "insufficient"), ("FAKE-ERR1", "failed"), ("", "unrecognized"), ("???", "unrecognized"),
    ("ABC123", "no_fixture")])
def test_query_runs_the_fixture_by_input(raw, outcome):
    at = _query(_run(), raw)
    assert _outcome(at) == outcome
    assert S.forbidden_word_violations(_md(at)) == [] and S.raw_script_violations(_md(at)) == []


def test_query_result_follows_the_input_each_time():
    at = _run()
    seen = []
    for raw in ("FAKE-OK01", "FAKE-ERR1", "FAKE-LOW1", "ABC123", "FAKE-OK01"):
        seen.append(_outcome(_query(at, raw)))
    assert seen == ["found", "failed", "insufficient", "no_fixture", "found"]


def test_result_card_keeps_the_input_verbatim_and_escaped_for_every_nasty_input():
    for raw in S.NASTY_INPUTS:
        at = _query(_run(), raw)
        card = _block(at, "lookup-result")
        assert S.raw_script_violations(card) == [] and S.raw_script_violations(_md(at)) == []
        shown = re.search(r'data-value="input-code">(.*?)</span>', card, re.S).group(1)
        assert S.special_char_violations(shown) == []
        assert S.text_of(shown).strip() == raw[:100].strip()   # 輸入框 max_chars=100：超長輸入由 widget 截斷（AppTest 也會）；完整長度的 escape 由單元測試驗


def test_isin_shaped_input_shows_only_the_inactive_notice():
    at = _query(_run(), "US0378331005")
    md = _md(at)
    assert _outcome(at) is None and 'data-block="isin-notice"' in md and "ISIN 目前未啟用" in md
    assert "US0378331005" not in md and 'data-block="lookup-result"' not in md


def test_nothing_is_shown_until_the_form_is_submitted():
    at = _run()
    at.text_input(key=S.KEY_INPUT).set_value("FAKE-OK01").run()
    assert _outcome(at) is None            # 只輸入、沒送出：不查
    at.button[0].click().run()
    assert _outcome(at) == "found"


def test_lookup_and_exp_sections_do_not_affect_each_other():
    at = _query(_run(), "FAKE-OK01")
    at = _cond(_scenario(at, "mixed"), 1, 2, 3)
    assert _outcome(at) == "found" and 'data-matched="2"' in _block(at, "exp0")
    at = _query(at, "FAKE-ERR1")
    assert _outcome(at) == "failed" and 'data-matched="2"' in _block(at, "exp0")


# ───────────────────────── 下區互動 ─────────────────────────

def test_six_scenarios_in_a_selectbox_and_every_scenario_renders():
    at = _run()
    assert list(at.selectbox(key=S.KEY_SCENARIO).options) == [fake.SCENARIOS[i][0] for i in IDS] and len(IDS) == 6
    for sid in IDS:
        _scenario(at, sid)
        _cond(at, 1, 2, 3)
        assert S.page_violations(_md(at)) == [], sid


@pytest.mark.parametrize("sid,expected", [("has_match", (2, 0)), ("no_match", (0, 0)), ("undetermined_only", (0, 3)), ("mixed", (2, 2))])
def test_all_conditions_on_gives_the_scenario_counts_and_the_three_places_agree(sid, expected):
    at = _cond(_scenario(_run(), sid), 1, 2, 3)
    exp0 = _block(at, "exp0")
    assert f'data-matched="{expected[0]}"' in exp0 and f'data-undetermined="{expected[1]}"' in exp0
    html = _block(at, "exp0") + _block(at, "exp2") + _block(at, "exp7")
    assert S.count_consistency_violations(html) == []
    assert len(re.findall(r'data-fund="', html)) == sum(expected)
    assert len(re.findall(r'data-trace="', html)) == 3


def test_result_changes_with_each_checkbox_and_returns_to_zero_conditions():
    at = _scenario(_run(), "mixed")
    states = []
    for ns in ((), (1,), (1, 2), (1, 2, 3), ()):
        _cond(at, *ns)
        states.append(re.search(r'data-block="exp0"[^>]*data-conditions="(\d)"', _block(at, "exp0")).group(1) + "|" + (
            re.search(r'data-matched="(\d)" data-undetermined="(\d)"', _block(at, "exp0")) or re.search(r"(尚未)", _block(at, "exp0"))).group(0))
    assert states == ['0|尚未', '1|data-matched="4" data-undetermined="1"', '2|data-matched="2" data-undetermined="2"',
                      '3|data-matched="2" data-undetermined="2"', '0|尚未']


def test_zero_conditions_in_every_scenario_has_no_counts_and_no_rows_except_the_failed_scenario():
    for sid in IDS:
        at = _scenario(_run(), sid)
        exp2, exp7 = _block(at, "exp2"), _block(at, "exp7")
        assert "data-fund=" not in exp2 and "data-trace=" not in exp7
        if sid == "source_failed":
            assert "⛔ 取數失敗" in _block(at, "exp0")
        else:
            assert 'data-counts-shown="no"' in _block(at, "exp0")


def test_source_failure_scenario_shows_the_failure_wording_and_no_counts_even_with_conditions():
    at = _cond(_scenario(_run(), "source_failed"), 1, 2, 3)
    for name in ("exp0", "exp2", "exp7"):
        block = _block(at, name)
        assert 'data-state="failed"' in block and "⛔ 取數失敗" in block and "data-matched" not in block
    assert "目前條件下" not in _md(at)
    assert "data-fund=" not in _md(at) and "data-trace=" not in _md(at)
    assert S.forbidden_word_violations(_md(at)) == []


def test_session_state_only_conditions_return_to_initial_in_a_fresh_session():
    at = _cond(_scenario(_run(), "has_match"), 1, 2)
    assert at.checkbox(key=S.KEY_COND.format(n=1)).value is True
    fresh = _run()                                  # 新的 session：不讀任何持久層，回初始
    assert not any(fresh.checkbox(key=S.KEY_COND.format(n=n)).value for n in range(1, COUNT + 1))
    assert 'data-counts-shown="no"' in _block(fresh, "exp0")


def test_exp1_has_only_checkboxes_no_save_button_and_no_save_wording():
    at = _run()
    assert len(at.checkbox) == COUNT and [b.label for b in at.button] == ["查詢"] and not at.text_area and len(at.text_input) == 1
    assert not [w for w in S.SAVE_WORDS if w in _md(at)] and not [w for w in S.SAVE_WORDS if any(w in c.label for c in at.checkbox)]


def test_every_state_has_no_forbidden_word_for_all_inputs_and_scenarios():
    for sid in IDS:
        for raw in ("FAKE-OK01", "FAKE-ERR1", "FAKE-LOW1", "", "US0378331005", S.NASTY_INPUTS[0]):
            at = _cond(_scenario(_query(_run(), raw), sid), 1, 2, 3)
            assert S.forbidden_word_violations(_md(at)) == [], (sid, raw)
            assert S.raw_script_violations(_md(at)) == [], (sid, raw)


# ───────────────────────── 離線、不讀憑證 ─────────────────────────

def _block_network(monkeypatch, calls):
    import socket

    def blocked(*a, **k):
        calls.append(a)
        raise AssertionError("Preview 不得連網")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    return socket


def test_network_block_positive_control_really_fires(monkeypatch):
    calls = []
    socket = _block_network(monkeypatch, calls)
    with pytest.raises(AssertionError):
        socket.create_connection(("127.0.0.1", 9))
    with pytest.raises(AssertionError):
        socket.socket().connect(("127.0.0.1", 9))
    assert len(calls) == 2


def test_everything_works_with_the_network_blocked(monkeypatch):
    calls = []
    _block_network(monkeypatch, calls)
    at = _run()
    for raw in ("FAKE-OK01", "FAKE-ERR1", "US0378331005", ""):
        _query(at, raw)
    for sid in IDS:
        _cond(_scenario(at, sid), 1, 2, 3)
    assert calls == []


def _spy_environ(monkeypatch, seen):
    real_env_get = os.environ.get

    def spy(key, *a, **k):
        if re.search(r"KEY|TOKEN|SECRET|CRED|PROXY|PASS", str(key), re.I):
            seen.append(key)
        return real_env_get(key, *a, **k)

    monkeypatch.setattr(os.environ, "get", spy)


def test_environ_spy_positive_control_records_a_credential_like_read(monkeypatch):
    seen = []
    _spy_environ(monkeypatch, seen)
    os.environ.get("SOME_API_KEY")
    os.environ.get("HTTPS_PROXY")
    os.environ.get("HARMLESS_NAME")
    assert seen == ["SOME_API_KEY", "HTTPS_PROXY"]


def test_no_credential_secret_or_proxy_environment_access_in_a_run(monkeypatch):
    seen = []
    _spy_environ(monkeypatch, seen)
    at = _run()
    _query(at, "FAKE-OK01")
    for sid in IDS:
        _cond(_scenario(at, sid), 1, 2, 3)
    assert seen == []


_SCAN_TAIL = """
new = set(sys.modules) - before
bad = sorted(m for m in new if m.split('.')[0] in ('services', 'gspread', 'requests', 'urllib3', 'repositories', 'infra', 'httpx', 'yfinance', 'ui_v2', 'ui')
             or m.startswith('ui_v3.fixtures') or m.startswith('ui_v3.adapters') or m in ('ui_v3.app_preview', 'ui_v3.shell.registry'))
print(repr(bad))
print(repr(sorted(m for m in new if m.startswith(('ui_v3', 'shared', 'fund_search')))))
"""


def _scan_subprocess(app_expr: str, loop: str) -> tuple:
    code = (f"import sys\nsys.path.insert(0, {str(S.ROOT)!r})\nimport streamlit\nimport streamlit.testing.v1\n"
            f"from streamlit.testing.v1 import AppTest\nbefore = set(sys.modules)\nat = {app_expr}.run()\nassert not at.exception, at.exception\n"
            f"{loop}{_SCAN_TAIL}")
    out = subprocess.run([sys.executable, "-c", code], cwd=str(S.ROOT), capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr[-2000:]
    bad, loaded = out.stdout.strip().splitlines()[-2:]
    return bad, loaded


def test_run_does_not_load_network_data_credential_or_registry_modules():
    loop = (f"at.text_input(key={S.KEY_INPUT!r}).set_value('FAKE-OK01')\nat.button[0].click().run()\nassert not at.exception, at.exception\n"
            f"for sid in ({IDS!r}):\n    at.selectbox(key={S.KEY_SCENARIO!r}).set_value(sid).run()\n    assert not at.exception, at.exception\n")
    bad, loaded = _scan_subprocess(f"AppTest.from_file({str(S.APP)!r}, default_timeout=60)", loop)
    assert bad == "[]", bad
    for needed in ("fund_search_renderer", "fund_search_logic", "fund_search_wording", "ui_v3.viewmodels.exp_counts", "shared.ui_semantics.rules"):
        assert needed in loaded, (needed, loaded)


@pytest.mark.parametrize("module", ["urllib3", "requests", "httpx"])
def test_subprocess_scan_positive_control_flags_an_importing_app(module):
    import importlib.util
    if importlib.util.find_spec(module) is None:
        pytest.skip(f"本環境沒有 {module}")
    src = "import " + module + chr(10) + "import streamlit as st" + chr(10) + "st.write(1)"
    bad, _ = _scan_subprocess(f"AppTest.from_string({src!r})", "")
    assert module in bad, bad


# ───────────────────────── 2026-11-18 C 線：查詢前、五欄白名單、配息方式候選 ─────────────────────────

def test_idle_card_disappears_after_the_first_query_and_never_comes_back_with_the_result():
    at = _run()
    assert 'data-block="lookup-idle"' in _md(at)
    at = _query(at, "FAKE-OK01")
    assert 'data-block="lookup-idle"' not in _md(at) and _outcome(at) == "found"
    at = _query(_run(), "US0378331005")
    assert 'data-block="lookup-idle"' not in _md(at) and 'data-block="isin-notice"' in _md(at)


@pytest.mark.parametrize("raw", ["FAKE-OK01", "FAKE-OK02", "FAKE-LOW1", "FAKE-ERR1", "", "???", "ABC123"])
def test_result_card_in_the_real_app_has_only_the_five_fields_and_the_collapsed_area_has_none(raw):
    at = _query(_run(), raw)
    assert S.lookup_field_violations(_block(at, "lookup-result")) == []
    assert S.details_field_violations(_block(at, "basic-info")) == []


def test_dividend_mode_candidates_are_shown_only_for_the_fake_found_codes():
    shown = {}
    for raw in ("FAKE-OK01", "FAKE-OK02", "FAKE-LOW1", "ABC123"):
        card = _block(_query(_run(), raw), "lookup-result")
        shown[raw] = ("配息型" in card, "累積型" in card)
    assert shown == {"FAKE-OK01": (True, False), "FAKE-OK02": (False, True), "FAKE-LOW1": (False, False), "ABC123": (False, False)}
