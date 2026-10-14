# -*- coding: utf-8 -*-
"""`services/v2_tables/market_indicator.py` 非美元幣別的匯率鍵（49 §6.1 Q9；fast lane，不打網路）。

依據：客戶 2026-09-26 同意 Q9「新增對應幣別的匯率鍵，由 L2 轉換層直接呼叫既有的 L1
`repositories/macro/yf.py::fetch_yf_close`（例：`EURTWD=X`）」；觀測日規則與美元同一條、同一個閘門
（`FX_OBS_DATE_RULE_VERIFIED`，2026-10-13 仍未驗證 → 不取數、不寫列）。

L1 一律以替身注入（monkeypatch 模組屬性）。
"""

from __future__ import annotations

import pandas as pd
import pytest

from services.v2_tables import market_indicator as mi

_FETCHED = "2026-09-25T06:00:00+00:00"


def _series(values, dates, *, ticker, exchange_tz="Europe/London"):
    """L1 回傳的替身；2026-10-13 起帶來源自報的交易所時區（匯率為 `Europe/London`，探測報告實測）。"""
    s = pd.Series(values, index=pd.DatetimeIndex([pd.Timestamp(d) for d in dates]), dtype=float, name=ticker)
    s.attrs["fetched_at"] = _FETCHED
    s.attrs["source"] = f"Yahoo:{ticker}"
    if exchange_tz is not None:
        s.attrs["exchange_tz"] = exchange_tz
    return s


def _stub(table):
    calls = []

    def fake(ticker, *args, **kwargs):
        calls.append(ticker)
        value = table[ticker]
        if isinstance(value, BaseException):
            raise value
        return value

    fake.calls = calls
    return fake


def _forbid(*args, **kwargs):
    raise AssertionError("閘門關閉時不得取數")


# ═══════════════════════ 鍵名、Yahoo 代碼、單位 ═══════════════════════


def test_美元的鍵與代碼與INDICATOR_SPECS那一格相同():
    assert mi.fx_indicator_key("USD") == "fx_twd_per_usd"
    assert mi.fx_yahoo_ticker("USD") == mi.INDICATOR_SPECS["fx_twd_per_usd"]["source"][1]
    assert mi.fx_value_unit("USD") == mi.INDICATOR_SPECS["fx_twd_per_usd"]["value_unit"]


@pytest.mark.parametrize("ccy, key, ticker", [
    ("EUR", "fx_twd_per_eur", "EURTWD=X"),
    ("JPY", "fx_twd_per_jpy", "JPYTWD=X"),
    ("ZAR", "fx_twd_per_zar", "ZARTWD=X"),
])
def test_非美元的鍵與代碼(ccy, key, ticker):
    assert mi.fx_indicator_key(ccy) == key
    assert mi.fx_yahoo_ticker(ccy) == ticker   # 方向「新臺幣／該幣」，與 USDTWD=X 同向
    assert mi.fx_value_unit(ccy) == f"新臺幣／{ccy}"


@pytest.mark.parametrize("bad", ["TWD", "eur", "EU", "EURO", "", None, 978])
def test_新臺幣與不合ISO的幣別一律炸(bad):
    with pytest.raises(ValueError):
        mi.fx_indicator_key(bad)
    with pytest.raises(ValueError):
        mi.fx_yahoo_ticker(bad)


@pytest.mark.parametrize("ccy", ["EUR", "JPY", "AUD", "ZAR", "CNY", "USD"])
def test_ui_v2的字面鏡像與L2逐幣相同(ccy):
    """`ui_v2/alo/logic.py::fx_key_for` 是 `fx_indicator_key` 的鏡像（ui_v2 不得 import services）。"""
    from ui_v2.alo import logic
    assert logic.fx_key_for(ccy) == mi.fx_indicator_key(ccy)
    assert logic.FX_KEY_PREFIX == mi.FX_KEY_PREFIX
    assert logic.fx_key_for("USD") == logic.FX_KEY


# ═══════════════════════ 閘門（與美元同一個）═══════════════════════


def test_閘門關閉_不取數_不寫列_pending與美元同一個代碼_不進errors(monkeypatch):
    assert mi.FX_OBS_DATE_RULE_VERIFIED is False
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", _forbid)
    out = mi.build_fx_indicator_table(["EUR", "JPY", "EUR"])
    assert out["rows"] == [] and out["errors"] == {} and out["fetched"] == {}
    assert out["pending"] == {"fx_twd_per_eur": mi.PENDING_FX_OBS_DATE_RULE,
                              "fx_twd_per_jpy": mi.PENDING_FX_OBS_DATE_RULE}
    assert "EURTWD=X" in out["skipped"]["fx_twd_per_eur"][0]


# 2026-10-14：匯率走「前一交易日收盤」語意＋最少根數門檻（`FX_MIN_REFERENCE_VOTES`，判讀 A 的 A1）；
# 經 builder 的例子需要足夠根數。夏令倫敦 00:00 ＝ UTC 前一天 23:00（探測報告實測）。
_EUR_STAMPS = [(pd.Timestamp(d) - pd.Timedelta(hours=1)).isoformat(sep=" ")
               for d in pd.bdate_range(end="2026-09-23", periods=24)]
_EUR_VALUES = [34.0 + i * 0.01 for i in range(len(_EUR_STAMPS))]


