# -*- coding: utf-8 -*-
"""`ui_v3/adapters/assets_source.py`（BL-0542 G-2「Preview 載入端」）的合約與降級矩陣測試。

兩種用途共用同一份 `CHECKS` 登錄表（體例同 `tests/test_v2_domain_allocation_evidence.py`）：
(a) 這裡對**真的**模組跑；(b) `test_ui_v3_assets_source_mutations.py` 對記憶體內的突變體跑，突變體必須至少讓一條檢查轉紅。

被測的東西：L2 結果 → 證據用引數的映射、fail-closed 降級、遮蔽、嚴格 JSON、純度。**生產者（`build_allocation_evidence`）是真的**，
所以斷言的是「生產者看到我們給的引數後回什麼」；期望值一律由本檔從輸入獨立算出（成本加總、占比），不從 adapter 的輸出抄。
持倉表是 L2 純函式 `build_alo_tables` 的真形狀（過 `contract.holding_row_problems`）；設定列是 L1 的真形狀。
L2 讀取入口與例外型別是替身——**這不證明真實的 Google／MoneyDJ／Yahoo 連線可用**（需要憑證；見 adapter 檔頭）。
"""
from __future__ import annotations

import copy
import json
import pathlib
import socket
import sys

import pytest

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import assets_source_support as X  # noqa: E402
from services.v2_domain import allocation_evidence as EV  # noqa: E402
from ui_v3.adapters import assets_source as REAL  # noqa: E402

REAL_PRODUCER = EV.build_allocation_evidence
SETTINGS_KEYS = ("alo_basis", "alo_target_weights", "alo_tolerance_pp", "alo_bucket_names")


class Spy:
    """記錄每次呼叫的生產者替身（呼叫真的生產者）。"""

    def __init__(self):
        self.calls = []

    def __call__(self, tables, **kw):
        self.calls.append((tables, kw))
        return REAL_PRODUCER(tables, **kw)


def run(M, *, secrets=(X.SECRET,), spy=None, **kw):
    reads, calls = X.make_reads(M, **kw)
    state = {}
    result = M.load(state, list(secrets), reads=reads, producer=spy)
    return result.to_primitive(), result, calls


def _by(items, key):
    return {i[key]: i for i in items}


def _dump(p):
    return json.dumps(p, ensure_ascii=False, allow_nan=False, sort_keys=True)


# ═══════════════════════ CHECKS ═══════════════════════


def check_happy_numbers_and_provenance(M):
    tables = X.two_fund_tables()
    p, result, calls = run(M, holdings=tables)
    assert p["status"] == "evaluated" and p["blocked_reason"] is None and p["problems"] == []
    e = p["evidence"]
    assert e["producer_id"] == EV.PRODUCER_ID and e["schema_version"] == EV.SCHEMA_VERSION
    holds = _by(e["holdings"], "fund_code")
    assert set(holds) == {"ZZ1", "ZZ2"}
    for src in tables["holding"]:        # 輸入列（L2 真形狀）逐檔對證據
        h = holds[src["fund_code"]]
        assert h["policy_id"] == src["policy_id"] and h["holding_id"] == src["holding_id"]
        assert h["value_status"] == "valued" and h["valued"] is True
        assert h["value_twd"] == float(src["cost_twd"]) and not isinstance(h["value_twd"], bool)
        assert h["cost_twd"] == src["cost_twd"] and h["units_shares"] == src["units_shares"]
        assert h["nav"]["status"] == "not_required" and h["fx"]["status"] == "not_required"
        assert h["source_row_count"] == 1 and h["source_rows"][0]["cost_twd"] == src["cost_twd"]
        assert h["reason"] is None and h["missing_kind"] is None
    cats = _by(e["categories"], "category")
    total = sum(h["cost_twd"] for h in tables["holding"])
    assert set(cats) == {"core", "sat"} and e["denominator"]["value_twd"] == float(total)
    assert e["denominator"]["verdict"] == "complete" and e["denominator"]["raw_row_count"] == 2
    for name, expect in (("core", 300000), ("sat", 100000)):
        c = cats[name]
        assert c["value_twd"] == float(expect) and c["status"] == "valued" and c["origin"] == "from_holdings"
        assert c["share"]["status"] == "computed" and c["share"]["covers_all_holdings"] is True
        assert c["share"]["share_of_covered_pct"] == expect / total * 100.0
        assert c["target"]["status"] == "set"
    assert e["source_coverage"]["status"] == "complete" and e["valuation_completeness"]["status"] == "complete"
    assert e["settings"]["basis"] == {"status": "set", "value": "成本"}
    assert e["settings"]["tolerance"]["value"] == 5.0
    assert e["settings"]["basis_market"] is False and e["settings"]["targets_weight_sum"] == 1.0
    assert e["input_problems"] == [] and e["evaluation_errors"] == [] and e["identity_conflict"] is None
    assert e["source"]["active_source"] == "selected"
    assert e["source"]["skipped_tabs"]["status"] == "provided" and e["source"]["omitted_rows"]["status"] == "provided"
    assert calls.settings == [(X.SECRET,)] and len(calls.holdings) == 1


