# -*- coding: utf-8 -*-
"""`services/v2_tables/exp_profile.py`（exp 正式模式批 C 的 C2：`fund_profile` 逐欄出處）守衛。

三支 L1 多半以替身注入（`fetchers=`），回傳形狀照 `repositories/fund/declared_profile.py` 的真實回傳寫；
另有幾條走**真的** L1（TDCC 的 `[]`、MoneyDJ 的綁定），網路一律換成替身。全程不打網路。
"""
from __future__ import annotations

import datetime as _dt

import pytest

import repositories.fund.declared_profile as dp
from repositories.fund import sources as src
from services.v2_tables import exp_profile as EP
from services.v2_tables import fund_keys

CODE = "TLZF9"
MDJ_AT = "2026-10-14T01:00:00+00:00"
FC_AT = "2026-10-14T00:30:00+00:00"
TDCC_OBS = "2026-10-14T00:10:00+00:00"


# ───────────────────────── L1 回傳的替身（形狀照 declared_profile）─────────────────────────

def mdj_ok(name="安聯收益成長基金", ccy="美元", freq="月配", inception="2012/03/23", *, bound=True,
           conflicts=(), at=MDJ_AT):
    return {"status": dp.STATUS_OK, "source": "MoneyDJ:www.moneydj.com:yp011001", "full_key": CODE,
            "fields": {"基金名稱": name, "計價幣別": ccy, "配息頻率": freq, "成立日期": inception},
            "label_conflicts": list(conflicts), "binding": {"code_in_label_table": bound, "code_in_page_text": True},
            "fetched_at": at, "error": None, "cooling": False, "cooling_remaining_sec": None}


def tdcc_ok(ccy="USD", name="安聯收益成長", observed=TDCC_OBS):
    return {"status": dp.STATUS_OK, "source": "TDCC:OpenAPI:3-2", "full_key": CODE,
            "fields": {"基金名稱": name, "計價幣別": ccy}, "fetched_at": None, "observed_at": observed,
            "error": None, "cooling": False, "cooling_remaining_sec": None}


def fc_ok(ccy="USD", at=FC_AT):
    return {"status": dp.STATUS_OK, "source": "FundClear:GetFundBasicInfo", "full_key": CODE,
            "fields": {"currency": ccy}, "fetched_at": at, "error": None, "cooling": False,
            "cooling_remaining_sec": None}


def failed(err="boom", *, cooling=False, left=None):
    return {"status": dp.STATUS_FAILED, "fields": {}, "fetched_at": None, "error": err, "cooling": cooling,
            "cooling_remaining_sec": left}


def not_listed():
    return {"status": dp.STATUS_NOT_LISTED, "fields": {}, "fetched_at": None, "observed_at": TDCC_OBS,
            "error": None, "cooling": False, "cooling_remaining_sec": None}


def _fetchers(mdj, tdcc, fc, calls=None):
    def mk(name, res):
        def f(full_key):
            if calls is not None:
                calls.append((name, full_key))
            return res
        return f
    return {"MoneyDJ": mk("MoneyDJ", mdj), "TDCC": mk("TDCC", tdcc), "FundClear": mk("FundClear", fc)}


def _keys(*codes):
    return fund_keys.resolve_full_keys(list(codes), mapping={})


def _one(mdj, tdcc, fc, code=CODE):
    out = EP.build_profiles(_keys(code), fetchers=_fetchers(mdj, tdcc, fc))
    return out, out["cells"][code]


# ═══════════════════════ 欄名、常數 ═══════════════════════

def test_欄名與ui_v2_logic逐字相同():
    from ui_v2.exp import logic
    assert EP.FUND_PROFILE_FIELDS == logic.FUND_PROFILE_FIELDS


