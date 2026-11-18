# -*- coding: utf-8 -*-
"""🔍 找一檔基金／依條件篩選 隔離式 FAKE Preview 測試共用：路徑、import 設定、頁面層級的判定函式（純函式；負控／變異一律在記憶體內現編）。"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
POC = ROOT / "poc" / "fund_search_fixture_preview"
APP = POC / "app_fund_search_preview.py"
for _p in (str(ROOT / "tests" / "ui_v2"), str(ROOT / "tests" / "ui_v3"), str(POC), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

KEY_INPUT = "fs_query_input"
KEY_SCENARIO = "uvp_fs_scenario"
KEY_COND = "fs_cond_{n}"

# 畫面上任何情境都不得出現的字樣（子字串比對）。
FORBIDDEN_WORDS = ("基金不存在", "查無基金", "查無此", "已確認", "推薦", "最佳", "排名", "精選", "NAV", "報酬", "績效", "領先", "落後")
# 規格：暫時條件不得有存檔語彙。
SAVE_WORDS = ("存檔", "儲存", "保存", "已存", "未存檔")
NASTY_INPUTS = ("<script>alert(1)</script>", "<img src=x onerror=alert(1)>", "\"'><b>x</b>", "$x^2$ **b** [a](http://example.invalid) `c`", "&amp; &lt;",
                "a\\b \\$x\\$ \\\\ \\n \\<b>", "line1\nline2", "line1\n\nline2", "a\r\nb", "zero\u200bwidth\u200d\ufeffjoin", "\u202eevil\u202c rtl \u200fmark",
                "emoji 😀🙂 ⚠️ 👨‍👩‍👧", "L" * 150 + "<b>")
# 單行輸入（真的能從瀏覽器 text_input 打進去的）；換行與超長（maxlength=100）只在單元與 AppTest 驗
BROWSER_PAYLOADS = tuple(p for p in NASTY_INPUTS if "\n" not in p and "\r" not in p and len(p) <= 100)


def text_of(html: str) -> str:
    """HTML → 可見文字（粗略；去標籤、還原常見字元參照）。"""
    t = re.sub(r"<[^>]+>", " ", html)
    return (t.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#x27;", "'")
             .replace("&#36;", "$").replace("&#92;", "\\").replace("&#10;", "\n").replace("&#13;", "\r").replace("&amp;", "&"))


def special_char_violations(shown_html: str):
    """使用者輸入顯示處的 HTML 不得留下 `<`、`>`、`$`、反斜線、換行（皆須已轉成字元參照）；刪掉 `safe()` 任一分支都會讓這裡報紅。"""
    return [c for c in ("<", ">", "$", "\\", "\n", "\r") if c in shown_html]


def forbidden_word_violations(html: str):
    visible = text_of(html)
    return [w for w in FORBIDDEN_WORDS if w in visible]


def raw_script_violations(html: str):
    """使用者輸入必須已被 escape：HTML 裡不得出現會執行的標籤／事件屬性（輸入內容只准以 `&lt;…&gt;` 形式出現）。"""
    bad = []
    if re.search(r"<\s*script\b", html, re.I):
        bad.append("raw <script>")
    if re.search(r"<\s*img\b", html, re.I):
        bad.append("raw <img>")
    if re.search(r"<[^>]*\bon[a-z]+\s*=", html, re.I):
        bad.append("raw onerror=")
    return bad


def _attr(html: str, block: str, name: str):
    m = re.search(rf'data-block="{block}"[^>]*?\b{name}="([^"]*)"', html)
    return None if m is None else m.group(1)


def count_consistency_violations(html: str):
    """EXP-0 的 N／M、EXP-2 的列數、EXP-7 的最後一列，三處必須一致（只看有展示 N／M 的情況）。"""
    out = []
    if _attr(html, "exp0", "data-counts-shown") != "yes":
        if 'data-block="exp2"' in html and re.search(r'data-block="exp2"[^>]*data-state="rows"', html):
            out.append("未展示 N／M 卻有 EXP-2 結果列")
        if re.search(r'data-block="exp7"[^>]*data-state="rows"', html):
            out.append("未展示 N／M 卻有 EXP-7 結果列")
        return out
    n, m = int(_attr(html, "exp0", "data-matched")), int(_attr(html, "exp0", "data-undetermined"))
    rows = len(re.findall(r'data-fund="', html))
    if rows != n + m:
        out.append(f"EXP-2 列數 {rows} ≠ N＋M {n}＋{m}")
    exp7 = html[html.index('data-block="exp7"'):] if 'data-block="exp7"' in html else ""
    last = re.findall(r'data-trace="\d+".*?data-col="matched"[^>]*>.*?</span>(\d+)</div>.*?data-col="undetermined"[^>]*>.*?</span>(\d+)</div>', exp7)
    if not last:
        out.append("EXP-7 沒有軌跡列")
    elif (int(last[-1][0]), int(last[-1][1])) != (n, m):
        out.append(f"EXP-7 末列 {last[-1]} ≠ (N, M)=({n}, {m})")
    shown = re.search(r'data-row="matched"[^>]*>.*?data-value="matched">(\d+)<', html)
    if shown is None or int(shown.group(1)) != n:
        out.append("EXP-0 畫面上的 N 與 data-matched 不一致")
    return out


def missing_shown_as_zero_violations(html: str):
    """EXP-2 每個格子的值，不是 fixture 的 `FAKE` 值，就必須是規則表缺值字樣（資料未備）；以 0／空白／破折號代替缺值＝違規。"""
    exp2 = re.search(r'data-block="exp2".*?(?=data-block="exp7"|$)', html, re.S)
    if exp2 is None:
        return []
    out = []
    for col, inner in re.findall(r'<div class="fs-cell" data-col="([a-z_]+)">(.*?)</div>', exp2.group(0)):
        value = text_of(re.sub(r'<span class="uv3-label".*?</span>', "", inner)).strip()
        if "FAKE" not in value and "資料未備" not in value:
            out.append((col, value))
    return out


def page_violations(html: str):
    return (forbidden_word_violations(html) + raw_script_violations(html) + count_consistency_violations(html)
            + missing_shown_as_zero_violations(html))


# ───────────────────────── 單檔查詢結果欄位白名單（DEC-2026-11-18-01：結果欄位只有五個） ─────────────────────────

# 欄位順序即客戶指示的順序。標籤文字取自 PendingWording（`row_*`），這裡寫死是為了讓『改字』也被這道守衛看見。
FIVE_LABELS = ("輸入代碼", "基金名稱", "配息方式", "成立日期", "經理費率")
# 結果卡內允許的 data-row 名稱：五欄各一，加上『沒有標籤』的狀態訊息列（result）與查詢前訊息列（idle，只在 idle 卡）。
LOOKUP_ROW_NAMES = ("result", "input-code", "name", "dividend-mode", "inception", "mgmt-fee")
# 結果卡與收合區都不得出現的欄位標籤／值（子字串比對；不寫死色碼、不依賴 DOM 順序）。
# 刻意不含『基金身份』『查詢結果』：失敗句『不是對基金身份的判斷』與單檔說明句『單檔查詢結果（唯讀…）』合法含有這兩詞；
# 這兩個欄位標籤由 `FIVE_LABELS` 的標籤白名單把關。
LOOKUP_UNAPPROVED_TOKENS = ("幣別", "NAV", "淨值", "報酬", "績效", "fetched_at", "as_of", "供應", "提供者", "備援", "資料日", "來源", "輸入類型", "currency")
_LABEL_RE = re.compile(r'<span class="uv3-label">(?:<span[^>]*>)?([^<]+)</span>')


def lookup_field_violations(card_html: str):
    """單檔查詢結果卡：標籤只能是五欄之一（且依序）、data-row 只能是白名單、不得含未核准欄位的字樣。"""
    bad = []
    labels = _LABEL_RE.findall(card_html)
    bad += [("非五欄標籤", x) for x in labels if x not in FIVE_LABELS]
    if [x for x in labels if x in FIVE_LABELS] != [x for x in FIVE_LABELS if x in labels]:
        bad.append(("五欄順序不對", labels))
    bad += [("非白名單 data-row", n) for n in re.findall(r'data-row="([^"]+)"', card_html) if n not in LOOKUP_ROW_NAMES]
    visible = text_of(card_html)
    bad += [("未核准欄位字樣", w) for w in LOOKUP_UNAPPROVED_TOKENS if w in visible]
    return bad


def lookup_text_violations(card_html: str, raw: str, found_name: str):
    """卡內『可見文字行集合』白名單：把卡片依標籤切成文字節點，每一個非空節點都必須是已知字樣——
    PendingWording 的字樣、規則表既有字樣（狀態列／資料不足）、FAKE 名稱，或這次輸入的原值。
    補足 `lookup_field_violations`（標籤＋data-row 白名單、字樣黑名單）看不到『未知新文字節點』的缺口。"""
    import html as _html
    import fund_search_wording as W
    from shared.ui_semantics import rules
    allowed = {w.text for w in W.FUND_SEARCH_PENDING.values()} | {found_name, raw.strip()}
    allowed |= {e.wording for e in rules.ENTRIES.values() if e.wording} | {a.text for a in rules.APPROVED_WORDING.values()}
    nodes = [_html.unescape(t).strip() for t in re.split(r"<[^>]+>", card_html)]
    return [("未知文字節點", n) for n in nodes if n and n not in allowed]


def details_field_violations(details_html: str):
    """預設收合區：不得有任何欄位列（標籤／data-row）；除『來源』（標題與限制句合法使用，不是欄位）外不得含未核准欄位字樣。"""
    bad = [("收合區出現欄位標籤", x) for x in _LABEL_RE.findall(details_html)]
    bad += [("收合區出現 data-row", n) for n in re.findall(r'data-row="([^"]+)"', details_html)]
    visible = text_of(details_html)
    bad += [("未核准欄位字樣", w) for w in LOOKUP_UNAPPROVED_TOKENS if w != "來源" and w in visible]
    return bad


def idle_violations(idle_html: str):
    """查詢前：整張卡的可見文字就只有『尚未查詢』，沒有任何標籤或欄位列。"""
    bad = []
    if text_of(idle_html).strip() != "尚未查詢":
        bad.append(("查詢前不只顯示『尚未查詢』", text_of(idle_html).strip()))
    if _LABEL_RE.findall(idle_html) or re.findall(r'data-row="(?!idle")', idle_html):
        bad.append(("查詢前出現欄位列", idle_html))
    return bad
