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
import re
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

from ui_v2 import health, page_health, plain  # noqa: E402

# BL-0250 批次 3-C（U9）：資料狀態行退場，頁首改主要原因＋另有；下面幾個字面改讀頁首那一支（`page_health`），
# 退場的兩個字樣只在本檔當作「不得出現」的字（有意識的更正，不是漏刪；`DEC-2026-10-21-01`）。
_RETIRED_STATUS_LABEL = "資料狀態："
_RETIRED_PROVENANCE_TITLE = "核心卡的來源與新鮮度"

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


def _visible_tagged(at, boxes=None):
    """同 `_visible`，另附每一句屬於哪一塊（`data-block`）的畫面範圍：遇到下一個 `data-block`、段標籤或 ③ 那一行就換塊／離開塊。
    不在任何塊範圍裡的句子、以及 Markdown 以外的元素（說明、展開區標題、按鈕）塊代號一律為 None —— 原因行只畫在卡自己的
    Markdown 裡，剝除不碰其他元素。只給「收起卡自己的原因行」剝除用（BL-0250 批次 3-D）。"""
    import re

    out, state = [], {"code": None}

    def walk(node):
        kind = type(node).__name__
        if kind in ("Markdown", "Caption"):
            value = node.value
            if kind == "Markdown":
                match = re.search(r'data-block="([^"]+)"', value)
                if match:
                    state["code"] = match.group(1)
                elif "layer-label" in value or "v2-attention" in value:
                    state["code"] = None
            code = state["code"] if (kind == "Markdown" or str(state["code"]).startswith("④")) else None
            out.append((code, " ".join(P.markdown_text(value).split())))
        elif kind == "Expander":
            # ④ 比照規則 5 的收合區（客戶 Q5 (b)）：標題那一句與裡面那一行屬於那一塊自己（`boxes`：標題 → 塊鍵）。
            key = (boxes or {}).get(str(node.label))
            out.append((key, str(node.label)))
            if key:
                saved, state["code"] = state["code"], key
                for child in getattr(node, "children", {}).values():
                    walk(child)
                state["code"] = saved
                return
        elif kind == "Button":
            out.append((None, node.label))
            if node.help:
                out.append((None, node.help))
        for child in getattr(node, "children", {}).values():
            walk(child)

    walk(at._tree)
    return out


def _quiet(page, script):
    """BL-0250 批次 3-D（新設計 B）：這一頁這一次收起了哪幾張卡、各寫了哪幾行原因（`sections.quiet_cards` 的回傳，只讀）。"""
    from ui_v2 import sections

    seen, details = [], []
    real, real_details = sections.quiet_cards, sections.quiet_details

    def spy(*args, **kwargs):
        out = real(*args, **kwargs)
        seen.append(out[0])
        return out

    def spy_details(*args, **kwargs):
        out = real_details(*args, **kwargs)
        details.append(out)
        return out

    sections.quiet_cards, sections.quiet_details = spy, spy_details
    try:
        at, _ = _run(script)
    finally:
        sections.quiet_cards, sections.quiet_details = real, real_details
    views = seen[-1] if seen else {}
    out = {code: [line["text"] for line in view["lines"]] for code, view in views.items()}
    # 客戶 2026-10-21 Q5 (b)（規則 5）：④ 比照的收合區也是「那一塊自己的一句原因」—— 標題一次、打開一次，同一張表、標上 `④`。
    for code, view in (details[-1] if details else {}).items():
        out[f"④{code}"] = [view["line"]["text"], view["line"]["text"]]
        _detail_titles[f"④{code}"] = view["title"]
    return at, out


