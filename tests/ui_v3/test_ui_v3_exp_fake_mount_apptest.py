# -*- coding: utf-8 -*-
"""🔍 找基金本地 FAKE 頁（Gate-M 方案 2a；客戶 #7073251388、總管 #7073385776）的 AppTest 行為守衛。

範圍：本地 New UI2 Preview 的 🔍 `exp` 頁。**只用 FAKE 假取數函式（`ui_v3.fixtures.exp_lookup_fake`）與合成 market stub；不取任何真實資料、不連網。**
AppTest 不能 `switch_page`，沿用 `test_ui_v3_settings_health_page.Env`（把 `st.Page`／`st.navigation` 換成替身，`app_preview.main()` 照跑）。
⚠️ AppTest 不載入瀏覽器 CSS、沒有真實導覽；390／1280 版面、鍵盤與焦點見 `test_ui_v3_exp_fake_mount_browser.py`。

固定的事實：
1. 頁級（頁頂橫幅）與卡級（結果卡標籤）FAKE 標示在**每個狀態**（尚未查詢、結果、取數失敗、頁面無法確認、入口攔截）都在；
2. 🔍 不畫 🌍 的 Status Bar、不呼叫 `adapter.load`（市場 loader 次數為 0）；
3. 🔍 不讀寫 ⚙️ 的 `SNAPSHOT_KEY`（無快照時不產生、有快照時不改）；🔍 的 session 鍵只有 `fl_` 系；不同 session 互不洩漏；
4. 零真實網路請求（socket 層守衛，攔到就是 `NetworkAttempt`）；
5. 看得見的字沒有工程資訊外漏；🌍／⚙️ 往返前後內容不變。
"""
from __future__ import annotations

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")

import fund_lookup_support as S
from fund_lookup_support import no_real_network  # noqa: F401 — autouse 網路守衛
import market_stubs as ms
from test_ui_v3_no_engineering_leak_guard import _Visible, leaks
from test_ui_v3_settings_health_page import PAGE_KEY, Env, health_rows, md
from ui_v3.adapters import fund_lookup as lookup_adapter
from ui_v3.fixtures import exp_lookup_fake as fake
from ui_v3.pages import exp_lookup as page
from ui_v3.viewmodels import exp_lookup_wording as W
from ui_v3.viewmodels import settings_health as vm

SUBMIT_CASES = ["FAKE-OK01", "FAKE-OK02", "FAKE-OK03", "FAKE-FAIL1", "FAKE-COOL1", "FAKE-IOERR", "FAKE-PAGE1", "FAKE-PAGE2", "FAKE-PAGE3",
                "FAKE-NAME1", "FAKE-REJ1", "ABC123", "   ", "https://example.invalid/x", "US0378331005"]


def submit(at, code: str):
    at.text_input(key=page.KEY_INPUT).set_value(code)
    at.button[0].click()
    return at.run()


def visible_text(at) -> str:
    parts = []
    for html in [m.value for m in at.markdown] + [m.value for m in at.sidebar.markdown]:
        parser = _Visible()
        parser.feed(html)
        parts += parser.parts
    return " ".join(parts)


def exp_keys(at) -> set:
    return {k for k in at.session_state.filtered_state if k != PAGE_KEY}


def check_marks(at) -> None:
    """頁級＋卡級 FAKE 標示恆在；沒有 🌍 Status Bar；沒有例外。"""
    assert not at.exception, at.exception
    text = md(at)
    assert 'data-block="page-fake"' in text and W.text("page_fake_banner") in text          # 頁級
    assert 'data-tag="fake"' in text and W.text("fake_tag") in text                         # 卡級
    assert 'data-shell="status-bar"' not in text                                            # 不畫 🌍 的 Status Bar
    assert [t.value for t in at.title] == [W.text("page_title")]


def check_exp_flow(env, monkeypatch=None) -> None:
    """一整條流程的所有不變量；變異負控也呼叫它（壞的實作必須讓它拋 AssertionError）。"""
    attempts: list = []
    if monkeypatch is not None:
        S.install_network_guard(monkeypatch, attempts)
    at = env.visit(env.session(), "exp")
    check_marks(at)                                                                         # 尚未查詢
    assert vm.SNAPSHOT_KEY not in at.session_state                                          # 沒有快照時不產生
    for code in ("FAKE-OK01", "FAKE-FAIL1", "FAKE-PAGE2", "   "):
        at = submit(at, code)
        check_marks(at)
        assert vm.SNAPSHOT_KEY not in at.session_state, code
        assert all(k.startswith(("fl_", "FormSubmitter:fl_")) for k in exp_keys(at)), exp_keys(at)
    assert env.calls == 0                                                                   # 市場 loader 次數為 0
    assert attempts == []                                                                   # 零網路請求


# ───────────────────────── 正控 ─────────────────────────

def test_idle_page_marks_page_level_and_card_level_fake_without_market_status_bar(monkeypatch):
    env = Env(monkeypatch)
    at = env.visit(env.session(), "exp")
    check_marks(at)
    assert 'data-state="idle"' in md(at) and env.calls == 0
    assert all(code in md(at) for code in fake.DEMO_CODES)                                  # 示範代碼提示在頁上


