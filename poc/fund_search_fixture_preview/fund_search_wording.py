# -*- coding: utf-8 -*-
"""🔍 找一檔基金／依條件篩選｜隔離式 FAKE Preview 的字樣（全部暫行，待客戶定字）。

- 已核准字樣**一律取規則表**（`shared/ui_semantics/rules.py`）：`missing`（◇ 資料未備）、`undetermined`（⬜ 無法判定）、
  `fetch_failed`（⛔ 取數失敗）、`insufficient`（資料不足）。本檔**不得**複寫它們的字串。
- EXP-0 的結論文案（含「尚未設定條件」）取 `ui_v3.viewmodels.exp_counts`，本檔不重造。
- 其餘新字樣全是 `PendingWording`（status 恆為 pending），出處一律標 `SOURCE`；畫面上以 `data-pending-wording` 與虛線底線標記。
"""
from __future__ import annotations

from html import escape
from types import MappingProxyType
from typing import Mapping

from shared.ui_semantics import rules
from ui_v3.viewmodels.preview_wording import PendingWording

SOURCE = "ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行"


def _w(key: str, text: str) -> PendingWording:
    return PendingWording(key, text, SOURCE)


_LIST = (
    # 上區：找一檔基金
    _w("page_title", "找一檔基金"),
    _w("input_label", "MoneyDJ 基金代碼或 ISIN"),
    _w("isin_note", "ISIN：尚未啟用（目前沒有已核准的 ISIN 對照來源）"),
    _w("submit_label", "查詢"),
    _w("isin_inactive_result", "ISIN 目前未啟用"),
    _w("isin_inactive_detail", "未用 ISIN 取數、未猜測任何代碼"),
    _w("fake_tag", "FAKE 模擬"),
    _w("row_result", "查詢結果"),
    _w("result_found", "找到模擬項目（FAKE）"),
    _w("suffix_unrecognized", "（無法辨識格式）"),
    _w("suffix_no_fixture", "（離線預覽沒有這個代碼的模擬資料）"),
    _w("fail_impact", "無法顯示這檔基金"),
    _w("fail_not_identity", "這次取數失敗，不是對基金身份的判斷"),
    _w("row_input_code", "輸入代碼"),
    _w("row_identity", "基金身份"),
    _w("identity_unconfirmed", "◇ 尚未確認"),
    _w("single_note", "單檔查詢結果（唯讀；不會加入選股池或任何清單）"),
    _w("row_name", "基金名稱"),
    _w("row_inception", "成立日"),
    _w("row_dividend_mode", "配息方式"),
    _w("row_mgmt_fee", "經理費率"),
    _w("details_title", "基本資料｜尚未取得｜來源與限制"),
    _w("row_source", "來源"),
    _w("row_fallback", "備援來源"),
    _w("row_asof", "資料日"),
    _w("not_obtained_note", "尚未取得：來源、備援來源、資料日的值尚未接線"),
    _w("limits_note", "本畫面為離線 FAKE 模擬，不是 MoneyDJ 或任何正式來源的資料；沒有發出任何請求"),
    # 下區：依條件篩選
    _w("section_exp_title", "依條件篩選"),
    _w("exp0_title", "篩選結果"),
    _w("exp1_title", "本次瀏覽暫時條件"),
    _w("exp1_note", "這些條件只在本次瀏覽生效，離開本頁後會清除"),
    _w("cond_label", "FAKE 條件 {n}"),
    _w("exp2_title", "結果清單"),
    _w("exp7_title", "篩選軌跡"),
    _w("exp_fail_impact", "此區無法顯示篩選結果"),
    _w("col_matched", "符合"),
    _w("col_undetermined", "無法判定"),
    _w("col_code", "基金代碼"),
    _w("col_name", "基金名稱"),
    _w("col_ccy", "幣別"),
    _w("col_nav_date", "最近淨值日"),
    _w("col_nav", "最近淨值"),
    _w("col_div", "近 12 個月配息佔淨值比"),
    _w("col_cond", "條件"),
    _w("col_before", "套用前檔數"),
    _w("row_undetermined_suffix", "（資料未備）"),
)


def _index(items) -> Mapping[str, PendingWording]:
    table = {w.key: w for w in items}
    if len(table) != len(items):
        raise ValueError("FUND_SEARCH_PENDING 有重複鍵")
    return MappingProxyType(table)


FUND_SEARCH_PENDING: Mapping[str, PendingWording] = _index(_LIST)

# 規則表鍵（已核准字樣）：missing／undetermined／fetch_failed 是狀態列（含符號）；insufficient 是純文字正式字樣。
RULE_STATUS_KEYS = ("missing", "undetermined", "fetch_failed")
RULE_PLAIN_KEYS = ("insufficient",)


def text(key: str, **fields: object) -> str:
    """暫行字樣取字（未知鍵 → KeyError，不猜）。"""
    template = FUND_SEARCH_PENDING[key].text
    return template.format(**fields) if fields else template


def pending(key: str, **fields: object) -> str:
    """畫面用 HTML：暫行字樣加 `data-pending-wording` 與虛線底線。"""
    return f'<span class="uv3-pending" data-pending-wording="{escape(key)}">{escape(text(key, **fields))}</span>'


def status(key: str) -> str:
    """畫面用 HTML：規則表的狀態列字樣（◇／⬜／⛔ 加字）。"""
    if key not in RULE_STATUS_KEYS:
        raise KeyError(f"{key!r} 不是本預覽使用的規則表狀態列鍵")
    entry = rules.entry(key)
    return f'<span class="uv3-st uv3-st-{entry.tone}" data-status-key="{escape(key)}">{escape(entry.wording)}</span>'


def plain(key: str) -> str:
    """畫面用 HTML：規則表的純文字正式字樣。"""
    if key not in RULE_PLAIN_KEYS:
        raise KeyError(f"{key!r} 不是本預覽使用的規則表純文字鍵")
    return f'<span data-approved-wording="{escape(key)}">{escape(rules.APPROVED_WORDING[key].text)}</span>'
