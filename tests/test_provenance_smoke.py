"""F-PROV-1 smoke test — 確保 schema-additive provenance 契約不退化(v19.106).

目的:CLAUDE.md §2.2 規定核心 fetcher 須帶 `source` + `fetched_at`,本檔
驗證主要 L1 + L2 fetcher 在「成功 path」回傳的 DataFrame / Series / dict 確實
含 provenance 欄位 / attrs / dict keys,防止後續 mechanical refactor 不小心拆掉。

策略:檔案內容靜態檢查為主(不需 import 含 streamlit / 外部 SDK 的 module);
僅關鍵 fetcher 走 monkeypatch 驗證 runtime schema。
"""
from __future__ import annotations

import os
import pandas as pd
import pytest


PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(name: str) -> str:
    with open(os.path.join(PROJ_ROOT, name), "r", encoding="utf-8") as f:
        return f.read()


def _read_pkg(pkg_path: str) -> str:
    """讀 sub-package 所有 .py concat(支援 P1-5 / P2-3 拆檔後字串搬子檔)。"""
    import glob as _g
    files = sorted(_g.glob(os.path.join(PROJ_ROOT, pkg_path, "*.py")))
    return "\n".join(open(f, "r", encoding="utf-8").read() for f in files)


# ── 1. macro_repository.fetch_fred:DataFrame 須含 source + fetched_at ──
def test_fetch_fred_carries_source_columns(monkeypatch):
    """phase 1 v19.82 — fetch_fred(成功 path)DataFrame 須含 schema-additive
    source/fetched_at columns(SSOT: repositories.macro_repository)。"""
    try:
        from repositories import macro_repository
    except ImportError as e:
        pytest.skip(f"macro_repository import failed: {e}")

    fake_json = {
        "observations": [
            {"date": "2026-05-01", "value": "3.1"},
            {"date": "2026-06-01", "value": "3.2"},
        ]
    }

    class _MockResp:
        status_code = 200
        text = ""
        def json(self):
            return fake_json
        def raise_for_status(self):
            pass

    def _mock_fetch(*args, **kwargs):
        return _MockResp()

    # B1 v19.205: fetch_fred 在 fred.py 內呼叫 fetch_url,patch sub-module binding。
    monkeypatch.setattr("repositories.macro.fred.fetch_url", _mock_fetch, raising=False)
    if hasattr(macro_repository.fetch_fred, "cache_clear"):
        macro_repository.fetch_fred.cache_clear()
    df = macro_repository.fetch_fred("CPILFESL", "dummy-key")
    assert isinstance(df, pd.DataFrame)
    if df.empty:
        pytest.skip("fetch_fred returned empty (fixture mismatch)")
    assert "source" in df.columns, "fetch_fred 須帶 schema-additive `source` 欄"
    assert "fetched_at" in df.columns, "fetch_fred 須帶 schema-additive `fetched_at` 欄"
    src = str(df["source"].iloc[0])
    assert src.startswith("FRED:"), f"source 須以 `FRED:` 開頭,實際 = {src}"


# ── 2. fund_repository:多 NAV fetcher 命名約定靜態檢查 ──
def test_fund_repository_nav_provenance_naming():
    """phase 6-17 v19.92-103 — fund_repository 各 NAV fetcher 須用約定命名。

    v19.202 第三階段 A1:P1-5 god module 拆 `repositories/fund/` 子套件後,
    NAV 命名字串搬到 sources.py / nav_metrics.py / fx_and_main.py;主檔變
    28 LOC shim 無字串,改讀整個子套件 concat。
    """
    src = _read_pkg("repositories/fund")
    # phase 6-7:FundClear / TDCC meta + NAV
    assert "FundClear:GetFundBasicInfo" in src, "_src_fundclear_meta 命名"
    assert "TDCC:OpenAPI" in src, "_src_tdcc_meta 命名"
    assert "FundClear:GetFundNAV" in src, "_src_fundclear_nav 命名"
    # phase 9-10:MoneyDJ / Cnyes / Morningstar / Yahoo NAV
    assert "MoneyDJ:" in src, "MoneyDJ fetcher 命名"
    assert "Cnyes:" in src, "Cnyes fetcher 命名"
    assert "Morningstar:" in src, "Morningstar fetcher 命名"
    assert "Yahoo:" in src, "Yahoo fetcher 命名"
    # phase 11-12:其他 fetcher
    assert "AllianzGI:" in src, "AllianzGI NAV 命名"
    assert "InsuranceSubdomain:" in src, "Insurance subdomain NAV 命名"
    # phase 13:dict-return MoneyDJ wb01/wb07/yp013000
    assert ":wb01" in src, "fetch_performance_wb01 命名"
    assert ":wb07" in src, "fetch_risk_metrics 命名"
    # phase 17:orchestrator-level
    assert "nav_source_used" in src, "fetch_fund_by_key 須暴露 nav_source_used"


# ── 3. services 層:phase 18-19 wrapper 命名約定 ──
def test_services_layer_provenance_naming():
    """phase 18 v19.104 + phase 19 v19.105 — L2 services wrapper 命名約定。"""
    cb_src = _read("services/crisis_backtest.py")
    assert "Yahoo:fetch_yf_close" in cb_src, "crisis_backtest 命名"
    assert "crisis_backtest" in cb_src, "phase 18 marker"

    # v19.202 第三階段 A1:P2-3 拆 services/calibration/ 後,實作搬子檔。
    mfo_src = _read("services/calibration/multi_factor.py")
    assert "multi_factor" in mfo_src, "multi_factor_optimization 命名"
    assert "_stamp_prov" in mfo_src, "phase 18 _stamp_prov helper 存在"

    # phase 19:us_liquidity_engine / valuation / risk_calibration
    ule_src = _read("services/us_liquidity_engine.py")
    assert "_provenance" in ule_src, "us_liquidity_engine orchestrator _provenance 存在"
    assert "FRED:" in ule_src, "us_liquidity_engine FRED 命名"

    vl_src = _read("services/valuation.py")
    assert "_provenance" in vl_src, "valuation.detect_valuation _provenance 存在"
    assert "FRED:" in vl_src or "GDPNOW" in vl_src, "valuation FRED 命名"

    # v19.202 第三階段 A1:P2-3 拆 services/calibration/ 後,實作搬 risk.py
    rc_src = _read("services/calibration/risk.py")
    assert "_provenance" in rc_src, "risk_calibration notes._provenance 存在"
    assert "FRED:" in rc_src, "risk_calibration FRED 命名"


# ── 4. reconcile pattern 不退化 ──
def test_reconcile_module_still_present():
    """services/reconcile.py 提供 5 個對帳 wrapper(F-RECON-1 v19.88-90),
    UI tab2 v19.91 渲染 3 組 chip 須有 caller 端入口。"""
    assert os.path.exists(os.path.join(PROJ_ROOT, "services/reconcile.py"))
    assert os.path.exists(os.path.join(PROJ_ROOT, "ui/tab2_single_fund.py"))
    rec_src = _read("services/reconcile.py")
    assert "reconcile_pair" in rec_src, "reconcile_pair 核心函式存在"
    # UI 接入 3 組 chip(v19.91)
    ui_src = _read("ui/tab2_single_fund.py")
    assert "sharpe_reconcile" in ui_src, "Sharpe chip 存在"
    assert "div_yield_reconcile" in ui_src, "配息殖利率 chip 存在"
    assert "ret_1y_reconcile" in ui_src, "1Y 報酬 chip 存在"
