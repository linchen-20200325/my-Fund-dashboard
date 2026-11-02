# -*- coding: utf-8 -*-
"""Design token **命名**（80 第 5 節 Design Contract；批 2b）。**只有名字，沒有值。**

- 值一律 None：80 第 5 節的尺度是「建議尺度，屬提案」，第 12 節把 token 數值列為內部決定；NG-4 A（`DEC-2026-11-02-05`）
  只保留狀態符號、顏色語意與正式用字，layout／component／spacing／typography 重建 —— 視覺值待各頁 New UI2 wireframe
  核准後才定（`DEC-2026-10-27-09` 深色側欄屬已釋放的視覺 theme，不在此給值）。80 第 5 節的建議尺度原樣記在 `proposed`，
  **不套用**，只供日後定值時對照。
- 顏色 token 只指向**語意色名鍵**（`shared/ui_semantics/rules.py::TONES` 的鍵；本層不 import 它，一致性由測試鎖），
  不寫色碼；顏色不是唯一訊息（狀態 chip 必有符號＋字樣，見規則表）。
- 本檔不放業務字樣、不放 CSS；只用標準函式庫；import 時零副作用。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

_SRC_80_5 = "80 §5 Design Contract"
_SRC_NG4 = "NG-4 A（DEC-2026-11-02-05：沿用狀態符號、語意色名、字樣規範；版面／元件／spacing／typography 重建）"


@dataclass(frozen=True)
class Token:
    """`name`：點分隔的語意名；`value`：恆為 None（本批不定值）；`refers_to`：指向的另一個 token 名或 tone 鍵；
    `proposed`：80 第 5 節寫的建議尺度原字（屬提案，未套用）。"""

    name: str
    source: str
    value: Optional[object] = None
    refers_to: Optional[str] = None
    proposed: Optional[str] = None


def _t(name: str, source: str = _SRC_80_5, proposed: Optional[str] = None, refers_to: Optional[str] = None) -> Token:
    return Token(name=name, source=source, proposed=proposed, refers_to=refers_to)


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

_TOKEN_LIST: Tuple[Token, ...] = (
    # spacing（80 §5：4px 基數；建議尺度屬提案）
    _t("space.1", proposed="4"),
    _t("space.2", proposed="8"),
    _t("space.3", proposed="12"),
    _t("space.4", proposed="16"),
    _t("space.6", proposed="24"),
    _t("space.8", proposed="32"),
    _t("gutter.mobile", proposed="16"),
    # typography（80 §5：五級；建議 22／17／20／15／12 屬提案）
    _t("type.page", proposed="22"),
    _t("type.section", proposed="17"),
    _t("type.metric", proposed="20"),
    _t("type.body", proposed="15"),
    _t("type.caption", proposed="12"),
    # card system
    _t("card.summary"),
    _t("card.chart"),
    _t("card.detail"),
    _t("radius.card"),
    _t("elevation.none"),
    # status chips（符號＋字樣由規則表依 kind 給；顏色只是第三重）
    *(_t(f"chip.{kind}") for kind in CHIP_TOKEN_KINDS),
    # source／freshness display
    _t("meta.asof"),
    _t("meta.source"),
    _t("meta.freshness"),
    # chart container
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
    # 語意色名（NG-4 A）：tone 鍵；值待視覺重建
    *(_t(f"color.tone.{tone}", source=_SRC_NG4) for tone in TONE_KEYS),
    # 狀態色：規則表每一列 → 指向一個 tone 鍵（不是色碼）
    *(_t(f"color.status.{key}", source=f"{_SRC_NG4}；shared/ui_semantics/rules.py", refers_to=f"color.tone.{tone}")
      for key, tone in STATUS_TONES.items()),
)

TOKENS: Dict[str, Token] = {t.name: t for t in _TOKEN_LIST}
TOKEN_NAMES: Tuple[str, ...] = tuple(t.name for t in _TOKEN_LIST)
