"""`.claude/agents/` 三個專業 Agent 定義檔的結構守衛（Quality Batch 3 PR-1；`DEC-2026-11-13-04`）。

守衛的是「結構」：frontmatter 欄位、工具白名單、七個二級標題、禁字與檔尾格式。
**不守衛**：agent 的實際執行期權限（那要用 `claude -p` 實測，屬 PR-2 範圍）、
也不證明資安隔離（工具白名單不等於資安隔離；敏感路徑 deny 規則屬待客戶裁示的 BL-0549）。

純標準庫、不依賴 yaml／streamlit，手動解析 frontmatter；每個守衛附一個「變異驗證」：
在測試內以字串操作構造違規樣本，確認該守衛真的會抓到（不修改實際檔案）。
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO / ".claude" / "agents"

EXPECTED_AGENTS = (
    "fund-nav-data",
    "fund-governance-auditor",
    "fund-independent-qa",
)
EXPECTED_TOOLS = {"Read", "Grep", "Glob"}
FORBIDDEN_TOOLS = {"Write", "Edit", "NotebookEdit", "Bash", "Agent"}
REQUIRED_DISALLOWED = {"Write", "Edit", "Bash"}
EXPECTED_HEADINGS = [
    "## Role",
    "## Trigger",
    "## Inputs",
    "## Tools",
    "## Forbidden",
    "## Output",
    "## Escalation",
]
# 禁字以片段組字，避免本檔自己命中（負控字串不落文件的同一個道理）
_FORBIDDEN_TEXT_PATTERNS = (
    re.compile(r"Co-Authored" + r"-By", re.IGNORECASE),
    re.compile(r"claude\.ai/code/" + r"session"),
    re.compile(r"session" + r"_[0-9A-Za-z]{16,}"),
    re.compile(r"CONSTITUTION" + r"-FILE"),
)


# --------------------------------------------------------------- 解析（純函式）
def parse_agent(text: str) -> tuple[dict[str, str], str]:
    """回傳 (frontmatter 鍵值, 本文)。frontmatter 缺失或未收尾即 ValueError。"""
    lines = text.split("\n")
    if not lines or lines[0] != "---":
        raise ValueError("缺開頭 ---")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError("frontmatter 未以 --- 收尾") from exc
    fm: dict[str, str] = {}
    for ln in lines[1:end]:
        if not ln.strip():
            continue
        if ":" not in ln:
            raise ValueError(f"frontmatter 行無法解析：{ln!r}")
        k, v = ln.split(":", 1)
        fm[k.strip()] = v.strip()
    return fm, "\n".join(lines[end + 1 :])


def split_list(value: str) -> set[str]:
    return {x.strip() for x in value.split(",") if x.strip()}


def h2_headings(body: str) -> list[str]:
    return [ln.rstrip() for ln in body.split("\n") if ln.startswith("## ")]


# ----------------------------------------------------------------- 各守衛判定
def check_frontmatter_basic(stem: str, fm: dict[str, str]) -> list[str]:
    errs = []
    if fm.get("name") != stem:
        errs.append(f"name {fm.get('name')!r} 必須等於檔名 {stem!r}")
    if not fm.get("description"):
        errs.append("缺 description")
    return errs


def check_tools_exact(fm: dict[str, str]) -> list[str]:
    got = split_list(fm.get("tools", ""))
    return [] if got == EXPECTED_TOOLS else [f"tools 須恰為 {sorted(EXPECTED_TOOLS)}，實得 {sorted(got)}"]


def check_tools_no_write(fm: dict[str, str]) -> list[str]:
    got = split_list(fm.get("tools", ""))
    bad = sorted(t for t in got if t in FORBIDDEN_TOOLS or t.startswith("mcp__"))
    return [f"tools 含禁用項 {bad}"] if bad else []


def check_disallowed(fm: dict[str, str]) -> list[str]:
    got = split_list(fm.get("disallowedTools", ""))
    missing = sorted(REQUIRED_DISALLOWED - got)
    return [f"disallowedTools 缺 {missing}"] if missing else []


def check_headings(body: str) -> list[str]:
    got = h2_headings(body)
    return [] if got == EXPECTED_HEADINGS else [f"二級標題須依序為 {EXPECTED_HEADINGS}，實得 {got}"]


def check_forbidden_text(text: str) -> list[str]:
    return [f"含禁字 {p.pattern}" for p in _FORBIDDEN_TEXT_PATTERNS if p.search(text)]


def check_format(text: str) -> list[str]:
    errs = []
    if not text.endswith("\n") or text.endswith("\n\n"):
        errs.append("結尾須為單一換行")
    for i, ln in enumerate(text.split("\n"), 1):
        if ln != ln.rstrip():
            errs.append(f"第 {i} 行有行尾空白")
    return errs


# --------------------------------------------------------------------- 載入
def _agent_paths() -> list[Path]:
    return sorted(AGENTS_DIR.glob("*.md"))


def _load(stem: str) -> tuple[str, dict[str, str], str]:
    text = (AGENTS_DIR / f"{stem}.md").read_text(encoding="utf-8")
    fm, body = parse_agent(text)
    return text, fm, body


# ================================================================ 真實檔案守衛
def test_三個預期Agent檔都存在():
    stems = {p.stem for p in _agent_paths()}
    missing = [s for s in EXPECTED_AGENTS if s not in stems]
    assert not missing, f".claude/agents/ 缺 {missing}"
    # 未來新增第四個以上不在本守衛禁止之列，但須另行審查；此處只確認預期三檔齊全。


def test_frontmatter有name且等於檔名並有description():
    for stem in EXPECTED_AGENTS:
        _, fm, _ = _load(stem)
        assert not check_frontmatter_basic(stem, fm), (stem, check_frontmatter_basic(stem, fm))


def test_tools恰好是Read_Grep_Glob():
    for stem in EXPECTED_AGENTS:
        _, fm, _ = _load(stem)
        assert not check_tools_exact(fm), (stem, check_tools_exact(fm))


def test_tools不含寫入_執行_委派或MCP項():
    for stem in EXPECTED_AGENTS:
        _, fm, _ = _load(stem)
        assert not check_tools_no_write(fm), (stem, check_tools_no_write(fm))


def test_disallowedTools含Write_Edit_Bash():
    for stem in EXPECTED_AGENTS:
        _, fm, _ = _load(stem)
        assert not check_disallowed(fm), (stem, check_disallowed(fm))


def test_本文恰有七個二級標題且順序正確():
    for stem in EXPECTED_AGENTS:
        _, _, body = _load(stem)
        assert not check_headings(body), (stem, check_headings(body))


def test_全文不含署名_session識別碼_憲法標記():
    for stem in EXPECTED_AGENTS:
        text, _, _ = _load(stem)
        assert not check_forbidden_text(text), (stem, check_forbidden_text(text))


def test_檔尾單一換行且無行尾空白():
    for stem in EXPECTED_AGENTS:
        text, _, _ = _load(stem)
        assert not check_format(text), (stem, check_format(text))


# ============================================================ 變異驗證（不改實檔）
def _good() -> str:
    return (AGENTS_DIR / "fund-nav-data.md").read_text(encoding="utf-8")


def test_變異_name與檔名不符會被抓到():
    text = _good().replace("name: fund-nav-data", "name: other-name", 1)
    fm, _ = parse_agent(text)
    assert check_frontmatter_basic("fund-nav-data", fm)


def test_變異_缺description會被抓到():
    text = re.sub(r"^description:.*\n", "", _good(), count=1, flags=re.MULTILINE)
    fm, _ = parse_agent(text)
    assert check_frontmatter_basic("fund-nav-data", fm)


def test_變異_tools多一項或少一項會被抓到():
    for new in ("tools: Read, Grep, Glob, Bash", "tools: Read, Grep"):
        text = _good().replace("tools: Read, Grep, Glob", new, 1)
        fm, _ = parse_agent(text)
        assert check_tools_exact(fm), new


def test_變異_tools含Write或mcp項會被抓到():
    for new in ("tools: Read, Grep, Glob, Write", "tools: Read, Grep, Glob, mcp__x__y"):
        text = _good().replace("tools: Read, Grep, Glob", new, 1)
        fm, _ = parse_agent(text)
        assert check_tools_no_write(fm), new


def test_變異_disallowedTools缺Bash會被抓到():
    text = _good().replace("NotebookEdit, Bash, Agent", "NotebookEdit, Agent", 1)
    fm, _ = parse_agent(text)
    assert check_disallowed(fm)


def test_變異_標題缺漏_錯序_多餘都會被抓到():
    body = parse_agent(_good())[1]
    assert not check_headings(body)
    assert check_headings(body.replace("## Escalation", "## Extra", 1))
    swapped = body.replace("## Role", "## @@", 1).replace("## Trigger", "## Role", 1).replace("## @@", "## Trigger", 1)
    assert check_headings(swapped)
    assert check_headings(body + "\n## 多餘\n")


def test_變異_禁字會被抓到():
    parts = {
        "co": "Co-Authored" + "-By: x",
        "url": "https://claude.ai/code/" + "session_abc",
        "sid": "session" + "_" + "A" * 20,
        "mark": "<!-- CONSTITUTION" + "-FILE -->",
    }
    for key, frag in parts.items():
        assert check_forbidden_text(_good() + frag), key


def test_變異_格式違規會被抓到():
    good = _good()
    assert not check_format(good)
    assert check_format(good + "\n")  # 兩個換行
    assert check_format(good.rstrip("\n"))  # 無換行
    assert check_format(good.replace("## Role", "## Role  ", 1))  # 行尾空白


def test_變異_frontmatter壞掉會丟ValueError():
    for bad in ("no frontmatter\n", "---\nname: a\n"):
        try:
            parse_agent(bad)
        except ValueError:
            continue
        raise AssertionError(f"應拋 ValueError：{bad!r}")
