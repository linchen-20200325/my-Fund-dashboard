# -*- coding: utf-8 -*-
"""💼 我的資產頁的 P3「頁級狀態」aggregation（page-level presentation status；純函式；零 streamlit import、零網路、零舊樹 import）。

客戶 2026-10-30 裁示（`docs/DECISIONS.md` `DEC-2026-10-30-04`；`docs/v2/74_assets_d3_formula_gate.md` 第 3 節 P3、第 4.1 節、第 5 節 F-n）：
**採 P3（頭條＋另一行），precedence 採 β**：
取數失敗 ＞ 無持倉 ＞ ◆ ＞ ◇ ＞ ⬜ ＞ 持股只評估一部分（H7／H6） ＞ 無偏離／帶內。
客戶原則：「整頁狀態必須同時涵蓋持股與配置；任何一區有異常、資料不足或尚未完整評估時，不得被另一區的正常結果遮蔽成『正常』。」

規則（74 Q1～Q8）：
- **Q1 分類**：每一區讀 logic 判定分支**明示**的分類鍵 `_page_class`（`HLD-0`／`ALO-0` 各自的 `conclusion_light` 分支寫入；詞表見
  `ui_v2/status_class.py`）。**不比對字面、不比對 `_tone`**。A6m、A5c、F-18（略過的分頁與持倉列）、F-19（有值而無目標）在 logic 裡已歸「資料未備」；
  H7／H6 部分評估歸「只評估一部分」（非正常）。
- **Q2 頭條**：依 β 排序，勝出的那一區是頭條；同級時「持股」先、「配置」後。
- **Q3 容器外觀**：容器的符號、狀態字、顏色＝頭條那一行自己的（`container`），不造新符號。
- **Q4 第二行**：另一區固定照印為第二行（含它自己的附行）。
- **Q5**：兩區都完整評估且正常 → 合成一行，照印兩句原字（以「；」相接，不寫「正常」）。
- **Q6**：兩區同為「尚未建立任何持倉」（同類、跑完管線後同字）→ 合成一行，前往 Sheets 鈕只出一次（`has_buttons` 只在合成行上為真）。
- **Q8 PE**：一區拋例外（`side["state"] == "error"`）→ 另一區照畫，拋例外的區歸取數失敗（沿用現況 F-15 (a)）。

**邊界（寫死）**：
- 本檔**只讀**兩個 side 的 model，**回傳新的 dict**（字串與 tuple 的複本），**絕不回寫** domain block；`HLD-0`／`ALO-0` 的原 rule result、
  原始狀態與 reason 完整留在各自區段、可追溯。
- 頭條**不是 rule result**：不進 Decision Digest、不得作為 Risk Cap 的輸入或輸出（回傳帶 `is_rule_result: False` 標明）；
  不新增買賣判斷；不改任何 threshold／formula／weight；不把 Missing／unavailable／not evaluated 補成 normal／safe／neutral／0。
- 不造第二套狀態詞：每一行的符號、狀態字、字樣都是該區（跑完正式管線後）的 block 自己的字；區段標籤「持股：」「配置：」與
  合成行「持股與配置：」沿用 74 F-5 推薦，**待客戶確認字樣**。
"""

from __future__ import annotations

from .. import sections, status_class as SC, symbols

AREA_HLD = "持股"
AREA_ALO = "配置"
AREA_BOTH = "持股與配置"
LABEL_SEPARATOR = "："           # 「持股：」「配置：」（74 F-5；待客戶確認字樣）
NORMAL_JOINER = "；"             # 兩句原字的分隔（74 Q5、F-5：與 C2 主判讀用的分隔相同）

KIND_TWO_ROWS = "two_rows"               # 頭條＋另一行
KIND_MERGED_NORMAL = "merged_normal"      # Q5：兩區都完整評估且正常
KIND_MERGED_NO_HOLDING = "merged_no_holding"   # Q6：同源同字（尚未建立任何持倉）

_BLOCK_CODE = {AREA_HLD: "HLD-0", AREA_ALO: "ALO-0"}
_AREA_ORDER = {AREA_HLD: 0, AREA_ALO: 1}   # 同級時「持股」先、「配置」後


def area_label(area: str) -> str:
    return f"{area}{LABEL_SEPARATOR}"


def _find(model: dict, code: str) -> dict:
    for block in model["blocks"]:
        if block["code"] == code:
            return block
    raise KeyError(code)


def _row(area, cls, glyph, state_word, text, lines, tone, code, has_buttons) -> dict:
    return {
        "area": area,
        "class": cls,
        "glyph": glyph,
        "state_word": state_word,
        "text": text,
        "lines": tuple(lines),
        "tone": tone,
        "code": code,                 # 這一行的來源 block（None＝這一區沒載入）；畫面要畫按鈕時回頭讀它
        "has_buttons": has_buttons,
    }


