# -*- coding: utf-8 -*-
"""`ui_v3/adapters/assets_source.py` 的突變測試——證明 `test_ui_v3_assets_source_contract.py`、差分測試與靜態守衛真的咬得住。

做法（同 `tests/test_allocation_evidence_mutations.py`）：讀**目前**的原始碼，套**一個**記憶體內字串替換（舊字串必須恰好出現一次，
否則本檔轉紅：目標消失或變得有歧義），把突變體 exec 進獨立命名空間（不寫檔、不進 `sys.modules`），然後
- 行為突變：跑整張 `CHECKS`＋設定解析的差分＋已知良值檢查，至少一條必須失敗；
- 靜態突變：對突變後的原始碼跑本批的靜態規則與既有守衛函式庫，至少一條必須回報違規。
對照組：未突變的原始碼經同一個載入器必須通過每一條檢查，所以「突變體紅燈」來自突變本身，不是載入方式。
活下來的突變只能列在 `SURVIVORS_DOCUMENTED`（附理由）；不為了殺一個突變而灌水斷言。
"""
from __future__ import annotations

import pathlib
import sys
import types

import pytest

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

pytest.importorskip("streamlit")     # 差分檢查要 import ui_v2；沒有 streamlit 的直譯器跳過，CI 會跑

import test_ui_v3_assets_source_contract as T            # noqa: E402
import test_ui_v3_assets_source_import_isolation as ISO  # noqa: E402
import test_ui_v3_assets_source_settings_differential as DIFF  # noqa: E402
import ui_v3_guard_lib as lib                             # noqa: E402

_SRC = lib.ROOT / "ui_v3" / "adapters" / "assets_source.py"
REL = "ui_v3/adapters/assets_source.py"

