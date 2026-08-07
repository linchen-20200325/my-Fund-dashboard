"""test_tab1_macro.py — ui/tab1_macro.py smoke 測試（v18.127 B-C.5）

驗證 B-C.5 抽出後 Tab1 render 函式：
- module import OK
- render_macro_tab callable + 無位置 arg（與其他 4 個 tab 同設計）
- render_indicator_map private helper 也 callable
- _calc_data_health / _friendly_error alias 正確

A1 cleanup: app.py 的 render_indicator_map shim 已於 v19.291 移除（無外部 caller），
            guard test test_app_py_shim_render_indicator_map_still_works 同步刪除。
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest


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
    """v18.255：sections 清單包含新章節 + 校準健檢 + 既有 5 章節 + 新聞時事。

    2026-08-07：移除 4 個**上游零寫入端**的章節(景氣循環羅盤 / 總經因果鏈 /
    細項燈號回測 / 變數重要性)。它們不是「這次剛好沒資料」而是「永遠不會有資料」,
    列在目錄裡只會讓 AI 每次多產幾段「這項目前沒資料」。判準與漂移鎖見下一條測試。
    """
    import fund_fetcher  # noqa: F401
    from ui.tab1_macro_ai import _build_macro_ai_snapshot
    _, _, sections = _build_macro_ai_snapshot({}, {}, {}, {}, [])
    must_have = ["景氣位階與分數", "校準健檢", "流動性壓力",
                 "23 項加扣分明細", "資本防線", "倒掛翻正歷史回測",
                 "台股熱錢三角交叉", "新聞時事"]
    for sec in must_have:
        assert sec in sections, f"sections 缺 {sec}"


def test_every_declared_section_has_a_real_producer():
    """宣稱的章節數不得高於實際做得出來的章節數(§1 不誇大)。

    做法:掃 `_build_macro_ai_snapshot` 這支函式,取它從 session_state 讀的每個 key,
    再去 `ui/` 全樹找有沒有人寫這個 key。**有讀無寫** = 那一節永遠是空的,
    卻仍列在 sections 目錄裡要 AI 逐節輸出 → 宣稱 N 節、實際做得出來的更少。
    走 AST(讀 `st.session_state.get(...)` 的字面引數 + 找 Subscript 寫入),
    不用 regex,免得掃到說明文字裡的同名字串。

    **範圍**:只管 `_macro_*` 這一族 stash。`_cal_*`(校準健檢)刻意不納入 ——
    那兩張校準卡是 v19.39 PR1C **主動 archive**(UI 降噪)且明文保留 stash 介面契約,
    本檔另有測試餵它們、守它們,屬「登記在案的暫停」而非漏接。若日後那個契約也
    決定不留,再一併收進本測試的範圍。

    **修正前會不會紅**:會 —— 修正前有 4 個 `_macro_*` 讀取端零寫入者。
    """
    import ast
    import pathlib
    _root = pathlib.Path(__file__).parents[1]
    _ai_src = (_root / "ui" / "tab1_macro_ai.py").read_text(encoding="utf-8")

    # (a) 這支函式讀了哪些 `_macro_*` stash
    _read: set[str] = set()
    for _n in ast.walk(ast.parse(_ai_src)):
        if (isinstance(_n, ast.Call)
                and isinstance(_n.func, ast.Attribute) and _n.func.attr == "get"
                and _n.args and isinstance(_n.args[0], ast.Constant)
                and isinstance(_n.args[0].value, str)
                and _n.args[0].value.startswith("_macro_")):
            _read.add(_n.args[0].value)
    assert _read, "抓不到任何 stash 讀取,結構已變請更新本測試"

    # (b) ui/ 全樹誰寫了這些 key(`st.session_state["..."] = ...`)
    _written: set[str] = set()
    for _p in (_root / "ui").rglob("*.py"):
        try:
            _t = ast.parse(_p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for _n in ast.walk(_t):
            _targets = []
            if isinstance(_n, ast.Assign):
                _targets = _n.targets
            elif isinstance(_n, (ast.AugAssign, ast.AnnAssign)):
                _targets = [_n.target]
            for _tg in _targets:
                if (isinstance(_tg, ast.Subscript)
                        and isinstance(_tg.slice, ast.Constant)
                        and isinstance(_tg.slice.value, str)):
                    _written.add(_tg.slice.value)

    _orphan = sorted(_read - _written)
    assert not _orphan, (
        f"AI 摘要讀了沒人寫的 stash(對應章節永遠空):{_orphan}")


def test_snapshot_reads_liquidity_stash(monkeypatch):
    """v18.255：session_state['_macro_liquidity'] 有資料時，snapshot 應出現「流動性壓力」段。"""
    import fund_fetcher  # noqa: F401
    from ui.tab1_macro_ai import _build_macro_ai_snapshot
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
    from ui.tab1_macro_ai import _build_macro_ai_snapshot
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
    from ui.tab1_macro_ai import _build_macro_ai_snapshot
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
    from ui.tab1_macro_ai import _build_macro_ai_snapshot
    _mock_streamlit(monkeypatch, {
        "_macro_hot_money": {
            # R26: 動態日期防 staleness threshold(原寫死 "2026-05-30",
            # 任何 >30 天的相對 today 都會被 hot money snapshot 排除)
            "date": (date.today() - timedelta(days=5)).strftime("%Y-%m-%d"),
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
    from ui.tab1_macro_ai import _build_macro_ai_snapshot
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
    from ui.tab1_macro_ai import _build_macro_ai_snapshot
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


@pytest.mark.skip(reason="v19.39 PR1C: 風險評分校準 + 景氣分數校準 panels archived（UI 移除）；stash keys 仍存供 AI 摘要")
def test_calibration_card_explainer_expanders_present():
    """v18.256：兩張校準卡都有 checkbox「📖 怎麼讀這張卡？」（hotfix：原 expander 巢狀 Streamlit 會炸）。

    v19.39 PR1C：兩張校準卡已 archive（UI 視覺降噪）。stash 介面契約由 _build_macro_ai_snapshot 測試守住。
    """


def test_no_st_stop_in_render_macro_tab():
    """v18.257：render_macro_tab 內禁用 st.stop()。

    第二張校準卡（景氣分數校準）原本用兩個 st.stop() 在沒按抓資料按鈕時提早中斷。
    但 st.stop() 會把整個 Streamlit script 殺掉，導致下方所有 sections
    （流動性壓力 / 景氣循環羅盤 / 23 項加扣分 / 熱錢 / 新聞）全部不 render。
    Hotfix 用 _msc_ready flag 取代 st.stop()。

    這個測試鎖死：tab1_macro.py 不能再出現 st.stop()，防止下次再踩。
    """
    from pathlib import Path
    src = (Path(__file__).parents[1] / "ui" / "tab1_macro.py").read_text(encoding="utf-8")
    import re
    matches = re.findall(r'^\s*st\.stop\(\)', src, flags=re.MULTILINE)
    assert len(matches) == 0, (
        f"render_macro_tab 內仍有 {len(matches)} 處 st.stop()，"
        f"會把下方所有 sections 殺光。請改用 if/else flag 模式。"
    )


@pytest.mark.skip(reason="v19.39 PR1C: 景氣分數校準 panel archived；_msc_ready flag 隨 panel 一併移除")
def test_macro_ready_flag_pattern_used():
    """v18.257：第二張校準卡用 _msc_ready flag（而非 st.stop）控制渲染。

    v19.39 PR1C：panel archived。test_no_st_stop_in_render_macro_tab 仍守住 st.stop 禁令。
    """


def test_enrich_fund_for_decision_div_signal_live_v19400():
    """v19.400 §1/§8:tab1 逐檔決策矩陣的「吃本金」訊號啟用。

    原 line 403 `from fund_fetcher import div_safety_check` 為 broken import
    (fund_fetcher 未 export → ImportError 被 except 吞 → div_info 恆 None,訊號長期 dead)。
    改指 services.portfolio_service 後,鎖死誠實語意:
      - 缺 1Y 含息報酬 → grey「無報酬資料」(非假吃本金 red;decision_matrix 僅 red bump)
      - 真吃本金(0% 含息 < 配息)→ red
      - 覆蓋充分(含息 > 配息)→ green
    若 import 再被改回壞掉 → div_info 恆 None → 本測試三條 assert 全炸,守住不回歸。"""
    from ui.tab1_macro import _enrich_fund_for_decision
    miss = _enrich_fund_for_decision({"code": "X", "metrics": {"annual_div_rate": 5.0}})
    assert miss["dividend_info"] is not None, "import 修好後 div_info 不應恆 None"
    assert miss["dividend_info"].get("alert_level") == "grey"
    eat = _enrich_fund_for_decision({"code": "Y", "metrics": {"ret_1y": 0.0, "annual_div_rate": 5.0}})
    assert eat["dividend_info"].get("alert_level") == "red"
    ok = _enrich_fund_for_decision({"code": "Z", "metrics": {"ret_1y": 8.0, "annual_div_rate": 5.0}})
    assert ok["dividend_info"].get("alert_level") == "green"
