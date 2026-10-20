# -*- coding: utf-8 -*-
"""各頁資料狀態的原因項目、件數、主要原因與總表列（BL-0250 批次 3-B；`docs/v2/44_fund_ui_ssot.md` 第七節第三小節之十三其七；
線框第六版 `docs/v2/61_bl0250_batch3_wireframe.md` 1.1、1.2、6.3；總管 2026-10-19 裁定 (a)(b)(c)）。

純函式模組：**不 import streamlit、不 import 舊樹、不 import 任何同樹模組**（`tests/ui_v2/test_ui_v2_live_import_guard.py`），
只用標準庫。不取數、不寫入、不讀時鐘（記錄時間由呼叫端給）。

⚠️ **本批狀態：純函式已落地、尚未接線。** 四頁「在產生 ⛔／◇／◷／尚未設定的那個地方交出原因項目」那一步，有幾處 ◇ 不改資料
語意就寫不出資料類（逐處見本批回報與 44 之十三其五），依總管裁定 (a) 的停止條件停下；接線、設定與診斷頁的總表塊等那幾處裁定後一起做。

**一項＝一個原因**（線框 1.1）：
- 尚未設定：鍵＝哪一個設定；取數失敗、資料未備：鍵＝哪一類資料；不是最新：整頁只算一項。
- 同一個原因影響幾張卡，都只算一項（同種類同鍵的項目合併，受影響清單取聯集）。
- 尚未設定與取數失敗永遠分開數，即使兩者在卡上都是 ⛔。
- 頁首「另有」＝全部項數扣掉主要原因那一項；總表「狀態」欄＝全部項數（含主要原因）。

**主要原因**（線框 1.2 新設計 A；總管裁定 (c)：3-C 的頁首主要原因一行必須呼叫 `main_reason`，兩邊在建構上逐字相同）：
第一個成立的順位就是主要原因 —— 1 整頁載不出來；2 尚未設定而且因此有主值讀不到；3 取數失敗（含改用預存淨值）；4 資料未備；
5 不是最新；6 只有「只影響比較值的尚未設定」這一種問題；都沒有 → 沒有主要原因。同順位比：(a) 讓比較多張核心卡有值讀不到的；
(b) 影響結論燈的；(c) 該頁固定的順序 —— 本模組**不訂**那一份順序，由交出項目的那一頁在產生處寫進 `order`（數字小的在前）。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# ───────────────────────── 種類與符號 ─────────────────────────

KIND_UNCONFIGURED = "尚未設定"
KIND_FETCH = "取數失敗"
KIND_MISSING = "資料未備"
KIND_STALE = "不是最新"
KINDS = (KIND_UNCONFIGURED, KIND_FETCH, KIND_MISSING, KIND_STALE)

SYMBOL_ERROR = "⛔"
SYMBOL_MISSING = "◇"
SYMBOL_STALE = "◷"
# 「另有」行與總表件數：尚未設定一律不加符號（線框 1.2 統一規則；客戶核准「另有 N 項」不加符號），其餘照各自符號。
COUNT_SYMBOLS = {KIND_UNCONFIGURED: "", KIND_FETCH: SYMBOL_ERROR, KIND_MISSING: SYMBOL_MISSING, KIND_STALE: SYMBOL_STALE}
STALE_KEY = "整頁"

PAGE_ORDER = ("mkt", "hld", "exp", "alo")
PAGE_NAMES = {"mkt": "市場總覽", "hld": "持倉體檢", "exp": "標的探索", "alo": "資產配置"}

TEXT_NOT_OPENED = "本次尚未開過這一頁"
AS_OF_LABEL = "資料截至"
AS_OF_UNKNOWN = "—"
NO_VALUE = "—"
TEXT_COUNT = "{kind} {n} 項"
TEXT_MAIN_PAGE_FAILED = "⛔ 本頁暫時無法判定：{cls}取數失敗"
TEXT_MAIN_UNCONFIGURED = "⛔ 主要原因：{key}尚未設定"
TEXT_MAIN_FETCH = "⛔ 主要原因：{key}取數失敗"
TEXT_MAIN_RETREAT = "⛔ 主要原因：{key}取數失敗，改用 {day} 的預存淨值（{codes}）"
TEXT_MAIN_MISSING = "◇ 主要原因：{key}資料未備"
TEXT_MAIN_STALE = "◷ 主要原因：部分只顯示最後有效資料"
TEXT_MAIN_COMPARE_ONLY = "尚未設定：{keys}（只影響比較值）"
TEXT_CARDS_UNREADABLE = "（{n} 張卡有值讀不到）"

DETAIL_LABELS = ("資料類", "項目", "狀態", "最近觀測日或資料日期", "最近取得時間（台北時間）", "延遲天數", "來源層級")
SUMMARY_LABELS = ("頁", "狀態", "主要原因", "記錄時間")

TAIPEI = timezone(timedelta(hours=8))
# 跨頁留著的記錄（每頁每次渲染整格覆寫）。⛔ 不得列入 `ui_v2/app_preview.py::_PAGE_STATE_TO_DROP`（同 `plain.RAW_STATE`）。
STATE_KEY = "_ui_v2_page_health"


# ───────────────────────── 原因項目 ─────────────────────────


def affected(card: str, item: str = "", *, core: bool = False, unreadable: bool = False, data_class=None,
             obs=None, fetched=None, delay=None, tier=None) -> dict:
    """受影響的一張卡或一個項目。`core`：是不是該頁的核心卡；`unreadable`：這一處的值讀不到（⛔ 或 ◇，不是只有比較值 ⬜）。
    `data_class`：這一處資料的資料類（由產生處寫明；不知道就留 None，明細表寫「—」，不猜）。其餘四個是明細表的來源與延遲欄。"""
    return {"card": card, "item": item, "core": bool(core), "unreadable": bool(unreadable), "data_class": data_class,
            "obs": obs, "fetched": fetched, "delay": delay, "tier": tier}


def make_item(kind: str, key: str, entries=(), *, lamp: bool = False, order: int = 0, retreat=None) -> dict:
    """一個原因項目。`kind` 四種之一；`key` 尚未設定寫哪一個設定、取數失敗與資料未備寫哪一類資料、不是最新一律 `STALE_KEY`。
    `lamp`：這個原因有沒有影響結論燈；`order`：該頁固定順序（產生處給）；`retreat`：改用預存淨值時 `{"day": 日期, "codes": [代碼…]}`。"""
    if kind not in KINDS:
        raise ValueError(f"不認得的種類：{kind!r}")
    if kind == KIND_STALE:
        key = STALE_KEY
    if not isinstance(key, str) or not key:
        raise ValueError(f"{kind} 的項目沒有鍵（不猜）")
    if retreat is not None and kind != KIND_FETCH:
        raise ValueError("改用預存淨值只屬取數失敗")
    return {"kind": kind, "key": key, "affected": [dict(e) for e in entries], "lamp": bool(lamp), "order": int(order),
            "retreat": None if retreat is None else {"day": retreat["day"], "codes": list(retreat["codes"])}}


def main_unreadable_cards(item: dict) -> list:
    """這個原因讓哪幾張核心卡有值讀不到（依出現順序、不重複）。"""
    out = []
    for entry in item["affected"]:
        if entry["core"] and entry["unreadable"] and entry["card"] not in out:
            out.append(entry["card"])
    return out


def blocks_main(item: dict) -> bool:
    """有沒有讓主值讀不到。"""
    return bool(main_unreadable_cards(item))


def merge_items(items) -> list:
    """同種類、同鍵的項目合併成一項（同一個原因影響幾張卡都只算一項）：受影響清單取聯集（同卡同項目只留一筆）、
    `lamp` 取或、`order` 取小、改用預存淨值的代碼取聯集。依第一次出現的順序回傳。"""
    merged: dict = {}
    for item in items:
        key = (item["kind"], item["key"])
        if key not in merged:
            merged[key] = make_item(item["kind"], item["key"], (), lamp=item["lamp"], order=item["order"],
                                    retreat=item["retreat"])
        target = merged[key]
        seen = {(e["card"], e["item"]) for e in target["affected"]}
        for entry in item["affected"]:
            if (entry["card"], entry["item"]) not in seen:
                target["affected"].append(dict(entry))
                seen.add((entry["card"], entry["item"]))
        target["lamp"] = target["lamp"] or item["lamp"]
        target["order"] = min(target["order"], item["order"])
        if item["retreat"] and target["retreat"] is not item["retreat"]:
            if target["retreat"] is None:
                target["retreat"] = {"day": item["retreat"]["day"], "codes": list(item["retreat"]["codes"])}
            else:
                for code in item["retreat"]["codes"]:
                    if code not in target["retreat"]["codes"]:
                        target["retreat"]["codes"].append(code)
    return list(merged.values())


def counts(items) -> dict:
    """依線框 1.1 的件數：種類 → 項數（合併後；不是最新整頁最多 1 項）。只回項數大於零的種類，依 `KINDS` 的順序。"""
    out = {}
    for item in merge_items(items):
        out[item["kind"]] = out.get(item["kind"], 0) + 1
    return {kind: out[kind] for kind in KINDS if out.get(kind)}


def count_text(by_kind: dict):
    """件數那一串（總表「狀態」欄、頁首「另有」行共用）：「尚未設定 2 項　⛔ 取數失敗 1 項　◇ 資料未備 1 項」。
    尚未設定不加符號。一項都沒有 → None（呼叫端改寫資料截至日，不寫「正常」）。"""
    parts = []
    for kind in KINDS:
        n = by_kind.get(kind)
        if n:
            symbol = COUNT_SYMBOLS[kind]
            parts.append(((symbol + " ") if symbol else "") + TEXT_COUNT.format(kind=kind, n=n))
    return "　".join(parts) or None


# ───────────────────────── 主要原因（新設計 A） ─────────────────────────


def _rank(item: dict, only_compare_unconfigured: bool):
    if item["kind"] == KIND_UNCONFIGURED:
        if blocks_main(item):
            return 2
        return 6 if only_compare_unconfigured else None
    return {KIND_FETCH: 3, KIND_MISSING: 4, KIND_STALE: 5}[item["kind"]]


def pick_main(items):
    """依新設計 A 的順位與同順位比法挑出唯一一項；沒有主要原因 → None。順位 6 那一種另由 `main_reason` 處理（它可能不只一項）。"""
    merged = merge_items(items)
    only_compare = bool(merged) and all(i["kind"] == KIND_UNCONFIGURED and not blocks_main(i) for i in merged)
    ranked = [(r, i) for i in merged if (r := _rank(i, only_compare)) is not None and r != 6]
    if not ranked:
        return None
    return min(ranked, key=lambda pair: (pair[0], -len(main_unreadable_cards(pair[1])), not pair[1]["lamp"],
                                         pair[1]["order"]))[1]


def main_reason(items, *, page_failure=None):
    """主要原因那一句（總表「主要原因」欄；3-C 頁首主要原因一行呼叫同一個函式）。沒有主要原因 → None。

    `page_failure`：整頁載不出來時那一類資料（例「淨值」；不知道是哪一類就寫「資料」，同 `plain.DATA_CLASS_DEFAULT`）——
    順位 1，其他項目一律不看。"""
    if page_failure is not None:
        return TEXT_MAIN_PAGE_FAILED.format(cls=page_failure)
    merged = merge_items(items)
    if merged and all(i["kind"] == KIND_UNCONFIGURED and not blocks_main(i) for i in merged):
        keys = sorted(merged, key=lambda i: i["order"])
        return TEXT_MAIN_COMPARE_ONLY.format(keys="、".join(i["key"] for i in keys))
    item = pick_main(merged)
    if item is None:
        return None
    n = len(main_unreadable_cards(item))
    tail = TEXT_CARDS_UNREADABLE.format(n=n) if n else ""
    if item["kind"] == KIND_UNCONFIGURED:
        return TEXT_MAIN_UNCONFIGURED.format(key=item["key"]) + tail
    if item["kind"] == KIND_FETCH:
        if item["retreat"]:
            return TEXT_MAIN_RETREAT.format(key=item["key"], day=item["retreat"]["day"],
                                            codes="、".join(item["retreat"]["codes"]))
        return TEXT_MAIN_FETCH.format(key=item["key"]) + tail
    if item["kind"] == KIND_MISSING:
        return TEXT_MAIN_MISSING.format(key=item["key"]) + tail
    return TEXT_MAIN_STALE


def other_counts(items, *, page_failure=None) -> dict:
    """頁首「另有」行的件數：全部項數扣掉主要原因那一項（線框 1.1）。順位 6（只影響比較值）時主要原因那一句已點名全部，回空。"""
    merged = merge_items(items)
    if page_failure is not None:
        return counts(merged)
    if merged and all(i["kind"] == KIND_UNCONFIGURED and not blocks_main(i) for i in merged):
        return {}
    main = pick_main(merged)
    skip = None if main is None else (main["kind"], main["key"])
    return counts([i for i in merged if (i["kind"], i["key"]) != skip])


# ───────────────────────── 跨頁記錄與總表 ─────────────────────────


def _stamp(now) -> str:
    if isinstance(now, datetime):
        if now.tzinfo is None:
            raise ValueError("記錄時間要帶時區（不猜）")
        return now.astimezone(timezone.utc).isoformat(timespec="seconds")
    return str(now)


def record(session_state, slug: str, items, *, as_of, now, page_failure=None) -> None:
    """記下這一頁這一次渲染的資料狀態（**整格覆寫**）。`now`：記錄時間（帶時區的 `datetime` 或 ISO 字串），由呼叫端給。"""
    if slug not in PAGE_NAMES:
        raise ValueError(f"不認得的頁：{slug}")
    store = dict(session_state.get(STATE_KEY) or {})
    store[slug] = {"at": _stamp(now), "items": merge_items(items), "as_of": as_of, "page_failure": page_failure}
    session_state[STATE_KEY] = store


def recorded_time_text(stamp) -> str:
    """記錄時間 →「時:分」台北時間（線框 6.3「記錄於 ‹時:分›」）。讀不懂 → 原樣（不猜）。"""
    try:
        when = datetime.fromisoformat(str(stamp))
    except ValueError:
        return str(stamp)
    if when.tzinfo is None:
        return str(stamp)
    return when.astimezone(TAIPEI).strftime("%H:%M")


def _band(entry) -> int:
    """總表排序（線框 6.3）：有尚未設定或 ⛔ → 只有 ◇ → 只有 ◷ → 沒有異常 → 本次尚未開過。"""
    if entry is None:
        return 4
    if entry.get("page_failure") is not None:
        return 0
    by_kind = counts(entry["items"])
    if by_kind.get(KIND_UNCONFIGURED) or by_kind.get(KIND_FETCH):
        return 0
    if by_kind.get(KIND_MISSING):
        return 1
    if by_kind.get(KIND_STALE):
        return 2
    return 3


def summary_rows(store) -> list:
    """總表第一層：一頁一列，依線框 6.3 排序（同級依固定頁序）。每列 `{"slug", "page", "status", "main", "at"}`；
    沒開過的頁「狀態」「主要原因」寫「—」與「本次尚未開過這一頁」，不給符號（沒評估不等於正常）。"""
    store = store or {}
    rows = []
    for index, slug in enumerate(PAGE_ORDER):
        entry = store.get(slug)
        if entry is None:
            rows.append(((4, index), {"slug": slug, "page": PAGE_NAMES[slug], "status": NO_VALUE,
                                      "main": TEXT_NOT_OPENED, "at": NO_VALUE}))
            continue
        by_kind = counts(entry["items"])
        if entry.get("page_failure") is not None:
            by_kind = dict(by_kind)
            by_kind[KIND_FETCH] = by_kind.get(KIND_FETCH, 0) + (0 if any(
                i["kind"] == KIND_FETCH and i["key"] == entry["page_failure"] for i in entry["items"]) else 1)
        status = count_text(by_kind) or f"{AS_OF_LABEL} {entry.get('as_of') or AS_OF_UNKNOWN}"
        main = main_reason(entry["items"], page_failure=entry.get("page_failure")) or NO_VALUE
        rows.append(((_band(entry), index), {"slug": slug, "page": PAGE_NAMES[slug], "status": status, "main": main,
                                             "at": recorded_time_text(entry["at"])}))
    return [row for _key, row in sorted(rows, key=lambda pair: pair[0])]


def _status_cell(item: dict) -> str:
    if item["kind"] == KIND_UNCONFIGURED:
        return f"{SYMBOL_ERROR} {KIND_UNCONFIGURED}：{item['key']}"
    if item["kind"] == KIND_FETCH:
        return f"{SYMBOL_ERROR} {KIND_FETCH}"
    if item["kind"] == KIND_MISSING:
        return f"{SYMBOL_MISSING} {KIND_MISSING}"
    return f"{SYMBOL_STALE} {KIND_STALE}"


def _cell(value) -> str:
    return NO_VALUE if value is None or value == "" else str(value)


def detail_rows(entry, normal=()) -> list:
    """「看哪一頁的明細」那一張表（總管裁定 (b)）：一列＝「一項 × 受影響的卡或項目」；沒有異常的項目（`normal`，`affected()` 的清單）
    也列，狀態欄寫「—」（不寫「正常」）。欄序 `DETAIL_LABELS`。沒開過的頁 → 空清單。"""
    if entry is None:
        return []
    out = []
    flagged = set()
    for item in entry["items"]:
        for e in item["affected"]:
            flagged.add((e["card"], e["item"]))
            out.append((_cell(e["data_class"]), _join(e), _status_cell(item), _cell(e["obs"]), _cell(e["fetched"]),
                        _cell(e["delay"]), _cell(e["tier"])))
    for e in normal or ():
        if (e["card"], e["item"]) in flagged:
            continue
        out.append((_cell(e["data_class"]), _join(e), NO_VALUE, _cell(e["obs"]), _cell(e["fetched"]),
                    _cell(e["delay"]), _cell(e["tier"])))
    return out


def _join(entry) -> str:
    return "　".join(part for part in (entry["card"], entry["item"]) if part) or NO_VALUE
