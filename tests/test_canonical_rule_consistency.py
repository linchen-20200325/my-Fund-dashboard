# -*- coding: utf-8 -*-
"""Canonical Rule Convergence 機械守衛（`DEC-2026-11-03-08`；唯讀掃文件，頁序只讀 ui_v3 登錄表）。

守什麼：
1. `docs/HANDOFF.md` 只有一個未劃線的「唯一下一接手點」；體積有上限（覆蓋、不累加）。
2. 現行頁名：`PROJECT_RULES.md` 13.2 第 1 點的頁名集合與順序＝`ui_v3.shell.registry.IA_PAGES`；舊頁名不得出現在該現行點。
3. 現行區（HANDOFF、BACKLOG 的 BL-0536 列、`PROJECT_RULES.md` 13.5、`docs/v2/80` 第 16 節）不得殘留暫時／待定字樣。
4. history 搬移無遺失：每個 `MOVED-BEGIN` 區塊的 sha256／位元組數與標記一致、README 清冊有登記；
   可取得基準 commit 時，與該 commit 原文比對（取不到則 skip 並明示，不假裝驗過）。

負控（假違規字串）全部在測試內現編，不落文件（`CLAUDE.md` §-2.A 第 8 款）。
已知未守：`docs/v2/81` 內尚存的劃線舊句與未核准字樣（BL-0541）；`PROJECT_RULES.md` 其餘章節的劃線舊句（BL-0541）。
"""
from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
KNOWN_BASES = ("82ba783f", "d6173220", "875b1955", "f07acd44", "21296a0d", "66a09ed2", "b9595833", "e6ff1902", "1f260bfc", "d4eabb35", "81827057", "6e021744")  # 已知基準清單；區塊 source 的 `@sha` 必須屬於此
BASE_COMMIT = "82ba783f"  # 預設基準；每個區塊的實際基準記在其 source 的 `@<sha>`（H2、B2 為 d6173220；S1～S3 為 875b1955；H3～H5、B3 為 f07acd44；H6、H7 為 21296a0d；H8 為 66a09ed2；H9 為 b9595833；H10 為 e6ff1902；H11 為 1f260bfc；H12 為 d4eabb35；H13 為 81827057）
HANDOFF_MAX_LINES = 120
BL0536_ROW_MAX_BYTES = 8000


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def strip_struck(text: str) -> str:
    """移除劃線段（現行區判讀只看未劃線文字）。"""
    return re.sub(r"~~.*?~~", "", text, flags=re.S)


def count_unstruck(text: str, phrase: str) -> int:
    return strip_struck(text).count(phrase)


STALE_MARKERS = ("PENDING", "擬：", "待客戶定字")


def stale_hits(text: str) -> list:
    t = strip_struck(text)
    return [m for m in STALE_MARKERS if m in t]


_BLOCK_RE = re.compile(
    r"<!-- MOVED-BEGIN id=(?P<id>\S+) source=(?P<source>\S+) sha256=(?P<sha>[0-9a-f]{64}) bytes=(?P<n>\d+) -->\n"
    r"(?P<body>.*?)\n<!-- MOVED-END id=(?P=id) -->\n",
    re.S,
)


def parse_blocks(text: str) -> list:
    return [m.groupdict() for m in _BLOCK_RE.finditer(text)]


def block_ok(b: dict) -> bool:
    body = b["body"].encode("utf-8")
    return hashlib.sha256(body).hexdigest() == b["sha"] and len(body) == int(b["n"])


# ---------------------------------------------------------------- 1 HANDOFF
def test_handoff_single_live_next_point():
    assert count_unstruck(_read("docs/HANDOFF.md"), "唯一下一接手點") == 1


def test_handoff_is_not_accumulating():
    n = len(_read("docs/HANDOFF.md").splitlines())
    assert n <= HANDOFF_MAX_LINES, f"HANDOFF 應覆蓋、不累加（{n} 行）"


_PARALLEL_RE = re.compile(r"\(\d\)|（\d）|(?:^|\s)\d[.、)]\s")


def has_parallel_numbering(line: str) -> bool:
    return bool(_PARALLEL_RE.search(line))


def test_handoff_next_point_is_one_sentence_not_parallel_list():
    lines = [l for l in _read("docs/HANDOFF.md").splitlines() if "唯一下一接手點" in strip_struck(l)]
    assert len(lines) == 1
    assert not has_parallel_numbering(lines[0]), "唯一下一接手點不得用 (1)(2) 或 1. 2. 並列"


def test_parallel_numbering_negative_control():
    assert has_parallel_numbering("唯一下一接手點：(1) 甲 (2) 乙")
    assert has_parallel_numbering("唯一下一接手點：1. 甲 2. 乙")
    assert not has_parallel_numbering("唯一下一接手點：先完成甲批的 CI 與合併")


