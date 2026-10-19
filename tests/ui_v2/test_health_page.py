# -*- coding: utf-8 -*-
"""Phase 3 P0-②：四頁頁首資料狀態行、同源錯誤去重、「前往設定與診斷」的畫面測試（slow lane；需要 streamlit）。

依據 `docs/v2/44_fund_ui_ssot.md` 第七節第三小節之七其二第 3、4 條、其五；59 線框第 2.5、2.6 節。
腳本沿用 `tests/ui_v2/_plain_scan.py`（五頁正式模式 × 情境；fixtures／替身當 `load_live`，不打網路）。

- 每一頁（正常畫面）恰一行資料狀態行；沒有任何異常時只寫「資料截至 …」，不寫「資料齊」「正常」。
- 未設定情境：「尚未設定：」在一般畫面恰 1 次（就是狀態行）；尚未設定那一族的狀態句與寫入用的原文 0 次。
- 「此區塊暫時無法判定」在畫面上的次數 ＝ 去重交出的受影響塊數（同一個行程裡攔下 `health.dedupe_failures` 的回傳）。
- 持倉體檢 stale 情境：狀態行有 `◷` 與資料截至日；② 卡上那一句副標帶 `◷`。
- 單頁入口（不傳 `settings_page`）：只寫一行「完整資料狀態在『設定與診斷』頁」，沒有頁面連結、沒有同名按鈕。
- 核心卡的來源與新鮮度徽章不在 ② 卡上、在 ④「核心卡的來源與新鮮度」裡。
- 示範模式沒有資料狀態行（BL-0367）。

預覽入口（`st.navigation`）下的頁面連結與「換到設定與診斷之後 save／refetch 0 次」在 `tests/ui_v2/test_preview_page.py`。
"""

import html
import pathlib
import sys

import pytest

# 整檔標 slow：畫面測試不進 fast lane（守衛：tests/ui_v2/test_ui_v2_lane_guards.py）。
pytestmark = pytest.mark.slow

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_HERE))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

import _plain_scan as P  # noqa: E402

from ui_v2 import health, plain  # noqa: E402

_PAGES = ("mkt", "hld", "exp", "alo")
_STATUS_CLASS = 'class="v2-status-line"'
_CASES = [(page, name) for page in _PAGES for name in P.SCRIPTS[page] if name != "整頁失敗"]


def _run(script, monkeypatch=None):
    from streamlit.testing.v1 import AppTest

    summaries = []
    if monkeypatch is not None:
        real = health.dedupe_failures

        def _spy(display):
            out = real(display)
            summaries.append(out[1])
            return out

        monkeypatch.setattr(health, "dedupe_failures", _spy)
    at = AppTest.from_string(script, default_timeout=120)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at, summaries


def _status_lines(at):
    return [P.markdown_text(m.value) for m in at.main.markdown if _STATUS_CLASS in m.value]


def _visible(at):
    """畫面上看得到的字：Markdown（去標籤）、Caption、展開區標題（每枚只算一次）、按鈕標籤與說明。"""
    out = []

    def walk(node):
        kind = type(node).__name__
        if kind in ("Markdown", "Caption"):
            out.append(" ".join(P.markdown_text(node.value).split()))
        elif kind == "Expander":
            out.append(str(node.label))
        elif kind == "Button":
            out.append(node.label)
            if node.help:
                out.append(node.help)
        for child in getattr(node, "children", {}).values():
            walk(child)

    walk(at._tree)
    return out


@pytest.mark.parametrize("page, name", _CASES)
def test_每頁恰一行資料狀態行_不寫資料齊或正常_附資料截至日(page, name):
    at, _ = _run(P.SCRIPTS[page][name])
    lines = _status_lines(at)
    assert len(lines) == 1, (page, name, lines)
    line = " ".join(lines[0].split())
    assert "資料齊" not in line and "正常" not in line, line
    assert health.AS_OF_LABEL in line, line


