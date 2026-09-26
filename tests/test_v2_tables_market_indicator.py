# -*- coding: utf-8 -*-
"""services/v2_tables/market_indicator.py 的單元測試（fast lane；不打任何網路）。

依據：docs/v2/49_data_integration_plan.md §2.1、§2.6、§2.8、§3.3、§4.4、§4.7 第 1 點，
      §6.1 Q1／Q2／Q3（客戶 2026-09-26 裁示）。
欄位契約的唯一真相來源是 docs/v2/44_fund_ui_ssot.md 第四節 `market_indicator` 表；
`services/v2_tables/contract.py` 只是它的鏡像，本檔第一段逐欄從 44 重抽比對。

L1 一律以替身函式注入（monkeypatch 模組屬性），不打真網路。
"""

from __future__ import annotations

import math
import pathlib
import re

import pandas as pd
import pytest

from services.v2_tables import contract
from services.v2_tables import market_indicator as mi

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_D44 = _ROOT / "docs" / "v2" / "44_fund_ui_ssot.md"

_FETCHED = "2026-09-25T06:00:00.123456+00:00"


# ═══════════════════════ 契約：44 是唯一真相來源 ═══════════════════════


def _strip_struck(text: str) -> str:
    return re.sub(r"~~.*?~~", "", text)


def _market_indicator_table_from_44():
    text = _D44.read_text(encoding="utf-8")
    sec4 = text[text.index("## 4. 資料庫結構"): text.index("## 5. 元件清單")]
    head = re.search(r"(?m)^#{3,4} 表 `market_indicator`", sec4)
    assert head, "44 第四節找不到 market_indicator 表"
    rest = sec4[head.end():]
    nxt = re.search(r"(?m)^#{3,4} ", rest)
    body = rest[: nxt.start()] if nxt else rest
    fields = []
    tier_cell = None
    for line in body.split("\n"):
        m = re.match(r"^\| `([a-z_]+)` \| ([^|]+) \| ([^|]+) \| ([^|]+) \| (.*) \|\s*$", line)
        if not m:
            continue
        name, typ, _unit, nullable, meaning = (g.strip() for g in m.groups())
        fields.append((name, typ, nullable == "是"))
        if name == "source_tier":
            tier_cell = _strip_struck(meaning)
    return tuple(fields), tier_cell


def test_契約欄位_型別_可空與44逐欄相同():
    fields, _tier = _market_indicator_table_from_44()
    assert len(fields) == 8, fields  # 空掃防呆
    assert contract.MARKET_INDICATOR_FIELDS == fields


def test_契約的source_tier值域與44相同():
    _fields, tier_cell = _market_indicator_table_from_44()
    assert tier_cell, "44 的 source_tier 語意欄沒抽到"
    domain = tuple(re.findall(r"`([^`]+)`", tier_cell.split("四個之一")[1].split("（")[0]))
    assert len(domain) == 4, domain
    assert contract.SOURCE_TIER_VALUES == domain


def test_契約檢查_好列零問題_每一欄的壞值都被點名():
    good = {
        "indicator_key": "vol_index", "obs_date": "2026-09-24", "release_date": "2026-09-24",
        "value_num": 16.5, "value_unit": "index", "source_tier": "市場指標",
        "is_revised": False, "fetched_at": _FETCHED,
    }
    assert contract.market_indicator_row_problems(good) == []
    bad_values = {
        "indicator_key": "", "obs_date": "2026/09/24", "release_date": None,
        "value_num": float("nan"), "value_unit": "", "source_tier": "T1",
        "is_revised": 0, "fetched_at": "2026-09-25T06:00:00",  # 無時區
    }
    for column, bad in bad_values.items():
        row = dict(good, **{column: bad})
        problems = contract.market_indicator_row_problems(row)
        assert problems and column in problems[0], (column, problems)
    missing = dict(good)
    del missing["value_num"]
    assert contract.market_indicator_row_problems(missing)
    extra = dict(good, note="x")
    assert contract.market_indicator_row_problems(extra)
    assert contract.market_indicator_row_problems(dict(good, value_num=True))  # bool 不是浮點


