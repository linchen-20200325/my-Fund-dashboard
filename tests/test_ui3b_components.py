"""tests/test_ui3b_components.py — UI3b 六個新元件的**誠實性**回歸網。

本檔刻意**不測「有沒有畫出來」** —— 那種測試在元件開始說謊時依然全綠。
每一條測試對應元件 docstring 裡的一條「**絕不**」，也就是：
把某個修復拿掉，這裡就必須轉紅（突變驗證，見 PR 描述的逐條紀錄）。

守的六件事（一句話版）
----------------------
1. 16 盞燈少一盞就 raise（不補格）。
2. 缺 X／Y 的點不得靜默消失。
3. σ≈0 不得被畫成 0。
4. 釘選欄不得從任何一組消失。
5. 缺值必須沿算式往下傳，不得用預設值頂替。
6. 沒填本金不得畫成 0%/0% 的假圓環。

外加兩道機器守衛：**零 hex／rgba 色字面值** 與 **元件純度**（無 session_state／
cache／repository・service import／網路）。
"""
from __future__ import annotations

import ast
import pathlib

import pandas as pd
import pytest

from shared.colors import (
    GRAY_44,
    MATERIAL_ORANGE,
    MD_BLUE_300,
    TRAFFIC_GREEN,
    TRAFFIC_NEUTRAL,
    TRAFFIC_RED,
    TRAFFIC_YELLOW,
    WARN_AMBER,
)

# ══════════════════════════════════════════════════════════════
# 受測檔清單（兩道機器守衛掃這六個檔）
# ══════════════════════════════════════════════════════════════
_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
UI3B_FILES = [
    "ui/components/macro_light_board.py",
    "ui/components/health_quadrant_scatter.py",
    "ui/components/nav_sigma_channel.py",
    "ui/components/column_group_tabs.py",
    "ui/components/formula_card.py",
    "ui/components/allocation_donut_card.py",
]


def _src(rel: str) -> str:
    return (_REPO_ROOT / rel).read_text(encoding="utf-8")


def _docstring_string_lines(tree: ast.AST) -> set[int]:
    """所有 docstring 所佔的行號（module / class / def 的第一個字串運算式）。"""
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                c = body[0].value
                out.update(range(c.lineno, (c.end_lineno or c.lineno) + 1))
    return out


def _code_only(rel: str) -> str:
    """原始碼**去掉 docstring 與註解**後的版本（其餘字元位置完全保留）。

    ⚠️ 這個 helper 是必要的，不是潔癖：本檔有多條「元件裡不准出現 X」的守衛，
    而這些元件的 docstring **正是在解釋為什麼不准出現 X**（例如
    macro_light_board 的「為什麼不用 st.columns」）。直接掃原始碼 → 那些說明
    會把守衛自己絆倒，於是下一個人就會把守衛放寬或刪掉 —— 那才是真的損失。
    保留非 docstring 的字串常數（那裡才可能藏違規）。

    ⚠️ **實作刻意用「就地塗白」而不是 `tokenize.untokenize`**（2026-08-28 突變驗證抓到）：
    `untokenize` 以 2-tuple 還原時會**自行插入空白**，`st.markdown` 會變成
    `st .markdown` —— 於是 `"st.columns" not in code` 這種**帶點號的守衛永遠不會命中**，
    測試看起來是綠的，實際上什麼都沒守。當時 M4（把 16 格改用 st.columns 排）
    這條突變**沒有轉紅**，就是被這個 bug 蓋住的。
    改為只把 docstring／註解的字元範圍換成空白，其餘一個字元都不動。
    """
    import io
    import tokenize

    src = _src(rel)
    doc_lines = _docstring_string_lines(ast.parse(src))
    lines = src.splitlines()

    def _blank(start: tuple[int, int], end: tuple[int, int]) -> None:
        (r1, c1), (r2, c2) = start, end
        if r1 == r2:
            ln = lines[r1 - 1]
            lines[r1 - 1] = ln[:c1] + " " * (c2 - c1) + ln[c2:]
            return
        lines[r1 - 1] = lines[r1 - 1][:c1]
        for r in range(r1, r2 - 1):
            lines[r] = ""
        lines[r2 - 1] = " " * c2 + lines[r2 - 1][c2:]

    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT or (
                tok.type == tokenize.STRING and tok.start[0] in doc_lines):
            _blank(tok.start, tok.end)
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
# 假 streamlit：讓 render_* 薄殼也能被測（它們是「強制印出來」的落點）
# ══════════════════════════════════════════════════════════════
class _FakeCtx:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class StreamlitSpy:
    """記錄 render_* 對 streamlit 的呼叫。"""

    def __init__(self) -> None:
        self.captions: list[str] = []
        self.markdowns: list[str] = []
        self.charts: list[object] = []
        self.dataframes: list[object] = []
        self.tab_labels: list[list[str]] = []
        self.radio_options: list[list[str]] = []

    # ── streamlit 介面 ──
    def caption(self, body, *a, **k):
        self.captions.append(str(body))

    def markdown(self, body, *a, **k):
        self.markdowns.append(str(body))

    def plotly_chart(self, fig, *a, **k):
        self.charts.append(fig)

    def dataframe(self, df, *a, **k):
        self.dataframes.append(df)

    def tabs(self, labels):
        self.tab_labels.append([str(x) for x in labels])
        return [_FakeCtx() for _ in labels]

    def radio(self, label, options, **k):
        self.radio_options.append([str(x) for x in options])
        return options[0]

    def columns(self, n):
        return [_FakeCtx() for _ in range(n if isinstance(n, int) else len(n))]

    @property
    def all_text(self) -> str:
        return "\n".join(self.captions + self.markdowns)


