"""v19.517:headless import 防迴歸 —— services.fund_service 可作「第一個 import」不撞循環。

2026-08-24 GitHub Actions 週報實爆:cron 走 process_one_fund → services.fund_row →
`from services.fund_service import ...` 為 process 內 **第一個** import services.fund_service,
它在檔中觸發 `import fund_fetcher`,fund_fetcher 回頭 `from services.fund_service import _RF_ANNUAL`
(及 calc_health_from_manual 等)→ 半初始化 → ImportError → 每檔基金抓取全失敗、週報中止。

修法:把 fund_service 內的 `from fund_fetcher import ...` 下移到**檔尾**(全部被回頭 import 的
symbol 定義完之後)。本測用 subprocess 在**全新直譯器**裡以各種順序 import,確保任一入口都不撞循環
(同 process 內先 import 過會被 prime,故必用子行程)。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]


def _import_in_fresh(pycode: str):
    return subprocess.run([sys.executable, "-c", pycode], cwd=str(_REPO),
                          capture_output=True, text=True)


def test_fund_service_imports_first_no_cycle():
    r = _import_in_fresh("import services.fund_service")
    assert r.returncode == 0, r.stderr[-3000:]
    assert "cannot import name '_RF_ANNUAL'" not in r.stderr
    assert "partially initialized module 'services.fund_service'" not in r.stderr


def test_fund_row_imports_first_no_cycle():
    # cron 真實入口(process_one_fund 在 fund_row)
    r = _import_in_fresh("import services.fund_row")
    assert r.returncode == 0, r.stderr[-3000:]
    assert "cannot import name" not in r.stderr


def test_fund_fetcher_first_still_ok():
    # App / pytest 的既有安全順序不得被破壞
    r = _import_in_fresh("import fund_fetcher; import services.fund_service")
    assert r.returncode == 0, r.stderr[-3000:]


def test_fund_fetcher_reexports_survive():
    # fund_fetcher 對 _RF_ANNUAL / set_risk_free_rate / calc_health_from_manual 的 re-export 仍在
    # (ui/tab1_macro.py 等 module-level `from fund_fetcher import set_risk_free_rate` 依賴之)
    r = _import_in_fresh(
        "from fund_fetcher import _RF_ANNUAL, set_risk_free_rate, calc_health_from_manual;"
        "print('REEXPORT_OK')")
    assert r.returncode == 0, r.stderr[-3000:]
    assert "REEXPORT_OK" in r.stdout


def test_moneydj_fetcher_imports():
    # process_one_fund 先 import 的 moneydj_fetcher(其 fund_service import 為函式內 lazy)
    r = _import_in_fresh("import services.moneydj_fetcher")
    assert r.returncode == 0, r.stderr[-3000:]