_detail_titles = {}   # ④ 比照那幾塊的標題（`_quiet` 填）


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
def test_每頁資料狀態行_資料截至日存在且只講一次_不寫資料齊或正常(page, name):
    # BL-0525 Batch A 測試契約遷移（`DEC-2026-10-29-05` (7)、44 之十九其八；有意識的更正，不是漏刪；T2）：
    # ~~舊名「test_每頁恰一行資料狀態行_不寫資料齊或正常_附資料截至日」，斷言 `len(lines) == 1`（狀態行必須是恰好一個文字元素）~~。
    # 舊斷言鎖的是**呈現形式**（單行文字），新契約允許日後改成 status chips（P3），所以形式不鎖；
    # 改驗它真正保護的資訊：①資料截至日存在、②只講一次（同源訊息不重複外露，P-16 的去重意圖）、③不寫「資料齊」「正常」。
    # 舊斷言在寫下當時為真；被權衡掉的是「一定是單一文字元素」。語意（◷／◇／⛔ 各自的判定）由本檔其他測試照舊鎖住，未動。
    at, _ = _run(P.SCRIPTS[page][name])
    lines = _status_lines(at)
    assert lines, (page, name)
    joined = " ".join(" ".join(line.split()) for line in lines)
    assert "資料齊" not in joined and "正常" not in joined, joined
    assert joined.count(page_health.AS_OF_LABEL) == 1, (page, name, joined)


@pytest.mark.parametrize("page", ["mkt", "hld", "alo"])
def test_沒有任何異常時只寫資料截至日(page):
    at, _ = _run(P.SCRIPTS[page]["正常"])
    line = " ".join(_status_lines(at)[0].split())
    assert line.startswith(page_health.AS_OF_LABEL) and _RETIRED_STATUS_LABEL not in line, line
    for symbol in ("◷", "◇", "⛔"):
        assert symbol not in line, line


