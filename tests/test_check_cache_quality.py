"""tests/test_check_cache_quality.py — A1「離線唯讀快取品質檢查」(`scripts/check_cache_quality.py`) 的測試.

授權依據：`DEC-2026-11-10-02`。守的是三件事：

1. **唯讀、零網路**（腳本最硬的邊界）：執行前後 cache 目錄所有檔案 sha256 與 mtime 不變；
   任何 socket 連線即失敗；檢查模組本身不 import requests/yfinance/urllib.request/httpx。
2. **分類正確、缺資料不當正常**：CONFIRMED / SUSPECTED / INSUFFICIENT_EVIDENCE / NO_FINDING 各有例；
   NaN 不被轉 0；缺 metadata／空表／缺欄／單列／全 NaN／無 git 歷史／參考檔損毀都降級為證據不足而不崩潰。
3. **決定性與 --out 保護**。

測試用的 parquet 讀取器是注入的假讀取器（檔案內容為 JSON），所以本檔在**沒有 pyarrow** 的環境也能跑
（`pytest --noconftest`）；只有最後的「真實快取結構」測試需要 pyarrow，缺時 skip（CI 具 pyarrow）。
"""
from __future__ import annotations

import ast
import base64
import builtins
import datetime as dt
import gzip
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts import check_cache_quality as cq  # noqa: E402

SCRIPT_PATH = REPO_ROOT / "scripts" / "check_cache_quality.py"
HAS_GIT = shutil.which("git") is not None


# ════════════════════════════════════════════════════════════════
# helpers
# ════════════════════════════════════════════════════════════════
def json_reader(data: bytes) -> pd.DataFrame:
    """假讀取器：檔案內容是 JSON（dict of lists）。"""
    return pd.DataFrame(json.loads(data.decode("utf-8")))


def _write(path: Path, obj) -> None:
    path.write_text(json.dumps(obj), encoding="utf-8")


def _bdays(start: str, n: int) -> list[str]:
    return [d.date().isoformat() for d in pd.bdate_range(start, periods=n)]


def index_payload(dates: list[str], closes: list) -> dict:
    return {"date": dates, "close": closes}


def make_cache(tmp: Path, *, spx=None, vix=None, twii=None, fred=None, meta="auto") -> Path:
    """建一個 cache 目錄（缺的 dataset 不建檔）。meta='auto' 依內容自動產生一致的 metadata。"""
    tmp.mkdir(parents=True, exist_ok=True)
    payloads = {"spx_history": spx, "vix_history": vix, "twii_history": twii, "fred_indicators": fred}
    ds_meta = {}
    for name, payload in payloads.items():
        if payload is None:
            continue
        _write(tmp / f"{name}.parquet", payload)
        key = "date"
        last = max(payload[key]) if payload.get(key) else None
        ds_meta[name] = {"name": name, "last_updated": last, "row_count": len(payload.get(key, [])), "last_error": None}
    if meta == "auto":
        _write(tmp / "metadata.json", {"updated_at": "x", "datasets": ds_meta})
    elif meta is not None:
        _write(tmp / "metadata.json", meta)
    return tmp


def clean_index(n: int = 12, start: str = "2026-01-05") -> dict:
    dates = _bdays(start, n)
    return index_payload(dates, [100.0 + 1.5 * i for i in range(n)])


def run(cache: Path, **kw) -> dict:
    kw.setdefault("use_git", False)
    return cq.run_checks(cache, reader=json_reader, **kw)


def findings_of(report: dict, dataset: str, check: str | None = None) -> list[dict]:
    return [f for f in report["findings"] if f["dataset"] == dataset and (check is None or f["check"] == check)]


def snapshot(root: Path) -> dict:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            st = p.stat()
            out[str(p.relative_to(root))] = (hashlib.sha256(p.read_bytes()).hexdigest(), st.st_mtime_ns)
    return out


def epoch(iso_utc: str) -> int:
    return int(dt.datetime.fromisoformat(iso_utc.replace("Z", "+00:00")).timestamp())


# ════════════════════════════════════════════════════════════════
# 1. 重用常數、無網路 import
# ════════════════════════════════════════════════════════════════
def test_constants_read_by_ast_match_update_macro_history():
    datasets, fred_ids, source = cq.load_declared_constants()
    assert source == "ast"
    try:
        from scripts import update_macro_history as umh
    except ImportError as exc:  # 缺 requests 等重依賴 → 退回純 ast 比對
        pytest.skip(f"無法 import update_macro_history：{exc}")
    assert tuple(umh.DATASETS) == datasets
    assert tuple(umh.FRED_SERIES_IDS) == fred_ids
    # 最小複本不得與原檔漂移（複本只在 ast 失敗時使用）
    assert cq._FALLBACK_DATASETS == datasets
    assert cq._FALLBACK_FRED_IDS == fred_ids


def test_constants_fallback_when_ast_unreadable(tmp_path):
    bad = tmp_path / "update_macro_history.py"
    bad.write_text("def broken(:\n", encoding="utf-8")
    datasets, fred_ids, source = cq.load_declared_constants(bad)
    assert source == "fallback_copy"
    assert datasets == cq._FALLBACK_DATASETS and fred_ids == cq._FALLBACK_FRED_IDS


