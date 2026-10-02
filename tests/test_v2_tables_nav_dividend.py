# -*- coding: utf-8 -*-
"""services/v2_tables/nav_dividend.py（L2）與 contract 的 `nav`／`dividend` 鏡像測試（fast lane；不打網路）。

依據：docs/v2/49_data_integration_plan.md §2.2、§2.6、§2.8、§4.3、§6.1 Q5／Q12（客戶裁示）、§6.2 T3。
欄位契約的唯一真相來源是 docs/v2/44_fund_ui_ssot.md 第四節 4.2 `nav`、4.3 `dividend`；
`services/v2_tables/contract.py` 只是鏡像，本檔第一段逐欄從 44 重抽比對。

L1 一律以替身函式注入（monkeypatch 模組屬性），不打真網路。
"""

from __future__ import annotations

import datetime as dt
import math
import pathlib
import re

import pandas as pd
import pytest

from services.v2_tables import contract
from services.v2_tables import nav_dividend as ND

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_D44 = _ROOT / "docs" / "v2" / "44_fund_ui_ssot.md"

_FETCHED = "2026-09-25T06:00:00.123456+00:00"
# 判「未來」用的固定當下（測試不依賴機器時鐘）。台灣日期 2026-10-01。
NOW = dt.datetime(2026, 9, 30, 20, 0, tzinfo=dt.timezone.utc)
_LIVE_SOURCE = "MoneyDJ:tcbbankfund.moneydj.com:wb02.djhtm:fetch_nav"


# ═══════════════════════ 契約：44 是唯一真相來源 ═══════════════════════

def _strip_struck(text: str) -> str:
    return re.sub(r"~~.*?~~", "", text)


def _table_from_44(name: str):
    text = _D44.read_text(encoding="utf-8")
    sec4 = text[text.index("## 4. 資料庫結構"): text.index("## 5. 元件清單")]
    head = re.search(rf"(?m)^#{{3,4}} (?:[0-9.]+ )?表 `{name}`", sec4)
    assert head, f"44 第四節找不到 {name} 表"
    rest = sec4[head.end():]
    nxt = re.search(r"(?m)^#{3,4} ", rest)
    body = rest[: nxt.start()] if nxt else rest
    fields, meanings = [], {}
    for line in body.split("\n"):
        m = re.match(r"^\| `([a-z_]+)` \| ([^|]+) \| ([^|]+) \| ([^|]+) \| (.*) \|\s*$", line)
        if m:
            col, typ, _unit, nullable, meaning = (g.strip() for g in m.groups())
            fields.append((col, typ, nullable == "是"))
            meanings[col] = _strip_struck(meaning)
    return tuple(fields), meanings


def test_契約_nav與44逐欄相同_source_tier值域相同():
    fields, meanings = _table_from_44("nav")
    assert len(fields) == 7, fields  # 空掃防呆
    assert contract.NAV_FIELDS == fields
    tiers = tuple(re.findall(r"`([^`]+)`", meanings["source_tier"]))
    assert tiers == contract.SOURCE_TIER_VALUES
    assert ND.SOURCE_TIER_NAV in tiers


def test_契約_dividend與44逐欄相同_div_kind值域相同():
    fields, meanings = _table_from_44("dividend")
    assert len(fields) == 7, fields
    assert contract.DIVIDEND_FIELDS == fields
    assert tuple(re.findall(r"`([a-z_]+)`", meanings["div_kind"])) == contract.DIV_KIND_VALUES
    assert ND.DIV_KIND_UNKNOWN in contract.DIV_KIND_VALUES


def _nav_row(**kw):
    row = {"fund_code": "ZZ9999", "nav_date": "2026-09-01", "nav_orig_ccy": 10.5, "ccy": "USD",
           "source_tier": "淨值", "is_estimated": False, "fetched_at": _FETCHED}
    row.update(kw)
    return row


def _div_row(**kw):
    row = {"fund_code": "ZZ9999", "ex_date": "2026-09-01", "pay_date": None,
           "div_per_unit_orig_ccy": 0.05, "ccy": "USD", "div_kind": "unknown", "fetched_at": _FETCHED}
    row.update(kw)
    return row


def test_契約_nav_row_problems_正反例():
    assert contract.nav_row_problems(_nav_row()) == []
    assert contract.nav_row_problems(_nav_row(nav_orig_ccy=0.0))
    assert contract.nav_row_problems(_nav_row(nav_orig_ccy=-1.0))
    assert contract.nav_row_problems(_nav_row(nav_orig_ccy=float("nan")))
    assert contract.nav_row_problems(_nav_row(ccy="usd"))
    assert contract.nav_row_problems(_nav_row(source_tier="T1"))
    assert contract.nav_row_problems(_nav_row(is_estimated=None))
    assert contract.nav_row_problems(_nav_row(fetched_at="2026-09-25T06:00:00"))   # 沒有時區
    assert contract.nav_row_problems(_nav_row(nav_date="2026/09/01"))
    assert contract.nav_row_problems(dict(_nav_row(), source="x"))                # 不得多欄


