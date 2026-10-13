"""CI 守衛：`.github/workflows/fx_obs_date_probe.yml` 的「按鈕分支」觸發不得變成執行入口。

## 守什麼

該 workflow 帶 `contents: write`。為了在 dispatch API 回 403 的環境也能觸發，
加了 `push` 到 `probe/fx-obs-date-trigger`（按鈕分支）。這條觸發只能當「按鈕」：

1. `on.push.branches` **只有** `probe/fx-obs-date-trigger`（不得擴成 main 或萬用字元）；
   `workflow_dispatch` 保留；沒有排程、沒有 pull_request。
2. 每一個 `actions/checkout` 都明確 `ref: main` —— 執行的永遠是 main 上的腳本，
   往按鈕分支推入改過的腳本不會被執行。
3. 報告分支 ≠ 觸發分支，且報告分支不會命中 push 觸發（防自我觸發迴圈）；
   推送指令只推到 `$RESULT_BRANCH`。

## ⚠️ 守不到什麼

* push 事件執行的是**被推那顆 commit 裡的 workflow 檔本身**。有人在按鈕分支上改掉這份 yml，
  本檔（跑在 main 的 CI）看不到那份改過的檔。本檔只守 repo 裡這一份。
* 不驗 GitHub 真的照文件行事；沒有觀測任何一次真實 run。
* 推送目標的檢查是對 `run:` 文字做的模式比對（找 `push` 指令的 refspec），
  換一種寫法（例如把分支名組進別的變數）可能需要同步改本檔。

PyYAML 會把 `on` 解析成布林 `True` 鍵，下方一律兩者都查。
"""
from __future__ import annotations

import fnmatch
import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

_WF = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "fx_obs_date_probe.yml"
_TRIGGER = "probe/fx-obs-date-trigger"
_RESULT = "probe/fx-obs-date-results"


@pytest.fixture(scope="module")
def wf() -> dict:
    return yaml.safe_load(_WF.read_text(encoding="utf-8"))


def _on(wf: dict) -> dict:
    on = wf.get("on", wf.get(True))
    assert isinstance(on, dict), f"on: 應為 mapping，實際 {on!r}"
    return on


def _steps(wf: dict):
    for job_name, job in wf["jobs"].items():
        for step in job.get("steps", []):
            yield job_name, job, step


def test_push_trigger_only_button_branch(wf):
    on = _on(wf)
    assert "workflow_dispatch" in on, "workflow_dispatch 必須保留"
    push = on.get("push")
    assert isinstance(push, dict), "應有 push 觸發（按鈕分支）"
    assert set(push) == {"branches"}, f"push 只允許 branches 篩選，實際 {sorted(push)}"
    assert push["branches"] == [_TRIGGER]
    for forbidden in ("schedule", "pull_request", "pull_request_target", "workflow_run"):
        assert forbidden not in on, f"不得有 {forbidden} 觸發"


def test_every_checkout_pins_main(wf):
    checkouts = [s for _, _, s in _steps(wf) if str(s.get("uses", "")).startswith("actions/checkout@")]
    assert checkouts, "應至少有一個 actions/checkout"
    for s in checkouts:
        w = s.get("with") or {}
        assert w.get("ref") == "main", f"checkout 必須 ref: main，實際 {w.get('ref')!r}"
        assert w.get("persist-credentials") is False, "checkout 不得把 token 留在 .git/config"


def test_result_branch_differs_and_never_triggers(wf):
    push_branches = _on(wf)["push"]["branches"]
    for job_name, job in wf["jobs"].items():
        rb = (job.get("env") or {}).get("RESULT_BRANCH")
        if rb is None:
            continue
        assert rb == _RESULT, f"{job_name} 的 RESULT_BRANCH 應為 {_RESULT}，實際 {rb!r}"
        assert rb not in push_branches
        assert not any(fnmatch.fnmatchcase(rb, pat) for pat in push_branches), (
            "報告分支會命中 push 觸發 → 自我觸發迴圈"
        )
    assert _TRIGGER != _RESULT


def test_push_commands_only_target_result_branch(wf):
    push_cmds = []
    for _, _, s in _steps(wf):
        run = s.get("run") or ""
        assert _TRIGGER not in run, "run 指令不得引用按鈕分支"
        for line in run.splitlines():
            if re.search(r"\bpush\b", line) and re.search(r"\b(a?git)\b", line):
                push_cmds.append(line.strip())
    assert push_cmds, "應至少有一行推送報告的指令"
    for line in push_cmds:
        assert "--force" not in line and " -f " not in f" {line} ", f"不得 force：{line}"
        assert "refs/heads/$RESULT_BRANCH" in line, f"推送目標必須是 $RESULT_BRANCH：{line}"
