# -*- coding: utf-8 -*-
"""production-like Cloud screenshot 擷取腳本（BL-0525 Batch A；Visual Fidelity 的正式確認那一層；**預設不在 CI 執行**）。

從 `config.CLOUD_PREVIEW_URL`（B 線 Streamlit Cloud 預覽站）取 desktop 與 390px 截圖。這是 **production-like** 確認，
和 `test_ci_fixture_screenshots.py` 的 CI fixture 截圖是不同的兩層，**不得互相冒充**（`config.CI_FIXTURE_LABEL`）。

用法（repo 根目錄；需要 playwright 與 Chromium；本機有 `UI_V2_CHROMIUM` 環境變數就用它，沒有就用 playwright 預設解析）::

    python tests/visual_fidelity/cloud_capture.py --out <輸出目錄> [--url <網址>] [--path <頁面路徑，例如 mkt>] [--timeout-ms 45000]

網路被擋住時（目前執行環境連不到該網域；只認 `net::ERR_*` 這類明確的網路層錯誤）：**不當成失敗**。腳本印出並寫入報告
`production-like Cloud capture blocked by current environment network policy`，附上原始錯誤，exit code 0 —— `Timeout`／`403`／休眠頁／非 app 內容**不是** blocked：分別以「無法判定」（exit 3）、「未擷取」（exit 4）呈現，讓人看得到。客戶 2026-10-29 裁示
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

import vf_config as config  # noqa: E402

# 結果狀態與 exit code（只有 blocked 與 captured 以 0 結束；無法判定與非真實 app 要讓人看得到，所以非 0）。
EXIT_OK = 0
EXIT_USAGE = 2
EXIT_UNDETERMINABLE = 3
EXIT_NOT_APP = 4

NOT_DETERMINABLE_NOTE = "無法判定（not determinable）：導覽失敗但不是明確的網路阻擋，不得當成網路政策阻擋"
SLEEPING_NOTE = "未擷取：預覽站顯示休眠頁（app 需要喚醒），不是真實 app 內容"
NOT_APP_NOTE = "未擷取：頁面載入了但找不到 Streamlit app 容器，不是真實 app 內容"

_SLEEP_MARKERS = ("gone to sleep", "get this app back up", "app back up")


def is_network_block(message: str) -> bool:
    """只認明確的網路層阻擋（`net::ERR_*`：tunnel、proxy、name 解析、連線被拒／重置等）。

    `Timeout`、`403`、`wait_for_selector` 逾時、休眠頁都**不是**這一類 —— 它們可能是 app 慢、被擋在別處或站點本身的狀態，
    把它們說成「blocked by current environment network policy」會是假的結論（無法判定就說無法判定）。
    """
    return "net::ERR_" in message


def assess_page(*, has_app_container: bool, body_text: str) -> str:
    """擷取後的最小內容檢查：回 `app`（真實 app）、`sleeping`（休眠頁）、`not_app`（其他）。"""
    if has_app_container:
        return "app"
    lowered = (body_text or "").lower()
    if any(marker in lowered for marker in _SLEEP_MARKERS):
        return "sleeping"
    return "not_app"


def report_text(*, url: str, outcome: str, files: list, reason: str = "") -> str:
    lines = ["# production-like Cloud screenshot report", "",
             "> **production-like Cloud screenshot**（不是 CI fixture screenshot；兩層不得互相冒充："
             f"{config.CI_FIXTURE_LABEL}）", "", f"- 網址：{url}", f"- 結果：{outcome}"]
    if reason:
        lines.append(f"- 原始錯誤：{reason}")
    for f in files:
        lines.append(f"- 截圖：`{f}`")
    return "\n".join(lines) + "\n"


def _find_app(tab, timeout_ms: int) -> bool:
    """Streamlit Community Cloud 把 app 放在 iframe 裡；本機或自架則在主框架。逐框架找 `stApp`，輪詢到逾時。"""
    waited = 0
    while waited <= timeout_ms:
        for frame in tab.frames:
            try:
                if frame.locator("[data-testid=stApp]").count() > 0:
                    return True
            except Exception:  # noqa: BLE001 - 框架正在導覽，下一輪再看
                pass
        tab.wait_for_timeout(1000)
        waited += 1000
    return False


def capture(url: str, out: pathlib.Path, *, path: str = "", timeout_ms: int = 45000) -> int:
    out.mkdir(parents=True, exist_ok=True)
    target = url.rstrip("/") + ("/" + path.strip("/") if path else "/")
    report = out / f"{config.CLOUD_FILE_PREFIX}__report.md"
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        print(f"匯入不到 playwright：{exc}", file=sys.stderr)
        return EXIT_USAGE
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
                    state = assess_page(has_app_container=_find_app(tab, timeout_ms),
                                        body_text=tab.inner_text("body") if tab.locator("body").count() else "")
                    if state != "app":
                        note = SLEEPING_NOTE if state == "sleeping" else NOT_APP_NOTE
                        print(note)
                        report.write_text(report_text(url=target, outcome=note, files=files), encoding="utf-8")
                        return EXIT_NOT_APP
                    tab.wait_for_timeout(3000)
                    fname = f"{config.CLOUD_FILE_PREFIX}__{vp_name}.png"
                    tab.screenshot(path=str(out / fname), full_page=True, animations="disabled")
                    files.append(fname)
                except Exception as exc:  # noqa: BLE001 - 分類後決定是 blocked、無法判定還是往外拋
                    message = str(exc)
                    first = message.splitlines()[0][:300] if message else repr(exc)
                    if is_network_block(message):
                        print(config.CLOUD_BLOCKED_NOTE)
                        report.write_text(report_text(url=target, outcome=config.CLOUD_BLOCKED_NOTE, files=files,
                                                      reason=first), encoding="utf-8")
                        return EXIT_OK
                    if "Timeout" in message or "403" in message:
                        print(NOT_DETERMINABLE_NOTE)
                        report.write_text(report_text(url=target, outcome=NOT_DETERMINABLE_NOTE, files=files,
                                                      reason=first), encoding="utf-8")
                        return EXIT_UNDETERMINABLE
                    raise
                finally:
                    ctx.close()
        finally:
            browser.close()
    report.write_text(report_text(url=target, outcome="captured", files=files), encoding="utf-8")
    print(f"captured: {', '.join(files)}")
    return EXIT_OK


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
