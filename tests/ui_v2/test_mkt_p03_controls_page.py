# -*- coding: utf-8 -*-
"""Phase 3 P0-③ 市場總覽控制項簡化的畫面層測試（slow lane；需要 streamlit，AppTest 真的跑整頁）。

依據：44 第七節第三小節之七其二第 5、7 條與 BL-0228、BL-0289（逐條見 `test_mkt_p03_controls_logic.py` 檔頭）。

正式模式走 `page.render(load_live=..., save_live=...)`：載入函式把 `user_setting` 的替身放在 session 裡
（每次重跑重新經 `live.parse_user_settings` 讀，與正式路徑同一支解析），寫入函式寫進同一個替身並記帳 ——
不打網路、不碰試算表。示範模式走 `ui_v2/app_mkt.py`（照舊，驗「示範模式畫面維持現行」）。
"""

from __future__ import annotations

import pathlib
import sys

import pytest

pytestmark = pytest.mark.slow

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

from ui_v2 import health  # noqa: E402
from ui_v2.mkt import live, logic  # noqa: E402

_APP_DEMO = _ROOT / "ui_v2" / "app_mkt.py"

_SCRIPT_LIVE = """
import sys
sys.path.insert(0, ROOT)
import streamlit as st
from ui_v2.mkt import fixtures, live, page

def _load():
    rows = st.session_state.setdefault("_p03_rows", dict(SEED))
    settings, error = live.parse_user_settings(rows)
    dataset = fixtures.dataset_all_empty() if EMPTY else fixtures.dataset_all_ok()
    return {"dataset": dataset,
            "notes": {"settings": settings, "settings_error": error,
                      "available_keys": ["vol_index", "credit_spread_pct", "policy_rate_pct", "term_spread_pct"],
                      "pending": {}, "masked_keys": [], "cooldowns": []}}

def _save(key, value, kind):
    st.session_state.setdefault("_p03_writes", []).append((key, value, kind))
    rows = st.session_state.setdefault("_p03_rows", dict(SEED))
    rows[key] = {"setting_value": value}
    return {"status": "saved"}

page.render(load_live=_load, save_live=_save)
"""


def _live(*, empty=False, seed=None):
    from streamlit.testing.v1 import AppTest

    script = (_SCRIPT_LIVE.replace("ROOT", repr(str(_ROOT)), 1)
              .replace("EMPTY", repr(bool(empty))).replace("SEED", repr(seed or {})))
    at = AppTest.from_string(script, default_timeout=60)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _demo(scenario="all_ok"):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(_APP_DEMO), default_timeout=60)
    at.query_params["scenario"] = scenario
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _text(at):
    return "\n".join([e.value for e in at.markdown] + [e.value for e in at.caption]
                     + [e.label for e in at.button] + [e.label for e in at.expander])


def _writes(at):
    return list(at.session_state["_p03_writes"]) if "_p03_writes" in at.session_state else []


# ───────────────────────── 第 7 條：正式模式不畫兩種永遠按不了的按鈕 ─────────────────────────


@pytest.mark.parametrize("empty", [False, True])
def test_正式模式_一般畫面沒有套用也沒有重新取數_存檔照舊在(empty):
    at = _live(empty=empty)
    assert not [b for b in at.button if b.label in ("套用", "重新取數")], [b.label for b in at.button]
    assert [b.key for b in at.button if b.label == "存檔"] == ["mkt4_save", "mkt5_save"]


def test_正式模式三塊皆空_燈下改畫前往設定與診斷_資料齊時沒有():
    """單頁入口沒有 `st.navigation`，`render_settings_link` 寫的是那一行說明（`health.SETTINGS_ELSEWHERE_TEXT`）；
    頁首資料狀態行本來就有一則，三塊皆空時燈下再多一則。"""
    def count(at):
        return sum(1 for e in at.caption if e.value == health.SETTINGS_ELSEWHERE_TEXT)

    assert count(_live(empty=False)) == 1
    assert count(_live(empty=True)) == 2