def test_module_has_no_network_imports():
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = {"requests", "yfinance", "httpx", "urllib.request", "urllib", "aiohttp", "http.client", "socket", "ftplib"}
    assert not (imported & forbidden), imported & forbidden
    # 真正 import 時（-I 隔離）也不得把 requests/yfinance/httpx 帶進來
    site = str(Path(pd.__file__).resolve().parents[1])  # -I 會忽略 PYTHONPATH，手動帶入 pandas 所在目錄
    code = (
        "import sys; sys.path[:0] = [%r, %r]; import scripts.check_cache_quality; "
        "bad = {'requests','yfinance','httpx'} & set(sys.modules); assert not bad, bad" % (str(REPO_ROOT), site)
    )
    r = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# ════════════════════════════════════════════════════════════════
# 2. 唯讀、零網路
# ════════════════════════════════════════════════════════════════
def test_read_only_and_no_write_to_cache(tmp_path, monkeypatch):
    cache = make_cache(tmp_path / "data_cache", spx=clean_index(), vix=clean_index(), twii=clean_index(),
                       fred={"date": ["2026-01-01"], "series_id": ["DGS10"], "value": [4.0]})
    before = snapshot(cache)
    cache_root = str(cache.resolve())
    real_open = builtins.open

    def guarded_open(file, mode="r", *a, **k):
        if isinstance(file, (str, bytes, os.PathLike)) and any(c in mode for c in "wax+"):
            if str(Path(os.fsdecode(file)).resolve()).startswith(cache_root):
                raise AssertionError(f"對 cache-dir 寫入：{file}")
        return real_open(file, mode, *a, **k)

    def deny(*a, **k):
        raise AssertionError("不得寫入／改名／刪除")

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(Path, "write_bytes", deny)
    monkeypatch.setattr(Path, "write_text", deny)
    monkeypatch.setattr(os, "remove", deny)
    monkeypatch.setattr(os, "rename", deny)
    monkeypatch.setattr(os, "replace", deny)
    run(cache)
    run(cache, use_git=True)  # 非 git 目錄 → 降級，不寫入
    monkeypatch.undo()
    assert snapshot(cache) == before


