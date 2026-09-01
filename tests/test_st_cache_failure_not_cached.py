# -*- coding: utf-8 -*-
"""AST CI 守衛：**靜態掃得到的** `@*.cache_data` / `@*.cache_resource` 裝飾點都要被交代。

⚠️ **標題刻意不寫「每一個」**（2026-09-01 第二輪稽核指出，**有意識的更正，不是漏刪**）：
~~「每一個 `@*.cache_data` / `@*.cache_resource` 裝飾點都要被交代」~~ 是一句
**可以被三行程式碼證偽的全稱句** —— 只要把裝飾器名字動態組出來
（`getattr(st, "cache" + "_data")`），本檔就看不到它。那三行本輪已補上守衛
（N6/N7/N8，見 `_const_str`），但**下一種寫法永遠還在**：靜態分析對一個可以
`exec` 的語言不可能窮舉。本檔能做的是**提高繞過的成本**，不是保證沒有漏網。
對照憲法 §-1.5.1c 判定 2 的方法教訓：「能被一條 grep 推翻的全稱句，就不該寫進憲法」——
守衛的標題同理。

## 這條守的是什麼

`@st.cache_data` **對「回傳值」快取、對「拋出的例外」不快取**（streamlit 1.59.2 實測）。
而本 repo 的 L1 慣例是「失敗 → 回 (空 DataFrame, err 字串)」——於是**一次上游瞬斷會把
那個空值鎖滿整個 TTL**：畫面空白、按「強制重抓」也只是把同一份失敗快取再讀一次。
這違反 v3 憲法 §02「**只快取成功結果；失敗時退避，不連續轟炸來源**」與 §2.4
「超過 TTL 應重新抓取」，而一個被鎖住的空值正是 §1「錯誤的數字比沒有數字更危險」。

## 判準：**被掃到的**裝飾點必須落在下列三類之一，否則 CI 紅燈

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
import re
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
        # ⚠️ 2026-09-01 第二輪：整段重寫（**有意識的更正，不是漏刪**）。
        # 舊理由與 `bf9ddc2` 逐字相同，而 `f5f4a1d` 已經把它講的三件事全部推翻：
        #   ~~「5 個無二義的失敗點 raise」~~ → AST 實數 raise=8 / return=2；
        #   ~~「另 2 個（非交易日／無 Foreign 類別）刻意仍 return」~~ → 那兩個
        #      **就是這個 PR 改成 raise 的**；
        #   ~~「連假週末真的就是沒有資料」~~ → 正是同一個 PR 在檔頭加刪除線推翻的那句。
        # 也就是說：這張登記表在**它自己所屬的那個 PR 裡**變成假的，沒有人回頭看。
        # → 現行寫法**不寫任何可被 AST 證偽的計數**，只寫政策
        #   （`test_raises_reasons_state_policy_not_counts` 機械擋住計數）。
        "內拋外譯：失敗路徑 raise _FetchFailed 穿過 @st.cache_data 不入快取，"
        "公開 wrapper 再譯回既有的 (df, err) 形狀。"
        "例外是「沒有任何節流器」的失敗分支（body status 落在 NO_COOLDOWN_KINDS、"
        "或 fetch_url 回 None 但來源未進退避）—— 那些仍 return，由 TTL_30MIN 節流；"
        "若那些也 raise，就變成每次 rerun 真打一次上游，比改版前更糟。"
        "實際分支數與歸屬以 repositories/hot_money_repository.py 內的註解為準，"
        "本欄不重述數字（重述必然漂移，2026-09-01 已實證）。",
    ),
    "repositories/hot_money_repository.py::_cached_usdtwd_series": (
        "_fetch_usdtwd_series_uncached",
        "repositories/hot_money_repository.py",
        # ⚠️ 2026-09-01 第三輪重寫（**有意識的更正，不是漏刪**）。舊理由
        # ~~「內拋外譯：兩個失敗點都無二義（上游拋例外／Yahoo 回空），一律 raise _FetchFailed。」~~
        # 兩個問題：(1)「兩個」是**中文數字的計數宣稱**，穿過了本檔自己的計數禁令
        #   —— 也就是這條守衛在 HEAD 上放行了一句它本來就該擋的話；
        # (2)「一律 raise」自本輪起**為假**：上游拋例外那一支已改為 return
        #   （它一個節流器都沒有，raise 會變成每次 rerun 真打一次 Yahoo，
        #    實測 base [1,0,0] → 7a45c89 [1,1,1] → 本輪 [1,0,0]）。
        "內拋外譯：依節流不變式逐支判 —— Yahoo 回空（有 host 冷卻或上游 _ttl_cache "
        "接手）走 raise _FetchFailed 穿過 @st.cache_data；上游拋例外（validate_yf_close "
        "的 schema 違反，_ttl_cache 不存例外、fetch_url 已 _note_success）沒有任何節流器，"
        "故仍 return 由 TTL_10MIN 承擔。實際分支歸屬以 "
        "repositories/hot_money_repository.py 內的表格為準，本欄不重述數字。",
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


# 摺疊結果的長度上限(字元)。理由見 `_const_str` 內 `_STR_FOLD_MAX_LEN` 那一段:
# 兩道終止保險擋不收斂,這一道擋「收斂到很大的值」造成的記憶體爆掉。
_STR_FOLD_MAX_LEN = 4096


def _const_str(node: ast.expr, strs: dict) -> "str | None":
    """盡力把一個運算式摺成字串常數；摺不出來回 `None`。

    ⚠️ 這個函式存在的唯一理由:`getattr(st, X)` 的第二個參數**不一定是字面值**。
    2026-09-01 第二輪稽核實測的三種繞道,原版全部逃掉(各 12 passed):

        N6  _c6 = getattr(st, "cache" + "_data") ; @_c6(ttl=60)           ⛔
        N7  _NAME7 = "cache_data" ; _c7 = getattr(st, _NAME7) ; @_c7(...) ⛔
        N8  @getattr(st, "cache" + "_data")(ttl=60)                       ⛔

    根因是原版要求 `args[1]` 必須是 `ast.Constant` —— 洗成 `BinOp`(字串拼接)
    或 `Name`(變數)就穿過去。**N6 實測是真的能運作的快取**
    (3 次呼叫實際只執行 1 次、有 `.clear`),不是理論上的漏洞。

    ⛔ **本函式不宣稱窮舉,而且結構上不可能窮舉**:`"".join([...])`、
    `"cache_data"[::-1][::-1]`、`chr(99)+...`、`sys.modules`、`exec` 等
    任意運算都繞得過。靜態分析對一個可以動態組字串的語言,只能提高繞過的成本。
    **本檔的標題與判準措辭已據此改寫,不再使用「每一個裝飾點」這種可被三行程式碼
    證偽的全稱句**(2026-09-01 稽核指出)。
    """
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else None
    if isinstance(node, ast.Name):
        return strs.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        _l = _const_str(node.left, strs)
        _r = _const_str(node.right, strs)
        if _l is None or _r is None:
            return None
        # ⛔ 長度上限(2026-09-01 第三輪補;**有意識的新增,不是漏想**)——
        #    兩道終止保險擋的是「**不收斂**」,擋不住「**收斂到一個很大的值**」。
        #    `_A0 = "x"` 後接 k 行 `_Ai = _A(i-1) + _A(i-1)` 是 **2^k 成長**,
        #    **實測**(在本檔的 `_str_const_names` 上直接量):
        #        k=16 →      65,536 字元        k=20 →   1,048,576 字元 /  28 MB
        #        k=24 →  16,777,216 字元 / 82 MB(0.04s)
        #    外推約 30~35 行就足以把 CI runner 吃到 OOM-kill,
        #    而 `_iter_py_files()` **對每一個被追蹤的 `.py` 都跑一次**。
        #    這一行讓超長的摺疊直接放棄(回 `None` ＝ **保守漏放**,不是誤報)——
        #    與本檔整體取捨一致:靜態分析只提高繞過成本,不保證窮舉。
        #    上限遠大於任何真實的裝飾器名(`cache_resource` 才 14 字元)。
        if len(_l) + len(_r) > _STR_FOLD_MAX_LEN:
            return None
        return _l + _r
    if isinstance(node, ast.JoinedStr):          # 全常數段的 f-string
        parts = []
        for v in node.values:
            _p = _const_str(v, strs)
            if _p is None:
                return None
            parts.append(_p)
        return "".join(parts)
    return None


# 摺疊的迭代上限。鏈式拼接(`_A = "a"` → `_B = _A + "b"` → `_C = _B + "c"`)每多一層
# 就多一輪;5 層已遠超過任何合理的「把字串藏起來」寫法,而上限保證本函式必然終止。
_STR_FOLD_MAX_PASSES = 5


def _str_const_names(tree: ast.AST) -> dict:
    """`X = "..."`(含可摺疊的拼接)→ {"X": "..."}。多輪迭代,接得住鏈式拼接。

    ⚠️ **兩道終止保險,是縱深防禦,不是「缺一不可」**
    (2026-09-01 第三輪更正,**有意識的更正,不是漏刪** · 決策者:本修復組):
      1. **先到先贏,不覆寫已知的名字** —— 否則 `s = s + "x"` 這種
         自我參照的累加會讓值每一輪都變,`while changed` 永不收斂。
      2. **輪數上限** `_STR_FOLD_MAX_PASSES` —— 就算 (1) 哪天被改掉也不會掛住 CI。

    **突變實測(本輪跑的,不是推論)**:

        MUT-1  只拿掉 (1) 先到先贏          → 18 passed(13.5s)   ← 仍然終止
        MUT-2  只拿掉 (2) 輪數上限          → 18 passed(11.0s)   ← 仍然終止
        MUT-3  兩道**都**拿掉               → **跑不完(>2 分鐘 timeout)**

    → 上一版寫 ~~「**缺一不可**」~~ **太滿**:任一道單獨存在都足以終止,
    **只有兩道全拿掉才會不收斂**。而且那句話與**它自己的下一行**自相矛盾 ——
    第 2 點就寫著「就算 (1) 哪天被改掉也不會掛住 CI」,那正是「不是缺一不可」的意思。
    **保留兩道的理由仍然成立**(縱深防禦:任一道被後人改壞,另一道還在),
    被權衡掉的只有那句**強度宣稱**。
    ⚠️ 代價要講明:同一個名字被重新綁定成不同字串時,本函式**只認第一次**,
    可能因此漏判(＝**保守漏放**,不是誤報)。這與本檔整體的取捨一致:
    靜態分析只能提高繞過成本,見 `_const_str` 的 ⛔ 段。
    """
    out: dict = {}
    for _ in range(_STR_FOLD_MAX_PASSES):
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            _v = _const_str(node.value, out)
            if _v is None:
                continue
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id not in out:
                    out[tgt.id] = _v
                    changed = True
        if not changed:
            break
    return out


def _is_getattr_cache(node: ast.expr, strs: dict) -> bool:
    """`getattr(<任何東西>, <摺得出 cache_data/cache_resource 的運算式>)`？"""
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "getattr" and len(node.args) >= 2):
        return False
    return _const_str(node.args[1], strs) in _CACHE_ATTRS


def _cache_symbol_names(tree: ast.AST, strs: "dict | None" = None) -> set[str]:
    """本檔內所有「其實就是 `st.cache_data` / `cache_resource`」的區域名字。

    ⚠️ 2026-09-01 修（稽核實測）：原本的 docstring 誇口「別名不敏感」，
    但那只對**模組**別名成立（`@_st_mod.cache_data` ✅），對**函式**別名一律逃掉：

        M3  from streamlit import cache_data as memo ; @memo(ttl=60)   → 逃掉 ⛔
        M4  _cd = st.cache_data ; @_cd(ttl=60)                          → 逃掉 ⛔

    本函式把這兩種綁定收進來。迭代到定點，接得住 `a = st.cache_data` → `b = a` 的鏈。
    （目前 repo 內 M3/M4 皆 0 命中，這是**防未來**，不是修現況。）

    ⚠️ 2026-09-01 第二輪追加:`_c6 = getattr(st, "cache" + "_data")` 這種
    **經由 `getattr` 的綁定**也要收進來(N6 / N7)，見 `_const_str`。
    """
    strs = _str_const_names(tree) if strs is None else strs
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
                       or (isinstance(v, ast.Name) and v.id in names)
                       or _is_getattr_cache(v, strs))
                if not hit:
                    continue
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name) and tgt.id not in names:
                        names.add(tgt.id)
                        changed = True
    return names


def _resolves_to_cache(node: ast.expr, names: set[str],
                       strs: "dict | None" = None) -> bool:
    """這個運算式最終是不是 `cache_data` / `cache_resource`？

    涵蓋（皆為 2026-09-01 兩輪稽核列出的繞道，實測原版全部逃掉）：
      · `st.cache_data` / `_st_mod.cache_data`（模組別名）
      · `memo` / `_cd`（函式別名，見 `_cache_symbol_names`）
      · `getattr(st, "cache_data")`（M5）
      · **`getattr(st, "cache" + "_data")`（N6/N8）與
        `getattr(st, _NAME)`（N7）—— 第二個參數摺得出常數字串就算**
      · 上述任一種再被呼叫一層：`st.cache_data(ttl=60)`、`getattr(...)(...)`

    ⛔ **不是窮舉,也不可能窮舉** —— 理由與已知逃生路徑見 `_const_str`。
    """
    strs = {} if strs is None else strs
    if isinstance(node, ast.Attribute):
        return node.attr in _CACHE_ATTRS
    if isinstance(node, ast.Name):
        return node.id in names
    if isinstance(node, ast.Call):
        if _is_getattr_cache(node, strs):
            return True
        return _resolves_to_cache(node.func, names, strs)
    return False


def _is_cache_decorator(dec: ast.expr, names: "set[str] | None" = None,
                        strs: "dict | None" = None) -> bool:
    """裝飾點判定 —— 模組別名、函式別名、`getattr`（含拼接／變數）都算。"""
    return _resolves_to_cache(dec,
                              names if names is not None else set(_CACHE_ATTRS),
                              strs)


def _collect_sites() -> dict[str, ast.FunctionDef]:
    sites: dict[str, ast.FunctionDef] = {}
    for path, rel in _iter_py_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:  # noqa: PERF203 — 壞檔不該讓本守衛整條掛掉
            continue
        strs = _str_const_names(tree)
        names = _cache_symbol_names(tree, strs)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if any(_is_cache_decorator(d, names, strs) for d in node.decorator_list):
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
        strs = _str_const_names(tree)
        names = _cache_symbol_names(tree, strs)
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
                    _resolves_to_cache(node, names, strs):
                offenders.append(f"{rel}:{getattr(node, 'lineno', '?')}")
            elif isinstance(node, ast.Call) and _is_getattr_cache(node, strs):
                offenders.append(f"{rel}:{getattr(node, 'lineno', '?')}")
    assert not offenders, (
        "以下位置在 `@` 裝飾語法之外引用了 cache_data / cache_resource，"
        "本檔的登記表結構上看不到它們：\n  " + "\n  ".join(sorted(set(offenders)))
        + "\n\n請改回 `@<模組>.cache_data(...)` 的裝飾寫法並登記，"
          "或（若確有必要）在本測試就地說明並豁免。"
    )


def _reason_of(key: str) -> str:
    """三張登記表共用的理由取值（`_RAISES` 的理由在 tuple 第 3 格）。"""
    if key in _RAISES:
        return _RAISES[key][2]
    return _WHITELIST.get(key) or _NO_EXTERNAL_ROUNDTRIP.get(key) or ""


_ALL_REGISTRY_KEYS = sorted(set(_RAISES) | set(_WHITELIST) | set(_NO_EXTERNAL_ROUNDTRIP))


@pytest.mark.parametrize("key", _ALL_REGISTRY_KEYS)
def test_exemptions_carry_a_reason(key):
    """每一格登記都必須附理由，且理由要能讓後人判斷「什麼時候可以移出」。

    ⚠️ **2026-09-01 第二輪擴大射程（稽核指出的結構缺口）**：本條原本只跑
    `_WHITELIST` 與 `_NO_EXTERNAL_ROUNDTRIP`，**`_RAISES` 的理由字串是全 repo
    唯一沒有任何測試檢查其內容的一格** —— 於是它在自己所屬的那個 PR 裡爛掉
    （宣稱「5 個失敗點」而 AST 實數 8、宣稱「另 2 個仍 return」而那兩個正是被改掉的），
    整整一輪沒有人發現。**沒有被任何測試看著的登記，遲早會說謊。**
    """
    reason = _reason_of(key)
    assert len(reason.strip()) >= 20, f"{key} 的登記理由太短或缺漏：{reason!r}"


# 會漂移的計數措辭：`5 個` / `2 處` / `3 條` / `7 個失敗點` / `兩個` / `7 支` / `raise=8` …
#
# ⚠️ **2026-09-01 第三輪擴大（有意識的更正，不是漏刪 · 決策者：本修復組）**：
# 上一版只認 **阿拉伯／全形數字 + 五個量詞**，於是**它自己要擋的那種句子還活在 HEAD 上** ——
# `_RAISES["…::_cached_usdtwd_series"]` 寫著「內拋外譯：**兩個**失敗點都無二義……」，
# **中文數字整個穿過去**（該句在本輪已連同其內容一起改寫，見該格）。
#
# **實測 BYPASS 清單（上一版 regex，本輪逐一跑過）**：
#     兩個 / 五個 / 七個 / 數個 / 若干 / 7 支 / 7 項 / 7 點 / 7 次 / 共 3 支 / 4 項 / raise=8
# **突變驗證（MUT-F）**：把理由換成
#     「七個失敗點中的五個…另兩個…共 3 支分支、4 項例外」
# → 上一版 **18 passed 全綠**；本版 **1 failed**（正控制：換回「5 個…另 2 個」→ 兩版都紅）。
#
# ⛔ **射程仍然只到 `_RAISES` 的理由欄，這一點沒有變，也是本輪刻意不擴的**：
# `repositories/hot_money_repository.py` 兩支公開 docstring 裡的
# `7/7`、`3/7`、`2/2`、「4 個逐字未動」**沒有任何守衛看得到**（F2 那個射程錯誤就出在那一格）。
# **不擴的理由**：把它擴成「掃全 repo 每一份 docstring 的數字」是**另一個守衛**
# ——600+ 檔的誤報面完全不同，且會擋掉大量合法的量測值登記（憲法 §8.2.A.0 規則 4
# 允許「標了日期的量測值」）。**本輪改用內容面處理**：那四個數字本輪已**獨立重測過**
# （逐分支比對 base vs 本分支：dtype 7/7 變、訊息 3/7 變、4 個逐字未動、USDTWD 訊息 2/2 未變），
# 並在該 docstring 就地標明量測方法。**「那一格沒有守衛」這個缺口本身，登記不修。**
#
# ⚠️ **`一` 刻意排除在中文數字之外（保守漏放，不是漏想）**：`一次` / `一點` / `一種` /
# `一道` 在中文裡壓倒性地是**慣用語**而不是計數（本檔自己的理由欄就有
# 「每次 rerun 真打**一次**上游」）。第一版把 `一` 收進去，實測**當場誤報**該句。
# 代價是「只有一個失敗點」這種真的計數宣稱會漏掉 —— 故另補 `只有一…` / `僅一…`
# 兩個明確的計數句型。**這是刻意的取捨，寫在這裡是為了讓後人知道它漏了什麼。**
_COUNT_CLAIM = re.compile(
    r"(?:[0-9０-９]+|[二三四五六七八九十兩两廿卅百千數数幾几]|(?:只有|僅|仅)一)\s*"
    r"[個个處处條条筆笔支項项點点次道種种類类]"
    r"|\b(?:raise|return|except|branch|分支|失敗點)\s*[=＝:：]\s*[0-9]+"
    r"|若干"
)


@pytest.mark.parametrize("key", sorted(_RAISES))
def test_raises_reasons_state_policy_not_counts(key):
    """⭐ `_RAISES` 的理由**不得寫可被 AST 證偽的計數** —— 寫政策，不寫數字。

    ## 為什麼是「禁止寫數字」而不是「檢查數字對不對」

    檢查數字對不對，等於要本檔去定義「什麼叫一個失敗點」（`raise` 節點數？
    失敗分支數？`return` 的失敗分支算不算？），而那個定義一改，
    守衛與被守的東西就會再度漂移 —— **把一個會腐爛的宣稱換成另一個會腐爛的宣稱**。
    直接禁掉這種宣稱，理由欄就只剩「政策」，而政策不會因為多加一個分支而變假。

    ## 這一條擋的是什麼（實證，不是假想）

    `bf9ddc2` 寫下「5 個無二義的失敗點 raise……另 2 個刻意仍 return」，
    `f5f4a1d` 把那 2 個也改成了 raise、AST 實數變成 8 —— **同一個 PR 內、
    相隔一個 commit，這句話就變成假的**，而且它是一張**守衛用的登記表**。
    憲法 `infra/source_backoff.py::_BackoffRegistryProxy` 記載的教訓正是這個形狀：
    「更正措辭時只修被點名的那個載體，剩下的副本會繼續說謊。」
    """
    reason = _RAISES[key][2]
    hits = _COUNT_CLAIM.findall(reason)
    assert not hits, (
        f"{key} 的 _RAISES 理由含可被 AST 證偽的計數 {hits}：{reason!r}\n"
        f"請改寫成**政策**（什麼情況 raise、什麼情況 return、為什麼），"
        f"把實際數字留在被守的原始碼註解裡 —— 登記表重述數字必然漂移。"
    )


# 上一版 `_COUNT_CLAIM` 實測會放過的措辭（2026-09-01 第三輪逐一跑過）。
# 每一個都是**真的會漂移的計數宣稱**，本清單就是這條守衛的迴歸網。
_COUNT_CLAIM_MUST_CATCH = (
    "5 個失敗點", "8 處", "2 條",                    # 舊版就抓得到（正控制，防改壞）
    "兩個失敗點", "五個", "七個", "三種", "十個",       # 中文數字 —— 舊版全部放過
    "數個", "若干",                                  # 概數 —— 舊版全部放過
    "7 支分支", "7 項例外", "7 點", "7 次", "共 3 支", "4 項",   # 量詞不在舊版清單
    "raise=8", "分支=3",                             # AST 節點數的等號寫法
    "只有一個失敗點", "僅一處",                        # `一` 的明確計數句型
)

# 中文裡壓倒性是慣用語、不是計數的寫法 —— **不得**誤報。
# `每次 rerun 真打一次上游` 就活在本檔自己的 `_RAISES` 理由裡：
# 第三輪第一版把 `一` 收進數字類，**當場誤報了它**，故 `一X` 刻意排除（見 `_COUNT_CLAIM`）。
_COUNT_CLAIM_MUST_PASS = (
    "每次 rerun 真打一次上游", "一律 raise _FetchFailed", "一點都不快取",
    "由 TTL_30MIN 節流", "404/407 是 SSOT 明訂刻意不退避", "v2 的 429 重試",
)


@pytest.mark.parametrize("phrase", _COUNT_CLAIM_MUST_CATCH)
def test_count_claim_regex_catches_drifting_phrasings(phrase):
    r"""⭐ 守衛的**守衛**：`_COUNT_CLAIM` 自己要抓得到它宣稱要擋的那些寫法。

    ## 為什麼需要這一條（2026-09-01 第三輪稽核實證，不是假想）

    上一版的 regex 是 `[0-9０-９]+\s*[個个处處條条筆笔]` —— 只認**阿拉伯／全形數字**
    加**五個量詞**。實測 BYPASS：`兩個` / `五個` / `數個` / `若干` / `7 支` / `7 項` /
    `7 次` / `raise=8` …

    **而它要擋的那種句子，當時就活在 HEAD 上**：
    `_RAISES["…::_cached_usdtwd_series"]` 寫著「內拋外譯：**兩個**失敗點都無二義……」。
    也就是說：**一條專門用來擋計數宣稱的守衛，放行了它正下方那一格裡的計數宣稱**，
    整整一輪沒有人發現 —— 與它自己 docstring 裡記載的病史是同一個形狀。

    **突變驗證（MUT-F）**：把理由換成
    「七個失敗點中的五個…另兩個…共 3 支分支、4 項例外」
    → 上一版 **18 passed 全綠**；本版 **1 failed**。
    """
    assert _COUNT_CLAIM.findall(phrase), (
        f"_COUNT_CLAIM 放過了一句會漂移的計數宣稱：{phrase!r}\n"
        f"這正是它存在的理由 —— 每一次放寬都要先問「它還抓得到這張清單嗎」。"
    )


@pytest.mark.parametrize("phrase", _COUNT_CLAIM_MUST_PASS)
def test_count_claim_regex_does_not_flag_idioms(phrase):
    """反向鎖：`_COUNT_CLAIM` **不得**誤報中文慣用語，否則沒有人寫得出合格的理由。

    誤報比漏報更糟：漏報只是守不到，誤報會逼作者為了過 CI 去改一句本來正確的話。
    """
    assert not _COUNT_CLAIM.findall(phrase), (
        f"_COUNT_CLAIM 誤報了一句慣用語：{phrase!r} → {_COUNT_CLAIM.findall(phrase)}"
    )


def test_const_folding_refuses_to_build_giant_strings():
    """⭐ 常數摺疊器不得被一段 `.py` 撐爆記憶體（2026-09-01 第三輪補）。

    ## 這是一個 DoS，不是理論問題

    `_str_const_names` 的兩道終止保險擋的是「**不收斂**」，
    **擋不住「收斂到一個非常大的值」**。`_A0 = "x"` 後接 k 行
    `_Ai = _A(i-1) + _A(i-1)` 是 **2^k 成長**。**本輪實測**（直接量 `_str_const_names`）：

        k=16 →      65,536 字元            k=20 →   1,048,576 字元 /  28 MB
        k=24 →  16,777,216 字元 / 82 MB    → 外推 k≈30~35 足以 OOM-kill CI runner

    而 `_iter_py_files()` **對每一個被追蹤的 `.py` 都跑一次**這個摺疊器 ——
    也就是說，任何人只要往 repo 裡塞一個約 35 行的檔案，就能讓 CI 整台掛掉。

    修法是 `_const_str` 內一行長度上限（`_STR_FOLD_MAX_LEN`），
    超過即回 `None`（＝**保守漏放**，不是誤報）。上限遠大於任何真實的裝飾器名
    （`cache_resource` 才 14 字元）。

    突變：拿掉那一行 → 本條的 `assert` 會拿到一個 2^24 長度的字串而轉紅。
    """
    src = '_A0 = "x"\n' + "".join(f"_A{i} = _A{i-1} + _A{i-1}\n" for i in range(1, 25))
    folded = _str_const_names(ast.parse(src))
    biggest = max((len(v) for v in folded.values()), default=0)
    assert biggest <= _STR_FOLD_MAX_LEN, (
        f"常數摺疊產生了 {biggest:,} 字元的字串（上限 {_STR_FOLD_MAX_LEN:,}）—— "
        f"2^k 成長的拼接鏈可以用約 35 行把 CI runner 吃到 OOM。"
    )
    # 正控制：上限不得大到把正常的裝飾器名也擋掉
    ok = _str_const_names(ast.parse('_N = "cache" + "_data"\n'))
    assert ok.get("_N") == "cache_data", f"上限訂太低，連正常摺疊都壞了：{ok}"
