# -*- coding: utf-8 -*-
"""設定與診斷**正式模式**才有的畫面調整（純函式；不 import streamlit、不 import 舊樹、不 import fixtures）。

依據：客戶 2026-09-26 核准的文字線框草稿「設定與診斷（SET）正式模式」第二版（含第 10、12 節裁示）。
全部只在正式模式生效；示範模式（`ui_v2/app_set.py`）不經過本檔，一個字都不變。

本檔做三件事，都不改 `logic.py` 的任何判定（草稿第 8 節：「本稿只加字，不改判定」）：
1. **拿掉示範字樣**（草稿 ✂1～✂4）：頁首副標在 `page.py` 處理；✂2～✂4 在 `apply_live_notes`。
2. **加上新文案**（草稿 ★1～★10）：每一句逐字照草稿，集中在下方常數；改字要先回草稿（`CLAUDE.md` §-1.5.4）。
3. **按鈕的正式行為**：「存檔」與「重新取數」的停用原因、執行中、結果行（草稿第 6 節）。

「尚未接上」一律由 L2 交出的旗標決定（草稿 B7；`notes["pending_tables"]` 等），本檔不自己猜。
遮蔽記號由 L2 交出（`notes["mask_token"]`），本檔不另寫一份。

`notes` 的形狀見 `ui_v2/set/source.py::load_live` 的 docstring。
"""

from __future__ import annotations

import copy
import math

from .. import plain
from . import logic

# ───────────────────────── 草稿文案（逐字；出處見各行註解） ─────────────────────────

MASKED_NOTE = "已遮蔽憑證"  # ★5，ACCEPTANCE.md 7.4 逐字
# ~~TEXT_PENDING_NAV_DIVIDEND = "淨值、配息尚未接取數來源"  # ★1，客戶 2026-09-26 定稿~~
# → 2026-10-09 換句（狀態更新，不是漏刪）：客戶裁示 Q1 不存 NAV、即時取得，「淨值尚未接」自此為假；
#   新句為客戶 2026-10-02 核准的 B 句，2026-10-09 再核准（`docs/v2/53_nav_source_plan.md` §7 第 1 列）。
TEXT_PENDING_DIVIDEND = "配息尚未接取數來源；淨值即時取得"  # ★1（SET-0），配息仍待接就印、不再看 nav
TEXT_REASON_KIND_PENDING = "原因：這一類的存放處尚未接上，暫無取得時間"  # ★2（SET-1）
TEXT_REASON_TIER_PENDING = "原因：這一層級的取數尚未接上"  # ★2（SET-2）
# ~~TEXT_LOG_SCOPE = "取數紀錄只記從 set 頁觸發的取數；市場總覽頁開頁時自己的取數不記在這裡。"  # ★3~~
# → 客戶 2026-10-19 裁示（`docs/DECISIONS.md` `DEC-2026-10-19-04`，BL-0250 批次 1；有意識的政策變更，不是漏刪）：
#   舊句在 `SET-0`、`SET-2`、`SET-6` 各印一次（同一句全頁三次），且「set 頁」是工程字樣。只留 `SET-6`（取數紀錄那一塊）一處，
#   改寫成下面這一句。舊句的用意（取數紀錄的射程只到本頁按的那幾次）完全保留；被權衡掉的是重複與工程字樣。
TEXT_LOG_SCOPE = "這裡只記在本頁按「重新取數」的結果；其他頁開頁時的取數不在這裡"  # ★3（只在 SET-6）
# ~~「set 頁」~~ → 「本頁」（同上裁示；只換這兩個字，句意不動）。
# ~~TEXT_MI_TIME_SCOPE = "這個時間是本頁最近一次取數存入的時間，不是市場總覽頁畫面上那一份的時間"~~
# → 2026-10-26 客戶裁示第 6 節（Google Sheet 零寫入；有意識的更正，不是漏刪）：本次工作階段的重新取數不再「存入」，
#   刪掉「存入」兩字，其餘一字未改。
TEXT_MI_TIME_SCOPE = "這個時間是本頁最近一次取數的時間，不是市場與趨勢頁畫面上那一份的時間"  # ★4
# 2026-10-26 裁示第 6 節：該塊含本次工作階段重新取數的結果（記憶體，未存入試算表）時，說明行加這一句標來源。
TEXT_RUNTIME_SOURCE = "含本次工作階段取數，未存入試算表"
# 2026-10-26 獨立稽核必修 1：本次資料在、但試算表那一份讀取失敗時，不說「含」（那會暗示試算表那份也在）。
TEXT_RUNTIME_SOURCE_SHEET_FAILED = "本次工作階段取數，未存入試算表；試算表讀取失敗"


def runtime_source_line(runtime: dict, errors: dict, tables) -> str | None:
    """該塊的標來源句：`tables` 裡有一張含本次工作階段資料才標；其中有一張試算表讀取失敗 → 失敗那一句。"""
    used = [t for t in tables if runtime.get(t)]
    if not used:
        return None
    return TEXT_RUNTIME_SOURCE_SHEET_FAILED if any(errors.get(t) for t in tables) else TEXT_RUNTIME_SOURCE
# SET-1 淨值列有時間時才印（客戶 2026-10-09 核准，`docs/v2/53_nav_source_plan.md` §7 第 4 列）。
TEXT_NAV_TIME_SCOPE = "這個時間是本頁最近一次重新取數淨值的時間，不是持倉頁畫面上那一份的時間"
# 客戶 2026-10-19 裁示（同上）：`SET-4` 某鍵沒有任何畫面用到時那一行。~~「改這個鍵會影響：44 各塊的來源欄沒有宣告用它」~~
# （`logic._used_by_text`，示範模式照舊）→ 正式模式寫這一句。
TEXT_USED_BY_NONE = "目前沒有畫面用到這個設定"
_USED_BY_NONE_DEMO = "改這個鍵會影響：44 各塊的來源欄沒有宣告用它"
# 客戶 2026-10-19 裁示（同上）：`SET-3`／`SET-4` 收合摘要不再列原始鍵名，只寫「N 個設定，M 個未設定」。
TEXT_SET4_SUMMARY = "{n} 個設定，{unset} 個未設定"
TEXT_SET4_SUMMARY_ALL_SET = "{n} 個設定，皆已設定"
# 客戶 2026-10-19 裁示（同上）：一般畫面上「服務帳戶（google_service_account）」寫成「Google 服務帳戶」；
# 讀取情境的「⛔ 未設定試算表 ID，暫停寫入」寫成「⛔ 尚未設定：試算表 ID」（存檔按鈕的停用原因屬寫入情境，照舊）。
# `SET-2`、`SET-6` 照印原文（44 `SET-2` 規則欄、第七節第三小節之七其二第 2 條），不換。
SERVICE_ACCOUNT_WORDS = (
    ("未設定服務帳戶（google_service_account）", "未設定 Google 服務帳戶"),
    ("服務帳戶（google_service_account）", "Google 服務帳戶"),
)
TEXT_NO_SHEET_ID_READ = "尚未設定：試算表 ID"
_RAW_TEXT_CODES = ("SET-2", "SET-6", "SET-7")

# ───────────── BL-0250 批次 3-A（客戶 2026-10-19 批次 3 裁示；44 第七節第三小節之十二） ─────────────
# 第 3 點：缺 Google 服務帳戶各處統一「⛔ 尚未設定：Google 服務帳戶」。照印原文的 `SET-2`／`SET-6` 內文照印原文（只拿掉
# 本頁加的「取數失敗：」字首，同「⛔ 未設定試算表 ID，暫停寫入」那一句的既有體例）；結論燈照舊（`DEC-2026-10-18-01` C1，
# 待裁示 (3) 原本就只問燈以外各處）。停用原因照線框第六版待裁示 (3) 寫的那兩句。
TEXT_SA_NOT_CONFIGURED = "尚未設定：Google 服務帳戶"
TEXT_SA_SAVE_REASON = "尚未設定 Google 服務帳戶，暫停寫入"
TEXT_SA_REFETCH_REASON = "尚未設定 Google 服務帳戶，暫停取數"
_SA_RAW_LINE = f"{logic.FETCH_FAIL_GLYPH} {plain.MSG_NO_SERVICE_ACCOUNT}"   # `_fail_map` 給缺服務帳戶的那一句（中間形；`SET-2`／`SET-6` 換回原文，其餘換統一句）
# 第 2 點：讀取情境的收合標題（`SET-4` 參數編輯、`SET-6` 取數紀錄）不再寫「取數失敗：user_setting／fetch_log」。
# 成因是尚未設定 → 「⛔ 尚未設定：<哪一項>」；設定試算表冷卻中 → 卡上那一句暫停句；其餘真的讀取失敗 → 取數失敗（⛔）。
TEXT_TITLE_FETCH_FAILED = f"{logic.FETCH_FAIL_GLYPH} {logic.TEXT_FETCH_FAILED}"
# 第 2 點（set|stale 那一種）：一筆取數紀錄裡**每一則**訊息都是「尚未設定」那一族時，那一筆的結果寫「⛔ 尚未設定：<哪一項>」；
# 只要混有任何一則別的訊息，照寫取數失敗（⛔）。訊息原文照印；`SET-0` 的燈色與「算一個失敗來源」的判定照舊（只改字）。
# U7（b）（c）：`SET-2`／`SET-6` 的結果欄不寫英文原值（`ok`／`failed`），原值移到進階診斷。`ok` 的中文借本頁重新取數結果行
# 已在用的「取數完成」（`TEXT_DONE`），不另造說法（實作組判讀，可推翻）。
TEXT_RESULT_OK = "取數完成"
TEXT_RESULT_FAILED = f"{logic.FETCH_FAIL_GLYPH} {logic.TEXT_FETCH_FAILED}"
RESULT_OK, RESULT_FAILED, RESULT_UNCONFIGURED = "ok", "failed", "unconfigured"
# U7（a）：`SET-3` 表頭與列上用中文；資料型態的中文（44 第四節第五小節六種 value_kind；線框第六版 6.4 (a)）。
SET3_COLUMN_LABELS = ["設定項目", "目前值", "資料型態", f"最後修改時間（{logic.DISPLAY_TZ_LABEL}）"]
KIND_NAMES = {"list": "清單", "rules": "條件", "date": "日期", "int": "數字", "float": "數字", "ratio": "數字"}
TEXT_SET4_PER_KEY_PLAIN = "每個設定的輸入方式依它的資料型態決定。"
# U7（c）：`SET-6` 不列紀錄編號欄（紀錄編號只在進階診斷）；排序說明不寫欄名。
SET6_COLUMN_LABELS = ["來源層級", f"開始（{logic.DISPLAY_TZ_LABEL}）", "耗時（秒）", "結果", "取回列數", "訊息"]
TEXT_SET6_ORDER_PLAIN = "由新到舊排列。"
# U7（d）＋待裁示 (5a) 第一案（客戶 2026-10-19 裁示第 5 點第一項）：欄位對照表留在原位、改標題、預設收合。
SET7_TITLE = "欄位對照（進階）"
SET7_SUMMARY = "每一欄資料用在哪一塊"

