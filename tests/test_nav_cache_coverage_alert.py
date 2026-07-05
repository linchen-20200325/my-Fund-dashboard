"""回歸網 — v19.321:NAV 快取 Action 覆蓋過低時發 GitHub Actions warning。

背景(user #2 深挖):`cache/nav/` 長期只有 TLZF9 一檔,且 source=cache_only —— 代表
每日 Action 其實 fetch 全敗(GitHub 美國 IP 被台灣站點封鎖、PROXY_URL 未生效),
只重存舊快取,卻仍回綠勾。`_emit_coverage_alert` 把這個靜默失敗變成 GitHub Actions
warning annotation(§1 Fail-Loud / §5 可觀測),讓 user 知道要設 PROXY_URL secret。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fetch_nav_cache.py"


def _load_module():
    """scripts 非 package → 用 importlib 從檔案路徑載(不會跑 main:在 __main__ guard 下)。"""
    spec = importlib.util.spec_from_file_location("_fnc_under_test", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_MOD = _load_module()


def test_low_coverage_emits_github_warning(capsys):
    """過半 code 沒抓到新資料 → 回 low=True 且印出 ::warning:: annotation。"""
    summary = [{"code": "TLZF9", "count": 10, "fresh": False}]
    summary += [{"code": f"C{i}", "count": 0, "fresh": False} for i in range(10)]  # 11 檔僅 0 fresh
    r = _MOD._emit_coverage_alert(summary)
    assert r["low"] is True
    assert r["total"] == 11 and r["fresh"] == [] and len(r["no_data"]) == 10
    out = capsys.readouterr().out
    assert "::warning" in out and "PROXY_URL" in out


def test_high_coverage_no_warning(capsys):
    """過半有新資料 → low=False,不發 warning。"""
    summary = [{"code": f"C{i}", "count": 100, "fresh": True} for i in range(10)]
    summary += [{"code": "X", "count": 0, "fresh": False}]  # 10/11 fresh
    r = _MOD._emit_coverage_alert(summary)
    assert r["low"] is False
    out = capsys.readouterr().out
    assert "::warning" not in out


def test_empty_summary_does_not_crash(capsys):
    """空 summary(理論上不會發生)→ 不炸、不誤報。"""
    r = _MOD._emit_coverage_alert([])
    assert r["low"] is False and r["total"] == 0


def test_writes_step_summary_when_env_set(tmp_path, monkeypatch, capsys):
    """GITHUB_STEP_SUMMARY 有設 → 低覆蓋時把診斷寫進 step summary 檔。"""
    step = tmp_path / "step_summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(step))
    summary = [{"code": "TLZF9", "count": 10, "fresh": False},
               {"code": "C1", "count": 0, "fresh": False}]
    _MOD._emit_coverage_alert(summary)
    assert step.exists()
    body = step.read_text(encoding="utf-8")
    assert "NAV 快取覆蓋過低" in body and "C1" in body  # C1 = 完全無快取(count 0)那檔
