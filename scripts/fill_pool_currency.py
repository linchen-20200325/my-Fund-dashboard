"""scripts/fill_pool_currency.py — 用基金名補選股池空白 currency 欄 (v19.497)。

user 2026-08-20:「選股池 currency 幫我填一填」。沙盒無 SA 憑證寫不了 GS,改掛 GitHub Actions
(有 SA)手動跑一次。§1 Fail-Loud + 保守:
- **只填空白的 currency**(不覆蓋使用者已填的)。
- 幣別優先從**基金名後綴**判(`_ccy_from_fund_name`:美元/台幣/EUR…);判不出來且**名稱含
  「台灣/臺灣」→ 推定 TWD**(台股基金無外幣級別字樣即台幣,推定會 log 標明);再判不出 → **留空不猜**。
- 其餘欄位(code/name/isin/secid/status…)原樣保留(upsert 傳完整 entry)。
- `--dry-run`:只列出會補什麼,不寫入。

exit:缺 SA/GS 未啟用 → 2;讀取失敗 → 1;部分寫入失敗 → 1;成功(含 0 筆可補)→ 0。

── GitHub repo secrets(同 weekly_nav_backfill)──
    google_service_account = SA 完整 JSON(須為選股池 Sheet 編輯者)
    POOL_SHEET_ID          = (選填)選股池目標本;未設走程式 baked 預設
先 dry-run 驗證(不寫入):python scripts/fill_pool_currency.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _derive_ccy(name: str) -> "tuple[str, str]":
    """(currency, 方法);判不出 → ('', '')。"""
    from repositories.fund.sources import _ccy_from_fund_name
    _c = _ccy_from_fund_name(name)
    if _c:
        return _c, "名稱幣別字樣"
    _n = str(name or "")
    if "台灣" in _n or "臺灣" in _n:      # 台股基金無外幣級別字樣 → 推定台幣(保守、log 標明)
        return "TWD", "台股基金推定(名稱含台灣)"
    return "", ""


def main() -> int:
    ap = argparse.ArgumentParser(description="用基金名補選股池空白 currency")
    ap.add_argument("--dry-run", action="store_true", help="只列出將補的,不寫入")
    args = ap.parse_args()

    from repositories.pool_repository import _gs_enabled, add_or_update, list_pool

    if not _gs_enabled():
        print("[fill_pool_currency] GS 後端未啟用(缺 SA / sheet id)→ 只存本機無意義,exit 2",
              file=sys.stderr)
        return 2
    try:
        pool = list_pool()
    except Exception as e:  # noqa: BLE001
        print(f"[fill_pool_currency] 讀取選股池失敗:{type(e).__name__}: {e}", file=sys.stderr)
        return 1
    if not pool:
        print("[fill_pool_currency] 選股池空,無可補", file=sys.stderr)
        return 2

    to_fill: list = []
    skipped: list = []
    for e in pool:
        if e.currency:                      # 已填 → 不覆蓋(§1 尊重使用者)
            continue
        ccy, how = _derive_ccy(e.name)
        if ccy:
            to_fill.append((e, ccy, how))
        else:
            skipped.append(e)

    print(f"[fill_pool_currency] 選股池 {len(pool)} 檔;空白 currency 可補 {len(to_fill)} 檔"
          f",判不出 {len(skipped)} 檔")
    for e, ccy, how in to_fill:
        print(f"  ✏️  {e.code:<8} {e.name[:22]:<22} → {ccy}   ({how})")
    for e in skipped:
        print(f"  ⬜  {e.code:<8} {e.name[:22]:<22} → 判不出幣別,留空(請手動)")

    if args.dry_run:
        print("[fill_pool_currency] --dry-run:僅列出,未寫入")
        return 0
    if not to_fill:
        print("[fill_pool_currency] 無可補,結束")
        return 0

    n_ok = 0
    for e, ccy, _how in to_fill:
        try:
            e.currency = ccy                # PoolEntry.__post_init__ 會 upper/strip
            add_or_update(e)                # upsert by code,其餘欄原樣保留
            n_ok += 1
        except Exception as ex:  # noqa: BLE001 — 單筆失敗續補其餘,末尾回非 0
            print(f"[fill_pool_currency] {e.code} 寫入失敗:{type(ex).__name__}: {ex}",
                  file=sys.stderr)
    print(f"[fill_pool_currency] 已補 {n_ok}/{len(to_fill)} 檔 currency")
    return 0 if n_ok == len(to_fill) else 1


if __name__ == "__main__":
    sys.exit(main())