# ★6（草稿 6.1）
TEXT_SAVED = "已存檔"  # 客戶 2026-09-26 定稿
TEXT_SAVE_MAYBE_WRITTEN = "未存檔。這次可能其實已寫入，請先重新整理本頁確認，再決定要不要重存"
TEXT_HINT_403 = "服務帳戶可能只有檢視權限，需要編輯者"
TEXT_HINT_404 = "請確認試算表 ID，以及已分享給服務帳戶"  # 後面接一個空格與 client_email（有才接）
TEXT_NO_SHEET_ID = "未設定試算表 ID，暫停寫入"  # 客戶 2026-09-26 定稿（B11：非燈位置全站統一這一句）
TEXT_NO_SERVICE_ACCOUNT = "未設定服務帳戶"  # `50` 第 8 節
TEXT_SHEET_COOLING = "設定試算表暫停重試，約剩 {n} 秒"  # 草稿擬（B2：統一用「約剩」）

# ★7
TEXT_SETTING_PENDING = "設定已存，{codes} 接上後生效"  # 客戶 2026-09-26 定稿格式

# ★8（草稿 6.2）
TEXT_TIER_NOT_WIRED = "這一層級的取數尚未接上"
TEXT_RUNNING = "取數中：{tier}"
TEXT_DONE = "取數完成：{tier}，取回 {n} 列；結果記在取數紀錄（層 4）"
# ~~TEXT_DONE_NOT_LOGGED = "取數完成：{tier}，取回 {n} 列"~~（取數紀錄寫不進去時只印前半）
# ~~TEXT_LOG_WRITE_FAILED = "⛔ 取數紀錄寫入失敗：{message}"~~
# → 2026-10-26 客戶裁示第 6 節（有意識的行為變更，不是漏刪）：取數紀錄改記在本次工作階段（記憶體），
#   不再寫試算表，「取數紀錄寫入失敗」不可能發生 —— 兩句與對應分支一併移除。
TEXT_DONE_EMPTY = "取數完成：{tier}，" + logic.TEXT_EMPTY_RESPONSE
# ~~TEXT_SET5_NOTE = "目前只有市場指標可以重新取數；取回的列存進設定試算表，市場總覽頁不會因此重新整理。"~~
# → 2026-10-09 換句（狀態更新，不是漏刪；客戶核准，`docs/v2/53_nav_source_plan.md` §7 第 9 列）。
# ~~TEXT_SET5_NOTE = ("目前市場指標與淨值可以重新取數。市場指標取回的列存進設定試算表，市場總覽頁不會因此重新整理；"
#                   "淨值只取持倉基金，除了記一筆取數紀錄，不寫入任何表。")~~
# → 2026-10-26 客戶裁示第 6 節（Google Sheet 零寫入；有意識的更正，不是漏刪）：舊句「存進設定試算表」不再為真。
TEXT_SET5_NOTE = ("目前市場指標與淨值可以重新取數。結果與取數紀錄只留在本次工作階段，不存入試算表；"
                  "市場與趨勢頁不會因此重新整理；淨值只取持倉基金。")

# ★9（草稿 ★9 細項；`50` 5.2／5.3／7.1／第 8 節，🟡 統一改成本頁的 ⚠，草稿 B3）
TEXT_HEADER_MISMATCH = "⛔ 標頭與規格不符：{tab}"
TEXT_HEADER_SPEC = "規格：{columns}"
TEXT_HEADER_SHEET = "試算表：{columns}"
TEXT_BAD_ROWS = "⚠ {n} 列格式不符，未採用"
TEXT_PK_CONFLICT = "⚠ 主鍵矛盾 {n} 組，未採用"
TEXT_REVISED_MISMATCH = "⚠ is_revised 與重算不符 {n} 列"
TEXT_DUPLICATE_LOG = "⚠ 重複紀錄 {n} 筆"

# `SET-0` 說明行（44 `SET-0` 來源欄；客戶 2026-10-18 裁示 S4，`DEC-2026-10-18-01`）：正式模式補明第三個輸入；
# 示範模式那一行（`logic._build_set0` 的 `detail_lines`）照舊。
TEXT_SET0_INPUTS_DEMO = logic.TEXT_LAMP_DATA_ONLY + "。本燈只讀 SET-1 的逾期筆數與 SET-2 的失敗來源數。"
TEXT_SET0_INPUTS = logic.TEXT_LAMP_DATA_ONLY + "。本燈讀三個輸入：SET-1 的逾期筆數、SET-2 的失敗來源數、設定試算表是否已設定。"

# 存檔失敗但「根本沒寫」的錯誤碼：這些不印「可能其實已寫入」那一行（2026-09-26 總管裁示）。
_NOT_WRITTEN_CODES = ("cooling", "not_configured", "no_service_account", "header_mismatch")

# ★10
TEXT_TITLE = "設定試算表：{title}"
TEXT_TITLE_FAILED = "⛔ 讀不到試算表名稱：{message}"

# 客戶 2026-09-26 已核准的市場總覽正式入口文案（草稿 6.2：「mkt 已核准文案，逐字沿用」）。
# 本套件不 import ui_v2.mkt（見 `__init__.py`），由 tests/ui_v2/test_set_live_logic.py 與 mkt 那一份逐字比對。
TEXT_SOURCE_COOLING = "來源冷卻中：{source}，約剩 {n} 秒"
TEXT_SOURCE_COOLING_MORE = "，另有 {n} 個來源冷卻中"

# 示範模式才有、正式模式要拿掉的字樣（草稿 ✂2～✂4）。
_DEMO_LINES = (
    logic.HINT_NOTE,
    "⚠ 本頁沒有後端：「存檔」按得下去，但不寫任何東西。",
    "⚠ 本頁沒有後端：「重新取數」按得下去，但不取數、不寫 fetch_log，也不演執行中那一態。",
)

# `SET-1` 資料類 → 表；`SET-2` 層級 → 表（★2 判斷「尚未接上」用）。
_KIND_TABLE = dict(logic.KIND_TABLES)
_TIER_TABLE = {"淨值": "nav", "配息": "dividend", "市場指標": "market_indicator", "其他": None}
# `notes["source_cooldowns"]` 是哪一層的來源（`source.load_live` 放的是 `market_indicator.source_cooldowns()`）。
# 其他層沒有對應的冷卻清單 → 不印冷卻原因（2026-10-09 總管裁示：不自創新句）。
_COOLDOWN_TIER = "市場指標"

# 哪一塊讀哪一張分頁（★9 標頭不符、格式不符出在哪；草稿 ★9「以讀到該分頁的塊為準」）。
_BLOCKS_READING = {
    "user_setting": ("SET-1", "SET-3", "SET-4", "SET-6"),
    "market_indicator": ("SET-1",),
    "fetch_log": ("SET-2", "SET-6"),
}


def _node(text, tone="中性") -> dict:
    return {"text": text, "_tone": tone}


def _masked(text, token) -> bool:
    return bool(token) and isinstance(text, str) and token in text


def seconds_left(remaining_sec) -> int:
    return math.ceil(remaining_sec or 0)


def sheet_cooling_text(remaining_sec) -> str:
    return TEXT_SHEET_COOLING.format(n=seconds_left(remaining_sec))


def cooldown_reason(cooldowns):
    """列出剩餘秒數最長的那一個來源，再加一句另有幾個；沒有冷卻中的來源回 None（同 mkt 已核准寫法）。"""
    live = [c for c in cooldowns or () if c.get("remaining_sec", 0) > 0]
    if not live:
        return None
    top = max(live, key=lambda c: c["remaining_sec"])
    text = TEXT_SOURCE_COOLING.format(source=top["source"], n=math.ceil(top["remaining_sec"]))
    others = len(live) - 1
    if others:
        text += TEXT_SOURCE_COOLING_MORE.format(n=others)
    return text


def sheet_configured(notes) -> bool:
    """設定試算表有沒有設定（44 `SET-0` 來源欄第二輪擴寫的那一個輸入；之八其三 (c-1)）。
    讀寫入閘門（`notes["gate"]`，不打上游）：狀態為 `not_configured` ⇒ 沒設。缺鍵就 `KeyError`，不猜。"""
    return notes["gate"]["state"] != "not_configured"


def service_account_configured(notes) -> bool:
    """服務帳戶有沒有設定（客戶 2026-10-18 裁示 C1／S1，`DEC-2026-10-18-01`）。只在設定試算表未設定時才需要
    （寫入閘門先判 ID，ID 沒設時閘門看不到服務帳戶）：閘門不是 `not_configured` → 回 True（閘門已經把缺服務帳戶判成
    `no_service_account`，那一支照 44 字面是 ⛔，不經本函式）。`not_configured` 時讀 `notes["service_account"]`，缺鍵就 `KeyError`，不猜。"""
    if notes["gate"]["state"] != "not_configured":
        return True
    return bool(notes["service_account"]["configured"])