@pytest.mark.parametrize("page", ["mkt", "hld", "alo"])
def test_沒有任何異常時只寫資料截至日(page):
    at, _ = _run(P.SCRIPTS[page]["正常"])
    line = " ".join(_status_lines(at)[0].split())
    assert line.startswith(health.AS_OF_LABEL) and health.STATUS_LABEL not in line, line
    for symbol in ("◷", "◇", "⛔"):
        assert symbol not in line, line


@pytest.mark.parametrize("page", _PAGES)
def test_未設定情境_尚未設定的類別句恰一次_狀態句與寫入原文在一般畫面0次(page):
    at, _ = _run(P.SCRIPTS[page]["未設定"])
    texts = _visible(at)
    joined = "\n".join(texts)
    # ~~`joined.count("尚未設定：") == 1`~~ → BL-0250 批次 1（客戶 2026-10-19 裁示 G3，`DEC-2026-10-19-04`；有意識的更正，不是漏刪）：
    # 客戶點名的位置 —— 結論燈、展開區標題、③ —— 改寫「尚未設定：〈哪一項〉」（不得寫成取數失敗）；市場總覽「設定讀不到」
    # 統一成同一種說法。資料狀態行那一句（類別句）照舊恰一次；塊內失敗摘要去重那一處照舊只留狀態族「⛔ 尚未設定」。
    # 舊斷言的用意（塊內不重複摘要、狀態句不外漏）照留；被權衡掉的是「整頁只准一處寫哪一項」。
    lamps = {" ".join(P.markdown_text(m.value).split()) for m in at.main.markdown
             if any(f'data-block="{page.upper()}-0"' in m.value for _ in [0])}
    titles = {str(e.label) for e in at.main.expander}
    status = " ".join(_status_lines(at)[0].split())
    allowed = ("資料面：", "卡：尚未設定：", "，暫不存檔", "，暫時列出全部指標", "⬜ 不適用：尚未設定：", "⬜ 不適用（尚未設定：", "，暫無篩選軌跡",
               "偏離提示卡 ⛔ 尚未設定：", "⛔ 尚未設定：資料來源的金鑰")
    # ↑ BL-0250 批次 3-A 同批總管裁定（決策者：AI 總管，適用客戶 `DEC-2026-10-19-05` 第 2 點；44 第七節第三小節之十二其九第 1、4 條）：
    # 持倉體檢偏離提示卡主值、市場總覽缺金鑰的指標（清單下方、明細表尾、新鮮度清單）寫「⛔ 尚未設定：〈哪一項〉」，是客戶裁示的格式，
    # 不是外漏的失敗摘要；資料狀態行那一句照舊恰一次（下一條斷言）。
    # ↑ BL-0250 批次 2（44 第七節第三小節之十一其六）：核心卡副標兩個冒號改括號，同一處、同一種說法（舊形保留在表裡不刪）。
    stray = [t for t in texts if f"{health.TEXT_NOT_CONFIGURED}：" in t and t != status and t not in lamps
             and t not in titles and not any(a in t for a in allowed)]
    assert stray == [], (page, stray)
    assert texts.count(status) == 1, page
    assert f"{health.TEXT_NOT_CONFIGURED}：" in " ".join(_status_lines(at)[0].split())
    for state in health.NOT_CONFIGURED_STATES:
        assert state not in joined, (page, state)
    assert plain.MSG_SETTINGS_NOT_CONFIGURED not in joined, page        # 寫入用的原文
    assert plain.MSG_POLICY_NOT_CONFIGURED not in joined, page


@pytest.mark.parametrize("page, name", _CASES)
def test_此區塊暫時無法判定的次數等於受影響塊數(page, name, monkeypatch):
    at, summaries = _run(P.SCRIPTS[page][name], monkeypatch)
    assert len(summaries) == 1, summaries
    shown = sum(t.count(health.TEXT_BLOCK_UNDECIDABLE) for t in _visible(at))
    assert shown == len(summaries[0]["affected_blocks"]), (page, name, shown, summaries[0])


