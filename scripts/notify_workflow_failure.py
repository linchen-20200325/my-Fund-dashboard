"""scripts/notify_workflow_failure.py — 排程失敗時推一則 LINE(2026-09-06 P0)。

為什麼要有這支
--------------
`.github/workflows/weekly_nav_backfill.yml`(每日 NAV 累積)連續四天紅燈掛在 Actions 頁上
**沒有任何人被通知** —— 使用者是自己打開 Google Sheet、發現淨值停在 09-01 才知道的。
本 repo 的 8 個 workflow 在此之前**沒有任何一個**帶 `if: failure()` 或失敗推播
(2026-09-06 實測 `grep -rn "failure()" .github/workflows/` 0 命中)。
排程壞掉而沒人知道 = 靜默的資料流失,正是 §1／§5 要防的那一種。

用法(在 workflow 的 `if: failure()` 步驟裡)
    python scripts/notify_workflow_failure.py --title "每日 NAV 自動補齊"
    python scripts/notify_workflow_failure.py --title X --dry-run   # 只印不送

讀的 env(GitHub Actions 自動注入,本機缺就退成 "?"):
    GITHUB_SERVER_URL / GITHUB_REPOSITORY / GITHUB_RUN_ID / GITHUB_WORKFLOW
    GITHUB_STEP_SUMMARY  —— 若排程本身有寫 step summary,**摘錄進推播內容**,
                            讓手機上直接看得到失敗原因,不必開電腦點進 Actions。
    LINE_CHANNEL_TOKEN(或 LINE_CHANNEL_ACCESS_TOKEN)/ LINE_USER_ID —— 見 infra/line_push.py

§1 Fail Loud 的取捨,寫清楚
--------------------------
- **推播成功 → exit 0。**
- **憑證沒設 / 推播失敗 → exit 1**,並在 log 印出「這次失敗沒有人被通知」。
  刻意**不**吞成 exit 0:通知管道自己壞掉,就是本檔要解決的那個病的復發,
  必須看得見。⚠️ 本腳本只會掛在 `if: failure()` 的步驟上 ——
  **它 exit 1 不會把任何一次綠燈變紅**(那個 job 已經是紅的了)。
- 它**不會**、也不該影響原本那個失敗的 exit code 或訊息。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_SUMMARY_KEEP = 900          # LINE text 上限 5000;留餘裕給抬頭與網址


def _env(name: str, default: str = "?") -> str:
    return str(os.environ.get(name) or default).strip()


def _run_url() -> str:
    _repo = _env("GITHUB_REPOSITORY", "")
    _rid = _env("GITHUB_RUN_ID", "")
    if not _repo or not _rid:
        return "(本機執行,無 run 網址)"
    return f"{_env('GITHUB_SERVER_URL', 'https://github.com')}/{_repo}/actions/runs/{_rid}"


def _summary_excerpt() -> str:
    """摘錄 `$GITHUB_STEP_SUMMARY`。讀不到 → 回空字串(不是失敗,只是沒有這個資訊)。"""
    _p = os.environ.get("GITHUB_STEP_SUMMARY")
    if not _p:
        return ""
    try:
        _txt = Path(_p).read_text(encoding="utf-8").strip()
    except Exception as _e:  # noqa: BLE001 — §1 記 log 不靜默,但讀不到 summary 不該擋推播
        print(f"[notify_workflow_failure] 讀 GITHUB_STEP_SUMMARY 失敗(非致命):"
              f"{type(_e).__name__}: {_e}", file=sys.stderr)
        return ""
    if len(_txt) > _SUMMARY_KEEP:
        _txt = _txt[:_SUMMARY_KEEP] + "\n…(截斷,完整內容見 run 頁面)"
    return _txt


def build_message(title: str) -> str:
    """組推播內容。純函式(除了讀 env),可單測。"""
    _lines = [
        f"🔴 排程失敗:{title}",
        f"workflow:{_env('GITHUB_WORKFLOW')}",
        f"run:{_run_url()}",
    ]
    _sum = _summary_excerpt()
    if _sum:
        _lines += ["", "── 這次的結果摘要 ──", _sum]
    _lines += ["", "⚠️ 排程失敗代表這一輪的資料**沒有累積進去**,不處理就會每天重演。"]
    return "\n".join(_lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="排程失敗時推 LINE(P0:排程紅燈沒人知道)")
    ap.add_argument("--title", default="排程", help="給人看的排程名稱")
    ap.add_argument("--dry-run", action="store_true", help="只印不送")
    args = ap.parse_args(argv)

    _msg = build_message(args.title)
    try:
        from infra.line_push import push_text
        _res = push_text(_msg, dry_run=args.dry_run)
    except Exception as _e:  # noqa: BLE001 — 含 LinePushError:§1 不吞
        print(f"[notify_workflow_failure] 🔴 推播失敗,**這次排程失敗沒有人被通知**:"
              f"{type(_e).__name__}: {_e}", file=sys.stderr)
        return 1

    if _res.get("sent"):
        print("[notify_workflow_failure] ✅ 已推播", file=sys.stderr)
        return 0
    if _res.get("dry_run"):
        print("[notify_workflow_failure] dry-run:不送", file=sys.stderr)
        return 0
    print(f"[notify_workflow_failure] 🔴 沒有推播出去({_res.get('reason')})——"
          f"**這次排程失敗沒有人被通知**,請設好 LINE_CHANNEL_TOKEN / LINE_USER_ID。",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
