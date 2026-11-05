# -*- coding: utf-8 -*-
"""💼 資產配置「載入端」adapter：既有正式資料層結果 → `AllocationEvidence`（BL-0542 G-2；內部候選，未接任何頁）。

這是 composition root：把 L2（`services.v2_tables`）已經存在的唯讀結果，組成既有的 Complete Evidence 單一生產者
`services.v2_domain.allocation_evidence.build_allocation_evidence` 要的引數，然後原樣交給它。
**不新增資料源、不新增公式、不新增分類器、不重算任何數字、不補任何缺值**；證據物件原樣通過（本檔不改它的任何欄位）。
**沒有頁、沒有 viewmodel、沒有 registry 登錄**（接頁需要線框草稿與客戶核准）；本檔不 import streamlit、不 import ui_v2。

兩層：
1. **純組裝層**（無 I/O，可單元測）：`parse_settings`、`settings_stage`、`holding_stage_inputs`、`evaluate`、`basis_mode_of`。
2. **薄 I/O 層** `load(state, secret_values)`：只在函式內才 import L2（`l2_reads()`；模組層零 L2 import，
   `test_ui_v3_preview_not_formal_guard` 的執行期白名單不受影響），只呼叫讀取路徑。測試以 `reads=`／`producer=` 兩個注入縫換掉 L2 與生產者，
   不碰 `sys.modules`。

範圍（fail-closed）：
- **只組成本基準（與基準未設）**。市值基準需要淨值與匯率的組裝（`assemble_nav`、淨值未備天數門檻）——那是 ui_v2 專屬邏輯，
  搬移未獲授權；所以市值基準一律回 `blocked`（`BLOCKED_MARKET_BASIS`），**不呼叫生產者**、不建 nav／匯率表、不用捏造或殘缺的淨值。
  本檔不讀、不定義、不搬動淨值未備天數門檻（單一擁有者仍是 ui_v2）。
- 設定解析 `parse_settings` 是 `ui_v2/alo/live.py::parse_user_settings` 對四個證據用鍵的最小鏡像（ui_v3 不得 import ui_v2），
  由 `tests/ui_v3/test_ui_v3_assets_source_settings_differential.py` 逐案與 ui_v2 比對鎖住。
  已知的**唯一有意差異**：JSON 裡超大整數（> 1e308）ui_v2 會在 `math.isfinite` 拋 `OverflowError`（整頁崩潰）；本檔當作「值不可用」。
  `alo_scenario_input` 不是證據輸入，本檔不解析它。
- 任何一個設定鍵不可用（解析失敗／最新一列壞掉）→ 與 ui_v2 同：整張 `user_setting` 視為讀不到（交給生產者 `errors["user_setting"]`），
  不把「壞的」畫成「未設定」；逐鍵狀態（set／unset／invalid／broken_row）另放在結果的 `settings_status`。

L2 結果 → 生產者引數（失敗一律固定句、不帶原文；從 L2 來的字串先過 L2 遮蔽）：
- 沒有 Active（未登入，或「無可用的 Active」）→ `source_state.active_source="none"`、持倉空表、不放 skipped 兩項（不知道，不假裝「沒有略過」）。
- 其他 `ActiveSourceError` → `errors["holding"]`＝固定句（只含白名單內的 error code）、`active_source="selected"`。
- `SettingsSheetError` → `errors["user_setting"]`＝固定句、`settings=None`（四個設定都是 read_failed）。
- 不放 `errors["policy"]`（會多出一個 `non_holding_read_error`，而本檔沒有讀 policy）。
- 匯率規則是否已驗證 `fx_rule_verified`：**每次載入時**讀 L2 `market_indicator.FX_OBS_DATE_RULE_VERIFIED` 的現值（不複製常數）。
  成本基準不需要任何非 TWD 匯率，所以生產者不會因它記 gate；它只原樣回聲在 `evidence.fx_rule_verified`。

⚠️ 未驗證（據實）：真實 Google／MoneyDJ／Yahoo 連線需要憑證，**測試只用替身與 L2 純函式 `build_alo_tables` 的真形狀**，
**不證明真實連線可用**。Preview 沒有登入與 Active 選擇 UI，真的載入時會走「沒有 Active」路徑。
「來源完整」的證據只有 ui_v2 同款的兩項（`skipped_holdings`、`skipped_tabs`）；L2 其他略過群組（孤兒、壞列等）不進證據，與 ui_v2 一致，未另行驗證其充分性。
`load_alo_tables_active` 遇到 `HoldingIdCollision`（防禦性、正式路徑不可達）等非 `ActiveSourceError` 例外時照 L2 契約往上拋（fail loud）。

**圖表可比性不由本檔主張**：結果的 `chart_claim` 恆為 `withheld_pending_approval`（含 blocked，含生產者回 comparable 的完整成本基準輸入）。
證據裡的 `chart_comparability` 是生產者的內部候選詞彙（未核准契約），原樣保留、不覆寫、不重算；任何讀者不得把它當成「圖表可比」的宣稱。

已揭露的事項（給客戶與下游讀者）：
(a) **personal_session 的存取面（刻意的、已揭露的例外）**：本檔不 import `services.v2_tables.personal_session`
    （`tests/test_personal_policy_reader.py` 把「誰 import 它」鎖成恰兩個檔，本批不改守衛），而是經 L2 模組屬性
    `alo_holdings.personal_session` 取得該模組的**常數**。允許的存取面**僅限**：`.ec` 上的 `AUTH_REQUIRED`、`UNAVAILABLE`、`ALL_ERROR_CODES`，
    以及 `.REASON_NO_ACTIVE`；**不呼叫它的任何函式**。由 `tests/ui_v3/test_ui_v3_assets_source_import_isolation.py` 以 AST 鎖定。
(b) **`load()` 對契約外輸入會拋例外**（程式錯誤）：L2 回傳缺 `holding` 鍵或不是 mapping、`secret_values` 型別不對、
    非 `ActiveSourceError`／`SettingsSheetError` 的例外（含 `HoldingIdCollision`）、設定回傳缺 `rows`／`broken_keys`。
    呼叫端（日後的頁）**不得 catch-all 後畫成空白或「完整」**——那會把程式錯誤變成假的正常。
    （`holding` 表本身的型別不對則**不拋**：原值交給生產者，記成 `holding_table_unreadable`＝來源 unknown、valuation failed。）
(c) 本 adapter 目前**沒有任何 production 呼叫端**，在 💼 頁（需線框草稿與客戶核准）接線之前都是如此。
(d) `settings_status` 的詞彙與證據的 `SettingFact` 詞彙**不同**（例：`bucket_names=[]` 在這裡是 `set`、在證據裡是 `empty`；
    讀取失敗在這裡是逐鍵 `read_failed`）。下游**不得把 `settings_status` 當成真相**，以證據為準；它只是解析階段的診斷。
(e) 略過列／略過分頁的字串（可能含試算表 ID 或網址）**只**由 L2 遮蔽器處理；遮蔽器認得的只有呼叫端傳入的秘密值，
    不認得的字串會原樣進證據。證據不是畫面字，上畫面前必須另行處理。

本檔所有名稱（含 `BLOCKED_MARKET_BASIS`、各狀態與問題代碼、結果 schema）皆為**內部候選**，不是已核准詞彙。
"""
from __future__ import annotations

