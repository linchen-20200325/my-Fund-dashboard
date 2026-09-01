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

import re

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
    """最小 gspread worksheet 假件(真 worksheet 有的四個方法都給,不缺 `row_values`)。

    ⚠️ `update` **不是 no-op**:它記下每一次呼叫的**範圍字串**,並且**按範圍逐格套用**。
    表頭修補的整個爭點就是「**動到了哪幾格**」—— 用 no-op 假件寫的守衛,
    在「只補 G1」與「整排重寫 A1:G1」之間**分辨不出來**,等於什麼都沒證明。
    """

    def __init__(self, rows):
        self.rows = [list(r) for r in rows]
        self.updates: list = []          # [(range, values), ...]

    def get_all_values(self):
        return [[str(c) for c in r] for r in self.rows]

    def row_values(self, n):
        """真 gspread 會**去掉尾端空格**再回傳 —— 假件照做,否則「缺幾格」會算錯。"""
        if len(self.rows) < n:
            return []
        r = [str(c) for c in self.rows[n - 1]]
        while r and r[-1] == "":
            r.pop()
        return r

    def update(self, rng, values):
        self.updates.append((rng, [list(v) for v in values]))
        m = re.fullmatch(r"([A-Z]+)(\d+)", str(rng))
        assert m, f"未預期的 A1 範圍格式:{rng!r}"
        col0 = 0
        for ch in m.group(1):
            col0 = col0 * 26 + (ord(ch) - 64)
        col0 -= 1
        row0 = int(m.group(2)) - 1
        while len(self.rows) <= row0:
            self.rows.append([])
        row = self.rows[row0]
        vals = list(values[0])
        while len(row) < col0 + len(vals):
            row.append("")
        row[col0: col0 + len(vals)] = vals

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


def test_existing_6col_sheet_gets_only_the_missing_cells_filled():
    """既有 6 欄分頁 → **只補 G1 那一格**,不是整排重寫。

    ⚠️ **本則 2026-09-01 加嚴過**(原名 `test_existing_6col_sheet_gets_header_repaired_not_resized`,
       原本只斷言 `ws.rows[0] == _HDR7`)。**舊斷言保留、另外再加新斷言 —— 是加嚴,不是替換。**
       舊斷言在**兩種實作下都會通過** ——
       「整排重寫 A1:G1」與「只補 G1」對這個英文表頭 fixture 產生**完全一樣的結果**,
       所以它證明不了本函式真正的行為。現在改成斷言**動到了哪幾格**。

    ⛔ 補法**不得**用 `ws.resize(cols=…)` —— gspread 送的是**絕對值**,在使用者手動維護到
       26 欄的表上等於刪掉 H..Z 欄連同內容。本假件**刻意不提供 `resize`**:
       誰改成 resize,這裡就 AttributeError 轉紅。
    """
    ws = _WS([_HDR6_LEGACY, ["OLD", "2026-07-01", "9.9", "n", "app", "t"]])
    GS.append_points([{"code": "NEW", "nav": 1.0, "nav_date": "2026-07-22",
                       "currency": "EUR"}], _sheet=_Sheet(ws))
    assert ws.updates == [("G1", [["currency"]])], (
        f"表頭修補動到的範圍不是「只有 G1」;實得 {ws.updates!r}")
    assert ws.rows[0] == _HDR7
    assert ws.rows[-1][6] == "EUR"


