"""ui/helpers/fund_grp_health/quality.py — 同類相對品質分 by_code(v19.496,A1)。

user 2026-08-20 核准 A1:6 因子在**小 universe(本組 funds)**排名 + **MoneyDJ 整體同類分位當
「報酬」大母體錨定**(可得則用大母體、缺則退小 universe 報酬 rank)+ 誠實標樣本數。

因子 → 百分位(0=最佳 ~ 1=最差,統一方向後餵 L2 `services.quality_score`):
  報酬  : MoneyDJ 同類分位(大母體;peer_percentile)>  小 universe 3Y/1Y 報酬 rank
  Sharpe: metrics.sharpe                    小 universe rank(高=最佳)
  下檔  : metrics.std_*(年化σ)             小 universe rank(**低=最佳 → 取負值再排**)
  操盤  : capture 操盤評分                  小 universe rank(高=最佳)
  配息  : coverage = 1Y含息 ÷ 年化配息率(截[0,2])  小 universe rank(高=最佳)
  成本  : 費用率                            小 universe rank(**低=最佳**;reuse expense_rank 升序)

§1:因子缺 → 退出分母(L2 處理),不填 0;同一指標小樣本由 quartile_rank 誠實回 None。
§8.2 L3 helper:讀 fund dict + 呼 L2 純函式,不新抓網路(操盤走已算好的 capture_map)。
"""
from __future__ import annotations

from typing import Optional


def _mval(f: dict, *keys) -> Optional[float]:
    """從 fund.metrics 依序取第一個有效數值(排除 bool);全缺 → None。"""
    m = (f or {}).get("metrics") or {}
    for k in keys:
        v = m.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
    return None


def _pct_from_rank(rank_i: Optional[int], n: int) -> Optional[float]:
    """名次(1=最佳)+ 樣本數 → percentile 0最佳~1最差;n<2 / 缺 → None。"""
    if rank_i is None or n is None or n < 2:
        return None
    return round((rank_i - 1) / (n - 1), 4)


def _assemble_factor_pcts(funds: list, capture_map: Optional[dict]) -> "tuple[dict, int]":
    """funds → ({code: {因子名: percentile 0最佳~1最差 | None}}, 本組檔數)。共用給 by_code / detail。"""
    from services.peer_rank import quartile_rank
    from services.portfolio_service import rank_funds_within_portfolio

    _cap = capture_map or {}
    try:
        _pr = rank_funds_within_portfolio(funds)
    except Exception:  # noqa: BLE001 — 排名不可用不阻斷,退各因子小 universe rank
        _pr = {}

    _sharpe: dict = {}
    _downside: dict = {}
    _skill: dict = {}
    _cover: dict = {}
    for f in funds:
        c = str(f["code"])
        s = _mval(f, "sharpe")
        if s is not None:
            _sharpe[c] = s
        sig = _mval(f, "std_1y", "std_2y", "std_3y", "std_5y")
        if sig is not None and sig > 0:
            _downside[c] = -sig
        _sk = (_cap.get(c) or {}).get("操盤評分")
        if isinstance(_sk, (int, float)) and not isinstance(_sk, bool):
            _skill[c] = float(_sk)
        _tr = _mval(f, "ret_1y_total")
        _adr = _mval(f, "annual_div_rate")
        if _tr is not None and _adr is not None and _adr > 0:
            _cover[c] = max(0.0, min(_tr / _adr, 2.0))

    def _pct_small(code, vmap):
        return quartile_rank(code, vmap).get("percentile")

    out: dict = {}
    for f in funds:
        c = str(f["code"])
        _p = _pr.get(c) or {}
        _pp = _p.get("peer_percentile")
        if isinstance(_pp, (int, float)) and not isinstance(_pp, bool):
            _ret_pct = round((100.0 - float(_pp)) / 100.0, 4)
        else:
            _ret_pct = _pct_from_rank(_p.get("return_rank"), _p.get("return_n") or 0)
        out[c] = {
            "報酬": _ret_pct,
            "Sharpe": _pct_small(c, _sharpe),
            "下檔": _pct_small(c, _downside),
            "操盤": _pct_small(c, _skill),
            "配息": _pct_small(c, _cover),
            "成本": _pct_from_rank(_p.get("expense_rank"), _p.get("expense_n") or 0),
        }
    return out, len(funds)


def quality_detail_for_code(code, funds: list,
                            capture_map: Optional[dict] = None) -> Optional[dict]:
    """單一 code 的完整品質分結果(供單一基金頁的貢獻分解)。

    回 compute_quality_score 的 dict(score / contributions / coverage_pct / note)+ n_group;
    code 不在 funds → None。
    """
    from services.quality_score import compute_quality_score

    funds = [f for f in (funds or []) if (f or {}).get("code")]
    _c = str(code or "").strip()
    if not _c or _c not in {str(f["code"]) for f in funds}:
        return None
    pcts, n_group = _assemble_factor_pcts(funds, capture_map)
    res = compute_quality_score(pcts.get(_c, {}))
    res["n_group"] = n_group
    return res


def quality_score_by_code(funds: list, capture_map: Optional[dict] = None) -> dict:
    """{code: {"相對品質分": label}} —— A1 同類相對品質分。

    label:「78 · 本組 12 檔」/「⬜ 資料不足」;⚠️ 小樣本(本組<4)加註「僅參考」。
    capture_map:build_merged_extra_columns 已算好的 capture_by_code 產物(取「操盤評分」);
      None → 操盤因子退出分母(§1 不重算、不新抓)。
    """
    from services.peer_rank import PEER_QUARTILE_MIN_N
    from services.quality_score import compute_quality_score

    funds = [f for f in (funds or []) if (f or {}).get("code")]
    if not funds:
        return {}

    pcts, n_group = _assemble_factor_pcts(funds, capture_map)
    _small_sample = n_group < PEER_QUARTILE_MIN_N

    out: dict = {}
    for f in funds:
        c = str(f["code"])
        _score = compute_quality_score(pcts.get(c, {}))["score"]
        if _score is None:
            out[c] = {"相對品質分": "⬜ 資料不足"}
        else:
            _tail = "・僅參考" if _small_sample else ""
            out[c] = {"相對品質分": f"{_score:.0f} · 本組 {n_group} 檔{_tail}"}
    return out


__all__ = ["quality_score_by_code", "quality_detail_for_code"]