def test_常數():
    assert EP.SOURCES == ("MoneyDJ", "TDCC", "FundClear")
    assert (EP.STATUS_OK, EP.STATUS_NOT_READY, EP.STATUS_FAILED, EP.STATUS_INCONSISTENT) == (
        "ok", "not_ready", "fetch_failed", "inconsistent")
    assert EP.DECLARED_CACHED_FUNCTIONS == (dp.fetch_moneydj_basic_fields, dp.fetch_tdcc_listing,
                                            dp.fetch_fundclear_declared_ccy)
    # ~~assert EP.PARTIAL_FAILURE_POLICY == "fail"（預設從嚴，待客戶裁示）~~
    # → 2026-10-14 客戶裁示（有意識的政策變更，不是漏刪）：預設 accept
    assert EP.PARTIAL_FAILURE_POLICY == "accept"


def test_配息對照表逐字照49():
    dist = ["月配", "月配息", "季配", "季配息", "半年配", "半年配息", "年配", "年配息", "雙月配", "月收"]
    accum = ["不配息", "無配息", "累積", "累積型"]
    assert EP.DIVIDEND_FREQ_TO_POLICY == {**{k: "dist" for k in dist}, **{k: "accum" for k in accum},
                                          "": None, "—": None, "不定期": None}


# ═══════════════════════ 母體 ═══════════════════════

def test_空母體():
    out = EP.build_profiles(_keys(), fetchers=_fetchers(mdj_ok(), tdcc_ok(), fc_ok()))
    assert out == {"rows": [], "cells": {}, "declared": {}, "source_status": {}, "table_wide_failed": False}


def test_也收results串列_重複代碼只處理一次():
    calls = []
    keys = _keys(CODE, CODE)["results"]
    out = EP.build_profiles(keys, fetchers=_fetchers(mdj_ok(), tdcc_ok(), fc_ok(), calls))
    assert len(out["rows"]) == 1 and len(calls) == 3


def test_單檔三源一致_全欄ok():
    out, cells = _one(mdj_ok(), tdcc_ok("USD"), fc_ok("USD"))
    assert out["rows"] == [{"fund_code": CODE, "fund_name": "安聯收益成長基金", "ccy": "USD",
                            "inception_on": "2012-03-23", "dividend_policy": "dist", "mgmt_fee_rate_pct": None,
                            "fetched_at": FC_AT}]                        # 被採用來源中最舊的實際取得時間
    assert cells["ccy"]["status"] == "ok" and cells["ccy"]["sources"] == ("MoneyDJ", "TDCC", "FundClear")
    assert cells["ccy"]["raw"] == {"MoneyDJ": "美元", "TDCC": "USD", "FundClear": "USD"}
    assert cells["ccy"]["observed_at"] == {"TDCC": TDCC_OBS}
    assert cells["ccy"]["fetched_at"] == {"MoneyDJ": MDJ_AT, "TDCC": None, "FundClear": FC_AT}
    assert out["declared"][CODE] == ("USD", "meta:MoneyDJ+TDCC+FundClear")
    assert cells["fund_name"] == {"value": "安聯收益成長基金", "status": "ok", "sources": ("MoneyDJ",),
                                  "failed_sources": (), "raw": {"MoneyDJ": "安聯收益成長基金"},
                                  "fetched_at": {"MoneyDJ": MDJ_AT}, "observed_at": {}, "reason": None}
    assert out["source_status"][CODE]["TDCC"] == {"status": "ok", "error": None, "cooling": False,
                                                  "cooling_remaining_sec": None}
    assert out["table_wide_failed"] is False


def test_ISO與中文一致_美元與USD():
    _out, cells = _one(mdj_ok(ccy="美元"), not_listed(), fc_ok("usd"))
    assert cells["ccy"]["value"] == "USD" and cells["ccy"]["sources"] == ("MoneyDJ", "FundClear")


def test_兩源不一致_inconsistent_declared空():
    out, cells = _one(mdj_ok(ccy="美元"), tdcc_ok("EUR"), not_listed())
    assert cells["ccy"]["status"] == "inconsistent" and cells["ccy"]["value"] is None
    assert cells["ccy"]["reason"].startswith("各來源幣別不一致（")
    assert out["declared"][CODE] == (None, None) and out["rows"][0]["ccy"] is None


def test_含零寬字元_認不出_與值並存_inconsistent():
    _out, cells = _one(mdj_ok(ccy="美元​"), tdcc_ok("USD"), not_listed())
    assert cells["ccy"]["status"] == "inconsistent"


