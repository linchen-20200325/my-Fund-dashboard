"""Layer 3-A「監控與評分層」稽核修正的回歸鎖(2026-08-14)。

每一條都必須**把 production 改回舊行為就紅**(PROCESS §4)。

涵蓋:
  E13 「試算 vs 真的寫進帳本」不得由 emoji 開頭決定   `ui/tab3_t7_ledger.py`
  E12 表單驗證失敗不得中止整個 script run             同上 + `ui/tab3_portfolio.py`
  E2  「載入成功」全站只有一個定義                     `ui/helpers/session.py`
  D2  跨保單借基金不得捏造 NAV=10.0 / FX=31.0          `ui/tab3_t7_ledger.py`
  D3  寫死的保底匯率必須留痕跡                          同上
  C2  死滑桿(0 consumer)拆除                           `ui/tab_fund_grp_health.py`
  A8  抓不到報價 → 留白,不得同時存在兩種相反語意       同上

⚠️ 本檔全部走 **AST / 純函式**,不啟動 streamlit runtime、不打網路 ——
   `tab3_t7_ledger.py` 的 render 函式有 3000 行且重度依賴 session_state,
   真跑它只會測到 mock 而不是邏輯(PROCESS §4:寧可少測,不可假綠)。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_T7 = _ROOT / "ui" / "tab3_t7_ledger.py"


def _src(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


def _code_lines(text: str) -> list[str]:
    """只留「不是 # 註解」的行。docstring 仍在,需要時另用 AST。"""
    return [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]


# ══════════════════════════════════════════════════════════════════════
# E13 — 落帳目標：試算 vs 真的寫進主帳本
# ══════════════════════════════════════════════════════════════════════
def test_commit_mode_options_come_from_ssot_constant():
    """**改回舊行為必紅** —— 三個 radio 不得各自寫死選項字串。

    舊碼 A/B/C 各寫一份 `options=["💡 暫存為方案…", "✅ 直接套用主帳本"]`,
    再各自 `startswith("💡")` 判斷。那個 💡 是唯一的安全閥:
    任何人為了統一文案把它換成 📝,三處判斷同時翻成 False →
    **使用者按「試算」會直接寫進真實帳本**,而且成功訊息照印。
    """
    from ui.tab3_t7_ledger import (
        T7_COMMIT_APPLY,
        T7_COMMIT_MODE_OPTIONS,
        T7_COMMIT_SCENARIO,
    )

    assert T7_COMMIT_MODE_OPTIONS == [T7_COMMIT_SCENARIO, T7_COMMIT_APPLY]

    _tree = ast.parse(_src("ui/tab3_t7_ledger.py"))
    _radio_opts = []
    for _n in ast.walk(_tree):
        if not isinstance(_n, ast.Call):
            continue
        _f = _n.func
        if not (isinstance(_f, ast.Attribute) and _f.attr == "radio"):
            continue
        for _kw in _n.keywords:
            if _kw.arg == "options":
                _radio_opts.append(_kw.value)
    # 找出「落帳目標」那幾個 radio(options 是 list literal 且含落帳字樣)= 不該存在
    _inline = [
        _o for _o in _radio_opts
        if isinstance(_o, ast.List)
        and any(isinstance(_e, ast.Constant) and "主帳本" in str(_e.value)
                for _e in _o.elts)
    ]
    assert not _inline, (
        f"仍有 {len(_inline)} 個落帳 radio 把選項字串寫死在原地 —— "
        "改文案時判斷邏輯不會跟著改(稽核 E13)")


def test_is_scenario_commit_uses_equality_not_prefix():
    """判定必須是「等於常數」,不是「開頭長什麼樣」。"""
    from ui.tab3_t7_ledger import (
        T7_COMMIT_APPLY,
        T7_COMMIT_SCENARIO,
        is_scenario_commit,
    )

    assert is_scenario_commit(T7_COMMIT_SCENARIO) is True
    assert is_scenario_commit(T7_COMMIT_APPLY) is False
    # 只有 emoji 對、文字不對 → 舊的 startswith 會說 True,現在必須拒絕
    with pytest.raises(ValueError):
        is_scenario_commit("💡 我自己編的選項")


