# -*- coding: utf-8 -*-
"""單檔基金查詢呈現元件 隔離式 FAKE Preview：AppTest（不開瀏覽器）。

驗：harness 可啟動、輸入互動（FakeLoader 經 adapter）、每個狀態的卡、CONFLICT 直接建構演示、session_state 只存淨化後的 ViewModel
（被安全攔截的輸入不留在 app 層的 state）、斷網仍綠（含正控）、子行程沒有載入取數／憑證相關模組（含正控）。
CI（環境變數 CI=true）依賴缺失 → fail，不得靜默 skip。
"""
from __future__ import annotations

import os
import re
import socket
import subprocess
import sys

import pytest

import fund_lookup_cmp_support as S

pytestmark = pytest.mark.slow

_IN_CI = os.environ.get("CI", "").strip().lower() == "true"
try:
    from streamlit.testing.v1 import AppTest
except ImportError as _exc:    # pragma: no cover - 依賴缺失
    if _IN_CI:
        pytest.fail(f"[CI] 匯入不到 streamlit：{_exc}（CI 環境必須有完整依賴；此處不得跳過）", pytrace=False)
    pytest.skip(f"本環境匯入不到 streamlit：{_exc}", allow_module_level=True)

import fund_lookup_fake_inputs as fake  # noqa: E402
from ui_v3.viewmodels.fund_lookup import FundLookupView, LookupState  # noqa: E402


def _run() -> AppTest:
    at = AppTest.from_file(str(S.APP), default_timeout=60).run()
    assert not at.exception, at.exception
    return at


def _md(at: AppTest) -> str:
    return "\n".join(m.value for m in at.markdown)


def _query(at: AppTest, raw: str) -> AppTest:
    at.text_input(key=S.KEY_INPUT).set_value(raw)
    at.button[0].click().run()          # st.form_submit_button
    assert not at.exception, at.exception
    return at


def _card(at: AppTest) -> str:
    found = [m.value for m in at.markdown if 'data-block="lookup-result"' in m.value or 'data-block="lookup-idle"' in m.value]
    assert len(found) == 1, len(found)
    return found[0]


def _state(at: AppTest):
    m = re.search(r'data-state="([a-z]+)"(?: data-reason="([a-z_]+)")?', _card(at))
    return m.group(1), m.group(2)


def test_initial_page_shows_the_harness_banner_first_title_label_isin_note_and_the_not_queried_card():
    at = _run()
    banners = [m.value for m in at.markdown if 'data-harness="true"' in m.value]
    assert len(banners) == 1 and "FAKE／測試資料（離線注入，未執行任何真實請求）" in banners[0] and at.markdown[0].value == banners[0]
    assert [t.value for t in at.title] == ["找一檔基金"]
    assert at.text_input(key=S.KEY_INPUT).label == "MoneyDJ 基金代碼或 ISIN" and at.text_input(key=S.KEY_INPUT).value == ""
    assert 'data-block="isin-note"' in _md(at)
    assert S.text_of(_card(at)).strip() == "尚未查詢" and _state(at) == ("idle", None)
    assert S.KEY_VIEW not in at.session_state


@pytest.mark.parametrize("raw,state,reason", [
    ("FAKE-OK01", "result", None), ("FAKE-OK02", "result", None), ("FAKE-OK03", "result", None),
    ("FAKE-FAIL1", "failed", "source_failed"), ("FAKE-COOL1", "failed", "source_cooling"), ("FAKE-IOERR", "failed", "loader_io_error"),
    ("FAKE-PAGE1", "unmatched", "unrecognized_page"), ("FAKE-PAGE2", "unmatched", "no_page"), ("FAKE-PAGE3", "unmatched", "source_not_listed"),
    ("FAKE-NAME1", "unmatched", "name_unconfirmed"), ("ABC123", "unmatched", "no_page"), ("fake-ok01", "result", None), ("  FAKE-OK01  ", "result", None),
    ("FAKE-REJ1", "blocked", "key_rejected"), ("   ", "blocked", "blank"), ("US0378331005", "blocked", "isin_shape"),
    ("http://x.example/a", "blocked", "url_shape"), ("A<B>C", "blocked", "code_format"), ("\tAB", "blocked", "control_or_non_ascii")])
def test_each_query_renders_the_expected_state_with_a_clean_card(raw, state, reason):
    at = _query(_run(), raw)
    assert _state(at) == (state, reason)
    card = _card(at)
    assert S.forbidden_word_violations(card) == [] and S.raw_script_violations(card) == []
    assert S.field_violations(card) == [] and S.fake_tag_order_violations(card) == []
    assert "尚未查詢" not in S.text_of(card)


def test_the_result_card_shows_the_five_labels_in_order_and_the_fake_name_before_nothing_else():
    at = _query(_run(), "FAKE-OK01")
    card = _card(at)
    assert [S.text_of(x).strip() for x in re.findall(r"<dt[^>]*>(.*?)</dt>", card, re.S)] == list(S.FIVE_LABELS)
    assert fake.FAKE_NAME in card and "配息型" in card and card.index('data-tag="fake"') < card.index("<dl")


