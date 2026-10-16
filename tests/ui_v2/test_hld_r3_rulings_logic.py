# -*- coding: utf-8 -*-
"""持倉體檢：客戶 2026-10-16 裁示第 2、5、8 點的純函式測試（fast lane；本檔不畫畫面）。

- 第 2 點：HLD-4「只有已存設定生效、下次載入套用」—— 正式結果只讀已存設定；「存檔」接上 `user_setting`。
- 第 5 點：HLD 配息改為只標缺的那幾檔「⬜ 資料未備」，其他基金照常顯示。
- 第 8 點：`44` 4.1 同鍵多列加總；客戶護欄：只有依既有正式鍵規則確認屬於同一個鍵、同一語意的資料才能加總，
  不得因名稱相似而合併（原文見 `44` 檔尾〈第七節第三小節之六〉）。

畫面層（`page.render` 真路徑）的同三點見 `test_hld_r3_rulings_page.py`（slow）。
"""

from __future__ import annotations

import copy
import pathlib
import sys
from datetime import date

import pytest

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_HERE))

from ui_v2.hld import fixtures, live, logic  # noqa: E402

import test_hld_live_assemble as A  # noqa: E402  —— 沿用組裝測試的合格輸入（`_kwargs`）與常數

_TODAY = date(2026, 9, 28)   # 假資料最後一筆淨值 9/18，距今恰 10 天（照用；同其他 hld 正式模式測試）
_DIRECT_ID = A._DIRECT_ID


def _rehomed_args(name="full"):
    args = copy.deepcopy(fixtures.scenario(name))
    for holding in args["dataset"].get("holding") or ():
        if holding["policy_id"] == _DIRECT_ID:
            holding["policy_id"] = "P-001"
    return args


def _prov(dataset):
    return {row["fund_code"]: {"cache_fallback": False, "stale": None} for row in dataset.get("nav") or ()}


def _live(dataset, **kw):
    return live.build_live_model(dataset, direct_policy_id=_DIRECT_ID, nav_provenance=_prov(dataset),
                                 today=_TODAY, **kw)


def _texts(model, code):
    return [mv["text"] for g in logic.find_block(model, code)["fund_groups"] for mv in g["main_values"]]


# ═══════════════════════════ 第 2 點：已存設定生效、存檔接上 ═══════════════════════════


def test_第2點_存檔三鍵_值與型別_門檻寫成讀得回來的JSON():
    rows = [("最大回撤", "低於", "-10"), ("配息佔淨值比", "高於", "6.5"), ("", "", "")]
    entries = live.hld4_save_entries("2026-02-01", "2026-09-19", rows)
    assert [(e["key"], e["value_kind"], e["error"]) for e in entries] == [
        ("hld_window_start", "date", None), ("hld_window_end", "date", None), ("hld_deviation_rules", "rules", None),
    ]
    assert [e["value"] for e in entries[:2]] == ["2026-02-01", "2026-09-19"]
    # 讀回：寫進去的字串經正式模式的解析器讀得回同一組門檻（三格全空的列＝沒有這一列）。
    parsed, problem = live.parse_user_settings({e["key"]: {"setting_value": e["value"]} for e in entries})
    assert problem is None
    assert [r["setting_value"] for r in parsed] == [
        "2026-02-01", "2026-09-19",
        [{"indicator": "最大回撤", "direction": "低於", "value": -10.0},
         {"indicator": "配息佔淨值比", "direction": "高於", "value": 6.5}],
    ]


def test_第2點_存檔三鍵的value_kind_與設定頁規格逐字相同():
    from ui_v2.set import spec

    mirror = {key: kind for key, kind in spec.SPEC_SETTING_KEYS if key.startswith("hld_")}
    assert mirror == live.SAVE_VALUE_KINDS
    assert set(live.SAVE_VALUE_KINDS) == set(live.SETTING_KEYS)


