"""services/portfolio_csv.py — 保單持倉總表 CSV 解析 + 保單組合分析(v19.445)。L2 純函式,零 IO。

user 上傳的「保單總表」CSV(比 Google Sheet 政策表乾淨、且帶成本基礎):
  保單號碼,基金代碼,基金名稱,幣別,級別,持有單位數,平均成本淨值,平均含息成本,平均匯率,
  投資金額(TWD),現金給付%,(每單位配息),累積已領配息(TWD)

本層:(1) 解析成 holdings、(2) 依保單彙總、(3) 用「現抓的現價 + 現匯」算真實報酬(含息)。
網路資料(現價/現匯/大盤)由 L3 抓好注入 —— 本層純計算,可測。§1:缺料顯式回 None,不猜。
"""
from __future__ import annotations

import csv as _csv
import io as _io
from typing import Any

# 表頭關鍵字 → 欄位(容忍順序 / 別名)
_COLKEYS = {
    "policy": ("保單",),
    "code": ("基金代碼", "代碼", "code"),
    "name": ("基金名稱", "名稱", "name"),
    "currency": ("幣別", "幣", "currency"),
    "tier": ("級別", "tier"),
    "units": ("持有單位", "單位數", "units"),
    "cost_nav": ("平均成本淨值",),
    "cost_incl_div": ("平均含息成本",),
    "fx": ("平均匯率", "匯率"),
    "invest_twd": ("投資金額",),
    "cash_pct": ("現金給付",),
    "cum_div_twd": ("累積已領配息", "累積配息", "已領配息"),
}
# 幣別 → 現匯 key(現匯由 caller 注入 {"美元": usdtwd, "台幣": 1.0})
_TWD_CCY = ("台幣", "twd", "ntd", "nt$")


def _f(x: Any) -> "float | None":
    """容忍 #N/A / 空 / 千分位 → float 或 None(§1 不硬填 0)。"""
    s = str(x if x is not None else "").strip().replace(",", "")
    if not s or s.upper() in ("#N/A", "N/A", "NA", "-", "—"):
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _match_cols(header: list) -> dict:
    """表頭 → {欄位: index}。找不到的欄位不在 dict(caller 用 .get 容錯)。"""
    hl = [str(h or "").strip().lower() for h in header]
    out: dict = {}
    for field, keys in _COLKEYS.items():
        for i, h in enumerate(hl):
            if any(k.lower() in h for k in keys):
                out[field] = i
                break
    return out


def parse_holdings(csv_text: str) -> list:
    """CSV 文字 → holdings list。每列一檔持倉。

    Returns [{policy, code, name, currency, tier, units, cost_nav, cost_incl_div,
              fx, invest_twd, cash_pct, cum_div_twd}]  (缺值 → None;policy/code 缺 → 丟該列)
    """
    rows = list(_csv.reader(_io.StringIO(csv_text or "")))
    if not rows:
        return []
    cols = _match_cols(rows[0])
    if "policy" not in cols or "code" not in cols:
        return []                                    # 表頭認不出 → 空(§1 不亂猜欄位)

    def _cell(r, field):
        i = cols.get(field)
        return r[i] if (i is not None and i < len(r)) else None

    out: list = []
    for r in rows[1:]:
        if not any(str(c).strip() for c in r):
            continue
        policy = str(_cell(r, "policy") or "").strip()
        code = str(_cell(r, "code") or "").strip().upper()
        if not policy or not code:
            continue
        out.append({
            "policy": policy, "code": code,
            "name": str(_cell(r, "name") or code).strip(),
            "currency": str(_cell(r, "currency") or "").strip(),
            "tier": str(_cell(r, "tier") or "").strip(),
            "units": _f(_cell(r, "units")),
            "cost_nav": _f(_cell(r, "cost_nav")),
            "cost_incl_div": _f(_cell(r, "cost_incl_div")),
            "fx": _f(_cell(r, "fx")),
            "invest_twd": _f(_cell(r, "invest_twd")),
            "cash_pct": _f(_cell(r, "cash_pct")),
            "cum_div_twd": _f(_cell(r, "cum_div_twd")),
        })
    return out


def summarize_by_policy(holdings: list) -> list:
    """依保單彙總:投資額 / 核心·衛星 / 累領配息 / 檔數。純加總,無現價需求。

    Returns [{policy, invest_twd, core_twd, satellite_twd, core_pct, cum_div_twd,
              n_funds, codes}]  依投資額降冪。
    """
    agg: dict = {}
    for h in holdings:
        p = h["policy"]
        d = agg.setdefault(p, {"policy": p, "invest_twd": 0.0, "core_twd": 0.0,
                               "satellite_twd": 0.0, "cum_div_twd": 0.0, "codes": []})
        inv = h.get("invest_twd") or 0.0
        d["invest_twd"] += inv
        if "核心" in (h.get("tier") or "") or "core" in (h.get("tier") or "").lower():
            d["core_twd"] += inv
        elif "衛星" in (h.get("tier") or "") or "satellite" in (h.get("tier") or "").lower():
            d["satellite_twd"] += inv
        d["cum_div_twd"] += h.get("cum_div_twd") or 0.0
        d["codes"].append(h["code"])
    out = list(agg.values())
    for d in out:
        d["n_funds"] = len(d["codes"])
        d["core_pct"] = (d["core_twd"] / d["invest_twd"] * 100) if d["invest_twd"] else None
    out.sort(key=lambda x: -x["invest_twd"])
    return out


