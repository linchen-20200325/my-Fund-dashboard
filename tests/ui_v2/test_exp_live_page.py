# -*- coding: utf-8 -*-
"""標的探索正式模式的執行期測試（slow lane；需要 streamlit）。

依據客戶 2026-10-13 裁示（B 線標的探索正式模式第一批）與 docs/v2/49_data_integration_plan.md §4.7 第 4 點：
- 把 `page` 模組上的 `fixtures` 換成「一存取就拋錯」的替身，正式模式照樣渲染完成（正控：示範模式必炸）；
- 篩選條件**只有成功儲存的才生效**：輸入欄填了不存 → 結論列與候選清單不動；按存檔 → 下一次重跑才套用；
- 基本資料缺欄：基金照列、缺的格「⬜ 資料未備：<原因>」，畫面上沒有示意字樣、沒有 None；
- `EXP-4` 一成一敗：畫面照實寫哪一鍵成功、哪一鍵失敗。

載入與寫入函式用替身（`tests/ui_v2/_exp_live_stub.py`），不呼叫 `source`、不打任何網路。
"""

import html
import json
import pathlib
import re
import sys

import pytest

# 整檔標 slow：畫面測試不進 fast lane（守衛：tests/ui_v2/test_ui_v2_lane_guards.py）。
pytestmark = pytest.mark.slow

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_HERE))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

import _exp_live_stub as STUB  # noqa: E402
import _exp_wired_fixture as WF  # noqa: E402
from ui_v2 import plain  # noqa: E402
from ui_v2.exp import live, logic, page  # noqa: E402

# Phase 3 P0-①（44 第七節第三小節之七其二）：正式模式一般畫面的欄位鍵改中文名、失敗原文移到跨頁的原始訊息、
# `EXP-1`「欄位」改下拉選單。以下兩支是本檔改定位／改字面期望用的小工具（斷言本身沒有拿掉）。
_CODE_HEAD = plain.key_name(logic.CODE_COLUMN)   # 「基金代碼」


def _raw_texts(at) -> str:
    return "\n".join(e["text"] for e in at.session_state[plain.RAW_STATE]["exp"]["entries"])


def _pick_field(at, key, field):
    """`EXP-1`「欄位」下拉：以中文名找到那一個選項（底層值仍是欄位鍵）。"""
    box = at.selectbox(key=key)
    return box.select_index(box.options.index(plain.key_name(field)))

_MARK = "正式路徑碰到 fixtures"


class _FixturesThatBite:
    def __getattr__(self, name):
        raise RuntimeError(f"{_MARK}：{name}")


_SCRIPT_LIVE = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
sys.path.insert(0, {str(_HERE)!r})
import _exp_live_stub as STUB
from ui_v2.exp import page
page.render(load_live=STUB.load_live, save_live=STUB.save_setting)
"""

_SCRIPT_DEMO = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
from ui_v2.exp import page
page.render()
"""


@pytest.fixture(autouse=True)
def _clean_stub():
    STUB.reset()
    yield
    STUB.reset()