def gate_reason(gate):
    """寫入閘門 → 停用原因（None＝可寫）。草稿 6.1／6.2 缺設定與設定試算表冷卻中那幾列。"""
    state = (gate or {}).get("state")
    if state == "ok":
        return None
    if state == "not_configured":
        return TEXT_NO_SHEET_ID
    if state == "no_service_account":
        # ~~`TEXT_NO_SERVICE_ACCOUNT`（「未設定服務帳戶」，`50` 第 8 節）~~ → BL-0250 批次 3-A（客戶 2026-10-19 批次 3 裁示第 3 點；
        # 有意識的政策變更，不是漏刪）。舊句的用意（缺服務帳戶所以暫停）照舊；被權衡掉的是它沒說是 Google 的、與其他處說法不一。
        return TEXT_SA_SAVE_REASON
    if state == "cooling":
        return sheet_cooling_text(gate.get("remaining_sec"))
    raise ValueError(f"未知的寫入閘門狀態 {state!r}")


# ───────────────────────── 按鈕 ─────────────────────────


def save_button(notes) -> dict:
    """SET-4「存檔」（草稿 6.1）：缺設定或設定試算表冷卻中 → 停用並寫原因；其餘可按。"""
    reason = gate_reason(notes["gate"])
    return logic._button(logic.TEXT_SAVE, "存檔", enabled=reason is None, disabled_reason=reason or "")


def refetch_button(picked, notes, *, running=False) -> dict:
    """SET-5「重新取數」（草稿 6.2）。判定順序：未選 → 層級未接上 → 缺設定 → 來源冷卻（只看市場指標層，見 `_COOLDOWN_TIER`）→ 設定試算表冷卻。"""
    if picked is not None and picked not in logic.TIERS:
        raise ValueError(f"來源層級 {picked!r} 不在 `44` 第四節那四個之內")
    if running:
        reason = TEXT_RUNNING.format(tier=picked)
    elif picked is None:
        reason = logic.TEXT_NO_TIER_PICKED
    elif picked not in notes["wired_tiers"]:
        reason = TEXT_TIER_NOT_WIRED
    else:
        gate = notes["gate"]
        reason = None
        if gate.get("state") == "no_service_account":
            reason = TEXT_SA_REFETCH_REASON   # BL-0250 批次 3-A：取數那一枚寫「暫停取數」
        elif gate.get("state") == "not_configured":
            reason = gate_reason(gate)
        if reason is None and picked == _COOLDOWN_TIER:
            reason = cooldown_reason(notes.get("source_cooldowns"))
        if reason is None and gate.get("state") == "cooling":
            reason = gate_reason(gate)
    return logic._button(logic.TEXT_REFETCH, "取數", enabled=reason is None, disabled_reason=reason or "")


def refetch_result_lines(result, mask_token) -> list:
    """重新取數的結果行（草稿 6.2 成功／回空／失敗）。回 `[node, ...]`。

    `result` 見 `source.refetch`：分工照 `services/v2_tables/settings_store.py` 的 docstring ——
    - `log_message`：與取數紀錄 `message` 的字串逐字相同（`44` SET-5 判準）；
    - `masked_errors`：已遮蔽的真錯誤；沒有 `log_message` 時以它組失敗行；
    - `empty`：來源回空、原因未提供（`44` SET-5 的回空，不是失敗）。
    ~~`message`：設定試算表本身的錯誤（寫不進取數紀錄），`stage` 為 `fetch_log_open`／`fetch_log` 時上畫面~~ →
    2026-10-26 客戶裁示第 6 節（有意識的行為變更，不是漏刪）：取數紀錄改記在本次工作階段，不寫試算表，
    「取數紀錄寫入失敗」那一行與它的分支不可能發生，已移除。
    """
    tier = result["tier"]
    failure = result.get("log_message")
    if failure is None and result.get("masked_errors"):
        failure = "\n".join(f"{k}: {v}" for k, v in result["masked_errors"].items())
    lines = []
    if failure:
        lines.append(_node(logic.fetch_failed_text(failure), "紅"))
        if _masked(failure, mask_token):
            lines.append(_node(MASKED_NOTE, "灰"))
    elif result.get("empty") and not result.get("fetched"):
        lines.append(_node(TEXT_DONE_EMPTY.format(tier=tier)))
    else:
        lines.append(_node(TEXT_DONE.format(tier=tier, n=result.get("fetched", 0))))
    return lines


def changed_settings(inputs, current_values) -> list:
    """「存檔」要寫哪幾鍵：輸入欄當下值與已存值不同的鍵（`44` SET-4：被編輯的那個鍵）。

    `inputs` 是 SET-4 模型的 `inputs`；`current_values` 是 `{鍵: 輸入欄當下字串}`。
    輸入欄清空 → `setting_value` 為 None（`44`：清除後是空值，不是空字串；清除＝清空後存檔）。
    回 `[(鍵, 值或 None, value_kind), ...]`，照 SET-4 的鍵順序。
    """
    out = []
    for field in inputs:
        key = field["name"]
        if key not in current_values:
            continue
        raw = current_values[key]
        # 只有空白或留空 → 清除這個鍵；其餘照原值比對、照原值寫（前後帶空白由型別檢查擋下，不靜默去掉）。
        value = None if raw is None or raw.strip() == "" else raw
        if value != field["_value"]:
            out.append((key, value, field["_kind"]))
    return out


def dataset_with_save_results(dataset, results):
    """把上一次「存檔」的結果疊進 dataset（不改呼叫端那一份）：沒存成的鍵，輸入欄畫當下輸入
    （`44` SET-4：該欄的當下輸入留在畫面上不清掉）；寫入失敗的鍵另帶失敗訊息（已遮蔽）。
    型別不符的鍵只放當下輸入 —— `logic` 會依它畫出型別說明（`44`：欄位下方顯示型別說明，不存檔）。"""
    if not results:
        return dataset
    out = dict(dataset)
    out["save_inputs"] = dict(dataset.get("save_inputs") or {})
    out["save_errors"] = dict(dataset.get("save_errors") or {})
    for key, result in results.items():
        if result["status"] == "saved":
            continue
        out["save_inputs"][key] = result.get("attempted")
        if result["status"] in ("failed", "read_only"):      # read_only：唯讀開關擋下，沿用失敗管道顯示原因
            out["save_errors"][key] = result["message"]
    return out


# ───────────────────────── 模型調整 ─────────────────────────


def _fail_map(dataset, notes) -> dict:
    """各表讀取失敗的畫面字串 → (正式模式顯示的字串, 下接的行, 色調)。燈（SET-0）不走這裡（照 `44` 字面）。"""
    token = notes["mask_token"]
    out = {}
    for table, message in (dataset.get("errors") or {}).items():
        info = notes["table_errors"].get(table, {})
        raw = logic.fetch_failed_text(message)
        extra = []
        if info.get("code") in ("not_configured", "no_service_account"):
            # B11：非燈位置統一「⛔ 未設定試算表 ID，暫停寫入」。BL-0250 批次 3-A：缺服務帳戶在 `SET-1`／`SET-3`／`SET-4` 先寫成
            # 這一形（`_SA_RAW_LINE`），再由 `_plain_set_words` 換成「⛔ 尚未設定：Google 服務帳戶」；照印原文的 `SET-2`／`SET-6`
            # 由 `_sa_raw_restore` 換回原文（客戶核准的待裁示 (3)「除來源健康卡與取數紀錄（照印原文）外」；同批稽核回修）。
            shown = f"{logic.FETCH_FAIL_GLYPH} {message}"
        elif info.get("code") == "header_mismatch":
            shown = TEXT_HEADER_MISMATCH.format(tab=info["tab"])
            extra.append(_node(TEXT_HEADER_SPEC.format(columns="、".join(info["expected"])), "紅"))
            sheet_line = TEXT_HEADER_SHEET.format(columns="、".join(info["actual"]))
            extra.append(_node(sheet_line, "紅"))
            if _masked(sheet_line, token):
                extra.append(_node(MASKED_NOTE, "灰"))
        else:
            shown = raw
        if _masked(shown, token):
            extra.insert(0, _node(MASKED_NOTE, "灰"))
        # 幾張表同一句失敗（例如同一次冷卻）時字串相同，取哪一張的轉換都一樣。
        out.setdefault(raw, (shown, extra, table))
    return out


def _decorate_placeholder(node, fail_map, notes, code, dataset=None):
    if not node or node.get("text") not in fail_map:
        return node
    shown, extra, _table = fail_map[node["text"]]
    info = notes["table_errors"].get("user_setting", {})
    setting_error = (dataset or {}).get("errors", {}).get("user_setting")
    if code in ("SET-3", "SET-4") and info.get("code") == "cooling" \
            and node["text"] == logic.fetch_failed_text(setting_error):
        # 草稿 6.1 末注：冷卻期間讀設定也被跳過；SET-3／SET-4 的值格改顯示暫停（黃，B4），不是 ⬜ 未設定。
        return {**node, "text": f"{logic.WARN_GLYPH} " + sheet_cooling_text(info.get("remaining_sec")),
                "_tone": "黃", "note_lines": []}
    return {**node, "text": shown, "note_lines": list(extra)}


def _strip_demo(lines):
    return [line for line in lines if line not in _DEMO_LINES]


def _structure_lines(notes, code) -> list:
    """★9：讀設定試算表時的結構檢查計數（大於 0 才出）。"""
    s = notes.get("structure") or {}
    lines = []
    if code == "SET-1":
        mi = s.get("market_indicator") or {}
        if mi.get("conflicts"):
            lines.append(_node(TEXT_PK_CONFLICT.format(n=mi["conflicts"]), "黃"))
        if mi.get("is_revised_mismatch"):
            lines.append(_node(TEXT_REVISED_MISMATCH.format(n=mi["is_revised_mismatch"]), "黃"))
        if mi.get("bad_rows"):
            lines.append(_node(TEXT_BAD_ROWS.format(n=mi["bad_rows"]), "黃"))
    if code in ("SET-3", "SET-4"):
        us = s.get("user_setting") or {}
        if us.get("bad_rows"):
            lines.append(_node(TEXT_BAD_ROWS.format(n=us["bad_rows"]), "黃"))
    if code == "SET-6":
        fl = s.get("fetch_log") or {}
        if fl.get("duplicates"):
            lines.append(_node(TEXT_DUPLICATE_LOG.format(n=fl["duplicates"]), "黃"))
        if fl.get("bad_rows"):
            lines.append(_node(TEXT_BAD_ROWS.format(n=fl["bad_rows"]), "黃"))
    return lines


