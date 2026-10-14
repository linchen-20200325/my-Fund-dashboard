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


LON_NC = "觀測日不早於取得日（界線 {d}：取得時刻的世界協調時間日期與交易所時區 Europe/London 日期取較晚者）{n} 筆不寫"
CHI_NC = "觀測日不早於取得日（界線 {d}：取得時刻的世界協調時間日期與交易所時區 America/Chicago 日期取較晚者）{n} 筆不寫"


def _rows(series, key="fx_twd_per_usd", obs_date_rule=mi.OBS_DATE_SAME_DAY):
    """~~`rows_from_daily_close(key, series, None, value_unit=…)`~~ → 2026-10-14 起 `obs_date_rule` 必填
    （客戶裁示匯率採「前一交易日收盤」語意；有意識的更正，不是漏刪）。

    本檔驗的是**日 K 日期 D 怎麼取**（交易所時區取日、未收盤、週末、過半數基準），預設以當日語意
    （`OBS_DATE_SAME_DAY`，觀測日＝D）跑，鍵名沿用 `fx_twd_per_usd` 只是為了訊息字面不變；
    外匯語意（觀測日＝D 的前一個平日）另見 tests/test_v2_tables_market_indicator_fx_prev_day.py。"""
    return mi.rows_from_daily_close(key, series, None, value_unit="新臺幣／美元", obs_date_rule=obs_date_rule)


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
    assert skipped == [LON_NC.format(d="2026-10-13", n=1)]
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
    assert skipped == [CHI_NC.format(d="2026-10-13", n=1)]


def test_VIX_UTC已換日_芝加哥仍是前一天_前一交易日收盤照寫_不倒退():
    """AI 總管 2026-10-14 裁決（稽核 M 實測）：取得於 2026-10-14T02:00Z（芝加哥 10-13 21:00、台北 10:00）。
    未收盤界線＝max(UTC 日 10-14, 芝加哥日 10-13)＝10-14 ⇒ 10-13 那根（已於 15:15 CT 收盤）照寫，
    與舊規則（UTC 取日）時效相同。~~舊版本測試：同一情境 10-13 不寫~~（有意識的更正，不是漏刪）。"""
    rows, _err, skipped = _rows(_series(VIX_TAIL, fetched_at="2026-10-14T02:00:00+00:00",
                                        exchange_tz=CHICAGO, ticker="^VIX"), key="vol_index")
    assert [r["obs_date"] for r in rows][-1] == "2026-10-13"
    assert [r["obs_date"] for r in rows] == ["2026-10-08", "2026-10-09", "2026-10-12", "2026-10-13"]
    assert skipped == []
    # 與舊規則（UTC 取日、以 UTC 取得日比）逐筆相同：這是保留既有 VIX 時效，不是新語意
    assert [r["obs_date"] for r in rows] == [_legacy_utc_day(t) for t, _c in VIX_TAIL
                                             if _legacy_utc_day(t) < "2026-10-14"]


def test_VIX_盤中取數_當天那根不寫():
    """取得於 2026-10-13T20:00Z（芝加哥 15:00，收盤前）：界線＝max(10-13, 10-13)＝10-13 ⇒ 10-13 那根不寫。"""
    rows, _err, skipped = _rows(_series(VIX_TAIL, fetched_at="2026-10-13T20:00:00+00:00",
                                        exchange_tz=CHICAGO, ticker="^VIX"), key="vol_index")
    assert "2026-10-13" not in [r["obs_date"] for r in rows]
    assert skipped == [CHI_NC.format(d="2026-10-13", n=1)]


def test_not_closed_cutoff_day_取世界協調時間與交易所當地日期較晚者():
    from zoneinfo import ZoneInfo
    assert mi.not_closed_cutoff_day("2026-10-14T02:00:00+00:00", ZoneInfo(CHICAGO)) == "2026-10-14"
    assert mi.not_closed_cutoff_day("2026-10-13T20:00:00+00:00", ZoneInfo(CHICAGO)) == "2026-10-13"
    assert mi.not_closed_cutoff_day("2026-10-13T23:30:00+00:00", ZoneInfo(LONDON)) == "2026-10-14"
    assert mi.not_closed_cutoff_day("2026-10-13T18:54:31+00:00", ZoneInfo(LONDON)) == "2026-10-13"


