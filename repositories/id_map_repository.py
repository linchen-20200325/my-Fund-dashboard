"""repositories/id_map_repository.py — 基金代號對照表持久化(v19.469)。L1 CRUD。

使用者自維護的「基金代號對照表」:把台灣/MoneyDJ 內部碼(如 ALZF9)對到國際識別碼
(晨星 secId / ISIN / 幣別 / 名稱)。用途:MoneyDJ 抓不到某檔淨值時,拿對到的**晨星 secId**
走既有 `repositories.fund.sources._src_morningstar_nav`(secId → Yahoo chart)補淨值。

背景(user 2026-08-18 提案):硬編 `_MORNINGSTAR_SECID_MAP` 只有幾檔、且不能自己加 →
做成**可自編輯的表**。你把 code→secId/ISIN 填進來,就解鎖那條晨星補淨值路。

雙後端(仿 pool_repository,存**同一本** POLICY_SHEET_ID,不同 worksheet):
- Google Sheets(主):worksheet `_fund_id_map`,你在自己的 Sheet 直接編。
- 本地 JSON fallback:`cache/fund_id_map/id_map.json`(Cloud FS ephemeral,dev/離線)。

§8.2 EX-CRUD-1:本地持久化 CRUD,UI 可直接 import。復用 pool_repository 的 `_get_sheet`/
`_gs_enabled`/`_col`(同一本 book 的 GS plumbing,避免重造 30 行)。
§1:GS 寫入失敗 → 例外往上拋(不靜默);`resolve_secid` 讀不到 → None(退硬編表/搜尋,不阻斷)。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from repositories.pool_repository import _col, _get_sheet, _gs_enabled

_WS_IDMAP = "_fund_id_map"
_HEADERS = ["code", "morningstar_secid", "isin", "currency", "name"]
_CACHE_DIR = Path(__file__).resolve().parent.parent / "cache" / "fund_id_map"
_LOCAL_FILE = "id_map.json"


@dataclass
class IdMapEntry:
    code: str
    morningstar_secid: str = ""
    isin: str = ""
    currency: str = "USD"
    name: str = ""

    def __post_init__(self):
        self.code = str(self.code or "").strip().upper()
        self.morningstar_secid = str(self.morningstar_secid or "").strip()
        self.isin = str(self.isin or "").strip().upper()
        self.currency = str(self.currency or "").strip().upper() or "USD"
        self.name = str(self.name or "").strip()

    def to_row(self) -> list:
        return [self.code, self.morningstar_secid, self.isin, self.currency, self.name]

    @classmethod
    def from_row(cls, row) -> "IdMapEntry | None":
        if not row or not str(row[0]).strip():
            return None
        row = list(row) + [""] * (len(_HEADERS) - len(row))
        return cls(code=str(row[0]), morningstar_secid=str(row[1] or ""),
                   isin=str(row[2] or ""), currency=str(row[3] or ""), name=str(row[4] or ""))

    @classmethod
    def from_dict(cls, d: dict) -> "IdMapEntry":
        return cls(**{k: d.get(k, "") for k in _HEADERS})


# ───────────────────────── 本地 JSON 後端 ─────────────────────────

class LocalJsonIdMapStore:
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
        except (json.JSONDecodeError, OSError) as _e:      # §1:壞檔不靜默 → log(不覆蓋原檔)
            import sys
            print(f"[id_map_repository] 本地對照表讀取失敗(視為空,未動原檔):"
                  f"{type(_e).__name__}: {_e}", file=sys.stderr)
            return []
        if not isinstance(_data, list):
            import sys
            print(f"[id_map_repository] 本地對照表格式非 list({type(_data).__name__})→ 視為空",
                  file=sys.stderr)
            return []
        return _data

    def _write(self, rows: list) -> None:
        self._path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_id_map(self) -> list:
        import sys
        out = []
        for d in self._read():
            if not isinstance(d, dict):
                print(f"[id_map_repository] 略過非 dict 項目:{type(d).__name__}", file=sys.stderr)
                continue
            try:
                e = IdMapEntry.from_dict(d)
                if e.code:
                    out.append(e)
            except (TypeError, ValueError) as _e:
                print(f"[id_map_repository] 略過壞損項目:{type(_e).__name__}: {_e}", file=sys.stderr)
                continue
        return out

    def upsert(self, entry: IdMapEntry) -> None:
        if not entry.code:
            raise ValueError("對照表 upsert 需要 code(§1 不接受空鍵)")
        rows = [asdict(e) for e in self.list_id_map() if e.code != entry.code]
        rows.append(asdict(entry))
        self._write(rows)

    def remove(self, code: str) -> None:
        code = str(code or "").strip().upper()
        self._write([asdict(e) for e in self.list_id_map() if e.code != code])


# ───────────────────────── Google Sheets 後端 ─────────────────────────

class GoogleSheetsIdMapStore:
    backend_name = "google-sheets"

    def __init__(self) -> None:
        self._sh = None

    def is_available(self) -> bool:
        return _gs_enabled()

    def _ws(self):
        if self._sh is None:
            self._sh = _get_sheet()
        try:
            ws = self._sh.worksheet(_WS_IDMAP)
        except Exception:
            ws = self._sh.add_worksheet(title=_WS_IDMAP, rows=200, cols=len(_HEADERS))
            ws.update("A1", [_HEADERS])
            return ws
        if ws.row_values(1)[: len(_HEADERS)] != _HEADERS:
            ws.update("A1", [_HEADERS])
        return ws

    def list_id_map(self) -> list:
        rows = self._ws().get_all_values()[1:]
        out = []
        for row in rows:
            e = IdMapEntry.from_row(row)
            if e is not None:
                out.append(e)
        return out

    def upsert(self, entry: IdMapEntry) -> None:
        if not entry.code:
            raise ValueError("對照表 upsert 需要 code(§1 不接受空鍵)")
        ws = self._ws()
        rows = ws.get_all_values()
        for idx, row in enumerate(rows[1:], start=2):
            if row and str(row[0]).strip().upper() == entry.code:
                ws.update(f"A{idx}:{_col(len(_HEADERS))}{idx}", [entry.to_row()])
                return
        # RAW:純數字代號不被 Sheets 解析成數字(同 pool_repository 稽核修)。
        ws.append_row(entry.to_row(), value_input_option="RAW")

    def remove(self, code: str) -> None:
        code = str(code or "").strip().upper()
        ws = self._ws()
        rows = ws.get_all_values()
        for idx, row in enumerate(rows[1:], start=2):
            if row and str(row[0]).strip().upper() == code:
                ws.delete_rows(idx)
                return


# ───────────────────────── 後端選擇 + 便利函式 ─────────────────────────

def get_id_map_store():
    """GS 可用 → GS;否則本地 JSON(§1:主後端明確)。"""
    gs = GoogleSheetsIdMapStore()
    if gs.is_available():
        return gs
    return LocalJsonIdMapStore()


def list_id_map() -> list:
    return get_id_map_store().list_id_map()


def add_or_update(entry: IdMapEntry) -> None:
    get_id_map_store().upsert(entry)
    _clear_id_map_cache()          # 立即生效:清快取,不必等 TTL


def remove_from_id_map(code: str) -> None:
    get_id_map_store().remove(code)
    _clear_id_map_cache()


# ── 查表:供 sources.py(hot path → 快取整份 code→entry)────────────────

def _load_id_map_dict() -> dict:
    """{code → IdMapEntry}。讀不到 → {}(不阻斷抓取鏈,§1)。"""
    try:
        return {e.code: e for e in list_id_map()}
    except Exception:  # noqa: BLE001 — 對照表不可用 → 空,退硬編/搜尋
        return {}


try:  # EX-CACHE-1:App 端走 st.cache_data(跨 rerun 共享 + TTL);headless 退無快取
    import streamlit as _st_idmap

    from shared.ttls import TTL_30MIN as _TTL_IDMAP

    @_st_idmap.cache_data(ttl=_TTL_IDMAP, show_spinner=False)
    def _cached_id_map() -> dict:
        return _load_id_map_dict()
except Exception:  # noqa: BLE001 — 無 streamlit(headless/測試)
    def _cached_id_map() -> dict:
        return _load_id_map_dict()


def _clear_id_map_cache() -> None:
    """改對照後清快取 → **立即生效**(不必等 30 分 TTL;稽核 #3)。

    `_cached_id_map` 為 `@st.cache_data`(跨 rerun/session 持久,st.rerun 清不掉)。寫入後
    `.clear()`;headless plain 版無 `.clear()`(本就無快取)→ try/except 忽略。
    """
    try:
        _cached_id_map.clear()
    except Exception:  # noqa: BLE001 — plain 版無 .clear();本就無快取,無需清
        pass


def _entry_of(code) -> "IdMapEntry | None":
    _c = str(code or "").strip().upper()
    return _cached_id_map().get(_c) if _c else None


def resolve_secid(code) -> "tuple[str, str] | None":
    """對照表有該 code 的**非空 secId** → (secId, currency);否則 None(退 ISIN 搜尋/硬編)。"""
    e = _entry_of(code)
    return (e.morningstar_secid, e.currency) if (e and e.morningstar_secid) else None


def resolve_isin(code) -> "str | None":
    """對照表有該 code 的**非空 ISIN** → ISIN;否則 None。

    供 `_src_morningstar_nav`:code 有 ISIN 沒 secId 時,拿 ISIN 去晨星搜 secId(比名稱準)。
    """
    e = _entry_of(code)
    return (e.isin or None) if e else None


def resolve_currency(code) -> "str | None":
    """對照表有該 code 的計價幣別 → currency;否則 None。

    供 ISIN 路徑用**使用者填的幣別**(如 TWD)抓 NAV,而非硬給 USD(稽核 v19.470 currency 修)。
    """
    e = _entry_of(code)
    return (e.currency or None) if e else None


def set_secid(code, secid, currency: str = "") -> None:
    """回存系統以 ISIN 搜到的 secId(下次直接用、不重搜)。保留既有 ISIN/name;清快取立即生效。

    §1:code 不在表 → **不硬建列**(set_secid 只回存既有 ISIN 列的 secId);空值 → 略過。
    """
    _c = str(code or "").strip().upper()
    _sec = str(secid or "").strip()
    if not _c or not _sec:
        return
    store = get_id_map_store()
    for e in store.list_id_map():
        if e.code == _c:
            e.morningstar_secid = _sec
            if currency:
                e.currency = str(currency).strip().upper()
            store.upsert(e)
            _clear_id_map_cache()
            return


__all__ = [
    "IdMapEntry", "LocalJsonIdMapStore", "GoogleSheetsIdMapStore",
    "get_id_map_store", "list_id_map", "add_or_update", "remove_from_id_map",
    "resolve_secid", "resolve_isin", "resolve_currency", "set_secid",
]