def test_含零寬字元_單獨出現_not_ready():
    _out, cells = _one(mdj_ok(ccy="USD​"), not_listed(), not_listed())
    assert cells["ccy"]["status"] == "not_ready" and "無法辨識" in cells["ccy"]["reason"]


def test_全失敗_逐格與table_wide():
    out, cells = _one(failed("m"), failed("t"), failed("f"))
    assert {f: c["status"] for f, c in cells.items()} == {
        "fund_name": "fetch_failed", "ccy": "fetch_failed", "inception_on": "fetch_failed",
        "dividend_policy": "fetch_failed", "mgmt_fee_rate_pct": "not_ready"}
    assert cells["ccy"]["failed_sources"] == ("MoneyDJ", "TDCC", "FundClear")
    assert out["table_wide_failed"] is True
    assert out["rows"][0]["fetched_at"] is None


def test_兩檔只有一檔全失敗_不是table_wide():
    def by_code(ok_res, bad):
        return lambda fk: ok_res if fk == "AAA111" else bad
    fetchers = {"MoneyDJ": by_code(mdj_ok(), failed()), "TDCC": by_code(tdcc_ok(), failed()),
                "FundClear": by_code(fc_ok(), failed())}
    out = EP.build_profiles(_keys("AAA111", "BBB222"), fetchers=fetchers)
    assert out["table_wide_failed"] is False


def test_部分失敗_fail政策_fetch_failed(monkeypatch):
    # 2026-10-14 客戶裁示後，從嚴行為只在切換成 "fail" 時出現（原「預設從嚴」測試改名，有意識的更正，不是漏刪）
    monkeypatch.setattr(EP, "PARTIAL_FAILURE_POLICY", "fail")
    _out, cells = _one(mdj_ok(ccy="USD"), failed("t"), fc_ok("USD"))
    assert cells["ccy"]["status"] == "fetch_failed" and cells["ccy"]["failed_sources"] == ("TDCC",)
    assert "部分來源取數失敗" in cells["ccy"]["reason"] and cells["ccy"]["value"] is None


def test_部分失敗_預設accept_照採一致的成功來源_失敗照樣標示():
    out, cells = _one(mdj_ok(ccy="USD"), failed("t 第一行\n第二行"), fc_ok("USD"))
    c = cells["ccy"]
    assert c["status"] == "ok" and c["value"] == "USD"
    assert c["sources"] == ("MoneyDJ", "FundClear") and c["failed_sources"] == ("TDCC",)
    assert "TDCC" not in c["sources"]                                     # 失敗來源不當成一致證據
    assert c["reason"].startswith("部分來源取數失敗，以其餘一致的來源為準（TDCC：t 第一行；")
    assert "第二行" not in c["reason"]                                    # 只放摘要，原文在 source_status
    assert out["source_status"][CODE]["TDCC"]["error"] == "t 第一行\n第二行"
    assert out["declared"][CODE] == ("USD", "meta:MoneyDJ+FundClear")
    assert out["rows"][0]["ccy"] == "USD"


def test_部分失敗_只剩一個成功來源_仍ok_帶failed_sources():
    out, cells = _one(failed("m", cooling=True, left=30.0), tdcc_ok("美元"), failed("f"))
    c = cells["ccy"]
    assert c["status"] == "ok" and c["value"] == "USD" and c["sources"] == ("TDCC",)
    assert c["failed_sources"] == ("MoneyDJ", "FundClear")
    assert "MoneyDJ：m；失敗記憶冷卻中，約剩 30.0 秒" in c["reason"] and "FundClear：f" in c["reason"]
    assert out["declared"][CODE] == ("USD", "meta:TDCC")


def test_部分失敗_成功來源只有未核實的MoneyDJ_不ok():
    out, cells = _one(mdj_ok(ccy="USD", bound=False), failed("t"), failed("f"))
    assert cells["ccy"]["status"] == "fetch_failed" and cells["ccy"]["value"] is None
    assert out["declared"][CODE] == (None, None)


