# -*- coding: utf-8 -*-
"""S2-T0 選股池 adapter／view model 的突變測試——證明本批的契約檢查真的咬得住 **production 函式**（`DEC-2026-11-17-04`）。

做法（同 `test_ui_v3_assets_source_mutations.py`）：讀**目前**的 production 原始碼，套**一個**記憶體內字串替換（舊字串必須恰好出現一次，
否則本檔轉紅：目標消失或變得有歧義），把突變體 exec 進獨立命名空間（不寫檔、不進 `sys.modules`、不改 repo 檔案），然後
- 行為突變：跑下方的檢查集，至少一條必須失敗；
- 靜態突變：對突變後的原始碼跑 `static_problems`，至少一條必須回報。
對照組：未突變的原始碼經同一個載入器必須通過每一條檢查，所以「突變體紅燈」來自突變本身，不是載入方式。
活下來的突變只能列在 `SURVIVORS_DOCUMENTED`（附理由）；本批沒有。
"""
from __future__ import annotations

import logging
import pathlib
import sys
import types

import pytest

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import test_ui_v3_exp_pool_adapter as AT  # noqa: E402
import ui_v3_guard_lib as lib              # noqa: E402

VM_SRC = lib.ROOT / "ui_v3" / "viewmodels" / "exp_pool.py"
AD_SRC = lib.ROOT / "ui_v3" / "adapters" / "exp_pool.py"
VM_MODULE, AD_MODULE = "ui_v3.viewmodels.exp_pool", "ui_v3.adapters.exp_pool"
SURVIVORS_DOCUMENTED: dict = {}


# ───────────────────────── 載入器 ─────────────────────────

def _load(source: str, module: str):
    package = module.rsplit(".", 1)[0]
    # `__name__` 取真模組名：dataclass 解析字串註解時要在 `sys.modules` 裡找得到宿主模組（突變體本身不進 `sys.modules`）。
    ns = {"__name__": module, "__package__": package}
    exec(compile(source, f"<mutant:{module}>", "exec", dont_inherit=True), ns)   # noqa: S102 - 本 repo 自己的原始碼，一處編輯
    return types.SimpleNamespace(**{k: v for k, v in ns.items() if not k.startswith("__")})


def _mutate(path: pathlib.Path, old: str, new: str, mid: str) -> str:
    source = path.read_text(encoding="utf-8")
    count = source.count(old)
    assert count == 1, f"{mid}: old string occurs {count} times in {path.name} (must be exactly 1)"
    return source.replace(old, new)


# ───────────────────────── 檢查集：view model ＋ 組裝（M＝被測的 view model 命名空間） ─────────────────────────

def _ok(M, *codes):
    return M.PoolSourceView(M.PoolState.OK, tuple(codes), None, "2026-11-17T10:00:00+00:00")


def _empty(M):
    return M.PoolSourceView(M.PoolState.EMPTY, (), None, None)


def _failed(M):
    return M.PoolSourceView(M.PoolState.FAILED, (), M.REASON_SOURCE_FAILED, None)


def _unavailable(M):
    return M.PoolSourceView(M.PoolState.UNAVAILABLE, (), M.REASON_POOL_UNAVAILABLE, None)


_TRI = {"A1": {"c1": "match", "c2": "match"}, "B2": {"c1": "match", "c2": "undetermined"},
        "C3": {"c1": "no_match", "c2": "match"}, "D4": {"c1": "undetermined", "c2": "no_match"}}


def vm_worked_example(M):
    r = M.build_exp_counts(_ok(M, "A1", "B2", "C3", "D4"), _TRI, ["c1", "c2"])
    assert r.status == M.COUNTS_COUNTED
    assert (r.conclusion.matched, r.conclusion.undetermined) == (1, 1)
    assert r.conclusion.text == "目前條件下有 1 檔符合；另有 1 檔無法判定"
    assert [(x.code, x.outcome) for x in r.rows] == [("A1", "match"), ("B2", "undetermined")]
    assert [(x.condition_id, x.before, x.matched, x.undetermined) for x in r.trajectory] == [("c1", 4, 2, 1), ("c2", 3, 1, 1)]