@pytest.fixture()
def spy(monkeypatch) -> StreamlitSpy:
    """把 streamlit 模組上會被元件用到的函式換掉（元件用 lazy import，指向同一個模組物件）。"""
    import streamlit as st

    s = StreamlitSpy()
    for name in ("caption", "markdown", "plotly_chart", "dataframe", "tabs",
                 "radio", "columns"):
        monkeypatch.setattr(st, name, getattr(s, name), raising=False)
    return s


# ══════════════════════════════════════════════════════════════
# 機器守衛 A：零 hex / rgba 色字面值
# ══════════════════════════════════════════════════════════════
class TestNoColorLiterals:
    """顏色一律走 `shared.colors`；半透明走 plotly 原生 `opacity=`。

    掃**非 docstring 的字串常數**（AST）—— 註解不在 AST 裡，故不會誤報；
    f-string 內插的片段是 `Constant`，同樣掃得到。
    """

    @pytest.mark.parametrize("rel", UI3B_FILES)
    def test_no_hex_or_rgba_literal(self, rel):
        import re
        tree = ast.parse(_src(rel))
        skip_lines = _docstring_string_lines(tree)   # 與 _code_only 共用同一份判定
        bad: list[str] = []
        pat = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\s*\(")
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.lineno in skip_lines:
                    continue
                if pat.search(node.value):
                    bad.append(f"line {node.lineno}: {node.value[:60]!r}")
        assert not bad, (
            f"{rel} 出現寫死的顏色字面值 —— 顏色一律 `from shared.colors import ...`，"
            f"半透明用 plotly `opacity=`：\n" + "\n".join(bad))


# ══════════════════════════════════════════════════════════════
# 機器守衛 B：元件純度
# ══════════════════════════════════════════════════════════════
class TestComponentPurity:
    """元件是純函式層：零 session_state、零 cache、零 repository/service、零網路。

    反例（憲法已登記的違憲案例）：`ui/components/mk_dashboard.py::_get_benchmark_series`
    在 UI 層 yfinance 直抓 + `st.session_state` 自建快取。**本批絕不複製那個寫法。**
    """

    _FORBIDDEN_MODULES = ("requests", "httpx", "yfinance", "urllib", "feedparser",
                          "gspread", "socket", "subprocess")

    @pytest.mark.parametrize("rel", UI3B_FILES)
    def test_no_session_state_or_cache(self, rel):
        src = _src(rel)
        tree = ast.parse(src)
        hits = [f"line {n.lineno}: .{n.attr}" for n in ast.walk(tree)
                if isinstance(n, ast.Attribute)
                and n.attr in ("session_state", "cache_data", "cache_resource")]
        assert not hits, (
            f"{rel} 碰了 session_state / cache —— 元件必須是純函式，"
            f"狀態與快取歸呼叫端／L1：\n" + "\n".join(hits))

    @pytest.mark.parametrize("rel", UI3B_FILES)
    def test_no_repository_service_or_network_import(self, rel):
        tree = ast.parse(_src(rel))
        bad: list[str] = []
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for nm in names:
                root = nm.split(".")[0]
                if root in ("repositories", "services", "infra") or root in self._FORBIDDEN_MODULES:
                    bad.append(f"line {node.lineno}: {nm}")
        assert not bad, (
            f"{rel} import 了 repository / service / 網路套件 —— 元件不得自行取數"
            f"（憲法違憲案例：mk_dashboard 在 UI 層 yfinance 直抓）：\n" + "\n".join(bad))


# ══════════════════════════════════════════════════════════════
# ① macro_light_board
# ══════════════════════════════════════════════════════════════
def _lights(n=16, **over):
    out = []
    for i in range(n):
        d = {"label": f"L{i}", "value": i, "level": "ok", "recon": None}
        d.update(over)
        out.append(d)
    return out


class TestMacroLightBoard:
    def test_wrong_light_count_raises_never_pads(self):
        """**絕不**補格／截斷：少一盞就 raise。

        補出來的空格會讓「上游少給了 3 盞」長得像「這 3 盞剛好沒資料」。
        """
        from ui.components.macro_light_board import build_macro_light_board_html
        with pytest.raises(ValueError, match="16"):
            build_macro_light_board_html(_lights(15))
        with pytest.raises(ValueError, match="16"):
            build_macro_light_board_html(_lights(17))
        # 剛好 16 才過
        assert build_macro_light_board_html(_lights(16))

    def test_none_value_renders_dash_not_zero(self):
        """**絕不**把 None 顯示成 0（0 會被拿去判讀）。"""
        from ui.components.macro_light_board import build_macro_light_board_html
        html = build_macro_light_board_html(_lights(16, value=None))
        assert "—" in html
        assert ">0<" not in html, "None 被畫成了 0"

    def test_all_missing_still_renders_16_cells(self):
        """全 16 盞皆缺 → **仍畫 16 格**（格子本身就是「一個都沒抓到」這個資訊）。"""
        from ui.components.macro_light_board import build_macro_light_board_html
        html = build_macro_light_board_html(_lights(16, value=None, level="unknown"))
        assert html.count("min-width:140px") == 16

    def test_recon_badge_four_states(self):
        """對帳徽章四態不得錯置；`recon is None` 與 `both_missing` 一律 ⬜ 單源。"""
        from ui.components.macro_light_board import build_recon_badge_html
        assert TRAFFIC_GREEN in build_recon_badge_html({"status": "agree"})
        assert TRAFFIC_RED in build_recon_badge_html({"status": "disagree"})
        for st_ in ("a_missing", "b_missing"):
            assert TRAFFIC_YELLOW in build_recon_badge_html({"status": st_})
        for missing in (None, {}, {"status": "both_missing"}, {"status": "???"}):
            out = build_recon_badge_html(missing)
            assert TRAFFIC_NEUTRAL in out and "單源" in out, missing

    def test_footnote_is_mandatory_and_states_single_source_meaning(self, spy):
        """**絕不**拿掉／收合常駐腳註；它必須講「單源不代表錯」。"""
        from ui.components.macro_light_board import (
            FOOTNOTE_TEXT, render_macro_light_board,
        )
        assert "US10Y" in FOOTNOTE_TEXT
        assert "單源不代表錯" in FOOTNOTE_TEXT
        render_macro_light_board(_lights(16), (72, "ok"))
        assert any(FOOTNOTE_TEXT in c for c in spy.captions), "常駐腳註沒有被印出來"

    def test_footnote_is_not_collapsible(self):
        """腳註不得藏進 expander，也不得有開關參數。"""
        import inspect

        from ui.components import macro_light_board as m
        code = _code_only("ui/components/macro_light_board.py")
        assert "expander" not in code, "腳註不得做成可收合"
        params = inspect.signature(m.render_macro_light_board).parameters
        assert not any("foot" in p for p in params), "腳註不得有開關參數"

    def test_grid_uses_flex_not_st_columns(self):
        """16 格**絕不**用 st.columns（窄螢幕會退化成 16 列垂直長條）。"""
        code = _code_only("ui/components/macro_light_board.py")
        assert "st.columns" not in code
        assert "flex-wrap:wrap" in code


# ══════════════════════════════════════════════════════════════
# ② health_quadrant_scatter
# ══════════════════════════════════════════════════════════════
class TestHealthQuadrantScatter:
    _ROWS = [
        {"name": "好基金", "sigma_rank": -2.1, "score_4d": 82,
         "invest_twd": 300000, "grade_4d": "A", "tier": "core"},
        {"name": "貴又爛", "sigma_rank": 0.4, "score_4d": 31,
         "invest_twd": 50000, "grade_4d": "D", "tier": "satellite"},
        {"name": "沒填本金", "sigma_rank": -0.5, "score_4d": 60,
         "invest_twd": None, "grade_4d": "B", "tier": None},
        {"name": "沒有σ", "sigma_rank": None, "score_4d": 55,
         "invest_twd": 10000, "grade_4d": "B", "tier": "core"},
        {"name": "沒有分數", "sigma_rank": -1.5, "score_4d": None,
         "invest_twd": 10000, "grade_4d": None, "tier": "core"},
    ]

    def test_missing_xy_points_are_listed_never_silently_dropped(self):
        """**絕不**讓缺 X／Y 的點靜默消失 —— 不畫，但一定要回報名字。"""
        from ui.components.health_quadrant_scatter import (
            build_health_quadrant_figure, split_placeable,
        )
        placeable, unplaceable = split_placeable(self._ROWS)
        assert [p["name"] for p in placeable] == ["好基金", "貴又爛", "沒填本金"]
        assert set(unplaceable) == {"沒有σ", "沒有分數"}

        fig, un, _ = build_health_quadrant_figure(self._ROWS)
        plotted = {t for tr in fig.data for t in (tr.text or ())}
        assert "沒有σ" not in plotted and "沒有分數" not in plotted
        assert set(un) == {"沒有σ", "沒有分數"}

    def test_render_prints_unplaceable_list(self, spy):
        """薄殼**必須**把無法定位清單印出來。"""
        from ui.components.health_quadrant_scatter import render_health_quadrant_scatter
        render_health_quadrant_scatter(self._ROWS)
        assert "無法定位" in spy.all_text
        assert "沒有σ" in spy.all_text and "沒有分數" in spy.all_text

    def test_score_axis_is_fixed_0_100(self):
        """Y 軸**絕不**自動縮放 —— 58 分不能在一組爛基金裡看起來位在頂端。"""
        from ui.components.health_quadrant_scatter import build_health_quadrant_figure
        fig, _, _ = build_health_quadrant_figure(self._ROWS)
        assert tuple(fig.layout.yaxis.range) == (0.0, 100.0)

    def test_no_amount_uses_open_marker_not_smallest_solid(self):
        """沒填本金 → **空心**（`-open`）+ 最小尺寸；**絕不**畫成實心小點。"""
        from ui.components.health_quadrant_scatter import build_health_quadrant_figure
        fig, _, n_missing = build_health_quadrant_figure(self._ROWS)
        assert n_missing == 1
        symbols: list[str] = []
        for tr in fig.data:
            symbols += [str(s) for s in (tr.marker.symbol or ())]
        assert any(s.endswith("-open") for s in symbols), "沒填本金沒有畫成空心"

    def test_render_footnotes_no_amount_meaning(self, spy):
        from ui.components.health_quadrant_scatter import render_health_quadrant_scatter
        render_health_quadrant_scatter(self._ROWS)
        assert "不是本金為 0" in spy.all_text

    def test_quadrant_shading_uses_opacity_not_rgba(self):
        """半透明走 plotly 原生 `opacity=`（守衛 A 已擋 rgba；這裡確認真的有設）。"""
        from ui.components.health_quadrant_scatter import build_health_quadrant_figure
        fig, _, _ = build_health_quadrant_figure(self._ROWS)
        rects = [s for s in fig.layout.shapes if s.type == "rect"]
        assert len(rects) == 4
        assert all(0 < float(s.opacity) < 1 for s in rects)

    def test_unknown_grade_is_gray_not_guessed(self):
        """A/B/C/D 不是 status_color 別名 → 不傳 mapping 時誠實顯示灰，**絕不**亂猜。"""
        from ui.components.health_quadrant_scatter import build_health_quadrant_figure
        fig, _, _ = build_health_quadrant_figure(self._ROWS)
        colors = [c for tr in fig.data for c in (tr.marker.color or ())]
        assert all(c == TRAFFIC_NEUTRAL for c in colors)
        fig2, _, _ = build_health_quadrant_figure(
            self._ROWS, grade_levels={"A": "ok", "B": "warn", "D": "bad"})
        colors2 = [c for tr in fig2.data for c in (tr.marker.color or ())]
        assert TRAFFIC_GREEN in colors2 and TRAFFIC_RED in colors2


# ══════════════════════════════════════════════════════════════
# ③ nav_sigma_channel
# ══════════════════════════════════════════════════════════════
def _nav(n: int, flat: bool = False) -> pd.Series:
    idx = pd.date_range("2026-01-01", periods=n, freq="D")
    vals = [10.0] * n if flat else [10.0 + i * 0.01 for i in range(n)]
    return pd.Series(vals, index=idx)


_GOOD_LEVELS = {"hwm": 12.0, "sigma_abs": 0.5, "current_nav": 11.0,
                "level_1s": 11.5, "level_2s": 11.0, "level_3s": 10.5,
                "sigma_rank": -2.0, "label": "x", "color": MD_BLUE_300}


class TestNavSigmaChannel:
    def test_sigma_zero_error_is_never_drawn_as_zero(self):
        """**絕不**把 σ≈0 當 0 畫。

        舊版回 `sigma_rank=0.0` → `rotation.classify_base` 判成 "high"（高基期、偏貴）
        → 一檔停售基金被列進賣出候選。故此模式一條 σ 線都不畫，並明講原因。
        """
        from ui.components.nav_sigma_channel import (
            MODE_FLAT, build_nav_sigma_figure, nav_sigma_state,
        )
        levels = {"error": "NAV 無波動(σ≈0),無法定位階"}
        mode, msg = nav_sigma_state(_nav(60, flat=True), levels)
        assert mode == MODE_FLAT
        assert "停售" in msg and "無 σ 位階" in msg
        fig = build_nav_sigma_figure(_nav(60, flat=True), levels)
        assert fig is not None
        assert len(fig.layout.shapes) == 0, "σ≈0 模式竟然畫了 σ 線／帶"
        assert len(fig.data) == 1  # 只有真實 NAV 線

    def test_sigma_zero_is_not_conflated_with_insufficient_data(self):
        """σ≈0 與「資料不足」是兩種 error，**絕不**混為一談。"""
        from ui.components.nav_sigma_channel import (
            MODE_FLAT, MODE_LINE_ONLY, nav_sigma_state,
        )
        assert nav_sigma_state(_nav(60), {"error": "資料不足"})[0] == MODE_LINE_ONLY
        assert nav_sigma_state(_nav(60), {"error": "報酬率序列不足"})[0] == MODE_LINE_ONLY
        assert nav_sigma_state(_nav(60), {"error": "NAV 無波動(σ≈0)"})[0] == MODE_FLAT

    def test_error_levels_draw_no_sigma_lines(self):
        """`"error" in levels` → 只畫 NAV 折線，**一條 σ 線都不畫**。"""
        from ui.components.nav_sigma_channel import build_nav_sigma_figure
        fig = build_nav_sigma_figure(_nav(60), {"error": "資料不足"})
        assert len(fig.layout.shapes) == 0

    def test_full_mode_draws_bands_and_lines(self):
        from ui.components.nav_sigma_channel import MODE_FULL, build_nav_sigma_figure, nav_sigma_state
        assert nav_sigma_state(_nav(60), _GOOD_LEVELS)[0] == MODE_FULL
        fig = build_nav_sigma_figure(_nav(60), _GOOD_LEVELS)
        assert len(fig.layout.shapes) == 7  # 3 帶 + 4 線（HWM/-1σ/-2σ/-3σ）

    def test_single_point_is_not_ready_never_fake_horizon(self):
        """只有 1 筆 → `not_ready`；**絕不**畫單點、**絕不**畫水平線（＝假地平線）。"""
        from ui.components.nav_sigma_channel import (
            MODE_NOT_READY, build_nav_sigma_figure, nav_sigma_state,
        )
        mode, msg = nav_sigma_state(_nav(1), _GOOD_LEVELS)
        assert mode == MODE_NOT_READY and "假地平線" in msg
        assert build_nav_sigma_figure(_nav(1), _GOOD_LEVELS) is None

    def test_under_20_points_draws_nothing(self):
        """NAV < 20 點 → 連折線都不畫。"""
        from ui.components.nav_sigma_channel import (
            MODE_NOT_READY, build_nav_sigma_figure, nav_sigma_state,
        )
        assert nav_sigma_state(_nav(19), _GOOD_LEVELS)[0] == MODE_NOT_READY
        assert build_nav_sigma_figure(_nav(19), _GOOD_LEVELS) is None
        assert nav_sigma_state(_nav(20), _GOOD_LEVELS)[0] != MODE_NOT_READY

    def test_nan_gaps_do_not_count_as_points(self):
        """週末的空格不是一天的淨值 —— 缺值不計入點數。"""
        from ui.components.nav_sigma_channel import MODE_NOT_READY, nav_sigma_state
        s = _nav(30)
        s.iloc[5:] = float("nan")          # 只剩 5 個有效點
        assert nav_sigma_state(s, _GOOD_LEVELS)[0] == MODE_NOT_READY

    def test_gaps_are_not_connected_never_ffill(self):
        """**絕不** ffill／connectgaps —— 基金 NAV T+1~T+3，週末無資料是正常。"""
        from ui.components.nav_sigma_channel import build_nav_sigma_figure
        s = _nav(60)
        s.iloc[10] = float("nan")
        fig = build_nav_sigma_figure(s, _GOOD_LEVELS)
        nav_trace = fig.data[0]
        assert nav_trace.connectgaps is False
        # 缺口原樣保留，沒有被補值
        assert any(v != v for v in nav_trace.y), "NAV 缺口被填掉了"
        # 實作碼裡完全不得出現 ffill／bfill（說明文字可以講，程式不能做）。
        code = _code_only("ui/components/nav_sigma_channel.py")
        assert "ffill" not in code and "bfill" not in code

    def test_empty_dividends_add_nothing(self):
        """`dividends` 為空 → 不畫也不加 caption（➖ 不適用，不是 ⬜ 缺資料）。"""
        from ui.components.nav_sigma_channel import build_nav_sigma_figure
        a = build_nav_sigma_figure(_nav(60), _GOOD_LEVELS, None)
        b = build_nav_sigma_figure(_nav(60), _GOOD_LEVELS, [])
        assert len(a.data) == len(b.data) == 1

    def test_dividends_are_marked_when_present(self):
        from ui.components.nav_sigma_channel import build_nav_sigma_figure
        fig = build_nav_sigma_figure(_nav(60), _GOOD_LEVELS,
                                     [pd.Timestamp("2026-01-15")])
        assert len(fig.data) == 2

    def test_component_never_computes_sigma_itself(self):
        """**絕不**自行實作 σ（定義住在 services/precision_service）。"""
        code = _code_only("ui/components/nav_sigma_channel.py")
        for token in ("pct_change", "std(", "sqrt", "cumsum", "rolling("):
            assert token not in code, f"元件自己算了 σ：{token}"


# ══════════════════════════════════════════════════════════════
# ④ column_group_tabs
# ══════════════════════════════════════════════════════════════
_PINNED = ["基金代碼/名稱", "淨值樣本", "評分覆蓋", "對帳"]
_DF = pd.DataFrame({
    "基金代碼/名稱": ["A", "B"], "淨值樣本": [30, 250], "評分覆蓋": ["3/4", "4/4"],
    "對帳": ["⬜", "✅"], "Sharpe": [None, 1.2], "σ": [None, 0.3],
    "配息率": [4.1, 2.0],
})
_GROUPS = [
    ("風險", ["Sharpe", "σ", "MaxDD"]),          # MaxDD 不存在
    ("配息", ["配息率"]),
    ("整組都沒算", ["X1", "X2"]),                 # 整組皆缺
]


class TestColumnGroupTabs:
    def test_pinned_columns_present_in_every_group(self):
        """**絕不**讓釘選欄從任何一組消失。

        一檔只抓到 30 筆淨值的基金，Sharpe/σ/MaxDD 整批留白但 4D Score 照樣給分 ——
        沒有 `淨值樣本` 那一欄，它在表裡與正常基金完全同形。
        """
        from ui.components.column_group_tabs import resolve_group_columns
        for _lbl, cols in _GROUPS:
            ordered, _mg, missing_pinned = resolve_group_columns(
                _DF.columns, cols, _PINNED)
            assert not missing_pinned
            assert ordered[:len(_PINNED)] == _PINNED, f"{_lbl} 組的釘選欄不在最前面"

    def test_render_keeps_pinned_in_every_tab(self, spy):
        from ui.components.column_group_tabs import render_column_group_tabs
        render_column_group_tabs(_DF, None, _GROUPS, _PINNED)
        # 3 組都畫得出表：第 3 組自己的欄全缺，但**釘選欄一定在** → 仍是一張表。
        # 這正是釘選欄的用處：即使某組整組沒算出來，識別資料是否足夠的那幾欄還在。
        assert len(spy.dataframes) == 3
        for df in spy.dataframes:
            for c in _PINNED:
                assert c in list(df.columns)

    def test_missing_columns_are_reported_not_silent(self):
        """`groups` 有、df 沒有的欄 → 靜默略過，但**必須**在 caption 列出。"""
        from ui.components.column_group_tabs import (
            build_missing_caption, resolve_group_columns,
        )
        ordered, missing_group, _ = resolve_group_columns(
            _DF.columns, ["Sharpe", "σ", "MaxDD"], _PINNED)
        assert "MaxDD" not in ordered and missing_group == ["MaxDD"]
        cap = build_missing_caption(missing_group, [])
        assert "MaxDD" in cap and "不是這些基金沒有" in cap

    def test_render_emits_missing_caption(self, spy):
        from ui.components.column_group_tabs import render_column_group_tabs
        render_column_group_tabs(_DF, None, _GROUPS, _PINNED)
        assert "MaxDD" in spy.all_text and "不是這些基金沒有" in spy.all_text

    def test_missing_pinned_is_reported_louder(self):
        """釘選欄自己缺 → 🔴（防線本身沒了），與一般缺欄不同級。"""
        from ui.components.column_group_tabs import build_missing_caption
        cap = build_missing_caption([], ["淨值樣本"])
        assert "🔴" in cap and "無法分辨" in cap

    def test_group_with_no_columns_still_shows_label(self, spy):
        """某組欄位全缺 → **標籤仍顯示**（憑空消失會讓人以為只有 2 組）。"""
        from ui.components.column_group_tabs import render_column_group_tabs
        render_column_group_tabs(_DF, None, _GROUPS, _PINNED)
        assert spy.tab_labels[-1] == ["風險", "配息", "整組都沒算"]

    def test_does_not_change_rows_content_or_order(self, spy):
        """**絕不**改列數、改內容、排序。"""
        from ui.components.column_group_tabs import render_column_group_tabs
        before = _DF.copy(deep=True)
        render_column_group_tabs(_DF, None, _GROUPS, _PINNED)
        pd.testing.assert_frame_equal(_DF, before)
        for df in spy.dataframes:
            assert len(df) == len(_DF)
            assert list(df["基金代碼/名稱"]) == list(_DF["基金代碼/名稱"])

    def test_radio_mode_is_available_as_fallback(self, spy):
        from ui.components.column_group_tabs import render_column_group_tabs
        render_column_group_tabs(_DF, None, _GROUPS, _PINNED, mode="radio")
        assert spy.radio_options == [["風險", "配息", "整組都沒算"]]
        assert spy.tab_labels == []

    def test_groups_are_not_defined_inside_the_component(self):
        """`groups`/`pinned` **絕不**寫在元件內（那會是第二份 SSOT）。"""
        code = _code_only("ui/components/column_group_tabs.py")
        assert "Sharpe" not in code and "MaxDD" not in code


# ══════════════════════════════════════════════════════════════
# ⑤ formula_card
# ══════════════════════════════════════════════════════════════
class TestFormulaCard:
    def test_missing_step_blocks_all_downstream_steps(self):
        """任一步缺值 → 該步 `—` + 就地說明；**其後全部標「上一步缺值」且不計算**。

        **絕不**用預設匯率／1.0 頂替 —— 用 1.0 當匯率會讓美元部位以 1:1 併進台幣
        總額，那不是「少一個數字」，是一個錯到 30 倍、而且長得完全正常的數字。
        """
        from ui.components.formula_card import BLOCKED_MARK, formula_card_html
        html = formula_card_html(
            title="台幣市值", formula="市值(TWD) = 市值(USD) × 匯率",
            steps=[
                {"label": "取匯率", "tokens": [("USDTWD", "plain")],
                 "result": None, "missing": "匯率來源未回應"},
                {"label": "換算", "tokens": [("1000", "value")],
                 "result": 31000, "result_suffix": " TWD"},
                {"label": "合計", "tokens": [], "result": 31000},
            ])
        assert "缺：匯率來源未回應" in html
        assert html.count(BLOCKED_MARK) == 2, "下游步驟沒有被擋住"
        assert "31000" not in html, "上游缺值，下游竟然還算出了數字"
        assert "1.0" not in html, "出現了頂替用的預設值"

    def test_all_present_steps_compute_normally(self):
        from ui.components.formula_card import BLOCKED_MARK, formula_card_html
        html = formula_card_html(
            title="配息殖利率", formula="殖利率 = 近12月配息 ÷ 現時淨值",
            steps=[{"label": "代入", "tokens": [("0.48", "value")],
                    "result": "4.12", "result_suffix": "%"}])
        assert "4.12%" in html and BLOCKED_MARK not in html

    def test_source_warn_token_has_amber_left_border(self):
        """手動輸入／估算值 → **視覺**揭露（左側 2px 琥珀邊），不只靠文字。"""
        from ui.components.formula_card import (
            KIND_SOURCE_WARN, KIND_VALUE, substitution_token,
        )
        warn = substitution_token("31.05", kind=KIND_SOURCE_WARN)
        plain = substitution_token("31.05", kind=KIND_VALUE)
        assert f"border-left:2px solid {WARN_AMBER}" in warn
        assert "border-left" not in plain

    def test_source_warn_without_notes_raises(self):
        """標了「這格可疑」卻不說可疑在哪 → 比不標更糟，故 raise。"""
        from ui.components.formula_card import formula_card_html
        with pytest.raises(ValueError, match="source_notes"):
            formula_card_html(
                title="t", formula="f",
                steps=[{"label": "l", "tokens": [("31.05", "source_warn")],
                        "result": 1}],
                source_notes=())

    def test_source_notes_always_carry_warning_mark(self):
        """來源註腳**必帶 ⚠**（元件自動補，不靠呼叫端記得）。"""
        from ui.components.formula_card import formula_card_html
        html = formula_card_html(
            title="t", formula="f",
            steps=[{"label": "l", "tokens": [("31.05", "source_warn")], "result": 1}],
            source_notes=["匯率為手動輸入"])
        assert "⚠ 匯率為手動輸入" in html

    def test_blocked_steps_do_not_trigger_source_warn_requirement(self):
        """被擋住的步驟不渲染 token → 不應反過來要求 source_notes。"""
        from ui.components.formula_card import formula_card_html
        html = formula_card_html(
            title="t", formula="f",
            steps=[{"label": "a", "tokens": [], "result": None, "missing": "x"},
                   {"label": "b", "tokens": [("v", "source_warn")], "result": 1}])
        assert "缺：x" in html

    def test_formula_card_has_no_streamlit_dependency(self):
        """純字串元件：**零 streamlit**（連 lazy import 都沒有）。"""
        code = _code_only("ui/components/formula_card.py")
        assert "streamlit" not in code


# ══════════════════════════════════════════════════════════════
# ⑥ allocation_donut_card
# ══════════════════════════════════════════════════════════════
def _summary(**over):
    d = {"total_twd": 100000.0, "core_twd": 70000.0, "sat_twd": 30000.0,
         "core_pct": 70.0, "sat_pct": 30.0, "n_funds": 4, "n_core": 2, "n_sat": 2,
         "n_tier_from_sheet": 4, "n_missing_amount": 0, "is_amount_weighted": True,
         "target_pct": 60.0, "diff_pct": 10.0}
    d.update(over)
    return d


class TestAllocationDonutCard:
    def test_no_amounts_means_no_donut(self):
        """**絕不**在全數沒填本金時畫圓環（畫了就是 0%/0% 的假圖）。"""
        from ui.components.allocation_donut_card import build_allocation_donut
        assert build_allocation_donut(_summary(
            is_amount_weighted=False, core_pct=None, sat_pct=None,
            core_twd=0.0, sat_twd=0.0, total_twd=0.0)) is None
        assert build_allocation_donut(None) is None

    def test_empty_state_says_it_is_not_absence_of_core(self, spy):
        from ui.components.allocation_donut_card import render_allocation_donut_card
        render_allocation_donut_card(
            _summary(is_amount_weighted=False, core_pct=None, core_twd=0.0,
                     sat_twd=0.0, total_twd=0.0),
            warn_pct=5.0, crit_pct=10.0)
        assert spy.charts == [], "沒填本金卻畫了圓環"
        assert "這不代表真的沒有核心資產" in spy.all_text

    def test_donut_always_has_exactly_two_slices(self):
        """**絕不**做多切片（N 檔=N 片但只 2 色 → 同色 wedge 糊成一片不可讀）。"""
        from ui.components.allocation_donut_card import build_allocation_donut
        fig = build_allocation_donut(_summary(n_funds=40, n_core=25, n_sat=15))
        assert len(fig.data) == 1
        assert len(fig.data[0].values) == 2
        assert list(fig.data[0].marker.colors) == [MD_BLUE_300, MATERIAL_ORANGE]

    def test_all_core_keeps_the_zero_satellite_slice(self):
        """全核心 → **仍是 2 片**，0 那片走 GRAY_44。

        刪掉會讓「沒有衛星」看起來像「沒有衛星這個分類」。
        """
        from ui.components.allocation_donut_card import build_allocation_donut
        fig = build_allocation_donut(_summary(
            core_twd=100000.0, sat_twd=0.0, core_pct=100.0, sat_pct=0.0,
            n_core=4, n_sat=0))
        assert len(fig.data[0].values) == 2
        assert list(fig.data[0].values) == [100000.0, 0.0], "0 值被塞了假的 epsilon"
        assert list(fig.data[0].marker.colors) == [MD_BLUE_300, GRAY_44]
        assert "衛星 0 檔" in list(fig.data[0].labels)

    def test_missing_amount_funds_are_footnoted(self):
        """`n_missing_amount > 0` → 圓環照畫，但**必列**「N 檔不在比例裡」。"""
        from ui.components.allocation_donut_card import (
            build_allocation_donut, build_footnotes,
        )
        s = _summary(n_missing_amount=3)
        assert build_allocation_donut(s) is not None
        notes = " ".join(build_footnotes(s))
        assert "3 檔" in notes and "不在這個比例裡" in notes

    def test_no_target_shows_dash_not_zero(self, spy):
        """`target_pct is None` → 偏差顯示 `—` + 「未設定目標」，**絕不**假設一個目標。"""
        from ui.components.allocation_donut_card import render_allocation_donut_card
        render_allocation_donut_card(_summary(target_pct=None, diff_pct=None),
                                     warn_pct=5.0, crit_pct=10.0)
        joined = spy.all_text
        assert "未設定目標" in joined
        assert "與目標偏差" in joined
        assert "0.0pp" not in joined and "+0.0" not in joined

    def test_deviation_thresholds_are_parameters_not_hardcoded(self):
        """三個門檻**絕不**寫死在元件內（目前無後端常數 SSOT）。"""
        import inspect

        from ui.components.allocation_donut_card import (
            deviation_level, render_allocation_donut_card,
        )
        code = _code_only("ui/components/allocation_donut_card.py")
        assert "5.0" not in code and "10.0" not in code, "門檻被寫死在元件裡"
        for fn in (deviation_level, render_allocation_donut_card):
            params = inspect.signature(fn).parameters
            assert params["warn_pct"].default is inspect.Parameter.empty
            assert params["crit_pct"].default is inspect.Parameter.empty

    def test_deviation_level_bands(self):
        from ui.components.allocation_donut_card import deviation_level
        kw = dict(warn_pct=5.0, crit_pct=10.0)
        assert deviation_level(3.0, **kw) == "ok"
        assert deviation_level(-3.0, **kw) == "ok"
        assert deviation_level(7.0, **kw) == "warn"
        assert deviation_level(10.0, **kw) == "warn"
        assert deviation_level(12.0, **kw) == "bad"
        assert deviation_level(None, **kw) == "unknown"

    def test_component_does_not_recompute_the_summary(self):
        """**絕不**自行加總／分類（那是 allocation.summarize_core_satellite 的事）。"""
        code = _code_only("ui/components/allocation_donut_card.py")
        for token in ("resolve_core_flag", "invest_twd\"", "policy_tier"):
            assert token not in code
