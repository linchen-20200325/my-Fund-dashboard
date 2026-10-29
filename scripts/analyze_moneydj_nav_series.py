#!/usr/bin/env python3
"""scripts/analyze_moneydj_nav_series.py — MoneyDJ NAV 多日 probe 的跨 run 分析（離線、唯讀、不連網）。

輸入：`probe/moneydj-nav-results` 分支的 checkout 路徑（遞迴找 `results/*/report.json.gz`，或直接給 `*.json.gz`）。
輸出：Markdown（stdout）；`--json` 改輸出結構化 JSON。

## 規則（客戶 2026-10-29 最終整合裁示第 8、17 節）
* **數的是「不同 NAV 日」，不是 run 次數**：休市日／同日重跑會重複同一個 NAV 日，只算一次。
* 每個 run 每個輸入只取「最新一筆 NAV（nav_date, nav）」入矩陣；不用頁面 `recent` 歷史回填（否則 1 個 run 就湊滿 3 日，違背「累積 3～5 個交易日」）。
* 逐 run 的觀察性裁定／ACDD01 baseline／EQTAL005 product mapping，一律由報告內的 `observations` 以 probe 腳本的同一組純函式**重算**
  （v1.0 舊報告也能分析；單一邏輯，不在此另寫第二套）。
* 最終分類 `classification` ∈ {insufficient_days, strong_observational_evidence_same_series, conflict_found, blocked}：
  - `blocked`：沒有任何 run 取得可解析的 NAV；
  - `conflict_found`：任一 run 的觀察性裁定為 conflict，或任一 NAV 日上輸入間 NAV／基金名稱不一致（優先於下兩者）；
  - `strong_observational_evidence_same_series`：三輸入 NAV 日、NAV 值、基金名稱全一致的**不同 NAV 日 ≥ 3**，且無 conflict；
  - `insufficient_days`：其餘（含 <3 個一致日）。
* **永不輸出 strictly comparable；不推定平台頁幣別**（`currency_evidence` 兩欄原樣帶出，不合併）。
"""
from __future__ import annotations

import argparse
import gzip
import importlib
import json
import math
import sys
import zlib
from pathlib import Path
from urllib.parse import urlparse

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

P = importlib.import_module("probe_moneydj_nav_equivalence")

MIN_DISTINCT_CONSISTENT_DATES = 3
MAX_DECOMPRESSED_BYTES = 40 * 1024 * 1024
INPUTS = P.FAMILIES["TLZF9"]          # (base, AL001, 24A7)
CLS_INSUFFICIENT = "insufficient_days"
CLS_STRONG = "strong_observational_evidence_same_series"
CLS_CONFLICT = "conflict_found"
CLS_BLOCKED = "blocked"


def load_reports(path) -> tuple[list, list]:
    """回傳 (reports, skipped)。只收 `script_version` 以 `moneydj_nav_equivalence` 開頭者；壞檔略過並記錄。"""
    p = Path(path)
    files = [p] if p.is_file() else sorted(p.rglob("*.json.gz"))
    reports, skipped = [], []
    for f in files:
        try:
            with gzip.open(f, "rb") as fh:
                raw = fh.read(MAX_DECOMPRESSED_BYTES + 1)
            if len(raw) > MAX_DECOMPRESSED_BYTES:
                skipped.append(f"{f.name}:too_large")
                continue
            rep = json.loads(raw.decode("utf-8"))
        except (OSError, EOFError, zlib.error, ValueError) as e:
            skipped.append(f"{f.parent.name}/{f.name}:{type(e).__name__}")
            continue
        if not isinstance(rep, dict) or not str(rep.get("script_version", "")).startswith("moneydj_nav_equivalence"):
            skipped.append(f"{f.parent.name}/{f.name}:not_moneydj_nav_report")
            continue
        rep["_stamp"] = f.parent.name
        reports.append(rep)
    reports.sort(key=lambda r: (str(r.get("generated_at_utc") or ""), r["_stamp"]))
    return reports, skipped


def _host(url) -> str:
    try:
        return urlparse(str(url)).hostname or "?"
    except ValueError:
        return "?"


def _same_nav(a, b) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)


def _latest_points(rep: dict) -> list:
    """每個輸入、每個（kind, transport）只取最新一筆 ok NAV → [{input, date, nav, name, host, kind, transport}]。
    base 輸入只收 prod 頁；帶後綴輸入只收 platform_* 頁（prod 頁可能只是回傳 base 頁，不算佐證）。"""
    out = []
    for o in rep.get("observations") or []:
        if not isinstance(o, dict) or not P._ok_nav(o) or o.get("input") not in INPUTS:
            continue
        kind = str(o.get("kind"))
        base_role = o["input"] == INPUTS[0]
        if base_role != kind.startswith("prod_nav30"):
            continue
        out.append({"input": o["input"], "date": o["nav_date"], "nav": o["nav"], "name": o.get("fund_name"),
                    "host": _host(o.get("url")), "kind": kind, "transport": o.get("transport")})
    return out