def vm_all_match_and_all_no_match(M):
    r = M.build_exp_counts(_ok(M, "A", "B", "C"), {c: {"k": "match"} for c in "ABC"}, ["k"])
    assert (r.conclusion.matched, r.conclusion.undetermined, len(r.rows)) == (3, 0, 3)
    z = M.build_exp_counts(_ok(M, "A", "B"), {c: {"k": "no_match"} for c in "AB"}, ["k"])
    assert z.status == M.COUNTS_COUNTED and z.conclusion.text == "目前條件下沒有符合的基金" and z.rows == ()
    assert [(x.before, x.matched, x.undetermined) for x in z.trajectory] == [(2, 0, 0)]


def vm_m_not_hidden(M):
    r = M.build_exp_counts(_ok(M, "A", "B"), {"A": {"k": "undetermined"}, "B": {"k": "undetermined"}}, ["k"])
    assert (r.conclusion.matched, r.conclusion.undetermined) == (0, 2)
    assert r.conclusion.text == "目前條件下沒有符合的基金；另有 2 檔無法判定"


def vm_missing_is_undetermined_never_zero(M):
    r = M.build_exp_counts(_ok(M, "A1", "B2", "C3"), {"A1": {"c": "match"}, "B2": {"c": None}, "C3": None}, ["c"])
    assert (r.conclusion.matched, r.conclusion.undetermined) == (1, 2)
    assert [x.outcome for x in r.rows] == ["match", "undetermined", "undetermined"]
    none_given = M.build_exp_counts(_ok(M, "A1", "B2", "C3"), {}, ["c"])
    assert (none_given.conclusion.matched, none_given.conclusion.undetermined) == (0, 3)


def vm_pool_states_never_make_counts(M):
    for view, status in ((_empty(M), M.COUNTS_POOL_EMPTY), (_unavailable(M), M.COUNTS_POOL_UNAVAILABLE), (_failed(M), M.COUNTS_POOL_FAILED)):
        for conditions in ([], ["c"]):
            r = M.build_exp_counts(view, {"A1": {"c": "match"}}, conditions)
            assert r.status == status and r.conclusion is None and r.rows == () and r.trajectory == () and not r.counts_shown
    assert len({M.COUNTS_POOL_EMPTY, M.COUNTS_POOL_UNAVAILABLE, M.COUNTS_POOL_FAILED, M.COUNTS_COUNTED}) == 4


def vm_zero_conditions(M):
    for tri in ({}, {"A1": {"c": "match"}}, None):
        r = M.build_exp_counts(_ok(M, "A1"), tri, [])
        assert r.status == M.COUNTS_NO_CONDITIONS and r.conclusion.text == "尚未設定條件"
        assert r.conclusion.matched is None and r.conclusion.undetermined is None and r.rows == () and r.trajectory == ()


def _raises(M, fn):
    try:
        fn()
    except M.PoolContractError:
        return True
    return False


def vm_fail_closed_inputs(M):
    ok = _ok(M, "A1")
    assert _raises(M, lambda: M.build_exp_counts(ok, {"A1": {"c": "match"}, "ZZ": {"c": "match"}}, ["c"]))
    assert _raises(M, lambda: M.build_exp_counts(_ok(M, "AB1"), {"ab1": {"c": "match"}}, ["c"]))
    for bad in ("MATCH", 1, True, "neutral", ""):
        assert _raises(M, lambda bad=bad: M.build_exp_counts(ok, {"A1": {"c": bad}}, ["c"])), bad
    for bad in (["c", "c"], ["c", ""], "c", None, [1]):
        assert _raises(M, lambda bad=bad: M.build_exp_counts(ok, {"A1": {"c": "match"}}, bad)), bad
    # 垃圾值若被後面的「不符合」擋掉，結果上看不出來——詞彙檢查必須在輸入端就擋（不能靠事後一致性碰巧攔到）
    assert _raises(M, lambda: M.build_exp_counts(ok, {"A1": {"c1": "MATCH", "c2": "no_match"}}, ["c1", "c2"]))
    assert _raises(M, lambda: M.build_exp_counts(ok, {"A1": {"c1": 7, "c2": "no_match"}}, ["c1", "c2"]))
    assert _raises(M, lambda: M.build_exp_counts(None, {}, []))
    assert _raises(M, lambda: M.build_exp_counts(ok, [], ["c"]))


