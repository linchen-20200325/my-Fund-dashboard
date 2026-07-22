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
§8.2:L2 service(比照 services/auto_search_store_gs.py),複用 `macro_weights_sheet_id`
     那本 workbook 加 `nav_history` 分頁;UI(L3)呼叫本層,**不自己開 gspread**。
     GS secrets 未設(local / CI)→ 安靜 no-op,不干擾。gspread I/O 為持久化職責,
     不在 §8.2「L2 禁 requests/httpx/bs4/feedparser」清單,且有 auto_search_store_gs 先例。

Worksheet schema `nav_history`(A1 = headers):
    code | date | nav | fund_name | source | recorded_at
主鍵 (code, date)。
"""
from __future__ import annotations

import datetime as _dt
from typing import Any

_WS_NAV = "nav_history"
_NAV_HEADERS = ["code", "date", "nav", "fund_name", "source", "recorded_at"]


class NavHistoryError(Exception):
    """nav_history 寫入/讀取失敗(§1 Fail Loud:呼叫端須看見,不靜默 no-op)。"""


def is_enabled() -> bool:
    """GS secrets 是否齊備(複用 macro.weights_store,同一份 sheet)。未齊 → 安靜 no-op。"""
    try:
        from services.macro.weights_store import _gs_enabled
        return _gs_enabled()
    except Exception:
        return False


def status() -> dict:
    """v19.362 ①:累積狀態診斷 — 回 {"enabled": bool, "missing": [缺的 secret 名]}。

    體檢瑕疵 #6「secrets 沒設 = 安靜略過 → 你以為在累積其實沒有」的解方:
    UI(Tab5 狀態燈 / hook 一次性提示)用本 fn 把靜默失敗變可見(§5 可觀測)。
    """
    missing: list[str] = []
    try:
        from infra.config import get_secret
        sa = get_secret("google_service_account") or {}
        if not (isinstance(sa, dict) and sa.get("client_email")):
            missing.append("google_service_account")
        if not get_secret("macro_weights_sheet_id"):
            missing.append("macro_weights_sheet_id")
    except Exception:
        missing = ["google_service_account", "macro_weights_sheet_id"]
    return {"enabled": not missing, "missing": missing}


def _norm_date(v: Any) -> str:
    """轉 'YYYY-MM-DD'。接受 date/datetime/'YYYY/MM/DD'/'YYYY-MM-DD...'。壞值回 ''(§1 不猜)。"""
    if v is None or v == "":
        return ""
    if isinstance(v, (_dt.date, _dt.datetime)):
        return v.strftime("%Y-%m-%d")
    s = str(v).strip().replace("/", "-")[:10]
    parts = s.split("-")
    if len(parts) == 3 and len(parts[0]) == 4 and all(p.isdigit() for p in parts):
        return s
    return ""


def _clean_points(points: list[dict]) -> list[dict]:
    """normalize + §1 過濾:code 空 / date 壞 / nav<=0 全丟(不偽造)。"""
    out: list[dict] = []
    for p in points:
        code = str(p.get("code") or "").strip().upper()
        d = _norm_date(p.get("nav_date"))
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
    return out


def _get_sheet():
    """開啟 macro_weights_sheet_id 那本 workbook(複用 secrets + 認證,同 auto_search_store_gs)。"""
    from infra.config import require_secret
    from repositories.policy_repository import get_gspread_client
    creds = dict(require_secret("google_service_account"))
    sheet_id = require_secret("macro_weights_sheet_id")
    client = get_gspread_client(creds)
    return client.open_by_key(sheet_id)


def _get_worksheet(sh):
    """取得 nav_history worksheet,不存在則建立 + 寫 header。"""
    try:
        return sh.worksheet(_WS_NAV)
    except Exception:
        ws = sh.add_worksheet(title=_WS_NAV, rows=1000, cols=len(_NAV_HEADERS))
        ws.update("A1", [_NAV_HEADERS])
        return ws


def append_points(points: list[dict], *, _sheet: Any = None) -> dict:
    """批次 append 多筆 nav 點:**讀一次去重 + 一次 append_rows**(省 Sheets quota;60 reads/min)。

    points: [{"code", "nav", "nav_date", "fund_name"(opt), "source"(opt)}]
    回傳 {"written": int, "skipped": int}。
    §1:資料不足的點被丟;GS 未啟用(且未注入 _sheet)→ 安靜 no-op 回 written=0。
        真 GS I/O 失敗 → raise NavHistoryError。
    _sheet:測試注入用(繞過真 gspread)。
    """
    clean = _clean_points(points)
    if not clean:
        return {"written": 0, "skipped": len(points)}
    if _sheet is None and not is_enabled():
        return {"written": 0, "skipped": len(points)}  # local/CI 無 secrets:安靜略過

    try:
        sh = _sheet if _sheet is not None else _get_sheet()
        ws = _get_worksheet(sh)
        existing = ws.get_all_values()  # 含 header
        seen: set = set()
        for r in existing[1:]:
            if len(r) >= 2:
                seen.add((str(r[0]).strip().upper(), str(r[1]).strip()[:10]))
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
                 source: str = "app", *, _sheet: Any = None) -> bool:
    """單筆 append(委派 append_points)。回傳 True=新寫入 / False=略過(去重/不足/未啟用)。"""
    res = append_points(
        [{"code": code, "nav": nav, "nav_date": nav_date,
          "fund_name": fund_name, "source": source}],
        _sheet=_sheet,
    )
    return res["written"] > 0


def load_points(code: str | None = None, *, _sheet: Any = None) -> list[dict]:
    """讀 nav_history(可選 code 過濾),回 [{code,date,nav,fund_name,source,recorded_at}]。
    tab 不存在 / 未啟用 → 回 []。供 Increment B 消費端 + 去重 lookup 用。
    """
    if _sheet is None and not is_enabled():
        return []
    try:
        sh = _sheet if _sheet is not None else _get_sheet()
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


def load_series(code: str, *, _sheet: Any = None):
    """v19.360 Increment B:讀 nav_history 累積點 → pd.Series(DatetimeIndex→float)。

    供 L2 fund_service 合併進 metrics 計算(消費端接線)。
    - 同日重複 keep-last、昇冪排序(§4.2 monotonic + unique)
    - provenance:attrs["source"]="GoogleSheet:nav_history:{code}" + attrs["fetched_at"]
    - 無資料 / 未啟用 → 空 Series(§1 不偽造);真 I/O 失敗 → NavHistoryError 上拋
      (由 caller 決定 fail-soft 退回 live-only)
    """
    import pandas as pd

    pts = load_points(code, _sheet=_sheet)  # 未啟用/無 tab → [];I/O 失敗 → raise
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
                    source: str = "csv_import", _sheet: Any = None) -> dict:
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

    enabled = _sheet is not None or is_enabled()
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

    res = append_points(points, _sheet=_sheet)   # (code,date) 去重 + 一次 append_rows
    out["written"] = res["written"]
    out["skipped_dup"] = out["parsed"] - res["written"]
    return out


__all__ = ["append_point", "append_points", "load_points", "load_series",
           "import_csv_text", "is_enabled", "status", "NavHistoryError"]
