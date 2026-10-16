"""守衛：子法 1 正式修正案 #8（`docs/v2/57_amendment_8_directional_judgment.md`）的完整性。

來源：客戶 2026-10-16 提案單 #8 核准裁示（`docs/DECISIONS.md` `DEC-2026-10-16-14`；
逐字存檔 `docs/evidence/decisions/2026-10-16_proposal8_approval.md`）。客戶核准方案 A：
子法 1 存檔 `docs/v2/CONSTITUTION.md` 一個位元組都不改，被修正的條文改由修正案 57 逐條列出，
兩者合讀為單一版本。

檢查什麼：
1. 57 存在（不 skip：檔案消失時，治理索引指向的現行條文就指不到了）。
2. 57 寫出的子法 1 sha256 等於 `tests/test_constitution_archive_integrity.py` 的
   `EXPECTED_SHA256`（讀檔取值，不另抄一份）—— 57 的行號與引文只對那個版本成立。
3. 57 含資料不足字樣「⬜ 無法判定（資料未備／證據不足）」。
4. `PROJECT_RULES.md` 與 `docs/DECISIONS.md` 都引用 57 的路徑（讀子法 1 時須併讀 57 的入口）。
5. 57 的原文引文與子法 1 對應行逐字一致。**涵蓋範圍**：57 裡依格式寫成的**每一則**
   原文引文（格式見 57 第 3 節開頭：一行 `**原文**（原文行號 ...）：`，空一行，接 `text` 圍欄），
   不只 1-1、1-5、1-6 三條。另以 `_EXPECTED_QUOTES` 釘住引文的行號集合，並核對引文標頭數
   等於解析成功數 —— 引文被刪、圍欄被改壞時會轉紅，不會因為「一則都沒抓到」而綠。
   比對前把 57 的跳脫碼（反斜線、字母 u、四位十六進位）以碼位還原成原字。

射程外（已知不驗，不得從綠燈推論已驗）：
- 「修正後完整條文」是否等於提案單 56 第 1 欄、是否符合客戶裁示 —— 那是語意，由稽核看。
- 母法〈專案重構終審令〉—— 原文不在 repo。
- 57 是否還有未跳脫的禁詞 —— 本守衛不掃禁詞。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
AMENDMENT_REL = "docs/v2/57_amendment_8_directional_judgment.md"
AMENDMENT = REPO_ROOT / AMENDMENT_REL
CONSTITUTION = REPO_ROOT / "docs" / "v2" / "CONSTITUTION.md"
ARCHIVE_GUARD = REPO_ROOT / "tests" / "test_constitution_archive_integrity.py"
INDEX_DOCS = ("PROJECT_RULES.md", "docs/DECISIONS.md")
INSUFFICIENT_WORDING = "⬜ 無法判定（資料未備／證據不足）"

_BACKSLASH = chr(92)
_ESCAPE_RE = re.compile(re.escape(_BACKSLASH) + r"u([0-9a-fA-F]{4})")
_QUOTE_HEADER = "**原文**（原文行號 "
_QUOTE_RE = re.compile(
    r"^\*\*原文\*\*（原文行號 `:(\d+)`(?:～`:(\d+)`)?）：\n\n```text\n(.*?)\n```$",
    re.M | re.S,
)

# 57 引用的子法 1 行號區間（含頭含尾）。改 57 的引文時同步改這裡 ——
# 這一份是期望值，不得改成從 57 推導（那樣「改引文」與「改期望」會由同一個動作完成）。
_EXPECTED_QUOTES = frozenset({
    (11, 11), (14, 14),
    (289, 289), (291, 291), (294, 296), (298, 298), (299, 299),
    (506, 506), (513, 513), (533, 533),
    (570, 570), (574, 574), (576, 576), (580, 580), (581, 581), (582, 582),
    (586, 588), (659, 659), (660, 661), (670, 670), (808, 808),
    (1075, 1075), (1114, 1114), (1118, 1118), (1129, 1129), (1168, 1168),
    (1405, 1405), (1406, 1406), (1528, 1528),
    (1838, 1838), (1873, 1873), (1947, 1947), (1950, 1950),
})
# 派工下限：1-1（:570）、1-5（:581）、1-6（:582）三條必須在比對範圍內。
_MUST_COVER = frozenset({(570, 570), (581, 581), (582, 582)})


def _decode(text: str) -> str:
    return _ESCAPE_RE.sub(lambda m: chr(int(m.group(1), 16)), text)


def _quotes(text: str) -> list[tuple[int, int, str]]:
    return [(int(m.group(1)), int(m.group(2) or m.group(1)), m.group(3))
            for m in _QUOTE_RE.finditer(text)]


def _mismatches(text: str, constitution_lines: list[str]) -> list[str]:
    bad = []
    for start, end, body in _quotes(text):
        expected = "\n".join(constitution_lines[start - 1:end])
        if _decode(body) != expected:
            bad.append(f":{start}～:{end}")
    return bad


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_amendment_exists():
    assert AMENDMENT.is_file(), f"找不到 {AMENDMENT_REL}（子法 1 正式修正案 #8，DEC-2026-10-16-14）"


def test_amendment_pins_the_archived_constitution_sha256():
    m = re.search(r'^EXPECTED_SHA256 = "([0-9a-f]{64})"$', _read(ARCHIVE_GUARD), re.M)
    assert m, "讀不到 tests/test_constitution_archive_integrity.py 的 EXPECTED_SHA256"
    assert m.group(1) in _read(AMENDMENT), (
        f"{AMENDMENT_REL} 沒有寫出子法 1 存檔守衛的 sha256 {m.group(1)}。"
        "57 的行號與引文只對該版子法 1 成立；子法 1 若經客戶裁示更動，57 須重新定位。"
    )


def test_amendment_states_the_insufficient_data_wording():
    assert INSUFFICIENT_WORDING in _read(AMENDMENT)


@pytest.mark.parametrize("rel", INDEX_DOCS)
def test_governance_index_points_to_the_amendment(rel):
    assert AMENDMENT_REL in _read(REPO_ROOT / rel), (
        f"{rel} 沒有引用 {AMENDMENT_REL}：讀子法 1 時須併讀修正案 #8，索引必須指過去。"
    )


def test_quote_set_is_pinned_and_fully_parsed():
    text = _read(AMENDMENT)
    found = [(s, e) for s, e, _ in _quotes(text)]
    assert text.count(_QUOTE_HEADER) == len(found), (
        "原文引文標頭數與解析成功數不同 —— 有引文的格式被改壞（標頭、空行或圍欄）。"
    )
    assert len(found) == len(set(found)), "同一段原文被引用兩次"
    assert set(found) == _EXPECTED_QUOTES, (
        f"引文行號集合變了：多了 {sorted(set(found) - _EXPECTED_QUOTES)}，"
        f"少了 {sorted(_EXPECTED_QUOTES - set(found))}"
    )
    assert _MUST_COVER <= set(found)


def test_every_quote_matches_the_constitution_verbatim():
    lines = _read(CONSTITUTION).split("\n")
    bad = _mismatches(_read(AMENDMENT), lines)
    assert not bad, f"{AMENDMENT_REL} 的原文引文與子法 1 不一致：{bad}"


def test_control_a_one_character_change_in_a_quote_is_caught():
    """負控：在記憶體裡把一則引文改一個字，比對必須抓到（不動工作樹）。"""
    lines = _read(CONSTITUTION).split("\n")
    text = _read(AMENDMENT)
    start, end, body = _quotes(text)[0]
    mutated_body = body[:-1] + ("X" if body[-1] != "X" else "Y")
    mutated = text.replace("```text\n" + body + "\n```", "```text\n" + mutated_body + "\n```", 1)
    assert mutated != text
    label = f":{start}～:{end}"
    assert label not in _mismatches(text, lines), "突變前這一則就不一致 —— 先修正控"
    assert label in _mismatches(mutated, lines), "改了一個字，比對沒有抓到 —— 比對沒有鑑別力"


def test_control_escape_decoding_restores_code_points():
    sample = _BACKSLASH + "u52a0" + _BACKSLASH + "u78bc"
    assert _decode(sample) == chr(0x52A0) + chr(0x78BC)
