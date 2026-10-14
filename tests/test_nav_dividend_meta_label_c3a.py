# -*- coding: utf-8 -*-
"""C3a：`nav_dividend` 多吃「meta 頁自報幣別」（`declared_ccy` ＋ `declared_ccy_source`）的那一支（fast lane；不打網路）。

hld（持倉手填）路徑零變化由 `tests/test_nav_dividend_golden_c3a.py` 逐位元組證明；本檔只測 meta 那一支：
- `ccy_source` 是呼叫端給的出處字串（配息是 `<出處>_matches_source`，不是幣別值）；
- 使用者可見文案不出現「持倉」，改用暫定字面「來源自報（<來源>）」；
- 判斷規則與 hld 相同：序列／配息宣告的幣別與 meta 不同 → 扣下；配息沒宣告 → 那幾筆不寫；
- `holding_ccy` 與 `declared_ccy` 混用 → ValueError；meta 模式下有列兩種 declared 鍵都沒帶 → ValueError；
- `declared_ccy_source` 白名單（`meta:` 前綴、不撞既有出處值、不以 `_matches_source` 結尾）；
- meta 文案「來源自報（…）」後面接「幣別」時補「的」（hld 字樣一字不動，黃金檔證明）；
- `chain_fetch` 可注入、預設值不變。
"""

from __future__ import annotations

import datetime as dt
import json

import pandas as pd
import pytest

import _a_chain_stub as H
import repositories.fund.sources as S
from repositories.fund import fund_orchestration as FO
from services.v2_tables import nav_dividend as ND

NOW = dt.datetime(2026, 10, 1, 0, 0, tzinfo=dt.timezone.utc)
L1_AT = "2026-09-30T08:00:00+00:00"
META = "meta:MoneyDJ+TDCC"
META_TEXT = "來源自報（MoneyDJ+TDCC）"
_NO_DROP = {"truncated": 0, "filtered": 0, "other_tables": 0}


def _fc_item(day, ccy, *, ccy_field="Currency"):
    return {"date": day, "ex_date": day, "pay_date": day, "amount": 0.04, "yield_pct": 0, "currency": ccy,
            S.DIV_PROVENANCE_KEY: {"parser": S.DIV_PARSER_FUNDCLEAR, "date_field": "ExDividendDate",
                                   "currency_field": ccy_field, "amount_field": "DividendAmount",
                                   "fetched_at": L1_AT}}


def _outcome():
    return {"outcome": FO.DIV_OUTCOME_ROWS, "legacy_inline_parse": False, "none_evidenced": False,
            "sources": [{"source": "FundClear", "parser": S.DIV_PARSER_FUNDCLEAR, "status": S.DIV_STATUS_ROWS,
                         "detail": "", "page_type": "yp010000", "dropped": dict(_NO_DROP)}]}


def _res(code, *, series_attrs=None, items=None, n=10):
    attrs = {"source": "FundClear:GetFundNAV", "fetched_at": L1_AT}
    attrs.update(series_attrs or {})
    return {"full_key": code, "series": H.series(n, start="2026-08-03", attrs=attrs),
            "dividends": items if items is not None else [_fc_item("2026-08-05", "USD"), _fc_item("2026-09-05", "USD")],
            FO.DIVIDENDS_OUTCOME_KEY: _outcome(), "data_source": "FundClear",
            "chain_started_at": "2026-09-30T07:00:00+00:00"}


def _fetch_from(by_code, calls=None):
    """注入用的 `chain_fetch`：A 鏈之後的判讀（`_nav_from_chain`／`_div_from_chain`）全部是真的。"""
    def fetch(chain_code, full_key):
        if calls is not None:
            calls.append((chain_code, full_key))
        res = by_code[chain_code]
        series, error = ND._nav_from_chain(res, "yp010000", chain_code, full_key)
        return series, error, ND._div_from_chain(res, full_key)
    return fetch