def test_unknown_commit_mode_refuses_to_guess():
    """**§1 核心** —— 認不得的落帳目標不可以默默選一邊。

    選 False(直接套用)= 打錯字就偷偷寫進真實帳本;
    選 True(暫存)= 使用者以為存檔了其實沒有。兩個都會弄壞資料,
    唯一安全的處理是**拋錯讓它在畫面上炸掉**。
    """
    from ui.tab3_t7_ledger import is_scenario_commit

    for _bad in ("", None, "隨便", "📝 暫存為方案（不動主帳本）"):
        with pytest.raises(ValueError):
            is_scenario_commit(_bad)


def test_no_startswith_decides_ledger_write():
    """守門:落帳判定不得再退回 `startswith` 寫法。"""
    _code = "\n".join(_code_lines(_src("ui/tab3_t7_ledger.py")))
    for _bad in ('_a_commit_mode.startswith', '_b_commit_mode.startswith',
                 '_c_commit_mode.startswith'):
        assert _bad not in _code, f"{_bad} 又出現了 —— 落帳判定回到 emoji 前綴(稽核 E13)"


# ══════════════════════════════════════════════════════════════════════
# E12 — 表單驗證失敗不得打空白整個 App
# ══════════════════════════════════════════════════════════════════════
def test_t7_has_no_st_stop_left():
    """**改回舊行為必紅** —— T7 不得再有 `st.stop()`。

    它中止的是整個 script run:連排在 Tab3 之後的「我的管理室」
    「參考 / 診斷」兩個分頁都會一起空白。使用者只是忘了填金額。
    """
    _tree = ast.parse(_src("ui/tab3_t7_ledger.py"))
    _stops = [
        _n for _n in ast.walk(_tree)
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
        and _n.func.attr == "stop"
        and isinstance(_n.func.value, ast.Name) and _n.func.value.id == "st"
    ]
    assert not _stops, (
        f"tab3_t7_ledger.py 仍有 {len(_stops)} 處 st.stop() —— "
        "表單填錯會讓 Tab3 以下所有分頁空白(稽核 E12)")


def test_t7_abort_is_catchable_and_shows_message():
    """`t7_abort` 必須(a) 先讓使用者看到錯誤 (b) 拋得出可攔截的例外。"""
    import ui.tab3_t7_ledger as T

    _shown: list = []
    _orig = T.st.error
    try:
        T.st.error = lambda m, *a, **k: _shown.append(m)
        with pytest.raises(T.T7InputAbort):
            T.t7_abort("❌ 測試用訊息")
    finally:
        T.st.error = _orig
    assert _shown == ["❌ 測試用訊息"], "中止前必須先把原因顯示出來,不可靜默"


def test_caller_catches_t7_abort():
    """0-consumer 條款:例外要有人接,否則等於換一種方式炸整頁。"""
    _tree = ast.parse(_src("ui/tab3_portfolio.py"))
    _caught = [
        _h for _n in ast.walk(_tree) if isinstance(_n, ast.Try)
        for _h in _n.handlers
        if isinstance(_h.type, ast.Name) and _h.type.id == "T7InputAbort"
    ]
    assert _caught, (
        "tab3_portfolio.py 沒有攔 T7InputAbort —— "
        "例外會一路往上炸掉整個 Tab3(比 st.stop() 更糟)")


# ══════════════════════════════════════════════════════════════════════
# E2 — 「載入成功」全站只有一個定義
# ══════════════════════════════════════════════════════════════════════
def test_fund_is_usable_rejects_failed_fetch():
    """**改回舊行為必紅** —— `loaded=True` 但帶 `load_error` 不算成功。

    `ui/helpers/portfolio/load.py` 對抓取失敗的基金寫的就是
    `{"loaded": True, "load_error": "…"}`。只判 `loaded` 會把失敗檔算成成功,
    這是「KPI 說 25 檔、表格只有 8 列」的成因。
    """
    from ui.helpers.session import fund_is_usable, usable_funds

    assert fund_is_usable({"loaded": True}) is True
    assert fund_is_usable({"loaded": True, "load_error": None}) is True
    assert fund_is_usable({"loaded": True, "load_error": "403 被擋"}) is False
    assert fund_is_usable({"loaded": False}) is False
    assert fund_is_usable(None) is False
    assert fund_is_usable("不是 dict") is False

    _funds = [
        {"code": "A", "loaded": True},
        {"code": "B", "loaded": True, "load_error": "抓不到"},
        {"code": "C", "loaded": False},
    ]
    assert [f["code"] for f in usable_funds(_funds)] == ["A"]
    assert usable_funds(None) == []


