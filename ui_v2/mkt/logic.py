# -*- coding: utf-8 -*-
"""市場總覽純邏輯。零 streamlit import、零舊 repo import、零網路。

所有判定住在這裡；page.py 只負責把下面 build_page_model() 產出的模型畫出來。
理由：streamlit 在本環境要靠 scratchpad 才匯入得到，邏輯綁進 streamlit 會讓測試跑不起來。

模型慣例：底線開頭的鍵是**機器用**（狀態、色調、層號…），不開頭底線的鍵是**畫面文字**。

⚠️ 本檔逐處標了「登記」的地方，是 `44`／`47` 沒有寫、而不決定就畫不出來的。
   一律照最保守的畫法做，**不自行發明規格**，逐筆列進回報。
"""

from __future__ import annotations

from datetime import date, timedelta

# 「這個參數沒有被傳」與「這個參數被傳成 None」是兩件事，不可混為一談：
# 前者要退回已套用的那一組，後者是使用者把欄位清空了。
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

# `44` 5.1 卡片表：四狀態各自的顏色語意。
_TONE_BY_STATE = {
    STATE_OK: "中性",
    STATE_MISSING: "灰",
    STATE_BIZ: "黃",
    STATE_ERROR: "紅",
}
# ⚠️ **`44` 對這四個狀態只排過一次序，而那一次把中間兩個並列同級。**
# `44` :310（`MKT-0` 規則欄，全檔唯一明文排過卡片四狀態的地方）逐字：
#   「三塊狀態取最差者：三塊皆 `ok` → 燈為中性灰，文案「三張卡的資料齊」；
#     任一塊為 `資料未備` 或 `業務例外` → 燈為黃，文案列出是哪一張卡；
#     任一塊為 `系統錯誤` → 燈為紅，文案列出失敗的那一段」
# 也就是 `ok` ＜ {`資料未備`, `業務例外`} ＜ `系統錯誤` —— 這是一個**偏序**，不是全序。
#
# ⛔ **舊表述 `_SEVERITY = {ok:0, 資料未備:1, 業務例外:2, 系統錯誤:3}` 把中間兩個排出先後，
#    那個先後是實作自己發明的，`44` 沒有授權**（客戶 2026-09-24 裁示拆掉）。
# ⚠️ **本檔這一筆比 `hld` 那一筆尖銳**：舊 `worst_state()` 的 docstring 自陳
#    「`44` MKT-0 規則逐字」，而 `MKT-0` 的規則欄（`44` :310）**正是全檔唯一把那兩個
#    並列同級的地方** —— **它引的那一行，恰好否證它自己排出來的先後。**
#    ⇒ 一個「逐字」標籤不保證引文與結論同向；**引了，就要讀完再對照自己寫了什麼**。
# 📌 同型的拆除 2026-09-23 已在 `ui_v2/hld/logic.py` 做過一次，本檔照同一套辦
#    （`_BAND` ／ `_band()` ／ `STATE_UNRANKED` ／ `block_tone()` ／ `tone_for_block()`
#    五個名字刻意與那一檔逐字相同，方便兩頁互相對讀）。
_BAND = {STATE_OK: 0, STATE_MISSING: 1, STATE_BIZ: 1, STATE_ERROR: 2}

# `worst_state()` 在「`資料未備` 與 `業務例外` 同時是最差」時回這個哨符。
# ⛔ 它**不是第五個狀態**（`44` 5.1 的四狀態是封閉列舉），也**不得寫進任何畫面文字**；
#    它只表示一件事：**`44` 沒有排這兩個的先後，本檔不替它排。**
# ⚠️ 考慮過、而且刻意**不用** `44` 5.2 的 `未定義` 徽章字面值 —— 那一個在 `44` :1735 逐字是
#    「某塊的來源欄寫了一個本檔第四節未定義的欄位 → 該欄位單獨列出並掛「未定義」徽章」，
#    與本處無關，借來用等於替 `44` 造新語意。
STATE_UNRANKED = None

# ⚠️ **`STATE_UNRANKED` 沒有「名字」，但它有「級」** —— 它只在
#    `資料未備` 與 `業務例外` 同時最差時產生，而 `44` :310 把那兩個放在**同一級**，
#    所以「哪一級」是確定的（就是中間那一級），不確定的只有「哪一個名字」。
#    `_band()` 因此答得出它；`_BAND` 本身**刻意不收這個鍵**，
#    因為收進去就等於承認它是第五個狀態。
_UNRANKED_BAND = 1

# 結論燈那一級同時有這兩個成員時，文案要照哪個順序把它們寫出來。
# ⚠️ **這是書寫順序，不是嚴重度順序** —— 取自 `44` :310 那一行自己把兩者並列時的寫法
#    （先 `資料未備`、後 `業務例外`）。拿它去推論誰比較嚴重，就是本輪剛拆掉的那個錯。
_UNRANKED_PAIR = (STATE_MISSING, STATE_BIZ)


def _band(state) -> int:
    """狀態 → `44` :310 那三級。`STATE_UNRANKED` 走上面那條註解說明的路。"""
    return _UNRANKED_BAND if state is STATE_UNRANKED else _BAND[state]

# 結論燈文案點名一張卡時，狀態要寫成哪一個徽章字面值（`47` D-03／D-04 的樣式）。
_STATE_IN_LIGHT_TEXT = {
    STATE_MISSING: "資料未備",
    STATE_BIZ: "不適用",
    STATE_ERROR: "取數失敗",
}

