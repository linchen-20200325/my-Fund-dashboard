# -*- coding: utf-8 -*-
"""CI deterministic screenshot ＋ 基本 layout 檢查（BL-0525 Batch A；Visual Fidelity 的 automated safety net；slow lane）。

⚠️ **CI fixture screenshot ≠ production-like Cloud screenshot。** 本檔產生的截圖只代表「CI 固定 fixtures 渲染出的畫面」，
不能拿來宣稱 Visual Fidelity Gate 通過；正式確認是 `cloud_capture.py` 從 B 線預覽站取的 production-like 截圖（見 `vf_config.py`）。
截圖檔名、artifact 名、報告第一行都帶這個標示。

做什麼：每個情境起一個 streamlit 子行程（固定 fixtures／替身、不打任何外部網路），用 Chromium 開 desktop（1280x800）與
390px mobile（390x844），各截一張整頁 PNG、量一次 layout（`layout_checks.MEASURE_JS`），把 PNG 與報告寫到 `$VISUAL_FIDELITY_OUT`。

情境：
- 五頁（`mkt`／`hld`／`exp`／`alo`／`set`）：沿用 `tests/ui_v2/test_live_390_page.py` 的正式模式腳本（同一份替身資料），
  只有 hard 檢查（V1～V3：例外、程式碼區塊外露、水平溢出）會轉紅；契約缺口（V4～V8）寫進報告，不轉紅 —— 今天的頁面還沒套用
  Presentation Contract（Batch C～F 的工作）。
- `primitives`：Batch A 新建的共用 presentation primitives 展示頁（`ui_v2/presentation_view.py`）。這一頁完全受本批控制，
  所以 V1～V6 全部 hard（strict）。

決定性：每個畫面截兩次（中間 reload 一次），逐位元組比對，結果寫進報告；**不轉紅**（字型與時間相關元素可能讓兩次不同，
那是需要人看的訊號，不是 bug）。沒有 baseline PNG（repo 零張截圖）；像素 baseline 比對留待有正式 baseline 後再加。

執行：只有環境變數 `VISUAL_FIDELITY_OUT` 有設才跑（`.github/workflows/pr-check.yml` 的 `visual-fidelity-safety-net` job 設定它）；
沒設就 skip —— slow lane 的 `-m slow` 會收到本檔，但不產生截圖。
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import sys

import pytest

pytestmark = pytest.mark.slow

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
_UI_V2_TESTS = _ROOT / "tests" / "ui_v2"
for _p in (str(_HERE), str(_UI_V2_TESTS), str(_ROOT)):
    sys.path.insert(0, _p)

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

import _ui_v2_chromium  # noqa: E402  瀏覽器解析（CI 找不到要 fail）
import vf_config as config  # noqa: E402
import layout_checks as LC  # noqa: E402
from test_live_390_page import _LAMP, _SCRIPTS  # noqa: E402

_OUT = os.environ.get(config.ENV_OUT_DIR, "").strip()

_PRIMITIVES_SCRIPT = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
import streamlit as st
from ui_v2 import presentation as P, presentation_view as V

st.markdown("## Presentation primitives（CI fixture）")
detail = P.detail_model(
    why=["近三個月波動偏低，是因為……（固定測試文字）"],
    source=["固定測試資料；取得時間 2026-10-28"],
    limits=["缺值日不補值"],
    where=["⚙️ 設定與診斷"],
)
chips = [P.chip("資料日 2026-10-28"), P.chip("近三月 -4.2%"), P.chip("◷ 延遲 3 日", "黃"), P.chip("來源 固定測試資料", "灰")]
model = P.chart_card_model("範例圖卡", chips, "近三個月波動偏低", detail=detail)
_data = {{"values": [{{"x": i, "y": 16 + (i % 9) * 0.3}} for i in range(60)]}}
_spec = {{"data": _data, "mark": "line", "encoding": {{"x": {{"field": "x", "type": "quantitative"}}, "y": {{"field": "y", "type": "quantitative"}}}}, "height": 220}}
V.render_chart_card(model, draw_chart=lambda: st.vega_lite_chart(spec=_spec, width="stretch"))
V.render_missing_placeholder(P.missing_model("範例 Missing 卡", "尚未接上正式來源", detail=P.detail_model(where=["資料來源決策待客戶裁示"])))
"""

