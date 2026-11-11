# -*- coding: utf-8 -*-
"""Design token（80 第 5 節 Design Contract；批 2b 命名，G3 批落值）。

- **值只有客戶核准的才有**：客戶對 G3 的裁示（經總管轉達；要點轉述，非逐字）＝**候選 B 的色票 ＋ 候選 A 的尺寸**
  （候選表見 `docs/evidence/fund_newui2_market_token_and_wireframe_proposal_2026_11_10.md` §A.5）。核准範圍內的 token 才有 `value`；
  其餘（`chart.*`、`state.*`、`cta.*`、`nav.*`，以及只指向別的 token 的 `color.status.*`（指向 tone）與 `meta.*`（指向 `type.caption`））仍為 None（`UNVALUED_BY_DESIGN`，測試鎖）。
  80 第 5 節的建議尺度原樣留在 `proposed`（`type.caption`：80 建議 12、核准值 13；`type.page`／`type.section`：80 建議 22／17、核准值
  現值 1.7rem／1.2rem —— 都是客戶核准的偏離，不改 `proposed`）。
- **唯一真相源**：`ui_v3/pages/mkt.py` 與 `ui_v3/shell/nav.py` 的 CSS 一律由本表經 `design/theme.py` 取值，不得另寫色碼或尺寸；
  `tests/ui_v3/test_ui_v3_design_tokens.py` 鎖「CSS 內出現的色碼都來自本表」。
- ⚠️ `.streamlit/config.toml` 是全 repo 共用（正式入口與 `ui_v2` 也讀它），G3 批**沒有改它**；Preview 的淺色主內容／深色側欄色票由 ui_v3 自己的 CSS
  覆寫（只在 ui_v3 頁面注入），所以 config.toml 的舊值（`#f6f8fa`／`#0e1117`／`#1f6feb`…）**只**對 Old UI／`ui_v2` 有效。
- 值的型別：尺寸＝帶單位字串（`"8px"`、`"1.7rem"`）；顏色＝`#rrggbb`；複合（card／chip／tone）＝唯讀 Mapping。
- 顏色 token 的語意色名鍵＝`shared/ui_semantics/rules.py::TONES` 的鍵（本層不 import 它，一致性由測試鎖）；顏色不是唯一訊息
  （狀態 chip 必有符號＋字樣，見規則表）。`STATUS_TONES` 對映與狀態語意**未動**。
- 本檔不放業務字樣、不放 CSS；只用標準函式庫；import 時零副作用。
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Dict, Optional, Tuple

_SRC_80_5 = "80 §5 Design Contract"
_SRC_G3 = "G3 核准值（候選 B 色票＋候選 A 尺寸；evidence #1204 §A.5；客戶經總管轉達）"
_SRC_NG4 = "NG-4 A（DEC-2026-11-02-05：沿用狀態符號、語意色名、字樣規範；版面／元件／spacing／typography 重建）"


@dataclass(frozen=True)
class Token:
    """`name`：點分隔的語意名；`value`：客戶核准的值（未核准＝None，見 `UNVALUED_BY_DESIGN`）；`refers_to`：指向的另一個 token 名或 tone 鍵；
    `proposed`：80 第 5 節寫的建議尺度原字（屬提案，與核准值可以不同，不因 `value` 而改）。"""

    name: str
    source: str
    value: Optional[object] = None
    refers_to: Optional[str] = None
    proposed: Optional[str] = None


def _t(name: str, source: str = _SRC_80_5, proposed: Optional[str] = None, refers_to: Optional[str] = None,
       value: Optional[object] = None) -> Token:
    if isinstance(value, dict):
        value = MappingProxyType(dict(value))
    return Token(name=name, source=source, value=value, proposed=proposed, refers_to=refers_to)


# 80 §5 status chips 列的六個 chip kind（＝`ui_v3/viewmodels/components.py::CHIP_KINDS`）。
CHIP_TOKEN_KINDS = ("attention", "missing", "undetermined", "failed", "stale", "neutral")
# 語意色名鍵（＝`shared/ui_semantics/rules.py::TONES` 的鍵）。
TONE_KEYS = ("neutral", "grey", "yellow", "red")
# 規則表各列的 tone（＝`shared/ui_semantics/rules.py::ENTRIES` 中字樣已核准者的 key → tone；一致性由測試鎖）。
STATUS_TONES: Dict[str, str] = {
    "ok": "neutral",
    "attention": "neutral",
    "missing": "grey",
    "undetermined": "grey",
    "not_applicable": "grey",
    "fetch_failed": "red",
    "stale": "yellow",
    "threshold_pending": "grey",
    "neutral": "neutral",
    "not_configured": "red",
    "user_param_unset": "grey",
}

# ── G3 核准值（候選 B 色票＋候選 A 尺寸）──────────────────────────────────────────────────────
# 色票（淺色主內容＋深色側欄；`DEC-2026-10-27-09` 的視覺 theme 方向不變，深色主內容不在範圍）
PALETTE: Dict[str, str] = {
    "color.page.bg": "#f5f7fb",
    "color.surface": "#ffffff",
    "color.text.primary": "#172033",
    "color.text.secondary": "#4a5670",
    "color.primary": "#1a5fd0",
    "color.card.border": "#7f8ca6",
    "color.sidebar.bg": "#101a33",
    "color.sidebar.bg2": "#18254a",
    "color.sidebar.text": "#e6edf3",
    "color.sidebar.text2": "#aab6cf",
    "color.sidebar.accent": "#5fd3d0",
    "color.sidebar.border": "#34466e",
}
# 語意色：字／底／邊（neutral 與 grey 共用一組值；兩鍵是否需視覺區分屬客戶另行裁示，#1204 §A.6 第 5 點）
TONE_VALUES: Dict[str, Dict[str, str]] = {
    "neutral": {"text": "#172033", "background": "#e6eaf3", "border": "#7f8ca6"},
    "grey": {"text": "#172033", "background": "#e6eaf3", "border": "#7f8ca6"},
    "yellow": {"text": "#6b4a0a", "background": "#fbf0d6", "border": "#b7791f"},
    "red": {"text": "#8a1f12", "background": "#fbe6e2", "border": "#c0392b"},
}
# chip 形狀（候選 A：圓角 12、內距 1×10、字級 14；顏色由 tone 給）
_CHIP_SHAPE = {"radius": "12px", "padding": "1px 10px", "font_size": "14px"}
# 卡片（候選 A：邊 1px、內距 10×12、不收斂到 4px 基數；面色與邊色取 `color.surface`／`color.card.border`）
_CARD_SHAPE = {"border_width": "1px", "padding": "10px 12px"}

_TOKEN_LIST: Tuple[Token, ...] = (
    # spacing（80 §5：4px 基數；候選 A＝80 §5 的值）
    _t("space.1", source=_SRC_G3, proposed="4", value="4px"),
    _t("space.2", source=_SRC_G3, proposed="8", value="8px"),
    _t("space.3", source=_SRC_G3, proposed="12", value="12px"),
    _t("space.4", source=_SRC_G3, proposed="16", value="16px"),
    _t("space.6", source=_SRC_G3, proposed="24", value="24px"),
    _t("space.8", source=_SRC_G3, proposed="32", value="32px"),
    _t("gutter.mobile", source=_SRC_G3, proposed="16", value="16px"),
    # typography（候選 A＝現值：27≈1.7rem／19≈1.2rem／20／15／13；80 §5 建議 22／17／20／15／12 留在 `proposed`）
    _t("type.page", source=_SRC_G3, proposed="22", value="1.7rem"),
    _t("type.section", source=_SRC_G3, proposed="17", value="1.2rem"),
    _t("type.metric", source=_SRC_G3, proposed="20", value="20px"),
    _t("type.body", source=_SRC_G3, proposed="15", value="15px"),
    _t("type.caption", source=_SRC_G3, proposed="12", value="13px"),
    # card system
    _t("card.summary", source=_SRC_G3, value=_CARD_SHAPE),
    _t("card.chart", source=_SRC_G3, value=_CARD_SHAPE),
    _t("card.detail", source=_SRC_G3, value=_CARD_SHAPE),
    _t("radius.card", source=_SRC_G3, value="8px"),
    _t("elevation.none", source=_SRC_G3, value="none"),
    # status chips（符號＋字樣由規則表依 kind 給；顏色只是第三重）
    *(_t(f"chip.{kind}", source=_SRC_G3, value=_CHIP_SHAPE) for kind in CHIP_TOKEN_KINDS),
    # source／freshness display
    # （#1204 §A.5：`type.caption` 含 meta.*；故只指向 `type.caption`、自己沒有值）
    _t("meta.asof", refers_to="type.caption"),
    _t("meta.source", refers_to="type.caption"),
    _t("meta.freshness", refers_to="type.caption"),
    # chart container（比例沿用現行 SVG viewBox 360×240、最大寬 720；不另立 token 值）
    _t("chart.height.primary"),
    _t("chart.height.secondary"),
    _t("chart.period"),
    # empty／error／loading（80 §5「state.empty.*」：四空狀態沿用 44 —— 未設定／資料未備／取數失敗／無資料；
    # 後綴英文名屬內部命名）
    _t("state.empty.unconfigured"),
    _t("state.empty.missing"),
    _t("state.empty.failed"),
    _t("state.empty.no_data"),
    _t("state.loading"),
    # CTA hierarchy
    _t("cta.primary"),
    _t("cta.secondary"),
    _t("cta.link"),
    # mobile navigation
    _t("nav.bottom"),
    _t("nav.item"),
    # G3 色票（頁面／文字／primary／卡片邊線／側欄）
    *(_t(name, source=_SRC_G3, value=value) for name, value in PALETTE.items()),
    # 語意色名（NG-4 A）：tone 鍵；值＝字／底／邊（候選 B）
    *(_t(f"color.tone.{tone}", source=f"{_SRC_NG4}；{_SRC_G3}", value=TONE_VALUES[tone]) for tone in TONE_KEYS),
    # 狀態色：規則表每一列 → 指向一個 tone 鍵（不是色碼；自己沒有值）
    *(_t(f"color.status.{key}", source=f"{_SRC_NG4}；shared/ui_semantics/rules.py", refers_to=f"color.tone.{tone}")
      for key, tone in STATUS_TONES.items()),
)

TOKENS: Dict[str, Token] = {t.name: t for t in _TOKEN_LIST}
TOKEN_NAMES: Tuple[str, ...] = tuple(t.name for t in _TOKEN_LIST)
# 設計上沒有核准值的 token（G3 範圍之外，或只指向 tone 的 `color.status.*`）；測試鎖「有值者＝核准清單、其餘恆為 None」。
VALUED_NAMES: Tuple[str, ...] = tuple(t.name for t in _TOKEN_LIST if t.value is not None)
UNVALUED_BY_DESIGN: Tuple[str, ...] = tuple(t.name for t in _TOKEN_LIST if t.value is None)


def value(name: str) -> object:
    """取核准值；沒有值（或名字不存在）＝Fail Loud（不給預設，不回 None）。"""
    token = TOKENS[name]
    if token.value is None:
        raise ValueError(f"token {name!r} 沒有核准值（見 UNVALUED_BY_DESIGN）")
    return token.value
