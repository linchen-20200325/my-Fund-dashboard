# -*- coding: utf-8 -*-
"""批 3b-4：hld／alo 只讀個人 Active Sheet 的畫面端（`ui_v2/active_gate.py`＋兩頁 source／page 接線）。

快速部分：字面與 code 對照、source 對失敗碼的對應。slow 部分（AppTest，需要 streamlit）：
沒有 Active ＝ 明確的「⬜ 尚未選定持倉資料來源」＋前往設定，**不是** 0／中性／空持倉／HOLD，且不碰 `POLICY_SHEET_ID`、服務帳戶、網路。
"""
from __future__ import annotations

import pathlib
import sys
import types

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

pytest.importorskip("pandas")
pytest.importorskip("streamlit")

from repositories import personal_drive_repository as drive  # noqa: E402
from repositories import policy_supplement_repository as sup  # noqa: E402
from shared import ui_v2_error_codes as ec  # noqa: E402
from ui_v2 import active_gate  # noqa: E402

_PAGES = ("hld", "alo")


# ═══════════════════════ 字面與 code ═══════════════════════

def test_字面_取自J13畫面路徑():
    assert active_gate.TEXT_NO_ACTIVE == "⬜ 尚未選定持倉資料來源"
    assert "⚙️ 設定" in active_gate.LINK_LABEL


def test_九code_各有去處_沒有新增code():
    nine = set(ec.ALL_ERROR_CODES)
    assert len(nine) == 9
    assert active_gate.NO_ACTIVE_CODES <= nine
    assert set(active_gate.FAILURE_TEXT) <= nine
    assert not (active_gate.NO_ACTIVE_CODES & set(active_gate.FAILURE_TEXT))
    # 九個裡沒有明確字面的（AUTH_STATE_INVALID）走預設句；未知 code 也走預設句，不當成沒有 Active、不當成成功
    rest = nine - active_gate.NO_ACTIVE_CODES - set(active_gate.FAILURE_TEXT)
    assert rest == {ec.AUTH_STATE_INVALID}
    for code in rest | {"NOT_A_CODE"}:
        assert active_gate.failure_text(code) == active_gate.FAILURE_TEXT_DEFAULT
        assert not active_gate.is_no_active(code)


def test_失敗字面_與L1安全訊息逐字一致():
    for code, text in active_gate.FAILURE_TEXT.items():
        assert text == drive._SAFE_MESSAGES[code], code


# ═══════════════════════ source 對應 ═══════════════════════

_SECRET = "zz-fake-secret-3b4"


def _hld_source(monkeypatch, exc):
    from ui_v2.hld import source

    monkeypatch.setattr(source, "st", types.SimpleNamespace(secrets={}, session_state={}))

    def fail(_state, _values):
        raise exc
    monkeypatch.setattr(source.alo_holdings, "load_alo_tables_active", fail)
    monkeypatch.setattr(source.settings_store, "load_user_settings",
                        lambda values: {"rows": {}, "broken_keys": [], "tab_missing": False, "bad_rows": []})
    return source


def _alo_source(monkeypatch, exc):
    from ui_v2.alo import source

    monkeypatch.setattr(source, "st", types.SimpleNamespace(secrets={}, session_state={}))

    def fail(_state, _values):
        raise exc
    monkeypatch.setattr(source.alo_holdings, "load_alo_tables_active", fail)
    monkeypatch.setattr(source.settings_store, "load_user_settings",
                        lambda values: {"rows": {}, "broken_keys": [], "tab_missing": False, "bad_rows": []})
    monkeypatch.setattr(source.settings_store, "load_market_indicator", lambda values: {"rows": []})
    return source


@pytest.fixture(params=_PAGES)
def build_source(request, monkeypatch):
    make = _hld_source if request.param == "hld" else _alo_source
    return request.param, lambda exc: make(monkeypatch, exc)