@pytest.mark.parametrize("start, end, rows, reason", [
    ("", "", [("", "", "")], logic.TEXT_BOTH_EMPTY),
    ("2026-01-01", "", [("", "", "")], logic.TEXT_BAD_RANGE),
    ("2026-09-19", "2026-01-01", [("", "", "")], logic.TEXT_BAD_RANGE),
    ("2026-01-01", "2026-09-19", [("最大回撤", "", "-1")], logic.TEXT_RULES_BAD),
])
def test_第2點_欄位不合格_三鍵都帶原因_任何鍵都不寫(start, end, rows, reason):
    entries = live.hld4_save_entries(start, end, rows)
    assert {e["error"] for e in entries} == {reason} and {e["value"] for e in entries} == {None}
    calls = []
    out = live.run_saves(entries, lambda *a: calls.append(a) or {"status": "saved"})
    assert calls == []
    assert out == {key: reason for key in live.SETTING_KEYS}


def test_第2點_逐鍵寫入_前一個鍵失敗就不寫下一個鍵_訊息照原文():
    entries = live.hld4_save_entries("2026-02-01", "2026-09-19", [("", "", "")])
    calls = []

    def save(key, value, kind):
        calls.append((key, value, kind))
        return {"status": "failed", "key": key, "message": "HTTP 503（已遮蔽）"}

    out = live.run_saves(entries, save)
    assert calls == [("hld_window_start", "2026-02-01", "date")]
    assert out == {"hld_window_start": "HTTP 503（已遮蔽）",
                   "hld_window_end": live.TEXT_PREVIOUS_FAILED,
                   "hld_deviation_rules": live.TEXT_PREVIOUS_FAILED}
    # 訊息空字串 → 退回狀態碼原文，不讓失敗看起來像成功
    assert live.run_saves(entries[:1], lambda *a: {"status": "kind_mismatch", "message": ""}) == {
        "hld_window_start": "kind_mismatch"}


def test_第2點_存檔結果寫進HLD4說明行_失敗不改任何計算_不改呼叫端那一份():
    args = _rehomed_args()
    base = _live(args["dataset"])
    ok = _live(args["dataset"], save_results={k: None for k in live.SETTING_KEYS})
    failed = _live(args["dataset"], save_results={"hld_window_start": "HTTP 503",
                                                  "hld_window_end": live.TEXT_PREVIOUS_FAILED,
                                                  "hld_deviation_rules": live.TEXT_PREVIOUS_FAILED})
    assert logic.find_block(ok, "HLD-4")["detail_lines"][-1] == live.TEXT_SAVED
    assert logic.find_block(failed, "HLD-4")["detail_lines"][-3:] == [
        f"{live.TEXT_SAVE_FAILED}hld_window_start：HTTP 503",
        f"{live.TEXT_SAVE_FAILED}hld_window_end：{live.TEXT_PREVIOUS_FAILED}",
        f"{live.TEXT_SAVE_FAILED}hld_deviation_rules：{live.TEXT_PREVIOUS_FAILED}",
    ]
    for code in ("HLD-2", "HLD-3"):
        assert _texts(failed, code) == _texts(base, code) == _texts(ok, code), code
    snapshot = copy.deepcopy(base)
    live.apply_save_results(base, {"hld_window_start": None})
    assert base == snapshot
    with pytest.raises(ValueError, match="本頁三鍵以外的鍵"):
        live.apply_save_results(base, {"mkt_window_days": None})


def test_第2點_套用值進不了正式模式_六塊只看已存設定():
    """正式模式整頁模型的區間與門檻只來自 dataset 的 `user_setting`；`build_live_model` 收不到套用值。"""
    args = _rehomed_args()
    model = _live(args["dataset"], fields={"window_start": "2026-06-01", "window_end": "2026-09-19"})
    assert model["_window"] == logic.saved_window(args["dataset"])
    with pytest.raises(TypeError):
        _live(args["dataset"], applied_window=("2026-06-01", "2026-09-19"))
    with pytest.raises(TypeError):
        _live(args["dataset"], applied_rules=[])