def test_受影響塊數不是空掃(monkeypatch):
    total = 0
    for page in _PAGES:
        _at, summaries = _run(P.SCRIPTS[page]["未設定"], monkeypatch)
        total += len(summaries[-1]["affected_blocks"])
        monkeypatch.undo()
    assert total >= 8, total


@pytest.mark.parametrize("page", _PAGES)
def test_同一類失敗摘要在一般畫面只出現在狀態行(page):
    at, _ = _run(P.SCRIPTS[page]["取數失敗"])
    line = " ".join(_status_lines(at)[0].split())
    assert f"{health.SYMBOL_ERROR} {health.TEXT_FETCH_FAILED}" in line, line
    joined = "\n".join(_visible(at))
    assert joined.count(f"{health.TEXT_FETCH_FAILED}：") == 1, page   # 「取數失敗：<資料類>」只在狀態行


def test_持倉體檢_stale_狀態行有時鐘記號與資料截至日_卡上副標也帶():
    at, _ = _run(P.SCRIPTS["hld"]["stale"])
    line = " ".join(_status_lines(at)[0].split())
    assert health.SYMBOL_STALE in line and f"{health.AS_OF_LABEL} 2026-" in line, line
    cards = [m.value for m in at.main.markdown if 'data-block="HLD-2"' in m.value or 'data-block="HLD-3"' in m.value]
    assert cards and all(f"{health.SYMBOL_STALE} 淨值取自預存序列" in html.unescape(v) for v in cards)


def test_持倉體檢_超過10日是資料未備不是時鐘():
    at, _ = _run(P.SCRIPTS["hld"]["超過10日"])
    line = " ".join(_status_lines(at)[0].split())
    assert health.SYMBOL_MISSING in line and health.SYMBOL_STALE not in line, line


@pytest.mark.parametrize("page", _PAGES)
def test_單頁入口只寫一行說明_沒有頁面連結_沒有同名按鈕(page):
    at, _ = _run(P.SCRIPTS[page]["正常"])
    assert health.SETTINGS_ELSEWHERE_TEXT in [c.value for c in at.main.caption]
    assert at.get("page_link") == []
    assert health.SETTINGS_LINK_LABEL not in [b.label for b in at.button]


@pytest.mark.parametrize("page", ["hld", "alo"])
def test_整頁錯誤畫面_那一行加導覽_不另畫狀態行(page):
    at, _ = _run(P.SCRIPTS[page]["整頁失敗"])
    assert _status_lines(at) == []
    assert health.SETTINGS_ELSEWHERE_TEXT in [c.value for c in at.main.caption]
    assert not at.button


@pytest.mark.parametrize("page", ["mkt", "exp"])
def test_核心卡的來源與新鮮度徽章移到第四段(page):
    at, _ = _run(P.SCRIPTS[page]["正常"])
    cards = [html.unescape(m.value) for m in at.main.markdown
             if any(f'data-block="{page.upper()}-{n}"' in m.value for n in (1, 2, 3))]
    assert cards
    # ~~"〔來源層級〕"~~ → BL-0250 批次 3-A（`DEC-2026-10-19-05` 第 1 點；有意識的更正，不是漏刪）：標的探索三張卡卡片層級的
    # 來源與新鮮度改寫一句「⬜ 不適用（…）」，照樣只在 ④ 那一枚展開區裡。
    word = "延遲 3 日" if page == "mkt" else "⬜ 不適用（這張卡由多檔基金組成"
    assert not any(word in card for card in cards), page
    box = [e for e in at.main.expander if e.label == health.PROVENANCE_TITLE]
    assert len(box) == 1 and box[0].proto.expanded is False
    assert word in html.unescape(" ".join(m.value for m in box[0].markdown))


