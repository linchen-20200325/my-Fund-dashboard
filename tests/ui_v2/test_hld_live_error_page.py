# -*- coding: utf-8 -*-
"""持倉體檢正式模式的錯誤畫面（hld S6b-1「防當機」）。slow lane；需要 streamlit。

Streamlit 預設 `showErrorDetails=full`：正式模式原本沒有任何 try，`load_live()` 或
`live.build_live_model(...)` 一拋例外就把 Traceback 印上畫面（含未遮蔽的訊息原文）。
本檔驗：不印 Traceback、不吞錯（畫出錯誤畫面，型別與遮蔽後的訊息原文都在）、假秘密值不上畫面。
"""

import pathlib
import sys

import pytest

pytestmark = pytest.mark.slow

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

# 假秘密值：只在本檔用，遮蔽函式把它換成記號。測試要驗它不出現在畫面上。
_FAKE_SECRET = "zz-fake-secret-7f3a"
_MASK = "‹已遮蔽›"


def _app(kind):
    from ui_v2.hld import fixtures, logic, page

    secret = "zz-fake-secret-7f3a"

    def mask(message):
        return message.replace(secret, "‹已遮蔽›")

    if kind == "load_raises":
        def load():
            raise RuntimeError(f"上游讀取失敗 token={secret} 請求逾時")
    else:
        def scrub(node):
            if isinstance(node, str):
                return node.replace(logic.HINT, "")
            if isinstance(node, dict):
                return {k: scrub(v) for k, v in node.items()}
            if isinstance(node, list):
                return [scrub(v) for v in node]
            return node

        dataset = scrub(fixtures.scenario("full")["dataset"])
        for holding in dataset["holding"]:
            if holding["policy_id"] == "DIRECT":
                holding["policy_id"] = "P-001"
        # 壞資料：`fund_errors` 點名持倉裡沒有的代碼 ⇒ `logic.fund_errors` raise ValueError，
        # 訊息裡會原樣帶出那個代碼 —— 把假秘密值塞在代碼裡，驗它經遮蔽才上畫面。
        dataset["fund_errors"] = {"nav": {secret: "x"}}
        live_args = {
            "direct_policy_id": "DIRECT",
            "nav_provenance": {
                row["fund_code"]: {"cache_fallback": False, "stale": None} for row in dataset["nav"]
            },
        }

        def load():
            return {"dataset": dataset, "live_args": live_args}

    page.render(load_live=load, mask_error=mask)


def _run(kind):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_app, args=(kind,), default_timeout=60)
    at.run()
    return at


def _texts(at) -> str:
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption]
    parts += [e.value for e in at.error] + [str(x.value) for x in at.exception]
    parts += [b.label for b in at.button] + [str(b.help) for b in at.button]
    return "\n".join(parts)


@pytest.mark.parametrize("kind, type_name", [
    ("load_raises", "RuntimeError"),
    ("build_raises", "ValueError"),
])
def test_S6b1_正式模式拋例外_畫錯誤畫面_不印Traceback_訊息經遮蔽(kind, type_name):
    from ui_v2.hld import live, logic

    at = _run(kind)
    # 不印 Traceback：沒有 st.exception 元素、任何文字裡都沒有 "Traceback"。
    assert len(at.exception) == 0, [x.value for x in at.exception]
    blob = _texts(at)
    assert "Traceback" not in blob
    # 不吞錯：錯誤畫面在，型別與遮蔽後的訊息原文都在。
    md = [m.value for m in at.markdown]
    errs = [v for v in md if logic.fetch_failed_text(type_name + "：") in v]
    assert len(errs) == 1, md
    assert _MASK in errs[0]
    assert any(logic.PRINT_AS_IS_LINE in v for v in md)
    assert f'<div class="hld-title">{logic.PAGE_TITLE}</div>' in md
    # 假秘密值不得出現在畫面任何地方。
    assert _FAKE_SECRET not in blob
    # 「重新取數」照 `44` 5.5 掛上、正式版停用、原因逐字（裁示 A）。
    assert [b.label for b in at.button] == ["重新取數"]
    assert at.button[0].disabled
    assert at.button[0].help == live.REFETCH_DISABLED_REASON
    # 整頁其餘塊不畫（例外之後沒有任何一塊被畫出半截）。
    assert not any('class="hld-layer-label' in v for v in md)


def test_S6b1_訊息原文其餘字元逐字保留():
    at = _run("load_raises")
    md = "\n".join(m.value for m in at.markdown)
    assert "上游讀取失敗 token=‹已遮蔽› 請求逾時" in md


def test_S6b1_mask_error與load_live要一起傳():
    from ui_v2.hld import page

    with pytest.raises(ValueError, match="要一起傳"):
        page.render(load_live=lambda: {}, mask_error=None)
    with pytest.raises(ValueError, match="要一起傳"):
        page.render(mask_error=str)
