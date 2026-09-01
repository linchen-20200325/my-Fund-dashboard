# -*- coding: utf-8 -*-
"""AST CI 守衛：每一個 `@*.cache_data` / `@*.cache_resource` 裝飾點都要被交代。

## 這條守的是什麼

`@st.cache_data` **對「回傳值」快取、對「拋出的例外」不快取**（streamlit 1.59.2 實測）。
而本 repo 的 L1 慣例是「失敗 → 回 (空 DataFrame, err 字串)」——於是**一次上游瞬斷會把
那個空值鎖滿整個 TTL**：畫面空白、按「強制重抓」也只是把同一份失敗快取再讀一次。
這違反 v3 憲法 §02「**只快取成功結果；失敗時退避，不連續轟炸來源**」與 §2.4
「超過 TTL 應重新抓取」，而一個被鎖住的空值正是 §1「錯誤的數字比沒有數字更危險」。

## 判準：每個裝飾點必須落在下列三類之一，否則 CI 紅燈

- **(a) `_RAISES`** —— 失敗路徑會 `raise`，例外穿過快取層不入快取。
- **(b) `_WHITELIST`** —— 已知未修，**附理由**（為什麼現在不修、卡在什麼前置）。
- **(c) `_NO_EXTERNAL_ROUNDTRIP`** —— 鏈路根本不對外往返，沒有「失敗被快取」這回事。

## 為什麼 (a) 要作者自己指名 raise 住在哪

跨模組自動追蹤「這條鏈會不會 raise」在本 repo 做不到：
`ui/helpers/v2_editor.py` 從 `repositories/policy_repository.py` import，而那是一個
**用 `globals()[name] = getattr(pkg, name)` 動態 re-export 的 shim** —— 沒有任何靜態
import 敘述可以跟。硬猜只會得到一個看起來有守、實際上猜錯就靜默放行的守衛。

故改為**作者宣告 + 機器查證**：(a) 類必須寫出「委派給哪個符號」與「那個符號住在哪個檔」，
本測試再用 AST 去那個檔裡確認 **`def <符號>` 真的含 `raise`**，並確認**裝飾函式真的呼叫
了那個符號**。兩端都對得上才算數。

⚠️ **突變測試（本檔存在的意義）**：把 `repositories/hot_money_repository.py` 的
`raise _FetchFailed(...)` 改回 `return (空 df, err)`，`test_raises_entries_really_raise`
**必須轉紅燈**。守不到東西的守衛等於沒有守衛。

## ⛔ 本檔守**不到**什麼（2026-09-01 稽核實測，誠實揭露）

本檔是**純形態守衛**：`test_raises_entries_really_raise` 用的是
`any(isinstance(n, ast.Raise) for n in ast.walk(target))` —— 它只問
「這個 `def` 裡**有沒有一個** `Raise` 節點」，**不問可達性、不問例外型別、
也不問它是不是長在失敗路徑上**。實測突變：

    M1  兩支 uncached 內所有 raise 全改回 return              → 2 條 FAILED ✅
    M2  只留 1 個 raise（其餘改回 return）                     → 11 passed ⛔
    M2b 真實失敗路徑全改 return，只塞
        `if days < 0: raise ValueError("unreachable")`        → 11 passed ⛔

M2b 與憲法 §-2 規則 6 的創始實證是同一個病（宣稱修好、實際是死碼、production 恆不觸發）
—— **而它當時就長在這個專門用來防該病的守衛裡**。

→ **補位的是 `tests/test_hot_money_failure_roundtrip.py`**：真 streamlit 下 patch 上游、
連呼 3 次、數「未快取實作」實際執行了幾次。M2b 在那一檔會轉紅。
**本檔負責「有沒有登記／登記表有沒有脫節」，那一檔負責「行為對不對」，兩者缺一不可。**
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent

# `tests/` 排除：測試自己的 fixture 快取不是 production 取數，鎖住也不會誤導使用者。
_SKIP_DIRS = {
    "tests", ".git", ".venv", "venv", "env", "node_modules",
    "build", "dist", "__pycache__", ".mypy_cache", ".pytest_cache",
}

# 根目錄 `conftest.py` 同屬測試基礎設施（它就是那個 pass-through stub 的產地），
# 與 `tests/` 同一個理由排除。
_SKIP_FILES = {"conftest.py"}

_CACHE_ATTRS = ("cache_data", "cache_resource")

# ── (a) 失敗會 raise ────────────────────────────────────────────────
# key: "<裝飾點檔案>::<裝飾函式名>"
# value: (委派符號, 該符號所在檔案, 理由)
#        委派符號為 "" → 表示 raise 就寫在裝飾函式自己的 body 裡。
_RAISES: dict[str, tuple[str, str, str]] = {
    "repositories/hot_money_repository.py::_cached_foreign_flow_series": (
        "_fetch_foreign_flow_series_uncached",
        "repositories/hot_money_repository.py",
        "內拋外譯：5 個無二義的失敗點 raise _FetchFailed，公開 wrapper 譯回 (df, err)。"
        "另 2 個「空有兩義」的分支（非交易日／無 Foreign 類別）刻意仍 return、照舊快取 —— "
        "連假週末真的就是沒有資料，改成 raise 會把 FinMind 免費額度燒到 402。",
    ),
    "repositories/hot_money_repository.py::_cached_usdtwd_series": (
        "_fetch_usdtwd_series_uncached",
        "repositories/hot_money_repository.py",
        "內拋外譯：兩個失敗點都無二義（上游拋例外／Yahoo 回空），一律 raise _FetchFailed。",
    ),
    # ⛔ ~~"ui/helpers/v2_editor.py::_cached_load_policy_v2"~~ 已於 2026-09-01
    #    移到 `_WHITELIST`（**有意識的更正，不是漏刪**）。舊登記理由寫
    #    「上游 load_policy_v2 讀取失敗即 raise PolicySheetError」——
    #    **實測推翻**：`repositories/policy/v2.py::load_policy_v2` 內層有
    #        try: ws = _with_quota_retry(sh.worksheet, title)
    #        except Exception: return empty
    #    → gspread 的 429 在**進到那個 raise 之前**就被吞成空 DataFrame，
    #    然後被 `@st.cache_data` 快取住（實測 3 次呼叫：上游只跑 1 次）。
    #    這與底下 `pool_repository` 白名單的理由是**一模一樣的形狀**
    #    （「訊號在快取層之前就死了」），卻被放進了 `_RAISES` —— 等於
    #    **把一個未修的點認證成已修**。理由見該白名單條目。
    "ui/helpers/v2_editor.py::_cached_list_policies": (
        "list_policy_worksheets",
        "repositories/policy/v2.py",
        "上游 list_policy_worksheets 失敗即 raise PolicySheetError，同上。",
    ),
}

# ── (b) 已知未修，附理由 ────────────────────────────────────────────
_WHITELIST: dict[str, str] = {
    "repositories/pool_repository.py::_cached_pool_map": (
        "待 #56 Batch 2；需先拆 _load_pool_map 的 `except → {}`（缺陷 #67）—— "
        "訊號在快取層之前就死了，這一層先改沒有意義。"
    ),
    "ui/tab5_data_guard.py::_cached_nh_coverage": (
        "待 #56 Batch 2；需先拆 services/nav_history_gs.py::load_points 內層的 "
        "`except → []`，且動工前置未解（gspread 跨呼叫冷卻）。"
    ),
    "ui/helpers/macro/ndc.py::_cached_ndc_score": (
        "憲法 §8.3.P `P-NDCCACHE-1` 指定由獨立一組裁決；且 L1 fetch_ndc_signal_history "
        "已自帶同為 15 分的 @_ttl_cache，只修 UI 這層改善 ≈ 0。"
    ),
    "ui/helpers/v2_editor.py::_cached_load_policy_v2": (
        "2026-09-01 由 _RAISES 移入（原登記為誤）。與 pool_repository 同形：訊號在快取層"
        "**之前**就死了 —— repositories/policy/v2.py::load_policy_v2 內層的 "
        "`except Exception: return empty`（`sh.worksheet` 那一段）會把 gspread 429 "
        "吞成空 DataFrame，於是被 @st.cache_data 快取住（實測 3 次呼叫上游只跑 1 次）。"
        "需先拆那個 except 才輪得到這一層，而那超出本批檔案邊界（§-1.5.3 C 禁止夾帶）。"
        "⚠️ 同檔的 _cached_list_policies 不同：list_policy_worksheets 沒有這層內吞，"
        "維持在 _RAISES。"
    ),
}

# ── (c) 鏈路無外部往返 ──────────────────────────────────────────────
_NO_EXTERNAL_ROUNDTRIP: dict[str, str] = {
    "ui/tab5_data_guard.py::_cached_nh_status": (
        "→ services/nav_history_gs.py::status，只讀 infra.config.get_secret(...)，"
        "完全不對外往返 —— 沒有「失敗結果被快取」這回事。"
    ),
}


def _git_tracked_py_files() -> "list[str] | None":
    """git **追蹤中**的 `.py`（`git ls-files --cached`）—— 也就是 CI 實際看得到的那一組。

    ⚠️ 為什麼不能用 `rglob`（2026-09-01 稽核指出）：`rglob` **不看 git**，
    任何人在工作區留一份 scratch / 備份 `.py`，都會被掃進來、然後因為「未歸類」
    而在本機把這條守衛弄紅。守衛應該守 **repo 的內容**，不是守某個人的工作區。

    ⚠️ **已知殘留（誠實揭露，不是漏想）**：一個**全新、尚未 `git add`** 的 `.py`
    不在這份清單裡，所以它新增的裝飾點要等到入 index 才會被看到。
    這是刻意的取捨 —— 本守衛是 **CI 閘門**，而 CI 的 checkout 裡只有被追蹤的檔案，
    讓兩邊看到同一組檔案，本機才不會出現「CI 綠、本機紅」這種無法重現的雜訊。
    **已追蹤檔案的未提交修改照樣看得到**（下面讀的是磁碟上的內容，不是 blob）。
    """
    import subprocess
    try:
        out = subprocess.run(
            ["git", "-C", str(_ROOT), "ls-files", "-z", "--cached", "--", "*.py"],
            capture_output=True, check=True, timeout=60,
        ).stdout.decode("utf-8")
    except Exception:            # 非 git checkout / 無 git → 退回 rglob（見下）
        return None
    return [p for p in out.split("\0") if p]


def _iter_py_files():
    _tracked = _git_tracked_py_files()
    if _tracked is None:
        # 降級模式：印一行讓人知道本次掃描可能含工作區殘留（不靜默切換行為）。
        print("[st-cache-guard] ⚠️ 取不到 git 檔案清單，退回 rglob —— "
              "工作區殘留的 .py 可能造成誤報")
        _rels = [p.relative_to(_ROOT).as_posix() for p in sorted(_ROOT.rglob("*.py"))]
    else:
        _rels = sorted(_tracked)
    for rel in _rels:
        parts = rel.split("/")
        if any(part in _SKIP_DIRS for part in parts):
            continue
        if rel in _SKIP_FILES:
            continue
        p = _ROOT / rel
        if not p.is_file():
            continue
        yield p, rel


def _cache_symbol_names(tree: ast.AST) -> set[str]:
    """本檔內所有「其實就是 `st.cache_data` / `cache_resource`」的區域名字。

    ⚠️ 2026-09-01 修（稽核實測）：原本的 docstring 誇口「別名不敏感」，
    但那只對**模組**別名成立（`@_st_mod.cache_data` ✅），對**函式**別名一律逃掉：

        M3  from streamlit import cache_data as memo ; @memo(ttl=60)   → 逃掉 ⛔
        M4  _cd = st.cache_data ; @_cd(ttl=60)                          → 逃掉 ⛔

    本函式把這兩種綁定收進來。迭代到定點，接得住 `a = st.cache_data` → `b = a` 的鏈。
    （目前 repo 內 M3/M4 皆 0 命中，這是**防未來**，不是修現況。）
    """
    names: set[str] = set(_CACHE_ATTRS)     # from streamlit import cache_data
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for a in node.names:
                    if a.name in _CACHE_ATTRS:
                        n = a.asname or a.name
                        if n not in names:
                            names.add(n)
                            changed = True
            elif isinstance(node, ast.Assign):
                v = node.value
                hit = ((isinstance(v, ast.Attribute) and v.attr in _CACHE_ATTRS)
                       or (isinstance(v, ast.Name) and v.id in names))
                if not hit:
                    continue
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name) and tgt.id not in names:
                        names.add(tgt.id)
                        changed = True
    return names


def _resolves_to_cache(node: ast.expr, names: set[str]) -> bool:
    """這個運算式最終是不是 `cache_data` / `cache_resource`？

    涵蓋（皆為 2026-09-01 稽核列出的繞道，實測原版全部逃掉）：
      · `st.cache_data` / `_st_mod.cache_data`（模組別名）
      · `memo` / `_cd`（函式別名，見 `_cache_symbol_names`）
      · `getattr(st, "cache_data")`（M5）
      · 上述任一種再被呼叫一層：`st.cache_data(ttl=60)`、`getattr(...)(...)`
    """
    if isinstance(node, ast.Attribute):
        return node.attr in _CACHE_ATTRS
    if isinstance(node, ast.Name):
        return node.id in names
    if isinstance(node, ast.Call):
        f = node.func
        if (isinstance(f, ast.Name) and f.id == "getattr" and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value in _CACHE_ATTRS):
            return True
        return _resolves_to_cache(f, names)
    return False


def _is_cache_decorator(dec: ast.expr, names: "set[str] | None" = None) -> bool:
    """裝飾點判定 —— 模組別名、函式別名、`getattr` 三種寫法都算。"""
    return _resolves_to_cache(dec, names if names is not None else set(_CACHE_ATTRS))


def _collect_sites() -> dict[str, ast.FunctionDef]:
    sites: dict[str, ast.FunctionDef] = {}
    for path, rel in _iter_py_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:  # noqa: PERF203 — 壞檔不該讓本守衛整條掛掉
            continue
        names = _cache_symbol_names(tree)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if any(_is_cache_decorator(d, names) for d in node.decorator_list):
                sites[f"{rel}::{node.name}"] = node
    return sites


def _find_def(rel_path: str, symbol: str) -> ast.FunctionDef | None:
    tree = ast.parse((_ROOT / rel_path).read_text(encoding="utf-8"), filename=rel_path)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol:
            return node
    return None


def _alias_map(rel_path: str) -> dict[str, str]:
    """`from X import foo as _f` → {"_f": "foo"}（含函式體內的 lazy import）。

    ⚠️ 沒有這一層，`ui/helpers/v2_editor.py` 的
    `from repositories.policy_repository import list_policy_worksheets as _lpw`
    會讓下面那條「裝飾函式有沒有真的呼叫登記的符號」誤判成脫節。
    """
    tree = ast.parse((_ROOT / rel_path).read_text(encoding="utf-8"), filename=rel_path)
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                if a.asname:
                    out[a.asname] = a.name.split(".")[-1]
    return out


def _called_names(fn: ast.AST, alias: dict[str, str] | None = None) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name):
                out.add(f.id)
            elif isinstance(f, ast.Attribute):
                out.add(f.attr)
    if alias:
        out |= {alias[n] for n in list(out) if n in alias}
    return out


# ════════════════════════════════════════════════════════════════════
# 測試
# ════════════════════════════════════════════════════════════════════
def test_every_cache_site_is_accounted_for():
    """新增任何一個 @*.cache_data 裝飾點，未歸類即 CI 紅燈。"""
    sites = set(_collect_sites())
    known = set(_RAISES) | set(_WHITELIST) | set(_NO_EXTERNAL_ROUNDTRIP)
    unaccounted = sorted(sites - known)
    assert not unaccounted, (
        "以下 @*.cache_data 裝飾點未被歸類：\n  " + "\n  ".join(unaccounted)
        + "\n\n請擇一：(a) 讓失敗路徑 raise 並登記進 _RAISES；"
        "(b) 附理由進 _WHITELIST；(c) 確認鏈路無外部往返後進 _NO_EXTERNAL_ROUNDTRIP。"
    )


def test_no_stale_registry_entries():
    """登記表不得留下已不存在的裝飾點 —— 否則它會從守衛退化成一張沒人維護的清單。"""
    sites = set(_collect_sites())
    known = set(_RAISES) | set(_WHITELIST) | set(_NO_EXTERNAL_ROUNDTRIP)
    stale = sorted(known - sites)
    assert not stale, f"登記表有不存在的裝飾點（已重構或改名？）：{stale}"


def test_registries_are_disjoint():
    """同一個裝飾點不得同時掛在兩類 —— 那會讓「它到底算哪一類」無法回答。"""
    pairs = [
        ("_RAISES", set(_RAISES)),
        ("_WHITELIST", set(_WHITELIST)),
        ("_NO_EXTERNAL_ROUNDTRIP", set(_NO_EXTERNAL_ROUNDTRIP)),
    ]
    for i, (na, a) in enumerate(pairs):
        for nb, b in pairs[i + 1:]:
            assert not (a & b), f"{na} 與 {nb} 重複登記：{sorted(a & b)}"


@pytest.mark.parametrize("key", sorted(_RAISES))
def test_raises_entries_really_raise(key):
    """⭐ 本檔的 fail-closed 主力：(a) 類宣告的 raise 必須真的存在。

    ⚠️ **突變測試就打在這一條**：把 hot_money 的 `raise _FetchFailed(...)` 改回
    `return (空 df, err)`，本條必須轉紅燈。
    """
    delegate, owner_rel, reason = _RAISES[key]
    assert reason.strip(), f"{key} 缺理由字串"

    site_rel, site_fn_name = key.split("::")
    site_fn = _collect_sites().get(key)
    assert site_fn is not None, f"{key} 不存在（登記表過期？）"

    if not delegate:
        # raise 直接寫在裝飾函式本體
        target = site_fn
    else:
        # ① 裝飾函式必須真的呼叫那個委派符號（不能只是登記表上寫爽的）
        called = _called_names(site_fn, _alias_map(site_rel))
        assert delegate in called, (
            f"{key} 未呼叫登記的委派符號 {delegate!r} —— "
            f"登記表與實作已脫節（{site_rel} 內實際呼叫：{sorted(called)}）"
        )
        target = _find_def(owner_rel, delegate)
        assert target is not None, f"{owner_rel} 內找不到 def {delegate}"

    has_raise = any(isinstance(n, ast.Raise) for n in ast.walk(target))
    assert has_raise, (
        f"{key} 登記為「失敗會 raise」，但 {owner_rel}::{delegate or site_fn_name} "
        f"內找不到任何 raise —— 失敗結果會被 @cache_data 鎖滿整個 TTL"
        f"（v3 憲法 §02「只快取成功結果」/ §2.4 / §1）。"
    )


def test_cache_decorator_is_only_used_via_at_syntax():
    """`cache_data` 只准以 `@` 裝飾語法出現 —— 否則本檔的登記表結構上看不到它。

    ⚠️ 2026-09-01 稽核實測的繞道（原版全部逃掉，目前 repo 內 0 命中，本條為防未來）：

        M6  _f = st.cache_data(ttl=60)(_impl)      # 不用 @，直接套用

    `_collect_sites()` 只看 `FunctionDef.decorator_list`，M6 這種寫法連被列舉的機會
    都沒有 —— 它不是「歸類錯」，是**根本不在候選集合裡**，而那正是本檔最危險的失效模式
    （一個看起來全綠、實際上什麼都沒看到的守衛）。故直接禁掉非 `@` 的用法。
    """
    offenders: list[str] = []
    for path, rel in _iter_py_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        names = _cache_symbol_names(tree)
        deco_ids: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                for d in node.decorator_list:
                    for sub in ast.walk(d):
                        deco_ids.add(id(sub))
        for node in ast.walk(tree):
            if id(node) in deco_ids:
                continue
            if isinstance(node, (ast.Attribute, ast.Name)) and \
                    not isinstance(getattr(node, "ctx", None), ast.Load):
                continue          # 賦值目標不是「使用」
            if isinstance(node, (ast.Attribute, ast.Name)) and \
                    _resolves_to_cache(node, names):
                offenders.append(f"{rel}:{getattr(node, 'lineno', '?')}")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id == "getattr" and len(node.args) >= 2 \
                    and isinstance(node.args[1], ast.Constant) \
                    and node.args[1].value in _CACHE_ATTRS:
                offenders.append(f"{rel}:{getattr(node, 'lineno', '?')}")
    assert not offenders, (
        "以下位置在 `@` 裝飾語法之外引用了 cache_data / cache_resource，"
        "本檔的登記表結構上看不到它們：\n  " + "\n  ".join(sorted(set(offenders)))
        + "\n\n請改回 `@<模組>.cache_data(...)` 的裝飾寫法並登記，"
          "或（若確有必要）在本測試就地說明並豁免。"
    )


@pytest.mark.parametrize("key", sorted(set(_WHITELIST) | set(_NO_EXTERNAL_ROUNDTRIP)))
def test_exemptions_carry_a_reason(key):
    """豁免必須附理由，且理由要能讓後人判斷「什麼時候可以移出」。"""
    reason = _WHITELIST.get(key) or _NO_EXTERNAL_ROUNDTRIP.get(key) or ""
    assert len(reason.strip()) >= 20, f"{key} 的豁免理由太短或缺漏：{reason!r}"
