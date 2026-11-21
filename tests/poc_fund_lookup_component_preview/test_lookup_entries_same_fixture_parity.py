# -*- coding: utf-8 -*-
"""兩個單碼入口（同一組輸入）對照實測：A＝`poc/fund_lookup_component_preview`（`ui_v3.adapters.fund_lookup.lookup_fund`＋注入 loader），
B＝`poc/fund_search_fixture_preview` 上區（`fund_search_logic.classify_lookup`＋`fund_search_renderer.lookup_card_html`）。

只量測與固定「現況」，不判定誰對、不改任何 poc／adapter。量測值固定在
`docs/evidence/ui_b3_lookup_health_controls_2026_11_21/measure.json`（本檔 `__main__` 可重產；測試比對兩者，漂移即紅燈）。

量測方法（全部離線、deterministic）：
- 「是否觸發 loader」：A 用 `FakeLoader.calls` 計次（spy）；B 沒有 loader 注入縫，只有一個 fixtures 字典，
  故以「繼承 dict 的 spy」計 `get` 次數（＝是否去查對照表）。兩者計次語意不同，表內分欄記錄，不當成同一件事。
- 「來源失敗」：A 的原生失敗碼是 `FAKE-FAIL1`；B 的原生失敗碼是 `FAKE-ERR1`。為了用**同一個輸入**比較，
  B 一欄額外注入 `FAKE-FAIL1 -> failed`（只在測試端注入 fixtures，不改 poc）；兩個原生碼也各量一次（`native_*` 列）。
- 「五欄」：輸入代碼、基金名稱、配息方式、成立日期、經理費率；表內只記畫面上**出現**的 data-row 與其可見文字。

對照結論（現況，量測值見 JSON）：
| 輸入 | A（lookup）| B（search 上區） |
| 空白／全空格 | BLOCKED/blank，loader 0 次，不回顯 | unrecognized（無法辨識格式），fixtures 0 次，**有輸入代碼列、值為缺值字樣** |
| ISIN 形 | BLOCKED/isin_shape，loader 0 次，不回顯 | isin（未啟用說明），fixtures 0 次，不回顯，沒有五欄 |
| 合法未知 | loader 1 次 → PAGE_UNMATCHED/no_page，回顯輸入 | no_fixture，fixtures 1 次，回顯輸入 |
| FAKE 成功 | loader 1 次 → RESULT，五欄齊 | found，fixtures 1 次，五欄齊（成立日期／費率為缺值字樣） |
| 來源失敗 | SOURCE_FAILED（取數失敗字樣），只有輸入代碼列，無其餘四欄 | failed（取數失敗字樣），只有輸入代碼列，無其餘四欄 |
共同點：失敗狀態兩邊都不畫其餘四欄（沒有把 Failed 鋪滿五欄）；差異：空白輸入 A 不回顯、B 回顯缺值字樣列；
成功時 A 的經理費率為「此欄尚無可顯示的值」、B 為「◇ 資料未備」（缺值字樣不同源）。
"""
from __future__ import annotations

import html as _html
import json
import pathlib
import re
import sys

import pytest

import fund_lookup_cmp_support as S  # noqa: F401  # 設定 sys.path（lookup poc、tests/ui_v3、ROOT）

ROOT = pathlib.Path(__file__).resolve().parents[2]
_SEARCH_POC = str(ROOT / "poc" / "fund_search_fixture_preview")
if _SEARCH_POC not in sys.path:
    sys.path.insert(0, _SEARCH_POC)

import fund_lookup_fake_inputs as LF  # noqa: E402
import fund_lookup_renderer as LR  # noqa: E402
import fund_search_fake_inputs as SF  # noqa: E402
import fund_search_logic as SL  # noqa: E402
import fund_search_renderer as SR  # noqa: E402
from ui_v3.adapters import fund_lookup as adapter  # noqa: E402
from ui_v3.adapters.fund_lookup import lookup_fund  # noqa: E402

