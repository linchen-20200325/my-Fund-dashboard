# -*- coding: utf-8 -*-
"""UI2 輸出 → AI 輸入前置缺口：離線邊界鎖（B-UI2-AI-INPUT-GAP-OFFLINE-TESTS-1；**tests-only，FAKE，零網路**）。

授權：總管 #1296 comment 7077293452（方案甲，唯一新增本檔）；設計卡 comment 7077068957。

本檔把「UI2 現有資料輸出」與「OneBrain 預期輸入」之間**已驗證／缺契約**的邊界釘成 CI：
- T1 FAKE 市場資料的出處欄位完整（🌍 market_view 每個 domain；market_indicator 每列＋表層狀態）。
- T2 NaN、空表、來源錯誤**不會**變成數值 0。
- T3 Yahoo／FRED 8 條＋FX 1 條序列：本檔**獨立手寫**一張表，逐列比對 (來源, 序列, 實際輸出位置)，位置由真 builder 的輸出觀察；
  每列 RIGHTS／AI USE 一律 NOT VERIFIED（本檔不宣稱任何權利已驗）。`USDTWD=X` 另受 FX 專屬 Gate，單列。
- T4 `FundLookupView` 現階段**沒有** provenance（來源、取得時間、觀測日）——這是**待裁的契約缺口**，
  不是「永遠不准加」；日後加欄位屬 Decision Gate，屆時在同一個 PR 更新本鎖。
- T5 本檔不 import `services.onebrain`；不新增 `test_onebrain_*` 檔（OneBrain 守衛以檔名白名單釘死 4 檔）。

⚠️ 本檔**不**組任何 AI 輸入文字、**不**定義 Digest 形狀、**不**呼叫任何 Provider。
⚠️ 所有序列、日期、數值都是測試內現編的 FAKE（數值刻意取 11.11 起的等差，不像真行情）；沒有任何真實市場資料。
⚠️ 每組都附「可轉紅負控」：把被測條件拿掉，同一支檢查函式必須失敗。
"""
from __future__ import annotations

import ast
import dataclasses
import datetime as dt
import math
import pathlib

import pandas as pd
import pytest

from fund_lookup_support import no_real_network  # noqa: F401 - autouse：所有網路入口換成會 raise 的守衛
from services.v2_tables import market_indicator as mi
from services.v2_tables import market_view as mv
from ui_v3.viewmodels.fund_lookup import (
    FieldStatus,
    FieldView,
    FundLookupView,
    LookupState,
    ProfileFields,
)

REPO = pathlib.Path(__file__).resolve().parents[2]
THIS_FILE = pathlib.Path(__file__).resolve()

FAKE_FETCHED = "2026-10-13T06:00:00+00:00"      # FAKE 取得時間
FAKE_TODAY = dt.date(2026, 10, 13)               # FAKE「今天」（FRED vintage 的查詢下界由它算）
FAKE_FRED_KEY = "fake-offline-key"               # FAKE 金鑰字樣；替身不讀它的內容


def _weekdays(start: str, end: str) -> list:
    return [d.strftime("%Y-%m-%d") for d in pd.bdate_range(start, end)]


FAKE_DATES = _weekdays("2026-10-01", "2026-10-09")      # 7 個平日，都早於 FAKE 取得日（皆已收盤）


def _fake_values(n: int, base: float = 11.11) -> list:
    return [round(base + i * 1.11, 2) for i in range(n)]


# ───────────────────────── FAKE L1 替身（形狀同既有 market 測試） ─────────────────────────

def fake_yahoo(ticker: str, values=None, dates=None, *, exchange_tz: str = "Etc/UTC"):
    dates = FAKE_DATES if dates is None else dates
    values = _fake_values(len(dates)) if values is None else values
    s = pd.Series(values, index=pd.to_datetime(dates), dtype=float, name=ticker)
    s.attrs["fetched_at"] = FAKE_FETCHED
    s.attrs["source"] = f"Yahoo:{ticker}"
    s.attrs["exchange_tz"] = exchange_tz
    return s