@pytest.mark.parametrize("page", _PAGES)
def test_示範模式沒有資料狀態行(page):
    from streamlit.testing.v1 import AppTest

    script = P._HEAD + f"from ui_v2.{page} import page\npage.render()\n"
    at = AppTest.from_string(script, default_timeout=120)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert _status_lines(at) == []
    assert health.SETTINGS_ELSEWHERE_TEXT not in [c.value for c in at.main.caption]
    assert not any(e.label == health.PROVENANCE_TITLE for e in at.main.expander)


@pytest.mark.parametrize("page", _PAGES)
def test_示範模式傳settings_page當場炸(page):
    from ui_v2.alo import page as A
    from ui_v2.exp import page as E
    from ui_v2.hld import page as H
    from ui_v2.mkt import page as M

    module = {"mkt": M, "hld": H, "exp": E, "alo": A}[page]
    with pytest.raises(ValueError, match="settings_page"):
        module.render(settings_page=object())


def test_資產配置兩鍵都沒存進去_卡片層寫儲存失敗_兩鍵原文都進進階診斷_BL0177():
    script = P._HEAD + """
from ui_v2.alo import fixtures, page
_dataset = fixtures.scenario("full")
_dataset["save_errors"] = {"alo_target_weights": "HTTP 503 目標那一鍵", "alo_tolerance_pp": "HTTP 503 容許帶那一鍵"}
page.render(load_live=lambda: {"dataset": _dataset, "notes": {}}, mask_error=str)
"""
    at, _ = _run(script)
    card = [html.unescape(m.value) for m in at.main.markdown if "alo-errline" in m.value]
    assert any(health.TEXT_SAVE_FAILED_BOTH in line for line in card), card
    assert not any("HTTP 503" in t for t in _visible(at))                       # 原文不在一般畫面
    raw = "\n".join(e["text"] for e in at.session_state[plain.RAW_STATE]["alo"]["entries"])
    assert "alo_target_weights：HTTP 503 目標那一鍵" in raw and "alo_tolerance_pp：HTTP 503 容許帶那一鍵" in raw


def test_資產配置只有一鍵失敗_不改成儲存失敗():
    script = P._HEAD + """
from ui_v2.alo import fixtures, page
_dataset = fixtures.scenario("full")
_dataset["save_errors"] = {"alo_tolerance_pp": "HTTP 503 容許帶那一鍵"}
page.render(load_live=lambda: {"dataset": _dataset, "notes": {}}, mask_error=str)
"""
    at, _ = _run(script)
    assert health.TEXT_SAVE_FAILED_BOTH not in "\n".join(_visible(at))


# ───────────────────────── 2026-10-17 稽核必修：「ok 但延遲」在 ② 卡上留 ◷ ─────────────────────────


def _cards(at, page):
    return [html.unescape(m.value) for m in at.main.markdown
            if any(f'data-block="{page.upper()}-{n}"' in m.value for n in (1, 2, 3))]


def test_市場總覽_黃色新鮮度徽章_卡上有時鐘_狀態行有時鐘(monkeypatch):
    """黃色調只能用替身造（`ui_v2/mkt/logic.py::_freshness_badge` 現行寫死中性，見 test_health_logic 的依據條）：
    把那一支換成「同一枚徽章、色調改黃」，其餘判定一行不動。"""
    from ui_v2.mkt import logic as L

    real = L._freshness_badge
    # BL-0250 批次 3-A：`_freshness_badge` 多一個延遲日數時區參數（正式模式台北日期），替身照收照轉。
    monkeypatch.setattr(L, "_freshness_badge", lambda rows, *args: dict(real(rows, *args), _tone="黃"))
    at, _ = _run(P.SCRIPTS["mkt"]["正常"])
    cards = _cards(at, "mkt")
    assert cards and all(f"{health.SYMBOL_STALE} 延遲 " in card for card in cards), cards
    line = " ".join(_status_lines(at)[0].split())
    assert health.SYMBOL_STALE in line and f"{health.AS_OF_LABEL} 2026-" in line, line
    box = [e for e in at.main.expander if e.label == health.PROVENANCE_TITLE]
    assert "延遲 3 日" in html.unescape(" ".join(m.value for m in box[0].markdown))   # ④ 照列原字面


