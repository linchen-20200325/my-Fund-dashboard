"""v19.308 回歸網 — 成立年改讀 MoneyDJ 現成成立日（SSOT fund_inception_years）。

user 2026-07-04：Streamlit Cloud IP 被 MoneyDJ 擋 → 只抓到近 1 月 NAV → 成立年
（原用 series.index[0]）算成 0.1 年、MK 3-3-3 ① 全數誤判不通過。改為「抓 MoneyDJ
頁面現成的成立日期」優先，序列僅當 fallback。本檔鎖住:
1. `fund_inception_years` 純函式：成立日優先 / 序列 fallback / 短序列不硬報。
2. `check_333_fund` 的 C1 改讀 `metrics["inception_date"]`（免依賴本地長歷史）。
"""
from __future__ import annotations

import pandas as pd

from services.fund_screening import check_333_fund, fund_inception_years


def _series(n: int) -> pd.Series:
    """n 個交易日、以「今天」結尾的合成 NAV（相對日期，避免 hard-code 造成 flaky）。"""
    idx = pd.date_range(end=pd.Timestamp.today().normalize(), periods=n, freq="B")
    return pd.Series([10.0 + 0.001 * i for i in range(n)], index=idx)


class TestFundInceptionYears:
    def test_inception_date_preferred(self):
        """有 MoneyDJ 成立日 → 直接用它算年數（不管本地序列多短）。"""
        yrs = fund_inception_years("2008-03-01", _series(30))  # 短序列
        assert yrs is not None and yrs > 15, "成立年應由成立日算出（>15 年）"

    def test_inception_slash_format(self):
        """YYYY/MM/DD 格式也吃（MoneyDJ 常見）。"""
        # fund_inception_years 只吃 ISO；fetcher 已把 / 換成 -，此處驗 ISO 前綴解析
        yrs = fund_inception_years("2010-01-01T00:00:00", _series(30))
        assert yrs is not None and yrs > 14

    def test_no_inception_long_series_uses_series(self):
        """無成立日 + 夠長序列（≥90 筆、≥0.5 年）→ 用序列最早日推算。"""
        yrs = fund_inception_years(None, _series(200))  # ~0.77 年
        assert yrs is not None and 0.5 < yrs < 1.5

    def test_no_inception_short_series_returns_none(self):
        """無成立日 + 過短序列（<90 筆、<0.5 年）→ None（§1 不硬報 0.1 年）。"""
        assert fund_inception_years(None, _series(30)) is None

    def test_garbage_inception_falls_back_to_series(self):
        """成立日格式壞掉 → 落到序列 fallback，不炸。"""
        yrs = fund_inception_years("not-a-date", _series(200))
        assert yrs is not None and 0.5 < yrs < 1.5

    def test_both_missing_returns_none(self):
        assert fund_inception_years(None, None) is None


class TestCheck333ReadsInception:
    def test_short_series_with_moneydj_inception_passes_c1(self):
        """截圖情境：本地序列僅 ~1 月，但 metrics 帶 MoneyDJ 成立日 → ① 成立年正確、通過。"""
        s = _series(30)
        r = check_333_fund(s, metrics={"inception_date": "2005-06-01"})
        assert r["c1_age_years"] is not None and r["c1_age_years"] > 15
        assert r["c1_pass"] is True

    def test_short_series_no_inception_is_insufficient(self):
        """短序列且無成立日 → c1 資料不足（None），不誤報 0.1 年 fail。"""
        s = _series(30)
        r = check_333_fund(s, metrics={})
        assert r["c1_age_years"] is None
        assert r["c1_pass"] is None  # 資料不足 → ❓ 而非 ❌