def fake_fred_frame(series_id: str, values=None, dates=None):
    """`fetch_fred_with_error` 出口形狀（market_view 用）：fetched_at 是欄位。"""
    dates = FAKE_DATES if dates is None else dates
    values = _fake_values(len(dates), 2.22) if values is None else values
    rows = [{"date": pd.Timestamp(d), "value": v, "realtime_start": pd.Timestamp("2026-10-13"),
             "source": f"FRED:{series_id}", "fetched_at": FAKE_FETCHED} for d, v in zip(dates, values)]
    return pd.DataFrame(rows, columns=["date", "value", "realtime_start", "source", "fetched_at"])


_VINTAGE_NOW = "9999-12-31"


def fake_vintage_frame(values=(3.33, 3.34)):
    """`fetch_fred_vintages_with_error` 出口形狀（market_indicator 的 FRED 三鍵用）。"""
    records = [("2026-08-01", "2026-09-02", _VINTAGE_NOW, values[0]),
               ("2026-09-01", "2026-10-02", _VINTAGE_NOW, values[1])]
    df = pd.DataFrame({
        "date": pd.to_datetime([r[0] for r in records]),
        "value": pd.Series([r[3] for r in records], dtype="float64"),
        "realtime_start": pd.to_datetime([r[1] for r in records]),
        "realtime_end": [r[2] for r in records],
    })
    df.attrs["fetched_at"] = FAKE_FETCHED
    df.attrs["realtime_floor"] = (FAKE_TODAY - dt.timedelta(days=mi.FRED_LOOKBACK_DAYS)).isoformat()
    df.attrs["source"] = "FRED:FAKE:vintages"
    return df


class Recorder:
    """依第一個參數回應的替身；記錄實際被要求的序列代碼（T3 用它對照，而不是讀 production 常數）。"""

    def __init__(self, by_key):
        self.by_key = by_key
        self.calls: list = []

    def __call__(self, key, *args):
        self.calls.append(key)
        result = self.by_key[key]
        if isinstance(result, BaseException):
            raise result
        return result


def view_fakes(*, vix=None, twii=None, gspc=None, fred=None) -> dict:
    yf = Recorder({"^VIX": vix or (fake_yahoo("^VIX"), None),
                   "^TWII": twii or (fake_yahoo("^TWII", exchange_tz="Asia/Taipei"), None),
                   "^GSPC": gspc or (fake_yahoo("^GSPC", exchange_tz="America/New_York"), None)})
    fr = Recorder(fred or {"DGS10": (fake_fred_frame("DGS10"), None), "DGS2": (fake_fred_frame("DGS2"), None)})
    return {"fetch_vix": yf, "fetch_taiex": yf, "fetch_sp500": yf, "fetch_fred": fr, "fred_api_key": FAKE_FRED_KEY}


@pytest.fixture
def indicator_l1(monkeypatch):
    """market_indicator 的兩支 L1 全換成 FAKE 替身；回傳 (yahoo, fred) 兩個 Recorder 供改寫與檢查。"""
    yahoo = Recorder({"^VIX": (fake_yahoo("^VIX"), None)})
    fred = Recorder({sid: (fake_vintage_frame(), None) for sid in ("BAMLH0A0HYM2", "T10Y2Y", "FEDFUNDS")})
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", yahoo)
    monkeypatch.setattr(mi, "fetch_fred_vintages_with_error", fred)
    monkeypatch.setattr(mi, "_utc_today", lambda: FAKE_TODAY)
    return yahoo, fred


# ═══════════════════════ T1：出處欄位完整 ═══════════════════════

#: 本檔手寫的預期出處標籤（不 import production 常數）。
LIVE_VIEW_DOMAINS = {
    "vix": ("Yahoo:^VIX", "index"),
    "taiex": ("Yahoo Finance (^TWII)", "index"),
    "sp500": ("Yahoo Finance (^GSPC)", "index"),
    "us10y": ("FRED (DGS10)", "%"),
    "us2y": ("FRED (DGS2)", "%"),
}
#: market_indicator 第一階段實際取數的四個鍵（FX 受 FX Gate、國發會兩鍵 pending，見 T3）。
LIVE_INDICATOR_KEYS = {"vol_index", "credit_spread_pct", "term_spread_pct", "policy_rate_pct"}


