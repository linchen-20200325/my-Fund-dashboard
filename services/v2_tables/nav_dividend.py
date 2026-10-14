# -*- coding: utf-8 -*-
"""持倉體檢（hld）要讀的 `nav`、`dividend` 兩張表：L1 `*_with_error` 回傳 → `44` 4.2／4.3 表列。

ui_v2 只經由 `ui_v2/<頁>/source.py` 碰到本檔（`49` §3.3 方案 A）。**本輪不接任何 UI。**

依據（逐條出處）：
- 客戶裁示 Q12＝A：資料不另外存，每次開頁即時抓。快取只在 L1（`fetch_nav`／`fetch_div` 掛
  `infra/cache.py::_daily_cache`，以台灣日曆日為界），本檔**不另疊快取**（`49` §4.4）、**不寫任何試算表**、
  ~~**不讀 `services/nav_history_gs.py` 的累積序列**（那是「保留歷史」，另一輪處理）。~~
  → **2026-10-13 狀態更新（有意識的變更，不是漏刪；依據：客戶 2026-10-13 裁示「B 線復用 repo 現有的多來源
  淨值取數鏈」＋總管同日技術裁定）**：淨值改走 A 鏈 `services.moneydj_fetcher.auto_fetch_moneydj`
  （來源、優先序、頁型迴圈、停止條件一個不改），A 鏈本來就會併入累積表 → 本檔照實收下，**逐點分辨**
  本次取得與累積表舊點（`_rows_with_history`），舊點的 `fetched_at` 取該點的 `recorded_at`，不冒充本次取得。
  舊句在寫下當時為真（當時只呼叫 L1 `fetch_nav`）；被推翻的是它的前提。仍然**不另疊快取、不寫任何試算表**。
- `49` §2.6 / §6.2 T3（幣別）：
  - `nav.ccy`：收**來源自報**的幣別（L1 序列 `attrs["currency"]`），或**持倉列的使用者手填幣別**
    （呼叫端傳入 `holding_ccy`；該欄語意就是計價幣別）。**預設值、名稱推測值一律不收**；
    兩者都沒有 → 該檔淨值整批不寫；兩者都有但不同 → 不猜哪個對，整批不寫。
    ⚠️ `fetch_nav` 目前**從不**自報幣別，所以實務上 `nav.ccy` 只會來自持倉列。
    → 2026-10-13 起走 A 鏈：A 鏈回的幣別（結果的 `currency`、序列 attrs 的 `currency`）**一律不採用**
      （可能是硬編表、推定值或來源預設值，分不出是不是來源自報；總管技術裁定第 5 條），`nav.ccy` 只來自持倉列。
  - `dividend.ccy`：**只收來源自報**，不沿用持倉列的幣別（配息幣別可能與計價幣別不同）。
    `fetch_div` 回傳的每一筆只有 `date`、`amount`、`source`、`fetched_at`，**沒有幣別** ⇒
    走 MoneyDJ 的基金配息一列都寫不進去（`49` §2.6；客戶 Q5 已知悉）。
    → 2026-10-13 狀態更新（有意識的更正，不是漏刪；客戶同日裁示「幣別規則與淨值相同」）：上面兩句只對舊的
      `build_dividend_table`（`fetch_div`）仍然為真。A 鏈那一支（`rows_from_chain_dividends`）：來源**仍必須自報**
      （沒宣告 → 不寫，`49` T3 的要求不變），自報值與持倉手填意思相同才寫、**標籤用持倉手填**；不同或認不出 → 整檔不寫。
  - 2026-10-14 C3a（客戶已裁示：淨值與配息幣別可以用 MoneyDJ／TDCC／FundClear 自報的幣別，要標明來源；
    與淨值資料不一 → ⬜）：標籤除了持倉手填（`holding_ccy`），也可以改吃 **meta 頁自報**（`declared_ccy` ＋
    `declared_ccy_source`；同一次呼叫只能一種）。判斷規則完全相同，只換出處字串（`ccy_source`）與文案字樣；
    持倉手填那一支（hld）的輸出與 C3a 之前逐位元組相同。exp 之後才會接上，本輪沒有呼叫端。見 `LABEL_SOURCE_HOLDING`。
- `49` §2.6 / Q5：`div_kind` 一律 `unknown`（來源沒有收益／本金區分）；`pay_date` 來源不給 → 空值。
- `49` §2.2：`fetch_div` 的 `date` **是不是除息日，`49` 沒有查頁面欄位語意**。本檔把它寫進 `ex_date`
  之前需要先確認 ⇒ `DIV_DATE_IS_EX_DATE_VERIFIED`（預設 False）。未確認前**不取數、不寫列**
  （體例同 `market_indicator.FX_OBS_DATE_RULE_VERIFIED`：取回來也寫不進去，只會多打來源）。
- `49` §2.8 / §4.3（舊資料不得冒充新資料）：`fetch_nav` 即時網址全敗、退回預存舊序列那一支
  （`attrs["source"]` 以 `GitHubActions:cache/nav/` 開頭，或 `attrs` 帶 `nav_quality`）：
  `fetched_at` **改取 `attrs["cache_updated_at"]`**（該支的 `attrs["fetched_at"]` 是讀檔當下，不是取得時間）；
  沒有 `cache_updated_at` 就整批不寫。過期與否看 `nav_quality["stale"]`（不看 `supports_annualized`），
  記在 `provenance`，**不寫進 `is_estimated`**（預存序列的值是真的公布淨值，不是推估值）。
- `CLAUDE.md` §1：週末、假日、停止交易日沒有列是正常狀態 —— 本檔**只轉 L1 給的日期**，
  不補列、不 ffill、不以 0 補；非有限值、非正淨值、負配息、同一主鍵兩個不同值 → 不寫該列並計數。

**provenance**：`44` 的 `nav`／`dividend` 兩表**沒有 `source` 欄**（`nav` 只有 `source_tier`）。
本檔不自創欄名；每一列照 `44` 帶 `fetched_at`，來源字串（L1 的 `attrs["source"]`／每筆的 `source`）、
幣別出處與舊序列旗標放在回傳的 `provenance[fund_code]`（每檔一次 L1 呼叫，同一檔的列共用同一個來源）。

**錯誤**：L1 失敗原文逐字放進 `errors[fund_code]`；L1 拋例外時放 `型別名: 訊息`（不吞）。
本層**不遮蔽**；遮蔽在寫出點做一次（同 `market_indicator`；`ui_v2/<頁>/source.py` 呼叫 `masking`）。

**基金代碼 → MoneyDJ `full_key`**：`49` §2.2 記載「Sheets 的 `fund_code` 能不能直接當 `full_key` 用，
本組沒有查」。本檔不猜：呼叫端**必須**明確給 `full_key`，本檔原樣交給 L1。
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import pandas as pd

from repositories.fund import fund_orchestration, nav_metrics
from repositories.fund.fund_orchestration import NAV_SOURCE_FAILURES_KEY, _NAV_NON_NATIVE_PREFIXES
from repositories.fund.fund_orchestration import (   # 2026-10-13 配息移交：A 鏈的配息總結（新增鍵）
    DIV_OUTCOME_FAILED, DIV_OUTCOME_NONE, DIV_OUTCOME_ROWS, DIVIDENDS_OUTCOME_KEY,
)
from repositories.fund.sources import (
    MS_SECID_FROM_CODE_SEARCH, MS_SECID_FROM_NAME_SEARCH, MS_SECID_ORIGIN_ATTR,
)
from repositories.fund.sources import (   # 2026-10-13 配息移交：三個配息解析器的解析依據（新增鍵）
    DIV_PARSER_CNYES, DIV_PARSER_FUNDCLEAR, DIV_PARSER_TCB, DIV_PROVENANCE_KEY, DIV_STATUS_ROWS,
    _normalize_declared_ccy, div_dropped_total,
)
from repositories.fund.nav_metrics import LIVE_FETCH_ERROR_ATTR, fetch_div_with_error
# 2026-10-13 客戶裁示：B 線復用既有多來源淨值鏈（A 鏈）。這是本目錄唯一一個 L2→L2 import，
# 守衛（`tests/test_v2_tables_market_indicator.py`）只對本檔、只放行這一個模組名（總管同日技術裁定第 1 條）。
from services.moneydj_fetcher import NAV_ATTEMPTS_KEY, auto_fetch_moneydj, nav_history_shared_reads
from services.v2_tables import contract
from services.v2_tables.market_indicator import EMPTY_WITHOUT_REASON


SOURCE_TIER_NAV = "淨值"           # `44` 值域四個之一
DIV_KIND_UNKNOWN = "unknown"       # Q5

# `49` §2.2：`fetch_div` 的 `date` 欄語意未查證（是不是除息日）。確認之前不取數、不寫列。
# ⚠️ 確認是除息日，才可以只改這一處；若其實是入帳日或公告日，要先改對照規則。
# 📌 2026-10-13 射程更正（有意識的更正，不是漏刪；客戶同日裁示 B 線配息改走 A 鏈）：本開關**只管舊的
# `build_dividend_table`（L1 `fetch_div` 那一支）**，維持 False —— 依 `_src_tcb_div` 自己的欄位註解，合庫頁第一欄是
# 「配息基準日」，而 `fetch_div` 把第一欄當日期、也不回報幣別（查證見 `DIV_EX_DATE_EVIDENCE` 上方）。
# B 線現行配息走 A 鏈，改用**逐來源**的判定 `DIV_EX_DATE_EVIDENCE`，不再有總開關。
DIV_DATE_IS_EX_DATE_VERIFIED = False

# 2026-10-13 總管技術裁定（稽核 5 殘留缺口，fail closed；體例同 `DIV_DATE_IS_EX_DATE_VERIFIED`）：
# 累積表（nav_history）的點不帶出處 —— `backfill_to_gs` 經 `_clean(raw)` 丟掉 attrs 後以 `source="backfill"`
# 寫入、`nav_history_hook` 以 `source="app"` 寫入，都沒有記 secId 從哪裡來；A 鏈以名稱或代碼搜尋得來的
# 晨星點會以「無出處的累積點」回到 B 線，B 線對 `secid_origin` 的拒收擋不住這一路。
# 客戶裁示之前：閘門關閉 → `nav_history_dates` 標出的累積點一律不寫；同一天即時值已蓋過的點本來就是即時值，照寫；
# 只剩累積點、沒有即時點的檔整檔不寫，記即時失敗原文。⚠️ 只在客戶裁示後才可以改這一處。
NAV_HISTORY_PROVENANCE_VERIFIED = False
TEXT_HISTORY_NOT_READ = "閘門關閉，本次未讀累積表"
TEXT_HISTORY_GATE_CLOSED = ("累積序列的出處不可考（可能含以名稱搜尋得來的資料），依規則暫不採用，待客戶裁示；"
                            "累積表 {n} 筆不寫")

# 退回預存舊序列的辨識（`49` §2.8）。
CACHE_FALLBACK_SOURCE_PREFIX = "GitHubActions:cache/nav/"

# ── 合理性門檻（第二輪回修 3；具名常數）──────────────────────────
# `nav_date`／`ex_date` 早於此日 → 不寫（L1 補年份或解析失準時常見的假日期，例：0001-09-18、1970-01-01）。
MIN_VALID_DATE = date(1900, 1, 1)
# 「未來日期」以台灣的日曆日判定：L1 以台灣日期建索引，台灣日期可能比世界協調時間的日期早一天進位。
# 晚於「當下的台灣日期」→ 不寫。
MARKET_DATE_TZ = timezone(timedelta(hours=8))
# `fetched_at`／`cache_updated_at` 晚於當下超過此秒數 → 不寫（取得時間不可能在未來）。
# 容差 300 秒（第三輪小修）：預存舊序列的 `cache_updated_at` 由另一台機器（GitHub Actions）寫入，
# 兩台機器的時鐘可能有偏差；L1 即時那一支的 `fetched_at` 也可能與本機時鐘有些微落差。
# 剛好晚 300 秒 → 收（邊界含在容差內）；晚 301 秒 → 拒收。nav 與 dividend 共用。
# ⚠️ 只放寬取得時間；`nav_date`／`ex_date` 的「晚於當下的台灣日期」判斷不受影響。
FETCHED_AT_MAX_FUTURE_SEC = 300

# 整檔不寫列的原因代碼（`withheld`）；L3 依代碼對照畫面文案（文案未定，屬草稿事項）。
WITHHELD_CCY_MISSING = "ccy_missing"                       # nav：來源沒自報、持倉也沒填
WITHHELD_CCY_CONFLICT = "ccy_conflict"                     # nav：來源自報與持倉手填（或手填之間）意思不同
WITHHELD_CCY_NOT_SOURCE_REPORTED = "ccy_not_source_reported"  # dividend：來源沒自報幣別
WITHHELD_FETCHED_AT_MISSING = "fetched_at_missing"         # 取不到真的取得時間（缺、格式不符、沒有時區）
WITHHELD_FETCHED_AT_FUTURE = "fetched_at_in_future"        # 取得時間晚於當下
WITHHELD_INPUT_CONFLICT = "input_conflict"                 # 同一檔基金給了互相矛盾的輸入
# 刻意不取數的原因代碼（`pending`，語意同 `market_indicator` 的 `pending`）。
PENDING_DIV_DATE_SEMANTICS = "div_date_semantics_unverified"

_PENDING_DIV_TEXT = (
    "fetch_div 的 date 欄是不是除息日尚未查證（49 §2.2）；確認之前不取數、不寫列"
    "（DIV_DATE_IS_EX_DATE_VERIFIED）"
)
# L1 回傳型別不對時寫進 `errors` 的前綴（第二輪回修 4）。
TYPE_ERROR_PREFIX = "L1 回傳型別不符"

# ── 幣別標籤的出處（2026-10-14 C3a；客戶已裁示：淨值與配息幣別可以用 MoneyDJ／TDCC／FundClear 自報的幣別，
# 要標明來源；與淨值資料不一 → ⬜）──────────────────────────────────────────────
# 標籤可以來自兩種輸入之一（同一次呼叫只能一種，混用 → ValueError，見 `_group_funds`）：
# - 持倉列手填（`holding_ccy`；hld 現行路徑）：`label_source` ＝ `LABEL_SOURCE_HOLDING`（預設值），
#   輸出與 C3a 之前逐位元組相同（`tests/test_nav_dividend_golden_c3a.py`）；
# - meta 頁自報（`declared_ccy` ＋ `declared_ccy_source`，例 `"meta:MoneyDJ+TDCC"`；exp 之後才會接上）：
#   `label_source` ＝ 呼叫端給的 `declared_ccy_source` 原值，原樣寫進 `provenance["ccy_source"]`。
# 判斷規則（衝突、缺值、序列／配息宣告的幣別與標籤不同 → 扣下）兩種輸入完全相同，只換文案字樣與出處字串。
LABEL_SOURCE_HOLDING = "holding_user_input"
# ⚠️ meta 路徑的使用者可見字樣「來源自報（<來源>）」是計算服務組 C3a 的**暫定字面**，exp 接上時另行送審；
# `<來源>` 取 `declared_ccy_source` 去掉 `META_SOURCE_PREFIX` 前綴後的原文（例 `meta:MoneyDJ+TDCC` → `MoneyDJ+TDCC`）。
TEXT_LABEL_DECLARED = "來源自報（{source}）"
META_SOURCE_PREFIX = "meta:"


def _label_words(label_source) -> dict:
    """依標籤出處決定使用者可見文案的字樣。預設（持倉手填）的字樣與 C3a 之前逐字相同。
    - `row`／`input`：hld 原文的「持倉列」「持倉手填」；meta 一律是「來源自報（<來源>）」。
    - `series`：`resolve_nav_ccy` 指稱淨值序列自報值的主詞（hld 原文是「來源」；meta 改「淨值序列」，
      免得與「來源自報（…）」混成同一個詞）。
    - `side`：衝突說明裡標籤那一側的標記（hld 原文 `holding`）。"""
    if label_source == LABEL_SOURCE_HOLDING:
        return {"row": "持倉列", "input": "持倉手填", "series": "來源", "side": "holding"}
    text = str(label_source)
    if text.startswith(META_SOURCE_PREFIX):
        text = text[len(META_SOURCE_PREFIX):]
    shown = TEXT_LABEL_DECLARED.format(source=text)
    return {"row": shown, "input": shown, "series": "淨值序列", "side": "declared"}


# ───────────────────────── 小工具 ─────────────────────────

def _now_utc(now) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError(f"now 須為帶時區的 datetime（{now!r}）")
    return now.astimezone(timezone.utc)


def _parse_aware(value) -> Optional[datetime]:
    """時間字串 → 帶時區的 datetime；取不到、格式不符、沒有時區回 None。"""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def _utc_iso(value) -> Optional[str]:
    """時間字串 → 世界協調時間 ISO 字串（同一瞬間，一律 `+00:00` 形式）；取不到回 None。"""
    parsed = _parse_aware(value)
    if parsed is None:
        return None
    return parsed.astimezone(timezone.utc).isoformat()


def _fetched_at_check(value, now_utc: datetime):
    """回 `(utc_iso 或 None, withheld 代碼或 None, 理由或 None)`。"""
    parsed = _parse_aware(value)
    if parsed is None:
        return None, WITHHELD_FETCHED_AT_MISSING, "取不到、格式不符或沒有時區"
    if (parsed - now_utc).total_seconds() > FETCHED_AT_MAX_FUTURE_SEC:
        return None, WITHHELD_FETCHED_AT_FUTURE, f"晚於當下（{value!r}）"
    return parsed.astimezone(timezone.utc).isoformat(), None, None


def _iso_ccy(value) -> Optional[str]:
    """ISO 4217 三個大寫英文字母才收；其他（含小寫、空白、None）一律 None，不改寫、不猜。"""
    if isinstance(value, str) and len(value) == 3 and all("A" <= ch <= "Z" for ch in value):
        return value
    return None


def _ccy_meaning(value):
    """只用來**比對**意思是否相同（去空白、大寫化）；寫入一律用原值。非字串回 `("?", repr)`。"""
    if isinstance(value, str):
        text = value.strip().upper()
        return text or None
    return ("?", repr(value))


def _is_bool(value) -> bool:
    """bool 與 numpy bool 都不算數字（`float(True)` 會變成 1.0）。"""
    return pd.api.types.is_bool(value)


def _call(fetch, *args):
    """呼叫 L1 `*_with_error`；回 `(值, 錯誤)`。

    - L1 拋例外 → `(None, '型別名: 訊息')`，不吞。
    - L1 回的不是二元組 → `(None, TYPE_ERROR_PREFIX…)`：只讓這一檔進 errors，不讓整批中斷。
    """
    try:
        result = fetch(*args)
    except Exception as exc:  # noqa: BLE001 —— 轉成可見的失敗原文，不是吞掉
        return None, f"{type(exc).__name__}: {exc}"
    if not isinstance(result, tuple) or len(result) != 2:
        return None, f"{TYPE_ERROR_PREFIX}：預期 (值, 錯誤) 二元組，收到 {type(result).__name__}"
    return result


def _is_blank_ccy(value) -> bool:
    """持倉幣別「沒有填」：None、float nan、`pd.NA`、`pd.NaT` 這類缺值（第三輪小修 2）。
    不參與衝突判斷、不參與去重（NaN != NaN，放進清單會去重失敗）。字串一律不算缺值。"""
    if value is None:
        return True
    if isinstance(value, str):
        return False
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):   # 陣列等非純量：不是「沒填」，留給 resolve 判成衝突或缺
        return False


def _group_funds(funds, *, chain: bool = False):
    """輸入 → `{fund_code: {"full_key", "portal", "holding_ccys": list, "label_source": str}}` 與
    `{fund_code: 矛盾說明}`。

    同一檔基金掛在多張保單下是常態，取數只做一次；但 `full_key`／`portal` 不一致就不猜。
    `holding_ccys` 收集所有持倉列的手填幣別原值（含不合格式的值，交給 `resolve_nav_ccy` 判斷）。

    2026-10-14 C3a：每一筆也可以改給 `declared_ccy`（meta 頁自報的幣別原值）＋ `declared_ccy_source`
    （出處字串，例 `"meta:MoneyDJ+TDCC"`）。此時 `holding_ccys` 收的是 `declared_ccy` 的原值（鍵名沿用，
    判法完全相同），`label_source` ＝ `declared_ccy_source`；沒給就是 `LABEL_SOURCE_HOLDING`。
    - 同一次呼叫裡同時出現 `holding_ccy` 與 `declared_ccy`（或 `declared_ccy_source`）→ `ValueError`（不混用：
      同一張表的標籤出處只能是一種，否則畫面分不出哪一列的幣別是誰說的）。
    - `declared_ccy_source` 不是前後無空白的非空字串、或等於 `LABEL_SOURCE_HOLDING` → `ValueError`（不猜出處）。
    - 同一檔基金的 `declared_ccy_source` 不同 → 該檔列為輸入矛盾（同 `full_key` 不一致）。
    """
    grouped, conflicts = {}, {}
    modes = set()
    for item in funds:
        code = item.get("fund_code")
        if not isinstance(code, str) or not code.strip() or code != code.strip():
            raise ValueError(f"fund_code 須為前後無空白的非空字串（{code!r}）")
        full_key = item.get("full_key")
        if not isinstance(full_key, str) or not full_key.strip():
            raise ValueError(f"{code}：full_key 須由呼叫端明確給出（{full_key!r}）；本檔不猜代碼對照")
        if full_key != full_key.strip():
            raise ValueError(f"{code}：full_key 前後帶空白（{full_key!r}）；本檔不偷偷去掉")
        portal = item.get("portal", "") or ""
        chain_code = item.get("chain_code") if chain else None   # 配息（另一批）不經 A 鏈，不看這一欄
        if chain and (not isinstance(chain_code, str) or not chain_code.strip()
                      or chain_code != chain_code.strip()):
            raise ValueError(f"{code}：chain_code（交給 A 鏈的代碼，`fund_keys` 的 parsed_code）須由呼叫端"
                             f"明確給出、前後無空白（{chain_code!r}）；本檔不猜代碼對照")
        declared = "declared_ccy" in item or "declared_ccy_source" in item
        if "holding_ccy" in item:
            modes.add("holding_ccy")
        if declared:
            modes.add("declared_ccy")
        if len(modes) > 1:
            raise ValueError(f"{code}：同一次呼叫同時給了 holding_ccy 與 declared_ccy；"
                             f"幣別標籤只能來自其中一種，本檔不混用")
        label_source = LABEL_SOURCE_HOLDING
        if declared:
            label_source = item.get("declared_ccy_source")
            if (not isinstance(label_source, str) or not label_source.strip() or label_source != label_source.strip()
                    or label_source == LABEL_SOURCE_HOLDING):
                raise ValueError(f"{code}：declared_ccy_source 須為前後無空白的非空字串、且不得是 "
                                 f"{LABEL_SOURCE_HOLDING!r}（{label_source!r}）；本檔不猜幣別出處")
        entry = grouped.setdefault(code, {"full_key": full_key, "portal": portal, "chain_code": chain_code,
                                          "holding_ccys": [], "label_source": label_source})
        if entry["full_key"] != full_key or entry["portal"] != portal or entry["chain_code"] != chain_code:
            conflicts[code] = (f"同一檔基金給了不同的 full_key／portal／chain_code："
                               f"({entry['full_key']!r}, {entry['portal']!r}, {entry['chain_code']!r}) vs "
                               f"({full_key!r}, {portal!r}, {chain_code!r})")
        elif entry["label_source"] != label_source:
            conflicts[code] = (f"同一檔基金給了不同的 declared_ccy_source："
                               f"{entry['label_source']!r} vs {label_source!r}")
        ccy_key = "declared_ccy" if declared else "holding_ccy"
        if ccy_key in item and not _is_blank_ccy(item[ccy_key]):
            if item[ccy_key] not in entry["holding_ccys"]:
                entry["holding_ccys"].append(item[ccy_key])
    return grouped, conflicts


def _check_rows_order(rows, fields, table):
    names = [name for name, _k, _n in fields]
    for row in rows:  # 出口前再核一次欄位與順序；不該發生，發生就是本檔的 bug（§1：當場炸）
        if list(row) != names:
            raise AssertionError(f"{table} 列的欄位與契約不符：{list(row)}")


def _date_bounds_reason(day: date, today_market: date) -> Optional[str]:
    if day < MIN_VALID_DATE:
        return f"早於 {MIN_VALID_DATE.isoformat()}"
    if day > today_market:
        return f"晚於當下的台灣日期 {today_market.isoformat()}"
    return None


def _date_value(value):
    """日期值 → `(YYYY-MM-DD 或 None, 不收的理由或 None)`。

    只收三種（第二輪回修必修 1）：`pd.Timestamp`（無時區、非 NaT）、`datetime.date`（不含
    `datetime.datetime`，那一種日期語意要看時刻）、恰好 `YYYY-MM-DD` 的字串。
    整數、`RangeIndex`、"Sep 18"、"09/10/2026" 一律不收 —— 不交給 pandas 去猜。
    """
    if value is pd.NaT:
        return None, "日期是 NaT"
    if isinstance(value, pd.Timestamp):
        if value.tzinfo is not None:
            return None, "帶時區、日期語意不明"
        return value.date(), None
    if isinstance(value, datetime):
        return None, "是 datetime（不是 pd.Timestamp 或 date），日期語意不明"
    if isinstance(value, date):
        return value, None
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            return None, "字串不是 YYYY-MM-DD"
        if parsed.isoformat() != value:
            return None, "字串不是 YYYY-MM-DD"
        return parsed, None
    return None, f"型別不是日期（{type(value).__name__}）"


def _dated(value, today_market: date):
    """`_date_value` 再加上下限檢查 → `(YYYY-MM-DD 或 None, 理由或 None)`。"""
    day, why = _date_value(value)
    if day is None:
        return None, why
    why = _date_bounds_reason(day, today_market)
    if why:
        return None, why
    return day.isoformat(), None


def _tally(counter: dict, reason: str, n: int = 1) -> None:
    counter[reason] = counter.get(reason, 0) + n


def _tally_lines(counter: dict, what: str) -> list:
    return [f"{what}{reason} {n} 筆不寫" for reason, n in counter.items()]


# ───────────────────────── nav ─────────────────────────

def resolve_nav_ccy(source_ccy, holding_ccys, *, label_source=LABEL_SOURCE_HOLDING):
    """`49` T3：`nav.ccy` 的取值。回 `(ccy, ccy_source, withheld_code, reason)`。

    - `label_source`（2026-10-14 C3a）：`holding_ccys` 這一側的出處（預設持倉手填）。採用這一側的值時
      `ccy_source` 就回它；文案字樣依它決定（`_label_words`），判法不變。

    - 合格（ISO 4217）的值寫入時一律用**原值**，不改寫。
    - 衝突判定（第二輪回修必修 2）：把來源自報與每一個持倉手填值**去空白、大寫化後**比意思；
      意思不只一種 → `ccy_conflict`（含「格式不對的值與合格的值意思不同」，例 `twd` vs `USD`、
      來源 `eur`／`EUR ` vs 持倉 `USD`）。非字串的值（例 840）意思無從比對，只要旁邊有別的值就當作衝突。
    - 意思相同時取合格的那一個（例 `usd` 與 `USD` 並存 → `USD`，出處記合格值那一方）。
    - 只有不合格式的值、沒有合格值 → `ccy_missing`（維持原判法：不改大小寫、不猜）。
    """
    # 缺值＝沒填（第三輪小修 2）。來源那一側的缺值必須在 append 之前先歸成 None（第四輪小修 1），
    # 否則 NaN 會帶著 ("?", 'nan') 的意思進衝突判斷。
    if _is_blank_ccy(source_ccy):
        source_ccy = None
    holding_ccys = [c for c in holding_ccys if not _is_blank_ccy(c)]
    provided = []
    if source_ccy is not None:
        provided.append(("source", source_ccy))
    words = _label_words(label_source)
    provided.extend((words["side"], c) for c in holding_ccys)
    meanings = {_ccy_meaning(v) for _side, v in provided} - {None}
    if len(meanings) > 1:
        shown = ", ".join(f"{side}:{v!r}" for side, v in provided)
        return None, None, WITHHELD_CCY_CONFLICT, f"幣別意思不一致（{shown}）"
    source = _iso_ccy(source_ccy)
    holding = next((c for c in holding_ccys if _iso_ccy(c)), None)
    if source:
        return source, "source_reported", None, None
    if holding:
        return holding, label_source, None, None
    detail = []
    if source_ccy is not None:
        detail.append(f"{words['series']}自報值不合 ISO 4217：{source_ccy!r}")
    bad = [repr(c) for c in holding_ccys if not _iso_ccy(c)]
    if bad:
        detail.append(f"{words['row']}幣別不合 ISO 4217：{', '.join(bad)}")
    reason = (f"{words['series']}未自報幣別、{words['row']}也沒有可用的幣別"
              + (f"（{'；'.join(detail)}）" if detail else ""))
    return None, None, WITHHELD_CCY_MISSING, reason


def _empty_out():
    return {"rows": [], "error": None, "withheld": None, "skipped": [], "fetched": 0,
            "skipped_rows": 0, "provenance": None}


class ReconcileError(AssertionError):
    """核帳不平：本檔計數的 bug（不是資料問題）。"""


def _reconcile(out, skipped_rows: int, table: str):
    """核帳（第三輪小修 3）：寫出的列數＋略過與合併的筆數＝L1 取回的筆數。
    對不上就是本檔的計數 bug（§1：當場炸，不交出一份帳對不上的結果）。"""
    out["skipped_rows"] = skipped_rows
    if len(out["rows"]) + skipped_rows != out["fetched"]:
        raise ReconcileError(f"{table} 核帳不平：rows {len(out['rows'])} ＋ skipped {skipped_rows}"
                             f" ≠ fetched {out['fetched']}")
    return out


def rows_from_nav_series(fund_code: str, series, error, *, holding_ccys=(), now=None,
                         label_source=LABEL_SOURCE_HOLDING) -> dict:
    """單一檔基金的 L1 淨值序列 → `{rows, error, withheld, skipped, fetched, provenance}`（純函式）。

    `error` 非空：原文照回、不寫列。`series` 不是 `pd.Series`（含 None）：型別錯誤進 `error`。
    空序列又沒有原因：回 `EMPTY_WITHOUT_REASON`、不寫列。`now`：判「未來」用的當下（測試注入）。
    `label_source`（2026-10-14 C3a）：`holding_ccys` 的出處（預設持倉手填；meta 路徑見 `_group_funds`），
    一路帶到幣別閘、累積表各段與 `resolve_nav_ccy`；只影響文案字樣與 `ccy_source`，不影響判斷。
    """
    out = _empty_out()
    if error:
        out["error"] = str(error)
        return out
    if not isinstance(series, pd.Series):
        out["error"] = f"{TYPE_ERROR_PREFIX}：預期 pd.Series，收到 {type(series).__name__}"
        return out
    if len(series) == 0:
        out["error"] = EMPTY_WITHOUT_REASON
        return out
    attrs = dict(series.attrs or {})
    if CHAIN_ATTR in attrs:
        blocked = _chain_ccy_gate(fund_code, series, attrs, holding_ccys, label_source=label_source)
        if blocked is not None:
            _add_chain_provenance(blocked, attrs)
            return blocked
    if any(key in attrs for key in _HISTORY_MARKERS):
        out = _rows_with_history(fund_code, series, attrs, holding_ccys=holding_ccys, now=now,
                                 label_source=label_source)
    else:
        out = _rows_from_segment(fund_code, series, holding_ccys=holding_ccys, now=now, label_source=label_source)
    _add_chain_provenance(out, attrs)
    return out


def _rows_from_segment(fund_code: str, series, *, holding_ccys=(), now=None,
                       label_source=LABEL_SOURCE_HOLDING) -> dict:
    """同一個來源、同一個取得時間的一段序列 → `{rows, error, withheld, skipped, fetched, provenance}`。
    （2026-10-13 前即 `rows_from_nav_series` 的本體，一字未改，只抽出來讓累積表那幾段共用。）"""
    out = _empty_out()
    now_utc = _now_utc(now)
    today_market = now_utc.astimezone(MARKET_DATE_TZ).date()
    out["fetched"] = len(series)
    attrs = dict(series.attrs or {})
    source = attrs.get("source")
    fallback = (isinstance(source, str) and source.startswith(CACHE_FALLBACK_SOURCE_PREFIX)) \
        or "nav_quality" in attrs
    quality = attrs.get("nav_quality") if isinstance(attrs.get("nav_quality"), dict) else {}
    stale = quality.get("stale") if fallback else None
    at_field = "cache_updated_at" if fallback else "fetched_at"
    fetched_at, at_code, at_why = _fetched_at_check(attrs.get(at_field), now_utc)

    ccy, ccy_source, withheld, why = resolve_nav_ccy(attrs.get("currency"), holding_ccys, label_source=label_source)
    # `live_error`（2026-10-09 客戶裁示 M-1 採 A）：退回預存舊序列時，L1 交出的本次即時網址失敗原文
    # （未遮蔽）；不是預存那一支 → None。只供 set 頁淨值層重新取數判失敗用；hld 不讀它，列照常寫。
    live_error = attrs.get(LIVE_FETCH_ERROR_ATTR) if fallback else None
    out["provenance"] = {"source": source, "fetched_at": fetched_at, "ccy_source": ccy_source,
                         "cache_fallback": bool(fallback), "stale": stale,
                         "live_error": None if live_error is None else str(live_error)}
    if withheld:
        out["withheld"] = withheld
        out["skipped"].append(f"{why}，{len(series)} 筆全部不寫")
        return _reconcile(out, len(series), "nav")
    if fetched_at is None:
        out["withheld"] = at_code
        lead = "退回預存舊序列，但 cache_updated_at " if fallback else "L1 回傳的 fetched_at "
        out["skipped"].append(f"{lead}{at_why}，{len(series)} 筆全部不寫（不以當下時間補）")
        return _reconcile(out, len(series), "nav")

    date_bad: dict = {}
    by_day: dict = {}
    for stamp, value in series.items():
        day, why = _dated(stamp, today_market)
        if day is None:
            _tally(date_bad, why)
            continue
        by_day.setdefault(day, []).append(value)

    value_bad: dict = {}
    collateral = conflicting = not_positive = contract_bad = merged = 0
    for day in sorted(by_day):
        valid = []
        invalid = 0
        for value in by_day[day]:
            if _is_bool(value):
                _tally(value_bad, "是布林值（不算數字）")
                invalid += 1
                continue
            try:
                number = float(value)
            except OverflowError:
                _tally(value_bad, "數值溢位（超出浮點範圍）")
                invalid += 1
                continue
            except (TypeError, ValueError):
                _tally(value_bad, "無法轉成數字")
                invalid += 1
                continue
            if not math.isfinite(number):
                _tally(value_bad, "非有限數值")
                invalid += 1
                continue
            valid.append(number)
        if invalid:
            collateral += len(valid)      # 原規則：同一日有無效值，該日整天不寫
            continue
        if len(set(valid)) > 1:
            conflicting += len(valid)     # 同一主鍵兩個不同值：不猜哪個對，該日全部不寫
            continue
        number = valid[0]
        if number <= 0:
            not_positive += len(valid)
            continue
        row = {
            "fund_code": fund_code,
            "nav_date": day,
            "nav_orig_ccy": number,
            "ccy": ccy,
            "source_tier": SOURCE_TIER_NAV,
            "is_estimated": False,        # 來源給的是公布淨值；預存舊序列另記在 provenance
            "fetched_at": fetched_at,
        }
        if contract.nav_row_problems(row):
            contract_bad += len(valid)
            continue
        merged += len(valid) - 1          # 同日同值：主鍵只留一列
        out["rows"].append(row)

    out["skipped"].extend(_tally_lines(date_bad, "日期："))
    out["skipped"].extend(_tally_lines(value_bad, "淨值"))
    if collateral:
        out["skipped"].append(f"同一日期另有無效淨值，連帶 {collateral} 筆有效值不寫")
    if not_positive:
        out["skipped"].append(f"淨值不大於 0 {not_positive} 筆不寫")
    if conflicting:
        out["skipped"].append(f"同一日期出現不同淨值 {conflicting} 筆不寫")
    if contract_bad:
        out["skipped"].append(f"不符欄位契約 {contract_bad} 筆不寫")
    if merged:
        out["skipped"].append(f"同日同值合併 {merged} 筆")
    total = (sum(date_bad.values()) + sum(value_bad.values()) + collateral + not_positive
             + conflicting + contract_bad + merged)
    return _reconcile(out, total, "nav")


# ───────────────────────── 累積表併入點（2026-10-13 總管技術裁定第 4 條）─────────────────────────

# A 鏈 `services/fund_service.py::_merge_nav_history_series` 在合併後序列上留下的 attrs 鍵（該函式是唯一寫入點）。
HISTORY_MERGED_ATTR = "nav_history_merged"
HISTORY_DATES_ATTR = "nav_history_dates"
HISTORY_RECORDED_AT_ATTR = "nav_history_recorded_at"
HISTORY_SOURCE_ATTR = "nav_history_source"
HISTORY_DATES_ERROR_ATTR = "nav_history_dates_error"
HISTORY_CURRENCY_ATTR = "nav_history_currency"            # {日期: 累積表該點宣告的幣別原值}
HISTORY_LIVE_CURRENCY_ATTR = "nav_history_live_currency"  # 併入前 live 那一段宣告的幣別原值
_HISTORY_MARKERS = (HISTORY_MERGED_ATTR, HISTORY_DATES_ATTR, HISTORY_DATES_ERROR_ATTR)
_HISTORY_ATTRS = (*_HISTORY_MARKERS, HISTORY_RECORDED_AT_ATTR, HISTORY_SOURCE_ATTR, HISTORY_CURRENCY_ATTR,
                  HISTORY_LIVE_CURRENCY_ATTR)

# 本檔轉接 A 鏈時掛在序列上的 attrs 鍵（`fetch_nav_chain_with_error` 是唯一寫入點）。
CHAIN_ATTR = "v2_chain"                              # {"page_type", "data_source", "fetched_at_from"}
CHAIN_FAILURES_ATTR = "v2_chain_failures"            # 各頁型、各來源沒採用的原文（未遮蔽）
CHAIN_HIST_READ_ERROR_ATTR = "v2_nav_history_read_error"   # 本次讀累積表失敗的原文（未遮蔽）
CHAIN_DECLARED_CCY_ATTR = "v2_declared_ccy"          # live 那一段序列自己宣告的幣別原值（不當標籤，只拿來比對）
_CHAIN_ATTRS = (CHAIN_ATTR, CHAIN_FAILURES_ATTR, CHAIN_HIST_READ_ERROR_ATTR, CHAIN_DECLARED_CCY_ATTR)

LATEST_FROM_LIVE = "live"                # 最新一筆是本次即時取得
LATEST_FROM_CACHE_NAV = "cache_nav"      # 最新一筆來自 `cache/nav` 預存檔（即時網址全敗）
LATEST_FROM_NAV_HISTORY = "nav_history"  # 最新一筆來自累積表（不是本次取得）

HISTORY_ONLY_LIVE_ERROR = "本次沒有取得任何即時淨值；序列全部來自累積表（A 鏈未交出逐來源原文）"

# ── 幣別閘（2026-10-13 稽核 5 B-1；總管技術裁定）────────────────────────────────
# 標籤仍只用持倉手填（裁定第 5 條本意不變）；但 A 鏈序列或累積表點**宣告了與持倉不同的幣別** →
# 那些數值根本不是持倉幣別計價（實例：晨星以 `currencyId=USD` 回的是換算成美元的淨值），貼上持倉幣別
# 就是錯的數字 → 整檔不寫（fail closed）。
# 非原生報價來源（SSOT：`fund_orchestration._NAV_NON_NATIVE_PREFIXES` ＝ 晨星／Yahoo／AlphaVantage）：
# 晨星的計價幣別由請求參數 `currencyId` 決定、Yahoo／AlphaVantage 是掛牌幣別，都不保證是基金原幣 →
# 這類序列**沒有宣告幣別**時同樣整檔不寫（不猜它是不是持倉幣別）。
TEXT_CCY_DECLARED_CONFLICT = ("淨值序列宣告的幣別與持倉手填不同（{shown}；持倉 {holding}）；"
                              "數值不是持倉幣別計價，不改標籤、不換算，{n} 筆全部不寫")
TEXT_CCY_NON_NATIVE_UNDECLARED = ("淨值來自非原生報價來源（{source}），計價幣別由請求參數或掛牌決定、"
                                  "序列卻沒有宣告幣別；不猜它是不是持倉幣別，{n} 筆全部不寫")
# 2026-10-14 C3a：meta 路徑（`label_source` 不是持倉手填）的同義文案；`{label}` ＝「來源自報（<來源>）」
# （暫定字面，exp 接上時另行送審，見 `TEXT_LABEL_DECLARED`）。上面兩句 hld 原文一字不動。
TEXT_CCY_DECLARED_CONFLICT_LABELED = ("淨值序列宣告的幣別與{label}的幣別不同（{shown}；{label} {holding}）；"
                                      "數值不是該幣別計價，不改標籤、不換算，{n} 筆全部不寫")
TEXT_CCY_NON_NATIVE_UNDECLARED_LABELED = ("淨值來自非原生報價來源（{source}），計價幣別由請求參數或掛牌決定、"
                                          "序列卻沒有宣告幣別；不猜它是不是{label}的幣別，{n} 筆全部不寫")
TEXT_NAME_SEARCH_SECID = "淨值來自以基金名稱搜尋的晨星代碼，依規則不採用（{origin}，來源 {source}）"


def _chain_ccy_gate(fund_code, series, attrs, holding_ccys, *, label_source=LABEL_SOURCE_HOLDING):
    """A 鏈那一支的幣別閘：擋下 → 回整檔不寫的輸出；放行 → None。不改任何標籤規則。
    `label_source`（2026-10-14 C3a）只決定文案字樣；判斷邏輯與 C3a 之前逐行相同。"""
    holding = {_ccy_meaning(c) for c in holding_ccys if not _is_blank_ccy(c)} - {None}
    if len(holding) != 1:
        return None          # 持倉沒填或互相矛盾：交給 resolve_nav_ccy 照原規則判（ccy_missing／ccy_conflict）
    held = next(iter(holding))
    declared = []
    live_decl = attrs.get(CHAIN_DECLARED_CCY_ATTR)
    hist_dates = attrs.get(HISTORY_DATES_ATTR) if isinstance(attrs.get(HISTORY_DATES_ATTR), list) else []
    has_live = len(series) > len(hist_dates)
    if has_live and not _is_blank_ccy(live_decl) and str(live_decl).strip():
        declared.append(("即時序列", live_decl))
    hist_ccy = attrs.get(HISTORY_CURRENCY_ATTR) if isinstance(attrs.get(HISTORY_CURRENCY_ATTR), dict) else {}
    if not NAV_HISTORY_PROVENANCE_VERIFIED:
        hist_ccy = {}        # 閘門關閉：累積點不寫，它們的宣告也不拿來擋即時那一段
    for day in sorted(hist_ccy):
        if str(hist_ccy[day] or "").strip():
            declared.append((f"累積表 {day}", hist_ccy[day]))
    bad = [(where, v) for where, v in declared if _ccy_meaning(v) != held]
    source = str(attrs.get("source") or "")
    text = None
    code = WITHHELD_CCY_CONFLICT
    if bad:
        shown = "、".join(f"{where}:{v!r}" for where, v in bad[:5]) + ("…" if len(bad) > 5 else "")
        if label_source == LABEL_SOURCE_HOLDING:
            text = TEXT_CCY_DECLARED_CONFLICT.format(shown=shown, holding=held, n=len(series))
        else:
            text = TEXT_CCY_DECLARED_CONFLICT_LABELED.format(label=_label_words(label_source)["input"], shown=shown,
                                                             holding=held, n=len(series))
    elif has_live and source.startswith(_NAV_NON_NATIVE_PREFIXES) and not str(live_decl or "").strip():
        if label_source == LABEL_SOURCE_HOLDING:
            text = TEXT_CCY_NON_NATIVE_UNDECLARED.format(source=source, n=len(series))
        else:
            text = TEXT_CCY_NON_NATIVE_UNDECLARED_LABELED.format(label=_label_words(label_source)["input"],
                                                                 source=source, n=len(series))
        code = WITHHELD_CCY_MISSING
    if text is None:
        return None
    out = _empty_out()
    out["fetched"] = len(series)
    out["withheld"] = code
    out["skipped"].append(text)
    out["provenance"] = {"source": attrs.get("source"), "fetched_at": None, "ccy_source": None,
                         "cache_fallback": False, "stale": None, "live_error": None}
    return _reconcile(out, len(series), "nav")


def _hist_group_rows(fund_code, part, source, recorded_at, *, holding_ccys, now, label_source=LABEL_SOURCE_HOLDING):
    """累積表裡同一個 `recorded_at` 的那幾點 → 一段的輸出。`recorded_at` 缺 → 整段不寫，不以當下時間補。"""
    if not recorded_at:
        out = _empty_out()
        out["fetched"] = len(part)
        out["withheld"] = WITHHELD_FETCHED_AT_MISSING
        out["skipped"].append(f"累積表這幾天沒有 recorded_at（寫入時間），{len(part)} 筆不寫（不以當下時間補）")
        return _reconcile(out, len(part), "nav")
    seg = part.copy()
    seg.attrs = {"source": source, "fetched_at": recorded_at}
    out = _rows_from_segment(fund_code, seg, holding_ccys=holding_ccys, now=now, label_source=label_source)
    out["skipped"] = [f"累積表（recorded_at {recorded_at}）：{line}" for line in out["skipped"]]
    return out


def _rows_with_history(fund_code, series, attrs, *, holding_ccys, now, label_source=LABEL_SOURCE_HOLDING) -> dict:
    """A 鏈併入了累積表的序列：逐點分成「本次即時（或預存檔）那一段」與「累積表各點」，各自照實帶 `fetched_at`。

    - 累積表的點：`fetched_at` ＝ 該點寫入累積表的 `recorded_at`（`load_series` 原值）；缺 → 那幾點不寫。
      **絕不**拿本次取得時間或讀表時間冒充（`49` §4.3／§4.4、`44`）。
    - 序列帶了併入標記、卻沒有日期清單（A 鏈算不出來）→ 分不出哪些是本次取得 → 整檔不寫。
    - `provenance` 另記 `latest_from`、`nav_history`；最新一筆不是本次即時取得（預存檔或累積表）時，
      `cache_fallback` 為真 —— 畫面據此標「不是本次取得」。
    """
    now_utc = _now_utc(now)
    dates = attrs.get(HISTORY_DATES_ATTR)
    hist_source = str(attrs.get(HISTORY_SOURCE_ATTR) or "nav_history")
    read_error = attrs.get(CHAIN_HIST_READ_ERROR_ATTR)
    if not isinstance(dates, list) or not all(isinstance(d, str) for d in dates):
        out = _empty_out()
        out["fetched"] = len(series)
        out["withheld"] = WITHHELD_FETCHED_AT_MISSING
        why = attrs.get(HISTORY_DATES_ERROR_ATTR) or f"沒有 {HISTORY_DATES_ATTR}"
        out["skipped"].append(
            f"A 鏈併入了累積表的點（{attrs.get(HISTORY_MERGED_ATTR)!s}），卻沒有交出是哪幾天（{why}）；"
            f"分不出哪些是本次即時取得，{len(series)} 筆全部不寫")
        out["provenance"] = {"source": attrs.get("source"), "fetched_at": None, "ccy_source": None,
                             "cache_fallback": False, "stale": None, "live_error": None,
                             "latest_from": None,
                             "nav_history": {"source": hist_source, "points": None, "written": 0,
                                             "recorded_at_missing": None, "read_error": read_error}}
        return _reconcile(out, len(series), "nav")

    hist_days = set(dates)
    recorded = attrs.get(HISTORY_RECORDED_AT_ATTR) if isinstance(attrs.get(HISTORY_RECORDED_AT_ATTR), dict) else {}
    is_hist = []
    groups: dict = {}
    for pos, stamp in enumerate(series.index):
        day, _why = _date_value(stamp)
        hit = day is not None and day.isoformat() in hist_days
        is_hist.append(hit)
        if hit:
            groups.setdefault(str(recorded.get(day.isoformat()) or ""), []).append(pos)
    live_mask = [not h for h in is_hist]
    live_part = series[live_mask]
    live_part.attrs = {k: v for k, v in attrs.items() if k not in _HISTORY_ATTRS and k not in _CHAIN_ATTRS}

    if not NAV_HISTORY_PROVENANCE_VERIFIED:
        return _rows_history_gate_closed(fund_code, live_part, attrs, groups, hist_source, read_error,
                                         holding_ccys=holding_ccys, now=now_utc, label_source=label_source)

    parts = []
    live_out = None
    if len(live_part):
        live_out = _rows_from_segment(fund_code, live_part, holding_ccys=holding_ccys, now=now_utc,
                                      label_source=label_source)
        parts.append(live_out)
    hist_written = hist_missing = 0
    for recorded_at in sorted(groups):
        one = _hist_group_rows(fund_code, series.iloc[groups[recorded_at]], hist_source, recorded_at,
                               holding_ccys=holding_ccys, now=now_utc, label_source=label_source)
        hist_written += len(one["rows"])
        if not recorded_at:
            hist_missing += len(groups[recorded_at])
        parts.append(one)

    out = _empty_out()
    for one in parts:
        out["rows"].extend(one["rows"])
        out["skipped"].extend(one["skipped"])
        out["fetched"] += one["fetched"]
    out["rows"].sort(key=lambda r: r["nav_date"])
    if not out["rows"]:
        lead = live_out if live_out is not None else (parts[0] if parts else None)
        out["withheld"] = lead["withheld"] if lead else None
    skipped_rows = sum(one["skipped_rows"] for one in parts)

    if live_out is not None:
        prov = dict(live_out["provenance"] or {})
    else:
        prov = {"source": None, "fetched_at": None, "ccy_source": None, "cache_fallback": False,
                "stale": None,
                "live_error": str(attrs.get(LIVE_FETCH_ERROR_ATTR) or attrs.get(CHAIN_FAILURES_ATTR)
                                  or HISTORY_ONLY_LIVE_ERROR)}
    if prov.get("ccy_source") is None:
        prov["ccy_source"] = next((one["provenance"]["ccy_source"] for one in parts
                                   if one["provenance"] and one["provenance"].get("ccy_source")), None)
    latest = None
    if out["rows"]:
        last_day = out["rows"][-1]["nav_date"]
        if last_day in hist_days:
            latest = LATEST_FROM_NAV_HISTORY
        elif prov.get("cache_fallback"):
            latest = LATEST_FROM_CACHE_NAV
        else:
            latest = LATEST_FROM_LIVE
    live_fallback = bool(prov.get("cache_fallback"))
    prov["cache_fallback"] = live_fallback or latest == LATEST_FROM_NAV_HISTORY or live_out is None
    if not live_fallback:
        prov["stale"] = None
    prov["latest_from"] = latest
    prov["nav_history"] = {"source": hist_source, "points": sum(len(v) for v in groups.values()),
                           "written": hist_written, "recorded_at_missing": hist_missing,
                           "read_error": None if read_error is None else str(read_error)}
    out["provenance"] = prov
    return _reconcile(out, skipped_rows, "nav")


def _rows_history_gate_closed(fund_code, live_part, attrs, groups, hist_source, read_error, *,
                              holding_ccys, now, label_source=LABEL_SOURCE_HOLDING) -> dict:
    """`NAV_HISTORY_PROVENANCE_VERIFIED` 關閉：累積點一律不寫，只寫即時那一段（見常數註解）。"""
    n_hist = sum(len(v) for v in groups.values())
    gate_line = TEXT_HISTORY_GATE_CLOSED.format(n=n_hist)
    if not len(live_part):
        out = _empty_out()
        live_error = str(attrs.get(LIVE_FETCH_ERROR_ATTR) or attrs.get(CHAIN_FAILURES_ATTR)
                         or HISTORY_ONLY_LIVE_ERROR)
        out["error"] = f"{live_error}\n{gate_line}"
        return out
    out = _rows_from_segment(fund_code, live_part, holding_ccys=holding_ccys, now=now, label_source=label_source)
    out["fetched"] += n_hist
    out["skipped"].append(gate_line)
    prov = out["provenance"] = dict(out["provenance"] or {})
    # 累積點一個都沒寫 → 最新一筆不可能來自累積表；`cache_fallback` 只反映即時那一段是不是預存檔
    prov["latest_from"] = ((LATEST_FROM_CACHE_NAV if prov.get("cache_fallback") else LATEST_FROM_LIVE)
                           if out["rows"] else None)
    prov["nav_history"] = {"source": hist_source, "points": n_hist, "written": 0,
                           "recorded_at_missing": sum(len(v) for k, v in groups.items() if not k),
                           "read_error": None if read_error is None else str(read_error),
                           "gate_closed": True, "withheld_by_gate": n_hist}
    return _reconcile(out, out["skipped_rows"] + n_hist, "nav")


def _add_chain_provenance(out: dict, attrs: dict) -> None:
    """A 鏈轉接那一支（序列帶 `CHAIN_ATTR`）：把頁型、採用來源、沒採用的來源原文、累積表讀取失敗補進 provenance。"""
    if CHAIN_ATTR not in attrs or out.get("provenance") is None:
        return
    prov = out["provenance"]
    prov["chain"] = dict(attrs.get(CHAIN_ATTR) or {})
    prov["chain_failures"] = attrs.get(CHAIN_FAILURES_ATTR)
    read_error = attrs.get(CHAIN_HIST_READ_ERROR_ATTR)
    hist = prov.setdefault("nav_history", {"source": None, "points": 0, "written": 0,
                                           "recorded_at_missing": 0, "read_error": None})
    if not NAV_HISTORY_PROVENANCE_VERIFIED:
        hist.setdefault("gate_closed", True)
        hist.setdefault("note", TEXT_HISTORY_NOT_READ)
    if read_error is not None:
        hist["read_error"] = str(read_error)
        out["skipped"].append(f"累積表本次讀取失敗，只用即時取得的部分：{read_error}")
    prov.setdefault("latest_from", LATEST_FROM_CACHE_NAV if prov.get("cache_fallback") else LATEST_FROM_LIVE)


# ───────────────────────── A 鏈轉接（客戶 2026-10-13 裁示：B 線復用既有多來源淨值鏈）─────────────────────────

# A 鏈實際用到、會讓「重新取數」拿到舊結果的 L1 快取（逐一實查：`_fetch_fund_single` 第 5 步、
# `fetch_fund_from_moneydj_url` 的持股與 legacy 最終備援）。set 頁 `refetch_nav` 依此逐一清掉。
# ⚠️ 只列真的會被 A 鏈呼叫到的；`fetch_div` 不在 A 鏈內（配息另一批），不列。
CHAIN_CACHED_FUNCTIONS = (
    nav_metrics.fetch_nav,               # legacy 最終備援（L1 日快取）
    nav_metrics.fetch_risk_metrics,      # wb07（L1 日快取）
    nav_metrics.fetch_performance_wb01,  # wb01（L1 日快取）
    nav_metrics.fetch_holdings,          # 持股（L1 日快取）
    fund_orchestration._holdings_ttl,    # 持股外層 L1 一小時快取
    fund_orchestration.fetch_fund_from_moneydj_url,   # A 鏈 L1 主入口（L1 十五分鐘快取，2026-10-13 補回）
)

TEXT_KEY_MISMATCH = ("A 鏈回傳的 full_key {got!r} 與代碼對照（fund_keys）的 full_key {want!r} 不同；"
                     "不猜哪一個對，這一檔的淨值不寫")
TEXT_KEY_MISSING = "A 鏈取到了淨值序列，卻沒有回傳 full_key，無法與代碼對照核對；這一檔的淨值不寫"
TEXT_NO_SERIES = "A 鏈（auto_fetch_moneydj({code!r})）沒有取得淨值序列"


def _chain_failure_lines(res: dict) -> list:
    """A 鏈回傳值 → 逐頁型、逐來源的失敗原文行（未遮蔽）。只讀 A 鏈自己交出的欄位，不自編原因。"""
    lines = []
    attempts = res.get(NAV_ATTEMPTS_KEY)
    if isinstance(attempts, list) and attempts:
        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue
            pt = attempt.get("page_type")
            # 2026-10-13 稽核 5 N3：成功（complete 且沒有錯誤）的那一次不印狀態行
            if attempt.get("status") != "complete" or attempt.get("error"):
                head = f"[{pt}] 狀態 {attempt.get('status')}"
                if attempt.get("error"):
                    head += f"：{attempt['error']}"
                lines.append(head)
            for f in attempt.get("nav_source_failures") or ():
                if isinstance(f, dict):
                    # 2026-10-13 稽核 5 N2：用每筆記錄自己的頁型（L1 會在同一次嘗試內換頁型重試）；
                    # 沒有頁型的那幾筆（legacy 段）標明，不冒用外層頁型。
                    own = f.get("page_type") or f"{pt}·legacy"
                    cand = f" 候選 {f['candidate']}" if f.get("candidate") else ""
                    lines.append(f"[{own}{cand}] {f.get('source')}：{f.get('error')}")
        return lines
    if res.get("error"):
        lines.append(str(res["error"]))
    for f in res.get(NAV_SOURCE_FAILURES_KEY) or ():
        if isinstance(f, dict):
            lines.append(f"{f.get('source')}：{f.get('error')}")
    return lines


def _nav_history_read_error(res: dict):
    for entry in res.get("source_trace") or ():
        if isinstance(entry, dict) and entry.get("source") == "nav_history_merge" and entry.get("success") is False:
            return str(entry.get("error") or "nav_history 讀取失敗（A 鏈未給原文）")
    return None


def fetch_nav_chain_with_error(chain_code: str, full_key: str):
    """B 線的淨值取數：**原樣**呼叫 A 鏈 `services.moneydj_fetcher.auto_fetch_moneydj(chain_code)`，
    回 `(Series, error)`（介面同 L1 `fetch_nav_with_error`）。

    - 來源、優先序、頁型迴圈、停止條件、nav_history 併入：全部是 A 鏈自己的，本函式一個都不重寫
      （客戶 2026-10-13 裁示；總管同日技術裁定第 2 條）。
    - `chain_code` 是 `fund_keys` 的 `parsed_code`（查表前的代碼；A 鏈自己查對照表）。A 鏈回傳的 `full_key`
      必須等於 `fund_keys` 的 `full_key`，不等就照實回錯誤，不猜。
    - 幣別：**完全不採用** A 鏈回的幣別（結果 dict 的 `currency` 可能是硬編表或推定值，序列 attrs 的幣別也可能是
      來源的預設值，無法可靠分辨是否來源自報）→ 序列 attrs 的 `currency` 一律拿掉，只用持倉手填（第 5 條）。
    - `fetched_at`：序列 attrs 自帶的優先；沒有時才用 A 鏈 L1 交出的 `chain_started_at`
      （L1 在被快取的函式內取得的本輪開始時間，帶時區，跟著結果一起快取；命中快取時就是原本那一次的時間），
      並在 `CHAIN_ATTR["fetched_at_from"]` 標 `"orchestrator"`。本層**不**用當下時間補。
      預存檔那一支照舊由 `rows_from_nav_series` 改取 `cache_updated_at`；累積表的點取各自的 `recorded_at`。
    - 失敗：沒有序列 → `(空 Series, 原文)`，原文逐頁型、逐來源列出 A 鏈交出的失敗原因（未遮蔽）。
    """
    res, page_type = auto_fetch_moneydj(chain_code, return_page_type=True)
    return _nav_from_chain(res, page_type, chain_code, full_key)


def _nav_from_chain(res, page_type, chain_code: str, full_key: str):
    """A 鏈回傳值 → `(Series, error)`（2026-10-13 自 `fetch_nav_chain_with_error` 抽出，本體一字未改，
    讓 `fetch_chain_with_error` 用同一次 A 鏈呼叫同時取淨值與配息）。"""
    if not isinstance(res, dict):
        return None, f"{TYPE_ERROR_PREFIX}：auto_fetch_moneydj 預期回 dict，收到 {type(res).__name__}"
    lines = _chain_failure_lines(res)
    read_error = _nav_history_read_error(res)
    got_key = res.get("full_key")
    series = res.get("series")
    usable = isinstance(series, pd.Series) and len(series) > 0
    if not usable:
        text = [TEXT_NO_SERIES.format(code=chain_code)]
        if got_key and got_key != full_key:
            text.append(TEXT_KEY_MISMATCH.format(got=got_key, want=full_key))
        text.extend(lines)
        if read_error is not None:
            text.append(f"累積表讀取失敗：{read_error}")
        return pd.Series(dtype=float), "\n".join(text)
    if not got_key:
        return pd.Series(dtype=float), TEXT_KEY_MISSING
    if got_key != full_key:
        return pd.Series(dtype=float), TEXT_KEY_MISMATCH.format(got=got_key, want=full_key)

    raw_attrs = dict(series.attrs or {})
    origin = raw_attrs.get(MS_SECID_ORIGIN_ATTR)
    if origin in (MS_SECID_FROM_NAME_SEARCH, MS_SECID_FROM_CODE_SEARCH):
        # 2026-10-13 稽核 5 B-2：客戶硬規則「不以基金名稱推定」；A 鏈照舊採用，B 線拒收（含跨度延長後整條換成它）
        return pd.Series(dtype=float), TEXT_NAME_SEARCH_SECID.format(origin=origin, source=raw_attrs.get("source"))
    out = series.copy()
    attrs = {k: v for k, v in raw_attrs.items() if k != "currency"}
    # 2026-10-13 B-1：宣告的幣別不當標籤，但另存起來給幣別閘比對（併入累積表時，live 原值記在另一個鍵）
    attrs[CHAIN_DECLARED_CCY_ATTR] = str(
        (raw_attrs.get(HISTORY_LIVE_CURRENCY_ATTR) if HISTORY_MERGED_ATTR in raw_attrs
         else raw_attrs.get("currency")) or "")
    fetched_at_from = "series_attrs"
    if not attrs.get("fetched_at"):
        # A 鏈 L1 在被快取的函式內取得的本輪開始時間（命中快取時是原本那一次的時間，不是當下）
        attrs["fetched_at"] = res.get("chain_started_at")
        fetched_at_from = "orchestrator"
    failures = "\n".join(lines) or None
    is_cache = (str(attrs.get("source") or "").startswith(CACHE_FALLBACK_SOURCE_PREFIX)
                or "nav_quality" in attrs)
    if is_cache:
        # 預存檔那一支：本次即時失敗的原文 ＝ A 鏈瀑布逐來源原文 ＋ fetch_nav 自己的逐網址原文
        attrs[LIVE_FETCH_ERROR_ATTR] = "\n".join(
            x for x in (failures, attrs.get(LIVE_FETCH_ERROR_ATTR)) if x) or None
        fetched_at_from = "cache_updated_at"   # 2026-10-13 稽核 5 N3：預存檔那一支用的是 cache_updated_at
    attrs[CHAIN_ATTR] = {"page_type": page_type, "data_source": res.get("data_source"),
                         "fetched_at_from": fetched_at_from}
    attrs[CHAIN_FAILURES_ATTR] = failures
    attrs[CHAIN_HIST_READ_ERROR_ATTR] = read_error
    out.attrs = attrs
    return out, None


def _merge_one(code, one, acc):
    acc["rows"].extend(one["rows"])
    acc["fetched"][code] = one["fetched"]
    acc["skipped_rows"][code] = one["skipped_rows"]
    if one["error"] is not None:
        acc["errors"][code] = one["error"]
    if one["withheld"]:
        acc["withheld"][code] = one["withheld"]
    if one["skipped"]:
        acc["skipped"][code] = one["skipped"]
    if one["provenance"] is not None:
        acc["provenance"][code] = one["provenance"]


def build_nav_table(funds, *, now=None) -> dict:
    """組出 `nav` 表的列。`funds`：可迭代的 dict，每個帶 `fund_code`、`full_key`、`chain_code`
    （2026-10-13 起必填：`fund_keys` 的 `parsed_code`，原樣交給 A 鏈），選填 `portal`（A 鏈不吃，非空即該檔報錯）、
    `holding_ccy`（持倉列使用者手填的幣別；同一檔多列持倉可重複出現）。
    取數經 `fetch_nav_chain_with_error` 走 A 鏈（客戶 2026-10-13 裁示），整個迴圈在
    `nav_history_shared_reads()` 範圍內（累積表本次只讀一次）。

    回傳 `{"rows", "errors", "withheld", "skipped", "fetched", "skipped_rows", "provenance"}`，皆以 `fund_code` 為鍵
    （`rows` 除外）：
    - `errors`：L1 失敗原文（未遮蔽）或型別錯誤；
    - `withheld`：整檔不寫列的原因代碼；`skipped`：不寫列的文字理由（整檔或逐列）；
    - `fetched`：L1 取回的筆數（過濾前）；L1 回錯誤或型別不對時為 0；
    - `skipped_rows`：略過與合併的筆數；有這兩個鍵的檔恆有 `len(該檔 rows) + skipped_rows == fetched`（核帳）；
    - ⚠️ **射程**：`fetched`／`skipped_rows` 只列**真的呼叫過 L1 的檔**（含取數失敗、型別錯誤，此時兩者為 0）。
      `withheld` 為 `input_conflict` 的檔**沒有呼叫 L1，也就沒有這兩個鍵** —— 不補 0（補 0 會讓它看起來像「取回 0 筆」）；
    - `provenance`：`{source, fetched_at, ccy_source, cache_fallback, stale, live_error}`（`live_error` 2026-10-09 加）。
    """
    return _build_tables(funds, now=now, with_dividends=False)["nav"]


def _build_tables(funds, *, now, with_dividends: bool, chain_fetch=None) -> dict:
    """`build_nav_table` 與 `build_nav_dividend_tables` 共用的迴圈（2026-10-13 抽出）。
    淨值那一半的每一步與抽出前逐行相同；`with_dividends` 為真時改呼叫 `fetch_chain_with_error`
    （**同一次** A 鏈呼叫多交出配息），淨值仍由同一個 `_nav_from_chain` 判讀。
    `chain_fetch`（2026-10-14 C3a）：`with_dividends` 為真時取代 `fetch_chain_with_error` 的可呼叫物
    （介面相同：`(chain_code, full_key) -> (Series, error, div)`）；None ＝ 預設 `fetch_chain_with_error`
    （在呼叫當下才解析模組層名稱，所以既有以 monkeypatch 換掉模組層 `fetch_chain_with_error` 的寫法照樣有效）。
    `with_dividends` 為假時不使用（淨值單表走 `fetch_nav_chain_with_error`）。"""
    if chain_fetch is not None and not callable(chain_fetch):
        raise ValueError(f"chain_fetch 須為可呼叫物（{chain_fetch!r}）")
    grouped, conflicts = _group_funds(funds, chain=True)
    acc = {"rows": [], "errors": {}, "withheld": {}, "skipped": {}, "fetched": {}, "skipped_rows": {},
           "provenance": {}}
    div_acc = _empty_div_acc() if with_dividends else None
    # 第 6 條：本次 build 內 A 鏈讀累積表，整張表只讀一次（範圍結束即丟；失敗照實重拋，不吞）。
    # 2026-10-13 稽核 5 B4：出處閘門關閉 → 本次 build 範圍內不讀累積表（A 鏈頁型選擇與沒有累積表時相同）
    with nav_history_shared_reads(skip_reads=not NAV_HISTORY_PROVENANCE_VERIFIED):
        for code, entry in grouped.items():
            if code in conflicts:
                acc["withheld"][code] = WITHHELD_INPUT_CONFLICT
                acc["skipped"][code] = [conflicts[code] + "；不取數、不寫列"]
                if div_acc is not None:
                    div_acc["withheld"][code] = WITHHELD_INPUT_CONFLICT
                    div_acc["skipped"][code] = [conflicts[code] + "；不取數、不寫列"]
                    div_acc["settled"][code] = False
                continue
            div = None
            if entry["portal"]:
                series, error = None, (f"A 鏈不吃 portal（收到 {entry['portal']!r}）；"
                                       f"`fund_keys` 一律給空字串，不猜這個值要怎麼用")
                div = {"items": None, "outcome": None, "error": error}
            elif div_acc is not None:
                series, error, div = _call_chain(entry["chain_code"], entry["full_key"], chain_fetch=chain_fetch)
            else:
                series, error = _call(fetch_nav_chain_with_error, entry["chain_code"], entry["full_key"])
            _merge_one(code, rows_from_nav_series(code, series, error, holding_ccys=entry["holding_ccys"], now=now,
                                                  label_source=entry["label_source"]), acc)
            if div_acc is not None:
                _merge_div(code, rows_from_chain_dividends(code, div, holding_ccys=entry["holding_ccys"], now=now,
                                                           label_source=entry["label_source"]), div_acc)
    _check_rows_order(acc["rows"], contract.NAV_FIELDS, "nav")
    if div_acc is not None:
        _check_rows_order(div_acc["rows"], contract.DIVIDEND_FIELDS, "dividend")
    return {"nav": acc, "dividend": div_acc}


# ───────────────────────── dividend ─────────────────────────

def rows_from_dividends(fund_code: str, items, error, *, now=None) -> dict:
    """單一檔基金的 L1 配息清單 → `{rows, error, withheld, skipped, fetched, provenance}`（純函式）。

    - `error` 非空：原文照回、不寫列。`items` 不是 list（含 None、字串）：型別錯誤進 `error`
      （不對字串逐字元計數）。
    - 空清單又沒有原因：**不是錯誤**。L1 原註：頁面取回且解析跑完、但沒有配息列 ——
      同時涵蓋「這檔不配息」與「頁面改版、解析不到」，本層分辨不出來，只如實記在 `skipped`。
    - 幣別只收每一筆自帶的 `currency`（來源自報、ISO 4217）；任何一筆沒有 → 那一筆不寫，
      整檔一筆都沒有 → `withheld = ccy_not_source_reported`。
    - `ex_date` 只收 `_date_value` 那三種，且不早於 `MIN_VALID_DATE`、不晚於當下的台灣日期。
    - `div_per_unit_orig_ccy` 不小於 0（0 照寫）；負數、布林、非有限值不寫。
    - 同一 `ex_date` 兩筆：金額相同只寫一列（主鍵），不同就該日全部不寫。
    - `fetched_at` 取每一筆自帶的值換成世界協調時間；取不到或晚於當下不寫（不以當下時間補）。
    """
    out = _empty_out()
    out["merged"] = 0   # 2026-10-13 新增鍵：同日同額合併的筆數（A 鏈配息那一支據此判「每一筆都寫進去了」）
    if error:
        out["error"] = str(error)
        return out
    if not isinstance(items, list):
        out["error"] = f"{TYPE_ERROR_PREFIX}：預期 list，收到 {type(items).__name__}"
        return out
    if not items:
        out["skipped"].append("來源頁面取回、但沒有任何配息列（無法分辨不配息或頁面改版，L1 原註）")
        return out
    now_utc = _now_utc(now)
    today_market = now_utc.astimezone(MARKET_DATE_TZ).date()
    out["fetched"] = len(items)
    sources = sorted({str(it.get("source")) for it in items if isinstance(it, dict) and it.get("source")})

    no_ccy = negative = conflicting = contract_bad = not_dict = merged = 0
    date_bad: dict = {}
    amount_bad: dict = {}
    time_bad: dict = {}
    time_codes = set()
    reached_time = 0
    candidates: dict = {}
    times = set()
    for item in items:
        if not isinstance(item, dict):
            not_dict += 1
            continue
        ccy = _iso_ccy(item.get("currency"))
        if ccy is None:
            no_ccy += 1
            continue
        day, why = _dated(item.get("date"), today_market)
        if day is None:
            _tally(date_bad, why)
            continue
        raw = item.get("amount")
        if _is_bool(raw):
            _tally(amount_bad, "是布林值（不算數字）")
            continue
        try:
            amount = float(raw)
        except OverflowError:
            _tally(amount_bad, "數值溢位（超出浮點範圍）")
            continue
        except (TypeError, ValueError):
            _tally(amount_bad, "無法轉成數字")
            continue
        if not math.isfinite(amount):
            _tally(amount_bad, "非有限數值")
            continue
        if amount < 0:
            negative += 1
            continue
        reached_time += 1
        fetched_at, code, why = _fetched_at_check(item.get("fetched_at"), now_utc)
        if fetched_at is None:
            _tally(time_bad, why)
            time_codes.add(code)
            continue
        times.add(fetched_at)
        candidates.setdefault(day, []).append((amount, ccy, fetched_at))

    for day in sorted(candidates):
        entries = candidates[day]
        if len({(a, c) for a, c, _t in entries}) > 1:
            conflicting += len(entries)
            continue
        amount, ccy, fetched_at = entries[0]
        row = {
            "fund_code": fund_code,
            "ex_date": day,
            "pay_date": None,                   # 來源不給（49 §2.2）
            "div_per_unit_orig_ccy": amount,
            "ccy": ccy,
            "div_kind": DIV_KIND_UNKNOWN,       # Q5
            "fetched_at": fetched_at,
        }
        if contract.dividend_row_problems(row):
            contract_bad += len(entries)
            continue
        merged += len(entries) - 1        # 同日同額：主鍵只留一列
        out["rows"].append(row)

    out["provenance"] = {"source": sources[0] if len(sources) == 1 else (sources or None),
                         "fetched_at": sorted(times)[-1] if times else None,
                         "ccy_source": "source_reported" if out["rows"] else None}
    if not_dict:
        out["skipped"].append(f"不是 dict {not_dict} 筆不寫")
    if no_ccy and no_ccy == len(items) - not_dict:
        out["withheld"] = WITHHELD_CCY_NOT_SOURCE_REPORTED
        out["skipped"].append(f"來源未自報配息幣別（49 T3：不沿用持倉幣別），{no_ccy} 筆全部不寫")
        return _reconcile(out, not_dict + no_ccy, "dividend")
    if no_ccy:
        out["skipped"].append(f"來源未自報配息幣別 {no_ccy} 筆不寫")
    out["skipped"].extend(_tally_lines(date_bad, "日期："))
    out["skipped"].extend(_tally_lines(amount_bad, "配息金額"))
    if negative:
        out["skipped"].append(f"配息金額為負 {negative} 筆不寫")
    if time_bad:
        out["skipped"].extend(f"fetched_at {line}（不以當下時間補）" for line in _tally_lines(time_bad, ""))
        if not out["rows"] and sum(time_bad.values()) == reached_time and len(time_codes) == 1:
            out["withheld"] = next(iter(time_codes))
    if conflicting:
        out["skipped"].append(f"同一日期出現不同配息 {conflicting} 筆不寫")
    if contract_bad:
        out["skipped"].append(f"不符欄位契約 {contract_bad} 筆不寫")
    if merged:
        out["skipped"].append(f"同日同值合併 {merged} 筆")
    out["merged"] = merged
    total = (not_dict + no_ccy + sum(date_bad.values()) + sum(amount_bad.values()) + negative
             + sum(time_bad.values()) + conflicting + contract_bad + merged)
    return _reconcile(out, total, "dividend")


def build_dividend_table(funds, *, now=None) -> dict:
    """組出 `dividend` 表的列。`funds` 同 `build_nav_table`（`holding_ccy` 在本表**不使用**，T3）。

    回傳 `{"rows", "errors", "pending", "withheld", "skipped", "fetched", "skipped_rows", "provenance"}`
    （`skipped_rows` 與核帳同 `build_nav_table`）。
    ⚠️ 射程：`fetched`／`skipped_rows` 只列真的呼叫過 L1 的檔；`input_conflict` 的檔與語意閘未開而列在
    `pending` 的檔**沒有呼叫 L1，也沒有這兩個鍵**，不補 0。
    `DIV_DATE_IS_EX_DATE_VERIFIED` 為假時：每一檔都列在 `pending`（代碼 `PENDING_DIV_DATE_SEMANTICS`）、
    **不呼叫 L1**、不寫列。
    """
    grouped, conflicts = _group_funds(funds)
    acc = {"rows": [], "errors": {}, "pending": {}, "withheld": {}, "skipped": {}, "fetched": {},
           "skipped_rows": {}, "provenance": {}}
    for code, entry in grouped.items():
        if code in conflicts:
            acc["withheld"][code] = WITHHELD_INPUT_CONFLICT
            acc["skipped"][code] = [conflicts[code] + "；不取數、不寫列"]
            continue
        if not DIV_DATE_IS_EX_DATE_VERIFIED:
            acc["pending"][code] = PENDING_DIV_DATE_SEMANTICS
            acc["skipped"][code] = [_PENDING_DIV_TEXT]
            continue
        items, error = _call(fetch_div_with_error, entry["full_key"], entry["portal"])
        _merge_one(code, rows_from_dividends(code, items, error, now=now), acc)
    _check_rows_order(acc["rows"], contract.DIVIDEND_FIELDS, "dividend")
    return acc


# ───────────────────────── 配息：A 鏈同一次呼叫交出的 dividends（客戶 2026-10-13 裁示）─────────────────────────
#
# 來源、順序沿用 A 鏈（`_fetch_fund_single` 第 4 步：合庫 MoneyDJ → FundClear → 鉅亨，第一個有列的採用）；
# 本層**不另外發請求**，只讀 `auto_fetch_moneydj` 回傳的 `dividends` 與 `dividends_fetch_outcome`。
#
# ── 日期語意：逐來源判定（取代單一總開關 `DIV_DATE_IS_EX_DATE_VERIFIED`）──────────────────────────────
# 證據只採：解析器的**欄名比對**（以表頭文字或 JSON 欄名認欄位，不靠寫死的欄位序號）與既有測試。
# 本組查過 repo：**沒有任何一份真實頁面的 fixture**（`tests/` 內的配息 HTML／JSON 都是手寫的最小樣本），
# 所以「這個來源的某一欄是除息日」不能靠靜態證據一次判定，改成**每一筆、每一頁當場核對**：
# - 合庫 MoneyDJ（`DIV_PARSER_TCB`）：解析器照寫死的序號取第 2 欄當 `ex_date`（它自己的註解說第 1 欄是配息基準日、
#   第 2 欄是除息日、第 7 欄是幣別；既有測試的 HTML 是依同一份註解手寫的，**循環，不算證據**）。
#   L1 本輪新增記下那一頁表頭第 2、7 格的文字 → 本層只收**表頭第 2 格恰為「除息日」**的那幾筆；
#   幣別只收表頭第 7 格恰為「幣別」、且該格有值的。表頭對不上（版面改了、巢狀表、合併儲存格）→ 不寫。
# - FundClear（`DIV_PARSER_FUNDCLEAR`）：解析器以 JSON 欄名取值 —— `ExDividendDate`／`exDividendDate` 優先，
#   沒有才退 `Date`／`date`（語意不明）。L1 新增記下實際取自哪個欄名 → 本層只收取自前兩者的。
#   幣別只收取自 `Currency`／`currency` 欄、且有值的（缺欄留白，2026-10-10 起不再死預設 USD）。
#   ⚠️ 解析器同時把同一個值寫進 `pay_date`（那不是入帳日）→ 本層**不讀** `pay_date`，照舊寫空值。
# - 鉅亨（`DIV_PARSER_CNYES`）：`date` 優先、`exDate` 次之；只收取自 `exDate` 的。**解析器不回報幣別** → 一律不寫。
# - 其他（沒有 `div_provenance` 的列，例如 A 鏈 legacy 段的 wb05 內嵌解析：它缺幣別時沿用基金層級幣別 ——
#   那是預設值，不是逐筆自報）→ 一律不寫。
DIV_EX_DATE_EVIDENCE = {
    # 解析器標記: (取哪一個鍵當日期, 解析依據裡記錄出處的鍵, 出處必須恰為其中之一)
    DIV_PARSER_TCB: ("ex_date", "ex_date_header", ("除息日",)),
    DIV_PARSER_FUNDCLEAR: ("ex_date", "date_field", ("ExDividendDate", "exDividendDate")),
    DIV_PARSER_CNYES: ("date", "date_field", ("exDate",)),
}
DIV_CCY_EVIDENCE = {
    # 解析器標記: (解析依據裡記錄幣別出處的鍵, 出處必須恰為其中之一)；不在表內 ＝ 解析器不回報幣別
    DIV_PARSER_TCB: ("currency_header", ("幣別",)),
    DIV_PARSER_FUNDCLEAR: ("currency_field", ("Currency", "currency")),
}
# ── 2026-10-13 稽核必修 2：金額欄同樣要有出處證據（只收程式碼裡找得到依據的字面）──────────────────
# - 合庫：`_src_tcb_div._parse_div_html` 自己的欄位註解寫 `col[4]=每單位配息額` → 表頭第 5 格必須恰為「每單位配息額」。
#   （⚠️ `fund_orchestration` legacy 段另一份內嵌解析的註解寫 `col[4]=配息金額`；那是**另一個解析器**的假設，
#   且那一支的列本來就不收，故不採。）另要求~~表頭格數與該列格數相同（`row_cells == header_cells`）~~
#   該列沒有 th 格、且取值讀的 td 格數等於表頭格數（`row_th_cells == 0 and row_td_cells == header_cells`；
#   稽核組 B 回修，見 `_tcb_cells_mismatch`），~~否則序號對不上表頭（合併儲存格、少一格、列首多一格 th）。~~
#   ⚠️ 上句「擋得住合併儲存格」已被稽核組 C 實測推翻：colspan／rowspan 時格數照樣相等、序號卻錯位。
#   現行：格數條件只擋「少一格、多一格、列首多一格 th」；合併儲存格改由 L1 記的 `table_has_span`
#   （整張表任一格 colspan／rowspan 不是 1）擋 —— 有合併、或缺這個鍵 → 對不上。
# - FundClear：解析器依序試 `DividendAmount`／`dividendAmount`／`Amount`／`amount`；欄名本身就說明是配息金額的
#   只有前兩個，`Amount`／`amount` 語意不明（同 `Date` 之於日期）→ 不收。
# - 鉅亨：依序試 `dividend`／`amount` → 只收 `dividend`。
# 不符 → 列 pending（與日期證明不了同一類：這一欄是什麼數字沒有證據），不寫列。
DIV_AMOUNT_EVIDENCE = {
    DIV_PARSER_TCB: ("amount_header", ("每單位配息額",)),
    DIV_PARSER_FUNDCLEAR: ("amount_field", ("DividendAmount", "dividendAmount")),
    DIV_PARSER_CNYES: ("amount_field", ("dividend",)),
}

# 整檔不寫的原因代碼（配息專用；其餘沿用上方 `WITHHELD_*`）。
WITHHELD_DIV_OUTCOME_UNDETERMINED = "div_outcome_undetermined"   # 沒有配息列，又分辨不出是不配息還是沒抓到
WITHHELD_DIV_ITEMS_REJECTED = "div_items_rejected"               # 有配息列，但一筆都過不了逐筆核對（原因見 skipped）
# 待查證（`pending`）：日期欄證明不了是除息日。
# 2026-10-13 稽核必修 2 擴大射程（代碼字面不改，免得下游對不上）：金額欄證明不了是每單位配息、
# 合庫表頭格數與列格數不同，也列在這一碼 —— 都是「這一欄是什麼沒有證據」。
PENDING_DIV_EX_DATE_UNVERIFIED = "div_ex_date_unverified"

TEXT_DIV_NONE = "A 鏈配息瀑布每一個來源都回報：成功取數、這一檔沒有配息紀錄"
TEXT_DIV_UNDETERMINED = ("A 鏈沒有取到配息列，但分辨不出是這一檔不配息、還是沒抓到（{detail}）；"
                         "不當成「沒有配息」，不寫列")
TEXT_DIV_FAILED = "A 鏈配息取數失敗（每一個來源都失敗）：\n{detail}"
TEXT_DIV_KEY_MISSING = "A 鏈沒有回傳 full_key，配息無法與代碼對照核對；這一檔的配息不寫"
TEXT_DIV_KEY_MISMATCH = ("A 鏈回傳的 full_key {got!r} 與代碼對照（fund_keys）的 full_key {want!r} 不同；"
                         "不猜哪一個對，這一檔的配息不寫")
TEXT_DIV_NO_PROVENANCE = "沒有解析依據（不是已登記的三個配息解析器交出的列）"
TEXT_DIV_DATE_UNVERIFIED = "日期欄證明不了是除息日（{parser}：{field}={value!r}）"
TEXT_DIV_AMOUNT_UNVERIFIED = "金額欄證明不了是每單位配息（{parser}：{field}={value!r}）"
TEXT_DIV_CELLS_MISMATCH = ("這一列含 th 格、取值讀的 td 格數與表頭格數不同，或表內有合併儲存格"
                           "（表頭 {hdr}、列 td {td}、th {th}、合併 {span}），欄位序號對不上表頭")


def _tcb_cells_mismatch(prov: dict) -> bool:
    """合庫配息列的欄位序號對不對得上表頭（稽核組 B 回修；fail closed）。
    L1 取值只讀 td（`_cols`），故要求：這一列**沒有** th（`row_th_cells == 0`），而且取值讀的 td 格數
    等於表頭格數（`row_td_cells == header_cells`），而且整張表沒有合併儲存格（`table_has_span is False`；
    稽核組 C 補）。任一不成立、任一個數不是 int、或 `table_has_span` 不是 bool（含缺鍵）→ 對不上。
    ~~`row_cells == header_cells`（th＋td 合計）~~：首格 th＋7 td 對 8 格表頭會放行、取值卻整排左移一格。"""
    td, th, hdr = prov.get("row_td_cells"), prov.get("row_th_cells"), prov.get("header_cells")
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in (td, th, hdr)):
        return True
    span = prov.get("table_has_span")
    if not isinstance(span, bool) or span:
        return True
    return th > 0 or td != hdr


# GAP-DIV-NONE-EVIDENCE-1（2026-10-13 稽核必修 3 登記；fail closed）：配息來源回空，可能是「確實不配息」，
# 也可能是「來源不認得這個代碼」。本輪採的證據是 A 鏈**同一輪、同一來源、同一代碼**取到東西
# （L1 `fund_orchestration._div_code_evidence`：FundClear 淨值或基本資料、合庫淨值或基本資料、
# 鉅亨淨值且 attrs 的端點恰為本代碼）。瀑布沒呼叫到的來源（例：FundClear 淨值已夠筆數 → 鉅亨淨值不會被打）
# 就沒有證據 → 視為未定、不顯示「區間內無配息」。repo 內沒有任何真實頁面樣本，「回空＝不配息」本身也未經線上查證。
TEXT_DIV_NONE_UNEVIDENCED = ("A 鏈配息瀑布每一個來源都回空，但本輪沒有「同一來源認得這個代碼」的證據"
                             "（來源不認得代碼時也會回空）；不當成「沒有配息」，不寫列：\n{detail}")
TEXT_DIV_DROPPED = "供列的來源回報有列沒有交出來（{detail}）；寫出的列不是全部，不算已確定"
TEXT_DIV_DATE_FORMAT = "日期不是 YYYY-MM-DD 或 YYYY/MM/DD（{value!r}）"
TEXT_DIV_CCY_UNDECLARED = "來源未宣告這一筆的配息幣別（{parser}）"
TEXT_DIV_CCY_CONFLICT = ("配息宣告的幣別與持倉手填不同或認不出（{shown}；持倉 {holding}）；不改標籤、不換算，"
                         "這一檔的配息 {n} 筆全部不寫")
# 2026-10-14 C3a：meta 路徑的同義文案（`{label}` 暫定字面見 `TEXT_LABEL_DECLARED`）；上句 hld 原文一字不動。
TEXT_DIV_CCY_CONFLICT_LABELED = ("配息宣告的幣別與{label}的幣別不同或認不出（{shown}；{label} {holding}）；"
                                 "不改標籤、不換算，這一檔的配息 {n} 筆全部不寫")


def _empty_div_acc() -> dict:
    return {"rows": [], "errors": {}, "pending": {}, "withheld": {}, "skipped": {}, "fetched": {},
            "skipped_rows": {}, "provenance": {}, "settled": {}}


def _merge_div(code, one, acc) -> None:
    _merge_one(code, one, acc)
    if one.get("pending"):
        acc["pending"][code] = one["pending"]
    acc["settled"][code] = bool(one.get("settled"))


def fetch_chain_with_error(chain_code: str, full_key: str):
    """**同一次** A 鏈呼叫 → `(Series, error, div)`：淨值那兩個值與 `fetch_nav_chain_with_error` 同一個判讀
    （`_nav_from_chain`）；`div` ＝ `{"items", "outcome", "error"}`，取自同一份回傳值的 `dividends` 與
    `dividends_fetch_outcome`，本函式不另外發任何請求。
    - A 鏈回傳的 `full_key` 缺或與 `fund_keys` 不同 → `div["error"]`（不猜哪一個對，同淨值）。
    - `secid_origin` 拒收不適用於配息：那是晨星**淨值**序列的代碼出處；配息三個解析器都以 A 鏈的基金代碼取數，
      不經任何名稱搜尋。累積表（nav_history）只存淨值，不存配息 → 累積表閘門同樣不適用。"""
    res, page_type = auto_fetch_moneydj(chain_code, return_page_type=True)
    series, error = _nav_from_chain(res, page_type, chain_code, full_key)
    return series, error, _div_from_chain(res, full_key)


def _div_from_chain(res, full_key: str) -> dict:
    if not isinstance(res, dict):
        return {"items": None, "outcome": None,
                "error": f"{TYPE_ERROR_PREFIX}：auto_fetch_moneydj 預期回 dict，收到 {type(res).__name__}"}
    got_key = res.get("full_key")
    if not got_key:
        text = TEXT_DIV_KEY_MISSING
        if res.get("error"):
            text += f"\n{res['error']}"
        return {"items": None, "outcome": None, "error": text}
    if got_key != full_key:
        return {"items": None, "outcome": None, "error": TEXT_DIV_KEY_MISMATCH.format(got=got_key, want=full_key)}
    return {"items": res.get("dividends"), "outcome": res.get(DIVIDENDS_OUTCOME_KEY), "error": None}


def _call_chain(chain_code: str, full_key: str, *, chain_fetch=None):
    """呼叫 `fetch_chain_with_error`（或注入的 `chain_fetch`，2026-10-14 C3a）；例外不吞，轉成兩邊的失敗原文（同 `_call`）。"""
    fetch = fetch_chain_with_error if chain_fetch is None else chain_fetch
    try:
        result = fetch(chain_code, full_key)
    except Exception as exc:  # noqa: BLE001 —— 轉成可見的失敗原文，不是吞掉
        text = f"{type(exc).__name__}: {exc}"
        return None, text, {"items": None, "outcome": None, "error": text}
    if not isinstance(result, tuple) or len(result) != 3:
        text = f"{TYPE_ERROR_PREFIX}：預期 (序列, 錯誤, 配息) 三元組，收到 {type(result).__name__}"
        return None, text, {"items": None, "outcome": None, "error": text}
    return result


def _div_date_text(value) -> Optional[str]:
    """配息日期字串 → `YYYY-MM-DD`；只收**恰好** `YYYY-MM-DD` 或 `YYYY/MM/DD`（補零、十個字元），其餘回 None。
    只換分隔符號，不交給 pandas 去猜（民國年、`9/1`、英文月份一律不收）。"""
    if not isinstance(value, str) or len(value) != 10:
        return None
    if value[4] == "/" and value[7] == "/":
        value = value.replace("/", "-")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return value if parsed.isoformat() == value else None


def _outcome_detail(outcome) -> str:
    if not isinstance(outcome, dict):
        return "A 鏈沒有交出配息取數狀態"
    lines = []
    for src in outcome.get("sources") or ():
        if isinstance(src, dict):
            pt = f"[{src.get('page_type')}] " if src.get("page_type") else ""
            lines.append(f"{pt}{src.get('source')}：{src.get('status')}"
                         + (f"（{src['detail']}）" if src.get("detail") else ""))
    if outcome.get("legacy_inline_parse"):
        lines.append("A 鏈另走了 legacy 段的 wb05 內嵌解析（該段沒有取數狀態）")
    return "\n".join(lines) or f"狀態 {outcome.get('outcome')!r}，沒有逐來源紀錄"


def _resolve_div_holding(holding_ccys, *, label_source=LABEL_SOURCE_HOLDING):
    """持倉手填幣別 → `(標籤, withheld 代碼, 理由)`；與 `resolve_nav_ccy` 對持倉那一側的判法相同
    （意思不一致 → 衝突；沒有合格 ISO 4217 的值 → 缺），標籤用持倉原值、不改寫。
    `label_source`（2026-10-14 C3a）：`holding_ccys` 的出處；只決定理由文案的字樣（`_label_words`），判法不變。"""
    row = _label_words(label_source)["row"]
    values = [c for c in holding_ccys if not _is_blank_ccy(c)]
    if len({_ccy_meaning(c) for c in values} - {None}) > 1:
        return None, WITHHELD_CCY_CONFLICT, f"{row}幣別意思不一致（{', '.join(repr(c) for c in values)}）"
    label = next((c for c in values if _iso_ccy(c)), None)
    if label is None:
        shown = f"（{row}幣別：{', '.join(repr(c) for c in values)}）" if values else ""
        return None, WITHHELD_CCY_MISSING, f"{row}沒有可用的幣別" + shown
    return label, None, None


def rows_from_chain_dividends(fund_code: str, div, *, holding_ccys=(), now=None,
                              label_source=LABEL_SOURCE_HOLDING) -> dict:
    """單一檔基金、A 鏈同一次呼叫交出的配息 → `{rows, error, withheld, pending, skipped, fetched, skipped_rows,
    provenance, settled}`（純函式）。

    - `div["error"]` 非空：原文照回、不寫列。`items` 不是 list：型別錯誤進 `error`。
    - 空清單：`dividends_fetch_outcome` 為 none_confirmed → 不寫列、`settled` 為真（確實沒有配息）；
      failed → `error`（逐來源原文）；其餘 → `withheld = div_outcome_undetermined`（分辨不出，不當成沒有配息）。
    - 有列：逐筆核對日期出處（`DIV_EX_DATE_EVIDENCE`）、日期格式、幣別出處（`DIV_CCY_EVIDENCE`）；
      幣別規則同淨值 —— **標籤用持倉手填**；來源宣告的幣別（經 L1 `_normalize_declared_ccy` 對照中文名）與持倉
      不同或認不出 → **整檔不寫**；來源沒宣告 → 那一筆不寫（整檔都沒宣告 → `ccy_not_source_reported`）。
    - 過關的列交給 `rows_from_dividends`（金額、`fetched_at`、主鍵、契約檢查同舊路徑）；`div_kind` 一律 `unknown`（Q5）、
      `pay_date` 一律空值；`fetched_at` 取 L1 逐筆記下的取得時間（`div_provenance["fetched_at"]`），不以當下時間補。
    - `settled`：A 鏈交出的每一筆都寫成列（或同日同額合併）、而且供列的那個來源自報取數狀態為 `rows`
      —— 只有這時「這一檔的配息就是這幾列」才成立；否則為假（hld 據此不把缺列說成「區間內無配息」）。
      2026-10-13 稽核回修：另要求供列來源回報的丟列數恰為 0（必修 1a：只讀前 59 列、被過濾、沒看的其他表）；
      空清單要 `none_confirmed` **而且** `none_evidenced`（必修 3：每個回空的來源本輪都認得這個代碼）。
    - 金額欄（必修 2）：出處要在 `DIV_AMOUNT_EVIDENCE` 內；合庫另要求表頭格數與列格數相同。
    - `provenance["coverage_start"]`（必修 1b）：寫出的列裡最舊的除息日；hld 據此判所選區間有沒有證據。
    - `label_source`（2026-10-14 C3a）：`holding_ccys` 的出處（預設持倉手填）。`provenance["ccy_source"]` ＝
      `f"{label_source}_matches_source"`（⚠️ 是出處字串，**不是**幣別值 `label`）；文案字樣依它決定，判法不變。
    """
    out = _empty_out()
    out.update(pending=None, settled=False)
    if not isinstance(div, dict):
        div = {"items": None, "outcome": None,
               "error": f"{TYPE_ERROR_PREFIX}：配息輸入預期 dict，收到 {type(div).__name__}"}
    outcome = div.get("outcome")
    outcome_name = outcome.get("outcome") if isinstance(outcome, dict) else None
    out["provenance"] = {"source": None, "fetched_at": None, "ccy_source": None, "outcome": outcome_name,
                         "outcome_detail": None if div.get("error") else _outcome_detail(outcome),
                         "settled": False}
    if div.get("error"):
        out["error"] = str(div["error"])
        return out
    items = div.get("items")
    if not isinstance(items, list):
        out["error"] = f"{TYPE_ERROR_PREFIX}：dividends 預期 list，收到 {type(items).__name__}"
        return out
    if not items:
        # 2026-10-13 稽核必修 3：none_confirmed 還要 `none_evidenced`（每個回空的來源，本輪都認得這個代碼）
        if outcome_name == DIV_OUTCOME_NONE and outcome.get("none_evidenced") is True:
            out["skipped"].append(TEXT_DIV_NONE)
            out["settled"] = out["provenance"]["settled"] = True
        elif outcome_name == DIV_OUTCOME_NONE:
            out["withheld"] = WITHHELD_DIV_OUTCOME_UNDETERMINED
            out["skipped"].append(TEXT_DIV_NONE_UNEVIDENCED.format(detail=_outcome_detail(outcome)))
        elif outcome_name == DIV_OUTCOME_FAILED:
            out["error"] = TEXT_DIV_FAILED.format(detail=_outcome_detail(outcome))
        else:
            out["withheld"] = WITHHELD_DIV_OUTCOME_UNDETERMINED
            out["skipped"].append(TEXT_DIV_UNDETERMINED.format(detail=_outcome_detail(outcome)))
        return out

    n = len(items)
    out["fetched"] = n
    label, held_code, held_why = _resolve_div_holding(holding_ccys, label_source=label_source)
    if held_code:
        out["withheld"] = held_code
        out["skipped"].append(f"{held_why}，配息 {n} 筆全部不寫")
        return _reconcile(out, n, "dividend")

    rejected: dict = {}
    date_unverified = ccy_undeclared = 0
    conflicts = []
    accepted = []
    parsers = set()
    for item in items:
        if not isinstance(item, dict):
            _tally(rejected, "不是 dict")
            continue
        prov = item.get(DIV_PROVENANCE_KEY)
        parser = prov.get("parser") if isinstance(prov, dict) else None
        rule = DIV_EX_DATE_EVIDENCE.get(parser)
        if rule is None:
            _tally(rejected, TEXT_DIV_NO_PROVENANCE)
            date_unverified += 1
            continue
        date_key, field_key, accept = rule
        if prov.get(field_key) not in accept:
            _tally(rejected, TEXT_DIV_DATE_UNVERIFIED.format(parser=parser, field=field_key,
                                                             value=prov.get(field_key)))
            date_unverified += 1
            continue
        amount_key, amount_accept = DIV_AMOUNT_EVIDENCE[parser]
        if prov.get(amount_key) not in amount_accept:
            _tally(rejected, TEXT_DIV_AMOUNT_UNVERIFIED.format(parser=parser, field=amount_key,
                                                               value=prov.get(amount_key)))
            date_unverified += 1
            continue
        if parser == DIV_PARSER_TCB and _tcb_cells_mismatch(prov):
            _tally(rejected, TEXT_DIV_CELLS_MISMATCH.format(hdr=prov.get("header_cells"), td=prov.get("row_td_cells"),
                                                            th=prov.get("row_th_cells"),
                                                            span=prov.get("table_has_span")))
            date_unverified += 1
            continue
        day = _div_date_text(item.get(date_key))
        if day is None:
            _tally(rejected, TEXT_DIV_DATE_FORMAT.format(value=item.get(date_key)))
            continue
        ccy_rule = DIV_CCY_EVIDENCE.get(parser)
        declared = item.get("currency") if ccy_rule and prov.get(ccy_rule[0]) in ccy_rule[1] else None
        if _is_blank_ccy(declared) or not str(declared).strip():
            _tally(rejected, TEXT_DIV_CCY_UNDECLARED.format(parser=parser))
            ccy_undeclared += 1
            continue
        if _normalize_declared_ccy(declared) != _ccy_meaning(label):
            conflicts.append(declared)
            continue
        parsers.add(parser)
        accepted.append({"date": day, "amount": item.get("amount"), "currency": label,
                         "fetched_at": prov.get("fetched_at"), "source": parser})

    if conflicts:
        shown = "、".join(repr(c) for c in conflicts[:5]) + ("…" if len(conflicts) > 5 else "")
        out["withheld"] = WITHHELD_CCY_CONFLICT
        if label_source == LABEL_SOURCE_HOLDING:
            out["skipped"].append(TEXT_DIV_CCY_CONFLICT.format(shown=shown, holding=label, n=n))
        else:
            out["skipped"].append(TEXT_DIV_CCY_CONFLICT_LABELED.format(
                label=_label_words(label_source)["input"], shown=shown, holding=label, n=n))
        return _reconcile(out, n, "dividend")

    n_rejected = sum(rejected.values())
    inner = rows_from_dividends(fund_code, accepted, None, now=now) if accepted else None
    if inner is not None:
        out["rows"] = inner["rows"]
        out["skipped"].extend(inner["skipped"])
        out["withheld"] = inner["withheld"]
    out["skipped"].extend(_tally_lines(rejected, ""))
    if not out["rows"] and out["withheld"] is None:
        if inner is None and date_unverified == n_rejected:
            out["pending"] = PENDING_DIV_EX_DATE_UNVERIFIED
        elif inner is None and ccy_undeclared == n_rejected:
            out["withheld"] = WITHHELD_CCY_NOT_SOURCE_REPORTED
        else:
            out["withheld"] = WITHHELD_DIV_ITEMS_REJECTED
    # 供列的來源：自報 `rows`，而且（稽核必修 1）回報的丟列數恰為 0 —— 算不出來（None）也算有丟列。
    suppliers = [s for s in (outcome.get("sources") if isinstance(outcome, dict) else None) or ()
                 if isinstance(s, dict) and s.get("parser") in parsers]
    supplier_ok = outcome_name == DIV_OUTCOME_ROWS and all(
        any(s.get("parser") == p and s.get("status") == DIV_STATUS_ROWS for s in suppliers) for p in parsers)
    dropped_ok = bool(suppliers) and all(div_dropped_total(s) == 0 for s in suppliers)
    if out["rows"] and not dropped_ok:
        out["skipped"].append(TEXT_DIV_DROPPED.format(
            detail="；".join(f"{s.get('source')}：{s.get('dropped')!r}" for s in suppliers) or "沒有逐來源紀錄"))
    inner_clean = inner is not None and inner["skipped_rows"] == inner["merged"]
    out["settled"] = bool(out["rows"]) and n_rejected == 0 and inner_clean and supplier_ok and dropped_ok
    times = sorted(r["fetched_at"] for r in out["rows"])
    # 稽核必修 1(b)：覆蓋期間起點 ＝ 寫出的列裡最舊的除息日（hld 據此判斷所選區間有沒有證據）
    out["provenance"].update(source=sorted(parsers) or None, fetched_at=times[-1] if times else None,
                             # C3a：`label_source`（出處字串），不是 `label`（幣別值）—— 否則 hld 會變成 "USD_matches_source"
                             ccy_source=f"{label_source}_matches_source" if out["rows"] else None,
                             settled=out["settled"],
                             coverage_start=min((r["ex_date"] for r in out["rows"]), default=None))
    return _reconcile(out, n_rejected + (inner["skipped_rows"] if inner is not None else 0), "dividend")


def build_nav_dividend_tables(funds, *, now=None, chain_fetch=None) -> dict:
    """hld 用：**同一次** A 鏈呼叫組出 `nav` 與 `dividend` 兩張表 → `{"nav": ..., "dividend": ...}`。

    - `funds` 每筆給 `holding_ccy`（持倉手填，hld）或 `declared_ccy` ＋ `declared_ccy_source`（meta 頁自報，
      2026-10-14 C3a；exp 之後才會接上），同一次呼叫只能一種（見 `_group_funds`）。
    - `chain_fetch`（2026-10-14 C3a）：可注入的 A 鏈取數（介面同 `fetch_chain_with_error`）；None ＝ 預設
      `fetch_chain_with_error`。

    - `nav`：與 `build_nav_table(funds, now=now)` 逐鍵相同（同一個迴圈、同一個判讀）。
    - `dividend`：`{"rows", "errors", "pending", "withheld", "skipped", "fetched", "skipped_rows", "provenance",
      "settled"}`，皆以 `fund_code` 為鍵（`rows` 除外）；`settled[代碼]` 見 `rows_from_chain_dividends`。
      `fetched`／`skipped_rows` 射程同 `build_nav_table`（`input_conflict` 的檔沒有這兩個鍵）。
    """
    return _build_tables(funds, now=now, with_dividends=True, chain_fetch=chain_fetch)
