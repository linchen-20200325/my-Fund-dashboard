"""v19.291 — 全站「呼叫了但沒真的 import 到」bare name 自動掃描回歸網。

背景:v19.287/288 這一輪連續挖出 6 個同病灶的真 bug——`fetch_holdings` /
`fetch_risk_metrics` / `fetch_performance_wb01` / `fetch_nav` /
`_BANK_PLATFORM_CODES` / `_MORNINGSTAR_SECID_MAP` 全部是「模組內呼叫了某個
名字,但這個模組從未真的 import 這個名字」——每次呼叫都拋 `NameError`,又被
外層 `except Exception: print(...)` 完整吞掉,production 上只看到資料靜默
消失,直到 user 反覆截圖才逐一挖出來。

user 明確要求(2026-07-01):「以後如果又有人漏搬東西,測試會直接抓出來,
不用等到你在正式環境上踩到才發現」。

做法:用 `ruff --select F405`(possibly-undefined-name-from-star-import)
掃全站 production 程式碼,對每一筆命中動態 import 該模組並用 `hasattr()`
驗證這個名字是否**真的**能在該模組命名空間解析。凡是解析不到的,就是跟
v19.287/288 一樣的真 bug,測試直接 fail、列出檔名+行號+名字,不用等 user
在 production 上踩到才發現。

v19.340 補盲區:**加選 F821(plain undefined name)**。F405 只在「模組本身
有 star-import」時觸發 — `sources.py` 沒有任何 star-import,所以
`fetch_fund_multi_source` 內漏搬的 `_fetch_fund_single`(v19.248 拆檔遺留,
多來源聚合主入口每呼叫必 NameError)是純 F821,本網原本完全看不見,直到
第六份外部 review 這輪跑 F821 才抓到。F821 為「確定未定義」,直接列為
違規不需 hasattr 動態驗證(annotation-only 用法也一併要求真的 import,
防未來拿掉 future-annotations 或 runtime introspect 註解時爆)。

v19.425 補「白名單自我失效」洞:`_KNOWN_FALSE_POSITIVES` 目前**是空的**。
原本唯一一條 `("repositories/fund/nav_metrics.py", "Path")` 豁免的對象
(`_NAV_HISTORY_CACHE_DIR = Path("cache") / "nav_history" if False else None`
這行死碼)已於 v19.424 刪除,該檔改用 `_Path_nh`——豁免留著就變成一條
**指向不存在程式碼的永久白名單**:該檔 1000+ 行,日後任何人誤寫裸 `Path`
都會被它靜默放行。為根治這個病灶,本檔另加
`test_no_stale_false_positive_entries`:掃描期間記錄每條白名單**實際被用到
幾次**,一條都沒命中 = 豁免對象已消失,直接 fail 要求刪除。
(順帶更正 `repositories/fund/nav_metrics.py:141-142` 的歸因敘述——那顆雷
不是因為「測試因 Windows 缺 ruff 而長期未執行」才潛伏:本檔對
`FileNotFoundError` 是 `raise AssertionError` 紅燈,不是靜默通過;
真正讓它潛伏的就是這條白名單本身。該檔不在本次所有權內,僅在此記錄。)
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# 只掃 production 程式碼(§8.2 四層架構的實際目錄),排除 tests/scripts/cache/
# docs 等非執行路徑,避免 fixture/範例程式碼產生無意義的雜訊。
_SCAN_TARGETS = [
    "repositories", "services", "ui", "infra", "shared",
    "app.py", "fund_fetcher.py",
]

# (檔案路徑後綴, 名字) → 已人工確認為假警報(dead code / 不可達分支),不是真 bug。
# 新增例外前必須先確認「真的不可達」,不可為了讓測試通過就隨便加。
#
# ⚠️ v19.425:本集合目前**刻意保持空的**。前一條 nav_metrics.py 的 `Path` 豁免
#    在 v19.424 刪掉死碼後就失去對象,卻繼續掛著 → 等同對整個 1000+ 行的
#    `repositories/fund/nav_metrics.py` 開了一張裸 `Path` 的永久免死金牌。
#    新增任何條目時,請一併確認 `test_no_stale_false_positive_entries` 會保護你:
#    該測試會在豁免對象消失時直接 fail,不會再留下無聲的放行。
_KNOWN_FALSE_POSITIVES: set[tuple[str, str]] = set()

# 掃描期間實際命中的白名單條目(供 `test_no_stale_false_positive_entries` 判斷失效)。
_FP_HITS: set[tuple[str, str]] = set()

# `_scan()` 的 memo(ruff subprocess 只跑一次,兩個測試共用)。
_SCAN_CACHE: dict = {}


def _file_to_module(rel_path: str) -> str:
    """把 repo-relative 檔案路徑轉成可 import 的模組名。"""
    p = rel_path[:-3] if rel_path.endswith(".py") else rel_path
    return p.replace("/", ".")


def _scan() -> list[str]:
    """跑一次 ruff + 動態解析,回傳未解析名清單;順帶把命中的白名單記進 `_FP_HITS`。

    v19.425:抽成 helper 讓兩個測試共用**同一次**掃描(ruff subprocess + 逐檔
    isolated import 是本檔最貴的操作,跑兩次沒必要);結果 memoize 在
    `_SCAN_CACHE`,同一個 pytest process 內只跑一次。
    """
    if "result" in _SCAN_CACHE:
        return _SCAN_CACHE["result"]
    try:
        # v19.291 教訓:`ruff` 是獨立編譯執行檔安裝(console_script entry
        # point),不是 `python -m ruff` 可呼叫的模組 —— 用 `-m` 呼叫會直接
        # 印「No module named ruff」到 stderr、stdout 留空,若沒接住這個
        # failure mode,`json.loads("" or "[]")` 會靜默拿到空陣列,整個測試
        # 形同虛設(手動驗證抓到:拿掉 fetch_holdings import 後,`-m` 版本
        # 完全沒抓到,因為根本沒真的跑 ruff)。直接呼叫 `ruff` binary(靠 PATH
        # 解析,requirements-dev.txt 裝的 ruff 會提供這個 console script)。
        proc = subprocess.run(
            ["ruff", "check",
             # v19.340:F405(star-import 歧義)+ F821(plain 未定義,無 star-import
             # 模組的漏搬 import 只會以 F821 現形 — sources.py 案例)
             "--select", "F405,F821", "--output-format=json", *_SCAN_TARGETS],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
        )
    except FileNotFoundError as e:
        raise AssertionError(
            f"ruff 未安裝或無法執行——本測試需要 ruff 才能掃描,"
            f"請確認 requirements-dev.txt 已安裝:{e}"
        )
    except subprocess.TimeoutExpired:
        raise AssertionError("ruff --select F405 掃描逾時(60s),請檢查 ruff 是否卡住")

    # ruff exit code 1 = 有 finding(正常),0 = 無 finding,其他為真的執行錯誤
    if proc.returncode not in (0, 1):
        raise AssertionError(
            f"ruff 執行失敗(exit={proc.returncode}):stdout={proc.stdout[:300]!r} "
            f"stderr={proc.stderr[:300]!r}"
        )

    if not proc.stdout.strip():
        # exit=1 但 stdout 空 → ruff 沒有真的跑(例如 binary 損毀/參數錯誤),
        # 不能靜默當「0 個 finding」處理,否則整個測試形同虛設(§1 Fail Loud)。
        raise AssertionError(
            f"ruff 回傳 exit={proc.returncode} 但 stdout 是空的,不能視為"
            f"「掃描通過」——ruff 可能沒有真的執行:stderr={proc.stderr[:300]!r}"
        )

    try:
        findings = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise AssertionError(f"ruff JSON 輸出無法解析:{proc.stdout[:500]}")

    _name_re = re.compile(r"`([^`]+)` may be undefined")
    _name_re_f821 = re.compile(r"Undefined name `([^`]+)`")
    _unresolved: list[str] = []

    for f in findings:
        _code = f.get("code", "")
        _msg = f.get("message", "")
        m = (_name_re_f821.search(_msg) if _code == "F821"
             else _name_re.search(_msg))
        if not m:
            continue
        name = m.group(1)
        abs_path = Path(f["filename"])
        rel_path = str(abs_path.relative_to(REPO_ROOT))
        line = f["location"]["row"]

        if (rel_path, name) in _KNOWN_FALSE_POSITIVES:
            # v19.425:記錄「這條豁免今天真的有擋到東西」。沒被記錄到的條目 =
            # 豁免對象已消失 → `test_no_stale_false_positive_entries` 會 fail。
            _FP_HITS.add((rel_path, name))
            continue

        if _code == "F821":
            # v19.340:F821 = 該名字在模組任何 scope 皆解析不到(非 star-import
            # 歧義),ruff 已可確定 → 不需動態載入驗證,直接列違規。
            _unresolved.append(
                f"{rel_path}:{line} `{name}` — F821 未定義名(呼叫時 NameError;"
                f"是否拆檔漏搬 import?同 v19.248 sources.py 病灶)"
            )
            continue

        modname = _file_to_module(rel_path)
        file_path = REPO_ROOT / rel_path
        # v19.291 教訓:一開始用 `importlib.import_module()` + `importlib.reload()`
        # 驗證,但 `reload()` 會**就地替換** `sys.modules[modname]` 的真實模組
        # 物件——同一個 pytest process 裡,其他模組手上早持有的舊 function
        # reference(例如 `fund_orchestration.py` 頂部 `from
        # repositories.fund.nav_metrics import fetch_holdings` 抓到的那顆函式
        # 物件)跟 reload 後的新物件不再是同一個 object,直接弄壞了
        # `test_fetch_holdings_is_actually_importable_in_fund_orchestration`
        # 這個既有測試裡的 `O.fetch_holdings is NM.fetch_holdings` 身分斷言。
        # 改法:用 `spec_from_file_location` 建一份「用完即丟」的隔離模組,
        # 執行完 `hasattr()` 驗證後,不論成功或失敗都把 `sys.modules[modname]`
        # 還原成呼叫前的狀態,確保本測試對其他測試檔完全無副作用。
        _prior_mod = sys.modules.get(modname)
        try:
            spec = importlib.util.spec_from_file_location(modname, file_path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[modname] = mod
            try:
                spec.loader.exec_module(mod)
            finally:
                if _prior_mod is not None:
                    sys.modules[modname] = _prior_mod
                else:
                    sys.modules.pop(modname, None)
        except Exception as e:
            _unresolved.append(
                f"{rel_path}:{line} `{name}` — 模組本身 import 失敗:"
                f"{type(e).__name__}: {e}"
            )
            continue

        if not hasattr(mod, name):
            _unresolved.append(
                f"{rel_path}:{line} `{name}` — 無法在 `{modname}` 模組命名空間"
                f"解析,呼叫時會 NameError(是否忘記 import?)"
            )

    _SCAN_CACHE["result"] = _unresolved
    return _unresolved


def test_no_unresolved_bare_names_in_production_code():
    """全站掃描:任何「呼叫了但沒真的 import 到」的 bare name,直接 fail。

    v19.287/288 那 6 個真 bug,全部都會被這個測試抓到(已用 v19.291 之前
    的真實壞狀態手動驗證過:回退掉 fund_orchestration.py 的 import 後,
    本測試會確實抓到 fetch_holdings/fetch_risk_metrics 等名字解析失敗)。
    """
    _unresolved = _scan()
    assert not _unresolved, (
        "全站掃描抓到「呼叫了但沒真的 import 到」的 bare name"
        "(跟 v19.287/288 的 fetch_holdings/fetch_risk_metrics 同一種病):\n"
        + "\n".join(_unresolved)
    )


def test_no_stale_false_positive_entries():
    """v19.425:白名單條目**沒擋到任何東西** = 豁免對象已消失,必須刪掉。

    真實案例:`("repositories/fund/nav_metrics.py", "Path")` 豁免的死碼
    (`_NAV_HISTORY_CACHE_DIR = Path(...) if False else None`)在 v19.424 被
    刪除,該檔改用 `_Path_nh`,但豁免留著沒清 —— 從那一刻起,那條白名單
    就變成「對一個 1000+ 行檔案裡的裸 `Path` 永久靜默放行」的後門。
    白名單只該在**當下真的有假警報**時存在,對象不在了就是死規則(§8.1 step 6)。
    """
    _scan()   # 確保掃描已執行(同一 process 內 memoized,不會重跑 ruff)
    stale = _KNOWN_FALSE_POSITIVES - _FP_HITS
    assert not stale, (
        "以下白名單條目在本次掃描中一次都沒命中 —— 豁免對象已不存在,"
        "留著等於對該檔該名字永久靜默放行,請直接刪除條目:\n  "
        + "\n  ".join(f"{f} :: {n}" for f, n in sorted(stale))
    )