def check_view_provenance(view: dict) -> None:
    """🌍 每個實際取數的 domain：status＝ok，source／fetched_at／obs_date／value_unit 皆有值且與預期相符。"""
    by_key = {d["domain"]: d for d in view["domains"]}
    for key, (source, unit) in LIVE_VIEW_DOMAINS.items():
        d = by_key[key]
        assert d["status"] == mv.STATE_OK, (key, d["status"], d["reason"])
        assert d["source"] == source, (key, d["source"])
        assert d["fetched_at"] == FAKE_FETCHED, (key, d["fetched_at"])
        assert isinstance(d["obs_date"], str) and d["obs_date"], (key, d["obs_date"])
        assert d["value_unit"] == unit, (key, d["value_unit"])
        assert d["points"], key


def check_indicator_provenance(table: dict) -> None:
    """market_indicator：每列有 obs_date／release_date／fetched_at／value_unit／source_tier；
    「狀態」在表層（errors／pending），「來源」由 indicator_key 對回 spec。
    ⚠️ FACT（缺口）：列本身**沒有**來源名欄位，也沒有逐列狀態欄（44 契約八欄如此）；AI 若只拿到列，無法自行回溯來源。"""
    keys = {r["indicator_key"] for r in table["rows"]}
    assert keys == LIVE_INDICATOR_KEYS, keys
    for row in table["rows"]:
        for field in ("obs_date", "release_date", "fetched_at", "value_unit", "source_tier"):
            assert row.get(field) not in (None, ""), (row["indicator_key"], field)
        assert row["fetched_at"] == FAKE_FETCHED
        assert "source" not in row and "status" not in row        # 缺口照實鎖住（見 docstring）
    assert not (LIVE_INDICATOR_KEYS & set(table["errors"])), table["errors"]
    assert not (LIVE_INDICATOR_KEYS & set(table["pending"])), table["pending"]


class TestT1Provenance:
    def test_market_view_FAKE_每個domain出處完整(self):
        view = mv.build_market_view(**view_fakes())
        check_view_provenance(view)

    def test_market_indicator_FAKE_每列出處完整_FEDFUNDS_vintage可離線注入(self, indicator_l1):
        table = mi.build_market_indicator_table(fred_api_key=FAKE_FRED_KEY)
        check_indicator_provenance(table)
        assert any(r["indicator_key"] == "policy_rate_pct" for r in table["rows"])   # FEDFUNDS vintage 非阻塞

    @pytest.mark.parametrize("field", ["source", "fetched_at", "obs_date", "value_unit"])
    def test_負控_view拿掉任一出處欄位_必須失敗(self, field):
        view = mv.build_market_view(**view_fakes())
        view["domains"][0][field] = None
        with pytest.raises(AssertionError):
            check_view_provenance(view)

    @pytest.mark.parametrize("field", ["obs_date", "fetched_at", "value_unit"])
    def test_負控_indicator列拿掉任一出處欄位_必須失敗(self, indicator_l1, field):
        table = mi.build_market_indicator_table(fred_api_key=FAKE_FRED_KEY)
        table["rows"][0][field] = None
        with pytest.raises(AssertionError):
            check_indicator_provenance(table)


# ═══════════════════════ T2：缺值不補 0 ═══════════════════════

def numbers_in_view(view: dict, key: str) -> list:
    d = {x["domain"]: x for x in view["domains"]}[key]
    return [p["value_num"] for p in d["points"]]


def check_no_fabricated_zero(values) -> None:
    """輸入裡沒有任何 0：輸出若出現 0 或非有限數，就是把缺值捏成了數字。"""
    for v in values:
        assert isinstance(v, (int, float)) and math.isfinite(v), v
        assert v != 0, "缺值被補成 0"