def test_第2點_source存檔走真的L2型別檢查_L1收到的就是三鍵原字串(monkeypatch):
    source = pytest.importorskip("ui_v2.hld.source")
    import types

    from services.v2_tables import settings_store

    monkeypatch.setattr(source, "st", types.SimpleNamespace(secrets={}, session_state={}))
    written = []

    def fake_l1(key, value, kind, *, mask):
        written.append((key, value, kind))
        return {"setting_key": key, "setting_value": value, "value_kind": kind, "updated_at": "2026-10-16T00:00:00Z"}

    monkeypatch.setattr(settings_store.store, "save_user_setting", fake_l1)
    entries = live.hld4_save_entries("2026-02-01", "2026-09-19", [("最大回撤", "低於", "-10")])
    out = live.run_saves(entries, source.save_setting)
    assert out == {key: None for key in live.SETTING_KEYS}
    assert written == [(e["key"], e["value"], e["value_kind"]) for e in entries]
    # 反向：型別不符時真的 L2 擋下、不呼叫 L1
    written.clear()
    bad = source.save_setting("hld_window_start", "2026/02/01", "date")
    assert bad["status"] == "kind_mismatch" and written == []


# ═══════════════════════════ 第 5 點：配息逐檔資料未備 ═══════════════════════════


def _div_table(*, settled, errors=None, rows=None):
    """L2 `build_nav_dividend_tables` 的 `dividend` 形狀（`assemble_live_load` R-18 讀的那幾個鍵）。"""
    return {"rows": copy.deepcopy(fixtures.dividends() if rows is None else rows), "errors": dict(errors or {}),
            "pending": {}, "withheld": {}, "skipped": {}, "fetched": {}, "skipped_rows": {}, "provenance": {},
            "settled": dict(settled)}


def _all_settled(**over):
    out = {code: True for code in A._CODES}
    out.update(over)
    return out


def test_第5點_一檔配息未確定_只有那一檔資料未備_它的部分列不進加總_其他檔照常():
    bad = A._MID_CODE
    # 未確定的那一檔照樣帶著部分配息列（L2 允許）—— 加總進去會得到偏低的數
    loaded = A._assemble(dividend_table=_div_table(settled=_all_settled(**{bad: False})))
    ds = loaded["dataset"]
    assert ds["pending_tables"] == ["fund_profile"]
    assert ds["dividend_not_ready"] == [bad]
    assert bad not in {r["fund_code"] for r in ds["dividend"]}
    assert {r["fund_code"] for r in ds["dividend"]} == set(A._CODES) - {bad}
    assert bad not in loaded["live_args"]["dividend_coverage"]
    model = A._build_model(loaded)
    hld3 = logic.find_block(model, "HLD-3")
    for group in hld3["fund_groups"]:
        texts = [mv["text"] for mv in group["main_values"]]
        if group["_fund_code"] == bad:
            assert texts == [logic.ND_TEXT, logic.ND_TEXT]
        else:
            assert logic.ND_TEXT not in texts, group["_fund_code"]
    hld8 = {r["_fund_code"]: r for r in logic.find_block(model, "HLD-8")["_rows"]}
    assert hld8[bad]["principal"]["text"] == logic.ND_TEXT
    assert all(hld8[c]["principal"]["text"] != logic.ND_TEXT for c in A._CODES if c != bad)


def test_第5點_代碼對照失敗的檔_也只標那一檔():
    bad = A._BAD_CODE
    key_results = [dict(r, ok=r["input"] != bad) for r in A._key_results(A._l2_holding_tables()["holding"])]
    table = A._nav_table(healthy=tuple(c for c in A._CODES if c != bad))
    for name in ("fetched", "skipped_rows", "provenance"):
        table[name].pop(bad, None)
    settled = {c: True for c in A._CODES if c != bad}
    rows = [r for r in fixtures.dividends() if r["fund_code"] != bad]
    loaded = A._assemble(key_results=key_results, nav_table=table,
                         dividend_table=_div_table(settled=settled, rows=rows))
    assert loaded["dataset"]["dividend_not_ready"] == [bad]
    assert loaded["dataset"]["pending_tables"] == ["fund_profile"]


