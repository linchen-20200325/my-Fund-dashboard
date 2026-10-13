# -*- coding: utf-8 -*-
"""市場總覽設定的畫面層測試（slow lane；需要 streamlit 可匯入）。

走 **`page.render(load_live=source.load_live, save_live=source.save_setting)`** 真的那一條路徑：
`page.st` 換成本檔的記錄式替身（模擬 streamlit 的「按鈕 callback 先跑、整頁再重跑」），
`source` 經真的 L2 `settings_store`，只把 L1 設定表換成記憶體替身（同 `test_mkt_settings_logic.py`）。
不用 AppTest：要驗的是「按存檔 → 重跑才生效」與「欄位暫存值不進正式結果」這兩件跨重跑的事，
記錄式替身可以逐步控制每一次重跑之間 session 裡放了什麼。
"""

from __future__ import annotations

import contextlib
import pathlib
import sys
import types
from datetime import date

import pytest

pytestmark = pytest.mark.slow

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

from ui_v2.mkt import fixtures, live, page  # noqa: E402

source = pytest.importorskip("ui_v2.mkt.source")

from test_mkt_settings_logic import _FakeSheet  # noqa: E402

from services.v2_tables import settings_store as S  # noqa: E402


class _FakeSt:
    """page.py 用到的那幾個 streamlit 函式的記錄式替身。"""

    def __init__(self):
        self.session_state = {}
        self.query_params = {}
        self.log = []
        self.buttons = {}

    def rerun_log(self):
        self.log, self.buttons = [], {}

    def markdown(self, body, **_kw):
        self.log.append(body)

    def caption(self, body, **_kw):
        self.log.append(body)

    def button(self, label, key=None, on_click=None, args=(), disabled=False, help=None, **_kw):
        self.buttons[key or label] = (on_click, tuple(args or ()), disabled, help)
        return False

    def click(self, key):
        on_click, args, disabled, _help = self.buttons[key]
        assert not disabled, f"{key} 停用中，按不下去"
        on_click(*args)

    def _widget(self, key, value):
        if key not in self.session_state:
            self.session_state[key] = value
        return self.session_state[key]

    def checkbox(self, label, value=False, key=None, **_kw):
        return self._widget(key, value)

    def number_input(self, label, value=None, key=None, **_kw):
        return self._widget(key, value)

    def date_input(self, label, value=None, key=None, **_kw):
        return self._widget(key, value)

    @contextlib.contextmanager
    def expander(self, label, expanded=False):
        self.log.append(label)
        yield

    def columns(self, n):
        return [contextlib.nullcontext() for _ in range(n)]


@pytest.fixture
def env(monkeypatch):
    sheet = _FakeSheet()
    fake = _FakeSt()
    monkeypatch.setattr(page, "st", fake)
    monkeypatch.setattr(source, "st", types.SimpleNamespace(secrets={}, session_state={}))
    monkeypatch.setattr(S.store, "load_user_settings", sheet.load)
    monkeypatch.setattr(S.store, "save_user_setting", sheet.save)
    monkeypatch.setattr(source.market_indicator, "source_cooldowns", list)
    monkeypatch.setattr(source.market_indicator, "build_market_indicator_table",
                        lambda **_kw: {"rows": [dict(r) for r in fixtures.dataset_all_ok()["rows"]],
                                       "errors": {}, "pending": {}, "skipped": {}})
    return sheet, fake


def _render(fake):
    fake.rerun_log()
    page.render(load_live=source.load_live, save_live=source.save_setting)
    return "\n".join(str(x) for x in fake.log)


def test_按存檔之後重跑才生效_未按存檔的欄位值不進三張核心卡(env):
    sheet, fake = env
    text = _render(fake)
    assert text.count("⬜ 不適用：尚未設定觀察窗") == 3
    fake.session_state["mkt4_days"] = 5
    fake.session_state["mkt4_baseline"] = date(2026, 9, 21)
    text = _render(fake)                                  # 欄位有值、沒按存檔：正式結果不動
    assert text.count("⬜ 不適用：尚未設定觀察窗") == 3
    assert "與觀察窗起點的差" not in text
    assert fake.buttons["mkt4_apply"][2] is True          # 正式模式的套用停用
    fake.click("mkt4_save")                               # callback：只寫 user_setting
    assert [w["setting_key"] for w in sheet.writes] == ["mkt_window_days", "mkt_baseline_date"]
    text = _render(fake)                                  # 重跑 → load_live 重新讀 → 生效
    assert "與觀察窗起點的差" in text and "尚未設定觀察窗" not in text
    assert live.TEXT_SAVED in text


def test_只填一欄_存檔鈕停用_寫明缺哪一欄(env):
    sheet, fake = env
    _render(fake)
    fake.session_state["mkt4_days"] = 5
    text = _render(fake)
    assert fake.buttons["mkt4_save"][2] is True and fake.buttons["mkt4_save"][3] == "缺少：比較基準日"
    assert "缺少：比較基準日" in text and "基準日 None" not in text
    assert sheet.writes == []


def test_新的工作階段以已存值填回欄位與勾選框(env):
    sheet, fake = env
    sheet.put("mkt_window_days", "5")
    sheet.put("mkt_baseline_date", "2026-09-21")
    sheet.put("mkt_indicator_keys", '["vol_index"]')
    _render(fake)
    assert fake.session_state["mkt4_days"] == 5
    assert fake.session_state["mkt4_baseline"] == date(2026, 9, 21)
    assert fake.session_state["mkt5_vol_index"] is True
    assert fake.session_state["mkt5_credit_spread_pct"] is False


def test_勾選存檔後重跑才過濾明細_核心卡不變(env):
    sheet, fake = env
    first = _render(fake)
    cards_before = [x for x in fake.log if "mkt-card" in str(x)]
    fake.session_state["mkt5_vol_index"] = True
    _render(fake)
    assert "依指標清單設定不顯示" not in "\n".join(str(x) for x in fake.log)   # 未存：明細照舊
    fake.click("mkt5_save")
    assert sheet.writes[-1]["setting_value"] == '["vol_index"]'
    after = _render(fake)
    assert "依指標清單設定不顯示" in after
    assert [x for x in fake.log if "mkt-card" in str(x)] == cards_before
    assert first != after


def test_半套已存設定_三張核心卡寫設定不完整(env):
    sheet, fake = env
    sheet.put("mkt_baseline_date", "2026-09-21")
    text = _render(fake)
    assert text.count("⬜ 設定不完整：缺觀察窗") == 3
    assert "兩者同向" not in text and "兩者分歧" not in text
