# -*- coding: utf-8 -*-
"""一般畫面去工程化（Phase 3 P0-①）畫面測試（slow lane；需要 streamlit）。

依據 `docs/v2/44_fund_ui_ssot.md` 第七節第三小節之七其二（`DEC-2026-10-17-03`）：五頁正式模式 × 情境
（正常、未設定、取數失敗、局部失敗、不是最新；持倉體檢與資產配置另加整頁錯誤畫面），一般畫面抽出來的字對下列
**0 命中**：塊代號、`層 1～4`、原始鍵名（取自 `ui_v2/set/spec.py` 的表名、欄名、設定鍵）、秘密鍵名、
例外型別名、`returned None`、`kind=`、`Traceback`。

設定與診斷頁的射程（44 同條第 1、2、8 條；本批派工單）：
- 塊代號與層字樣：排除 `SET-7` 欄位對照表（44 明文照列「用到它的塊代號清單」）與「進階診斷（原始訊息）」；
- 鍵名：只看 `SET-0`、`SET-1`（本批只換 `SET-1` 那兩個鍵名；`SET-3`／`SET-4`／`SET-7` 的鍵名不在本批）；
- 失敗原文、秘密鍵名、例外型別名：**不在本頁的檢查射程** —— 設定與診斷頁照印原文（`SET-2` 規則欄
  「訊息原文照印」原字保留），本批不改本頁的失敗訊息。

正控：同一個抽字器掃進階診斷那一枚要命中原文；掃示範模式要命中塊代號 —— 證明抽字器真的抽得到。
"""

from __future__ import annotations

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

import _plain_scan as SCAN  # noqa: E402

from ui_v2 import plain  # noqa: E402
from ui_v2.set import spec  # noqa: E402
from ui_v2.set import live as set_live  # noqa: E402

_KEYS = {table for table, _ in spec.SPEC_TABLES}
_KEYS |= {column for _, columns in spec.SPEC_TABLES for column in columns}
_KEYS |= {key for key, _ in spec.SPEC_SETTING_KEYS}
_SECRETS = ("POLICY_SHEET_ID", "SETTINGS_SHEET_ID", "POOL_SHEET_ID", "FRED_API_KEY", "google_service_account",
            "PROXY_URL")

PATTERNS = {
    "塊代號": re.compile(r"\b(MKT|HLD|EXP|ALO|SET)-\d\b"),
    "層字樣": re.compile(r"層\s*[1-4]"),
    "原始鍵名": re.compile(
        r"(?<![A-Za-z0-9_])(" + "|".join(sorted(map(re.escape, _KEYS), key=len, reverse=True)) + r")(?![A-Za-z0-9_])"
    ),
    "秘密鍵名": re.compile("|".join(_SECRETS)),
    "例外型別名": re.compile(r"\w+(Error|Exception)"),
    "實作字樣": re.compile(r"returned None|kind=|Traceback"),
}

_CASES = [(page, name) for page, scripts in SCAN.SCRIPTS.items() for name in scripts]


def _run(script):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(script, default_timeout=90)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _hits(texts, names):
    out = []
    for text in texts:
        for name in names:
            match = PATTERNS[name].search(text)
            if match:
                out.append((name, match.group(0), " ".join(text.split())[:160]))
    return out


def _set_block_texts(at, codes):
    """設定與診斷頁：`data-block` 為 `codes` 之一的那幾格（欄）裡的字。"""
    out = []

    def collect(node, sink):
        sink.extend(SCAN._element_texts(node))
        for child in getattr(node, "children", {}).values():
            collect(child, sink)

    def walk(node):
        kind = type(node).__name__
        if kind in ("Column", "Markdown"):
            raw = []

            def grab(n):
                if type(n).__name__ == "Markdown":
                    raw.append(n.value)
                for ch in getattr(n, "children", {}).values():
                    grab(ch)

            grab(node)
            if any(f'data-block="{code}"' in value for code in codes for value in raw):
                if kind == "Column":
                    collect(node, out)
                    return
                if kind == "Markdown":
                    out.extend(SCAN._element_texts(node))
        for child in getattr(node, "children", {}).values():
            walk(child)

    walk(at._tree)
    return out


@pytest.mark.parametrize("page, name", _CASES, ids=[f"{p}-{n}" for p, n in _CASES])
def test_一般畫面沒有工程字樣(page, name):
    at = _run(SCAN.SCRIPTS[page][name])
    if page != "set":
        texts = SCAN.screen_texts(at)
        assert len(texts) >= 3
        assert _hits(texts, PATTERNS) == []
        return
    # BL-0250 批次 3-A U7（d）：`SET-7` 正式模式收合標題改「欄位對照（進階）」（`ui_v2/set/live.py::SET7_TITLE`），照舊排除。
    texts = SCAN.screen_texts(at, skip_expanders=(plain.ADVANCED_DIAG_TITLE, plain.BLOCK_NAMES["SET-7"], set_live.SET7_TITLE))
    assert len(texts) >= 10
    assert _hits(texts, ("塊代號", "層字樣")) == []
    key_texts = _set_block_texts(at, ("SET-0", "SET-1"))
    assert key_texts, "找不到 SET-0／SET-1 —— data-block 定位失效"
    assert [h for h in _hits(key_texts, ("原始鍵名",)) if h[1] in ("days_calendar", "set_max_age_days")] == []


