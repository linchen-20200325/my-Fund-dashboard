# -*- coding: utf-8 -*-
"""exp 頁 C2 接線（基本資料、淨值、配息比）的純函式測試（fast lane；不需要 streamlit、不打網路）。

客戶已裁示的規則（派工單編號）逐條各有測試：1 缺欄照列／無法判定、2 代碼欄第一欄、3 幣別出處標示、
5 經理費率留空、8 取數失敗 ⛔、10 來源標示（不加欄）、11 舊淨值 10 天門檻、12 部分來源失敗、
13 近 12 個月無配息、14 幣別衝突；另有配息比窗口邊界、遮蔽、`ccy_undetermined`、契約守衛。
L2 形狀的假資料住在 `_exp_wired_fixture.py`；形狀與真 L2 一致與否，由檔尾的契約測試（走真的 L2）釘住。
"""

from __future__ import annotations

import html
import pathlib
import sys
from datetime import date

import pytest

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parents[1]))
sys.path.insert(0, str(_HERE))

import _exp_wired_fixture as F  # noqa: E402
from ui_v2 import thresholds  # noqa: E402
from ui_v2.exp import live, logic  # noqa: E402

_ALL = ({"field": "fund_code", "op": "不等於", "value": "ZZZ"},)


def _settings(rules=_ALL, columns=logic.COLUMN_ORDER, sort=None):
    return {live.KEY_RULES: None if rules is None else tuple(rules),
            live.KEY_COLUMNS: None if columns is None else tuple(columns),
            live.KEY_SORT: sort, live.KEY_WATCH: None}


def _keys(codes=F.CODES):
    return [{"input": c, "ok": True, "full_key": c, "portal": "", "parsed_code": c, "error": None} for c in codes]


def _wired(*, profiles=None, nav_out=None, codes=F.CODES, unresolved=None, today=F.TODAY, mask=F.mask):
    return F.assemble(profiles or F.profiles(codes=codes), codes, nav_out, unresolved=unresolved, today=today,
                      mask_=mask)


def _model(wired=None, settings=None, compare=(), **kw):
    wired = wired or _wired()
    settings = settings or _settings()
    pool = {"status": "ok", "backend": "x", "codes": [r["fund_code"] for r in wired["fund_profile"]],
            "dropped_blank": 0, "duplicates": 0, "message": None}
    inputs = {"dataset": live.build_dataset(pool, settings, wired),
              "notes": {"pool": pool, "settings": settings, "settings_error": None, "cells": wired["cells"]}}
    return live.build_live_model(inputs, compare_checked=compare, save_wired=True, **kw)


def _row(model, code):
    return logic.find_row(logic.find_block(model, "EXP-2"), code)


def _cell(model, code, column):
    return _row(model, code)["_cells"][column]


# ═════════════════════ 鏡像常數對拍 ═════════════════════


def test_門檻只有一個出處_文字與資產配置頁逐字相同():
    from ui_v2.alo import logic as alo_logic
    from ui_v2.hld import live as hld_live

    assert live.NAV_OLD_DAYS is thresholds.NAV_NOT_READY_DAYS == 10 and live.thresholds is thresholds
    assert live.NAV_NOT_READY_DATED_TEXT == alo_logic.NAV_NOT_READY_DATED_TEXT
    assert live.NAV_NOT_READY_DATED_TEXT.endswith(hld_live.NAV_NOTE_NOT_READY.replace("{limit}", "{days}"))
    source = (_HERE.parents[1] / "ui_v2" / "exp" / "live.py").read_text(encoding="utf-8")
    assert "NAV_OLD_DAYS = thresholds.NAV_NOT_READY_DAYS" in source
    assert "> 10" not in source and ">= 11" not in source       # 不另寫 10


def test_L2狀態字面與本檔鏡像相同():
    exp_profile = pytest.importorskip("services.v2_tables.exp_profile")
    exp_nav = pytest.importorskip("services.v2_tables.exp_nav")
    nav_dividend = pytest.importorskip("services.v2_tables.nav_dividend")
    assert live.PROFILE_STATUS_OK == exp_profile.STATUS_OK
    assert live.PROFILE_STATUS_NOT_READY == exp_profile.STATUS_NOT_READY
    assert live.PROFILE_STATUS_FAILED == exp_profile.STATUS_FAILED
    assert live.PROFILE_STATUS_INCONSISTENT == exp_profile.STATUS_INCONSISTENT
    assert live.TEXT_KEY_FAILED == exp_profile.TEXT_KEY_FAILED
    assert live.PROFILE_COLUMNS == exp_profile.CELL_FIELDS
    assert F.TEXT_MGMT_FEE == exp_profile.TEXT_MGMT_FEE
    assert F.TEXT_CCY_UNDETERMINED == exp_nav.TEXT_CCY_UNDETERMINED          # 假資料的 L2 原文
    assert live.DIVIDEND_POLICY_ACCUM == exp_profile.DIVIDEND_POLICY_ACCUM
    assert F.DIV_CCY_DIFFERS == nav_dividend.WITHHELD_DIV_CCY_DIFFERS
    assert F.TEXT_DIV_NONE == nav_dividend.TEXT_DIV_NONE
    assert set(F.WITHHELD_TEXTS) == {nav_dividend.WITHHELD_CCY_MISSING, nav_dividend.WITHHELD_CCY_CONFLICT,
                                     nav_dividend.WITHHELD_FETCHED_AT_MISSING,
                                     nav_dividend.WITHHELD_FETCHED_AT_FUTURE, exp_nav.WITHHELD_CCY_UNDETERMINED}
    assert F.INPUT_CONFLICT == nav_dividend.WITHHELD_INPUT_CONFLICT


# ═════════════════════ 規則 1、2、3、5、8、10、12：基本資料 ═════════════════════


def test_規則2_代碼欄固定第一欄():
    block = logic.find_block(_model(), "EXP-2")
    assert block["column_keys"][0] == logic.CODE_COLUMN
    assert block["column_keys"][1:] == logic.COLUMN_ORDER          # 沒有新增欄位（規則 10）


def test_規則1_基本資料缺值_基金照列_該格寫資料未備與原因():
    model = _model()
    assert [r["_fund_code"] for r in logic.find_block(model, "EXP-2")["_rows"]] == sorted(F.CODES)
    node = _cell(model, "F06", "ccy")
    assert node["text"].startswith(logic.ND_TEXT + "：各來源幣別不一致") and node["_state"] == logic.STATE_MISSING


def test_規則1_條件用到缺值欄位_無法判定_不算符合不排除():
    rules = ({"field": "inception_on", "op": "晚於", "value": "2000-01-01"},)
    model = _model(settings=_settings(rules=rules))
    codes = [r["_fund_code"] for r in logic.find_block(model, "EXP-2")["_rows"]]
    assert "D04" in codes and "G07" in codes                                  # 不排除
    judge = _cell(model, "D04", logic.JUDGE_COLUMN)
    assert judge["text"] == "⬜ 無法判定（資料未備：inception_on）"
    lamp = logic.find_block(model, "EXP-0")
    assert lamp["_tone_override"] != "紅"                                     # 不亮紅燈


def test_規則3與10_幣別值旁掛來源標示_tooltip寫來源自報():
    node = _cell(_model(), "A01", "ccy")
    assert node["text"] == "USD" and node["source_tag"] == "MoneyDJ+TDCC"
    assert node["source_tip"] == "計價幣別出處（來源自報）：MoneyDJ+TDCC"


def test_規則5_經理費率留空_原因是不以最高經理費代替():
    model = _model(compare=("A01",))
    exp6 = logic.find_block(model, "EXP-6")
    fee = exp6["_fields"][[k for k, _ in logic.EXP6_FIELDS].index("mgmt_fee_rate_pct")]
    assert fee["text"] == f"{logic.ND_TEXT}：{F.TEXT_MGMT_FEE}"
    cmp_cell = logic.find_block(model, "EXP-3")["_columns"][0]["_cells"]["mgmt_fee_rate_pct"]
    assert cmp_cell["text"] == fee["text"]