# ═══════════════════════ 替身 L1 ═══════════════════════


def _series(values, dates, *, fetched_at=_FETCHED, ticker="^VIX"):
    s = pd.Series(values, index=pd.to_datetime(dates), dtype=float, name=ticker)
    if fetched_at is not None:
        s.attrs["fetched_at"] = fetched_at
    s.attrs["source"] = f"Yahoo:{ticker}"
    return s


def _stub_yf(table):
    """table: {ticker: (Series, error)}；記錄被呼叫的 ticker。"""
    calls = []

    def fake(ticker, *args, **kwargs):
        calls.append(ticker)
        value = table[ticker]
        if isinstance(value, BaseException):
            raise value
        return value

    fake.calls = calls
    return fake


def _forbid(name):
    def boom(*args, **kwargs):
        raise AssertionError(f"第一階段不得呼叫 {name}")
    return boom


@pytest.fixture
def fx_verified(monkeypatch):
    """把匯率切日規則的開關打開（模擬「驗證完改一處」之後的狀態）。"""
    monkeypatch.setattr(mi, "FX_OBS_DATE_RULE_VERIFIED", True)


@pytest.fixture
def no_other_l1(monkeypatch):
    """FRED 與國發會第一階段不取數（49 §2.6 T1、Q3(c)）；被呼叫就紅。"""
    import repositories.macro.fred as fred
    import repositories.macro_tw_local_repository as tw

    for module, name in ((fred, "fetch_fred"), (fred, "fetch_fred_with_error"),
                         (tw, "fetch_tw_business_indicator_with_error"),
                         (tw, "_finmind_business_indicator"),
                         (tw, "fetch_ndc_signal_history")):
        monkeypatch.setattr(module, name, _forbid(name))


def _ok_table():
    return {
        "^VIX": (_series([16.0, 17.5], ["2026-09-23", "2026-09-24"]), None),
        "USDTWD=X": (_series([31.2, 31.25], ["2026-09-23", "2026-09-24"], ticker="USDTWD=X"), None),
    }


# ═══════════════════════ 日頻收盤行情（Q3 a/b） ═══════════════════════


def test_日頻收盤_公布日等於觀測日_is_revised為否_fetched_at取L1值(monkeypatch, no_other_l1, fx_verified):
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", _stub_yf(_ok_table()))
    out = mi.build_market_indicator_table()
    vix = [r for r in out["rows"] if r["indicator_key"] == "vol_index"]
    assert [r["obs_date"] for r in vix] == ["2026-09-23", "2026-09-24"]
    for row in out["rows"]:
        assert row["release_date"] == row["obs_date"]
        assert row["is_revised"] is False
        assert row["fetched_at"] == _FETCHED  # 不以當下時間覆寫（49 §2.8、§4.4）
        assert row["source_tier"] == "市場指標"
        assert contract.market_indicator_row_problems(row) == []
        assert list(row) == [name for name, _t, _n in contract.MARKET_INDICATOR_FIELDS]
    assert [r["value_num"] for r in vix] == [16.0, 17.5]
    fx = [r for r in out["rows"] if r["indicator_key"] == "fx_twd_per_usd"]
    assert {r["value_unit"] for r in fx} == {"新臺幣／美元"}  # 49 §4.6：以 MKT-3 宣告為準
    assert {r["value_unit"] for r in vix} == {"index"}
    assert out["errors"] == {}


def test_開關打開時_呼叫的L1就是49點名的兩個ticker(monkeypatch, no_other_l1, fx_verified):
    fake = _stub_yf(_ok_table())
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", fake)
    mi.build_market_indicator_table()
    assert sorted(fake.calls) == ["USDTWD=X", "^VIX"]


def test_失敗原文逐字保留_該鍵不寫列(monkeypatch, no_other_l1, fx_verified):
    raw = "fetch_url returned None: ^VIX (kind=timeout)  全形　與\n換行都要留"
    table = _ok_table()
    table["^VIX"] = (pd.Series(dtype=float, name="^VIX"), raw)
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", _stub_yf(table))
    out = mi.build_market_indicator_table()
    assert out["errors"]["vol_index"] == raw
    assert not [r for r in out["rows"] if r["indicator_key"] == "vol_index"]
    assert [r for r in out["rows"] if r["indicator_key"] == "fx_twd_per_usd"]  # 另一個鍵照寫


