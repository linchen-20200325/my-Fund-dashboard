"""2026-10-10 客戶裁示(A 級資料正確性缺陷):**未知幣別 ≠ USD**。

正式原則與本檔守住的面向(正反例並列;已知 USD / TWD 的既有行為列為回歸):

- 取數源頭缺幣別 → 空白,不再填 "USD"(L1 `sources` / `fund_orchestration`)。
- batch load:抓回空值不得覆蓋 Sheet 已填幣別;抓回不同值(Q4 currency conflict)
  也不得覆蓋、不自動寫回,換匯 / 單位數路徑 fail closed。
- 未知幣別不組 FX symbol、不查匯率(`get_latest_fx` 中央守門 + `d_mode`)。
- `normalize_ccy` 預設不再是 USD;`Ledger` 換股遇未知幣別 fail closed(Q1,F4 最小解凍)。
- T7 自動估算:幣別未知 → 不估算單位數、不自動存檔(Q1,F1 最小解凍)。
- 晨星請求必帶 `currencyId` → 幣別未知 fail closed,不以 USD 猜測(Q2)。
- 換源防護:幣別未知 → 擋下(Q3)。

全部離線:任何對外連線一律以 monkeypatch 攔截;斷言「沒有發出請求」用錄製器。
"""
from __future__ import annotations

import ast
import datetime as _dt
import io
import json
import pathlib
import types

import pandas as pd
import pytest

import repositories.fund.sources as S

ROOT = pathlib.Path(__file__).resolve().parents[1]


# ════════════════════════════════════════════════════════════════════════════
# 1) L1 取數源頭:缺幣別 → 空白(不再是 USD)
# ════════════════════════════════════════════════════════════════════════════
class _Resp:
    def __init__(self, text="", payload=None):
        self.text = text
        self._payload = payload

    def json(self):
        return self._payload


_PAGE_NO_CCY = ("<html><table><tr><td>基金名稱</td><td>某境內基金A</td></tr>"
                "<tr><td>風險報酬等級</td><td>RR4</td></tr></table>" + "x" * 600 + "</html>")
_PAGE_EUR = ("<html><table><tr><td>基金名稱</td><td>某基金E</td></tr>"
             "<tr><td>計價幣別</td><td>歐元</td></tr></table>" + "x" * 600 + "</html>")


def test_direct_url_missing_currency_is_blank(monkeypatch):
    monkeypatch.setattr(S, "fetch_url_with_retry", lambda *a, **k: _Resp(_PAGE_NO_CCY))
    monkeypatch.setattr(S, "is_valid_moneydj_page", lambda t: True)
    out = S._src_direct_moneydj_url("https://www.moneydj.com/funddj/ya/yp010000.djhtm?a=XX01")
    assert out["fund_name"] == "某境內基金A"
    assert out["currency"] == ""                 # 未知 ≠ USD


def test_direct_url_fetch_failure_currency_is_blank(monkeypatch):
    monkeypatch.setattr(S, "fetch_url_with_retry", lambda *a, **k: None)
    out = S._src_direct_moneydj_url("https://x")
    assert out["error"] == "direct_url_invalid"
    assert out["currency"] == ""


def test_direct_url_declared_currency_kept(monkeypatch):
    """回歸:頁面有「計價幣別」→ 照實帶回(不被本修正改寫)。"""
    monkeypatch.setattr(S, "fetch_url_with_retry", lambda *a, **k: _Resp(_PAGE_EUR))
    monkeypatch.setattr(S, "is_valid_moneydj_page", lambda t: True)
    assert S._src_direct_moneydj_url("https://x")["currency"] == "歐元"


def test_fundclear_meta_missing_currency_is_blank(monkeypatch):
    monkeypatch.setattr(S, "fetch_url_with_retry",
                        lambda *a, **k: _Resp(payload={"Data": {"FundName": "F"}}))
    assert S._src_fundclear_meta("ZZ01").get("currency") == ""


def test_fundclear_meta_declared_usd_kept(monkeypatch):
    monkeypatch.setattr(S, "fetch_url_with_retry",
                        lambda *a, **k: _Resp(payload={"Data": {"FundName": "F",
                                                                "Currency": "USD"}}))
    assert S._src_fundclear_meta("ZZ01")["currency"] == "USD"


