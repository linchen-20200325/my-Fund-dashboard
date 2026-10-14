"""tests/test_moneydj_basic_probe.py — `scripts/probe_moneydj_basic_page.py` 與其 workflow 的守衛（不打網路）。

## 第一部分：workflow 形狀（比照 `tests/test_fx_obs_date_probe_workflow.py`，判準逐條照抄、只換常數）

`.github/workflows/moneydj_basic_probe.yml` 帶 `contents: write`，push 到按鈕分支
`probe/moneydj-basic-trigger` 觸發。這條觸發只能當「按鈕」：

1. `on.push.branches` 只有按鈕分支；`workflow_dispatch` 保留；無排程、無 pull_request。
2. 恰好一個 `actions/checkout`，`ref: main`、`persist-credentials: false`。
3. step 的 `run`／`with`／`env` 與 job `env` 不得引用觸發端的 ref／SHA。
4. 探測步驟之前不得有取碼的 git 子指令；之後只能針對 `$RESULT_BRANCH`。
5. 推送指令恰好一行，`origin`、無旗標、refspec 恰為 `HEAD:refs/heads/$RESULT_BRANCH`。

另加本 workflow 專屬的四條：沒有 dispatch 輸入參數（代碼寫在腳本裡，不吃使用者輸入）、
有 `timeout-minutes`、提交報告那一步 `if: always()` 且報告路徑含時間戳與 run id、
除提交報告那一步的 `GITHUB_TOKEN` 外不引用任何 secret（沒有先例把 `PROXY_URL` 橋接進 `infra.proxy`）。

⚠️ 守不到什麼：與 fx 那支相同（見該檔「守不到什麼」一段，本檔不重抄）——
push 事件執行的是被推那顆 commit 裡的 workflow 檔本身；指令檢查只是逐行文字斷詞；
不驗 GitHub 真的照文件行事；沒有觀測任何一次真實 run。缺 pyyaml 一律紅燈、不 skip。

## 第二部分：探測腳本（注入假的 fetch，不連網）

只驗腳本把「取數結果」與「declared_profile 正式解析函式的結果」照實記進報告，
**不驗 MoneyDJ 實際長什麼樣** —— 那正是探測要量的東西。
負控代碼一律以 `probe.make_negative_control(...)` 在執行期生成，不寫字面值。
"""
from __future__ import annotations

import base64
import fnmatch
import gzip
import importlib.util
import json
import re
import shlex
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_WF = _ROOT / ".github" / "workflows" / "moneydj_basic_probe.yml"
_TRIGGER = "probe/moneydj-basic-trigger"
_RESULT = "probe/moneydj-basic-results"
_PROBE_SCRIPT = "scripts/probe_moneydj_basic_page.py"
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
    for forbidden in ("schedule", "pull_request", "pull_request_target", "workflow_run"):
        assert forbidden not in on, f"不得有 {forbidden} 觸發"


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


# ═════════════════════════════════════════════════════════════════════
# 第一部分補充：本 workflow 專屬
# ═════════════════════════════════════════════════════════════════════

def test_dispatch_has_no_inputs(wf):
    disp = _on(wf).get("workflow_dispatch")
    assert not (disp or {}).get("inputs"), "代碼清單寫在腳本裡；workflow 不接受使用者輸入"
    for _, _, s in _steps(wf):
        assert "github.event.inputs" not in repr(s), "不得把使用者輸入接進任何 step"


def test_timeout_and_commit_step_always(wf):
    job = wf["jobs"]["probe"]
    assert isinstance(job.get("timeout-minutes"), int) and job["timeout-minutes"] > 0
    commit = [s for s in job["steps"] if "$RESULT_BRANCH" in (s.get("run") or "")]
    assert commit and all(s.get("if") == "always()" for s in commit), "提交報告那一步必須 if: always()"
    assert "results/$STAMP" in commit[0]["run"] and "GITHUB_RUN_ID" in commit[0]["run"], (
        "報告路徑須含時間戳與 run id")