def check_no_active_source_both_forms(M):
    for exc in (X.FakeActiveSourceError("AUTH_REQUIRED"), X.FakeActiveSourceError("UNAVAILABLE", "no_active")):
        p, _r, calls = run(M, holding_exc=exc)
        e = p["evidence"]
        assert p["problems"] == ["no_active_source"] and p["holding_failure_code"] is None
        assert e["source"]["active_source"] == "none" and e["holdings"] == []
        assert e["source_coverage"]["status"] == "not_selected" and "no_active_source" in e["source_coverage"]["reason_codes"]
        assert e["valuation_completeness"]["status"] == "not_evaluated"
        assert e["chart_comparability"]["status"] == "not_evaluated"          # 不是 comparable，也不是「完整的空」
        assert e["denominator"]["value_twd"] is None and e["categories"] == []
        assert e["coverage"]["uncovered_value"]["status"] != "none_uncovered"
        assert e["source"]["read_errors"]["items"] == []                      # 「沒有 Active」不是讀取錯誤
        assert len(calls.settings) == 1 and len(calls.holdings) == 1


def check_other_active_source_error_is_a_read_failure(M):
    for code, reason in (("PERMISSION_DENIED", None), ("UNAVAILABLE", "deploy_config"), ("NETWORK_ERROR", None),
                         ("SCHEMA_INVALID", "policy_header")):
        p, _r, _c = run(M, holding_exc=X.FakeActiveSourceError(code, reason))
        e = p["evidence"]
        assert p["problems"] == ["holding_read_failed"] and p["holding_failure_code"] == code
        assert e["source"]["active_source"] == "selected"
        assert dict(map(tuple, e["source"]["read_errors"]["items"])) == {"holding": f"holding source read failed ({code})"}
        assert e["source_coverage"]["status"] == "failed" and e["valuation_completeness"]["status"] == "failed"
        assert e["chart_comparability"]["status"] == "not_comparable"
        assert e["holdings"] == [] and e["denominator"]["value_twd"] is None
    # 不在白名單內的 code（可能夾帶秘密）一律寫成 unknown
    p, _r, _c = run(M, holding_exc=X.FakeActiveSourceError(X.SECRET))
    assert p["holding_failure_code"] == "unknown" and X.SECRET not in _dump(p)
    p, _r, _c = run(M, holding_exc=X.FakeActiveSourceError(None))
    assert p["holding_failure_code"] == "unknown"


def check_settings_read_failure(M):
    p, _r, _c = run(M, holdings=X.two_fund_tables(), settings_exc=X.FakeSettingsError("boom " + X.SECRET))
    e = p["evidence"]
    assert p["problems"] == ["settings_read_failed"]
    assert dict(p["settings_status"]) == {k: "read_failed" for k in SETTINGS_KEYS}
    for name in ("basis", "targets", "tolerance", "bucket_names"):
        assert e["settings"][name]["status"] == "read_failed"                  # 不是 unset
    assert dict(map(tuple, e["source"]["read_errors"]["items"])) == {"user_setting": "user_setting read failed"}
    assert e["valuation_completeness"]["status"] == "failed"
    assert e["source_coverage"]["status"] == "incomplete" and "settings_read_failed" in e["source_coverage"]["reason_codes"]
    assert e["chart_comparability"]["status"] == "not_comparable"
    assert X.SECRET not in _dump(p) and "boom" not in _dump(p)                  # 原文一律丟棄


def check_unset_basis_is_not_defaulted_to_cost(M):
    spy = Spy()
    p, _r, _c = run(M, holdings=X.two_fund_tables(), settings=X.settings_payload(X.settings_rows(basis=None)), spy=spy)
    e = p["evidence"]
    assert e["settings"]["basis"]["status"] == "unset" and e["settings"]["basis"]["value"] is None
    assert spy.calls[0][1]["settings"]["basis"] is None
    assert e["valuation_completeness"] == {"status": "not_evaluated", "reason_codes": ["basis_unset"]}
    assert all(h["value_status"] == "not_evaluated" and h["value_twd"] is None for h in e["holdings"])
    assert e["denominator"]["value_twd"] is None and e["categories"] == []
    assert e["chart_comparability"]["status"] == "not_evaluated"
    assert p["problems"] == [] and dict(p["settings_status"])["alo_basis"] == "unset"
    # 整張設定表都沒有（分頁存在但沒有任何列）：同樣是 unset，不是 read_failed、不是預設成本
    p, _r, _c = run(M, holdings=X.two_fund_tables(), settings=X.settings_payload({}))
    assert {k: v["status"] for k, v in p["evidence"]["settings"].items() if k in ("basis", "targets", "tolerance", "bucket_names")} \
        == {"basis": "unset", "targets": "unset", "tolerance": "unset", "bucket_names": "unset"}


def check_invalid_or_broken_setting_is_not_unset(M):
    bad_targets = X.settings_rows(targets='[{"bucket":"core","weight_ratio":60}]')       # 60 不是 0~1 的比率
    p, _r, _c = run(M, holdings=X.two_fund_tables(), settings=X.settings_payload(bad_targets))
    e = p["evidence"]
    assert p["problems"] == ["settings_value_unusable"]
    assert dict(p["settings_status"]) == {"alo_basis": "set", "alo_target_weights": "invalid",
                                          "alo_tolerance_pp": "set", "alo_bucket_names": "set"}
    assert e["settings"]["targets"]["status"] == "read_failed" and e["settings"]["basis"]["status"] == "read_failed"
    assert dict(map(tuple, e["source"]["read_errors"]["items"])) == {"user_setting": "user_setting value unusable"}
    assert e["valuation_completeness"]["status"] == "failed" and e["chart_comparability"]["status"] == "not_comparable"
    # 最新一列壞掉的鍵（L1 的 broken_keys）：與 invalid 同樣不是「未設定」，且狀態分開記
    p, _r, _c = run(M, holdings=X.two_fund_tables(), settings=X.settings_payload(
        {k: v for k, v in X.settings_rows().items() if k != "alo_tolerance_pp"}, broken=["alo_tolerance_pp"]))
    assert dict(p["settings_status"])["alo_tolerance_pp"] == "broken_row"
    assert p["evidence"]["settings"]["tolerance"]["status"] == "read_failed" and p["problems"] == ["settings_value_unusable"]


