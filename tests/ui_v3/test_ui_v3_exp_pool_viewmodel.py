# -*- coding: utf-8 -*-
"""S2-T0（`DEC-2026-11-17-04`）：選股池 view model 與 EXP-0／2／7 組裝測試（純標準函式庫；不依賴 conftest）。

本機執行：
    pytest tests/ui_v3/test_ui_v3_exp_pool_viewmodel.py -q --noconftest -p no:cacheprovider

⚠️ 輸入全是**測試注入**的三態與選股池代碼，不是正式資料，也不是正式篩選判準；本檔不證明 🔍 找基金頁面或選股池功能已完成。
預期值一律寫成字面常數或用獨立 oracle 算（不用被測的組合函式自己算自己）。
"""
from __future__ import annotations

import dataclasses
import os
import random
import sys

import pytest

from ui_v3.viewmodels import exp_counts as ec
from ui_v3.viewmodels import exp_pool as vm
from ui_v3.viewmodels.exp_pool import (
    COUNTS_COUNTED,
    COUNTS_NO_CONDITIONS,
    COUNTS_POOL_EMPTY,
    COUNTS_POOL_FAILED,
    COUNTS_POOL_UNAVAILABLE,
    Exp2Row,
    Exp7Row,
    ExpCountsView,
    PoolContractError,
    PoolSourceView,
    PoolState,
    build_exp_counts,
)

M_, N_, U_ = "match", "no_match", "undetermined"


def _ci_is_true() -> bool:
    """環境變數 CI 非空且不是 0／false（大小寫不分）→ 視為 CI。"""
    return os.environ.get("CI", "").strip().lower() not in ("", "0", "false")


def ok_view(*codes: str) -> PoolSourceView:
    return PoolSourceView(PoolState.OK, tuple(codes), None, "2026-11-17T10:00:00+00:00")


EMPTY_VIEW = PoolSourceView(PoolState.EMPTY, (), None, "2026-11-17T10:00:00+00:00")
FAILED_VIEW = PoolSourceView(PoolState.FAILED, (), vm.REASON_SOURCE_FAILED, None)
UNAVAILABLE_VIEW = PoolSourceView(PoolState.UNAVAILABLE, (), vm.REASON_POOL_UNAVAILABLE, None)


# ───────────────────────── PoolSourceView：四狀態與驗證 ─────────────────────────

def test_four_states_are_distinct_and_exactly_four():
    assert {s.name for s in PoolState} == {"OK", "EMPTY", "FAILED", "UNAVAILABLE"}
    views = [ok_view("A1"), EMPTY_VIEW, FAILED_VIEW, UNAVAILABLE_VIEW]
    assert len({v.state for v in views}) == 4
    assert [v.usable for v in views] == [True, True, False, False]
    assert len({v for v in views}) == 4                      # 彼此不相等（可區分）


@pytest.mark.parametrize("reason", [vm.REASON_SOURCE_FAILED, vm.REASON_SOURCE_COOLING, vm.REASON_LOADER_RAISED])
def test_failed_accepts_only_its_own_category_codes(reason):
    assert PoolSourceView(PoolState.FAILED, (), reason).reason_code == reason


def test_unavailable_accepts_only_its_own_category_code_and_never_names_a_cause():
    assert PoolSourceView(PoolState.UNAVAILABLE, (), vm.REASON_POOL_UNAVAILABLE).reason_code == "pool_unavailable"
    for bad in (vm.REASON_SOURCE_FAILED, vm.REASON_LOADER_RAISED, None, "", "not_configured", "credential_invalid"):
        with pytest.raises(PoolContractError):
            PoolSourceView(PoolState.UNAVAILABLE, (), bad)
    for bad in (vm.REASON_POOL_UNAVAILABLE, None, "", "free text from a message"):
        with pytest.raises(PoolContractError):
            PoolSourceView(PoolState.FAILED, (), bad)


