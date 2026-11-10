"""B1 純離線驗證:FRED「全表最大日期 + 1」增量語意與三個候選方案(2026-11-10)。

證據標籤(每個測試 docstring 開頭):
  [機制成立-合成]   以合成世界驗證生產函式(update_one 等)或候選模擬的機制;
                    對真實 FRED 回傳行為 NOT VERIFIED。
  [真實資料-副本]   直接觀察 data_cache 快取副本(僅記憶體讀取、不寫檔);只斷言結構性不變量,
                    不釘死會隨每週 Actions 提交而變的具體數值。
  [推論]            由上述推得、未直接觀察。
  [NOT VERIFIED]    真實 FRED 回傳、發布延遲真值、vintage 修訂——本檔一律不宣稱。

硬限制:不連網(socket 連線即 fail)、不寫 data_cache、不 import streamlit/infra;
假 Key 於執行期組成;候選 A/B/B2/C 僅存在於 tests/_fred_incremental_sim.py,不是 production。
"""
from __future__ import annotations

import datetime as dt
import hashlib
import socket
import sys
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("pyarrow")

_TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_TESTS))
import _fred_incremental_sim as S  # noqa: E402

D = dt.date
STRATS = ("baseline", "A", "B", "B2", "C")
REAL_PARQUET = _TESTS.parent / "data_cache" / "fred_indicators.parquet"


