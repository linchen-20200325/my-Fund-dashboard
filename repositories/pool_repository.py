"""repositories/pool_repository.py — 選股池(候選基金)持久化(v19.428)。L1 CRUD。

使用者維護的「選股池」= 一組候選基金,供換股顧問配對。雙後端(仿 ~~auto_search_store~~ —— 該模組已於 2026-08-31 因 production 0 caller 整檔刪除,此處僅存設計淵源;同型現例見 `repositories/portfolio_perf_repository.py`):
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
        # ⚠️ 2026-09-06:~~`self._dir.mkdir(parents=True, exist_ok=True)`~~ 由建構子移到
        #    `_write()`(**有意識的更正,不是漏刪** · 決策者:AI 執行組,依客戶
        #    2026-09-06「查詢一律唯讀」的同一把尺)。
        #    **舊寫法的理由仍然成立**:建構子先把目錄準備好,`_write` 就永遠不必操心。
        #    **被權衡掉的是**:`get_pool_store()` 在**唯讀**路徑上也會 new 一個本地後端,
        #    於是「只是列出選股池」會在磁碟上長出一個目錄 —— 同一個形狀的病,
        #    只是落點從 Google Sheet 換成本機檔案系統。
        #    ⛔ 這**不在**客戶那句授權的字面射程內(他講的是 Google Sheet),
        #       本項為執行組主動收斂,若客戶認為多餘,單獨撤銷本項即可,不影響三處主切除。
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
        self._dir.mkdir(parents=True, exist_ok=True)   # 2026-09-06:由建構子移來(只在真寫時建目錄)
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


def _get_sheet(oauth_client=None):
    """開啟選股池目標 Sheet(v19.472:`POOL_SHEET_ID` secret → baked `_POOL_SHEET_ID_DEFAULT`,
    獨立一本、不共用持倉)。

    **憑證優先序(v19.508 手機友善)**:
      1. **Service Account**(App + headless cron 共用;SA 信箱須為該 Sheet 編輯者)。
      2. SA 缺、或 SA 開不了這本(未分享 403/404)→ **注入的使用者 OAuth client**
         (手機免設 SA:直接用登入者身分讀寫他自己有權限的那本)。
    ⚠️ 429/配額錯誤 = 暫時性 → **不降級**(降級會誤判 SA 壞掉),§1 往上拋。
    兩者皆不可用 → 明確 raise(不靜默假裝空),呼叫端 UI 顯示可行動訊息。

    mirror 自 `ui/tab3_portfolio._t3_sheet_client`(task #43 SA→OAuth 回退)的 L1 版:
    決策同「SA 優先、429 不降級、OAuth 建置失敗不崩」,但 client 由 UI 注入(L1 不碰
    session_state,守 §8.2 硬規則;pool_repository 為 EX-CRUD-1 允許 UI 直呼)。
    """
    sheet_id = _pool_sheet_id()
    if not sheet_id:   # baked 預設非空 → 正常不會到這;防禦某人把預設清空 + 沒設 secret
        raise KeyError("選股池 GS 需要 POOL_SHEET_ID secret 或 _POOL_SHEET_ID_DEFAULT(§1)")
    # ── 1) Service Account 優先(不變:App + cron 共讀同表)──
    if _sa_present():
        from infra.config import require_secret
        from repositories.policy_repository import get_gspread_client
        # v19.430:傳 raw secret(str/dict 皆可,get_gspread_client 內部正規化)。
        sa_client = get_gspread_client(require_secret("google_service_account"))
        try:
            return sa_client.open_by_key(sheet_id)
        except Exception as _e:   # noqa: BLE001 — 分流:配額暫時性 vs 真的開不了
            from infra.gspread_retry import is_quota_error
            # 429/配額 → 暫時性,不可降級(§1 往上拋,呼叫端稍後重試)。
            # 無注入 OAuth 可退 → 一樣往上拋(SA 未分享是設定問題,誠實報錯)。
            if is_quota_error(_e) or oauth_client is None:
                raise
            # SA 存在但開不了這本(未分享)→ 落到下面用注入的使用者 OAuth
    # ── 2) 使用者 OAuth(SA 缺 或 SA 開不了此本 且有注入)──
    if oauth_client is not None:
        return oauth_client.open_by_key(sheet_id)
    # ── 3) 兩者皆無 → 明確報錯(is_available() 正常會先擋下,此為防禦)──
    raise RuntimeError(
        "選股池 GS 無可用憑證:未設 Service Account,也未注入使用者 OAuth client。")


def _is_missing_worksheet(exc: BaseException) -> bool:
    """「這本試算表上**還沒有** `_fund_pool` 分頁」→ True;**其餘一律 False**。

    False 的意思是「**這次讀不到**」——403 未分享、429 配額、5xx、連線中斷、
    憑證壞掉……全部落在這一邊,呼叫端必須讓它往上拋(§1 Fail Loud:
    「空的」與「讀不到」不可以壓成同一個回傳值)。

    **判定順序刻意是「先否定、再肯定」**:
      1. **帶 HTTP 狀態碼、或是配額錯誤 → 直接 False**(委派 `infra.gspread_retry`,
         那是本 repo 這兩件事的 SSOT,不在這裡重寫一份)。
         這一道擋的是「訊息裡剛好出現 WorksheetNotFound 字樣的 APIError」。
      2. 其餘才看名字/訊息裡有沒有 `WorksheetNotFound`(duck-typed)。

    ⚠️ **為什麼要 duck-type,不 import `gspread.exceptions`**:沿用本 repo 既有做法
    (`repositories/policy/_helpers.py::_is_worksheet_not_found`,v18.253)——
    容 gspread 版本差異,且 **CI 精簡環境根本沒裝 gspread**
    (那個環境裡 `http_status_of` 恆回 None,所以第 2 道的**肯定判定**才是主力,
    第 1 道只是加強;若把主力放在第 1 道,無 gspread 環境會把 403 誤判成「沒有分頁」)。

    ⚠️ **與 `services/nav_history_gs.py::load_points` 的先例有一處刻意不同,不是漏抄**:
    那裡寫的是「**沒有 HTTP 狀態碼且非配額** → 視為分頁不存在」(純否定式)。
    純否定式會把 **`requests.ConnectionError` 這種連線中斷**也放行成「分頁不存在」
    —— 那仍然是一次「讀不到」被講成「沒有」。本函式**多要一個肯定證據**
    (名字/訊息真的說 WorksheetNotFound),因此嚴格更緊。
    **兩邊理由並陳**:先例的寫法在 gspread 有裝的環境下涵蓋了絕大多數真實案例,
    而且不必猜例外名字;**被權衡掉的是它在「沒有狀態碼的非 404 失敗」上的沉默**。
    取嚴的方向與 §1 一致 —— 誤判時寧可**多拋一次**(使用者看到紅燈),
    不要**少拋一次**(使用者看到假的空池)。

    ⚠️ `.endswith` 而非 `==`:讓測試替身(如 `FakeWorksheetNotFound`)不必 import
    gspread 就能重現「分頁不存在」這個形狀 —— 本 repo `tests/test_policy_store.py`
    早有 `Exception("WorksheetNotFound")` 的同型慣例。
    """
    try:
        from infra.gspread_retry import http_status_of, is_quota_error
        if http_status_of(exc) is not None or is_quota_error(exc):
            return False
    except Exception:  # noqa: BLE001 — 偵測工具本身壞掉 → 不敢說「只是沒有分頁」
        return False   # §1:分不清就當作讀失敗(往上拋),不當作空池
    return (type(exc).__name__.endswith("WorksheetNotFound")
            or "WorksheetNotFound" in str(exc))


def _col(n: int) -> str:
    out = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out


class GoogleSheetsPoolStore:
    backend_name = "google-sheets"

    def __init__(self, oauth_client=None) -> None:
        self._sh = None
        # v19.508:SA 缺時,UI 注入的使用者 OAuth gspread client(手機免設 SA)。
        # None → 純 SA 行為(headless/cron 不變)。
        self._oauth_client = oauth_client

    def is_available(self) -> bool:
        # v19.508:SA **或** 注入的使用者 OAuth client 任一在 → GS 可用
        # (sheet id 恆 baked 非空)。原僅 `_gs_enabled()`(SA-only)。
        return bool((_sa_present() or self._oauth_client is not None) and _pool_sheet_id())

    def _ws(self, *, for_write: bool = False):
        """取得 `_fund_pool` worksheet。

        ⚠️ **2026-09-06:本函式從「無條件確保 schema」改為「只有寫入路徑才確保 schema」**
        (**有意識的政策變更,不是漏刪** · 決策者:**客戶** · 客戶 2026-09-06 永久授權:
        「凡是『查詢/搜尋』功能,一律強制走『純讀取(唯讀)』,絕對禁止反向寫入我的
        Google Sheet。不用問我,直接切斷寫入!」)。

        **舊寫法**(原文保留於下,加刪除線):
        ~~try: ws = self._sh.worksheet(_WS_POOL)~~
        ~~except Exception:~~
        ~~    ws = self._sh.add_worksheet(...); ws.update("A1", [_HEADERS]); return ws~~
        ~~if ws.row_values(1)[: len(_HEADERS)] != _HEADERS: ws.update("A1", [_HEADERS])~~

        **舊寫法的理由仍然成立**:把「分頁存在 + 表頭正確」這個不變式收在**唯一一處**,
        讀寫兩條路徑都不必各自處理 schema —— 那是很正統的做法,一行都沒有寫錯。
        **被權衡掉的是它的副作用位置**:`list_pool()` 這個名字叫「列出」、語意是純讀的函式,
        會經由本函式**改動使用者的試算表**;而觸發條件綁在**遠端狀態**(分頁不存在、
        或表頭列與 `_HEADERS` 不符)、**不綁在使用者意圖** ——
        於是「沒用過選股池的人」與「自己在 Sheet 上改過表頭文字的人」,
        只要打開 ⑤ 設定頁就會被無聲改一次表,而且平常測不出來、log 也看不到。

        **現行**:`for_write=False`(預設,讀取路徑)—— 分頁不存在就回 `None`,
        表頭不符也**一格都不碰**。`for_write=True`(`upsert` / `remove` 等真正的寫入動作)
        —— 行為與舊寫法**逐字相同**,建表與補表頭都還在,功能沒有消失。

        ⚠️ **表頭不符時為什麼讀得下去**:`PoolEntry.from_row` 是**按位置**解析的,
        表頭列的文字對程式沒有作用。舊寫法的整排重寫也**不會**修好資料列,
        它只是把使用者自己取的欄名改掉 —— 換來的好處是零。
        (同精神已見於 `services/nav_history_gs.py::_get_worksheet` 的長註:
        「表頭文字對程式完全沒有作用,它只是給人看的,因此它屬於使用者。」)

        回傳:worksheet;或 `None`(唯讀路徑**且**分頁尚不存在)。

        ⚠️ **`None` 只有一個意思:分頁真的還沒建。**
        讀取失敗(403 未分享 / 429 配額 / 5xx / 連線中斷)**一律往上拋**,
        由 `ui/helpers/fund_grp_health/switch_advisor_section.py` 的
        `system_error("選股池讀取失敗", …)` 顯示紅燈,並由 `_load_pool_map`
        登記跨呼叫冷卻。**不得**把它們併回 `None` —— 那會讓「讀不到」
        長得跟「你的池是空的」一模一樣(§1「空有兩義」)。
        判定見 `_is_missing_worksheet`。
        """
        if self._sh is None:
            self._sh = _get_sheet(self._oauth_client)
        try:
            ws = self._sh.worksheet(_WS_POOL)
        except Exception as _e_ws:
            if not for_write:
                # ── 唯讀路徑 ────────────────────────────────────────────────
                # ⚠️ **2026-09-06 就地修正:這裡原本是裸 `except Exception: return None`**
                #    (**有意識的更正,不是漏刪** · 決策者:AI 執行組 · 依 §1 Fail Loud)。
                #    **舊寫法的用意仍然成立**:「分頁還沒建 = 這本表上沒有選股池」,
                #    誠實回空、不代替使用者建表 —— 那半句一個字都沒錯,也一個字都沒改。
                #    **被權衡掉的是它的射程**:裸 `except Exception` 把
                #    **403 未分享 / 429 配額 / 5xx / 連線中斷** 一起收進來,
                #    全部壓成同一個回傳值 → `list_pool()` 回 `[]` →
                #    使用者看到的是「**你的選股池是空的**」,而不是「**這次讀不到**」。
                #    那正是 §1 點名的「空有兩義」,也是本檔 `_load_pool_map` 的
                #    2026-09-01 長註逐字寫過的那個病。
                #
                # ⛔ **它會造成的三件事,都是實測可重現的,不是推論**:
                #    (1) `_load_pool_map` 的 `except → record_gspread_failure → raise`
                #        **永遠進不去**(因為下游根本沒拋),於是 `record_gspread_success`
                #        會對一次 403 蓋上「成功」——**跨呼叫冷卻學不到這次失敗**。
                #    (2) `_cached_pool_map` 是 `@st.cache_data`:例外不入快取、**空值會**。
                #        於是一次瞬斷把假的空池**鎖滿 TTL_30MIN**。
                #    (3) `ui/helpers/fund_grp_health/switch_advisor_section.py` 早就寫好了
                #        `except → system_error("選股池讀取失敗", hint="選股池顯示為空
                #        不代表它是空的,可能只是這次讀不到。")` 這個紅燈 ——
                #        被這一層吞掉之後,**那段程式碼再也不會被執行到**。
                #
                # **現行**:只有「分頁真的還沒建」才視為空池;其餘一律往上拋。
                if not _is_missing_worksheet(_e_ws):
                    raise
                import sys
                print(f"[pool_repository] 唯讀路徑:`{_WS_POOL}` 分頁尚不存在 → 視為空選股池"
                      f"(不建表;新增標的時才會建)", file=sys.stderr)
                return None
            # 寫入路徑:行為與 2026-09-06 之前逐字相同(分頁不在就建 + 寫表頭)。
            # ⚠️ 這裡**刻意不加**上面那道分流:真的是 403/429 時 `add_worksheet` 自己就會拋,
            #    失敗照樣浮出來;在寫入路徑上多一道判斷只會改動一段沒有壞掉的行為。
            ws = self._sh.add_worksheet(title=_WS_POOL, rows=200, cols=len(_HEADERS))
            ws.update("A1", [_HEADERS])
            return ws
        if for_write and ws.row_values(1)[: len(_HEADERS)] != _HEADERS:   # 補 header(欄位缺失時)
            ws.update("A1", [_HEADERS])
        return ws

    def list_pool(self) -> list:
        # 唯讀:`_ws()` 不帶 for_write → 不建表、不補表頭(2026-09-06 客戶授權)。
        ws = self._ws()
        # ⚠️ `None` **只**代表「分頁真的還沒建」= 空選股池(合法狀態)。
        #    讀失敗不會走到這裡 —— `_ws()` 已經把它拋出去了(§1,見該函式 docstring)。
        #    ⛔ 不得在這裡補一層 `try/except → []`:那會把上面那道分流整個作廢。
        if ws is None:
            return []
        rows = ws.get_all_values()[1:]
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
        # 真正的寫入路徑 → 照舊確保分頁與表頭存在(行為與 2026-09-06 之前逐字相同)。
        ws = self._ws(for_write=True)
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
        # 同 upsert:使用者明確按下的刪除動作屬寫入路徑,行為與 2026-09-06 之前逐字相同。
        ws = self._ws(for_write=True)
        rows = ws.get_all_values()
        for idx, row in enumerate(rows[1:], start=2):
            if row and str(row[0]).strip() == code:
                ws.delete_rows(idx)
                return


# ───────────────────────── 後端選擇 + 便利函式 ─────────────────────────

def get_pool_store(oauth_client=None):
    """GS 可用(SA 或注入的使用者 OAuth)→ GS;否則本地 JSON(§1:主後端明確,不靜默雙寫)。

    v19.508:`oauth_client` 選填 —— UI 在 SA 缺時可注入登入者的 gspread client(手機免設 SA)。
    headless/cron caller 不傳 → 純 SA 行為(與改動前完全一致)。
    """
    gs = GoogleSheetsPoolStore(oauth_client=oauth_client)
    if gs.is_available():
        return gs
    return LocalJsonPoolStore()


def pool_backend_status(oauth_client=None) -> str:
    """回報 `get_pool_store(oauth_client)` 會落到哪個後端,供 UI 誠實提示(§1 不靜默):
      - `"service_account"`:SA 在 → 永久保存(App + cron 共用)。
      - `"oauth"`:SA 缺、但有注入使用者 OAuth → 用登入者身分永久保存到雲端。
      - `"local"`:兩者皆無 → **只存本地暫存,Cloud 重開會消失**(UI 須大聲警告)。

    v19.508:防「OAuth 取不到 → 靜默落本地 → 顯示成功 → 重開消失」的 §1 破口。純函式、可單測。
    """
    if _sa_present():
        return "service_account"
    if oauth_client is not None:
        return "oauth"
    return "local"


def list_pool(oauth_client=None) -> list:
    return get_pool_store(oauth_client).list_pool()


def _after_pool_write(oauth_client=None) -> None:
    """寫入成功後的收尾:**清查表快取 ＋ 解除讀取冷卻**(2026-09-01 稽核 N1)。

    ⚠️ 只清快取是不夠的 —— 稽核實跑重現:讀取先吃過一次 403 → 登記 900 秒冷卻 →
    上游恢復 → 使用者在 UI 成功寫入 → `_clear_pool_cache()` 清得掉快取,
    **清不掉退避** → 下一次 `resolve_secid` 仍在冷卻窗內直接回 `{}`、0 趟,
    於是「改池後立即生效」這句承諾在冷卻窗內**不再為真**(最長 15 分鐘)。

    **寫入成功本身就是「這把憑證 + 這本試算表現在是健康的」的最強證據** ——
    它證明了**這本開得起來、而且可寫**。
    ⚠️ **2026-09-01 措辭收緊(稽核 NEW-7)**:~~「同時證明了配額沒滿」~~ 說得太滿 ——
    Sheets 的**讀與寫是不同的配額桶**,寫成功不證明**讀**配額可用
    (⚠️ 該關係本組與稽核都沒能一手查證,egress 擋住官方頁 → 這裡不對配額做宣稱)。
    所以這裡呼叫 `record_gspread_success`,把兩把鑰匙一起解除。
    """
    _clear_pool_cache()               # 立即生效:清補淨值查表快取,不必等 TTL
    try:
        from infra.gspread_retry import record_gspread_success
        record_gspread_success(*_pool_backoff_ident(oauth_client))
    except Exception as _e:  # noqa: BLE001 — 解除退避是收尾動作,壞掉不該讓寫入看起來失敗
        print(f"[pool_repository] 寫入成功但解除讀取冷卻時出錯(不影響寫入):"
              f"{type(_e).__name__}: {str(_e)[:120]}")


def add_or_update(entry: PoolEntry, oauth_client=None) -> None:
    get_pool_store(oauth_client).upsert(entry)
    _after_pool_write(oauth_client)


def remove_from_pool(code: str, oauth_client=None) -> None:
    get_pool_store(oauth_client).remove(code)
    _after_pool_write(oauth_client)


def set_type_override(code: str, type_override: str, oauth_client=None) -> None:
    """改某檔的手動型態(震盪/成長/空=自動)。找不到 code → 例外(§1 不靜默)。"""
    store = get_pool_store(oauth_client)
    for e in store.list_pool():
        if e.code == str(code).strip():
            e.type_override = type_override if type_override in _VALID_TYPES else ""
            store.upsert(e)
            _after_pool_write(oauth_client)
            return
    raise KeyError(f"選股池無此標的:{code}")


# ── 補淨值查表(v19.472 併入對照表:供 repositories/fund/sources.py hot path)──────────
# 選股池同時是「code → 晨星 secId / ISIN / 幣別」對照表。MoneyDJ 抓不到淨值時,sources.py
# 查本表拿 secId(或用 ISIN 去晨星串 secId)走「晨星 → Yahoo chart」補淨值。快取整份
# code→entry(大小寫不敏感鍵),~~改池後 `_clear_pool_cache()` 立即生效~~(退役 id_map_repository)。
# ⚠️ **2026-09-01 就地更正(有意識的更正,不是漏刪;決策者:客戶指派的稽核複驗)**:
# 自本檔接上跨呼叫來源冷卻起,「清快取」**不再等於**「立即生效」—— 讀取若正處於冷卻窗內,
# `_pool_map_or_empty()` 會在進場處直接回 `{}`,清快取清不到它。
# **現行寫法**:寫入成功一律走 `_after_pool_write()`,它**清快取 ＋ 解除兩把退避鑰匙**,
# 「立即生效」這句承諾因此才重新為真。舊表述的用意仍然成立(改完池不該等 30 分 TTL),
# 被權衡掉的只是它的機制描述 —— 現在光清快取已經不夠了。

def _pool_backoff_ident(oauth_client=None) -> "tuple[str, str]":
    """本次查表會用哪把憑證、打哪一本 → (actor, sheet_id)。

    走**本地 JSON** 後端時回 `("", "")` —— 那條路不上網,沒有來源可以退避
    (`infra.gspread_retry.should_skip_gspread` / `record_gspread_failure` 看到空
    actor 一律 no-op)。actor 只有 `"sa"` / `"oauth"` 兩個值,理由見
    `infra/gspread_retry.py` 檔尾「actor(憑證身分)為什麼只有兩個值」。
    """
    try:
        if _sa_present():
            return ("sa", _pool_sheet_id())
        if oauth_client is not None:
            return ("oauth", _pool_sheet_id())
    except Exception:  # noqa: BLE001 — 偵測失敗 = 當作沒有憑證(不退避,行為最保守)
        pass
    return ("", "")


def _load_pool_map() -> dict:
    """{CODE(大寫) → PoolEntry}。

    ⚠️ **2026-09-01 起:失敗一律往上拋,不再吞成 `{}`**(有意識的行為變更,不是漏刪;
    決策者:客戶 2026-09-01「批次 2(gspread 相關站點):加上跨呼叫冷卻退避」)。

    **舊寫法為什麼非改不可**:它把「讀失敗」和「選股池是空的」壓成同一個回傳值,
    而下游 `_cached_pool_map` 是 `@st.cache_data` —— streamlit **不快取例外、
    但會快取空值**,於是一次瞬斷會把那個假的空池**鎖滿 30 分鐘 TTL**,
    期間所有補淨值查表全部 miss。**空選股池是合法狀態**(使用者還沒加任何標的),
    兩者同義就是 §1 點名的「空有兩義」。
    (`app.py` 檔頭的 `@st.cache_data` 清單早已把本處列為「鎖住」的五處之一。)

    **舊寫法的用意仍然成立**:補淨值鏈**不該**因為選股池讀不到就整條炸掉。
    那個用意由 `_pool_map_or_empty()` 承接 —— **例外在快取之內拋、在快取之外譯**,
    §1 與「不阻斷抓取鏈」兩件事同時成立。
    """
    _actor, _sid = _pool_backoff_ident()
    try:
        _m = {e.code.strip().upper(): e for e in list_pool() if e.code.strip()}
    except Exception as _e:
        from infra.gspread_retry import record_gspread_failure
        _k, _cd = record_gspread_failure(_actor, _sid, _e)
        if _k:
            print(f"[pool_repository] 選股池讀取失敗 → 登記冷卻 {_cd}s(key={_k}):"
                  f"{type(_e).__name__}: {str(_e)[:120]}")
        raise
    from infra.gspread_retry import record_gspread_success
    record_gspread_success(_actor, _sid)
    return _m


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


def _pool_map_or_empty() -> dict:
    """補淨值查表的**對外入口**:冷卻期內或讀失敗 → `{}`,不阻斷抓取鏈。

    這是「內拋外譯」的**外譯**那一半 —— `_load_pool_map` 在快取**之內**照實拋
    (例外不入 `@st.cache_data`,失敗因此不會被鎖滿 TTL),本函式在快取**之外**
    把它翻成「這次查不到」,維持 `resolve_secid` / `resolve_isin` /
    `resolve_currency` 對 `repositories/fund/sources.py` 既有的「None → 退硬編表 /
    名稱搜尋」契約。

    ⚠️ 冷卻檢查放在這裡(而不是放進 `_cached_pool_map`)的理由:命中快取時那支
    函式**根本不會執行**,把 gate 放進去會變成「有快取就不查、沒快取才查」的隨機行為;
    放在入口則是每次都查一次,而且冷卻期內**連快取都不必碰**就直接回 `{}`。
    """
    from infra.gspread_retry import should_skip_gspread
    _actor, _sid = _pool_backoff_ident()
    _skip, _left, _kind = should_skip_gspread(_actor, _sid)
    if _skip:
        print(f"[pool_repository] 選股池剛失敗過(kind={_kind}),冷卻中還剩 {_left:.0f}s "
              f"→ 本次不打 Google Sheets,退硬編表/名稱搜尋")
        return {}
    try:
        return _cached_pool_map()
    except Exception as _e:  # noqa: BLE001 — 外譯:抓取鏈不因選股池讀不到而中斷
        print(f"[pool_repository] 選股池不可用,退硬編表/名稱搜尋:"
              f"{type(_e).__name__}: {str(_e)[:120]}")
        return {}


def _pool_entry_of(code) -> "PoolEntry | None":
    _c = str(code or "").strip().upper()
    return _pool_map_or_empty().get(_c) if _c else None


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


def set_secid(code, secid, currency: str = "", name: str = "", oauth_client=None) -> None:
    """回存以 ISIN 搜到的 secId(下次直接用、不重搜)。保留既有 ISIN;清快取立即生效。

    v19.473(user「只填代號+ISIN,其餘自動」):也可帶自動判到的 `currency` / `name`:
    - `currency` 非空 → 覆蓋(空 → 沿用既有,不打成 USD)。
    - `name` 非空**且既有名稱為空** → 補上(不覆蓋使用者已填的名稱)。
    §1:code 不在選股池 → **不硬建列**(只回存既有列的 secId);空 secId → 略過。

    v19.508:`oauth_client` 選填 —— headless(sources.py 補淨值)不傳走 SA;UI 可注入 OAuth。
    """
    _c = str(code or "").strip().upper()
    _sec = str(secid or "").strip()
    if not _c or not _sec:
        return
    store = get_pool_store(oauth_client)
    for e in store.list_pool():
        if e.code.strip().upper() == _c:
            e.morningstar_secid = _sec
            if currency:
                e.currency = str(currency).strip().upper()
            if name and not e.name:          # 只在空名稱時補(不蓋使用者填的)
                e.name = str(name).strip()
            store.upsert(e)
            _after_pool_write(oauth_client)
            return


__all__ = [
    "PoolEntry", "LocalJsonPoolStore", "GoogleSheetsPoolStore",
    "get_pool_store", "pool_backend_status",
    "list_pool", "add_or_update", "remove_from_pool", "set_type_override",
    "resolve_secid", "resolve_isin", "resolve_currency", "set_secid",
]
