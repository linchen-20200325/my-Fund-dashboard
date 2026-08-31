"""輪動配對兩元件(2026-08-31 客戶拍板 Q1~Q4)— UI 落點與委派的結構守衛。

線框:`docs/wireframes/rotation-components-wireframe.html`(客戶已拍板,Q1~Q4 照推薦)。

守什麼(全部 AST / sentinel,不用純字串掃 —— docstring 騙不到 Call 節點):
  A. **Q1 位置**:元件 A(🛡️ 持倉互斥避險)在 `_render_health_3tables` 內、
     淘汰候選紅區(business_alert)**之後**、「📊 健診大表」標題**之前**;
     且只在 `source_tab == "health"` 的 ② 健診 Tab 渲染(Tab3 embed 不夾帶)。
  B. **Q3 改型**:③ 批次結果區改呼叫 `render_complementary_explorer_from_df`,
     不再攤開渲染 `render_rotation_section_from_df`;Expander **預設收合**
     (`expanded=False` 必須是字面 False —— 缺 keyword 或動態值都算違規,fail-closed)。
  C. **委派為真**(sentinel):元件 A 真的經 `services.homogeneity` 取得彙整;
     元件 B 真的經 `services.rotation.suggest_rotation_pairs`(SSOT 預設門檻)
     並與 ② 共用同一份表身 `_render_pairs_body`(重新 inline 第二份表 → 紅)。
  D. **§1 誠實**:被剔除檔名單真的被畫出來(拿掉 excluded 渲染 → 紅)。

⚠️ 突變驗證紀錄(2026-08-31,提交前實跑;「拿掉修復必須轉紅」):
  - 把元件 A 呼叫移到「📊 健診大表」標題之後 → test_q1 紅
  - 拿掉 `source_tab == "health"` gate → test_element_a_only_on_health_tab 紅
  - 批次 tab 改回 `render_rotation_section_from_df` → test_q3 紅
  - `st.expander(..., expanded=False)` 改 True / 刪 keyword → test_expander 紅
  - 元件 B 改為自己 inline 一份表(不呼叫 `_render_pairs_body`)→ sentinel 紅
  - 元件 A 拿掉 excluded caption → test_excluded_rendered 紅

已知守不到(誠實列出):跨檔動態 `getattr` 呼叫;把 gate 條件改成恆真
(`== "health" or True`);渲染順序若改以「先存 list 再亂序執行」的間接形式。
"""
from __future__ import annotations

import ast
import pathlib

import numpy as np
import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _parse(rel: str) -> ast.Module:
    return ast.parse((ROOT / rel).read_text(encoding="utf-8"))


def _fn(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"找不到函式 {name} —— 改名請同步本守衛")


def _calls_named(scope: ast.AST, name: str) -> list:
    out = []
    for node in ast.walk(scope):
        if isinstance(node, ast.Call):
            f = node.func
            if (isinstance(f, ast.Name) and f.id == name) or \
               (isinstance(f, ast.Attribute) and f.attr == name):
                out.append(node)
    return out


# ═══════════════════════════════════════════════════════════════════════
# A. Q1 位置 + ② 限定
# ═══════════════════════════════════════════════════════════════════════

_HEALTH = "ui/tab_fund_grp_health.py"


def test_q1_element_a_sits_between_red_zone_and_big_table():
    """淘汰候選(結論摘要)→ 🛡️ 元件 A → 📊 健診大表,順序即客戶拍板的 Q1。"""
    fn = _fn(_parse(_HEALTH), "_render_health_3tables")
    red = _calls_named(fn, "business_alert")
    me = _calls_named(fn, "render_mutual_exclusion_section")
    big = [c for c in _calls_named(fn, "markdown")
           if c.args and isinstance(c.args[0], ast.Constant)
           and isinstance(c.args[0].value, str) and "📊 健診大表" in c.args[0].value]
    assert red, "淘汰候選紅區(business_alert)不見了 —— Q1 的錨點消失,請同步線框與本守衛"
    assert me, "元件 A(render_mutual_exclusion_section)未在 _render_health_3tables 內被呼叫"
    assert big, "「📊 健診大表」標題不見了 —— Q1 的另一個錨點消失"
    me_line = me[0].lineno
    assert max(c.lineno for c in red) < me_line, (
        "元件 A 必須在淘汰候選紅區(結論摘要)**之後**(Q1 拍板位置)")
    assert me_line < max(c.lineno for c in big), (
        "元件 A 必須在「📊 健診大表」標題**之前**(Q1 拍板位置)")