def vm_view_contradictions(M):
    S, P = M.PoolState, M.PoolSourceView
    for kwargs in (dict(state=S.OK, codes=()), dict(state=S.EMPTY, codes=("A1",)), dict(state=S.OK, codes=("A1", "A1")),
                   dict(state=S.OK, codes=("A1",), reason_code=M.REASON_SOURCE_FAILED), dict(state=S.OK, codes=("A1", " ")),
                   dict(state=S.OK, codes=["A1"]), dict(state=S.FAILED, reason_code="free text"), dict(state=S.FAILED, reason_code=None),
                   dict(state=S.UNAVAILABLE, reason_code=M.REASON_SOURCE_FAILED), dict(state=S.FAILED, codes=("A1",), reason_code=M.REASON_SOURCE_FAILED),
                   dict(state=S.OK, codes=("A1",), read_at="not a date"), dict(state=S.FAILED, reason_code=M.REASON_SOURCE_FAILED, read_at="2026-11-17T10:00:00+00:00"),
                   dict(state="ok", codes=("A1",))):
        assert _raises(M, lambda kwargs=kwargs: P(**kwargs)), kwargs


def vm_opaque_codes(M):
    codes = ("AB1", "ab1", "AB 1", "ＡＢ１", "US0378331005", " lead")
    assert _ok(M, *codes).codes == codes


def vm_no_echo(M):
    poison = "secret-token-abc123"
    for fn in (lambda: M.PoolSourceView(M.PoolState.OK, (poison, poison)), lambda: M.PoolSourceView(M.PoolState.FAILED, (), poison),
               lambda: M.build_exp_counts(_ok(M, "A1"), {"A1": {"c": poison}}, ["c"]), lambda: M.build_exp_counts(_ok(M, "A1"), {poison: {}}, ["c"])):
        try:
            fn()
        except M.PoolContractError as exc:
            assert poison not in str(exc) and poison not in repr(exc.args)
        else:
            raise AssertionError("expected PoolContractError")


def vm_counts_view_invariants(M):
    from ui_v3.viewmodels import exp_counts as ec
    concl = ec.exp0_conclusion(1, 2, 0)
    rows2 = (M.Exp2Row("A1", "match"), M.Exp2Row("B2", "match"))
    good = (M.Exp7Row("c", 2, 2, 0),)
    assert M.ExpCountsView(M.COUNTS_COUNTED, 1, concl, rows2, good).conclusion.matched == 2
    assert _raises(M, lambda: M.ExpCountsView(M.COUNTS_COUNTED, 1, concl, rows2[:1], good))                       # 列數 ≠ N+M
    concl_nm = ec.exp0_conclusion(1, 1, 1)                                                                          # N=1、M=1，但只有 1 列（符合者夠數、少了無法判定那一列）
    assert _raises(M, lambda: M.ExpCountsView(M.COUNTS_COUNTED, 1, concl_nm, rows2[:1], (M.Exp7Row("c", 2, 1, 1),)))
    assert _raises(M, lambda: M.ExpCountsView(M.COUNTS_COUNTED, 1, concl, rows2, (M.Exp7Row("c", 2, 1, 1),)))     # 末列 ≠ EXP-0
    assert _raises(M, lambda: M.ExpCountsView(M.COUNTS_POOL_FAILED, 1, concl))
    assert _raises(M, lambda: M.ExpCountsView(M.COUNTS_NO_CONDITIONS, 0, concl))


VM_CHECKS = [vm_worked_example, vm_all_match_and_all_no_match, vm_m_not_hidden, vm_missing_is_undetermined_never_zero, vm_pool_states_never_make_counts,
             vm_zero_conditions, vm_fail_closed_inputs, vm_view_contradictions, vm_opaque_codes, vm_no_echo, vm_counts_view_invariants]


# ───────────────────────── 檢查集：adapter（A＝被測的 adapter 命名空間；view model 用真的） ─────────────────────────