def test_no_network_access(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("檢查腳本不得觸發網路")

    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(socket, "getaddrinfo", boom)
    try:
        import urllib.request
        monkeypatch.setattr(urllib.request, "urlopen", boom)
    except ImportError:
        pass
    try:
        import requests
        monkeypatch.setattr(requests.sessions.Session, "request", boom)
    except ImportError:
        pass
    cache = make_cache(tmp_path / "c", spx=clean_index(), vix=clean_index(), twii=clean_index(),
                       fred={"date": ["2026-01-01"], "series_id": ["DGS10"], "value": [4.0]})
    report = run(cache, use_git=True)
    assert report["datasets"]["spx_history"]["readable"]


# ════════════════════════════════════════════════════════════════
# 3. 缺漏處理（降級為證據不足，不崩潰）
# ════════════════════════════════════════════════════════════════
def test_missing_files_all_insufficient(tmp_path):
    cache = make_cache(tmp_path / "c", meta=None)
    report = run(cache)
    assert report["summary"]["counts_total"][cq.CONFIRMED] == 0
    for name in ("spx_history", "vix_history", "twii_history", "fred_indicators"):
        fs = findings_of(report, name)
        assert [f["level"] for f in fs] == [cq.INSUFFICIENT] and fs[0]["check"] == "read"


def test_default_reader_without_pyarrow_degrades_gracefully(tmp_path):
    cache = make_cache(tmp_path / "c", spx=clean_index())
    (cache / "spx_history.parquet").write_bytes(b"not a parquet")
    report = cq.run_checks(cache, use_git=False)  # 預設讀取器：壞檔或缺 pyarrow 都應是證據不足
    f = findings_of(report, "spx_history", "read")
    assert f and f[0]["level"] == cq.INSUFFICIENT


def test_empty_table_and_missing_columns_and_single_row(tmp_path):
    cache = make_cache(tmp_path / "c", spx={"date": [], "close": []}, vix={"date": ["2026-01-05"]},
                       twii=index_payload(["2026-01-05"], [100.0]))
    report = run(cache)
    assert findings_of(report, "spx_history")[0]["check"] == "empty"
    assert findings_of(report, "spx_history")[0]["level"] == cq.INSUFFICIENT
    assert findings_of(report, "vix_history")[0]["check"] == "columns"
    # 單列：可評估，無異常 → NO_FINDING（且不崩潰）
    levels = {f["level"] for f in findings_of(report, "twii_history")}
    assert levels == {cq.INSUFFICIENT, cq.NO_FINDING} or levels == {cq.NO_FINDING}


def test_missing_metadata_is_insufficient_not_ok(tmp_path):
    cache = make_cache(tmp_path / "c", spx=clean_index(), meta=None)
    report = run(cache)
    f = findings_of(report, "spx_history", "metadata_consistency")
    assert f and f[0]["level"] == cq.INSUFFICIENT
    # 損毀 metadata
    (cache / "metadata.json").write_text("{not json", encoding="utf-8")
    report = run(cache)
    assert findings_of(report, "spx_history", "metadata_consistency")[0]["level"] == cq.INSUFFICIENT


def test_all_nan_close_is_confirmed_and_never_zero(tmp_path):
    cache = make_cache(tmp_path / "c", spx=index_payload(_bdays("2026-01-05", 3), [None, None, None]))
    report = run(cache)
    bad = findings_of(report, "spx_history", "bad_close")
    assert bad and bad[0]["level"] == cq.CONFIRMED
    assert all(f["check"] != "nonpositive_close" for f in findings_of(report, "spx_history"))  # NaN 沒被當成 0
    assert "0.0" not in json.dumps(bad[0]["detail"])


def test_corrupt_reference_degrades(tmp_path):
    cache = make_cache(tmp_path / "c", spx=clean_index())
    ref = tmp_path / "ref.json"
    ref.write_text("{{{ garbage", encoding="utf-8")
    report = run(cache, reference_path=ref)
    assert report["reference"]["status"] == "unavailable"
    f = findings_of(report, "spx_history", "reference_compare")
    assert f and f[0]["level"] == cq.INSUFFICIENT
    missing = run(cache, reference_path=tmp_path / "nope.json")
    assert findings_of(missing, "spx_history", "reference_compare")[0]["level"] == cq.INSUFFICIENT


def test_no_reference_is_insufficient_not_ok(tmp_path):
    report = run(make_cache(tmp_path / "c", spx=clean_index()))
    assert findings_of(report, "spx_history", "reference_compare")[0]["level"] == cq.INSUFFICIENT


# ════════════════════════════════════════════════════════════════
# 4. 分類正確
# ════════════════════════════════════════════════════════════════
def test_index_confirmed_cases(tmp_path):
    d = _bdays("2026-01-05", 6)
    spx = index_payload(d + [d[2]], [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 9.0])  # 重複日期
    vix = index_payload(d, [5.0, -1.0, 7.0, 8.0, 9.0, 10.0])  # 非正值
    cache = make_cache(tmp_path / "c", spx=spx, vix=vix, twii=clean_index(),
                       meta={"datasets": {"twii_history": {"row_count": 999, "last_updated": "2020-01-01"}}})
    report = run(cache)
    assert findings_of(report, "spx_history", "duplicate_dates")[0]["level"] == cq.CONFIRMED
    assert findings_of(report, "vix_history", "nonpositive_close")[0]["level"] == cq.CONFIRMED
    assert findings_of(report, "twii_history", "metadata_row_count")[0]["level"] == cq.CONFIRMED
    assert findings_of(report, "twii_history", "metadata_last_updated")[0]["level"] == cq.CONFIRMED


def test_unsorted_and_bad_date_confirmed(tmp_path):
    spx = index_payload(["2026-01-06", "2026-01-05", "not-a-date"], [1.0, 2.0, 3.0])
    report = run(make_cache(tmp_path / "c", spx=spx))
    assert findings_of(report, "spx_history", "not_sorted")[0]["level"] == cq.CONFIRMED
    assert findings_of(report, "spx_history", "bad_date")[0]["level"] == cq.CONFIRMED


def test_index_suspected_cases(tmp_path):
    dates = ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-10"]  # 1/10 是週六
    closes = [10.0, 10.0, 11.0, 12.0]  # 1/06 等於前一列
    report = run(make_cache(tmp_path / "c", twii=index_payload(dates, closes)))
    assert findings_of(report, "twii_history", "flat_rows")[0]["level"] == cq.SUSPECTED
    wk = findings_of(report, "twii_history", "weekend_rows")[0]
    assert wk["level"] == cq.SUSPECTED and wk["detail"] == ["2026-01-10"]


def test_no_finding_wording_and_clean_dataset(tmp_path):
    cache = make_cache(tmp_path / "c", spx=clean_index())
    report = run(cache)
    nf = findings_of(report, "spx_history", "all")
    assert nf and nf[0]["level"] == cq.NO_FINDING and "未發現不等於正常" in nf[0]["summary"]
    md = cq.render_markdown(report)
    assert "未發現不等於正常" in md
    assert "不是正式資料契約" in md


def test_vix_vs_spx_date_set_is_observation_only(tmp_path):
    d = _bdays("2026-01-05", 5)
    spx = index_payload(d, [1, 2, 3, 4, 5.0])
    vix = index_payload(d + ["2026-01-12"], [1, 2, 3, 4, 5, 6.0])
    report = run(make_cache(tmp_path / "c", spx=spx, vix=vix))
    ob = [o for o in report["observations"] if o["check"] == "date_set_vs_spx"][0]
    assert ob["detail"]["vix_not_in_spx"] == ["2026-01-12"] and ob["detail"]["spx_not_in_vix"] == []
    assert all(f["check"] != "date_set_vs_spx" for f in report["findings"])  # 不是 finding


# ════════════════════════════════════════════════════════════════
# 5. FRED 盲點偵測
# ════════════════════════════════════════════════════════════════
def _fred_payload() -> dict:
    rows = []
    for d in pd.bdate_range("2024-01-01", "2026-03-31"):  # 日頻，共同最大日期 2026-03-31
        rows.append((d.date().isoformat(), "DGS10", 4.0))
    for d in pd.date_range("2024-01-01", "2025-12-01", freq="MS"):  # 月頻，停在 2025-12-01
        rows.append((d.date().isoformat(), "CPIAUCSL", 300.0))
    for d in pd.date_range("2024-01-01", "2026-03-01", freq="MS"):  # 月頻缺 2025-06-01
        if d.date().isoformat() != "2025-06-01":
            rows.append((d.date().isoformat(), "UNRATE", 4.0))
    for d in ["2026-02-06", "2026-02-13", "2026-02-20", "2026-02-27", "2026-03-06"]:  # 起點晚、列數少
        rows.append((d, "DTWEXBGS", 120.0))
    rows.append(("2026-03-01", "NOT_DECLARED", 1.0))
    return {"date": [r[0] for r in rows], "series_id": [r[1] for r in rows], "value": [r[2] for r in rows]}


def test_fred_blind_spots(tmp_path):
    cache = make_cache(tmp_path / "c", fred=_fred_payload())
    report = run(cache)
    ds = "fred_indicators"
    fa = report["datasets"][ds]
    assert fa["common_max_date"] == "2026-03-31"
    zero = findings_of(report, ds, "declared_series_zero_rows")[0]
    assert zero["level"] == cq.CONFIRMED
    ids = cq.load_declared_constants()[1]
    assert zero["detail"] == sorted(s for s in ids if s not in {"DGS10", "CPIAUCSL", "UNRATE", "DTWEXBGS"})
    lag = {f["series"]: f for f in findings_of(report, ds, "lag_behind_common_max")}
    assert "CPIAUCSL" in lag and lag["CPIAUCSL"]["detail"]["lag_days"] == 120
    assert "DGS10" not in lag and "UNRATE" not in lag  # 2026-03-01 距 03-31 僅 30 天
    gaps = {f["series"]: f for f in findings_of(report, ds, "gaps")}
    assert gaps["UNRATE"]["detail"][0]["from"] == "2025-05-01" and gaps["UNRATE"]["detail"][0]["to"] == "2025-07-01"
    assert "DTWEXBGS" in {f["series"] for f in findings_of(report, ds, "few_rows")}
    assert any(f["series"] == "DTWEXBGS" for f in findings_of(report, ds, "late_start"))
    assert any(o["check"] == "undeclared_series" for o in report["observations"])
    table = {r["series_id"]: r for r in fa["series"]}
    assert table["DGS10"]["inferred_frequency"] == "日頻" and table["CPIAUCSL"]["inferred_frequency"] == "月頻"
    assert table["DTWEXBGS"]["inferred_frequency"] == "週頻"


def test_fred_does_not_alter_values_and_keeps_nan_missing(tmp_path):
    payload = {"date": ["2026-01-01", "2026-01-02", "2026-01-02"], "series_id": ["DGS10"] * 3, "value": [4.0, None, 4.1]}
    df = pd.DataFrame(payload)
    before = df.copy(deep=True)
    findings, _, _ = cq.check_fred_dataset(df, "", None, "no meta", ["DGS10"])
    pd.testing.assert_frame_equal(df, before)  # 輸入未被改
    nan = [f for f in findings if f.check == "nan_values"][0]
    assert nan.level == cq.CONFIRMED and nan.detail == {"DGS10": 1}
    assert [f for f in findings if f.check == "duplicate_keys"][0].level == cq.CONFIRMED


def test_fred_missing_columns_and_empty():
    f, _, _ = cq.check_fred_dataset(pd.DataFrame({"date": [], "value": []}), "", None, "", ["DGS10"])
    assert f[0].level == cq.INSUFFICIENT and f[0].check == "columns"
    f, _, _ = cq.check_fred_dataset(pd.DataFrame({"date": [], "series_id": [], "value": []}), "", None, "", ["DGS10"])
    assert f[0].level == cq.INSUFFICIENT and f[0].check == "empty"


# ════════════════════════════════════════════════════════════════
# 6. 盤中提交時間判斷（手造 commit 時間表，含 DST 與 TWII）
# ════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "dataset, utc_iso, expected_inside, expected_local_date",
    [
        ("spx_history", "2026-03-06T14:35:00Z", True, dt.date(2026, 3, 6)),   # EST：09:35
        ("spx_history", "2026-03-06T13:35:00Z", False, dt.date(2026, 3, 6)),  # EST：08:35 盤前
        ("spx_history", "2026-03-09T13:35:00Z", True, dt.date(2026, 3, 9)),   # DST 後 EDT：09:35
        ("spx_history", "2026-03-09T13:25:00Z", False, dt.date(2026, 3, 9)),  # EDT：09:25 盤前
        ("spx_history", "2026-03-09T20:05:00Z", False, dt.date(2026, 3, 9)),  # EDT：16:05 盤後
        ("spx_history", "2026-11-02T14:35:00Z", True, dt.date(2026, 11, 2)),  # DST 結束後 EST：09:35
        ("spx_history", "2026-11-02T13:35:00Z", False, dt.date(2026, 11, 2)),  # EST：08:35
        ("spx_history", "2026-06-06T14:35:00Z", False, dt.date(2026, 6, 6)),  # 週六
        ("vix_history", "2026-06-03T13:35:13Z", True, dt.date(2026, 6, 3)),   # CDT：08:35
        ("vix_history", "2026-06-03T20:10:00Z", True, dt.date(2026, 6, 3)),   # CDT：15:10
        ("vix_history", "2026-06-03T20:20:00Z", False, dt.date(2026, 6, 3)),  # CDT：15:20
        ("twii_history", "2026-06-03T03:00:00Z", True, dt.date(2026, 6, 3)),  # 台北 11:00
        ("twii_history", "2026-06-03T06:00:00Z", False, dt.date(2026, 6, 3)),  # 台北 14:00 盤後
        ("twii_history", "2026-06-03T00:30:00Z", False, dt.date(2026, 6, 3)),  # 台北 08:30 盤前
        ("twii_history", "2026-06-07T03:00:00Z", False, dt.date(2026, 6, 7)),  # 週日
    ],
)
def test_in_regular_session(dataset, utc_iso, expected_inside, expected_local_date):
    inside, local_date = cq.in_regular_session(dataset, epoch(utc_iso))
    assert inside is expected_inside and local_date == expected_local_date


