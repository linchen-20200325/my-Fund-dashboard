"""tests/test_policy_invest_twd_parse.py — 保單本金欄解析（§1 Fail Loud）。

守的是 2026-08 稽核「必修 3」：`_normalize_invest_twd` 原本 `except: return 0`，
Sheet 本金欄寫成 `NT$1,000` / `1000元` 會**靜默變 0**，該檔基金隨即在
「投入本金 / 核心% / 月配息 / 回撤權重」全部消失，畫面零提示。

紅燈型態：
- `parse_invest_twd` / `normalize_invest_twd_column` / `get_invest_twd_parse_errors`
  三組測試在修正前為 **ImportError 紅**（這三個 symbol 當時不存在）。
- `test_normalize_invest_twd_still_returns_int_zero_on_failure` 在修正前**會綠**
  （回傳契約刻意不變），它守的是「不要為了修這個 bug 去改回傳型別、
  連累 scripts/ 與 v1/v2 六個 caller」。
"""
from __future__ import annotations

import pandas as pd
import pytest

from repositories.policy_repository import (
    _normalize_invest_twd,
    get_invest_twd_parse_errors,
    normalize_invest_twd_column,
    parse_invest_twd,
    reset_invest_twd_parse_errors,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_invest_twd_parse_errors()
    yield
    reset_invest_twd_parse_errors()


# ── parse_invest_twd：可解析 ──────────────────────────────────────────
@pytest.mark.parametrize("raw,expect", [
    (1000, 1000),
    (1000.0, 1000),
    ("1000", 1000),
    ("1,000,000", 1_000_000),
    ("  1,000  ", 1000),
    (0, 0),
])
def test_parse_ok(raw, expect):
    val, err = parse_invest_twd(raw)
    assert err is None
    assert val == expect


def test_parse_truncates_decimal_documented_behaviour():
    """小數無條件捨去（沿用既有行為）—— docstring 有明講，這裡鎖住不被無聲改掉。"""
    assert parse_invest_twd(1000.9)[0] == 1000
    assert parse_invest_twd(-1000.9)[0] == -1000   # 往 0 靠


# ── parse_invest_twd：未填 vs 解析失敗要分得開 ─────────────────────────
@pytest.mark.parametrize("raw", [None, "", "   ", float("nan")])
def test_parse_blank_is_zero_not_an_error(raw):
    """空白 = 「這列沒填本金」，屬正常業務狀態，不該進錯誤清單。

    NaN 一併視為空白：它幾乎都來自 pandas 對空儲存格的表示，
    報成錯誤會製造假警報、淹掉真正的格式問題。
    """
    val, err = parse_invest_twd(raw)
    assert val == 0
    assert err is None


@pytest.mark.parametrize("raw", [
    "NT$1,000",     # 使用者最常見寫法
    "1000元",
    "一百萬",
    "1,0 0 0",
    "abc",
    float("inf"),
    float("-inf"),
    [1000],
])
def test_parse_unparseable_returns_none_with_reason(raw):
    val, err = parse_invest_twd(raw)
    assert val is None
    assert err and isinstance(err, str)


# ── 既有 caller 契約不變 ──────────────────────────────────────────────
def test_normalize_invest_twd_still_returns_int_zero_on_failure():
    """回傳型別刻意維持 int（0）—— 六個 caller + scripts/ 不受影響。"""
    assert _normalize_invest_twd("NT$1,000") == 0
    assert _normalize_invest_twd("1,000") == 1000
    assert _normalize_invest_twd("") == 0


def test_normalize_invest_twd_records_failure_into_registry():
    """失敗不再靜默：registry 要留痕，UI 才彙總得出來。"""
    _normalize_invest_twd("1000元")
    errs = get_invest_twd_parse_errors()
    assert len(errs) == 1
    assert "1000元" in errs[0]["raw"]


def test_normalize_invest_twd_success_leaves_registry_empty():
    _normalize_invest_twd("1,234")
    assert get_invest_twd_parse_errors() == []


# ── normalize_invest_twd_column：列號 + 主鍵 ──────────────────────────
def _df(vals: list, **cols) -> pd.DataFrame:
    data = {"invest_twd": vals}
    data.update(cols)
    return pd.DataFrame(data)


def test_column_normalizer_reports_row_number_and_identity():
    """列號要對得上 Google Sheet（header 佔第 1 列 → 第 0 筆資料 = 第 2 列）。"""
    df = _df(
        ["1,000", "NT$500", 2000],
        policy_id=["P1", "P1", "P2"],
        fund_url=["u1", "u2", "u3"],
    )
    bad = normalize_invest_twd_column(
        df, source="v1/Policies", id_cols=("policy_id", "fund_url"))
    assert len(bad) == 1
    assert bad[0]["row"] == 3            # index 1 → sheet 第 3 列
    assert bad[0]["policy_id"] == "P1"
    assert bad[0]["fund_url"] == "u2"
    assert bad[0]["source"] == "v1/Policies"
    # 值本身仍寫回 int，下游算式不炸
    assert list(df["invest_twd"]) == [1000, 0, 2000]


def test_column_normalizer_writes_attrs_and_registry():
    df = _df(["oops"], policy_id=["P1"])
    bad = normalize_invest_twd_column(df, source="t", id_cols=("policy_id",))
    assert df.attrs["invest_twd_parse_errors"] == bad
    assert len(get_invest_twd_parse_errors()) == 1


def test_column_normalizer_all_good_returns_empty():
    df = _df([1, "2", "3,000", "", None])
    assert normalize_invest_twd_column(df) == []
    assert list(df["invest_twd"]) == [1, 2, 3000, 0, 0]


def test_column_normalizer_empty_dataframe():
    df = pd.DataFrame({"invest_twd": []})
    assert normalize_invest_twd_column(df) == []


def test_column_normalizer_missing_column_is_noop():
    df = pd.DataFrame({"other": [1]})
    assert normalize_invest_twd_column(df) == []


def test_column_normalizer_accumulates_across_calls():
    """v2 讀整本 Sheet 會逐分頁呼叫，錯誤要跨分頁累加（reset 由 loader 進場時做）。"""
    normalize_invest_twd_column(_df(["bad1"]), source="tab-A")
    normalize_invest_twd_column(_df(["bad2"]), source="tab-B")
    errs = get_invest_twd_parse_errors()
    assert {e["source"] for e in errs} == {"tab-A", "tab-B"}


def test_reset_clears_registry():
    normalize_invest_twd_column(_df(["bad"]))
    assert get_invest_twd_parse_errors()
    reset_invest_twd_parse_errors()
    assert get_invest_twd_parse_errors() == []


def test_registry_getter_returns_copy():
    normalize_invest_twd_column(_df(["bad"]))
    got = get_invest_twd_parse_errors()
    got.clear()
    assert len(get_invest_twd_parse_errors()) == 1


# ── 接線驗證（PROCESS §4）：L1 loader 真的有接出去 ─────────────────────
# 判準：把 v1.load_policies 裡那一行 normalize_invest_twd_column 換回
# `.map(_normalize_invest_twd)`，下面兩條會紅（列號/主鍵拿不到）。
def _make_client(records: list):
    from unittest.mock import MagicMock
    ws = MagicMock()
    ws.get_all_records.return_value = records
    ws.get_all_values.return_value = []
    sh = MagicMock()
    sh.worksheet.return_value = ws
    client = MagicMock()
    client.open_by_key.return_value = sh
    return client


def _row(pid: str, url: str, amount) -> dict:
    return {
        "policy_id": pid, "policy_name": f"保單{pid}", "fund_url": url,
        "invest_twd": amount, "invest_date": "2024-01-01",
        "currency": "USD", "fx_at_buy": "31.5", "notes": "",
    }


def test_load_policies_surfaces_bad_invest_twd_rows():
    from repositories.policy_repository import load_policies
    client = _make_client([
        _row("P1", "AAA", "1,000"),
        _row("P1", "BBB", "NT$2,000"),
    ])
    df = load_policies(client, "FAKE_ID")
    assert list(df["invest_twd"]) == [1000, 0]

    errs = get_invest_twd_parse_errors()
    assert len(errs) == 1
    assert errs[0]["row"] == 3
    assert errs[0]["fund_url"] == "BBB"


def test_load_policies_resets_registry_between_loads():
    """replace 語意：第二次載入成功後，畫面不該還掛著上一次的錯誤。"""
    from repositories.policy_repository import load_policies
    load_policies(_make_client([_row("P1", "BAD", "1000元")]), "FAKE_ID")
    assert len(get_invest_twd_parse_errors()) == 1
    load_policies(_make_client([_row("P1", "OK", 1000)]), "FAKE_ID")
    assert get_invest_twd_parse_errors() == []
