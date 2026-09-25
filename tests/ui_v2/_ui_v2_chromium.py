# -*- coding: utf-8 -*-
"""ui_v2 畫面測試共用：找 Chromium、決定找不到時是 skip 還是 fail。

- 有環境變數 `UI_V2_CHROMIUM` → 用它指的執行檔；
  沒有 → 交給 playwright 預設解析（`PLAYWRIGHT_BROWSERS_PATH` 或 `playwright install` 裝的那一份）。
- **CI（環境變數 `CI=true`）找不到 playwright 或瀏覽器 → 失敗，不得 skip**：
  CI slow lane 有裝 chromium（`.github/workflows/pr-check.yml`），在那裡 skip 等於整組畫面測試沒跑卻顯示綠。
- 本機找不到 → skip（本機不一定裝了瀏覽器）。

- 起 streamlit 子行程：`streamlit_server()`（子行程輸出寫暫存檔，起不來時尾端 50 行進 fail 訊息；
  健康檢查用不帶代理的 opener —— 為什麼見該函式內註解）。

⚠️ 本檔與測試檔都**不寫死任何瀏覽器路徑**；守衛：`test_ui_v2_lane_guards.py`。
"""

import contextlib
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


# ───────────────────────── 起 streamlit 子行程 ─────────────────────────

LOG_TAIL_LINES = 50


def _tail(path, n=LOG_TAIL_LINES):
    try:
        lines = pathlib.Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return f"（讀不到子行程輸出檔 {path}：{exc}）"
    return "\n".join(lines[-n:]) if lines else "（子行程沒有任何輸出）"


@contextlib.contextmanager
def streamlit_server(app, *, timeout_s=60.0, extra_args=()):
    """起 `streamlit run <app>`，等 `/_stcore/health` 回 ok 後 yield base URL；結束時收掉子行程。

    - 子行程 stdout／stderr 寫到暫存檔（不開 PIPE：沒人讀，緩衝塞滿會讓 streamlit 卡住）；
      起不來時把尾端 50 行與 exit code 放進 `pytest.fail` 訊息 —— CI 上看得到原因。
    - 起不來一律 `pytest.fail`（本機與 CI 都是）：瀏覽器已經找到，streamlit 起不來是真的壞。
    """
    import socket
    import subprocess
    import sys
    import tempfile
    import time
    import urllib.request

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    cmd = [
        sys.executable, "-m", "streamlit", "run", str(app),
        "--server.headless", "true",
        "--server.port", str(port),
        "--browser.gatherUsageStats", "false",
        *extra_args,
    ]
    log = tempfile.NamedTemporaryFile(prefix="ui_v2_streamlit_", suffix=".log", delete=False)
    proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    # ⚠️ 健康檢查必須用自己的、不帶代理的 opener，不得用 `urllib.request.urlopen`（2026-09-25 CI 根因）：
    # `urlopen` 第一次被呼叫時會建一個**模組全域**的 opener 並永久快取（`urllib.request._opener`），
    # 其 ProxyHandler 在建立當下就把環境變數的代理抄進去。slow lane 裡 `tests/test_app_apptest.py`
    # 用 monkeypatch 把 HTTP(S)_PROXY 指到 127.0.0.1:9（discard port）並刪掉 NO_PROXY，
    # 同行程內的 AppTest 渲染觸發了第一次 urlopen → 快取的 opener 帶著那個代理活到測試結束；
    # monkeypatch 還原的只有環境變數，還原不了那個 opener。之後這裡再 urlopen 本機，
    # 請求被送去 127.0.0.1:9 → 一律 ConnectionRefused，streamlit 其實一秒內就起來了。
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    ready = False
    try:
        started = time.monotonic()
        deadline = started + timeout_s
        last_error = None
        while not ready and proc.poll() is None and time.monotonic() < deadline:
            try:
                ready = opener.open(base + "/_stcore/health", timeout=2).read() == b"ok"
            except Exception as exc:  # noqa: BLE001 - 還沒起來，記下最後一次原因
                last_error = exc
            if not ready:
                time.sleep(0.5)
        if not ready:
            log.flush()
            pytest.fail(
                "streamlit 沒有起來"
                f"（exit code={proc.poll()}，等了 {time.monotonic() - started:.1f} 秒（上限 {timeout_s:.0f}），最後一次健康檢查錯誤：{last_error!r}）\n"
                f"指令：{' '.join(cmd)}\n"
                f"── 子行程輸出尾端 {LOG_TAIL_LINES} 行（{log.name}）──\n{_tail(log.name)}",
                pytrace=False,
            )
        yield base
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=20)
        log.close()
        if ready:  # 起得來就不留輸出檔；起不來的留著（路徑在 fail 訊息裡）
            pathlib.Path(log.name).unlink(missing_ok=True)