def test_第5點_取數失敗那一支維持既有呈現_不算進資料未備():
    bad = A._OK_CODE
    loaded = A._assemble(dividend_table=_div_table(settled=_all_settled(**{bad: False}), errors={bad: "上游逾時"}))
    assert loaded["dataset"]["dividend_not_ready"] == []
    assert loaded["dataset"]["fund_errors"]["dividend"] == {bad: "上游逾時"}
    model = A._build_model(loaded)
    texts = [mv["text"] for g in logic.find_block(model, "HLD-3")["fund_groups"] if g["_fund_code"] == bad
             for mv in g["main_values"]]
    assert texts == [logic.ERR_TEXT, logic.ERR_TEXT]


def test_第5點_覆蓋閘門只標區間起點早於該檔最舊除息日的那一檔():
    rows = [r for r in fixtures.dividends() if not (r["fund_code"] == A._MID_CODE and r["ex_date"] < "2026-01-01")]
    loaded = A._assemble(dividend_table=_div_table(settled=_all_settled(), rows=rows))
    coverage = loaded["live_args"]["dividend_coverage"]
    assert coverage[A._MID_CODE] > A._WINDOW[0] and coverage[A._OK_CODE] <= A._WINDOW[0]
    gated = live._gate_dividend_coverage(loaded["dataset"], coverage)
    assert gated["dividend_not_ready"] == [A._MID_CODE]
    assert {r["fund_code"] for r in gated["dividend"]} == set(A._CODES) - {A._MID_CODE}
    model = A._build_model(loaded)
    for g in logic.find_block(model, "HLD-3")["fund_groups"]:
        texts = [mv["text"] for mv in g["main_values"]]
        assert (texts == [logic.ND_TEXT, logic.ND_TEXT]) is (g["_fund_code"] == A._MID_CODE), g["_fund_code"]


def test_第5點_門檻指標資料未備時_HLD1寫出dividend那一句():
    bad = A._MID_CODE
    rules = [{"indicator": "配息佔淨值比", "direction": "高於", "value": -1.0}]
    loaded = A._assemble(settings=A._settings(rules=rules),
                         dividend_table=_div_table(settled=_all_settled(**{bad: False})))
    hld1 = logic.find_block(A._build_model(loaded), "HLD-1")
    assert logic.empty_source_text(["dividend"]) in hld1["detail_lines"]
    assert {r["_fund_code"] for r in hld1["_rows"]} == set(A._CODES) - {bad}


@pytest.mark.parametrize("value, exc", [
    ("AAAA", TypeError),            # 字串會被拆成單字元
    ([""], TypeError),
    (["ZZZZ"], ValueError),         # 持倉以外的代碼
])
def test_第5點_dividend_not_ready形狀不對一律raise(value, exc):
    args = _rehomed_args()
    args["dataset"]["dividend_not_ready"] = value
    with pytest.raises(exc):
        logic.build_page_model(**args)


def test_第5點_示範模式沒有這個鍵_畫面一格不變():
    args = fixtures.scenario("full")
    assert "dividend_not_ready" not in args["dataset"]
    with_empty = copy.deepcopy(args)
    with_empty["dataset"]["dividend_not_ready"] = []
    assert logic.build_page_model(**args) == logic.build_page_model(**with_empty)


# ═══════════════════════════ 第 8 點：同鍵多列加總 ═══════════════════════════


