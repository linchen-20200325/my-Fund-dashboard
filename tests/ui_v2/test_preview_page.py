# -*- coding: utf-8 -*-
"""B 線預覽入口 `ui_v2/app_preview.py` 的執行期測試（slow lane；需要 streamlit 與 L1 相依）。

客戶 2026-10-12 核准新增預覽入口。靜態守衛在 `tests/ui_v2/test_preview_entry.py`（fast lane）；
本檔補 AST 看不到的那一半：

- (b) 執行期：預覽入口傳給四頁 `page.render` 的物件，與同一頁 `ui_v2/app_<頁>_live.py` 傳的**是同一批物件**；
- (c)(e) 沒有任何憑證時，四頁真資料各自照實顯示缺失，**不碰 fixtures**（各頁 `page` 上的 `fixtures`
      換成「一存取就拋錯」的替身，體例同 `tests/ui_v2/test_mkt_live_page.py`）、畫面上沒有任何示意字樣；
- ~~(d) 標的探索在每一種示範情境（含存檔失敗開關、網址打錯情境名）下，示意資料標示都是本頁第一個元素；~~
  → 2026-10-13（狀態更新，不是漏刪；客戶裁示 B 線標的探索正式模式第一批）：標的探索改走正式模式，
  併入 (b)(c)(e) 的「真資料頁」；示意資料標示撤下。
- 換頁（真 L2 ＋ 真 L1 ＋ 假 gspread）：
  - 回歸：資產配置與設定與診斷同名的 `live_alo_*` 輸入欄，在 `st.navigation` 下**不會**互相帶值、
    不會被另一頁的「存檔」寫回試算表 —— 預覽入口本身**沒有任何清除**，靠的是 streamlit 1.59.2
    把頁的 script hash 算進 widget id。升版改了算法，這一條先紅。
  - 反方向（設定與診斷 → 資產配置）同樣不帶值，資產配置存檔只寫回試算表上的原值。
  - 各頁程式自己寫進 session、換頁就要清的兩份狀態（`app_preview._PAGE_STATE_TO_DROP`），各附對照組：
    資產配置的存檔失敗帳（只讓容許帶那一鍵失敗）、市場總覽「套用」的值（回來要與新開一模一樣）。
- 誤導文字：~~側邊欄寫明標的探索為示意資料；標的探索頁沒有 `st.success`，除了示意資料標示那一句否定句，
  主畫面不出現「真實資料」四個字。~~ → 2026-10-13：~~側邊欄寫明標的探索只接上代碼；~~五頁畫面都不得有示意字樣
  （2026-10-15：#966 起標的探索也接上基本資料與淨值，側邊欄那一句已刪；狀態更新，不是漏刪）。

**換頁一律走真的 `st.navigation`**：腳本呼叫 `app_preview.main()`，以 `AppTest._page_hash`
（`calc_hash(url_path)`，與 `st.Page._script_hash` 同一個算法）選頁。⚠️ `_page_hash` 是 AppTest 的私有屬性
（`AppTest.switch_page` 只收檔案路徑，收不了 callable 頁）。私有屬性一旦失效，測試要紅而不是靜默空跑：
經 `_go` 換頁的地方檢查頁標題真的換了；直接用 `_select` 的三個呼叫點（參數化後共 6 次執行：
注入比對 4 頁＋標的探索 1 次、fixtures 替身正控 1 次）畫面不會出現頁標題（`render` 被換成記錄器、
或預期整頁拋例外），改以記錄器的呼叫次數與例外內容把關。
⛔ 不再用「同一支腳本以查詢參數切頁」的接頭：那條路五頁共用同一個 script hash，正式環境不存在，
曾經讓本組誤判同名輸入欄會跨頁寫入（2026-10-12 紅隊推翻）。

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

from streamlit.util import calc_hash  # noqa: E402

from infra import source_backoff as SB  # noqa: E402
from repositories import policy_supplement_repository as POL  # noqa: E402
from repositories import pool_repository as POOL  # noqa: E402
from repositories import settings_sheet_repository as SET_REPO  # noqa: E402
from services.v2_tables import exp_universe as EXP_UNIVERSE  # noqa: E402
from services.v2_tables import market_indicator as MI  # noqa: E402
from ui_v2.alo import page as alo_page  # noqa: E402
from ui_v2.alo import source as alo_source  # noqa: E402
from ui_v2.exp import page as exp_page  # noqa: E402
from ui_v2.exp import source as exp_source  # noqa: E402
from ui_v2.hld import page as hld_page  # noqa: E402
from ui_v2.hld import source as hld_source  # noqa: E402
from ui_v2.mkt import page as mkt_page  # noqa: E402
from ui_v2.mkt import source as mkt_source  # noqa: E402
from ui_v2.set import page as set_page  # noqa: E402
from ui_v2.set import source as set_source  # noqa: E402

_PREVIEW_PATH = _ROOT / "ui_v2" / "app_preview.py"
_MARK = "正式路徑碰到 fixtures"
_NO_NET = "測試替身：本測試不打網路"
# 2026-10-13：標的探索接上正式模式（狀態更新，不是漏刪），加入 exp。
_LIVE_PAGES = {"mkt": mkt_page, "hld": hld_page, "exp": exp_page, "alo": alo_page, "set": set_page}
_SOURCES = {"mkt": mkt_source, "hld": hld_source, "exp": exp_source, "alo": alo_source, "set": set_source}

# 真的 `st.navigation`：與 `streamlit run ui_v2/app_preview.py` 跑的是同一個 `main()`。
# 用 `from ui_v2 import app_preview`（而不是 `AppTest.from_file`）是為了讓測試能 monkeypatch 那個模組物件。
_NAV = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
from ui_v2 import app_preview
app_preview.main()
"""