def test_契約_dividend_row_problems_正反例():
    assert contract.dividend_row_problems(_div_row()) == []
    assert contract.dividend_row_problems(_div_row(div_per_unit_orig_ccy=0.0)) == []   # 0 合法
    assert contract.dividend_row_problems(_div_row(pay_date="2026-09-15")) == []
    assert contract.dividend_row_problems(_div_row(div_per_unit_orig_ccy=-0.01))       # 負數被拒
    assert contract.dividend_row_problems(_div_row(div_kind="Income"))
    assert contract.dividend_row_problems(_div_row(ccy=None))
    assert contract.dividend_row_problems(_div_row(pay_date=""))


# ═══════════════════════ 假 L1 ═══════════════════════

def _series(points, **attrs):
    s = pd.Series({pd.Timestamp(d): v for d, v in points}, dtype=float).sort_index()
    base = {"source": _LIVE_SOURCE, "fetched_at": _FETCHED}
    base.update(attrs)
    s.attrs.update({k: v for k, v in base.items() if v is not None})
    return s


def _nav_stub(table, calls=None):
    """full_key → (Series, error) 或例外。"""
    def fake(full_key, portal=""):
        if calls is not None:
            calls.append((full_key, portal))
        value = table[full_key]
        if isinstance(value, Exception):
            raise value
        return value
    return fake


def _forbid(name):
    def fake(*_a, **_k):
        raise AssertionError(f"{name} 不該被呼叫")
    return fake


def fund(code="ZZ9999", full_key="ZZ9999", ccy="USD", **kw):
    item = {"fund_code": code, "full_key": full_key}
    if ccy is not None:
        item["holding_ccy"] = ccy
    item.update(kw)
    return item


# ═══════════════════════ nav：正例 ═══════════════════════

def test_nav正例_逐欄照44_幣別取持倉手填_provenance記來源(monkeypatch):
    s = _series([("2026-09-01", 10.5), ("2026-09-02", 10.6)])
    monkeypatch.setattr(ND, "fetch_nav_with_error", _nav_stub({"ZZ9999": (s, None)}))
    out = ND.build_nav_table([fund()])
    assert out["rows"] == [
        _nav_row(nav_date="2026-09-01", nav_orig_ccy=10.5),
        _nav_row(nav_date="2026-09-02", nav_orig_ccy=10.6),
    ]
    assert [list(r) for r in out["rows"]] == [[n for n, _t, _x in contract.NAV_FIELDS]] * 2
    assert out["errors"] == {} and out["withheld"] == {} and out["fetched"] == {"ZZ9999": 2}
    assert out["provenance"]["ZZ9999"] == {
        "source": _LIVE_SOURCE, "fetched_at": _FETCHED, "ccy_source": "holding_user_input",
        "cache_fallback": False, "stale": None}


def test_nav_週末與假日沒有列_不補列(monkeypatch):
    # 2026-09-04 週五、09-07 週一；中間的週末不得出現
    s = _series([("2026-09-04", 10.0), ("2026-09-07", 10.2)])
    monkeypatch.setattr(ND, "fetch_nav_with_error", _nav_stub({"ZZ9999": (s, None)}))
    rows = ND.build_nav_table([fund()])["rows"]
    assert [r["nav_date"] for r in rows] == ["2026-09-04", "2026-09-07"]


def test_nav_fetched_at換成世界協調時間_同一瞬間_一律加00冒號00形式():
    for given in ("2026-09-25T14:00:00+08:00", "2026-09-25T06:00:00Z", "2026-09-25T06:00:00+00:00"):
        s = _series([("2026-09-01", 10.0)], fetched_at=given)
        out = ND.rows_from_nav_series("ZZ9999", s, None, holding_ccys={"USD"}, now=NOW)
        assert out["rows"][0]["fetched_at"] == "2026-09-25T06:00:00+00:00", given


def test_nav_單筆照寫():
    out = ND.rows_from_nav_series("ZZ9999", _series([("2026-09-01", 9.9)]), None, holding_ccys={"USD"})
    assert len(out["rows"]) == 1 and out["skipped"] == []


