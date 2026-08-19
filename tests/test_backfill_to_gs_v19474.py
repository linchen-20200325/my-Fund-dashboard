"""v19.474:一鍵補全部缺淨值 `nav_history_store.backfill_to_gs`。

user 2026-08-18「前面資料有缺的都要補起來」——把持倉 ∪ 選股池逐檔完整歷史(含選股池
ISIN→晨星 ~5.5 年)一次抓齊 → 本地 cache + 雲端 nav_history(永久)。

驗證重點(§1/§2.4/§3.2/§5):
- 抓到 → 逐檔 fetched/date 範圍 + 收集點一次寫 GS
- 抓不到 / 空序列 → 該檔 error 誠實回報,不偽造(§1),不擋整批
- 代號去重 + upper(§2.1)
- 序列清洗:唯一日期 × 非 NaN × >0(§3.2)
- GS 未啟用 → gs_enabled=False / gs_written=0,不呼叫 append_points(§2.4)
- append_points 拋錯 → 已抓檔標記雲端寫入失敗(§1 不靜默)
- progress_cb 逐檔回呼
"""
import numpy as np
import pandas as pd
import pytest

import services.nav_history_store as NS


def _series(pairs):
    idx = pd.to_datetime([d for d, _ in pairs])
    return pd.Series([v for _, v in pairs], index=idx, dtype=float)


@pytest.fixture(autouse=True)
def _no_disk(monkeypatch):
    """本地 cache 讀寫改記憶體,測試不碰磁碟。"""
    _store: dict = {}
    monkeypatch.setattr(NS, "_load_cache_series",
                        lambda code: _store.get(code, pd.Series(dtype=float)))
    monkeypatch.setattr(NS, "_save_cache_series",
                        lambda code, s: _store.__setitem__(code, s))
    return _store


def _wire(monkeypatch, *, fetch, enabled=True, append=None):
    """接上 auto_fetch_moneydj / nav_history_gs.is_enabled / append_points 假件。"""
    import services.moneydj_fetcher as MF
    import services.nav_history_gs as GS
    monkeypatch.setattr(MF, "auto_fetch_moneydj", fetch)
    monkeypatch.setattr(GS, "is_enabled", lambda: enabled)
    _calls = []

    def _default_append(points, **kw):
        _calls.append(points)
        return {"written": len(points), "skipped": 0}

    monkeypatch.setattr(GS, "append_points", append or _default_append)
    return _calls


# ── happy path:兩檔抓到 → 一次寫 GS ─────────────────────────────────────
def test_backfill_ok_two_funds_single_gs_write(monkeypatch):
    fds = {
        "AAA": {"series": _series([("2020-01-01", 10.0), ("2020-01-02", 10.5)]),
                "fund_name": "Fund A USD"},
        "BBB": {"series": _series([("2021-06-01", 20.0)]), "full_key": "BBB-key"},
    }
    calls = _wire(monkeypatch, fetch=lambda c: fds[c])
    out = NS.backfill_to_gs(["AAA", "BBB"])

    assert out["gs_enabled"] is True
    assert out["n_ok"] == 2 and out["n_fail"] == 0
    assert out["gs_written"] == 3            # 2 + 1 點,一次寫入
    assert len(calls) == 1                   # §5:只呼叫 append_points 一次
    _by = {r["code"]: r for r in out["results"]}
    assert _by["AAA"]["fetched"] == 2
    assert _by["AAA"]["date_min"] == "2020-01-01" and _by["AAA"]["date_max"] == "2020-01-02"
    assert _by["BBB"]["fetched"] == 1
    # 收集的點帶 code/nav/nav_date/fund_name/source
    _pt = calls[0][0]
    assert _pt["code"] == "AAA" and _pt["source"] == "backfill"
    assert _pt["fund_name"] == "Fund A USD" and "nav_date" in _pt and "nav" in _pt