# 每一頁畫出來一定有的頁標題（各頁 `page.py` 的 `<div class="…title">頁名</div>`；hld 正式模式錯誤畫面同一個）。
_TITLE = {
    "mkt": '<div class="mkt-page-title">市場總覽</div>',
    "hld": '<div class="hld-title">持倉體檢</div>',
    "exp": '<div class="exp-title">標的探索</div>',
    "alo": '<div class="alo-title">資產配置</div>',
    "set": '<div class="set-title">設定與診斷</div>',
}


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
    # 2026-10-13：標的探索的母體讀選股池；沒有服務帳戶 → L2 回「選股池未設定雲端來源」，不讀本機暫存檔。
    monkeypatch.setattr(POOL, "_sa_present", lambda: False)
    monkeypatch.setattr(MI, "fetch_yf_close_with_error", lambda ticker, *a, **k: (None, _NO_NET))
    # 2026-10-13：FRED 三鍵接上；slow lane 設了 FRED_API_KEY 環境變數，不擋的話會真的去打 FRED。
    monkeypatch.setattr(MI, "fetch_fred_vintages_with_error", lambda *a, **k: (None, _NO_NET))
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


def _app_test(**query):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(_NAV, default_timeout=120)
    for key, value in query.items():
        at.query_params[key] = value
    return at


def _select(at, slug):
    """選 `st.navigation` 的頁（下一次 `run()` 生效）。`calc_hash(url_path)` ＝ `st.Page._script_hash`。"""
    at._page_hash = calc_hash(slug)
    return at


def _go(at, slug):
    """經 `st.navigation` 換到 `slug` 那一頁並跑一次；確認真的換過去了（防 `_page_hash` 失效時空跑）。"""
    _select(at, slug).run()
    assert not at.exception, [e.value for e in at.exception]
    assert _TITLE[slug] in [e.value for e in at.main.markdown], (slug, "沒有換到這一頁")
    return at


def _raw_text(at, slug) -> str:
    """Phase 3 P0-①：四頁移出一般畫面的原文（跨頁的原始訊息；設定與診斷頁的進階診斷讀這一份）。"""
    from ui_v2 import plain

    if plain.RAW_STATE not in at.session_state:
        return ""
    store = at.session_state[plain.RAW_STATE]
    return "\n".join(entry["text"] for entry in (store.get(slug) or {}).get("entries", ()))


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
    # ~~assert "標的探索為示意資料" in at.sidebar.info[0].value~~（2026-10-13 標的探索接上正式模式；狀態更新，不是漏刪）
    assert "示意資料" not in at.sidebar.info[0].value
    assert '<div class="mkt-page-title">市場總覽</div>' in [e.value for e in at.main.markdown]
    assert not at.main.warning


# ═══════════════════════ (c)(e) 無憑證：四頁照實顯示缺失 ═══════════════════════


_MISSING = {
    "mkt": ("⛔ 取數失敗：" + _NO_NET,),
    "hld": (POL.NOT_CONFIGURED_MESSAGE, SET_REPO.NOT_CONFIGURED_MESSAGE),
    "alo": (POL.NOT_CONFIGURED_MESSAGE, SET_REPO.NOT_CONFIGURED_MESSAGE),
    "set": (SET_REPO.NOT_CONFIGURED_MESSAGE,),
    "exp": (EXP_UNIVERSE.TEXT_NOT_CLOUD, SET_REPO.NOT_CONFIGURED_MESSAGE),   # 2026-10-13 新增
}


@pytest.mark.parametrize("slug", sorted(_LIVE_PAGES))
def test_e_無憑證_四頁照實顯示缺失_沒有Traceback_不碰fixtures_沒有示意字樣(no_secrets, biting, slug):
    at = _go(_app_test(), slug)
    text = _main_text(at)
    # Phase 3 P0-①（44 第七節第三小節之七其二第 2 條）：四頁的原文移到跨頁的原始訊息（不刪除）；
    # 設定與診斷頁照舊照印原文。
    where = text if slug == "set" else _raw_text(at, slug)
    for needle in _MISSING[slug]:
        assert needle in where, (slug, needle)
        if slug != "set":
            assert needle not in text, (slug, needle)
    assert _MARK not in text
    # fixtures 的每一個基金名、類別名、訊息原文都帶「示意」；正式模式的頁首也不印情境名。
    assert "示意" not in text, slug
    assert not re.search(r"·\s*情境 ", text), slug
    assert not at.main.warning, slug  # 示意資料標示不會出現在真資料頁