def test_部分失敗_成功來源有認不出_不ok():
    _out, cells = _one(mdj_ok(ccy="美金幣"), tdcc_ok("USD"), failed("f"))
    assert cells["ccy"]["status"] == "inconsistent"


def test_部分失敗_原因摘要過長截斷():
    _out, cells = _one(mdj_ok(ccy="USD"), failed("x" * 200), not_listed())
    assert "x" * 80 + "…" in cells["ccy"]["reason"] and "x" * 81 not in cells["ccy"]["reason"]


def test_政策常數不合法_ValueError(monkeypatch):
    monkeypatch.setattr(EP, "PARTIAL_FAILURE_POLICY", "maybe")
    with pytest.raises(ValueError, match="PARTIAL_FAILURE_POLICY"):
        _one(mdj_ok(), tdcc_ok(), fc_ok())


def test_MoneyDJ未綁定_三欄not_ready_不參與幣別():
    out, cells = _one(mdj_ok(ccy="EUR", bound=False), tdcc_ok("USD"), not_listed())
    for f in ("fund_name", "inception_on", "dividend_policy"):
        assert cells[f]["status"] == "not_ready" and cells[f]["reason"] == EP.TEXT_UNBOUND
        assert cells[f]["value"] is None
    assert cells["mgmt_fee_rate_pct"]["status"] == "not_ready"
    assert cells["ccy"]["status"] == "ok" and cells["ccy"]["value"] == "USD" and cells["ccy"]["sources"] == ("TDCC",)
    assert out["declared"][CODE] == ("USD", "meta:TDCC")
    assert out["rows"][0]["fetched_at"] is None                         # 只有 TDCC 被採用 → None


def test_MoneyDJ沒有binding鍵_視為未綁定():
    res = mdj_ok()
    del res["binding"]
    _out, cells = _one(res, not_listed(), not_listed())
    assert cells["fund_name"]["reason"] == EP.TEXT_UNBOUND


def test_TDCC空清單_真L1_failed(monkeypatch):
    monkeypatch.setattr(src, "_tdcc_cache", {"3-2": []})
    dp.fetch_tdcc_listing.cache_clear()
    try:
        fetchers = _fetchers(mdj_ok(ccy=None), None, not_listed())
        fetchers["TDCC"] = dp.fetch_tdcc_listing
        out = EP.build_profiles(_keys(CODE), fetchers=fetchers)
    finally:
        dp.fetch_tdcc_listing.cache_clear()
    assert out["source_status"][CODE]["TDCC"]["status"] == "failed"
    assert out["cells"][CODE]["ccy"]["status"] == "fetch_failed"


def test_各源not_listed_MoneyDJ有值照採():
    _out, cells = _one(mdj_ok(ccy="USD"), not_listed(), not_listed())
    assert cells["ccy"]["status"] == "ok" and cells["ccy"]["sources"] == ("MoneyDJ",)


def test_三源都未收錄_not_ready():
    _out, cells = _one(not_listed(), not_listed(), not_listed())
    assert cells["ccy"]["status"] == "not_ready" and cells["ccy"]["reason"].startswith("各來源未提供幣別／未收錄")
    assert cells["fund_name"]["reason"] == "MoneyDJ 未收錄此代碼"


def test_來源有這一檔但沒寫幣別_not_ready():
    _out, cells = _one(mdj_ok(ccy=None), tdcc_ok(""), fc_ok(None))
    assert cells["ccy"]["status"] == "not_ready"


def test_冷卻資訊():
    out, cells = _one(failed("m", cooling=True, left=120.0), not_listed(), not_listed())
    assert "約剩 120.0 秒" in cells["fund_name"]["reason"]
    assert out["source_status"][CODE]["MoneyDJ"] == {"status": "failed", "error": "m", "cooling": True,
                                                     "cooling_remaining_sec": 120.0}


def test_L1拋例外_轉成failed原文():
    fetchers = _fetchers(mdj_ok(), tdcc_ok(), fc_ok())

    def boom(_k):
        raise RuntimeError("壞了")
    fetchers["FundClear"] = boom
    out = EP.build_profiles(_keys(CODE), fetchers=fetchers)
    assert out["source_status"][CODE]["FundClear"]["error"] == "RuntimeError: 壞了"


