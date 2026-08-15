"""services/tdcc_nav_accumulate.py — L2:TDCC 11641 近7天官方淨值 → 對到持倉 → nav_history points。

流程:L1 `fetch_offshore_nav_recent()`(11641 近7天)→ 每檔持倉用**名稱**高門檻對到 11641 的基金
→ 產出 `append_points` 契約的 points(code=持倉內部碼 → 健診讀得回),對不上誠實跳過並回報(§1)。

安全(headless 適用):高門檻(預設 0.9,子字串命中級)+ 回 report(matched/unmatched + score)供
呼叫端(UI / cron log)檢視;只 append 不覆寫;近7天窗 → 漏跑可補。名稱對錯風險由高門檻 + 報表控管,
**建議首次以 UI 手動跑、核對 matched 名稱無誤後再排每日 cron**。
"""
from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

_MIN_SCORE = 0.9        # 名稱比對門檻(rank_candidates 子字串命中=0.9);headless 求穩


def accumulate_points(holdings: list, frame: "pd.DataFrame | None",
                      min_score: float = _MIN_SCORE) -> tuple:
    """持倉 [{code, name}] + 11641 frame → (points, report)。

    points:[{code(持倉碼), nav, nav_date, fund_name, source}](append_points 契約)。
    report:{matched:[{code, matched_name, score, n}], unmatched:[code...]}。
    """
    if frame is None or len(frame) == 0:
        return [], {"matched": [], "unmatched": [str(h.get("code") or "?") for h in (holdings or [])]}

    from services.fundclear_backfill import rank_candidates
    _funds = (frame[["fund_code", "name"]].dropna().drop_duplicates()
              .rename(columns={"fund_code": "value"}).to_dict("records"))

    points: list = []
    matched: list = []
    unmatched: list = []
    for _h in (holdings or []):
        _hc = str(_h.get("code") or "").strip().upper()
        _hn = str(_h.get("name") or "").strip()
        if not _hc or not _hn:
            unmatched.append(_hc or "?")
            continue
        _ranked = rank_candidates(_hn, _funds, top=1)
        if not _ranked or float(_ranked[0].get("score") or 0) < min_score:
            unmatched.append(_hc)
            continue
        _fc = _ranked[0]["value"]
        _rows = frame[frame["fund_code"] == _fc]
        for _r in _rows.itertuples(index=False):
            points.append({
                "code": _hc, "nav": float(_r.nav),
                "nav_date": pd.Timestamp(_r.nav_date).strftime("%Y-%m-%d"),
                "fund_name": _hn, "source": "tdcc_opendata_11641",
            })
        matched.append({"code": _hc, "matched_name": _ranked[0]["name"],
                        "score": _ranked[0]["score"], "n": int(len(_rows))})
    return points, {"matched": matched, "unmatched": unmatched}


def accumulate_and_store(holdings: list, min_score: float = _MIN_SCORE) -> dict:
    """抓 11641 → 對持倉 → 寫 GS nav_history。回 {ok, written, skipped, report, n_points}。

    §1:抓不到 → ok=False。對不到的持倉列在 report.unmatched(不亂存)。
    """
    from repositories.tdcc_nav_opendata import fetch_offshore_nav_recent
    _frame = fetch_offshore_nav_recent()
    if _frame is None or len(_frame) == 0:
        return {"ok": False, "reason": "11641 抓不到資料(data.gov.tw 不可達或空)",
                "report": {"matched": [], "unmatched": [str(h.get("code") or "?") for h in (holdings or [])]}}
    _points, _report = accumulate_points(holdings, _frame, min_score)
    if not _points:
        return {"ok": True, "written": 0, "skipped": 0, "n_points": 0, "report": _report}
    from services.nav_history_gs import append_points
    _res = append_points(_points)
    return {"ok": True, "written": _res.get("written"), "skipped": _res.get("skipped"),
            "n_points": len(_points), "report": _report}


__all__ = ["accumulate_points", "accumulate_and_store"]
