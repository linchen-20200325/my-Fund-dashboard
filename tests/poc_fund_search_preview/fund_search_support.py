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
NASTY_INPUTS = ("<script>alert(1)</script>", "<img src=x onerror=alert(1)>", "\"'><b>x</b>", "$x^2$ **b** [a](http://example.invalid) `c`", "&amp; &lt;")


def text_of(html: str) -> str:
    """HTML → 可見文字（粗略；去標籤、還原常見字元參照）。"""
    t = re.sub(r"<[^>]+>", " ", html)
    return (t.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#x27;", "'")
             .replace("&#36;", "$").replace("&#92;", "\\").replace("&amp;", "&"))


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