EVIDENCE = ROOT / "docs" / "evidence" / "ui_b3_lookup_health_controls_2026_11_21" / "measure.json"
FIVE_ROWS = ("input-code", "name", "dividend-mode", "inception", "mgmt-fee")
FIVE_LABELS = {"input-code": "輸入代碼", "name": "基金名稱", "dividend-mode": "配息方式", "inception": "成立日期", "mgmt-fee": "經理費率"}

#: (case id, 輸入, 說明)。同一個輸入餵給兩個入口。
SHARED_CASES = (
    ("blank_empty", "", "空字串"),
    ("blank_spaces", "   ", "全空格"),
    ("isin_shape", "LU0000000001", "ISIN 形（人造）"),
    ("legit_unknown", "ABC123", "合法格式、兩邊都沒有的代碼"),
    ("fake_success", "FAKE-OK01", "FAKE 成功"),
    ("source_failed", "FAKE-FAIL1", "來源失敗（B 端以測試注入 fixtures 對齊）"),
    ("padded_lower", " fake-ok01 ", "前後空格＋小寫的 FAKE 成功"),
)
#: 各自原生的碼（不能共用：兩個 fixture 表的失敗／部分缺值碼不同）。
NATIVE_CASES = (
    ("native_failed_A", "FAKE-FAIL1", "A", "A 原生失敗碼"),
    ("native_failed_B", "FAKE-ERR1", "B", "B 原生失敗碼"),
    ("native_partial_missing_A", "FAKE-OK03", "A", "A 原生：配息方式與成立日期缺值"),
    ("native_partial_missing_B", "FAKE-LOW1", "B", "B 原生：資料不足（四欄缺值）"),
)


class SpyFixtures(dict):
    """B 沒有 loader 注入縫；以 dict 子類計 `get`（＝查對照表）次數。"""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.gets = 0

    def get(self, key, default=None):
        self.gets += 1
        return super().get(key, default)