@pytest.mark.parametrize("page", _PAGES)
def test_未設定情境_尚未設定的類別句恰一次_狀態句與寫入原文在一般畫面0次(page):
    at, quiet = _quiet(page, P.SCRIPTS[page]["未設定"])
    # BL-0250 批次 3-D（新設計 B；44 第七節第三小節之十五、之七其二第 3 條指標；有意識的政策變更，不是漏刪；決策者：客戶
    # `DEC-2026-10-21-03`）：收起的卡上每種原因一行（「⛔ 尚未設定：‹哪一項›」），同源原因因此可能在幾張收起卡上各寫一行。
    # 下面的 stray 比對只在**收起卡自己的畫面範圍**裡、把**那一張卡自己的**原因行各剝掉一次再看 —— 收起卡以外的任何位置、
    # 以及收起卡上原因行以外的字照舊逐句比對，`exact` 白名單照舊有效（不放寬）。
    # ~~從整頁每一句裡刪掉所有原因行~~（2026-10-21 3-D 獨立稽核必修 1；有意識的更正，不是漏刪：那樣會把收起卡以外同字面的外漏
    # 一起刪掉，`exact` 白名單變成死碼；稽核突變：卡片後插一句同字面的 caption，舊寫法照樣通過）。
    texts = []
    left = {code: list(lines) for code, lines in quiet.items()}   # 每張收起卡的每一行原因只剝一次（＝卡上畫了一次）
    boxes = {f"{title}　—　{lines[0]}": code for code, (title, lines) in
             ((c, (_detail_titles.get(c), l)) for c, l in quiet.items() if c.startswith("④"))}
    for code, text in _visible_tagged(at, boxes):
        if code in left:
            for line in list(left[code]):
                if line in text:
                    text = text.replace(line, "", 1)
                    left[code].remove(line)
            text = " ".join(text.split())
        texts.append(text)
    assert all(not lines for lines in left.values()), (page, left)        # 每一行原因都真的畫在那張卡自己的範圍裡
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
               )
    # BL-0250 批次 3-A 同批總管裁定（決策者：AI 總管，總管適用客戶裁示第 2 點；44 第七節第三小節之十二其九第 1、4 條）：
    # 持倉體檢偏離提示卡主值、市場總覽缺金鑰的指標（清單下方、明細表尾、新鮮度清單）寫「⛔ 尚未設定：〈哪一項〉」，是客戶裁示的格式，
    # 不是外漏的失敗摘要；資料狀態行那一句照舊恰一次（下一條斷言）。
    # ~~以子字串免檢（"偏離提示卡 ⛔ 尚未設定："、"⛔ 尚未設定：資料來源的金鑰"）~~ → 同批稽核回修：改成整句精確比對（有意識的更正，
    # 不是漏刪；子字串免檢會連帶放過同一行裡別的外漏）。
    exact = {
        "mkt": {"⛔ 尚未設定：資料來源的金鑰（高收益信用利差、政策利率、期限利差）",
                "指標 最近觀測日 最近取得時間（UTC+8） 來源層級 延遲日數 高收益信用利差 ⛔ 尚未設定：資料來源的金鑰 ⛔ ⛔ ⛔ "
                "政策利率 ⛔ 尚未設定：資料來源的金鑰 ⛔ ⛔ ⛔ 期限利差 ⛔ 尚未設定：資料來源的金鑰 ⛔ ⛔ ⛔ 波動度指數 取數失敗 ⛔ ⛔ ⛔ ⛔"},
        # ~~"hld": {"偏離提示卡 ⛔ 尚未設定：保單試算表 ⛔ 此區塊暫時無法判定 本卡只描述現況與你設定的門檻差多少，不提供任何處置方向。
        # 哪幾檔現在超出了我自己寫下的那條線，超出多少"}~~ → BL-0250 批次 3-D（有意識的更正，不是漏刪）：這一句是偏離提示卡收起前的
        # 樣子；3-D 起這張卡在「未設定」情境收起，那一句不再出現（值位置寫法改在關掉收起的畫面驗，見
        # `tests/ui_v2/test_bl0250_batch3a_page.py`）。白名單留著一句不會出現的字等於死碼，下一行另驗白名單每一句都真的在畫面上。
    }.get(page, set())
    # ↑ BL-0250 批次 2（44 第七節第三小節之十一其六）：核心卡副標兩個冒號改括號，同一處、同一種說法（舊形保留在表裡不刪）。
    stray = [t for t in texts if f"{health.TEXT_NOT_CONFIGURED}：" in t and t != status and t not in lamps
             and t not in titles and t not in exact and not any(a in t for a in allowed)]
    assert stray == [], (page, stray)
    assert all(t in texts for t in exact), (page, [t for t in exact if t not in texts])   # 白名單不是死碼
    assert texts.count(status) == 1, page
    # ~~`f"{TEXT_NOT_CONFIGURED}：" in 狀態行`~~ → BL-0250 批次 3-C（U9）：頁首主要原因寫「‹哪一項›尚未設定」、「另有」寫「尚未設定 N 項」
    # （有意識的政策變更，不是漏刪；`DEC-2026-10-21-01`）。
    assert health.TEXT_NOT_CONFIGURED in " ".join(_status_lines(at)[0].split())
    # 3-C：頁首主要原因「‹哪一項›尚未設定」與某幾句狀態句同字面（例「保單試算表尚未設定」），頁首是正當的那一處，比對時除外。
    head = " ".join(_status_lines(at)[0].split())
    rest = "\n".join(t for t in texts if t != head)
    for state in health.NOT_CONFIGURED_STATES:
        assert state not in rest, (page, state)
    assert plain.MSG_SETTINGS_NOT_CONFIGURED not in joined, page        # 寫入用的原文
    assert plain.MSG_POLICY_NOT_CONFIGURED not in joined, page


