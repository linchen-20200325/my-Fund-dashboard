# -*- coding: utf-8 -*-
"""持倉體檢純邏輯。零 streamlit import、零舊 repo import、零網路。

所有判定住在這裡；page.py 只負責把 build_page_model() 產出的模型畫出來。
理由：streamlit 在本環境要靠 scratchpad 才匯入得到，邏輯綁進 streamlit 會讓測試跑不起來。

模型慣例：底線開頭的鍵是**機器用**（狀態、色調、層號…），不開頭底線的鍵是**畫面文字**。

⚠️ 本檔逐處標了「登記」的地方，是 `44` 沒有寫、而不決定就畫不出來的。
   一律照最保守的畫法做，**不自行發明規格、不補 SSOT 缺口**，逐筆列進回報。
"""

from __future__ import annotations

import math
from datetime import date

# 「這個參數沒有被傳」與「這個參數被傳成 None」是兩件事。
_UNSET = object()

# ───────────────────────── 常數（逐字引 `44`） ─────────────────────────

# `44` 5.1 卡片四狀態。本輪已改為逐主值判定，不掛在整張卡。
STATE_OK = "ok"
STATE_MISSING = "資料未備"
STATE_BIZ = "業務例外"
STATE_ERROR = "系統錯誤"

# `44` 5.2 徽章：`狀態` 那一列的七個字面值（封閉列舉）。
STATUS_BADGE_LITERALS = (
    "資料未備",
    "不適用",
    "取數失敗",
    "推估",
    "修正過",
    "部分缺",
    "未定義",
)

# `44` 5.3 按鈕：八類，八類之外沒有第九類。
BUTTON_KINDS = ("取數", "套用", "展開", "匯出", "新增列", "清除", "導覽", "存檔")

# `44` 5.3 禁止欄：這四張表由 Sheets 維護，本儀表板唯讀，沒有任何一類按鈕寫入它們。
READONLY_TABLES = ("holding", "policy", "nav", "dividend")

# 各類按鈕的寫入對象。
# ⚠️ 登記：`44` 寫「`取數` 類只寫取數回來的列與 `fetch_log`」，
#    但本頁缺的四張表**都在唯讀清單裡**，於是這一頁的 `取數` 沒有表可寫。
#    那正是草稿登記的 ⛔ H-05（「這一頁缺的是 Sheets 維護的表，這枚重新取數按了沒事」）。
#    本檔照最保守的一邊做：**只寫 `fetch_log`**，不自行擴權去寫那四張表。
_BUTTON_WRITES = {
    "取數": frozenset({"fetch_log"}),
    "套用": frozenset(),
    "展開": frozenset(),
    "匯出": frozenset(),
    "新增列": frozenset(),
    "清除": frozenset(),
    "導覽": frozenset(),
    "存檔": frozenset({"user_setting"}),
}
SAVE_WRITES = set(_BUTTON_WRITES["存檔"])

# `44` HLD-4 二次擴寫：「套用」重算本頁每一個以那三組欄位取值的塊。
APPLY_RECALC_BLOCKS = ("HLD-1", "HLD-2", "HLD-3", "HLD-5", "HLD-7", "HLD-8")

# `44` 1.2 呈現層禁令：禁方向詞。
FORBIDDEN_DIRECTION_WORDS = (
    "買進",
    "賣出",
    "加碼",
    "減碼",
    "調升",
    "調降",
    "汰弱留強",
    "逢低",
    "停利",
    "停損",
)
# `44` 1.2：禁箭頭。
FORBIDDEN_ARROWS = ("↑", "↓", "▲", "▼")
# `44` 1.1 節判準：按鈕標籤四個禁詞。
FORBIDDEN_BUTTON_WORDS = ("一鍵", "最佳", "推薦", "最適")

# 判「同一張卡有沒有把兩種幣別合成一個數」用的幣別字面值。
KNOWN_CURRENCIES = ("USD", "EUR", "TWD", "JPY", "GBP")

_TONE_BY_STATE = {
    STATE_OK: "中性",
    STATE_MISSING: "灰",
    STATE_BIZ: "黃",
    STATE_ERROR: "紅",
}
_SEVERITY = {STATE_OK: 0, STATE_MISSING: 1, STATE_BIZ: 2, STATE_ERROR: 3}

# 塊名逐字引 `44` 3.2 的層次表與各塊標題。
BLOCK_TITLES = {
    "HLD-0": "體檢結論燈",
    "HLD-1": "偏離提示卡",
    "HLD-2": "績效與風險卡",
    "HLD-3": "配息與本金卡",
    "HLD-4": "檢視區間與門檻輸入",
    "HLD-5": "單檔展開",
    "HLD-6": "淨值與配息序列",
    "HLD-7": "計算軌跡",
    "HLD-8": "最大回撤與本金類配息佔比",
}
BLOCK_LAYERS = {
    "HLD-0": 1,
    "HLD-1": 2,
    "HLD-2": 2,
    "HLD-3": 2,
    "HLD-4": 3,
    "HLD-5": 3,
    "HLD-6": 4,
    "HLD-7": 4,
    "HLD-8": 4,
}

# 「回答什麼」逐字引 `44` 3.2 各塊那一格（HLD-2／HLD-3／HLD-7 取 2026-09-22 改寫後的句子）。
ANSWERS = {
    "HLD-0": "這個月我需不需要打開這一頁細看",
    "HLD-1": "哪幾檔現在超出了我自己寫下的那條線，超出多少",
    "HLD-2": "我這幾檔在同一段期間裡，各自走了多少、抖了多大",
    "HLD-3": "我在這段區間裡逐檔收到多少配息，這些配息相當於淨值的多少",
    "HLD-4": "我現在是用哪一段期間、哪幾條線在檢查",
    "HLD-5": "這一檔單獨看，淨值和配息是怎麼交錯的",
    "HLD-6": "本頁那四塊用到的原始數字，逐筆是什麼",
    "HLD-7": "本頁那四塊上的每一個數字，是拿哪幾筆、怎麼算出來的",
    "HLD-8": "那兩個從核心卡移下來的值，逐檔是多少",
}

PAGE_TITLE = "持倉體檢"
PAGE_ANSWERS = "我手上這些基金，哪幾檔偏離了我自己設的門檻"

# `44` 4.5：時間一律以世界協調時間存放。
STORAGE_TIMEZONE = "UTC"

# `44` HLD-2 規則欄逐字：年化基數為交易日 252（欄位語意 `days_trading`）。
TRADING_DAYS_PER_YEAR = 252

# 每一個數字後面帶的字。草稿逐字要求：「螢幕上每一個數字後面都帶（示意）」。
# 理由寫在草稿 §A：填一個看起來合理的數字、客戶會把它讀成真的，那是線框最容易犯的一種造假。
HINT = "（示意）"

# 指標名 → 它住在哪一塊（`44` HLD-7 規則欄：輸出值與該列指標名所在那一塊上顯示的值逐字相同）。
INDICATOR_OWNER = {
    "區間報酬率": "HLD-2",
    "期間波動": "HLD-2",
    "期間配息合計": "HLD-3",
    "配息佔淨值比": "HLD-3",
    "最大回撤": "HLD-8",
    "本金類配息佔比": "HLD-8",
}

# `44` :583（第七輪）：門檻的指標名取 `HLD-1`／`HLD-2`／`HLD-3`／`HLD-8` 四塊各自出的指標。
# ⚠️ `HLD-1` 不另外貢獻名字 —— 它出的是「<指標名> 與門檻的差額」，由門檻自己導出來，會繞回自己。
#    **不替 `44` 發明第七個名字**（登記，不是動工授權）。
RULE_INDICATOR_NAMES = tuple(INDICATOR_OWNER)

# ⚠️ 0 caller。依 `44` §6「**不刪，只標**」保留（上一輪誤刪，本輪復原）。
#    它的四項與現行母體六項**對不上** —— ⛔ 不要拿它當母體用。**登記待裁。**
_RULE_INDICATORS = ("最大回撤", "配息佔淨值比", "區間報酬率", "期間波動")

