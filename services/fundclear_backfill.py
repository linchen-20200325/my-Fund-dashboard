"""services/fundclear_backfill.py — L2 編排:FundClear offshore 歷史淨值 → GS nav_history。

流程(spec + user 2026-08-13 決策「用 App 現有持倉名字自動比對」+「先試 1-2 檔」+「存 GS」):
  1. 用持倉**基金名**去 FundClear `fund-name-selection` 清單模糊比對 → 候選 (organize/fund) 三碼之二
  2. user 眼睛確認 → 選級別(class)→ 抓完整歷史(單次 POST,~20yr)
  3. 轉 points → `services.nav_history_gs.append_points` 寫進 GS `nav_history` 分頁
     → 被 `fund_service._merge_nav_history_series` 讀回併入序列 → 餵 `compute_1y_total_return`
     → live 全敗時(如 ACTI71 抓 0 筆)純累積歷史整段頂上(v19.366),根治外推誤判。

L2:呼叫 L1 `repositories.fundclear_offshore` + L2 `services.nav_history_gs`(允許 L2→L1/L2)。
名稱正規化 + 排名為純函式(離線可測);抓取/寫入在部署環境(NAS proxy)執行。
"""
from __future__ import annotations

import difflib
import logging
import re
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)

_MATCH_MIN_SCORE = 0.55        # 低於此不列入候選(避免無關基金混入)
_CONTAINS_SCORE = 0.9          # 子字串完全包含 → 高分(級別後綴差異容忍)


def _normalize_name(name) -> str:
    """基金名正規化(比對用):去空白 / 全形半形括號統一 / 去常見級別·幣別雜訊。"""
    s = re.sub(r"\s+", "", str(name or ""))
    s = s.replace("（", "(").replace("）", ")")
    return s


def rank_candidates(target_name: str, fund_list: list, top: int = 5) -> list[dict]:
    """純函式:target 基金名 vs FundClear 基金清單 → 依相似度排序候選(附 score)。

    子字串完全包含 → 高分(App 名多為基準名、FundClear 名可能帶級別後綴)。
    """
    _t = _normalize_name(target_name)
    if not _t:
        return []
    scored: list[dict] = []
    for f in (fund_list or []):
        _n = _normalize_name(f.get("name"))
        if not _n:
            continue
        _ratio = difflib.SequenceMatcher(None, _t, _n).ratio()
        _score = _CONTAINS_SCORE if (_t in _n or _n in _t) else _ratio
        if _score >= _MATCH_MIN_SCORE:
            scored.append({**f, "score": round(float(_score), 4)})
    scored.sort(key=lambda x: -x["score"])
    return scored[:top]


def resolve_search_name(term: str, code_name_map: dict) -> tuple[str, str]:
    """user 想**用代碼**搜:term 命中 code_name_map(代碼→名稱)→ 回 (名稱, 代碼大寫);

    否則視 term 為名稱 → 回 (term, "")。用途:拿**名稱**去 FundClear 找、拿**代碼**存回
    nav_history(健診才讀得回)。code_name_map 由呼叫端從選股池 + 持倉組出(代碼統一大寫)。
    """
    _key = str(term or "").strip().upper()
    _name = (code_name_map or {}).get(_key)
    if _name:
        return str(_name).strip(), _key
    return str(term or "").strip(), ""


