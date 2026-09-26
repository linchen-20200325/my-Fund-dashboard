# -*- coding: utf-8 -*-
"""`44` 第四節欄位契約的鏡像（本批只有 `market_indicator` 一張表）。

⚠️ **真相源是 docs/v2/44_fund_ui_ssot.md，不是本檔。** 本檔是鏡像：
   `tests/test_v2_tables_market_indicator.py` 每次從 `44` 逐欄重抽欄名、型別、可空與
   `source_tier` 值域，與本檔比對，漂了就紅。L2 不讀文件檔（純度守衛不准），
   也不得 import `ui_v2`（上行），所以不能共用 `ui_v2/set/fixtures.py::SPEC_TABLES`。

`44` 第四節開頭：「可空」為「否」的欄位若取不到值，該筆不寫入，不以零或空字串補。
`market_indicator_row_problems` 就是那一條的逐列檢查：回傳空清單才可以寫入。
"""

from __future__ import annotations

import math
from datetime import date, datetime

# (欄名, 型別字面值, 可空) —— 順序與 `44` 表格相同。
MARKET_INDICATOR_FIELDS = (
    ("indicator_key", "字串", False),
    ("obs_date", "日期", False),
    ("release_date", "日期", False),
    ("value_num", "浮點", False),
    ("value_unit", "字串", False),
    ("source_tier", "字串", False),
    ("is_revised", "布林", False),
    ("fetched_at", "時間", False),
)

# `44` `market_indicator.source_tier`：四個之一。
SOURCE_TIER_VALUES = ("淨值", "配息", "市場指標", "其他")


def _problem_for(column: str, kind: str, value) -> str | None:
    """單一欄位的檢查；None 表示合格。"""
    if value is None:
        return f"{column}：取不到值"
    if kind == "字串":
        if not isinstance(value, str) or value.strip() == "":
            return f"{column}：不是非空字串（{value!r}）"
        return None
    if kind == "日期":
        if not isinstance(value, str):
            return f"{column}：日期須為 YYYY-MM-DD 字串（{value!r}）"
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            return f"{column}：日期格式不符（{value!r}）"
        if parsed.isoformat() != value:
            return f"{column}：日期格式不符（{value!r}）"
        return None
    if kind == "浮點":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return f"{column}：不是數值（{value!r}）"
        if not math.isfinite(float(value)):
            return f"{column}：不是有限數值（{value!r}）"
        return None
    if kind == "布林":
        if not isinstance(value, bool):
            return f"{column}：不是布林（{value!r}）"
        return None
    if kind == "時間":
        if not isinstance(value, str):
            return f"{column}：時間須為 ISO 字串（{value!r}）"
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return f"{column}：時間格式不符（{value!r}）"
        if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
            return f"{column}：時間須為世界協調時間（{value!r}）"
        return None
    raise ValueError(f"契約裡出現未知型別 {kind!r}（{column}）")


def market_indicator_row_problems(row: dict) -> list:
    """回傳這一列違反契約的地方；空清單＝可以寫入。欄位多一個、少一個都算。"""
    names = [name for name, _kind, _nullable in MARKET_INDICATOR_FIELDS]
    problems = []
    for name, kind, nullable in MARKET_INDICATOR_FIELDS:
        if name not in row:
            problems.append(f"{name}：缺欄")
            continue
        value = row[name]
        if value is None and nullable:
            continue
        found = _problem_for(name, kind, value)
        if found:
            problems.append(found)
    extra = [k for k in row if k not in names]
    if extra:
        problems.append(f"多出契約沒有的欄：{extra}")
    if row.get("source_tier") not in SOURCE_TIER_VALUES and "source_tier" in row \
            and not any(p.startswith("source_tier") for p in problems):
        problems.append(f"source_tier：不在值域 {SOURCE_TIER_VALUES}（{row['source_tier']!r}）")
    return problems
