# -*- coding: utf-8 -*-
"""設定與診斷正式模式的執行期測試（slow lane；需要 streamlit）。

依據 docs/v2/49_data_integration_plan.md §4.7 第 4 點（同 test_mkt_live_page.py）：
把 `page` 模組上的 `fixtures` 換成「一存取就拋錯」的替身，再以正式模式呼叫 `page.render(...)`。
正式模式的任何一條路徑讀了 fixtures，這裡就紅；正控：同一個替身之下示範模式必須炸。

另走一條「真 L2 ＋ 真 L1 ＋ 假 gspread」的整合路徑（`ui_v2/set/source.py` 的三個函式），
驗草稿的存檔、重新取數與遮蔽在畫面上的樣子（M11 的 SET-2／SET-6 版）。
"""

import html as _htmlmod
import pathlib
import secrets as _rnd
import sys
import types

import pytest

# 整檔標 slow：畫面測試不進 fast lane（守衛：tests/ui_v2/test_ui_v2_lane_guards.py）。
pytestmark = pytest.mark.slow

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "tests"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

import _set_live_harness as harness  # noqa: E402
from ui_v2.set import live, logic, page  # noqa: E402

source = pytest.importorskip("ui_v2.set.source")

_MARK = "正式路徑碰到 fixtures"

_SCRIPT_LIVE = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
sys.path.insert(0, {str(pathlib.Path(__file__).resolve().parent)!r})
import _set_live_harness as h
from ui_v2.set import page
page.render(**h.LOADERS)
"""

_SCRIPT_DEMO = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
from ui_v2.set import page
page.render()
"""


class _FixturesThatBite:
    def __getattr__(self, name):
        raise RuntimeError(f"{_MARK}：{name}")


def _run(script=_SCRIPT_LIVE):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(script, default_timeout=60)
    at.run()
    return at


def _rendered(at):
    out = [_htmlmod.unescape(e.value) for e in at.markdown] + [e.value for e in at.caption]
    for b in at.button:
        out.append(b.label)
        if b.help:
            out.append(b.help)
    out += [e.label for e in at.expander]
    return out


# ═══════════════════════ 整合環境：真 L2 ＋ 真 L1 ＋ 假 gspread ═══════════════════════

KEY = "k" + _rnd.token_hex(12)
SHEET = "sheet" + _rnd.token_hex(8)


@pytest.fixture
def real(monkeypatch):
    from _fake_settings_sheet import FakeClient, FakeSpreadsheet
    from infra import gspread_retry as GR
    from infra import source_backoff as SB
    from repositories import settings_sheet_repository as R

    class Book(FakeSpreadsheet):
        title = "客戶的設定本"

    book = Book()
    cfg = {"SETTINGS_SHEET_ID": SHEET, "FRED_API_KEY": KEY,
           "google_service_account": {"client_email": "sa@example.iam.gserviceaccount.com"}}
    monkeypatch.setattr(R, "get_secret", lambda key, default=None: cfg.get(key, default))
    monkeypatch.setattr(R, "_make_client", lambda creds: FakeClient(book))
    monkeypatch.setattr(R, "_TITLES", {})
    monkeypatch.setattr(GR.time, "sleep", lambda _s: None)
    monkeypatch.setattr(source, "st", types.SimpleNamespace(secrets=cfg, session_state={}))
    monkeypatch.setattr(source.market_indicator, "source_cooldowns", lambda: [])
    monkeypatch.setattr(page, "fixtures", _FixturesThatBite())
    R.clear_cache()
    SB.reset_all()
    harness.LOADERS.clear()
    harness.LOADERS.update(load_live=source.load_live, save_live=source.save_setting,
                           refetch_live=source.refetch)
    book.cfg = cfg
    yield book
    harness.LOADERS.clear()
    R.clear_cache()
    SB.reset_all()


def _stub_fetch(monkeypatch, series=None, error=None):
    from services.v2_tables import market_indicator as mi
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", lambda ticker, *a, **k: (series, error))


def _vix():
    import pandas as pd
    s = pd.Series([17.0, 18.5], index=pd.to_datetime(["2026-09-22", "2026-09-23"]), dtype=float, name="^VIX")
    s.attrs["fetched_at"] = "2026-09-25T06:00:00+00:00"
    return s


# ═══════════════════════ 正式模式不碰 fixtures ═══════════════════════


def test_正式模式_fixtures一碰就炸的情況下照樣渲染完成(real):
    at = _run()
    assert not at.exception, [e.value for e in at.exception]
    text = "\n".join(_rendered(at))
    assert "設定試算表：客戶的設定本" in text and _MARK not in text


def test_正控_同一個替身之下示範模式必須炸(real):
    at = _run(_SCRIPT_DEMO)
    assert at.exception and _MARK in at.exception[0].value


def test_只傳一部分注入函式_當場炸(real):
    harness.LOADERS.pop("refetch_live")
    at = _run()
    assert at.exception and "refetch_live" in at.exception[0].value


