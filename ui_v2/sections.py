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

**不做什麼（護欄 2）**：不改任何 `_state`、顏色、門檻、算法、資料來源與寫入；不新增按鈕；不改任何一格的文案字面
（③ 的字句是本組依 59 線框擬的，見各函式）。**示範模式不經過本模組**（44 第七節第三小節之八開頭第 4 條）。
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