def _run(script, monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr(page, "fixtures", _FixturesThatBite())
    at = AppTest.from_string(script, default_timeout=60)
    at.run()
    return at


def _text(at) -> str:
    out = [html.unescape(e.value) for e in at.markdown] + [e.value for e in at.caption]
    out += [e.label for e in at.button] + [e.label for e in at.expander] + [e.label for e in at.checkbox]
    return "\n".join(out)


def _lamp(at) -> str:
    hits = [m.group(1) for e in at.markdown for m in re.finditer(r'class="exp-lamp-text">(.*?)</span>', e.value)]
    assert len(hits) == 1, hits
    return html.unescape(hits[0])


def _ok(at):
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_正式模式_fixtures一碰就炸也照樣渲染_缺欄照寫_沒有示意字樣(monkeypatch):
    STUB.STORE["exp_filter_rules"] = json.dumps([{"field": "fund_code", "op": "不等於", "value": "C03"}],
                                                ensure_ascii=False)
    STUB.STORE["exp_visible_columns"] = json.dumps(list(logic.COLUMN_ORDER))
    at = _ok(_run(_SCRIPT_LIVE, monkeypatch))
    text = _text(at)
    assert _MARK not in text
    assert _lamp(at) == "目前條件下有 2 檔"
    assert "⬜ 資料未備：基本資料尚未接入" in text and "⬜ 資料未備：淨值尚未接入" in text
    assert f"<th>{_CODE_HEAD}</th>" in text and ">A01</td>" in text and ">B02</td>" in text and ">C03</td>" not in text
    assert "示意" not in text and "None" not in text
    assert not at.warning  # 沒有 session state 與 widget 預設值相衝的警告
    assert not re.search(r"·\s*情境 ", text)


def test_正控_同一個替身之下示範模式一定會炸(monkeypatch):
    at = _run(_SCRIPT_DEMO, monkeypatch)
    assert at.exception and any(_MARK in e.value for e in at.exception)


def test_只吃已存值_填了不存不生效_存檔後下一次重跑才套用(monkeypatch):
    at = _ok(_run(_SCRIPT_LIVE, monkeypatch))
    assert _lamp(at) == logic.TEXT_NO_CONDITION
    at.button(key="exp1live_btn_0").click().run()            # 新增條件
    _ok(at)
    _pick_field(at, "exp1live_1_field", "fund_code")
    at.text_input(key="exp1live_1_op").input("等於")
    at.text_input(key="exp1live_1_value").input("A01").run()
    _ok(at)
    assert _lamp(at) == logic.TEXT_NO_CONDITION              # 未存：正式結果不動
    assert logic.TEXT_UNSAVED_RULES in _text(at)
    assert STUB.SAVES == []
    at.button(key="exp1live_btn_1").click().run()            # 存檔
    _ok(at)
    assert STUB.SAVES == [("exp_filter_rules", '[{"field": "fund_code", "op": "等於", "value": "A01"}]', "rules")]
    assert _lamp(at) == "目前條件下有 1 檔"                    # 重跑重新讀已存值 → 生效
    assert logic.TEXT_UNSAVED_RULES not in _text(at)
    assert live.TEXT_SAVED in _text(at)


def test_存檔失敗_條件列留在畫面上_正式結果不變(monkeypatch):
    STUB.FAIL_KEYS.add("exp_filter_rules")
    at = _ok(_run(_SCRIPT_LIVE, monkeypatch))
    at.button(key="exp1live_btn_0").click().run()
    _pick_field(at, "exp1live_1_field", "fund_code")
    at.text_input(key="exp1live_1_op").input("等於")
    at.text_input(key="exp1live_1_value").input("A01").run()
    at.button(key="exp1live_btn_1").click().run()
    _ok(at)
    text = _text(at)
    raw = "存檔寫入失敗：exp_filter_rules：exp_filter_rules 寫入失敗（測試注入）"
    # 失敗訊息（替身回的是整句中文、不帶上游英文字樣）照 `plain._looks_raw` 判定留在一般畫面，鍵名照換中文。
    assert plain.plain_text(raw, page="exp", code="EXP-1") in text
    assert "存檔寫入失敗：" in text and raw.split("：")[1] not in text.replace("寫入失敗（測試注入）", "")
    assert at.text_input(key="exp1live_1_value").value == "A01"
    assert _lamp(at) == logic.TEXT_NO_CONDITION


def test_EXP4一成一敗_畫面照實寫哪一鍵成功哪一鍵失敗(monkeypatch):
    STUB.FAIL_KEYS.add("exp_sort_column")
    at = _ok(_run(_SCRIPT_LIVE, monkeypatch))
    at.checkbox(key="exp4live_col_ccy").check().run()
    _ok(at)
    assert live.TEXT_UNSAVED_EXP4 in _text(at)
    at.button(key="exp4live_btn_0").click().run()
    _ok(at)
    text = _text(at)
    assert f"{plain.key_name('exp_visible_columns')}：已存檔" in text
    raw = "存檔寫入失敗：exp_sort_column：exp_sort_column 寫入失敗（測試注入）"
    # 失敗訊息（替身回的是整句中文、不帶上游英文字樣）照 `plain._looks_raw` 判定留在一般畫面，鍵名照換中文。
    assert plain.plain_text(raw, page="exp", code="EXP-4") in text
    assert "存檔寫入失敗：" in text and raw.split("：")[1] not in text.replace("寫入失敗（測試注入）", "")
    assert STUB.STORE == {"exp_visible_columns": '["ccy"]'}


def test_EXP5加入觀察清單_寫已存與勾起的聯集(monkeypatch):
    STUB.STORE["exp_filter_rules"] = json.dumps([{"field": "fund_code", "op": "不等於", "value": "C03"}],
                                                ensure_ascii=False)
    STUB.STORE["exp_watchlist"] = '["Z09"]'
    at = _ok(_run(_SCRIPT_LIVE, monkeypatch))
    at.checkbox(key="exp2_觀察清單_A01__live").check().run()
    _ok(at)
    at.button(key="exp5live_btn_0").click().run()
    _ok(at)
    assert STUB.STORE["exp_watchlist"] == '["A01", "Z09"]'


# ═════════════════════ 2026-10-13 稽核 L 回修：讀失敗 → 恢復 → 存檔，不得用空值蓋掉雲端 ═════════════════════

_SAVED_RULES = json.dumps([{"field": "fund_code", "op": "不等於", "value": "C03"}], ensure_ascii=False)


def _first_rule_id(at) -> str:
    ids = sorted({t.key.split("_")[1] for t in at.text_input if t.key and t.key.startswith("exp1live_")})
    assert len(ids) == 1, ids
    return ids[0]


def test_讀失敗那一輪_不建EXP4勾選框_新增條件與存檔都停用(monkeypatch):
    STUB.READ_ERROR.append("讀設定失敗（測試注入）")
    at = _ok(_run(_SCRIPT_LIVE, monkeypatch))
    keys = {c.key for c in at.checkbox}
    assert not [k for k in keys if k and k.startswith("exp4live_col_")]
    assert not [s for s in at.selectbox if s.key == "exp4live_sort"]
    assert at.button(key="exp1live_btn_0").disabled                 # 新增條件
    for key in ("exp1live_btn_1", "exp4live_btn_0", "exp5live_btn_0"):
        assert at.button(key=key).disabled, key
    assert "讀設定失敗（測試注入）" not in _text(at)                 # 原文移到跨頁的原始訊息
    assert "讀設定失敗（測試注入）" in _raw_texts(at)
    # ~~assert "⛔ 使用者設定 取數失敗" in _text(at)~~ → 2026-10-17 Phase 3 P0-②（44 第七節第三小節之七其二第 3 條；
    # 有意識的更正，不是漏刪）：同源失敗摘要只在頁首資料狀態行出現一次；那一句換成「⛔ 取數失敗：使用者設定」。
    assert "⛔ 取數失敗：使用者設定" in _text(at)
    assert "⛔ 使用者設定 取數失敗" not in _text(at)


def test_讀失敗後恢復_輸入欄改回已存值_存檔不寫空值(monkeypatch):
    STUB.STORE["exp_visible_columns"] = '["fund_name", "nav_date"]'
    STUB.STORE["exp_sort_column"] = '["nav_date"]'
    STUB.STORE["exp_filter_rules"] = _SAVED_RULES
    at = _ok(_run(_SCRIPT_LIVE, monkeypatch))                      # 第一輪：讀得到，以已存值填
    assert at.checkbox(key="exp4live_col_nav_date").value is True
    STUB.READ_ERROR.append("讀設定失敗（測試注入）")
    _ok(at.run())                                                  # 第二輪：讀失敗
    STUB.READ_ERROR.clear()
    _ok(at.run())                                                  # 第三輪：恢復
    assert at.checkbox(key="exp4live_col_fund_name").value is True
    assert at.checkbox(key="exp4live_col_nav_date").value is True
    assert at.selectbox(key="exp4live_sort").value == logic.COLUMN_LABELS["nav_date"]
    assert at.text_input(key="exp1live_" + _first_rule_id(at) + "_value").value == "C03"
    at.button(key="exp4live_btn_0").click().run()                  # 存檔：寫回的是已存值，不是空值
    _ok(at)
    at.button(key="exp1live_btn_1").click().run()
    _ok(at)
    assert ("exp_visible_columns", '["fund_name", "nav_date"]', "list") in STUB.SAVES
    assert ("exp_sort_column", '["nav_date"]', "list") in STUB.SAVES
    assert ("exp_filter_rules", _SAVED_RULES, "rules") in STUB.SAVES
    assert STUB.STORE["exp_visible_columns"] == '["fund_name", "nav_date"]'
    assert STUB.STORE["exp_filter_rules"] == _SAVED_RULES


def test_他處改了設定_重跑後輸入欄改成新的已存值(monkeypatch):
    STUB.STORE["exp_visible_columns"] = '["fund_name"]'
    at = _ok(_run(_SCRIPT_LIVE, monkeypatch))
    assert at.checkbox(key="exp4live_col_fund_name").value is True
    at.checkbox(key="exp4live_col_ccy").check().run()               # 使用者動了一格、沒存
    _ok(at)
    STUB.STORE["exp_visible_columns"] = '["nav_date"]'             # 別處（例如設定與診斷）改了
    _ok(at.run())
    assert at.checkbox(key="exp4live_col_nav_date").value is True
    assert at.checkbox(key="exp4live_col_fund_name").value is False
    assert at.checkbox(key="exp4live_col_ccy").value is False


def test_存檔成功後_同一份結果不被當成他處改了而清掉_已存檔照樣顯示(monkeypatch):
    at = _ok(_run(_SCRIPT_LIVE, monkeypatch))
    at.checkbox(key="exp4live_col_ccy").check().run()
    at.button(key="exp4live_btn_0").click().run()
    _ok(at)
    assert live.TEXT_SAVED in _text(at)
    assert at.checkbox(key="exp4live_col_ccy").value is True


# ═════════════════════ 客戶 2026-10-13 裁示：條件作用在資料未備欄位 → 無法判定 ═════════════════════


def test_條件作用在資料未備欄位_畫面照列並標無法判定_結論列灰燈不紅(monkeypatch):
    STUB.STORE["exp_filter_rules"] = json.dumps(
        [{"field": "fund_code", "op": "不等於", "value": "C03"}, {"field": "ccy", "op": "等於", "value": "USD"}],
        ensure_ascii=False)
    at = _ok(_run(_SCRIPT_LIVE, monkeypatch))
    text = _text(at)
    assert _lamp(at) == "目前條件下沒有符合的基金；另有 2 檔無法判定"
    assert "⛔" not in "".join(m.group(0) for e in at.markdown
                               for m in re.finditer(r'class="exp-lamp".*?</div>', e.value, re.S))
    assert f"<th>{_CODE_HEAD}</th><th>篩選判定</th>" in text
    assert text.count(f"⬜ 無法判定（資料未備：{plain.key_name('ccy')}）") == 2
    assert ">A01</td>" in text and ">B02</td>" in text and ">C03</td>" not in text
    assert "<th>無法判定</th>" in text                                    # EXP-7 第四欄


def test_大於小於填了非數字_存檔停用_存檔區寫明_改成數字後才可存(monkeypatch):
    """總管 2026-10-13 決定（比照 Q-07 前例）：停用存檔、寫明哪一列；不自動修正、不丟棄那一列。"""
    at = _ok(_run(_SCRIPT_LIVE, monkeypatch))
    at.button(key="exp1live_btn_0").click().run()            # 新增條件
    rule_id = _first_rule_id(at)
    _pick_field(at, f"exp1live_{rule_id}_field", "mgmt_fee_rate_pct")
    at.text_input(key=f"exp1live_{rule_id}_op").input("大於")
    at.text_input(key=f"exp1live_{rule_id}_value").input("abc").run()
    _ok(at)
    line = "第 1 列：條件數值「abc」不是數值，大於／小於只能比數值"
    assert at.button(key="exp1live_btn_1").disabled
    assert line in _text(at)
    assert at.text_input(key=f"exp1live_{rule_id}_value").value == "abc"   # 不改、不丟
    assert STUB.SAVES == []
    at.text_input(key=f"exp1live_{rule_id}_value").input("1.5").run()
    _ok(at)
    assert not at.button(key="exp1live_btn_1").disabled
    assert line not in _text(at)
    at.button(key="exp1live_btn_1").click().run()
    _ok(at)
    assert STUB.SAVES == [("exp_filter_rules",
                           '[{"field": "mgmt_fee_rate_pct", "op": "大於", "value": "1.5"}]', "rules")]


# ───────────────────────── 2026-10-14 C2 接線：基本資料、淨值、配息比 ─────────────────────────

_ALL_RULES = json.dumps([{"field": "fund_code", "op": "不等於", "value": "ZZZ"}], ensure_ascii=False)


def _wired_store():
    STUB.WIRED.append(True)
    STUB.STORE["exp_filter_rules"] = _ALL_RULES
    STUB.STORE["exp_visible_columns"] = json.dumps(list(logic.COLUMN_ORDER))


def _raw_table(at) -> str:
    hits = [e.value for e in at.markdown if 'class="exp-table"' in e.value and f"<th>{_CODE_HEAD}</th>" in e.value]
    assert len(hits) == 1, len(hits)                 # EXP-2 那一張（EXP-7 另有一張，不含代碼欄）
    return hits[0]


def test_C2接線_代碼欄第一欄_沒有新增欄位_舊淨值與無配息照裁示寫(monkeypatch):
    _wired_store()
    at = _ok(_run(_SCRIPT_LIVE, monkeypatch))
    table = _raw_table(at)
    heads = [html.unescape(h) for h in re.findall(r"<th>(.*?)</th>", table)]
    assert heads == [_CODE_HEAD] + [plain.key_name(logic.COLUMN_LABELS[c]) for c in logic.COLUMN_ORDER]   # 規則 2、10
    text = html.unescape(table)
    assert "⬜ 資料未備：最近一筆淨值 2026-10-03，已超過 10 日" in text                       # 規則 11
    assert ">2026-10-04<" in text                                                              # 10 天照用
    assert "⬜ 不適用：近 12 個月無配息" in text and "0.00%" not in text                       # 規則 13
    assert ">6.00%<" in text
    assert text.count('class="exp-src"') >= 8                                                  # 規則 10
    # 遮蔽：那一格的失敗原文移到跨頁的原始訊息（Phase 3 P0-①），遮蔽照舊在原文上做、秘密值哪裡都不出現。
    assert "‹已遮蔽›" in _raw_texts(at) and WF.SECRET not in text and WF.SECRET not in _raw_texts(at)
    assert "尚未接入" not in _text(at)


def test_C2接線_值與tooltip含腳本與引號_一律escape(monkeypatch):
    _wired_store()
    at = _ok(_run(_SCRIPT_LIVE, monkeypatch))
    table = _raw_table(at)
    assert "<script>" not in table and 'Evil"Src' not in table
    # 2026-10-14 修正輪（Q M1）：`_esc` 比照 hld —— HTML 與 Markdown 字元一律改成數字字元參照。
    assert page._esc(WF.XSS_NAME) in table and "&#60;script&#62;alert&#40;&#34;x&#34;&#41;" in table
    assert 'title="淨值來源：Evil&#34;Src&#60;b&#62;' in table
    assert re.search(r'<td style="[^"]*" title="[^"]*">', table)


def test_C2接線_錯誤原文含換行與Markdown語法_不跳出表格_不變成標題(monkeypatch):
    """Q M1：原文含 `\n\n`、`## `、`|`、`*` —— 交給 `st.markdown` 的表格字串裡一個都不得以語法形式出現。"""
    _wired_store()
    at = _ok(_run(_SCRIPT_LIVE, monkeypatch))
    table = _raw_table(at)
    assert "\n" not in table                                               # 換行折掉（Markdown 不會跳出 HTML 區塊）
    for raw in ("## ", "|", "*粗體*", "_斜體_"):
        assert raw not in table, raw
    # Phase 3 P0-①：那一格的失敗原文移到跨頁的原始訊息（一般畫面只寫狀態句）；內容還在、只是換了地方。
    assert "## 注入標題\n| a | b |" in _raw_texts(at)
    text = html.unescape(table)
    # ~~assert "⛔ 資料 取數失敗" in text~~ → 2026-10-17 Phase 3 P0-②（有意識的更正，不是漏刪）：表格列裡的失敗只留
    # 狀態族「⛔ 取數失敗」（資料類摘要只在頁首資料狀態行一次）；那一格照舊是失敗、照舊看得到 ⛔。
    assert "⛔ 取數失敗" in text and "⛔ 資料 取數失敗" not in text


def _wired_app(tmp_path) -> pathlib.Path:
    app = tmp_path / "exp_wired_app.py"
    app.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(_ROOT)!r})\n"
        f"sys.path.insert(0, {str(_HERE)!r})\n"
        "import json\n"
        "import _exp_live_stub as STUB\n"
        "from ui_v2.exp import logic, page\n"
        "STUB.reset()\n"
        "STUB.WIRED.append(True)\n"
        f"STUB.STORE['exp_filter_rules'] = {_ALL_RULES!r}\n"
        "STUB.STORE['exp_visible_columns'] = json.dumps(list(logic.COLUMN_ORDER))\n"
        "page.render(load_live=STUB.load_live, save_live=STUB.save_setting)\n",
        encoding="utf-8",
    )
    return app