# 塊名逐字引 `44` 3.1 的層次表。
BLOCK_TITLES = {
    "MKT-0": "環境結論燈",
    "MKT-1": "風險情緒卡",
    "MKT-2": "景氣位置卡",
    "MKT-3": "資金與匯率卡",
    "MKT-4": "觀察窗與比較基準輸入",
    "MKT-5": "指標清單設定",
    "MKT-6": "指標明細表",
    "MKT-7": "新鮮度與來源清單",
}
BLOCK_LAYERS = {
    "MKT-0": 1,
    "MKT-1": 2,
    "MKT-2": 2,
    "MKT-3": 2,
    "MKT-4": 3,
    "MKT-5": 3,
    "MKT-6": 4,
    "MKT-7": 4,
}

# 各卡的主值：(來源鍵, 畫面標籤, 小數位數, 單位字面值, 本卡宣告的單位)
# 標籤與小數位數逐字引 `44` 3.1 各塊的來源欄與規則欄。
# ⚠️ 登記：`leading_index`／`coincident_index` 的小數位數 `44` 沒有定（`47` Q-13）。
#    本檔不替它挑一個 —— decimals=None 時照 value_num 原樣印。
_CARD_SPECS = {
    "MKT-1": [
        ("vol_index", "波動度指數", 1, "", None),
        ("credit_spread_pct", "高收益信用利差", 2, "pp", "pp"),
    ],
    "MKT-2": [
        ("leading_index", "領先指標", None, "", None),
        ("coincident_index", "同時指標", None, "", None),
    ],
    "MKT-3": [
        ("policy_rate_pct", "政策利率", 2, "%", "%"),
        ("fx_twd_per_usd", "新臺幣對美元匯率", 3, "新臺幣／美元", "新臺幣／美元"),
    ],
}

MKT6_COLUMNS = (
    "indicator_key",
    "obs_date",
    "release_date",
    "value_num",
    "value_unit",
    "source_tier",
    "fetched_at",
    "is_revised",
)
# `47` D-14：八個中文欄頭的字面為線框組擬定。
MKT6_COLUMN_LABELS = {
    "indicator_key": "指標鍵",
    "obs_date": "觀測日",
    "release_date": "公布日",
    "value_num": "數值",
    "value_unit": "單位",
    "source_tier": "來源層級",
    "fetched_at": "取得時間",
    "is_revised": "是否修正",
}

# `44` 4.5：時間一律以世界協調時間存放。
STORAGE_TIMEZONE = "UTC"


# ───────────────────────── 格式 ─────────────────────────


def format_value(value: float, decimals: int | None) -> str:
    """decimals 為 None 時照原樣印 —— SSOT 沒定小數位數就不替它挑一個。"""
    if decimals is None:
        return str(value)
    return f"{value:.{decimals}f}"


def format_signed(value: float, decimals: int) -> str:
    """`44` 1.2：期間變化以正負號與數字寫出（例：-2.3%），不配箭頭。"""
    return f"{value:+.{decimals}f}"


def tone_for_state(state: str) -> str:
    """四狀態 → 顏色語意。`44` 5.1 卡片那張表。回傳語意字串，不回色碼。"""
    return _TONE_BY_STATE[state]


def block_tone(states) -> str:
    """一塊的邊框顏色。**只做呈現，不做嚴重度判定。**

    ⚠️ 為什麼要有這一支：`44` 5.1 現行讀法逐字「**四狀態掛在主值上，不掛在整張卡**」，
    而卡層級本身 `44` **沒有給一個狀態，也沒有給一個顏色**。邊框得有個顏色才畫得出來，
    這一支就是那個實作必需品，**它不宣稱任何一個狀態比另一個嚴重**。
    規則：這一塊的主值裡出現過最顯眼的那個顏色。顏色語意逐值取自 `44` 5.1 那張表。
    ⚠️ 依據是客戶 2026-09-23 的原話「顏色是 UI 顯示，不是嚴重度；兩者正交」
    （`44` :2344 轉述）—— 本函式站在「顯示」那一邊，所以它可以排顏色；
    `worst_state()` 站在「嚴重度」那一邊，所以它**不**排 `資料未備` 與 `業務例外`。
    ⚠️ 「站在哪一邊」是**本組的接法**，不是客戶的字。
    ⛔ 本函式的輸入是**主值**的狀態（恆為四狀態之一），不是塊的狀態 ——
       塊的狀態可能是 `STATE_UNRANKED`，那個要走 `_band()`，不走這裡。
    """
    tones = {tone_for_state(s) for s in states}
    for tone in ("紅", "黃", "灰"):
        if tone in tones:
            return tone
    return "中性"


def tone_for_block(state, states) -> str:
    """一塊要畫的顏色。

    狀態排得出來 → 照 `44` 5.1 那張表把那個狀態翻成顏色（本檔既有行為，一格未動）。
    排不出來（`資料未備` 與 `業務例外` 同級）→ 才退到 `block_tone()` 看主值的顏色。
    ⚠️ 這樣寫的用意：**拆掉 tie-break 不改變任何一個現行畫面的顏色**，
    改變的只有「這一塊最差的是哪一個狀態」這句宣稱在同級時不再硬答。
    """
    return block_tone(states) if state is STATE_UNRANKED else tone_for_state(state)


# ───────────────────────── 斷點 ─────────────────────────