@pytest.mark.parametrize("code", sorted(active_gate.NO_ACTIVE_CODES))
def test_沒有Active_source拋NoActiveSource_不是錯誤_不退回舊路徑(build_source, code):
    from services.v2_tables import alo_holdings

    _page, make = build_source
    reason = active_gate.REASON_NO_ACTIVE if code == "UNAVAILABLE" else None   # UNAVAILABLE 要帶「沒有 Active」的 reason
    source = make(alo_holdings.ActiveSourceError(code, reason))
    with pytest.raises(active_gate.NoActiveSource) as e:
        source.load_live()
    assert e.value.code == code and e.value.__suppress_context__ is True


def test_reason字面_與L2橋接一致():
    from services.v2_tables import personal_session as ps

    assert active_gate.REASON_NO_ACTIVE == ps.REASON_NO_ACTIVE


@pytest.mark.parametrize("reason", [None, "deploy_config", "something_else"])
def test_UNAVAILABLE非沒有Active的原因_不是未選定畫面_走既有失敗路徑(build_source, reason):
    # F3：UNAVAILABLE 身兼數職。只有 reason＝no_active 才畫「尚未選定持倉資料來源」；
    # 部署設定缺等其他原因走既有持倉讀取失敗路徑（FAILURE_TEXT_DEFAULT），不把 Error 混成 Missing。
    from services.v2_tables import alo_holdings

    page, make = build_source
    assert not active_gate.is_no_active("UNAVAILABLE", reason)
    source = make(alo_holdings.ActiveSourceError("UNAVAILABLE", reason))
    out = source.load_live()
    errors = out["dataset"]["errors"]
    assert errors["holding"] == active_gate.FAILURE_TEXT_DEFAULT
    if page == "alo":
        assert errors["policy"] == active_gate.FAILURE_TEXT_DEFAULT
    assert out["dataset"]["holding"] == []


def test_is_no_active_只有真的沒有Active才是():
    assert active_gate.is_no_active("AUTH_REQUIRED")
    assert active_gate.is_no_active("UNAVAILABLE", active_gate.REASON_NO_ACTIVE)
    assert not active_gate.is_no_active("UNAVAILABLE")
    assert not active_gate.is_no_active("UNAVAILABLE", "deploy_config")
    assert not active_gate.is_no_active("AUTH_EXPIRED", active_gate.REASON_NO_ACTIVE)


@pytest.mark.parametrize("code", sorted(set(active_gate.FAILURE_TEXT) | {ec.AUTH_STATE_INVALID}))
def test_其餘失敗碼_走既有持倉讀取失敗路徑_訊息是固定字面(build_source, code):
    from services.v2_tables import alo_holdings

    page, make = build_source
    source = make(alo_holdings.ActiveSourceError(code))
    out = source.load_live()
    errors = out["dataset"]["errors"]
    assert errors["holding"] == active_gate.failure_text(code)
    if page == "alo":
        assert errors["policy"] == active_gate.failure_text(code)
    assert out["dataset"]["holding"] == []   # 讀不到不是 0 列正常資料；錯誤訊息並存，畫面走既有失敗畫法


@pytest.mark.parametrize("reason", sorted(active_gate.SCHEMA_REASON_TEXT))
def test_SCHEMA_INVALID細分原因_各有固定句_不帶儲存格原文(build_source, reason):
    from services.v2_tables import alo_holdings

    page, make = build_source
    source = make(alo_holdings.ActiveSourceError(ec.SCHEMA_INVALID, reason, "_持倉補充"))
    errors = source.load_live()["dataset"]["errors"]
    assert errors["holding"] == active_gate.SCHEMA_REASON_TEXT[reason] == active_gate.failure_text(ec.SCHEMA_INVALID, reason)


def test_全部保單分頁標頭壞_不說缺少保單分頁():
    assert "缺少保單分頁" not in active_gate.failure_text(ec.SCHEMA_INVALID, "policy_header")
    assert "缺少保單分頁" in active_gate.failure_text(ec.SCHEMA_INVALID, "no_policy_tab")
    assert active_gate.failure_text(ec.SCHEMA_INVALID) == active_gate.FAILURE_TEXT["SCHEMA_INVALID"]
    assert active_gate.failure_text(ec.UPSTREAM_ERROR, "policy_header") == active_gate.FAILURE_TEXT["UPSTREAM_ERROR"]