# (id, old (恰好一次), new, 它破壞什麼)
BEHAVIOUR = [
    ("A01_no_active_marked_selected", '{"active_source": "none", "errors": errors}', '{"active_source": "selected", "errors": errors}',
     "沒有 Active 被當成已選定的來源"),
    ("A02_no_active_never_recognised", "        if reads.is_no_active(exc):\n            return HoldingOutcome(KIND_NO_ACTIVE)",
     "        if False:\n            return HoldingOutcome(KIND_NO_ACTIVE)", "沒有 Active 被當成一般讀取失敗"),
    ("A03_holding_error_passed_as_policy", 'errors["holding"] = f"holding', 'errors["policy"] = f"holding',
     "持倉讀取失敗被記成 policy 表錯誤（多出 non_holding_read_error，且 holding 失敗消失）"),
    ("A04_market_basis_not_blocked_in_evaluate",
     "    if stage.market_basis:\n        return AssetsLoadResult(STATUS_BLOCKED",
     "    if False:\n        return AssetsLoadResult(STATUS_BLOCKED", "市值基準照樣往生產者走"),
    ("A05_market_basis_not_blocked_in_load", "    if stage.market_basis:\n        return evaluate(stage, None,",
     "    if False:\n        return evaluate(stage, None,", "市值基準仍讀持倉並往下走"),
    ("A06_unset_basis_defaulted_to_cost", "        values[name] = value\n",
     '        values[name] = value if not (name == "basis" and value is None) else BASIS_COST_VALUE\n', "未設的基準被預設成「成本」"),
    ("A07_skipped_reasons_unmasked", '"reasons": [mask(str(r)) for r in reasons] if', '"reasons": [str(r) for r in reasons] if',
     "略過列原因的秘密沒被遮蔽"),
    ("A08_skipped_tab_error_unmasked", '            entry["error"] = mask(error)', '            entry["error"] = error',
     "略過分頁錯誤原文的秘密沒被遮蔽"),
    ("A09_text_fields_unmasked", "    return mask(value) if isinstance(value, str) else value", "    return value",
     "分頁名／基金代號的秘密沒被遮蔽"),
    ("A10_fx_rule_hard_coded", "fx_rule_verified=reads.read_fx_rule_verified(),", "fx_rule_verified=True,",
     "匯率規則狀態寫死成已驗證，不讀 L2 現值"),
    ("A11_settings_failure_read_as_empty", "        return SettingsOutcome(KIND_FAILED)   # 原文一律丟棄（可能含秘密）",
     "        return SettingsOutcome(KIND_LOADED, {}, ())", "設定讀取失敗被當成「全部未設定」"),
    ("A12_invalid_setting_read_as_unset", "                except _Bad:\n                    value, status = None, SETTING_INVALID",
     "                except _Bad:\n                    value, status = None, SETTING_UNSET", "解析失敗的設定被當成未設定"),
    ("A13_broken_keys_ignored", "        elif key in broken:", "        elif False:", "最新一列壞掉的鍵被忽略"),
    ("A14_skipped_tabs_dropped", '    if tables.get("skipped_tabs") is not None:', "    if False:", "被略過的分頁不進證據"),
    ("A15_skipped_holdings_dropped", '    if tables.get("skipped_holdings") is not None:', "    if False:", "沒寫進持倉的列不進證據"),
    ("A16_nav_not_ready_fabricated", "nav_not_ready=None,", 'nav_not_ready={"codes": [], "days": 10},', "憑空塞入淨值未備天數"),
    ("A17_unknown_error_code_leaked", "    return code if isinstance(code, str) and code in known else _UNKNOWN_CODE", "    return code",
     "白名單外的 error code（可能夾帶秘密）原樣外漏"),
    ("A18_input_table_mutated", '    return {"holding": tables["holding"]}, source_state',
     '    return {"holding": tables["holding"].reverse() or tables["holding"]}, source_state', "輸入持倉表被原地修改"),
    ("A19_market_detection_wrong_value", 'parsed.values["basis"] == BASIS_MARKET_VALUE', 'parsed.values["basis"] == BASIS_COST_VALUE',
     "市值基準的辨認條件寫反"),
    ("A20_unusable_settings_accepted", "        return all(status in (SETTING_SET, SETTING_UNSET) for _key, status in self.statuses)",
     "        return True", "不可用的設定仍被當成可用"),
    ("A21_non_bool_fx_flag_passed_through",
     "fx_rule_verified = None   # 非布林＝不明，當「未提供」（生產者會記 gate），不猜", "pass", "非布林的匯率規則狀態原樣交給生產者"),
    ("A22_market_basis_mode_wrong", "return _ev.BasisMode(market=True, track_stale=True)", "return _ev.BasisMode(market=False, track_stale=False)",
     "市值基準走成本路徑"),
    ("A23_unknown_basis_defaults_to_cost", '    raise ValueError("unsupported basis value")', "    return _ev.BasisMode(market=False, track_stale=False)",
     "未知基準被預設成成本"),
    ("A24_weight_bounds_removed", "if number is None or not 0.0 <= number <= 1.0:", "if number is None:", "目標比重不檢查 0～1"),
    ("A25_tolerance_non_finite_accepted", '    if not math.isfinite(number):\n        raise _Bad("tolerance finite")',
     '    if False:\n        raise _Bad("tolerance finite")', "容許帶接受 nan／inf"),
    ("A26_untrimmed_json_accepted", '    if not isinstance(text, str) or text != text.strip():\n        raise _Bad("not a trimmed string")',
     '    if not isinstance(text, str):\n        raise _Bad("not a trimmed string")', "前後有空白的 JSON 仍被接受"),
    ("A27_bool_counts_as_number", "    if isinstance(value, bool) or not isinstance(value, (int, float)):\n        return None\n    try:",
     "    if not isinstance(value, (int, float)):\n        return None\n    try:", "布林被當成數字"),
    ("A28_overflow_not_caught", "    except OverflowError:\n        return None", "    except ZeroDivisionError:\n        return None",
     "超大整數讓解析崩潰（ui_v2 同病；adapter 必須 fail-closed）"),
    ("A29_any_string_is_a_basis", "    if text not in (BASIS_COST_VALUE, BASIS_MARKET_VALUE):", "    if not isinstance(text, str):", "任何字串都是合法基準"),
    ("A30_target_extra_fields_accepted", 'if not isinstance(item, dict) or set(item) != {"bucket", "weight_ratio"}:', "if not isinstance(item, dict):",
     "目標元素多／少欄位仍被接受"),
    ("A31_blank_bucket_accepted", '        if not isinstance(bucket, str) or not bucket.strip():\n            raise _Bad("target bucket")',
     '        if not isinstance(bucket, str):\n            raise _Bad("target bucket")', "空白類別名被接受"),
    ("A33_blocked_without_reason", "AssetsLoadResult(STATUS_BLOCKED, BLOCKED_MARKET_BASIS, None, (), stage.statuses)",
     "AssetsLoadResult(STATUS_BLOCKED, None, None, (), stage.statuses)", "blocked 結果沒有原因代碼"),
    ("A34_read_failed_status_lost", "tuple((key, SETTING_READ_FAILED) for key, _name in _SETTING_KEYS), False, True)",
     "tuple((key, SETTING_UNSET) for key, _name in _SETTING_KEYS), False, True)", "設定讀取失敗在逐鍵狀態裡變成 unset"),
    ("A35_no_active_problem_dropped", "        problems.append(PROBLEM_NO_ACTIVE)", "        pass", "沒有 Active 不進問題清單"),
    ("A36_skipped_row_number_lost", '"row": item.get("row"),', '"row": None,', "略過列的列號遺失"),
    ("A39_claim_asserted_when_evidence_comparable", '            "chart_claim": self.chart_claim,',
     '            "chart_claim": "asserted" if (self.evidence is not None and self.evidence.chart_comparability.status == "comparable") '
     "else self.chart_claim,", "證據寫 comparable 時 claim 變成 asserted"),
    ("A40_claim_value_not_validated", "        if self.chart_claim != CHART_CLAIM_WITHHELD:", "        if False:", "claim 欄位接受任意值"),
    ("A41_claim_default_changed", 'chart_claim: str = CHART_CLAIM_WITHHELD\n', 'chart_claim: str = "asserted"\n', "claim 預設值不是 withheld"),
    ("A42_claim_omitted_from_primitive", '            "chart_claim": self.chart_claim,\n', "", "claim 沒進 to_primitive"),
    ("A43_broken_keys_split_by_tuple", 'return SettingsOutcome(KIND_LOADED, payload["rows"], payload["broken_keys"])',
     'return SettingsOutcome(KIND_LOADED, payload["rows"], tuple(payload["broken_keys"]))', "字串 broken_keys 被拆成字元而無聲失效"),
    ("A44_holding_table_listified_early", 'return {"holding": tables["holding"]}, source_state',
     'return {"holding": list(tables["holding"])}, source_state', "holding 表型別錯誤在 adapter 內就拋例外，生產者記不到"),
    ("A45_failure_code_unmasked_in_result_and_sentence", "    return mask(holding.failure_code or _UNKNOWN_CODE)",
     "    return holding.failure_code or _UNKNOWN_CODE", "被汙染的白名單讓秘密從 code 外漏"),
    ("A46_failure_code_unknown_fallback_removed", "    return mask(holding.failure_code or _UNKNOWN_CODE)",
     "    return mask(holding.failure_code)", "沒有 code 時句子帶出 None"),
    ("A37_blocked_but_evidence_present",
     "return AssetsLoadResult(STATUS_BLOCKED, BLOCKED_MARKET_BASIS, None, (), stage.statuses)",
     "return AssetsLoadResult(STATUS_BLOCKED, BLOCKED_MARKET_BASIS, _ev.build_allocation_evidence({'holding': []}, settings=None, "
     "nav_not_ready=None, fx_key_of=lambda c: c, basis_mode_of=basis_mode_of), (), stage.statuses)",
     "blocked 結果仍帶著用空資料算出的證據"),
]

