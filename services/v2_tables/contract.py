# -*- coding: utf-8 -*-
"""`44` 第四節欄位契約的鏡像（`market_indicator`、`user_setting`、`fetch_log` 三張表）。

⚠️ **真相源是 docs/v2/44_fund_ui_ssot.md，不是本檔。** 本檔是鏡像：
   `tests/test_v2_tables_market_indicator.py` 每次從 `44` 逐欄重抽欄名、型別、可空與
   `source_tier` 值域，與本檔比對，漂了就紅。L2 不讀文件檔（純度守衛不准），
   也不得 import `ui_v2`（上行），所以不能共用 `ui_v2/set/fixtures.py::SPEC_TABLES`。

`44` 第四節開頭：「可空」為「否」的欄位若取不到值，該筆不寫入，不以零或空字串補。
`market_indicator_row_problems` 就是那一條的逐列檢查：回傳空清單才可以寫入。
`user_setting_row_problems`、`fetch_log_row_problems` 同理（2026-09-26 set 頁第 1 步新增）；
兩張表的欄位鏡像由 `tests/test_v2_tables_contract_settings.py` 從 `44` 逐欄重抽比對。

⚠️ L1 `repositories/settings_sheet_repository.py` 另有一份同形的標頭常數（L1 不得 import L2，
   所以不能直接 import 本檔）；那一份由同一支測試與本檔逐欄比對，兩份鏡像都以 `44` 為準。
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

# `44` §4.5 表 `user_setting`（順序同 `44`）。
USER_SETTING_FIELDS = (
    ("setting_key", "字串", False),
    ("setting_value", "字串", True),
    ("value_kind", "字串", False),
    ("updated_at", "時間", True),
)
# `44` `user_setting.value_kind` 值域。
VALUE_KIND_VALUES = ("int", "float", "date", "ratio", "list", "rules")

# `44` §4.5 表 `fetch_log`（順序同 `44`）。`source_tier` 值域同上。
FETCH_LOG_FIELDS = (
    ("log_id", "字串", False),
    ("source_tier", "字串", False),
    ("started_at", "時間", False),
    ("finished_at", "時間", True),
    ("outcome", "字串", False),
    ("row_count", "整數", True),
    ("message", "字串", True),
)
# `44` `fetch_log.outcome` 值域。
OUTCOME_VALUES = ("ok", "failed")


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
    if kind == "整數":
        if isinstance(value, bool) or not isinstance(value, int):
            return f"{column}：不是整數（{value!r}）"
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


def _fields_problems(fields, row: dict) -> list:
    """逐欄檢查型別與可空；欄位多一個、少一個都算。"""
    names = [name for name, _kind, _nullable in fields]
    problems = []
    for name, kind, nullable in fields:
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
    return problems


def _domain_problem(row: dict, column: str, domain, problems: list) -> None:
    if column in row and row.get(column) is not None and row.get(column) not in domain \
            and not any(p.startswith(column) for p in problems):
        problems.append(f"{column}：不在值域 {domain}（{row[column]!r}）")


def market_indicator_row_problems(row: dict) -> list:
    """回傳這一列違反契約的地方；空清單＝可以寫入。欄位多一個、少一個都算。"""
    problems = _fields_problems(MARKET_INDICATOR_FIELDS, row)
    if row.get("source_tier") not in SOURCE_TIER_VALUES and "source_tier" in row \
            and not any(p.startswith("source_tier") for p in problems):
        problems.append(f"source_tier：不在值域 {SOURCE_TIER_VALUES}（{row['source_tier']!r}）")
    return problems


def user_setting_row_problems(row: dict) -> list:
    """`user_setting` 一列的契約檢查；空清單＝合格。`value_kind` 須在值域內。

    ⚠️ `setting_value` 可空：None 表示未設定或已清除。空字串**不是**合法值 ——
    `44`「清除某鍵，該鍵的 `setting_value` 回到空值而不是 0 或空字串」。
    """
    problems = _fields_problems(USER_SETTING_FIELDS, row)
    _domain_problem(row, "value_kind", VALUE_KIND_VALUES, problems)
    return problems


def fetch_log_row_problems(row: dict) -> list:
    """`fetch_log` 一列的契約檢查；空清單＝合格。

    除型別外另核三條 `44` 寫明的規則：`source_tier`、`outcome` 在值域內；
    `row_count` 不為負；`outcome` 為 `failed` 時 `row_count` 為空（「失敗時為空」）、
    `message` 非空（表判準「讓一次取數失敗，`outcome` 為 `failed` 且 `message` 非空」）；
    `outcome` 為 `ok` 時 `message` 為空（「成功時為空」）。
    """
    problems = _fields_problems(FETCH_LOG_FIELDS, row)
    _domain_problem(row, "source_tier", SOURCE_TIER_VALUES, problems)
    _domain_problem(row, "outcome", OUTCOME_VALUES, problems)
    count = row.get("row_count")
    if isinstance(count, int) and not isinstance(count, bool) and count < 0:
        problems.append(f"row_count：不可為負（{count!r}）")
    if row.get("outcome") == "failed":
        if count is not None:
            problems.append("row_count：outcome 為 failed 時須為空")
        if row.get("message") is None:
            problems.append("message：outcome 為 failed 時不可為空")
    if row.get("outcome") == "ok" and row.get("message") is not None:
        problems.append("message：outcome 為 ok 時須為空")
    return problems
