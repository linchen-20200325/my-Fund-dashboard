# -*- coding: utf-8 -*-
"""正式模式的 Answer-first 四段重排（Phase 3 P1-④；`docs/v2/44_fund_ui_ssot.md` 第七節第三小節之八其一，
客戶裁示 `DEC-2026-10-17-07` 第 (a-1)～(a-4) 題）。

純函式模組：**不 import streamlit、不 import 舊樹、不 import 任何模組**（`tests/ui_v2/test_ui_v2_live_import_guard.py`）。
各頁 logic 的狀態字面在本檔放鏡像常數，由 `tests/ui_v2/test_sections_logic.py` 逐字比對真身。

輸入一律是各頁正式模式已走完 `plain.plain_model` → `symbols.apply` → `health` 那幾步的一般畫面模型（已深拷貝）；
本模組只做三件事：

1. **層次歸屬**（`relayer`，(a-1) 選項 A）：標的探索 `EXP-2` → 層 3、`EXP-3` → 層 4；資產配置 `ALO-1` → 層 3。
   移入層 3／層 4 的塊 `_default_open` 改為假（44 第五節第四小節「層 3 與層 4 的 `default_open` 為假」）。
   持倉體檢 `HLD-1` **結構上照舊屬層 2**、`_default_open` 照舊為真，只是畫面上畫在 ③（之八其一 (a-1) 第 2 條）——
   本模組不動它的層，畫在哪裡由 `page.py` 決定。`ALO-3` 留在層 2（同條第 4 條）。
2. **③需要注意的內容**（`attention_items`）：只讀本頁已經算出來的結果，不自己取數、不新增判定；沒有就回空串列（不列）。
   - 市場總覽：`MKT-0` 從三張核心卡讀到的資料面例外（三張卡的 `_state`），合成「資料面」那一行；
     不畫「變化大不大」、不寫「沒有例外」（(a-3)、(a-4) 選項 B）。
   - 標的探索：`EXP-0` 已算出的無法判定檔數（`_undet_count`，與燈上「另有 M 檔無法判定」同一個數）。
   - 資產配置：`ALO-2` 已算出的帶外類別（`band_text` 為「外」的那幾列）。
   - 持倉體檢：③ 由 `HLD-1` 整塊撐起（`page.py` 直接畫那一塊）；本模組只在偏離列的基金名前加 `◆`（`mark_hld1_rows`）。
3. **持倉體檢 ① 的三個計數**（`hld_counts`，(a-2) 選項 B）：持有 n 檔、`◆ 需要注意` m 檔、`⬜ 無法判定` j 檔 ——
   m ＝ `HLD-0` 的偏離檔數（`_deviation_count`，燈上「有 N 檔超出」的 N）、j ＝ `HLD-1` 已彙總的「沒有進入偏離評估」的
   不重複檔數（`_unevaluated_count`，不論成因；2026-10-18 更正，見 44 之八其一 (a-2) 第 1 條）、n ＝ `HLD-2` 已讀到的不重複基金代碼數（三個數同一個單位；`fund_groups` 是逐筆持倉分組，同檔兩張保單只算 1）。不寫 `○`、不寫「正常」，不列持有減另兩數的差。

4. **設定與診斷**（Phase 3 P1-⑥，之八其二 (b-1)～(b-4)、其三 (c-1)；`set_reshape`）：`SET-2` → 層 4、`SET-3` → 層 3；
   `SET-0` 黃燈那一句改「◷ N 類資料超過你設的上限」、設定試算表未設定時改出空狀態欄第三句；`SET-1` 比較欄「外」前加 `◷`；
   ③ 由 `SET-1` 已算出的「外」那幾列撐起（`set_attention`）。
5. **客戶 2026-10-18 裁示**（`DEC-2026-10-18-01`；44 第七節第三小節之九）：
   - BL-0371：沒有異常時省略整體正常宣告 —— 正式與示範模式皆同，改在各頁 logic（`ui_v2/mkt/logic.py`、`ui_v2/set/logic.py`），
     本模組不經手。
   - BL-0373：市場總覽 `MKT-7` 取數失敗的鍵不掛「資料未備」，改「取數失敗」、四格 `⛔`；`MKT-5` 可選項目同一批鍵改掛「取數失敗」
     （`mark_mkt7_fetch_failed`）；`MKT-6` 表尾那一句依成因改寫（`mark_mkt6_fetch_failed`）。
   - S1／C1：設定試算表未設定 → 第三句優先於由此衍生的讀取失敗；服務帳戶也未設定時維持 ⛔（`set_conclusion`）。

**不做什麼（護欄 2）**：不改任何 `_state`、顏色、門檻、算法、資料來源與寫入；不新增按鈕；不改任何一格的文案字面
（③ 的字句是本組依 59 線框擬的，見各函式）。**示範模式不經過本模組**（44 第七節第三小節之八開頭第 4 條）。
例外（44 字面明訂的，只在設定與診斷頁）：`SET-0` 在設定試算表未設定時改灰、改出第三句（之八其三 (c-1)），黃燈那一句換字面
（之八其二 (b-2) 第 3 條）；`SET-1` 比較欄「外」加 `◷`（之七其四）。判定（逾期數、失敗來源、內外）一個都不動。
"""

from __future__ import annotations

from . import page_health

# ───────────────────────── 鏡像常數（真身在各頁 logic；測試逐字比對） ─────────────────────────

STATE_OK = "ok"
STATE_MISSING = "資料未備"
STATE_BIZ = "業務例外"
STATE_ERROR = "系統錯誤"

HLD_TEXT_NO_HOLDING = "尚未建立任何持倉"
HLD_TEXT_NO_RULES = "尚未設定門檻"
ALO_TEXT_OUT = "外"

# ───────────────────────── 層次歸屬（之八其一 (a-1) 選項 A） ─────────────────────────

RELAYER = {
    "exp": {"EXP-2": 3, "EXP-3": 4},
    "alo": {"ALO-1": 3},
    # Phase 3 P1-⑥（之八其二 (b-2) 選項 B 第 1 條；歸屬理由見之八其一 (a-1) 第 3 條）：
    # `SET-3` 規則參數卡 → 層 3（④「操作」，與 `SET-4` 參數編輯同一組）、`SET-2` 來源健康卡 → 層 4（④「證據／來源」）。
    "set": {"SET-2": 4, "SET-3": 3},
}

# 持倉體檢 ③ 畫的那一塊（結構上照舊屬層 2）。
HLD_ATTENTION_CODE = "HLD-1"
# 標的探索 ④ 合成一個「結果清單」框的兩塊（59 第 4.2 節；之八其一 (a-1) 第 3 條）。
EXP_RESULT_CODES = ("EXP-2", "EXP-3")
EXP_RESULT_TITLE = "結果清單"
# 資產配置 `ALO-3` 在 ② 預設只畫一枚 `展開` 類入口（之八其一 (a-1) 第 4 條；59 第 5.1 節［開始試算］）。
ALO_SCENARIO_CODE = "ALO-3"
ALO_SCENARIO_ENTRY = "開始試算"

# ───────────────────────── ③ 的字面（本組依 59 線框擬定） ─────────────────────────

SYMBOL_ATTENTION = "◆"
SYMBOL_MISSING = "◇"
SYMBOL_UNDECIDABLE = "⬜"
SYMBOL_ERROR = "⛔"

MKT_DATA_PREFIX = "資料面："
# 卡片狀態 → 這一張卡在 ③ 寫什麼（符號照之七其四：資料未備 ◇、不適用 ⬜、`系統錯誤` ⛔）。字樣照 `MKT-0` 燈點名卡片時
# 的同一組（`ui_v2/mkt/logic.py::_STATE_IN_LIGHT_TEXT`）。`系統錯誤` 只留狀態族「⛔ 取數失敗」：失敗摘要只在頁首資料狀態行
# 出現一次，「此區塊暫時無法判定」一塊只寫一次、寫在該塊自己身上（之七其二第 3 條；`ui_v2/health.py`）。
_MKT_STATE_WORDS = {
    STATE_MISSING: f"{SYMBOL_MISSING} 資料未備",
    STATE_BIZ: f"{SYMBOL_UNDECIDABLE} 不適用",
    STATE_ERROR: f"{SYMBOL_ERROR} 取數失敗",
}
# 同一張卡兩者並陳時的書寫順序（真身 `ui_v2/mkt/logic.py::_UNRANKED_PAIR`；不是嚴重度）。
_MKT_UNRANKED_ORDER = (STATE_MISSING, STATE_BIZ)
MKT_CARD_CODES = ("MKT-1", "MKT-2", "MKT-3")

EXP_UNDET_TEXT = "{m} 檔無法判定：照列在結果清單中，不算符合、不排除"
ALO_OUT_TEXT = "{bucket} 超出容許帶"

HLD_COUNTS_TEXT = "持有 {n} 檔　{attention} 需要注意 {m} 檔　{undecidable} 無法判定 {j} 檔"


