"""ui/components/cards.py — GitHub-style 卡片外框 chrome SSOT(v19.273 Phase 2 TOP 2)。

PHASE1_AUDIT_DELTA.md TOP 2:3 處 inline `<div style=background:GH_BG_CARD;border:...>`
卡片外框 chrome 重複(色票已 v19.254 SSOT,剩 radius/padding/margin/extra boilerplate)。

設計:
- 純字串 helper,零 streamlit / plotly / pandas 依賴(只 shared.colors L0)
- byte-identical 輸出 → 收斂 3 callsite 0 視覺變化
- 卡片**內容**各 callsite 自建(3 種不同 layout:banner / σ表 / empty-state),
  本 helper 只統一**外框 chrome**(GH_BG_CARD bg + GH_BORDER border + 圓角)
"""
from __future__ import annotations

from shared.colors import GH_BG_CARD, GH_BORDER


def gh_card(
    inner_html: str,
    *,
    radius: int = 10,
    padding: str = "14px 18px",
    margin: str = "8px 0",
    extra: str = "",
) -> str:
    """組 GitHub-style 卡片外框 HTML(SSOT)。

    輸出 `<div style='background:{GH_BG_CARD};border:1px solid {GH_BORDER};
    border-radius:{radius}px;padding:{padding}[;margin:{margin}][;{extra}]'>{inner}</div>`。

    Args
    ----
    inner_html : str   卡片內容 HTML(callsite 自建)
    radius     : int   圓角 px(預設 10)
    padding    : str   CSS padding(預設 "14px 18px")
    margin     : str   CSS margin(預設 "8px 0";傳 "" 則省略 margin 宣告)
    extra      : str   附加 CSS(如 "display:flex;...";傳 "" 則不附加)

    Returns
    -------
    str  完整 `<div>...</div>` HTML 字串,供 `st.markdown(..., unsafe_allow_html=True)`。
    """
    parts = [
        f"background:{GH_BG_CARD}",
        f"border:1px solid {GH_BORDER}",
        f"border-radius:{radius}px",
        f"padding:{padding}",
    ]
    if margin:
        parts.append(f"margin:{margin}")
    if extra:
        parts.append(extra)
    style = ";".join(parts)
    return f"<div style='{style}'>{inner_html}</div>"