class TestT2MissingIsNotZero:
    def test_view_NaN被丟掉_不是補0(self):
        vals = [11.11, float("nan"), 13.33, float("nan"), 15.55, 16.66, 17.77]
        view = mv.build_market_view(**view_fakes(vix=(fake_yahoo("^VIX", vals), None)))
        nums = numbers_in_view(view, "vix")
        assert len(nums) == 5
        check_no_fabricated_zero(nums)

    def test_view_空表與來源錯誤_非ok且沒有任何點(self):
        empty = fake_yahoo("^VIX", [], [])
        view = mv.build_market_view(**view_fakes(vix=(empty, None), twii=(None, "FAKE 來源錯誤"),
                                                 gspc=RuntimeError("FAKE 例外")))
        by = {d["domain"]: d for d in view["domains"]}
        for key in ("vix", "taiex", "sp500"):
            assert by[key]["status"] != mv.STATE_OK and by[key]["points"] == [], key
            assert by[key]["reason"], key

    def test_view_FRED_NaN丟掉_空表非ok(self):
        fred = {"DGS10": (fake_fred_frame("DGS10", [4.1, float("nan"), 4.3, 4.4, 4.5, 4.6, 4.7]), None),
                "DGS2": (fake_fred_frame("DGS2", [], []), None)}
        view = mv.build_market_view(**view_fakes(fred=fred))
        check_no_fabricated_zero(numbers_in_view(view, "us10y"))
        assert len(numbers_in_view(view, "us10y")) == 6
        us2y = {d["domain"]: d for d in view["domains"]}["us2y"]
        assert us2y["status"] != mv.STATE_OK and us2y["points"] == []

    def test_indicator_來源錯誤與空表_該鍵不寫列_錯誤照實留下(self, indicator_l1):
        yahoo, fred = indicator_l1
        yahoo.by_key["^VIX"] = (fake_yahoo("^VIX", [], []), None)
        fred.by_key["FEDFUNDS"] = (None, "FAKE 來源錯誤")
        fred.by_key["T10Y2Y"] = ConnectionError("FAKE 例外")
        table = mi.build_market_indicator_table(fred_api_key=FAKE_FRED_KEY)
        keys = {r["indicator_key"] for r in table["rows"]}
        assert keys == {"credit_spread_pct"}
        assert "policy_rate_pct" in table["errors"] and "term_spread_pct" in table["errors"]
        check_no_fabricated_zero([r["value_num"] for r in table["rows"]])

    def test_indicator_NaN_不補0(self, indicator_l1):
        yahoo, _fred = indicator_l1
        yahoo.by_key["^VIX"] = (fake_yahoo("^VIX", [11.11, float("nan"), 13.33, 14.44, 15.55, 16.66, 17.77]), None)
        table = mi.build_market_indicator_table(fred_api_key=FAKE_FRED_KEY)
        vix = [r["value_num"] for r in table["rows"] if r["indicator_key"] == "vol_index"]
        assert len(vix) == 6
        check_no_fabricated_zero(vix)

    def test_負控_先把NaN補0再餵進來_檢查必須失敗(self):
        vals = pd.Series([11.11, float("nan"), 13.33, 14.44, 15.55, 16.66, 17.77]).fillna(0).tolist()
        view = mv.build_market_view(**view_fakes(vix=(fake_yahoo("^VIX", vals), None)))
        with pytest.raises(AssertionError):
            check_no_fabricated_zero(numbers_in_view(view, "vix"))


# ═══════════════════════ T3：8＋1 序列清單（獨立手寫，逐列對照「來源＋序列＋實際輸出位置」） ═══════════════════════
#
# 2026-11-22 Work QA Must-Fix（#1296 comment 7077712971／總管 7077736106）：舊版只比 (來源, 序列) 集合，
# 兩個 FRED 序列的輸出位置對調時集合不變、守衛不會紅。現改為逐列比 (來源, 序列, 輸出位置)：
# - 預期表 `SERIES_TABLE` 為本檔手寫字面值（不 import production 常數）。
# - 觀察值不讀 production spec、也不從記錄器推導位置：每條序列餵**互不重疊的 FAKE 數值簽章**，
#   跑真 builder 之後，從**輸出**（market_view 的 domain points、market_indicator 的列）看每個位置
#   實際拿到的是哪一組簽章，才回推「哪條序列流到哪個位置」。

