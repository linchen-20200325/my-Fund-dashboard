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

from ui_v2 import plain  # noqa: E402
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
    assert all(b.disabled for b in saves)
    # BL-0250 批次 1（`DEC-2026-10-19-04`）：ALO-3 那一枚原因改「試算存檔尚未開放」，ALO-1／ALO-4 照舊。
    assert sorted(b.help for b in saves) == sorted([live.SAVE_DISABLED_REASON] * 2 + [live.SCENARIO_SAVE_DISABLED_REASON])
    goto = [b for b in at.button if b.label == logic.TEXT_GOTO_SHEETS]
    assert len(goto) == 1 and not goto[0].disabled            # 導覽鈕照掛、不停用（草稿 §F 第 16 題）
    add = [b for b in at.button if b.label == logic.TEXT_ADD_SCENARIO]
    assert len(add) == 1 and not add[0].disabled


def test_市值基準下每一檔都資料未備_不偽造不隱藏(monkeypatch):
    """~~`nav` 是 `settings_store.PENDING_TABLES` 的一員~~ 本頁不取淨值（2026-10-09：L2 已把 nav 移出
    `PENDING_TABLES`，但 alo 取淨值未獲授權；狀態更新，不是漏刪）⇒ 市值基準沒有基準值。
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
    # Phase 3 P0-①：正式模式標籤裡的鍵名換成中文（`plain.key_name`）；兩個選項與它們的存值照舊。
    assert list(radios[0].options) == [plain.key_name(logic.BASIS_LABELS[logic.BASIS_COST]),
                                       plain.key_name(logic.BASIS_LABELS[logic.BASIS_MV])]
    assert not radios[0].disabled


def test_市值基準下淨值過期_畫面上逐檔印出實際淨值日(monkeypatch):
    """客戶 2026-10-14 裁示「舊淨值要標示實際資料日期；超過 10 天門檻 →『⬜ 資料未備』，不得參與相關計算」：
    正式模式 dataset 帶 `nav_not_ready.last` 時，畫面上那一句要帶每一檔的實際淨值日（不是舊的無日期那一句）。"""
    import copy as _copy

    dataset = _copy.deepcopy(_DATASET)
    for row in dataset["user_setting"]:
        if row["setting_key"] == "alo_basis":
            row["setting_value"] = logic.BASIS_MV
    dataset["nav_not_ready"] = {"codes": ["AAAA", "BBBB"], "days": 10,
                                "last": {"AAAA": "2026-09-14", "BBBB": "2026-09-03"}}
    script = _SCRIPT_LIVE.replace(repr(_DATASET), repr(dataset))
    at = _run(script, monkeypatch)
    assert not at.exception, [e.value for e in at.exception]
    text = "\n".join(_rendered(at))
    assert "◇ 資料未備：最近一筆淨值 2026-09-14（AAAA）、2026-09-03（BBBB），已超過 10 日" in text  # 2026-10-17 ◆／◇ 小批：正式模式「⬜ 資料未備」改 ◇（44 第七節第三小節之七其四；示範模式照舊）
    assert "⬜ 資料未備" not in text
    assert logic.NAV_NOT_READY_TEXT.format(days=10) not in text


def test_holding與policy一起取數失敗時照樣畫得完(monkeypatch):
    import copy as _copy

    dataset = _copy.deepcopy(_DATASET)
    dataset["errors"] = live.tables_failed_together("HTTP 503 upstream unavailable")
    dataset["holding"], dataset["policy"] = [], []
    script = _SCRIPT_LIVE.replace(repr(_DATASET), repr(dataset))
    at = _run(script, monkeypatch)
    assert not at.exception, [e.value for e in at.exception]
    text = "\n".join(_rendered(at))
    # Phase 3 P0-①：一般畫面只寫狀態句（⛔ 照舊）；原文移到跨頁的原始訊息（設定與診斷頁的進階診斷）。
    assert text.count("取數失敗") >= 2                        # 兩張表各自的失敗框照畫
    assert "HTTP 503 upstream unavailable" not in text
    raw = [e["text"] for e in at.session_state[plain.RAW_STATE]["alo"]["entries"]]
    assert sum("HTTP 503 upstream unavailable" in t for t in raw) >= 2
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


def _raw_texts(at):
    return [e["text"] for e in at.session_state[plain.RAW_STATE]["alo"]["entries"]]


def _fail_line_index(at, code="ALO-1"):
    """失敗鍵原位那一行。Phase 3 P0-①：一般畫面是 `plain` 改寫後的狀態句，原文只在跨頁的原始訊息裡。"""
    shown = plain.plain_text(logic.fetch_failed_text(_FAIL_MSG), page="alo", code=code)
    error = f'<div class="alo-errline" role="alert">{shown}</div>'
    values = _markdown_values(at)
    assert values.count(error) == 1, values
    assert logic.fetch_failed_text(_FAIL_MSG) in _raw_texts(at)
    assert not any(_FAIL_MSG in v for v in values)
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
    index = _fail_line_index(at, "ALO-4")
    basis = [i for i, v in enumerate(values) if v.startswith('<div class="alo-line">目前基準：')]
    assert basis and index > basis[0]
    assert not any(logic.TEXT_SAVE_FAILED in v for v in values)
    assert at.radio(key="live_alo_basis").value == logic.BASIS_MV          # 當下選的值不清掉


def test_有寫入函式時_ALO3存檔照舊停用_其餘兩枚可按(monkeypatch, probe):
    at = _run(_SCRIPT_SAVE, monkeypatch)
    assert not at.button(key="live_alo1_btn_0").disabled
    assert not at.button(key="live_alo4_btn_1").disabled
    alo3 = [b for b in at.button if b.label == logic.TEXT_SAVE and b.key.startswith("live_alo3")]
    assert len(alo3) == 1 and alo3[0].disabled and alo3[0].help == live.SCENARIO_SAVE_DISABLED_REASON  # BL-0250 批次 1（`DEC-2026-10-19-04`）：ALO-3 試算存檔的停用原因改「試算存檔尚未開放」
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
    # Phase 3 P0-①：一般畫面是改寫後的狀態句（圖示照舊），原文移到跨頁的原始訊息。
    # ~~failed = …plain.plain_text(f"{logic.TEXT_SAVE_FAILED}：{message}", …)~~ → 2026-10-17 Phase 3 P0-②（BL-0177；
    # 有意識的更正，不是漏刪）：讀失敗時按存檔，兩鍵都記為存檔失敗 ⇒ 卡片層改寫「儲存失敗」（`health.TEXT_SAVE_FAILED_BOTH`），
    # 兩鍵的原文各一筆進進階診斷。「兩鍵都失敗、卡片層一行、按鈕不停用、寫入 0 次」照舊。
    from ui_v2 import health

    failed = f'<div class="alo-errline" role="alert">{logic.SAVE_FAIL_GLYPH} {health.TEXT_SAVE_FAILED_BOTH}</div>'
    assert _markdown_values(at).count(failed) == 2                # ALO-1、ALO-4 各一行
    assert f"{logic.TEXT_SAVE_FAILED}：{message}" in _raw_texts(at)
    for key in ("alo_target_weights", "alo_tolerance_pp", "alo_basis", "alo_bucket_names"):
        assert f"{logic.TEXT_SAVE_FAILED}：{key}：{message}" in _raw_texts(at), key   # 兩鍵原文都進原始訊息


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


# ═══════════════════════ 未設定且沒動過的鍵不寫空值列（2026-10-15 Phase 2 批 2）═══════════════════════
#
# 重現（修正前）：四鍵都未設定時沒動就按 ALO-1、ALO-4 的存檔，寫入函式被呼叫四次、值皆為 None ——
# 真路徑下 L1 `save_user_setting` 會對每個鍵追加一列 `setting_value` 空白的紀錄。

def _with_unset(keys):
    import copy as _copy

    dataset = _copy.deepcopy(_DATASET)
    for row in dataset["user_setting"]:
        if row["setting_key"] in keys:
            row["setting_value"], row["updated_at"] = None, None
    return dataset, dict(_RAW, **{key: None for key in keys})


def test_四鍵都未設定_沒動就按兩枚存檔_寫入0次_畫面無失敗行(monkeypatch, probe):
    dataset, raw = _with_unset(set(live.SAVE_WIRED_KEYS))
    at = _run(_save_script(dataset, raw), monkeypatch)
    assert not at.exception, [e.value for e in at.exception]
    for button_key in ("live_alo1_btn_0", "live_alo4_btn_1"):
        assert not at.button(key=button_key).disabled
        at.button(key=button_key).click().run()
        assert not at.exception, [e.value for e in at.exception]
    assert probe.calls == []
    assert not any('class="alo-errline"' in v for v in _markdown_values(at))


def test_只有容許帶未設定_沒動就按存檔_只寫目標列(monkeypatch, probe):
    dataset, raw = _with_unset({"alo_tolerance_pp"})
    at = _run(_save_script(dataset, raw), monkeypatch)
    at.button(key="live_alo1_btn_0").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert probe.calls == [("alo_target_weights", _RAW["alo_target_weights"], "list")]


def test_容許帶未設定_使用者填了才寫(monkeypatch, probe):
    dataset, raw = _with_unset({"alo_tolerance_pp"})
    at = _run(_save_script(dataset, raw), monkeypatch)
    at.text_input(key="live_alo_tolerance_pp").set_value("3")
    at.button(key="live_alo1_btn_0").click().run()
    assert [call for call in probe.calls if call[0] == "alo_tolerance_pp"] == [("alo_tolerance_pp", "3", "float")]


# ═══════════════════════ 存檔失敗後恰逢讀取冷卻：打的字暫存帶回（客戶 2026-10-16 裁示方案 B）═══════════════════════
#
# 重現（2026-10-15 Phase 2 批 2，修正前）：容許帶打 5 → 存檔失敗 → 下一輪讀 `user_setting` 回冷卻 ⇒
# ALO-1／ALO-4 不畫輸入欄（`ALO-GAP-設定取數失敗`）⇒ 冷卻結束重繪時欄位回到表上的 4，打的 5 不見。
# 載入函式改由探針模組提供：`probe.cooling` 為真時回冷卻那一輪的資料（`errors["user_setting"]`、`setting_raw` 為空），
# 否則回 `probe.dataset`／`probe.raw`。探針的寫入不回寫到讀取（表上的值不會因為存成功而變），
# 這樣「存成功後丟掉暫存」才看得出差別。

_COOLING_MSG = "設定試算表暫停重試，還剩 30 秒（上次失敗類別：api）"


def _cooling_script():
    return f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
from ui_v2.alo import page
import {_PROBE} as probe

page.render(load_live=probe.load, save_live=probe.save)
"""


