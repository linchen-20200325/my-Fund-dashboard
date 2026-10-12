"""守衛：`docs/v2/CONSTITUTION.md` 是子法 1 原文的逐位元組存檔，不得被悄悄改寫。

來源：PR #837 分支 `docs/v2-constitution-governance` 的 head `5569d85`；
客戶 2026-10-12 核准存檔（存檔 commit `b1f9436`）。

⚠️ 本守衛只檢查「位元組有沒有變」，不檢查內容對不對 —— 原文本來就不得更正。
⚠️ 檔案不在也算失敗，不 skip：檔案消失和被改寫一樣，main 上的引用都會指不到原文。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_PATH = REPO_ROOT / "docs" / "v2" / "CONSTITUTION.md"
EXPECTED_SHA256 = "9c6bf1fdd3ac56d30f4c12e18d466bc7f05fc529bdb4b899d8dd7909527ea9d7"

_WHY = (
    "這是子法 1 原文的逐位元組存檔（#837 head 5569d85，客戶 2026-10-12 核准存檔），"
    "不得改寫；若要更動，須客戶裁示。"
)


def test_constitution_archive_exists():
    assert ARCHIVE_PATH.is_file(), (
        f"找不到 {ARCHIVE_PATH.relative_to(REPO_ROOT).as_posix()}。\n{_WHY}"
    )


def test_constitution_archive_is_byte_identical():
    assert ARCHIVE_PATH.is_file(), (
        f"找不到 {ARCHIVE_PATH.relative_to(REPO_ROOT).as_posix()}。\n{_WHY}"
    )
    actual = hashlib.sha256(ARCHIVE_PATH.read_bytes()).hexdigest()
    assert actual == EXPECTED_SHA256, (
        f"{ARCHIVE_PATH.relative_to(REPO_ROOT).as_posix()} 的 sha256 與存檔時不同：\n"
        f"  預期 {EXPECTED_SHA256}\n"
        f"  實際 {actual}\n"
        f"{_WHY}"
    )