def _hist(first_seen: dict, shallow=frozenset()) -> cq.GitHistory:
    return cq.GitHistory("ok", "", first_seen, shallow, len(first_seen), 0)


def test_intraday_freeze_flags_only_same_day_row_in_session():
    h = _hist({
        dt.date(2026, 6, 3): ("a" * 40, epoch("2026-06-03T13:35:13Z")),  # 當日列、盤中提交 → 標記
        dt.date(2026, 6, 2): ("a" * 40, epoch("2026-06-03T13:35:13Z")),  # 同提交但非當日列 → 不標記
        dt.date(2026, 6, 4): ("b" * 40, epoch("2026-06-07T03:00:00Z")),  # 週日提交 → 不標記
    })
    fs = cq.check_intraday_freeze("spx_history", [dt.date(2026, 6, 2), dt.date(2026, 6, 3), dt.date(2026, 6, 4)], h)
    assert [f.level for f in fs] == [cq.SUSPECTED]
    assert [r["date"] for r in fs[0].detail] == ["2026-06-03"] and fs[0].detail[0]["first_seen_commit"] == "aaaaaaaa"
    assert fs[0].detail[0]["commit_local"].startswith("2026-06-03 09:35:13")


def test_intraday_freeze_twii_and_vix():
    h = _hist({dt.date(2026, 6, 3): ("c" * 40, epoch("2026-06-03T03:00:00Z"))})
    assert cq.check_intraday_freeze("twii_history", [dt.date(2026, 6, 3)], h)[0].level == cq.SUSPECTED
    h2 = _hist({dt.date(2026, 6, 3): ("c" * 40, epoch("2026-06-03T06:00:00Z"))})  # 台股已收盤
    assert cq.check_intraday_freeze("twii_history", [dt.date(2026, 6, 3)], h2) == []