import dataclasses
import json
import math
from collections.abc import Mapping
from typing import Callable, Optional

from services.v2_domain import allocation_evidence as _ev

__all__ = (
    "RESULT_SCHEMA_VERSION", "CHART_CLAIM_WITHHELD", "STATUS_EVALUATED", "STATUS_BLOCKED", "BLOCKED_MARKET_BASIS",
    "BASIS_COST_VALUE", "BASIS_MARKET_VALUE",
    "SETTING_SET", "SETTING_UNSET", "SETTING_INVALID", "SETTING_BROKEN", "SETTING_READ_FAILED",
    "PROBLEM_NO_ACTIVE", "PROBLEM_HOLDING_READ_FAILED", "PROBLEM_SETTINGS_READ_FAILED", "PROBLEM_SETTINGS_UNUSABLE",
    "KIND_LOADED", "KIND_NO_ACTIVE", "KIND_FAILED",
    "HoldingOutcome", "SettingsOutcome", "ParsedSettings", "SettingsStage", "AssetsLoadResult", "L2Reads",
    "basis_mode_of", "parse_settings", "settings_stage", "holding_stage_inputs", "evaluate", "l2_reads", "load",
)

RESULT_SCHEMA_VERSION = 1   # INTERNAL CANDIDATE（與證據 schema 一樣不是已核准契約）