@pytest.fixture(autouse=True)
def _no_network_and_restore(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("離線測試不得建立網路連線")
    monkeypatch.setattr(socket.socket, "connect", _boom)
    monkeypatch.setattr(socket, "create_connection", _boom)
    keep = {k: getattr(S.PROD, k) for k in
            ("CACHE_DIR", "META_PATH", "_fred_get_single", "FRED_SERIES_IDS",
             "_FRED_INTER_CALL_SLEEP_SEC")}
    yield
    for k, v in keep.items():
        setattr(S.PROD, k, v)


def _truth(world, sid, start, today):
    return {d for d, _v, rel in world[sid] if start <= d <= today and rel <= today}


def _run(strategy, runs, world, tmp_path, **kw):
    return S.run_timeline(strategy, runs, world, tmp_path, **kw)


# ═════════════ 情境定義(矩陣用);回 (final, runs, world, 檢核函式) ═════════════
def _scn_s1(tmp_path, strategy, two_failures=False):
    world = {"X": S.periodic_world(D(2026, 4, 1), D(2026, 6, 30), 7),
             "Y": S.periodic_world(D(2026, 4, 2), D(2026, 6, 30), 7)}
    ids = ("X", "Y")
    runs = [{"today": D(2026, 5, 3), "ids": ids},
            {"today": D(2026, 5, 10), "ids": ids, "fail": {"X"}}]
    if two_failures:
        runs.append({"today": D(2026, 5, 17), "ids": ids, "fail": {"X"}})
    runs.append({"today": D(2026, 5, 24), "ids": ids})
    final, metas, _ = _run(strategy, runs, world, tmp_path, years=1)
    miss = sorted(_truth(world, "X", D(2025, 5, 24), D(2026, 5, 24)) - set(S.as_dates(final, "X")))
    return final, runs, miss, metas


def _verdict_s1(tmp_path, strategy, two_failures=False):
    final, runs, miss, _ = _scn_s1(tmp_path, strategy, two_failures)
    if strategy == "C":
        dg = S.diagnose(final, ("X", "Y"), runs[-1]["today"], years=1)
        flagged = sorted(k for k, v in dg.items() if "internal_gap" in v["flags"])
        ok = flagged == ["X"]
        return ("DETECT" if ok else "FAIL",
                f"缺 {len(miss)} 個觀測;internal_gap 旗標={flagged}(只偵測,表未修復)")
    return ("PASS" if not miss else "FAIL", f"X 永久缺觀測日 {[str(m) for m in miss]}")


def _scn_s2(tmp_path, strategy):
    world = {"DGS": S.daily_world(D(2024, 6, 1), D(2026, 6, 30)),
             "NEW": S.periodic_world(D(2024, 6, 5), D(2026, 6, 30), 7)}
    runs = [{"today": D(2026, 6, 2), "ids": ("DGS",)},
            {"today": D(2026, 6, 28), "ids": ("DGS", "NEW")}]
    final, _m, _s = _run(strategy, runs, world, tmp_path, years=2)
    miss = _truth(world, "NEW", S.window_start(D(2026, 6, 28), 2), D(2026, 6, 28)) \
        - set(S.as_dates(final, "NEW"))
    return final, runs, miss


def _verdict_s2(tmp_path, strategy):
    final, runs, miss = _scn_s2(tmp_path, strategy)
    if strategy == "C":
        d = S.diagnose(final, ("DGS", "NEW"), runs[-1]["today"], years=2)
        return ("DETECT" if "head_gap" in d["NEW"]["flags"] else "FAIL",
                f"NEW 缺 {len(miss)} 列;旗標={d['NEW']['flags']}(只偵測)")
    return ("PASS" if not miss else "FAIL", f"NEW 缺 {len(miss)} 個窗內觀測")


def _scn_s3(tmp_path, strategy):
    """假設世界:觀測日 M 月 1 日於同月 20 日公布(真實月頻慣例通常是 M+1 月公布,故此為假設,
    非對真實 FRED 的描述)。結論僅限結構性論點:嚴格以觀測日過濾時,觀測日早於全表最大日期的
    月頻值取不到。UNRATE 的真實觀察與該過濾模型衝突,成因未解;CPI/M2 停更亦可能是 series 級取數失敗。"""
    world = {"DGS": S.daily_world(D(2026, 1, 1), D(2026, 6, 30)),
             "CPI": [S.obs(D(2026, m, 1), 100 + m, D(2026, m, 1) + dt.timedelta(days=19))
                     for m in range(1, 7)]}          # 05-01 於 05-20 公布:假設的延遲模型
    ids = ("DGS", "CPI")
    runs = [{"today": D(2026, 5, 15), "ids": ids}, {"today": D(2026, 5, 22), "ids": ids},
            {"today": D(2026, 5, 30), "ids": ids}]
    final, metas, _ = _run(strategy, runs, world, tmp_path, years=1)
    return final, runs, world, metas


def _verdict_s3(tmp_path, strategy):
    final, runs, world, _ = _scn_s3(tmp_path, strategy)
    got = D(2026, 5, 1) in S.as_dates(final, "CPI")
    if strategy == "C":
        d = S.diagnose(final, ("DGS", "CPI"), runs[-1]["today"], years=1)
        late = "stale" in d["CPI"]["flags"]
        return ("DETECT" if late else "FAIL",
                f"05-30 時 CPI 旗標={d['CPI']['flags']}(落後 59 天 < 門檻 75 天 → 未偵測;最快約 75 天後)")
    return ("PASS" if got else "FAIL",
            "CPI 05-01 " + ("已取得" if got else "永不取到(觀測日 < 全表最大日期)"))


def _scn_s5(tmp_path, strategy):
    world = {"DGS": S.daily_world(D(2025, 6, 1), D(2026, 6, 30)),
             "Z": S.periodic_world(D(2025, 6, 5), D(2026, 6, 30), 7)}
    initial = pd.DataFrame(
        [(d, "DGS", v) for d, v, r in world["DGS"] if r <= D(2026, 5, 31)], columns=S.COLS)
    runs = [{"today": D(2026, 6, 1), "ids": ("DGS", "Z")}]
    final, metas, starts = _run(strategy, runs, world, tmp_path, initial=initial, years=1)
    miss = _truth(world, "Z", S.window_start(D(2026, 6, 1), 1), D(2026, 6, 1)) \
        - set(S.as_dates(final, "Z"))
    return final, runs, miss, initial


def _verdict_s5(tmp_path, strategy):
    final, runs, miss, initial = _scn_s5(tmp_path, strategy)
    if strategy == "C":
        d = S.diagnose(final, ("DGS", "Z"), runs[-1]["today"], years=1)
        return ("DETECT" if "head_gap" in d["Z"]["flags"] or "zero_rows" in d["Z"]["flags"]
                else "FAIL", f"Z 缺 {len(miss)} 列;旗標={d['Z']['flags']}")
    return ("PASS" if not miss else "FAIL", f"零列 Z 缺 {len(miss)} 個窗內觀測")


def _verdict_s6(tmp_path, strategy):
    world = {"X": S.periodic_world(D(2026, 4, 1), D(2026, 6, 30), 7),
             "Y": S.periodic_world(D(2026, 4, 2), D(2026, 6, 30), 7),
             "Z": S.periodic_world(D(2026, 2, 6), D(2026, 3, 20), 7)}   # Z 合法地久無新資料(超過重疊窗口)
    ids = ("X", "Y", "Z")
    runs = [{"today": D(2026, 5, 3), "ids": ids},
            {"today": D(2026, 5, 10), "ids": ids, "fail": {"Y"}}]
    final, metas, _ = _run(strategy, runs, world, tmp_path, years=1)
    m = metas[-1]
    if strategy == "baseline":
        extra = set(m) - {"name", "last_updated", "row_count", "last_error"}
        return ("PARTIAL" if extra else "FAIL",
                f"metadata 多餘欄位={sorted(extra)}(無則無 per-series 欄位);last_error={m['last_error']}")
    if strategy == "C":
        d = S.diagnose(final, ids, runs[-1]["today"], years=1)
        hit = set(d["Y"]["flags"]) & {"stale", "zero_rows", "internal_gap"}
        return ("DETECT" if hit else "FAIL",
                f"Y 失敗旗標={sorted(hit)}(空集合=一週內不會被旗標);Z 旗標={d['Z']['flags']},二者無法區分失敗與合法無新資料")
    ss = m["series_status"]
    same = ss["Y"]["status"] == ss["Z"]["status"]
    if same:
        return ("PARTIAL", f"有 per-series 狀態,但失敗 Y 與合法無新資料 Z 同為 {ss['Y']['status']}(現行取數層不回錯誤)")
    return ("PASS", f"重疊錨點使存活 series 必回至少 1 列:Y={ss['Y']['status']}、Z={ss['Z']['status']};"
                    "空回應可判為失敗(前提:該 series 未被上游移除,NOT VERIFIED)")


def _verdict_s7(tmp_path, strategy):
    world = {"X": [S.obs(D(2026, 6, 1) + dt.timedelta(days=i), 10 + i) for i in range(4)]}
    world["X"].append(S.obs(D(2026, 6, 1), 11.0, D(2026, 6, 20)))     # 06-01 的修訂版(假設)
    world["X"] += [S.obs(D(2026, 6, 5) + dt.timedelta(days=i), 20 + i) for i in range(21)]
    runs = [{"today": D(2026, 6, 5), "ids": ("X",)}, {"today": D(2026, 6, 25), "ids": ("X",)}]
    final, metas, _ = _run(strategy, runs, world, tmp_path, years=1)
    v = S.values(final, "X")[D(2026, 6, 1)]
    conflicts = metas[-1].get("conflicts", [])
    if strategy == "B":
        return ("FAIL" if v == 11.0 and not conflicts else "PASS",
                f"06-01 值 10→{v},未留任何差異記錄(靜默覆寫)")
    if strategy == "B2":
        return ("PASS" if v == 10.0 and len(conflicts) == 1 else "FAIL",
                f"保留舊值 {v},差異清單 {len(conflicts)} 筆(未採用修訂值,需裁示)")
    return ("PASS" if v == 10.0 else "FAIL",
            f"不重疊 → 舊值 {v} 不被動(但也永不採用修訂值)")


def _verdict_s8(tmp_path, strategy):
    world = {"X": S.daily_world(D(2026, 5, 1), D(2026, 6, 30))}
    runs = [{"today": D(2026, 6, 10), "ids": ("X",)}]
    d1 = tmp_path / "r1"
    d2 = tmp_path / "r2"
    d1.mkdir()
    d2.mkdir()
    f1, m1, _ = _run(strategy, runs, world, d1, years=1)
    runs2 = runs + [{"today": D(2026, 6, 10), "ids": ("X",)}]
    f2, m2, _ = _run(strategy, runs2, world, d2, years=1)
    p1, p2 = tmp_path / "o1.parquet", tmp_path / "o2.parquet"
    f1.to_parquet(p1, compression="snappy", index=False)
    f2.to_parquet(p2, compression="snappy", index=False)
    same = p1.read_bytes() == p2.read_bytes()
    err = m2[-1]["last_error"]
    if strategy == "C":
        return ("PARTIAL" if same and err else "PASS", f"同 baseline;位元組相同={same};第二輪 last_error={err}")
    if not same:
        return "FAIL", "兩次輸出 Parquet 位元組不同"
    return ("PARTIAL" if err else "PASS",
            f"輸出位元組相同;第二輪 last_error={err!r}" + ("(重跑被誤報為錯誤)" if err else ""))


def _verdict_s9(tmp_path, strategy):
    world = {"W": S.periodic_world(D(2025, 7, 4), D(2026, 11, 6), 7)}
    initial = pd.DataFrame([(d, "W", v) for d, v, _r in world["W"] if d >= D(2026, 6, 5)
                            and d <= D(2026, 10, 30)], columns=S.COLS)
    runs = [{"today": D(2026, 11, 8), "ids": ("W",)}]
    final, _m, _s = _run(strategy, runs, world, tmp_path, initial=initial, years=1)
    head = [d for d in S.as_dates(final, "W") if d < D(2026, 6, 5)]
    if strategy == "C":
        d = S.diagnose(final, ("W",), runs[-1]["today"], years=1)
        return ("DETECT" if "head_gap" in d["W"]["flags"] else "FAIL",
                f"旗標={d['W']['flags']},建議起點={d['W']['suggest_start']}")
    return ("PASS" if head else "FAIL", f"起點之前的歷史補回 {len(head)} 列")


def _verdict_s10(tmp_path, strategy):
    months = [D(2025, 6 + i, 1) if 6 + i <= 12 else D(2026, 6 + i - 12, 1) for i in range(0, 11)]
    world = {"M": [S.obs(d, 100 + i, d + dt.timedelta(days=19)) for i, d in enumerate(months)]}
    initial = pd.DataFrame([(d, "M", v) for d, v, _r in world["M"] if d != D(2026, 1, 1)
                            and d <= D(2026, 4, 1)], columns=S.COLS)
    runs = [{"today": D(2026, 5, 30), "ids": ("M",)}]
    final, _m, _s = _run(strategy, runs, world, tmp_path, initial=initial, years=2)
    healed = D(2026, 1, 1) in S.as_dates(final, "M")
    if strategy == "C":
        d = S.diagnose(final, ("M",), runs[-1]["today"], years=2)
        return ("DETECT" if "internal_gap" in d["M"]["flags"] else "FAIL",
                f"旗標={d['M']['flags']},建議起點={d['M']['suggest_start']}")
    return ("PASS" if healed else "FAIL", "既有 2026-01 空洞(距最新 90 天)" + ("已補" if healed else "未補"))


SCENARIOS = {
    "S1 單週失敗後恢復": lambda p, s: _verdict_s1(p, s),
    "S1b 連兩週失敗後恢復": lambda p, s: _verdict_s1(p, s, True),
    "S2 後加入 series": _verdict_s2,
    "S3 月頻發布延遲": _verdict_s3,
    "S5 零列 series": _verdict_s5,
    "S6 部分成功 metadata": _verdict_s6,
    "S7 重疊區修訂值": _verdict_s7,
    "S8 冪等(重跑)": _verdict_s8,
    "S9 既有表起點前缺頭": _verdict_s9,
    "S10 既有內部空洞(90天前)": _verdict_s10,
}

# 釘住的預期矩陣(PASS 修復/無害;FAIL 失敗;PARTIAL 部分;DETECT 只偵測不修復)
EXPECTED = {
    "S1 單週失敗後恢復":      dict(baseline="FAIL", A="PASS", B="PASS", B2="PASS", C="DETECT"),
    "S1b 連兩週失敗後恢復":   dict(baseline="FAIL", A="PASS", B="PASS", B2="PASS", C="DETECT"),
    "S2 後加入 series":       dict(baseline="FAIL", A="PASS", B="PASS", B2="PASS", C="DETECT"),
    "S3 月頻發布延遲":        dict(baseline="FAIL", A="PASS", B="PASS", B2="PASS", C="FAIL"),
    "S5 零列 series":         dict(baseline="FAIL", A="PASS", B="PASS", B2="PASS", C="DETECT"),
    "S6 部分成功 metadata":   dict(baseline="FAIL", A="PARTIAL", B="PASS", B2="PASS", C="FAIL"),
    "S7 重疊區修訂值":        dict(baseline="PASS", A="PASS", B="FAIL", B2="PASS", C="PASS"),
    "S8 冪等(重跑)":          dict(baseline="PARTIAL", A="PARTIAL", B="PASS", B2="PASS", C="PARTIAL"),
    "S9 既有表起點前缺頭":    dict(baseline="FAIL", A="FAIL", B="FAIL", B2="FAIL", C="DETECT"),
    "S10 既有內部空洞(90天前)": dict(baseline="FAIL", A="FAIL", B="PASS", B2="PASS", C="DETECT"),
}


@pytest.mark.parametrize("scn", list(SCENARIOS))
@pytest.mark.parametrize("strategy", STRATS)
def test_matrix_cell(scn, strategy, tmp_path):
    """[機制成立-合成] 方案×情境矩陣逐格釘住;baseline/C 的表由 production update_one 產生。"""
    verdict, reason = SCENARIOS[scn](tmp_path, strategy)
    assert verdict == EXPECTED[scn][strategy], f"{scn}/{strategy}: {verdict} | {reason}"


# ═════════════ 基線(生產函式)機制 ═════════════
def test_s1_baseline_meta_hides_failed_series(tmp_path):
    """[機制成立-合成] 單一 series 失敗那週:last_error 仍 None、last_updated 照樣前進,缺的觀測永不回補。"""
    final, runs, miss, metas = _scn_s1(tmp_path, "baseline")
    assert metas[1]["last_error"] is None
    assert metas[1]["last_updated"] > metas[0]["last_updated"]
    assert D(2026, 5, 6) in miss


def test_s3_global_max_and_release_delay_model(tmp_path):
    """[機制成立-合成;僅在嚴格觀測日過濾模型下成立,假設 05-01 於 05-20 公布,非真實月頻慣例]
    月頻觀測日 05-01(05-20 公布)早於全表最大日期 05-29 → 永不取到。
    結構性結論:月頻起始日觀測在公布當下,觀測日必然早於日頻 series 的最大日期。"""
    final, runs, world, metas = _scn_s3(tmp_path, "baseline")
    assert metas[-1]["last_updated"] == "2026-05-29"
    assert D(2026, 5, 1) not in S.as_dates(final, "CPI")
    assert max(S.as_dates(final, "CPI")) == D(2026, 4, 1)


def test_s6_failure_and_empty_indistinguishable_at_fetch_layer(tmp_path):
    """[機制成立-合成] 生產 fetch_fred_indicators 對「取數失敗」與「無新資料」都不產生該 series 的列,
    輸出完全相同 → 事後無法區分。(替換 _fred_get_single 為回空表,與其失敗路徑同形)"""
    S.PROD._FRED_INTER_CALL_SLEEP_SEC = 0.0
    S.PROD.FRED_SERIES_IDS = ("X", "Y")

    def fake(sid, start, end, key):
        return pd.DataFrame({"date": [D(2026, 5, 1)], "value": [1.0]}) if sid == "X" else pd.DataFrame()
    S.PROD._fred_get_single = fake
    out = S.PROD.fetch_fred_indicators(D(2026, 5, 1), D(2026, 5, 2), "fake" + "key")
    assert set(out.series_id) == {"X"}


def test_s8_baseline_rerun_reports_false_error(tmp_path):
    """[機制成立-合成] 同日重跑:表不變,但第二輪 last_error='抓取結果為空'(無新資料被當成錯誤)。"""
    world = {"X": S.daily_world(D(2026, 5, 1), D(2026, 6, 30))}
    runs = [{"today": D(2026, 6, 10), "ids": ("X",)}] * 2
    _f, metas, _s = _run("baseline", runs, world, tmp_path, years=1)
    assert metas[0]["last_error"] is None
    assert metas[1]["last_error"] == "抓取結果為空"


def test_production_merge_dedupe_keeps_last_overwrites_silently():
    """[機制成立-合成] production _merge_dedupe 對同 (date, series_id) 保留 new:舊值被覆寫且無任何記錄。
    現行增量起點不重疊所以此路徑平時不觸發;任何重疊窗口方案都會啟動它。"""
    old = pd.DataFrame([(D(2026, 6, 1), "X", 10.0)], columns=S.COLS)
    new = pd.DataFrame([(D(2026, 6, 1), "X", 11.0)], columns=S.COLS)
    out = S.PROD._merge_dedupe(old, new, key=["date", "series_id"])
    assert len(out) == 1 and float(out.value.iloc[0]) == 11.0


def test_sim_baseline_equals_production(tmp_path):
    """[機制成立-合成] 驗證模擬器:純函式 baseline 與 production update_one 在同一時間線得到相同表。"""
    world = {"A1": S.daily_world(D(2026, 1, 1), D(2026, 6, 30)),
             "B1": S.periodic_world(D(2026, 1, 3), D(2026, 6, 30), 7)}
    ids = ("A1", "B1")
    runs = [{"today": D(2026, 3, 1), "ids": ids}, {"today": D(2026, 4, 1), "ids": ids, "fail": {"B1"}},
            {"today": D(2026, 5, 1), "ids": ids}]
    prod, _m, _s = _run("baseline", runs, world, tmp_path, years=1)
    table = None
    for r in runs:
        table, _meta = S.pure_update("baseline", table, r["ids"], r["today"], world,
                                     fail=r.get("fail", ()), years=1)
    a = prod.sort_values(S.COLS[:2]).reset_index(drop=True)
    b = table.sort_values(S.COLS[:2]).reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b)