def test_e_正控_同一個替身之下示範模式一定會炸(no_secrets, monkeypatch):
    """替身真的會咬人：把標的探索的 fixtures 換掉，跑**示範入口**（一定讀 fixtures），必須炸。

    ~~原本走預覽入口的標的探索頁~~ → 2026-10-13 預覽的標的探索改走正式模式（狀態更新，不是漏刪），
    預覽裡已沒有示範模式的頁，改跑示範入口 `ui_v2/app_exp.py`。"""
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr(exp_page, "fixtures", _FixturesThatBite())
    at = AppTest.from_file(str(_ROOT / "ui_v2" / "app_exp.py"), default_timeout=120)
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
    at = _select(_app_test(), slug)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    live = AppTest.from_file(str(_ROOT / "ui_v2" / f"app_{slug}_live.py"), default_timeout=120)
    live.run()
    assert not live.exception, [e.value for e in live.exception]
    assert len(calls) == 2, calls
    (preview_args, preview_kwargs), (live_args, live_kwargs) = calls
    assert preview_args == live_args == ()
    # ~~`preview_kwargs.keys() == live_kwargs.keys()`~~ → 2026-10-17 P0-②（有意識的更正，不是漏刪）：預覽在四頁
    # 多傳一個 `settings_page`（設定與診斷那一頁的 `st.Page`，只換頁）；拿掉它之後其餘照舊逐一相同、同一物件。
    preview_kwargs = dict(preview_kwargs)
    settings_page = preview_kwargs.pop("settings_page", None)
    if slug == "set":
        assert settings_page is None
    else:
        from streamlit.navigation.page import StreamlitPage

        assert isinstance(settings_page, StreamlitPage) and settings_page.url_path == "set", settings_page
        assert settings_page.title == dict((s, t) for s, t, _f in preview.PAGES)["set"]
    assert "settings_page" not in live_kwargs
    assert preview_kwargs.keys() == live_kwargs.keys() and preview_kwargs
    for name, obj in preview_kwargs.items():
        assert obj is live_kwargs[name], (slug, name)
        assert getattr(obj, "__module__", None) == _SOURCES[slug].__name__, (slug, name)


def test_b_執行期_標的探索的示範入口照舊不傳任何參數(monkeypatch):
    """~~預覽的標的探索與示範入口一樣不傳任何參數~~ → 2026-10-13（狀態更新，不是漏刪）：預覽改與
    `app_exp_live.py` 傳同一批物件（上一條參數化已含 exp）；示範入口不動。"""
    from streamlit.testing.v1 import AppTest

    calls = _record_render(monkeypatch, exp_page)
    AppTest.from_file(str(_ROOT / "ui_v2" / "app_exp.py"), default_timeout=120).run()
    assert calls == [((), {})]


# ═══════════════════════ (d) ~~標的探索：每一種情境都看得到標示~~ ═══════════════════════
#
# ~~`_first_main_element`／`_EXP_CASES`／`test_d_每一種情境_示意資料標示都是本頁第一個元素`／`test_d_示意資料標示的字面`~~
# → 2026-10-13 撤下（狀態更新，不是漏刪；客戶裁示 B 線標的探索正式模式第一批）：預覽的標的探索改走正式模式，
#   不再有示範情境與示意標示（那一句「本頁為示意資料、不是真實資料」接上真資料後就是假話）。
#   正式模式「不碰 fixtures、沒有示意字樣、照實顯示缺失」由上面 (e) 的參數化（已含 exp）驗。


def test_d_預覽沒有示意資料標示這個常數了():
    assert not hasattr(preview, "EXP_DEMO_BANNER")


# ═══════════════════════ 換頁（真 st.navigation） ═══════════════════════


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


def _tolerance_rows(book):
    rows = book.data(SET_REPO.TAB_USER_SETTING) if SET_REPO.TAB_USER_SETTING in book.tabs else []
    return [row[:3] for row in rows[1:] if row[0] == "alo_tolerance_pp"]


def _save_set(at):
    save = at.button(key="live_set4_btn_0")
    assert not save.disabled, save.help
    save.click().run()
    assert not at.exception, [e.value for e in at.exception]


def test_回歸_同名輸入欄在st_navigation下不跨頁_不被另一頁的存檔寫回(settings_book):
    """預覽入口**沒有任何清除**；靠的是 streamlit 1.59.2 把頁的 script hash 算進 widget id。

    升版若改了 widget id 算法（不再帶頁的 script hash），資產配置打的 99 會出現在設定與診斷的同名欄、
    再被那一頁的「存檔」寫進試算表 —— 本條就會紅。
    """
    at = _go(_app_test(), "alo")
    at.text_input(key="live_alo_tolerance_pp").input("99").run()
    assert at.text_input(key="live_alo_tolerance_pp").value == "99"   # 同一頁內重跑：值還在
    _go(at, "set")
    assert at.text_input(key="live_alo_tolerance_pp").value == ""     # 設定與診斷讀到的是它自己的（尚未設定）
    _save_set(at)
    assert _tolerance_rows(settings_book) == []


def test_回歸_正控_同一頁輸入再存檔確實會寫入(settings_book):
    """證明上一條的「寫入 0 列」不是因為存檔根本寫不進去。"""
    at = _go(_app_test(), "set")
    at.text_input(key="live_alo_tolerance_pp").input("99").run()
    _save_set(at)
    assert _tolerance_rows(settings_book) == [["alo_tolerance_pp", "99", "float"]]


