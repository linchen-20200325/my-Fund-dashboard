# -*- coding: utf-8 -*-
"""💼 我的資產頁的「視覺層級」模型（純函式；零 streamlit import、零網路、零舊樹 import）。

BL-0525 Batch D（客戶 2026-10-30 裁示 D-1～D-12，`DEC-2026-10-30-02`；線框 `docs/v2/73_assets_wireframe_batch_d.md`）。
輸入是 `ui_v2/alo`、`ui_v2/hld` 兩頁**已經算好**的 page model（含 `plain`／`symbols` 之後的畫面字）；輸出是 `page.py` 要畫的純資料。

**本檔只改位置與版型，不改資料語意，不新增任何彙總公式**（D-5A）：
- 總資產／總損益／報酬／配息四格一律誠實 Missing（`◇ 資料未備`），不估值、不借別的欄、不算任何合計；
- 一句主判讀只取既有已算出的值：持有檔數 `n`（`sections.hld_holding_count`：`HLD-2` 實際列出的不重複基金檔數，與門檻無關）、最大配置差距類別（`ALO-0` 的 `_leaders`）；
- Primary／Secondary 是 presentation component（D-7）：只讀既有 block output（`ALO-2`、`ALO-6`、`HLD-2`），不新增 block ID、不產生 canonical 值、
  不排序（沿既有正式規則的列序）、不截斷（D-12：全列）、不跨幣別合計或平均。
- 每個被收合或不畫的內容都留在 detail（`docs/v2/67` 第 5.1 節：簡化呈現不得減少決策脈絡）。
"""

from __future__ import annotations

from .. import presentation as P
from .. import page_health, sections, symbols
from ..alo import logic as alo_logic

SLUG = "ast"
PAGE_TITLE = "💼 我的資產"
PAGE_ANSWERS = "我的錢放在哪？有沒有偏離？哪些持股需要注意？"   # D-9：沿用，正式保留

# ───────────────────────── D-5B：第一屏 compact summary strip（四格，一個 summary container）─────────────────────────

SUMMARY_LABELS = ("總資產", "總損益", "報酬", "配息")
SUMMARY_MISSING_TEXT = P.MISSING_CHIP_TEXT   # `◇ 資料未備`（44 之十九其五第 4 條；不寫「n 項資料未備」、不自創新詞）
SUMMARY_DETAIL_WHY = "這四項目前沒有已核准的彙總算法，本頁不估值、不借別的欄位、不做任何合計。"
SUMMARY_DETAIL_SOURCE = "各檔的原幣數值見下方「持股明細」與「各檔區間報酬」，逐檔呈現。"
SUMMARY_DETAIL_LIMITS = ("各檔數值為原幣，不跨幣別合計或平均。", "未驗證的匯率保持關閉，不以匯率換算成單一幣別。")
SUMMARY_DETAIL_WHERE = "待彙總算法核准後才會顯示；目前請看逐檔數值。"


def summary_strip() -> dict:
    """四格 summary：`{"slots": [{"label", "value", "tone"}], "detail": detail_model}`。四格值一律 Missing。"""
    slots = [{"label": label, "value": SUMMARY_MISSING_TEXT, "tone": "灰"} for label in SUMMARY_LABELS]
    detail = P.detail_model(
        why=[SUMMARY_DETAIL_WHY], source=[SUMMARY_DETAIL_SOURCE], limits=list(SUMMARY_DETAIL_LIMITS),
        where=[SUMMARY_DETAIL_WHERE],
    )
    return {"slots": slots, "detail": detail}


# ───────────────────────── D-10：一句主判讀（C2 去重版）─────────────────────────

TEXT_UNDECIDABLE_COUNT = "持有檔數無法判定"
TEXT_UNDECIDABLE_GAP = alo_logic.TEXT_UNDECIDABLE_GAP   # 「配置差距無法判定」：字面不變，定義自 2026-10-30 起住在 `ui_v2/alo/logic.py`（`ALO-0` 也用它，DEC-2026-10-30-04）