def check_skipped_evidence_downgrades_and_is_masked(M):
    tables = X.tables_with_skips()
    assert tables["skipped_holdings"] and tables["skipped_tabs"]
    p, _r, _c = run(M, holdings=tables)
    e = p["evidence"]
    assert e["source_coverage"]["status"] == "incomplete"
    assert {"skipped_tabs_present", "omitted_rows_present"} <= set(e["source_coverage"]["reason_codes"])
    assert e["denominator"]["omitted_row_count"] == 1 and e["denominator"]["skipped_tab_count"] == 1
    assert e["chart_comparability"]["status"] == "not_comparable"
    assert e["source"]["skipped_tabs"]["items"][0]["tab"] == "PX-OTHER"
    assert e["source"]["omitted_rows"]["items"][0]["fund_code"] == "ZZ2" and e["source"]["omitted_rows"]["items"][0]["row"] == 3
    assert e["source"]["omitted_rows"]["items"][0]["tab"] == "PX-TEST-001" and e["source"]["omitted_rows"]["items"][0]["reasons"]
    assert "omitted_row_reason_codes_undefined" in e["open_gates"]
    out = _dump(p)
    assert X.SECRET not in out and X.MASK_TOKEN in out                          # 試算表分頁錯誤原文裡的秘密已被遮蔽
    # 略過列的原因、分頁名、基金代號都過遮蔽
    leaky = X.loaded_tables([X.holding_row("A")], skipped_holdings=[
        {"tab": X.SECRET, "row": 7, "policy_id": "P", "fund_code": X.SECRET, "reasons": [f"bad {X.SECRET}"]}],
        skipped_tabs=[{"tab": X.SECRET, "error": f"err {X.SECRET}"}])
    p, _r, _c = run(M, holdings=leaky)
    assert X.SECRET not in _dump(p)


def check_empty_holdings_proven_vs_unproven(M):
    proven, _r, _c = run(M, holdings=X.loaded_tables([]))
    unproven, _r2, _c2 = run(M, holdings={"holding": [], "policy": []})             # 沒有 skipped 兩項＝不知道
    a, b = proven["evidence"], unproven["evidence"]
    assert a["source_coverage"]["status"] == "complete" and b["source_coverage"]["status"] == "unknown"
    assert {"skipped_tabs_not_provided", "omitted_rows_not_provided"} <= set(b["source_coverage"]["reason_codes"])
    for ev in (a, b):                                                              # 兩者都不是 comparable，也沒有任何金額
        assert ev["valuation_completeness"]["status"] == "not_evaluated" and "no_holdings" in ev["valuation_completeness"]["reason_codes"]
        assert ev["chart_comparability"]["status"] != "comparable" and ev["denominator"]["value_twd"] is None
        assert ev["coverage"]["uncovered_value"]["status"] != "none_uncovered"
    assert b["chart_comparability"]["status"] == "not_comparable"


def check_identity_conflict_is_recorded(M):
    rows = [X.holding_row("A", "core", holding_id="P|A|1"), X.holding_row("A", "sat", holding_id="P|A|2")]
    p, _r, _c = run(M, holdings=X.loaded_tables(rows))
    e = p["evidence"]
    assert e["identity_conflict"] is not None and e["identity_conflict"]["key"] == ["PX-1", "A"]
    assert e["valuation_completeness"]["status"] == "failed" and e["chart_comparability"]["status"] == "not_comparable"
    assert e["denominator"]["value_twd"] is None and e["categories"] == []


def check_unclassified_never_comparable(M):
    p, _r, _c = run(M, holdings=X.loaded_tables([X.holding_row("A", None), X.holding_row("B", "core")]))
    e = p["evidence"]
    unclassified = [c for c in e["categories"] if c["is_unclassified"]]
    assert len(unclassified) == 1 and unclassified[0]["value_twd"] == 100000.0
    assert "unclassified_comparability_unjudged" in e["open_gates"]
    assert e["chart_comparability"]["status"] == "undetermined"                   # 不宣稱 comparable，也不宣稱 not_comparable


def check_target_and_tolerance_unset(M):
    t = X.two_fund_tables()
    p, _r, _c = run(M, holdings=t, settings=X.settings_payload(X.settings_rows(targets=None)))
    e = p["evidence"]
    assert e["settings"]["targets"]["status"] == "unset" and e["chart_comparability"]["status"] == "not_evaluated"
    assert "targets_unset" in e["chart_comparability"]["failing_conditions"]
    p, _r, _c = run(M, holdings=t, settings=X.settings_payload(X.settings_rows(tolerance=None)))
    assert p["evidence"]["settings"]["tolerance"]["status"] == "unset"
    assert "tolerance_unset_effect_unjudged" in p["evidence"]["open_gates"]        # 記錄，不補預設容許帶


