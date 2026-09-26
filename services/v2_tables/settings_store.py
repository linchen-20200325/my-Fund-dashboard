# -*- coding: utf-8 -*-
"""設定與取數紀錄的 L2 入口（set 頁第 1、2 步；docs/v2/50_settings_sheet_design.md）。

ui_v2 只經由 `ui_v2/<頁>/source.py` 碰到本檔（`49` §3.3 方案 A），本檔再呼叫
L1 `repositories/settings_sheet_repository.py`。本檔做兩件事：

1. **把遮蔽接上 L1**：L1 不得 import 本套件（上行），所以 L1 每個公開函式都要求 `mask`；
   本檔把 `masking.mask_message(訊息, 秘密值)` 包成 `mask` 交下去。秘密值由 L3 讀好傳進來
   （`masking.py` 檔頭：L2 不讀 secrets）。
2. **第 2 步：取數後寫表**（`market_indicator` ＋ `fetch_log`）：
   `run_market_indicator_fetch` 先寫 `fetch_log_open`，再以 `MarketIndicatorSheetSink` 當
   `build_market_indicator_table(sink=...)` 的 sink 呼叫；sink 寫 `market_indicator`、再寫 `fetch_log`。
   **本輪只給 set 頁觸發用，不接任何 UI。**

失敗處理（`50` 第 8 節）：
- 寫表失敗**不讓取數結果消失**：sink 不往上拋寫表的 `SettingsSheetError`，改記在
  `sink.persist` 交回（`build_market_indicator_table` 的 sink 例外會往上拋，那樣畫面就拿不到
  本次取數的結果 —— 與 `50`「本次取數的結果照常顯示在頁面上，另外標明取數紀錄寫入失敗」相違）。
  寫表以外的例外（程式錯誤、ValueError）照樣往上拋，不吞。
- 取數紀錄本身寫失敗時**不遞迴**：不為「寫 `fetch_log` 失敗」再寫一筆 `fetch_log`。
- 失敗訊息在本層遮一次，同一份字串同時放進 `fetch_log.message` 與回傳值
  （`ACCEPTANCE.md` 7.3 最後一條、7.4）。L1 不再遮第二次。

fetch_log 的 outcome（回修第 2 輪總管裁示必修 1、3、4；定案記在 docs/v2/50 第 10 節）：
- `ok`：沒有任何失敗原因；`row_count`＝**L1 取回的列數（過濾前）**，取自 `table["fetched"]`
  （`44`：「取回的列數」—— 不是過濾後的 `rows` 數，也不是新追加的列數）。
- **取數回空**（`44` SET-5）：L1 沒有給錯誤原文、只回空 → 該鍵不算失敗（`ok`、該鍵取回 0 列）；
  L1 有錯誤原文 → `failed`。判別方式：`errors[鍵]` 恰為 `market_indicator.EMPTY_WITHOUT_REASON`
  且取回 0 列，就是「L1 沒給原因的空」。⚠️ 已知限制：L1 失敗但沒交出原因時也會長這樣，分不出來。
- `failed`：任一鍵有錯誤原文；或某鍵取回 >0 列但**一列都沒寫成**（例如全部缺 `fetched_at`）；
  或寫前看到主鍵矛盾（**只擋矛盾的主鍵，其餘照寫**）；~~或 `market_indicator` 寫入失敗。~~
  `row_count` 為空，`message` 為遮蔽後的原因（多條以換行分隔）。
  ⚠️ 2026-09-26 更正（有意識的更正，不是漏刪；決策者：AI 總管）：劃掉的那一條~~**實際寫不出來**~~
  → **對「上游（gspread）讀寫失敗、會登記冷卻的那一類」寫不出來**（第 6 輪收窄；上一輪寫成全稱，
  被紅隊以標頭不符的情形實測推翻）。
  那一類：`market_indicator` 寫入時 gspread 呼叫失敗，L1 會登記冷卻（`record_gspread_failure`；
  試算表鍵或 429 的憑證鍵，冷卻秒數都大於 0），緊接著寫 `fetch_log` 時~~一定~~會被 `should_skip_gspread`
  擋下（`code="cooling"`），所以 `fetch_log` 不會有這一列；`fetch_log_open` 那一列留著，讀取端要等
  `OPEN_LOG_STALE_SEC`（1 小時）之後才顯示為「取數沒有結束紀錄」。那一次取數的真正原因只在回傳的
  `persist`（`stage="fetch_log"`、`message` 含寫表失敗與冷卻兩段原文、`log_message` 是本來要寫的那一句）
  裡，**不會進試算表**。
  **已知不登記冷卻的有：標頭不符**（L1 拋 `SettingsSheetError(code="header_mismatch")`，不是上游失敗）——
  這時 `fetch_log` 會照常寫出 `failed`，`message` 含「market_indicator 寫入失敗：標頭與規格不符……」
  （由 `tests/test_v2_tables_settings_store.py::test_market_indicator標頭不符_fetch_log照常寫failed且附原因`
  釘住）。⚠️ 這份「不登記冷卻」清單**未窮舉**，只列已知的。
  舊句的用意（寫表失敗要記 `failed`）仍然成立，錯的是它描述的是意圖、不是行為。
  **行為修正已登記下一輪**；本輪只改說明文字，邏輯未動。
- `pending`（第一階段刻意不取數）與部分列被略過（例如當天未收盤的那一列）不是失敗。
"""