def hero_holding_count(n, holding_error: bool):
    """主判讀用的持有檔數：持倉來源本身有錯（`prepare_live` 回傳的 `holding_error`＝`dataset["errors"]["holding"]` 有字：整張讀不到，
    或部分分頁被略過）時，`HLD-2` 列出的檔數建立在不完整的持倉上，不能當成「持有 n 檔」→ None（「持有檔數無法判定」，D-10：資料不足照實說）。
    沒有持倉來源錯誤（含只是門檻未設、燈紅是別的原因）→ 原樣用 `sections.hld_holding_count` 的 n。HLD 自己的判定、`HLD-2` 的列一個都不動。"""
    return None if holding_error else n


def has_unevaluated_category(alo2) -> bool:
    """`ALO-2` 有沒有任何一列沒評估到差距（`_diff` 為 None）：目標比重留空、持倉類別沒有目標（例：未分類）、或比重基準值缺。
    只讀 `ALO-2` 已算出的 `_diff`，不另算；沒有 `ALO-2`（配置那一側沒載入）或沒有任何列 → False（沒有「被漏掉的類別」可說，
    該情形的字樣由 `ALO-0` 自己那一行承擔）。`docs/v2/74` A6m（既有缺陷 F-13）：`ALO-0` 在這幾種情形仍寫「各類別皆在容許帶內」，
    本頁一句主判讀不複述那一句。
    ~~⚠️ 只涵蓋 A6m 條件 (1)(2)；條件 (3)（持倉來源有略過的 ALO 分頁）**沒有**涵蓋：`prepare_live` 的回傳不帶 `notes["skipped"]`，
    已記在 `docs/v2/71`（稽核回修〈沒做或沒驗〉第 4 點）與 `docs/v2/74`（A6m、檔頭 v5 更正），待客戶裁示後再接。~~
    → 2026-10-30（客戶裁示 `DEC-2026-10-30-04` F-13／F-18；狀態更新，不是漏刪）：條件 (3) 與 BL-0411 略過的持倉列改由 `ALO-0` 自己記的
    `_incomplete` 承擔（資料承載層把略過的分頁與列交進 dataset，`ui_v2/alo/logic.py::conclusion_light`），見 `allocation_incomplete`。"""
    return any(row["_diff"] is None for row in (alo2 or {}).get("_rows") or ())


def allocation_incomplete(alo0, alo2) -> bool:
    """一句主判讀的 `incomplete`：`ALO-2` 有沒評估到的列（`has_unevaluated_category`），或 `ALO-0` 自己記了 `_incomplete`
    （略過的保單分頁、略過的持倉列，DEC-2026-10-30-04 F-13 條件 (3)／F-18）。只讀既有旗標，不另算。"""
    return has_unevaluated_category(alo2) or bool((alo0 or {}).get("_incomplete"))


def hero_sentence(n, alo0, *, incomplete: bool = False) -> str:
    """「持有 ‹n› 檔基金；目前最大配置差距在 ‹類別›。」

    - `n`：`hero_holding_count(sections.hld_holding_count(hld_model), holding_error)`（持有檔數 int，或 None）。None → 「持有檔數無法判定」，
      不從別處補數、不把 missing 推成 0 或正常；門檻未設或燈紅（持倉來源沒有錯）時 `n` 仍照 `HLD-2` 列出的檔數（它與門檻無關）。
    - `alo0`：`ALO-0` 的 block（或 None＝配置那一側整個沒載入）。黃燈且有 `_leaders` → 點名全部並列類別（沿用 `ALO-0` 已算出的全列規則，
      與 parent 相同）；「各類別皆在容許帶內」→ 照 `ALO-0` 的字（不編「差距在 X」）；其餘（沒有持倉、目標或容許帶未設、讀不到…）→
      「配置差距無法判定」，原因由 `ALO-0` 自己那一行承擔。不寫加碼／減碼、不寫方向、不新算差距。
    - `incomplete`：`has_unevaluated_category(ALO-2)`。**為真時一律「配置差距無法判定」**，不論 `ALO-0` 寫皆在帶內或已點名類別（A7）。
      理由：「目前最大配置差距在 X」是對整個類別集合的最大值宣稱；有類別 `_diff=None`（例：`partial` 的債券有目標但值缺）時，
      該類別的差距未知、可能才是最大，說「最大」就是在不完整的集合上宣稱最大值（客戶裁示 D-10：不把 Missing 推論成正常；資料不足照實「無法判定」）。
      `ALO-0` 本身不動，仍在 Primary 寫它自己的「X 與目標差 N 個百分點」——它從不說「最大」，兩者不矛盾。
      （稽核回修第三輪 SF-2：還原第一輪的嚴格行為，取代第二輪 S5 的「A7 照 parent 點名」。客戶若要放寬為「有 A7 領先者就點名」，
      只需把下面 `incomplete` 判斷搬到只包「皆在帶內」那個分支，是一行改動。）
    """
    head = f"持有 {n} 檔基金" if n else TEXT_UNDECIDABLE_COUNT
    leaders = tuple((alo0 or {}).get("_leaders") or ())
    if incomplete:
        tail = TEXT_UNDECIDABLE_GAP
    elif leaders:
        tail = f"目前最大配置差距在 {'、'.join(leaders)}"
    elif alo0 is not None and alo0.get("text") == alo_logic.TEXT_ALL_IN_BAND:
        tail = alo_logic.TEXT_ALL_IN_BAND
    else:
        tail = TEXT_UNDECIDABLE_GAP
    return f"{head}；{tail}。"