def _find(model: dict, code: str):
    """找塊；找不到就 `KeyError`（本模組讀的每一塊都是該頁固定有的塊，不見了是 bug，不以空值代替）。"""
    for block in model["blocks"]:
        if block["code"] == code:
            return block
    raise KeyError(f"頁面模型裡沒有 {code}")


def relayer(model: dict, page: str) -> list:
    """把本頁移層的塊改到新層（就地改寫），回改到的塊代號。不在 `RELAYER` 的頁原樣不動。"""
    moved = []
    for code, layer in RELAYER.get(page, {}).items():
        block = _find(model, code)   # 移層對象不見了 → KeyError，不得靜默略過
        block["_layer"] = layer
        block["_default_open"] = False
        moved.append(code)
    return moved


# 各頁資料狀態總表（`SET-8`）裡的「核心卡」：改層之後仍在層 2、而且在 ② 畫成一張卡的塊（3-B 稽核回修第 4 條）。
# 改層前的三張核心卡照舊用於頁上的徽章搬移與資料狀態行（那兩步一字不動）；本表只給總表的件數與「（N 張卡有值讀不到）」用。
# `ALO-3` 在 ② 只畫一枚「開始試算」入口、不是一張卡（線框第六版 5.2 那一例「持倉取數失敗（1 張卡有值讀不到）」）。
HEALTH_ENTRY_ONLY = {"alo": (ALO_SCENARIO_CODE,)}
# 3-B 第二輪稽核回修 D（決策者：AI 總管）：標的探索的核心卡照客戶裁示原文「EXP 三張核心卡」，`EXP-1`～`EXP-3` 都算，
# 改層不扣（客戶的字面優先於從 44 推導的定義）。其他頁照舊：`ALO-1` 移到 ④、`ALO-3` 只是入口，不算。
HEALTH_KEEP_MOVED = ("exp",)


def health_cards(codes, page: str) -> list:
    """`codes`：改層前的層 2 塊代號（各頁 `logic.codes_in_layer(model, 2)`）→ 總表用的核心卡（順序不變；純函式，不改模型）。"""
    moved = {} if page in HEALTH_KEEP_MOVED else RELAYER.get(page, {})
    entries = HEALTH_ENTRY_ONLY.get(page, ())
    return [code for code in codes if moved.get(code, 2) == 2 and code not in entries]


def _item(symbol: str, text: str, tone: str) -> dict:
    return {"symbol": symbol, "text": text, "_tone": tone}


# 客戶 2026-10-19 裁示 G3（`DEC-2026-10-19-04`，BL-0250 批次 1）：該塊的失敗全部屬「尚未設定」那一族時（`health.relabel_unconfigured`
# 在塊上記的 `_unconfigured`），③ 與入口標題寫「⛔ 尚未設定：<哪一項>」，不寫「⛔ 取數失敗」。⛔ 照舊（判定照舊是 `系統錯誤`）。
UNCONFIGURED_KEY = "_unconfigured"   # 真身 `ui_v2/health.py::UNCONFIGURED_KEY`（測試比對）
TEXT_NOT_CONFIGURED = "尚未設定"


def _unconfigured_line(names) -> str:
    return f"{SYMBOL_ERROR} {TEXT_NOT_CONFIGURED}：{'、'.join(names)}"


def _mkt_words(card: dict) -> list:
    state = card["_state"]
    if state == STATE_ERROR and card.get(UNCONFIGURED_KEY):
        return [_unconfigured_line(card[UNCONFIGURED_KEY])]
    if state in _MKT_STATE_WORDS:
        return [_MKT_STATE_WORDS[state]]
    if state is None:
        # 卡上同時有資料未備與業務例外的主值（logic 的哨符狀態）：兩件事都真的發生了，兩個都寫。
        present = {mv["_state"] for mv in card["main_values"]}
        return [_MKT_STATE_WORDS[s] for s in _MKT_UNRANKED_ORDER if s in present] or [
            _MKT_STATE_WORDS[s] for s in _MKT_UNRANKED_ORDER
        ]
    return []


def mkt_attention(model: dict) -> list:
    """市場總覽 ③：三張核心卡裡狀態不是 `ok` 的那幾張，合成一行「資料面：<卡名> <狀態>；…」。全是 `ok` → 空串列。
    顏色讀 `MKT-0` 已算出的燈色（`_tone`；灰／黃／紅），不另判（2026-10-18 獨立稽核必修 2）。"""
    light = _find(model, "MKT-0")
    parts = []
    for code in MKT_CARD_CODES:
        card = _find(model, code)
        if card["_state"] == STATE_OK:
            continue
        words = _mkt_words(card)
        if words:
            parts.append(f"{card['title']} {'／'.join(words)}")
    if not parts:
        return []
    return [_item("", MKT_DATA_PREFIX + "；".join(parts), light["_tone"])]


def exp_attention(model: dict) -> list:
    """標的探索 ③：`EXP-0` 已算出的無法判定檔數（`_undet_count`，正式模式一定有這個鍵）大於零時一行；否則空串列。"""
    count = _find(model, "EXP-0")["_undet_count"]
    if count <= 0:
        return []
    return [_item(SYMBOL_UNDECIDABLE, EXP_UNDET_TEXT.format(m=count), "灰")]


def alo_attention(model: dict) -> list:
    """資產配置 ③：`ALO-2` 算出帶外（「外」）的每一個類別一行，依 `ALO-2` 的列序；沒有就空串列。"""
    alo2 = _find(model, "ALO-2")
    return [
        _item(SYMBOL_ATTENTION, ALO_OUT_TEXT.format(bucket=row["bucket_text"]), "中性")
        for row in alo2["_rows"]
        if row["band_text"] == ALO_TEXT_OUT
    ]


def attention_items(model: dict, page: str) -> list:
    """③需要注意要列的項目（`[{"symbol", "text", "_tone"}]`）。持倉體檢由 `HLD-1` 整塊撐起，這裡回空串列。"""
    if page == "mkt":
        return mkt_attention(model)
    if page == "exp":
        return exp_attention(model)
    if page == "alo":
        return alo_attention(model)
    if page == "hld":
        return []
    if page == "set":
        return set_attention(model)
    raise ValueError(f"沒有這一頁：{page!r}")


def mark_hld1_rows(model: dict) -> int:
    """持倉體檢 ③ 的偏離列：基金名前加 `◆ `（就地改寫），回改了幾列。只改畫面字串，`_` 開頭的鍵一個都不碰。"""
    block = _find(model, HLD_ATTENTION_CODE)
    count = 0
    for row in block["_rows"]:
        name = row["fund_name"]
        if isinstance(name, str) and not name.startswith(SYMBOL_ATTENTION):
            row["fund_name"] = f"{SYMBOL_ATTENTION} {name}"
            count += 1
    return count


def hld_counts(model: dict):
    """持倉體檢 ① 的三個計數那一行；不該列時回 None。字串由 `hld_count_values` 的 (n, m, j) 組成（BL-0525 Batch D 抽出，算法不變）。"""
    values = hld_count_values(model)
    if values is None:
        return None
    n, m, j = values
    return HLD_COUNTS_TEXT.format(n=n, attention=SYMBOL_ATTENTION, m=m, undecidable=SYMBOL_UNDECIDABLE, j=j)


def hld_count_values(model: dict):
    """持倉體檢 ① 的三個計數 `(n, m, j)`；不該列時回 None。

    只在「有持倉、門檻已設、燈不是紅」時列：沒有持倉或門檻未設時燈的那一句就是答案（59 第 3.3、3.4 節），
    紅燈時這一頁的數字先不要照著讀（`HLD-0` 紅燈文案），列計數會把讀不到的說成讀到了。
    鍵一律直讀（缺鍵就 `KeyError`，不以 0 代替）。n ≥ m ＋ j 不成立時當場炸（m 與 j 互斥，都是持倉的子集）。
    """
    light, hld1, hld2 = _find(model, "HLD-0"), _find(model, "HLD-1"), _find(model, "HLD-2")
    if light["_tone"] == "紅" or light["text"] in (HLD_TEXT_NO_HOLDING, HLD_TEXT_NO_RULES):
        return None
    # n、m、j 同一個單位：不重複基金代碼數（總管 2026-10-18 裁定）。`fund_groups` 是逐筆持倉（保單 × 基金代碼）分組，
    # 同一檔分在兩張保單時有兩組 ⇒ 只數不重複的 `_fund_code`；HLD-2 顯示的內容一格不動。
    n = len({group["_fund_code"] for group in hld2["fund_groups"]})
    if n == 0:
        return None
    m, j = light["_deviation_count"], hld1["_unevaluated_count"]
    if n < m + j:
        raise ValueError(f"持倉體檢計數不成立：持有 {n} 檔 < 需要注意 {m} 檔 ＋ 無法判定 {j} 檔")
    return n, m, j


_FAMILY_FETCH_FAILED = f"{SYMBOL_ERROR} 取數失敗"
_FAMILY_MISSING = f"{SYMBOL_MISSING} 資料未備"


