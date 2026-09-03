"""services/nav_history_gs.py — v19.359 Track 2:每日 NAV 快照累積到 Google Sheets

背景(Track 1 驗證後的轉向):境外/保單基金的**歷史** NAV 從 GitHub Actions 美國 IP
幾乎全抓不到(TDCC 3-4 回空、AllianzGI/CnYES/MoneyDJ 改版或被擋 —— run #557 log 實證)。
但 **App 端**(repositories/fund/sources.py 完整 fallback chain + NAS 代理)在使用者實際查詢時
**抓得到「當日最新淨值」**(user 2026-07-22 於 App 確認淨值日期是最近的)。

本模組把 App 顯示成功的那一筆 `(code, date, nav)` append 進 Google Sheet `nav_history` 分頁
—— 靠日常使用「**從現在累積**」歷史序列,時間久了解鎖 Sortino/Calmar/3Y/5Y/3-3-3
(每天 1 筆:~60 交易日解鎖 Sortino/Sharpe、~756 日解鎖 3Y、~1260 日解鎖 5Y)。

§1 Fail Loud:資料不足(nav<=0 / date 壞 / code 空)→ **不寫**(不偽造);
             真 GS I/O 失敗 → **raise NavHistoryError**(呼叫端須看見,不靜默吞)。
§5 冪等:`(code, date)` 去重 —— 同日重複查同檔只留 1 筆,不灌水。
§8.2:L2 service(~~比照 services/auto_search_store_gs.py~~),存進 `_nav_sheet_id()` 那本
     workbook(v19.472 改獨立 `NAV_SHEET_ID`)加 `nav_history` 分頁;UI(L3)呼叫本層,**不自己開 gspread**。
     GS secrets 未設(local / CI)→ 安靜 no-op,不干擾。gspread I/O 為持久化職責,
     ~~不在 §8.2「L2 禁 requests/httpx/bs4/feedparser」清單,且有 auto_search_store_gs 先例。~~

     ⚠️ **2026-08-31 更正(有意識的變更,不是漏刪;決策者:客戶 2026-08-31 授權死碼清理)** ——
     上面那兩句劃掉的**不是因為檔案被刪才失效,是它們本來就不是有效的豁免理由**:
     (a) `services/auto_search_store_gs.py` 已整檔刪除(production 0 caller),
         **那個「先例」不存在了**;而且它當年**自己也沒有登錄在 §8.2.A 例外表**
         —— 兩檔曾互為背書,兩檔都是 §8.2 末句禁止的「未經登錄的軟例外」。
     (b) 「不在字表清單裡」證明的是**清單不全**,不是這樣寫是對的
         (本 repo 憲法 §-1.5.1c 判定 2 已記載該字表漏抓兩次)。
     **現況據實說明**:本檔的 gspread 往返**仍未登錄於 §8.2.A 例外表**,
     已登記在 `tests/test_services_purity_contract.py::GSPREAD_DEBT`(登記 ≠ 核准)。
     **本輪未修它** —— 把 gspread 持久化搬出 L2 會動到 NAV 歷史鏈,
     屬 §8.4 步驟 4 的範圍決定,不在本輪(死碼清理)授權內。

Worksheet schema `nav_history`(A1 = headers):
    code | date | nav | fund_name | source | recorded_at | currency
主鍵 (code, date)。

⚠️ **`currency` 為 2026-09-01 新增的第 7 欄,存的是「寫入當下量到的觀測值」**
(來源序列自己宣告的 `Series.attrs["currency"]`),**不是猜出來的**。
這張表 `(code, date)` 去重且**永不刪除** —— 一個欄位不存在,它記不下來的事實就是
**永久失去**(既有的 `source` 欄存的是 `"app"`/`"backfill"`/`"nas_cron"`,反推不出 fetcher,
更反推不出幣別)。故先把欄位開出來、確保寫入端帶上,封堵後續污染。
⚠️ **空字串 = 誠實的未知,不是失敗**:多數 producer 手上沒有觀測值(全 repo 只有晨星 /
Yahoo / FundClear 會宣告),**既有列一律留空,不回填任何猜測值**(§1:不知道 ≠ TWD)。
⛔ 本輪**刻意沒有任何下游消費者讀這一欄** —— 採用點守門依客戶 2026-09-01 指示另批補齊。
"""
from __future__ import annotations

import contextlib as _contextlib
import datetime as _dt
import threading as _threading
from typing import Any

# v19.509 稽核 mitigation:健診 tab 於主執行緒捕獲**單一** OAuth gspread client 後,傳進
# 最多 4 個 worker 執行緒併發讀 nav_history。gspread client 底層 requests.Session **非**
# thread-safe(SA 路徑每次 _get_sheet 建新 client 故無此問題;OAuth 路徑共用注入的同一個)。
# 用本 lock 序列化「注入 OAuth client」的 GS I/O(唯讀為主,序列化成本遠小於 MoneyDJ 抓取,
# 且順帶避免 4-way 併發打爆 OAuth 60 reads/min quota)。SA 路徑不鎖(本就各自新 client)。
_OAUTH_GS_LOCK = _threading.Lock()


def _gs_guard(oauth_client: Any, _sheet: Any):
    """注入 OAuth client 且非測試注入 _sheet → 上鎖序列化;否則 no-op(SA / 測試路徑不序列化)。"""
    return _OAUTH_GS_LOCK if (oauth_client is not None and _sheet is None) else _contextlib.nullcontext()


_WS_NAV = "nav_history"
_NAV_HEADERS = ["code", "date", "nav", "fund_name", "source", "recorded_at",
                "currency"]
# v19.472:NAV 淨值存進**獨立一本** Google Sheet(user 2026-08-18 指定「基金淨值存取」那本)。
#   目標本 = `NAV_SHEET_ID` secret → baked 預設(**僅此兩層,無自動回退**;v19.506 更正:
#   原註寫「回退舊 macro_weights_sheet_id」是**誤導**,`_nav_sheet_id()` 從未做此回退。
#   若既有累積在別本,須自行把 `NAV_SHEET_ID` secret 指過去)。
#   baked 讓 Cloud 重開不掉;⚠️ Service Account 信箱須被加為**該本**的「編輯者」讀寫才成功。
_NAV_SHEET_ID_DEFAULT = "1b92nXxjGLJOOLP_Srvz2Cf69Y443Sdldp1_dWQzZncQ"


