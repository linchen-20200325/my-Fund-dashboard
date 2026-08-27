"""tests/test_no_direct_main_push_scripts.py — 守衛：`scripts/` 底下不得存在「直推 main」的腳本。

## 由來（2026-08-27，客戶裁示）

> 「quick_merge.sh 處置：依憲法規範，一律走標準 PR + CI 綠燈與獨立稽核驗收，
>  **嚴禁繞過 PR 直推 main**。」

被裁示禁止的 `scripts/quick_merge.sh` 已整檔刪除。**但刪一個檔案擋不住下一個人再寫一個** ——
本守衛就是為了讓「再寫一個」在 CI 當場紅燈，而不是等到它已經把 code 推上 main 才被發現。

該腳本原本的檔頭還寫著「用途（**CLAUDE.md §4 例外**）」，而 `CLAUDE.md §4` 是
「計算層（Computation Correctness）」，**那條例外從來不存在**；最接近的 `PROCESS.md §4`
（Auto-Ship）要求的更是**相反**的事：「必須使用 `gh pr create --fill` 建立請求，並主動執行
`gh pr merge <PR號碼> --merge --delete-branch`」。
→ 一句假引用就能讓一個違憲工具在 repo 裡合法存在兩個月。本守衛不看註解怎麼寫，只看**它做什麼**。

## 涵蓋範圍

`scripts/` 底下的 shell 腳本（`*.sh`，含無副檔名但帶 shebang 的可執行檔），禁止：

1. 明寫推 main / master：`git push ... origin main`、`... origin HEAD:main`、`... origin master` 等；
2. **裸 `git push` 但腳本內先 `git checkout main`** —— 這是 `quick_merge.sh` 用的形狀，
   單看 `git push` 那行完全無害，要合起來看才成立。

## ⚠️ 刻意**不**涵蓋 `.github/workflows/`（寫在這裡，避免下一個人誤以為有保護網）

本守衛**不掃** GitHub Actions workflow。這是有意識的取捨，不是漏掉：

- `.github/workflows/update_macro_history.yml` 有一個**裸 `git push`** —— cron 在 main 上寫入
  總經歷史增量快照（commit message 帶 `[skip ci]`）。那是**既有、獨立授權的資料快取自動化**，
  不是「繞過 PR 交付程式碼」，客戶的裁示射程不及於它。
- `.github/workflows/export_db.yml` 是 `git push -f origin _pub:data` —— 推的是 `data` 分支，
  **不是 main**。
- 若把 workflow 一起掃，本守衛第一天就會紅在 `update_macro_history.yml` 上，
  逼下一個人要嘛放寬判定、要嘛加一份白名單 —— 那正是 `CLAUDE.md §8.2.A` 點名要防的
  「未經登錄的軟例外」溫床，最後守衛會被改到守不住東西。
- 且 workflow 檔本身的每一次修改都要走 PR，已有一道 gate。

**所以：本守衛只保護「開發者手動執行的 shell 工具」這一面。**
若日後要把 workflow 也納入，必須同時處理上述兩個既有正當用途，不要靠放寬 regex 蒙混過去。

## Test Liveness（`PROCESS.md §4`）

`scripts/` 不存在、或一個 shell 腳本都掃不到 → **fail 而不是 skip**。
「掃不到東西所以通過」與「真的沒有違規」在總結行上長得一模一樣，那等於這個測試不存在。
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

# 明寫推主線分支。涵蓋 `git push origin main` / `git push -u origin main`
# / `git push origin HEAD:main` / `git push origin main:main` 等變形。
_EXPLICIT_MAIN_PUSH = re.compile(
    r"""git\s+push\b        # git push
        (?:\s+-{1,2}[\w-]+)*  # 任意 flag（-u / --force / --set-upstream …）
        \s+\S+                # remote（origin / upstream / URL …）
        \s+(?:HEAD:)?         # 可選的 HEAD:
        (?:main|master)\b     # 主線分支名
    """,
    re.VERBOSE,
)

# 裸 push（沒指定 refspec）——單獨看無害，但若腳本內先切到 main 就等於推 main。
_BARE_PUSH = re.compile(r"git\s+push\s*(?:$|[;&|#])", re.MULTILINE)
_CHECKOUT_MAIN = re.compile(r"git\s+checkout\s+(?:-\S+\s+)*(?:main|master)\b")


def _shell_scripts() -> list[Path]:
    """`scripts/` 底下所有 shell 腳本（.sh，或無副檔名但帶 sh/bash shebang）。"""
    found: list[Path] = []
    for path in sorted(SCRIPTS_DIR.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix == ".sh":
            found.append(path)
            continue
        if path.suffix == "":
            try:
                first = path.open("r", encoding="utf-8", errors="replace").readline()
            except OSError:
                continue
            if first.startswith("#!") and ("sh" in first or "bash" in first):
                found.append(path)
    return found


def _strip_comments(text: str) -> str:
    """去掉 `#` 註解，只留實際會執行的部分。

    守衛的對象是**行為**不是說明文字 —— 檔頭寫「大功能變更仍走 PR：gh pr create …」
    這種說明句不該讓守衛紅；反過來，把 `git push origin main` 藏進註解也不該讓它變綠
    （藏進註解就不會執行，本來就無害）。
    """
    out = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        # 行尾註解：保守處理，只切掉前面有空白的 `#`
        out.append(re.split(r"\s#", line, maxsplit=1)[0])
    return "\n".join(out)


def test_scripts_dir_is_scannable() -> None:
    """Liveness：掃不到東西要紅，不能靜默通過。"""
    assert SCRIPTS_DIR.is_dir(), f"scripts/ 不存在：{SCRIPTS_DIR}——本守衛失去掃描對象，視同失效"
    scripts = _shell_scripts()
    assert scripts, (
        f"{SCRIPTS_DIR} 底下掃不到任何 shell 腳本。"
        "若確實已全部移除，請連同本守衛一起重新評估；"
        "在那之前『0 個檔案所以通過』等於這條測試不存在。"
    )


def test_no_script_pushes_directly_to_main() -> None:
    """`scripts/` 內不得有繞過 PR 直推 main 的腳本（客戶 2026-08-27 裁示）。"""
    violations: list[str] = []

    for path in _shell_scripts():
        body = _strip_comments(path.read_text(encoding="utf-8", errors="replace"))
        rel = path.relative_to(REPO_ROOT)

        if _EXPLICIT_MAIN_PUSH.search(body):
            violations.append(f"{rel}：明寫 `git push … main/master`")
        elif _BARE_PUSH.search(body) and _CHECKOUT_MAIN.search(body):
            violations.append(
                f"{rel}：先 `git checkout main` 再裸 `git push` —— 等同直推 main"
            )

    assert not violations, (
        "偵測到繞過 PR 直推 main 的腳本：\n  "
        + "\n  ".join(violations)
        + "\n\n客戶 2026-08-27 裁示：一律走標準 PR + CI 綠燈與獨立稽核驗收，嚴禁繞過 PR 直推 main。"
        "\n正規流程見 `PROCESS.md §4` Auto-Ship："
        "`gh pr create --fill` → CI 綠 + 稽核通過 → `gh pr merge <PR號碼> --merge --delete-branch`。"
        "\n（前例：`scripts/quick_merge.sh`，檔頭以不存在的「CLAUDE.md §4 例外」自我授權，已於 2026-08-27 刪除。）"
    )