# ═════════════ 候選方案性質 ═════════════
@pytest.mark.parametrize("strategy", ["A", "B", "B2"])
def test_no_duplicate_dates_and_unrelated_series_untouched(strategy, tmp_path):
    """[機制成立-合成] 重疊/逐 series 起點不產生重複 (date, series_id);失敗 series 的既有列逐列不變。"""
    final, _runs, _miss, _m = _scn_s1(tmp_path, strategy, two_failures=True)
    assert not final.duplicated(["date", "series_id"]).any()
    world = {"X": S.periodic_world(D(2026, 4, 1), D(2026, 6, 30), 7),
             "Y": S.periodic_world(D(2026, 4, 2), D(2026, 6, 30), 7)}
    t0, _ = S.pure_update(strategy, None, ("X", "Y"), D(2026, 5, 3), world, years=1)
    t1, _ = S.pure_update(strategy, t0, ("X", "Y"), D(2026, 5, 10), world, fail={"X"}, years=1)
    pd.testing.assert_frame_equal(
        t0[t0.series_id == "X"].reset_index(drop=True),
        t1[t1.series_id == "X"].reset_index(drop=True))


@pytest.mark.parametrize("strategy", ["A", "B", "B2"])
def test_candidates_never_invent_values(strategy, tmp_path):
    """[機制成立-合成] 缺值不填 0、不插補:輸出每一列都出自世界的某筆觀測。"""
    final, _runs, _miss, _m = _scn_s1(tmp_path, strategy, two_failures=True)
    assert final.value.notna().all()
    world = {"X": S.periodic_world(D(2026, 4, 1), D(2026, 6, 30), 7),
             "Y": S.periodic_world(D(2026, 4, 2), D(2026, 6, 30), 7)}
    allowed = {(d, sid, v) for sid, rows in world.items() for d, v, _r in rows}
    got = {(pd.Timestamp(d).date(), s, float(v)) for d, s, v in final[S.COLS].itertuples(index=False)}
    assert got <= allowed