def _placeholder_family(placeholder: dict, unconfigured=None) -> str:
    """佔位 → 摘要那一行的狀態族。`系統錯誤` 只留「⛔ 取數失敗」（「此區塊暫時無法判定」一塊只寫一次，已寫在卡上；
    之七其二第 3 條）；該塊的失敗全部屬尚未設定（`unconfigured`）時寫「⛔ 尚未設定：<哪一項>」（客戶 G3）；
    其餘照佔位自己那一句（已經過 `symbols`，資料未備是 ◇）。只讀既有的 `_empty_kind`，不另判。"""
    if placeholder["_empty_kind"] == STATE_ERROR:
        return _unconfigured_line(unconfigured) if unconfigured else _FAMILY_FETCH_FAILED
    return placeholder["text"]


def alo1_summary(block: dict) -> str:
    """`ALO-1` 移進 ④ 之後收合時的摘要那一行（44 第五節第四小節：缺了什麼在摘要那一行就看得見、不把空狀態藏進展開內容）。
    只拼卡上已經有的字：佔位 → 狀態族；否則類別數或「未設定」，有類別的目標比重缺值（`_weight` 為 None，卡上寫資料未備）
    → 加「◇ 資料未備」，再加容許帶那一句。"""
    placeholder = block["placeholder"]
    if placeholder:
        return _placeholder_family(placeholder, block.get(UNCONFIGURED_KEY))
    rows = block["_rows"]
    parts = [f"{len(rows)} 個類別"] if rows else list(block["unset_lines"])
    if any(row["_weight"] is None for row in rows):
        parts.append(_FAMILY_MISSING)
    parts += list(block["tolerance_lines"])
    return "；".join(parts)


def alo3_entry_title(block: dict) -> str:
    """`ALO-3`「開始試算」入口那一枚展開區的標題：卡為空狀態或取數失敗時帶出狀態族
    （「開始試算　—　◇ 資料未備」「開始試算　—　⛔ 取數失敗」；44 第五節第四小節「不把空狀態藏進展開內容」）。
    只讀卡上既有的佔位（`placeholder` 與它的 `_empty_kind`），不另判；沒有佔位時只寫「開始試算」。"""
    placeholder = block["placeholder"]
    if not placeholder:
        return ALO_SCENARIO_ENTRY
    return f"{ALO_SCENARIO_ENTRY}　—　{_placeholder_family(placeholder, block.get(UNCONFIGURED_KEY))}"


# ───────────────────────── 設定與診斷（Phase 3 P1-⑥；之八其二 (b-1)～(b-4)、其三 (c-1)） ─────────────────────────
# 鏡像常數：真身在 `ui_v2/set/logic.py`（`TEXT_OUT`、`EMPTY_GLYPH`、`conclusion_light`／`_build_set0` 的字面），測試逐字比對。

SET_TEXT_OUT = "外"
SET_STATE_OVERDUE = "有逾期"
SET_STATE_EMPTY = "空狀態"
SET_EMPTY_GLYPH = "⬜"
SET_STATE_WORD_EMPTY = "狀態：尚不足以判定"
SYMBOL_STALE = "◷"
SET_EMPTY_KIND_NO_SOURCE = "來源缺"
# ~~`SET_LOG_TABLE = "fetch_log"`~~（只給 `set2_summary`「缺 fetch_log：」那一句用；BL-0250 批次 3-C 那一句拿掉後同次刪除）
# 正式模式 `SET-3` 壞列的目前值（真身 `ui_v2/set/live.py::TEXT_BAD_ROWS` 以 n=1 帶入）。
SET_BAD_ROW_TEXT = "⚠ 1 列格式不符，未採用"

# 44 `SET-0` 規則欄（之八其二 (b-2) 第 3 條）：黃燈那一句改寫；N 的算法照舊（`SET-1` 一列一類，逾期筆數就是逾期類數）。
SET_OVERDUE_TEXT = SYMBOL_STALE + " {n} 類資料超過你設的上限"
# 44 `SET-0` 空狀態欄第三句（之八其三 (c-1)）：只寫狀態，不寫操作指引。
SET_NO_SHEET_TEXT = f"{SET_EMPTY_GLYPH} 無法判定：尚未設定設定試算表"
# ③需要注意：`SET-1` 已算出的「外」那幾列（之八其二 (b-2) 第 4 條）；字句是本組依 59 第 6.1 節擬的（59 原寫「超過你設的上限
# ‹n› 日」，‹n› 為上限；本組改寫距今日數，上限值不從字串裡拆，避免把「上限 n 日」讀成「超過 n 日」）。
SET_ATTENTION_TEXT = "{kind}：距今 {days} 日，超過你設的上限"
# `SET-0` 燈旁那一枚 `導覽`（之八其二 (b-1) 第 2 條）：同頁錨點，只捲到 ④ 的 `SET-5`；不觸發取數、重新整理、存檔或寫入。
SET_NAV_LABEL = "前往重新取數"
SET_NAV_ANCHOR = "set-refetch"
SET_REFETCH_CODE = "SET-5"
# 市場總覽狀態徽章「取數失敗」（真身 `ui_v2/mkt/logic.py::_status_badge("取數失敗")`；44 第五節第二小節七個字面值之一）。
MKT_BADGE_FETCH_FAILED = {"_kind": "狀態", "_tone": "黃", "text": "取數失敗"}
MKT_BADGE_MISSING_TEXT = "資料未備"
MKT7_CELLS = ("obs_text", "fetched_text", "tier_text", "delay_text")
# `MKT-6` 一筆觀測也沒有時的那一句（真身 `ui_v2/mkt/logic.py::empty_source_text(["market_indicator"])`；`plain` 之前的形狀）與取代它的狀態族。
MKT6_EMPTY_LINE = "⬜ 資料未備：market_indicator 尚無資料"
LINE_FETCH_FAILED = f"{SYMBOL_ERROR} 取數失敗"
MKT_NOT_CONFIGURED = "尚未設定"   # BL-0250 批次 3-A：`MKT-5`／`MKT-6`／`MKT-7` 成因是設定沒設的那幾處（`ui_v2/health.py::TEXT_NOT_CONFIGURED` 同字，測試比對）


def set_conclusion(model: dict, *, sheet_configured: bool, service_account_configured: bool = True) -> None:
    """`SET-0` 的改寫（就地）：

    - 設定試算表未設定 → 燈為灰、文案「⬜ 無法判定：尚未設定設定試算表」；與空狀態欄另兩句、由此衍生的讀取失敗同時成立時
      以這一句為準（之八其三 (c-1)；客戶 2026-10-18 裁示 S1，`DEC-2026-10-18-01`）。圖示與狀態字照本頁空狀態那一組。
    - **例外（C1）**：服務帳戶也未設定（`service_account_configured` 為假）時不出第三句 —— 缺服務帳戶是取數能力失敗，
      不是由設定試算表未設定衍生的；燈維持 `live.apply_live_notes` 已畫好的 ⛔（與只缺服務帳戶時同一盞），本函式不動它
      （客戶 2026-10-18 裁示 C1；兩者同時成立時採保守 ⛔ ＝ 總管指定讀法，可被客戶推翻）。
    - 黃燈（`_state` 為「有逾期」）→ 文案改「◷ N 類資料超過你設的上限」，N 取 `SET-1` 已算出的逾期數；燈色、圖示照舊。
    其餘情形（紅、另兩句空狀態、兩個計數皆為零那一支）一字不動（後者 logic 已不寫文案，客戶 2026-10-18 裁示 BL-0371）。
    """
    light = _find(model, "SET-0")
    if not sheet_configured:
        if not service_account_configured:
            if light["_tone"] != "紅":
                raise ValueError(f"服務帳戶與設定試算表皆未設定，SET-0 卻不是紅燈（{light['_tone']}）")
            return
        light.update(_tone="灰", _state=SET_STATE_EMPTY, glyph=SET_EMPTY_GLYPH, state_word=SET_STATE_WORD_EMPTY,
                     text=SET_NO_SHEET_TEXT, note_lines=[])
        return
    if light["_state"] == SET_STATE_OVERDUE:
        overdue = _find(model, "SET-1")["_overdue"]
        if overdue <= 0:
            raise ValueError(f"SET-0 為有逾期，但 SET-1 的逾期數是 {overdue}")
        light["text"] = SET_OVERDUE_TEXT.format(n=overdue)


def _set_is_out(row: dict) -> bool:
    text = row["compare_text"]
    return text == SET_TEXT_OUT or text == f"{SYMBOL_STALE} {SET_TEXT_OUT}"


def mark_set1_rows(model: dict) -> int:
    """`SET-1` 比較欄為「外」的列 → 「◷ 外」（之七其四：超過新鮮度上限的筆，文字前加 ◷；顏色照舊）。回改了幾列。
    「內」、`⬜`、「⬜ 不適用：…」一字不動；不加 `✓`、不寫「資料齊」「正常」（之八其二 (b-2) 第 2 條）。"""
    count = 0
    for row in _find(model, "SET-1")["_rows"]:
        if row["compare_text"] == SET_TEXT_OUT:
            row["compare_text"] = f"{SYMBOL_STALE} {SET_TEXT_OUT}"
            count += 1
    return count


