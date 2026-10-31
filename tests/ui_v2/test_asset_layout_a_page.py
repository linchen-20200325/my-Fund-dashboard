# -*- coding: utf-8 -*-
"""💼 我的資產 V7 Layout A（presentation de-duplication）的守衛（slow lane；需要 streamlit；固定 fixtures、不打網路）。

客戶 2026-10-31 裁示（`docs/DECISIONS.md` `DEC-2026-10-31-01`／`-02`；線框 `docs/v2/76_assets_v7_layout_a_wireframe.md`）：
頁級 P3 容器取代合併頁內 `HLD-0`／`ALO-0` 兩枚燈的重複 presentation。Domain Block Identity ≠ Presentation Instance。

本檔守：
- 驗收第 5 項：`HLD-0`／`ALO-0` 原 block semantics 不變（`_page_class`／`_state`／`_tone`／字樣／`lines`／`detail_lines`／`buttons` 前後相等；
  單獨 HLD／ALO 頁輸出不變——燈元件、燈標題、原說明句都還在）；
- 驗收第 6 項：前往 Sheets 鈕不遺失（key 不變、在持股明細第一個位置、出現條件不變、整頁只一枚）；
- 驗收第 7 項：omitted rows／Missing reason 附行不遺失；
- 驗收第 11 項：附行不得因合成／de-duplication 被吞掉（ALO-0 `_attached_n > 0` 的 `_page_class` 不得為 NORMAL／NO_HOLDING；
  真實模型逐格斷言每一區的附行至少出現在容器某一行）；
- 客戶線框裁示 2：合併頁 ALO-0 說明句改「此配置判讀只讀…」，單獨 ALO 頁與原常數不變。
"""

from __future__ import annotations

import copy
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
import test_p3_page_status_logic as P3  # noqa: E402  （借用真實模型建法 `_hld_side`／`_alo_side`；同一份管線）
from ui_v2 import status_class as SC  # noqa: E402
from ui_v2.alo import fixtures as AF  # noqa: E402
from ui_v2.alo import logic as AL  # noqa: E402
from ui_v2.asset import page as asset_page  # noqa: E402
from ui_v2.asset import page_status as PS  # noqa: E402
from ui_v2.hld import fixtures as HF  # noqa: E402
from ui_v2.hld import logic as HL  # noqa: E402

READS_PLAIN = "本燈只讀 目標對照卡 算出的差距，不指出方向。"
READS_MERGED = "此配置判讀只讀 目標對照卡 算出的差距，不指出方向。"
_SKIPPED_TABS = [{"tab": "PX-TEST-009", "error": "標頭格式有誤"}]


def _run(script):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_string(script, default_timeout=120)
    at.run()
    assert [e.value for e in at.exception] == []
    return at


def _md(at) -> str:
    return "\n".join(m.value for m in at.markdown)


def _flat(node, out=None):
    """AppTest 元素樹依畫面順序攤平成 [(type, key 或 value)]。"""
    out = [] if out is None else out
    kind = getattr(node, "type", None)
    if kind == "button":
        out.append(("button", node.key))
    elif kind == "markdown":
        out.append(("markdown", node.value))
    for child in getattr(node, "children", {}).values():
        _flat(child, out)
    return out


# ───────────────────────── 真實模型：變體集合 ─────────────────────────


def _alo_variants():
    for name in AF.ALL_SCENARIO_NAMES:
        base = AF.scenario(name)
        yield name, P3._alo_side(base)
        yield name + "+rows", P3._alo_side(P3._with(base, skipped_holdings=P3._SKIPPED))
        yield name + "+tabs", P3._alo_side(P3._with(base, skipped_tabs=_SKIPPED_TABS))


def _hld_variants():
    for name in HF.ALL_SCENARIO_NAMES:
        args = HF.scenario(name)
        yield name, P3._hld_side(args)
        ds = P3._with(args["dataset"], skipped_holdings=P3._SKIPPED)
        yield name + "+rows", P3._hld_side({**args, "dataset": ds})
    yield "h7", P3._hld_side({"dataset": P3._h7()})
    yield "h6", P3._hld_side({"dataset": P3._h6()})


# ───────────────────────── 驗收 11：附行不得被合成／de-duplication 吞掉 ─────────────────────────


