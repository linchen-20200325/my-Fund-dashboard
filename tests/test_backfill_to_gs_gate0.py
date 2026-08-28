"""Gate 0（2026-08-28）:`backfill_to_gs` 寫進 nav_history 之前先與既有歷史對帳。

**為什麼需要這道閘門(不是儀式,是實際會壞的路)**
每天 20:00 TW 的 `weekly_nav_backfill` 對「持倉 ∪ 選股池」全跑 `backfill_to_gs`。
其中 `_rescue_by_isin` 的採用條件只看「筆數 × 跨度」,**沒有任何幣別條件** ——
同一檔基金的美元 / 歐元 / 避險級別在晨星、Yahoo 都查得到,只要跨度更長就整條換掉。
而 `nav_history` 的去重鍵是 `(code, date)` 且**永不刪除**:
**錯的先寫進去,對的就永遠寫不進來**,下游 1Y 報酬 / Sharpe / σ 全部照錯的算,
畫面上沒有任何警示(§1:錯誤的數字比沒有數字更危險)。

驗證重點:
- 重疊日淨值對不上 → 該檔**擋下**(雲端與本地 cache 皆不寫)+ error 誠實回報,其餘檔照跑
- 重疊日一致(重複下載)/ 零重疊(純新增)→ 照寫,不誤擋
- 讀不到既有歷史 → **fail-closed**:本次不寫雲端 + gs_error,但抓取結果不被覆蓋
- §5 配額:整批**只讀一次** nav_history(逐檔各讀一次會吃光 60 reads/min)
- ⚠️ **這道閘門保護不到什麼**:只比對重疊日期 → 新代碼首次回填零重疊 → verdict 恆為
  clean → 閘門無效。本檔用 `test_gate0_hole_...` 把這個洞**明確測出來**,不假裝沒有。
"""
import pandas as pd
import pytest

import services.nav_history_gs as GS
import services.nav_history_store as NS


def _series(pairs):
    return pd.Series([v for _, v in pairs],
                     index=pd.to_datetime([d for d, _ in pairs]), dtype=float)


def _existing(code, pairs):
    """模擬 nav_history 既有列(`load_points` 的回傳形狀)。"""
    return [{"code": code, "date": d, "nav": v, "fund_name": "", "source": "backfill",
             "recorded_at": ""} for d, v in pairs]


@pytest.fixture
def cache_store(monkeypatch):
    """本地 cache 讀寫改記憶體(測試不碰磁碟),同時可斷言「有沒有被寫」。"""
    store: dict = {}
    monkeypatch.setattr(NS, "_load_cache_series",
                        lambda code: store.get(code, pd.Series(dtype=float)))
    monkeypatch.setattr(NS, "_save_cache_series",
                        lambda code, s: store.__setitem__(code, s))
    return store


def _wire(monkeypatch, *, fetch, existing=None, load=None, reads=None):
    """接上 auto_fetch / is_enabled / load_points / append_points 假件,回收集到的寫入點。"""
    import services.moneydj_fetcher as MF

    monkeypatch.setattr(MF, "auto_fetch_moneydj", lambda code, **kw: fetch(code))
    monkeypatch.setattr(GS, "is_enabled", lambda: True)

    def _default_load(code=None, **kw):
        if reads is not None:
            reads.append(code)
        return list(existing or [])

    monkeypatch.setattr(GS, "load_points", load or _default_load)
    written: list = []

    def _append(points, **kw):
        written.extend(points)
        return {"written": len(points), "skipped": 0}

    monkeypatch.setattr(GS, "append_points", _append)
    return written


# ── 核心:對不上就擋,而且不擋其他檔 ──────────────────────────────────────
def test_gate0_blocks_conflicting_series_but_other_funds_still_written(
        monkeypatch, cache_store):
    """既有是一種幣別、這次抓到另一種 → 該檔擋下;另一檔照寫(§1 不擋整批)。"""
    fds = {
        # 重疊日 2024-01-02 既有 10.00、這次 33.10 → 差 231% ≫ 容差
        "EURUSD": {"series": _series([("2024-01-02", 33.10), ("2024-01-03", 33.20)]),
                   "fund_name": "Fund X"},
        "OK": {"series": _series([("2024-01-02", 20.0)]), "fund_name": "Fund OK"},
    }
    written = _wire(monkeypatch, fetch=lambda c: fds[c],
                    existing=_existing("EURUSD", [("2024-01-02", 10.00)]))
    out = NS.backfill_to_gs(["EURUSD", "OK"])

    _by = {r["code"]: r for r in out["results"]}
    assert _by["EURUSD"]["error"], "重疊日對不上卻放行 → 錯的會永久寫死(去重鍵 code+date)"
    assert "衝突" in _by["EURUSD"]["error"] and "已擋下未寫入" in _by["EURUSD"]["error"]
    assert "2024-01-02" in _by["EURUSD"]["error"], "錯誤訊息要指出是哪一天對不上"
    # 被擋的檔:雲端不寫、**本地 cache 也不寫**(可疑序列不該進任何一層)
    assert not [p for p in written if p["code"] == "EURUSD"]
    assert "EURUSD" not in cache_store
    # 其他檔照跑
    assert _by["OK"]["error"] is None and _by["OK"]["fetched"] == 1
    assert [p["code"] for p in written] == ["OK"]
    assert "OK" in cache_store
    assert out["n_fail"] == 1 and out["n_ok"] == 1