# 圖表可比性的「主張」欄位唯一合法值（INTERNAL CANDIDATE）。證據裡的 `chart_comparability` 是生產者的內部候選詞彙（未核准），
# Preview adapter 從不主張「可比」：不論證據怎麼說（含 comparable），這個欄位恆為此值，blocked 結果也一樣。
CHART_CLAIM_WITHHELD = "withheld_pending_approval"

STATUS_EVALUATED = "evaluated"
STATUS_BLOCKED = "blocked"
BLOCKED_MARKET_BASIS = "market_basis_assembly_not_available_in_preview"   # INTERNAL CANDIDATE

# 基準存值：L2 `settings_store.ENUM_SETTING_VALUES["alo_basis"]` 的可選值；哪一個是成本、哪一個是市值是領域語意，
# L2 只給集合，所以這裡各寫一次，由測試對 L2 與 ui_v2 逐字鎖住（不是第二份真相源）。
BASIS_COST_VALUE = "成本"
BASIS_MARKET_VALUE = "市值"

SETTING_SET = "set"
SETTING_UNSET = "unset"
SETTING_INVALID = "invalid"
SETTING_BROKEN = "broken_row"
SETTING_READ_FAILED = "read_failed"

PROBLEM_NO_ACTIVE = "no_active_source"
PROBLEM_HOLDING_READ_FAILED = "holding_read_failed"
PROBLEM_SETTINGS_READ_FAILED = "settings_read_failed"
PROBLEM_SETTINGS_UNUSABLE = "settings_value_unusable"

KIND_LOADED = "loaded"
KIND_NO_ACTIVE = "no_active"
KIND_FAILED = "failed"

# 證據用的四個設定鍵：試算表鍵 → 生產者鍵（順序固定）。
_SETTING_KEYS = (
    ("alo_basis", "basis"),
    ("alo_target_weights", "targets"),
    ("alo_tolerance_pp", "tolerance"),
    ("alo_bucket_names", "bucket_names"),
)

_UNKNOWN_CODE = "unknown"
_MSG_SETTINGS_READ_FAILED = "user_setting read failed"
_MSG_SETTINGS_UNUSABLE = "user_setting value unusable"


# ═══════════════════════ 基準 → BasisMode ═══════════════════════


def basis_mode_of(basis) -> "_ev.BasisMode":
    """基準存值 → `BasisMode`（與 ui_v2：市值基準走市場路徑並追蹤過期；成本基準不走）。未知值大聲失敗，由生產者記成 `basis_mode_error`。"""
    if basis == BASIS_COST_VALUE:
        return _ev.BasisMode(market=False, track_stale=False)
    if basis == BASIS_MARKET_VALUE:
        return _ev.BasisMode(market=True, track_stale=True)
    raise ValueError("unsupported basis value")


# ═══════════════════════ 設定解析（ui_v2/alo/live.py 的最小鏡像；四個證據鍵） ═══════════════════════


class _Bad(ValueError):
    """設定值不是約定的形狀（內部用；不外漏原文）。"""


def _reject_constant(_name):
    raise _Bad("non-finite constant")


def _json_array(text) -> list:
    if not isinstance(text, str) or text != text.strip():
        raise _Bad("not a trimmed string")
    try:
        data = json.loads(text, parse_constant=_reject_constant)
    except _Bad:
        raise
    except (ValueError, RecursionError):
        raise _Bad("not json") from None
    if not isinstance(data, list):
        raise _Bad("not an array")
    return data


