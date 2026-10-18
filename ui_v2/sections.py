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
   m ＝ `HLD-0` 的偏離檔數（`_deviation_count`，燈上「有 N 檔超出」的 N）、j ＝ `HLD-1` 卡尾的缺淨值檔數
   （`missing_nav_count`）、n ＝ `HLD-2` 已讀到的持倉檔數（逐檔分組數）。不寫 `○`、不寫「正常」，不列持有減另兩數的差。

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
    for block in model.get("blocks") or ():
        if block.get("code") == code:
            return block
    return None


def relayer(model: dict, page: str) -> list:
    """把本頁移層的塊改到新層（就地改寫），回改到的塊代號。不在 `RELAYER` 的頁原樣不動。"""
    moved = []
    for code, layer in RELAYER.get(page, {}).items():
        block = _find(model, code)
        if block is None:
            raise KeyError(f"{page} 頁模型裡沒有 {code}（移層對象不見了，不得靜默略過）")
        block["_layer"] = layer
        block["_default_open"] = False
        moved.append(code)
    return moved


def _item(symbol: str, text: str, tone: str) -> dict:
    return {"symbol": symbol, "text": text, "_tone": tone}


def _mkt_words(card: dict) -> list:
    state = card.get("_state")
    if state in _MKT_STATE_WORDS:
        return [_MKT_STATE_WORDS[state]]
    if state is None:
        # 卡上同時有資料未備與業務例外的主值（logic 的哨符狀態）：兩件事都真的發生了，兩個都寫。
        present = {mv.get("_state") for mv in card.get("main_values") or ()}
        return [_MKT_STATE_WORDS[s] for s in _MKT_UNRANKED_ORDER if s in present] or [
            _MKT_STATE_WORDS[s] for s in _MKT_UNRANKED_ORDER
        ]
    return []


def mkt_attention(model: dict) -> list:
    """市場總覽 ③：三張核心卡裡狀態不是 `ok` 的那幾張，合成一行「資料面：<卡名> <狀態>；…」。全是 `ok` → 空串列。"""
    parts = []
    for code in MKT_CARD_CODES:
        card = _find(model, code)
        if card is None or card.get("_state") == STATE_OK:
            continue
        words = _mkt_words(card)
        if words:
            parts.append(f"{card['title']} {'／'.join(words)}")
    if not parts:
        return []
    return [_item("", MKT_DATA_PREFIX + "；".join(parts), "灰")]


def exp_attention(model: dict) -> list:
    """標的探索 ③：`EXP-0` 已算出的無法判定檔數大於零時一行；否則空串列。"""
    light = _find(model, "EXP-0") or {}
    count = light.get("_undet_count") or 0
    if count <= 0:
        return []
    return [_item(SYMBOL_UNDECIDABLE, EXP_UNDET_TEXT.format(m=count), "灰")]


def alo_attention(model: dict) -> list:
    """資產配置 ③：`ALO-2` 算出帶外（「外」）的每一個類別一行，依 `ALO-2` 的列序；沒有就空串列。"""
    alo2 = _find(model, "ALO-2") or {}
    return [
        _item(SYMBOL_ATTENTION, ALO_OUT_TEXT.format(bucket=row["bucket_text"]), "中性")
        for row in alo2.get("_rows") or ()
        if row.get("band_text") == ALO_TEXT_OUT
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
    block = _find(model, HLD_ATTENTION_CODE) or {}
    count = 0
    for row in block.get("_rows") or ():
        name = row.get("fund_name")
        if isinstance(name, str) and not name.startswith(SYMBOL_ATTENTION):
            row["fund_name"] = f"{SYMBOL_ATTENTION} {name}"
            count += 1
    return count


def hld_counts(model: dict):
    """持倉體檢 ① 的三個計數那一行；不該列時回 None。

    只在「有持倉、門檻已設、燈不是紅」時列：沒有持倉或門檻未設時燈的那一句就是答案（59 第 3.3、3.4 節），
    紅燈時這一頁的數字先不要照著讀（`HLD-0` 紅燈文案），列計數會把讀不到的說成讀到了。
    """
    light = _find(model, "HLD-0") or {}
    hld1 = _find(model, "HLD-1") or {}
    hld2 = _find(model, "HLD-2") or {}
    if light.get("_tone") == "紅" or light.get("text") in (HLD_TEXT_NO_HOLDING, HLD_TEXT_NO_RULES):
        return None
    n = len(hld2.get("fund_groups") or ())
    if n == 0:
        return None
    return HLD_COUNTS_TEXT.format(
        n=n, attention=SYMBOL_ATTENTION, m=light.get("_deviation_count") or 0,
        undecidable=SYMBOL_UNDECIDABLE, j=hld1.get("missing_nav_count") or 0,
    )


def alo1_summary(block: dict) -> str:
    """`ALO-1` 移進 ④ 之後收合時的摘要那一行（44 第五節第四小節：缺了什麼在摘要那一行就看得見）。
    只拼卡上已經有的字：失敗佔位 → 狀態族「⛔ 取數失敗」（「此區塊暫時無法判定」一塊只寫一次，已寫在卡上；
    之七其二第 3 條）、其他佔位 → 那一句；否則類別數或「未設定」，加上容許帶那一句。"""
    placeholder = block.get("placeholder")
    if placeholder:
        if placeholder.get("_empty_kind") == STATE_ERROR:
            return f"{SYMBOL_ERROR} 取數失敗"
        return placeholder.get("text") or ""
    parts = [f"{len(block['_rows'])} 個類別"] if block.get("_rows") else list(block.get("unset_lines") or ())
    parts += list(block.get("tolerance_lines") or ())
    return "；".join(parts)