def test_舊規則漏洞_倫敦當天那根UTC為昨天23點_新規則正確排除():
    """報告中 `2026-10-12T23:00Z` 那根（＝倫敦 10-13 00:00，交易進行中）收盤為 null；**合成**它帶值的情形。
    舊規則取 UTC 日 10-12 < 取得日 10-13 → 會把盤中值當成 10-12 的收盤寫進去（日期也錯）；
    新規則取倫敦日 10-13，不早於倫敦取得日 10-13 → 不寫。"""
    today = (USD_TODAY_LONDON, 32.1)   # 合成：報告原值為 null
    rows, _err, skipped = _rows(_series(USD_TAIL + [today]))
    assert [r["obs_date"] for r in rows][-1] == "2026-10-09"
    assert "2026-10-12" not in [r["obs_date"] for r in rows]
    assert 32.1 not in [r["value_num"] for r in rows]
    assert skipped == [LON_NC.format(d="2026-10-13", n=1)]
    assert _legacy_utc_day(USD_TODAY_LONDON) == "2026-10-12"   # 舊規則的錯位


def test_倫敦已過午夜UTC還沒_前一個倫敦日成為已收盤():
    """取得於 2026-10-13T23:30Z ＝ 倫敦 10-14 00:30：倫敦 10-13 那根（UTC 10-12 23:00）已收盤 → 以 10-13 寫入；
    倫敦 10-14 那根（UTC 10-13 23:00，合成）不寫。"""
    tomorrow = (USD_TODAY_LONDON + 86400, 32.2)   # 合成：2026-10-13T23:00Z ＝ 倫敦 10-14 00:00
    rows, _err, skipped = _rows(_series(USD_TAIL + [(USD_TODAY_LONDON, 32.1), tomorrow],
                                        fetched_at="2026-10-13T23:30:00+00:00"))
    assert [(r["obs_date"], r["value_num"]) for r in rows][-1] == ("2026-10-13", 32.1)
    assert skipped == [LON_NC.format(d="2026-10-14", n=1)]


def test_缺交易所時區_整批不寫_不退回UTC():
    rows, err, skipped = _rows(_series(USD_SUMMER_HEAD, exchange_tz=None))
    assert rows == [] and err is None
    assert skipped == ["L1 回傳未帶交易所時區（來源未報，或改版前的快取物件；attrs['exchange_tz']），"
                       "不推定，4 筆全部不寫"]


def test_交易所時區為空字串_同缺():
    rows, _err, skipped = _rows(_series(USD_SUMMER_HEAD, exchange_tz=""))
    assert rows == [] and "L1 回傳未帶交易所時區" in skipped[0]


@pytest.mark.parametrize("bad", ["Mars/Olympus_Mons", "../etc/passwd", "europe/london ", 123,
                                 # 2026-10-14 稽核 N／M：目錄名（IsADirectoryError）、過長（ENAMETOOLONG）、
                                 # 非 Area/Location 形式、posix/ right/ 別名樹
                                 "America", "Europe", "America/Argentina", "A" * 300, "Europe/" + "A" * 300,
                                 "Factory", "posixrules", "UTC", "posix/Europe/London", "right/Europe/London"])
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


def _london_weekday_midnights(first: str, n: int, base: float = 31.5):
    """合成：從 `first`（倫敦日期）起 n 個倫敦平日的 00:00（以 zoneinfo 換算成 Unix 秒），值逐根 +0.001。
    外匯語意有最少根數門檻（`FX_MIN_REFERENCE_VOTES`），經 builder 的測試需要足夠根數。"""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    day, out = date.fromisoformat(first), []
    while len(out) < n:
        if day.weekday() < 5:
            out.append((int(datetime(day.year, day.month, day.day, tzinfo=ZoneInfo(LONDON)).timestamp()),
                        round(base + len(out) * 0.001, 6)))
        day += timedelta(days=1)
    return out


