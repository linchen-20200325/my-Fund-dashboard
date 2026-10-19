# -*- coding: utf-8 -*-
"""BL-0250 實機驗收回修 批次 1（客戶 2026-10-19 裁示，`docs/DECISIONS.md` `DEC-2026-10-19-04`）的畫面守衛。

情境腳本與抽字器重用 `tests/ui_v2/_plain_scan.py`（五頁正式模式；只用各頁 fixtures／替身，不打網路）。
示範模式不變另由各頁既有守衛與本檔最後一組正控釘住。
"""

from __future__ import annotations

import functools
import pathlib
import sys

import pytest

_HERE = pathlib.Path(__file__).resolve().parent
for _p in (_HERE, _HERE.parent, _HERE.parents[1]):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

pytestmark = pytest.mark.slow

import _plain_scan as SCAN  # noqa: E402

from ui_v2 import plain  # noqa: E402

_EXTRA = {
    ("alo", "partial"): SCAN._alo("partial"),
    ("alo", "nobucket"): SCAN._alo("nobucket"),
}


@functools.lru_cache(maxsize=None)
def _at(page, name):
    from streamlit.testing.v1 import AppTest

    script = _EXTRA.get((page, name)) or SCAN.SCRIPTS[page][name]
    at = AppTest.from_string(script, default_timeout=90)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _texts(page, name):
    skip = (plain.ADVANCED_DIAG_TITLE,) if page == "set" else ()
    return [" ".join(t.split()) for t in SCAN.screen_texts(_at(page, name), skip_expanders=skip)]


def _joined(page, name):
    return "\n".join(_texts(page, name))


def _status_line(page, name):
    lines = [t for t in _texts(page, name) if t.startswith("資料狀態：") or t.startswith("資料截至")]
    assert lines, _texts(page, name)[:6]
    return lines[0]


def _expander_titles(page, name):
    out = []

    def walk(node):
        if type(node).__name__ == "Expander":
            out.append(str(node.label))
        for child in getattr(node, "children", {}).values():
            walk(child)

    walk(_at(page, name)._tree)
    return out


def _block_text(page, name, code):
    out = []

    def walk(node):
        if type(node).__name__ == "Markdown" and f'data-block="{code}"' in (node.value or ""):
            out.append(" ".join(SCAN.markdown_text(node.value).split()))
        for child in getattr(node, "children", {}).values():
            walk(child)

    walk(_at(page, name)._tree)
    assert out, code
    return out[0]


# ───────────────────────── 1. 市場總覽 MKT-6／MKT-7 ─────────────────────────


def test_MKT7_台北時間_表頭註明時區_不再寫UTC():
    text = _joined("mkt", "正常")
    assert "最近取得時間（UTC+8）" in text and "2026-09-24 10:00" in text
    assert "2026-09-24T02:00:00Z" not in text
    assert "時間以 UTC 顯示" not in text


def test_MKT6_取得時間台北時間_是否修正改是否_表頭指標():
    text = _joined("mkt", "正常")
    assert "取得時間（UTC+8）" in text and "2026-09-17 10:00" in text
    assert " False" not in text and " True" not in text
    assert "指標鍵" not in text
    table = [t for t in _texts("mkt", "正常") if t.startswith("指標 觀測日")]
    assert table and " 否" in table[0]


# ───────────────────────── 2. 標的探索佔位字 ─────────────────────────


# ~~正式模式沒有佔位字、④ 寫「◇ 資料未備」~~ → 獨立稽核 M1 後撤回（總管裁定；有意識的更正，不是漏刪）：
# EXP 核心卡來源層級缺值的符號（◇／⬜／其他）待客戶 Decision Gate；佔位字外漏維持現況。本條鎖住現況，客戶裁示後改。
@pytest.mark.parametrize("name", list(SCAN.SCRIPTS["exp"]))
def test_EXP_佔位字維持現況_待客戶裁示(name):
    provenance = [t for t in _texts("exp", name) if t.startswith("卡 項目 來源與新鮮度")]
    assert provenance and "〔來源層級〕" in provenance[0] and "〔新鮮度〕" in provenance[0]
    assert "◇ 資料未備" not in provenance[0]


# ───────────────────────── 3. 資產配置資料狀態行 ─────────────────────────


def test_ALO_格內資料未備_狀態行報菱形():
    assert "◇ 資料未備" in _joined("alo", "partial")
    assert "◇ 資料未備" in _status_line("alo", "partial")


def test_ALO_正常_狀態行不報菱形():
    assert "◇" not in _status_line("alo", "正常")


# ───────────────────────── 4. ALO-6 百分比 ─────────────────────────


def test_ALO6_表尾合計是百分比():
    texts = _texts("alo", "正常")
    assert "總體佔比合計 100.0%" in texts
    assert "總體佔比合計 1" not in texts
    assert any(t.startswith("類別內佔比合計") and t.endswith("100.0%") for t in texts)


# ───────────────────────── 5. G5 ─────────────────────────


def test_G5_純過期淨值寫菱形():
    text = _joined("hld", "超過10日")
    assert "◇ 另有 3 檔淨值超過 10 日未更新（資料未備），未列入" in text
    assert "◇ 其中 3 檔淨值超過 10 日未更新（資料未備）" in text
    assert "⬜ 另有" not in text and "⬜ 其中" not in text


