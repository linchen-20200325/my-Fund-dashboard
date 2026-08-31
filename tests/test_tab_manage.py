"""📋 我的管理室(ui/tab_manage,v19.433)。

UI 難以單元測,鎖住:回寫前處理純函式、bare-mode 誠實降級、分頁註冊、選股池編輯器
已從換股顧問移除(避免 DuplicateWidgetID)。
"""
from __future__ import annotations

import re
from pathlib import Path

import ui.tab_manage as M

_ROOT = Path(__file__).resolve().parent.parent


def test_today_tw_iso():
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", M._today_tw())


def test_portfolio_section_removed_from_manage():
    """v19.462(user 2026-08-17:帳本已有 + 流程圖 Portfolio 歸配置&帳本):管理室移除

    「投資組合(持倉)」一覽 + 整組回寫 CRUD(`_sec_portfolio` / `_save_policy` /
    `_delete_policy` / `_prepare_write_df` / `_run_fix_and_shrink`),不再於管理室渲染/寫回政策 Sheet。
    """
    for _dead in ("_sec_portfolio", "_save_policy", "_delete_policy",
                  "_prepare_write_df", "_run_fix_and_shrink"):
        assert not hasattr(M, _dead), f"{_dead} 應已移除(投資組合退場管理室)"
    _tm = (_ROOT / "ui" / "tab_manage.py").read_text(encoding="utf-8")
    assert "_sec_portfolio()" not in _tm and "write_policy_v2" not in _tm


def test_policy_client_and_sheet_bare_mode_degrades_not_crash():
    _c, _reason = M._policy_client_and_sheet()
    assert _c is None and isinstance(_reason, str) and "登入" in _reason   # 誠實提示,不崩


def test_manage_tab_registered_in_app():
    """管理室必須真的被掛出去(寫好沒接線 = 沒交付)。

    ⚠️ **2026-08-31 由 WP-F 收斂:七 → 五。有意識的政策變更,不是漏改。**
    (日期 2026-08-31;決策者:**客戶 2026-08-31 拍板的五分頁動線線框**
    `docs/wireframes/fund-wireframe-final.html` §03)

    **舊斷言**(原地保留、加刪除線,不刪)::

        ~~txt = (_ROOT / "app.py").read_text(encoding="utf-8")~~
        ~~assert "from ui.tab_manage import render_manage_tab" in txt~~
        ~~assert "📋 我的管理室" in txt and "with tab_manage:" in txt~~

    **舊斷言的理由仍然成立**:`render_manage_tab` 若沒有任何 caller 就是死碼 ——
    本 repo 反覆出現「算對了沒接出去」,這條就是管理室的接線鎖。

    **被權衡掉的是它假設「接線的人一定是 `app.py`、而且管理室一定是頂層分頁」**:
    七→五之後管理室是「⑤ ⚙️ 設定與診斷」裡的**分區**,由
    `ui/tab_settings_diag.py::_render_maintain_section` lazy import 並呼叫;
    `app.py` 依設計**不再**直接 import 它(留著會讓「app.py 掛了幾個入口」有兩種讀法,
    也很容易被人順手掛回 `st.tabs` 而同一塊畫兩次)。照舊斷言驗,會把**正確的接線
    判成違規**。另,舊斷言第二段寫死「📋 我的管理室」本身就是第二份標籤。

    **改法:驗「接線鏈真的通到 `app.py`」,而不是「`app.py` 自己 import」** ——
    (a) ⑤ 合併頁真的呼叫 `render_manage_tab()`;
    (b) `app.py` 真的掛了 ⑤;
    (c) ⑤ 的分頁名走 `story_nav` SSOT、且 `app.py` 內不得出現該字面值。
    **範圍沒有放寬** —— 三段缺一即紅,且比舊寫法**多驗了中間那一節**。
    """
    import ast as _ast

    _app = (_ROOT / "app.py").read_text(encoding="utf-8")
    _sd = (_ROOT / "ui" / "tab_settings_diag.py").read_text(encoding="utf-8")

    def _calls(src: str, fn: str) -> list:
        """該原始碼裡對 `fn` 的**真實呼叫**（AST），不是字串出現次數。

        ⚠️ **必須用 AST**：`ui/tab_settings_diag.py` 的**模組 docstring 裡就寫著**
        「`render_manage_tab()` 原樣呼叫」，所以 `"render_manage_tab()" in src`
        會被檔案自己的說明文字騙成綠燈。
        **實測（2026-08-31 突變 N3）**：把那一行真正的呼叫換成 `pass`，
        字串版斷言**照樣 GREEN**；改用 AST 後才轉紅。
        （本 session 同型假綠已出現三次：M8 兩棵 AST 樹、f-string 常數、本條。）
        """
        return [n for n in _ast.walk(_ast.parse(src))
                if isinstance(n, _ast.Call)
                and (getattr(n.func, "id", None) == fn
                     or getattr(n.func, "attr", None) == fn)]

    # (a) ⑤ 合併頁 → 管理室
    assert "from ui.tab_manage import render_manage_tab" in _sd, (
        "⑤ 設定與診斷沒有 import 管理室 —— 管理室變成死碼")
    assert _calls(_sd, "render_manage_tab"), "⑤ 只 import 沒呼叫 —— 算對了沒接出去"

    # (b) app.py → ⑤
    assert "from ui.tab_settings_diag import render_settings_diag_tab" in _app
    assert "with tab_settings:" in _app, "app.py 沒有 ⑤ 的 with 區塊"
    assert _calls(_app, "render_settings_diag_tab"), "app.py 只 import 沒呼叫 ⑤"

    # (c) ⑤ 的分頁名吃 SSOT(不得寫死字面值)
    #
    # ⚠️ 比對的是 **AST 的字串常數**,不是原始碼文字 —— `app.py` 的沿革註解本來就
    #    寫著「⑤ ⚙️ 設定與診斷」,用 `in _app` 會被檔案自己的說明文字騙過而誤判違規。
    #    (本條第一版就是這樣紅的;同型假陽性/假陰性在本 repo 已出現多次。)
    import ast as _ast

    from ui.helpers.story_nav import tab_label

    assert '_tab_label("settings")' in _app, "⑤ 的分頁名沒走 story_nav SSOT"
    _live = [n.value for n in _ast.walk(_ast.parse(_app))
             if isinstance(n, _ast.Constant) and isinstance(n.value, str)]
    _hard = [s for s in _live if tab_label("settings") in s]
    assert not _hard, (
        f"app.py 仍有寫死的分頁名字串 {_hard} —— 又出現第二份標籤")