def _is_twd(ccy: str) -> bool:
    return any(k in str(ccy or "").lower() for k in _TWD_CCY)


def enrich_returns(holdings: list, *, nav_by_code: dict, usdtwd: "float | None") -> list:
    """為每檔算真實報酬(含息,TWD)。現價/現匯由 caller 注入。

    現值_TWD = 單位 × 現在淨值(原幣) × 現匯;台幣 fx=1、美元 fx=usdtwd。
    總報酬_TWD = 現值 + 累積已領配息 − 投資額;報酬% = 總報酬 ÷ 投資額。
    缺現價 / 缺單位 / 缺成本 → current_value_twd/total_return_* = None(§1 不猜)。
    """
    out: list = []
    for h in holdings:
        code = h["code"]
        nav = nav_by_code.get(code)
        units = h.get("units")
        inv = h.get("invest_twd")
        fx = 1.0 if _is_twd(h.get("currency")) else usdtwd
        cur_val = None
        if isinstance(nav, (int, float)) and nav > 0 and isinstance(units, (int, float)) \
                and isinstance(fx, (int, float)) and fx > 0:
            cur_val = units * float(nav) * float(fx)
        tr_twd = tr_pct = None
        if cur_val is not None and isinstance(inv, (int, float)) and inv > 0:
            tr_twd = cur_val + (h.get("cum_div_twd") or 0.0) - inv
            tr_pct = tr_twd / inv * 100.0
        out.append({**h, "current_nav": nav, "current_fx": fx,
                    "current_value_twd": cur_val,
                    "total_return_twd": tr_twd, "total_return_pct": tr_pct})
    return out


def policy_returns(enriched: list) -> list:
    """依保單彙總真實報酬 + 排名(最差在前)。缺現價的檔不計入該保單分母(誠實,標 covered)。

    Returns [{policy, invest_twd, current_value_twd, cum_div_twd, total_return_twd,
              total_return_pct, n_funds, n_priced, rank}]  依報酬%升冪(最差 rank=1)。
    covered = 有現價的檔;若保單全無現價 → total_return_pct=None(不排名)。
    """
    agg: dict = {}
    for h in enriched:
        p = h["policy"]
        d = agg.setdefault(p, {"policy": p, "invest_twd": 0.0, "cum_div_twd": 0.0,
                               "priced_invest": 0.0, "priced_value": 0.0,
                               "n_funds": 0, "n_priced": 0})
        d["invest_twd"] += h.get("invest_twd") or 0.0
        d["cum_div_twd"] += h.get("cum_div_twd") or 0.0
        d["n_funds"] += 1
        if h.get("current_value_twd") is not None and (h.get("invest_twd") or 0) > 0:
            d["priced_invest"] += h["invest_twd"]
            d["priced_value"] += h["current_value_twd"]
            d["n_priced"] += 1
    out: list = []
    for d in agg.values():
        # 報酬用「有現價的部分」當分母(§1:沒現價的不硬算)
        cur = d["priced_value"] if d["n_priced"] else None
        tr_twd = tr_pct = None
        if cur is not None and d["priced_invest"] > 0:
            # 已領配息按有現價占比分攤,避免用全部配息除部分成本高估
            _div = d["cum_div_twd"] * (d["priced_invest"] / d["invest_twd"]) if d["invest_twd"] else 0.0
            tr_twd = cur + _div - d["priced_invest"]
            tr_pct = tr_twd / d["priced_invest"] * 100.0
        out.append({"policy": d["policy"], "invest_twd": d["invest_twd"],
                    "current_value_twd": cur, "cum_div_twd": d["cum_div_twd"],
                    "total_return_twd": tr_twd, "total_return_pct": tr_pct,
                    "n_funds": d["n_funds"], "n_priced": d["n_priced"]})
    # 排名:有報酬%的升冪(最差在前),None 殿後
    _ranked = sorted([o for o in out if o["total_return_pct"] is not None],
                     key=lambda x: x["total_return_pct"])
    for i, o in enumerate(_ranked):
        o["rank"] = i + 1
    for o in out:
        o.setdefault("rank", None)
    out.sort(key=lambda x: (x["rank"] is None, x.get("rank") or 0))
    return out


__all__ = ["parse_holdings", "summarize_by_policy", "enrich_returns", "policy_returns"]
