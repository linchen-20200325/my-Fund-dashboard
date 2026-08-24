"""v19.523:infra.html_to_png —— 通用 HTML→PNG 截圖(headless Chromium)。

除息月曆 PNG 推播改「截 App 那張 HTML」(user 2026-08-24)的底層。純截圖 I/O(L0);§1 fail-loud:
playwright / Chromium 缺 → HtmlRenderError(呼叫端退 Flex / 純文字)。真截圖類測試在 Chromium
不可用時 **skip**(CI fast lane 未裝 playwright/chromium → 純函式測試仍跑,不破 CI)。
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infra.html_to_png import (  # noqa: E402
    HtmlRenderError,
    _chromium_candidates,
    html_to_png,
)

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_SAMPLE = ('<!doctype html><html><head><meta charset="utf-8"></head><body>'
           '<div class="wrap" style="width:320px;padding:24px;background:#fff">'
           '<h1>基金 除息 行事曆</h1><p>ABC 123 測試</p></div></body></html>')


def _render_or_skip(html=_SAMPLE, **kw) -> bytes:
    try:
        return html_to_png(html, **kw)
    except HtmlRenderError as e:                       # Chromium/playwright 不可用 → skip 而非 fail
        pytest.skip(f"Chromium/playwright 不可用,跳過真截圖:{e}")


# ── §1 fail-loud(無需瀏覽器,CI 恆跑)────────────────────────────────────
def test_empty_html_raises():
    for bad in ("", "   ", None):
        with pytest.raises(HtmlRenderError):
            html_to_png(bad)


def test_missing_playwright_raises(monkeypatch):
    # 模擬 playwright 未安裝 → import 失敗 → HtmlRenderError(不需真瀏覽器)
    import builtins
    _real = builtins.__import__

    def _fake(name, *a, **k):
        if name.startswith("playwright"):
            raise ImportError("no playwright")
        return _real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", _fake)
    with pytest.raises(HtmlRenderError) as ei:
        html_to_png(_SAMPLE)
    assert "playwright" in str(ei.value)


# ── _chromium_candidates(純函式)──────────────────────────────────────
def test_candidates_env_override_first(monkeypatch):
    monkeypatch.setenv("CHROMIUM_EXECUTABLE_PATH", "/custom/chrome")
    c = _chromium_candidates()
    assert c and c[0] == "/custom/chrome"              # env 覆寫排最前
    assert "/usr/bin/chromium" in c                    # 系統路徑仍在
    assert len(c) == len(set(c))                       # 去重


def test_candidates_no_env_no_empty(monkeypatch):
    monkeypatch.delenv("CHROMIUM_EXECUTABLE_PATH", raising=False)
    c = _chromium_candidates()
    assert "/usr/bin/chromium" in c and all(c)         # 無空字串候選


# ── 真截圖(Chromium 不可用時 skip)──────────────────────────────────────
def test_real_render_valid_png():
    b = _render_or_skip()
    assert b[:8] == _PNG_MAGIC and len(b) > 1000


def test_real_render_full_page_when_no_selector():
    b = _render_or_skip(selector=None)
    assert b[:8] == _PNG_MAGIC


def test_real_render_selector_not_taller_than_full():
    # 只截 .wrap 高度應 ≤ full_page(緊實裁切);兩者皆合法 PNG
    from PIL import Image
    full = _render_or_skip(selector=None)
    el = _render_or_skip(selector=".wrap")
    hf = Image.open(io.BytesIO(full)).size[1]
    he = Image.open(io.BytesIO(el)).size[1]
    assert he <= hf


def test_real_render_missing_selector_falls_back_full_page():
    # selector 找不到 → 退 full_page(不炸、仍出圖)
    b = _render_or_skip(selector=".does-not-exist")
    assert b[:8] == _PNG_MAGIC


# ── §1 反 tofu:缺中文字型時寧可 raise,也不推一張沒人看得懂的圖 ────────────────────
def test_require_cjk_passes_when_font_available():
    # 本機/CI 有中文字型 → require_cjk 不應誤擋(避免探針變成假警報)
    b = _render_or_skip(require_cjk=True)
    assert b[:8] == _PNG_MAGIC


def test_assert_cjk_renderable_raises_when_widths_match():
    # 中文寬度 == 私用區(必為 notdef)寬度 → 判定缺中文字型 → raise(不需真瀏覽器)
    from infra.html_to_png import _assert_cjk_renderable

    class _P:
        def evaluate(self, _js):
            return {"zh": 32.0, "pua": 32.0}           # 兩者相同 = 都在畫 tofu 方塊
    with pytest.raises(HtmlRenderError) as ei:
        _assert_cjk_renderable(_P())
    assert "字型" in str(ei.value)


def test_assert_cjk_renderable_passes_when_widths_differ():
    from infra.html_to_png import _assert_cjk_renderable

    class _P:
        def evaluate(self, _js):
            return {"zh": 64.0, "pua": 32.0}           # 中文有真字形(全形寬)→ 放行
    _assert_cjk_renderable(_P())                        # 不 raise = 通過


def test_assert_cjk_renderable_probe_failure_does_not_block():
    # 探針本身壞掉(evaluate 爆) → 不阻擋出圖(只在「明確測到 tofu」時才 fail)
    from infra.html_to_png import _assert_cjk_renderable

    class _P:
        def evaluate(self, _js):
            raise RuntimeError("probe unavailable")
    _assert_cjk_renderable(_P())                        # 不 raise = 通過