def test_b_overlap_sensitivity_n_matters_for_internal_holes(tmp_path):
    """[機制成立-合成] 空洞在 90 天前:N=100 補得到、N=60 補不到 → N 是需要依據的設計參數。"""
    for n, expect in ((100, True), (60, False)):
        sub = tmp_path / f"n{n}"
        sub.mkdir()
        months = [D(2025, 6 + i, 1) if 6 + i <= 12 else D(2026, 6 + i - 12, 1) for i in range(0, 11)]
        world = {"M": [S.obs(d, 100 + i, d + dt.timedelta(days=19)) for i, d in enumerate(months)]}
        initial = pd.DataFrame([(d, "M", v) for d, v, _r in world["M"] if d != D(2026, 1, 1)
                                and d <= D(2026, 4, 1)], columns=S.COLS)
        final, _m, _s = _run("B", [{"today": D(2026, 5, 30), "ids": ("M",)}], world, sub,
                             initial=initial, years=2, n_map={"D": 7, "W": 21, "M": n})
        assert (D(2026, 1, 1) in S.as_dates(final, "M")) is expect


def test_b2_apply_new_variant_logs_and_adopts(tmp_path):
    """[機制成立-合成] B2 的 apply_new 變體:採用修訂值但留下差異清單(與 B 的差別是『有記錄』)。"""
    world = {"X": [S.obs(D(2026, 6, 1), 10.0), S.obs(D(2026, 6, 1), 11.0, D(2026, 6, 20)),
                   S.obs(D(2026, 6, 5), 20.0)]}
    runs = [{"today": D(2026, 6, 6), "ids": ("X",)}, {"today": D(2026, 6, 25), "ids": ("X",)}]
    final, metas, _ = _run("B2", runs, world, tmp_path, years=1, on_conflict="apply_new")
    assert S.values(final, "X")[D(2026, 6, 1)] == 11.0
    assert metas[-1]["conflicts"] == [{"date": D(2026, 6, 1), "series_id": "X", "old": 10.0, "new": 11.0}]