def test_nav_新基金只有幾筆_照寫不補():
    pts = [("2026-09-28", 10.0), ("2026-09-29", 10.01), ("2026-09-30", 10.02)]
    out = ND.rows_from_nav_series("NEW001", _series(pts), None, holding_ccys={"TWD"})
    assert [r["nav_date"] for r in out["rows"]] == ["2026-09-28", "2026-09-29", "2026-09-30"]
    assert all(r["ccy"] == "TWD" for r in out["rows"])


def test_nav_停售基金_最後一筆之後沒有列():
    pts = [("2024-03-01", 8.0), ("2024-03-04", 7.9)]
    out = ND.rows_from_nav_series("HALT01", _series(pts), None, holding_ccys={"USD"})
    assert [r["nav_date"] for r in out["rows"]] == ["2024-03-01", "2024-03-04"]


# ═══════════════════════ nav：缺值與失敗 ═══════════════════════

def test_nav_全NaN_一列都不寫_理由寫明():
    s = _series([("2026-09-01", float("nan")), ("2026-09-02", float("nan"))])
    out = ND.rows_from_nav_series("ZZ9999", s, None, holding_ccys={"USD"})
    assert out["rows"] == []
    assert any("非有限數值 2 筆" in t for t in out["skipped"])


def test_nav_部分NaN_只略過那幾筆_不ffill():
    s = _series([("2026-09-01", 10.0), ("2026-09-02", float("nan")), ("2026-09-03", 10.2)])
    out = ND.rows_from_nav_series("ZZ9999", s, None, holding_ccys={"USD"})
    assert [(r["nav_date"], r["nav_orig_ccy"]) for r in out["rows"]] == [
        ("2026-09-01", 10.0), ("2026-09-03", 10.2)]


def test_nav_零與負淨值不寫():
    s = _series([("2026-09-01", 0.0), ("2026-09-02", -1.0), ("2026-09-03", 10.0)])
    out = ND.rows_from_nav_series("ZZ9999", s, None, holding_ccys={"USD"})
    assert [r["nav_date"] for r in out["rows"]] == ["2026-09-03"]
    assert any("不大於 0 2 筆" in t for t in out["skipped"])


def test_nav_空序列沒有原因_回弱訊息_不寫():
    out = ND.rows_from_nav_series("ZZ9999", pd.Series(dtype=float), None, holding_ccys={"USD"})
    assert out["rows"] == [] and out["error"] == ND.EMPTY_WITHOUT_REASON


def test_nav_取數失敗_原文逐字進errors(monkeypatch):
    msg = "fetch_nav('ZZ9999') 即時網址與預存檔皆失敗:\nhttps://x → 取數失敗(kind=http_403)"
    monkeypatch.setattr(ND, "fetch_nav_with_error",
                        _nav_stub({"ZZ9999": (pd.Series(dtype=float), msg)}))
    out = ND.build_nav_table([fund()])
    assert out["rows"] == [] and out["errors"] == {"ZZ9999": msg} and out["fetched"] == {"ZZ9999": 0}


def test_nav_L1拋例外_轉成型別名加原文_其他基金照跑(monkeypatch):
    ok = _series([("2026-09-01", 10.0)])
    monkeypatch.setattr(ND, "fetch_nav_with_error",
                        _nav_stub({"BAD": RuntimeError("boom"), "ZZ9999": (ok, None)}))
    out = ND.build_nav_table([fund(code="BAD", full_key="BAD"), fund()])
    assert out["errors"] == {"BAD": "RuntimeError: boom"}
    assert [r["fund_code"] for r in out["rows"]] == ["ZZ9999"]


def test_nav_fetched_at取不到或沒有時區_整批不寫_不以當下時間補():
    for at in (None, "", "2026-09-25T06:00:00", "not-a-time"):
        s = _series([("2026-09-01", 10.0)], fetched_at=at)
        if at is None:
            s.attrs.pop("fetched_at", None)
        out = ND.rows_from_nav_series("ZZ9999", s, None, holding_ccys={"USD"})
        assert out["rows"] == [], at
        assert out["withheld"] == ND.WITHHELD_FETCHED_AT_MISSING, at


def test_nav_同一日期同值只寫一列_不同值該日全不寫():
    s = pd.Series([10.0, 10.0, 11.0, 12.0],
                  index=[pd.Timestamp("2026-09-01"), pd.Timestamp("2026-09-01"),
                         pd.Timestamp("2026-09-02"), pd.Timestamp("2026-09-02")])
    s.attrs.update({"source": _LIVE_SOURCE, "fetched_at": _FETCHED})
    out = ND.rows_from_nav_series("ZZ9999", s, None, holding_ccys={"USD"})
    assert [r["nav_date"] for r in out["rows"]] == ["2026-09-01"]
    assert any("同一日期出現不同淨值 2 筆" in t for t in out["skipped"])