@pytest.mark.parametrize("relpath,ctx", [
    ("ui/tab3_portfolio.py", "組合 KPI 卡「N 檔」"),
    ("ui/tab3_t7_ledger.py", "T7 帳本可落帳的基金清單"),
    ("ui/helpers/portfolio/concentration.py", "集中度風險分母"),
])
def test_user_facing_counts_use_the_ssot(relpath, ctx):
    """這三處的數字/計算會直接被使用者看到或拿來決策,必須走 SSOT。"""
    _code = "\n".join(_code_lines(_src(relpath)))
    assert ("usable_funds" in _code or "fund_is_usable" in _code), (
        f"{relpath}（{ctx}）未走 SSOT 判定 —— "
        "抓失敗的基金會被算成載入成功(稽核 E2)")


# ══════════════════════════════════════════════════════════════════════
# D2 / D3 — 不得捏造 NAV / FX；填補必須留痕跡
# ══════════════════════════════════════════════════════════════════════
def test_borrow_fund_no_longer_fabricates_nav_and_fx():
    """**改回舊行為必紅** —— 跨保單借基金不得再憑空給 10.0 / 31.0。

    舊碼 `float(_src_f.get("avg_nav") or 10.0)` 與
    `float(_src_f.get("fx_avg") or 31.0)`：來源沒有淨值或匯率就編一個。
    10.0 剛好是基金常見的發行價,看起來特別像真的;
    借過來之後這兩個數字會一路流進單位數、市值、換匯與未實現損益。
    """
    _code = "\n".join(_code_lines(_src("ui/tab3_t7_ledger.py")))
    assert 'or 10.0)' not in _code, "avg_nav 仍有 `or 10.0` 捏造(稽核 D2)"
    assert 'or 31.0)' not in _code, "fx_avg 仍有 `or 31.0` 捏造(稽核 D2)"
    # 正向:必須改成「缺就擋下」
    assert "_blockers" in _code, "沒有阻擋邏輯 —— 缺淨值/匯率仍會被借進來"


def test_fx_fallback_leaves_a_trace():
    """§1:填補必須(1)顯式(2)寫 log(3)帶旗標。舊碼只做到 (1)。"""
    _code = "\n".join(_code_lines(_src("ui/tab3_t7_ledger.py")))
    assert "_FX_FALLBACK[_ccy]" in _code, "測試已與實作脫節,請更新選取條件"
    assert "_t7_fx_fabricated" in _code, (
        "用了寫死的保底匯率卻沒有任何旗標 —— "
        "市值與報酬率建立在猜測上,使用者看不出來(稽核 D3)")
    assert "stderr" in _code, "保底匯率沒有寫 log"


def test_fx_fabricated_flag_is_reset_each_run():
    """旗標必須每輪重設,否則使用者補好匯率後警告還掛著 → 學會忽略它。"""
    _code = "\n".join(_code_lines(_src("ui/tab3_t7_ledger.py")))
    assert 'st.session_state["_t7_fx_fabricated"] = {}' in _code, (
        "旗標沒有每輪重設,會殘留上一輪的結果")