@pytest.mark.parametrize("page, name", _CASES)
def test_此區塊暫時無法判定的次數等於受影響塊數(page, name, monkeypatch):
    # BL-0250 批次 3-D（新設計 B；之七其二第 3 條指標；有意識的政策變更，不是漏刪；決策者：客戶 `DEC-2026-10-21-03`）：
    # ~~畫面上的次數 ＝ 受影響塊數~~ → 收起的卡上那一句由原因行取代（不畫），其餘受影響的塊照舊一塊一次；收起的卡一定寫了原因行。
    real = health.dedupe_failures
    summaries = []

    def _spy_dedupe(display):
        out = real(display)
        summaries.append(out[1])
        return out

    monkeypatch.setattr(health, "dedupe_failures", _spy_dedupe)
    at, quiet = _quiet(page, P.SCRIPTS[page][name])
    assert len(summaries) == 1, summaries
    shown = sum(t.count(health.TEXT_BLOCK_UNDECIDABLE) for t in _visible(at))
    kept = [code for code in summaries[0]["affected_blocks"] if code not in quiet and f"④{code}" not in quiet]
    assert shown == len(kept), (page, name, shown, kept, sorted(quiet))
    assert all(quiet[code] for code in quiet), quiet


def test_受影響塊數不是空掃(monkeypatch):
    total = 0
    for page in _PAGES:
        _at, summaries = _run(P.SCRIPTS[page]["未設定"], monkeypatch)
        total += len(summaries[-1]["affected_blocks"])
        monkeypatch.undo()
    assert total >= 8, total


@pytest.mark.parametrize("page", _PAGES)
def test_同一類失敗摘要在一般畫面只出現在頁首(page):
    # ~~狀態行「⛔ 取數失敗：<資料類>」恰一次~~ → BL-0250 批次 3-C（U9）：頁首主要原因寫「⛔ 主要原因：<資料類>取數失敗」；
    # 同源失敗摘要照舊不在頁面其餘位置重複（有意識的政策變更，不是漏刪；`DEC-2026-10-21-01`）。
    at, quiet = _quiet(page, P.SCRIPTS[page]["取數失敗"])
    line = " ".join(_status_lines(at)[0].split())
    assert line.startswith(f"{health.SYMBOL_ERROR} 主要原因：") and health.TEXT_FETCH_FAILED in line, line
    joined = "\n".join(t for t in _visible(at) if t != line)
    # BL-0250 批次 3-D（新設計 B；之七其二第 3 條指標；有意識的政策變更，不是漏刪；決策者：客戶 `DEC-2026-10-21-03`）：
    # ~~頁首以外 0 次~~ → 收起的卡每張寫一行自己的原因（「⛔ 取數失敗：‹…›」），恰好那幾行；其餘位置照舊 0 次。
    reasons = [r for lines in quiet.values() for r in lines if f"{health.TEXT_FETCH_FAILED}：" in r]
    assert joined.count(f"{health.TEXT_FETCH_FAILED}：") == len(reasons), (page, reasons)
    for reason in reasons:
        joined = joined.replace(reason, "", 1)
    assert joined.count(f"{health.TEXT_FETCH_FAILED}：") == 0, page


def test_持倉體檢_stale_狀態行有時鐘記號與資料截至日_卡上副標也帶():
    at, _ = _run(P.SCRIPTS["hld"]["stale"])
    line = " ".join(_status_lines(at)[0].split())
    assert health.SYMBOL_STALE in line and f"{page_health.AS_OF_LABEL} 2026-" in line, line
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


def _detail_text(at, page):
    """設定與診斷頁各頁資料狀態總表那一頁的明細（同一份記錄，`page_health.detail_rows`）攤成一串字。"""
    return " ".join(" ".join(row) for row in page_health.detail_rows(at.session_state[page_health.STATE_KEY][page]))