def test_nav_索引帶時區_不猜日期():
    s = pd.Series([10.0], index=[pd.Timestamp("2026-09-01T23:00:00", tz="UTC")])
    s.attrs.update({"source": _LIVE_SOURCE, "fetched_at": _FETCHED})
    out = ND.rows_from_nav_series("ZZ9999", s, None, holding_ccys={"USD"})
    assert out["rows"] == [] and any("帶時區" in t for t in out["skipped"])


# ═══════════════════════ nav：幣別（T3）═══════════════════════

def test_nav_幣別缺_整批不寫_不猜不預設USD():
    out = ND.rows_from_nav_series("ZZ9999", _series([("2026-09-01", 10.0)]), None, holding_ccys=())
    assert out["rows"] == [] and out["withheld"] == ND.WITHHELD_CCY_MISSING


def test_nav_持倉幣別不合ISO4217_不改大小寫_整批不寫():
    for bad in ("usd", " USD", "US", "美元", ""):
        out = ND.rows_from_nav_series("ZZ9999", _series([("2026-09-01", 10.0)]), None,
                                      holding_ccys={bad})
        assert out["rows"] == [], bad
        assert out["withheld"] == ND.WITHHELD_CCY_MISSING, bad


def test_nav_來源自報幣別優先記出處_與持倉相同照寫():
    s = _series([("2026-09-01", 10.0)], currency="EUR")
    out = ND.rows_from_nav_series("ZZ9999", s, None, holding_ccys={"EUR"})
    assert out["rows"][0]["ccy"] == "EUR"
    assert out["provenance"]["ccy_source"] == "source_reported"
    only_source = ND.rows_from_nav_series("ZZ9999", s, None, holding_ccys=())
    assert only_source["rows"][0]["ccy"] == "EUR"


def test_nav_來源自報與持倉不同_不猜_整批不寫():
    s = _series([("2026-09-01", 10.0)], currency="EUR")
    out = ND.rows_from_nav_series("ZZ9999", s, None, holding_ccys={"USD"})
    assert out["rows"] == [] and out["withheld"] == ND.WITHHELD_CCY_CONFLICT


def test_nav_同一檔多列持倉幣別互相不同_整批不寫(monkeypatch):
    s = _series([("2026-09-01", 10.0)])
    monkeypatch.setattr(ND, "fetch_nav_with_error", _nav_stub({"ZZ9999": (s, None)}))
    out = ND.build_nav_table([fund(ccy="USD"), fund(ccy="TWD")])
    assert out["rows"] == [] and out["withheld"] == {"ZZ9999": ND.WITHHELD_CCY_CONFLICT}


def test_nav_同一檔多列持倉_只取數一次(monkeypatch):
    calls = []
    s = _series([("2026-09-01", 10.0)])
    monkeypatch.setattr(ND, "fetch_nav_with_error", _nav_stub({"ZZ9999": (s, None)}, calls))
    out = ND.build_nav_table([fund(), fund(), fund(ccy=None)])
    assert calls == [("ZZ9999", "")] and len(out["rows"]) == 1


def test_nav_同一檔給了不同full_key_不取數不寫(monkeypatch):
    monkeypatch.setattr(ND, "fetch_nav_with_error", _forbid("fetch_nav_with_error"))
    out = ND.build_nav_table([fund(full_key="A1"), fund(full_key="A2")])
    assert out["rows"] == [] and out["withheld"] == {"ZZ9999": ND.WITHHELD_INPUT_CONFLICT}


def test_nav_沒給full_key_當場炸_不拿fund_code去猜():
    with pytest.raises(ValueError):
        ND.build_nav_table([{"fund_code": "ZZ9999"}])


# ═══════════════════════ nav：退回預存舊序列（49 §2.8／§4.3）═══════════════════════

def test_nav_預存舊序列_fetched_at改取cache_updated_at_stale照記():
    s = _series([("2026-04-22", 8.7848), ("2026-04-23", 8.8005)],
                source="GitHubActions:cache/nav/TLZF9.json",
                fetched_at="2026-10-02T01:00:00+00:00",          # 讀檔當下，不是取得時間
                cache_updated_at="2026-07-22T04:31:29.432936+00:00",
                nav_quality={"stale": True, "usable": True})
    out = ND.rows_from_nav_series("TLZF9", s, None, holding_ccys={"USD"})
    assert {r["fetched_at"] for r in out["rows"]} == {"2026-07-22T04:31:29.432936+00:00"}
    assert all(r["is_estimated"] is False for r in out["rows"])
    assert out["provenance"]["cache_fallback"] is True and out["provenance"]["stale"] is True


