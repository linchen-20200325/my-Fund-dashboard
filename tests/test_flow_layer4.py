"""Layer 4「行動閉環」稽核修正的回歸鎖(2026-08-15)。

涵蓋:
  E6 nav_history 回填:零確認寫入 → 兩段式(預覽 → 確認)+ 衝突偵測 fail-closed
  E7 `portfolio_funds` 靜默全覆蓋(保單組合分析上傳)→ v19.461 整段移除,改守「覆蓋路徑不得復活」

E8(通報預覽與 NAS 週報 6 項差異)的**治本**需要把 NAS 端三個重製函式抽成
共用 pipeline,而它們依賴的 `build_merged_extra_columns` / `capture_by_code`
目前住在 L3(`ui/helpers/`)—— L2 不能 import(§8.2)。屬 §8.4「需先提案」的
重構範圍,本批未動,現況維持「誠實揭露差異」。
"""
from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent


def _src(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


def _code_lines(text: str) -> str:
    return "\n".join(ln for ln in text.splitlines()
                     if not ln.lstrip().startswith("#"))


# ══════════════════════════════════════════════════════════════════════
# E6 — nav_history 回填不得零確認寫入
# ══════════════════════════════════════════════════════════════════════
def _pts(pairs) -> list:
    return [{"code": "X", "nav": v, "nav_date": d} for d, v in pairs]


def test_conflict_detected_when_navs_disagree(monkeypatch):
    """**改回舊行為必紅** —— 重疊日淨值對不上 = 極可能選錯級別。

    `nav_history` 的去重鍵只有 `(code, date)`。同一檔基金常有多個級別
    (美元累積 / 美元配息 / 歐元避險…),淨值完全不同。選錯級別寫進去之後,
    **正確級別的淨值會被當成重複而永遠寫不進來**,而錯的那份會被健診
    拿去算 1Y 報酬、Sharpe、σ。
    """
    import services.nav_history_gs as G
    from services.fundclear_backfill import analyze_backfill_conflict

    monkeypatch.setattr(G, "load_points", lambda code=None, **kw: [
        {"code": "X", "date": "2026-01-02", "nav": 10.0},
        {"code": "X", "date": "2026-01-03", "nav": 10.1},
    ])
    _r = analyze_backfill_conflict("X", _pts([("2026-01-02", 12.5),
                                              ("2026-01-03", 12.6)]))
    assert _r["verdict"] == "conflict"
    assert _r["n_conflict"] == 2
    assert _r["samples"][0]["date"] == "2026-01-02"
    assert _r["samples"][0]["diff_pct"] > 0


def test_identical_reload_is_duplicate_not_conflict(monkeypatch):
    """同一份資料重抓 = 重複,不是衝突(不該嚇使用者)。"""
    import services.nav_history_gs as G
    from services.fundclear_backfill import analyze_backfill_conflict

    monkeypatch.setattr(G, "load_points", lambda code=None, **kw: [
        {"code": "X", "date": "2026-01-02", "nav": 10.0},
    ])
    _r = analyze_backfill_conflict("X", _pts([("2026-01-02", 10.0)]))
    assert _r["verdict"] == "duplicate" and _r["n_conflict"] == 0


def test_rounding_noise_is_not_a_conflict(monkeypatch):
    """容差是為了抓「差一個級別」(差 5~30%),不是抓四捨五入。"""
    import services.nav_history_gs as G
    from services.fundclear_backfill import analyze_backfill_conflict

    monkeypatch.setattr(G, "load_points", lambda code=None, **kw: [
        {"code": "X", "date": "2026-01-02", "nav": 10.0000},
    ])
    _r = analyze_backfill_conflict("X", _pts([("2026-01-02", 10.0005)]))
    assert _r["verdict"] == "duplicate", "0.005% 的差異不該被判成選錯級別"


def test_no_history_is_clean(monkeypatch):
    """沒有既有資料 → 純新增。"""
    import services.nav_history_gs as G
    from services.fundclear_backfill import analyze_backfill_conflict

    monkeypatch.setattr(G, "load_points", lambda code=None, **kw: [])
    assert analyze_backfill_conflict("X", _pts([("2026-01-02", 10.0)]))["verdict"] == "clean"


def test_unreadable_history_is_unknown_not_clean(monkeypatch):
    """**§1 核心** —— 讀不到既有資料時不可宣稱「安全」。

    回 clean 等於在不知情的狀況下向使用者保證不會撞到 —— 那是編的。
    """
    import services.nav_history_gs as G
    from services.fundclear_backfill import analyze_backfill_conflict

    def _boom(code=None, **kw):
        raise RuntimeError("GS 沒設定")

    monkeypatch.setattr(G, "load_points", _boom)
    _r = analyze_backfill_conflict("X", _pts([("2026-01-02", 10.0)]))
    assert _r["verdict"] == "unknown", "讀不到就說不知道,不可說安全"


def test_conflict_threshold_is_ssot():
    """容差不得寫死在函式裡(§3.3)。"""
    import ast as _ast
    import inspect
    import textwrap

    from services import fundclear_backfill as B

    _tree = _ast.parse(textwrap.dedent(inspect.getsource(B.analyze_backfill_conflict)))
    _imported = {
        _a.name for _n in _ast.walk(_tree) if isinstance(_n, _ast.ImportFrom)
        for _a in _n.names
        if (_n.module or "").startswith("shared.signal_thresholds")
    }
    assert "NAV_BACKFILL_CONFLICT_REL_TOL" in _imported


def test_download_supports_dry_run_and_fails_closed():
    """**改回舊行為必紅** —— 必須有 dry_run,且偵測到衝突時**即使非 dry-run 也不寫**。

    確認鈕的責任是「使用者看過了」,不是「跳過安全檢查」。
    """
    import inspect

    from services.fundclear_backfill import download_and_store

    _sig = inspect.signature(download_and_store)
    assert "dry_run" in _sig.parameters, "沒有 dry-run → 沒辦法先預覽再寫"
    assert _sig.parameters["dry_run"].default is False, "預設必須是「會寫」以外的安全側"

    _code = _code_lines(inspect.getsource(download_and_store))
    assert 'verdict") == "conflict"' in _code, (
        "非 dry-run 路徑沒有擋衝突 —— 確認鈕會變成繞過安全檢查的後門")


# v19.472:FundClear 挑基金補歷史 UI(含 dry-run 預覽/確認兩步)已依 user 2026-08-18 要求
# 從管理室移除(只留手動 CSV 上傳),故原 `test_ui_has_two_step_preview_then_commit`(斷言
# tab_manage 走 dry_run=True / navbf_preview / navbf_commit / _bf_key)隨該 UI 一併退場。
# services/fundclear_backfill 的 dry-run 正確性仍由上方 test_download_supports_dry_run_and_fails_closed
# 守住(該 service 已無 UI 消費者,是否整段退役另行提案,不在本次移除範圍內)。


# ══════════════════════════════════════════════════════════════════════
# E7 — portfolio_funds 不得靜默全覆蓋(v19.461:保單組合分析已整段移除)
# ══════════════════════════════════════════════════════════════════════
def test_policy_csv_overwrite_path_removed():
    """v19.461(user 2026-08-17「只移除保單組合分析、保留持倉」):

    原 E7 守的是「保單組合分析上傳總表 → 覆蓋 `portfolio_funds` 前必須確認」。
    該功能(`_sec_policy_portfolio` + `polcsv_load` 上傳按鈕)已整段拔除 ——
    **根本沒有覆蓋路徑了**(比「有覆蓋但要確認」更安全)。

    這裡把守門意圖從「覆蓋要確認」升級成「危險的靜默全覆蓋 pattern 不得復活」:
    tab_manage 不得再直接指派 `st.session_state["portfolio_funds"] = ...`,
    也不得再有 `polcsv_load` 上傳按鈕。持倉唯一真相仍是政策 Sheet。
    """
    _src_tm = _src("ui/tab_manage.py")
    _blk = _code_lines(_src_tm)
    # 直接覆蓋 portfolio_funds 的危險寫入不得存在(讀取 .get(...) 允許)
    import re as _re
    assert not _re.search(r'portfolio_funds"\]\s*=[^=]', _blk), (
        "tab_manage 又出現直接覆蓋 portfolio_funds 的路徑(E7 治本已拔,不得復活)")
    # 保單組合分析上傳按鈕 / 函式不得復活
    assert "polcsv_load" not in _blk, "保單組合分析上傳按鈕不得復活(user 2026-08-17 移除)"
    assert "def _sec_policy_portfolio" not in _blk, (
        "保單組合分析區塊函式不得復活(user 2026-08-17 移除)")


# ══════════════════════════════════════════════════════════════════════
# E8 — 治本未做，但「不得宣稱同一套邏輯」這件事要守住
# ══════════════════════════════════════════════════════════════════════
def test_notify_preview_does_not_claim_parity_with_nas():
    """預覽與 NAS 週報實測有 6 項差異,文案不得宣稱「同一套邏輯」。

    治本(抽共用 pipeline)需要先把 `build_merged_extra_columns` /
    `capture_by_code` 從 L3 搬到 L2 —— 屬 §8.4 需先提案的重構,本批未動。
    在那之前,至少不能對使用者說謊。
    """
    _blk = _code_lines(_src("ui/tab_manage.py"))
    assert "和 NAS 週報同一套邏輯" not in _blk, (
        "預覽仍宣稱與 NAS 週報同一套邏輯,但實測有 6 項差異")
    assert "可能與 NAS 實際送出的不同" in _blk, "差異揭露不見了"


@pytest.mark.parametrize("name", ["_assemble_rows", "_underperf_by_code"])
def test_nas_duplicates_are_documented_as_such(name):
    """NAS 端的重製函式必須標明「這是重製」——否則下次有人只改一邊。"""
    import inspect

    from scripts import weekly_switch_notify as M

    _doc = (inspect.getdoc(getattr(M, name)) or "")
    assert "重製" in _doc, (
        f"{name} 的 docstring 沒說明它是 L3 helper 的重製版 —— "
        "改一邊不改另一邊會讓預覽與實際送出的內容分歧")
