"""混合 schema 政策 Sheet 相容(v19.432)。

user 的 Sheet 同時有「中文表頭 v2 分頁」(基金代號/類型/級別/幣別/淨投資金額)與
「英文 v1 分頁」(fund_url/policy_tier)。修前:偵測回 v2 → load_all_policies_v2 跳過 v1 分頁
→ 只在英文分頁的基金(ALBT8)整批漏掉。修後:兩種 schema 分頁都吃,不漏基金。
"""
from __future__ import annotations

import pandas as pd


class _FakeWS:
    def __init__(self, title, header, records):
        self.title = title
        self._h = header
        self._r = records

    def row_values(self, n):
        return list(self._h) if n == 1 else []

    def get_all_records(self, **k):
        return self._r

    def get_all_values(self):
        return [list(self._h)] + [[str(r.get(h, "")) for h in self._h] for r in self._r]


class _FakeSheet:
    def __init__(self, wss):
        self._w = wss

    def worksheets(self):
        return self._w


class _FakeClient:
    def __init__(self, sh):
        self._s = sh

    def open_by_key(self, k):
        return self._s


# ── _v1_frame_to_v2 映射 ────────────────────────────────
def test_v1_frame_to_v2_maps_columns():
    from repositories.policy.v2 import _v1_frame_to_v2
    df = pd.DataFrame([{"policy_id": "P", "fund_url": "ALBT8", "policy_tier": "core",
                        "fx_avg": "31.5", "currency": "美元", "invest_twd": "100"}])
    out = _v1_frame_to_v2(df)
    assert out["fund_code"].iloc[0] == "ALBT8"          # fund_url → fund_code(裸代號原樣)
    assert out["tier"].iloc[0] == "core"                # policy_tier → tier
    assert out["avg_fx"].iloc[0] == "31.5"              # fx_avg → avg_fx
    assert out["item_type"].iloc[0] == "fund"           # v1 全為基金列


# ── _records_to_policy_df 中文表頭別名(v1 path)────────────
def test_records_to_policy_df_chinese_headers_captured():
    from repositories.policy.v2 import _records_to_policy_df
    recs = [{"保單編號": "P1", "類型": "fund", "基金代號": "ACTI71",
             "淨投資金額": "499509", "級別": "core", "幣別": "美元"}]
    df = _records_to_policy_df(recs)
    _row = df[df["fund_url"] == "ACTI71"]
    assert len(_row) == 1                               # 中文分頁的基金有被抓到
    assert _row.iloc[0]["policy_id"] == "P1"
    assert _row.iloc[0]["policy_tier"] == "core"
    assert int(float(_row.iloc[0]["invest_twd"])) == 499509


def test_records_to_policy_df_pure_english_unchanged():
    from repositories.policy.v2 import _records_to_policy_df
    recs = [{"policy_id": "P", "fund_url": "X1", "invest_twd": "100",
             "policy_tier": "satellite", "currency": "美元"}]
    df = _records_to_policy_df(recs)
    _row = df[df["fund_url"] == "X1"]
    assert len(_row) == 1 and _row.iloc[0]["policy_tier"] == "satellite"


# ── load_all_policies_v2 混合分頁(v2 path,user 實際走的)────────
def test_load_all_policies_v2_captures_both_schemas():
    from repositories.policy.v2 import load_all_policies_v2
    v2tab = _FakeWS("PA", ["保單編號", "類型", "基金代號", "淨投資金額", "級別", "幣別"],
                    [{"保單編號": "PA", "類型": "fund", "基金代號": "TLZF9",
                      "淨投資金額": "1000", "級別": "core", "幣別": "美元"}])
    v1tab = _FakeWS("PB", ["policy_id", "fund_url", "invest_twd", "policy_tier", "currency"],
                    [{"policy_id": "PB", "fund_url": "ALBT8", "invest_twd": "2000",
                      "policy_tier": "core", "currency": "美元"}])
    client = _FakeClient(_FakeSheet([v2tab, v1tab]))
    df = load_all_policies_v2(client, "sid")
    codes = {str(x).strip() for x in df["fund_code"]}
    assert "TLZF9" in codes and "ALBT8" in codes        # 兩種 schema 都吃到(不漏英文分頁)
    _alb = df[df["fund_code"] == "ALBT8"].iloc[0]
    assert _alb["item_type"] == "fund" and _alb["tier"] == "core"
    assert int(float(_alb["invest_twd"])) == 2000


# ── 稽核 FINDING 2:v1→v2 路徑也要擋 schema-leak 鬼列 ────────────
def test_v1_frame_to_v2_drops_ghost_row():
    from repositories.policy.v2 import _v1_frame_to_v2
    df = pd.DataFrame([
        {"policy_id": "P", "fund_url": "ALBT8", "invest_date": "2026-01-01",
         "currency": "美元", "policy_tier": "core"},
        {"policy_id": "fund_url", "fund_url": "fund_url", "invest_date": "invest_date",
         "currency": "currency", "policy_tier": "policy_tier"},              # 鬼列
    ])
    out = _v1_frame_to_v2(df)
    codes = set(out["fund_code"])
    assert "ALBT8" in codes and "FUND_URL" not in codes   # 鬼列不得變幽靈基金


# ── 稽核 FINDING 3:v2 分頁同時有中英文欄 → 不製造重複欄、不崩 ────────
def test_load_all_policies_v2_dup_zh_en_columns_no_crash():
    from repositories.policy.v2 import load_all_policies_v2
    ws = _FakeWS("PA",
                 ["保單編號", "類型", "基金代號", "fund_code", "淨投資金額", "級別"],
                 [{"保單編號": "PA", "類型": "fund", "基金代號": "ZZZ", "fund_code": "F9",
                   "淨投資金額": "1", "級別": "core"}])
    df = load_all_policies_v2(_FakeClient(_FakeSheet([ws])), "sid")
    _fc = df["fund_code"]
    assert getattr(_fc, "ndim", 1) == 1                    # 單一 Series,非重複欄 DataFrame
    assert "F9" in set(_fc)                                 # guard:既有英文欄勝出,不被中文覆蓋