def _fails_closed(A, raw):
    try:
        A.adapt_pool_result(raw)
    except AT.PoolContractError:
        return True
    return False


def ad_four_states(A):
    S = AT.PoolState
    assert A.adapt_pool_result(AT.l2_ok(("A1",))).state is S.OK
    assert A.adapt_pool_result(AT.l2_ok(())).state is S.EMPTY
    failed, cooling = A.adapt_pool_result(AT.l2_not_ok("failed")), A.adapt_pool_result(AT.l2_not_ok("failed", cooling=True))
    unavailable = A.adapt_pool_result(AT.l2_not_ok("pool_not_cloud"))
    assert failed.state is S.FAILED and failed.reason_code == AT.REASON_SOURCE_FAILED
    assert cooling.state is S.FAILED and cooling.reason_code == AT.REASON_SOURCE_COOLING
    assert unavailable.state is S.UNAVAILABLE and unavailable.reason_code == AT.REASON_POOL_UNAVAILABLE


def ad_unknown_and_malformed_fail_closed(A):
    for status in ("mystery", "OK", "", "ok ", None, 1, ["ok"]):
        assert _fails_closed(A, AT.l2_ok(("A1",), status=status)), status
        assert _fails_closed(A, AT.l2_not_ok(status=status)), status
    for raw in (None, [], "ok", 0):
        assert _fails_closed(A, raw)
    for key in AT.adapter.L2_REQUIRED_KEYS:
        raw = AT.l2_ok()
        del raw[key]
        assert _fails_closed(A, raw), key


def ad_type_and_contradiction_failures(A):
    for over in (dict(codes=None), dict(codes="A1"), dict(codes=("A1",)), dict(codes=[None]), dict(codes=[""]), dict(codes=["A1", "A1"]),
                 dict(dropped_blank=True), dict(dropped_blank=-1), dict(duplicates=1.0), dict(backend=None), dict(ttl_sec=0), dict(ttl_sec=True),
                 dict(cooling=1), dict(cooling=True), dict(message="boom"), dict(read_at="garbage")):
        assert _fails_closed(A, AT.l2_ok(("A1",), **over)), over
    for status in ("failed", "pool_not_cloud"):
        for over in (dict(codes=["A1"]), dict(message=None), dict(message=5), dict(read_at=AT.READ_AT), dict(dropped_blank=1), dict(duplicates=1),
                     dict(codes=None), dict(cooling="no")):
            assert _fails_closed(A, AT.l2_not_ok(status, **over)), (status, over)
    assert _fails_closed(A, AT.l2_not_ok("pool_not_cloud", cooling=True))


class _Boom(Exception):
    pass


def ad_loader_exception_is_failed_without_leak(A):
    poison = "secret-token-abc123"
    lines = []

    class Handler(logging.Handler):
        def emit(self, record):
            lines.append(record.getMessage())

    handler, root = Handler(logging.DEBUG), logging.getLogger()
    previous = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)

    def loader(_):
        raise _Boom(poison)

    try:
        view = A.load_pool_view(loader, [poison])
    finally:
        root.removeHandler(handler)
        root.setLevel(previous)
    assert view.state is AT.PoolState.FAILED and view.reason_code == AT.REASON_LOADER_RAISED
    assert poison not in repr(view) and all(poison not in line for line in lines) and lines


def ad_loader_contract_error_still_raises(A):
    for bad in (None, {}, AT.l2_ok(("A1",), status="mystery"), "ok"):
        try:
            A.load_pool_view(lambda _s, bad=bad: bad, [])
        except AT.PoolContractError:
            continue
        raise AssertionError("contract error must propagate")


def ad_loader_is_injected_and_receives_secrets(A):
    import inspect
    assert [p.default for p in inspect.signature(A.load_pool_view).parameters.values()] == [inspect.Parameter.empty] * 2
    seen = []
    A.load_pool_view(lambda s: seen.append(s) or AT.l2_ok(("A1",)), ["s1", "s2"])
    assert seen == [["s1", "s2"]]
    for bad in (None, "x", 3):
        try:
            A.load_pool_view(bad, [])
        except AT.PoolContractError:
            continue
        raise AssertionError("loader must be callable")


