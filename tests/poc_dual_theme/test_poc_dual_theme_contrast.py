# -*- coding: utf-8 -*-
"""雙模式隔離 PoC：瀏覽器實測對比度（標 `slow`）。

配對**不寫死**：由瀏覽器 computed style 導出（每個可見文字節點的 color／fill、各層祖先 background 與 opacity），
再用 `poc_dual_theme_contrast_lib`（本 PoC 自寫 WCAG 計算器，含 alpha 合成）計算。蒐集多個互動狀態：
idle、expander 展開、radio hover、鍵盤 focus、button hover、主選單 popover、側欄（窄螢幕要點原生展開鈕）。

判定：一般文字 ≥ 4.5、大字 ≥ 3；功能性邊界／圖形（radio 圓環與圓點、expander／button 邊框、圖線、座標軸、focus 外框）≥ 3；
卡片與 chip 邊框只報告（裝飾性；內容靠符號＋字樣），但目前也 ≥ 3。
⚠️ 已知例外（原生、不在 PoC 控制範圍）：主選單 popover 的小字（快速鍵提示、版本字）在**兩個模式**都是 4.16:1（<4.5）——記錄為發現，不當作 PoC 通過。
`POC_DUAL_THEME_REPORT_DIR` 有設定時把全部量測寫成 JSON（供 evidence 引用）。
"""
import json
import os
import pathlib
import sys

import pytest

pytestmark = pytest.mark.slow

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

pytest.importorskip("streamlit", reason="本環境匯入不到 streamlit")

import poc_dual_theme_browser_lib as L  # noqa: E402
import poc_dual_theme_contrast_lib as cl  # noqa: E402
import _ui_v2_chromium  # noqa: E402

_POPOVER_STATE = "主選單 popover 開啟"
_POPOVER_FLOOR = 4.0  # 原生 popover 小字實測 4.16；記錄為發現，底線 4.0 防止它更糟