def test_probe_step_runs_script_with_report_path(wf):
    runs = [(s.get("run") or "").strip() for _, _, s in _steps(wf) if _PROBE_SCRIPT in (s.get("run") or "")]
    assert runs == [f'python {_PROBE_SCRIPT} --out "$REPORT_PATH"']


_SECRET_RE = re.compile(r"secrets|github\.token", re.IGNORECASE)
_ALLOWED_SECRET = "${{ secrets.GITHUB_TOKEN }}"


def _secret_violations(text: str) -> list:
    """整份 yml **文字**掃描（不經 YAML 解析，註解、頂層 env、任何寫法都看得到）：
    `secrets`／`github.token` 只准以 `${{ secrets.GITHUB_TOKEN }}` 出現**恰好一次**，且在提交報告那一步裡。
    回傳違規描述；空串列＝合規。"""
    out = []
    lines = text.splitlines()
    hits = [(i, m) for i, ln in enumerate(lines) for m in _SECRET_RE.finditer(ln)]
    allowed_lines = [i for i, ln in enumerate(lines) if _ALLOWED_SECRET in ln]
    for i, m in hits:
        ln = lines[i]
        if i in allowed_lines and m.group(0) == "secrets" and ln[m.start() - 4:m.end() + len(".GITHUB_TOKEN }}")] \
                == _ALLOWED_SECRET:
            continue
        out.append(f"第 {i + 1} 行不允許的寫法：{ln.strip()}")
    if len(allowed_lines) != 1:
        out.append(f"`{_ALLOWED_SECRET}` 應恰好出現一次，實際 {len(allowed_lines)} 次")
    else:
        # 那一行必須在提交報告那一步（自它往上找最近的 `- name:`）
        step = next((lines[k] for k in range(allowed_lines[0], -1, -1) if lines[k].strip().startswith("- name:")),
                    "")
        if "Commit report" not in step:
            out.append(f"`{_ALLOWED_SECRET}` 不在提交報告那一步：{step.strip()}")
    return out


def test_only_github_token_secret_and_only_in_commit_step():
    """沒有先例把環境變數橋接進 infra.proxy → 不使用 PROXY_URL 等任何其他 secret（#961 稽核第 1 項）。
    #961 修正輪：改為整份文字掃描（YAML 解析看不到註解與頂層 env 以外的寫法）。"""
    assert _secret_violations(_WF.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("label,inject", [
    ("頂層 env", "env:\n  X: ${{ secrets.PROXY_URL }}\n"),
    ("github.token", "# 註解也算\nenv:\n  T: ${{ github.token }}\n"),
    ("中括號取 secret", "env:\n  X: ${{ secrets['PROXY_URL'] }}\n"),
    ("toJSON(secrets)", "env:\n  ALL: ${{ toJSON(secrets) }}\n"),
])
def test_secret_scan_catches_audit_variants(label, inject):
    base = _WF.read_text(encoding="utf-8")
    bad = base.replace("\njobs:\n", "\n" + inject + "jobs:\n", 1)
    assert bad != base
    assert _secret_violations(bad), f"{label} 應被擋下"


def test_secret_scan_catches_second_github_token_elsewhere():
    base = _WF.read_text(encoding="utf-8")
    bad = base.replace("      - name: Run probe\n",
                       "      - name: Run probe\n        env:\n          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}\n", 1)
    assert bad != base and _secret_violations(bad)


# ═════════════════════════════════════════════════════════════════════
# 第二部分：探測腳本
# ═════════════════════════════════════════════════════════════════════

_SCRIPT = _ROOT / "scripts" / "probe_moneydj_basic_page.py"
_spec = importlib.util.spec_from_file_location("probe_moneydj_basic_page", _SCRIPT)
probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probe)

_CODE = "JFZN3"
_CODE2 = "TLZF9"
_NEG = probe.make_negative_control(4242)


