# -*- coding: utf-8 -*-
"""呈現規則資料表：狀態鍵 → 符號、字樣、tone；β 頁級 precedence；行動詞詞彙參照（80 第 3.3 節 (c)）。

**只轉錄已核准的字樣，不新增任何詞、符號或 tone。** 每一列都帶 `source`（文件節次／DEC 編號）與 `doc_refs`
（字樣逐字出現的 repo 文件路徑；規則表守衛測試讀這些文件逐字比對，測試位置見檔尾註解）。
已核准字樣不明確或不存在的，一律標 `PENDING_WORDING` 並寫明缺口出處（`gap`），**不得在這裡補一個字樣**。

適用範圍（BL-0532 射程）：**只限正式模式**。示範模式依 44 照舊（例：示範模式仍是 `⬜ 資料未備`），不在本表內；
`ui_v2/mkt/chart.py::TEXT_EMPTY` 那類版面示意字樣逐一判讀（見 `chart_empty` 列），不得全域取代。

護欄：
- 顏色不是唯一訊息（44 第一節第二小節、之十九其五第 1 條、`PROJECT_RULES.md` 13.2 第 3 條）：凡 tone 不是中性的列，
  必有符號＋字樣；tone 是**語意色名鍵**（不是色碼），色碼屬 design 層，本批不給值（NG-4 A）。
- 本表不判定任何資料狀態：判定在下層與正式規則；這裡只做「已判定的狀態鍵 → 呈現」的對照與 β 取最重。
- 只用標準函式庫；import 時零副作用。
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Mapping, Optional, Tuple

# 字樣尚未核准（或來源互相衝突）的標記。這不是畫面字樣，畫面層遇到它必須停下（`entry_for_*` 會拒絕交出它）。
PENDING_WORDING = "PENDING_WORDING"

DOC_44 = "docs/v2/44_fund_ui_ssot.md"
DOC_67 = "docs/v2/67_ai_action_vocabulary.md"
DOC_79 = "docs/v2/79_final_ui_contract_freeze.md"
DOC_80 = "docs/v2/80_new_ui2_architecture_proposal.md"
DOC_DECISIONS = "docs/DECISIONS.md"

# ───────────────────────── tone（語意色名鍵；不是色碼） ─────────────────────────
# 鍵 → 44 已落字的中文色名。44 只用這四個名字描述狀態色（第五節第一小節卡片表、之七其三、之七其四）。
TONE_NEUTRAL = "neutral"
TONE_GREY = "grey"
TONE_YELLOW = "yellow"
TONE_RED = "red"
TONES: Mapping[str, str] = MappingProxyType({
    TONE_NEUTRAL: "中性",
    TONE_GREY: "灰",
    TONE_YELLOW: "黃",
    TONE_RED: "紅",
})
TONES_SOURCE = "44 第五節第一小節卡片表「顏色語意」欄；44 第一節第二小節（顏色只映射資料狀態與新鮮度）；NG-4 A（DEC-2026-11-02-05）"


@dataclass(frozen=True)
class SemanticEntry:
    """一列規則：`key` → 符號、字樣、tone。

    - `symbol`／`wording` 皆 None：刻意不寫字（例：`ok` 不寫「資料齊」「正常」）。
    - `wording == PENDING_WORDING`：已核准字樣不明確或不存在；`gap` 說明缺口出處；此時 `symbol`／`tone` 可為 None。
    - 有 `symbol` 時 `wording` 必以「符號＋半形空白」開頭（44／79 的落字形式）。
    """

    key: str
    symbol: Optional[str]
    wording: Optional[str]
    tone: Optional[str]
    source: str
    doc_refs: Tuple[str, ...] = ()
    note: str = ""
    gap: str = ""

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError(f"{self.key}: 必須帶 source")
        pending = self.wording == PENDING_WORDING
        if pending:
            if not self.gap.strip():
                raise ValueError(f"{self.key}: PENDING_WORDING 必須寫明缺口出處（gap）")
            return
        if self.tone not in TONES:
            raise ValueError(f"{self.key}: tone 必須是 {tuple(TONES)} 之一，收到 {self.tone!r}")
        if self.symbol is not None:
            if not self.wording or not self.wording.startswith(self.symbol + " "):
                raise ValueError(f"{self.key}: 有符號時字樣必須以「符號＋空白」開頭")
            if not self.doc_refs:
                raise ValueError(f"{self.key}: 有字樣時必須列出逐字出處文件（doc_refs）")
        elif self.wording is not None:
            raise ValueError(f"{self.key}: 沒有符號的列不得自帶字樣（避免只靠文字或顏色表意的半套呈現）")
        if self.tone != TONE_NEUTRAL and self.symbol is None:
            raise ValueError(f"{self.key}: 非中性 tone 必須同時有符號與字樣（顏色不是唯一訊息）")

    @property
    def is_pending(self) -> bool:
        return self.wording == PENDING_WORDING


_ENTRY_LIST = (
    SemanticEntry(
        key="ok",
        symbol=None,
        wording=None,
        tone=TONE_NEUTRAL,
        source="44 第五節第一小節卡片表 ok 列（主值不著色，用中性文字色）；44 第七節第三小節之七其二第 4 條（沒有任何異常時不寫「資料齊」或「正常」）",
        note="刻意不寫字：不是漏字。",
    ),
    SemanticEntry(
        key="attention",
        symbol="◆",
        wording="◆ 需要注意",
        tone=TONE_NEUTRAL,
        source="79 §11；44 第七節第三小節之七其三第 1 條（不著色、中性文字色；DEC-2026-10-17-03 第 (3) 題）",
        doc_refs=(DOC_44, DOC_79),
        note="規則判出的注意事項；≠ 賣出訊號（79 §11）。只承接下層已判出的注意，本表不判定。",
    ),
    SemanticEntry(
        key="missing",
        symbol="◇",
        wording="◇ 資料未備",
        tone=TONE_GREY,
        source="44 第七節第三小節之七其四；44 第五節第一小節資料未備列（灰）；79 §11；DEC-2026-11-02-01（四）；BL-0532（只限正式模式）",
        doc_refs=(DOC_44, DOC_79, DOC_80),
        note="≠ 0、≠ 中性（79 §11）。示範模式依 44 照舊，不在本表。",
    ),
    SemanticEntry(
        key="undetermined",
        symbol="⬜",
        wording="⬜ 無法判定",
        tone=TONE_GREY,
        source="79 §11（⬜ 無法判定，含不適用、未設定）；44 第七節第三小節之七其四（⬜ 只留給無法判定這一族）；67 §2.6（不得以非灰色狀態色呈現）",
        doc_refs=(DOC_44, DOC_67, DOC_79, DOC_80),
        note="≠ 安全、≠ 續抱、≠ HOLD（79 §11）。",
    ),
    SemanticEntry(
        key="not_applicable",
        symbol="⬜",
        wording="⬜ 不適用",
        tone=TONE_GREY,
        source="44 第五節第一小節業務例外列（主值 `⬜ 不適用`；黃→灰，客戶 2026-10-16 裁示第 7 點）；44 第七節第三小節之七其四第 1 條",
        doc_refs=(DOC_44,),
        note="無法判定族的一種；44 原字為「⬜ 不適用」後接冒號與原因，本列只收字首。",
    ),
    SemanticEntry(
        key="fetch_failed",
        symbol="⛔",
        wording="⛔ 取數失敗",
        tone=TONE_RED,
        source="44 第五節第一小節系統錯誤列（`⛔ 取數失敗`，紅）；44 第七節第三小節之七其四；79 §11",
        doc_refs=(DOC_44, DOC_79),
        note="上游取數失敗；≠ 查無（79 §11）。",
    ),
    SemanticEntry(
        key="stale",
        symbol="◷",
        wording="◷ 不是最新",
        tone=TONE_YELLOW,
        source="79 §11（◷ 不是最新；門檻未裁示時不判）；44 第七節第三小節之七其四（文字前加 ◷；顏色照舊＝黃）；44 第五節第二小節新鮮度徽章",
        doc_refs=(DOC_79,),
        note="44 的用法是「在原有文字前加 ◷」，不是一個獨立句；只有正式門檻判為舊才用，門檻未裁示時見 threshold_pending。",
    ),
    SemanticEntry(
        key="threshold_pending",
        symbol="⬜",
        wording="⬜ 門檻待裁示",
        tone=TONE_GREY,
        source="80 §5 source／freshness display 列（門檻未裁示時只顯示天數與「⬜ 門檻待裁示」）；44 第七節第三小節之十九其四第 1 條；tone 為推論（見 note）",
        doc_refs=(DOC_44, DOC_79, DOC_80),
        note="無法判定族。⚠️ tone＝灰是推論（總管可推翻）：沒有任何來源逐字寫「門檻待裁示」的顏色；"
             "依 44 之七其四（⬜ 只留給無法判定這一族）與 67 §2.6（無法判定不得用非灰色）推得。",
    ),
    SemanticEntry(
        key="neutral",
        symbol=None,
        wording=None,
        tone=TONE_NEUTRAL,
        source="80 §5 status chips 列（chip.neutral）；44 第七節第三小節之十九其四第 1 條（chip 只呈現已算出的值：資料日、延遲……）",
        note="中性 chip（資料日、延遲天數之類 metadata）；字樣由 view model 的 label_key 給，本表不給。",
    ),
    SemanticEntry(
        key="not_configured",
        symbol="⛔",
        wording="⛔ 尚未設定",
        tone=TONE_RED,
        source="44 第七節第三小節之十二其二第 1 條（DEC-2026-10-19-05：成因是某個設定沒設、沒有執行取數 → `⛔ 尚未設定：<哪一項>`；⛔、紅色照舊；不寫成取數失敗）",
        doc_refs=(DOC_44,),
        note="狀態族字樣；「哪一項」一頁只交代一次（形式見 NOT_CONFIGURED_FORM），其餘位置寫狀態族 `⛔ 尚未設定`（44 之七其二第 3 條）。"
             "已執行取數或連線之後失敗的才是 fetch_failed；兩者不混用。",
    ),
    SemanticEntry(
        key="user_param_unset",
        symbol="⬜",
        wording="⬜ 未設定",
        tone=TONE_GREY,
        source="44 SET-3 規則欄與空狀態欄（未設定的鍵目前值欄顯示 `⬜ 未設定`）；44 第四節第五小節表 `user_setting`（沒有內建值）；44 第七節第三小節之十二其二第 1 條末句（「⬜ 未設定」＝使用者自己的參數沒填，不在該條、字面照舊）；tone 為推論（見 note）",
        doc_refs=(DOC_44,),
        note="使用者自己的參數留空（G3†：系統不代填）；不是取數失敗、不是尚未設定的資料來源。"
             "⛔ 不計入資料狀態件數、不進 β 頁級排序（DEC-2026-10-20-01：使用者自己的參數留空不是資料狀態；44 之十三其八第 23 條）。"
             "已知落差照 44 據實保留：ui_v2 資產配置／標的探索那幾格現行畫 ◇（BL-0382 登記，未裁），本列字面只依 SET-3。"
             "⚠️ tone＝灰是推論（總管可推翻）：44 未逐字寫這一格的顏色；依 44 之七其四（⬜ 只留給無法判定這一族）推得。",
    ),
    SemanticEntry(
        key="chart_empty",
        symbol=None,
        wording=PENDING_WORDING,
        tone=None,
        source="BL-0532 射程；80 §3.3 (c)；79 §11（「⬜ 資料未取得」之類為版面示意）；44 第七節第三小節之十八其三第 2 條、之十九其五第 3 條",
        gap=(
            "圖表整張無資料時的字樣：44 之十八其三第 2 條（之十九其五第 3 條沿用）規定改用空狀態元件的模板（第五節第五小節，"
            "模板依成因選）、不畫空白座標軸；New UI2 上的確切呈現隨圖卡線框裁定；"
            "`ui_v2/mkt/chart.py::TEXT_EMPTY`（「⬜ 資料未取得，無法繪圖」）屬版面示意、BL-0532 定為實作批逐一判讀。"
            "New UI2 圖卡尚無核准線框，本批不定字；日後依成因（缺資料／取數失敗／未設定）隨 New UI2 圖卡線框裁定。"
        ),
    ),
)

# 唯讀（MappingProxyType）：規則表在執行期不得被改寫。
ENTRIES: Mapping[str, SemanticEntry] = MappingProxyType({e.key: e for e in _ENTRY_LIST})

# 缺值的正式字樣（BL-0532；DEC-2026-11-02-01）。`ui_v3/viewmodels/common.py::MISSING_TEXT` 的單一來源。
MISSING_TEXT = ENTRIES["missing"].wording

# ───────────────────────── view model 鍵 → 規則鍵 ─────────────────────────
# 80 第 6 節共同欄位 `status` 的五個值（`ui_v3/viewmodels/common.py::STATUSES`，一致性由測試鎖）。
STATUS_TO_KEY: Mapping[str, str] = MappingProxyType({
    "ok": "ok",
    "missing": "missing",
    "failed": "fetch_failed",
    "stale": "stale",
    "undetermined": "undetermined",
})
# `failed` 的成因若是「設定沒設、沒有執行取數」，下層以這個 reason_code 標示 → 呈現 `⛔ 尚未設定`，不得寫成取數失敗
# （44 之十二其二第 1 條）。鍵名屬內部命名；adapters 負責把下層的原因對到它。
REASON_NOT_CONFIGURED = "not_configured"

# 一般畫面上 fetch_failed 的組合形式（44 已落字的模板；`<…>` 為佔位，不是字樣）：
# - 四頁一般畫面：`⛔ <中文資料類> 取數失敗` 加一句影響範圍（44 §5.5 系統錯誤列，DEC-2026-10-17-03）；
# - 同一來源失敗、同頁其餘受影響的塊：`⛔ 此區塊暫時無法判定`（44 之七其二第 3 條；屬系統錯誤族，紅，不加 ⬜）；
# - 尚未設定：`⛔ 尚未設定：<哪一項>`（44 之十二其二第 1 條）。
FETCH_FAILED_SCREEN_FORM = "⛔ <中文資料類> 取數失敗"
FETCH_FAILED_SAME_SOURCE_TEXT = "⛔ 此區塊暫時無法判定"
NOT_CONFIGURED_FORM = "⛔ 尚未設定：<哪一項>"
COMPOSITE_FORMS_SOURCE = "44 §5.5 系統錯誤列（DEC-2026-10-17-03）；44 第七節第三小節之七其二第 3 條；44 第七節第三小節之十二其二第 1 條（DEC-2026-10-19-05）"
# 80 第 6 節 `freshness_state`：fresh 不加任何標記；stale → ◷；門檻未裁示（undetermined）→ ⬜ 門檻待裁示（80 §5）。
FRESHNESS_TO_KEY: Mapping[str, Optional[str]] = MappingProxyType({
    "fresh": None,
    "stale": "stale",
    "undetermined": "threshold_pending",
})
# 80 第 5 節 status chips 的 kind（`ui_v3/viewmodels/components.py::CHIP_KINDS`，一致性由測試鎖）。
CHIP_KIND_TO_KEY: Mapping[str, str] = MappingProxyType({
    "attention": "attention",
    "missing": "missing",
    "undetermined": "undetermined",
    "failed": "fetch_failed",
    "stale": "stale",
    "neutral": "neutral",
})


def entry(key: str, *, allow_pending: bool = False) -> SemanticEntry:
    """依規則鍵取一列。未知鍵 → KeyError（不猜）。

    字樣未核准（PENDING_WORDING）的列預設拒絕交出（LookupError），以免佔位字串上畫面；
    只有檢視規則表本身（守衛、報告）時才傳 `allow_pending=True`。
    """
    if key not in ENTRIES:
        raise KeyError(f"未知的呈現規則鍵 {key!r}")
    found = ENTRIES[key]
    if found.is_pending and not allow_pending:
        raise LookupError(f"{key!r} 的字樣尚未核准（PENDING_WORDING）：{found.gap}")
    return found


def entry_for_status(status: str, reason_code: Optional[str] = None) -> SemanticEntry:
    """view model `status`（＋可選的 `reason_code`）→ 規則列。

    `failed` 的呈現（44）：
    - 成因是設定沒設、沒有執行取數（`reason_code == REASON_NOT_CONFIGURED`）→ `not_configured`（`⛔ 尚未設定`），
      **永遠不寫成取數失敗**（44 之十二其二第 1 條）；
    - 其餘 → `fetch_failed`（`⛔ 取數失敗`）。一般畫面上它以組合形式出現：`⛔ <中文資料類> 取數失敗` 加一句影響範圍
      （44 §5.5），同一來源的其餘受影響塊寫 `⛔ 此區塊暫時無法判定`（44 之七其二第 3 條）；
      組合文案由 view model builder 依 `FETCH_FAILED_SCREEN_FORM`／`FETCH_FAILED_SAME_SOURCE_TEXT` 組，本函式只給狀態列。
    `REASON_NOT_CONFIGURED` 只對 `failed` 有意義；配在其他 status 上 → ValueError（狀態與原因矛盾，不猜）。
    """
    if status not in STATUS_TO_KEY:
        raise KeyError(f"未知的 status {status!r}")
    if reason_code == REASON_NOT_CONFIGURED:
        if status != "failed":
            raise ValueError(f"reason_code={REASON_NOT_CONFIGURED!r} 只能配 status='failed'，收到 {status!r}")
        return entry("not_configured")
    return entry(STATUS_TO_KEY[status])


def entry_for_freshness(freshness_state: str) -> Optional[SemanticEntry]:
    """`freshness_state` → 規則列；`fresh` 回 None（不加標記，也不寫「正常」）。"""
    if freshness_state not in FRESHNESS_TO_KEY:
        raise KeyError(f"未知的 freshness_state {freshness_state!r}")
    key = FRESHNESS_TO_KEY[freshness_state]
    return None if key is None else entry(key)


def entry_for_chip_kind(kind: str) -> SemanticEntry:
    """`StatusChip.kind` → 規則列。"""
    if kind not in CHIP_KIND_TO_KEY:
        raise KeyError(f"未知的 chip kind {kind!r}")
    return entry(CHIP_KIND_TO_KEY[kind])


def pending_entries() -> Tuple[SemanticEntry, ...]:
    return tuple(e for e in _ENTRY_LIST if e.is_pending)


# ───────────────────────── β 頁級 precedence（DEC-2026-10-30-04） ─────────────────────────
# 客戶原話（逐字；測試比對 `docs/DECISIONS.md`）。範圍限制：只用於 page-level presentation status；
# 不改 domain block 原判定、不進 Decision Digest、不是 Risk Cap 的輸入或輸出。
BETA_QUOTE = "取數失敗 > 無持倉 > ◆ > ◇ > ⬜ > 持股只評估一部分（H7） > 無偏離／帶內"
BETA_SOURCE = "DEC-2026-10-30-04（P3／β；只限 page-level presentation status）"


@dataclass(frozen=True)
class PrecedenceLevel:
    """β 的一級：`key`（程式鍵）、`beta_label`（客戶原話中的該段，逐字）、`entry_key`（對應規則列；None＝本表無字樣）。"""

    key: str
    beta_label: str
    entry_key: Optional[str]
    source: str = BETA_SOURCE
    wording_gap: str = ""

    def __post_init__(self) -> None:
        if self.entry_key is None and not self.wording_gap.strip():
            raise ValueError(f"{self.key}: 沒有對應規則列時必須寫明字樣缺口（wording_gap）")


# 由重到輕。`no_holding`／`partial`／`normal` 的頁級顯示字樣不在本批來源（44／67／79 §11）內，entry_key 為 None。
_BETA_WORDING_GAP = ("頁級顯示字樣（PENDING_WORDING）：74 F-5 字樣屬 ui_v2 頁級 aggregation 的呈現，不自動沿用；"
                     "隨 💼 我的資產 New UI2 wireframe Gate 一併提出")
BETA_LEVELS: Tuple[PrecedenceLevel, ...] = (
    PrecedenceLevel("fetch_failed", "取數失敗", "fetch_failed"),
    PrecedenceLevel("no_holding", "無持倉", None, wording_gap=_BETA_WORDING_GAP),
    PrecedenceLevel("attention", "◆", "attention"),
    PrecedenceLevel("missing", "◇", "missing"),
    PrecedenceLevel("undetermined", "⬜", "undetermined"),
    PrecedenceLevel("partial", "持股只評估一部分（H7）", None, wording_gap=_BETA_WORDING_GAP),
    PrecedenceLevel("normal", "無偏離／帶內", None, wording_gap=_BETA_WORDING_GAP),
)
BETA_RANK: Mapping[str, int] = MappingProxyType({level.key: index for index, level in enumerate(BETA_LEVELS)})


def resolve_precedence(classes: Iterable[str]) -> str:
    """多個 β 級別鍵 → 最重的那一個（客戶原則：任何一區異常或未完整評估，不得被另一區的正常遮蔽）。

    空輸入 → ValueError：沒有任何分類不代表正常（Missing ≠ 正常）。未知鍵 → KeyError（不猜）。

    ⛔ 上線閘門：P3 page-level 頁燈的 production 以 BL-0411 修好為前提（DEC-2026-10-30-04：「先修 BL-0411，再允許 P3
    production 上線」）。在那之前本函式**不得**接進任何頁級燈或頁級結論；目前只供規則表測試與日後 view model 備用。
    """
    keys = list(classes)
    if not keys:
        raise ValueError("沒有任何分類可比較；不得推論為正常")
    for key in keys:
        if key not in BETA_RANK:
            raise KeyError(f"未知的 β 級別 {key!r}")
    return min(keys, key=BETA_RANK.__getitem__)


# ───────────────────────── 行動詞詞彙參照（67 §2；不新增詞） ─────────────────────────
# 67 第 2.1～2.6 節標題，逐字、依序；`ui_v3/viewmodels/action_slot.py` 讀這一份。
ACTION_WORDS: Tuple[str, ...] = ("續抱", "觀察", "降低曝險", "減碼", "替代比較", "無法判定")
ACTION_WORDS_SOURCE = "67 §2（六個行動詞，語意邊界 SSOT）；67 §8.2（System Action State 值域只用六詞，不新增行動詞）"
# 「無法判定」的呈現字型（67 §2.6、§8.2：沿用 44 既有字型）。括號內是「缺什麼」的兩種原因，不是新行動詞。
ACTION_UNDETERMINED_FORM = "⬜ 無法判定（資料未備／證據不足）"
ACTION_UNDETERMINED_FORM_SOURCE = "67 §2.6；67 §8.2「呈現」列；44 第七節第三小節之四其三"

# 守衛測試：tests/ui_v3/test_ui_v3_semantics_rules.py、tests/ui_v3/test_ui_v3_design_tokens.py。