@pytest.fixture(scope="module")
def results():
    api = _ui_v2_chromium.import_sync_api()
    out = {}
    with _ui_v2_chromium.streamlit_server(L.APP) as base, api.sync_playwright() as p:
        browser = _ui_v2_chromium.launch(p)
        try:
            for width in L.WIDTHS:
                for mode in L.MODES:
                    ctx, page = L.open_page(browser, base, width)
                    try:
                        if mode == "dark":
                            L.switch_mode(page, "dark")
                        out[(width, mode)] = L.collect_contrast(page)
                    finally:
                        ctx.close()
        finally:
            browser.close()
    report_dir = os.environ.get("POC_DUAL_THEME_REPORT_DIR")
    if report_dir:
        d = pathlib.Path(report_dir)
        d.mkdir(parents=True, exist_ok=True)
        (d / "poc_dual_theme_contrast.json").write_text(
            json.dumps({f"{w}-{m}": v for (w, m), v in out.items()}, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


@pytest.mark.parametrize("mode", L.MODES)
@pytest.mark.parametrize("width", L.WIDTHS)
def test_all_rendered_text_pairs_meet_wcag_aa(results, width, mode):
    data = results[(width, mode)]
    assert len(data["texts"]) >= 60, "蒐到的文字節點太少（蒐集失效）"
    assert data["sidebar_visible"], "側欄沒有被蒐到"
    states = {t["state"] for t in data["texts"]}
    assert {"idle", "expander 展開", "radio hover", "radio 鍵盤 focus", "button hover", _POPOVER_STATE} <= states, states
    regions = {t["region"] for t in data["texts"]}
    assert {"main", "sidebar", "header"} <= regions, regions
    low = [t for t in data["texts"] if t["state"] != _POPOVER_STATE and t["ratio"] < t["need"]]
    assert not low, "文字對比度不足：\n" + "\n".join(f"  {t['ratio']} < {t['need']} [{t['state']}/{t['region']}] {t['text']!r} fg={t['fg']} bg={t['bg']}" for t in low)


@pytest.mark.parametrize("mode", L.MODES)
@pytest.mark.parametrize("width", L.WIDTHS)
def test_native_popover_small_text_is_a_recorded_finding_not_a_pass(results, width, mode):
    pop = [t for t in results[(width, mode)]["texts"] if t["state"] == _POPOVER_STATE and t["region"] == "other"]
    assert pop, "沒蒐到主選單 popover 文字"
    assert all(t["ratio"] >= _POPOVER_FLOOR for t in pop), [(t["text"], t["ratio"]) for t in pop]
    # 發現：兩模式相同（原生面板不隨 PoC 模式改變）
    assert min(t["ratio"] for t in pop) < 4.5, "若此處已 ≥4.5，請更新 evidence 的發現（原生 popover 已改善）"


@pytest.mark.parametrize("mode", L.MODES)
@pytest.mark.parametrize("width", L.WIDTHS)
def test_all_boundaries_meet_non_text_3_to_1(results, width, mode):
    bs = results[(width, mode)]["boundaries"]
    names = {b["name"] for b in bs}
    must = {"radio 未選圓環", "radio 選取圓點", "expander 邊框", "button 邊框", "圖 甲 線", "圖 乙 虛線", "圖 座標軸", "radio 鍵盤 focus 外框",
            "button 鍵盤 focus 外框", "卡片邊框", "chip 邊框 red", "chip 邊框 yellow"}
    assert must <= names, must - names
    low = [b for b in bs if b["ratio"] < cl.NON_TEXT_MIN]
    assert not low, "非文字邊界／圖形對比度 <3:1：\n" + "\n".join(f"  {b['ratio']} [{b['name']}] {b['fg']} on {b['outer']}" for b in low)


def test_dark_native_chrome_pairs_are_dark_not_light(results):
    """暗色模式下頁首／主區／側欄實際是深底（不是只有一部分變色）。"""
    for width in L.WIDTHS:
        texts = results[(width, "dark")]["texts"]
        for region in ("main", "sidebar", "header"):
            bgs = [t["bg"] for t in texts if t["region"] == region and t["state"] == "idle"]
            assert bgs, (width, region)
            lum = [cl.luminance([int(x) for x in b[4:-1].split(",")]) for b in bgs]
            assert max(lum) < 0.1, (width, region, set(bgs))
        light = results[(width, "light")]["texts"]
        main_bgs = {t["bg"] for t in light if t["region"] == "main" and t["state"] == "idle"}
        assert all(cl.luminance([int(x) for x in b[4:-1].split(",")]) > 0.5 for b in main_bgs), (width, main_bgs)


# ───────────────────────── 負控：計算器對真正的低對比必須報 ─────────────────────────

def test_mutation_injected_low_contrast_text_is_detected():
    api = _ui_v2_chromium.import_sync_api()
    with _ui_v2_chromium.streamlit_server(L.APP) as base, api.sync_playwright() as p:
        browser = _ui_v2_chromium.launch(p)
        try:
            ctx, page = L.open_page(browser, base, 1280)
            base_low = [t for t in L.text_pairs(page) if t["ratio"] < t["need"]]
            page.add_style_tag(content='[data-testid="stMain"] p{color:#bdbdbd !important}')
            page.wait_for_timeout(300)
            after = [t for t in L.text_pairs(page) if t["ratio"] < t["need"]]
            assert len(after) > len(base_low) + 5, "注入淺灰字後，對比度蒐集沒有報出新的低對比"
            ctx.close()
            ctx, page = L.open_page(browser, base, 1280)
            L.switch_mode(page, "dark")
            page.add_style_tag(content='.st-key-poc-card-chart{border-color:#172036 !important}')
            page.wait_for_timeout(300)
            b = L.box_pair(page, ".st-key-poc-card-chart", prop="border")
            assert b["ratio"] < cl.NON_TEXT_MIN, "把卡片邊框改成與底色相同後，邊界對比檢查沒有報"
            ctx.close()
        finally:
            browser.close()
