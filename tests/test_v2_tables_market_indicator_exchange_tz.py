# -*- coding: utf-8 -*-
"""觀測日改以「來源自報的交易所時區」取日（客戶 2026-10-13 裁示）的單元測試（fast lane；不打任何網路）。

- L1 `repositories/macro/yf.py::fetch_yf_close`：回應 `meta.exchangeTimezoneName` 原字串 → `attrs["exchange_tz"]`；
  缺就不放（不填預設值）；純新增 attrs，索引與值不變。以假回應測試。
- L2 `services/v2_tables/market_indicator.py`：`_obs_date(stamp, exchange_tz)` 與 `rows_from_daily_close`
  的新規則（缺／不認得時區整鍵不寫、未收盤以交易所時區判斷、週末根跳過、當地時刻須自洽）。

**fixture 的時間戳與收盤值逐字抄自探測報告**（`origin/probe/fx-obs-date-results` 分支
`results/20261013T185433Z_run38450455092/report.json` 的 `raw_excerpt` 頭尾節錄；本檔不在執行期讀該分支）。
少數標明「合成」的根是為了構造報告裡沒有的情境（例如報告中收盤為 null 的那一根若帶值）。
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from services.v2_tables import market_indicator as mi

# ── 探測報告節錄（Unix 秒, 收盤）─────────────────────────────────────────
# USDTWD=X：exchangeTimezoneName = Europe/London
USD_SUMMER_HEAD = [   # 2024-10，倫敦夏令：每根 UTC 23:00 ＝ 倫敦隔日 00:00
    (1728860400, 32.130001068115234),   # 2024-10-13T23:00Z → 倫敦 10-14（一）
    (1728946800, 32.152000427246094),   # 2024-10-14T23:00Z → 10-15
    (1729033200, 32.17100143432617),    # 2024-10-15T23:00Z → 10-16
    (1729119600, 32.1349983215332),     # 2024-10-16T23:00Z → 10-17
]
USD_DST_EDGE = [      # 夏令結束（2024-10-27）前後
    (1729724400, 32.00400161743164),    # 2024-10-23T23:00Z → 倫敦 10-24（四）
    (1729810800, 31.983800888061523),   # 2024-10-24T23:00Z → 10-25（五）
    (1730073600, 32.06380081176758),    # 2024-10-28T00:00Z → 10-28（一，冬令）
    (1730160000, 32.01380157470703),    # 2024-10-29T00:00Z → 10-29
]
USD_WINTER = [        # 倫敦冬令：每根 UTC 00:00 ＝ 倫敦同日 00:00
    (1730246400, 32.00299835205078),    # 2024-10-30
    (1730332800, 31.86549949645996),    # 2024-10-31
    (1730419200, 31.86280059814453),    # 2024-11-01（五）
    (1730678400, 31.922800064086914),   # 2024-11-04（一）
]
USD_TAIL = [
    (1790895600, 31.88680076599121),    # 2026-10-01T23:00Z → 倫敦 10-02（五）
    (1791154800, 31.834400177001953),   # 2026-10-04T23:00Z → 10-05（一）；舊規則會算成週日 10-04
    (1791241200, 31.751399993896484),   # → 10-06
    (1791327600, 31.776899337768555),   # → 10-07
    (1791414000, 31.84830093383789),    # → 10-08
    (1791500400, 31.925399780273438),   # 2026-10-08T23:00Z → 10-09（五）
]
USD_TODAY_LONDON = 1791846000   # 2026-10-12T23:00Z ＝ 倫敦 10-13 00:00（報告中收盤為 null）
USD_INTRADAY = (1791917670, 32.14500045776367)   # 2026-10-13T18:54:30Z（盤中，＝ regularMarketTime）
USD_FETCHED = "2026-10-13T18:54:31.379935+00:00"

# ^VIX：exchangeTimezoneName = America/Chicago；夏令 UTC 07:00、冬令 UTC 08:00，當地都是 02:00
VIX_DST_EDGE = [
    (1730358000, 23.15999984741211),    # 2024-10-31T07:00Z（CDT 02:00）
    (1730444400, 21.8799991607666),     # 2024-11-01T07:00Z
    (1730707200, 21.979999542236328),   # 2024-11-04T08:00Z（CST 02:00）
    (1730793600, 20.489999771118164),   # 2024-11-05T08:00Z
]
VIX_TAIL = [
    (1791442800, 15.40999984741211),    # 2026-10-08T07:00Z
    (1791529200, 14.84000015258789),    # 2026-10-09T07:00Z
    (1791788400, 15.210000038146973),   # 2026-10-12T07:00Z
    (1791874800, 15.479999542236328),   # 2026-10-13T07:00Z（取得當天）
]
VIX_FETCHED = "2026-10-13T18:54:31.760243+00:00"

LONDON = "Europe/London"
CHICAGO = "America/Chicago"


def _series(bars, *, fetched_at=USD_FETCHED, exchange_tz=LONDON, ticker="USDTWD=X"):
    """建法照抄 L1：`pd.to_datetime(秒, unit="s")`（不帶時區＝世界協調時間）；attrs 同 L1。"""
    s = pd.Series([c for _t, c in bars], index=pd.to_datetime([t for t, _c in bars], unit="s"),
                  dtype=float, name=ticker)
    s.attrs["source"] = f"Yahoo:{ticker}"
    s.attrs["fetched_at"] = fetched_at
    if exchange_tz is not None:
        s.attrs["exchange_tz"] = exchange_tz
    return s


def _rows(series, key="fx_twd_per_usd"):
    return mi.rows_from_daily_close(key, series, None, value_unit="新臺幣／美元")


def _legacy_utc_day(sec) -> str:
    """舊規則（2026-10-13 前）：世界協調時間取日期。只用來在測試裡對照新舊差異。"""
    return pd.to_datetime(sec, unit="s").date().isoformat()


# ═══════════════════════ L2：_obs_date ═══════════════════════


def test_obs_date_夏令UTC23點_取倫敦隔日():
    assert mi._obs_date(pd.to_datetime(1728860400, unit="s"), LONDON) == "2024-10-14"
    assert _legacy_utc_day(1728860400) == "2024-10-13"   # 舊規則早一天


def test_obs_date_冬令UTC0點_取倫敦同日():
    assert mi._obs_date(pd.to_datetime(1730246400, unit="s"), LONDON) == "2024-10-30"


def test_obs_date_帶時區的時間戳直接換算_不帶時區視為UTC():
    aware = pd.Timestamp("2024-10-14 07:00", tz="Asia/Taipei")   # ＝ UTC 10-13 23:00
    assert mi._obs_date(aware, LONDON) == "2024-10-14"
    assert mi._obs_date(pd.Timestamp("2024-10-13 23:00"), LONDON) == "2024-10-14"


@pytest.mark.parametrize("bad", [None, "", "Mars/Olympus_Mons", "../etc/passwd", 123])
def test_obs_date_認不得的時區_當場炸_不退回UTC(bad):
    with pytest.raises(ValueError):
        mi._obs_date(pd.Timestamp("2024-10-13 23:00"), bad)


# ═══════════════════════ L2：rows_from_daily_close ═══════════════════════


def test_夏令_UTC23點各根取倫敦隔日_無週末():
    rows, err, skipped = _rows(_series(USD_SUMMER_HEAD))
    assert err is None and skipped == []
    assert [r["obs_date"] for r in rows] == ["2024-10-14", "2024-10-15", "2024-10-16", "2024-10-17"]
    assert [r["release_date"] for r in rows] == [r["obs_date"] for r in rows]   # Q3(a)
    assert [r["value_num"] for r in rows] == [c for _t, c in USD_SUMMER_HEAD]
    assert all(r["fetched_at"] == USD_FETCHED for r in rows)


def test_冬令_UTC0點各根取倫敦同日():
    rows, _err, skipped = _rows(_series(USD_WINTER))
    assert skipped == []
    assert [r["obs_date"] for r in rows] == ["2024-10-30", "2024-10-31", "2024-11-01", "2024-11-04"]


def test_跨夏令結束_當地時刻都是00點_自洽_週五不缺():
    rows, _err, skipped = _rows(_series(USD_DST_EDGE))
    assert skipped == []
    assert [r["obs_date"] for r in rows] == ["2024-10-24", "2024-10-25", "2024-10-28", "2024-10-29"]
    assert date.fromisoformat(rows[1]["obs_date"]).weekday() == 4   # 週五在
    # 舊規則：10-24T23:00Z 會算成 10-24（四），週五 10-25 消失
    assert _legacy_utc_day(USD_DST_EDGE[1][0]) == "2024-10-24"


def test_尾段真實資料_新規則無週日_週五在_盤中根不寫():
    rows, err, skipped = _rows(_series(USD_TAIL + [USD_INTRADAY]))
    assert err is None
    obs = [r["obs_date"] for r in rows]
    assert obs == ["2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09"]
    assert all(date.fromisoformat(d).weekday() < 5 for d in obs)
    assert skipped == ["觀測日不早於取得日（2026-10-13，交易所時區 Europe/London）1 筆不寫"]
    # 舊規則下同一批會出現週日 10-04
    assert _legacy_utc_day(USD_TAIL[1][0]) == "2026-10-04"


def test_VIX型_芝加哥當地02點_跨夏冬令自洽_取日與UTC相同():
    rows, _err, skipped = _rows(_series(VIX_DST_EDGE, fetched_at=VIX_FETCHED, exchange_tz=CHICAGO,
                                        ticker="^VIX"), key="vol_index")
    assert skipped == []
    assert [r["obs_date"] for r in rows] == ["2024-10-31", "2024-11-01", "2024-11-04", "2024-11-05"]
    assert [r["obs_date"] for r in rows] == [_legacy_utc_day(t) for t, _c in VIX_DST_EDGE]


def test_VIX型_取得當天那根不寫():
    rows, _err, skipped = _rows(_series(VIX_TAIL, fetched_at=VIX_FETCHED, exchange_tz=CHICAGO,
                                        ticker="^VIX"), key="vol_index")
    assert [r["obs_date"] for r in rows] == ["2026-10-08", "2026-10-09", "2026-10-12"]
    assert skipped == ["觀測日不早於取得日（2026-10-13，交易所時區 America/Chicago）1 筆不寫"]


def test_取得時間換成交易所時區再比_UTC已過午夜但芝加哥還是當天():
    """取得於 2026-10-14T03:00Z ＝ 芝加哥 10-13 22:00 → 10-13 那根仍算「不早於取得日」，不寫。
    （舊規則以 UTC 日 10-14 比，會寫。新規則較保守，照客戶裁示以同一交易所時區比。）"""
    rows, _err, skipped = _rows(_series(VIX_TAIL, fetched_at="2026-10-14T03:00:00+00:00",
                                        exchange_tz=CHICAGO, ticker="^VIX"), key="vol_index")
    assert [r["obs_date"] for r in rows] == ["2026-10-08", "2026-10-09", "2026-10-12"]
    assert skipped == ["觀測日不早於取得日（2026-10-13，交易所時區 America/Chicago）1 筆不寫"]


def test_舊規則漏洞_倫敦當天那根UTC為昨天23點_新規則正確排除():
    """報告中 `2026-10-12T23:00Z` 那根（＝倫敦 10-13 00:00，交易進行中）收盤為 null；**合成**它帶值的情形。
    舊規則取 UTC 日 10-12 < 取得日 10-13 → 會把盤中值當成 10-12 的收盤寫進去（日期也錯）；
    新規則取倫敦日 10-13，不早於倫敦取得日 10-13 → 不寫。"""
    today = (USD_TODAY_LONDON, 32.1)   # 合成：報告原值為 null
    rows, _err, skipped = _rows(_series(USD_TAIL + [today]))
    assert [r["obs_date"] for r in rows][-1] == "2026-10-09"
    assert "2026-10-12" not in [r["obs_date"] for r in rows]
    assert 32.1 not in [r["value_num"] for r in rows]
    assert skipped == ["觀測日不早於取得日（2026-10-13，交易所時區 Europe/London）1 筆不寫"]
    assert _legacy_utc_day(USD_TODAY_LONDON) == "2026-10-12"   # 舊規則的錯位


def test_倫敦已過午夜UTC還沒_前一個倫敦日成為已收盤():
    """取得於 2026-10-13T23:30Z ＝ 倫敦 10-14 00:30：倫敦 10-13 那根（UTC 10-12 23:00）已收盤 → 以 10-13 寫入；
    倫敦 10-14 那根（UTC 10-13 23:00，合成）不寫。"""
    tomorrow = (USD_TODAY_LONDON + 86400, 32.2)   # 合成：2026-10-13T23:00Z ＝ 倫敦 10-14 00:00
    rows, _err, skipped = _rows(_series(USD_TAIL + [(USD_TODAY_LONDON, 32.1), tomorrow],
                                        fetched_at="2026-10-13T23:30:00+00:00"))
    assert [(r["obs_date"], r["value_num"]) for r in rows][-1] == ("2026-10-13", 32.1)
    assert skipped == ["觀測日不早於取得日（2026-10-14，交易所時區 Europe/London）1 筆不寫"]


def test_缺交易所時區_整批不寫_不退回UTC():
    rows, err, skipped = _rows(_series(USD_SUMMER_HEAD, exchange_tz=None))
    assert rows == [] and err is None
    assert skipped == ["來源未提供交易所時區（attrs['exchange_tz']），不推定，4 筆全部不寫"]


def test_交易所時區為空字串_同缺():
    rows, _err, skipped = _rows(_series(USD_SUMMER_HEAD, exchange_tz=""))
    assert rows == [] and "來源未提供交易所時區" in skipped[0]


@pytest.mark.parametrize("bad", ["Mars/Olympus_Mons", "../etc/passwd", "europe/london ", 123])
def test_不認得的交易所時區_整批不寫(bad):
    rows, err, skipped = _rows(_series(USD_SUMMER_HEAD, exchange_tz=bad))
    assert rows == [] and err is None
    assert len(skipped) == 1 and "無法辨識" in skipped[0] and repr(bad) in skipped[0]


def test_週末根跳過並計數():
    sat = (1790982000, 31.9)   # 合成：2026-10-02T23:00Z ＝ 倫敦 10-03（六）00:00
    rows, _err, skipped = _rows(_series(USD_TAIL[:1] + [sat] + USD_TAIL[1:]))
    assert "2026-10-03" not in [r["obs_date"] for r in rows]
    assert len(rows) == len(USD_TAIL)
    assert skipped == ["觀測日（交易所時區 Europe/London）為星期六或星期日 1 筆不寫"]


def test_當地時刻與多數不一致的根跳過並計數():
    odd = (1791207000, 15.0)   # 合成：2026-10-05T13:30Z ＝ 芝加哥 08:30（其餘都是 02:00）
    bars = VIX_TAIL[:1] + [odd] + VIX_TAIL[1:]
    bars.sort()
    rows, _err, skipped = _rows(_series(bars, fetched_at=VIX_FETCHED, exchange_tz=CHICAGO, ticker="^VIX"),
                                key="vol_index")
    assert "2026-10-05" not in [r["obs_date"] for r in rows]
    assert [r["obs_date"] for r in rows] == ["2026-10-08", "2026-10-09", "2026-10-12"]
    assert "當地時刻與同鍵已收盤根的基準 02:00:00（交易所時區 America/Chicago）不一致 1 筆不寫" in skipped


def test_已收盤根的當地時刻沒有過半數_全部不寫():
    bars = [(1791442800, 15.4), (1791547200, 14.8)]   # 合成：芝加哥 02:00 與 07:00 各一根
    rows, _err, skipped = _rows(_series(bars, fetched_at=VIX_FETCHED, exchange_tz=CHICAGO, ticker="^VIX"),
                                key="vol_index")
    assert rows == []
    assert len(skipped) == 1 and "沒有過半數一致的值" in skipped[0] and "2 筆不寫" in skipped[0]


def test_同日重複仍整天不寫():
    dup = (USD_TAIL[-1][0] + 3600, 31.93)   # 合成：倫敦 10-09 01:00，與 10-09 00:00 同日
    rows, _err, skipped = _rows(_series(USD_TAIL + [dup]))
    assert "2026-10-09" not in [r["obs_date"] for r in rows]
    assert "同一觀測日重複 2 筆不寫" in skipped


def test_開閘時_build_fx_indicator_table套新規則(monkeypatch):
    monkeypatch.setattr(mi, "FX_OBS_DATE_RULE_VERIFIED", True)
    s = _series(USD_TAIL + [USD_INTRADAY], ticker="JPYTWD=X")
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", lambda ticker, *a, **k: (s, None))
    out = mi.build_fx_indicator_table(["JPY"])
    assert [r["obs_date"] for r in out["rows"]][0] == "2026-10-02"
    assert out["fetched"] == {"fx_twd_per_jpy": 7}


def test_閘門仍為False():
    assert mi.FX_OBS_DATE_RULE_VERIFIED is False


# ═══════════════════════ L1：fetch_yf_close 帶出交易所時區 ═══════════════════════


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def _payload(meta):
    result = {"timestamp": [t for t, _c in USD_SUMMER_HEAD],
              "indicators": {"quote": [{"close": [c for _t, c in USD_SUMMER_HEAD]}]}}
    if meta is not ...:
        result["meta"] = meta
    return {"chart": {"result": [result], "error": None}}


@pytest.fixture
def yf_mod():
    from repositories.macro import yf
    yf.fetch_yf_close.cache_clear()
    yield yf
    yf.fetch_yf_close.cache_clear()


def _fetch(yf_mod, monkeypatch, meta):
    yf_mod.fetch_yf_close.cache_clear()
    monkeypatch.setattr(yf_mod, "fetch_url", lambda *a, **k: _Resp(_payload(meta)))
    return yf_mod.fetch_yf_close_with_error("USDTWD=X")


def test_L1_回應帶交易所時區_原字串放進attrs_索引與值不變(yf_mod, monkeypatch):
    s, err = _fetch(yf_mod, monkeypatch, {"exchangeTimezoneName": LONDON, "gmtoffset": 3600})
    base, base_err = _fetch(yf_mod, monkeypatch, ...)   # 沒有 meta 的同一份回應
    assert err is None and base_err is None
    assert s.attrs["exchange_tz"] == LONDON and yf_mod.EXCHANGE_TZ_ATTR == "exchange_tz"
    assert "exchange_tz" not in base.attrs
    pd.testing.assert_series_equal(s, base)   # 索引、值、名稱、dtype 全同
    assert {k: v for k, v in s.attrs.items() if k not in ("exchange_tz", "fetched_at")} == \
        {k: v for k, v in base.attrs.items() if k != "fetched_at"}
    assert list(s.index) == list(pd.to_datetime([t for t, _c in USD_SUMMER_HEAD], unit="s"))


def test_L1_不驗時區名稱_原樣交出(yf_mod, monkeypatch):
    s, err = _fetch(yf_mod, monkeypatch, {"exchangeTimezoneName": "Mars/Olympus_Mons"})
    assert err is None and s.attrs["exchange_tz"] == "Mars/Olympus_Mons"


@pytest.mark.parametrize("meta", [{}, {"exchangeTimezoneName": ""}, {"exchangeTimezoneName": None},
                                  {"exchangeTimezoneName": 3600}, ["not", "a", "dict"], None])
def test_L1_缺或形狀不對_不放這個鍵_不變成解析失敗(yf_mod, monkeypatch, meta):
    s, err = _fetch(yf_mod, monkeypatch, meta)
    assert err is None and len(s) == len(USD_SUMMER_HEAD)
    assert "exchange_tz" not in s.attrs


def test_L1_到L2_端到端_夏令取倫敦隔日(yf_mod, monkeypatch):
    s, err = _fetch(yf_mod, monkeypatch, {"exchangeTimezoneName": LONDON})
    rows, row_err, skipped = mi.rows_from_daily_close("fx_twd_per_usd", s, err, value_unit="新臺幣／美元")
    assert row_err is None and skipped == []
    assert [r["obs_date"] for r in rows] == ["2024-10-14", "2024-10-15", "2024-10-16", "2024-10-17"]