def test_fundclear_div_missing_currency_is_blank(monkeypatch):
    monkeypatch.setattr(S, "fetch_url_with_retry", lambda *a, **k: _Resp(payload={
        "Data": [{"DividendAmount": 0.05, "ExDividendDate": "2026-09-01"}]}))
    divs = S._src_fundclear_div("ZZ01")
    assert len(divs) == 1 and divs[0]["currency"] == ""


def test_tdcc_meta_missing_currency_key_is_blank(monkeypatch):
    monkeypatch.setattr(S, "_tdcc_get",
                        lambda ep, *a, **k: ([{"基金代碼": "ZZ01", "基金名稱": "某基金"}]
                                             if ep == "3-2" else []))
    assert S._src_tdcc_meta("ZZ01").get("currency") == ""


# ════════════════════════════════════════════════════════════════════════════
# 2) normalize_ccy:未知 → "",已知不變(Q1)
# ════════════════════════════════════════════════════════════════════════════
def test_normalize_ccy_unknown_is_blank_not_usd():
    from services.currency import normalize_ccy
    for raw in ("", None, "   "):
        assert normalize_ccy(raw) == ""          # ~~"USD"~~(2026-10-10 前的死預設)


@pytest.mark.parametrize("raw,iso", [("USD", "USD"), ("美元", "USD"),
                                     ("TWD", "TWD"), ("台幣", "TWD"), ("usd", "USD")])
def test_normalize_ccy_known_unchanged(raw, iso):
    from services.currency import normalize_ccy
    assert normalize_ccy(raw) == iso


# ════════════════════════════════════════════════════════════════════════════
# 3) FX:未知幣別不組幣對、不查匯率(中央守門)
# ════════════════════════════════════════════════════════════════════════════
def _patch_yf(monkeypatch, rate=31.5):
    calls = []

    def _yf(pair, **k):
        calls.append(pair)
        return pd.Series([rate])

    import repositories.macro_repository as MR
    monkeypatch.setattr(MR, "fetch_yf_close", _yf)
    from repositories.fund import fx_and_main as FX
    FX._clear_fx_cache()
    return calls


@pytest.mark.parametrize("pair", ["TWD", "TWD=X", "TWD=x", "XTWD"])
def test_get_latest_fx_incomplete_pair_not_queried(monkeypatch, pair):
    calls = _patch_yf(monkeypatch)
    from repositories.fund.fx_and_main import get_latest_fx
    assert get_latest_fx(pair) is None
    assert calls == []                           # 一個請求都沒有發


def test_get_latest_fx_empty_ccy_fstring_not_queried(monkeypatch):
    """呼叫端 f"{ccy}TWD" 且 ccy 為空 → 不得拿到 Yahoo `TWD=X`(≈USD/TWD)。"""
    calls = _patch_yf(monkeypatch)
    from services.fund_service import get_latest_fx
    ccy = ""
    assert get_latest_fx(f"{ccy}TWD") is None
    assert calls == []


def test_get_latest_fx_usd_still_works(monkeypatch):
    """回歸:已知 USD 照常查。"""
    calls = _patch_yf(monkeypatch, rate=32.1)
    from repositories.fund.fx_and_main import get_latest_fx
    assert get_latest_fx("USDTWD") == 32.1
    assert calls == ["USDTWD=X"]


# ════════════════════════════════════════════════════════════════════════════
# 4) d_mode(D3):未知 → ok=False「幣別未知」,不查匯率、不用 31.0
# ════════════════════════════════════════════════════════════════════════════
def _fake_fetch(payload):
    return lambda code: payload


def test_d_mode_missing_currency_fails_closed():
    from ui.helpers.d_mode import fetch_fund_meta_safe
    _fx_calls = []
    out = fetch_fund_meta_safe(
        "X", _fetch=_fake_fetch({"fund_name": "X", "series": pd.Series([10.0]),
                                 "dividends": []}),
        _fx_lookup=lambda pair: _fx_calls.append(pair) or 31.5)
    assert out["ok"] is False
    assert out["error"] == "幣別未知"
    assert out["currency"] == ""
    assert _fx_calls == []