STATIC = [
    ("S01_l2_import_hoisted_to_module_level", "from services.v2_domain import allocation_evidence as _ev\n",
     "from services.v2_domain import allocation_evidence as _ev\nfrom services.v2_tables import masking\n", "L2 import 上提到模組層"),
    ("S02_streamlit_imported", "import json\nimport math\n", "import json\nimport math\nimport streamlit\n", "adapter import streamlit"),
    ("S03_sys_modules_trick", "import json\nimport math\n", "import json\nimport math\nimport sys\n_MODULES = sys.modules\n", "用 sys.modules 繞過 import 守衛"),
    ("S04_write_function_imported", "import json\nimport math\n",
     "import json\nimport math\nfrom services.v2_tables.settings_store import save_setting_for_page\n", "import 已知寫入函式"),
    ("S05_import_time_side_effect", 'STATUS_EVALUATED = "evaluated"\n', 'STATUS_EVALUATED = "evaluated"\nprint("loaded")\n', "import 時有執行語句"),
    ("S06_nav_threshold_defined_here", '_UNKNOWN_CODE = "unknown"\n', '_UNKNOWN_CODE = "unknown"\nNAV_NOT_READY' + '_DAYS = 10\n', "在這裡定義淨值未備天數門檻"),
    ("S07_env_shaped_literal", '_UNKNOWN_CODE = "unknown"\n', '_UNKNOWN_CODE = "UNKNOWN' + '_CODE"\n', "環境變數形的字串常數（會外漏成工程詞）"),
    ("S09_personal_session_function_called", "    codes = personal_session.ec\n", "    codes = personal_session.ec\n    personal_session.logout({})\n",
     "呼叫 personal_session 的函式"),
    ("S10_personal_session_extra_attribute", "    codes = personal_session.ec\n", "    codes = personal_session.ec\n    _x = personal_session.status\n",
     "讀 personal_session 允許面以外的屬性"),
    ("S11_personal_session_imported_in_function", "    codes = personal_session.ec\n",
     "    codes = personal_session.ec\n    from services.v2_tables import personal_session as _ps\n", "新增 personal_session 的 import 句"),
    ("S12_error_code_handle_called", "    codes = personal_session.ec\n", "    codes = personal_session.ec\n    codes.AUTH_REQUIRED()\n", "呼叫 error code 把手"),
    ("S08_ui_v2_imported", "import json\nimport math\n", "import json\nimport math\nfrom ui_v2.alo import live\n", "adapter import ui_v2"),
]