def test_b_idempotent_when_world_unchanged(tmp_path):
    """[機制成立-合成] 世界不變時,B/B2 連跑兩次表逐列相同、B2 差異清單為空。"""
    world = {"X": S.daily_world(D(2026, 5, 1), D(2026, 6, 30))}
    t1, _ = S.pure_update("B2", None, ("X",), D(2026, 6, 10), world, years=1)
    t2, m2 = S.pure_update("B2", t1, ("X",), D(2026, 6, 10), world, years=1)
    pd.testing.assert_frame_equal(t1.reset_index(drop=True), t2.reset_index(drop=True))
    assert m2["conflicts"] == []


def test_permanently_empty_series_costs_window_every_run_but_adds_nothing(tmp_path):
    """[機制成立-合成] 世界上永遠無資料的 declared series:A/B 每輪都以視窗起點重抓(成本),且不產生任何列。
    是否會有此類真實 series 為 NOT VERIFIED(快取副本中的零列 series 原因未知)。"""
    world = {"X": S.daily_world(D(2026, 1, 1), D(2026, 6, 30))}
    for strat in ("A", "B"):
        table = None
        for today in (D(2026, 5, 1), D(2026, 5, 8)):
            starts = S.compute_starts(strat, table, ("X", "Z"), today, years=1)
            assert starts["Z"] == S.window_start(today, 1)
            table, _m = S.pure_update(strat, table, ("X", "Z"), today, world, years=1)
        assert "Z" not in set(table.series_id)


