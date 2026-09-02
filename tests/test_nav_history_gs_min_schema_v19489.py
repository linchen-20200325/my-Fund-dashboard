"""v19.489:nav_history Google Sheet **最小 schema** — user 手動只維護 code|date|nav 三欄。

user 2026-08-19 要求「Sheet 只放代號+淨值(+日期),其餘系統自動」。本測試鎖:
- 3 欄 sheet(code|date|nav,無 metadata 欄)讀取 / load_series 正常。
- 跨日期格式去重:user 手填 '2020/1/2' 與系統寫的 ISO '2020-01-02' 視為同一天(不重複列)。
- append 對只給 code|date|nav 的點自動補 metadata。
"""
import services.nav_history_gs as M


class _WS:
    def __init__(self, rows):
        self.rows = rows

    def get_all_values(self):
        return [[str(c) for c in r] for r in self.rows]

    def append_rows(self, rows, **k):
        self.rows.extend([list(r) for r in rows])

    def row_values(self, n):
        """真 gspread worksheet 一定有的方法 —— `_get_worksheet` 2026-09-01 起會用它
        判斷既有分頁的表頭要不要補欄。

        ⚠️ **2026-09-01 更正(有意識的更正,不是漏刪)**:本句原寫
        ~~「照抄 `pool_repository._ws` **慣例**」~~ —— 那在 commit 1 寫下時是對的,
        但 commit 2 把表頭修補**收窄成「只補缺的那幾格、絕不寫 A1」**,
        **刻意偏離**了 `pool_repository._ws` 的整排比對慣例(理由:本模組
        逐位置讀、從不讀表頭文字,故表頭屬於使用者)。
        **改實作卻沒回頭改註解,會留下一句和 `services/nav_history_gs.py`
        正面矛盾的敘述** —— 現據實更正。"""
        return list(self.rows[n - 1]) if len(self.rows) >= n else []

    def append_row(self, r, **k):
        self.rows.append(list(r))

    def update(self, *a, **k):
        pass


class _SH:
    def __init__(self, ws):
        self._ws = ws

    def worksheet(self, name):
        return self._ws

    def add_worksheet(self, **k):
        return self._ws


# ── 3 欄最小 schema 讀取 ───────────────────────────────────────────────
def test_load_points_tolerates_3col_sheet():
    ws = _WS([["code", "date", "nav"],
              ["ACDD19", "2020/1/2", "46.58"],
              ["ACDD19", "2020/1/3", "46.32"]])
    pts = M.load_points("ACDD19", _sheet=_SH(ws))
    assert len(pts) == 2
    assert pts[0]["nav"] == 46.58
    assert pts[0]["fund_name"] == "" and pts[0]["source"] == ""   # metadata 空,不炸


def test_load_series_from_3col_sheet():
    ws = _WS([["code", "date", "nav"],
              ["ACDD19", "2020/1/2", "46.58"],
              ["ACDD19", "2020/1/6", "45.81"],
              ["ACDD19", "2020/1/3", "46.32"]])
    s = M.load_series("ACDD19", _sheet=_SH(ws))
    assert len(s) == 3
    assert str(s.index.min().date()) == "2020-01-02"
    assert str(s.index.max().date()) == "2020-01-06"
    assert s.iloc[0] == 46.58   # 昇冪排序後第一筆


# ── 跨日期格式去重(v19.489 修) ────────────────────────────────────────
def test_dedup_across_date_formats():
    """user 手填 slash '2020/1/2';系統增量寫 ISO '2020-01-02' → 同一天,不重複。"""
    ws = _WS([["code", "date", "nav"],
              ["ACDD19", "2020/1/2", "46.58"]])   # user 手填 slash
    res = M.append_points(
        [{"code": "ACDD19", "nav": 99.0, "nav_date": "2020-01-02"}],   # 系統 ISO 同一天
        _sheet=_SH(ws),
    )
    assert res["written"] == 0 and res["skipped"] == 1   # 視為重複 → 不寫
    assert len(ws.rows) == 2                              # header + 原 1 列,無新增


def test_dedup_new_date_still_written():
    ws = _WS([["code", "date", "nav"],
              ["ACDD19", "2020/1/2", "46.58"]])
    res = M.append_points(
        [{"code": "ACDD19", "nav": 45.09, "nav_date": "2020/1/7"}],   # 新日期
        _sheet=_SH(ws),
    )
    assert res["written"] == 1
    assert len(ws.rows) == 3


# ── append 自動補 metadata(user 只給 code|date|nav)─────────────────────
def test_append_autofills_metadata():
    ws = _WS([["code", "date", "nav"]])
    M.append_points([{"code": "ACDD19", "nav": 46.58, "nav_date": "2020/1/2"}], _sheet=_SH(ws))
    row = ws.rows[-1]
    assert row[0] == "ACDD19" and row[1] == "2020-01-02" and row[2] == 46.58
    assert row[4] == "app"          # source 自動
    assert row[5] and "T" in row[5]  # recorded_at 自動(ISO 時間戳)
