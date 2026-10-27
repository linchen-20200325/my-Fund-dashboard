"""CI 守衛：`.github/workflows/twse_eps_probe.yml` 的「按鈕分支」觸發不得變成執行入口。

## 守什麼

該 workflow 帶 `contents: write`。為了在 dispatch API 回 403 的環境也能觸發，
加了 `push` 到 `probe/twse-eps-trigger`（按鈕分支）。這條觸發只能當「按鈕」：

1. `on.push.branches` **只有** `probe/twse-eps-trigger`（不得擴成 main 或萬用字元）；
   `workflow_dispatch` 保留；沒有 pull_request。
   **2026-10-27 起（客戶裁示 A）新增固定排程 `schedule`**：恰好兩條 cron、僅週一至週五、分鐘不落在整點／半點、
   小時與分鐘皆為固定整數（無 `*`／步進）。排程事件走與手動相同的路徑（同樣 checkout main、同樣 secret 範圍）。
   停用方式：刪除 `schedule:` 區塊並 PR（見 yml 檔頭）；停用時本檔 `test_schedule_*` 需一併改為斷言無排程。
2. **恰好一個** `actions/checkout`，且明確 `ref: main` —— 執行的永遠是 main 上的腳本。
3. step 的 `run` / `with` / `env` 與 job `env` **不得引用觸發端的 ref／SHA**
   （`github.sha` / `github.ref` / `github.head_ref` / `GITHUB_SHA` / `GITHUB_REF` / `head_ref`）
   —— 引用了就是有人想取回或使用觸發分支的內容。**本檔不設例外**：
   `Record executed SHA` 那一步用 `git rev-parse HEAD` 而非任何上述名稱，報告裡的觸發 SHA
   由腳本在執行期從 runner 預設環境變數讀取，不經 yml。
4. checkout 之後的取碼指令 —— `git checkout` / `git fetch` / `git pull` / `git switch` /
   `git reset` / `git restore`，以及**也能把別的版本內容寫到磁碟**的 `git show`
   （`git show <rev>:<path> > file`）/ `git archive` / `git worktree` ——
   在「執行探測腳本」那一步**之前**一律不得出現；之後（報告流程）每一行都
   必須只針對 `$RESULT_BRANCH`（`fetch ... "$RESULT_BRANCH"`、`checkout -B "$RESULT_BRANCH" FETCH_HEAD`、
   `checkout --orphan "$RESULT_BRANCH"`）。
5. 推送指令行：remote 必須是 `origin`、不得帶任何旗標、refspec **剛好一個**且等於
   `HEAD:refs/heads/$RESULT_BRANCH`；報告分支 ≠ 觸發分支，且不會命中 push 觸發（防自我觸發迴圈）。

## ⚠️ 守不到什麼（射程外缺口）

* push 事件執行的是**被推那顆 commit 裡的 workflow 檔本身**。有人在按鈕分支上改掉這份 yml，
  本檔（跑在 main 的 CI）看不到那份改過的檔。本檔只守 repo 裡這一份。
* 不驗 GitHub 真的照文件行事；沒有觀測任何一次真實 run。
* 指令檢查是對 `run:` 的**逐行文字**做的（`shlex` 斷詞；同一行以 `;` `&&` `||` `|` 串接、
  或以 `if` / `then` / `!` 開頭的 git 指令**看得到**）。
  **不加引號的** `$(...)` 內嵌也**看得到**：`shlex` 會把 `(` 斷成獨立的分隔符，
  例如 `X=$(git checkout origin/other -- scripts)` 會被擋（實測）。
  以下寫法**看不到**：
  **加了雙引號的** `"$(...)"` 內嵌（整串被當成一個字）、反引號內嵌的 git、
  跨行接續（`\\` 換行）、把 git 包進 shell 函式後以別名呼叫（`agit` 這個名字已特別認得，
  別的名字不認得）、`eval`／變數組出的指令、
  `env`／`command`／`sudo` 等前綴包住的 git、以及非 git 的取碼手段
  （`curl`／`gh api` 下載檔案、`actions/download-artifact`、其他 `uses:` action）。
  其中「其他 `uses:` action」僅由「恰好一個 actions/checkout」部分涵蓋。
* 只檢查 git 子指令名稱是否在第 4 點的清單內；清單外仍能取得別的版本內容的子指令
  （例如 `git cat-file -p <rev>:<path> > file`、`git read-tree` ＋ `git checkout-index`、
  `git bundle unbundle`）**看不到**。
* 腳本自己（`scripts/probe_twse_eps.py`）若在執行期去讀觸發分支的內容，本檔看不到。

PyYAML 會把 `on` 解析成布林 `True` 鍵，下方一律兩者都查。
缺 pyyaml **一律紅燈、不 skip**（安全守衛；先例見
`tests/test_dividend_calendar_cron_v19537.py::_load_workflow_yaml`，v19.540）。
"""
from __future__ import annotations