def test_user_authored_headers_are_never_overwritten():
    """使用者自己取的表頭(非英文、6 格)→ **前 6 格逐格不變**,只有第 7 格被補上。

    **為什麼可以這樣做(理由必須成立,不是偷懶)**:本模組**沒有任何一處讀表頭列的文字** ——
    `load_points` / `append_points` 都是 `get_all_values()[1:]` **跳過**第 1 列,
    再以 `r[0]`..`r[6]` **逐位置**取值。表頭文字對程式**零作用**,它只是給人看的,
    因此它**屬於使用者**;而這張表使用者**會手動維護**。
    整排重寫會把他取的名字改掉,換來的好處是**零**。

    **突變**:把實作改回 `ws.update("A1", [_NAV_HEADERS])` → 本則必須轉紅。
    """
    zh = ["代碼", "日期", "淨值", "來源", "更新時間", "備註"]
    ws = _WS([list(zh), ["OLD", "2026-07-01", "9.9", "n", "app", "t"]])
    GS.append_points([{"code": "NEW", "nav": 1.0, "nav_date": "2026-07-22",
                       "currency": "JPY"}], _sheet=_Sheet(ws))

    assert ws.rows[0][:6] == zh, (
        f"使用者自己取的表頭被改掉了(前 6 格應逐格不變);實得 {ws.rows[0][:6]!r}")
    assert ws.rows[0][6] == "currency", f"第 7 格沒補上;實得 {ws.rows[0]!r}"
    assert all(r != "A1" for r, _v in ws.updates), (
        f"寫了 A1 → 覆寫了使用者的表頭;實得 {ws.updates!r}")
    assert ws.rows[-1][6] == "JPY"        # 資料照樣落在第 7 欄


def test_three_col_min_schema_gets_four_cells_filled_and_first_three_untouched():
    """**3 欄最小 schema** —— user 2026-08-19 明文要求支援的形狀(見
    `tests/test_nav_history_gs_min_schema_v19489.py` 檔頭)。

    ⚠️ **2026-09-01 稽核補**:本 PR 前一版的敘述(PR body、`_get_worksheet` 註解、
       本檔某個測試名)都寫「**只補缺的那一格 / 本批就是 G1**」——
       **那只對 6 欄表成立**。3 欄表補的是 **`D1:G1` 四格**。
       **程式一直是對的**(`_NAV_HEADERS[len(_hdr):]` 本來就一般化),
       **錯的是敘述,而且這個形狀當時沒有任何測試。**

    真正該守的不變式**與欄數無關**:**既有的那幾格,一格都不許動。**
    """
    zh3 = ["代碼", "日期", "淨值"]        # 使用者自己取的名字,而且只有 3 欄
    ws = _WS([list(zh3), ["OLD", "2020/1/2", "46.58"]])
    GS.append_points([{"code": "NEW", "nav": 1.0, "nav_date": "2026-07-22",
                       "currency": "GBP"}], _sheet=_Sheet(ws))

    assert ws.updates == [("D1", [["fund_name", "source", "recorded_at", "currency"]])], (
        f"3 欄表補的應該是 D1:G1 四格,而且不得碰 A1:C1;實得 {ws.updates!r}")
    assert ws.rows[0][:3] == zh3, (
        f"使用者的 3 欄表頭被改掉了;實得 {ws.rows[0][:3]!r}")
    assert ws.rows[0] == zh3 + ["fund_name", "source", "recorded_at", "currency"]
    assert ws.rows[-1][6] == "GBP"        # 資料照樣落在第 7 欄


def test_header_already_full_length_is_left_completely_alone():
    """表頭長度已達 7 → **什麼都不做**(一次 update 都不發)。"""
    zh7 = ["代碼", "日期", "淨值", "來源", "更新時間", "備註", "幣別"]
    ws = _WS([list(zh7), ["OLD", "2026-07-01", "9.9", "n", "app", "t", "USD"]])
    GS.append_points([{"code": "NEW", "nav": 1.0, "nav_date": "2026-07-22"}],
                     _sheet=_Sheet(ws))
    assert ws.updates == [], f"表頭已足長卻還去動它;實得 {ws.updates!r}"
    assert ws.rows[0] == zh7


def test_blank_header_row_gets_the_full_header():
    """第 1 列整列空白(全新 / 空白工作表)→ 寫整排沒有覆寫任何東西,可以照寫。"""
    ws = _WS([["", "", ""]])
    GS.append_points([{"code": "NEW", "nav": 1.0, "nav_date": "2026-07-22"}],
                     _sheet=_Sheet(ws))
    assert ws.updates == [("A1", [_HDR7])]
    assert ws.rows[0] == _HDR7


@pytest.mark.parametrize("idx0,want", [(0, "A"), (5, "F"), (6, "G"), (25, "Z"),
                                       (26, "AA"), (27, "AB")])
