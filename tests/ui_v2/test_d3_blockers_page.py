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
    # ~~`== 2`（配置燈下一次、持股燈下一次）~~ → D-3 第二輪（獨立稽核 S2，`DEC-2026-10-30-04` F-18；有意識的更正，不是漏刪）：
    # 「基金占比」表尾的佔比合計之後也接一次（件數與合計不假裝覆蓋完整集合）。各自原狀態與 reason 照留。
    # ~~`== 3`（配置燈下、基金占比表尾、持股燈下）~~ → D-3 第三輪（獨立稽核 should-fix 1，`DEC-2026-10-30-04` F-18；有意識的更正，
    # 不是漏刪）：「配置明細」容器內的「歸屬明細」（`ALO-6`）表尾合計之後也接一次；「基金占比」讀同一份表尾，仍只一次。
    # ~~`== 4`~~ → D-3 第三輪補（總管派工；有意識的更正，不是漏刪）：持股側「單檔展開」（`HLD-5`）與「最大回撤與本金類配息佔比」
    # （`HLD-8`）的說明區最後也各接一次（件數改「◇ 資料未備：持倉」）。
    # ~~`== 6`~~ → D-3 第三輪補 2（總管派工；有意識的更正，不是漏刪）：「各檔區間報酬（原幣）」的限制區最後也接一次。
    # ~~`== 7`~~ → P3 頁級狀態實作批（2026-10-31；`DEC-2026-10-30-04`；有意識的更正，不是漏刪）：頁頂的頁級狀態容器兩行（持股、配置）
    # 各照印該區自己的附行（略過的列），多 2 次。各區段內的原次數照舊。
    assert md.count(_SKIPPED_FORMAL) == 9      # 容器兩行＋配置燈下、基金占比、歸屬明細、持股燈下、單檔展開、最大回撤表、各檔區間報酬
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


# ───────────────────────── D-3 阻擋項修正第二輪（獨立稽核 B1／S1／S2／S3）─────────────────────────

_TAB_EXTRA = '_alo_dataset = dict(_alo_dataset, skipped_tabs=[{"tab": "PX-TEST-009", "error": "標頭格式有誤"}])\n'
_TAB_FORMAL = "⛔ PX-TEST-009 取數失敗"
_NO_HOLDING = "尚未建立任何持倉"
_FULL_SET_LINE = "目前這一組門檻下，沒有任何一檔超出。"


def test_B1_單頁資產配置_持倉為空只略過分頁_不寫尚未建立任何持倉_分頁在燈下():
    md = _md(_single_alo("noholding", extra=_TAB_EXTRA))
    assert _NO_HOLDING not in md
    assert alo_logic.TEXT_UNDECIDABLE_GAP in md and _TAB_FORMAL in md
    assert "⛔ 主要原因：持倉取數失敗" in md                          # 頁首認得那一句的資料類（不落到「認不出」）


def test_B1_單頁資產配置_有持倉略過分頁_分頁在燈下可辨識():
    md = _md(_single_alo("inband", extra=_TAB_EXTRA))
    assert alo_logic.TEXT_ALL_IN_BAND not in md and _TAB_FORMAL in md


def test_S1_單頁我的持股_零偏離而有略過的列_偏離提示卡不寫無偏離項與那一句():
    md = _md(_single_hld(partial=True, skipped=True))
    assert _FULL_SET_LINE not in md
    assert "無偏離項" not in md                                       # 燈與偏離提示卡都不寫
    assert md.count(_SKIPPED_FORMAL) >= 2                             # 燈下、偏離提示卡各一次


def test_S1_S2_合併頁_零偏離而有略過的列_需要注意不寫覆蓋完整集合_基金占比不寫N檔():
    at = _run_script(F.script("full", alo="inband", hld_partial=True, skipped_rows=True))
    md = _md(at)
    attention = md[md.index("③需要注意"):]
    assert "無偏離項" not in attention.split("持股明細")[0] and _FULL_SET_LINE not in md
    share = md[md.index(">基金占比</div>"):md.index(">各檔區間報酬（原幣）</div>")]
    assert not re.search(r">\d+ 檔<", share)                          # 件數那一枚不畫
    assert "◇ 資料未備" in share and _SKIPPED_FORMAL in share         # 改既有 ◇ 資料未備，並接上略過的列


def test_S3_單頁我的持股_H6逐檔配息取數失敗_燈下帶那一檔_不寫那一句():
    extra = '_hld_dataset["fund_errors"] = {"nav": {}, "dividend": {"CCCC": "上游逾時（探針）"}}\n'
    body = F._HLD_PARTIAL.replace('_hld_dataset["pending_tables"] = ["fund_profile", "dividend"]\n', "") + extra + """
from ui_v2.hld import page as hld_page
hld_page.render(load_live=_hld_load, mask_error=str, save_live=lambda *_a: {"status": "saved"})
"""
    md = _md(_run_script(_SINGLE_HEAD + body))
    assert "配息與本金卡：⛔ CCCC 取數失敗" in md
    assert "⛔ 主要原因：配息取數失敗" in md                          # 頁首照舊（燈那一句的資料類照抄卡上的）
    assert _FULL_SET_LINE not in md.split("偏離提示卡")[0]            # 燈那一區不寫（偏離提示卡那一句照舊：HLD-1 每一檔都評估過）
