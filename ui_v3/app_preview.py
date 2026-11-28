# -*- coding: utf-8 -*-
"""ui_v3（New UI2）獨立 **Preview App** 入口 —— 目前有 🌍 市場與趨勢（BL-0536 rendering 批；客戶 2026-11-03 授權只進 Preview）
與 ⚙️ 設定→資料健康度第一階段（BL-0540 Phase 1A；客戶 2026-11-21 裁示，僅本地 Preview、唯讀、僅市場與利率）、
以及 🔍 找基金的**本地 FAKE 頁**（Gate-M 方案 2a；客戶 2026-11-22 選方案 B，總管 #1296 comment 7073385776 核可唯一例外；頁級＋卡級永久標示 FAKE、不接任何真來源）。

⛔ 這**不是**正式入口：不切正式 Streamlit entrypoint、不 cutover、Old UI 與 `ui_v2` 不在這裡、也不在這裡暴露；
   preview ≠ 正式 App（`DEC-2026-11-02-06`、`DEC-2026-11-03-04`）。本檔不得被 `app.py`、`ui/`、`ui_v2/` 引用
   （守衛：`tests/ui_v3/test_ui_v3_preview_not_formal_guard.py`）；**不得**設為「正式 App」的 main file；
   獨立 Preview App 可使用本檔作 main file（客戶方案 B／P1，2026-11-21，Cloud 建站、部署、OAuth、Secrets 與正式切換另依各自授權）。
⛔ 除下列唯一例外外，不得 import `ui_v3.fixtures`（preview 不得顯示 fake 資料）；唯一例外＝🔍 頁只能在 `_render_exp` 函式內 import `ui_v3.fixtures.exp_lookup_fake`
   （模組層、其他函式、其他檔案、其他 fixtures 模組一律由守衛攔截）；不得 import ui_v2／Old UI。

執行：repo 根目錄 `streamlit run ui_v3/app_preview.py`。`main()` 會把 repo 根目錄補進 `sys.path`（`streamlit run` 只加腳本所在資料夾）。

設計：
- 所有 import（含 streamlit）都在函式內：import 本檔零副作用（只有定義；`main()` 只在 `__main__` 才執行）。
- 只導覽 `shell.registry.registered_pages()` 的頁；沒有已核准並實作的頁 → `PreviewNotReady`（不渲染空殼）；
  登錄為已掛載、卻沒有對應 renderer → `NotImplementedError`（Fail Loud，不畫空殼）。
- 導覽：routing 用 `st.navigation(position="hidden")`，五頁導覽（桌機側欄＋手機頁首 S1 五格）與 Status Bar 由 `pages/chrome.py` 自畫（Shell；`docs/v2/80` 第 17 節）；未掛載的頁可見但不可進、不建空殼。
- 資料：由 `adapters.market_page.load()` 呼叫既有 L2→L1（不新增資料源、不新增 dependency）；FRED 金鑰沿用 `st.secrets`／環境變數 `FRED_API_KEY`。
"""
from __future__ import annotations


def _ensure_repo_root_on_path() -> None:
    import pathlib
    import sys

    root = str(pathlib.Path(__file__).resolve().parents[1])
    if root not in sys.path:
        sys.path.insert(0, root)


def _render_mkt() -> None:
    """🌍 頁：讀 controls → adapter 取數並組 view model → 頁渲染（頁只吃 view model）。"""
    import os

    import streamlit as st

    from ui_v3.adapters import market_page as adapter
    from ui_v3.adapters import shell_status
    from ui_v3.pages import chrome, mkt
    from ui_v3.viewmodels import settings_health

    period, view, rates_key = mkt.selected_controls()
    st.session_state.pop(settings_health.SNAPSHOT_KEY, None)   # 這次若取數失敗，不得留下上一次的快照給 ⚙️ 當成「當次」
    market_view, table = adapter.load([st.secrets, os.environ])
    model = adapter.build_market_page(market_view, table, period=period, primary_view=view, rates_key=rates_key)
    status = shell_status.from_market_model(model)
    # 同一 session 的快照：只存**這次已產生**的逐列狀態（frozen），給 ⚙️ 唯讀讀取；st.session_state 每個使用者 session 各自一份，不進全域 cache。
    st.session_state[settings_health.SNAPSHOT_KEY] = settings_health.HealthSnapshot(tuple(model.statuses), status)
    chrome.render_status(status)   # Status Bar＋側欄資料狀態區＋更新資料 CTA（來源：既有 health）
    mkt.render(model)
    chrome.render_footer()