def test_intraday_freeze_shallow_unknown_and_unavailable():
    sha = "d" * 40
    h = _hist({dt.date(2026, 6, 3): (sha, epoch("2026-06-03T13:35:13Z"))}, shallow=frozenset({sha}))
    fs = cq.check_intraday_freeze("spx_history", [dt.date(2026, 6, 3), dt.date(2026, 6, 4)], h)
    assert {f.check for f in fs} == {"intraday_freeze_shallow", "intraday_freeze_untracked"}
    assert all(f.level == cq.INSUFFICIENT for f in fs)  # 淺層邊界與未提交列都不判定
    assert cq.check_intraday_freeze("spx_history", [], None)[0].level == cq.INSUFFICIENT
    assert cq.check_intraday_freeze("spx_history", [], cq.GitHistory("unavailable", "x"))[0].level == cq.INSUFFICIENT


# ════════════════════════════════════════════════════════════════
# 7. 真實 git（暫存 repo；僅本機 git，無網路）
# ════════════════════════════════════════════════════════════════
def _git(repo: Path, *args: str, date: str | None = None) -> None:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
    if date:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false",
                    *args], cwd=repo, env=env, check=True, capture_output=True)


@pytest.fixture
def git_repo(tmp_path):
    if not HAS_GIT:
        pytest.skip("無 git")
    repo = tmp_path / "repo"
    cache = repo / "data_cache"
    cache.mkdir(parents=True)
    _git(repo, "init", "-q")
    d1 = ["2026-06-01", "2026-06-02"]
    _write(cache / "spx_history.parquet", index_payload(d1, [10.0, 11.0]))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "c1", date="2026-06-02T23:34:00+0000")  # 紐約 19:34，盤後
    _write(cache / "spx_history.parquet", index_payload(d1 + ["2026-06-03"], [10.0, 11.0, 12.0]))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "c2", date="2026-06-03T13:35:13+0000")  # 紐約 09:35:13 盤中
    _write(cache / "spx_history.parquet", index_payload(d1 + ["2026-06-03", "2026-06-04"], [10.0, 11.0, 12.5, 13.0]))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "c3", date="2026-06-07T03:00:00+0000")  # 週日，休市
    return repo


def test_git_history_first_seen_and_intraday_flag(git_repo):
    cache = git_repo / "data_cache"
    h = cq.load_git_history(cache, "spx_history.parquet", json_reader)
    assert h.status == "ok" and h.commit_count == 3
    assert h.first_seen[dt.date(2026, 6, 3)][1] == epoch("2026-06-03T13:35:13Z")
    assert h.first_seen[dt.date(2026, 6, 4)][1] == epoch("2026-06-07T03:00:00Z")
    report = cq.run_checks(cache, reader=json_reader, use_git=True)
    fz = findings_of(report, "spx_history", "intraday_freeze")
    assert [f["level"] for f in fz] == [cq.SUSPECTED]
    assert [r["date"] for r in fz[0]["detail"]] == ["2026-06-03"]  # 06-04 週日提交、06-01/02 盤後 → 不標記
    # 工作樹與 git 同值 → 該檔不被改動
    assert subprocess.run(["git", "status", "--porcelain"], cwd=git_repo, capture_output=True, text=True).stdout == ""