def test_市場總覽_中性延遲_卡上與狀態行都沒有時鐘():
    at, _ = _run(P.SCRIPTS["mkt"]["正常"])
    assert not any(health.SYMBOL_STALE in card for card in _cards(at, "mkt"))
    assert not any("延遲 " in card for card in _cards(at, "mkt"))                    # 中性的延遲徽章移到 ④
    assert health.SYMBOL_STALE not in _status_lines(at)[0]


def test_持倉體檢_黃色新鮮度徽章_逐檔標頭有時鐘_狀態行有時鐘(monkeypatch):
    """同上：`ui_v2/hld/live.py::nav_freshness` 現行只交灰與中性；替身把中性那一支改黃（日數、門檻、灰色那一支不動）。"""
    from ui_v2.hld import live as HL

    real = HL.nav_freshness

    def yellow(*args, **kwargs):
        out = real(*args, **kwargs)
        for entry in out.values():
            if entry["badge"]["_tone"] == "中性":
                entry["badge"] = dict(entry["badge"], _tone="黃")
        return out

    monkeypatch.setattr(HL, "nav_freshness", yellow)
    at, _ = _run(P.SCRIPTS["hld"]["正常"])
    cards = [c for c in _cards(at, "hld") if 'data-block="HLD-2"' in c or 'data-block="HLD-3"' in c]
    assert cards and all(f"{health.SYMBOL_STALE} 延遲 10 日" in card for card in cards), cards
    assert health.SYMBOL_STALE in _status_lines(at)[0]


def test_持倉體檢_中性延遲_徽章移到第四段_卡上與狀態行都沒有時鐘():
    """稽核可選 2：持倉體檢逐檔的新鮮度徽章（中性「延遲 10 日」）不在 ② 卡上、在 ④「核心卡的來源與新鮮度」裡。"""
    at, _ = _run(P.SCRIPTS["hld"]["正常"])
    cards = [c for c in _cards(at, "hld") if 'data-block="HLD-2"' in c or 'data-block="HLD-3"' in c]
    assert cards and not any("延遲 10 日" in card or health.SYMBOL_STALE in card for card in cards), cards
    assert health.SYMBOL_STALE not in _status_lines(at)[0]
    box = [e for e in at.main.expander if e.label == health.PROVENANCE_TITLE]
    assert len(box) == 1 and box[0].proto.expanded is False
    body = html.unescape(" ".join(m.value for m in box[0].markdown))
    assert body.count("延遲 10 日") >= 6, body                                     # 兩張卡 × 三檔


# ───────────────────────── Phase 3 P1-④：結論燈同一則訊息不印兩次 ─────────────────────────
# 本段只驗 `_plain_scan` 畫面情境裡的 5 處；模型層的完整變動範圍（含持倉體檢與資產配置的 ⬜）見 `health.trim_light_echo`。


def _lamp_text(at, code):
    lamps = [" ".join(P.markdown_text(m.value).split()) for m in at.main.markdown if f'data-block="{code}"' in m.value]
    assert len(lamps) == 1, (code, lamps)
    return lamps[0]