# ══════════════════════════════════════════════════════════════════════
# C2 — 死滑桿拆除
# ══════════════════════════════════════════════════════════════════════
def test_dead_warn_gap_slider_removed():
    """**改回舊行為必紅** —— 「吃本金閾值 %」滑桿對畫面零影響,不該留著。

    它產出的 `div_health_light_🧮` 全 production 0 consumer(只有測試在讀);
    表上真正的「吃本金燈號 (1Y·MK)」走 `check_eating_principal_1y_mk`,
    門檻取自 shared/signal_thresholds,與滑桿無關。
    拖動它,畫面上一個像素都不會變 —— 騙人的控制項比沒有控制項更糟。
    """
    _tree = ast.parse(_src("ui/tab_fund_grp_health.py"))
    _sliders = [
        _n for _n in ast.walk(_tree)
        if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
        and _n.func.attr == "slider"
    ]
    assert not _sliders, "「吃本金閾值 %」滑桿還在(稽核 C2)"


def test_warn_gap_value_comes_from_ssot():
    """拆掉滑桿後下游仍要一個值,不可在 UI 寫死 2.0(§3.3)。"""
    from services.health.dividend_calc import DEFAULT_WARN_GAP_PCT
    from ui.tab_fund_grp_health import _DEFAULT_WARN_GAP

    assert _DEFAULT_WARN_GAP == DEFAULT_WARN_GAP_PCT


# ══════════════════════════════════════════════════════════════════════
# A8 — 抓不到報價：兩處不得再給出相反的答案
# ══════════════════════════════════════════════════════════════════════
def test_summary_no_longer_falls_back_to_cost_basis():
    """**改回舊行為必紅** —— 抓不到報價時不得把市值當成成本。

    舊碼在總表把 `_nav/_fx` 換成 `cost_unit/fx_avg` → 市值 = 成本
    → **損益恆 0、報酬恆 0.00%**(看起來剛好打平);
    而同一份資料在帳本表走 `else 0` → 市值 0 → **報酬 −100%**(看起來賠光)。
    同一個情境兩個相反的答案,兩個都是編的。
    """
    _code = "\n".join(_code_lines(_src("ui/tab3_t7_ledger.py")))
    assert "_nav = _l.position.cost_unit" not in _code, (
        "總表仍把成本基礎當成市值 —— 損益會恆 0(稽核 A8)")
    assert "n_unpriced" in _code, "沒有統計算不出市值的部位,無從揭露"


def test_return_pct_can_be_unknown():
    """分母為 0 時報酬率是**不知道**,不是 0.00%(§1 兩種狀態要分得開)。"""
    _code = "\n".join(_code_lines(_src("ui/tab3_t7_ledger.py")))
    assert '"unrealized_pl_pct": (round(_pl_pct, 2)' in _code, (
        "測試已與實作脫節,請更新選取條件")
    assert "_fmt_ret_pct" in _code, (
        "報酬率可能是 None,但沒有對應的格式化 —— "
        "舊的 f-string 會 TypeError 炸掉整個面板")


def test_unpriced_positions_are_disclosed():
    """排除掉的部位必須講出來,否則使用者只看到總金額莫名少一塊。"""
    _code = "\n".join(_code_lines(_src("ui/tab3_t7_ledger.py")))
    assert "_unpriced_funds" in _code
    assert "⬜ 無今日報價" in _code, "沒有報價的列必須看得出來,不可留空白裝正常"


# ══════════════════════════════════════════════════════════════════════
# A9 — 分到錢卻沒落帳的列必須看得出來
# ══════════════════════════════════════════════════════════════════════
def test_unbooked_rows_are_marked():
    """**改回舊行為必紅** —— 沒落帳的列不得印一個像已配出去的金額。

    舊碼 `"應買 TWD": f"{share_twd:,.0f}"` 無條件執行,而真正的 subscribe
    被 `if share_twd > 0 and _n > 0 and _x > 0` 擋著 ——
    抓不到報價的那一檔在畫面上與成功落帳的一模一樣。
    """
    _code = "\n".join(_code_lines(_src("ui/tab3_t7_ledger.py")))
    assert "_b_skipped" in _code, "沒有收集未落帳的檔(稽核 A9)"
    assert "⛔ 未落帳" in _code, "未落帳的列沒有標記"
    assert '"booked_twd"' in _code, (
        "「本次投入 TWD」仍顯示使用者填的目標金額而非實際落帳金額")