def test_element_a_only_on_health_tab():
    """Q1 拍板的是 ② 組合健診頁 —— Tab3 embed(source_tab='portfolio')不得夾帶。

    判準:呼叫點必須有一個 If 祖先,其條件字面包含 `source_tab == 'health'`
    (正向比對 Eq,不是「有出現 source_tab 就好」—— 極性看運算子,不看 not)。
    """
    tree = _parse(_HEALTH)
    fn = _fn(tree, "_render_health_3tables")
    parents: dict = {}
    for node in ast.walk(fn):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node
    (call,) = _calls_named(fn, "render_mutual_exclusion_section")
    guarded = False
    cur = call
    while id(cur) in parents:
        cur = parents[id(cur)]
        if isinstance(cur, ast.If):
            for cmp_ in [n for n in ast.walk(cur.test) if isinstance(n, ast.Compare)]:
                names = {ast.unparse(cmp_.left)} | {ast.unparse(c) for c in cmp_.comparators}
                if ("source_tab" in names and "'health'" in names
                        and all(isinstance(op, ast.Eq) for op in cmp_.ops)):
                    guarded = True
    assert guarded, (
        "元件 A 的呼叫沒有被 `source_tab == 'health'` 的 If 包住 —— "
        "Tab3 持倉健診 embed 會夾帶未經草稿拍板的版面異動(§-1.5 v3 §03-2 ①)")


def test_element_a_does_not_redraw_the_matrix():
    """Q1 原文:完整相關性矩陣**不搬家** —— 元件 A 不得 import plotly / 重畫熱力圖。"""
    tree = _parse("ui/components/mutual_exclusion.py")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(a.name.split(".")[0] == "plotly" for a in node.names), \
                "元件 A import 了 plotly —— 矩陣熱力圖不該搬進來(Q1:依據不搬家)"
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] != "plotly", \
                "元件 A import 了 plotly —— 矩陣熱力圖不該搬進來(Q1:依據不搬家)"
    assert not _calls_named(tree, "_render_correlation_matrix"), \
        "元件 A 呼叫了 _render_correlation_matrix —— 完整矩陣留在進階分析,不重畫"


# ═══════════════════════════════════════════════════════════════════════
# B. Q3 改型:批次端收合 Expander
# ═══════════════════════════════════════════════════════════════════════

_BATCH = "ui/tab_batch_analysis.py"
_ROT = "ui/helpers/fund_grp_health/rotation.py"


def test_q3_batch_tab_uses_the_collapsed_explorer():
    """③ 批次結果區:呼叫元件 B;不得再攤開呼叫舊的 render_rotation_section_from_df。"""
    tree = _parse(_BATCH)
    assert _calls_named(tree, "render_complementary_explorer_from_df"), (
        "批次結果區沒有呼叫元件 B(render_complementary_explorer_from_df)—— Q3 改型斷線")
    assert not _calls_named(tree, "render_rotation_section_from_df"), (
        "批次結果區仍在呼叫 render_rotation_section_from_df(攤開照抄 ② 的舊型態)—— "
        "Q3 拍板為「改型為收合互補探索」,兩個都畫會出現兩份輪動區塊")


def test_q3_explorer_expander_is_collapsed_by_default():
    """Expander 必須字面 `expanded=False`(fail-closed:缺 keyword / 動態值 / True 都紅)。

    「批次跑完不展開,避免結果區被撐爆」是 Q3 拍板的呈現核心 ——
    st.expander 預設值雖然也是收合,但**不寫出來**就守不住(改預設、換 helper 都隱形)。
    """
    fn = _fn(_parse(_ROT), "render_complementary_explorer_from_df")
    exps = [c for c in ast.walk(fn)
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
            and c.func.attr == "expander"]
    assert len(exps) == 1, f"元件 B 應恰有 1 個 expander,掃到 {len(exps)} 個"
    kw = {k.arg: k.value for k in exps[0].keywords}
    assert "expanded" in kw, "expander 缺 expanded= 字面宣告(fail-closed)"
    v = kw["expanded"]
    assert isinstance(v, ast.Constant) and v.value is False, (
        "expander 不是字面 expanded=False —— Q3 拍板「預設收合」被改掉")


