# -*- coding: utf-8 -*-
"""`user_setting`、`fetch_log` 欄位契約鏡像的守衛（fast lane；不打網路、不需 gspread）。

真相源是 docs/v2/44_fund_ui_ssot.md §4.5。本檔每次從 `44` 逐欄重抽欄名、型別、可空與值域，
與兩份鏡像比對，漂了就紅：
- `services/v2_tables/contract.py`（L2）
- `repositories/settings_sheet_repository.py` 的標頭規格（L1；L1 不得 import L2，所以另有一份）
做法仿 tests/test_v2_tables_market_indicator.py 對 `market_indicator` 的抽法。
"""

from __future__ import annotations

import pathlib
import re

import pytest

from repositories import settings_sheet_repository as repo
from services.v2_tables import contract

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_D44 = _ROOT / "docs" / "v2" / "44_fund_ui_ssot.md"


def _strip_struck(text: str) -> str:
    return re.sub(r"~~.*?~~", "", text)


def _table_from_44(name: str):
    """回傳 ((欄名, 型別, 可空), ...) 與 {欄名: 語意欄（去掉刪除線）}。"""
    text = _D44.read_text(encoding="utf-8")
    sec4 = text[text.index("## 4. 資料庫結構"): text.index("## 5. 元件清單")]
    head = re.search(rf"(?m)^#{{3,4}} 表 `{name}`", sec4)
    assert head, f"44 第四節找不到 {name} 表"
    rest = sec4[head.end():]
    nxt = re.search(r"(?m)^#{3,4} ", rest)
    body = rest[: nxt.start()] if nxt else rest
    fields, meanings = [], {}
    for line in body.split("\n"):
        m = re.match(r"^\| `([a-z_]+)` \| ([^|]+) \| ([^|]+) \| ([^|]+) \| (.*) \|\s*$", line)
        if not m:
            continue
        col, typ, _unit, nullable, meaning = (g.strip() for g in m.groups())
        fields.append((col, typ, nullable == "是"))
        meanings[col] = _strip_struck(meaning)
    return tuple(fields), meanings


def _backticked(cell: str) -> tuple:
    return tuple(re.findall(r"`([^`]+)`", cell))


# ═══════════════════════ 正控：抽取器真的抽得到東西 ═══════════════════════

def test_正控_抽取器對已知的market_indicator表抽得到八欄():
    fields, _ = _table_from_44("market_indicator")
    assert fields == contract.MARKET_INDICATOR_FIELDS


def test_負控_抽取器對不存在的表會炸而不是回空():
    with pytest.raises(AssertionError):
        _table_from_44("no_such_table_xyz")


# ═══════════════════════ user_setting ═══════════════════════

def test_user_setting契約與44逐欄相同():
    fields, _ = _table_from_44("user_setting")
    assert len(fields) == 4, fields  # 空掃防呆
    assert contract.USER_SETTING_FIELDS == fields


def test_user_setting的value_kind值域與44相同():
    _, meanings = _table_from_44("user_setting")
    assert _backticked(meanings["value_kind"]) == contract.VALUE_KIND_VALUES


# ═══════════════════════ fetch_log ═══════════════════════

def test_fetch_log契約與44逐欄相同():
    fields, _ = _table_from_44("fetch_log")
    assert len(fields) == 7, fields
    assert contract.FETCH_LOG_FIELDS == fields


def test_fetch_log的source_tier與outcome值域與44相同():
    _, meanings = _table_from_44("fetch_log")
    assert _backticked(meanings["source_tier"]) == contract.SOURCE_TIER_VALUES
    assert _backticked(meanings["outcome"]) == contract.OUTCOME_VALUES


# ═══════════════════════ L1 的標頭鏡像 ═══════════════════════

def test_L1標頭規格與contract逐欄相同():
    assert repo.USER_SETTING_SPEC == contract.USER_SETTING_FIELDS
    assert repo.FETCH_LOG_SPEC == contract.FETCH_LOG_FIELDS
    assert repo.MARKET_INDICATOR_SPEC == contract.MARKET_INDICATOR_FIELDS
    assert repo.VALUE_KIND_VALUES == contract.VALUE_KIND_VALUES
    assert repo.SOURCE_TIER_VALUES == contract.SOURCE_TIER_VALUES
    assert repo.OUTCOME_VALUES == contract.OUTCOME_VALUES


def test_fetch_log_open是fetch_log的前三欄():
    """`50` 4.4：輔助分頁三欄借自 `fetch_log`，沒有新語意。"""
    assert repo.FETCH_LOG_OPEN_SPEC == contract.FETCH_LOG_FIELDS[:3]
    assert [n for n, _k, _nl in repo.FETCH_LOG_OPEN_SPEC] == ["log_id", "source_tier", "started_at"]


# ═══════════════════════ 逐列檢查 ═══════════════════════

def _setting(**kw):
    row = {"setting_key": "mkt_window_days", "setting_value": "90", "value_kind": "int",
           "updated_at": "2026-09-26T03:14:15Z"}
    row.update(kw)
    return row


def test_user_setting列_合格與清除():
    assert contract.user_setting_row_problems(_setting()) == []
    assert contract.user_setting_row_problems(_setting(setting_value=None, updated_at=None)) == []


@pytest.mark.parametrize("patch", [
    {"setting_value": ""},            # 44：清除後是空值，不是空字串
    {"value_kind": "text"},
    {"setting_key": ""},
    {"updated_at": "2026-09-26T03:14:15"},   # 沒有時區
])
def test_user_setting列_不合格(patch):
    assert contract.user_setting_row_problems(_setting(**patch))


def _log(**kw):
    row = {"log_id": "x-1", "source_tier": "市場指標", "started_at": "2026-09-26T03:00:00Z",
           "finished_at": "2026-09-26T03:00:05Z", "outcome": "ok", "row_count": 3,
           "message": None}
    row.update(kw)
    return row


def test_fetch_log列_合格():
    assert contract.fetch_log_row_problems(_log()) == []
    assert contract.fetch_log_row_problems(
        _log(outcome="failed", row_count=None, message="boom", finished_at=None)) == []


@pytest.mark.parametrize("patch", [
    {"outcome": "failed"},                                   # 失敗時 row_count 須為空、message 非空
    {"outcome": "failed", "row_count": None},                # message 空
    {"message": "x"},                                        # ok 時 message 須為空
    {"row_count": -1},
    {"row_count": True},
    {"source_tier": "T1"},
    {"outcome": "partial"},
])
def test_fetch_log列_不合格(patch):
    assert contract.fetch_log_row_problems(_log(**patch))
