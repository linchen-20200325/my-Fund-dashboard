"""tests/test_nav_history_currency_column.py — nav_history 第 7 欄 `currency`(2026-09-01)。

**為什麼要有這一欄(問題陳述,不是儀式)**
`nav_history`(Google Sheets)是唯一**永不刪除**的 NAV 持久化出口,去重鍵 `(code, date)`。
schema 原本六欄、**沒有幣別欄** —— 而**一個欄位不存在,它記不下來的事實就是永久失去的**:
既有的 `source` 欄存的是 `"app"` / `"backfill"` / `"nas_cron"`(誰觸發的),
**反推不出 fetcher,更反推不出幣別**。錯的先寫進去,對的就永遠寫不進來,
下游 1Y 報酬 / Sharpe / σ 全部照錯的算,而畫面上不會有任何異狀
(§1「錯誤的數字比沒有數字更危險」)。

**本檔守的四件事**
1. **寫入 → 讀回 round-trip**:真的走 `append_points` / `load_points`,列**實寫 7 個值**、
   第 7 格就是幣別、讀回來拿得到。—— 在此之前**寫入端的列形狀從來沒有任何契約在守**
   (實測:把 `append_points` 改成實寫 7 個值 + 表頭 7 欄,全套 fast lane 6257 → 6257,
   一顆都沒紅)。本檔的 round-trip 就是補上那個契約。
2. **取值只走「量測線」**:`_extract_points` 取的必須是**序列自己宣告**的
   `attrs["currency"]`,`fd["currency"]` **不得**當 fallback(理由見該測試 docstring)。
3. **合併序列不繼承 live 的幣別宣告**:`_merge_nav_history_series` 過去無條件把 live 的
   整份 attrs 蓋到「live ∪ 累積歷史」上。
4. **舊列容忍**:6 格舊列讀回 `currency == ""`(誠實的未知),**其餘 6 欄一格不動**。

⚠️ **空字串 = 誠實的未知,不是失敗。** 全 repo 只有晨星 / Yahoo / FundClear 會宣告幣別,
   故**新列也會有相當比例是空的**;既有列一律留空,**不得回填 TWD 或任何猜測值**(§1)。

⚠️ **fixture 一律用「字面表頭 list」,禁止引用 `_NAV_HEADERS` 建 fixture。**
   既有 5 個測試都寫成 `_Sheet([list(GS._NAV_HEADERS), …])` —— 常數一改 fixture 跟著改,
   測試會**靜靜繼續綠燈、什麼都沒證明**。本檔刻意把表頭寫死,常數改了就要有人來看這裡。
"""
from __future__ import annotations

import pandas as pd
import pytest

# prime 匯入順序(**不是多餘的 import**):`services.fund_service` ↔ `fund_fetcher` 是既有的
# latent 互相 import,把 fund_service 當本檔第一個 import 會撞循環 —— 同
# `tests/test_nav_history_consume.py` / `tests/test_nav_history_visibility.py` 的既有慣例。
import fund_fetcher  # noqa: F401,E402

from services import nav_history_gs as GS  # noqa: E402
from services.fund_service import _merge_nav_history_series  # noqa: E402
from shared.data_quality import (  # noqa: E402
    nav_series_currency,
    reconcile_row_currencies,
)
from ui.helpers.nav_history_hook import _extract_points  # noqa: E402

# ⚠️ 字面表頭,**刻意不引用 `GS._NAV_HEADERS`**(見檔頭最後一段)。
_HDR7 = ["code", "date", "nav", "fund_name", "source", "recorded_at", "currency"]
_HDR6_LEGACY = ["code", "date", "nav", "fund_name", "source", "recorded_at"]


class _WS:
    """最小 gspread worksheet 假件(真 worksheet 有的四個方法都給,不缺 `row_values`)。"""

    def __init__(self, rows):
        self.rows = [list(r) for r in rows]

    def get_all_values(self):
        return [[str(c) for c in r] for r in self.rows]

    def row_values(self, n):
        return list(self.rows[n - 1]) if len(self.rows) >= n else []

    def update(self, rng, values):
        assert rng == "A1"
        self.rows[0] = list(values[0])

    def append_rows(self, rows, **_k):
        self.rows.extend([list(r) for r in rows])


class _Sheet:
    def __init__(self, ws):
        self._ws = ws

    def worksheet(self, _name):
        return self._ws


