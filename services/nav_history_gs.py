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
§8.2:L2 service(比照 services/auto_search_store_gs.py),存進 `_nav_sheet_id()` 那本
     workbook(v19.472 改獨立 `NAV_SHEET_ID`)加 `nav_history` 分頁;UI(L3)呼叫本層,**不自己開 gspread**。
     GS secrets 未設(local / CI)→ 安靜 no-op,不干擾。gspread I/O 為持久化職責,
     不在 §8.2「L2 禁 requests/httpx/bs4/feedparser」清單,且有 auto_search_store_gs 先例。

Worksheet schema `nav_history`(A1 = headers):
    code | date | nav | fund_name | source | recorded_at
主鍵 (code, date)。
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
_NAV_HEADERS = ["code", "date", "nav", "fund_name", "source", "recorded_at"]
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


def _clean_points(points: list[dict]) -> list[dict]:
    """normalize + §1 過濾:code 空 / date 壞 / nav<=0 全丟(不偽造)。

    §5 可觀測性(v19.461):日期被 `_norm_date` 剔除(未來日 / 月日超範圍 / 非法日)且
    **原始 nav_date 非空**時 → 這是「有值但壞掉」的髒資料(多半上游 misparse,如 user
    2026-08-17 ALZF9 被 parse 成 2026-10-12 未來日)。單獨計數 + log 一行,避免和去重
    `skipped` 混算被淹沒(稽核 §5 建議)。此處只 log,過濾行為不變(仍不寫入 §1)。
    """
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


def _get_worksheet(sh):
    """取得 nav_history worksheet,不存在則建立 + 寫 header。"""
    try:
        return sh.worksheet(_WS_NAV)
    except Exception:
        ws = sh.add_worksheet(title=_WS_NAV, rows=1000, cols=len(_NAV_HEADERS))
        ws.update("A1", [_NAV_HEADERS])
        return ws


def append_points(points: list[dict], *, _sheet: Any = None, oauth_client: Any = None) -> dict:
    """批次 append 多筆 nav 點:**讀一次去重 + 一次 append_rows**(省 Sheets quota;60 reads/min)。

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
                    # v19.489:去重鍵的日期先過 _norm_date 正規化,讓 user 手填的 '2020/1/2'
                    # 與系統寫的 ISO '2020-01-02' 視為同一天(否則同日兩格式 → 重複列 + load
                    # 時系統值覆蓋 user 值)。_norm_date 回 '' 的怪日期退回原字串,不弱化既有去重。
                    _ed = _norm_date(str(r[1]).strip()) or str(r[1]).strip()[:10]
                    seen.add((str(r[0]).strip().upper(), _ed))
            recorded_at = _dt.datetime.now(_dt.timezone.utc).isoformat()
            new_rows: list = []
            for c in clean:  # 同批內也去重(同 code+date 只留第一筆)
                key = (c["code"], c["date"])
                if key in seen:
                    continue
                seen.add(key)
                new_rows.append([c["code"], c["date"], c["nav"],
                                 c["fund_name"], c["source"], recorded_at])
            if new_rows:
                ws.append_rows(new_rows, value_input_option="USER_ENTERED")
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


def load_points(code: str | None = None, *, _sheet: Any = None,
                oauth_client: Any = None) -> list[dict]:
    """讀 nav_history(可選 code 過濾),回 [{code,date,nav,fund_name,source,recorded_at}]。
    tab 不存在 / 未啟用(SA 缺且無 OAuth)→ 回 []。供 Increment B 消費端 + 去重 lookup 用。
    oauth_client:v19.509 —— SA 缺時 UI 注入登入者身分讀雲端(與寫入同一本)。
    """
    if _sheet is None and not is_enabled() and oauth_client is None:
        return []
    try:
        with _gs_guard(oauth_client, _sheet):     # v19.509:序列化共用 OAuth client 併發讀
            sh = _sheet if _sheet is not None else _get_sheet(oauth_client)
            try:
                ws = sh.worksheet(_WS_NAV)
            except Exception:
                return []
            rows = ws.get_all_values()[1:]
    except Exception as e:
        raise NavHistoryError(f"nav_history load 失敗:{e}") from e

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
            "code": c, "date": str(r[1]).strip()[:10], "nav": nav_f,
            "fund_name": r[3] if len(r) > 3 else "",
            "source": r[4] if len(r) > 4 else "",
            "recorded_at": r[5] if len(r) > 5 else "",
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
           "backend_status", "NavHistoryError"]