def _nav_sheet_id() -> str:
    """nav_history 目標 Sheet ID:`NAV_SHEET_ID` secret → baked `_NAV_SHEET_ID_DEFAULT`。

    v19.472(user 2026-08-18「基金淨值存另一本」):NAV 改存**獨立一本**(見 `_NAV_SHEET_ID_DEFAULT`),
    不再與總經權重(`macro_weights_sheet_id`)那本混。baked 讓 Cloud 重開不掉 + SA 齊備即啟用
    (§1 主後端明確);要換本(或指回舊 macro_weights 那本以續讀既有累積)→ 設 `NAV_SHEET_ID` secret。
    """
    from infra.config import get_secret
    return (str(get_secret("NAV_SHEET_ID") or "").strip()
            or _NAV_SHEET_ID_DEFAULT)


class NavHistoryError(Exception):
    """nav_history 寫入/讀取失敗(§1 Fail Loud:呼叫端須看見,不靜默 no-op)。"""


def _sa_to_dict(v: Any) -> dict:
    """Service Account secret 正規化:dict 原樣;**JSON 字串 → dict**(NAS/cron 的
    env fallback 只能給字串,v19.363 ③);解析失敗 / 其他型別 → {}(視同缺)。"""
    if isinstance(v, dict):
        return v
    if isinstance(v, str) and v.strip():
        import json
        try:
            parsed = json.loads(v)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, TypeError):
            return {}
    return {}


def is_enabled() -> bool:
    """GS secrets 是否齊備。v19.363 起 `status()` 為 SSOT(含 env JSON 字串 SA 支援,
    NAS cron 環境不再被誤判未啟用);Streamlit 端行為不變(同兩把 secrets)。"""
    return status()["enabled"]


def status() -> dict:
    """v19.362 ①:累積狀態診斷 — 回 {"enabled": bool, "missing": [缺的 secret 名]}。

    體檢瑕疵 #6「secrets 沒設 = 安靜略過 → 你以為在累積其實沒有」的解方:
    UI(Tab5 狀態燈 / hook 一次性提示)用本 fn 把靜默失敗變可見(§5 可觀測)。
    v19.363 ③:SA 支援 env JSON 字串(_sa_to_dict),NAS cron 可用。
    v19.379:回傳增設 `diag` 細分失敗模式 —— absent(App 完全沒讀到)/ unparseable
    (有值但非合法 JSON)/ no_client_email(JSON 缺欄),並旁證 `st_secrets_alive`
    (讀不讀得到既有 FRED_API_KEY),讓 UI 直接講出「放錯地方」還是「引號貼壞」(§5 可觀測)。
    """
    missing: list[str] = []
    diag: dict = {}
    try:
        from infra.config import get_secret
        _raw_sa = get_secret("google_service_account")
        if _raw_sa is None or (isinstance(_raw_sa, str) and not _raw_sa.strip()):
            missing.append("google_service_account")
            diag["google_service_account"] = "absent"          # App 完全沒讀到這把 key
        else:
            sa = _sa_to_dict(_raw_sa)
            if not sa:
                missing.append("google_service_account")
                diag["google_service_account"] = "unparseable"  # 有值但不是合法 JSON dict
            elif not sa.get("client_email"):
                missing.append("google_service_account")
                diag["google_service_account"] = "no_client_email"
            else:
                diag["google_service_account"] = "ok"
        if not _nav_sheet_id():                       # v19.472:baked 預設非空 → 恆 ok(SA 為唯一 gate)
            missing.append("NAV_SHEET_ID")
            diag["nav_sheet_id"] = "absent"
        else:
            diag["nav_sheet_id"] = "ok"
        # 旁證:讀得到既有 FRED_API_KEY = st.secrets 本身有效(問題只在這兩把);
        # 讀不到 = 整份 secrets 沒生效(TOML 壞 / 放錯 App / 沒 reboot)。
        diag["st_secrets_alive"] = bool(get_secret("FRED_API_KEY"))
    except Exception as e:
        missing = ["google_service_account", "NAV_SHEET_ID"]   # v19.472:改用 NAV 專屬 sheet id
        diag = {"error": f"{type(e).__name__}: {str(e)[:80]}"}
    return {"enabled": not missing, "missing": missing, "diag": diag}


def _norm_date(v: Any) -> str:
    """轉 'YYYY-MM-DD'。接受 date/datetime/'YYYY/MM/DD'/'YYYY-MM-DD...'。壞值回 ''(§1 不猜)。

    v19.461 資料把關(user 2026-08-17 回報 ALZF9 未來日期 2026-10-12):除 4 位數年 + 全數字,
    另擋 **月/日範圍** 與 **未來日期**(NAV 不可能是未來;根治 TDCC/opendata `pd.to_datetime`
    把民國年或日月顛倒誤 parse 成未來日 → 靜默存進 nav_history 的 bug)。
    """
    if v is None or v == "":
        return ""
    if isinstance(v, (_dt.date, _dt.datetime)):
        s = v.strftime("%Y-%m-%d")
    else:
        s = str(v).strip().replace("/", "-")[:10]
    parts = s.split("-")
    if not (len(parts) == 3 and len(parts[0]) == 4 and all(p.isdigit() for p in parts)):
        return ""
    _y, _m, _dd = int(parts[0]), int(parts[1]), int(parts[2])
    if not (1 <= _m <= 12 and 1 <= _dd <= 31):     # 月/日範圍(擋日月顛倒等亂 parse)
        return ""
    try:
        _today = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8))).date()
        if _dt.date(_y, _m, _dd) > _today:         # 未來日期 → 丟(§1 不存不可能的資料)
            return ""
    except ValueError:                              # 非法日期(如 2-30)→ 丟
        return ""
    return f"{_y:04d}-{_m:02d}-{_dd:02d}"


def norm_date_key(v: Any) -> str:
    """`(code, date)` 主鍵用的日期字串 —— **寫入去重、讀取、Gate 0 對帳共用這一把尺**。

    `_norm_date` 回 `''` 的怪日期(未來日 / 月日超範圍 / 非法)**退回原字串前 10 碼**,
    不弱化既有去重、也不靜默丟資料(§1:不猜)。

    2026-08-28 稽核修正 —— 為什麼要把它抽成一個公用函式
    ---------------------------------------------------
    在此之前這條規則只寫在 `append_points` 的迴圈裡(**寫入端有正規化**),
    而 `load_points`(**讀取端**)回的是未正規化的原始字串。兩邊不同尺的後果:
    `fundclear_backfill.analyze_backfill_conflict` 拿讀取端的字串當 dict key、
    拿 incoming 的 ISO 去查 —— 既有列若是 user 手填的 `'2020/1/2'`,
    **永遠查不中 → 零重疊 → verdict 恆為 `clean` → 整道閘門靜默失效**
    (實測:既有 `'2024/01/02'` 10.00 vs 這次 33.10 → 放行)。
    而 `append_points` 的 v19.489 註解自己就寫著這種手填斜線列**確實存在**。

    **一把尺、三個消費端** —— `append_points`(去重鍵)/ `load_points`(讀取)/
    `analyze_backfill_conflict`(對帳兩側),避免再度出現「寫入端有、讀取端沒有」。
    """
    return _norm_date(v) or str(v if v is not None else "").strip()[:10]


