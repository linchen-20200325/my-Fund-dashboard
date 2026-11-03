# -*- coding: utf-8 -*-
"""🌍 Preview 頁的字樣查表：**已核准字樣取規則表、尚未核准的暫時字樣集中在這一個檔**（BL-0536 rendering 批）。

規則：
- 客戶 2026-11-03 已裁示的正式字樣（`DEC-2026-11-03-07`）住 `shared/ui_semantics/rules.py::APPROVED_WORDING`，**單一來源、不在這裡重複**；
  `text()`／`span()` 先查規則表、再查本檔，畫面上已核准字樣**不帶** `data-pending-wording` 與虛線底線。
- 本檔只剩**尚未核准**的暫時字樣（`PREVIEW_PENDING_WORDING`，status 恆為 `pending`）。已核准的鍵不得同時留在本檔
  （守衛 `tests/ui_v3/test_ui_v3_preview_wording_guard.py` 鎖：兩表鍵不重疊；暫時字樣不得與規則表任何已核准字樣相同）。
- 已核准的狀態符號與字樣（◆ ◇ ⬜ ⛔ ◷ 與其句型）一律取規則表 `ENTRIES`，**不在這裡重複**。
- 每一條暫時字樣都帶 `source`（81 線框「擬：」、ui_v2 既有字樣沿用、或執行組暫擬）；畫面上以 `pending_span()` 輸出時帶
  `data-pending-wording="<key>"` 屬性，機器可辨識。客戶定字後搬進規則表並自此刪除對應列。

⚠️ 本檔的字樣為**執行組暫擬／沿用**，可被客戶推翻；「沿用 ui_v2」者的核准狀態**未查證**。
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
from types import MappingProxyType
from typing import Mapping

from shared.ui_semantics import rules

STATUS_PENDING = "pending"

_SRC_81 = "81 第 3.1 節「擬：」（PENDING，待客戶定字）"
_SRC_UIV2 = "沿用 ui_v2 既有字樣（核准狀態未查證）"
_SRC_EXEC = "執行組暫擬（Preview 用；可被客戶推翻）"
_SRC_SHELL = "客戶 2026-11-03 Shell 要求列舉（尚未入規則表，待客戶定字）"


@dataclass(frozen=True)
class PendingWording:
    key: str
    text: str
    source: str
    status: str = STATUS_PENDING

    def __post_init__(self) -> None:
        if not self.key or not self.text.strip():
            raise ValueError("key 與 text 不得為空")
        if self.status != STATUS_PENDING:
            raise ValueError("Preview 暫時字樣的 status 只能是 pending（定字後請移進規則表並刪除這一列）")


def _w(key: str, text: str, source: str) -> PendingWording:
    return PendingWording(key, text, source)


_LIST = (
    # 首屏欄位名「市場狀態」「是否需注意」已核准（`field_market_state`／`field_attention`，規則表）；原合併列標籤 `status_row_label`
    # 於客戶 2026-11-03 首屏採 C 後移除（DEC-2026-11-03-09：兩列各自有欄位標籤）。
    _w("evidence_single_note", "只含這一條序列自身的視窗，未與另一條比較", _SRC_EXEC),
    # Primary
    _w("title_compare", "台股 vs S&P 500（歸一化）", _SRC_81 + "；標題字樣 PENDING"),
    _w("view_label", "檢視", _SRC_81),
    _w("period_label", "期間", _SRC_EXEC),
    _w("series_taiex", "台股", _SRC_UIV2),
    _w("series_sp500", "S&P 500", _SRC_UIV2),
    _w("series_vix", "VIX", _SRC_UIV2),
    _w("data_date_no_elapsed", "{label} 資料日 {date}", _SRC_EXEC),
    _w("negative_elapsed_suffix", "取得時間早於觀測日", _SRC_UIV2 + "；字首 `⬜ 不適用` 取規則表（BACKLOG H2 adapter 要求 (1)）"),
    _w("insufficient_effect", "此期間比序列涵蓋範圍長，未縮短冒充", _SRC_EXEC),
    _w("fetch_failed_effect", "此序列未畫出", _SRC_EXEC + "；`⛔ <中文資料類> 取數失敗` 句型取規則表"),
    _w("window_withheld_note", "兩條序列在這個期間內無法在同一基準日比較（{reason}）", _SRC_EXEC),
    _w("reason_missing", "缺資料", _SRC_EXEC),
    _w("reason_fetch_failed", "取數失敗", _SRC_EXEC + "；取數失敗≠缺資料，不併入「缺資料」"),
    _w("reason_not_configured", "尚未設定", _SRC_EXEC),
    _w("reason_no_common", "沒有共同有效觀測日", _SRC_EXEC),
    _w("reason_few_common", "共同有效觀測日不足", _SRC_EXEC),
    _w("reason_few_points", "有效點數不足", _SRC_EXEC),
    # 來源與限制
    _w("source_limits_title", "▸ 來源與限制", _SRC_81),
    _w("limits_taiex", "台股來源為 Yahoo Finance ^TWII（非 TWSE 官方）；只作指數價格，不延伸成交量與市場統計", "`DEC-2026-10-27-43` 既有說明"),
    _w("limits_obs_date", "資料日為觀測日；取得時間為本頁取數時間，不是公布時間", _SRC_EXEC),
    _w("fetched_at_line", "{label} 取得時間 {stamp}（台北時間）", _SRC_EXEC),
    _w("source_line", "{label} 來源 {source}", _SRC_EXEC),
    # Secondary
    _w("secondary_vix_title", "風險｜VIX", _SRC_UIV2),
    _w("secondary_rates_title", "利率與信用", _SRC_UIV2),
    _w("rates_term_spread", "期限利差", _SRC_UIV2),
    _w("rates_credit_spread", "信用利差", _SRC_UIV2),
    _w("rates_policy_rate", "政策利率", _SRC_UIV2),
    _w("rates_obs_note", "資料日為 FRED 觀測日（不是公布日）；利差單位為百分點（pp），政策利率單位為百分比（%）", _SRC_UIV2),
    _w("secondary_latest", "最新 {value}{unit}", _SRC_EXEC),
    _w("secondary_spark_caption", "近 1Y 走勢", _SRC_EXEC),
    # 依據卡
    _w("evidence_card_1", "MKT-1 風險情緒", _SRC_UIV2),
    _w("evidence_card_2", "MKT-2 景氣位置", _SRC_UIV2),
    _w("evidence_card_3", "MKT-3 資金與匯率", _SRC_UIV2),
    _w("evidence_no_rule_note", "僅列已取得的觀測值，沒有正式規則可判定", _SRC_EXEC),
    # 尚未取得／各項狀態
    _w("missing_group_title", "▸ 尚未取得（{n} 項）", _SRC_81),
    _w("status_group_title", "▸ 各項資料狀態", _SRC_81),
    _w("missing_taiex_volume", "台股成交量", _SRC_UIV2),
    _w("missing_market_stats", "市場統計", _SRC_UIV2),
    _w("missing_nasdaq", "NASDAQ", _SRC_UIV2),
    _w("missing_msci_world", "MSCI World", _SRC_UIV2),
    _w("missing_msci_em", "MSCI EM", _SRC_UIV2),
    _w("missing_eps_pe", "EPS×PE 情境", _SRC_UIV2),
    _w("missing_implied_earnings", "implied trailing 盈餘", _SRC_UIV2),
    # 版面連接字樣（原硬寫在頁面程式內）
    _w("colon", "：", _SRC_EXEC),
    _w("separator", " ｜ ", _SRC_EXEC),
    _w("label_colon", "{label}：", _SRC_EXEC),
    _w("evidence_period_change", "近{period} {change}", _SRC_EXEC),
    _w("chart_aria", "{title}（{period}）", _SRC_EXEC),
    _w("status_ok_row", "{label}：取得 ｜ 來源 {source} ｜ 資料日 {date}", _SRC_EXEC),
    # 全站 Navigation Shell（BL-0536 Shell 批；客戶 2026-11-03 Shell 要求列舉的字樣尚未入規則表 → 全部 pending）。
    # 五頁完整頁名已核准（80 第 7 節／`shell/registry.py`），不在這裡；這裡只有 Shell 自己的字樣。
    _w("shell_app_title", "基金投資儀表板", _SRC_SHELL),
    _w("shell_nav_short_mkt", "市場", _SRC_SHELL),
    _w("shell_nav_short_ast", "資產", _SRC_SHELL),
    _w("shell_nav_short_exp", "找基金", _SRC_SHELL),
    _w("shell_nav_short_ai", "AI", _SRC_SHELL),
    _w("shell_nav_short_set", "設定", _SRC_SHELL),
    _w("shell_nav_aria", "主要導覽", _SRC_EXEC),
    _w("shell_nav_soon", "開發中", _SRC_SHELL),
    _w("shell_preview_tag", "PREVIEW", _SRC_SHELL),
    _w("shell_preview_tip", "Preview｜非正式頁面", _SRC_SHELL),
    _w("shell_status_counts", "{ok}／{total} 項取得", _SRC_EXEC),
    _w("shell_status_partial", "部分資料缺失（{ok}／{total} 項取得）", _SRC_EXEC),
    _w("shell_status_none", "主要資料缺失（0／{total} 項取得）", _SRC_EXEC),
    _w("shell_status_failed_note", "其中 {n} 項取數失敗", _SRC_EXEC),
    _w("shell_updated", "更新：{time}", _SRC_SHELL),
    _w("shell_data_status_label", "資料狀態", _SRC_SHELL),
    _w("shell_updated_label", "最後更新時間", _SRC_SHELL),
    _w("shell_refresh_cta", "更新資料", _SRC_SHELL),
    _w("shell_refresh_unavailable", "預覽版尚未開放更新資料", _SRC_EXEC),
    # 頁級
    _w("preview_banner", "Preview 預覽（非正式頁面）：字樣標有虛線底線者為暫時字樣，待客戶定字", _SRC_EXEC),
)

def _index(items) -> Mapping[str, PendingWording]:
    table = {w.key: w for w in items}
    if len(table) != len(items):  # 重複鍵＝寫錯
        raise ValueError("PREVIEW_PENDING_WORDING 有重複鍵")
    return MappingProxyType(table)


PREVIEW_PENDING_WORDING: Mapping[str, PendingWording] = _index(_LIST)


def text(key: str, **fields: object) -> str:
    """取字樣（先規則表的正式字樣、再暫時字樣）並代入欄位；未知鍵 → KeyError（不猜）。"""
    if key in rules.APPROVED_WORDING:
        template = rules.APPROVED_WORDING[key].text
    else:
        template = PREVIEW_PENDING_WORDING[key].text
    return template.format(**fields) if fields else template


def is_approved(key: str) -> bool:
    return key in rules.APPROVED_WORDING


def pending_span(key: str, **fields: object) -> str:
    """畫面用 HTML：暫時字樣加 `data-pending-wording` 屬性與虛線底線（機器與人眼都可辨識）。已核准的鍵不得走這裡。"""
    if key in rules.APPROVED_WORDING:
        raise KeyError(f"{key!r} 已是正式字樣，請用 span()（不得再標 pending）")
    return f'<span class="uv3-pending" data-pending-wording="{escape(key)}">{escape(text(key, **fields))}</span>'


def span(key: str, **fields: object) -> str:
    """畫面用 HTML：正式字樣＝純文字（不加虛線、不標 pending）；暫時字樣＝`pending_span`。呼叫端不需知道它核准了沒有。"""
    if key in rules.APPROVED_WORDING:
        return escape(text(key, **fields))
    return pending_span(key, **fields)


def span_html(key: str, **html_fields: str) -> str:
    """同 `span`，但欄位值是**已跳脫的 HTML 片段**（例如巢狀的暫時字樣）；模板本身仍會跳脫。"""
    if key in rules.APPROVED_WORDING:
        template = rules.APPROVED_WORDING[key].text
    else:
        template = PREVIEW_PENDING_WORDING[key].text
    return escape(template).format(**html_fields)