def classify_side(area: str, side: dict) -> dict:
    """一區 → 一個 row（新 dict）。`side` 是 `ui_v2/asset/page.py::_prepare` 的回傳（`state`＝`ok`／`error`／`no_active`）。

    `ok`：讀 `HLD-0`／`ALO-0` 的 `_page_class` 與它們已經算好的 `glyph`／`state_word`／`text`／附行；缺 `_page_class` 或值不在詞表 → 直接炸
    （§1 Fail Loud：不猜一個類）。`error`（PE／取數失敗）：歸取數失敗，符號與狀態字沿用既有的「⛔」「狀態：取數失敗」。
    `no_active`（沒有 Active Sheet，J-13 的第三種狀態）：只會在與另一區取數失敗混合時走到這裡（整頁都沒有 Active 時頁面早已改畫「尚未選定」）；
    歸「未設定」，字沿用 side["line"]（＝ `active_gate.TEXT_NO_ACTIVE`）。
    """
    state = side["state"]
    if state == "error":
        return _row(area, SC.ERROR, sections.SYMBOL_ERROR, symbols.STATE_PREFIX + "取數失敗", "", (), "紅", None, False)
    if state == "no_active":
        text = side["line"]   # `page.py::_prepare` 放的就是 `active_gate.TEXT_NO_ACTIVE`（「⬜ 尚未選定持倉資料來源」）
        glyph = symbols.SYMBOL_UNDECIDABLE
        return _row(area, SC.UNSET, glyph, symbols.STATE_PREFIX + "中性", text.removeprefix(glyph + " "), (), "灰", None, False)
    if state != "ok":
        raise ValueError(f"未知的 side state：{state!r}")
    code = _BLOCK_CODE[area]
    block = _find(side["model"], code)
    cls = block["_page_class"]   # 缺 → KeyError（logic 沒明示分類，本檔不猜）
    if cls not in SC.RANK:
        raise ValueError(f"{code} 的 _page_class 不在詞表：{cls!r}")
    if area == AREA_HLD:
        lines = block["lines"]
    else:
        # ALO-0 燈下自己的附行（略過的分頁、略過的持倉列）＝ `detail_lines` 最前面 `_attached_n` 行（跑完管線後的字）；沒有 → 空。
        n = block.get("_attached_n", 0)
        if n > len(block["detail_lines"]):
            raise ValueError(f"ALO-0 的 _attached_n={n} 超過 detail_lines 行數 {len(block['detail_lines'])}")
        lines = block["detail_lines"][:n]
    return _row(area, cls, block["glyph"], block["state_word"], block["text"], lines, block["_tone"], code,
                bool(block.get("buttons")))


def _merge(rows: list) -> dict | None:
    """Q5／Q6：只在兩區都完整評估且正常，或同為「尚未建立任何持倉」且跑完管線後同字時合成一行。"""
    first, second = rows
    if first["class"] == second["class"] == SC.NORMAL:
        # Q5：照印兩句原字，不寫「正常」，不加區段標籤；附行只留持股那一句（74 Q5）。
        merged = _row(None, SC.NORMAL, first["glyph"], first["state_word"],
                      first["text"] + NORMAL_JOINER + second["text"], first["lines"], first["tone"], first["code"], first["has_buttons"])
        return {"kind": KIND_MERGED_NORMAL, "rows": [merged]}
    if first["class"] == second["class"] == SC.NO_HOLDING and first["text"] == second["text"]:
        merged = _row(AREA_BOTH, SC.NO_HOLDING, first["glyph"], first["state_word"], first["text"], first["lines"],
                      first["tone"], first["code"], first["has_buttons"])
        return {"kind": KIND_MERGED_NO_HOLDING, "rows": [merged]}
    return None


def aggregate(hld_side: dict, alo_side: dict) -> dict:
    """P3 頁級狀態。純函式：只讀 `hld_side`／`alo_side`，回傳新 dict，絕不回寫任何 block。

    回傳 `{"kind", "rows", "container", "headline_class", "is_rule_result": False}`：
    `rows[0]` 是頭條；`rows[1]`（若有）是另一區，固定照印。`container` 的符號、狀態字、顏色＝頭條那一行自己的。
    """
    rows = [classify_side(AREA_HLD, hld_side), classify_side(AREA_ALO, alo_side)]
    merged = _merge(rows)
    if merged is None:
        rows.sort(key=lambda r: (SC.RANK[r["class"]], _AREA_ORDER[r["area"]]))
        merged = {"kind": KIND_TWO_ROWS, "rows": rows}
    head = merged["rows"][0]
    merged["container"] = {"glyph": head["glyph"], "state_word": head["state_word"], "tone": head["tone"]}
    merged["headline_class"] = head["class"]
    merged["is_rule_result"] = False   # 頭條不是 rule result：不進 Digest、不是 Risk Cap 的輸入或輸出
    return merged


def row_label(row: dict) -> str:
    """一行的畫面字（符號＋狀態字＋區段標籤＋字樣）。每個狀態至少有符號與狀態字，不靠顏色單獨辨識。"""
    parts = [row["glyph"], row["state_word"]]
    body = (area_label(row["area"]) if row["area"] else "") + row["text"]
    return "　".join(p for p in (" ".join(p for p in parts if p), body) if p)