def test_L1拋例外_轉成原文放進errors_不吞(monkeypatch, no_other_l1, fx_verified):
    table = _ok_table()
    table["USDTWD=X"] = ValueError("validate_yf_close: attrs.source 必須以 'Yahoo:' 開頭")
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", _stub_yf(table))
    out = mi.build_market_indicator_table()
    assert out["errors"]["fx_twd_per_usd"] == (
        "ValueError: validate_yf_close: attrs.source 必須以 'Yahoo:' 開頭")
    assert not [r for r in out["rows"] if r["indicator_key"] == "fx_twd_per_usd"]


def test_空序列但沒有原因_寫49訂的弱訊息而不是當成資料未備(monkeypatch, no_other_l1):
    table = _ok_table()
    table["^VIX"] = (pd.Series(dtype=float, name="^VIX"), None)
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", _stub_yf(table))
    out = mi.build_market_indicator_table()
    assert out["errors"]["vol_index"] == "來源回傳空值，原因未提供"


def test_fetched_at取不到_整鍵不寫列_不以當下時間補(monkeypatch, no_other_l1):
    table = _ok_table()
    table["^VIX"] = (_series([16.0], ["2026-09-24"], fetched_at=None), None)
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", _stub_yf(table))
    out = mi.build_market_indicator_table()
    assert not [r for r in out["rows"] if r["indicator_key"] == "vol_index"]
    assert out["skipped"]["vol_index"]
    assert "vol_index" not in out["errors"]


@pytest.mark.parametrize("bad", ["2026-09-25T06:00:00", "not-a-time", ""])
def test_fetched_at沒有時區或解析不了_不寫列(monkeypatch, no_other_l1, bad):
    table = _ok_table()
    table["^VIX"] = (_series([16.0], ["2026-09-24"], fetched_at=bad), None)
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", _stub_yf(table))
    out = mi.build_market_indicator_table()
    assert not [r for r in out["rows"] if r["indicator_key"] == "vol_index"]


def test_fetched_at非UTC_換算成UTC同一瞬間(monkeypatch, no_other_l1):
    table = _ok_table()
    table["^VIX"] = (_series([16.0], ["2026-09-23"], fetched_at="2026-09-25T08:00:00+08:00"), None)
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", _stub_yf(table))
    out = mi.build_market_indicator_table()
    (row,) = [r for r in out["rows"] if r["indicator_key"] == "vol_index"]
    assert row["fetched_at"] == "2026-09-25T00:00:00+00:00"


def test_非有限值的列略過並計數_不補值(monkeypatch, no_other_l1):
    table = _ok_table()
    table["^VIX"] = (_series([16.0, float("nan"), float("inf"), 18.0],
                             ["2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24"]), None)
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", _stub_yf(table))
    out = mi.build_market_indicator_table()
    vix = [r for r in out["rows"] if r["indicator_key"] == "vol_index"]
    assert [r["obs_date"] for r in vix] == ["2026-09-21", "2026-09-24"]
    assert all(math.isfinite(r["value_num"]) for r in vix)
    # 理由要歸對類：非有限值是「數值非有限值」，不是被契約檢查順手擋下（突變 M9 抓到的鬆綁）
    assert out["skipped"]["vol_index"] == ["數值非有限值 2 筆不寫"]


def test_觀測日不早於取得日_當成未收盤值不寫(monkeypatch, no_other_l1):
    """取得當天（UTC）與之後的觀測可能是盤中值，Q3 的「收盤行情」前提不成立 → 不寫。"""
    table = _ok_table()
    table["^VIX"] = (_series([16.0, 17.0, 18.0], ["2026-09-24", "2026-09-25", "2026-09-26"]), None)
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", _stub_yf(table))
    out = mi.build_market_indicator_table()
    vix = [r for r in out["rows"] if r["indicator_key"] == "vol_index"]
    assert [r["obs_date"] for r in vix] == ["2026-09-24"]
    assert out["skipped"]["vol_index"]