def columns_for_width(width_px: int) -> int:
    """`44` 2.1 客戶最終版：≤768 單欄／769-1279 兩欄／≥1280 三欄。

    ⚠️ `47` 的三個斷點小節標題仍寫 1024／640 —— 那兩個值已由客戶廢棄
    （`44` 2.1 逐字：「1024 / 640 廢棄，未量過裝置」）。以 `44` 為準。
    """
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
    # 層 3：`44` 逐字「五頁的層 3 各只有兩塊，兩塊並排同一列」——
    # ≥1280 時第三欄空著，所以並排數上限是 2 而不是 3。
    return min(2, columns_for_width(width_px))


# ───────────────────────── 文案模板（逐字引 `44` 5.5） ─────────────────────────


def empty_source_text(source_keys) -> str:
    return "⬜ 資料未備：" + " 與 ".join(source_keys) + " 尚無資料"


def not_applicable_text(reason: str) -> str:
    return "⬜ 不適用：" + reason


def fetch_failed_text(message: str) -> str:
    """訊息原文照印 —— 不改寫成安撫語句，也不截斷。"""
    return "⛔ 取數失敗：" + message


def partial_range_text(start: str, end: str) -> str:
    return f"缺 {start} 至 {end}"


# ───────────────────────── 新鮮度 ─────────────────────────


def delay_days(obs_date: str, fetched_at: str) -> int:
    """`44` MKT-7 逐字：延遲日數 ＝ fetched_at 的日期減 obs_date，單位日曆日。"""
    return (date.fromisoformat(fetched_at[:10]) - date.fromisoformat(obs_date)).days


def freshness_badge_text(delay: int) -> str | None:
    """`延遲 N 日` 在 `44` MKT-7 有定義，直接算得出來。

    ⚠️ 登記：`即時`／`當日` 兩級的判定門檻 `44` 沒有定（`47` Q-05）。
    本檔**不自行發明門檻** —— delay <= 0 時回 None，由呼叫端掛一枚 `未定義` 狀態徽章。
    """
    if delay >= 1:
        return f"延遲 {delay} 日"
    return None


# ───────────────────────── 主值狀態（逐主值） ─────────────────────────


def main_value_state(rows, *, expected_unit: str | None = None, error: str | None = None) -> str:
    """一個主值的四狀態。`44` 5.1 本輪已把四狀態改為掛在主值上。

    順序刻意是「失敗 → 缺 → 單位不符 → ok」：取數失敗比缺資料更該說出來（§1 Fail Loud）。
    expected_unit 為 None 時不做單位檢查 —— `44` 只有 MKT-3 那一塊宣告了單位。
    """
    if error:
        return STATE_ERROR
    if not rows:
        return STATE_MISSING
    if expected_unit is not None and rows[-1]["value_unit"] != expected_unit:
        return STATE_BIZ
    return STATE_OK


def worst_state(states):
    """最差的那一個狀態；**兩者同級時不替 `44` 排先後**，回 `STATE_UNRANKED`。

    `44` :310 只排到 `ok` ＜ {`資料未備`, `業務例外`} ＜ `系統錯誤`。
    最差那一級只有一個成員時照回那個成員；最差那一級同時有 `資料未備` 與 `業務例外` 時
    **沒有答案** —— 回 `STATE_UNRANKED`，不挑一個充數。

    ⚠️ **舊 docstring 寫「`44` MKT-0 規則逐字：三塊狀態取最差者」** ——
       前半句是真的（`44` :310 確實寫了「三塊狀態取最差者」），**但它只抄了半句**：
       同一行接下來就把 `資料未備` 與 `業務例外` 並列成同一個結果（都是黃）。
       **抄前半句、丟掉後半句，抄出來的就是一個 `44` 沒有寫的全序。**
    ⚠️ **回傳值與輸入順序無關**（同級時回哨符，不回「第一個」）。
    ⚠️ 空集回 `資料未備`：本檔既有行為，`44` 未訂（一塊的主值集合為空時沒有東西可讀）。
       **本輪一格未動這條**。
    ⚠️ **輸入可以含 `STATE_UNRANKED`**（結論燈讀的三塊狀態就可能含它）——
       見 `_band()`。⛔ 這一條是本輪的當掉點：漏了它，結論燈那一支會 `KeyError: None`。
    """
    if not states:
        return STATE_MISSING
    top = max(_band(s) for s in states)
    tied = {s for s in states if _band(s) == top}
    if len(tied) == 1:
        return next(iter(tied))
    return STATE_UNRANKED


# ───────────────────────── 取數與過濾 ─────────────────────────


def rows_for_key(dataset: dict, key: str) -> list[dict]:
    """依 obs_date 遞增回傳該鍵的全部觀測。"""
    rows = [r for r in dataset.get("rows", []) if r["indicator_key"] == key]
    return sorted(rows, key=lambda r: (r["obs_date"], r["release_date"]))


def all_keys(dataset: dict) -> list[str]:
    """`44` MKT-5 逐字：清單以 indicator_key 的字面值排列，不依任何分數排序。

    ⚠️ 登記：可選鍵清單的來源 `44` 沒有寫（`47` Q-09）。
    本檔取「資料表裡出現過的鍵」∪「三張核心卡點名的六個鍵」，是最保守的一種
    （不隱藏任何已經有資料的鍵，也不讓卡片點名的鍵從清單裡消失）。
    """
    from_rows = {r["indicator_key"] for r in dataset.get("rows", [])}
    return sorted(from_rows | set(_six_keys()))


def _six_keys() -> tuple:
    return tuple(spec[0] for specs in _CARD_SPECS.values() for spec in specs)