def test_a1_col(idx0, want):
    assert GS._a1_col(idx0) == want


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
# 5. `backfill_to_gs` 的幣別寫入路徑(**第二個寫入端**)
#
# ⚠️ **這一段是 2026-09-01 獨立稽核擋下 PR 後補的,原因要寫清楚**:
#    本 PR 自陳「補上寫入端的列形狀契約」,但**兩個寫入端只守了一個** ——
#    `ui/helpers/nav_history_hook.py` 有守,`backfill_to_gs` **零守衛**。
#    稽核實跑兩個突變,**全套 6310 passed 一顆都沒紅**:
#      突變 1:換源時幣別不跟隨(退回 3-tuple 語意)→ 全綠
#      突變 2:`"currency": _ccy` → `"currency": ""`(永遠不寫幣別)→ 全綠
#    而突變 1 當場重現了本 PR 要修的那個造假:MoneyDJ(USD, 30 天) 被
#    yahoo(EUR, 600 天) 換掉之後,**600 列全部掛上已經被丟棄那條序列的 USD 宣告**。
#    憲法明列「突變測試(拔掉修復邏輯必須轉為紅燈)」是必做項 —— 沒有這一段,
#    本 PR 最核心的那個修法**沒有任何測試看著它**,而這張表是**永不刪除**的。
# ══════════════════════════════════════════════════════════════════════
@pytest.fixture
def _cache_store(monkeypatch):
    """本地 cache 讀寫改記憶體(不碰磁碟)。慣例同 `tests/test_nav_currency_swap_guard.py`。"""
    import services.nav_history_store as NS
    store: dict = {}
    monkeypatch.setattr(NS, "_load_cache_series",
                        lambda code: store.get(code, pd.Series(dtype=float)))
    monkeypatch.setattr(NS, "_save_cache_series",
                        lambda code, s: store.__setitem__(code, s))
    return store


def _wire_backfill(monkeypatch, *, fd, yahoo=None, morningstar=None, cnyes=None,
                   isin="LU0000000001", pool_ccy=None):
    """接上每日排程實際走的那條鏈的所有外部邊界,回傳「寫進雲端的點」。

    慣例沿用 `tests/test_nav_currency_swap_guard.py::_wire_l2`(同一條鏈、同一組邊界)。
    `load_points` 回 `[]` → Gate 0 零重疊 → verdict `clean` 放行
    (那是 Gate 0 的**已知破口 a**,本節刻意利用它把幣別這條線單獨隔離出來測)。

    三個候選源與 `isin` 都可獨立指定,才驅動得到 `_rescue_by_isin` 的**每一個出口**:
    傳 `None` = 回空序列;傳 **Exception 實例** = 該源拋例外;傳 Series = 該源回那條序列。
    `isin=None` = 池中沒有 ISIN(救援 gate 不成立)。
    """
    import repositories.fund.sources as SRC
    import repositories.pool_repository as POOL
    import services.moneydj_fetcher as MF
    import services.nav_history_gs as _GS

    _empty = pd.Series(dtype=float)

    def _src(v):
        if isinstance(v, BaseException):
            raise v
        return _empty if v is None else v

    monkeypatch.setattr(MF, "auto_fetch_moneydj", lambda code, **kw: fd)
    monkeypatch.setattr(POOL, "resolve_isin", lambda code: isin)
    monkeypatch.setattr(POOL, "resolve_currency", lambda code: pool_ccy)
    monkeypatch.setattr(SRC, "_src_yahoo_finance_nav", lambda code: _src(yahoo))
    monkeypatch.setattr(SRC, "_src_morningstar_nav",
                        lambda code, fund_name="": _src(morningstar))
    monkeypatch.setattr(SRC, "_src_cnyes_nav", lambda code: _src(cnyes))
    monkeypatch.setattr(_GS, "is_enabled", lambda: True)
    monkeypatch.setattr(_GS, "load_points", lambda code=None, **kw: [])
    written: list = []

    def _append(points, **kw):
        written.extend(points)
        return {"written": len(points), "skipped": 0}

    monkeypatch.setattr(_GS, "append_points", _append)
    return written


def _daily(n, start="2020-01-01", ccy=None):
    return _series(_days(n, start), [10.0 + i * 0.001 for i in range(n)], ccy=ccy)