def test_示範模式畫面維持現行_套用與重新取數照舊畫且三塊皆空時重新取數可按():
    at = _demo("all_empty")
    labels = [b.label for b in at.button]
    assert "套用" in labels
    retries = [b for b in at.button if b.label == "重新取數"]
    assert len(retries) == 4 and not any(b.disabled for b in retries)
    assert health.SETTINGS_ELSEWHERE_TEXT not in _text(at)


# ───────────────────────── 第 5 條：多選清單 ─────────────────────────


def test_正式模式_MKT5是一份多選清單_上限6_中文指標名_沒有逐鍵勾選框():
    at = _live()
    (pick,) = [m for m in at.multiselect if m.key == "mkt5_pick"]
    assert pick.max_selections == logic.INDICATOR_PICK_CAP == 6
    assert "波動度指數" in pick.options and "vol_index" not in pick.options
    assert pick.label == live.PICK_LABEL
    assert not [c for c in at.checkbox if str(c.key).startswith("mkt5_")]
    assert pick.value == []                                         # 從未存過：不代填


def test_示範模式_MKT5照舊是逐鍵勾選框():
    at = _demo()
    assert [c for c in at.checkbox if str(c.key).startswith("mkt5_")]
    assert not [m for m in at.multiselect if m.key == "mkt5_pick"]


def test_正式模式_選取存檔_存檔格式不變_重跑後才過濾明細_核心卡不變():
    at = _live()
    cards = [e.value for e in at.markdown if 'class="mkt-card"' in e.value]
    at.multiselect(key="mkt5_pick").set_value(["vol_index", "credit_spread_pct"]).run()
    assert "依指標清單設定不顯示" not in _text(at)                       # 未存：明細照舊
    at.button(key="mkt5_save").click().run()
    assert _writes(at) == [("mkt_indicator_keys", '["credit_spread_pct", "vol_index"]', "list")]
    assert "依指標清單設定不顯示" in _text(at)
    assert [e.value for e in at.markdown if 'class="mkt-card"' in e.value] == cards


def test_正式模式_已存清單回填多選清單():
    at = _live(seed={"mkt_indicator_keys": {"setting_value": '["term_spread_pct", "vol_index"]'}})
    assert at.multiselect(key="mkt5_pick").value == ["term_spread_pct", "vol_index"]   # 依可選清單順序（字面值排序）


def test_正式模式_選滿6項_其餘停用並附一行停用原因():
    at = _live()
    six = ["coincident_index", "credit_spread_pct", "fx_twd_per_usd", "leading_index", "policy_rate_pct",
           "term_spread_pct"]
    at.multiselect(key="mkt5_pick").set_value(six).run()
    assert "已達勾選上限 6，請先取消一項" in [e.value for e in at.caption]
    assert not at.button(key="mkt5_save").disabled


# ───────────────────────── BL-0228 ─────────────────────────


def test_BL0228_從未存過且一個都沒選_存檔停用_什麼都不寫():
    at = _live()
    save = at.button(key="mkt5_save")
    assert save.disabled and save.help == logic.TEXT_SAVE_NOTHING_PICKED
    assert _writes(at) == []


def test_BL0228_已存過再清空_照舊可存成空陣列():
    at = _live(seed={"mkt_indicator_keys": {"setting_value": '["vol_index"]'}})
    at.multiselect(key="mkt5_pick").set_value([]).run()
    save = at.button(key="mkt5_save")
    assert not save.disabled
    save.click().run()
    assert _writes(at) == [("mkt_indicator_keys", "[]", "list")]
    assert logic.TEXT_NOTHING_SELECTED in _text(at)


# ───────────────────────── BL-0289 ─────────────────────────


def test_BL0289_示範模式只套天數_畫面沒有基準日None():
    at = _demo()
    at.number_input(key="mkt4_days").set_value(5).run()
    at.button(key="mkt4_apply").click().run()
    assert not at.exception, [e.value for e in at.exception]
    text = _text(at)
    assert "None" not in text
    assert logic.TEXT_INCOMPLETE_NO_BASELINE in text                 # MKT-4 標題與三張核心卡副標


def test_BL0289_正式模式欄位只填天數_畫面沒有基準日None():
    at = _live()
    at.number_input(key="mkt4_days").set_value(5).run()
    text = _text(at)
    assert "None" not in text and logic.TEXT_SAVE_MISSING_BASELINE in text


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
