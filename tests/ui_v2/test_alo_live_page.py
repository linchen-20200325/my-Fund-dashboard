# -*- coding: utf-8 -*-
"""資產配置正式模式的執行期測試（slow lane；需要 streamlit）。

依據 docs/v2/49_data_integration_plan.md §4.7 第 4 點：
把 `page` 模組上的 `fixtures` 屬性換成「一存取就拋錯」的替身，再以 stub 載入函式呼叫
`page.render(load_live=...)`。只要正式模式的任何一條路徑讀了 fixtures，這裡就紅。
這一條補的是 import 掃描抓不到的東西：`page.py` 本來就 import `fixtures`（示範模式要用），
「有沒有 import」證明不了「正式模式有沒有呼叫」。

另附正控：同一個替身之下**不傳**載入函式（示範模式）必須炸 —— 證明替身真的會咬人。
stub 只回一份最小的合法資料，不呼叫 `source`、不打任何網路。
"""

import json
import pathlib
import sys

import pytest

# 整檔標 slow：畫面測試不進 fast lane（守衛：tests/ui_v2/test_ui_v2_lane_guards.py）。
pytestmark = pytest.mark.slow

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

from ui_v2.alo import live, logic, page  # noqa: E402

_MARK = "正式路徑碰到 fixtures"
_CORE, _SAT = "核心", "衛星"


class _FixturesThatBite:
    """任何屬性存取都拋錯的 fixtures 替身。"""

    def __getattr__(self, name):
        raise RuntimeError(f"{_MARK}：{name}")


_DATASET = {
    "holding": [{
        "holding_id": "P001|AAAA|1", "policy_id": "P001", "fund_code": "AAAA",
        "fund_name": "某檔基金", "ccy": "TWD", "units_shares": 1000.0,
        "cost_orig_ccy": 700000.0, "cost_twd": 700000, "opened_on": "2021-04-01",
        "bucket": _CORE, "last_synced_at": "2026-09-23T04:00:00Z",
    }, {
        "holding_id": "P001|BBBB|1", "policy_id": "P001", "fund_code": "BBBB",
        "fund_name": "另一檔基金", "ccy": "TWD", "units_shares": 2000.0,
        "cost_orig_ccy": 300000.0, "cost_twd": 300000, "opened_on": "2022-06-10",
        "bucket": _SAT, "last_synced_at": "2026-09-23T04:00:00Z",
    }],
    "nav": [],
    "policy": [{
        "policy_id": "P001", "policy_name": "某張保單", "issuer": "某發行單位", "ccy": "TWD",
        "premium_paid_twd": 1000000, "fee_rate_pct": None, "opened_on": "2021-03-15",
        "status": "active",
    }],
    "market_indicator": [],
    "user_setting": [
        {"setting_key": "alo_target_weights", "value_kind": "list",
         "setting_value": [{"bucket": _CORE, "weight_ratio": 0.6},
                           {"bucket": _SAT, "weight_ratio": 0.4}],
         "updated_at": "2026-09-20T06:00:00Z"},
        {"setting_key": "alo_tolerance_pp", "value_kind": "float", "setting_value": 4.0,
         "updated_at": "2026-09-20T06:00:00Z"},
        {"setting_key": "alo_basis", "value_kind": "list", "setting_value": "成本",
         "updated_at": "2026-09-20T06:00:00Z"},
        {"setting_key": "alo_bucket_names", "value_kind": "list", "setting_value": [_CORE, _SAT],
         "updated_at": "2026-09-20T06:00:00Z"},
        {"setting_key": "alo_scenario_input", "value_kind": "list", "setting_value": None,
         "updated_at": None},
    ],
    "errors": {},
    "save_errors": {},
}

_SCRIPT_LIVE = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
from ui_v2.alo import page

def _stub_loader():
    return {{"dataset": {_DATASET!r}, "notes": {{}}}}