_TOL_FAIL = "容許帶寫入失敗（測試注入）"


@pytest.fixture
def tolerance_save_fails(monkeypatch):
    """資產配置的存檔函式只對 `alo_tolerance_pp` 回失敗（其餘鍵照真的 L2 寫）；設定與診斷的存檔不受影響。"""
    real = alo_source.save_setting

    def flaky(key, value, kind):
        if key == "alo_tolerance_pp":
            return {"status": "failed", "key": key, "message": _TOL_FAIL}
        return real(key, value, kind)

    monkeypatch.setattr(alo_source, "save_setting", flaky)


def _tolerance_fail_then_set_ok_then_back(book):
    """資產配置存容許帶失敗 → 設定與診斷把同一鍵存成功 → 回資產配置。回傳回來後的 (失敗帳, 畫面字)。"""
    at = _go(_app_test(), "alo")
    at.text_input(key="live_alo_tolerance_pp").input("7").run()
    at.button(key="live_alo1_btn_0").click().run()
    assert not at.exception, [e.value for e in at.exception]
    errors = at.session_state[alo_page._SAVE_ERRORS_STATE]
    assert errors.get("alo_tolerance_pp") == _TOL_FAIL                   # 失敗的確實是容許帶那一鍵
    assert [k for k, m in errors.items() if m == _TOL_FAIL] == ["alo_tolerance_pp"]
    assert _TOL_FAIL in _raw_text(at, "alo")                              # 失敗當下照實記下（原文移到進階診斷）
    assert "⛔" in _main_text(at)                                          # 一般畫面照實顯示失敗狀態
    _go(at, "set")
    at.text_input(key="live_alo_tolerance_pp").input("7").run()
    _save_set(at)
    assert _tolerance_rows(book) == [["alo_tolerance_pp", "7", "float"]]  # 這一鍵在設定與診斷真的存成功了
    _go(at, "alo")
    text = _main_text(at) + "\n" + _raw_text(at, "alo")      # 一般畫面＋原始訊息（Phase 3 P0-①：原文移到後者）
    if alo_page._SAVE_ERRORS_STATE not in at.session_state:   # AppTest 的 session_state 沒有 .get
        return None, text
    return at.session_state[alo_page._SAVE_ERRORS_STATE], text


def test_必修2_容許帶在設定與診斷存成功後_回資產配置不再顯示該鍵的失敗(settings_book, tolerance_save_fails):
    state, text = _tolerance_fail_then_set_ok_then_back(settings_book)
    assert state is None
    assert _TOL_FAIL not in text


def test_必修2_對照組_拿掉換頁pop_容許帶的失敗提示殘留(settings_book, tolerance_save_fails, monkeypatch):
    monkeypatch.setattr(preview, "_PAGE_STATE_TO_DROP", ("_mkt_applied",))   # 只拿掉資產配置那一格
    state, text = _tolerance_fail_then_set_ok_then_back(settings_book)
    assert state == {"alo_tolerance_pp": _TOL_FAIL}
    assert _TOL_FAIL in text


def _tolerance_fail_then_leave_and_back():
    """資產配置容許帶打 7、存檔失敗（暫存存下）→ 換到市場總覽（什麼都不做）→ 回資產配置。
    回傳回來後的 (暫存或 None, 容許帶欄位的值)。

    ⚠️ 刻意換到市場總覽、不換到設定與診斷：本組實測，從設定與診斷換回來的第一輪，`live_alo_tolerance_pp`
    這個鍵在 session 裡還查得到（值是設定與診斷那一頁同名欄的），帶回那一支不會走到，
    對照組就證明不了「沒清暫存會帶回」。市場總覽沒有同名欄。"""
    at = _go(_app_test(), "alo")
    at.text_input(key="live_alo_tolerance_pp").input("7").run()
    at.button(key="live_alo1_btn_0").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state[alo_page._PENDING_INPUTS_STATE] == {
        "alo_tolerance_pp": {"text": "7", "raw": None}}                  # 前提：失敗那個鍵確實暫存了
    _go(at, "mkt")
    _go(at, "alo")
    pending = (at.session_state[alo_page._PENDING_INPUTS_STATE]
               if alo_page._PENDING_INPUTS_STATE in at.session_state else None)  # AppTest 的 session_state 沒有 .get
    return pending, at.text_input(key="live_alo_tolerance_pp").value


def test_暫存帶回_存檔失敗後換頁再回來_暫存已清_欄位顯示試算表上的值(settings_book, tolerance_save_fails):
    """客戶 2026-10-16 裁示方案 B：資產配置寫入失敗那個鍵的輸入欄暫存，預覽換頁一併清（`_PAGE_STATE_TO_DROP`）。"""
    pending, value = _tolerance_fail_then_leave_and_back()
    assert pending is None
    assert value == ""                                                   # 試算表上沒有這個鍵 ⇒ 空白，不帶回 7


