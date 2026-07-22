"""scripts/migrate_nav_caches_to_sheet.py — 舊 NAV 快取一次性遷移進 Google Sheet(v19.365 ④)

三套儲存收斂的「搬家車」:把兩套舊磁碟/git 快取的歷史點灌進 durable SSOT
(Google Sheet `nav_history`),之後長期讀寫都以 Sheet 為主:

  1. cache/nav/{CODE}.json        — CI 每日快取(schema: {"history":[{"date","nav"}]})
  2. cache/nav_history/{code}.json — Tab6 手動 CSV 匯入(schema: {"dates":[...],"values":[...]})

冪等:走 nav_history_gs.append_points 的 (code,date) 去重,重跑不灌水(§5)。
過濾:預設只搬 fetch_nav_cache._discover_fund_codes 清單內的代碼(擋測試殘留檔
      如 XYZ/CACHED01);要全搬 → `python ... --all`。
§1:secrets 缺 → exit 2;壞檔顯式 skip + 計數,不猜不補。

用法(本機 / NAS,需 env 兩把 secrets,同 accumulate_nav_tw.py):
    python scripts/migrate_nav_caches_to_sheet.py          # 只搬白名單代碼
    python scripts/migrate_nav_caches_to_sheet.py --all    # 全搬
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _allowed_codes() -> set:
    """白名單 = fetch_nav_cache._discover_fund_codes(SSOT,同 ③)。失敗回空集(不猜)。"""
    try:
        spec = importlib.util.spec_from_file_location(
            "_fnc", _ROOT / "scripts" / "fetch_nav_cache.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return {c.strip().upper() for c in mod._discover_fund_codes()}
    except Exception as e:  # noqa: BLE001
        print(f"[allow] ⚠️ 無法載入白名單:{e}")
        return set()


def collect_points(nav_dir: Path, hist_dir: Path, allow: set | None) -> tuple[list, list]:
    """讀兩套舊快取 → 統一成 append_points 的 point dicts。回 (points, skipped_files)。

    allow=None → 不過濾(--all);否則只收白名單代碼。壞檔 / 濾掉的顯式列入 skipped。
    """
    points: list[dict] = []
    skipped: list[str] = []

    # 1) cache/nav(CI schema)
    for f in sorted(nav_dir.glob("*.json")) if nav_dir.is_dir() else []:
        code = f.stem.strip().upper()
        if allow is not None and code not in allow:
            skipped.append(f"{f.name}(非白名單)")
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            rows = d.get("history") or []
            n0 = len(points)
            for r in rows:
                points.append({"code": code, "nav": r.get("nav"),
                               "nav_date": r.get("date"),
                               "fund_name": d.get("fund_name") or "",
                               "source": "migrate_ci_cache"})
            print(f"  📦 cache/nav/{f.name}: {len(points) - n0} 點")
        except Exception as e:  # noqa: BLE001
            skipped.append(f"{f.name}({type(e).__name__})")

    # 2) cache/nav_history(Tab6 store schema)
    for f in sorted(hist_dir.glob("*.json")) if hist_dir.is_dir() else []:
        code = f.stem.strip().upper()
        if allow is not None and code not in allow:
            skipped.append(f"{f.name}(非白名單)")
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            dates, values = d.get("dates") or [], d.get("values") or []
            if len(dates) != len(values):
                skipped.append(f"{f.name}(dates/values 長度不符)")
                continue
            n0 = len(points)
            for dt, v in zip(dates, values):
                points.append({"code": code, "nav": v, "nav_date": dt,
                               "fund_name": "", "source": "migrate_disk_store"})
            print(f"  📦 cache/nav_history/{f.name}: {len(points) - n0} 點")
        except Exception as e:  # noqa: BLE001
            skipped.append(f"{f.name}({type(e).__name__})")

    return points, skipped


def main(argv: list | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    migrate_all = "--all" in args

    from services.nav_history_gs import append_points, status
    st = status()
    if not st["enabled"]:
        print(f"❌ Google Sheets 未設定,缺:{', '.join(st['missing'])}")
        return 2

    allow = None if migrate_all else _allowed_codes()
    if allow is not None and not allow:
        print("❌ 白名單載入失敗且未指定 --all(§1 不猜)")
        return 2

    points, skipped = collect_points(_ROOT / "cache" / "nav",
                                     _ROOT / "cache" / "nav_history", allow)
    if skipped:
        print(f"  ⚠️ 略過 {len(skipped)} 檔:{', '.join(skipped)}")
    if not points:
        print("(無可遷移點)")
        return 0

    res = append_points(points)  # (code,date) 去重 + §1 過濾壞點
    print(f"\n📊 遷移完成:讀到 {len(points)} 點 → 新寫入 {res['written']} 筆"
          f"(重複/壞點略過 {res['skipped']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
