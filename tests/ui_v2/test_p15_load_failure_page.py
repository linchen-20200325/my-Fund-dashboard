# -*- coding: utf-8 -*-
"""Phase 3 P1-⑤（BL-0362）：正式模式 `load_live()` 拋例外時的整頁畫面（slow lane；需要 streamlit）。

原本市場總覽、標的探索、資產配置、設定與診斷四頁的 `page.render` 呼叫 `load_live()` 沒有包例外，
正式頁畫出 Streamlit 例外框（本機含完整 Traceback 與訊息原文）。修法比照持倉體檢既有的錯誤畫面：

- 不印 Traceback、不吞：頁名、提問句、一行「⛔ 資料 取數失敗：本頁暫時無法判定」（`plain.plain_error_line` 既有的字），其餘塊不畫；
- 一般畫面不印例外型別與訊息原文；型別與**遮蔽後**的訊息原文收進設定與診斷頁的進階診斷（`plain.record_raw`）；
- 四頁（不含設定與診斷本身）錯誤行下面接「前往設定與診斷」（只換頁；44 第七節第三小節之七其五第 2 條、護欄 3）；
- 設定與診斷頁自己載入失敗：不掛導覽（它就是那一頁），錯誤行下面直接畫進階診斷；下一次載入成功就拿掉那一筆。

預覽入口（真的 `st.navigation`）那一半沿用 `tests/ui_v2/test_preview_page.py` 的接頭與 fixture。
"""

import html
import pathlib
import sys

import pytest

# 整檔標 slow：畫面測試不進 fast lane（守衛：tests/ui_v2/test_ui_v2_lane_guards.py）。
pytestmark = pytest.mark.slow

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_HERE))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

from ui_v2 import health, plain  # noqa: E402

_SECRET = "zz-fake-secret-p15"
_MASK = "‹已遮蔽›"
_MESSAGE = f"上游讀取失敗 token={_SECRET} /srv/app/secret_path.py"
_PLAIN_LINE = plain.plain_error_line("⛔ 取數失敗：x", page="mkt")[0]
_PAGES = ("mkt", "exp", "alo", "set")
_TITLE_CLASS = {"mkt": "mkt-page-title", "exp": "exp-title", "alo": "alo-title", "set": "set-title"}


def _script(slug, mask):
    """`mask`：`"ok"`（遮蔽假秘密值）、`"none"`（不傳遮蔽函式）、`"raises"`（遮蔽函式本身壞了）。"""
    extra = {"set": ", save_live=lambda *a: {}, refetch_live=lambda *a: {}"}.get(slug, ", save_live=lambda *a: {}")
    mask_arg = {
        "ok": f", mask_error=lambda s: s.replace({_SECRET!r}, {_MASK!r})",
        "none": "",
        "raises": ", mask_error=lambda s: 1 / 0",
    }[mask]
    return f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
from ui_v2.{slug} import page

def boom():
    raise RuntimeError({_MESSAGE!r})

