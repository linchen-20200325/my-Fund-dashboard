"""NAV 幣別守門(2026-09-01):**禁止把整條淨值序列換成另一種計價幣別**。

**在防哪一條真實路徑(不是儀式)**
`.github/workflows/weekly_nav_backfill.yml` 每天 12:00 UTC(TW 20:00)跑
`scripts/weekly_nav_backfill.py` → `services.nav_history_store.backfill_to_gs`。
其中的長歷史救援有兩處**整條序列替換**的採用點,在此之前**採用條件只有
「筆數 × 跨度」,一個字都沒提幣別**:

  - L1 `repositories/fund/fund_orchestration.py::_span_extend_insurance_nav`
  - L2 `services/nav_history_store.py::backfill_to_gs::_rescue_by_isin`

而候選來源正好是最會換幣別的兩個:`_src_morningstar_nav` 拿 `currencyId` 跟晨星要
**換算後**的淨值(查不到使用者幣別時死預設 `"USD"`),`_src_yahoo_finance_nav` 打的是
`{secId}.F`(法蘭克福掛牌)。跨度更長 → 整條蓋掉 → 寫進 `nav_history`,而該表去重鍵是
`(code, date)` 且**永不刪除** → 錯的先寫進去、對的永遠寫不進來,下游 1Y 報酬 / Sharpe /
σ / 配息殖利率全部照錯的算,**畫面上不會有任何異狀**(§1:錯誤的數字比沒有數字更危險;
§4.1:TWD vs USD vs 原幣,禁止跨幣別直接混寫)。

驗證重點
- L0 判定器:只有兩邊都是可辨識 ISO 三碼時才敢說 match / mismatch;其餘一律 unknown(§1 不猜)
- L1 provenance:晨星 / Yahoo 抓回來的序列**要宣告自己是哪一種幣別**(先前整個丟掉)
- L2 / L1 採用點:幣別明確不一致 → **拒絕換源 + 誠實記錄**,⛔ 絕不換算、絕不混寫
- **不誤擋**:幣別一致 → 照常換源(長歷史救援不能被這道守門廢掉)
- **已知破口就地釘住**:候選不宣告幣別(如 cnyes)時**仍會換源** —— 這是刻意的權衡,
  不是漏做。釘成測試是為了讓日後任何改動都是**有意識的**,而不是悄悄變嚴或變鬆。
  ⛔ 不要把它讀成「洞只有這一個」——完整已知分類見 `shared/data_quality.py` 該節。
"""
import pandas as pd
import pytest

from shared.data_quality import (
    NAV_CCY_MATCH,
    NAV_CCY_MISMATCH,
    NAV_CCY_UNKNOWN,
    assess_nav_series_swap,
    nav_currency_verdict,
    nav_series_currency,
    normalize_iso_ccy,
)


def _series(pairs, ccy=None):
    s = pd.Series([v for _, v in pairs],
                  index=pd.to_datetime([d for d, _ in pairs]), dtype=float)
    if ccy is not None:
        s.attrs["currency"] = ccy
    return s


def _long(n, end="2025-01-01", start_val=10.0, ccy=None):
    """n 筆日資料(跨度 ≈ n-1 天)。"""
    idx = pd.date_range(end=end, periods=n, freq="D")
    s = pd.Series([start_val + i / 100.0 for i in range(n)], index=idx, dtype=float)
    if ccy is not None:
        s.attrs["currency"] = ccy
    return s


# ══════════════════════════════════════════════════════════════════════════
# L0:判定器本身(shared/data_quality.py)
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("raw,want", [
    ("usd", "USD"), (" twd ", "TWD"), ("EUR", "EUR"),
    ("美元", ""),        # 中文別名是 L2 normalize_ccy 的職責,L0 不猜
    ("USDX", ""),        # 四碼 → 不是 ISO 三碼
    ("US", ""), ("", ""), (None, ""), (123, ""),
])
def test_normalize_iso_ccy_never_guesses(raw, want):
    assert normalize_iso_ccy(raw) == want