from __future__ import annotations

import json
import math
from datetime import date
from typing import Callable, Optional

from repositories import settings_sheet_repository as store
from repositories.macro.yf import fetch_yf_close
from services.v2_tables import market_indicator as mi
from services.v2_tables.masking import mask_message

SettingsSheetError = store.SettingsSheetError

# ── 接線狀態（線框草稿第 10 節 B7：「尚未接上」由 L2 交給畫面，畫面不自己猜）────────────
# `49` Q12：第一階段只落地 `user_setting`、`market_indicator`、`fetch_log`；`nav`、`dividend`
# 等到 hld 階段再裁。這裡的清單就是畫面上 ★1／★2 那幾行的唯一依據。
WIRED_TABLES = ("user_setting", "market_indicator", "fetch_log")
PENDING_TABLES = ("nav", "dividend")
# set 頁「重新取數」目前只接上市場指標那一層（`run_market_indicator_fetch`）。
WIRED_TIERS = (mi.SOURCE_TIER,)
# 會讀已存設定（`user_setting`）的頁：目前只有 set 頁自己（`set_` 開頭的鍵）。
# mkt／hld／exp／alo 四頁尚未讀取已存設定（線框草稿 ★7）；哪一頁接上了，就把它的前綴加進來。
PAGES_READING_SETTINGS = ("set",)

# 「重新取數」要清的 L1 快取：第一階段真的會取數的來源 → 那個來源的 L1 取數函式本身
# （`_ttl_cache` 包過、有 `cache_clear()`）。`50` 第 10 節 B9 定案：只清本次會用到的 L1 函式
# 自己的快取，**不動來源冷卻、不呼叫全域清除**（`clear_all_caches`／`global_refresh_all`
# 都會經 `_CACHE_REGISTRY` 裡的冷卻代理解除所有來源冷卻）。
# `market_indicator` 經 `fetch_yf_close_with_error` 取 Yahoo，那一支走的是 `fetch_yf_close` 的快取。
_CACHED_FETCHER_BY_SOURCE = {"Yahoo": fetch_yf_close}


def masker(secret_values) -> Callable[[str], str]:
    """秘密值清單 → `mask`。**拒收字串**：`list("abc")` 會把一把金鑰拆成單一字元去遮，
    等於把訊息裡每個出現過的字母都換成記號（回修第 2 輪 8）。"""
    if isinstance(secret_values, (str, bytes)):
        raise TypeError("secret_values 須為秘密值的清單，不可直接傳字串")
    values = list(secret_values)
    return lambda message: mask_message(message, values)


# ── 讀寫（L3 → 這裡 → L1）────────────────────────────────────────────

