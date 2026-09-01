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
    "ui/helpers/v2_editor.py::_cached_load_policy_v2": (
        "load_policy_v2",
        "repositories/policy/v2.py",
        "上游 load_policy_v2 讀取失敗即 raise PolicySheetError，例外穿過快取層；"
        "caller 端 _load_policy_into_buf 接住後走 _show_quota_friendly 顯示。",
    ),
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
}

# ── (c) 鏈路無外部往返 ──────────────────────────────────────────────
_NO_EXTERNAL_ROUNDTRIP: dict[str, str] = {
    "ui/tab5_data_guard.py::_cached_nh_status": (
        "→ services/nav_history_gs.py::status，只讀 infra.config.get_secret(...)，"
        "完全不對外往返 —— 沒有「失敗結果被快取」這回事。"
    ),
}


def _iter_py_files():
    for p in sorted(_ROOT.rglob("*.py")):
        rel = p.relative_to(_ROOT)
        if any(part in _SKIP_DIRS for part in rel.parts):
            continue
        yield p, rel.as_posix()


def _is_cache_decorator(dec: ast.expr) -> bool:
    """別名不敏感：`@st.cache_data` / `@_st_mod.cache_data` / `@_st_pool.cache_data(...)` 都算。

    ⚠️ 刻意**不**寫死 `st.` —— `ui/helpers/macro/ndc.py` 用的是 `@_st_mod.cache_data`，
    寫死模組名的樣式結構上就掃不到它（憲法 §8.2.A.1 驗證段 ① 已就地記過這個教訓）。
    """
    node = dec.func if isinstance(dec, ast.Call) else dec
    if isinstance(node, ast.Attribute):
        return node.attr in ("cache_data", "cache_resource")
    if isinstance(node, ast.Name):
        return node.id in ("cache_data", "cache_resource")
    return False


def _collect_sites() -> dict[str, ast.FunctionDef]:
    sites: dict[str, ast.FunctionDef] = {}
    for path, rel in _iter_py_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:  # noqa: PERF203 — 壞檔不該讓本守衛整條掛掉
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if any(_is_cache_decorator(d) for d in node.decorator_list):
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


@pytest.mark.parametrize("key", sorted(set(_WHITELIST) | set(_NO_EXTERNAL_ROUNDTRIP)))
def test_exemptions_carry_a_reason(key):
    """豁免必須附理由，且理由要能讓後人判斷「什麼時候可以移出」。"""
    reason = _WHITELIST.get(key) or _NO_EXTERNAL_ROUNDTRIP.get(key) or ""
    assert len(reason.strip()) >= 20, f"{key} 的豁免理由太短或缺漏：{reason!r}"