@pytest.fixture
def cooling(probe):
    import copy as _copy

    probe.dataset = _copy.deepcopy(_DATASET)
    probe.raw = dict(_RAW)
    probe.cooling = False
    probe.cool_on_fail = True

    def load():
        if probe.cooling:
            dataset = _copy.deepcopy(_DATASET)
            dataset["errors"] = {"user_setting": _COOLING_MSG}
            dataset["user_setting"] = []
            return {"dataset": dataset, "notes": {"setting_raw": {}}}
        return {"dataset": _copy.deepcopy(probe.dataset), "notes": {"setting_raw": dict(probe.raw)}}

    real_save = probe.save

    def save(key, value, kind):
        out = real_save(key, value, kind)
        if out["status"] != "saved" and probe.cool_on_fail:
            probe.cooling = True                     # 寫入失敗 ⇒ L1 登記冷卻，下一輪讀取被擋
        return out

    probe.load, probe.save = load, save
    return probe


def _save_fails_into_cooling(monkeypatch, cooling, failing, edit, button_key):
    cooling.failing = set(failing)
    at = _run(_cooling_script(), monkeypatch)
    assert not at.exception, [e.value for e in at.exception]
    edit(at)
    at.button(key=button_key).click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(at.text_input) == 0 and len(at.radio) == 0      # 冷卻那一輪：照舊不畫輸入欄（不改版面）
    return at