page.render(load_live=boom{extra}{mask_arg})
"""


def _run(slug, mask="ok"):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(_script(slug, mask), default_timeout=60)
    at.run()
    return at


def _visible(at) -> str:
    out = [html.unescape(m.value) for m in at.markdown] + [c.value for c in at.caption]
    out += [b.label for b in at.button] + [e.label for e in at.expander]
    return "\n".join(out)


def _outside_diag(at) -> str:
    """進階診斷那一枚展開區**以外**的字（設定與診斷頁的錯誤畫面會畫那一枚，原文本來就該在裡面）。"""
    diag = [m.value for e in at.expander if e.label == plain.ADVANCED_DIAG_TITLE for m in e.markdown]
    return "\n".join(html.unescape(m.value) for m in at.markdown if m.value not in diag) + "\n" + "\n".join(
        c.value for c in at.caption)


def _raw(at, slug) -> list:
    return [e["text"] for e in at.session_state[plain.RAW_STATE][slug]["entries"]]


# ═══════════════════════ 單頁入口：四頁都不再露出例外框 ═══════════════════════


@pytest.mark.parametrize("slug", _PAGES)
def test_load_live拋例外_沒有例外框_畫頁名提問句與一行狀態(slug):
    at = _run(slug)
    assert not at.exception, [e.value for e in at.exception]
    assert not at.code
    md = [m.value for m in at.markdown]
    assert any(f'class="{_TITLE_CLASS[slug]}"' in v for v in md), md
    lines = [v for v in md if 'role="alert"' in v]
    assert len(lines) == 1, lines
    assert html.escape(_PLAIN_LINE, quote=True) in lines[0]
    text = _outside_diag(at)
    for leaked in ("Traceback", "RuntimeError", _SECRET, _MASK, "上游讀取失敗", "/srv/app"):
        assert leaked not in text, (slug, leaked)
    # 其餘塊不畫：沒有段標籤、沒有任何按鈕（存檔、重新取數都沒有）、沒有資料狀態行。
    assert plain.LABEL_LAYER1 not in text and plain.LABEL_LAYER2 not in text
    assert [b.label for b in at.button] == []
    assert 'class="v2-status-line"' not in "\n".join(md)


@pytest.mark.parametrize("slug", _PAGES)
def test_原文經遮蔽才收進進階診斷(slug):
    at = _run(slug)
    raw = _raw(at, slug)
    assert raw == [f"⛔ 取數失敗：RuntimeError：{_MESSAGE.replace(_SECRET, _MASK)}"], raw


def _run_logged(slug, caplog, mask="ok"):
    import logging

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        at = _run(slug, mask)
    records = [r for r in caplog.records if r.levelno == logging.WARNING and r.name.startswith("ui_v2.")]
    return at, records


@pytest.mark.parametrize("slug", _PAGES)
def test_載入失敗寫一筆WARNING_內容經遮蔽(slug, caplog):
    """CLAUDE.md 第三節第三小節：接住例外至少要 log（P1-⑤ 稽核必修：拿掉 log 這條要紅）。"""
    at, records = _run_logged(slug, caplog)
    assert not at.exception, [e.value for e in at.exception]
    assert len(records) == 1, [(r.name, r.getMessage()) for r in records]
    message = records[0].getMessage()
    assert "RuntimeError" in message and _MASK in message, message
    assert _SECRET not in message, message


@pytest.mark.parametrize("slug", _PAGES)
def test_沒有遮蔽函式時_log只有型別_不含假秘密值(slug, caplog):
    at, records = _run_logged(slug, caplog, mask="none")
    assert len(records) == 1, [(r.name, r.getMessage()) for r in records]
    message = records[0].getMessage()
    assert "RuntimeError" in message and _SECRET not in message and "上游讀取失敗" not in message, message


@pytest.mark.parametrize("slug", _PAGES)
@pytest.mark.parametrize("mask", ("none", "raises"))
def test_沒有遮蔽函式或遮蔽壞了_只收型別_不帶訊息(slug, mask):
    at = _run(slug, mask)
    assert not at.exception, [e.value for e in at.exception]
    raw = _raw(at, slug)
    assert raw == ["⛔ 取數失敗：RuntimeError"], raw
    assert _SECRET not in _visible(at)


@pytest.mark.parametrize("slug", ("mkt", "exp", "alo"))
def test_四頁錯誤行下面接前往設定與診斷_單頁入口只寫一行說明(slug):
    at = _run(slug)
    assert [c.value for c in at.caption] == [health.SETTINGS_ELSEWHERE_TEXT]
    assert at.get("page_link") == []


def test_設定與診斷頁自己載入失敗_不掛導覽_錯誤行下面直接畫進階診斷():
    at = _run("set")
    assert at.get("page_link") == [] and health.SETTINGS_ELSEWHERE_TEXT not in [c.value for c in at.caption]
    diag = [e for e in at.expander if e.label == plain.ADVANCED_DIAG_TITLE]
    assert len(diag) == 1
    body = "\n".join(html.unescape(m.value) for m in diag[0].markdown)
    assert "RuntimeError" in body and _MASK in body and _SECRET not in body
    assert plain.PAGE_NAMES["set"] in body


@pytest.mark.parametrize("slug", ("mkt", "exp", "set"))
def test_示範模式傳遮蔽函式_當場炸(slug):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
from ui_v2.{slug} import page
page.render(mask_error=lambda s: s)
""", default_timeout=60)
    at.run()
    assert at.exception and "mask_error" in at.exception[0].value


# ═══════════════════════ 預覽入口（真的 st.navigation）：導覽只換頁、原文到得了設定與診斷 ═══════════════════════

