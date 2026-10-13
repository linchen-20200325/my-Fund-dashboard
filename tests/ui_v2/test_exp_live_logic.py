# -*- coding: utf-8 -*-
"""標的探索正式模式的純邏輯測試（fast lane；不需要 streamlit、不連網、不碰 L1）。

依據客戶 2026-10-13 裁示（B 線標的探索正式模式第一批）：
- **只有成功儲存的設定才生效**：輸入欄當下的值不得影響 `EXP-2`／`EXP-7`／`EXP-0`（突變測試的目標：
  把 `logic.build_page_model(saved_only=True)` 那一段拿掉，`test_只吃已存值_*` 幾條要轉紅）；
- **基本資料缺欄：基金仍保留在清單**，缺的格寫「⬜ 資料未備：<原因>」，不印 None、不填 0、不從代碼推名稱；
- 讀不到設定（錯誤）與沒設定分開顯示；`EXP-4` 一成一敗照實講哪一鍵成功、哪一鍵失敗。

示範模式不受影響由既有的 `tests/ui_v2/test_exp_logic.py` 全套守住（本檔不重複）。
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ui_v2.exp import fixtures, live, logic  # noqa: E402
from ui_v2.set import spec as set_spec  # noqa: E402


def _pool(codes=("B02", "A01", "C03"), *, status="ok", message=None, blank=0, dup=0):
    return {"status": status, "backend": "service_account" if status != "pool_not_cloud" else "local",
            "codes": list(codes) if status == "ok" else [], "dropped_blank": blank, "duplicates": dup,
            "message": message}


def _settings(rules=None, columns=None, sort=None, watch=None):
    return {live.KEY_RULES: None if rules is None else tuple(rules),
            live.KEY_COLUMNS: None if columns is None else tuple(columns),
            live.KEY_SORT: sort,
            live.KEY_WATCH: None if watch is None else tuple(watch)}


def _input(pool=None, settings=None, settings_error=None):
    pool = pool or _pool()
    settings = settings or _settings()
    return {"dataset": live.build_dataset(pool, settings),
            "notes": {"pool": pool, "settings": settings, "settings_error": settings_error}}


def _model(**kwargs):
    inputs = kwargs.pop("inputs", None) or _input()
    return live.build_live_model(inputs, save_wired=kwargs.pop("save_wired", True), **kwargs)


def _b(model, code):
    return logic.find_block(model, code)


def _codes(model):
    return [row["_fund_code"] for row in _b(model, "EXP-2")["_rows"]]


_NOT_C03 = ({"field": "fund_code", "op": "不等於", "value": "C03"},)


# ═════════════════════ 鏡像與形狀 ═════════════════════


def test_按鈕類別常數是44那八類的成員():
    assert live.ACTION_SAVE in logic.BUTTON_KINDS and live.ACTION_ADD_ROW in logic.BUTTON_KINDS


def test_四鍵與value_kind是set頁規格快照的鏡像():
    mirror = {key: kind for key, kind in set_spec.SPEC_SETTING_KEYS if key.startswith("exp_")}
    assert mirror == live.VALUE_KINDS


def test_比較方向是fixtures那一份的鏡像_正式路徑不import_fixtures():
    assert live.RULE_OPERATORS == fixtures.OPERATORS
    import ast

    tree = ast.parse(pathlib.Path(live.__file__).read_text(encoding="utf-8"))
    imported = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    imported += [f"{n.module}.{a.name}" if n.module else a.name
                 for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names]
    assert imported and not [m for m in imported if "fixtures" in m or "streamlit" in m], imported


def test_dataset與示範資料同形():
    data = live.build_dataset(_pool(), _settings())
    demo = fixtures.scenario("full")["dataset"]
    assert set(data) == set(demo)
    assert [r["setting_key"] for r in data["user_setting"]] == [r["setting_key"] for r in demo["user_setting"]]
    row = data["fund_profile"][0]
    assert set(row) == set(logic.FUND_PROFILE_FIELDS)
    assert row["fund_code"] == "B02" and all(v is None for k, v in row.items() if k != "fund_code")
    assert data["nav"] == [] and data["dividend"] == [] and data["div_ratio_pct"] == {} and data["errors"] == {}


# ═════════════════════ 設定解析：讀不到 ≠ 沒設定 ═════════════════════


def _rows(**values):
    return {key: {"setting_key": key, "setting_value": value} for key, value in values.items()}


def test_解析_合法四鍵():
    rows = _rows(exp_filter_rules=json.dumps(list(_NOT_C03), ensure_ascii=False),
                 exp_visible_columns='["fund_name", "nav_date"]', exp_sort_column='["nav_date"]',
                 exp_watchlist='["A01"]')
    settings, error = live.parse_user_settings(rows, [])
    assert error is None
    assert settings == _settings(rules=_NOT_C03, columns=("fund_name", "nav_date"), sort="nav_date", watch=("A01",))


def test_解析_沒有那一列是未設定_不是錯誤():
    assert live.parse_user_settings({}, []) == (live.EMPTY_SETTINGS, None)
    assert live.parse_user_settings(_rows(exp_sort_column="[]"), [])[0][live.KEY_SORT] is None


@pytest.mark.parametrize("rows, broken", [
    (_rows(exp_filter_rules="not json"), []),
    (_rows(exp_filter_rules='[{"field": "ccy", "op": "包含", "value": "USD"}]'), []),       # 比較方向不在六個之內
    (_rows(exp_filter_rules='[{"field": "名稱", "op": "等於", "value": "x"}]'), []),       # 欄位不在可選清單
    (_rows(exp_filter_rules='[{"field": "ccy", "op": "等於"}]'), []),                      # 少一欄
    (_rows(exp_visible_columns='["fund_name", "分數"]'), []),
    (_rows(exp_sort_column='["nav_date", "ccy"]'), []),
    (_rows(exp_watchlist='["A01", "A01"]'), []),
    (_rows(exp_watchlist='[NaN]'), []),
    ({}, ["exp_watchlist"]),
])
def test_解析_讀不了_回訊息_四鍵一律None_不當成未設定(rows, broken):
    settings, error = live.parse_user_settings(rows, broken)
    assert error and error.startswith("設定值讀不到可用的形狀")
    assert settings == live.EMPTY_SETTINGS


def test_讀不到設定_與沒設定分開顯示_存檔一律停用():
    unset = _model(inputs=_input(settings=_settings()))
    assert _b(unset, "EXP-0")["text"] == logic.TEXT_NO_CONDITION
    assert logic.TEXT_NO_CONDITION in _b(unset, "EXP-2")["notes"]
    broken = _model(inputs=_input(settings=dict(live.EMPTY_SETTINGS), settings_error="HTTP 403 讀不到"))
    exp0 = _b(broken, "EXP-0")
    assert exp0["_tone_override"] == "紅" and exp0["text"] != logic.TEXT_NO_CONDITION
    assert any("HTTP 403 讀不到" in line for line in exp0["fetch_fail_lines"])
    for code in ("EXP-1", "EXP-2", "EXP-4", "EXP-5", "EXP-7"):
        block = _b(broken, code)
        assert block["_state"] == logic.STATE_ERROR, code
        assert logic.TEXT_NO_CONDITION not in block["notes"], code
    assert logic.TEXT_ONLY_FUND_NAME not in _b(broken, "EXP-2")["notes"]      # 不知道 ≠ 使用者沒勾
    assert _b(broken, "EXP-5")["detail_lines"][0] == logic.TEXT_WATCHLIST_UNREADABLE
    for code in ("EXP-1", "EXP-4", "EXP-5"):
        for button in _b(broken, code)["buttons"]:
            if button["_action_kind"] == "存檔":
                assert not button["_enabled"] and button["disabled_reason"] == live.SAVE_UNREADABLE_REASON
    # 第二道：讀不到時 EXP-5 的存檔輸入本身就帶錯誤（不會把已存觀察清單蓋成只剩這次勾的幾檔）
    assert live.exp5_save_entries((), ("A01",), "HTTP 403")[0]["error"] == live.SAVE_UNREADABLE_REASON


# ═════════════════════ 只吃已存值（客戶 2026-10-13 裁示；突變測試目標） ═════════════════════


def test_只吃已存值_欄位的條件不影響候選清單與結論與軌跡():
    saved = _input(settings=_settings(rules=_NOT_C03))
    base = _model(inputs=saved)
    assert _codes(base) == ["A01", "B02"]
    draft = [{"field": "fund_code", "op": "等於", "value": "A01"}]
    edited = _model(inputs=saved, field_rules=draft)
    assert _codes(edited) == ["A01", "B02"]                                    # 未存的條件不進 EXP-2
    assert _b(edited, "EXP-0")["text"] == _b(base, "EXP-0")["text"] == "目前條件下有 2 檔"   # 正式模式不帶示意
    assert [r["condition_text"] for r in _b(edited, "EXP-7")["_rows"]] == ["fund_code 不等於 C03"]
    # EXP-1 的輸入列照畫當下內容，並標「未存檔」
    exp1 = _b(edited, "EXP-1")
    assert [r["text"] for r in exp1["_rows"]] == ["fund_code 等於 A01"]
    assert logic.TEXT_UNSAVED_RULES in exp1["detail_lines"]
    assert logic.TEXT_UNSAVED_RULES not in _b(base, "EXP-1")["detail_lines"]


def test_只吃已存值_從未存過時_欄位有條件也是尚未設定條件():
    model = _model(inputs=_input(settings=_settings()), field_rules=[{"field": "fund_code", "op": "等於", "value": "A01"}])
    assert _b(model, "EXP-0")["text"] == logic.TEXT_NO_CONDITION and _codes(model) == []


def test_只吃已存值_欄位勾選與排序不影響候選清單的欄():
    saved = _input(settings=_settings(rules=_NOT_C03, columns=("fund_name",)))
    model = _model(inputs=saved, field_columns=["fund_name", "ccy", "nav_date"], field_sort="nav_date")
    assert _b(model, "EXP-2")["column_keys"] == (logic.CODE_COLUMN, "fund_name")
    assert _b(model, "EXP-2")["sort_caption"] == "依 fund_code 字面值排列（未選排序欄位）"
    assert live.TEXT_UNSAVED_EXP4 in _b(model, "EXP-4")["detail_lines"]
    same = _model(inputs=saved, field_columns=["fund_name"], field_sort=None)
    assert live.TEXT_UNSAVED_EXP4 not in _b(same, "EXP-4")["detail_lines"]


def test_示範模式照舊取當下值_對照組():
    """對照組：同一份資料走示範模式（`saved_only` 預設 False），當下的條件**會**進 EXP-2 ——
    證明上面幾條紅綠真的取決於 `saved_only`，不是資料湊巧。"""
    dataset = live.build_dataset(_pool(), _settings(rules=_NOT_C03))
    demo = logic.build_page_model(dataset, draft_rules=[{"field": "fund_code", "op": "等於", "value": "A01"}])
    assert [r["_fund_code"] for r in _b(demo, "EXP-2")["_rows"]] == ["A01"]


# ═════════════════════ 缺欄：基金仍保留在清單 ═════════════════════


def test_只有代碼_其餘欄寫資料未備與原因_基金不消失_不印None_不帶示意():
    model = _model(inputs=_input(settings=_settings(rules=_NOT_C03, columns=logic.COLUMN_ORDER)))
    exp2 = _b(model, "EXP-2")
    assert exp2["column_keys"] == (logic.CODE_COLUMN,) + logic.COLUMN_ORDER
    assert _codes(model) == ["A01", "B02"]
    for row in exp2["_rows"]:
        assert row["_cells"][logic.CODE_COLUMN]["text"] == row["_fund_code"]
        for column in logic.COLUMN_ORDER:
            assert row["_cells"][column]["text"] == live.missing_text(column), column
            assert row["_cells"][column]["_state"] == logic.STATE_MISSING
    assert live.missing_text("fund_name") == "⬜ 資料未備：基本資料尚未接入"
    strings = logic.collect_ui_strings(model)
    assert not [s for s in strings if "None" in s]
    assert not [s for s in strings if "示意" in s]


def test_對照與單檔基礎資料_缺欄照寫_欄頭不拿代碼頂替基金名():
    model = _model(inputs=_input(settings=_settings(rules=_NOT_C03)), compare_checked=("A01", "B02"))
    columns = _b(model, "EXP-3")["_columns"]
    assert [c["head_text"] for c in columns] == ["A01　⬜ 資料未備", "B02　⬜ 資料未備"]
    for column in columns:
        assert all(cell["text"].startswith("⬜ 資料未備：") for cell in column["_cells"].values())
    fields = _b(model, "EXP-6")["_fields"]
    assert [f["text"] for f in fields][1] == "A01"                             # fund_code 那一格原樣
    assert all(f["text"] == live.missing_text(key)
               for (key, _l), f in zip(logic.EXP6_FIELDS, fields) if key != "fund_code")


def test_母體說明行_略過與重複的筆數():
    model = _model(inputs=_input(pool=_pool(blank=2, dup=1), settings=_settings(rules=_NOT_C03)))
    lines = _b(model, "EXP-2")["detail_lines"]
    assert any(line.startswith("母體：選股池的基金代碼 3 檔") for line in lines)
    assert "選股池有 2 列代碼為空白，未列入。" in lines and "選股池有 1 列代碼重複，只列一次。" in lines


@pytest.mark.parametrize("status, message", [("pool_not_cloud", "選股池未設定雲端來源（測試）"),
                                             ("failed", "APIError: 403 （測試）")])
def test_母體讀不到_照取數失敗畫_不講成沒有符合的基金(status, message):
    model = _model(inputs=_input(pool=_pool(status=status, message=message), settings=_settings(rules=_NOT_C03)))
    exp0 = _b(model, "EXP-0")
    assert exp0["_tone_override"] == "紅"
    assert any(message in line for line in exp0["fetch_fail_lines"])
    assert logic.TEXT_NO_MATCH not in _b(model, "EXP-2")["notes"]
    assert any(message in line for line in _b(model, "EXP-2")["notes"])


# ═════════════════════ 條件作用在 ⬜ 欄位：不替缺值選邊（E-09），也不讓整頁當掉 ═════════════════════


def test_條件作用在資料未備的欄位_計算失敗_不排除也不保留_整頁照畫():
    rules = ({"field": "ccy", "op": "等於", "value": "USD"},)
    model = _model(inputs=_input(settings=_settings(rules=rules)))
    exp0 = _b(model, "EXP-0")
    assert exp0["_tone_override"] == "紅" and exp0["state_word"] == "計算失敗"
    assert exp0["text"] == "讀到的那兩塊有一塊計算失敗"
    assert _codes(model) == []                                        # 不是「全部保留」也不是「0 檔符合」
    assert logic.TEXT_NO_MATCH not in _b(model, "EXP-2")["notes"]
    assert any(n.startswith(logic.COMPUTE_ERR_TEXT) and "ccy 等於 USD" in n for n in _b(model, "EXP-2")["notes"])
    exp7 = _b(model, "EXP-7")
    assert exp7["_rows"] == [] and exp7["summary_text"] == logic.COMPUTE_ERR_TEXT
    # 示範模式照舊炸（既有行為不變）
    with pytest.raises(logic.UnspecifiedComparison):
        logic.build_page_model(live.build_dataset(_pool(), _settings(rules=rules)))


# ═════════════════════ 存檔輸入 ═════════════════════


def test_EXP1存檔_原樣寫回_數值留空的列照寫_欄位不合法就不寫():
    rows = [{"_id": 3, "field": "fund_code", "op": "等於", "value": "A01"},
            {"_id": 4, "field": "mgmt_fee_rate_pct", "op": "小於", "value": ""}]
    entry = live.exp1_save_entries(rows)[0]
    assert entry["error"] is None and entry["value_kind"] == "rules"
    assert json.loads(entry["value"]) == [{"field": "fund_code", "op": "等於", "value": "A01"},
                                          {"field": "mgmt_fee_rate_pct", "op": "小於", "value": ""}]
    # 讀回逐字相同
    settings, error = live.parse_user_settings(_rows(exp_filter_rules=entry["value"]), [])
    assert error is None and list(settings[live.KEY_RULES]) == [{k: r[k] for k in ("field", "op", "value")} for r in rows]
    bad = live.exp1_save_entries([{"field": "名稱", "op": "等於", "value": "x"}])[0]
    assert bad["value"] is None and "第 1 列" in bad["error"]
    assert live.exp1_save_entries([])[0]["value"] == "[]"                      # 清空也存得回去


def test_EXP4存檔_一枚按鈕寫兩鍵_排序存成長度0或1的陣列():
    entries = live.exp4_save_entries(["nav_date", "fund_name"], "nav_date")
    assert [(e["key"], e["value"], e["value_kind"]) for e in entries] == [
        ("exp_visible_columns", '["fund_name", "nav_date"]', "list"), ("exp_sort_column", '["nav_date"]', "list")]
    assert live.exp4_save_entries([], None)[1]["value"] == "[]"


def test_EXP5存檔_已存與這次勾的聯集_同一檔只一次():
    entry = live.exp5_save_entries(("A01",), ("B02", "A01"))[0]
    assert json.loads(entry["value"]) == ["A01", "B02"]


def _saver(fail_keys=(), record=None):
    def save(key, value, kind):
        if record is not None:
            record.append((key, value, kind))
        if key in fail_keys:
            return {"status": "failed", "key": key, "message": f"{key} 寫入失敗（測試）"}
        return {"status": "saved", "key": key}
    return save


def test_EXP4一成一敗_照實講哪一鍵成功哪一鍵失敗_不整體顯示成功():
    record = []
    results = live.run_saves(live.exp4_save_entries(["fund_name"], None),
                             _saver(fail_keys=("exp_sort_column",), record=record))
    assert results == {"exp_visible_columns": None, "exp_sort_column": "exp_sort_column 寫入失敗（測試）"}
    assert [k for k, _v, _k in record] == ["exp_visible_columns", "exp_sort_column"]
    model = _model(save_results=results)
    exp4 = _b(model, "EXP-4")
    assert "exp_visible_columns：已存檔" in exp4["detail_lines"]
    assert live.TEXT_SAVED not in exp4["detail_lines"]                         # 不出整體「已存檔」
    assert exp4["error_lines"] == ["存檔寫入失敗：exp_sort_column：exp_sort_column 寫入失敗（測試）"]


def test_EXP4前一鍵失敗就不寫後一鍵_逐鍵照實寫():
    record = []
    results = live.run_saves(live.exp4_save_entries(["fund_name"], None),
                             _saver(fail_keys=("exp_visible_columns",), record=record))
    assert [k for k, _v, _k in record] == ["exp_visible_columns"]
    # ~~assert results["exp_sort_column"] == "前一個鍵存檔失敗，本鍵未寫入"~~ → 2026-10-13 稽核回修：不冠「寫入失敗」
    assert results["exp_sort_column"] == live.TEXT_SKIPPED == "未寫入：前一個鍵存檔失敗"
    exp4 = _b(_model(save_results=results), "EXP-4")
    assert exp4["error_lines"] == [
        "存檔寫入失敗：exp_visible_columns：exp_visible_columns 寫入失敗（測試）",
        "exp_sort_column：未寫入：前一個鍵存檔失敗",
    ]
    assert not [line for line in exp4["error_lines"] if line.startswith("存檔寫入失敗：exp_sort_column")]


def test_全部成功_一行已存檔():
    model = _model(save_results={"exp_filter_rules": None})
    assert live.TEXT_SAVED in _b(model, "EXP-1")["detail_lines"]


def test_帶錯誤的輸入一鍵都不寫():
    record = []
    results = live.run_saves(live.exp1_save_entries([{"field": "x", "op": "等於", "value": "1"}]), _saver(record=record))
    assert record == [] and results["exp_filter_rules"].startswith("未存檔：")


def test_沒接寫入函式_存檔停用():
    model = _model(save_wired=False)
    for code in ("EXP-1", "EXP-4", "EXP-5"):
        for button in _b(model, code)["buttons"]:
            if button["_action_kind"] == "存檔":
                assert not button["_enabled"] and button["disabled_reason"] == live.SAVE_DISABLED_REASON


# ═════════════════════ 2026-10-13 稽核 K／L 回修 ═════════════════════


def test_存完又改了_不再單寫已存檔_改寫照實的句子():
    saved = _input(settings=_settings(rules=_NOT_C03))
    edited = _model(inputs=saved, field_rules=[{"field": "fund_code", "op": "等於", "value": "A01"}],
                    save_results={"exp_filter_rules": None})
    lines = _b(edited, "EXP-1")["detail_lines"]
    assert logic.TEXT_UNSAVED_RULES in lines and live.TEXT_SAVED_THEN_EDITED in lines
    assert live.TEXT_SAVED not in lines
    same = _model(inputs=saved, field_rules=list(_NOT_C03), save_results={"exp_filter_rules": None})
    assert live.TEXT_SAVED in _b(same, "EXP-1")["detail_lines"]
    exp4 = _b(_model(inputs=saved, field_columns=["ccy"], field_sort=None,
                     save_results={"exp_visible_columns": None, "exp_sort_column": None}), "EXP-4")
    assert live.TEXT_SAVED_THEN_EDITED in exp4["detail_lines"] and live.TEXT_SAVED not in exp4["detail_lines"]


def test_代碼欄存在時_不說只顯示基金名():
    model = _model(inputs=_input(settings=_settings(rules=_NOT_C03, columns=())))
    exp2 = _b(model, "EXP-2")
    assert exp2["column_keys"] == (logic.CODE_COLUMN, "fund_name")
    assert logic.TEXT_ONLY_FUND_NAME not in exp2["notes"]
    assert logic.TEXT_ONLY_CODE_AND_NAME in exp2["notes"]
    assert _b(model, "EXP-4")["summary_text"] == logic.TEXT_ONLY_CODE_AND_NAME
    # 對照組：同一份資料不帶代碼欄（示範模式的組法）→ 照舊「目前只顯示基金名」
    demo = logic.build_page_model(live.build_dataset(_pool(), _settings(rules=_NOT_C03, columns=())))
    assert logic.TEXT_ONLY_FUND_NAME in _b(demo, "EXP-2")["notes"]
    assert logic.TEXT_ONLY_CODE_AND_NAME not in _b(demo, "EXP-2")["notes"]


def test_讀不到設定時_新增條件也停用():
    broken = _model(inputs=_input(settings=dict(live.EMPTY_SETTINGS), settings_error="HTTP 403"))
    add = [b for b in _b(broken, "EXP-1")["buttons"] if b["_action_kind"] == live.ACTION_ADD_ROW]
    assert add and not add[0]["_enabled"]
    ok = _model()
    add = [b for b in _b(ok, "EXP-1")["buttons"] if b["_action_kind"] == live.ACTION_ADD_ROW]
    assert add and add[0]["_enabled"]


def test_指紋_同值同指紋_換值換指紋_存檔後的預期值與讀回相同():
    a = _settings(rules=_NOT_C03, columns=("fund_name",))
    assert live.settings_fingerprint(a) == live.settings_fingerprint(dict(a))
    assert live.settings_fingerprint(a) != live.settings_fingerprint(_settings(rules=_NOT_C03))
    assert live.settings_fingerprint(live.EMPTY_SETTINGS) != live.settings_fingerprint(_settings(columns=()))
    entries = live.exp4_save_entries(["ccy"], "ccy")
    results = {"exp_visible_columns": None, "exp_sort_column": "失敗"}
    after = live.settings_after_saves(a, entries, results)
    assert after[live.KEY_COLUMNS] == ("ccy",) and after[live.KEY_SORT] is None   # 失敗的那一鍵不改
    read_back, error = live.parse_user_settings(_rows(
        exp_filter_rules=json.dumps(list(_NOT_C03), ensure_ascii=False),
        exp_visible_columns=entries[0]["value"]), [])
    assert error is None and live.settings_fingerprint(read_back) == live.settings_fingerprint(after)


_CODE_SHAPES = ["00123", "0050", "ALZF9", "ACDD01", "AB-123", "tw-0001", "A01.US", "F0025"]


@pytest.mark.parametrize("code", _CODE_SHAPES)
def test_正式模式_任何代碼形狀_代碼以外的欄全部缺值_不推任何屬性(code):
    """稽核 K M5：釘死「代碼以外的欄全部 ⬜／None」。依代碼形狀推幣別、推名稱這類突變會在這裡紅。"""
    pool = _pool(codes=(code,))
    data = live.build_dataset(pool, _settings(rules=({"field": "fund_code", "op": "等於", "value": code},),
                                              columns=logic.COLUMN_ORDER))
    row = data["fund_profile"][0]
    assert row["fund_code"] == code
    assert {k: v for k, v in row.items() if k != "fund_code"} == {k: None for k in logic.FUND_PROFILE_FIELDS
                                                                  if k != "fund_code"}
    assert data["nav"] == [] and data["dividend"] == [] and data["div_ratio_pct"] == {}
    model = live.build_live_model({"dataset": data, "notes": {"pool": pool, "settings": None or {},
                                                              "settings_error": None}},
                                  compare_checked=(code,), save_wired=True)
    (exp2_row,) = _b(model, "EXP-2")["_rows"]
    for column in logic.COLUMN_ORDER:
        assert exp2_row["_cells"][column]["text"] == live.missing_text(column), (code, column)
    for column in _b(model, "EXP-3")["_columns"]:
        assert all(cell["_state"] == logic.STATE_MISSING for cell in column["_cells"].values()), code
    texts = [f["text"] for f in _b(model, "EXP-6")["_fields"]]
    assert texts[1] == code and all(t.startswith("⬜ 資料未備：") for i, t in enumerate(texts) if i != 1)



def test_母體說明行_讀取時間轉台北時間_寫出最長更新間隔():
    pool = dict(_pool(), read_at="2026-10-13T10:05:00+00:00", ttl_sec=3600)
    assert live.pool_read_line(pool) == "選股池讀取於 2026-10-13 18:05（台北時間），最長約 1 小時更新一次。"
    lines = _b(_model(inputs=_input(pool=pool, settings=_settings(rules=_NOT_C03))), "EXP-2")["detail_lines"]
    assert live.pool_read_line(pool) in lines
    assert live.pool_read_line(dict(pool, read_at=None)) is None
    assert live.pool_read_line(dict(pool, read_at="2026-10-13T10:05:00")) is None     # 沒有時區：不猜
    assert live.pool_read_line(dict(pool, read_at="壞字串")) is None
