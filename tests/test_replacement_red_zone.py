"""回歸網 — v19.315:健診「淘汰候選紅區」依賴 build_dividend_summary_row 曝露的 `_verdict`。

紅區(ui/tab_fund_grp_health.py `_render_health_3tables` 頂部)靠篩選 `_verdict == "replace"`
把 MK 4 規則觸發的基金提到最上面。本檔守 SSOT 資料端契約:
1. row 一定含 `_verdict` key(紅區篩選鍵不可消失)。
2. Sharpe<0 且 max_dd<-30%(MK 規則 d)→ verdict = "replace"(進紅區)。
3. 關鍵指標全缺 → verdict = "unknown"(不下假綠燈、不誤進紅區)。
"""
from __future__ import annotations

from services.health.report import build_dividend_summary_row


def test_row_exposes_verdict_key():
    row = build_dividend_summary_row({"metrics": {}, "moneydj_raw": {}}, "TEST0")
    assert "_verdict" in row, "row 缺 _verdict —— 淘汰候選紅區的篩選鍵不可消失"


def test_bad_fund_verdict_is_replace():
    """MK 規則 (d):Sharpe<0 且 max_dd<-30% → replace(該進淘汰候選紅區)。"""
    fd = {"metrics": {"sharpe": -0.8, "max_drawdown": -42.0}, "moneydj_raw": {}}
    row = build_dividend_summary_row(fd, "TESTBAD", holding_years=2.0)
    assert row["_verdict"] == "replace", row["_verdict"]
    assert "🔴" in row["換標的建議"]


def test_empty_fund_verdict_is_unknown_not_keep():
    """關鍵指標全缺 → unknown(§1 不下假綠燈,也不誤判成 replace 進紅區)。"""
    row = build_dividend_summary_row({"metrics": {}, "moneydj_raw": {}}, "TESTEMPTY")
    assert row["_verdict"] == "unknown", row["_verdict"]