def _page(table_rows: str, outside: str = "", title: str = "基本資料") -> str:
    return (f"<html><head><title>{title}</title></head><body><div>{outside}</div>"
            f"<table>{table_rows}</table></body></html>")


_ROWS_WITH_CODE = ("<tr><td>基金名稱</td><td>測試環球基金A</td></tr>"
                   f"<tr><td>基金代碼</td><td>{_CODE}</td></tr>"
                   "<tr><td>計價幣別</td><td>美元</td><td>配息頻率</td><td>月配</td></tr>"
                   "<tr><td>成立日期</td><td>2001/02/03</td></tr>"
                   "<tr><td>最高經理費(%)</td><td>1.5</td></tr>")
_ROWS_NO_CODE = ("<tr><td>基金名稱</td><td>另一檔基金</td></tr>"
                 "<tr><td>計價幣別</td><td>歐元</td></tr>")


class _Resp:
    def __init__(self, html: str, url: str = "https://www.moneydj.com/x", status: int = 200):
        self.content = html.encode("big5", errors="replace")
        self.text = html
        self.url = url
        self.status_code = status
        self.history = []
        self.headers = {"Content-Type": "text/html"}
        self.encoding = "big5"


class _BadTextResp(_Resp):
    @property
    def text(self):
        raise UnicodeDecodeError("big5", b"\xff", 0, 1, "壞位元組")

    @text.setter
    def text(self, v):
        pass


# ── 解析：表自身文字與候選表 ─────────────────────────────────────────

def test_analyze_表內有代碼_兩版綁定皆成立_最高經理費不讀():
    out = probe.analyze_html(_page(_ROWS_WITH_CODE), _CODE)
    assert out["fields"] == {"基金名稱": "測試環球基金A", "計價幣別": "美元",
                             "配息頻率": "月配", "成立日期": "2001/02/03"}
    nt = out["name_table"]
    assert nt["index"] == 0 and nt["consistent_with_whole_page_parse"] is True
    assert nt["mentions_own"] is True and nt["mentions_incl_nested"] is True
    assert out["would_be_ok_now"] is True
    assert out["would_be_ok_with_table_binding_own"] is True
    assert out["would_be_ok_with_table_binding_incl_nested"] is True
    assert out["title_tag_html"] == "<title>基本資料</title>"


def test_analyze_代碼只在表外_現行判ok但綁定不成立():
    out = probe.analyze_html(_page(_ROWS_NO_CODE, outside=f"相關基金 {_CODE}"), _CODE)
    assert out["page_text_mentions_code"] is True and out["would_be_ok_now"] is True
    assert out["would_be_ok_with_table_binding_own"] is False
    assert out["would_be_ok_with_table_binding_incl_nested"] is False


def test_analyze_詞界_長代碼不算提到短代碼():
    out = probe.analyze_html(_page(_ROWS_NO_CODE, outside=_CODE + "0"), _CODE)
    assert out["page_text_mentions_code"] is False


@pytest.mark.parametrize("where", ["th", "caption"])
def test_自身文字含th與caption(where):
    extra = (f"<caption>代碼 {_CODE}</caption>" if where == "caption"
             else f"<tr><th>代碼 {_CODE}</th></tr>")
    html = ("<html><body><table>" + extra + _ROWS_NO_CODE + "</table></body></html>")
    nt = probe.analyze_html(html, _CODE)["name_table"]
    assert nt["mentions_own"] is True and nt["mentions_incl_nested"] is True
    assert nt["own_text_is_subset"] is True


@pytest.mark.parametrize("hidden", [f"<!-- {_CODE} -->", f"<script>var c='{_CODE}';</script>"])
def test_自身文字不含註解與script(hidden):
    html = _page(_ROWS_NO_CODE.replace("另一檔基金", "另一檔基金" + hidden))
    out = probe.analyze_html(html, _CODE)
    assert out["name_table"]["mentions_own"] is False
    assert out["name_table"]["mentions_incl_nested"] is False
    assert out["would_be_ok_with_table_binding_own"] is False


