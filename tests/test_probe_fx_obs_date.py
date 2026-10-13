"""tests/test_probe_fx_obs_date.py — `scripts/probe_fx_obs_date.py` 的分析函式（手寫假回應，不連網）。

探測腳本只讀：它取 Yahoo 日線、用**正式那一條** `_obs_date` 算觀測日，再把分布寫成報告。
本檔只驗分析是否算對，不驗 Yahoo 實際長什麼樣（那正是探測要量的東西）。

時間戳都由 `datetime(..., tzinfo=UTC)` 算出，不手寫 Unix 秒，免得例子本身算錯。
"""
from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "probe_fx_obs_date.py"
_spec = importlib.util.spec_from_file_location("probe_fx_obs_date", _SCRIPT)
probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probe)


def _sec(y, m, d, hh=0, mm=0) -> int:
    return int(datetime(y, m, d, hh, mm, tzinfo=timezone.utc).timestamp())


def _payload(timestamps, closes=None, meta=None):
    closes = closes if closes is not None else [30.0 + i * 0.01 for i in range(len(timestamps))]
    return {"chart": {"result": [{
        "meta": meta if meta is not None else {
            "exchangeTimezoneName": "Europe/London", "gmtoffset": 3600,
            "regularMarketTime": timestamps[-1] if timestamps else None,
        },
        "timestamp": timestamps,
        "indicators": {"quote": [{"close": closes}]},
    }], "error": None}}


@pytest.fixture(scope="module")
def obs_fn():
    """正式規則（`market_indicator._obs_date`），確認腳本借用的真的是那一條。"""
    return probe.production_obs_date_of_epoch()


# ── 觀測日規則：借用正式那一條，且探測不改閘門 ──────────────────────────

def test_借用的是正式規則_23點UTC取當天(obs_fn):
    from services.v2_tables import market_indicator as mi
    sec = _sec(2026, 9, 23, 23, 0)
    assert obs_fn(sec) == "2026-09-23"
    assert obs_fn(sec) == mi._obs_date(datetime(2026, 9, 23, 23, 0))
    assert mi.FX_OBS_DATE_RULE_VERIFIED is False  # 探測只讀，不碰閘門


# ── 星期分布 ─────────────────────────────────────────────

def test_星期分布_週日23點UTC會被算成週日(obs_fn):
    # 2026-07-05 是週日；夏令倫敦 23:00 UTC ＝ 週一 00:00（以倫敦午夜為界時代表週一那根）
    ts = [_sec(2026, 7, 5, 23), _sec(2026, 7, 6, 23), _sec(2026, 7, 7, 23)]
    out = probe.weekday_distribution(ts, obs_fn)
    assert out["counts"]["Sun"] == 1
    assert out["counts"]["Mon"] == 1 and out["counts"]["Tue"] == 1
    assert out["weekend_count"] == 1
    assert out["weekend_examples"][0]["obs_date"] == "2026-07-05"
    assert out["weekend_examples"][0]["weekday"] == "Sun"


def test_缺週五_只看中間的週_頭尾兩週不計(obs_fn):
    # W1（2026-01-05 週一起）：只有週一 → 頭週，不計
    # W2：週一～週四，缺週五 → 計入
    # W3：週一～週五齊 → 不缺
    # W4：只有週一 → 尾週，不計
    ts = [_sec(2026, 1, 5, 12)]
    ts += [_sec(2026, 1, d, 12) for d in (12, 13, 14, 15)]
    ts += [_sec(2026, 1, d, 12) for d in (19, 20, 21, 22, 23)]
    ts += [_sec(2026, 1, 26, 12)]
    out = probe.weekday_distribution(ts, obs_fn)
    assert out["iso_weeks_considered"] == 2
    assert out["iso_weeks_missing_friday"] == ["2026-W03"]
    assert out["iso_weeks_missing_friday_count"] == 1
    assert out["weekend_count"] == 0