def test_fund_history_section_fully_removed():
    """v19.461(user 2026-08-17「介面不友善→全拿掉」):曾經查過的基金清單整段**完全移除**,

    說明書 + 管理室兩邊都不得再有該 widget / 渲染函式 / 指路 stub(選股池編輯器本身即 watchlist)。
    """
    _t6 = (_ROOT / "ui" / "tab6_manual.py").read_text(encoding="utf-8")
    _tm = (_ROOT / "ui" / "tab_manage.py").read_text(encoding="utf-8")
    # 說明書:無該 widget、無指路 stub
    assert "_fh_add_form" not in _t6 and "_fh_promote_btn" not in _t6
    assert "曾經查過" not in _t6
    # 管理室:整段渲染函式 + widget 都已刪
    assert "def _render_fund_history" not in _tm and "_fh_add_form" not in _tm
    assert "_import_history_to_pool" not in _tm


def test_nav_csv_tool_moved_to_manage():
    """v19.461:🗄️ NAV 歷史資料管理(手動 CSV)由說明書搬到管理室(集中 NAV 補歷史)。"""
    _t6 = (_ROOT / "ui" / "tab6_manual.py").read_text(encoding="utf-8")
    _tm = (_ROOT / "ui" / "tab_manage.py").read_text(encoding="utf-8")
    assert "nav_history_store" not in _t6 and "_nh_upload_csv" not in _t6   # 說明書已移出
    assert "_nh_upload_csv" in _tm and "nav_history_store" in _tm            # 管理室已收入


def test_mk_clock_section_not_rendered():
    """v19.461(user 2026-08-17「這個也移除」):美林時鐘(策略3 景氣時鐘觀測站)不再於 UI 渲染。

    純邏輯 classify_phase + PMI SSOT 常數留在 mk_clock.py(SSOT-lock 測試用),但不得有 render 呼叫。
    """
    _lt = (_ROOT / "ui" / "tab1_macro_longterm.py").read_text(encoding="utf-8")
    _t1 = (_ROOT / "ui" / "tab1_macro.py").read_text(encoding="utf-8")
    assert "render_mk_clock_section" not in _lt   # 呼叫 + import 都已移除
    assert "render_mk_clock_section" not in _t1   # 死 import 也清掉


def test_pool_editor_no_longer_called_in_switch_advisor_section():
    """換股顧問區不得再直接呼叫 _render_pool_editor()(已移到管理室;避免同 run 雙渲染崩)。"""
    txt = (_ROOT / "ui" / "helpers" / "fund_grp_health" / "switch_advisor_section.py").read_text(encoding="utf-8")
    _fn = txt.split("def render_switch_advisor_section")[1]
    assert "_render_pool_editor()" not in _fn