def check_market_basis_is_blocked_without_calling_the_producer(M):
    for rows in (X.settings_rows(basis="市值"), X.settings_rows(basis="市值", targets="{broken")):
        spy = Spy()
        p, result, calls = run(M, holdings=X.two_fund_tables(), settings=X.settings_payload(rows), spy=spy)
        assert spy.calls == []                                                      # 生產者沒有被呼叫（沒有捏造／殘缺的淨值）
        assert calls.holdings == []                                                 # 連持倉都不讀
        assert p["status"] == "blocked" and p["blocked_reason"] == "market_basis_assembly_not_available_in_preview"
        assert p["evidence"] is None and result.evidence is None and p["problems"] == []
        assert dict(p["settings_status"])["alo_basis"] == "set"
        assert calls.fx_rule == 0                                                   # 也沒有去讀匯率規則狀態
    # 對照：成本基準會呼叫生產者，且只呼叫一次
    spy = Spy()
    run(M, holdings=X.two_fund_tables(), spy=spy)
    assert len(spy.calls) == 1


def check_producer_arguments_are_exactly_the_cost_path(M):
    spy = Spy()
    tables = X.two_fund_tables()
    run(M, holdings=tables, spy=spy)
    passed, kw = spy.calls[0]
    assert set(passed) == {"holding"}                                               # 不建 nav／market_indicator
    assert kw["nav_not_ready"] is None and kw["nav_provenance"] is None and kw["category_of"] is None
    # 淨值輸入宣告：adapter 不得宣稱「已組裝」（生產者無法驗證這個宣稱；它目前什麼都不傳，市值基準維持 blocked）
    assert kw.get("nav_input_state") in (None, "not_assembled")
    assert set(kw["source_state"]) == {"active_source", "errors", "skipped_tabs", "skipped_holdings"}
    assert kw["source_state"]["errors"] == {}
    mode = kw["basis_mode_of"]("成本")
    assert (mode.market, mode.track_stale) == (False, False)
    assert kw["settings"] == {"basis": "成本", "tolerance": 5.0, "bucket_names": ["core", "sat"],
                              "targets": [{"bucket": "core", "weight_ratio": 0.75}, {"bucket": "sat", "weight_ratio": 0.25}]}
    # 各種失敗時 errors 只會有 holding／user_setting，從不放 policy（會多出 non_holding_read_error）
    for kwargs in ({"holding_exc": X.FakeActiveSourceError("PERMISSION_DENIED")}, {"settings_exc": X.FakeSettingsError("x"), "holdings": tables},
                   {"holding_exc": X.FakeActiveSourceError("AUTH_REQUIRED"), "settings_exc": X.FakeSettingsError("x")}):
        spy = Spy()
        p, _r, _c = run(M, spy=spy, **kwargs)
        assert set(spy.calls[0][1]["source_state"]["errors"]) <= {"holding", "user_setting"}
        assert "non_holding_read_error" not in p["evidence"]["source_coverage"]["reason_codes"]
        assert "non_holding_read_error_effect_unjudged" not in p["evidence"]["open_gates"]


def check_no_active_source_state_claims_nothing_about_skips(M):
    spy = Spy()
    run(M, holding_exc=X.FakeActiveSourceError("AUTH_REQUIRED"), spy=spy)
    state = spy.calls[0][1]["source_state"]
    assert state["active_source"] == "none" and "skipped_tabs" not in state and "skipped_holdings" not in state
    spy = Spy()
    run(M, holding_exc=X.FakeActiveSourceError("PERMISSION_DENIED"), spy=spy)
    state = spy.calls[0][1]["source_state"]
    assert state["active_source"] == "selected" and "skipped_tabs" not in state and "skipped_holdings" not in state


def check_fx_rule_is_read_live_every_load(M):
    flag = {"v": False}
    reads, calls = X.make_reads(M, holdings=X.two_fund_tables(), fx_flag=lambda: flag["v"])
    seen = []
    for value in (False, True, None, False, True):
        flag["v"] = value
        spy = Spy()
        result = M.load({}, [X.SECRET], reads=reads, producer=spy)
        seen.append(spy.calls[0][1]["fx_rule_verified"])
        assert result.to_primitive()["evidence"]["fx_rule_verified"] == ("not_provided" if value is None else value)
    assert seen == [False, True, None, False, True] and calls.fx_rule == 5
    # 非布林（例如整數、字串）＝不明：當 None（未提供），不原樣交給生產者（它會對非布林拋 TypeError）
    for odd in (1, 0, "yes", object()):
        flag["v"] = odd
        spy = Spy()
        result = M.load({}, [X.SECRET], reads=reads, producer=spy)
        assert spy.calls[0][1]["fx_rule_verified"] is None
        assert result.evidence is not None
    # 成本基準不需要任何非 TWD 匯率：不論匯率規則狀態，都沒有 fx 閘門與 fx 列
    for value in (True, False, None):
        flag["v"] = value
        p = M.load({}, [X.SECRET], reads=reads).to_primitive()
        assert not [g for g in p["evidence"]["open_gates"] if g.startswith("fx_")]
        assert all(h["fx"]["status"] == "not_required" for h in p["evidence"]["holdings"])


