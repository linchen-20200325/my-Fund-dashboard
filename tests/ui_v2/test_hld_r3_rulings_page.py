# -*- coding: utf-8 -*-
"""持倉體檢：客戶 2026-10-16 裁示第 2、8 點的畫面測試（slow lane；`page.render` 真路徑 ＋ 記錄式替身）。

- 第 2 點：正式模式只有已存設定生效 —— 「套用」停用（原因句）、按了或 session 裡留著套用值，六塊照已存值；
  「存檔」寫進 `user_setting`（替身），下一次載入（替身每次重讀）才以新值計算；寫入失敗原文照印、欄位不清、計算不變。
- 第 8 點：同鍵兩列而語意欄不同 → 正式模式畫既有錯誤畫面，不出現 Traceback。

純函式層見 `test_hld_r3_rulings_logic.py`。
"""

from __future__ import annotations

import copy
import pathlib
import sys
import types
from datetime import date

import pytest

# 整檔標 slow：畫面測試不進 fast lane（守衛：tests/ui_v2/test_ui_v2_lane_guards.py）。
pytestmark = pytest.mark.slow

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

from ui_v2 import plain  # noqa: E402
from ui_v2.hld import fixtures, live, logic, page  # noqa: E402

_PROBE = "_hld_r3_rulings_probe"
_TODAY = date(2026, 9, 28)
_NEW_START = "2026-06-01"
_FAIL_MSG = "HTTP 503 upstream unavailable（已遮蔽）"

_SCRIPT = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
from ui_v2.hld import page
import {_PROBE} as probe