import test_preview_page as PV  # noqa: E402  —— 沿用預覽入口的接頭與 fixture
no_secrets = PV.no_secrets
biting = PV.biting
settings_book = PV.settings_book


def _boom_load(monkeypatch, slug, calls=None):
    # → 2026-10-30 Batch D（`DEC-2026-10-30-02`；有意識的更正，不是漏刪）：預覽的 `alo` 併入合併頁 `ast`，合併頁一次載入配置與持股兩側
    #   （兩側讀同一個 Active Sheet，現實中會一起失敗）；`alo` 這一格因此讓兩個 source 的載入一起拋同一個例外（舊：只換 `alo` 一個）。
    for name in ((slug, "hld") if slug == "alo" else (slug,)):
        source = PV._RECORDED_SOURCES[name]

        def boom(_name=name):
            if calls is not None:
                calls.append(_name)
            raise RuntimeError(_MESSAGE)

        boom.__module__ = source.__name__
        monkeypatch.setattr(source, "load_live", boom)
        monkeypatch.setattr(source, "mask_error", lambda s: s.replace(_SECRET, _MASK))


@pytest.mark.parametrize("slug", ("mkt", "exp", "alo"))
def test_預覽_載入失敗頁的前往設定與診斷是頁面連結_換過去看得到原文(no_secrets, biting, monkeypatch, slug):
    _boom_load(monkeypatch, slug)
    at = PV._go(PV._app_test(), slug)
    links = [e for e in at.get("page_link") if e.proto.label == health.SETTINGS_LINK_LABEL]
    assert len(links) == 1 and links[0].proto.page == "set", [e.proto for e in at.get("page_link")]
    assert "RuntimeError" not in PV._main_text(at) and _SECRET not in PV._main_text(at)
    PV._go(at, "set")
    diag = [e for e in at.main.expander if e.label == plain.ADVANCED_DIAG_TITLE]
    assert len(diag) == 1
    body = "\n".join(html.unescape(m.value) for m in diag[0].markdown)
    assert f"⛔ 取數失敗：RuntimeError：{_MESSAGE.replace(_SECRET, _MASK)}" in body, body
    assert _SECRET not in body and plain.PAGE_NAMES[slug] in body


@pytest.mark.parametrize("slug", ("mkt", "exp", "alo"))
def test_預覽_載入失敗頁換到設定與診斷_save與refetch都是0次_試算表一列未動(settings_book, biting, monkeypatch, slug):
    """護欄 3（44 第七節第三小節之七其五第 4 條的驗法）：錯誤畫面的導覽只換頁。"""
    calls = PV._recorders(monkeypatch)
    _boom_load(monkeypatch, slug)
    at = PV._go(PV._app_test(), slug)
    PV._go(at, "set")
    PV._go(at, slug)
    before = PV._book_state(settings_book)
    PV._go(at, "set")
    assert calls["save"] == [] and calls["refetch"] == [], calls
    assert PV._book_state(settings_book) == before


def test_預覽_設定與診斷先失敗後成功_進階診斷裡那一筆跟著拿掉(no_secrets, biting, monkeypatch):
    source = PV._SOURCES["set"]
    real = source.load_live
    state = {"fail": True}

    def flaky():
        if state["fail"]:
            raise RuntimeError(_MESSAGE)
        return real()

    flaky.__module__ = source.__name__
    monkeypatch.setattr(source, "load_live", flaky)
    monkeypatch.setattr(source, "mask_error", lambda s: s.replace(_SECRET, _MASK))
    at = PV._go(PV._app_test(), "set")
    assert "set" in at.session_state[plain.RAW_STATE]
    assert [b.label for b in at.main.button] == []          # 錯誤畫面：沒有存檔、沒有重新取數
    state["fail"] = False
    PV._go(at, "set")
    assert "set" not in (at.session_state[plain.RAW_STATE] if plain.RAW_STATE in at.session_state else {})
    assert at.main.button, "正控：載入成功時整頁照常畫（有按鈕）"
    diag = [e for e in at.main.expander if e.label == plain.ADVANCED_DIAG_TITLE]
    body = "\n".join(html.unescape(m.value) for m in diag[0].markdown)
    assert "RuntimeError" not in body