def test_暫存帶回_對照組_拿掉換頁pop_回來時帶回沒存成功的字(settings_book, tolerance_save_fails, monkeypatch):
    monkeypatch.setattr(preview, "_PAGE_STATE_TO_DROP",
                        tuple(k for k in preview._PAGE_STATE_TO_DROP if k != alo_page._PENDING_INPUTS_STATE))
    pending, value = _tolerance_fail_then_leave_and_back()
    assert pending == {"alo_tolerance_pp": {"text": "7", "raw": None}}
    assert value == "7"


def test_反方向回歸_設定與診斷打的值不帶到資產配置_資產配置存檔只寫回原值(settings_book):
    from services.v2_tables import settings_store

    assert settings_store.save_setting_for_page("alo_tolerance_pp", "4", "float", [])["status"] == "saved"
    SET_REPO.clear_cache()
    at = _go(_app_test(), "set")
    assert at.text_input(key="live_alo_tolerance_pp").value == "4"
    at.text_input(key="live_alo_tolerance_pp").input("77").run()
    _go(at, "alo")
    assert at.text_input(key="live_alo_tolerance_pp").value == "4"       # 資產配置顯示試算表上的值
    at.button(key="live_alo1_btn_0").click().run()
    assert not at.exception, [e.value for e in at.exception]
    rows = _tolerance_rows(settings_book)
    assert rows and all(row == ["alo_tolerance_pp", "4", "float"] for row in rows), rows


# ═══════════════════════ 市場總覽「套用」的值：換頁就清 ═══════════════════════


@pytest.fixture
def vix_series(monkeypatch, no_secrets):
    """市場總覽有一段 VIX 日線可算（不打網路），套用不同觀察窗時三張核心卡的數字才會不同。"""
    import pandas as pd

    # ~~`pd.date_range("2026-06-01", periods=120, freq="D")`、attrs 只有 fetched_at~~ → 2026-10-14（稽核 N 的 B1；
    # 有意識的更正，不是漏刪）：L1 自 2026-10-13 起帶來源自報的交易所時區，缺時區整鍵不寫 —— 舊替身沒帶，
    # VIX 一列都寫不進去，三張核心卡變成「資料未備」，下面兩條客戶裁示守衛等於拿空畫面比空畫面。
    # 改成 VIX 日線的真實形狀：工作日、芝加哥當地 02:00（夏令 UTC 07:00；探測報告實測），帶 `exchange_tz`。
    index = pd.bdate_range("2026-05-01", periods=105) + pd.Timedelta(hours=7)
    series = pd.Series([15.0 + (i % 9) for i in range(105)], index=index, dtype=float, name="^VIX")
    series.attrs["fetched_at"] = "2026-10-01T06:00:00+00:00"
    series.attrs["exchange_tz"] = "America/Chicago"
    monkeypatch.setattr(MI, "fetch_yf_close_with_error", lambda ticker, *a, **k: (series.copy(), None))


@pytest.fixture
def vix_saved(vix_series, settings_book):
    """`vix_series` ＋ 設定試算表上**已存**一組比較條件（觀察窗 10 日、基準日 2026-08-03）。

    2026-10-14（稽核 N 的 N-A；有意識的更正，不是漏刪）：只有 `vix_series` 時讀不到任何已存設定，
    比較列永遠是「比較條件讀不到」—— 暫存值就算漏進正式結果，畫面也一樣，兩條客戶裁示守衛抓不到
    （突變 MB1、MB2 皆存活，origin/main 上亦同）。這裡經正式 L1 `save_user_setting` 寫進假試算表，
    寫法照 `mkt.live.mkt4_save_entries`（含一致性憑證鍵），讓比較列真的算出數字。
    """
    from ui_v2.mkt import live as mkt_live

    for entry in mkt_live.mkt4_save_entries(10, "2026-08-03"):
        assert entry["error"] is None, entry
        SET_REPO.save_user_setting(entry["key"], entry["value"], entry["value_kind"], mask=lambda text: text)
    SET_REPO.clear_cache()
    return settings_book


def _mkt_screen(at):
    return [html.unescape(e.value) for e in at.main.markdown] + [e.value for e in at.main.caption] \
        + [e.label for e in at.main.expander]


def _cards(at):
    """三張核心卡（正式結果）那幾段 HTML。"""
    return [e.value for e in at.main.markdown if 'class="mkt-card"' in e.value]


_VIX_VALUE_RE = re.compile(r'波動度指數</div>\s*<div class="mkt-mv-value"[^>]*>\s*\d+(?:\.\d+)?\s*</div>')


def _compare_shown(texts) -> bool:
    """MKT-1 的比較列真的以已存設定算出數字（不是「比較條件讀不到」）—— 2026-10-14 稽核 N 的 N-A。"""
    return any(re.search(r"與觀察窗起點的差：-?\d", t) for t in texts)


def _vix_value_shown(texts) -> bool:
    """MKT-1 的波動度指數有畫出數值（不是「資料未備」）—— 客戶裁示守衛不得是空對空的前提（2026-10-14 稽核 N 的 B1）。"""
    return any(_VIX_VALUE_RE.search(t) for t in texts)


def _fill_mkt_window(at):
    import datetime

    at.number_input(key="mkt4_days").set_value(30).run()
    at.date_input(key="mkt4_baseline").set_value(datetime.date(2026, 9, 1)).run()
    assert not at.exception, [e.value for e in at.exception]