page.render(load_live=_stub_loader)
"""

_SCRIPT_DEMO = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
from ui_v2.alo import page
page.render()
"""


def _run(script, monkeypatch):
    from streamlit.testing.v1 import AppTest

    # AppTest 在同一個行程裡跑腳本，腳本 import 到的就是這一個 page 模組物件。
    monkeypatch.setattr(page, "fixtures", _FixturesThatBite())
    at = AppTest.from_string(script, default_timeout=120)
    at.run()
    return at


def _rendered(at):
    """⚠️ **radio 一定要收**：正式模式畫面上就有一枚（`live_alo_basis`），而
    `test_正式模式頁首只留提問句_零示意字樣零情境名` 的三道檢查全部建立在本函式上 ——
    漏收 radio，三道一起失效（紅隊 2026-09-28 突變 M-V2：只汙染正式模式的 radio 標籤，
    962 條測試全綠）。收標籤也收選項字面：`format_func` 之後的選項字串同樣會上畫面。"""
    out = [e.value for e in at.markdown] + [e.value for e in at.caption]
    out += [e.label for e in at.button] + [e.label for e in at.expander]
    out += [b.help for b in at.button if b.help]
    out += [e.label for e in at.text_input]
    for element in at.radio:
        out.append(element.label)
        out.extend(str(option) for option in element.options)
        if element.value is not None:
            out.append(str(element.value))
        if getattr(element, "help", None):
            out.append(element.help)
    return out


def test_正式模式_fixtures一碰就炸的情況下照樣渲染完成(monkeypatch):
    at = _run(_SCRIPT_LIVE, monkeypatch)
    assert not at.exception, [e.value for e in at.exception]
    text = "\n".join(_rendered(at))
    assert _MARK not in text
    assert "70.0%" in text and "30.0%" in text        # stub 的成本比重真的上了畫面


def test_正式模式頁首只留提問句_零示意字樣零情境名(monkeypatch):
    at = _run(_SCRIPT_LIVE, monkeypatch)
    sub = [e.value for e in at.markdown if e.value.startswith('<div class="alo-sub">')]
    assert sub == [f'<div class="alo-sub">{logic.PAGE_ANSWERS}</div>']
    text = "\n".join(_rendered(at))
    assert logic.HINT_NOTE not in text and logic.PAGE_HINT_NOTE not in text
    assert "示意" not in text
    # ⚠️ 不能只掃「情境」兩個字：ALO-3 的塊名逐字就叫「情境試算卡」（`44` 3.4），掃了必誤報。
    # 要擋的是示範模式那一段標籤，所以逐字比對 fixtures 的那一份。
    from ui_v2.alo import fixtures as _demo          # 只有測試讀它；page 上的 fixtures 是會咬人的替身
    for label in _demo.SCENARIO_LABELS.values():
        assert label not in text, label
    assert "\u3000·\u3000情境 " not in text


def test_存檔停用並寫出原因_匯出與導覽照舊(monkeypatch):
    at = _run(_SCRIPT_LIVE, monkeypatch)
    saves = [b for b in at.button if b.label == logic.TEXT_SAVE]
    assert len(saves) == 3                                    # ALO-1／ALO-3／ALO-4 各一枚
    assert all(b.disabled and b.help == live.SAVE_DISABLED_REASON for b in saves)
    goto = [b for b in at.button if b.label == logic.TEXT_GOTO_SHEETS]
    assert len(goto) == 1 and not goto[0].disabled            # 導覽鈕照掛、不停用（草稿 §F 第 16 題）
    add = [b for b in at.button if b.label == logic.TEXT_ADD_SCENARIO]
    assert len(add) == 1 and not add[0].disabled