def test_nav_series_currency_reads_attrs_and_survives_junk():
    assert nav_series_currency(_series([("2025-01-02", 10.0)], ccy="usd")) == "USD"
    assert nav_series_currency(_series([("2025-01-02", 10.0)])) == ""   # 沒宣告 = 未知
    assert nav_series_currency(None) == ""
    assert nav_series_currency(object()) == ""


@pytest.mark.parametrize("exp,cand,want", [
    ("TWD", "TWD", NAV_CCY_MATCH),
    ("TWD", "USD", NAV_CCY_MISMATCH),
    ("TWD", "", NAV_CCY_UNKNOWN),      # 候選沒宣告 → 不知道 ≠ 不一致
    ("", "USD", NAV_CCY_UNKNOWN),      # 預期不明 → 同上
    ("美元", "USD", NAV_CCY_UNKNOWN),  # 非 ISO 三碼一律未知,不硬解
])
def test_nav_currency_verdict(exp, cand, want):
    assert nav_currency_verdict(exp, cand) == want


def test_assess_swap_blocks_only_on_explicit_mismatch():
    bad = assess_nav_series_swap(expected_ccy="TWD", candidate_ccy="USD",
                                 candidate_source="morningstar(ISIN)",
                                 current_source="moneydj")
    assert bad["safe"] is False and bad["verdict"] == NAV_CCY_MISMATCH
    # 訊息要能讓人一眼看懂「誰對誰」,不是一句「幣別錯誤」
    assert "TWD" in bad["reason"] and "USD" in bad["reason"]
    assert "morningstar(ISIN)" in bad["reason"]

    for ok in (assess_nav_series_swap(expected_ccy="TWD", candidate_ccy="TWD"),
               assess_nav_series_swap(expected_ccy="", candidate_ccy="USD"),
               assess_nav_series_swap(expected_ccy="TWD", candidate_ccy="")):
        assert ok["safe"] is True and ok["reason"] == ""


def test_assess_swap_has_no_conversion_escape_hatch():
    """§4.1/§1:判定器**不得**提供「換算後序列」這種出口 —— 在寫入端偷偷換匯會做出
    一條看起來連續、實際混過兩種幣別的序列,比拒絕替換危險得多。"""
    out = assess_nav_series_swap(expected_ccy="TWD", candidate_ccy="USD")
    assert set(out) == {"verdict", "safe", "expected_ccy", "candidate_ccy", "reason"}
    assert not any("fx" in k or "rate" in k or "convert" in k for k in out)


# ══════════════════════════════════════════════════════════════════════════
# L1 provenance:抓回來的序列要宣告自己是哪一種幣別
# ══════════════════════════════════════════════════════════════════════════
class _FakeUrlResp:
    def __init__(self, payload: bytes):
        self._p = payload

    def read(self):
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_morningstar_series_declares_the_currency_it_asked_for(monkeypatch):
    """晨星是拿 `currencyId` 要**換算後**的淨值 → 序列必須把那個幣別宣告出來。

    不宣告的後果就是本檔開頭那條路徑:下游只比筆數 × 跨度,整條蓋掉別種幣別的序列。
    """
    import json

    import repositories.fund.sources as S

    seen: list = []
    payload = json.dumps({"TimeSeries": {"Security": [{"HistoryDetail": [
        {"EndDate": "2024-01-02", "Value": "10.5"},
        {"EndDate": "2024-01-03", "Value": "10.6"},
    ]}]}}).encode()

    def _fake_urlopen(req, **kw):
        seen.append(getattr(req, "full_url", str(req)))
        return _FakeUrlResp(payload)

    # 選股池填了 TWD → `_src_morningstar_nav` 應該用 TWD 去要,序列也應該宣告 TWD
    monkeypatch.setattr("repositories.pool_repository.resolve_secid",
                        lambda code: ("0PFAKE00001", "TWD"))
    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)

    s = S._src_morningstar_nav("ZZZZ9")
    assert len(s) == 2
    assert "currencyId=TWD" in seen[0], "前提沒成立:沒有用池中幣別去要"
    assert s.attrs.get("currency") == "TWD"