# ~~`_apply_mkt_window`／`_mkt_apply_leave_return` 與下面兩條「套用後換頁再回來」~~
# → **2026-10-13 狀態更新（不是漏刪；客戶裁示：未儲存的暫存設定不得影響正式結果）**：
#   正式模式（預覽四頁皆是）的「套用」停用、三張核心卡只讀已存設定，`"_mkt_applied"` 不再進任何計算，
#   舊兩條要驗的「套用改了畫面、換頁回來要清掉」在正式模式已不可能發生。改驗裁示本身：
#   欄位填了不存 → 三張核心卡不動；換頁回來與新開相同；直接塞一份 `_mkt_applied` 也不改畫面。


def test_市場總覽_正式模式套用停用_未存的欄位值不改三張核心卡_換頁回來與新開相同(vix_saved):
    at = _go(_app_test(), "mkt")
    fresh = _mkt_screen(at)
    cards = _cards(at)
    assert cards, "抓不到三張核心卡 —— 下面的比較會變成空比"
    assert _vix_value_shown(cards), "波動度指數沒有數值 —— 下面的比較會變成空畫面比空畫面"
    assert _compare_shown(cards), "比較列沒有算出數字 —— 暫存值漏進正式結果時畫面也不會變"
    # ~~assert at.button(key="mkt4_apply").disabled~~ → 2026-10-17 Phase 3 P0-③（44 第七節第三小節之七其二第 7 條；
    # 有意識的更正，不是漏刪）：正式模式下永遠停用的「套用」一般畫面不畫。測試名保留，便於對照沿革。
    assert not [b for b in at.button if b.key == "mkt4_apply" or b.label == "套用"]
    _fill_mkt_window(at)
    assert _cards(at) == cards                              # 欄位有值、沒存檔：正式結果不動
    _go(at, "hld")
    _go(at, "mkt")
    assert _mkt_screen(at) == fresh


def test_市場總覽_session裡的套用值不進正式結果(vix_saved):
    at = _go(_app_test(), "mkt")
    fresh = _mkt_screen(at)
    assert _vix_value_shown(fresh), "波動度指數沒有數值 —— 下面的比較會變成空畫面比空畫面"
    assert _compare_shown(fresh), "比較列沒有算出數字 —— 暫存值漏進正式結果時畫面也不會變"
    at.session_state["_mkt_applied"] = {"window_days": 30, "baseline_date": "2026-09-01"}
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert _mkt_screen(at) == fresh


# ═══════════════════════ 持倉體檢「套用」的值：換頁再回來，畫面與計算一致（2026-10-15 Phase 2 批 1） ═══════════════════════
#
# 盤點時懷疑：持倉體檢「套用」（`ui_v2/hld/page.py::_APPLIED_KEY`）是頁面程式自己存進 session 的，
# 預覽入口換頁不清它；輸入欄離開這一頁會被清掉（檔頭那條 widget id 規則）→「輸入欄空白、計算仍用看不見的舊區間」，
# 與 2026-10-12 市場總覽那一份同型。**本組重現的結果是不成立**：回來那一次欄位還沒畫過，
# `ui_v2/hld/logic.py::_build_page_model` 以**已套用的區間**當欄位的值（`fields = ... else {"window_start": applied_window[0], ...}`），
# 門檻列的格子也照已套用的門檻畫 —— 輸入欄回填套用值，與計算一致。故預覽入口的換頁清單**不加**這一格。
# 本條守的是「一致」本身，不釘套用值留不留（那屬客戶裁示）：回來後要嘛整組是套用的（欄位＝套用值、卡＝套用結果），
# 要嘛整組是新開的（欄位＝新開值、卡＝新開結果）；兩邊各取一半就紅。

_HLD_NEW_START = "2026-06-01"


@pytest.fixture
def hld_dataset(monkeypatch, no_secrets):
    """持倉體檢有一份算得出數字的資料（假資料 `full` 去掉「（示意）」字樣、DIRECT 改掛既有保單；不打網路）。

    體例照 `tests/ui_v2/test_hld_live_page.py::_apply_app`：today 固定 2026-09-28（淨值恰 10 天、照算）。
    預覽入口每次渲染才讀 `hld_source.load_live`，換掉模組屬性即可。"""
    import datetime

    from ui_v2.hld import fixtures as hld_fixtures
    from ui_v2.hld import logic as hld_logic

    def scrub(node):
        if isinstance(node, str):
            return node.replace(hld_logic.HINT, "")
        if isinstance(node, dict):
            return {k: scrub(v) for k, v in node.items()}
        if isinstance(node, list):
            return [scrub(v) for v in node]
        return node

    dataset = scrub(hld_fixtures.scenario("full")["dataset"])
    for holding in dataset["holding"]:
        if holding["policy_id"] == "DIRECT":
            holding["policy_id"] = "P-001"
    live_args = {
        "direct_policy_id": "DIRECT",
        "today": datetime.date(2026, 9, 28),
        "nav_provenance": {row["fund_code"]: {"cache_fallback": False, "stale": None} for row in dataset["nav"]},
    }
    monkeypatch.setattr(hld_source, "load_live", lambda: {"dataset": dataset, "live_args": live_args})