def _clean_points(points: list[dict]) -> list[dict]:
    """normalize + §1 過濾:code 空 / date 壞 / nav<=0 全丟(不偽造)。

    §5 可觀測性(v19.461):日期被 `_norm_date` 剔除(未來日 / 月日超範圍 / 非法日)且
    **原始 nav_date 非空**時 → 這是「有值但壞掉」的髒資料(多半上游 misparse,如 user
    2026-08-17 ALZF9 被 parse 成 2026-10-12 未來日)。單獨計數 + log 一行,避免和去重
    `skipped` 混算被淹沒(稽核 §5 建議)。此處只 log,過濾行為不變(仍不寫入 §1)。
    """
    from shared.data_quality import normalize_iso_ccy

    out: list[dict] = []
    _bad_dates: list[str] = []
    for p in points:
        code = str(p.get("code") or "").strip().upper()
        _raw_date = p.get("nav_date")
        d = _norm_date(_raw_date)
        if not d and _raw_date not in (None, ""):
            _bad_dates.append(f"{code or '?'}={_raw_date!r}")
        try:
            nav_f = float(p.get("nav"))
        except (TypeError, ValueError):
            nav_f = None
        if code and d and nav_f is not None and nav_f > 0:
            out.append({
                "code": code, "date": d, "nav": nav_f,
                "fund_name": str(p.get("fund_name") or ""),
                "source": str(p.get("source") or "app"),
                # 2026-09-01 第 7 欄。⚠️ 本函式是**白名單輸出** —— 沒列在這裡的 key
                # 會被整個丟掉,呼叫端加了 `currency` 也是安靜的 no-op(實測)。
                # 非 ISO 三碼(中文別名 / `None` / 垃圾字串)一律收成 `""`(§1 不猜);
                # 這張表永不刪除,寧可留空也不要寫一個猜的幣別進去。
                "currency": normalize_iso_ccy(p.get("currency")),
            })
    if _bad_dates:
        import sys as _sys
        print(f"[nav_history_gs] 剔除 {len(_bad_dates)} 筆壞/未來日期(不寫入 nav_history):"
              f"{', '.join(_bad_dates[:10])}{' …' if len(_bad_dates) > 10 else ''}",
              file=_sys.stderr)
    return out


def backend_status(oauth_client: Any = None) -> str:
    """nav_history 寫入會落到哪個後端:'service_account' / 'oauth' / 'local'。

    v19.509(user 2026-08-22「都用手機 沒有電腦」):UI 用此**誠實提示**落點 —— SA 齊備 →
    雲端永久;SA 缺但有登入 OAuth → 雲端永久(使用者身分,mirror 選股池);兩者皆無 →
    只存本機(容器重啟清空,UI 須警告,§1 不讓 user 誤以為在累積)。
    """
    if is_enabled():
        return "service_account"
    if oauth_client is not None:
        return "oauth"
    return "local"


def _get_sheet(oauth_client: Any = None):
    """開啟 NAV 專屬 workbook(`_nav_sheet_id()`)。

    **憑證優先序(v19.509 手機友善,mirror 選股池 `pool_repository._get_sheet`)**:
      1. **Service Account**(App + cron 共用;SA 走 `_sa_to_dict`,env JSON 字串與 st.secrets
         dict 都吃;SA 信箱須為該 Sheet 編輯者)。
      2. SA 缺、或 SA 開不了此本(未分享 403/404)→ **注入的使用者 OAuth client**
         (手機免設 SA:用登入者身分讀寫他自己有權限的那本)。
    ⚠️ 429/配額 = 暫時性 → **不降級**(§1 往上拋,不誤判 SA 壞)。兩者皆無 → raise。
    v19.472:目標 Sheet = `_nav_sheet_id()`(NAV_SHEET_ID secret → baked `_NAV_SHEET_ID_DEFAULT`)。
    """
    from infra.config import get_secret
    sheet_id = _nav_sheet_id()
    # ── 1) Service Account 優先(不變:env JSON 字串 / st.secrets dict 皆吃)──
    #    用 get_secret(非 require_secret):SA 缺時不預先 raise,好落到 OAuth 分支。
    creds = _sa_to_dict(get_secret("google_service_account"))
    if creds.get("client_email"):
        from repositories.policy_repository import get_gspread_client
        client = get_gspread_client(creds)
        try:
            return client.open_by_key(sheet_id)
        except Exception as e:
            from infra.gspread_retry import is_quota_error
            # 429/配額 → 暫時性,不可降級;無 OAuth 可退 → 一樣拋(SA 未分享是設定問題,誠實報錯)。
            # v19.380:gspread 對「SA 無權限」回 SpreadsheetNotFound(str 常空)→ 印可行動訊息。
            if is_quota_error(e) or oauth_client is None:
                raise NavHistoryError(
                    f"開表失敗（{type(e).__name__}）:服務帳戶 {creds.get('client_email', '?')} "
                    f"找不到或無權限存取 sheet_id={sheet_id!r}。請確認:"
                    f"(1) 已把該服務帳戶信箱加進這張 Sheet 的「共用 → 編輯者」;"
                    f"(2) sheet_id 是那張 Sheet 的 ID;(3) 該 GCP project 已啟用 Google Drive API。"
                ) from e
            # SA 存在但開不了這本 → 落到下面用注入的使用者 OAuth
    # ── 2) 使用者 OAuth(SA 缺 或 SA 開不了此本 且有注入)──
    if oauth_client is not None:
        try:
            return oauth_client.open_by_key(sheet_id)
        except Exception as e:
            raise NavHistoryError(
                f"OAuth 開表失敗（{type(e).__name__}）:你登入的 Google 帳號找不到或無權限存取 "
                f"nav_history sheet_id={sheet_id!r}。請確認這張 Sheet 是你的 Google 帳號可編輯的。"
            ) from e
    # ── 3) 兩者皆無 → 明確報錯(呼叫端 gate 正常會先擋,此為防禦)──
    raise NavHistoryError(
        "nav_history 無可用憑證:未設 Service Account,也未注入使用者 OAuth client。")