def _save_fail_lines(result, token) -> list:
    """★6 失敗框（草稿 6.1）：第 1、2 行照既有；第 3 行「未存檔。…」；403／404 另加一行；含遮蔽加 ★5。"""
    message = result["message"]
    lines = [logic.save_failed_text(message)]
    if _masked(message, token):
        lines.append(MASKED_NOTE)
    lines.append(logic.TEXT_KEEP_INPUT)
    hint = result.get("hint") or ""
    is_403 = result.get("http_status") == 403 or hint == TEXT_HINT_403
    is_404 = result.get("http_status") == 404 or hint.startswith(TEXT_HINT_404)
    # 「可能其實已寫入」只限一般失敗：冷卻、缺設定、標頭不符、403／404（打不開或沒有權限）都是根本沒寫。
    if result.get("status") != "read_only" and result.get("code") not in _NOT_WRITTEN_CODES \
            and not is_403 and not is_404:
        lines.append(TEXT_SAVE_MAYBE_WRITTEN)
    if is_403:
        lines.append(TEXT_HINT_403)
    elif is_404:
        email = result.get("client_email") or ""
        lines.append(f"{TEXT_HINT_404} {email}" if email else TEXT_HINT_404)
    return lines


def _drop_dev_notes(node):
    """BL-0345（2026-10-19）：把 `logic.LIVE_DEV_NOTE_EDITS` 列的純開發註記從正式模式拿掉（整棵模型走一遍）。

    只認整句相等：句子等於表裡的鍵 → 換成表裡的值；值為 None 就整句拿掉。**只刪、不新寫任何字。**
    示範模式不經過本函式，輸出不變。
    """
    edits = logic.LIVE_DEV_NOTE_EDITS
    if isinstance(node, dict):
        for key, value in node.items():
            node[key] = _drop_dev_notes(value)
        return node
    if isinstance(node, (list, tuple)):
        kept = [_drop_dev_notes(v) for v in node if not (isinstance(v, str) and v in edits and edits[v] is None)]
        return type(node)(kept)
    if isinstance(node, str) and node in edits and edits[node] is not None:
        return edits[node]
    return node


