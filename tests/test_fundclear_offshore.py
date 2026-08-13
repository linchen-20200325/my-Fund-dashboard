"""repositories/fundclear_offshore 離線 golden tests。

環境無法連 FundClear → 網路層(_post_json)mock 掉,測解析/清洗/陷阱處理(spec §9 分離原則)。
fixture 取自開發規格書實測範例(§2.4 / §3)。
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from repositories import fundclear_offshore as fc

# spec §2.4 成功回應(降冪、字串 navValue、陷阱欄位 navValueDiffRate/lastDayNav)
_SUCCESS = {
    "fundCurr": "USD",
    "currencyName": "美元",
    "tableList": [
        {"navTxnDate": "2026/08/12", "navValue": "4086.950000", "navValueDiffRate": "0.00%", "lastDayNav": 4086.95},
        {"navTxnDate": "2026/08/11", "navValue": "4058.210000", "navValueDiffRate": "0.71%", "lastDayNav": 4086.95},
        {"navTxnDate": "2026/08/10", "navValue": "4092.860000", "navValueDiffRate": "-0.14%", "lastDayNav": 4086.95},
    ],
}
# spec §2.4 失敗回應(schema 不同:有 message/data、無 tableList)
_FAILURE = {"message": "無符合您搜尋條件的資料,請調整條件再試一次", "data": None}


def test_parse_nav_history_success_ascending_and_traps_dropped():
    """§2.4/§3:升冪排序、只留 nav_date/nav、丟棄 navValueDiffRate+lastDayNav、幣別入 attrs。"""
    df = fc._parse_nav_history(_SUCCESS)
    assert list(df.columns) == ["nav_date", "nav"]                 # 陷阱欄位已丟(T-5)
    assert df["nav_date"].is_monotonic_increasing                  # API 降冪 → 升冪(T-5)
    assert df["nav_date"].iloc[0] == pd.Timestamp("2026-08-10")
    assert df["nav_date"].iloc[-1] == pd.Timestamp("2026-08-12")
    assert abs(df["nav"].iloc[-1] - 4086.95) < 1e-6                # 字串 → float
    assert df.attrs["currency"] == "USD"
    assert (df["nav"] > 0).all()


def test_parse_nav_history_failure_returns_empty_with_columns():
    """§2.4:失敗 schema(無 tableList)→ 空 df 且欄位齊全(T-6),不回 None/不 raise。"""
    df = fc._parse_nav_history(_FAILURE)
    assert df.empty
    assert list(df.columns) == ["nav_date", "nav"]


def test_parse_nav_history_cleans_and_drops_bad_rows():
    """FR-7:千分位逗號清除、nav<=0 丟棄、重複日期去重(keep first)。"""
    data = {"fundCurr": "USD", "tableList": [
        {"navTxnDate": "2026/08/12", "navValue": "1,234.560000"},   # 千分位逗號
        {"navTxnDate": "2026/08/11", "navValue": "0.000000"},       # nav<=0 → 丟
        {"navTxnDate": "2026/08/10", "navValue": "1000.000000"},
        {"navTxnDate": "2026/08/10", "navValue": "9999.000000"},    # 重複日 → keep first
    ]}
    df = fc._parse_nav_history(data)
    assert len(df) == 2                                            # 0 值 + 重複各丟一筆
    assert abs(df[df["nav_date"] == pd.Timestamp("2026-08-12")]["nav"].iloc[0] - 1234.56) < 1e-6
    # keep="first":原始降冪第一筆 2026/08/10=1000 留下(9999 被丟)
    assert abs(df[df["nav_date"] == pd.Timestamp("2026-08-10")]["nav"].iloc[0] - 1000.0) < 1e-6


def test_parse_selection():
    got = fc._parse_selection([
        {"name": "安聯全球高成長科技基金-IT累積類股(美元)", "value": "AGIF-HT5"},
        {"name": "安聯全球高成長科技基金-A配息類股(美元)", "value": "AGIF-HTG"},
        {"name": "壞資料無 value"},
    ])
    assert {c["value"] for c in got} == {"AGIF-HT5", "AGIF-HTG"}   # 無 value 的被濾掉


def test_get_nav_history_rejects_all_class(monkeypatch):
    """T-4:fundClassCode='all' → ValueError(不打網路)。"""
    monkeypatch.setattr(fc, "_post_json", lambda *a, **k: _SUCCESS)  # 確保就算打了也不炸
    with pytest.raises(ValueError):
        fc.get_nav_history("019", "A003600004", "all", date(2026, 8, 1), date(2026, 8, 12))


def test_get_nav_history_end_to_end_mocked(monkeypatch):
    """T-5:get_nav_history 經解析後升冪 + 欄位僅 nav_date/nav + body 帶正確日期格式。"""
    _captured = {}

    def _fake_post(path, body, **kw):
        _captured["path"], _captured["body"] = path, body
        return _SUCCESS

    monkeypatch.setattr(fc, "_post_json", _fake_post)
    df = fc.get_nav_history("019", "A003600004", "AGIF-HT5", date(2026, 8, 1), date(2026, 8, 12))
    assert set(df.columns) == {"nav_date", "nav"}
    assert df["nav_date"].is_monotonic_increasing
    assert _captured["body"]["startDate"] == "2026/08/01"          # 斜線日期格式(spec §2.1)
    assert _captured["body"]["fundClassCode"] == "AGIF-HT5"


def test_get_nav_history_empty_result_mocked(monkeypatch):
    """T-6:查無資料 → 空 df,欄位齊全。"""
    monkeypatch.setattr(fc, "_post_json", lambda *a, **k: _FAILURE)
    df = fc.get_nav_history("019", "A003600004", "AGIF-HT5", date(1990, 1, 1), date(1990, 12, 31))
    assert df.empty
    assert list(df.columns) == ["nav_date", "nav"]


def test_cache_key_stable_across_process():
    """FR-3:快取 key 用 md5(非內建 hash())→ 跨行程穩定、同 body 同 key。"""
    k1 = fc._cache_key("/p", {"b": 1, "a": 2})
    k2 = fc._cache_key("/p", {"a": 2, "b": 1})     # sort_keys → 順序無關
    assert k1 == k2 and len(k1) == 16


# ── L2 名稱比對排名(純函式,離線可測)──
def test_rank_candidates_contains_and_filters():
    from services.fundclear_backfill import rank_candidates
    funds = [
        {"name": "聯博多元資產收益組合基金", "value": "AA1"},          # 完全包含 target
        {"name": "聯博多元資產收益組合基金-AI配息類股(美元)", "value": "AA2"},  # 帶級別後綴
        {"name": "貝萊德世界科技基金", "value": "BB1"},                # 無關
    ]
    got = rank_candidates("聯博多元資產收益組合基金", funds, top=5)
    _codes = [c["value"] for c in got]
    assert "AA1" in _codes and "AA2" in _codes         # 兩個聯博都入選
    assert "BB1" not in _codes                          # 無關基金被門檻濾掉
    assert got[0]["score"] >= 0.9                       # 子字串命中 → 高分


def test_rank_candidates_empty_target():
    from services.fundclear_backfill import rank_candidates
    assert rank_candidates("", [{"name": "x", "value": "1"}]) == []


def test_throttle_enforces_min_interval(monkeypatch):
    """FR-4:相鄰請求 <0.7s → sleep 補足(稽核修:_throttle 原本沒被呼叫)。"""
    import repositories.fundclear_offshore as fcmod
    _sleeps = []
    monkeypatch.setattr(fcmod.time, "time", lambda: 100.0)          # 凍結時間
    monkeypatch.setattr(fcmod.time, "sleep", lambda s: _sleeps.append(s))
    fcmod._last_request_ts = 0.0
    fcmod._throttle()                                               # 首次:elapsed 大 → 不睡
    fcmod._throttle()                                               # 立刻再打:elapsed 0 → 睡 ~0.7
    assert any(abs(s - fcmod._THROTTLE_SEC) < 0.05 for s in _sleeps), _sleeps


def test_post_json_wires_throttle(monkeypatch):
    """稽核修:_post_json 每次打網路前確實呼叫 _throttle(先前定義卻沒接)。"""
    import requests

    import repositories.fundclear_offshore as fcmod
    _n = {"throttle": 0}
    monkeypatch.setattr(fcmod, "_throttle", lambda: _n.__setitem__("throttle", _n["throttle"] + 1))
    monkeypatch.setattr("infra.proxy.get_proxy_config", lambda: None)

    class _Resp:
        status_code = 200

        def json(self):
            return {"ok": True}

    class _Sess:
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, *a, **k):
            return _Resp()

        def post(self, *a, **k):
            return _Resp()

    monkeypatch.setattr(requests, "Session", lambda: _Sess())
    out = fcmod._post_json("/x", {"a": 1}, use_cache=False)
    assert out == {"ok": True} and _n["throttle"] >= 1


def test_download_and_store_point_key_contract(monkeypatch):
    """稽核 #1/#11:download_and_store 產出的 point dict key 必須符合 append_points 契約
    (code/nav/nav_date/fund_name/source),且 code=持倉內部碼 → 健診才讀得回。"""
    from datetime import date

    import services.fundclear_backfill as bf
    _df = pd.DataFrame({"nav_date": pd.to_datetime(["2020-01-01", "2020-01-02"]),
                        "nav": [10.0, 10.5]})
    _df.attrs["currency"] = "USD"
    monkeypatch.setattr(fc, "get_nav_history", lambda *a, **k: _df)
    _cap = {}
    import services.nav_history_gs as gs
    monkeypatch.setattr(gs, "append_points",
                        lambda pts: (_cap.setdefault("pts", pts), {"written": len(pts), "skipped": 0})[1])
    res = bf.download_and_store("019", "F", "C", "ACTI71", fund_name="X",
                               start=date(2019, 1, 1), end=date(2021, 1, 1))
    assert res["ok"] and res["count"] == 2 and res["currency"] == "USD"
    _p = _cap["pts"][0]
    assert set(_p) >= {"code", "nav", "nav_date", "fund_name", "source"}
    assert _p["code"] == "ACTI71" and _p["source"] == "fundclear_offshore"
    assert _p["nav_date"] == "2020-01-01"                          # ISO 日期字串


def test_find_fund_candidates_scan_range(monkeypatch):
    """scan_range>0 → 逐一掃描 001..NNN 機構(繞過機構清單 endpoint),命中機構帶進候選 + 附 organize_code。"""
    import repositories.fundclear_offshore as fcmod
    from services.fundclear_backfill import find_fund_candidates
    _calls = []

    def _fake_list_funds(org):
        _calls.append(org)
        return [{"name": "聯博多元資產收益組合基金", "value": "AA1"}] if org == "037" else []

    monkeypatch.setattr(fcmod, "list_funds", _fake_list_funds)
    got = find_fund_candidates("聯博多元資產收益組合基金", scan_range=40)
    assert got and got[0]["value"] == "AA1"
    assert got[0]["organize_code"] == "037"          # 掃描有帶回命中的機構代碼
    assert "001" in _calls and "037" in _calls        # 三位補零、確實逐一掃


def test_list_organizes_falls_back_to_known(monkeypatch):
    """機構清單 endpoint 全敗 → 回退已知機構(019 安聯 / 037 聯博),不 raise(避免整段卡死)。"""
    import repositories.fundclear_offshore as fcmod

    def _boom(*a, **k):
        raise fcmod.FundclearError("endpoint 不存在")

    monkeypatch.setattr(fcmod, "_post_json", _boom)
    got = fcmod.list_organizes()
    _codes = {o["value"] for o in got}
    assert "019" in _codes and "037" in _codes and len(got) == len(fcmod._KNOWN_ORGANIZES)