# ── 抓不到 / 空序列 → §1 誠實 error,不擋整批 ───────────────────────────
def test_backfill_missing_series_reports_error(monkeypatch):
    def _fetch(c):
        return {"series": _series([("2020-01-01", 10.0)])} if c == "GOOD" \
            else {"series": pd.Series(dtype=float), "error": "抓不到淨值(晨星查無 secId)"}
    _wire(monkeypatch, fetch=_fetch)
    out = NS.backfill_to_gs(["GOOD", "BAD"])
    _by = {r["code"]: r for r in out["results"]}
    assert _by["GOOD"]["error"] is None and _by["GOOD"]["fetched"] == 1
    assert _by["BAD"]["error"] and "晨星查無 secId" in _by["BAD"]["error"]
    assert _by["BAD"]["fetched"] == 0
    assert out["n_ok"] == 1 and out["n_fail"] == 1


def test_backfill_fetch_raises_is_isolated(monkeypatch):
    def _fetch(c):
        if c == "BOOM":
            raise RuntimeError("network down")
        return {"series": _series([("2020-01-01", 10.0)])}
    _wire(monkeypatch, fetch=_fetch)
    out = NS.backfill_to_gs(["BOOM", "OK"])
    _by = {r["code"]: r for r in out["results"]}
    assert "補抓失敗" in _by["BOOM"]["error"] and "RuntimeError" in _by["BOOM"]["error"]
    assert _by["OK"]["error"] is None            # 一檔炸不擋另一檔
    assert out["n_ok"] == 1 and out["n_fail"] == 1


# ── 代號去重 + upper(§2.1)──────────────────────────────────────────────
def test_backfill_dedup_and_upper(monkeypatch):
    seen = []

    def _fetch(c):
        seen.append(c)
        return {"series": _series([("2020-01-01", 10.0)])}
    _wire(monkeypatch, fetch=_fetch)
    out = NS.backfill_to_gs(["aaa", "AAA", " aaa ", "bbb"])
    assert seen == ["AAA", "BBB"]                # 去重 + upper,只抓兩次
    assert len(out["results"]) == 2


# ── 序列清洗:唯一日期 × 非 NaN × >0(§3.2/§4.2)─────────────────────────
def test_backfill_cleans_series(monkeypatch):
    dirty = _series([("2020-01-01", 10.0), ("2020-01-01", 10.2),   # 重複日
                     ("2020-01-02", np.nan),                        # NaN
                     ("2020-01-03", 0.0), ("2020-01-04", -5.0),     # <=0
                     ("2020-01-05", 11.0)])
    calls = _wire(monkeypatch, fetch=lambda c: {"series": dirty})
    out = NS.backfill_to_gs(["X"])
    r = out["results"][0]
    assert r["fetched"] == 2                     # 只剩 01-01(去重留最後)與 01-05
    assert r["date_min"] == "2020-01-01" and r["date_max"] == "2020-01-05"
    assert len(calls[0]) == 2 and all(p["nav"] > 0 for p in calls[0])


def test_backfill_all_dirty_reports_empty(monkeypatch):
    dirty = _series([("2020-01-01", np.nan), ("2020-01-02", -1.0)])
    _wire(monkeypatch, fetch=lambda c: {"series": dirty})
    out = NS.backfill_to_gs(["X"])
    assert out["results"][0]["error"] and "清乾淨後為空" in out["results"][0]["error"]
    assert out["n_ok"] == 0


def test_backfill_same_date_valid_plus_nan_keeps_valid(monkeypatch):
    """稽核 F5:同日「有效值 + NaN」——先驗值再去重,不可整日丟失。"""
    dirty = _series([("2020-01-01", 10.0), ("2020-01-01", np.nan),
                     ("2020-01-02", 11.0), ("2020-01-02", -5.0)])
    calls = _wire(monkeypatch, fetch=lambda c: {"series": dirty})
    out = NS.backfill_to_gs(["X"])
    r = out["results"][0]
    assert r["fetched"] == 2                       # 兩天都保住(各留有效值)
    _navs = {p["nav_date"].isoformat(): p["nav"] for p in calls[0]}
    assert _navs == {"2020-01-01": 10.0, "2020-01-02": 11.0}