def test_d_mode_cache_hit_conflict_fails_closed():
    """Q4:session 快取命中,但 Sheet(TWD)與來源(USD)幣別衝突 → fail closed。"""
    from ui.helpers.d_mode import fetch_fund_meta_safe
    _hit = {"name": "某台幣基金", "currency": "TWD", "series": pd.Series([300.0]),
            "moneydj_raw": {"currency": "USD"}, "fx_avg": 32.0}
    out = fetch_fund_meta_safe("ACDD01", _existing={"ACDD01": _hit},
                               _fetch=lambda c: pytest.fail("不應再抓網路"),
                               _fx_lookup=lambda p: pytest.fail("不應查匯率"))
    assert out["ok"] is False and out["error"] == "幣別未知"


def test_d_mode_known_usd_and_twd_unchanged():
    """回歸:已知 USD 照查匯率;TWD fx=1。"""
    from ui.helpers.d_mode import fetch_fund_meta_safe
    o_usd = fetch_fund_meta_safe(
        "U", _fetch=_fake_fetch({"fund_name": "U", "currency": "USD",
                                 "series": pd.Series([10.0])}),
        _fx_lookup=lambda pair: 31.5 if pair == "USDTWD" else None)
    assert o_usd["ok"] is True and o_usd["fx"] == 31.5 and o_usd["currency"] == "USD"
    o_twd = fetch_fund_meta_safe(
        "T", _fetch=_fake_fetch({"fund_name": "T", "currency": "TWD",
                                 "series": pd.Series([10.0])}),
        _fx_lookup=lambda pair: pytest.fail("TWD 不應查匯率"))
    assert o_twd["ok"] is True and o_twd["fx"] == 1.0


# ════════════════════════════════════════════════════════════════════════════
# 5) cloud_io v2 loader(D1/D2):Sheet 空白 + 無舊值 → 空白,不是 USD
# ════════════════════════════════════════════════════════════════════════════
def _v2_df(ccy):
    return pd.DataFrame([{
        "policy_id": "P1", "fund_code": "ACDD01", "fund_name": "安聯台灣大壩",
        "currency": ccy, "tier": "", "invest_twd": 294904, "div_cash_pct": 100,
        "units": 907.8, "avg_nav": 324.85, "avg_fx": 1.0}])


@pytest.mark.parametrize("sheet_ccy,expect", [("", ""), ("TWD", "TWD"), ("USD", "USD")])
def test_cloud_io_v2_loader_currency(monkeypatch, sheet_ccy, expect):
    import ui.helpers.cloud_io as cio
    monkeypatch.setattr(cio, "load_all_policies_v2", lambda client, sid: _v2_df(sheet_ccy))
    ss: dict = {}
    out = cio._load_all_from_sheet_v2(object(), "sid", ss)
    assert out["ok"] is True
    assert ss["portfolio_funds"][0]["currency"] == expect
    led = next(iter(ss["t7_ledgers"].values()))
    assert led.currency == expect


def test_j1_path_checkup_no_longer_divides_by_usd(monkeypatch):
    """J1 重現路徑(第二組 r1 第 3 段):Sheet 幣別空白 + 首次載入 → checkup
    舊行為算出 95.86 單位(多除一次 USDTWD);修正後誠實留白,不算錯。"""
    import ui.helpers.cloud_io as cio
    import ui.helpers.fund.checkup as ck
    monkeypatch.setattr(cio, "load_all_policies_v2", lambda client, sid: _v2_df(""))
    monkeypatch.setattr(ck, "_safe_fx",
                        lambda c: None if not c else (1.0 if c == "TWD" else 32.112))
    ss: dict = {}
    cio._load_all_from_sheet_v2(object(), "sid", ss)
    pf = dict(ss["portfolio_funds"][0], loaded=True, metrics={"nav": 324.85},
              moneydj_raw={"currency": ""})
    r = ck.build_checkup_dataframe([pf]).iloc[0]
    assert r["計價幣別"] == "—"
    assert r["可申購單位數"] is None or pd.isna(r["可申購單位數"])
    assert r["可申購單位數"] != 95.86


# ════════════════════════════════════════════════════════════════════════════
# 6) Q4 currency conflict:不覆蓋 Sheet、不自動寫回、換匯 / 單位數 fail closed
# ════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("sheet,src,expect", [
    ("TWD", "", "TWD"),       # 來源未知 → 用 Sheet
    ("", "USD", "USD"),       # Sheet 空白 → 用來源
    ("TWD", "台幣", "TWD"),   # 別名一致 → 不算衝突
    ("TWD", "USD", ""),       # 衝突 → 未知(fail closed)
    ("", "", ""),             # 兩邊都未知
    ("美元", "USD", "USD"),
])
def test_fund_currency_for_calc(sheet, src, expect):
    from ui.helpers.portfolio.load import fund_currency_for_calc
    f = {"currency": sheet, "moneydj_raw": {"currency": src}}
    assert fund_currency_for_calc(f) == expect