def test_yahoo_series_declares_currency_from_chart_meta(monkeypatch):
    """Yahoo v8 chart 的 `meta.currency` 一直都在,先前**整個丟掉**。"""
    import json

    import repositories.fund.sources as S

    payload = json.dumps({"chart": {"result": [{
        "meta": {"currency": "EUR"},
        "timestamp": [1704153600, 1704240000],
        "indicators": {"quote": [{"close": [10.5, 10.6]}]},
    }]}}).encode()

    monkeypatch.setattr("repositories.pool_repository.resolve_secid",
                        lambda code: ("0PFAKE00001", "USD"))
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, **kw: _FakeUrlResp(payload))

    s = S._src_yahoo_finance_nav("ZZZZ9")
    assert len(s) == 2
    assert s.attrs.get("currency") == "EUR", (
        "`{secId}.F` 是法蘭克福掛牌 —— 幣別不帶出來,下游就會拿歐元序列蓋掉美元序列")


def test_yahoo_missing_meta_currency_is_unknown_not_guessed(monkeypatch):
    """meta 沒給幣別 → 留空(未知),**不准**退回 USD 之類的死預設(§1 不猜)。"""
    import json

    import repositories.fund.sources as S

    payload = json.dumps({"chart": {"result": [{
        "timestamp": [1704153600], "indicators": {"quote": [{"close": [10.5]}]},
    }]}}).encode()
    monkeypatch.setattr("repositories.pool_repository.resolve_secid",
                        lambda code: ("0PFAKE00001", "USD"))
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, **kw: _FakeUrlResp(payload))

    s = S._src_yahoo_finance_nav("ZZZZ9")
    assert s.attrs.get("currency") == "" and nav_series_currency(s) == ""


# ══════════════════════════════════════════════════════════════════════════
# L1 採用點:_span_extend_insurance_nav
# ══════════════════════════════════════════════════════════════════════════
def _wire_l1(monkeypatch, *, ms, pool_ccy=None):
    import repositories.fund.fund_orchestration as O
    import repositories.pool_repository as POOL
    monkeypatch.setattr(O, "_src_morningstar_nav",
                        lambda code, fund_name="": ms)
    monkeypatch.setattr(O, "_src_cnyes_nav", lambda code: pd.Series(dtype=float))
    monkeypatch.setattr(POOL, "resolve_currency", lambda code: pool_ccy)
    return O


def test_span_extend_refuses_currency_swap(monkeypatch, capsys):
    """台幣基金 + 晨星回美元長歷史 → **拒絕換源**,保留原本(正確幣別)的短序列。"""
    O = _wire_l1(monkeypatch, ms=_long(1200, ccy="USD"))
    _short_twd = _long(30, ccy="TWD")

    s, src, span = O._span_extend_insurance_nav(
        "TLZF9", _short_twd, "moneydj_legacy_scrape", fund_name="安聯台幣計價基金")

    assert len(s) == 30 and src == "moneydj_legacy_scrape", (
        "台幣序列被美元序列整條換掉 —— 這正是每天 20:00 的排程會做的事")
    assert 0 < span < 300
    _out = capsys.readouterr().out
    assert "拒絕換源" in _out and "TWD" in _out and "USD" in _out, "§1:拒寫要留下 log"


def test_span_extend_still_adopts_when_currency_matches(monkeypatch):
    """不誤擋:幣別一致 → 長歷史救援照舊生效(這道守門不能把功能廢掉)。"""
    O = _wire_l1(monkeypatch, ms=_long(1200, ccy="TWD"))
    s, src, span = O._span_extend_insurance_nav(
        "TLZF9", _long(30, ccy="TWD"), "moneydj_legacy_scrape",
        fund_name="安聯台幣計價基金")
    assert len(s) == 1200 and src == "morningstar(span-extend)" and span > 300