def _series(dates, vals, ccy=None):
    s = pd.Series(vals, index=pd.to_datetime(dates), dtype=float)
    if ccy is not None:
        s.attrs["currency"] = ccy
    return s


# ══════════════════════════════════════════════════════════════════════
# 1. 寫入 → 讀回 round-trip(列形狀的契約;此前完全沒有)
# ══════════════════════════════════════════════════════════════════════
def test_append_then_load_round_trips_currency():
    ws = _WS([_HDR7])
    res = GS.append_points(
        [{"code": "TLZF9", "nav": 12.34, "nav_date": "2026-07-22",
          "fund_name": "安聯", "source": "app", "currency": "USD"}],
        _sheet=_Sheet(ws),
    )
    assert res == {"written": 1, "skipped": 0}

    row = ws.rows[-1]
    assert len(row) == 7, (
        f"寫入端沒有實寫第 7 個值 → 幣別根本沒進表;實得 {len(row)} 格:{row!r}")
    assert row[6] == "USD", f"第 7 格不是幣別;實得 {row!r}"

    pts = GS.load_points("TLZF9", _sheet=_Sheet(ws))
    assert len(pts) == 1
    assert pts[0]["currency"] == "USD", (
        f"讀取端沒有回 currency → 加欄等於零效果;實得 {pts[0]!r}")


def test_append_writes_empty_currency_when_unknown_not_a_guess():
    """量不到幣別 → 第 7 格是**空字串**(誠實的未知),不是 TWD、不是任何猜測值(§1)。"""
    ws = _WS([_HDR7])
    GS.append_points([{"code": "X", "nav": 1.5, "nav_date": "2026-07-22"}],
                     _sheet=_Sheet(ws))
    assert ws.rows[-1][6] == "", f"未知幣別被填了值:{ws.rows[-1]!r}"


def test_non_iso_currency_is_not_written_verbatim():
    """中文別名 / 垃圾字串一律收成 `""` —— 這張表永不刪除,寧可留空也不寫猜的。"""
    ws = _WS([_HDR7])
    GS.append_points([{"code": "X", "nav": 1.5, "nav_date": "2026-07-22",
                       "currency": "美元"}], _sheet=_Sheet(ws))
    assert ws.rows[-1][6] == ""


def test_clean_points_keeps_currency_key():
    """`_clean_points` 是**白名單輸出 key** —— 沒收 currency 的話整條線是安靜的 no-op。"""
    out = GS._clean_points([{"code": "x", "nav": 1.0, "nav_date": "2026-07-22",
                             "currency": "usd"}])
    assert out and out[0]["currency"] == "USD", (
        f"currency 被白名單丟掉了(整條線靜默 no-op);實得 {out!r}")


def test_existing_6col_sheet_gets_header_repaired_not_resized():
    """既有 6 欄分頁 → 補表頭到 7 欄。

    ⛔ 補法必須是 `ws.update("A1", …)`(照抄 `pool_repository._ws` 慣例),
       **不得**用 `ws.resize(cols=…)` —— gspread 送的是**絕對值**,在使用者手動維護到
       26 欄的表上等於刪掉 H..Z 欄連同內容。本假件**刻意不提供 `resize`**:
       誰改成 resize,這裡就 AttributeError 轉紅。
    """
    ws = _WS([_HDR6_LEGACY, ["OLD", "2026-07-01", "9.9", "n", "app", "t"]])
    GS.append_points([{"code": "NEW", "nav": 1.0, "nav_date": "2026-07-22",
                       "currency": "EUR"}], _sheet=_Sheet(ws))
    assert ws.rows[0] == _HDR7, f"表頭沒補到 7 欄;實得 {ws.rows[0]!r}"
    assert ws.rows[-1][6] == "EUR"