def test_checkup_conflict_fails_closed(monkeypatch):
    import ui.helpers.fund.checkup as ck
    monkeypatch.setattr(ck, "_safe_fx",
                        lambda c: pytest.fail(f"衝突時不應查匯率({c})"))
    f = {"loaded": True, "code": "ACDD01", "name": "安聯台灣大壩基金-A累積型(台幣)",
         "currency": "TWD", "invest_twd": 294904, "metrics": {"nav": 324.85},
         "moneydj_raw": {"currency": "USD"}}
    r = ck.build_checkup_dataframe([f]).iloc[0]
    assert r["計價幣別"] == "—"


def test_checkup_known_twd_unchanged(monkeypatch):
    """回歸:Sheet 與來源皆 TWD → 照算(1M / 324.85)。"""
    import ui.helpers.fund.checkup as ck
    monkeypatch.setattr(ck, "_safe_fx", lambda c: 1.0 if c == "TWD" else None)
    f = {"loaded": True, "code": "ACDD01", "name": "安聯台灣大壩", "currency": "TWD",
         "invest_twd": 294904, "metrics": {"nav": 324.85}, "moneydj_raw": {"currency": "TWD"}}
    r = ck.build_checkup_dataframe([f]).iloc[0]
    assert r["計價幣別"] == "TWD" and r["可申購單位數"] == pytest.approx(3078.34, abs=0.01)


class _FakeSt:
    """batch_load_unloaded_funds 用到的 streamlit 最小替身(不渲染、不 rerun)。"""

    def __init__(self, funds):
        self.session_state = types.SimpleNamespace(portfolio_funds=funds)
        self.session_state.get = lambda k, d=None: getattr(self.session_state, k, d)
        self.reruns = 0

    def empty(self):
        return types.SimpleNamespace(info=lambda *a, **k: None,
                                     success=lambda *a, **k: None)

    def progress(self, *a, **k):
        return types.SimpleNamespace(progress=lambda *a, **k: None)

    def write(self, *a, **k):
        pass

    def warning(self, *a, **k):
        pass

    def rerun(self):
        self.reruns += 1


def _run_batch_load(monkeypatch, funds, fetched_by_code):
    import services.fund_service as FS
    import ui.helpers.data_registry as DR
    import ui.helpers.portfolio.load as L
    fake = _FakeSt(funds)
    monkeypatch.setattr(L, "st", fake)
    monkeypatch.setattr(FS, "fetch_fund_from_moneydj_url_enriched",
                        lambda code: dict(fetched_by_code[code]))
    monkeypatch.setattr(DR, "_update_data_registry", lambda: None)
    L.batch_load_unloaded_funds()
    return fake.session_state.portfolio_funds


def test_batch_load_blank_fetch_keeps_sheet_currency(monkeypatch):
    funds = [{"code": "ACDD01", "policy_id": "P1", "currency": "TWD", "loaded": False}]
    out = _run_batch_load(monkeypatch, funds,
                          {"ACDD01": {"fund_name": "安聯台灣大壩", "currency": ""}})
    assert out[0]["currency"] == "TWD"           # 抓回空值不得覆蓋 Sheet


def test_batch_load_conflict_keeps_sheet_and_fails_closed(monkeypatch):
    from ui.helpers.portfolio.load import fund_currency_for_calc
    funds = [{"code": "ACDD01", "policy_id": "P1", "currency": "TWD", "loaded": False}]
    out = _run_batch_load(monkeypatch, funds,
                          {"ACDD01": {"fund_name": "安聯台灣大壩", "currency": "USD"}})
    assert out[0]["currency"] == "TWD"           # 不以來源覆蓋 Sheet(不會被 dump 寫回)
    assert out[0]["moneydj_raw"]["currency"] == "USD"   # 也不以 Sheet 覆蓋來源事實
    assert fund_currency_for_calc(out[0]) == ""  # 正式計算 fail closed