def test_代碼只在巢狀表_自身版不成立_含巢狀版成立():
    html = _page("<tr><td>基金名稱</td><td>甲基金</td></tr>"
                 f"<tr><td>附註</td><td><table><tr><td>{_CODE}</td></tr></table></td></tr>")
    out = probe.analyze_html(html, _CODE)
    nt = out["name_table"]
    assert nt["contains_nested_table"] is True
    assert nt["mentions_incl_nested"] is True and nt["mentions_own"] is False
    assert nt["own_text_is_subset"] is True
    assert out["would_be_ok_with_table_binding_own"] is False
    assert out["would_be_ok_with_table_binding_incl_nested"] is True


def test_巢狀表_選內層且與整頁解析一致():
    inner = f"<table>{_ROWS_NO_CODE}</table>"
    html = ("<html><body><table><tr><td>" + inner + "</td></tr></table>"
            "<table><tr><td>外表無關</td></tr></table></body></html>")
    nt = probe.analyze_html(html, _CODE)["name_table"]
    assert nt["index"] == 1 and nt["nested_in_table"] is True
    assert nt["consistent_with_whole_page_parse"] is True


def test_候選表計數_且取第一張而非最後一張():
    """兩張含「基金名稱」的表：第一張沒有代碼、第二張有。正式函式取第一張 → 綁定不成立。
    （突變「取最後一張表」會讓本測試轉紅。）"""
    html = ("<html><body>" + f"<table>{_ROWS_NO_CODE}</table>" + f"<table>{_ROWS_WITH_CODE}</table>"
            + "</body></html>")
    out = probe.analyze_html(html, _CODE)
    assert out["name_table_candidate_count"] == 2
    assert [c["mentions_own"] for c in out["name_table_candidates"]] == [False, True]
    assert out["name_table"]["index"] == 0
    assert out["name_table"]["fields"]["基金名稱"] == "另一檔基金" == out["fields"]["基金名稱"]
    assert out["would_be_ok_with_table_binding_own"] is False


def test_沒有基金名稱表():
    out = probe.analyze_html("<html><body>系統維護中 基金 淨值</body></html>", _CODE)
    assert out["fields"] is None and out["name_table"] is None and out["name_table_candidate_count"] == 0
    assert out["would_be_ok_now"] is False and out["would_be_ok_with_table_binding_own"] is False


# ── 負控與順序 ─────────────────────────────────────────────────────

def test_負控規則_由執行期生成且符合正式代碼形狀():
    from repositories.fund import declared_profile as dp
    assert _NEG == "NX" + format(4242, "X")
    assert dp._CODE_RE.match(_NEG)
    assert _NEG not in probe.PROBE_CODES


def test_負控排第二():
    assert probe.order_codes(["A1", "B2", "C3"], _NEG) == ["A1", _NEG, "B2", "C3"]
    assert probe.order_codes([], _NEG) == [_NEG]


# ── run：假網路、假時鐘 ─────────────────────────────────────────────

def _urls(code):
    return [(h, p, f"https://{h}/funddj/yp/{p}.djhtm?a={code}")
            for p in ("yp011001", "yp011000") for h in ("tcb", "www")]