def _meta_funds(code, ccy="USD", source=META):
    return [{"fund_code": code, "full_key": code, "chain_code": code, "portal": "",
             "declared_ccy": ccy, "declared_ccy_source": source}]


def _build(funds, by_code, calls=None):
    return ND.build_nav_dividend_tables(funds, now=NOW, chain_fetch=_fetch_from(by_code, calls))


# ═══════════════════════ ccy_source 與標籤 ═══════════════════════

def test_meta_收_ccy_source是出處字串_配息是出處加matches_source():
    out = _build(_meta_funds("MZ01"), {"MZ01": _res("MZ01")})
    nav, div = out["nav"], out["dividend"]
    assert len(nav["rows"]) == 10 and {r["ccy"] for r in nav["rows"]} == {"USD"}
    assert nav["provenance"]["MZ01"]["ccy_source"] == META
    assert [r["ex_date"] for r in div["rows"]] == ["2026-08-05", "2026-09-05"]
    assert {r["ccy"] for r in div["rows"]} == {"USD"}
    assert div["provenance"]["MZ01"]["ccy_source"] == f"{META}_matches_source"
    assert div["provenance"]["MZ01"]["ccy_source"] != "USD_matches_source"   # :1464 的陷阱
    assert div["settled"] == {"MZ01": True}


def test_hld預設_配息ccy_source仍是holding_user_input_matches_source_不是幣別值():
    funds = [{"fund_code": "MZ01", "full_key": "MZ01", "chain_code": "MZ01", "portal": "", "holding_ccy": "USD"}]
    out = _build(funds, {"MZ01": _res("MZ01")})
    assert out["dividend"]["provenance"]["MZ01"]["ccy_source"] == "holding_user_input_matches_source"
    assert out["nav"]["provenance"]["MZ01"]["ccy_source"] == "holding_user_input"


def test_meta與hld_寫出的列與判斷結果相同_只差出處字串():
    hld = _build([{"fund_code": "MZ01", "full_key": "MZ01", "chain_code": "MZ01", "portal": "", "holding_ccy": "USD"}],
                 {"MZ01": _res("MZ01")})
    meta = _build(_meta_funds("MZ01"), {"MZ01": _res("MZ01")})
    for table in ("nav", "dividend"):
        assert meta[table]["rows"] == hld[table]["rows"]
        assert meta[table]["withheld"] == hld[table]["withheld"]
        assert meta[table]["skipped_rows"] == hld[table]["skipped_rows"]


# ═══════════════════════ 文案不出現「持倉」 ═══════════════════════

def _all_text(out) -> str:
    return json.dumps(out, ensure_ascii=False, default=str)


@pytest.mark.parametrize("ccy, attrs, items, nav_code, div_code", [
    ("usd", None, None, ND.WITHHELD_CCY_MISSING, ND.WITHHELD_CCY_MISSING),          # 格式不合
    (None, None, None, ND.WITHHELD_CCY_MISSING, ND.WITHHELD_CCY_MISSING),           # 缺值
    ("USD", {"currency": "EUR"}, None, ND.WITHHELD_CCY_CONFLICT, None),             # 序列宣告不同
    # ~~配息宣告不同 → ND.WITHHELD_CCY_CONFLICT~~ → 2026-10-14 exp C2 修正輪（`49` Q7；有意識的更正，不是漏刪）：
    # meta 模式下「認得出、但不同」改為 `div_ccy_differs`；認不出的仍是 `ccy_conflict`（見檔尾兩條）。
    ("TWD", None, None, None, ND.WITHHELD_DIV_CCY_DIFFERS),                         # 配息宣告不同（認得出）
])
def test_meta_各種扣下_文案沒有持倉_有來源自報字樣(ccy, attrs, items, nav_code, div_code):
    out = _build(_meta_funds("MZ01", ccy), {"MZ01": _res("MZ01", series_attrs=attrs, items=items)})
    assert out["nav"]["withheld"].get("MZ01") == nav_code
    assert out["dividend"]["withheld"].get("MZ01") == div_code
    text = _all_text(out)
    assert "持倉" not in text
    assert META_TEXT in text


