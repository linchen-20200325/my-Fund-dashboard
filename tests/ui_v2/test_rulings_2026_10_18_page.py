# -*- coding: utf-8 -*-
"""客戶 2026-10-18 裁示（`docs/DECISIONS.md` `DEC-2026-10-18-01`；44 第七節第三小節之九）的畫面測試。

用 `tests/ui_v2/_plain_scan.py` 的正式模式腳本（真 L2 ＋ 真 L1 ＋ 假 gspread，不打網路）：
- BL-0371：正式模式 `MKT-0`、`SET-0` 燈上不出現「資料齊」「來源皆可達」，全情境畫面不出現「正常」；
- BL-0373：市場總覽取數失敗而沒有任何觀測的鍵，`MKT-7` 那一列是「取數失敗」與 ⛔，不是「資料未備」；
- S1／C1：只缺設定試算表 → 第三句；設定試算表與服務帳戶都缺 → ⛔（與只缺服務帳戶同一盞）；
- C2：燈下那一枚導覽是同頁錨點（不是按鈕、不重跑），落點「重新取數」那一枚展開區照舊收合（不替使用者展開）。
**C3 未裁**，本檔不碰（`test_set_reshape_page.py::test_未設定_導覽照舊顯示_它指向的重新取數停用` 照舊）。
"""

from __future__ import annotations

import pathlib
import sys

import pytest

pytestmark = pytest.mark.slow

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_ROOT))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

import _plain_scan as SCAN  # noqa: E402

from ui_v2 import sections  # noqa: E402


def _run(script):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(script, default_timeout=90)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _md(at) -> list:
    return [m.value for m in at.markdown]


def _one(values, needle) -> str:
    hits = [v for v in values if needle in v]
    assert len(hits) == 1, hits
    return hits[0]


# ───────────────────────── BL-0371 ─────────────────────────


@pytest.mark.parametrize("page, name", [(p, n) for p in ("mkt", "set") for n in SCAN.SCRIPTS[p]])
def test_BL0371_正式模式燈上不寫資料齊或來源皆可達_畫面不寫正常(page, name):
    at = _run(SCAN.SCRIPTS[page][name])
    values = _md(at)
    lamp = _one(values, 'class="mkt-light"' if page == "mkt" else 'class="set-lamp"')
    for word in ("資料齊", "來源皆可達", "正常"):
        assert word not in lamp, (page, name, word)
    assert "正常" not in "\n".join(SCAN.screen_texts(at)), (page, name)


def test_BL0371_市場總覽三塊皆ok_燈上沒有文案_燈色照舊():
    values = _md(_run(SCAN.SCRIPTS["mkt"]["正常"]))
    lamp = _one(values, 'class="mkt-light"')
    assert '<div class="mkt-light-text"></div>' in lamp, lamp


# ───────────────────────── BL-0373：MKT-7 ─────────────────────────

_MKT7_FAILED = SCAN._mkt(
    '(lambda d: dict(d, rows=[r for r in d["rows"] if r["indicator_key"] != "vol_index"]))'
    "(fixtures.dataset_mkt1_fetch_failed())",
    settings=SCAN._MKT_SAVED,   # 已存清單含 vol_index（正式模式從未存過時明細不全列）
)


def test_BL0373_MKT7取數失敗而沒有觀測的鍵_寫取數失敗與禁止號_不寫資料未備():
    at = _run(_MKT7_FAILED)
    table = _one(_md(at), "<th>最近觀測日</th>")
    name = "波動度指數"   # 一般畫面把指標鍵 vol_index 換成中文名（`plain`）
    row = table.split(name, 1)[1].split("</tr>", 1)[0]
    assert "取數失敗" in row and row.count("⛔") >= 4, row
    assert "資料未備" not in row and "◇" not in row and "⬜" not in row, row


_ERR = "HTTPSConnectionPool(host='example.invalid'): Max retries exceeded"
_MKT6_MIXED = SCAN._mkt('dict(fixtures.dataset_mkt1_fetch_failed(), rows=[])', settings=SCAN._MKT_SAVED)
_MKT6_ALL_FAILED = SCAN._mkt(
    'dict(fixtures.dataset_mkt1_fetch_failed(), rows=[], errors={"vol_index": %r, "credit_spread_pct": %r})' % (_ERR, _ERR),
    settings=SCAN._MKT_SAVED,
)


