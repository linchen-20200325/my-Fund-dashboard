# -*- coding: utf-8 -*-
"""S0：EXP-0 計數文案與 EXP-2／EXP-7 一致性驗證測試（純標準函式庫；不 import streamlit，不依賴 conftest）。

本機執行：
    /root/.local/bin/pytest tests/ui_v3/test_ui_v3_exp_counts.py -q --noconftest -p no:cacheprovider
"""
from __future__ import annotations

import ast
import dataclasses
import re

import pytest

import ui_v3_guard_lib as lib
from ui_v3.viewmodels import exp_counts as ec
from ui_v3.viewmodels.exp_counts import (
    ExpCountsConclusion,
    exp0_conclusion,
    require_count,
    verify_exp2_row_count,
    verify_exp7_last_row,
)

REL = "ui_v3/viewmodels/exp_counts.py"
SOURCE_PATH = lib.UI_V3 / "viewmodels" / "exp_counts.py"


# ───────── 四種文案（逐字，全形標點） ─────────
@pytest.mark.parametrize("n,m,expected", [
    (3, 0, "目前條件下有 3 檔符合"),
    (3, 2, "目前條件下有 3 檔符合；另有 2 檔無法判定"),
    (0, 0, "目前條件下沒有符合的基金"),
    (0, 4, "目前條件下沒有符合的基金；另有 4 檔無法判定"),
    (1, 1, "目前條件下有 1 檔符合；另有 1 檔無法判定"),
])
def test_four_wordings_verbatim(n, m, expected):
    result = exp0_conclusion(1, n, m)
    assert result.text == expected
    assert (result.matched, result.undetermined) == (n, m)
    assert result.counts_shown is True


def test_no_tail_when_undetermined_is_zero():
    assert "無法判定" not in exp0_conclusion(2, 5, 0).text
    assert "無法判定" not in exp0_conclusion(2, 0, 0).text
    assert "另有" not in exp0_conclusion(2, 0, 0).text


def test_undetermined_is_never_counted_as_match_or_zero():
    """M 只出現在尾句，不併入 N；N=0、M>0 仍是「沒有符合」。"""
    r = exp0_conclusion(1, 0, 7)
    assert r.text.startswith("目前條件下沒有符合的基金")
    assert r.matched == 0 and r.undetermined == 7
    assert "有 7 檔符合" not in r.text


def test_no_thousands_separator_and_large_integers():
    big = 10 ** 30
    r = exp0_conclusion(1, big, big + 1)
    assert r.text == f"目前條件下有 {big} 檔符合；另有 {big + 1} 檔無法判定"
    assert "," not in r.text and "，" not in exp0_conclusion(1, 1234567, 0).text
    assert exp0_conclusion(1, 1234567, 0).text == "目前條件下有 1234567 檔符合"


def test_wording_uses_fullwidth_semicolon_only():
    text = exp0_conclusion(1, 2, 3).text
    assert "；" in text and ";" not in text


# ───────── 無條件 ─────────
@pytest.mark.parametrize("matched,undetermined", [
    (None, None),
    (5, 3),
    (0, 0),
    (5, None),
    (None, 3),
    (-1, -1),
    ("x", True),
    (1.5, float("nan")),
])
def test_no_conditions_shows_no_counts_even_if_values_passed(matched, undetermined):
    r = exp0_conclusion(0, matched, undetermined)
    assert r.text == "尚未設定條件"
    assert r.matched is None and r.undetermined is None
    assert r.counts_shown is False
    assert "檔" not in r.text


# ───────── 有條件：缺值與型別錯誤 ─────────
BAD_VALUES = [None, -1, -10 ** 20, True, False, 1.0, 2.5, float("nan"), float("inf"), "3", "", b"3", [3], (3,)]


@pytest.mark.parametrize("bad", BAD_VALUES)
def test_bad_matched_raises_with_field_name_and_value(bad):
    with pytest.raises(ValueError) as err:
        exp0_conclusion(2, bad, 0)
    assert "matched" in str(err.value)
    assert repr(bad) in str(err.value)


@pytest.mark.parametrize("bad", BAD_VALUES)
def test_bad_undetermined_raises_with_field_name_and_value(bad):
    with pytest.raises(ValueError) as err:
        exp0_conclusion(2, 0, bad)
    assert "undetermined" in str(err.value)
    assert repr(bad) in str(err.value)