def test_session_state_holds_only_the_sanitized_view_and_never_a_blocked_raw_input():
    for raw in ("US0378331005", "http://x.example/a", "\tAB", "L" * 100):
        at = _query(_run(), raw)
        view = at.session_state[S.KEY_VIEW]
        assert isinstance(view, FundLookupView) and view.state is LookupState.BLOCKED and view.input_code is None
        # app 層的 state 除了 widget 自己的 key 之外，沒有任何地方存有輸入原值
        stored = {k: v for k, v in at.session_state.filtered_state.items() if k != S.KEY_INPUT}
        assert raw.strip() not in repr(stored), (raw, stored)
    at = _query(_run(), "A<B>C")
    assert at.session_state[S.KEY_VIEW].input_code == "A<B>C"      # 只有通過安全回顯檢查者才留 view 內


def test_the_view_survives_a_rerun_and_a_new_query_replaces_it():
    at = _query(_run(), "FAKE-OK01")
    assert _state(at) == ("result", None)
    at.run()
    assert _state(at) == ("result", None)
    assert _state(_query(at, "FAKE-FAIL1")) == ("failed", "source_failed")


def test_the_conflict_demo_is_a_direct_construction_and_renders_the_conflict_marker():
    at = _run()
    at.selectbox(key=S.KEY_MODE).set_value("conflict_direct").run()
    assert not at.exception
    card = _card(at)
    assert card.count('data-field-status="conflict"') == 2 and fake.CONFLICT_CODE in card and S.field_violations(card) == []
    at.selectbox(key=S.KEY_MODE).set_value("adapter").run()
    assert _state(at) == ("idle", None)


def test_the_loader_is_not_called_for_blocked_inputs_and_is_called_once_for_a_passing_input():
    from ui_v3.adapters.fund_lookup import lookup_fund
    for raw in ("   ", "US0378331005", "http://x.example", "\tA", "L" * 100):
        loader = fake.make_loader()
        lookup_fund(loader, raw)
        assert loader.calls == [], raw
    for raw in ("A<B>C",):                  # 通過全部入口規則者（格式不符）也不呼叫 loader
        loader = fake.make_loader()
        lookup_fund(loader, raw)
        assert loader.calls == []
    loader = fake.make_loader()
    lookup_fund(loader, " FAKE-OK01 ")
    assert loader.calls == ["FAKE-OK01"]


# ───────────────────────── 斷網仍綠（含正控） ─────────────────────────

class NetworkAttempt(AssertionError):
    pass


def _install_network_guard(monkeypatch, attempts):
    def blocker(name):
        def _blocked(*args, **kwargs):
            attempts.append(name)
            raise NetworkAttempt(name)
        return _blocked
    monkeypatch.setattr(socket.socket, "connect", blocker("socket.connect"))
    monkeypatch.setattr(socket.socket, "connect_ex", blocker("socket.connect_ex"))
    monkeypatch.setattr(socket, "create_connection", blocker("socket.create_connection"))
    monkeypatch.setattr(socket, "getaddrinfo", blocker("socket.getaddrinfo"))


def test_the_whole_flow_runs_with_every_network_entry_point_blocked(monkeypatch):
    attempts: list = []
    _install_network_guard(monkeypatch, attempts)
    at = _run()
    for raw in ("FAKE-OK01", "FAKE-FAIL1", "FAKE-PAGE1", "US0378331005", "FAKE-IOERR"):
        _query(at, raw)
    assert attempts == []


def test_positive_control_the_network_guard_really_blocks(monkeypatch):
    attempts: list = []
    _install_network_guard(monkeypatch, attempts)
    with pytest.raises(NetworkAttempt):
        socket.create_connection(("127.0.0.1", 9))
    assert attempts == ["socket.create_connection"]


_PROBE = r"""
import sys
sys.path[:0] = [{poc!r}, {root!r}]
{extra}
import fund_lookup_fake_inputs, fund_lookup_renderer, fund_lookup_wording
from ui_v3.adapters.fund_lookup import lookup_fund
v = lookup_fund(fund_lookup_fake_inputs.make_loader(), 'FAKE-OK01')
fund_lookup_renderer.lookup_card_html(v, fake=True)
bad = sorted(m for m in sys.modules if m.split('.')[0] in {names!r} or m.startswith('google.'))
print('LOADED=' + ','.join(bad))
"""
_FORBIDDEN_ROOTS = {"requests", "gspread", "yfinance", "feedparser", "httpx", "urllib3", "services", "repositories", "infra", "fund_fetcher"}   # `google` 本身是 site 的 namespace 套件（import ui_v3.design 就會出現），故另以 `google.` 子模組判斷


def _probe(extra=""):
    code = _PROBE.format(poc=str(S.POC), root=str(S.ROOT), extra=extra, names=_FORBIDDEN_ROOTS)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(S.ROOT), timeout=120, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert out.returncode == 0, out.stderr[-800:]
    return [x for x in out.stdout.strip().splitlines()[-1].removeprefix("LOADED=").split(",") if x]


def test_a_fresh_interpreter_running_the_adapter_and_renderer_loads_no_fetch_credential_or_network_module():
    assert _probe() == []


def test_positive_control_the_probe_does_see_a_forbidden_module_when_one_is_imported():
    assert "infra" in {m.split(".")[0] for m in _probe("import infra")}