def set_attention(model: dict) -> list:
    """設定與診斷 ③：`SET-1` 比較欄為「外」的每一列一行（依 `SET-1` 列序）；沒有就空串列（不列）。
    只讀 `SET-1` 已算出的比較結果與距今日數，不另判。"""
    return [
        _item(SYMBOL_STALE, SET_ATTENTION_TEXT.format(kind=row["_kind_label"], days=row["_days"]), "黃")
        for row in _find(model, "SET-1")["_rows"]
        if _set_is_out(row)
    ]


def set_reshape(model: dict, *, sheet_configured: bool, service_account_configured: bool = True) -> None:
    """設定與診斷頁正式模式的重排（就地）：移層（`SET-2` → 層 4、`SET-3` → 層 3）、`SET-0` 的改寫、`SET-1` 的 ◷。"""
    relayer(model, "set")
    set_conclusion(model, sheet_configured=sheet_configured, service_account_configured=service_account_configured)
    mark_set1_rows(model)


# ───────────────────────── 市場總覽（客戶 2026-10-18 裁示 BL-0373；44 第七節第三小節之九） ─────────────────────────


def mark_mkt7_fetch_failed(model: dict, failed_keys, unconfigured=None) -> int:
    """`MKT-7` 取數失敗的鍵（`failed_keys`：資料層 `errors` 裡有失敗字串的鍵）那一列：徽章「資料未備」→「取數失敗」、
    四格 `⬜` → `⛔`，並記 `_fetch_failed`；`MKT-5` 可選項目同一批鍵的「資料未備」徽章 →「取數失敗」（就地改寫）。
    回改了幾處（列＋項目）。要在 `plain` 把鍵換成中文名之前呼叫（比對的是原鍵）。

    客戶 2026-10-18 裁示 BL-0373：取數失敗＝⛔、資料未備＝◇，不得把取數失敗判成資料未備。只動「這個鍵一筆觀測也沒有、
    而且資料層回報了失敗」的那幾處（logic 已把它們與真正的資料未備分開：資料未備那幾列帶 `_missing_cells`）；
    有觀測的列（取數失敗但沿用既有列）照舊。`MKT-6` 那一句在 `plain`／`symbols` 之後由 `mark_mkt6_fetch_failed` 處理。

    `unconfigured`（BL-0250 批次 3-A，總管適用客戶 `DEC-2026-10-19-05` 第 2 點；44 第七節第三小節之十二其二第 4 條）：
    {鍵: 尚未設定的對象}（例 `{"credit_spread_pct": "資料來源的金鑰"}`）—— 資料層記成那個鍵的失敗、但成因是設定沒設
    （沒有執行取數）的那幾個鍵。那幾處不掛「取數失敗」，`MKT-7` 那一列最近觀測日格寫「⛔ 尚未設定：<哪一項>」、另三格 `⛔`、
    不掛徽章（狀態徽章七個字面值不新增第八個），記 `_unconfigured`；`MKT-5` 可選項目拿掉「資料未備」、記 `_unconfigured`
    （頁面另寫一行）。真的取數／連線失敗的鍵照舊。"""
    unconfigured = dict(unconfigured or {})
    failed = set(failed_keys or ()) - set(unconfigured)
    count = 0
    for row in _find(model, "MKT-7")["_rows"]:
        name = unconfigured.get(row["indicator_key"])
        if name is not None and not row.get("_missing_cells") \
                and any(b.get("text") == MKT_BADGE_MISSING_TEXT for b in row["badges"]):
            row["badges"] = [b for b in row["badges"] if b.get("text") != MKT_BADGE_MISSING_TEXT]
            for cell in MKT7_CELLS:
                if row[cell] == SYMBOL_UNDECIDABLE:
                    row[cell] = SYMBOL_ERROR
            row["obs_text"] = f"{SYMBOL_ERROR} {MKT_NOT_CONFIGURED}：{name}"
            row["_unconfigured"] = name
            count += 1
            continue
        if row["indicator_key"] not in failed or row.get("_missing_cells"):
            continue
        if not any(b.get("text") == MKT_BADGE_MISSING_TEXT for b in row["badges"]):
            continue
        row["badges"] = [dict(MKT_BADGE_FETCH_FAILED) if b.get("text") == MKT_BADGE_MISSING_TEXT else b
                         for b in row["badges"]]
        for cell in MKT7_CELLS:
            if row[cell] == SYMBOL_UNDECIDABLE:
                row[cell] = SYMBOL_ERROR
        row["_fetch_failed"] = True
        # BL-0250 批次 3-B（總管第二輪裁定第 4 點）：這一列的取數失敗屬哪一類資料，在產生處寫明（畫面字不變）。
        row[page_health.FETCH_CLASS_KEY] = page_health.DATA_CLASSES["market_indicator"]
        count += 1
    for item in _find(model, "MKT-5").get("_items") or ():
        name = unconfigured.get(item.get("name"))
        if name is not None and any(b.get("text") == MKT_BADGE_MISSING_TEXT for b in item["badges"]):
            item["badges"] = [b for b in item["badges"] if b.get("text") != MKT_BADGE_MISSING_TEXT]
            item["_unconfigured"] = name
            count += 1
            continue
        if item.get("name") in failed and any(b.get("text") == MKT_BADGE_MISSING_TEXT for b in item["badges"]):
            item["badges"] = [dict(MKT_BADGE_FETCH_FAILED) if b.get("text") == MKT_BADGE_MISSING_TEXT else b
                              for b in item["badges"]]
            item[page_health.FETCH_CLASS_KEY] = page_health.DATA_CLASSES["market_indicator"]   # BL-0250 批次 3-B
            count += 1
    return count


def _is_mkt6_empty_line(line) -> bool:
    """`MKT-6` 一筆觀測也沒有時那一句（logic `empty_source_text(["market_indicator"])`，經 `plain`／`symbols` 之後表名換中文、
    符號換 ◇）。只認「資料未備：…尚無資料」這個形狀。"""
    return (isinstance(line, str) and line.endswith("尚無資料")
            and (line.startswith(f"{SYMBOL_MISSING} 資料未備：") or line.startswith(f"{SYMBOL_UNDECIDABLE} 資料未備：")))


def mark_mkt6_fetch_failed(model: dict) -> int:
    """`MKT-6` 一筆觀測也沒有時，表尾那一句依成因改寫（BL-0373；就地改寫，回改了幾處）。在 `plain`／`symbols` 之後呼叫，
    讀 `MKT-7` 上一步記的 `_fetch_failed` 與畫面上的指標名：

    - `MKT-7` 列出的每一個鍵都是取數失敗 → 那一句改成狀態族「⛔ 取數失敗」；
    - 成因混合（有取數失敗、也有真正的資料未備）→ 資料未備那一句照留，下一行另加「⛔ 取數失敗：<失敗的指標名>」
      （與持倉體檢同向：取數失敗另外說出來，不算進資料未備）；
    - 沒有任何取數失敗 → 不動。

    BL-0250 批次 3-A（總管適用客戶 `DEC-2026-10-19-05` 第 2 點）：`MKT-7` 記了 `_unconfigured` 的鍵（成因是設定沒設）不算取數失敗，
    另寫一行「⛔ 尚未設定：<哪一項>」；與別的成因（取數失敗、資料未備）並存時括號列出是哪幾個指標。列出的每一個鍵都屬
    尚未設定時，那一句只寫「⛔ 尚未設定：<哪一項>」（同上「全部失敗只寫狀態族」的寫法）。"""
    mkt6, mkt7 = _find(model, "MKT-6"), _find(model, "MKT-7")
    rows7 = mkt7["_rows"]
    lines = mkt6["detail_lines"]
    if mkt6.get("_rows") or not rows7 or not any(_is_mkt6_empty_line(line) for line in lines):
        return 0
    failed = [r["indicator_key"] for r in rows7 if r.get("_fetch_failed")]
    unconfigured: dict = {}
    for r in rows7:
        if r.get("_unconfigured"):
            unconfigured.setdefault(r["_unconfigured"], []).append(r["indicator_key"])
    if not failed and not unconfigured:
        return 0
    n_unconfigured = sum(len(v) for v in unconfigured.values())
    missing = len(rows7) - len(failed) - n_unconfigured
    extra = []
    if failed:
        extra.append(LINE_FETCH_FAILED if not missing and not unconfigured else f"{LINE_FETCH_FAILED}：" + "、".join(failed))
    for name, keys in unconfigured.items():
        alone = not missing and not failed and len(unconfigured) == 1
        extra.append(f"{SYMBOL_ERROR} {MKT_NOT_CONFIGURED}：{name}" + ("" if alone else "（" + "、".join(keys) + "）"))
    out = []
    for line in lines:
        if _is_mkt6_empty_line(line):
            if missing:
                out.append(line)       # 真正的資料未備那一句照留
            out.extend(extra)
        else:
            out.append(line)
    mkt6["detail_lines"] = out
    return 1


def _node_text(node: dict) -> str:
    glyph = node.get("glyph", "")
    text = node["text"]
    return f"{glyph} {text}" if glyph and not text.startswith(glyph) else text