class _World:
    """假網路＋假時鐘＋假退避：`cool[host] = (到期時刻, 分類)`。"""

    def __init__(self, fetch_map=None, cool=None, raise_on=()):
        self.t = 0.0
        self.fetch_map = fetch_map or {}
        self.cool = dict(cool or {})
        self.raise_on = set(raise_on)
        self.calls, self.sleeps = [], []
        self.kind = ""

    def clock(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s

    def backoff(self, url):
        host = probe._host(url)
        until, kind = self.cool.get(host, (0.0, ""))
        return (self.t < until, max(0.0, until - self.t), kind if self.t < until else "")

    def fetch(self, url, timeout, retries):
        self.calls.append((url, timeout, retries))
        if url in self.raise_on:
            raise RuntimeError("連線炸了 " + url)
        v = self.fetch_map.get(url)
        if isinstance(v, tuple):          # (None, 分類, 印出的 log)
            print(v[2])
            self.kind = v[1]
            return None
        self.kind = ""
        return v

    def pop(self):
        k, self.kind = self.kind, ""
        return k


def _run(world, *, codes=(_CODE,), public_specs=(), tdcc=None, on_progress=None, budget=1800):
    return probe.run(list(codes), url_builder=_urls, fetcher=world.fetch, pop_fail_kind=world.pop,
                     backoff_check=world.backoff, public_specs=list(public_specs),
                     tdcc_list_getter=lambda: tdcc, backoff_state_getter=lambda: [],
                     sleep_fn=world.sleep, clock=world.clock, wait_budget_sec=budget,
                     negative_control=_NEG, on_progress=on_progress)


def test_run_先廣後深_負控第二():
    w = _World()
    _run(w, codes=(_CODE, _CODE2))
    got = [c[0] for c in w.calls]
    first = [u for c in (_CODE, _NEG, _CODE2) for (_h, p, u) in _urls(c) if p == "yp011001"]
    second = [u for c in (_CODE, _NEG, _CODE2) for (_h, p, u) in _urls(c) if p == "yp011000"]
    assert got == first + second
    assert all(c[1:] == (20, 1) for c in w.calls)


def test_run_逐網址記錄_成功失敗例外皆照錄():
    u = {(h, p): url for h, p, url in _urls(_CODE)}
    html = _page(_ROWS_WITH_CODE)
    w = _World(fetch_map={u[("tcb", "yp011001")]: (None, "not_found",
                                                   "[proxy] 全部嘗試失敗（last_seen_status=404, perr=0）：x"),
                          u[("www", "yp011001")]: _Resp(html, url="https://www.moneydj.com/final"),
                          u[("www", "yp011000")]: _BadTextResp(html)},
               raise_on={u[("tcb", "yp011000")]})
    report = _run(w)
    recs = {(r["host"], r["page_type"]): r for r in report["pages"][_CODE]}
    r404 = recs[("tcb", "yp011001")]
    assert r404["outcome"] == "http_failed" and r404["http_status"] == 404
    assert r404["http_status_source"] == "fetch_log:last_seen_status" and r404["fail_kind"] == "not_found"
    ok = recs[("www", "yp011001")]
    assert ok["outcome"] == "fetched" and ok["http_status"] == 200
    assert ok["final_url"] == "https://www.moneydj.com/final" and ok["round"] == 1
    raw = gzip.decompress(base64.b64decode(ok["raw_html_gzip_b64"]))
    assert raw == html.encode("big5", errors="replace") and ok["content_length_bytes"] == len(raw)
    boom = recs[("tcb", "yp011000")]
    assert boom["outcome"] == "exception" and boom["error"]["type"] == "RuntimeError"
    bad = recs[("www", "yp011000")]
    assert bad["outcome"] == "exception" and bad["error"]["type"] == "UnicodeDecodeError"
    assert report["summary"]["fetched_page_count_real"] == 1
    assert report["negative_control"]["code"] == _NEG and report["complete"] is True
    assert "runner IP 直連" in report["network_path"]


def test_run_可等的冷卻_等到期後續取_並記錄():
    w = _World(cool={"tcb": (100.0, "unreachable")})
    report = _run(w)
    tcb = [r for r in report["pages"][_CODE] if r["host"] == "tcb"]
    assert [r["outcome"] for r in tcb] == ["empty_response", "empty_response"]
    waited = [x for x in report["waits"] if x["waited_sec"] is not None]
    assert len(waited) == 1 and waited[0]["host"] == "tcb" and waited[0]["kind"] == "unreachable"
    assert waited[0]["after"]["still_cooling"] is False
    assert waited[0]["waited_sec"] == pytest.approx(100.0 + probe.WAIT_PAD_SEC)


def test_run_blocked不等_每主機只等一次_超預算不等():
    w = _World(cool={"tcb": (10_000.0, "blocked")})
    report = _run(w)
    assert all(r["outcome"] == "cooldown" for r in report["pages"][_CODE] if r["host"] == "tcb")
    assert all(x["waited_sec"] is None and "blocked" in x["skip_reason"] for x in report["waits"])
    assert not any(c[0].startswith("https://tcb/") for c in w.calls)

    w2 = _World(cool={"tcb": (5_000.0, "server_error")})
    r2 = _run(w2, budget=60)
    assert all(x["waited_sec"] is None and x["skip_reason"] == "超過等待預算" for x in r2["waits"])


def test_run_同一主機第二次冷卻不再等():
    w = _World()

    def fetch(url, timeout, retries):
        w.calls.append((url, timeout, retries))
        if url.startswith("https://tcb/"):     # 每次失敗都讓 tcb 再冷卻 50 秒
            w.cool["tcb"] = (w.t + 50.0, "unreachable")
        return None

    w.fetch = fetch
    report = _run(w)
    tcb_waits = [x for x in report["waits"] if x["host"] == "tcb"]
    assert [x["waited_sec"] is not None for x in tcb_waits][:1] == [True]
    assert any(x["skip_reason"] == "此主機已等過一次" for x in tcb_waits)


def test_run_只在確實發請求前sleep():
    w = _World(cool={"tcb": (10_000.0, "blocked"), "www": (10_000.0, "blocked")})
    _run(w)
    assert w.calls == [] and w.sleeps == []
    w2 = _World()
    _run(w2)
    assert len(w2.calls) == 8 and w2.sleeps == [probe.SLEEP_SEC] * 7


def test_預設公開呼叫不含moneydj():
    from repositories.fund import declared_profile as dp
    names = [s[0] for s in probe._default_public_specs(dp)]
    assert names == ["fetch_tdcc_listing", "fetch_fundclear_declared_ccy"]


def test_run_公開函式_例外不中止_不發請求時不sleep():
    def boom(code):
        raise ValueError("壞了")
    specs = [("fetch_tdcc_listing", lambda c: {"status": "not_listed"}, lambda c: "https://tdcc/x",
              lambda c: False),
             ("fetch_fundclear_declared_ccy", boom, lambda c: f"https://fc/x?FundCode={c}", lambda c: True)]
    w = _World(cool={"tcb": (10_000.0, "blocked"), "www": (10_000.0, "blocked")})
    report = _run(w, public_specs=specs)
    pc = report["public_calls"][_CODE]
    assert pc["fetch_fundclear_declared_ccy"]["exception"]["type"] == "ValueError"
    assert pc["fetch_tdcc_listing"]["result"] == {"status": "not_listed"}
    # 頁面全冷卻 → 第一個真正發請求的是 FundClear（不 sleep），負控的 FundClear 前 sleep 一次
    assert w.sleeps == [probe.SLEEP_SEC]
    assert report["summary"]["per_code"][_CODE]["public_status"] == {
        "fetch_tdcc_listing": "not_listed", "fetch_fundclear_declared_ccy": "exception"}


# ── TDCC ───────────────────────────────────────────────────────────

def test_tdcc_比中規則與正式函式相同_只看第一個非空代碼欄():
    from repositories.fund import declared_profile as dp
    data = [{"基金代碼": _CODE, "基金名稱": "甲", "計價幣別": "美元"},
            {"基金代碼": "OTHER1", "境外基金代碼": _CODE, "基金名稱": "乙"},
            {"基金代碼": "", "境外基金代碼": _CODE.lower(), "基金名稱": "丙"},
            {"基金名稱": f"丁 {_CODE} 相關"},
            "不是 dict"]
    ext = probe.tdcc_listing_extract(data, [_CODE], code_keys=tuple(dp._TDCC_CODE_KEYS))
    assert ext["total_rows"] == 5 and ext["dict_rows"] == 4 and ext["non_dict_rows"] == 1
    got = [(m["code_key"], m["row"]["基金名稱"]) for m in ext["rows_matching_like_declared_profile"][_CODE]]
    assert got == [("基金代碼", "甲"), ("境外基金代碼", "丙")]
    assert ext["rows_mentioning_code_any_field"][_CODE]["count"] == 4
    full = ext["full_listing"]
    assert full["form"] == "full_json_gzip_b64"
    assert json.loads(gzip.decompress(base64.b64decode(full["data"]))) == data


def test_tdcc_太大改存精簡版_空快取寫明出處():
    data = [{"基金代碼": f"C{i}", "基金名稱": f"名{i}", "計價幣別": "美元", "備註": "x" * 50} for i in range(50)]
    ext = probe.tdcc_listing_extract(data, [_CODE], full_max_b64=10)
    full = ext["full_listing"]
    assert full["form"] == "slim_code_and_name_gzip_b64"
    slim = json.loads(gzip.decompress(base64.b64decode(full["data"])))
    assert slim[0] == {"基金代碼": "C0", "境外基金代碼": None, "基金名稱": "名0"}
    none = probe.tdcc_listing_extract(None, [_CODE])
    assert none["available"] is False and "public_calls" in none["note"]


# ── main：退出碼、嚴格 JSON、逐步寫出 ──────────────────────────────

def _main_kwargs(world, **over):
    kw = dict(url_builder=_urls, fetcher=world.fetch, pop_fail_kind=world.pop, backoff_check=world.backoff,
              public_specs=[], tdcc_list_getter=lambda: None, backoff_state_getter=lambda: [],
              sleep_fn=world.sleep, clock=world.clock, negative_control=_NEG)
    kw.update(over)
    return kw


def test_main_嚴格JSON_無樣本時退出碼1(tmp_path):
    out = tmp_path / "r.json"
    w = _World()
    specs = [("f", lambda c: {"status": "failed", "x": float("nan")}, lambda c: "https://f/x", lambda c: False)]
    rc = probe.main(["--out", str(out)], **_main_kwargs(w, public_specs=specs))
    assert rc == 1
    text = out.read_text(encoding="utf-8")
    data = json.loads(text)
    assert "NaN" not in text and data["complete"] is True
    assert data["public_calls"][probe.PROBE_CODES[0]]["f"]["result"]["x"] is None


def test_main_只有負控取到頁面時退出碼1(tmp_path):
    out = tmp_path / "r.json"
    html = _page(_ROWS_NO_CODE)
    w = _World(fetch_map={u: _Resp(html) for (_h, _p, u) in _urls(_NEG)})
    rc = probe.main(["--out", str(out)], **_main_kwargs(w))
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["summary"]["fetched_page_count_negative_control"] == 4
    assert data["summary"]["fetched_page_count_real"] == 0 and rc == 1


def test_main_實際代碼有樣本時退出碼0(tmp_path):
    out = tmp_path / "r.json"
    html = _page(_ROWS_WITH_CODE)
    w = _World(fetch_map={u: _Resp(html) for (_h, _p, u) in _urls(probe.PROBE_CODES[0])})
    assert probe.main(["--out", str(out)], **_main_kwargs(w)) == 0


def test_main_寫不出嚴格JSON時保底寬鬆寫出並標記(tmp_path):
    out = tmp_path / "r.json"
    w = _World()
    specs = [("f", lambda c: {"status": "ok", "bad": {float("nan"): 1}}, lambda c: "https://f/x", lambda c: False)]
    assert probe.main(["--out", str(out)], **_main_kwargs(w, public_specs=specs)) == 1
    assert "strict_json_error" in out.read_text(encoding="utf-8")


def test_main_逐步寫出_中途就有未完成版報告(tmp_path):
    """第二個代碼開始取數時，報告檔必須已經存在且 complete=false（突變「拿掉逐步寫出」會轉紅）。"""
    out = tmp_path / "r.json"
    w = _World()
    seen = []
    second = probe.order_codes(probe.PROBE_CODES, _NEG)[1]

    def fetch(url, timeout, retries):
        if url.endswith("=" + second) and not seen:
            seen.append(json.loads(out.read_text(encoding="utf-8")) if out.exists() else None)
        return None

    probe.main(["--out", str(out)], **_main_kwargs(w, fetcher=fetch))
    assert seen and seen[0] is not None, "第二個代碼開始前報告檔應已寫出"
    assert seen[0]["complete"] is False and seen[0]["pages"][probe.PROBE_CODES[0]]
    assert json.loads(out.read_text(encoding="utf-8"))["complete"] is True


def test_mask_遮蔽代理帳密_查詢字串保留(monkeypatch):
    monkeypatch.setenv("PROXY_URL", "http://user:secretpw@nas.example:3128")
    secrets = probe._secret_literals()
    masked = probe.mask_text(f"ProxyError http://user:secretpw@nas.example:3128 ?a={_CODE}", secrets)
    assert "secretpw" not in masked and f"?a={_CODE}" in masked


def test_run_等待後重查仍在冷卻_記cooldown且不發請求():
    """等完冷卻後重查仍在冷卻（例如冷卻被延長）→ 記 cooldown、不發請求（#961 修正輪：稽核突變 W1）。"""
    w = _World()

    def backoff(url):
        if probe._host(url) == "tcb":
            return True, 10.0, "unreachable"     # 永遠還剩 10 秒
        return False, 0.0, ""

    w.backoff = backoff
    report = _run(w)
    tcb = [r for r in report["pages"][_CODE] if r["host"] == "tcb"]
    assert tcb and all(r["outcome"] == "cooldown" for r in tcb)
    assert not any(c[0].startswith("https://tcb/") for c in w.calls)
    waited = [x for x in report["waits"] if x["waited_sec"] is not None]
    assert len(waited) == 1 and waited[0]["after"]["still_cooling"] is True


def test_write_report_原子寫出_中途失敗不毀舊檔(tmp_path, monkeypatch):
    """先寫 .tmp 再 os.replace：寫到一半失敗時，既有報告檔保持原樣（#961 修正輪：稽核突變 X6）。"""
    out = tmp_path / "r.json"
    out.write_text('{"old": true}\n', encoding="utf-8")
    real = Path.write_text

    def half_then_fail(self, data, *a, **k):
        real(self, data[: len(data) // 2], *a, **k)
        raise OSError("磁碟寫到一半壞了")

    monkeypatch.setattr(Path, "write_text", half_then_fail)
    with pytest.raises(OSError):
        probe.write_report({"complete": False, "x": "y" * 1000}, out)
    monkeypatch.setattr(Path, "write_text", real)
    assert json.loads(out.read_text(encoding="utf-8")) == {"old": True}
    probe.write_report({"complete": True}, out)
    assert json.loads(out.read_text(encoding="utf-8")) == {"complete": True}
    assert not (tmp_path / "r.json.tmp").exists()


def test_raw_html_超過上限截斷並標記(monkeypatch):
    monkeypatch.setattr(probe, "MAX_RAW_BYTES", 100)
    html = _page(_ROWS_WITH_CODE + "<tr><td>x</td></tr>" * 50)
    w = _World(fetch_map={u: _Resp(html) for (_h, _p, u) in _urls(_CODE)})
    rec = _run(w)["pages"][_CODE][0]
    assert rec["raw_truncated"] is True
    assert len(gzip.decompress(base64.b64decode(rec["raw_html_gzip_b64"]))) == 100
    assert rec["content_length_bytes"] > 100


def test_raw_html_上限為1MB():
    assert probe.MAX_RAW_BYTES == 1_000_000