def _recover(at, cooling):
    cooling.cooling = False
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _set_tolerance(value):
    return lambda at: at.text_input(key="live_alo_tolerance_pp").set_value(value)


def test_暫存帶回_容許帶存檔失敗進冷卻_恢復後欄位帶回打的字_失敗行在_寫入次數不變(monkeypatch, cooling):
    at = _save_fails_into_cooling(monkeypatch, cooling, {"alo_tolerance_pp"}, _set_tolerance("5"),
                                  "live_alo1_btn_0")
    written = len(cooling.calls)
    assert written == 2                                        # 目標列＋容許帶各寫一次
    _recover(at, cooling)
    assert at.text_input(key="live_alo_tolerance_pp").value == "5"
    _fail_line_index(at)                                       # 失敗行照舊顯示
    assert len(cooling.calls) == written                       # 不自動存檔


def test_暫存帶回_恢復後再按存檔_寫出帶回的字不是舊值(monkeypatch, cooling):
    at = _save_fails_into_cooling(monkeypatch, cooling, {"alo_tolerance_pp"}, _set_tolerance("5"),
                                  "live_alo1_btn_0")
    _recover(at, cooling)
    cooling.failing = set()
    at.button(key="live_alo1_btn_0").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert cooling.calls[-1] == ("alo_tolerance_pp", "5", "float")
    assert not any('class="alo-errline"' in v for v in _markdown_values(at))


def test_暫存帶回_冷卻那一輪按存檔_暫存不被清(monkeypatch, cooling):
    at = _save_fails_into_cooling(monkeypatch, cooling, {"alo_tolerance_pp"}, _set_tolerance("5"),
                                  "live_alo1_btn_0")
    written = len(cooling.calls)
    at.button(key="live_alo1_btn_0").click().run()             # 讀取失敗那一輪：不寫，記成存檔失敗
    assert not at.exception, [e.value for e in at.exception]
    assert len(cooling.calls) == written
    _recover(at, cooling)
    assert at.text_input(key="live_alo_tolerance_pp").value == "5"