def set2_summary(block: dict) -> str:
    """`SET-2` 移進 ④「證據／來源」之後收合時的摘要那一行（44 第五節第四小節：缺什麼在摘要就看得見）。
    只拼卡上已有的格：佔位 → 佔位那一句；否則依列序分三組 —— 結果為 `failed` 的層級、三欄缺值（資料未備）的層級、
    結果為 `ok` 的層級。不寫「正常」。"""
    placeholder = block["placeholder"]
    if placeholder:
        if placeholder.get("_empty_kind") == SET_EMPTY_KIND_NO_SOURCE:
            # ~~比照 `SET-6` 收合摘要「缺 fetch_log：尚無取數紀錄」：寫出缺的來源鍵（44 第五節第四小節）。
            # `return f"缺 fetch_log：{_node_text(placeholder)}"`~~ → BL-0250 批次 3-C（客戶 2026-10-21 Q4；`DEC-2026-10-21-02`；
            # 44 第七節第三小節之十四）：完全沒有任何取數紀錄時，標題只寫佔位那一句（不露出表名；符號照舊）。
            # 第五節第四小節元件判準只在 `SET-2`／`SET-6` 這一種情形開窄例外，其他塊同型摘要不動（有意識的政策變更，不是漏刪）。
            return _node_text(placeholder)
        # BL-0250 批次 3-A：讀取失敗的成因由 `ui_v2/set/live.py::_read_failure_title` 先寫好（尚未設定不寫成取數失敗）。
        return block.get("_plain_summary") or _node_text(placeholder)
    # BL-0250 批次 3-A（客戶 2026-10-19 批次 3 裁示；44 第七節第三小節之十二）：結果欄改中文之後，分組改讀 `live` 記的 `_result`
    # （沒有記的照舊讀結果欄的英文原值 —— 只有測試直接組的區塊會這樣）。全屬尚未設定的那一筆另成一組，不算進取數失敗。
    def result(row):
        return row.get("_result", row["result_text"])

    failed = [r["tier_text"] for r in block["_rows"] if result(r) == "failed"]
    unconfigured = [f"{SYMBOL_ERROR} 尚未設定：{'、'.join(r['_unconfigured_names'])}（{r['tier_text']}）"
                    for r in block["_rows"] if result(r) == "unconfigured"]
    missing = [r["tier_text"] for r in block["_rows"] if result(r) not in ("failed", "ok", "unconfigured")]
    ok = [r["tier_text"] for r in block["_rows"] if result(r) == "ok"]
    parts = []
    if failed:
        parts.append(f"{SYMBOL_ERROR} 最近一次取數失敗：" + "、".join(failed))
    parts.extend(unconfigured)
    if missing:
        parts.append(f"{SYMBOL_MISSING} 資料未備：" + "、".join(missing))
    if ok:
        # ~~「最近一次 ok：」~~ → U7（b）：不寫英文原值（有意識的政策變更，不是漏刪；決策者：客戶 2026-10-19 批次 3 裁示）。
        parts.append("最近一次取數完成：" + "、".join(ok))
    return "；".join(parts)


def set3_summary(block: dict) -> str:
    """`SET-3` 移進 ④「操作」之後收合時的摘要那一行（44 第五節第四小節：缺什麼在摘要就看得見）。只拼卡上已有的字，
    標點比照 `SET-4` 的摘要用「，」：

    - 佔位 → 佔位那一句；
    - 卡頭紅字（正式模式 ★10，例：「⛔ 未設定試算表 ID，暫停寫入」）→ 先寫那一句；**沒有任何列時就只寫那一句**，
      不寫「0 個鍵」（2026-10-18 獨立稽核必修 M1：正式模式未設定時佔位已併入卡頭，舊寫法會報「0 個鍵」）；
    - 否則設定數，加上目前值為「⬜ 未設定」「⬜ 不適用：值與型別不符」「⚠ 1 列格式不符，未採用」（正式模式壞列）的個數
      （~~鍵名~~ → 客戶 2026-10-19 裁示只寫個數）；
    - 最後接上卡上的結構檢查行（正式模式 ★9 的 `live_lines`，例：格式不符未採用 N 列）。
    """
    placeholder = block["placeholder"]
    if placeholder:
        return _node_text(placeholder)
    rows = block["_rows"]
    red_heads = [node["text"] for node in block.get("head_lines") or () if node["_tone"] == "紅"]
    if not rows and red_heads:
        return "，".join(red_heads)
    # ~~f"{len(rows)} 個鍵"、「N 個未設定：<鍵名、鍵名…>」~~ → 客戶 2026-10-19 裁示（`DEC-2026-10-19-04`，BL-0250 批次 1；
    # 有意識的政策變更，不是漏刪）：摘要不再列原始鍵名（全部未設定時一行列十八個鍵名），只寫「N 個設定，M 個未設定」；
    # 值與型別不符、格式不符未採用兩種同樣只寫個數。哪幾個鍵照舊在展開後的表上逐列看得到（換位置，不刪除）。
    parts = red_heads + [f"{len(rows)} 個設定"]
    unset = [r["key_text"] for r in rows if r["value_text"] == f"{SET_EMPTY_GLYPH} 未設定"]
    bad = [r["key_text"] for r in rows if r["value_text"] == f"{SET_EMPTY_GLYPH} 不適用：值與型別不符"]
    broken = [r["key_text"] for r in rows if r["value_text"] == SET_BAD_ROW_TEXT]
    if unset:
        parts.append(f"{len(unset)} 個未設定")
    if bad:
        parts.append(f"{len(bad)} 個值與型別不符")
    if broken:
        parts.append(f"{len(broken)} 個格式不符未採用")
    parts += [node["text"] for node in block.get("live_lines") or () if node["_tone"] != "中性"]
    return "，".join(parts)


# ───────────────────────── 新設計 B：卡片安靜收起（BL-0250 批次 3-D） ─────────────────────────
# 客戶 2026-10-19 核准新設計 B（`DEC-2026-10-19-05`），2026-10-21 核准進入 3-D 並裁示 Decision Gate Q1～Q4（`docs/DECISIONS.md`
# `DEC-2026-10-21-03`、`-04`）；唯一正式定義：線框 `docs/v2/61_bl0250_batch3_wireframe.md` 1.4（規則 1～4；規則 5 見下方「不做」）；
# 落字：44 第七節第三小節之十五。
#
# 本段只做**判定與組字**（純函式、不改模型）；畫法在各頁 `page.py` 的收起分支。呼叫點一律在 `health_view.collect_page_health`
# 與 `record_page_health` **之後**、畫卡之前 —— 頁首主要原因與設定與診斷頁總表（`SET-8`）讀的是收集那一步記下的同一份記錄，
# 收起與否不回頭影響它們。**示範模式不經過本段**（本模組本來就只給正式模式）。
#
# 判定（客戶 Q2 (a)、總管內部判定照列）：
# - 卡上主值**全部**畫成 ⛔ 或 ◇ → 收起；只有部分讀不到 → 不收起（規則 3）；主值全部是 ⬜（業務例外／算不出來）→ 不收起
#   （⬜ 不是讀不到，總管判定）；◷ 是讀得到的值，不收起。
# - 收起之後：卡名＋「（暫時收起）」＋每種原因一行（規則 2：尚未設定一行、取數失敗一行、資料未備依原因句分行，不合併不同種）；
#   不畫主值、主值身上的徽章與說明、卡頭徽章、「這張卡回答什麼」那句，以及被原因行取代的重複 ⛔／◇ 行（例「⛔ 此區塊暫時無法判定」）；
#   `⬜ 不適用（…）` 只有**由同一原因衍生**的那幾句不畫，原因不同的照留（客戶 Q2 (a)）。其餘非主值的內容照留
#   （說明句、判讀證據、按鈕與它的停用原因、輸入欄；總管判定：持倉體檢計算軌跡、標的探索「暫不提供存檔」、資產配置「開始試算」照留）。
# - 原因行的字沿用 3-A／3-C 既有原因字（「⛔ 尚未設定：‹哪一項›」「⛔ 取數失敗：‹…›」「◇ 資料未備：‹…›」），不新造句型；
#   ‹…› 在市場總覽寫值名（卡上每個主值都有一行值名；照 1.4 例子），其他頁寫收集那一步記下的資料類（同頁首、總表的字；
#   卡上沒有值名那一行）；排序依值在卡上的順序（沒有值名的頁依收集那一步的順序）。
# - **不收起、照現況畫**（保守退路，不是靜默）：收集那一步出錯；某一種讀不到在收集那一步找不到對應的原因項目（原因行寫不出來）；
#   持倉體檢逐檔分組掛著判讀證據（逐檔「◇ 最近一筆淨值 ‹日期›，已超過 10 日」等新鮮度副標或徽章）—— 收起會把逐檔的判讀證據
#   吃掉，而 1.4 沒有定那幾句收起後放哪裡（3-D 實作組停手項，登記待裁；見 `QUIET_HOLD_EVIDENCE`）。
#
# ⛔ 不做（客戶 Q3）：規則 5「詳細資料裡的收合區比照」—— 現有收合標題「標題　—　摘要」一格只承載一句摘要，一塊有兩種原因時
#   寫不下兩行（規則 2），而「打開只有一行」會拿掉 ④ 裡的判讀證據（例「前往 Sheets 維護持倉」）；照 Q3「無法唯一承載原因 → 停手回報，
#   不自創新文案」，3-D 不改任何收合區（停手項）。

