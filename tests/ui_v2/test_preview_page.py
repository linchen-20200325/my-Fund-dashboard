# -*- coding: utf-8 -*-
"""B 線預覽入口 `ui_v2/app_preview.py` 的執行期測試（slow lane；需要 streamlit 與 L1 相依）。

客戶 2026-10-12 核准新增預覽入口。靜態守衛在 `tests/ui_v2/test_preview_entry.py`（fast lane）；
本檔補 AST 看不到的那一半：

- (b) 執行期：預覽入口傳給四頁 `page.render` 的物件，與同一頁 `ui_v2/app_<頁>_live.py` 傳的**是同一批物件**；
- (c)(e) 沒有任何憑證時，四頁真資料各自照實顯示缺失，**不碰 fixtures**（各頁 `page` 上的 `fixtures`
      換成「一存取就拋錯」的替身，體例同 `tests/ui_v2/test_mkt_live_page.py`）、畫面上沒有任何示意字樣；
- (d) 標的探索在每一種示範情境（含存檔失敗開關、網址打錯情境名）下，示意資料標示都是本頁第一個元素；
- 換頁清除：資產配置沒存檔的輸入不會跟著同名 key 進到設定與診斷、再被那一頁的「存檔」寫回試算表
      （真 L2 ＋ 真 L1 ＋ 假 gspread；附對照組：拿掉清除就真的寫進去了）。

不打任何網路：Yahoo 取數以替身回錯誤；試算表 ID 與服務帳戶一律以 `get_secret` 替身回「沒有設定」。
"""

import html
import pathlib
import re
import sys
import types

import pytest

# 整檔標 slow：畫面測試不進 fast lane（守衛：tests/ui_v2/test_ui_v2_lane_guards.py）。
pytestmark = pytest.mark.slow

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "tests"))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")
preview = pytest.importorskip("ui_v2.app_preview")  # 需要 L1 的相依（gspread、bs4 等）

from infra import source_backoff as SB  # noqa: E402
from repositories import policy_supplement_repository as POL  # noqa: E402
from repositories import settings_sheet_repository as SET_REPO  # noqa: E402
from services.v2_tables import market_indicator as MI  # noqa: E402
from ui_v2.alo import page as alo_page  # noqa: E402
from ui_v2.alo import source as alo_source  # noqa: E402
from ui_v2.exp import fixtures as exp_fixtures  # noqa: E402
from ui_v2.exp import page as exp_page  # noqa: E402
from ui_v2.hld import page as hld_page  # noqa: E402
from ui_v2.hld import source as hld_source  # noqa: E402
from ui_v2.mkt import page as mkt_page  # noqa: E402
from ui_v2.mkt import source as mkt_source  # noqa: E402
from ui_v2.set import page as set_page  # noqa: E402
from ui_v2.set import source as set_source  # noqa: E402

_PREVIEW_PATH = _ROOT / "ui_v2" / "app_preview.py"
_MARK = "正式路徑碰到 fixtures"
_NO_NET = "測試替身：本測試不打網路"
_LIVE_PAGES = {"mkt": mkt_page, "hld": hld_page, "alo": alo_page, "set": set_page}
_SOURCES = {"mkt": mkt_source, "hld": hld_source, "alo": alo_source, "set": set_source}