NV = "NOT VERIFIED"
VIEW = "market_view"
IND = "market_indicator"
#: 本檔獨立手寫。每列＝一個實際輸出位置（^VIX 有兩個去處，分兩列）。gate：該列另受的專屬 Gate。
SERIES_TABLE = (
    # (來源, 序列, 輸出位置, RIGHTS, AI USE, 專屬 Gate)
    ("Yahoo", "^VIX", (VIEW, "vix"), NV, NV, None),
    ("Yahoo", "^VIX", (IND, "vol_index"), NV, NV, None),
    ("Yahoo", "^TWII", (VIEW, "taiex"), NV, NV, None),
    ("Yahoo", "^GSPC", (VIEW, "sp500"), NV, NV, None),
    ("FRED", "DGS10", (VIEW, "us10y"), NV, NV, None),
    ("FRED", "DGS2", (VIEW, "us2y"), NV, NV, None),
    ("FRED", "T10Y2Y", (IND, "term_spread_pct"), NV, NV, None),
    ("FRED", "BAMLH0A0HYM2", (IND, "credit_spread_pct"), NV, NV, None),
    ("FRED", "FEDFUNDS", (IND, "policy_rate_pct"), NV, NV, None),
    ("Yahoo", "USDTWD=X", (IND, "fx_twd_per_usd"), NV, NV, "FX 觀測日規則 Gate（目前關閉、不取數）"),
)

#: FAKE 數值簽章（互不重疊；只是本檔的輸入，與 production 無關）。
SIGNATURES = {
    (VIEW, ("Yahoo", "^VIX")): _fake_values(7, 11.11),
    (VIEW, ("Yahoo", "^TWII")): _fake_values(7, 21.11),
    (VIEW, ("Yahoo", "^GSPC")): _fake_values(7, 31.11),
    (VIEW, ("FRED", "DGS10")): _fake_values(7, 4.11),
    (VIEW, ("FRED", "DGS2")): [round(3.61 + i * 0.01, 2) for i in range(7)],
    (IND, ("Yahoo", "^VIX")): _fake_values(7, 51.11),
    (IND, ("FRED", "BAMLH0A0HYM2")): [5.51, 5.52],
    (IND, ("FRED", "T10Y2Y")): [0.61, 0.62],
    (IND, ("FRED", "FEDFUNDS")): [3.33, 3.34],
}


def live_rows(table=SERIES_TABLE) -> set:
    return {(src, sid, dest) for src, sid, dest, _r, _a, gate in table if gate is None}


def check_rights_not_claimed(table) -> None:
    for row in table:
        assert row[3] == NV and row[4] == NV, f"{row[1]}：本檔不得宣稱權利或 AI 使用已驗"


def check_rows_match(expected: set, observed: set) -> None:
    """逐列比 (來源, 序列, 輸出位置)。"""
    assert observed == expected, {"production 多出／錯位": observed - expected, "production 沒有": expected - observed}


def _which_series(layer: str, values) -> tuple:
    """輸出某位置拿到的數值 → 唯一一組簽章（同一層內）。對不上或對到兩組都當場失敗。"""
    vals = {round(v, 2) for v in values}
    hits = [key for (lyr, key), sig in SIGNATURES.items() if lyr == layer and vals and vals <= set(sig)]
    assert len(hits) == 1, (layer, sorted(vals), hits)
    return hits[0]