def test_git_shallow_clone_marks_boundary_insufficient(git_repo, tmp_path):
    clone = tmp_path / "shallow"
    subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{git_repo}", str(clone)], check=True, capture_output=True)
    h = cq.load_git_history(clone / "data_cache", "spx_history.parquet", json_reader)
    assert h.status == "ok" and h.shallow_shas
    fs = cq.check_intraday_freeze("spx_history", sorted(h.first_seen), h)
    assert fs and all(f.level == cq.INSUFFICIENT for f in fs)  # 全部列的首見提交是淺層邊界 → 不判定


def test_git_unavailable_degrades(tmp_path, git_repo):
    plain = make_cache(tmp_path / "plain", spx=clean_index())
    h = cq.load_git_history(plain, "spx_history.parquet", json_reader)
    assert h.status == "unavailable"
    h2 = cq.load_git_history(git_repo / "data_cache", "spx_history.parquet", json_reader, git_exe="git-does-not-exist-xyz")
    assert h2.status == "unavailable" and "git" in h2.reason
    h3 = cq.load_git_history(git_repo / "data_cache", "twii_history.parquet", json_reader)  # 歷史中無此檔
    assert h3.status == "unavailable"


# ════════════════════════════════════════════════════════════════
# 8. 參考檔比對
# ════════════════════════════════════════════════════════════════
def _ref_report(bars: dict, tz="America/New_York", *, bad_sha=False, symbol="^GSPC") -> dict:
    stamps = [epoch(f"{d}T14:30:00Z") for d in bars]
    chart = {"chart": {"result": [{"meta": {"exchangeTimezoneName": tz}, "timestamp": stamps,
                                   "indicators": {"quote": [{"close": list(bars.values())}]}}]}}
    raw = json.dumps(chart).encode()
    return {"probe": "synthetic", "run_id": "1", "started_at_utc": "x", "requests": [{
        "requested_index": symbol, "ok": True, "raw_sha256": "0" * 64 if bad_sha else hashlib.sha256(raw).hexdigest(),
        "raw_gzip_b64": base64.b64encode(gzip.compress(raw)).decode()}]}


def test_reference_mismatch_confirmed_and_null_not_zero(tmp_path):
    d = _bdays("2026-06-01", 4)  # 6/1~6/4
    cache = make_cache(tmp_path / "c", spx=index_payload(d, [100.0, 101.0, 102.0, 103.0]))
    ref = tmp_path / "ref.json"
    _write(ref, _ref_report({d[0]: 100.0, d[1]: 101.0, d[2]: 99.0, d[3]: None}))
    report = run(cache, reference_path=ref)
    mm = findings_of(report, "spx_history", "reference_mismatch")
    assert mm and mm[0]["level"] == cq.CONFIRMED
    assert [r["date"] for r in mm[0]["detail"]] == [d[2]] and mm[0]["detail"][0]["reference_close"] == 99.0
    facts = report["datasets"]["spx_history"]
    assert facts["reference_overlap_days"] == 3  # 參考 null 的那天不比、不當 0
    assert report["reference"]["status"] == "ok" and len(report["reference"]["file_sha256"]) == 64


def test_reference_equal_within_float32_tolerance_and_other_symbol(tmp_path):
    d = _bdays("2026-06-01", 2)
    cache = make_cache(tmp_path / "c", spx=index_payload(d, [7595.97998, 100.0]))
    ref = tmp_path / "ref.json"
    _write(ref, _ref_report({d[0]: 7595.979980469, d[1]: 100.0}))
    report = run(cache, reference_path=ref)
    assert not findings_of(report, "spx_history", "reference_mismatch")
    _write(ref, _ref_report({d[0]: 1.0}, symbol="^VIX"))  # 沒有 ^GSPC 序列
    report = run(cache, reference_path=ref)
    assert findings_of(report, "spx_history", "reference_compare")[0]["level"] == cq.INSUFFICIENT


def test_reference_sha_mismatch_is_insufficient(tmp_path):
    d = _bdays("2026-06-01", 2)
    cache = make_cache(tmp_path / "c", spx=index_payload(d, [1.0, 2.0]))
    ref = tmp_path / "ref.json"
    _write(ref, _ref_report({d[0]: 1.0, d[1]: 2.0}, bad_sha=True))
    report = run(cache, reference_path=ref)
    assert findings_of(report, "spx_history", "reference_compare")[0]["level"] == cq.INSUFFICIENT
    assert not findings_of(report, "spx_history", "reference_mismatch")


