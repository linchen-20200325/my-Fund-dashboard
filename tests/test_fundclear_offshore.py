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
