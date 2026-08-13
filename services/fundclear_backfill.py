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


def download_and_store(organize_code: str, fund_code: str, class_code: str,
                       app_code: str, fund_name: str = "",
                       start: Optional[date] = None, end: Optional[date] = None) -> dict:
    """抓完整歷史 → 寫 GS nav_history。回 {ok, count, currency, span, written, skipped, reason}。

    app_code:持倉端的內部碼(如 ACTI71)—— nav_history 以此為 key,才會被健診讀回。
    §1:查無資料 → ok=False + reason(不靜默寫空)。
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

    from services.nav_history_gs import append_points
    _res = append_points(points)
    return {
        "ok": True,
        "count": int(len(df)),
        "currency": _currency,
        "span": (str(df["nav_date"].min())[:10], str(df["nav_date"].max())[:10]),
        "written": _res.get("written"),
        "skipped": _res.get("skipped"),
    }


__all__ = ["rank_candidates", "find_fund_candidates", "list_classes_for",
           "download_and_store"]