def test_11_ALO0有附行_page_class不得是NORMAL或NO_HOLDING():
    seen_attached = 0
    for name, side in _alo_variants():
        block = AL.find_block(side["model"], "ALO-0")
        if block.get("_attached_n", 0) > 0:
            seen_attached += 1
            assert block["_page_class"] not in (SC.NORMAL, SC.NO_HOLDING), (name, block["_page_class"])
    assert seen_attached >= 3, "掃描集合裡至少要有幾個真的有附行的情境，否則這條守衛是空轉"


def test_11_真實模型逐格_每一區的附行都至少出現在容器某一行_不被合成行吞掉():
    alos = list(_alo_variants())
    hlds = list(_hld_variants())
    checked_alo = checked_hld = 0
    for hname, hside in hlds:
        h0 = HL.find_block(hside["model"], "HLD-0")
        for aname, aside in alos:
            a0 = AL.find_block(aside["model"], "ALO-0")
            out = PS.aggregate(hside, aside)
            shown = {line for row in out["rows"] for line in row["lines"]}
            a_att = a0["detail_lines"][:a0.get("_attached_n", 0)]
            for line in a_att:
                assert line in shown, (hname, aname, "ALO 附行被吞", line)
            for line in h0["lines"]:
                assert line in shown, (hname, aname, "HLD lines 被吞", line)
            checked_alo += bool(a_att)
            checked_hld += bool(h0["lines"])
    assert checked_alo > 0 and checked_hld > 0, "沒有任何格子真的有附行 → 守衛空轉"


def test_11_合併頁區段內說明行不重複容器已印的附行():
    for name, side in _alo_variants():
        block = AL.find_block(side["model"], "ALO-0")
        attached = block["detail_lines"][:block.get("_attached_n", 0)]
        entry = asset_page.alo0_entry_lines(block)
        for line in attached:
            assert line not in entry, (name, line)


# ───────────────────────── 驗收 5：block semantics 不變 ─────────────────────────


def test_5_說明行與aggregate都不回寫block_前後深拷貝相等():
    for name, side in list(_alo_variants()):
        before = copy.deepcopy(side["model"])
        asset_page.alo0_entry_lines(AL.find_block(side["model"], "ALO-0"))
        assert side["model"] == before, name
    for name, side in list(_hld_variants()):
        before = copy.deepcopy(side["model"])
        asset_page.hld0_entry_lines(HL.find_block(side["model"], "HLD-0"))
        assert side["model"] == before, name


def test_5_說明行取自block原字_只有ALO0說明句一字轉換():
    for name, side in _alo_variants():
        block = AL.find_block(side["model"], "ALO-0")
        n = block.get("_attached_n", 0)
        expect = [block["answers"]] + [READS_MERGED if line == READS_PLAIN else line for line in block["detail_lines"][n:]]
        assert asset_page.alo0_entry_lines(block) == expect, name
        if READS_PLAIN in block["detail_lines"]:
            assert READS_PLAIN not in asset_page.alo0_entry_lines(block) and READS_MERGED in asset_page.alo0_entry_lines(block)
    for name, side in _hld_variants():
        block = HL.find_block(side["model"], "HLD-0")
        assert asset_page.hld0_entry_lines(block) == [block["answers"], *block["detail_lines"]], name


def test_5_原說明句只在合併頁轉換_單獨ALO頁與常數不變():
    from ui_v2.alo import page as alo_page
    full_block = AL.find_block(P3._alo_side(AF.scenario("full"))["model"], "ALO-0")
    assert READS_PLAIN in full_block["detail_lines"], "block 本身（logic／plain 轉換後）的字樣不變"
    assert AL.TEXT_ALO0_READS == "本燈只讀 ALO-2 算出的差距，不指出方向。"
    assert alo_page._render_alo0 is not asset_page.alo0_entry_lines


def test_S1_上游說明句字樣改了_合併頁fail_loud_不靜默退回本燈():
    block = copy.deepcopy(AL.find_block(P3._alo_side(AF.scenario("full"))["model"], "ALO-0"))
    block["detail_lines"] = [line.replace("本燈只讀", "本判讀只讀") for line in block["detail_lines"]]
    with pytest.raises(ValueError, match="預期原字樣"):
        asset_page.alo0_entry_lines(block)