def test_backfill_drops_future_dates(monkeypatch):
    """稽核 F1:上游 misparse 出的未來日 → 不進 fetched/date_max/雲端(對齊 GS 守衛)。"""
    import datetime as _dt
    _tw = _dt.timezone(_dt.timedelta(hours=8))
    _future = (_dt.datetime.now(_tw).date() + _dt.timedelta(days=400)).isoformat()
    s = _series([("2020-01-01", 10.0), ("2020-01-02", 10.5), (_future, 99.0)])
    calls = _wire(monkeypatch, fetch=lambda c: {"series": s})
    out = NS.backfill_to_gs(["X"])
    r = out["results"][0]
    assert r["fetched"] == 2                        # 未來日被丟
    assert r["date_max"] == "2020-01-02"            # date_max 誠實 = 真實最後可用日
    assert all(p["nav"] != 99.0 for p in calls[0])  # 未來日的值不進雲端


def test_backfill_bad_index_isolated_not_whole_batch(monkeypatch):
    """稽核 F2:某檔序列 index 非日期(清洗會炸)→ 只該檔 error,不擋整批。"""
    def _fetch(c):
        if c == "BADIDX":
            return {"series": pd.Series([10.0, 11.0], index=["nope", "still-bad"])}
        return {"series": _series([("2020-01-01", 10.0)])}
    _wire(monkeypatch, fetch=_fetch)
    out = NS.backfill_to_gs(["BADIDX", "GOOD"])
    _by = {r["code"]: r for r in out["results"]}
    assert _by["BADIDX"]["error"]                   # 該檔誠實回 error
    assert _by["GOOD"]["error"] is None and _by["GOOD"]["fetched"] == 1
    assert out["n_ok"] == 1 and out["n_fail"] == 1


# ── GS 未啟用 → 不寫、據實標記(§2.4)──────────────────────────────────
def test_backfill_gs_disabled_local_only(monkeypatch):
    calls = _wire(monkeypatch, fetch=lambda c: {"series": _series([("2020-01-01", 10.0)])},
                  enabled=False)
    out = NS.backfill_to_gs(["X"])
    assert out["gs_enabled"] is False and out["gs_written"] == 0
    assert out["n_ok"] == 1                       # 仍抓到、存本機
    assert calls == []                            # 未啟用 → 不呼叫 append_points
    assert out["results"][0]["error"] is None     # 本機成功不算失敗


# ── append_points 拋錯 → §1/§5:寫入失敗獨立回報,不抹掉 fetch 結果 ────────
def test_backfill_gs_write_failure_surfaced(monkeypatch):
    def _boom(points, **kw):
        raise RuntimeError("quota exceeded")
    _wire(monkeypatch, fetch=lambda c: {"series": _series([("2020-01-01", 10.0)])},
          append=_boom)
    out = NS.backfill_to_gs(["X"])
    assert out["gs_written"] == 0
    assert out["gs_error"] and "雲端寫入失敗" in out["gs_error"]   # 寫入失敗走 batch 級 gs_error
    assert out["results"][0]["error"] is None                     # fetch 成功不因 write 失敗被抹掉
    assert out["n_ok"] == 1 and out["n_fail"] == 0                # 抓到就算 ok(§5 不混為一談)


# ── progress_cb 逐檔回呼 ────────────────────────────────────────────────
def test_backfill_progress_callback(monkeypatch):
    _wire(monkeypatch, fetch=lambda c: {"series": _series([("2020-01-01", 10.0)])})
    seen = []
    NS.backfill_to_gs(["A", "B"], progress_cb=lambda i, n, code: seen.append((i, n, code)))
    assert (0, 2, "A") in seen and (1, 2, "B") in seen
    assert (2, 2, "") in seen                     # 收尾回呼


