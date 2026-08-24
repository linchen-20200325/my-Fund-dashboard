"""v19.520:App tab_manage 讀選股池必帶 OAuth client(drift-lock)。

bug(user 2026-08-24 回報):管理室「除息行事曆」顯示「選股池與已載入持倉都是空的」,但同頁
「選股池」明明有 10 檔。根因:除息行事曆 / 一鍵補淨值 / 通報預覽 三處呼叫 `list_pool()` **沒帶
OAuth client** → 手機(無 Service Account,只有 Google 登入)雲端環境 `pool_repository` 靜默退回
空的本地 JSON → 讀成空。選股池編輯器有帶 `_pool_oauth_client()` 故讀得到、排程用 SA 也讀得到。

修:三處均改 `list_pool(oauth_client=_pool_oauth_client())`。本測鎖住不再回歸(UI 難做功能單測,
以原始碼 drift-lock 守 —— 任何 list_pool( 呼叫都須帶 oauth_client)。
"""
import re
from pathlib import Path

_SRC = (Path(__file__).resolve().parents[1] / "ui" / "tab_manage.py").read_text(encoding="utf-8")


def test_no_clientless_list_pool_call():
    # 不得出現不帶引數的 list_pool()(手機 OAuth-only 會靜默讀成空)
    assert "list_pool()" not in _SRC


def test_every_list_pool_call_passes_oauth_client():
    calls = [m.start() for m in re.finditer(r"list_pool\(", _SRC)]
    assert calls, "tab_manage 應仍有 list_pool 呼叫(否則本測失去意義)"
    for pos in calls:
        seg = _SRC[pos:pos + 90]
        assert "oauth_client" in seg, f"list_pool 呼叫未帶 oauth_client:…{seg[:70]}…"


def test_pool_oauth_helper_is_imported():
    # 修法依賴選股池編輯器同一個 helper(SA 缺時取登入者 OAuth;拿不到→None 退 SA/本地)
    assert "_pool_oauth_client" in _SRC