def test_nav_預存舊序列沒有cache_updated_at_整批不寫():
    s = _series([("2026-04-23", 8.8005)], source="GitHubActions:cache/nav/TLZF9.json",
                fetched_at="2026-10-02T01:00:00+00:00")
    out = ND.rows_from_nav_series("TLZF9", s, None, holding_ccys={"USD"})
    assert out["rows"] == [] and out["withheld"] == ND.WITHHELD_FETCHED_AT_MISSING


def test_nav_只帶nav_quality也算預存舊序列():
    s = _series([("2026-04-23", 8.8)], fetched_at="2026-10-02T01:00:00+00:00",
                nav_quality={"stale": False})
    out = ND.rows_from_nav_series("TLZF9", s, None, holding_ccys={"USD"})
    assert out["rows"] == [] and out["provenance"]["cache_fallback"] is True


# ═══════════════════════ dividend ═══════════════════════

def _divs(*rows, source="MoneyDJ:fetch_div:ZZ9999", fetched=_FETCHED, currency=None):
    out = []
    for d, amt in rows:
        item = {"date": d, "amount": amt, "source": source, "fetched_at": fetched}
        if currency is not None:
            item["currency"] = currency
        out.append(item)
    return out


def test_dividend_除息日語意未查證時_不取數_全部pending(monkeypatch):
    assert ND.DIV_DATE_IS_EX_DATE_VERIFIED is False
    monkeypatch.setattr(ND, "fetch_div_with_error", _forbid("fetch_div_with_error"))
    out = ND.build_dividend_table([fund()])
    assert out["rows"] == [] and out["errors"] == {}
    assert out["pending"] == {"ZZ9999": ND.PENDING_DIV_DATE_SEMANTICS}


def test_dividend_MoneyDJ形狀沒有幣別_整批不寫_不沿用持倉幣別(monkeypatch):
    monkeypatch.setattr(ND, "DIV_DATE_IS_EX_DATE_VERIFIED", True)
    items = _divs(("2026-09-01", 0.05), ("2026-08-01", 0.05))
    monkeypatch.setattr(ND, "fetch_div_with_error", lambda fk, portal="": (items, None))
    out = ND.build_dividend_table([fund(ccy="USD")])          # 持倉有 USD 也不得拿來用
    assert out["rows"] == []
    assert out["withheld"] == {"ZZ9999": ND.WITHHELD_CCY_NOT_SOURCE_REPORTED}
    assert out["fetched"] == {"ZZ9999": 2}


def test_dividend_來源自報幣別時_逐欄照44_div_kind為unknown_pay_date為空():
    out = ND.rows_from_dividends("ZZ9999", _divs(("2026-09-01", 0.05), currency="USD"), None)
    assert out["rows"] == [_div_row()]
    assert [list(r) for r in out["rows"]] == [[n for n, _t, _x in contract.DIVIDEND_FIELDS]]
    assert out["provenance"]["source"] == "MoneyDJ:fetch_div:ZZ9999"


def test_dividend_配息為零照寫_負數不寫():
    out = ND.rows_from_dividends(
        "ZZ9999", _divs(("2026-09-01", 0.0), ("2026-08-01", -0.01), currency="USD"), None)
    assert [(r["ex_date"], r["div_per_unit_orig_ccy"]) for r in out["rows"]] == [("2026-09-01", 0.0)]
    assert any("為負 1 筆" in t for t in out["skipped"])


def test_dividend_全NaN_一列都不寫():
    out = ND.rows_from_dividends("ZZ9999", _divs(("2026-09-01", float("nan")), currency="USD"), None)
    assert out["rows"] == [] and any("非有限數值" in t for t in out["skipped"])


def test_dividend_空清單沒有原因_不是錯誤_如實記錄():
    out = ND.rows_from_dividends("ZZ9999", [], None)
    assert out["rows"] == [] and out["error"] is None and out["skipped"]


def test_dividend_取數失敗_原文逐字進errors(monkeypatch):
    monkeypatch.setattr(ND, "DIV_DATE_IS_EX_DATE_VERIFIED", True)
    msg = "fetch_div('ZZ9999') 所有配息網址取數或解析失敗:\nhttps://x → 取數失敗(kind=timeout)"
    monkeypatch.setattr(ND, "fetch_div_with_error", lambda fk, portal="": ([], msg))
    out = ND.build_dividend_table([fund()])
    assert out["errors"] == {"ZZ9999": msg} and out["rows"] == []