def _hld_cards(at):
    """層 2 三張核心卡（正式結果）那幾段 HTML。"""
    # Phase 3 P0-①：正式模式卡頭不印塊代號，改以 `data-block` 屬性定位。
    return [e.value for e in at.main.markdown if 'class="hld-card"' in e.value and 'data-block="HLD-' in e.value]


def _hld_field(at):
    return at.text_input(key="hld4_window_start").value


def test_持倉體檢_套用後換頁再回來_輸入欄與核心卡用的是同一個區間(hld_dataset):
    at = _go(_app_test(), "hld")
    fresh_field, fresh_cards = _hld_field(at), _hld_cards(at)
    assert fresh_cards, "抓不到核心卡 —— 下面的比較會變成空比"
    assert fresh_field and fresh_field != _HLD_NEW_START, fresh_field
    # ~~按「套用」之後核心卡換成新區間、換頁回來兩者一致~~ → 客戶 2026-10-16 裁示第 2 點（有意識的更正，不是漏刪）：
    # 正式模式「套用」停用、核心卡只讀已存設定 —— 改欄位按套用，核心卡不動；換頁回來輸入欄回到已存值、核心卡照舊。
    # BL-0250 批次 3-A U4（`DEC-2026-10-19-05`；有意識的更正，不是漏刪）：正式模式不畫永遠停用的「套用」 ——
    # ~~找到那一枚停用的「套用」按下去~~ → 畫面上沒有那一枚；改欄位之後照舊驗核心卡不動、換頁回來回到已存值。
    assert not [b for b in at.main.button if b.label == "套用"]
    at.text_input(key="hld4_window_start").input(_HLD_NEW_START).run()
    assert not at.exception, [e.value for e in at.exception]
    assert _hld_cards(at) == fresh_cards
    _go(at, "mkt")
    _go(at, "hld")
    assert (_hld_field(at), _hld_cards(at)) == (fresh_field, fresh_cards)


def test_換頁清單_同一頁內重跑不清_換頁只清清單內的key():
    """單元層：只有換頁那一次 pop；同一頁重跑不碰；清單以外的 key 不碰。"""
    from streamlit.testing.v1 import AppTest

    key = alo_page._SAVE_ERRORS_STATE
    # ~~assert preview._PAGE_STATE_TO_DROP == (key, "_mkt_applied")~~（2026-10-13 多一格市場總覽存檔結果；狀態更新，不是漏刪）
    # ~~… == (key, "_mkt_applied", mkt_page._SAVE_RESULTS_STATE)~~ → 2026-10-13 多兩格標的探索的（狀態更新，不是漏刪）
    assert preview._PAGE_STATE_TO_DROP == (key, "_mkt_applied", mkt_page._SAVE_RESULTS_STATE,
                                           exp_page._SAVE_RESULTS_STATE, exp_page._RULES_STATE,
                                           exp_page._SEEDED_STATE,  # 2026-10-13 稽核 L 回修
                                           alo_page._PENDING_INPUTS_STATE,  # 2026-10-16 客戶裁示方案 B
                                           hld_page._SAVE_RESULTS_STATE)  # 2026-10-16 客戶裁示第 2 點
    script = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
