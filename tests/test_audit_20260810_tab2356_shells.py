"""2026-08-10 稽核 Q3 — Tab2 / Tab3 / Tab5 / Tab6 空殼、死讀、圖表命名、SPEC 漂移。

守四件事（每條標「修正前紅不紅」）：

* **B1 空殼** — `expanded=True` 的 expander 對使用者等同「沒有殼」，卻仍多一圈邊框 +
  一個「可以收起來」的假暗示。位置類斷言一律走 **AST**（不掃原始碼字面、不硬編行號）。
* **B3 死讀** — `session_state["compass_data"]` 全 repo 0 writer，餵給 `advise_fund`
  的 VIX 恆為 None → 那條規則長期失效卻無人察覺。改吃 Tab① 寫入的 `indicators`，
  並附 **接線測試**（PROCESS §4）：算出來的 VIX 必須真的被傳進 `advise_fund`。
* **B7 圖表命名** — 資產成長曲線畫的是 `(NAV_t / NAV_0) × invest_twd`，
  既不是投入本金也不是市值；y 軸與末點標註不得再用會被讀成「我現在有多少錢」的字眼。
* **B6 SPEC 漂移** — CFNAI 黃線 / 短線桶標題 / MOVE·PCR 來源欄 / L1 KPI 名稱。

⚠️ 本檔**不**碰 Tab① 與健診相關檔案（其他 Coder 所有權）。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_TAB2 = _ROOT / "ui" / "tab2_single_fund.py"
_TAB3 = _ROOT / "ui" / "tab3_portfolio.py"
_T7 = _ROOT / "ui" / "tab3_t7_ledger.py"
_TAB5 = _ROOT / "ui" / "tab5_data_guard.py"
_TAB6 = _ROOT / "ui" / "tab6_manual.py"
_SPEC = _ROOT / "SPEC.md"


# ══════════════════════════════════════════════════════════════
# 共用 AST 工具（位置類斷言一律走這裡，不做原始碼子字串掃描）
# ══════════════════════════════════════════════════════════════
def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _static_text(node: ast.AST | None) -> str:
    """把 Constant / f-string 的**常數片段**接起來；動態片段以空字串代入。

    用途：expander 標題常寫成 f-string（`f"📋 保單 **{pid}** … {n} 檔基金"`），
    只靠 `ast.Constant` 會整條漏掉。
    """
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else ""
    if isinstance(node, ast.JoinedStr):
        return "".join(
            v.value for v in node.values
            if isinstance(v, ast.Constant) and isinstance(v.value, str)
        )
    return ""


def _expander_calls(path: Path) -> list[tuple[int, str, object]]:
    """回傳檔內所有 `st.expander(...)` 的 (行號, 標題常數片段, expanded 值)。

    `expanded` 未給時回 `None`（Streamlit 預設收合）。
    """
    out: list[tuple[int, str, object]] = []
    for node in ast.walk(_tree(path)):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Attribute) and fn.attr == "expander"):
            continue
        title = _static_text(node.args[0]) if node.args else ""
        expanded: object = None
        for kw in node.keywords:
            if kw.arg == "expanded" and isinstance(kw.value, ast.Constant):
                expanded = kw.value.value
        out.append((node.lineno, title, expanded))
    return out


def _always_open(path: Path) -> list[tuple[int, str]]:
    return [(ln, t) for ln, t, exp in _expander_calls(path) if exp is True]


def _string_constants(path: Path) -> set[str]:
    return {
        n.value for n in ast.walk(_tree(path))
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    }


def _fstring_prefixes(path: Path) -> set[str]:
    """所有 f-string 的**開頭常數片段**（用來驗圖表標註文字，不掃行號）。"""
    out: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.JoinedStr) and node.values:
            head = node.values[0]
            if isinstance(head, ast.Constant) and isinstance(head.value, str):
                out.add(head.value)
    return out


# ══════════════════════════════════════════════════════════════
# B1 — 永遠展開的摺疊殼
# ══════════════════════════════════════════════════════════════
@pytest.mark.parametrize("path", [_TAB2, _TAB5, _TAB6],
                         ids=["tab2", "tab5", "tab6"])
def test_no_always_open_expander(path: Path) -> None:
    """這三個檔不得再有 `expanded=True` 的 expander。

    修正前：**紅**（tab2 三處 / tab5 一處 / tab6 兩處）。
    """
    offenders = _always_open(path)
    assert not offenders, (
        f"{path.name} 仍有永遠展開的摺疊殼（原則 1）："
        + "、".join(f"L{ln}「{t[:24]}」" for ln, t in offenders)
    )


def test_tab3_fx_exposure_summary_has_no_shell() -> None:
    """Tab3「FX 曝險摘要」不得再包在 expander 內（它含 USD 過半的風險警告）。

    修正前：**紅**（該區塊是 `expanded=True` 的 expander）。
    """
    hits = [ln for ln, t, _ in _expander_calls(_TAB3) if "FX 曝險摘要" in t]
    assert not hits, f"FX 曝險摘要仍被 expander 包住於行 {hits}"


def test_tab3_remaining_always_open_expanders_are_known_subset() -> None:
    """Tab3 兩檔剩下的 `expanded=True` 只能是**本輪刻意未動**的兩處分組殼。

    這兩處（保單分組卡片、T7 編輯持倉表單）不在本輪稽核點名清單內，屬「同型未點名」，
    已寫進交付報告等裁決。本測試的作用是**封住新增** —— 之後任何人再加一個
    永遠展開的殼就會紅；把這兩處收掉則仍然綠（子集斷言，不是相等斷言）。

    修正前：**紅**（tab3_portfolio 還多一個 FX 曝險摘要殼）。
    """
    known = ("檔基金", "編輯持倉")
    offenders: list[str] = []
    for path in (_TAB3, _T7):
        for ln, title in _always_open(path):
            if not any(k in title for k in known):
                offenders.append(f"{path.name}:L{ln}「{title[:24]}」")
    assert not offenders, (
        "出現未登記的永遠展開摺疊殼（原則 1）：" + "、".join(offenders)
    )


# ══════════════════════════════════════════════════════════════
# B3 — compass_data 死讀 → 改吃 Tab① indicators
# ══════════════════════════════════════════════════════════════
def test_no_dead_compass_data_read() -> None:
    """Tab3 不得再讀 0 writer 的 session key。

    該 key 的唯一寫入端（總經指南針）已移除 → 讀到的永遠是 None，
    `advise_fund` 吃 VIX 的那條規則等於被靜默停用。

    修正前：**紅**（三處讀取）。
    """
    assert "compass_data" not in _string_constants(_TAB3), (
        "tab3_portfolio 仍在讀取全 repo 0 writer 的 session key"
    )


def _reset_state() -> None:
    """只清本檔用到的兩把 key（沿用既有測試的 `del st.session_state[k]` 手法）。"""
    import streamlit as st
    for k in ("indicators", "_t3_vix_advice_note_shown"):
        if k in st.session_state:
            del st.session_state[k]


def test_vix_helper_returns_none_when_macro_not_loaded() -> None:
    """使用者沒開過 Tab① → 無 indicators → 回 None（§1 不得捏造一個 VIX）。

    修正前：**紅**（helper 不存在 → ImportError）。
    """
    from ui.tab3_portfolio import _vix_for_advice
    _reset_state()
    assert _vix_for_advice(note=False) is None


def test_vix_helper_reads_indicators_value() -> None:
    """有 indicators → 取 `["VIX"]["value"]`，單位為指數點原值（不做任何換算）。

    修正前：**紅**（helper 不存在）。
    """
    import streamlit as st
    from ui.tab3_portfolio import _vix_for_advice
    _reset_state()
    st.session_state["indicators"] = {"VIX": {"name": "VIX 恐慌指數", "value": 27.5}}
    got = _vix_for_advice(note=False)
    assert got == pytest.approx(27.5, abs=1e-9)


@pytest.mark.parametrize("bad", [None, "N/A", "", {}, "查無資料"])
def test_vix_helper_degrades_to_none_on_bad_value(bad) -> None:
    """值缺 / 非數值 → 回 None 讓 advisor 降級，**不得**回 0 或任何預設值。

    0 在 `advise_fund` 裡是合法的「極度平靜」，用它頂替缺值會直接改變建議語意。

    修正前：**紅**（helper 不存在）。
    """
    import streamlit as st
    from ui.tab3_portfolio import _vix_for_advice
    _reset_state()
    st.session_state["indicators"] = {"VIX": {"value": bad}}
    assert _vix_for_advice(note=False) is None


def test_vix_helper_note_path_does_not_raise() -> None:
    """缺值提示路徑（note=True，預設值）本身不得拋例外，且只印一次。

    修正前：**紅**（helper 不存在）。
    """
    from ui.tab3_portfolio import _vix_for_advice
    import streamlit as st
    _reset_state()
    assert _vix_for_advice() is None
    assert st.session_state.get("_t3_vix_advice_note_shown") is True
    assert _vix_for_advice() is None  # 第二次不得再拋


def test_advise_fund_actually_receives_the_helper_value() -> None:
    """**接線測試**（PROCESS §4）：算出來的 VIX 必須真的被傳進 `advise_fund`。

    形狀就是 repo 迄今成本最高的失效模式 —— 「算對了但沒接出去」：
    helper 寫得再正確，只要呼叫端漏傳，畫面上那條規則照樣失效，
    而 lint / 單元測試全部照綠。

    作法：AST 找出所有 `x = _vix_for_advice(...)` 的目標名，再檢查每個
    `advise_fund(...)` 的 vix 參數（第 4 個位置引數或 `vix=`）都是其中之一。

    修正前：**紅**（呼叫端傳的是從 compass_data 死讀出來的變數）。
    """
    tree = _tree(_TAB3)
    produced: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        val = node.value
        if isinstance(val, ast.Call) and isinstance(val.func, ast.Name) \
                and val.func.id == "_vix_for_advice":
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    produced.add(tgt.id)
    assert len(produced) >= 2, (
        f"預期兩處建議計算都改吃同一個 helper，實際取得 {sorted(produced)}"
    )

    consumed: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "advise_fund"):
            continue
        arg = None
        for kw in node.keywords:
            if kw.arg == "vix":
                arg = kw.value
        if arg is None and len(node.args) >= 4:
            arg = node.args[3]
        name = arg.id if isinstance(arg, ast.Name) else repr(arg)
        consumed.append((node.lineno, name))

    assert consumed, "tab3_portfolio 找不到任何 advise_fund 呼叫"
    bad = [f"L{ln}→{n}" for ln, n in consumed if n not in produced]
    assert not bad, (
        f"advise_fund 的 VIX 參數沒接到 helper 產出：{bad}；helper 產出 {sorted(produced)}"
    )


# ══════════════════════════════════════════════════════════════
# B7 — 資產成長曲線的命名誠實化
# ══════════════════════════════════════════════════════════════
def _yaxis_titles(path: Path) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(_tree(path)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr not in ("update_yaxes", "update_layout"):
            continue
        for kw in node.keywords:
            if kw.arg in ("title_text", "yaxis_title"):
                txt = _static_text(kw.value)
                if txt:
                    out.add(txt)
    return out


def test_growth_curve_yaxis_is_not_called_total_assets() -> None:
    """y 軸不得叫「總資產」—— 那條線既不是本金也不是市值。

    它畫的是逐檔 `(NAV_t / NAV_0) × invest_twd` 加總：起點等於投入本金，
    之後只隨淨值相對漲跌縮放，未計入配息 / 實際扣款時點 / 匯率。

    修正前：**紅**（y 軸寫「總資產 (NTD)」）。
    """
    titles = _yaxis_titles(_TAB3)
    bad = [t for t in titles if "總資產" in t]
    assert not bad, f"y 軸仍使用會被讀成「我現在有多少錢」的字眼：{bad}"
    assert any("模擬市值" in t for t in titles), (
        f"預期 y 軸改為誠實名稱，實際的軸標題有：{sorted(titles)}"
    )


def test_growth_curve_last_marker_is_not_labeled_as_cash_on_hand() -> None:
    """曲線末點標註不得只寫「今 …」（最容易被讀成戶頭餘額）。

    修正前：**紅**（末點標 `f"今 {fmt_twd(...)}"`）。
    """
    prefixes = _fstring_prefixes(_TAB3)
    assert "今 " not in prefixes, "曲線末點仍標成「今 …」"
    assert any(p.startswith("今日模擬") for p in prefixes), (
        "預期末點改標為「今日模擬 …」，未找到"
    )


def test_growth_curve_explains_what_it_is_not() -> None:
    """原則 4：曲線下方必須說明它**不是**戶頭現在的錢，且在**同一句話裡**
    列出未計入的三項（配息 / 實際扣款時點 / 匯率）與可核對的真實來源。

    刻意在同一個字串常數內檢查 —— 若只驗這幾個詞出現在整份檔案的任何地方，
    Tab3 到處都在講匯率與配息，這條測試會恆綠、等於沒測。

    修正前：**紅**（只有「怎麼看」一句，沒有任何口徑說明）。
    """
    consts = _string_constants(_TAB3)
    caption = [c for c in consts if "不是你戶頭現在的錢" in c]
    assert caption, "缺少「它不是你戶頭現在的錢」這句最關鍵的否定式說明"
    body = caption[0]
    for kw in ("配息", "扣款", "匯率", "對帳單"):
        assert kw in body, f"曲線口徑說明缺少關鍵字：{kw}"


# ══════════════════════════════════════════════════════════════
# B6 — SPEC.md 與程式碼漂移
# ══════════════════════════════════════════════════════════════
def _spec_text() -> str:
    return _SPEC.read_text(encoding="utf-8")


def _spec_row(prefix: str) -> str:
    for line in _spec_text().splitlines():
        if line.startswith(prefix):
            return line
    raise AssertionError(f"SPEC.md 找不到以 {prefix!r} 開頭的表格列")


def test_spec_cfnai_row_drops_diffusion_index_threshold() -> None:
    """CFNAI 黃線必須是官方零點，不得再寫 Diffusion Index 的那個值。

    `shared/signal_thresholds.py` 對該值明文標註「與 CFNAI 水準值無關，禁止混用」；
    程式端 v19.404 已改吃 `CFNAI_TREND_GROWTH`。文件留著舊值 =
    替同一顆地雷保留復活入口（下一個人會照文件把程式改回去）。

    修正前：**紅**（該列黃線寫 −0.35，來源欄也標 −0.35 警戒）。
    """
    from shared.signal_thresholds import CFNAI_TREND_GROWTH
    row = _spec_row("| CFNAI")
    for bad in ("-0.35", "−0.35"):   # ASCII hyphen 與 U+2212 減號都要擋
        assert bad not in row, f"CFNAI 列仍出現 Diffusion Index 門檻：{row}"
    assert "CFNAI_TREND_GROWTH" in row, f"CFNAI 列未指向 SSOT 常數名：{row}"
    assert CFNAI_TREND_GROWTH == pytest.approx(0.0, abs=1e-12), (
        "SSOT 的 CFNAI 趨勢零點被改動 → SPEC 該列需同步重寫"
    )


def test_spec_short_bucket_heading_follows_ssot_wording() -> None:
    """短線桶的章節標題必須跟著 `BUCKET_META` 的中文用語走。

    2026-08-07 user 拍板把該桶副標從英文行話改成中文，SPEC 沒跟上。

    修正前：**紅**（標題仍寫舊的英文行話版本）。
    """
    from shared.macro_buckets import BUCKET_META
    meta = BUCKET_META["short"]
    want = f"### {meta['emoji']} {meta['title']}（{meta['sub']}）"
    assert want in _spec_text(), f"SPEC 缺少與 SSOT 同源的短線桶標題：{want}"


@pytest.mark.parametrize("prefix", ["| MOVE", "| Put/Call"])
def test_spec_move_pcr_rows_do_not_cite_removed_constants(prefix: str) -> None:
    """這兩列的來源欄不得再指向 `beginner_view` 內**已刪除**的常數。

    指向不存在符號的「來源」比沒有來源更糟 —— 它讓讀者以為有東西在守。

    修正前：**紅**（兩列都寫「對齊 macro_beginner_view._MOVE_WARNING / ._PCR_PANIC」）。
    """
    row = _spec_row(prefix)
    assert "macro_beginner_view" not in row, (
        f"來源欄仍指向已刪除的 beginner_view 常數：{row}"
    )
    assert "macro_buckets" in row, f"來源欄未指向真正定義門檻的 registry：{row}"


def test_spec_l1_kpi_row_says_principal_not_total_assets() -> None:
    """§7 的 L1 KPI 列必須寫「投入本金」——畫面上那顆字卡早已改名。

    修正前：**紅**（該列寫「💰總資產」）。
    """
    row = _spec_row("| L1 總覽級 KPI")
    assert "總資產" not in row, f"L1 KPI 列仍寫「總資產」：{row}"
    assert "投入本金" in row, f"L1 KPI 列未對齊畫面字卡名稱：{row}"