def test_同一觀測日重複_主鍵會撞_該日全部不寫(monkeypatch, no_other_l1):
    table = _ok_table()
    table["^VIX"] = (_series([16.0, 16.1, 17.0], ["2026-09-23", "2026-09-23", "2026-09-24"]), None)
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", _stub_yf(table))
    out = mi.build_market_indicator_table()
    vix = [r for r in out["rows"] if r["indicator_key"] == "vol_index"]
    assert [r["obs_date"] for r in vix] == ["2026-09-24"]


# ═══════════════════════ Q1／Q2／Q3(c)／T1：第一階段不寫列的鍵 ═══════════════════════


def test_第一階段不寫列的六個鍵_不寫列_不取數_原因代碼各自登記(monkeypatch, no_other_l1):
    fake = _stub_yf(_ok_table())
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", fake)
    out = mi.build_market_indicator_table()
    written = {r["indicator_key"] for r in out["rows"]}
    assert written == {"vol_index"}
    assert fake.calls == ["^VIX"]  # 匯率在驗證前不取數
    assert out["pending"] == {
        "fx_twd_per_usd": mi.PENDING_FX_OBS_DATE_RULE,
        "credit_spread_pct": mi.PENDING_FRED_RELEASE_DATE,
        "term_spread_pct": mi.PENDING_FRED_RELEASE_DATE,
        "policy_rate_pct": mi.PENDING_FRED_RELEASE_DATE,
        "leading_index": mi.PENDING_NDC_NO_RELEASE_DATE,
        "coincident_index": mi.PENDING_NDC_NO_RELEASE_DATE,
    }
    for key in out["pending"]:
        assert key not in out["errors"]  # 不是失敗，是資料未備
        assert out["skipped"][key], key


def test_匯率開關_預設關_只改一處就恢復寫列(monkeypatch, no_other_l1):
    assert mi.FX_OBS_DATE_RULE_VERIFIED is False
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", _stub_yf(_ok_table()))
    monkeypatch.setattr(mi, "FX_OBS_DATE_RULE_VERIFIED", True)
    out = mi.build_market_indicator_table()
    assert {r["indicator_key"] for r in out["rows"]} == {"vol_index", "fx_twd_per_usd"}
    assert "fx_twd_per_usd" not in out["pending"]


def test_時間戳落在23點UTC_現行規則取世界協調時間的日期(monkeypatch, no_other_l1, fx_verified):
    """稽核必修 1 要的那一條：記錄現行規則在 23:00 UTC 時的行為。

    `2026-09-23 23:00 UTC` 在台北已是 09-24、在倫敦（夏令）也已是 09-24。
    現行規則取世界協調時間的日期 → `2026-09-23`。若 Yahoo 的匯率日線以倫敦午夜為界，
    這一根其實代表 09-24 ⇒ 差一天。**本條釘住現行行為，不宣稱它對** ——
    正是因為無法以真實資料驗證，`FX_OBS_DATE_RULE_VERIFIED` 預設關、匯率不寫列。
    """
    table = _ok_table()
    table["USDTWD=X"] = (_series([31.2], [pd.Timestamp("2026-09-23 23:00:00")],
                                 ticker="USDTWD=X"), None)
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", _stub_yf(table))
    (row,) = [r for r in mi.build_market_indicator_table()["rows"]
              if r["indicator_key"] == "fx_twd_per_usd"]
    assert row["obs_date"] == "2026-09-23"
    assert row["release_date"] == "2026-09-23"
    # 有時區的時間戳先換成世界協調時間再取日期（台北 07:00 → 前一天 23:00 UTC）
    assert mi._obs_date(pd.Timestamp("2026-09-24 07:00", tz="Asia/Taipei")) == "2026-09-23"