def test_backfill_writes_the_currency_measured_on_the_series(monkeypatch, _cache_store):
    """`backfill_to_gs` 寫入的每一點都帶**序列量到的**幣別。

    序列夠長(跨度 > `_SPAN_TARGET_DAYS`)→ 不觸發 ISIN 救援,單獨隔離「基本路徑」。

    **突變**:`"currency": _ccy` → `"currency": ""` → 本則必須轉紅。
    """
    import services.nav_history_store as NS
    written = _wire_backfill(monkeypatch, fd={"series": _daily(2000, ccy="USD"),
                                              "fund_name": "F"})
    out = NS.backfill_to_gs(["X"])
    assert out["results"][0]["fetched"] == 2000 and out["results"][0]["source"] == "moneydj"
    assert written, "沒有任何點被寫進雲端 → 本則什麼都沒測到"
    assert {p["currency"] for p in written} == {"USD"}, (
        f"寫入的幣別不是序列量到的值;實得 {sorted({p['currency'] for p in written})!r}")


def test_backfill_currency_follows_the_adopted_series_when_rescue_swaps_source(
        monkeypatch, _cache_store):
    """⭐ **本 PR 最核心的那個修法,這是唯一看著它的守衛。**

    MoneyDJ(USD、30 天)跨度不足 → `_rescue_by_isin` 換成 yahoo(EUR、600 天)。
    被寫入的 600 列**每一列都來自 yahoo**,所以幣別必須是 **EUR**;
    掛上 MoneyDJ 那條**已經被丟棄**的序列的 USD 宣告 = §1 明令禁止的憑空編造,
    而且會**永久**留在 `nav_history`(去重鍵 `(code, date)`、永不刪除)。

    **突變**:把換源時的幣別跟隨拿掉(退回 3-tuple 語意)——
    `s, src, _cur = _cand, f"{_name}(ISIN)", _span(_cand)` → 本則必須轉紅
    (實測突變後 `currency` 集合會變成 `{'USD'}`)。
    """
    import services.nav_history_store as NS
    written = _wire_backfill(
        monkeypatch,
        fd={"series": _daily(30, "2025-01-01", ccy="USD"), "fund_name": "F"},
        yahoo=_daily(600, "2020-01-01", ccy="EUR"))
    r = NS.backfill_to_gs(["X"])["results"][0]
    assert "yahoo" in (r["source"] or ""), (
        f"救援沒有換源 → 本則沒測到要測的東西;實得 source={r['source']!r}")
    assert written, "沒有任何點被寫進雲端 → 本則什麼都沒測到"
    _got = {p["currency"] for p in written}
    assert _got == {"EUR"}, (
        f"換源後幣別沒有跟著換 —— 被丟棄那條序列的宣告被掛到 {len(written)} 列上;"
        f"實得 {sorted(_got)!r}")
    assert "USD" not in _got, "MoneyDJ 的宣告出現在 yahoo 的列上(§1 憑空編造)"


def test_backfill_never_falls_back_to_fd_currency(monkeypatch, _cache_store):
    """第二個寫入端同樣**不得**退回 `fd["currency"]`(宣告線)。

    fixture 刻意讓兩條線矛盾:`fd["currency"]="TWD"`、序列不宣告 → 必須寫 `""`。
    """
    import services.nav_history_store as NS
    written = _wire_backfill(monkeypatch,
                             fd={"series": _daily(2000), "currency": "TWD",
                                 "fund_name": "F"})
    NS.backfill_to_gs(["X"])
    assert written and {p["currency"] for p in written} == {""}, (
        f"取到了「宣告線」(fd['currency'])而不是「量測線」;"
        f"實得 {sorted({p['currency'] for p in written})!r}")