_EXP2_DOM_JS = """() => {
  const tables = [...document.querySelectorAll('table.exp-table')]
    .filter(t => t.querySelector('th') && t.querySelector('th').textContent === CODE_HEAD);
  const t = tables[0];
  const rows = t ? [...t.querySelectorAll('tbody tr')] : [];
  return {
    tables: tables.length,
    heads: t ? [...t.querySelectorAll('thead th')].map(e => e.textContent) : [],
    first: rows.map(r => r.cells[0].textContent),
    widths: rows.map(r => r.cells.length),
    titles: t ? [...t.querySelectorAll('td[title]')].map(e => e.getAttribute('title')) : [],
    scripts: t ? t.querySelectorAll('script').length : -1,
    bold: t ? t.querySelectorAll('td b').length : -1,
    src: t ? t.querySelectorAll('.exp-src').length : 0,
    names: rows.map(r => r.cells[1].textContent),
    injected_headings: [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')]
      .filter(h => h.textContent.includes('注入標題')).length,
    tables_in_cells: t ? t.querySelectorAll('td table').length : -1,
    scroll_width: t ? t.closest('.exp-scroll').scrollWidth : -1,
    client_width: t ? t.closest('.exp-scroll').clientWidth : -1,
    src_max_width: t ? Math.max(...[...t.querySelectorAll('.exp-src')].map(e => e.getBoundingClientRect().width)) : -1,
    src_limit_px: t && t.querySelector('.exp-src')
      ? parseFloat(getComputedStyle(t.querySelector('.exp-src')).maxWidth) : -1,
  };
}"""