def test_span_extend_adopts_when_currency_unknown(monkeypatch):
    """**已知破口,刻意釘住**:候選沒宣告幣別 → 仍然換源。

    擋掉會讓「補到 5 年」對所有未宣告幣別的來源(cnyes)整個失效 —— 拿一個確定的
    功能損失換一個不確定的風險。此處選擇照舊採用,由 `backfill_to_gs` 的 Gate 0
    當第二道。⛔ 這**不是**「已經補完了」,只是這個權衡是**有意識**做的。
    """
    O = _wire_l1(monkeypatch, ms=_long(1200))          # 候選無 attrs["currency"]
    s, src, _ = O._span_extend_insurance_nav(
        "TLZF9", _long(30, ccy="TWD"), "moneydj_legacy_scrape",
        fund_name="安聯台幣計價基金")
    assert len(s) == 1200 and src == "morningstar(span-extend)"


# ══════════════════════════════════════════════════════════════════════════
# L2 採用點:backfill_to_gs::_rescue_by_isin(每日排程實際走的那一條)
# ══════════════════════════════════════════════════════════════════════════
@pytest.fixture
def cache_store(monkeypatch):
    """本地 cache 讀寫改記憶體(不碰磁碟),同時可斷言「有沒有被寫」。"""
    import services.nav_history_store as NS
    store: dict = {}
    monkeypatch.setattr(NS, "_load_cache_series",
                        lambda code: store.get(code, pd.Series(dtype=float)))
    monkeypatch.setattr(NS, "_save_cache_series",
                        lambda code, s: store.__setitem__(code, s))
    return store


def _wire_l2(monkeypatch, *, fd, yahoo, pool_ccy=None):
    """接上每日排程實際走的那條鏈的所有外部邊界,回傳「寫進雲端的點」。"""
    import repositories.fund.sources as SRC
    import repositories.pool_repository as POOL
    import services.moneydj_fetcher as MF
    import services.nav_history_gs as GS

    monkeypatch.setattr(MF, "auto_fetch_moneydj", lambda code, **kw: fd)
    monkeypatch.setattr(POOL, "resolve_isin", lambda code: "LU0000000001")
    monkeypatch.setattr(POOL, "resolve_currency", lambda code: pool_ccy)
    monkeypatch.setattr(SRC, "_src_yahoo_finance_nav", lambda code: yahoo)
    monkeypatch.setattr(SRC, "_src_morningstar_nav",
                        lambda code, fund_name="": pd.Series(dtype=float))
    monkeypatch.setattr(SRC, "_src_cnyes_nav", lambda code: pd.Series(dtype=float))
    monkeypatch.setattr(GS, "is_enabled", lambda: True)
    monkeypatch.setattr(GS, "load_points", lambda code=None, **kw: [])
    written: list = []

    def _append(points, **kw):
        written.extend(points)
        return {"written": len(points), "skipped": 0}

    monkeypatch.setattr(GS, "append_points", _append)
    return written


def test_backfill_refuses_currency_swap_and_still_writes_the_right_series(
        monkeypatch, cache_store, capsys):
    """每日排程端到端:台幣短序列 + 美元長候選 → 拒絕換源,**照樣寫入台幣那條**。

    這是本次修復的核心行為:拒絕的代價只是「歷史維持短跨度」,而放行的代價是一條
    混過兩種幣別、且因 `(code, date)` 去重而**永遠改不掉**的 nav_history。
    """
    import services.nav_history_store as NS

    _short_twd = _series([("2024-12-01", 15.10), ("2024-12-30", 15.20)], ccy="TWD")
    written = _wire_l2(
        monkeypatch,
        fd={"series": _short_twd, "fund_name": "安聯台灣智慧", "currency": "TWD"},
        yahoo=_long(1900, ccy="USD"),          # 跨度 > 5 年 → 一定通過筆數/跨度門檻
    )
    out = NS.backfill_to_gs(["ACDD19"])
    r = out["results"][0]

    assert r["source"] == "moneydj", "美元長歷史整條蓋掉台幣序列 → 下游全部算錯"
    assert r["fetched"] == 2
    assert r["ccy_refused"] and "幣別不一致" in r["ccy_refused"]
    assert r["error"] is None and r["blocked"] is False, (
        "拒絕換源 ≠ 整檔擋下:原本正確幣別的那條照樣要寫進去")
    assert [p["nav"] for p in written] == [15.10, 15.20]
    assert "ACDD19" in cache_store
    assert "拒絕 ISIN 救援換源" in capsys.readouterr().err, "§1:拒寫要留下 log"


