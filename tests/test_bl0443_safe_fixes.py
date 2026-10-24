"""BL-0443 安全修(2026-10-24 客戶授權)—— 既有原則下的 Missing 誠實呈現/揭露。

鎖住:舊行為錯(Missing 被寫成「確認沒事」/0%/續抱/未填成本)、新行為對(維持 None + 揭露)、
正常路徑不變。不改任何判法、公式、門檻或行動語意。

第 (2) 項 `tag_health_check` 判為 C(Healthy→N/A 會改變 `_verdict_text` 的行動字樣「續抱領息」,
屬 DG-2「N/A／Unset 是否擋行動」),本檔不測、不修。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# ── (1) assess_underperformance:紅燈判不出來 ≠ 確認不是紅燈 ─────────────────────

def test_redlight_none_with_blank_eat_stays_none():
    from services.switch_advisor import assess_underperformance
    r = assess_underperformance(excess_pct=None, eat_status="", redlight=None)
    assert r["redlight"] is None            # 舊:False(用全 None 輸入重算 → Error→False)
    assert r["is_underperforming"] is False  # 判法不變:None 不觸發絕對虧損


def test_redlight_none_still_lets_lag_trigger():
    from services.switch_advisor import assess_underperformance
    r = assess_underperformance(excess_pct=-10.0, eat_status="", redlight=None)
    assert r["is_underperforming"] is True and r["lags_benchmark"] is True
    assert r["redlight"] is None and r["reasons"] == ["跑輸大盤"]


def test_redlight_normal_paths_unchanged():
    from services.switch_advisor import assess_underperformance
    assert assess_underperformance(excess_pct=0.0, redlight=True)["is_underperforming"] is True
    _f = assess_underperformance(excess_pct=0.0, redlight=False)
    assert _f["is_underperforming"] is False and _f["redlight"] is False
    # 有吃本金燈號(非空)仍照舊重算:plain 🔴 吃本金 → 紅燈
    _e = assess_underperformance(excess_pct=None, eat_status="🔴 吃本金", redlight=None)
    assert _e["redlight"] is True and _e["is_underperforming"] is True


def test_script_underperf_red_failure_keeps_none(monkeypatch):
    """週報:紅燈計算炸掉 → log + None,不再被 assess 重算成 False。"""
    import fund_fetcher  # noqa: F401  (prime 既有 latent 互 import,同 test_weekly_switch_notify)
    from scripts import weekly_switch_notify as M
    import services.fund_grp_health.capture as C
    import services.fund_total_return as T
    import services.health.dividend as D

    monkeypatch.setattr(C, "capture_by_code", lambda funds: {})
    monkeypatch.setattr(D, "check_eating_principal_1y_mk", lambda f: {})

    def _boom(f):
        raise RuntimeError("x")
    monkeypatch.setattr(T, "compute_1y_total_return", _boom)
    out = M._underperf_by_code([{"code": "AAA", "currency": "USD"}])
    assert out["AAA"]["redlight"] is None and out["AAA"]["is_underperforming"] is False


def test_script_assemble_rows_excepts_are_logged(monkeypatch, capsys):
    import fund_fetcher  # noqa: F401
    from scripts import weekly_switch_notify as M
    import services.fund_grp_health.unified as U
    import services.fx_regime_service as FXR
    import services.health.dividend as D
    import services.health.report as R

    def _boom(*a, **kw):
        raise ValueError("boom")
    monkeypatch.setattr(U, "build_merged_extra_columns", lambda funds, phase, score: ([], {}))
    monkeypatch.setattr(R, "build_health_analysis_row", _boom)
    monkeypatch.setattr(D, "check_eating_principal_1y_mk", _boom)
    monkeypatch.setattr(FXR, "fx_regime_by_ccy", lambda *a, **kw: {})
    r = M._assemble_rows([{"code": "ZZZ", "name": "z", "series": None, "moneydj_raw": {}}], {})[0]
    err = capsys.readouterr().err
    assert "ZZZ 健診列計算失敗" in err and "ZZZ 吃本金判定失敗" in err   # 舊:靜默
    assert r["吃本金燈號"] == "" and r["基金類別"] is None                 # 退值行為不變


def test_switch_section_discloses_redlight_unknown():
    s = _src("ui/helpers/fund_grp_health/switch_advisor_section.py")
    assert '"⬜ 絕對虧損未判定"' in s and 'u.get("redlight") is None' in s


# ── (3) T7 衛星停利:成本 ≤0 不得變 0% 續抱;缺值原因不得一律寫「未填成本」 ──────────

def test_t7_cost_le_zero_is_none_not_zero():
    s = _src("ui/tab3_t7_ledger.py")
    assert "_pl_pct = (_pl_twd / _cost * 100.0) if _cost > 0 else None" in s
    _code = "\n".join(l.split("#", 1)[0] for l in s.splitlines())   # 去註解(更正註保留舊式)
    assert "if _cost > 0 else 0.0" not in _code
    assert '_pl_pct_str = f"{_pl_pct:+.2f}%" if _pl_pct is not None else "—"' in s


def test_satellite_none_pct_is_no_cost_not_hold():
    from services.satellite import satellite_stop_gain
    assert satellite_stop_gain(None, True)["status"] == "no_cost"      # None → ⬜(不是續抱)
    assert satellite_stop_gain(0.0, True)["status"] == "hold"           # 舊碼 0.0 會走到這裡
    assert satellite_stop_gain(16.0, True)["status"] == "batch"         # 正常路徑不變


def test_t7_missing_reason_labels():
    s = _src("ui/tab3_t7_ledger.py")
    assert 'return f"⬜ {missing_why}"' in s
    assert '_sat_stop_label(_f, None, "無持倉")' in s
    assert '_sat_stop_label(_f, None, "無今日報價")' in s          # 舊:誤標「未填成本」
    assert '_sat_stop_label(_f, None),' not in s


def test_t7_ledger_avg_fx_fallback_is_flagged():
    s = _src("ui/tab3_t7_ledger.py")
    assert 'st.session_state["_t7_fx_ledger_avg"] = {}' in s       # 每輪重設
    assert 'setdefault("_t7_fx_ledger_avg", {})' in s               # 用了就記
    assert 'st.session_state.get("_t7_fx_ledger_avg")' in s         # 面板揭露
    assert "smoke-allow-pass — fallback 靜默" not in s              # 不再靜默吞例外


# ── (4) ladder235:未給燈 ≠ 0% 加碼 ─────────────────────────────────────────

def _wk(values) -> pd.Series:
    idx = pd.date_range("2022-01-07", periods=len(values), freq="W-FRI")
    return pd.Series([float(v) for v in values], index=idx)


def test_ladder_blank_deploy_pct_is_none():
    from services.ladder235 import ladder_signal
    for r in (ladder_signal(_wk([100 + 0.1 * i for i in range(10)]), vix=15, category="科技股票型"),
              ladder_signal(_wk([100] * 30), vix=15, category="科技股票型"),
              ladder_signal(None, vix=15, category="科技股票型"),
              ladder_signal(_wk([100 + 0.1 * i for i in range(60)]), vix=15, category="貨幣市場基金")):
        assert r["lamp"] is None
        assert r["deploy_pct"] is None and r["deploy_pct"] != 0.0   # 舊:0.0(＝巡航比例)


def test_ladder_ok_path_unchanged():
    from services.ladder235 import ladder_signal
    r = ladder_signal(_wk([100 + 0.1 * i for i in range(60)]), vix=15, category="科技股票型")
    assert r["status"] == "ok" and r["lamp"] == "巡航" and r["deploy_pct"] == 0.0


# ── (5) 健診「倉位」欄揭露區間σ fallback ────────────────────────────────────

def test_position_column_discloses_range_fallback():
    s = _src("services/fund_row.py")
    assert "BUY_MODE_RANGE_FALLBACK as _BUY_MODE_FB" in s
    assert '_mk_pos += "（⚠️ 區間σ·資料不足）"' in s
    h = _src("ui/helpers/fund_grp_health/columns.py")
    assert "區間σ·資料不足" in h


# ── (6) Tab2 −2σ 卡揭露布林窗不足 ──────────────────────────────────────────

def test_tab2_minus2sigma_discloses_short_window():
    s = _src("ui/tab2_single_fund.py")
    assert "_bb_win_n = min(20, len(s))" in s
    assert 'f"{_bb_win_note}"' in s
    assert "小量試單（部位 ≤20%）" in s   # 行動文字不變(壓行動屬 DG)


# ── (7) 成長型 caption 不再宣稱「先跑總經分頁」 ──────────────────────────────

def test_switch_caption_no_false_macro_claim():
    s = _src("ui/helpers/fund_grp_health/switch_advisor_section.py")
    assert "'未取得(先跑總經分頁→成長型判斷才啟用)'" not in s
    assert "本頁目前沒有總經 composite 來源" in s


# ── (8) peer_rank 預設標籤 ───────────────────────────────────────────────

def test_peer_default_label_covers_missing_series():
    s = _src("ui/tab_fund_grp_health.py")
    assert '"無同類可比(未分類或無淨值序列)"' in s
    assert '"無同類可比(未分類)")' not in s


def test_peer_labels_skip_classified_without_series():
    """已分類但無序列者確實不在回傳 → 走預設標籤(用字需涵蓋此情形)。"""
    from services.peer_rank import peer_quartile_labels
    rows = [{"ok": True, "code": "A", "_fund_raw": {"category": "科技股票型", "series": None}}]
    assert "A" not in peer_quartile_labels(rows)
