# -*- coding: utf-8 -*-
"""💼 我的資產頁的 view model（S-VM 切片；純 Python、frozen、建構時驗證；無 streamlit／services／I/O）。

依據：`docs/v2/82` §11.9.7（390px 線框）、§11.9.9、§11.9.10、§11.9.11、§11.11（J-1～J-18）；
客戶 2026-11-14 授權（只限新增 5 檔，限 fake／fixture 輸入；**不接頁、不掛 registry、不寫 renderer、不接正式資料**）。

本層只放**代碼與事實**，不放畫面文字。需要字樣時只有兩條路：
(1) 引用 `shared/ui_semantics/rules.py` 已核准的狀態字樣——以規則表的**鍵**表示（`status_key`），不複製字樣；
(2) 暫時字樣：集中在本檔最後一節 `ASSETS_PENDING_WORDING`（與 `preview_wording.py` 同款：`PendingWording`、status 恆為 pending、
    每條帶 source）。**候選字樣來源是 82 線框的〔候選／待裁示〕文字，未核准**；日後客戶定字後搬進規則表並刪除該列。
VM 物件本身只存代碼（`cause_key`、`source_state`…），不存字樣。

⚠️ **本檔所有名稱與代碼（`source_state`、`cause_key`、類別 (a)(b)、`a20_cell_N`、`field_code`…）皆為「內部候選，非核准詞彙」**：
不是新狀態詞、不是 cause_key 映射的正式規格、不是欄位名稱的正式規格（`DEC-2026-11-09-04` UI-1）。
**命名說明**：本檔刻意不使用 `reason_code` 這個名稱——`cause_key`、`source_state`、`status_key` 等都是**內部候選的程式鍵**，
**不是** UI-1 所指的「使用者面 reason_code／狀態詞／狀態映射」，也不會作為畫面字出現；`status_key` 只是指向 `rules.py` 已核准鍵的引用。
（`blocked_reason` 是載入端結果的既有欄位名，原樣沿用，不是本檔新增。）
類別 (a)＝原始資料缺漏或取數失敗；類別 (b)＝原始資料可能存在，但正式計算口徑尚未核准故不提供結果（82 §11.9.11）。
兩類**必須是可區分的兩個代碼**，不得合併成一句、也不得互相冒充。

硬規則（逐條有測試）：
- **A20 恆為固定 4 格**，格位用位置代碼 `a20_cell_1`～`a20_cell_4`，**不寫金融名詞**（四格的現行標籤屬 T5，未核准）；
  缺值一律 `value=None`＋原因，**絕不轉 0**。本階段 `A20_VALUES_ENABLED = False`（Formula Gate）：任何非 None 的值建構時即 ValueError。
- **不含**任何金額合計、類別小計、百分比、100%、配置比例、報酬、損益、健康／安全／過期／正常判斷（T1＝B、N＝C、`DEC-2026-11-09-02`）。
  本檔沒有任何欄位能承載這些東西；`AllocationEvidence.categories[*].value_twd` 不會被帶進來（adapter 根本不讀 `categories`）。
- A50 持倉列**不固化欄位集合**（82 標 T6 欄位未核准）：`HoldingRow` 只是 `RowFact` 的 tuple，`field_code` 由 adapter 呼叫端決定；
  VM 不列舉合法欄位，且 `A50Section.field_set_status` 恆為 `FIELD_SET_PENDING_T6`。
- 入口（A10 的「持倉入口」）只在 A50 有可用列時存在；a（未選 Active）、b（讀取失敗）、c（完整但無列）、市值基準 blocked 一律沒有入口，
  也不寫「持倉 0」。入口條件對映是 UI-2 的**暫行候選**（82 §11.9.9 自標 NOT VERIFIED），見 adapter。
- `chart_claim` 恆為 `withheld_pending_approval`（與載入端 adapter 的 `AssetsLoadResult` 一致）；本層沒有圖、沒有圖表可比性欄位。

**暫行標示**：本批凡是「82 沒有規定、由執行組暫行選定」的歸類與條件，一律登記在公開常數 `PROVISIONAL_ITEMS`（唯一 key＋說明＋對應缺口），
並在相關 docstring 標「暫行：…不得升格」。它們都不是客戶核准的規則，升格需客戶 Decision Gate。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional, Tuple

from shared.ui_semantics import rules
from ui_v3.viewmodels.common import require_key, require_text
from ui_v3.viewmodels.exp_counts import require_count
from ui_v3.viewmodels.preview_wording import STATUS_PENDING, PendingWording

# ───────────────────────── 區塊順序與固定結構 ─────────────────────────

BLOCK_ORDER = ("A00", "A10", "A20", "A30", "A40", "A50", "A52", "A60")
A20_CELL_CODES = ("a20_cell_1", "a20_cell_2", "a20_cell_3", "a20_cell_4")   # 內部候選；位置代碼，不是金融名詞
# Formula Gate：A20 四格的正式計算未核准 → 本階段任何非 None 的值都拒絕。日後客戶核准後由授權的批次改這個常數（含測試）。
A20_VALUES_ENABLED = False
# 與載入端 adapter 的 `CHART_CLAIM_WITHHELD` 同值（測試鎖；VM 不 import adapters）。
CHART_CLAIM_WITHHELD = "withheld_pending_approval"

# 本層可引用的**已核准**狀態字樣（規則表 `ENTRIES` 的鍵；不複製字樣，不新增任何一個）。
APPROVED_STATUS_KEYS = ("missing", "undetermined", "fetch_failed", "not_configured", "user_param_unset")

# 首屏元素點數上限（頁級 chip＋核心數字；82 §0.1、§11.2；DEC-2026-11-03-11）。
FIRST_SCREEN_LIMIT = 5

# A50 欄位集合狀態：T6 未核准，恆為此值（見 `A50Section`）。
FIELD_SET_PENDING_T6 = "pending_t6"

# ───────────────────────── 內部候選代碼表（非核准詞彙） ─────────────────────────

# 缺值原因類別（82 §11.9.11；內部候選）。
CATEGORY_SOURCE_DATA = "source_data_missing_or_failed"       # (a) 原始資料缺漏或取數失敗
CATEGORY_BASIS_NOT_APPROVED = "calculation_basis_not_approved"   # (b) 原始資料可能存在，但正式計算口徑尚未核准
CAUSE_CATEGORIES = (CATEGORY_SOURCE_DATA, CATEGORY_BASIS_NOT_APPROVED)   # 順序＝顯示順序（a 在前）

# 缺值原因鍵（內部候選）。
CAUSE_PARTIAL_SOURCE = "partial_source"                                  # (a) 部分略過
CAUSE_SAME_AS_SOURCE_STATUS = "same_as_source_status"                    # (a) 引用 A00 同一狀態
CAUSE_FIELD_NOT_PROVIDED = "field_not_provided"                          # (a) 逐檔欄位來源沒有值
CAUSE_VALUE_UNUSABLE = "value_unusable"                                  # (a) 值的型別不可用
CAUSE_BASIS_NOT_APPROVED_WITH_ROWS = "basis_not_approved_with_rows"      # (b) 已有可看的持倉列，但計算口徑未核准
CAUSE_BASIS_NOT_APPROVED = "basis_not_approved"                          # (b) 計算口徑未核准（不聲稱有持倉列）
_CAUSE_CATEGORY = MappingProxyType({
    CAUSE_PARTIAL_SOURCE: CATEGORY_SOURCE_DATA,
    CAUSE_SAME_AS_SOURCE_STATUS: CATEGORY_SOURCE_DATA,
    CAUSE_FIELD_NOT_PROVIDED: CATEGORY_SOURCE_DATA,
    CAUSE_VALUE_UNUSABLE: CATEGORY_SOURCE_DATA,
    CAUSE_BASIS_NOT_APPROVED_WITH_ROWS: CATEGORY_BASIS_NOT_APPROVED,
    CAUSE_BASIS_NOT_APPROVED: CATEGORY_BASIS_NOT_APPROVED,
})
CAUSE_KEYS = tuple(_CAUSE_CATEGORY)

# 來源狀態（A00；內部候選）。對映 82 §11.9.11 的三種來源情境：complete／partial／（not_selected｜read_failed｜complete_no_rows）；
# `undetermined`＝證據不足以歸入前面任何一個（fail-closed，不當作完整）；`not_read`＝本批市值基準 blocked，持倉來源**根本沒讀**。
SRC_COMPLETE = "complete"
SRC_PARTIAL = "partial"
SRC_NOT_SELECTED = "not_selected"            # (a) 未選 Active
SRC_READ_FAILED = "read_failed"              # (b) 讀取失敗
SRC_COMPLETE_NO_ROWS = "complete_no_rows"    # (c) 來源完整且無有效列
SRC_UNDETERMINED = "undetermined"
SRC_NOT_READ = "not_read"
SOURCE_STATES = (SRC_COMPLETE, SRC_PARTIAL, SRC_NOT_SELECTED, SRC_READ_FAILED, SRC_COMPLETE_NO_ROWS, SRC_UNDETERMINED, SRC_NOT_READ)
# 不可能有持倉入口／可展開 A50 的來源狀態。
NO_ROWS_SOURCE_STATES = (SRC_NOT_SELECTED, SRC_READ_FAILED, SRC_COMPLETE_NO_ROWS, SRC_NOT_READ)
_A00_STATUS_KEY = MappingProxyType({
    SRC_COMPLETE: None, SRC_PARTIAL: None, SRC_NOT_SELECTED: None, SRC_COMPLETE_NO_ROWS: None,
    SRC_READ_FAILED: "fetch_failed", SRC_UNDETERMINED: "undetermined", SRC_NOT_READ: "undetermined",
})

# 設定項目與狀態（內部候選；狀態詞彙＝載入結果的 `settings_status`，不是證據的 `SettingFact` 詞彙）。
SETTING_CODES = ("basis", "targets", "tolerance", "bucket_names")
SETTING_STATES = ("set", "unset", "invalid", "broken_row", "read_failed")

# 資料限制代碼（內部候選）：本階段不做任何匯率換算。
LIMIT_NO_FX_CONVERSION = "no_fx_conversion"
LIMIT_CODES = (LIMIT_NO_FX_CONVERSION,)

ENTRY_TARGET_BLOCK = "A50"

ROW_STATE_PRESENT = "present"
ROW_STATE_MISSING = "missing"
A50_ROWS = "rows"                  # 有可用列（手機收合／桌面條件式展開由 renderer 日後決定，不在 VM）
A50_STATUS_ONLY = "status_only"    # 一列狀態文字；不畫空表、不寫「持倉 0」


def category_of_cause(cause_key: str) -> str:
    """原因鍵 → 類別 (a)(b)。未知代碼 KeyError（不猜）。"""
    return _CAUSE_CATEGORY[cause_key]


def a00_status_key_of(source_state: str) -> Optional[str]:
    """來源狀態 → A00 要引用的已核准狀態字樣鍵；沒有已核准字樣者為 None（改走暫時字樣）。"""
    return _A00_STATUS_KEY[source_state]


# ───────────────────────── 驗證輔助 ─────────────────────────

def _tuple_of(name: str, value: object, cls: type, *, non_empty: bool = False) -> tuple:
    if not isinstance(value, tuple) or not all(isinstance(v, cls) for v in value):
        raise TypeError(f"{name} 必須是 {cls.__name__} 的 tuple")
    if non_empty and not value:
        raise ValueError(f"{name} 不得為空")
    return value


def _require_in(name: str, value: object, allowed: tuple) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(f"{name} 必須在 {allowed}，收到 {value!r}")
    return value


def _require_approved_status_key(name: str, value: object) -> str:
    _require_in(name, value, APPROVED_STATUS_KEYS)
    if value not in rules.ENTRIES:   # 規則表若移除該鍵，這裡大聲失敗（不留下指向空氣的引用）
        raise ValueError(f"{name}={value!r} 不在規則表 ENTRIES")
    return value


# ───────────────────────── 缺值事實 ─────────────────────────

@dataclass(frozen=True)
class CauseFact:
    """缺值的一個原因：類別 (a)(b)＋原因鍵。`category` 必須與 `cause_key` 的類別一致（兩類不得互相冒充）。"""

    category: str
    cause_key: str

    def __post_init__(self) -> None:
        _require_in("category", self.category, CAUSE_CATEGORIES)
        _require_in("cause_key", self.cause_key, CAUSE_KEYS)
        if _CAUSE_CATEGORY[self.cause_key] != self.category:
            raise ValueError(f"cause_key={self.cause_key!r} 屬於 {_CAUSE_CATEGORY[self.cause_key]!r}，不是 {self.category!r}")


@dataclass(frozen=True)
class MissingFact:
    """一個「值沒有、而且不是 0」的事實：已核准狀態字樣的鍵＋一至兩個原因（類別 (a) 在前、(b) 在後；原因鍵不得重複）。

    類別 (b) 只能搭 `missing`（`◇ 資料未備`）——82 §11.9.7：狀態字樣仍只用已核准的那一個，兩類差別只在「說明原因」。
    """

    status_key: str
    causes: Tuple[CauseFact, ...]

    def __post_init__(self) -> None:
        _require_approved_status_key("status_key", self.status_key)
        _tuple_of("causes", self.causes, CauseFact, non_empty=True)
        codes = [r.cause_key for r in self.causes]
        if len(set(codes)) != len(codes):
            raise ValueError("causes 不得有重複的原因鍵")
        order = [CAUSE_CATEGORIES.index(r.category) for r in self.causes]
        if order != sorted(order):
            raise ValueError("causes 必須類別 (a) 在前、(b) 在後")
        if CATEGORY_BASIS_NOT_APPROVED in self.categories and self.status_key != "missing":
            raise ValueError("類別 (b)（計算口徑未核准）只能搭 status_key='missing'（狀態字樣只用已核准的 `◇ 資料未備`）")

    @property
    def categories(self) -> Tuple[str, ...]:
        return tuple(r.category for r in self.causes)


# ───────────────────────── A00 ─────────────────────────

@dataclass(frozen=True)
class A00Status:
    """頁級來源狀態（單一正式狀態容器）。

    - `status_key`：該來源狀態對應的**已核准**狀態字樣鍵（`a00_status_key_of`）；沒有已核准字樣的狀態為 None（改走暫時字樣，鍵＝`source_state`
      加 `a00_` 前綴，見 `ASSETS_PENDING_WORDING`）。
    - `failure_code`：僅 `read_failed` 可有；**內部分類碼，只用來選「人話失敗分類」，不得上畫面**（原文與代碼都不上一般畫面）。
    - 暫行（`PROVISIONAL_ITEMS`：`a00_states_without_approved_symbol`、`market_basis_blocked_symbol_and_category`）：
      complete／partial／not_selected／complete_no_rows 沒有已核准符號，改走暫時字樣；市值基準 blocked 的 `not_read` 借用已核准的
      `undetermined` 符號——82 都沒有規定，不得升格。
    - `cause_key`：僅 `not_read` 可有（市值基準 blocked 的原因碼，原樣透傳；內部候選）。
    """

    source_state: str
    status_key: Optional[str]
    failure_code: Optional[str] = None
    cause_key: Optional[str] = None

    def __post_init__(self) -> None:
        _require_in("source_state", self.source_state, SOURCE_STATES)
        expected = _A00_STATUS_KEY[self.source_state]
        if self.status_key != expected:
            raise ValueError(f"source_state={self.source_state!r} 的 status_key 必須是 {expected!r}，收到 {self.status_key!r}")
        if self.status_key is not None:
            _require_approved_status_key("status_key", self.status_key)
        if self.failure_code is not None:
            require_text("failure_code", self.failure_code)
            if self.source_state != SRC_READ_FAILED:
                raise ValueError("failure_code 只有 read_failed 可有")
        if self.cause_key is not None:
            require_key("cause_key", self.cause_key)
            if self.source_state != SRC_NOT_READ:
                raise ValueError("cause_key 只有 not_read 可有")
        if self.source_state == SRC_NOT_READ and self.cause_key is None:
            raise ValueError("not_read 必須帶 cause_key")


# ───────────────────────── A10 ─────────────────────────

@dataclass(frozen=True)
class PositionEntry:
    """A10 降級卡的「持倉入口」。**UI-2：暫行候選，不得升格為 production 規則**（82 §11.9.9 自標 NOT VERIFIED）。

    入口不攜帶任何數字（不放檔數、涵蓋率、占比；82 §11.9.9「入口不放」）、不是 chip。`provisional` 恆為 True（建構時驗證）；
    存在條件由 adapter 的暫行候選函式決定，並由 `AssetsPageModel` 驗證「有入口 ⇒ A50 有可用列」。
    """

    target_block: str = ENTRY_TARGET_BLOCK
    provisional: bool = True

    def __post_init__(self) -> None:
        if self.target_block != ENTRY_TARGET_BLOCK:
            raise ValueError(f"入口只能指向 {ENTRY_TARGET_BLOCK}")
        if self.provisional is not True:
            raise ValueError("入口是 UI-2 暫行候選，provisional 必須為 True（不得升格為 production 規則）")


@dataclass(frozen=True)
class A10Card:
    """A10 資產配置降級卡（主圖區在缺口徑時的精簡降級卡；不畫圖、不含任何比例／金額）。

    - `missing`：狀態字樣鍵＋原因（類別 (a)(b) 分開並列，不混成一句）。
    - `basis_state`／`basis_value`：SPEC 的「基準」一項；`basis_value` 是使用者設定的原值（使用者資料，不是系統字樣），僅 `basis_state=='set'` 時可有。
      SPEC 的其餘項（單位、時點、缺項）屬 T5，**本批不建模**。
    - `limit_codes`：必要資料限制代碼。
    - `entry`：持倉入口（可為 None）。
    """

    missing: MissingFact
    basis_state: str
    basis_value: Optional[str]
    limit_codes: Tuple[str, ...]
    entry: Optional[PositionEntry] = None

    def __post_init__(self) -> None:
        if not isinstance(self.missing, MissingFact):
            raise TypeError("missing 必須是 MissingFact")
        _require_in("basis_state", self.basis_state, SETTING_STATES)
        if self.basis_value is not None:
            require_text("basis_value", self.basis_value)
            if self.basis_state != "set":
                raise ValueError("basis_value 只有 basis_state='set' 才可有")
        _tuple_of("limit_codes", self.limit_codes, str)
        for code in self.limit_codes:
            _require_in("limit_codes", code, LIMIT_CODES)
        if self.entry is not None and not isinstance(self.entry, PositionEntry):
            raise TypeError("entry 必須是 PositionEntry 或 None")


# ───────────────────────── A20 ─────────────────────────

@dataclass(frozen=True)
class A20Cell:
    """A20 摘要的一格。本階段 `value` 恆為 None（Formula Gate）；缺值＝None＋`missing`，**絕不轉 0**。"""

    cell_code: str
    value: Optional[float]
    missing: MissingFact

    def __post_init__(self) -> None:
        _require_in("cell_code", self.cell_code, A20_CELL_CODES)
        if not isinstance(self.missing, MissingFact):
            raise TypeError("missing 必須是 MissingFact")
        if self.value is not None:
            if not A20_VALUES_ENABLED:
                raise ValueError("A20 的正式計算未核准（Formula Gate）：value 只能是 None（缺值不得轉成 0 或任何數字）")
            if isinstance(self.value, bool) or not isinstance(self.value, (int, float)) or not math.isfinite(self.value):
                raise ValueError(f"value 必須是有限數字或 None，收到 {self.value!r}")


@dataclass(frozen=True)
class A20Summary:
    """A20 四項摘要：恆為固定 4 格，順序固定為 `A20_CELL_CODES`。

    暫行（`PROVISIONAL_ITEMS`：`a20_cells_share_one_missing_fact`）：82 要求四格「逐格各自判斷、不統一寫成同一原因」，但逐格判斷需要
    公式定義（Formula Gate，未核准）；adapter 因此讓四格共用同一個 `MissingFact`。這是暫行做法，不得升格。
    """

    cells: Tuple[A20Cell, ...]

    def __post_init__(self) -> None:
        _tuple_of("cells", self.cells, A20Cell)
        if tuple(c.cell_code for c in self.cells) != A20_CELL_CODES:
            raise ValueError(f"A20 必須恆為固定 4 格且順序為 {A20_CELL_CODES}")


# ───────────────────────── A30 / A40 ─────────────────────────

@dataclass(frozen=True)
class NoResultLine:
    """A30（偏離／未評估）、A40（配息／近期事件）的單行狀態：**不顯示結果**。是否保留此行屬 T7（82 §11.9.11 標〔待裁示〕）。"""

    block: str
    missing: MissingFact

    def __post_init__(self) -> None:
        _require_in("block", self.block, ("A30", "A40"))
        if not isinstance(self.missing, MissingFact):
            raise TypeError("missing 必須是 MissingFact")


# ───────────────────────── A50 ─────────────────────────

@dataclass(frozen=True)
class RowFact:
    """持倉列的一個欄位事實。`field_code` 由 adapter 呼叫端決定；本層**不列舉合法欄位**（T6 未核准）。

    present：`value` 為非空字串或有限數字（bool、NaN、inf 皆拒絕）；missing：`value` 必為 None 且帶原因（缺值不得是 0 或空字串）。
    """

    field_code: str
    state: str
    value: object
    missing: Optional[MissingFact] = None

    def __post_init__(self) -> None:
        require_key("field_code", self.field_code)
        _require_in("state", self.state, (ROW_STATE_PRESENT, ROW_STATE_MISSING))
        if self.state == ROW_STATE_PRESENT:
            if self.missing is not None:
                raise ValueError("present 的事實不得帶 missing")
            if isinstance(self.value, bool) or self.value is None:
                raise ValueError(f"present 的值不可用：{self.value!r}")
            if isinstance(self.value, str):
                require_text("value", self.value)
            elif not isinstance(self.value, (int, float)) or not math.isfinite(self.value):
                raise ValueError(f"present 的值必須是非空字串或有限數字，收到 {self.value!r}")
        else:
            if self.value is not None:
                raise ValueError("missing 的事實不得攜帶值（Missing ≠ 0／空字串）")
            if not isinstance(self.missing, MissingFact):
                raise ValueError("missing 的事實必須帶 MissingFact")


@dataclass(frozen=True)
class HoldingRow:
    """一列持倉（來源既有順序，`ordinal` 從 1 起；無排序、無 Top N、無排名）。欄位集合不固定（見 `RowFact`）。"""

    ordinal: int
    facts: Tuple[RowFact, ...]

    def __post_init__(self) -> None:
        if isinstance(self.ordinal, bool) or not isinstance(self.ordinal, int) or self.ordinal < 1:
            raise ValueError(f"ordinal 必須是 >=1 的整數，收到 {self.ordinal!r}")
        _tuple_of("facts", self.facts, RowFact, non_empty=True)
        codes = [f.field_code for f in self.facts]
        if len(set(codes)) != len(codes):
            raise ValueError("同一列的 field_code 不得重複")


@dataclass(frozen=True)
class A50Section:
    """A50 完整持倉。`rows` 狀態＝有可用列（≥1）；`status_only`＝只有一列狀態文字（引用 A00 同一狀態），不畫空表、不寫「持倉 0」。

    `field_set_status` 恆為 `FIELD_SET_PENDING_T6`：欄位集合屬 T6（未核准），本層不固化。
    """

    state: str
    rows: Tuple[HoldingRow, ...] = ()
    field_set_status: str = FIELD_SET_PENDING_T6

    def __post_init__(self) -> None:
        _require_in("state", self.state, (A50_ROWS, A50_STATUS_ONLY))
        _tuple_of("rows", self.rows, HoldingRow)
        if self.field_set_status != FIELD_SET_PENDING_T6:
            raise ValueError("欄位集合屬 T6（未核准），field_set_status 只能是 pending_t6")
        if self.state == A50_ROWS and not self.rows:
            raise ValueError("state='rows' 必須至少一列（沒有列請用 status_only，不得畫空表）")
        if self.state == A50_STATUS_ONLY and self.rows:
            raise ValueError("status_only 不得帶列")
        if [r.ordinal for r in self.rows] != list(range(1, len(self.rows) + 1)):
            raise ValueError("rows 的 ordinal 必須是 1..n 連續且依來源順序")

    @property
    def row_count(self) -> int:
        return len(self.rows)


# ───────────────────────── A52 ─────────────────────────

@dataclass(frozen=True)
class SettingState:
    """使用者設定的一項狀態（唯讀；`setting_code` 與 `state` 皆內部候選）。"""

    setting_code: str
    state: str

    def __post_init__(self) -> None:
        _require_in("setting_code", self.setting_code, SETTING_CODES)
        _require_in("state", self.state, SETTING_STATES)


@dataclass(frozen=True)
class A52Section:
    """類別歸屬與使用者設定（唯讀；內容屬〔待裁示〕，本批只承載四個設定項目的狀態碼）。

    暫行（`PROVISIONAL_ITEMS`：`a52_four_setting_states`）：82 未規定 A52 的內容；四項設定狀態是執行組暫行承載，不得升格。
    """

    settings: Tuple[SettingState, ...]

    def __post_init__(self) -> None:
        _tuple_of("settings", self.settings, SettingState)
        if tuple(s.setting_code for s in self.settings) != SETTING_CODES:
            raise ValueError(f"settings 必須依序為 {SETTING_CODES}")


# ───────────────────────── A60 ─────────────────────────

@dataclass(frozen=True)
class A60Evidence:
    """來源、略過、缺項證據（預設收合）。

    - `skipped_tab_count`／`skipped_row_count`：略過的分頁數／列數（**嚴格 int**）；來源沒有提供證據時為 None（≠ 0，不知道就是不知道）。
    - `causes`：只能是類別 (a)。**(b)「計算口徑未核准」不得由 A60 承載**（82 §11.9.7：承載位置未定，不得暗示 A60 已承載）。
    - `problem_codes`：載入階段的問題代碼（內部候選；不上畫面）。
    - 暫行（`PROVISIONAL_ITEMS`：`a60_field_set`）：A60 內部版面與欄位集合是 82 缺口 G-A（未畫）；這裡只承載「略過件數＋問題碼＋(a) 原因」，
      是執行組暫行選定的最小集合，不得升格。
    """

    skipped_tab_count: Optional[int]
    skipped_row_count: Optional[int]
    problem_codes: Tuple[str, ...]
    causes: Tuple[CauseFact, ...]

    def __post_init__(self) -> None:
        for name in ("skipped_tab_count", "skipped_row_count"):
            value = getattr(self, name)
            if value is not None:
                require_count(name, value)
        _tuple_of("problem_codes", self.problem_codes, str)
        for code in self.problem_codes:
            require_key("problem_codes", code)
        _tuple_of("causes", self.causes, CauseFact)
        if any(r.category != CATEGORY_SOURCE_DATA for r in self.causes):
            raise ValueError("A60 只承載類別 (a)；(b) 的承載位置未定，不得放進 A60")


# ───────────────────────── 整頁 ─────────────────────────

@dataclass(frozen=True)
class AssetsPageModel:
    """💼 頁的完整 view model。區塊順序固定為 `BLOCK_ORDER`（`blocks()`）。"""

    a00: A00Status
    a10: A10Card
    a20: A20Summary
    a30: NoResultLine
    a40: NoResultLine
    a50: A50Section
    a52: A52Section
    a60: A60Evidence
    chart_claim: str = CHART_CLAIM_WITHHELD

    def __post_init__(self) -> None:
        for name, cls in (("a00", A00Status), ("a10", A10Card), ("a20", A20Summary), ("a30", NoResultLine),
                          ("a40", NoResultLine), ("a50", A50Section), ("a52", A52Section), ("a60", A60Evidence)):
            if not isinstance(getattr(self, name), cls):
                raise TypeError(f"{name} 必須是 {cls.__name__}")
        if (self.a30.block, self.a40.block) != ("A30", "A40"):
            raise ValueError("a30／a40 的 block 必須分別是 A30／A40")
        if self.chart_claim != CHART_CLAIM_WITHHELD:
            raise ValueError("chart_claim 只能是 withheld_pending_approval（本層不主張圖表可比）")
        usable = self.a00.source_state not in NO_ROWS_SOURCE_STATES
        if self.a50.state == A50_ROWS and not usable:
            raise ValueError(f"來源狀態 {self.a00.source_state!r} 不可能有可用持倉列")
        if self.a10.entry is not None and self.a50.state != A50_ROWS:
            raise ValueError("入口只在 A50 有可用列時存在（無可用列不得出現導向空內容的入口）")

    def blocks(self) -> Tuple[Tuple[str, object], ...]:
        """依 `BLOCK_ORDER` 排列的 (區塊代碼, 區塊內容)。"""
        parts = (self.a00, self.a10, self.a20, self.a30, self.a40, self.a50, self.a52, self.a60)
        return tuple(zip(BLOCK_ORDER, parts))


# ───────────────────────── 首屏元素點數 ─────────────────────────

@dataclass(frozen=True)
class FirstScreenCountPolicy:
    """首屏元素點數的計法選項。**A10 入口與原因句是否計入首屏預算＝〔待 UI Review〕，本檔不替客戶下結論**，故沒有預設值，呼叫端必須明選。"""

    count_a10_entry: bool
    count_a10_causes: bool

    def __post_init__(self) -> None:
        for name in ("count_a10_entry", "count_a10_causes"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} 必須是 bool")


POLICY_A10_TEXT_EXCLUDED = FirstScreenCountPolicy(count_a10_entry=False, count_a10_causes=False)   # 82 §11.9.9：入口不是 chip
POLICY_A10_TEXT_INCLUDED = FirstScreenCountPolicy(count_a10_entry=True, count_a10_causes=True)     # 最保守讀法


def first_screen_element_count(model: AssetsPageModel, policy: FirstScreenCountPolicy) -> int:
    """首屏元素點數（頁級 chip＋核心數字；Missing 佔位仍計入的保守讀法）。

    固定計入：A00 單一狀態容器 1 個＋A20 四格各 1 個（值為 Missing 的佔位格仍計入）。
    依 `policy`（**待 UI Review**）可選計入：A10 入口（有入口才 +1）、A10 原因句（每個原因 +1）。
    A30／A40 的單行狀態、A50 以後不在首屏計法內（Primary 區之後）。這是「執行組的計法」，不是客戶核准的計法。
    """
    if not isinstance(model, AssetsPageModel):
        raise TypeError("model 必須是 AssetsPageModel")
    if not isinstance(policy, FirstScreenCountPolicy):
        raise TypeError("policy 必須是 FirstScreenCountPolicy（沒有預設：待 UI Review）")
    count = 1 + len(model.a20.cells)
    if policy.count_a10_entry and model.a10.entry is not None:
        count += 1
    if policy.count_a10_causes:
        count += len(model.a10.missing.causes)
    return count


def first_screen_within_limit(model: AssetsPageModel, policy: FirstScreenCountPolicy) -> bool:
    """首屏元素點數是否 ≤ `FIRST_SCREEN_LIMIT`。"""
    return first_screen_element_count(model, policy) <= FIRST_SCREEN_LIMIT


# ───────────────────────── 暫行標示清單 ─────────────────────────

@dataclass(frozen=True)
class ProvisionalItem:
    """一個「82 沒有規定、由執行組暫行選定」的歸類或條件。**不是客戶核准的規則，不得升格**；升格需客戶 Decision Gate。"""

    key: str
    note: str
    gap_ref: str

    def __post_init__(self) -> None:
        require_key("key", self.key)
        require_text("note", self.note)
        require_text("gap_ref", self.gap_ref)


def _p(key: str, note: str, gap_ref: str) -> ProvisionalItem:
    return ProvisionalItem(key, note, gap_ref)


PROVISIONAL_ITEMS = (
    _p("partial_narrow_definition",
       "暫行：『部分缺漏』只限 coverage=incomplete 且有略過證據（略過分頁或略過列件數>0）且有可用列；設定讀取失敗造成的 incomplete 歸 undetermined。不得升格。",
       "G-E；82 §11.9.11 三種來源狀態"),
    _p("complete_no_rows_is_category_a",
       "暫行：(c)『來源完整但無持倉列』歸類別 (a)（原因＝引用 A00），82 未規定；執行組暫行，不得升格，待客戶 Decision Gate。",
       "82 §11.7 狀態三 (c)；G-C"),
    _p("a20_cells_share_one_missing_fact",
       "暫行：A20 四格共用同一個 MissingFact；82 要求逐格各自判斷，但公式未核准（Formula Gate）無法判。不得升格。",
       "82 §11.9.7 情境二；J-9；Formula Gate"),
    _p("entry_shown_when_undetermined_with_rows",
       "暫行：來源狀態為 undetermined 但證據有列時仍出現入口（82 只要求『讀取成功且至少一列』）。不得升格。",
       "82 §11.9.9；J-1；UI-2"),
    _p("entry_extra_coverage_and_blocked_conditions",
       "暫行：入口在 82 的兩項條件之外，額外排除『來源涵蓋為未選／失敗』與『市值基準 blocked』。不得升格。",
       "82 §11.9.9；UI-2；G-E"),
    _p("a60_field_set",
       "暫行：A60 只承載略過分頁件數、略過列件數、問題碼與類別 (a) 原因；內部版面與欄位集合尚未畫（缺口）。不得升格。",
       "G-A；82 §11.6、§11.7"),
    _p("market_basis_blocked_symbol_and_category",
       "暫行：市值基準 blocked 時 A00 借用已核准的『無法判定』符號、A10／A20 歸類別 (b)；82 未規定此情境。不得升格。",
       "G-F；82 §11.3"),
    _p("a00_states_without_approved_symbol",
       "暫行：complete／partial／not_selected／complete_no_rows 四種來源狀態沒有已核准符號，改走暫時字樣（pending）；內容為〔待裁示〕。不得升格。",
       "82 §11.7、§11.9.11 A00；G-5"),
    _p("cause_basis_not_approved_plain_wording_derived",
       "暫行：『配置比較的計算口徑尚未核准，故不提供結果』是執行組由 82 候選句衍生（去掉『已有持倉資料可查看』），非 82 原句。不得升格。",
       "82 §11.9.7；UI-1"),
    _p("a52_four_setting_states",
       "暫行：A52 只承載基準、目標、容許帶、類別名稱四項設定的狀態碼；82 未規定 A52 內容。不得升格。",
       "82 §11.6 A52〔待裁示〕"),
    _p("first_screen_count_policies",
       "待 UI Review：A10 入口與原因句是否計入首屏預算有兩種計法，本層不替客戶下結論，呼叫端必須明選。",
       "82 §11.2、§11.9.9；J-2；DEC-2026-11-03-11"),
    _p("complete_requires_zero_skip_evidence",
       "暫行：coverage=complete 仍須兩項略過證據都『已提供』且件數為 0，否則降級 undetermined（不顯示來源已讀完）。82 未規定此防禦。不得升格。",
       "82 §11.9.11 來源完整"),
    _p("bucket_blank_semantics_gap",
       "已知落差：82 §11.3 規定『bucket 空白＝未分類，獨立呈現、不推斷』，而本層列事實把空白一律當缺值；因此預設欄位集合不含 bucket，"
       "呼叫端明確傳入時才擷取，且其空白語意未依 82 處理。",
       "82 §11.3；T6"),
    _p("provisional_row_fields_exclude_amounts",
       "暫行：A50 預設欄位集合只含識別、幣別、數量欄位，不含任何金額或比例欄位（客戶明示不產生未核准金額）；欄位集合本身屬 T6，不是規格，不得升格。",
       "T6；DEC-2026-11-09-02"),
)

PROVISIONAL_KEYS = tuple(p.key for p in PROVISIONAL_ITEMS)


def provisional_item(key: str) -> ProvisionalItem:
    """查暫行標示；未知鍵 KeyError。"""
    for item in PROVISIONAL_ITEMS:
        if item.key == key:
            return item
    raise KeyError(key)


# ───────────────────────── 暫時字樣（候選；與 preview_wording 同款） ─────────────────────────
# 以下**不是 VM 資料**：VM 物件只存代碼。這張表讓日後的 renderer 有地方查「候選字樣」，並以 `data-pending-wording` 標記。
# 來源一律是 82 線框的〔候選／待裁示〕文字，未核准；已核准字樣取規則表（`APPROVED_STATUS_KEYS`），不在這裡重複，也不含任何狀態符號。

_SRC_82 = "docs/v2/82 §11.9.7／§11.9.9 線框候選文字（候選、未核准；DEC-2026-11-09-04 UI-1／UI-2）"
_SRC_EXEC = "執行組由 82 候選文字衍生（候選、未核准；可被客戶推翻）"


def _w(key: str, text: str, source: str) -> PendingWording:
    return PendingWording(key, text, source)


_PENDING_LIST = (
    _w("a00_complete", "來源已讀完", _SRC_82 + "：A00「來源：<已讀完，描述性>」；字樣待裁示"),
    _w("a00_partial", "部分略過", _SRC_82 + "：A00「部分略過；件數為事實，字樣待裁示」"),
    _w("a00_not_selected", "尚未選定持倉資料來源（不退回別本 Sheet）", _SRC_82 + "：情境三 (a)"),
    _w("a00_complete_no_rows", "沒有有效持倉列", _SRC_82 + "：情境三 (c)，僅在來源完整的證據成立時才可使用"),
    _w("cause_partial_source", "來源不完整（部分略過）", _SRC_82 + "：情境二 類別(a)"),
    _w("cause_basis_not_approved_with_rows", "已有持倉資料可查看；配置比較的計算口徑尚未核准，故不提供結果", _SRC_82 + "：情境一 類別(b)"),
    _w("cause_basis_not_approved", "配置比較的計算口徑尚未核准，故不提供結果", _SRC_EXEC + "（去掉「已有持倉資料可查看」：未讀取或無可用列時不得聲稱有）"),
    _w("entry_view_holdings", "查看持倉明細", _SRC_82 + "：入口文案〔待裁示〕"),
    _w("limit_no_fx_conversion", "目前未做匯率換算，各檔原幣數值不合計", _SRC_82 + "：限制列；字樣待 T5"),
)


def _index(items: Tuple[PendingWording, ...]) -> Mapping[str, PendingWording]:
    table = {w.key: w for w in items}
    if len(table) != len(items):
        raise ValueError("ASSETS_PENDING_WORDING 有重複鍵")
    for w in items:
        if w.status != STATUS_PENDING:
            raise ValueError(f"{w.key}: 暫時字樣的 status 只能是 pending")
    return MappingProxyType(table)


ASSETS_PENDING_WORDING: Mapping[str, PendingWording] = _index(_PENDING_LIST)


def pending_wording(key: str) -> PendingWording:
    """查暫時字樣；未知鍵 KeyError（不猜）。已核准字樣不在這裡（取規則表）。"""
    return ASSETS_PENDING_WORDING[key]