def test_同一觀測日兩根_算重複(obs_fn):
    ts = [_sec(2026, 3, 2, 0, 0), _sec(2026, 3, 2, 23, 0), _sec(2026, 3, 3, 23, 0)]
    out = probe.weekday_distribution(ts, obs_fn)
    assert out["duplicate_obs_date_count"] == 1
    assert out["duplicate_obs_date_examples"][0]["obs_date"] == "2026-03-02"
    assert len(out["duplicate_obs_date_examples"][0]["timestamps"]) == 2


# ── 時分分布（夏令／冬令分組） ──────────────────────────────

def test_時分分布_依倫敦夏令冬令分組():
    summer = _sec(2026, 7, 6, 23, 0)    # 倫敦 BST
    winter = _sec(2026, 1, 6, 0, 0)     # 倫敦 GMT
    out = probe.utc_hhmm_distribution([summer, winter], ("Europe/London",))
    assert out["all"] == {"00:00": 1, "23:00": 1}
    assert out["by_zone"]["Europe/London"] == {"dst": {"23:00": 1}, "std": {"00:00": 1}}


def test_時分分布_倫敦與紐約夏令切換日不同_分開計():
    # 2026-03-10：紐約已進夏令（3/8 起），倫敦尚未（3/29 起）
    sec = _sec(2026, 3, 10, 0, 0)
    out = probe.utc_hhmm_distribution([sec], ("Europe/London", "America/New_York"))
    assert out["by_zone"]["Europe/London"]["std"] == {"00:00": 1}
    assert out["by_zone"]["America/New_York"]["dst"] == {"00:00": 1}


# ── 現行規則 vs 當地日期 ───────────────────────────────────

def test_當地日期不一致_台北與倫敦各自計(obs_fn):
    sec = _sec(2026, 9, 23, 23, 0)   # 台北 09-24 07:00；倫敦（BST）09-24 00:00
    noon = _sec(2026, 9, 23, 12, 0)  # 三地都還是 09-23
    out = probe.local_date_mismatch([sec, noon], obs_fn, ("Asia/Taipei", "Europe/London", "America/New_York"))
    assert out["Asia/Taipei"]["mismatch_count"] == 1
    assert out["Asia/Taipei"]["examples"][0]["local_date"] == "2026-09-24"
    assert out["Europe/London"]["mismatch_count"] == 1
    assert out["America/New_York"]["mismatch_count"] == 0
    assert out["Asia/Taipei"]["total"] == 2


# ── 最後一根比對 ────────────────────────────────────────────

def test_最後一根_等於regularMarketTime():
    ts = [_sec(2026, 9, 22, 23), _sec(2026, 9, 23, 14, 7)]
    out = probe.last_bar_check(ts, {"regularMarketTime": ts[-1]})
    assert out["equal"] is True and out["diff_sec"] == 0


def test_最後一根_不等於regularMarketTime_回差秒():
    ts = [_sec(2026, 9, 22, 23), _sec(2026, 9, 23, 23)]
    rmt = ts[-1] + 3600
    out = probe.last_bar_check(ts, {"regularMarketTime": rmt})
    assert out["equal"] is False and out["diff_sec"] == 3600


def test_最後一根_meta缺regularMarketTime_不當成相等():
    out = probe.last_bar_check([_sec(2026, 9, 23, 23)], {})
    assert out["equal"] is False and out["diff_sec"] is None


# ── 解析與節錄 ──────────────────────────────────────────────

def test_解析_chart_error_當場報出原因():
    with pytest.raises(ValueError, match="chart.error"):
        probe.extract_chart({"chart": {"result": None,
                                       "error": {"code": "Not Found", "description": "No data found"}}})


def test_解析_時間戳與收盤長度不一致_報錯():
    p = _payload([_sec(2026, 9, 22), _sec(2026, 9, 23)], closes=[1.0])
    with pytest.raises(ValueError, match="長度不一致"):
        probe.extract_chart(p)


