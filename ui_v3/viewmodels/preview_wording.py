# -*- coding: utf-8 -*-
"""🌍 Preview 頁的**暫時字樣**（BL-0536 rendering 批）：尚未經客戶核准的畫面字樣，集中在這一個檔。

規則：
- **只有 Preview App 用**；這些字樣**不是**呈現規則資料表（`shared/ui_semantics/rules.py`）的內容，也不得進該表
  （守衛 `tests/ui_v3/test_ui_v3_preview_wording_guard.py` 鎖：每一條都不得與規則表任何已核准字樣相同、規則表的 PENDING 列不得被這裡補字）。
- 已核准的狀態符號與字樣（◆ ◇ ⬜ ⛔ ◷ 與其句型）一律取規則表，**不在這裡重複**。
- 每一條都帶 `source`（它從哪來：81 線框「擬：」、ui_v2 既有字樣沿用、或執行組暫擬），以及 `status`：
  `pending`（待客戶定字）。畫面上以 `pending_span()` 輸出時帶 `data-pending-wording="<key>"` 屬性，機器可辨識。
- 客戶驗收 Preview 時，一次檢視 `PREVIEW_PENDING_WORDING` 全表即可定字或改字；定字後再搬進規則表並自此刪除對應列。

⚠️ 本檔的字樣為**執行組暫擬／沿用**，可被客戶推翻；「沿用 ui_v2」者的核准狀態**未查證**。
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
from types import MappingProxyType
from typing import Mapping

STATUS_PENDING = "pending"

_SRC_81 = "81 第 3.1 節「擬：」（PENDING，待客戶定字）"
_SRC_UIV2 = "沿用 ui_v2 既有字樣（核准狀態未查證）"
_SRC_EXEC = "執行組暫擬（Preview 用；可被客戶推翻）"


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
    # 首屏欄位名（81 第 3.1 節）
    _w("status_row_label", "市場狀態／是否需注意", _SRC_81),
    _w("hero_sentence", "暫無完整市場綜合判定（缺正式 aggregation rule）", _SRC_81 + "；`DEC-2026-10-27-41` 既有句"),
    _w("evidence_label", "重要依據", _SRC_81),
    _w("freshness_label", "資料新鮮度", _SRC_81),
    _w("evidence_single_note", "只含這一條序列自身的視窗，未與另一條比較", _SRC_EXEC),
    # Primary
    _w("title_compare", "台股 vs S&P 500（歸一化）", _SRC_81 + "；標題字樣 PENDING"),
    _w("view_label", "檢視", _SRC_81),
    _w("period_label", "期間", _SRC_EXEC),
    _w("view_compare", "比較", _SRC_81),
    _w("view_vix", "VIX", _SRC_81),
    _w("view_us10y", "美10Y", _SRC_81),
    _w("view_us2y", "美2Y", _SRC_81),
    _w("series_taiex", "台股", _SRC_UIV2),
    _w("series_sp500", "S&P 500", _SRC_UIV2),
    _w("series_vix", "VIX", _SRC_UIV2),
    _w("series_us10y", "美 10Y", _SRC_UIV2),
    _w("series_us2y", "美 2Y", _SRC_UIV2),
    _w("base_chip", "基準日 {date}＝{base}", _SRC_81 + "；normalized disclosure 最終 label 未核准"),
    _w("frequency_line", "頻率 日｜缺值不補、斷線", _SRC_81),
    _w("data_date_line", "{label} 資料日 {date}（經過 {days} 日）", _SRC_UIV2 + "；日期格式本批用 YYYY-MM-DD"),
    _w("data_date_no_elapsed", "{label} 資料日 {date}", _SRC_EXEC),
    _w("negative_elapsed_suffix", "取得時間早於觀測日", _SRC_UIV2 + "；字首 `⬜ 不適用` 取規則表（BACKLOG H2 adapter 要求 (1)）"),
    _w("insufficient", "資料不足", "81 第 4.1 節 S7／`DEC-2026-11-03-04` B2：「資料不足」最終畫面字樣未核准"),
    _w("insufficient_effect", "此期間比序列涵蓋範圍長，未縮短冒充", _SRC_EXEC),
    _w("chart_empty", "此圖目前沒有可畫的資料", "規則表 `chart_empty` 為 PENDING（BL-0536-W1）；整張圖無資料字樣未核准"),
    _w("fetch_failed_effect", "此序列未畫出", _SRC_EXEC + "；`⛔ <中文資料類> 取數失敗` 句型取規則表"),
    _w("single_chart_note", "僅畫這一條序列；另一條{reason}，未做比較", _SRC_EXEC),
    _w("fallback_note", "兩條序列都有資料，但{reason}；僅畫其中一條，不是比較", _SRC_EXEC),
    _w("window_withheld_note", "兩條序列在這個期間內無法在同一基準日比較（原因代碼：{code}）", _SRC_EXEC),
    _w("reason_missing", "缺資料", _SRC_EXEC),
    _w("reason_insufficient", "資料不足", _SRC_EXEC),
    _w("reason_stopped", "在此視窗內已停更", _SRC_EXEC),
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
    _w("fact_vix", "VIX", _SRC_UIV2),
    _w("fact_credit_spread", "信用利差", _SRC_UIV2),
    _w("fact_policy_rate", "政策利率", _SRC_UIV2),
    _w("fact_fx", "匯率（新臺幣／美元）", _SRC_UIV2),
    _w("fact_ndc", "景氣指標", _SRC_UIV2),
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
    """取暫時字樣並代入欄位；未知鍵 → KeyError（不猜）。"""
    return PREVIEW_PENDING_WORDING[key].text.format(**fields) if fields else PREVIEW_PENDING_WORDING[key].text


def pending_span(key: str, **fields: object) -> str:
    """畫面用 HTML：暫時字樣加 `data-pending-wording` 屬性與虛線底線（機器與人眼都可辨識）。"""
    return f'<span class="uv3-pending" data-pending-wording="{escape(key)}">{escape(text(key, **fields))}</span>'
