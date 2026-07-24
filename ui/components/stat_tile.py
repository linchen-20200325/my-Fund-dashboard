"""ui/components/stat_tile.py — 統一 KPI tile 元件 (v19.388 V2)。

收斂目標(可視化稽核 ③):原「數字 + 狀態色」有 8 種手刻 HTML 風格(radius 混用
4/6/8/10/12/14px、padding 各異)外加 ~97 個 st.metric。本檔以既有 `gh_card` 為 chrome
基底,狀態色走 `status_color()`,提供單一 `stat_tile()`。

§1:value=None → 顯示「—」(誠實不足),**不假造 0**;傳入值原樣呈現、不竄改。
"""
from __future__ import annotations

from shared.colors import GH_FG_MUTED, GH_FG_PRIMARY
from ui.components.cards import gh_card
from ui.components.status import status_color


def stat_tile(value, label: str, *, status=None, sublabel: str = "",
              value_suffix: str = "") -> str:
    """回傳一個 KPI tile 的 HTML(caller 自行 `st.markdown(..., unsafe_allow_html=True)`)。

    value       : 主數字(None → 「—」,§1 誠實)。原樣呈現,不做四捨五入/竄改。
    label       : 上方小標。
    status      : status_color 可識別的 level(ok/warn/caution/bad/unknown);None = 不顯狀態。
    sublabel    : 狀態列文字(省略時用 status 的預設 label)。
    value_suffix: 數字後綴(如 "%")。
    """
    s = status_color(status) if status is not None else None
    rail = (f"<span style='position:absolute;left:0;top:0;bottom:0;width:3px;"
            f"background:{s.hex}'></span>" if s else "")
    val_txt = "—" if value is None else f"{value}{value_suffix}"
    if s:
        status_line = (f"<div style='font-size:11px;color:{s.hex};margin-top:2px'>"
                       f"{s.emoji} {sublabel or s.label}</div>")
    elif sublabel:
        status_line = f"<div style='font-size:11px;color:{GH_FG_MUTED};margin-top:2px'>{sublabel}</div>"
    else:
        status_line = ""
    inner = (
        f"{rail}"
        f"<div style='font-size:11px;color:{GH_FG_MUTED}'>{label}</div>"
        f"<div style='font-size:22px;font-weight:700;color:{GH_FG_PRIMARY};"
        f"line-height:1.15;font-variant-numeric:tabular-nums'>{val_txt}</div>"
        f"{status_line}")
    return gh_card(inner, radius=9, padding="12px 14px",
                   extra="position:relative;overflow:hidden;display:flex;flex-direction:column;gap:2px")
