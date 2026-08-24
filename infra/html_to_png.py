"""infra/html_to_png.py — 通用 HTML → PNG 截圖(無頭 Chromium)。L0 infra(瀏覽器 I/O)。

用途:把「自成一頁的 HTML 字串」用 headless Chromium 截成 PNG bytes,供 LINE 圖片推播等。
**通用、零領域知識**(不 import 任何 L1/L2/L3;HTML 由呼叫端傳入),故置於 L0。

§1 Fail-Loud:playwright 未安裝 / Chromium 無法啟動 / 逾時 / 內容空 → raise `HtmlRenderError`
(不回半張圖、不吞例外)。呼叫端(每月 cron)接到後退回 Flex / 純文字,提醒仍送達。

Chromium 路徑:先讓 playwright **自動解析**(CI/正式機用 `playwright install` 裝、版本相符時成立);
失敗則退**候選 executable path**(部分環境預裝的 Chromium build 與 playwright 版本不符 → 顯式指路;
可用環境變數 `CHROMIUM_EXECUTABLE_PATH` 覆寫)。截圖固定 light 主題(對齊 App 核准樣張、跨機穩定)。
"""
from __future__ import annotations

import glob as _glob
import os as _os

_DEFAULT_WIDTH = 820
_DEFAULT_SCALE = 2
_DEFAULT_TIMEOUT_MS = 20_000
_LAUNCH_ARGS = ["--no-sandbox", "--force-color-profile=srgb", "--hide-scrollbars"]


class HtmlRenderError(RuntimeError):
    """HTML→PNG 截圖失敗(playwright 缺 / Chromium 無法啟動 / 逾時 / 空內容)。訊息不含機敏資料。"""