def _a1_col(idx0: int) -> str:
    """0-based 欄索引 → A1 欄名(0→`"A"`、6→`"G"`、26→`"AA"`)。純函式,無 I/O。"""
    _s, _n = "", idx0 + 1
    while _n:
        _n, _r = divmod(_n - 1, 26)
        _s = chr(65 + _r) + _s
    return _s


def _get_worksheet(sh):
    """取得 nav_history worksheet,不存在則建立 + 寫 header;**既有分頁只補「缺的那幾格」**。

    2026-09-01(第 7 欄 `currency`):~~既有分頁是 6 欄建的,不補的話新欄會是無標題的 G 欄。~~
    → **2026-09-01 就地更正(有意識的更正,不是漏刪)**:舊句把既有分頁一律當成 **6 欄**,
    與本 docstring 下方那段「缺幾格取決於既有表頭有多長」**同段自相矛盾**。
    **現行**:既有分頁**有幾欄不一定**(6 欄舊 schema / 3 欄最小 schema 都真實存在),
    不補的話新欄會是**無標題的欄**。

    **為什麼是「只補缺格」而不是「整排重寫」——這是本函式唯一該記住的事**
    ------------------------------------------------------------------
    本模組**沒有任何一處讀表頭列的文字**:`load_points` 與 `append_points` 都是
    `ws.get_all_values()[1:]` **跳過**第 1 列,再以 `r[0]`..`r[6]` **逐位置**取值;
    `load_series` / `coverage_status` 都走 `load_points`。
    (⚠️ 別跟 `_pick_col` / `import_csv_text` 的 `rows[0]` 混淆 —— 那是**使用者上傳的
    CSV** 的第一列,不是這張 worksheet 的表頭。)

    → **表頭文字對程式完全沒有作用,它只是給人看的,因此它屬於使用者。**
    這張表使用者**會手動維護**,他大可把表頭寫成 `代碼 | 日期 | 淨值 | …`;
    整排重寫會把他自己取的名字改掉,而**換來的好處是零**(程式根本不看)。
    所以:**長度夠了就什麼都不做;不夠就只把尾巴缺的那幾格補上,永遠不碰 A1。**

    ⚠️ **「缺幾格」取決於既有表頭有多長,不是固定一格**(2026-09-01 稽核指出,就地更正):
    6 欄舊分頁 → 補 `G1` **一格**;而 **user 2026-08-19 明文要求支援的 3 欄最小 schema**
    (`code | date | nav`,見 `tests/test_nav_history_gs_min_schema_v19489.py` 檔頭)
    → 補 **`D1:G1` 四格**。`_NAV_HEADERS[len(_hdr):]` 本來就一般化了,
    **舊註解寫「本批就是 G1」是敘述錯誤,不是程式錯誤。**

    ⚠️ **本處刻意偏離 `repositories/pool_repository.py::PoolRepo._ws` 與
    `repositories/portfolio_perf_repository.py::PerfRepo._ws` 的整排比對慣例**
    (`if ws.row_values(1)[: len(_HEADERS)] != _HEADERS: ws.update("A1", [_HEADERS])`)。
    那兩處的取捨與這裡不同,不能照抄;差別見本 PR 描述的登記。

    ⛔ **絕對不要改用 `ws.resize(cols=...)`**:gspread 送出的是**絕對值**
    (`{"gridProperties": {"columnCount": 7}}`),在使用者自己維護到 26 欄的表上等於
    **刪掉 H..Z 欄連同內容**。`values.append` 本來就會視需要擴欄,不需要也不該先 resize。
    """
    try:
        ws = sh.worksheet(_WS_NAV)
    except Exception:
        # 分頁本來不存在 → 整排寫沒有覆寫任何東西。
        ws = sh.add_worksheet(title=_WS_NAV, rows=1000, cols=len(_NAV_HEADERS))
        ws.update("A1", [_NAV_HEADERS])
        return ws
    _hdr = ws.row_values(1)
    if not any(str(_c).strip() for _c in _hdr):
        # 第 1 列整列空白(全新 / 空白工作表)→ 同樣沒有東西會被覆寫,照寫整排。
        ws.update("A1", [_NAV_HEADERS])
    elif len(_hdr) < len(_NAV_HEADERS):
        # **只補尾巴缺的那幾格**(6 欄表 → `G1`;3 欄最小 schema → `D1:G1`);
        # 既有的那幾格**一格都不碰**,不論它們寫的是什麼。
        ws.update(f"{_a1_col(len(_hdr))}1", [_NAV_HEADERS[len(_hdr):]])
    return ws


