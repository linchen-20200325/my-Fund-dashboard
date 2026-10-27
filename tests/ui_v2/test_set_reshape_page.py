# -*- coding: utf-8 -*-
"""設定與診斷頁正式模式重排的畫面測試（Phase 3 P1-⑥；`docs/v2/44_fund_ui_ssot.md` 第七節第三小節之八其二、其三）。

用 `tests/ui_v2/_plain_scan.py` 的設定與診斷正式模式腳本（真 L2 ＋ 真 L1 ＋ 假 gspread，不打網路）。
驗：①結論 → ②關鍵數字（只有資料新鮮度卡）→ ③需要注意（有「外」才畫）→ ④詳細資料（「操作」：規則參數卡、重新取數 ——
參數編輯第一階段不畫（客戶 2026-10-26 裁示第 7 節）；
「證據／來源」：來源健康卡、取數紀錄、欄位對照表、進階診斷）；`SET-0` 燈下那一枚同頁導覽；示範模式畫面逐位元組不變。
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys

import pytest

pytestmark = pytest.mark.slow

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_ROOT))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

import _plain_scan as SCAN  # noqa: E402

from ui_v2 import plain, sections  # noqa: E402
from ui_v2.set import fixtures  # noqa: E402

_LIVE = [name for name in SCAN.SCRIPTS["set"]]


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


def _label(values, label) -> int:
    return _first(values, f">{label}</div>")


def _expander(at, prefix):
    found = [e for e in at.expander if e.label.startswith(prefix)]
    assert len(found) == 1, [e.label for e in at.expander]
    return found[0]


def _lamp(values) -> str:
    hits = [v for v in values if 'class="set-lamp"' in v]
    assert len(hits) == 1, hits
    return hits[0]


@pytest.mark.parametrize("name", _LIVE)
def test_四段由上而下_SET1在關鍵數字_SET2SET3搬進詳細資料(name):
    at = _run(SCAN.SCRIPTS["set"][name])
    values = _md(at)
    one, two, three, four = (_label(values, plain.LABEL_LAYER1), _label(values, plain.LABEL_LAYER2),
                             _label(values, plain.LABEL_ATTENTION), _label(values, plain.LABEL_DETAILS))
    ops, evidence = _label(values, plain.LABEL_LAYER3), _label(values, plain.LABEL_LAYER4)
    assert -1 not in (one, two, four, ops, evidence)
    assert one < two < four < ops < evidence
    if three != -1:
        assert two < three < four
    set1 = _first(values, 'data-block="SET-1"')
    assert two < set1 < four
    # 規則參數卡在「操作」、來源健康卡在「證據／來源」，各是一枚預設收合的展開區，卡本體畫在展開區裡。
    set3 = _expander(at, "規則參數卡　—　")
    set2 = _expander(at, "來源健康卡　—　")
    assert not set3.proto.expanded and not set2.proto.expanded
    assert any('data-block="SET-3"' in m.value for m in set3.markdown)
    assert any('data-block="SET-2"' in m.value for m in set2.markdown)
    labels = [e.label for e in at.expander]
    # ~~`assert labels.index(set3.label) < labels.index(<「參數編輯」展開區>)`~~ —— 有意識的行為變更，不是漏刪（決策者：客戶
    # 2026-10-26 裁示第 7 節；`DEC-2026-10-25-04` J-6、2026-10-26 J-14 補記）：新 B UI 第一階段 `SET-4` 參數編輯塊整塊不畫
    # （`ui_v2/readonly.py`）。44 正文 SET-4 塊待正式修正程序（44 凍結，本測試不改 44）。
    assert not any(x.startswith("參數編輯") for x in labels), labels
    assert labels.index(set3.label) < labels.index(next(x for x in labels if x.startswith("重新取數")))
    assert labels.index(set2.label) > labels.index(next(x for x in labels if x.startswith("重新取數")))
    assert labels.index(set2.label) < labels.index(next(x for x in labels if x.startswith("取數紀錄")))


@pytest.mark.parametrize("name", _LIVE)
def test_燈下一枚同頁導覽_落點在重新取數之前_不是按鈕(name):
    at = _run(SCAN.SCRIPTS["set"][name])
    values = _md(at)
    lamp = values.index(_lamp(values))
    nav = _first(values, f'href="#{sections.SET_NAV_ANCHOR}"')
    assert nav == lamp + 1 or (nav > lamp and all("set-note" in v for v in values[lamp + 1:nav])), (lamp, nav)
    assert sections.SET_NAV_LABEL in values[nav]
    anchor = _first(values, f'id="{sections.SET_NAV_ANCHOR}"')
    assert _label(values, plain.LABEL_LAYER3) < anchor < _label(values, plain.LABEL_LAYER4)
    assert sum(f'id="{sections.SET_NAV_ANCHOR}"' in v for v in values) == 1
    # 不新增按鈕：畫面上的按鈕只有既有的「重新取數」一枚。
    # ~~`== ["存檔", "重新取數"]`~~ —— 有意識的行為變更，不是漏刪（客戶 2026-10-26 裁示第 7 節；J-6／J-14）：
    # 第一階段唯讀，`SET-4` 的「存檔」連同整塊不畫。44 待正式修正程序。
    assert sorted(b.label for b in at.button) == ["重新取數"]


def test_有逾期_需要注意列出外那一列_SET1比較欄加時鐘():
    """這支腳本另有一個層級取數失敗，燈是紅（失敗來源優先，44 SET-0 規則欄照舊）；黃燈那一句的改寫由
    `tests/ui_v2/test_set_reshape_logic.py` 驗。這裡驗 ③ 與 `SET-1` 在畫面上的樣子：③ 照樣列出「外」那一列。
    ~~燈上寫「失敗的來源層級」~~ → BL-0250 批次 3-A（`DEC-2026-10-19-05` 第 2 點；有意識的更正，不是漏刪）：那一筆取數紀錄的
    每一則訊息都是「未設定 FRED_API_KEY」⇒ 燈照舊紅（算一個失敗來源），字寫「尚未設定：資料來源的金鑰（市場指標）」。"""
    at = _run(SCAN.SCRIPTS["set"]["stale"])
    values = _md(at)
    lamp = _lamp(values)
    assert "尚未設定：資料來源的金鑰（市場指標）" in lamp and "失敗的來源層級" not in lamp
    assert "⛔" in lamp
    assert "筆資料超過你設定的新鮮度上限" not in "\n".join(values)
    assert "其餘正常" not in "\n".join(values)
    three = _label(values, plain.LABEL_ATTENTION)
    assert three != -1
    items = [v for v in values if 'class="v2-attention"' in v]
    assert items and all("超過你設的上限" in v and "◷" in v for v in items)
    table = next(v for v in values if "與上限比較" in v)
    assert "◷ 外" in table


@pytest.mark.parametrize("name", ["正常", "取數紀錄", "局部失敗"])
def test_沒有逾期_需要注意整段不畫(name):
    values = _md(_run(SCAN.SCRIPTS["set"][name]))
    assert _label(values, plain.LABEL_ATTENTION) == -1
    assert not [v for v in values if 'class="v2-attention"' in v]


def test_設定試算表未設定_燈寫第三句():
    values = _md(_run(SCAN.SCRIPTS["set"]["未設定"]))
    lamp = _lamp(values)
    assert "⬜ 無法判定：尚未設定設定試算表" in lamp
    assert "取數失敗" not in lamp


@pytest.mark.parametrize("name", _LIVE)
def test_全情境沒有勾與一切正常字樣(name):
    at = _run(SCAN.SCRIPTS["set"][name])
    text = "\n".join(SCAN.screen_texts(at))
    for word in ("✓", "其餘正常", "沒有例外"):
        assert word not in text, word


# ───────────────────────── 示範模式：畫面逐位元組不變 ─────────────────────────

_DEMO = SCAN._HEAD + "from ui_v2.set import page\npage.render()\n"


_ALL_CLEAR_EMPTY = '<span class="set-stword">狀態：無逾期、無失敗來源</span><span class="set-lamp-text"></span>'
_ALL_CLEAR_OLD = '<span class="set-stword">狀態：無逾期、無失敗來源</span><span class="set-lamp-text">資料齊、來源皆可達</span>'
_RESTORED = []


def _restore_all_clear(markup: str) -> str:
    if _ALL_CLEAR_EMPTY in markup:
        _RESTORED.append(1)
        return markup.replace(_ALL_CLEAR_EMPTY, _ALL_CLEAR_OLD)
    assert "資料齊" not in markup and "來源皆可達" not in markup
    return markup


_SET_TITLE_NEW = '<div class="set-title">⚙️ 設定</div>'
_HEX = re.compile(r"#[0-9a-fA-F]{6}\b")
_SET_TITLE_OLD = '<div class="set-title">設定與診斷</div>'


def test_示範模式畫面逐位元組不變():
    """示範模式不經過重排（44 之八開頭第 4 條）。17 情境 × 存檔失敗開關，把 AppTest 抓到的 markdown、展開區標題、按鈕、
    說明、單選、輸入欄標籤序列化後取 md5；基準值於 c44e1551（P1-④ 稽核通過版）量得。"""
    out = []
    for name in fixtures.ALL_SCENARIO_NAMES:
        for save_failed in ("0", "1"):
            from streamlit.testing.v1 import AppTest

            at = AppTest.from_string(f"import sys\nsys.path.insert(0, {str(_ROOT)!r})\nfrom ui_v2.set import page\n"
                                     "page.render()\n", default_timeout=60)
            at.query_params["scenario"] = name
            at.query_params["savefail"] = save_failed
            at.run()
            assert not at.exception
            # 客戶 2026-10-18 裁示 BL-0371（`DEC-2026-10-18-01`）：示範模式同樣不寫「資料齊、來源皆可達」。證明「示範畫面只差這一句」：
            # 把燈上那一格還原成舊字面，md5 必須回到舊基準值（c44e1551）；其餘一格不動。
            restored_md = [_restore_all_clear(m.value) for m in at.markdown]
            # 2026-10-27 BL-0478（DEC-2026-10-27-02，決策者：客戶）：頁名「設定與診斷」→「⚙️ 設定」；頁標題那一格還原成舊字面，
            # 證明示範畫面只差頁名這一格（每個畫面恰一格）。
            assert restored_md.count(_SET_TITLE_NEW) == 1, name
            restored_md = [_SET_TITLE_OLD if m == _SET_TITLE_NEW else m for m in restored_md]
            # 2026-10-27 BL-0484（DEC-2026-10-27-09，決策者：客戶；有意識的更正，不是漏刪）：主內容區改淺色，頁面 CSS 裡的色碼
            # （theme token 值）全換；色碼一律換成佔位再取摘要。證明「只差色碼」：同一支腳本在改動前的 main（75b8e7d6）上
            # 以同樣方式（色碼換佔位）量得 `a0b1d5c5b527d47e1433e0dac1d858d8`，與本檔現值相同；改動前的完整 md5
            # `1e269cdf55b4f1078cd9624bb6d88ec8` 含色碼，已不適用（舊句在寫下當時為真，被權衡掉的是色碼不得變）。
            restored_md = [_HEX.sub("#HEX", m) for m in restored_md]
            out.append([name, save_failed, restored_md, [e.label for e in at.expander],
                        [(b.label, b.disabled, b.help) for b in at.button], [c.value for c in at.caption],
                        [r.label for r in at.radio], [t.label for t in at.text_input] + [t.label for t in at.text_area]])
    digest = hashlib.md5(json.dumps(out, ensure_ascii=False).encode()).hexdigest()
    assert _RESTORED, "一盞齊燈也沒還原 —— 這一條會變成空掃"
    # ~~assert digest == "1e269cdf55b4f1078cd9624bb6d88ec8"~~（含色碼的舊基準值，還原 BL-0371 那一句之後；見上方 2026-10-27 說明）
    assert digest == "a0b1d5c5b527d47e1433e0dac1d858d8", digest   # 色碼換佔位後的基準值


def test_示範模式不重排_沒有需要注意_沒有導覽():
    at = _run(_DEMO)
    values = _md(at)
    assert _label(values, plain.LABEL_ATTENTION) == -1
    assert _first(values, f'href="#{sections.SET_NAV_ANCHOR}"') == -1
    assert not [e for e in at.expander if e.label.startswith(("規則參數卡", "來源健康卡"))]


# ───────────────────────── 2026-10-18 獨立稽核回修（M1、S3、S5） ─────────────────────────


def test_未設定_規則參數卡摘要寫紅字那一句_不寫0個鍵():
    """M1：正式模式未設定時，`SET-3` 的佔位併入卡頭紅字（★10）、沒有任何列；摘要要寫出那一句，不得寫「0 個鍵」。"""
    at = _run(SCAN.SCRIPTS["set"]["未設定"])
    label = _expander(at, "規則參數卡　—　").label
    assert "⛔" in label and "0 個鍵" not in label, label


def test_未設定_導覽照舊顯示_它指向的重新取數停用():
    """S3（登記情境 C3）：重新取數不可執行時，`SET-0` 燈下那一枚導覽照 44 仍然顯示；落點那一枚「重新取數」是停用的。"""
    at = _run(SCAN.SCRIPTS["set"]["未設定"])
    values = _md(at)
    assert _first(values, f'href="#{sections.SET_NAV_ANCHOR}"') != -1
    assert _first(values, f'id="{sections.SET_NAV_ANCHOR}"') != -1
    refetch = [b for b in at.button if b.label == "重新取數"]
    assert len(refetch) == 1 and refetch[0].disabled


# S5：正式模式的純黃燈情境（只有逾期、沒有失敗來源）。資料取自示範情境 stale（不打網路），經正式模式的整條路徑畫出。
_PURE_YELLOW = SCAN._HEAD + """
from ui_v2.set import page, fixtures
_ds = fixtures.scenario("stale")
_notes = {"mask_token": "<已遮蔽>", "pending_tables": [], "wired_tiers": ["淨值", "配息", "市場指標", "其他"],
          "pages_reading_settings": [], "gate": {"state": "ok"}, "title": {"state": "ok", "text": "測試用設定本"},
          "table_errors": {}, "structure": {}, "source_cooldowns": []}
page.render(load_live=lambda: {"dataset": _ds, "notes": _notes}, save_live=lambda *a: {}, refetch_live=lambda t: {})
"""


def test_純黃燈_燈寫類數句_需要注意列出同一類():
    from ui_v2.set import logic as set_logic

    overdue = set_logic.find_block(set_logic.build_page_model(fixtures.scenario("stale")), "SET-1")["_overdue"]
    assert overdue > 0
    values = _md(_run(_PURE_YELLOW))
    lamp = _lamp(values)
    assert f"◷ {overdue} 類資料超過你設的上限" in lamp
    assert "狀態：有逾期" in lamp and "失敗的來源層級" not in lamp and "其餘正常" not in lamp
    assert "筆資料超過你設定的新鮮度上限" not in "\n".join(values)
    items = [v for v in values if 'class="v2-attention"' in v]
    assert len(items) == overdue
