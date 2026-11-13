# -*- coding: utf-8 -*-
"""「黃金檔／摘要釘死」測試的 CPython 版本守衛（測試共用 helper；不是測試檔）。

為什麼有這個檔（BL-0342／BL-0453；證據 `docs/evidence/quality_batch1_delta_2026_11_13.md` §1.2-6）：
`tests/fixtures/alo_core_golden_before.json` 與數個「整頁模型逐格釘死」的測試，其預期值是在 **CPython 3.11** 錄的
（黃金檔檔頭 `python: 3.11.18`，CI 四條 lane 都固定 3.11）。**CPython 3.12 起內建 `sum()` 對 float 改用補償加總**，
`_build_alo2` 內 `sum(r["_value"] ...)` 在 `alo2_family/cost:near_tied_leaders_within_1e9` 情境差 1 ulp，只影響內部浮點欄
（`_current_pct`／`_diff`／`_in_total`），使用者可見文字相同；但逐位元組比對與 md5/sha256 摘要因此在非 3.11 直譯器上變紅。
這**不是**黃金檔漂移、**不是**程式退化 ⇒ **禁止重錄 Golden、禁止放寬比對**。

處置（三分支，決策集中在純函式 `decide`）：
  * `run`  ：直譯器 == 基準版本 ⇒ 測試**一字不變地照跑**（嚴格逐位元組比對）。
  * `skip` ：直譯器 != 基準版本、且不在 CI ⇒ 帶明確原因 skip（本機 3.12／3.13 開發用）。
  * `fail` ：直譯器 != 基準版本、且在 CI（`GITHUB_ACTIONS=="true"`）⇒ **失敗，不是 skip**（tripwire）：
             日後有人把 CI 升到 3.12+，Golden 守衛不得悄悄消失；需客戶 Decision Gate 重新基準，**不得自行重錄**。

⚠️ 這裡不放任何「讓 3.13 變綠」的捷徑：不改容差、不重算預期值、不用全域 conftest hook 自動 skip；
   使用方式只有一種 —— 在受影響的測試函式上加 `@baseline_python_only`。
⚠️ 比對只看 (major, minor)：3.11.x 之間 `sum()` 語意相同；基準常數須與黃金檔檔頭一致
   （`tests/test_py_baseline_guard.py` 會讀黃金檔檔頭交叉驗證，兩者漂移會紅）。
"""

from __future__ import annotations

import functools
import os
import sys

#: 黃金檔／摘要的基準直譯器 (major, minor)。黃金檔檔頭 `python: 3.11.18`；CI 固定 3.11.18。
BASELINE_PYTHON = (3, 11)

#: 判定 CI 的環境變數與其值（GitHub Actions 會設 `GITHUB_ACTIONS=true`）。
CI_ENV_VAR = "GITHUB_ACTIONS"
CI_ENV_VALUE = "true"

RUN = "run"
SKIP = "skip"
FAIL = "fail"

SKIP_REASON = (
    "BL-0342／BL-0453：黃金檔／摘要的基準是 CPython {baseline}（檔頭 python: 3.11.18）；"
    "目前直譯器 CPython {current}。CPython≥3.12 的內建 float sum() 改為補償加總，內部浮點欄（_current_pct／_diff／_in_total）"
    "差 1 ulp，使逐位元組／摘要比對變紅 —— 這不是行為退化。不得重錄 Golden、不得放寬比對；此測試只在基準版本直譯器（CI 為 3.11）執行。"
)
FAIL_MESSAGE = (
    "tripwire：CI 的直譯器是 CPython {current}，不是黃金檔／摘要的基準 CPython {baseline}（BL-0342／BL-0453）。"
    "CPython≥3.12 的 float sum() 補償加總會讓這些 Golden 測試產生 1 ulp 差異；不得在此靜默 skip。"
    "請不要自行重錄 Golden 或放寬比對 —— 升級 CI Python 版本、重新基準屬客戶 Decision Gate。"
)


def _mm(version) -> tuple:
    return (int(version[0]), int(version[1]))


def _fmt(version) -> str:
    return ".".join(str(int(x)) for x in tuple(version)[:2])


def decide(py_version, ci_flag, baseline=BASELINE_PYTHON) -> str:
    """純函式：('run'|'skip'|'fail')。`py_version`／`baseline` 取前兩個數字 (major, minor)；`ci_flag` 為 bool。"""
    if _mm(py_version) == _mm(baseline):
        return RUN
    return FAIL if ci_flag else SKIP


def current_python() -> tuple:
    """目前直譯器的 (major, minor)；獨立成函式讓自測可以假造。"""
    return (sys.version_info[0], sys.version_info[1])


def is_ci(environ=None) -> bool:
    """`GITHUB_ACTIONS == "true"`；`environ` 預設 `os.environ`。"""
    env = os.environ if environ is None else environ
    return env.get(CI_ENV_VAR) == CI_ENV_VALUE


def baseline_python_only(func):
    """裝飾器：只在基準直譯器執行測試本體；其餘依 `decide` skip 或 fail（見模組說明）。不改測試本體的任何斷言。

    以 `functools.wraps` 保留簽名，pytest 的 fixtures／parametrize 照常運作。"""
    import pytest   # 延後 import：helper 本身不強制依賴 pytest（但只在測試環境被使用）

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        cur = current_python()
        verdict = decide(cur, is_ci())
        if verdict == SKIP:
            pytest.skip(SKIP_REASON.format(baseline=_fmt(BASELINE_PYTHON), current=_fmt(cur)))
        if verdict == FAIL:
            pytest.fail(FAIL_MESSAGE.format(baseline=_fmt(BASELINE_PYTHON), current=_fmt(cur)), pytrace=False)
        return func(*args, **kwargs)

    wrapper.__baseline_python_only__ = True   # 供自測以 AST／屬性確認「真的有掛上」
    return wrapper