def test_handoff_guard_negative_control():
    fake = "唯一下一接手點 A\n唯一下一接手點 B\n~~唯一下一接手點 C~~"
    assert count_unstruck(fake, "唯一下一接手點") == 2


# ---------------------------------------------------------------- 2 頁名
def _ia_titles() -> list:
    from ui_v3.shell.registry import IA_PAGES

    return [p.title for p in IA_PAGES]


def _rules_132_point1() -> str:
    for line in _read("PROJECT_RULES.md").splitlines():
        if line.startswith("1. **五頁資訊架構與職責"):
            return line
    raise AssertionError("找不到 PROJECT_RULES.md 13.2 第 1 點")


def test_132_point1_page_names_match_registry_in_order():
    line = strip_struck(_rules_132_point1())
    pos = []
    for t in _ia_titles():
        assert t in line, f"13.2 第 1 點缺現行頁名：{t}"
        pos.append(line.index(t))
    assert pos == sorted(pos), "13.2 第 1 點頁名順序與 IA_PAGES 不一致"


def test_132_point1_has_no_old_top_level_pages():
    line = strip_struck(_rules_132_point1())
    assert "⚖️ 資產配置" not in line
    assert "💼 我的持股" not in line


OLD_PAGE_NAMES = ("⚖️", "💼 我的持股")
_EXEMPT = ("superseded", "NOT CURRENT", "~~", "歷史")


def old_page_hits(text: str) -> list:
    """整檔掃舊頁名；排除含 superseded／NOT CURRENT／劃線／歷史標記的行。"""
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        if any(x in line for x in _EXEMPT):
            continue
        if any(o in line for o in OLD_PAGE_NAMES):
            hits.append(n)
    return hits


@pytest.mark.parametrize("rel", ["PROJECT_RULES.md", "docs/HANDOFF.md"])
def test_current_files_have_no_unmarked_old_page_names(rel):
    assert old_page_hits(_read(rel)) == [], f"{rel} 有未標 superseded 的舊頁名行"


def test_page_name_guard_negative_control():
    assert "⚖️ 資產配置" in strip_struck("🌍 市場與趨勢、⚖️ 資產配置、💼 我的持股")
    assert old_page_hits("新五頁 🌍 → ⚖️資產配置 → 💼 我的持股") == [1]
    assert old_page_hits("舊頁序 ⚖️資產配置（superseded: DEC）") == []


# ---------------------------------------------------------------- 3 現行區殘留
def _bl0536_row() -> str:
    rows = [l for l in _read("docs/BACKLOG.md").splitlines() if l.startswith("| BL-0536 |")]
    assert len(rows) == 1
    return rows[0]


def _section(text: str, start_prefix: str, end_prefix=None) -> str:
    lines = text.splitlines()
    i = next(k for k, l in enumerate(lines) if l.startswith(start_prefix))
    j = len(lines)
    if end_prefix:
        j = next(k for k in range(i + 1, len(lines)) if lines[k].startswith(end_prefix))
    return "\n".join(lines[i:j])


@pytest.mark.parametrize(
    "name,getter",
    [
        ("docs/HANDOFF.md", lambda: _read("docs/HANDOFF.md")),
        ("BACKLOG BL-0536 列", _bl0536_row),
        ("PROJECT_RULES 13.5", lambda: _section(_read("PROJECT_RULES.md"), "### 13.5 ", "## 第 14 節")),
        ("docs/v2/80 第 16 節", lambda: _section(_read("docs/v2/80_new_ui2_architecture_proposal.md"), "## 16. ")),
    ],
)
def test_current_areas_have_no_stale_markers(name, getter):
    assert stale_hits(getter()) == [], f"{name} 現行區殘留暫時／待定字樣"


def test_bl0536_row_stays_slim():
    assert len(_bl0536_row().encode("utf-8")) <= BL0536_ROW_MAX_BYTES


def test_stale_marker_negative_control():
    assert stale_hits("字樣 PENDING 中") == ["PENDING"]
    assert stale_hits("~~擬：舊字~~ 新字") == []


# ---------------------------------------------------------------- 4 history 無遺失
HISTORY = [p for p in sorted((ROOT / "docs/evidence/history").glob("*.md")) if p.name != "README.md"]


def test_history_files_exist_and_marked_not_current():
    assert HISTORY, "docs/evidence/history/ 沒有搬出檔"
    for p in HISTORY:
        assert "NOT CURRENT" in p.read_text(encoding="utf-8")[:600]