def apply_live_notes(model: dict, dataset: dict, notes: dict, *, save_results=None) -> dict:
    """回傳調整過的模型複本（不改呼叫端手上的那一份）。

    `dataset`：交給 `logic.build_page_model` 的那一份（讀它的 `errors` 對出失敗字串）。
    `save_results`：上一次按「存檔」的結果 `{鍵: result}`（`source.save_setting` 的回傳），沒有就 None。
    """
    out = _drop_dev_notes(copy.deepcopy(model))
    token = notes["mask_token"]
    fail_map = _fail_map(dataset, notes)
    pending_tables = set(notes["pending_tables"])
    wired_tiers = set(notes["wired_tiers"])

    # ── SET-0：燈的外框與文字照 `44`（含 5.5 系統錯誤模板 `logic.fetch_failed_text`），只在下一行加 ★5；說明行加 ★1、★3 ──
    set0 = logic.find_block(out, "SET-0")
    if not sheet_configured(notes) and not service_account_configured(notes):
        # 客戶 2026-10-18 裁示 C1（`DEC-2026-10-18-01`）：設定試算表與服務帳戶都沒設時，讀取失敗看到的只有「沒設 ID」，
        # 缺服務帳戶被蓋掉；燈改用缺服務帳戶那一句（與只缺服務帳戶時同一盞 ⛔ 讀取失敗），不出第三句（`sections.set_conclusion`）。
        message = notes["service_account"]["message"]
        set0.update(_tone="紅", _state="讀取失敗", glyph=logic.FETCH_FAIL_GLYPH, state_word="狀態：取數失敗",
                    text=logic.fetch_failed_text(message))
    set0["note_lines"] = [MASKED_NOTE] if _masked(set0["text"], token) else []
    # 客戶 2026-10-18 裁示 S4：說明行補明第三個輸入（設定試算表是否已設定）。示範模式不經過本檔，照舊。
    set0["detail_lines"] = [TEXT_SET0_INPUTS if line == TEXT_SET0_INPUTS_DEMO else line for line in set0["detail_lines"]]
    if "dividend" in pending_tables:
        set0["detail_lines"].append(TEXT_PENDING_DIVIDEND)
    # ~~set0["detail_lines"].append(TEXT_LOG_SCOPE)~~ → 客戶 2026-10-19 裁示：取數紀錄的射程說明只留在 `SET-6`。

    # ── SET-1 ──
    set1 = logic.find_block(out, "SET-1")
    for row in set1["_rows"]:
        table = _KIND_TABLE[row["_kind_label"]]
        row["note_lines"], row["at_note_lines"] = [], []
        if row["_empty"] and table in pending_tables:
            row["note_lines"].append(TEXT_REASON_KIND_PENDING)  # ★2
        if row["_failed"] and row["at_text"] in fail_map:
            shown, extra, _t = fail_map[row["at_text"]]
            row["at_text"] = shown
            row["at_note_lines"] = [n["text"] for n in extra]
        if table == "market_indicator" and not row["_failed"] and not row["_empty"]:
            row["note_lines"].append(TEXT_MI_TIME_SCOPE)  # ★4
        if table == "nav" and not row["_failed"] and not row["_empty"]:
            row["note_lines"].append(TEXT_NAV_TIME_SCOPE)  # 2026-10-09 核准
    set1["fail_nodes"] = [_decorate_placeholder(n, fail_map, notes, "SET-1") for n in set1["fail_nodes"]]
    set1["live_lines"] = _structure_lines(notes, "SET-1")
    set1["detail_lines"] = _strip_demo(set1["detail_lines"])  # ✂2
    runtime = notes.get("runtime") or {}
    errors = dataset.get("errors") or {}
    line = runtime_source_line(runtime, errors, ("market_indicator", "fetch_log"))   # 2026-10-26 裁示第 6 節：標來源
    if line:
        set1["detail_lines"].append(line)
    # 客戶 2026-10-19 裁示：新鮮度上限那一行不帶括號裡的鍵名（`（set_max_age_days）`，一般畫面換字後是「（新鮮度上限日數）」）。
    set1["limit_lines"] = [line.replace(f"（{logic.MAX_AGE_KEY}）", "") for line in set1.get("limit_lines") or ()]

    # ── SET-2 ──
    set2 = logic.find_block(out, "SET-2")
    set2["placeholder"] = _decorate_placeholder(set2["placeholder"], fail_map, notes, "SET-2")
    for row in set2["_rows"]:
        row["note_lines"], row["message_note_lines"] = [], []
        table = _TIER_TABLE[row["_tier"]]
        record_missing = row["result_text"] == "⬜"
        not_wired = row["_tier"] not in wired_tiers and (table is None or table in pending_tables)
        if record_missing and not_wired:
            row["note_lines"].append(TEXT_REASON_TIER_PENDING)  # ★2
        if _masked(row["message_text"], token):
            row["message_note_lines"].append(MASKED_NOTE)  # ★5
    set2["detail_lines"] = _strip_demo(set2["detail_lines"])  # ✂2（★3 只留在 SET-6，客戶 2026-10-19 裁示）
    line = runtime_source_line(runtime, errors, ("fetch_log",))   # 2026-10-26 裁示第 6 節：標來源
    if line:
        set2["detail_lines"].append(line)
    _plain_results(set2, dataset)
    _relabel_unconfigured_lamp(set0, set2)
    if set2["placeholder"]:
        set2["_plain_summary"] = _read_failure_title(set2["placeholder"], dataset, notes, "fetch_log")

    # ── SET-3：★10 在卡頭下方第一行 ──
    set3 = logic.find_block(out, "SET-3")
    title = notes["title"]
    head = []
    if title["state"] == "ok":
        head.append(_node(TEXT_TITLE.format(title=title["text"])))
    elif title["state"] == "not_configured":
        head.append(_node(f"{logic.FETCH_FAIL_GLYPH} {TEXT_NO_SHEET_ID}", "紅"))
    elif title["state"] == "cooling":
        # 草稿 B4：設定試算表冷卻是暫停、不是失敗，與 SET-3／SET-4 同一句黃色暫停句。
        head.append(_node(f"{logic.WARN_GLYPH} " + sheet_cooling_text(title.get("remaining_sec")), "黃"))
    elif plain.MSG_NO_SERVICE_ACCOUNT in (title["text"] or ""):
        # BL-0250 批次 3-A：缺服務帳戶讀不到名稱 → 同一句「⛔ 尚未設定：Google 服務帳戶」（`_plain_set_words` 換字），不寫「讀不到試算表名稱」。
        head.append(_node(_SA_RAW_LINE, "紅"))
    else:
        head.append(_node(TEXT_TITLE_FAILED.format(message=title["text"]), "紅"))
        if _masked(title["text"], token):
            head.append(_node(MASKED_NOTE, "灰"))
    set3["head_lines"] = head
    placeholder = _decorate_placeholder(set3["placeholder"], fail_map, notes, "SET-3", dataset)
    sa_missing = title["state"] == "failed" and plain.MSG_NO_SERVICE_ACCOUNT in (title["text"] or "")
    if placeholder and (title["state"] == "not_configured" or sa_missing) and placeholder["text"] == head[0]["text"]:
        # 草稿 7.1：同一句不重複印，★10 那一行即本塊的失敗行（BL-0250 批次 3-A：缺服務帳戶同理；冷卻中照舊兩行）。
        placeholder = None
    set3["placeholder"] = placeholder
    broken = set((notes.get("structure") or {}).get("user_setting", {}).get("broken_keys", ()))
    set3["column_labels"] = list(SET3_COLUMN_LABELS)   # BL-0250 批次 3-A U7（a）
    for row in set3["_rows"]:
        if row["_key"] in broken:  # `50` 第 8 節：最新一列解析不了 → 錯誤狀態，不是 ⬜ 未設定
            row["value_text"] = TEXT_BAD_ROWS.format(n=1)
            row["raw_text"] = ""
        # U7（a）：列上寫中文設定名（對照只維護 `ui_v2/plain.py` 一份，同 `SET-4` 輸入欄標籤）與資料型態的中文；
        # 型別缺（`⬜`）照舊。底層鍵、`value_kind`、判定一個都不動；英文原名照舊在進階診斷「原始鍵名對照」。
        row["key_text"] = plain.key_name(row["_key"])
        row["kind_text"] = KIND_NAMES.get(row["kind_text"], row["kind_text"])
    set3["live_lines"] = _structure_lines(notes, "SET-3")
    set3["detail_lines"] = _strip_demo(set3["detail_lines"])  # ✂2

    # ── SET-4 ──
    set4 = logic.find_block(out, "SET-4")
    set4["fail_nodes"] = [_decorate_placeholder(n, fail_map, notes, "SET-4", dataset) for n in set4["fail_nodes"]]
    top = []
    gate = notes["gate"]
    setting_code = notes["table_errors"].get("user_setting", {}).get("code")
    if gate["state"] in ("not_configured", "no_service_account") and setting_code != gate["state"]:
        # 去重比對錯誤碼、不比對字串：讀設定已因同一個缺設定失敗時，本塊的失敗行就是這件事，不再多印一行。
        # BL-0250 批次 3-A：缺服務帳戶那一行寫「⛔ 尚未設定：Google 服務帳戶」（停用原因另寫在按鈕上）。
        line = (f"{logic.FETCH_FAIL_GLYPH} {TEXT_SA_NOT_CONFIGURED}" if gate["state"] == "no_service_account"
                else f"{logic.FETCH_FAIL_GLYPH} {gate_reason(gate)}")
        top.append(_node(line, "紅"))
    set4["top_lines"] = top
    reading = set(notes["pages_reading_settings"])
    results = save_results or {}
    for field in set4["inputs"]:
        key = field["name"]
        prefix = key.split("_", 1)[0]
        if prefix not in reading:
            blocks = dict(dataset["spec"]["key_used_by"]).get(key, ())
            if field["_value"] is None:
                field["used_by_text"] = None  # 草稿 B9：未設定的鍵不出 ★7，只留「⬜ 未設定」
            elif blocks:
                field["used_by_text"] = TEXT_SETTING_PENDING.format(codes="、".join(blocks))  # ★7
        if key in broken:
            field["unset_lines"] = [TEXT_BAD_ROWS.format(n=1)]
        result = results.get(key)
        field["saved_lines"] = []
        if result is None:
            continue
        if result["status"] == "saved":
            field["saved_lines"] = [TEXT_SAVED]
        elif result["status"] in ("failed", "read_only"):
            field["fail_lines"] = _save_fail_lines(result, token)
        elif result["status"] == "kind_missing":
            # 客戶 2026-09-26 裁示後每一鍵都有型別（alo_basis 定為 list 枚舉）；走到這裡是本頁的 bug，當場炸（§1）。
            raise ValueError(f"{key} 的 value_kind 未定，正式模式不該發生（{result.get('message')}）")
        # kind_mismatch：型別說明由 logic 依當下輸入畫出（`dataset["save_inputs"]`），這裡不另加。
    if not set4["inputs"]:
        # 讀不到設定、畫面上沒有輸入欄（SET-GAP-失敗無輸入欄）：上游失敗後存檔與讀取共用冷卻，所以正式模式下
        # 這是存檔失敗後最常見的樣子。「上面這一欄…」那一行照 logic 不印（會是假話），其餘照 ★6。
        set4["orphan_fail_lines"] = [
            [line for line in _save_fail_lines(results[k], token) if line != logic.TEXT_KEEP_INPUT]
            for k in sorted(results) if results[k]["status"] in ("failed", "read_only")
        ]
    for field in set4["inputs"]:
        if field.get("used_by_text") == _USED_BY_NONE_DEMO:
            field["used_by_text"] = TEXT_USED_BY_NONE
        # 客戶 2026-10-19 裁示：輸入欄標籤 ~~`<鍵名>（<value_kind>）`~~（`logic` SET-GAP-輸入欄型態，示範模式照舊）→ 中文設定名
        # （對照只維護 `ui_v2/plain.py` 一份；找不到中文名的鍵照原字）。底層鍵、`value_kind`、存檔內容一個都不動。
        field["label"] = plain.key_name(field["name"])
    if set4["fail_nodes"]:
        # BL-0250 批次 3-A：~~「取數失敗：user_setting」~~（`logic`，示範模式照舊）→ 依成因寫（`_read_failure_title`）。
        set4["summary_text"] = _read_failure_title(set4["fail_nodes"][0], dataset, notes, "user_setting")
    else:
        unset = sum(1 for field in set4["inputs"] if field["_value"] is None)
        n = len(set4["inputs"])
        set4["summary_text"] = (TEXT_SET4_SUMMARY.format(n=n, unset=unset) if unset
                                else TEXT_SET4_SUMMARY_ALL_SET.format(n=n))
    set4["buttons"] = [save_button(notes)]
    set4["live_lines"] = _structure_lines(notes, "SET-4")
    set4["detail_lines"] = _strip_demo(set4["detail_lines"])  # ✂3
    # U7（a）：「逐鍵編輯，一鍵一個輸入欄，欄位型態依 value_kind 決定。」（`logic`，示範模式照舊）→ 一般用語。
    per_key = logic.TEXT_SET4_PER_KEY.replace("`", "") + "。"
    set4["detail_lines"] = [TEXT_SET4_PER_KEY_PLAIN if line == per_key else line for line in set4["detail_lines"]]

    # ── SET-5：說明行換成 ★8（✂4）；按鈕由 page 依當下單選呼叫 `refetch_button` ──
    set5 = logic.find_block(out, "SET-5")
    set5["detail_lines"] = _strip_demo(set5["detail_lines"]) + [TEXT_SET5_NOTE]
    set5["buttons"] = [refetch_button(None, notes)]

    # ── SET-6 ──
    set6 = logic.find_block(out, "SET-6")
    set6["placeholder"] = _decorate_placeholder(set6["placeholder"], fail_map, notes, "SET-6")
    if set6["placeholder"] and set6["placeholder"].get("_empty_kind") != "來源缺":
        # BL-0250 批次 3-A：~~「取數失敗：fetch_log」~~（`logic`，示範模式照舊）→ 依成因寫（`_read_failure_title`）。
        set6["summary_text"] = _read_failure_title(set6["placeholder"], dataset, notes, "fetch_log")
    elif set6["placeholder"]:
        # BL-0250 批次 3-C（客戶 2026-10-21 Q4；`DEC-2026-10-21-02`）：完全沒有任何取數紀錄 → 收合標題只寫「尚無取數紀錄」，
        # ~~「缺 fetch_log：尚無取數紀錄」~~（`logic` 那一句，示範模式照舊）。只限 `SET-2`／`SET-6` 這一種情形（有意識的政策變更，不是漏刪）。
        set6["summary_text"] = logic.TEXT_NO_RECORDS
    _plain_log_rows(set6, dataset)
    for row in set6["_rows"]:
        row["cell_notes"] = {5: [MASKED_NOTE]} if _masked(row["cells"][5], token) else {}
    tail = []
    for line in set6["tail_lines"]:
        for raw, (shown, _extra, _t) in fail_map.items():
            if raw in line:
                line = line.replace(raw, shown)
        tail.append(line)
    set6["tail_lines"] = tail
    set6["live_lines"] = _structure_lines(notes, "SET-6")
    order = logic.TEXT_SET6_ORDER.replace("`", "") + "。"
    set6["detail_lines"] = [TEXT_SET6_ORDER_PLAIN if line == order else line
                            for line in _strip_demo(set6["detail_lines"])] + [TEXT_LOG_SCOPE]  # ✂2、★3；U7（c）
    line = runtime_source_line(runtime, errors, ("fetch_log",))   # 2026-10-26 裁示第 6 節：標來源
    if line:
        set6["detail_lines"].append(line)

    _sa_raw_restore((set2, set6))

    # ── SET-7：U7（d）＋待裁示 (5a)：留在原位、改標題、預設收合（本來就收合；內容一字不改） ──
    set7 = logic.find_block(out, "SET-7")
    set7["title"] = SET7_TITLE
    tail = set7["summary_text"].partition("，另有 ")[2]   # 未定義的欄位照舊在摘要說出來（44 第五節第四小節）
    set7["summary_text"] = SET7_SUMMARY + (f"，另有 {tail}" if tail else "")
    set7["_default_open"] = False
    return _plain_set_words(out)


# ───────────────────────── BL-0250 批次 3-A 的幾支輔助 ─────────────────────────


def record_unconfigured_names(record):
    """一筆 `fetch_log` 紀錄（`outcome` 為 `failed`）的每一則訊息是不是都屬「尚未設定」那一族（`plain._KNOWN_MESSAGES`）。
    是 → 回尚未設定的對象（例 `["資料來源的金鑰"]`，依出現順序、不重複）；否則（含沒有訊息、混有任何一則別的訊息）→ None。
    訊息一則一行、形如「<鍵>: <訊息>」（`services/v2_tables/settings_store.py` 組的那一份）；沒有「: 」的行整行當一則。"""
    if record.get("outcome") != "failed":
        return None
    message = record.get("message")
    if not isinstance(message, str) or not message.strip():
        return None
    names = []
    for line in message.split("\n"):
        if not line.strip():
            continue
        part = line.split(": ", 1)[1] if ": " in line else line
        state = plain.not_configured_state(part)
        if state is None:
            return None
        name = state[: -len("尚未設定")] if state.endswith("尚未設定") else state
        if name not in names:
            names.append(name)
    return names or None


def _result_text(record) -> tuple:
    """(結果欄的字, 結果類別)。未知的 `outcome` 照拋（同 `logic._build_set2`，44 第四節第五小節值域只有 ok／failed）。"""
    outcome = record.get("outcome")
    if outcome == "ok":
        return TEXT_RESULT_OK, RESULT_OK
    if outcome == "failed":
        names = record_unconfigured_names(record)
        if names:
            return f"{logic.FETCH_FAIL_GLYPH} {plain_not_configured(names)}", RESULT_UNCONFIGURED
        return TEXT_RESULT_FAILED, RESULT_FAILED
    raise ValueError(f"fetch_log.outcome {outcome!r} 不是 ok 或 failed")