# ═══════════════════════ AppTest：沒有 Active 的畫面（正式入口，真的 L2） ═══════════════════════

@pytest.mark.slow
@pytest.mark.parametrize("entry", ["app_hld_live.py", "app_alo_live.py"])
def test_沒有Active_畫面是尚未選定_不碰POLICY_SHEET_ID_服務帳戶_網路(monkeypatch, entry):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("POLICY_SHEET_ID", "ENV_POLICY_SHEET_SENTINEL")
    touched = []

    def boom(name):
        def fn(*a, **k):
            touched.append(name)
            raise AssertionError(f"沒有 Active 時不得碰 {name}")
        return fn

    for name in ("policy_sheet_id", "_service_account", "_make_client", "get_secret",
                 "load_policy_holding_rows", "load_supplement_tabs"):
        monkeypatch.setattr(sup, name, boom(name))
    monkeypatch.setattr(drive.requests, "get", boom("requests.get"))

    at = AppTest.from_file(str(_ROOT / "ui_v2" / entry), default_timeout=60)
    at.run()
    assert touched == []
    assert len(at.exception) == 0, [x.value for x in at.exception]
    md = "\n".join(m.value for m in at.markdown) + "\n".join(c.value for c in at.caption)
    assert active_gate.TEXT_NO_ACTIVE in md
    # 不是 0／中性／空持倉（正常）／HOLD／錯誤
    for bad in ("HOLD", "取數失敗", "尚未建立任何持倉", "沒有持倉", "Traceback"):
        assert bad not in md, bad
    assert not at.dataframe and not at.table
    # 單頁入口沒有 st.navigation → 只寫一行說明（有 navigation 的預覽入口見下一條）
    assert active_gate.LINK_ELSEWHERE_TEXT in md


@pytest.mark.slow
@pytest.mark.parametrize("slug", _PAGES)
def test_沒有Active_總表記尚未設定_不記取數失敗也不記沒有異常(slug):
    from streamlit.testing.v1 import AppTest

    from ui_v2 import page_health

    entry = {"hld": "app_hld_live.py", "alo": "app_alo_live.py"}[slug]
    at = AppTest.from_file(str(_ROOT / "ui_v2" / entry), default_timeout=60)
    at.run()
    rec = at.session_state[page_health.STATE_KEY][slug]
    assert rec["page_failure"] is None and not rec.get("collect_error")
    assert [(i["kind"], i["key"]) for i in rec["items"]] == [(page_health.KIND_UNCONFIGURED, active_gate.UNCONFIGURED_KEY)]
    # 擋主要原因（值讀不到）：不落在「只影響比較值」（順位 6）
    item = rec["items"][0]
    assert page_health.blocks_main(item) and not page_health.only_compare_unconfigured(rec["items"])
    main = page_health.main_reason(rec["items"])
    assert main == page_health.TEXT_MAIN_UNCONFIGURED.format(key=active_gate.UNCONFIGURED_KEY)
    assert "只影響比較值" not in main


@pytest.mark.slow
@pytest.mark.parametrize("slug", _PAGES)
def test_有settings_page時_畫page_link(slug):
    """`render_no_active` 傳了 settings_page → 一枚 `st.page_link`（只換頁）；原始碼層面釘死用的是 `st.page_link` 與 LINK_LABEL。"""
    import ast

    src = (_ROOT / "ui_v2" / "active_gate.py").read_text(encoding="utf-8")
    calls = [n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "page_link"]
    assert len(calls) == 1 and "LINK_LABEL" in ast.dump(calls[0])
    for rel in (f"ui_v2/{slug}/page.py",):
        text = (_ROOT / rel).read_text(encoding="utf-8")
        assert "active_gate.render_no_active(" in text and "settings_page=settings_page" in text