# ── 5.1 `_rescue_by_isin` 的**每一個出口**,不是只有 happy path ─────────────
#
# ⚠️ **這一組是 2026-09-01 第二輪稽核挖出來的,原因比洞本身重要**:
#    上面三條守衛**只驅動「一次成功換源」這一條路徑**(yahoo 成功、其餘回空)。
#    而 `_rescue_by_isin` 實際有**六條**互不相同的路徑,只有其中一條被守到:
#      (1) `resolve_isin` 拋例外 → 提早 return(序列不變)
#      (2) 池中沒有 ISIN        → 提早 return(序列不變)          ← M6
#      (3) 某個候選源拋例外      → `continue`(序列不變)
#      (4) **採用門檻不成立**    → 整個 if 不進去,連 `_assess_swap` 都沒走到(序列不變)
#      (5) 候選**因幣別被拒**    → `continue`(序列不變)            ← M7
#      (6) 採用                 → 賦值,**而且迴圈還會繼續**(可重複)  ← M8
#    ⚠️ **稽核給的清單是四條,把 (3) 與 (5) 併成一條、且漏掉 (4)** ——
#    本組讀碼後逐條數出**六條**,(3)(4) 是稽核沒點名的,一併補守衛。
#    ⚠️ 「六條」是本組讀碼歸納,**不宣稱窮舉**;驗證方式見 PR 描述。
#
# **通則(留給下一個人的一句話)**:
#   **守衛要覆蓋函式的每一個出口,不是只覆蓋 happy path。**
#   「補了兩格」不代表沒有第三格 —— 這三個洞全部長在 `if`/`continue`/`return`
#   的**非主線分支**上,而它們寫進的是一張**永不刪除**的表。
def test_rescue_refused_on_currency_keeps_the_original_series_declaration(
        monkeypatch, _cache_store):
    """⛔ **最嚴重的一個**:候選**因幣別對不上被拒絕**時,幣別不得被那個候選污染。

    `_assess_swap` 判定「候選幣別對不上 → 拒絕採用」→ 序列**沒有換**,留下 MoneyDJ
    那 30 列;但被拒絕那個候選的 `EUR` **絕不能**被蓋到那 30 列上 —— 那是 §1 憑空編造,
    而且**發生在唯一一道幣別守門的 else 分支裡**(這條路真的會走到:`ccy_refused`
    是 cron summary 有在報的欄位)。

    **突變**:在 `_ccy_notes.append(...)` 之後、`continue` 之前加 `cur_ccy = _cand_ccy`
    → 本則必須轉紅(實測突變前該突變**完全沉默**:nav 十二個測試檔 230 passed)。
    """
    import services.nav_history_store as NS
    written = _wire_backfill(
        monkeypatch,
        fd={"series": _daily(30, "2025-01-01", ccy="USD"), "currency": "USD",
            "fund_name": "F"},
        yahoo=_daily(600, "2020-01-01", ccy="EUR"))       # 幣別對不上 → 必被拒
    r = NS.backfill_to_gs(["X"])["results"][0]
    assert r["ccy_refused"], "本則沒有走到「因幣別被拒」那條分支 → 什麼都沒測到"
    assert r["source"] == "moneydj", f"序列不該被換掉;實得 source={r['source']!r}"
    _got = {p["currency"] for p in written}
    assert _got == {"USD"}, (
        f"被**拒絕**的候選的幣別被蓋到留下來那條序列上(§1 憑空編造);實得 {sorted(_got)!r}")
    assert "EUR" not in _got


def test_rescue_without_isin_keeps_the_measured_currency(monkeypatch, _cache_store):
    """池中**沒有 ISIN**(救援 gate 不成立)→ 幣別必須原封留著,不得掉成空字串。

    這不是造假,是**靜默資料遺失** —— 但它落在**多數路徑**上(救援的 gate 原文就是
    「池中有 ISIN 才觸發」,退回 MoneyDJ 短窗是常態),而這張表**永不刪除**:
    空掉的那一格**以後補不回來**(本 PR 自己的原則:既有列一律留空、不得回填)。

    **突變**:`if not _isin: return s, src, _ccy_notes, ""` → 本則必須轉紅。
    """
    import services.nav_history_store as NS
    written = _wire_backfill(
        monkeypatch, isin=None,                          # ← 池中沒有 ISIN
        fd={"series": _daily(30, "2025-01-01", ccy="USD"), "fund_name": "F"},
        yahoo=_daily(600, "2020-01-01", ccy="EUR"))      # 永遠不會被查詢
    r = NS.backfill_to_gs(["X"])["results"][0]
    assert r["source"] == "moneydj" and r["fetched"] == 30
    assert {p["currency"] for p in written} == {"USD"}, (
        f"沒有 ISIN 就把量到的幣別弄丟了(靜默資料遺失,永久補不回);"
        f"實得 {sorted({p['currency'] for p in written})!r}")