@pytest.mark.parametrize("bad", [None, -1, True, 1.0, "1", []])
def test_bad_conditions_count_raises(bad):
    with pytest.raises(ValueError) as err:
        exp0_conclusion(bad, 1, 0)
    assert "conditions_count" in str(err.value)


def test_missing_is_never_treated_as_zero():
    with pytest.raises(ValueError):
        exp0_conclusion(1, None, None)
    with pytest.raises(ValueError):
        exp0_conclusion(3, 4, None)
    with pytest.raises(ValueError):
        exp0_conclusion(3, None, 0)


def test_require_count_accepts_plain_nonnegative_ints():
    assert require_count("x", 0) == 0
    assert require_count("x", 12) == 12
    assert require_count("x", 10 ** 40) == 10 ** 40


# ───────── 回傳型別 ─────────
def test_conclusion_is_frozen_dataclass():
    r = exp0_conclusion(1, 1, 0)
    assert dataclasses.is_dataclass(r) and isinstance(r, ExpCountsConclusion)
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.matched = 9  # type: ignore[misc]


@pytest.mark.parametrize("kwargs", [
    dict(text=""),
    dict(text="   "),
    dict(text=None),
    dict(text="x", matched=1),
    dict(text="x", undetermined=1),
    dict(text="x", matched=-1, undetermined=0),
    dict(text="x", matched=True, undetermined=0),
])
def test_conclusion_rejects_inconsistent_construction(kwargs):
    with pytest.raises(ValueError):
        ExpCountsConclusion(**kwargs)


# ───────── EXP-2 列數 ─────────
@pytest.mark.parametrize("rows,n,m", [(5, 3, 2), (0, 0, 0), (7, 7, 0), (4, 0, 4), (10 ** 30 + 1, 10 ** 30, 1)])
def test_exp2_row_count_consistent_passes(rows, n, m):
    assert verify_exp2_row_count(rows, n, m) is None


@pytest.mark.parametrize("rows,n,m", [(4, 3, 2), (6, 3, 2), (3, 3, 2), (0, 1, 0), (1, 0, 0)])
def test_exp2_row_count_mismatch_raises(rows, n, m):
    with pytest.raises(ValueError):
        verify_exp2_row_count(rows, n, m)


@pytest.mark.parametrize("rows,n,m", [(None, 1, 0), (1, None, 0), (1, 1, None), (True, 1, 0), (1.0, 1, 0), (-1, 0, 0), ("1", 1, 0)])
def test_exp2_row_count_bad_inputs_raise(rows, n, m):
    with pytest.raises(ValueError):
        verify_exp2_row_count(rows, n, m)


def test_exp2_does_not_treat_missing_undetermined_as_zero():
    with pytest.raises(ValueError):
        verify_exp2_row_count(3, 3, None)


# ───────── EXP-7 末列 ─────────
def test_exp7_last_row_consistent_passes():
    rows = [(10, 1), (6, 2), (3, 2)]
    assert verify_exp7_last_row(rows, 3, 2) is None
    assert verify_exp7_last_row([[4, 0]], 4, 0) is None


@pytest.mark.parametrize("n,m", [(4, 2), (3, 1), (2, 3), (0, 0)])
def test_exp7_last_row_mismatch_raises(n, m):
    with pytest.raises(ValueError):
        verify_exp7_last_row([(10, 1), (3, 2)], n, m)


def test_exp7_matched_mismatch_message_names_both_numbers():
    with pytest.raises(ValueError) as err:
        verify_exp7_last_row([(3, 2)], 4, 2)
    assert "3" in str(err.value) and "4" in str(err.value)


def test_exp7_only_the_last_row_is_checked():
    """規格只要求末列＝N、M：前面各列不檢查（含非遞增、含缺值），不自創額外規則。"""
    rows = [(2, 0), (9, 5), (None, None), (3, 2)]
    assert verify_exp7_last_row(rows, 3, 2) is None


def test_exp7_multiple_conditions_with_missing_in_last_row_raises():
    rows = [(10, 1), (6, None)]
    with pytest.raises(ValueError):
        verify_exp7_last_row(rows, 6, 0)  # 缺值不得當 0