def test_batch_load_blank_sheet_takes_source(monkeypatch):
    """回歸:Sheet 空白 → 採用來源宣告值(與修正前相同)。"""
    funds = [{"code": "TLZF9", "policy_id": "P1", "currency": "", "loaded": False}]
    out = _run_batch_load(monkeypatch, funds,
                          {"TLZF9": {"fund_name": "安聯收益成長", "currency": "USD"}})
    assert out[0]["currency"] == "USD"


def test_reuse_across_ledgers_does_not_overwrite_sheet_currency():
    from ui.helpers.portfolio.load import reuse_fund_info_by_code
    prev = [{"code": "AAA", "loaded": True, "series": [1], "currency": "USD"}]
    merged = [{"code": "AAA", "loaded": False, "currency": "TWD"}]
    reuse_fund_info_by_code(merged, prev)
    assert merged[0]["currency"] == "TWD"


# ════════════════════════════════════════════════════════════════════════════
# 7) Ledger(Q1,F4):缺幣別 → ""、換股遇未知 fail closed;已知照舊
# ════════════════════════════════════════════════════════════════════════════
def test_ledger_from_dict_missing_currency_is_blank():
    from services.ledger_service import Ledger
    assert Ledger.from_dict({"fund_code": "A", "transactions": []}).currency == ""


@pytest.mark.parametrize("fn", ["switch_same_currency", "switch_cross_currency"])
def test_switch_unknown_currency_fails_closed(fn):
    from services.ledger_service import Ledger, Switch
    a = Ledger(fund_code="TWDFUND", currency="")
    a.subscribe(amount_twd=300000, fx_rate=1.0, nav=300.0, txn_date=_dt.date(2026, 1, 2))
    b = Ledger(fund_code="USDFUND", currency="USD")
    kw = {"units_to_redeem": None, "nav_from_redeem": 300.0, "nav_to_buy": 10.0,
          "fee_orig": 0.0, "txn_date": _dt.date(2026, 2, 2)}
    if fn == "switch_cross_currency":
        kw.update(cross_rate=1 / 32.1, fx_to_at_switch_twd=32.1)
    units_before = a.position.units
    with pytest.raises(ValueError, match="幣別未知"):
        getattr(Switch, fn)(a, b, **kw)
    assert a.currency == ""                      # ~~被改寫成 "USD"~~(修正前)
    assert a.position.units == units_before      # 帳本完全沒動


def test_switch_known_same_currency_unchanged():
    from services.ledger_service import Ledger, Switch
    a = Ledger(fund_code="A", currency="USD")
    a.subscribe(amount_twd=32000, fx_rate=32.0, nav=10.0, txn_date=_dt.date(2026, 1, 2))
    b = Ledger(fund_code="B", currency="美元")
    r = Switch.switch_same_currency(a, b, units_to_redeem=None, nav_from_redeem=10.0,
                                    nav_to_buy=20.0, fee_orig=0.0,
                                    txn_date=_dt.date(2026, 2, 2))
    assert r.units_added_to == pytest.approx(50.0)
    assert b.currency == "USD"


# ════════════════════════════════════════════════════════════════════════════
# 8) 換源防護(Q3):幣別未知 → 擋下
# ════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("exp,cand,safe", [
    ("TWD", "TWD", True), ("USD", "USD", True),       # match → 放行(回歸)
    ("TWD", "USD", False),                            # mismatch → 擋(回歸)
    ("", "USD", False), ("TWD", "", False), ("", "", False),   # unknown → 擋(新)
])
def test_swap_guard_unknown_blocks(exp, cand, safe):
    from shared.data_quality import assess_nav_series_swap
    r = assess_nav_series_swap(expected_ccy=exp, candidate_ccy=cand)
    assert r["safe"] is safe
    if not safe:
        assert r["reason"]                       # 擋下一定有理由可記 log


def test_span_extend_unknown_expected_ccy_does_not_swap(monkeypatch):
    import repositories.fund.fund_orchestration as fo
    short = pd.Series([10.0 + i * 0.01 for i in range(20)],
                      index=pd.date_range("2026-08-01", periods=20))
    long = pd.Series([9.0 + i * 0.001 for i in range(800)],
                     index=pd.date_range("2024-01-01", periods=800))
    long.attrs["currency"] = "USD"
    monkeypatch.setattr(fo, "_correct_currency", lambda c, n, code: "")   # 預期幣別判不出
    monkeypatch.setattr(fo, "_src_morningstar_nav", lambda code, fund_name="": long)
    monkeypatch.setattr(fo, "_src_cnyes_nav", lambda code: pd.Series(dtype=float))
    s, src, _span = fo._span_extend_insurance_nav("TLZF9", short, "moneydj",
                                                  fund_name="X", is_insurance_code=True)
    assert src == "moneydj" and len(s) == 20     # 未換源