# 算式的文字寫法（`44` HLD-7：算式以文字寫出，不寫任何實作語言的語法）。
FORMULA_TEXT = {
    "區間報酬率": "區間末單位淨值 ÷ 區間首單位淨值，再減一",
    "期間波動": "日報酬標準差 × 年化基數 252 的平方根",
    "最大回撤": "區間內每一日的單位淨值除以它之前的最高單位淨值，取最小值後減一",
    "期間配息合計": "區間內各筆每單位配息 × 持有單位數，加總",
    "配息佔淨值比": "區間內各筆每單位配息加總，除以區間末單位淨值",
    "本金類配息佔比": "本金類配息金額，除以期間配息合計",
}
_DEVIATION_FORMULA = "該檔的實際值減門檻值"


# ───────────────────────── 格式 ─────────────────────────


def format_pct(value: float, *, signed: bool = False) -> str:
    """百分點，小數 2 位（`44` HLD-2 規則欄逐字）。"""
    return f"{value:+.2f}%" if signed else f"{value:.2f}%"


def format_amount(value: float, ccy: str) -> str:
    """原幣金額。逐檔寫出該檔 `ccy` 的字面值（客戶 2026-09-22 設計引導第三條）。"""
    return f"{value:,.2f} {ccy}"


def format_signed_pp(value: float) -> str:
    """`44` 1.2：期間變化以正負號與數字寫出，不配箭頭。"""
    return f"{value:+.2f} pp"


def hinted(text: str) -> str:
    return text + HINT


def tone_for_state(state: str) -> str:
    """四狀態 → 顏色語意。`44` 5.1 卡片那張表。回傳語意字串，不回色碼。"""
    return _TONE_BY_STATE[state]


def worst_state(states) -> str:
    if not states:
        return STATE_MISSING
    return max(states, key=lambda s: _SEVERITY[s])


# ───────────────────────── 斷點 ─────────────────────────


def columns_for_width(width_px: int) -> int:
    """`44` 2.1 客戶最終版：≤768 單欄／769-1279 兩欄／≥1280 三欄。"""
    if width_px <= 768:
        return 1
    if width_px <= 1279:
        return 2
    return 3


def layer_columns(layer: int, width_px: int) -> int:
    """各層在該寬度下同一列並排幾塊。`44` 2.1 那張四段表。"""
    if layer in (1, 4):
        return 1  # 單欄滿寬，逐塊上下堆疊
    if layer == 2:
        return columns_for_width(width_px)
    # 層 3：`44` 逐字「五頁的層 3 各只有兩塊，兩塊並排同一列，第三欄空著」。
    return min(2, columns_for_width(width_px))


# ───────────────────────── 文案模板（逐字引 `44` 5.5） ─────────────────────────


def empty_source_text(source_keys) -> str:
    return "⬜ 資料未備：" + " 與 ".join(source_keys) + " 尚無資料"


def not_applicable_text(reason: str) -> str:
    return "⬜ 不適用：" + reason


def fetch_failed_text(message: str) -> str:
    """訊息原文照印 —— 不改寫成安撫語句，也不截斷。"""
    return "⚠ 取數失敗：" + message


def partial_range_text(start: str, end: str) -> str:
    return f"缺 {start} 至 {end}"


TEXT_NO_HOLDING = "尚未建立任何持倉"
TEXT_NO_RULES = "尚未設定門檻"
TEXT_NO_DEVIATION = "無偏離項"
TEXT_SHEETS_READONLY = "持倉資料在 Sheets 維護，本儀表板唯讀"
TEXT_GOTO_SHEETS = "前往 Sheets 維護持倉"
TEXT_BAD_RANGE = "起日不晚於迄日"
TEXT_BOTH_EMPTY = "區間兩個欄位皆未填"
TEXT_DIRECT_HOLD = "直接持有"

NA_NO_WINDOW = not_applicable_text("尚未設定區間")
NA_NO_RULES = not_applicable_text(TEXT_NO_RULES)
# ⚠️ 下列四個 0 caller，依 `44` §6「不刪，只標」保留：字面值與 `fund_metrics` 裡
#    `not_applicable_text(...)` 是同一句話的第二份來源。**登記待裁。**
#    （`NA_NO_WINDOW`／`NA_NO_RULES` 是 live 的，不在此列。）
NA_FEW_NAV = not_applicable_text("區間內淨值筆數不足")
NA_LATE_INCEPTION = not_applicable_text("成立日晚於區間起點")
NA_NO_DIVIDEND = not_applicable_text("區間內無配息")
NA_UNKNOWN_KIND = not_applicable_text("配息類別未知")
ND_TEXT = "⬜ 資料未備"
ERR_TEXT = "⚠ 取數失敗"


# ───────────────────────── 算式（純數學） ─────────────────────────


def return_pct(navs) -> float | None:
    """區間報酬率：以區間首末兩筆計算，單位百分點。"""
    if not navs or len(navs) < 2:
        return None
    first = navs[0]
    if math.isclose(first, 0.0, abs_tol=1e-12):
        return None
    return (navs[-1] / first - 1.0) * 100.0


def drawdown_pct(navs) -> float | None:
    """最大回撤：逐日除以之前的最高值，取最小值後減一。"""
    if not navs or len(navs) < 2:
        return None
    peak = navs[0]
    worst = 0.0
    for value in navs:
        peak = max(peak, value)
        if math.isclose(peak, 0.0, abs_tol=1e-12):
            return None
        worst = min(worst, value / peak - 1.0)
    return worst * 100.0


def vol_pct(navs) -> float | None:
    """期間波動：日報酬標準差年化，年化基數為交易日 252。"""
    if not navs or len(navs) < 2:
        return None
    rets = []
    for previous, current in zip(navs, navs[1:]):
        if math.isclose(previous, 0.0, abs_tol=1e-12):
            return None
        rets.append(current / previous - 1.0)
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    variance = sum((r - mean) ** 2 for r in rets) / len(rets)
    return math.sqrt(variance) * math.sqrt(TRADING_DAYS_PER_YEAR) * 100.0


# ───────────────────────── 取數與切片 ─────────────────────────


def _rows_for(dataset, table, fund_code):
    return [row for row in dataset.get(table, []) if row["fund_code"] == fund_code]


def _in_window(rows, key, window):
    start, end = window
    if not start or not end:
        return []
    return sorted(
        (row for row in rows if start <= row[key] <= end), key=lambda row: row[key]
    )


def _setting(dataset, key):
    for row in dataset.get("user_setting", []):
        if row["setting_key"] == key:
            return row["setting_value"]
    return None


def saved_window(dataset):
    return (_setting(dataset, "hld_window_start"), _setting(dataset, "hld_window_end"))


def saved_rules(dataset):
    return list(_setting(dataset, "hld_deviation_rules") or ())


def window_is_valid(window) -> bool:
    start, end = window
    if not start or not end:
        return False
    try:
        return date.fromisoformat(start) <= date.fromisoformat(end)
    except ValueError:
        return False


# ───────────────────────── 逐檔指標 ─────────────────────────


def main_value_state(*, error=None, missing=False, na_reason=None) -> str:
    """一個主值的四狀態。`44` 5.1：四狀態掛在主值上，不掛在整張卡。

    順序刻意是「失敗 → 缺 → 不適用 → ok」：取數失敗比缺資料更該說出來（§1 Fail Loud）。
    """
    if error:
        return STATE_ERROR
    if missing:
        return STATE_MISSING
    if na_reason:
        return STATE_BIZ
    return STATE_OK