def test_rescue_consecutive_swaps_currency_tracks_the_last_adopted_source(
        monkeypatch, _cache_store):
    """**連續換源**:yahoo(EUR, 300 天)→ morningstar(JPY, 600 天)→ 幣別必須是 **JPY**。

    迴圈會**連續採用**:被寫入的每一列最後都來自 morningstar,幣別若凍在**第一個**
    被採用的候選(EUR),序列是最後一個的、宣告卻是第一個的 ——
    **與本 PR 修的是同一個造假,只是晚一圈迴圈。**

    **突變**(對既有守衛真正沉默的那一版,本組實測 230 passed):
    只在「第一次採用」時設幣別 —— `if not src.endswith("(ISIN)"): cur_ccy = _cand_ccy`
    → 本則必須轉紅。
    ⚠️ 本組第一版突變寫成 `cur_ccy = cur_ccy or _cand_ccy`,**被上面那條單次換源守衛
    抓到了**(因為該 fixture 的 MoneyDJ 有宣告 USD)—— 那不是忠實的「沉默突變」,
    據實記下來,免得後人以為隨便寫個突變就能證明覆蓋度。
    """
    import services.nav_history_store as NS
    written = _wire_backfill(
        monkeypatch,
        fd={"series": _daily(30, "2025-01-01"), "fund_name": "F"},   # MoneyDJ 不宣告
        yahoo=_daily(300, "2024-01-01", ccy="EUR"),
        morningstar=_daily(600, "2020-01-01", ccy="JPY"))
    r = NS.backfill_to_gs(["X"])["results"][0]
    assert "morningstar" in (r["source"] or ""), (
        f"沒有連續換到 morningstar → 本則沒測到要測的東西;實得 source={r['source']!r}")
    _got = {p["currency"] for p in written}
    assert _got == {"JPY"}, (
        f"幣別凍在第一個被採用的候選,序列卻是最後一個的;實得 {sorted(_got)!r}")
    assert "EUR" not in _got


def test_rescue_candidate_below_adoption_threshold_does_not_touch_currency(
        monkeypatch, _cache_store):
    """**採用門檻不成立**(候選 < 10 筆)→ 連 `_assess_swap` 都沒走到,幣別不得變。

    ⚠️ **這條路徑稽核的四出口清單沒有點名**(本組讀碼時數出來的第 (4) 條)。
    它是實務上最常走的一條:候選源回了東西、但稀疏或跨度不夠 → 不採用。
    """
    import services.nav_history_store as NS
    written = _wire_backfill(
        monkeypatch,
        fd={"series": _daily(30, "2025-01-01", ccy="USD"), "fund_name": "F"},
        yahoo=_daily(5, "2020-01-01", ccy="EUR"))     # 只有 5 筆 → 門檻不成立
    r = NS.backfill_to_gs(["X"])["results"][0]
    assert r["source"] == "moneydj" and not r["ccy_refused"], (
        "本則應該連幣別守門都沒走到(門檻先擋掉),實際卻走到了 → fixture 沒對準")
    assert {p["currency"] for p in written} == {"USD"}


def test_rescue_all_sources_raising_keeps_the_measured_currency(
        monkeypatch, _cache_store):
    """**三個候選源全部拋例外** → 三次 `continue`,幣別必須原封不動。

    ⚠️ 同樣是稽核四出口清單沒點名的一條(本組數出來的第 (3) 條,且此處是**三源組合**)。
    """
    import services.nav_history_store as NS
    written = _wire_backfill(
        monkeypatch,
        fd={"series": _daily(30, "2025-01-01", ccy="USD"), "fund_name": "F"},
        yahoo=RuntimeError("yahoo down"),
        morningstar=RuntimeError("ms down"),
        cnyes=RuntimeError("cnyes down"))
    r = NS.backfill_to_gs(["X"])["results"][0]
    assert r["source"] == "moneydj" and r["fetched"] == 30
    assert {p["currency"] for p in written} == {"USD"}


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
