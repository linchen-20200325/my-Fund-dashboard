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
   - BL-0373：市場總覽 `MKT-7` 取數失敗的鍵不掛「資料未備」，改「取數失敗」、四格 `⛔`（`mark_mkt7_fetch_failed`）。
   - S1／C1：設定試算表未設定 → 第三句優先於由此衍生的讀取失敗；服務帳戶也未設定時維持 ⛔（`set_conclusion`）。

**不做什麼（護欄 2）**：不改任何 `_state`、顏色、門檻、算法、資料來源與寫入；不新增按鈕；不改任何一格的文案字面
（③ 的字句是本組依 59 線框擬的，見各函式）。**示範模式不經過本模組**（44 第七節第三小節之八開頭第 4 條）。
例外（44 字面明訂的，只在設定與診斷頁）：`SET-0` 在設定試算表未設定時改灰、改出第三句（之八其三 (c-1)），黃燈那一句換字面
（之八其二 (b-2) 第 3 條）；`SET-1` 比較欄「外」加 `◷`（之七其四）。判定（逾期數、失敗來源、內外）一個都不動。
"""

from __future__ import annotations

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


def _item(symbol: str, text: str, tone: str) -> dict:
    return {"symbol": symbol, "text": text, "_tone": tone}


def _mkt_words(card: dict) -> list:
    state = card["_state"]
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
    """持倉體檢 ① 的三個計數那一行；不該列時回 None。

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
    return HLD_COUNTS_TEXT.format(n=n, attention=SYMBOL_ATTENTION, m=m, undecidable=SYMBOL_UNDECIDABLE, j=j)


_FAMILY_FETCH_FAILED = f"{SYMBOL_ERROR} 取數失敗"
_FAMILY_MISSING = f"{SYMBOL_MISSING} 資料未備"


def _placeholder_family(placeholder: dict) -> str:
    """佔位 → 摘要那一行的狀態族。`系統錯誤` 只留「⛔ 取數失敗」（「此區塊暫時無法判定」一塊只寫一次，已寫在卡上；
    之七其二第 3 條）；其餘照佔位自己那一句（已經過 `symbols`，資料未備是 ◇）。只讀既有的 `_empty_kind`，不另判。"""
    if placeholder["_empty_kind"] == STATE_ERROR:
        return _FAMILY_FETCH_FAILED
    return placeholder["text"]


def alo1_summary(block: dict) -> str:
    """`ALO-1` 移進 ④ 之後收合時的摘要那一行（44 第五節第四小節：缺了什麼在摘要那一行就看得見、不把空狀態藏進展開內容）。
    只拼卡上已經有的字：佔位 → 狀態族；否則類別數或「未設定」，有類別的目標比重缺值（`_weight` 為 None，卡上寫資料未備）
    → 加「◇ 資料未備」，再加容許帶那一句。"""
    placeholder = block["placeholder"]
    if placeholder:
        return _placeholder_family(placeholder)
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
    return f"{ALO_SCENARIO_ENTRY}　—　{_placeholder_family(placeholder)}"


# ───────────────────────── 設定與診斷（Phase 3 P1-⑥；之八其二 (b-1)～(b-4)、其三 (c-1)） ─────────────────────────
# 鏡像常數：真身在 `ui_v2/set/logic.py`（`TEXT_OUT`、`EMPTY_GLYPH`、`conclusion_light`／`_build_set0` 的字面），測試逐字比對。

SET_TEXT_OUT = "外"
SET_STATE_OVERDUE = "有逾期"
SET_STATE_EMPTY = "空狀態"
SET_EMPTY_GLYPH = "⬜"
SET_STATE_WORD_EMPTY = "狀態：尚不足以判定"
SYMBOL_STALE = "◷"
SET_EMPTY_KIND_NO_SOURCE = "來源缺"
SET_LOG_TABLE = "fetch_log"
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
# `MKT-6` 一筆觀測也沒有時的那一句（真身 `ui_v2/mkt/logic.py::empty_source_text(["market_indicator"])`）與取代它的狀態族。
MKT6_EMPTY_LINE = "⬜ 資料未備：market_indicator 尚無資料"
LINE_FETCH_FAILED = f"{SYMBOL_ERROR} 取數失敗"


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


def mark_mkt7_fetch_failed(model: dict, failed_keys) -> int:
    """`MKT-7` 取數失敗的鍵（`failed_keys`：資料層 `errors` 裡有失敗字串的鍵）那一列：徽章「資料未備」→「取數失敗」、
    四格 `⬜` → `⛔`（就地改寫）。回改了幾列。

    客戶 2026-10-18 裁示 BL-0373：取數失敗＝⛔、資料未備＝◇，不得把取數失敗判成資料未備。只動「這個鍵一筆觀測也沒有、
    而且資料層回報了失敗」的那幾列（logic 已把它們與真正的資料未備分開：資料未備那幾列帶 `_missing_cells`）；
    有觀測的列（取數失敗但沿用既有列）照舊。"""
    failed = set(failed_keys or ())
    count = 0
    for row in _find(model, "MKT-7")["_rows"]:
        if row["indicator_key"] not in failed or row.get("_missing_cells"):
            continue
        if not any(b.get("text") == MKT_BADGE_MISSING_TEXT for b in row["badges"]):
            continue
        row["badges"] = [dict(MKT_BADGE_FETCH_FAILED) if b.get("text") == MKT_BADGE_MISSING_TEXT else b
                         for b in row["badges"]]
        for cell in MKT7_CELLS:
            if row[cell] == SYMBOL_UNDECIDABLE:
                row[cell] = SYMBOL_ERROR
        count += 1
    count += _mark_mkt6_fetch_failed(model)
    return count