# ~~("未設定", "狀態：取數失敗 尚未設定")、("未設定保單", …)~~ → BL-0250 批次 1（客戶 G3，`DEC-2026-10-19-04`；有意識的更正，
# 不是漏刪）：失敗全部屬尚未設定時，燈的狀態字改「狀態：尚未設定」，那一句寫哪一項；⛔ 照舊只出現一次。
@pytest.mark.parametrize(("name", "rest", "fetch_words"), [
    ("未設定", "狀態：尚未設定 尚未設定：設定試算表", 0),
    ("未設定保單", "狀態：尚未設定 尚未設定：保單試算表", 0),
    ("取數失敗", "狀態：取數失敗 我這一季", 1),
    ("局部失敗", "狀態：取數失敗 我這一季", 1),
])
def test_資產配置結論燈_停止符號與取數失敗各只出現一次(name, rest, fetch_words):
    """改前畫面是「⛔ 狀態：取數失敗 ⛔ 尚未設定」「⛔ 狀態：取數失敗 ⛔ 取數失敗」（P0-② 稽核所見）。"""
    at, _ = _run(P.SCRIPTS["alo"][name])
    lamp = _lamp_text(at, "ALO-0")
    assert lamp.count(health.SYMBOL_ERROR) == 1, lamp
    assert lamp.count(health.TEXT_FETCH_FAILED) == fetch_words, lamp
    assert lamp.startswith(f"{health.SYMBOL_ERROR} {rest}"), lamp


def test_持倉體檢超過10日_結論燈的方塊只出現一次():
    at, _ = _run(P.SCRIPTS["hld"]["超過10日"])
    lamp = _lamp_text(at, "HLD-0")
    # 2026-10-17 ◆／◇ 小批：資料未備的句首改 ◇、與燈的 ⬜ 不同，去重不再觸發（`ui_v2/health.py::trim_light_echo` 說明）；
    # 燈的方塊照舊只出現一次。
    assert lamp.startswith("⬜ 狀態：中性 ◇ 資料未備"), lamp
    assert lamp.count("⬜") == 1, lamp


def test_示範模式的結論燈照舊():
    """示範模式畫面維持現行（BL-0367）：取數失敗情境的燈文字照舊是 logic 交出的原句（本步只在正式模式的去重裡做）。"""
    from streamlit.testing.v1 import AppTest

    from ui_v2.alo import fixtures as AF
    from ui_v2.alo import logic as AL

    at = AppTest.from_file(str(_ROOT / "ui_v2" / "app_alo.py"), default_timeout=60)
    at.query_params["scenario"] = "holdfail"
    at.run()
    assert not at.exception
    expected = AL.find_block(AL.build_page_model(AF.scenario("holdfail")), "ALO-0")["text"]
    lamps = [m.value for m in at.main.markdown if 'class="alo-lamp"' in m.value]
    assert len(lamps) == 1 and html.escape(expected) in lamps[0], (expected, lamps)


@pytest.mark.parametrize(("page", "code", "pattern"), [
    ("hld", "HLD-0", r"^◆ 狀態：需要注意 有 \d+ 檔超出你設定的門檻"),
    ("alo", "ALO-0", r"^◆ 狀態：需要注意 \S+ 與目標差 \d+\.\d 個百分點"),
])
def test_正式模式偏離的結論燈_不著色_以菱形需要注意呈現(page, code, pattern):
    """2026-10-17 ◆／◇ 小批（44 第七節第三小節之七其三；`ui_v2/symbols.py`）：偏離的燈不再畫成黃色。"""
    import re

    from ui_v2.hld import theme as HT

    at, _ = _run(P.SCRIPTS[page]["正常"])
    lamp = _lamp_text(at, code)
    assert re.match(pattern, lamp), lamp
    raw = [m.value for m in at.main.markdown if f'data-block="{code}"' in m.value][0]
    assert HT.STATE_WARN not in raw and HT.TEXT_PRIMARY in raw, raw[:300]
    assert "黃燈" not in " ".join(P.markdown_text(m.value) for m in at.main.markdown)


@pytest.mark.parametrize("name", sorted(P.SCRIPTS["set"]))
def test_設定與診斷正式頁_畫面上沒有方塊資料未備(name):
    """2026-10-17 ◆／◇ 小批獨立稽核 M2：狀態徽章「資料未備」帶的圖示改 ◇（`ui_v2/symbols.py`），文字不動。"""
    at, _ = _run(P.SCRIPTS["set"][name])
    text = " ".join(P.screen_texts(at))
    assert "⬜ 資料未備" not in text, name