def test_history_blocks_hash_and_manifest():
    readme = _read("docs/evidence/history/README.md")
    seen = 0
    for p in HISTORY:
        for b in parse_blocks(p.read_text(encoding="utf-8")):
            seen += 1
            assert block_ok(b), f"{p.name} 區塊 {b['id']} 與標記的 sha256／bytes 不符（搬移後被改動或遺失）"
            assert b["id"] in readme, f"README 清冊缺區塊 {b['id']}"
    assert seen >= 12


def block_base(b: dict) -> str:
    """區塊自己的基準 commit：source 的 `@<sha>`；沒寫才退回預設基準。"""
    m = re.search(r"@([0-9a-f]{7,40})$", b["source"])
    return m.group(1) if m else BASE_COMMIT


def base_known(sha: str) -> bool:
    """`@sha` 是否屬已知基準（完整 sha 或前綴皆可，至少 7 碼）。"""
    return len(sha) >= 7 and any(k.startswith(sha) or sha.startswith(k) for k in KNOWN_BASES)


def test_history_block_bases_are_known():
    for p in HISTORY:
        for b in parse_blocks(p.read_text(encoding="utf-8")):
            sha = block_base(b)
            assert base_known(sha), f"{p.name} 區塊 {b['id']} 的基準 @{sha} 不在已知基準清單 {KNOWN_BASES}"


def test_base_known_negative_control():
    assert base_known("82ba783f") and base_known("d6173220")
    assert base_known("d6173220" + "0" * 32)
    assert not base_known("deadbee")
    assert not base_known("ffffffff")
    assert not base_known("82ba78")


def _git_show(path: str, commit: str = BASE_COMMIT):
    try:
        r = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT, capture_output=True, timeout=60)
    except Exception:
        return None
    return r.stdout.decode("utf-8") if r.returncode == 0 else None


def test_history_blocks_match_base_commit_when_available():
    bases = {block_base(b) for p in HISTORY for b in parse_blocks(p.read_text(encoding="utf-8"))}
    avail = {c for c in bases if _git_show("docs/HANDOFF.md", c) is not None}
    if not avail:
        pytest.skip(f"取不到任何基準 commit {sorted(bases)}（淺 clone）；僅驗了 sha256／清冊，未與原文比對")
    for p in HISTORY:
        for b in parse_blocks(p.read_text(encoding="utf-8")):
            base = block_base(b)
            if base not in avail:
                continue  # 該區塊的基準取不到：僅驗 sha256／清冊
            path = b["source"].split("@")[0].split("#")[0]
            orig = _git_show(path, base)
            assert orig is not None, (base, path)
            if b["id"] == "H1":
                assert orig == b["body"]
            else:
                for line in b["body"].split("\n"):
                    assert line in orig, f"區塊 {b['id']} 有不在基準 {base} 原文的行"


def test_block_base_parsing():
    assert block_base({"source": "docs/HANDOFF.md#x@d6173220"}) == "d6173220"
    assert block_base({"source": "docs/HANDOFF.md@82ba783f"}) == "82ba783f"
    assert block_base({"source": "docs/HANDOFF.md"}) == BASE_COMMIT


def test_history_guard_negative_control():
    body = "原文一行\n第二行"
    ok = {"body": body, "sha": hashlib.sha256(body.encode()).hexdigest(), "n": str(len(body.encode()))}
    assert block_ok(ok)
    assert not block_ok({**ok, "body": body + "x"})
    assert not block_ok({**ok, "body": "原文一行"})


# ---------------------------------------------------------------- DECISIONS 結構
def decisions_structure_problems(text: str) -> list:
    """DECISIONS.md 結構：第五節標題恰好 1 個；`### DEC-` 標題的編號不重複。"""
    lines = text.splitlines()
    problems = []
    n5 = [l for l in lines if l.startswith("## 五、歷史索引")]
    if len(n5) != 1:
        problems.append(f"「## 五、歷史索引」標題行應恰好 1 個，實際 {len(n5)}")
    ids = []
    for l in lines:
        m = re.match(r"### (DEC-\d{4}-\d{2}-\d{2}-\d+)", l)
        if m:
            ids.append(m.group(1))
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        problems.append(f"DEC 標題編號重複：{dup}")
    return problems


def test_decisions_md_structure_no_duplicate_headings():
    assert decisions_structure_problems(_read("docs/DECISIONS.md")) == []


def test_decisions_structure_negative_control():
    good = "## 五、歷史索引（x）\n### DEC-2026-11-03-11｜a\n### DEC-2026-11-03-12｜b\n"
    assert decisions_structure_problems(good) == []
    assert decisions_structure_problems(good + "## 五、歷史索引（x）\n")
    assert decisions_structure_problems(good + "### DEC-2026-11-03-12｜b\n")
    # 行中引文不算標題行（真實事故：反引號引文被誤取代成標題）
    assert decisions_structure_problems(good + "- 原文 `## 五、歷史索引（x）` 逐字恢復\n") == []