def test_dividend_L1拋例外_轉成型別名加原文(monkeypatch):
    monkeypatch.setattr(ND, "DIV_DATE_IS_EX_DATE_VERIFIED", True)

    def boom(fk, portal=""):
        raise ValueError("schema bad")
    monkeypatch.setattr(ND, "fetch_div_with_error", boom)
    assert ND.build_dividend_table([fund()])["errors"] == {"ZZ9999": "ValueError: schema bad"}


def test_dividend_fetched_at沒有時區_不寫_不以當下時間補():
    out = ND.rows_from_dividends(
        "ZZ9999", _divs(("2026-09-01", 0.05), currency="USD", fetched="2026-09-25T06:00:00"), None)
    assert out["rows"] == [] and out["withheld"] == ND.WITHHELD_FETCHED_AT_MISSING


def test_dividend_同日同額寫一列_同日不同額全不寫():
    same = ND.rows_from_dividends(
        "ZZ9999", _divs(("2026-09-01", 0.05), ("2026-09-01", 0.05), currency="USD"), None)
    assert len(same["rows"]) == 1
    diff = ND.rows_from_dividends(
        "ZZ9999", _divs(("2026-09-01", 0.05), ("2026-09-01", 0.07), currency="USD"), None)
    assert diff["rows"] == [] and any("不同配息 2 筆" in t for t in diff["skipped"])


def test_dividend_日期格式不符不寫():
    out = ND.rows_from_dividends("ZZ9999", _divs(("2026/09/01", 0.05), currency="USD"), None)
    assert out["rows"] == [] and any("YYYY-MM-DD" in t for t in out["skipped"])


# ═══════════════════════ 範圍：只讀、不碰 UI、不另疊快取 ═══════════════════════

def test_範圍_本檔沒有寫入函式_也沒有快取裝飾():
    public = [n for n in dir(ND) if not n.startswith("_") and callable(getattr(ND, n))]
    assert "build_nav_table" in public    # 空掃防呆
    for word in ("write", "save", "append", "update", "delete", "put"):
        assert not [n for n in public if word in n.lower()], word
    src = (_ROOT / "services" / "v2_tables" / "nav_dividend.py").read_text(encoding="utf-8")
    for token in ("cache_data", "_ttl_cache", "_daily_cache", "lru_cache", "nav_history_gs", "gspread"):
        assert token not in re.sub(r'(?s)""".*?"""', "", src), token


def test_範圍_L1快取仍是daily_cache_本層沒有疊第二層():
    from repositories.fund import nav_metrics
    assert ND.fetch_nav_with_error is nav_metrics.fetch_nav_with_error
    assert ND.fetch_div_with_error is nav_metrics.fetch_div_with_error
    assert hasattr(nav_metrics.fetch_nav, "cache_clear")
    assert hasattr(nav_metrics.fetch_div, "cache_clear")


def test_數值_淨值保留原精度不四捨五入():
    out = ND.rows_from_nav_series("ZZ9999", _series([("2026-09-01", 8.80051234)]), None,
                                  holding_ccys={"USD"})
    assert math.isclose(out["rows"][0]["nav_orig_ccy"], 8.80051234, rel_tol=0, abs_tol=0)



# ═══════════════════════ 第二輪回修 ═══════════════════════
# 必修 1：非日期的索引不得被寫成假日期

def _raw_series(values, index, **attrs):
    s = pd.Series(values, index=index, dtype=object)
    s.attrs.update({"source": _LIVE_SOURCE, "fetched_at": _FETCHED})
    s.attrs.update(attrs)
    return s


@pytest.mark.parametrize("index, reason", [
    (pd.RangeIndex(2), "型別不是日期"),
    ([0, 1], "型別不是日期"),
    (["Sep 18", "Sep 19"], "字串不是 YYYY-MM-DD"),
    (["09/10/2026", "09/11/2026"], "字串不是 YYYY-MM-DD"),
    (["2026-9-1", "2026-09-1"], "字串不是 YYYY-MM-DD"),
    ([1.5, 2.5], "型別不是日期"),
])
def test_必修1_非日期索引一律不寫_理由寫明(index, reason):
    out = ND.rows_from_nav_series("ZZ9999", _raw_series([10.0, 10.1], index), None,
                                  holding_ccys={"USD"}, now=NOW)
    assert out["rows"] == [], index
    assert any(reason in t and "2 筆" in t for t in out["skipped"]), out["skipped"]
    assert not [r for r in out["rows"] if r["nav_date"] in ("1970-01-01", "0001-09-18")]


