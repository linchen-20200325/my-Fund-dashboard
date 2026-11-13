# -*- coding: utf-8 -*-
"""PR 模板「最小 Impact Check」守衛（客戶 2026-11-13 Batch 2 第 2 項）。

守什麼（只守兩件事，不新增任何 Gate）：
1. ``.github/pull_request_template.md`` 存在，且必要標題都在（「會渲染出來的」標題，不含註解內的字）。
2. 模板全文（含 HTML 註解）不含禁用署名字樣：共同作者行、session 網址／ID。

不守什麼（據實揭露）：
- 不守 PR body 實際內容：MCP／``gh`` 建 PR 時 body 由作者自己寫，**不會自動套用模板**；
  真正使用模板靠作者（人工或新對話 AI）照著填，本測試擋不住。
- 不守 GitHub 是否實際採用該檔名／位置（以 GitHub 官方文件為準，本測試不連網）。
- 不守 commit message（不在 repo 檔案內）。

註解錨點陷阱（``PROCESS.md`` §4）：標題檢查前先剝掉 HTML 註解，否則把標題寫進註解也會過。
禁用字樣的偵測式與負控全部在測試內由片段現編，不以字面落在任何檔案（``CLAUDE.md`` §-2.A 第 8 款的精神）。
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = REPO_ROOT / ".github" / "pull_request_template.md"

# 必要標題（二級標題）與 Impact Check 七維度＋Gate 對映的粗體標籤。
REQUIRED_HEADINGS = ("來源與授權", "Impact Check", "風險分級", "QA／CI 狀態", "衛生")
REQUIRED_DIMENSIONS = (
    "功能行為", "資料契約", "金融公式與門檻", "UI", "測試", "SSOT 文件", "回滾條件",
    "Stop／Decision Gate 對映",
)

# 禁用字樣：由片段組出，避免本檔自己成為 git grep 的命中。
_P = "-".join
_FORBIDDEN = (
    re.compile(_P(["co", "authored", "by"]), re.I),
    re.compile(_P(["claude", "session"]), re.I),
    re.compile(r"claude\.ai/code/" + "sess" + "ion", re.I),
    re.compile("sess" + r"ion_[0-9A-Za-z]{16,}"),
)

_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


def _strip_comments(text: str) -> str:
    return _COMMENT_RE.sub("", text)


def missing_headings(text: str) -> list[str]:
    body = _strip_comments(text)
    return [h for h in REQUIRED_HEADINGS
            if not re.search(rf"^##[ \t]+{re.escape(h)}", body, re.M)]


def missing_dimensions(text: str) -> list[str]:
    body = _strip_comments(text)
    return [d for d in REQUIRED_DIMENSIONS if f"**{d}**" not in body]


def forbidden_hits(text: str) -> list[str]:
    return [p.pattern for p in _FORBIDDEN if p.search(text)]


def _read() -> str:
    assert TEMPLATE.is_file(), f"缺少 {TEMPLATE.relative_to(REPO_ROOT)}"
    return TEMPLATE.read_text(encoding="utf-8")


def test_template_has_required_headings():
    assert missing_headings(_read()) == []


def test_template_has_seven_dimensions_and_gate_line():
    assert missing_dimensions(_read()) == []


def test_template_has_no_forbidden_attribution_strings():
    assert forbidden_hits(_read()) == []


# ── 負控：偵測器必須真的會紅（Test Liveness；假違規字串在此現編，不落文件）──
def test_negative_control_heading_inside_comment_does_not_count():
    fake = "<!-- ## Impact Check -->\n## 來源與授權\n"
    assert "Impact Check" in missing_headings(fake)


def test_negative_control_removed_dimension_is_detected():
    stripped = _read().replace("**回滾條件**", "**x**")
    assert "回滾條件" in missing_dimensions(stripped)


def test_negative_control_forbidden_strings_are_detected():
    bad_trailer = _P(["Co", "Authored", "By"]) + ": X <x@example.invalid>"
    bad_url = "https://claude.ai/code/" + "sess" + "ion_" + "A" * 20
    assert forbidden_hits(bad_trailer)
    assert forbidden_hits(bad_url)
