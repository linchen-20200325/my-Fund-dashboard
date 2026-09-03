"""tests/test_batch_checkpoint.py — 批次分析磁碟續存 L1 測試。

§6 三大最易錯輸入:
1. 壞 checkpoint 檔          → load 回 None(不 crash;§1 可重跑)
2. run_id 對「同一份清單」穩定 → 順序 / 大小寫 / 重複無關(續跑命中正確存檔的關鍵)
3. 原子覆寫                  → save 兩次後只剩 1 個正式檔、無殘留 temp

外加:round-trip(含 JSON-safe None/float/bool)、缺檔、結構不符、delete 冪等、
list_recent 新→舊排序且跳過壞檔、save 自動建目錄。

全部導向 tmp_path,不碰真 data_cache/。
"""
from __future__ import annotations

import json
import os

import pytest

from repositories import batch_checkpoint as bc


@pytest.fixture(autouse=True)
def _tmp_dir(tmp_path, monkeypatch):
    """把 checkpoint 目錄導到 tmp,避免污染 repo data_cache/。"""
    monkeypatch.setattr(bc, "_DIR", tmp_path / "batch")
    return tmp_path / "batch"


# ───────────────────── run_id 穩定性(輸入#2)─────────────────────
def test_run_id_stable_across_order_case_dup():
    a = bc.compute_run_id(["accp138", "B07", "0050"])
    b = bc.compute_run_id(["0050", "ACCP138", "b07", "0050", "  "])
    assert a == b and len(a) == 12


def test_run_id_differs_for_different_sets():
    assert bc.compute_run_id(["A123"]) != bc.compute_run_id(["A124"])


# ───────────────────── round-trip ─────────────────────
def test_save_load_roundtrip_json_safe_values():
    rows = {
        "ACCP138": {"status": "ok", "nav": 104.0, "sharpe": None, "is_sparse": False},
        "B07": {"status": "fetch_fail", "note": "403", "nav": None},
    }
    rid = bc.compute_run_id(["ACCP138", "B07"])
    bc.save(rid, ["ACCP138", "B07"], rows)
    d = bc.load(rid)
    assert d["rows"] == rows
    assert d["n_done"] == 2
    assert d["codes"] == ["ACCP138", "B07"]


def test_save_creates_dir(_tmp_dir):
    assert not _tmp_dir.exists()          # fixture 尚未建
    bc.save("deadbeef0001", ["X"], {"X": {"status": "ok"}})
    assert _tmp_dir.exists()


def test_load_missing_returns_none():
    assert bc.load("nonexistent0") is None


# ───────────────────── 壞檔容錯(輸入#1)─────────────────────
def test_load_corrupt_json_returns_none(_tmp_dir):
    _tmp_dir.mkdir(parents=True, exist_ok=True)
    (_tmp_dir / "batch_bad1.json").write_text("{not valid json", encoding="utf-8")
    assert bc.load("bad1") is None        # 不 raise


def test_load_wrong_structure_returns_none(_tmp_dir):
    _tmp_dir.mkdir(parents=True, exist_ok=True)
    (_tmp_dir / "batch_bad2.json").write_text(json.dumps({"foo": 1}), encoding="utf-8")
    assert bc.load("bad2") is None        # 有效 json 但缺 rows dict → None


# ───────────────────── 原子覆寫(輸入#3)─────────────────────
def test_save_atomic_overwrite_no_leftover_temp(_tmp_dir):
    rid = bc.compute_run_id(["X"])
    bc.save(rid, ["X"], {"X": {"n": 1}})
    bc.save(rid, ["X"], {"X": {"n": 2}})            # 覆寫
    assert bc.load(rid)["rows"]["X"]["n"] == 2       # 後寫贏
    # 只有 1 個正式檔、無殘留 .tmp_
    formal = list(_tmp_dir.glob("batch_*.json"))
    temps = list(_tmp_dir.glob(".tmp_batch_*"))
    assert len(formal) == 1 and len(temps) == 0


# ───────────────────── delete / list_recent ─────────────────────
def test_delete_removes_and_idempotent():
    rid = bc.compute_run_id(["X"])
    bc.save(rid, ["X"], {"X": {"status": "ok"}})
    bc.delete(rid)
    assert bc.load(rid) is None
    bc.delete(rid)                         # 再刪不炸


def test_list_recent_newest_first_and_skips_corrupt(_tmp_dir):
    bc.save("aaaaaaaaaaaa", ["A"], {"A": {"status": "ok"}})
    bc.save("bbbbbbbbbbbb", ["B", "C"], {"B": {"status": "ok"}})
    # 強制 mtime 排序:b 比 a 新
    os.utime(_tmp_dir / "batch_aaaaaaaaaaaa.json", (1000, 1000))
    os.utime(_tmp_dir / "batch_bbbbbbbbbbbb.json", (2000, 2000))
    # 混一個壞檔 → 應被跳過
    (_tmp_dir / "batch_corrupt0.json").write_text("garbage", encoding="utf-8")

    recent = bc.list_recent()
    ids = [r["run_id"] for r in recent]
    assert ids == ["bbbbbbbbbbbb", "aaaaaaaaaaaa"]     # 新→舊,壞檔不列
    assert recent[0]["n_codes"] == 2 and recent[0]["n_done"] == 1


def test_list_recent_empty_when_no_dir():
    assert bc.list_recent() == []


# ─────────── 整合:L2 攤平列必須能無損穿過 L1 checkpoint ───────────
# ⚠️ 2026-08-28 Phase 1.4:本區塊原有 test_analyze_row_survives_checkpoint,
#   驗「services.fund_batch.analyze_fund_row 產的列 → bc.save(json.dump) → bc.load 無損還原」
#   這條跨模組契約。隨 `services/fund_batch.py` 整檔刪除而移除
#   (**測試對象消失,不是為了讓 CI 綠**;該檔 production 0 caller,user 2026-08-28 明確點名刪除)。
#   ⚠️ 連帶效果據實記錄:`batch_checkpoint.save` 的「輸入須 JSON-safe」這個要求**仍然成立**,
#   只是它原本唯一的 production 生產者不見了,故不再有可驗的對象;
#   日後若有新的 L2 生產者接進 checkpoint,應在此重建同型整合測試。