def observe_rows(indicator_l1) -> tuple:
    """跑真 builder（全 FAKE 簽章），從**輸出**觀察 (來源, 序列, 位置)；另回傳實際取數呼叫（看 FX 零呼叫用）。"""
    sig = {key: vals for (lyr, key), vals in SIGNATURES.items() if lyr == VIEW}
    fakes = view_fakes(
        vix=(fake_yahoo("^VIX", sig[("Yahoo", "^VIX")]), None),
        twii=(fake_yahoo("^TWII", sig[("Yahoo", "^TWII")], exchange_tz="Asia/Taipei"), None),
        gspc=(fake_yahoo("^GSPC", sig[("Yahoo", "^GSPC")], exchange_tz="America/New_York"), None),
        fred={"DGS10": (fake_fred_frame("DGS10", sig[("FRED", "DGS10")]), None),
              "DGS2": (fake_fred_frame("DGS2", sig[("FRED", "DGS2")]), None)})
    view = mv.build_market_view(**fakes)
    yahoo, fred = indicator_l1
    yahoo.by_key["^VIX"] = (fake_yahoo("^VIX", SIGNATURES[(IND, ("Yahoo", "^VIX"))]), None)
    for sid in ("BAMLH0A0HYM2", "T10Y2Y", "FEDFUNDS"):
        fred.by_key[sid] = (fake_vintage_frame(tuple(SIGNATURES[(IND, ("FRED", sid))])), None)
    table = mi.build_market_indicator_table(fred_api_key=FAKE_FRED_KEY)

    observed = set()
    for d in view["domains"]:
        if d["points"]:
            src, sid = _which_series(VIEW, [p["value_num"] for p in d["points"]])
            observed.add((src, sid, (VIEW, d["domain"])))
    by_key: dict = {}
    for r in table["rows"]:
        by_key.setdefault(r["indicator_key"], []).append(r["value_num"])
    for key, values in by_key.items():
        src, sid = _which_series(IND, values)
        observed.add((src, sid, (IND, key)))
    calls = {("Yahoo", t) for t in fakes["fetch_vix"].calls + yahoo.calls}
    calls |= {("FRED", s) for s in fakes["fetch_fred"].calls + fred.calls}
    return observed, calls, table


def _swap_fred_destinations(monkeypatch) -> None:
    """記憶體變異（monkeypatch，測試結束自動還原）：對調 credit／term 兩鍵的 FRED 序列；序列集合不變。"""
    specs = {k: dict(v) for k, v in mi.INDICATOR_SPECS.items()}
    specs["credit_spread_pct"]["source"], specs["term_spread_pct"]["source"] = (
        specs["term_spread_pct"]["source"], specs["credit_spread_pct"]["source"])
    monkeypatch.setattr(mi, "INDICATOR_SPECS", specs)