@pytest.mark.parametrize("kwargs", [
    dict(state=PoolState.OK, codes=()),                                          # OK 但沒代碼
    dict(state=PoolState.EMPTY, codes=("A1",)),                                  # EMPTY 卻有代碼
    dict(state=PoolState.FAILED, codes=("A1",), reason_code=vm.REASON_SOURCE_FAILED),
    dict(state=PoolState.UNAVAILABLE, codes=("A1",), reason_code=vm.REASON_POOL_UNAVAILABLE),
    dict(state=PoolState.OK, codes=("A1",), reason_code=vm.REASON_SOURCE_FAILED),  # OK 卻帶失敗碼
    dict(state=PoolState.EMPTY, reason_code=vm.REASON_SOURCE_FAILED),
    dict(state=PoolState.FAILED, reason_code=vm.REASON_SOURCE_FAILED, read_at="2026-11-17T10:00:00+00:00"),
    dict(state="ok", codes=("A1",)),                                             # 狀態不是 PoolState
    dict(state=None),
    dict(state=PoolState.OK, codes=["A1"]),                                      # 不是 tuple
    dict(state=PoolState.OK, codes=("A1", "A1")),                                # 精確重複
    dict(state=PoolState.OK, codes=("A1", "")),                                  # 空字串
    dict(state=PoolState.OK, codes=("A1", "   ")),                               # 全空白
    dict(state=PoolState.OK, codes=("A1", None)),
    dict(state=PoolState.OK, codes=("A1", 123)),
    dict(state=PoolState.OK, codes=("A1", b"B2")),
])
def test_invalid_or_contradictory_views_are_rejected(kwargs):
    with pytest.raises(PoolContractError):
        PoolSourceView(**kwargs)


@pytest.mark.parametrize("read_at", ["not a date", "2026-13-45", "", "yesterday", 1731800000, 1.5, b"2026-11-17", ["2026-11-17"]])
def test_read_at_must_be_iso_string_or_none(read_at):
    with pytest.raises(PoolContractError):
        PoolSourceView(PoolState.OK, ("A1",), None, read_at)
    assert PoolSourceView(PoolState.OK, ("A1",), None, None).read_at is None
    assert PoolSourceView(PoolState.OK, ("A1",), None, "2026-11-17T10:00:00+00:00").read_at == "2026-11-17T10:00:00+00:00"


OPAQUE_CODES = ("AB1", "ab1", "Ab1", "AB 1", "ＡＢ１", "US0378331005", "us0378331005", "TW000T0001A0", "0050", "00-50", " lead", "trail ",
                "R-ID-1", "A;B", "<script>", "基金甲")


def test_codes_are_opaque_strings_kept_exactly_in_order():
    view = ok_view(*OPAQUE_CODES)
    assert view.codes == OPAQUE_CODES                        # 原樣、保序、不正規化、不去空白、不改大小寫
    assert all(type(c) is str for c in view.codes)
    assert len(view.codes) == len(set(OPAQUE_CODES))         # 大小寫不同＝不同代碼，都在


def test_codes_are_never_interpreted_as_identity():
    """類 ISIN 字串、數字字串、帶連字號字串都只是字串：沒有任何屬性被派生、被改寫或被標成基金身份。"""
    view = ok_view("US0378331005", "0050")
    assert view.codes == ("US0378331005", "0050")
    assert {f.name for f in dataclasses.fields(PoolSourceView)} == {"state", "codes", "reason_code", "read_at"}


def test_view_models_are_frozen_and_have_no_leaky_fields():
    view = ok_view("A1")
    with pytest.raises(dataclasses.FrozenInstanceError):
        view.codes = ("B2",)                                 # type: ignore[misc]
    for cls in (PoolSourceView, Exp2Row, Exp7Row, ExpCountsView):
        names = {f.name for f in dataclasses.fields(cls)}
        assert not names & {"message", "backend", "error", "exception", "traceback", "raw", "secret", "ttl_sec", "cooling"}, (cls, names)


@pytest.mark.parametrize("poison", ["secret-token-abc123", "https://sheets.example/?key=SECRET", "KeyError: 'private'"])
def test_validation_errors_never_echo_the_offending_value(poison):
    attempts = [
        lambda: PoolSourceView(PoolState.OK, (poison, poison)),
        lambda: PoolSourceView(PoolState.OK, (poison,), poison),
        lambda: PoolSourceView(PoolState.OK, (poison,), None, poison),
        lambda: PoolSourceView(PoolState.FAILED, (), poison),
        lambda: PoolSourceView(poison),                      # type: ignore[arg-type]
        lambda: Exp2Row(poison, poison),
        lambda: build_exp_counts(ok_view("A1"), {"A1": {"c": poison}}, ["c"]),
        lambda: build_exp_counts(ok_view("A1"), {poison: {"c": M_}}, ["c"]),
        lambda: build_exp_counts(ok_view("A1"), {}, [poison, poison]),
    ]
    for attempt in attempts:
        with pytest.raises(PoolContractError) as info:
            attempt()
        assert poison not in str(info.value) and poison not in repr(info.value.args)