# ════════════════════════════════════════════════════════════════════════════
# 9) 晨星(Q2):請求必帶 currencyId → 幣別未知 fail closed,不以 USD 猜測
# ════════════════════════════════════════════════════════════════════════════
def _record_urlopen(monkeypatch, payload):
    import urllib.request as UR
    seen = []

    class _R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _open(req, timeout=None):
        seen.append(getattr(req, "full_url", req))
        return _R(json.dumps(payload).encode())

    monkeypatch.setattr(UR, "urlopen", _open)
    return seen


def test_screener_unknown_currency_no_request(monkeypatch):
    seen = _record_urlopen(monkeypatch, {"rows": []})
    S._ms_screener_cache.pop("LU0000000001", None)
    assert S._morningstar_screener_secid("LU0000000001") == ""
    assert S._morningstar_screener_secid("LU0000000001", currency="  ") == ""
    assert seen == []
    assert "LU0000000001" not in S._ms_screener_cache   # 不是「查無」,不入負快取


def test_pool_isin_unknown_ccy_does_not_call_screener(monkeypatch):
    import repositories.pool_repository as P
    monkeypatch.setattr(P, "resolve_secid", lambda c: None)
    monkeypatch.setattr(P, "resolve_isin", lambda c: "LU0766462157")
    monkeypatch.setattr(P, "resolve_currency", lambda c: None)
    monkeypatch.setattr(S, "_morningstar_screener_secid",
                        lambda *a, **k: pytest.fail("幣別未知不應呼叫 screener"))
    assert S._pool_secid_lookup("XXXX") == ""


def test_resolve_secid_blank_currency_not_usd(monkeypatch):
    import repositories.pool_repository as P
    entry = types.SimpleNamespace(morningstar_secid="F0X", currency="")
    monkeypatch.setattr(P, "_pool_entry_of", lambda code: entry)
    assert P.resolve_secid("X") == ("F0X", "")   # ~~("F0X", "USD")~~


def _isolate_ms(monkeypatch, *, secid=None, isin=None, ccy=None, search="F0SEARCH"):
    import repositories.pool_repository as P
    monkeypatch.setattr(P, "resolve_secid", lambda c: secid)
    monkeypatch.setattr(P, "resolve_isin", lambda c: isin)
    monkeypatch.setattr(P, "resolve_currency", lambda c: ccy)
    monkeypatch.setattr(S, "_morningstar_search_secid", lambda *a, **k: search)


def test_morningstar_nav_unknown_currency_fails_closed(monkeypatch):
    _isolate_ms(monkeypatch)
    seen = _record_urlopen(monkeypatch, {})
    s = S._src_morningstar_nav("ZZZ9", fund_name="某基金")
    assert s.empty
    assert seen == []                            # 沒有任何晨星 timeseries 請求


def test_morningstar_nav_isin_unknown_currency_fails_closed(monkeypatch):
    _isolate_ms(monkeypatch, isin="LU0000000002")
    S._ms_ccy_cache.pop("LU0000000002", None)
    seen = _record_urlopen(monkeypatch, {})
    s = S._src_morningstar_nav("ZZZ8")
    assert s.empty and seen == []                # screener 與 timeseries 都沒有發


def test_morningstar_nav_pool_secid_blank_currency_fails_closed(monkeypatch):
    _isolate_ms(monkeypatch, secid=("F0POOL", ""))
    seen = _record_urlopen(monkeypatch, {})
    assert S._src_morningstar_nav("ZZZ7").empty and seen == []


_MS_TS = {"TimeSeries": {"Security": [{"HistoryDetail": [
    {"EndDate": "2026-09-01", "Value": "10.1"}, {"EndDate": "2026-09-02", "Value": "10.2"}]}]}}