def window_start(window_days: int | None, baseline_date: str | None) -> str | None:
    """觀察窗起點。

    ⚠️ 登記：`44` MKT-4 宣告了兩個輸入（觀察窗長度 days_calendar、比較基準日），
    但**沒有寫兩者怎麼組成觀察窗**。本檔取「基準日往前推 window_days 個日曆日」——
    那是唯一同時用到兩個輸入的組法，也是最保守的一種（不額外引入第三個隱含參數）。
    """
    if not window_days or window_days <= 0 or not baseline_date:
        return None
    return (date.fromisoformat(baseline_date) - timedelta(days=int(window_days))).isoformat()


# ───────────────────────── 徽章 ─────────────────────────


def _status_badge(text: str) -> dict:
    if text not in STATUS_BADGE_LITERALS:
        raise ValueError(f"狀態徽章字面值 {text!r} 不在 `44` 5.2 的七個之內")
    return {"_kind": "狀態", "_tone": "黃" if text != "資料未備" else "灰", "text": text}


def _source_badge(tier: str) -> dict:
    """`44` 5.2：來源徽章中性、不著色。"""
    return {"_kind": "來源", "_tone": "中性", "text": tier}


def _freshness_badge(rows) -> dict:
    if not rows:
        return _status_badge("未定義")
    latest = rows[-1]
    delay = delay_days(latest["obs_date"], latest["fetched_at"])
    text = freshness_badge_text(delay)
    if text is None:
        return _status_badge("未定義")
    return {"_kind": "新鮮度", "_tone": "中性", "text": text}


def _redline_badge(mark: str) -> dict:
    """`44` 5.2：紅線徽章只出現在說明區，不出現在任何數值旁。"""
    return {"_kind": "紅線", "_tone": "中性", "_slot": "說明區", "text": mark}


# ───────────────────────── 按鈕 ─────────────────────────


def _button(label, kind, *, writes=frozenset(), enabled=True, disabled_reason="") -> dict:
    return {
        "_action_kind": kind,
        "_writes": set(writes),
        "_enabled": bool(enabled),
        "_visible": True,  # `44` 5.3：按鈕停用時不隱藏
        "label": label,
        "disabled_reason": disabled_reason,
    }


def _retry_button() -> dict:
    """`取數` 類只寫取回的列與 fetch_log，四張表一個字也不寫（`44` 5.3）。"""
    return _button("重新取數", "取數", writes={"market_indicator", "fetch_log"})


# ───────────────────────── 三張核心卡 ─────────────────────────


def _build_card(code, dataset, *, window_days, baseline_date, selected_keys):
    specs = _CARD_SPECS[code]
    errors = dataset.get("errors", {})
    main_values = []
    detail_lines = []
    badges = []

    # `44` MKT-5 空狀態：一個也沒勾 → 三張核心卡顯示 `來源缺`，文案「尚未選定任何指標」。
    # ⚠️ 登記：selected_keys 為 None 代表該設定「未設定」（MKT-5 沒有寫回路徑，見下）。
    #    勾選與三張核心卡那六個固定鍵的關係 `44` 沒有寫（`47` Q-09），
    #    故 None 時不套用任何過濾 —— 照各卡自己「來源」欄點名的鍵取數，那是 `44` 唯一寫明的綁定。
    nothing_selected = selected_keys is not None and len(selected_keys) == 0

    for source_key, label, decimals, unit_text, expected_unit in specs:
        rows = rows_for_key(dataset, source_key)
        if nothing_selected:
            rows = []
        error = errors.get(source_key)
        state = main_value_state(rows, expected_unit=expected_unit, error=error)

        value_badges = []
        reason_text = ""
        if state == STATE_OK:
            value_text = format_value(rows[-1]["value_num"], decimals)
            value_badges.append(_source_badge(rows[-1]["source_tier"]))
            value_badges.append(_freshness_badge(rows))
        elif state == STATE_MISSING:
            value_text = "⬜ 資料未備"
            reason_text = source_key
            value_badges.append(_status_badge("資料未備"))
        elif state == STATE_BIZ:
            value_text = not_applicable_text("單位不符")
            reason_text = rows[-1]["value_unit"]
            value_badges.append(_status_badge("不適用"))
            detail_lines.append(f"來源給的單位字面值：{rows[-1]['value_unit']}")
        else:
            value_text = fetch_failed_text(error)
            reason_text = error
            value_badges.append(_status_badge("取數失敗"))

        main_value = {
            "_source_key": source_key,
            "_state": state,
            "_tone": tone_for_state(state),
            "_has_number": state == STATE_OK,
            "label": label,
            "value_text": value_text,
            "unit_text": unit_text if state == STATE_OK else "",
            "reason_text": reason_text,
            "badges": value_badges,
        }
        if source_key == "fx_twd_per_usd" and state == STATE_OK:
            # `44` MKT-3 逐字：單位固定寫成「新臺幣／美元」並在卡上明寫方向，不顯示倒數。
            main_value["direction_text"] = f"方向：1 美元 ＝ {value_text} 新臺幣"
        main_values.append(main_value)

    states = [mv["_state"] for mv in main_values]
    # `44` 5.1：一組主值為 ok 而另一組不是時，標題掛「部分缺」徽章。
    if STATE_OK in states and any(s != STATE_OK for s in states):
        badges.append(_status_badge("部分缺"))

    if nothing_selected:
        detail_lines.insert(0, "尚未選定任何指標")

    detail_lines.extend(
        _card_detail_lines(
            code,
            dataset,
            window_days=window_days,
            baseline_date=baseline_date,
            nothing_selected=nothing_selected,
        )
    )

    block_state = worst_state(states)
    buttons = []
    if any(s in (STATE_MISSING, STATE_ERROR) for s in states):
        buttons.append(_retry_button())

    return {
        "code": code,
        "title": BLOCK_TITLES[code],
        "_layer": BLOCK_LAYERS[code],
        "_default_open": True,
        "_state": block_state,
        # ⛔ **不是 `tone_for_state(block_state)`** —— `block_state` 現在可能是
        #    `STATE_UNRANKED`，那個查 `_TONE_BY_STATE` 會 `KeyError: None`。
        "_tone": tone_for_block(block_state, states),
        "_all_missing": all(s == STATE_MISSING for s in states),
        "answers": _ANSWERS[code],
        "summary_text": "",
        "main_values": main_values,
        "detail_lines": detail_lines,
        "badges": badges,
        "buttons": buttons,
    }