def _split_first_holding(dataset, *, units=500.0, cost_orig=5000.0, cost_twd=150000, **diff):
    """把第一筆持倉拆成「同鍵兩列」：第二列 holding_id 不同、其餘欄同（`diff` 蓋掉幾欄）。"""
    first = dataset["holding"][0]
    second = dict(first, holding_id=first["holding_id"] + "-2", units_shares=units,
                  cost_orig_ccy=cost_orig, cost_twd=cost_twd, **diff)
    dataset["holding"].insert(1, second)
    return first, second


@pytest.mark.parametrize("mode", ["demo", "live"])
def test_第8點_同鍵兩列_HLD1到HLD5只剩一列_單位與成本為兩列之和(mode):
    args = _rehomed_args()
    args["dataset"]["user_setting"] = fixtures.user_settings(
        window=(fixtures.WINDOW_START, fixtures.WINDOW_END),
        rules=[{"indicator": "最大回撤", "direction": "低於", "value": 1.0}],   # 每一檔都列上偏離表
    )
    first, second = _split_first_holding(args["dataset"])
    want_units = first["units_shares"] + second["units_shares"]
    want_twd = first["cost_twd"] + second["cost_twd"]
    build = (lambda: logic.build_page_model(**args, open_fund=first["holding_id"])) if mode == "demo" else (
        lambda: _live(args["dataset"], open_fund=first["holding_id"]))
    model = build()
    codes = [h["fund_code"] for h in fixtures.holdings()]
    hld1 = logic.find_block(model, "HLD-1")
    assert sorted(r["_fund_code"] for r in hld1["_rows"]) == sorted(codes)
    for code in ("HLD-2", "HLD-3"):
        assert len(logic.find_block(model, code)["fund_groups"]) == len(codes), code
    items = logic.find_block(model, "HLD-5")["_items"]
    assert [i["_holding_id"] for i in items].count(first["holding_id"]) == 1
    assert second["holding_id"] not in [i["_holding_id"] for i in items]
    fields = dict(next(i for i in items if i["_holding_id"] == first["holding_id"])["_fields"])
    hint = logic.HINT if mode == "demo" else ""
    assert fields["單位數"] == f"{want_units:,.3f}{hint}"
    assert fields["成本（新臺幣）"] == f"{want_twd:,} 元{hint}"
    # 期間配息合計用的單位數也是兩列之和
    total = next(mv for g in logic.find_block(model, "HLD-3")["fund_groups"] if g["_fund_code"] == first["fund_code"]
                 for mv in g["main_values"] if mv["label"] == "期間配息合計")
    alone = logic.fund_metrics(args["dataset"], dict(first, units_shares=want_units),
                               (fixtures.WINDOW_START, fixtures.WINDOW_END))["期間配息合計"]
    assert total["_raw"] == pytest.approx(alone["_raw"])


def test_第8點_鍵只去前後空白_不改大小寫_不補0():
    rows = [
        {"holding_id": "1", "policy_id": "P1", "fund_code": "AB01", "units_shares": 1.0, "cost_orig_ccy": 1.0,
         "cost_twd": 1, "ccy": "USD", "fund_name": "某基金", "bucket": None, "opened_on": "2026-01-01",
         "last_synced_at": "x"},
    ]
    same = dict(rows[0], holding_id="2", policy_id=" P1 ", fund_code="AB01 ")
    case = dict(rows[0], holding_id="3", fund_code="ab01")
    zero = dict(rows[0], holding_id="4", fund_code="0AB01")
    merged = logic.merge_same_key_holdings(rows + [same, case, zero])
    assert [r["holding_id"] for r in merged] == ["1", "3", "4"]
    assert merged[0]["units_shares"] == 2.0 and merged[0]["cost_twd"] == 2


def test_第8點_名稱相同但鍵不同_不合併():
    args = _rehomed_args()
    first = args["dataset"]["holding"][0]
    other_policy = dict(first, holding_id="H-X", policy_id="P-OTHER")   # 名稱、代碼、幣別都相同，只有保單不同
    other_code = dict(first, holding_id="H-Y", fund_code="ZZZZ")         # 名稱相同、代碼不同
    merged = logic.merge_same_key_holdings(args["dataset"]["holding"] + [other_policy, other_code])
    assert len(merged) == len(args["dataset"]["holding"]) + 2
    assert {"H-X", "H-Y"} <= {r["holding_id"] for r in merged}