QUIET_MARK = "（暫時收起）"
# 射程（線框附錄 2 P3 影響塊）。`SET-1` 不收卡，只拿掉表下重複那一行（線框 6.2；`set1_duplicate_fail_nodes`）。
QUIET_CODES = {
    "mkt": ("MKT-1", "MKT-2", "MKT-3"),
    "hld": ("HLD-1", "HLD-2", "HLD-3"),
    "exp": ("EXP-1",),
    "alo": ("ALO-2", "ALO-3"),
}
# 卡上每個主值有一行值名的頁：原因行寫值名（1.4 例子「⛔ 取數失敗：波動度指數」）。
QUIET_VALUE_NAMES = ("mkt",)
QUIET_HOLD_EVIDENCE = "逐檔分組掛著判讀證據"
QUIET_HOLD_NO_ITEM = "收集那一步找不到原因項目"
QUIET_HOLD_COLLECT = "收集那一步出錯"

# 鏡像常數（真身 `ui_v2/health.py`；`tests/ui_v2/test_bl0250_batch3d_logic.py` 逐字比對）。
TEXT_FETCH_FAILED = "取數失敗"
TEXT_MISSING = "資料未備"
LINE_BLOCK_UNDECIDABLE = f"{SYMBOL_ERROR} 此區塊暫時無法判定"
LINE_NOT_CONFIGURED = f"{SYMBOL_ERROR} {TEXT_NOT_CONFIGURED}"
LINE_SETTINGS_UNREADABLE = f"{SYMBOL_ERROR} 設定讀不到"
LINE_MISSING = f"{SYMBOL_MISSING} {TEXT_MISSING}"
_UNREADABLE_STATES = frozenset({STATE_ERROR, STATE_MISSING})
_UNREADABLE_EMPTY = frozenset({STATE_ERROR, "來源缺"})
_KIND_ERROR, _KIND_MISSING = "⛔", "◇"


def _value_text(node: dict) -> str:
    for key in ("value_text", "text"):
        value = node.get(key)
        if isinstance(value, str):
            return value
    return ""


def quiet_value_kind(node: dict):
    """一個主值畫成什麼：`"⛔"`、`"◇"`，讀得到（含 ⬜、◷）回 None。只讀既有的 `_state`／`_empty_kind` 與畫出來的字，不另判。"""
    text = _value_text(node)
    if text.startswith(f"{SYMBOL_UNDECIDABLE} "):
        return None
    if node.get("_state") == STATE_MISSING or node.get("_empty_kind") == "來源缺" or text.startswith(f"{SYMBOL_MISSING} "):
        return _KIND_MISSING
    if (node.get("_state") == STATE_ERROR or node.get("_empty_kind") == STATE_ERROR
            or text.startswith(f"{SYMBOL_ERROR} ")):
        return _KIND_ERROR
    return None


def _block_level(block: dict) -> list:
    """沒有逐值節點的塊（整塊佔位）：以塊自己的狀態當唯一的主值。"""
    state = block.get("_state")
    return [{"_state": state}] if state in _UNREADABLE_STATES else [{"_state": state or STATE_OK, "text": "ok"}]


def _quiet_values(block: dict, page: str):
    """`(主值清單, 不收起的理由或 None)`。主值清單裡每一個是畫在卡上的值節點；讀得到的列（偏離列、條件列、對照列）一列就算一個
    讀得到的主值（總管判定：有列 ＝ 部分讀得到，不收起）。"""
    code = block.get("code")
    if page == "mkt":
        return list(block.get("main_values") or ()), None
    if code == "HLD-1" or page == "alo":
        if block.get("_rows"):
            return [{"_state": STATE_OK, "text": "row"}], None
        node = block.get("_placeholder") if code == "HLD-1" else block.get("placeholder")
        return ([node] if node else _block_level(block)), None
    if page == "hld":
        groups = list(block.get("fund_groups") or ())
        if not groups:
            return _block_level(block), None
        values = [value for group in groups for value in group.get("main_values") or ()]
        if any(group.get("freshness_note") or group.get("freshness_badge") for group in groups):
            return values, QUIET_HOLD_EVIDENCE
        return values, None
    if page == "exp":
        if block.get("_rows"):
            return [{"_state": STATE_OK, "text": "row"}], None
        return _block_level(block), None
    return [], None


def _card_entries(items, title: str) -> list:
    """收集那一步記下、點到這張卡而且「讀不到」的 `(種類, 鍵, 項目名)`，依收集順序。"""
    out = []
    for item in items or ():
        for entry in item.get("affected") or ():
            if entry.get("card") == title and entry.get("unreadable"):
                out.append((item["kind"], item["key"], entry.get("item") or ""))
    return out


def _names(entries, kind) -> list:
    return list(dict.fromkeys(key for k, key, _label in entries if k == kind))


def _error_is_fetch(label, fetch_keys, fetch_labels, labelled, unconfigured, unconf_labels) -> bool:
    """市場總覽一個 ⛔ 主值算取數失敗還是尚未設定：收集那一步點名到這個值的那一種優先；兩種都有而取數失敗項目沒有值名時，
    沒被尚未設定點名的 ⛔ 歸取數失敗；只有一種時就是那一種。"""
    if fetch_keys and label in fetch_labels:
        return True
    if unconfigured and label in unconf_labels:
        return False
    if fetch_keys and not unconfigured:
        return True
    if unconfigured and not fetch_keys:
        return False
    return bool(fetch_keys) and not labelled


# 卡上會畫出來的非主值文字欄位（各頁卡片的說明句、卡尾、失敗行、空狀態句）。
_BLOCK_LINE_FIELDS = ("detail_lines", "tail_lines", "notes", "fetch_fail_lines", "error_lines", "unset_lines",
                      "save_fail_notes", "redline_note")


def _block_lines(block: dict) -> list:
    out = []
    for field in _BLOCK_LINE_FIELDS:
        value = block.get(field)
        if isinstance(value, str):
            out.append(value)
        elif isinstance(value, (list, tuple)):
            out += [v for v in value if isinstance(v, str)]
    tail = block.get("freshness_tail")
    if isinstance(tail, dict) and isinstance(tail.get("text"), str):
        out.append(tail["text"])
    return out


