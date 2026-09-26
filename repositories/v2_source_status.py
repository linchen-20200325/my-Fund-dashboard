# -*- coding: utf-8 -*-
"""ui_v2 用的來源冷卻狀態唯讀出口（L1；新增檔，不改任何既有檔）。

為什麼要有這一檔：L2 純度守衛（tests/test_services_purity_contract.py）的 import 白名單
不含 `infra.source_backoff`，而 L3（ui_v2）不得碰舊樹；`CLAUDE.md` §8.2 允許 L1 → L0，
所以冷卻狀態由這一層讀出、交給 `services/v2_tables`。

只讀、不改狀態：不呼叫 `reset_*`、`record_*`。
"""

from __future__ import annotations

from infra.source_backoff import get_backoff_state, source_key


def host_of(url: str) -> str:
    """URL → 退避鍵（與 `infra.proxy.fetch_url` 登記冷卻時用的是同一個函式）。"""
    return source_key(url)


def cooling_sources(hosts) -> list:
    """回傳 hosts 之中仍在冷卻的來源，欄位同 `get_backoff_state()`，依剩餘秒數由多到少。"""
    wanted = set(hosts)
    return [dict(s) for s in get_backoff_state() if s["source"] in wanted]
