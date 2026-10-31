# -*- coding: utf-8 -*-
"""P3 頁級狀態容器在合併頁 `💼 我的資產` 上的畫面守衛（slow lane；需要 streamlit；AppTest，固定 fixtures、不打網路）。

客戶 2026-10-30 裁示 P3／β（`DEC-2026-10-30-04`）。純函式 aggregation 的組合矩陣見 `test_p3_page_status_logic.py`；本檔守：
容器只有一個（Visual Budget 計 1 個）、頭條與第二行、Q5／Q6 合成、PE 另一區照畫、沒有 Active 時不畫、兩區說明容器與 data-block 錨點（V7 Layout A 後不再畫燈元件）各自區段的字樣不變。
"""

from __future__ import annotations

import html
import pathlib
import re
import sys

import pytest

pytestmark = pytest.mark.slow

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

import _ast_fixture as F  # noqa: E402


def _run(script):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_string(script, default_timeout=120)
    at.run()
    assert [e.value for e in at.exception] == []
    return at


def _md(at) -> str:
    return "\n".join(m.value for m in at.markdown)


def _status(at):
    """容器的 (kind, 容器 html, [(class, area, 可見文字)…])；沒有容器 → None。"""
    blocks = [m.value for m in at.markdown if 'data-section="page-status"' in m.value]
    assert len(blocks) <= 1, "頁級狀態容器只能有一個（Visual Budget 計 1 個）"
    if not blocks:
        return None
    block = blocks[0]
    kind = re.search(r'data-kind="([^"]+)"', block).group(1)
    rows = []
    for match in re.finditer(r'<div class="ast-pstatus-(?:head|second)" data-row="([^"]*)" data-area="([^"]*)">(.*?)</div></div>', block, re.S):
        text = html.unescape(re.sub(r"<[^>]+>", " ", match.group(3)))
        rows.append((match.group(1), match.group(2), re.sub(r"\s+", " ", text).strip()))
    return kind, block, rows


def test_兩區都完整評估且正常_合成一行_照印兩句原字_不寫正常():
    at = _run(F.script("full", hld="noexceed", alo="inband"))
    kind, block, rows = _status(at)
    assert kind == "merged_normal" and len(rows) == 1
    assert "無偏離項；各類別皆在容許帶內" in rows[0][2] and "正常" not in rows[0][2]
    assert rows[0][2].startswith("⬜")                      # 符號與狀態字都在，不靠顏色
    assert "狀態：中性" in rows[0][2]


def test_頭條加另一行_兩區都有偏離_持股先_配置在第二行():
    at = _run(F.script("full"))                              # 持股 full（◆）、配置 full（◆）
    kind, _block, rows = _status(at)
    assert kind == "two_rows" and [r[1] for r in rows] == ["持股", "配置"] and [r[0] for r in rows] == ["需要注意", "需要注意"]
    assert rows[0][2].startswith("◆") and "持股：" in rows[0][2] and "配置：" in rows[1][2]
    assert "與目標差" in rows[1][2]


def test_配置有類別沒評估到_A6m_持股正常也不能合成帶內_頭條是資料未備():
    at = _run(F.script("full", hld="noexceed", blank_target=True))
    kind, _block, rows = _status(at)
    assert kind == "two_rows" and rows[0][0] == "資料未備" and rows[0][1] == "配置"
    assert "配置差距無法判定" in rows[0][2] and "各類別皆在容許帶內" not in rows[0][2]
    assert rows[1][0] == "無偏離" and rows[1][1] == "持股"       # 正常那一區仍照印在第二行
    assert "各類別皆在容許帶內" not in _md(at)               # 全頁沒有一處帶內字樣（F-13）


def test_持股只評估一部分_H7_頭條是只評估一部分_帶既有缺值原因_不與正常合成():
    at = _run(F.script("full", hld_partial=True, alo="inband"))
    kind, _block, rows = _status(at)
    assert kind == "two_rows" and rows[0][0] == "只評估一部分" and rows[0][1] == "持股"
    assert "無偏離項" in rows[0][2] and "◇ 資料未備" in rows[0][2]
    assert rows[1][0] == "無偏離" and rows[1][1] == "配置"


def test_取數失敗_一區拋例外_該區是頭條_另一區照畫():
    at = _run(F.script("alo_fail"))
    kind, _block, rows = _status(at)
    assert rows[0][0] == "取數失敗" and rows[0][1] == "配置" and "⛔" in rows[0][2] and "狀態：取數失敗" in rows[0][2]
    assert rows[1][1] == "持股" and rows[1][0] == "需要注意"
    at = _run(F.script("hld_fail"))
    _kind, _block, rows = _status(at)
    assert rows[0][0] == "取數失敗" and rows[0][1] == "持股" and rows[1][1] == "配置"


def test_兩區同為尚未建立任何持倉_合成一行_前往Sheets鈕整頁只出現一次():
    at = _run(F.script("full", hld="empty", alo="noholding"))
    kind, _block, rows = _status(at)
    assert kind == "merged_no_holding" and len(rows) == 1 and "持股與配置：尚未建立任何持倉" in rows[0][2]
    # 容器本身不畫鈕；持股區段 `HLD-0` 說明容器前的那一枚（既有；A 後燈元件已取消、鈕位置保留）是唯一與頁級狀態對應的前往 Sheets 鈕。
    # （`ALO-4` 卡自己另有一枚，屬該卡既有的空狀態，不是頁級狀態的鈕。）
    keys = [b.key for b in at.button]
    assert keys.count("HLD-0_btn_0") == 1 and not [k for k in keys if k and k.startswith("ast_status")]


def test_略過的持倉列_兩區都是資料未備_附行照印():
    at = _run(F.script("full", hld="noexceed", alo="inband", skipped_rows=True))
    kind, _block, rows = _status(at)
    assert [r[0] for r in rows] == ["資料未備", "資料未備"] and [r[1] for r in rows] == ["持股", "配置"]
    assert all("未列入" in r[2] for r in rows)


def test_沒有ActiveSheet_整頁改畫尚未選定_不畫頁級狀態容器():
    at = _run(F.script("no_active"))
    assert _status(at) is None


# ~~`test_容器只有一個_兩枚燈各自區段的字樣與判定不變`~~ → V7 Layout A 實作批（2026-10-31；`DEC-2026-10-31-02`；有意識的更正，不是漏刪）：
# 合併頁已不畫兩枚燈元件，改名為「兩區說明容器與 data-block 錨點仍在」；斷言內容（容器唯一、錨點在、字樣不變）一項未放寬。
def test_容器只有一個_兩區說明容器與data_block錨點仍在各自區段_字樣與判定不變():
    at = _run(F.script("full", hld="noexceed", alo="inband"))
    md = _md(at)
    assert md.count('data-section="page-status"') == 1
    assert 'data-block="HLD-0"' in md and 'data-block="ALO-0"' in md          # 兩個 domain block 的 data-block 錨點仍在各自區段（燈元件已由 A 取消，錨點留在說明容器）
    assert "各類別皆在容許帶內" in md and "無偏離項" in md
