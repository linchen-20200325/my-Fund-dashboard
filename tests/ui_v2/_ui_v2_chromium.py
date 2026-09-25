# -*- coding: utf-8 -*-
"""ui_v2 畫面測試共用：找 Chromium、決定找不到時是 skip 還是 fail。

- 有環境變數 `UI_V2_CHROMIUM` → 用它指的執行檔；
  沒有 → 交給 playwright 預設解析（`PLAYWRIGHT_BROWSERS_PATH` 或 `playwright install` 裝的那一份）。
- **CI（環境變數 `CI=true`）找不到 playwright 或瀏覽器 → 失敗，不得 skip**：
  CI slow lane 有裝 chromium（`.github/workflows/pr-check.yml`），在那裡 skip 等於整組畫面測試沒跑卻顯示綠。
- 本機找不到 → skip（本機不一定裝了瀏覽器）。

⚠️ 本檔與測試檔都**不寫死任何瀏覽器路徑**；守衛：`test_ui_v2_lane_guards.py`。
"""

import os
import pathlib

import pytest

ENV_VAR = "UI_V2_CHROMIUM"


def in_ci() -> bool:
    return os.environ.get("CI", "").strip().lower() == "true"


def unavailable(reason: str):
    if in_ci():
        pytest.fail(f"CI 上瀏覽器測試不得 skip：{reason}", pytrace=False)
    pytest.skip(reason)


def import_sync_api():
    try:
        from playwright import sync_api
    except ImportError as exc:  # noqa: BLE001 - 轉成 skip／fail，原因照印
        unavailable(f"匯入不到 playwright：{exc}")
    return sync_api


def launch(playwright):
    path = os.environ.get(ENV_VAR) or None
    if path and not pathlib.Path(path).exists():
        unavailable(f"{ENV_VAR} 指向的路徑不存在：{path}")
    try:
        if path:
            return playwright.chromium.launch(executable_path=path)
        return playwright.chromium.launch()
    except Exception as exc:  # noqa: BLE001 - 轉成 skip／fail，原因照印
        unavailable(f"Chromium 啟動失敗（{ENV_VAR}={path!r}）：{exc}")