def test_q3_explorer_grid_is_three_columns_only():
    """元件 B 內所有 st.columns 都是字面 3(鐵律 1;與全站 grid contract 同向)。"""
    fn = _fn(_parse(_ROT), "render_complementary_explorer_from_df")
    cols = [c for c in ast.walk(fn)
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
            and c.func.attr == "columns"]
    assert cols, "元件 B 沒有任何 st.columns —— 3 欄網格(滑桿列 / 卡片格)不見了"
    for c in cols:
        assert c.args and isinstance(c.args[0], ast.Constant) and c.args[0].value == 3, \
            f"元件 B 出現非 3 欄的 columns(line {c.lineno})—— 違反鐵律 1"


# ═══════════════════════════════════════════════════════════════════════
# C. 委派 sentinel(重新 inline / 斷線 → 紅)
# ═══════════════════════════════════════════════════════════════════════

_BATCH_DF = pd.DataFrame([
    {"code": "A", "基金名": "A基", "基金類別": "股票型", "4D Grade": "A",
     "σ rank": "-0.20σ", "距 HWM %": "-3%", "操盤評分": 80,
     "吃本金燈號 (1Y · )": "🟢", "ccy": "USD"},
    {"code": "B", "基金名": "B基", "基金類別": "債券型", "4D Grade": "B",
     "σ rank": "-2.00σ", "距 HWM %": "-18%", "操盤評分": 75,
     "吃本金燈號 (1Y · )": "🟡 注意", "ccy": "TWD"},
])


def test_explorer_routes_through_l2_and_shared_body(monkeypatch):
    """元件 B 的配對真的來自 L2(SSOT 預設門檻),表身真的走共用 `_render_pairs_body`。"""
    import services.rotation as SR
    import ui.helpers.fund_grp_health.rotation as UIR
    from shared.signal_thresholds import (
        ROTATION_BUY_MIN_SCORE,
        ROTATION_BUY_SIGMA,
        ROTATION_SELL_SIGMA,
    )

    seen: dict = {}
    _orig = SR.suggest_rotation_pairs

    def _rec_pairs(rows, sell_sigma, buy_sigma, min_score):
        seen["l2"] = (len(rows), sell_sigma, buy_sigma, min_score)
        return _orig(rows, sell_sigma=sell_sigma, buy_sigma=buy_sigma,
                     min_score=min_score)

    def _rec_body(rows, pairs, sell, buy, *, key_prefix, offer_download):
        seen["body"] = (len(rows), len(pairs), key_prefix, offer_download)

    monkeypatch.setattr(SR, "suggest_rotation_pairs", _rec_pairs)
    monkeypatch.setattr(UIR, "_render_pairs_body", _rec_body)
    _render_explorer_bare()      # ⚠️ 一定要走這個 helper,理由見它的 docstring
    assert seen.get("l2") == (2, ROTATION_SELL_SIGMA, ROTATION_BUY_SIGMA,
                              float(ROTATION_BUY_MIN_SCORE)), (
        "元件 B 未經 services.rotation.suggest_rotation_pairs(或門檻不走 SSOT 預設)")
    assert seen.get("body") == (2, 1, "batch_rot_", True), (
        "元件 B 未把完整配對表委派給共用 `_render_pairs_body` —— "
        "重新 inline 第二份表 = ②/③ 表身分家(§2.1)")