def test_開閘時_build_fx_indicator_table套新規則(monkeypatch):
    """~~`USD_TAIL + 盤中值` → 首列 10-02、fetched 7~~ → 2026-10-14（客戶裁示前一交易日語意＋A1 最少根數門檻；
    有意識的更正，不是漏刪）：舊例只有 6 根已收盤，不足門檻；改用 25 根合成倫敦 00:00 平日根 ＋ 盤中值。
    首根倫敦 09-01（二）→ 觀測日 08-31（一）；盤中值未收盤不寫。"""
    monkeypatch.setattr(mi, "FX_OBS_DATE_RULE_VERIFIED", True)
    bars = _london_weekday_midnights("2026-09-01", 25)
    s = _series(bars + [USD_INTRADAY], ticker="JPYTWD=X")
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", lambda ticker, *a, **k: (s, None))
    out = mi.build_fx_indicator_table(["JPY"])
    assert [r["obs_date"] for r in out["rows"]][0] == "2026-08-31"
    assert len(out["rows"]) == 25 and out["fetched"] == {"fx_twd_per_jpy": 26}


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
    rows, row_err, skipped = mi.rows_from_daily_close("fx_twd_per_usd", s, err, value_unit="新臺幣／美元",
                                                      obs_date_rule=mi.OBS_DATE_SAME_DAY)
    assert row_err is None and skipped == []
    assert [r["obs_date"] for r in rows] == ["2024-10-14", "2024-10-15", "2024-10-16", "2024-10-17"]


# ═══════════════════════ 2026-10-14 稽核 N／M 合併修正輪 ═══════════════════════


@pytest.mark.parametrize("name", ["America", "America/Argentina", "A" * 300, "Factory", "posixrules", "UTC",
                                  "posix/Europe/London", "right/America/Chicago"])
def test_exchange_zone_目錄名過長名與非地區名_回None_不拋例外(name):
    assert mi.exchange_zone(name) is None


@pytest.mark.parametrize("name", [LONDON, CHICAGO, "Etc/UTC", "America/Argentina/Buenos_Aires"])
def test_exchange_zone_IANA地區名_接受(name):
    assert mi.exchange_zone(name) is not None


def test_怪時區不讓整張表炸掉_FRED鍵照寫(monkeypatch):
    """VIX 帶 `America`（目錄名，ZoneInfo 拋 IsADirectoryError）：該鍵整批不寫，其他鍵（FRED）照寫。"""
    from shared import fred_series

    vix = _series(VIX_TAIL, fetched_at=VIX_FETCHED, exchange_tz="America", ticker="^VIX")
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", lambda ticker, *a, **k: (vix, None))
    monkeypatch.setattr(mi, "_utc_today", lambda: date(2026, 10, 13))
    floor = (date(2026, 10, 13) - pd.Timedelta(days=mi.FRED_LOOKBACK_DAYS)).isoformat()
    frame = pd.DataFrame({"date": pd.to_datetime(["2026-08-01"]), "value": [4.3],
                          "realtime_start": pd.to_datetime(["2026-09-02"]), "realtime_end": ["9999-12-31"]})
    frame.attrs.update({"fetched_at": "2026-10-13T06:00:00+00:00", "realtime_floor": floor,
                        "source": "FRED:X:vintages"})
    monkeypatch.setattr(mi, "fetch_fred_vintages_with_error", lambda sid, key, start: (frame.copy(), None))
    assert fred_series.FRED_FED_FUNDS   # 前提：FRED 鍵存在
    out = mi.build_market_indicator_table(fred_api_key="KEY")
    keys = {r["indicator_key"] for r in out["rows"]}
    assert "vol_index" not in keys
    assert {"credit_spread_pct", "term_spread_pct", "policy_rate_pct"} <= keys
    assert "無法辨識" in out["skipped"]["vol_index"][0] and "vol_index" not in out["errors"]


def test_probe的zone_known借用同一個判定():
    import importlib.util
    from pathlib import Path
    script = Path(__file__).resolve().parents[1] / "scripts" / "probe_fx_obs_date.py"
    spec = importlib.util.spec_from_file_location("probe_fx_obs_date_tz", script)
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    for name in ["America", "Factory", "posixrules", "UTC", "posix/Europe/London", LONDON, CHICAGO, None]:
        assert probe.zone_known(name) is (mi.exchange_zone(name) is not None), name


def test_過半數基準_在同一鍵之內計算_不跨鍵(monkeypatch):
    """兩個鍵各自自洽（匯率倫敦 00:00、VIX 芝加哥 02:00）：若基準跨鍵合算，VIX 的 02:00 會被當成少數而丟掉。"""
    monkeypatch.setattr(mi, "FX_OBS_DATE_RULE_VERIFIED", True)
    # ~~`USD_TAIL[:5]`（倫敦 00:00 × 5）~~ → 2026-10-14：外匯語意有最少根數門檻（A1），改 25 根合成（不是漏刪）
    usd = _series(_london_weekday_midnights("2026-09-01", 25), ticker="USDTWD=X")   # 倫敦 00:00 × 25
    vix = _series(VIX_TAIL[:3], fetched_at=VIX_FETCHED, exchange_tz=CHICAGO, ticker="^VIX")   # 芝加哥 02:00 × 3
    table = {"USDTWD=X": usd, "^VIX": vix}
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", lambda ticker, *a, **k: (table[ticker], None))
    out = mi.build_market_indicator_table()
    by_key = {}
    for r in out["rows"]:
        by_key[r["indicator_key"]] = by_key.get(r["indicator_key"], 0) + 1
    assert by_key["fx_twd_per_usd"] == 25 and by_key["vol_index"] == 3
    assert "vol_index" not in out["skipped"] and "fx_twd_per_usd" not in out["skipped"]