def load_user_settings(secret_values) -> dict:
    return store.load_user_settings(mask=masker(secret_values))


# 枚舉型的鍵（客戶 2026-09-26 裁示；44 未改）：value_kind 為 `list`，值只能是下列其中之一。
# **可選值的唯一真相源在這裡**；`ui_v2/set/logic.py::ENUM_SETTING_VALUES` 是鏡像（由測試比對）。
ENUM_SETTING_VALUES = {"alo_basis": ("成本", "市值")}
ENUM_KIND = "list"


class ValueKindMismatch(ValueError):
    """`44` SET-4：輸入值與 `value_kind` 不符 → 不存檔。`code`：`kind_mismatch`／`kind_missing`。"""

    def __init__(self, message: str, *, code: str):
        super().__init__(message)
        self.code = code


def _is_int_literal(text: str) -> bool:
    """`-?[0-9]+`，只收 ASCII 數字（本套件的 import 白名單不含 `re`；2026-09-26 總管裁示不收全形等其他數字）。"""
    digits = text[1:] if text.startswith("-") else text
    return digits != "" and all("0" <= ch <= "9" for ch in digits)   # 只收 ASCII 0-9


def value_matches_kind(value: str, kind: str) -> bool:
    """`setting_value` 合不合 `value_kind`（`44` 4.5 那六種）。

    判法與 `ui_v2/set/logic.py::value_matches_kind` 相同（那一份登記為 SET-GAP-型別判定規則）：
    int 為整數字面、float 為數字字面、ratio 為 0 到 1 的數字、date 為 YYYY-MM-DD、
    list 與 rules 為 JSON 陣列字面。L2 不得 import ui_v2，所以這裡另寫一份，
    由 tests/test_v2_tables_settings_store_page.py 以同一批輸入逐一比對兩份結果。
    `kind` 不在六種之內 → ValueError（呼叫端的 bug）。
    """
    if kind not in store.VALUE_KIND_VALUES:
        raise ValueError(f"value_kind {kind!r} 不在 {store.VALUE_KIND_VALUES} 之內")
    if value != value.strip():
        # 前後有空白一律判不符，不靜默去掉（2026-09-26 總管裁示，Fail Loud；44 SET-4 判準：輸入欄內容與存檔前逐字相同）。
        return False
    text = value
    if kind == "int":
        return _is_int_literal(text)
    if kind in ("float", "ratio"):
        whole, dot, frac = text.partition(".")
        if not _is_int_literal(whole) or (dot and not _is_int_literal(frac)) or frac.startswith("-"):
            return False
        return kind == "float" or 0.0 <= float(text) <= 1.0
    if kind == "date":
        parts = text.split("-")
        if [len(p) for p in parts] != [4, 2, 2] or not all(_is_int_literal(p) and p[0] != "-" for p in parts):
            return False
        try:
            date.fromisoformat(text)
        except ValueError:
            return False
        return True
    try:
        parsed = json.loads(text, parse_constant=_reject_constant)  # NaN／Infinity 不是合法值
    except ValueError:
        return False
    return isinstance(parsed, list) and _all_finite(parsed)


def _reject_constant(name):
    raise ValueError(f"不收 {name}")


def _all_finite(node) -> bool:
    """解析後遞迴檢查：`[1e999]` 這類字面會溢位成 inf，`parse_constant` 攔不到（它只管 NaN／Infinity 字樣）。"""
    if isinstance(node, float):
        return math.isfinite(node)
    if isinstance(node, list):
        return all(_all_finite(item) for item in node)
    if isinstance(node, dict):
        return all(_all_finite(item) for item in node.values())
    return True


