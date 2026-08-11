"""repositories/portfolio_perf_repository.py — 組合績效永久快照持久化(v19.430)。L1 CRUD。

「定期追蹤投資組合績效」的**往前累積**層:每天存一列組合層績效快照,幾週後成為
可稽核的績效帳(捕捉**真實權重路徑** —— 這是「用目前權重回推過去」的走勢重建拿不到的)。
雙後端(仿 pool_repository / auto_search_store):
- **Google Sheets**(secrets 有設 → 主):worksheet `_portfolio_perf_history`,跨裝置同步、reboot 不掉。
- **本地 JSON**(無 GS → fallback):`cache/portfolio_perf/perf_history.json`(Cloud FS ephemeral,dev/離線用)。

§8.2 EX-CRUD-1:本地持久化 CRUD(讀+寫同檔、無 TTL cache、無外部 HTTP fetcher),UI 可直接 import。
§1:啟用 GS 後寫入失敗 → 例外往上拋(不靜默吞、不偷偷降級,避免資料默默遺失)。

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
        self._dir.mkdir(parents=True, exist_ok=True)
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


class GoogleSheetsPerfStore:
    backend_name = "google-sheets"

    def __init__(self) -> None:
        self._sh = None

    def is_available(self) -> bool:
        return _gs_enabled()

    def _ws(self):
        if self._sh is None:
            self._sh = _get_sheet()
        try:
            ws = self._sh.worksheet(_WS_PERF)
        except Exception:
            ws = self._sh.add_worksheet(title=_WS_PERF, rows=400, cols=len(_HEADERS))
            ws.update("A1", [_HEADERS])
            return ws
        if ws.row_values(1)[: len(_HEADERS)] != _HEADERS:      # 補 header(欄位缺失時)
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
        ws = self._ws()
        rows = ws.get_all_values()
        for idx, row in enumerate(rows[1:], start=2):
            if row and str(row[0]).strip() == snap.date:       # 同日覆蓋最新
                ws.update(f"A{idx}:{_col(len(_HEADERS))}{idx}", [snap.to_row()])
                return
        ws.append_row(snap.to_row(), value_input_option="USER_ENTERED")


# ───────────────────────── 後端選擇 + 便利函式 ─────────────────────────

def get_perf_store():
    """GS 可用 → GS;否則本地 JSON(§1:主後端明確,不靜默雙寫)。"""
    gs = GoogleSheetsPerfStore()
    if gs.is_available():
        return gs
    return LocalJsonPerfStore()


def load_snapshots() -> list:
    return get_perf_store().load_snapshots()


def append_snapshot(snap: PerfSnapshot) -> None:
    get_perf_store().append_snapshot(snap)


def is_enabled() -> bool:
    """GS 後端是否啟用(secrets 齊備)。False = 走本地 JSON。"""
    return _gs_enabled()


__all__ = [
    "PerfSnapshot", "LocalJsonPerfStore", "GoogleSheetsPerfStore",
    "get_perf_store", "load_snapshots", "append_snapshot", "is_enabled",
]

# 欄位順序一致性守門:PerfSnapshot 欄位須與 _HEADERS 對齊(漂移即炸,§1)
assert [f.name for f in fields(PerfSnapshot)] == _HEADERS, \
    "PerfSnapshot 欄位與 _HEADERS 不同步 —— 兩者須一致(row 序列化依賴此順序)"