def test_diagnose_cannot_tell_legit_publication_lag_from_a_miss():
    """[推論-合成] C 的『落後門檻』無法區分合法發布延遲與漏抓:兩種表在同一天得到相同旗標。
    (需發布日曆才能區分;真實發布日曆 NOT VERIFIED)"""
    legit = pd.DataFrame([(D(2026, m, 1), "M", 1.0) for m in range(1, 5)], columns=S.COLS)
    missed = legit.copy()
    today = D(2026, 6, 20)             # 04-01 距今 80 天 > 75
    f_legit = S.diagnose(legit, ("M",), today, years=1)["M"]["flags"]
    f_missed = S.diagnose(missed, ("M",), today, years=1)["M"]["flags"]
    assert f_legit == f_missed and "stale" in f_legit


def test_diagnose_row_drop_and_zero_rows():
    """[機制成立-合成] C:列數驟減與零列旗標。"""
    t = pd.DataFrame([(D(2026, 6, 1) + dt.timedelta(days=i), "X", 1.0) for i in range(5)], columns=S.COLS)
    d = S.diagnose(t, ("X", "Z"), D(2026, 6, 6), years=1, prev_counts={"X": 100})
    assert "row_drop" in d["X"]["flags"] and d["Z"]["flags"] == ["zero_rows"]