def check_setting_value(setting_value: Optional[str], value_kind: Optional[str], *,
                        setting_key: Optional[str] = None) -> None:
    """存檔前的型別檢查（`44` SET-4：輸入值與 `value_kind` 不符 → 不存檔）。不符就 `ValueKindMismatch`。

    - `setting_value` 為 None（清除該鍵）：不判值，只要 `value_kind` 在值域內就放行。
    - `value_kind` 為空或不在值域：不存（`44` 4.5 `value_kind` 不可空）。
    - 枚舉鍵（`ENUM_SETTING_VALUES`）：`value_kind` 須為 `list`，值只收可選值之一，其他一律型別不符。
    """
    if value_kind not in store.VALUE_KIND_VALUES:
        raise ValueKindMismatch(f"value_kind 未定（{value_kind!r}），不存檔", code="kind_missing")
    if setting_key in ENUM_SETTING_VALUES and value_kind != ENUM_KIND:
        raise ValueKindMismatch(f"{setting_key} 的 value_kind 須為 {ENUM_KIND}，不存檔", code="kind_mismatch")
    if setting_value is None:
        return
    if setting_key in ENUM_SETTING_VALUES:
        if setting_value not in ENUM_SETTING_VALUES[setting_key]:
            raise ValueKindMismatch(
                f"setting_value 不在 {setting_key} 的可選值 {ENUM_SETTING_VALUES[setting_key]} 之內，不存檔",
                code="kind_mismatch")
        return
    if not isinstance(setting_value, str) or setting_value.strip() == "" \
            or not value_matches_kind(setting_value, value_kind):
        raise ValueKindMismatch(f"setting_value 與 value_kind 不符（{value_kind}），不存檔",
                                code="kind_mismatch")


def save_user_setting(setting_key: str, setting_value: Optional[str], value_kind: str,
                      secret_values) -> dict:
    """存一個鍵。**先檢查值與型別**（`check_setting_value`），不符就拋 `ValueKindMismatch`、
    不呼叫 L1（不寫、也不清快取 —— 沒有任何寫入發生）。相符才交 L1（L1 不論成敗都清快取）。"""
    # 寫進去的就是使用者輸入的原值，不做任何轉換；前後帶空白由型別檢查擋下（2026-09-26 總管裁示）。
    check_setting_value(setting_value, value_kind, setting_key=setting_key)
    return store.save_user_setting(setting_key, setting_value, value_kind,
                                   mask=masker(secret_values))


def save_setting_for_page(setting_key: str, setting_value: Optional[str], value_kind: Optional[str],
                          secret_values) -> dict:
    """給 set 頁「存檔」用：把成敗收成一個純 dict（訊息皆已遮蔽），畫面依 `status` 選文案。

    `status`：`saved`／`kind_mismatch`／`kind_missing`（未寫）／`failed`（寫入失敗或冷卻、缺設定）。
    失敗時帶 `code`、`http_status`、`hint`、`remaining_sec`、`client_email`（`50` 第 8 節的 403／404 提示用；
    `client_email` 依 ACCEPTANCE 7.2 丙不遮）。寫表以外的例外照樣往上拋，不吞。
    """
    try:
        row = save_user_setting(setting_key, setting_value, value_kind, secret_values)
    except ValueKindMismatch as exc:
        return {"status": exc.code, "key": setting_key, "message": str(exc)}
    except store.SettingsSheetError as exc:
        return {"status": "failed", "key": setting_key, "message": str(exc), "code": exc.code,
                "http_status": exc.http_status, "hint": exc.hint,
                "remaining_sec": exc.remaining_sec,
                "client_email": exc.details.get("client_email") or ""}
    return {"status": "saved", "key": setting_key, "row": row}


def sheet_gate(secret_values) -> dict:
    """寫入閘門（不打上游）：`{"state", "message"（已遮蔽）, "remaining_sec"}`。見 L1 `gate_status`。"""
    return store.gate_status(mask=masker(secret_values))


def sheet_title(secret_values) -> str:
    """設定試算表的標題，**已過遮蔽**（標題不是憑證，但若客戶把 ID 取成標題就會被遮）。
    讀不到 → `SettingsSheetError`（訊息已遮蔽）。"""
    mask = masker(secret_values)
    return mask(store.load_sheet_title(mask=mask))


def load_fetch_log(secret_values) -> dict:
    return store.load_fetch_log(mask=masker(secret_values))


