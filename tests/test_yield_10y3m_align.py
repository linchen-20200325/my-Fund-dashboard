"""v19.195 A2 — 10Y-3M 殖利率曲線評分對齊 10Y-2Y(三段)。

跨站審查發現:基金原本 10Y-3M 用 binary `>0 → +2`,把曲線轉平(0~0.5)當滿分多頭,
且與同卡的 signal/color(已用 0.5/0 三段)矛盾、與 10Y-2Y 及台股危險線不一致。
本修正改三段:>0.5 多頭(+2) / 0~0.5 轉平中性(0) / <0 倒掛(-2)。
"""
from __future__ import annotations


class TestScoreRule:
    def test_10y3m_three_zone(self):
        from services.macro_validation import SCORE_RULES
        _w, fn = SCORE_RULES["YIELD_10Y3M"]
        assert fn(0.8) == 2.0, "正斜率 >0.5 → 多頭 +2"
        assert fn(0.3) == 0.0, "轉平 0~0.5 → 中性 0(原 bug 給 +2)"
        assert fn(0.0) == 0.0, "剛好 0 → 中性"
        assert fn(-0.2) == -2.0, "倒掛 <0 → -2"

    def test_10y3m_matches_10y2y_shape(self):
        """10Y-3M 與 10Y-2Y 同三段形狀(都用 0.5 / 0 邊界)。"""
        from services.macro_validation import SCORE_RULES
        _, fn3m = SCORE_RULES["YIELD_10Y3M"]
        _, fn2y = SCORE_RULES["YIELD_10Y2Y"]
        for v in (0.8, 0.3, 0.0, -0.2):
            assert fn3m(v) == fn2y(v), f"10Y-3M 與 10Y-2Y 在 v={v} 應同分"


class TestProductionAligned:
    def test_macro_service_10y3m_not_binary(self):
        """production fetch_all_indicators 的 10Y-3M score 不得再是 binary `>0`。

        B1 v19.205 / P1-7:services/macro_service.py 已拆 services/macro/ 子套件。
        """
        import glob as _g
        src = "\n".join(open(p, encoding="utf-8").read()
                        for p in sorted(_g.glob("services/macro/*.py")))
        assert "score=2 if v>0 else -2,\n                weight=2, series=sp3m)" not in src, \
            "10Y-3M 仍是 binary score(未對齊)"
        # 三段版存在(緊鄰 sp3m 區塊)
        assert "score=2 if v>0.5 else (-2 if v<0 else 0),\n                weight=2, series=sp3m)" in src
