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
    profiles = profiles or F.profiles()
    return live.assemble_wired(profiles, list(codes), nav_out if nav_out is not None else F.nav_out(codes),
                               unresolved=unresolved or {}, today=today, mask=mask,
                               withheld_texts=F.WITHHELD_TEXTS, input_conflict=F.INPUT_CONFLICT)


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
    assert F.TEXT_CCY_UNDETERMINED == exp_nav.TEXT_CCY_UNDETERMINED
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


def _ratio(rows, *, nav_day=date(2026, 10, 10), settled=True, coverage=date(2020, 1, 1), nav=10.0, ccy="USD"):
    return live.dividend_ratio(nav, ccy, nav_day, rows, settled=settled, coverage_start=coverage)


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


def test_規則13_確認完整且窗口內無配息_不適用_不是0也不是資料未備():
    model = _model()
    node = _cell(model, "B02", "div_ratio_pct")
    assert node["text"] == "⬜ 不適用：近 12 個月無配息" and node["_state"] == logic.STATE_BIZ
    assert "0.00%" not in node["text"] and logic.ND_TEXT not in node["text"]
    kind, ratio, _ = _ratio([_d(date(2024, 1, 1))])                          # 有配息列、但都在窗口外
    assert (kind, ratio) == ("none", None)
    kind, ratio, _ = _ratio([_d(date(2026, 5, 1), 0.0)])                     # 窗口內合計為 0
    assert (kind, ratio) == ("none", None)


def test_配息比前提不成立_資料未備():
    assert _ratio([_d(date(2026, 5, 1))], settled=False)[0] == "not_ready"
    kind, _r, why = _ratio([_d(date(2026, 5, 1))], coverage=date(2026, 5, 1))     # 覆蓋起點晚於窗口起點
    assert kind == "not_ready" and "未涵蓋近 12 個月" in why
    kind, _r, why = _ratio([_d(date(2026, 5, 1), ccy="TWD")])                    # 配息幣別與淨值幣別不同
    assert kind == "not_ready" and "TWD" in why
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
        assert node["text"] == f"{logic.ND_TEXT}：{F.CONFLICT_LINE}"
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
    assert _cell(_model(), "F06", "nav_date")["text"] == f"{logic.ND_TEXT}：{F.TEXT_CCY_UNDETERMINED}"


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
    assert title == ' title="a&quot;b&lt;script&gt;x&lt;/script&gt;"'
    assert page._src_html(node) == '<span class="exp-src">Evil&quot;Src&lt;b&gt;</span>'
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


def test_沒有接線結果時行為與接線前相同():
    pool = {"status": "ok", "backend": "x", "codes": ["A01"], "dropped_blank": 0, "duplicates": 0, "message": None}
    data = live.build_dataset(pool, _settings())
    assert data["fund_profile"] == [live._profile_row("A01")] and data["nav"] == [] and data["div_ratio_pct"] == {}


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
    from datetime import datetime, timezone

    def mdj(full_key):
        return {"status": "ok", "fields": {"基金名稱": f"基金{full_key}", "計價幣別": "美元", "配息頻率": "月配",
                                           "成立日期": "2010/01/15"},
                "binding": {"code_in_label_table": True}, "fetched_at": "2026-10-14T01:00:00+00:00"}

    def tdcc(full_key):
        return {"status": "ok", "fields": {"計價幣別": "美元"}, "fetched_at": None, "observed_at": "2026-10-14"}

    def fundclear(full_key):
        if full_key == "K02":
            raise RuntimeError(f"HTTP 503 token={F.SECRET}")
        return {"status": "ok", "fields": {"currency": "USD"}, "fetched_at": "2026-10-14T01:00:00+00:00"}

    keys = _keys(("K01", "K02"))
    profiles = exp_profile.build_profiles(keys, fetchers={"MoneyDJ": mdj, "TDCC": tdcc, "FundClear": fundclear})
    assert profiles["declared"]["K02"] == ("USD", "meta:MoneyDJ+TDCC")      # 部分失敗、其餘一致（規則 12）

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
                                input_conflict=nav_dividend.WITHHELD_INPUT_CONFLICT)
    assert [r["fund_code"] for r in wired["nav"]] == ["K01", "K02"]
    assert wired["nav"][0]["nav_date"] == "2026-10-09" and wired["nav"][0]["ccy"] == "USD"
    k02 = wired["cells"]["K02"]["ccy"]
    assert k02["text"] is None and "FundClear 失敗" in k02["source_tag"]
    assert F.SECRET not in k02["source_tip"] and "‹已遮蔽›" in k02["source_tip"]
    ratio = wired["cells"]["K01"]["div_ratio_pct"]
    assert ratio["text"].startswith(logic.ND_TEXT)                          # 沒有配息證據 → 不算、不是 0
    model = _model(wired, settings=_settings())
    assert _cell(model, "K01", "nav_orig_ccy")["text"] == "10.0000 USD"
