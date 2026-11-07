# -*- coding: utf-8 -*-
"""全站共用 Navigation Shell 守衛（BL-0536 Shell 批；選型 Route C，見 `docs/v2/80` 第 17 節）。

涵蓋：導覽（五頁、順序、只有已掛載頁可進、未掛載頁可見但不可進、無空殼頁、🤖 不可進）、Status Bar／側欄資料狀態區
（內容只來自既有 health；全取得時不寫「正常」；沒有取得時間寫缺資料、不推估）、更新資料 CTA（本批不可用＋原因）、
Responsive（斷點、頁首導覽與側欄不同時出現、觸控高度、safe-area、無底部 overlay——靜態 CSS 檢查；真實 390／1280 量測見
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


def test_short_label_keys_exist_for_every_page_and_are_approved_in_the_single_ssot():
    """客戶 2026-11-03 裁示第四項：Shell 字樣已正式核准，只住規則表；暫時字樣表不得再有同鍵（不建立第二套字樣表）。"""
    for item in nav.nav_items():
        assert W.is_approved(item.short_key) and item.short_key not in W.PREVIEW_PENDING_WORDING
        assert item.soon_key in rules.APPROVED_WORDING and item.soon_key not in W.PREVIEW_PENDING_WORDING
    assert [W.text(i.short_key) for i in nav.nav_items()] == ["市場", "資產", "找基金", "AI", "設定"]


def test_not_yet_open_label_is_not_open_for_ai_and_under_development_for_the_rest():
    labels = {i.slug: W.text(i.soon_key) for i in nav.nav_items()}
    assert labels == {"mkt": "開發中", "ast": "開發中", "exp": "開發中", "ai": "尚未開放", "set": "開發中"}


# ───────────────────────────── Status Bar／側欄／CTA 的純字串 ─────────────────────────────

def test_status_bar_when_all_primary_data_present_never_says_normal_or_complete():
    from ui_v3.pages import chrome
    html = chrome.status_bar_html(status(), today=date(2026, 11, 3))
    text = re.sub(r"<[^>]+>", " ", html)
    assert "PREVIEW" in text and "更新：14:00" in text
    assert "uv3-chip" not in html and "data-pending-wording" not in html
    assert "正常" not in text and "資料齊" not in text           # rules.entry("ok") 刻意無字
    assert rules.entry("ok").wording is None
    assert "部分" not in text and "缺失" not in text


def test_status_bar_partial_none_and_failed_note():
    from ui_v3.pages import chrome
    partial = re.sub(r"<[^>]+>", " ", chrome.status_bar_html(status(LEVEL_PARTIAL, 3, 5, 0), today=date(2026, 11, 3)))
    assert "部分資料未取得（3／5 項已取得）" in partial and rules.entry("missing").symbol in partial and "取數失敗" not in partial
    failed = re.sub(r"<[^>]+>", " ", chrome.status_bar_html(status(LEVEL_PARTIAL, 3, 5, 2), today=date(2026, 11, 3)))
    assert "其中 2 項取數失敗" in failed
    none = re.sub(r"<[^>]+>", " ", chrome.status_bar_html(status(LEVEL_NONE, 0, 5, 0, fetched=None), today=date(2026, 11, 3)))
    assert "0／5 項已取得" in none and "部分資料未取得" not in none and "主要資料" not in none     # 一項也沒取得：用已核准的計數字樣，不另造句型


def test_missing_fetch_time_shows_missing_text_not_a_guess_and_never_a_chip():
    from ui_v3.pages import chrome
    html = chrome.status_bar_html(status(fetched=None), today=date(2026, 11, 3))
    assert 'data-status-key="missing"' in html and rules.entry("missing").wording in html
    assert "uv3-chip" not in html                                  # 客戶裁示第一項：Status Bar 不放 chip 形式元素（放了就得計入首屏預算）
    assert not re.search(r"\d{2}:\d{2}", html)                   # 沒有取得時間就沒有時間，不補現在時間
    side = chrome.sidebar_status_html(status(fetched=None))
    assert 'data-status-key="missing"' in side and "uv3-chip" not in side


@pytest.mark.parametrize("st", [status(), status(LEVEL_PARTIAL, 3, 5, 0), status(LEVEL_PARTIAL, 3, 5, 2), status(LEVEL_NONE, 0, 5, 0, fetched=None),
                                status(fetched=None)])
def test_shell_chrome_has_no_chip_form_elements_or_core_number_elements(st):
    """客戶 2026-11-03 裁示第一項：Status Bar（與側欄狀態區）若放資料狀態 chip 或核心數字就不能以位於 Shell 排除計數。
    本批的做法是兩處都不放：純文字一行，沒有 `uv3-chip`、沒有 `uv3-evidence`（頁級核心數字元素）。"""
    from ui_v3.pages import chrome
    for html in (chrome.status_bar_html(st, today=date(2026, 11, 3)), chrome.sidebar_status_html(st)):
        assert "uv3-chip" not in html and "uv3-evidence" not in html, html


def test_status_counts_cover_only_the_registered_items_actually_checked_and_never_claim_system_wide_health():
    """客戶裁示第四項：分母必須是明確、已登錄且本次檢查涵蓋的項目；文字不得暗示涵蓋超過實際檢查的五條主要序列。"""
    from ui_v3.adapters import shell_status
    from ui_v3.pages import chrome
    model = _model()
    st = shell_status.from_market_model(model)
    assert st.total == len(model.statuses) == 5            # 分母＝本次檢查涵蓋的已登錄項目（五條主要序列），不是常數、不是全系統
    for level_status in (status(LEVEL_PARTIAL, 3, 5, 2), status(LEVEL_NONE, 0, 5, 0), status()):
        text = re.sub(r"<[^>]+>", " ", chrome.status_bar_html(level_status) + chrome.sidebar_status_html(level_status))
        for overreach in ("全系統", "全站", "整體", "所有資料", "全部資料", "主要資料", "系統健康", "健康度"):
            assert overreach not in text, overreach
    # 負控（記憶體內現編）：model 多一項已登錄項目，分母必須跟著變
    from dataclasses import replace
    bigger = replace(model, statuses=model.statuses + (model.statuses[0],))
    assert shell_status.from_market_model(bigger).total == 6


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
        for html in (chrome.disabled_side_html(item), chrome.disabled_top_html(item)):
            assert 'aria-disabled="true"' in html and "<a " not in html and "href" not in html
            assert W.text(item.soon_key) in html and item.title in html


def test_sidebar_status_block_has_counts_and_full_fetch_time():
    from ui_v3.pages import chrome
    text = re.sub(r"<[^>]+>", " ", chrome.sidebar_status_html(status()))
    assert "5／5 項已取得" in text and "2026-11-03 14:00" in text and "正常" not in text


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

def test_css_switches_between_sidebar_and_top_nav_at_one_breakpoint():
    css = nav.shell_css()
    assert nav.MOBILE_MAX_PX == 768 and nav.TOUCH_MIN_PX == 48 and nav.TOP_NAV_HEIGHT_PX >= nav.TOUCH_MIN_PX
    base, _, mobile = css.partition(f"@media (max-width:{nav.MOBILE_MAX_PX}px)")
    assert mobile, "沒有手機斷點"
    assert f".st-key-{nav.TOP_KEY}" in base
    assert "display:none !important" in base.split(f".st-key-{nav.TOP_KEY}")[1][:80]
    assert 'stSidebar"]' in mobile and "display:none" in mobile
    assert "position:sticky" in mobile and "top:env(safe-area-inset-top)" in mobile
    assert "flex-wrap:nowrap" in mobile and "overflow-x:hidden" in mobile and "width:100%" in mobile
    assert f"height:{nav.TOP_NAV_HEIGHT_PX}px" in mobile and f"min-height:{nav.TOUCH_MIN_PX}px" in mobile
    assert "bottom:0" not in mobile and "position:fixed" not in mobile
    assert "padding-bottom:calc(" not in mobile                    # 不再有底部 overlay 的避讓假空間
    assert "font-weight:700" in css and "text-decoration:underline" in mobile
    assert ":focus-visible" in mobile and "outline:" in mobile
    assert "overflow-x:auto" not in mobile and "overflow-x:scroll" not in mobile
    assert "overflow" not in css.split("<style>")[1].split('[data-testid="stSidebarCollapseButton"]')[0]


def test_top_nav_is_not_a_second_router_and_uses_all_five_approved_labels():
    from ui_v3.pages import chrome
    import inspect

    render_src = inspect.getsource(chrome.render_navigation)
    assert "nav.TOP_KEY" in render_src and "nav.BOTTOM_KEY" not in render_src
    assert "st.page_link" in render_src and "disabled_top_html" in render_src
    assert [W.text(i.short_key) for i in nav.nav_items()] == ["市場", "資產", "找基金", "AI", "設定"]
    assert {i.slug for i in nav.nav_items() if i.available} == {"mkt"}
    assert all(not i.available for i in nav.nav_items() if i.slug != "mkt")
    css = nav.shell_css()
    assert ".st-key-uv3-bottom-nav" not in css
    assert "position:fixed" not in css


def test_sidebar_has_no_collapse_control_and_no_second_nav_on_desktop():
    css = nav.shell_css()
    assert "stSidebarCollapseButton" in css


# ───────────────────────────── 字樣 ─────────────────────────────

def test_shell_wording_lives_only_in_the_rules_table_and_matches_the_client_ruling_verbatim():
    """單一 SSOT：`shell_*` 只在規則表；`preview_wording` 不留任何 Shell 鍵（舊暫擬定義已退役）。逐字出處守衛在 `test_ui_v3_semantics_rules`。"""
    shell_keys = [k for k in rules.APPROVED_WORDING if k.startswith("shell_")]
    assert len(shell_keys) == 19
    assert not [k for k in W.PREVIEW_PENDING_WORDING if k.startswith("shell_")]
    evidence = (Path(__file__).resolve().parents[2] / rules.EVIDENCE_SHELL_RULING).read_text(encoding="utf-8")
    for key in shell_keys:
        item = rules.approved(key)
        assert item.ruling_text in evidence and item.source == rules.SHELL_RULING_SOURCE, key
    # 客戶裁示第四項列舉的整串（順序與分隔照裁示逐字）
    assert "基金投資儀表板／市場、資產、找基金、AI、設定（短標）／開發中／🤖：尚未開放／PREVIEW／Preview｜非正式頁面／更新：{時間}／資料狀態／最後更新時間／更新資料／預覽版尚未開放更新資料／部分資料未取得（{n}／{m} 項已取得）／其中 {n} 項取數失敗／{n}／{m} 項已取得／主要導覽" in evidence


def test_old_provisional_shell_wording_is_banned_everywhere_in_ui_v3_sources():
    """舊暫擬字樣（「部分資料缺失」「項取得」「主要資料缺失」）退役；被禁字串在測試內拼接，不以字面落進任何檔案。"""
    banned = ("部分資料" + "缺失", "項" + "取得）", "} 項" + "取得", "主要資料" + "缺失")
    root = Path(__file__).resolve().parents[2]
    for path in list((root / "ui_v3").rglob("*.py")) + [root / "shared" / "ui_semantics" / "rules.py"]:
        text = path.read_text(encoding="utf-8").replace("項已取得", "")
        assert not [b for b in banned if b in text], (path.name, [b for b in banned if b in text])


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
    # 導覽連結只有 🌍（側欄一個＋頁首一個）；未掛載頁沒有 renderer、沒有 `st.Page`
    links = [e for e in at.get("page_link")] if hasattr(at, "get") else []
    assert len(links) == 2, links
    assert {l.proto.label for l in links} == {"市場與趨勢", "市場"}
    assert [t.value for t in at.title] == ["🌍 市場與趨勢"]


def test_app_status_for_missing_failure_and_not_configured(monkeypatch):
    at = run(monkeypatch, view=dict(tw="missing"))
    assert "部分資料未取得（4／5 項已取得）" in main_text(at) and "取數失敗" not in main_text(at).split('data-shell="status-bar"')[1].split("</div>")[0]
    at = run(monkeypatch, view=dict(us="error"))
    assert "取數失敗" in main_text(at).split('data-shell="status-bar"')[1].split("</div>")[0]
    at = run(monkeypatch, view=dict(tw="missing", us="missing"))
    assert not at.exception and "部分資料未取得" in main_text(at)


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