def quiet_view(block: dict, items, page: str):
    """一張卡收不收起。回 `(view, hold)`：收起 → `view` 為 `{"code", "title", "mark", "lines": [{"text", "_tone"}, ...],
    "unconfigured": [...], "fetch": bool, "missing": bool}`、`hold` 為 None；不收起 → `(None, 理由或 None)`
    （理由 None ＝ 規則本來就不收起：讀得到、部分讀得到、全部 ⬜）。"""
    values, hold = _quiet_values(block, page)
    kinds = [quiet_value_kind(v) for v in values]
    if not values or any(k is None for k in kinds):
        return None, None
    if hold:
        return None, hold
    title = block.get("title", "")
    entries = _card_entries(items, title)
    unconfigured = _names(entries, page_health.KIND_UNCONFIGURED)
    fetch_keys = _names(entries, page_health.KIND_FETCH)
    missing_keys = _names(entries, page_health.KIND_MISSING)
    if (_KIND_ERROR in kinds and not (unconfigured or fetch_keys)) or (_KIND_MISSING in kinds and not missing_keys):
        return None, QUIET_HOLD_NO_ITEM
    value_names = page in QUIET_VALUE_NAMES
    fetch_labels = [label for k, _key, label in entries if k == page_health.KIND_FETCH]
    labelled = value_names and fetch_labels and all(fetch_labels)
    unconf_labels = [label for k, _key, label in entries if k == page_health.KIND_UNCONFIGURED and label]
    groups = {}          # 原因 → {"text", "_tone", "notes", "names", "order"}

    def put(key, text_head, tone, name, notes=(), order=0):
        group = groups.setdefault(key, {"head": text_head, "_tone": tone, "names": [], "notes": [], "order": order})
        if name and name not in group["names"]:
            group["names"].append(name)
        for note in notes:
            if note not in group["notes"]:
                group["notes"].append(note)

    error_head = f"{SYMBOL_ERROR} {TEXT_FETCH_FAILED}："
    missing_head = f"{SYMBOL_MISSING} {TEXT_MISSING}："
    if value_names:
        for index, (value, kind) in enumerate(zip(values, kinds)):
            label = value.get("label", "")
            notes = tuple(value.get("note_lines") or ())
            if kind == _KIND_MISSING:
                put(("missing", notes), missing_head, "灰", label, notes, index)
            elif _error_is_fetch(label, fetch_keys, fetch_labels, labelled, unconfigured, unconf_labels):
                put(("fetch",), error_head, "紅", label if labelled else None, notes, index)
            else:
                put(("unconfigured",), None, "紅", None, (), index)
        # 安全網（2026-10-21 3-D 獨立稽核缺陷 2；有意識的更正，不是漏刪）：收集那一步記下、點到這張卡的取數失敗或尚未設定，
        # 不論對不對得上卡上哪一個值，都要各有一行 —— ~~對不上值的那一種整行不寫~~（舊寫法在取數失敗項目沒有值名、同卡又有
        # 尚未設定時，取數失敗那一行整行消失）。對不上值時排在最後、字用資料類（既有字型「⛔ 取數失敗：‹資料類›」）。
        if _KIND_ERROR in kinds and fetch_keys and ("fetch",) not in groups:
            put(("fetch",), error_head, "紅", None, (), len(values))
        if _KIND_ERROR in kinds and unconfigured and ("unconfigured",) not in groups:
            put(("unconfigured",), None, "紅", None, (), len(values))
    else:
        if _KIND_ERROR in kinds:
            for index, (kind, _key, _label) in enumerate(entries):
                if kind == page_health.KIND_UNCONFIGURED:
                    put(("unconfigured",), None, "紅", None, (), index)
                elif kind == page_health.KIND_FETCH:
                    put(("fetch",), error_head, "紅", None, (), index)
        if _KIND_MISSING in kinds:
            first = next(i for i, (k, _key, _l) in enumerate(entries) if k == page_health.KIND_MISSING)
            put(("missing", ()), missing_head, "灰", None, (), first)
    # 一張卡記了資料未備、主值卻全是 ⛔（例：持倉體檢偏離提示卡退回預存又過期，資料未備那幾檔寫在卡尾）：卡上照留的非主值句裡
    # 已有 ◇（判讀證據）就不另寫；沒有 → 補一行「◇ 資料未備：‹資料類›」（既有字型），◇ 不因收起而消失（同批稽核建議 3）。
    if missing_keys and _KIND_MISSING not in kinds and not any(k[0] == "missing" for k in groups):
        probe = {"unconfigured": unconfigured, "fetch": ("fetch",) in groups, "missing": False, "fetch_keys": list(fetch_keys)}
        if not any(SYMBOL_MISSING in line and quiet_keep(probe, line) for line in _block_lines(block)):
            first = next(i for i, (k, _key, _l) in enumerate(entries) if k == page_health.KIND_MISSING)
            put(("missing", ()), missing_head, "灰", None, (), len(values) + first)
    if ("fetch",) in groups and not groups[("fetch",)]["names"]:
        groups[("fetch",)]["names"] = list(fetch_keys)
    if ("unconfigured",) in groups:
        groups[("unconfigured",)]["names"] = list(unconfigured)
        groups[("unconfigured",)]["head"] = f"{LINE_NOT_CONFIGURED}："
    for key, group in groups.items():
        if key[0] == "missing" and not group["names"]:
            group["names"] = list(missing_keys)
    lines = []
    for _key, group in sorted(groups.items(), key=lambda kv: kv[1]["order"]):
        lines.append({"text": group["head"] + "、".join(group["names"]), "_tone": group["_tone"]})
        lines += [{"text": note, "_tone": "灰"} for note in group["notes"]]
    view = {"code": block.get("code"), "title": title, "mark": QUIET_MARK, "lines": lines,
            "unconfigured": unconfigured, "fetch": ("fetch",) in groups,
            "missing": any(k[0] == "missing" for k in groups),
            # 2026-10-21 3-D 第三輪（Q2 (a) 落地缺口；有意識的更正，不是漏刪；決策者：AI 總管依稽核確認）：帶出這張卡取數失敗與
            # 資料未備的鍵（資料類），`quiet_keep` 判 ⬜ 句是不是同一原因衍生時要看到資料類，不再只看種類。
            "fetch_keys": list(fetch_keys) if ("fetch",) in groups else [],
            "missing_keys": list(missing_keys) if any(k[0] == "missing" for k in groups) else [],
            # 客戶 2026-10-21 Q7 (a)（`DEC-2026-10-21-05`）：持倉體檢逐檔分組的卡收起時，分組標頭（既有字樣，例「基金 A · 幣別 USD」）
            # 照留，每一檔一行，接在原因行下面。
            "fund_heads": [g.get("head_text") for g in block.get("fund_groups") or () if g.get("head_text")]}
    return view, None


def quiet_cards(display: dict, collected, page: str, recorded=None) -> tuple:
    """本頁射程內每一張卡的收起判定 → `({塊代號: view}, {塊代號: 不收起的理由})`。
    `collected`：`health_view.collect_page_health` 的回傳；`recorded`：本頁剛記下的那一格（`page_health.recorded`）。
    收集出錯（`collected` 帶 `error`）或記錄那一步改寫成收集失敗（`recorded` 帶 `collect_error`，頁首寫「⛔ 本頁狀態無法彙整」）
    → 一張都不收起（照 3-C 的畫法，與頁首那一句一致：原因寫不出來就不收）。"""
    codes = QUIET_CODES.get(page, ())
    if not codes:
        return {}, {}
    if (not isinstance(collected, dict) or "error" in collected
            or (isinstance(recorded, dict) and recorded.get("collect_error"))):
        return {}, {code: QUIET_HOLD_COLLECT for code in codes}
    items = collected.get("items") or ()
    views, holds = {}, {}
    for block in display.get("blocks") or ():
        if block.get("code") not in codes:
            continue
        view, hold = quiet_view(block, items, page)
        if view is not None:
            views[block["code"]] = view
        elif hold:
            holds[block["code"]] = hold
    return views, holds


def quiet_keep(view: dict, line) -> bool:
    """收起的卡上，一句非主值的字照不照畫：被原因行取代的重複 ⛔／◇（狀態族、或「⛔ 尚未設定：‹這張卡已寫在原因行的那幾項›」）
    與由同一原因衍生的 `⬜ 不適用（…）` 不畫；其餘照畫（客戶 Q2 (a)：原因不同的 ⬜ 照留）。`view` 為 None → 一律照畫。"""
    if view is None or not isinstance(line, str):
        return True
    text = line.strip()
    names = set(view.get("unconfigured") or ())
    # 狀態族句只在這張卡已有同一種原因行時才省（同批稽核建議 3；~~一律不畫~~，有意識的更正，不是漏刪）：
    # 「◇ 資料未備」要有資料未備那一行、「⛔ 取數失敗」要有取數失敗那一行、「⛔ 尚未設定」要有尚未設定那一行；
    # 「⛔ 此區塊暫時無法判定」「⛔ 設定讀不到」屬 ⛔ 那一族，有任何一行 ⛔ 原因就省。
    error_line = bool(view.get("fetch")) or bool(names)
    family = {LINE_MISSING: bool(view.get("missing")), LINE_FETCH_FAILED: bool(view.get("fetch")),
              LINE_NOT_CONFIGURED: bool(names), LINE_BLOCK_UNDECIDABLE: error_line,
              LINE_SETTINGS_UNREADABLE: error_line}
    if text in family:
        return not family[text]
    head = f"{LINE_NOT_CONFIGURED}："
    if text.startswith(head) and names and set(text[len(head):].split("、")) <= names:
        return False
    if text.startswith(f"{SYMBOL_UNDECIDABLE} "):
        if any(f"{TEXT_NOT_CONFIGURED}：{name}" in text for name in names):
            return False
        # ~~if view.get("fetch") and TEXT_FETCH_FAILED in text: return False~~
        # ~~if view.get("missing") and TEXT_MISSING in text: return False~~
        # → 2026-10-21 3-D 第三輪（有意識的更正，不是漏刪；決策者：AI 總管依稽核確認）：舊寫法只看種類，「⬜ 不適用（取數失敗：別的資料）」
        # 會被當成同一原因而不畫，違反客戶 Q2 (a)（原因不同的 ⬜ 照留）。現行比照尚未設定那一支：句子裡要寫出這張卡的某一類資料
        # （`fetch_keys`／`missing_keys`）才算同一原因、不畫；寫不出是哪一類的照留。舊寫法的用意（同源衍生不重複畫）照留。
        fetch_keys = [k for k in view.get("fetch_keys") or () if k]
        if view.get("fetch") and TEXT_FETCH_FAILED in text and any(k in text for k in fetch_keys):
            return False
        missing_keys = [k for k in view.get("missing_keys") or () if k]
        if view.get("missing") and TEXT_MISSING in text and any(k in text for k in missing_keys):
            return False
    return True


def set1_duplicate_fail_nodes(block: dict) -> list:
    """設定與診斷頁 `SET-1` 資料新鮮度卡表格下面的失敗行裡，與表格某一列「最近取得時間」格逐字相同的那幾行（線框 6.2：
    尚未設定時淨值、市場指標兩列各寫「⛔ 尚未設定：試算表 ID」，表下又一行同一句 → 只拿掉表下重複的那一行；表格照留三列）。
    回要拿掉的節點；不同字的失敗行照留。卡不收起。"""
    cells = {row.get("at_text") for row in block.get("_rows") or ()}
    return [node for node in block.get("fail_nodes") or () if node and node.get("text") in cells]