def test_fetchers鍵不對_ValueError():
    with pytest.raises(ValueError, match="fetchers"):
        EP.build_profiles(_keys(CODE), fetchers={"MoneyDJ": lambda k: {}})


# ═══════════════════════ 配息、成立日、經理費 ═══════════════════════

@pytest.mark.parametrize("word, want", [
    *[(w, "dist") for w in ("月配", "月配息", "季配", "季配息", "半年配", "半年配息", "年配", "年配息", "雙月配", "月收")],
    *[(w, "accum") for w in ("不配息", "無配息", "累積", "累積型")],
    (" 月配 ", "dist"),
])
def test_配息頻率_表內字樣(word, want):
    _out, cells = _one(mdj_ok(freq=word), not_listed(), not_listed())
    assert cells["dividend_policy"]["status"] == "ok" and cells["dividend_policy"]["value"] == want
    assert cells["dividend_policy"]["raw"] == {"MoneyDJ": word}


@pytest.mark.parametrize("word", ["不定期", "—", ""])
def test_配息頻率_不寫入類(word):
    _out, cells = _one(mdj_ok(freq=word), not_listed(), not_listed())
    assert cells["dividend_policy"]["status"] == "not_ready"
    assert cells["dividend_policy"]["reason"] == f"配息頻率「{word}」依對照表不判定配息方式"


@pytest.mark.parametrize("word", ["每月", "月配息(美元)", "季"])
def test_配息頻率_表外(word):
    _out, cells = _one(mdj_ok(freq=word), not_listed(), not_listed())
    assert cells["dividend_policy"]["status"] == "not_ready"
    assert cells["dividend_policy"]["reason"] == f"配息頻率「{word}」不在對照表"


def test_配息頻率_來源沒寫_not_ready():
    _out, cells = _one(mdj_ok(freq=None), not_listed(), not_listed())
    assert cells["dividend_policy"]["reason"] == "MoneyDJ 未提供「配息頻率」"


# ~~("2012/3/5", "2012-03-05") 原列可辨識~~ → 2026-10-14 稽核必修 7（有意識的更正，不是漏刪）：字面須恰為十個字元，改列無法辨識組
# → 同日 #963 之後的收尾（有意識的更正，不是漏刪；決策者：AI 總管）：`2012/3/5` 等不補零寫法**改回可辨識**。
#   理由：月日不補零沒有歧義，拒收只增加 ⬜資料未備；稽核 V、W 兩組獨立建議放寬。
#   內部空白、全形數字、前後分隔符不同照舊拒收（見下一支）。
@pytest.mark.parametrize("raw, want", [
    ("2012/03/23", "2012-03-23"), ("2012-03-23", "2012-03-23"), (" 2012/03/23 ", "2012-03-23"),
    ("1900/01/01", "1900-01-01"),
    ("2012/3/5", "2012-03-05"), ("2012-3-5", "2012-03-05"), ("2012/03/5", "2012-03-05"), ("2012-03-5", "2012-03-05"),
    ("2012/3/05", "2012-03-05"), ("　2012/3/5　", "2012-03-05"),        # 全形空白在頭尾：去掉
])
def test_成立日期_可辨識寫法(raw, want):
    _out, cells = _one(mdj_ok(inception=raw), not_listed(), not_listed())
    assert cells["inception_on"]["status"] == "ok" and cells["inception_on"]["value"] == want


# ~~"2012/3/5"、"2012/03/5"、"2012-03-5" 原列無法辨識~~ → 同上，改列可辨識組（有意識的更正，不是漏刪）
@pytest.mark.parametrize("raw", ["2018/02/30", "101/03/23", "2012年3月23日", "2012.03.23", "２０１２/03/23",
                                 "2012/03-23", "2012/03/ 5", "2012/ 3/05", "2012 /03/23",
                                 "0099/01/01", "1899/12/31", "2012/03/2３", "+012/03/23", "2012/03/23x",
                                 "2012/3-5", "2012/ 3/5", "2012/３/5", "2012/3/５", "2012/003/05", "2012/3/005",
                                 "2012//3/5", "2012/3/5/", "2012/3/", "2012-3/5", "12012/3/5", "2012/00/05",
                                 "2012/3/0", "2012/13/1", "2012　/3/5"])
