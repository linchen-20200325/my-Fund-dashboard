# -*- coding: utf-8 -*-
"""BL-0345（2026-10-19）：正式模式一般畫面不得出現純開發註記（「⚠ 44 …」「待客戶裁決」「44 自己寫」「SSOT」）。

情境腳本與抽字器重用 `tests/ui_v2/_plain_scan.py`。示範模式不變（正控：示範模式仍命中）。
"""

from __future__ import annotations

import pathlib
import re
import sys

import pytest

_HERE = pathlib.Path(__file__).resolve().parent
for _p in (_HERE, _HERE.parent, _HERE.parents[1]):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

pytestmark = pytest.mark.slow

import _plain_scan as SCAN  # noqa: E402

from ui_v2 import plain  # noqa: E402

DEV_NOTE = re.compile(r"⚠ ?44|待客戶裁決|44 自己寫|SSOT")

# 白名單（只此一句）：EXP-4「這份可選欄位是五項，而客戶已拍板的線框草稿畫的是四項」那一段是對客戶的揭露，
# 不是開發註記，BL-0345 派工明令保留；它句尾含「44 是 SSOT」，故以句中這個標記整句放行。
_ALLOW = ("客戶已拍板的線框草稿畫的是四項",)

# 不含上面 regex 字樣、但同樣在本輪刪除的兩句（另外釘住）。
_ALSO_GONE = ("兩個不同參數", "這一種算不算可接受待裁決")

_CASES = [(page, name) for page, scripts in SCAN.SCRIPTS.items() for name in scripts]


def _run(script):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(script, default_timeout=90)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _texts(at, page):
    # 設定與診斷頁的「進階診斷」照印原文（客戶裁示），不算一般畫面。
    skip = (plain.ADVANCED_DIAG_TITLE,) if page == "set" else ()
    return SCAN.screen_texts(at, skip_expanders=skip)


@pytest.mark.parametrize("page, name", _CASES, ids=[f"{p}-{n}" for p, n in _CASES])
def test_正式模式一般畫面沒有開發註記(page, name):
    texts = _texts(_run(SCAN.SCRIPTS[page][name]), page)
    assert len(texts) >= 3
    hits = [t for t in texts if DEV_NOTE.search(t) and not any(a in t for a in _ALLOW)]
    assert hits == [], [" ".join(h.split())[:160] for h in hits]
    assert [t for t in texts if any(k in t for k in _ALSO_GONE)] == []


def test_保留句仍在_白名單不是空轉():
    texts = _texts(_run(SCAN.SCRIPTS["exp"]["正常"]), "exp")
    assert any(_ALLOW[0] in t for t in texts)
    assert any("本塊跟著「對照」那一組勾起的第一檔。" == " ".join(t.split()) for t in texts)


_DEMO = {p: f"from ui_v2.{p} import page\npage.render()\n" for p in ("alo", "exp", "set")}


@pytest.mark.parametrize("page", sorted(_DEMO))
def test_正控_示範模式照舊命中開發註記(page):
    texts = SCAN.screen_texts(_run(SCAN._HEAD + _DEMO[page]))
    assert [t for t in texts if DEV_NOTE.search(t) and not any(a in t for a in _ALLOW)]


# ── BL-0525 Batch C（T13 遷移）：新視覺層級的 detail 容器也不得有純開發註記 ──
# 舊母體 `SCAN.SCRIPTS["mkt"]` 的五個情境沒有餵 `market_view`（走舊版面）；新層級只在有 Data View 時出現，所以另掃 `MKT_TREND`。
def test_正式模式_市場趨勢新層級_一般畫面沒有開發註記():
    texts = _texts(_run(SCAN.MKT_TREND), "mkt")
    assert len(texts) >= 10
    assert any("尚未取得" in t for t in texts), "新層級沒畫出來 —— 掃描是空掃"
    hits = [t for t in texts if DEV_NOTE.search(t)]
    assert hits == [], [" ".join(h.split())[:160] for h in hits]
    assert [t for t in texts if any(k in t for k in _ALSO_GONE)] == []
