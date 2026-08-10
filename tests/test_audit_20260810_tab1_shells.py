"""2026-08-10 稽核 — Tab① 兩項:空殼摺疊容器拆除(B1)+ 綜合分數接線(B4)。

覆蓋:
  B1  `expanded=True` 的 expander 空殼一律拆掉。
      user 原則:「不想要有闔上的資料」+「重複的移除」。`expanded=True` 只設定
      摺疊把手的**初始**狀態,把手本身還在 —— 使用者誤點一次,已經算好的內容就
      整段消失;而外框標題往往是正上方區塊標題(或面板自己標題)的第二份副本。
      三個現場:決策矩陣 / 中國副盤(`ui/tab1_macro.py`)、流動性壓力預警引擎
      (`ui/tab1_macro_radar.py`)。
      ⚠️ **範圍**:只管 `expanded=True` 這種「外框沒擋住任何東西、只多印一次標題」
      的空殼。`expanded=False`(Z-Score 完整矩陣 / ARCHIVED 台股熱錢 / 美股流動性
      raw data 等)是**另一個問題** —— 那是「要不要預設收合大量原始資料」的取捨,
      本次未受指派,刻意不納入,免得順手把沒被裁決的東西一起改掉(`CLAUDE.md §-1`)。

  B4  AI 摘要「綜合分數」的 producer ↔ consumer 接線(`PROCESS.md §4`)。
      判準寫在 `TestCompositeScoreWiring` 的 docstring:拿掉 stash 那一行就必須紅。

⚠️ 位置 / 結構類斷言一律走 AST(本 repo 既有慣例):`ui/tab1_macro.py` 的沿革註解
   大量引述區塊名與函式名,`src.index()` / `in src` 會提前命中註解變成假通過。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_TAB1 = _ROOT / "ui" / "tab1_macro.py"
_RADAR = _ROOT / "ui" / "tab1_macro_radar.py"
_AI = _ROOT / "ui" / "tab1_macro_ai.py"

# Streamlit 這幾個 primitive 都渲染成「可收合容器」(同 tests/test_app_smoke.py 的清單)。
_COLLAPSIBLE_ATTRS = ("expander", "status", "popover", "dialog")

_SHELL_FREE_FILES = (_TAB1, _RADAR)


# ══════════════════════════════════════════════════════════════
# 共用 AST 工具
# ══════════════════════════════════════════════════════════════
def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def _fn_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    return str(getattr(call.func, "attr", ""))


def _md_headings(path: Path) -> list[str]:
    """該檔所有 `st.markdown("#…")` 的標題字面值(只取以 `#` 開頭者)。"""
    out: list[str] = []
    for _n in ast.walk(_tree(path)):
        if (isinstance(_n, ast.Call) and _fn_name(_n) == "markdown"
                and _n.args and isinstance(_n.args[0], ast.Constant)
                and isinstance(_n.args[0].value, str)
                and _n.args[0].value.startswith("#")):
            out.append(_n.args[0].value)
    return out


def _heading_level(text: str) -> int:
    return len(text) - len(text.lstrip("#"))


def _wraps_name(path: Path, name: str) -> list[int]:
    """回傳「把 `name` 包在可收合容器裡」的 `with` 行號(沒有則空 list)。"""
    hits: list[int] = []
    for _n in ast.walk(_tree(path)):
        if not isinstance(_n, ast.With):
            continue
        if not any(isinstance(_i.context_expr, ast.Call)
                   and _fn_name(_i.context_expr) in _COLLAPSIBLE_ATTRS
                   for _i in _n.items):
            continue
        if any(isinstance(_x, ast.Name) and _x.id == name
               for _x in ast.walk(_n)):
            hits.append(_n.lineno)
    return hits


# ══════════════════════════════════════════════════════════════
# B1 — 空殼摺疊容器
# ══════════════════════════════════════════════════════════════
@pytest.mark.parametrize("path", _SHELL_FREE_FILES, ids=[p.name for p in _SHELL_FREE_FILES])
def test_no_default_open_collapsible_shell(path: Path):
    """**修正前必紅**(舊行為與斷言衝突,非 ImportError)—— 修正前三處都是
    `expanded=True`,本條直接與它們相斥。

    `expanded=True` 的摺疊容器對「揭露」零貢獻:它一開始就是開的,所以外框從來
    沒有擋住任何東西;它唯一的淨效果是多印一次標題,外加一個誤點就把內容收起來
    的把手。要視覺分界用 `st.container(border=True)`(本 repo 既有慣例,
    見 `ui/helpers/v2_editor.py`),那個不可收合。
    """
    _bad = [(_n.lineno, _kw.value.value)
            for _n in ast.walk(_tree(path))
            if isinstance(_n, ast.Call) and _fn_name(_n) in _COLLAPSIBLE_ATTRS
            for _kw in _n.keywords
            if _kw.arg == "expanded" and isinstance(_kw.value, ast.Constant)
            and _kw.value.value is True]
    assert not _bad, (
        f"{path.name} 又出現預設展開的摺疊容器(行 {[b[0] for b in _bad]})—— "
        "外框沒擋住任何東西,只多印一次標題並留下一個誤點就收合的把手")


def test_china_drag_panel_renders_without_a_collapsible_frame():
    """**修正前必紅**(舊行為衝突)—— 修正前面板被包在 `expanded=True` 外框內。

    面板自己第一行就畫一張帶標題與 regime 的卡,三條早退路徑也各自帶同一個標題,
    外框那行標籤是第二份副本(user 原則:重複的移除)。
    """
    assert not _wraps_name(_TAB1, "_render_china_drag_panel"), (
        "中國副盤又被包回可收合容器 —— 它是 4 個已經算好的唯讀數字,闔起來等於算了不給看")


def test_liquidity_engine_block_keeps_a_heading_at_the_sibling_level():
    """**修正前必紅**(舊行為衝突)—— 修正前這一段的標題是 expander 的**標籤**,
    不是 `st.markdown` 標題,本條抓不到而紅。

    拆外框不可以順手把標題弄丟:同一段裡 ④ 短線風險雷達是 `###`,⑤ 流動性壓力
    預警引擎必須同級,否則版面會變成「④ 之下掛著一坨沒有名字的圖表」。
    """
    _hs = _md_headings(_RADAR)
    _h4 = [h for h in _hs if "短線風險雷達" in h]
    _h5 = [h for h in _hs if "流動性壓力預警引擎" in h]
    assert len(_h4) == 1, f"④ 短線風險雷達標題應恰好一處,實際 {_h4}"
    assert len(_h5) == 1, f"⑤ 流動性壓力預警引擎標題應恰好一處,實際 {_h5}"
    assert _heading_level(_h5[0]) == _heading_level(_h4[0]), (
        f"⑤ 與同段的 ④ 標題層級不一致:{_h5[0]!r} vs {_h4[0]!r}")


def test_decision_matrix_title_is_printed_exactly_once():
    """**修正前必紅**(舊行為衝突)—— 修正前同一句話在畫面上連印三次:
    呼叫端的 `##` 區塊標題、外框 expander 的標籤、renderer 內部的 `###`,
    三者只差一個 emoji 與一段括號補述。

    拆掉外框之後剩兩個標題會直接疊在一起,所以 renderer 內那層 `###` 一併移除。
    本條守「只剩一個,且它是區塊級(`##`)」;renderer 內留下的 caption 講的是
    推導鏈,與呼叫端那句「所以我該怎麼做」不同義,不在本條管轄範圍。
    """
    _hits = [h for h in _md_headings(_TAB1) if "決策矩陣" in h]
    assert len(_hits) == 1, f"決策矩陣標題應恰好一處,實際 {_hits}"
    assert _heading_level(_hits[0]) == 2, (
        f"決策矩陣標題應是區塊級(兩個井號),實際 {_hits[0]!r}")


# ══════════════════════════════════════════════════════════════
# B4 — 綜合分數 producer ↔ consumer 接線
# ══════════════════════════════════════════════════════════════
_SESSION_KEY = "composite_score"


class _FakeSessionState(dict):
    def __getattr__(self, k):
        return self.get(k)

    def __setattr__(self, k, v):
        self[k] = v


class _FakeST:
    def __init__(self, session_state):
        self.session_state = session_state


@pytest.fixture()
def _mock_ss(monkeypatch):
    import streamlit as st
    monkeypatch.setattr(st, "session_state", _FakeSessionState({}))


def _session_writes(path: Path) -> dict[str, ast.expr]:
    """該檔所有 `st.session_state["<key>"] = <expr>` 的 key → 右手邊運算式。"""
    out: dict[str, ast.expr] = {}
    for _n in ast.walk(_tree(path)):
        if not isinstance(_n, ast.Assign):
            continue
        for _tg in _n.targets:
            if (isinstance(_tg, ast.Subscript)
                    and isinstance(_tg.slice, ast.Constant)
                    and isinstance(_tg.slice.value, str)
                    and isinstance(_tg.value, ast.Attribute)
                    and _tg.value.attr == "session_state"):
                out[_tg.slice.value] = _n.value
    return out


def _snapshot_score_arg() -> ast.expr:
    """`render_ai_summary_section` 餵給 `_build_macro_ai_snapshot` 的第 3 個引數。"""
    for _n in ast.walk(_tree(_AI)):
        if isinstance(_n, ast.Call) and _fn_name(_n) == "_build_macro_ai_snapshot":
            assert len(_n.args) >= 3, "snapshot 呼叫的引數少於 3 個,結構已變請更新本測試"
            return _n.args[2]
    raise AssertionError("ui/tab1_macro_ai.py 找不到 _build_macro_ai_snapshot 呼叫")


def _eval_with_session(expr: ast.expr, session: dict):
    """在只有 `st` 的命名空間裡求值 —— 直接跑**呼叫端原始碼那一段運算式**,
    而不是在測試裡重寫一份等價的讀法(重寫等於測試自說自話,呼叫端改了也不會紅)。"""
    _mod = ast.Expression(body=expr)
    ast.fix_missing_locations(_mod)
    return eval(compile(_mod, "<wiring>", "eval"),  # noqa: S307 — 求值對象來自本 repo 原始碼
                {"st": _FakeST(_FakeSessionState(session))})


class TestCompositeScoreWiring:
    """`PROCESS.md §4` 接線驗證。

    **判準**:把 `ui/tab1_macro.py` 裡那一行 stash 拿掉 →
    `test_producer_stashes_the_computed_score` 立刻紅;
    把消費端讀的 key 改掉 / 改回給預設值 →
    `test_consumer_reads_the_same_key_and_gets_the_number` 立刻紅。

    **修正前會不會紅**:
      - producer 那條:**不會**。這個 key 的寫入端 v19.428 就已經補上
        (稽核清單寫的「0 writer」經複驗**不成立**),本條是補上缺席的回歸鎖 ——
        原本沒有任何測試守它,刪掉那一行不會有人知道。
      - consumer 兩條:**會**(舊行為衝突紅)。舊碼是 `score or "—"`,
        composite 正好等於 0.0 會被 falsy 吃掉;且格式化位數與畫面對不上。
    """

    def test_producer_stashes_the_computed_score(self):
        """寫進 session 的必須是**算出來的變數**,不得是字面常數(§1 反造假)。"""
        _writes = _session_writes(_TAB1)
        assert _SESSION_KEY in _writes, (
            f"ui/tab1_macro.py 沒有把總分 stash 進 session['{_SESSION_KEY}'] —— "
            "下游 AI 摘要與換股顧問成長型分支會永遠讀不到")
        _rhs = _writes[_SESSION_KEY]
        assert isinstance(_rhs, ast.Name), (
            f"stash 的右手邊不是變數而是 {type(_rhs).__name__} —— 疑似寫死的假值")
        # 這個變數必須綁自 composite 的計算呼叫,而不是隨便一個同名 local
        _bound_by_calc = any(
            isinstance(_n, ast.Assign)
            and any(isinstance(_t, ast.Name) and _t.id == _rhs.id for _t in _n.targets)
            and isinstance(_n.value, ast.Call)
            and _fn_name(_n.value).lstrip("_").startswith("calculate_composite_score")
            for _n in ast.walk(_tree(_TAB1)))
        assert _bound_by_calc, (
            f"session['{_SESSION_KEY}'] 收的變數 {_rhs.id!r} 不是 composite 計算的回傳值")

    def test_consumer_reads_the_same_key_and_gets_the_number(self, _mock_ss):
        """消費端讀到的必須是 producer 寫進去的那個數,而且真的進得了 prompt。"""
        _arg = _snapshot_score_arg()
        assert _eval_with_session(_arg, {_SESSION_KEY: 15.5}) == pytest.approx(15.5), (
            "AI 摘要沒有從 producer 寫的那個 session key 取數")

        from ui.tab1_macro_ai import _build_macro_ai_snapshot
        _snap, _, _ = _build_macro_ai_snapshot(
            {}, {"phase": "擴張", "score": 6.8},
            _eval_with_session(_arg, {_SESSION_KEY: 15.5}), None, [])
        assert "+15.5" in _snap, "取到了數字卻沒進 prompt(算對了但沒接出去)"

    def test_zero_is_a_reading_not_a_missing_value(self, _mock_ss):
        """**修正前必紅**(舊行為衝突)—— 舊碼 `score or "—"`:composite 是有正負的
        加權淨分,正好落在 0.0(多空完全打平)是**真讀數**,卻會被 falsy 判成缺資料。
        同型缺陷見 `PROCESS.md §4` 表格第一列。"""
        from ui.tab1_macro_ai import _build_macro_ai_snapshot
        _arg = _snapshot_score_arg()
        _snap, _, _ = _build_macro_ai_snapshot(
            {}, {"phase": "中性", "score": 5.0},
            _eval_with_session(_arg, {_SESSION_KEY: 0.0}), None, [])
        _line = next(ln for ln in _snap.splitlines() if "綜合分數" in ln)
        assert "+0.0" in _line, f"0.0 被當成缺值:{_line!r}"
        assert "—" not in _line.split("綜合分數")[-1], f"0.0 仍印成缺值符號:{_line!r}"

    def test_missing_score_still_says_missing(self, _mock_ss):
        """§1 反向:producer 那一段真的沒跑完時,不可以編一個數字出來。"""
        from ui.tab1_macro_ai import _build_macro_ai_snapshot
        _arg = _snapshot_score_arg()
        _snap, _, _ = _build_macro_ai_snapshot(
            {}, {"phase": "擴張", "score": 6.8},
            _eval_with_session(_arg, {}), None, [])
        _line = next(ln for ln in _snap.splitlines() if "綜合分數" in ln)
        assert "—" in _line.split("綜合分數")[-1], f"缺值時卻印出數字:{_line!r}"

    @pytest.mark.parametrize("bad", [True, False, "15.5", None, {}, [],
                                     float("nan"), float("inf")])
    def test_non_numeric_never_becomes_a_fake_number(self, bad):
        """邊界:布林 / 字串 / 空容器 / NaN / inf 都不是讀數,一律回缺值符號,
        不得被 float() 硬轉後送進 prompt。兩個特別容易漏的:
        `True` 是 `int` 的子型別(會變 `+1.0`),NaN 會被格式化成 `+nan`。"""
        from ui.tab1_macro_ai import _format_composite
        assert _format_composite(bad) == "—"

    def test_dict_carrier_still_supported(self):
        """舊契約相容:曾有以 dict 承載總分的讀法(換股顧問側仍容忍),不得回歸。"""
        from ui.tab1_macro_ai import _format_composite
        assert _format_composite({"total": -8.0}) == "-8.0"
        assert _format_composite({"score": 3.5}) == "+3.5"
        assert _format_composite({"note": "no number here"}) == "—"
