"""repositories/portfolio_perf_repository.py — 組合績效永久快照持久化(v19.430)。L1 CRUD。

「定期追蹤投資組合績效」的**往前累積**層:每天存一列組合層績效快照,幾週後成為
可稽核的績效帳(捕捉**真實權重路徑** —— 這是「用目前權重回推過去」的走勢重建拿不到的)。
雙後端(仿 pool_repository / ~~auto_search_store~~ —— 後者已於 2026-08-31 因 production 0 caller 整檔刪除,此處僅存設計淵源):
- **Google Sheets**(secrets 有設 → 主):worksheet `_portfolio_perf_history`,跨裝置同步、reboot 不掉。
- **本地 JSON**(無 GS → fallback):`cache/portfolio_perf/perf_history.json`(Cloud FS ephemeral,dev/離線用)。

§8.2 EX-CRUD-1:本地持久化 CRUD(讀+寫同檔、無 TTL cache、無外部 HTTP fetcher),UI 可直接 import。
§1:啟用 GS 後寫入失敗 → 例外往上拋(不靜默吞、不偷偷降級,避免資料默默遺失)。

⛔ **讀寫分離(2026-09-06,客戶永久授權「查詢一律唯讀」)**
--------------------------------------------------------
**讀路徑保證零寫入**,一格都不動:

- :meth:`GoogleSheetsPerfStore._ws` — 唯讀開啟,分頁不存在 / 表頭不符 → raise
  :class:`SheetNotProvisioned`(**前提不足**,由 UI 畫成灰態,不是紅色故障)。
- :meth:`GoogleSheetsPerfStore._ws_for_write` — 補建分頁 / 補表頭,**只准從
  :meth:`~GoogleSheetsPerfStore.append_snapshot` 進來**,而它只在使用者按下快照按鈕時被呼叫。
- :class:`LocalJsonPerfStore` 的 `mkdir` 同樣搬到 `_write()`,讀路徑不碰磁碟。

**修這件事的起因(2026-09-06 離線實測,fake worksheet,零真連線)**:
`load_snapshots()` —— 一個名字是讀的函式 —— 在遠端分頁不存在時會送出
`add_worksheet` + `update("A1", ...)` **兩筆寫入**;分頁在、表頭不符時送出 `update("A1", ...)` **一筆**。
寫入藏在 `load_snapshots → _ws → add_worksheet` **兩層底下**,而且**只在遠端狀態不符預期時觸發**
—— 也就是本機測試最不容易踩到、最像「它不會寫」的那一種。
守衛:`tests/test_portfolio_perf_render_no_writes.py`。

Row schema:**以 date 為唯一鍵**(upsert;同日覆蓋最新,讓當日最終權重勝出)。
數值欄缺值一律存空字串、讀回為 None(§1 不以 0 偽裝缺值)。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

_WS_PERF = "_portfolio_perf_history"
_HEADERS = [
    "date", "period_return_pct", "cagr_pct", "ann_vol_pct", "sharpe",
    "max_drawdown_pct", "n_funds", "total_cost_twd", "is_equal_weight",
    "weights_hash", "weights_json", "coverage_start", "coverage_end",
    "n_days", "recorded_at",
]
_CACHE_DIR = Path(__file__).resolve().parent.parent / "cache" / "portfolio_perf"
_LOCAL_FILE = "perf_history.json"


@dataclass
class PerfSnapshot:
    date: str                              # ISO date(TW),唯一鍵
    period_return_pct: "float | None" = None
    cagr_pct: "float | None" = None
    ann_vol_pct: "float | None" = None
    sharpe: "float | None" = None
    max_drawdown_pct: "float | None" = None
    n_funds: int = 0
    total_cost_twd: "float | None" = None  # 成本基礎 Σ invest_twd(§B.2;非市值)
    is_equal_weight: bool = False          # 權重退等權旗標(Σ invest_twd ≤ 0 時)
    weights_hash: str = ""                 # 排序後 {code: round(w,4)} 的穩定 hash
    weights_json: str = ""                 # 歸一化權重 JSON(稽核用)
    coverage_start: str = ""
    coverage_end: str = ""
    n_days: int = 0
    recorded_at: str = ""                  # ISO ts(UTC)

    def __post_init__(self):
        self.date = str(self.date or "").strip()

    def to_row(self) -> list:
        return [_cell(getattr(self, h)) for h in _HEADERS]

    @classmethod
    def from_row(cls, row: list) -> "PerfSnapshot | None":
        if not row or not str(row[0]).strip():
            return None
        row = list(row) + [""] * (len(_HEADERS) - len(row))
        d = dict(zip(_HEADERS, row))
        return cls._from_str_map(d)

    @classmethod
    def from_dict(cls, d: dict) -> "PerfSnapshot | None":
        if not str(d.get("date", "")).strip():
            return None
        return cls._from_str_map({h: d.get(h, "") for h in _HEADERS})

    @classmethod
    def _from_str_map(cls, d: dict) -> "PerfSnapshot":
        return cls(
            date=str(d["date"]),
            period_return_pct=_num(d["period_return_pct"]),
            cagr_pct=_num(d["cagr_pct"]),
            ann_vol_pct=_num(d["ann_vol_pct"]),
            sharpe=_num(d["sharpe"]),
            max_drawdown_pct=_num(d["max_drawdown_pct"]),
            n_funds=_int(d["n_funds"]),
            total_cost_twd=_num(d["total_cost_twd"]),
            is_equal_weight=_bool(d["is_equal_weight"]),
            weights_hash=str(d["weights_hash"] or ""),
            weights_json=str(d["weights_json"] or ""),
            coverage_start=str(d["coverage_start"] or ""),
            coverage_end=str(d["coverage_end"] or ""),
            n_days=_int(d["n_days"]),
            recorded_at=str(d["recorded_at"] or ""),
        )


# ───────────────────────── 值轉換 helper(§1:缺值 = 空/None,不以 0 偽裝)─────────────

def _cell(v) -> str:
    """dataclass 值 → 儲存字串。None → ""(空);bool → "1"/"0";其餘 str()。"""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "1" if v else "0"
    return str(v)


def _num(s) -> "float | None":
    """字串 → float;空 / 壞 → None(§1 不硬填 0)。"""
    _s = str(s).strip()
    if _s == "":
        return None
    try:
        return float(_s)
    except (TypeError, ValueError):
        return None


def _int(s) -> int:
    _v = _num(s)
    return int(_v) if _v is not None else 0


def _bool(s) -> bool:
    return str(s).strip().lower() in ("1", "true", "yes")


# ───────────────────────── 本地 JSON 後端 ─────────────────────────

class LocalJsonPerfStore:
    backend_name = "local-json"

    def __init__(self, base_dir: "Path | None" = None) -> None:
        self._dir = base_dir or _CACHE_DIR
        # ⛔ **不在這裡 mkdir。** 建目錄是**寫入**,而本類別會被 `load_snapshots()`
        #    這條純讀路徑建構(`get_perf_store()` 每次都 new 一個)—— 光是渲染就會在
        #    使用者磁碟上長出一個目錄,與 GS 後端「讀路徑偷偷建分頁」是同一個病的本地版。
        #    改在 `_write()` 內就地建(見該方法)。
        self._path = self._dir / _LOCAL_FILE

    def is_available(self) -> bool:
        return True

    def _read(self) -> list:
        if not self._path.exists():
            return []
        try:
            _data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as _e:       # §1:壞檔不靜默 → log(視為空,不覆蓋原檔)
            import sys
            print(f"[portfolio_perf_repository] 本地快照讀取失敗(視為空,未動原檔):"
                  f"{type(_e).__name__}: {_e}", file=sys.stderr)
            return []
        if not isinstance(_data, list):
            import sys
            print(f"[portfolio_perf_repository] 本地快照格式非 list({type(_data).__name__})→ 視為空",
                  file=sys.stderr)
            return []
        return _data

    def _write(self, rows: list) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)   # ← 唯一會建目錄的地方(寫入時才建)
        self._path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_snapshots(self) -> list:
        import sys
        out = []
        for d in self._read():
            if not isinstance(d, dict):
                print(f"[portfolio_perf_repository] 略過非 dict 快照項目:{type(d).__name__}", file=sys.stderr)
                continue
            snap = PerfSnapshot.from_dict(d)
            if snap is not None:
                out.append(snap)
        out.sort(key=lambda s: s.date)                      # 舊 → 新(走勢畫圖友善)
        return out

    def append_snapshot(self, snap: PerfSnapshot) -> None:
        if not snap.date:
            raise ValueError("績效快照 upsert 需要 date(§1 不接受空鍵)")
        rows = [asdict(s) for s in self.load_snapshots() if s.date != snap.date]  # 同日覆蓋最新
        rows.append(asdict(snap))
        rows.sort(key=lambda r: r.get("date", ""))
        self._write(rows)


# ───────────────────────── Google Sheets 後端 ─────────────────────────

def _gs_enabled() -> bool:
    try:
        from services.macro.weights_store import _gs_enabled as _en
        return _en()
    except Exception:  # noqa: BLE001 — 偵測失敗 = 視為未啟用 → 走本地
        return False


def _get_sheet():
    """開啟與 policy/macro/pool 同一份 Google Sheet(複用 secrets),v19.430。"""
    from infra.config import require_secret
    from repositories.policy_repository import get_gspread_client
    creds = require_secret("google_service_account")   # str(JSON)/dict 皆可,get_gspread_client 正規化
    sheet_id = require_secret("macro_weights_sheet_id")
    return get_gspread_client(creds).open_by_key(sheet_id)


def _col(n: int) -> str:
    out = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out


class SheetNotProvisioned(RuntimeError):
    """遠端快照分頁還沒建好(不存在 / 表頭不符)—— **前提不足,不是系統故障**。

    為什麼要有一個專屬型別(而不是回 `[]` 或丟通用 Exception)
    ------------------------------------------------------
    這兩件事在 UI 上是**不同顏色**(客戶四大鐵律第 3 條):

    - **前提不足**(分頁還沒建、表頭還沒寫)→ 灰態 `not_ready()`,講清楚缺什麼、去哪補;
    - **系統真出錯**(憑證壞掉、Google API 500、網路斷)→ 紅色 `system_error()`。

    用通用 `Exception` 兩者就分不開,呼叫端只能猜;回 `[]` 則是**靜默吞掉**
    (`CLAUDE.md §1` 明禁)—— 使用者會看到一片空白,而且以為「本來就沒資料」。

    ⛔ **本例外不得在讀路徑內被就地「修好」**(建分頁 / 補表頭)。
    那正是本型別誕生的原因:2026-09-06 實測,`load_snapshots()` 這個**名字是讀**的函式,
    在分頁不存在時會 `add_worksheet` + `update("A1", ...)` —— **兩筆寫入藏在兩層底下,
    只在遠端狀態不符預期時才觸發**,也就是最不會被測到、最像「它不會寫」的那一種。
    補建分頁是**寫入**,只能從使用者明示的寫入動作進來(見 :meth:`GoogleSheetsPerfStore._ws_for_write`)。
    """

    def __init__(self, message: str, *, where: str = "") -> None:
        super().__init__(message)
        #: 「去哪補」—— 灰態三要素之一,由 UI 端取用(不在這層決定文案的呈現方式)。
        self.where = where


class GoogleSheetsPerfStore:
    backend_name = "google-sheets"

    def __init__(self) -> None:
        self._sh = None

    def is_available(self) -> bool:
        return _gs_enabled()

    def _ws(self):
        """**唯讀**開啟快照分頁。分頁不存在 / 表頭不符 → raise :class:`SheetNotProvisioned`。

        ⛔ **本方法保證零寫入。** 不 `add_worksheet`、不 `update`、不改任何一格。
        2026-09-06 之前這裡會就地建分頁 + 補表頭,於是**光是渲染 ④ 的績效追蹤區塊
        就會動到客戶的 Google Sheet** —— 而函式名字叫 `_ws`、呼叫端叫 `load_snapshots`,
        沒有任何一層看得出來它會寫。補建的動作已搬到 :meth:`_ws_for_write`。
        """
        if self._sh is None:
            self._sh = _get_sheet()
        try:
            ws = self._sh.worksheet(_WS_PERF)
        except Exception as _e:                                # 分頁不存在 → 前提不足,不就地建
            raise SheetNotProvisioned(
                f"雲端還沒有「{_WS_PERF}」這個快照分頁",
                where="本區的「💾 存一筆今天的績效快照」按鈕(按一次就會幫你建好)",
            ) from _e
        if ws.row_values(1)[: len(_HEADERS)] != _HEADERS:      # 表頭不符 → 同上,不就地補
            raise SheetNotProvisioned(
                f"雲端「{_WS_PERF}」分頁的表頭與目前欄位定義不符",
                where="本區的「💾 存一筆今天的績效快照」按鈕(按一次會補好表頭再寫)",
            )
        return ws

    def _ws_for_write(self):
        """**寫入前**開啟:分頁不存在就建、表頭不符就補,然後回傳。

        ⛔ **只准從使用者明示的寫入動作進來**(目前唯一入口是 :meth:`append_snapshot`,
        而它唯一的 production 呼叫端是 ④ 那顆快照按鈕的 `if` 正分支)。
        任何「順路確保一下分頁存在」的用法都是把寫入偷渡回讀路徑,禁止。
        """
        try:
            return self._ws()                                  # 已備妥 → 零寫入直接用
        except SheetNotProvisioned:
            pass
        if self._sh is None:                                   # pragma: no cover — _ws() 已建過
            self._sh = _get_sheet()
        try:
            ws = self._sh.worksheet(_WS_PERF)
        except Exception:
            ws = self._sh.add_worksheet(title=_WS_PERF, rows=400, cols=len(_HEADERS))
        ws.update("A1", [_HEADERS])
        return ws

    def load_snapshots(self) -> list:
        rows = self._ws().get_all_values()[1:]
        out = []
        for row in rows:
            snap = PerfSnapshot.from_row(row)
            if snap is not None:
                out.append(snap)
        out.sort(key=lambda s: s.date)
        return out

    def append_snapshot(self, snap: PerfSnapshot) -> None:
        if not snap.date:
            raise ValueError("績效快照 upsert 需要 date(§1 不接受空鍵)")
        ws = self._ws_for_write()          # ← 明示寫入動作才走得到這裡(見該方法 docstring)
        rows = ws.get_all_values()
        for idx, row in enumerate(rows[1:], start=2):
            if row and str(row[0]).strip() == snap.date:       # 同日覆蓋最新
                ws.update(f"A{idx}:{_col(len(_HEADERS))}{idx}", [snap.to_row()])
                return
        # RAW(非 USER_ENTERED):date 主鍵 "2026-08-11" 若被 Sheets 解析成日期型,
        # get_all_values 會回顯示字串(如 "8/11/2026")→ 破壞字串比對去重 → 同日重複列。
        # 與上面 in-place update(gspread 預設 RAW)一致,主鍵欄一律存字面值。
        ws.append_row(snap.to_row(), value_input_option="RAW")


# ───────────────────────── 後端選擇 + 便利函式 ─────────────────────────

def get_perf_store():
    """GS 可用 → GS;否則本地 JSON(§1:主後端明確,不靜默雙寫)。"""
    gs = GoogleSheetsPerfStore()
    if gs.is_available():
        return gs
    return LocalJsonPerfStore()


def load_snapshots() -> list:
    """讀快照歷史。**零寫入**(§1:不就地補建、不靜默回空)。

    :raises SheetNotProvisioned: 雲端分頁還沒建好 / 表頭不符 —— **前提不足,不是故障**。
        呼叫端應畫成**灰態**(`not_ready`),不要畫成紅色錯誤,也不要吞掉當成「沒資料」。
    """
    return get_perf_store().load_snapshots()


def append_snapshot(snap: PerfSnapshot) -> None:
    get_perf_store().append_snapshot(snap)


def is_enabled() -> bool:
    """GS 後端是否啟用(secrets 齊備)。False = 走本地 JSON。"""
    return _gs_enabled()


__all__ = [
    "PerfSnapshot", "SheetNotProvisioned", "LocalJsonPerfStore", "GoogleSheetsPerfStore",
    "get_perf_store", "load_snapshots", "append_snapshot", "is_enabled",
]

# 欄位順序一致性守門:PerfSnapshot 欄位須與 _HEADERS 對齊(漂移即炸,§1)
assert [f.name for f in fields(PerfSnapshot)] == _HEADERS, \
    "PerfSnapshot 欄位與 _HEADERS 不同步 —— 兩者須一致(row 序列化依賴此順序)"
