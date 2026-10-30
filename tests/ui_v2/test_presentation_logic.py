# -*- coding: utf-8 -*-
"""共用 presentation primitives 的形狀測試（BL-0525 Batch A；T10 的 logic 半邊；fast lane，不需要 streamlit）。

驗 `ui_v2/presentation.py`：chip 3～5 枚、每圖至多一句、detail 預設不外露內容全保留、Missing 不寫 0／中性／留空。
畫 Streamlit 的那一半在 `test_presentation_page.py`。
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from ui_v2 import presentation as P

_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _chips(n, tone="中性"):
    return [P.chip(f"標籤{i}", tone) for i in range(n)]


# ── chip ──


def test_chip_文字必須非空_tone必須合法():
    with pytest.raises(ValueError):
        P.chip("  ")
    with pytest.raises(ValueError):
        P.chip("x", "綠")
    with pytest.raises(ValueError):
        P.chip("x", title=" ")
    assert P.chip(" 資料日 2026-10-28 ", "灰")["text"] == "資料日 2026-10-28"


def test_chip_html_跳脫_且狀態用文字不只靠顏色():
    html = P.chip_html(P.chip('<b>"x"</b>', "紅", title="a&b"))
    assert "<b>" not in html and "&lt;b&gt;" in html and "&amp;" in html
    # 顏色走 data-tone + CSS class，不寫行內色碼；字（與符號）才是資訊載體。
    assert 'data-tone="紅"' in html and "style=" not in html


def test_missing_chip_是_44_現行字樣_灰色_符號與字都在():
    c = P.missing_chip()
    assert c["text"] == "◇ 資料未備" and c["tone"] == "灰"


def test_chips_html_超過五枚轉紅_六枚要先split():
    assert P.chips_html([]) == ""
    assert P.chips_html(_chips(5)).count("pc-chip\"") == 5
    with pytest.raises(ValueError):
        P.chips_html(_chips(6))
    shown, overflow = P.split_chips(_chips(7))
    assert len(shown) == 5 and len(overflow) == 2
    # 溢出的不丟：能轉成 detail 可放的字。
    assert P.overflow_lines(overflow) == ["標籤5", "標籤6"]


def test_split_chips_拒絕不是chip的東西():
    with pytest.raises(ValueError):
        P.split_chips(["純字串"])


# ── 一句摘要 ──


@pytest.mark.parametrize("text, ok", [
    ("近三個月波動偏低", True),
    ("近三個月波動偏低。", True),
    ("第一句。第二句。", False),
    ("第一行\n第二行", False),
    ("", False),
    ("   ", False),
    (None, False),
])
def test_is_one_sentence(text, ok):
    assert P.is_one_sentence(text) is ok


# ── detail ──


def test_detail_預設無內容就不畫展開區_有內容標題只列有的組():
    assert P.detail_model() == {"title": None, "groups": []}
    d = P.detail_model(why=["原因甲"], where=["到設定頁補"])
    assert d["title"] == "▸ 為什麼‧去哪補"
    full = P.detail_model(why=["a"], source=["b"], limits=["c"], where=["d"])
    assert full["title"] == "▸ 為什麼‧來源‧限制‧去哪補"


def test_detail_內容完整保留_空白行轉紅():
    d = P.detail_model(why=["甲", "乙"], source=["Yahoo:^VIX，取得 2026-10-28"], limits=["缺值日不補值"], where=["⚙️ 設定"])
    texts = P.detail_texts(d)
    for needle in ("甲", "乙", "Yahoo:^VIX，取得 2026-10-28", "缺值日不補值", "⚙️ 設定"):
        assert needle in texts
    html = P.detail_html(d)
    assert "缺值日不補值" in html and html.count("<li>") == 5
    with pytest.raises(ValueError):
        P.detail_model(why=["", "x"])


# ── chart card ──


def test_chart_card_三到五枚chips_一句摘要():
    d = P.detail_model(source=["來源"])
    m = P.chart_card_model("VIX", _chips(3), "近三個月波動偏低", detail=d)
    assert m["kind"] == "chart_card" and len(m["chips"]) == 3
    html = P.chart_card_head_html(m)
    assert "VIX" in html and "近三個月波動偏低" in html and html.count('class="pc-chip"') == 3
    for n in (2, 6):
        with pytest.raises(ValueError):
            P.chart_card_model("VIX", _chips(n), "一句")
    with pytest.raises(ValueError):
        P.chart_card_model("VIX", _chips(4), "兩句。真的。")
    with pytest.raises(ValueError):
        P.chart_card_model(" ", _chips(4), "一句")


def test_chart_card_head_不含detail內容_長說明不在圖表之前():
    d = P.detail_model(why=["很長的為什麼" * 20], source=["很長的來源" * 20])
    m = P.chart_card_model("TAIEX", _chips(4), "一句", detail=d)
    head = P.chart_card_head_html(m)
    assert "很長的為什麼" not in head and "很長的來源" not in head


# ── Missing ──


def test_missing_不寫0_不寫中性_不留空():
    m = P.missing_model("信用利差", "尚未接上正式來源", detail=P.detail_model(where=["資料來源決策待客戶裁示"]))
    assert m["kind"] == "missing" and m["chips"][0]["text"] == "◇ 資料未備"
    assert "value" not in m and "value_text" not in m   # 模型沒有可被畫成 0 的欄位
    html = P.missing_card_html(m)
    assert "◇ 資料未備" in html and "尚未接上正式來源" in html
    where = P.detail_model(where=["到設定頁補"])
    for bad in ("", "  ", "兩句。真的。", "多行\n原因"):
        with pytest.raises(ValueError):
            P.missing_model("x", bad, detail=where)


def test_missing_必含去哪補_缺了轉紅():
    with pytest.raises(ValueError):
        P.missing_model("x", "原因")                                   # 沒給 detail
    with pytest.raises(ValueError):
        P.missing_model("x", "原因", detail=P.detail_model())           # 空 detail
    with pytest.raises(ValueError):
        P.missing_model("x", "原因", detail=P.detail_model(why=["只有為什麼"]))   # 缺「去哪補」組
    m = P.missing_model("x", "原因", detail=P.detail_model(why=["甲"], where=["到設定頁補"]))
    assert m["detail"]["title"] == "▸ 為什麼‧去哪補"


def test_missing_額外chip也受上限約束():
    where = P.detail_model(where=["到設定頁補"])
    P.missing_model("x", "原因", detail=where, extra_chips=_chips(4))
    with pytest.raises(ValueError):
        P.missing_model("x", "原因", detail=where, extra_chips=_chips(5))


# ── 隔離 ──


def test_純函式模組不import_streamlit_也不import舊樹():
    tree = ast.parse((_ROOT / "ui_v2" / "presentation.py").read_text(encoding="utf-8"))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            roots.add((node.module or "").split(".")[0])
    assert "streamlit" not in roots
    assert not roots & {"ui", "services", "repositories", "shared", "infra", "fund_fetcher"}, roots


def test_primitives_目前沒有被任何頁面呼叫_Batch_A不改畫面():
    """Batch A 只建 primitives；頁面套用屬 Batch C～F。哪一批開始套用，就在那一批把這條改成正向守衛。"""
    users = []
    for path in (_ROOT / "ui_v2").rglob("*.py"):
        if path.name in ("presentation.py", "presentation_view.py"):
            continue
        text = path.read_text(encoding="utf-8")
        if "presentation_view" in text or "from ui_v2 import presentation" in text or "from . import presentation" in text:
            users.append(str(path.relative_to(_ROOT)))
    assert users == [], users