def test_規則8_基本資料取數失敗_紅色禁止號():
    node = _cell(_model(), "G07", "fund_name")
    assert node["text"] == "⛔ 取數失敗：MoneyDJ 取數失敗" and node["_state"] == logic.STATE_ERROR
    assert node["_tone"] == "紅" and node["source_tag"] == "MoneyDJ 失敗"


def test_規則12_部分來源失敗_顯示一致的值_標示失敗來源與原因():
    node = _cell(_model(), "D04", "ccy")
    assert node["text"] == "USD" and node["_state"] == logic.STATE_OK
    assert node["source_tag"] == "MoneyDJ+TDCC · FundClear 失敗"
    assert "取數失敗的來源：FundClear" in node["source_tip"] and "HTTP 503" in node["source_tip"]
    assert "FundClear" not in node["source_tag"].split(" · ")[0]              # 失敗來源不算一致證據


def test_profile_cell_note_未知狀態與缺原因一律raise():
    with pytest.raises(ValueError):
        live.profile_cell_note("ccy", F.cell(None, "weird", reason="x"))
    with pytest.raises(ValueError):
        live.profile_cell_note("ccy", F.cell(None, "not_ready", reason=None))


# ═════════════════════ 規則 11：舊淨值 ═════════════════════


def test_規則11_剛好10天不算舊_11天算舊():
    assert live.nav_is_old(date(2026, 10, 4), F.TODAY) is False
    assert live.nav_is_old(date(2026, 10, 3), F.TODAY) is True
    with pytest.raises(ValueError):
        live.nav_is_old(date(2026, 10, 15), F.TODAY)


def test_規則11_舊淨值三格寫實際日期_不交給計算():
    wired = _wired()
    model = _model(wired)
    text = "⬜ 資料未備：最近一筆淨值 2026-10-03，已超過 10 日"
    for column in live.NAV_COLUMNS:
        assert _cell(model, "C03", column)["text"] == text
    assert all(r["fund_code"] != "C03" for r in wired["nav"])               # 不進 dataset → 不參與排序與任何計算
    assert "C03" not in wired["div_ratio_pct"]                               # 配息比不計算
    assert _cell(model, "B02", "nav_date")["text"] == "2026-10-04"            # 10 天照用


def test_規則11_依淨值排序時舊淨值不參與():
    model = _model(settings=_settings(sort="nav_orig_ccy"))
    order = [r["_fund_code"] for r in logic.find_block(model, "EXP-2")["_rows"]]
    usable = [c for c in order if _cell(model, c, "nav_orig_ccy")["_state"] == logic.STATE_OK]
    assert order[:len(usable)] == usable and "C03" not in usable


# ═════════════════════ 規則 13、14 與配息比 ═════════════════════


def test_配息比算式_窗口內合計除以最新淨值():
    model = _model()
    assert _cell(model, "A01", "div_ratio_pct")["text"] == "6.00%"
    wired = _wired()
    assert wired["div_ratio_pct"]["A01"] == pytest.approx(6.0)
    assert wired["div_ratio_pct"]["H08"] == pytest.approx(2.5)
    tip = _cell(model, "A01", "div_ratio_pct")["source_tip"]
    assert "2025-10-10（不含）至 2026-10-10 之間的配息共 12 筆" in tip
    assert _cell(model, "A01", "div_ratio_pct")["source_tag"] == live.TAG_RATIO


def _ratio(rows, *, nav_day=date(2026, 10, 10), settled=True, coverage=date(2020, 1, 1), nav=10.0, ccy="USD",
           accum=False):
    return live.dividend_ratio(nav, ccy, nav_day, rows, settled=settled, coverage_start=coverage,
                               accum_confirmed=accum)


def _d(day, amount=0.1, ccy="USD"):
    return {"ex_date": day, "div_per_unit_orig_ccy": amount, "ccy": ccy}


def test_配息比窗口邊界_剛好12個月前那天不含_最新日含():
    kind, ratio, _ = _ratio([_d(date(2025, 10, 10), 5.0), _d(date(2026, 10, 10), 0.1)])
    assert kind == "ok" and ratio == pytest.approx(1.0)                      # 只算 2026-10-10 那一筆
    kind, ratio, _ = _ratio([_d(date(2025, 10, 11), 0.2)])
    assert kind == "ok" and ratio == pytest.approx(2.0)                      # 起點隔天算進來
    kind, _r, _ = _ratio([_d(date(2026, 10, 11), 0.2)], coverage=date(2020, 1, 1))
    assert kind == "none"                                                     # 晚於最新淨值日不算


def test_配息比窗口_閏日往前一年是2月28日():
    assert live.window_start(date(2028, 2, 29)) == date(2027, 2, 28)
    assert live.window_start(date(2026, 10, 10)) == date(2025, 10, 10)


def test_規則13_有配息列且覆蓋成立_窗口內無配息_不適用_不是0也不是資料未備():
    kind, ratio, _ = _ratio([_d(date(2024, 1, 1))])                          # 有配息列、但都在窗口外
    assert (kind, ratio) == ("none", None)
    kind, ratio, _ = _ratio([_d(date(2026, 5, 1), 0.0)])                     # 窗口內合計為 0
    assert (kind, ratio) == ("none", None)


def test_配息比前提不成立_資料未備():
    assert _ratio([_d(date(2026, 5, 1))], settled=False)[0] == "not_ready"
    kind, _r, why = _ratio([_d(date(2026, 5, 1))], coverage=date(2026, 5, 1))     # 覆蓋起點晚於窗口起點
    assert kind == "not_ready" and "未涵蓋近 12 個月" in why
    kind, _r, why = _ratio([_d(date(2026, 5, 1), ccy="TWD")])                    # 配息幣別與淨值幣別不同
    assert kind == "ccy_differs" and "TWD" in why                               # `49` Q7：不適用（另一條測試）
    node = _cell(_model(), "D04", "div_ratio_pct")
    assert node["text"].startswith(logic.ND_TEXT + "：配息資料未確認完整")


def test_覆蓋起點剛好等於窗口起點_成立():
    kind, ratio, _ = _ratio([_d(date(2025, 10, 10), 9.0), _d(date(2026, 1, 1), 0.3)], coverage=date(2025, 10, 10))
    assert kind == "ok" and ratio == pytest.approx(3.0)


def test_規則14_淨值與基本資料幣別衝突_保留基本資料幣別_三格資料未備():
    model = _model()
    assert _cell(model, "E05", "ccy")["text"] == "USD"
    for column in live.NAV_COLUMNS:
        node = _cell(model, "E05", column)
        assert node["text"] == f"{logic.ND_TEXT}：{live.plain_reason(F.CONFLICT_LINE)}"
        assert "即時序列 宣告「EUR」" in node["text"]
    assert "E05" not in _wired()["div_ratio_pct"]


def test_規則14_資料層之外再擋一次_淨值列幣別與基本資料不同():
    out = F.nav_out(("A01",))
    for row in out["nav"]["rows"]:
        row["ccy"] = "EUR"
    wired = _wired(nav_out=out, codes=("A01",), profiles=F.profiles(codes=("A01",)))
    assert wired["nav"] == [] and "A01" not in wired["div_ratio_pct"]
    assert wired["cells"]["A01"]["nav_date"]["text"] == (
        f"{logic.ND_TEXT}：淨值資料幣別 EUR 與基本資料幣別 USD 不同，淨值與配息比不計算")


# ═════════════════════ ccy_undetermined、代碼無法對照、扣下代碼 ═════════════════════


def test_幣別未確定_傳None給資料層_畫面寫資料層的固定文字():
    prof = F.profiles()
    funds, unresolved = live.nav_requests(["F06", "A01"], _keys(), prof["declared"])
    assert unresolved == {}
    f06 = next(f for f in funds if f["fund_code"] == "F06")
    assert f06["declared_ccy"] is None and f06["declared_ccy_source"] is None
    assert next(f for f in funds if f["fund_code"] == "A01")["declared_ccy_source"] == "meta:MoneyDJ+TDCC"
    assert _cell(_model(), "F06", "nav_date")["text"] == f"{logic.ND_TEXT}：{live.TEXT_CCY_UNDETERMINED}"