# ───────────────────────── EXP-0／2／7：固定案例（預期值為字面常數） ─────────────────────────

POOL4 = ("A1", "B2", "C3", "D4")
TRI4 = {
    "A1": {"c1": M_, "c2": M_},        # 符合
    "B2": {"c1": M_, "c2": U_},        # 無法判定
    "C3": {"c1": N_, "c2": M_},        # 不符合（第一條就被排除）
    "D4": {"c1": U_, "c2": N_},        # 第一條無法判定、第二條不符合 → 被排除
}


def test_worked_example_n_m_rows_and_trajectory():
    result = build_exp_counts(ok_view(*POOL4), TRI4, ["c1", "c2"])
    assert result.status == COUNTS_COUNTED and result.counts_shown and result.conditions_count == 2
    assert (result.conclusion.matched, result.conclusion.undetermined) == (1, 1)
    assert result.conclusion.text == "目前條件下有 1 檔符合；另有 1 檔無法判定"
    assert result.rows == (Exp2Row("A1", M_), Exp2Row("B2", U_))
    assert result.trajectory == (Exp7Row("c1", 4, 2, 1), Exp7Row("c2", 3, 1, 1))


def test_exp0_text_is_reused_from_s0_not_reimplemented():
    for n_codes, tri, expected in [
        (3, {"A": M_, "B": M_, "C": M_}, ec.exp0_conclusion(1, 3, 0).text),
        (2, {"A": M_, "B": U_}, ec.exp0_conclusion(1, 1, 1).text),
        (2, {"A": N_, "B": N_}, ec.exp0_conclusion(1, 0, 0).text),
        (2, {"A": N_, "B": U_}, ec.exp0_conclusion(1, 0, 1).text),
    ]:
        codes = tuple(tri)[:n_codes]
        result = build_exp_counts(ok_view(*codes), {c: {"c1": t} for c, t in tri.items()}, ["c1"])
        assert result.conclusion.text == expected


def test_row_count_equals_n_plus_m_and_last_trajectory_row_equals_exp0():
    result = build_exp_counts(ok_view(*POOL4), TRI4, ["c1", "c2"])
    n, m = result.conclusion.matched, result.conclusion.undetermined
    ec.verify_exp2_row_count(len(result.rows), n, m)
    ec.verify_exp7_last_row([(r.matched, r.undetermined) for r in result.trajectory], n, m)
    assert len(result.rows) == n + m
    assert (result.trajectory[-1].matched, result.trajectory[-1].undetermined) == (n, m)


def test_m_greater_than_zero_never_hidden_and_never_counted_as_match():
    result = build_exp_counts(ok_view("A1", "B2"), {"A1": {"c": U_}, "B2": {"c": U_}}, ["c"])
    assert (result.conclusion.matched, result.conclusion.undetermined) == (0, 2)
    assert result.conclusion.text == "目前條件下沒有符合的基金；另有 2 檔無法判定"
    assert [r.outcome for r in result.rows] == [U_, U_]


def test_n_zero_m_zero_with_a_real_pool_is_zero_match_not_empty_pool():
    result = build_exp_counts(ok_view("A1", "B2"), {"A1": {"c": N_}, "B2": {"c": N_}}, ["c"])
    assert result.status == COUNTS_COUNTED
    assert result.conclusion.text == "目前條件下沒有符合的基金"
    assert (result.conclusion.matched, result.conclusion.undetermined) == (0, 0)
    assert result.rows == () and result.trajectory == (Exp7Row("c", 2, 0, 0),)


def test_empty_pool_is_distinct_from_a_pool_with_zero_matches_and_produces_no_counts():
    zero_match = build_exp_counts(ok_view("A1"), {"A1": {"c": N_}}, ["c"])
    empty = build_exp_counts(EMPTY_VIEW, {}, ["c"])
    assert empty.status == COUNTS_POOL_EMPTY != zero_match.status
    assert empty.conclusion is None and not empty.counts_shown and empty.rows == () and empty.trajectory == ()
    assert zero_match.conclusion is not None and zero_match.conclusion.counts_shown