def _metric(value, *, text, ccy, error=None, missing=False, na_reason=None, label=""):
    state = main_value_state(error=error, missing=missing, na_reason=na_reason)
    if state == STATE_OK:
        shown = text
    elif state == STATE_MISSING:
        shown = ND_TEXT
    elif state == STATE_BIZ:
        shown = na_reason
    else:
        shown = ERR_TEXT
    return {
        "_value_node": True,
        "_state": state,
        "_tone": tone_for_state(state),
        "_has_number": state == STATE_OK,
        "_ccy": ccy,
        "_raw": value if state == STATE_OK else None,
        "label": label,
        "text": shown,
        "value_text": shown,
        "reason_text": (error or "") if state == STATE_ERROR else "",
    }


def fund_metrics(dataset, fund, window):
    """一檔在一段區間內的六個指標。**所有卡與所有表都讀這一份**，
    這樣 `44` HLD-7 判準要的「軌跡與所在那一塊逐字相同」才是由構造保證的。"""
    code = fund["fund_code"]
    ccy = fund["ccy"]
    errors = dataset.get("errors", {})
    nav_error = errors.get("nav")
    div_error = errors.get("dividend")

    profile = next(
        (p for p in dataset.get("fund_profile", []) if p["fund_code"] == code), None
    )
    start, end = window
    has_window = window_is_valid(window)

    nav_rows = _in_window(_rows_for(dataset, "nav", code), "nav_date", window)
    navs = [row["nav_orig_ccy"] for row in nav_rows]
    all_nav_rows = _rows_for(dataset, "nav", code)

    late = bool(
        profile and start and profile.get("inception_on") and profile["inception_on"] > start
    )

    def nav_na():
        if not has_window:
            return "尚未設定區間"
        if late:
            return "成立日晚於區間起點"
        if len(navs) < 2:
            return "區間內淨值筆數不足"
        return None

    nav_missing = bool(has_window and not all_nav_rows)
    na_nav = None if nav_missing else nav_na()
    na_nav_text = not_applicable_text(na_nav) if na_nav else None

    ret = return_pct(navs)
    vol = vol_pct(navs)
    draw = drawdown_pct(navs)

    div_rows = _in_window(_rows_for(dataset, "dividend", code), "ex_date", window)
    per_unit_total = sum(row["div_per_unit_orig_ccy"] for row in div_rows)
    units = fund["units_shares"]
    div_total = per_unit_total * units
    nav_last = navs[-1] if navs else None
    unknown_rows = [row for row in div_rows if row["div_kind"] == "unknown"]
    principal_sum = sum(
        row["div_per_unit_orig_ccy"] for row in div_rows if row["div_kind"] == "principal"
    )

    def div_na():
        if not has_window:
            return "尚未設定區間"
        if not div_rows:
            return "區間內無配息"
        return None

    na_div = div_na()
    na_div_text = not_applicable_text(na_div) if na_div else None

    # 配息佔淨值比：`44` 寫「期間配息除以區間末 `nav_orig_ccy`」。
    # ⚠️ 登記（量綱，`44` 沒有講清楚）：`期間配息合計` 是**金額**，而 `nav_orig_ccy` 是
    #    **每單位淨值**，兩者相除得到的是**單位數**，不是百分點。
    #    唯一能得到百分點的讀法是「**每單位配息加總** ÷ 區間末每單位淨值」——
    #    它與「合計 ÷ 區間末淨值 × 持有單位數」同值。本檔取這一種，**不自行改規格**。
    yield_na = na_div
    if yield_na is None and nav_last is None:
        yield_value = None
    else:
        yield_value = (per_unit_total / nav_last * 100.0) if nav_last else None

    principal_na = na_div
    if principal_na is None and unknown_rows:
        principal_na = "配息類別未知"
    principal_value = (
        (principal_sum / per_unit_total * 100.0)
        if per_unit_total and not principal_na
        else None
    )

    return {
        "_fund_code": code,
        "_ccy": ccy,
        "fund_name": fund["fund_name"],
        "units_shares": units,
        "nav_rows": nav_rows,
        "div_rows": div_rows,
        "unknown_count": len(unknown_rows),
        "nav_missing": nav_missing,
        "區間報酬率": _metric(
            ret,
            text=hinted(format_pct(ret, signed=True)) if ret is not None else "",
            ccy=ccy,
            error=nav_error,
            missing=nav_missing,
            na_reason=na_nav_text,
            label="區間報酬率",
        ),
        "期間波動": _metric(
            vol,
            text=hinted(format_pct(vol)) if vol is not None else "",
            ccy=ccy,
            error=nav_error,
            missing=nav_missing,
            na_reason=na_nav_text,
            label="期間波動",
        ),
        "最大回撤": _metric(
            draw,
            text=hinted(format_pct(draw)) if draw is not None else "",
            ccy=ccy,
            error=nav_error,
            missing=nav_missing,
            na_reason=na_nav_text,
            label="最大回撤",
        ),
        "期間配息合計": _metric(
            div_total,
            text=hinted(format_amount(div_total, ccy)),
            ccy=ccy,
            error=div_error,
            missing=False,
            na_reason=na_div_text,
            label="期間配息合計",
        ),
        "配息佔淨值比": _metric(
            yield_value,
            text=hinted(format_pct(yield_value)) if yield_value is not None else "",
            ccy=ccy,
            error=div_error,
            missing=bool(nav_missing or (na_div is None and nav_last is None)),
            na_reason=na_div_text,
            label="配息佔淨值比",
        ),
        "本金類配息佔比": _metric(
            principal_value,
            text=hinted(format_pct(principal_value)) if principal_value is not None else "",
            ccy=ccy,
            error=div_error,
            missing=False,
            na_reason=not_applicable_text(principal_na) if principal_na else None,
            label="本金類配息佔比",
        ),
    }


def all_metrics(dataset, window):
    funds = sorted(dataset.get("holding", []), key=lambda h: h["fund_code"])
    return [fund_metrics(dataset, fund, window) for fund in funds]


# ───────────────────────── 徽章與按鈕 ─────────────────────────


def status_badge(text: str) -> dict:
    if text not in STATUS_BADGE_LITERALS:
        raise ValueError(f"狀態徽章字面值 {text!r} 不在 `44` 5.2 的七個之內")
    return {"_kind": "狀態", "_tone": "灰" if text == "資料未備" else "黃", "text": text}


def source_badge(tier: str) -> dict:
    """`44` 5.2：來源徽章中性、不著色。"""
    return {"_kind": "來源", "_tone": "中性", "text": tier}


def _redline_badge(mark: str) -> dict:
    """`44` 5.2：紅線徽章只出現在說明區，不出現在任何數值旁。"""
    return {"_kind": "紅線", "_tone": "中性", "_slot": "說明區", "text": mark}


def button_writes(kind: str) -> set:
    return set(_BUTTON_WRITES[kind])


def _button(label, kind, *, enabled=True, disabled_reason="") -> dict:
    if kind not in BUTTON_KINDS:
        raise ValueError(f"按鈕類別 {kind!r} 不在 `44` 5.3 的八類之內")
    for word in FORBIDDEN_BUTTON_WORDS:
        if word in label:
            raise ValueError(f"按鈕標籤 {label!r} 含禁詞 {word!r}（`44` 1.1）")
    return {
        "_action_kind": kind,
        "_writes": button_writes(kind),
        "_enabled": bool(enabled),
        "_visible": True,  # `44` 5.3：按鈕停用時不隱藏
        "label": label,
        "disabled_reason": disabled_reason,
    }


def _retry_button() -> dict:
    return _button("重新取數", "取數")


def blocks_recalculated_by(action_kind: str) -> tuple:
    """`44` HLD-4：「套用」重算六塊；「存檔」不重算任何一塊。"""
    return APPLY_RECALC_BLOCKS if action_kind == "套用" else ()


# ───────────────────────── HLD-1 偏離提示卡 ─────────────────────────


def _breaches(rule, value) -> bool:
    if rule["direction"] == "低於":
        return value < rule["value"]
    if rule["direction"] == "高於":
        return value > rule["value"]
    return False