def test_backfill_progress_cb_error_does_not_break(monkeypatch):
    _wire(monkeypatch, fetch=lambda c: {"series": _series([("2020-01-01", 10.0)])})

    def _bad_cb(i, n, code):
        raise ValueError("ui blew up")
    out = NS.backfill_to_gs(["A"], progress_cb=_bad_cb)   # 不應拋出
    assert out["n_ok"] == 1


def test_backfill_empty_codes(monkeypatch):
    calls = _wire(monkeypatch, fetch=lambda c: {"series": _series([("2020-01-01", 10.0)])})
    out = NS.backfill_to_gs([])
    assert out["results"] == [] and out["n_ok"] == 0 and out["gs_written"] == 0
    assert calls == []


# ══════════════════════════════════════════════════════════════════════════
# v19.475:ISIN 直驅長歷史救援(繞過保單前綴 gate;user 回報「不是抓半年的嗎」)
# ══════════════════════════════════════════════════════════════════════════
def _long(n_days, end="2025-01-01"):
    """n_days 筆日資料的長序列(span ≈ n_days-1 天)。"""
    idx = pd.date_range(end=end, periods=n_days, freq="D")
    return pd.Series([10.0 + i / 100.0 for i in range(n_days)], index=idx, dtype=float)


def _wire_rescue(monkeypatch, *, isin="LU123", ms=None, cnyes=None):
    """接上 ISIN 救援三件套:pool_repository.resolve_isin + 晨星/CnYES source。"""
    import repositories.fund.sources as SRC
    import repositories.pool_repository as PR
    monkeypatch.setattr(PR, "resolve_isin", lambda code: isin)
    monkeypatch.setattr(SRC, "_src_morningstar_nav",
                        lambda code, fund_name="": (ms if ms is not None else pd.Series(dtype=float)))
    monkeypatch.setattr(SRC, "_src_cnyes_nav",
                        lambda code: (cnyes if cnyes is not None else pd.Series(dtype=float)))


def test_rescue_morningstar_replaces_short_moneydj(monkeypatch):
    """auto 只 ~30 天 + 池有 ISIN → 晨星長歷史(不看前綴)取代;source=morningstar(ISIN)。"""
    short = _series([("2024-12-01", 10.0), ("2024-12-30", 10.5)])   # ~29d
    _wire(monkeypatch, fetch=lambda c: {"series": short})
    _wire_rescue(monkeypatch, ms=_long(800))                        # ~2.2yr
    r = NS.backfill_to_gs(["ACDD19"])["results"][0]                 # AC* 前綴(原本被 gate 擋)
    assert r["source"] == "morningstar(ISIN)"
    assert r["fetched"] == 800 and r["span_days"] >= 730


def test_rescue_falls_to_cnyes_when_morningstar_empty(monkeypatch):
    short = _series([("2024-12-01", 10.0), ("2024-12-30", 10.5)])
    _wire(monkeypatch, fetch=lambda c: {"series": short})
    _wire_rescue(monkeypatch, ms=pd.Series(dtype=float), cnyes=_long(900))
    r = NS.backfill_to_gs(["ALBT8"])["results"][0]
    assert r["source"] == "cnyes(ISIN)" and r["span_days"] >= 730


def test_rescue_skipped_when_no_isin(monkeypatch):
    short = _series([("2024-12-01", 10.0), ("2024-12-30", 10.5)])
    _wire(monkeypatch, fetch=lambda c: {"series": short})
    _wire_rescue(monkeypatch, isin="", ms=_long(800))              # 無 ISIN → 不救援
    r = NS.backfill_to_gs(["X"])["results"][0]
    assert r["source"] == "moneydj" and r["fetched"] == 2