def test_gate0_blocks_currency_swap_through_real_rescue_by_isin(monkeypatch, cache_store):
    """端到端重現紅隊路徑:MoneyDJ 短窗(對的幣別)→ ISIN 救援換到跨度更長的**別的幣別**。

    `_rescue_by_isin` 只比「筆數 × 跨度」,一定會採用長的那條;Gate 0 是最後一道。
    """
    import repositories.fund.sources as SRC
    import repositories.pool_repository as POOL

    _short_usd = _series([("2025-01-02", 10.00), ("2025-01-03", 10.01)])
    # 跨度 > 5 年 + 點數更多 → 必定通過 `_rescue_by_isin` 的採用門檻
    _long_dates = ([f"2018-01-{d:02d}" for d in range(1, 19)]
                   + ["2025-01-02", "2025-01-03"])
    _long_other_ccy = pd.Series([33.0 + i * 0.01 for i in range(len(_long_dates))],
                                index=pd.to_datetime(_long_dates), dtype=float)

    monkeypatch.setattr(POOL, "resolve_isin", lambda code: "LU0000000001")
    monkeypatch.setattr(SRC, "_src_yahoo_finance_nav", lambda code: _long_other_ccy)
    monkeypatch.setattr(SRC, "_src_morningstar_nav",
                        lambda code, fund_name="": pd.Series(dtype=float))
    monkeypatch.setattr(SRC, "_src_cnyes_nav", lambda code: pd.Series(dtype=float))

    written = _wire(monkeypatch, fetch=lambda c: {"series": _short_usd, "fund_name": "F"},
                    existing=_existing("SWAP", [("2025-01-02", 10.00),
                                                ("2025-01-03", 10.01)]))
    out = NS.backfill_to_gs(["SWAP"])
    r = out["results"][0]

    assert r["source"] == "yahoo(ISIN)", "前提沒成立:救援沒換源,這個測試就沒測到東西"
    assert r["error"] and "衝突" in r["error"], "換到別的幣別卻寫進永不刪除的表"
    assert written == [] and "SWAP" not in cache_store


# ── 不誤擋:重複下載 / 純新增 ─────────────────────────────────────────────
def test_gate0_allows_identical_overlap(monkeypatch, cache_store):
    """重疊日數值一致(重複下載)→ 照寫(去重在 append_points 端處理)。"""
    written = _wire(monkeypatch,
                    fetch=lambda c: {"series": _series([("2024-01-02", 10.0),
                                                        ("2024-01-03", 10.1)])},
                    existing=_existing("A", [("2024-01-02", 10.0)]))
    out = NS.backfill_to_gs(["A"])
    assert out["results"][0]["error"] is None
    assert len(written) == 2 and "A" in cache_store


def test_gate0_allows_pure_new_dates(monkeypatch, cache_store):
    """零重疊(純新增,例如每天補最新一筆)→ 照寫。"""
    written = _wire(monkeypatch,
                    fetch=lambda c: {"series": _series([("2024-02-01", 12.0)])},
                    existing=_existing("A", [("2024-01-02", 10.0)]))
    out = NS.backfill_to_gs(["A"])
    assert out["results"][0]["error"] is None and len(written) == 1


def test_gate0_tolerates_rounding_difference(monkeypatch, cache_store):
    """同級別的差異只該來自四捨五入 → 容差內不得誤擋(否則每天的 job 全紅)。"""
    written = _wire(monkeypatch,
                    fetch=lambda c: {"series": _series([("2024-01-02", 10.001)])},
                    existing=_existing("A", [("2024-01-02", 10.0)]))
    assert NS.backfill_to_gs(["A"])["results"][0]["error"] is None
    assert len(written) == 1