def test_過半數基準_要嚴格過半_最多數但未過半不算():
    """五根已收盤：02:00 兩根、其他三個時刻各一根 —— 02:00 是最多數但只有 2/5，不過半 ⇒ 全部不寫。"""
    base = 1791356400   # 2026-10-07T07:00Z（芝加哥 02:00）
    bars = [(base, 15.0), (base + 86400, 15.1),                     # 10-07、10-08 02:00
            (base + 2 * 86400 + 3600, 15.2),                         # 10-09 03:00
            (base + 5 * 86400 + 7200, 15.3),                         # 10-12 04:00
            (base + 6 * 86400 + 10800, 15.4)]                        # 10-13 05:00
    rows, _err, skipped = _rows(_series(bars, fetched_at="2026-10-15T06:00:00+00:00",
                                        exchange_tz=CHICAGO, ticker="^VIX"), key="vol_index")
    assert rows == []
    assert len(skipped) == 1 and "沒有過半數一致的值" in skipped[0] and "5 筆不寫" in skipped[0]
    # 對照：多一根 02:00（3/6 仍不過半）也不寫；再多一根（4/7）就過半，02:00 那四根寫入
    more = bars + [(base + 7 * 86400, 15.5)]                         # 10-14 02:00
    assert _rows(_series(more, fetched_at="2026-10-16T06:00:00+00:00", exchange_tz=CHICAGO,
                         ticker="^VIX"), key="vol_index")[0] == []
    most = more + [(base + 8 * 86400, 15.6)]                         # 10-15 02:00
    rows3, _e, skipped3 = _rows(_series(most, fetched_at="2026-10-17T06:00:00+00:00", exchange_tz=CHICAGO,
                                        ticker="^VIX"), key="vol_index")
    assert [r["obs_date"] for r in rows3] == ["2026-10-07", "2026-10-08", "2026-10-14", "2026-10-15"]
    assert any("基準 02:00:00" in x and "不一致 3 筆不寫" in x for x in skipped3)


def test_判定順序_倫敦當天00點與盤中值同日_歸重複不歸未收盤():
    """釘住「重複 → 未收盤」的順序（稽核 M 突變 M7：兩者對調時舊測試全綠）。
    倫敦 10-13 00:00 那一根（合成：帶值）與盤中值（倫敦 10-13 19:54）同一個倫敦日 ⇒ 兩根都歸「重複」。"""
    rows, _err, skipped = _rows(_series(USD_TAIL + [(USD_TODAY_LONDON, 32.1), USD_INTRADAY]))
    assert [r["obs_date"] for r in rows][-1] == "2026-10-09"
    assert skipped == ["同一觀測日重複 2 筆不寫"]


def test_exchange_zone_posix與right前綴_即使系統有那棵子樹也拒絕(monkeypatch):
    """本機 tzdata 沒有 `posix/`、`right/` 子樹（ZoneInfo 本來就認不得），前綴檢查在這裡測不出來；
    以替身 ZoneInfo（什麼都認得）模擬有那棵子樹的系統（例如 Debian 的 tzdata），前綴檢查要自己擋下。"""
    sentinel = object()
    monkeypatch.setattr(mi, "ZoneInfo", lambda name: sentinel)
    assert mi.exchange_zone("posix/Europe/London") is None
    assert mi.exchange_zone("right/America/Chicago") is None
    assert mi.exchange_zone("Europe/London") is sentinel


