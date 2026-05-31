"""test_tab1_macro.py — ui/tab1_macro.py smoke 測試（v18.127 B-C.5）

驗證 B-C.5 抽出後 Tab1 render 函式：
- module import OK
- render_macro_tab callable + 無位置 arg（與其他 4 個 tab 同設計）
- render_indicator_map private helper 也 callable
- _calc_data_health / _friendly_error alias 正確
"""
from __future__ import annotations


def test_module_imports_ok():
    """tab1_macro.py 可被 import；render_macro_tab 無位置 arg。"""
    import fund_fetcher  # noqa: F401
    from ui.tab1_macro import render_macro_tab
    import inspect
    assert callable(render_macro_tab)
    sig = inspect.signature(render_macro_tab)
    assert len(sig.parameters) == 0, "render_macro_tab 應為純無參數函式"


def test_render_indicator_map_callable():
    """render_indicator_map (Tab1 私有 Sankey helper) 從 app.py 搬入後 callable。"""
    import fund_fetcher  # noqa: F401
    from ui.tab1_macro import render_indicator_map
    import inspect
    assert callable(render_indicator_map)
    assert len(inspect.signature(render_indicator_map).parameters) == 0


def test_friendly_error_alias():
    """_friendly_error 從 ui.helpers.session 正確 import。"""
    import fund_fetcher  # noqa: F401
    from ui.tab1_macro import _friendly_error
    from ui.helpers.session import friendly_error
    assert _friendly_error is friendly_error


def test_calc_data_health_wrapper():
    """_calc_data_health(ind) delegate to ui.helpers.session。"""
    import fund_fetcher  # noqa: F401
    from ui.tab1_macro import _calc_data_health
    ind = {"PMI": {"value": 50}}
    pct, traffic = _calc_data_health(ind)
    assert pct == 6
    assert traffic == "🔴"


def test_app_py_shim_render_indicator_map_still_works():
    """app.py 保留 render_indicator_map shim（純 source 驗證避免觸發 streamlit）。"""
    from pathlib import Path
    src = (Path(__file__).parent / "app.py").read_text(encoding="utf-8")
    # B-C.5 後應該有 shim line
    assert "from ui.tab1_macro import render_indicator_map" in src


# ──────────────────────────────────────────────────────────────
# v18.255 _build_macro_ai_snapshot 9 章節白話翻譯 + 校準三段式
# ──────────────────────────────────────────────────────────────
class _FakeSessionState(dict):
    """模擬 st.session_state（dict + attribute access）。"""
    def __getattr__(self, k):
        return self.get(k)
    def __setattr__(self, k, v):
        self[k] = v


def _mock_streamlit(monkeypatch, session_state: dict):
    """把 streamlit.session_state 換成 fake dict，讓 snapshot 能讀。"""
    import streamlit as st
    monkeypatch.setattr(st, "session_state", _FakeSessionState(session_state))


def test_snapshot_sections_include_all_new_v255():
    """v18.255：sections 清單包含 9 個新章節 + 校準健檢 + 既有 5 章節 + 新聞時事。"""
    import fund_fetcher  # noqa: F401
    from ui.tab1_macro import _build_macro_ai_snapshot
    _, _, sections = _build_macro_ai_snapshot({}, {}, {}, {}, [])
    must_have = ["景氣位階與分數", "校準健檢", "流動性壓力", "景氣循環羅盤",
                 "23 項加扣分明細", "資本防線", "倒掛翻正歷史回測",
                 "總經因果鏈", "細項燈號回測", "變數重要性",
                 "台股熱錢三角交叉", "新聞時事"]
    for sec in must_have:
        assert sec in sections, f"sections 缺 {sec}"


def test_snapshot_reads_liquidity_stash(monkeypatch):
    """v18.255：session_state['_macro_liquidity'] 有資料時，snapshot 應出現「流動性壓力」段。"""
    import fund_fetcher  # noqa: F401
    from ui.tab1_macro import _build_macro_ai_snapshot
    _mock_streamlit(monkeypatch, {
        "_macro_liquidity": {
            "value": 1.45, "tier": "警戒", "signal": "🟡",
            "verdict": "深水區流動性轉緊，留意 risk-off",
            "top_contrib": [
                {"name": "VIX", "contrib": 0.6},
                {"name": "HY 利差", "contrib": 0.4},
            ],
        },
    })
    snap, _, _ = _build_macro_ai_snapshot({}, {}, {}, {}, [])
    assert "流動性壓力" in snap
    assert "警戒" in snap
    assert "VIX" in snap
    assert "深水區流動性轉緊" in snap


def test_snapshot_reads_capital_line_stash(monkeypatch):
    """v18.255：本金侵蝕基金應出現在白話摘要。"""
    import fund_fetcher  # noqa: F401
    from ui.tab1_macro import _build_macro_ai_snapshot
    _mock_streamlit(monkeypatch, {
        "_macro_capital_line": {
            "n_funds": 5,
            "n_eroded": 2,
            "eroded_funds": [
                {"name": "高收益債 A", "tr1y": 2.0, "adr": 8.0},
            ],
        },
    })
    snap, _, _ = _build_macro_ai_snapshot({}, {}, {}, {}, [])
    assert "本金侵蝕" in snap
    assert "2/5" in snap
    assert "高收益債 A" in snap