# ═════════════ 真實快取副本(僅記憶體唯讀;只斷言結構性不變量) ═════════════
@pytest.fixture(scope="module")
def real_table():
    if not REAL_PARQUET.exists():
        pytest.skip("data_cache/fred_indicators.parquet 不存在")
    return pd.read_parquet(REAL_PARQUET)


def test_real_copy_read_does_not_modify_file():
    """[真實資料-副本] 讀取快取副本前後 sha256 相同(本檔不覆寫既有 Parquet)。"""
    if not REAL_PARQUET.exists():
        pytest.skip("data_cache/fred_indicators.parquet 不存在")
    h1 = hashlib.sha256(REAL_PARQUET.read_bytes()).hexdigest()
    pd.read_parquet(REAL_PARQUET)
    S.real_copy_starts(pd.read_parquet(REAL_PARQUET), S.PROD.FRED_SERIES_IDS)
    assert hashlib.sha256(REAL_PARQUET.read_bytes()).hexdigest() == h1


def test_real_copy_start_table_structural_invariants(real_table):
    """[真實資料-副本] 模擬日固定為常數 2026-11-10(非 datetime.now)。
    結構性不變量:現行語意每個 series 起點皆為『全表最大日期+1』;A 起點不晚於 baseline 起點之外的
    有資料 series 皆 = 自身最大日期+1;B 起點 <= A 起點;零列 series 在 A/B 的起點 = 視窗起點。
    具體數值(哪些 series 落後多久)見草稿報告,隨每週 Actions 提交而變,不在此釘死。"""
    assert S.SIM_DAY == D(2026, 11, 10)
    ids = S.PROD.FRED_SERIES_IDS
    tab = S.real_copy_starts(real_table, ids)
    gmax = pd.to_datetime(real_table.date).max().date()
    wstart = S.window_start(S.SIM_DAY, S.DEFAULT_YEARS)
    assert set(tab.baseline) == {gmax + S.ONE}
    for r in tab.itertuples():
        if r.rows == 0:
            assert r.A == wstart and r.B == wstart and "zero_rows" in r.C_flags
        else:
            assert r.A == r.max + S.ONE and r.B <= r.A
            assert r.A <= r.baseline


def test_real_copy_has_no_duplicate_keys(real_table):
    """[真實資料-副本] 快取副本無重複 (date, series_id)(重疊窗口合併前的前置條件)。"""
    assert not real_table.duplicated(["date", "series_id"]).any()
