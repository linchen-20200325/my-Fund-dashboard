# -*- coding: utf-8 -*-
"""匯率採「前一交易日收盤」語意與日期（客戶 2026-10-14 裁示）的單元測試（fast lane；不打任何網路）。

客戶原話：「匯率採『前一交易日收盤』語意與日期。但這只是批准規則，不代表批准立即開閘。美元必須完成後續實證並通過
獨立稽核後才能顯示。EUR／JPY／CNY 未驗證完成前維持資料未備，不得推估、替代或自動換來源。」

依據：兩組獨立判讀（探測報告 `origin/probe/fx-obs-date-results` 分支
`results/20261014T064729Z_run38524215912/report.json`）—— Yahoo 外匯日 K 標日期 D 的那根，已收盤後 close（與 open）
≈ 倫敦 D 日剛開始的價格，等於 Yahoo 自己的「D−1 收盤／前收」。

- 外匯（`OBS_DATE_PREV_WEEKDAY`）：觀測日＝日 K 日期 D 的前一個平日；^VIX 等非外匯（`OBS_DATE_SAME_DAY`）不變。
- 未收盤、週末、當地時刻基準看位移前的 D；「同一觀測日重複」看位移後的觀測日。
- 判讀 A 的 A1：外匯另加最少根數門檻 `FX_MIN_REFERENCE_VOTES`。
- 閘門 `FX_OBS_DATE_RULE_VERIFIED` 仍為 False：閘門關閉時對外輸出與 origin/main（`753d59c`）逐欄相同（literal 黃金檔）。
- 另補 #957 延後的兩條反例：未收盤根只投票、不進分母；重複根替錯位時刻投票。

**`USD_GOLDEN` 的時間戳與收盤值逐字抄自上述報告的 `tickers["USDTWD=X"].raw_daily_full`**（索引 496～523；
收盤為 null 的那一根照 L1 `.dropna()` 不放進序列，見註解）；本檔不在執行期讀該分支。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from services.v2_tables import market_indicator as mi

LONDON = "Europe/London"
CHICAGO = "America/Chicago"

# ── 報告片段（Unix 秒, 收盤）：USDTWD=X，exchangeTimezoneName＝Europe/London，倫敦夏令（UTC 23:00 ＝ 倫敦 00:00）──
USD_GOLDEN = [
    (1788822000, 31.504899978637695),   # 倫敦 09-08（二）00:00
    (1788908400, 31.49920082092285),    # 09-09（三）
    (1788994800, 31.464000701904297),   # 09-10（四）
    (1789081200, 31.635000228881836),   # 09-11（五）
    (1789340400, 31.67620086669922),    # 09-14（一）
    (1789426800, 31.717599868774414),   # 09-15（二）
    (1789513200, 31.773399353027344),   # 09-16（三）
    (1789599600, 31.859600067138672),   # 09-17（四）
    (1789686000, 31.85110092163086),    # 09-18（五）
    (1789945200, 31.809099197387695),   # 09-21（一）
    (1790031600, 31.738399505615234),   # 09-22（二）
    (1790118000, 31.679500579833984),   # 09-23（三）
    (1790204400, 31.789499282836914),   # 09-24（四）
    (1790290800, 31.80620002746582),    # 09-25（五）
    (1790550000, 31.77869987487793),    # 09-28（一）
    (1790636400, 31.78219985961914),    # 09-29（二）
    (1790722800, 31.850000381469727),   # 09-30（三）
    (1790809200, 31.867900848388672),   # 10-01（四）
    (1790895600, 31.88680076599121),    # 10-02（五）
    (1791154800, 31.834400177001953),   # 10-05（一）
    (1791241200, 31.751399993896484),   # 10-06（二）
    (1791327600, 31.776899337768555),   # 10-07（三）
    (1791414000, 31.84830093383789),    # 10-08（四）
    (1791500400, 31.925399780273438),   # 10-09（五）
    (1791759600, 31.916099548339844),   # 10-12（一）
    (1791846000, 31.927799224853516),   # 10-13（二）
    # 報告索引 522：(1791932400, null) 倫敦 10-14（三）00:00 —— L1 `.dropna()` 丟掉，不放進序列。
    #   該根 open＝32.124000549316406＝ meta regularMarketPrice 32.138 − fulldayChange 0.014（Yahoo 前收）。
]
USD_INTRADAY = (1791960442, 32.13800048828125)   # 索引 523：倫敦 10-14 07:47（＝ regularMarketTime，盤中）
USD_FETCHED = "2026-10-14T06:47:25.697143+00:00"  # 報告 fetched_at_utc
# 依新語意的期望觀測日（日 K 日期 D 的前一個平日；週一 → 上週五），與 USD_GOLDEN 逐根對應。
GOLDEN_OBS = [
    "2026-09-07", "2026-09-08", "2026-09-09", "2026-09-10", "2026-09-11",
    "2026-09-14", "2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18",
    "2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24", "2026-09-25",
    "2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01", "2026-10-02",
    "2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09",
    "2026-10-12",
]

FX_NC = ("日 K 日期（交易所時區 Europe/London，位移前）不早於取得日（界線 {d}：取得時刻的世界協調時間日期與"
         "交易所時區日期取較晚者），可能是盤中即時值，{n} 筆不寫")


def _series(bars, *, fetched_at=USD_FETCHED, exchange_tz=LONDON, ticker="USDTWD=X"):
    """建法照抄 L1：`pd.to_datetime(秒, unit="s")`（不帶時區＝世界協調時間）；attrs 同 L1。"""
    s = pd.Series([c for _t, c in bars], index=pd.to_datetime([t for t, _c in bars], unit="s"),
                  dtype=float, name=ticker)
    s.attrs.update(source=f"Yahoo:{ticker}", fetched_at=fetched_at)
    if exchange_tz is not None:
        s.attrs["exchange_tz"] = exchange_tz
    return s


def _fx(series, key="fx_twd_per_usd"):
    return mi.rows_from_daily_close(key, series, None, value_unit="新臺幣／美元",
                                    obs_date_rule=mi.OBS_DATE_PREV_WEEKDAY)


def _same(series, key="vol_index"):
    return mi.rows_from_daily_close(key, series, None, value_unit="index", obs_date_rule=mi.OBS_DATE_SAME_DAY)


def _lon(y, m, d, hh=0) -> int:
    return int(datetime(y, m, d, hh, tzinfo=ZoneInfo(LONDON)).timestamp())


def _weekday_midnights(first: date, n: int, base: float = 31.0):
    """合成：從 `first` 起 n 個倫敦平日的 00:00，值逐根 +0.001。"""
    out, day = [], first
    while len(out) < n:
        if day.weekday() < 5:
            out.append((_lon(day.year, day.month, day.day), round(base + len(out) * 0.001, 6)))
        day += timedelta(days=1)
    return out


# ═══════════════════════ prev_weekday ═══════════════════════


@pytest.mark.parametrize("day, prev", [
    ("2026-10-13", "2026-10-12"),   # 二 → 一
    ("2026-10-16", "2026-10-15"),   # 五 → 四
    ("2026-10-12", "2026-10-09"),   # 一 → 上週五
    ("2026-10-11", "2026-10-09"),   # 日 → 五
    ("2026-10-10", "2026-10-09"),   # 六 → 五
    ("2026-12-28", "2026-12-25"),   # 一 → 上週五（耶誕節）：不查國定假日，照樣寫成那一天
])
def test_prev_weekday(day, prev):
    assert mi.prev_weekday(date.fromisoformat(day)) == date.fromisoformat(prev)


# ═══════════════════════ 黃金檔：報告片段 ═══════════════════════


def test_黃金檔_USD報告片段_觀測日為前一個平日_值逐根對應_盤中根不寫():
    rows, err, skipped = _fx(_series(USD_GOLDEN + [USD_INTRADAY]))
    assert err is None
    assert [r["obs_date"] for r in rows] == GOLDEN_OBS
    assert [r["value_num"] for r in rows] == [c for _t, c in USD_GOLDEN]
    assert [r["release_date"] for r in rows] == GOLDEN_OBS                      # Q3(a)
    assert all(r["is_revised"] is False and r["fetched_at"] == USD_FETCHED for r in rows)
    assert skipped == [FX_NC.format(d="2026-10-14", n=1)]
    # 前一份報告「寫入的 10-13 值」31.9278 依新語意屬 10-12（倫敦 10-13 那根＝10-12 收盤）
    assert dict((r["obs_date"], r["value_num"]) for r in rows)["2026-10-12"] == 31.927799224853516
    assert "2026-10-13" not in GOLDEN_OBS                                       # 盤中根位移後是 10-13，也不寫


def test_週一那根寫成上週五_週五那根寫成週四():
    rows, _err, _sk = _fx(_series(USD_GOLDEN))
    by_obs = {r["obs_date"]: r["value_num"] for r in rows}
    assert by_obs["2026-10-09"] == 31.916099548339844   # 倫敦 10-12（一）那根
    assert by_obs["2026-10-08"] == 31.925399780273438   # 倫敦 10-09（五）那根
    assert all(date.fromisoformat(d).weekday() < 5 for d in by_obs)


def test_週日根與週一根撞同一觀測日_該日全部不寫_不擇一():
    """合成週日根（倫敦 10-11 00:00）：D＝週日 → 上週五 10-09；週一根 D＝10-12 → 10-09 ⇒ 兩根都不寫、10-09 整天不寫。
    週日根先歸「重複」（判定順序：重複 → 未收盤 → 週末），只進分母、不投票；其餘根照寫。"""
    sunday = (_lon(2026, 10, 11), 31.95)
    rows, _err, skipped = _fx(_series(sorted(USD_GOLDEN + [sunday])))
    obs = [r["obs_date"] for r in rows]
    assert "2026-10-09" not in obs
    assert obs == [d for d in GOLDEN_OBS if d != "2026-10-09"]
    assert 31.95 not in [r["value_num"] for r in rows] and 31.916099548339844 not in [r["value_num"] for r in rows]
    assert skipped == ["位移後同一觀測日重複（觀測日＝日 K 日期的前一個平日）2 筆不寫"]


def test_週六根同樣撞上週五_該日全部不寫():
    saturday = (_lon(2026, 10, 10), 31.95)
    rows, _err, skipped = _fx(_series(sorted(USD_GOLDEN + [saturday])))
    assert "2026-10-09" not in [r["obs_date"] for r in rows]
    assert len(rows) == len(USD_GOLDEN) - 1
    assert skipped == ["位移後同一觀測日重複（觀測日＝日 K 日期的前一個平日）2 筆不寫"]


def test_只有週末根_沒有撞到時_仍以週末歸類不寫():
    """拿掉週一根（倫敦 10-12），另加週日根（倫敦 10-11）：週日 → 上週五 10-09，沒有別的根映到 10-09（週五那根 → 週四）
    ⇒ 不歸「重複」，歸「週末」不寫（D 為週末代表日界錯位，位移不會讓它變正常）；10-09 因此沒有值。"""
    bars = [b for b in USD_GOLDEN if b[0] != 1791759600] + [(_lon(2026, 10, 11), 31.95)]
    rows, _err, skipped = _fx(_series(sorted(bars)))
    assert "2026-10-09" not in [r["obs_date"] for r in rows]
    assert skipped == ["日 K 日期（交易所時區 Europe/London，位移前）為星期六或星期日 1 筆不寫"]


def test_未收盤根_位移後雖早於界線仍不寫_倫敦當天00點帶值時與盤中值同歸重複():
    """倫敦 10-14 00:00 那根（報告為 null；合成帶值）與盤中值同一個 D ⇒ 位移後同為 10-13 ⇒ 兩根歸「重複」，都不寫。"""
    today = (1791932400, 32.124000549316406)
    rows, _err, skipped = _fx(_series(USD_GOLDEN + [today, USD_INTRADAY]))
    assert [r["obs_date"] for r in rows] == GOLDEN_OBS
    assert skipped == ["位移後同一觀測日重複（觀測日＝日 K 日期的前一個平日）2 筆不寫"]


def test_倫敦已換日_前一個倫敦日那根成為已收盤_寫成再前一個平日():
    """取得於 2026-10-13T23:30Z（倫敦 10-14 00:30）：倫敦 10-13 那根（D＝10-13）已收盤 → 觀測日 10-12。"""
    rows, _err, skipped = _fx(_series(USD_GOLDEN, fetched_at="2026-10-13T23:30:00+00:00"))
    assert [r["obs_date"] for r in rows][-1] == "2026-10-12"
    assert skipped == []
    rows2, _e, skipped2 = _fx(_series(USD_GOLDEN, fetched_at="2026-10-13T18:00:00+00:00"))   # 倫敦 10-13 19:00
    assert [r["obs_date"] for r in rows2][-1] == "2026-10-09"
    assert skipped2 == [FX_NC.format(d="2026-10-13", n=1)]


def test_外匯語意_obs_date與release_date相同_欄位與契約一致():
    from services.v2_tables import contract
    rows, _err, _sk = _fx(_series(USD_GOLDEN))
    names = [name for name, _t, _n in contract.MARKET_INDICATOR_FIELDS]
    assert all(list(r) == names and contract.market_indicator_row_problems(r) == [] for r in rows)


# ═══════════════════════ 判讀 A 的 A1：最少根數門檻（只套外匯）═══════════════════════


def test_A1_單根已收盤的停更報價_外匯不寫():
    """`CNYTWD=X`／`CNHTWD=X` 只回一根的形狀：那一根若已收盤（停更的前一天報價、或週末取數），分母 1、過半數必然成立；
    門檻擋下 ⇒ 整鍵不寫。"""
    stale = [(_lon(2026, 10, 12), 4.5)]
    rows, err, skipped = _fx(_series(stale, ticker="CNYTWD=X"), key="fx_twd_per_cny")
    assert rows == [] and err is None
    assert skipped == ["已收盤平日根中與過半數基準 00:00:00（交易所時區 Europe/London）同一時刻者只有 1 根，"
                       f"少於外匯最少根數門檻 {mi.FX_MIN_REFERENCE_VOTES}，無法自證日界，1 筆不寫"]


@pytest.mark.parametrize("n, written", [(mi.FX_MIN_REFERENCE_VOTES - 1, 0),
                                        (mi.FX_MIN_REFERENCE_VOTES, mi.FX_MIN_REFERENCE_VOTES),
                                        (mi.FX_MIN_REFERENCE_VOTES + 1, mi.FX_MIN_REFERENCE_VOTES + 1)])
def test_A1_門檻邊界_恰等於門檻照寫_少一根整鍵不寫(n, written):
    bars = _weekday_midnights(date(2026, 8, 3), n)
    rows, _err, skipped = _fx(_series(bars, fetched_at="2026-10-14T06:00:00+00:00"))
    assert len(rows) == written
    if not written:
        assert skipped == [f"已收盤平日根中與過半數基準 00:00:00（交易所時區 Europe/London）同一時刻者只有 {n} 根，"
                           f"少於外匯最少根數門檻 {mi.FX_MIN_REFERENCE_VOTES}，無法自證日界，{n} 筆不寫"]
    else:
        assert skipped == []


def test_A1_門檻看的是基準的票數_不是分母():
    """門檻 20 根乾淨根 ＋ 1 對重複根（不投票、只進分母）：基準 00:00 得 20 票 ≥ 門檻，照寫 20 根。
    去掉一根乾淨根（19 票）⇒ 即使分母仍 ≥ 20 也不寫。"""
    clean = _weekday_midnights(date(2026, 8, 3), mi.FX_MIN_REFERENCE_VOTES)
    dup = [(_lon(2026, 9, 15), 31.5), (_lon(2026, 9, 15, 1), 31.6)]          # 同一個 D（09-15）⇒ 位移後同為 09-14
    rows, _e, skipped = _fx(_series(sorted(clean + dup), fetched_at="2026-10-14T06:00:00+00:00"))
    assert len(rows) == mi.FX_MIN_REFERENCE_VOTES
    rows2, _e, skipped2 = _fx(_series(sorted(clean[1:] + dup), fetched_at="2026-10-14T06:00:00+00:00"))
    assert rows2 == [] and any("只有 19 根" in x for x in skipped2)


def test_A1_門檻只套外匯_非外匯少根照舊寫():
    vix = [(1791442800, 15.40999984741211), (1791529200, 14.84000015258789)]
    rows, _err, skipped = _same(_series(vix, fetched_at="2026-10-14T02:00:00+00:00", exchange_tz=CHICAGO,
                                        ticker="^VIX"))
    assert [r["obs_date"] for r in rows] == ["2026-10-08", "2026-10-09"] and skipped == []


# ═══════════════════════ #957 延後的兩條反例（觀測日語意無關；以當日語意驗）═══════════════════════


def test_反例_未收盤根不得投票_也不進分母():
    """已收盤 4 根：倫敦 10-06、10-07 的 00:00 兩根，10-08、10-09 的 03:00 兩根（合成）；另一根未收盤
    （倫敦 10-13 00:00，合成帶值；取得於 10-13 18:54Z）。
    - 現行：分母 4，00:00 與 03:00 各 2 票，2 > 2 不成立 ⇒ 無基準，整鍵不寫。
    - 突變「未收盤根只投票、不進分母」：00:00 得 3 票 > 2 ⇒ 基準 00:00，寫入 10-06、10-07（本條抓這個）。
    - 突變「未收盤根投票也進分母」：分母 5、00:00 得 3 票 > 2.5 ⇒ 同樣會寫（本條也抓）。"""
    bars = [(_lon(2026, 10, 6), 31.75), (_lon(2026, 10, 7), 31.77),
            (_lon(2026, 10, 8, 3), 31.84), (_lon(2026, 10, 9, 3), 31.92),
            (_lon(2026, 10, 13), 32.1)]
    rows, _err, skipped = _same(_series(bars, fetched_at="2026-10-13T18:54:31+00:00"), key="fx_twd_per_usd")
    assert rows == []
    assert "觀測日不早於取得日（界線 2026-10-13：取得時刻的世界協調時間日期與交易所時區 Europe/London 日期取較晚者）1 筆不寫" \
        in skipped
    (base,) = [x for x in skipped if "沒有過半數一致的值" in x]
    assert "票數 00:00:00×2、03:00:00×2；分母 4" in base and "4 筆不寫" in base


def test_反例_重複根不得替錯位時刻投票():
    """倫敦夏令。乾淨根 00:00 × 4（10-05～10-08）；錯位根 23:00 × 3（10-12、10-13、10-15，各自不重複）；
    另有一對**時間戳完全相同**的重複根（10-14 23:00，錯位時刻）。分母 9。
    - 現行：00:00 得 4 票、23:00 得 3 票（重複根不投票），門檻 4.5 ⇒ 都未過半，整鍵不寫。
    - 突變「重複根也投票」：23:00 得 5 票 > 4.5 ⇒ 基準 23:00，3 根錯位根寫入、4 根正確根被丟（本條抓這個）。"""
    clean = [(_lon(2026, 10, d), 31.0 + d / 100) for d in (5, 6, 7, 8)]
    wrong = [(_lon(2026, 10, d, 23), 32.0 + d / 100) for d in (12, 13, 15)]
    dup = [(_lon(2026, 10, 14, 23), 33.0), (_lon(2026, 10, 14, 23), 33.1)]
    rows, _err, skipped = _same(_series(sorted(clean + wrong + dup), fetched_at="2026-10-20T12:00:00+00:00"),
                                key="fx_twd_per_usd")
    assert [r for r in rows if r["value_num"] >= 32.0] == []           # 錯位根一根都不寫
    assert rows == []
    assert "同一觀測日重複 2 筆不寫" in skipped
    (base,) = [x for x in skipped if "沒有過半數一致的值" in x]
    assert "票數 00:00:00×4、23:00:00×3；分母 9" in base and "7 筆不寫" in base


def test_外匯語意_未收盤判定看位移前的日K日期_盤中根不進分母():
    """2026-10-14 稽核 X N3：投票迴圈的未收盤判定必須看**位移前**的日 K 日期 D，不得看位移後的觀測日。
    合成（倫敦夏令）：已收盤平日根 00:00 × 25、01:00 × 24（各自不同的 D，不重複）；另加 1 根盤中值，
    D＝取得當日（倫敦 10-14 07:47），位移後觀測日 10-13 早於界線 10-14。
    - 正確：盤中根 D 不早於界線 ⇒ 不進分母；分母 49，00:00 得 25 票 > 24.5 ⇒ 基準 00:00，寫入 25 列。
    - 突變「投票迴圈改看位移後的觀測日」：盤中根進分母 ⇒ 分母 50，25 > 25 不成立 ⇒ 無基準，整鍵不寫（本條抓這個）。
    - 突變「寫列迴圈改看位移後的觀測日」：盤中根不歸「未收盤」、改歸「當地時刻不一致」⇒ skipped 不同（本條也抓）。"""
    bars, day, n0, n1 = [], date(2026, 7, 1), 0, 0
    while n0 < 25 or n1 < 24:
        if day.weekday() < 5:
            if n0 <= n1 and n0 < 25:
                bars.append((_lon(day.year, day.month, day.day), round(31.0 + n0 * 0.001, 6)))
                n0 += 1
            else:
                bars.append((_lon(day.year, day.month, day.day, 1), round(32.0 + n1 * 0.001, 6)))
                n1 += 1
        day += timedelta(days=1)
    intraday = (_lon(2026, 10, 14, 7) + 47 * 60, 99.0)                       # 倫敦 10-14 07:47（盤中）
    rows, err, skipped = _fx(_series(bars + [intraday], fetched_at="2026-10-14T06:47:25+00:00"))
    assert err is None
    assert len(rows) == 25
    assert all(31.0 <= r["value_num"] < 32.0 for r in rows)                  # 只寫 00:00 那 25 根
    assert 99.0 not in [r["value_num"] for r in rows]
    assert skipped == [FX_NC.format(d="2026-10-14", n=1),
                       "當地時刻與同鍵已收盤根的基準 00:00:00（交易所時區 Europe/London）不一致 24 筆不寫"]


# ═══════════════════════ 呼叫端與外匯判定 ═══════════════════════


def test_obs_date_rule必填_給錯值當場炸():
    s = _series(USD_GOLDEN)
    with pytest.raises(TypeError):
        mi.rows_from_daily_close("fx_twd_per_usd", s, None, value_unit="新臺幣／美元")   # noqa —— 故意漏給
    with pytest.raises(ValueError, match="obs_date_rule"):
        mi.rows_from_daily_close("fx_twd_per_usd", s, None, value_unit="新臺幣／美元", obs_date_rule="prev_day")


def test_外匯判定沿用既有閘門標記_INDICATOR_SPECS只有美元一鍵是外匯():
    fx_keys = {k for k, spec in mi.INDICATOR_SPECS.items()
               if mi._obs_date_rule_of(spec) == mi.OBS_DATE_PREV_WEEKDAY}
    assert fx_keys == {"fx_twd_per_usd"}
    assert {k for k, spec in mi.INDICATOR_SPECS.items() if spec["phase1"] == "write_if_fx_verified"} == fx_keys
    assert mi._obs_date_rule_of(mi.INDICATOR_SPECS["vol_index"]) == mi.OBS_DATE_SAME_DAY


def _vix_tail():
    vix = [(1791442800, 15.40999984741211), (1791529200, 14.84000015258789),
           (1791788400, 15.210000038146973), (1791874800, 15.479999542236328)]
    return _series(vix, fetched_at="2026-10-14T02:00:00+00:00", exchange_tz=CHICAGO, ticker="^VIX")


def test_開閘時_美元走前一交易日語意_VIX不受影響(monkeypatch):
    monkeypatch.setattr(mi, "FX_OBS_DATE_RULE_VERIFIED", True)
    table = {"^VIX": (_vix_tail(), None), "USDTWD=X": (_series(USD_GOLDEN + [USD_INTRADAY]), None)}
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", lambda ticker, *a, **k: table[ticker])
    out = mi.build_market_indicator_table()
    fx = [r["obs_date"] for r in out["rows"] if r["indicator_key"] == "fx_twd_per_usd"]
    vix = [r for r in out["rows"] if r["indicator_key"] == "vol_index"]
    assert fx == GOLDEN_OBS
    assert vix == _same(_vix_tail())[0]
    assert [r["obs_date"] for r in vix] == ["2026-10-08", "2026-10-09", "2026-10-12", "2026-10-13"]


def test_開閘時_非美元幣別同樣走前一交易日語意(monkeypatch):
    monkeypatch.setattr(mi, "FX_OBS_DATE_RULE_VERIFIED", True)
    s = _series(USD_GOLDEN, ticker="EURTWD=X")
    monkeypatch.setattr(mi, "fetch_yf_close_with_error", lambda ticker, *a, **k: (s, None))
    out = mi.build_fx_indicator_table(["EUR"])
    assert [r["obs_date"] for r in out["rows"]] == GOLDEN_OBS


# ═══════════════════════ 閘門關閉：對外輸出與 origin/main（753d59c）相同 ═══════════════════════
# 期望值由 origin/main 的 `market_indicator.py` 以同一份 fixture 實跑後照抄（2026-10-14，資料工程組）。

_MAIN_VIX_ROWS = [("2026-10-08", 15.40999984741211), ("2026-10-09", 14.84000015258789),
                  ("2026-10-12", 15.210000038146973), ("2026-10-13", 15.479999542236328)]
_MAIN_NO_KEY = {
    "errors": {"credit_spread_pct": "未設定 FRED_API_KEY", "policy_rate_pct": "未設定 FRED_API_KEY",
               "term_spread_pct": "未設定 FRED_API_KEY"},
    "fetched": {"credit_spread_pct": 0, "policy_rate_pct": 0, "term_spread_pct": 0, "vol_index": 4},
    "pending": {"coincident_index": "ndc_no_release_date", "fx_twd_per_usd": "fx_obs_date_rule",
                "leading_index": "ndc_no_release_date"},
    "rows": [{"indicator_key": "vol_index", "obs_date": d, "release_date": d, "value_num": v, "value_unit": "index",
              "source_tier": "市場指標", "is_revised": False, "fetched_at": "2026-10-14T02:00:00+00:00"}
             for d, v in _MAIN_VIX_ROWS],
    "skipped": {"coincident_index": ["國發會景氣指標來源不給公布日；客戶 2026-09-26 裁示 Q3(c)：第一階段顯示資料未備"],
                "fx_twd_per_usd": ["USDTWD=X 的觀測日切日規則待以真實資料驗證（總管 2026-09-26 裁定；"
                                   "FX_OBS_DATE_RULE_VERIFIED）"],
                "leading_index": ["國發會景氣指標來源不給公布日；客戶 2026-09-26 裁示 Q3(c)：第一階段顯示資料未備"]},
}
_MAIN_FX = {
    "errors": {}, "fetched": {}, "rows": [],
    "pending": {f"fx_twd_per_{c}": "fx_obs_date_rule" for c in ("cnh", "cny", "eur", "jpy")},
    "skipped": {f"fx_twd_per_{c.lower()}": [f"{c}TWD=X 與 USDTWD=X 套同一條觀測日切日規則、同一個閘門，"
                                            f"待以真實資料驗證（FX_OBS_DATE_RULE_VERIFIED）"]
                for c in ("CNH", "CNY", "EUR", "JPY")},
}


def test_閘門關閉_build_market_indicator_table與main逐欄相同_匯率不取數(monkeypatch):
    assert mi.FX_OBS_DATE_RULE_VERIFIED is False
    calls = []

    def fake(ticker, *a, **k):
        calls.append(ticker)
        assert ticker == "^VIX", "閘門關閉時不得取匯率"
        return _vix_tail(), None

    monkeypatch.setattr(mi, "fetch_yf_close_with_error", fake)
    out = mi.build_market_indicator_table()
    assert out == _MAIN_NO_KEY
    assert list(out["rows"][0]) == list(_MAIN_NO_KEY["rows"][0])          # 欄位順序也相同
    assert calls == ["^VIX"]


def test_閘門關閉_build_fx_indicator_table與main逐欄相同_不取數(monkeypatch):
    assert mi.FX_OBS_DATE_RULE_VERIFIED is False

    def forbid(*a, **k):
        raise AssertionError("閘門關閉時不得取數")

    monkeypatch.setattr(mi, "fetch_yf_close_with_error", forbid)
    assert mi.build_fx_indicator_table(["EUR", "JPY", "CNY", "CNH"]) == _MAIN_FX
