"""TDCC 11641 境外基金淨值(data.gov.tw)L1 解析 + L2 累積 離線測試。

環境無法連 data.gov.tw → 只測純函式(parse_nav_csv / accumulate_points),用固定 CSV fixture。
"""
from __future__ import annotations

import pandas as pd

from repositories.tdcc_nav_opendata import parse_nav_csv
from services.tdcc_nav_accumulate import accumulate_points

# 中文表頭 CSV(11641 欄:基金代碼/名稱/日期/淨值/幣別/ISIN/總代理)
_CSV = (
    "基金代碼,基金名稱,日期,基金淨值,計價幣別,ISIN代碼,總代理機構\n"
    "X001,聯博多元資產收益組合基金AI配息(美元),2026/08/12,10.50,USD,LU0000000001,聯博\n"
    "X001,聯博多元資產收益組合基金AI配息(美元),2026/08/11,10.40,USD,LU0000000001,聯博\n"
    "X002,安聯台灣大壩基金,2026/08/12,25.00,TWD,,安聯\n"
    "X003,壞資料無淨值,2026/08/12,,USD,,某代理\n"          # 無淨值 → 丟
)


def test_parse_nav_csv_clean_and_sorted():
    df = parse_nav_csv(_CSV)
    assert list(df.columns) == ["fund_code", "name", "nav_date", "nav", "currency", "isin", "agent"]
    assert len(df) == 3                                          # 壞資料列被丟
    _x001 = df[df["fund_code"] == "X001"]
    assert list(_x001["nav_date"]) == [pd.Timestamp("2026-08-11"), pd.Timestamp("2026-08-12")]  # 升冪
    assert abs(_x001["nav"].iloc[-1] - 10.50) < 1e-9
    assert (df["nav"] > 0).all()


def test_parse_nav_csv_empty():
    df = parse_nav_csv("")
    assert df.empty and list(df.columns)[0] == "fund_code"


def test_accumulate_points_matches_by_name():
    """持倉用**名稱**對到 11641 → 產出 code=持倉內部碼 的 points;對不上列 unmatched。"""
    frame = parse_nav_csv(_CSV)
    holdings = [
        {"code": "ACTI71", "name": "聯博多元資產收益組合基金AI配息(美元)"},  # 對到 X001
        {"code": "ZZZ99", "name": "完全不存在的某某基金"},                  # 對不上
    ]
    points, report = accumulate_points(holdings, frame)
    _acti = [p for p in points if p["code"] == "ACTI71"]
    assert len(_acti) == 2                                       # X001 的兩天
    assert all(p["source"] == "tdcc_opendata_11641" for p in _acti)
    assert {p["nav_date"] for p in _acti} == {"2026-08-11", "2026-08-12"}
    assert set(_acti[0].keys()) >= {"code", "nav", "nav_date", "fund_name", "source"}  # append_points 契約
    assert "ZZZ99" in report["unmatched"]
    assert any(m["code"] == "ACTI71" for m in report["matched"])


def test_accumulate_points_empty_frame_all_unmatched():
    points, report = accumulate_points([{"code": "ACTI71", "name": "聯博"}], parse_nav_csv(""))
    assert points == [] and report["unmatched"] == ["ACTI71"]