@pytest.mark.parametrize("rows", [[], (), None, "ab", b"ab", [(1,)], [(1, 2, 3)], [5], [None], [(True, 0)], [(1, False)], [(-1, 0)], [(1.0, 0)]])
def test_exp7_malformed_rows_raise(rows):
    with pytest.raises(ValueError):
        verify_exp7_last_row(rows, 1, 0)


@pytest.mark.parametrize("n,m", [(None, 0), (0, None), (True, 0), (-1, 0), (1.0, 0)])
def test_exp7_bad_expected_values_raise(n, m):
    with pytest.raises(ValueError):
        verify_exp7_last_row([(1, 0)], n, m)


def test_exp7_large_integers():
    big = 10 ** 30
    assert verify_exp7_last_row([(1, 1), (big, big + 1)], big, big + 1) is None
    with pytest.raises(ValueError):
        verify_exp7_last_row([(big, big)], big, big + 1)


# ───────── 端到端：結論列與兩表一致 ─────────
def test_conclusion_and_tables_agree_for_a_multi_condition_scenario():
    n, m = 3, 2
    conclusion = exp0_conclusion(3, n, m)
    exp7 = [(12, 1), (7, 2), (n, m)]
    verify_exp2_row_count(n + m, conclusion.matched, conclusion.undetermined)
    verify_exp7_last_row(exp7, conclusion.matched, conclusion.undetermined)
    assert conclusion.text == "目前條件下有 3 檔符合；另有 2 檔無法判定"


# ───────── 模組本身的守衛（不 import streamlit；以 ast 讀原始碼） ─────────
def test_module_does_not_import_streamlit_or_anything_outside_stdlib():
    tree = ast.parse(lib.read(SOURCE_PATH))
    mods = lib.imports_of(tree, "ui_v3.viewmodels")
    roots = {m.split(".")[0] for m in mods}
    assert "streamlit" not in roots
    assert roots <= lib.STDLIB, roots - lib.STDLIB
    assert not any(r in ("ui_v2", "ui", "services", "repositories", "shared", "infra", "fixtures") for r in roots)


def test_module_passes_existing_guards():
    source = lib.read(SOURCE_PATH)
    assert lib.import_violations(REL, source) == []
    assert lib.write_surface_violations(REL, source) == []
    assert lib.module_level_side_effects(source) == []
    assert REL in {lib.rel_of(p) for p in lib.population()}


def test_visible_string_constants_have_no_env_var_shape():
    """畫面可能用到的字串常數（排除 docstring）不得是「大寫底線」形；raise 訊息一併檢查（比既有守衛更嚴）。"""
    tree = ast.parse(lib.read(SOURCE_PATH))
    skip = {id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
            and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant)}
    shape = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")
    hits = [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in skip and shape.search(n.value)]
    assert hits == []


def test_text_constants_are_the_approved_wording():
    assert ec.TEXT_NO_CONDITION == "尚未設定條件"
    assert ec.TEXT_NO_MATCH == "目前條件下沒有符合的基金"
    assert ec.TEXT_HAS_MATCH_PREFIX + "9" + ec.TEXT_HAS_MATCH_SUFFIX == "目前條件下有 9 檔符合"
    assert ec.TEXT_UNDETERMINED_PREFIX + "9" + ec.TEXT_UNDETERMINED_SUFFIX == "；另有 9 檔無法判定"


# ───────── 負控：違規片段餵 guard_lib 必須轉紅（記憶體內，不寫檔） ─────────
@pytest.mark.parametrize("snippet,needle", [
    ("import streamlit as st", "streamlit"),
    ("from ui_v2.exp import logic", "ui_v2"),
    ("from ui_v3.fixtures import scenarios", "不得 import ui_v3.fixtures"),
    ("import pandas as pd", "第三方"),
    ("import requests", "網路"),
])
def test_negative_control_import_guard_flags_violations_in_this_layer(snippet, needle):
    hits = lib.import_violations(REL, snippet)
    assert hits and any(needle in h for h in hits), hits


def test_negative_control_side_effect_guard_flags_module_level_call():
    assert lib.module_level_side_effects(lib.read(SOURCE_PATH) + "\nexp0_conclusion(1, 1, 0)\n")
    assert lib.module_level_side_effects("print('x')")