def find_fund_candidates(target_name: str, organize_code: Optional[str] = None,
                         top: int = 5, scan_range: int = 0) -> list[dict]:
    """用基金名找 FundClear 候選基金 [{name, value=fundCode, organize_code, organize_name, score}]。

    organize_code 給定 → 只搜該機構(快、省呼叫);
    scan_range>0 → **暴力掃描** 001..{scan_range:03d} 機構(繞過抓不到的機構清單 endpoint,
      逐一打**已驗證**的 fund-name-selection;較慢但不需正確 endpoint,適合部署環境自助);
    否則 → 列舉所有機構(spec §2.5 未驗證,org endpoint 失敗會 raise,呼叫端提示改填代碼或掃描)。
    """
    from repositories import fundclear_offshore as fc
    if organize_code:
        orgs = [{"value": organize_code, "name": ""}]
    elif scan_range and scan_range > 0:
        orgs = [{"value": f"{i:03d}", "name": ""} for i in range(1, scan_range + 1)]
    else:
        orgs = fc.list_organizes()                 # 失敗 → FundclearError 往上拋(§1)
    all_funds: list[dict] = []
    for o in orgs:
        _oc = o.get("value")
        if not _oc:
            continue
        try:
            for f in fc.list_funds(_oc):
                all_funds.append({**f, "organize_code": _oc,
                                  "organize_name": o.get("name", "")})
        except Exception as e:  # noqa: BLE001 — 單一機構清單失敗只記 warning,不中斷其餘(NFR-1)
            logger.warning("list_funds(%s) 失敗:%s", _oc, e)
    return rank_candidates(target_name, all_funds, top)


def list_classes_for(organize_code: str, fund_code: str) -> list[dict]:
    """薄封裝 L1:某基金的級別清單(供 UI 讓 user 選 Acc/配息 級別)。"""
    from repositories import fundclear_offshore as fc
    return fc.list_classes(organize_code, fund_code)


def analyze_backfill_conflict(app_code: str, points: list) -> dict:
    """寫入前的衝突偵測（稽核 E6，2026-08-14）。

    回 `{n_existing, n_overlap, n_conflict, samples, verdict}`。

    **為什麼一定要有這一步**：`nav_history` 的去重鍵只有 `(code, date)`。
    同一檔基金常有多個級別（美元累積 / 美元配息 / 歐元避險…），淨值完全不同。
    一旦選錯級別寫進去，**正確級別的淨值會被當成重複而永遠寫不進來** ——
    而錯的那份會被健診拿去算 1Y 報酬、Sharpe、σ。而那個分頁在說明書上是
    「🚨 絕對不要刪…無法從任何來源重建」。

    判定邏輯：比對重疊日期的淨值。同級別的差異只該來自四捨五入；
    差超過 `NAV_BACKFILL_CONFLICT_REL_TOL` 幾乎必然是不同級別。

    verdict:
      - `"clean"`     沒有重疊 → 純新增，安全
      - `"duplicate"` 有重疊但數值一致 → 重複下載，寫進去也只會被略過
      - `"conflict"`  有重疊且數值不同 → **極可能選錯級別**，應擋下
      - `"unknown"`   讀不到既有資料（GS 未啟用等）→ 不宣稱安全（§1）
    """
    from shared.signal_thresholds import NAV_BACKFILL_CONFLICT_REL_TOL

    _blank = {"n_existing": 0, "n_overlap": 0, "n_conflict": 0,
              "samples": [], "verdict": "unknown"}
    try:
        from services.nav_history_gs import load_points
        _existing = load_points(app_code) or []
    except Exception as _e:  # noqa: BLE001
        import sys as _sys
        print(f"[fundclear_backfill] 衝突偵測讀不到既有 nav_history: "
              f"{type(_e).__name__}: {_e}", file=_sys.stderr)
        return {**_blank, "reason": f"{type(_e).__name__}: {_e}"}

    _old = {}
    for _p in _existing:
        _d = str(_p.get("date") or _p.get("nav_date") or "")[:10]
        try:
            _v = float(_p.get("nav"))
        except (TypeError, ValueError):
            continue
        if _d and _v > 0:
            _old[_d] = _v
    if not _old:
        # 讀得到但一筆都沒有 → 這檔還沒累積過 → 純新增
        return {**_blank, "verdict": "clean"}

    _overlap: list = []
    _conflict: list = []
    for _p in points:
        _d = str(_p.get("nav_date") or "")[:10]
        _v = _p.get("nav")
        if _d not in _old:
            continue
        _overlap.append(_d)
        try:
            _new = float(_v)
        except (TypeError, ValueError):
            continue
        _ref = _old[_d]
        if _ref > 0 and abs(_new - _ref) / _ref > NAV_BACKFILL_CONFLICT_REL_TOL:
            _conflict.append({"date": _d, "existing": _ref, "incoming": _new,
                              "diff_pct": (_new - _ref) / _ref * 100.0})

    _verdict = ("conflict" if _conflict
                else "duplicate" if _overlap else "clean")
    return {
        "n_existing": len(_old),
        "n_overlap": len(_overlap),
        "n_conflict": len(_conflict),
        # 只回前幾筆給 UI 顯示 —— 使用者要的是「看一眼就知道差多少」,不是全部倒出來
        "samples": sorted(_conflict, key=lambda x: x["date"])[:5],
        "verdict": _verdict,
    }