def test_代碼無法對照_不取淨值_三格寫原因():
    keys = _keys()
    keys[0] = {"input": "A01", "ok": False, "full_key": None, "portal": None, "parsed_code": None,
               "error": "查無對照"}
    funds, unresolved = live.nav_requests(["A01", "B02"], keys, F.profiles()["declared"])
    assert [f["fund_code"] for f in funds] == ["B02"]
    assert unresolved == {"A01": "代碼無法對照：查無對照"}


def test_未登記的扣下代碼與輸入矛盾_raise():
    out = F.nav_out(("A01",))
    out["nav"]["withheld"]["A01"] = "something_new"
    with pytest.raises(ValueError, match="未登記"):
        _wired(nav_out=out, codes=("A01",), profiles=F.profiles(codes=("A01",)))
    out["nav"]["withheld"]["A01"] = F.INPUT_CONFLICT
    with pytest.raises(ValueError):
        _wired(nav_out=out, codes=("A01",), profiles=F.profiles(codes=("A01",)))


def test_規則8_淨值取數失敗_紅色禁止號():
    node = _cell(_model(), "G07", "nav_orig_ccy")
    assert node["text"].startswith("⛔ 取數失敗：") and node["_state"] == logic.STATE_ERROR


# ═════════════════════ 遮蔽、escape ═════════════════════


def test_每一格的原因與tooltip都經過遮蔽():
    wired = _wired()
    flat = [v for notes in wired["cells"].values() for n in notes.values()
            for v in (n["text"], n["source_tag"], n["source_tip"]) if v]
    assert flat and not any(F.SECRET in v for v in flat)
    assert any("‹已遮蔽›" in v for v in flat)
    with pytest.raises(TypeError):
        live.assemble_wired(F.profiles(), [], None, unresolved={}, today=F.TODAY, mask=None,
                            withheld_texts=F.WITHHELD_TEXTS, input_conflict=F.INPUT_CONFLICT)


def test_mask回傳非字串_raise():
    with pytest.raises(TypeError):
        _wired(mask=lambda text: None)


def test_today只收date():
    from datetime import datetime

    with pytest.raises(TypeError):
        _wired(today=datetime(2026, 10, 14))


def test_XSS_值與tooltip在畫面層一律escape():
    st = pytest.importorskip("streamlit")  # noqa: F841 —— page.py 要 import streamlit
    from ui_v2.exp import page

    node = {"text": F.XSS_NAME, "source_tag": F.XSS_SOURCE, "source_tip": 'a"b<script>x</script>'}
    title = page._title_attr(node)
    assert title == ' title="a&#34;b&#60;script&#62;x&#60;/script&#62;"'
    assert page._src_html(node) == '<span class="exp-src">Evil&#34;Src&#60;b&#62;</span>'
    assert page._title_attr({"source_tip": None}) == "" and page._src_html({}) == ""
    assert html.unescape(title[len(' title="'):-1]) == node["source_tip"]


# ═════════════════════ 取數名單、畫面調整的契約 ═════════════════════


def test_淨值只取EXP2會列出的檔():
    rows = F.profiles()["rows"]
    assert live.nav_codes_needed(rows, _settings(rules=None), None) == []
    assert live.nav_codes_needed(rows, _settings(), "讀不到") == []
    rules = ({"field": "fund_code", "op": "等於", "value": "A01"},)
    assert live.nav_codes_needed(rows, _settings(rules=rules), None) == ["A01"]
    rules = ({"field": "inception_on", "op": "晚於", "value": "2000-01-01"},)  # D04 缺值 → 無法判定，照列、照取
    assert "D04" in live.nav_codes_needed(rows, _settings(rules=rules), None)


def test_畫面調整_有值卻說不可用_或缺格卻說可用_raise():
    wired = _wired()
    wired["cells"]["A01"]["fund_name"] = live._note("⬜ 資料未備：x", logic.STATE_MISSING)
    with pytest.raises(ValueError, match="有值"):
        _model(wired)
    wired = _wired()
    wired["cells"]["C03"]["nav_date"] = live._note(None, logic.STATE_OK)
    with pytest.raises(ValueError, match="缺格"):
        _model(wired)
    wired = _wired()
    del wired["cells"]["A01"]["ccy"]
    with pytest.raises(ValueError, match="沒有原因紀錄"):
        _model(wired)


def test_沒有接線結果時_只有測試替身標記才走舊路():
    pool = {"status": "ok", "backend": "x", "codes": ["A01"], "dropped_blank": 0, "duplicates": 0, "message": None}
    data = live.build_dataset(pool, _settings())
    assert data["fund_profile"] == [live._profile_row("A01")] and data["nav"] == [] and data["div_ratio_pct"] == {}
    notes = {"pool": pool, "settings": _settings(), "settings_error": None}
    with pytest.raises(ValueError, match="正式入口一定要交接線結果"):          # Q O3：正式入口不得靜默走舊路
        live.build_live_model({"dataset": data, "notes": notes}, save_wired=True)
    notes[live.UNWIRED_FOR_TESTS] = True
    model = live.build_live_model({"dataset": data, "notes": notes}, save_wired=True)
    assert _cell(model, "A01", "ccy")["text"] == live.missing_text("ccy")


def test_代碼對照表讀不到_整批取數失敗():
    pool = {"status": "ok", "backend": "x", "codes": ["A01"], "dropped_blank": 0, "duplicates": 0, "message": None}
    data = live.build_dataset(pool, _settings(), live.wiring_failed("代碼對照表讀取失敗：OSError: x"))
    assert data["fund_profile"] == [] and data["errors"] == {"fund_profile": "代碼對照表讀取失敗：OSError: x"}


# ═════════════════════ 契約：走真的 L2（注入 L1 替身） ═════════════════════