# ── 「來源自報（…）」接「幣別」要有「的」（2026-10-14 回修）──

_MISSING_DE = "）幣別"


@pytest.mark.parametrize("ccys", [["x"], [""], ["usd"], ["USD", "EUR"], ["usd", "EUR"], [None], [840]])
def test_meta_各種扣下_文案不出現缺的的串接(ccys):
    funds = [row for c in ccys for row in _meta_funds("MZ01", c)]
    out = _build(funds, {"MZ01": _res("MZ01")})
    text = _all_text(out)
    assert out["nav"]["withheld"] or out["dividend"]["withheld"]
    assert _MISSING_DE not in text, text
    assert "持倉" not in text


@pytest.mark.parametrize("source_ccy, held", [
    ("x", ["x"]), (None, ["x"]), (None, [""]), ("USD", ["EUR"]), (None, ["usd", "USD"]), ("eur", ["eur"])])
def test_meta_resolve_nav_ccy與配息標籤_文案不出現缺的的串接(source_ccy, held):
    _ccy, _src, _code, why = ND.resolve_nav_ccy(source_ccy, held, label_source=META)
    _label, _dcode, dwhy = ND._resolve_div_holding(held, label_source=META)
    for line in (why, dwhy):
        assert _MISSING_DE not in str(line), line


def test_meta_配息標籤缺值與衝突_文案原文():
    assert ND._resolve_div_holding(["x"], label_source=META)[2] == (
        f"{META_TEXT}沒有可用的幣別（{META_TEXT}的幣別：'x'）")
    assert ND._resolve_div_holding([""], label_source=META)[2] == f"{META_TEXT}沒有可用的幣別（{META_TEXT}的幣別：''）"
    assert ND._resolve_div_holding(["USD", "EUR"], label_source=META)[2] == (
        f"{META_TEXT}的幣別意思不一致（'USD', 'EUR'）")


def test_hld_配息標籤文案字樣不變():
    assert ND._resolve_div_holding(["x"])[2] == "持倉列沒有可用的幣別（持倉列幣別：'x'）"
    assert ND._resolve_div_holding(["USD", "EUR"])[2] == "持倉列幣別意思不一致（'USD', 'EUR'）"
    assert ND.resolve_nav_ccy("eur", ["eur"])[3] == (
        "來源未自報幣別、持倉列也沒有可用的幣別（來源自報值不合 ISO 4217：'eur'；持倉列幣別不合 ISO 4217：'eur'）")


def test_meta_非原生報價未宣告_文案沒有持倉():
    ms = {"source": "Morningstar:0P000TEST", S.MS_SECID_ORIGIN_ATTR: S.MS_SECID_FROM_POOL}
    out = _build(_meta_funds("MZ01"), {"MZ01": _res("MZ01", series_attrs=ms)})
    assert out["nav"]["withheld"] == {"MZ01": ND.WITHHELD_CCY_MISSING}
    line = out["nav"]["skipped"]["MZ01"][0]
    assert "持倉" not in line and META_TEXT in line and "Morningstar:0P000TEST" in line


def test_meta_兩筆meta幣別意思不同_淨值與配息都扣下_文案沒有持倉():
    funds = [*_meta_funds("MZ01", "USD"), *_meta_funds("MZ01", "EUR")]
    out = _build(funds, {"MZ01": _res("MZ01")})
    assert out["nav"]["withheld"] == {"MZ01": ND.WITHHELD_CCY_CONFLICT}
    assert out["dividend"]["withheld"] == {"MZ01": ND.WITHHELD_CCY_CONFLICT}
    assert "持倉" not in _all_text(out)
    assert "declared:'USD'" in out["nav"]["skipped"]["MZ01"][0]


