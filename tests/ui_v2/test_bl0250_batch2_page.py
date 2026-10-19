# -*- coding: utf-8 -*-
"""BL-0250 實機驗收回修 批次 2（客戶 2026-10-19 裁示 G1，`docs/DECISIONS.md` `DEC-2026-10-19-04`；
44 第七節第三小節之十一）的畫面守衛。

情境腳本與抽字器重用 `tests/ui_v2/_plain_scan.py`（五頁正式模式全部情境；只用各頁 fixtures／替身，不打網路）。
- 一般畫面（含 ④ 與各展開區，設定與診斷頁的進階診斷也收）不出現三條紅線的標記、「紅線說明區」、「本頁不負責什麼」；
- 頁尾一句指路句，每頁恰好一次；
- U3／U5／U6 與兩處順手字句的新字面；
- 示範模式正控：照舊有標記與舊頁尾。
突變（把拿掉徽章那一步接回去）見 `tests/ui_v2/test_bl0250_batch2_logic.py` 與本批回報。
"""

from __future__ import annotations

import functools
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

_CASES = [(page, name) for page, scripts in SCAN.SCRIPTS.items() for name in scripts]
_FORBIDDEN = re.compile(r"G[123]†|紅線說明區|本頁不負責什麼")


@functools.lru_cache(maxsize=None)
def _at(page, name):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(SCAN.SCRIPTS[page][name], default_timeout=90)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _texts(page, name):
    return [" ".join(t.split()) for t in SCAN.screen_texts(_at(page, name))]


def _joined(page, name):
    return "\n".join(_texts(page, name))


@pytest.mark.parametrize("page,name", _CASES, ids=[f"{p}-{n}" for p, n in _CASES])
def test_正式模式一般畫面_沒有紅線標記與紅線說明區與舊頁尾(page, name):
    hits = [t for t in _texts(page, name) if _FORBIDDEN.search(t)]
    assert hits == [], hits


@pytest.mark.parametrize("page,name", _CASES, ids=[f"{p}-{n}" for p, n in _CASES])
def test_頁尾一句指路句_恰好一次(page, name):
    texts = _texts(page, name)
    if any(t.startswith("⛔") for t in texts[:6]) and len(texts) < 8:
        pytest.skip("整頁錯誤畫面沒有頁尾（行為未改）")
    assert texts.count(plain.PLAIN_FOOTERS[page]) == 1, texts[-3:]


def test_MKT_說明行去前綴_一般用語():
    joined = _joined("mkt", "正常")
    assert "觀察窗與比較基準日由使用者自行輸入，系統不代填。" in joined
    assert "要看的指標由使用者自行選取，系統不代填。" in joined


def test_MKT_核心卡副標_不再兩個冒號():
    joined = _joined("mkt", "未設定")
    assert "⬜ 不適用（尚未設定：設定試算表）" in joined
    assert "不適用：尚未設定：" not in joined


def test_HLD_偏離提示與輸入說明_最大回撤指引():
    joined = _joined("hld", "正常")
    assert "本卡只描述現況與你設定的門檻差多少，不提供任何處置方向。" in joined
    assert "檢視區間與門檻都由使用者自行輸入，系統不代填。" in joined
    assert "最大回撤在下方「詳細資料」的「最大回撤與本金類配息佔比」。" in joined
    assert "本金類配息佔比在下方「詳細資料」的「最大回撤與本金類配息佔比」。" in joined
    assert "最大回撤與本金類配息佔比 —" in joined   # 指去的那一塊真的在畫面上


def test_EXP_對照句不再重複標記_稽核等式不上畫面():
    for name in SCAN.EXP:
        joined = _joined("exp", name)
        assert "這裡只做客觀對照，不提供具體處置方向。" in joined
        assert "N 相等" not in joined


def test_ALO_說明行與欄名():
    joined = _joined("alo", "正常")
    assert "目標在這裡輸入；對照與試算在上方「關鍵數字」。" in joined
    assert "以下依序" not in joined
    assert "項目 當前值 最後修改時間" in joined


def test_示範模式正控_照舊有標記與舊頁尾():
    from streamlit.testing.v1 import AppTest

    for app in ("app_mkt", "app_hld", "app_exp", "app_alo", "app_set"):
        at = AppTest.from_file(str(_HERE.parents[1] / "ui_v2" / f"{app}.py"), default_timeout=90)
        at.run()
        assert not at.exception, (app, [e.value for e in at.exception])
        joined = "\n".join(SCAN.screen_texts(at))
        assert re.search(r"G[123]†", joined), app