def _plain(markup: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", markup))).strip()


def _five_rows(markup: str) -> dict:
    """畫面上出現的五欄 data-row → 值文字（已去掉欄位標籤）。"""
    rows = {}
    for m in re.finditer(r'data-row="(input-code|name|dividend-mode|inception|mgmt-fee)"[^>]*>(.*?)</div>', markup, re.S):
        text = _plain(m.group(2))
        label = FIVE_LABELS[m.group(1)]
        rows[m.group(1)] = text[len(label):].strip() if text.startswith(label) else text
    return rows


def _row_status(markup: str) -> dict:
    return dict(re.findall(r'data-row="(input-code|name|dividend-mode|inception|mgmt-fee)" data-field-status="([a-z]+)"', markup))


def _flags(visible: str) -> dict:
    return {"failed_marker": "取數失敗" in visible, "undetermined_marker": "無法判定" in visible,
            "missing_marker_count": visible.count("資料未備") + visible.count("此欄尚無可顯示的值")}


def measure_a(raw: str) -> dict:
    loader = LF.make_loader()
    view = lookup_fund(loader, raw)
    markup = LR.lookup_card_html(view, fake=True)
    rows = _five_rows(markup)
    visible = _plain(markup)
    return {"state": view.state.name, "reason": view.reason_code, "loader_or_table_calls": len(loader.calls),
            "echo": rows.get("input-code"), "rows_shown": [r for r in FIVE_ROWS if r in rows],
            "row_texts": rows, "field_status": _row_status(markup), **_flags(visible), "visible_text": visible}


def measure_b(raw: str, *, inject_failed: bool = False) -> dict:
    fixtures = SpyFixtures(SF.LOOKUP_FIXTURES)
    if inject_failed:
        fixtures["FAKE-FAIL1"] = SL.OUT_FAILED
    result = SL.classify_lookup(raw, fixtures)
    if result.outcome == SL.OUT_ISIN:
        markup = SR.isin_result_html()
    else:
        markup = SR.lookup_card_html(result, SF.FAKE_FOUND_NAME, SF.LOOKUP_DIVIDEND_MODE.get(raw.strip().upper()))
    rows = _five_rows(markup)
    visible = _plain(markup)
    return {"state": result.outcome, "reason": None, "loader_or_table_calls": fixtures.gets,
            "echo": rows.get("input-code"), "rows_shown": [r for r in FIVE_ROWS if r in rows],
            "row_texts": rows, "field_status": {}, **_flags(visible), "visible_text": visible}


def measure() -> dict:
    table = {"_note": "A=lookup_fund(注入 FakeLoader)；B=classify_lookup(SpyFixtures)；loader_or_table_calls：A=loader 呼叫次數、B=fixtures.get 次數",
             "shared_inputs": {}, "native": {}}
    for cid, raw, _desc in SHARED_CASES:
        table["shared_inputs"][cid] = {"input": raw, "A": measure_a(raw), "B": measure_b(raw, inject_failed=True)}
    for cid, raw, side, _desc in NATIVE_CASES:
        table["native"][cid] = {"input": raw, "side": side, side: measure_a(raw) if side == "A" else measure_b(raw)}
    return table


# ───────────────────────── 測試 ─────────────────────────

def test_committed_measure_json_equals_current_measurement():
    assert json.loads(EVIDENCE.read_text(encoding="utf-8")) == measure()


@pytest.mark.parametrize("cid", ["blank_empty", "blank_spaces", "isin_shape"])
def test_intercepted_inputs_never_reach_loader_or_table_on_either_entry(cid):
    row = measure()["shared_inputs"][cid]
    assert row["A"]["loader_or_table_calls"] == 0 and row["B"]["loader_or_table_calls"] == 0


@pytest.mark.parametrize("cid", ["legit_unknown", "fake_success", "source_failed", "padded_lower"])
def test_passed_inputs_trigger_exactly_one_lookup_on_either_entry(cid):
    row = measure()["shared_inputs"][cid]
    assert row["A"]["loader_or_table_calls"] == 1 and row["B"]["loader_or_table_calls"] == 1


def test_states_per_shared_input_are_pinned():
    t = measure()["shared_inputs"]
    assert {k: (v["A"]["state"], v["A"]["reason"]) for k, v in t.items()} == {
        "blank_empty": ("BLOCKED", "blank"), "blank_spaces": ("BLOCKED", "blank"), "isin_shape": ("BLOCKED", "isin_shape"),
        "legit_unknown": ("PAGE_UNMATCHED", "no_page"), "fake_success": ("RESULT", None),
        "source_failed": ("SOURCE_FAILED", "source_failed"), "padded_lower": ("RESULT", None)}
    assert {k: v["B"]["state"] for k, v in t.items()} == {
        "blank_empty": "unrecognized", "blank_spaces": "unrecognized", "isin_shape": "isin",
        "legit_unknown": "no_fixture", "fake_success": "found", "source_failed": "failed", "padded_lower": "found"}


def test_echo_policy_difference_on_blank_and_isin_is_pinned():
    t = measure()["shared_inputs"]
    for cid in ("blank_empty", "blank_spaces", "isin_shape"):
        assert t[cid]["A"]["echo"] is None and "input-code" not in t[cid]["A"]["rows_shown"]   # A：被攔截者結構上不回顯
    assert t["isin_shape"]["B"]["echo"] is None and t["isin_shape"]["B"]["rows_shown"] == []   # B：ISIN 形只出說明，不回顯
    for cid in ("blank_empty", "blank_spaces"):                                                # B：空白仍畫輸入代碼列（值為缺值字樣）
        assert t[cid]["B"]["rows_shown"] == ["input-code"] and t[cid]["B"]["echo"] == "⬜ 資料未備"
    assert t["legit_unknown"]["A"]["echo"] == t["legit_unknown"]["B"]["echo"] == "ABC123"


def test_failed_states_show_only_the_input_row_on_both_entries_never_five_failed_cells():
    t = measure()["shared_inputs"]["source_failed"]
    for side in ("A", "B"):
        assert t[side]["failed_marker"] is True
        assert t[side]["rows_shown"] == ["input-code"] and t[side]["missing_marker_count"] == 0
    n = measure()["native"]
    assert n["native_failed_A"]["A"]["state"] == "SOURCE_FAILED" and n["native_failed_B"]["B"]["state"] == "failed"
    assert n["native_failed_A"]["A"]["rows_shown"] == n["native_failed_B"]["B"]["rows_shown"] == ["input-code"]


def test_missing_cells_show_in_five_rows_only_when_result_or_found_and_wording_differs_by_entry():
    t = measure()["shared_inputs"]["fake_success"]
    assert t["A"]["rows_shown"] == t["B"]["rows_shown"] == list(FIVE_ROWS)
    assert t["A"]["row_texts"]["mgmt-fee"] == "此欄尚無可顯示的值" and t["B"]["row_texts"]["mgmt-fee"] == "⬜ 資料未備"
    assert t["A"]["field_status"]["mgmt-fee"] == "missing" and t["A"]["field_status"]["name"] == "value"
    n = measure()["native"]
    a = n["native_partial_missing_A"]["A"]
    assert a["field_status"]["dividend-mode"] == a["field_status"]["inception"] == "missing" and a["field_status"]["name"] == "value"
    b = n["native_partial_missing_B"]["B"]
    assert b["state"] == "insufficient" and b["rows_shown"] == list(FIVE_ROWS)
    assert all(b["row_texts"][r] == "⬜ 資料未備" for r in ("name", "dividend-mode", "inception", "mgmt-fee"))


def test_padded_lowercase_success_is_echoed_differently():
    t = measure()["shared_inputs"]["padded_lower"]
    assert t["A"]["echo"] == "fake-ok01"          # A：只去 ASCII 空格、不轉大寫
    assert t["B"]["echo"] == "fake-ok01"          # B：視覺文字經 _plain 正規化空白；原值含前後空格由 renderer escape 保留
    assert SR.lookup_card_html(SL.classify_lookup(" fake-ok01 ", SF.LOOKUP_FIXTURES), SF.FAKE_FOUND_NAME).count(" fake-ok01 ") == 1


def test_no_row_in_either_entry_renders_zero_for_a_missing_cell():
    t = measure()
    cells = [v[s]["row_texts"] for v in t["shared_inputs"].values() for s in ("A", "B")]
    for texts in cells:
        for name, text in texts.items():
            if name != "input-code":
                assert text not in ("0", "0.0", "0%", "無", "不配息")


# 變異負控（全在記憶體內現編）：拿掉攔截／ISIN 判斷後，量測必須與固定值不同，證明上面的固定值真的守得到。
def test_mutation_removing_entry_a_interception_changes_the_measurement(monkeypatch):
    baseline = measure()
    monkeypatch.setattr(adapter, "screen_input", lambda raw: None)
    try:
        got = measure_a("   ")
    except Exception as exc:                      # 攔截被拿掉後，空白輸入可能直接觸發契約錯誤；那同樣證明守得到
        got = {"raised": type(exc).__name__}
    assert got != baseline["shared_inputs"]["blank_spaces"]["A"]


def test_mutation_removing_entry_b_isin_shape_check_changes_the_measurement(monkeypatch):
    baseline = measure()["shared_inputs"]["isin_shape"]["B"]
    monkeypatch.setattr(SL, "_ISIN_SHAPE", re.compile(r"(?!x)x"))
    assert measure_b("LU0000000001")["state"] != baseline["state"]


if __name__ == "__main__":      # 重產 measure.json：python tests/poc_fund_lookup_component_preview/test_lookup_entries_same_fixture_parity.py
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(measure(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("wrote", EVIDENCE)
