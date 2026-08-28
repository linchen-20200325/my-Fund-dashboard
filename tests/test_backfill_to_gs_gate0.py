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
- ⚠️ **這道閘門保護不到什麼**:**開放式描述,不是窮舉**。已知分類見
  `services/nav_history_store.backfill_to_gs` 函式內註解（a~e:零重疊 / code key 不一致 /
  `gs_on=False` / 其餘寫入路徑 / 模式被關掉）。本檔用 `test_gate0_hole_...` 把「零重疊」
  那一項**明確測出來**,不假裝沒有;⛔ **不要**把它讀成「洞只有這一個」——
  2026-08-28 稽核就是因為上一版寫成封閉列舉而抓到另外四項。
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

    ⛔ **本測試涵蓋的是「零重疊」這一項,不是全部的洞。** 2026-08-28 稽核在上一版
    寫成封閉列舉之後,又實測出至少四項(code key 不一致 / `gs_on=False` 時整道閘門
    不跑 / 其餘寫入路徑無閘門 / 模式被關掉)。完整已知分類見
    `services/nav_history_store.backfill_to_gs` 函式內註解 —— 那裡同樣**不是窮舉**。
    """
    written = _wire(monkeypatch,
                    fetch=lambda c: {"series": _series([("2024-01-02", 33.10)])},
                    existing=[])            # 這檔還沒有任何歷史
    out = NS.backfill_to_gs(["NEWCODE"])
    assert out["results"][0]["error"] is None
    assert len(written) == 1, "若這裡變綠(擋下了)代表洞被補了 → 請更新本測試與註解"


def test_gate0_hole_local_cache_still_takes_a_bad_series_when_cloud_is_off(
        monkeypatch, cache_store):
    """⚠️ **已知且刻意保留的第二個洞** —— `gs_on=False` 時整道閘門**根本不跑**。

    2026-08-28 稽核把它寫進「保護不到什麼」的已知分類,但**當時只寫在註解裡、沒有測**。
    一個只存在於註解的行為宣稱,下次重構就會靜默改掉而沒人知道（本 repo 的病史正是
    「宣稱與實況不符活了很久」）—— 故補這一測把它**釘成事實**。

    實際行為:沒有 SA 也沒有 OAuth → `is_enabled()` 為 False → 不讀既有歷史、不判定,
    **可疑序列照樣寫進本地 cache**（`ui/tab_manage.py` 在 `backend_status` 為 `local`
    時按鈕仍可按）。本地 cache 可重建、不是那張永不刪除的表,所以危害小於雲端 ——
    但「小於」不等於「沒有」,不得假裝它有被守住。

    ⛔ 若哪天這裡變綠(擋下了),代表洞被補了 → **請更新本測試與 `backfill_to_gs` 註解**。
    """
    import services.moneydj_fetcher as MF

    monkeypatch.setattr(MF, "auto_fetch_moneydj",
                        lambda code, **kw: {"series": _series([("2024-01-02", 33.10)])})
    monkeypatch.setattr(GS, "is_enabled", lambda: False)      # 雲端沒開

    def _boom(*a, **kw):     # 閘門若真的跑了就會踩到這裡
        raise AssertionError("gs_on=False 不該去讀既有歷史")

    monkeypatch.setattr(GS, "load_points", _boom)
    out = NS.backfill_to_gs(["BAD"])
    _r = out["results"][0]
    assert _r["blocked"] is False and _r["error"] is None, "雲端關閉時閘門不該判定"
    assert out["gs_enabled"] is False and out["gs_written"] == 0
    assert not cache_store["BAD"].empty, (
        "可疑序列沒有進本地 cache —— 行為變了,請更新本測與註解")


# ── 接線守衛:把閘門拆掉必紅 ──────────────────────────────────────────────
def test_gate0_is_actually_wired_into_backfill_to_gs():
    """**改回舊行為必紅**:閘門必須接在每天在跑的 `backfill_to_gs` 上。

    背景:`analyze_backfill_conflict` 早就存在也早就有測試,但它只接在
    `fundclear_backfill.download_and_store`(production 0 caller)上 ——
    **每天真的在跑的那條路一道護欄都沒有**。這個測試守的就是「有沒有接上」。
    """
    import ast
    import inspect

    # 只看**程式碼**,不看註解 —— `ast.unparse(ast.parse(...))` 會把註解丟掉。
    # （踩過:本函式的註解裡就寫著 `== "conflict"` 這個舊字面,純字串比對會誤判。）
    _code = ast.unparse(ast.parse(inspect.getsource(NS.backfill_to_gs)))
    assert "analyze_backfill_conflict" in _code, "閘門沒接上 backfill_to_gs"
    # 2026-08-28:原本守的是 `verdict") == "conflict"`。那個字面**本身就是必修 3 的 bug**
    # （黑名單 → unknown 與日後新增的 verdict 靜默放行）,故改守**白名單**的形狀。
    assert "_GATE0_SAFE_VERDICTS" in _code, "verdict 判斷不是白名單 = fail-open"
    assert "== 'conflict'" not in _code, "退回黑名單判斷 = 必修 3 的 fail-open 復活"
    assert "'blocked'] = True" in _code, "擋下時沒有留下機器可讀的旗標"


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


# ══════════════════════════════════════════════════════════════════════════
# 2026-08-28 兩組獨立稽核的必修項（正確性 + 營運風險）
# 每一條都對應一個「閘門在,但**沒有作用**／有作用但**沒人知道**」的實際失效模式。
# ══════════════════════════════════════════════════════════════════════════


class _FakeWS:
    """最小 gspread worksheet 假件（`get_all_values` + `append_rows`）。"""

    def __init__(self, rows):
        self.rows = [list(r) for r in rows]

    def get_all_values(self):
        return [list(r) for r in self.rows]

    def append_rows(self, rows, **_kw):
        self.rows.extend([list(r) for r in rows])


class _FakeSheet:
    def __init__(self, ws):
        self._ws = ws

    def worksheet(self, _title):
        return self._ws


_HDR = ["code", "date", "nav", "fund_name", "source", "recorded_at"]


# ── 必修 1:既有列是斜線日期時,整道閘門會靜默被繞過 ────────────────────────
def test_gate0_matches_hand_typed_slash_dates(monkeypatch, cache_store):
    """既有列是 user 手填的 `'2024/01/02'`、這次抓到 ISO 同一天 → **必須**判成衝突。

    修之前:`load_points` 回**原始字串**、incoming 是 ISO,兩邊不同尺 →
    dict key 永遠查不中 → 零重疊 → verdict 恆為 `clean` → **錯幣別序列直接放行**。
    而 `append_points` 的 v19.489 註解自陳這種手填斜線列**確實存在**。
    """
    written = _wire(monkeypatch,
                    fetch=lambda c: {"series": _series([("2024-01-02", 33.10)])},
                    existing=_existing("X", [("2024/01/02", 10.00)]))
    out = NS.backfill_to_gs(["X"])
    r = out["results"][0]
    assert r["error"] and "衝突" in r["error"], (
        "既有列是斜線日期就繞過閘門 → 錯幣別序列寫進永不刪除的表")
    assert r["blocked"] is True
    assert written == [] and "X" not in cache_store


def test_load_points_uses_the_same_date_ruler_as_append_points():
    """讀取端與寫入端**同一把尺**（`norm_date_key`）—— 這是必修 1 的根因層。"""
    ws = _FakeWS([_HDR, ["X", "2024/01/02", "10.0", "", "", ""]])
    pts = GS.load_points("X", _sheet=_FakeSheet(ws))
    assert pts[0]["date"] == "2024-01-02", (
        f"讀取端沒有正規化 → 與 append_points 的去重鍵不同尺;實得 {pts[0]['date']!r}")
    # 兩端同尺 = 同一個函式
    assert GS.norm_date_key("2024/01/02") == GS.norm_date_key("2024-01-02") == "2024-01-02"
    # 怪日期（未來日 / 非法日）→ `_norm_date` 回 '' → **退回原字串前 10 碼**,
    # 與 `append_points` 修前的既有行為**逐字相同**:不弱化既有去重、也不靜默丟資料。
    # （這條 fallback 只在既有列之間生效 —— incoming 側的未來日早被 `_clean` /
    #   `_clean_points` 濾掉,不可能走到這裡。）
    assert GS.norm_date_key("2099/12/31") == "2099/12/31"
    assert GS.norm_date_key("2024/02/30") == "2024/02/30"


def test_gate0_end_to_end_through_the_real_load_points_and_append_points(
        monkeypatch, cache_store):
    """**不假 load_points / append_points**,用真的那兩支打同一張假 sheet。

    稽核實測的原始情境:既有列 `'2024/01/02'`(斜線)+ 這次抓到別的幣別三天 →
    修之前 `{'written': 1, 'skipped': 2}`,非重疊那天以錯幣別落地 →
    那張永不刪除的表變成**混幣別序列**,比整條換掉更難發現。
    """
    import services.moneydj_fetcher as MF

    ws = _FakeWS([_HDR, ["X", "2024/01/02", "10.0", "", "", ""]])
    sheet = _FakeSheet(ws)
    monkeypatch.setattr(MF, "auto_fetch_moneydj", lambda code, **kw: {
        "series": _series([("2024-01-02", 33.10), ("2024-01-03", 33.20),
                           ("2024-01-04", 33.30)]), "fund_name": "F"})
    monkeypatch.setattr(GS, "is_enabled", lambda: True)
    monkeypatch.setattr(GS, "_get_sheet", lambda oauth_client=None: sheet)

    out = NS.backfill_to_gs(["X"])
    assert out["results"][0]["blocked"] is True
    assert out["gs_written"] == 0
    # 那張表除了 header 與原本那一列之外,不該多出任何東西
    assert ws.rows == [_HDR, ["X", "2024/01/02", "10.0", "", "", ""]], (
        f"混幣別序列已落地:{ws.rows}")


# ── 必修 2:「讀到但一筆都用不了」被當成「本來就沒有」 ──────────────────────
def test_analyze_returns_unknown_when_existing_rows_are_all_unusable():
    """既有列存在但沒有一筆能解析出 (日期, 淨值) → `unknown`,**不是** `clean`。

    §1:不知道 ≠ 沒有。函式手上明明有 `len(_existing)` 可以分辨。
    """
    from services import fundclear_backfill as B

    _r = B.analyze_backfill_conflict(
        "X", [{"code": "X", "nav": 33.0, "nav_date": "2024-01-02"}],
        existing_points=[{"code": "X", "date": "2024-01-02", "nav": "N/A"},
                         {"code": "X", "date": "2024-01-03", "nav": 0.0},
                         {"code": "X", "nav": 5.0}])            # 缺 date 欄
    assert _r["verdict"] == "unknown", "讀不懂那張表卻宣稱安全"
    assert "3" in str(_r.get("reason")), "要講出讀到幾筆,否則使用者無從判斷"
    # 真的空的（這檔還沒累積過）仍是 clean —— 不可矯枉過正
    assert B.analyze_backfill_conflict(
        "X", [{"code": "X", "nav": 33.0, "nav_date": "2024-01-02"}],
        existing_points=[])["verdict"] == "clean"


def test_gate0_blocks_when_existing_rows_are_all_unusable(monkeypatch, cache_store):
    """必修 2 ✕ 必修 3 串起來:`unknown` 必須真的被擋（否則修了判定也沒用）。"""
    written = _wire(monkeypatch,
                    fetch=lambda c: {"series": _series([("2024-01-02", 33.10)])},
                    existing=[{"code": "X", "date": "2024-01-02", "nav": "壞掉"}])
    out = NS.backfill_to_gs(["X"])
    assert out["results"][0]["blocked"] is True
    assert "unknown" in out["results"][0]["error"]
    assert written == [] and "X" not in cache_store


# ── 必修 3:verdict 判斷是 fail-open ───────────────────────────────────────
def test_gate0_blocks_any_verdict_outside_the_safe_whitelist(monkeypatch, cache_store):
    """**白名單**:只有 clean / duplicate 放行。日後新增的 verdict 不得靜默通過。"""
    import services.fundclear_backfill as B

    monkeypatch.setattr(B, "analyze_backfill_conflict",
                        lambda *a, **k: {"verdict": "some_future_verdict",
                                         "n_existing": 1, "n_overlap": 0,
                                         "n_conflict": 0, "samples": []})
    written = _wire(monkeypatch,
                    fetch=lambda c: {"series": _series([("2024-01-02", 33.10)])},
                    existing=_existing("X", [("2024-01-01", 10.0)]))
    out = NS.backfill_to_gs(["X"])
    assert out["results"][0]["blocked"] is True, (
        "黑名單 `== \"conflict\"` → 任何新 verdict 都靜默放行")
    assert written == []
    assert NS._GATE0_SAFE_VERDICTS == ("clean", "duplicate")


def test_download_and_store_is_also_fail_closed(monkeypatch):
    """另一條 caller（`download_and_store`）同樣是白名單 —— 必修 2 讓 unknown 更常出現,
    留著黑名單等於當場開一個新洞。"""
    from services import fundclear_backfill as B

    monkeypatch.setattr(B, "analyze_backfill_conflict",
                        lambda *a, **k: {"verdict": "unknown", "n_existing": 0,
                                         "n_overlap": 0, "n_conflict": 0,
                                         "samples": [], "reason": "讀不到"})
    monkeypatch.setattr(GS, "append_points",
                        lambda *a, **k: pytest.fail("unknown 還照寫 = fail-open"))
    import pandas as _pd

    import repositories.fundclear_offshore as FC

    _df = _pd.DataFrame({"nav_date": _pd.to_datetime(["2024-01-02"]), "nav": [1.0]})
    monkeypatch.setattr(FC, "get_nav_history", lambda *a, **k: _df)
    _r = B.download_and_store("ORG", "F1", "C1", "X")
    assert _r["ok"] is False and _r["written"] == 0
    assert "verdict" in _r["reason"] and "unknown" in _r["reason"]


# ── 必做 8:關閉開關（kill switch）──────────────────────────────────────────
def test_gate0_mode_defaults_to_enforce(monkeypatch):
    monkeypatch.delenv("NAV_GATE0_MODE", raising=False)
    assert NS._gate0_mode() == "enforce"


def test_gate0_mode_unrecognized_value_falls_back_to_enforce(monkeypatch):
    """打錯字不該靜默變成「沒有護欄」。"""
    monkeypatch.setenv("NAV_GATE0_MODE", "enfoce")       # typo
    assert NS._gate0_mode() == "enforce"


def test_gate0_observe_mode_reports_but_does_not_block(monkeypatch, cache_store):
    """`observe`:照常判定、照常回報,但**不擋** —— 誤擋時的止血 + 先量衝擊面。"""
    monkeypatch.setenv("NAV_GATE0_MODE", "observe")
    written = _wire(monkeypatch,
                    fetch=lambda c: {"series": _series([("2024-01-02", 33.10)])},
                    existing=_existing("X", [("2024-01-02", 10.00)]))
    r = NS.backfill_to_gs(["X"])["results"][0]
    assert r["blocked"] is False and r["error"] is None, "observe 不該擋"
    assert r["gate_observed"] and "衝突" in r["gate_observed"], "observe 仍要留下判定"
    assert "已擋下" not in r["gate_observed"], "沒擋卻寫『已擋下』= 訊息說謊"
    assert len(written) == 1


def test_gate0_off_mode_still_writes_to_the_cloud(monkeypatch, cache_store):
    """`off` 是**刻意不讀**,不是**讀失敗** —— 兩者混為一談會讓 off 順手關掉整個雲端寫入。"""
    monkeypatch.setenv("NAV_GATE0_MODE", "off")

    def _never(code=None, **kw):
        raise AssertionError("off 模式不該去讀既有歷史")

    written = _wire(monkeypatch,
                    fetch=lambda c: {"series": _series([("2024-01-02", 33.10)])},
                    load=_never)
    out = NS.backfill_to_gs(["X"])
    assert out["gate_mode"] == "off"
    assert out["results"][0]["error"] is None and out["gs_error"] is None
    assert len(written) == 1, "off 只該關掉閘門,不該連雲端寫入一起關掉"


# ── 必修 5:結果要分得開「被擋下」與「抓不到」 ─────────────────────────────
def test_blocked_is_a_flag_not_a_chinese_error_string(monkeypatch, cache_store):
    """呼叫端要靠**旗標**分辨,不是比對中文錯誤字串(字串一改就靜默失準)。"""
    fds = {"BAD": {"series": _series([("2024-01-02", 33.10)])},
           "NOFETCH": {"series": None, "error": "MoneyDJ 掛了"}}
    _wire(monkeypatch, fetch=lambda c: fds[c],
          existing=_existing("BAD", [("2024-01-02", 10.00)]))
    out = NS.backfill_to_gs(["BAD", "NOFETCH"])
    _by = {r["code"]: r for r in out["results"]}
    assert _by["BAD"]["blocked"] is True and _by["BAD"]["fetched"] == 1
    assert _by["NOFETCH"]["blocked"] is False and _by["NOFETCH"]["fetched"] == 0
    # n_fail 含兩者;純「抓不到」= n_fail - n_blocked
    assert out["n_fail"] == 2 and out["n_blocked"] == 1


# ── 必修 5:UI 三處說謊,而且指路指向唯一沒有閘門的那條路 ────────────────────
# UI 難做功能單測（Streamlit widget），沿用本 repo 既有做法以**原始碼 drift-lock** 守
# （前例：`tests/test_tab_manage_pool_oauth_v19520.py`）。守的是**形狀**不是文案措辭。
def _tab_manage_src() -> str:
    import pathlib
    return (pathlib.Path(__file__).resolve().parents[1]
            / "ui" / "tab_manage.py").read_text(encoding="utf-8")


def _backfill_fn_ast():
    """`_sec_nav_backfill_auto` 的 AST（只看程式碼,不看註解）。"""
    import ast
    for _n in ast.walk(ast.parse(_tab_manage_src())):
        if isinstance(_n, ast.FunctionDef) and _n.name == "_sec_nav_backfill_auto":
            return _n
    raise AssertionError("找不到 _sec_nav_backfill_auto —— 本測失去意義,請更新")


def test_ui_does_not_send_blocked_funds_to_the_unguarded_manual_csv():
    """「用下方 CSV 手動補」**只能**掛在真的抓不到的檔上。

    手動 CSV 是 `nav_history` 各條寫入路徑中**沒有 Gate 0** 的那一條 ——
    把「疑似抓到錯幣別」的檔導過去,等於教使用者繞過剛剛擋住他的護欄（§1）。
    """
    import ast

    _fn = _backfill_fn_ast()
    _csv_hints = [_n for _n in ast.walk(_fn)
                  if isinstance(_n, ast.Constant) and isinstance(_n.value, str)
                  and "CSV 手動補" in _n.value]
    assert _csv_hints, "找不到那句指引 —— 文案改了就更新本測（守的是形狀不是字）"
    _code = ast.unparse(_fn)
    assert "_n_nofetch" in _code, "指引沒有跟『純抓不到』的計數綁在一起"
    # 舊寫法:`if _res["n_fail"]:` 後直接接 CSV 指引 → 把被擋的檔也算進去
    assert "_res['n_fail']:" not in _code, (
        "又用 n_fail 當『抓不到』—— n_fail 含被 Gate 0 擋下的檔")
    assert "n_blocked" in _code, "UI 沒有把『被擋下』與『抓不到』分開"


def test_ui_marks_blocked_funds_red_not_grey():
    """render_state 五態:『還沒載入/還沒設定』才是 ⬜;**偵測到的真失敗是 🔴**。

    2026-08-28 補強（本測原本守不住它自己宣稱的東西）
    ------------------------------------------------
    舊版只斷言「🔴 出現在 `_sec_nav_backfill_auto` 的**某處**」+「`st.error` 出現在某處」。
    突變實測:把**表格列**的 blocked 分支整段拿掉（被擋的檔退回 `⬜ {error}`）,
    本測**仍然綠燈** —— 因為底下總結那段的 🔴 與 `st.error` 還在,兩個斷言都還找得到字。
    也就是說它守的是「這個字有沒有出現」,不是「**被擋的列是不是紅的**」。
    （`st.error` 那句更弱:檔案裡本來就有一個給 `gs_error` 用的 `st.error`。）

    改法:兩個斷言都**綁在條件上** —— 必須存在「條件提到 blocked / _n_blocked」的分支,
    且該分支**自己**產出 🔴 / 呼叫 st.error。守的仍是形狀不是文案。
    """
    import ast

    _fn = _backfill_fn_ast()

    def _ifs_testing(_pred):
        for _n in ast.walk(_fn):
            if isinstance(_n, ast.If) and _pred(ast.unparse(_n.test)):
                yield _n

    # ⚠️ 逐列的條件是 `r.get("blocked")`,總結的條件是 `_n_blocked` —— 後者的字串**包含**
    #    前者,直接用 `"blocked" in cond` 會讓總結那段冒充逐列那段（本測補強時實測踩到:
    #    把逐列分支整段拿掉仍然綠燈）。故比對前先把 `_n_blocked` 消掉。
    def _row_level(_c):
        return "blocked" in _c.replace("_n_blocked", "")

    # (1) 表格列:被擋下的列必須是 🔴,不是 ⬜（⬜ = 還沒載入,會被讀成「還沒輪到它」）
    assert any("🔴" in ast.unparse(_b) for _n in _ifs_testing(_row_level)
               for _b in _n.body), (
        "沒有任何『以 blocked 為條件』的分支產出 🔴 —— "
        "被擋下是偵測到的資料完整性故障,不得與『還沒載入』共用 ⬜")

    # (2) 總結:有檔被擋下時不得只以 st.success 收尾（綠燈蓋掉紅燈）
    assert any("st.error" in ast.unparse(_b)
               for _n in _ifs_testing(lambda _c: "_n_blocked" in _c)
               for _b in _n.body), (
        "沒有任何『以 _n_blocked 為條件』的分支呼叫 st.error —— "
        "有檔被擋下卻仍綠燈收尾（檔內另有給 gs_error 用的 st.error,不算數）")


def test_ui_hides_the_nav_range_of_a_rejected_series():
    """被擋的檔不得顯示『淨值起迄』—— 那是**被拒絕的那條序列**的區間。

    舊條件是 `if r["date_min"]`（沒有排除 error）→ 使用者會以為那段歷史已經在雲端了
    （§1:錯誤的數字比沒有數字更危險）。
    """
    import ast

    _fn = _backfill_fn_ast()
    _cells = [_n for _n in ast.walk(_fn)
              if isinstance(_n, ast.Dict)
              and any(isinstance(_k, ast.Constant) and _k.value == "淨值起迄"
                      for _k in _n.keys)]
    assert _cells, "找不到『淨值起迄』欄 —— 版面改了就更新本測"
    _expr = [_v for _d in _cells for _k, _v in zip(_d.keys, _d.values)
             if isinstance(_k, ast.Constant) and _k.value == "淨值起迄"][0]
    _src = ast.unparse(_expr)
    assert "error" in _src, f"『淨值起迄』沒有排除 error 的檔:{_src}"
