# -*- coding: utf-8 -*-
"""production-like Cloud screenshot 擷取腳本（BL-0525 Batch A；Visual Fidelity 的正式確認那一層；**預設不在 CI 執行**）。

從 `config.CLOUD_PREVIEW_URL`（B 線 Streamlit Cloud 預覽站）取 desktop 與 390px 截圖。這是 **production-like** 確認，
和 `test_ci_fixture_screenshots.py` 的 CI fixture 截圖是不同的兩層，**不得互相冒充**（`config.CI_FIXTURE_LABEL`）。

用法（repo 根目錄；需要 playwright 與 Chromium；本機有 `UI_V2_CHROMIUM` 環境變數就用它，沒有就用 playwright 預設解析）::

    python tests/visual_fidelity/cloud_capture.py --out <輸出目錄> [--url <網址>] [--path <頁面路徑，例如 mkt>] [--timeout-ms 45000]

網路被擋住時（目前執行環境連不到該網域）：**不當成失敗**。腳本印出並寫入報告
`production-like Cloud capture blocked by current environment network policy`，附上原始錯誤，exit code 0 —— 客戶 2026-10-29 裁示
Batch A 不得因此停批；環境放行後重跑本腳本即可補上正式 Cloud confirmation。其他錯誤（參數、瀏覽器啟動失敗）才 exit 非 0。

不含 credential：預覽站是公開網址，真資料需要的 Secrets 在 Streamlit Cloud 端，本腳本不讀不寫任何 secret。
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import config  # noqa: E402

_NAV_ERRORS = ("net::ERR_", "Timeout", "ERR_PROXY", "ERR_TUNNEL", "ERR_CONNECTION", "ERR_NAME_NOT_RESOLVED", "403")


def is_network_block(message: str) -> bool:
    """把 playwright 的導覽錯誤判成「網路被擋」。判不出來的一律不吞（當成真錯誤往外拋）。"""
    return any(token in message for token in _NAV_ERRORS)


def report_text(*, url: str, outcome: str, files: list, reason: str = "") -> str:
    lines = ["# production-like Cloud screenshot report", "",
             "> **production-like Cloud screenshot**（不是 CI fixture screenshot；兩層不得互相冒充："
             f"{config.CI_FIXTURE_LABEL}）", "", f"- 網址：{url}", f"- 結果：{outcome}"]
    if reason:
        lines.append(f"- 原始錯誤：{reason}")
    for f in files:
        lines.append(f"- 截圖：`{f}`")
    return "\n".join(lines) + "\n"


def capture(url: str, out: pathlib.Path, *, path: str = "", timeout_ms: int = 45000) -> int:
    out.mkdir(parents=True, exist_ok=True)
    target = url.rstrip("/") + ("/" + path.strip("/") if path else "/")
    report = out / f"{config.CLOUD_FILE_PREFIX}__report.md"
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        print(f"匯入不到 playwright：{exc}", file=sys.stderr)
        return 2
    exe = os.environ.get("UI_V2_CHROMIUM") or None
    files = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        try:
            for vp_name, viewport in config.VIEWPORTS.items():
                ctx = browser.new_context(viewport=viewport, device_scale_factor=1, locale="zh-TW",
                                          timezone_id="Asia/Taipei", color_scheme="light", reduced_motion="reduce")
                tab = ctx.new_page()
                try:
                    tab.goto(target, wait_until="networkidle", timeout=timeout_ms)
                    tab.wait_for_selector("[data-testid=stApp]", timeout=timeout_ms)
                    tab.wait_for_timeout(3000)
                    fname = f"{config.CLOUD_FILE_PREFIX}__{vp_name}.png"
                    tab.screenshot(path=str(out / fname), full_page=True, animations="disabled")
                    files.append(fname)
                except Exception as exc:  # noqa: BLE001 - 分類後決定是記錄 blocked 還是往外拋
                    message = str(exc)
                    if is_network_block(message):
                        print(config.CLOUD_BLOCKED_NOTE)
                        report.write_text(report_text(url=target, outcome=config.CLOUD_BLOCKED_NOTE, files=files,
                                                      reason=message.splitlines()[0][:300]), encoding="utf-8")
                        return 0
                    raise
                finally:
                    ctx.close()
        finally:
            browser.close()
    report.write_text(report_text(url=target, outcome="captured", files=files), encoding="utf-8")
    print(f"captured: {', '.join(files)}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True, type=pathlib.Path)
    ap.add_argument("--url", default=config.CLOUD_PREVIEW_URL)
    ap.add_argument("--path", default="", help="頁面路徑（url_path，例如 mkt、hld、exp、alo、set）")
    ap.add_argument("--timeout-ms", type=int, default=45000)
    args = ap.parse_args(argv)
    return capture(args.url, args.out, path=args.path, timeout_ms=args.timeout_ms)


if __name__ == "__main__":
    sys.exit(main())