# ───────────────────────── 線框 1.4 規則 5：詳細資料裡的收合區比照（客戶 2026-10-21 Q5 (b)；`DEC-2026-10-21-05`） ─────────────────────────
# 只套用於 ④ 詳細資料裡「主值全部讀不到（⛔／◇）、只有一種原因、收合區內沒有判讀證據」的收合區：標題用既有格式「標題　—　一句原因」，
# 原因句與卡片原因行同一套既有字型；打開只有那一行。其他收合區（兩種以上原因、有判讀證據、部分讀得到）一律照現況。
# 工程判定（3-D 實作組，可推翻）：
# - 「只有一種原因」＝收集那一步點到這一塊、讀不到的原因項目恰好一項（一種、一個鍵）；同一種兩個鍵（例「尚未設定：A、B」）算兩種，照現況。
# - ~~「部分讀得到」：塊上有任何列、逐檔項目、欄位或輸入（`_DETAIL_CONTENT_KEYS`）就算有內容，照現況；塊上有按鈕也照現況~~
#   ~~（第五節第三小節「停用時不隱藏」，打開只有一行會把按鈕拿掉）。~~
#   → 2026-10-21 稽核複驗加固（有意識的更正，不是漏刪；決策者：AI 總管依稽核指正）：舊寫法是「內容欄位白名單」，清單外的欄位
#   （例 ALO-6 `footer_lines`、HLD-6 `div_rows`／`_missing_lines`、ALO-1 `intro_line`）不被檢查，收起時會被靜默拿掉。
#   現行改保守預設：塊上只要有任何非空欄位不在 `_DETAIL_IGNORABLE`（已知的空佔位、塊的中繼資料、表頭、會被逐句檢查判讀證據的說明句欄位），
#   就算有內容，照現況。按鈕（`buttons`）不在可忽略清單 → 有按鈕照舊不比照（第五節第三小節「停用時不隱藏」）。
#   舊寫法的用意（有內容就不收）照留；被權衡掉的是「列舉內容欄位」這個做法 —— 漏列一個欄位就會把那一欄靜默拿掉。
# - 「判讀證據」：塊上照留的句子（拿掉被原因行取代的狀態族句之後）帶 ⛔／◇，或是線框與本檔點名照留的那幾塊
#   （持倉體檢計算軌跡「四塊沒有一塊出數…」那一句，線框 3.3；資產配置分組定義的「前往 Sheets 維護持倉」，之十四其二第 7 條）。
QUIET_DETAIL_CODES = {
    "mkt": ("MKT-4", "MKT-5", "MKT-6", "MKT-7"),
    "hld": ("HLD-4", "HLD-5", "HLD-6", "HLD-7", "HLD-8"),
    "exp": ("EXP-4", "EXP-5", "EXP-6", "EXP-7"),    # 結果清單（EXP-2＋EXP-3 合成一框）不在射程：兩塊合一，不是一塊的收合區
    "alo": ("ALO-1", "ALO-4", "ALO-5", "ALO-6", "ALO-7"),
}
QUIET_DETAIL_EVIDENCE = {"hld": ("HLD-7",), "alo": ("ALO-4",)}
# ~~_DETAIL_CONTENT_KEYS = ("_rows", "_items", "nav_rows", "nav_groups", "_fields", "inputs", "_options", "main_values",~~
# ~~                        "fund_groups", "input_rows")~~  → 改為下方可忽略清單（保守預設，理由見上方工程判定第二條）。
# 收起時可以忽略的欄位：塊的中繼資料（代號、標題、回答的問題、層、狀態、色調、衍生理由）、被原因行取代的空佔位與摘要句、
# 讀不到的鍵、表頭（沒有列時只是欄名）；以及 `_block_lines` 會逐句檢查判讀證據的說明句欄位（帶 ⛔／◇ 就照現況）。
_DETAIL_IGNORABLE = frozenset(("code", "title", "answers", "_layer", "_state", "_tone", "_derived", "_derived_reason",
                               "summary_text", "placeholder", "_placeholder", "_empty_kind", "_unconfigured", "_missing_keys",
                               "column_labels", "freshness_tail") + _BLOCK_LINE_FIELDS)


def _detail_has_content(block: dict) -> bool:
    """塊上有沒有任何「不在可忽略清單、且非空」的欄位（保守預設：清單外一律算有內容）。"""
    for key, value in block.items():
        if key in _DETAIL_IGNORABLE or value is None or value is False:
            continue
        if isinstance(value, (str, list, tuple, dict, set, frozenset)) and len(value) == 0:
            continue
        return True
    return False


def _detail_unreadable(block: dict) -> bool:
    placeholder = block.get("placeholder") or block.get("_placeholder")
    if isinstance(placeholder, dict) and quiet_value_kind(placeholder):
        return True
    return block.get("_state") in _UNREADABLE_STATES or block.get("_empty_kind") in _UNREADABLE_EMPTY


def quiet_detail_view(block: dict, items, page: str):
    """④ 一塊收合區比不比照規則 5 → `{"code", "title", "line": {"text", "_tone"}}` 或 None（照現況）。"""
    code = block.get("code")
    if code not in QUIET_DETAIL_CODES.get(page, ()) or code in QUIET_DETAIL_EVIDENCE.get(page, ()):
        return None
    if _detail_has_content(block) or not _detail_unreadable(block):
        return None
    title = block.get("title", "")
    entries = list(dict.fromkeys((kind, key) for kind, key, _label in _card_entries(items, title)))
    if len(entries) != 1:
        return None
    kind, key = entries[0]
    if kind == page_health.KIND_UNCONFIGURED:
        line = {"text": f"{LINE_NOT_CONFIGURED}：{key}", "_tone": "紅"}
        view = {"unconfigured": [key], "fetch": False, "missing": False}
    elif kind == page_health.KIND_FETCH:
        line = {"text": f"{SYMBOL_ERROR} {TEXT_FETCH_FAILED}：{key}", "_tone": "紅"}
        view = {"unconfigured": [], "fetch": True, "missing": False, "fetch_keys": [key]}
    elif kind == page_health.KIND_MISSING:
        line = {"text": f"{SYMBOL_MISSING} {TEXT_MISSING}：{key}", "_tone": "灰"}
        view = {"unconfigured": [], "fetch": False, "missing": True, "missing_keys": [key]}
    else:
        return None
    # ~~for text in _block_lines(block) + notes: 只查說明句欄位~~ → 2026-10-21 第二輪加固（有意識的更正，不是漏刪；決策者：AI 總管
    # 依稽核複驗反例）：摘要句（`summary_text`）與空佔位（`placeholder`／`_placeholder` 的字）也逐句檢查 —— 它們原本列在可忽略清單、
    # 無條件忽略；只有是「被原因行取代的狀態族句」（`quiet_keep` 判為不畫）才忽略，帶 ⛔／◇ 又不是那種句子（例「◇ 另有 2 檔淨值
    # 超過 10 日，未列入」「⛔ 此區塊暫時無法判定（另有 3 檔改用預存淨值）」）→ 照現況。
    texts = _block_lines(block) + [n for n in block.get("notes") or () if isinstance(n, str)]
    if isinstance(block.get("summary_text"), str):
        texts.append(block["summary_text"])
    for field in ("placeholder", "_placeholder"):
        holder = block.get(field)
        if isinstance(holder, dict) and isinstance(holder.get("text"), str):
            texts.append(holder["text"])
        elif isinstance(holder, str):
            texts.append(holder)
    for text in texts:
        # 獨立 ⬜（客戶 Q2 (a)：原因不同的 ⬜ 照留）：④ 收合區打開只剩一行，留不住 ⬜。`quiet_keep` 的「同一原因衍生」判定在取數失敗、
        # 資料未備兩種只看 ⬜ 句裡有沒有那個字樣、不看是哪一類資料（例「⬜ 不適用（取數失敗：別的資料）」會被判成同一原因），
        # 沿用不了 → 依總管指示改採更保守的「凡 ⬜ 都不收」。本機比照的九個收合區沒有任何一句 ⬜，比照結果不變。
        if SYMBOL_UNDECIDABLE in text:
            return None
        if quiet_keep(view, text) and (SYMBOL_ERROR in text or SYMBOL_MISSING in text):
            return None          # 收合區內有判讀證據 → 照現況
    return {"code": code, "title": title, "line": line}


def quiet_details(display: dict, collected, page: str, recorded=None) -> dict:
    """本頁 ④ 哪幾塊收合區比照規則 5 → `{塊代號: view}`。收集或記錄出錯 → 一塊都不比照（同 `quiet_cards`）。"""
    if not QUIET_DETAIL_CODES.get(page):
        return {}
    if (not isinstance(collected, dict) or "error" in collected
            or (isinstance(recorded, dict) and recorded.get("collect_error"))):
        return {}
    items = collected.get("items") or ()
    out = {}
    for block in display.get("blocks") or ():
        view = quiet_detail_view(block, items, page)
        if view is not None:
            out[view["code"]] = view
    return out
