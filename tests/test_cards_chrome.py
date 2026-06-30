"""v19.273 Phase 2 TOP 2 — gh_card chrome SSOT byte-identical 守門。

確認 gh_card() 對 3 個 migrate callsite 的輸出與原 inline HTML **完全 byte-identical**,
保證 0 視覺變化。任何未來改動破壞輸出格式 → 立即 fail。
"""
from __future__ import annotations

from shared.colors import GH_BG_CARD, GH_BORDER, GRAY_55
from ui.components.cards import gh_card


def test_site1_tab2_signal_banner():
    """tab2_single_fund.py:359 策略3 訊號 banner(radius10 + flex extra + margin8)。"""
    inner = "INNER"
    out = gh_card(inner, radius=10, padding="14px 18px", margin="8px 0",
                  extra="display:flex;align-items:center;gap:16px;flex-wrap:wrap")
    expected = (
        f"<div style='background:{GH_BG_CARD};border:1px solid {GH_BORDER};"
        f"border-radius:10px;padding:14px 18px;margin:8px 0;"
        f"display:flex;align-items:center;gap:16px;flex-wrap:wrap'>INNER</div>"
    )
    assert out == expected


def test_site2_tab2_sigma_card():
    """tab2_single_fund.py:564 σ 買賣點卡(radius10 + 無 extra + margin10)。"""
    inner = "INNER"
    out = gh_card(inner, radius=10, padding="12px 16px", margin="10px 0")
    expected = (
        f"<div style='background:{GH_BG_CARD};border:1px solid {GH_BORDER};"
        f"border-radius:10px;padding:12px 16px;margin:10px 0'>INNER</div>"
    )
    assert out == expected


def test_site3_inflection_empty_state():
    """tab1_macro_inflection.py:248 持倉紅綠燈 empty-state(radius8 + 無 margin + color extra)。"""
    inner = "INNER"
    out = gh_card(inner, radius=8, padding="10px 16px", margin="",
                  extra=f"color:{GRAY_55};font-size:12px;text-align:center")
    expected = (
        f"<div style='background:{GH_BG_CARD};border:1px solid {GH_BORDER};"
        f"border-radius:8px;padding:10px 16px;"
        f"color:{GRAY_55};font-size:12px;text-align:center'>INNER</div>"
    )
    assert out == expected


def test_defaults():
    """預設參數:radius10 / padding 14px 18px / margin 8px 0 / 無 extra。"""
    out = gh_card("X")
    expected = (
        f"<div style='background:{GH_BG_CARD};border:1px solid {GH_BORDER};"
        f"border-radius:10px;padding:14px 18px;margin:8px 0'>X</div>"
    )
    assert out == expected


def test_empty_margin_omits_margin_decl():
    out = gh_card("X", margin="")
    assert "margin:" not in out


def test_empty_extra_no_trailing_semicolon():
    out = gh_card("X")
    # margin:8px 0 結尾後直接 '> ,無多餘分號
    assert out.endswith("margin:8px 0'>X</div>")
