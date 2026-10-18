# -*- coding: utf-8 -*-
"""客戶 2026-10-18 第二筆裁示 BL-0374 C3（`docs/DECISIONS.md` `DEC-2026-10-18-02`；44 第七節第三小節之十其一）的畫面測試。

C3 維持現狀：重新取數不能按時（設定試算表未設定、按鈕停用），`SET-0` 燈下那一枚導覽照常顯示；導覽只帶使用者到
對應位置，不代表重新取數可以執行，也不得因此觸發取數、重新整理或重新讀取。程式行為不改，本檔只釘住：
- 導覽是純 HTML 同頁錨點（`<a href="#…">`，沒有 `onclick`、不是 `st.button`），按下不會重跑頁面；
- 整次渲染（含導覽）裡，重新取數的回呼一次都沒被呼叫、讀取回呼只被頁面本身呼叫一次；
- 落點那一枚「重新取數」照舊停用（既有 `test_set_reshape_page.py::test_未設定_導覽照舊顯示_它指向的重新取數停用` 照留）。
用 `tests/ui_v2/_plain_scan.py` 的設定與診斷正式模式腳本（真 L2 ＋ 真 L1 ＋ 假 gspread，不打網路）。
"""

from __future__ import annotations

import pathlib
import sys

import pytest

pytestmark = pytest.mark.slow

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_ROOT))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

import _plain_scan as SCAN  # noqa: E402

from ui_v2 import sections  # noqa: E402

_RENDER = "page.render(load_live=source.load_live, save_live=source.save_setting, refetch_live=source.refetch)"
_COUNTED = """
def _count(name, fn):
    def wrapped(*a, **k):
        st.session_state[name] = st.session_state.get(name, 0) + 1
        return fn(*a, **k)
    return wrapped
page.render(load_live=_count("_c3_load", source.load_live), save_live=_count("_c3_save", source.save_setting),
            refetch_live=_count("_c3_refetch", source.refetch))
""".strip()


def _counted(script: str) -> str:
    assert script.count(_RENDER) == 1
    body = "\n".join("    " + line for line in _COUNTED.splitlines())
    return script.replace("    " + _RENDER, body) if ("    " + _RENDER) in script else script.replace(_RENDER, _COUNTED)


def _run(script):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(script, default_timeout=90)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_C3_未設定_導覽不觸發取數或重新讀取():
    at = _run(_counted(SCAN.SCRIPTS["set"]["未設定"]))
    values = [m.value for m in at.markdown]
    navs = [v for v in values if f'href="#{sections.SET_NAV_ANCHOR}"' in v]
    assert len(navs) == 1, navs
    nav = navs[0]
    assert "<a " in nav and sections.SET_NAV_LABEL in nav
    for word in ("onclick", "<script", "<form", "javascript:"):
        assert word not in nav, word
    assert sections.SET_NAV_LABEL not in [b.label for b in at.button]      # 不是 st.button：按下不重跑、不取數
    refetch = [b for b in at.button if b.label == "重新取數"]
    assert len(refetch) == 1 and refetch[0].disabled                        # 落點那一枚照舊停用（C3 維持現狀）
    state = at.session_state
    assert "_c3_refetch" not in state                                       # 重新取數一次都沒被呼叫
    assert "_c3_save" not in state
    assert state["_c3_load"] == 1                                           # 只有頁面本身讀一次


# ───────────────────────── BL-0375：持倉體檢正式模式（真 L2 ＋ 假上游） ─────────────────────────


@pytest.mark.parametrize("name, retreat", [("退回預存過期", True), ("超過10日", False)])
def test_BL0375_持倉體檢_退回預存又過期畫禁止號與日期_非退回照舊資料未備(name, retreat):
    at = _run(SCAN.SCRIPTS["hld"][name])
    md = "\n".join(m.value for m in at.markdown)
    line = "改用 2026-09-18 的預存淨值"
    assert (line in md) is retreat
    assert ("⛔ 取數失敗" in md) is retreat
    assert "淨值取自預存序列，不是本次取得；最近一筆" not in md      # 過期的那一份不再掛「⬜ 資料未備」那一類副標
    assert "資料未備" in md                                          # 不是預存的過期檔照舊資料未備
    status = next(v for v in at.markdown if "v2-status-line" in v.value).value
    assert ("⛔ 取數失敗：淨值" in status) is retreat                # 資料狀態行記到淨值這一類