def ad_base_exceptions_pass_through(A):
    def loader(_):
        raise KeyboardInterrupt()

    try:
        A.load_pool_view(loader, [])
    except KeyboardInterrupt:
        return
    raise AssertionError("KeyboardInterrupt must not be swallowed")


def ad_ordinary_exceptions_all_failed(A):
    for exc in (KeyError("k"), RuntimeError("r"), OSError(1, "o")):
        def loader(_, exc=exc):
            raise exc
        assert A.load_pool_view(loader, []).state is AT.PoolState.FAILED


AD_CHECKS = [ad_four_states, ad_unknown_and_malformed_fail_closed, ad_type_and_contradiction_failures, ad_loader_exception_is_failed_without_leak,
             ad_loader_contract_error_still_raises, ad_loader_is_injected_and_receives_secrets, ad_base_exceptions_pass_through, ad_ordinary_exceptions_all_failed]


def _failures(checks, module) -> list:
    failed = []
    for fn in checks:
        try:
            fn(module)
        except BaseException as exc:  # noqa: BLE001 - 任何失敗或崩潰都代表「突變被發現」；KeyboardInterrupt 不吞
            if isinstance(exc, KeyboardInterrupt):
                raise
            failed.append(fn.__name__)
    return failed


# ───────────────────────── 突變清單：(id, old〔恰好一次〕, new, 它破壞什麼) ─────────────────────────