def plain_not_configured(names) -> str:
    return "尚未設定：" + "、".join(names)


def _plain_results(set2: dict, dataset: dict) -> None:
    """`SET-2` 各列的結果欄改中文；全屬尚未設定的那一筆不掛「取數失敗」徽章（就地改寫）。
    列上另記 `_result`（ok／failed／unconfigured）與 `_unconfigured_names`，給收合摘要與燈讀（不是判定，只是成因的記號）。"""
    if not set2["_rows"]:
        return
    latest = logic.latest_per_tier(dataset.get("fetch_log") or ())
    for row in set2["_rows"]:
        record = latest.get(row["_tier"])
        if record is None:
            continue
        text, kind = _result_text(record)
        row["result_text"], row["_result"] = text, kind
        if kind == RESULT_UNCONFIGURED:
            row["_unconfigured_names"] = record_unconfigured_names(record)
        # 結果欄已寫出取數失敗或尚未設定（都帶 ⛔），同一列的「取數失敗」徽章不再重複（尚未設定那一種更不得掛它）。
        row["badges"] = [b for b in row["badges"] if b.get("text") != logic.TEXT_FETCH_FAILED]


def _relabel_unconfigured_lamp(set0: dict, set2: dict) -> None:
    """`SET-0` 紅燈「失敗的來源層級：…」：最近一次紀錄全屬尚未設定的層級改寫「尚未設定：<哪一項>（<層級>）」；
    失敗的層級全是這一種時，狀態字「狀態：來源失敗」→「狀態：尚未設定」。燈色、圖示、`_state` 與失敗來源數照舊（只改字）。"""
    if set0.get("_state") != "來源失敗":
        return
    rows = {row["_tier"]: row for row in set2["_rows"]}
    real, unconfigured = [], []
    for tier in set2["_failed_tiers"]:
        row = rows.get(tier) or {}
        if row.get("_result") == RESULT_UNCONFIGURED:
            unconfigured.append(f"{plain_not_configured(row['_unconfigured_names'])}（{tier}）")
        else:
            real.append(tier)
    if not unconfigured:
        return
    parts = (["失敗的來源層級：" + "、".join(real)] if real else []) + unconfigured
    set0["text"] = "；".join(parts)
    if not real:
        set0["state_word"] = "狀態：尚未設定"


def _plain_log_rows(set6: dict, dataset: dict) -> None:
    """`SET-6`：不列紀錄編號欄（U7（c）；紀錄編號與結果原值移到進階診斷 `_raw_log`）、結果欄改中文（就地改寫）。"""
    set6["column_labels"] = list(SET6_COLUMN_LABELS)
    by_id = {r["log_id"]: r for r in dataset.get("fetch_log") or ()}
    for row in set6["_rows"]:
        record = by_id[row["_log_id"]]
        cells = list(row["cells"][1:])          # 拿掉第一格（log_id）
        cells[3] = _result_text(record)[0]       # 結果
        row["cells"] = cells
    # 同批稽核回修（E）：進階診斷只列一般表上那幾筆（同順序；超出保留筆數被移除的列不列，兩邊筆數一致）。
    set6["_raw_log"] = [
        (by_id[row["_log_id"]]["log_id"], logic.format_time(by_id[row["_log_id"]]["started_at"]), by_id[row["_log_id"]]["outcome"])
        for row in set6["_rows"]
    ]


def _sa_raw_restore(blocks) -> None:
    """`SET-2`（來源健康卡）／`SET-6`（取數紀錄）照印原文的那一格，缺 Google 服務帳戶時照舊印原文（`logic.fetch_failed_text`
    包住 `plain.MSG_NO_SERVICE_ACCOUNT` 那一句；就地改寫；與批次 3-A 之前逐字相同）。
    客戶核准的待裁示 (3) 原文：缺服務帳戶統一一句是「燈以外各處」「除來源健康卡與取數紀錄（照印原文）外」；那一格的
    `google_service_account` 屬客戶核准的照印原文例外，不算工程名稱外漏（44 第七節第三小節之十二其三第 2 條）。
    ~~一般畫面改寫統一句、原文移到進階診斷（同批總管裁定其九第 3 條）~~ → 同批稽核後撤回（有意識的更正，不是漏刪；決策者：AI 總管；
    理由：超出 `DEC-2026-10-19-05` 核准的待裁示 (3) 射程）。"""
    raw = logic.fetch_failed_text(plain.MSG_NO_SERVICE_ACCOUNT)
    for block in blocks:
        node = block.get("placeholder")
        if node and node.get("text") == _SA_RAW_LINE:
            node["text"] = raw
        if block.get("tail_lines"):
            block["tail_lines"] = [raw if line == _SA_RAW_LINE else line for line in block["tail_lines"]]


def _read_failure_title(node: dict, dataset: dict, notes: dict, table: str) -> str:
    """讀取失敗時那一塊收合標題的字（BL-0250 批次 3-A；不寫工程字樣、不把尚未設定寫成取數失敗）。"""
    code = notes["table_errors"].get(table, {}).get("code")
    if code == "not_configured":
        return f"{logic.FETCH_FAIL_GLYPH} {TEXT_NO_SHEET_ID_READ}"
    if code == "no_service_account":
        return f"{logic.FETCH_FAIL_GLYPH} {TEXT_SA_NOT_CONFIGURED}"
    if code == "cooling" and table == "user_setting":
        return node["text"]          # 卡上那一句暫停句（黃，草稿 B4），不是取數失敗
    if code == "cooling":
        # 同批稽核回修：`SET-2`／`SET-6`（讀 `fetch_log`）冷卻中也寫同一句暫停句（44 之十二其二「冷卻中 → 卡上那一句暫停句」）；
        # 這兩塊照印原文的那一格照舊印原文，只有收合標題寫暫停句。原本落到取數失敗，與規定不一致。
        info = notes["table_errors"].get(table, {})
        return f"{logic.WARN_GLYPH} " + sheet_cooling_text(info.get("remaining_sec"))
    return TEXT_TITLE_FETCH_FAILED


def _plain_set_words(model: dict) -> dict:
    """客戶 2026-10-19 裁示（BL-0250 批次 1）：一般畫面的兩處字樣（就地改寫並回傳）。
    `SET-2`、`SET-6`、`SET-7` 照印原文、不換；按鈕的停用原因（寫入情境）不換。"""
    read_line = f"{logic.FETCH_FAIL_GLYPH} {TEXT_NO_SHEET_ID}"

    def visit(node, key=None):
        if isinstance(node, dict):
            for name in list(node):
                if name == "disabled_reason":
                    continue
                node[name] = visit(node[name], name)
            return node
        if isinstance(node, list):
            return [visit(item, key) for item in node]
        if isinstance(node, tuple):
            return tuple(visit(item, key) for item in node)
        if isinstance(node, str) and not (isinstance(key, str) and key.startswith("_")):
            if node == read_line:
                node = f"{logic.FETCH_FAIL_GLYPH} {TEXT_NO_SHEET_ID_READ}"
            elif node == _SA_RAW_LINE:   # BL-0250 批次 3-A：缺服務帳戶（讀取情境）同一句
                node = f"{logic.FETCH_FAIL_GLYPH} {TEXT_SA_NOT_CONFIGURED}"
            for raw, shown in SERVICE_ACCOUNT_WORDS:
                node = node.replace(raw, shown)
        return node

    for block in model.get("blocks") or ():
        if block.get("code") in _RAW_TEXT_CODES:
            continue
        visit(block)
    return model


# ───────────────────────── Google 個人登入（批 3b-2；`docs/v2/65_set_wireframe_and_cap_gate_01_02.md` 第 B、C、D 節） ─────────────────────────
#
# 本段是「第二層 Google 帳號卡」的讀模型（純函式；不 import streamlit、不 import 舊樹、不碰任何權杖）。
# 輸入是 L2 `services/v2_tables/personal_session.py` 回的純 dict（`status()`／`begin_login()`），由 `source.login_live`
# 組好交來；本段只決定「畫哪幾行字、哪幾枚鈕」。登入、確認、登出、切換是工作階段身分動作，**不是試算表寫入**：
# 這幾枚鈕不在 `logic` 的按鈕表裡、沒有 `_writes`，不經 `readonly.strip_write_controls`，也不取代它。
#
# 文案出處（逐字取自 65 第 B、C、D 節，標〔文件組擬定〕者為客戶已核准整體方向內的擬定字樣）：
#   卡標題「Google 帳號」、「登入方式：Google 個人帳號」、「授權範圍：唯讀（列出與讀取試算表）」、
#   「已登入 ‹帳號›」「已登入（帳號讀不到）」、［登入 Google］［重新登入］［切換帳號］［登出］、
#   B-1「⛔ 尚未設定：Google 登入」＋「這個儀表板還沒設定 Google 登入，目前無法登入。」、
#   B-2「⬜ 未登入」＋「登入後可列出你能用的試算表」、B-3「⛔ 登入沒有完成」、
#   B-4「◷ 登入已過期」＋「登入已過期，需要重新登入」、B-5「⬜ 無法判定」＋「讀不到登入狀態」、
#   D-2「切換後要重新選擇試算表」。
# 本批新增、65 沒有逐字定義的字樣（請客戶審字）：見下方標 NEW 的常數。
# 原因句只描述狀態、不寫指示動作（58 U-32、客戶 2026-10-02／10-03 裁示）；燈一律帶文字（58 U-21）。

