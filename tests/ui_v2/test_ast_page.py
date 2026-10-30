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


# ═════════ 稽核回修（BL-0525 Batch D 第二輪）：頁級資料日、目標合計、容器標題帶狀態、n、失敗優先、F-13、小項 ═════════

from ui_v2 import page_health  # noqa: E402
from ui_v2.alo import logic as alo_logic  # noqa: E402


def _s(variant="full", **kw):
    return _run(script=F.script(variant, **kw))


def _hero(at) -> str:
    return re.search(r'class="ast-hero"[^>]*>([^<]+)<', _md(at)).group(1)


def _labels(at) -> list:
    return [label for label, _ in _expanders(at.main)]


def _container(at, name) -> str:
    return next(label for label in _labels(at) if label.split("　—　")[0] == name)


def _health(at, slug) -> dict:
    return at.session_state[page_health.STATE_KEY][slug]


def test_頁級資料日_兩側各一列_與單頁頁首同一組字(full):
    md = _md(full)
    dates = dict(re.findall(r"(資產配置|持股明細)　資料截至 ([^<]+)<", md))
    assert dates == {"資產配置": "2026-09-23", "持股明細": "2026-09-18"}      # 兩側各自的日期，沒有合成一個頁級日期
    assert f"資料日 {dates['資產配置'][5:]}" in md                              # Primary chip 仍在（沒有年的短寫法不再是唯一出處）
    assert md.index("資料截至") < md.index('class="ast-summary"')               # 在第一屏、summary 之前
    assert md.count("資料截至") == 2


@pytest.mark.parametrize("kw,side", [({"alo": "holdfail"}, "資產配置"), ({"alo": "first"}, "資產配置"), ({"hld": "empty"}, "持股明細")])
def test_頁級資料日_沒有日期就寫破折_不補不借另一側(kw, side):
    at = _s(**kw)
    assert [e.value for e in at.exception] == []
    md = _md(at)
    assert f"{side}　資料截至 —<" in md
    other = "持股明細" if side == "資產配置" else "資產配置"
    assert re.search(rf"{other}　資料截至 \d{{4}}-\d{{2}}-\d{{2}}<", md)


def test_頁級資料日_載入失敗那一側寫破折_另一側日期照寫():
    at = _run("alo_fail")
    md = _md(at)
    assert "資產配置　資料截至 —<" in md and re.search(r"持股明細　資料截至 \d{4}-\d{2}-\d{2}<", md)


def test_目標合計一行回到Primary_單頁頁面頂端那一行灰字():
    at = _s(alo="partial")
    md = _md(at)
    assert re.findall(r'class="alo-topline">([^<]*)<', md) == ["目標合計 90%"]
    assert md.index('data-section="primary"') < md.index('class="alo-topline"') < md.index('data-chart="primary"')
    assert 'class="alo-topline"' not in _md(_run("full"))                     # 目標合計剛好 100% 時單頁也不畫


def test_容器標題帶出有失敗的塊_ALO設定讀不到():
    at = _s(alo="settingfail")
    assert [e.value for e in at.exception] == []
    assert "目標輸入卡　—　⛔ 取數失敗" in _container(at, "我的條件")
    assert "歸屬明細　—　⛔ 取數失敗：使用者設定" in _container(at, "配置明細")
    assert "目標修改紀錄　—　⛔ 取數失敗：使用者設定" in _container(at, "配置明細")
    assert "檢視區間與門檻輸入、" in _container(at, "我的條件") and "檢視區間與門檻輸入　—" not in _container(at, "我的條件")   # 正常的塊只寫標題
    # 與單頁展開區標題同一個字面
    single = _single_alo_labels("settingfail")
    assert any(label.startswith("目標輸入卡　—　⛔ 取數失敗") for label in single)
    assert any(label.startswith("歸屬明細　—　⛔ 取數失敗：使用者設定") for label in single)


def _single_alo_labels(scenario):
    """單頁（正式模式）展開區標題：同一份 fixtures 資料，走 `alo/page.py::render(load_live=...)`。"""
    from streamlit.testing.v1 import AppTest
    code = (f"import sys; sys.path.insert(0, {str(_ROOT)!r})\n"
            "from ui_v2.alo import fixtures, page\n"
            f"page.render(load_live=lambda: {{'dataset': fixtures.scenario({scenario!r}), 'notes': {{}}}}, mask_error=str)")
    at = AppTest.from_string(code, default_timeout=120)
    at.run()
    assert [e.value for e in at.exception] == []
    return [label for label, _ in _expanders(at.main)]


def test_容器標題帶出資料未備與缺_持股與配置兩側():
    assert "缺 持倉" in _container(_s(alo="first"), "配置明細")
    assert "◇ 資料未備" in _container(_s(alo="partial"), "我的條件")
    assert "尚未設定" in _container(_s(hld="empty"), "我的條件")
    assert "◇ 資料未備：尚未建立任何持倉" in _container(_s(hld="empty"), "持股明細")


def test_容器標題正常時照舊只列標題_沒有被誤標狀態():
    at = _s(alo="inband")
    assert _container(at, "我的條件") == "我的條件　—　檢視區間與門檻輸入、目標輸入卡、分組定義"
    assert _container(at, "配置明細") == "配置明細　—　歸屬明細、目標修改紀錄"