def test_meta_resolve_nav_ccy_缺值文案_主詞換成淨值序列():
    ccy, src, code, why = ND.resolve_nav_ccy("eur", ["eur"], label_source=META)
    assert (ccy, src, code) == (None, None, ND.WITHHELD_CCY_MISSING)
    assert why == ("淨值序列未自報幣別、來源自報（MoneyDJ+TDCC）也沒有可用的幣別"
                   "（淨值序列自報值不合 ISO 4217：'eur'；來源自報（MoneyDJ+TDCC）的幣別不合 ISO 4217：'eur'）")
    assert ND.resolve_nav_ccy(None, ["USD"], label_source=META)[:2] == ("USD", META)


def test_meta_出處沒有meta前綴_字樣照原文顯示():
    # `_group_funds` 已拒收沒有 `meta:` 前綴的出處；純函式 `resolve_nav_ccy` 等仍可直接收 `label_source`，字樣照原文
    assert ND._label_words("TDCC:基本資料")["row"] == "來源自報（TDCC:基本資料）"
    assert ND._label_words("TDCC:基本資料")["row_ccy"] == "來源自報（TDCC:基本資料）的"
    assert ND._label_words(META)["row"] == META_TEXT
    hld = ND._label_words(ND.LABEL_SOURCE_HOLDING)
    assert hld["row"] == "持倉列" and hld["row_ccy"] == "持倉列"   # hld 原文「持倉列幣別」不加「的」


def test_meta_去前綴只去開頭一次():
    assert ND._label_words("meta:meta:X")["row"] == "來源自報（meta:X）"
    assert ND._label_words("Xmeta:")["row"] == "來源自報（Xmeta:）"


# ═══════════════════════ 序列／配息宣告的幣別與 meta 不同 → 扣下 ═══════════════════════

def test_meta_序列宣告幣別與meta不同_淨值整檔扣下():
    out = _build(_meta_funds("MZ01", "USD"), {"MZ01": _res("MZ01", series_attrs={"currency": "JPY"})})
    assert out["nav"]["rows"] == []
    assert out["nav"]["withheld"] == {"MZ01": ND.WITHHELD_CCY_CONFLICT}
    assert "即時序列:'JPY'" in out["nav"]["skipped"]["MZ01"][0]
    assert out["nav"]["fetched"]["MZ01"] == 10 and out["nav"]["skipped_rows"]["MZ01"] == 10


def test_meta_配息宣告幣別與meta不同_配息整檔扣下():
    items = [_fc_item("2026-08-05", "USD"), _fc_item("2026-09-05", "EUR")]
    out = _build(_meta_funds("MZ01", "USD"), {"MZ01": _res("MZ01", items=items)})
    assert out["dividend"]["rows"] == []
    # ~~ND.WITHHELD_CCY_CONFLICT~~ → 2026-10-14（`49` Q7）：'EUR' 認得出、與 meta 不同 → `div_ccy_differs`；文案不變。
    assert out["dividend"]["withheld"] == {"MZ01": ND.WITHHELD_DIV_CCY_DIFFERS}
    assert out["dividend"]["skipped"]["MZ01"] == [
        f"配息宣告的幣別與{META_TEXT}的幣別不同或認不出（'EUR'；{META_TEXT} USD）；"
        "不改標籤、不換算，這一檔的配息 2 筆全部不寫"]
    assert len(out["nav"]["rows"]) == 10   # 淨值不受影響


def test_meta_配息沒宣告的那幾筆不寫_其餘照寫():
    items = [_fc_item("2026-08-05", "USD"), _fc_item("2026-09-05", "", ccy_field="")]
    out = _build(_meta_funds("MZ01", "USD"), {"MZ01": _res("MZ01", items=items)})
    assert [r["ex_date"] for r in out["dividend"]["rows"]] == ["2026-08-05"]
    assert out["dividend"]["settled"] == {"MZ01": False}


