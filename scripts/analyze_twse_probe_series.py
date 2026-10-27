#!/usr/bin/env python3
"""scripts/analyze_twse_probe_series.py — BL-0509 多日 probe 的跨 run 分析（離線、純標準庫、唯讀）。

輸入：一個或多個目錄／檔案；目錄會遞迴找 `*.json.gz`（例：`probe/twse-eps-results` 分支 checkout 後的 `results/`，
或 `docs/evidence/probe_twse_eps/`），只收 `probe == "twse_eps"` 的報告，依 `generated_at_utc` 排序。
輸出：Markdown（stdout；`--out` 另存一份）。

## 它做什麼／不做什麼
* 只彙整報告裡**已有**的欄位；**不補 0、不補值、不推測缺的資料**。樣本不足一律明寫「樣本不足」。
* 時序欄位（`timeseries`、`openapi_vs_rwd`、`terms_research`）只有 `schema_version >= 2` 的報告才有；
  v1 報告只能用 `freshness`／`schema` 的子集，缺的欄位顯示 `—`（不補）。
* **不下結論性裁示**：「疑似 revision」只是 sha 不同的觀察，可能是別的原因（見輸出內的說明）；
  發布延遲是「首次被觀察到」的**上界**（解析度＝兩次 run 的間隔）；授權恆標「⬜ 授權條款尚未完成驗證」。
* 「台北日」以報告的 `run_date_taipei` 為準；**不是**交易日曆（本腳本不知道哪天休市）。
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

TZ_TAIPEI = timezone(timedelta(hours=8))
MIN_RUNS_FOR_CHANGE = 2          # 判斷「有沒有變」至少要幾份報告
MIN_DISTINCT_DATES_FOR_LAG = 2   # 推發布延遲至少要觀察到幾個不同的來源日期
MIN_RUN_DATES_FOR_FREQUENCY = 3  # 談更新頻率至少要幾個不同的台北日
PE_FIELD_MARKERS = ("PE", "本益比")
LICENSE_UNVERIFIED = "⬜ 授權條款尚未完成驗證"
INSUFFICIENT = "樣本不足"


# ───────────────────────── 載入 ─────────────────────────

def _parse_dt(raw):
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_date(raw):
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def load_reports(paths) -> tuple:
    """回傳 (reports, skipped)；reports 依 generated_at_utc 排序，每份附 `_source`、`_dt_utc`。"""
    files = []
    for p in paths:
        pp = Path(p)
        if pp.is_dir():
            files += sorted(pp.rglob("*.json.gz"))
        elif pp.is_file():
            files.append(pp)
    reports, skipped = [], []
    for f in files:
        try:
            with gzip.open(f, "rb") as fh:
                rep = json.loads(fh.read().decode("utf-8"))
        except (OSError, ValueError) as e:
            skipped.append((str(f), f"{type(e).__name__}"))
            continue
        if not isinstance(rep, dict) or rep.get("probe") != "twse_eps":
            skipped.append((str(f), "not a twse_eps probe report"))
            continue
        dt = _parse_dt(rep.get("generated_at_utc"))
        if dt is None:
            skipped.append((str(f), "no parseable generated_at_utc"))
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        rep["_source"] = str(f)
        rep["_dt_utc"] = dt
        reports.append(rep)
    reports.sort(key=lambda r: r["_dt_utc"])
    return reports, skipped


# ───────────────────────── 單端點檢視（正規化 v1／v2） ─────────────────────────

def _rows_v1(res):
    sc = res.get("schema") or {}
    if sc.get("top_level") == "list":
        return sc.get("n_rows")
    d = sc.get("data")
    return d.get("n_rows") if isinstance(d, dict) else None


def ep_view(report, ep_id, transport) -> dict | None:
    for e in report.get("endpoints", []):
        if e.get("id") != ep_id:
            continue
        res = (e.get("transports") or {}).get(transport)
        if res is None:
            return None
        ts = res.get("timeseries") or {}
        fr = res.get("freshness") or {}
        latest = _parse_date(ts.get("latest_source_date") or fr.get("latest_source_date"))
        n_cells = ts.get("n_cells")
        missing = None
        if n_cells:
            missing = (ts.get("empty_string_cells", 0) + ts.get("dash_cells", 0) + ts.get("null_cells", 0))
        return {
            "group": e.get("group"),
            "outcome": res.get("outcome"),
            "sha": res.get("body_sha256"),
            "schema_hash": ts.get("schema_hash"),
            "rows": ts.get("row_count") if ts else _rows_v1(res),
            "latest": latest,
            "top_level_date_raw": ts.get("top_level_date_raw"),
            "n_cells": n_cells,
            "missing_cells": missing,
            "missing_by_field": ts.get("missing_by_field") or {},
            "has_ts": bool(ts),
        }
    return None


def run_label(report) -> str:
    dt = report["_dt_utc"].astimezone(TZ_TAIPEI)
    return dt.strftime("%m-%d %H:%M")


def run_taipei_date(report):
    return _parse_date(report.get("run_date_taipei")) or report["_dt_utc"].astimezone(TZ_TAIPEI).date()


def _short(h, n=8):
    return h[:n] if h else "—"


def _md_table(headers, rows) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join("—" if c is None else str(c) for c in r) + " |")
    return "\n".join(out)


def _endpoint_ids(reports):
    seen, order = set(), []
    for r in reports:
        for e in r.get("endpoints", []):
            if e["id"] not in seen:
                seen.add(e["id"])
                order.append(e["id"])
    return order


# ───────────────────────── 各分析區塊 ─────────────────────────

def section_overview(reports, skipped, transport) -> str:
    dates = sorted({run_taipei_date(r) for r in reports})
    lines = ["## 1. 樣本概況", ""]
    lines.append(f"- 報告份數：**{len(reports)}**；不同台北日：**{len(dates)}**"
                 + (f"（{dates[0]} ～ {dates[-1]}）" if dates else ""))
    lines.append(f"- 分析路徑（transport）：`{transport}`")
    lines.append("- 台北日以報告 `run_date_taipei` 為準，**不是交易日曆**（本腳本不知道哪天休市）。")
    if reports:
        lines.append("- 各 run（台北時間）：" + "、".join(f"{run_label(r)}" for r in reports))
        v1 = sum(1 for r in reports if int(r.get("schema_version") or 1) < 2)
        if v1:
            lines.append(f"- ⚠️ 其中 {v1} 份為 schema_version 1，無 `timeseries`／`openapi_vs_rwd`／`terms_research`，對應欄位顯示 `—`（不補）。")
    if len(reports) < MIN_RUNS_FOR_CHANGE:
        lines.append(f"- **{INSUFFICIENT}**：只有 {len(reports)} 份報告，以下「是否變化」「推進」「修正」各節皆無法判定，只列單點觀察。")
    if len(dates) < MIN_RUN_DATES_FOR_FREQUENCY:
        lines.append(f"- 更新頻率：**{INSUFFICIENT}**（不同台北日 {len(dates)} < {MIN_RUN_DATES_FOR_FREQUENCY}）。")
    for src, why in skipped:
        lines.append(f"- 略過 `{src}`：{why}")
    return "\n".join(lines)


def section_changes(reports, transport) -> str:
    lines = ["## 2. 各端點跨 run 變化（sha／schema_hash／列數）", ""]
    if len(reports) < MIN_RUNS_FOR_CHANGE:
        lines.append(f"**{INSUFFICIENT}**（需要至少 {MIN_RUNS_FOR_CHANGE} 份報告）。單點觀察：")
        lines.append("")
    rows = []
    for ep in _endpoint_ids(reports):
        views = [ep_view(r, ep, transport) for r in reports]
        ok = [v for v in views if v and v.get("sha")]
        shas = [v["sha"] for v in ok]
        hashes = [v["schema_hash"] for v in ok if v["schema_hash"]]
        rowc = [v["rows"] for v in ok if v["rows"] is not None]
        if len(reports) < MIN_RUNS_FOR_CHANGE:
            rows.append([ep, ok[0]["outcome"] if ok else (views[0] or {}).get("outcome"), _short(shas[0]) if shas else "—",
                         _short(hashes[0]) if hashes else "—", rowc[0] if rowc else "—", INSUFFICIENT])
            continue
        if len(ok) < MIN_RUNS_FOR_CHANGE:
            rows.append([ep, "—", "—", "—", "—", f"{INSUFFICIENT}（有本文的 run 只有 {len(ok)} 份）"])
            continue
        sha_chg = sum(1 for a, b in zip(shas, shas[1:]) if a != b)
        sch = (f"{'變' if len(set(hashes)) > 1 else '不變'}（{len(set(hashes))} 種）" if len(hashes) >= MIN_RUNS_FOR_CHANGE
               else INSUFFICIENT)
        rc = (f"{min(rowc)}～{max(rowc)}（{'變' if min(rowc) != max(rowc) else '不變'}）" if rowc else "—")
        rows.append([ep, f"{len(ok)}/{len(reports)} 份有本文", f"相鄰 run sha 變 {sha_chg}/{len(shas) - 1} 次", sch, rc, ""])
    heads = (["端點", "outcome／有本文", "sha", "schema_hash", "列數", "備註"])
    if len(reports) < MIN_RUNS_FOR_CHANGE:
        heads = ["端點", "outcome", "sha[:8]", "schema_hash[:8]", "列數", "備註"]
    lines.append(_md_table(heads, rows))
    lines.append("")
    lines.append("說明：sha 不同＝回應位元組不同（可能因來源日期推進、列數變動、欄位重排、或值被修正），**本表不區分原因**。")
    return "\n".join(lines)


def section_latest_date_progress(reports, transport) -> str:
    lines = ["## 3. latest_source_date 隨 run 時間的推進與發布延遲", ""]
    lines.append("lag_days＝`run_date_taipei` − `latest_source_date`（日曆日）。財報群組的日期是『出表日期』（發布日），不是財報期間。")
    lines.append("")
    for ep in _endpoint_ids(reports):
        views = [(r, ep_view(r, ep, transport)) for r in reports]
        if not any(v and v["latest"] for _r, v in views):
            continue
        rows = [[run_label(r), v["latest"].isoformat() if v and v["latest"] else "—",
                 (run_taipei_date(r) - v["latest"]).days if v and v["latest"] else "—"] for r, v in views]
        lines.append(f"### {ep}")
        lines.append(_md_table(["run（台北）", "latest_source_date", "lag_days"], rows))
        dates = sorted({v["latest"] for _r, v in views if v and v["latest"]})
        if len(dates) < MIN_DISTINCT_DATES_FOR_LAG:
            lines.append(f"- 發布延遲（首次出現時點）：**{INSUFFICIENT}**（只觀察到 {len(dates)} 個不同來源日期，需 ≥ {MIN_DISTINCT_DATES_FOR_LAG}）。")
        else:
            first = {}
            for r, v in views:
                if v and v["latest"] and v["latest"] not in first:
                    first[v["latest"]] = r["_dt_utc"].astimezone(TZ_TAIPEI)
            frows = []
            for d in dates:
                t = first[d]
                mid = datetime(d.year, d.month, d.day, tzinfo=TZ_TAIPEI)
                frows.append([d.isoformat(), t.strftime("%m-%d %H:%M"), f"{(t - mid).total_seconds() / 3600:.1f}"])
            lines.append(_md_table(["來源日期", "首次被觀察到（台北）", "距該日 00:00 的小時數（上界）"], frows))
            lines.append("- 『首次被觀察到』是**上界**：真實發布時點早於或等於該 run；解析度＝兩次 run 的間隔。第一個來源日期可能在第一次 run 之前就已存在，**不可當作它的發布時點**。")
        lines.append("")
    return "\n".join(lines).rstrip()


def section_openapi_vs_rwd(reports, transport) -> str:
    lines = ["## 4. openapi vs rwd 來源日期差（rwd − openapi，天）", ""]
    rows = []
    for r in reports:
        for item in (r.get("openapi_vs_rwd") or []):
            if item.get("transport") != transport:
                continue
            rows.append([run_label(r), item.get("pair"), item.get("openapi_latest_source_date"),
                         item.get("rwd_latest_source_date"), item.get("diff_days"),
                         item.get("row_date_diff_days"), item.get("reason")])
    if not rows:
        lines.append("無資料（報告沒有 `openapi_vs_rwd`，可能全為 schema_version 1）。")
        return "\n".join(lines)
    lines.append(_md_table(["run（台北）", "pair", "openapi latest", "rwd latest", "diff_days", "列內日期 diff", "缺值原因"], rows))
    diffs = {}
    for r in reports:
        for item in (r.get("openapi_vs_rwd") or []):
            if item.get("transport") == transport and item.get("diff_days") is not None:
                diffs.setdefault(item["pair"], []).append(item["diff_days"])
    lines.append("")
    for pair, ds in sorted(diffs.items()):
        if len(ds) < MIN_RUNS_FOR_CHANGE:
            lines.append(f"- {pair}：{INSUFFICIENT}（可算差距的 run 只有 {len(ds)} 份）。")
        else:
            lines.append(f"- {pair}：diff_days 範圍 {min(ds)}～{max(ds)}（{len(ds)} 份）；{'穩定' if min(ds) == max(ds) else '不穩定'}。")
    lines.append("- rwd 頂層 `date` 可能是查詢日而非資料列日期；`latest_source_date` 為兩者最大值（與 freshness 同口徑），列內日期差另列供對照。")
    return "\n".join(lines)


def section_missing(reports, transport) -> str:
    lines = ["## 5. Missing（空字串／`-`／null）比例", ""]
    lines.append("比例＝(空字串＋`-`＋null 格數) ÷ 全部格數。**只計數，不補 0**；PE 欄位另列。")
    lines.append("")
    any_rows = False
    for ep in _endpoint_ids(reports):
        views = [(r, ep_view(r, ep, transport)) for r in reports]
        if not any(v and v["n_cells"] for _r, v in views):
            continue
        any_rows = True
        rows = []
        for r, v in views:
            if not v or not v["n_cells"]:
                rows.append([run_label(r), "—", "—", "—"])
                continue
            pe = {k: sum(c.values()) for k, c in v["missing_by_field"].items() if any(m in k for m in PE_FIELD_MARKERS)}
            rows.append([run_label(r), f"{v['missing_cells']}/{v['n_cells']}",
                         f"{v['missing_cells'] / v['n_cells']:.4%}", json.dumps(pe, ensure_ascii=False) if pe else "—"])
        lines.append(f"### {ep}")
        lines.append(_md_table(["run（台北）", "缺值格/全部格", "比例", "PE 類欄位缺值數"], rows))
        ratios = [v["missing_cells"] / v["n_cells"] for _r, v in views if v and v["n_cells"]]
        if len(ratios) < MIN_RUNS_FOR_CHANGE:
            lines.append(f"- 比例變化：**{INSUFFICIENT}**。")
        else:
            lines.append(f"- 比例範圍 {min(ratios):.4%}～{max(ratios):.4%}（{'有變' if min(ratios) != max(ratios) else '不變'}）。")
        lines.append("")
    if not any_rows:
        lines.append("無資料（報告沒有 `timeseries`）。")
    return "\n".join(lines).rstrip()


def section_revision(reports, transport) -> str:
    lines = ["## 6. 疑似 revision（同一 latest_source_date、sha 不同）", ""]
    suspects, comparable = [], 0
    for ep in _endpoint_ids(reports):
        groups = {}
        for r in reports:
            v = ep_view(r, ep, transport)
            if v and v["latest"] and v["sha"]:
                groups.setdefault(v["latest"], []).append((r, v))
        for d, items in sorted(groups.items()):
            if len(items) < 2:
                continue
            comparable += 1
            shas = {v["sha"] for _r, v in items}
            if len(shas) > 1:
                suspects.append((ep, d, items))
    if comparable == 0:
        lines.append(f"**{INSUFFICIENT}**：沒有任何端點在 ≥ 2 份報告中出現同一個 `latest_source_date`，無法比較同日資料是否被修正。")
        return "\n".join(lines)
    lines.append(f"可比較的（端點，來源日期）組合：{comparable}；其中 sha 不一致：{len(suspects)}。")
    lines.append("")
    if suspects:
        rows = []
        for ep, d, items in suspects:
            rows.append([ep, d.isoformat(), "、".join(f"{run_label(r)}={_short(v['sha'])}" for r, v in items),
                         "、".join(sorted({str(v['rows']) for _r, v in items}))])
        lines.append(_md_table(["端點", "來源日期", "各 run 的 sha[:8]", "列數集合"], rows))
    lines.append("")
    lines.append("⚠️ **sha 不同 ≠ 已確認 revision**。其他可能：同日不同 as-of 版本、rwd 頂層 `date`（查詢日）變動、"
                 "非日期欄位的盤中／盤後更新、列數增減、欄位順序變動、回應中的時間戳或雜訊。"
                 "要確認修正，需另比對『同一來源日期、同一代號』的欄位值（本腳本不存全表，做不到）。")
    return "\n".join(lines)


def section_nas_vs_direct(reports) -> str:
    lines = ["## 7. direct vs nas_proxy 一致性（旁證）", ""]
    total = same = 0
    for r in reports:
        for e in r.get("endpoints", []):
            if "direct_vs_nas_same_body" in e:
                total += 1
                same += 1 if e["direct_vs_nas_same_body"] else 0
    if not total:
        lines.append("無資料（沒有端點同時具備兩路徑的回應本文）。")
    else:
        lines.append(f"同一 run 內兩路徑本文 sha 相同：{same}/{total}。不同＝兩路徑取得的位元組不同（可能是取數時間差或來源動態內容）。**仍不能證明流量經過 NAS**（報告沒有出口 IP）。")
    return "\n".join(lines)


def section_terms(reports) -> str:
    lines = ["## 8. 條款研究（最新一份報告；不構成授權結論）", ""]
    lines.append(f"**{LICENSE_UNVERIFIED}**——下列只代表『頁面存在、含關鍵詞』，不是已讀懂條款，更不是可否商用的判斷。")
    lines.append("")
    rep = reports[-1] if reports else None
    if not rep:
        return "\n".join(lines)
    rows = []
    for e in rep.get("endpoints", []):
        if e.get("group") != "terms_reach":
            continue
        for tr, res in (e.get("transports") or {}).items():
            tp = res.get("terms_page") or {}
            chain = res.get("redirect_chain") or []
            rows.append([e["id"], tr, res.get("outcome"), res.get("n_hops"),
                         " → ".join(f"{h.get('host')}{h.get('path')}[{h.get('status')}]" for h in chain) or "—",
                         json.dumps(tp.get("counts"), ensure_ascii=False) if tp else "—", tp.get("status")])
    tr_res = rep.get("terms_research") or {}
    for f in tr_res.get("followed", []):
        for tr, res in (f.get("transports") or {}).items():
            tp = res.get("terms_page") or {}
            chain = res.get("redirect_chain") or []
            rows.append([f["id"], tr, res.get("outcome"), res.get("n_hops"),
                         " → ".join(f"{h.get('host')}{h.get('path')}[{h.get('status')}]" for h in chain) or "—",
                         json.dumps(tp.get("counts"), ensure_ascii=False) if tp else "—", tp.get("status")])
    if rows:
        lines.append(_md_table(["端點", "路徑", "outcome", "跳數", "redirect 鏈（host path [status]）", "關鍵詞次數", "狀態"], rows))
    else:
        lines.append("報告沒有條款研究資料。")
    sd = tr_res.get("swagger_description") or {}
    if sd.get("links"):
        lines.append("")
        lines.append("swagger `info.description` 內的連結：")
        for l in sd["links"]:
            lines.append(f"- {l.get('url')}（host `{l.get('host')}`，白名單內：{l.get('allowed')}）")
    return "\n".join(lines)


def section_limits() -> str:
    return "\n".join([
        "## 9. 多日序列可以／不可以得出的結論",
        "",
        "**可以（樣本足夠時，且都是觀察不是裁示）**：",
        "- 某端點的回應、欄位清單（schema_hash）、列數在觀察期間是否變動；",
        "- `latest_source_date` 隨 run 推進的節奏，以及它落後台北日幾天（lag_days）；",
        "- 某來源日期『首次被觀察到』的時點上界（≈ 發布延遲上界）；",
        "- openapi 與 rwd 的來源日期差是否穩定；",
        "- 空字串／`-` 缺值格數與比例是否變動；",
        "- 條款頁是否存在、是否含關鍵詞。",
        "",
        "**不可以**：",
        "- 授權／可否商用（需人讀條款；恆標 " + LICENSE_UNVERIFIED + "）；",
        "- 真正的修正（revision）——sha 不同只是線索，且報告不存全表；",
        "- 正式更新頻率／SLA——3～5 個交易日、每日 2 次的樣本，涵蓋不到財報季、假期、補班日；",
        "- 精確發布時點——只有上界；",
        "- 『流量經過 NAS』——沒有出口 IP 證據；",
        "- 市場整體 trailing PE／implied earnings——端點未提供，口徑待驗；",
        "- 任何可接正式 signal／AI Brain／正式資料層的結論。",
    ])


def analyze(reports, skipped=(), transport="direct") -> str:
    parts = ["# BL-0509 TWSE probe 多日序列分析", "",
             "> 研究性彙整，非 Data Source Decision Gate 裁示；不接正式 signal／AI Brain。", ""]
    parts.append(section_overview(reports, list(skipped), transport))
    if reports:
        parts += ["", section_changes(reports, transport),
                  "", section_latest_date_progress(reports, transport),
                  "", section_openapi_vs_rwd(reports, transport),
                  "", section_missing(reports, transport),
                  "", section_revision(reports, transport),
                  "", section_nas_vs_direct(reports),
                  "", section_terms(reports)]
    parts += ["", section_limits(), ""]
    return "\n".join(parts)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="+", help="目錄（遞迴找 *.json.gz）或 report.json.gz 檔")
    ap.add_argument("--out", help="另存 Markdown 的路徑")
    ap.add_argument("--transport", choices=("direct", "nas_proxy"), default="direct")
    args = ap.parse_args(argv)
    reports, skipped = load_reports(args.paths)
    md = analyze(reports, skipped, args.transport)
    sys.stdout.write(md)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(md, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