def test_morningstar_nav_known_usd_unchanged(monkeypatch):
    """回歸:硬編表手工宣告 USD(TLZF9)→ 照常以 USD 請求、序列標 USD。"""
    _isolate_ms(monkeypatch)
    seen = _record_urlopen(monkeypatch, _MS_TS)
    s = S._src_morningstar_nav("TLZF9")
    assert len(s) == 2 and s.attrs["currency"] == "USD"
    assert len(seen) == 1 and "currencyId=USD" in seen[0]


def test_morningstar_nav_pool_known_twd_uses_twd(monkeypatch):
    _isolate_ms(monkeypatch, secid=("F0POOLT", "TWD"))
    seen = _record_urlopen(monkeypatch, _MS_TS)
    s = S._src_morningstar_nav("ZZZ6")
    assert s.attrs["currency"] == "TWD" and "currencyId=TWD" in seen[0]


# ════════════════════════════════════════════════════════════════════════════
# 10) T7(Q1,F1 最小解凍):幣別未知 → 不查匯率、不估算單位數、不自動存檔
#     T7 是凍結 Tab 內的巢狀程式碼 —— 以 AST 取出**原樣**的函式 / 迴圈,注入替身後實跑。
# ════════════════════════════════════════════════════════════════════════════
_T7_SRC = (ROOT / "ui" / "tab3_t7_ledger.py").read_text(encoding="utf-8")
_T7_TREE = ast.parse(_T7_SRC)


def _t7_func(name):
    for n in ast.walk(_T7_TREE):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    raise AssertionError(name)


def _t7_auto_est_block():
    for n in ast.walk(_T7_TREE):
        for field in ("body", "orelse"):
            body = getattr(n, field, None)
            if not isinstance(body, list):
                continue
            for i, st_ in enumerate(body):
                if (isinstance(st_, ast.For) and isinstance(st_.target, ast.Name)
                        and st_.target.id == "_f_ae"):
                    return body[i - 3:i + 2]     # 三個計數器 + 迴圈 + 存檔 if
    raise AssertionError("auto-estimate loop not found")


class _T7St:
    def __init__(self):
        self.session_state = types.SimpleNamespace(t7_ledgers={})
        self.session_state.setdefault = lambda k, d: d
        self.msgs = []

    def success(self, m):
        self.msgs.append(m)

    warning = info = success


def _t7_namespace(fx_calls, saves, nav_calls=None):
    from services.ledger_service import Ledger
    from ui.helpers.portfolio.load import fund_currency_for_calc
    ns = {
        "st": _T7St(), "pd": pd, "_d_t7": _dt.date,
        "_ccy_calc_t7": fund_currency_for_calc,
        "_nav_now": lambda code: (nav_calls.append(code) if nav_calls is not None else None) or 10.0,
        "_fx_now": lambda pair: fx_calls.append(pair) or 32.0,
        "_FX_FALLBACK": {"USD": 32.0},
        "fund_pk_str": lambda f: f"{f.get('policy_id', '')}::{f.get('code', '')}",
        "_LedT7": Ledger,
        "_nav_at_date_t7": lambda f, d: 0.0,
        "_sync_invest_twd_from_ledgers": lambda: None,
        "_t7_save_snapshot_to_sheets": lambda: saves.append(1) or "",
    }
    mod = ast.Module(body=[_t7_func("_latest_nav_fx_t7")], type_ignores=[])
    exec(compile(mod, "t7_latest_nav_fx", "exec"), ns)  # noqa: S102 — 實跑凍結 Tab 原樣程式碼
    return ns


def test_t7_latest_nav_fx_unknown_currency_no_fx_query():
    fx_calls, saves = [], []
    ns = _t7_namespace(fx_calls, saves)
    nav, fx = ns["_latest_nav_fx_t7"]({"code": "X", "currency": ""})
    assert (nav, fx) == (10.0, 0.0)
    assert fx_calls == []                        # 不組 "TWD"、不查匯率、不用保底匯率
    nav, fx = ns["_latest_nav_fx_t7"]({"code": "X", "currency": "TWD",
                                       "moneydj_raw": {"currency": "USD"}})
    assert fx == 0.0 and fx_calls == []          # Q4 衝突同樣 fail closed


def test_t7_latest_nav_fx_known_usd_unchanged():
    fx_calls, saves = [], []
    ns = _t7_namespace(fx_calls, saves)
    assert ns["_latest_nav_fx_t7"]({"code": "U", "currency": "USD"}) == (10.0, 32.0)
    assert fx_calls == ["USDTWD"]