# ══════════════════════════════════════════════════════════════════════
# 2. 取值只走「量測線」—— fd["currency"] 不得當 fallback
# ══════════════════════════════════════════════════════════════════════
def test_extract_points_takes_series_attrs_never_fd_currency():
    """兩條線刻意矛盾:`fd["currency"]="TWD"` vs 序列宣告 `""` → 必須回 `""`。

    **為什麼不准用 `fd["currency"]` 當 fallback**:那是「宣告線」,它**無法分辨量測與猜測**
    —— 上游實測有 7 處死預設(MoneyDJ ×2 / TCB / TDCC / FundClear ×2 預設 USD、
    AllianzGI 預設 TWD),而 `fund_orchestration._correct_currency` 不只修不回、
    **還會覆蓋量到的正確值**(名稱含「台灣」→ 蓋掉量到的 USD)。
    寫進 `nav_history` 就永遠改不掉(§1)。

    **突變**:在取值處加一行 `or fd.get("currency")` → 本則必須轉紅。
    """
    fd = {"code": "X", "fund_name": "某某基金", "currency": "TWD",
          "series": _series(["2026-07-21", "2026-07-22"], [11.0, 11.1])}  # 序列不宣告
    pts = _extract_points(fd)
    assert len(pts) == 2
    assert all(p["currency"] == "" for p in pts), (
        f"取到了「宣告線」(fd['currency'])而不是「量測線」;實得 {pts!r}")


def test_extract_points_uses_measured_currency_when_series_declares_it():
    fd = {"code": "X", "fund_name": "n",
          "series": _series(["2026-07-21"], [11.0], ccy="USD")}
    assert _extract_points(fd)[0]["currency"] == "USD"


# ══════════════════════════════════════════════════════════════════════
# 3. 合併序列不得繼承 live 的幣別宣告
# ══════════════════════════════════════════════════════════════════════
def _days(n, start="2026-01-01"):
    return [str(d.date()) for d in pd.date_range(start, periods=n, freq="D")]


def test_merge_does_not_inherit_live_currency_over_hist(monkeypatch):
    """live 2 筆宣告 USD + hist 56 筆宣告 TWD → merged 58 點**不得**對外宣告 USD。

    修之前:`merged.attrs = dict(getattr(s_live, "attrs", {}) or {})` 無條件整份複製,
    實測 merged 58 點對外宣告 **USD** —— 下游全部照 USD 算,畫面上沒有任何異狀。

    **突變**:把該行改回無條件繼承(拿掉 reconcile)→ 本則必須轉紅。
    """
    hist = _series(_days(56, "2026-01-01"), [10.0 + i for i in range(56)], ccy="TWD")
    live = _series(_days(2, "2026-03-01"), [20.0, 20.1], ccy="USD")
    monkeypatch.setattr(GS, "load_series", lambda code, **_k: hist)

    merged, trace = _merge_nav_history_series(live, "X")
    assert trace and trace.get("success") is True and trace["added"] == 56
    assert len(merged) == 58
    assert nav_series_currency(merged) == "", (
        f"合併序列繼承了 live 的幣別宣告(混幣別卻宣告單一幣別);"
        f"實得 {merged.attrs.get('currency')!r}")


def test_merge_keeps_currency_when_both_sides_agree(monkeypatch):
    """兩邊都宣告同一個 ISO 三碼 → 合併後照樣宣告(不是一律清空,那會是另一種失真)。"""
    hist = _series(_days(5, "2026-01-01"), [10.0] * 5, ccy="USD")
    live = _series(_days(2, "2026-03-01"), [20.0, 20.1], ccy="usd")
    monkeypatch.setattr(GS, "load_series", lambda code, **_k: hist)
    merged, _ = _merge_nav_history_series(live, "X")
    assert nav_series_currency(merged) == "USD"


def test_merge_drops_stale_live_currency_when_hist_unknown(monkeypatch):
    """hist 未宣告 → 合併後不得沿用 live 的宣告(§1:不知道 ≠ 一致)。"""
    hist = _series(_days(5, "2026-01-01"), [10.0] * 5)          # 無宣告
    live = _series(_days(2, "2026-03-01"), [20.0, 20.1], ccy="USD")
    monkeypatch.setattr(GS, "load_series", lambda code, **_k: hist)
    merged, _ = _merge_nav_history_series(live, "X")
    assert "currency" not in merged.attrs and nav_series_currency(merged) == ""


def test_merge_rescue_branch_live_none_takes_hist_currency(monkeypatch):
    """`s_live is None` 救援分支:merged 全部是 hist 的列 → 誠實沿用 hist 的宣告。

    ⚠️ 修之前這個分支的 merged **完全沒有 currency**(空 live 的 attrs 是 `{}`)——
    那是三個分支裡唯一不撒謊的一個,但它把 hist 量到的觀測值整個丟掉。
    """
    hist = _series(_days(30, "2026-01-01"), [10.0] * 30, ccy="TWD")
    monkeypatch.setattr(GS, "load_series", lambda code, **_k: hist)
    merged, trace = _merge_nav_history_series(None, "X")
    assert trace and trace.get("success") is True and len(merged) == 30
    assert nav_series_currency(merged) == "TWD"


