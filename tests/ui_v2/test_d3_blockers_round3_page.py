# -*- coding: utf-8 -*-
"""D-3 阻擋項修正第三輪（獨立稽核 B-NEW-1、should-fix 1、should-fix 3；客戶 2026-10-30 裁示 `DEC-2026-10-30-04` F-18）在畫面上的守衛
（slow lane；需要 streamlit；AppTest，固定 fixtures、不打網路）。

- **B-NEW-1**：有 DIRECT 列、保單分頁上的持倉列又全數被略過時，單頁 `💼 我的持股` 與合併頁 `💼 我的資產` 的持股側不再畫成
  「⛔ 資料 取數失敗」；DIRECT 那一行黃字與略過的列都畫出來。有持倉時同一組合也照常畫完。
- **should-fix 1**：單頁 `⚖️ 資產配置` 與合併頁「配置明細」的「歸屬明細」標題不寫「N 檔」、表尾合計之後接略過的列；
  「分組定義」不寫「未指派 0 檔」。
- **should-fix 3**：持倉列全數被略過時，「單檔展開」「最大回撤與本金類配息佔比」兩個展開區標題寫「◇ 資料未備：持倉」。
"""

from __future__ import annotations

import pathlib
import re
import sys

import pytest

pytestmark = pytest.mark.slow

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_HERE))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

import _ast_fixture as F  # noqa: E402

_SKIPPED_ROW = {"tab": "PX-TEST-001", "row": 3, "policy_id": "PX-TEST-001", "fund_code": "ZZ8888", "reasons": ["缺持倉補充"]}
_SKIPPED_FORMAL = "◇ 資料未備：PX-TEST-001 第 3 列（ZZ8888） 未列入：缺持倉補充"
_DIRECT_LINE = "⚠ DIRECT 列暫不支援，該筆不計入體檢（2 筆）"
_FAILED = "取數失敗：本頁暫時無法判定"

# 真的走 `assemble_live_load`（L2 輸出形狀，含 `direct` 與 `skipped_holdings`），再交給頁面。
_HLD_LOAD = f"""
import sys, copy
sys.path.insert(0, {str(_ROOT)!r}); sys.path.insert(0, {str(_HERE)!r})
import test_hld_live_assemble as TH
_tables = TH._l2_holding_tables(direct=TH._l2_direct())
_HOLDINGS = HOLDINGS
if not _HOLDINGS:
    _tables["holding"] = []
_tables["skipped_holdings"] = [{_SKIPPED_ROW!r}]
_kw = TH._kwargs(holding_tables=_tables, key_results=TH._key_results(_tables["holding"]))
if not _HOLDINGS:
    _kw["nav_table"] = TH._empty_nav_table()
_loaded = TH.live.assemble_live_load(**_kw)
_loaded["live_args"]["today"] = TH._TODAY
"""


def _run(script):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_string(script, default_timeout=180)
    at.run()
    assert [e.value for e in at.exception] == []
    return at


def _md(at) -> str:
    return "\n".join(m.value for m in at.markdown)


def _hld_single(holdings: bool):
    return _run(_HLD_LOAD.replace("_HOLDINGS = HOLDINGS", f"_HOLDINGS = {holdings!r}") + """
from ui_v2.hld import page as HP
HP.render(load_live=lambda: _loaded, mask_error=str, save_live=lambda *_a: {"status": "saved"})
""")


def _merged(holdings: bool):
    return _run(_HLD_LOAD.replace("_HOLDINGS = HOLDINGS", f"_HOLDINGS = {holdings!r}") + f"""
from ui_v2.alo import fixtures as alo_fixtures
from ui_v2.asset import page as P
_ads = dict(alo_fixtures.scenario({"inband" if holdings else "noholding"!r}),
            skipped_holdings=[{{k: v for k, v in {_SKIPPED_ROW!r}.items() if k != "policy_id"}}])
P.render(alo_live={{"load": lambda: {{"dataset": _ads, "notes": {{}}}}, "save": lambda *_a: {{"status": "saved"}}, "mask": str}},
         hld_live={{"load": lambda: _loaded, "save": lambda *_a: {{"status": "saved"}}, "mask": str}})
""")


# ───────────────────────── B-NEW-1 ─────────────────────────


def test_BNEW1_單頁我的持股_DIRECT加持倉全數略過_不畫取數失敗_兩種揭露都在():
    at = _hld_single(False)
    md = _md(at)
    assert _FAILED not in md and [e.value for e in at.error] == []
    assert _DIRECT_LINE in md and _SKIPPED_FORMAL in md
    assert "尚未建立任何持倉" not in md
    labels = [e.label for e in at.expander]
    assert "單檔展開　—　◇ 資料未備：持倉 · DIRECT 2 筆未列入" in labels


def test_BNEW1_單頁我的持股_DIRECT加略過的列加有持倉_照常畫完():
    at = _hld_single(True)
    md = _md(at)
    assert _FAILED not in md and [e.value for e in at.error] == []
    assert _DIRECT_LINE in md and _SKIPPED_FORMAL in md