def test_G5_退回預存照舊紅並帶日期_與純過期不合併():
    text = _joined("hld", "退回預存過期")
    assert "⛔ 淨值 取數失敗：AAAA：改用 2026-09-18 的預存淨值" in text
    assert "◇ 另有 2 檔淨值超過 10 日未更新（資料未備），未列入" in text   # AAAA 不在這 2 檔裡


# ───────────────────────── 6. G3 ─────────────────────────


def test_G3_持倉體檢_全部尚未設定_燈不寫取數失敗():
    light = _block_text("hld", "未設定", "HLD-0")
    assert "狀態：尚未設定" in light and "尚未設定：保單試算表、設定試算表" in light
    assert "取數失敗" not in light


def test_G3_持倉體檢_真的取數失敗_燈照舊():
    assert "狀態：取數失敗" in _block_text("hld", "取數失敗", "HLD-0")


def test_G3_資產配置_展開區標題寫尚未設定哪一項():
    titles = _expander_titles("alo", "未設定")
    assert "開始試算　—　⛔ 尚未設定：設定試算表" in titles
    assert not any("取數失敗" in t for t in titles), titles
    assert "狀態：尚未設定" in _block_text("alo", "未設定", "ALO-0")


def test_G3_資產配置_真的取數失敗_標題照舊():
    assert any(t.endswith("⛔ 取數失敗") for t in _expander_titles("alo", "取數失敗"))


def test_G3_市場總覽_只換屬尚未設定的那一張卡_設定讀不到統一說法():
    light = _block_text("mkt", "未設定", "MKT-0")
    assert "風險情緒卡：取數失敗" in light                      # 波動度指數真的取數失敗
    assert "資金與匯率卡：尚未設定：資料來源的金鑰" in light
    assert "資料面：風險情緒卡 ⛔ 取數失敗；景氣位置卡 ◇ 資料未備；資金與匯率卡 ⛔ 尚未設定：資料來源的金鑰" in _texts("mkt", "未設定")
    titles = _expander_titles("mkt", "未設定")
    assert "觀察窗與比較基準輸入　—　尚未設定：設定試算表" in titles
    assert not any("設定讀不到" in t for t in _texts("mkt", "未設定") + titles)


def test_G3_標的探索_展開區摘要寫尚未設定哪一項():
    titles = _expander_titles("exp", "未設定")
    assert "欄位與排序設定　—　⛔ 尚未設定：設定試算表" in titles
    assert "尚未設定：選股池的雲端來源、設定試算表，暫無篩選軌跡" in _texts("exp", "未設定")


# ───────────────────────── 7. 字句（不需解凍的 A／B 項） ─────────────────────────


def test_SET_取數紀錄射程只說一次_不寫set頁():
    for name in SCAN.SCRIPTS["set"]:
        texts = _texts("set", name)
        assert texts.count("這裡只記在本頁按「重新取數」的結果；其他頁開頁時的取數不在這裡") == 1, name
        assert not any("set 頁" in t for t in texts), name


def test_SET_摘要只寫個數_標籤中文_影響說明_新鮮度上限():
    titles = _expander_titles("set", "正常")
    assert "規則參數卡　—　18 個設定，18 個未設定" in titles
    assert "參數編輯　—　18 個設定，18 個未設定" in titles
    texts = _texts("set", "正常")
    assert "計算基礎" in texts and not any(t.startswith("alo_basis（") for t in texts)
    assert "目前沒有畫面用到這個設定" in texts
    assert not any("44 各塊的來源欄" in t for t in texts)
    assert "新鮮度上限：⬜ 未設定" in texts and not any("新鮮度上限日數）" in t for t in texts)


def test_SET_服務帳戶與試算表ID字樣():
    failed = _joined("set", "取數失敗")
    assert "未設定 Google 服務帳戶" in failed
    unset = _texts("set", "未設定")
    assert "⛔ 尚未設定：試算表 ID" in unset
    # 來源健康卡照印原文（44 SET-2），存檔按鈕的停用原因屬寫入情境，兩者照舊。
    assert "⛔ 未設定試算表 ID，暫停寫入" in unset


def test_ALO_字句():
    texts = _texts("alo", "正常")
    assert "類別在 Sheets 維護；這裡的存檔只存比重基準與類別名稱" in texts
    assert "持倉資料在 Sheets 維護，本儀表板唯讀" in texts         # 44 ALO-4 逐字
    assert "目標修改紀錄　—　目標比重、容許帶皆已設定" in _expander_titles("alo", "正常")
    assert "「未分類」沒有目標比重，這一列不計算目標、差額與內外" in _texts("alo", "nobucket")
    help_texts = [b.help for b in _at("alo", "正常").button if b.disabled]
    assert "試算存檔尚未開放" in help_texts


def test_EXP_字句():
    texts = _texts("exp", "正常")
    assert not any(t.startswith("本塊不自取數") for t in texts)
    assert "先在結果清單勾一檔「對照」" in texts
    assert "取數失敗，暫無篩選軌跡" in _texts("exp", "取數失敗")
    assert not any("正式模式" in t for t in texts)


def test_HLD_字句():
    texts = _texts("hld", "正常")
    for gone in ("第三個值", "這兩個值原本各是", "欄位一律無預設值", "點一檔展開一檔", "展開中的那一檔", "輸出值與該列指標名"):
        assert not any(gone in t for t in texts), gone
    assert "依基金代碼排列（不代表優先順序）" in _joined("hld", "正常")
    assert "週末與假日沒有資料屬正常。" in texts
    assert "偏離提示只客觀描述現況與目標差距，不提供任何處置方向。" in _joined("hld", "正常")   # 44 逐字照留