_RAW_EXPECTED = {
    ("mkt", "未設定"): ("未設定 FRED_API_KEY", "fetch_url returned None: ^VIX (kind=unreachable)", "未設定試算表 ID，暫停寫入"),
    ("hld", "未設定"): ("未設定保單試算表 ID（POLICY_SHEET_ID），不讀取",),
    ("hld", "整頁失敗"): ("RuntimeError", "fetch_url returned None (kind=unreachable)"),
    ("exp", "未設定"): ("未設定試算表 ID，暫停寫入", "選股池未設定雲端來源"),
    ("alo", "未設定保單"): ("未設定保單試算表 ID（POLICY_SHEET_ID），不讀取",),
    ("alo", "整頁失敗"): ("ValueError", "兩列的 bucket 不同"),
}


@pytest.mark.parametrize("page, name", sorted(_RAW_EXPECTED), ids=[f"{p}-{n}" for p, n in sorted(_RAW_EXPECTED)])
def test_原文不刪除_收進跨頁的原始訊息(page, name):
    at = _run(SCAN.SCRIPTS[page][name])
    store = at.session_state[plain.RAW_STATE]
    texts = "\n".join(entry["text"] for entry in store[page]["entries"])
    for piece in _RAW_EXPECTED[(page, name)]:
        assert piece in texts, (piece, texts[:500])


def test_正常情境寫空_不留上一輪的錯():
    at = _run(SCAN.SCRIPTS["hld"]["正常"])
    assert at.session_state[plain.RAW_STATE]["hld"]["entries"] == []


def test_正控_進階診斷照印原文與塊代號():
    at = _run(SCAN.SCRIPTS["set"]["局部失敗"])
    diag = SCAN.expander_texts(at, plain.ADVANCED_DIAG_TITLE)
    assert diag, "進階診斷那一枚不在畫面上"
    assert any(SCAN.SET_PRESET_RAW in text for text in diag)
    names = {h[0] for h in _hits(diag, PATTERNS)}
    assert {"塊代號", "實作字樣"} <= names, names
    labels = [e.label for e in at.expander]
    assert labels[-1] == plain.ADVANCED_DIAG_TITLE            # ④詳細資料的最後一枚
    assert not [e for e in at.expander if e.label == plain.ADVANCED_DIAG_TITLE and e.proto.expanded]


def test_進階診斷_原文含空行與Markdown語法_不跳出表格_不變成標題():
    """原本在標的探索候選清單格內驗的那一條（`test_exp_live_page.py` 的 Q M1）跟著原文搬到這裡：
    原文含 `\\n\\n`、`## `、`|`、`*` —— 進階診斷的表格字串裡一個都不得以語法形式出現，內容照留。"""
    raw = "⛔ 取數失敗：x\n\n## 注入標題\n| a | b |\n*粗體*"
    at = _run(SCAN._set(preset={"hld": [{"where": "HLD-2 績效與風險卡", "text": raw}]}))
    diag = [e for e in at.expander if e.label == plain.ADVANCED_DIAG_TITLE][0]
    table = [m.value for m in diag.markdown if "注入標題" in m.value]
    assert len(table) == 1
    assert "\n" not in table[0] and "## " not in table[0] and "|" not in table[0] and "*粗體*" not in table[0]
    assert "&#35;&#35; 注入標題" in table[0] and "&#124;" in table[0] and "&#42;粗體&#42;" in table[0]
    assert not at.code


def test_進階診斷_沒有開過其他頁時照實說():
    at = _run(SCAN.SCRIPTS["set"]["正常"])
    diag = "\n".join(SCAN.expander_texts(at, plain.ADVANCED_DIAG_TITLE))
    from ui_v2.set import page as set_page

    assert set_page.ADVANCED_DIAG_NO_PAGE in diag


_DEMO = {
    "mkt": "from ui_v2.mkt import page\npage.render()\n",
    "hld": "from ui_v2.hld import page\npage.render()\n",
    "exp": "from ui_v2.exp import page\npage.render()\n",
    "alo": "from ui_v2.alo import page\npage.render()\n",
    "set": "from ui_v2.set import page\npage.render()\n",
}


@pytest.mark.parametrize("page", sorted(_DEMO))
def test_正控_示範模式照舊有塊代號與層字樣_沒有進階診斷(page):
    at = _run(SCAN._HEAD + _DEMO[page])
    names = {h[0] for h in _hits(SCAN.screen_texts(at), PATTERNS)}
    assert {"塊代號", "層字樣"} <= names, names
    assert plain.ADVANCED_DIAG_TITLE not in [e.label for e in at.expander]
    assert plain.RAW_STATE not in at.session_state