def deviation_rows(metrics, rules):
    """逐檔算出門檻所指的值，只列出超出門檻的檔。

    回傳 (列, 未列入的原因統計)。缺淨值的檔**不進本表、不佔一列、不計入列數**
    （客戶 `H-01` 裁示；`44` HLD-1 空狀態 2026-09-22 改寫）。
    """
    rows = []
    skipped = {"missing": set(), "error": set(), "na": set()}
    for metric in metrics:
        for rule in rules:
            name = rule["indicator"]
            if name not in RULE_INDICATOR_NAMES:
                # `44` :583 自第七輪起給了母體，草稿 ⛔ H-12「沒有候選清單」已為假、已撤。
                # 母體之外的名字仍然**不猜**，照舊登記成一種未列入。
                skipped["na"].add(metric["_fund_code"])
                continue
            node = metric[name]
            if node["_state"] == STATE_ERROR:
                skipped["error"].add(metric["_fund_code"])
                continue
            if node["_state"] == STATE_MISSING:
                skipped["missing"].add(metric["_fund_code"])
                continue
            if node["_state"] == STATE_BIZ:
                skipped["na"].add(metric["_fund_code"])
                continue
            if not _breaches(rule, node["_raw"]):
                continue
            delta = node["_raw"] - rule["value"]
            rows.append(
                {
                    "_fund_code": metric["_fund_code"],
                    "_indicator": name,
                    # 軌跡上的指標名刻意與 HLD-8 的「最大回撤」分開 ——
                    # 門檻可以拿任何一個指標來比，同名會讓 `44` HLD-7 那一行判準
                    # 分不出「這一列的值該去哪一塊對」。
                    "trace_indicator": f"{name} 與門檻的差額",
                    "_ccy": metric["_ccy"],
                    "_value_node": True,
                    "_state": STATE_OK,
                    "_tone": "中性",
                    "_has_number": True,
                    "fund_name": metric["fund_name"],
                    "actual_text": node["text"],
                    "threshold_text": hinted(format_pct(rule["value"])),
                    "delta_text": hinted(format_signed_pp(delta)),
                    "text": hinted(format_signed_pp(delta)),
                }
            )
    rows.sort(key=lambda row: (row["_fund_code"], row["_indicator"]))
    return rows, skipped


def _build_hld1(metrics, rules, *, has_holdings):
    badges = [_redline_badge("G2†")]
    buttons = []
    detail_lines = ["依 fund_code 字面值排列，不排序成優先順序。"]
    tail_lines = []

    if not has_holdings:
        rows, skipped = [], {"missing": set(), "error": set(), "na": set()}
        state = STATE_MISSING
        summary = TEXT_NO_HOLDING
        detail_lines = [empty_source_text(["holding"]), TEXT_NO_HOLDING]
        buttons.append(_retry_button())
        placeholder = _metric(None, text="", ccy="", missing=True, label="偏離筆數")
    elif not rules:
        rows, skipped = [], {"missing": set(), "error": set(), "na": set()}
        state = STATE_BIZ
        summary = TEXT_NO_RULES
        detail_lines = ["不以任何內建值代替。"]
        placeholder = _metric(
            None, text="", ccy="", na_reason=NA_NO_RULES, label="偏離筆數"
        )
    else:
        rows, skipped = deviation_rows(metrics, rules)
        state = STATE_OK
        placeholder = None
        summary = f"{len(rows)} 列（示意）" if rows else TEXT_NO_DEVIATION
        if not rows:
            # ⚠️ 登記：零列長什麼樣 `44` 沒有寫（草稿 ⛔ H-06：零筆偏離不屬空狀態四種）。
            #    本檔照草稿的畫法：一句「無偏離項」，不掛任何空狀態徽章。
            detail_lines.append("目前這一組門檻下，沒有任何一檔超出。")
        if skipped["missing"]:
            tail_lines.append(
                f"⬜ 另有 {len(skipped['missing'])} 檔缺淨值，未列入{HINT}"
            )
            tail_lines.append(
                "未列入的檔不進上表、也不進偏離筆數；燈上的 N 與本卡列數因此相等。"
            )
            buttons.append(_retry_button())
        if skipped["error"]:
            tail_lines.append(
                f"⚠ 另有 {len(skipped['error'])} 檔的門檻指標取數失敗，未列入{HINT}"
            )
            buttons.append(_retry_button())
        if skipped["na"]:
            tail_lines.append(
                f"⬜ 另有 {len(skipped['na'])} 檔的門檻指標不適用，未列入{HINT}"
            )

    return {
        "code": "HLD-1",
        "title": BLOCK_TITLES["HLD-1"],
        "_layer": 2,
        "_default_open": True,
        "_state": state,
        "_tone": tone_for_state(state),
        "_rows": rows,
        "_placeholder": placeholder,
        "missing_nav_count": len(skipped["missing"]),
        "column_labels": ["基金名", "實際值", "門檻值", "差額"],
        "answers": ANSWERS["HLD-1"],
        "summary_text": summary,
        "detail_lines": detail_lines,
        "tail_lines": tail_lines,
        "badges": badges,
        "buttons": buttons,
        "redline_note": "偏離提示只客觀描述現況與目標差距，不提供任何處置方向。",
    }


# ───────────────────────── HLD-2 / HLD-3 核心卡 ─────────────────────────


def _build_core_card(code, metrics, labels, *, has_holdings, has_window, subtitle, moved_note):
    groups = []
    for metric in metrics:
        values = [metric[label] for label in labels]
        groups.append(
            {
                "_fund_code": metric["_fund_code"],
                "_ccy": metric["_ccy"],
                "head_text": f"{metric['fund_name']} · 幣別 {metric['_ccy']}{HINT}",
                "main_values": values,
            }
        )

    states = [mv["_state"] for group in groups for mv in group["main_values"]]
    badges = []
    detail_lines = [subtitle]
    buttons = []

    if not has_holdings:
        state = STATE_MISSING
        detail_lines = [NA_NO_WINDOW if not has_window else subtitle, ND_TEXT, TEXT_NO_HOLDING]
        buttons.append(_retry_button())
        summary = TEXT_NO_HOLDING
    else:
        state = worst_state(states)
        if not has_window:
            detail_lines.insert(0, NA_NO_WINDOW)
        # `44` 5.1：一組主值為 ok 而另一組不是時，標題掛「部分缺」徽章。
        for group in groups:
            group_states = [mv["_state"] for mv in group["main_values"]]
            if STATE_OK in group_states and any(s != STATE_OK for s in group_states):
                badges.append(status_badge("部分缺"))
                break
        if any(s in (STATE_MISSING, STATE_ERROR) for s in states):
            buttons.append(_retry_button())
        summary = f"{len(groups)} 檔{HINT}"

    if moved_note:
        detail_lines.append(moved_note)

    error_lines = []
    for group in groups:
        for mv in group["main_values"]:
            if mv["_state"] == STATE_ERROR and mv["reason_text"]:
                line = fetch_failed_text(mv["reason_text"])
                if line not in error_lines:
                    error_lines.append(line)
                    error_lines.append("訊息原文照印，不改寫成安撫語句。")

    return {
        "code": code,
        "title": BLOCK_TITLES[code],
        "_layer": 2,
        "_default_open": True,
        "_state": state,
        "_tone": tone_for_state(state),
        "fund_groups": groups,
        "answers": ANSWERS[code],
        "summary_text": summary,
        "detail_lines": detail_lines + error_lines,
        "badges": badges,
        "buttons": buttons,
    }


# ───────────────────────── HLD-0 結論燈 ─────────────────────────

_LAMP_LOOK = {
    "灰": ("⬜", "狀態：中性"),
    "黃": ("⚠", "狀態：要多看一眼"),
    "紅": ("✖", "狀態：取數失敗"),
}