# 「回答什麼」逐字引 `44` 3.1 各塊那一格。
_ANSWERS = {
    "MKT-0": "我今天在這一頁看到的東西，可不可以照著讀",
    "MKT-1": "市場的緊張程度，跟我選的那個起點比，是拉開了還是收回去了",
    "MKT-2": "景氣的兩條線現在是一起走還是各走各的",
    "MKT-3": "換匯這一段，在我選的期間裡走了多寬",
    "MKT-4": "我現在是拿哪一段期間在比",
    "MKT-5": "這一頁現在在看的是哪幾個指標",
    "MKT-6": "上面三張卡那幾個數，逐筆長什麼樣",
    "MKT-7": "這一頁的每一個數字，是什麼時候、從哪一層來的",
}


def _card_detail_lines(code, dataset, *, window_days, baseline_date, nothing_selected):
    """各卡的副標。`44` MKT-4 逐字：未填時三張核心卡的副標顯示
    `⬜ 不適用：尚未設定觀察窗`。"""
    lines = []
    if nothing_selected:
        return lines

    start = window_start(window_days, baseline_date)
    if start is None:
        lines.append(not_applicable_text("尚未設定觀察窗"))

    if code == "MKT-1":
        lines.extend(_mkt1_delta_lines(dataset, start))
    elif code == "MKT-2":
        lines.extend(_mkt2_direction_lines(dataset, baseline_date))
    elif code == "MKT-3":
        lines.extend(_mkt3_range_lines(dataset, start, baseline_date))
    return lines


def _mkt1_delta_lines(dataset, start):
    """`44` MKT-1 逐字：副標顯示兩者與 MKT-4 所選觀察窗起點的差，
    寫成帶正負號的數字，不配箭頭。"""
    if start is None:
        return []
    parts = []
    for source_key, _label, decimals, unit_text, _expected in _CARD_SPECS["MKT-1"]:
        rows = rows_for_key(dataset, source_key)
        if not rows:
            continue
        if start < rows[0]["obs_date"]:
            return [not_applicable_text("觀察窗起點早於序列第一筆")]
        baseline_rows = [r for r in rows if r["obs_date"] <= start]
        if not baseline_rows:
            return [not_applicable_text("觀察窗起點早於序列第一筆")]
        delta = rows[-1]["value_num"] - baseline_rows[-1]["value_num"]
        parts.append(format_signed(delta, decimals if decimals is not None else 2) + (f" {unit_text}" if unit_text else ""))
    if not parts:
        return []
    return ["與觀察窗起點的差：" + " ／ ".join(parts)]


def _mkt2_direction_lines(dataset, baseline_date):
    """`44` MKT-2 逐字：副標顯示兩者最近 6 筆的方向一致或分歧；
    release_date 晚於比較基準日 → 該筆不進入計算，副標加一行寫被排除的筆數。

    ⚠️ 登記：「方向」怎麼算（逐期差／頭尾差／斜率）`44` 沒有寫（`47` Q-11）。
    本檔取**頭尾差的正負號**，是三種裡最少自由度的一種；三種會給出不同答案，
    這一筆等客戶裁，本檔不宣稱它是規格。
    """
    lines = []
    excluded = 0
    usable = {}
    for source_key in ("leading_index", "coincident_index"):
        rows = rows_for_key(dataset, source_key)
        if baseline_date:
            kept = [r for r in rows if r["release_date"] <= baseline_date]
            excluded += len(rows) - len(kept)
            rows = kept
        usable[source_key] = rows

    if excluded:
        lines.append(f"公布日晚於比較基準日，排除 {excluded} 筆")

    counts = [len(rows) for rows in usable.values() if rows]
    if counts and min(counts) < 6:
        lines.append(not_applicable_text("可用筆數不足 6"))
        return lines
    if not counts or len(counts) < 2:
        return lines
    if baseline_date is None:
        return lines

    signs = []
    for rows in usable.values():
        window = rows[-6:]
        signs.append(1 if window[-1]["value_num"] >= window[0]["value_num"] else -1)
    lines.append("兩者同向" if signs[0] == signs[1] else "兩者分歧")
    return lines


def _mkt3_range_lines(dataset, start, baseline_date):
    """`44` MKT-3 逐字：副標顯示匯率在 MKT-4 觀察窗內的區間高低兩個值。"""
    if start is None or baseline_date is None:
        return []
    rows = [
        r
        for r in rows_for_key(dataset, "fx_twd_per_usd")
        if start <= r["obs_date"] <= baseline_date and r["value_unit"] == "新臺幣／美元"
    ]
    if not rows:
        # ⚠️ 登記：觀察窗內一筆也沒有時的文案 `44` 沒有寫。照 5.5 的 `算不出來` 模板寫。
        return [not_applicable_text("觀察窗內無任何觀測")]
    values = [r["value_num"] for r in rows]
    return [
        "觀察窗內區間　低 "
        + format_value(min(values), 3)
        + "　高 "
        + format_value(max(values), 3)
    ]