def download_and_store(organize_code: str, fund_code: str, class_code: str,
                       app_code: str, fund_name: str = "",
                       start: Optional[date] = None, end: Optional[date] = None,
                       *, dry_run: bool = False) -> dict:
    """抓完整歷史 →（可選）寫 GS nav_history。

    回 `{ok, count, currency, span, written, skipped, conflict, dry_run, reason}`。

    app_code:持倉端的內部碼(如 ACTI71)—— nav_history 以此為 key,才會被健診讀回。
    §1:查無資料 → ok=False + reason(不靜默寫空)。

    dry_run（稽核 E6，2026-08-14）
    -----------------------------
    True → **只抓不寫**，回傳含 `conflict` 衝突分析供 UI 預覽。
    原本這支是「按一下就把數千筆寫進一個無法重建的分頁」，中間沒有任何確認；
    而去重鍵只有 `(code, date)`，選錯級別寫進去之後正確資料就永遠進不來了。
    現在 UI 走「① 預覽 → 看衝突分析 → ② 確認寫入」兩段。

    ⚠️ 非 dry-run 時若偵測到 `conflict`，**本函式仍會擋下不寫**（fail-closed）——
    確認鈕的責任是「使用者看過了」，不是「跳過安全檢查」。
    要覆蓋既有資料請先處理 Sheet 上那幾列（本函式不做刪除：§1 不代使用者毀資料）。
    """
    from repositories import fundclear_offshore as fc
    _start = start or date(2000, 1, 1)             # spec §3.5:早於成立日不報錯,只回實際區間
    _end = end or date.today()
    df = fc.get_nav_history(organize_code, fund_code, class_code, _start, _end)
    if df.empty:
        return {"ok": False, "count": 0, "reason": "FundClear 查無資料(級別/三碼可能不符)"}

    _currency = str(df.attrs.get("currency") or "")
    points = [{"code": app_code, "nav": float(r.nav),
               "nav_date": r.nav_date.strftime("%Y-%m-%d"),
               "fund_name": fund_name, "source": "fundclear_offshore"}
              for r in df.itertuples(index=False)]   # itertuples(非 iterrows)符 NFR-2

    _base = {
        "ok": True,
        "count": int(len(df)),
        "currency": _currency,
        "span": (str(df["nav_date"].min())[:10], str(df["nav_date"].max())[:10]),
        "conflict": analyze_backfill_conflict(app_code, points),
        "dry_run": bool(dry_run),
        "written": 0,
        "skipped": 0,
    }
    if dry_run:
        return _base

    if _base["conflict"].get("verdict") == "conflict":
        # fail-closed:重疊日的淨值對不上 = 幾乎必然是不同級別。
        # 寫進去會讓正確資料**永久**進不來,而且健診會拿錯的算報酬(§1)。
        return {**_base, "ok": False,
                "reason": "偵測到淨值衝突（極可能選錯級別）—— 已擋下未寫入"}

    from services.nav_history_gs import append_points
    _res = append_points(points)
    return {**_base,
            "written": _res.get("written"),
            "skipped": _res.get("skipped")}


__all__ = ["rank_candidates", "find_fund_candidates", "list_classes_for",
           "analyze_backfill_conflict", "download_and_store"]