import fnmatch
import re
import shlex
from pathlib import Path

import pytest

_WF = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "twse_eps_probe.yml"
_TRIGGER = "probe/twse-eps-trigger"
_RESULT = "probe/twse-eps-results"
_PROBE_SCRIPT = "scripts/probe_twse_eps.py"
_REFSPEC = "HEAD:refs/heads/$RESULT_BRANCH"
_FORBIDDEN_REF_TOKENS = ("github.sha", "github.ref", "github.head_ref",
                         "GITHUB_SHA", "GITHUB_REF", "head_ref")
_CONTENT_VERBS = {"checkout", "fetch", "pull", "switch", "reset", "restore",
                  # 也能把別的版本內容寫到磁碟：`git show <rev>:<path> > file`、`git archive`、`git worktree add`
                  "show", "archive", "worktree"}
_GIT_NAMES = {"git", "agit"}


def _load_workflow_yaml() -> dict:
    """解析 workflow YAML；**缺 pyyaml 一律紅燈，不 skip**（安全守衛專用）。"""
    import yaml  # 刻意在函式內 import：缺套件 → 測試紅燈，不是 skip
    return yaml.safe_load(_WF.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def wf() -> dict:
    return _load_workflow_yaml()


def _on(wf: dict) -> dict:
    on = wf.get("on", wf.get(True))
    assert isinstance(on, dict), f"on: 應為 mapping，實際 {on!r}"
    return on


def _steps(wf: dict):
    for job_name, job in wf["jobs"].items():
        for step in job.get("steps", []):
            yield job_name, job, step


_SEPARATORS = {";", "&&", "||", "|", "&", "(", ")", "()", "{", "}"}
_LEADING_KEYWORDS = {"if", "then", "elif", "else", "while", "until", "do", "!", "time"}


def _git_cmds(line: str) -> list[tuple[str, list[str]]]:
    """把一行 run 文字解析成 [(git 子指令, 其後參數), ...]；一行可含多個以 `;` `&&` `||` `|` 串接的指令。

    跳過 `if` / `then` / `!` 等前綴關鍵字與 `git -c k=v` 這類全域選項，參數截到第一個重導向為止；
    `agit` 是本 workflow 自訂的「帶認證的 git」。斷詞失敗（引號不成對）→ 紅燈，不靜默放行。
    """
    s = line.strip()
    if not s or s.startswith("#"):
        return []
    lx = shlex.shlex(s, posix=True, punctuation_chars=True)
    lx.whitespace_split = True
    try:
        toks = list(lx)
    except ValueError as e:
        pytest.fail(f"run 行斷詞失敗，無法檢查：{s}（{e}）")
    segments, cur = [], []
    for t in toks:
        if t in _SEPARATORS:
            segments.append(cur)
            cur = []
        else:
            cur.append(t)
    segments.append(cur)
    out = []
    for seg in segments:
        while seg and seg[0] in _LEADING_KEYWORDS:
            seg = seg[1:]
        if not seg or seg[0] not in _GIT_NAMES:
            continue
        i = 1
        while i < len(seg) and seg[i].startswith("-"):
            i += 2 if seg[i] in ("-c", "-C") else 1
        if i >= len(seg):
            continue
        args = []
        for a in seg[i + 1:]:
            if a and set(a) <= set("<>&|"):  # 重導向（`>`、`>>`）之後不是 git 參數
                break
            args.append(a)
        out.append((seg[i], args))
    return out


def test_push_trigger_only_button_branch(wf):
    on = _on(wf)
    assert "workflow_dispatch" in on, "workflow_dispatch 必須保留"
    push = on.get("push")
    assert isinstance(push, dict), "應有 push 觸發（按鈕分支）"
    assert set(push) == {"branches"}, f"push 只允許 branches 篩選，實際 {sorted(push)}"
    assert push["branches"] == [_TRIGGER]
    for forbidden in ("pull_request", "pull_request_target", "workflow_run", "issue_comment", "repository_dispatch"):
        assert forbidden not in on, f"不得有 {forbidden} 觸發"
    assert set(on) == {"push", "schedule", "workflow_dispatch"}, f"on: 只允許 push／schedule／workflow_dispatch：{sorted(on, key=str)}"


_EXPECTED_CRONS = ["37 11 * * 1-5", "43 22 * * 1-5"]   # 台北週一至週五 19:37／週二至週六 06:43


def test_schedule_exactly_two_weekday_crons_off_the_hour(wf):
    sched = _on(wf).get("schedule")
    assert isinstance(sched, list), "應有 schedule（2026-10-27 客戶裁示 A）"
    assert all(isinstance(x, dict) and set(x) == {"cron"} for x in sched), f"schedule 項目只允許 cron：{sched!r}"
    crons = [x["cron"] for x in sched]
    assert crons == _EXPECTED_CRONS, f"cron 與裁示不符：{crons}"
    for c in crons:
        f = c.split()
        assert len(f) == 5, f"cron 應為 5 欄：{c}"
        minute, hour, dom, mon, dow = f
        assert minute.isdigit() and hour.isdigit(), f"分鐘／小時須為固定整數：{c}"
        assert int(minute) not in (0, 30), f"分鐘不得落在整點／半點：{c}"
        assert (dom, mon) == ("*", "*"), f"不得限定日期／月份：{c}"
        assert dow == "1-5", f"僅週一至週五：{c}"


def test_schedule_is_documented_in_header_with_disable_instruction():
    head = _WF.read_text(encoding="utf-8").split("\non:\n", 1)[0]
    for needle in ("shadow probe", "2026-10-27", "如何停用", "schedule:", "不接正式 signal"):
        assert needle in head, f"yml 檔頭缺少排程說明：{needle}"
    assert "沒有排程" not in head, "檔頭仍寫著『沒有排程』（過期敘述）"


def test_exactly_one_checkout_and_it_pins_main(wf):
    checkouts = [s for _, _, s in _steps(wf) if str(s.get("uses", "")).startswith("actions/checkout@")]
    assert len(checkouts) == 1, f"應恰好一個 actions/checkout，實際 {len(checkouts)}"
    w = checkouts[0].get("with") or {}
    assert w.get("ref") == "main", f"checkout 必須 ref: main，實際 {w.get('ref')!r}"
    assert w.get("persist-credentials") is False, "checkout 不得把 token 留在 .git/config"


def test_no_trigger_ref_or_sha_referenced(wf):
    blobs = []
    for job_name, job in wf["jobs"].items():
        blobs.append((f"{job_name}.env", repr(job.get("env") or {})))
    for job_name, _, s in _steps(wf):
        label = f"{job_name}/{s.get('name', '?')}"
        blobs.append((f"{label}.run", s.get("run") or ""))
        blobs.append((f"{label}.with", repr(s.get("with") or {})))
        blobs.append((f"{label}.env", repr(s.get("env") or {})))
    for where, text in blobs:
        for tok in _FORBIDDEN_REF_TOKENS:
            assert tok not in text, f"{where} 引用了觸發端的 ref/SHA（{tok}）"


def test_executed_sha_recorded_after_checkout(wf):
    steps = [s for _, _, s in _steps(wf)]
    idx_co = next(i for i, s in enumerate(steps) if str(s.get("uses", "")).startswith("actions/checkout@"))
    idx_probe = next(i for i, s in enumerate(steps) if _PROBE_SCRIPT in (s.get("run") or ""))
    rec = [i for i, s in enumerate(steps)
           if re.search(r"PROBE_EXECUTED_SHA=\$\(git rev-parse HEAD\)", s.get("run") or "")
           and "$GITHUB_ENV" in (s.get("run") or "")]
    assert rec, "checkout 後應以 git rev-parse HEAD 寫入 PROBE_EXECUTED_SHA"
    assert all(idx_co < i < idx_probe for i in rec), "必須在 checkout 之後、探測之前記錄"


def test_no_content_fetch_except_result_branch(wf):
    steps = [s for _, _, s in _steps(wf)]
    idx_probe = next(i for i, s in enumerate(steps) if _PROBE_SCRIPT in (s.get("run") or ""))
    cmds = [(i, line.strip(), verb, args)
            for i, s in enumerate(steps)
            for line in (s.get("run") or "").splitlines()
            for verb, args in _git_cmds(line)
            if verb in _CONTENT_VERBS]
    for i, line, verb, args in cmds:
        assert i > idx_probe, f"探測執行前不得有 git {verb}：{line}"
        assert "$RESULT_BRANCH" in args, f"報告流程的 git {verb} 只能針對 $RESULT_BRANCH：{line}"
        other_refs = [a for a in args if not a.startswith("-")
                      and a not in ("origin", "$RESULT_BRANCH", "FETCH_HEAD")]
        assert not other_refs, f"git {verb} 帶了 $RESULT_BRANCH 以外的對象 {other_refs}：{line}"


def test_result_branch_differs_and_never_triggers(wf):
    push_branches = _on(wf)["push"]["branches"]
    found = False
    for job_name, job in wf["jobs"].items():
        rb = (job.get("env") or {}).get("RESULT_BRANCH")
        if rb is None:
            continue
        found = True
        assert rb == _RESULT, f"{job_name} 的 RESULT_BRANCH 應為 {_RESULT}，實際 {rb!r}"
        assert rb not in push_branches
        assert not any(fnmatch.fnmatchcase(rb, pat) for pat in push_branches), (
            "報告分支會命中 push 觸發 → 自我觸發迴圈"
        )
    assert found, "找不到 RESULT_BRANCH"
    assert _TRIGGER != _RESULT


def test_push_command_refspec_exact(wf):
    pushes = []
    for _, _, s in _steps(wf):
        run = s.get("run") or ""
        assert _TRIGGER not in run, "run 指令不得引用按鈕分支"
        for line in run.splitlines():
            line_pushes = [args for verb, args in _git_cmds(line) if verb == "push"]
            pushes.extend((line.strip(), a) for a in line_pushes)
            if (not line_pushes and re.search(r"\bpush\b", line)
                    and not line.strip().startswith(("echo", "#"))):
                pytest.fail(f"認不得的 push 寫法（本檔只認 git／agit）：{line.strip()}")
    assert len(pushes) == 1, f"應恰好一行推送指令，實際 {[p[0] for p in pushes]}"
    line, args = pushes[0]
    flags = [a for a in args if a.startswith("-")]
    assert not flags, f"推送不得帶旗標 {flags}：{line}"
    assert args[:1] == ["origin"], f"remote 必須是 origin：{line}"
    refspecs = args[1:]
    assert refspecs == [_REFSPEC], f"refspec 必須剛好一個且為 {_REFSPEC}，實際 {refspecs}"


# ───────────────────────── 以下為 TWSE probe 追加的守衛（secret／force／main） ─────────────────────────
#
# 追加範圍：PROXY_URL 只在「Run probe」步驟的 env；run 字串與其他步驟不碰 secret；
# 沒有 `set -x`／`set -o xtrace`；沒有把 secret echo 出來；沒有 force 推送；不推 main。
# ⚠️ 射程外：只看 yml 文字。腳本（scripts/probe_twse_eps.py）是否印出 PROXY_URL 由腳本自己的測試負責，
# 本檔看不到；`${{ secrets.* }}` 以外的間接取得（例如 vars、跨 job outputs）本檔也不涵蓋。

_PROBE_STEP_NAME = "Run probe"


def _all_text_blobs(wf: dict):
    for job_name, job in wf["jobs"].items():
        yield f"{job_name}.env", repr(job.get("env") or {})
    for job_name, _, s in _steps(wf):
        label = f"{job_name}/{s.get('name', '?')}"
        yield f"{label}.run", s.get("run") or ""
        yield f"{label}.with", repr(s.get("with") or {})
        yield f"{label}.env", repr(s.get("env") or {})
        yield f"{label}.if", str(s.get("if") or "")


def test_proxy_url_only_in_run_probe_step_env(wf):
    hits = []
    for job_name, job in wf["jobs"].items():
        assert "PROXY_URL" not in repr(job.get("env") or {}), f"{job_name} job-level env 不得含 PROXY_URL"
        for s in job.get("steps", []):
            name = s.get("name", "?")
            for field in ("run", "with", "if"):
                assert "PROXY_URL" not in str(s.get(field) or ""), f"步驟「{name}」的 {field} 含 PROXY_URL"
            env = s.get("env") or {}
            if "PROXY_URL" in env or "PROXY_URL" in repr(env):
                hits.append((name, env))
    assert len(hits) == 1, f"PROXY_URL 應只出現在一個步驟的 env，實際 {[h[0] for h in hits]}"
    name, env = hits[0]
    assert name == _PROBE_STEP_NAME, f"PROXY_URL 只能在「{_PROBE_STEP_NAME}」步驟，實際在「{name}」"
    assert env.get("PROXY_URL") == "${{ secrets.PROXY_URL }}", f"PROXY_URL 必須取自 secrets.PROXY_URL：{env!r}"
    # 該步驟的 run 只能是跑探測腳本，不得內嵌 secret 或印環境
    probe = next(s for _, _, s in _steps(wf) if s.get("name") == _PROBE_STEP_NAME)
    assert _PROBE_SCRIPT in (probe.get("run") or "")


def test_secrets_only_referenced_where_expected(wf):
    """`secrets.*` 只允許：Run probe 的 PROXY_URL、Commit report 的 GH_TOKEN(GITHUB_TOKEN)；且都只在 env，不在 run。"""
    allowed = {("Run probe", "secrets.PROXY_URL"), ("Commit report to probe/twse-eps-results", "secrets.GITHUB_TOKEN")}
    seen = set()
    for where, text in _all_text_blobs(wf):
        for m in re.finditer(r"secrets\.[A-Za-z0-9_]+", text):
            assert where.endswith(".env"), f"{where} 在 env 以外引用 {m.group(0)}"
            step = where.split("/", 1)[1].rsplit(".", 1)[0] if "/" in where else where
            assert (step, m.group(0)) in allowed, f"{where} 引用了未預期的 secret：{m.group(0)}"
            seen.add((step, m.group(0)))
    assert seen == allowed, f"secret 引用與預期不符：{sorted(seen)}"
    # 也不得整包吐出 secrets／env 上下文
    for where, text in _all_text_blobs(wf):
        assert "toJSON(secrets" not in text and "secrets }}" not in text, f"{where} 整包展開 secrets"


def test_no_xtrace_and_no_secret_echo(wf):
    secret_names = ("PROXY_URL", "GH_TOKEN", "GITHUB_TOKEN")
    for _, _, s in _steps(wf):
        run = s.get("run") or ""
        label = s.get("name", "?")
        assert not re.search(r"\bset\s+-[A-Za-z]*x", run), f"「{label}」含 set -x"
        assert not re.search(r"\bxtrace\b", run), f"「{label}」含 xtrace"
        assert "bash -x" not in run and "sh -x" not in run, f"「{label}」以 -x 執行 shell"
        assert "ACTIONS_STEP_DEBUG" not in run
        for line in run.splitlines():
            st = line.strip()
            if re.match(r"(echo|printf|cat|env|printenv|set)\b", st) or "| tee" in st:
                for n in secret_names:
                    assert n not in st, f"「{label}」把 {n} 印出：{st}"
                if re.search(r"\$\{?AUTH\}?", st):
                    # AUTH 由 token 衍生；唯一允許的是登記遮罩
                    assert st.startswith('echo "::add-mask::'), f"「{label}」印出衍生自 token 的 AUTH：{st}"
        # 不得印整個環境
        assert not re.search(r"(^|\s)(env|printenv)(\s*$|\s*\|)", run, re.M), f"「{label}」印整個環境"
    # AUTH 的遮罩必須先於任何使用它的指令
    commit = next(s for _, _, s in _steps(wf) if s.get("env", {}).get("GH_TOKEN"))
    run = commit["run"]
    assert run.index("::add-mask::${AUTH}") < run.index("agit()"), "add-mask 必須先於 agit 使用 AUTH"


def test_no_force_push_and_never_pushes_main(wf):
    for _, _, s in _steps(wf):
        run = s.get("run") or ""
        label = s.get("name", "?")
        assert not re.search(r"--force|--force-with-lease|--mirror|--delete", run), (
            f"「{label}」含 force／mirror／delete 類旗標")
        for line in run.splitlines():  # 短旗標 -f 只在 push 行檢查（`[ ! -f file ]` 是檔案測試，不是 force）
            for verb, args in _git_cmds(line):
                if verb == "push":
                    assert not any(a == "-f" or (a.startswith("-") and not a.startswith("--") and "f" in a)
                                   for a in args), f"「{label}」push 帶 -f：{line.strip()}"
        assert not re.search(r"\+\s*HEAD|\+refs/", run), f"「{label}」有 `+` 前綴的 force refspec"
        assert not re.search(r"refs/heads/main\b|origin\s+main\b|:main\b|\bmaster\b", run), (
            f"「{label}」疑似觸碰 main 分支")
        assert "gh api" not in run and "curl" not in run, f"「{label}」不應用 gh api／curl 寫遠端"
    push = _on(wf)["push"]["branches"]
    assert "main" not in push and not any(fnmatch.fnmatchcase("main", p) for p in push)


def test_only_commit_step_has_write_token_and_checkout_has_no_persisted_creds(wf):
    # contents: write 是整個 workflow 唯一的權限，且 GITHUB_TOKEN 只在 commit 報告那一步出現
    assert wf.get("permissions") == {"contents": "write"}, f"permissions 應只有 contents: write：{wf.get('permissions')!r}"
    with_token = [s.get("name") for _, _, s in _steps(wf) if "GITHUB_TOKEN" in repr(s)]
    assert with_token == ["Commit report to probe/twse-eps-results"], f"GITHUB_TOKEN 出現的步驟：{with_token}"
    # 報告只含一個 add 目標，且位於 results/ 底下
    adds = [l.strip() for _, _, s in _steps(wf) for l in (s.get("run") or "").splitlines()
            if re.match(r"\s*git add\b", l)]
    assert adds == ['git add "results/$STAMP/report.json.gz"'], f"git add 只應加報告檔：{adds}"
