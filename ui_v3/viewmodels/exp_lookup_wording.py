# -*- coding: utf-8 -*-
"""單檔基金查詢呈現元件｜字樣（既有隔離預覽字樣的複本；Gate-M M-copy 第一段；全部暫行，待客戶／設計者定字）。

授權：`DEC-2026-11-18-04`（要點轉述，來源待核，NOT VERIFIED）。本檔的**新字樣一律是 `PendingWording`**（status 恆為 pending），
出處一律標 `SOURCE`；畫面上以 `data-pending-wording` 與虛線底線標記。

- 已核准字樣**不複寫**：狀態列符號與字樣（`⛔ 取數失敗`、`⬜ 無法判定`）一律經 `shared.ui_semantics.rules` 的 API 取得（`status()`），
  本檔沒有任何一個字串等於規則表已核准字樣（守衛逐條比對）。
- 缺值字樣**刻意不用符號**：`◇ 資料未備`（規則表 `missing`）只限正式模式，`⬜ 資料未備` 是 fund_search 預覽的 PendingWording（R2 待裁示）；
  本元件的缺值字樣是不帶符號的 `field_missing`，**不替客戶決定 ◇／⬜**（`DEC-2026-11-18-01` R2、`DEC-2026-11-18-04` (E5) 仍待裁）。
- 沒有任何字樣表達「基金不存在／查無」：取數失敗、頁面無法確認、入口攔截都不是對基金存在與否的結論，各有獨立文案。
"""
from __future__ import annotations

from html import escape
from types import MappingProxyType
from typing import Mapping

from shared.ui_semantics import rules
from ui_v3.viewmodels.preview_wording import PendingWording

SOURCE = "DEC-2026-11-18-04（轉述，待核）"


def _w(key: str, text: str) -> PendingWording:
    return PendingWording(key, text, SOURCE)


_LIST = (
    # 表單
    _w("page_title", "找一檔基金"),
    _w("input_label", "MoneyDJ 基金代碼或 ISIN"),
    _w("isin_note", "ISIN：尚未啟用（目前沒有已核准的 ISIN 對照來源）"),
    _w("submit_label", "查詢"),
    # 結果卡共用
    _w("not_queried", "尚未查詢"),
    _w("fake_tag", "FAKE 模擬"),
    _w("single_note", "單檔查詢結果（唯讀；不會加入選股池或任何清單）"),
    _w("not_identity", "這不是對基金身份的判斷"),
    # 五欄標籤（依客戶列出的順序）
    _w("row_input_code", "輸入代碼"),
    _w("row_name", "基金名稱"),
    _w("row_dividend_mode", "配息方式"),
    _w("row_inception", "成立日期"),
    _w("row_mgmt_fee", "經理費率"),
    # 欄位值
    _w("div_mode_distributing", "配息型"),
    _w("div_mode_accumulating", "累積型"),
    _w("field_missing", "此欄尚無可顯示的值"),
    _w("field_conflict", "此欄的來源值不一致，未選用任何一個"),
    # RESULT
    _w("state_result", "查詢結果（模擬資料）"),
    # SOURCE_FAILED（⛔ 取數失敗 取規則表；下列是補充說明）
    _w("failed_impact", "無法顯示這檔基金的欄位"),
    _w("failed_source_failed", "來源回報取數失敗"),
    _w("failed_source_cooling", "來源剛失敗，暫時冷卻中，請稍後再查"),
    _w("failed_loader_io_error", "取數連線失敗"),
    # PAGE_UNMATCHED（⬜ 無法判定 取規則表；下列是補充說明）
    _w("unmatched_impact", "頁面無法確認是這一檔，不顯示任何欄位"),
    _w("unmatched_unrecognized_page", "頁面格式無法辨識"),
    _w("unmatched_no_page", "找不到對應頁面"),
    _w("unmatched_source_not_listed", "來源沒有列出這一檔"),
    _w("unmatched_name_unconfirmed", "頁面上的基金名稱無法確認"),
    # BLOCKED（入口攔截；未發出任何查詢）
    _w("blocked_impact", "輸入未通過檢查，未發出查詢"),
    _w("blocked_blank", "請先輸入基金代碼"),
    _w("blocked_control_or_non_ascii", "輸入含不可顯示或非英數的字元"),
    _w("blocked_url_shape", "請輸入基金代碼，不要貼網址"),
    _w("blocked_isin_shape", "ISIN 目前未啟用"),
    _w("blocked_isin_detail", "未用 ISIN 取數、未猜測任何代碼"),
    _w("blocked_code_format", "代碼格式不符"),
    _w("blocked_key_rejected", "這個代碼無法用於查詢"),
)


def _index(items) -> Mapping[str, PendingWording]:
    table = {w.key: w for w in items}
    if len(table) != len(items):
        raise ValueError("FUND_LOOKUP_PENDING 有重複鍵")
    return MappingProxyType(table)


FUND_LOOKUP_PENDING: Mapping[str, PendingWording] = _index(_LIST)

#: 本元件使用的規則表狀態列鍵（已核准字樣；符號＋字樣都取規則表，本檔不複寫）。
RULE_STATUS_KEYS = ("undetermined", "fetch_failed")


def text(key: str, **fields: object) -> str:
    """暫行字樣取字（未知鍵 → KeyError，不猜）。"""
    template = FUND_LOOKUP_PENDING[key].text
    return template.format(**fields) if fields else template


def pending(key: str, **fields: object) -> str:
    """畫面用 HTML：暫行字樣加 `data-pending-wording` 與虛線底線。"""
    return f'<span class="uv3-pending" data-pending-wording="{escape(key)}">{escape(text(key, **fields))}</span>'


def status(key: str) -> str:
    """畫面用 HTML：規則表的狀態列字樣（符號＋字樣取自規則表，tone 取自規則表）。"""
    if key not in RULE_STATUS_KEYS:
        raise KeyError(f"{key!r} 不是本元件使用的規則表狀態列鍵")
    entry = rules.entry(key)
    return f'<span class="uv3-st uv3-st-{entry.tone}" data-status-key="{escape(key)}">{escape(entry.wording)}</span>'