def test_BL0373_MKT5取數失敗與資料未備分兩行各帶符號():
    at = _run(_MKT7_FAILED)
    captions = [c.value for c in at.caption]
    failed = [c for c in captions if c.startswith("⛔ 取數失敗：")]
    missing = [c for c in captions if c.startswith("◇ 資料未備：")]
    assert failed == ["⛔ 取數失敗：波動度指數"], captions
    assert all("波動度指數" not in c for c in missing), captions
    assert not [c for c in captions if c.startswith("資料未備：") or c.startswith("取數失敗：")], captions   # 都帶符號


def test_BL0373_MKT5資料未備的鍵_沒有失敗紀錄_寫菱形資料未備():
    script = SCAN._mkt(
        '(lambda d: dict(d, errors={}, rows=[r for r in d["rows"] if r["indicator_key"] != "vol_index"]))'
        "(fixtures.dataset_mkt1_fetch_failed())",
        settings=SCAN._MKT_SAVED,
    )
    captions = [c.value for c in _run(script).caption]
    assert "◇ 資料未備：波動度指數" in captions, captions
    assert not [c for c in captions if c.startswith("⛔ 取數失敗：")], captions


def test_BL0373_MKT6成因混合_資料未備那一句照留_另加一行取數失敗():
    text = "\n".join(SCAN.screen_texts(_run(_MKT6_MIXED)))
    assert "資料未備：市場指標 尚無資料" in text and "⛔ 取數失敗：波動度指數" in text, text[-800:]


def test_BL0373_MKT6全部取數失敗_表尾只寫取數失敗():
    text = "\n".join(SCAN.screen_texts(_run(_MKT6_ALL_FAILED)))
    assert "資料未備：市場指標 尚無資料" not in text
    assert "⛔ 取數失敗" in text


# ───────────────────────── S1／C1 ─────────────────────────

_BOTH_UNSET = SCAN._set(cfg={})
_ONLY_SA_MISSING = SCAN._set(cfg={"SETTINGS_SHEET_ID": "sheet-for-plain-scan"})


def test_S1_只缺設定試算表_燈寫第三句():
    lamp = _one(_md(_run(SCAN.SCRIPTS["set"]["未設定"])), 'class="set-lamp"')
    assert sections.SET_NO_SHEET_TEXT in lamp and "取數失敗" not in lamp


def test_C1_設定試算表與服務帳戶都缺_燈為禁止號_與只缺服務帳戶同一盞():
    both = _one(_md(_run(_BOTH_UNSET)), 'class="set-lamp"')
    only_sa = _one(_md(_run(_ONLY_SA_MISSING)), 'class="set-lamp"')
    # ~~"狀態：取數失敗" in both~~ → 同批總管裁定（適用 `DEC-2026-10-19-05` 第 3 點；有意識的更正，不是漏刪）：
    # 成因全是缺 Google 服務帳戶時燈字寫尚未設定；⛔ 紅燈與「與只缺服務帳戶同一盞」照舊。
    assert "⛔" in both and "狀態：尚未設定" in both and "尚未設定：Google 服務帳戶" in both, both
    assert sections.SET_NO_SHEET_TEXT not in both and "取數失敗" not in both, both
    assert both == only_sa


def test_C1C3_兩者都未設定時_燈下導覽照舊顯示_落點那一枚重新取數停用():
    """C3 未裁，現況照舊（不改行為）：兩者都未設定、燈為 ⛔ 時，燈下那一枚同頁導覽仍顯示。"""
    at = _run(_BOTH_UNSET)
    values = _md(at)
    assert _one(values, f'href="#{sections.SET_NAV_ANCHOR}"')
    assert _one(values, f'id="{sections.SET_NAV_ANCHOR}"')
    refetch = [b for b in at.button if b.label == "重新取數"]
    assert len(refetch) == 1 and refetch[0].disabled


# ───────────────────────── C2 ─────────────────────────


@pytest.mark.parametrize("name", list(SCAN.SCRIPTS["set"]))
def test_C2_導覽是同頁錨點_不是按鈕_重新取數那一枚展開區照舊收合(name):
    at = _run(SCAN.SCRIPTS["set"][name])
    values = _md(at)
    nav = _one(values, f'href="#{sections.SET_NAV_ANCHOR}"')
    assert "<a " in nav and sections.SET_NAV_LABEL in nav and "onclick" not in nav
    assert sections.SET_NAV_LABEL not in [b.label for b in at.button]          # 不是 st.button：按下不重跑、不取數
    refetch = [e for e in at.expander if e.label.startswith("重新取數")]
    assert len(refetch) == 1 and refetch[0].proto.expanded is False, [e.label for e in at.expander]