#: 活下來的突變 → 理由（每一條都是等價突變，不是漏測）
SURVIVORS_DOCUMENTED = {
    "A32_nan_constant_accepted": "保留並揭露（不刪）：與 ui_v2 逐行同構，刪了反而讓鏡像失去對照；`parse_constant` 拒絕 NaN／Infinity 在本檔是縱深防禦：NaN 在 targets 會被 `_finite_number` 擋、"
                                 "在 bucket_names 不是字串、在頂層不是陣列，結果與 ui_v2 相同（差分 415 案證實）。",
}
EQUIVALENT = [
    ("A32_nan_constant_accepted", "json.loads(text, parse_constant=_reject_constant)", "json.loads(text)", "JSON 的 NaN／Infinity 被接受"),
]


def _source() -> str:
    return _SRC.read_text(encoding="utf-8")


def _mutate(old: str, new: str, mid: str) -> str:
    source = _source()
    count = source.count(old)
    assert count == 1, f"{mid}: old string occurs {count} times in assets_source.py (must be exactly 1)"
    return source.replace(old, new)


def _load(source: str):
    # `__name__` 取真模組名：`dataclasses` 解析字串註解時要在 `sys.modules` 裡找得到宿主模組（突變體本身不進 `sys.modules`）。
    ns = {"__name__": "ui_v3.adapters.assets_source", "__package__": "ui_v3.adapters"}
    exec(compile(source, "<mutant:assets_source>", "exec", dont_inherit=True), ns)   # noqa: S102 - 本 repo 自己的原始碼，一處編輯
    return types.SimpleNamespace(**{k: v for k, v in ns.items() if not k.startswith("__")})


def check_settings_differential(M):
    assert DIFF.single_key_mismatches(M) == []


def check_known_good_settings(M):
    parsed = M.parse_settings(T.X.settings_rows(), [])
    assert parsed.usable and parsed.values == {
        "basis": "成本", "tolerance": 5.0, "bucket_names": ["core", "sat"],
        "targets": [{"bucket": "core", "weight_ratio": 0.75}, {"bucket": "sat", "weight_ratio": 0.25}]}
    assert type(parsed.values["tolerance"]) is float and all(type(t["weight_ratio"]) is float for t in parsed.values["targets"])


def _failures(module) -> list:
    failed = []
    for fn in list(T.CHECKS) + [check_settings_differential, check_known_good_settings]:
        try:
            fn(module)
        except BaseException as exc:  # noqa: BLE001 - 任何失敗或崩潰都代表「突變被發現」；KeyboardInterrupt 不吞
            if isinstance(exc, KeyboardInterrupt):
                raise
            failed.append(fn.__name__)
    return failed


def _static_findings(source: str) -> list:
    return (ISO.static_isolation_problems(source) + ISO.personal_session_surface_problems(source) + lib.import_violations(REL, source)
            + lib.write_surface_violations(REL, source) + lib.module_level_side_effects(source))


def test_control_unmutated_source_passes_every_check_and_static_rule():
    assert _failures(_load(_source())) == []
    assert _static_findings(_source()) == []


@pytest.mark.parametrize("mutation", BEHAVIOUR, ids=lambda m: m[0])
def test_behaviour_mutation_is_killed(mutation):
    mid, old, new, doc = mutation
    killers = _failures(_load(_mutate(old, new, mid)))
    assert killers, f"{mid} ({doc}): no check noticed the mutation"


@pytest.mark.parametrize("mutation", STATIC, ids=lambda m: m[0])
def test_static_mutation_is_killed(mutation):
    mid, old, new, doc = mutation
    findings = _static_findings(_mutate(old, new, mid))
    assert findings, f"{mid} ({doc}): no static rule noticed the mutation"


@pytest.mark.parametrize("mutation", EQUIVALENT, ids=lambda m: m[0])
def test_documented_survivors_are_equivalent_and_still_target_existing_code(mutation):
    mid, old, new, _doc = mutation
    assert mid in SURVIVORS_DOCUMENTED and SURVIVORS_DOCUMENTED[mid].strip()
    assert _failures(_load(_mutate(old, new, mid))) == []          # 確實沒人發現（等價）；理由在 SURVIVORS_DOCUMENTED


def test_mutation_lists_are_not_trivial_and_ids_are_unique():
    ids = [m[0] for m in BEHAVIOUR + STATIC + EQUIVALENT]
    assert len(ids) == len(set(ids)) and len(BEHAVIOUR) >= 35 and len(STATIC) >= 8


def test_mutants_do_not_replace_or_pollute_sys_modules():
    real = sys.modules["ui_v3.adapters.assets_source"]
    before = set(sys.modules)
    mutant = _load(_mutate(*BEHAVIOUR[0][1:3], BEHAVIOUR[0][0]))
    assert sys.modules["ui_v3.adapters.assets_source"] is real and mutant.load is not real.load
    assert set(sys.modules) - before == set()