def check_basis_mode_mapping(M):
    cost, market = M.basis_mode_of(M.BASIS_COST_VALUE), M.basis_mode_of(M.BASIS_MARKET_VALUE)
    assert (cost.market, cost.track_stale) == (False, False) and (market.market, market.track_stale) == (True, True)
    for bad in ("cost", "mv", "", None, 0, "成本 "):
        with pytest.raises(ValueError):
            M.basis_mode_of(bad)
    # 未知基準一旦到了生產者，由它記成 basis_mode_error（不預設成本、不預設市值）
    stage = M.SettingsStage({"basis": "未知", "targets": None, "tolerance": None, "bucket_names": None}, None, (), False, False)
    result = M.evaluate(stage, M.HoldingOutcome("loaded", tables=X.two_fund_tables()), mask=X.mask,
                        fx_key_of=lambda c: "fx_" + c, fx_rule_verified=False)
    e = result.to_primitive()["evidence"]
    assert "basis_mode_error" in e["valuation_completeness"]["reason_codes"] and e["holdings"][0]["value_twd"] is None


def check_only_the_happy_case_is_comparable(M):
    """生產者回什麼就是什麼（本檔不重算）：但 adapter 不得把任何降級情境變成 comparable。"""
    t = X.two_fund_tables()
    scenarios = {
        "no_active": dict(holding_exc=X.FakeActiveSourceError("AUTH_REQUIRED")),
        "denied": dict(holding_exc=X.FakeActiveSourceError("PERMISSION_DENIED")),
        "settings_failed": dict(holdings=t, settings_exc=X.FakeSettingsError("x")),
        "basis_unset": dict(holdings=t, settings=X.settings_payload(X.settings_rows(basis=None))),
        "targets_unset": dict(holdings=t, settings=X.settings_payload(X.settings_rows(targets=None))),
        "invalid": dict(holdings=t, settings=X.settings_payload(X.settings_rows(tolerance="x"))),
        "skips": dict(holdings=X.tables_with_skips()),
        "empty_unproven": dict(holdings={"holding": []}),
        "unclassified": dict(holdings=X.loaded_tables([X.holding_row("A", None)])),
        "no_skip_keys": dict(holdings={"holding": t["holding"]}),
    }
    for name, kw in scenarios.items():
        p, _r, _c = run(M, **kw)
        assert p["evidence"]["chart_comparability"]["status"] != "comparable", name
    p, _r, _c = run(M, holdings=t)                                                 # 唯一的 comparable：生產者自己對完整輸入的結論
    assert p["evidence"]["chart_comparability"]["status"] == "comparable"


def check_broken_keys_of_any_type_never_fail_open(M):
    """`broken_keys` 原樣交給解析：字串／整數／dict 這類型別錯誤 → 四鍵 invalid（絕不被拆成字元而無聲丟掉壞列標記）。"""
    t = X.two_fund_tables()
    for bad in ("alo_basis", "alo_tolerance_pp", 5, {"alo_basis": 1}, 1.5, True):
        p, _r, _c = run(M, holdings=t, settings=X.settings_payload(broken=bad))
        e = p["evidence"]
        assert {s for _k, s in p["settings_status"].items()} == {"invalid"}, bad
        assert p["problems"] == ["settings_value_unusable"] and e["valuation_completeness"]["status"] == "failed", bad
        assert e["chart_comparability"]["status"] == "not_comparable", bad
    for container in (list, tuple, set, frozenset):                       # 合法容器：壞鍵 → broken_row
        p, _r, _c = run(M, holdings=t, settings=X.settings_payload(broken=container(["alo_tolerance_pp"])))
        assert p["settings_status"]["alo_tolerance_pp"] == "broken_row" and p["settings_status"]["alo_basis"] == "set", container
        assert p["evidence"]["valuation_completeness"]["status"] == "failed"
    for empty in (None, [], (), set()):                                   # 沒有壞鍵
        p, _r, _c = run(M, holdings=t, settings=X.settings_payload(broken=empty))
        assert p["problems"] == [] and p["evidence"]["valuation_completeness"]["status"] == "complete", empty
    p, _r, _c = run(M, holdings=t, settings=X.settings_payload(broken=["alo_scenario_input"]))   # 非證據鍵：不影響
    assert p["problems"] == [] and p["evidence"]["valuation_completeness"]["status"] == "complete"


def check_unreadable_holding_table_is_recorded_not_raised(M):
    """`holding` 表的型別不對 → 原值交給生產者，記成 holding_table_unreadable（fail-closed 證據）；契約外（缺鍵、tables 不是 mapping）仍大聲失敗。"""
    for bad in (None, 5, object(), 1.5):
        p, _r, _c = run(M, holdings={"holding": bad, "skipped_tabs": [], "skipped_holdings": []})
        e = p["evidence"]
        assert "holding_table_unreadable" in e["source_coverage"]["reason_codes"] and e["source_coverage"]["status"] == "unknown", bad
        assert e["valuation_completeness"]["status"] == "failed" and "holding_table_unreadable" in e["valuation_completeness"]["reason_codes"]
        assert e["chart_comparability"]["status"] == "not_comparable" and e["denominator"]["value_twd"] is None and e["holdings"] == []
        assert any(x["stage"] == "holding_table" for x in e["evaluation_errors"])
    p, _r, _c = run(M, holdings={"holding": "abc", "skipped_tabs": [], "skipped_holdings": []})   # 字串：不能被當成空表而「完整」
    assert p["evidence"]["chart_comparability"]["status"] != "comparable" and p["evidence"]["valuation_completeness"]["status"] == "failed"
    with pytest.raises(KeyError):
        run(M, holdings={"skipped_tabs": [], "skipped_holdings": []})
    with pytest.raises(AttributeError):
        run(M, holdings=[])