def test_meta_配息全部沒宣告_ccy_not_source_reported():
    items = [_fc_item("2026-08-05", "", ccy_field=""), _fc_item("2026-09-05", "", ccy_field="")]
    out = _build(_meta_funds("MZ01", "USD"), {"MZ01": _res("MZ01", items=items)})
    assert out["dividend"]["rows"] == []
    assert out["dividend"]["withheld"] == {"MZ01": ND.WITHHELD_CCY_NOT_SOURCE_REPORTED}


def test_meta_累積表閘門開啟時_各段的ccy_source都是meta出處(monkeypatch):
    monkeypatch.setattr(ND, "NAV_HISTORY_PROVENANCE_VERIFIED", True)
    dates = ["2026-07-01", "2026-07-02"]
    hist = pd.Series([9.0, 9.01], index=pd.to_datetime(dates), dtype=float)
    s = pd.concat([hist, H.series(5, start="2026-08-03")])
    s.attrs = {"source": "FundClear:GetFundNAV", "fetched_at": L1_AT, ND.HISTORY_MERGED_ATTR: 2,
               ND.HISTORY_DATES_ATTR: dates,
               ND.HISTORY_RECORDED_AT_ATTR: {d: "2026-07-05T00:00:00+00:00" for d in dates},
               ND.HISTORY_SOURCE_ATTR: "nav_history"}
    out = ND.rows_from_nav_series("MZ01", s, None, holding_ccys=["USD"], now=NOW, label_source=META)
    assert len(out["rows"]) == 7
    assert out["provenance"]["ccy_source"] == META


def test_meta_累積表閘門關閉_即時那一段的ccy_source是meta出處():
    dates = ["2026-07-01"]
    s = pd.concat([pd.Series([9.0], index=pd.to_datetime(dates), dtype=float), H.series(5, start="2026-08-03")])
    s.attrs = {"source": "FundClear:GetFundNAV", "fetched_at": L1_AT, ND.HISTORY_MERGED_ATTR: 1,
               ND.HISTORY_DATES_ATTR: dates, ND.HISTORY_RECORDED_AT_ATTR: {}, ND.HISTORY_SOURCE_ATTR: "nav_history"}
    out = ND.rows_from_nav_series("MZ01", s, None, holding_ccys=["USD"], now=NOW, label_source=META)
    assert len(out["rows"]) == 5 and out["provenance"]["ccy_source"] == META


# ═══════════════════════ 輸入檢查 ═══════════════════════

def test_混用holding_ccy與declared_ccy_ValueError_不同列():
    funds = [*_meta_funds("MZ01"),
             {"fund_code": "MZ02", "full_key": "MZ02", "chain_code": "MZ02", "portal": "", "holding_ccy": "USD"}]
    with pytest.raises(ValueError, match="不混用"):
        _build(funds, {})


def test_混用holding_ccy與declared_ccy_ValueError_同一列():
    funds = [dict(_meta_funds("MZ01")[0], holding_ccy=None)]
    with pytest.raises(ValueError, match="不混用"):
        _build(funds, {})


def test_混用_只給declared_ccy_source也算meta():
    funds = [{"fund_code": "MZ01", "full_key": "MZ01", "chain_code": "MZ01", "portal": "",
              "declared_ccy_source": META, "holding_ccy": "USD"}]
    with pytest.raises(ValueError, match="不混用"):
        _build(funds, {})


@pytest.mark.parametrize("source", [None, "", " meta:X", "meta:X ", 5, ND.LABEL_SOURCE_HOLDING])
def test_declared_ccy_source不合格_ValueError(source):
    with pytest.raises(ValueError, match="declared_ccy_source"):
        _build(_meta_funds("MZ01", source=source), {})


# ── 白名單（2026-10-14 回修）：每一種拒收各一組 ──

@pytest.mark.parametrize("source", ["source_reported", "x", "TDCC:基本資料", "Meta:MoneyDJ", "META:MoneyDJ"])
def test_declared_ccy_source_沒有meta前綴_ValueError(source):
    with pytest.raises(ValueError, match="須以 'meta:' 開頭|不得是既有的出處值"):
        _build(_meta_funds("MZ01", source=source), {})


