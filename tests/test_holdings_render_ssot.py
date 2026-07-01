"""v19.282 test — 持股明細共用渲染器(SSOT)。

Tab2 單一基金 + 組合健檢原各有一份 byte-identical 持股渲染 → 抽 SSOT
`ui.helpers.holdings.render_holdings_detail` / `render_holdings_diag`,兩處共用。
本檔守共用 render 契約(有資料渲染 / 空回 False / diag 攤開)。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import streamlit


def test_render_holdings_detail_empty_returns_false():
    from ui.helpers.holdings import render_holdings_detail
    assert render_holdings_detail({}) is False
    assert render_holdings_detail({"sector_alloc": [], "top_holdings": []}) is False


def test_render_holdings_detail_renders_sectors_and_tops():
    """有資料 → 渲染產業 + 前十大 + 中文對照,回 True。"""
    from ui.helpers.holdings import render_holdings_detail
    holdings = {
        "sector_alloc": [{"name": "資訊科技", "pct": 40.0}],
        "top_holdings": [{"name": "NVIDIA CORP", "pct": 6.5, "sector": "IT"}],
    }
    md_calls: list = []
    with patch.object(streamlit, "columns",
                      return_value=(MagicMock(), MagicMock())), \
         patch.object(streamlit, "markdown",
                      side_effect=lambda *a, **k: md_calls.append(a[0] if a else "")):
        ok = render_holdings_detail(holdings)
    assert ok is True
    blob = "\n".join(str(x) for x in md_calls)
    assert "資訊科技" in blob, "應渲染產業配置"
    assert "NVIDIA" in blob, "應渲染前十大持股"
    assert "輝達" in blob, "應帶中文對照(_zh_holding)"
    assert "6.5%" in blob


def test_render_holdings_diag_expands_diag_lines():
    """空持股 diag → st.code 攤開逐源結果。"""
    from ui.helpers.holdings import render_holdings_diag
    cap: list = []
    code: list = []
    with patch.object(streamlit, "caption",
                      side_effect=lambda *a, **k: cap.append(a[0] if a else "")), \
         patch.object(streamlit, "code",
                      side_effect=lambda *a, **k: code.append(a[0] if a else "")):
        render_holdings_diag({"diag": [
            "MoneyDJ｜16 候選 URL 全失敗",
            "cnyes｜TLZF9/portfolio 200 但無持股 keys=['x']",
        ]})
    assert any("三源" in c for c in cap)
    assert code and "cnyes" in code[0] and "MoneyDJ" in code[0]


def test_render_holdings_diag_no_diag_hints_old_version():
    """無 diag → 提示線上仍舊版(引導 Reboot)。"""
    from ui.helpers.holdings import render_holdings_diag
    cap: list = []
    with patch.object(streamlit, "caption",
                      side_effect=lambda *a, **k: cap.append(a[0] if a else "")), \
         patch.object(streamlit, "code", side_effect=lambda *a, **k: None):
        render_holdings_diag({"source": "—"})
    assert any("舊版" in c or "Reboot" in c for c in cap)
