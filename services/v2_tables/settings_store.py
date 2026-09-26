# -*- coding: utf-8 -*-
"""設定與取數紀錄的 L2 入口（set 頁第 1、2 步；docs/v2/50_settings_sheet_design.md）。

ui_v2 只經由 `ui_v2/<頁>/source.py` 碰到本檔（`49` §3.3 方案 A），本檔再呼叫
L1 `repositories/settings_sheet_repository.py`。本檔做兩件事：

1. **把遮蔽接上 L1**：L1 不得 import 本套件（上行），所以 L1 每個公開函式都要求 `mask`；
   本檔把 `masking.mask_message(訊息, 秘密值)` 包成 `mask` 交下去。秘密值由 L3 讀好傳進來
   （`masking.py` 檔頭：L2 不讀 secrets）。
2. **第 2 步：取數後寫表**（`market_indicator` ＋ `fetch_log`）：
   `run_market_indicator_fetch` 先寫 `fetch_log_open`，再以 `MarketIndicatorSheetSink` 當
   `build_market_indicator_table(sink=...)` 的 sink 呼叫；sink 寫 `market_indicator`、再寫 `fetch_log`。
   **本輪只給 set 頁觸發用，不接任何 UI。**

失敗處理（`50` 第 8 節）：
- 寫表失敗**不讓取數結果消失**：sink 不往上拋寫表的 `SettingsSheetError`，改記在
  `sink.persist` 交回（`build_market_indicator_table` 的 sink 例外會往上拋，那樣畫面就拿不到
  本次取數的結果 —— 與 `50`「本次取數的結果照常顯示在頁面上，另外標明取數紀錄寫入失敗」相違）。
  寫表以外的例外（程式錯誤、ValueError）照樣往上拋，不吞。
- 取數紀錄本身寫失敗時**不遞迴**：不為「寫 `fetch_log` 失敗」再寫一筆 `fetch_log`。
- 失敗訊息在本層遮一次，同一份字串同時放進 `fetch_log.message` 與回傳值
  （`ACCEPTANCE.md` 7.3 最後一條、7.4）。L1 不再遮第二次。

fetch_log 的 outcome（本檔拍板，理由寫在回報）：
- `ok`：沒有任何鍵出錯、沒有主鍵矛盾、`market_indicator` 寫入成功；`row_count`＝取回的列數
  （`44`「取回的列數」，不是新追加的列數）。
- `failed`：任一鍵有錯誤原文、或寫前看到主鍵矛盾（整批不寫）、或 `market_indicator` 寫入失敗；
  `row_count` 為空，`message` 為遮蔽後的原因。沒有錯誤的鍵照樣寫入（主鍵矛盾除外）。
- `pending`／`skipped`（第一階段刻意不取數、逐筆略過）不是錯誤，不影響 outcome。
"""

from __future__ import annotations

from typing import Callable, Optional

from repositories import settings_sheet_repository as store
from services.v2_tables import market_indicator as mi
from services.v2_tables.masking import mask_message

SettingsSheetError = store.SettingsSheetError


def masker(secret_values) -> Callable[[str], str]:
    values = list(secret_values)
    return lambda message: mask_message(message, values)


# ── 讀寫（L3 → 這裡 → L1）────────────────────────────────────────────

def load_user_settings(secret_values) -> dict:
    return store.load_user_settings(mask=masker(secret_values))


def save_user_setting(setting_key: str, setting_value: Optional[str], value_kind: str,
                      secret_values) -> dict:
    return store.save_user_setting(setting_key, setting_value, value_kind,
                                   mask=masker(secret_values))


def load_fetch_log(secret_values) -> dict:
    return store.load_fetch_log(mask=masker(secret_values))


def load_market_indicator(secret_values) -> dict:
    return store.load_market_indicator(mask=masker(secret_values))


# ── 第 2 步：market_indicator 取數後寫表 ─────────────────────────────