def check_failure_code_is_masked_even_if_the_whitelist_is_poisoned(M):
    reads, _calls = X.make_reads(M, holding_exc=X.FakeActiveSourceError(X.SECRET), known_codes={X.SECRET})
    result = M.load({}, [X.SECRET], reads=reads)
    p = result.to_primitive()
    assert X.SECRET not in _dump(p)
    assert p["holding_failure_code"] == X.MASK_TOKEN and result.holding_failure_code == X.MASK_TOKEN
    assert dict(map(tuple, p["evidence"]["source"]["read_errors"]["items"]))["holding"] == f"holding source read failed ({X.MASK_TOKEN})"
    # 結果沒有帶 code 的失敗（純函式直接餵）：句子寫 unknown，不寫 None
    stage = M.settings_stage(M.SettingsOutcome("loaded", X.settings_rows(), ()))
    out = M.evaluate(stage, M.HoldingOutcome("failed"), mask=X.mask, fx_key_of=lambda c: c, fx_rule_verified=False).to_primitive()
    assert dict(map(tuple, out["evidence"]["source"]["read_errors"]["items"]))["holding"] == "holding source read failed (unknown)"
    assert out["holding_failure_code"] == "unknown"


def check_chart_claim_is_always_withheld(M):
    """每個降級矩陣情境（含 blocked、含生產者回 comparable 的完整成本基準）：claim 恆為 withheld；證據不被覆寫、也不被重算。"""
    t = X.two_fund_tables()
    scenarios = {
        "happy": dict(holdings=t), "no_active": dict(holding_exc=X.FakeActiveSourceError("AUTH_REQUIRED")),
        "no_active2": dict(holding_exc=X.FakeActiveSourceError("UNAVAILABLE", "no_active")),
        "denied": dict(holding_exc=X.FakeActiveSourceError("PERMISSION_DENIED")),
        "unknown_code": dict(holding_exc=X.FakeActiveSourceError(X.SECRET)),
        "settings_failed": dict(holdings=t, settings_exc=X.FakeSettingsError("x")),
        "basis_unset": dict(holdings=t, settings=X.settings_payload(X.settings_rows(basis=None))),
        "all_unset": dict(holdings=t, settings=X.settings_payload({})),
        "targets_unset": dict(holdings=t, settings=X.settings_payload(X.settings_rows(targets=None))),
        "tolerance_unset": dict(holdings=t, settings=X.settings_payload(X.settings_rows(tolerance=None))),
        "invalid": dict(holdings=t, settings=X.settings_payload(X.settings_rows(tolerance="x"))),
        "broken": dict(holdings=t, settings=X.settings_payload(
            {k: v for k, v in X.settings_rows().items() if k != "alo_tolerance_pp"}, broken=["alo_tolerance_pp"])),
        "market_blocked": dict(holdings=t, settings=X.settings_payload(X.settings_rows(basis="市值"))),
        "skips": dict(holdings=X.tables_with_skips()),
        "empty_proven": dict(holdings=X.loaded_tables([])), "empty_unproven": dict(holdings={"holding": []}),
        "conflict": dict(holdings=X.loaded_tables([X.holding_row("A", "core", holding_id="P|A|1"),
                                                   X.holding_row("A", "sat", holding_id="P|A|2")])),
        "unclassified": dict(holdings=X.loaded_tables([X.holding_row("A", None)])),
    }
    for name, kw in scenarios.items():
        p, result, _c = run(M, **kw)
        assert p["chart_claim"] == "withheld_pending_approval" and result.chart_claim == "withheld_pending_approval", name
    # 生產者說 comparable 的那一案：證據原樣是 comparable，主張仍是 withheld（沒有覆寫、也沒有從證據推導）
    p, result, _c = run(M, holdings=t)
    assert p["evidence"]["chart_comparability"]["status"] == "comparable"
    assert result.evidence.chart_comparability.status == "comparable"
    assert p["chart_claim"] == "withheld_pending_approval"
    # blocked 結果同樣帶欄位；欄位只允許那一個值
    blocked = run(M, holdings=t, settings=X.settings_payload(X.settings_rows(basis="市值")))[0]
    assert blocked["status"] == "blocked" and blocked["chart_claim"] == "withheld_pending_approval"
    for bad in ("asserted", "comparable", "", None):
        with pytest.raises(ValueError):
            M.AssetsLoadResult(M.STATUS_EVALUATED, None, None, (), (), chart_claim=bad)


def check_strict_json_and_missing_stays_none(M):
    t = X.two_fund_tables()
    for kw in (dict(holdings=t), dict(holdings=X.tables_with_skips()), dict(holding_exc=X.FakeActiveSourceError("AUTH_REQUIRED")),
               dict(holdings=X.loaded_tables([X.holding_row("A", "core", cost=100000)]),
                    settings=X.settings_payload(X.settings_rows(targets='[{"bucket":"core","weight_ratio":0.5},{"bucket":"sat","weight_ratio":0.5}]')))):
        p, result, _c = run(M, **kw)
        text = json.dumps(p, allow_nan=False)                                       # 不含 NaN／Infinity
        assert json.loads(text) == p
        assert result.status == p["status"] and result.schema_version == p["schema_version"] == 1
    # 目標有、持倉沒有的類別：來源有略過證據時是「未證實的零」＝ None，不是 0.0
    p, _r, _c = run(M, holdings=X.tables_with_skips())
    sat = _by(p["evidence"]["categories"], "category")["sat"]
    assert sat["value_twd"] is None and sat["origin"] == "target_without_holdings" and sat["share"]["share_of_covered_pct"] is None


