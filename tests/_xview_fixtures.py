# -*- coding: utf-8 -*-
"""BL-0520 Cross-View 特徵化測試（`tests/test_xview_characterization.py`）的共用替身（不是測試檔）。

描述現況，不代表核准現況語意。本檔只放「造資料」與「換掉網路／streamlit」的工具；
不碰任何 production 行為，不打網路，不讀任何試算表。
"""

from __future__ import annotations

import sys
import types

import pandas as pd

MARKER = "描述現況，不代表核准現況語意"

# 2026-10-27 06:00 UTC：本檔所有 Yahoo 風格序列共用的「取得時間」。
FETCHED = "2026-10-27T06:00:00+00:00"


def yf_series(ticker, dates, values, *, fetched_at=FETCHED, exchange_tz="Etc/UTC", currency=None):
    """`repositories.macro.yf.fetch_yf_close` 出口形狀：DatetimeIndex、float、`attrs` 含 source／fetched_at／exchange_tz。"""
    s = pd.Series(list(values), index=pd.to_datetime(list(dates)), dtype=float, name=ticker)
    s.attrs["source"] = f"Yahoo:{ticker}"
    if fetched_at is not None:
        s.attrs["fetched_at"] = fetched_at
    if exchange_tz is not None:
        s.attrs["exchange_tz"] = exchange_tz
    if currency is not None:
        s.attrs["currency"] = currency
    return s


class FakeChartResponse:
    """`infra.proxy.fetch_url` 的替身回應：只實作 `fetch_yf_close` 用到的 `.json()`（Yahoo chart v8 形狀）。"""

    def __init__(self, dates, values, tz="America/New_York"):
        self._ts = [int(pd.Timestamp(d, tz="UTC").timestamp()) for d in dates]
        self._close = list(values)
        self._tz = tz

    def json(self):
        return {"chart": {"result": [{"timestamp": self._ts,
                                      "indicators": {"quote": [{"close": self._close}]},
                                      "meta": {"exchangeTimezoneName": self._tz}}]}}


# ───────────────────────── 假的 streamlit（只給需要 import ui 模組的特徵化測試用） ─────────────────────────

class _SessionState(dict):
    __getattr__ = dict.get

    def __setattr__(self, key, value):
        self[key] = value


class _Anything:
    """什麼都接得住的物件：可呼叫、可當 context manager、可迭代（空）、可取任意屬性。"""

    def __call__(self, *a, **k):
        return _Anything()

    def __getattr__(self, name):
        return _Anything()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        return iter(())


def _decorator(*a, **k):
    if len(a) == 1 and callable(a[0]) and not k:
        return a[0]
    return _decorator


def make_fake_streamlit(log: list, button_results: list | None = None):
    """回傳假的 `streamlit` 模組。`st.markdown`／`st.caption`／`st.error` 的第一個參數記進 `log`；
    `st.button` 依序吐 `button_results`（用完後一律 False）。"""
    results = list(button_results or [])
    mod = types.ModuleType("streamlit")
    mod.session_state = _SessionState()
    mod.cache_data = _decorator
    mod.cache_resource = _decorator
    mod.fragment = _decorator
    mod.markdown = lambda *a, **k: log.append(("markdown", a[0] if a else ""))
    mod.caption = lambda *a, **k: log.append(("caption", a[0] if a else ""))
    mod.error = lambda *a, **k: log.append(("error", a[0] if a else ""))
    mod.button = lambda *a, **k: (results.pop(0) if results else False)
    mod.container = lambda *a, **k: _Anything()
    mod.spinner = lambda *a, **k: _Anything()
    mod.__getattr__ = lambda name: _Anything()
    return mod


def swap_in_fake_streamlit(log: list, button_results: list | None = None):
    """把 `streamlit` 與所有已載入的 `ui.*` 模組從 `sys.modules` 換掉，回傳 `(fake, restore)`。

    `restore()` 還原：新載入的 `ui.*`／`streamlit` 模組全部丟掉、原本的放回去，不污染同一行程裡的其他測試。
    """
    saved = {n: m for n, m in sys.modules.items() if n == "streamlit" or n.startswith("streamlit.") or n.startswith("ui.") or n == "ui"}
    for n in saved:
        sys.modules.pop(n, None)
    fake = make_fake_streamlit(log, button_results)
    sys.modules["streamlit"] = fake

    def restore():
        for n in [n for n in sys.modules if n == "streamlit" or n.startswith("streamlit.") or n.startswith("ui.") or n == "ui"]:
            sys.modules.pop(n, None)
        sys.modules.update(saved)

    return fake, restore
