"""test_tab2_single_fund.py — ui/tab2_single_fund.py smoke 測試（v18.126 B-C.4）

驗證 B-C.4 抽出後 Tab2 render 函式：
- module import 不報錯
- render_single_fund_tab 是 callable + 無位置 arg
- 內部 _calc_data_health helper 與 ui.helpers.session 同源
- _friendly_error / _is_core_fund alias 從 ui.helpers.session 正確 import

不直接 mock-render（Tab2 內容複雜、需大量 session_state 鋪墊，留 deploy 驗證）
"""
from __future__ import annotations


def test_module_imports_ok():
    """tab2_single_fund.py 可被 import；render_single_fund_tab 無位置 arg。"""
    import fund_fetcher  # noqa: F401
    from ui.tab2_single_fund import render_single_fund_tab
    import inspect
    assert callable(render_single_fund_tab)
    sig = inspect.signature(render_single_fund_tab)
    assert len(sig.parameters) == 0, "render_single_fund_tab 應為純無參數函式"


def test_friendly_error_imported():
    """_friendly_error 從 ui.helpers.session 正確 import."""
    import fund_fetcher  # noqa: F401
    from ui.tab2_single_fund import _friendly_error
    from ui.helpers.session import friendly_error
    assert _friendly_error is friendly_error


def test_is_core_fund_imported():
    """_is_core_fund 從 ui.helpers.session 正確 import."""
    import fund_fetcher  # noqa: F401
    from ui.tab2_single_fund import _is_core_fund
    # 用幾個關鍵字驗 round-trip
    assert _is_core_fund("摩根多重收益基金") is True
    assert _is_core_fund("AI 半導體基金") is False
    assert _is_core_fund("") is False


def test_calc_data_health_returns_pct_traffic():
    """_calc_data_health 應 delegate 給 ui.helpers.session.calc_data_health。"""
    import fund_fetcher  # noqa: F401
    from ui.tab2_single_fund import _calc_data_health
    ind = {"PMI": {"value": 50}, "VIX": {"value": 18}}   # 2/16 = 12.5%
    pct, traffic = _calc_data_health(ind)
    assert pct == 12
    assert traffic == "🔴"




# ──────────────────────────────────────────────────────────────
# v18.258：投資試算 section（每百萬投入 → 單位數 / 配息估算）
# ──────────────────────────────────────────────────────────────
def test_invest_calc_section_present():
    """Tab2 應在 AI 上方多出「💰 投資試算」section（v18.258）。"""
    from pathlib import Path
    src = (Path(__file__).parents[1] / "ui" / "tab2_single_fund.py").read_text(encoding="utf-8")
    assert "#### 💰 投資試算" in src, "缺少投資試算 section 標題"
    assert "可申購單位數" in src, "缺少『可申購單位數』指標"
    # 應該支援配息型 + 累積型兩種分支
    assert "年化配息" in src, "缺少年化配息計算"
    assert "累積型" in src, "缺少累積型基金的 fallback 分支"


def test_invest_calc_above_ai_section():
    """投資試算 section 必須在『④ AI 深度解盤』上方（順序敏感）。"""
    from pathlib import Path
    src = (Path(__file__).parents[1] / "ui" / "tab2_single_fund.py").read_text(encoding="utf-8")
    _idx_calc = src.find("#### 💰 投資試算")
    _idx_ai = src.find("### ④ AI 深度解盤")
    assert _idx_calc > 0 and _idx_ai > 0
    assert _idx_calc < _idx_ai, "投資試算必須在 AI 深度解盤上方"


def test_invest_calc_stashed_to_ai_snapshot():
    """試算結果應 stash 到 session_state 並進 AI snapshot。"""
    from pathlib import Path
    src = (Path(__file__).parents[1] / "ui" / "tab2_single_fund.py").read_text(encoding="utf-8")
    assert '_calc_invest_' in src, "缺少 session_state stash key"
    # AI snapshot 段應讀取試算 stash
    assert 'st.session_state.get(f"_calc_invest_' in src
    assert "投資試算（每百萬可申購單位與配息估算）" in src, \
        "sections 清單必須宣告投資試算章節"