def _render_explorer_bare() -> None:
    """bare 模式渲染元件 B,**並清掉它留在根 DeltaGenerator 上的 form 殘留**。

    ⚠️ `finally` 不是防禦性程式碼,是修一個實測到的**行程污染**(2026-08-31 稽核抓到)。
    元件 B 自 2026-08-31 起含 `with st.form(...)`;bare 模式(無 ScriptRunContext)離開
    該區塊後,根 DeltaGenerator(`st._main`,模組級單例)會留下 `_form_data`,活過整個
    pytest 行程 → 之後任何用 AppTest 且畫面上有 `st.button` 的測試都會被判成
    「按鈕在 form 裡」而丟 StreamlitAPIException(實測打掛 `tests/test_render_smoke.py` 3 條)。

    本檔在**本 PR 之前無害**(當時元件 B 沒有 form),是被 form 化「連坐」才需要收尾 ——
    **不是本檔自己的舊債**,故一併補上。完整機制、版本註記與「為什麼不能連
    `_active_dg = _main_dg` 一起抄」見
    `tests/test_rotation_form_rerun_20260831.py::_render_bare` 的 docstring。

    ⚠️ **本檔任何 bare 渲染元件 B 的地方都要走這裡**,不要直接呼叫 —— 直接呼叫必漏。
    """
    import streamlit as st

    import ui.helpers.fund_grp_health.rotation as UIR
    try:
        UIR.render_complementary_explorer_from_df(_BATCH_DF)
    finally:
        # 例外路徑也要清 —— 渲染中途爆掉時殘留最嚴重(with 沒走完)。
        _main = getattr(st, "_main", None)
        if _main is not None:
            _main._form_data = None


def test_bare_render_here_leaves_no_form_state_on_the_root_dg():
    """本檔 bare 渲染元件 B 之後,`st._main._form_data` 必須回到 None。

    ⚠️ **這條守的是別的檔案,不是本檔** —— 而那正是它非有不可的理由:
    `st._main` 是模組級單例,bare 模式(無 ScriptRunContext)下 `with st.form(...)`
    的殘留會活過整個 pytest 行程,讓**之後**任何用 AppTest 且畫面上有 `st.button`
    的測試被誤判成「按鈕在 form 裡」而丟 StreamlitAPIException
    (實測受害者:`tests/test_render_smoke.py` 3 條)。

    上面 `test_explorer_routes_through_l2_and_shared_body` 的 `finally` 收尾若被刪掉,
    **本檔自己照樣全綠**、CI 也可能因為 marker 分流/字母序剛好而全綠 ——
    **沒有這條,那行 `finally` 就是一段沒有守衛的修復,下一個人整理程式碼時可以無聲刪掉。**

    完整機制、版本註記與「為什麼不能抄 `_active_dg` 那行」見
    `tests/test_rotation_form_rerun_20260831.py::_render_bare` 的 docstring。
    """
    import streamlit as st

    _main = getattr(st, "_main", None)
    assert _main is not None, "streamlit 沒有 _main —— 本守衛的前提不成立,請重新確認版本"
    _main._form_data = None      # 先歸零,免得被同行程更早的測試影響、驗到假綠
    _render_explorer_bare()
    assert getattr(_main, "_form_data", None) is None, (
        f"bare 渲染後根 DG 仍殘留 form 狀態:{_main._form_data!r} —— "
        "同一個 pytest 行程內,後續任何 AppTest 畫面上的 st.button 都會被誤判成"
        "「在 form 內」而丟 StreamlitAPIException。")


def test_render_pairs_ui_still_routes_through_shared_body(monkeypatch):
    """② 既有入口同樣走共用表身 —— 兩入口同一份表,不因本輪抽出而分家。"""
    import ui.helpers.fund_grp_health.rotation as UIR

    seen: dict = {}
    monkeypatch.setattr(UIR, "_render_pairs_body",
                        lambda rows, pairs, sell, buy, *, key_prefix, offer_download:
                        seen.setdefault("args", (len(rows), key_prefix, offer_download)))
    rows = [{"code": "A", "name": "A", "σ rank": "-0.2σ", "基金類別": "股票型",
             "4D Grade": "A", "操盤評分": 80, "吃本金燈號": "🟢",
             "距 HWM %": "-3%", "currency": "USD"}]
    UIR._render_pairs_ui(rows, key_prefix="t_", offer_download=False)
    assert seen.get("args") == (1, "t_", False), (
        "_render_pairs_ui 未委派 `_render_pairs_body` —— 表身被重新 inline")