# ───────────────────────── 結論燈 ─────────────────────────


def conclusion_light(cards) -> dict:
    """`44` MKT-0 規則與空狀態逐字。本塊不自取數，只讀三張卡已經算出來的狀態值。"""
    states = [card["_state"] for card in cards]

    # 空狀態先判：三塊皆無資料 → 灰燈 ＋ 一枚重新取數。
    if cards and all(card["_all_missing"] for card in cards):
        return {
            "_tone": "灰",
            "text": "本頁三張卡皆未取到資料",
            "buttons": [_retry_button()],
        }

    if all(state == STATE_OK for state in states):
        return {"_tone": "灰", "text": "三張卡的資料齊", "buttons": []}

    # ⛔ **這一段本輪整段改寫，因為舊寫法有兩處都吃不到 `STATE_UNRANKED`（會當掉）**：
    #   (a) `_STATE_IN_LIGHT_TEXT[worst]` → `KeyError: None`；
    #   (b) `next(card for card in cards if card["_state"] == worst)` → 沒有一張卡
    #       的 `_state` 會等於哨符（三塊各自只有一個狀態時，哨符出在**燈**這一層），
    #       於是 `StopIteration` —— 整頁畫不出來。
    #
    # **改寫的原則：凡 `44` 決定得了的，照 `44`；`44` 沒排的，就不排。**
    #  · **燈色**：`44` :310 把燈色寫成三條**以級為準**的規則（皆 ok → 灰／任一為
    #    `資料未備` **或** `業務例外` → 黃／任一為 `系統錯誤` → 紅）。
    #    ⇒ 燈色**從來不需要那個 tie-break**，它只需要「最高的那一級」。
    #  · **點名哪一張卡**：`44` :310 逐字是「文案**列出**是哪一張卡」——
    #    它要的是「列出」，不是「從同級的幾張裡挑一張」。
    #    ⇒ 本檔改成**把最高那一級的卡全部列出來**。
    # ⚠️ **登記：這是本輪被迫做的一個呈現決定，`44` 沒有寫「同級有好幾張時怎麼辦」。**
    #    取「全部列出」而不是「挑第一張」的理由：挑第一張**就是**本輪正在拆的那種
    #    看不見的先後（那一次是按狀態排，這一次是按卡片在清單裡的位置排）。
    #    **現行三張卡只有一張進最高級時，本函式的輸出與改寫前逐字相同** ——
    #    差別只在同級有好幾張時，舊寫法會默默吞掉其餘幾張。
    #
    # ⚠️ **射程比「拆自創先後」這個框架聽起來大，就地量出來寫明（2026-09-24 稽核指出）**：
    #    窮舉四狀態 × 三張卡 ＝ **64 種組合**，與 `fd5e41b` 逐一對跑，
    #    **本塊文案有變的是 30 種**，而且**不是全部都來自同級**：
    #      · **12 種**是**真的同級**（最高那一級同時有 `資料未備` 與 `業務例外`）；
    #      · **18 種**是**同一個狀態、好幾張卡** —— 舊碼對「哪一個狀態」本來就不含糊，
    #        它只是**默默吞掉了其餘幾張卡的名字**。
    #    ⇒ **本輪在這一塊修掉的是兩件事，不是一件**：一個自創的狀態先後，
    #      以及一個自創的「只報第一張卡」。上面那句「差別只在同級有好幾張時」
    #      **措辭本身沒說錯**（那 18 種確實也是「好幾張」），
    #      但讀的人很容易以為只動到同級那 12 種。**據實寫出數字，免得被低估。**
    top = max(_band(state) for state in states)
    tone = "紅" if top == _BAND[STATE_ERROR] else "黃"
    named = [card for card in cards if _band(card["_state"]) == top]
    return {
        "_tone": tone,
        "text": "；".join(f"{card['title']}：{_light_words(card)}" for card in named),
        "buttons": [],
    }


def _light_words(card) -> str:
    """一張被點名的卡，狀態要寫成哪個（或哪幾個）徽章字面值。

    卡的狀態排得出來 → 一個字面值（本檔既有行為，一字未動）。
    排不出來（這張卡同時有 `資料未備` 與 `業務例外` 的主值）→ **兩個都寫**。
    ⚠️ **兩個都寫不是「兩個都最嚴重」，是「這張卡上這兩件事都真的發生了」** ——
       它描述的是卡上的事實，不是排名。⛔ 不得反過來被讀成一個先後。
    ⚠️ 書寫順序取自 `_UNRANKED_PAIR`（`44` :310 並列兩者時自己的寫法），**不是**嚴重度。
    """
    state = card["_state"]
    if state is not STATE_UNRANKED:
        return _STATE_IN_LIGHT_TEXT[state]
    present = {mv["_state"] for mv in card.get("main_values", [])}
    words = [_STATE_IN_LIGHT_TEXT[s] for s in _UNRANKED_PAIR if s in present]
    # 哨符按定義就是那兩個同時出現；真的沒撈到（例如卡的形狀日後改了）就照實兩個都寫，
    # **不靜默挑一個**。
    return "／".join(words or [_STATE_IN_LIGHT_TEXT[s] for s in _UNRANKED_PAIR])


def _build_light(cards) -> dict:
    light = conclusion_light(cards)
    return {
        "code": "MKT-0",
        "title": BLOCK_TITLES["MKT-0"],
        "_layer": 1,
        "_default_open": True,
        "_tone": light["_tone"],
        "answers": _ANSWERS["MKT-0"],
        "summary_text": "",
        "text": light["text"],
        "main_values": [],  # `44`：這一塊沒有任何數字
        "detail_lines": [],
        "badges": [],
        "buttons": light["buttons"],
    }