def append_points(points: list[dict], *, _sheet: Any = None, oauth_client: Any = None) -> dict:
    """批次 append 多筆 nav 點:**讀一次去重 + 一次 append_rows**(省 Sheets quota;60 reads/min)。

    ⚠️ **2026-09-01 誠實更正:本路徑現在是 2 次 read,不是 1 次。**
    `_get_worksheet` 為了判斷表頭要不要補欄,多發了一次 `ws.row_values(1)`
    (在既有分頁上;分頁不存在的新建路徑不受影響)。上面那句「讀一次」描述的是
    **去重讀**(`get_all_values`)那一次,仍然只有一次;但**整條寫入路徑的 read 次數
    由 1 變 2**,這是本次加第 7 欄付出的代價,登記在此。
    ⚠️ **刻意不為了省這次 read 改用 `existing[0]`**(總管 2026-09-01 裁決):那會讓
    同一個不變式長出**兩條實作路徑**(一條在 `_get_worksheet` 內、一條在外),
    而 `_get_worksheet` 是讀寫兩條路徑**共用**的。「最小改動」與「單一真相源」
    兩條都指向**改敘述、不改程式**。

    points: [{"code", "nav", "nav_date", "fund_name"(opt), "source"(opt)}]
    回傳 {"written": int, "skipped": int}。
    §1:資料不足的點被丟;GS 未啟用(SA 缺且未注入 OAuth、且未注入 _sheet)→ 安靜 no-op 回 written=0。
        真 GS I/O 失敗 → raise NavHistoryError。
    _sheet:測試注入用(繞過真 gspread)。
    oauth_client:v19.509 —— SA 缺時 UI 注入登入者 gspread client,改用使用者身分寫雲端。
    """
    clean = _clean_points(points)
    if not clean:
        return {"written": 0, "skipped": len(points)}
    if _sheet is None and not is_enabled() and oauth_client is None:
        return {"written": 0, "skipped": len(points)}  # local/CI 無 SA 無 OAuth:安靜略過

    try:
        with _gs_guard(oauth_client, _sheet):     # v19.509:序列化共用 OAuth client 併發讀寫
            sh = _sheet if _sheet is not None else _get_sheet(oauth_client)
            ws = _get_worksheet(sh)
            existing = ws.get_all_values()  # 含 header
            seen: set = set()
            for r in existing[1:]:
                if len(r) >= 2:
                    # v19.489:去重鍵的日期先正規化,讓 user 手填的 '2020/1/2' 與系統寫的
                    # ISO '2020-01-02' 視為同一天(否則同日兩格式 → 重複列 + load 時系統值
                    # 覆蓋 user 值)。2026-08-28:同一條規則抽成 `norm_date_key`,讀取端
                    # (`load_points`)與 Gate 0 對帳共用同一把尺 —— 表達式等價,行為不變。
                    seen.add((str(r[0]).strip().upper(), norm_date_key(r[1])))
            recorded_at = _dt.datetime.now(_dt.timezone.utc).isoformat()
            new_rows: list = []
            for c in clean:  # 同批內也去重(同 code+date 只留第一筆)
                key = (c["code"], c["date"])
                if key in seen:
                    continue
                seen.add(key)
                new_rows.append([c["code"], c["date"], c["nav"],
                                 c["fund_name"], c["source"], recorded_at,
                                 c["currency"]])
            if new_rows:
                ws.append_rows(new_rows, value_input_option="USER_ENTERED")
            # 2026-09-01 稽核 N1:**寫入成功 → 解除讀取冷卻**。
            # 稽核實跑重現的回歸:讀取先吃過一次 403 → 登記 900s 冷卻 → 上游恢復 →
            # 使用者在 Tab5 按「📥 匯入到 nav_history」→ **成功寫入 N 筆** →
            # `_clear_nh_caches()` 清得掉快取、**清不掉退避** → 緊接著的
            # `coverage_status()` 仍 raise → 紅色「累積內容讀取失敗」就顯示在
            # **一次成功匯入的正下方**,最長 15 分鐘(429 則 30 分鐘)。
            # 相對修改前是**回歸**:修改前清完快取會真的重讀,立刻看到剛匯入的資料。
            # 寫入成功證明了**這本開得起來、而且可寫**。
            # ⚠️ 2026-09-01 措辭收緊(稽核 NEW-7):~~「配額沒滿」~~ 說得太滿 ——
            # Sheets 讀與寫是不同配額桶,寫成功不證明讀配額可用(該關係未能一手查證)。
            # ⚠️ 2026-09-01 稽核 NEW-3:**這幾行必須自己包 try** —— 它在主 `try:` 之內,
            # 而主 `try:` 的 `except` 會把任何例外譯成 `raise NavHistoryError`。
            # 稽核實測(讓 record_gspread_success 拋):`ws.append_rows` **已經收到那一列**,
            # 使用者的資料**真的寫進去了**,Tab5 卻顯示「匯入失敗」——
            # 那是 §1 的**反向造假**:報一個與事實不符的失敗。
            # (pool 的 `_after_pool_write` 一開始就這樣寫了,nav 這邊漏掉 —— 稽核第五格。)
            try:
                _wa, _wsid = (("", "") if _sheet is not None
                              else _nav_backoff_ident(oauth_client))
                if _wa:
                    from infra.gspread_retry import record_gspread_success
                    record_gspread_success(_wa, _wsid)
            except Exception as _e_sb:  # noqa: BLE001 — 收尾動作壞掉不得推翻一次成功的寫入
                import sys as _sys2
                print(f"[nav_history_gs] 寫入成功但解除讀取冷卻時出錯(資料已寫入,"
                      f"不影響本次結果):{type(_e_sb).__name__}: {str(_e_sb)[:120]}",
                      file=_sys2.stderr)
            return {"written": len(new_rows), "skipped": len(points) - len(new_rows)}
    except NavHistoryError:
        raise
    except Exception as e:
        raise NavHistoryError(f"nav_history append_points 失敗:{e}") from e


def append_point(code: str, nav: Any, nav_date: Any, fund_name: str = "",
                 source: str = "app", *, _sheet: Any = None, oauth_client: Any = None) -> bool:
    """單筆 append(委派 append_points)。回傳 True=新寫入 / False=略過(去重/不足/未啟用)。"""
    res = append_points(
        [{"code": code, "nav": nav, "nav_date": nav_date,
          "fund_name": fund_name, "source": source}],
        _sheet=_sheet, oauth_client=oauth_client,
    )
    return res["written"] > 0


def _nav_backoff_ident(oauth_client: Any = None) -> "tuple[str, str]":
    """本次讀寫會用哪把憑證、打哪一本 → (actor, sheet_id);未啟用 → ("", "")。

    actor 只有 `"sa"` / `"oauth"` 兩個值,鑰匙怎麼切、為什麼切兩把,見
    `infra/gspread_retry.py` 檔尾「跨呼叫『來源冷卻』—— gspread 版」。
    """
    try:
        if is_enabled():
            return ("sa", _nav_sheet_id())
        if oauth_client is not None:
            return ("oauth", _nav_sheet_id())
    except Exception:  # noqa: BLE001 — 偵測失敗 = 當作沒有憑證(不退避,行為最保守)
        pass
    return ("", "")


