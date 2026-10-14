"""tests/test_moneydj_basic_probe.py — `scripts/probe_moneydj_basic_page.py` 與其 workflow 的守衛（不打網路）。

## 第一部分：workflow 形狀（比照 `tests/test_fx_obs_date_probe_workflow.py`，判準逐條照抄、只換常數）

`.github/workflows/moneydj_basic_probe.yml` 帶 `contents: write`，push 到按鈕分支
`probe/moneydj-basic-trigger` 觸發。這條觸發只能當「按鈕」：

1. `on.push.branches` 只有按鈕分支；`workflow_dispatch` 保留；無排程、無 pull_request。
2. 恰好一個 `actions/checkout`，`ref: main`、`persist-credentials: false`。
3. step 的 `run`／`with`／`env` 與 job `env` 不得引用觸發端的 ref／SHA。
4. 探測步驟之前不得有取碼的 git 子指令；之後只能針對 `$RESULT_BRANCH`。
5. 推送指令恰好一行，`origin`、無旗標、refspec 恰為 `HEAD:refs/heads/$RESULT_BRANCH`。

另加本 workflow 專屬的三條：沒有 dispatch 輸入參數（代碼寫在腳本裡，不吃使用者輸入）、
有 `timeout-minutes`、提交報告那一步 `if: always()` 且報告路徑含時間戳與 run id。

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


# ═════════════════════════════════════════════════════════════════════
# 第二部分：探測腳本
# ═════════════════════════════════════════════════════════════════════

_SCRIPT = _ROOT / "scripts" / "probe_moneydj_basic_page.py"
_spec = importlib.util.spec_from_file_location("probe_moneydj_basic_page", _SCRIPT)
probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probe)

_CODE = "JFZN3"
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


def test_analyze_表內有代碼_綁定成立_最高經理費不讀():
    out = probe.analyze_html(_page(_ROWS_WITH_CODE), _CODE)
    assert out["fields"] == {"基金名稱": "測試環球基金A", "計價幣別": "美元",
                             "配息頻率": "月配", "成立日期": "2001/02/03"}
    nt = out["name_table"]
    assert nt["index"] == 0 and nt["consistent_with_whole_page_parse"] is True
    assert nt["table_text_mentions_code"] is True and nt["own_rows_text_mentions_code"] is True
    assert nt["probe_codes_mentioned"] == [_CODE]
    assert out["would_be_ok_now"] is True and out["would_be_ok_with_table_binding"] is True
    assert out["title_tag_html"] == "<title>基本資料</title>"


def test_analyze_代碼只在表外_現行判ok但綁定規則不成立():
    out = probe.analyze_html(_page(_ROWS_NO_CODE, outside=f"相關基金 {_CODE}"), _CODE)
    assert out["page_text_mentions_code"] is True
    assert out["name_table"]["table_text_mentions_code"] is False
    assert out["would_be_ok_now"] is True
    assert out["would_be_ok_with_table_binding"] is False
    assert out["page_text_code_snippets"] and _CODE in out["page_text_code_snippets"][0]


def test_analyze_詞界_長代碼不算提到短代碼():
    out = probe.analyze_html(_page(_ROWS_NO_CODE, outside=_CODE + "0"), _CODE)
    assert out["page_text_mentions_code"] is False


def test_analyze_巢狀表_選內層且與整頁解析一致():
    inner = f"<table>{_ROWS_NO_CODE}</table>"
    html = ("<html><body><table><tr><td>" + inner + "</td></tr></table>"
            "<table><tr><td>外表無關</td></tr></table></body></html>")
    nt = probe.analyze_html(html, _CODE)["name_table"]
    assert nt["index"] == 1 and nt["nested_in_table"] is True
    assert nt["consistent_with_whole_page_parse"] is True


def test_analyze_自身列不含巢狀表文字():
    html = _page("<tr><td>基金名稱</td><td>甲基金</td></tr>"
                 f"<tr><td>附註</td><td><table><tr><td>{_CODE}</td></tr></table></td></tr>")
    nt = probe.analyze_html(html, _CODE)["name_table"]
    assert nt["contains_nested_table"] is True
    assert nt["table_text_mentions_code"] is True
    assert nt["own_rows_text_mentions_code"] is False


def test_analyze_沒有基金名稱表():
    out = probe.analyze_html("<html><body>系統維護中 基金 淨值</body></html>", _CODE)
    assert out["fields"] is None and out["name_table"] is None
    assert out["would_be_ok_now"] is False and out["would_be_ok_with_table_binding"] is False


def test_負控規則_由執行期生成且符合正式代碼形狀():
    from repositories.fund import declared_profile as dp
    assert _NEG == "NX" + format(4242, "X")
    assert dp._CODE_RE.match(_NEG)
    assert _NEG not in probe.PROBE_CODES


def _urls(code):
    return [(h, p, f"https://{h}/funddj/yp/{p}.djhtm?a={code}")
            for p in ("yp011001", "yp011000") for h in ("tcb", "www")]


def _run(fetch_map, *, cool=(), public_fns=None, tdcc=None, sleeps=None, raise_on=()):
    calls = []
    state = {"kind": ""}

    def fetcher(url, timeout, retries):
        calls.append((url, timeout, retries))
        if url in raise_on:
            raise RuntimeError("連線炸了 " + url)
        v = fetch_map.get(url)
        if isinstance(v, tuple):          # (None, 分類, 印出的 log)
            print(v[2])
            state["kind"] = v[1]
            return None
        state["kind"] = ""
        return v

    def pop():
        k, state["kind"] = state["kind"], ""
        return k

    report = probe.run(
        [_CODE], url_builder=_urls, fetcher=fetcher, pop_fail_kind=pop,
        backoff_check=lambda u: (u in cool, "blocked" if u in cool else ""),
        public_fns=public_fns if public_fns is not None else {"f": lambda c: {"status": "failed", "code": c}},
        tdcc_list_getter=lambda: tdcc, backoff_state_getter=lambda: [],
        sleep_fn=(sleeps.append if sleeps is not None else (lambda s: None)),
        negative_control=_NEG)
    return report, calls


def test_run_逐網址記錄_成功失敗冷卻例外皆照錄():
    u = [x[2] for x in _urls(_CODE)]
    html = _page(_ROWS_WITH_CODE)
    fmap = {u[0]: (None, "not_found", "[proxy] 全部嘗試失敗（last_seen_status=404, perr=0, block=0, tmo=0）：x"),
            u[1]: _Resp(html, url="https://www.moneydj.com/final")}
    report, calls = _run(fmap, cool={u[2]}, raise_on={u[3]})
    recs = report["pages"][_CODE]
    assert [r["outcome"] for r in recs] == ["http_failed", "fetched", "cooldown", "exception"]
    assert recs[0]["http_status"] == 404 and recs[0]["http_status_source"] == "fetch_log:last_seen_status"
    assert recs[0]["fail_kind"] == "not_found" and recs[0]["fetch_log"]
    assert recs[1]["http_status"] == 200 and recs[1]["final_url"] == "https://www.moneydj.com/final"
    assert recs[1]["parse"]["would_be_ok_with_table_binding"] is True
    raw = gzip.decompress(base64.b64decode(recs[1]["raw_html_gzip_b64"]))
    assert raw == html.encode("big5", errors="replace")
    assert recs[1]["content_length_bytes"] == len(raw)
    assert recs[2]["cooldown_origin_kind"] == "blocked"
    assert recs[3]["error"]["type"] == "RuntimeError" and "連線炸了" in recs[3]["error"]["message"]
    # 冷卻中的網址不發請求；呼叫參數照 declared_profile（timeout=20, retries=1）
    assert u[2] not in [c[0] for c in calls]
    assert all(c[1:] == (20, 1) for c in calls)
    # 負控同樣探測，且記錄生成規則
    assert _NEG in report["pages"]
    assert report["negative_control"] == {"code": _NEG, "rule": probe.NEGATIVE_CONTROL_RULE}


def test_run_只在真的發請求前sleep_冷卻不sleep():
    sleeps = []
    cool = {x[2] for c in (_CODE, _NEG) for x in _urls(c)}
    report, calls = _run({}, cool=cool, public_fns={}, sleeps=sleeps)
    assert calls == [] and sleeps == []


def test_run_第一個請求不sleep_之後每個請求前sleep():
    sleeps = []
    report, calls = _run({}, public_fns={}, sleeps=sleeps)
    assert len(calls) == 8 and sleeps == [probe.SLEEP_SEC] * 7


def test_run_公開函式例外不中止():
    def boom(code):
        raise ValueError("壞了")
    report, _ = _run({}, public_fns={"fetch_moneydj_basic_fields": boom,
                                     "fetch_tdcc_listing": lambda c: {"status": "not_listed"}})
    pc = report["public_calls"][_CODE]
    assert pc["fetch_moneydj_basic_fields"]["exception"]["type"] == "ValueError"
    assert pc["fetch_tdcc_listing"]["result"] == {"status": "not_listed"}
    assert report["summary"][_CODE]["public_status"] == {
        "fetch_moneydj_basic_fields": "exception", "fetch_tdcc_listing": "not_listed"}


def test_tdcc_只存相關列_欄名與總筆數():
    data = [{"基金代碼": _CODE, "基金名稱": "甲", "計價幣別": "美元"},
            {"境外基金代碼": "XX1", "基金名稱": f"乙 {_CODE} 相關", "計價幣別": "歐元"},
            {"基金代碼": "ZZ9", "基金名稱": "丙", "其他": None},
            "不是 dict"]
    ext = probe.tdcc_listing_extract(data, [_CODE])
    assert ext["total_rows"] == 4 and ext["dict_rows"] == 3 and ext["non_dict_rows"] == 1
    assert ext["columns"] == sorted({"基金代碼", "境外基金代碼", "基金名稱", "計價幣別", "其他"})
    assert ext["rows_matching_code_keys"][_CODE] == [data[0]]
    assert ext["rows_mentioning_code_any_field"][_CODE]["count"] == 2
    assert probe.tdcc_listing_extract(None, [_CODE])["available"] is False


def _main_kwargs(**over):
    kw = dict(url_builder=lambda c: [], fetcher=lambda *a, **k: None, pop_fail_kind=lambda: "",
              backoff_check=lambda u: (False, ""), public_fns={},
              tdcc_list_getter=lambda: None, backoff_state_getter=lambda: [],
              sleep_fn=lambda s: None, negative_control=_NEG)
    kw.update(over)
    return kw


def test_main_嚴格JSON_且無樣本時退出碼1(tmp_path):
    out = tmp_path / "r.json"
    rc = probe.main(["--out", str(out)], **_main_kwargs(
        public_fns={"f": lambda c: {"status": "failed", "x": float("nan")}}))
    assert rc == 1
    text = out.read_text(encoding="utf-8")
    data = json.loads(text)
    assert "NaN" not in text
    assert data["public_calls"][probe.PROBE_CODES[0]]["f"]["result"]["x"] is None
    assert data["negative_control"]["rule"] == probe.NEGATIVE_CONTROL_RULE


def test_main_有樣本時退出碼0(tmp_path):
    out = tmp_path / "r.json"
    html = _page(_ROWS_WITH_CODE)
    rc = probe.main(["--out", str(out)], **_main_kwargs(
        url_builder=lambda c: [("www", "yp011001", f"https://www/x?a={c}")],
        fetcher=lambda url, timeout, retries: _Resp(html)))
    assert rc == 0
    n_codes = len(probe.PROBE_CODES) + 1
    assert json.loads(out.read_text(encoding="utf-8"))["summary"]["fetched_page_count"] == n_codes


def test_main_寫不出嚴格JSON時保底寬鬆寫出並標記(tmp_path):
    out = tmp_path / "r.json"
    rc = probe.main(["--out", str(out)], **_main_kwargs(
        public_fns={"f": lambda c: {"status": "ok", "bad": {float("nan"): 1}}}))
    assert rc == 1
    assert "strict_json_error" in out.read_text(encoding="utf-8")


def test_mask_遮蔽代理帳密_查詢字串保留(monkeypatch):
    monkeypatch.setenv("PROXY_URL", "http://user:secretpw@nas.example:3128")
    secrets = probe._secret_literals()
    masked = probe.mask_text(f"ProxyError http://user:secretpw@nas.example:3128 ?a={_CODE}", secrets)
    assert "secretpw" not in masked and f"?a={_CODE}" in masked