def _finite_number(value):
    """有限數 → float，否則 None（bool 不是數）。超大整數（`math.isfinite` 會 OverflowError）一律當不可用——與 ui_v2 的唯一有意差異。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        finite = math.isfinite(value)
    except OverflowError:
        return None
    return float(value) if finite else None


def _weight_ratio(value):
    if value is None:
        return None
    number = _finite_number(value)
    if number is None or not 0.0 <= number <= 1.0:
        raise _Bad("weight_ratio")
    return number


def _parse_targets(text) -> list:
    out = []
    for item in _json_array(text):
        if not isinstance(item, dict) or set(item) != {"bucket", "weight_ratio"}:
            raise _Bad("target element shape")
        bucket = item["bucket"]
        if not isinstance(bucket, str) or not bucket.strip():
            raise _Bad("target bucket")
        out.append({"bucket": bucket, "weight_ratio": _weight_ratio(item["weight_ratio"])})
    return out


def _parse_bucket_names(text) -> list:
    names = _json_array(text)
    for name in names:
        if not isinstance(name, str) or not name.strip():
            raise _Bad("bucket name")
    return list(names)


def _parse_tolerance(text) -> float:
    if not isinstance(text, str) or text != text.strip():
        raise _Bad("tolerance text")
    try:
        number = float(text)
    except ValueError:
        raise _Bad("tolerance number") from None
    if not math.isfinite(number):
        raise _Bad("tolerance finite")
    return number


def _parse_basis(text) -> str:
    if text not in (BASIS_COST_VALUE, BASIS_MARKET_VALUE):
        raise _Bad("basis value")
    return text


_PARSERS = {
    "alo_basis": _parse_basis,
    "alo_target_weights": _parse_targets,
    "alo_tolerance_pp": _parse_tolerance,
    "alo_bucket_names": _parse_bucket_names,
}


@dataclasses.dataclass(frozen=True)
class ParsedSettings:
    """`parse_settings` 的結果。`values` 鍵為生產者的四個設定鍵（未設／不可用＝None）；`statuses` 鍵為試算表鍵。"""

    values: Mapping
    statuses: tuple   # ((試算表鍵, 狀態), ...) 依 `_SETTING_KEYS` 順序

    @property
    def usable(self) -> bool:
        return all(status in (SETTING_SET, SETTING_UNSET) for _key, status in self.statuses)


def parse_settings(rows, broken_keys=()) -> ParsedSettings:
    """L2 `load_user_settings()` 的 `rows`／`broken_keys` → 四個證據設定鍵的解析結果。純函式；輸入不被修改。

    - 沒有這一列／值為 None → `unset`（不補預設）；
    - 值解析不了 → `invalid`；最新一列壞掉的鍵（`broken_keys`）→ `broken_row`（兩者都不是「未設定」）；
    - `rows` 不是 mapping、`broken_keys` 不是 list／tuple／set → 四鍵一律 `invalid`（fail-closed，不當成沒設定）。
    """
    if rows is not None and not isinstance(rows, Mapping):
        return _all_invalid()
    if broken_keys is None:
        broken = frozenset()
    elif isinstance(broken_keys, (list, tuple, set, frozenset)):
        try:
            broken = frozenset(broken_keys)
        except TypeError:
            return _all_invalid()
    else:
        return _all_invalid()
    rows = rows or {}
    values, statuses = {}, []
    for key, name in _SETTING_KEYS:
        entry = rows.get(key) or {}
        value, status = None, SETTING_UNSET
        if not isinstance(entry, Mapping):
            status = SETTING_INVALID
        elif key in broken:
            status = SETTING_BROKEN
        else:
            raw = entry.get("setting_value")
            if raw is not None:
                try:
                    value, status = _PARSERS[key](raw), SETTING_SET
                except _Bad:
                    value, status = None, SETTING_INVALID
        values[name] = value
        statuses.append((key, status))
    return ParsedSettings(values, tuple(statuses))


def _all_invalid() -> ParsedSettings:
    return ParsedSettings({name: None for _key, name in _SETTING_KEYS},
                          tuple((key, SETTING_INVALID) for key, _name in _SETTING_KEYS))


# ═══════════════════════ L2 結果的中介形狀 ═══════════════════════


@dataclasses.dataclass(frozen=True)
class SettingsOutcome:
    """`user_setting` 讀取結果：`loaded`（帶 L2 的 rows／broken_keys）或 `failed`（不帶任何原文）。"""

    kind: str
    rows: Optional[Mapping] = None
    broken_keys: object = ()   # L2 給的原值；型別由 `parse_settings` 檢查（list／tuple／set 以外 → 四鍵 invalid）


@dataclasses.dataclass(frozen=True)
class HoldingOutcome:
    """持倉讀取結果：`loaded`（帶 L2 的表）、`no_active`、`failed`（只帶白名單內的 error code）。"""

    kind: str
    tables: Optional[Mapping] = None
    failure_code: Optional[str] = None


@dataclasses.dataclass(frozen=True)
class SettingsStage:
    """設定階段的結論：生產者要的 `settings`（可用時）／`user_setting` 錯誤句（不可用時）、逐鍵狀態、是否為市值基準。"""

    settings: Optional[Mapping]
    error: Optional[str]
    statuses: tuple
    market_basis: bool
    read_failed: bool


def settings_stage(outcome: SettingsOutcome) -> SettingsStage:
    """設定讀取結果 → 設定階段結論（純函式）。"""
    if outcome.kind != KIND_LOADED:
        return SettingsStage(None, _MSG_SETTINGS_READ_FAILED,
                             tuple((key, SETTING_READ_FAILED) for key, _name in _SETTING_KEYS), False, True)
    parsed = parse_settings(outcome.rows, outcome.broken_keys)
    market = dict(parsed.statuses).get("alo_basis") == SETTING_SET and parsed.values["basis"] == BASIS_MARKET_VALUE
    if parsed.usable:
        return SettingsStage(dict(parsed.values), None, parsed.statuses, market, False)
    return SettingsStage(None, _MSG_SETTINGS_UNUSABLE, parsed.statuses, market, False)


# ═══════════════════════ 持倉階段 → 生產者引數 ═══════════════════════


def _mask_text(value, mask):
    return mask(value) if isinstance(value, str) else value


def _skipped_holdings(items, mask):
    out = []
    for item in items:
        if not isinstance(item, Mapping):
            out.append(item)   # 形狀不對：原樣交給生產者記成 invalid（不猜、不吞）
            continue
        reasons = item.get("reasons")
        out.append({
            "tab": _mask_text(item.get("tab"), mask),
            "row": item.get("row"),
            "fund_code": _mask_text(item.get("fund_code"), mask),
            "reasons": [mask(str(r)) for r in reasons] if isinstance(reasons, (list, tuple)) and reasons else None,
        })
    return out


def _skipped_tabs(items, mask):
    out = []
    for item in items:
        if not isinstance(item, Mapping):
            out.append(item)
            continue
        entry = {"tab": _mask_text(item.get("tab"), mask)}
        error = item.get("error")
        if isinstance(error, str) and error.strip():
            entry["error"] = mask(error)
        out.append(entry)
    return out


def _failure_code(holding: HoldingOutcome, mask) -> str:
    """失敗 code（已在 `_read_holdings` 過白名單）再過一次遮蔽——白名單若被注入了秘密，句子與結果欄位都不外漏。"""
    return mask(holding.failure_code or _UNKNOWN_CODE)


def holding_stage_inputs(holding: HoldingOutcome, stage: SettingsStage, *, mask) -> tuple:
    """持倉結果＋設定階段 → `(tables, source_state)`（純函式）。成本基準只放 `holding` 表；不建 nav／market_indicator。"""
    errors = {} if stage.error is None else {"user_setting": stage.error}
    if holding.kind == KIND_NO_ACTIVE:
        return {"holding": []}, {"active_source": "none", "errors": errors}
    if holding.kind == KIND_FAILED:
        code = _failure_code(holding, mask)
        errors["holding"] = f"holding source read failed ({code})"   # code 已過白名單與遮蔽（`_failure_code`）
        return {"holding": []}, {"active_source": "selected", "errors": errors}
    if holding.kind != KIND_LOADED or holding.tables is None:
        raise ValueError(f"unsupported holding outcome kind {holding.kind!r}")
    tables = holding.tables
    source_state = {"active_source": "selected", "errors": errors}
    # 存在的鍵才放（即使是空 list＝「讀過、沒有略過」）；缺鍵＝不知道，讓生產者記成 not_provided（來源不算完整）。
    if tables.get("skipped_tabs") is not None:
        source_state["skipped_tabs"] = _skipped_tabs(tables["skipped_tabs"], mask)
    if tables.get("skipped_holdings") is not None:
        source_state["skipped_holdings"] = _skipped_holdings(tables["skipped_holdings"], mask)
    # 原值交給生產者（它自己 `list()` 並把不可讀記成 `holding_table_unreadable`）；缺 `holding` 鍵仍是 KeyError（契約外，大聲失敗）。
    return {"holding": tables["holding"]}, source_state


# ═══════════════════════ 結果 ═══════════════════════


@dataclasses.dataclass(frozen=True)
class AssetsLoadResult:
    """載入結果（凍結）。`evidence` 是生產者原樣產出的 `AllocationEvidence`（`blocked` 時為 None）；英文代碼，無畫面字。"""

    status: str
    blocked_reason: Optional[str]
    evidence: Optional["_ev.AllocationEvidence"]
    problems: tuple
    settings_status: tuple
    holding_failure_code: Optional[str] = None
    schema_version: int = RESULT_SCHEMA_VERSION
    # 恆為 `CHART_CLAIM_WITHHELD`（建構時驗證，其他值當場 ValueError）。`evidence.chart_comparability` 是內部候選、未核准的詞彙，
    # 即使它寫 comparable，Preview adapter 也不據以宣稱圖表可比；本欄不是由證據推導（沒有重算、沒有覆寫證據）。
    chart_claim: str = CHART_CLAIM_WITHHELD

    def __post_init__(self) -> None:
        if self.chart_claim != CHART_CLAIM_WITHHELD:
            raise ValueError("chart_claim can only be the withheld value; Preview never asserts a comparable chart")

    def to_primitive(self) -> dict:
        """嚴格 JSON 形式（證據走生產者自己的 `to_primitive`；缺值維持 None，不變成 0）。"""
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "blocked_reason": self.blocked_reason,
            "problems": list(self.problems),
            "settings_status": {key: status for key, status in self.settings_status},
            "holding_failure_code": self.holding_failure_code,
            "chart_claim": self.chart_claim,
            "evidence": None if self.evidence is None else _ev.to_primitive(self.evidence),
        }


def evaluate(stage: SettingsStage, holding: Optional[HoldingOutcome], *, mask, fx_key_of, fx_rule_verified,
             producer: Optional[Callable] = None) -> AssetsLoadResult:
    """設定階段＋持倉結果 → `AssetsLoadResult`（純函式；唯一的下游呼叫是注入的生產者）。

    市值基準 → `blocked`，**不呼叫生產者**（`holding` 可為 None）。其餘一律呼叫生產者一次，`nav_not_ready=None`、`nav_provenance=None`
    （成本基準用不到；生產者只在市值路徑驗證它們）。
    """
    if stage.market_basis:
        return AssetsLoadResult(STATUS_BLOCKED, BLOCKED_MARKET_BASIS, None, (), stage.statuses)
    if holding is None:
        raise TypeError("holding outcome is required unless the basis is market value")
    if fx_rule_verified is not None and not isinstance(fx_rule_verified, bool):
        fx_rule_verified = None   # 非布林＝不明，當「未提供」（生產者會記 gate），不猜
    tables, source_state = holding_stage_inputs(holding, stage, mask=mask)
    build = producer if producer is not None else _ev.build_allocation_evidence
    evidence = build(
        tables, settings=stage.settings, nav_not_ready=None, fx_key_of=fx_key_of, basis_mode_of=basis_mode_of,
        category_of=None, source_state=source_state, nav_provenance=None, fx_rule_verified=fx_rule_verified)
    problems = []
    if holding.kind == KIND_NO_ACTIVE:
        problems.append(PROBLEM_NO_ACTIVE)
    if holding.kind == KIND_FAILED:
        problems.append(PROBLEM_HOLDING_READ_FAILED)
    if stage.read_failed:
        problems.append(PROBLEM_SETTINGS_READ_FAILED)
    elif stage.error is not None:
        problems.append(PROBLEM_SETTINGS_UNUSABLE)
    return AssetsLoadResult(STATUS_EVALUATED, None, evidence, tuple(problems), stage.statuses,
                            _failure_code(holding, mask) if holding.kind == KIND_FAILED else None)


# ═══════════════════════ 薄 I/O 層 ═══════════════════════


@dataclasses.dataclass(frozen=True)
class L2Reads:
    """`load` 對 L2 的全部依賴（注入縫）。預設值見 `l2_reads()`；測試換成替身，不碰 `sys.modules`。"""

    read_holdings: Callable          # (state, secret_values) -> mapping；失敗拋 holding_errors 之一
    read_settings: Callable          # (secret_values) -> mapping（rows／broken_keys）；失敗拋 settings_errors 之一
    holding_errors: tuple
    settings_errors: tuple
    is_no_active: Callable           # (exc) -> bool
    known_codes: frozenset           # 白名單內的 error code（不在內的一律寫成 unknown）
    make_mask: Callable              # (secret_values) -> (str -> str)
    fx_key_of: Callable
    read_fx_rule_verified: Callable  # () -> bool | None（每次載入時讀現值）


def l2_reads() -> L2Reads:
    """預設注入：真的 L2。**在函式內才 import**（import 本模組時不得載入 pandas／L1）。只取讀取入口。"""
    from services.v2_tables import alo_holdings, market_indicator, settings_store  # lazy
    # 橋接模組經 `alo_holdings` 的屬性取得，不另開 import 句：`tests/test_personal_policy_reader.py` 把「誰 import personal_session」
    # 鎖成恰兩個檔，本檔不加入那份名單（零守衛變更）。`ec` 是它持有的九個 error code（`shared` 不開放給 ui_v3 直接 import）。
    personal_session = alo_holdings.personal_session
    codes = personal_session.ec

    def is_no_active(exc) -> bool:
        # 與 `ui_v2/active_gate.is_no_active` 同一判定：未登入；或 UNAVAILABLE 且 reason 為「沒有 Active」。
        if exc.code == codes.AUTH_REQUIRED:
            return True
        return exc.code == codes.UNAVAILABLE and getattr(exc, "reason", None) == personal_session.REASON_NO_ACTIVE

    return L2Reads(
        read_holdings=alo_holdings.load_alo_tables_active,
        read_settings=settings_store.load_user_settings,
        holding_errors=(alo_holdings.ActiveSourceError,),
        settings_errors=(settings_store.SettingsSheetError,),
        is_no_active=is_no_active,
        known_codes=frozenset(codes.ALL_ERROR_CODES),
        make_mask=alo_holdings.masker,
        fx_key_of=market_indicator.fx_indicator_key,
        read_fx_rule_verified=lambda: market_indicator.FX_OBS_DATE_RULE_VERIFIED,
    )


def _safe_code(code, known) -> str:
    return code if isinstance(code, str) and code in known else _UNKNOWN_CODE


def _read_settings(reads: L2Reads, secret_values) -> SettingsOutcome:
    try:
        payload = reads.read_settings(secret_values)
    except reads.settings_errors:
        return SettingsOutcome(KIND_FAILED)   # 原文一律丟棄（可能含秘密）
    # `broken_keys` 原樣傳遞（不 tuple()）：字串會被拆成單字元而無聲丟掉壞列標記；型別不對由 `parse_settings` 一律判四鍵 invalid。
    return SettingsOutcome(KIND_LOADED, payload["rows"], payload["broken_keys"])


def _read_holdings(reads: L2Reads, state, secret_values) -> HoldingOutcome:
    try:
        tables = reads.read_holdings(state, secret_values)
    except reads.holding_errors as exc:
        if reads.is_no_active(exc):
            return HoldingOutcome(KIND_NO_ACTIVE)
        return HoldingOutcome(KIND_FAILED, failure_code=_safe_code(getattr(exc, "code", None), reads.known_codes))
    return HoldingOutcome(KIND_LOADED, tables=tables)


def load(state, secret_values, *, reads: Optional[L2Reads] = None, producer: Optional[Callable] = None) -> AssetsLoadResult:
    """取數＋組裝＋交給生產者。`state`：呼叫端注入的可變 mapping（L2 續期／清 session 會用；本檔不 import streamlit）；
    `secret_values`：呼叫端讀好的秘密值清單（只給 L2 遮蔽用）。

    順序：先讀設定（市值基準直接 `blocked`，不再讀持倉、不呼叫生產者），再讀持倉。只呼叫唯讀入口。
    生產者的程式錯誤（引數型別不對等）照樣往上拋；資料與設定的問題由它記成證據，不拋。
    """
    reads = reads if reads is not None else l2_reads()
    mask = reads.make_mask(secret_values)   # 先建遮蔽器：秘密值型別不對（例如傳成字串）在任何讀取之前就大聲失敗
    stage = settings_stage(_read_settings(reads, secret_values))
    if stage.market_basis:
        return evaluate(stage, None, mask=mask, fx_key_of=reads.fx_key_of, fx_rule_verified=None, producer=producer)
    holding = _read_holdings(reads, state, secret_values)
    return evaluate(stage, holding, mask=mask, fx_key_of=reads.fx_key_of,
                    fx_rule_verified=reads.read_fx_rule_verified(), producer=producer)