@pytest.mark.parametrize("column, value", [
    ("ccy", "EUR"), ("fund_name", "另一個名稱"), ("bucket", "別的類別"), ("opened_on", "2020-01-01"),
    ("last_synced_at", "2026-01-01T04:00:00Z"),
])
def test_第8點_同鍵但語意欄不同_不加總_raise(column, value):
    args = _rehomed_args()
    _split_first_holding(args["dataset"], **{column: value})
    with pytest.raises(ValueError, match=f"兩列的 {column} 不同"):
        logic.build_page_model(**args)


def test_第8點_第二列holding_id壞了_不因加總被蓋掉():
    args = _rehomed_args()
    _first, second = _split_first_holding(args["dataset"])
    second["holding_id"] = ""
    with pytest.raises(logic.HoldingIdError):
        logic.build_page_model(**args)


def test_第8點_沒有同鍵時_模型與輸入同一個dataset逐字相同():
    """示範假資料沒有同鍵兩列：加總是空操作（不換 dataset 物件、不改任何欄）。"""
    for name in fixtures.ALL_SCENARIO_NAMES:
        holding = fixtures.scenario(name)["dataset"].get("holding") or []
        assert logic.merge_same_key_holdings(holding) == holding, name


def test_第8點_ALO同鍵兩列幣別不同_不加總_raise():
    from ui_v2.alo import logic as alo_logic

    row = {"holding_id": "P1|A|1", "policy_id": "P1", "fund_code": "A", "units_shares": 1.0, "cost_orig_ccy": 10.0,
           "cost_twd": 300, "ccy": "USD", "bucket": "核心"}
    ds = {"holding": [row, dict(row, holding_id="P1|A|2", ccy="EUR")]}
    with pytest.raises(ValueError, match="兩列的 ccy 不同"):
        alo_logic.aggregated_holdings(ds)
    same = {"holding": [row, dict(row, holding_id="P1|A|2")]}
    (merged,) = alo_logic.aggregated_holdings(same)
    assert (merged["units_shares"], merged["cost_orig_ccy"], merged["cost_twd"]) == (2.0, 20.0, 600)


def test_第8點_正式模式_同鍵不同語意_page畫錯誤畫面的那一個例外():
    """正式模式 `build_live_model` 往外拋 ValueError —— `page.render` 的 try 接住、畫既有錯誤畫面（slow 檔驗畫面）。"""
    args = _rehomed_args()
    _split_first_holding(args["dataset"], ccy="EUR")
    with pytest.raises(ValueError, match="同鍵不同語意，不加總"):
        _live(args["dataset"])


