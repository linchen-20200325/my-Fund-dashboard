"""§1 回歸:併入 nav_history 累積序列後,nav_span_days 必須跟著重算(v19.431)。

線上事故:Tab2 標頭「淨值 1579 筆 · 跨度 42 天」自相矛盾 —— 1579 筆日淨值不可能跨 42 天。
根因:nav_span_days 停在 **pre-merge live 序列**(bank_platform 30 筆≈42 天),
finalize_fund_metrics 把 series 換成合併後 1579 筆長序列時沒重算 span。
"""
from __future__ import annotations

import inspect

import numpy as np
import pandas as pd

import services.fund_service as FS


def test_finalize_recomputes_nav_span_from_merged_series(monkeypatch):
    idx = pd.bdate_range("2024-01-02", periods=400)        # ~575 日曆日
    long_s = pd.Series(np.linspace(10.0, 12.0, 400), index=idx)

    # 模擬 nav_history 併入:回傳長序列 + success trace
    monkeypatch.setattr(
        FS, "_merge_nav_history_series",
        lambda s, code: (long_s, {"source": "nav_history", "success": True,
                                  "note": "累積序列併入 +370 筆（live 30 → 400）"}),
    )
    result = {
        "series": pd.Series([10.0, 10.1],
                            index=pd.to_datetime(["2026-08-09", "2026-08-10"])),
        "fund_code": "TESTX", "data_source": "bank_platform",
        "nav_span_days": 1,                                # pre-merge 陳舊值(42 的縮影)
        "dividends": [], "source_trace": [],
    }
    out = FS.finalize_fund_metrics(result)

    _expected = int((long_s.index.max() - long_s.index.min()).days)
    assert out["nav_span_days"] == _expected              # 跟合併後 series 一致
    assert out["nav_span_days"] > 500                      # 不再停在 pre-merge 的 1
    assert len(out["series"]) == 400                        # series 確實已換成長序列


def test_finalize_source_recomputes_span_in_success_block():
    """source-lock:重算必須在 merge success 區塊、且從合併後 series 的 index 算(防重構誤刪)。"""
    src = inspect.getsource(FS.finalize_fund_metrics)
    assert 'result["nav_span_days"]' in src and "s.index.max()" in src, (
        "finalize_fund_metrics 併入累積序列後須重算 nav_span_days(從合併後 series 首末日),"
        "否則 Tab2 標頭『N 筆 · 跨度 X 天』會不同源(§1)"
    )


def test_tab2_freshness_falls_back_to_series_date():
    """source-lock:淨值日純量欄缺時(bank_platform 不回傳)退用合併後 series 末日。"""
    from pathlib import Path
    txt = (Path(__file__).resolve().parent.parent / "ui" / "tab2_single_fund.py").read_text(encoding="utf-8")
    assert "s.index.max().date()" in txt and "DatetimeIndex" in txt, (
        "缺 nav_date 純量時應退用 series 末日(且僅在 DatetimeIndex 時),讓有日期的來源誠實顯示最新淨值日"
    )