def test_契約_真的exp_profile與exp_nav_輸出接得上assemble_wired():
    """`exp_profile.build_profiles`（注入三支 L1 替身）＋ `exp_nav.load_nav_dividend`（注入 A 鏈替身）→ 本檔。
    只驗形狀接得上與幾個關鍵格；L2 本身的規則由 L2 的測試守。"""
    exp_profile = pytest.importorskip("services.v2_tables.exp_profile")
    exp_nav = pytest.importorskip("services.v2_tables.exp_nav")
    nav_dividend = pytest.importorskip("services.v2_tables.nav_dividend")
    pd = pytest.importorskip("pandas")
    from datetime import datetime, timezone  # noqa: F811

    dp = pytest.importorskip("repositories.fund.declared_profile")

    def mdj(full_key):
        # ~~刻意回 not_listed 避開 #967 舊 binding 形狀~~ → 2026-10-14 #967 合併後（有意識的更正，不是漏刪）：
        # 改回 ok 形狀；`method` 取 L1 公開常數 `MONEYDJ_BINDING_METHOD`，其餘四欄照 L2 `_bound` 的要求
        # （identity_confirmed is True、兩個張數為 int 1、name_nonempty is True）。not_listed 另有一條測試。
        return {"status": "ok", "fields": {"基金名稱": f"基金{full_key}", "計價幣別": "美元", "配息頻率": "月配",
                                           "成立日期": "2010/01/15"},
                "binding": {"method": dp.MONEYDJ_BINDING_METHOD, "identity_confirmed": True,
                            "name_table_count": 1, "populated_name_table_count": 1, "name_nonempty": True},
                "fetched_at": "2026-10-14T01:00:00+00:00"}

    def tdcc(full_key):
        return {"status": "ok", "fields": {"計價幣別": "美元"}, "fetched_at": None, "observed_at": "2026-10-14"}

    def fundclear(full_key):
        if full_key == "K02":
            raise RuntimeError(f"HTTP 503 token={F.SECRET}")
        return {"status": "ok", "fields": {"currency": "USD"}, "fetched_at": "2026-10-14T01:00:00+00:00"}

    keys = _keys(("K01", "K02"))
    profiles = exp_profile.build_profiles(keys, fetchers={"MoneyDJ": mdj, "TDCC": tdcc, "FundClear": fundclear},
                                          now=datetime(2026, 10, 14, 2, 0, tzinfo=timezone.utc))
    assert profiles["declared"]["K01"] == ("USD", "meta:MoneyDJ+TDCC+FundClear")
    assert profiles["declared"]["K02"] == ("USD", "meta:MoneyDJ+TDCC")      # 部分失敗、其餘一致（規則 12）
    assert profiles["rows"][0]["fund_name"] == "基金K01"                    # 身分判準通過（MoneyDJ 欄有值）

    def chain(chain_code, full_key):
        days = pd.date_range("2026-09-01", "2026-10-09", freq="B")
        attrs = {"source": "FundClear:GetFundNAV", "fetched_at": "2026-10-14T00:00:00+00:00", "currency": "USD"}
        res = {"full_key": full_key, "series": pd.Series([10.0] * len(days), index=days), "dividends": [],
               "data_source": "FundClear", "chain_started_at": "2026-10-14T00:00:00+00:00"}
        res["series"].attrs.update(attrs)
        series, error = nav_dividend._nav_from_chain(res, "yp010000", chain_code, full_key)
        return series, error, nav_dividend._div_from_chain(res, full_key)

    exp_nav.clear_memo()
    try:
        funds, unresolved = live.nav_requests(["K01", "K02"], keys, profiles["declared"])
        out = exp_nav.load_nav_dividend(funds, now=datetime(2026, 10, 14, 2, 0, tzinfo=timezone.utc),
                                        chain_fetch=chain)
    finally:
        exp_nav.clear_memo()
    secret_mask = lambda text: text.replace(F.SECRET, "‹已遮蔽›")  # noqa: E731
    withheld = {nav_dividend.WITHHELD_CCY_MISSING: None, nav_dividend.WITHHELD_CCY_CONFLICT: None,
                nav_dividend.WITHHELD_FETCHED_AT_MISSING: None, nav_dividend.WITHHELD_FETCHED_AT_FUTURE: None,
                exp_nav.WITHHELD_CCY_UNDETERMINED: exp_nav.TEXT_CCY_UNDETERMINED}
    wired = live.assemble_wired(profiles, ["K01", "K02"], out, unresolved=unresolved, today=date(2026, 10, 14),
                                mask=secret_mask, withheld_texts=withheld,
                                input_conflict=nav_dividend.WITHHELD_INPUT_CONFLICT,
                                div_ccy_differs=nav_dividend.WITHHELD_DIV_CCY_DIFFERS)
    assert [r["fund_code"] for r in wired["nav"]] == ["K01", "K02"]
    assert wired["nav"][0]["nav_date"] == "2026-10-09" and wired["nav"][0]["ccy"] == "USD"
    k02 = wired["cells"]["K02"]["ccy"]
    assert k02["text"] is None and "FundClear 失敗" in k02["source_tag"]
    assert F.SECRET not in k02["source_tip"] and "‹已遮蔽›" in k02["source_tip"]
    ratio = wired["cells"]["K01"]["div_ratio_pct"]
    assert ratio["text"].startswith(logic.ND_TEXT)                          # 沒有配息證據 → 不算、不是 0
    model = _model(wired, settings=_settings())
    assert _cell(model, "K01", "nav_orig_ccy")["text"] == "10.0000 USD"


# ═════════════════════ 2026-10-14 修正輪 ═════════════════════


def _all_strings(wired):
    return [v for notes in wired["cells"].values() for n in notes.values()
            for v in (n["text"], n["source_tag"], n["source_tip"]) if v]


def test_規則13_無配息列_配息政策已確認為累積型_不適用_標示不是計算():
    node = _cell(_model(), "B02", "div_ratio_pct")
    assert node["text"] == "⬜ 不適用：近 12 個月無配息" and node["_state"] == logic.STATE_BIZ
    assert node["source_tag"] == live.TAG_DIV_REPORTED and node["source_tag"] != live.TAG_RATIO
    # ~~頁型被刪掉的寫法~~ → 合併修正輪 B1：頁型保留成「（頁面 …）」
    assert ("配息依據：FundClear（頁面 yp010000）：沒有配息紀錄；合庫配息頁（頁面 yp010000）：沒有配息紀錄"
            in node["source_tip"])
    assert "empty" not in node["source_tip"] and "[yp" not in node["source_tip"]


def test_規則13_無配息列_配息政策為配息型_資料未備_保留期無法確認():
    node = _cell(_model(), "I09", "div_ratio_pct")
    assert node["text"] == f"{logic.ND_TEXT}：{live.TEXT_DIV_NONE_UNVERIFIED}"
    assert node["_state"] == logic.STATE_MISSING and node["source_tag"] != live.TAG_RATIO
    assert "配息依據：" in node["source_tip"]


@pytest.mark.parametrize("policy", [F.cell("dist"), F.cell(None, "not_ready", reason="配息頻率「不定期」依對照表不判定配息方式"),
                                    F.cell(None, "fetch_failed", failed=("MoneyDJ",), reason="MoneyDJ 取數失敗")])
def test_規則13_無配息列_配息政策不是已確認的累積型_一律資料未備(policy):
    overrides = F.default_overrides()
    overrides["B02"] = {"dividend_policy": policy}
    wired = _wired(profiles=F.profiles(overrides, codes=("B02",)), codes=("B02",))
    assert wired["cells"]["B02"]["div_ratio_pct"]["text"] == f"{logic.ND_TEXT}：{live.TEXT_DIV_NONE_UNVERIFIED}"


def test_dividend_ratio_無配息列_只看累積型旗標():
    assert _ratio([], accum=True)[0] == "none"
    kind, _r, why = _ratio([], accum=False)
    assert kind == "not_ready" and why == live.TEXT_DIV_NONE_UNVERIFIED


def test_Q7_配息幣別與淨值幣別不同_不適用():
    node = _cell(_model(), "J10", "div_ratio_pct")
    assert node["text"] == "⬜ 不適用：配息幣別與淨值幣別不同" and node["_state"] == logic.STATE_BIZ


def test_Q7_配息幣別認不出_維持資料未備():
    out = F.nav_out(("A01",))
    out["dividend"]["withheld"]["A01"] = "ccy_conflict"
    out["dividend"]["skipped"]["A01"] = [F.DIV_CCY_CONFLICT_LINE]
    out["dividend"]["rows"] = []
    wired = _wired(nav_out=out, codes=("A01",))
    text = wired["cells"]["A01"]["div_ratio_pct"]["text"]
    assert text.startswith(logic.ND_TEXT + "：") and "不適用" not in text


def test_Q7_本層再擋一次_窗口內配息幣別不同也是不適用():
    out = F.nav_out(("A01",))
    for row in out["dividend"]["rows"]:
        row["ccy"] = "EUR"
    wired = _wired(nav_out=out, codes=("A01",))
    assert wired["cells"]["A01"]["div_ratio_pct"]["text"] == live.TEXT_DIV_CCY_DIFFERS_NA


def test_幣別未確定_畫面不寫內部名稱():
    text = _cell(_model(), "F06", "nav_date")["text"]
    assert text == f"{logic.ND_TEXT}：計價幣別未確定（基本資料各來源幣別缺或不一致），淨值與配息比不取數"
    assert "declared_ccy_source" not in text


_INTERNAL = ("A 鏈", "auto_fetch_moneydj", "source_status", "moneydj_wb05", "{'", "'undetermined'", "：empty",
             ":'", "declared_ccy_source", "tcb_moneydj_div", "fundclear_div", "[yp0", "None")


def test_使用者可見文字沒有內部名稱():
    strings = _all_strings(_wired())
    assert strings
    leaks = sorted({(word, v) for v in strings for word in _INTERNAL if word in v})
    assert leaks == []