def test_5_單獨HLD與ALO頁輸出不變_燈元件與燈標題與原說明句都在():
    hld_md = _md(_run(F._HEAD + """
from ui_v2.hld import page as hld_page
hld_page.render(load_live=_hld_load, mask_error=str, save_live=lambda *_a: {"status": "saved"})
"""))
    assert hld_md.count('class="hld-lamp"') == 1 and "體檢結論燈" in hld_md and hld_md.count('data-block="HLD-0"') == 1
    alo_md = _md(_run(F._HEAD + """
from ui_v2.alo import page as alo_page
alo_page.render(load_live=_alo_load, mask_error=str)
"""))
    assert alo_md.count('class="alo-lamp"') == 1 and "差距結論燈" in alo_md and alo_md.count('data-block="ALO-0"') == 1
    assert READS_PLAIN in alo_md and READS_MERGED not in alo_md


# ───────────────────────── 合併頁：A 的畫面 ─────────────────────────


@pytest.fixture(scope="module")
def full():
    return _run(F.script("full"))


def test_合併頁_兩枚燈元件與燈標題不重複_data_block各恰一個(full):
    md = _md(full)
    assert md.count('class="alo-lamp"') == 0 and md.count('class="hld-lamp"') == 0
    assert "差距結論燈" not in md and "體檢結論燈" not in md
    assert md.count('data-block="ALO-0"') == 1 and md.count('data-block="HLD-0"') == 1


def test_合併頁_ALO0說明行在Primary圖下方_字樣改為此配置判讀(full):
    md = _md(full)
    assert READS_MERGED in md and READS_PLAIN not in md and md.count(READS_MERGED) == 1
    assert md.index('data-chart="primary"') < md.index('data-block="ALO-0"')
    alo0 = AL.find_block(P3._alo_side(AF.scenario("full"))["model"], "ALO-0")
    assert alo0["answers"] in md[md.index('data-block="ALO-0"'):]


def test_合併頁_HLD0說明行在持股明細內_按鈕與計數行位置(full):
    md = _md(full)
    assert md.index('class="ast-section-label">持股明細<') < md.index('data-block="HLD-0"')


def test_6_前往Sheets鈕_空持倉情境_key不變_在持股明細第一個位置_整頁一枚():
    at = _run(F.script("full", hld="empty", alo="noholding"))
    keys = [b.key for b in at.button]
    assert keys.count("HLD-0_btn_0") == 1
    flat = _flat(at.main)
    label = next(i for i, (t, v) in enumerate(flat) if t == "markdown" and 'class="ast-section-label">持股明細<' in v)
    nxt = flat[label + 1]
    assert nxt == ("button", "HLD-0_btn_0"), nxt            # 持股明細第一個位置
    assert 'data-block="HLD-0"' in flat[label + 2][1]       # 緊接著是說明容器（Sheets 維護說明與按鈕相鄰）
    assert "Sheets" in flat[label + 2][1]
    assert 'class="ast-pstatus"' not in flat[label + 1][1]  # 鈕不在 P3 HTML 容器內
    pstatus = next(v for t, v in flat if t == "markdown" and 'data-section="page-status"' in v)
    assert "<button" not in pstatus


def test_6_前往Sheets鈕_出現條件不變_有持倉的情境不畫(full):
    assert "HLD-0_btn_0" not in [b.key for b in full.button]
    block = HL.find_block(P3._hld_side(HF.scenario("full"))["model"], "HLD-0")
    assert not block["buttons"]


def test_7_omitted_rows附行_容器兩行照印_頁面總次數至少兩次():
    at = _run(F.script("full", hld="noexceed", alo="inband", skipped_rows=True))
    md = _md(at)
    status = next(m.value for m in at.markdown if 'data-section="page-status"' in m.value)
    needle = "未列入：缺持倉補充"
    assert status.count(needle) == 2 and md.count(needle) >= 2


def test_極端組合_容器照印Missing_error_reason_不因A隱藏():
    # 稽核指出的兩個組合：skipped_rows + hld=fetchfail；skipped_rows + hld_partial + alo=nofx
    at1 = _run(F.script("full", hld="fetchfail", skipped_rows=True))
    status1 = next(m.value for m in at1.markdown if 'data-section="page-status"' in m.value)
    assert "取數失敗" in status1 and "未列入：缺持倉補充" in status1
    at2 = _run(F.script("full", alo="nofx", hld_partial=True, skipped_rows=True))
    status2 = next(m.value for m in at2.markdown if 'data-section="page-status"' in m.value)
    assert status2.count("未列入：缺持倉補充") == 2