# ════════════════════════════════════════════════════════════════
# 9. 決定性、--out 保護、CLI
# ════════════════════════════════════════════════════════════════
def test_deterministic_bytes_and_as_of_injection(tmp_path):
    cache = make_cache(tmp_path / "c", spx=clean_index(), vix=clean_index(), twii=clean_index(),
                       fred=_fred_payload())
    a, b = run(cache), run(cache)
    assert cq.render_json(a) == cq.render_json(b) and cq.render_markdown(a) == cq.render_markdown(b)
    assert a["as_of"] is None and "2026-11" not in cq.render_json(a)  # 預設不含執行時間
    c = run(cache, as_of="2026-11-10T00:00:00Z")
    assert c["as_of"] == "2026-11-10T00:00:00Z"
    assert cq.render_json(a).endswith("}\n") and cq.render_markdown(a).endswith("\n")
    levels = [f["level"] for f in a["findings"]]
    assert levels == sorted(levels, key=cq.LEVEL_ORDER.index)  # 固定排序


def test_cli_out_protection(tmp_path, capsys):
    cache = make_cache(tmp_path / "data_cache", spx=clean_index())
    before = snapshot(cache)
    argv = ["--cache-dir", str(cache), "--no-git"]
    assert cq.main(argv + ["--out", str(cache / "report.md")], reader=json_reader) == 2  # 在 cache-dir 內
    existing = tmp_path / "exists.md"
    existing.write_text("keep", encoding="utf-8")
    assert cq.main(argv + ["--out", str(existing)], reader=json_reader) == 2  # 已存在
    assert existing.read_text(encoding="utf-8") == "keep"
    assert cq.main(argv + ["--out", str(tmp_path / "nodir" / "r.md")], reader=json_reader) == 2  # 父目錄不存在
    assert cq.main(["--cache-dir", str(tmp_path / "missing"), "--no-git"], reader=json_reader) == 2
    out = tmp_path / "report.json"
    assert cq.main(argv + ["--format", "json", "--out", str(out)], reader=json_reader) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["report_kind"] == "cache_quality_a1_offline"
    assert cq.main(argv + ["--format", "json", "--out", str(out)], reader=json_reader) == 2  # 第二次：已存在
    assert snapshot(cache) == before
    capsys.readouterr()
    assert cq.main(argv + ["--format", "json"], reader=json_reader) == 0  # 預設只印 stdout
    assert capsys.readouterr().out == out.read_text(encoding="utf-8")


# ════════════════════════════════════════════════════════════════
# 10. 真實快取結構（需 pyarrow；CI 具備，本機缺時 skip）
# ════════════════════════════════════════════════════════════════
def test_real_cache_structure_with_pyarrow():
    pytest.importorskip("pyarrow")
    cache = REPO_ROOT / "data_cache"
    before = snapshot(cache)
    report = cq.run_checks(cache, use_git=False)  # 預設 pandas.read_parquet 讀取器
    assert snapshot(cache) == before  # 唯讀
    assert sorted(report["datasets"]) == sorted(cq.load_declared_constants()[0])
    for name in cq.INDEX_DATASETS:
        fa = report["datasets"][name]
        assert fa["readable"] and fa["rows"] > 1000 and fa["first_date"] <= "2011-06-07"
    fred = report["datasets"]["fred_indicators"]
    declared = cq.load_declared_constants()[1]
    assert fred["readable"] and 0 < fred["series_count"] <= len(declared)
    in_cache = {r["series_id"] for r in fred["series"]}
    assert in_cache <= set(declared)  # 已知事實的穩定部分：快取內的 series 皆為宣告者
    # 已知歷史事實（歷史列不會被移除，故只斷言超集）：VIX 有而 SPX 無的日期含兩個 2026 假日列
    ob = [o for o in report["observations"] if o["check"] == "date_set_vs_spx"][0]
    assert {"2026-05-25", "2026-09-07"} <= set(ob["detail"]["vix_not_in_spx"])
    # 零列宣告 series 的 finding（若存在）必須恰為「宣告而快取沒有」的差集
    zero = findings_of(report, "fred_indicators", "declared_series_zero_rows")
    assert (zero[0]["detail"] if zero else []) == sorted(set(declared) - in_cache)
    # metadata 與檔案應一致（檔案與 metadata 同一次寫入）
    assert not any(f["check"].startswith("metadata_") and f["level"] == cq.CONFIRMED for f in report["findings"])


# ════════════════════════════════════════════════════════════════
# 11. 紅隊 QA 修正：git ref 注入、git 子命令白名單、NO_FINDING 文案、參考檔上限、FRED 全缺值
# ════════════════════════════════════════════════════════════════
class _RunSpy:
    """記錄 subprocess.run 的所有呼叫（仍轉交真實執行）。"""

    def __init__(self, monkeypatch):
        self.calls: list[tuple[list, dict]] = []
        real = subprocess.run

        def spy(argv, *a, **k):
            self.calls.append((list(argv), k))
            return real(argv, *a, **k)

        monkeypatch.setattr(cq.subprocess, "run", spy)


@pytest.mark.parametrize("bad_ref", ["--output={x}", "-x", "--all", "a b", "a\nb", "a\tb", "", "-"])
def test_git_ref_injection_rejected_without_calling_git(tmp_path, monkeypatch, bad_ref):
    cache = make_cache(tmp_path / "data_cache", spx=clean_index())
    target = tmp_path / "X"
    ref = bad_ref.replace("{x}", str(target))
    spy = _RunSpy(monkeypatch)
    popen_calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: popen_calls.append(a) or (_ for _ in ()).throw(AssertionError))
    rc = cq.main(["--cache-dir", str(cache), f"--git-ref={ref}"], reader=json_reader)
    assert rc == 2 and not target.exists() and spy.calls == [] and popen_calls == []
    with pytest.raises(ValueError):  # 函式層也擋
        cq.load_git_history(cache, "spx_history.parquet", json_reader, ref=ref)
    assert spy.calls == [] and not target.exists()


