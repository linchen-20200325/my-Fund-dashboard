# -*- coding: utf-8 -*-
"""正式模式 Answer-first 四段重排的畫面測試（Phase 3 P1-④；`docs/v2/44_fund_ui_ssot.md` 第七節第三小節之八其一）。

用 `tests/ui_v2/_plain_scan.py` 的四頁正式模式腳本（只用 fixtures／替身當 `load_live`，不打網路）。
驗的是段落順序與塊落在哪一段：①結論 → ②關鍵數字 → ③需要注意（有才畫）→ ④詳細資料。
示範模式不經過重排，另驗一次（44 第七節第三小節之八開頭第 4 條）。
"""

from __future__ import annotations

import pathlib
import sys

import pytest

pytestmark = pytest.mark.slow

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parents[1]))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

import _plain_scan as SCAN  # noqa: E402

from ui_v2 import plain, sections  # noqa: E402

_LIVE = [(page, name) for page in ("mkt", "hld", "exp", "alo") for name in SCAN.SCRIPTS[page] if name != "整頁失敗"]


def _run(script):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(script, default_timeout=90)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _md(at) -> list:
    return [m.value for m in at.markdown]


def _first(values, needle) -> int:
    hits = [i for i, v in enumerate(values) if needle in v]
    return hits[0] if hits else -1


def _label_index(values, label) -> int:
    hits = [i for i, v in enumerate(values) if f">{label}</div>" in v]
    return hits[0] if hits else -1


def _block_index(values, code) -> int:
    return _first(values, f'data-block="{code}"')


def _expander(at, prefix):
    found = [e for e in at.expander if e.label.startswith(prefix)]
    assert len(found) == 1, [e.label for e in at.expander]
    return found[0]


@pytest.mark.parametrize("page, name", _LIVE, ids=[f"{p}-{n}" for p, n in _LIVE])
def test_四段由上而下_需要注意有才畫(page, name):
    values = _md(_run(SCAN.SCRIPTS[page][name]))
    one = _label_index(values, plain.LABEL_LAYER1)
    two = _label_index(values, plain.LABEL_LAYER2)
    three = _label_index(values, plain.LABEL_ATTENTION)
    four = _label_index(values, plain.LABEL_DETAILS)
    assert -1 not in (one, two, four), (one, two, four)
    assert one < two < four
    if three != -1:
        assert two < three < four
    assert _label_index(values, plain.LABEL_LAYER3) > four
    assert _label_index(values, plain.LABEL_LAYER4) > four


def test_持倉體檢_HLD1畫在需要注意_關鍵數字只畫另兩張_結論另列三個計數():
    values = _md(_run(SCAN.SCRIPTS["hld"]["正常"]))
    two, three, four = (_label_index(values, x) for x in (plain.LABEL_LAYER2, plain.LABEL_ATTENTION, plain.LABEL_DETAILS))
    assert two < three < four
    assert three < _block_index(values, "HLD-1") < four
    assert two < _block_index(values, "HLD-2") < three
    assert two < _block_index(values, "HLD-3") < three
    counts = [v for v in values if v.startswith('<div class="hld-lamp-text">持有 ')]
    assert len(counts) == 1 and "◆ 需要注意" in counts[0] and "⬜ 無法判定" in counts[0]
    assert _first(values, counts[0]) < two
    assert "○" not in counts[0] and "正常" not in counts[0]
    hld1 = values[_block_index(values, "HLD-1")]
    assert "<td>◆ " in hld1     # 偏離列的基金名前加 ◆


def test_標的探索_結果清單框收合_EXP2與EXP3在框內_關鍵數字只剩條件():
    at = _run(SCAN.SCRIPTS["exp"]["正常"])
    values = _md(at)
    four = _label_index(values, plain.LABEL_DETAILS)
    assert _block_index(values, "EXP-1") < four
    box = _expander(at, sections.EXP_RESULT_TITLE)
    assert not box.proto.expanded
    inside = [m.value for m in box.markdown]
    assert _block_index(inside, "EXP-2") != -1 and _block_index(inside, "EXP-3") != -1
    assert _block_index(values, "EXP-2") > four and _block_index(values, "EXP-3") > four
    # 兩組勾選框跟著候選清單進了框（判定與鍵不變，只換位置）
    assert box.checkbox


def test_標的探索_有無法判定檔時_需要注意列出():
    values = _md(_run(SCAN.SCRIPTS["exp"]["stale"]))
    three = _label_index(values, plain.LABEL_ATTENTION)
    if three == -1:
        pytest.skip("這組情境沒有無法判定的檔（③ 不畫，由四段順序那一條驗）")
    assert any("檔無法判定：照列在結果清單中" in v for v in values[three:])


def test_資產配置_需要注意列帶外類別_ALO1在詳細資料收合_ALO3只畫開始試算入口():
    at = _run(SCAN.SCRIPTS["alo"]["正常"])
    values = _md(at)
    three, four = _label_index(values, plain.LABEL_ATTENTION), _label_index(values, plain.LABEL_DETAILS)
    assert three != -1
    assert any("◆ " in v and "超出容許帶" in v for v in values[three:four])
    target = _expander(at, plain.BLOCK_NAMES["ALO-1"])
    assert not target.proto.expanded
    assert _block_index([m.value for m in target.markdown], "ALO-1") != -1
    entry = _expander(at, sections.ALO_SCENARIO_ENTRY)
    assert not entry.proto.expanded
    assert _block_index([m.value for m in entry.markdown], "ALO-3") != -1
    assert _block_index(values, "ALO-2") < three


def test_市場總覽_有資料面例外才畫需要注意_沒有就不畫也不寫沒有例外():
    values = _md(_run(SCAN.SCRIPTS["mkt"]["局部失敗"]))
    three = _label_index(values, plain.LABEL_ATTENTION)
    assert three != -1
    assert values[three + 1].count(sections.MKT_DATA_PREFIX) == 1
    ok = _md(_run(SCAN.SCRIPTS["mkt"]["正常"]))
    if _label_index(ok, plain.LABEL_ATTENTION) == -1:
        assert not any(sections.MKT_DATA_PREFIX in v for v in ok)
    joined = "\n".join(ok)
    assert "沒有例外" not in joined and "變化大不大" not in joined


_DEMO = {
    "mkt": "from ui_v2.mkt import page\npage.render()\n",
    "hld": "from ui_v2.hld import page\npage.render()\n",
    "exp": "from ui_v2.exp import page\npage.render()\n",
    "alo": "from ui_v2.alo import page\npage.render()\n",
}


@pytest.mark.parametrize("page", sorted(_DEMO))
def test_示範模式不重排(page):
    at = _run(SCAN._HEAD + _DEMO[page])
    values = _md(at)
    assert _label_index(values, plain.LABEL_ATTENTION) == -1
    assert not [e for e in at.expander if e.label.startswith((sections.EXP_RESULT_TITLE, sections.ALO_SCENARIO_ENTRY))]