# ───────────────────────── 層 3 ─────────────────────────


def _build_mkt4(*, window_days, baseline_date, field_window_days=_UNSET, field_baseline_date=_UNSET):
    """`44` MKT-4：兩枚按鈕並存 —— 套用只重算不寫回、存檔只寫回不重算。

    ⚠️ 兩組值刻意分開，這是 `44` 本輪擴寫的重點：
    `window_days`／`baseline_date` 是**已套用**的那一組（驅動三張核心卡）；
    `field_*` 是**欄位當下**的值（決定存檔能不能按、決定欄位下方的說明）。
    合成同一組會讓「填了值但還沒按套用」時存檔誤停用 —— 那等於把兩枚按鈕綁回一枚。
    """
    if field_window_days is _UNSET:
        field_window_days = window_days
    if field_baseline_date is _UNSET:
        field_baseline_date = baseline_date

    detail_lines = []
    both_empty = field_window_days is None and field_baseline_date is None
    invalid = field_window_days is not None and (
        not isinstance(field_window_days, int) or field_window_days <= 0
    )
    applied_invalid = window_days is not None and (
        not isinstance(window_days, int) or window_days <= 0
    )
    applied_empty = window_days is None and baseline_date is None

    if invalid:
        detail_lines.append("日數為正整數")

    inputs = [
        {
            "_input": True,
            "_default": None,  # `44` 逐字：欄位無預設值
            "_value": field_window_days,
            "name": "days_calendar",
            "label": "觀察窗長度（days_calendar）",
            "placeholder": "請輸入日數（日曆日）",
        },
        {
            "_input": True,
            "_default": None,
            "_value": field_baseline_date,
            "name": "mkt_baseline_date",
            "label": "比較基準日",
            "placeholder": "請選擇日期",
        },
    ]

    apply_button = _button("套用", "套用", writes=set())
    save_button = _button(
        "存檔",
        "存檔",
        writes={"user_setting"},  # `44` 5.3：存檔類只寫 user_setting
        enabled=not both_empty and not invalid,
        disabled_reason="兩個欄位皆未填" if both_empty else ("日數為正整數" if invalid else ""),
    )

    if both_empty:
        summary = "尚未設定觀察窗與比較基準日"
    elif invalid:
        summary = "輸入尚未通過檢查"
    else:
        summary = f"{field_window_days} 日曆日，基準日 {field_baseline_date}"

    return {
        "code": "MKT-4",
        "title": BLOCK_TITLES["MKT-4"],
        "_layer": 3,
        "_default_open": False,
        "_applied": not applied_invalid and not applied_empty,
        "_saved": False,  # 本輪不真的寫檔；存檔的寫入對象是 user_setting 的替身
        "answers": _ANSWERS["MKT-4"],
        "summary_text": summary,
        "main_values": [],
        "detail_lines": detail_lines,
        "badges": [_redline_badge("G3†")],
        "buttons": [apply_button, save_button],
        "inputs": inputs,
    }


def _build_mkt5(dataset, selected_keys):
    """`44` MKT-5：清單以字面值排列、勾選上限 6、達上限其餘停用並附原因。

    ⚠️ 登記：本塊**沒有寫回路徑** —— `44` MKT-4 本輪補宣告了寫入對象
    （體例同 EXP-5：有寫入動作的塊在來源欄寫出寫入對象），**MKT-5 的來源欄沒有補**；
    `47` Q-08 亦登記本頁勾選無處可存。故本塊做成**唯讀勾選**，
    不自行補一枚存檔鈕（那會是發明規格）。
    """
    selected = set(selected_keys or ())
    at_cap = len(selected) >= 6
    keys = all_keys(dataset)
    have_rows = {r["indicator_key"] for r in dataset.get("rows", [])}

    items = []
    for key in keys:
        checked = key in selected
        enabled = checked or not at_cap
        item = {
            "_input": True,
            "_default": None,  # 一個也沒有預先勾
            "_value": checked,
            "_enabled": enabled,
            "_readonly": True,
            "name": key,
            "label": key,
            "disabled_reason": "" if enabled else "已達勾選上限 6，請先取消一項",
            "badges": [] if key in have_rows else [_status_badge("資料未備")],
        }
        items.append(item)

    if selected_keys is None:
        summary = "尚未設定，依 `44` 只讀不寫"
    elif not selected:
        summary = "尚未選定任何指標"
    else:
        summary = f"已勾選 {len(selected)} ／ 上限 6"

    detail_lines = [
        "本塊在 `44` 的來源欄只宣告讀、未宣告寫入對象，故此處為唯讀勾選。",
    ]

    return {
        "code": "MKT-5",
        "title": BLOCK_TITLES["MKT-5"],
        "_layer": 3,
        "_default_open": False,
        "_readonly": True,
        "_items": items,
        "answers": _ANSWERS["MKT-5"],
        "summary_text": summary,
        "main_values": [],
        "detail_lines": detail_lines,
        "badges": [_redline_badge("G3†")],
        "buttons": [],  # 唯讀：本塊沒有任何按鈕
        "inputs": items,
    }


# ───────────────────────── 層 4 ─────────────────────────