@pytest.mark.parametrize("source", ["meta:", "meta: MoneyDJ", "meta:\tMoneyDJ"])
def test_declared_ccy_source_前綴後沒有緊接來源名稱_ValueError(source):
    with pytest.raises(ValueError, match="之後須緊接非空白的來源名稱"):
        _build(_meta_funds("MZ01", source=source), {})


@pytest.mark.parametrize("source", ["holding_user_input", "Holding_User_Input", "HOLDING_USER_INPUT",
                                    "meta:holding_user_input", "meta:Holding_User_Input"])
def test_declared_ccy_source_撞holding_user_input_大小寫不分_ValueError(source):
    with pytest.raises(ValueError, match="不得是既有的出處值"):
        _build(_meta_funds("MZ01", source=source), {})


@pytest.mark.parametrize("source", ["source_reported", "Source_Reported", "meta:source_reported",
                                    "meta:SOURCE_REPORTED"])
def test_declared_ccy_source_撞source_reported_大小寫不分_ValueError(source):
    with pytest.raises(ValueError, match="不得是既有的出處值"):
        _build(_meta_funds("MZ01", source=source), {})


@pytest.mark.parametrize("source", ["x_matches_source", "meta:x_matches_source", "meta:MoneyDJ_MATCHES_SOURCE",
                                    "meta:_matches_source"])
def test_declared_ccy_source_以matches_source結尾_ValueError(source):
    with pytest.raises(ValueError, match="_matches_source"):
        _build(_meta_funds("MZ01", source=source), {})


# ~~合法值原列 "meta:TDCC:基本資料"、"meta:FundClear 境外"~~ → 2026-10-14 C2（有意識的更正，不是漏刪；決策者：AI 總管；
# 依據 #959 非阻擋項）：白名單收緊為「前綴後須為 ASCII 英數段以 + 相接」，這兩個改列在下方的拒收組。
@pytest.mark.parametrize("source", ["meta:MoneyDJ", "meta:MoneyDJ+TDCC", "meta:FundClear", "meta:MoneyDJ+TDCC+FundClear"])
def test_declared_ccy_source_合法值照常通過(source):
    out = _build(_meta_funds("MZ01", source=source), {"MZ01": _res("MZ01")})
    assert out["nav"]["provenance"]["MZ01"]["ccy_source"] == source
    assert out["dividend"]["provenance"]["MZ01"]["ccy_source"] == f"{source}_matches_source"


# ── meta 模式下每一列都要明確帶 declared 鍵（2026-10-14 回修）──

def _bare(code):
    return {"fund_code": code, "full_key": code, "chain_code": code, "portal": ""}


@pytest.mark.parametrize("order", ["meta_first", "bare_first"])
def test_meta模式混入兩種鍵都沒帶的列_ValueError_點名該列(order):
    rows = [*_meta_funds("MZ01"), _bare("MZ02")]
    if order == "bare_first":
        rows.reverse()
    with pytest.raises(ValueError, match="MZ02") as exc:
        _build(rows, {})
    assert "MZ01" not in str(exc.value).split("：", 1)[0]


def test_meta模式_同一檔一列有鍵一列沒鍵_也ValueError():
    with pytest.raises(ValueError, match="MZ01.*兩種鍵都沒帶"):
        _build([*_meta_funds("MZ01"), _bare("MZ01")], {})


def test_meta模式_無鍵列只點名一次():
    with pytest.raises(ValueError) as exc:
        _build([*_meta_funds("MZ01"), _bare("MZ02"), _bare("MZ02"), _bare("MZ03")], {})
    assert str(exc.value).startswith("MZ02、MZ03：")


def test_meta模式_無鍵列判定不需要走兩次funds_產生器也可以():
    with pytest.raises(ValueError, match="MZ02"):
        _build(iter([*_meta_funds("MZ01"), _bare("MZ02")]), {})