VIEWMODEL = [
    ("V01_n_counts_all_rows", "    n = sum(1 for r in rows if r.outcome == TRI_MATCH)\n    m = len(rows) - n", "    n = len(rows)\n    m = 0", "N 把無法判定也算成符合"),
    ("V02_alive_ignores_no_match", "alive = sum(1 for tris in per_code.values() if TRI_NO_MATCH not in tris[: step + 1])", "alive = len(per_code)",
     "EXP-7 把不符合者仍算在存活數"),
    ("V03_missing_value_becomes_no_match", "    value = per_code.get(condition_id)\n    if value is None:\n        return TRI_UNDETERMINED",
     "    value = per_code.get(condition_id)\n    if value is None:\n        return TRI_NO_MATCH", "缺值被當成不符合（偽稱 0）"),
    ("V04_missing_code_becomes_match", "    if per_code is None:\n        return TRI_UNDETERMINED", "    if per_code is None:\n        return TRI_MATCH", "整檔缺值被當成符合"),
    ("V05_unknown_code_allowed", "    if unknown:\n", "    if False:\n", "三態輸入含不在池內的代碼仍放行"),
    ("V06_empty_pool_counted", "    if pool_view.state is PoolState.EMPTY:\n        return ExpCountsView(COUNTS_POOL_EMPTY, len(ids))",
     "    if False:\n        return ExpCountsView(COUNTS_POOL_EMPTY, len(ids))", "空池被併入「沒有符合的基金」"),
    ("V07_unavailable_reported_as_failed", "return ExpCountsView(COUNTS_POOL_UNAVAILABLE, len(ids))", "return ExpCountsView(COUNTS_POOL_FAILED, len(ids))",
     "不可用與失敗混為一談"),
    ("V08_zero_conditions_counted", "    if not ids:\n        return ExpCountsView(COUNTS_NO_CONDITIONS", "    if False:\n        return ExpCountsView(COUNTS_NO_CONDITIONS",
     "零條件仍展示 N／M"),
    ("V09_no_match_rows_listed", "        if TRI_NO_MATCH in tris:\n            continue", "        if False:\n            continue", "不符合的檔也被列進 EXP-2"),
    ("V10_duplicate_codes_allowed", '_need(len(set(self.codes)) == len(self.codes), "codes", "no duplicates", self.codes)',
     '_need(True, "codes", "no duplicates", self.codes)', "選股池代碼重複被放行"),
    ("V11_reason_code_unchecked", "_need(isinstance(self.reason_code, str) and self.reason_code in allowed,", "_need(True,", "失敗／不可用的類別碼不驗（可塞自由文字）"),
    ("V12_error_echoes_value", 'f"{field}: expected {expected}, got {_kind(value)}"', 'f"{field}: expected {expected}, got {value!r}"', "驗證錯誤回顯收到的值"),
    ("V13_m_dropped_from_exp0", "exp0_conclusion(len(ids), n, m)", "exp0_conclusion(len(ids), n, 0)", "EXP-0 隱藏 M"),
    ("V14_undetermined_listed_as_match", "TRI_UNDETERMINED if TRI_UNDETERMINED in tris else TRI_MATCH", "TRI_MATCH", "無法判定被列成符合"),
    ("V15_ok_with_reason_code", '_need(self.reason_code is None, "reason_code", "None when state is OK", self.reason_code)', '_need(True, "reason_code", "None when state is OK", self.reason_code)',
     "OK 狀態可夾帶失敗類別碼"),
    ("V16_ok_with_no_codes", '_need(len(self.codes) > 0, "codes", "non-empty tuple when state is OK", self.codes)', '_need(True, "codes", "non-empty tuple when state is OK", self.codes)',
     "OK 卻沒有代碼（與 EMPTY 混淆）"),
    ("V17_empty_with_codes", '_need(len(self.codes) == 0, "codes", "empty tuple when state is EMPTY", self.codes)', '_need(True, "codes", "empty tuple when state is EMPTY", self.codes)',
     "EMPTY 卻帶代碼"),
    ("V18_read_at_unvalidated", "_dt.datetime.fromisoformat(self.read_at)", "None", "read_at 不驗 ISO"),
    ("V19_exp2_row_count_unchecked", "verify_exp2_row_count(len(self.rows), n, m)", "pass", "EXP-2 列數與 N+M 的一致性不驗"),
    ("V20_exp7_last_row_unchecked", "verify_exp7_last_row([(r.matched, r.undetermined) for r in self.trajectory], n, m)", "pass", "EXP-7 末列與 EXP-0 的一致性不驗"),
    ("V21_before_is_always_pool_size", "        alive_before = alive\n", "        alive_before = len(pool_view.codes)\n", "EXP-7 的套用前不是上一列的存活數"),
    ("V22_sure_uses_any", "all(t == TRI_MATCH for t in tris[: step + 1])", "any(t == TRI_MATCH for t in tris[: step + 1])", "只要有一條符合就算全部符合"),
    ("V23_conditions_not_unique", '_need(len(set(conditions)) == len(conditions), "conditions", "unique ids", conditions)',
     '_need(True, "conditions", "unique ids", conditions)', "條件 id 重複被放行"),
    ("V24_tristate_vocabulary_unchecked", '_need(isinstance(value, str) and value in _TRI_VALUES, "tristate value", "match/no_match/undetermined", value)',
     '_need(True, "tristate value", "match/no_match/undetermined", value)', "三態輸入不在詞彙內仍被當成符合"),
    ("V25_empty_pool_with_counts_view", '            _need(self.conclusion is None, "conclusion", "None when the pool yields no counts", self.conclusion)',
     '            pass', "不可用／失敗／空池的結果可以夾帶結論"),
]

