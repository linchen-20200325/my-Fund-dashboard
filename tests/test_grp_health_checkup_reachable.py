"""② 持倉體檢 — 「🩺 基金體檢 PK + 4 大健診卡」**可達性**守衛（2026-09-02 T4）。

## 這個檔為什麼存在

`ui/helpers/fund_checkup.render_fund_checkup` 長在
`tab_fund_grp_health._render_health_table` 的 `if funds_extra:` 裡面，而唯一會走到
`if ok_rows:` 的那個呼叫點原本寫死 `funds_extra=None` → **production 路徑恆不觸發**。
畫面文案、程式註解與拍板線框三處都宣稱這個區塊在 ② 頁上，實際上使用者從來沒看過它。

既有守衛 `tests/test_grp_health_checkup_order.py` 全部是**子字串比對**，其中
`assert "_render_health_table(rows, funds_extra=" in src` **正好被 `funds_extra=None`
命中** —— 也就是那道檢查在「功能完全沒渲染」的狀態下是全綠的。子字串看得到「有人寫了
這個參數」，看不到「傳進去的是什麼」。本檔改成**實跑 `_render_health_3tables`、看
`_render_health_table` 真正收到的引數**（行為斷言，不是關鍵字斷言）。

## ⚠️ 給下一個人：守衛是會無聲死掉的

把下面任何一條斷言用 `if False:` / `return` 之類的死分支關掉，pytest 依然報 **PASSED**、
`--collect-only` 的條數也**不會變** —— 也就是「守衛死掉」看起來比「守衛活著」更綠。
**唯一能偵測守衛還活著的方法，就是突變測試**：把修復拿掉（把呼叫點的
`funds_extra=funds_extra` 改回 `funds_extra=None`），本檔必須轉紅。改動本檔時請重跑一次。
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def _no_fx(monkeypatch):
    """`_render_health_3tables` 會無條件呼叫 `fx_regime_by_ccy()`（不在 try 內）。

    測試不打外網 —— 只換掉這一個取數，其餘路徑照真跑。
    """
    import services.fx_regime_service as _fxs
    monkeypatch.setattr(_fxs, "fx_regime_by_ccy", lambda *a, **k: {}, raising=True)


_ROWS = [{
    "code": "AAA111",
    "ok": True,
    "_fund_raw": {},
    "_principal_twd": 1_000_000.0,
    "fx_spot": 30.0,
}]


def _run_and_capture(monkeypatch, *, funds_extra):
    """跑 `_render_health_3tables`，回傳 `_render_health_table` 實際收到的 kwargs。"""
    import ui.tab_fund_grp_health as T

    seen: dict = {}

    def _recorder(rows, funds_extra=None, **kw):   # noqa: ANN001
        seen["called"] = True
        seen["funds_extra"] = funds_extra

    monkeypatch.setattr(T, "_render_health_table", _recorder, raising=True)
    T._render_health_3tables(_ROWS, funds_extra=funds_extra,
                             show_screener=False, source_tab="health")
    return seen


class TestCheckupIsReachable:
    def test_funds_extra_reaches_health_table(self, monkeypatch, _no_fx):
        """② 主路徑必須把 funds_extra **原封**交給 `_render_health_table`。

        突變：呼叫點改回 `funds_extra=None` → 本條轉紅
        （`AssertionError: _render_health_table 收到的 funds_extra 是 None`）。
        """
        sentinel = [{"code": "AAA111", "name": "PROBE", "loaded": True}]
        seen = _run_and_capture(monkeypatch, funds_extra=sentinel)
        assert seen.get("called"), "_render_health_table 根本沒被呼叫 —— 主路徑斷了"
        assert seen["funds_extra"] is not None, (
            "_render_health_table 收到的 funds_extra 是 None —— "
            "🩺 基金體檢 PK / 健診卡整段永遠不會渲染"
        )
        assert seen["funds_extra"] == sentinel, (
            f"funds_extra 被換掉了：{seen['funds_extra']!r}（應原封透傳）"
        )

    def test_render_fund_checkup_actually_invoked(self, monkeypatch, _no_fx):
        """端到端：走完整 ② 主路徑，`render_fund_checkup` 必須真的被叫到一次。

        這一條刻意**不** stub `_render_health_table` —— 它要證明的正是
        「PK 區塊在真實渲染鏈上畫得出來」，而不是「某個參數長得對」。

        突變：呼叫點改回 `funds_extra=None` → 本條轉紅
        （`AssertionError: render_fund_checkup 一次都沒被呼叫`）。
        """
        import ui.helpers.fund_checkup as _chk
        import ui.tab_fund_grp_health as T

        calls: list = []
        monkeypatch.setattr(
            _chk, "render_fund_checkup",
            lambda funds, expanded=False: calls.append((funds, expanded)),
            raising=True,
        )
        sentinel = [{"code": "AAA111", "name": "PROBE", "loaded": True}]
        T._render_health_3tables(_ROWS, funds_extra=sentinel,
                                 show_screener=False, source_tab="health")
        assert calls, "render_fund_checkup 一次都沒被呼叫 —— 🩺 基金體檢 PK 沒有渲染"
        assert calls[0][0] == sentinel, "render_fund_checkup 拿到的不是本次的 funds_extra"
        assert calls[0][1] is True, (
            "上移到健診大表之上後應 expanded=True（v19.190），否則使用者以為沒有這個區塊"
        )