def test_snapshot_calibration_three_step_format(monkeypatch):
    """v18.255：校準健檢改三段式（代表/為什麼/該怎麼做）。"""
    import fund_fetcher  # noqa: F401
    from ui.tab1_macro import _build_macro_ai_snapshot
    _mock_streamlit(monkeypatch, {
        "_cal_macro_score": {
            "src": "真實 FRED + SPX × 10 年（120 月）",
            "horizon": 12,
            "cur_score": 6.41,
            "cur_phase": "Expansion",
            "overall_acc_pct": 83.3,
            "phase_acc": [{"phase": "Expansion", "hit_rate_pct": 81, "n": 79}],
            "grid_top": None,
        },
        "_cal_risk_score": {
            "src": "真實 FRED + SPX × 10 年（120 月）",
            "horizon": 6,
            "drawdown_pct": -20,
            "rolling_win": 30,
            "no_hit": True,
        },
    })
    snap, _, _ = _build_macro_ai_snapshot({}, {}, {}, {}, [])
    # 三段式關鍵字
    assert "【代表】" in snap
    assert "【為什麼】" in snap
    assert "【該怎麼做】" in snap
    # no_hit 應該有放寬建議
    assert "放寬" in snap
    # 命中率數字
    assert "83.3" in snap


def test_snapshot_reads_hot_money_divergence(monkeypatch):
    """v18.255：熱錢三角交叉背離應在 snapshot 標註。"""
    import fund_fetcher  # noqa: F401
    from ui.tab1_macro import _build_macro_ai_snapshot
    _mock_streamlit(monkeypatch, {
        "_macro_hot_money": {
            "date": "2026-05-30",
            "state": "背離｜熱錢停泊匯市",
            "is_divergence": True,
            "interpretation": "外資匯入但暫不進股市",
            "foreign_net_yi": 120.0,
            "roll_flow": 500.0,
            "roll_apprec_pct": 0.8,
            "window": 5,
        },
    })
    snap, _, _ = _build_macro_ai_snapshot({}, {}, {}, {}, [])
    assert "熱錢停泊匯市" in snap
    assert "背離警示" in snap
    assert "外資匯入但暫不進股市" in snap


def test_snapshot_no_state_no_section(monkeypatch):
    """v18.255：當 session_state 空時，snapshot 不應該出現新章節資料行（但 sections 清單仍含 key）。"""
    import fund_fetcher  # noqa: F401
    from ui.tab1_macro import _build_macro_ai_snapshot
    _mock_streamlit(monkeypatch, {})
    snap, _, sections = _build_macro_ai_snapshot({}, {}, {}, {}, [])
    # 沒 stash → snapshot 不應出現「流動性壓力」「本金侵蝕」「熱錢」等具體判讀
    assert "流動性壓力：" not in snap
    assert "資本防線：" not in snap
    assert "台股熱錢三角交叉" not in snap
    # 但 sections 清單仍含 key（讓 AI widget 知道有這個維度可以問）
    assert "流動性壓力" in sections


def test_snapshot_reads_23items_top_contributors(monkeypatch):
    """v18.255：23 項明細 Top3 正/負貢獻寫入 snapshot。"""
    import fund_fetcher  # noqa: F401
    from ui.tab1_macro import _build_macro_ai_snapshot
    _mock_streamlit(monkeypatch, {
        "_macro_23items": {
            "n_total": 23, "n_pos": 12, "n_neg": 8,
            "top_pos": [{"name": "PMI", "verdict": "PMI 52 → 製造業擴張，貢獻 +1.0 分"}],
            "top_neg": [{"name": "SAHM", "verdict": "SAHM 0.6 → 勞動市場惡化，扣 -0.5 分"}],
        },
    })
    snap, _, _ = _build_macro_ai_snapshot({}, {}, {}, {}, [])
    assert "12 項正貢獻" in snap
    assert "8 項負貢獻" in snap
    assert "PMI 52" in snap
    assert "SAHM 0.6" in snap


def test_calibration_card_explainer_expanders_present():
    """v18.256：兩張校準卡都有 checkbox「📖 怎麼讀這張卡？」（hotfix：原 expander 巢狀 Streamlit 會炸）。"""
    from pathlib import Path
    src = (Path(__file__).parent / "ui" / "tab1_macro.py").read_text(encoding="utf-8")
    # 兩處 checkbox（hotfix v18.256：父層 expander 內禁巢狀 expander → 改 checkbox）
    assert src.count('📖 怎麼讀這張卡？（白話三段式）') == 2
    # 三段式關鍵字
    assert "① 這張卡在算什麼？" in src
    assert "② 三個調整鈕意義" in src or "② 三個關鍵讀數" in src
    assert "③ 結果怎麼解讀？" in src or "③ 看到結果該怎麼用？" in src
    # v18.256：確保兩處不再用 st.expander（會炸） → 改 st.checkbox
    import re
    matches = list(re.finditer(r'(st\.expander|st\.checkbox).*?"📖 怎麼讀這張卡', src))
    assert len(matches) == 2, "應有兩處『📖 怎麼讀這張卡』錨點"
    for m in matches:
        assert "st.checkbox" in m.group(0), \
            f"hotfix v18.256：必須用 st.checkbox 避免巢狀 expander，但找到 {m.group(0)[:60]}"
