# -*- coding: utf-8 -*-
"""💼 我的資產頁的執行期測試（BL-0525 Batch D；slow lane，需要 streamlit；AppTest，固定 fixtures、不打網路）。

守：D-1（容器內各 block 小標題、不巢狀展開區、block ID 全保留）、D-3（暫停：沒有任何合併燈，`HLD-0`／`ALO-0` 各一枚、各在其區段）、
D-5（四格 summary 在第一屏、誠實 Missing）、D-6（Secondary 兩張）、D-8（頁頂「持倉資料來源」一列、不改 OAuth）、
一側載入失敗不拖垮另一側、沒有 Active Sheet 的明確狀態。
"""

from __future__ import annotations

import pathlib
import re
import sys

import pytest

pytestmark = pytest.mark.slow

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_HERE))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

import _ast_fixture as F  # noqa: E402
from ui_v2 import active_gate, plain  # noqa: E402
from ui_v2.asset import overview as OV  # noqa: E402


def _run(variant="full", script=None):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_string(script or F.script(variant), default_timeout=120)
    at.run()
    return at


def _md(at) -> str:
    return "\n".join(m.value for m in at.markdown)


def _blocks(at) -> set:
    return set(re.findall(r'data-block="([A-Z]+-\d)"', _md(at)))


def _expanders(node, ancestors=0, found=None):
    """遞迴走 AppTest 元素樹：回 [(label, 祖先展開區數)]。"""
    found = [] if found is None else found
    is_exp = getattr(node, "type", None) == "expander"
    if is_exp:
        found.append((node.label, ancestors))
    for child in getattr(node, "children", {}).values():
        _expanders(child, ancestors + (1 if is_exp else 0), found)
    return found


@pytest.fixture(scope="module")
def full():
    return _run("full")


def test_full_渲染無例外(full):
    assert [e.value for e in full.exception] == []


def test_不巢狀展開區_D1(full):
    nested = [(label, depth) for label, depth in _expanders(full.main) if depth > 0]
    assert nested == [], nested


def test_block_ID全保留_容器內各塊有小標題(full):
    seen = _blocks(full)
    expected = {"ALO-0", "ALO-1", "ALO-2", "ALO-3", "ALO-4", "ALO-6", "ALO-7", "HLD-0", "HLD-1", "HLD-2", "HLD-3", "HLD-4",
                "HLD-6", "HLD-7", "HLD-8"}
    assert expected <= seen, expected - seen
    labels = [label for label, _ in _expanders(full.main)]
    # 單塊容器（沒有 data-block 小標題）＝該塊自己的展開區，標題是塊的正式標題：HLD-5、ALO-5
    assert any(label.startswith("單檔展開") for label in labels)      # HLD-5
    assert any(label.startswith("試算結果匯出") for label in labels)   # ALO-5
    assert "ast-block-head" in _md(full)


def test_層3為3個容器_層4為2個容器_名稱依D11(full):
    labels = [label for label, _ in _expanders(full.main)]
    group = [label for label in labels if label.split("　—　")[0] in ("我的條件", "持股明細", "配置明細")]
    assert [g.split("　—　")[0] for g in group] == ["我的條件", "持股明細", "配置明細"]
    assert not any("證據" in label for label in labels)


def test_第一屏順序_selector在summary之前_summary在主判讀之前_主判讀在Primary之前(full):
    md = _md(full)
    marks = [md.index('class="ast-source-label"'), md.index('class="ast-title"'), md.index('class="ast-summary"'),
             md.index('class="ast-hero"'), md.index('data-section="primary"'), md.index('data-section="secondary"')]
    assert marks == sorted(marks), marks


def test_summary四格_一個容器_全是Missing(full):
    md = _md(full)
    assert md.count('class="ast-summary"') == 1
    slots = re.findall(r'data-slot="([^"]+)"', md)
    assert slots == ["總資產", "總損益", "報酬", "配息"]
    values = re.findall(r'class="ast-slot-value"[^>]*>([^<]+)<', md)
    assert values == ["◇ 資料未備"] * 4


def test_一句主判讀只取既有值(full):
    sentence = re.search(r'class="ast-hero"[^>]*>([^<]+)<', _md(full)).group(1)
    assert re.fullmatch(r"持有 \d+ 檔基金；(目前最大配置差距在 .+|各類別皆在容許帶內|配置差距無法判定)。", sentence), sentence
    assert not any(w in sentence for w in ("加碼", "減碼", "買", "賣"))


def test_沒有合併燈_D3暫停_HLD0與ALO0各一枚各在其區段(full):
    md = _md(full)
    assert md.count('class="alo-lamp"') == 1 and md.count('class="hld-lamp"') == 1
    assert md.count('data-block="ALO-0"') == 1 and md.count('data-block="HLD-0"') == 1
    for token in ("page-light", "combined", "ast-lamp", "ast-light"):
        assert token not in md, token
    # ALO-0 在 Primary 區（資產配置標題之後、持股明細標題之前）；HLD-0 在持股明細區
    holdings_label = md.index('class="ast-section-label">持股明細<')
    assert md.index('data-section="primary"') < md.index('data-block="ALO-0"') < holdings_label < md.index('data-block="HLD-0"')


