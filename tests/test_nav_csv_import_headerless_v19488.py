"""v19.488:NAV CSV 上傳 — 內容偵測 date/nav 欄,修「無表頭 cache/GS-export 解析失敗」。

Bug:app 從 Google Sheets `nav_history` 匯出的 CSV 是**無表頭、code 開頭**的 6-7 欄格式
(code,date,nav,name,source,fetched_at)。原 parser 靠 pandas 預設 header=0 → 第一列資料
被當表頭,退路挑 code 欄當 date、date 值當 nav → 全 row 失敗。改內容偵測後全解析。
"""
import io

import pandas as pd

from services.nav_history_store import (
    _detect_columns,
    export_nav_csv,
    import_nav_csv,
)


def _read(b: bytes) -> pd.DataFrame:
    """比照 import_nav_csv 的讀法(header=None, dtype=str,多 encoding)。"""
    for enc in ("utf-8-sig", "utf-8", "big5", "cp950"):
        try:
            df = pd.read_csv(io.BytesIO(b), encoding=enc, header=None, dtype=str)
            if not df.empty:
                return df
        except Exception:
            continue
    raise AssertionError("read failed")


# ── 核心:_detect_columns 內容偵測(純函式) ─────────────────────────────
def test_detect_headerless_code_first_gs_export():
    """無表頭 GS/cache 匯出格式:code,date,nav,name,source,fetched_at → date=1, nav=2。"""
    rows = "\n".join(
        f"ACDD19,2020/1/{d},{40 + d}.5,安聯台灣智慧基金,backfill,2026-08-19T00:30:59+00:00"
        for d in range(1, 20)
    )
    df = _read(rows.encode("utf-8"))
    assert _detect_columns(df) == (1, 2)


def test_detect_standard_date_nav_header():
    df = _read(b"date,nav\n2024/03/15,12.34\n2024/03/16,12.40\n2024/03/17,12.55\n")
    assert _detect_columns(df) == (0, 1)


def test_detect_chinese_header():
    df = _read("日期,淨值\n2024/03/15,12.34\n2024/03/16,12.40\n".encode("utf-8"))
    assert _detect_columns(df) == (0, 1)


def test_detect_roc_dates():
    df = _read(b"date,nav\n113/03/15,12.34\n113/03/16,12.40\n113/03/17,12.55\n")
    dcol, ncol = _detect_columns(df)
    assert (dcol, ncol) == (0, 1)


def test_detect_fetched_at_collision_picks_varying_date_col():
    """關鍵:col5 fetched_at 也解析成日期,但為常數 → 取相異值最多的真淨值日欄(col1)。"""
    rows = "\n".join(
        f"ACDD19,2021/6/{d},{100 + d}.0,x,backfill,2026-08-19T00:30:59+00:00"
        for d in range(1, 25)
    )
    df = _read(rows.encode("utf-8"))
    dcol, ncol = _detect_columns(df)
    assert dcol == 1 and ncol == 2   # 不可挑到常數時間戳 col5


# ── 端到端:import_nav_csv(monkeypatch cache 到 tmp)────────────────────
def _patch_cache(monkeypatch, tmp_path):
    import services.nav_history_store as st
    monkeypatch.setattr(st, "_CACHE_DIR", tmp_path / "nav_history")


def test_import_headerless_gs_export_parses_all(monkeypatch, tmp_path):
    _patch_cache(monkeypatch, tmp_path)
    rows = "\n".join(
        f"ACDD19,2020/1/{d},{40 + d}.5,安聯台灣智慧基金,backfill,2026-08-19T00:30:59+00:00"
        for d in range(1, 29)
    )
    r = import_nav_csv("ACDD19", rows.encode("utf-8"))
    assert r["errors"] == []
    assert r["total"] == 28
    assert r["date_min"] == "2020-01-01" and r["date_max"] == "2020-01-28"


def test_import_big5_name_does_not_break(monkeypatch, tmp_path):
    """Big5 編碼的中文名欄不可讓整檔解析失敗(只有 name 欄非 ASCII)。"""
    _patch_cache(monkeypatch, tmp_path)
    line = "ACDD19,2020/1/2,46.58,安聯台灣智慧基金,backfill,2026-08-19T00:30:59+00:00\n"
    r = import_nav_csv("ACDD19", line.encode("big5"))
    assert r["errors"] == [] and r["total"] == 1


def test_export_import_roundtrip(monkeypatch, tmp_path):
    """app 自己的 export_nav_csv(date,nav 表頭)→ import 必須完整還原。"""
    _patch_cache(monkeypatch, tmp_path)
    src = "\n".join(f"AAA,2022/2/{d},{50 + d}.25,n,backfill,ts" for d in range(1, 15))
    import_nav_csv("AAA", src.encode("utf-8"))
    exported = export_nav_csv("AAA")            # date,nav 表頭格式
    import services.nav_history_store as st
    monkeypatch.setattr(st, "_CACHE_DIR", tmp_path / "nav_history2")
    r = import_nav_csv("AAA", exported)
    assert r["errors"] == [] and r["total"] == 14


def test_import_garbage_still_fails_loud(monkeypatch, tmp_path):
    """§1:真的沒有 date/nav 欄 → 誠實回錯,不靜默成功。"""
    _patch_cache(monkeypatch, tmp_path)
    r = import_nav_csv("Z", b"foo,bar,baz\nhello,world,test\nlorem,ipsum,dolor\n")
    assert r["errors"] and r["total"] == 0
