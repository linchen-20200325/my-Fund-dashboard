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
    # 頁級 FAKE 標示（Gate-M 方案 2a：頁級＋卡級永久可見；兩者皆暫行字樣，待客戶／設計者定字）
    _w("page_fake_banner", "FAKE 模擬頁：以下全部是離線測試資料，沒有查詢任何真實來源"),
    _w("page_fake_hint", "可輸入的 FAKE 示範代碼：{codes}"),
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
    # ── NAV／輔助判定 sibling（A-EXP-NAV-SIBLING-FAKE-1；全部暫行字樣，待客戶／設計者定字）──
    _w("nav_section", "淨值（原幣）"),
    _w("nav_row_value", "最新淨值"),
    _w("nav_row_date", "觀測日"),
    _w("nav_row_source", "來源"),
    _w("nav_row_cache", "快取更新時間"),
    _w("nav_row_supplier", "原始供應者擷取時間"),
    _w("nav_supplier_unknown", "未知"),
    _w("nav_row_ccy_declared", "自報幣別（不視為淨值幣別）"),
    _w("nav_row_ccy_at", "幣別自報時間"),
    _w("nav_time_differ", "資料時間不同：依欄位分別標示"),
    _w("nav_row_dividend", "配息資料"),
    _w("nav_div_missing", "未取得"),
    _w("nav_div_present", "有配息"),
    _w("nav_div_none", "無配息（事實）"),
    _w("nav_withheld_conflict", "淨值已扣下：資料互相矛盾"),
    _w("nav_withheld_not_admitted", "淨值已扣下：來源准入未通過"),
    _w("nav_missing", "淨值：尚無可顯示的值"),
    _w("nav_diag", "診斷"),
    _w("nav_diag_dates", "NAV 最早日 {a}／宣告成立日 {b}"),
    _w("nav_diag_t0", "NAV 日期與宣告成立日不一致"),
    _w("nav_row_reasons", "未通過准入"),
    _w("nr_input_conflict", "資料互相矛盾"),
    _w("nr_identity_unverified", "基金身分尚未核證"),
    _w("nr_class_unverified", "基金級別尚未核證"),
    _w("nr_rights_unverified", "權利未核證"),
    _w("nr_source_untraceable", "來源無法追溯"),
    _w("nr_ccy_source_unclear", "幣別來源不明"),
    _w("judge_section", "輔助判定（非建議）"),
    _w("judge_row_333", "3-3-3"),
    _w("judge_row_eating", "吃本金"),
    _w("judge_pass_333", "通過 3-3-3"),
    _w("judge_fail_333", "未達 3-3-3"),
    _w("judge_pass_eating", "含息報酬不低於配息率（未吃本金）"),
    _w("judge_fail_eating", "含息報酬低於配息率（吃本金）"),
    _w("judge_eating_na", "吃本金：不適用"),
    _w("mr_input_conflict", "無法判定原因：資料互相矛盾"),
    _w("mr_identity_unverified", "無法判定原因：基金身分尚未核證"),
    _w("mr_rights_unverified", "無法判定原因：衍生計算權利未核證"),
    _w("mr_nav_not_admitted", "無法判定原因：淨值未通過准入"),
    _w("mr_dividend_not_obtained", "無法判定原因：配息資料未取得"),
    _w("mr_history_short", "無法判定原因：3 年年化未取得（序列不足）"),
    _w("mr_inception_missing", "無法判定原因：缺成立日"),
    _w("mr_return_1y_missing", "無法判定原因：缺 1 年含息報酬"),
    _w("mr_proxy_input", "無法判定原因：成立年數為推估值"),
    _w("mr_stale", "無法判定原因：資料偏舊"),
    _w("mr_required_input_missing", "無法判定原因：必要輸入缺失"),
    _w("fold_why", "為什麼／來源／限制"),
    _w("fold_missing", "尚未取得"),
    _w("fold_none", "無"),
    _w("limit_withheld", "淨值未顯示：資料互相矛盾或來源未通過准入；本頁不判斷誰對，也不修正任何一邊。"),
    _w("limit_verified", "淨值已通過身分、來源、權利、用途四項准入。判定只在輸入完整且已准入時才計算；公式本身未改。"),
    _w("limit_ai", "AI 使用權：未核證（不得供 AI 讀取）"),
    _w("miss_nav", "淨值可信度"),
    _w("miss_dividend", "配息序列"),
    _w("miss_return_3y", "3 年配息還原年化"),
    _w("miss_rights", "權利核證"),
    _w("miss_class", "級別核證"),
    _w("slot_title", "OneBrain 解釋：未啟用"),
    _w("slot_body", "此位置之後只會顯示有來源、有反面證據的短結論；目前不產生任何 AI 結論。"),
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