@pytest.mark.parametrize("page", ["mkt", "hld", "exp", "alo", "set"])
def test_正式模式塊代號只在data_block屬性(page):
    at = _run(SCAN.SCRIPTS[page]["正常"])
    html = "\n".join(m.value for m in at.markdown)
    found = set(re.findall(r'data-block="([A-Z]{3}-\d)"', html))
    assert f"{page.upper()}-0" in found and len(found) >= 4, found
    assert not re.search(r'class="[a-z]+-card-code"', html)


_EXP_LIVE = SCAN._HEAD + """
import _exp_live_stub as STUB
from ui_v2.exp import page
page.render(load_live=STUB.load_live, save_live=STUB.save_setting)
"""


def test_EXP1欄位下拉_中文名顯示_底層存欄位鍵_清空照樣可存():
    import json

    import _exp_live_stub as STUB

    STUB.reset()                                               # 替身只在這裡種一次（腳本每次重跑不重設）
    STUB.WIRED.append(True)
    STUB.STORE["exp_filter_rules"] = json.dumps([{"field": "fund_code", "op": "不等於", "value": "ZZZ"}])
    at = _run(_EXP_LIVE)
    field = [s for s in at.selectbox if s.label == "欄位"]
    assert len(field) == 1
    assert field[0].value == "fund_code"                      # 已存的值照舊選在那一格
    from ui_v2.exp import logic as E

    assert field[0].options == [plain.key_name(f) for f in E.FUND_PROFILE_FIELDS]
    assert "fund_code" not in field[0].options
    field[0].select_index(field[0].options.index(plain.key_name("ccy"))).run()
    assert [s for s in at.selectbox if s.label == "欄位"][0].value == "ccy"   # 底層值是欄位鍵
    save = [b for b in at.button if b.label == E.TEXT_SAVE]
    save[0].click().run()
    assert STUB.SAVES[-1][0] == "exp_filter_rules" and '"field": "ccy"' in STUB.SAVES[-1][1]
    clear = [b for b in at.button if b.label == E.TEXT_CLEAR_ROW]
    clear[0].click().run()
    [b for b in at.button if b.label == E.TEXT_SAVE][0].click().run()
    assert STUB.SAVES[-1] == ("exp_filter_rules", "[]", STUB.SAVES[-1][2])
    STUB.reset()


def test_EXP1欄位下拉_不在清單裡的舊值照樣列出_存檔判定照舊由live決定():
    """44 第七節第三小節之七其二第 6 條：未知的舊值照樣保留。下拉把它列為選項、選在原位，不默默丟掉；
    按存檔時寫不寫得進去照舊由 `live.exp1_save_entries` 判定（本批不改寫入判定）。"""
    import _exp_live_stub as STUB
    from streamlit.testing.v1 import AppTest

    from ui_v2.exp import live
    from ui_v2.exp import logic as E
    from ui_v2.exp import page as exp_page

    STUB.reset()
    loaded = STUB.load_live()
    at = AppTest.from_string(_EXP_LIVE, default_timeout=90)
    at.session_state[exp_page._SEEDED_STATE] = live.settings_fingerprint(loaded["notes"]["settings"])
    at.session_state[exp_page._RULES_STATE] = [{"_id": 1, "field": "legacy_field", "op": "等於", "value": "1"}]
    at.session_state[exp_page._RULE_SEQ_STATE] = 1
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    box = at.selectbox(key="exp1live_1_field")
    assert box.value == "legacy_field" and "legacy_field" in box.options
    expected = live.exp1_save_entries([{"field": "legacy_field", "op": "等於", "value": "1"}])
    [b for b in at.button if b.label == E.TEXT_SAVE][0].click().run()
    if expected[0]["error"]:
        assert STUB.SAVES == []                                  # 與改成下拉之前相同：live 擋下、不寫
    else:
        assert STUB.SAVES[-1][1] == expected[0]["value"]
    STUB.reset()


# ───────── 新 B UI 第一階段唯讀下的休眠寫入路徑（2026-10-26） ─────────
@pytest.fixture(autouse=True)
def _dormant_write_path(monkeypatch):
    """本檔驗的是**休眠中的寫入路徑**（存檔怎麼寫、結果怎麼顯示、或以 L2 存檔佈置測試資料）。第一階段唯讀
    （客戶 2026-10-26 裁示第 7 節；`DEC-2026-10-25-04` J-6、2026-10-26 J-14 補記）下 `is_read_only()` 恆為 True、
    五頁正式模式不畫「存檔」與 `SET-4`；這裡把兩道開關同時打開再驗，**不是**宣稱 production 可寫。
    第一階段的真實行為（不畫、短路、零呼叫）見 `tests/ui_v2/test_readonly_write_surface_guard.py`。"""
    import pathlib as _pathlib
    import sys as _sys

    _sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parent))
    import _dormant_writes

    _dormant_writes.enable(monkeypatch)