# ═══════════════════════ 2026-10-14 收尾小輪：基準根的母體 ═══════════════════════
# ~~基準（過半數的當地時刻）在「已收盤根」上計算：觀測日 < 未收盤界線的根，**含**同日重複根與週末根，~~
# ~~**不含**未收盤根（盤中值的時刻不是日界）。重複與週末根本身不寫，但計入母體 —— 它們出現就代表日界可疑，~~
# ~~計進分母只會讓基準更難成立（從嚴），不會讓錯位的根被寫進去。~~
# → 2026-10-14 更正（AI 總管裁決，依據稽核 M 反例；有意識的更正，不是漏刪）：舊註解的「只會讓基準更難成立」不成立 ——
#   當時重複根與週末根也替自己的時刻**投票**，日界錯位時週末根與錯位根同一時刻，會把錯位那一邊推過半數。
#   現行：**分母**＝已收盤根全部（含重複根、週末根；不含未收盤根）；**票**＝只有不重複的平日已收盤根；
#   某時刻票數 > 分母 / 2 才成為基準。可疑根只進分母、不投票，「只會讓基準更難成立」自此才成立。


def test_基準母體_含週末根_週末根讓多數不過半時全部不寫():
    """平日 02:00 三根 ＋ 週末 05:00 三根（合成）：母體 6 根、02:00 只 3/6 不過半 ⇒ 全部不寫。
    （若把週末根排出母體，02:00 會變成 3/3，平日三根就會被寫進去 —— 稽核 N 的 O10。）"""
    wk = [(1791270000, 15.0), (1791356400, 15.1), (1791442800, 15.2)]      # 10-06／07／08 07:00Z（02:00 CDT）
    we = [(1791021600, 16.0), (1791108000, 16.1), (1791626400, 16.2)]      # 10-03(六)／04(日)／10(六) 10:00Z（05:00 CDT）
    rows, _err, skipped = _rows(_series(sorted(wk + we), fetched_at="2026-10-14T06:00:00+00:00",
                                        exchange_tz=CHICAGO, ticker="^VIX"), key="vol_index")
    assert rows == []
    assert "觀測日（交易所時區 America/Chicago）為星期六或星期日 3 筆不寫" in skipped
    assert any("沒有過半數一致的值" in x and "3 筆不寫" in x for x in skipped)


def test_基準母體_含重複根_重複根讓多數不過半時全部不寫():
    """10-06、10-07 02:00 兩根 ＋ 10-08 03:00／04:00 兩根（同日重複，合成）：母體 4 根、02:00 只 2/4 ⇒ 全部不寫。
    （若把重複根排出母體，02:00 會變成 2/2 —— 稽核 N 的 O9。）"""
    bars = [(1791270000, 15.0), (1791356400, 15.1), (1791446400, 15.2), (1791450000, 15.3)]
    rows, _err, skipped = _rows(_series(bars, fetched_at="2026-10-14T06:00:00+00:00",
                                        exchange_tz=CHICAGO, ticker="^VIX"), key="vol_index")
    assert rows == []
    assert "同一觀測日重複 2 筆不寫" in skipped
    assert any("沒有過半數一致的值" in x and "2 筆不寫" in x for x in skipped)


def test_基準母體_不含未收盤根_盤中值不干擾基準():
    """~~尾段 5 根倫敦 00:00 ＋ 盤中值：基準 00:00、5/5~~ → 2026-10-14 改例子（稽核 N：突變 O10b 把未收盤根也算進基準時，
    舊例子 5 根 00:00 仍過半、測試照綠，守不住要守的性質；有意識的更正，不是漏刪）。
    新例子讓盤中值那一根能翻轉過半與否（依「分母＝已收盤根全部、票＝不重複的平日已收盤根」重算）：
    已收盤 3 根 —— 倫敦 10-07、10-08 的 00:00 兩根（節錄）＋ 10-09 03:00 一根（合成，時刻不同）；另加盤中值（倫敦 10-13 19:54）。
    - 盤中值**不計入**（現行）：分母 3，00:00 得 2 票 > 1.5 ⇒ 基準 00:00，寫入 10-07、10-08；03:00 那根不一致不寫。
    - 盤中值**計入**（突變 O10b）：分母 4，00:00 得 2 票、19:54 得 1 票，2 > 2 不成立 ⇒ 無基準、整鍵不寫。"""
    odd = (USD_TAIL[5][0] + 3 * 3600, 31.93)                # 2026-10-09T02:00Z ＝ 倫敦（夏令）10-09 03:00
    rows, _err, skipped = _rows(_series(USD_TAIL[3:5] + [odd, USD_INTRADAY]))
    assert [r["obs_date"] for r in rows] == ["2026-10-07", "2026-10-08"]
    assert LON_NC.format(d="2026-10-13", n=1) in skipped
    assert any("基準 00:00:00" in x and "不一致 1 筆不寫" in x for x in skipped)