def test_市值基準下每一檔都資料未備_不偽造不隱藏(monkeypatch):
    """`nav` 是 `settings_store.PENDING_TABLES` 的一員 ⇒ 市值基準沒有基準值。
    照 `CLAUDE.md` §1 顯示 `⬜ 資料未備`，不填 0、不拿成本頂替、不把選項灰掉。"""
    import copy as _copy

    dataset = _copy.deepcopy(_DATASET)
    for row in dataset["user_setting"]:
        if row["setting_key"] == "alo_basis":
            row["setting_value"] = logic.BASIS_MV
    script = _SCRIPT_LIVE.replace(repr(_DATASET), repr(dataset))
    at = _run(script, monkeypatch)
    assert not at.exception, [e.value for e in at.exception]
    text = "\n".join(_rendered(at))
    assert logic.TEXT_NOT_READY in text or "資料未備" in text
    # 比重基準仍是二選一，兩個選項都還在、都選得動（不准灰掉或移除）。
    radios = [r for r in at.radio if r.key == "live_alo_basis"]
    assert len(radios) == 1
    # AppTest 的 `options` 回的是 `format_func` 之後的標籤（`logic.BASIS_LABELS`），不是存值。
    assert list(radios[0].options) == [logic.BASIS_LABELS[logic.BASIS_COST],
                                       logic.BASIS_LABELS[logic.BASIS_MV]]
    assert not radios[0].disabled


def test_holding與policy一起取數失敗時照樣畫得完(monkeypatch):
    import copy as _copy

    dataset = _copy.deepcopy(_DATASET)
    dataset["errors"] = live.tables_failed_together("HTTP 503 upstream unavailable")
    dataset["holding"], dataset["policy"] = [], []
    script = _SCRIPT_LIVE.replace(repr(_DATASET), repr(dataset))
    at = _run(script, monkeypatch)
    assert not at.exception, [e.value for e in at.exception]
    text = "\n".join(_rendered(at))
    assert text.count("HTTP 503 upstream unavailable") >= 2   # 兩張表各自的失敗框
    assert logic.HINT_NOTE not in text


def test_正控_同一個替身之下示範模式一定會炸(monkeypatch):
    at = _run(_SCRIPT_DEMO, monkeypatch)
    assert at.exception, "替身沒有咬人 ⇒ 上面幾條是空的"
    assert any(_MARK in e.value for e in at.exception)


def test_不傳載入函式時_render的預設值就是None():
    import inspect

    param = inspect.signature(page.render).parameters["load_live"]
    assert param.default is None
    assert param.kind is inspect.Parameter.KEYWORD_ONLY


# ═══════════════════════ 存檔接上寫入（ALO-1／ALO-4，客戶 2026-10-09 裁示）═══════════════════════
#
# 寫入函式以替身注入：腳本經 `sys.modules` 裡的探針模組呼叫它，測試端讀它記下的呼叫。
# 不呼叫 `source`、不打任何網路。

_PROBE = "_alo_live_save_probe"
_FAIL_MSG = "HTTP 503 upstream unavailable（已遮蔽）"

# 試算表上的原字串（`source.load_live` 的 `notes["setting_raw"]`）：沒動過的欄位寫回它。
_RAW = {
    "alo_target_weights": f'[{{"bucket": "{_CORE}", "weight_ratio": 0.6}}, {{"bucket": "{_SAT}", "weight_ratio": 0.4}}]',
    "alo_tolerance_pp": "4",
    "alo_basis": "成本",
    "alo_bucket_names": f'["{_CORE}", "{_SAT}"]',
    "alo_scenario_input": None,
}


def _save_script(dataset=None, raw=None):
    dataset = _DATASET if dataset is None else dataset
    notes = {"setting_raw": _RAW if raw is None else raw}
    return f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
from ui_v2.alo import page
import {_PROBE} as probe

def _stub_loader():
    return {{"dataset": {dataset!r}, "notes": {notes!r}}}