def load_points(code: str | None = None, *, _sheet: Any = None,
                oauth_client: Any = None, retries: bool = False) -> list[dict]:
    """讀 nav_history(可選 code 過濾),回 [{code,date,nav,fund_name,source,recorded_at}]。
    tab 不存在 / 未啟用(SA 缺且無 OAuth)→ 回 []。供 Increment B 消費端 + 去重 lookup 用。
    oauth_client:v19.509 —— SA 缺時 UI 注入登入者身分讀雲端(與寫入同一本)。

    retries(2026-09-03,Gate 0 cron 修復)
    -------------------------------------
    **預設 `False`,行為與改動前逐字相同。** 只有 `nav_history_store.backfill_to_gs`
    的 Gate 0 預讀傳 `True`。

    起因:2026-09-02 production 事故 —— 那次讀取被 `client.open_by_key` 的**單次 5xx**
    打斷、**零重試**,直接判定「讀不到既有歷史 → 本次不寫雲端」(fail-closed,§1)。
    15 次排程執行有 2 次命中(8/31、9/2)。9/2 因新加的跨呼叫冷卻(見上方「2026-09-01
    跨呼叫來源冷卻」段)第一個 5xx 就登記 300 秒冷卻,反而讓它連自己重試的機會都沒有 ——
    對照 8/31(冷卻機制當時還不存在),2 分鐘後同一張表的其他讀取就成功了,證明那次是
    短暫性的。

    `retries=True` 時,`infra.gspread_retry.kind_for_gspread_error` 判為「多半是暫時性」
    (5xx / 逾時,`GSPREAD_RETRYABLE_KINDS`)的失敗,會在**同一次呼叫內**依
    `infra.gspread_retry.DEFAULT_QUOTA_BACKOFFS` 重試;配額(429)/封鎖(403)/設定錯誤
    (404/407)**不重試**,理由見 `infra.gspread_retry.with_gspread_retry` docstring。

    **冷卻的登記時機不變**:仍在下面 `except Exception as e:` 那一層 ——
    即**全部重試用完、例外真正往外傳播之後**才登記,不會被中途的暫時性失敗提前鎖住。

    其他呼叫點**刻意不傳 `True`**,理由是它們掛在畫面渲染 / 使用者互動的主執行緒上,
    加幾秒重試延遲會直接拖慢畫面;Gate 0 是排程 / 手動批次操作,可以吃這幾秒。
    ⚠️ **2026-09-03 逐一實測(caller 清單本身，不是推論)**:
    - `load_series()`(本檔)→ 被 `services/fund_service.py::_merge_nav_history_series`
      →`finalize_fund_metrics` 呼叫,後者是**每次算單一基金 metrics 都會經過**的函式
      (單基金頁 / 群組健診 / 批次分析共用),屬熱路徑,**不傳 `True`**。
      另一個呼叫點 `scripts/watchlist_push.py:167` 是排程腳本,理論上可承受重試延遲，
      但為保持「只動 Gate 0 這一件事」的最小改動原則，本次**未一併加上**,維持原行為。
    - `coverage_status()`(本檔)→ Tab5 資料看板背後（經 `ui/tab5_data_guard.py`
      的 `@st.cache_data` 薄快取層），同屬畫面渲染路徑,**不傳 `True`**。
    - `services/fundclear_backfill.py::analyze_backfill_conflict` 內的
      `load_points(app_code)` 呼叫 → 供 T7 帳本手動回補流程的衝突偵測用，
      同屬使用者互動同步路徑（按下按鈕等結果），**不傳 `True`**。
    ⚠️ **上一版本行原寫「`ui/helpers/nav_history_hook.py` 每次看基金就寫入的路徑」
    ——這句話指錯了函式,已就地更正（有意識的更正，不是漏刪）**：`nav_history_hook.py`
    呼叫的是 `append_points()`（寫入路徑，本檔 :371 起）與 `status()`（純讀 secrets，
    完全不碰 `_get_sheet` / gspread I/O），**不是** `load_points()`；本次修復範圍
    僅限 Gate 0 的**讀取**路徑，`append_points()` 內部同樣呼叫 `_get_sheet()`
    且同樣零重試（:399），但那是**寫入路徑**，不在本次任務範圍內
    （任務原文：「讓那次 Gate 0 預讀有重試機會，就這一件事」）——
    寫入路徑的 `_get_sheet()` 零重試現況維持不變，留給後續任務視情況處理。

    ── 2026-09-01 跨呼叫來源冷卻(客戶指示:批次 2)────────────────────────────
    **為什麼冷卻要放在這一支,而不是放在 `coverage_status` 或 UI 的快取上**:
    真正會轟炸 Google 的不是診斷頁那一次,是 `load_series` —— 健診每檔基金各呼叫
    一次,每次 `_get_sheet()`(open_by_key)+ `worksheet()` + `get_all_values()`
    = **3 趟往返**;25 檔 ≈ 75 趟/rerun,而讀取配額是 60/min/憑證。
    `services/fund_service.py` 對讀取失敗是 **fail-soft**(log 後退回 live-only),
    所以失敗**不會**讓那個迴圈停下來 —— 沒有冷卻,它會每次 rerun 重演一次。
    這就是 2026-08-14「rerun 起算 17 秒後 WebSocket onclose」的形狀。

    **冷卻期內為什麼是 raise 而不是回 `[]`**:回 `[]` 會與「這檔真的還沒累積」
    同義(§1「空有兩義」),`fund_service` 會印出「⬜ 累積序列空(SA 未啟用/無累積)」
    這種**與事實不符**的訊息,然後靜靜地少算歷史。改成 raise `NavHistoryError`,
    走的是該檔**既有的** fail-soft 分支(「⚠️ 讀取失敗,退回 live-only」)——
    與「真的打了但失敗」逐字相同,只是**沒有付出那 3 趟往返**。
    Tab5 的 `_cached_nh_coverage` 同理:它外層既有的 `system_error(...)` 會照實顯示,
    而不是掉進「⬜ 讀不到任何累積點 —— 可能尚未啟用」那個灰字(那句會誤導)。
    """
    if _sheet is None and not is_enabled() and oauth_client is None:
        return []

    # `_sheet` 是測試注入(不碰真 gspread)→ 不查冷卻、不登記,避免污染測試狀態。
    _actor, _sid = ("", "") if _sheet is not None else _nav_backoff_ident(oauth_client)
    if _actor:
        from infra.gspread_retry import should_skip_gspread
        _skip, _left, _kind = should_skip_gspread(_actor, _sid)
        if _skip:
            raise NavHistoryError(
                f"nav_history 剛失敗過(kind={_kind}),來源冷卻中還剩 {_left:.0f} 秒 "
                f"→ 本次不打 Google Sheets(避免連續轟炸 / 配額耗盡)。"
                f"要立即重試請用 sidebar 的「全域刷新」。")

    try:
        with _gs_guard(oauth_client, _sheet):     # v19.509:序列化共用 OAuth client 併發讀
            if retries and _sheet is None:
                # 2026-09-03 Gate 0 修復:根因是 `_get_sheet()` 內 `client.open_by_key`
                # 的單次 5xx、零重試(見 load_points docstring「retries」段)。只重試
                # `_get_sheet()` 這一步 —— 之後的 `sh.worksheet()` / `get_all_values()`
                # 邏輯不動一行,刻意不包一層巢狀 function:那樣會把這兩行的 AST 歸屬
                # 從 `load_points()` 換到別的函式名下,悄悄弄丟
                # `tests/test_services_purity_contract.py::GSPREAD_DEBT` 的既有登記
                # (`"services/nav_history_gs.py::load_points()"`)——那條測試按**符號名**
                # 認地雷,不是按行號,搬家等於這裡多開一個「未登記」的新地雷。
                # 也**不在這裡登記冷卻** —— 冷卻只在下面 except 那一層、全部重試用完
                # 之後才登記。
                from infra.gspread_retry import with_gspread_retry
                sh = with_gspread_retry(_get_sheet, oauth_client)
            else:
                sh = _sheet if _sheet is not None else _get_sheet(oauth_client)
            try:
                ws = sh.worksheet(_WS_NAV)
            except Exception as _e_ws:
                # 2026-09-01:原本這裡是**無條件** `return []` —— 於是 `sh.worksheet()`
                # 打出來的 429 / 403 會被壓成「這張表沒有 nav_history 分頁」,
                # 對外與「分頁真的還沒建」完全同義(§1「空有兩義」),而且
                # **冷卻機制永遠學不到那次失敗**(app.py 檔頭已記載這條鏈把
                # `_cached_nh_coverage` 鎖滿 TTL_5MIN 的實測)。
                # 現在只放行「不是 API 錯誤」的那一種(WorksheetNotFound 等);
                # 帶 HTTP 狀態碼的 / 配額錯誤一律往上拋,由外層登記冷卻。
                from infra.gspread_retry import http_status_of, is_quota_error
                if http_status_of(_e_ws) is None and not is_quota_error(_e_ws):
                    return []
                raise
            rows = ws.get_all_values()[1:]
    except Exception as e:
        if _actor:
            from infra.gspread_retry import record_gspread_failure
            _k, _cd = record_gspread_failure(_actor, _sid, e)
            if _k:
                import sys as _sys
                print(f"[nav_history_gs] 讀取失敗 → 登記冷卻 {_cd}s(key={_k}):"
                      f"{type(e).__name__}: {str(e)[:120]}", file=_sys.stderr)
        raise NavHistoryError(f"nav_history load 失敗:{e}") from e
    if _actor:
        from infra.gspread_retry import record_gspread_success
        record_gspread_success(_actor, _sid)

    want = str(code or "").strip().upper()
    out: list[dict] = []
    for r in rows:
        if len(r) < 3:
            continue
        c = str(r[0]).strip().upper()
        if want and c != want:
            continue
        try:
            nav_f = float(r[2])
        except (TypeError, ValueError):
            continue
        out.append({
            # 2026-08-28 稽核修正:讀取端**過去沒有**正規化,與 `append_points` 的去重鍵
            # 不同尺 —— 既有列若是手填 '2020/1/2',Gate 0 拿 ISO 去比對永遠零重疊,
            # 整道閘門靜默失效(理由與實測見 `norm_date_key`)。
            "code": c, "date": norm_date_key(r[1]), "nav": nav_f,
            "fund_name": r[3] if len(r) > 3 else "",
            "source": r[4] if len(r) > 4 else "",
            "recorded_at": r[5] if len(r) > 5 else "",
            # 2026-09-01 第 7 欄。舊列(6 格 / 最小 3 欄 schema)→ `""`(未知),
            # 同既有 `fund_name` / `source` 的容忍寫法,**不回填任何猜測值**(§1)。
            "currency": r[6] if len(r) > 6 else "",
        })
    return out