def test_暫存帶回_冷卻期間表上值改了_恢復後以表為準(monkeypatch, cooling):
    at = _save_fails_into_cooling(monkeypatch, cooling, {"alo_tolerance_pp"}, _set_tolerance("5"),
                                  "live_alo1_btn_0")
    for row in cooling.dataset["user_setting"]:
        if row["setting_key"] == "alo_tolerance_pp":
            row["setting_value"] = 6.0
    cooling.raw["alo_tolerance_pp"] = "6"
    _recover(at, cooling)
    assert at.text_input(key="live_alo_tolerance_pp").value == "6"


def test_暫存帶回_存成功之後再遇冷卻_恢復後顯示表上值(monkeypatch, cooling):
    cooling.failing, cooling.cool_on_fail = {"alo_tolerance_pp"}, False
    at = _run(_cooling_script(), monkeypatch)
    at.text_input(key="live_alo_tolerance_pp").set_value("5")
    at.button(key="live_alo1_btn_0").click().run()             # 失敗、沒冷卻 ⇒ 有暫存
    cooling.failing = set()
    at.button(key="live_alo1_btn_0").click().run()             # 這一次存成功 ⇒ 暫存丟掉
    assert cooling.calls[-1] == ("alo_tolerance_pp", "5", "float")
    cooling.cooling = True                                     # 之後另一個原因進了冷卻
    at.run()
    assert len(at.text_input) == 0
    _recover(at, cooling)
    # 探針的寫入不回寫到讀取，表上仍是 4：畫面顯示表上值，不帶回已經存出去的暫存。
    assert at.text_input(key="live_alo_tolerance_pp").value == "4"


def test_暫存帶回_目標列比重(monkeypatch, cooling):
    at = _save_fails_into_cooling(
        monkeypatch, cooling, {"alo_target_weights"},
        lambda at: at.text_input(key="live_alo_target_0_weight").set_value("0.65"), "live_alo1_btn_0")
    _recover(at, cooling)
    assert at.text_input(key="live_alo_target_0_weight").value == "0.65"
    assert at.text_input(key="live_alo_tolerance_pp").value == "4"   # 存成功的那個鍵不帶回（本來也沒改）


def test_暫存帶回_ALO4類別名稱(monkeypatch, cooling):
    at = _save_fails_into_cooling(
        monkeypatch, cooling, {"alo_bucket_names"},
        lambda at: at.text_input(key="live_alo_bucket_name_0").set_value("成長"), "live_alo4_btn_1")
    _recover(at, cooling)
    assert at.text_input(key="live_alo_bucket_name_0").value == "成長"


def test_暫存帶回_ALO4比重基準radio(monkeypatch, cooling):
    at = _save_fails_into_cooling(
        monkeypatch, cooling, {"alo_basis"},
        lambda at: at.radio(key="live_alo_basis").set_value(logic.BASIS_MV), "live_alo4_btn_1")
    _recover(at, cooling)
    assert at.radio(key="live_alo_basis").value == logic.BASIS_MV


def test_暫存帶回_ALO4比重基準暫存值不在選項內_頁面不崩_顯示表上值_丟掉該欄暫存(monkeypatch, cooling):
    """2026-10-16 稽核 B4：radio 帶回用 `options.index`，暫存值不在選項內時不得拋錯把整頁炸掉。"""
    at = _save_fails_into_cooling(
        monkeypatch, cooling, {"alo_basis"},
        lambda at: at.radio(key="live_alo_basis").set_value(logic.BASIS_MV), "live_alo4_btn_1")
    at.session_state[page._PENDING_INPUTS_STATE] = {"alo_basis": {"text": "不是選項的值", "raw": _RAW["alo_basis"]}}
    _recover(at, cooling)
    assert at.radio(key="live_alo_basis").value == logic.BASIS_COST            # 表上值（_RAW 的「成本」）
    assert "alo_basis" not in at.session_state[page._PENDING_INPUTS_STATE]


def test_暫存帶回_帶回之後再改字_又遇冷卻_帶回的是最新的字(monkeypatch, cooling):
    at = _save_fails_into_cooling(monkeypatch, cooling, {"alo_tolerance_pp"}, _set_tolerance("5"),
                                  "live_alo1_btn_0")
    _recover(at, cooling)
    at.text_input(key="live_alo_tolerance_pp").set_value("8").run()   # 跟著走：暫存刷新成 8
    cooling.cooling = True
    at.run()
    assert len(at.text_input) == 0
    _recover(at, cooling)
    assert at.text_input(key="live_alo_tolerance_pp").value == "8"


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