LOGIN_CARD_TITLE = "Google 帳號"
LOGIN_METHOD_LINE = "登入方式：Google 個人帳號"
# 這句是靜態字樣，其真實性來自 `infra/personal_oauth.py::_scope_problem`：授權範圍不是恰為四項最小 scope 就拒絕登入。
LOGIN_SCOPE_LINE = "授權範圍：唯讀（列出與讀取試算表）"
TEXT_LOGIN_LOGGED_IN = "已登入 {email}"
TEXT_LOGIN_LOGGED_IN_NO_EMAIL = "已登入（帳號讀不到）"
TEXT_LOGIN_LOGGED_OUT = "⬜ 未登入"
TEXT_LOGIN_LOGGED_OUT_NOTE = "登入後可列出你能用的試算表"
TEXT_LOGIN_NOT_CONFIGURED = "⛔ 尚未設定：Google 登入"
TEXT_LOGIN_NOT_CONFIGURED_NOTE = "這個儀表板還沒設定 Google 登入，目前無法登入。"
TEXT_LOGIN_FAILED = "⛔ 登入沒有完成"
TEXT_LOGIN_EXPIRED = "◷ 登入已過期"
TEXT_LOGIN_EXPIRED_NOTE = "登入已過期，需要重新登入"
TEXT_LOGIN_UNKNOWN = "⬜ 無法判定"
TEXT_LOGIN_UNKNOWN_NOTE = "讀不到登入狀態"
TEXT_LOGIN_SWITCH_NOTE = "切換後要重新選擇試算表"
# NEW：待確認登入面板（65 沒有定義這一步的字樣；字樣出自本批派工單的指定句型）
TEXT_LOGIN_PENDING = "以 {email} 登入？"
# NEW：D-2 切換確認與 B-3 原因分類的字樣（65 只定義了分類名稱「取消／被拒／換取失敗」，沒有逐字句）
TEXT_LOGIN_REASON_REJECTED = "原因：登入驗證資訊不符或已逾時"
TEXT_LOGIN_REASON_SCOPE = "原因：授權範圍或帳號身分未通過檢查"
TEXT_LOGIN_REASON_EXCHANGE = "原因：向 Google 換取登入資料失敗"
TEXT_LOGIN_REASON_CANCELLED = "原因：登入被取消或沒有完成"   # NEW（授權頁導回帶 error）

LOGIN_BUTTON_LOGIN = "登入 Google"
LOGIN_BUTTON_RELOGIN = "重新登入"
LOGIN_BUTTON_SWITCH = "切換帳號"
LOGIN_BUTTON_LOGOUT = "登出"
LOGIN_BUTTON_CONFIRM = "確認"            # NEW
LOGIN_BUTTON_CANCEL = "取消"             # NEW
LOGIN_BUTTON_SWITCH_GO = "繼續切換"      # NEW

# 畫面層與來源層共用的動作代號（白名單；來源層只接這幾個）。
LOGIN_ACTIONS = ("confirm", "reject", "logout", "switch_ask", "switch_cancel", "switch_go")

# 授權網址只接 Google 授權端點（防呼叫端傳入非預期網址後被畫成連結）。
_AUTHORIZE_PREFIX = "https://accounts.google.com/"

_ERR_AUTH_EXPIRED = "AUTH_EXPIRED"
_ERR_AUTH_REQUIRED = "AUTH_REQUIRED"
_ERR_STATE_INVALID = "AUTH_STATE_INVALID"
_ERR_PERMISSION = "PERMISSION_DENIED"
_ERR_UNAVAILABLE = "UNAVAILABLE"
_ERR_EXCHANGE = ("NETWORK_ERROR", "UPSTREAM_ERROR")


def login_error_lines(code) -> list:
    """錯誤代號 → 畫面字（只比對代號，不比對例外字串；J-9）。未知代號一律落「⬜ 無法判定」，不當成功。"""
    if code == _ERR_AUTH_EXPIRED:
        return [TEXT_LOGIN_EXPIRED, TEXT_LOGIN_EXPIRED_NOTE]
    if code == _ERR_AUTH_REQUIRED:   # 授權頁導回帶 error（取消或沒有完成）：來源層記 AUTH_REQUIRED
        return [TEXT_LOGIN_FAILED, TEXT_LOGIN_REASON_CANCELLED]
    if code == _ERR_STATE_INVALID:
        return [TEXT_LOGIN_FAILED, TEXT_LOGIN_REASON_REJECTED]
    if code == _ERR_PERMISSION:
        return [TEXT_LOGIN_FAILED, TEXT_LOGIN_REASON_SCOPE]
    if code in _ERR_EXCHANGE:
        return [TEXT_LOGIN_FAILED, TEXT_LOGIN_REASON_EXCHANGE]
    return [TEXT_LOGIN_UNKNOWN, TEXT_LOGIN_UNKNOWN_NOTE]


def _login_button(action: str, label: str, url=None) -> dict:
    button = {"action": action, "label": label}
    if url is not None:
        button["url"] = url
    return button