# ───────────────────────── D-4：Primary＝資產配置 現況 vs 目標（讀 ALO-2）─────────────────────────

ALLOC_LABEL = "資產配置"   # `PRIMARY_TITLE` 的前半；頁級資料日那一列標「配置這一側」時也用這個詞（沿用，不另創）
PRIMARY_TITLE = f"{ALLOC_LABEL}：現況 vs 目標"
PRIMARY_DETAIL_TITLE = "▸ 各類別全表‧來源‧限制"
TEXT_CURRENT = "現況"
TEXT_TARGET = "目標"


def _pct_or_none(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def primary_rows(alo2: dict) -> list:
    """`ALO-2` 的逐類別列 → 圖的資料。數值原樣取 `_current_pct`／`_target_pct`（None＝該格 Missing，圖上不畫條、只印原字）。
    列序＝`ALO-2` 的列序（既有正式規則），不重排。"""
    out = []
    for row in alo2.get("_rows") or ():
        out.append({
            "bucket": row["bucket_text"],
            "current_pct": _pct_or_none(row.get("_current_pct")),
            "target_pct": _pct_or_none(row.get("_target_pct")),
            "current_text": row["current_text"], "target_text": row["target_text"],
            "diff_text": row["diff_text"], "band_text": row["band_text"],
        })
    return out


def primary_chips(alo1: dict, alo4: dict, as_of) -> list:
    """Primary 的 chips（3～4 枚）：容許帶、比重基準、資料日。字一律取 `ALO-1`／`ALO-4` 卡上**已有的行**，不另寫；
    「最大差距」不再做成 chip（`ALO-0` 那一行已承擔，D-10 去重）。唯讀、不可點（基準只能由 `ALO-4` 的使用者設定決定）。"""
    chips = []
    for lines in (alo1.get("tolerance_lines") or (), ([alo4.get("basis_line")] if alo4.get("basis_line") else [])):
        for line in lines:
            chips.append(P.chip(line, "灰" if "未設定" in line else "中性"))
    if as_of:
        chips.append(P.chip(f"資料日 {as_of[5:]}"))
    return chips


# ───────────────────────── D-6／D-12：Secondary ×2（基金占比、各檔區間報酬；全列、不截斷）─────────────────────────

SHARE_TITLE = "基金占比"
RETURNS_TITLE = "各檔區間報酬（原幣）"
SECONDARY_COUNT = 2   # 客戶 2026-10-30：2 張真資料，不湊第三張
SECONDARY_DETAIL_TITLE = "▸ 為什麼‧來源‧限制‧去哪補"


def share_rows(alo6: dict) -> list:
    """`ALO-6` 逐檔「佔總體比」→ 水平條資料。`_in_total` 是 0～1 的比例；None（缺基準值）＝不畫條、只印 `in_total_text` 原字。列序＝`ALO-6`。"""
    out = []
    for row in alo6.get("_rows") or ():
        ratio = row.get("_in_total")
        ratio = ratio if isinstance(ratio, (int, float)) and not isinstance(ratio, bool) else None
        out.append({"label": row["fund_text"], "bucket": row["bucket_text"], "ratio": ratio, "text": row["in_total_text"]})
    return out


def share_excluded_count(rows: list) -> int:
    return sum(1 for r in rows if r["ratio"] is None)


def share_omitted_lines(alo2) -> list:
    """BL-0411／F-18 第二輪（獨立稽核 S2；`DEC-2026-10-30-04`）：保單分頁上沒寫進持倉的列（`ALO-2` 記的 `_omitted_rows`）各一行，
    字同 `ALO-0` 燈下那幾行（`page_health.omitted_row_lines`，正式模式的 ◇ 同 `ui_v2/symbols.py`）。沒有 → 空 list。只讀既有紀錄，不另算。"""
    rows = (alo2 or {}).get("_omitted_rows") or ()
    return [line.replace(symbols.MISSING_OLD, symbols.MISSING_NEW) for line in page_health.omitted_row_lines(rows)]


def share_chips(alo4: dict, rows: list, *, omitted_lines=()) -> list:
    """`omitted_lines`（`share_omitted_lines`）非空時，~~「N 檔」~~ 那一枚改既有 `◇ 資料未備`（`P.missing_chip`）：
    本卡列出的只是被接受的持倉，「N 檔」會假裝覆蓋完整集合（D-3 第二輪，稽核 S2；同合併頁一句主判讀「持有檔數無法判定」）。"""
    chips = [P.missing_chip() if omitted_lines else P.chip(f"{len(rows)} 檔")]
    if alo4.get("basis_line"):
        chips.append(P.chip(alo4["basis_line"], "灰" if "未設定" in alo4["basis_line"] else "中性"))
    excluded = share_excluded_count(rows)
    if excluded:
        chips.append(P.chip(f"{excluded} 檔無基準值", "灰"))
    return chips


RETURN_LABEL = "區間報酬率"
TEXT_RETURNS_NOT_SUMMED = "原幣，不合計"


def return_rows(hld2: dict) -> list:
    """`HLD-2` 逐檔「區間報酬率」→ 水平條資料。`value`＝`_raw`（百分點，原幣）；非 ok 的檔 `value` 為 None，只印該格原字（不適用／資料未備／取數失敗）；
    該檔根本沒有「區間報酬率」那一格 → 仍列該檔，`value` 為 None、字寫 `◇ 資料未備`（不靜默丟列）。
    標籤含幣別（`head_text`）。列序＝`HLD-2`。不跨幣別合計、不畫平均線。"""
    out = []
    for group in hld2.get("fund_groups") or ():
        node = next((mv for mv in group["main_values"] if mv.get("label") == RETURN_LABEL), None)
        if node is None:   # 這一檔沒有「區間報酬率」那一格：照列該檔、誠實寫資料未備（不整列丟掉）
            out.append({"label": group["head_text"], "ccy": group.get("_ccy", ""), "value": None, "text": P.MISSING_CHIP_TEXT})
            continue
        value = node.get("_raw") if node.get("_has_number") else None
        value = value if isinstance(value, (int, float)) and not isinstance(value, bool) else None
        out.append({"label": group["head_text"], "ccy": group.get("_ccy", ""), "value": value, "text": node["text"]})
    return out


def return_scale(rows: list) -> float:
    """條長的分母＝可畫的最大絕對值（0 → 1.0，避免除零；全部不可畫時不會被用到）。純顯示比例，不是分析值。"""
    values = [abs(r["value"]) for r in rows if r["value"] is not None]
    top = max(values) if values else 0.0
    return top if top > 0 else 1.0


def return_chips(hld4: dict, rows: list) -> list:
    window = {f["name"]: f.get("_value") for f in hld4.get("inputs") or ()}
    start, end = window.get("window_start"), window.get("window_end")
    chips = [P.chip(f"區間 {start}～{end}") if start and end else P.chip("區間未設", "灰")]
    chips.append(P.chip(f"{sum(1 for r in rows if r['value'] is not None)} 檔有值"))
    chips.append(P.chip(TEXT_RETURNS_NOT_SUMMED, "灰"))
    return chips


# 不過濾空白行：`P.detail_model` 的契約是「空行代表上游漏了資訊」→ 當場 `ValueError`（不默默吞掉）；單頁也是原樣畫上游給的行。
def share_detail(alo6: dict, *, omitted_lines=()) -> dict:
    """`omitted_lines` 非空時接在 `ALO-6` 表尾（各類別內與總體的佔比合計）之後：那幾個合計只涵蓋被接受的持倉，
    略過的是哪幾列、為什麼緊接著寫出（D-3 第二輪，稽核 S2）。表尾字一個不改（量的不變式照舊成立）。"""
    return P.detail_model(why=[alo6["answers"]],
                          limits=list(alo6["footer_lines"]) + list(omitted_lines) + list(alo6["detail_lines"]))


def returns_detail(hld2: dict) -> dict:
    return P.detail_model(why=[hld2["answers"]], limits=list(hld2["detail_lines"]) + [TEXT_RETURNS_NOT_SUMMED])


# ───────────────────────── 層 3／層 4：grouped containers（3a＋4a；D-1／D-2／D-11）─────────────────────────

# 容器名（D-11：「我的條件」「持股明細」「配置明細」；單塊容器沿用該塊自己的正式標題，不另創新詞）。
HOLDINGS_LABEL = "持股明細"   # 第 8 區（客戶產品結構第 8 項）：HLD-2／HLD-3 逐檔卡
CONTAINER_CONDITIONS = "我的條件"
CONTAINER_HOLD_DETAIL = "持股明細"
CONTAINER_ALLOC_DETAIL = "配置明細"

# 容器 → 其內塊代號（順序＝容器內小標題順序）。block ID 一個都不少：HLD-4／ALO-1／ALO-4、HLD-5、ALO-5、HLD-6／7／8、ALO-6／7。
LAYER3_CONTAINERS = (
    (CONTAINER_CONDITIONS, ("HLD-4", "ALO-1", "ALO-4")),
    (None, ("HLD-5",)),     # 單塊容器：標題＝塊自己的標題
    (None, ("ALO-5",)),
)
LAYER4_CONTAINERS = (
    (CONTAINER_HOLD_DETAIL, ("HLD-6", "HLD-7", "HLD-8")),
    (CONTAINER_ALLOC_DETAIL, ("ALO-6", "ALO-7")),
)
ALL_GROUPED_CODES = tuple(code for _name, codes in LAYER3_CONTAINERS + LAYER4_CONTAINERS for code in codes)


def container_title(name, codes, titles: dict, states: dict | None = None) -> str:
    """容器標題：`<名稱>　—　<其內塊的正式標題以頓號列出>`（只用既有塊標題，沒有新詞）。

    `states`：`{塊代號: 該塊單頁展開區標題上「—」後面那一句}`，只放**有狀態**（取數失敗、資料未備、缺 X、尚未設定…）的塊。
    有狀態的塊寫成 `<標題>　—　<狀態>`（單頁 `_expander` 的同一個字面），沒有就只寫標題。收合時狀態就看得見，
    不把空狀態藏進展開內容（44 第五節第四小節）。
    """
    states = states or {}
    return f"{name}　—　{'、'.join(titles[c] + (f'　—　{states[c]}' if states.get(c) else '') for c in codes)}"


# 單頁展開區標題「—」後面那一句，凡帶下列字樣就是在說「這一塊現在不完整」（字樣全部是各頁 `logic`／`sections` 既有的；本頁不新編）。
STATE_MARKERS = (sections.SYMBOL_ERROR, sections.SYMBOL_MISSING, sections.SYMBOL_UNDECIDABLE, "取數失敗", "取不到", "未設定", "資料未備",
                 "缺 ", "被排除", "門檻 0 列")
# 塊上本來就有的「這一塊有東西沒到位」旗標（非空串列＝有狀態）：先看旗標、再看字樣。`ALO-1` 的 `unset_lines`（目標比重未設）、
# `ALO-4` 的 `unassigned_lines`（有基金未指派類別）／`bucket_unset_lines`（類別名稱未設）／`mismatch_lines`（類別名稱對不上）。
STATE_LIST_FLAGS = ("unset_lines", "unassigned_lines", "bucket_unset_lines", "mismatch_lines")


def block_state(block: dict, summary) -> str | None:
    """一塊在單頁展開區標題上「—」後面那一句（`summary`）→ 這一塊現在是不是有狀態：有 → 回那一句，沒有 → None。

    判斷只讀塊上既有的東西，不新判定：佔位（`placeholder`）、紅／灰色調（`_tone`）、`STATE_LIST_FLAGS` 的旗標、
    或那一句本身帶 `STATE_MARKERS` 的字樣（字樣判斷是啟發式：漏掉的狀態只會讓標題比單頁短，不會多編狀態）。正常的塊（類別數、檔數、列數、設定摘要）回 None，容器標題照舊只列標題。
    已知還沒涵蓋的字樣見 `docs/v2/71`（稽核回修第二輪〈沒做或沒驗〉）；`tests/ui_v2/test_ast_page.py` 對 ALO／HLD 全部 fixture 情境逐塊釘住。
    """
    if not isinstance(summary, str) or not summary.strip():
        return None
    if (block.get("placeholder") or block.get("_tone") in ("紅", "灰") or any(block.get(flag) for flag in STATE_LIST_FLAGS)
            or any(m in summary for m in STATE_MARKERS)):
        return summary
    return None


# ───────────────────────── 頁級資料日（兩側各一列，缺就寫缺）─────────────────────────


def data_date_line(label: str, as_of) -> str:
    """「<側> 資料截至 <日期>」：字樣取 `page_health.AS_OF_LABEL`／`AS_OF_UNKNOWN`（單頁頁首 `header_view` 的同一組字）。
    沒有資料日（那一側沒載入、或沒有任何淨值日期）→ 「—」，不補日期、不借另一側的。"""
    return f"{label}　{page_health.AS_OF_LABEL} {as_of or page_health.AS_OF_UNKNOWN}"


# ───────────────────────── 頁尾（D-11：不新增結論；兩區「不負責什麼」都保留，只去重複）─────────────────────────

SELF_POINTER = "，單檔績效請到我的持股"   # 配置頁頁尾的指路半句：「我的持股」在合併後就是本頁自己，指向自己的那半句去掉；其餘（不產生再平衡動作、挑標的請到找基金…）逐字保留


def footer_text(footer_lines_by_side) -> str:
    """兩側（配置、持股）已經過 `plain` 的頁尾句子 → 合併頁頁尾一段。逐字沿用、完全相同的句子只留一句；只移除指向本頁自己的那半句。不加任何新句。"""
    seen = []
    for lines in footer_lines_by_side:
        for line in lines:
            line = line.replace(SELF_POINTER, "")
            if line not in seen:
                seen.append(line)
    return " ".join(seen)


# ───────────────────────── ▸ 尚未取得（11）─────────────────────────

MISSING_GROUP_ITEMS = (
    ("總資產", "沒有已核准的彙總算法；跨幣別不合計"),
    ("總損益", "沒有已核准的彙總算法；跨幣別不合計"),
    ("組合報酬", "沒有已核准的彙總算法；跨幣別不合計"),
    ("組合配息", "沒有已核准的彙總算法；跨幣別不合計"),
    ("區域", "尚無已核准的資料來源"),
    ("幣別曝險", "需要新的彙總，且換算受匯率驗證限制；本批不做"),
    ("投資風格", "尚無已核准的資料來源"),
    ("同類平均", "尚無已核准的資料來源"),
    ("基準指數", "尚無已核准的資料來源"),
)
MISSING_GROUP_PREFIX = "▸ 尚未取得"


def missing_group() -> dict:
    """「▸ 尚未取得」：預設收合，摘要列就點名缺哪幾項；每一項 `◇ 資料未備`＋一句原因，一項不少。"""
    names = "、".join(name for name, _why in MISSING_GROUP_ITEMS)
    items = [{"name": name, "chip": P.missing_chip(), "reason": why} for name, why in MISSING_GROUP_ITEMS]
    return {"title": f"{MISSING_GROUP_PREFIX}：{names}", "items": items}


def page_strings(n, alo0) -> list:
    """本頁新增層級會印出的固定字串（供禁詞／方向性字樣掃描）。"""
    out = [PAGE_TITLE, PAGE_ANSWERS, hero_sentence(n, alo0), PRIMARY_TITLE, SHARE_TITLE, RETURNS_TITLE,
           SECONDARY_DETAIL_TITLE, PRIMARY_DETAIL_TITLE, TEXT_RETURNS_NOT_SUMMED,
           CONTAINER_CONDITIONS, CONTAINER_HOLD_DETAIL, CONTAINER_ALLOC_DETAIL, missing_group()["title"]]
    out += P.detail_texts(summary_strip()["detail"])
    out += [s["label"] for s in summary_strip()["slots"]]
    out += [item["reason"] for item in missing_group()["items"]]
    return out