def test_閘門打開_取EURTWD並套與美元同一條規則(monkeypatch):
    monkeypatch.setattr(mi, "FX_OBS_DATE_RULE_VERIFIED", True)
    # 2026-10-13：時間戳改用匯率日線的真實形狀（夏令時倫敦 00:00 ＝ UTC 前一天 23:00；探測報告實測）。
    # ~~舊例 `["2026-09-22", "2026-09-23 23:00:00"]` 取世界協調時間日期~~ → 新規則取交易所時區（倫敦）日期；
    # 舊例兩根的倫敦當地時刻不同（01:00／00:00），在新規則下會因「當地時刻不一致」整批不寫，故換例（不是漏刪）。
    # ~~`dates = ["2026-09-21 23:00:00", "2026-09-22 23:00:00"]`，期望觀測日 09-22、09-23~~ → 2026-10-14（客戶裁示
    # 前一交易日語意＋A1 門檻；有意識的更正，不是漏刪）：兩根不足門檻，改 24 根；最後兩根的日 K 日期是 09-22（二）、
    # 09-23（三），觀測日取前一個平日 ⇒ 09-21、09-22；首根日 K 日期 08-21（五）→ 08-20。
    fake = _stub({"EURTWD=X": (_series(_EUR_VALUES, _EUR_STAMPS, ticker="EURTWD=X"), None)})
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", fake)
    out = mi.build_fx_indicator_table(["EUR"])
    assert fake.calls == ["EURTWD=X"]
    assert out["pending"] == {} and out["errors"] == {} and out["fetched"] == {"fx_twd_per_eur": 24}
    got = [(r["indicator_key"], r["obs_date"], r["value_num"], r["value_unit"]) for r in out["rows"]]
    assert len(got) == 24
    assert got[0] == ("fx_twd_per_eur", "2026-08-20", 34.0, "新臺幣／EUR")
    assert got[-2:] == [("fx_twd_per_eur", "2026-09-21", _EUR_VALUES[-2], "新臺幣／EUR"),
                        ("fx_twd_per_eur", "2026-09-22", _EUR_VALUES[-1], "新臺幣／EUR")]
    same_rule, _e, _s = mi.rows_from_daily_close(
        "fx_twd_per_eur", _series(_EUR_VALUES, _EUR_STAMPS, ticker="EURTWD=X"),
        None, value_unit="新臺幣／EUR", obs_date_rule=mi.OBS_DATE_PREV_WEEKDAY)
    assert same_rule == out["rows"]


def test_閘門打開_取數失敗原文照放errors_不寫列(monkeypatch):
    monkeypatch.setattr(mi, "FX_OBS_DATE_RULE_VERIFIED", True)
    monkeypatch.setattr(mi, "fetch_yf_close_with_error",
                        _stub({"EURTWD=X": (pd.Series(dtype=float), "fetch_url returned None: EURTWD=X")}))
    out = mi.build_fx_indicator_table(["EUR"])
    assert out["rows"] == []
    assert out["errors"] == {"fx_twd_per_eur": "fetch_url returned None: EURTWD=X"}
    assert out["fetched"] == {"fx_twd_per_eur": 0}


def test_閘門打開_L1拋例外_轉成型別名與原文_不吞(monkeypatch):
    monkeypatch.setattr(mi, "FX_OBS_DATE_RULE_VERIFIED", True)
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", _stub({"EURTWD=X": RuntimeError("boom")}))
    assert mi.build_fx_indicator_table(["EUR"])["errors"] == {"fx_twd_per_eur": "RuntimeError: boom"}


@pytest.mark.parametrize("ccy", ["USD", "TWD"])
def test_美元與新臺幣不走這裡(ccy, monkeypatch):
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", _forbid)
    with pytest.raises(ValueError):
        mi.build_fx_indicator_table([ccy])


def test_INDICATOR_SPECS七鍵不變_市場總覽頁不受影響():
    assert set(mi.INDICATOR_SPECS) == {"vol_index", "fx_twd_per_usd", "credit_spread_pct", "term_spread_pct",
                                       "policy_rate_pct", "leading_index", "coincident_index"}


def test_出口檢查_欄位或順序不符契約就當場炸(monkeypatch):
    """2026-10-13 稽核 N4：比照 `build_market_indicator_table` 出口前核欄位與順序。"""
    monkeypatch.setattr(mi, "FX_OBS_DATE_RULE_VERIFIED", True)
    monkeypatch.setattr(mi, "fetch_yf_close_with_error",
                        _stub({"EURTWD=X": (_series(_EUR_VALUES, _EUR_STAMPS, ticker="EURTWD=X"), None)}))
    # ~~單根 `["2026-09-22"]`~~ → 2026-10-14：單根不足最少根數門檻、一列都不寫，出口檢查就空轉；改 24 根（不是漏刪）
    real = mi.rows_from_daily_close

    def reordered(*args, **kwargs):
        rows, error, skipped = real(*args, **kwargs)
        return [dict(reversed(list(r.items()))) for r in rows], error, skipped

    monkeypatch.setattr(mi, "rows_from_daily_close", reordered)
    assert real("fx_twd_per_eur", _series(_EUR_VALUES, _EUR_STAMPS, ticker="EURTWD=X"), None,
                value_unit="新臺幣／EUR", obs_date_rule=mi.OBS_DATE_PREV_WEEKDAY)[0]   # 前提：真的有列可檢查
    with pytest.raises(AssertionError, match="欄位與契約不符"):
        mi.build_fx_indicator_table(["EUR"])
