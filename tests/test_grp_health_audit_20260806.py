"""tests/test_grp_health_audit_20260806.py — 2026-08-06 健診 / 批次稽核必修回歸網。

守住六件事(每條註明「修正前是哪一種紅」):
1. σ_abs≈0(停售基金 NAV 走平)→ `calc_hwm_sigma_levels` 誠實回 error,
   下游 `classify_base` 得到 unknown,**不會**變成 🔴 高基期並被列進賣出候選。
   → 修正前:**舊行為衝突紅**(舊版 sigma_rank=0.0 → classify_base 回 "high")。
2. 批次大表有「淨值日期 / 淨值新鮮度」欄,且 `build_batch_unified_row` 真的填了值。
   → 修正前:**舊行為衝突紅**(欄名不在 BATCH_UNIFIED_COLUMNS)。
3. 捕捉率 `low_confidence` / vs大盤 `full_period` 兩個旗標**接得出去**
   —— 欄名在 `_UNIFIED_FRONT`,且 `capture_by_code` 產得出來(PROCESS §4 接線驗證)。
   → 修正前:**舊行為衝突紅**(欄名不存在)。
4. 非 TWD/USD 幣別 → 無基準(留白),不對 SPX 硬比。
   → 修正前:**舊行為衝突紅**(EUR 回 "SPX")。
5. 批次大表的 column_config 覆蓋所有欄,且「備註」拿到寬欄位。
   → 修正前:**舊行為衝突紅**(`unified_column_config` 不存在 → ImportError;
     但第二個 assert 針對的是「批次表根本沒傳 column_config」這件事,
     由 `test_batch_table_passes_column_config` 以原始碼掃描守住)。
6. 回測區不再有第二份「當前訊號」→ 與大表 live 值打架的來源已移除。
   → 修正前:**舊行為衝突紅**(原始碼含該 expander)。
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent


# ── 1. σ≈0(停售 / 剛成立)不得被判成高基期 ────────────────────────────
def test_flat_nav_returns_error_not_zero_sigma_rank():
    from services.precision_service import calc_hwm_sigma_levels
    _idx = pd.date_range("2024-01-01", periods=300, freq="D")
    flat = pd.Series([12.34] * 300, index=_idx)     # 停售 → NAV 完全不動
    r = calc_hwm_sigma_levels(flat)
    assert "error" in r, "σ≈0 必須誠實回 error,不可回未定義的 sigma_rank"
    assert r.get("sigma_rank") is None


def test_flat_nav_does_not_become_high_base():
    """整條鏈:NAV 走平 → σ rank 欄 '—' → classify_base unknown → ⬜ 資料不足。"""
    from services.rotation import classify_base
    from ui.helpers.fund_grp_health.risk import hwm_sigma_by_code
    _idx = pd.date_range("2024-01-01", periods=300, freq="D")
    funds = [{"code": "HALTED", "series": pd.Series([12.34] * 300, index=_idx)}]
    cols = hwm_sigma_by_code(funds)["HALTED"]
    assert cols["σ rank"] == "—"
    assert classify_base(cols["σ rank"]) == "unknown"


def test_flat_nav_not_offered_as_sell_candidate():
    """§1:停售基金不得出現在輪動配對的『賣出』欄。"""
    from services.rotation import suggest_rotation_pairs
    rows = [{"code": "HALTED", "基金名": "停售基金", "σ rank": "—", "基金類別": "股票型"},
            {"code": "LIVE", "基金名": "活躍基金", "σ rank": "-2.30σ", "基金類別": "債券型",
             "4D Grade": "B", "吃本金燈號": "🟢 健康", "操盤評分": 70, "距 HWM %": "-15.0%"}]
    assert [p["sell_code"] for p in suggest_rotation_pairs(rows)] == []


# ── 2. 批次表新鮮度欄(§4.6 分辨週末 vs 停售)─────────────────────────
def test_batch_columns_include_nav_freshness():
    from ui.helpers.fund_grp_health.unified import BATCH_UNIFIED_COLUMNS
    assert "淨值日期" in BATCH_UNIFIED_COLUMNS
    assert "淨值新鮮度" in BATCH_UNIFIED_COLUMNS


def test_nav_freshness_label_three_states():
    import datetime as _dt
    from services.fund_row import nav_freshness_label
    _today = _dt.date(2026, 8, 6)
    assert nav_freshness_label("2026-08-05", _today)[0].startswith("🟢")
    assert nav_freshness_label("2026-08-01", _today)[0].startswith("🟠")
    _stale, _age = nav_freshness_label("2023-08-01", _today)
    assert _stale.startswith("🔴") and _age > 1000
    assert nav_freshness_label("", _today) == ("⬜ 無淨值日期", None)
    assert nav_freshness_label("not-a-date", _today) == ("⬜ 無淨值日期", None)


def test_batch_row_actually_fills_freshness(monkeypatch):
    """接線驗證(PROCESS §4):欄位存在不算數,`build_batch_unified_row` 要真的填。

    拿掉 build_batch_unified_row 裡寫入這兩欄的那幾行,本條就會紅。
    """
    import services.fund_row as FR
    # 2026-08-14 Layer 3-C:production 已改從 L2 讀 —— patch L3 不會生效,
    # 會變成安靜地打真網路(PROCESS §4 假綠)。靶點必須跟著 production 走。
    import services.fx_regime_service as FXR
    import ui.helpers.fund_grp_health.unified as U

    def _fake_process_one_fund(code, principal_twd, *a, **kw):
        return {"code": code, "ok": True, "基金名": "測試基金",
                "ccy": "USD", "_nav_date": "2023-08-01", "_fund_raw": {}}

    monkeypatch.setattr(FR, "process_one_fund", _fake_process_one_fund)
    monkeypatch.setattr(FXR, "fx_regime_by_ccy", lambda *a, **kw: {})   # 不打網路
    row = U.build_batch_unified_row("TESTCODE")
    assert row["淨值日期"] == "2023-08-01"
    assert row["淨值新鮮度"].startswith("🔴")


# ── 3. 兩個可信度旗標必須接得出去(不是算完就丟)────────────────────
def test_confidence_flag_columns_registered():
    from ui.helpers.fund_grp_health.unified import _UNIFIED_FRONT
    _names = [c for c, _ in _UNIFIED_FRONT]
    assert "捕捉樣本" in _names, "capture_ratio.low_confidence 沒接到大表"
    assert "vs 大盤期間" in _names, "benchmark_compare.full_period 沒接到大表"


def test_capture_by_code_emits_flags(monkeypatch):
    """低樣本(各 3 個漲/跌月)→ 捕捉樣本標 ⚠️;短共同歷史 → vs 大盤期間標全期。"""
    import ui.helpers.fund_grp_health.capture as C
    _idx = pd.date_range("2026-01-31", periods=7, freq="ME")
    bench = pd.Series(100 * np.cumprod([1 + x for x in [0] + [0.03] * 3 + [-0.04] * 3]), index=_idx)
    fund = pd.Series(100 * np.cumprod([1 + x for x in [0] + [0.03] * 3 + [-0.008] * 3]), index=_idx)
    monkeypatch.setattr(C, "_benchmark_nav", lambda m: bench)
    out = C.capture_by_code([{"code": "F1", "series": fund, "currency": "USD"}])["F1"]
    assert out["操盤評分"] is not None
    assert out["捕捉樣本"].startswith("⚠️") and "3漲/3跌" in out["捕捉樣本"]
    assert out["vs 大盤期間"].startswith("⚠️")      # 共同歷史 < 1 年 → 全期


def test_capture_blank_explains_why_for_unsupported_currency():
    """EUR 基金 → 三個捕捉值留白,且旗標欄說出**為什麼**(不是空白了事)。"""
    from ui.helpers.fund_grp_health.capture import capture_by_code
    _idx = pd.date_range("2024-01-31", periods=30, freq="ME")
    fund = pd.Series(np.linspace(10, 20, 30), index=_idx)
    out = capture_by_code([{"code": "EU1", "series": fund, "currency": "EUR"}])["EU1"]
    assert out["操盤評分"] is None and out["vs 大盤%"] is None
    assert "EUR" in out["捕捉樣本"]


# ── 4/5. column_config 覆蓋率 + 批次表真的有傳 ──────────────────────
def test_unified_column_config_covers_batch_columns():
    from ui.helpers.fund_grp_health.columns import unified_column_config
    from ui.helpers.fund_grp_health.unified import BATCH_UNIFIED_COLUMNS
    cfg = unified_column_config(batch=True)
    _missing = [c for c in BATCH_UNIFIED_COLUMNS if c not in cfg]
    assert not _missing, f"批次大表這些欄仍無 column_config(無 help/寬度):{_missing}"


def test_note_column_is_wide_and_documented():
    """「備註」= 唯一的失敗原因揭露(§1),必須有寬度 + help。"""
    from ui.helpers.fund_grp_health.columns import batch_column_config
    _note = batch_column_config()["備註"]
    _spec = _note if isinstance(_note, dict) else getattr(_note, "__dict__", {})
    _blob = str(_spec) or str(_note)
    assert "large" in _blob, "「備註」未給寬欄 → 失敗原因仍會被截斷"
    assert "重試" in _blob, "「備註」help 未說明哪類原因值得重試"


def test_batch_table_passes_column_config():
    """接線驗證:設定寫好但沒傳給 st.dataframe 一樣沒效果。

    ⚠️ 走 AST 不走 regex。原版用 `re.search(r"st\\.dataframe\\(...df,...")`,
    而同一個檔案上方的**註解**裡就寫著這串字(在解釋「原本裸 st.dataframe(df, ...)
    改成帶 column_config」)。`re.search` 先命中註解、group 裡當然沒有
    column_config → 恆紅的假失敗,程式碼其實是對的。
    AST 看不到註解,不會再被自己的說明文騙。
    """
    import ast as _ast
    _p = _ROOT / "ui" / "tab_batch_analysis.py"
    src = _p.read_text(encoding="utf-8")
    assert "unified_column_config" in src
    _calls = [n for n in _ast.walk(_ast.parse(src))
              if isinstance(n, _ast.Call)
              and getattr(n.func, "attr", "") == "dataframe"]
    assert _calls, "找不到 st.dataframe 呼叫(結構已變,請更新本測試)"
    assert any(any(k.arg == "column_config" for k in c.keywords) for c in _calls), \
        "批次大表的 st.dataframe 仍未帶 column_config"


# ── 6. 回測區「當前訊號快照」已移除(與大表 live 值打架的第二來源)──
def test_backtest_section_has_no_duplicate_current_signal():
    src = (_ROOT / "ui" / "helpers" / "fund_grp_health" / "backtest_section.py").read_text(
        encoding="utf-8")
    _code_lines = [ln for ln in src.splitlines()
                   if not ln.lstrip().startswith("#")]
    _code = "\n".join(_code_lines)
    assert "current_signal_snapshot" not in _code
    assert "st.expander" not in _code


# ── 7. 配息矩陣:缺值不得畫成 0% 假柱 ────────────────────────────────
def test_dividend_matrix_keeps_none_not_zero():
    """§1:`_rc_ret` / `_rc_div` 對缺值必須保留 None。

    以原始碼掃描守住(圖表本身需 streamlit runtime)。修正前:**舊行為衝突紅**
    (舊版寫 `else 0.0` / `float(... or ... or 0)`)。
    """
    src = (_ROOT / "ui" / "helpers" / "fund_grp_health" / "dividend.py").read_text(
        encoding="utf-8")
    assert "_rc_ret.append(round(_ret_v, 2) if _ret_v is not None else None)" in src
    assert "_resolve_adr_with_fallback" in src, "12M 配息 fallback 應走 SSOT,不再 inline 抄一份"
    # 靜默吞例外(except ...: → 只有 pass)一律不留
    assert not re.search(r"except[^\n]*:\s*\n\s*pass\b", src)