ADAPTER = [
    ("A01_unknown_status_passes", "    if status not in _KNOWN_STATUSES:", "    if False:", "未知 status 被放行"),
    ("A02_failed_is_empty", "return PoolSourceView(PoolState.FAILED, (), REASON_SOURCE_COOLING if cooling else REASON_SOURCE_FAILED, None)",
     "return PoolSourceView(PoolState.EMPTY, (), None, None)", "來源失敗被當成空池"),
    ("A03_ok_empty_stays_ok", "PoolState.OK if codes else PoolState.EMPTY", "PoolState.OK", "空池沒有被分成 EMPTY"),
    ("A04_not_cloud_is_failed", "return PoolSourceView(PoolState.UNAVAILABLE, (), REASON_POOL_UNAVAILABLE, None)",
     "return PoolSourceView(PoolState.FAILED, (), REASON_SOURCE_FAILED, None)", "pool_not_cloud 被當成來源失敗"),
    ("A05_codes_type_unchecked", '_need(isinstance(raw["codes"], list), "codes", "list", raw["codes"])', '_need(True, "codes", "list", raw["codes"])', "codes 不是 list 也放行"),
    ("A06_missing_keys_unchecked", "    if missing:\n", "    if False:\n", "缺鍵不擋"),
    ("A07_loader_exception_not_caught", "    except Exception as exc:", "    except KeyError as exc:", "取數函式拋例外沒轉成失敗"),
    ("A08_log_leaks_exception_text", "type(exc).__name__)", "exc)", "例外字串進 log"),
    ("A09_contract_error_swallowed",
     "    return adapt_pool_result(raw)\n",
     "    try:\n        return adapt_pool_result(raw)\n    except Exception:\n        return PoolSourceView(PoolState.FAILED, (), REASON_LOADER_RAISED, None)\n",
     "契約錯誤被吞成 FAILED"),
    ("A10_cooling_ignored", "REASON_SOURCE_COOLING if cooling else REASON_SOURCE_FAILED", "REASON_SOURCE_FAILED", "冷卻中與一般失敗不分"),
    ("A11_ok_may_carry_message", '_need(message is None, "message", "None when status is ok", message)', '_need(True, "message", "None when status is ok", message)',
     "status=ok 卻帶訊息仍放行"),
    ("A12_failed_may_carry_codes", '_need(len(raw["codes"]) == 0, "codes", "empty list when status is not ok", raw["codes"])',
     '_need(True, "codes", "empty list when status is not ok", raw["codes"])', "failed 卻帶代碼仍放行"),
    ("A13_bool_counts_accepted", "isinstance(value, int) and not isinstance(value, bool) and value >= 0", "isinstance(value, int)", "bool／負數當統計值放行"),
    ("A14_secrets_not_forwarded", "raw = loader(secret_values)", "raw = loader([])", "遮蔽用的 secret_values 沒有轉交給取數函式"),
    ("A15_loader_has_default", "def load_pool_view(loader: Callable[..., object], secret_values: Iterable[str])",
     "def load_pool_view(loader: Callable[..., object] = None, secret_values: Iterable[str] = ())", "取數函式有預設值（不再必須由呼叫端注入）"),
    ("A16_failed_may_carry_read_at", '_need(read_at is None, "read_at", "None when status is not ok", read_at)', '_need(True, "read_at", "None when status is not ok", read_at)',
     "failed 卻帶讀取時間仍放行"),
    ("A17_failed_message_unchecked", '_need(isinstance(message, str), "message", "str when status is not ok", message)', '_need(True, "message", "str when status is not ok", message)',
     "failed 的 message 型別不驗"),
    ("A18_failed_stats_unchecked", '_need(dropped_blank == 0 and duplicates == 0, "dropped_blank/duplicates", "0 when status is not ok", dropped_blank)',
     '_need(True, "dropped_blank/duplicates", "0 when status is not ok", dropped_blank)', "failed 卻帶統計仍放行"),
    ("A19_loader_callable_unchecked", '_need(callable(loader), "loader", "callable", loader)', '_need(True, "loader", "callable", loader)',
     "取數函式不是 callable 被當成取數失敗"),
    ("A20_status_type_unchecked", '_need(isinstance(status, str), "status", "str", status)', '_need(True, "status", "str", status)', "status 型別不驗"),
    ("A21_cloud_cooling_allowed", '_need(not cooling, "cooling", "False when status is pool_not_cloud", cooling)', '_need(True, "cooling", "False when status is pool_not_cloud", cooling)',
     "pool_not_cloud 可以同時冷卻中"),
]