def check_inputs_are_not_mutated(M):
    for build in (X.two_fund_tables, X.tables_with_skips):
        tables = build()
        payload = X.settings_payload()
        before_t, before_s = copy.deepcopy(tables), copy.deepcopy(payload)
        run(M, holdings=tables, settings=payload)
        assert tables == before_t and payload == before_s
    result_a = run(M, holdings=X.two_fund_tables())[0]
    result_b = run(M, holdings=X.two_fund_tables())[0]
    assert result_a == result_b                                                    # 同輸入、同輸出（冪等）
    # 結果是凍結物件
    result = run(M, holdings=X.two_fund_tables())[1]
    with pytest.raises(Exception):
        result.status = "blocked"


def check_exceptions_not_in_the_contract_propagate(M):
    """L2 契約內的失敗才轉成證據；其他例外（含防禦性的 `HoldingIdCollision` 類）照樣往上拋，不被吞。"""
    with pytest.raises(KeyError):
        run(M, holding_exc=KeyError("collision"))
    with pytest.raises(ZeroDivisionError):
        run(M, settings_exc=ZeroDivisionError())


CHECKS = [
    check_happy_numbers_and_provenance, check_no_active_source_both_forms, check_other_active_source_error_is_a_read_failure,
    check_settings_read_failure, check_unset_basis_is_not_defaulted_to_cost, check_invalid_or_broken_setting_is_not_unset,
    check_skipped_evidence_downgrades_and_is_masked, check_empty_holdings_proven_vs_unproven, check_identity_conflict_is_recorded,
    check_unclassified_never_comparable, check_target_and_tolerance_unset, check_market_basis_is_blocked_without_calling_the_producer,
    check_producer_arguments_are_exactly_the_cost_path, check_no_active_source_state_claims_nothing_about_skips,
    check_fx_rule_is_read_live_every_load, check_basis_mode_mapping, check_only_the_happy_case_is_comparable,
    check_broken_keys_of_any_type_never_fail_open, check_unreadable_holding_table_is_recorded_not_raised,
    check_failure_code_is_masked_even_if_the_whitelist_is_poisoned,
    check_chart_claim_is_always_withheld, check_strict_json_and_missing_stays_none, check_inputs_are_not_mutated, check_exceptions_not_in_the_contract_propagate,
]


@pytest.mark.parametrize("check", CHECKS, ids=lambda f: f.__name__)
def test_real_module_passes(check):
    check(REAL)


def test_checks_registry_is_not_trivial_and_names_are_unique():
    assert len({f.__name__ for f in CHECKS}) == len(CHECKS) >= 20


# ═══════════════════════ 真 L2 的形狀與接線（不連網） ═══════════════════════


def test_real_l2_rows_have_contract_shape_and_dates_are_strings():
    from services.v2_tables import contract
    tables = X.two_fund_tables()
    assert tables["holding"]
    for h in tables["holding"]:
        assert contract.holding_row_problems(h) == []
        assert all(isinstance(h[k], str) for k in ("opened_on", "last_synced_at", "holding_id", "policy_id", "fund_code"))
        assert isinstance(h["cost_twd"], int) and isinstance(h["units_shares"], float)
    # 證據裡不會出現 date／datetime 物件（to_primitive 後都是字串／數字）
    p = REAL.load({}, [], reads=X.make_reads(REAL, holdings=tables)[0]).to_primitive()
    assert json.loads(json.dumps(p, allow_nan=False)) == p


def test_real_l1_settings_shape_through_the_adapter(monkeypatch):
    """設定列用 L1 `load_user_settings` 的真輸出（假 gspread 試算表；含最新一列壞掉的鍵）。"""
    from _fake_settings_sheet import FakeClient, FakeSpreadsheet, FakeWorksheet
    from infra import gspread_retry as GR
    from infra import source_backoff as SB
    from repositories import settings_sheet_repository as L1
    book = FakeSpreadsheet()
    monkeypatch.setattr(L1, "get_secret", lambda key, default=None: {"SETTINGS_SHEET_ID": "sheet-x", "google_service_account":
                                                                    {"client_email": "sa@example.iam.gserviceaccount.com"}}.get(key, default))
    monkeypatch.setattr(L1, "_make_client", lambda creds: FakeClient(book))
    monkeypatch.setattr(GR.time, "sleep", lambda _s: None)
    L1.clear_cache()
    SB.reset_all()
    head = ["setting_key", "setting_value", "value_kind", "updated_at"]
    book.tabs["user_setting_log"] = FakeWorksheet(book, "user_setting_log", [
        head,
        ["alo_basis", "成本", "list", "2026-11-01T00:00:00Z"],
        ["alo_target_weights", '[{"bucket":"core","weight_ratio":0.75},{"bucket":"sat","weight_ratio":0.25}]', "list", "2026-11-01T00:00:00Z"],
        ["alo_tolerance_pp", "5", "float", "2026-11-01T00:00:00Z"],
        ["alo_bucket_names", '["core","sat"]', "list", "2026-11-01T00:00:00Z"],
        ["alo_tolerance_pp", "6", "floaty", "2026-11-01T00:00:01Z"],          # 最新一列壞掉 → broken_keys，不退回較舊的 5
    ])
    try:
        payload = L1.load_user_settings(mask=X.mask)
    finally:
        L1.clear_cache()
        SB.reset_all()
    assert payload["broken_keys"] == ["alo_tolerance_pp"] and set(payload["rows"]) >= {"alo_basis", "alo_target_weights"}
    reads, _calls = X.make_reads(REAL, holdings=X.two_fund_tables(), settings=payload)
    p = REAL.load({}, [], reads=reads).to_primitive()
    assert dict(p["settings_status"])["alo_tolerance_pp"] == "broken_row" and dict(p["settings_status"])["alo_basis"] == "set"
    assert p["evidence"]["valuation_completeness"]["status"] == "failed"