# ~~核心卡的來源與新鮮度徽章移到第四段（④ 那一枚展開區）~~ → BL-0250 批次 3-C（G2；線框第六版第 7 節第 2、11 列；
# `DEC-2026-10-21-01`；有意識的政策變更，不是漏刪）：拿下來的那一份不再畫在 ④，改由設定與診斷頁總表明細承接。
@pytest.mark.parametrize("page", ["mkt", "exp"])
def test_核心卡的來源與新鮮度徽章不在卡上_不再畫在第四段_在總表明細(page):
    at, _ = _run(P.SCRIPTS[page]["正常"])
    cards = [html.unescape(m.value) for m in at.main.markdown
             if any(f'data-block="{page.upper()}-{n}"' in m.value for n in (1, 2, 3))]
    assert cards
    # ~~"〔來源層級〕"~~ → BL-0250 批次 3-A（`DEC-2026-10-19-05` 第 1 點；有意識的更正，不是漏刪）：標的探索三張卡卡片層級的
    # 來源與新鮮度改寫一句「⬜ 不適用（…）」，照樣只在 ④ 那一枚展開區裡。
    word = "延遲 3 日" if page == "mkt" else "⬜ 不適用（這張卡由多檔基金組成"
    # BL-0525 Batch A 測試契約遷移（`DEC-2026-10-29-05` (7)、44 之十九其二第 4 條／其八；T3；有意識的更正，不是漏刪）：
    # ~~`assert not any(word in card for card in cards)`（卡片 HTML 裡完全不得出現來源字樣）~~ → 新契約推薦卡內「▸ 來源」展開區
    # （P2、P9），所以「卡內完全沒有來源」不再是要鎖的東西；要鎖的是⑥主畫面不必全部外露：把卡片裡的 `<details>` 展開區剝掉後
    # （＝預設可見的那一層），不得有來源字樣。⑤provenance 可追溯：總表明細**或**卡內展開區至少有一處（兩處並存，44 之十九其二第 4 條）。
    # 舊斷言在寫下當時為真；被權衡掉的是「來源字樣一律不得進卡片 HTML」。現況（來源只在總表明細）照樣通過。
    visible = [re.sub(r"<details\b.*?</details>", "", card, flags=re.S) for card in cards]
    assert not any(word in card for card in visible), page
    assert not any(e.label == _RETIRED_PROVENANCE_TITLE for e in at.main.expander)
    assert word in _detail_text(at, page) or any(word in card for card in cards), page


@pytest.mark.parametrize("page", _PAGES)
def test_示範模式沒有資料狀態行(page):
    from streamlit.testing.v1 import AppTest

    script = P._HEAD + f"from ui_v2.{page} import page\npage.render()\n"
    at = AppTest.from_string(script, default_timeout=120)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert _status_lines(at) == []
    assert health.SETTINGS_ELSEWHERE_TEXT not in [c.value for c in at.main.caption]
    assert not any(e.label == _RETIRED_PROVENANCE_TITLE for e in at.main.expander)


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
    assert health.SYMBOL_STALE in line and f"{page_health.AS_OF_LABEL} 2026-" in line, line
    # ~~④ 照列原字面~~ → 3-C：原字面在總表明細（有意識的政策變更，不是漏刪）
    assert not any(e.label == _RETIRED_PROVENANCE_TITLE for e in at.main.expander)
    assert "延遲 3 日" in _detail_text(at, "mkt")


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
    # ~~在 ④「核心卡的來源與新鮮度」裡（兩張卡 × 三檔）~~ → 3-C：④ 不再畫，同一份在總表明細（有意識的政策變更，不是漏刪）
    assert not any(e.label == _RETIRED_PROVENANCE_TITLE for e in at.main.expander)
    # ~~`body.count("延遲 10 日") >= 6`（兩張卡 × 三檔，另有淨值表逐檔三列）~~ → 3-C 總管裁定第 4 點：核心卡列與新增的
    # 淨值明細列分開數、各自精確（不只放寬下限；有意識的更正，不是漏刪）。
    rows = [row for row in page_health.detail_rows(at.session_state[page_health.STATE_KEY]["hld"])
            if row[5] == "延遲 10 日"]
    card_rows = [row for row in rows if row[1].startswith(("績效與風險卡", "配息與本金卡"))]
    nav_rows = [row for row in rows if row[1].startswith("淨值與配息序列")]
    assert len(card_rows) == 6, card_rows                                          # 兩張核心卡 × 三檔
    assert len(nav_rows) == 3 and all(row[0] == row[6] == "淨值" for row in nav_rows), nav_rows   # 淨值表逐檔三列
    assert len(rows) == len(card_rows) + len(nav_rows), rows                       # 沒有第三種列帶這個延遲


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