def test_BNEW1_合併頁_DIRECT加持倉全數略過_持股側不畫取數失敗_略過的列可辨識():
    at = _merged(False)
    md = _md(at)
    assert _FAILED not in md
    assert _DIRECT_LINE in md and _SKIPPED_FORMAL in md
    assert "尚未建立任何持倉" not in md


def test_BNEW1_合併頁_DIRECT加略過的列加有持倉_照常畫完():
    at = _merged(True)
    md = _md(at)
    assert _FAILED not in md
    assert _DIRECT_LINE in md and _SKIPPED_FORMAL in md


# ───────────────────────── should-fix 1 ─────────────────────────

_ALO_SKIPPED = "◇ 資料未備：PX-TEST-001 第 7 列（ZZ9999） 未列入：缺持倉補充"


def _single_alo_skipped():
    head = F._HEAD.replace('alo_fixtures.scenario("full")', 'alo_fixtures.scenario("inband")')
    return _run(head + F._SKIPPED_ROWS + """
from ui_v2.alo import page as alo_page
alo_page.render(load_live=_alo_load, mask_error=str)
""")


def test_SF1_單頁資產配置_歸屬明細不寫N檔_合計之後接略過的列_分組定義不寫未指派0檔():
    at = _single_alo_skipped()
    labels = [e.label for e in at.expander]
    assert "歸屬明細　—　◇ 資料未備：持倉" in labels   # ~~「歸屬明細　—　◇ 資料未備」~~（第三輪補：帶資料類；有意識的更正，不是漏刪）
    assert not any(re.match(r"歸屬明細　—　\d+ 檔", label) for label in labels)
    group = next(label for label in labels if label.startswith("分組定義"))
    assert "未指派 ◇ 資料未備：持倉" in group and not re.search(r"未指派 \d+ 檔", group)   # 第三輪補：帶資料類
    md = _md(at)
    total = md.index("總體佔比合計")
    assert _ALO_SKIPPED in md[total:]


def test_SF1_合併頁配置明細_歸屬明細不寫N檔_略過的列在表尾_基金占比只接一次():
    at = _run(F.script("full", alo="inband", skipped_rows=True))
    md = _md(at)
    assert not re.search(r"歸屬明細　—　\d+ 檔", md) and "歸屬明細　—　◇ 資料未備：持倉" in md   # 第三輪補：帶資料類
    assert not re.search(r"未指派 \d+ 檔", md)
    share = md[md.index(">基金占比</div>"):md.index(">各檔區間報酬（原幣）</div>")]
    assert share.count(_ALO_SKIPPED) == 1


# ───────────────────────── should-fix 3 ─────────────────────────


def test_SF3_單頁我的持股_持倉全數被略過_展開區標題寫資料未備持倉():
    head = F._HEAD.replace('hld_fixtures.scenario("full")', 'hld_fixtures.scenario("empty")')
    at = _run(head + F._SKIPPED_ROWS + """
from ui_v2.hld import page as hld_page
hld_page.render(load_live=_hld_load, mask_error=str, save_live=lambda *_a: {"status": "saved"})
""")
    labels = [e.label for e in at.expander]
    assert "單檔展開　—　◇ 資料未備：持倉" in labels
    assert "最大回撤與本金類配息佔比　—　◇ 資料未備：持倉" in labels


def test_SF1_單頁我的持股_有持倉而有略過的列_單檔展開與最大回撤標題不寫N檔():
    at = _run(F._HEAD + F._SKIPPED_ROWS + """
from ui_v2.hld import page as hld_page
hld_page.render(load_live=_hld_load, mask_error=str, save_live=lambda *_a: {"status": "saved"})
""")
    labels = [e.label for e in at.expander]
    assert "單檔展開　—　◇ 資料未備：持倉 · 同時最多展開一檔" in labels
    assert "最大回撤與本金類配息佔比　—　◇ 資料未備：持倉 · 有值取不到或不適用" in labels
    assert not any(re.match(r"(單檔展開|最大回撤與本金類配息佔比)　—　\d+ 檔", label) for label in labels)
    assert _md(at).count("◇ 資料未備：PX-TEST-001 第 7 列（ZZ9999） 未列入：缺持倉補充") >= 3   # 燈下、單檔展開、最大回撤表


def test_補2_合併頁各檔區間報酬_有持倉而有略過的列_接一次():
    at = _run(F.script("full", alo="inband", skipped_rows=True))
    md = _md(at)
    returns = md[md.index(">各檔區間報酬（原幣）</div>"):]
    limits = returns[returns.index('<div class="pc-detail-name">限制</div>'):]
    limits = limits[:limits.index("</ul>")]
    assert limits.count(_ALO_SKIPPED) == 1 and limits.rstrip().endswith(f"<li>{_ALO_SKIPPED}</li>")
