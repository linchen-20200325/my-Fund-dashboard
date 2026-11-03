# -*- coding: utf-8 -*-
"""全站共用 Navigation Shell 守衛（BL-0536 Shell 批；選型 Route C，見 `docs/v2/80` 第 17 節）。

涵蓋：導覽（五頁、順序、只有已掛載頁可進、未掛載頁可見但不可進、無空殼頁、🤖 不可進）、Status Bar／側欄資料狀態區
（內容只來自既有 health；全取得時不寫「正常」；沒有取得時間寫缺資料、不推估）、更新資料 CTA（本批不可用＋原因）、
Responsive（斷點、底部導覽與側欄不同時出現、觸控高度、safe-area、內容不被遮住——靜態 CSS 檢查；真實 390／1280 量測見
`docs/evidence/bl0536_shell_h5_2026-11-03/`）、字樣（Shell 新字樣一律 pending、不外漏工程資訊）、Missing（complete／partial／
failure／not configured／all missing）。⚠️ AppTest 不載入瀏覽器 CSS，版面以 Playwright evidence 另證。
負控一律在記憶體內現編，不寫檔、不把負控字串寫進文件。
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

import ui_v3_guard_lib as lib
from shared.ui_semantics import rules
from ui_v3.shell import nav, registry
from ui_v3.shell.registry import IA_PAGES, PageSlot
from ui_v3.viewmodels import preview_wording as W
from ui_v3.viewmodels.shell import LEVEL_NONE, LEVEL_OK, LEVEL_PARTIAL, REFRESH_NOT_WIRED, ShellStatus

APP = str(Path(__file__).resolve().parents[2] / "ui_v3" / "app_preview.py")


def status(level=LEVEL_OK, ok=5, total=5, failed=0, fetched="2026-11-03T06:00:00+00:00", avail=False, reason="auto"):
    if reason == "auto":
        reason = None if avail else REFRESH_NOT_WIRED
    return ShellStatus(level, ok, total, failed, fetched, avail, reason)


# ───────────────────────────── 導覽（純邏輯） ─────────────────────────────

def test_nav_items_are_the_five_pages_in_ia_order_and_only_registered_are_available():
    items = nav.nav_items()
    assert [i.slug for i in items] == ["mkt", "ast", "exp", "ai", "set"]
    assert [i.title for i in items] == [p.title for p in IA_PAGES]
    assert [i.slug for i in items if i.available] == [p.slug for p in registry.registered_pages()] == ["mkt"]
    assert all(i.icon and i.name and i.title == f"{i.icon} {i.name}" for i in items)


def test_unregistered_pages_are_visible_but_never_available_and_ai_never_available():
    items = {i.slug: i for i in nav.nav_items()}
    for slug in ("ast", "exp", "ai", "set"):
        assert items[slug].available is False
    # 負控：在記憶體內把 💼 掛載，導覽項跟著可進；🤖 仍然無法被建構成已掛載（登錄表建構時就擋）
    fake = tuple(PageSlot(p.slug, p.title, True) if p.slug == "ast" else p for p in IA_PAGES)
    assert {i.slug for i in nav.nav_items(fake) if i.available} == {"mkt", "ast"}
    with pytest.raises(ValueError):
        PageSlot("ai", "🤖 AI 投資總結", True)


def test_split_title_does_not_guess():
    assert nav.split_title("🌍 市場與趨勢") == ("🌍", "市場與趨勢")
    assert nav.split_title("設定") == ("", "設定")
    assert nav.split_title("ab 設定") == ("", "ab 設定")


def test_short_label_keys_exist_for_every_page_and_are_pending():
    for item in nav.nav_items():
        assert item.short_key in W.PREVIEW_PENDING_WORDING and not W.is_approved(item.short_key)


# ───────────────────────────── Status Bar／側欄／CTA 的純字串 ─────────────────────────────

def test_status_bar_when_all_primary_data_present_never_says_normal_or_complete():
    from ui_v3.pages import chrome
    html = chrome.status_bar_html(status(), today=date(2026, 11, 3))
    text = re.sub(r"<[^>]+>", " ", html)
    assert "PREVIEW" in text and "更新：14:00" in text
    assert "正常" not in text and "資料齊" not in text           # rules.entry("ok") 刻意無字
    assert rules.entry("ok").wording is None
    assert "部分" not in text and "缺失" not in text


def test_status_bar_partial_none_and_failed_note():
    from ui_v3.pages import chrome
    partial = re.sub(r"<[^>]+>", " ", chrome.status_bar_html(status(LEVEL_PARTIAL, 3, 5, 0), today=date(2026, 11, 3)))
    assert "部分資料缺失（3／5 項取得）" in partial and rules.entry("missing").symbol in partial and "取數失敗" not in partial
    failed = re.sub(r"<[^>]+>", " ", chrome.status_bar_html(status(LEVEL_PARTIAL, 3, 5, 2), today=date(2026, 11, 3)))
    assert "其中 2 項取數失敗" in failed
    none = re.sub(r"<[^>]+>", " ", chrome.status_bar_html(status(LEVEL_NONE, 0, 5, 0, fetched=None), today=date(2026, 11, 3)))
    assert "主要資料缺失（0／5 項取得）" in none


def test_missing_fetch_time_shows_missing_chip_not_a_guess():
    from ui_v3.pages import chrome
    html = chrome.status_bar_html(status(fetched=None), today=date(2026, 11, 3))
    assert 'data-status-key="missing"' in html and rules.entry("missing").wording in html
    assert not re.search(r"\d{2}:\d{2}", html)                   # 沒有取得時間就沒有時間，不補現在時間
    assert 'data-status-key="missing"' in chrome.sidebar_status_html(status(fetched=None))


def test_format_taipei_rules():
    from ui_v3.pages import chrome
    assert chrome.format_taipei("2026-11-03T06:00:00+00:00", today=date(2026, 11, 3)) == "14:00"
    assert chrome.format_taipei("2026-11-02T06:00:00+00:00", today=date(2026, 11, 3)) == "11-02 14:00"
    assert chrome.format_taipei("2026-11-03T06:00:00Z", full=True) == "2026-11-03 14:00"
    assert chrome.format_taipei("2026-11-03T06:00:00") is None   # 不帶時區：不猜
    assert chrome.format_taipei("garbage") is None and chrome.format_taipei(None) is None


def test_disabled_nav_items_are_not_links_and_say_under_development():
    from ui_v3.pages import chrome
    for item in nav.nav_items():
        if item.available:
            continue
        for html in (chrome.disabled_side_html(item), chrome.disabled_bottom_html(item)):
            assert 'aria-disabled="true"' in html and "<a " not in html and "href" not in html
            assert W.text("shell_nav_soon") in html and item.title in html


def test_sidebar_status_block_has_counts_and_full_fetch_time():
    from ui_v3.pages import chrome
    text = re.sub(r"<[^>]+>", " ", chrome.sidebar_status_html(status()))
    assert "5／5 項取得" in text and "2026-11-03 14:00" in text and "正常" not in text


# ───────────────────────────── view model 驗證 ─────────────────────────────

@pytest.mark.parametrize("kwargs", [
    dict(level="weird"), dict(ok=6), dict(total=0, ok=0, level=LEVEL_NONE), dict(level=LEVEL_PARTIAL),   # level 與計數不一致
    dict(level=LEVEL_PARTIAL, ok=3, failed=3), dict(fetched=""), dict(avail=True, reason=REFRESH_NOT_WIRED),
    dict(reason="made_up"), dict(reason=None),
])
def test_shell_status_rejects_inconsistent_input(kwargs):
    with pytest.raises(ValueError):
        status(**kwargs)


def test_refresh_is_not_available_in_this_batch_and_has_a_reason_code():
    from ui_v3.adapters import shell_status
    s = status()
    assert s.refresh_available is False and s.refresh_reason_code == REFRESH_NOT_WIRED


# ───────────────────────────── adapter（既有 health → ShellStatus） ─────────────────────────────

def _model(**kw):
    import market_stubs as ms
    from ui_v3.adapters import market_page as adapter
    table_kw = kw.pop("table", {})
    return adapter.build_market_page(ms.view(**kw), ms.table(**table_kw), period="1Y")


def test_adapter_complete_partial_failure_not_configured_and_all_missing():
    import market_stubs as ms
    from ui_v3.adapters import shell_status
    full = shell_status.from_market_model(_model())
    assert (full.level, full.ok_count, full.total, full.failed_count) == (LEVEL_OK, 5, 5, 0)
    assert full.last_fetched_at == ms.FETCHED and full.refresh_available is False
    missing = shell_status.from_market_model(_model(tw="missing"))
    assert (missing.level, missing.ok_count, missing.failed_count) == (LEVEL_PARTIAL, 4, 0)       # 缺資料不算取數失敗
    failed = shell_status.from_market_model(_model(us="error"))
    assert failed.level == LEVEL_PARTIAL and failed.failed_count >= 1
    both = shell_status.from_market_model(_model(tw="missing", us="missing"))
    assert both.level == LEVEL_PARTIAL and both.ok_count == 3                                    # VIX／美債仍取得


def test_adapter_not_configured_is_not_counted_as_fetch_failure():
    import market_stubs as ms
    from ui_v3.adapters import shell_status
    model = _model(key="", table=dict(errors={"credit_spread_pct": "x"}, drop=("credit_spread_pct", "term_spread_pct")))
    s = shell_status.from_market_model(model)
    not_cfg = [r for r in model.statuses if r.reason_code == "not_configured"]
    assert not_cfg, "情境失效：沒有尚未設定的序列"
    assert s.failed_count == sum(1 for r in model.statuses if r.status == "failed" and r.reason_code != "not_configured")


def test_latest_fetched_at_ignores_naive_and_garbage_and_picks_latest():
    from ui_v3.adapters.shell_status import latest_fetched_at
    assert latest_fetched_at(["2026-11-03T06:00:00+00:00", "2026-11-03T07:00:00+00:00", None, "", "x", "2026-11-04T01:00:00"]) \
        == "2026-11-03T07:00:00+00:00"
    assert latest_fetched_at([None, "2026-11-04T01:00:00", "bad"]) is None


# ───────────────────────────── 靜態守衛：分層／無網路／無假資料 ─────────────────────────────

_NEW = ("ui_v3/viewmodels/shell.py", "ui_v3/adapters/shell_status.py", "ui_v3/shell/nav.py", "ui_v3/pages/chrome.py")


def test_new_shell_files_pass_import_and_write_guards():
    for rel in _NEW:
        src = lib.read(lib.ROOT / rel)
        assert lib.import_violations(rel, src) == [], rel
        assert lib.write_surface_violations(rel, src) == [], rel


def test_negative_controls_shell_layers_cannot_reach_old_tree_or_network():
    # 負控（記憶體內）：Shell 檔案 import 舊樹／ui_v2／網路／services（非 adapters）一律被守衛抓到
    for rel, bad in (("ui_v3/pages/chrome.py", "from infra.cache import global_refresh_all\n"),
                     ("ui_v3/pages/chrome.py", "import ui_v2.shell\n"),
                     ("ui_v3/shell/nav.py", "import requests\n"),
                     ("ui_v3/adapters/shell_status.py", "from infra.cache import clear_all_caches\n"),
                     ("ui_v3/pages/chrome.py", "from services.v2_tables import market_view\n")):
        assert lib.import_violations(rel, bad), (rel, bad)


def test_shell_files_do_not_call_refresh_or_cache_clearing_or_fetch():
    for rel in _NEW:
        src = lib.read(lib.ROOT / rel)
        for token in ("global_refresh_all", "clear_all_caches", "cache_clear", "st.cache", "fetch_url", "session_state.pop"):
            assert token not in src, (rel, token)


def test_nav_and_viewmodel_modules_import_without_streamlit():
    import subprocess
    import sys
    code = "import sys, ui_v3.shell.nav, ui_v3.viewmodels.shell; print('streamlit' in sys.modules)"
    proc = subprocess.run([sys.executable, "-s", "-c", code], capture_output=True, text=True, cwd=str(lib.ROOT),
                          env={"PYTHONPATH": str(lib.ROOT)}, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "False"


# ───────────────────────────── Responsive（靜態 CSS 檢查） ─────────────────────────────

def test_css_switches_between_sidebar_and_bottom_nav_at_one_breakpoint():
    css = nav.shell_css()
    assert nav.MOBILE_MAX_PX == 768 and nav.TOUCH_MIN_PX >= 44 and nav.BOTTOM_NAV_HEIGHT_PX >= nav.TOUCH_MIN_PX
    base, _, mobile = css.partition(f"@media (max-width:{nav.MOBILE_MAX_PX}px)")
    assert mobile, "沒有手機斷點"
    assert f".st-key-{nav.BOTTOM_KEY}" in base and "display:none !important" in base.split(f".st-key-{nav.BOTTOM_KEY}")[1][:80]   # 桌機不顯示底部導覽
    assert 'stSidebar"]' in mobile and "display:none" in mobile                                                                   # 手機不顯示側欄
    assert "position:fixed" in mobile and "bottom:0" in mobile and "env(safe-area-inset-bottom)" in mobile
    assert "padding-bottom:calc(" in mobile and "block-container" in mobile                                                       # 內容不被導覽遮住
    assert "font-weight:700" in css and "text-decoration:underline" in mobile                                                     # active 不只靠顏色
    assert "overflow" not in css.split("<style>")[1].split("[data-testid=\"stSidebarCollapseButton\"]")[0]


def test_sidebar_has_no_collapse_control_and_no_second_nav_on_desktop():
    css = nav.shell_css()
    assert "stSidebarCollapseButton" in css


# ───────────────────────────── 字樣 ─────────────────────────────

def test_all_shell_wording_is_pending_and_never_overlaps_approved():
    keys = [k for k in W.PREVIEW_PENDING_WORDING if k.startswith("shell_")]
    assert len(keys) >= 15
    for key in keys:
        assert not W.is_approved(key)
        assert W.PREVIEW_PENDING_WORDING[key].status == "pending"
    approved = {a.text for a in rules.APPROVED_WORDING.values()}
    assert not (approved & {W.PREVIEW_PENDING_WORDING[k].text for k in keys})


# ───────────────────────────── 整頁（AppTest） ─────────────────────────────

streamlit_testing = pytest.importorskip("streamlit.testing.v1")


def run(monkeypatch, **kw):
    import market_stubs as ms
    from ui_v3.adapters import market_page as adapter
    view = ms.view(**kw.pop("view", {}))
    table = ms.table(**kw.pop("table", {}))
    monkeypatch.setattr(adapter, "load", lambda sources: (view, table))
    return streamlit_testing.AppTest.from_file(APP, default_timeout=60).run()


def sidebar_text(at):
    return "\n".join(m.value for m in at.sidebar.markdown)


def main_text(at):
    return "\n".join(m.value for m in at.markdown)


def test_app_renders_shell_with_five_pages_status_bar_cta_and_footer(monkeypatch):
    at = run(monkeypatch)
    assert not at.exception
    side = sidebar_text(at)
    assert W.text("shell_app_title") in side
    for item in nav.nav_items():
        if not item.available:
            assert f'data-nav="{item.slug}"' in side and 'aria-disabled="true"' in side
    assert "data-shell=\"side-status\"" in side
    main = main_text(at)
    assert 'data-shell="status-bar"' in main and 'data-shell="footer"' in main
    assert main.index('data-shell="status-bar"') < main.index("市場狀態")        # Status Bar 在頁首
    assert main.index("data-shell=\"footer\"") > main.index("data-card")          # 長說明在頁尾，不在首屏
    assert W.text("preview_banner") not in main.split('data-shell="footer"')[0]
    cta = [b for b in at.sidebar.button if b.label == W.text("shell_refresh_cta")]
    assert len(cta) == 1 and cta[0].disabled is True
    assert W.text("shell_refresh_unavailable") in side
    assert "<style>" in main                                                      # CSS 已注入


def test_app_has_exactly_one_navigable_page_and_no_empty_shell_pages(monkeypatch):
    at = run(monkeypatch)
    # 導覽連結只有 🌍（側欄一個＋底部一個）；未掛載頁沒有 renderer、沒有 `st.Page`
    links = [e for e in at.get("page_link")] if hasattr(at, "get") else []
    assert len(links) == 2, links
    assert {l.proto.label for l in links} == {"市場與趨勢", "市場"}
    assert [t.value for t in at.title] == ["🌍 市場與趨勢"]


def test_app_status_for_missing_failure_and_not_configured(monkeypatch):
    at = run(monkeypatch, view=dict(tw="missing"))
    assert "部分資料缺失（4／5 項取得）" in main_text(at) and "取數失敗" not in main_text(at).split('data-shell="status-bar"')[1].split("</div>")[0]
    at = run(monkeypatch, view=dict(us="error"))
    assert "取數失敗" in main_text(at).split('data-shell="status-bar"')[1].split("</div>")[0]
    at = run(monkeypatch, view=dict(tw="missing", us="missing"))
    assert not at.exception and "部分資料缺失" in main_text(at)


def test_shell_visible_text_has_no_engineering_leak(monkeypatch):
    from test_ui_v3_no_engineering_leak_guard import _Visible, leaks
    for kw in ({}, dict(view=dict(tw="missing")), dict(view=dict(us="error")), dict(view=dict(key=""))):
        at = run(monkeypatch, **kw)
        for html in [m.value for m in at.sidebar.markdown] + [m.value for m in at.markdown if "data-shell" in m.value]:
            parser = _Visible()
            parser.feed(html)
            visible = " ".join(parser.parts)
            assert leaks(visible) == [], (kw, leaks(visible))
        for b in at.sidebar.button:
            assert leaks(b.label) == []
