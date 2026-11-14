# -*- coding: utf-8 -*-
"""💼 我的資產頁 adapter（S-VM 切片）：`AssetsLoadResult.to_primitive()` 形狀的純 dict → `AssetsPageModel`。

**純函式：無 I/O、無 streamlit、不 import `services.*`／`repositories.*`／`infra.*`／`shared.*`、不 import `ui_v3.fixtures`、也不 import
同層的載入端 adapter**（`AssetsLoadResult` 的產出者，BL-0542 G-2；它在載入時會連帶 import L2，本檔刻意不依賴它）。載入端的狀態／問題／設定代碼
在這裡**各寫一次**：與載入端／生產者同值（讀碼對照），但**未經本批測試鎖定，NOT VERIFIED**；真生產者形狀對照已延後，需另行授權。
本檔**沒有 production 呼叫端**、沒有頁、沒有 registry 登錄；輸入只限 fake／fixture 或測試端組出的同形 dict。

輸入形狀（`AssetsLoadResult.to_primitive()`）：
`{schema_version, status, blocked_reason, problems, settings_status, holding_failure_code, chart_claim, evidence}`；
`evidence` 為 `AllocationEvidence` 的 primitive（`blocked` 時為 None）。本檔**只讀** `evidence` 的 `source`、`holdings`、`source_coverage`、
`settings`（僅取基準的值）。**從不讀 `categories`、`denominator`、`coverage`**，所以 `categories[*].value_twd` 等金額欄位不可能被帶進 VM（測試以
「存取追蹤 dict」鎖住）。

fail-closed 的選擇（逐條有測試）：
- **封包契約違規 → `ValueError`**（程式錯誤，不得被吞成空白或「完整」）：輸入不是 Mapping、缺必要鍵、`schema_version` 不是 1、
  `status` 不是 evaluated／blocked、`chart_claim` 不是 withheld、`problems`／`settings_status` 含未知代碼、evaluated 卻沒有 evidence、
  blocked 卻帶 evidence、evidence 缺 `source`／`holdings`／`source_coverage`、持倉列不是 Mapping。
- **證據內部的未知值 → 降級為 `undetermined`（⬜ 無法判定）**，絕不當成完整：`source_coverage.status` 是未知字串、coverage 說 incomplete 卻沒有略過證據…。
  生產者的詞彙明文是「內部候選」，它的值域本來就可能變。
- 缺值一律 `None`＋原因，不轉 0、不補空字串；來源沒提供的件數是 `None`，不是 0。

⚠️ 入口（A10 的「持倉入口」）對映**不是 production 規則**：82 §11.9.9 自標 NOT VERIFIED，`DEC-2026-11-09-04` UI-2 明定為「暫行候選，不得升格 production
規則」。本檔只把它實作成一個明確命名的暫行候選函式 `provisional_holding_entry_available`，**只在 fixture 測試中驗證**；它依「讀取成功」與
「至少一列可用持倉」兩項，其中「可用持倉列」＝證據 `holdings` 至少一列，這個對映本身未經客戶或獨立 QA 確認。

已知限制（不在本批決定，登記給客戶）：市值基準時載入端一律 `blocked`、不讀持倉 → 本 VM 無 A50 列，使用者看不到原幣持倉
（與 82 §11.3「FX 無法驗證，原幣資料仍可查看」有張力，82 缺口 G-F）。**本檔不處置、不為此開 FX 閘。**
所有代碼皆內部候選，非核准詞彙。
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Optional, Sequence, Tuple

from ui_v3.viewmodels import assets_page as vm

__all__ = (
    "RESULT_SCHEMA_VERSION", "STATUS_EVALUATED", "STATUS_BLOCKED", "PROVISIONAL_ROW_FIELDS", "PROVISIONAL_ROW_FIELDS_NOTE", "FORBIDDEN_ROW_FIELDS",
    "build_assets_page", "provisional_holding_entry_available",
)

# ───────────────────────── 載入端代碼的複寫（讀碼對照，未經測試鎖定，NOT VERIFIED） ─────────────────────────
RESULT_SCHEMA_VERSION = 1
STATUS_EVALUATED = "evaluated"
STATUS_BLOCKED = "blocked"
_PROBLEM_NO_ACTIVE = "no_active_source"
_PROBLEM_HOLDING_READ_FAILED = "holding_read_failed"
_PROBLEMS = (_PROBLEM_NO_ACTIVE, _PROBLEM_HOLDING_READ_FAILED, "settings_read_failed", "settings_value_unusable")
# 結果的設定鍵（試算表鍵）→ VM 設定代碼；順序＝載入端的設定鍵表。
_SETTING_KEY_MAP = (("alo_basis", "basis"), ("alo_target_weights", "targets"), ("alo_tolerance_pp", "tolerance"),
                    ("alo_bucket_names", "bucket_names"))
_REQUIRED_ENVELOPE_KEYS = ("schema_version", "status", "blocked_reason", "problems", "settings_status",
                           "holding_failure_code", "chart_claim", "evidence")

# 證據生產者（`services.v2_domain.allocation_evidence`）的詞彙（讀碼對照，未經測試鎖定，NOT VERIFIED）：`source_coverage.status`、`ProvidedItems.status`。
_COVERAGE_COMPLETE = "complete"
_COVERAGE_INCOMPLETE = "incomplete"
_COVERAGE_FAILED = "failed"
_COVERAGE_NOT_SELECTED = "not_selected"
_FACET_PROVIDED = "provided"
_SETTING_SET = "set"

# 持倉列的**暫行**欄位集合：T6（欄位集合與語意）未核准，這只是讓 VM 有東西可承載的起手式，**不是欄位規格**。
# 說明（含兩個暫行登記項的引用）放在公開字串 `PROVISIONAL_ROW_FIELDS_NOTE`，測試可檢。
PROVISIONAL_ROW_FIELDS_NOTE = (
    "暫行（暫行登記項：provisional_row_fields_exclude_amounts）：預設欄位集合只含識別、幣別、數量欄位，不含任何金額或比例欄位"
    "（含逐檔 cost_twd、value_twd；客戶明示不產生未核准金額）；欄位集合屬 T6，不是規格，不得升格。"
    "已知落差（暫行登記項：bucket_blank_semantics_gap）：預設也不含 bucket——82 §11.3 規定空白＝未分類、獨立呈現、不推斷，"
    "而 _row_fact 把空白一律當缺值；呼叫端仍可明確傳入 bucket，但其空白語意未依 82 處理，不得升格。")
PROVISIONAL_ROW_FIELDS = ("fund_name", "fund_code", "ccy", "units_shares")
# 證據持倉列裡**會把金額／比例帶進來**的欄位名：未核准金額不得產生（T1＝B、N＝C，`DEC-2026-11-09-02`；客戶 2026-11-14 明示），
# 呼叫端明確傳 `row_fields` 指名它們時 fail-closed（ValueError）。這是「擋已知金額／比例欄位名」的最小黑名單，**不是**允許清單：
# 不固化欄位集合（不在名單內也不代表核准）；日後客戶核准某個金額欄位時，由授權的批次從此名單移除。
FORBIDDEN_ROW_FIELDS = ("value_twd", "cost_twd", "cost_orig_ccy", "share_of_covered_pct", "weight_ratio")


# ───────────────────────── 封包驗證（契約違規 → ValueError） ─────────────────────────

class _Envelope:
    """驗證後的封包（只含本檔需要的欄位；不保留對輸入 dict 的可變參照）。"""

    __slots__ = ("status", "blocked_reason", "problems", "settings_status", "holding_failure_code", "evidence")

    def __init__(self, status, blocked_reason, problems, settings_status, holding_failure_code, evidence):
        self.status = status
        self.blocked_reason = blocked_reason
        self.problems = problems
        self.settings_status = settings_status
        self.holding_failure_code = holding_failure_code
        self.evidence = evidence


def _require_mapping(name: str, value) -> Mapping:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} 必須是 Mapping，收到 {type(value).__name__}")
    return value


def _envelope(result) -> _Envelope:
    result = _require_mapping("result", result)
    for key in _REQUIRED_ENVELOPE_KEYS:
        if key not in result:
            raise ValueError(f"result 缺必要鍵 {key!r}")
    version = result["schema_version"]
    if type(version) is not int or version != RESULT_SCHEMA_VERSION:
        raise ValueError(f"不支援的 schema_version {version!r}（只認 {RESULT_SCHEMA_VERSION}）")
    status = result["status"]
    if status not in (STATUS_EVALUATED, STATUS_BLOCKED):
        raise ValueError(f"未知的 status {status!r}")
    if result["chart_claim"] != vm.CHART_CLAIM_WITHHELD:
        raise ValueError("chart_claim 只能是 withheld_pending_approval（本層不主張圖表可比）")
    problems = result["problems"]
    if not isinstance(problems, (list, tuple)) or not all(isinstance(p, str) for p in problems):
        raise ValueError("problems 必須是字串 list")
    unknown = [p for p in problems if p not in _PROBLEMS]
    if unknown:
        raise ValueError(f"未知的 problems 代碼 {unknown!r}")
    settings_status = _require_mapping("settings_status", result["settings_status"])
    states = []
    for key, code in _SETTING_KEY_MAP:
        if key not in settings_status:
            raise ValueError(f"settings_status 缺 {key!r}")
        state = settings_status[key]
        if state not in vm.SETTING_STATES:
            raise ValueError(f"settings_status[{key!r}] 未知狀態 {state!r}")
        states.append((code, state))
    failure_code = result["holding_failure_code"]
    if failure_code is not None and (not isinstance(failure_code, str) or not failure_code.strip()):
        raise ValueError("holding_failure_code 必須是非空字串或 None")
    blocked_reason = result["blocked_reason"]
    evidence = result["evidence"]
    if status == STATUS_BLOCKED:
        if evidence is not None:
            raise ValueError("blocked 的結果不得帶 evidence")
        if not isinstance(blocked_reason, str) or not blocked_reason.strip():
            raise ValueError("blocked 必須帶 blocked_reason")
    else:
        _require_mapping("evidence", evidence)
        for key in ("source", "holdings", "source_coverage"):
            if key not in evidence:
                raise ValueError(f"evidence 缺必要鍵 {key!r}")
        if not isinstance(evidence["holdings"], (list, tuple)):
            raise ValueError("evidence['holdings'] 必須是 list")
    return _Envelope(status, blocked_reason, tuple(problems), tuple(states), failure_code, evidence)


# ───────────────────────── 事實擷取 ─────────────────────────

def _provided_count(source: Mapping, name: str) -> Optional[int]:
    """略過證據（`evidence['source'][name]`）的件數：只有來源「提供了」才有數字，其餘（未提供、無效）一律 None——不知道不是 0。"""
    facet = _require_mapping(f"evidence['source'][{name!r}]", source.get(name))
    if facet.get("status") != _FACET_PROVIDED:
        return None
    items = facet.get("items")
    if not isinstance(items, (list, tuple)):
        raise ValueError("略過證據 status=provided 但 items 不是 list")
    return len(items)


class _Resolved:
    """由封包解出的來源狀態與可用持倉列（供 `build_assets_page` 與入口函式共用，兩者不會不一致）。"""

    __slots__ = ("state", "holdings", "skipped_tabs", "skipped_rows")

    def __init__(self, state, holdings, skipped_tabs, skipped_rows):
        self.state = state
        self.holdings = holdings
        self.skipped_tabs = skipped_tabs
        self.skipped_rows = skipped_rows


def _resolve(env: _Envelope) -> _Resolved:
    """證據 → 來源狀態與可用持倉列（共用解析）。

    暫行（`PROVISIONAL_ITEMS`）：`partial_narrow_definition`（部分缺漏只限 incomplete＋有略過證據＋有列）、
    `complete_requires_zero_skip_evidence`（coverage=complete 仍須兩項略過證據都已提供且件數為 0，否則降級 undetermined）、
    `complete_no_rows_is_category_a`（(c) 來源完整但無列）、`entry_extra_coverage_and_blocked_conditions`（NO_ROWS 狀態一律不展示列）、
    `problems_override_contradicting_coverage`（問題碼 no_active／holding_read_failed 優先於矛盾的 coverage 與有列的證據）、
    `early_return_skips_row_and_coverage_validation`（有 no_active／holding_read_failed 問題碼時提早回傳，**略過持倉列 Mapping 驗證與
    source_coverage 驗證**——此時持倉列形狀錯誤不會被偵測；已知落差）。
    以上都是執行組暫行選定，82 未規定，不得升格。
    """
    if env.status == STATUS_BLOCKED:
        return _Resolved(vm.SRC_NOT_READ, (), None, None)
    evidence = env.evidence
    source = _require_mapping("evidence['source']", evidence["source"])
    skipped_tabs = _provided_count(source, "skipped_tabs")
    skipped_rows = _provided_count(source, "omitted_rows")
    if _PROBLEM_NO_ACTIVE in env.problems:
        return _Resolved(vm.SRC_NOT_SELECTED, (), skipped_tabs, skipped_rows)
    if _PROBLEM_HOLDING_READ_FAILED in env.problems:
        return _Resolved(vm.SRC_READ_FAILED, (), skipped_tabs, skipped_rows)
    rows = tuple(_require_mapping("evidence['holdings'] 的列", r) for r in evidence["holdings"])
    coverage = _require_mapping("evidence['source_coverage']", evidence["source_coverage"]).get("status")
    if coverage == _COVERAGE_NOT_SELECTED:
        state = vm.SRC_NOT_SELECTED
    elif coverage == _COVERAGE_FAILED:
        state = vm.SRC_READ_FAILED
    elif coverage == _COVERAGE_COMPLETE:
        if skipped_tabs != 0 or skipped_rows != 0:   # 任一略過證據未提供（None）或件數 >0：不得顯示來源已讀完（含不得寫成 (c)）
            state = vm.SRC_UNDETERMINED
        else:
            state = vm.SRC_COMPLETE if rows else vm.SRC_COMPLETE_NO_ROWS
    elif coverage == _COVERAGE_INCOMPLETE and rows and ((skipped_tabs or 0) > 0 or (skipped_rows or 0) > 0):
        state = vm.SRC_PARTIAL
    else:
        state = vm.SRC_UNDETERMINED   # 未知值／unknown／沒有略過證據的 incomplete：fail-closed，不當成完整
    if state in vm.NO_ROWS_SOURCE_STATES:
        rows = ()   # 證據自相矛盾（例如 coverage 說失敗卻有列）：不展示列，以來源狀態為準
    return _Resolved(state, rows, skipped_tabs, skipped_rows)


def _causes_for(source_state: str, row_count: int) -> Tuple[vm.CauseFact, ...]:
    """A10／A20／A30／A40 共用的原因（類別 (a) 在前、(b) 在後，分開成兩個事實，不合併）。

    暫行（`PROVISIONAL_ITEMS`，皆 82 未規定、不得升格）：
    - **(c)『來源完整但無持倉列』（complete_no_rows）歸類別 (a)**，原因＝引用 A00（`complete_no_rows_is_category_a`；待客戶 Decision Gate）；
    - 四格與 A30／A40 共用同一組原因（`a20_cells_share_one_missing_fact`）；
    - 市值基準 blocked（not_read）歸類別 (b)（`market_basis_blocked_symbol_and_category`）；
    - undetermined 且有列時原因含『已有持倉資料可查看』的 (b)（`undetermined_with_rows_claims_viewable_holdings`，證據不足仍聲稱有資料可看）；
    - A30／A40 沿用同一組原因（`a30_a40_share_one_missing_fact`）。
    """
    a_partial = vm.CauseFact(vm.CATEGORY_SOURCE_DATA, vm.CAUSE_PARTIAL_SOURCE)
    a_same = vm.CauseFact(vm.CATEGORY_SOURCE_DATA, vm.CAUSE_SAME_AS_SOURCE_STATUS)
    b_rows = vm.CauseFact(vm.CATEGORY_BASIS_NOT_APPROVED, vm.CAUSE_BASIS_NOT_APPROVED_WITH_ROWS)
    b_plain = vm.CauseFact(vm.CATEGORY_BASIS_NOT_APPROVED, vm.CAUSE_BASIS_NOT_APPROVED)
    if source_state == vm.SRC_COMPLETE:
        return (b_rows,)
    if source_state == vm.SRC_PARTIAL:
        return (a_partial, b_rows)
    if source_state == vm.SRC_NOT_READ:
        return (b_plain,)
    if source_state == vm.SRC_UNDETERMINED:
        return (a_same, b_rows) if row_count > 0 else (a_same,)
    return (a_same,)   # not_selected／read_failed／complete_no_rows：原始資料缺漏或取數失敗，原因引用 A00


def _a60_causes(source_state: str) -> Tuple[vm.CauseFact, ...]:
    """A60 只承載類別 (a)；來源完整或根本沒讀時沒有 (a) 原因。暫行（`PROVISIONAL_ITEMS`：`a60_field_set`），不得升格。"""
    if source_state == vm.SRC_PARTIAL:
        return (vm.CauseFact(vm.CATEGORY_SOURCE_DATA, vm.CAUSE_PARTIAL_SOURCE),)
    if source_state in (vm.SRC_COMPLETE, vm.SRC_NOT_READ):
        return ()
    return (vm.CauseFact(vm.CATEGORY_SOURCE_DATA, vm.CAUSE_SAME_AS_SOURCE_STATUS),)


def _row_fact(field_code: str, raw: Mapping) -> vm.RowFact:
    """逐檔欄位事實。暫行（`PROVISIONAL_ITEMS`：`row_field_missing_always_category_a`）：欄位沒有值或型別不可用一律歸類別 (a)，82 未規定，不得升格。"""
    value = raw.get(field_code)
    if value is None or (isinstance(value, str) and not value.strip()):
        code = vm.CAUSE_FIELD_NOT_PROVIDED
    elif isinstance(value, bool) or not isinstance(value, (str, int, float)) or (isinstance(value, float) and not math.isfinite(value)):
        code = vm.CAUSE_VALUE_UNUSABLE
    else:
        return vm.RowFact(field_code, vm.ROW_STATE_PRESENT, value, None)
    return vm.RowFact(field_code, vm.ROW_STATE_MISSING, None,
                      vm.MissingFact("missing", (vm.CauseFact(vm.CATEGORY_SOURCE_DATA, code),)))


def _rows(holdings: Sequence, row_fields: Tuple[str, ...]) -> Tuple[vm.HoldingRow, ...]:
    out = []
    for ordinal, raw in enumerate(holdings, start=1):
        out.append(vm.HoldingRow(ordinal, tuple(_row_fact(code, raw) for code in row_fields)))
    return tuple(out)


def _check_row_fields(row_fields) -> Tuple[str, ...]:
    if isinstance(row_fields, (str, bytes)) or not isinstance(row_fields, (tuple, list)) or not row_fields:
        raise ValueError("row_fields 必須是非空的 tuple／list")
    fields = tuple(row_fields)
    if len(set(fields)) != len(fields):
        raise ValueError("row_fields 不得重複")
    banned = [f for f in fields if f in FORBIDDEN_ROW_FIELDS]
    if banned:
        raise ValueError(f"row_fields 不得指名會帶進金額／比例的欄位 {banned!r}（T1＝B、N＝C）")
    return fields   # 各欄位代碼的格式由 `RowFact` 驗證


def _basis_value(env: _Envelope, basis_state: str) -> Optional[str]:
    """基準的使用者設定原值（只在證據存在、且設定狀態為 set 時取；取不到就是 None）。"""
    if env.evidence is None or basis_state != _SETTING_SET:
        return None
    settings = env.evidence.get("settings")
    fact = settings.get("basis") if isinstance(settings, Mapping) else None
    if isinstance(fact, Mapping) and fact.get("status") == _SETTING_SET:
        value = fact.get("value")
        if isinstance(value, str) and value.strip():
            return value
    return None


# ───────────────────────── 公開函式 ─────────────────────────

def provisional_holding_entry_available(result) -> bool:
    """【暫行候選／UI-2／NOT VERIFIED，**不得升格為 production 規則**】A10 是否出現「持倉入口」。

    暫行（`PROVISIONAL_ITEMS`）：`entry_extra_coverage_and_blocked_conditions`——82 只有『讀取成功』＋『至少一列』兩項條件，這裡額外排除
    來源涵蓋為未選／失敗與市值基準 blocked；`entry_shown_when_undetermined_with_rows`——來源狀態 undetermined 但有列時仍出現入口。皆不得升格。

    依 82 §11.9.9 兩項同時成立：(1) 持倉讀取成功（沒有 no_active_source／holding_read_failed 問題、來源涵蓋不是未選／失敗，且不是市值基準 blocked）；
    (2) 證據 `holdings` 至少一列。**不使用 n／m／j、不算 N／M、不增門檻、不依賴任何被 Gate 擋住的值。**
    「`holdings` 至少一列 ＝ 可用持倉列」這個對映未經客戶或獨立 QA 確認。契約違規的封包照樣 `ValueError`。
    與 `build_assets_page(...).a10.entry is not None` 恆一致（共用同一個解析）。
    """
    return len(_resolve(_envelope(result)).holdings) > 0


def build_assets_page(result, *, row_fields=PROVISIONAL_ROW_FIELDS) -> vm.AssetsPageModel:
    """`AssetsLoadResult.to_primitive()` 形狀的 dict → `AssetsPageModel`。純函式；不修改輸入、不保留對輸入的參照。

    `row_fields`：A50 持倉列要擷取的欄位代碼（預設是**暫行**集合，T6 未核准；可換）。契約違規 → `ValueError`（見模組 docstring）。
    """
    env = _envelope(result)
    fields = _check_row_fields(row_fields)
    resolved = _resolve(env)
    state, holdings = resolved.state, resolved.holdings
    row_count = len(holdings)

    a00 = vm.A00Status(
        state, vm.a00_status_key_of(state),
        failure_code=env.holding_failure_code if state == vm.SRC_READ_FAILED else None,
        cause_key=env.blocked_reason if state == vm.SRC_NOT_READ else None)
    missing = vm.MissingFact("missing", _causes_for(state, row_count))
    basis_state = dict(env.settings_status)["basis"]
    a10 = vm.A10Card(missing, basis_state, _basis_value(env, basis_state), vm.LIMIT_CODES,
                     vm.PositionEntry() if row_count > 0 else None)
    a20 = vm.A20Summary(tuple(vm.A20Cell(code, None, missing) for code in vm.A20_CELL_CODES))
    a50 = vm.A50Section(vm.A50_ROWS, _rows(holdings, fields)) if row_count > 0 else vm.A50Section(vm.A50_STATUS_ONLY)
    a52 = vm.A52Section(tuple(vm.SettingState(code, st) for code, st in env.settings_status))
    a60 = vm.A60Evidence(resolved.skipped_tabs, resolved.skipped_rows, env.problems, _a60_causes(state))
    return vm.AssetsPageModel(
        a00=a00, a10=a10, a20=a20, a30=vm.NoResultLine("A30", missing), a40=vm.NoResultLine("A40", missing),
        a50=a50, a52=a52, a60=a60)