def _run_auto_est(funds, nav_calls=None):
    fx_calls, saves = [], []
    ns = _t7_namespace(fx_calls, saves, nav_calls)
    ns["_pf_t7"] = funds
    mod = ast.Module(body=_t7_auto_est_block(), type_ignores=[])
    exec(compile(mod, "t7_auto_est", "exec"), ns)  # noqa: S102 — 同上
    return ns["st"].session_state.t7_ledgers, saves, fx_calls


def test_t7_auto_estimate_unknown_currency_no_units_no_save():
    nav_calls = []
    leds, saves, fx_calls = _run_auto_est(
        [{"code": "ACDD01", "policy_id": "P1", "currency": "", "invest_twd": 294904}],
        nav_calls)
    assert leds == {} and saves == [] and fx_calls == []
    assert nav_calls == []        # 幣別未知在進入取價之前就擋下(不被誤計成「NAV 抓不到」)


def test_t7_auto_estimate_conflict_no_units_no_save():
    leds, saves, _ = _run_auto_est(
        [{"code": "ACDD01", "policy_id": "P1", "currency": "TWD", "invest_twd": 294904,
          "moneydj_raw": {"currency": "USD"}}])
    assert leds == {} and saves == []


def test_t7_auto_estimate_known_usd_unchanged():
    leds, saves, fx_calls = _run_auto_est(
        [{"code": "TLZF9", "policy_id": "P1", "currency": "USD", "invest_twd": 32000}])
    led = leds["P1::TLZF9"]
    assert led.currency == "USD"
    assert led.position.units == pytest.approx(32000 / (10.0 * 32.0))
    assert saves == [1] and fx_calls == ["USDTWD"]


def test_t7_auto_estimate_known_twd_unchanged():
    leds, saves, fx_calls = _run_auto_est(
        [{"code": "ACDD01", "policy_id": "P1", "currency": "TWD", "invest_twd": 3000}])
    assert leds["P1::ACDD01"].position.units == pytest.approx(300.0)
    assert fx_calls == [] and saves == [1]


def test_t7_no_literal_usd_currency_fallback():
    """凍結 Tab 內不得再有「缺幣別 → USD」的字面預設(.get("currency","USD") / or "USD")。"""
    bad = []
    for n in ast.walk(_T7_TREE):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "get" and len(n.args) >= 2
                and isinstance(n.args[0], ast.Constant) and n.args[0].value == "currency"
                and isinstance(n.args[1], ast.Constant) and n.args[1].value == "USD"):
            bad.append(n.lineno)
        if (isinstance(n, ast.BoolOp) and isinstance(n.op, ast.Or)
                and any(isinstance(v, ast.Constant) and v.value == "USD" for v in n.values)):
            bad.append(n.lineno)
    assert bad == []


def test_t7_c_switch_prechecks_currency_before_any_ledger_mutation():
    """C 換股:任一檔幣別未知 → 在**任何帳本異動之前**整批擋下。

    非情境模式下,迴圈中途 raise 不會回滾先前已成交的配對;故守門必須在迴圈之前。
    (C 區塊深嵌於凍結 Tab,無法單獨實跑 —— 以 AST 釘住「守門在 for 之前、且會 raise」。)
    """
    for n in ast.walk(_T7_TREE):
        if not isinstance(n, ast.Try):
            continue
        idx = [i for i, st_ in enumerate(n.body)
               if isinstance(st_, ast.For) and isinstance(st_.target, ast.Tuple)
               and [e.id for e in st_.target.elts if isinstance(e, ast.Name)] == ["_spk", "_cfg"]]
        if not idx:
            continue
        before = n.body[:idx[0]]
        guards = [st_ for st_ in before if isinstance(st_, ast.If)
                  and any(isinstance(x, ast.Raise) for x in ast.walk(st_))
                  and "_ccy_unk_c" in ast.unparse(st_.test)]
        assert guards, "C 換股迴圈之前沒有幣別未知守門"
        _calc = [st_ for st_ in before if "_ccy_calc_t7" in ast.unparse(st_)]
        assert _calc, "守門沒有用 fund_currency_for_calc(未知 / 衝突)判定"
        return
    raise AssertionError("找不到 C 換股的 try/for 區塊")