def analyze(reports: list) -> dict:
    runs, by_date = [], {}
    any_nav = False
    for rep in reports:
        obs = [o for o in rep.get("observations") or [] if isinstance(o, dict)]
        blocked = all(v.get("blocked") or rep.get("transports", {}).get(t) != "enabled"
                      for t, v in (rep.get("network_blocked") or {}).items()) if rep.get("network_blocked") else False
        pts = _latest_points(rep)
        any_nav = any_nav or bool(pts)
        for pt in pts:
            by_date.setdefault(pt["date"], {}).setdefault(pt["input"], []).append({**pt, "run": rep["_stamp"]})
        obsv = P.observational_assessment(obs, INPUTS) if pts else {"verdict": "blocked" if blocked else P.V_OBS_INCOMPLETE,
                                                                     "currency_evidence": None}
        runs.append({"run": rep["_stamp"], "generated_at_utc": rep.get("generated_at_utc"),
                     "executed_sha": rep.get("executed_sha"), "observational": obsv["verdict"],
                     "differences": obsv.get("differences", []), "currency_evidence": obsv.get("currency_evidence"),
                     "baseline_ACDD01": P.baseline_assessment(obs, blocked=blocked)["verdict"],
                     "product_mapping_status": P.product_mapping_section(obs)["status"]})
    matrix, conflicts, consistent_dates = [], [], []
    for d in sorted(by_date):
        cells, navs, names = {}, [], set()
        for inp in INPUTS:
            es = by_date[d].get(inp, [])
            cells[inp] = [{"nav": e["nav"], "name": e["name"], "host": e["host"], "kind": e["kind"], "run": e["run"]} for e in es]
            navs += [e["nav"] for e in es]
            names |= {str(e["name"]).strip() for e in es if e["name"]}
        missing = [i for i in INPUTS if not cells[i]]
        nav_conflict = bool(navs) and any(not _same_nav(navs[0], x) for x in navs[1:])
        name_conflict = len(names) > 1
        if nav_conflict or name_conflict:
            status = "conflict"
            conflicts.append({"nav_date": d, "nav_conflict": nav_conflict, "name_conflict": name_conflict,
                              "navs": sorted(set(navs)), "names": sorted(names)})
        elif missing:
            status = "partial"
        else:
            status = "all_three_equal"
            consistent_dates.append(d)
        matrix.append({"nav_date": d, "status": status, "missing_inputs": missing, "cells": cells})
    run_conflicts = [r["run"] for r in runs if r["observational"] == P.V_OBS_CONFLICT]
    if not any_nav:
        cls = CLS_BLOCKED
    elif conflicts or run_conflicts:
        cls = CLS_CONFLICT
    elif len(consistent_dates) >= MIN_DISTINCT_CONSISTENT_DATES:
        cls = CLS_STRONG
    else:
        cls = CLS_INSUFFICIENT
    mapping = "OBSERVED_ON_PAGE" if any(r["product_mapping_status"] == "OBSERVED_ON_PAGE" for r in runs) else "UNVERIFIED"
    return {"runs_count": len(runs), "distinct_nav_dates": len(by_date),
            "distinct_consistent_nav_dates": len(consistent_dates), "consistent_dates": consistent_dates,
            "min_required_dates": MIN_DISTINCT_CONSISTENT_DATES, "date_matrix": matrix, "date_conflicts": conflicts,
            "run_level_conflicts": run_conflicts, "runs": runs,
            "acdd01_baseline_per_run": {r["run"]: r["baseline_ACDD01"] for r in runs},
            "eqtal005_mapping_status": mapping, "classification": cls,
            "note": "數不同 NAV 日而非 run 次數；不推定平台頁幣別；永不輸出 strictly comparable"}


def render_markdown(res: dict, skipped: list) -> str:
    L = ["# MoneyDJ NAV 多日 probe 分析", "",
         f"- runs：{res['runs_count']}；不同 NAV 日：{res['distinct_nav_dates']}；"
         f"三輸入一致的不同 NAV 日：**{res['distinct_consistent_nav_dates']}**（門檻 {res['min_required_dates']}）",
         f"- **classification：`{res['classification']}`**",
         f"- EQTAL005 → ACDD01 mapping：`{res['eqtal005_mapping_status']}`（來源＝客戶確認；預設 UNVERIFIED）"]
    if skipped:
        L.append(f"- 略過的檔：{skipped}")
    L += ["", "## NAV 日矩陣（儲存格＝NAV｜基金名稱｜來源 host）", "",
          "| NAV 日 | 狀態 | " + " | ".join(INPUTS) + " |", "|---|---|" + "---|" * len(INPUTS)]
    for row in res["date_matrix"]:
        cells = []
        for inp in INPUTS:
            es = row["cells"][inp]
            cells.append("<br>".join(sorted({f"{e['nav']}｜{e['name'] or '—'}｜{e['host']}" for e in es})) or "—")
        L.append(f"| {row['nav_date']} | {row['status']} | " + " | ".join(cells) + " |")
    L += ["", "## 逐 run", "", "| run | 觀察性裁定 | ACDD01 baseline | 差異 | currency_evidence（兩欄分開，不合併） |", "|---|---|---|---|---|"]
    for r in res["runs"]:
        L.append(f"| {r['run']} | {r['observational']} | {r['baseline_ACDD01']} | {r['differences'] or '—'} | {r['currency_evidence']} |")
    if res["date_conflicts"] or res["run_level_conflicts"]:
        L += ["", "## Conflicts", f"- NAV 日層級：{res['date_conflicts']}", f"- run 層級：{res['run_level_conflicts']}"]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("path", help="probe/moneydj-nav-results 分支 checkout 路徑（含 results/*/report.json.gz）")
    ap.add_argument("--json", action="store_true", help="輸出 JSON 而非 Markdown")
    args = ap.parse_args(argv)
    reports, skipped = load_reports(args.path)
    res = analyze(reports)
    print(json.dumps(res, ensure_ascii=False, indent=1) if args.json else render_markdown(res, skipped), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