@pytest.mark.parametrize("code", SUBMIT_CASES)
def test_every_submitted_state_keeps_both_fake_marks_and_has_no_engineering_leak(monkeypatch, code):
    env = Env(monkeypatch)
    attempts: list = []
    S.install_network_guard(monkeypatch, attempts)
    at = submit(env.visit(env.session(), "exp"), code)
    check_marks(at)
    assert leaks(visible_text(at)) == [], (code, leaks(visible_text(at)))
    assert env.calls == 0 and attempts == []
    assert all(k.startswith(("fl_", "FormSubmitter:fl_")) for k in exp_keys(at)), exp_keys(at)


def test_result_card_shows_only_the_five_rows_and_a_fake_name(monkeypatch):
    env = Env(monkeypatch)
    at = submit(env.visit(env.session(), "exp"), "FAKE-OK01")
    text = md(at)
    for row in ("input-code", "name", "dividend-mode", "inception", "mgmt-fee"):
        assert f'data-row="{row}"' in text, row
    assert fake.FAKE_NAME in text and "不存在" not in text and "查無" not in text


def test_blocked_input_does_not_call_the_loader_and_is_not_echoed(monkeypatch):
    calls: list = []
    monkeypatch.setattr(fake, "make_loader", lambda: (lambda q: calls.append(q) or {}))
    env = Env(monkeypatch)
    at = submit(env.visit(env.session(), "exp"), "https://example.invalid/secret-path")
    check_marks(at)
    assert calls == [] and "secret-path" not in md(at)


def test_market_snapshot_is_never_read_or_written_by_the_search_page(monkeypatch):
    env = Env(monkeypatch)
    at = env.session()
    at = env.visit(at, "mkt")
    assert env.calls == 1
    before = at.session_state[vm.SNAPSHOT_KEY]
    market_text = md(at)
    at = env.visit(at, "exp")
    at = submit(at, "FAKE-OK01")
    at = submit(at, "FAKE-IOERR")
    assert at.session_state[vm.SNAPSHOT_KEY] == before and env.calls == 1                  # 快照不變、沒有多取數
    at = env.visit(at, "set")
    rows_after = health_rows(at)
    at2 = env.visit(env.session(), "mkt")                                                   # 對照組：另一個 session 只走 🌍→⚙️
    at2 = env.visit(at2, "set")
    assert [r["html"] for r in rows_after] == [r["html"] for r in health_rows(at2)]
    at = env.visit(at, "mkt")
    assert md(at) == market_text                                                            # 🌍 往返前後逐字相同


def test_sessions_do_not_leak_search_results_to_each_other(monkeypatch):
    env = Env(monkeypatch)
    first = submit(env.visit(env.session(), "exp"), "FAKE-OK01")
    assert page.KEY_VIEW in first.session_state
    other = env.visit(env.session(), "exp")
    assert page.KEY_VIEW not in other.session_state and 'data-state="idle"' in md(other)


def test_full_flow_invariants_hold_on_the_real_implementation(monkeypatch):
    check_exp_flow(Env(monkeypatch), monkeypatch)


def test_wrong_session_value_type_fails_loud_not_silently(monkeypatch):
    env = Env(monkeypatch)
    at = env.session()
    at.session_state[page.KEY_VIEW] = "not a view"
    at = env.visit(at, "exp")
    assert at.exception


# ───────────────────────── 變異負控：壞的實作必須讓同一個檢查函式失敗 ─────────────────────────

def test_mutation_page_banner_removed_is_caught(monkeypatch):
    monkeypatch.setattr(page, "page_header_html", lambda codes_hint: "")
    with pytest.raises(AssertionError):
        check_exp_flow(Env(monkeypatch))


def test_mutation_card_level_fake_tag_removed_is_caught(monkeypatch):
    real = page.render_card
    monkeypatch.setattr(page, "render_card", lambda view, *, fake: real(view, fake=False))
    with pytest.raises(AssertionError):
        check_exp_flow(Env(monkeypatch))


def test_mutation_search_page_writing_the_health_snapshot_key_is_caught(monkeypatch):
    import streamlit as st
    real = lookup_adapter.lookup_fund

    def bad(loader, raw):
        st.session_state[vm.SNAPSHOT_KEY] = object()
        return real(loader, raw)

    monkeypatch.setattr(lookup_adapter, "lookup_fund", bad)
    with pytest.raises(AssertionError):
        check_exp_flow(Env(monkeypatch))


def test_mutation_search_page_calling_the_market_loader_is_caught(monkeypatch):
    env = Env(monkeypatch)
    from ui_v3.adapters import market_page as market_adapter
    real = fake.make_loader

    def bad_make():
        market_adapter.load([{}, {}])
        return real()

    monkeypatch.setattr(fake, "make_loader", bad_make)
    with pytest.raises(AssertionError):
        check_exp_flow(env)


def test_mutation_search_page_touching_the_network_is_caught(monkeypatch):
    import socket
    real = fake.make_loader

    def bad_make():
        socket.create_connection(("example.invalid", 80), timeout=1)
        return real()

    monkeypatch.setattr(fake, "make_loader", bad_make)
    with pytest.raises(AssertionError):
        check_exp_flow(Env(monkeypatch), monkeypatch)


def test_mutation_search_page_with_a_foreign_session_key_is_caught(monkeypatch):
    import streamlit as st
    real = lookup_adapter.lookup_fund

    def bad(loader, raw):
        st.session_state["uv3_mkt_period"] = "1Y"
        return real(loader, raw)

    monkeypatch.setattr(lookup_adapter, "lookup_fund", bad)
    with pytest.raises(AssertionError):
        check_exp_flow(Env(monkeypatch))
