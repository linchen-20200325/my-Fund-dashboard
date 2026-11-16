# -*- coding: utf-8 -*-
"""💼 我的資產頁 Preview 的**暫行**字樣（只供隔離式假資料 Preview 的 renderer 使用；暫行·未核准）。

與 `assets_page.py` 內的 `ASSETS_PENDING_WORDING`（狀態與原因句）分工：本檔只放 renderer 版面需要、但前者沒有的幾個標籤字樣。
每一條都是 `PendingWording`（status 恆為 pending、帶出處）；畫面上以 `data-pending-wording` 標記並帶虛線底線，客戶定字後搬進規則表並刪除該列。

出處（讀碼對照）：A20 四格標籤＝`docs/v2/82` 說明的「程式現行標籤（總資產、總損益、報酬、配息）」，即 `ui_v2/asset/overview.py` 的
`SUMMARY_LABELS`；82 明寫「四格標籤＝A20 現行標籤，不代表核准新文案」。其餘標籤取自 82 §11.9.4 線框的欄位名。
**一律暫行、未核准，可被客戶推翻；不新增任何狀態詞、符號或規則。**
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Mapping, Tuple

from ui_v3.viewmodels.assets_page import A20_CELL_CODES
from ui_v3.viewmodels.preview_wording import STATUS_PENDING, PendingWording

_SRC_LABEL = "docs/v2/82 摘要標籤說明（程式現行標籤；暫行、未核准、可被客戶推翻）"
_SRC_WIRE = "docs/v2/82 §11.9.4 線框欄位名（暫行、未核准、可被客戶推翻）"
_SRC_EXEC = "執行組暫擬（Preview 用；暫行、未核准）"

# A20 四格位置代碼 → 暫行標籤字樣鍵（順序＝`A20_CELL_CODES`）。
A20_LABEL_KEYS: Tuple[Tuple[str, str], ...] = tuple(zip(A20_CELL_CODES, (
    "label_total_assets", "label_total_pnl", "label_return", "label_dividend")))

_LIST = (
    PendingWording("label_total_assets", "總資產", _SRC_LABEL),
    PendingWording("label_total_pnl", "總損益", _SRC_LABEL),
    PendingWording("label_return", "報酬", _SRC_LABEL),
    PendingWording("label_dividend", "配息", _SRC_LABEL),
    PendingWording("a20_labels_note", "四格標籤為暫行字樣，尚未核准", _SRC_EXEC),
    PendingWording("a00_label", "來源", _SRC_WIRE),
    PendingWording("a10_title", "資產配置", _SRC_WIRE),
    PendingWording("a10_basis_label", "基準", _SRC_WIRE),
    PendingWording("separator", "｜", _SRC_WIRE),
)


def _index(items: Tuple[PendingWording, ...]) -> Mapping[str, PendingWording]:
    table = {w.key: w for w in items}
    if len(table) != len(items):
        raise ValueError("ASSETS_PREVIEW_WORDING 有重複鍵")
    for w in items:
        if w.status != STATUS_PENDING:
            raise ValueError(f"{w.key}: 暫行字樣的 status 只能是 pending")
    return MappingProxyType(table)


ASSETS_PREVIEW_WORDING: Mapping[str, PendingWording] = _index(_LIST)


def preview_wording(key: str) -> PendingWording:
    """查暫行字樣；未知鍵 KeyError（不猜）。"""
    return ASSETS_PREVIEW_WORDING[key]
