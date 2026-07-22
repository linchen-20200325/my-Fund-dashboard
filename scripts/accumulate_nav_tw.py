"""scripts/accumulate_nav_tw.py — 每日 NAV 累積(台灣端 NAS / 本機 cron)v19.363 ③

封住策略體檢的最後致命傷「**覆蓋靠使用習慣**」:不靠 user 開 App,由台灣 IP 端
(NAS / 本機)每天自動抓一次最新淨值,寫入 Google Sheet `nav_history` 分頁 ——
與 App 端(v19.359)/CSV 匯入(v19.361)走**同一條累積管線**,(code, date) 冪等。

與 scripts/fetch_nav_cache.py(GitHub CI,美國 IP,精簡依賴)的差異:
  本腳本在**台灣 IP** 跑、裝**完整 requirements** → 直接走 app 已驗證的抓取鏈
  `services.moneydj_fetcher.auto_fetch_moneydj`(tab2/健診同一條),不做平行精簡實作。

── NAS / 本機 前置 ─────────────────────────────────────────────
1. 台灣 IP(直連即可;PROXY_URL 有設也相容)
2. `pip install -r requirements.txt`(需完整依賴;streamlit 只是被 import,不啟動)
3. 環境變數(infra.config env fallback):
     google_service_account = Service Account 的**完整 JSON 字串**
     macro_weights_sheet_id = Google Sheet ID
4. cron(建議台灣時間傍晚,基金 NAV 多為 T+1 傍晚更新):
     30 18 * * 1-5  cd /path/to/my-Fund-dashboard && python scripts/accumulate_nav_tw.py

── 行為 ────────────────────────────────────────────────────────
§1 Fail Loud:secrets 缺 → exit 2(不靜默);單檔抓失敗 → 顯式 skip + 計數(不偽造);
             全部抓失敗 → exit 1(cron 信可見)。
§5 冪等:同日重跑 (code,date) 去重,不灌水。
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _load_codes() -> list:
    """基金代碼 SSOT:復用 fetch_nav_cache._discover_fund_codes(硬編碼 baseline ∪
    cache self-heal ∪ Google Sheet),避免第二份清單漂移。載入失敗 → env NAV_CODES。"""
    try:
        spec = importlib.util.spec_from_file_location(
            "_fnc", _ROOT / "scripts" / "fetch_nav_cache.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return list(mod._discover_fund_codes())
    except Exception as e:  # noqa: BLE001
        print(f"[codes] ⚠️ 無法載入 fetch_nav_cache 清單:{e} → 改用 env NAV_CODES")
        env = os.environ.get("NAV_CODES", "")
        codes = [c.strip().upper() for c in env.split(",") if c.strip()]
        if not codes:
            print("[codes] ❌ NAV_CODES 也未設 → 無代碼可抓(§1 不猜)")
        return codes


def _default_fetch(code: str) -> dict:
    """App 已驗證的共用抓取鏈(tab2/健診同一條;台灣 IP 直連)。"""
    from services.moneydj_fetcher import auto_fetch_moneydj
    return auto_fetch_moneydj(code) or {}


def accumulate_once(codes: list, fetch_fn=None, append_fn=None) -> dict:
    """抓 codes 的最新 NAV → 一次批次寫入 nav_history。回傳 summary dict。

    fetch_fn / append_fn 可注入(測試用);單檔抓失敗顯式 skip 不中斷整批(§4.6)。
    """
    # _extract_point 為純函式(series 末點 SSOT,同 App 端取值規則);
    # scripts/ 為 ops 入口不受 L1-L3 import 規則約束,直接復用避免第二份取值邏輯。
    from ui.helpers.nav_history_hook import _extract_point

    if fetch_fn is None:
        fetch_fn = _default_fetch
    if append_fn is None:
        from services.nav_history_gs import append_points
        append_fn = append_points

    points, skipped_fetch = [], []
    for code in codes:
        try:
            fd = fetch_fn(code)
        except Exception as e:  # noqa: BLE001 — 單檔炸不拖累整批,顯式記錄
            print(f"  ⚠️ {code} 抓取失敗:{type(e).__name__}: {str(e)[:80]}")
            skipped_fetch.append(code)
            continue
        p = _extract_point(fd, code)
        if p is None:
            print(f"  ⚠️ {code} 無有效 (nav, date)(§1 不偽造,跳過)")
            skipped_fetch.append(code)
            continue
        p["source"] = "nas_cron"
        points.append(p)
        print(f"  ✅ {code} {p['nav_date']} nav={p['nav']}")

    res = append_fn(points) if points else {"written": 0, "skipped": 0}
    return {
        "total": len(codes),
        "fetched": len(points),
        "written": int(res.get("written", 0)),
        "skipped_dup": len(points) - int(res.get("written", 0)),
        "skipped_fetch": skipped_fetch,
    }


def main() -> int:
    from services.nav_history_gs import status
    st = status()
    if not st["enabled"]:
        print(f"❌ Google Sheets 未設定,缺:{', '.join(st['missing'])}"
              f"(env: google_service_account=SA JSON 字串 / macro_weights_sheet_id)")
        return 2  # §1 Fail Loud:配置錯 → 非零退出,cron 信可見

    codes = _load_codes()
    if not codes:
        return 2
    print(f"📋 台灣端每日累積:{len(codes)} 檔 → nav_history")
    s = accumulate_once(codes)
    print(f"\n📊 summary:total={s['total']} fetched={s['fetched']} "
          f"written={s['written']} dup={s['skipped_dup']} "
          f"fetch_fail={len(s['skipped_fetch'])}"
          f"{'(' + ', '.join(s['skipped_fetch']) + ')' if s['skipped_fetch'] else ''}")
    if s["fetched"] == 0:
        print("❌ 全部抓取失敗 — 檢查網路 / 來源改版")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