# ═══════════════════════ 草稿逐項 ═══════════════════════


def test_草稿剪1_頁首只留提問句_示意字樣全拿掉(real):
    at = _run()
    sub = [e.value for e in at.markdown if e.value.startswith('<div class="set-sub">')]
    assert sub == ['<div class="set-sub">畫面上的數字現在可不可信，不可信是卡在哪一段</div>']
    text = "\n".join(_rendered(at))
    for demo in ("情境", "示意值", "本頁沒有後端"):
        assert demo not in text, demo


def test_星1至星4星8星10_正常狀態都畫出來(real, monkeypatch):
    _stub_fetch(monkeypatch, _vix())
    source.refetch("市場指標")
    at = _run()
    text = "\n".join(_rendered(at))
    for line in (live.TEXT_PENDING_NAV_DIVIDEND, live.TEXT_LOG_SCOPE, live.TEXT_REASON_KIND_PENDING,
                 live.TEXT_REASON_TIER_PENDING, live.TEXT_MI_TIME_SCOPE, live.TEXT_SET5_NOTE,
                 "設定試算表：客戶的設定本", "資料未備"):
        assert line in text, line
    assert text.count(live.TEXT_LOG_SCOPE) == 3                     # ★3 三處
    assert SHEET not in text and KEY not in text


def test_ID未設_存檔與重新取數都停用_燈照44外框(real):
    real.cfg.pop("SETTINGS_SHEET_ID")
    at = _run()
    assert not at.exception
    text = "\n".join(_rendered(at))
    assert "⛔ 取數失敗：未設定試算表 ID，暫停寫入" in text
    save = [b for b in at.button if b.label == "存檔"][0]
    assert save.disabled and save.help == "未設定試算表 ID，暫停寫入"


def test_存檔_按下後寫進試算表_下一輪畫已存檔_再下一輪消失(real):
    at = _run()
    at.text_input(key="live_set_max_age_days").set_value("21")
    [b for b in at.button if b.label == "存檔"][0].click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert "已存檔" in "\n".join(_rendered(at))
    assert real.data("user_setting_log")[-1][:3] == ["set_max_age_days", "21", "int"]
    at.run()
    assert "已存檔" not in "\n".join(_rendered(at))


def test_存檔_型別不符_不寫_畫型別說明(real):
    at = _run()
    at.text_input(key="live_set_max_age_days").set_value("ninety")
    [b for b in at.button if b.label == "存檔"][0].click()
    at.run()
    text = "\n".join(_rendered(at))
    assert "型別說明：" in text and "已存檔" not in text
    assert "user_setting_log" not in real.tabs


def test_重新取數_淨值停用_市場指標按下後寫紀錄並畫結果行(real, monkeypatch):
    _stub_fetch(monkeypatch, _vix())
    at = _run()
    at.radio(key="live_set5_tier").set_value("淨值").run()
    btn = [b for b in at.button if b.label == "重新取數"][0]
    assert btn.disabled and btn.help == "這一層級的取數尚未接上"
    at.radio(key="live_set5_tier").set_value("市場指標").run()
    btn = [b for b in at.button if b.label == "重新取數"][0]
    assert not btn.disabled
    btn.click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    text = "\n".join(_rendered(at))
    assert "取數完成：市場指標，取回 2 列；結果記在取數紀錄（層 4）" in text
    assert [r[4] for r in real.data("fetch_log")[1:]] == ["ok"]


def test_M11_SET版_取數失敗訊息與fetch_log逐字相同_SET2與SET6下一行加註(real, monkeypatch):
    from services.v2_tables import settings_store as S
    _stub_fetch(monkeypatch, None, f"HTTPSConnectionPool(host='127.0.0.1'): /x?api_key={KEY} refused")
    source.refetch("市場指標")
    stored = S.load_fetch_log([])["rows"][-1]["message"]
    assert KEY not in stored and "‹已遮蔽›" in stored
    at = _run()
    escaped = _htmlmod.escape(stored, quote=True)
    tables = [e.value for e in at.markdown if escaped in e.value]
    assert len(tables) == 2                                          # SET-2 與 SET-6 各一處
    for markup in tables:
        after = markup.split(escaped, 1)[1].removeprefix("</span>")   # SET-2 的訊息格帶紅色 span
        assert after.startswith('<span class="set-raw">已遮蔽憑證</span>')
    assert KEY not in "\n".join(_rendered(at))


# ═══════════════════════ 示範模式回歸 ═══════════════════════


def test_示範模式_沒有任何正式模式文案_示意字樣照舊():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(_ROOT / "ui_v2" / "app_set.py"), default_timeout=60)
    at.run()
    text = "\n".join(_rendered(at))
    assert "資料為假資料" in text and "本頁沒有後端" in text
    for line in (live.TEXT_LOG_SCOPE, live.TEXT_PENDING_NAV_DIVIDEND, live.TEXT_SET5_NOTE, "設定試算表："):
        assert line not in text, line