class TestT3SeriesList:
    def test_表格為9條序列_10個輸出位置_8條即時加1條FX(self):
        assert len(SERIES_TABLE) == 10
        assert len({(r[0], r[1]) for r in SERIES_TABLE}) == 9
        assert len({(s, i) for s, i, _d in live_rows()}) == 8
        assert [r[1] for r in SERIES_TABLE if r[5] is not None] == ["USDTWD=X"]

    def test_每列RIGHTS與AI_USE皆為NOT_VERIFIED(self):
        check_rights_not_claimed(SERIES_TABLE)

    def test_逐列_來源序列輸出位置_與真builder輸出一致(self, indicator_l1):
        observed, _calls, _t = observe_rows(indicator_l1)
        check_rows_match(live_rows(), observed)

    def test_指定兩列_BAMLH0A0HYM2到credit_T10Y2Y到term(self, indicator_l1):
        observed, _calls, _t = observe_rows(indicator_l1)
        assert ("FRED", "BAMLH0A0HYM2", (IND, "credit_spread_pct")) in observed
        assert ("FRED", "T10Y2Y", (IND, "term_spread_pct")) in observed

    def test_FX列_Gate關閉_零呼叫_無輸出列_pending(self, indicator_l1):
        observed, calls, table = observe_rows(indicator_l1)
        assert ("Yahoo", "USDTWD=X") not in calls
        assert not any(dest == (IND, "fx_twd_per_usd") for _s, _i, dest in observed)
        assert "fx_twd_per_usd" in table["pending"]
        assert mi.INDICATOR_SPECS["fx_twd_per_usd"]["source"] == ("Yahoo", "USDTWD=X")

    def test_負控_對調credit與term的FRED序列_集合不變但逐列守衛必紅(self, indicator_l1, monkeypatch):
        _swap_fred_destinations(monkeypatch)
        observed, calls, _t = observe_rows(indicator_l1)
        # 序列集合與呼叫集合都沒變（舊版只比這個，所以會漏判）……
        assert {(s, i) for s, i, _d in observed} == {(s, i) for s, i, _d in live_rows()}
        assert ("FRED", "T10Y2Y") in calls and ("FRED", "BAMLH0A0HYM2") in calls
        # ……但逐列守衛必須轉紅，且錯位就是這兩列
        assert ("FRED", "T10Y2Y", (IND, "credit_spread_pct")) in observed
        with pytest.raises(AssertionError):
            check_rows_match(live_rows(), observed)

    def test_負控_預期表多一列或少一列_對照必紅(self, indicator_l1):
        observed, _calls, _t = observe_rows(indicator_l1)
        with pytest.raises(AssertionError):
            check_rows_match(live_rows() | {("Yahoo", "^FAKE", (VIEW, "vix"))}, observed)
        with pytest.raises(AssertionError):
            check_rows_match(live_rows() - {("FRED", "FEDFUNDS", (IND, "policy_rate_pct"))}, observed)

    def test_負控_任一列宣稱已驗_必須失敗(self):
        tampered = list(SERIES_TABLE)
        tampered[0] = tampered[0][:3] + ("VERIFIED",) + tampered[0][4:]
        with pytest.raises(AssertionError):
            check_rights_not_claimed(tampered)


# ═══════════════════════ T4：FundLookupView 缺 provenance（待裁契約缺口） ═══════════════════════

GAP_MESSAGE = ("G4 待裁契約缺口：FundLookupView 目前不帶來源／取得時間／觀測日。這不是永遠禁止新增欄位；"
               "要加 provenance 須先經 Decision Gate，屆時在同一個 PR 更新本鎖。")
PROVENANCE_NAMES = {"source", "sources", "provider", "fetched_at", "observed_at", "obs_date", "as_of", "url", "provenance"}


def field_names(cls) -> set:
    return {f.name for f in dataclasses.fields(cls)}


def check_lookup_view_gap(view_cls=FundLookupView, profile_cls=ProfileFields, field_cls=FieldView) -> None:
    assert field_names(view_cls) == {"state", "input_code", "reason_code", "fields"}, GAP_MESSAGE
    assert field_names(profile_cls) == {"fund_name", "dividend_policy", "inception_on", "mgmt_fee_rate_pct"}, GAP_MESSAGE
    assert field_names(field_cls) == {"status", "value"}, GAP_MESSAGE
    for cls in (view_cls, profile_cls, field_cls):
        assert not (field_names(cls) & PROVENANCE_NAMES), GAP_MESSAGE


class TestT4LookupViewGap:
    def test_FundLookupView目前沒有provenance(self):
        check_lookup_view_gap()

    def test_RESULT實例也只有四個欄位值_沒有來源或日期可讀(self):
        fields = ProfileFields(FieldView(FieldStatus.VALUE, "FAKE 範例基金"), FieldView(FieldStatus.MISSING, None),
                               FieldView(FieldStatus.MISSING, None), FieldView(FieldStatus.MISSING, None))
        view = FundLookupView(LookupState.RESULT, "FAKE01", None, fields)
        assert set(dataclasses.asdict(view)) == {"state", "input_code", "reason_code", "fields"}

    def test_負控_加一個source欄位_鎖必須失敗(self):
        @dataclasses.dataclass(frozen=True)
        class WithSource(FundLookupView):
            source: str = "FAKE"
        with pytest.raises(AssertionError):
            check_lookup_view_gap(view_cls=WithSource)

    def test_負控_FieldView加fetched_at_鎖必須失敗(self):
        @dataclasses.dataclass(frozen=True)
        class WithFetched(FieldView):
            fetched_at: str = "FAKE"
        with pytest.raises(AssertionError):
            check_lookup_view_gap(field_cls=WithFetched)