def _build_mkt6(dataset):
    """`44` MKT-6：一列一筆觀測，欄位依宣告順序固定，不依數值排序。"""
    rows = list(dataset.get("rows", []))
    table_rows = []
    blank_notes = []
    for row in rows:
        cells = {column: row.get(column) for column in MKT6_COLUMNS}
        for column in MKT6_COLUMNS:
            if cells[column] is None or cells[column] == "":
                cells[column] = "⬜"
                blank_notes.append(f"{row.get('indicator_key')} / {row.get('obs_date')}")
        cells["_row_badge"] = "修正過" if row.get("is_revised") else ""
        table_rows.append(cells)

    detail_lines = []
    if not rows:
        detail_lines.append(empty_source_text(["market_indicator"]))
        detail_lines.append("尚無任何觀測")
    for note in blank_notes:
        detail_lines.append(f"該筆有空格：{note}")

    latest = max((r["obs_date"] for r in rows), default=None)
    summary = "尚無任何觀測" if not rows else f"共 {len(rows)} 筆觀測，最近一筆 {latest}"

    return {
        "code": "MKT-6",
        "title": BLOCK_TITLES["MKT-6"],
        "_layer": 4,
        "_default_open": False,
        "_columns": MKT6_COLUMNS,
        "_rows": table_rows,
        "column_labels": [MKT6_COLUMN_LABELS[c] for c in MKT6_COLUMNS],
        "answers": _ANSWERS["MKT-6"],
        "summary_text": summary,
        "main_values": [],
        "detail_lines": detail_lines,
        "badges": [],
        "buttons": [],
    }


def _build_mkt7(dataset):
    """`44` MKT-7：一列一個 indicator_key，取各組最近一筆。"""
    keys = all_keys(dataset)
    rows_out = []
    worst_delay = None
    for key in keys:
        rows = rows_for_key(dataset, key)
        if not rows:
            rows_out.append(
                {
                    "indicator_key": key,
                    "obs_text": "⬜",
                    "fetched_text": "⬜",
                    "tier_text": "⬜",
                    "delay_text": "⬜",
                    "badges": [_status_badge("資料未備")],
                }
            )
            continue
        latest = rows[-1]
        delay = delay_days(latest["obs_date"], latest["fetched_at"])
        if delay < 0:
            delay_text = not_applicable_text("取得時間早於觀測日")
        else:
            delay_text = f"{delay} 日"
            worst_delay = delay if worst_delay is None else max(worst_delay, delay)
        rows_out.append(
            {
                "indicator_key": key,
                "obs_text": latest["obs_date"],
                "fetched_text": latest["fetched_at"],
                "tier_text": latest["source_tier"],
                "delay_text": delay_text,
                "badges": [],
            }
        )

    has_any = any(dataset.get("rows", []))
    summary = (
        f"{len(keys)} 個指標鍵，最舊一筆延遲 {worst_delay} 日"
        if has_any and worst_delay is not None
        else "尚無任何指標鍵"
    )

    return {
        "code": "MKT-7",
        "title": BLOCK_TITLES["MKT-7"],
        "_layer": 4,
        "_default_open": False,
        "_rows": rows_out,
        "column_labels": ["指標鍵", "最近觀測日", "最近取得時間", "來源層級", "延遲日數"],
        "answers": _ANSWERS["MKT-7"],
        "summary_text": summary,
        "main_values": [],
        # `44` MKT-7 逐字：顯示時轉當地時區並在表頭註明時區字面值。
        # 本輪不做時區切換器（`47` Q-10：本頁無任何塊定義該元件，八類按鈕亦無「切換」類），
        # 故表頭註明的就是存放時區本身。
        "detail_lines": [f"時間以 {STORAGE_TIMEZONE} 顯示"],
        "badges": [],
        "buttons": [],
    }


# ───────────────────────── 組裝 ─────────────────────────


def build_page_model(
    dataset: dict,
    *,
    window_days: int | None = None,
    baseline_date: str | None = None,
    selected_keys=None,
    viewport_width: int = 1280,
    field_window_days=_UNSET,
    field_baseline_date=_UNSET,
) -> dict:
    """把假資料 ＋ 使用者輸入組成一份純資料模型。page.py 只負責把它畫出來。"""
    cards = [
        _build_card(
            code,
            dataset,
            window_days=window_days,
            baseline_date=baseline_date,
            selected_keys=selected_keys,
        )
        for code in ("MKT-1", "MKT-2", "MKT-3")
    ]
    blocks = [_build_light(cards)]
    blocks.extend(cards)
    blocks.append(
        _build_mkt4(
            window_days=window_days,
            baseline_date=baseline_date,
            field_window_days=field_window_days,
            field_baseline_date=field_baseline_date,
        )
    )
    blocks.append(_build_mkt5(dataset, selected_keys))
    blocks.append(_build_mkt6(dataset))
    blocks.append(_build_mkt7(dataset))

    return {
        "title": "市場總覽",
        "answers": "現在的市場環境，和我上次看的時候比，變了哪裡",
        "_viewport_width": viewport_width,
        "_columns": columns_for_width(viewport_width),
        "blocks": blocks,
        # `44` 3.0 ／ `47` 4.1：本頁不負責什麼，頁尾三行指路。
        "footer_lines": [
            "這個問題在持倉體檢",
            "這個問題在標的探索",
            "這個問題在資產配置",
            "本頁不對任何標的下結論；觀察窗與指標清單由使用者輸入",
        ],
        "footer_badges": [_redline_badge("G3†")],
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


def collect_ui_strings(model: dict) -> list:
    """把介面全頁文字抓成一份清單（`44` 1.2 節判準）。

    刻意連機器用的鍵一起走過 —— 寧可多抓，不可漏抓。
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