# ═══════════════════════ 2026-10-14 稽核 M 反例：可疑根只進分母、不投票 ═══════════════════════


def _counterexample_series():
    """稽核 M 的 counterex.py 序列（逐字照抄其建法）：倫敦冬令；A 段 9 根正確（倫敦 00:00 ＝ UTC 00:00）；
    B 段 10 根錯位（交易日 D 標在倫敦 D−1 23:00）—— 其中 8 根落在平日、2 根落在週日（11-16、11-23）。"""
    a_days = ["2025-11-03", "2025-11-04", "2025-11-05", "2025-11-06", "2025-11-07",
              "2025-11-10", "2025-11-11", "2025-11-12", "2025-11-13"]
    b_trade = ["2025-11-17", "2025-11-18", "2025-11-19", "2025-11-20", "2025-11-21",
               "2025-11-24", "2025-11-25", "2025-11-26", "2025-11-27", "2025-11-28"]
    idx = [pd.Timestamp(d) for d in a_days] + [pd.Timestamp(d) - pd.Timedelta(hours=1) for d in b_trade]
    vals = [30.0 + i * 0.01 for i in range(len(a_days))] + [31.0 + i * 0.01 for i in range(len(b_trade))]
    s = pd.Series(vals, index=pd.DatetimeIndex(idx), dtype=float, name="USDTWD=X")
    s.attrs.update(source="Yahoo:USDTWD=X", fetched_at="2025-12-01T12:00:00+00:00", exchange_tz=LONDON)
    return s


def test_稽核M反例_週末根不得替錯位時刻投票_錯位根一根都不寫():
    """推算（新規則）：已收盤 19 根全部進分母（無未收盤根）。投票只算不重複的平日根：
    00:00 ＝ A 段 9 票；23:00 ＝ B 段平日 8 票（兩根週日不投票）。過半門檻 19/2 ＝ 9.5 ⇒ 9 與 8 都未過半
    ⇒ 無基準，整鍵不寫。（舊做法：週日兩根也替 23:00 投票 ⇒ 23:00 得 10 票 > 9.5 ⇒ 基準變 23:00，
    8 根錯位根以早一天的觀測日寫入、9 根正確的根被丟掉。）以實跑結果為準。"""
    rows, err, skipped = mi.rows_from_daily_close("fx_twd_per_usd", _counterexample_series(), None,
                                                  value_unit="新臺幣／美元", obs_date_rule=mi.OBS_DATE_SAME_DAY)
    assert err is None
    assert [r for r in rows if r["value_num"] >= 31.0] == []          # 錯位根一根都不寫
    assert rows == []                                                  # 依推算：整鍵不寫
    assert "觀測日（交易所時區 Europe/London）為星期六或星期日 2 筆不寫" in skipped
    (base,) = [x for x in skipped if "沒有過半數一致的值" in x]
    assert "票數 00:00:00×9、23:00:00×8；分母 19" in base and "17 筆不寫" in base


def test_可疑根少量出現時_正確基準仍成立_正確的根照寫():
    """尾段 6 根倫敦 00:00（平日、不重複）＋ 一根週日 23:00（與錯位時刻同一時刻，合成）
    ＋ 一對同日重複根（倫敦 10-12 00:00 與 01:00，合成）：分母 9，00:00 得 6 票 > 4.5 ⇒ 基準 00:00，6 根照寫。"""
    sunday_2300 = (1790895600 + 3 * 86400 - 3600, 31.9)     # 2026-10-04T22:00Z ＝ 倫敦（夏令）10-04（日）23:00
    dup_a = (1791154800 + 7 * 86400, 31.95)                 # 2026-10-11T23:00Z ＝ 倫敦 10-12 00:00
    dup_b = (1791154800 + 7 * 86400 + 3600, 31.96)          # 2026-10-12T00:00Z ＝ 倫敦 10-12 01:00
    bars = sorted(USD_TAIL + [sunday_2300, dup_a, dup_b])
    rows, _err, skipped = _rows(_series(bars, fetched_at="2026-10-13T18:54:31+00:00"))
    assert [r["obs_date"] for r in rows] == ["2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07",
                                             "2026-10-08", "2026-10-09"]
    assert "同一觀測日重複 2 筆不寫" in skipped
    assert "觀測日（交易所時區 Europe/London）為星期六或星期日 1 筆不寫" in skipped
    assert not any("不一致" in x or "沒有過半數" in x for x in skipped)
