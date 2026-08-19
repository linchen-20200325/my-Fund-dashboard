#!/usr/bin/env python3
"""scripts/compare_inception_years.py —  3-3-3 兩份「成立年數」對照器（唯讀診斷）。

本檔**不改任何 production 判定**，只把兩套演算法對同一份 `fd` 各自算出來的
成立年數 / 3 年年化 / 3-3-3 判定並排印出來，讓 user 決定要不要收斂。

兩套演算法
==========
A 版：`services/health/report.py::build_health_analysis_row`
      → 成立年走 `services/health/report.py::_compute_holding_years`
      → 再走 SSOT `services/fund_screening.py::fund_inception_years`
      本檔**直接呼叫 production 函式**，零轉錄。

B 版：`services/fund_row.py::process_one_fund` 內嵌的 3-3-3 區塊。
      該區塊沒有被抽成函式，無法 import → 本檔 `_variant_b_*` 為**忠實轉錄**。
      轉錄漂移由 `tests/test_compare_inception_years.py` 的等價鎖守住：
      該測試拿同一批 fixture 餵**真的** `process_one_fund`，比對本檔轉錄的輸出，
      一旦 `fund_row.py` 的內嵌邏輯改動而本檔沒跟上，測試立刻紅。

查證結論（動工前先查，PROCESS §6）
=================================
稽核表列的「A 多讀一個 `fd.metrics.inception_date` 來源」**在 production 不可達**：
`metrics["inception_date"]` 全 repo 只有一個 writer（`services/fund_service.py`
`finalize_fund_metrics` 尾段），而它的前置條件正是「頂層 `inception_date` 已為真值」
——也就是 B 讀的同一個欄位。因此不存在「只有 metrics 帶成立日」的基金；
「保單子網域被封鎖 → 只有 metrics 有成立日」的情境是空集合。

真正還可能分歧的只剩「**兩邊都沒有成立日、雙雙退回 NAV 序列**」那條分支：
  D1 今日基準：A 的序列分支用 UTC 當日，B 用本機時區當日（台灣 = UTC+8）
               → 台灣時間 00:00–08:00 之間跑，兩者差 1 天（≈ 0.0027 年）。
               ⚠️ A 的**成立日分支**用的是本機當日，與 B 相同 —— 只有序列分支有此差。
  D2 樣本數  ：A 數 `len(series)`，B 數「不重複日期字串」的個數；序列若含同日重複
               （live + 累積歷史 union 後可能出現），兩者跨過 90 筆門檻的時機不同。
  D3 首日截斷：A 用 `(Timestamp - Timestamp).days` —— 首筆若帶盤中時間會被向下截斷；
               B 先切成 `YYYY-MM-DD` 再相減，不受影響。
以上三者都只在「無成立日」時才有機會發生，且量級 ≤ 1 天，只有剛好卡在 3.0 年
邊界的基金會翻轉判定。本工具就是用來量這件事到底有沒有發生在實際持倉上。

輸入來源（為什麼這樣選）
========================
兩套演算法吃的都是完整 `fd` dict（含 `series` / `inception_date` / `metrics` / `perf`），
repo 內**沒有**任何現成快照同時帶這幾樣：
  - `data_cache/*.parquet`  → 只有總經序列，無基金
  - `cache/nav/*.json`      → 只有 NAV 累積，無成立日 / metrics
  - 組合備份 JSON            → 只有持倉金額，無 NAV
  - 批次分析下載 CSV         → 有 nav_date（末日）但無**首日**、無成立日
所以採「一次上線抓 → dump 快照 → 之後純離線重跑」兩段式：
  1) `--live --dump snap.json`  上線抓一次（走 production `auto_fetch_moneydj`）
  2) `--snapshot snap.json`     之後隨時離線重跑，零網路
快照保留 NAV index 的**完整字串**（含時間 / 時區 / 重複日期），不壓成 date→value dict，
否則會把 D2 / D3 這兩個差異來源在輸入端就抹掉，量出假的「零差異」（§1）。

代號清單預設讀 `config/preset_funds.json`（repo 內既有的實際常用基金清單）；
Google Sheet 保單持倉需 OAuth，腳本場景取不到 → 用 `--codes A,B,C` 貼上即可。

CLI
===
    python scripts/compare_inception_years.py --live --dump snap.json
    python scripts/compare_inception_years.py --snapshot snap.json
    python scripts/compare_inception_years.py --live --codes ACCP138,TLZF9
    python scripts/compare_inception_years.py --snapshot snap.json --all
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

_REPO = Path(__file__).resolve().parent.parent
_PRESET_JSON = _REPO / "config" / "preset_funds.json"


# ════════════════════════════════════════════════════════════════════════
# B 版：`services/fund_row.py::process_one_fund` 內嵌 3-3-3 區塊的忠實轉錄
#   ⚠️ 改這裡之前先看 tests/test_compare_inception_years.py 的等價鎖。
#   ⚠️ 這裡刻意不「順手修正」任何看起來像 bug 的寫法 —— 本檔的用途是量差異，
#      把 B 寫成 A 的樣子等於量出零差異，違反本次任務目的。
# ════════════════════════════════════════════════════════════════════════
def variant_b_nav_dict(fd: dict) -> dict:
    """B 版在算 3-3-3 之前先把 `fd["series"]` 攤平成的那份 dict（轉錄）。

    key 取索引字串前 10 碼 → **同日重複會被吃掉一筆**（D2 的來源）。
    """
    nav_s = fd.get("series")
    if nav_s is None:
        return {}
    return {
        str(idx)[:10]: float(v)
        for idx, v in nav_s.items()
        if v == v  # NaN guard（NaN != NaN）
    }


def variant_b_years(fd: dict, nav_dict: dict, today=None):
    """B 版成立年數（轉錄）。回傳 float 年數或 None。

    Args:
        today: 注入用（測試 / 重現）；None → `date.today()`（本機時區，D1 的來源）
    """
    # v19.485:成立年數推導改呼 SSOT(H3 proxy<3年→None);B 版本就該鏡射 fund_row,
    # 現在literal同源,parity 不再靠人工轉錄維持。today 注入供重現。
    from services.health.dividend import derive_years_for_333
    _mj_raw_333 = fd.get("moneydj_raw") or fd
    _inc_meta = (fd.get("inception_date") or _mj_raw_333.get("inception_date") or "")
    _first_iso = sorted(nav_dict.keys())[0] if nav_dict else None
    _yrs_inc, _ = derive_years_for_333(_inc_meta, _first_iso, today=today)
    return _yrs_inc


def variant_b_ann_3y(fd: dict):
    """B 版 3 年年化 %（v19.485 改呼 SSOT:含息優先 + P3 複數保護,鏡射 fund_row）。"""
    from services.health.dividend import derive_ann_3y_for_333
    _ann_3y, _ = derive_ann_3y_for_333(fd, fd.get("metrics") or {})
    return _ann_3y


def variant_b_status(fd: dict, today=None) -> str:
    """B 版最終顯示字串（轉錄 `fund_row.py` 的 emoji + 訊息截斷規則）。"""
    from services.health.dividend import check_333_principle

    _333_emoji = "⬜"
    _333_msg = "資料不足"
    try:
        nav_dict = variant_b_nav_dict(fd)
        _yrs_inc = variant_b_years(fd, nav_dict, today=today)
        _ann_3y = variant_b_ann_3y(fd)
        _333_r = check_333_principle(_yrs_inc, _ann_3y)
        if _333_r.get("passed") is True:
            _333_emoji = "✅"
        elif _333_r.get("passed") is False:
            _333_emoji = "❌"
        _333_msg = _333_r.get("message", "")
    except Exception as _e_333:  # noqa: BLE001 — 轉錄 B 的「誠實報計算失敗」語意
        _333_emoji = "⚠️"
        _333_msg = f"計算失敗({type(_e_333).__name__})"
    return f"{_333_emoji} {_333_msg[:32]}" if _333_msg else _333_emoji


# ════════════════════════════════════════════════════════════════════════
# A 版：直接呼 production（零轉錄）
# ════════════════════════════════════════════════════════════════════════
def _normalize_like_a(fd: dict) -> dict:
    """複製 `build_health_analysis_row` 進門那道 shape normalize。

    只影響 `_compute_holding_years` 讀到的 dict 形狀（頂層 vs moneydj_raw），
    不影響取值結果 —— 但為了「A 端看到的東西跟 production 一模一樣」仍照做。
    """
    if "moneydj_raw" not in fd and "perf" in fd:
        return {
            "moneydj_raw": fd,
            "metrics": fd.get("metrics") or {},
            "series": fd.get("series"),
            "perf_source": fd.get("perf_source"),
        }
    return fd


def variant_a_years(fd: dict):
    from services.health.report import _compute_holding_years
    return _compute_holding_years(_normalize_like_a(fd))


def variant_a_row(fd: dict, code: str) -> dict:
    from services.health.report import build_health_analysis_row
    return build_health_analysis_row(fd, code)


# ════════════════════════════════════════════════════════════════════════
# 差異歸因
# ════════════════════════════════════════════════════════════════════════
def _inception_from(fd: dict) -> tuple:
    """回傳 (取到的成立日字串或 None, 命中的欄位名)。

    順序照 A 版（頂層 → metrics → moneydj_raw）；B 版少中間那一段。
    """
    _mj = fd.get("moneydj_raw") or {}
    if fd.get("inception_date"):
        return str(fd["inception_date"]), "fd.inception_date"
    if (fd.get("metrics") or {}).get("inception_date"):
        return str(fd["metrics"]["inception_date"]), "fd.metrics.inception_date"
    if _mj.get("inception_date"):
        return str(_mj["inception_date"]), "fd.moneydj_raw.inception_date"
    return None, "（無）"


def _series_facts(fd: dict, nav_dict: dict) -> dict:
    s = fd.get("series")
    out = {
        "n_series": None, "n_nav_dict": len(nav_dict),
        "first_a": None, "first_b": None,
        "index_tz": None, "index_has_time": None,
    }
    if s is None:
        return out
    try:
        s2 = s.dropna().sort_index()
        out["n_series"] = int(len(s2))
        if len(s2):
            first = pd.Timestamp(s2.index[0])
            out["first_a"] = str(first)
            out["index_tz"] = str(first.tz) if first.tzinfo is not None else None
            out["index_has_time"] = bool(
                first.hour or first.minute or first.second or first.microsecond)
    except Exception as e:  # noqa: BLE001 — 診斷腳本：算不出就標明，不猜
        out["first_a"] = f"<無法解析: {type(e).__name__}>"
    if nav_dict:
        out["first_b"] = sorted(nav_dict.keys())[0]
    return out


def diagnose(fd: dict, code: str, today_local=None) -> dict:
    """對單檔跑兩套演算法 + 歸因。純函式（除了讀 fd），零 IO、零網路。"""
    nav_dict = variant_b_nav_dict(fd)
    inc_val, inc_src = _inception_from(fd)
    facts = _series_facts(fd, nav_dict)

    yrs_a = variant_a_years(fd)
    yrs_b = variant_b_years(fd, nav_dict, today=today_local)

    row_a = variant_a_row(fd, code)
    status_a = row_a.get(" 3-3-3") or ""
    # v19.485 PR-2:3-3-3 的 verdict 3 年年化改由 SSOT `derive_ann_3y_for_333`(含息優先)
    #   單一來源供 A(report verdict)/ B(fund_row verdict)共用 → 兩邊必然相同(不再分歧)。
    #   ⚠️ 與顯示欄「3Y 年化 %」(row_a,純NAV chain)**刻意分開**:此處比的是 verdict 口徑,
    #   拿顯示欄(純NAV)去比 B 的含息會製造假分歧(H4 decouple 後)。
    from services.health.dividend import derive_ann_3y_for_333
    ann_a, _ = derive_ann_3y_for_333(fd, fd.get("metrics") or {})   # report verdict 口徑
    status_b = variant_b_status(fd, today=today_local)
    ann_b = variant_b_ann_3y(fd)

    reasons: list[str] = []
    if inc_val:
        # 成立日存在 → 兩邊都走成立日分支、都用本機當日 → 理論上必然相同
        if inc_src == "fd.metrics.inception_date":
            reasons.append(
                "成立日只在 metrics —— 這是稽核假設的高風險情境，"
                "與『單一 writer』查證結論相牴觸，請回頭複查 finalize_fund_metrics")
        if not _years_close(yrs_a, yrs_b):
            reasons.append("成立日分支兩邊不同 —— 非預期，請貼本列回報")
    else:
        if not _years_close(yrs_a, yrs_b):
            if facts["n_series"] != facts["n_nav_dict"]:
                reasons.append(
                    f"D2 樣本數：序列 {facts['n_series']} 筆 vs 不重複日期 "
                    f"{facts['n_nav_dict']} 筆（同日重複被吃掉）")
            if facts["index_has_time"]:
                reasons.append("D3 首日帶盤中時間 → A 端相減被向下截斷")
            if facts["first_a"] and facts["first_b"] and \
                    str(facts["first_a"])[:10] != str(facts["first_b"])[:10]:
                reasons.append(
                    f"首筆日期不同：A={str(facts['first_a'])[:10]} / B={facts['first_b']}")
            if not reasons:
                reasons.append("D1 今日基準：A 用 UTC 當日、B 用本機當日（≤ 1 天）")
    if _num_differs(ann_a, ann_b):
        reasons.append(f"3 年年化不同：A={ann_a} / B={ann_b}")

    return {
        "code": code,
        "inception": inc_val, "inception_src": inc_src,
        "years_a": yrs_a, "years_b": yrs_b,
        "ann_a": ann_a, "ann_b": ann_b,
        "status_a": status_a, "status_b": status_b,
        "verdict_a": (status_a or "?")[:1], "verdict_b": (status_b or "?")[:1],
        "differs": (not _years_close(yrs_a, yrs_b))
                   or ((status_a or "")[:1] != (status_b or "")[:1]),
        "reasons": reasons,
        **facts,
    }


def _years_close(a, b) -> bool:
    """浮點比較走容差（§4.3 禁 `==`）。兩邊都 None 視為相同。"""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    import math
    return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-9)


def _num_differs(a, b) -> bool:
    if a is None and b is None:
        return False
    if a is None or b is None:
        return True
    import math
    try:
        return not math.isclose(float(a), float(b), rel_tol=1e-6, abs_tol=1e-9)
    except (TypeError, ValueError):
        return str(a) != str(b)


# ════════════════════════════════════════════════════════════════════════
# 快照 I/O（離線重跑用）
# ════════════════════════════════════════════════════════════════════════
def fd_to_snapshot(fd: dict) -> dict:
    """把 fd 縮成「本比較需要的最小欄位」，NAV index 保留完整字串（見檔頭說明）。"""
    s = fd.get("series")
    nav_points = []
    if s is not None:
        try:
            nav_points = [[str(i), (None if v != v else float(v))] for i, v in s.items()]
        except Exception as e:  # noqa: BLE001
            nav_points = []
            print(f"[snapshot] ⚠️ series 無法序列化：{type(e).__name__}: {e}")
    _m = fd.get("metrics") or {}
    return {
        "inception_date": fd.get("inception_date"),
        "metrics": {k: _m.get(k) for k in
                    ("inception_date", "ret_3y_ann", "ret_3y_cum", "ret_3y",
                     "sharpe", "std_1y", "max_drawdown", "ret_5y_ann",
                     "ret_5y_cum", "ret_5y", "nav")},
        "perf": dict(fd.get("perf") or {}),
        "perf_source": fd.get("perf_source"),
        "fund_name": fd.get("fund_name"),
        "category": fd.get("category"),
        "nav_points": nav_points,
    }


def snapshot_to_fd(snap: dict) -> dict:
    pts = [(i, v) for i, v in (snap.get("nav_points") or []) if v is not None]
    if pts:
        idx = pd.to_datetime([i for i, _ in pts])
        series = pd.Series([float(v) for _, v in pts], index=idx)
    else:
        series = None
    return {
        "inception_date": snap.get("inception_date"),
        "metrics": dict(snap.get("metrics") or {}),
        "perf": dict(snap.get("perf") or {}),
        "perf_source": snap.get("perf_source"),
        "fund_name": snap.get("fund_name"),
        "category": snap.get("category"),
        "series": series,
    }


def load_codes(args) -> list:
    if args.codes:
        return [c.strip().upper() for c in args.codes.split(",") if c.strip()]
    if not _PRESET_JSON.exists():
        raise SystemExit(f"找不到 {_PRESET_JSON}；請用 --codes 指定代號清單")
    data = json.loads(_PRESET_JSON.read_text(encoding="utf-8"))
    return [str(f.get("code", "")).strip().upper()
            for f in (data.get("funds") or []) if f.get("code")]


# ════════════════════════════════════════════════════════════════════════
# 報告
# ════════════════════════════════════════════════════════════════════════
def _fmt_years(v) -> str:
    return "—" if v is None else f"{float(v):.2f} 年"


def render_report(rows: list, show_all: bool = False) -> str:
    out: list = []
    out.append("=" * 78)
    out.append(" 3-3-3 成立年數 — A（health/report）vs B（fund_row）對照")
    out.append(f"跑的時間：本機 {_dt.datetime.now():%Y-%m-%d %H:%M} / "
               f"UTC {_dt.datetime.now(_dt.timezone.utc):%Y-%m-%d %H:%M}")
    out.append("=" * 78)

    diff_rows = [r for r in rows if r["differs"]]
    out.append("")
    out.append(f"共比對 {len(rows)} 檔；**判定或年數不同的有 {len(diff_rows)} 檔**。")
    out.append("")

    if diff_rows:
        out.append("── 不同的那幾檔 ─────────────────────────────────────────")
        for r in diff_rows:
            out.append("")
            out.append(f"● {r['code']}")
            out.append(f"    成立年數   A={_fmt_years(r['years_a'])}"
                       f"    B={_fmt_years(r['years_b'])}")
            out.append(f"    3-3-3 判定 A={r['status_a'] or '—'}")
            out.append(f"               B={r['status_b'] or '—'}")
            out.append(f"    成立日     {r['inception'] or '（抓不到，兩邊都退 NAV 首日）'}"
                       f"（來源 {r['inception_src']}）")
            out.append(f"    NAV        首筆 A={r['first_a']} / B={r['first_b']}；"
                       f"筆數 A={r['n_series']} / B={r['n_nav_dict']}")
            for why in r["reasons"]:
                out.append(f"    ↳ 差異來源：{why}")
        out.append("")
    else:
        out.append("── 沒有任何一檔的判定或年數不同 ───────────────────────")
        out.append("   → 這一輪的實際持倉上，兩份演算法輸出一致；")
        out.append("     收斂成一份屬「整理」而非「修 bug」，請照 §-1 自行決定要不要做。")
        out.append("")

    if show_all:
        out.append("── 全部明細（--all）───────────────────────────────────")
        out.append(f"{'代號':<10} {'A 年數':>9} {'B 年數':>9}  {'A':<2} {'B':<2} 成立日來源")
        for r in rows:
            out.append(f"{r['code']:<10} {_fmt_years(r['years_a']):>9} "
                       f"{_fmt_years(r['years_b']):>9}  "
                       f"{r['verdict_a']:<2} {r['verdict_b']:<2} {r['inception_src']}")
        out.append("")

    out.append("── 怎麼讀 ─────────────────────────────────────────────")
    out.append("  ✅ 通過 3-3-3 ／ ❌ 明確未通過 ／ ⬜ 資料不足 ／ ⚠️ 計算失敗")
    out.append("  A 端沒有 ⚠️ 這個狀態 —— 它把「算爆了」歸到 ⬜（B 這點比較誠實）。")
    out.append("  成立日抓得到時，兩邊讀的是同一個欄位、用同一個當日基準 → 必然一致；")
    out.append("  只有兩邊都退回 NAV 首日推算時才可能差（差距 ≤ 1 天，見檔頭 D1/D2/D3）。")
    return "\n".join(out)


# ════════════════════════════════════════════════════════════════════════
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=" 3-3-3 兩份成立年數對照（唯讀）")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--live", action="store_true",
                     help="上線抓（走 production auto_fetch_moneydj）")
    src.add_argument("--snapshot", metavar="FILE",
                     help="離線：讀先前 --dump 出來的快照")
    ap.add_argument("--codes", help="逗號分隔代號；省略則讀 config/preset_funds.json")
    ap.add_argument("--dump", metavar="FILE", help="--live 時同時把快照存下來供離線重跑")
    ap.add_argument("--all", action="store_true", help="附全部明細，不只印不同的")
    ap.add_argument("--out", metavar="FILE", help="報告另存純文字檔")
    args = ap.parse_args(argv)

    fds: dict = {}
    if args.snapshot:
        raw = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
        for code, snap in (raw.get("funds") or {}).items():
            fds[code] = snapshot_to_fd(snap)
        if not fds:
            raise SystemExit(f"{args.snapshot} 沒有任何基金資料")
    else:
        from services.moneydj_fetcher import auto_fetch_moneydj
        for code in load_codes(args):
            print(f"[live] 抓 {code} …")
            try:
                fd = auto_fetch_moneydj(code)
            except Exception as e:  # noqa: BLE001 — 單檔炸掉不擋整批，但要說出來
                print(f"[live] ❌ {code} 抓取失敗：{type(e).__name__}: {e}")
                continue
            if not isinstance(fd, dict) or fd.get("series") is None:
                print(f"[live] ⬜ {code} 無 NAV 序列（B 端在 3-3-3 之前就會退出，跳過）")
                continue
            fds[code] = fd
        if args.dump:
            Path(args.dump).write_text(json.dumps(
                {"dumped_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                 "funds": {c: fd_to_snapshot(f) for c, f in fds.items()}},
                ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"[dump] 快照已存 → {args.dump}")

    rows = [diagnose(fd, code) for code, fd in sorted(fds.items())]
    report = render_report(rows, show_all=args.all)
    print(report)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"\n[out] 報告已存 → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
