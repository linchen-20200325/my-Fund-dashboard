"""CI 守衛:**push 到 main 的 run 不得被後續 push 取消**(2026-09-07)

## 這個檔案在守什麼(為什麼會有這一組測試)

`.github/workflows/pr-check.yml` 的 concurrency group 原本是
`pr-check-${{ github.ref }}` 配 `cancel-in-progress: true`。
**push 事件的 `github.ref` 恆為 `refs/heads/main`** —— 於是**連續兩次合併會落在同一組**,
後一次合併的 push 會**取消前一次尚未跑完的 main run**。

**實際發生過**(2026-09-07,可自驗):run `34107180350`(event=`push`、head_branch=`main`、
head_sha `d60910f` = #796 的 merge commit)的 **Fast checks 與 Slow tests 皆 `cancelled`**
(09:44:16Z),成因是 #800 的合併 push 在數秒前搶佔;Schema gate 因為已經跑完才是 `success`。

**為什麼這是缺口,不只是雜訊 ——**
1. 本 repo 的合併紀律硬性要求「**merge 完不算完**:回頭逐 job 驗 main 上那一次 CI run」。
   這個取消讓那一步**結構上跑不完**。
2. 若後續沒有再一次合併,那顆 merge commit 就是「**零完整 main 驗證**」,而且**沒有人會察覺**
   —— 沒有任何東西會報錯,取消本身就是靜默的。
3. run-level 顯示 `cancelled`,**長得很像失敗**:讀的人要嘛誤判為紅,要嘛養成
   「cancelled 沒關係」的習慣。**兩種都危險**(本 repo 紀律明寫 `cancelled` ≠ `success`)。

## 修法與本檔的守法

group 尾端補上**只在 push 事件生效**的 `github.sha` → 每顆 merge commit 自成一組;
PR 事件走固定字串,group 在同一個 PR 內維持穩定 → **新 push 取消舊 run 的省時行為保留**。

本檔**不做字面字串比對**(換個等價寫法就會失效,那種守衛只是把設定抄兩份)。
作法是**解析 YAML 取出 concurrency 運算式,再用一個小型 GitHub 運算式求值器,
在模擬的事件 context 下把它算出來**,然後斷言**行為**:

* **push**:同一條 `refs/heads/main`、兩顆不同 commit → group 必須**不同**
  (或 `cancel-in-progress` 對 push 求值為 false)。**兩種等價修法都放行。**
* **pull_request**:同一個 PR、兩次 push → group 必須**相同**,且 `cancel-in-progress` 為 true。

因此把修復改成**另一種等價寫法**(例如 `cancel-in-progress:` 依事件判斷、或改用
`github.event.pull_request.number || github.sha` 這個常見慣用法)**不會誤紅**;
只有**真的退化成「兩顆 merge commit 共用一組又會互相取消」才會紅**。

## ⚠️ 這條守衛守不到什麼(誠實列出,不要以為它守的比實際多)

1. **它不驗 GitHub 真的照它的文件行事。** 本檔求值的是 workflow 設定,
   不是 GitHub 的排程器;沒有任何一次真實 run 被本檔觀測過。
2. **它只認得求值器實作的那一小塊運算式文法**(字串常值、`github.*` context、
   `==` `!=` `!` `&&` `||`、括號)。用到 `format()` / `contains()` / `hashFiles()`
   等函式,或 `github` 以外的 context(`inputs.*`、`env.*`、`vars.*`)→
   **直接丟 `UnsupportedExpression` 紅燈**,不會靜默放行。**擴充語法時請連同本檔一起擴。**
3. **它只模擬 `push` / `pull_request` 兩種事件。** `workflow_dispatch` 與任何日後新增的
   事件**沒有被涵蓋**;`on:` 事件清單本身也不歸本檔管(只做前提檢查,見
   `test_premise_push_to_main_still_triggers_this_workflow`)。
4. **它守不到「pending run 被更新的 run 取代」這個洞。** GitHub 文件載明:即使
   `cancel-in-progress: false`,當同組又有新 run 排隊時,**先前 pending 的那個會被取消**。
   也就是說,若日後改採「`cancel-in-progress` 依事件判斷」那條路,**三次快速連續合併
   仍可能讓中間那顆 commit 拿不到完整 main 驗證** —— 本檔會判它合格(因為它確實滿足
   「push 不會取消進行中的 run」),**但那個洞還在**。現行修法(每顆 commit 自成一組)
   沒有這個洞,這也是選它的理由;**但本檔並不強制必須用現行修法**。
5. **它只看 workflow 層級的 `concurrency:`。** job 層級各自宣告 concurrency 會讓本檔的
   分析不完整 —— 故偵測到就**紅燈要求擴充**(見 `test_no_job_level_concurrency_blindspot`),
   而不是假裝沒看到。
6. **它不保證 run 會跑成功**,只保證「不會被下一次 push 取消」。lane 自己紅掉是另一回事。
7. **它不管其他 workflow 檔**。`.github/workflows/` 底下其餘檔案完全不在射程內。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = _ROOT / ".github" / "workflows" / "pr-check.yml"


# ══════════════════════════════════════════════════════════════════════
# 0. 載入 —— 缺 pyyaml 一律紅燈,不 skip
# ══════════════════════════════════════════════════════════════════════
def _load_workflow() -> dict:
    """解析 workflow YAML;**缺 pyyaml 一律紅燈,不 skip**。

    沿用 `tests/test_dividend_calendar_cron_v19537.py::_load_workflow_yaml` 的 v19.540
    先例:`pytest.importorskip` 會在缺套件時**靜默 skip**,而 skip 在 pytest 是綠燈 ——
    等於守衛在最需要它的環境裡自己關機。`pyyaml>=6.0` 已宣告於 `requirements-dev.txt`,
    缺了就是環境沒照 requirements 裝,那本來就該紅。
    """
    import yaml  # 刻意在函式內 import:缺套件 → 紅燈,不是 skip

    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.strip(), f"{WORKFLOW} 是空的 —— 下面所有『命中 0』的結論都會假成立"
    return yaml.safe_load(text)


# ══════════════════════════════════════════════════════════════════════
# 1. 極小的 GitHub 運算式求值器
#    —— 只認得本 workflow 用到的那一小塊文法,其餘一律 fail loud(§1)
# ══════════════════════════════════════════════════════════════════════
class UnsupportedExpression(Exception):
    """求值器看不懂的運算式。**刻意往紅燈倒** —— 看不懂就不准放行。"""


# `github` context 中本求值器**有模擬**的欄位。不在此表 → fail loud。
# (刻意用白名單:回傳 None 混過去會讓守衛在看不懂的設定上「靜默通過」。)
_MODELLED_GITHUB_FIELDS = frozenset(
    {
        "event_name", "ref", "ref_name", "ref_type", "sha", "run_id", "run_number",
        "run_attempt", "head_ref", "base_ref", "repository", "repository_owner",
        "workflow", "workflow_ref", "actor", "job", "event",
    }
)

_TOKEN_RE = re.compile(
    r"""\s*(?:
          (?P<str>'(?:[^']|'')*')
        | (?P<op>==|!=|&&|\|\||[()!])
        | (?P<num>-?\d+(?:\.\d+)?)
        | (?P<name>[A-Za-z_][A-Za-z0-9_\-]*(?:\.[A-Za-z_][A-Za-z0-9_\-]*)*)
    )""",
    re.VERBOSE,
)


def _tokenize(src: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    pos = 0
    while pos < len(src):
        if src[pos].isspace():
            pos += 1
            continue
        m = _TOKEN_RE.match(src, pos)
        if not m or m.end() == pos:
            raise UnsupportedExpression(f"無法解析的字元 {src[pos]!r} @{pos}:{src!r}")
        kind = m.lastgroup
        assert kind is not None
        out.append((kind, m.group(kind)))
        pos = m.end()
    return out


def _truthy(v) -> bool:
    """GitHub 的 falsy:`false` / `0` / `''` / `null`。其餘為 truthy。"""
    return not (v is None or v is False or v == "" or v == 0)


class _Parser:
    """遞迴下降;優先序 `||` < `&&` < 比較 < 一元 `!` < primary。"""

    def __init__(self, toks: list[tuple[str, str]], ctx: dict):
        self.toks, self.i, self.ctx = toks, 0, ctx

    def _peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else (None, None)

    def _eat(self, val):
        if self._peek()[1] == val:
            self.i += 1
            return True
        return False

    def parse(self):
        v = self._or()
        if self.i != len(self.toks):
            raise UnsupportedExpression(f"運算式尾端有解析不掉的殘餘:{self.toks[self.i:]!r}")
        return v

    def _or(self):
        left = self._and()
        while self._eat("||"):
            right = self._and()
            # GitHub:`a || b` → a 為 truthy 回 a,否則回 b(回的是**值**不是布林)
            left = left if _truthy(left) else right
        return left

    def _and(self):
        left = self._cmp()
        while self._eat("&&"):
            right = self._cmp()
            # GitHub:`a && b` → a 為 falsy 回 a,否則回 b
            left = right if _truthy(left) else left
        return left

    def _cmp(self):
        left = self._unary()
        while self._peek()[1] in ("==", "!="):
            op = self.toks[self.i][1]
            self.i += 1
            right = self._unary()
            eq = left == right
            left = eq if op == "==" else not eq
        return left

    def _unary(self):
        if self._eat("!"):
            return not _truthy(self._unary())
        return self._primary()

    def _primary(self):
        kind, val = self._peek()
        if val == "(":
            self.i += 1
            inner = self._or()
            if not self._eat(")"):
                raise UnsupportedExpression("括號沒有收掉")
            return inner
        self.i += 1
        if kind == "str":
            return val[1:-1].replace("''", "'")
        if kind == "num":
            return float(val) if "." in val else int(val)
        if kind == "name":
            low = val.lower()
            if low == "true":
                return True
            if low == "false":
                return False
            if low == "null":
                return None
            if self._peek()[1] == "(":
                raise UnsupportedExpression(
                    f"用到函式 {val}() —— 本求值器沒有實作,請連同本守衛一起擴充"
                )
            return self._lookup(val)
        raise UnsupportedExpression(f"看不懂的 token:{(kind, val)!r}")

    def _lookup(self, path: str):
        parts = path.split(".")
        if parts[0] != "github":
            raise UnsupportedExpression(
                f"用到未模擬的 context {parts[0]!r}(只模擬 github.*)—— 請連同本守衛一起擴充"
            )
        if len(parts) == 1:
            raise UnsupportedExpression("裸用 `github`,無法求值")
        if parts[1] not in _MODELLED_GITHUB_FIELDS:
            raise UnsupportedExpression(
                f"github.{parts[1]} 不在本求值器模擬的欄位內 —— 請連同本守衛一起擴充"
            )
        cur = self.ctx["github"].get(parts[1])
        # `github.event.*` 之下的 payload 逐事件而異:缺鍵回 null(同 GitHub 語意)。
        for p in parts[2:]:
            cur = cur.get(p) if isinstance(cur, dict) else None
        return cur


def _eval_expr(src: str, ctx: dict):
    return _Parser(_tokenize(src), ctx).parse()


_INTERP_RE = re.compile(r"\$\{\{(.*?)\}\}", re.DOTALL)


def _render(template, ctx: dict) -> str:
    """把帶 `${{ }}` 的設定值在給定 context 下算成字串。

    非字串(例如 `cancel-in-progress: true` 被 YAML 直接解析成 bool)原樣轉字串。
    """
    if not isinstance(template, str):
        return "true" if template is True else "false" if template is False else str(template)

    def _sub(m):
        v = _eval_expr(m.group(1), ctx)
        return "true" if v is True else "false" if v is False else "" if v is None else str(v)

    return _INTERP_RE.sub(_sub, template)


# ══════════════════════════════════════════════════════════════════════
# 2. 模擬事件 context
# ══════════════════════════════════════════════════════════════════════
def _push_ctx(sha: str, run_id: str) -> dict:
    """合併進 main 的 push。**`github.ref` 恆為 `refs/heads/main`** —— 這正是病灶。"""
    return {
        "github": {
            "event_name": "push", "ref": "refs/heads/main", "ref_name": "main",
            "ref_type": "branch", "sha": sha, "run_id": run_id, "run_number": "2046",
            "run_attempt": "1", "head_ref": "", "base_ref": "",
            "repository": "linchen-20200325/my-Fund-dashboard",
            "repository_owner": "linchen-20200325", "workflow": "PR Check",
            "workflow_ref": "linchen-20200325/my-Fund-dashboard/.github/workflows/pr-check.yml@refs/heads/main",
            "actor": "linchen-20200325", "job": "fast-checks",
            "event": {"before": "0" * 40, "after": sha},
        }
    }


def _pr_ctx(sha: str, run_id: str, number: int = 123) -> dict:
    """同一個 PR 的第 N 次 push:`ref` 固定、`sha`(merge commit)每次都變。"""
    return {
        "github": {
            "event_name": "pull_request", "ref": f"refs/pull/{number}/merge",
            "ref_name": f"{number}/merge", "ref_type": "branch", "sha": sha,
            "run_id": run_id, "run_number": "2047", "run_attempt": "1",
            "head_ref": "claude/some-feature", "base_ref": "main",
            "repository": "linchen-20200325/my-Fund-dashboard",
            "repository_owner": "linchen-20200325", "workflow": "PR Check",
            "workflow_ref": "linchen-20200325/my-Fund-dashboard/.github/workflows/pr-check.yml@refs/heads/main",
            "actor": "linchen-20200325", "job": "fast-checks",
            "event": {"number": number, "pull_request": {"number": number}},
        }
    }


def _concurrency(doc: dict) -> dict:
    cc = doc.get("concurrency")
    assert isinstance(cc, dict), (
        "pr-check.yml 沒有 workflow 層級的 `concurrency:` mapping —— "
        "本守衛的分析對象消失了,請先讀本檔開頭再決定怎麼辦"
    )
    assert str(cc.get("group", "")).strip(), "`concurrency.group` 是空的"
    return cc


def _push_is_protected(cc: dict) -> tuple[bool, str]:
    """兩顆 merge commit 會不會互相取消?回 (安全嗎, 說明)。

    **兩種等價修法都放行**:
      (a) group 每顆 commit 各自一組(現行修法);
      (b) `cancel-in-progress` 對 push 事件求值為 false。
    """
    a = _render(cc["group"], _push_ctx("a" * 40, "111"))
    b = _render(cc["group"], _push_ctx("b" * 40, "222"))
    if a != b:
        return True, f"group 每顆 commit 各自一組:\n  {a}\n  {b}"
    cip = _render(cc.get("cancel-in-progress", False), _push_ctx("a" * 40, "111"))
    if cip.lower() != "true":
        return True, f"group 相同但 push 事件不取消(cancel-in-progress → {cip!r})"
    return False, (
        f"兩顆不同的 merge commit 落在**同一組** {a!r},且 cancel-in-progress 對 push "
        f"求值為 true → 後一次合併會取消前一次尚未跑完的 main run"
    )


# ══════════════════════════════════════════════════════════════════════
# 3. 斷言
# ══════════════════════════════════════════════════════════════════════
def test_two_merges_to_main_do_not_cancel_each_other():
    """**本檔的主結論**:連續兩次合併,前一次的 main run 不得被後一次取消。"""
    ok, why = _push_is_protected(_concurrency(_load_workflow()))
    assert ok, (
        "CI 守衛退化:push 到 main 的 run 會被後續 push 取消。\n"
        f"{why}\n"
        "→ 後果:那顆 merge commit 拿不到完整的 main 驗證,而且**沒有人會察覺**;\n"
        "  run-level 會顯示 cancelled(本 repo 紀律:cancelled ≠ success)。\n"
        "→ 修法二選一:group 帶入每次 push 唯一值(如 github.sha),\n"
        "  或讓 cancel-in-progress 對 push 事件求值為 false。詳見本檔開頭。"
    )


def test_pr_pushes_still_cancel_each_other():
    """**反向護欄**:修 push 不准把 PR 分支的省時取消一起關掉。

    這條是刻意的:單純把 `cancel-in-progress` 全域改成 false 也能讓上一條變綠,
    但那會讓 PR 每次 push 都堆積 run。本條擋掉那個走法。
    """
    cc = _concurrency(_load_workflow())
    a = _render(cc["group"], _pr_ctx("c" * 40, "333"))
    b = _render(cc["group"], _pr_ctx("d" * 40, "444"))
    assert a == b, (
        "同一個 PR 的兩次 push 落在不同的 concurrency group,舊 run 不會再被取消 → "
        f"每次 push 都會堆一輪 CI。\n  {a}\n  {b}"
    )
    cip = _render(cc.get("cancel-in-progress", False), _pr_ctx("c" * 40, "333"))
    assert cip.lower() == "true", (
        f"PR 事件的 cancel-in-progress 求值為 {cip!r} → PR 分支上舊 run 不會被取消。"
    )


def test_no_job_level_concurrency_blindspot():
    """job 層級 concurrency 會讓本檔的 workflow 層級分析不完整 → 紅燈要求擴充。"""
    doc = _load_workflow()
    jobs = doc.get("jobs") or {}
    assert jobs, "pr-check.yml 沒有任何 job —— 前提不成立"
    offenders = sorted(n for n, j in jobs.items() if isinstance(j, dict) and "concurrency" in j)
    assert not offenders, (
        f"下列 job 自帶 concurrency:{offenders} —— 本守衛只分析 workflow 層級,"
        "結論會不完整。請連同本檔一起擴充,不要直接刪掉這條。"
    )


def test_premise_push_to_main_still_triggers_this_workflow():
    """前提檢查:本檔整組推論建立在「合併進 main 會觸發這條 workflow」上。

    ⚠️ 這**不是**在鎖 `on:` 清單。若哪天真的刻意移除 push→main 觸發,
    本條會紅 —— 那時該做的是回頭讀本檔開頭、重新判斷這組守衛還要不要留,
    而不是把這條刪掉了事。
    """
    doc = _load_workflow()
    # ⚠️ YAML 1.1 會把裸 `on:` 解析成布林 True(不是字串 "on")—— 兩種都接。
    on_cfg = doc.get("on") if "on" in doc else doc.get(True)
    assert isinstance(on_cfg, dict), f"`on:` 不是 mapping:{on_cfg!r}"
    assert "push" in on_cfg, "`on:` 已無 push 觸發 —— 本守衛的前提消失,請重讀本檔開頭"
    assert "main" in (on_cfg["push"] or {}).get("branches", []), (
        "`on.push.branches` 已不含 main —— 同上"
    )


# ══════════════════════════════════════════════════════════════════════
# 4. 內建突變證明 —— 守衛自己要能證明它有牙齒
#    (§-1.5 v2 對照表第 7 項「突變測試:拿掉修復必須能轉紅燈」的常駐版本)
# ══════════════════════════════════════════════════════════════════════
_HISTORICAL_BROKEN = {"group": "pr-check-${{ github.ref }}", "cancel-in-progress": True}


def test_the_guard_would_catch_the_historical_broken_config():
    """把 2026-09-07 之前那份**真的出過事**的設定餵進同一組分析 → 必須判為不安全。

    沒有這條,上面那些斷言可能只是「恰好都成立」而從來沒有紅過。
    """
    ok, why = _push_is_protected(_HISTORICAL_BROKEN)
    assert not ok, "守衛沒有牙齒:歷史上真的造成 run 34107180350 被取消的設定竟被判為安全"
    assert "同一組" in why


def test_the_guard_would_catch_the_lazy_global_false():
    """反向護欄也要有牙齒:全域 `cancel-in-progress: false` 必須被 PR 那條擋下來。"""
    cc = {"group": "pr-check-${{ github.ref }}", "cancel-in-progress": False}
    assert _push_is_protected(cc)[0], "全域 false 本來就該讓 push 安全(前提檢查)"
    assert _render(cc["cancel-in-progress"], _pr_ctx("c" * 40, "333")) == "false", (
        "全域 false 之下 PR 事件仍求值為 true → 反向護欄失效"
    )


# ══════════════════════════════════════════════════════════════════════
# 5. 求值器自我驗證 —— 正對照 + fail-loud 行為
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "expr, ctx, expected",
    [
        ("github.event_name == 'push'", _push_ctx("x" * 40, "1"), True),
        ("github.event_name == 'push'", _pr_ctx("x" * 40, "1"), False),
        ("github.event_name == 'push' && github.sha || 'shared'", _push_ctx("z" * 40, "1"), "z" * 40),
        ("github.event_name == 'push' && github.sha || 'shared'", _pr_ctx("z" * 40, "1"), "shared"),
        ("github.event.pull_request.number || github.sha", _pr_ctx("q" * 40, "1"), 123),
        ("github.event.pull_request.number || github.sha", _push_ctx("q" * 40, "1"), "q" * 40),
        ("!(github.event_name == 'push')", _push_ctx("x" * 40, "1"), False),
        ("github.event_name != 'push'", _push_ctx("x" * 40, "1"), False),
    ],
)
def test_expression_evaluator_positive_controls(expr, ctx, expected):
    """求值器本身要是活的 —— 不然上面每一條斷言都建立在沙上。"""
    assert _eval_expr(expr, ctx) == expected


@pytest.mark.parametrize(
    "expr",
    [
        "format('{0}', github.sha)",   # 函式:沒實作
        "inputs.foo",                  # 未模擬的 context
        "github.token",                # 未模擬的 github 欄位
        "github",                      # 裸 context
        "github.sha &&",               # 語法殘缺
    ],
)
def test_evaluator_fails_loud_on_things_it_cannot_understand(expr):
    """看不懂就丟例外(紅燈),**不准**回一個空字串矇混過去(§1 Fail Loud)。

    這條是本檔最重要的自我保護:若求值器對看不懂的運算式靜默回 `''`,
    兩個 push context 會算出相同的 group → 反而讓守衛在最該紅的時候變綠。
    """
    with pytest.raises(UnsupportedExpression):
        _eval_expr(expr, _push_ctx("x" * 40, "1"))