def test_必修1_三種合格日期都收():
    idx = [pd.Timestamp("2026-09-01"), dt.date(2026, 9, 2), "2026-09-03"]
    out = ND.rows_from_nav_series("ZZ9999", _raw_series([10.0, 10.1, 10.2], idx), None,
                                  holding_ccys={"USD"}, now=NOW)
    assert [r["nav_date"] for r in out["rows"]] == ["2026-09-01", "2026-09-02", "2026-09-03"]
    assert out["skipped"] == []


def test_必修1_單一datetime值不收_pd把datetime索引轉成Timestamp則照收():
    # 單點檢查：`_date_value` 對 datetime.datetime（非 pd.Timestamp）不收。
    assert ND._date_value(dt.datetime(2026, 9, 1))[0] is None
    # pandas 建索引時會把 datetime 轉成 Timestamp —— 那是 L1 的真實形狀，照收。
    out = ND.rows_from_nav_series("ZZ9999", _raw_series([10.0], [dt.datetime(2026, 9, 1)]), None,
                                  holding_ccys={"USD"}, now=NOW)
    assert [r["nav_date"] for r in out["rows"]] == ["2026-09-01"]


def test_必修1_NaT不寫():
    out = ND.rows_from_nav_series("ZZ9999", _raw_series([10.0], [pd.NaT]), None,
                                  holding_ccys={"USD"}, now=NOW)
    assert out["rows"] == [] and any("NaT" in t for t in out["skipped"])


# 必修 2：幣別衝突不得被格式不對的值藏掉

@pytest.mark.parametrize("source, holdings", [
    (None, ["twd", "USD"]),
    ("eur", ["USD"]),
    ("EUR ", ["USD"]),
    (None, [840, "USD"]),
])
def test_必修2_格式不對但意思不同_判衝突(source, holdings):
    s = _series([("2026-09-01", 10.0)], currency=source)
    out = ND.rows_from_nav_series("ZZ9999", s, None, holding_ccys=holdings, now=NOW)
    assert out["rows"] == []
    assert out["withheld"] == ND.WITHHELD_CCY_CONFLICT


def test_必修2_意思相同時用合格原值_不改寫():
    s = _series([("2026-09-01", 10.0)], currency="usd ")
    out = ND.rows_from_nav_series("ZZ9999", s, None, holding_ccys=["USD", "usd"], now=NOW)
    assert [r["ccy"] for r in out["rows"]] == ["USD"]
    assert out["provenance"]["ccy_source"] == "holding_user_input"


def test_必修2_格式不對的值單獨出現_維持缺():
    for alone in (["twd"], ["Usd "]):
        out = ND.rows_from_nav_series("ZZ9999", _series([("2026-09-01", 10.0)]), None,
                                      holding_ccys=alone, now=NOW)
        assert out["withheld"] == ND.WITHHELD_CCY_MISSING, alone


# 3：未來與過舊

def test_3_fetched_at晚於當下_整批不寫_代碼與理由正確():
    s = _series([("2026-09-01", 10.0)], fetched_at="2026-10-05T00:00:00+00:00")
    out = ND.rows_from_nav_series("ZZ9999", s, None, holding_ccys={"USD"}, now=NOW)
    assert out["rows"] == [] and out["withheld"] == ND.WITHHELD_FETCHED_AT_FUTURE
    assert any("晚於當下" in t for t in out["skipped"])


def test_3_nav_date未來或1900以前不寫_台灣當日照收():
    idx = ["1899-12-31", "1900-01-01", "2026-10-01", "2026-10-02"]   # NOW 的台灣日期是 2026-10-01
    out = ND.rows_from_nav_series("ZZ9999", _raw_series([1.0, 2.0, 3.0, 4.0], idx), None,
                                  holding_ccys={"USD"}, now=NOW)
    assert [r["nav_date"] for r in out["rows"]] == ["1900-01-01", "2026-10-01"]
    assert any("早於 1900-01-01 1 筆" in t for t in out["skipped"])
    assert any("晚於當下的台灣日期 2026-10-01 1 筆" in t for t in out["skipped"])


def test_3_ex_date未來或1900以前不寫_fetched_at未來不寫():
    items = _divs(("1899-01-01", 0.1), ("2026-10-02", 0.1), ("2026-09-01", 0.1), currency="USD")
    out = ND.rows_from_dividends("ZZ9999", items, None, now=NOW)
    assert [r["ex_date"] for r in out["rows"]] == ["2026-09-01"]
    future = _divs(("2026-09-01", 0.1), currency="USD", fetched="2027-01-01T00:00:00+00:00")
    out2 = ND.rows_from_dividends("ZZ9999", future, None, now=NOW)
    assert out2["rows"] == [] and out2["withheld"] == ND.WITHHELD_FETCHED_AT_FUTURE