# 依 slug 呼叫預覽入口的那一頁函式（與 `st.navigation` 執行的是同一個函式物件）。
_ROUTER = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
import streamlit as st
from ui_v2 import app_preview as p
dict((slug, fn) for slug, _t, fn in p.PAGES)[st.query_params["p"]]()
"""


class _FixturesThatBite:
    """任何屬性存取都拋錯的 fixtures 替身。"""

    def __getattr__(self, name):
        raise RuntimeError(f"{_MARK}：{name}")


@pytest.fixture
def no_secrets(monkeypatch):
    """沒有任何憑證：兩本試算表的 ID 與服務帳戶都讀不到；市場總覽的 Yahoo 取數以替身回錯誤（不打網路）。"""
    for key in ("SETTINGS_SHEET_ID", "POLICY_SHEET_ID", "google_service_account", "PROXY_URL"):
        monkeypatch.delenv(key, raising=False)
    nothing = lambda key, default=None: default  # noqa: E731
    monkeypatch.setattr(SET_REPO, "get_secret", nothing)
    monkeypatch.setattr(POL, "get_secret", nothing)
    monkeypatch.setattr(MI, "fetch_yf_close_with_error", lambda ticker, *a, **k: (None, _NO_NET))
    SET_REPO.clear_cache()
    POL.clear_cache()
    SB.reset_all()
    yield
    SET_REPO.clear_cache()
    POL.clear_cache()
    SB.reset_all()


@pytest.fixture
def biting(monkeypatch):
    """四頁真資料的 `page` 模組上的 `fixtures` 一律換成替身：任何一條正式路徑碰到就炸。"""
    for page in _LIVE_PAGES.values():
        monkeypatch.setattr(page, "fixtures", _FixturesThatBite())


def _app_test(script=_ROUTER, **query):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(script, default_timeout=120)
    for key, value in query.items():
        at.query_params[key] = value
    return at


def _main_text(at) -> str:
    """主畫面（不含側邊欄）上的字：markdown、caption、各種提示框、按鈕與輸入欄標籤。"""
    main = at.main
    out = [html.unescape(e.value) for e in main.markdown] + [e.value for e in main.caption]
    for kind in ("warning", "error", "info", "success"):
        out += [e.value for e in getattr(main, kind)]
    out += [b.label for b in main.button] + [b.help for b in main.button if b.help]
    out += [e.label for e in main.expander] + [e.label for e in main.text_input]
    for radio in main.radio:
        out.append(radio.label)
        out += [str(o) for o in radio.options]
    return "\n".join(out)


# ═══════════════════════ 整個入口（st.navigation） ═══════════════════════


def test_整個入口跑得起來_預設頁是市場總覽_側邊欄寫明非正式站(no_secrets, biting):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(_PREVIEW_PATH), default_timeout=120)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert [e.value for e in at.sidebar.info] == [preview.PREVIEW_NOTE]
    assert "B 線 UI 預覽（非正式站）" in preview.PREVIEW_NOTE
    assert '<div class="mkt-page-title">市場總覽</div>' in [e.value for e in at.main.markdown]
    assert not at.main.warning  # 示意資料標示只屬於標的探索那一頁


# ═══════════════════════ (c)(e) 無憑證：四頁照實顯示缺失 ═══════════════════════


_MISSING = {
    "mkt": ("⛔ 取數失敗：" + _NO_NET,),
    "hld": (POL.NOT_CONFIGURED_MESSAGE, SET_REPO.NOT_CONFIGURED_MESSAGE),
    "alo": (POL.NOT_CONFIGURED_MESSAGE, SET_REPO.NOT_CONFIGURED_MESSAGE),
    "set": (SET_REPO.NOT_CONFIGURED_MESSAGE,),
}


@pytest.mark.parametrize("slug", sorted(_LIVE_PAGES))
def test_e_無憑證_四頁照實顯示缺失_沒有Traceback_不碰fixtures_沒有示意字樣(no_secrets, biting, slug):
    at = _app_test(p=slug)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    text = _main_text(at)
    for needle in _MISSING[slug]:
        assert needle in text, (slug, needle)
    assert _MARK not in text
    # fixtures 的每一個基金名、類別名、訊息原文都帶「示意」；正式模式的頁首也不印情境名。
    assert "示意" not in text, slug
    assert not re.search(r"·\s*情境 ", text), slug
    assert not at.main.warning, slug  # 示意資料標示不會出現在真資料頁


def test_e_正控_同一個替身之下示範模式一定會炸(no_secrets, monkeypatch):
    """替身真的會咬人：把標的探索（示範模式，一定讀 fixtures）的 fixtures 也換掉，必須炸。"""
    monkeypatch.setattr(exp_page, "fixtures", _FixturesThatBite())
    at = _app_test(p="exp")
    at.run()
    assert at.exception and any(_MARK in e.value for e in at.exception)


# ═══════════════════════ (b) 執行期：注入物件與 live 入口相同 ═══════════════════════


def _record_render(monkeypatch, page_module) -> list:
    calls = []

    def _recorder(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(page_module, "render", _recorder)
    return calls


@pytest.mark.parametrize("slug", sorted(_LIVE_PAGES))
def test_b_執行期_四頁傳入的物件與live入口傳的是同一批(no_secrets, monkeypatch, slug):
    from streamlit.testing.v1 import AppTest

    calls = _record_render(monkeypatch, _LIVE_PAGES[slug])
    at = _app_test(p=slug)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    live = AppTest.from_file(str(_ROOT / "ui_v2" / f"app_{slug}_live.py"), default_timeout=120)
    live.run()
    assert not live.exception, [e.value for e in live.exception]
    assert len(calls) == 2, calls
    (preview_args, preview_kwargs), (live_args, live_kwargs) = calls
    assert preview_args == live_args == ()
    assert preview_kwargs.keys() == live_kwargs.keys() and preview_kwargs
    for name, obj in preview_kwargs.items():
        assert obj is live_kwargs[name], (slug, name)
        assert getattr(obj, "__module__", None) == _SOURCES[slug].__name__, (slug, name)


def test_b_執行期_標的探索與示範入口一樣不傳任何參數(monkeypatch):
    from streamlit.testing.v1 import AppTest

    calls = _record_render(monkeypatch, exp_page)
    _app_test(p="exp").run()
    AppTest.from_file(str(_ROOT / "ui_v2" / "app_exp.py"), default_timeout=120).run()
    assert calls == [((), {}), ((), {})]


# ═══════════════════════ (d) 標的探索：每一種情境都看得到標示 ═══════════════════════


def _first_main_element(at):
    children = at.main.children
    return children[min(children)]


_EXP_CASES = [(name, "0") for name in exp_fixtures.ALL_SCENARIO_NAMES] + [
    (exp_fixtures.ALL_SCENARIO_NAMES[0], "1"),
    (exp_fixtures.ALL_SCENARIO_NAMES[-1], "1"),
    ("沒有這個情境", "0"),
]


@pytest.mark.parametrize("scenario, savefail", _EXP_CASES)
def test_d_每一種情境_示意資料標示都是本頁第一個元素(scenario, savefail):
    at = _app_test(p="exp", scenario=scenario, savefail=savefail)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    first = _first_main_element(at)
    assert first.type == "warning", first
    assert first.value == preview.EXP_DEMO_BANNER
    assert [e.value for e in at.main.warning] == [preview.EXP_DEMO_BANNER]


def test_d_示意資料標示的字面():
    for needle in ("示意資料", "不是真實資料", "尚未接真資料", "假資料"):
        assert needle in preview.EXP_DEMO_BANNER


# ═══════════════════════ 換頁清除：同名輸入欄不跨頁、不被別頁存檔寫回 ═══════════════════════


@pytest.fixture
def settings_book(monkeypatch, no_secrets):
    """設定試算表接得上（假 gspread），保單試算表照舊沒設定（體例同 tests/ui_v2/test_set_live_page.py）。"""
    from _fake_settings_sheet import FakeClient, FakeSpreadsheet

    from infra import gspread_retry as GR

    class Book(FakeSpreadsheet):
        title = "客戶的設定本"

    book = Book()
    cfg = {"SETTINGS_SHEET_ID": "sheet-preview-test",
           "google_service_account": {"client_email": "sa@example.iam.gserviceaccount.com"}}
    monkeypatch.setattr(SET_REPO, "get_secret", lambda key, default=None: cfg.get(key, default))
    monkeypatch.setattr(SET_REPO, "_make_client", lambda creds: FakeClient(book))
    monkeypatch.setattr(SET_REPO, "_TITLES", {})
    monkeypatch.setattr(GR, "time", types.SimpleNamespace(sleep=lambda _s: None))
    SET_REPO.clear_cache()
    SB.reset_all()
    return book


def _settings_rows(book):
    return book.data(SET_REPO.TAB_USER_SETTING) if SET_REPO.TAB_USER_SETTING in book.tabs else []


def _type_on_alo_then_save_on_set(book):
    """在資產配置的容許帶欄打 99、不存檔，換到設定與診斷、不碰任何欄位直接按「存檔」。"""
    at = _app_test(p="alo")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    at.text_input(key="live_alo_tolerance_pp").input("99").run()
    # 同一頁內重跑不清：剛打的值還在。
    assert at.text_input(key="live_alo_tolerance_pp").value == "99"
    at.query_params["p"] = "set"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    shown = at.text_input(key="live_alo_tolerance_pp").value
    save = at.button(key="live_set4_btn_0")
    assert not save.disabled, save.help
    save.click().run()
    assert not at.exception, [e.value for e in at.exception]
    return shown, [row for row in _settings_rows(book)[1:] if row[0] == "alo_tolerance_pp"]


def test_換頁_資產配置沒存檔的輸入不會被設定與診斷的存檔寫回試算表(settings_book):
    shown, written = _type_on_alo_then_save_on_set(settings_book)
    assert shown == ""          # 設定與診斷的欄位是它自己讀到的值（尚未設定 ⇒ 空），不是資產配置打的 99
    assert written == []


def test_換頁_對照組_拿掉清除就真的寫回去了(settings_book, monkeypatch):
    """證明上一條不是空的：同名 key 真的會帶過去，而且真的會被別頁的存檔寫回試算表。"""
    monkeypatch.setattr(preview, "_forget_shared_live_inputs", lambda slug: None)
    shown, written = _type_on_alo_then_save_on_set(settings_book)
    assert shown == "99"
    assert [row[:3] for row in written] == [["alo_tolerance_pp", "99", "float"]]


def test_換頁清除只清live前綴_不碰其他頁的狀態():
    """單元層：只有「換頁」那一次清，而且只清 `live_` 開頭的 key。"""
    from streamlit.testing.v1 import AppTest

    script = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
import streamlit as st
from ui_v2 import app_preview as p
p._forget_shared_live_inputs(st.query_params["p"])   # 與預覽入口每一頁的順序相同：先清、再畫
st.session_state.setdefault("live_x", "keep-until-switch")
st.session_state.setdefault("_hld_applied", "untouched")
st.write(sorted(k for k in st.session_state if not k.startswith("_preview")))
"""
    at = AppTest.from_string(script)
    at.query_params["p"] = "alo"
    at.run()
    assert "live_x" in at.session_state and at.session_state["live_x"] == "keep-until-switch"
    at.session_state["live_x"] = "typed"
    at.session_state["_hld_applied"] = "set-by-another-page"
    at.run()                                   # 同一頁重跑：不清
    assert at.session_state["live_x"] == "typed"
    at.query_params["p"] = "set"
    at.run()                                   # 換頁：清掉後被 setdefault 重新放回初始值
    assert at.session_state["live_x"] == "keep-until-switch"
    assert at.session_state["_hld_applied"] == "set-by-another-page"   # 非 live_ 前綴：換頁也不碰