page.render(load_live=_stub_loader, save_live=probe.save)
"""


_SCRIPT_SAVE = _save_script()


@pytest.fixture
def probe(monkeypatch):
    import types

    module = types.ModuleType(_PROBE)
    module.calls = []
    module.failing = set()

    def save(key, value, kind):
        module.calls.append((key, value, kind))
        if key in module.failing:
            return {"status": "failed", "key": key, "message": _FAIL_MSG}
        return {"status": "saved", "key": key, "row": {}}

    module.save = save
    monkeypatch.setitem(sys.modules, _PROBE, module)
    return module


def _markdown_values(at):
    return [e.value for e in at.markdown]


def _fail_line_index(at):
    error = f'<div class="alo-errline" role="alert">{logic.fetch_failed_text(_FAIL_MSG)}</div>'
    values = _markdown_values(at)
    assert values.count(error) == 1, values
    return values.index(error)


def test_ALO1存檔_一鍵成功一鍵失敗_失敗鍵原位出現取數失敗原文_輸入不清_再按兩鍵都再寫(monkeypatch, probe):
    probe.failing = {"alo_tolerance_pp"}
    at = _run(_SCRIPT_SAVE, monkeypatch)
    assert not at.exception, [e.value for e in at.exception]
    save = at.button(key="live_alo1_btn_0")
    assert not save.disabled                                   # 正式模式拿到寫入函式 ⇒ 可按
    at.text_input(key="live_alo_target_0_weight").set_value("0.65")
    at.text_input(key="live_alo_tolerance_pp").set_value("5")
    save.click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert probe.calls == [
        ("alo_target_weights",
         f'[{{"bucket": "{_CORE}", "weight_ratio": 0.65}}, {{"bucket": "{_SAT}", "weight_ratio": 0.4}}]', "list"),
        ("alo_tolerance_pp", "5", "float"),
    ]
    # 失敗的那一鍵：在容許帶那一段之後（緊接「容許帶：…」那一行）；卡片層不印第二次。
    values = _markdown_values(at)
    index = _fail_line_index(at)
    assert values[index - 1].startswith('<div class="alo-line">容許帶：'), values[index - 1]
    assert not any(logic.TEXT_SAVE_FAILED in v for v in values)
    # 當下內容留在畫面上不清掉（`44` ALO-1 空狀態）。
    assert at.text_input(key="live_alo_target_0_weight").value == "0.65"
    assert at.text_input(key="live_alo_tolerance_pp").value == "5"
    # 失敗的鍵維持可重新儲存：再按一次，照樣兩鍵都寫（一枚按鈕寫兩鍵，不拆）。
    assert not at.button(key="live_alo1_btn_0").disabled
    at.button(key="live_alo1_btn_0").click().run()
    assert [c[0] for c in probe.calls] == ["alo_target_weights", "alo_tolerance_pp"] * 2
    # 這一次都成功 ⇒ 逐鍵那一行消失。
    probe.failing = set()
    at.button(key="live_alo1_btn_0").click().run()
    assert not any("取數失敗" in v for v in _markdown_values(at))


def test_ALO1存檔_目標列失敗_印在目標列那一段之後_容許帶之前(monkeypatch, probe):
    probe.failing = {"alo_target_weights"}
    at = _run(_SCRIPT_SAVE, monkeypatch)
    at.button(key="live_alo1_btn_0").click().run()
    assert not at.exception, [e.value for e in at.exception]
    values = _markdown_values(at)
    index = _fail_line_index(at)
    tolerance = [i for i, v in enumerate(values) if v.startswith('<div class="alo-line">容許帶：')]
    assert tolerance and index < tolerance[0]


def test_ALO4存檔_類別名稱失敗_基準照寫_失敗鍵原位(monkeypatch, probe):
    probe.failing = {"alo_bucket_names"}
    at = _run(_SCRIPT_SAVE, monkeypatch)
    at.radio(key="live_alo_basis").set_value(logic.BASIS_MV)
    at.button(key="live_alo4_btn_1").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert probe.calls == [
        ("alo_basis", logic.BASIS_MV, "list"),
        ("alo_bucket_names", f'["{_CORE}", "{_SAT}"]', "list"),
    ]
    values = _markdown_values(at)
    index = _fail_line_index(at)
    basis = [i for i, v in enumerate(values) if v.startswith('<div class="alo-line">目前基準：')]
    assert basis and index > basis[0]
    assert not any(logic.TEXT_SAVE_FAILED in v for v in values)
    assert at.radio(key="live_alo_basis").value == logic.BASIS_MV          # 當下選的值不清掉


def test_有寫入函式時_ALO3存檔照舊停用_其餘兩枚可按(monkeypatch, probe):
    at = _run(_SCRIPT_SAVE, monkeypatch)
    assert not at.button(key="live_alo1_btn_0").disabled
    assert not at.button(key="live_alo4_btn_1").disabled
    alo3 = [b for b in at.button if b.label == logic.TEXT_SAVE and b.key.startswith("live_alo3")]
    assert len(alo3) == 1 and alo3[0].disabled and alo3[0].help == live.SAVE_DISABLED_REASON
    assert probe.calls == []                                   # 沒按就沒寫


def test_只傳save_live不傳load_live_當場炸():
    with pytest.raises(ValueError, match="save_live"):
        page.render(save_live=lambda *a: None)



def test_設定讀取失敗時按存檔_卡上出現存檔寫入失敗行_寫入0次(monkeypatch, probe):
    """2026-10-09 稽核回修：讀失敗時不寫（寫了就是拿空白蓋掉讀不到的真值），但不能按了沒反應 ——
    兩鍵都記為存檔失敗、走卡片層既有「存檔寫入失敗：<讀取失敗原文>」。按鈕不停用。"""
    import copy as _copy

    message = "HTTP 429 quota exceeded（已遮蔽）"
    dataset = _copy.deepcopy(_DATASET)
    dataset["errors"] = {"user_setting": message}
    dataset["user_setting"] = []
    at = _run(_save_script(dataset, raw={}), monkeypatch)
    assert not at.exception, [e.value for e in at.exception]
    for button_key in ("live_alo1_btn_0", "live_alo4_btn_1"):
        assert not at.button(key=button_key).disabled
        at.button(key=button_key).click().run()
        assert not at.exception, [e.value for e in at.exception]
    assert probe.calls == []
    failed = (f'<div class="alo-errline" role="alert">{logic.SAVE_FAIL_GLYPH} '
              f'{logic.TEXT_SAVE_FAILED}：{message}</div>')
    assert _markdown_values(at).count(failed) == 2                # ALO-1、ALO-4 各一行


def test_已存值帶四位以上小數_沒動就按存檔_寫回原值不寫顯示字串(monkeypatch, probe):
    import copy as _copy

    dataset = _copy.deepcopy(_DATASET)
    raw = dict(_RAW, alo_target_weights=(f'[{{"bucket": "{_CORE}", "weight_ratio": 0.333333}}, '
                                         f'{{"bucket": "{_SAT}", "weight_ratio": 0.00001}}]'),
               alo_tolerance_pp="2.55555")
    for row in dataset["user_setting"]:
        if row["setting_key"] == "alo_target_weights":
            row["setting_value"] = [{"bucket": _CORE, "weight_ratio": 0.333333},
                                    {"bucket": _SAT, "weight_ratio": 0.00001}]
        if row["setting_key"] == "alo_tolerance_pp":
            row["setting_value"] = 2.55555
    at = _run(_save_script(dataset, raw), monkeypatch)
    assert at.text_input(key="live_alo_target_0_weight").value == "0.3333"   # 前提：顯示字串被四捨五入過
    assert at.text_input(key="live_alo_tolerance_pp").value == "2.5556"
    at.button(key="live_alo1_btn_0").click().run()
    assert not at.exception, [e.value for e in at.exception]
    written = dict((key, value) for key, value, _kind in probe.calls)
    assert written["alo_tolerance_pp"] == "2.55555"
    assert json.loads(written["alo_target_weights"]) == json.loads(raw["alo_target_weights"])