def _chromium_candidates() -> list:
    """常見預裝 Chromium executable 路徑(env 覆寫 → /opt/pw-browsers → ~/.cache → 系統)。排序穩定、去重。"""
    _out: list = []
    _env = _os.environ.get("CHROMIUM_EXECUTABLE_PATH", "").strip()
    if _env:
        _out.append(_env)
    for _g in ("/opt/pw-browsers/chromium-*/chrome-linux/chrome",
               _os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux/chrome")):
        _out.extend(sorted(_glob.glob(_g)))
    _out.extend(["/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"])
    _seen, _uniq = set(), []
    for _p in _out:
        if _p and _p not in _seen:
            _seen.add(_p)
            _uniq.append(_p)
    return _uniq


def _launch(pw):
    """先試 playwright 自動解析,失敗退候選 executable path;全失敗 → HtmlRenderError(§1)。"""
    try:
        return pw.chromium.launch(headless=True, args=_LAUNCH_ARGS)
    except Exception as _e0:  # noqa: BLE001 — 版本不符/自動路徑缺 → 退顯式候選路徑
        _last = _e0
        for _exe in _chromium_candidates():
            if not _os.path.exists(_exe):
                continue
            try:
                return pw.chromium.launch(headless=True, executable_path=_exe, args=_LAUNCH_ARGS)
            except Exception as _e:  # noqa: BLE001 — 該候選啟不動 → 試下一個
                _last = _e
        raise HtmlRenderError(
            f"Chromium 無法啟動(已試自動解析 + 候選路徑):{type(_last).__name__}: {_last}") from _last


# 中文字形探針:私用區 U+E000/E001 **保證無字形**(必為 notdef 方塊)。若「基金」量到的寬度與私用區
# 相同 → 兩者都在畫 notdef → 該機器沒有中文字型,Chromium 會整張畫成 tofu 方塊(§1 不可當成功)。
_CJK_PROBE_JS = """() => {
  const c = document.createElement('canvas').getContext('2d');
  c.font = '32px sans-serif';
  return {zh: c.measureText('基金').width, pua: c.measureText('').width};
}"""


def _assert_cjk_renderable(page) -> None:
    """在**已載入的頁面**內量測中文字形是否真的畫得出來;畫不出 → raise(§1 不推 tofu 圖)。

    量不到(evaluate 失敗 / 回傳異常)→ **不阻擋**(維持現狀,不因探針本身壞掉而擋掉正常出圖)。
    """
    try:
        _m = page.evaluate(_CJK_PROBE_JS)
        _zh, _pua = float(_m.get("zh") or 0), float(_m.get("pua") or 0)
    except Exception:  # noqa: BLE001 — 探針不可用 → 不擋(僅在「明確測到 tofu」時才 fail)
        return
    if _zh > 0 and _pua > 0 and abs(_zh - _pua) < 0.01:
        raise HtmlRenderError(
            "此機器缺中文字型,Chromium 會把中文畫成 tofu 方塊 —— 拒絕輸出無法閱讀的圖(§1)。"
            "請安裝中文字型(如 `apt-get install -y fonts-noto-cjk`)後重試。")


def html_to_png(html: str, *, width: int = _DEFAULT_WIDTH, scale: int = _DEFAULT_SCALE,
                selector: "str | None" = ".wrap", color_scheme: str = "light",
                timeout_ms: int = _DEFAULT_TIMEOUT_MS, require_cjk: bool = False) -> bytes:
    """HTML 字串 → PNG bytes(headless Chromium 截圖)。純截圖、無外部網路抓取。

    Args:
        width: 視窗寬(px);scale: device_scale_factor(2 = retina 清晰)。
        selector: 只截這個元素(緊實裁切、去除頁邊);找不到或 None → 整頁 full_page。
        color_scheme: 'light'/'dark' — 本專案 HTML 主題感知,截圖釘死 light(可讀、對齊 App 樣張)。
        timeout_ms: 單步逾時(set_content / screenshot)。
        require_cjk: 內容含中文時設 True —— 出圖前先量測中文字形畫不畫得出來,畫不出(runner 缺中文
            字型 → 整張 tofu 方塊)則 raise,**不回一張沒人看得懂的圖**(§1)。
    Returns:
        PNG bytes。
    Raises:
        HtmlRenderError — playwright 缺 / Chromium 無法啟動 / 逾時 / 內容空 / (require_cjk 時)
        缺中文字型會畫成 tofu(§1 不回半圖、不回不可讀的圖)。
    """
    _html = str(html or "")
    if not _html.strip():
        raise HtmlRenderError("空 HTML,拒絕截圖(§1 不產生空白圖)")
    try:
        from playwright.sync_api import sync_playwright
    except Exception as _e:  # noqa: BLE001 — playwright 未安裝
        raise HtmlRenderError(
            "playwright 未安裝(cron 需 `pip install playwright && playwright install chromium`)") from _e

    _png = b""
    try:
        with sync_playwright() as _pw:
            _b = _launch(_pw)
            try:
                _pg = _b.new_page(viewport={"width": int(width), "height": 900},
                                  device_scale_factor=int(scale), color_scheme=color_scheme)
                _pg.set_default_timeout(int(timeout_ms))
                _pg.set_content(_html, wait_until="networkidle")
                # 主題感知 HTML → 釘死 light(截圖跨機一致、對齊 App 核准樣張)
                _pg.evaluate("(cs)=>document.documentElement.setAttribute('data-theme',cs)", color_scheme)
                if require_cjk:                       # 缺中文字型 → 早退 raise,不產 tofu 圖(§1)
                    _assert_cjk_renderable(_pg)
                _el = _pg.query_selector(selector) if selector else None
                _png = _el.screenshot() if _el else _pg.screenshot(full_page=True)
            finally:
                _b.close()
    except HtmlRenderError:
        raise
    except Exception as _e:  # noqa: BLE001 — 截圖過程任何錯 → 統一成 HtmlRenderError(§1)
        raise HtmlRenderError(f"HTML 截圖失敗:{type(_e).__name__}: {_e}") from _e
    if not _png or len(_png) < 100:
        raise HtmlRenderError("截圖輸出異常過小(疑空白 / 未成頁)")
    return _png


__all__ = ["html_to_png", "HtmlRenderError"]