def _mark_mkt6_fetch_failed(model: dict) -> int:
    """`MKT-6` 一筆觀測也沒有、而 `MKT-7` 列出的每一個鍵都是取數失敗（上一步已改掛「取數失敗」）時，
    `MKT-6` 那一句「資料未備：…尚無資料」改成狀態族「⛔ 取數失敗」（BL-0373）。有任何一個鍵是真正的資料未備
    （例：公布日未接上而暫不寫入），成因不只取數失敗，照舊不動。回改了幾處（0 或 1）。"""
    mkt6, mkt7 = _find(model, "MKT-6"), _find(model, "MKT-7")
    rows7 = mkt7["_rows"]
    if mkt6.get("_rows") or not rows7:
        return 0
    if not all(any(b.get("text") == MKT_BADGE_FETCH_FAILED["text"] for b in r["badges"]) for r in rows7):
        return 0
    lines = mkt6["detail_lines"]
    if MKT6_EMPTY_LINE not in lines:
        return 0
    mkt6["detail_lines"] = [LINE_FETCH_FAILED if line == MKT6_EMPTY_LINE else line for line in lines]
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
            # 比照 `SET-6` 收合摘要「缺 fetch_log：尚無取數紀錄」：寫出缺的來源鍵（44 第五節第四小節）。
            return f"缺 {SET_LOG_TABLE}：{_node_text(placeholder)}"
        return _node_text(placeholder)
    failed = [r["tier_text"] for r in block["_rows"] if r["result_text"] == "failed"]
    missing = [r["tier_text"] for r in block["_rows"] if r["result_text"] not in ("failed", "ok")]
    ok = [r["tier_text"] for r in block["_rows"] if r["result_text"] == "ok"]
    parts = []
    if failed:
        parts.append(f"{SYMBOL_ERROR} 最近一次取數失敗：" + "、".join(failed))
    if missing:
        parts.append(f"{SYMBOL_MISSING} 資料未備：" + "、".join(missing))
    if ok:
        parts.append("最近一次 ok：" + "、".join(ok))
    return "；".join(parts)


def set3_summary(block: dict) -> str:
    """`SET-3` 移進 ④「操作」之後收合時的摘要那一行（44 第五節第四小節：缺什麼在摘要就看得見）。只拼卡上已有的字，
    標點比照 `SET-4` 的摘要用「，」：

    - 佔位 → 佔位那一句；
    - 卡頭紅字（正式模式 ★10，例：「⛔ 未設定試算表 ID，暫停寫入」）→ 先寫那一句；**沒有任何列時就只寫那一句**，
      不寫「0 個鍵」（2026-10-18 獨立稽核必修 M1：正式模式未設定時佔位已併入卡頭，舊寫法會報「0 個鍵」）；
    - 否則鍵數，加上目前值為「⬜ 未設定」「⬜ 不適用：值與型別不符」「⚠ 1 列格式不符，未採用」（正式模式壞列）的鍵名；
    - 最後接上卡上的結構檢查行（正式模式 ★9 的 `live_lines`，例：格式不符未採用 N 列）。
    """
    placeholder = block["placeholder"]
    if placeholder:
        return _node_text(placeholder)
    rows = block["_rows"]
    red_heads = [node["text"] for node in block.get("head_lines") or () if node["_tone"] == "紅"]
    if not rows and red_heads:
        return "，".join(red_heads)
    parts = red_heads + [f"{len(rows)} 個鍵"]
    unset = [r["key_text"] for r in rows if r["value_text"] == f"{SET_EMPTY_GLYPH} 未設定"]
    bad = [r["key_text"] for r in rows if r["value_text"] == f"{SET_EMPTY_GLYPH} 不適用：值與型別不符"]
    broken = [r["key_text"] for r in rows if r["value_text"] == SET_BAD_ROW_TEXT]
    if unset:
        parts.append(f"{len(unset)} 個未設定：" + "、".join(unset))
    if bad:
        parts.append(f"{len(bad)} 個值與型別不符：" + "、".join(bad))
    if broken:
        parts.append(f"{len(broken)} 個格式不符未採用：" + "、".join(broken))
    parts += [node["text"] for node in block.get("live_lines") or () if node["_tone"] != "中性"]
    return "，".join(parts)