def test_git_all_refs_is_separate_flag_and_unverifiable_ref_degrades(git_repo, monkeypatch):
    cache = git_repo / "data_cache"
    assert cq.load_git_history(cache, "spx_history.parquet", json_reader, all_refs=True).status == "ok"
    assert cq.load_git_history(cache, "spx_history.parquet", json_reader, ref="HEAD").status == "ok"
    h = cq.load_git_history(cache, "spx_history.parquet", json_reader, ref="no-such-branch")
    assert h.status == "unavailable" and "commit" in h.reason
    rc = cq.main(["--cache-dir", str(cache), "--git-all-refs", "--format", "json"], reader=json_reader)
    assert rc == 0


def test_git_calls_are_whitelisted_readonly_and_networkless(git_repo, monkeypatch):
    spy = _RunSpy(monkeypatch)
    cq.run_checks(git_repo / "data_cache", reader=json_reader, use_git=True)
    assert spy.calls, "應有 git 呼叫"
    for argv, kw in spy.calls:
        assert argv[1] == "--no-optional-locks", argv
        assert argv[2] in {"rev-parse", "log", "show"}, argv
        assert kw["env"]["GIT_NO_LAZY_FETCH"] == "1" and kw["env"]["GIT_TERMINAL_PROMPT"] == "0"
        if argv[2] == "show" or (argv[2] == "log" and "--all" not in argv):
            assert "--end-of-options" in argv, argv
    # 變異檢查：任何其他子命令都必須被 _git 擋下（不會到 subprocess）
    before = len(spy.calls)
    for sub in ("fetch", "gc", "update-index", "checkout", "pull", "config"):
        with pytest.raises(ValueError):
            cq._git([sub], git_repo, "git")
    assert len(spy.calls) == before


def test_no_finding_mentions_insufficient_when_present(tmp_path):
    report = run(make_cache(tmp_path / "c", spx=clean_index()))  # 無 git／無參考 → 有證據不足
    nf = findings_of(report, "spx_history", "all")[0]
    assert nf["level"] == cq.NO_FINDING and "另有" in nf["summary"] and "證據不足" in nf["summary"]
    assert "未發現不等於正常" in nf["summary"]


def test_reference_decompressed_size_limit(tmp_path, monkeypatch):
    d = _bdays("2026-06-01", 2)
    ref = tmp_path / "ref.json"
    raw = json.dumps({"pad": "A" * 20000, "chart": {"result": [{"meta": {}, "timestamp": [epoch(f"{d[0]}T14:30:00Z")],
                      "indicators": {"quote": [{"close": [1.0]}]}}]}}).encode()
    rep = {"probe": "x", "requests": [{"requested_index": "^GSPC", "ok": True,
                                       "raw_gzip_b64": base64.b64encode(gzip.compress(raw)).decode()}]}
    _write(ref, rep)
    assert ref.stat().st_size < 2000 < len(raw)  # 壓縮後很小、解開後很大（模擬壓縮炸彈）
    assert cq.load_reference(ref).series["^GSPC"]["closes"]  # 預設上限內正常
    monkeypatch.setattr(cq, "MAX_REFERENCE_BYTES", 2000)
    r = cq.load_reference(ref)
    assert "上限" in r.series["^GSPC"]["problem"] and not r.series["^GSPC"]["closes"]
    cache = make_cache(tmp_path / "c", spx=index_payload(d, [1.0, 2.0]))
    assert findings_of(run(cache, reference_path=ref), "spx_history", "reference_compare")[0]["level"] == cq.INSUFFICIENT
    monkeypatch.setattr(cq, "MAX_REFERENCE_BYTES", 10)  # 參考檔本身超過上限
    assert cq.load_reference(ref).status == "unavailable"


def test_reference_deeply_nested_json_degrades(tmp_path):
    deep = "[" * 200000
    ref = tmp_path / "deep.json"
    ref.write_text(deep, encoding="utf-8")
    assert cq.load_reference(ref).status == "unavailable"
    raw = deep.encode()
    rep = {"probe": "x", "requests": [{"requested_index": "^GSPC", "ok": True,
                                       "raw_gzip_b64": base64.b64encode(gzip.compress(raw)).decode()}]}
    ref2 = tmp_path / "deep2.json"
    _write(ref2, rep)
    r = cq.load_reference(ref2)
    assert r.status == "ok" and r.series["^GSPC"]["problem"] and not r.series["^GSPC"]["closes"]


def test_fred_zero_rows_vs_all_missing_distinguished():
    df = pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "series_id": ["DGS10", "DGS2"], "value": [4.0, None]})
    findings, _, _ = cq.check_fred_dataset(df, "", None, "", ["DGS10", "DGS2", "PPIACO"])
    by = {f.check: f for f in findings}
    assert by["declared_series_zero_rows"].detail == ["PPIACO"]
    assert by["declared_series_all_missing"].detail == ["DGS2"]
    assert by["declared_series_all_missing"].level == cq.CONFIRMED