def test_meta模式_全部明確帶declared_含None_正常():
    funds = [*_meta_funds("MZ01", "USD"), *_meta_funds("MZ02", None),
             {**_bare("MZ03"), "declared_ccy_source": META}]          # 只給出處也算有帶
    out = _build(funds, {c: _res(c) for c in ("MZ01", "MZ02", "MZ03")})
    assert out["nav"]["provenance"]["MZ01"]["ccy_source"] == META
    assert out["nav"]["withheld"] == {"MZ02": ND.WITHHELD_CCY_MISSING, "MZ03": ND.WITHHELD_CCY_MISSING}
    assert out["dividend"]["withheld"] == {"MZ02": ND.WITHHELD_CCY_MISSING, "MZ03": ND.WITHHELD_CCY_MISSING}
    text = _all_text(out)
    assert "持倉" not in text and ND.LABEL_SOURCE_HOLDING not in text


def test_hld_沒有任何列帶declared鍵_沒帶holding_ccy的列照舊不報錯():
    out = _build([_bare("MZ01"), {**_bare("MZ02"), "holding_ccy": "USD"}],
                 {"MZ01": _res("MZ01"), "MZ02": _res("MZ02")})
    assert out["nav"]["withheld"] == {"MZ01": ND.WITHHELD_CCY_MISSING}
    assert out["nav"]["provenance"]["MZ02"]["ccy_source"] == ND.LABEL_SOURCE_HOLDING


def test_同一檔meta出處不同_列為輸入矛盾_不取數():
    calls = []
    funds = [*_meta_funds("MZ01", source="meta:MoneyDJ"), *_meta_funds("MZ01", source="meta:TDCC")]
    out = _build(funds, {"MZ01": _res("MZ01")}, calls)
    assert calls == []
    assert out["nav"]["withheld"] == {"MZ01": ND.WITHHELD_INPUT_CONFLICT}
    assert out["dividend"]["withheld"] == {"MZ01": ND.WITHHELD_INPUT_CONFLICT}
    assert "declared_ccy_source" in out["nav"]["skipped"]["MZ01"][0]


# ═══════════════════════ chain_fetch 注入 ═══════════════════════

def test_注入的chain_fetch被呼叫_參數是chain_code與full_key(monkeypatch):
    monkeypatch.setattr(ND, "fetch_chain_with_error", lambda *a, **k: pytest.fail("注入時不得呼叫預設值"))
    calls = []
    funds = [{"fund_code": "MZ01", "full_key": "MZ01", "chain_code": "MZ01", "portal": "", "holding_ccy": "USD"}]
    out = _build(funds, {"MZ01": _res("MZ01")}, calls)
    assert calls == [("MZ01", "MZ01")]
    assert len(out["nav"]["rows"]) == 10


def test_chain_fetch預設值不變_沒給就呼叫模組層fetch_chain_with_error(monkeypatch):
    import inspect
    assert inspect.signature(ND.build_nav_dividend_tables).parameters["chain_fetch"].default is None
    calls = []
    monkeypatch.setattr(ND, "fetch_chain_with_error", _fetch_from({"MZ01": _res("MZ01")}, calls))
    funds = [{"fund_code": "MZ01", "full_key": "MZ01", "chain_code": "MZ01", "portal": "", "holding_ccy": "USD"}]
    out = ND.build_nav_dividend_tables(funds, now=NOW)
    assert calls == [("MZ01", "MZ01")] and len(out["nav"]["rows"]) == 10


def test_chain_fetch拋例外_照舊轉成兩邊的失敗原文():
    def boom(chain_code, full_key):
        raise RuntimeError("壞了")
    out = ND.build_nav_dividend_tables(_meta_funds("MZ01"), now=NOW, chain_fetch=boom)
    assert out["nav"]["errors"] == {"MZ01": "RuntimeError: 壞了"}
    assert out["dividend"]["errors"] == {"MZ01": "RuntimeError: 壞了"}