def conclusion_light(cards, *, has_holdings, has_rules, deviation_count):
    """`44` HLD-0 規則與空狀態逐字。本塊不自取數，只讀三塊已經算出來的值。"""
    states = [card["_state"] for card in cards]
    lines = []

    if not has_holdings:
        # ⚠️ 登記：持倉為空與門檻未設兩句同時成立時哪一句出現，`44` 沒有寫（草稿 ⛔ H-17）。
        #    本檔照草稿：取持倉那一句，另一句補在下面括號裡。
        if not has_rules:
            lines.append("（另：尚未設定門檻。兩句同時成立時哪一句出現，規格沒有寫）")
        return {
            "_tone": "灰",
            "_state": STATE_MISSING,
            "text": TEXT_NO_HOLDING,
            "lines": lines,
            "detail_lines": [TEXT_SHEETS_READONLY],
            "buttons": [_button(TEXT_GOTO_SHEETS, "導覽")],
        }

    if not has_rules:
        return {
            "_tone": "灰",
            "_state": STATE_BIZ,
            "text": TEXT_NO_RULES,
            "lines": ["門檻由你自己輸入，這一頁不提任何候選值。"],
            "detail_lines": [],
            "buttons": [],
        }

    if STATE_ERROR in states:
        # ⚠️ 登記：紅燈的文案字面 `44` 沒有給（草稿 ⛔ H-16）。本句取自草稿。
        named = [c["title"] for c in cards if c["_state"] == STATE_ERROR]
        return {
            "_tone": "紅",
            "_state": STATE_ERROR,
            "text": "有一塊取數失敗，這一頁的數字先不要照著讀",
            "lines": [f"{'、'.join(named)}：取數失敗。"],
            "detail_lines": [
                "紅燈說的是「這一頁的數字能不能照著讀」，不是「你的持倉出事了」。"
            ],
            "buttons": [],
        }

    if deviation_count > 0:
        return {
            "_tone": "黃",
            "_state": STATE_OK,
            "text": f"有 {deviation_count} 檔超出你設定的門檻{HINT}",
            "lines": ["哪幾檔分別超出的是哪一條線，看下面的偏離提示卡。"],
            "detail_lines": ["黃燈說的是「要不要多看一眼」，不是「該調整了」。"],
            "buttons": [],
        }

    if all(state == STATE_OK for state in states):
        return {
            "_tone": "灰",
            "_state": STATE_OK,
            "text": TEXT_NO_DEVIATION,
            "lines": ["目前這一組門檻下，沒有任何一檔超出。"],
            "detail_lines": [],
            "buttons": [],
        }

    # ⚠️ 登記：三塊不全是 ok、偏離筆數為零、又沒有系統錯誤時，
    #    `44` HLD-0 三條規則**一條也沒命中**（草稿 ⛔ H-03）。
    #    本檔照草稿被迫挑的那一邊：灰燈，文案沿用「無偏離項」。**這不是規格。**
    return {
        "_tone": "灰",
        "_state": worst_state(states),
        "text": TEXT_NO_DEVIATION,
        "lines": ["有一塊進了「不適用」，偏離筆數為零。"],
        "detail_lines": [
            "這一頁的燈色描述的是「要不要多看一眼」，不描述持倉好壞。"
        ],
        "buttons": [],
    }


def _build_hld0(cards, *, has_holdings, has_rules, deviation_count):
    light = conclusion_light(
        cards,
        has_holdings=has_holdings,
        has_rules=has_rules,
        deviation_count=deviation_count,
    )
    glyph, state_word = _LAMP_LOOK[light["_tone"]]
    return {
        "code": "HLD-0",
        "title": BLOCK_TITLES["HLD-0"],
        "_layer": 1,
        "_default_open": True,
        "_state": light["_state"],
        "_tone": light["_tone"],
        "_reads": ("HLD-1", "HLD-2", "HLD-3"),
        "_deviation_count": deviation_count,
        "glyph": glyph,
        "state_word": state_word,
        "text": light["text"],
        "main_values": [],  # `44`：這一塊沒有任何數字
        "answers": ANSWERS["HLD-0"],
        "summary_text": light["text"],
        "lines": light["lines"],
        "detail_lines": light["detail_lines"],
        "badges": [],
        "buttons": light["buttons"],
    }


# ───────────────────────── HLD-4 檢視區間與門檻輸入 ─────────────────────────


def _field(name, label, placeholder, value):
    return {
        "_input": True,
        "_default": None,  # `44` HLD-4：三組欄位皆為使用者輸入，無預設值（G3†）
        "_value": value,
        "name": name,
        "label": label,
        "placeholder": placeholder,
    }


def _build_hld4(*, applied_window, fields, rules):
    field_start = fields.get("window_start")
    field_end = fields.get("window_end")
    both_empty = not field_start and not field_end
    bad_range = bool(
        field_start and field_end and not window_is_valid((field_start, field_end))
    )

    detail_lines = []
    if bad_range:
        detail_lines.append(TEXT_BAD_RANGE)
    if both_empty:
        detail_lines.append(NA_NO_WINDOW)

    inputs = [
        _field("window_start", "區間起日", "請選擇日期（YYYY-MM-DD）", field_start),
        _field("window_end", "區間迄日", "請選擇日期（YYYY-MM-DD）", field_end),
    ]
    threshold_rows = []
    for index, rule in enumerate(rules or [{"indicator": "", "direction": "", "value": ""}]):
        threshold_rows.append(
            [
                _field(f"rule_{index}_indicator", "指標名", "請輸入指標名", rule["indicator"]),
                _field(f"rule_{index}_direction", "比較方向", "請輸入比較方向", rule["direction"]),
                _field(f"rule_{index}_value", "數值", "請輸入數值", rule["value"]),
            ]
        )

    enabled_save = not both_empty and not bad_range
    reason = TEXT_BOTH_EMPTY if both_empty else (TEXT_BAD_RANGE if bad_range else "")
    buttons = [
        _button("新增一列", "新增列"),
        _button("套用", "套用", enabled=not bad_range, disabled_reason=TEXT_BAD_RANGE if bad_range else ""),
        _button("存檔", "存檔", enabled=enabled_save, disabled_reason=reason),
    ]
    row_buttons = [_button("清除這一列", "清除") for _ in threshold_rows]

    if both_empty:
        summary = "尚未設定區間；門檻一列也沒有；存檔停用" if not rules else "尚未設定區間"
    elif bad_range:
        summary = "輸入尚未通過檢查"
    else:
        rule_count = len(rules or ())
        summary = f"區間 {field_start}{HINT} 至 {field_end}{HINT} · 門檻 {rule_count} 列{HINT}"

    return {
        "code": "HLD-4",
        "title": BLOCK_TITLES["HLD-4"],
        "_layer": 3,
        "_default_open": False,
        "_state": STATE_OK,
        "_tone": "中性",
        "_applied": window_is_valid(applied_window),
        "answers": ANSWERS["HLD-4"],
        "summary_text": summary,
        "inputs": inputs,
        "rule_indicator_names": RULE_INDICATOR_NAMES,
        "threshold_caption": "門檻（指標名＋比較方向＋數值，可增減列）",
        "threshold_rows": threshold_rows,
        "row_buttons": row_buttons,
        "detail_lines": detail_lines,
        "badges": [_redline_badge("G3†")],
        "buttons": buttons,
        "notes": [
            "兩枚按鈕並存，各做一件事。「套用」只讀這些欄位的當下值、"
            "重算 HLD-1、HLD-2、HLD-3、HLD-5、HLD-7、HLD-8 六塊，"
            "不寫任何資料表、不改欄位的內容。",
            "「存檔」把當下值寫回使用者設定並更新最後修改時間，不重算任何一塊。"
            "要兩件事都發生就兩枚都按；兩枚的先後不影響結果。",
            "「存檔」只寫使用者設定，不寫持倉、保單、淨值、配息四張表任何一張，"
            "也不代你填任何值、不把空欄補成任何候選值。",
            "欄位一律無預設值：首次開啟四個欄位全是空的。本塊不對門檻數值提出任何候選值。",
        ],
        "redline_note": "所有試算參數均由使用者自行輸入，系統不代填。",
    }