def test_第8點_source加真的L2組表_同鍵兩列端到端只剩一列():
    """`alo_holdings.build_alo_tables`（真 L2，保單分頁同鍵兩列 → 兩筆 `holding`，id 為 `|1`、`|2`）
    → `live.assemble_live_load` → `live.build_live_model`：HLD-5 只剩一列、單位數與成本為兩列之和。"""
    pytest.importorskip("pandas")
    from services.v2_tables import alo_holdings as AH

    def prow(row, units, invest):
        return {"policy_id": "PX-1", "fund_code": "ZZ01", "fund_name": "測試基金甲", "currency": "USD",
                "tier": "core", "invest_twd": invest, "div_cash_pct": 100.0, "units": units, "avg_nav": 10.0,
                "avg_fx": 30.0, "_tab": "PX-1", "_row": row}

    supp = {"_row": 2, "_raw": ("PX-1", "ZZ01", "2001-01-01", "2001-02-03", "類別甲"), "policy_id": "PX-1",
            "fund_code": "ZZ01", "opened_on": "2001-01-01", "last_checked_on": "2001-02-03", "bucket": "類別甲"}
    prof = {"_row": 2, "_raw": ("PX-1", "保單甲", "某人壽", "USD", "1", "2001-01-01", "active"), "policy_id": "PX-1",
            "policy_name": "保單甲", "issuer": "某人壽", "ccy": "USD", "premium_paid_twd": 1, "opened_on": "2001-01-01",
            "status": "active"}
    tabs = {AH.TAB_SUPPLEMENT: {"records": [supp], "bad_rows": [], "blank_rows": 0, "tab_missing": False},
            AH.TAB_PROFILE: {"records": [prof], "bad_rows": [], "blank_rows": 0, "tab_missing": False}}
    tables = AH.build_alo_tables([prow(2, 1000.0, 300000), prow(3, 500.0, 150000)], tabs)
    assert [h["holding_id"] for h in tables["holding"]] == ["PX-1|ZZ01|1", "PX-1|ZZ01|2"]
    keys = [{"input": "ZZ01", "ok": True, "full_key": "FK", "portal": "", "parsed_code": "ZZ01",
             "mapping_hit": True, "error": None}]
    nav_table = {"rows": [], "errors": {}, "withheld": {}, "skipped": {}, "fetched": {"ZZ01": 0},
                 "skipped_rows": {}, "provenance": {}}
    loaded = live.assemble_live_load(**A._kwargs(holding_tables=tables, key_results=keys, nav_table=nav_table))
    model = live.build_live_model(loaded["dataset"], open_fund="PX-1|ZZ01|1", today=_TODAY, **loaded["live_args"])
    items = logic.find_block(model, "HLD-5")["_items"]
    assert [i["_holding_id"] for i in items] == ["PX-1|ZZ01|1"]
    fields = dict(items[0]["_fields"])
    assert fields["單位數"] == f"{1500.0:,.3f}"
    assert fields["成本（新臺幣）"] == f"{450000:,} 元"


# ═══════════ 總管 2026-10-16 判定（必修）：設定讀取失敗時「存檔」停用，免得空白欄位覆蓋已存值 ═══════════


def _settings_failed_dataset():
    args = _rehomed_args()
    args["dataset"]["user_setting"] = []
    args["dataset"]["errors"] = {"user_setting": "ConnectionError: 設定表讀取逾時（測試用原文）"}
    return args["dataset"]


@pytest.mark.parametrize("fields", [
    None,                                                            # 首次渲染：欄位空白
    {"window_start": "2026-02-01", "window_end": "2026-09-19"},      # 使用者自己填了合格的值，照樣不開放
])
def test_總管判定_設定讀取失敗_存檔停用_原因句(fields):
    model = _live(_settings_failed_dataset(), fields=fields)
    save = next(b for b in logic.find_block(model, "HLD-4")["buttons"] if b["_action_kind"] == "存檔")
    assert (save["_enabled"], save["disabled_reason"]) == (False, live.SAVE_BLOCKED_READ_FAILED_REASON)
    # 正控：設定讀得到、同一組欄位值時，存檔是開的
    ok = _live(_rehomed_args()["dataset"], fields={"window_start": "2026-02-01", "window_end": "2026-09-19"})
    assert next(b for b in logic.find_block(ok, "HLD-4")["buttons"] if b["_action_kind"] == "存檔")["_enabled"]


def test_總管判定_設定讀取失敗的原因句_禁詞零命中():
    banned = [chr(0x4e00) + chr(0x9375), chr(0x6700) + chr(0x4f73), chr(0x63a8) + chr(0x85a6),
              chr(0x6700) + chr(0x9069), chr(0x8cb7) + chr(0x9032), chr(0x8ce3) + chr(0x51fa),
              chr(0x52a0) + chr(0x78bc), chr(0x6e1b) + chr(0x78bc)]
    assert not [w for w in banned if w in live.SAVE_BLOCKED_READ_FAILED_REASON]