def load_series(code: str, *, _sheet: Any = None, oauth_client: Any = None):
    """v19.360 Increment B:讀 nav_history 累積點 → pd.Series(DatetimeIndex→float)。

    供 L2 fund_service 合併進 metrics 計算(消費端接線)。
    - 同日重複 keep-last、昇冪排序(§4.2 monotonic + unique)
    - provenance:attrs["source"]="GoogleSheet:nav_history:{code}" + attrs["fetched_at"]
    - 無資料 / 未啟用 → 空 Series(§1 不偽造);真 I/O 失敗 → NavHistoryError 上拋
      (由 caller 決定 fail-soft 退回 live-only)
    """
    import pandas as pd

    pts = load_points(code, _sheet=_sheet, oauth_client=oauth_client)  # 未啟用/無 tab → [];I/O 失敗 → raise
    if not pts:
        return pd.Series(dtype=float)
    idx = pd.to_datetime([p["date"] for p in pts], errors="coerce")
    s = pd.Series([p["nav"] for p in pts], index=idx, dtype=float)
    s = s[s.index.notna()]                       # 壞日期顯式丟棄(load_points 已濾 nav<=0)
    if s.empty:
        return pd.Series(dtype=float)
    s = s.groupby(s.index).last().sort_index()   # 同日 keep-last + 昇冪
    s.attrs["source"] = f"GoogleSheet:nav_history:{str(code).strip().upper()}"
    s.attrs["fetched_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
    # 2026-09-01:**逐列一致才敢宣告**幣別(§1 / §4.1)。這張表的列來自多條寫入路徑、
    # 多個 fetcher,同一個 code 的列**可以**混到不同幣別;只要有一列未知或彼此不一致,
    # 就完全不設這個 key(未知),**絕不挑一個、絕不換算**。
    # ⚠️ 沒有這幾行的話,加欄位是**零效果** —— 本函式原本只設 `source` / `fetched_at`,
    #    下游(`fund_service._merge_nav_history_series`)拿不到累積序列的幣別宣告。
    # ⚠️ 比對範圍刻意取**該 code 的全部載入列**,不是只取存活到 Series 裡的那些:
    #    方向是保守的(只會少宣告,不會多宣告),而多宣告才是會害死人的那一邊。
    from shared.data_quality import reconcile_row_currencies
    _ccy = reconcile_row_currencies([p.get("currency") for p in pts])
    if _ccy:
        s.attrs["currency"] = _ccy
    return s


def coverage_status(codes: "list | tuple | None" = None, *, _sheet: Any = None,
                    oauth_client: Any = None) -> dict:
    """每檔基金**累積了多少** —— 回 {CODE: {points, first, last, span_days}}。

    2026-08-11 新增。與 `status()` 互補,兩者回答的是**不同問題**:
      - `status()`        → 「能不能累」(兩把 secrets 設對沒)
      - `coverage_status()` → 「累了多少」(點數 / 起訖 / 跨度)

    為什麼需要它:累積機制寫入正常(畫面每次都有「本次新存 N 筆」)、狀態燈是綠的,
    但序列可以一動不動好幾週 —— 因為累到的點還全部落在 live 的滾動窗內
    (`fund_service._merge_nav_history_series` 的 `added <= 0` 分支)。
    這三件事同時成立時,**畫面上沒有任何地方講得出中間的落差**,只能猜。
    本函式就是把「累了多少」這件事變成可讀的數字(§5 可觀測)。

    Args:
        codes: 只回這些代碼(大小寫不拘)。None → 回 sheet 內全部。
        _sheet: 測試注入用(繞過真 gspread)。

    Returns:
        `{CODE: {"points": int, "first": "YYYY-MM-DD", "last": ..., "span_days": int}}`
        **未啟用 / tab 不存在 → 回 `{}`** —— 呼叫端須據此顯示「未啟用」而非「0 點」,
        兩者意義完全不同(§1:不知道 ≠ 沒有)。
        真 I/O 失敗 → `NavHistoryError` 上拋,由 UI 顯示而不是靜默留白。
    """
    _want = {str(c).strip().upper() for c in (codes or []) if str(c).strip()}
    _pts = load_points(None, _sheet=_sheet, oauth_client=oauth_client)   # 一次讀完整張表,再本地分組(省 quota)
    if not _pts:
        return {}

    _by: dict = {}
    for _p in _pts:
        _c = _p["code"]
        if _want and _c not in _want:
            continue
        _d = _p["date"]
        if not _d:
            continue
        _e = _by.setdefault(_c, {"dates": set()})
        _e["dates"].add(_d)          # (code, date) 是主鍵,但防禦性去重

    _out: dict = {}
    for _c, _e in _by.items():
        _ds = sorted(_e["dates"])
        _span = 0
        try:
            _span = (_dt.date.fromisoformat(_ds[-1])
                     - _dt.date.fromisoformat(_ds[0])).days
        except (ValueError, IndexError):
            _span = 0                 # 日期格式壞 → 跨度未知,點數仍誠實回報
        _out[_c] = {
            "points": len(_ds),
            "first": _ds[0],
            "last": _ds[-1],
            "span_days": _span,
        }
    return _out


# ── v19.361 PR-2(A):保單對帳單 CSV 歷史匯入 ──────────────────────
_DATE_COL_HINTS = ("日期", "淨值日期", "除息日", "date", "nav_date", "時間")
_NAV_COL_HINTS = ("淨值", "單位淨值", "基金淨值", "nav", "value", "price")


def _pick_col(cols: list, hints: tuple, exclude: int | None = None) -> int | None:
    """從 header 找欄位 index(大小寫不敏感、substring 命中)。找不到回 None。

    exclude:跳過該 index —— 如「淨值日期」同時含「淨值」,nav 欄偵測須排除已選定的
    date 欄,否則兩者都指到同一欄(v19.361 匯入測試抓到的真 bug)。
    """
    for i, c in enumerate(cols):
        if i == exclude:
            continue
        low = str(c).strip().lower()
        if any(h.lower() in low for h in hints):
            return i
    return None


def import_csv_text(code: str, csv_text: str, *, fund_name: str = "",
                    source: str = "csv_import", _sheet: Any = None,
                    oauth_client: Any = None) -> dict:
    """CSV 文字 → 解析 → 批次寫入 nav_history(委派 append_points:§1 過濾 + §5 去重)。

    唯一能「立刻補回數年歷史」的路:user 從保險公司對帳單下載歷史淨值,一次灌入。
    - 欄位偵測:header 含 日期/淨值 等關鍵字 → 對應欄;無 header → 第 1 欄=date、第 2 欄=nav
    - 日期:ROC(113/03/15)與西元都吃(復用 nav_history_store._parse_roc_or_western_date)
    - 壞列顯式 skip + 計數回報(§1:不猜、不靜默丟)
    回 {"enabled", "rows", "parsed", "written", "skipped_rows", "skipped_dup"}。
    """
    import csv as _csv
    import io

    from services.nav_history_store import _parse_roc_or_western_date

    enabled = _sheet is not None or is_enabled() or oauth_client is not None
    out = {"enabled": enabled, "rows": 0, "parsed": 0, "written": 0,
           "skipped_rows": 0, "skipped_dup": 0}

    rows = [r for r in _csv.reader(io.StringIO(csv_text or "")) if any(
        str(c).strip() for c in r)]
    if not rows:
        return out

    # header 偵測:首列有任一欄命中 date/nav 關鍵字 → 當 header
    # date 先選;nav 排除 date 欄(「淨值日期」含「淨值」會誤中,exclude 防呆)
    d_i = _pick_col(rows[0], _DATE_COL_HINTS)
    n_i = _pick_col(rows[0], _NAV_COL_HINTS, exclude=d_i)
    if d_i is not None or n_i is not None:
        data_rows = rows[1:]
        d_i = 0 if d_i is None else d_i
        n_i = 1 if n_i is None else n_i
    else:                       # 無 header:第 1 欄=date、第 2 欄=nav
        data_rows, d_i, n_i = rows, 0, 1

    out["rows"] = len(data_rows)
    points: list[dict] = []
    for r in data_rows:
        if len(r) <= max(d_i, n_i):
            out["skipped_rows"] += 1
            continue
        ts = _parse_roc_or_western_date(str(r[d_i]))
        try:
            nav_f = float(str(r[n_i]).replace(",", "").strip())
        except (TypeError, ValueError):
            nav_f = None
        if ts is None or nav_f is None or nav_f <= 0:
            out["skipped_rows"] += 1     # §1 顯式 skip + 計數,不猜不補
            continue
        points.append({"code": code, "nav": nav_f,
                       "nav_date": ts.strftime("%Y-%m-%d"),
                       "fund_name": fund_name, "source": source})
    out["parsed"] = len(points)
    if not points or not enabled:
        return out

    res = append_points(points, _sheet=_sheet, oauth_client=oauth_client)   # (code,date) 去重 + 一次 append_rows
    out["written"] = res["written"]
    out["skipped_dup"] = out["parsed"] - res["written"]
    return out


__all__ = ["append_point", "append_points", "load_points", "load_series",
           "import_csv_text", "coverage_status", "is_enabled", "status",
           "backend_status", "norm_date_key", "NavHistoryError"]