@pytest.mark.parametrize("view,status", [(UNAVAILABLE_VIEW, COUNTS_POOL_UNAVAILABLE), (FAILED_VIEW, COUNTS_POOL_FAILED)])
@pytest.mark.parametrize("conditions", [[], ["c1"], ["c1", "c2"]])
def test_unavailable_or_failed_pool_never_produces_n_m_or_a_fake_zero(view, status, conditions):
    result = build_exp_counts(view, {"A1": {"c1": M_}}, conditions)        # 即使呼叫端塞了三態，也不得被用來湊 N／M
    assert result.status == status and not result.counts_shown
    assert result.conclusion is None                                        # 沒有 N／M，也沒有「沒有符合的基金」或「尚未設定條件」
    assert result.rows == () and result.trajectory == ()


def test_unavailable_and_failed_are_distinguishable_in_the_counts_result():
    assert build_exp_counts(UNAVAILABLE_VIEW, {}, ["c"]).status != build_exp_counts(FAILED_VIEW, {}, ["c"]).status


@pytest.mark.parametrize("pool", [ok_view("A1", "B2"), ok_view("A1")])
def test_zero_conditions_shows_only_the_no_condition_text(pool):
    for tri in ({}, {"A1": {"c": M_}}, None, "ignored when there are no conditions"):
        result = build_exp_counts(pool, tri, [])
        assert result.status == COUNTS_NO_CONDITIONS and result.conditions_count == 0
        assert result.conclusion.text == "尚未設定條件"
        assert (result.conclusion.matched, result.conclusion.undetermined) == (None, None) and not result.conclusion.counts_shown
        assert result.rows == () and result.trajectory == ()


def test_missing_tristate_is_undetermined_never_zero_never_no_match():
    pool = ok_view("A1", "B2", "C3")
    tri = {"A1": {"c": M_}, "B2": {"c": None}, "C3": None}                 # B2 值缺、C3 整檔缺；D4 不存在於池故不在此
    result = build_exp_counts(pool, tri, ["c"])
    assert (result.conclusion.matched, result.conclusion.undetermined) == (1, 2)
    assert result.rows == (Exp2Row("A1", M_), Exp2Row("B2", U_), Exp2Row("C3", U_))
    assert result.trajectory == (Exp7Row("c", 3, 1, 2),)
    # 整張表都沒給：全部無法判定，N 絕不是被湊出來的 0 或 3
    none_given = build_exp_counts(pool, {}, ["c"])
    assert (none_given.conclusion.matched, none_given.conclusion.undetermined) == (0, 3)


@pytest.mark.parametrize("bad", ["MATCH", "yes", "符合", 0, 1, True, False, 1.0, "", [], {}, "neutral"])
def test_tristate_values_outside_the_vocabulary_fail_closed(bad):
    with pytest.raises(PoolContractError):
        build_exp_counts(ok_view("A1"), {"A1": {"c": bad}}, ["c"])


def test_tristate_for_a_code_not_in_the_pool_fails_closed():
    with pytest.raises(PoolContractError):
        build_exp_counts(ok_view("A1"), {"A1": {"c": M_}, "ZZ": {"c": M_}}, ["c"])
    with pytest.raises(PoolContractError):                                 # 大小寫不同＝不同代碼（不透明）
        build_exp_counts(ok_view("AB1"), {"ab1": {"c": M_}}, ["c"])


@pytest.mark.parametrize("bad", [None, "c1", b"c1", {"c1"}, {"c1": 1}, 5, ["c1", "c1"], ["c1", ""], ["c1", "  "], ["c1", None], [1], [["c1"]]])
def test_conditions_must_be_a_list_or_tuple_of_unique_non_blank_ids(bad):
    with pytest.raises(PoolContractError):
        build_exp_counts(ok_view("A1"), {"A1": {"c1": M_}}, bad)


def test_pool_view_must_be_a_pool_source_view():
    for bad in (None, {}, "ok", ("A1",), {"state": "ok"}):
        with pytest.raises(PoolContractError):
            build_exp_counts(bad, {}, ["c"])                               # type: ignore[arg-type]