def test_冷卻狀態_只看第一階段真的會打的主機(monkeypatch):
    import repositories.v2_source_status as status

    seen = {}

    def fake_cooling(hosts):
        seen["hosts"] = list(hosts)
        return [{"source": "query1.finance.yahoo.com", "remaining_sec": 44.2}]

    monkeypatch.setattr(mi, "cooling_sources", fake_cooling)
    assert mi.source_cooldowns() == [{"source": "query1.finance.yahoo.com", "remaining_sec": 44.2}]
    assert seen["hosts"] == ["query1.finance.yahoo.com"]
    assert status.host_of("https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX") == \
        "query1.finance.yahoo.com"


def test_冷卻狀態_L1出口只讀不改(monkeypatch):
    import infra.source_backoff as sb
    import repositories.v2_source_status as status

    sb.reset_all()
    try:
        sb.record_failure("query1.finance.yahoo.com", "rate_limited")
        sb.record_failure("other.example.test", "rate_limited")
        got = status.cooling_sources(["query1.finance.yahoo.com"])
        assert [g["source"] for g in got] == ["query1.finance.yahoo.com"]
        assert got[0]["remaining_sec"] > 0
        assert len(sb.get_backoff_state()) == 2  # 讀完狀態還在
    finally:
        sb.reset_all()


def test_指標對照_Q1美國聯邦基金利率_Q2台灣國發會():
    spec = mi.INDICATOR_SPECS
    assert spec["policy_rate_pct"]["source"] == ("FRED", "FEDFUNDS")
    assert spec["leading_index"]["source"] == ("FinMind:TaiwanBusinessIndicator", "leading")
    assert spec["coincident_index"]["source"] == ("FinMind:TaiwanBusinessIndicator", "coincident")
    assert spec["credit_spread_pct"]["source"] == ("FRED", "BAMLH0A0HYM2")
    assert spec["term_spread_pct"]["source"] == ("FRED", "T10Y2Y")
    assert spec["vol_index"]["source"] == ("Yahoo", "^VIX")
    assert spec["fx_twd_per_usd"]["source"] == ("Yahoo", "USDTWD=X")
    assert set(spec) == {"vol_index", "credit_spread_pct", "leading_index", "coincident_index",
                         "policy_rate_pct", "fx_twd_per_usd", "term_spread_pct"}
    for key, s in spec.items():
        if s["phase1"] != "write":
            assert s["pending_reason"], key


def test_指標對照與ui_v2假資料的鍵集合相同():
    """鍵名以 mkt fixtures 的六鍵＋第七鍵為準（49 §2.1）；L2 不得 import ui_v2，所以在測試裡比。"""
    from ui_v2.mkt import fixtures
    assert set(mi.INDICATOR_SPECS) == set(fixtures.SIX_KEYS) | {fixtures.EXTRA_KEY}


# ═══════════════════════ Q12 接縫 ═══════════════════════


def test_落地接縫_預設不寫_傳入時收到同一份結果(monkeypatch, no_other_l1):
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", _stub_yf(_ok_table()))
    got = []
    out = mi.build_market_indicator_table(sink=got.append)
    assert set(out) == {"rows", "errors", "pending", "skipped"}
    assert got == [out]
    assert mi.build_market_indicator_table()["rows"] == out["rows"]


def test_落地接縫拋錯_不吞(monkeypatch, no_other_l1):
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", _stub_yf(_ok_table()))

    def sink(_table):
        raise RuntimeError("寫入失敗")

    with pytest.raises(RuntimeError):
        mi.build_market_indicator_table(sink=sink)


# ═══════════════════════ 層級：v2_tables 只准往下 import ═══════════════════════


def test_v2_tables只import標準庫與L0_L1():
    import ast

    allowed_top = {"__future__", "datetime", "json", "math", "typing", "pandas",
                   "repositories", "shared", "services"}
    files = sorted((_ROOT / "services" / "v2_tables").glob("*.py"))
    assert len(files) >= 3, files
    seen = 0
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                assert node.level == 0, (path.name, "相對 import 不在 L2 白名單")
                names = [node.module]
            for name in names:
                seen += 1
                top = name.split(".")[0]
                assert top in allowed_top, (path.name, name)
                if top == "services":
                    assert name.startswith("services.v2_tables"), (path.name, name)
                assert not name.startswith("ui"), (path.name, name)
    assert seen >= 5