# 圖表畫好的標誌（vega-lite 非同步渲染；量測前要等到，否則會量到 0 張圖）。
_CHART_READY = "[data-testid=stVegaLiteChart] canvas, [data-testid=stVegaLiteChart] svg, .vega-embed canvas, .vega-embed svg"

# (情境名, 腳本, 等待的選擇器們, strict)
SCENARIOS = [(name, _SCRIPTS[name], (_LAMP[name],), False) for name in ("mkt", "hld", "exp", "alo", "set")]
SCENARIOS.append(("primitives", _PRIMITIVES_SCRIPT, (".pc-card-title", _CHART_READY), True))

_ENTRIES: list = []


@pytest.fixture(scope="module")
def browser():
    if not _OUT:
        pytest.skip(f"{config.ENV_OUT_DIR} 未設定：CI fixture 截圖只在 visual-fidelity-safety-net job 產生")
    api = _ui_v2_chromium.import_sync_api()
    with api.sync_playwright() as p:
        instance = _ui_v2_chromium.launch(p)
        try:
            yield instance
        finally:
            instance.close()


@pytest.fixture(scope="module", autouse=True)
def _write_report():
    yield
    if _OUT and _ENTRIES:
        out = pathlib.Path(_OUT)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{config.CI_FILE_PREFIX}__report.md").write_text(LC.render_report(_ENTRIES), encoding="utf-8")


def _shot(tab) -> bytes:
    return tab.screenshot(full_page=True, animations="disabled")


@pytest.mark.parametrize("name, script, ready_selectors, strict", SCENARIOS, ids=[s[0] for s in SCENARIOS])
def test_CI_fixture_截圖與layout檢查(browser, tmp_path, name, script, ready_selectors, strict):
    out = pathlib.Path(_OUT)
    out.mkdir(parents=True, exist_ok=True)
    app = tmp_path / f"app_vf_{name}.py"
    app.write_text(script, encoding="utf-8")
    failures = []
    with _ui_v2_chromium.streamlit_server(app) as base:
        for vp_name, viewport in config.VIEWPORTS.items():
            ctx = browser.new_context(viewport=viewport, device_scale_factor=1, locale="zh-TW",
                                      timezone_id="Asia/Taipei", color_scheme="light", reduced_motion="reduce")
            tab = ctx.new_page()
            try:
                tab.goto(base + "/", wait_until="networkidle")
                for selector in ready_selectors:
                    tab.wait_for_selector(selector, timeout=60000)
                tab.wait_for_timeout(1500)
                tab.mouse.move(1, 1)
                first = _shot(tab)
                measure = tab.evaluate(LC.MEASURE_JS)
                tab.reload(wait_until="networkidle")
                for selector in ready_selectors:
                    tab.wait_for_selector(selector, timeout=60000)
                tab.wait_for_timeout(1500)
                tab.mouse.move(1, 1)
                second = _shot(tab)
            finally:
                ctx.close()
            fname = f"{config.CI_FILE_PREFIX}__{name}__{vp_name}.png"
            (out / fname).write_bytes(first)
            assert first[:8] == b"\x89PNG\r\n\x1a\n" and len(first) > 1000, fname
            if strict:   # 展示頁必須真的畫出圖表，否則 V4／V5 是空過
                assert measure["charts"], (name, vp_name, "strict 情境量不到任何圖表 —— 等待條件或腳本失效")
            results = LC.evaluate(measure, strict=strict)
            _ENTRIES.append({"scenario": name, "viewport": vp_name, "file": fname, "results": results,
                             "deterministic": hashlib.sha256(first).digest() == hashlib.sha256(second).digest()})
            failures.extend((vp_name, r) for r in LC.hard_failures(results))
    assert not failures, [(vp, r["id"], r["title"], r["detail"]) for vp, r in failures]
