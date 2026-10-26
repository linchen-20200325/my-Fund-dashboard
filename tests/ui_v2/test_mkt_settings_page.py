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

    def multiselect(self, label, options=(), key=None, max_selections=None, disabled=False, help=None, **_kw):
        # Phase 3 P0-③：正式模式 MKT-5 改多選清單。記下選項與上限，供測試驗；沒選過時值為空清單（同 streamlit）。
        self.multiselects = getattr(self, "multiselects", {})
        self.multiselects[key] = (list(options), max_selections, disabled, help)
        return self._widget(key, [])

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
    # 與正式環境同一組旗標：國發會兩鍵、匯率鍵第一階段不取數（N3：不進可勾清單）
    pending = {"leading_index": "ndc_no_release_date", "coincident_index": "ndc_no_release_date",
               "fx_twd_per_usd": "fx_obs_date_rule"}
    rows = [dict(r) for r in fixtures.dataset_all_ok()["rows"] if r["indicator_key"] not in pending]
    monkeypatch.setattr(source.market_indicator, "build_market_indicator_table",
                        lambda **_kw: {"rows": [dict(r) for r in rows],
                                       "errors": {}, "pending": dict(pending), "skipped": {}})
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
    # ~~assert fake.buttons["mkt4_apply"][2] is True  # 正式模式的套用停用~~ → 2026-10-17 Phase 3 P0-③（44 第七節第三小節之七
    # 其二第 7 條；有意識的更正，不是漏刪）：正式模式下永遠停用的「套用」一般畫面不畫。
    assert "mkt4_apply" not in fake.buttons
    fake.click("mkt4_save")                               # callback：只寫 user_setting
    assert [w["setting_key"] for w in sheet.writes] == ["mkt_window_days", "mkt_baseline_date", "mkt_compare_pair"]
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
    sheet.put_complete(5, "2026-09-21")
    sheet.put("mkt_indicator_keys", '["vol_index"]')
    _render(fake)
    assert fake.session_state["mkt4_days"] == 5
    assert fake.session_state["mkt4_baseline"] == date(2026, 9, 21)
    # ~~逐鍵勾選框 mkt5_<鍵> 依已存清單~~ → 2026-10-17 Phase 3 P0-③：多選清單一格（判定不變）。
    assert fake.session_state["mkt5_pick"] == ["vol_index"]


def test_勾選存檔後重跑才過濾明細_核心卡不變(env):
    sheet, fake = env
    first = _render(fake)
    cards_before = [x for x in fake.log if "mkt-card" in str(x)]
    assert "尚未選定任何指標，請在指標清單勾選並存檔" in first          # 從未存過：明細不列（總管裁定）
    fake.session_state["mkt5_pick"] = ["vol_index"]
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
    assert text.count("⬜ 設定不完整：缺觀察窗") == 4          # 三張核心卡 ＋ MKT-4 標題（N2：標題寫已存那一組）
    assert "兩者同向" not in text and "兩者分歧" not in text


# ═══════════════════ 2026-10-13 稽核 G／H 回修 ═══════════════════


def test_H1_已存值存在時_使用者改的欄位與勾選框_重跑後保留使用者的值(env):
    """防「已存值每次重跑都蓋掉 session」：只有 session 裡**沒有**那一格時才以已存值填。"""
    sheet, fake = env
    sheet.put_complete(5, "2026-09-21")
    sheet.put("mkt_indicator_keys", '["vol_index"]')
    _render(fake)
    fake.session_state["mkt4_days"] = 7
    fake.session_state["mkt4_baseline"] = date(2026, 9, 1)
    fake.session_state["mkt5_pick"] = ["credit_spread_pct"]
    text = _render(fake)
    assert fake.session_state["mkt4_days"] == 7
    assert fake.session_state["mkt4_baseline"] == date(2026, 9, 1)
    assert fake.session_state["mkt5_pick"] == ["credit_spread_pct"]
    assert live.TEXT_UNSAVED_WINDOW in text and live.TEXT_UNSAVED_PICKS in text
    # N2：標題仍寫已存那一組
    assert "5 日曆日，基準日 2026-09-21" in text and "7 日曆日" not in text