def test_tristate_by_code_must_be_a_mapping_when_it_is_used():
    for bad in (None, [], "x", 3):
        with pytest.raises(PoolContractError):
            build_exp_counts(ok_view("A1"), bad, ["c"])
    with pytest.raises(PoolContractError):
        build_exp_counts(ok_view("A1"), {"A1": "match"}, ["c"])


def test_rows_keep_pool_order_and_opaque_codes_exactly():
    codes = ("zz", "AB1", "ab1", "AB 1", "ＡＢ１", "US0378331005")
    tri = {c: {"c": M_} for c in codes}
    result = build_exp_counts(ok_view(*codes), tri, ["c"])
    assert tuple(r.code for r in result.rows) == codes
    assert result.conclusion.matched == len(codes)


def test_conditions_are_only_function_arguments_nothing_is_retained():
    pool, tri, conds = ok_view("A1"), {"A1": {"c": M_}}, ["c"]
    first = build_exp_counts(pool, tri, conds)
    assert (tri, conds) == ({"A1": {"c": M_}}, ["c"])                      # 輸入不被改動
    assert build_exp_counts(pool, tri, conds) == first                     # 無殘留狀態：同輸入同輸出
    other = build_exp_counts(pool, {"A1": {"c": N_}}, ["c"])
    assert other != first and build_exp_counts(pool, tri, conds) == first  # 中間換條件，不污染下一次


# ───────────────────────── 與 S0 / 獨立 oracle / 真 L2 steps 對照 ─────────────────────────

def _oracle(codes, tri, ids):
    """獨立 oracle：逐條累計（和 L2 的走法一致），不共用被測函式的任何程式碼。"""
    alive, steps = list(codes), []
    unsure = set()
    for cid in ids:
        before = len(alive)
        kept = []
        for c in alive:
            t = (tri.get(c) or {}).get(cid) or U_
            if t == N_:
                unsure.discard(c)
                continue
            if t == U_:
                unsure.add(c)
            kept.append(c)
        alive = kept
        sure = [c for c in alive if c not in unsure]
        steps.append((cid, before, len(sure), len(alive) - len(sure)))
    return alive, unsure, steps


def _random_case(rng):
    codes = tuple(f"P{i}" for i in range(rng.randint(1, 9)))
    ids = [f"k{i}" for i in range(rng.randint(1, 5))]
    tri = {c: {cid: rng.choice([M_, N_, U_, None]) for cid in ids} for c in codes if rng.random() > 0.1}
    return codes, ids, tri


def test_random_cases_match_an_independent_oracle():
    rng = random.Random(20261117)
    for _ in range(400):
        codes, ids, tri = _random_case(rng)
        alive, unsure, steps = _oracle(codes, tri, ids)
        result = build_exp_counts(ok_view(*codes), tri, ids)
        assert tuple(r.code for r in result.rows) == tuple(alive)
        assert {r.code for r in result.rows if r.outcome == U_} == unsure
        assert [(r.condition_id, r.before, r.matched, r.undetermined) for r in result.trajectory] == steps
        n = len(alive) - len(unsure)
        assert (result.conclusion.matched, result.conclusion.undetermined) == (n, len(unsure))
        assert len(result.rows) == n + len(unsure)


def test_random_cases_agree_with_the_real_l2_apply_rules_tristate_steps():
    """差分：同一組三態餵給真正的 L2 `apply_rules_tristate`（純計算），步驟與列出的檔必須相同。"""
    try:
        from services.v2_domain import rule_filter
    except ImportError as exc:
        reason = "無法 import L2 services.v2_domain.rule_filter（本機缺依賴？）：" + type(exc).__name__ + ": " + str(exc)[:160]
        if _ci_is_true():
            pytest.fail("[CI] " + reason + "（CI 環境必須有完整依賴；此處不得跳過）")
        print("[SKIP-LOCAL] " + reason, file=sys.stderr)
        pytest.skip(reason)
    rng = random.Random(7)
    for _ in range(200):
        codes, ids, tri = _random_case(rng)
        lookup = lambda left, op, right: ({M_: True, N_: False, U_: None}[(tri.get(left) or {}).get(right) or U_], "why")  # noqa: E731
        rows = [{"fund_code": c, "x": c} for c in codes]
        steps, listed, undet = rule_filter.apply_rules_tristate(
            rows, [{"field": "x", "op": "eq", "value": cid} for cid in ids], compare=lookup)
        result = build_exp_counts(ok_view(*codes), tri, ids)
        assert [(s[2], s[3]) for s in steps] == [(r.matched, r.undetermined) for r in result.trajectory]
        assert [s[1] for s in steps] == [r.before for r in result.trajectory]
        assert [r["fund_code"] for r in listed] == [r.code for r in result.rows]
        assert set(undet) == {r.code for r in result.rows if r.outcome == U_}