def test_chain_fetch不是可呼叫物_ValueError():
    with pytest.raises(ValueError, match="chain_fetch"):
        ND.build_nav_dividend_tables(_meta_funds("MZ01"), now=NOW, chain_fetch="x")


# ── 2026-10-14 C2：前綴後須為 ASCII 英數段以 + 相接（#959 非阻擋項）──

@pytest.mark.parametrize("source", ["meta:TDCC:基本資料", "meta:FundClear 境外", "meta:meta:X", "meta:Money\u200bDJ",
                                    "meta:ＭｏｎｅｙＤＪ", "meta:MoneyDJ+", "meta:+TDCC", "meta:MoneyDJ++TDCC",
                                    "meta:Money_DJ", "meta:MoneyDJ\u200b"])
def test_declared_ccy_source_非英數段以加號相接_ValueError(source):
    with pytest.raises(ValueError, match="ASCII 英數段以 '\\+' 相接"):
        _build(_meta_funds("MZ01", source=source), {})


@pytest.mark.parametrize("source", ["meta:meta:X", "meta:Money\u200bDJ", "TDCC:基本資料"])
def test_公開函式_壞label_source_ValueError(source):
    with pytest.raises(ValueError, match="label_source"):
        ND.resolve_nav_ccy("USD", ["USD"], label_source=source)
    with pytest.raises(ValueError, match="label_source"):
        ND.rows_from_nav_series("MZ01", H.series(3, start="2026-08-03"), None, holding_ccys=["USD"], now=NOW,
                                label_source=source)
    with pytest.raises(ValueError, match="label_source"):   # 有錯誤原文也一樣先擋
        ND.rows_from_nav_series("MZ01", None, "boom", label_source=source)
    with pytest.raises(ValueError, match="label_source"):
        ND.rows_from_chain_dividends("MZ01", {"items": [], "outcome": None, "error": None}, label_source=source)


def test_公開函式_持倉手填與合法meta照常():
    assert ND.resolve_nav_ccy("USD", ["USD"])[:2] == ("USD", "source_reported")
    assert ND.resolve_nav_ccy(None, ["USD"], label_source=META)[:2] == ("USD", META)


# ═══════════════════════ 2026-10-14 exp C2 修正輪：配息幣別「不同」與「認不出」分開（`49` Q7） ═══════════════════════

def test_meta_配息宣告幣別認不出_維持ccy_conflict_不是div_ccy_differs():
    items = [_fc_item("2026-08-05", "USD"), _fc_item("2026-09-05", "美元累積")]   # 認不出（不在別名表、不是 ISO）
    out = _build(_meta_funds("MZ01", "USD"), {"MZ01": _res("MZ01", items=items)})
    assert out["dividend"]["rows"] == []
    assert out["dividend"]["withheld"] == {"MZ01": ND.WITHHELD_CCY_CONFLICT}


def test_meta_配息宣告一筆不同一筆認不出_從嚴_ccy_conflict():
    items = [_fc_item("2026-08-05", "EUR"), _fc_item("2026-09-05", "美元累積")]
    out = _build(_meta_funds("MZ01", "USD"), {"MZ01": _res("MZ01", items=items)})
    assert out["dividend"]["withheld"] == {"MZ01": ND.WITHHELD_CCY_CONFLICT}


def test_hld_配息宣告幣別不同_照舊ccy_conflict_不產生新代碼():
    items = [_fc_item("2026-08-05", "USD"), _fc_item("2026-09-05", "EUR")]
    funds = [{"fund_code": "MZ01", "full_key": "MZ01", "chain_code": "MZ01", "portal": "", "holding_ccy": "USD"}]
    out = _build(funds, {"MZ01": _res("MZ01", items=items)})
    assert out["dividend"]["withheld"] == {"MZ01": ND.WITHHELD_CCY_CONFLICT}
