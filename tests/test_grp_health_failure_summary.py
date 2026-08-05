"""test_grp_health_failure_summary — 組合健診失敗摘要前置 + Sharpe 來源欄收合。

2026-08-05 稽核:
- 🟡 必修 4:輸入 2 檔只成功 1 檔時,KPI「檢查檔數」只算成功數,而「❌ 抓取失敗」
  區在 **226 行渲染之後**(淘汰候選 / 48+ 欄大表 / PK / 換標 / 景氣適配 / 相關性 /
  比較圖 / 配息明細)—— 使用者看到「1」要捲很久才知道另一檔怎麼了。
- 🟢 選作 6:`Sharpe 來源` 欄在全批同源時逐列重複、零資訊量。收合**只做在呈現層**,
  `_UNIFIED_FRONT` / `BATCH_UNIFIED_COLUMNS` 欄序常數完全不動
  (`tests/test_risk_metric_disclosure.py:329-330` 續綠)。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from ui.tab_fund_grp_health import _fold_uniform_sharpe_source

_SRC = (Path(__file__).resolve().parents[1] / "ui" / "tab_fund_grp_health.py"
        ).read_text(encoding="utf-8")


# ══════════════════════════════════════════════════════════════
# 必修 4 — 失敗摘要必須排在 KPI 之前
# ══════════════════════════════════════════════════════════════
class TestFailureSummaryPlacement:
    def test_error_block_precedes_kpi_columns(self):
        """**修正前必紅**:修正前第一個 `if err_rows:` 出現在 KPI 之後 226 行。"""
        _kpi = _SRC.index("k1, k2, k3, k4, k5 = st.columns(5)")
        # 比對「真程式碼」而非註解字串:縮排 + 緊接 st.error 的那一段
        _err = _SRC.index("\n        if err_rows:\n            st.error(")
        assert _err < _kpi, (
            "失敗摘要仍排在 KPI 之後 —— 使用者看到『檢查檔數 1』時無從得知另一檔為何消失")

    def test_kpi_shows_failed_delta(self):
        """**修正前必紅**:`k1.metric("檢查檔數", len(ok_rows))` 原本沒有 delta。"""
        assert 'delta=(f"-{len(err_rows)}" if err_rows else None)' in _SRC

    def test_failed_delta_is_not_rendered_green(self):
        """抓取失敗是**壞消息**,delta 必須是紅色 → 不得用 `delta_color="inverse"`。

        **修正前必紅**。Streamlit 契約:
          normal(預設) → 負值紅、正值綠
          inverse      → 負值**綠**、正值紅   ← 給「成本下降是好事」用
        前一版誤用 inverse,畫面渲染成「檢查檔數 1 🟢 −1」= 少掉一檔是好消息,
        方向與修正目的完全相反;而舊測試 `assert 'delta_color="inverse"' in _SRC`
        把這個 bug **鎖成規格**(PROCESS.md §4 案例 #4「測試把錯誤制度化」的變體)。
        """
        assert 'delta_color="inverse"' not in _SRC, (
            "抓取失敗的 delta 被設成 inverse → 負值會渲染成綠色,壞消息看起來像好消息")

    def test_full_failure_section_kept(self):
        """明細區(代號 + 逐條 st.error)保留在原處,前置摘要不取代它。"""
        assert "#### ❌ 抓取失敗" in _SRC

    def test_error_summary_carries_code_and_reason(self):
        """摘要必須含代號與錯誤原因(§1:缺料要講清楚哪一筆、為什麼)。"""
        assert "r.get('code', '?')" in _SRC and "r.get('error', '?')" in _SRC

    def test_no_new_inline_hex_colour(self):
        """必修 4 用 st.error 原生元件,不得在 UI 層新寫死色票(§3.3)。"""
        import re

        _seg = _SRC[_SRC.index("稽核 🟡 必修 4"):][:1400]
        assert "st.error(" in _seg, "失敗摘要未使用 st.error 原生元件"
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", _seg), "必修 4 區段出現寫死色票"


# ══════════════════════════════════════════════════════════════
# 選作 6 — Sharpe 來源欄動態收合(df 層,常數不動)
# ══════════════════════════════════════════════════════════════
class TestFoldUniformSharpeSource:
    def test_uniform_source_column_dropped(self):
        _df = pd.DataFrame({"code": ["A", "B", "C"],
                            "Sharpe 來源": ["wb07 1Y(官方)"] * 3})
        _out, _lbl = _fold_uniform_sharpe_source(_df)
        assert "Sharpe 來源" not in _out.columns
        assert _lbl == "wb07 1Y(官方)"
        assert list(_out["code"]) == ["A", "B", "C"]      # 其餘欄不動

    def test_mixed_period_keeps_column(self):
        """真混期正是本欄存在的理由(§2.2)—— 絕不可收合。"""
        _df = pd.DataFrame({"code": ["A", "B"],
                            "Sharpe 來源": ["wb07 1Y(官方)", "⚠️ wb07 6M(非1Y)"]})
        _out, _lbl = _fold_uniform_sharpe_source(_df)
        assert "Sharpe 來源" in _out.columns and _lbl is None

    def test_any_missing_value_keeps_column(self):
        _df = pd.DataFrame({"code": ["A", "B"],
                            "Sharpe 來源": ["wb07 1Y(官方)", None]})
        _out, _lbl = _fold_uniform_sharpe_source(_df)
        assert "Sharpe 來源" in _out.columns and _lbl is None

    def test_all_unknown_is_still_uniform(self):
        """全部 `⬜ —` 也是單一來源狀態 → 收合並在 caption 照實說『都沒有來源』。"""
        _df = pd.DataFrame({"code": ["A", "B"], "Sharpe 來源": ["⬜ —", "⬜ —"]})
        _out, _lbl = _fold_uniform_sharpe_source(_df)
        assert "Sharpe 來源" not in _out.columns and _lbl == "⬜ —"

    def test_column_absent_is_noop(self):
        """Tab3 持倉健診不供 extra → 整組欄不出現,不得炸。"""
        _df = pd.DataFrame({"code": ["A"]})
        _out, _lbl = _fold_uniform_sharpe_source(_df)
        assert list(_out.columns) == ["code"] and _lbl is None

    def test_empty_df_is_noop(self):
        _df = pd.DataFrame({"code": [], "Sharpe 來源": []})
        _out, _lbl = _fold_uniform_sharpe_source(_df)
        assert _lbl is None

    def test_none_df_is_noop(self):
        assert _fold_uniform_sharpe_source(None) == (None, None)


class TestFoldIsWiredIn:
    def test_render_health_table_consumes_fold(self):
        """**修正前必紅** —— 收合函式若沒接進 `_render_health_table` 就是 0 consumer。"""
        assert "df, _sharpe_src_uniform = _fold_uniform_sharpe_source(df)" in _SRC
        assert "if _sharpe_src_uniform:" in _SRC, "收合後沒有把單一來源用 caption 講一次"

    def test_ssot_column_constants_untouched(self):
        """收合只在 df 層 —— 欄序常數必須維持原樣,否則 disclosure 測試會斷。"""
        from ui.helpers.fund_grp_health.unified import (
            BATCH_UNIFIED_COLUMNS,
            _UNIFIED_FRONT,
        )
        _front = [c for c, _ in _UNIFIED_FRONT]
        assert _front.index("Sharpe 來源") == _front.index("Sharpe 1Y") + 1
        assert "Sharpe 來源" in BATCH_UNIFIED_COLUMNS


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