page.render(load_live=probe.load, mask_error=str, save_live=probe.save)
"""


def _scrub(node):
    if isinstance(node, str):
        return node.replace(logic.HINT, "")
    if isinstance(node, dict):
        return {k: _scrub(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_scrub(v) for v in node]
    return node


@pytest.fixture
def probe(monkeypatch):
    """替身試算表：`sheet` 是已存的三鍵；`load` 每次都重讀它（同正式模式 `source.load_live` 每次重跑重讀 `user_setting`）。"""
    module = types.ModuleType(_PROBE)
    module.sheet = {"window": (fixtures.WINDOW_START, fixtures.WINDOW_END),
                    "rules": copy.deepcopy(fixtures._RULES_DEFAULT)}
    module.calls, module.failing, module.mutate = [], set(), None

    def dataset():
        ds = _scrub(copy.deepcopy(fixtures.scenario("full")["dataset"]))
        for holding in ds["holding"]:
            if holding["policy_id"] == "DIRECT":
                holding["policy_id"] = "P-001"
        ds["user_setting"] = fixtures.user_settings(window=module.sheet["window"], rules=module.sheet["rules"])
        if module.mutate:
            module.mutate(ds)
        return ds

    def load():
        ds = dataset()
        return {"dataset": ds, "live_args": {
            "direct_policy_id": "DIRECT", "today": _TODAY,
            "nav_provenance": {r["fund_code"]: {"cache_fallback": False, "stale": None} for r in ds["nav"]}}}

    def save(key, value, kind):
        module.calls.append((key, value, kind))
        if key in module.failing:
            return {"status": "failed", "key": key, "message": _FAIL_MSG}
        if key == "hld_window_start":
            module.sheet["window"] = (value, module.sheet["window"][1])
        elif key == "hld_window_end":
            module.sheet["window"] = (module.sheet["window"][0], value)
        else:
            import json
            module.sheet["rules"] = json.loads(value)
        return {"status": "saved", "key": key, "row": {}}

    module.dataset, module.load, module.save = dataset, load, save
    monkeypatch.setitem(sys.modules, _PROBE, module)
    return module


def _run():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(_SCRIPT, default_timeout=60)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def _button_key(kind):
    hld4 = logic.find_block(logic.build_page_model(**fixtures.scenario("full")), "HLD-4")
    return next(f"hld4_btn_{i}" for i, b in enumerate(hld4["buttons"]) if b["_action_kind"] == kind)


def _block_blob(at, code) -> str:
    """一塊在畫面上的全部文字（同 `test_hld_live_page.py::_block_blob`）。
    Phase 3 P0-①：正式模式卡頭不印塊代號，改讀 `data-block` 屬性；展開區標題以塊名起頭。"""
    for m in at.markdown:
        if f'<span class="hld-card-code">{code}</span>' in m.value or f'data-block="{code}"' in m.value:
            return m.value
    for exp in at.expander:
        if exp.label.startswith(f"{code}　") or exp.label.startswith(f"{plain.BLOCK_NAMES[code]}　—　"):
            return "\n".join([exp.label] + [m.value for m in exp.markdown] + [c.value for c in exp.caption])
    raise AssertionError(f"畫面上找不到 {code}")


def _blobs(at):
    return {code: _block_blob(at, code) for code in logic.APPLY_RECALC_BLOCKS}


def _expected_model(probe, window):
    ds = probe.dataset()
    for row in ds["user_setting"]:
        if row["setting_key"] in ("hld_window_start", "hld_window_end"):
            row["setting_value"] = window[0] if row["setting_key"] == "hld_window_start" else window[1]
    return live.build_live_model(ds, direct_policy_id="DIRECT", today=_TODAY,
                                 nav_provenance={r["fund_code"]: {"cache_fallback": False, "stale": None}
                                                 for r in ds["nav"]})


def test_第2點_正式模式_改欄位按套用_套用停用_六塊照已存值(probe):
    at = _run()
    before = _blobs(at)
    # ~~畫面上那一枚「套用」停用、附 `APPLY_DISABLED_REASON`，按下去不動~~ → BL-0250 批次 3-A U4（`DEC-2026-10-19-05`；
    # 有意識的更正，不是漏刪）：正式模式一般畫面不畫這一枚永遠停用的「套用」，原本停用原因的意思改成一句說明畫在「存檔」下面。
    # 「改欄位、六塊照已存值」照舊驗；模型裡那一枚照舊停用＋原因（`tests/ui_v2/test_bl0250_batch3a_logic.py`）。
    assert not [b for b in at.main.button if b.label == "套用"]
    with pytest.raises(KeyError):
        at.button(key=_button_key("套用"))
    assert live.TEXT_APPLY_NOT_SHOWN in "\n".join(m.value for m in at.main.markdown)
    at.text_input(key="hld4_window_start").input(_NEW_START).run()
    assert not at.exception
    assert _blobs(at) == before
    # 就算 session 裡留著一份套用值（例如預覽站從示範頁帶過來），正式模式也不讀它
    at.session_state["_hld_applied"] = {"window": (_NEW_START, fixtures.WINDOW_END), "rules": []}
    at.run()
    assert _blobs(at) == before
    assert probe.calls == []          # 套用不寫任何東西


def test_第2點_存檔成功_寫出三鍵_下一次載入以已存值計算_欄位不清(probe):
    at = _run()
    before = _blobs(at)
    at.text_input(key="hld4_window_start").input(_NEW_START).run()
    assert _blobs(at) == before                       # 只改欄位：計算不動
    save = at.button(key=_button_key("存檔"))
    assert save.disabled is False
    save.click().run()
    assert not at.exception
    assert [(k, v, kind) for k, v, kind in probe.calls[:2]] == [
        ("hld_window_start", _NEW_START, "date"), ("hld_window_end", fixtures.WINDOW_END, "date")]
    assert [c[0] for c in probe.calls] == list(live.SETTING_KEYS)
    assert probe.sheet["window"] == (_NEW_START, fixtures.WINDOW_END)
    assert at.text_input(key="hld4_window_start").value == _NEW_START
    assert live.TEXT_SAVED in _block_blob(at, "HLD-4")
    # 存檔後這一次重跑就是「下一次載入」：替身重讀已存設定，六塊換成新區間算出來的那一組
    want = _expected_model(probe, (_NEW_START, fixtures.WINDOW_END))
    hld2 = _block_blob(at, "HLD-2")
    assert hld2 != before["HLD-2"]
    for text in (mv["text"] for g in logic.find_block(want, "HLD-2")["fund_groups"] for mv in g["main_values"]):
        assert page._esc(text) in hld2, text


def test_第2點_存檔寫入失敗_原文照印_欄位不清_計算不變_後面的鍵不寫(probe):
    probe.failing = {"hld_window_start"}
    at = _run()
    before = _blobs(at)
    at.text_input(key="hld4_window_start").input(_NEW_START)
    at.button(key=_button_key("存檔")).click().run()
    assert not at.exception
    assert probe.calls == [("hld_window_start", _NEW_START, "date")]
    blob = _block_blob(at, "HLD-4")
    # Phase 3 P0-①：一般畫面是改寫後的那一句（鍵名換中文、上游原文換狀態句），原文移到跨頁的原始訊息。
    raw = f"{live.TEXT_SAVE_FAILED}hld_window_start：{_FAIL_MSG}"
    assert page._esc(plain.plain_text(raw, page="hld", code="HLD-4")) in blob
    assert raw in [e["text"] for e in at.session_state[plain.RAW_STATE]["hld"]["entries"]]
    previous = f"{live.TEXT_SAVE_FAILED}hld_window_end：{live.TEXT_PREVIOUS_FAILED}"
    assert page._esc(plain.plain_text(previous, page="hld", code="HLD-4")) in blob
    assert live.TEXT_PREVIOUS_FAILED in blob                    # 本頁自己的句子照留
    assert at.text_input(key="hld4_window_start").value == _NEW_START
    after = _blobs(at)
    for code in logic.APPLY_RECALC_BLOCKS:
        if code != "HLD-4":
            assert after[code] == before[code], code


def test_第8點_正式模式_同鍵兩列幣別不同_畫既有錯誤畫面_沒有Traceback(probe):
    def split(ds):
        first = ds["holding"][0]
        ds["holding"].append(dict(first, holding_id=first["holding_id"] + "-2", ccy="JPY"))

    probe.mutate = split
    at = _run()
    md = "\n".join(m.value for m in at.markdown)
    assert "Traceback" not in md and not at.code
    # Phase 3 P0-①：一般畫面一句狀態；型別與原文移到跨頁的原始訊息。
    assert page._esc(plain.plain_error_line(logic.fetch_failed_text("ValueError：x"), page="hld")[0]) in md
    raw = "\n".join(e["text"] for e in at.session_state[plain.RAW_STATE]["hld"]["entries"])
    assert logic.fetch_failed_text("ValueError：") in raw
    assert "兩列的 ccy 不同（同鍵不同語意，不加總）" in raw and "兩列的 ccy 不同" not in md
    assert [b.label for b in at.button] == []


def test_存檔結果過期_欄位改得與存檔當下不同_已存檔就不再顯示(probe):
    """總管 2026-10-16 判定（PR #976 稽核後）：存檔後又改了欄位，「已存檔」不得再掛在畫面上；改回存檔當下的值也不再出現（已清掉）。"""
    at = _run()
    at.text_input(key="hld4_window_start").input(_NEW_START)
    at.button(key=_button_key("存檔")).click().run()
    assert live.TEXT_SAVED in _block_blob(at, "HLD-4")
    at.run()                                                  # 欄位沒動：照樣顯示
    assert live.TEXT_SAVED in _block_blob(at, "HLD-4")
    at.text_input(key="hld4_window_start").input("2026-07-01").run()
    assert not at.exception
    assert live.TEXT_SAVED not in _block_blob(at, "HLD-4")
    assert page._SAVE_RESULTS_STATE not in at.session_state
    at.text_input(key="hld4_window_start").input(_NEW_START).run()
    assert live.TEXT_SAVED not in _block_blob(at, "HLD-4")