def _conflict_text(conflicts) -> str:
    parts = []
    for c in conflicts:
        key, obs, rel = c["key"]
        parts.append(
            f"主鍵矛盾：({key}, {obs}, {rel}) 既有 value_num={c['existing_value_num']!r}"
            f"（{c['existing_value_unit']}），本次 {c['new_value_num']!r}（{c['new_value_unit']}），"
            "本次整批不寫入")
    return "\n".join(parts)


class MarketIndicatorSheetSink:
    """`build_market_indicator_table(sink=...)` 的 sink：寫 `market_indicator` 與 `fetch_log`。

    用法：`sink.begin()`（寫 `fetch_log_open`）→ 當 sink 傳入 → 讀 `sink.persist`。
    `begin()` 失敗時 sink 停用：之後不再嘗試任何寫入，`persist` 記下失敗階段與原文。
    """

    def __init__(self, secret_values):
        self._mask = masker(secret_values)
        self.opened: Optional[dict] = None
        self.persist = {"ok": False, "stage": "not_started", "message": None,
                        "error_code": None, "log_id": None, "fetch_log": None,
                        "appended": 0, "already_present": 0, "conflicts": [],
                        "masked_errors": {}}

    def _fail(self, stage: str, exc: store.SettingsSheetError) -> None:
        self.persist.update(ok=False, stage=stage, message=str(exc), error_code=exc.code)

    def begin(self) -> bool:
        try:
            self.opened = store.open_fetch_log(mi.SOURCE_TIER, mask=self._mask)
        except store.SettingsSheetError as exc:
            self._fail("fetch_log_open", exc)
            return False
        self.persist.update(stage="started", log_id=self.opened["log_id"])
        return True

    def __call__(self, table: dict) -> None:
        masked = {k: self._mask(str(v)) for k, v in table["errors"].items()}
        self.persist["masked_errors"] = masked
        if self.opened is None:
            return  # begin 失敗或沒呼叫：不寫任何東西（persist 已記原因）
        reasons = [f"{k}: {v}" for k, v in masked.items()]
        write_failed = None
        try:
            result = store.append_market_indicator(table["rows"], mask=self._mask)
        except store.SettingsSheetError as exc:
            write_failed = exc
            reasons.append(f"market_indicator 寫入失敗：{exc}")
        else:
            self.persist.update(appended=result["appended"],
                                already_present=result["already_present"],
                                conflicts=result["conflicts"])
            if result["conflicts"]:
                reasons.append(self._mask(_conflict_text(result["conflicts"])))
        if reasons:
            outcome, row_count, message = "failed", None, "\n".join(reasons)
        else:
            outcome, row_count, message = "ok", len(table["rows"]), None
        try:
            logged = store.close_fetch_log(self.opened, outcome=outcome, row_count=row_count,
                                           message=message, mask=self._mask)
        except store.SettingsSheetError as exc:
            # 不遞迴：不為了「寫 fetch_log 失敗」再寫一筆 fetch_log，只回報。
            self._fail("fetch_log", exc)
            if write_failed is not None:
                self.persist["message"] = f"{write_failed}\n{exc}"
            return
        self.persist["fetch_log"] = logged
        if write_failed is not None:
            self._fail("market_indicator", write_failed)
            return
        self.persist.update(ok=True, stage="done", message=None, error_code=None)


def run_market_indicator_fetch(secret_values, *,
                               build: Callable = mi.build_market_indicator_table) -> dict:
    """set 頁「取數」：寫 `fetch_log_open` → 取數並寫表 → 寫 `fetch_log`。

    回傳 `{"table": build 的回傳（錯誤原文未遮）, "persist": sink.persist}`。
    畫面顯示錯誤請用 `persist["masked_errors"]`（與 `fetch_log.message` 同一份遮蔽後字串）。
    `fetch_log_open` 寫不進去時仍照常取數（`50` 第 8 節：結果照常顯示），只是不寫表。
    """
    sink = MarketIndicatorSheetSink(secret_values)
    sink.begin()
    table = build(sink=sink)
    return {"table": table, "persist": sink.persist}