def test_C2接線_瀏覽器_代碼欄第一欄_title已escape_來源標示存在_沒有新增欄位(tmp_path):
    """Chromium 實測（客戶規則 2、10 與 escape）：DOM 查詢，不看截圖。"""
    import _ui_v2_chromium

    api = _ui_v2_chromium.import_sync_api()
    with api.sync_playwright() as p:
        browser = _ui_v2_chromium.launch(p)
        try:
            with _ui_v2_chromium.streamlit_server(_wired_app(tmp_path)) as base:
                tab = browser.new_page(viewport={"width": 1600, "height": 2200})
                tab.goto(base + "/", wait_until="networkidle")
                tab.wait_for_selector("table.exp-table", timeout=60000)
                tab.wait_for_timeout(1500)
                dom = tab.evaluate(_EXP2_DOM_JS.replace("CODE_HEAD", repr(_CODE_HEAD)))
                assert dom["tables"] == 1, dom                                   # EXP-2 那一張（帶代碼欄）
                assert dom["heads"] == [_CODE_HEAD] + [plain.key_name(logic.COLUMN_LABELS[c]) for c in logic.COLUMN_ORDER]
                assert dom["first"] == sorted(WF.CODES)                          # 代碼欄是第一欄
                assert dom["widths"] == [len(dom["heads"])] * len(WF.CODES)     # 每列格數＝表頭數，沒有新增欄
                assert any(t.startswith('淨值來源：Evil"Src<b>') for t in dom["titles"]), dom["titles"]
                assert dom["scripts"] == 0 and dom["bold"] == 0                  # 字串沒有變成標籤
                assert dom["src"] >= 8
                assert any(n.startswith(WF.XSS_NAME) for n in dom["names"])
                # Q M1：錯誤原文裡的 `## ` 不得變成標題、`|` 不得變成另一張表。
                assert dom["injected_headings"] == 0 and dom["tables_in_cells"] == 0
                # Q O1：1600 寬桌機，候選表不需要橫捲（`.exp-src` 限寬＋省略號，全文在 tooltip）。
                assert dom["scroll_width"] <= dom["client_width"] + 1, (dom["scroll_width"], dom["client_width"])
                assert dom["src_max_width"] <= dom["src_limit_px"] + 1
                tab.close()
        finally:
            browser.close()