@pytest.mark.parametrize("kw", [{"hld": "nothr"}, {"hld": "fetchfail"}, {"hld": "holdfail_nothr"}])
def test_主判讀的n取HLD2實際列出的檔數_門檻未設或燈紅也不寫無法判定(kw):
    at = _s(**kw)
    assert _hero(at).startswith("持有 3 檔基金；")
    assert "持有檔數無法判定" not in _md(at)
    assert re.search(r"基金 A", _md(at))                                      # Secondary 確實列了這幾檔


def test_主判讀的n_沒有任何持倉才寫無法判定_不寫0檔():
    hero = _hero(_s(hld="empty"))
    assert hero.startswith("持有檔數無法判定；") and "0 檔" not in hero


def test_F13_有類別沒評估到_主判讀不寫皆在容許帶內():
    for kw in ({"alo": "partial"}, {"alo": "unbkt"}, {"alo": "nobucket"}, {"alo": "inband", "blank_target": True}):
        at = _s(**kw)
        hero = _hero(at)
        assert "各類別皆在容許帶內" not in hero and "最大配置差距在" not in hero, (kw, hero)
        assert hero.endswith("配置差距無法判定。"), (kw, hero)


def test_F13_ALO0本身一字沒改_空白目標的inband燈仍寫皆在容許帶內_主判讀另擋():
    at = _s(alo="inband", blank_target=True)
    md = _md(at)
    assert md.count(alo_logic.TEXT_ALL_IN_BAND) == 1                         # ALO-0 那一行（既有缺陷 F-13 由客戶另裁，本批不改）
    assert _hero(at) == "持有 3 檔基金；配置差距無法判定。"
    assert _hero(_s(alo="inband")) == f"持有 3 檔基金；{alo_logic.TEXT_ALL_IN_BAND}。"   # 評估完整時照 ALO-0 既有字


def test_取數失敗優先於尚未設定_配置失敗_持股沒有Active():
    at = _run("alo_fail_hld_noactive")
    assert [e.value for e in at.exception] == []
    md = _md(at)
    assert OV.PAGE_TITLE in md and 'class="ast-summary"' in md             # 不是整頁「尚未選定」
    assert _health(at, "alo")["page_failure"] and not _health(at, "alo")["items"]      # 失敗那側的記錄沒被覆寫成尚未設定
    assert [i["kind"] for i in _health(at, "hld")["items"]] == [page_health.KIND_UNCONFIGURED]   # 沒有 Active 的那側只記它自己
    assert "alo-load-boom" not in md and re.search(r"⛔ [^<]*取數失敗", md)


def test_取數失敗優先於尚未設定_持股失敗_配置沒有Active():
    at = _run("alo_noactive_hld_fail")
    assert [e.value for e in at.exception] == []
    assert 'class="ast-summary"' in _md(at)
    assert _health(at, "hld")["page_failure"] and not _health(at, "hld")["items"]
    assert [i["kind"] for i in _health(at, "alo")["items"]] == [page_health.KIND_UNCONFIGURED]


def test_兩側都沒有Active_仍是整頁尚未選定_兩格都記尚未設定():
    at = _run("no_active")
    for slug in ("alo", "hld"):
        assert [i["kind"] for i in _health(at, slug)["items"]] == [page_health.KIND_UNCONFIGURED]
    assert 'class="ast-summary"' not in _md(at)


def test_持倉體檢計數拋ValueError_只有持股這一側改畫狀態_配置照常():
    at = _run("hld_count_boom")
    assert [e.value for e in at.exception] == []
    md = _md(at)
    assert "ALO-0" in _blocks(at) and "ALO-2" in _blocks(at) and "HLD-0" not in _blocks(at)
    assert _health(at, "hld")["page_failure"] and _health(at, "alo")["page_failure"] is None
    assert "計數不成立" not in md                                              # 原文只進進階診斷
    assert _hero(at).startswith("持有檔數無法判定；目前最大配置差距在 ")


def test_一側失敗_完整那一句只畫一次_各區段只寫短狀態並點名是哪一區():
    at = _run("alo_fail")
    errs = re.findall(r'class="ast-err"[^>]*>([^<]*)<', _md(at))
    full = [e for e in errs if e.startswith("⛔") and "取數失敗：" in e]
    assert len(full) == 1 and errs.count(full[0]) == 1
    assert all(len(e) <= len("資產配置　") + len("試算結果匯出　—　") + len("⛔ 取數失敗") for e in errs if e != full[0])
    # 失敗的是哪幾塊，容器標題列看得見
    assert "目標輸入卡　—　⛔ 取數失敗" in _container(at, "我的條件") and "歸屬明細　—　⛔ 取數失敗" in _container(at, "配置明細")
    assert "試算結果匯出　—　⛔ 取數失敗" in "\n".join(errs)


def test_收合區比照_flat小標題也帶block_ID_settingfail時15個ID都在():
    at = _s(alo="settingfail")
    seen = _blocks(at)
    assert {"ALO-6", "ALO-7"} <= seen                                          # 修之前：15 → 13
    assert seen == {"ALO-0", "ALO-1", "ALO-2", "ALO-3", "ALO-4", "ALO-6", "ALO-7", "HLD-0", "HLD-1", "HLD-2", "HLD-3", "HLD-4",
                    "HLD-6", "HLD-7", "HLD-8"}


def test_規則順序同單頁_ALO1先於收合區比照_展開區標題帶摘要與data_block():
    at = _s(alo="settingfail")
    assert "ALO-1" in _blocks(at)                                              # 即使收合區比照也想把它換成一行，單頁是先走 ALO-1
    assert "目標輸入卡　—　⛔ 取數失敗" in _container(at, "我的條件")
