"""回歸網 — v19.319:_src_cache_files 路徑修正 + fetch_nav 快取 fallback 接線。

修兩件(user 指名 item 6):
1. **路徑 bug**:原 `__file__.parent` 指到 `repositories/fund/cache/nav`(不存在),
   GitHub Actions(`scripts/fetch_nav_cache.py`)實際寫入 repo 根 `cache/nav/`。改 `parents[2]`。
2. **死接線**:`_src_cache_files` 原本只在 sources `__all__` re-export、沒接進 fetch chain
   (原唯一消費者 fetch_nav_history_long 也因危機回測 v19.314 拔除而孤立)。
   改接進 **fetch_nav**(live 路徑)當所有 live URL 失敗(IP 封鎖)時的最終 fallback。
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from fund_fetcher import _src_cache_files, fetch_nav  # 走 root shim 避開循環 import
from repositories.fund import nav_metrics  # monkeypatch requests 用

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CACHE_DIR = _REPO_ROOT / "cache" / "nav"
_TEST_CODE = "ZZTEST9"


@pytest.fixture
def _seed_cache():
    """在 repo 根 cache/nav/ 寫入測試快取,測完刪除(不污染 production 檔)。"""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = _CACHE_DIR / f"{_TEST_CODE}.json"
    payload = {
        "updated_at": "2026-07-05T00:00:00Z",
        "history": [
            {"date": "2026-06-01", "nav": 10.0},
            {"date": "2026-06-02", "nav": 10.5},
            {"date": "2026-06-03", "nav": 10.2},
        ],
    }
    p.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    yield p
    p.unlink(missing_ok=True)


def test_cache_path_points_to_repo_root(_seed_cache):
    """路徑修正:_src_cache_files 必須讀到 repo 根 cache/nav/(非 repositories/fund/…)。"""
    s = _src_cache_files(_TEST_CODE)
    assert not s.empty, "路徑修正後應讀到 repo 根 cache/nav/ 的測試檔(修正前會回空)"
    assert len(s) == 3
    assert abs(float(s.iloc[0]) - 10.0) < 1e-9
    assert s.attrs.get("source", "").startswith("GitHubActions:cache/nav/")


def test_src_cache_files_missing_returns_empty():
    """檔案不存在 → 回空 Series(§1 不炸、不造假)。"""
    s = _src_cache_files("NOSUCHCODE_ZZZ")
    assert isinstance(s, pd.Series) and s.empty


def test_fetch_nav_falls_back_to_cache_when_live_fails(_seed_cache, monkeypatch):
    """live URL 全敗(IP 封鎖模擬)→ fetch_nav 退回 GitHub Actions 快取。"""
    class _FakeResp:
        status_code = 503
        text = ""

    monkeypatch.setattr(nav_metrics.requests, "get", lambda *a, **k: _FakeResp())
    s = fetch_nav(_TEST_CODE)
    assert not s.empty, "live 全敗時應退回 GitHub Actions 快取(接線前會回空)"
    assert len(s) == 3
    assert s.attrs.get("source", "").startswith("GitHubActions:cache/nav/")


def test_fetch_nav_no_cache_still_returns_empty(monkeypatch):
    """live 全敗 + 無快取檔 → 仍回空 Series(不炸、不假資料)。"""
    class _FakeResp:
        status_code = 503
        text = ""

    monkeypatch.setattr(nav_metrics.requests, "get", lambda *a, **k: _FakeResp())
    s = fetch_nav("NOSUCHCODE_ZZZ")
    assert isinstance(s, pd.Series) and s.empty