def test_節錄_頭尾各30根():
    ts = [_sec(2026, 1, 1) + i * 86400 for i in range(100)]
    out = probe.excerpt(ts, list(range(100)))
    assert out["total"] == 100
    assert len(out["head"]) == 30 and len(out["tail"]) == 30
    assert out["head"][0]["close"] == 0 and out["tail"][-1]["close"] == 99


def test_analyze_彙整_交易所時區納入分組(obs_fn):
    ts = [_sec(2026, 7, 6, 23), _sec(2026, 7, 7, 23)]
    meta = {"exchangeTimezoneName": "Europe/London", "gmtoffset": 3600,
            "regularMarketTime": ts[-1], "currentTradingPeriod": {"regular": {"timezone": "BST"}}}
    out = probe.analyze(_payload(ts, meta=meta), obs_fn)
    assert out["bar_count"] == 2
    assert out["meta_summary"]["currentTradingPeriod"] == {"regular": {"timezone": "BST"}}
    assert set(out["utc_hhmm"]["by_zone"]) == {"Europe/London", "America/New_York"}
    assert "Asia/Taipei" in out["obs_date_vs_local_date"]
    assert out["last_bar"]["equal"] is True


# ── 遮蔽 ────────────────────────────────────────────────────

def test_遮蔽_查詢字串與代理帳密():
    raw = ("ProxyError http://user:secret@nas.example:3128 "
           "https://query1.finance.yahoo.com/v8/finance/chart/X?interval=1d&range=2y end")
    out = probe.mask_text(raw)
    assert "secret" not in out and "user:" not in out
    assert "interval=1d" not in out
    assert "http://***@nas.example:3128" in out
    assert "chart/X?***" in out


def test_遮蔽_明列的秘密字面值():
    assert probe.mask_text("boom tok123 boom", secrets=("tok123",)) == "boom *** boom"


# ── 端到端（假 fetcher，不連網） ─────────────────────────────

class _Resp:
    def __init__(self, payload):
        self._p = payload
        self.content = json.dumps(payload).encode()

    def json(self):
        return self._p


def test_main_寫出報告_失敗原文照錄並遮蔽(tmp_path, monkeypatch, obs_fn):
    monkeypatch.setenv("PROXY_URL", "http://u:pw@nas:3128")
    ts = [_sec(2026, 7, 6, 23), _sec(2026, 7, 7, 23)]
    calls = []

    def fake_fetch(url, params=None, timeout=None, backoff_on_429=None):
        calls.append((url, params, timeout, backoff_on_429))
        if url.endswith("/^VIX"):
            print("[proxy] 未預期狀態碼 500 (attempt 1/3): https://q/x?k=v | body=http://u:pw@nas:3128")
            return None
        return _Resp(_payload(ts))

    out = tmp_path / "r.json"
    rc = probe.main(["--tickers", "USDTWD=X,EURTWD=X", "--out", str(out)],
                    fetcher=fake_fetch, pop_fail_kind=lambda: "server_error", obs_date_fn=obs_fn)
    assert rc == 0
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert list(rep["tickers"]) == ["USDTWD=X", "^VIX", "EURTWD=X"]
    assert rep["tickers"]["USDTWD=X"]["ok"] is True
    vix = rep["tickers"]["^VIX"]
    assert vix["ok"] is False and "server_error" in vix["error"]
    text = out.read_text(encoding="utf-8")
    assert "u:pw@" not in text and "k=v" not in text
    assert rep["proxy_env_set"] is True
    assert rep["fx_obs_date_rule_verified_at_run"] is False
    # 參數與正式 `fetch_yf_close` 相同
    assert all(c[1] == {"interval": "1d", "range": "2y"} and c[2] == 15 and c[3] is False
               for c in calls)


def test_main_主要代號失敗_退出碼1但報告仍寫出(tmp_path, obs_fn):
    out = tmp_path / "r.json"
    rc = probe.main(["--tickers", "USDTWD=X", "--out", str(out)],
                    fetcher=lambda *a, **k: None, pop_fail_kind=lambda: "", obs_date_fn=obs_fn)
    assert rc == 1
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert rep["tickers"]["USDTWD=X"]["ok"] is False
