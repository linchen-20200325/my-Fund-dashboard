# -*- coding: utf-8 -*-
"""💼 我的資產頁的「視覺層級」模型（純函式；零 streamlit import、零網路、零舊樹 import）。

BL-0525 Batch D（客戶 2026-10-30 裁示 D-1～D-12，`DEC-2026-10-30-02`；線框 `docs/v2/73_assets_wireframe_batch_d.md`）。
輸入是 `ui_v2/alo`、`ui_v2/hld` 兩頁**已經算好**的 page model（含 `plain`／`symbols` 之後的畫面字）；輸出是 `page.py` 要畫的純資料。

**本檔只改位置與版型，不改資料語意，不新增任何彙總公式**（D-5A）：
- 總資產／總損益／報酬／配息四格一律誠實 Missing（`◇ 資料未備`），不估值、不借別的欄、不算任何合計；
- 一句主判讀只取既有已算出的值：持有檔數 `n`（`sections.hld_count_values`）、最大配置差距類別（`ALO-0` 的 `_leaders`）；
- Primary／Secondary 是 presentation component（D-7）：只讀既有 block output（`ALO-2`、`ALO-6`、`HLD-2`），不新增 block ID、不產生 canonical 值、
  不排序（沿既有正式規則的列序）、不截斷（D-12：全列）、不跨幣別合計或平均。
- 每個被收合或不畫的內容都留在 detail（`docs/v2/67` 第 5.1 節：簡化呈現不得減少決策脈絡）。
"""

from __future__ import annotations

from .. import presentation as P
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
TEXT_UNDECIDABLE_GAP = "配置差距無法判定"


def hero_sentence(counts, alo0) -> str:
    """「持有 ‹n› 檔基金；目前最大配置差距在 ‹類別›。」

    - `counts`：`sections.hld_count_values(hld_model)`（`(n, m, j)` 或 None）。None（無持倉、門檻未設、紅燈、n＝0）→ 「持有檔數無法判定」，
      不從別處補數、不把 missing 推成 0 或正常。
    - `alo0`：`ALO-0` 的 block（或 None＝配置那一側整個沒載入）。黃燈且有 `_leaders` → 點名全部並列類別（沿用 `ALO-0` 已算出的全列規則）；
      「各類別皆在容許帶內」→ 照 `ALO-0` 的字（不編「差距在 X」）；其餘（沒有持倉、目標或容許帶未設、讀不到…）→ 「配置差距無法判定」，
      原因由 `ALO-0` 自己那一行承擔。不寫加碼／減碼、不寫方向、不新算差距。
    """
    head = f"持有 {counts[0]} 檔基金" if counts else TEXT_UNDECIDABLE_COUNT
    leaders = tuple((alo0 or {}).get("_leaders") or ())
    if leaders:
        tail = f"目前最大配置差距在 {'、'.join(leaders)}"
    elif alo0 is not None and alo0.get("text") == alo_logic.TEXT_ALL_IN_BAND:
        tail = alo_logic.TEXT_ALL_IN_BAND
    else:
        tail = TEXT_UNDECIDABLE_GAP
    return f"{head}；{tail}。"


# ───────────────────────── D-4：Primary＝資產配置 現況 vs 目標（讀 ALO-2）─────────────────────────

PRIMARY_TITLE = "資產配置：現況 vs 目標"
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


def share_chips(alo4: dict, rows: list) -> list:
    chips = [P.chip(f"{len(rows)} 檔")]
    if alo4.get("basis_line"):
        chips.append(P.chip(alo4["basis_line"], "灰" if "未設定" in alo4["basis_line"] else "中性"))
    excluded = share_excluded_count(rows)
    if excluded:
        chips.append(P.chip(f"{excluded} 檔無基準值", "灰"))
    return chips


RETURN_LABEL = "區間報酬率"
TEXT_RETURNS_NOT_SUMMED = "原幣，不合計"


def return_rows(hld2: dict) -> list:
    """`HLD-2` 逐檔「區間報酬率」→ 水平條資料。`value`＝`_raw`（百分點，原幣）；非 ok 的檔 `value` 為 None，只印該格原字（不適用／資料未備／取數失敗）。
    標籤含幣別（`head_text`）。列序＝`HLD-2`。不跨幣別合計、不畫平均線。"""
    out = []
    for group in hld2.get("fund_groups") or ():
        node = next((mv for mv in group["main_values"] if mv.get("label") == RETURN_LABEL), None)
        if node is None:
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


def _nonblank(lines) -> list:
    return [line for line in lines if isinstance(line, str) and line.strip()]


def share_detail(alo6: dict) -> dict:
    return P.detail_model(why=_nonblank([alo6.get("answers")]), limits=_nonblank(list(alo6.get("footer_lines") or ())
                                                                              + list(alo6.get("detail_lines") or ())))


def returns_detail(hld2: dict) -> dict:
    return P.detail_model(why=_nonblank([hld2.get("answers")]),
                          limits=_nonblank(list(hld2.get("detail_lines") or ()) + [TEXT_RETURNS_NOT_SUMMED]))


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


def container_title(name, codes, titles: dict) -> str:
    """容器標題：`<名稱>　—　<其內塊的正式標題以頓號列出>`（只用既有塊標題，沒有新詞）。"""
    return f"{name}　—　{'、'.join(titles[c] for c in codes)}"


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


def page_strings(counts, alo0) -> list:
    """本頁新增層級會印出的固定字串（供禁詞／方向性字樣掃描）。"""
    out = [PAGE_TITLE, PAGE_ANSWERS, hero_sentence(counts, alo0), PRIMARY_TITLE, SHARE_TITLE, RETURNS_TITLE,
           SECONDARY_DETAIL_TITLE, PRIMARY_DETAIL_TITLE, TEXT_RETURNS_NOT_SUMMED,
           CONTAINER_CONDITIONS, CONTAINER_HOLD_DETAIL, CONTAINER_ALLOC_DETAIL, missing_group()["title"]]
    out += P.detail_texts(summary_strip()["detail"])
    out += [s["label"] for s in summary_strip()["slots"]]
    out += [item["reason"] for item in missing_group()["items"]]
    return out