# ───────────────────────── HLD-5 單檔展開 ─────────────────────────


def _build_hld5(dataset, metrics, *, open_fund, has_window):
    policies = {p["policy_id"]: p for p in dataset.get("policy", [])}
    holdings = {h["fund_code"]: h for h in dataset.get("holding", [])}
    items = []
    for index, metric in enumerate(metrics):
        holding = holdings[metric["_fund_code"]]
        policy = policies.get(holding["policy_id"])
        is_direct = holding["policy_id"] == "DIRECT"
        fields = [
            ("保單", TEXT_DIRECT_HOLD if is_direct else (policy or {}).get("policy_name", "⬜")),
            ("發行單位", "—" if is_direct else (policy or {}).get("issuer", "⬜")),
            ("持有起始日", holding["opened_on"] + HINT),
            ("單位數", f"{holding['units_shares']:,.3f}{HINT}"),
            ("成本（原幣）", hinted(format_amount(holding["cost_orig_ccy"], holding["ccy"]))),
            ("成本（新臺幣）", f"{holding['cost_twd']:,} 元{HINT}"),
            ("類別", holding["bucket"] or "⬜"),
            ("最後對帳", holding["last_synced_at"][:10] + HINT),
        ]
        has_nav = bool(metric["nav_rows"])
        items.append(
            {
                "_fund_code": metric["_fund_code"],
                "_ccy": metric["_ccy"],
                # `44` :119／:128／§5.4「展開區不自動展開」—— 上一輪寫 `index == 0`，三處都撞。
                "_open": metric["_fund_code"] == open_fund,
                "_fields": fields,
                "head_text": f"{metric['fund_name']} · {metric['_fund_code']}{HINT}",
                "nav_plot_text": (
                    "〔淨值折線〕與〔配息長條〕共用同一條時間軸"
                    if has_nav
                    # `44` :708 明文回指 §5.5 模板，不是自己寫一句散文。
                    else empty_source_text(["nav"])
                ),
                "div_plot_text": "〔配息長條〕照畫 · 本輪以佔位框代替，不畫真圖",
            }
        )

    if not items:
        state = STATE_MISSING
        summary = TEXT_NO_HOLDING
        detail_lines = [ND_TEXT, "尚未建立任何持倉，沒有可以展開的檔。"]
    else:
        state = STATE_OK
        summary = f"{len(items)} 檔{HINT} · 同時最多展開一檔"
        detail_lines = ["點一檔展開一檔，同時最多展開一檔；展開區不巢狀第二層。"]
        if not has_window:
            detail_lines.insert(0, NA_NO_WINDOW)

    return {
        "code": "HLD-5",
        "title": BLOCK_TITLES["HLD-5"],
        "_layer": 3,
        "_default_open": False,
        "_state": state,
        "_tone": tone_for_state(state),
        "_items": items,
        "_rows": items,
        "answers": ANSWERS["HLD-5"],
        "summary_text": summary,
        "detail_lines": detail_lines,
        "badges": [],
        "buttons": [],
    }


# ───────────────────────── HLD-6 淨值與配息序列 ─────────────────────────

_DIV_KIND_TEXT = {"income": "收益", "principal": "本金", "unknown": "來源未區分"}


def _build_hld6(dataset):
    nav_rows = []
    for row in sorted(
        dataset.get("nav", []), key=lambda r: (r["fund_code"], r["nav_date"])
    ):
        nav_rows.append(
            {
                "_fund_code": row["fund_code"],
                "_estimated_badge": "推估" if row["is_estimated"] else "",
                # ⚠️ 兩枚徽章**做進模型**：渲染時現組的 dict 沒有 `_kind`，`collect_badges()`
                #    結構上收不到（`test_來源徽章中性不著色` 因此空掃至今）；走 helper 另有
                #    字面值守衛（不在 `44` 5.2 那七個之內會 raise）。
                "_source_badge": source_badge(row["source_tier"]),
                "_estimated_badge_node": (
                    status_badge("推估") if row["is_estimated"] else None
                ),
                "fund_code": row["fund_code"],
                "nav_date": row["nav_date"],
                "nav_text": f"{row['nav_orig_ccy']:.4f}{HINT}",
                "ccy": row["ccy"],
                "source_tier": row["source_tier"],
            }
        )
    div_rows = []
    for row in sorted(
        dataset.get("dividend", []), key=lambda r: (r["fund_code"], r["ex_date"])
    ):
        div_rows.append(
            {
                "_fund_code": row["fund_code"],
                "fund_code": row["fund_code"],
                "ex_date": row["ex_date"],
                # `44` 4.3：`pay_date` 是兩張表裡唯一「可空」為是的欄位；空的時候顯示 ⬜。
                "pay_date": row["pay_date"] or "⬜",
                "div_text": f"{row['div_per_unit_orig_ccy']:.4f}{HINT}",
                "ccy": row["ccy"],
                "div_kind": _DIV_KIND_TEXT.get(row["div_kind"], row["div_kind"]),
            }
        )

    state = STATE_OK if (nav_rows or div_rows) else STATE_MISSING
    summary = (
        f"淨值 {len(nav_rows)} 列{HINT} · 配息 {len(div_rows)} 列{HINT}"
        if state == STATE_OK
        else f"{ND_TEXT}：兩張表都沒有列"
    )
    detail_lines = [
        "表不做任何補值，缺的日期不出現在表上；週末與假日沒有列屬正常。"
        "可空的只有配息表的入帳日一欄，空的時候顯示 ⬜。"
    ]
    if state == STATE_MISSING:
        # `44` :719 只寫「無列 → `來源缺`」。兩張表為空**不一定**等於沒有持倉
        # （取數失敗、區間外都可能），上一輪那句原因是假資料下碰巧成立，已撤。
        detail_lines = [empty_source_text(["nav", "dividend"])]

    return {
        "code": "HLD-6",
        "title": BLOCK_TITLES["HLD-6"],
        "_layer": 4,
        "_default_open": False,
        "_state": state,
        "_tone": tone_for_state(state),
        "nav_rows": nav_rows,
        "div_rows": div_rows,
        "nav_labels": ["基金代碼", "淨值日期", "單位淨值（原幣）", "幣別", "來源層級", "推估"],
        "div_labels": ["基金代碼", "除息日", "入帳日", "每單位配息（原幣）", "幣別", "配息類別"],
        "answers": ANSWERS["HLD-6"],
        "summary_text": summary,
        "detail_lines": detail_lines,
        "badges": [],
        "buttons": [],
    }


# ───────────────────────── HLD-8 ─────────────────────────


