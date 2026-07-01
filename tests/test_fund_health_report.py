"""v19.181 — services.health.report 純函式單元測試。

守住共用 row builder 的 schema 與 SSOT 串接行為:
- build_health_analysis_row → 健康分析 row(4D + 6 進階指標 + 3-3-3)
- build_dividend_summary_row → 配息相關 row(adr + 1Y + 吃本金 + 換標的)
- HEALTH_COLUMNS / DIVIDEND_COLUMNS schema 不漂移
"""
from __future__ import annotations

from services.health.report import (
    DIVIDEND_COLUMNS,
    HEALTH_COLUMNS,
    build_dividend_summary_row,
    build_health_analysis_row,
)


class TestHealthAnalysisRow:
    def test_empty_fd_returns_row_with_dashes(self):
        r = build_health_analysis_row({}, "TEST")
        assert r["code"] == "TEST"
        assert r["4D Grade"] == "—"
        assert r["4D Score"] is None
        assert r["Sharpe 1Y"] is None
        assert "MK 3-3-3" in r

    def test_full_metrics_populates_fields(self):
        fd = {
            "moneydj_raw": {"perf": {"1Y": 8.0}, "moneydj_div_yield": 5.0},
            "metrics": {
                "sharpe": 1.2, "std_1y": 12.0,
                "max_drawdown": -15.0,
                "ret_3y_ann": 8.5, "ret_5y_ann": 7.0,
            },
        }
        r = build_health_analysis_row(fd, "X1234")
        assert r["code"] == "X1234"
        assert r["Sharpe 1Y"] == 1.2
        assert r["Max DD %"] == -15.0
        assert r["3Y 年化 %"] == 8.5
        assert r["5Y 年化 %"] == 7.0
        # 4D Grade 應該被算出來(雖具體值取決於 compute_4d_health 邏輯)
        assert r["4D Grade"] not in (None,)

    def test_schema_keys_match_health_columns(self):
        r = build_health_analysis_row({}, "TEST")
        for col in HEALTH_COLUMNS:
            assert col in r, f"row 缺欄位 {col}(HEALTH_COLUMNS 與 row schema 漂移)"

    def test_flat_fd_normalize_works(self):
        """平坦 fd(top-level perf 無 moneydj_raw)應自動 wrap。"""
        flat = {
            "perf": {"1Y": 10.0},
            "metrics": {"sharpe": 0.8},
        }
        r = build_health_analysis_row(flat, "FLAT1")
        assert r["Sharpe 1Y"] == 0.8

    def test_alpha_falls_back_to_ret_1y_total_when_perf_1y_missing(self):
        """v19.290 回歸網:user 反饋「上下兩個面板同一種資料,上面有下面沒有」
        ——追出 Alpha 計算讀的是 `perf["1Y"]`,但短窗口保單代碼兩條寫入路徑
        (wb01 注入 / 本地 350d+ 窗口注入)都不滿足,`perf["1Y"]` 永遠是 None,
        Alpha 因此永遠算不出來 —— 即使同一個 fd 內`metrics.ret_1y_total`
        早就透過 compute_1y_total_return() 的 SSOT fallback chain 算出真實值
        (畫面上「1Y 含息報酬」那格用的正是這個值)。

        本測試鎖住:`perf["1Y"]` 缺、但 `metrics.ret_1y_total` 有值時,
        Alpha 仍應該算出來(用 ret_1y_total 當 tr1y,而非停在 None)。
        """
        fd = {
            "moneydj_raw": {"perf": {}, "moneydj_div_yield": 9.49},
            "metrics": {
                "sharpe": 0.32,
                "ret_1y_total": 2.11,      # 短窗口本地含息計算(46 天)
                "ret_1y_window_days": 46,
                "annual_div_rate": 9.49,
            },
        }
        r = build_health_analysis_row(fd, "SHORT1")
        assert r["Alpha %"] is not None, (
            "perf['1Y'] 缺但 ret_1y_total 有值時,Alpha 仍應 fallback 算出來"
            "(不應該永遠停在 None)"
        )
        assert abs(r["Alpha %"] - (2.11 - 9.49)) < 0.05, (
            f"Alpha 應等於 tr1y(ret_1y_total) - 配息率,實際 {r['Alpha %']}"
        )


