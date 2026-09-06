"""tests/test_nav_history_grid_limits.py — nav_history 分頁「網格寬度」守衛(2026-09-06 P0)。

這個檔為什麼存在
----------------
`currency` 第 7 欄併入後,`weekly_nav_backfill` 連續多天寫入失敗,使用者的雲端 NAV
從 2026-09-01 起停止累積。**一手證據**(2026-09-06 於 GitHub Actions 以唯讀方式讀
使用者那張 Sheet 的 gridProperties,原樣照錄):

    DIAG expected_headers_len: 7
    DIAG worksheet: {"title": "nav_history", "rowCount": 22254, "colCount": 6}
    DIAG gridProperties: {"rowCount": 22254, "columnCount": 6}
    DIAG header_len: 6
    DIAG header: ["code", "date", "nav", "fund_name", "source", "recorded_at"]

分頁是 **6 欄**建的(`add_worksheet(..., cols=len(_NAV_HEADERS))`,建立當日 `_NAV_HEADERS`
還是 6),`gridProperties.columnCount` **不會**因為後來常數變長而自己長寬 →
`_get_worksheet` 對 `G1` 發 `values.update` → Sheets 回 400
`Range (nav_history!G1) exceeds grid limits. Max rows: 22254, Max columns: 6`。

⚠️ **過期的是「兩樣」東西,守衛必須兩半都釘住(2026-09-06 總管複驗指出)**
------------------------------------------------------------------------
證據裡有兩個 6,不是同一個:

  (a) **網格寬度** `columnCount: 6`  —— 實體上只有 A..F 欄,寫 G 欄直接 400;
  (b) **表頭列內容** `header_len: 6` —— 第 1 列只有 6 個欄名,沒有 `currency`。

只補 (a) 會「寫得進去、但第 7 欄沒有欄名」。本 repo 現行的 `nav_history` 讀取端
(`load_points` 的 `ws.get_all_values()[1:]`)是**逐位置**取值、跳過第 1 列,
所以那不會立刻壞掉 —— 但 (1) 這張表使用者會**用眼睛看、用手維護**,一欄無名的
USD/TWD 沒有人看得懂;(2) 任何一天有人改用 header 當 key 的讀法,
`gspread.utils.to_records` 對空欄名**不會拋例外,而是產生一個 `''` key**(本機實測),
那正是 §1 最怕的**靜默**失敗。
→ 故 (a)(b) 兩半各有自己的測試,見 `test_the_header_row_ends_up_seven_wide_...`。

⛔ 為什麼既有的 `tests/test_nav_history_currency_column.py` 抓不到(這才是重點)
------------------------------------------------------------------------------
該檔的假件 `_WS` **沒有 `col_count` / `row_count` 的概念** —— 它的 `update` 會自己
`row.append("")` 把列補長,`append_rows` 直接 `self.rows.extend(...)`。
也就是說:**那個假 worksheet 是無限寬的,永遠不可能回 `exceeds grid limits`**,
所以這個 bug 在 CI 裡**結構上不可能被抓到**,不是「剛好沒測到」。
本檔補的就是那個維度:一個**有邊界**的假 worksheet。

⚠️ 本檔假件在一處**比真實 API 嚴格**,刻意如此,不得被引用為 API 行為的證據
------------------------------------------------------------------------------
`append_rows` 這裡在「列比網格寬」時會拋。**真實 `values.append` 到底會不會自動擴欄,
本批沒有查證**(gspread 的 docstring 自稱會,但它的實作對此沒有做任何事,等於在轉述
Sheets API 行為;要實測必須真的往某張表寫,而本批禁止對使用者的表做驗證性寫入)。
故意讓假件從嚴的理由:**修復不應該依賴一個沒查證過的行為** ——
`_ensure_grid_width` 在兩條寫入路徑之前就把網格補寬,誰會不會自動擴欄都不影響結果。
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from services import nav_history_gs as GS  # noqa: E402

# 字面表頭,刻意不引用 `GS._NAV_HEADERS` —— 引用它的話,常數再變長一次時
# 這些測試會跟著「自動同意」,而那正是本次事故的形狀。
_HDR6_LEGACY = ["code", "date", "nav", "fund_name", "source", "recorded_at"]
_HDR3_MIN = ["code", "date", "nav"]


class _GridExceeded(Exception):
    """模擬 Sheets 對「寫到網格外」回的 400,訊息形狀照抄 production 實際收到的那一句。"""


def _col0(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


class _GridWS:
    """有**邊界**的最小 gspread worksheet 假件。

    與既有 `_WS` 的唯一差別,也是本檔全部的價值:它知道自己有幾欄,
    寫到欄外會像真的 Sheets 一樣拋 400。
    """

    def __init__(self, rows, *, col_count, row_count=1000):
        self.rows = [list(r) for r in rows]
        self._cols = int(col_count)
        self._rows_cap = int(row_count)
        self.calls: list = []          # 依序記下每一次動作,用來驗「補寬發生在寫入之前」
        self.updates: list = []
        self.appended: list = []
        self.add_cols_calls: list = []
        self.resize_calls: list = []

    # gspread 的 col_count / row_count 是 property，讀 _properties["gridProperties"]
    @property
    def col_count(self) -> int:
        return self._cols

    @property
    def row_count(self) -> int:
        return self._rows_cap

    def resize(self, rows=None, cols=None):
        """**絕對值**語意 —— 照抄 gspread 6.2.1:送 gridProperties.columnCount。

        比現在小就是**刪欄**;憲法禁止寫死絕對值,理由就在這裡。
        """
        self.resize_calls.append((rows, cols))
        self.calls.append(("resize", rows, cols))
        if cols is not None:
            self._cols = int(cols)
        if rows is not None:
            self._rows_cap = int(rows)

    def add_cols(self, cols: int):
        """gspread 6.2.1 實測原始碼就是 `self.resize(cols=self.col_count + cols)`。"""
        self.add_cols_calls.append(int(cols))
        self.calls.append(("add_cols", int(cols)))
        self.resize(cols=self._cols + int(cols))

    def _guard(self, rng: str, last_col0: int, last_row0: int):
        if last_col0 >= self._cols or last_row0 >= self._rows_cap:
            raise _GridExceeded(
                f"APIError: [400]: Range (nav_history!{rng}) exceeds grid limits. "
                f"Max rows: {self._rows_cap}, Max columns: {self._cols}")

    def get_all_values(self):
        return [[str(c) for c in r] for r in self.rows]

    def row_values(self, n):
        """真 gspread 會去掉尾端空格再回傳。"""
        if len(self.rows) < n:
            return []
        r = [str(c) for c in self.rows[n - 1]]
        while r and r[-1] == "":
            r.pop()
        return r

    def update(self, rng, values):
        m = re.fullmatch(r"([A-Z]+)(\d+)", str(rng))
        assert m, f"未預期的 A1 範圍格式:{rng!r}"
        c0, r0 = _col0(m.group(1)), int(m.group(2)) - 1
        vals = list(values[0])
        self._guard(str(rng), c0 + len(vals) - 1, r0)
        self.updates.append((str(rng), [list(v) for v in values]))
        self.calls.append(("update", str(rng)))
        while len(self.rows) <= r0:
            self.rows.append([])
        row = self.rows[r0]
        while len(row) < c0 + len(vals):
            row.append("")
        row[c0: c0 + len(vals)] = vals

    def append_rows(self, rows, **_k):
        for r in rows:
            self._guard(f"A:{chr(64 + len(r))}", len(r) - 1, 0)
        self.appended.extend([list(r) for r in rows])
        self.calls.append(("append_rows", len(rows)))
        self.rows.extend([list(r) for r in rows])


class _Sheet:
    def __init__(self, ws):
        self._ws = ws

    def worksheet(self, _name):
        return self._ws


def _pt(code="AAA", date="2026-09-06", nav=10.5, ccy="USD"):
    return {"code": code, "nav": nav, "nav_date": date,
            "fund_name": "測試基金", "source": "nas_cron", "currency": ccy}


# ─────────────────────────── 正對照:證明這個假件真的會咬 ───────────────────────────

def test_the_fake_actually_bites_otherwise_a_green_suite_proves_nothing():
    """先證明假件本身有邊界 —— 否則下面每一條綠燈都只是在跟一個無限寬的假件玩。"""
    ws = _GridWS([list(_HDR6_LEGACY)], col_count=6)
    with pytest.raises(_GridExceeded) as ei:
        ws.update("G1", [["currency"]])
    assert "exceeds grid limits" in str(ei.value)
    assert "Max columns: 6" in str(ei.value)

    ws2 = _GridWS([list(_HDR6_LEGACY)], col_count=6)
    with pytest.raises(_GridExceeded):
        ws2.append_rows([["a", "b", "c", "d", "e", "f", "g"]])


# ─────────────────────────── 事故本身的回歸守衛 ───────────────────────────

def test_six_col_grid_is_widened_so_the_write_succeeds():
    """**這一條就是 2026-09-06 的事故**:6 欄網格 + 6 格表頭 + 7 欄 schema。

    沒有 `_ensure_grid_width` 時,`_get_worksheet` 會對 G1 發 update → 400 →
    `append_points` 包成 NavHistoryError,雲端一筆都寫不進去。
    """
    ws = _GridWS([list(_HDR6_LEGACY)], col_count=6, row_count=22254)
    res = GS.append_points([_pt()], _sheet=_Sheet(ws))

    assert res["written"] == 1
    assert ws.col_count >= 7, "網格沒有被補寬 → 事故重演"
    assert ws.add_cols_calls == [1], f"應該只補 1 欄,實際 {ws.add_cols_calls}"
    assert ("G1", [["currency"]]) in ws.updates, "表頭第 7 格沒有補上"
    assert len(ws.appended) == 1 and len(ws.appended[0]) == 7
    assert ws.appended[0][6] == "USD"


def test_widening_happens_before_the_first_write():
    """順序寫死:補寬必須在**任何**寫入之前,否則第一個寫入就先炸了。"""
    ws = _GridWS([list(_HDR6_LEGACY)], col_count=6)
    GS.append_points([_pt()], _sheet=_Sheet(ws))
    kinds = [c[0] for c in ws.calls]
    assert "add_cols" in kinds
    first_write = min(kinds.index(k) for k in ("update", "append_rows") if k in kinds)
    assert kinds.index("add_cols") < first_write


def test_three_col_min_schema_is_widened_and_patched():
    """user 2026-08-19 明文要求支援的 3 欄最小 schema:補 4 欄 + 補 D1:G1。"""
    ws = _GridWS([list(_HDR3_MIN)], col_count=3)
    res = GS.append_points([_pt()], _sheet=_Sheet(ws))
    assert res["written"] == 1
    assert ws.add_cols_calls == [4]
    assert ws.col_count == 7
    assert ws.updates and ws.updates[0][0] == "D1"


# ─────────────────────────── 另一半:表頭列也必須被補好 ───────────────────────────

def test_the_header_row_ends_up_seven_wide_with_currency_named():
    """(b) 半:網格補寬**之後**,第 1 列必須真的多出 `currency` 這個欄名。

    只補網格不補表頭 → 寫得進去,但第 7 欄無名。拿掉 `_get_worksheet` 的表頭補格
    那一支,本條會轉紅(補寬那幾條不會)——兩半各自有守衛,就是這個意思。
    """
    ws = _GridWS([list(_HDR6_LEGACY)], col_count=6, row_count=22254)
    GS.append_points([_pt()], _sheet=_Sheet(ws))

    hdr = ws.row_values(1)
    assert len(hdr) == 7, f"表頭沒有補到 7 格,實際 {hdr}"
    assert hdr[:6] == _HDR6_LEGACY, "既有的 6 個欄名被動到了"
    assert hdr[6] == "currency"


def test_user_authored_header_names_survive_the_widening():
    """使用者把表頭改成中文 → 補寬與補格都**不能**碰他取的名字,只補尾巴那一格。"""
    mine = ["代碼", "日期", "淨值", "基金名稱", "來源", "寫入時間"]
    ws = _GridWS([list(mine)], col_count=6)
    GS.append_points([_pt()], _sheet=_Sheet(ws))

    hdr = ws.row_values(1)
    assert hdr[:6] == mine, "使用者自己取的欄名被覆寫了"
    assert hdr[6] == "currency"
    assert [u[0] for u in ws.updates] == ["G1"], f"動到了多餘的格:{ws.updates}"


def test_min_schema_header_gets_all_four_missing_names():
    ws = _GridWS([list(_HDR3_MIN)], col_count=3)
    GS.append_points([_pt()], _sheet=_Sheet(ws))
    hdr = ws.row_values(1)
    assert hdr == ["code", "date", "nav", "fund_name", "source", "recorded_at", "currency"]


# ─────────────────────────── 不得越補越糟 ───────────────────────────

def test_a_wide_user_maintained_sheet_is_never_touched():
    """使用者自己維護到 26 欄 → **一次 resize 都不能發**(發了就可能刪掉 H..Z)。"""
    ws = _GridWS([list(_HDR6_LEGACY) + [f"我的欄{i}" for i in range(20)]], col_count=26)
    res = GS.append_points([_pt()], _sheet=_Sheet(ws))
    assert res["written"] == 1
    assert ws.resize_calls == [], f"不該動網格,實際發了 {ws.resize_calls}"
    assert ws.add_cols_calls == []
    assert ws.col_count == 26


def test_header_already_seven_wide_grid_exactly_seven_does_nothing():
    ws = _GridWS([list(_HDR6_LEGACY) + ["currency"]], col_count=7)
    res = GS.append_points([_pt()], _sheet=_Sheet(ws))
    assert res["written"] == 1
    assert ws.resize_calls == [] and ws.updates == []


def test_ensure_grid_width_is_a_no_op_on_fakes_without_col_count():
    """既有測試的假件沒有 `col_count` —— 那些測試不該因為本修復而爆掉。"""

    class _NoGrid:
        pass

    assert GS._ensure_grid_width(_NoGrid()) == 0


# ─────────────────────────── 憲法禁令仍然有效(只是射程講清楚) ───────────────────────────

def test_production_never_hardcodes_an_absolute_resize():
    """⛔ `ws.resize(cols=<字面常數>)` 一律禁止 —— 絕對值會把使用者的 H..Z 欄刪掉。

    放行的是**相對追加** `add_cols(n)`(gspread 內部雖然也是 resize,但那個絕對值
    是從當下的 `col_count` 算出來的,只會變寬)。本條用 AST,不用字面 grep。
    """
    src = (_ROOT / "services" / "nav_history_gs.py").read_text(encoding="utf-8")
    bad: list = []
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if not (isinstance(f, ast.Attribute) and f.attr == "resize"):
            continue
        for kw in node.keywords:
            if kw.arg == "cols" and isinstance(kw.value, ast.Constant):
                bad.append(ast.unparse(node))
    assert not bad, f"寫死絕對欄數的 resize:{bad}"


def test_ensure_grid_width_exists_and_is_called_by_get_worksheet():
    """守住接線本身 —— 函式在、但沒有人呼叫它,是本 repo 反覆出現的失效模式。"""
    src = (_ROOT / "services" / "nav_history_gs.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next((n for n in tree.body
               if isinstance(n, ast.FunctionDef) and n.name == "_get_worksheet"), None)
    assert fn is not None, "_get_worksheet 不見了"
    called = {ast.unparse(n.func) for n in ast.walk(fn) if isinstance(n, ast.Call)}
    assert "_ensure_grid_width" in called, "_get_worksheet 沒有呼叫 _ensure_grid_width"
