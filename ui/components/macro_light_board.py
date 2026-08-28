"""ui/components/macro_light_board.py — 總經 16 盞燈 + 對帳徽章看板（UI3b）。

本元件存在的理由，一句話：**把「這個數字有沒有被第二種算法驗過」畫進看板本身。**

背景（§4.3 重算對帳 / F-RECON-1）
--------------------------------
Data Guard 的 16 盞燈（12 FRED + 4 Yahoo，數量由 `shared` 端 SSOT 釘死、
`tests/test_d5_macro_ssot_v195.py::test_total_count_is_16` 守著）在畫面上**長得完全一樣**：
每一盞都是「一個數字 + 一顆燈」。但其中只有 **US10Y** 有第二演算法可對帳，
其餘 15 盞是**單源** —— 抓到什麼就是什麼，沒有任何東西在旁邊說「這個數字我也算了一次」。

看板不講這件事的話，使用者會把 16 盞燈當成同一種可信度。**它們不是。**
所以本元件的**第三列（對帳徽章列）與常駐腳註是強制的**，不是裝飾。

⚠️ 常駐腳註不可關、不可收合（本元件的誠實前提）
------------------------------------------------
腳註寫的是「16 盞中只有 US10Y 有第二演算法可對帳，其餘為單源；
**單源不代表錯，代表沒有被第二種算法驗過**」。
把它做成 expander／可關閉開關 = 讓「預設看不到」變成常態 —— 那等於沒寫。
`tests/test_ui3b_components.py::TestMacroLightBoard` 以字串守住它一定在輸出裡。

⚠️ 為什麼不用 `st.columns`
--------------------------
16 格用 `st.columns(16)` 在窄螢幕會退化成**16 列垂直長條**（每格一行），
看板的「一眼掃過去」完全消失。故用**單一 markdown 內的 CSS flex-wrap**
（`flex:1 1 140px;min-width:140px`），寬螢幕自動排多欄、窄螢幕自動折行成 2~3 欄。

§1 Fail Loud
------------
- 主數字 `None` → 顯示 `—`，**不是 0**（0 是一個會被拿去判讀的值）。
- `lights` 長度 != 16 → **raise**。不補格、不截斷 —— 悄悄補 3 個 `—` 出來，
  畫面會長得像「16 盞都在、只是有幾盞沒資料」，而真相是「上游少給了 3 盞」。
- 全 16 盞皆 `None` 時**仍畫滿 16 格**：此時格子本身就是資訊（「一個都沒抓到」）。
  這與「還沒按載入」是兩件事 —— 後者請由呼叫端走
  `ui.helpers.render_state.not_ready(..., where=...)`，不要進本元件。

⛔ **禁止 `degraded=True`**：本看板產出的是使用者要拿去判讀的**數值**，
不是「掉了一張圖」。呼叫端若要包 try，一律 `system_error(..., degraded=False)`。

純函式邊界
----------
`build_macro_light_board_html()` / `build_recon_badge_html()` 為**純字串函式**
（只依賴 `shared.colors` L0 與 `ui.components.status`），零 streamlit、零 session_state、
零 cache、零 repository/service import、零網路。`render_macro_light_board()` 是唯一
碰 streamlit 的薄殼（只 `st.markdown` + `st.caption`）。
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from shared.colors import (
    GH_BORDER,
    GH_FG_MUTED,
    GH_FG_PRIMARY,
    TRAFFIC_GREEN,
    TRAFFIC_NEUTRAL,
    TRAFFIC_RED,
    TRAFFIC_YELLOW,
)
from ui.components.cards import gh_card
from ui.components.status import status_color

# 16 = 12 FRED + 4 Yahoo。**不是可調參數** —— 與 D5_KEYS 同一個事實，
# 上游要加指標請先改 SSOT，再讓這裡跟著紅。
EXPECTED_LIGHT_COUNT: int = 16

# 缺值符號：與 `ui/helpers/render_state.py` 的 ⬜ 家規同源。
MISSING_VALUE_MARK: str = "—"

# 對帳徽章四態 → (emoji, 文字, 色)。**唯一**的對帳視覺對映表。
# key 直接吃 `services/reconcile.py::reconcile_pair` 的 `status` 字串，不另建詞彙。
_RECON_BADGE: dict[str, tuple[str, str, str]] = {
    "agree":        ("✅", "雙源一致", TRAFFIC_GREEN),
    "disagree":     ("⚠️", "雙源不符", TRAFFIC_RED),
    "a_missing":    ("🟡", "單邊缺",   TRAFFIC_YELLOW),
    "b_missing":    ("🟡", "單邊缺",   TRAFFIC_YELLOW),
    "both_missing": ("⬜", "單源",     TRAFFIC_NEUTRAL),
}
# `recon is None`（這盞燈根本沒有第二演算法）與 `both_missing` 同視覺：都是「單源」。
_RECON_SINGLE_SOURCE: tuple[str, str, str] = _RECON_BADGE["both_missing"]

# 常駐腳註。**不可關、不可收合**（見模組 docstring）。
FOOTNOTE_TEXT: str = (
    "⬜ 對帳說明：16 盞燈目前只有 **US10Y** 有第二種演算法可交叉驗算（§4.3 重算對帳），"
    "其餘 15 盞為**單源** —— 抓到什麼就顯示什麼。"
    "**單源不代表錯，代表這個數字沒有被第二種算法驗過。**"
)


def _esc(text: Any) -> str:
    """最小 HTML 逸出（值來自上游資料，不預設它乾淨）。"""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def build_recon_badge_html(recon: Mapping[str, Any] | None) -> str:
    """對帳徽章 HTML（純字串）。

    `recon` 直接吃 `services/reconcile.py` 的回傳 dict（讀 `status` 欄）。
    `None`（本盞燈沒有第二演算法）／`both_missing`／無法識別的 status
    一律落到 **⬜ 單源** —— 未知不得冒充「一致」。
    """
    if not recon:
        emoji, text, color = _RECON_SINGLE_SOURCE
    else:
        status = str(recon.get("status") or "").strip().lower()
        emoji, text, color = _RECON_BADGE.get(status, _RECON_SINGLE_SOURCE)
    return (f"<div style='font-size:11px;color:{color};margin-top:4px;"
            f"display:flex;align-items:center;gap:4px'>{emoji} {_esc(text)}</div>")


def _build_cell_html(light: Mapping[str, Any]) -> str:
    """單盞燈的格子 HTML：標籤 / 主數字 / 狀態列 / 對帳徽章列。"""
    label = _esc(light.get("label") or light.get("key") or "")
    value = light.get("value")
    suffix = _esc(light.get("suffix") or "")
    # §1：None → 「—」，不是 0。0 會被當成一個真的觀測值拿去判讀。
    value_txt = MISSING_VALUE_MARK if value is None else f"{_esc(value)}{suffix}"
    s = status_color(light.get("level"))
    return (
        f"<div style='flex:1 1 140px;min-width:140px;background:transparent;"
        f"border:1px solid {GH_BORDER};border-radius:9px;padding:8px 12px;"
        f"display:flex;flex-direction:column;gap:2px'>"
        f"<div style='font-size:11px;color:{GH_FG_MUTED}'>{label}</div>"
        f"<div style='font-size:22px;font-weight:700;color:{GH_FG_PRIMARY};"
        f"line-height:1.15;font-variant-numeric:tabular-nums'>{value_txt}</div>"
        f"<div style='font-size:11px;color:{s.hex}'>{s.emoji} {_esc(s.label)}</div>"
        f"{build_recon_badge_html(light.get('recon'))}"
        f"</div>")


def build_macro_light_board_html(
    lights: Sequence[Mapping[str, Any]],
    health: tuple[Any, str] | None = None,
) -> str:
    """16 盞燈看板 HTML（純字串，可單元測試）。

    Parameters
    ----------
    lights : 長度**必須** == 16 的 list[dict]。每筆可帶：
             `label` / `key`（標題）、`value`（主數字，None → `—`）、`suffix`（單位）、
             `level`（`status_color` 可識別的 level）、
             `recon`（`reconcile_pair` 回傳 dict 或 None）。
    health : `(score, level)`；`None` = 不顯示健康度標頭。
             `score is None` → 顯示 `—`（不捏 0）。

    Raises
    ------
    ValueError : `lights` 長度 != 16。**刻意不補、不截斷**（見模組 docstring）。
    """
    n = len(lights)
    if n != EXPECTED_LIGHT_COUNT:
        raise ValueError(
            f"總經燈板固定 {EXPECTED_LIGHT_COUNT} 盞（12 FRED + 4 Yahoo），收到 {n} 盞。"
            "本元件刻意不自動補格／截斷 —— 補出來的空格會讓「上游少給了幾盞」"
            "長得像「這幾盞剛好沒資料」。請修正上游來源清單（D5_KEYS SSOT）。")

    head = ""
    if health is not None:
        score, level = health
        hs = status_color(level)
        score_txt = MISSING_VALUE_MARK if score is None else _esc(score)
        head = (f"<div style='display:flex;align-items:baseline;gap:8px;margin-bottom:8px'>"
                f"<span style='font-size:11px;color:{GH_FG_MUTED}'>總經健康度</span>"
                f"<span style='font-size:22px;font-weight:700;color:{hs.hex};"
                f"font-variant-numeric:tabular-nums'>{score_txt}</span>"
                f"<span style='font-size:12.5px;color:{hs.hex}'>{hs.emoji} "
                f"{_esc(hs.label)}</span></div>")

    cells = "".join(_build_cell_html(lt or {}) for lt in lights)
    grid = (f"<div style='display:flex;flex-wrap:wrap;gap:8px;"
            f"align-items:stretch'>{cells}</div>")
    return gh_card(head + grid)


def render_macro_light_board(
    lights: Sequence[Mapping[str, Any]],
    health: tuple[Any, str] | None = None,
) -> None:
    """薄殼：畫看板 + **常駐**腳註。腳註不接受任何開關參數（刻意的）。"""
    import streamlit as st  # lazy：讓純函式部分可在無 streamlit 環境測試

    st.markdown(build_macro_light_board_html(lights, health), unsafe_allow_html=True)
    st.caption(FOOTNOTE_TEXT)