def test_element_a_routes_through_l2_summary(monkeypatch):
    """元件 A 的答案真的來自 services.homogeneity(輸入 = 共用 builder 的同一份)。"""
    import services.homogeneity as SH
    from ui.components.mutual_exclusion import render_mutual_exclusion_section
    from ui.helpers.fund_grp_health.correlation import build_corr_input

    idx = pd.date_range("2024-01-01", periods=60, freq="D")
    funds = [
        {"code": "A", "name": "A基", "series": pd.Series(np.linspace(100, 110, 60), index=idx),
         "moneydj_raw": {"holdings": {"top_holdings": [{"name": "TSMC"}],
                                      "sector_alloc": [{"name": "tech", "pct": 80}]}}},
        {"code": "B", "name": "B基", "series": pd.Series(np.linspace(100, 90, 60), index=idx),
         "moneydj_raw": {"holdings": {"top_holdings": [{"name": "AAPL"}],
                                      "sector_alloc": [{"name": "fin", "pct": 60}]}}},
    ]
    seen: dict = {}
    _orig = SH.build_mutual_exclusion_summary

    def _rec(hov_input, corr_input, hov_result, corr_result):
        seen["codes"] = ([f["code"] for f in hov_input], [f["code"] for f in corr_input])
        return _orig(hov_input, corr_input, hov_result, corr_result)

    monkeypatch.setattr(SH, "build_mutual_exclusion_summary", _rec)
    render_mutual_exclusion_section(funds)
    assert seen.get("codes") == (["A", "B"], ["A", "B"]), (
        "元件 A 未經 services.homogeneity.build_mutual_exclusion_summary 取得彙整 —— "
        "警示對/同質化被搬回 UI 自算(違反 L2 單一核心)")
    # 輸入 builder 共用:corr_input 必須帶 name(剔除名單標名靠它,§1)
    assert all("name" in f for f in build_corr_input(funds))


def test_element_a_under_two_funds_is_grey_and_never_computes(monkeypatch):
    """< 2 檔:⬜ 灰色說明(not_ready),且不進計算(前提不足 ≠ 故障,鐵律 ③)。"""
    import services.homogeneity as SH
    import ui.components.mutual_exclusion as ME

    called: dict = {}
    monkeypatch.setattr(ME, "not_ready",
                        lambda msg, **kw: called.setdefault("grey", str(msg)))
    monkeypatch.setattr(SH, "build_mutual_exclusion_summary",
                        lambda *a, **k: called.setdefault("computed", True))
    ME.render_mutual_exclusion_section([{"code": "A", "name": "A基"}])
    assert "grey" in called and "2 檔" in called["grey"], \
        "< 2 檔沒有走 ⬜ not_ready 灰色說明"
    assert "computed" not in called, "< 2 檔仍進了計算(該是前提守門,不是算完再丟)"


# ═══════════════════════════════════════════════════════════════════════
# D. §1 誠實:剔除名單真的被畫出來
# ═══════════════════════════════════════════════════════════════════════


def test_excluded_funds_are_rendered_by_name(monkeypatch):
    """元件 A:被剔除檔(缺持股+產業)的**名字**必須出現在畫面輸出(拿掉渲染 → 紅)。"""
    import ui.components.mutual_exclusion as ME

    idx = pd.date_range("2024-01-01", periods=60, freq="D")
    rng = np.random.default_rng(1)
    funds = [
        {"code": "A", "name": "A基",
         "series": pd.Series(100 + np.cumsum(rng.normal(0, 1, 60)), index=idx),
         "moneydj_raw": {"holdings": {"top_holdings": [{"name": "TSMC"}],
                                      "sector_alloc": [{"name": "tech", "pct": 80}]}}},
        {"code": "B", "name": "B基",
         "series": pd.Series(100 + np.cumsum(rng.normal(0, 1, 60)), index=idx),
         "moneydj_raw": {"holdings": {"top_holdings": [{"name": "AAPL"}],
                                      "sector_alloc": [{"name": "fin", "pct": 60}]}}},
        {"code": "C", "name": "缺料基", "series": None,
         "moneydj_raw": {"holdings": {"top_holdings": [], "sector_alloc": []}}},
    ]
    texts: list = []
    monkeypatch.setattr(ME.st, "caption", lambda body, **kw: texts.append(str(body)))
    ME.render_mutual_exclusion_section(funds)
    joined = "\n".join(texts)
    assert "缺料基" in joined and "C" in joined, (
        "被剔除的缺資料檔沒有具名出現在畫面 —— §1:靜默縮小比對範圍是本輪要修掉的病")
    assert "⬜" in joined, "剔除名單必須用 ⬜ 灰態呈現(不是紅、不是消失)"