def test_merge_early_return_branch_returns_live_object_itself(monkeypatch):
    """`added <= 0` 早退分支:回傳的**就是 live 物件本身**,merged 根本沒建出來。

    釘住這件事,免得後人(或後續的稽核)以為這裡也經過 reconcile —— 它沒有,
    而且**不需要**:回傳的每一列都是 live 的列,live 自己的宣告描述的正是那些列。
    """
    live = _series(_days(5, "2026-01-01"), [10.0] * 5, ccy="USD")
    hist = _series(_days(3, "2026-01-01"), [9.0] * 3, ccy="TWD")   # 全被 live 涵蓋
    monkeypatch.setattr(GS, "load_series", lambda code, **_k: hist)
    merged, trace = _merge_nav_history_series(live, "X")
    assert merged is live                      # 同一個物件,不是新建的
    assert trace["added"] == 0 and trace["merged"] is False
    assert nav_series_currency(merged) == "USD"


# ══════════════════════════════════════════════════════════════════════
# 4. 舊列容忍:6 格舊列 → currency 空,其餘 6 欄一格不動
# ══════════════════════════════════════════════════════════════════════
def test_legacy_6col_row_reads_back_empty_currency_and_untouched_fields():
    ws = _WS([_HDR6_LEGACY,
              ["TLZF9", "2026-07-22", "12.34", "安聯", "backfill", "2026-07-22T01:02:03Z"]])
    pts = GS.load_points("TLZF9", _sheet=_Sheet(ws))
    assert pts == [{
        "code": "TLZF9",
        "date": "2026-07-22",
        "nav": 12.34,
        "fund_name": "安聯",
        "source": "backfill",
        "recorded_at": "2026-07-22T01:02:03Z",
        "currency": "",        # 誠實的未知 —— **不得**回填 TWD 或任何猜測值(§1)
    }], f"舊列讀回來變了樣(順手改壞別欄?);實得 {pts!r}"


def test_legacy_3col_min_schema_still_reads_back_empty_currency():
    """user 手動維護的最小 3 欄 schema(v19.489)照樣不炸,currency 空。"""
    ws = _WS([["code", "date", "nav"], ["ACDD19", "2020/1/2", "46.58"]])
    pts = GS.load_points("ACDD19", _sheet=_Sheet(ws))
    assert pts[0]["currency"] == "" and pts[0]["date"] == "2020-01-02"


def test_load_series_declares_currency_only_when_every_row_agrees():
    """`load_series` 逐列一致才設 `attrs["currency"]` —— 沒有這幾行,加欄是零效果。"""
    ok = _WS([_HDR7,
              ["X", "2026-07-21", "10.0", "", "app", "t", "USD"],
              ["X", "2026-07-22", "10.1", "", "app", "t", "USD"]])
    assert GS.load_series("X", _sheet=_Sheet(ok)).attrs.get("currency") == "USD"

    mixed = _WS([_HDR7,
                 ["X", "2026-07-21", "10.0", "", "app", "t", "USD"],
                 ["X", "2026-07-22", "10.1", "", "app", "t", "TWD"]])
    assert "currency" not in GS.load_series("X", _sheet=_Sheet(mixed)).attrs

    partial = _WS([_HDR7,
                   ["X", "2026-07-21", "10.0", "", "app", "t", "USD"],
                   ["X", "2026-07-22", "10.1", "", "app", "t", ""]])
    assert "currency" not in GS.load_series("X", _sheet=_Sheet(partial)).attrs


# ══════════════════════════════════════════════════════════════════════
# 5. L0 純函式 reconcile_row_currencies
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("ccys,want", [
    (["USD", "USD"], "USD"),
    (["usd", " Usd "], "USD"),
    (["USD", "TWD"], ""),        # 不一致 → 未知,絕不挑一個
    (["USD", ""], ""),           # 任一未知 → 未知(§1:不知道 ≠ 一致)
    (["USD", "美元"], ""),        # 非 ISO 三碼一律當未知,不猜
    ([], ""),                    # 沒有任何宣告可依據
    (["EUR"], "EUR"),
    ([None, "USD"], ""),
])
def test_reconcile_row_currencies(ccys, want):
    assert reconcile_row_currencies(ccys) == want
