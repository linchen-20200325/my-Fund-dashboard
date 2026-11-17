# -*- coding: utf-8 -*-
"""🔍 找一檔基金／依條件篩選｜隔離式 FAKE Preview 的假輸入（全部是人造的離線資料；不取數、不連線、不讀任何東西）。

- 每一個基金代碼都以 `FAKE-` 開頭、每個名稱都以 `FAKE` 開頭、每個「有值」的格子都是 `FAKE_VALUE`；缺值用 `None`（畫面顯示規則表的缺值字樣，不是 0）。
- ⚠️ 三態（符合／不符合／資料不足無法判定）是**測試輸入**：每檔基金×每個條件都由本檔**明確給定**，
  預覽不從任何金融數值推導它，也不是任何正式篩選判準；僅供畫面與計數演示，不得搬入 production。
- 資料不足無法判定（`undetermined`）的基金，至少有一格缺值（與畫面上「資料未備」一致；守衛鎖定）。
"""
from __future__ import annotations

FAKE_VALUE = "FAKE 值"
MATCH, NOMATCH, UNDET = "match", "nomatch", "undetermined"
CONDITION_COUNT = 3
COLUMNS = ("code", "name", "ccy", "nav_date", "nav", "div")

# 單檔查詢的 FAKE 代碼表（輸入去頭尾空白、轉大寫後比對）：結果由本表決定，不是由格式推導。
LOOKUP_FIXTURES = {
    "FAKE-OK01": "found",
    "FAKE-LOW1": "insufficient",
    "FAKE-ERR1": "failed",
}
FAKE_FOUND_NAME = "FAKE 模擬基金（非正式名稱）"
HARNESS_CODES_HINT = "FAKE 代碼：FAKE-OK01（找到）／FAKE-LOW1（資料不足）／FAKE-ERR1（查詢失敗）"


def _fund(n, name, states, missing=()):
    cells = {"code": "FAKE-%03d" % n, "name": "FAKE 基金 " + name, "ccy": FAKE_VALUE, "nav_date": FAKE_VALUE,
             "nav": FAKE_VALUE, "div": FAKE_VALUE}
    for col in missing:
        cells[col] = None
    return {"cells": cells, "states": tuple(states)}


_M, _X, _U = MATCH, NOMATCH, UNDET

_POOLS = {
    # 全勾 N=2、M=0；只勾條件 1：N=4、M=0
    "has_match": (
        _fund(1, "甲", (_M, _M, _M)), _fund(2, "乙", (_M, _M, _M)), _fund(3, "丙", (_M, _X, _M)),
        _fund(4, "丁", (_X, _M, _M)), _fund(5, "戊", (_M, _M, _X)), _fund(6, "己", (_X, _X, _X)),
    ),
    # 全勾 N=0、M=0（無符合也無無法判定）
    "no_match": (
        _fund(1, "甲", (_X, _M, _M)), _fund(2, "乙", (_M, _X, _M)), _fund(3, "丙", (_M, _M, _X)), _fund(4, "丁", (_X, _X, _X)),
    ),
    # 全勾 N=0、M=3
    "undetermined_only": (
        _fund(1, "甲", (_M, _U, _M), missing=("nav",)), _fund(2, "乙", (_U, _M, _M), missing=("div",)),
        _fund(3, "丙", (_M, _M, _U), missing=("nav_date", "nav")), _fund(4, "丁", (_X, _X, _X)), _fund(5, "戊", (_M, _M, _X)),
    ),
    # 全勾 N=2、M=2；只勾條件 1：N=4、M=1；勾條件 1＋2：N=2、M=2
    "mixed": (
        _fund(1, "甲", (_M, _M, _M)), _fund(2, "乙", (_M, _M, _M)), _fund(3, "丙", (_M, _U, _M), missing=("div",)),
        _fund(4, "丁", (_U, _M, _M), missing=("nav",)), _fund(5, "戊", (_X, _M, _M)), _fund(6, "己", (_M, _X, _M)),
    ),
}

# 情境：id → (harness 選單標籤, 池 id 或 None)。None＝來源失敗（EXP 區顯示失敗字樣，不展示 N／M）。
SCENARIOS = {
    "has_match": ("有符合（全勾 N=2、M=0）", "has_match"),
    "no_match": ("無符合（全勾 N=0、M=0）", "no_match"),
    "undetermined_only": ("只有無法判定（全勾 N=0、M=3）", "undetermined_only"),
    "mixed": ("有符合也有無法判定（全勾 N=2、M=2）", "mixed"),
    "source_failed": ("選股池來源失敗", None),
}
DEFAULT_SCENARIO = "has_match"


def build(scenario_id):
    """回傳新的（每次呼叫都是新物件）情境輸入：{"failed": bool, "pool": [ {cells, states}, … ]}。未知情境 → KeyError。"""
    label, pool_id = SCENARIOS[scenario_id]
    if pool_id is None:
        return {"failed": True, "pool": []}
    return {"failed": False,
            "pool": [{"cells": dict(f["cells"]), "states": tuple(f["states"])} for f in _POOLS[pool_id]]}