# ──────────────────────────────────────────────────────────────
# v18.259：投資試算 TWD 換算（即時 FX rate 走 get_latest_fx）
# ──────────────────────────────────────────────────────────────
def test_invest_calc_fetches_fx_rate():
    """非 TWD 基金應呼叫 get_latest_fx 抓 {CCY}TWD=X 即時匯率。"""
    from pathlib import Path
    src = (Path(__file__).parents[1] / "ui" / "tab2_single_fund.py").read_text(encoding="utf-8")
    # v19.247 R16:EX-PASSTHRU-1 升級 — UI 改走 L2 services.fund_service.get_latest_fx
    assert "from services.fund_service import get_latest_fx" in src, \
        "必須 import get_latest_fx 抓即時匯率(v19.247 R16 後走 L2 facade)"
    # v18.264：簽名加 fred_api_key 後位置/kwarg 均可，只驗 ticker pair 出現
    assert 'get_latest_fx(f"{_ccy}TWD=X"' in src, \
        "應呼叫 get_latest_fx 用 {CCY}TWD=X pair（簽名 v18.264 後可加 fred_api_key）"
    # v18.278：normalize 後 _ccy 已是 ISO，改用 != "TWD"（不需 .upper()）
    assert '_ccy != "TWD"' in src, "TWD 基金應跳過 FX 抓取（v18.278 後 normalize → 不需 .upper()）"


def test_invest_calc_twd_conversion_displayed():
    """配息型 + 累積型分支都應顯示 TWD 換算結果。"""
    from pathlib import Path
    src = (Path(__file__).parents[1] / "ui" / "tab2_single_fund.py").read_text(encoding="utf-8")
    # 換算 TWD 提示文字
    assert "💱 **換算 TWD**" in src, "缺少 TWD 換算的 success 提示"
    # FX 抓取失敗的 fallback
    assert "無法取得" in src and "即時匯率" in src, \
        "FX 抓取失敗應顯示 fallback warning"


def test_invest_calc_stash_includes_twd_fields():
    """session_state stash 應包含 fx_to_twd / amount_twd 等 TWD 欄位。"""
    from pathlib import Path
    src = (Path(__file__).parents[1] / "ui" / "tab2_single_fund.py").read_text(encoding="utf-8")
    # 必須 stash 換算後 TWD 數字供 AI 使用
    assert '"fx_to_twd"' in src
    assert '"amount_twd"' in src
    assert '"annual_dividend_twd"' in src, "配息型 stash 缺 annual_dividend_twd"
    assert '"monthly_dividend_twd"' in src, "配息型 stash 缺 monthly_dividend_twd"
    assert '"proj_1y_twd"' in src, "累積型 stash 缺 proj_1y_twd"


def test_ai_snapshot_includes_twd_translation():
    """AI snapshot 在有 FX 時應拼入 TWD 換算字串。"""
    from pathlib import Path
    src = (Path(__file__).parents[1] / "ui" / "tab2_single_fund.py").read_text(encoding="utf-8")
    assert "TWD 換算" in src, "snapshot 缺少 TWD 換算字串"
    assert "_cs_fx" in src, "snapshot 應讀 fx_to_twd"
    assert "_cs_amt_twd" in src, "snapshot 應讀 amount_twd"


# ──────────────────────────────────────────────────────────────
# v18.260p6：投入金額改為 TWD（換原幣算單位/月配息/月配股）
# ──────────────────────────────────────────────────────────────
def test_invest_calc_input_label_is_twd():
    """投入金額 label 必須改為「新台幣 TWD」（不再用基金原幣）。"""
    from pathlib import Path
    src = (Path(__file__).parents[1] / "ui" / "tab2_single_fund.py").read_text(encoding="utf-8")
    assert "投入金額（新台幣 TWD）" in src, "label 應為「投入金額（新台幣 TWD）」"
    # 舊 label 不應存在
    assert "投入金額（基金原幣別：" not in src, "舊原幣 label 應移除"


def test_invest_calc_stash_includes_amount_local_and_monthly_units():
    """stash 應新增 amount_local（換原幣）+ monthly_dividend_units（月配股）。"""
    from pathlib import Path
    src = (Path(__file__).parents[1] / "ui" / "tab2_single_fund.py").read_text(encoding="utf-8")
    assert '"amount_local"' in src, "stash 缺 amount_local（換原幣後本金）"
    assert '"monthly_dividend_units"' in src, "stash 缺 monthly_dividend_units（月配股）"


def test_invest_calc_metric_cards_show_twd():
    """metric 卡主秀「月配息（TWD）」+「月配股（單位）」。"""
    from pathlib import Path
    src = (Path(__file__).parents[1] / "ui" / "tab2_single_fund.py").read_text(encoding="utf-8")
    assert '"月配息（TWD）"' in src, "metric 應主秀「月配息（TWD）」"
    assert '"月配股（單位）"' in src, "metric 應新增「月配股（單位）」"


def test_invest_calc_manual_fx_fallback():
    """FX 抓不到時應提供手動 number_input fallback（不擋流程）。"""
    from pathlib import Path
    src = (Path(__file__).parents[1] / "ui" / "tab2_single_fund.py").read_text(encoding="utf-8")
    assert "_fx_manual" in src, "缺少手動 FX 模式 flag"
    assert "切換手動模式" in src, "缺少手動模式切換提示"
    assert "手動填 1" in src, "缺少手動填匯率 input label"