@pytest.mark.parametrize("raw, want", [
    ("A 鏈（auto_fetch_moneydj('G07')）沒有取得淨值序列", "多來源取數沒有取得淨值序列"),
    ("A 鏈配息瀑布每一個來源都回報：成功取數、這一檔沒有配息紀錄", "配息每一個來源都回報：成功取數、這一檔沒有配息紀錄"),
    ("A 鏈配息取數失敗（每一個來源都失敗）", "配息取數失敗（每一個來源都失敗）"),
    ("can't parse 'x' near 'y", "can't parse 「x」 near 'y"),
    ("（TCB：{'truncated': None, 'filtered': 0}）", "（TCB：截斷 未記錄、過濾 0）"),
    ("yp011001@tcbbankfund.moneydj.com：HTTP 404；yp011001@www.moneydj.com：不符身分判準",
     "境外基本資料頁（合庫子網域）：HTTP 404；境外基本資料頁（主站）：不符身分判準"),
    ("yp099999@other.example：HTTP 404", "頁面 yp099999（other.example）：HTTP 404"),
    ("供列的來源回報有列沒有交出來（TCB：{'truncated': 3, 'filtered': 0, 'other_tables': 0}）",
     "供列的來源回報有列沒有交出來（TCB：截斷 3、過濾 0、其他表格 0）"),
    ("狀態 'undetermined'，沒有逐來源紀錄", "狀態 無法判定，沒有逐來源紀錄"),
    ("[yp010000] FundClear：empty", "FundClear（頁面 yp010000）：沒有配息紀錄"),
    ("[yp010000] 其他", "（頁面 yp010000）其他"),
    ("幣別不同（即時序列:'EUR'；來源自報 USD）", "幣別不同（即時序列 宣告「EUR」；來源自報 USD）"),
    ("各來源（MoneyDJ:'美元'→USD）", "各來源（MoneyDJ 宣告「美元」→USD）"),
    ("（FundClear：HTTP 503；完整原文見 source_status）", "（FundClear：HTTP 503）"),
    ("RuntimeError: Pool(host='x', port=443): timeout", "RuntimeError: Pool（host=「x」, port=443）: timeout"),
    ("認不得的原因原樣留下", "認不得的原因原樣留下"),
])
def test_原因白話化_白名單與通則_不吞原因(raw, want):
    assert live.plain_reason(raw) == want


# ═════════════════════ 2026-10-15 #966 修正輪 2：plain_reason 走樣與效能（稽核 Q） ═════════════════════


@pytest.mark.parametrize("raw, want", [
    # 稽核 Q 可選項：`int()` 不再被吃成 `int`（舊版全域刪空括號）
    ("invalid literal for int() with base 10: 'x'", "invalid literal for int（） with base 10: 「x」"),
    ("f() 與 g（） 都失敗", "f（） 與 g（） 都失敗"),
    # 入口呼叫拿掉時，只連包著它的那一對括號一起拿掉（全形、半形各一）
    ("A 鏈（auto_fetch_moneydj('G07')）與 f() 都失敗", "多來源取數與 f（） 都失敗"),
    ("A 鏈(auto_fetch_moneydj('G07'))失敗", "多來源取數失敗"),
    ("auto_fetch_moneydj('G07') 回空", " 回空"),
    # 稽核 Q 可選項：字面 `{}` 原樣留下，不寫成「（空）」
    ("明細 {}，格式 {} 未填", "明細 {}，格式 {} 未填"),
    # 讀不懂的字面只去殼、不炸（舊版 `{[1]}` 丟 TypeError，整頁組裝跟著炸）
    ("集合 {[1]} 與 {()}", "集合 （[1]） 與 {()}"),
    ("{'rows': 3}", "有配息列 3"),
    # 已知未涵蓋：巢狀呼叫只改最內層（`docs/v2/44` 7.3.3 有記）
    ("outer(inner(x))", "outer(inner（x）)"),
])
def test_修正輪2_空括號與空dict不走樣_怪字面不炸(raw, want):
    assert live.plain_reason(raw) == want


@pytest.mark.parametrize("raw", [
    "{'a': " + "-" * 100_000 + "1}",          # 剖析器堆疊溢位：MemoryError
    "{'a': 1" + "+1" * 50_000 + "}",          # RecursionError
    "{[1]}",                                  # TypeError
], ids=["MemoryError", "RecursionError", "TypeError"])
def test_修正輪2_literal_eval丟的各種例外_都照去殼處理_不炸(raw):
    out = live.plain_reason(raw)
    assert "{" not in out and "}" not in out and out.startswith("（")


# 修正前的 `_DECLARED`（d00365c 原字），只用來做新舊等價對照；不得拿去用在正式路徑。
_OLD_DECLARED = r"([^\s:：（(、，；]+):'([^']*)'"


def _declared_corpus():
    import random

    pieces = ["即時序列:'EUR'", "MoneyDJ:'美元'", "TDCC:'歐元'", "FundClear:沒提供", "a:'", "':'", ":'x'", "'",
              "（", "(", "、", "，", "；", " ", "\n", "：", "中文", "abc", "None", "{'rows': 3}", "[yp010000]",
              "yp011001@www.moneydj.com", "auto_fetch_moneydj('G07')", "A 鏈", "int()", "{}", "名" * 63, "名" * 64,
              "名" * 65, "x" * 200]
    rng = random.Random(20261015)
    corpus = [rng.choice(pieces) for _ in range(200)]
    corpus += ["".join(rng.choice(pieces) for _ in range(rng.randint(2, 12))) for _ in range(3000)]
    corpus += ["名" * n + ":'EUR'" for n in (1, 63, 64, 65, 66, 200, 5000)]
    corpus += ["前綴 " + "a" * n + ":'v' 後" + "b" * n + ":'w'" for n in (10, 64, 65, 129)]
    return corpus


def test_修正輪2_宣告樣式加上限_新舊替換逐字相同():
    """名稱段加上限 64 之後，`來源:'值'` 的替換結果與舊式逐字相同（含名稱段超過 64 字：前面那段原樣留著、不丟字）。"""
    import re

    old = re.compile(_OLD_DECLARED)
    assert old.pattern != live._DECLARED.pattern                             # 前提：真的換了 pattern

    def fmt(m):
        return f"{m.group(1)} 宣告「{m.group(2)}」"

    diffs = [t for t in _declared_corpus() if old.sub(fmt, t) != live._DECLARED.sub(fmt, t)]
    assert diffs == []