# ═══════════════════════ T5：本檔不 import OneBrain、不新增 test_onebrain_* ═══════════════════════

AUTHORISED_ONEBRAIN_TESTS = {"test_onebrain_provider_types.py", "test_onebrain_fake_provider.py",
                             "test_onebrain_offline_guard.py", "test_onebrain_evidence_input.py"}
_TARGET = "services" + ".onebrain"          # 拆開拼接：本檔原始碼不留可被誤掃的完整字面 import


def onebrain_references(source: str) -> list:
    """AST：Import／ImportFrom／`from services import onebrain`／import_module 與 __import__ 的字串常數。"""
    hits = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            hits += [a.name for a in node.names if a.name == _TARGET or a.name.startswith(_TARGET + ".")]
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module == _TARGET or node.module.startswith(_TARGET + "."):
                hits.append(node.module)
            elif node.module == "services" and any(a.name == "onebrain" for a in node.names):
                hits.append("services:onebrain")
        elif isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant):
            arg = node.args[0].value
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name in ("import_module", "__import__") and isinstance(arg, str) and arg.startswith(_TARGET):
                hits.append(f"{name}:{arg}")
    return hits


def check_onebrain_test_files(found: set) -> None:
    """正向與負控共用：`tests/` 下 `test_onebrain_*.py` 必須恰為授權的 4 檔。"""
    assert found == AUTHORISED_ONEBRAIN_TESTS, found


def actual_onebrain_test_files() -> set:
    return {p.name for p in (REPO / "tests").rglob("test_onebrain_*.py")}


class TestT5Boundary:
    def test_本檔不import_OneBrain(self):
        assert onebrain_references(THIS_FILE.read_text(encoding="utf-8")) == []

    def test_本檔不是test_onebrain_檔_OneBrain測試仍恰為授權的4檔(self):
        assert not THIS_FILE.name.startswith("test_onebrain_")
        check_onebrain_test_files(actual_onebrain_test_files())

    def test_production不引用本檔(self):
        stem = THIS_FILE.stem
        for root in ("ui_v3", "ui_v2", "ui", "services", "repositories", "infra", "shared"):
            for p in (REPO / root).rglob("*.py"):
                assert stem not in p.read_text(encoding="utf-8"), str(p.relative_to(REPO))

    @pytest.mark.parametrize("snippet", [
        "import " + _TARGET,
        "import " + _TARGET + ".fake_provider as f",
        "from " + _TARGET + " import fake_provider",
        "from services import " + "onebrain",
        "import importlib\nimportlib.import_module('" + _TARGET + "')",
        "__import__('" + _TARGET + ".provider_types')",
    ])
    def test_負控_各種import寫法都被偵測(self, snippet):
        assert onebrain_references(snippet) != []

    def test_對照_合規原始碼不誤報(self):
        assert onebrain_references("import services.v2_tables\nfrom services import v2_domain\nx = 'onebrain'") == []

    def test_負控_多一個test_onebrain_檔名_白名單比對必須失敗(self):
        with pytest.raises(AssertionError):
            check_onebrain_test_files(actual_onebrain_test_files() | {"test_onebrain_extra.py"})
        with pytest.raises(AssertionError):
            check_onebrain_test_files(actual_onebrain_test_files() - {"test_onebrain_fake_provider.py"})


def test_零網路守衛本身有效(no_real_network):
    """負控：真的碰 socket 會被擋並記錄（之後清掉，讓 autouse 收尾斷言照常檢查其餘測試）。"""
    import socket
    import fund_lookup_support as S
    with pytest.raises(S.NetworkAttempt):
        socket.create_connection(("127.0.0.1", 9), timeout=0.01)
    assert no_real_network == ["socket.create_connection"]
    no_real_network.clear()