def test_rescue_skipped_when_moneydj_already_long(monkeypatch):
    """auto 已 > 2 年 → 不觸發救援(不白呼叫晨星)。"""
    import repositories.fund.sources as SRC
    import repositories.pool_repository as PR
    called = {"ms": 0}

    def _ms(code, fund_name=""):
        called["ms"] += 1
        return _long(2000)
    _wire(monkeypatch, fetch=lambda c: {"series": _long(800)})     # auto 已 ~2.2yr(>730)
    monkeypatch.setattr(PR, "resolve_isin", lambda code: "LU1")
    monkeypatch.setattr(SRC, "_src_morningstar_nav", _ms)
    monkeypatch.setattr(SRC, "_src_cnyes_nav", lambda code: pd.Series(dtype=float))
    r = NS.backfill_to_gs(["X"])["results"][0]
    assert r["source"] == "moneydj" and called["ms"] == 0


def test_rescue_candidate_shorter_not_adopted(monkeypatch):
    """候選比 auto 短 → 不採用(單調不減,§ 與 orchestration 同精神)。"""
    _wire(monkeypatch, fetch=lambda c: {"series": _long(400)})     # ~399d(<730 → 觸發救援)
    _wire_rescue(monkeypatch, ms=_long(300))                       # 更短 → 不換
    r = NS.backfill_to_gs(["X"])["results"][0]
    assert r["source"] == "moneydj" and r["fetched"] == 400


def test_rescue_source_raises_isolated(monkeypatch):
    """晨星救援拋錯 → 只 log,CnYES 接手,不擋整檔(§1)。"""
    import repositories.fund.sources as SRC
    import repositories.pool_repository as PR
    _wire(monkeypatch, fetch=lambda c: {"series": _series([("2024-12-01", 10.0), ("2024-12-30", 10.5)])})
    monkeypatch.setattr(PR, "resolve_isin", lambda code: "LU1")

    def _boom(code, fund_name=""):
        raise RuntimeError("morningstar 403")
    monkeypatch.setattr(SRC, "_src_morningstar_nav", _boom)
    monkeypatch.setattr(SRC, "_src_cnyes_nav", lambda code: _long(800))
    r = NS.backfill_to_gs(["X"])["results"][0]
    assert r["source"] == "cnyes(ISIN)" and r["error"] is None


def test_rescue_sparse_candidate_not_adopted_over_dense(monkeypatch):
    """稽核 F1:候選跨度略長但**點數少很多** → 不可換掉密集現有序列(3Y/5Y 年化需足點數)。"""
    dense = _long(500)                                      # 500 筆日資料 / span 499(<730 → 觸發救援)
    sparse_longer = _series([("2020-01-01", 10.0), ("2020-06-01", 10.1),
                             ("2021-01-01", 10.2), ("2021-06-01", 10.3),
                             ("2022-01-01", 10.4), ("2022-06-01", 10.5),
                             ("2023-01-01", 10.6), ("2023-06-01", 10.7),
                             ("2024-01-01", 10.8), ("2024-06-01", 10.9),
                             ("2024-12-01", 11.0)])         # 11 筆(≥10)/ span ~1795(>499)但稀疏
    _wire(monkeypatch, fetch=lambda c: {"series": dense})
    _wire_rescue(monkeypatch, ms=sparse_longer)
    r = NS.backfill_to_gs(["X"])["results"][0]
    assert r["source"] == "moneydj" and r["fetched"] == 500   # 密集現有序列保住,不被稀疏候選換掉


def test_rescue_tz_aware_candidate_handled(monkeypatch):
    """稽核 Low:tz-aware 候選 index → _clean 轉 naive,不拋、仍可採用。"""
    short = _series([("2024-12-01", 10.0), ("2024-12-30", 10.5)])
    _idx = pd.date_range(end="2025-01-01", periods=800, freq="D", tz="UTC")
    tz_series = pd.Series([10.0 + i / 100.0 for i in range(800)], index=_idx, dtype=float)
    _wire(monkeypatch, fetch=lambda c: {"series": short})
    _wire_rescue(monkeypatch, ms=tz_series)
    r = NS.backfill_to_gs(["X"])["results"][0]
    assert r["source"] == "morningstar(ISIN)" and r["fetched"] == 800