# 靜態突變：(id, 檔, old〔恰好一次〕, new, 說明)
STATIC = [
    ("S01_adapter_imports_os", AD_SRC, "import logging\n", "import logging\nimport os\n", "adapter 讀環境變數"),
    ("S02_adapter_imports_real_l2", AD_SRC, "import logging\n", "import logging\nfrom services.v2_tables import exp_universe\n", "adapter import 真實 L2"),
    ("S03_adapter_imports_identity_resolver", AD_SRC, "import logging\n", "import logging\nfrom services.v2_tables.fund_keys import resolve_full_keys\n",
     "adapter 解析身份（冒用 R-ID-1）"),
    ("S04_adapter_imports_requests", AD_SRC, "import logging\n", "import logging\nimport requests\n", "adapter 發網路請求"),
    ("S05_viewmodel_imports_streamlit", VM_SRC, "import datetime as _dt\n", "import datetime as _dt\nimport streamlit as st\n", "view model 碰 session_state"),
    ("S06_viewmodel_writes_file", VM_SRC, "def _kind(value: object) -> str:\n    return type(value).__name__\n",
     "def _kind(value: object) -> str:\n    open('x.txt', 'w').write('1')\n    return type(value).__name__\n", "view model 寫檔"),
    ("S07_adapter_reads_environment", AD_SRC, "def _non_negative_int(raw: dict, field: str) -> int:\n",
     "def _non_negative_int(raw: dict, field: str) -> int:\n    import os\n    os.environ.get('K')\n", "adapter 在函式內讀環境變數"),
    ("S08_adapter_imports_json_persistence", AD_SRC, "import logging\n", "import logging\nimport sqlite3\n", "adapter 寫持久層"),
]


def test_control_unmutated_sources_pass_every_check_and_static_rule():
    vm = _load(VM_SRC.read_text(encoding="utf-8"), VM_MODULE)
    ad = _load(AD_SRC.read_text(encoding="utf-8"), AD_MODULE)
    assert _failures(VM_CHECKS, vm) == [] and _failures(AD_CHECKS, ad) == []
    assert AT.static_problems(AT.VIEWMODEL_REL, VM_SRC.read_text(encoding="utf-8")) == []
    assert AT.static_problems(AT.ADAPTER_REL, AD_SRC.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("mutation", VIEWMODEL, ids=lambda m: m[0])
def test_viewmodel_mutation_is_killed(mutation):
    mid, old, new, doc = mutation
    killers = _failures(VM_CHECKS, _load(_mutate(VM_SRC, old, new, mid), VM_MODULE))
    assert killers, f"{mid} ({doc}): no check noticed the mutation"


@pytest.mark.parametrize("mutation", ADAPTER, ids=lambda m: m[0])
def test_adapter_mutation_is_killed(mutation):
    mid, old, new, doc = mutation
    killers = _failures(AD_CHECKS, _load(_mutate(AD_SRC, old, new, mid), AD_MODULE))
    assert killers, f"{mid} ({doc}): no check noticed the mutation"


@pytest.mark.parametrize("mutation", STATIC, ids=lambda m: m[0])
def test_static_mutation_is_killed(mutation):
    mid, path, old, new, doc = mutation
    rel = AT.VIEWMODEL_REL if path == VM_SRC else AT.ADAPTER_REL
    assert AT.static_problems(rel, _mutate(path, old, new, mid)), f"{mid} ({doc}): no static rule noticed the mutation"


def test_no_surviving_mutants_are_hiding_and_lists_are_not_trivial():
    ids = [m[0] for m in VIEWMODEL + ADAPTER] + [m[0] for m in STATIC]
    assert len(ids) == len(set(ids)) and not SURVIVORS_DOCUMENTED
    assert len(VIEWMODEL) >= 20 and len(ADAPTER) >= 18 and len(STATIC) >= 8


def test_mutants_do_not_replace_or_pollute_sys_modules():
    real_vm, real_ad = sys.modules[VM_MODULE], sys.modules[AD_MODULE]
    before = set(sys.modules)
    _load(_mutate(VM_SRC, *VIEWMODEL[0][1:3], VIEWMODEL[0][0]), VM_MODULE)
    _load(_mutate(AD_SRC, *ADAPTER[0][1:3], ADAPTER[0][0]), AD_MODULE)
    assert sys.modules[VM_MODULE] is real_vm and sys.modules[AD_MODULE] is real_ad and set(sys.modules) == before


def test_mutation_targets_are_production_files_not_tests():
    assert VM_SRC.parts[-3:] == ("ui_v3", "viewmodels", "exp_pool.py") and AD_SRC.parts[-3:] == ("ui_v3", "adapters", "exp_pool.py")