def test_Secondary恰兩張_基金占比與各檔區間報酬_全列捲動區(full):
    md = _md(full)
    assert md.count('data-section="secondary"') == 2
    assert OV.SHARE_TITLE in md and OV.RETURNS_TITLE in md
    assert md.count('class="ast-scroll"') == 2
    assert "原幣，不合計" in md


def test_Primary現況與目標_兩條_直接標籤(full):
    md = _md(full)
    assert OV.PRIMARY_TITLE in md
    assert md.count(f">{OV.TEXT_CURRENT}<") >= 1 and md.count(f">{OV.TEXT_TARGET}<") >= 1
    assert 'data-chart="primary"' in md


def test_頁尾兩區不負責什麼都在(full):
    footer = re.search(r'class="ast-footer">([^<]+)<', _md(full)).group(1)
    assert plain.PLAIN_FOOTERS["hld"] in footer
    assert plain.PLAIN_FOOTERS["alo"].replace(OV.SELF_POINTER, "") in footer       # 只去掉指向本頁自己的半句
    assert "不產生再平衡動作" in footer and "不提供調整方向" in footer


def test_尚未取得群組在_九項名稱在摘要列(full):
    labels = [label for label, _ in _expanders(full.main)]
    group = [label for label in labels if label.startswith("▸ 尚未取得")]
    assert len(group) == 1 and all(name in group[0] for name, _ in OV.MISSING_GROUP_ITEMS)


def test_寫入控制沒有新增_ALO3存檔照舊停用(full):
    labels = [b.label for b in full.button]
    assert not any("存檔" in label and not b.disabled for label, b in zip(labels, full.button))


# ───────────────────────── 一側失敗、沒有 Active ─────────────────────────


def test_配置側載入失敗_持股側照常_區段改畫一句狀態():
    at = _run("alo_fail")
    assert [e.value for e in at.exception] == []
    md = _md(at)
    assert 'class="ast-err"' in md and "alo-load-boom" not in md      # 原文只進進階診斷，一般畫面一句狀態
    assert "HLD-0" in _blocks(at) and "HLD-2" in _blocks(at)
    assert "ALO-0" not in _blocks(at)


def test_持股側載入失敗_配置側照常():
    at = _run("hld_fail")
    assert [e.value for e in at.exception] == []
    md = _md(at)
    assert 'class="ast-err"' in md and "hld-load-boom" not in md
    assert "ALO-0" in _blocks(at) and "ALO-2" in _blocks(at)
    assert OV.RETURNS_TITLE in md                                      # Secondary 兩張都還在（失敗那張改畫狀態句）


def test_沒有Active_整頁明確第三種狀態_沿既有字樣與連結():
    at = _run("no_active")
    assert [e.value for e in at.exception] == []
    md = _md(at)
    assert md.count(active_gate.TEXT_NO_ACTIVE) == 1
    assert OV.PAGE_TITLE in md and 'class="ast-summary"' not in md and "ALO-0" not in md
    assert any(active_gate.LINK_ELSEWHERE_TEXT in c.value for c in at.caption)   # 單頁入口沒有 settings_page → 說明行


# ───────────────────────── D-8：selector（重用既有 picker、不碰 OAuth）─────────────────────────

_PICKER_SCRIPT = F.script("full").replace("page.render(", """
import streamlit as st
_data = {"status": {"login_state": "logged_in", "email": "u@example.com",
                    "active_sheet": {"id": "S1", "name": "本A"}, "pending_sheet": None},
         "list": {"ok": True, "sheets": [{"id": "S1", "name": "本A"}, {"id": "S2", "name": "本B"}]}, "notice": None}
def _act(action, arg=None):
    st.session_state.setdefault("_calls", []).append((action, arg))
page.render(picker_live={"load": lambda: _data, "act": _act}, """, 1)


def test_已登入_頁頂有持倉資料來源_選單與動作沿用picker_live():
    at = _run(script=_PICKER_SCRIPT)
    assert [e.value for e in at.exception] == []
    assert [s.key for s in at.selectbox] == ["set_picker_select"]
    assert any(b.label == "重新列出" or "列出" in b.label for b in at.button)
    at.selectbox[0].select("S2").run()
    assert at.session_state["_calls"] == [("select", "S2")]
    md = _md(at)
    assert md.index("持倉資料來源") < md.index('class="ast-title"')


def test_未登入_selector列只有沒有Active字樣_不畫選單():
    at = _run("no_active")
    assert list(at.selectbox) == []


def test_不碰OAuth_asset套件不import任何登入或個人憑證模組():
    import ast as _ast
    banned = ("personal_oauth", "personal_session", "streamlit_oauth", "ui_v2.set.source", "infra", "services", "repositories")
    for path in (_ROOT / "ui_v2" / "asset").glob("*.py"):
        for node in _ast.walk(_ast.parse(path.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, _ast.Import) else \
                    [node.module or ""] if isinstance(node, _ast.ImportFrom) else []
            for name in names:
                assert not any(name == b or name.startswith(b + ".") or name.endswith("." + b) for b in banned), (path.name, name)
