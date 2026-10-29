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
- 只掃目前追蹤的檔案（內容與路徑名）；git 歷史中的既有出現**不改寫**（客戶裁示），本守衛不看歷史。
- **不涵蓋 PR title／PR body／commit message／branch name／issue／review comment**：
  這些不在 repo 檔案內，pytest 掃 working tree 達成不了（``PROJECT_RULES.md`` 12.3 第 3 點的
  其餘射程仍靠人工自查），**不得宣稱本守衛是完整的 machine enforcement**。
- 只有已登記進 ``_BANNED_DIGESTS`` 的姓名會被偵測；未登記的其他作者無法由本守衛證明為 0。
- 只比對 CJK n-gram；羅馬拼音、拆成非 CJK 字元等寫法不在射程內。
- 通用名詞「老師」本身不違規；只比對具體「姓氏＋老師」組合。
- 單一姓氏字（1 字）不入表：單字姓氏與一般文字大量重疊，必然誤報。
- 2 字「名」與各「姓＋老師」組合入表前已在 HEAD 實測 0 命中（含新分隔符正規化），
  未發現與一般用語碰撞；日後若某個 token 誤報，移除該雜湊並在此註明原因（不寫明文）。
- 正規化會移除分隔符號與括號引號，因此跨括號的相鄰字會被接起來比對 —— 這是刻意的
  （擋拆字繞過），代價是極少數跨標點的誤報，屆時以上條處理。
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
    "f37aa29ce45883b490b7ab1ee934634ecee0c02b4b7e8384e121033d9e9c53e7",  # 6: N2 名（繁）
    "25d62f08a54ff6c3a2be4db309276b3f607f75bcf4675a772788793d5b5a902a",  # 7: N2 名（簡）
    "2d34d7a6d918cf4b8bc7e489a841f56a0fb90b6a9b79721203196a8487700f7e",  # 8: N3 名（繁）
    "d81f20a7f58b0e41a35cb4d677441f1c11659eabf63b3176f11200120e889a3f",  # 9: N3 名（簡）
    "10b0a2d372d3fff088fce51386d21b7fff5c8ec851cc9ff50611b9db02ceccde",  # 10: N2 姓＋老師（繁）
    "95e5daf3bb5e1c41a3c9a608be736abfc23d4a7e6f3abc032146a67f61e1e1ec",  # 11: N2 姓＋老师（簡）
    "25cc69b9272df71edeaba72ceb11e67aba315bc5a743de0dca6320596bb0fda9",  # 12: N2 姓＋老师（混）
    "33324496e7242ffa9e5b1430b0e94ca3525196b86bbe3d5ecb9b3e47fdfb60fe",  # 13: N2 姓＋老師（混）
    "e111f027193cba59a44f6df1e62d439b5e3c54bb82e413883dcf1cbd321fd174",  # 14: N3 姓＋老師（繁）
    "db5992404723befb095f82a2f0cc49f84aef2231c3810ca27a854bbef757cad1",  # 15: N3 姓＋老师（簡）
    "5c427f164c790d7471e1da4f6ba03e30f240403f4cd9d73284cf0ee093bf0afa",  # 16: N3 姓＋老师（混）
    "13e67bd791e94addb3cddf48357b6360a35a2f88f4b76be741a31578a5a46859",  # 17: N3 姓＋老師（混）
)
_INDEX = {d: i for i, d in enumerate(_BANNED_DIGESTS)}

# 空白 + 常見零寬／格式字元 + 常見分隔符號與括號引號（NFKC 之後才套用，
# 故全形空白／全形括號已先轉成半形）。目的是擋「名・字」「名-字」「「名」字」這類拆字。
_STRIP_RE = re.compile(
    r"[\s\u200b\u200c\u200d\u2060\ufeff\u00ad"
    r"\u30fb\u00b7\u2027\u2022\-\u2010\u2011\u2012\u2013\u2014\u2015_/|\\"
    r"\u300c\u300d\u300e\u300f\u3010\u3011\u3014\u3015\u3008\u3009\u300a\u300b"
    r"()\[\]{}<>\"'\u201c\u201d\u2018\u2019]+"
)
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


def _normalize(line: str) -> str:
    return _STRIP_RE.sub("", unicodedata.normalize("NFKC", line))