def load_market_indicator(secret_values) -> dict:
    return store.load_market_indicator(mask=masker(secret_values))


# ── 第 2 步：market_indicator 取數後寫表 ─────────────────────────────

def _conflict_text(conflicts) -> str:
    parts = [f"主鍵矛盾 {len(conflicts)} 筆（這些主鍵本次不寫入，其餘照寫）："]
    for c in conflicts:
        key, obs, rel = c["key"]
        parts.append(
            f"({key}, {obs}, {rel}) 既有 value_num={c['existing_value_num']!r}"
            f"（{c['existing_value_unit']}），本次 {c['new_value_num']!r}（{c['new_value_unit']}）")
    return "\n".join(parts)


class MarketIndicatorSheetSink:
    """`build_market_indicator_table(sink=...)` 的 sink：寫 `market_indicator` 與 `fetch_log`。

    用法：`sink.begin()`（寫 `fetch_log_open`）→ 當 sink 傳入 → 讀 `sink.persist`。
    `begin()` 失敗時 sink 停用：之後不再嘗試任何寫入，`persist` 記下失敗階段與原文。

    ⚠️ **`begin()` 失敗時 `persist["log_message"]` 為 None**（沒有要寫的 `fetch_log` 列，也就沒有那一句）。
    這時畫面要顯示取數錯誤，**一律讀 `persist["masked_errors"]`**（已遮蔽，`begin()` 失敗時照樣會填），
    設定試算表本身的錯誤讀 `persist["message"]`。`log_message` 只在 `begin()` 成功後才有意義：
    它與要寫進 `fetch_log.message` 的字串逐字相同（寫入成敗都放）。
    """

    def __init__(self, secret_values):
        self._mask = masker(secret_values)
        self.opened: Optional[dict] = None
        self.persist = {"ok": False, "stage": "not_started", "message": None,
                        "error_code": None, "log_id": None, "fetch_log": None,
                        "appended": 0, "already_present": 0, "conflicts": [],
                        "masked_errors": {}, "empty": {}, "log_message": None}

    def _fail(self, stage: str, exc: store.SettingsSheetError) -> None:
        self.persist.update(ok=False, stage=stage, message=str(exc), error_code=exc.code)

    def begin(self) -> bool:
        try:
            self.opened = store.open_fetch_log(mi.SOURCE_TIER, mask=self._mask)
        except store.SettingsSheetError as exc:
            self._fail("fetch_log_open", exc)
            return False
        self.persist.update(stage="started", log_id=self.opened["log_id"])
        return True

    def __call__(self, table: dict) -> None:
        fetched = table.get("fetched", {})
        # 回修第 3 輪 6：「來源回傳空值、原因未提供」（`44` SET-5 的回空）與真錯誤分開列。
        # `masked_errors` 只放真錯誤，它們就是寫進 `fetch_log.message` 的那幾段字串（同一份）；
        # 回空放 `empty`（該次 `fetch_log` 記 ok、message 為空，畫面自行顯示「回應為空」）。
        empty, masked = {}, {}
        for key, raw in table["errors"].items():
            text = self._mask(str(raw))
            if raw == mi.EMPTY_WITHOUT_REASON and fetched.get(key, 0) == 0:
                empty[key] = text
            else:
                masked[key] = text
        self.persist["masked_errors"] = masked
        self.persist["empty"] = empty
        if self.opened is None:
            return  # begin 失敗或沒呼叫：不寫任何東西（persist 已記原因）
        rows_by_key: dict = {}
        for row in table["rows"]:
            rows_by_key[row["indicator_key"]] = rows_by_key.get(row["indicator_key"], 0) + 1
        reasons = []
        for key, text in masked.items():   # `empty` 不在這裡：`44` SET-5，L1 沒給原因的空不算失敗
            reasons.append(f"{key}: {text}")
        for key, count in fetched.items():
            if count > 0 and rows_by_key.get(key, 0) == 0 and key not in table["errors"]:
                why = "；".join(table.get("skipped", {}).get(key, [])) or "原因未記錄"
                reasons.append(self._mask(f"{key}: 取回 {count} 列，全部未寫入（{why}）"))
        write_failed = None
        try:
            result = store.append_market_indicator(table["rows"], mask=self._mask)
        except store.SettingsSheetError as exc:
            write_failed = exc
            reasons.append(f"market_indicator 寫入失敗：{exc}")
        else:
            self.persist.update(appended=result["appended"],
                                already_present=result["already_present"],
                                conflicts=result["conflicts"])
            if result["conflicts"]:
                reasons.append(self._mask(_conflict_text(result["conflicts"])))
        if reasons:
            outcome, row_count, message = "failed", None, "\n".join(reasons)
        else:
            outcome, row_count, message = "ok", sum(fetched.values()), None
        # 回修第 4 輪 3：與要寫進 `fetch_log.message` 的字串逐字相同；不論下面寫入成敗都放。
        self.persist["log_message"] = message
        try:
            logged = store.close_fetch_log(self.opened, outcome=outcome, row_count=row_count,
                                           message=message, mask=self._mask)
        except store.SettingsSheetError as exc:
            # 不遞迴：不為了「寫 fetch_log 失敗」再寫一筆 fetch_log，只回報。
            self._fail("fetch_log", exc)
            if write_failed is not None:
                self.persist["message"] = f"{write_failed}\n{exc}"
            return
        self.persist["fetch_log"] = logged
        if write_failed is not None:
            self._fail("market_indicator", write_failed)
            return
        self.persist.update(ok=True, stage="done", message=None, error_code=None)