# ───────────────────────── ExpCountsView 自身的不變量（不信任組裝函式） ─────────────────────────

def _concl(n, m):
    return ec.exp0_conclusion(1, n, m)


def test_counts_view_rejects_inconsistent_exp2_row_count():
    with pytest.raises(PoolContractError):
        ExpCountsView(COUNTS_COUNTED, 1, _concl(2, 0), (Exp2Row("A1", M_),), (Exp7Row("c", 2, 2, 0),))
    with pytest.raises(PoolContractError):                                  # N=1、M=1：符合者夠數，但少了「無法判定」那一列
        ExpCountsView(COUNTS_COUNTED, 1, _concl(1, 1), (Exp2Row("A1", M_),), (Exp7Row("c", 2, 1, 1),))


def test_counts_view_rejects_last_trajectory_row_not_equal_to_exp0():
    rows = (Exp2Row("A1", M_), Exp2Row("B2", M_))
    with pytest.raises(PoolContractError):
        ExpCountsView(COUNTS_COUNTED, 1, _concl(2, 0), rows, (Exp7Row("c", 2, 1, 1),))
    assert ExpCountsView(COUNTS_COUNTED, 1, _concl(2, 0), rows, (Exp7Row("c", 2, 2, 0),)).conclusion.matched == 2


def test_counts_view_rejects_wrong_match_row_split_and_missing_trajectory():
    rows = (Exp2Row("A1", U_), Exp2Row("B2", U_))                           # N=2 宣稱，但列裡沒有任何「符合」
    with pytest.raises(PoolContractError):
        ExpCountsView(COUNTS_COUNTED, 1, _concl(2, 0), rows, (Exp7Row("c", 2, 2, 0),))
    with pytest.raises(PoolContractError):
        ExpCountsView(COUNTS_COUNTED, 1, _concl(0, 0), (), ())


@pytest.mark.parametrize("status", [COUNTS_POOL_EMPTY, COUNTS_POOL_UNAVAILABLE, COUNTS_POOL_FAILED])
def test_non_usable_statuses_cannot_carry_counts_or_rows(status):
    ExpCountsView(status, 1)
    with pytest.raises(PoolContractError):
        ExpCountsView(status, 1, _concl(0, 0))
    with pytest.raises(PoolContractError):
        ExpCountsView(status, 1, None, (Exp2Row("A1", M_),))
    with pytest.raises(PoolContractError):
        ExpCountsView(status, 1, None, (), (Exp7Row("c", 0, 0, 0),))


def test_no_conditions_status_requires_zero_conditions_and_the_exact_text():
    ExpCountsView(COUNTS_NO_CONDITIONS, 0, ec.exp0_conclusion(0, None, None))
    with pytest.raises(PoolContractError):
        ExpCountsView(COUNTS_NO_CONDITIONS, 1, ec.exp0_conclusion(0, None, None))
    with pytest.raises(PoolContractError):
        ExpCountsView(COUNTS_NO_CONDITIONS, 0, _concl(0, 0))                 # 不得帶 N／M
    with pytest.raises(PoolContractError):
        ExpCountsView(COUNTS_NO_CONDITIONS, 0, None)
    with pytest.raises(PoolContractError):
        ExpCountsView("whatever", 0)


def test_exp2_and_exp7_row_validation():
    for bad in ({"code": "", "outcome": M_}, {"code": "A", "outcome": N_}, {"code": "A", "outcome": "MATCH"}, {"code": None, "outcome": M_}):
        with pytest.raises(PoolContractError):
            Exp2Row(**bad)
    for bad in ((" ", 1, 1, 0), ("c", -1, 0, 0), ("c", 1, 2, 0), ("c", 1, 1, 1), ("c", None, 0, 0), ("c", True, 0, 0), ("c", 1, 1.0, 0)):
        with pytest.raises(ValueError):
            Exp7Row(*bad)