def test_l2_reads_default_wiring_points_at_the_real_read_paths():
    from services.v2_tables import alo_holdings, market_indicator, personal_session, settings_store
    reads = REAL.l2_reads()
    assert reads.read_holdings is alo_holdings.load_alo_tables_active
    assert reads.read_settings is settings_store.load_user_settings
    assert reads.holding_errors == (alo_holdings.ActiveSourceError,)
    assert reads.settings_errors == (settings_store.SettingsSheetError,)
    assert reads.make_mask is alo_holdings.masker
    assert reads.fx_key_of is market_indicator.fx_indicator_key
    assert reads.known_codes == frozenset(personal_session.ec.ALL_ERROR_CODES) and len(reads.known_codes) == 9


def test_fx_rule_reader_follows_the_live_l2_attribute(monkeypatch):
    from services.v2_tables import market_indicator
    reads = REAL.l2_reads()
    for value in (True, False):
        monkeypatch.setattr(market_indicator, "FX_OBS_DATE_RULE_VERIFIED", value)
        assert reads.read_fx_rule_verified() is value
    import dataclasses
    fake, _calls = X.make_reads(REAL, holdings=X.two_fund_tables())
    mixed = dataclasses.replace(reads, read_holdings=fake.read_holdings, read_settings=fake.read_settings)
    for value in (True, False):
        monkeypatch.setattr(market_indicator, "FX_OBS_DATE_RULE_VERIFIED", value)
        assert REAL.load({}, [], reads=mixed).to_primitive()["evidence"]["fx_rule_verified"] is value


def test_no_active_judgement_matches_ui_v2_active_gate_exactly():
    pytest.importorskip("streamlit")          # ui_v2.active_gate 會 import streamlit
    from ui_v2 import active_gate
    reads = REAL.l2_reads()
    codes = sorted(reads.known_codes) + ["", "unknown", None]
    for code in codes:
        for reason in (None, "no_active", "deploy_config", "policy_header", "supplement_header", "other"):
            exc = X.FakeActiveSourceError(code, reason)
            assert reads.is_no_active(exc) is active_gate.is_no_active(code, reason), (code, reason)


def test_support_known_codes_literal_has_not_drifted_from_l2():
    from services.v2_tables import personal_session
    assert X.KNOWN_CODES == frozenset(personal_session.ec.ALL_ERROR_CODES)
    assert REAL.l2_reads().known_codes == X.KNOWN_CODES


def test_basis_words_match_l2_and_ui_v2():
    from services.v2_tables import settings_store
    assert settings_store.ENUM_SETTING_VALUES["alo_basis"] == (REAL.BASIS_COST_VALUE, REAL.BASIS_MARKET_VALUE)
    from ui_v2.alo import logic
    assert (logic.BASIS_COST, logic.BASIS_MV) == (REAL.BASIS_COST_VALUE, REAL.BASIS_MARKET_VALUE)


def test_real_l2_without_credentials_ends_in_no_active_and_blocks_all_network(monkeypatch):
    """真的預設 L2（不注入）：Preview 沒有登入／Active，沒有憑證時必須落在「沒有 Active＋設定讀不到」，且全程不開 socket。
    ⚠️ 這只證明「無憑證路徑 fail-closed」，**不證明有憑證時真實連線可用**。"""
    def no_network(*_a, **_k):
        raise AssertionError("assets_source.load tried to open a network connection")
    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    from repositories import settings_sheet_repository as L1
    monkeypatch.setattr(L1, "get_secret", lambda key, default=None: default)
    L1.clear_cache()
    result = REAL.load({}, [])
    p = result.to_primitive()
    e = p["evidence"]
    assert p["status"] == "evaluated" and "no_active_source" in p["problems"] and "settings_read_failed" in p["problems"]
    assert e["source_coverage"]["status"] == "not_selected" and e["chart_comparability"]["status"] != "comparable"
    assert e["holdings"] == [] and e["denominator"]["value_twd"] is None
    json.dumps(p, allow_nan=False)


def test_secret_values_given_as_a_plain_string_fail_loud_before_any_read():
    """真的 L2 遮蔽器拒收字串（`list("abc")` 會把金鑰拆成單字元）；adapter 先建遮蔽器，所以一次讀取都不會發生。"""
    import dataclasses
    from services.v2_tables import alo_holdings
    reads, calls = X.make_reads(REAL, holdings=X.two_fund_tables())
    reads = dataclasses.replace(reads, make_mask=alo_holdings.masker)
    with pytest.raises(TypeError):
        REAL.load({}, "not-a-list", reads=reads)
    assert calls.settings == [] and calls.holdings == []