def _build_hld8(metrics, *, has_holdings, has_window):
    rows = []
    unknown_total = 0
    for metric in metrics:
        unknown_total += metric["unknown_count"]
        rows.append(
            {
                "_fund_code": metric["_fund_code"],
                "_ccy": metric["_ccy"],
                "fund_name": metric["fund_name"],
                "ccy_text": f"{metric['_ccy']}{HINT}",
                "drawdown": metric["最大回撤"],
                "principal": metric["本金類配息佔比"],
            }
        )

    detail_lines = [
        "這兩個值原本各是績效與風險卡、配息與本金卡的第三個值；"
        "客戶 2026-09-22 裁定核心卡各留兩個主值，第三個值移到這一層。"
        "兩個值都是比率，逐檔仍寫出幣別字面值，本表沒有任何跨幣別的合計、平均或比值。"
    ]
    buttons = []
    if not has_holdings:
        state = STATE_MISSING
        summary = f"{ND_TEXT}：{TEXT_NO_HOLDING}"
        detail_lines = [empty_source_text(["holding"]), TEXT_NO_HOLDING]
    else:
        states = [row["drawdown"]["_state"] for row in rows] + [
            row["principal"]["_state"] for row in rows
        ]
        state = worst_state(states)
        summary = (
            f"{len(rows)} 檔{HINT} · 兩個值皆出數"
            if state == STATE_OK
            else f"{len(rows)} 檔{HINT} · 有值取不到或不適用"
        )
        if not has_window:
            detail_lines.insert(0, NA_NO_WINDOW)
        if unknown_total:
            # `44` HLD-8 空狀態逐字：並在**表下**寫出未知的筆數。
            detail_lines.append(f"配息類別未知的筆數：{unknown_total} 筆{HINT}")
        # ⚠️ 上一輪曾收成「只有取數失敗才掛」，**本輪撤回**：`44` :762 第一句逐字
        #    「四狀態逐值判定，**與核心卡同一套**」，收窄後同一個缺淨值條件下核心卡各一枚、
        #    本塊零枚，同一套當場破掉；上一輪引的 §5.5「整格為準」自己寫明射程不含核心卡那張表。
        #    ⛔ 「四塊一起拿掉」是另一邊，**屬客戶地盤，不替客戶選**（登記待裁）。
        if any(s in (STATE_MISSING, STATE_ERROR) for s in states):
            buttons.append(_retry_button())

    return {
        "code": "HLD-8",
        "title": BLOCK_TITLES["HLD-8"],
        "_layer": 4,
        "_default_open": False,
        "_state": state,
        "_tone": tone_for_state(state),
        "_rows": rows,
        "column_labels": ["基金名", "幣別", "最大回撤", "本金類配息佔比"],
        "answers": ANSWERS["HLD-8"],
        "summary_text": summary,
        "detail_lines": detail_lines,
        "badges": [],
        "buttons": buttons,
    }


# ───────────────────────── HLD-7 計算軌跡 ─────────────────────────


def _inputs_text(metric, indicator):
    if indicator in ("區間報酬率", "期間波動", "最大回撤"):
        rows = metric["nav_rows"]
        if not rows:
            return f"0 筆{HINT}"
        return (
            f"{len(rows)} 筆{HINT} · {rows[0]['nav_date']}{HINT}"
            f" 至 {rows[-1]['nav_date']}{HINT}"
        )
    rows = metric["div_rows"]
    if not rows:
        return f"0 筆{HINT}"
    return (
        f"{len(rows)} 筆{HINT} · {rows[0]['ex_date']}{HINT}"
        f" 至 {rows[-1]['ex_date']}{HINT}"
    )


def _build_hld7(metrics, hld1_rows, *, has_holdings):
    rows = []
    for metric in metrics:
        for indicator, owner in INDICATOR_OWNER.items():
            node = metric[indicator]
            rows.append(
                {
                    "_fund_code": metric["_fund_code"],
                    "_indicator": indicator,
                    "_owner_code": owner,
                    "_ccy": metric["_ccy"],
                    "indicator_text": f"{indicator}（{metric['fund_name']}）",
                    "inputs_text": _inputs_text(metric, indicator),
                    "formula_text": FORMULA_TEXT[indicator],
                    "output_text": node["text"],
                }
            )
    for row in hld1_rows:
        rows.append(
            {
                "_fund_code": row["_fund_code"],
                "_indicator": row["trace_indicator"],
                "_owner_code": "HLD-1",
                "_ccy": row["_ccy"],
                "indicator_text": f"{row['trace_indicator']}（{row['fund_name']}）",
                "inputs_text": f"1 條門檻{HINT} · 門檻值 {row['threshold_text']}",
                "formula_text": _DEVIATION_FORMULA,
                "output_text": row["delta_text"],
            }
        )

    # `44` :730「四塊沒有一塊出數 → `來源缺`」。上一輪只看有沒有持倉，於是「有持倉但
    # 四塊一個數都沒出」時塊態還是 `ok`（實測 18 列全不適用，塊卻宣稱正常）。
    # ⚠️ 同一格另有一句「輸入欄照列」，兩句**同時滿足**：`來源缺` 定塊的狀態、
    #    「輸入欄照列」定列的畫面，兩者不同層。⛔ 把列吞掉只印「來源缺」是假話 ——
    #    來源在，是區間沒設。
    any_output = bool(hld1_rows) or any(
        metric[indicator]["_state"] == STATE_OK
        for metric in metrics
        for indicator in INDICATOR_OWNER
    )
    state = STATE_OK if (has_holdings and rows and any_output) else STATE_MISSING
    if state == STATE_MISSING:
        detail_lines = [
            empty_source_text(["HLD-1", "HLD-2", "HLD-3", "HLD-8"]),
            "四塊沒有一塊出數；下面各列的輸入筆數與不適用原因照列。",
        ]
        summary = (
            f"{ND_TEXT}：四塊沒有一塊出數 · {len(rows)} 列{HINT}"
            if rows
            else f"{ND_TEXT}：四塊沒有一塊出數"
        )
    else:
        detail_lines = [
            "輸出值與該列指標名所在那一塊上顯示的值逐字相同；"
            "算式以文字寫出，不寫任何實作語言的語法。"
            "該塊把該指標判為不適用時，輸出欄顯示同一句不適用文案，輸入欄照列。"
        ]
        summary = f"逐檔逐指標 {len(rows)} 列{HINT}"

    return {
        "code": "HLD-7",
        "title": BLOCK_TITLES["HLD-7"],
        "_layer": 4,
        "_default_open": False,
        "_state": state,
        "_tone": tone_for_state(state),
        "_rows": rows,
        "column_labels": [
            "指標名",
            "取用的輸入筆數與首末日期",
            "算式的文字寫法",
            "輸出值",
        ],
        "answers": ANSWERS["HLD-7"],
        "summary_text": summary,
        "detail_lines": detail_lines,
        "badges": [],
        "buttons": [],
    }


# ───────────────────────── 組裝 ─────────────────────────


def build_page_model(
    dataset: dict,
    *,
    fields=None,
    viewport_width: int = 1280,
    open_fund=None,
) -> dict:
    """把假資料 ＋ 使用者輸入組成一份純資料模型。page.py 只負責把它畫出來。

    ⚠️ **登記（`44` HLD-4 自己登記為待客戶裁決的那一個缺口）**：
    使用者按了「存檔」、沒按「套用」，然後重新載入 —— 此時三張核心卡顯示什麼，`44` 沒有訂。
    兩種讀法（載入時就拿存過的值算一次／等使用者再按一次「套用」）都讀得通。
    **本檔取前者**，理由是後者會讓畫面印出「⬜ 不適用：尚未設定區間」，
    而那句話在區間明明已經設過的情況下**是假的** —— 印一句假的比多算一次危險（§1）。
    **這不是規格，是被迫挑的一邊；客戶裁哪一邊，改的只有這一行。**
    """
    applied_window = saved_window(dataset)
    rules = saved_rules(dataset)
    metrics = all_metrics(dataset, applied_window)
    has_holdings = bool(dataset.get("holding"))
    has_window = window_is_valid(applied_window)

    fields = dict(fields) if fields else {
        "window_start": applied_window[0],
        "window_end": applied_window[1],
    }

    hld1 = _build_hld1(metrics, rules, has_holdings=has_holdings)
    hld2 = _build_core_card(
        "HLD-2",
        metrics,
        ("區間報酬率", "期間波動"),
        has_holdings=has_holdings,
        has_window=has_window,
        subtitle="兩個主值。各值以原幣計算，逐檔寫出幣別字面值；"
        "本卡沒有任何跨幣別的合計、平均或比值。",
        moved_note="第三個值「最大回撤」已依客戶 2026-09-22 裁定移到層 4 的 HLD-8。",
    )
    hld3 = _build_core_card(
        "HLD-3",
        metrics,
        ("期間配息合計", "配息佔淨值比"),
        has_holdings=has_holdings,
        has_window=has_window,
        subtitle="兩個主值，皆為算術結果，卡上不對它們加任何評語。"
        "配息合計以原幣逐檔顯示，逐檔寫出幣別字面值；"
        "本卡沒有任何跨幣別的合計、平均或比值。",
        moved_note="第三個值「本金類配息佔比」已依客戶 2026-09-22 裁定移到層 4 的 HLD-8。"
        "配息類別未知的列仍計入期間配息合計。",
    )
    cards = [hld1, hld2, hld3]
    hld0 = _build_hld0(
        cards,
        has_holdings=has_holdings,
        has_rules=bool(rules),
        deviation_count=len(hld1["_rows"]),
    )
    blocks = [
        hld0,
        hld1,
        hld2,
        hld3,
        _build_hld4(applied_window=applied_window, fields=fields, rules=rules),
        _build_hld5(dataset, metrics, open_fund=open_fund, has_window=has_window),
        _build_hld6(dataset),
        _build_hld7(metrics, hld1["_rows"], has_holdings=has_holdings),
        _build_hld8(metrics, has_holdings=has_holdings, has_window=has_window),
    ]

    return {
        "title": PAGE_TITLE,
        "answers": PAGE_ANSWERS,
        "_viewport_width": viewport_width,
        "_columns": columns_for_width(viewport_width),
        "_window": applied_window,
        "blocks": blocks,
        # `44` 3.2：本頁不負責什麼。
        "footer_lines": [
            "不挑新標的，那是標的探索",
            "不談市場環境，那是市場總覽",
            "不決定要不要調整 —— 本頁只呈現偏離，處置方向不在本頁產生",
            "偏離提示只客觀描述現況與目標差距；門檻與區間由使用者自行輸入",
        ],
        "footer_badges": [_redline_badge("G2†"), _redline_badge("G3†")],
    }