def test_backfill_aggregates_currency_refusals_for_callers(monkeypatch, cache_store):
    """`n_ccy_refused` 聚合(稽核 🔴 必修):呼叫端要能一眼拿到次數,不必去掃 `results`。

    ⚠️ 它與 `n_blocked` **語意相反**,必須分得開:`n_blocked` 是「整檔沒寫入」,
    本欄是「有寫入(寫的是原幣別那條),只是沒換成更長的候選」。
    只把理由塞進 `results` 而沒有任何聚合／消費者 = 揭露了但沒人看得見(§5)。
    """
    import services.nav_history_store as NS

    _wire_l2(monkeypatch,
             fd={"series": _series([("2024-12-01", 15.1), ("2024-12-30", 15.2)]),
                 "fund_name": "F", "currency": "TWD"},
             yahoo=_long(1900, ccy="USD"))
    out = NS.backfill_to_gs(["ACDD19"])
    assert out["n_ccy_refused"] == 1
    assert out["n_blocked"] == 0 and out["n_fail"] == 0 and out["n_ok"] == 1


def test_backfill_does_not_convert_currency(monkeypatch, cache_store):
    """⛔ 禁止靜默換算:被拒絕之後寫進去的必須是**原始台幣數值**,不是換匯過的。"""
    import services.nav_history_store as NS

    written = _wire_l2(
        monkeypatch,
        fd={"series": _series([("2024-12-02", 15.10)], ccy="TWD"),
            "fund_name": "F", "currency": "TWD"},
        yahoo=_long(1900, ccy="USD"),
    )
    NS.backfill_to_gs(["ACDD19"])
    assert [p["nav"] for p in written] == [15.10]


def test_backfill_uses_pool_currency_when_meta_missing(monkeypatch, cache_store):
    """上游 meta 沒帶幣別 → 退選股池使用者填的幣別(中文別名也要能用)。"""
    import services.nav_history_store as NS

    _wire_l2(monkeypatch,
             fd={"series": _series([("2024-12-01", 15.1), ("2024-12-30", 15.2)]),
                 "fund_name": "F"},
             yahoo=_long(1900, ccy="USD"),
             pool_ccy="台幣")
    r = NS.backfill_to_gs(["ACDD19"])["results"][0]
    assert r["source"] == "moneydj" and r["ccy_refused"]


def test_backfill_still_rescues_when_currency_matches(monkeypatch, cache_store):
    """不誤擋:幣別一致 → ISIN 長歷史救援照舊(user「補到 5 年」的功能不能被廢掉)。"""
    import services.nav_history_store as NS

    _wire_l2(monkeypatch,
             fd={"series": _series([("2024-12-01", 10.0), ("2024-12-30", 10.5)]),
                 "fund_name": "F", "currency": "USD"},
             yahoo=_long(1900, ccy="USD"))
    r = NS.backfill_to_gs(["TLZF9"])["results"][0]
    assert r["source"] == "yahoo(ISIN)" and r["fetched"] == 1900
    assert r["ccy_refused"] is None


def test_backfill_adopts_when_candidate_currency_unknown(monkeypatch, cache_store):
    """**已知破口,刻意釘住**(同 L1 那則):候選沒宣告幣別 → 仍然換源。

    ⛔ 不要把這則測試讀成「這樣是對的」——它釘的是「這個權衡是有意識做的」。
    這一格底下還有 `backfill_to_gs` 的 Gate 0 當第二道(與既有 nav_history 對帳)。
    """
    import services.nav_history_store as NS

    _wire_l2(monkeypatch,
             fd={"series": _series([("2024-12-01", 10.0), ("2024-12-30", 10.5)]),
                 "fund_name": "F", "currency": "TWD"},
             yahoo=_long(1900))                      # 無 attrs["currency"]
    r = NS.backfill_to_gs(["TLZF9"])["results"][0]
    assert r["source"] == "yahoo(ISIN)" and r["ccy_refused"] is None