def test_成立日期_無法辨識(raw):
    _out, cells = _one(mdj_ok(inception=raw), not_listed(), not_listed())
    assert cells["inception_on"]["status"] == "not_ready"
    assert cells["inception_on"]["reason"] == f"成立日期字樣無法辨識：{raw}"


def test_經理費恆None():
    out, cells = _one(mdj_ok(), tdcc_ok(), fc_ok())
    assert out["rows"][0]["mgmt_fee_rate_pct"] is None
    assert cells["mgmt_fee_rate_pct"]["status"] == "not_ready" and cells["mgmt_fee_rate_pct"]["reason"] == EP.TEXT_MGMT_FEE


def test_MoneyDJ標籤自相矛盾_名稱not_ready_幣別認不出():
    res = mdj_ok(name=None, ccy=None, conflicts=[{"label": "基金名稱", "values": ["A", "B"]},
                                                  {"label": "計價幣別", "values": ["美元", "歐元"]}])
    _out, cells = _one(res, tdcc_ok("USD"), not_listed())
    assert cells["fund_name"]["status"] == "not_ready" and "出現不同的值" in cells["fund_name"]["reason"]
    assert cells["ccy"]["status"] == "inconsistent"


# ═══════════════════════ 代碼對照失敗、列層時間 ═══════════════════════

def test_代碼對照失敗_各欄not_ready_不取數():
    calls = []
    out = EP.build_profiles(_keys("壞 代碼"), fetchers=_fetchers(mdj_ok(), tdcc_ok(), fc_ok(), calls))
    cells = out["cells"]["壞 代碼"]
    assert calls == []
    assert all(c["status"] == "not_ready" and c["reason"].startswith("代碼無法對照：") for c in cells.values())
    assert out["declared"]["壞 代碼"] == (None, None) and out["source_status"]["壞 代碼"] == {}
    assert out["rows"][0] == {"fund_code": "壞 代碼", "fund_name": None, "ccy": None, "inception_on": None,
                              "dividend_policy": None, "mgmt_fee_rate_pct": None, "fetched_at": None}
    assert out["table_wide_failed"] is False


def test_列層fetched_at_取被採用來源中最舊():
    out, _ = _one(mdj_ok(at="2026-10-14T03:00:00+00:00"), not_listed(), fc_ok("USD", at="2026-10-14T02:00:00+00:00"))
    assert out["rows"][0]["fetched_at"] == "2026-10-14T02:00:00+00:00"


def test_列層fetched_at_FundClear沒被採用就不算():
    # FundClear 未收錄 → 只有 MoneyDJ 被採用
    out, _ = _one(mdj_ok(), not_listed(), not_listed())
    assert out["rows"][0]["fetched_at"] == MDJ_AT


def test_declared出處只由SOURCES組成():
    out, _ = _one(mdj_ok(ccy="USD"), tdcc_ok("USD"), not_listed())
    iso, source = out["declared"][CODE]
    assert source == "meta:MoneyDJ+TDCC"
    assert all(part in EP.SOURCES for part in source.removeprefix("meta:").split("+"))


def test_declared出處過得了nav_dividend白名單():
    from services.v2_tables import nav_dividend as ND
    out, _ = _one(mdj_ok(ccy="USD"), tdcc_ok("USD"), fc_ok("USD"))
    assert ND._declared_source_problem(out["declared"][CODE][1]) is None


# ═══════════════════════ 走真的 MoneyDJ L1（綁定）═══════════════════════

class _Resp:
    def __init__(self, text):
        self.text = text


def _real_mdj(monkeypatch, html):
    import infra.proxy as proxy_mod

    def fake(url, **k):
        proxy_mod._TLS_FAIL.kind = ""
        return _Resp(html)
    monkeypatch.setattr(dp, "fetch_url_with_retry", fake)
    monkeypatch.setattr(src, "_is_domestic_code", lambda code, page_type="": False)
    dp.fetch_moneydj_basic_fields.cache_clear()


