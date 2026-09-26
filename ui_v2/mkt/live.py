# -*- coding: utf-8 -*-
"""市場總覽正式模式才有的畫面調整（純函式；不 import streamlit、不 import 舊樹）。

依據：客戶 2026-09-26 核准的文字線框草稿（正式入口 `ui_v2/app_mkt_live.py`）。
全部只在正式模式生效；示範模式（`ui_v2/app_mkt.py`）不經過本檔，一個字都不變。

1. 頁首只留提問句 —— 在 `page.py` 處理，本檔不涉。
2. 失敗訊息經過遮蔽（`ui_v2/mkt/source.py` 呼叫 L2 遮蔽）後，含遮蔽記號的訊息在下一行加註 `MASKED_NOTE`。
3. 資料未備的值，下一行寫原因（`REASON_TEXT`，依 L2 交出的原因代碼對照）。
4. 「存檔」停用並寫出原因；in-memory 說明與 updated_at 那一行不顯示（在 `page.py` 處理）。
5. 「重新取數」停用並寫出原因；來源冷卻中時改寫剩餘秒數。
6. 不新增「舊資料」字樣（本檔沒有這一條文案；新鮮度照舊由「延遲 N 日」交代）。

⚠️ 文案逐字照草稿；改字要先回草稿（`CLAUDE.md` §-1.5.4）。
"""

from __future__ import annotations

import copy
import math

from . import logic

MASKED_NOTE = "已遮蔽憑證"
SAVE_DISABLED_REASON = "設定存檔尚未接上，存了也留不到下次開頁"
RETRY_DISABLED_REASON = "重新取數尚未接上"

# 原因代碼（L2 `services/v2_tables/market_indicator.py` 的 PENDING_*）→ 畫面文案。
REASON_TEXT = {
    "fred_release_date": "原因：公布日尚未接上，暫不寫入",
    "ndc_no_release_date": "原因：來源不提供公布日",
    "fx_obs_date_rule": "原因：觀測日切日規則待以真實資料驗證",
}

_CARD_CODES = ("MKT-1", "MKT-2", "MKT-3")


def cooldown_reason(cooldowns) -> str | None:
    """列出剩餘秒數最長的那一個來源，再加一句另有幾個；沒有冷卻中的來源回 None。"""
    live = [c for c in cooldowns or () if c.get("remaining_sec", 0) > 0]
    if not live:
        return None
    top = max(live, key=lambda c: c["remaining_sec"])
    text = f"來源冷卻中：{top['source']}，約剩 {math.ceil(top['remaining_sec'])} 秒"
    others = len(live) - 1
    if others:
        text += f"，另有 {others} 個來源冷卻中"
    return text


def _walk_buttons(node):
    if isinstance(node, dict):
        if "_action_kind" in node:
            yield node
        for value in node.values():
            yield from _walk_buttons(value)
    elif isinstance(node, (list, tuple)):
        for value in node:
            yield from _walk_buttons(value)


def apply_live_notes(model: dict, notes: dict) -> dict:
    """回傳調整過的模型複本（不改呼叫端手上的那一份）。

    notes：`{"pending": {鍵: 原因代碼}, "masked_keys": [鍵...], "cooldowns": [...]}`。
    未知的原因代碼當場 KeyError —— 沒有核准文案的原因不上畫面（§1：不自行編原因）。
    """
    out = copy.deepcopy(model)
    pending = dict(notes.get("pending", {}))
    masked = set(notes.get("masked_keys", ()))

    for code in _CARD_CODES:
        block = logic.find_block(out, code)
        for mv in block["main_values"]:
            key = mv["_source_key"]
            lines = []
            if mv["_state"] == logic.STATE_MISSING and key in pending:
                lines.append(REASON_TEXT[pending[key]])
            if mv["_state"] == logic.STATE_ERROR and key in masked:
                lines.append(MASKED_NOTE)
            if lines:
                mv["note_lines"] = lines

    mkt7 = logic.find_block(out, "MKT-7")
    for row in mkt7["_rows"]:
        key = row["indicator_key"]
        if key in pending and any(b.get("text") == logic.STATE_MISSING for b in row["badges"]):
            mkt7["detail_lines"].append(f"{key}　{REASON_TEXT[pending[key]]}")

    retry_reason = cooldown_reason(notes.get("cooldowns")) or RETRY_DISABLED_REASON
    for button in _walk_buttons(out["blocks"]):
        if button["_action_kind"] == "取數":
            button["_enabled"] = False
            button["disabled_reason"] = retry_reason
        elif button["_action_kind"] == "存檔":
            button["_enabled"] = False
            button["disabled_reason"] = SAVE_DISABLED_REASON
    return out
