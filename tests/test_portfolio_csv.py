"""L2 保單持倉總表 CSV 解析 + 分析(services/portfolio_csv,v19.445)。

守:CSV 解析(表頭關鍵字/別名、#N/A、千分位、缺 policy·code 跳過)、依保單彙總(核心/衛星)、
真實報酬(現值=單位×現價×現匯、含息、台幣 fx=1)、保單排名(最差在前)、缺現價誠實不硬算。
全用**假資料**(假保單號 PA01/PA02、假金額)——絕不含任何真實保單資料。
"""
from __future__ import annotations

from services.portfolio_csv import (
    enrich_returns,
    parse_holdings,
    policy_returns,
    summarize_by_policy,
)

_CSV = (
    "保單號碼,基金代碼,基金名稱,幣別,級別,持有單位數,平均成本淨值,平均含息成本,"
    "平均匯率,投資金額(TWD),現金給付%,,累積已領配息(TWD)\n"
    "PA01,FUNDX,測試基金X,美元,核心,100,10,9,30,30000,100,0.05,500\n"
    "PA01,FUNDY,測試基金Y,台幣,衛星,50,200,200,1,10000,100,#N/A,\n"
    "PA02,FUNDX,測試基金X,美元,核心,200,10,9,30,60000,80,0.05,1000\n"
)


# ── parse ──────────────────────────────────────────────────
def test_parse_basic_and_types():
    hs = parse_holdings(_CSV)
    assert len(hs) == 3
    h = hs[0]
    assert h["policy"] == "PA01" and h["code"] == "FUNDX" and h["currency"] == "美元"
    assert h["tier"] == "核心" and h["units"] == 100.0 and h["invest_twd"] == 30000.0
    assert h["cum_div_twd"] == 500.0


def test_parse_na_and_thousands():
    hs = parse_holdings("保單號碼,基金代碼,投資金額(TWD),累積已領配息(TWD)\n"
                        "PA01,FUNDY,\"1,234,567\",#N/A\n")
    assert hs[0]["invest_twd"] == 1234567.0 and hs[0]["cum_div_twd"] is None   # #N/A → None


def test_parse_skips_missing_policy_or_code():
    hs = parse_holdings("保單號碼,基金代碼,投資金額(TWD)\nPA01,,100\n,FUNDX,100\nPA01,FUNDX,100\n")
    assert len(hs) == 1 and hs[0]["policy"] == "PA01"


def test_parse_unknown_header_returns_empty():
    assert parse_holdings("a,b,c\n1,2,3\n") == []          # 認不出 policy/code → 空(§1)


# ── summarize ──────────────────────────────────────────────
def test_summarize_by_policy_core_satellite():
    s = {d["policy"]: d for d in summarize_by_policy(parse_holdings(_CSV))}
    assert s["PA01"]["invest_twd"] == 40000.0 and s["PA01"]["n_funds"] == 2
    assert s["PA01"]["core_twd"] == 30000.0 and s["PA01"]["satellite_twd"] == 10000.0
    assert abs(s["PA01"]["core_pct"] - 75.0) < 1e-9
    assert s["PA02"]["cum_div_twd"] == 1000.0


# ── enrich_returns ─────────────────────────────────────────
def test_enrich_returns_math():
    hs = parse_holdings(_CSV)
    en = enrich_returns(hs, nav_by_code={"FUNDX": 11.0, "FUNDY": 210.0}, usdtwd=31.0)
    fx = {h["code"] + h["policy"]: h for h in en}
    # PA01 FUNDX:100×11×31=34100;+500-30000 → +4600 → 15.33%
    a = fx["FUNDXPA01"]
    assert abs(a["current_value_twd"] - 34100.0) < 1e-6
    assert abs(a["total_return_twd"] - 4600.0) < 1e-6
    # 台幣 fx=1:PA01 FUNDY 50×210×1=10500
    b = fx["FUNDYPA01"]
    assert abs(b["current_value_twd"] - 10500.0) < 1e-6


def test_enrich_missing_nav_is_none():
    hs = parse_holdings(_CSV)
    en = enrich_returns(hs, nav_by_code={"FUNDY": 210.0}, usdtwd=31.0)   # 缺 FUNDX 現價
    miss = [h for h in en if h["code"] == "FUNDX"]
    assert all(h["current_value_twd"] is None and h["total_return_pct"] is None for h in miss)


# ── policy_returns 排名 ────────────────────────────────────
def test_policy_returns_ranks_worst_first():
    en = enrich_returns(parse_holdings(_CSV),
                        nav_by_code={"FUNDX": 11.0, "FUNDY": 210.0}, usdtwd=31.0)
    pr = policy_returns(en)
    # PA01 ≈ (44600+500-40000)/40000 = 12.75%;PA02 ≈ (68200+1000-60000)/60000 = 15.33%
    by = {p["policy"]: p for p in pr}
    assert abs(by["PA01"]["total_return_pct"] - 12.75) < 0.01
    assert abs(by["PA02"]["total_return_pct"] - 15.333) < 0.01
    assert by["PA01"]["rank"] == 1 and by["PA02"]["rank"] == 2   # 最差(PA01)排第 1
    assert pr[0]["policy"] == "PA01"                              # 排序:最差在前


def test_policy_returns_all_unpriced_no_rank():
    en = enrich_returns(parse_holdings(_CSV), nav_by_code={}, usdtwd=31.0)   # 全無現價
    pr = policy_returns(en)
    assert all(p["total_return_pct"] is None and p["rank"] is None for p in pr)
