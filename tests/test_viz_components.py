"""V2 可視化元件骨幹單元測試 (v19.388)。

重點(總監指令:資料誠信):元件**不得遺失或竄改傳入的數據** —— signed_bar 保留原 y
(含 None 不變 0)、stat_tile 原樣呈現 value(None→「—」)、狀態色對映正確不錯置。
"""
from __future__ import annotations

from shared.colors import (
    GH_BG_CARD, TRAFFIC_GREEN, TRAFFIC_NEUTRAL, TRAFFIC_RED, TRAFFIC_YELLOW,
)
from ui.components.chart_factory import (
    HEIGHTS, PLOTLY_CONFIG, apply_dark_template, signed_bar_fig, sparkline_fig,
)
from ui.components.stat_tile import stat_tile
from ui.components.status import status_chip, status_color, status_hex


class TestStatusColor:
    def test_aliases_map_to_traffic_ssot(self):
        assert status_color("good").hex == TRAFFIC_GREEN
        assert status_color("GREEN").hex == TRAFFIC_GREEN     # 大小寫容錯
        assert status_color("warn").hex == TRAFFIC_YELLOW
        assert status_color("critical").hex == TRAFFIC_RED
        assert status_color("fail").hex == TRAFFIC_RED
        assert status_color("unknown").hex == TRAFFIC_NEUTRAL

    def test_unrecognized_falls_back_unknown(self):
        s = status_color("???")
        assert s.level == "unknown" and s.hex == TRAFFIC_NEUTRAL

    def test_every_status_ships_emoji_and_label(self):
        # dataviz #4:狀態恆帶 icon + label,不靠顏色單獨編碼
        for lv in ("ok", "warn", "caution", "bad", "unknown"):
            s = status_color(lv)
            assert s.emoji and s.label

    def test_status_hex_shortcut(self):
        assert status_hex("bad") == TRAFFIC_RED

    def test_status_chip_has_icon_and_hex(self):
        html = status_chip("配息覆蓋", "ok", sublabel="96%")
        assert "🟢" in html and TRAFFIC_GREEN in html and "配息覆蓋" in html and "96%" in html


class TestChartFactory:
    def test_apply_dark_template_unifies_surface(self):
        import plotly.graph_objects as go
        fig = go.Figure(go.Scatter(y=[1, 2, 3]))
        apply_dark_template(fig, height="standard")
        assert fig.layout.paper_bgcolor == GH_BG_CARD
        assert fig.layout.plot_bgcolor == GH_BG_CARD
        assert fig.layout.height == HEIGHTS["standard"]

    def test_legend_toggle(self):
        import plotly.graph_objects as go
        f1 = apply_dark_template(go.Figure(go.Bar(y=[1])), legend=False)
        assert f1.layout.showlegend is False
        f2 = apply_dark_template(go.Figure(go.Bar(y=[1])), legend=True)
        assert f2.layout.showlegend is True

    def test_config_hides_modebar(self):
        assert PLOTLY_CONFIG["displayModeBar"] is False

    def test_sparkline_transparent_and_axisless(self):
        fig = sparkline_fig([1.0, 2.0, 1.5])
        assert fig.layout.paper_bgcolor == "rgba(0,0,0,0)"
        assert fig.layout.xaxis.visible is False and fig.layout.yaxis.visible is False
        assert list(fig.data[0].y) == [1.0, 2.0, 1.5]   # 值不遺失


class TestSignedBarDataIntegrity:
    """§1:依號上色、缺值留缺口、且**保留原 y 不竄改**。"""

    def test_values_preserved_exactly_including_none(self):
        y = [5.1, -3.2, None, 0.0]
        fig = signed_bar_fig(["A", "B", "C", "D"], y)
        got = list(fig.data[0].y)
        assert got == [5.1, -3.2, None, 0.0]   # None 保留、不變 0(反造假)

    def test_color_follows_sign(self):
        fig = signed_bar_fig(["A", "B", "C", "D"], [5.1, -3.2, None, 0.0])
        colors = list(fig.data[0].marker.color)
        # 正→綠 / 負→紅 / None→缺口灰 / 0.0→綠(0>=0,設計選擇)
        assert colors == [TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_NEUTRAL, TRAFFIC_GREEN]

    def test_nan_treated_as_gap_not_red(self):
        # QA 前瞻:V3 接真實 pandas df 時 NaN 缺口不可被誤上紅色(§1)
        fig = signed_bar_fig(["A", "B"], [float("nan"), -2.0])
        assert list(fig.data[0].marker.color) == [TRAFFIC_NEUTRAL, TRAFFIC_RED]

    def test_has_zero_baseline(self):
        fig = signed_bar_fig(["A"], [1.0])
        assert any(getattr(s, "y0", None) == 0 for s in fig.layout.shapes)


class TestStatTileDataIntegrity:
    def test_value_rendered_verbatim(self):
        html = stat_tile("1.42", "Sharpe", status="ok")
        assert "1.42" in html and "Sharpe" in html and TRAFFIC_GREEN in html

    def test_missing_value_shows_dash_not_zero(self):
        # None → 值區顯示「—」(§1 誠實),不假造 0/健康讀數
        html = stat_tile(None, "最大回撤", status="unknown")
        assert "—" in html
        assert ">0<" not in html and ">0.0<" not in html  # 值區未渲染假 0

    def test_status_rail_uses_correct_color(self):
        assert TRAFFIC_RED in stat_tile("-18%", "回撤", status="bad")
        assert TRAFFIC_GREEN in stat_tile("96%", "覆蓋", status="ok")