def test_存檔失敗原文_欄位一改也不再顯示(probe):
    probe.failing = {"hld_window_start"}
    at = _run()
    at.text_input(key="hld4_window_start").input(_NEW_START)
    at.button(key=_button_key("存檔")).click().run()
    assert live.TEXT_SAVE_FAILED in _block_blob(at, "HLD-4")
    at.text_input(key="hld4_window_start").input("2026-07-01").run()
    assert live.TEXT_SAVE_FAILED not in _block_blob(at, "HLD-4")


# ───────── 新 B UI 第一階段唯讀下的休眠寫入路徑（2026-10-26） ─────────
@pytest.fixture(autouse=True)
def _dormant_write_path(monkeypatch):
    """本檔驗的是**休眠中的寫入路徑**（存檔怎麼寫、結果怎麼顯示、或以 L2 存檔佈置測試資料）。第一階段唯讀
    （客戶 2026-10-26 裁示第 7 節；`DEC-2026-10-25-04` J-6、2026-10-26 J-14 補記）下 `is_read_only()` 恆為 True、
    五頁正式模式不畫「存檔」與 `SET-4`；這裡把兩道開關同時打開再驗，**不是**宣稱 production 可寫。
    第一階段的真實行為（不畫、短路、零呼叫）見 `tests/ui_v2/test_readonly_write_surface_guard.py`。"""
    import pathlib as _pathlib
    import sys as _sys

    _sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parent))
    import _dormant_writes

    _dormant_writes.enable(monkeypatch)
