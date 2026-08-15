"""tests/test_audit_20260814_batch01.py — 2026-08-14 稽核 第 0+1 批回歸鎖。

本檔守的是**六輪實機稽核**（部署站台 + 本機 clone 逐行核對）抓到的問題。
每一條都必須在「把程式碼改回舊行為」時變紅 —— 依 `PROCESS.md §4`，
產生端修對了但沒有會變紅的測試，等於沒修。

測試策略說明（為什麼有些用 source-inspection）
------------------------------------------------
本批多數修正落在 Streamlit render path 內（`st.session_state` / `st.button`），
單元測試無法在不啟 Streamlit runtime 的情況下驅動。硬要 mock 整個 `st` 反而
會變成「測 mock 不測程式」。因此：
- **純函式** → 直接行為測試（首選）
- **render path** → 讀原始碼比對關鍵字，鎖住「舊寫法不得回來、新寫法必須在」

source-inspection 不是理想解，但它**會在 revert 時變紅**，這是本專案對測試的
最低要求。等日後 render path 抽出純函式，再把對應條目升級成行為測試。
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _code_lines_containing(src: str, needle: str) -> list[str]:
    """回傳含 `needle` 的**程式碼**行（排除純註解行）。

    為什麼一定要排除註解
    --------------------
    本批的修正都在原地留了「原本是 X，為什麼錯」的說明註解。若直接對整份
    原始碼做 `assert X not in src`，那些說明註解會讓測試**恆紅** ——
    2026-08-14 的獨立稽核就是抓到 4 條這樣寫的測試。
    """
    return [ln for ln in src.splitlines()
            if needle in ln and not ln.strip().startswith("#")]


def _read_source(relpath: str) -> str:
    """直接讀檔取原始碼 —— **不 import**。

    `app.py` 的 module body 就是應用程式本體（`st.tabs` + 七個 `render_*_tab()`
    會真的跑一遍，其中 `_update_data_registry()` 會**真的打網路**抓 USDTWD）。
    測試不該為了讀一段字串去啟動整個 app（本專案慣例：測試不打網路）。
    """
    return (_REPO_ROOT / relpath).read_text(encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════
# J1 — 幣別誤判（台幣基金被判 USD → 單位數差 32 倍）
# ══════════════════════════════════════════════════════════════════════════

class TestCurrencyNotFabricated:
    """`ui/helpers/v2_editor.py` 不得在 Sheet 的 currency 欄空白時捏造 USD。

    實機證據（2026-08-14 部署站台）：
      ACDD01「安聯台灣大壩基金-A累積型(台幣)」NAV 324.85 **台幣**，
      被標成 USD → 原幣本金 = 294,904 ÷ 32.112 = 9,183.64
      → 可申購單位數 95.86，而正確值是 294,904 ÷ 324.85 = **907.8**。
      低估 32.1 倍，且讓「FX 曝險摘要」印出「USD 25 檔（100%）」的錯誤警語。
    """

    def test_blank_returns_empty_not_usd(self):
        from ui.helpers.v2_editor import _ccy_from_sheet
        for _blank in ("", "   ", None):
            assert _ccy_from_sheet(_blank) == "", (
                f"空白幣別({_blank!r}) 被填成非空值 —— "
                "下游 checkup/fund_row 的『抓不到就標失敗』守門會因此失效"
            )

    def test_chinese_is_normalized(self):
        """Sheet 填中文「台幣」時要正規化，不能原樣丟給下游當 ISO 碼。"""
        from ui.helpers.v2_editor import _ccy_from_sheet
        assert _ccy_from_sheet("台幣") == "TWD"
        assert _ccy_from_sheet("新台幣") == "TWD"
        assert _ccy_from_sheet("美元") == "USD"

    def test_iso_is_respected(self):
        from ui.helpers.v2_editor import _ccy_from_sheet
        assert _ccy_from_sheet("USD") == "USD"
        assert _ccy_from_sheet(" twd ") == "TWD"

    def test_call_site_uses_helper_not_or_usd(self):
        """`or "USD"` 不得回到 v2_editor —— 那是本 bug 的注入點。"""
        import ui.helpers.v2_editor as _v2
        _src = inspect.getsource(_v2)
        # 允許 docstring 裡引用舊寫法（說明用），只擋真正的程式碼
        _code_lines = [
            ln for ln in _src.splitlines()
            if 'or "USD"' in ln and not ln.strip().startswith("#")
            and "原本" not in ln and "原 " not in ln
        ]
        assert not _code_lines, (
            f"v2_editor 仍有 `or \"USD\"` 的程式碼行：{_code_lines}"
        )


def test_fx_exposure_does_not_default_to_usd():
    """`tab3_portfolio` FX 曝險摘要不得把未知幣別併進 USD。

    原本是 `str(...or "USD").strip().upper() or "USD"`（**雙重** fallback），
    直接造出「組合 100% 為 USD 計價」的假風險警語。
    """
    import ui.tab3_portfolio as _t3
    _src = inspect.getsource(_t3)
    assert '_UNKNOWN_CCY' in _src, "未知幣別桶不見了"
    assert 'str(_pf_fx.get("currency") or "USD")' not in _src, (
        "FX 曝險摘要又把未知幣別預設成 USD"
    )


# ══════════════════════════════════════════════════════════════════════════
# E3 — dividend_safety 的 nav_change 傳錯值
# ══════════════════════════════════════════════════════════════════════════

class TestDividendSafetyNavChange:
    """`nav_change` 必須是**淨值變化**，不是含息報酬。

    `dividend_safety` 只用這個參數驅動一個獨立警語：
        if nav_change < NAV_DROP_WARNING_PCT: "⚠️ 淨值下跌 X%,配息源頭值得確認"
    傳含息報酬的後果與設計目的完全相反 —— 配息愈高，警示愈不可能觸發。
    """

    def test_contract_nav_change_drives_the_warning(self):
        """先鎖住 dividend_safety 的契約本身（純函式，真行為測試）。"""
        from services.portfolio_service import dividend_safety
        from shared.signal_thresholds import NAV_DROP_WARNING_PCT

        _below = NAV_DROP_WARNING_PCT - 1.0   # 明確低於門檻 → 應觸發
        _above = NAV_DROP_WARNING_PCT + 1.0   # 高於門檻 → 不應觸發

        _hit = dividend_safety(total_return=2.0, dividend_yield=8.0,
                               nav_change=_below)
        _miss = dividend_safety(total_return=2.0, dividend_yield=8.0,
                                nav_change=_above)
        assert _hit.get("nav_warning"), (
            "nav_change 低於門檻時未產生 nav_warning —— 契約已改變，"
            "請同步檢查 services/health/dividend.py 的呼叫端"
        )
        assert "淨值下跌" in str(_hit["nav_warning"])
        assert not _miss.get("nav_warning"), "nav_change 高於門檻卻誤觸發警語"

    def test_caller_passes_nav_change_not_total_return(self):
        """呼叫端不得再傳 `nav_change=tr1y`。"""
        import services.health.dividend as _d
        _src = inspect.getsource(_d)
        # 註解裡會引用舊寫法說明修正理由 → 必須排除註解行，否則測試恆紅
        _hits = _code_lines_containing(_src, "nav_change=tr1y")
        assert not _hits, (
            f"又把含息報酬當淨值變化傳給 dividend_safety（{_hits}）—— "
            "會讓「配息愈高、淨值崩跌警示愈不觸發」的反向 bug 復活"
        )
        assert 'nav_change_pct' in _src, "沒有改用 _tr1y_meta 的 nav_change_pct"


# ══════════════════════════════════════════════════════════════════════════
# D4 — 無風險利率不得捏造 4.0
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("relpath", ["app.py", "ui/tab1_macro.py"])
def test_risk_free_rate_not_fabricated(relpath):
    """`FED_RATE.value` 缺值時不可捏造 4%（會流進全站 Sharpe/Sortino）。

    另外原寫法 `None / 100` 會直接 TypeError，且該段不在任何 try 內。
    """
    _src = _read_source(relpath)   # 讀檔不 import（見 _read_source docstring）
    for _bad in ('get("value", 4.0)', 'get("value",4.0)'):
        _hits = _code_lines_containing(_src, _bad)
        assert not _hits, (
            f"{relpath} 仍以 4.0 當 FED_RATE 預設（{_hits}）—— "
            "缺值時會捏造無風險利率並汙染全站風險指標"
        )


# ══════════════════════════════════════════════════════════════════════════
# C3 — T7「目標單位數」死碼
# ══════════════════════════════════════════════════════════════════════════

def test_t7_investment_mode_not_overwritten_in_form():
    """form 內不得無條件把 `_a_new_mode_key` 洗成 "twd"。

    原本 form 外依 selectbox「投入方式」算好的值會被覆寫，導致
    「🎯 目標單位數」兩處分支恆為死碼 —— 使用者選了單位模式，
    畫面仍給「💵 預計投入台幣」。
    """
    import ui.tab3_t7_ledger as _t7
    _src = inspect.getsource(_t7)
    _bad = [ln for ln in _src.splitlines()
            if ln.strip() == '_a_new_mode_key = "twd"']
    assert not _bad, (
        "form 內又出現無條件覆寫 `_a_new_mode_key = \"twd\"` —— "
        "「🎯 目標單位數」會再度變成死選項"
    )
    # 正向：form 外依 selectbox 決定的那段必須還在
    assert '_a_new_mode_disp.startswith' in _src, "投入方式 selectbox 的判定不見了"


# ══════════════════════════════════════════════════════════════════════════
# F1 — 名詞解釋字典必須真的被呼叫（PROCESS.md §4 0-consumer 條款）
# ══════════════════════════════════════════════════════════════════════════

def test_metric_explainer_covers_mdd_and_coverage():
    """`mdd` / `div_coverage` 早就寫在字典裡，卻長期 0 consumer。"""
    from ui.helpers.chart.metric_explainers import METRIC_EXPLAINERS

    for _k in ("mdd", "div_coverage"):
        assert _k in METRIC_EXPLAINERS, f"explainer 字典少了 {_k}"

    import ui.tab2_single_fund as _t2
    _src = inspect.getsource(_t2)
    assert '"mdd"' in _src and '"div_coverage"' in _src, (
        "個基深掘沒有把 mdd / div_coverage 帶進 render_metric_explainer —— "
        "這兩條是本頁對新手最重要的名詞（最多會虧多少 / 配息有沒有吃本金）"
    )


# ══════════════════════════════════════════════════════════════════════════
# E4 / E5 — 假 API 名稱與捏造端點字串
# ══════════════════════════════════════════════════════════════════════════

def test_no_nonexistent_finmind_dataset_name():
    """`TaiwanMacroEconomics` 這個 FinMind dataset **不存在**（v19.342 查證）。"""
    import ui.helpers.io.data_registry as _dr
    _src = inspect.getsource(_dr._update_data_registry)
    _hits = _code_lines_containing(_src, "TaiwanMacroEconomics")
    assert not _hits, (
        f"資料診斷頁又顯示不存在的 FinMind dataset 名稱給使用者：{_hits}"
    )


@pytest.mark.parametrize("modname,bad", [
    ("ui.tab5_data_guard", "yp401000"),
    ("ui.tab5_data_guard", "yp405000"),
    ("ui.tab5_data_guard", "yp407000"),
    ("ui.tab6_manual", "wh06_3"),
    ("ui.tab6_manual", "yp401000"),
])
def test_no_fabricated_endpoint_strings(modname, bad):
    """這些端點字串全 repo 零命中 —— 顯示給使用者等於誤導排查方向。"""
    import importlib
    _mod = importlib.import_module(modname)
    _src = inspect.getsource(_mod)
    # 允許出現在說明修正理由的註解裡
    _hits = [ln for ln in _src.splitlines()
             if bad in ln and not ln.strip().startswith("#")]
    assert not _hits, f"{modname} 仍在顯示捏造端點 {bad}：{_hits}"


def test_holdings_source_not_nav_page():
    """`yp004002` 是 NAV 歷史頁，不是持股頁 —— 比純捏造更誤導。"""
    import ui.helpers.io.data_registry as _dr
    _src = inspect.getsource(_dr._update_data_registry)
    _hits = [ln for ln in _src.splitlines()
             if "yp004002" in ln and not ln.strip().startswith("#")]
    assert not _hits, f"持股來源又指回 NAV 歷史頁：{_hits}"


# ══════════════════════════════════════════════════════════════════════════
# E9 / E10 — 管理室通報
# ══════════════════════════════════════════════════════════════════════════

def test_notify_excludes_load_error_funds():
    """通報觀察集合必須排除抓取失敗的檔。

    `ui/helpers/portfolio/load.py:219-221` 會對失敗的基金寫
    `{"loaded": True, "load_error": ...}`，所以只看 `loaded` 會把失敗檔算進去。
    全 repo 其他 8 個消費端都用 `loaded and not load_error`。
    """
    import ui.tab_manage as _tm
    _src = inspect.getsource(_tm._sec_notify)
    # 正向斷言必須排除註解，否則「程式碼 revert、註解留著」也會綠（半假綠）
    assert _code_lines_containing(_src, "load_error"), (
        "_sec_notify 又只看 loaded —— 抓取失敗的基金會被算進通報觀察集合"
    )


def test_line_status_uses_same_alias_resolution_as_push():
    """LINE 燈號必須與 `push_text` 用同一套別名解析，否則假陰性。

    只設 `LINE_CHANNEL_ACCESS_TOKEN`（GitHub secret 常用）時，
    舊寫法會顯示 🔴「尚未設定」**且短路讓測試按鈕整顆不渲染**。
    """
    import ui.tab_manage as _tm
    _src = inspect.getsource(_tm._sec_notify)
    assert _code_lines_containing(_src, "LINE_CHANNEL_ACCESS_TOKEN"), (
        "LINE 燈號沒有處理別名 → 只設別名時功能正常卻顯示未設定、且不給測試"
    )


def test_notify_preview_does_not_claim_identical_to_nas():
    """不得再宣稱「和 NAS 週報同一套邏輯」—— 實測 6 項差異。"""
    import ui.tab_manage as _tm
    _src = inspect.getsource(_tm)
    _hits = [ln for ln in _src.splitlines()
             if "同一套邏輯" in ln and not ln.strip().startswith("#")]
    assert not _hits, f"又宣稱與 NAS 同一套邏輯：{_hits}"


# ══════════════════════════════════════════════════════════════════════════
# E14 / H1 / H2 / H3 — 指路文案與分頁名 SSOT
# ══════════════════════════════════════════════════════════════════════════

def test_sidebar_uses_tab_label_ssot():
    """sidebar 三處指路不得寫死已不存在的分頁名「Tab3」。"""
    import ui.sidebar as _sb
    _src = inspect.getsource(_sb)
    _hits = _code_lines_containing(_src, "Tab3")
    assert not _hits, f"sidebar 又出現寫死的 Tab3 指路：{_hits}"
    # 鎖真正的產出（`_TAB_PORTFOLIO_SB`），不是鎖「原始碼裡有 tab_label 這個字」
    assert _code_lines_containing(_src, "_TAB_PORTFOLIO_SB"), (
        "sidebar 沒有改吃 story_nav 的分頁名 SSOT"
    )


@pytest.mark.parametrize("relpath,expr,old_title", [
    ("ui/tab3_portfolio.py", "_tab_label_t3('portfolio')", "組合基金管理"),
    ("ui/tab2_single_fund.py", "_tab_label_t2('fund')", "單一基金深度分析"),
])
def test_page_title_matches_tab_label(relpath, expr, old_title):
    """頁面 H1 必須與分頁列同源，否則同一頁兩個名字。

    ⚠️ 不可只斷言 `"tab_label" in src` —— 這兩個檔本來就有
    `render_ai_summary_widget(tab_label=...)` 的 kwarg，那樣寫是**假綠**
    （2026-08-14 獨立稽核抓到）。要鎖就鎖 H1 真正用的那個運算式。
    """
    _src = _read_source(relpath)
    assert expr in _src, f"{relpath} 的頁面 H1 沒有改吃 story_nav SSOT（缺 {expr}）"
    # 舊的寫死標題不得出現在 st.markdown 的 H1（註解/docstring 提及可放行）
    _hits = [ln for ln in _code_lines_containing(_src, old_title)
             if "st.markdown" in ln]
    assert not _hits, f"{relpath} 的 H1 又寫死成「{old_title}」：{_hits}"


@pytest.mark.parametrize("modname", [
    "ui.tab3_t7_ledger", "ui.tab2_single_fund", "ui.tab3_portfolio",
])
def test_no_dead_button_pointers(modname):
    """指路文案不得指向不存在的按鈕。

    「📡 全量抓取」與「📡 從 Sheet 同步」全 repo 都沒有對應按鈕。
    """
    import importlib
    _mod = importlib.import_module(modname)
    _src = inspect.getsource(_mod)
    for _dead in ("全量抓取", "從 Sheet 同步"):
        _hits = [ln for ln in _src.splitlines()
                 if _dead in ln and not ln.strip().startswith("#")]
        assert not _hits, f"{modname} 仍指向不存在的按鈕「{_dead}」：{_hits}"


# ══════════════════════════════════════════════════════════════════════════
# N1 — 連線中斷（rerun 成本）
# ══════════════════════════════════════════════════════════════════════════

def test_portfolio_health_is_cached():
    """持倉健診不得每次 rerun 都重跑 ThreadPool。

    實機證據：25 檔持倉下，rerun 起算 17 秒後 `WebSocket onclose`。
    """
    import ui.tab3_portfolio as _t3
    _src = inspect.getsource(_t3)
    assert "_pf_health_cache" in _src, "持倉健診沒有快取 —— 每次互動都會重跑 25 檔"
    assert "_pf_health_fingerprint" in _src, "沒有持倉指紋，無法判斷該不該重算"
    assert "pf_health_recalc" in _src, "沒有提供顯式的「重新計算」出口"


def test_tab3_ai_snapshot_is_memoized():
    """AI 快照不得在使用者按下 AI 按鈕之前、且每次 rerun 都重算。

    它內含 `fetch_usdtwd_frame`、逐檔 `compute_max_drawdown`、相關性矩陣、
    每個幣別一次 `get_latest_fx` —— 全是網路 / O(N) 成本。
    """
    import ui.tab3_portfolio as _t3
    _src = inspect.getsource(_t3._render_tab3_ai_summary)
    assert "_tab3_ai_snap" in _src, "AI 快照沒有記憶化"


def test_phase3b_backtest_is_button_gated():
    """60 月 expanding window 回測不得無條件執行。

    `st.expander` 收合不會阻止 body 執行，而 `st.tabs` 單次 run 會渲染全部分頁。
    """
    import ui.tab5_data_guard as _t5
    _src = inspect.getsource(_t5.render_data_guard_tab)
    assert "btn_d5_p3b" in _src, "Phase 3-B 回測沒有改成按鈕觸發"


def test_nav_history_status_is_cached():
    """兩支 Google Sheets 查詢必須走快取（原本每次 rerun 各打一次）。"""
    import ui.tab5_data_guard as _t5
    _src = inspect.getsource(_t5)
    assert "_cached_nh_status" in _src and "_cached_nh_coverage" in _src, (
        "nav_history 狀態查詢沒有快取 —— 每次互動都會讀兩次 Google Sheets"
    )
    assert "_clear_nh_caches" in _src, (
        "沒有在匯入寫入後清快取 → 會顯示寫入前的累積點數"
    )


def test_data_registry_does_not_store_full_series():
    """registry 只保留抽查用的最新幾筆，不存完整 Series。"""
    import ui.helpers.io.data_registry as _dr
    _src = inspect.getsource(_dr)
    assert "_SNAP_HEAD_N" in _src, "registry 又把完整 Series 塞進 session_state"
    _src_fn = inspect.getsource(_dr._update_data_registry)
    assert "head(_SNAP_HEAD_N)" in _src_fn, "沒有截斷 Series"


# ══════════════════════════════════════════════════════════════════════════
# 第二輪獨立稽核 觀察 C：P1/P2 三項「有修但沒鎖」，依本檔 docstring 標準補上
# ══════════════════════════════════════════════════════════════════════════

def test_phase3b_failure_is_not_disguised_as_not_run():
    """Phase 3-B 失敗不得被偽裝成「尚未執行」（§1 掩蓋問題 = 違憲）。

    我在第一版把失敗存成 `None`，而 `None` 正是「尚未執行」的 sentinel ——
    下一輪 rerun 就會印「⬜ 尚未執行 —— 按上方按鈕才會計算」，
    使用者永遠不知道它其實算爆了。三態必須可區分。
    """
    _src = _read_source("ui/tab5_data_guard.py")
    assert _code_lines_containing(_src, '"_error"'), (
        "Phase 3-B 失敗沒有存成可辨識的 error sentinel"
    )
    # 失敗分支不得再把 None 當成失敗態寫回
    _bad = [ln for ln in _code_lines_containing(_src, '_d5_p3b_out"] = None')]
    assert not _bad, f"失敗又被存成 None（會偽裝成「尚未執行」）：{_bad}"


def test_snapshot_viewer_head_count_uses_ssot():
    """Snapshot Viewer 的筆數不得手抄 —— 必須吃 `_SNAP_HEAD_N`。

    原本 selectbox 標籤、`.head(5)`、caption 文案各寫死一次「5」，
    改常數不會連動（§3.3 的第二份真相）。
    """
    _src = _read_source("ui/tab5_data_guard.py")
    assert _code_lines_containing(_src, "head(_SNAP_N)"), (
        "Snapshot Viewer 又寫死 head(5)"
    )
    _hard = [ln for ln in _code_lines_containing(_src, ".head(5)")]
    assert not _hard, f"仍有手抄的 .head(5)：{_hard}"


def test_ai_snapshot_fingerprint_covers_all_inputs():
    """AI 快照指紋必須涵蓋所有會改變 snapshot 內容的輸入。

    漏掉的話：使用者調了核心目標 % 或改了 v2 編輯器的配息拆分欄位，
    指紋不變 → AI 拿**舊快照**講話，而畫面上沒有任何提示。
    （這比持倉健診嚴重，因為 AI 區沒有「重新計算」的出口。）
    """
    import ui.tab3_portfolio as _t3
    _src = inspect.getsource(_t3._render_tab3_ai_summary)
    for _need in ("portfolio_core_pct", "_v2_buf"):
        assert _code_lines_containing(_src, _need), (
            f"AI 快照指紋沒有涵蓋 {_need} —— 改它之後 AI 會用舊資料講話"
        )


def test_fx_exposure_failure_logs_to_stderr():
    """FX 曝險是風險揭露，失敗必須寫 stderr。

    Streamlit Cloud 的 log 面板只顯示 stderr，走 stdout 的 print 撈不到。
    """
    import ui.tab3_portfolio as _t3
    _src = inspect.getsource(_t3)
    _blk = [ln for ln in _src.splitlines() if "FX 曝險摘要] 渲染失敗" in ln]
    assert _blk, "FX 曝險失敗的 log 不見了"
    # 該 print 必須帶 stderr（同一段落內）
    _idx = _src.splitlines().index(_blk[0])
    _window = "\n".join(_src.splitlines()[_idx:_idx + 3])
    assert "stderr" in _window, (
        "FX 曝險失敗仍走 stdout —— Streamlit Cloud log 撈不到"
    )
