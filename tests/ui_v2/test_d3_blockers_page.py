# -*- coding: utf-8 -*-
"""D-3 阻擋項（客戶 2026-10-30 裁示 `DEC-2026-10-30-04`）在畫面上的守衛（slow lane；需要 streamlit；AppTest，固定 fixtures、不打網路）。

單頁 `💼 我的持股`、單頁 `⚖️ 資產配置` 與合併頁 `💼 我的資產` 各跑一次：
- F-2：持股只評估一部分（74 H7）時，燈那一區照舊「無偏離項」之外，也畫出 `HLD-3` 卡上既有的「◇ 資料未備」字樣；
- F-18／BL-0411：有持倉列被略過時，兩枚燈都不寫正常字樣，略過的那一列與 L2 原因字畫在燈下；合併頁一句主判讀不寫「持有 N 檔」。
- F-13／F-19：配置有類別沒評估到時，整頁沒有一處「各類別皆在容許帶內」。
"""

from __future__ import annotations

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
from ui_v2.alo import logic as alo_logic  # noqa: E402

_SKIPPED_FORMAL = "◇ 資料未備：PX-TEST-001 第 7 列（ZZ9999） 未列入：缺持倉補充"
_PARTIAL_FORMAL = "配息與本金卡：◇ 資料未備"


def _run_script(script):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_string(script, default_timeout=120)
    at.run()
    assert [e.value for e in at.exception] == []
    return at


def _md(at) -> str:
    return "\n".join(m.value for m in at.markdown)


def _hero(at) -> str:
    return re.search(r'class="ast-hero"[^>]*>([^<]+)<', _md(at)).group(1)


_SINGLE_HEAD = F._HEAD


def _single_hld(partial=False, skipped=False):
    body = (F._HLD_PARTIAL if partial else "") + (F._SKIPPED_ROWS if skipped else "") + """
from ui_v2.hld import page as hld_page
hld_page.render(load_live=_hld_load, mask_error=str, save_live=lambda *_a: {"status": "saved"})
"""
    return _run_script(_SINGLE_HEAD + body)


def _single_alo(alo="inband", skipped=False, extra=""):
    head = _SINGLE_HEAD.replace('alo_fixtures.scenario("full")', f"alo_fixtures.scenario({alo!r})")
    body = extra + (F._SKIPPED_ROWS if skipped else "") + """
from ui_v2.alo import page as alo_page
alo_page.render(load_live=_alo_load, mask_error=str)
"""
    return _run_script(head + body)


# ───────────────────────── F-2 ─────────────────────────


def test_F2_單頁我的持股_H7燈下畫出既有缺值字樣():
    md = _md(_single_hld(partial=True))
    assert "無偏離項" in md and _PARTIAL_FORMAL in md


def test_F2_合併頁_H7持股明細燈下畫出既有缺值字樣():
    md = _md(_run_script(F.script("full", hld_partial=True)))
    assert _PARTIAL_FORMAL in md


# ───────────────────────── F-18／BL-0411 ─────────────────────────


def test_BL0411_單頁我的持股_燈不寫正常字樣_略過的列與原因畫在燈下_不畫持有N檔():
    md = _md(_single_hld(partial=False, skipped=True))
    assert _SKIPPED_FORMAL in md
    assert "無偏離項" not in md
    assert not re.search(r"持有 \d+ 檔　", md)                      # 三個計數那一行不畫（不假裝覆蓋完整集合）


def test_BL0411_單頁資產配置_帶內改無法判定_略過的列畫在燈下():
    md = _md(_single_alo("inband", skipped=True))
    assert alo_logic.TEXT_ALL_IN_BAND not in md
    assert alo_logic.TEXT_UNDECIDABLE_GAP in md and _SKIPPED_FORMAL in md


def test_BL0411_合併頁_主判讀持有檔數無法判定_兩枚燈下都畫略過的列():
    at = _run_script(F.script("full", alo="inband", skipped_rows=True))
    md = _md(at)
    assert _hero(at) == "持有檔數無法判定；配置差距無法判定。"
    assert md.count(_SKIPPED_FORMAL) == 2                         # 配置燈下一次、持股燈下一次（各自原狀態與 reason 照留）
    assert alo_logic.TEXT_ALL_IN_BAND not in md
    assert not re.search(r"持有 \d+ 檔　", md)


# ───────────────────────── F-13／F-19 ─────────────────────────


def test_F19_單頁資產配置_有值而沒有目標的類別_整頁沒有皆在帶內():
    extra = "_alo_dataset = alo_fixtures._dataset(unbucket='CCCC', tolerance=40)\n"
    md = _md(_single_alo("full", extra=extra))
    assert alo_logic.TEXT_ALL_IN_BAND not in md and alo_logic.TEXT_UNDECIDABLE_GAP in md


def test_雙方完整正常_合併頁照舊皆在帶內_沒有略過字樣():
    at = _run_script(F.script("full", alo="inband"))
    assert _hero(at) == f"持有 3 檔基金；{alo_logic.TEXT_ALL_IN_BAND}。"
    assert "未列入：" not in _md(at)
