"""tests/test_public_repo_name_redaction.py — 公開 repo 外部教材作者姓名遮蔽守衛（2026-10-27）

目的
----
客戶規則（2026-10-27）：公開 repo 的任何追蹤檔（程式、註解、測試、fixture、文件）
不得出現外部投資教材作者／老師的真實姓名。本守衛掃 ``git ls-files`` 的所有文字檔，
命中即失敗，訊息只給 ``path:line`` 與雜湊索引，**永不印出原文**。

為什麼只存雜湊
--------------
本檔只保存「加鹽 sha256」摘要，不存任何明文姓名 —— 守衛本身若寫明文，就會變成
它要擋的那個違規（也會自我命中）。比對流程：

1. 每行做 NFKC 正規化，移除所有空白與零寬字元（避免用空格／零寬字元拆字繞過）；
2. 取每段連續 CJK 字元的 2~4 字 n-gram；
3. 每個 n-gram 以 ``_SALT + ngram`` 算 sha256，與 ``_BANNED_DIGESTS`` 比對。

⚠️ 誠實揭露：這些是公眾人物的 2~4 字短姓名，字元空間很小，雜湊**可被暴力窮舉還原**。
這是可接受的取捨 —— 目的只是不讓明文出現在檔案、grep 結果與 CI log 裡，
不是密碼學等級的保密。

如何新增一個名字
----------------
在本機（不要寫進任何會被 commit 的檔案、也不要貼進 PR／commit message）執行::

    python3 -c "import hashlib,unicodedata;print(hashlib.sha256(b'public-repo-name-redaction-v1:'+unicodedata.normalize('NFKC','<名字>').encode()).hexdigest())"

把輸出的十六進位字串加進 ``_BANNED_DIGESTS``（繁體／簡體變體各算一次），
註解只寫中性代號（N1/N2/...），**絕不 commit 明文**。長度須為 2~4 個 CJK 字元。

射程外（據實揭露）
------------------
- 只掃目前追蹤的檔案；git 歷史中的既有出現**不改寫**（客戶裁示），本守衛不看歷史。
- 只比對 CJK n-gram；羅馬拼音、拆成非 CJK 字元等寫法不在射程內。
- 通用名詞「老師」本身不違規；只比對具體「姓氏＋老師」組合。
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import unicodedata
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SELF = Path(__file__).resolve()

_SALT = b"public-repo-name-redaction-v1:"

# 只存雜湊，不存明文。註解只用中性代號。
_BANNED_DIGESTS: tuple[str, ...] = (
    "cc5cdcd7ec421eba28458d0d41426518cbf6862ac3380679ec61795bedec4eed",  # 0: N2 全名（繁）
    "b596a0f32e02341ebf8ba3cb1b192201e1c2889d0e0038bc0b65a9b15a4ef892",  # 1: N2 全名（簡）
    "6adf82d60c6e53cd06d319baaa17cbbe3443b7cbdf843e0e1f4040cf42334be6",  # 2: N3 全名（繁）
    "8c428f9cbfa0cbaff9b607d98a19972d7f47a8df80afe6124310dc64feb3ffdb",  # 3: N3 全名（簡）
    "d6326bb79e4b25da027e01211f8fb46f50a82cef5ba4d3df6a1903827c7fa348",  # 4: N1 姓＋老師（繁）
    "70ae24ca6a9aa53e4270fa9ae443ff3423fccbc91f15c44836c644e232d722a0",  # 5: N1 姓＋老师（簡）
)
_INDEX = {d: i for i, d in enumerate(_BANNED_DIGESTS)}

# 空白 + 常見零寬／格式字元
_STRIP_RE = re.compile(r"[\s​‌‍⁠﻿­]+")
# CJK 統一表意文字（含擴充 A）與相容表意文字
_CJK_RUN_RE = re.compile(r"[㐀-䶿一-鿿豈-﫿]{2,}")
_NGRAM_LENGTHS = (2, 3, 4)


def _tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=_REPO, capture_output=True, check=True
    ).stdout
    return [_REPO / p for p in out.decode("utf-8", "surrogateescape").split("\0") if p]


def _read_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:8192]:  # 二進位檔
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _line_hits(line: str) -> set[int]:
    norm = _STRIP_RE.sub("", unicodedata.normalize("NFKC", line))
    hits: set[int] = set()
    for m in _CJK_RUN_RE.finditer(norm):
        run = m.group()
        for n in _NGRAM_LENGTHS:
            for i in range(len(run) - n + 1):
                d = hashlib.sha256(_SALT + run[i : i + n].encode("utf-8")).hexdigest()
                idx = _INDEX.get(d)
                if idx is not None:
                    hits.add(idx)
    return hits


def test_digest_table_well_formed():
    assert len(set(_BANNED_DIGESTS)) == len(_BANNED_DIGESTS)
    for d in _BANNED_DIGESTS:
        assert re.fullmatch(r"[0-9a-f]{64}", d)


def test_detector_clean_sample_and_strip():
    """健全性：乾淨樣本 0 命中、空白與零寬字元會被移除（正控見下方說明）。

    正控無法在不寫明文的前提下內建；改由 PR 驗證「同一守衛在遮蔽前的 origin/main 上會失敗」。
    """
    assert _line_hits("外部投資教材「挑三揀四」法則") == set()
    assert _STRIP_RE.sub("", "甲​ 乙　丙") == "甲乙丙"


def test_no_external_author_names_in_tracked_files():
    violations: list[str] = []
    for path in _tracked_files():
        if path.resolve() == _SELF:
            continue
        text = _read_text(path)
        if text is None or not _CJK_RUN_RE.search(text):
            continue
        rel = path.relative_to(_REPO).as_posix()
        for lineno, line in enumerate(text.splitlines(), 1):
            if not _CJK_RUN_RE.search(line):
                continue
            for idx in sorted(_line_hits(line)):
                violations.append(f"{rel}:{lineno} (banned digest #{idx})")
    assert not violations, (
        "公開 repo 不得出現外部教材作者姓名（只列位置與雜湊索引，不印原文）：\n"
        + "\n".join(violations)
    )
