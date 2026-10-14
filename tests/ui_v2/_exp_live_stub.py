# -*- coding: utf-8 -*-
"""tests/ui_v2/test_exp_live_page.py 用的替身：一份 in-memory 的 `user_setting` ＋ 固定的選股池代碼。

不呼叫 `ui_v2/exp/source.py`、不打任何網路。`load_live`／`save_setting` 的回傳形狀與 source 相同，
解析走真的 `ui_v2/exp/live.py`（所以「存了 → 下一次重跑讀回」走的是正式路徑的同一套解析）。

`WIRED`（2026-10-14 C2 接線）：非空時 `load_live` 改交「基本資料＋淨值已接上」的結果 ——
母體換成 `_exp_wired_fixture.CODES`，L2 形狀的假資料走真的 `live.nav_codes_needed`／`nav_requests`／`assemble_wired`
（與 `source._load_funds` 同一條組裝路徑，只把 L2 呼叫換成假資料）。
"""

from __future__ import annotations

import _exp_wired_fixture as WF

from ui_v2.exp import live

STORE: dict = {}          # 鍵 → setting_value 字串（試算表上的那一份）
FAIL_KEYS: set = set()    # 這些鍵存檔時回失敗
SAVES: list = []          # 每一次存檔呼叫 (鍵, 值, value_kind)
READ_ERROR: list = []     # 非空時 load_live 照「讀設定失敗」交回（第一個元素是訊息原文）
WIRED: list = []          # 非空時交 C2 接線結果（見檔頭）
POOL = {"status": "ok", "backend": "service_account", "codes": ["B02", "A01", "C03"],
        "dropped_blank": 0, "duplicates": 0, "message": None}


def reset() -> None:
    STORE.clear()
    FAIL_KEYS.clear()
    SAVES.clear()
    READ_ERROR.clear()
    WIRED.clear()


def _wired(settings, error) -> dict:
    profiles = WF.profiles()
    needed = live.nav_codes_needed(profiles["rows"], settings, error)
    key_results = [{"input": c, "ok": True, "full_key": c, "portal": "", "parsed_code": c, "error": None}
                   for c in WF.CODES]
    _funds, unresolved = live.nav_requests(needed, key_results, profiles["declared"])
    return live.assemble_wired(profiles, needed, WF.nav_out(codes=needed) if needed else None,
                               unresolved=unresolved, today=WF.TODAY, mask=WF.mask,
                               withheld_texts=WF.WITHHELD_TEXTS, input_conflict=WF.INPUT_CONFLICT)


def load_live() -> dict:
    rows = {key: {"setting_key": key, "setting_value": value} for key, value in STORE.items()}
    settings, error = live.parse_user_settings(rows, [])
    if READ_ERROR:
        settings, error = dict(live.EMPTY_SETTINGS), READ_ERROR[0]
    if WIRED:
        pool = dict(POOL, codes=list(WF.CODES))
        wired = _wired(settings, error)
        return {"dataset": live.build_dataset(pool, settings, wired),
                "notes": {"pool": pool, "settings": settings, "settings_error": error, "cells": wired["cells"]}}
    return {"dataset": live.build_dataset(POOL, settings),
            "notes": {"pool": dict(POOL), "settings": settings, "settings_error": error}}


def save_setting(key, value, kind) -> dict:
    SAVES.append((key, value, kind))
    if key in FAIL_KEYS:
        return {"status": "failed", "key": key, "message": f"{key} 寫入失敗（測試注入）"}
    STORE[key] = value
    return {"status": "saved", "key": key}
