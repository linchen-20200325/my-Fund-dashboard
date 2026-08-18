"""repositories/pool_repository.py — 選股池(候選基金)持久化(v19.428)。L1 CRUD。

使用者維護的「選股池」= 一組候選基金,供換股顧問配對。雙後端(仿 auto_search_store):
- **Google Sheets**(secrets 有設 → 主):worksheet `_fund_pool`,跨裝置同步、Cloud reboot 不掉。
  v19.472:目標 Sheet 改成**獨立一本**(`POOL_SHEET_ID` secret → baked `_POOL_SHEET_ID_DEFAULT`,
  見 `_pool_sheet_id`)—— user 2026-08-18「基金要另一本,不能共上方(持倉)的 id」。**不再共用
  `POLICY_SHEET_ID`**。仍用 Service Account(App + headless cron 共讀同表);**SA 須被加為該
  Sheet 編輯者**(同 NAV 自動累積的分享動作)。
- **本地 JSON**(無 GS → fallback):`cache/fund_pool/pool.json`(Cloud FS ephemeral,dev/離線用)。

§8.2 EX-CRUD-1:本地持久化 CRUD(讀+寫同檔、無 TTL cache、無外部 HTTP fetcher),UI 可直接 import。
§1:啟用 GS 後寫入失敗 → 例外往上拋(不靜默吞、不偷偷降級,避免資料默默遺失)。

Entry schema:code / name / category / type_override(震盪|成長|空=自動)/ note / added_at / status
  / **isin / currency / morningstar_secid**(v19.472 併入「基金代號對照表」補淨值用)。
以 **code 為唯一鍵**(upsert)。type_override 空 = 交給 `fund_type_classifier` 自動判定。
v19.472:選股池同時是 code→晨星 secId/ISIN 對照表 —— `resolve_secid/isin/currency` + `set_secid`
供 `repositories/fund/sources.py` 補淨值查表(退役獨立 `id_map_repository`)。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

_WS_POOL = "_fund_pool"
# v19.458 深度強化③:+status 欄(狀態機 WATCHING→TRIGGERED→HOLDING→CLOSED),
# additive → 舊 6 欄列經 from_row pad 後 status="" → 預設 WATCHING,向後相容。
# v19.472:併入「基金代號對照表」—— +isin/currency/morningstar_secid 三欄(仍 additive,
#   舊 7 欄列 from_row pad 後三欄="",向後相容)。選股池同時當「code→晨星 secId/ISIN」對照表,
#   sources.py 補淨值時查本表(退役獨立 id_map_repository,user 2026-08-18「兩表共用」)。
_HEADERS = ["code", "name", "category", "type_override", "note", "added_at", "status",
            "isin", "currency", "morningstar_secid"]
_CACHE_DIR = Path(__file__).resolve().parent.parent / "cache" / "fund_pool"
_LOCAL_FILE = "pool.json"
# v19.472:選股池「另一本」Sheet 的 baked 預設(user 2026-08-18 指定,與持倉 POLICY_SHEET_ID
#   **不同本**)。secret `POOL_SHEET_ID` 可覆蓋;baked 讓 Cloud 重開不掉(§1 主後端明確)。
#   ⚠️ Service Account 信箱須被加為這本 Sheet 的「編輯者」,寫入才成功。
_POOL_SHEET_ID_DEFAULT = "1bxzejYaS8-yw1fK2pKecG_jGLVJDc4uF8vuSEP-Dw9E"
_VALID_TYPES = ("震盪", "成長", "")     # 空 = 自動判定
# 狀態機合法值(本地定義,不 import L2 switch_state_machine,守 §8.2 不上行依賴)
_VALID_STATUSES = ("WATCHING", "TRIGGERED", "HOLDING", "CLOSED")


@dataclass
class PoolEntry:
    code: str
    name: str = ""
    category: str = ""
    type_override: str = ""             # 震盪 | 成長 | ""(自動)
    note: str = ""
    added_at: str = ""                  # ISO date str
    status: str = "WATCHING"            # 狀態機:WATCHING|TRIGGERED|HOLDING|CLOSED
    # v19.472 併入對照表(補淨值用):MoneyDJ 抓不到時,靠 isin/secId 走晨星補淨值路。
    isin: str = ""                      # 國際證券識別碼(如 LU0766462157);大寫
    currency: str = ""                  # 計價幣別(如 USD/TWD);空 = 未知,抓取時退 USD(§4.1 不硬給)
    morningstar_secid: str = ""         # 晨星 secId(系統用 ISIN 自動搜到後回存,免重搜)

    def __post_init__(self):
        self.code = str(self.code or "").strip()
        self.type_override = self.type_override if self.type_override in _VALID_TYPES else ""
        _st = str(self.status or "").strip().upper()
        self.status = _st if _st in _VALID_STATUSES else "WATCHING"
        self.isin = str(self.isin or "").strip().upper()
        self.currency = str(self.currency or "").strip().upper()
        self.morningstar_secid = str(self.morningstar_secid or "").strip()

    def to_row(self) -> list:
        return [self.code, self.name, self.category, self.type_override,
                self.note, self.added_at, self.status,
                self.isin, self.currency, self.morningstar_secid]

    @classmethod
    def from_row(cls, row: list) -> "PoolEntry | None":
        if not row or not str(row[0]).strip():
            return None
        row = list(row) + [""] * (len(_HEADERS) - len(row))
        return cls(code=str(row[0]), name=str(row[1] or ""), category=str(row[2] or ""),
                   type_override=str(row[3] or ""), note=str(row[4] or ""),
                   added_at=str(row[5] or ""), status=str(row[6] or ""),
                   isin=str(row[7] or ""), currency=str(row[8] or ""),
                   morningstar_secid=str(row[9] or ""))

    @classmethod
    def from_dict(cls, d: dict) -> "PoolEntry":
        return cls(**{k: d.get(k, "") for k in _HEADERS})


def _today_tw() -> str:
    """今日(台北時區)ISO 日期字串,供 added_at 預設。"""
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8))).date().isoformat()


# ───────────────────────── 本地 JSON 後端 ─────────────────────────

class LocalJsonPoolStore:
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
        except (json.JSONDecodeError, OSError) as _e:      # §1:壞檔不靜默 → log(視為空池,不覆蓋原檔)
            import sys
            print(f"[pool_repository] 本地選股池讀取失敗(視為空池,未動原檔):"
                  f"{type(_e).__name__}: {_e}", file=sys.stderr)
            return []
        if not isinstance(_data, list):                    # 合法 JSON 但非 list → 誠實視為空 + log
            import sys
            print(f"[pool_repository] 本地選股池格式非 list({type(_data).__name__})→ 視為空池",
                  file=sys.stderr)
            return []
        return _data

    def _write(self, rows: list) -> None:
        self._path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_pool(self) -> list:
        import sys
        out = []
        for d in self._read():
            if not isinstance(d, dict):                    # 非 dict 項目 → 略過 + log(§1 不硬解)
                print(f"[pool_repository] 略過非 dict 選股池項目:{type(d).__name__}", file=sys.stderr)
                continue
            try:
                e = PoolEntry.from_dict(d)
                if e.code:
                    out.append(e)
            except (TypeError, ValueError) as _e:
                print(f"[pool_repository] 略過壞損選股池項目:{type(_e).__name__}: {_e}", file=sys.stderr)
                continue
        return out

    def upsert(self, entry: PoolEntry) -> None:
        if not entry.code:
            raise ValueError("選股池 upsert 需要 code(§1 不接受空鍵)")
        if not entry.added_at:
            entry.added_at = _today_tw()
        rows = [asdict(e) for e in self.list_pool() if e.code != entry.code]
        rows.append(asdict(entry))
        self._write(rows)

    def remove(self, code: str) -> None:
        code = str(code or "").strip()
        self._write([asdict(e) for e in self.list_pool() if e.code != code])


# ───────────────────────── Google Sheets 後端 ─────────────────────────

def _pool_sheet_id() -> str:
    """選股池目標 Sheet ID:**優先 secret `POOL_SHEET_ID`**,無則回退 baked
    `_POOL_SHEET_ID_DEFAULT`(user 2026-08-18 指定的那本)。

    v19.472(user 2026-08-18「基金要另一本,不能共上方的 id」):選股池改存**獨立一本**
    Google Sheet,**不再共用持倉 `POLICY_SHEET_ID`**(避免動到持倉那本)。baked 預設讓
    Cloud 重開不掉(§1 主後端明確);要換本 → 設 `POOL_SHEET_ID` secret 覆蓋。仍走
    Service Account(App + headless cron 共讀同一張表);⚠️ SA 信箱須被加為該 Sheet 編輯者。
    """
    from infra.config import get_secret
    return (str(get_secret("POOL_SHEET_ID") or "").strip()
            or _POOL_SHEET_ID_DEFAULT)


def _sa_present() -> bool:
    """Service Account secret 是否具備 client_email(dict 直讀;JSON 字串則解析,支援 env fallback)。"""
    from infra.config import get_secret
    _sa = get_secret("google_service_account")
    if isinstance(_sa, dict):
        return bool(_sa.get("client_email"))
    if isinstance(_sa, str) and _sa.strip():
        try:
            return bool(json.loads(_sa).get("client_email"))
        except (json.JSONDecodeError, AttributeError, TypeError):
            return False
    return False


def _gs_enabled() -> bool:
    """選股池 GS 後端是否可用:SA 憑證(含 client_email)+ 目標 sheet id 都在。

    v19.472:目標 sheet 改 `POOL_SHEET_ID` → baked 預設(見 `_pool_sheet_id`),故 sheet id
    恆非空 → **SA 為唯一 gate**(有 SA 就走 GS,寫進獨立選股池那本)。偵測失敗 → False → 走本地。
    """
    try:
        return bool(_sa_present() and _pool_sheet_id())
    except Exception:  # noqa: BLE001 — 偵測失敗 = 視為未啟用 → 走本地
        return False


def _get_sheet():
    """開啟選股池目標 Sheet(v19.472:`POOL_SHEET_ID` secret → baked `_POOL_SHEET_ID_DEFAULT`,
    獨立一本、不共用持倉)。

    仍用 Service Account:App 與 headless cron 共讀同一張表。⚠️ **SA 信箱須被加為該 Sheet 的
    「編輯者」**(與 NAV 自動累積同一把 SA、同一個分享動作);未分享 → `open_by_key` 失敗往上拋
    (§1 不靜默,呼叫端 UI 顯示「讀取失敗」而非假裝空)。
    """
    from infra.config import require_secret
    from repositories.policy_repository import get_gspread_client
    # v19.430:傳 raw secret(str/dict 皆可,get_gspread_client 內部正規化)。
    creds = require_secret("google_service_account")
    sheet_id = _pool_sheet_id()
    if not sheet_id:   # baked 預設非空 → 正常不會到這;防禦某人把預設清空 + 沒設 secret
        raise KeyError("選股池 GS 需要 POOL_SHEET_ID secret 或 _POOL_SHEET_ID_DEFAULT(§1)")
    return get_gspread_client(creds).open_by_key(sheet_id)


def _col(n: int) -> str:
    out = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out


class GoogleSheetsPoolStore:
    backend_name = "google-sheets"

    def __init__(self) -> None:
        self._sh = None

    def is_available(self) -> bool:
        return _gs_enabled()

    def _ws(self):
        if self._sh is None:
            self._sh = _get_sheet()
        try:
            ws = self._sh.worksheet(_WS_POOL)
        except Exception:
            ws = self._sh.add_worksheet(title=_WS_POOL, rows=200, cols=len(_HEADERS))
            ws.update("A1", [_HEADERS])
            return ws
        if ws.row_values(1)[: len(_HEADERS)] != _HEADERS:     # 補 header(欄位缺失時)
            ws.update("A1", [_HEADERS])
        return ws

    def list_pool(self) -> list:
        rows = self._ws().get_all_values()[1:]
        out = []
        for row in rows:
            e = PoolEntry.from_row(row)
            if e is not None:
                out.append(e)
        return out

    def upsert(self, entry: PoolEntry) -> None:
        if not entry.code:
            raise ValueError("選股池 upsert 需要 code(§1 不接受空鍵)")
        if not entry.added_at:
            entry.added_at = _today_tw()
        ws = self._ws()
        rows = ws.get_all_values()
        for idx, row in enumerate(rows[1:], start=2):
            if row and str(row[0]).strip() == entry.code:
                ws.update(f"A{idx}:{_col(len(_HEADERS))}{idx}", [entry.to_row()])
                return
        # RAW(非 USER_ENTERED):純數字基金代號如 "0050" 若被 Sheets 解析成數字 50,
        # get_all_values 會回 "50" → 破壞 code 主鍵字串比對去重 → 同檔重複列(v19.430 稽核修)。
        ws.append_row(entry.to_row(), value_input_option="RAW")

    def remove(self, code: str) -> None:
        code = str(code or "").strip()
        ws = self._ws()
        rows = ws.get_all_values()
        for idx, row in enumerate(rows[1:], start=2):
            if row and str(row[0]).strip() == code:
                ws.delete_rows(idx)
                return


# ───────────────────────── 後端選擇 + 便利函式 ─────────────────────────

def get_pool_store():
    """GS 可用 → GS;否則本地 JSON(§1:主後端明確,不靜默雙寫)。"""
    gs = GoogleSheetsPoolStore()
    if gs.is_available():
        return gs
    return LocalJsonPoolStore()


def list_pool() -> list:
    return get_pool_store().list_pool()


def add_or_update(entry: PoolEntry) -> None:
    get_pool_store().upsert(entry)
    _clear_pool_cache()               # 立即生效:清補淨值查表快取,不必等 TTL


def remove_from_pool(code: str) -> None:
    get_pool_store().remove(code)
    _clear_pool_cache()


def set_type_override(code: str, type_override: str) -> None:
    """改某檔的手動型態(震盪/成長/空=自動)。找不到 code → 例外(§1 不靜默)。"""
    store = get_pool_store()
    for e in store.list_pool():
        if e.code == str(code).strip():
            e.type_override = type_override if type_override in _VALID_TYPES else ""
            store.upsert(e)
            _clear_pool_cache()
            return
    raise KeyError(f"選股池無此標的:{code}")


# ── 補淨值查表(v19.472 併入對照表:供 repositories/fund/sources.py hot path)──────────
# 選股池同時是「code → 晨星 secId / ISIN / 幣別」對照表。MoneyDJ 抓不到淨值時,sources.py
# 查本表拿 secId(或用 ISIN 去晨星串 secId)走「晨星 → Yahoo chart」補淨值。快取整份
# code→entry(大小寫不敏感鍵),改池後 `_clear_pool_cache()` 立即生效(退役 id_map_repository)。

def _load_pool_map() -> dict:
    """{CODE(大寫) → PoolEntry}。讀不到 → {}(不阻斷抓取鏈,§1 退硬編/搜尋)。"""
    try:
        return {e.code.strip().upper(): e for e in list_pool() if e.code.strip()}
    except Exception:  # noqa: BLE001 — 選股池不可用 → 空,退硬編表/名稱搜尋
        return {}


try:  # EX-CACHE-1:App 端走 st.cache_data(跨 rerun 共享 + TTL);headless 退無快取
    import streamlit as _st_pool

    from shared.ttls import TTL_30MIN as _TTL_POOL

    @_st_pool.cache_data(ttl=_TTL_POOL, show_spinner=False)
    def _cached_pool_map() -> dict:
        return _load_pool_map()
except Exception:  # noqa: BLE001 — 無 streamlit(headless/測試)
    def _cached_pool_map() -> dict:
        return _load_pool_map()


def _clear_pool_cache() -> None:
    """改選股池後清補淨值查表快取 → **立即生效**(不必等 30 分 TTL)。

    `_cached_pool_map` 為 `@st.cache_data`(跨 rerun/session 持久);headless plain 版
    無 `.clear()`(本就無快取)→ try/except 忽略。
    """
    try:
        _cached_pool_map.clear()
    except Exception:  # noqa: BLE001 — plain 版無 .clear();本就無快取,無需清
        pass


def _pool_entry_of(code) -> "PoolEntry | None":
    _c = str(code or "").strip().upper()
    return _cached_pool_map().get(_c) if _c else None


def resolve_secid(code) -> "tuple[str, str] | None":
    """選股池有該 code 的**非空 secId** → (secId, currency);否則 None(退 ISIN 搜尋/硬編)。

    currency 空(未知)→ 回 USD 當抓取預設(§4.1:只在真的不知道時才退 USD,不寫回)。
    """
    e = _pool_entry_of(code)
    return (e.morningstar_secid, e.currency or "USD") if (e and e.morningstar_secid) else None


def resolve_isin(code) -> "str | None":
    """選股池有該 code 的**非空 ISIN** → ISIN;否則 None(拿去晨星搜 secId,比名稱準)。"""
    e = _pool_entry_of(code)
    return (e.isin or None) if e else None


def resolve_currency(code) -> "str | None":
    """選股池有該 code 的計價幣別 → currency;否則 None(讓 sources.py 用使用者填的幣別抓)。"""
    e = _pool_entry_of(code)
    return (e.currency or None) if e else None


def set_secid(code, secid, currency: str = "", name: str = "") -> None:
    """回存以 ISIN 搜到的 secId(下次直接用、不重搜)。保留既有 ISIN;清快取立即生效。

    v19.473(user「只填代號+ISIN,其餘自動」):也可帶自動判到的 `currency` / `name`:
    - `currency` 非空 → 覆蓋(空 → 沿用既有,不打成 USD)。
    - `name` 非空**且既有名稱為空** → 補上(不覆蓋使用者已填的名稱)。
    §1:code 不在選股池 → **不硬建列**(只回存既有列的 secId);空 secId → 略過。
    """
    _c = str(code or "").strip().upper()
    _sec = str(secid or "").strip()
    if not _c or not _sec:
        return
    store = get_pool_store()
    for e in store.list_pool():
        if e.code.strip().upper() == _c:
            e.morningstar_secid = _sec
            if currency:
                e.currency = str(currency).strip().upper()
            if name and not e.name:          # 只在空名稱時補(不蓋使用者填的)
                e.name = str(name).strip()
            store.upsert(e)
            _clear_pool_cache()
            return


__all__ = [
    "PoolEntry", "LocalJsonPoolStore", "GoogleSheetsPoolStore",
    "get_pool_store", "list_pool", "add_or_update", "remove_from_pool", "set_type_override",
    "resolve_secid", "resolve_isin", "resolve_currency", "set_secid",
]