def test_N4_從未存過_勾選框不預勾_明細寫請勾選並存檔(env):
    _sheet, fake = env
    text = _render(fake)
    # ~~逐鍵勾選框皆 False／不在可勾清單的鍵沒有勾選框~~ → 2026-10-17 Phase 3 P0-③：多選清單一格，判定不變。
    assert fake.session_state["mkt5_pick"] == []                           # 不代填
    options, cap, _disabled, _help = fake.multiselects["mkt5_pick"]
    assert options == ["credit_spread_pct", "policy_rate_pct", "term_spread_pct", "vol_index"]   # N3：母體不變
    assert cap == 6
    assert text.count("尚未選定任何指標，請在指標清單勾選並存檔") >= 3   # MKT-5 摘要、MKT-6、MKT-7
    assert live.TEXT_UNSAVED_PICKS not in text and live.TEXT_UNSAVED_WINDOW not in text   # 剛載入不誤標


def test_B2_混搭的已存設定_頁面寫不一致_不出比較數字(env):
    sheet, fake = env
    sheet.put_complete(5, "2026-09-21")
    sheet.put("mkt_window_days", "6")
    text = _render(fake)
    assert text.count("⬜ 設定不完整：比較條件不一致，請重新存檔") >= 3
    assert "與觀察窗起點的差" not in text


def test_B1_已存天數過大_整頁不當_當成設定讀不到(env):
    sheet, fake = env
    sheet.put_complete(5, "2026-09-21")
    sheet.put("mkt_window_days", "1000000")
    text = _render(fake)                                   # 不得 raise
    assert "設定讀不到" in text and "與觀察窗起點的差" not in text


# ═══════════════════ 2026-10-17 Phase 3 P0-③ 稽核回修 ═══════════════════


def test_P03_BL0228_畫面把從未存過傳進存檔回呼_繞過停用直接叫也不寫(env):
    """稽核必修 (1)：守住 `page.render` → `_on_save_mkt5_live(..., never_saved)` 這條接線。
    從未存過 → 回呼的最後一個參數是 True，就算繞過停用直接叫回呼也一鍵不寫；已存過 → False（清空再存照舊寫 "[]"）。"""
    sheet, fake = env
    _render(fake)
    on_click, args, disabled, _help = fake.buttons["mkt5_save"]
    assert disabled is True and args[-1] is True
    on_click(*args)                                        # 繞過畫面停用：第二道必須擋下
    assert sheet.writes == []

    sheet.put("mkt_indicator_keys", '["vol_index"]')
    fresh = _FakeSt()
    page.st = fresh                                        # 新的工作階段（monkeypatch 結束時還原）
    _render(fresh)
    on_click, args, disabled, _help = fresh.buttons["mkt5_save"]
    assert args[-1] is False
    fresh.session_state["mkt5_pick"] = []
    _render(fresh)
    on_click, args, disabled, _help = fresh.buttons["mkt5_save"]
    assert disabled is False and args[-1] is False
    on_click(*args)
    assert sheet.writes[-1]["setting_value"] == "[]"


def test_P03_session舊值含已不在可選清單的鍵_重跑時濾掉(env):
    """稽核可選 (a)：多選清單只收可選清單內的值；session 殘留的舊鍵在畫之前明確濾掉（不依賴 streamlit 默默丟棄）。"""
    _sheet, fake = env
    _render(fake)
    fake.session_state["mkt5_pick"] = ["vol_index", "leading_index", "已下架的鍵"]   # leading_index：N3 不在可選清單
    _render(fake)
    assert fake.session_state["mkt5_pick"] == ["vol_index"]


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