# ── fail-closed:讀不到既有歷史就不敢寫 ───────────────────────────────────
def test_gate0_fails_closed_when_existing_history_unreadable(monkeypatch, cache_store):
    """讀不到既有歷史 → **不往無法重建的表盲寫**;但抓取結果不被覆蓋(§1 兩件事分開)。"""
    def _boom(code=None, **kw):
        raise RuntimeError("Sheets 讀取失敗")

    written = _wire(monkeypatch,
                    fetch=lambda c: {"series": _series([("2024-01-02", 10.0)])},
                    load=_boom)
    out = NS.backfill_to_gs(["A"])

    assert written == [], "讀不到既有資料還寫 = 在猜"
    assert out["gs_written"] == 0
    assert out["gs_error"] and "不寫雲端" in out["gs_error"]
    # 抓取本身成功 → 不可歸零(否則 UI 誤報「0 檔抓到」);本地 cache 可重建,照寫
    assert out["n_ok"] == 1 and out["results"][0]["error"] is None
    assert "A" in cache_store


# ── §5 配額:整批只讀一次 ────────────────────────────────────────────────
def test_gate0_reads_existing_history_only_once_for_many_codes(monkeypatch, cache_store):
    """`load_points` 是 `get_all_values()` 讀整張表 —— 逐檔各讀一次會吃光讀取配額。"""
    reads: list = []
    _wire(monkeypatch, fetch=lambda c: {"series": _series([("2024-01-02", 10.0)])},
          existing=_existing("A", [("2024-01-02", 10.0)]), reads=reads)
    NS.backfill_to_gs(["A", "B", "C", "D", "E"])
    assert len(reads) == 1, f"整批只能讀一次,實際讀了 {len(reads)} 次"


# ── 誠實揭露:這道閘門保護不到的洞 ────────────────────────────────────────
def test_gate0_hole_first_backfill_of_a_new_code_is_not_protected(monkeypatch, cache_store):
    """⚠️ **已知且刻意保留的洞,不是 bug** —— 本測試存在是為了不讓後人以為補完了。

    `analyze_backfill_conflict` 只比對**重疊日期**。某個 code **第一次**回填時
    既有歷史是空的 → 零重疊 → verdict 恆為 `"clean"` → **Gate 0 對它完全無效**,
    錯幣別序列一樣寫得進去。Gate 0 保護的是「**已經有歷史的 code**」;
    新加入選股池的標的仍然沒有保護,要靠後續批次(幣別欄 / 拒絕未知幣別)。
    """
    written = _wire(monkeypatch,
                    fetch=lambda c: {"series": _series([("2024-01-02", 33.10)])},
                    existing=[])            # 這檔還沒有任何歷史
    out = NS.backfill_to_gs(["NEWCODE"])
    assert out["results"][0]["error"] is None
    assert len(written) == 1, "若這裡變綠(擋下了)代表洞被補了 → 請更新本測試與註解"


# ── 接線守衛:把閘門拆掉必紅 ──────────────────────────────────────────────
def test_gate0_is_actually_wired_into_backfill_to_gs():
    """**改回舊行為必紅**:閘門必須接在每天在跑的 `backfill_to_gs` 上。

    背景:`analyze_backfill_conflict` 早就存在也早就有測試,但它只接在
    `fundclear_backfill.download_and_store`(production 0 caller)上 ——
    **每天真的在跑的那條路一道護欄都沒有**。這個測試守的就是「有沒有接上」。
    """
    import inspect

    _src = inspect.getsource(NS.backfill_to_gs)
    assert "analyze_backfill_conflict" in _src, "閘門沒接上 backfill_to_gs"
    assert 'verdict") == "conflict"' in _src, "偵測到衝突卻沒有擋下的分支"


# ── 注入路徑本身的契約(§5 配額的實作手段)────────────────────────────────
def test_analyze_accepts_injected_existing_and_does_not_read_again(monkeypatch):
    """批次端已代讀 → `analyze_backfill_conflict` 不得自己再讀一次整張表。"""
    from services import fundclear_backfill as B

    def _boom(code=None, **kw):
        raise AssertionError("注入了 existing_points 還去讀表 = 配額白燒")

    monkeypatch.setattr(GS, "load_points", _boom)
    _r = B.analyze_backfill_conflict(
        "X", [{"code": "X", "nav": 33.0, "nav_date": "2024-01-02"}],
        existing_points=[{"code": "X", "date": "2024-01-02", "nav": 10.0}])
    assert _r["verdict"] == "conflict" and _r["n_conflict"] == 1


def test_analyze_without_injection_still_reads_itself():
    """預設(不注入)行為不變 —— 既有 caller `download_and_store` 不受影響。"""
    import inspect

    from services import fundclear_backfill as B

    _p = inspect.signature(B.analyze_backfill_conflict).parameters["existing_points"]
    assert _p.default is None, "預設必須是「自己去讀」,不可讓漏傳變成靜默略過比對"