@pytest.mark.parametrize("inside, want", [(True, "ok"), (False, "not_ready")])
def test_真L1_代碼在不在表內決定名稱採不採用(monkeypatch, inside, want):
    code_row = f"<tr><td>基金代碼</td><td>{CODE}</td></tr>" if inside else ""
    html = (f"<html><body><a href='#'>{CODE}</a><table><tr><td>基金名稱</td><td>某基金</td></tr>{code_row}"
            "</table></body></html>")
    _real_mdj(monkeypatch, html)
    try:
        fetchers = _fetchers(None, not_listed(), not_listed())
        fetchers["MoneyDJ"] = dp.fetch_moneydj_basic_fields
        out = EP.build_profiles(_keys(CODE), fetchers=fetchers)
    finally:
        dp.fetch_moneydj_basic_fields.cache_clear()
    assert out["source_status"][CODE]["MoneyDJ"]["status"] == "ok"
    assert out["cells"][CODE]["fund_name"]["status"] == want


def test_成立日期_年份下限常數():
    assert EP.MIN_INCEPTION_YEAR == 1900


# ───────────────────────── 成立日期上限：不晚於台灣今天（#963 之後的收尾）─────────────────────────


# 台灣 2026-10-14 08:30（世界協調時間 2026-10-14 00:30）
_NOW_TW_MORNING = _dt.datetime(2026, 10, 14, 0, 30, tzinfo=_dt.timezone.utc)


@pytest.mark.parametrize("raw, want_status", [
    ("2026/10/14", "ok"), ("2026-10-14", "ok"), ("2026/10/13", "ok"),
    ("2026/10/15", "not_ready"), ("2026-10-15", "not_ready"), ("2027/1/1", "not_ready"),
])
def test_成立日期_不晚於台灣今天(raw, want_status):
    out = EP.build_profiles(_keys(CODE), fetchers=_fetchers(mdj_ok(inception=raw), not_listed(), not_listed()),
                            now=_NOW_TW_MORNING)
    cell = out["cells"][CODE]["inception_on"]
    assert cell["status"] == want_status
    if want_status == "not_ready":
        assert cell["reason"] == f"成立日期字樣無法辨識：{raw}"


def test_成立日期_今天以台灣日期判_不是世界協調時間():
    # 世界協調時間 2026-10-13 16:30 ＝ 台灣 2026-10-14 00:30：台灣已是 14 日，14 日收、15 日不收
    now = _dt.datetime(2026, 10, 13, 16, 30, tzinfo=_dt.timezone.utc)
    assert EP.taiwan_today(now) == _dt.date(2026, 10, 14)
    assert EP.parse_inception("2026/10/14", today=EP.taiwan_today(now)) == "2026-10-14"
    assert EP.parse_inception("2026/10/15", today=EP.taiwan_today(now)) is None


def test_parse_inception_today必須注入且為date():
    with pytest.raises(TypeError):
        EP.parse_inception("2012/3/5")                                    # 沒給 today
    with pytest.raises(TypeError):
        EP.parse_inception("2012/3/5", today=_dt.datetime(2026, 10, 14))  # datetime 不收（比較會出錯）
    assert EP.parse_inception("2012/3/5", today=_dt.date(2026, 10, 14)) == "2012-03-05"


def test_build_profiles_now要帶時區():
    with pytest.raises(ValueError, match="now"):
        EP.build_profiles(_keys(CODE), fetchers=_fetchers(mdj_ok(), not_listed(), not_listed()),
                          now=_dt.datetime(2026, 10, 14))


@pytest.mark.parametrize("flag", [1, "yes", "True", [True], 1.0])
def test_綁定旗標必須恰為True_truthy不算(flag):
    # 2026-10-14 稽核 W（突變存活）：`_bound` 必須是 `is True`，放寬成 truthy 要紅
    res = mdj_ok()
    res["binding"]["code_in_label_table"] = flag
    _out, cells = _one(res, not_listed(), not_listed())
    assert cells["fund_name"]["status"] == "not_ready" and cells["fund_name"]["reason"] == EP.TEXT_UNBOUND