# ───────────────────────── 查詢與掃描 ─────────────────────────


def all_blocks(model: dict) -> list:
    return list(model["blocks"])


def find_block(model: dict, code: str) -> dict:
    for block in model["blocks"]:
        if block["code"] == code:
            return block
    raise KeyError(code)


def codes_in_layer(model: dict, layer: int) -> list:
    return [b["code"] for b in model["blocks"] if b["_layer"] == layer]


def fund_group(block: dict, fund_code: str) -> dict:
    for group in block.get("fund_groups", []):
        if group["_fund_code"] == fund_code:
            return group
    raise KeyError(fund_code)


def find_row(block: dict, fund_code: str) -> dict:
    for row in block.get("_rows", []):
        if row["_fund_code"] == fund_code:
            return row
    raise KeyError(fund_code)


def find_button(model: dict, label: str) -> dict:
    for button in collect_buttons(model):
        if button["label"] == label:
            return button
    raise KeyError(label)


def _walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, (list, tuple, set)):
        for value in node:
            yield from _walk(value)


def collect_badges(model: dict) -> list:
    return [n for n in _walk(model) if isinstance(n, dict) and "_kind" in n and "text" in n]


def collect_buttons(model: dict) -> list:
    return [n for n in _walk(model) if isinstance(n, dict) and "_action_kind" in n]


def collect_inputs(model: dict) -> list:
    return [n for n in _walk(model) if isinstance(n, dict) and n.get("_input") is True]


def value_nodes(model) -> list:
    return [n for n in _walk(model) if isinstance(n, dict) and n.get("_value_node")]


def numeric_nodes(model) -> list:
    return [n for n in value_nodes(model) if n["_has_number"]]


def non_ok_value_nodes(model) -> list:
    return [n for n in value_nodes(model) if n["_state"] != STATE_OK]


def empty_state_texts(model) -> set:
    """全頁用到的空狀態文案。

    母體不只主值位置 —— `44` HLD-4 把「⬜ 不適用：尚未設定區間」放在**核心卡的副標**，
    所以只掃主值會漏掉它。這裡收兩種：主值位置的字串，
    加上任何一句**恰好是**不適用／資料未備／取數失敗模板本身的畫面文字
    （帶來源鍵或帶訊息原文的那幾句不算 —— 它們是那一句後面再接東西，不是同一句）。
    """
    texts = {n["text"] for n in non_ok_value_nodes(model)}
    for line in collect_ui_strings(model):
        if line in (ND_TEXT, ERR_TEXT) or line.startswith("⬜ 不適用："):
            texts.add(line)
    return texts


def cross_currency_nodes(model) -> list:
    """把兩種幣別的數合成一個值的節點。`44` 5.1「同一張卡不混不同幣別做平均」、
    `HLD-2` 判準「沒有任何一個跨幣別的合計數」、`HLD-8`「本表不做任何跨幣別的合計、平均或比值」。

    ⚠️ **舊版從來沒有守到東西**：它要求「同一個 `text` 字串裡出現兩個幣別字面值」，
    而本頁的百分比不帶幣別、金額只帶一個 —— 實測六情境每個節點的幣別命中數恆為 1，
    **那個條件永遠不成立**。稽核把一個真的跨幣別平均塞進核心卡，舊版毫無反應。

    現行改為**歸屬檢查**：每一個出數的值都必須掛在某一檔底下，且幣別與那一檔相同。
    一個跨幣別的合計／平均／比值，**要嘛掛不到任何一檔底下**（卡層級或表層級的合計），
    **要嘛幣別對不上它所在的那一檔** —— 兩條路都會被抓到。
    """
    bad = []
    for block in model["blocks"]:
        containers = list(block.get("fund_groups", ())) + [
            row for row in block.get("_rows", ()) if isinstance(row, dict) and "_fund_code" in row
        ]
        owned = set()
        for container in containers:
            ccy = container.get("_ccy")
            for node in value_nodes(container):
                owned.add(id(node))
                if not node["_has_number"]:
                    continue
                if not isinstance(ccy, str) or not ccy or node["_ccy"] != ccy:
                    bad.append(node)
        for node in value_nodes(block):
            # 掛不到任何一檔底下的出數值 —— 那正是一個跨幣別合計會長的樣子。
            if node["_has_number"] and id(node) not in owned:
                bad.append(node)
    return bad


def block_value_strings(block: dict) -> list:
    return [n["text"] for n in value_nodes(block)]


def value_shown_in_block(model, owner_code, fund_code, indicator) -> str:
    """那一塊上實際顯示的字串。`44` HLD-7 判準要的就是這個。"""
    block = find_block(model, owner_code)
    if owner_code in ("HLD-2", "HLD-3"):
        for mv in fund_group(block, fund_code)["main_values"]:
            if mv["label"] == indicator:
                return mv["text"]
    elif owner_code == "HLD-8":
        row = find_row(block, fund_code)
        key = "drawdown" if indicator == "最大回撤" else "principal"
        return row[key]["text"]
    elif owner_code == "HLD-1":
        for row in block["_rows"]:
            if row["_fund_code"] == fund_code and row["trace_indicator"] == indicator:
                return row["delta_text"]
    raise KeyError((owner_code, fund_code, indicator))


def collect_ui_strings(model: dict) -> list:
    """把介面全頁文字抓成一份清單（`44` 1.2 節判準）。

    刻意連機器用的鍵一起走過 —— 寧可多抓，不可漏抓。
    ⚠️ 走的是**模型**，不是本檔的原始碼 —— 禁令字表住在本檔的常數裡，
    所以它不會掃到自己（負控不落文件）。
    """
    out = []

    def walk(node):
        if isinstance(node, str):
            out.append(node)
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple, set)):
            for value in node:
                walk(value)

    walk(model)
    return out


def scan_forbidden(strings) -> dict:
    """禁方向詞 ＋ 禁箭頭的字表掃描。回傳 {詞: [命中的字串]}，全清時回 {}。"""
    hits = {}
    for term in FORBIDDEN_DIRECTION_WORDS + FORBIDDEN_ARROWS:
        matched = [s for s in strings if isinstance(s, str) and term in s]
        if matched:
            hits[term] = matched
    return hits