def refetch_cached_functions() -> list:
    """「重新取數」前要清快取的 L1 取數函式（第一階段真的會取數的來源各一支，去重）。
    來源沒有登記在 `_CACHED_FETCHER_BY_SOURCE` → KeyError（新接一個來源卻忘了登記，當場炸）。"""
    out = []
    for spec in mi.INDICATOR_SPECS.values():
        if mi._phase1_of(spec) == "write":
            out.append(_CACHED_FETCHER_BY_SOURCE[spec["source"][0]])
    return list(dict.fromkeys(out))


def refetch_market_indicator(secret_values, *,
                             build: Callable = mi.build_market_indicator_table) -> dict:
    """set 頁「重新取數」（市場指標）：先清本次會用到的 L1 取數函式自己的快取，再照
    `run_market_indicator_fetch` 取數寫表。**不動來源冷卻、不呼叫全域清除**（`50` B9）。
    冷卻中的來源照樣由 L1（`infra.source_backoff`）擋下，不因清了快取就多打一次。"""
    for fetcher in refetch_cached_functions():
        fetcher.cache_clear()
    return run_market_indicator_fetch(secret_values, build=build)


def run_market_indicator_fetch(secret_values, *,
                               build: Callable = mi.build_market_indicator_table) -> dict:
    """set 頁「取數」：寫 `fetch_log_open` → 取數並寫表 → 寫 `fetch_log`。

    回傳 `{"table": build 的回傳（錯誤原文未遮）, "persist": sink.persist}`。
    畫面顯示錯誤請用 `persist["masked_errors"]`（與 `fetch_log.message` 同一份遮蔽後字串）；
    回空（`44` SET-5）另列在 `persist["empty"]`，不是錯誤。
    `fetch_log_open` 寫不進去時仍照常取數（`50` 第 8 節：結果照常顯示），只是不寫表；
    此時 `persist["log_message"]` 為 None，錯誤請讀 `persist["masked_errors"]`（見 `MarketIndicatorSheetSink`）。
    ⚠️ `market_indicator` 寫入時 gspread 上游失敗（會登記冷卻的那一類）時 `fetch_log` 寫不進去（被冷卻擋下）；
    標頭不符等不登記冷卻的失敗則照常寫出 `failed`。見檔頭 outcome 段的更正。
    """
    sink = MarketIndicatorSheetSink(secret_values)
    sink.begin()
    table = build(sink=sink)
    return {"table": table, "persist": sink.persist}