def _render_set(pages: dict) -> None:
    """⚙️ 頁：只讀同 session 已有的快照（`_render_mkt` 留下的）；**不呼叫 `adapter.load`、不取數**。沒有快照 → 如實顯示尚未評估＋市場入口。"""
    import streamlit as st

    from ui_v3.pages import chrome
    from ui_v3.pages import settings_health as page
    from ui_v3.viewmodels import settings_health

    snapshot = st.session_state.get(settings_health.SNAPSHOT_KEY)
    if snapshot is not None and not isinstance(snapshot, settings_health.HealthSnapshot):
        raise TypeError(f"session 快照型別錯誤：{type(snapshot).__name__}（不猜、不忽略）")
    if snapshot is not None:
        chrome.render_status(snapshot.shell_status)
    page.render(None if snapshot is None else settings_health.build_from_snapshot(snapshot), market_page=pages.get("mkt"))


def _render_exp() -> None:
    """🔍 頁（本地 FAKE）：輸入 → FAKE 假取數函式（`ui_v3.fixtures.exp_lookup_fake`，只在此函式內 import）→ adapter → 頁渲染。

    **不呼叫 `adapter.load`、不取數、不讀寫 ⚙️ 的快照鍵、不畫 🌍 的 Status Bar**；`session_state` 只存經 adapter 淨化後的 ViewModel（`fl_` 前綴鍵）。
    頁級（頁頂橫幅）與卡級（結果卡標籤）都永久標示 FAKE。
    """
    import streamlit as st

    import ui_v3.fixtures.exp_lookup_fake as fake
    from ui_v3.adapters.exp_nav import load_exp_nav
    from ui_v3.adapters.fund_lookup import lookup_fund, not_queried
    from ui_v3.pages import exp_lookup as page
    from ui_v3.viewmodels.exp_nav import ExpNavView
    from ui_v3.viewmodels.fund_lookup import FundLookupView, LookupState

    page.render_css()
    page.render_page_header(fake.demo_codes_hint())
    raw = page.render_form()
    if raw is not None:
        st.session_state[page.KEY_VIEW] = lookup_fund(fake.make_loader(), raw)
        submitted = st.session_state[page.KEY_VIEW]
        # NAV／輔助判定 sibling（A-EXP-NAV-SIBLING-FAKE-1）：只有五欄有結果時才取；判定與格式化在來源層，這裡只傳遞
        st.session_state[page.KEY_NAV] = load_exp_nav(fake.make_nav_loader(), raw) if submitted.state is LookupState.RESULT else None
    view = st.session_state.get(page.KEY_VIEW, not_queried())
    if not isinstance(view, FundLookupView):
        raise TypeError(f"session 的查詢結果型別錯誤：{type(view).__name__}（不猜、不忽略）")
    nav = st.session_state.get(page.KEY_NAV)
    if nav is not None and not isinstance(nav, ExpNavView):
        raise TypeError(f"session 的 NAV 結果型別錯誤：{type(nav).__name__}（不猜、不忽略）")
    page.render_card(view, fake=True, nav=nav)


def _holder_renderer(fn, pages: dict):
    return lambda: fn(pages)


def main() -> None:
    """註冊已掛載的頁並啟動導覽。沒有已掛載的頁 → `PreviewNotReady`。"""
    _ensure_repo_root_on_path()
    import streamlit as st

    from ui_v3.shell.registry import assert_preview_ready

    pages = assert_preview_ready()
    st_pages: dict = {}   # `_render_set` 要連回 🌍 的 st.Page；頁建好後才填，執行時才讀
    renderers = {"mkt": _render_mkt, "exp": _render_exp, "set": _holder_renderer(_render_set, st_pages)}
    missing = [p.slug for p in pages if p.slug not in renderers]
    if missing:
        raise NotImplementedError(f"已掛載的頁沒有 renderer：{missing}（不畫空殼）")
    from ui_v3.pages import chrome

    st.set_page_config(page_title=pages[0].title, page_icon="🌍", layout="wide", initial_sidebar_state="expanded")
    st_pages.update({p.slug: st.Page(renderers[p.slug], title=p.title, url_path=p.slug, default=i == 0) for i, p in enumerate(pages)})
    navigation = st.navigation(list(st_pages.values()), position="hidden")   # routing 只用 Streamlit；導覽畫面由 Shell 自畫
    chrome.render_navigation(st_pages, next((p.slug for p in pages if p.title == navigation.title), None))   # 五頁導覽（側欄＋手機頁首 S1 五格）；未掛載的頁可見但不可進，不建空殼
    navigation.run()


if __name__ == "__main__":
    main()
