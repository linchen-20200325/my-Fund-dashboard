"""tests/test_migrate_nav_caches.py — v19.365 ④:舊 NAV 快取遷移 Sheet(儲存收斂)。

守:
- collect_points:兩套 schema(CI cache/nav + Tab6 cache/nav_history)都解析成統一 point
- 白名單過濾:非白名單代碼(測試殘留 XYZ/CACHED01 類)顯式 skip + 列名
- allow=None(--all)→ 不過濾
- 壞檔(爛 JSON / dates,values 長度不符)顯式 skip,不炸整批(§1/§4.6)
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT = (Path(__file__).resolve().parents[1]
           / "scripts" / "migrate_nav_caches_to_sheet.py")


def _load():
    spec = importlib.util.spec_from_file_location("_mig_under_test", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_MOD = _load()


def _mk_dirs(tmp_path):
    nav = tmp_path / "nav"
    hist = tmp_path / "nav_history"
    nav.mkdir()
    hist.mkdir()
    return nav, hist


def test_collects_both_schemas(tmp_path):
    nav, hist = _mk_dirs(tmp_path)
    (nav / "TLZF9.json").write_text(json.dumps({
        "code": "TLZF9", "fund_name": "安聯",
        "history": [{"date": "2026-07-20", "nav": 12.1},
                    {"date": "2026-07-21", "nav": 12.2}]}), encoding="utf-8")
    (hist / "ACTI94.json").write_text(json.dumps({
        "timestamp": 1.0, "dates": ["2024-01-02", "2024-01-03"],
        "values": [10.0, 10.1]}), encoding="utf-8")
    pts, skipped = _MOD.collect_points(nav, hist, allow={"TLZF9", "ACTI94"})
    assert len(pts) == 4 and skipped == []
    srcs = {p["source"] for p in pts}
    assert srcs == {"migrate_ci_cache", "migrate_disk_store"}
    tl = [p for p in pts if p["code"] == "TLZF9"]
    assert tl[0]["nav_date"] == "2026-07-20" and tl[0]["fund_name"] == "安聯"


def test_whitelist_filters_test_leftovers(tmp_path):
    nav, hist = _mk_dirs(tmp_path)
    (hist / "XYZ.json").write_text(json.dumps({
        "timestamp": 1.0, "dates": ["2024-01-01"], "values": [10.0]}), encoding="utf-8")
    (hist / "ACTI94.json").write_text(json.dumps({
        "timestamp": 1.0, "dates": ["2024-01-02"], "values": [10.0]}), encoding="utf-8")
    pts, skipped = _MOD.collect_points(nav, hist, allow={"ACTI94"})
    assert len(pts) == 1 and pts[0]["code"] == "ACTI94"
    assert any("XYZ" in s for s in skipped)           # 顯式列名,不靜默


def test_allow_none_migrates_all(tmp_path):
    nav, hist = _mk_dirs(tmp_path)
    (hist / "XYZ.json").write_text(json.dumps({
        "timestamp": 1.0, "dates": ["2024-01-01"], "values": [10.0]}), encoding="utf-8")
    pts, skipped = _MOD.collect_points(nav, hist, allow=None)
    assert len(pts) == 1 and skipped == []


def test_bad_files_skipped_explicitly(tmp_path):
    nav, hist = _mk_dirs(tmp_path)
    (nav / "BAD.json").write_text("not json", encoding="utf-8")
    (hist / "MISMATCH.json").write_text(json.dumps({
        "timestamp": 1.0, "dates": ["2024-01-01", "2024-01-02"],
        "values": [10.0]}), encoding="utf-8")          # 長度不符
    (nav / "OK.json").write_text(json.dumps({
        "history": [{"date": "2026-07-20", "nav": 1.0}]}), encoding="utf-8")
    pts, skipped = _MOD.collect_points(nav, hist, allow=None)
    assert len(pts) == 1 and pts[0]["code"] == "OK"
    assert len(skipped) == 2                            # 兩壞檔都被顯式記錄


def test_missing_dirs_return_empty(tmp_path):
    pts, skipped = _MOD.collect_points(tmp_path / "no1", tmp_path / "no2", allow=None)
    assert pts == [] and skipped == []