def _line_hits(line: str, index: dict[str, int] | None = None) -> set[int]:
    if index is None:
        index = _INDEX
    norm = _normalize(line)
    hits: set[int] = set()
    for m in _CJK_RUN_RE.finditer(norm):
        run = m.group()
        for n in _NGRAM_LENGTHS:
            for i in range(len(run) - n + 1):
                d = hashlib.sha256(_SALT + run[i : i + n].encode("utf-8")).hexdigest()
                idx = index.get(d)
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
    assert _STRIP_RE.sub("", "甲\u200b 乙\u3000丙") == "甲乙丙"


def _scan(paths: list[Path], index: dict[str, int]) -> list[str]:
    violations: list[str] = []
    for path in paths:
        if path.resolve() == _SELF:
            continue
        text = _read_text(path)
        if text is None or not _CJK_RUN_RE.search(text):
            continue
        try:
            rel = path.relative_to(_REPO).as_posix()
        except ValueError:
            rel = path.name
        for lineno, line in enumerate(text.splitlines(), 1):
            for idx in sorted(_line_hits(line, index)):
                violations.append(f"{rel}:{lineno} (banned digest #{idx})")
    return violations


def test_positive_control_detects_split_synthetic_token(tmp_path):
    """內建正控：不存任何明文姓名，改用一個無害的合成字串當「禁字」，
    寫進暫存檔並用零寬字元／分隔符號／括號拆開，證明掃描器真的抓得到。"""
    synthetic = "測試甲乙"  # 無害合成 token，非任何人名
    digest = hashlib.sha256(_SALT + synthetic.encode("utf-8")).hexdigest()
    index = {digest: 0}
    samples = [
        "前文測試甲乙後文",
        "前文測\u200b試・甲-乙後文",
        "前文「測試」(甲)／乙後文",
        "前文測\u3000試 — 甲｜乙後文",
    ]
    f = tmp_path / "sample.md"
    f.write_text("\n".join(["無關的一行"] + samples), encoding="utf-8")
    got = _scan([f], index)
    assert got == [f"sample.md:{n} (banned digest #0)" for n in range(2, 2 + len(samples))]
    assert _scan([f], {}) == []


def _path_hits(rel: str, index: dict[str, int] | None = None) -> set[int]:
    """逐段（以 ``/`` 分隔）比對路徑，避免 ``_STRIP_RE`` 移除 ``/`` 後把相鄰目錄名的字接起來誤報。

    已知限制：單一路徑段內仍套用與內容相同的正規化（移除底線、連字號等），
    故同一檔名內以分隔符拆開的字會被接起來比對（刻意，擋拆字繞過）。
    """
    hits: set[int] = set()
    for seg in rel.split("/"):
        hits |= _line_hits(seg, index)
    return hits


def test_path_scan_positive_and_negative_control():
    """路徑掃描正控／負控：合成假名（非任何人名）。"""
    synthetic = "測試甲乙"
    digest = hashlib.sha256(_SALT + synthetic.encode("utf-8")).hexdigest()
    index = {digest: 0}
    assert _path_hits("docs/測試甲乙_notes.md", index) == {0}
    assert _path_hits("docs/測試-甲乙/x.md", index) == {0}
    assert _path_hits("docs/一般文件.md", index) == set()
    # 跨目錄相鄰字不得接起來誤報
    assert _path_hits("測試/甲乙/x.md", index) == set()


def test_no_external_author_names_in_tracked_paths():
    """路徑名（檔名／目錄名）同樣不得含已登記姓名。"""
    violations = []
    for path in _tracked_files():
        rel = path.relative_to(_REPO).as_posix()
        for idx in sorted(_path_hits(rel)):
            violations.append(f"<path #{idx}> (banned digest #{idx})")
    assert not violations, (
        "追蹤檔的路徑名含已登記姓名（只列摘要索引，不印原文）：\n" + "\n".join(violations)
    )


def test_no_external_author_names_in_tracked_files():
    violations = _scan(_tracked_files(), _INDEX)
    assert not violations, (
        "公開 repo 不得出現外部教材作者姓名（只列位置與雜湊索引，不印原文）：\n"
        + "\n".join(violations)
    )
