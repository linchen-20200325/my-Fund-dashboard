"""回歸網 — GitHub Action `fetch_nav_cache.yml` 的精簡 pip install 必須覆蓋
`scripts/fetch_nav_cache.py` 的 import 鏈需求。

2026-07-05 真 bug(user 貼失敗 run):排毒重構後 `fetch_yahoo_finance_history`
於 `scripts/fetch_nav_cache.py:301`
    `from repositories.fund.sources import YF_MORNINGSTAR_CHART_URL`
而該 import 會拉入整個 `repositories/fund` package,其 module-load 時即
`from bs4 import BeautifulSoup`(並用 "lxml" parser)。但 workflow 只裝了
`requests pandas gspread google-auth` → `ModuleNotFoundError: No module named 'bs4'`。

設計脈絡:`shared/api_endpoints.py` docstring 明定此 URL 常數**留在
`repositories/fund/sources.py`(L1 source-local SSOT)、script 從那 import**
(不搬 shared)。因此正解是 workflow 補裝 import 鏈需要的 bs4+lxml,而非改 import 來源。

本檔守兩件事:
1. workflow 的 pip install 清單含 `beautifulsoup4` + `lxml`。
2. 在「CI 沒裝的重依賴(streamlit/feedparser/yfinance/scipy/…)全部擋掉」的乾淨直譯器下,
   script 的關鍵 import 仍能解析 → 若未來 import 鏈長出**新硬依賴**,本測試會紅,
   提醒同步 `fetch_nav_cache.yml` 的 pip install(而非等每日 cron 半夜炸掉才發現)。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_WF = _REPO / ".github" / "workflows" / "fetch_nav_cache.yml"


def _pip_install_line() -> str:
    text = _WF.read_text(encoding="utf-8")
    for line in text.splitlines():
        if "pip install" in line:
            return line
    return ""


def test_workflow_installs_bs4_and_lxml():
    """workflow 必須裝 bs4+lxml(import 鏈的硬依賴)。"""
    line = _pip_install_line()
    assert line, "fetch_nav_cache.yml 找不到 pip install 行"
    assert "beautifulsoup4" in line, (
        "fetch_nav_cache.yml 必須裝 beautifulsoup4 — script 的 Yahoo fallback import "
        "repositories.fund.sources,該 package module-load 即 import bs4"
    )
    assert "lxml" in line, (
        "fetch_nav_cache.yml 必須裝 lxml — repositories.fund.sources 全數用 "
        "BeautifulSoup(html, 'lxml') parser"
    )


def test_critical_import_resolves_under_ci_minimal_deps():
    """擬真 CI:擋掉 CI 不裝的重依賴,script 的關鍵 import 仍須成功。

    若未來有人在 repositories/fund/* 頂層新增 `import scipy` 之類硬依賴,
    此測試會失敗 → 逼迫同步更新 workflow 的 pip install(或把該 import 改 lazy)。
    """
    # CI 的 fetch_nav_cache job 只裝:requests pandas gspread google-auth beautifulsoup4 lxml
    # (+ 這些的傳遞依賴如 numpy)。以下是它「明確沒裝」的重依賴,全擋。
    blocked = "streamlit feedparser yfinance scipy sqlalchemy plotly pandera nest_asyncio"
    code = (
        "import builtins\n"
        "_real = builtins.__import__\n"
        f"_BLOCK = set('{blocked}'.split())\n"
        "def _b(name, *a, **k):\n"
        "    if name.split('.')[0] in _BLOCK:\n"
        "        raise ModuleNotFoundError('simulated-CI blocked: ' + name)\n"
        "    return _real(name, *a, **k)\n"
        "builtins.__import__ = _b\n"
        "from repositories.fund.sources import YF_MORNINGSTAR_CHART_URL\n"
        "assert YF_MORNINGSTAR_CHART_URL.startswith('http'), YF_MORNINGSTAR_CHART_URL\n"
        "print('OK')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(_REPO),
    )
    assert proc.returncode == 0, (
        "fetch_nav_cache 的 import 鏈在 CI 精簡依賴下解析失敗 —— "
        "可能 repositories/fund/* 長出新硬依賴,需同步更新 "
        ".github/workflows/fetch_nav_cache.yml 的 pip install。\nstderr:\n" + proc.stderr
    )