import streamlit as st
from ui_v2 import app_preview as p
p._on_page(st.query_params["slug"])
"""
    at = AppTest.from_string(script)
    at.query_params["slug"] = "alo"
    at.run()
    at.session_state[key] = {"alo_tolerance_pp": "失敗"}
    at.session_state["_mkt_applied"] = {"window_days": 30}
    at.session_state["_hld_applied"] = "別頁自己的狀態"
    at.run()                                                 # 同一頁重跑：不清
    assert at.session_state[key] == {"alo_tolerance_pp": "失敗"}
    assert at.session_state["_mkt_applied"] == {"window_days": 30}
    at.query_params["slug"] = "set"
    at.run()                                                 # 換頁：pop
    assert key not in at.session_state and "_mkt_applied" not in at.session_state
    assert at.session_state["_hld_applied"] == "別頁自己的狀態"   # 其他程式寫入的 key 不碰


# ═══════════════════════ Phase 3 P0-①：跨頁的原始訊息（設定與診斷頁的進階診斷） ═══════════════════════


def test_P0_1_開過持倉體檢再到設定與診斷_進階診斷照印那一頁移出的原文(no_secrets, biting):
    """44 第七節第三小節之七其二第 8 條：四頁移出一般畫面的原文，換頁之後在設定與診斷頁的「進階診斷（原始訊息）」
    照印（只收本次瀏覽開過的頁）。它不在 `_PAGE_STATE_TO_DROP` 裡，換頁不會被清掉。"""
    from ui_v2 import plain

    at = _go(_app_test(), "hld")
    assert POL.NOT_CONFIGURED_MESSAGE not in _main_text(at)          # 一般畫面不印原文
    assert POL.NOT_CONFIGURED_MESSAGE in _raw_text(at, "hld")
    _go(at, "set")
    diag = [e for e in at.main.expander if e.label == plain.ADVANCED_DIAG_TITLE]
    assert len(diag) == 1
    body = "\n".join(html.unescape(m.value) for m in diag[0].markdown)
    assert POL.NOT_CONFIGURED_MESSAGE in body and plain.PAGE_NAMES["hld"] in body
    assert f"{plain.PAGE_NAMES['exp']}（" not in body                  # 沒開過的頁不在「已記錄的頁」裡


# ═══════════════════════ Phase 3 P0-②：「前往設定與診斷」只換頁 ═══════════════════════


def _recorders(monkeypatch):
    """五頁 source 的 load／save／refetch 換成「記下呼叫再照原樣做」的替身（預覽的頁函式在呼叫時才取屬性）。"""
    calls = {"save": [], "refetch": [], "load": []}
    for slug, source in _SOURCES.items():
        for attr, kind in (("save_setting", "save"), ("refetch", "refetch"), ("load_live", "load")):
            real = getattr(source, attr, None)
            if real is None:
                continue

            def _wrap(*args, _real=real, _kind=kind, _slug=slug, **kwargs):
                calls[_kind].append((_slug, args))
                return _real(*args, **kwargs)

            _wrap.__module__ = source.__name__
            monkeypatch.setattr(source, attr, _wrap)
    return calls


@pytest.mark.parametrize("slug", ["mkt", "hld", "exp", "alo"])
def test_P0_2_四頁的前往設定與診斷是頁面連結_指向設定與診斷_沒有同名按鈕(no_secrets, biting, slug):
    from ui_v2 import health

    at = _go(_app_test(), slug)
    links = [e for e in at.get("page_link") if e.proto.label == health.SETTINGS_LINK_LABEL]
    assert len(links) == 1, [e.proto for e in at.get("page_link")]
    assert links[0].proto.page == "set" and links[0].proto.page_script_hash == calc_hash("set")
    assert health.SETTINGS_LINK_LABEL not in [b.label for b in at.button]
    assert health.SETTINGS_ELSEWHERE_TEXT not in [c.value for c in at.main.caption]   # 預覽有連結，不寫那一行


def _book_state(book):
    """試算表每一分頁的列（含表頭）與到目前為止的寫入呼叫。"""
    from _fake_settings_sheet import WRITE_METHODS

    rows = {title: [list(r) for r in ws.rows] for title, ws in book.tabs.items()}
    writes = [c for c in book.calls if c[0] in WRITE_METHODS]
    return rows, writes


@pytest.mark.parametrize("slug", ["mkt", "hld", "exp", "alo"])
def test_P0_2_畫頁面連結與換到設定與診斷_save與refetch都是0次_試算表一列未動(settings_book, biting, monkeypatch, slug):
    """護欄 3：導覽只換頁（44 第七節第三小節之七其五第 4 條的驗法）。畫出連結的那一輪、以及換到設定與診斷之後：
    任何一頁的存檔與重新取數都沒有被呼叫，設定試算表每一分頁的列與寫入呼叫都與換頁之前相同（讀取照常）。"""
    calls = _recorders(monkeypatch)
    at = _go(_app_test(), slug)
    assert calls["load"], "正控：替身確實接在預覽的呼叫路徑上"
    assert calls["save"] == [] and calls["refetch"] == [], calls
    # 先到設定與診斷一次：那一頁自己的讀取（不論會不會在假試算表上留下任何呼叫）算在「換頁之前」，
    # 下面比的只有「再換一次頁」這個動作本身。
    _go(at, "set")
    _go(at, slug)
    before = _book_state(settings_book)
    _go(at, "set")      # 等同按下連結：連結的目的地就是這一頁（上一條已驗 page 與雜湊）
    assert any(s == "set" for s, _a in calls["load"]), calls["load"]
    assert calls["save"] == [] and calls["refetch"] == [], calls
    assert _book_state(settings_book) == before


def test_P0_2_正控_同一組替身之下真的按存檔就記得到_試算表也真的多一列(settings_book, biting, monkeypatch):
    """上一條「0 次、一列未動」不是空掃：同一組替身與同一本假試算表，在設定與診斷真的按存檔，
    替身記到呼叫、試算表多一列。"""
    calls = _recorders(monkeypatch)
    at = _go(_app_test(), "set")
    before = _book_state(settings_book)
    at.text_input(key="live_alo_tolerance_pp").input("99").run()
    _save_set(at)
    assert calls["save"], calls
    assert _book_state(settings_book) != before
    assert _tolerance_rows(settings_book) == [["alo_tolerance_pp", "99", "float"]]


def test_P0_2_寫入用的原文經換頁後在設定與診斷的進階診斷照印(no_secrets, biting):
    """`NOT_CONFIGURED_MESSAGE`（設定試算表那一句，寫入用的訊息被讀取端回報）：一般畫面 0 次、進階診斷 ≥1 次。"""
    from ui_v2 import plain

    at = _go(_app_test(), "mkt")
    assert SET_REPO.NOT_CONFIGURED_MESSAGE not in _main_text(at)
    _go(at, "set")
    diag = [e for e in at.main.expander if e.label == plain.ADVANCED_DIAG_TITLE]
    assert len(diag) == 1
    body = "\n".join(html.unescape(m.value) for m in diag[0].markdown)
    assert body.count(SET_REPO.NOT_CONFIGURED_MESSAGE) >= 1