def _clean_email(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def login_view(login_input) -> dict:
    """第二層 Google 帳號卡的讀模型。

    `login_input`：`{"status": personal_session.status() 的 dict 或 None, "begin": begin_login() 的 dict 或 None,
    "notice": 上一個動作留下的錯誤代號或 None, "switch_confirm": bool}`。
    回傳 `{"state", "lines", "buttons", "error_code"}`：`state` ∈ logged_out／pending_login／logged_in／
    not_configured／unknown；`buttons` 每枚 `{"action", "label"}`，登入鈕另帶 `"url"`（授權網址，不是權杖）。
    待確認登入優先於已登入（換帳號時要先讓使用者看見待確認的帳號）；待確認帳號讀不到時只給［取消］、不給［確認］。
    不存在任何自動確認的路徑：確認只由使用者按［確認］觸發。
    """
    inp = login_input if isinstance(login_input, dict) else {}
    status = inp.get("status")
    notice = inp.get("notice") if isinstance(inp.get("notice"), str) else None
    notice_lines = login_error_lines(notice) if notice else []

    def view(state, lines, buttons, code=None):
        return {"state": state, "lines": list(lines), "buttons": list(buttons), "error_code": code}

    login_state = status.get("login_state") if isinstance(status, dict) else None
    if login_state not in ("logged_out", "pending_login", "logged_in"):
        return view("unknown", notice_lines + [TEXT_LOGIN_UNKNOWN, TEXT_LOGIN_UNKNOWN_NOTE], [], notice)

    if login_state == "pending_login":
        email = _clean_email(status.get("pending_login_email"))
        if email is None:   # 沒有帳號可給使用者看 → 不給確認鈕（不得在看不到帳號時確認）
            return view("pending_login", notice_lines + [TEXT_LOGIN_UNKNOWN, TEXT_LOGIN_UNKNOWN_NOTE],
                        [_login_button("reject", LOGIN_BUTTON_CANCEL)], notice)
        return view("pending_login", notice_lines + [TEXT_LOGIN_PENDING.format(email=email)],
                    [{**_login_button("confirm", LOGIN_BUTTON_CONFIRM), "arg": email},   # 確認的是「畫面上顯示的這個帳號」
                     _login_button("reject", LOGIN_BUTTON_CANCEL)],
                    notice)

    if login_state == "logged_in":
        email = _clean_email(status.get("email"))
        head = TEXT_LOGIN_LOGGED_IN.format(email=email) if email else TEXT_LOGIN_LOGGED_IN_NO_EMAIL
        if inp.get("switch_confirm") is True:
            return view("logged_in", notice_lines + [head, TEXT_LOGIN_SWITCH_NOTE],
                        [_login_button("switch_go", LOGIN_BUTTON_SWITCH_GO),
                         _login_button("switch_cancel", LOGIN_BUTTON_CANCEL)], notice)
        return view("logged_in", notice_lines + [head, LOGIN_METHOD_LINE, LOGIN_SCOPE_LINE],
                    [_login_button("switch_ask", LOGIN_BUTTON_SWITCH), _login_button("logout", LOGIN_BUTTON_LOGOUT)],
                    notice)

    # logged_out
    begin = inp.get("begin")
    if not isinstance(begin, dict):
        return view("unknown", notice_lines + [TEXT_LOGIN_UNKNOWN, TEXT_LOGIN_UNKNOWN_NOTE], [], notice)
    if begin.get("ok") is not True:
        # `begin_login` 的 UNAVAILABLE 不只代表「部署沒設定 Google 登入」（`infra/personal_oauth.py` 在登記授權請求失敗等
        # 暫時或內部失敗時也丟 UNAVAILABLE），橋接的回傳又只帶代號、分不出來 → 無法證明是未設定，一律落「⬜ 無法判定」，
        # 不印「尚未設定」（B-1 字樣常數保留，待橋接能證明未設定時再接）。
        code = begin.get("error_code")
        return view("unknown", notice_lines + login_error_lines(code), [], code if isinstance(code, str) else None)
    url = begin.get("authorize_url")
    if not (isinstance(url, str) and url.startswith(_AUTHORIZE_PREFIX)):
        return view("unknown", notice_lines + [TEXT_LOGIN_UNKNOWN, TEXT_LOGIN_UNKNOWN_NOTE], [], notice)
    if notice:   # B-3／B-4：同一位置的［重新登入］
        return view("logged_out", notice_lines, [_login_button("login", LOGIN_BUTTON_RELOGIN, url)], notice)
    return view("logged_out", [TEXT_LOGIN_LOGGED_OUT, TEXT_LOGIN_LOGGED_OUT_NOTE],
                [_login_button("login", LOGIN_BUTTON_LOGIN, url)], None)


# ───────────────────────── 試算表選擇與「使用這一本」（批 3b-3；`docs/v2/65_set_wireframe_and_cap_gate_01_02.md` 第 E 節） ─────────────────────────
#
# 純函式讀模型：輸入是 `source.picker_load()` 交來的純 dict，輸出「畫哪幾行字、下拉有哪幾個選項、哪幾枚鈕」。
# 規則（客戶已核准）：只在「正式登入（已確認）」後出現；候選只來自 L2 `list_for_picker` 的清單（登入帳號可存取的試算表），
# 不猜、不 fallback、不補任何預設；選中只是「待確認（尚未使用）」，按［使用這一本］驗證成功才是「使用中」；
# 失敗時「使用中」永遠取自當下狀態（舊的那一本），不取自這一次嘗試的結果；沒有任何「清除使用中」的控制項。
# 文案：標〔65〕者逐字取自 65 第 E 節；標 NEW 者 65 沒有逐字定義，待客戶審字。

PICKER_CARD_TITLE = "試算表連線"                          # 〔65〕第 A 節卡名
PICKER_SELECT_LABEL = "選擇 Google Sheet"                  # 〔65〕E 節下拉標題
TEXT_PICKER_ACTIVE = "使用中：{name}（{sheet_id}）"          # 客戶指定字樣「使用中」＋顯示名稱與 ID（不顯示任何權杖）
TEXT_PICKER_ACCOUNT = "帳號：{email}"                       # NEW 待客戶審字
TEXT_PICKER_NO_ACTIVE = "⬜ 尚未選定試算表"                   # 〔65〕第 4 節
TEXT_PICKER_PENDING = "待確認（尚未使用）：{name}"            # 客戶指定字樣「待確認（尚未使用）」
TEXT_PICKER_STILL_ACTIVE = "目前使用中仍是：{name}（未變更）"  # 〔65〕E 節失敗線框
TEXT_PICKER_SWITCHED = "◆ 已切換為：{name}"                  # 〔65〕E 節成功線框
TEXT_PICKER_EMPTY = "⬜ 沒有可選的試算表"                      # NEW 待客戶審字（客戶指定句型「⬜ 無法判定／沒有可選的試算表」）
TEXT_PICKER_EMPTY_NOTE = "這個帳號目前沒有可列出的試算表"      # 〔65〕E-4
TEXT_PICKER_UNKNOWN = "⬜ 無法判定"                           # 〔65〕E-8
TEXT_PICKER_UNKNOWN_NOTE = "讀不到試算表清單"                  # NEW 待客戶審字
TEXT_PICKER_LIST_FAILED = "⛔ 列出試算表失敗"                  # 〔65〕E-7
TEXT_PICKER_LIST_DENIED = "⛔ 這個帳號沒有列出試算表的權限"      # 〔65〕E-5
TEXT_PICKER_USE_DENIED = "⛔ 無權限：切換沒有完成。"            # 〔65〕E 節失敗線框
TEXT_PICKER_USE_NOT_FOUND = "⛔ 找不到：切換沒有完成。"          # NEW 待客戶審字（65 只列「⛔ 找不到」）
TEXT_PICKER_USE_FAILED = "⛔ 驗證失敗：切換沒有完成。"           # NEW 待客戶審字（65 只列「⛔ 驗證失敗」）
TEXT_PICKER_SELECT_NOT_FOUND = "⛔ 找不到這本試算表"             # NEW 待客戶審字
TEXT_PICKER_UNKNOWN_USE_NOTE = "切換沒有完成，原因讀不到"        # NEW 待客戶審字（「使用這一本」失敗、分不出原因）
TEXT_PICKER_UNKNOWN_SELECT_NOTE = "選取沒有完成，原因讀不到"     # NEW 待客戶審字（選本失敗、分不出原因）
PICKER_PLACEHOLDER = "請選擇試算表"                           # NEW 待客戶審字
PICKER_ACTIVE_MARK = "（使用中）"                             # 〔65〕E 節「目前使用中」的簡寫；NEW 待客戶審字
PICKER_BUTTON_USE = "使用這一本"                              # 〔65〕
PICKER_BUTTON_RELIST = "重新列出"                             # NEW 待客戶審字

# 畫面層與來源層共用的動作代號（白名單）。
PICKER_ACTIONS = ("select", "use", "relist")

_PICKER_ID_TAIL = 6


def _picker_str(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def _picker_sheets(listing) -> list:
    """清單 → 乾淨的 `[{id, name}]`（只收字串 id；名稱缺就用 id；同 id 只留第一筆）。清單不是成功結果 → 空。"""
    if not (isinstance(listing, dict) and listing.get("ok") is True and isinstance(listing.get("sheets"), list)):
        return []
    seen, out = set(), []
    for item in listing["sheets"]:
        sid = _picker_str(item.get("id")) if isinstance(item, dict) else None
        if sid is None or sid in seen:
            continue
        seen.add(sid)
        out.append({"id": sid, "name": _picker_str(item.get("name")) or sid})
    return out


def _picker_label(sheet: dict, active_id) -> str:
    tail = sheet["id"][-_PICKER_ID_TAIL:]
    mark = PICKER_ACTIVE_MARK if sheet["id"] == active_id else ""
    return f"{sheet['name']}（…{tail}）{mark}"


def picker_error_lines(code, context: str) -> list:
    """錯誤代號 → 畫面字（只比對九個代號之一，不比對例外字串；未知代號落「⬜ 無法判定」，不當成功）。
    `context` ∈ list（列清單）／select（選本）／use（使用這一本）。"""
    if code == _ERR_AUTH_EXPIRED:
        return [TEXT_LOGIN_EXPIRED, TEXT_LOGIN_EXPIRED_NOTE]
    if code == _ERR_AUTH_REQUIRED:
        return [TEXT_LOGIN_LOGGED_OUT, TEXT_LOGIN_LOGGED_OUT_NOTE]
    if code == _ERR_PERMISSION:
        return [TEXT_PICKER_LIST_DENIED if context == "list" else TEXT_PICKER_USE_DENIED]
    if code == "SHEET_NOT_FOUND":
        return [TEXT_PICKER_SELECT_NOT_FOUND if context == "select" else TEXT_PICKER_USE_NOT_FOUND]
    if code in ("SCHEMA_INVALID",) + _ERR_EXCHANGE:
        return [TEXT_PICKER_LIST_FAILED if context == "list" else TEXT_PICKER_USE_FAILED]
    note = {"use": TEXT_PICKER_UNKNOWN_USE_NOTE, "select": TEXT_PICKER_UNKNOWN_SELECT_NOTE}.get(context,
                                                                                               TEXT_PICKER_UNKNOWN_NOTE)
    return [TEXT_PICKER_UNKNOWN, note]   # 不把「使用這一本」的失敗說成「讀不到試算表清單」


def picker_view(picker_input) -> dict:
    """「試算表連線」卡的讀模型。

    `picker_input`：`{"status": personal_session.status() 的 dict 或 None, "list": 清單結果（`{"ok": True, "sheets": [...]}` 或
    `{"ok": False, "error_code": ...}`）或 None, "notice": 上一個動作留下的 `{"kind", "code", "name"}` 或 None}`。
    回傳 `{"state", "lines", "options", "selected", "buttons"}`：`state` ∈ hidden／ready／empty／list_error／unknown。
    `options` 每項 `{"id", "label"}`，只來自清單；`selected` 是待確認那一本在 `options` 內的位置（沒有或不在清單內 → None）；
    `buttons` 每枚 `{"action", "label"}`，［使用這一本］另帶 `"arg"`＝畫面上顯示的待確認試算表 id。
    未正式登入（含待確認登入、未登入、讀不到狀態）一律 hidden：沒有任何輸出可畫。
    """
    inp = picker_input if isinstance(picker_input, dict) else {}
    status = inp.get("status")

    def view(state, lines=(), options=(), selected=None, buttons=()):
        return {"state": state, "lines": list(lines), "options": list(options), "selected": selected,
                "buttons": list(buttons)}

    if not (isinstance(status, dict) and status.get("login_state") == "logged_in"):
        return view("hidden")

    active = status.get("active_sheet") if isinstance(status.get("active_sheet"), dict) else None
    active_id = _picker_str(active.get("id")) if active else None
    active_name = (_picker_str(active.get("name")) or active_id) if active_id else None
    pend = status.get("pending_sheet") if isinstance(status.get("pending_sheet"), dict) else None
    pend_id = _picker_str(pend.get("id")) if pend else None
    pend_name = (_picker_str(pend.get("name")) or pend_id) if pend_id else None

    notice = inp.get("notice") if isinstance(inp.get("notice"), dict) else None
    lines: list = []
    if notice and notice.get("kind") == "use_ok" and active_id and _picker_str(notice.get("name")):
        lines.append(TEXT_PICKER_SWITCHED.format(name=active_name))   # 名稱取當下狀態（Active），不取回傳值
    elif notice and notice.get("kind") in ("use_fail", "select_fail"):
        context = "use" if notice["kind"] == "use_fail" else "select"
        lines += picker_error_lines(notice.get("code"), context)
        if context == "use" and active_id:   # 失敗維持舊 Active：名稱取自當下狀態
            lines.append(TEXT_PICKER_STILL_ACTIVE.format(name=active_name))
    if active_id:
        lines.append(TEXT_PICKER_ACTIVE.format(name=active_name, sheet_id=active_id))
        email = _clean_email(status.get("email"))
        if email:
            lines.append(TEXT_PICKER_ACCOUNT.format(email=email))
    else:
        lines.append(TEXT_PICKER_NO_ACTIVE)

    buttons: list = []

    listing = inp.get("list")
    relist = {"action": "relist", "label": PICKER_BUTTON_RELIST}
    # 待確認那一本只在它「就在畫面列出的清單內」時才顯示與給［使用這一本］：清單失敗／重列後不含它／空清單 → 不給
    # （fail closed：不對一本畫面上看不到的試算表發出驗證）。
    if not isinstance(listing, dict):
        return view("unknown", lines + [TEXT_PICKER_UNKNOWN, TEXT_PICKER_UNKNOWN_NOTE], buttons=[relist])
    if listing.get("ok") is not True:
        code = listing.get("error_code")
        return view("list_error", lines + picker_error_lines(code if isinstance(code, str) else None, "list"),
                    buttons=[relist])
    sheets = _picker_sheets(listing)
    if not sheets:   # API 成功但清單為零（或全是壞項）：照實說沒有可選的，不補任何預設
        return view("empty", lines + [TEXT_PICKER_EMPTY, TEXT_PICKER_EMPTY_NOTE], buttons=[relist])
    options = [{"id": s["id"], "label": _picker_label(s, active_id)} for s in sheets]
    ids = [o["id"] for o in options]
    selected = ids.index(pend_id) if pend_id in ids else None
    if selected is not None and pend_id != active_id:
        lines.append(TEXT_PICKER_PENDING.format(name=pend_name))
        buttons.append({"action": "use", "label": PICKER_BUTTON_USE, "arg": pend_id})   # 綁定畫面上顯示的待確認那一本
    return view("ready", lines, options, selected, buttons + [relist])
