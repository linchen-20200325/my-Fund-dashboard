"""tests/test_accumulate_nav_tw.py — v19.363 ③:台灣端每日累積(NAS cron)。

守:
- accumulate_once:正常抓 → 取 series 末點、source=nas_cron、批次寫入 summary 正確
- 單檔抓失敗(raise / 空 fd)→ 顯式 skip 不拖累整批(§4.6)
- 同日重跑 → append 端 (code,date) 去重(§5 冪等,summary dup 計數)
- L2 env JSON 字串 SA:status() 在 NAS env(SA 為字串)下 enabled=True(v19.363 修)
- _sa_to_dict:dict 原樣 / JSON 字串 → dict / 壞字串 → {}
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

from services import nav_history_gs as GS

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "accumulate_nav_tw.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("_acc_under_test", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_MOD = _load_script()


def _fd(code: str, navs: list, dates: list) -> dict:
    idx = pd.to_datetime(dates)
    return {"full_key": code, "fund_name": f"{code} 基金",
            "series": pd.Series(navs, index=idx, dtype=float)}


# ── accumulate_once 核心 ──────────────────────────────────────
def test_accumulate_happy_path_tags_nas_cron():
    captured = {}

    def _fetch(code):
        return _fd(code, [10.0, 10.5], ["2026-07-21", "2026-07-22"])

    def _append(points):
        captured["points"] = points
        return {"written": len(points), "skipped": 0}

    s = _MOD.accumulate_once(["TLZF9", "ANZ89"], fetch_fn=_fetch, append_fn=_append)
    assert s["total"] == 2 and s["fetched"] == 2 and s["written"] == 2
    assert all(p["source"] == "nas_cron" for p in captured["points"])
    assert captured["points"][0]["nav"] == 10.5                    # series 末點 SSOT
    assert captured["points"][0]["nav_date"] == "2026-07-22"


def test_accumulate_single_failure_does_not_abort_batch():
    def _fetch(code):
        if code == "BAD1":
            raise RuntimeError("timeout")
        if code == "BAD2":
            return {}                                              # 空 fd → 無有效點
        return _fd(code, [9.9], ["2026-07-22"])

    s = _MOD.accumulate_once(["BAD1", "TLZF9", "BAD2"],
                             fetch_fn=_fetch,
                             append_fn=lambda pts: {"written": len(pts), "skipped": 0})
    assert s["fetched"] == 1 and s["written"] == 1
    assert set(s["skipped_fetch"]) == {"BAD1", "BAD2"}             # 顯式計數,不靜默


def test_accumulate_idempotent_dup_counted():
    """append 端已有同 (code,date) → written 0、dup 計數(§5 重跑不灌水)。"""
    s = _MOD.accumulate_once(
        ["TLZF9"],
        fetch_fn=lambda c: _fd(c, [10.0], ["2026-07-22"]),
        append_fn=lambda pts: {"written": 0, "skipped": len(pts)},  # 模擬全撞日
    )
    assert s["fetched"] == 1 and s["written"] == 0 and s["skipped_dup"] == 1


def test_accumulate_empty_codes():
    s = _MOD.accumulate_once([], fetch_fn=lambda c: {}, append_fn=lambda p: {})
    assert s["total"] == 0 and s["fetched"] == 0 and s["written"] == 0


# ── v19.363 L2:env JSON 字串 SA(NAS 環境)──────────────────
def test_sa_to_dict_variants():
    sa = {"client_email": "sa@x.iam"}
    assert GS._sa_to_dict(sa) is sa                                # dict 原樣
    assert GS._sa_to_dict(json.dumps(sa)) == sa                    # JSON 字串 → dict
    assert GS._sa_to_dict("not json") == {}                        # 壞字串 → 缺
    assert GS._sa_to_dict(None) == {}
    assert GS._sa_to_dict(123) == {}


def test_status_enabled_with_env_string_sa(monkeypatch):
    """NAS env fallback:SA 為 JSON 字串 → status()/is_enabled 都應視為啟用。"""
    import infra.config as _cfg
    _fake = {"google_service_account": json.dumps({"client_email": "sa@x.iam"}),
             "macro_weights_sheet_id": "sheet123"}
    monkeypatch.setattr(_cfg, "get_secret", lambda k, default=None: _fake.get(k, default))
    assert GS.status()["enabled"] is True
    assert GS.is_enabled() is True                                 # SSOT 同向