_LONG = 100_000
_PERF_INPUTS = {
    "a": "a" * _LONG,
    "中": "中" * _LONG,
    "'": "'" * _LONG,
    "a:": "a:" * (_LONG // 2),
    "長名稱:'v'": "名" * _LONG + ":'EUR'",
    "[頁型] +長串": "[yp010000] " + "a" * _LONG,
    "頁型@+a.": "yp011001@" + "a." * (_LONG // 2),
    "{ +長串": "{'a': '" + "x" * _LONG,
    "name( +長串": "f(" + "x" * _LONG,
    "中英引號混合": ("來源中文abc'x'" * (_LONG // 10))[:_LONG],
}
# 2026-10-15 #966 修正輪 3（獨立稽核必修）：頁型標記後接一長串空白 —— 四種空白 × 結尾（無、接 x、接「：」）。
_WS_KINDS = {"半形": " ", "tab": "\t", "全形": "\u3000", "NBSP": "\u00a0"}
for _ws_name, _ws in _WS_KINDS.items():
    for _tail_name, _tail in (("", ""), ("+x", "x"), ("+：", "："), ("+名稱：", "FundClear：")):
        _PERF_INPUTS[f"[頁型]+長{_ws_name}空白{_tail_name}"] = "[yp010000]" + _ws * _LONG + _tail


@pytest.mark.parametrize("name", list(_PERF_INPUTS))
def test_修正輪2_效能_十萬字的病態輸入_兩秒內(name):
    """稽核 Q 效能必修：d00365c 的 `_DECLARED` 對長串不含空白的字是平方時間（實測 4 萬個「中」約 15 秒）。"""
    import time

    text = _PERF_INPUTS[name]
    assert len(text) >= _LONG
    started = time.perf_counter()
    live.plain_reason(text)
    assert time.perf_counter() - started < 2.0


@pytest.mark.parametrize("ws", ["\u0020", "\t", "\u3000", "\u00a0"], ids=["半形", "tab", "全形", "NBSP"])
def test_修正輪3_頁型後只有空白緊接冒號_空白不當來源名稱(ws):
    """邊角語意（總管修正輪 3 要求先判斷再釘住）：舊式會把冒號前那一個空白當成來源名稱，畫成「 （頁面 …）：」；
    空白不是來源名稱 → 新式不當成「來源（頁面 頁型）：」，改由頁型通則畫成「（頁面 頁型）：」。"""
    assert live.plain_reason(f"[yp010000]{ws * 3}：其他") == "（頁面 yp010000）：其他"
    assert live.plain_reason(f"[yp010000]{ws}FundClear：empty") == "FundClear（頁面 yp010000）：沒有配息紀錄"


# 修正前的 `_PAGE_SOURCE`（f383c0c 原字），只用來做新舊等價對照；不得拿去用在正式路徑。
_OLD_PAGE_SOURCE = r"\[([a-z]{2}\d{6})\]\s*([^\[\]：\n；]+?)："


def test_修正輪3_頁型來源樣式_新舊替換逐字相同_只差空白名稱那個邊角():
    import random
    import re

    old = re.compile(_OLD_PAGE_SOURCE)
    new = live._PAGE_SOURCE
    assert old.pattern != new.pattern                                       # 前提：真的換了 pattern

    def fmt(m):
        return f"{m.group(2)}（頁面 {m.group(1)}）："

    def pipe(pat, text):                                                   # 照 `plain_reason` 的順序：先來源、再頁型通則
        return live._PAGE_TYPE.sub(lambda m: f"（頁面 {m.group(1)}）", pat.sub(fmt, text))

    pieces = ["[yp010000]", "[yp010001]", " ", "\t", "\u3000", "\u00a0", "\n", "\r", "：", "；", "[", "]", "FundClear",
              "合庫配息頁", "x", "a b", "empty", "，", "(", "'"]
    rng = random.Random(20261015)
    corpus = ["".join(rng.choice(pieces) for _ in range(rng.randint(1, 12))) for _ in range(20000)]
    corpus += [f"[yp010000]{ws * n}{tail}" for ws in (" ", "\t", "\u3000", "\u00a0") for n in (0, 1, 2, 5)
               for tail in ("", "x", "：", "x：", "\n：", "；：", "FundClear：empty")]

    def edge(text):                                                         # 舊式以「全是空白」當名稱命中
        return any(m.group(2).strip() == "" for m in old.finditer(text))

    edges = [t for t in corpus if edge(t)]
    assert edges                                                            # 語料真的含這個邊角
    diffs = [t for t in corpus if pipe(old, t) != pipe(new, t)]
    assert diffs and set(diffs) <= set(edges)
    for text in edges:                                                      # 邊角上的差別只有「開頭多一個空白名稱」
        if text in diffs:
            assert pipe(new, text) == pipe(old, re.sub(r"(\[[a-z]{2}\d{6}\])\s*(?=：)", r"\1", text))


def test_修正輪3_dict讀得懂但格式化失敗_照去殼處理_不炸():
    raw = "{'a': 0x" + "f" * 4000 + "}"                     # str() 轉十進位超過 4300 位上限 → ValueError
    out = live.plain_reason(raw)
    assert out == "（a: 0x" + "f" * 4000 + "）"


def test_修正輪2_效能_長名稱宣告_輸出不丟字():
    text = "名" * _LONG + ":'EUR'"
    assert live.plain_reason(text) == "名" * _LONG + " 宣告「EUR」"


def test_原因白話化只收字串():
    with pytest.raises(TypeError):
        live.plain_reason(None)


def _secret_source_out():
    out = F.nav_out(("A01",))
    out["nav"]["provenance"]["A01"]["source"] = f"FundClear:{F.SECRET}"
    return out


def test_來源標示經過遮蔽():
    """P M14：秘密值放在 `provenance.source` —— 它會進標示；標示本身要被遮蔽。"""
    node = _wired(nav_out=_secret_source_out(), codes=("A01",))["cells"]["A01"]["nav_date"]
    assert F.SECRET not in node["source_tag"] and "‹已遮蔽›" in node["source_tag"]


def test_tooltip經過遮蔽():
    """Q O2：同一個秘密值也進 tooltip（「淨值來源：…」）；tooltip 要被遮蔽。"""
    node = _wired(nav_out=_secret_source_out(), codes=("A01",))["cells"]["A01"]["nav_date"]
    assert F.SECRET not in node["source_tip"] and "‹已遮蔽›" in node["source_tip"]


def test_代碼對照表讀不到_摘要據實_不寫0檔候選():
    pool = {"status": "ok", "backend": "x", "codes": ["A01"], "dropped_blank": 0, "duplicates": 0, "message": None}
    wired = live.wiring_failed("代碼對照表讀取失敗：OSError: x")
    settings = _settings()
    inputs = {"dataset": live.build_dataset(pool, settings, wired),
              "notes": {"pool": pool, "settings": settings, "settings_error": None, "cells": {},
                        "wiring_error": wired["errors"]["fund_profile"]}}
    exp2 = logic.find_block(live.build_live_model(inputs, save_wired=True), "EXP-2")
    # ~~驗 `summary_text`~~ → 合併修正輪 D4（有意識的更正，不是漏刪）：EXP-2 是層 2 核心卡，`page.py` 不印 summary；
    # 改驗卡內實際印出的失敗行（`notes`，由 `page._notes` 畫出）與結論燈。
    assert exp2["notes"] == ["fund_profile：⛔ 取數失敗：代碼對照表讀取失敗：OSError: x"]
    assert not any("0 檔" in line or logic.TEXT_NO_MATCH in line for line in exp2["notes"])
    exp0 = logic.find_block(live.build_live_model(inputs, save_wired=True), "EXP-0")
    assert "0 檔" not in exp0["text"]


def test_契約_無配息列與有配息列的provenance_與真L2同形():
    nav_dividend = pytest.importorskip("services.v2_tables.nav_dividend")
    fo = pytest.importorskip("repositories.fund.fund_orchestration")
    outcome = {"outcome": fo.DIV_OUTCOME_NONE, "none_evidenced": True, "legacy_inline_parse": False,
               "sources": [{"source": "FundClear", "page_type": "yp010000", "status": "empty", "detail": ""},
                           {"source": "合庫配息頁", "page_type": "yp010000", "status": "empty", "detail": ""}]}
    real = nav_dividend.rows_from_chain_dividends("B02", {"items": [], "outcome": outcome, "error": None},
                                                  holding_ccys=["USD"], label_source=F.META)
    assert real["settled"] is True and real["rows"] == [] and real["skipped"] == [F.TEXT_DIV_NONE]
    assert real["provenance"] == F._div_prov_none()                       # 同形且同值（含 outcome_detail）
    assert "coverage_start" not in real["provenance"]
    fake_rows = F._div_prov_rows(["fundclear_div"], date(2026, 1, 1))
    assert set(fake_rows) == {"source", "fetched_at", "ccy_source", "outcome", "outcome_detail", "settled",
                              "coverage_start"}


# ═════════════════════ 2026-10-14 合併修正輪（#967 合併後） ═════════════════════


def test_B1_同一來源兩頁型結果不同_畫面看得出是兩頁():
    text = live.plain_reason("[yp010000] FundClear：empty\n[yp010001] FundClear：failed".replace("\n", "；"))
    assert text == "FundClear（頁面 yp010000）：沒有配息紀錄；FundClear（頁面 yp010001）：取數失敗"
    assert "yp010000" in text and "yp010001" in text


def test_D1_有配息列但沒有覆蓋起點_不當作有涵蓋():
    kind, _r, why = _ratio([_d(date(2026, 5, 1))], coverage=None)
    assert kind == "not_ready" and "未記錄" in why


def test_D2_先遮蔽再白話化_秘密值含引號也遮得掉():
    secret = "tok 'en' XYZ"                        # 白話化會把成對單引號改成「」；若先白話化，秘密值就比對不到
    assert live.plain_reason(secret) != secret                                # 前提：這個值真的會被白話化改寫
    out = F.nav_out(("A01",))
    out["nav"]["errors"]["A01"] = f"HTTP 503 key={secret}"
    out["nav"]["rows"] = [r for r in out["nav"]["rows"] if r["fund_code"] != "A01"]
    wired = _wired(nav_out=out, codes=("A01",), mask=lambda t: t.replace(secret, "‹已遮蔽›"))
    node = wired["cells"]["A01"]["nav_date"]
    assert "‹已遮蔽›" in node["text"] and "XYZ" not in node["text"] and "tok" not in node["text"]


_KEEP = object()


def _differs_out(dates, missing=0, *, rejected=0, skipped=_KEEP, mask=F.mask):
    """`rejected`：L2 交出的 `conflict_rejected_rows`（`_KEEP` 以外的值照放；`_DROP` ＝ 不放這個鍵）。"""
    out = F.nav_out(("J10",))
    prov = out["dividend"]["provenance"]["J10"]
    prov["conflict_ex_dates"] = dates
    prov["conflict_ex_dates_missing"] = missing
    if rejected is _DROP:
        prov.pop("conflict_rejected_rows", None)
    else:
        prov["conflict_rejected_rows"] = rejected
    if skipped is not _KEEP:
        out["dividend"]["skipped"]["J10"] = skipped
    return _wired(nav_out=out, codes=("J10",), mask=mask)["cells"]["J10"]["div_ratio_pct"]


_DROP = object()


def test_C2_衝突落在窗口內_不適用():
    node = _differs_out(["2024-01-05", "2026-09-05"])
    assert node["text"] == "⬜ 不適用：配息幣別與淨值幣別不同" and node["state"] == logic.STATE_BIZ
    assert node["source_tag"] == live.TAG_DIV_CCY_DECLARED
    assert node["source_tip"].startswith("來源：配息資料（各筆幣別宣告）") and "不同或認不出" not in node["source_tip"]
    assert "2026-09-05" in node["source_tip"]
    # 修正輪 2（稽核 P 必修）：L2 原文（先遮蔽、再白話化）照實附上 —— 幣別值與筆數找得回來
    assert ("資料層紀錄：配息宣告的幣別與來源自報（MoneyDJ+TDCC）的幣別不同（「EUR」、「EUR」；來源自報（MoneyDJ+TDCC） USD）；"
            "不改標籤、不換算，這一檔的配息 2 筆全部不寫") in node["source_tip"]


def test_C2_衝突只在窗口外_資料未備():
    node = _differs_out(["2023-03-01", "2024-01-05"])
    assert node["text"] == f"{logic.ND_TEXT}：{live.TEXT_DIV_CCY_DIFFERS_BEFORE}" and node["state"] == logic.STATE_MISSING


def test_C2_窗口邊界_起點當天不在窗口內_隔天在():
    # J10 最新淨值日 2026-10-12 → 窗口 (2025-10-12, 2026-10-12]
    assert _differs_out(["2025-10-12"])["text"] == f"{logic.ND_TEXT}：{live.TEXT_DIV_CCY_DIFFERS_BEFORE}"
    assert _differs_out(["2025-10-11"])["text"] == f"{logic.ND_TEXT}：{live.TEXT_DIV_CCY_DIFFERS_BEFORE}"
    assert _differs_out(["2025-10-13"])["text"] == live.TEXT_DIV_CCY_DIFFERS_NA
    assert _differs_out(["2026-10-12"])["text"] == live.TEXT_DIV_CCY_DIFFERS_NA


def test_C2_衝突晚於最新淨值日_窗口外_資料未備():
    assert _differs_out(["2026-10-13"])["text"] == f"{logic.ND_TEXT}：{live.TEXT_DIV_CCY_DIFFERS_OUTSIDE}"


@pytest.mark.parametrize("dates, missing", [(["2026-09-05", None], 1), ([], 0), (None, None), (["2026-09-05"], 1)])
def test_C2_衝突筆缺日期或沒交出日期_資料未備(dates, missing):
    node = _differs_out(dates, missing)
    assert node["text"] == f"{logic.ND_TEXT}：{live.TEXT_DIV_CCY_DIFFERS_UNKNOWN}"


def test_修正輪2_有被剔除的列_衝突只在以前_一律無法確認_tooltip揭露():
    """稽核 P：2020 年 EUR ＋ 一筆被剔除的列 → 不得說「只出現在近 12 個月以前」。"""
    node = _differs_out(["2020-03-05"], rejected=1)
    assert node["text"] == f"{logic.ND_TEXT}：{live.TEXT_DIV_CCY_DIFFERS_UNKNOWN}" and node["state"] == logic.STATE_MISSING
    assert live.TEXT_DIV_CCY_DIFFERS_BEFORE not in node["text"]
    assert live.TIP_DIV_REJECTED.format(n=1) in node["source_tip"] and "2020-03-05" in node["source_tip"]


def test_修正輪2_有被剔除的列_衝突晚於淨值日_也無法確認():
    assert _differs_out(["2026-10-13"], rejected=2)["text"] == f"{logic.ND_TEXT}：{live.TEXT_DIV_CCY_DIFFERS_UNKNOWN}"


@pytest.mark.parametrize("rejected", [_DROP, None, "1", True, False, 1.0, -1])
def test_修正輪2_資料層沒交出合法的剔除筆數_無法確認(rejected):
    node = _differs_out(["2020-03-05"], rejected=rejected)
    assert node["text"] == f"{logic.ND_TEXT}：{live.TEXT_DIV_CCY_DIFFERS_UNKNOWN}"
    assert live.TIP_DIV_REJECTED_UNKNOWN in node["source_tip"]


def test_修正輪2_窗口內已確認有衝突_有被剔除的列仍是不適用():
    node = _differs_out(["2020-03-05", "2026-09-05"], rejected=3)
    assert node["text"] == live.TEXT_DIV_CCY_DIFFERS_NA
    assert live.TIP_DIV_REJECTED.format(n=3) in node["source_tip"]


def test_修正輪2_沒有被剔除的列_衝突只在以前_照舊不下結論():
    assert _differs_out(["2020-03-05"], rejected=0)["text"] == f"{logic.ND_TEXT}：{live.TEXT_DIV_CCY_DIFFERS_BEFORE}"


def test_修正輪2_缺日期那一支_tooltip也附資料層紀錄():
    node = _differs_out(["2026-09-05", None], 1)
    assert node["text"] == f"{logic.ND_TEXT}：{live.TEXT_DIV_CCY_DIFFERS_UNKNOWN}"
    assert "資料層紀錄：" in node["source_tip"] and "「EUR」" in node["source_tip"]


def test_修正輪2_資料層紀錄也先遮蔽再白話化():
    secret = "tok 'en' XYZ"                          # 先白話化的話，成對單引號會變「」，秘密值就比對不到
    line = f"配息宣告的幣別與來源自報的幣別不同（'EUR'；{secret}）；這一檔的配息 1 筆全部不寫"
    node = _differs_out(["2020-03-05"], skipped=[line], mask=lambda t: t.replace(secret, "‹已遮蔽›"))
    assert "‹已遮蔽›" in node["source_tip"] and "XYZ" not in node["source_tip"] and "tok" not in node["source_tip"]


def test_修正輪2_真的L2_壞日期被剔除_2020衝突_無法確認_tooltip有幣別筆數與剔除原因():
    """稽核 P 情境走真的 `exp_nav` → `nav_dividend`（只替換 A 鏈取數）：2020 年 EUR ＋ `2020-13-45` EUR。"""
    exp_nav = pytest.importorskip("services.v2_tables.exp_nav")
    nav_dividend = pytest.importorskip("services.v2_tables.nav_dividend")
    S = pytest.importorskip("repositories.fund.sources")
    FO = pytest.importorskip("repositories.fund.fund_orchestration")
    pd = pytest.importorskip("pandas")
    from datetime import datetime, timezone

    at = "2026-10-14T00:00:00+00:00"

    def item(day):
        return {"date": day, "ex_date": day, "pay_date": day, "amount": 0.04, "yield_pct": 0, "currency": "EUR",
                S.DIV_PROVENANCE_KEY: {"parser": S.DIV_PARSER_FUNDCLEAR, "date_field": "ExDividendDate",
                                       "currency_field": "Currency", "amount_field": "DividendAmount",
                                       "fetched_at": at}}

    outcome = {"outcome": FO.DIV_OUTCOME_ROWS, "legacy_inline_parse": False, "none_evidenced": False,
               "sources": [{"source": "FundClear", "parser": S.DIV_PARSER_FUNDCLEAR, "status": S.DIV_STATUS_ROWS,
                            "detail": "", "page_type": "yp010000",
                            "dropped": {"truncated": 0, "filtered": 0, "other_tables": 0}}]}

    def chain(chain_code, full_key):
        days = pd.date_range("2026-09-01", "2026-10-09", freq="B")
        res = {"full_key": full_key, "series": pd.Series([10.0] * len(days), index=days),
               "dividends": [item("2020-03-05"), item("2020-13-45")], FO.DIVIDENDS_OUTCOME_KEY: outcome,
               "data_source": "FundClear", "chain_started_at": at}
        res["series"].attrs.update({"source": "FundClear:GetFundNAV", "fetched_at": at, "currency": "USD"})
        series, error = nav_dividend._nav_from_chain(res, "yp010000", chain_code, full_key)
        return series, error, nav_dividend._div_from_chain(res, full_key)

    funds = [{"fund_code": "B01", "full_key": "B01", "chain_code": "B01", "portal": "",
              "declared_ccy": "USD", "declared_ccy_source": "meta:MoneyDJ+TDCC"}]
    exp_nav.clear_memo()
    try:
        out = exp_nav.load_nav_dividend(funds, now=datetime(2026, 10, 14, 2, 0, tzinfo=timezone.utc),
                                        chain_fetch=chain)
    finally:
        exp_nav.clear_memo()
    div = out["dividend"]
    # 前提：真 L2 走了 div_ccy_differs、只交出 2020 那一筆衝突日期、壞日期那筆以剔除計數交出
    assert div["withheld"] == {"B01": nav_dividend.WITHHELD_DIV_CCY_DIFFERS}
    prov = div["provenance"]["B01"]
    assert prov["conflict_ex_dates"] == ["2020-03-05"] and prov["conflict_ex_dates_missing"] == 0
    assert prov["conflict_rejected_rows"] == 1
    profiles = {"rows": [], "cells": {}, "declared": {}, "source_status": {}}
    wired = live.assemble_wired(profiles, ["B01"], out, unresolved={}, today=date(2026, 10, 14), mask=F.mask,
                                withheld_texts=F.WITHHELD_TEXTS, input_conflict=F.INPUT_CONFLICT,
                                div_ccy_differs=nav_dividend.WITHHELD_DIV_CCY_DIFFERS)
    node = wired["cells"]["B01"]["div_ratio_pct"]
    assert node["text"] == f"{logic.ND_TEXT}：{live.TEXT_DIV_CCY_DIFFERS_UNKNOWN}"
    tip = node["source_tip"]
    assert "「EUR」" in tip and "這一檔的配息 2 筆全部不寫" in tip            # 幣別值、筆數
    assert "日期不是 YYYY-MM-DD 或 YYYY/MM/DD（「2020-13-45」） 1 筆不寫" in tip   # 被剔除的列
    assert live.TIP_DIV_REJECTED.format(n=1) in tip and "不同或認不出" not in tip


def test_C2_窗口判斷與配息比共用同一支():
    source = (_HERE.parents[1] / "ui_v2" / "exp" / "live.py").read_text(encoding="utf-8")
    assert source.count("window_start(nav_day) < day <= nav_day") == 1
    assert "in_ratio_window(ex_day, nav_day)" in source and "in_ratio_window(d, nav_day)" in source


def test_A2_真的exp_profile_各種新狀態的原因句_白話化後據實且沒有內部名稱():
    """#967 合併後：MoneyDJ `unrecognized_page`／`not_found`、TDCC `code_unmapped`、MoneyDJ 取數失敗 —— 走真 L2。"""
    exp_profile = pytest.importorskip("services.v2_tables.exp_profile")
    dp = pytest.importorskip("repositories.fund.declared_profile")
    from datetime import datetime, timezone

    attempts = {
        "U01": [{"page_type": "yp011001", "host": "tcbbankfund.moneydj.com", "outcome": "not_found_404"},
                {"page_type": "yp011001", "host": "www.moneydj.com", "outcome": "unrecognized_page",
                 "problem": "含基金名稱標籤的表 0 張（空殼頁）"}],
        "N02": [{"page_type": p, "host": h, "outcome": "not_found_404"}
                for p in ("yp011000", "yp011001") for h in dp.MONEYDJ_HOSTS],
        "F03": [{"page_type": "yp011000", "host": "www.moneydj.com", "outcome": "http_failed",
                 "fail_kind": "timeout"}],
    }
    attempts["T04"] = attempts["N02"]
    status = {"U01": dp.STATUS_UNRECOGNIZED, "N02": dp.STATUS_NOT_FOUND, "F03": dp.STATUS_FAILED,
              "T04": dp.STATUS_NOT_FOUND}

    def mdj(full_key):
        short = "；".join(dp._attempt_short(a) for a in attempts[full_key])
        return {"status": status[full_key], "source": "MoneyDJ", "full_key": full_key,
                "fields": {lb: None for lb in dp.MONEYDJ_LABELS}, "label_conflicts": [], "provenance": None,
                "fetched_at": None, "attempts": attempts[full_key], "error": short, "reason": short,
                "failure_reason": short if full_key == "F03" else None}

    def tdcc(full_key):
        return {"status": dp.STATUS_CODE_UNMAPPED, "fields": {}, "fetched_at": None, "observed_at": None,
                "error": None}

    def fundclear(full_key):
        if full_key == "T04":
            raise RuntimeError("HTTP 503")
        return {"status": "ok", "fields": {"currency": "USD"}, "fetched_at": "2026-10-14T01:00:00+00:00"}

    profiles = exp_profile.build_profiles(_keys(("U01", "N02", "F03", "T04")),
                                          fetchers={"MoneyDJ": mdj, "TDCC": tdcc, "FundClear": fundclear},
                                          now=datetime(2026, 10, 14, 2, 0, tzinfo=timezone.utc))
    wired = F.assemble(profiles, (), None)              # 只看基本資料各格（不取淨值）
    u01 = wired["cells"]["U01"]["fund_name"]["text"]
    assert u01 == ("⬜ 資料未備：MoneyDJ 頁面無法確認是本檔：境外基本資料頁（合庫子網域）：HTTP 404；"
                   "境外基本資料頁（主站）：含基金名稱標籤的表 0 張（空殼頁）")
    assert wired["cells"]["N02"]["fund_name"]["text"] == f"{logic.ND_TEXT}：{exp_profile.TEXT_MDJ_NOT_FOUND}"
    f03 = wired["cells"]["F03"]["fund_name"]["text"]
    assert f03.startswith("⛔ 取數失敗：MoneyDJ 取數失敗：") and "境內基本資料頁（主站）" in f03 and "timeout" in f03
    ccy_tip = wired["cells"]["U01"]["ccy"]["source_tip"] or ""
    assert "FundClear" in ccy_tip
    t04 = wired["cells"]["T04"]["ccy"]["text"]                 # 三來源都沒有可用幣別：TDCC 代碼體系不同、FundClear 失敗
    assert t04.startswith("⛔ 取數失敗：") and "代碼無法對照（TDCC 清單使用不同代碼體系）" in t04
    leaks = sorted({(w, v) for v in _all_strings(wired)
                    for w in ("yp011000", "yp011001", "@www", "@tcbbankfund", "moneydj.com", "code_unmapped",
                              "unrecognized_page", "not_found") if w in v})
    assert leaks == []


def test_契約_MoneyDJ_not_listed_L2仍收_畫成資料未備():
    exp_profile = pytest.importorskip("services.v2_tables.exp_profile")
    dp = pytest.importorskip("repositories.fund.declared_profile")
    from datetime import datetime, timezone

    profiles = exp_profile.build_profiles(
        _keys(("L01",)),
        fetchers={"MoneyDJ": lambda k: {"status": dp.STATUS_NOT_LISTED, "fields": {}, "fetched_at": None},
                  "TDCC": lambda k: {"status": "ok", "fields": {"計價幣別": "美元"}, "fetched_at": None,
                                     "observed_at": "2026-10-14"},
                  "FundClear": lambda k: {"status": "ok", "fields": {"currency": "USD"},
                                          "fetched_at": "2026-10-14T01:00:00+00:00"}},
        now=datetime(2026, 10, 14, 2, 0, tzinfo=timezone.utc))
    assert profiles["declared"]["L01"] == ("USD", "meta:TDCC+FundClear")
    wired = F.assemble(profiles, (), None)
    assert wired["cells"]["L01"]["fund_name"]["text"] == f"{logic.ND_TEXT}：MoneyDJ 未收錄此代碼"
