"""Regression: 持續失業金 (CCSA / CONT_CLAIMS) Z-Score 單位錯位假極端。

User 2026-06-28 回報「評分方式有問題」：中期循環 Z-Score 矩陣顯示
「持續失業金週頻 值 1821000 萬、Z=+57324.01 極端」。

根因（§4.1 量綱陷阱）：services/macro_service.py 建 R["CONT_CLAIMS"] 時
`series=s/10000`（萬人）但 `value=int(v)` 仍是原始人數（~1,821,000）→
Z=(1.82M - 萬人均值~200)/萬人std~32 ≈ +57000 假極端，並汙染「就業」子循環
與整體景氣循環評分。對照上方 ICSA/JOBLESS（L772-780）value/series 都 /10000
為正確寫法。修法：CONT_CLAIMS 的 value/prev 同樣 /10000，與 series 一致。

本測試雙重守衛：
1. 結構：CONT_CLAIMS 區塊 value/prev 必須 /10000（不可 int(v)），與 series 一致。
2. 數值：示範 value 與 series 單位一致時 |Z| 合理，錯位時 |Z| 爆量（記錄根因）。
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd


def _cont_claims_block() -> str:
    src = open("services/macro_service.py", encoding="utf-8").read()
    # 抓 R["CONT_CLAIMS"] = dict(...) 到該 dict 收尾（weight=...）
    m = re.search(r'R\["CONT_CLAIMS"\]\s*=\s*dict\(.*?weight=[^\n]*\)', src, re.S)
    assert m, "找不到 R[\"CONT_CLAIMS\"] = dict(...) 區塊"
    return m.group(0)


def test_cont_claims_value_series_same_unit():
    """value/prev 必須與 series 同單位（皆 /10000，萬人），不可殘留原始人數 int(v)。"""
    block = _cont_claims_block()
    assert "series=s/10000" in block, "series 應為萬人（s/10000）"
    assert "value=round(v/10000" in block, (
        "value 必須 /10000 與 series（萬人）一致，否則 Z-Score 單位錯位爆量假極端"
    )
    assert "value=int(v)" not in block, "value=int(v)（原始人數）為已知 bug 寫法，禁止回退"


def test_unit_mismatch_blows_up_zscore_consistent_is_sane():
    """記錄根因：value 與 series 單位一致 → |Z| 合理；錯位（value 原始/series 萬人）→ |Z| 爆量。"""
    rng = np.random.default_rng(0)
    raw = pd.Series(1_820_000 + rng.normal(0, 30_000, 260))  # 原始人數序列
    v_raw = float(raw.iloc[-1])
    series_wan = raw / 10000  # 萬人

    def z(series, value):
        s = series.dropna()
        mu, sig = float(s.mean()), float(s.std())
        return (float(value) - mu) / sig if sig else None

    z_mismatch = z(series_wan, v_raw)              # bug：value 原始人數
    z_consistent = z(series_wan, round(v_raw / 10000, 1))  # fix：value 萬人

    assert abs(z_mismatch) > 1000, "錯位單位應產生爆量 Z（重現 user 的 +57324 量級）"
    assert abs(z_consistent) < 5, "單位一致時 Z 應落在合理 ±5 內"