class TestDividendSummaryRow:
    def test_empty_fd_returns_row(self):
        r = build_dividend_summary_row({}, "TEST")
        assert r["code"] == "TEST"
        assert r["1Y 含息 %"] is None
        assert r["年化配息率 %"] is None
        assert "資料不足" in r["吃本金燈號 (1Y·MK)"] or "—" in r["吃本金燈號 (1Y·MK)"]
        assert r["換標的建議"].startswith("⬜") or "資料不足" in r["換標的建議"]

    def test_eat_principal_marked(self):
        """高 adr + 低 tr1y → 應顯示 🔴 吃本金。"""
        fd = {
            "moneydj_raw": {
                "perf": {"1Y": 2.0},
                "moneydj_div_yield": 10.0,
            },
            "metrics": {},
        }
        r = build_dividend_summary_row(fd, "EAT1", principal_twd=1_000_000,
                                       holding_years=2)
        assert "吃本金" in r["吃本金燈號 (1Y·MK)"]
        assert r["年化配息率 %"] == 10.0
        assert r["1Y 含息 %"] == 2.0

    def test_replacement_verdict_threaded(self):
        """換標的建議欄位應透過 SSOT 串接,不直接寫死。"""
        fd = {
            "moneydj_raw": {
                "perf": {"1Y": 2.0},
                "moneydj_div_yield": 10.0,
            },
            "metrics": {"sharpe": -0.5, "max_drawdown": -35.0},
        }
        r = build_dividend_summary_row(fd, "REP1", holding_years=2)
        # rule (a) + (d) 都中 → 🔴 換
        assert "🔴" in r["換標的建議"] or "換" in r["換標的建議"]

    def test_schema_keys_match_dividend_columns(self):
        r = build_dividend_summary_row({}, "TEST")
        for col in DIVIDEND_COLUMNS:
            assert col in r, f"row 缺欄位 {col}(DIVIDEND_COLUMNS 與 row schema 漂移)"


class TestSixFactorReadingV182:
    """v19.182 regression — build_health_analysis_row 必須抓得到 6F factors。

    根因:v19.181 `_fdata = fd if "perf" in fd else mj` 在內部 normalize 後
    fd 被改成 nested,條件反轉 → _fdata=mj 但 mj 無 metrics → Sortino/Calmar/
    Expense 全 None。修法:組 `{metrics, perf}` dict 顯式傳入。

    守住:nested fd / 平坦 fd 兩種 shape 都拿得到。
    """

    def test_nested_fd_sortino_present(self):
        """nested fd(Tab2/Tab3 場景):有 moneydj_raw + top-level metrics。"""
        fd = {
            "moneydj_raw": {"perf": {"1Y": 8.5}, "moneydj_div_yield": 5.0},
            "metrics": {"sharpe": 1.2, "sortino": 1.5, "calmar": 0.8,
                        "max_drawdown": -15.0, "expense_ratio": 1.2,
                        "annual_div_rate": 5.0},
        }
        r = build_health_analysis_row(fd, "X")
        assert r["Sortino"] == 1.5, f"v19.182 修法後 nested fd 應拿到 Sortino,實際 {r['Sortino']}"
        assert r["Calmar"] == 0.8, f"Calmar 應 0.8,實際 {r['Calmar']}"
        assert r["費用率 %"] == 1.2, f"Expense 應 1.2,實際 {r['費用率 %']}"

    def test_flat_fd_sortino_present(self):
        """平坦 fd(健診 Tab 場景):top-level 直接有 perf + metrics。"""
        fd = {
            "perf": {"1Y": 8.5}, "moneydj_div_yield": 5.0,
            "metrics": {"sharpe": 1.2, "sortino": 1.5, "calmar": 0.8,
                        "max_drawdown": -15.0, "expense_ratio": 1.2,
                        "annual_div_rate": 5.0},
        }
        r = build_health_analysis_row(fd, "X")
        assert r["Sortino"] == 1.5, "平坦 fd 應拿到 Sortino"
        assert r["Calmar"] == 0.8
        assert r["費用率 %"] == 1.2

    def test_nested_and_flat_same_result(self):
        """同樣資料用 nested vs 平坦 shape 包,row builder 應回相同 6F 值。"""
        metrics = {"sharpe": 1.0, "sortino": 1.2, "calmar": 0.5,
                   "max_drawdown": -10.0, "expense_ratio": 0.9,
                   "annual_div_rate": 4.0}
        nested = {"moneydj_raw": {"perf": {"1Y": 7.0}}, "metrics": metrics}
        flat = {"perf": {"1Y": 7.0}, "metrics": metrics}
        r_n = build_health_analysis_row(nested, "N")
        r_f = build_health_analysis_row(flat, "F")
        for col in ("Sortino", "Calmar", "費用率 %", "Max DD %", "Alpha %"):
            assert r_n[col] == r_f[col], (
                f"nested vs 平坦 {col} 不同(SSOT 違反):{r_n[col]} vs {r_f[col]}"
            )

    def test_metrics_missing_factors_none_not_raise(self):
        """metrics 沒這些欄位 → 應回 None(不該 raise)。"""
        fd = {
            "moneydj_raw": {"perf": {"1Y": 8.0}},
            "metrics": {"sharpe": 1.0},  # 沒 sortino/calmar/expense
        }
        r = build_health_analysis_row(fd, "X")
        assert r["Sortino"] is None
        assert r["Calmar"] is None
        assert r["費用率 %"] is None


class TestColumnsConstants:
    """守住 column 順序常數(供 UI 用)。"""

    def test_health_columns_has_required(self):
        required = {"code", "基金名", "4D Grade", "Sharpe 1Y", "Sortino",
                    "Calmar", "Alpha %", "費用率 %", "Max DD %",
                    "3Y 年化 %", "5Y 年化 %", "MK 3-3-3"}
        assert required <= set(HEALTH_COLUMNS)

    def test_dividend_columns_has_required(self):
        required = {"code", "基金名", "1Y 含息 %", "年化配息率 %",
                    "吃本金燈號 (1Y·MK)", "換標的建議"}
        assert required <= set(DIVIDEND_COLUMNS)