def test_3_門檻是具名常數():
    assert ND.MIN_VALID_DATE == dt.date(1900, 1, 1)
    assert ND.FETCHED_AT_MAX_FUTURE_SEC == 0


# 4：L1 回傳型別不對

@pytest.mark.parametrize("bad", [None, "2026-09-01", [10.0, 10.1], {"2026-09-01": 10.0}])
def test_4_nav型別不對_進errors_不是fetched_at_missing(bad):
    out = ND.rows_from_nav_series("ZZ9999", bad, None, holding_ccys={"USD"}, now=NOW)
    assert out["error"].startswith(ND.TYPE_ERROR_PREFIX)
    assert out["withheld"] is None and out["fetched"] == 0


@pytest.mark.parametrize("bad", [None, "abcdef", {"date": "2026-09-01"}, ("x",)])
def test_4_dividend型別不對_進errors_字串不逐字元計數(bad):
    out = ND.rows_from_dividends("ZZ9999", bad, None, now=NOW)
    assert out["error"].startswith(ND.TYPE_ERROR_PREFIX)
    assert out["fetched"] == 0 and out["withheld"] is None


def test_4_某一檔回非二元組_只有那一檔進errors_其他照跑(monkeypatch):
    ok = _series([("2026-09-01", 10.0)])

    def fake(full_key, portal=""):
        return {"BAD": ok, "BAD3": (ok, None, "x"), "ZZ9999": (ok, None)}[full_key]
    monkeypatch.setattr(ND, "fetch_nav_with_error", fake)
    out = ND.build_nav_table([fund(code="BAD", full_key="BAD"), fund(code="BAD3", full_key="BAD3"),
                              fund()], now=NOW)
    assert set(out["errors"]) == {"BAD", "BAD3"}
    assert all(v.startswith(ND.TYPE_ERROR_PREFIX) for v in out["errors"].values())
    assert [r["fund_code"] for r in out["rows"]] == ["ZZ9999"]


def test_4_dividend某一檔回非二元組_只有那一檔進errors(monkeypatch):
    monkeypatch.setattr(ND, "DIV_DATE_IS_EX_DATE_VERIFIED", True)
    good = _divs(("2026-09-01", 0.1), currency="USD")

    def fake(full_key, portal=""):
        return good if full_key == "BAD" else (good, None)
    monkeypatch.setattr(ND, "fetch_div_with_error", fake)
    out = ND.build_dividend_table([fund(code="BAD", full_key="BAD"), fund()], now=NOW)
    assert list(out["errors"]) == ["BAD"] and [r["fund_code"] for r in out["rows"]] == ["ZZ9999"]


# 5：bool 不算數字

def test_5_bool淨值與bool配息不寫():
    out = ND.rows_from_nav_series("ZZ9999", _raw_series([True, 10.0], ["2026-09-01", "2026-09-02"]),
                                  None, holding_ccys={"USD"}, now=NOW)
    assert [r["nav_date"] for r in out["rows"]] == ["2026-09-02"]
    assert any("布林值" in t and "1 筆" in t for t in out["skipped"])
    divs = _divs(("2026-09-01", True), ("2026-08-01", 0.1), currency="USD")
    out2 = ND.rows_from_dividends("ZZ9999", divs, None, now=NOW)
    assert [r["ex_date"] for r in out2["rows"]] == ["2026-08-01"]
    assert any("布林值" in t for t in out2["skipped"])


# 6：skipped 計數正確

def test_6_同日一筆NaN一筆有效_計數分開寫():
    idx = ["2026-09-01", "2026-09-01", "2026-09-02"]
    out = ND.rows_from_nav_series("ZZ9999", _raw_series([float("nan"), 10.0, 10.5], idx), None,
                                  holding_ccys={"USD"}, now=NOW)
    assert [r["nav_date"] for r in out["rows"]] == ["2026-09-02"]     # 丟不丟照原規則：該日整天不寫
    assert "淨值非有限數值 1 筆不寫" in out["skipped"]
    assert "同一日期另有無效淨值，連帶 1 筆有效值不寫" in out["skipped"]


# 7：full_key 前後帶空白就 raise

@pytest.mark.parametrize("key", [" ZZ9999", "ZZ9999 ", "ZZ9999\n"])
def test_7_full_key前後帶空白就raise(key):
    with pytest.raises(ValueError):
        ND.build_nav_table([fund(full_key=key)])
    with pytest.raises(ValueError):
        ND.build_dividend_table([fund(full_key=key)])
