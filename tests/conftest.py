"""tests/conftest.py — pytest 全域前置。

## 唯一職責：prime 匯入順序

`services.fund_service` ↔ `fund_fetcher` 之間存在**既有的 latent 循環 import**
（`fund_fetcher.py:316` 回頭 `from services.fund_service import _RF_ANNUAL`）。

任何測試檔若把 `services.fund_service`（或會連帶拉起它的下游模組）當成該檔的
**第一個** import，就會撞進循環 → pytest **收集階段 ERROR**。

失敗模式特別惡劣：
- 是**整檔收集失敗**，不是單條測試紅 —— 總結只顯示
  `ERROR tests/xxx.py` + `Interrupted: 1 error during collection`；
- 訊息完全不提「循環 import」，很容易被誤判成「新測試寫壞了」而回頭亂改。

## 為什麼要用 conftest 而不是每個檔各自記得

在本檔誕生前，靠的是「每個測試檔自己記得先 import fund_fetcher」：

- `tests/test_nav_history_consume.py:18-21`（有完整註解）
- `tests/test_fund_load_enriched.py`
- `tests/test_nav_history_visibility.py`（2026-08-11 忘了 → 當場 collection ERROR，
  本檔因此誕生）

三個檔案、兩次踩坑。conftest 在**所有測試收集之前**跑一次，往後新增測試檔
不必再知道這件事。

⚠️ 既有那三個檔案裡的 prime import **刻意保留**（重複 import 是 no-op），
讓它們單獨執行（`python -m pytest tests/test_xxx.py`）時也不依賴本檔。

## 前提

`import fund_fetcher` 需要 repo root 在 `sys.path`。本專案三個 pytest 入口
全部走 `python -m pytest`（會把 CWD 放進 `sys.path`）：
- `.pre-commit-config.yaml` 的 `pytest-smoke` hook
- `.github/workflows/pr-check.yml` 的 schema-gate 與 slow lane

若日後改成裸 `pytest` 或搬動工作目錄，這裡會**立刻整批紅**（而不是靜默失效）
—— 那是正確的訊號，代表 import 前提變了，要一起處理。
"""
from __future__ import annotations

# 走自然入口，讓循環在正確的方向上先解開。這一行**不是多餘的 import**，
# 拿掉會讓部分測試檔在收集階段 ERROR（見上方 docstring）。
import fund_fetcher  # noqa: F401


# ════════════════════════════════════════════════════════════
# 第二職責：每條測試前後清空「來源退避」狀態（v3 憲法 §02）
# ════════════════════════════════════════════════════════════
# `infra.source_backoff` 的狀態是 **module-level、跨呼叫存活**的（這正是它的用途：
# 讓下一次 rerun 不要再打同一個剛失敗的來源）。在 pytest 裡這會變成**跨測試污染**：
# `tests/test_proxy_infra.py` 有 30+ 條測試共用同一個假 host `example.com`，
# 只要前一條讓它進了退避，後面每一條都會在 `fetch_url` 進場處被跳過 → 整批假紅。
#
# ⚠️ 這是**測試隔離**，不是把功能關掉：真正驗證退避行為的
# `tests/test_source_backoff.py` 會在自己的測試體內主動製造失敗再斷言，
# 本 fixture 只保證每條測試從乾淨狀態開始（等同 production 的「全域刷新」）。
import pytest as _pytest


@_pytest.fixture(autouse=True)
def _reset_source_backoff():
    from infra import source_backoff as _sb
    _sb.reset_all()
    yield
    _sb.reset_all()
